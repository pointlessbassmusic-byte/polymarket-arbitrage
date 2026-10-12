"""Out-of-sample tracker for `divergence-catchup-btc`.

The cross-asset study found that after a US session with stocks up more
than 0.5% and BTC down more than 0.5%, BTC's next 24 hours averaged
+0.41% (t 1.5, sign unstable). The registry's rule is that nothing found
in a sample is judged on that sample, so this records every qualifying
day from 2026-10-10 on and the BTC return that followed, until there are
enough to decide (60 qualifying days at the written bar).

Definitions match cryptobot.crossasset_study: S&P 500 close-to-close
from FRED's SP500 series (published the next morning), BTC sampled at
16:00 New York time from Coinbase hourly bars; a day's row is complete
once the following 16:00 ET print exists. Rows live in
state/oos/divergence.jsonl; the collector loop updates them daily.

    python -m cryptobot.oos_track --state state            # update
    python -m cryptobot.oos_track --state state --report
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import io
import json
import logging
import math
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx

from .crossasset_study import ET, price_at_et

logger = logging.getLogger(__name__)

START = dt.date(2026, 10, 10)          # the first out-of-sample day
THRESHOLD = 0.005
TARGET_DAYS = 60
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"
COINBASE_URL = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
FILE = Path("oos") / "divergence.jsonl"


def classify(spx: float, btc: float, threshold: float = THRESHOLD) -> Optional[str]:
    if spx > threshold and btc < -threshold:
        return "stocks up, BTC down"
    if spx < -threshold and btc > threshold:
        return "stocks down, BTC up"
    return None


def parse_fred(text: str) -> dict[dt.date, float]:
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or row[0] in ("observation_date", "DATE"):
            continue
        try:
            out[dt.date.fromisoformat(row[0])] = float(row[1])
        except ValueError:
            continue
    return out


def hourly_from_coinbase(rows: list) -> dict[int, tuple[float, float]]:
    """Coinbase candle rows [ts, low, high, open, close, vol] -> {ts: (open, close)}."""
    return {int(r[0]): (float(r[3]), float(r[4])) for r in rows}


def build_rows(spx: dict[dt.date, float], hourly: dict, start: dt.date = START,
               threshold: float = THRESHOLD) -> list[dict]:
    """One row per S&P session from `start`: the day's S&P and BTC
    moves, the class, and the next-24h BTC return when its print exists."""
    days = sorted(d for d in spx if d >= start)
    out = []
    for d in days:
        prev = max((p for p in spx if p < d), default=None)
        if prev is None:
            continue
        p16, p16_prev = price_at_et(hourly, d, 16), price_at_et(hourly, prev, 16)
        if not (p16 and p16_prev):
            continue
        spx_ret = math.log(spx[d] / spx[prev])
        btc_ret = math.log(p16 / p16_prev)
        nxt = price_at_et(hourly, d + dt.timedelta(days=1), 16)
        out.append({"day": d.isoformat(), "spx": spx_ret, "btc": btc_ret,
                    "kind": classify(spx_ret, btc_ret, threshold),
                    "btc_next24": math.log(nxt / p16) if nxt else None})
    return out


def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """Fresh rows replace same-day rows (a day completes when its next-24h
    print arrives); earlier rows are kept."""
    by = {r["day"]: r for r in existing}
    for r in fresh:
        old = by.get(r["day"])
        if old is None or old.get("btc_next24") is None:
            by[r["day"]] = r
    return [by[k] for k in sorted(by)]


def summary(rows: list[dict], target_days: int = TARGET_DAYS) -> dict:
    q = [r for r in rows if r.get("kind") == "stocks up, BTC down" and r.get("btc_next24") is not None]
    m = [r for r in rows if r.get("kind") == "stocks down, BTC up" and r.get("btc_next24") is not None]

    def stat(xs):
        if len(xs) < 2:
            return {"n": len(xs), "mean": statistics.fmean(xs) if xs else None, "t": None}
        sd = statistics.pstdev(xs)
        return {"n": len(xs), "mean": statistics.fmean(xs),
                "t": statistics.fmean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else None}
    out = {"days_tracked": len(rows), "first": rows[0]["day"] if rows else None, "last": rows[-1]["day"] if rows else None,
           "qualifying": stat([r["btc_next24"] for r in q]), "mirror": stat([r["btc_next24"] for r in m]),
           "target_days": target_days, "pending": sum(1 for r in rows if r.get("kind") and r.get("btc_next24") is None)}
    qs = out["qualifying"]
    out["decided"] = qs["n"] >= target_days
    if out["decided"]:
        ok = (qs["mean"] or 0) >= 0.003 - 0.0008 and (qs["t"] or 0) >= 2.0 and (out["mirror"]["mean"] or 0) >= 0
        out["verdict"] = "alive" if ok else "killed"
    else:
        out["verdict"] = "collecting"
    return out


def read_rows(state_dir: Path) -> list[dict]:
    p = Path(state_dir) / FILE
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def write_rows(state_dir: Path, rows: list[dict]) -> None:
    p = Path(state_dir) / FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


async def fetch_inputs(client: httpx.AsyncClient, days_back: int = 10) -> tuple[dict, dict]:
    r = await client.get(FRED_URL)
    if r.status_code >= 400:
        raise RuntimeError(f"FRED SP500 -> {r.status_code}")
    spx = parse_fred(r.text)
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=days_back)
    hourly: dict = {}
    t = start
    while t < end:
        e = min(t + dt.timedelta(hours=300), end)
        r = await client.get(COINBASE_URL, params={"granularity": 3600, "start": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                   "end": e.strftime("%Y-%m-%dT%H:%M:%SZ")})
        if r.status_code >= 400:
            raise RuntimeError(f"Coinbase candles -> {r.status_code}")
        hourly.update(hourly_from_coinbase(r.json()))
        t = e
    return spx, hourly


async def update(state_dir: Path, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Fetch the last days, rebuild their rows, merge, save; returns the summary."""
    own = client is None
    c = client or httpx.AsyncClient(timeout=60, headers={"User-Agent": "cryptobot-oos/1.0"})
    try:
        spx, hourly = await fetch_inputs(c)
    finally:
        if own:
            await c.aclose()
    first_day = max(START, dt.date.today() - dt.timedelta(days=12))
    fresh = build_rows(spx, hourly, start=first_day)
    rows = merge(read_rows(state_dir), fresh)
    write_rows(state_dir, rows)
    return summary(rows)


