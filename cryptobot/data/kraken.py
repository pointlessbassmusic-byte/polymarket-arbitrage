"""Kraken public spot data — the long leg of the carry trade.

Only public endpoints: asset pairs (to map a Hyperliquid coin to its
Kraken USD pair) and tickers. Trading needs a signed private API and is
kept in the execution layer.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kraken.com/0/public"

# Kraken Pro spot fees from 2026-07-09 (cross-platform tiers; tier by the
# best of 30-day spot volume, futures volume or assets on platform):
# (30-day spot volume floor USD, maker, taker). Source: kraken.com/features/
# fee-schedule and support "Cross-platform fee tiers". Before that date the
# entry tier was 0.16% / 0.26%; the carry study's history keeps those.
FEE_TIERS = (
    (0, 0.0040, 0.0080), (2_500, 0.0030, 0.0060), (10_000, 0.0022, 0.0038),
    (25_000, 0.0020, 0.0035), (50_000, 0.0015, 0.0030), (100_000, 0.0012, 0.0025),
    (250_000, 0.0010, 0.0022), (500_000, 0.0008, 0.0020), (1_000_000, 0.0006, 0.0018),
    (2_500_000, 0.0004, 0.0015), (5_000_000, 0.0002, 0.0012), (10_000_000, 0.0, 0.0010),
)
MAKER_FEE, TAKER_FEE = FEE_TIERS[0][1], FEE_TIERS[0][2]      # tier 1: what a new account pays

# Spot margin (US retail via Kraken Derivatives US since 2026-05-06): an
# opening fee on the margin extended plus a rollover fee every 4 hours,
# each 0.02-0.04% for DOGE/PEPE/SHIB (0.01-0.02% for BTC), locked at entry
# and shown on the order form. The midpoint is the planning number.
MARGIN_FEE_RANGE = {"BTC": (0.0001, 0.0002)}
MARGIN_FEE_DEFAULT = (0.0002, 0.0004)


def fees_for_tier(tier: int = 1) -> tuple[float, float]:
    """(maker, taker) for Kraken Pro tier 1..12."""
    t = FEE_TIERS[max(1, min(int(tier), len(FEE_TIERS))) - 1]
    return t[1], t[2]


def margin_fee_4h(coin: str) -> float:
    """Planning rollover (and opening) fee per 4 hours: the midpoint of
    Kraken's published range for the coin."""
    lo, hi = MARGIN_FEE_RANGE.get(hl_to_base(coin), MARGIN_FEE_DEFAULT)
    return (lo + hi) / 2

# Kraken names a few assets differently from everyone else.
_ALIASES = {"DOGE": "XDG", "BTC": "XBT"}


def hl_to_base(coin: str) -> str:
    """kPEPE -> PEPE. Hyperliquid's k-prefix means 1000 units."""
    return coin[1:] if coin.startswith("k") and coin[1:].isupper() else coin


class KrakenClient:
    def __init__(self, timeout: float = 15.0,
                 client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL, timeout=timeout,
            headers={"User-Agent": "crypto-vol-bot/0.1"})
        self._owns_client = client is None
        self._pairs: dict[str, str] = {}      # base symbol -> kraken pair name

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def usd_pairs(self) -> dict[str, str]:
        """{base: pair_name} for every USD spot pair."""
        if self._pairs:
            return self._pairs
        resp = await self._client.get("/AssetPairs")
        resp.raise_for_status()
        result = (resp.json() or {}).get("result") or {}
        out = {}
        for name, info in result.items():
            ws = info.get("wsname") or ""
            if "/" not in ws:
                continue
            base, quote = ws.split("/", 1)
            if quote != "USD":
                continue
            out[base] = name
        self._pairs = out
        return out

    async def pair_for(self, hl_coin: str) -> Optional[str]:
        pairs = await self.usd_pairs()
        base = hl_to_base(hl_coin)
        return pairs.get(base) or pairs.get(_ALIASES.get(base, ""))

    async def tickers(self, pair_names: list[str]) -> dict[str, tuple[float, float]]:
        """{pair: (bid, ask)}."""
        if not pair_names:
            return {}
        resp = await self._client.get("/Ticker", params={"pair": ",".join(pair_names)})
        resp.raise_for_status()
        result = (resp.json() or {}).get("result") or {}
        out = {}
        for name, t in result.items():
            try:
                out[name] = (float(t["b"][0]), float(t["a"][0]))
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        return out
