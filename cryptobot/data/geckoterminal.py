"""GeckoTerminal OHLCV client (free, no key) — historical DEX pool candles.

GeckoTerminal (CoinGecko's DEX arm) serves per-pool OHLCV for the same
pools DexScreener tracks, which makes it the natural history source for
backtesting this bot's detectors: the candles describe exactly the pools
the scanner would have traded.

Endpoint: /api/v2/networks/{network}/pools/{pool}/ohlcv/{timeframe}
Rows come newest-first as [ts, open, high, low, close, volume_usd].
Rate limit ~30 calls/min.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.geckoterminal.com/api/v2"

# DexScreener chain name -> GeckoTerminal network id
GT_NETWORKS = {
    "ethereum": "eth",
    "base": "base",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
    "polygon": "polygon_pos",
    "solana": "solana",
}


@dataclass
class Candle:
    ts: float          # bucket start, unix seconds
    open: float
    high: float
    low: float
    close: float
    volume_usd: float


class GeckoTerminalClient:
    def __init__(self, timeout: float = 20.0,
                 client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL, timeout=timeout,
            headers={"User-Agent": "crypto-vol-bot/0.1",
                     "Accept": "application/json"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ohlcv(self, chain: str, pool: str, *, timeframe: str = "minute",
                    aggregate: int = 5, limit: int = 1000,
                    before_ts: Optional[int] = None) -> list[Candle]:
        """One page of candles, returned OLDEST-first."""
        network = GT_NETWORKS.get(chain)
        if network is None:
            raise ValueError(f"no GeckoTerminal network mapped for {chain!r}")
        params: dict = {"aggregate": aggregate, "limit": min(limit, 1000),
                        "currency": "usd"}
        if before_ts:
            params["before_timestamp"] = before_ts
        for attempt in range(3):
            try:
                resp = await self._client.get(
                    f"/networks/{network}/pools/{pool}/ohlcv/{timeframe}",
                    params=params,
                )
                if resp.status_code == 429:
                    await asyncio.sleep(10.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                rows = (((resp.json() or {}).get("data") or {})
                        .get("attributes") or {}).get("ohlcv_list") or []
                candles = [
                    Candle(ts=float(r[0]), open=float(r[1]), high=float(r[2]),
                           low=float(r[3]), close=float(r[4]),
                           volume_usd=float(r[5]))
                    for r in rows if len(r) >= 6 and float(r[4]) > 0
                ]
                candles.sort(key=lambda c: c.ts)
                return candles
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                logger.warning("geckoterminal ohlcv failed (%s), retrying", exc)
                await asyncio.sleep(3.0 * (attempt + 1))
        return []

    async def ohlcv_history(self, chain: str, pool: str, *, days: float,
                            aggregate: int = 5,
                            timeframe: str = "minute") -> list[Candle]:
        """Paginate back `days` of candles (multiple calls).

        `timeframe` is minute/hour/day; `aggregate` is candles per bucket.

        Pagination stops on TIME, not on candle count. GeckoTerminal omits
        empty buckets, so a sparse pool returns 1000 candles spanning
        months rather than the 3.5 days a dense pool would — walking the
        cursor back past the free tier's history limit and collecting 401s
        instead of data.
        """
        import time as _time
        minutes = {"minute": 1, "hour": 60, "day": 1440}[timeframe]
        needed = int(days * 24 * 60 / (aggregate * minutes))
        floor_ts = _time.time() - days * 86400
        out: list[Candle] = []
        before: Optional[int] = None
        for _ in range(12):                      # hard page cap
            try:
                page = await self.ohlcv(chain, pool, timeframe=timeframe,
                                        aggregate=aggregate, limit=1000,
                                        before_ts=before)
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning("ohlcv page failed for %s (%s) - keeping %d "
                               "candles already fetched", pool[:10], exc, len(out))
                break
            if not page:
                break
            out = page + out
            oldest = int(page[0].ts)
            if oldest <= floor_ts or len(out) >= needed or len(page) < 100:
                break
            before = oldest
            await asyncio.sleep(2.1)             # stay under the rate limit
        out = [c for c in out if c.ts >= floor_ts]
        return out[-needed:] if len(out) > needed else out
