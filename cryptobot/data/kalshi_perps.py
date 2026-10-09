"""Kalshi perpetuals market data (no key needed).

Daily candles, mids and funding for the bot, seeded with cached
Hyperliquid history for the tercile fit (Kalshi's perps only trade
since June 2026). Prices are per CONTRACT on Kalshi and divided by the
contract's units so the bot sees the same per-coin price units it was
validated on. Funding is exchanged every 8 hours; the bot accrues hourly,
so the current estimate is returned as an hourly-equivalent rate.
"""
from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import httpx

from ..execution.kalshi_perps import BASE, CONTRACTS
from .geckoterminal import Candle

logger = logging.getLogger(__name__)

DAY = 86400
FUNDING_PERIOD_H = 8.0


class KalshiMarketData:
    def __init__(self, history_seed: Optional[Path] = None,
                 client: Optional[httpx.AsyncClient] = None, base_url: str = BASE):
        self._c = client or httpx.AsyncClient(timeout=25)
        self._owns = client is None
        self.base = base_url.rstrip("/")
        self._seed: dict[str, list[Candle]] = {}
        self.seed_loaded = False
        if history_seed:
            if Path(history_seed).exists():
                pools = pickle.loads(Path(history_seed).read_bytes())
                for _, (meta, cs) in pools.items():
                    if meta.symbol in CONTRACTS:
                        self._seed[meta.symbol] = list(cs)
                self.seed_loaded = bool(self._seed)
            if not self.seed_loaded:
                logger.warning("history seed %s missing or empty: terciles would be fit on Kalshi's "
                               "own candles only (since June 2026). Build it: python -m "
                               "cryptobot.data.coinbase_futures --seed %s", history_seed, history_seed)
        self._markets: tuple[float, dict] = (0.0, {})

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r = await self._c.get(self.base + path, params=params)
        r.raise_for_status()
        return r.json()

    async def markets(self, max_age_s: float = 10.0) -> dict:
        ts, cached = self._markets
        if cached and time.time() - ts < max_age_s:
            return cached
        d = await self._get("/margin/markets", {"limit": 200})
        by = {m["ticker"]: m for m in d.get("markets", [])}
        self._markets = (time.time(), by)
        return by

    async def universe(self) -> list[str]:
        by = await self.markets()
        return [coin for coin, c in CONTRACTS.items()
                if (by.get(c.ticker) or {}).get("status") == "active"]

    async def candles(self, coin: str, interval: str = "1d", **_) -> list[Candle]:
        c = CONTRACTS[coin]
        end = int(time.time())
        d = await self._get(f"/margin/markets/{c.ticker}/candlesticks",
                            {"start_ts": end - 400 * DAY, "end_ts": end, "period_interval": 1440})
        out: list[Candle] = []
        u = c.units_per_contract
        for row in d.get("candlesticks", []):
            p = row.get("price") or {}
            close = float(p.get("close") or 0) / u
            if close <= 0:
                continue
            end_ts = float(row.get("end_period_ts") or 0)
            out.append(Candle(ts=end_ts - DAY, open=float(p.get("open") or 0) / u,
                              high=float(p.get("high") or 0) / u, low=float(p.get("low") or 0) / u,
                              close=close,
                              volume_usd=float(row.get("volume_notional_value_dollars") or 0)))
        out.sort(key=lambda x: x.ts)
        first = out[0].ts if out else float("inf")
        return [x for x in self._seed.get(coin, []) if x.ts < first] + out

    async def all_mids(self) -> dict[str, float]:
        by = await self.markets()
        out = {}
        for coin, c in CONTRACTS.items():
            m = by.get(c.ticker)
            if not m or m.get("status") != "active":
                continue
            bid, ask = float(m.get("bid") or 0), float(m.get("ask") or 0)
            px = (bid + ask) / 2 if bid > 0 and ask > 0 else float(m.get("price") or 0)
            if px > 0:
                out[coin] = px / c.units_per_contract
        return out

    async def funding_rates(self) -> dict[str, float]:
        """Hourly-equivalent funding per coin (positive = longs pay)."""
        out = {}
        for coin, c in CONTRACTS.items():
            try:
                d = await self._get("/margin/funding_rates/estimate", {"ticker": c.ticker})
            except Exception as exc:                   # inactive market, or not listed yet
                logger.debug("funding estimate for %s unavailable: %s", coin, exc)
                continue
            try:
                out[coin] = float(d.get("funding_rate") or 0.0) / FUNDING_PERIOD_H
            except (TypeError, ValueError):
                continue
        return out

    async def funding_history(self, coin: str, limit: int = 500) -> list[tuple[float, float]]:
        """(ts, rate per 8h period) oldest first."""
        c = CONTRACTS[coin]
        d = await self._get("/margin/funding_rates/historical", {"ticker": c.ticker, "limit": limit})
        rows = []
        import datetime as dt
        for r in d.get("funding_rates", []):
            try:
                ts = dt.datetime.fromisoformat(r["funding_time"].replace("Z", "+00:00")).timestamp()
                rows.append((ts, float(r.get("funding_rate") or 0.0)))
            except (KeyError, ValueError, TypeError):
                continue
        return sorted(rows)

    async def margin_rates(self) -> dict[str, float]:
        """No intraday/overnight switch on Kalshi; nothing to cap by."""
        return {}
