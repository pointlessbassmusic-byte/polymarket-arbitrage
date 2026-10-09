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
TAKER_FEE = 0.0026
MAKER_FEE = 0.0016

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
