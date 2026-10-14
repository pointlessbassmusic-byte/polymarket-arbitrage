"""`kalshi-perps-maker-taker`: does providing liquidity on Kalshi perps
earn more than the 2 bp maker fee after adverse selection, and does
taker order flow predict the next minutes?

Input: the public trade tape (cryptobot.perp_tape), one row per trade:
[ts, price, contracts, taker side (+1 buy, -1 sell), id].

Maker markout. The maker on each trade is on the opposite side of the
taker. Fair value at t + h is the median price of the next 5 trades
after t + h. Maker markout (bp of price) = -side x (FV - p) / p x 1e4,
contract-weighted; net subtracts the 2 bp maker fee. The taker's
markout at 10 s is the effective cost of crossing (half-spread plus
impact). t is clustered by clock hour, halves by date.

Flow. On a 5-minute grid, net signed contracts over the prior 5 and 30
minutes (standardised) against the next 5 and 30 minutes' trade-price
return, Newey-West; a sign rule (long when flow > 0, short when < 0)
net of 4 bp (maker in and out) and of 12 bp (taker: fees plus the
measured half-spread, rounded).

    python -m cryptobot.maker_taker_study --state <dir with tape/>
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from .binary_tails_study import cluster_t
from .crossasset_study import ols
from .perp_tape import DEFAULT

MAKER_FEE_BP = 2.0
TAKER_FEE_BP = 4.0
HORIZONS = (10, 60, 300, 1800)
NEXT_K = 5
GRID = 300


def load(path: Path) -> list[list]:
    rows = {}
    for line in path.open():
        if line.strip():
            r = json.loads(line)
            rows[r[4]] = r
    return sorted(rows.values(), key=lambda r: (r[0], r[4]))


def fair_after(ts: list[float], px: list[float], t: float) -> float | None:
    i = bisect.bisect_right(ts, t)
    if i + NEXT_K > len(ts):
        return None
    return statistics.median(px[i:i + NEXT_K])


def markouts(rows: list[list]) -> dict:
    ts = [r[0] for r in rows]
    px = [r[1] for r in rows]
    sizes = sorted(r[2] for r in rows)
    big = sizes[int(0.9 * len(sizes))] if sizes else 0
    days = sorted({dt.datetime.fromtimestamp(r[0], dt.timezone.utc).date().isoformat() for r in rows})
    mid_day = days[len(days) // 2] if days else ""
    out = {}
    for h in HORIZONS:
        per = []           # (maker bp, weight, hour, day, big, busy)
        for r in rows:
            fv = fair_after(ts, px, r[0] + h)
            if fv is None:
                continue
            m = -r[3] * (fv - r[1]) / r[1] * 1e4
            t = dt.datetime.fromtimestamp(r[0], dt.timezone.utc)
            per.append((m, r[2], int(r[0] // 3600), t.date().isoformat(), r[2] >= big, 13 <= t.hour < 17))
        if not per:
            continue
        def wmean(xs):
            w = sum(x[1] for x in xs)
            return sum(x[0] * x[1] for x in xs) / w if w else float("nan")
        # clustered t on hourly contract-weighted means
        by_h = defaultdict(list)
        for x in per:
            by_h[x[2]].append(x)
        hourly = [wmean(v) - MAKER_FEE_BP for v in by_h.values()]
        hs = statistics.pstdev(hourly) if len(hourly) > 2 else 0.0
        h1 = [x for x in per if x[3] < mid_day]
        h2 = [x for x in per if x[3] >= mid_day]
        out[h] = {"n": len(per), "maker_gross_bp": wmean(per), "maker_net_bp": wmean(per) - MAKER_FEE_BP,
                  "t": statistics.fmean(hourly) / (hs / math.sqrt(len(hourly))) if hs > 0 else 0.0,
                  "h1": wmean(h1) - MAKER_FEE_BP if h1 else None, "h2": wmean(h2) - MAKER_FEE_BP if h2 else None,
                  "big_trades": wmean([x for x in per if x[4]]) - MAKER_FEE_BP,
                  "small_trades": wmean([x for x in per if not x[4]]) - MAKER_FEE_BP,
                  "us_hours": wmean([x for x in per if x[5]]) - MAKER_FEE_BP,
                  "other_hours": wmean([x for x in per if not x[5]]) - MAKER_FEE_BP}
    if 10 in out:
        out["taker_cost_10s_bp"] = -out[10]["maker_gross_bp"] + TAKER_FEE_BP
    return out


def flow(rows: list[list]) -> dict:
    if len(rows) < 1000:
        return {}
    t0 = int(rows[0][0] // GRID) * GRID
    t1 = int(rows[-1][0] // GRID) * GRID
    net = defaultdict(float)
    last_px = {}
    for r in rows:
        b = int(r[0] // GRID) * GRID
        net[b] += r[2] * r[3]
        last_px[b] = r[1]
    grid = list(range(t0, t1 + GRID, GRID))
    price, p = [], None
    for g in grid:
        p = last_px.get(g, p)
        price.append(p)
    out = {}
    days = sorted({dt.datetime.fromtimestamp(g, dt.timezone.utc).date().isoformat() for g in grid})
    mid_day = days[len(days) // 2]
    for look in (1, 6):                   # 5 and 30 minutes of flow
        for ahead in (1, 6):              # next 5 and 30 minutes
            xs, ys, dd = [], [], []
            for i in range(look, len(grid) - ahead):
                if price[i] is None or price[i + ahead] is None:
                    continue
                f = sum(net.get(grid[k], 0.0) for k in range(i - look + 1, i + 1))
                xs.append(f)
                ys.append(math.log(price[i + ahead] / price[i]) * 1e4)
                dd.append(dt.datetime.fromtimestamp(grid[i], dt.timezone.utc).date().isoformat())
            if len(xs) < 200:
                continue
            m, s = statistics.fmean(xs), statistics.pstdev(xs)
            z = [[(x - m) / s if s > 0 else 0.0] for x in xs]
            reg = ols(ys, z, nw_lags=max(ahead, 5))
            # sign rule, non-overlapping: step by `ahead`
            trades = [(math.copysign(1, x) * y, d) for k, (x, y, d) in enumerate(zip(xs, ys, dd)) if k % ahead == 0 and x != 0]
            g = [v for v, _ in trades]
            out[f"{look * 5}m flow -> next {ahead * 5}m"] = {
                "n": len(xs), "beta_bp_per_sd": reg["beta"][1], "t": reg["t"][1],
                "rule_gross_bp": statistics.fmean(g) if g else None,
                "rule_maker_net_bp": (statistics.fmean(g) - 2 * MAKER_FEE_BP) if g else None,
                "rule_taker_net_bp": (statistics.fmean(g) - 12.0) if g else None,
                "rule_t": cluster_t(g, [d for _, d in trades]) if g else 0.0,
                "h1": statistics.fmean([v for v, d in trades if d < mid_day] or [0.0]) - 2 * MAKER_FEE_BP,
                "h2": statistics.fmean([v for v, d in trades if d >= mid_day] or [0.0]) - 2 * MAKER_FEE_BP}
    return out


def run(state: Path, tickers=None) -> dict:
    res = {"tickers": {}}
    for tk in tickers or DEFAULT:
        p = state / "tape" / f"{tk}.jsonl"
        if not p.exists():
            continue
        rows = load(p)
        if len(rows) < 1000:
            continue
        res["tickers"][tk] = {"trades": len(rows), "days": round((rows[-1][0] - rows[0][0]) / 86400, 1),
                              "contracts_per_day": sum(r[2] for r in rows) / max((rows[-1][0] - rows[0][0]) / 86400, 1e-9),
                              "buy_share": sum(r[2] for r in rows if r[3] > 0) / sum(r[2] for r in rows),
                              "markout": markouts(rows), "flow": flow(rows)}
    cands, killed = [], []
    for tk, v in res["tickers"].items():
        m = v["markout"].get(300)
        m60 = v["markout"].get(60)
        if m and m["maker_net_bp"] >= 1 and m["t"] >= 2.5 and (m["h1"] or 0) > 0 and (m["h2"] or 0) > 0:
            cands.append(f"maker {tk}")
        if m and m60 and m["maker_net_bp"] < 0 and m60["maker_net_bp"] < 0:
            killed.append(f"maker {tk}")
        for k, f in v["flow"].items():
            if f["rule_maker_net_bp"] is not None and f["rule_maker_net_bp"] >= 4 and f["rule_t"] >= 2.5 and f["h1"] > 0 and f["h2"] > 0:
                cands.append(f"flow {tk} {k}")
    res["candidates"], res["killed"] = cands, killed
    return res


def render(res: dict) -> str:
    o = ["Kalshi perps, maker vs taker on the public tape; maker fee 2 bp, taker 4 bp; markout vs the median of the next 5 trades after t+h"]
    o.append(f"  {'ticker':13s} {'days':>4s} {'trades':>8s} {'buy%':>5s} {'taker cost':>10s} | maker net bp at 10s / 60s / 300s / 1800s (t at 300s) | 300s: halves, big vs small trades, 13-17 UTC vs other")
    for tk, v in res["tickers"].items():
        m = v["markout"]
        nets = " / ".join(f"{m[h]['maker_net_bp']:+.1f}" if h in m else "-" for h in HORIZONS)
        m3 = m.get(300, {})
        extra = (f"{m3.get('h1', 0):+.1f}/{m3.get('h2', 0):+.1f}, big {m3.get('big_trades', 0):+.1f} small {m3.get('small_trades', 0):+.1f}, "
                 f"US {m3.get('us_hours', 0):+.1f} other {m3.get('other_hours', 0):+.1f}") if m3 else ""
        o.append(f"  {tk:13s} {v['days']:4.0f} {v['trades']:8d} {v['buy_share']:5.0%} {m.get('taker_cost_10s_bp', 0):9.1f}bp | {nets} (t {m3.get('t', 0):+.1f}) | {extra}")
    o.append("  taker flow -> next return (beta bp per sd of flow, t; sign rule net bp at maker cost, t)")
    for tk, v in res["tickers"].items():
        parts = [f"{k}: {f['beta_bp_per_sd']:+.2f} (t {f['t']:+.1f}); rule {f['rule_maker_net_bp']:+.1f} (t {f['rule_t']:+.1f})" for k, f in v["flow"].items()]
        o.append(f"    {tk:13s} " + "; ".join(parts))
    o.append(f"verdict: candidates {res['candidates'] or 'none'}; killed {res['killed'] or 'none'}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("tickers", nargs="*")
    a = ap.parse_args(argv)
    res = run(a.state, a.tickers or None)
    print(render(res))
    (a.state / "maker_taker_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
