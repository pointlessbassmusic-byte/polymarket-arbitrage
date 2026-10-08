"""Pre-registered test `btc-beta-hedge-bounce-short`: does a long BTC
hedge, sized to the prior years' beta, improve the bounce-short?

Memecoin shorts lose in BTC rallies. For every walk-forward trade of the
rule (cuts refit on prior years), take BTC's close-to-close return over
the same horizon from the entry day, fit beta = cov / var on the trades
of PRIOR years only, and compare hedged P&L (trade + beta x BTC - hedge
cost) with unhedged, by year. The hedge over the full horizon
over-hedges trades that exit early at a barrier, which is the
conservative direction for the hedge's own return.
"""
from __future__ import annotations

import argparse
import math
import pickle
import statistics
from pathlib import Path

from .perp_study import Barrier, collect, parse_rule
from .research import bucket_of, quantiles

DAY = 86400
HEDGE_RT = 0.0010           # BTC perp round trip, per unit of hedge notional


def btc_forward(all_pools: dict, horizon: int) -> dict[int, float]:
    """day -> BTC close-to-close return over `horizon` days."""
    for key, (meta, cs) in all_pools.items():
        if meta.symbol == "BTC":
            closes = {int(c.ts // DAY) * DAY: c.close for c in cs if c.close > 0}
            return {d: closes[d + horizon * DAY] / px - 1.0
                    for d, px in closes.items() if d + horizon * DAY in closes}
    raise ValueError("BTC not in the all-perps cache")


def walk_forward_trades(rows, rule, min_fit_years: int = 2) -> list[dict]:
    (f1, b1), (f2, b2) = rule
    years = sorted({r["year"] for r in rows})
    out = []
    for y in years[min_fit_years:]:
        fit = [r for r in rows if r["year"] < y]
        cuts = {f: quantiles(fit, f, 3) for f in (f1, f2)}
        out += [r for r in rows if r["year"] == y and bucket_of(r[f1], cuts[f1]) == b1
                and bucket_of(r[f2], cuts[f2]) == b2]
    return out


def _beta(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 20:
        return 0.0
    xs, ys = [b for _, b in pairs], [p for p, _ in pairs]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    var = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else 0.0


def _stats(xs: list[float], stamps: int) -> dict:
    if len(xs) < 3:
        return {"n": len(xs), "mean": 0.0, "sd": 0.0, "sr": 0.0, "t": 0.0}
    m, sd = statistics.mean(xs), statistics.stdev(xs)
    sr = m / sd if sd else 0.0
    return {"n": len(xs), "mean": m, "sd": sd, "sr": sr, "t": sr * math.sqrt(max(stamps, 1))}


def study(trades: list[dict], btc_fwd: dict[int, float], cost: float) -> list[dict]:
    """Per year: unhedged vs hedged with beta from prior years' trades."""
    for r in trades:
        d = int(r["ts"] // DAY) * DAY
        r["btc"] = btc_fwd.get(d)
    trades = [r for r in trades if r["btc"] is not None]
    out = []
    for y in sorted({r["year"] for r in trades}):
        prior = [(-(r["pnl"]) if False else r["pnl"], r["btc"]) for r in trades if r["year"] < y]
        beta = -_beta(prior)                       # trades lose when BTC rises: hedge is LONG BTC
        beta = max(0.0, beta)
        g = [r for r in trades if r["year"] == y]
        stamps = len({r["ts"] for r in g})
        un = [r["pnl"] - cost for r in g]
        he = [r["pnl"] - cost + beta * r["btc"] - HEDGE_RT * beta for r in g]
        out.append({"year": y, "beta": beta, "unhedged": _stats(un, stamps), "hedged": _stats(he, stamps),
                    "corr": _corr([r["pnl"] for r in g], [r["btc"] for r in g])})
    return out


def _corr(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def render(rows: list[dict]) -> str:
    out = ["year  n   beta  corr(pnl,btc)   unhedged mean  SR     t   |  hedged mean  SR     t"]
    better = 0
    for r in rows:
        u, h = r["unhedged"], r["hedged"]
        better += h["sr"] > u["sr"]
        out.append(f"{r['year']} {u['n']:4d}  {r['beta']:+.2f}   {r['corr']:+.2f}        "
                   f"{100 * u['mean']:+6.2f}%  {u['sr']:+.3f} {u['t']:+5.2f}  |  "
                   f"{100 * h['mean']:+6.2f}%  {h['sr']:+.3f} {h['t']:+5.2f}")
    out.append(f"hedged Sharpe higher in {better} of {len(rows)} years")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--all", type=Path, required=True, help="all-perps cache with BTC")
    ap.add_argument("--rule", default="move_1d[2]&move_3d[0]")
    ap.add_argument("--target", type=float, default=0.20)
    ap.add_argument("--stop", type=float, default=0.10)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--cost", type=float, default=0.0017, help="round trip incl. funding, per trade")
    ap.add_argument("--start-year", type=int, default=2022)
    args = ap.parse_args()
    pools = pickle.loads(args.cache.read_bytes())
    rows = collect(pools, Barrier(args.target, args.stop), args.days, "short")
    trades = [r for r in walk_forward_trades(rows, parse_rule(args.rule)) if r["year"] >= args.start_year]
    btc = btc_forward(pickle.loads(args.all.read_bytes()), args.days)
    print(render(study(trades, btc, args.cost)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
