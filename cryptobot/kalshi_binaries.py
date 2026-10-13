"""Collector for `kalshi-btc-hourly-tails`: Kalshi's hourly BTC above/below
markets (series KXBTCD), settled, with their minute-by-minute quotes.

Kalshi lists about 190 strikes an hour and 30-35 of them trade. The
public API serves the settled markets (result, settlement print, volume)
a thousand a page, and for each market the minute candlesticks of its
life: YES bid and ask closes, the last trade and the volume per minute.
Both need no key; the read limit is a few requests a second, so this
paces itself at `pace_s` and slows down on a 429.

    python -m cryptobot.kalshi_binaries --state state --days 30       # list, then candles, newest first
    python -m cryptobot.kalshi_binaries --state state --status

Files: state/kalshi_binaries/markets.jsonl (one row per traded market)
and state/kalshi_binaries/candles/<close date>.jsonl (one row per
market: ticker and bars [end_ts, yes_bid, yes_ask, last, volume]).
Resumable: markets already on file and candles already fetched are
skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from .data.nasdaq import append_jsonl, read_jsonl

logger = logging.getLogger(__name__)

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXBTCD"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cryptobot-research", "Accept": "application/json"}
PACE_S = 0.7


def _f(x) -> Optional[float]:
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def compact(m: dict) -> dict:
    """The fields the study needs, from a market object."""
    return {"ticker": m["ticker"], "event": m.get("event_ticker"), "series": m["ticker"].split("-")[0],
            "strike_type": m.get("strike_type"), "floor": _f(m.get("floor_strike")), "cap": _f(m.get("cap_strike")),
            "open_ts": _ts(m["open_time"]), "close_ts": _ts(m["close_time"]), "result": m.get("result"),
            "settle": _f(m.get("expiration_value")), "volume": _f(m.get("volume_fp")) or 0.0}


class KalshiBinaries:
    def __init__(self, state_dir: Path, client=None, pace_s: float = PACE_S, series: str = SERIES, interval: int = 1):
        self.dir = Path(state_dir) / "kalshi_binaries"
        self.markets_file = self.dir / "markets.jsonl"
        self.candles_dir = self.dir / "candles"
        self.series = series
        self.interval = interval   # candle minutes: 1 for intraday markets, 60 for daily/weekly, 1440 for monthly and longer
        self._c = client or httpx.AsyncClient(timeout=60, headers=UA)
        self._owns = client is None
        self.pace_s = pace_s
        self.base_pace_s = pace_s
        self._last = 0.0
        self.requests = 0

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        for i in range(8):
            wait = self.pace_s - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._c.get(BASE + path, params=params)
            except httpx.HTTPError as exc:                # a dropped connection is retried like a throttle
                logger.warning("%s: %s; retrying", path, type(exc).__name__)
                self._last = time.monotonic()
                await asyncio.sleep(2.0 * (i + 1))
                continue
            self._last = time.monotonic()
            self.requests += 1
            if r.status_code == 200:
                self.pace_s = max(self.base_pace_s, self.pace_s * 0.97)   # ease back after a throttle
                return r.json()
            if r.status_code == 429:
                self.pace_s = min(5.0, self.pace_s * 1.5 + 0.2)
                await asyncio.sleep(self.pace_s * 4 * (i + 1))
                continue
            raise RuntimeError(f"{path} -> {r.status_code}")
        raise RuntimeError(f"{path}: still throttled after 8 tries")

    def markets(self) -> list[dict]:
        return read_jsonl(self.markets_file)

    def candles_done(self) -> set[str]:
        out = set()
        if self.candles_dir.exists():
            for p in self.candles_dir.glob("*.jsonl"):
                out.update(r["ticker"] for r in read_jsonl(p))
        return out

    async def list_settled(self, since: dt.datetime, max_pages: int = 5000) -> int:
        """Append every settled market with volume that closed after `since`."""
        have = {m["ticker"] for m in self.markets()}
        cursor, pages, added = None, 0, 0
        since_ts = int(since.timestamp())
        while pages < max_pages:
            params = {"series_ticker": self.series, "status": "settled", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            j = await self._get("/markets", params)
            ms = j.get("markets", [])
            pages += 1
            if not ms:
                break
            for m in ms:
                if (_f(m.get("volume_fp")) or 0) <= 0 or m["ticker"] in have or not m.get("result"):
                    continue
                row = compact(m)
                if row["close_ts"] < since_ts:
                    continue
                append_jsonl(self.markets_file, row)
                have.add(row["ticker"])
                added += 1
            oldest = min(_ts(m["close_time"]) for m in ms)
            cursor = j.get("cursor")
            if not cursor or oldest < since_ts:
                break
        return added

    async def fetch_candles(self, limit: Optional[int] = None, newest_first: bool = True) -> int:
        done = self.candles_done()
        todo = [m for m in self.markets() if m["ticker"] not in done]
        todo.sort(key=lambda m: m["close_ts"], reverse=newest_first)
        n = 0
        for m in todo[:limit]:
            try:
                j = await self._get(f"/series/{m['series']}/markets/{m['ticker']}/candlesticks",
                                    {"start_ts": m["open_ts"] - 60 * self.interval, "end_ts": m["close_ts"] + 60, "period_interval": self.interval})
            except RuntimeError as exc:                   # one market the endpoint refuses must not stop the pull
                logger.warning("candles %s: %s (stored empty)", m["ticker"], exc)
                j = {"candlesticks": [], "error": str(exc)}
            bars = []
            for c in j.get("candlesticks", []):
                bars.append([int(c.get("end_period_ts") or 0), _f((c.get("yes_bid") or {}).get("close_dollars")),
                             _f((c.get("yes_ask") or {}).get("close_dollars")), _f((c.get("price") or {}).get("close_dollars")),
                             _f(c.get("volume_fp")) or 0.0])
            day = dt.datetime.fromtimestamp(m["close_ts"], dt.timezone.utc).date().isoformat()
            row = {"ticker": m["ticker"], "bars": bars}
            if j.get("error"):
                row["error"] = j["error"]
            append_jsonl(self.candles_dir / f"{day}.jsonl", row)
            n += 1
            if n % 200 == 0:
                logger.info("candles: %d fetched, %d to go, pace %.2fs", n, len(todo) - n, self.pace_s)
        return n

    def status(self) -> dict:
        ms = self.markets()
        done = self.candles_done()
        return {"markets": len(ms), "with_candles": sum(1 for m in ms if m["ticker"] in done),
                "events": len({m["event"] for m in ms}),
                "first": dt.datetime.fromtimestamp(min(m["close_ts"] for m in ms), dt.timezone.utc).isoformat() if ms else None,
                "last": dt.datetime.fromtimestamp(max(m["close_ts"] for m in ms), dt.timezone.utc).isoformat() if ms else None}


async def collect(state_dir: Path, days: int = 30, client=None, limit: Optional[int] = None, pace_s: float = PACE_S,
                  series: str = SERIES, interval: int = 1) -> dict:
    c = KalshiBinaries(state_dir, client=client, pace_s=pace_s, series=series, interval=interval)
    try:
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        listed = await c.list_settled(since)
        fetched = await c.fetch_candles(limit=limit)
        return {"listed": listed, "candles": fetched, "requests": c.requests, **c.status()}
    finally:
        await c.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=None, help="at most this many candle fetches this run")
    ap.add_argument("--pace", type=float, default=PACE_S, help="seconds between public requests")
    ap.add_argument("--series", default=SERIES, help="Kalshi series ticker (KXBTCD hourly ladder, KXBTC15M 15-minute up/down, KXETHD, ...)")
    ap.add_argument("--interval", type=int, default=1, help="candle minutes (1, 60 or 1440)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.status:
        print(KalshiBinaries(a.state).status())
        return 0
    print(asyncio.run(collect(a.state, a.days, limit=a.limit, pace_s=a.pace, series=a.series, interval=a.interval)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
