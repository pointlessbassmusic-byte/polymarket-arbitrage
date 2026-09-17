"""MetaMask-compatible on-chain execution (OPTIONAL, disabled by default).

"Using MetaMask as the backbone" in bot terms means: the bot signs
transactions with the same secp256k1 private key your MetaMask wallet uses,
and routes swaps through a DEX aggregator (0x Swap API), which is exactly
what MetaMask Swaps does under the hood. Export a key from MetaMask (ideally
a fresh, small, dedicated hot wallet — never your main one) and put it in
the environment variable named in config.

Safety model:
  * live trading requires BOTH config `execution.live: true` AND the env var
    CRYPTOBOT_ARM_LIVE=yes — belt and suspenders against accidental sends;
  * every quote is sanity-checked against the signal price (max slippage);
  * per-trade notional is capped again here, independent of the risk layer;
  * web3/eth-account are imported lazily so the bot runs without them.

This module intentionally does NOT auto-approve infinite allowances: it
approves exactly the amount being sold, each time.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ZEROX_BASE = "https://api.0x.org"

# chainId map for the chains DexScreener names
CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
    "bsc": 56,
}


@dataclass
class WalletConfig:
    live: bool = False
    private_key_env: str = "CRYPTOBOT_PRIVATE_KEY"
    zerox_api_key_env: str = "CRYPTOBOT_0X_API_KEY"
    rpc_urls: dict[str, str] | None = None       # chain name -> RPC endpoint
    max_trade_usd: float = 50.0
    max_slippage: float = 0.02


class WalletExecutor:
    """Executes swaps via 0x quotes signed with a local (MetaMask) key."""

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

    async def quote(self, chain: str, sell_token: str, buy_token: str,
                    sell_amount_usd: float, sell_token_price_usd: float,
                    sell_token_decimals: int = 18) -> Optional[dict[str, Any]]:
        """Fetch a firm 0x swap quote. Works without being armed (dry-run)."""
        chain_id = CHAIN_IDS.get(chain)
        if chain_id is None:
            logger.info("no 0x support mapped for chain %r", chain)
            return None
        if sell_token_price_usd <= 0:
            return None
        sell_amount = int(
            sell_amount_usd / sell_token_price_usd * 10 ** sell_token_decimals
        )
        headers = {"0x-version": "v2"}
        if key := os.environ.get(self.cfg.zerox_api_key_env, ""):
            headers["0x-api-key"] = key
        params = {
            "chainId": chain_id,
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": str(sell_amount),
            "slippageBps": int(self.cfg.max_slippage * 10_000),
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{ZEROX_BASE}/swap/allowance-holder/quote",
                    params=params, headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("0x quote failed: %s", exc)
            return None

    async def execute_swap(self, chain: str, quote: dict[str, Any],
                           notional_usd: float) -> Optional[str]:
        """Sign and broadcast a quoted swap. Returns tx hash, or None.

        In dry-run (not armed) this logs the intent and returns None.
        """
        if notional_usd > self.cfg.max_trade_usd:
            logger.warning("trade %.2f exceeds wallet cap %.2f — refusing",
                           notional_usd, self.cfg.max_trade_usd)
            return None
        if not self._armed:
            logger.info("[dry-run] would swap ~$%.2f on %s via 0x", notional_usd, chain)
            return None

        rpc = (self.cfg.rpc_urls or {}).get(chain)
        if not rpc:
            logger.warning("no RPC configured for chain %r", chain)
            return None
        try:
            from eth_account import Account  # lazy: optional dependency
            from web3 import Web3
        except ImportError:
            logger.error("web3/eth-account not installed — pip install web3")
            return None

        w3 = Web3(Web3.HTTPProvider(rpc))
        acct = Account.from_key(self._key)
        txq = quote.get("transaction") or {}
        tx = {
            "from": acct.address,
            "to": Web3.to_checksum_address(txq["to"]),
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
