"""Order-book recorder for Kalshi's perps: the first data class the desk
keeps that is not a close.

Every `interval_s` seconds, for each ticker, the public order book
(25 levels a side) is read and reduced to a row: best bid and ask, the
spread, depth within 10, 25 and 50 bp of mid on each side (contracts and
dollars), the imbalance at each band, and once a minute the market's
last price, open interest and reference (index) price, from which the
basis follows. Rows go to state/books/<TICKER>/<YYYY-MM-DD>.jsonl.

Pre-registered use: `kalshi-book-imbalance` (does the imbalance predict
the next minutes' mid beyond the cost?), judged after 30 days. Runs
inside the desk when collectors.orderbook.enabled is true.

    python -m cryptobot.book_recorder --state state --once      # one snapshot of every ticker
    python -m cryptobot.book_recorder --state state --report
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

BASE = "https://external-api.kalshi.com/trade-api/v2"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cryptobot-desk", "Accept": "application/json"}
DEFAULT_TICKERS = ("KXDOGEPERP", "KXKSHIBPERP", "KXBTCPERP", "KXETHPERP", "KXSOLPERP", "KXXRPPERP", "KXUS500PERP", "KXGOLDPERP")
BANDS_BP = (10, 25, 50)
DEPTH = 25


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def reduce_book(book: dict, contract_units: float = 1.0) -> Optional[dict]:
    """The features of one order book: best quotes, spread, banded depth
    and imbalance. Sizes are contracts and Kalshi quotes the price of ONE
    contract, so dollars are size x price; `contract_units` is kept on
    the row for reference only."""
    asks = sorted(((_f(p), _f(q)) for p, q in (book.get("asks") or []) if _f(p) > 0 and _f(q) > 0), key=lambda x: x[0])
    bids = sorted(((_f(p), _f(q)) for p, q in (book.get("bids") or []) if _f(p) > 0 and _f(q) > 0), key=lambda x: -x[0])
    if not asks or not bids:
        return None
    ask, bid = asks[0][0], bids[0][0]
    if ask <= bid:
        return None
    mid = (ask + bid) / 2
    row = {"bid": bid, "ask": ask, "mid": mid, "spread_bp": (ask - bid) / mid * 1e4,
           "bid_size": bids[0][1], "ask_size": asks[0][1], "levels": [len(bids), len(asks)]}
    for bp in BANDS_BP:
        lo, hi = mid * (1 - bp / 1e4), mid * (1 + bp / 1e4)
        b = sum(q for p, q in bids if p >= lo)
        a = sum(q for p, q in asks if p <= hi)
        row[f"bid_{bp}"] = b
        row[f"ask_{bp}"] = a
        row[f"imb_{bp}"] = (b - a) / (b + a) if (b + a) > 0 else 0.0
    row["bid_usd_25"] = row["bid_25"] * mid
    row["ask_usd_25"] = row["ask_25"] * mid
    row["units"] = contract_units
    return row


class BookRecorder:
    def __init__(self, state_dir: Path, tickers=DEFAULT_TICKERS, interval_s: float = 15.0,
                 client=None, now=None, sleep=None):
        self.state = Path(state_dir)
        self.tickers = tuple(tickers)
        self.interval_s = float(interval_s)
        self._c = client or httpx.AsyncClient(timeout=20, headers=UA)
        self._owns = client is None
        self._now = now or time.time
        self._sleep = sleep or asyncio.sleep
        self._units: dict[str, float] = {}
        self._market_at: dict[str, float] = {}
        self._market: dict[str, dict] = {}
        self.last: dict[str, dict] = {}
        self.errors = 0

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    def file_for(self, ticker: str, ts: float) -> Path:
        day = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
        return self.state / "books" / ticker / f"{day}.jsonl"

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r = await self._c.get(BASE + path, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"{path} -> {r.status_code}")
        return r.json()

    async def market(self, ticker: str, ts: float) -> dict:
        """Last price, open interest, reference price; refreshed once a minute."""
        if ts - self._market_at.get(ticker, 0.0) >= 60.0:
            m = (await self._get(f"/margin/markets/{ticker}")).get("market") or {}
            self._units[ticker] = _f(m.get("contract_size")) or 1.0
            ref = (m.get("reference_price") or {}).get("price")
            self._market[ticker] = {"last": _f(m.get("price")), "oi": _f(m.get("open_interest")), "ref": _f(ref)}
            self._market_at[ticker] = ts
        return self._market.get(ticker, {})

    async def snapshot(self, ticker: str) -> Optional[dict]:
        ts = self._now()
        mk = await self.market(ticker, ts)
        book = (await self._get(f"/margin/markets/{ticker}/orderbook", {"depth": DEPTH})).get("orderbook") or {}
        row = reduce_book(book, self._units.get(ticker, 1.0))
        if row is None:
            return None
        row.update(ts=round(ts, 1), ticker=ticker, last=mk.get("last"), oi=mk.get("oi"), ref=mk.get("ref"))
        row["basis_bp"] = (row["mid"] / mk["ref"] - 1) * 1e4 if mk.get("ref") else None
        append_jsonl(self.file_for(ticker, ts), row)
        self.last[ticker] = row
        return row

    async def run_once(self) -> dict[str, Optional[dict]]:
        out = {}
        for t in self.tickers:
            try:
                out[t] = await self.snapshot(t)
            except Exception as exc:                      # noqa: BLE001 - one ticker down must not stop the rest
                self.errors += 1
                logger.warning("book %s: %s", t, exc)
                out[t] = None
        return out

    async def run_forever(self) -> None:
        logger.info("order-book recorder: %d tickers every %.0fs", len(self.tickers), self.interval_s)
        while True:
            t0 = self._now()
            await self.run_once()
            await self._sleep(max(1.0, self.interval_s - (self._now() - t0)))


# ----------------------------------------------------------------- status

def status(state_dir: Path) -> dict:
    """Rows on file per ticker, the days covered, and the latest row."""
    root = Path(state_dir) / "books"
    out = {}
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        files = sorted(d.glob("*.jsonl"))
        if not files:
            continue
        rows = sum(1 for p in files for _ in p.open())
        last = read_jsonl(files[-1])
        lr = last[-1] if last else {}
        out[d.name] = {"days": len(files), "rows": rows, "first": files[0].stem, "last_day": files[-1].stem,
                       "last_ts": lr.get("ts"), "spread_bp": lr.get("spread_bp"), "imb_25": lr.get("imb_25"),
                       "bid_usd_25": lr.get("bid_usd_25"), "ask_usd_25": lr.get("ask_usd_25"), "basis_bp": lr.get("basis_bp")}
    return out


def render(st: dict) -> str:
    if not st:
        return "no order-book rows yet"
    o = [f"{'ticker':14s} {'days':>4s} {'rows':>7s} {'spread':>7s} {'imb25':>6s} {'bid$25bp':>9s} {'ask$25bp':>9s} {'basis':>6s}  last"]
    for t, s in st.items():
        when = dt.datetime.fromtimestamp(s["last_ts"], dt.timezone.utc).strftime("%m-%d %H:%M") if s.get("last_ts") else "-"
        o.append(f"{t:14s} {s['days']:4d} {s['rows']:7d} {s['spread_bp'] or 0:6.1f}bp {s['imb_25'] or 0:+6.2f} "
                 f"{s['bid_usd_25'] or 0:9,.0f} {s['ask_usd_25'] or 0:9,.0f} {(s['basis_bp'] or 0):+5.1f}bp  {when}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--tickers", nargs="*", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.once:
        async def once():
            rec = BookRecorder(a.state, tickers=a.tickers or DEFAULT_TICKERS)
            try:
                return await rec.run_once()
            finally:
                await rec.close()
        out = asyncio.run(once())
        for t, r in out.items():
            print(t, "no book" if r is None else f"mid {r['mid']:.4f} spread {r['spread_bp']:.1f}bp imb25 {r['imb_25']:+.2f} "
                                                 f"depth25 ${r['bid_usd_25']:,.0f}/${r['ask_usd_25']:,.0f} basis {r['basis_bp'] if r['basis_bp'] is None else round(r['basis_bp'], 1)}")
        return 0
    print(render(status(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
