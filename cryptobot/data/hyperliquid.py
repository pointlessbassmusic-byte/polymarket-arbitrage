"""Hyperliquid public info API — perp candles and funding history, no key.

Hyperliquid is a perpetuals DEX with 0.035% taker / 0.010% maker fees,
short-selling, and multi-year daily history for the memecoins this
project trades. That makes it both the venue the cost arithmetic points
at and the only free source found so far with history spanning more than
one market regime.

Endpoint: POST https://api.hyperliquid.xyz/info with a JSON body.
  {"type": "meta"}                          universe of perps
  {"type": "candleSnapshot", "req": {...}}  up to ~5000 candles
  {"type": "fundingHistory", "coin", "startTime"}  500 rows per call,
                                            hourly, paginate on time

Small-cap coins are listed with a "k" prefix (kPEPE = 1000 PEPE); prices
are per thousand tokens, which does not affect returns.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from cryptobot.data.geckoterminal import Candle

logger = logging.getLogger(__name__)

INFO_URL = "https://api.hyperliquid.xyz/info"

TAKER_FEE = 0.00035
MAKER_FEE = 0.00010

# Hyperliquid names for the memecoins in this project's universe.
MEMECOINS = ("DOGE", "kPEPE", "kSHIB", "kBONK", "kFLOKI", "WIF", "POPCAT",
             "TURBO", "BRETT", "kNEIRO", "GOAT", "MOODENG", "PNUT",
             "FARTCOIN", "SPX", "TRUMP", "AERO", "kLUNC")


@dataclass
class Funding:
    ts: float
    rate: float        # per funding interval (hourly), fraction
    premium: float


class HyperliquidClient:
    def __init__(self, timeout: float = 20.0,
                 client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": "crypto-vol-bot/0.1"})
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _info(self, body: dict):
        for attempt in range(3):
            try:
                resp = await self._client.post(INFO_URL, json=body)
                if resp.status_code == 429:
                    await asyncio.sleep(5.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                logger.warning("hyperliquid %s failed (%s), retrying", body.get("type"), exc)
                await asyncio.sleep(2.0 * (attempt + 1))
        return None

    async def universe(self) -> list[str]:
        meta = await self._info({"type": "meta"}) or {}
        return [u["name"] for u in meta.get("universe", []) if not u.get("isDelisted")]

    async def candles(self, coin: str, interval: str = "1d", *,
                      start_ms: int = 0, end_ms: Optional[int] = None) -> list[Candle]:
        """Candles oldest-first. The API returns at most ~5000 per call."""
        end_ms = end_ms or int(time.time() * 1000)
        rows = await self._info({"type": "candleSnapshot",
                                 "req": {"coin": coin, "interval": interval,
                                         "startTime": start_ms, "endTime": end_ms}}) or []
        out = [Candle(ts=r["t"] / 1000.0, open=float(r["o"]), high=float(r["h"]),
                      low=float(r["l"]), close=float(r["c"]), volume_usd=float(r["v"]) * float(r["c"]))
               for r in rows if float(r["c"]) > 0]
        out.sort(key=lambda c: c.ts)
        return out

    async def funding_history(self, coin: str, *, start_ms: int = 0,
                              max_calls: int = 120) -> list[Funding]:
        """All funding rows from start_ms, paginating 500 at a time."""
        out: list[Funding] = []
        cursor = start_ms
        for _ in range(max_calls):
            rows = await self._info({"type": "fundingHistory", "coin": coin,
                                     "startTime": cursor}) or []
            if not rows:
                break
            out.extend(Funding(ts=r["time"] / 1000.0, rate=float(r["fundingRate"]),
                               premium=float(r.get("premium") or 0.0)) for r in rows)
            last = int(rows[-1]["time"])
            if len(rows) < 500 or last <= cursor:
                break
            cursor = last + 1
            await asyncio.sleep(0.25)
        return out
