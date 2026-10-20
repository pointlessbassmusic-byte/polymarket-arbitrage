"""`daytrade-timeblock`: backtest the day trading bot's time-block scalper.

Three variants (cryptobot.daytrade) x 15m and 30m x BTC, ETH, SOL, DOGE
on two years of Coinbase 15-minute candles (30m resampled), at Kalshi
perps taker costs. Per cell: trades, net bp a trade, t clustered by day,
halves, win rate, exit mix, by window; DSR at the 24 trials.

    python -m cryptobot.daytrade_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

from .binary_tails_study import cluster_t
from .daytrade import VARIANTS, backtest, cost_bp, resample
from .stats import dsr

ASSETS = ("BTC", "ETH", "SOL", "DOGE")
FRAMES = (("15m", 900), ("30m", 1800))


def load(scratch: Path, asset: str):
    p = scratch / "dt" / f"{asset}_15m.json"
    return [tuple(r) for r in json.loads(p.read_text())] if p.exists() else []


def summarize(tr: list[dict]) -> dict:
    if len(tr) < 5:
        return {"n": len(tr)}
    nets = [t["net_bp"] for t in tr]
    days = [dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).date().isoformat() for t in tr]
    mid = sorted(days)[len(days) // 2]
    out = {"n": len(tr), "net": statistics.fmean(nets), "gross": statistics.fmean(t["gross_bp"] for t in tr),
           "t": cluster_t(nets, days), "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
           "h1": statistics.fmean([x for x, d in zip(nets, days) if d < mid] or [0.0]),
           "h2": statistics.fmean([x for x, d in zip(nets, days) if d >= mid] or [0.0]),
           "sr": statistics.fmean(nets) / statistics.pstdev(nets) if statistics.pstdev(nets) > 0 else 0.0,
           "exits": {k: sum(1 for t in tr if t["reason"] == k) / len(tr) for k in ("target", "stop", "flat_out_of_hours")}}
    for w in ("bull", "bear"):
        x = [t["net_bp"] for t in tr if t["window"] == w]
        out[w] = (len(x), statistics.fmean(x) if x else None)
    out["per_day"] = len(tr) / max(1, len(set(days)))
    return out


def run(scratch: Path) -> dict:
    cells = {}
    for asset in ASSETS:
        b15 = load(scratch, asset)
        if not b15:
            continue
        for fname, sec in FRAMES:
            bars = b15 if sec == 900 else resample(b15, sec)
            for v in VARIANTS:
                tr = backtest(bars, v, asset)
                cells[(v, fname, asset)] = {"summary": summarize(tr), "returns": [t["net_bp"] / 1e4 for t in tr]}
    srs = [c["summary"]["sr"] for c in cells.values() if c["summary"].get("n", 0) >= 5]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    n_trials = max(1, len(cells))
    for c in cells.values():
        r = c.pop("returns")
        c["summary"]["dsr"] = dsr(r, n_trials, var_sr) if len(r) >= 20 else None
    cands, by_variant = [], {}
    for (v, f, a), c in cells.items():
        s = c["summary"]
        by_variant.setdefault(v, []).append(s.get("net", 0.0))
        if (s.get("n", 0) >= 200 and s["net"] >= 5 and s["t"] >= 2.5 and s["h1"] > 0 and s["h2"] > 0
                and (s["dsr"] or 0) >= 0.95):
            cands.append(f"{v} {f} {a}")
    killed = [v for v, nets in by_variant.items() if nets and all(x < 0 for x in nets)]
    return {"cells": {f"{v}|{f}|{a}": c["summary"] for (v, f, a), c in cells.items()}, "candidates": cands,
            "killed_variants": killed, "trials": n_trials}


def render(res: dict) -> str:
    o = ["day trading bot, time-block scalper, Coinbase 15m candles (30m resampled), Kalshi perps taker costs: "
         + ", ".join(f"{a} {cost_bp(a):.1f} bp" for a in ASSETS) + " a round trip"]
    o.append(f"  {'cell':16s} {'trades':>6s} {'/day':>5s} {'gross':>7s} {'net bp':>7s} {'t':>5s} {'win':>4s} {'halves':>13s} {'DSR':>5s}  bull window / bear window (n, net)   exits tgt/stop/flat")
    for k, s in res["cells"].items():
        v, f, a = k.split("|")
        if s.get("n", 0) < 5:
            o.append(f"  {v} {f} {a:5s} n {s.get('n', 0)}")
            continue
        bu, be = s["bull"], s["bear"]
        ex = s["exits"]
        o.append(f"  {v} {f} {a:5s}   {s['n']:6d} {s['per_day']:5.2f} {s['gross']:+7.1f} {s['net']:+7.1f} {s['t']:+5.1f} {s['hit']:4.0%} "
                 f"{s['h1']:+6.1f}/{s['h2']:+6.1f} {s['dsr'] if s['dsr'] is not None else 0:5.2f}  "
                 f"{bu[0]} {bu[1] if bu[1] is not None else 0:+.1f} / {be[0]} {be[1] if be[1] is not None else 0:+.1f}   "
                 f"{ex['target']:.0%}/{ex['stop']:.0%}/{ex['flat_out_of_hours']:.0%}")
    o.append(f"verdict: candidates {res['candidates'] or 'none'}; variants killed (negative on every cell) {res['killed_variants'] or 'none'}; {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    res = run(a.scratch)
    print(render(res))
    (a.scratch / "daytrade_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
