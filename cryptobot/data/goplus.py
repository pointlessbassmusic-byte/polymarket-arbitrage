"""GoPlus Labs token-security screen — the anti-rug database.

Free, permissionless API (https://docs.gopluslabs.io) that returns 20+
contract-level risk flags per token: honeypot status, buy/sell taxes,
mintability, owner powers (pause trading, edit balances, blacklist),
holder concentration. Screening every candidate against it before entry
is standard practice in every serious memecoin bot — a token whose chart
looks perfect is worthless if the contract won't let you sell.

Verdicts are cached (contract code rarely changes) and the screen fails
OPEN by default on API errors for the liquid, aged universe this bot
already filters to — configurable to fail closed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.gopluslabs.io/api/v1"

# GoPlus chain ids for the chain names DexScreener uses (EVM only;
# Solana uses a separate GoPlus endpoint and is skipped for now).
GOPLUS_CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "base": "8453",
    "avalanche": "43114",
}


@dataclass
class SecurityVerdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    checked_at: float = 0.0
    known: bool = True     # False = API failed / chain unsupported

    def __str__(self) -> str:
        if self.ok:
            return "clear" if self.known else "unscreened"
        return "REJECTED: " + "; ".join(self.reasons)


# Keys GoPlus populates for any contract it has actually analysed. A
# record missing all of them is not "a token with no problems" — it is a
# token nobody has looked at yet, which is precisely the fresh-deploy
# case this screen exists to catch.
_CORE_KEYS = ("is_honeypot", "buy_tax", "sell_tax", "is_open_source",
              "cannot_sell_all", "owner_address")


def is_analysed(data: dict) -> bool:
    """True when the record carries real analysis, not just an echo."""
    return any(k in data for k in _CORE_KEYS)


@dataclass
class ScreenConfig:
    max_buy_tax: float = 0.10
    max_sell_tax: float = 0.10
    max_creator_percent: float = 0.20    # creator holding >20% of supply
    block_on_unknown: bool = False       # fail closed when API unavailable
    cache_ttl_s: float = 3600.0


def _flag(data: dict, key: str) -> bool:
    return str(data.get(key, "")) == "1"


def _tax(data: dict, key: str) -> float:
    try:
        return float(data.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


_RENOUNCED_OWNERS = {
    "", "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
}


def _renounced(data: dict) -> bool:
    """Ownership renounced (and not hidden): owner-power functions are inert.

    Without this, blue-chip memecoins like PEPE get rejected — the contract
    HAS pause/blacklist functions, but nobody can call them anymore.
    """
    if _flag(data, "hidden_owner"):
        return False
    owner = str(data.get("owner_address") or "").lower()
    return owner in _RENOUNCED_OWNERS


def evaluate(data: dict, cfg: ScreenConfig) -> SecurityVerdict:
    """Turn one GoPlus token record into a trade/no-trade verdict.

    Absence of flags is NOT evidence of safety: an empty or unanalysed
    record must come back `known=False` so the caller can decide, rather
    than silently reading as a clean bill of health.
    """
    if not is_analysed(data):
        return SecurityVerdict(ok=not cfg.block_on_unknown, known=False,
                               reasons=["no GoPlus analysis for this contract"],
                               checked_at=time.time())
    reasons: list[str] = []

    # Hard rejects: the contract can stop you from exiting.
    if _flag(data, "is_honeypot"):
        reasons.append("honeypot")
    if _flag(data, "cannot_sell_all"):
        reasons.append("cannot sell full position")
    if _flag(data, "cannot_buy"):
        reasons.append("buying disabled")

    # Owner-power rejects — only enforceable while someone holds ownership.
    if not _renounced(data):
        if _flag(data, "transfer_pausable"):
            reasons.append("owner can pause trading")
        if _flag(data, "owner_change_balance"):
            reasons.append("owner can edit balances")
        if _flag(data, "is_blacklisted"):
            reasons.append("blacklist function present")
        if _flag(data, "can_take_back_ownership"):
            reasons.append("renounce is reversible")
        if _flag(data, "personal_slippage_modifiable"):
            reasons.append("per-address tax rates")

    sell_tax = _tax(data, "sell_tax")
    buy_tax = _tax(data, "buy_tax")
    if sell_tax > cfg.max_sell_tax:
        reasons.append(f"sell tax {sell_tax:.0%}")
    if buy_tax > cfg.max_buy_tax:
        reasons.append(f"buy tax {buy_tax:.0%}")

    creator = _tax(data, "creator_percent")
    if creator > cfg.max_creator_percent:
        reasons.append(f"creator holds {creator:.0%}")

    # Soft flags: suspicious but not disqualifying alone — reject only in
    # combination (a closed-source mintable proxy is a rug template).
    soft = sum((
        _flag(data, "is_mintable"),
        not _flag(data, "is_open_source"),
        _flag(data, "is_proxy"),
    ))
    if soft >= 2:
        reasons.append("mintable/closed-source/proxy combination")

    return SecurityVerdict(ok=not reasons, reasons=reasons, checked_at=time.time())


class TokenScreen:
    def __init__(self, cfg: Optional[ScreenConfig] = None,
                 client: Optional[httpx.AsyncClient] = None):
        self.cfg = cfg or ScreenConfig()
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL, timeout=15.0,
            headers={"User-Agent": "crypto-vol-bot/0.1"},
        )
        self._owns_client = client is None
        self._cache: dict[str, SecurityVerdict] = {}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def check(self, chain: str, token_address: str) -> SecurityVerdict:
        """Screen one token. Unknown chains / API failures return a verdict
        with known=False whose ok honors cfg.block_on_unknown."""
        chain_id = GOPLUS_CHAIN_IDS.get(chain)
        if chain_id is None or not token_address:
            return SecurityVerdict(ok=not self.cfg.block_on_unknown, known=False)

        cache_key = f"{chain}:{token_address.lower()}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached.checked_at < self.cfg.cache_ttl_s:
            return cached

        data = await self._fetch(chain_id, token_address)
        if data is None:
            return SecurityVerdict(ok=not self.cfg.block_on_unknown, known=False)

        verdict = evaluate(data, self.cfg)
        # Never cache an unknown verdict: caching it would freeze a
        # "nobody has analysed this yet" answer for the whole TTL, right
        # through the window when GoPlus first indexes the contract.
        if verdict.known:
            self._cache[cache_key] = verdict
        if not verdict.ok:
            logger.info("security screen %s %s: %s", chain, token_address[:10], verdict)
        return verdict

    async def _fetch(self, chain_id: str, token_address: str) -> Optional[dict]:
        for attempt in range(3):
            try:
                resp = await self._client.get(
                    f"/token_security/{chain_id}",
                    params={"contract_addresses": token_address},
                )
                if resp.status_code == 429:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                result = (resp.json() or {}).get("result") or {}
                # Result is keyed by (lowercased) contract address.
                for addr, data in result.items():
                    if addr.lower() == token_address.lower():
                        return data
                return None
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    logger.warning("goplus check failed: %s", exc)
                    return None
                await asyncio.sleep(1.5 * (attempt + 1))
        return None
