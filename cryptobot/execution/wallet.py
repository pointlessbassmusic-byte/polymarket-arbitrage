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
  * transactions on mempool-exposed chains are broadcast through a PRIVATE
    RELAY (Flashbots Protect on Ethereum, 48 Club on BSC) so sandwich bots
    never see them pending; trading such a chain without one is refused
    by default;
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

# Private transaction relays: a swap broadcast to a public mempool is
# visible to sandwich bots before it lands, and a volatile memecoin swap
# is exactly what they hunt. Sending through a private relay keeps the
# transaction hidden until it is included. Free, no key required.
PRIVATE_RPCS = {
    "ethereum": "https://rpc.flashbots.net/fast",   # Flashbots Protect
    "bsc": "https://rpc.48.club",                   # 48 Club private txs
}

# Chains with a public mempool, where an unprotected swap is exposed.
# The centralized-sequencer L2s (base/arbitrum/optimism) have no public
# pending pool to snipe from, so they are not listed — that is a real
# property of those chains, not an oversight.
MEMPOOL_EXPOSED = {"ethereum", "bsc", "polygon"}

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
    # chain -> private relay for SENDING transactions (reads still use
    # rpc_urls). Defaults to the known free relays; set {} to disable.
    private_rpc_urls: dict[str, str] = field(
        default_factory=lambda: dict(PRIVATE_RPCS))
    # Refuse live trades on a mempool-exposed chain with no private relay.
    require_mev_protection: bool = True
    max_trade_usd: float = 50.0
    max_slippage: float = 0.02


def _same_addr(a: Any, b: Any) -> bool:
    return str(a or "").lower() == str(b or "").lower()


class QuoteRejected(Exception):
    """The aggregator's response does not match what we asked for."""


def validate_quote(quote: dict, *, chain: str, sell_token: str,
                   buy_token: str, sell_amount_raw: int,
                   max_slippage: float) -> None:
    """Check a 0x response against the request BEFORE signing it.

    The transaction that gets signed is built entirely out of this
    response — `to`, `data` and `value` all come off the wire. Whoever
    can answer for the aggregator (a compromised endpoint, a hostile
    resolver, an egress proxy) would otherwise get a blank cheque
    against the hot wallet. None of these checks cost anything; all of
    them fail closed.
    """
    txq = quote.get("transaction") or {}
    if not txq.get("to") or not txq.get("data"):
        raise QuoteRejected("quote carries no transaction")

    # The only native value we ever intend to send is the amount we asked
    # to sell (and zero when selling an ERC-20). Anything above that is
    # the response trying to spend more of the wallet than we offered.
    value = int(txq.get("value") or 0)
    intended = sell_amount_raw if _same_addr(sell_token, NATIVE) else 0
    if value > intended:
        raise QuoteRejected(
            f"quote would send {value} wei, we offered {intended}")

    # It must be the trade we asked for, on the chain we asked for.
    if (cid := quote.get("chainId")) is not None and int(cid) != CHAIN_IDS[chain]:
        raise QuoteRejected(f"quote is for chain {cid}, expected "
                            f"{CHAIN_IDS[chain]}")
    for field_name, expected in (("sellToken", sell_token),
                                 ("buyToken", buy_token)):
        got = quote.get(field_name)
        if got is not None and not _same_addr(got, expected):
            raise QuoteRejected(f"{field_name} is {got}, expected {expected}")
    got_sell = quote.get("sellAmount")
    if got_sell is not None and int(got_sell) > sell_amount_raw:
        raise QuoteRejected(f"quote sells {got_sell}, we offered "
                            f"{sell_amount_raw}")

    # Slippage must be enforced by a figure in the response, not merely by
    # the slippageBps we asked the remote side to honor.
    min_buy = quote.get("minBuyAmount")
    buy = quote.get("buyAmount")
    if min_buy is not None and buy is not None and int(buy) > 0:
        if int(min_buy) < int(buy) * (1.0 - max_slippage) * 0.99:
            raise QuoteRejected(
                f"minBuyAmount {min_buy} allows more slippage than the "
                f"configured {max_slippage:.1%}")


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
        try:
            validate_quote(quote, chain=chain, sell_token=NATIVE,
                           buy_token=token_address, sell_amount_raw=sell_raw,
                           max_slippage=self.cfg.max_slippage)
        except QuoteRejected as exc:
            logger.error("refusing to sign buy quote on %s: %s", chain, exc)
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

        try:
            validate_quote(quote, chain=chain, sell_token=token_address,
                           buy_token=NATIVE, sell_amount_raw=sell_raw,
                           max_slippage=self.cfg.max_slippage)
        except QuoteRejected as exc:
            logger.error("refusing to sign sell quote on %s: %s", chain, exc)
            return None

        # Approve for exactly this amount if needed. The spender is named
        # by the response, so it must be the same contract the transaction
        # itself calls — otherwise a crafted quote could farm an allowance
        # out to an unrelated address.
        allowance_issue = ((quote.get("issues") or {}).get("allowance")) or {}
        spender = allowance_issue.get("spender")
        tx_target = ((quote.get("transaction") or {}).get("to"))
        if spender and not _same_addr(spender, tx_target):
            logger.error("refusing to approve %s: it is not the contract the "
                         "quote calls (%s)", spender, tx_target)
            return None
        if spender:
            ok = await asyncio.to_thread(
                self._approve, w3, acct, chain, token_address, spender, sell_raw
            )
            if not ok:
                return None
        return await asyncio.to_thread(self._broadcast, w3, acct, chain, quote)

    # -- signing plumbing (sync, run in threads) ---------------------------

    def mev_protected(self, chain: str) -> bool:
        """True when this chain's sends cannot be sniped from a mempool."""
        if chain not in MEMPOOL_EXPOSED:
            return True          # no public pending pool to watch
        return bool(self.cfg.private_rpc_urls.get(chain))

    def _send_provider(self, w3, chain: str):
        """Web3 pointed at the private relay for broadcasting, when one is
        configured; otherwise the same public provider used for reads."""
        relay = self.cfg.private_rpc_urls.get(chain)
        if not relay:
            return w3
        try:
            from web3 import Web3
            return Web3(Web3.HTTPProvider(relay, request_kwargs={"timeout": 20}))
        except ImportError:
            return w3

    def _connect(self, chain: str):
        rpc = self.cfg.rpc_urls.get(chain)
        if not rpc:
            logger.warning("no RPC configured for chain %r", chain)
            return None, None
        if self.cfg.require_mev_protection and not self.mev_protected(chain):
            logger.error(
                "refusing to trade %s: public mempool and no private relay "
                "configured — swaps would be sandwich-exposed. Set "
                "execution.private_rpc_urls.%s or require_mev_protection: false",
                chain, chain)
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
            sender = self._send_provider(w3, chain)
            tx_hash = sender.eth.send_raw_transaction(signed.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
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
            sender = self._send_provider(w3, chain)
            tx_hash = sender.eth.send_raw_transaction(signed.raw_transaction)
            logger.info("broadcast %s on %s%s", tx_hash.hex(), chain,
                        " (private relay)"
                        if self.cfg.private_rpc_urls.get(chain) else "")
            return tx_hash.hex()
        except Exception:
            logger.exception("broadcast failed on %s", chain)
            return None