def render(rows: list[dict]) -> str:
    s = summary(rows)
    if not rows:
        return "divergence tracker: no rows yet"
    o = [f"divergence tracker ({s['first']} .. {s['last']}, {s['days_tracked']} sessions): "
         f"qualifying {s['qualifying']['n']} of {s['target_days']} needed, mirror {s['mirror']['n']}, "
         f"pending next-24h prints {s['pending']}, status {s['verdict']}"]
    for name in ("qualifying", "mirror"):
        st = s[name]
        if st["n"]:
            o.append(f"  {name}: n {st['n']}, mean next-24h {(st['mean'] or 0)*100:+.2f}%"
                     + (f", t {st['t']:+.1f}" if st["t"] is not None else ""))
    for r in [r for r in rows if r.get("kind")][-10:]:
        nxt = r.get("btc_next24")
        o.append(f"  {r['day']} {r['kind']:20s} S&P {r['spx']*100:+.2f}% BTC {r['btc']*100:+.2f}% "
                 f"-> next 24h {nxt*100:+.2f}%" if nxt is not None else
                 f"  {r['day']} {r['kind']:20s} S&P {r['spx']*100:+.2f}% BTC {r['btc']*100:+.2f}% -> pending")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not a.report:
        print(json.dumps(asyncio.run(update(a.state)), indent=1, default=str))
    print(render(read_rows(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
