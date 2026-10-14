"""Kalshi perps public trade tape: every trade with price, size and the
taker's side ("bid" = buyer-initiated, "ask" = seller-initiated; checked
on the tape: bid-taker prints sit ~1 bp above the local median, ask-taker
prints ~1.3 bp below).

Pulls backwards from now with `max_ts` pages of 1,000 and stores
state/tape/<TICKER>.jsonl as [ts, price, count, side(+1 buy / -1 sell)].
Resumable: a second run fills from the newest stored trade forward and
continues the backfill below the oldest.

    python -m cryptobot.perp_tape --state state --days 60 KXDOGEPERP KXBTCPERP
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE = "https://external-api.kalshi.com/trade-api/v2"
UA = {"User-Agent": "cryptobot-research/0.1", "Accept": "application/json"}
DEFAULT = ("KXDOGEPERP", "KXKSHIBPERP", "KXBTCPERP", "KXETHPERP", "KXSOLPERP", "KXXRPPERP",
           "KXUS500PERP", "KXGOLDPERP", "KXSILVERPERP")


def _ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def parse(t: dict) -> list:
    return [round(_ts(t["created_time"]), 3), float(t["price"]), float(t["count"]), 1 if t["taker_side"] == "bid" else -1,
            t["trade_id"]]


class Tape:
    def __init__(self, state_dir: Path, client=None, pace_s: float = 0.35):
        self.root = Path(state_dir) / "tape"
        self.root.mkdir(parents=True, exist_ok=True)
        self.c = client or httpx.Client(timeout=30, headers=UA)
        self.pace_s = pace_s

    def path(self, ticker: str) -> Path:
        return self.root / f"{ticker}.jsonl"

    def load(self, ticker: str) -> list[list]:
        p = self.path(ticker)
        if not p.exists():
            return []
        rows = {}
        for line in p.open():
            if line.strip():
                r = json.loads(line)
                rows[r[4]] = r
        return sorted(rows.values(), key=lambda r: r[0])

    def _page(self, ticker: str, max_ts: Optional[int] = None, min_ts: Optional[int] = None) -> list[dict]:
        params = {"ticker": ticker, "limit": 1000}
        if max_ts:
            params["max_ts"] = max_ts
        if min_ts:
            params["min_ts"] = min_ts
        for attempt in range(8):
            try:
                r = self.c.get(BASE + "/margin/trades", params=params)
            except httpx.TransportError:
                time.sleep(1 + attempt)
                continue
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            time.sleep(self.pace_s)
            return r.json().get("trades", [])
        raise RuntimeError(f"{ticker}: throttled")

    def pull(self, ticker: str, days: float) -> dict:
        have = self.load(ticker)
        ids = {r[4] for r in have}
        floor = time.time() - days * 86400
        added = 0
        with self.path(ticker).open("a") as f:
            def take(ts_rows):
                nonlocal added
                for t in ts_rows:
                    r = parse(t)
                    if r[4] not in ids:
                        ids.add(r[4])
                        f.write(json.dumps(r) + "\n")
                        added += 1
            # forward fill: newest first down to what we have
            newest = have[-1][0] if have else None
            max_ts = None
            while True:
                page = self._page(ticker, max_ts=max_ts)
                if not page:
                    break
                take(page)
                oldest = min(_ts(t["created_time"]) for t in page)
                if (newest and oldest <= newest) or oldest < floor or len(page) < 1000:
                    break
                max_ts = int(oldest)        # whole seconds; duplicates at the boundary are dropped by trade_id
            # backfill below the oldest stored
            lo = min([r[0] for r in have] + [oldest if page else time.time()])
            max_ts = int(lo)
            while lo > floor:
                page = self._page(ticker, max_ts=max_ts)
                if not page:
                    break
                take(page)
                o = min(_ts(t["created_time"]) for t in page)
                if o >= lo - 1e-6 and len(page) < 1000:
                    break
                lo = min(lo, o)
                if int(o) == max_ts:          # 1,000 trades in one second: step past it
                    max_ts -= 1
                else:
                    max_ts = int(o)
                if len(page) < 1000:
                    break
        rows = self.load(ticker)
        return {"ticker": ticker, "added": added, "trades": len(rows),
                "first": dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc).isoformat() if rows else None,
                "last": dt.datetime.fromtimestamp(rows[-1][0], dt.timezone.utc).isoformat() if rows else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--days", type=float, default=60)
    ap.add_argument("tickers", nargs="*", default=list(DEFAULT))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t = Tape(a.state)
    for tk in a.tickers:
        print(t.pull(tk, a.days), flush=True)
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
