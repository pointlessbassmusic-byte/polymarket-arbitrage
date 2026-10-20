"""`kalshi-polyus-crossvenue`: the same BTC contract on Kalshi and on
Polymarket US. Both settle on CF Benchmarks' BRTI, averaged over the 60
seconds before the settlement instant; Polymarket's "at or above K" is
Kalshi's "above K - 0.01" (two-decimal settlement), and the 15-minute
up/down markets both settle ties as Up.

The recorder polls both public books for every matched pair and writes
the two-sided prices and sizes. The locked edge of a pair, per contract
at N contracts, net of both taker fees:

  A  YES at Kalshi's ask + NO at Polymarket (sell YES at its bid)
     = 1 - K_ask - (1 - P_bid) - fees  = P_bid - K_ask - fees
  B  YES at Polymarket's ask + NO at Kalshi (1 - Kalshi's YES bid)
     = K_bid - P_ask - fees

Kalshi's fee is 0.07 x C x p x (1-p), rounded up to the cent per order;
Polymarket US's taker fee is 0.0695 x C x p x (1-p).

CAUTION: Polymarket US's public /bbo and /book endpoints are snapshots
refreshed about every 30 seconds (tested 2026-10-14: 7 changes in 157
one-second polls against Kalshi's 124; the sizes are not the book's).
Gaps against Kalshi's live book on fast markets (15-minute, hourly near
expiry) are mostly that staleness. Each row carries `p_ts`, the
snapshot's own timestamp, and `p_age_s`.

    python -m cryptobot.crossvenue_recorder --dir <dir> --hours 6
    python -m cryptobot.crossvenue_recorder --dir <dir> --report
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

PM = "https://gateway.polymarket.us"
KA = "https://api.elections.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "cryptobot-research/0.1", "Accept": "application/json"}
SIZE = 10
K_FEE, P_FEE = 0.07, 0.0695
MON = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def kalshi_fee(p: float, n: int = SIZE) -> float:
    return math.ceil(round(K_FEE * n * p * (1 - p) * 100, 6)) / 100


def pm_fee(p: float, n: int = SIZE) -> float:
    return P_FEE * n * p * (1 - p)


def edges(k_bid, k_ask, p_bid, p_ask, n: int = SIZE) -> tuple[Optional[float], Optional[float]]:
    """Locked profit per contract for direction A and B (None when a side has no quote)."""
    a = b = None
    if k_ask is not None and p_bid is not None:
        cost = n * k_ask + kalshi_fee(k_ask, n) + n * (1 - p_bid) + pm_fee(p_bid, n)
        a = (n - cost) / n
    if p_ask is not None and k_bid is not None:
        cost = n * p_ask + pm_fee(p_ask, n) + n * (1 - k_bid) + kalshi_fee(1 - k_bid, n)
        b = (n - cost) / n
    return a, b


def kalshi_code(close_et: dt.datetime) -> str:
    return f"{close_et:%y}{MON[close_et.month - 1]}{close_et:%d}{close_et:%H}"


def match(pm_markets: list[dict]) -> list[dict]:
    """Pairs (family, Polymarket slug, Kalshi ticker, strike, close time) for the above/below ladders and 15-minute up/down."""
    out = []
    for m in pm_markets:
        s = m.get("slug") or ""
        mo = re.match(r"cpc-btc-above-(hr|day|wk)-(\d{4})-(\d{2})-(\d{2})(?:-(\d{2})00z)?-(\d+)$", s)
        if mo:
            fam, y, mth, d, hz, k = mo.groups()
            if fam == "hr":
                close = dt.datetime(int(y), int(mth), int(d), int(hz), tzinfo=dt.timezone.utc).astimezone(ET)
            else:
                close = dt.datetime(int(y), int(mth), int(d), 17, tzinfo=ET)
            strike = float(k)
            ticker = f"KXBTCD-{kalshi_code(close)}-T{strike - 0.01:.2f}"
            out.append({"family": {"hr": "hourly", "day": "daily", "wk": "weekly"}[fam], "slug": s, "ticker": ticker,
                        "strike": strike, "close": close.timestamp()})
            continue
        mo = re.match(r"cpc-btc-updown-15m-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})z$", s)
        if mo:
            y, mth, d, hh, mm = map(int, mo.groups())
            start = dt.datetime(y, mth, d, hh, mm, tzinfo=dt.timezone.utc)
            close = (start + dt.timedelta(minutes=15)).astimezone(ET)
            ticker = f"KXBTC15M-{close:%y}{MON[close.month - 1]}{close:%d%H%M}-{close:%M}"
            out.append({"family": "15m", "slug": s, "ticker": ticker, "strike": None, "close": close.timestamp()})
    return out


class Recorder:
    def __init__(self, d: Path, client=None, pace_s: float = 0.12):
        self.dir = Path(d) / "crossvenue"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.c = client or httpx.Client(timeout=20, headers=UA)
        self.pace_s = pace_s
        self.pairs: list[dict] = []
        self.k_missing: set[str] = set()

    def _get(self, url, params=None):
        for a in range(4):
            try:
                r = self.c.get(url, params=params)
                if r.status_code == 429:
                    time.sleep(2 + 2 * a)
                    continue
                return r
            except httpx.TransportError:
                time.sleep(1 + a)
        return None

    def discover(self) -> int:
        ms, off = [], 0
        while True:
            r = self._get(f"{PM}/v1/markets", {"limit": 500, "offset": off, "active": "true", "closed": "false"})
            page = (r.json().get("markets") if r is not None and r.status_code == 200 else None) or []
            ms += [m for m in page if (m.get("slug") or "").startswith("cpc-btc-")]
            if len(page) < 500:
                break
            off += 500
        now = time.time()
        self.pairs = [p for p in match(ms) if p["close"] > now + 60 and p["ticker"] not in self.k_missing]
        return len(self.pairs)

    def k_book(self, ticker: str):
        r = self._get(f"{KA}/markets/{ticker}/orderbook")
        if r is None or r.status_code == 404:
            self.k_missing.add(ticker)
            return None
        if r.status_code != 200:
            return None
        ob = r.json().get("orderbook_fp") or {}
        yes = [(float(p), float(q)) for p, q in ob.get("yes_dollars") or []]
        no = [(float(p), float(q)) for p, q in ob.get("no_dollars") or []]
        kb = max(yes) if yes else None
        nb = max(no) if no else None
        return {"k_bid": kb[0] if kb else None, "k_bid_sz": kb[1] if kb else 0.0,
                "k_ask": round(1 - nb[0], 4) if nb else None, "k_ask_sz": nb[1] if nb else 0.0}

    def p_book(self, slug: str):
        r = self._get(f"{PM}/v1/markets/{slug}/bbo")
        if r is None or r.status_code != 200:
            return None
        md = r.json().get("marketData") or {}
        def v(x):
            try:
                return float((x or {}).get("value"))
            except (TypeError, ValueError):
                return None
        ts = (md.get("lastPriceSample") or {}).get("ts")
        age = None
        if ts:
            try:
                age = time.time() - dt.datetime.fromisoformat(ts[:26].rstrip("Z") + "+00:00").timestamp()
            except ValueError:
                age = None
        return {"p_bid": v(md.get("bestBid")), "p_ask": v(md.get("bestAsk")),
                "p_bid_sz": float(md.get("bidShares") or 0), "p_ask_sz": float(md.get("askShares") or 0),
                "p_ts": ts, "p_age_s": round(age, 1) if age is not None else None}

    def near(self, limit_per_family: int = 14) -> list[dict]:
        """The pairs worth polling: per family, the soonest expiry and the strikes nearest the middle of the ladder."""
        by = defaultdict(list)
        for p in self.pairs:
            by[p["family"]].append(p)
        out = []
        for fam, ps in by.items():
            first = min(p["close"] for p in ps)
            ps = [p for p in ps if p["close"] == first]
            if fam == "15m":
                out += ps
                continue
            ps.sort(key=lambda p: p["strike"])
            mid = getattr(self, "_mid", {}).get(fam)
            if mid is None:
                mid = ps[len(ps) // 2]["strike"]
            ps.sort(key=lambda p: abs(p["strike"] - mid))
            out += ps[:limit_per_family]
        return out

    def snapshot(self) -> int:
        n = 0
        f = (self.dir / f"{dt.date.today().isoformat()}.jsonl").open("a")
        mids = defaultdict(list)
        for p in self.near():
            kb = self.k_book(p["ticker"])
            time.sleep(self.pace_s)
            pb = self.p_book(p["slug"])
            time.sleep(self.pace_s)
            if not kb or not pb:
                continue
            a, b = edges(kb["k_bid"], kb["k_ask"], pb["p_bid"], pb["p_ask"])
            row = {"ts": round(time.time(), 1), **{k: p[k] for k in ("family", "slug", "ticker", "strike", "close")}, **kb, **pb,
                   "edge_a": a, "edge_b": b}
            f.write(json.dumps(row) + "\n")
            n += 1
            if kb["k_bid"] is not None and kb["k_ask"] is not None and p["strike"] is not None and 0.2 < (kb["k_bid"] + kb["k_ask"]) / 2 < 0.8:
                mids[p["family"]].append(p["strike"])
        f.close()
        self._mid = {k: statistics.median(v) for k, v in mids.items()}
        return n

    def run(self, hours: float, every_s: float = 30.0) -> int:
        end, total, last_disc = time.time() + hours * 3600, 0, 0.0
        while time.time() < end:
            t0 = time.time()
            if t0 - last_disc > 600:
                self.discover()
                last_disc = t0
            total += self.snapshot()
            time.sleep(max(1.0, every_s - (time.time() - t0)))
        return total


def report(d: Path, min_edge: float = 0.01, min_size: float = SIZE) -> str:
    rows = []
    for p in sorted((Path(d) / "crossvenue").glob("*.jsonl")):
        rows += [json.loads(l) for l in p.open() if l.strip()]
    if not rows:
        return "no cross-venue rows yet"
    o = [f"Kalshi vs Polymarket US, same BRTI contracts: {len(rows)} pair snapshots, "
         f"{(rows[-1]['ts'] - rows[0]['ts']) / 3600:.1f} hours; locked edge per contract at {SIZE} contracts net of both taker fees"]
    by = defaultdict(list)
    for r in rows:
        by[r["family"]].append(r)
    for fam, rs in sorted(by.items()):
        both = [r for r in rs if None not in (r["k_bid"], r["k_ask"], r["p_bid"], r["p_ask"])]
        diffs = [abs((r["k_bid"] + r["k_ask"]) / 2 - (r["p_bid"] + r["p_ask"]) / 2) for r in both]
        best = [max(x for x in (r["edge_a"], r["edge_b"]) if x is not None) for r in rs if r["edge_a"] is not None or r["edge_b"] is not None]
        good = []
        for r in rs:
            if r["edge_a"] is not None and r["edge_a"] >= min_edge and r["k_ask_sz"] >= min_size and r["p_bid_sz"] >= min_size:
                good.append((r, "A", r["edge_a"]))
            if r["edge_b"] is not None and r["edge_b"] >= min_edge and r["p_ask_sz"] >= min_size and r["k_bid_sz"] >= min_size:
                good.append((r, "B", r["edge_b"]))
        # episodes: same pair and direction, consecutive snapshots within 90 s
        eps, last = [], {}
        for r, side, e in sorted(good, key=lambda x: x[0]["ts"]):
            k = (r["slug"], side)
            if k in last and r["ts"] - last[k][-1]["end"] <= 90:
                last[k][-1]["end"] = r["ts"]
                last[k][-1]["edges"].append(e)
            else:
                ep = {"start": r["ts"], "end": r["ts"], "edges": [e], "slug": r["slug"], "side": side}
                last.setdefault(k, []).append(ep)
                eps.append(ep)
        o.append(f"  {fam:7s} snapshots {len(rs):6d}; mid-price gap between venues median {statistics.median(diffs) * 100 if diffs else 0:.1f}c, "
                 f"p90 {sorted(diffs)[int(.9 * len(diffs))] * 100 if diffs else 0:.1f}c; best locked edge median {statistics.median(best) * 100 if best else 0:+.1f}c, "
                 f"max {max(best) * 100 if best else 0:+.1f}c")
        o.append(f"          snapshots with edge >= {min_edge * 100:.0f}c and >= {min_size:.0f} contracts both sides: {len(good)}; episodes {len(eps)}"
                 + (f"; longest {max(e['end'] - e['start'] for e in eps):.0f}s, lasting >= 30s: {sum(1 for e in eps if e['end'] - e['start'] >= 30)}, "
                    f"median edge {statistics.median([statistics.fmean(e['edges']) for e in eps]) * 100:+.1f}c" if eps else ""))
        for e in sorted(eps, key=lambda e: -statistics.fmean(e["edges"]))[:5]:
            o.append(f"            {e['slug']} side {e['side']}: {statistics.fmean(e['edges']) * 100:+.1f}c for {e['end'] - e['start']:.0f}s "
                     f"from {dt.datetime.fromtimestamp(e['start'], ET):%m-%d %H:%M} ET")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path("."))
    ap.add_argument("--hours", type=float, default=6)
    ap.add_argument("--every", type=float, default=30)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    if not a.report:
        rec = Recorder(a.dir)
        print(f"matched pairs: {rec.discover()}", flush=True)
        print(f"recorded {rec.run(a.hours, a.every)} pair snapshots", flush=True)
    print(report(a.dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
