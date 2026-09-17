"""MetaMask-backbone on-chain execution (OPTIONAL, disabled by default).

"MetaMask as the backbone" in bot terms: the bot signs transactions with the
same secp256k1 private key your MetaMask wallet uses, and routes swaps
through the 0x Swap API — the aggregator MetaMask Swaps itself uses under
the hood. Export a key from MetaMask (a fresh, small, dedicated hot wallet —
never your main one) into the env var named in config.

Entry = sell the chain's native token, buy the target token (no allowance
needed for native). Exit = sell the token back for native, approving the 0x
AllowanceHolder for exactly the amount sold, each time — never infinite.

Safety model:
  * live trading requires BOTH config `execution.live: true` AND the env var
    CRYPTOBOT_ARM_LIVE=yes — belt and suspenders against accidental sends;
  * per-trade notional is capped here again, independent of the risk layer;
  * slippage is bounded on every quote;
  * web3/eth-account import lazily so paper mode needs neither.

Solana pairs are scan/paper only: MetaMask + 0x are EVM, so live execution
covers the EVM chains mapped below.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ZEROX_BASE = "https://api.0x.org"

# 0x convention for the chain's native gas token
NATIVE = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

# chainId map for the chain names DexScreener uses (EVM only)
CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
    "bsc": 56,
}

# CoinGecko ids for each chain's native token, for USD sizing of entries
NATIVE_GECKO_IDS = {
    "ethereum": "ethereum",
    "base": "ethereum",
    "arbitrum": "ethereum",
    "optimism": "ethereum",
    "polygon": "polygon-ecosystem-token",
    "bsc": "binancecoin",
}

_ERC20_MIN_ABI = [
    {"name": "decimals", "outputs": [{"type": "uint8"}], "inputs": [],
     "stateMutability": "view", "type": "function"},
    {"name": "approve", "outputs": [{"type": "bool"}],
     "inputs": [{"name": "spender", "type": "address"},
                 {"name": "amount", "type": "uint256"}],
     "stateMutability": "nonpayable", "type": "function"},
    {"name": "allowance", "outputs": [{"type": "uint256"}],
     "inputs": [{"name": "owner", "type": "address"},
                 {"name": "spender", "type": "address"}],
     "stateMutability": "view", "type": "function"},
]


@dataclass
class WalletConfig:
    live: bool = False
    private_key_env: str = "CRYPTOBOT_PRIVATE_KEY"
    zerox_api_key_env: str = "CRYPTOBOT_0X_API_KEY"
    rpc_urls: dict[str, str] = field(default_factory=dict)  # chain -> RPC
    max_trade_usd: float = 50.0
    max_slippage: float = 0.02


class WalletExecutor:
    """Buys and sells DEX tokens via 0x quotes signed with a local key."""

    def __init__(self, cfg: WalletConfig):
        self.cfg = cfg
        self._armed = (
            cfg.live and os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        )
        self._key = os.environ.get(cfg.private_key_env, "")
        if cfg.live and not self._armed:
            logger.warning(
                "execution.live is true but CRYPTOBOT_ARM_LIVE!=yes — staying in dry-run"
            )
        if self._armed and not self._key:
            logger.warning("live armed but no private key in $%s — staying in dry-run",
                           cfg.private_key_env)
            self._armed = False

    @property
    def armed(self) -> bool:
        return self._armed

    def supports(self, chain: str) -> bool:
        return chain in CHAIN_IDS

    # -- 0x quotes ---------------------------------------------------------

    async def _quote(self, chain: str, sell_token: str, buy_token: str,
                     sell_amount_raw: int, taker: Optional[str]) -> Optional[dict]:
        headers = {"0x-version": "v2"}
        if key := os.environ.get(self.cfg.zerox_api_key_env, ""):
            headers["0x-api-key"] = key
        params: dict[str, Any] = {
            "chainId": CHAIN_IDS[chain],
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": str(sell_amount_raw),
            "slippageBps": int(self.cfg.max_slippage * 10_000),
        }
        if taker:
            params["taker"] = taker
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{ZEROX_BASE}/swap/allowance-holder/quote",
                    params=params, headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("0x quote failed on %s: %s", chain, exc)
            return None

    # -- high-level entry / exit ------------------------------------------

    async def buy(self, chain: str, token_address: str, notional_usd: float,
                  native_price_usd: float) -> Optional[str]:
        """Swap native -> token for ~notional_usd. Returns tx hash or None."""
        if not self.supports(chain):
            logger.info("chain %r not EVM/0x — paper only", chain)
            return None
        if notional_usd > self.cfg.max_trade_usd:
            logger.warning("buy %.2f exceeds wallet cap %.2f — refusing",
                           notional_usd, self.cfg.max_trade_usd)
            return None
        if native_price_usd <= 0:
            logger.warning("no native price for %s — cannot size entry", chain)
            return None
        sell_raw = int(notional_usd / native_price_usd * 10 ** 18)

        if not self._armed:
            logger.info("[dry-run] would buy ~$%.2f of %s on %s (native -> token)",
                        notional_usd, token_address[:10], chain)
            return None

        w3, acct = self._connect(chain)
        if w3 is None:
            return None
        quote = await self._quote(chain, NATIVE, token_address, sell_raw, acct.address)
        if not quote:
            return None
        return await asyncio.to_thread(self._broadcast, w3, acct, chain, quote)

    async def sell(self, chain: str, token_address: str,
                   qty_tokens: float) -> Optional[str]:
        """Swap token -> native for the full position quantity."""
        if not self.supports(chain):
            return None
        if not self._armed:
            logger.info("[dry-run] would sell %.6g of %s on %s (token -> native)",
                        qty_tokens, token_address[:10], chain)
            return None

        w3, acct = self._connect(chain)
        if w3 is None:
            return None

        def _prepare() -> Optional[int]:
            token = w3.eth.contract(
                address=w3.to_checksum_address(token_address), abi=_ERC20_MIN_ABI
            )
            decimals = token.functions.decimals().call()
            return int(qty_tokens * 10 ** decimals)

        sell_raw = await asyncio.to_thread(_prepare)
        if not sell_raw:
            return None
        quote = await self._quote(chain, token_address, NATIVE, sell_raw, acct.address)
        if not quote:
            return None

        # Approve the 0x AllowanceHolder for exactly this amount if needed.
        allowance_issue = ((quote.get("issues") or {}).get("allowance")) or {}
        spender = allowance_issue.get("spender")
        if spender:
            ok = await asyncio.to_thread(
                self._approve, w3, acct, chain, token_address, spender, sell_raw
            )
            if not ok:
                return None
        return await asyncio.to_thread(self._broadcast, w3, acct, chain, quote)

    # -- signing plumbing (sync, run in threads) ---------------------------

    def _connect(self, chain: str):
        rpc = self.cfg.rpc_urls.get(chain)
        if not rpc:
            logger.warning("no RPC configured for chain %r", chain)
            return None, None
        try:
            from eth_account import Account  # lazy: optional dependency
            from web3 import Web3
        except ImportError:
            logger.error("web3/eth-account not installed — pip install web3")
            return None, None
        return Web3(Web3.HTTPProvider(rpc)), Account.from_key(self._key)

    def _approve(self, w3, acct, chain: str, token_address: str,
                 spender: str, amount: int) -> bool:
        try:
            token = w3.eth.contract(
                address=w3.to_checksum_address(token_address), abi=_ERC20_MIN_ABI
            )
            current = token.functions.allowance(
                acct.address, w3.to_checksum_address(spender)
            ).call()
            if current >= amount:
                return True
            tx = token.functions.approve(
                w3.to_checksum_address(spender), amount
            ).build_transaction({
                "from": acct.address,
                "nonce": w3.eth.get_transaction_count(acct.address),
                "gasPrice": w3.eth.gas_price,
                "chainId": CHAIN_IDS[chain],
            })
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            logger.info("approved %s for %d units", spender[:10], amount)
            return True
        except Exception:
            logger.exception("approval failed on %s", chain)
            return False

    def _broadcast(self, w3, acct, chain: str, quote: dict) -> Optional[str]:
        try:
            txq = quote.get("transaction") or {}
            tx = {
                "from": acct.address,
                "to": w3.to_checksum_address(txq["to"]),
                "data": txq["data"],
                "value": int(txq.get("value") or 0),
                "gas": int(txq.get("gas") or 500_000),
                "gasPrice": int(txq.get("gasPrice") or w3.eth.gas_price),
                "nonce": w3.eth.get_transaction_count(acct.address),
                "chainId": CHAIN_IDS[chain],
            }
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info("broadcast %s on %s", tx_hash.hex(), chain)
            return tx_hash.hex()
        except Exception:
            logger.exception("broadcast failed on %s", chain)
            return None
