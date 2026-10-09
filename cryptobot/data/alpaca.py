"""Alpaca market data: intraday and daily bars from the free IEX feed.

The investigation queue's equity items need 5-minute bars (ORB pilot)
and daily closes (PEAD, overnight study); this is the free source. IEX
is one exchange's prints, so volumes are a fraction of consolidated
volume; prices are fine for bar-based rules. Paper keys work for data.

Candles use the project's `Candle` shape; `volume_usd` is shares x close
(IEX shares, not consolidated).
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import httpx

from .geckoterminal import Candle

DATA_URL = "https://data.alpaca.markets"


def _ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


class AlpacaData:
    def __init__(self, key_id: Optional[str] = None, secret: Optional[str] = None, *,
                 feed: str = "iex", base_url: str = DATA_URL,
                 client: Optional[httpx.AsyncClient] = None, timeout_s: float = 30.0):
        self._key = key_id if key_id is not None else os.environ.get("CRYPTOBOT_ALPACA_KEY_ID", "")
        self._secret = secret if secret is not None else os.environ.get("CRYPTOBOT_ALPACA_SECRET_KEY", "")
        self.feed = feed
        self.base = base_url.rstrip("/")
        self._c = client or httpx.AsyncClient(timeout=timeout_s)
        self._owns = client is None

    @property
    def has_key(self) -> bool:
        return bool(self._key and self._secret)

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    async def _get(self, path: str, params: dict) -> dict:
        r = await self._c.request("GET", self.base + path, params=params,
                                  headers={"APCA-API-KEY-ID": self._key, "APCA-API-SECRET-KEY": self._secret})
        if r.status_code >= 400:
            raise RuntimeError(f"alpaca data {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    async def bars(self, symbol: str, timeframe: str = "5Min", start: Optional[dt.datetime] = None,
                   end: Optional[dt.datetime] = None, limit: int = 10_000) -> list[Candle]:
        """All bars for `symbol` between start and end (UTC), following
        the page token until exhausted."""
        params = {"symbols": symbol, "timeframe": timeframe, "limit": limit, "feed": self.feed,
                  "adjustment": "raw"}
        if start:
            params["start"] = start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        if end:
            params["end"] = end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        out: list[Candle] = []
        token = None
        while True:
            if token:
                params["page_token"] = token
            d = await self._get("/v2/stocks/bars", params)
            for b in (d.get("bars") or {}).get(symbol) or []:
                c = float(b["c"])
                out.append(Candle(ts=_ts(b["t"]), open=float(b["o"]), high=float(b["h"]),
                                  low=float(b["l"]), close=c, volume_usd=float(b.get("v") or 0) * c))
            token = d.get("next_page_token")
            if not token:
                break
        return out

    async def daily(self, symbol: str, start: Optional[dt.datetime] = None) -> list[Candle]:
        return await self.bars(symbol, "1Day", start)

    async def latest_quote(self, symbol: str) -> tuple[float, float]:
        d = await self._get("/v2/stocks/quotes/latest", {"symbols": symbol, "feed": self.feed})
        q = (d.get("quotes") or {}).get(symbol) or {}
        return float(q.get("bp") or 0), float(q.get("ap") or 0)
