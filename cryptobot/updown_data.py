"""Collector for Polymarket "Bitcoin Up or Down" markets and BTC candles.

Each market pays $1 per share to Up if Chainlink's BTC/USD price at the
end of the window is >= the price at its start, else to Down. This pulls,
for every resolved market in a series over the last N days:

  * start / end time, token ids, the resolved outcome;
  * the Up token's price history at ~1-minute fidelity (CLOB
    prices-history), which is what a trader would have been quoted;

plus 1-minute BTC-USD candles from Coinbase for the same span, used to
compute model fair values and indicators at each decision time.

Everything is cached to one pickle and the collector resumes where it
stopped, so a container restart costs nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
COINBASE = "https://api.exchange.coinbase.com"


@dataclass
class UpDownMarket:
    slug: str
    start: int
    end: int
    up_token: str
    down_token: str
    up_won: Optional[bool]               # None until resolved
    volume: float = 0.0
    history: list = field(default_factory=list)   # [(ts, up_price)]


class _Unpickler(pickle.Unpickler):
    """Caches written by `python -m cryptobot.updown_data` record the class
    as __main__.UpDownMarket; resolve it to this module either way."""

    def find_class(self, module, name):
        if name == "UpDownMarket":
            return UpDownMarket
        return super().find_class(module, name)


def load(path: Path) -> dict:
    with open(path, "rb") as f:
        return _Unpickler(f).load()


def parse_event(ev: dict) -> Optional[UpDownMarket]:
    try:
        m = ev["markets"][0]
        outcomes = json.loads(m["outcomes"])
        tokens = json.loads(m["clobTokenIds"])
        prices = json.loads(m.get("outcomePrices") or "[]")
        iu, idn = outcomes.index("Up"), outcomes.index("Down")
        start = int(dt.datetime.fromisoformat(
            (m.get("eventStartTime") or ev.get("startTime")).replace("Z", "+00:00")).timestamp())
        end = int(dt.datetime.fromisoformat(m["endDate"].replace("Z", "+00:00")).timestamp())
    except (KeyError, ValueError, IndexError, TypeError, AttributeError):
        return None
    up_won = None
    if m.get("closed") and len(prices) == 2:
        pu = float(prices[iu])
        up_won = True if pu > 0.99 else False if pu < 0.01 else None
    return UpDownMarket(ev.get("slug", ""), start, end, tokens[iu], tokens[idn], up_won,
                        float(m.get("volumeNum") or m.get("volume") or 0.0))


class Collector:
    def __init__(self, path: Path, series: str, days: float, client=None, pause: float = 0.25):
        self.path, self.series, self.days, self.pause = path, series, days, pause
        self.c = client or httpx.AsyncClient(timeout=30)
        self.data = load(path) if path.exists() else {"markets": {}, "candles": {}}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(self.data))
        tmp.replace(self.path)

    async def _get(self, url, params):
        for attempt in range(4):
            try:
                r = await self.c.get(url, params=params)
                if r.status_code == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                logger.warning("%s failed: %s", url.split("/")[-1], exc)
                await asyncio.sleep(2 * (attempt + 1))
        return None

    async def markets(self) -> None:
        cutoff = time.time() - self.days * 86400
        offset = 0
        while True:
            evs = await self._get(f"{GAMMA}/events", {
                "series_slug": self.series, "closed": "true", "limit": 100,
                "offset": offset, "order": "startDate", "ascending": "false"})
            if not evs:
                break
            oldest = None
            for ev in evs:
                mk = parse_event(ev)
                if mk is None:
                    continue
                oldest = mk.start if oldest is None else min(oldest, mk.start)
                if mk.start >= cutoff and mk.slug not in self.data["markets"]:
                    self.data["markets"][mk.slug] = mk
            logger.info("listed offset %d, %d markets kept", offset, len(self.data["markets"]))
            if oldest is not None and oldest < cutoff:
                break
            offset += 100
            await asyncio.sleep(self.pause)
        self.save()

    async def histories(self) -> None:
        todo = [m for m in self.data["markets"].values() if not m.history and m.up_won is not None]
        for i, m in enumerate(todo):
            h = await self._get(f"{CLOB}/prices-history", {
                "market": m.up_token, "startTs": m.start - 120, "endTs": m.end + 60,
                "fidelity": 1})
            m.history = [(int(p["t"]), float(p["p"])) for p in (h or {}).get("history", [])]
            if not m.history:
                m.history = [(-1, -1.0)]          # mark as tried
            if i % 100 == 0:
                logger.info("history %d / %d", i, len(todo))
                self.save()
            await asyncio.sleep(self.pause)
        self.save()

    async def candles(self, product: str = "BTC-USD") -> None:
        ms = self.data["markets"].values()
        if not ms:
            return
        lo = min(m.start for m in ms) - 6 * 3600
        hi = max(m.end for m in ms) + 120
        have = self.data["candles"].setdefault(product, {})
        t = lo
        while t < hi:
            if all((t + k * 60) in have for k in range(0, 300, 30)):
                t += 300 * 60
                continue
            rows = await self._get(f"{COINBASE}/products/{product}/candles", {
                "granularity": 60,
                "start": dt.datetime.utcfromtimestamp(t).isoformat(),
                "end": dt.datetime.utcfromtimestamp(t + 300 * 60).isoformat()})
            for r in rows or []:
                # [time, low, high, open, close, volume]
                have[int(r[0])] = (float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]))
            t += 300 * 60
            await asyncio.sleep(0.35)
        logger.info("candles: %d minutes", len(have))
        self.save()

    async def run(self) -> None:
        try:
            await self.markets()
            await self.candles()
            await self.histories()
        finally:
            await self.c.aclose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--series", default="btc-up-or-down-15m")
    ap.add_argument("--days", type=float, default=30)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    # Use the package's classes so the cache pickles as cryptobot.updown_data.*
    from cryptobot.updown_data import Collector as C
    asyncio.run(C(args.out, args.series, args.days).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
