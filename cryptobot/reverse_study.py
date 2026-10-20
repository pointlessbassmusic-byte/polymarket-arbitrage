"""Pre-registered test `stop-and-reverse`: when the bounce-short is
stopped out, is the opposite position right?

For every walk-forward trade of the rule, find the day the +10% stop was
hit (conservative ordering: a day that touches both barriers counts as
the stop), open a LONG at the stop price with the mirrored geometry
(+20% target, -10% stop, 14 days) and score it with the same barrier
logic, net of the round trip. Variant B exits the short at +5% adverse
and reverses there instead. Reported by year with entry-day-clustered
t-statistics, next to what the stopped shorts themselves lost.
"""
from __future__ import annotations

import argparse
import math
import pickle
import statistics
from pathlib import Path

from .hedge_study import walk_forward_trades
from .perp_study import Barrier, _pct, collect, parse_rule

DAY = 86400


def index_candles(pools: dict) -> dict:
    out = {}
    for _, (meta, cs) in pools.items():
        out[meta.symbol] = {
            "ts": {int(c.ts // DAY) * DAY: i for i, c in enumerate(cs)},
            "high": [c.high for c in cs], "low": [c.low for c in cs], "close": [c.close for c in cs]}
    return out


def first_adverse_day(cd: dict, i: int, entry: float, level: float, target: float, horizon: int):
    """First day within the hold on which the short's price reaches
    entry x (1 + level) before the target; None if the target or the
    time exit came first."""
    tgt = entry * (1 - target)
    last = min(i + horizon, len(cd["close"]) - 1)
    for j in range(i + 1, last + 1):
        if cd["high"][j] >= entry * (1 + level):
            return j
        if cd["low"][j] <= tgt:
            return None
    return None


def reversal_outcome(cd: dict, j: int, entry: float, bar: Barrier, horizon: int) -> float:
    """Net-of-nothing realised return of a long from `entry` opened on day j,
    scored from day j+1 (the stop fill is intraday; the next bar is the
    first the reversal can be judged on)."""
    from .perp_study import outcome
    _, r = outcome(cd["high"], cd["low"], cd["close"], j, entry, bar, horizon, "long")
    return r


def study(pools: dict, trades: list[dict], *, level: float, bar: Barrier, horizon: int, cost: float) -> list[dict]:
    idx = index_candles(pools)
    rows = []
    for t in trades:
        cd = idx.get(t["symbol"])
        if cd is None:
            continue
        i = cd["ts"].get(int(t["ts"] // DAY) * DAY)
        if i is None:
            continue
        entry = cd["close"][i]
        j = first_adverse_day(cd, i, entry, level, bar.target, horizon)
        if j is None:
            continue
        rev_entry = entry * (1 + level)
        rows.append({"year": t["year"], "ts": t["ts"], "symbol": t["symbol"],
                     "short_loss": -level - cost, "reversal": reversal_outcome(cd, j, rev_entry, bar, horizon) - cost})
    return rows


def _stats(xs: list[float], stamps: int) -> dict:
    if len(xs) < 3:
        return {"n": len(xs), "mean": 0.0, "t": 0.0, "hit": 0.0}
    m, sd = statistics.mean(xs), statistics.stdev(xs)
    return {"n": len(xs), "mean": m, "t": (m / sd * math.sqrt(max(stamps, 1))) if sd else 0.0,
            "hit": sum(1 for x in xs if x > 0) / len(xs)}


def render(name: str, rows: list[dict], n_trades: int) -> str:
    out = [f"{name}: {len(rows)} of {n_trades} trades reached the reversal level",
           "year   n   hit   reversal mean    t     | stopped shorts' own loss"]
    pos = 0
    years = sorted({r["year"] for r in rows})
    for y in years:
        g = [r for r in rows if r["year"] == y]
        s = _stats([r["reversal"] for r in g], len({r["ts"] for r in g}))
        pos += s["mean"] > 0
        out.append(f"{y}  {s['n']:3d}  {100 * s['hit']:4.0f}%   {100 * s['mean']:+7.2f}%  {s['t']:+5.2f}   | {100 * statistics.mean(r['short_loss'] for r in g):+6.2f}%")
    s = _stats([r["reversal"] for r in rows], len({r["ts"] for r in rows}))
    out.append(f"all   {s['n']:3d}  {100 * s['hit']:4.0f}%   {100 * s['mean']:+7.2f}%  {s['t']:+5.2f}   positive years {pos}/{len(years)}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--rule", default="move_1d[2]&move_3d[0]")
    ap.add_argument("--target", type=float, default=0.20)
    ap.add_argument("--stop", type=float, default=0.10)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--cost", type=float, default=0.0017)
    ap.add_argument("--start-year", type=int, default=2022)
    args = ap.parse_args()
    pools = pickle.loads(args.cache.read_bytes())
    bar = Barrier(args.target, args.stop)
    rows = collect(pools, bar, args.days, "short")
    trades = [r for r in walk_forward_trades(rows, parse_rule(args.rule)) if r["year"] >= args.start_year]
    for name, level in (("A: reverse at the +10% stop", args.stop), ("B: exit and reverse at +5%", 0.05)):
        print(render(name, study(pools, trades, level=level, bar=bar, horizon=args.days, cost=args.cost), len(trades)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
