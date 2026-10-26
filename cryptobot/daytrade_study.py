"""`daytrade-timeblock`: backtest the day trading bot's time-block scalper.

Three variants (cryptobot.daytrade) x 15m and 30m x BTC, ETH, SOL, DOGE
on two years of Coinbase 15-minute candles (30m resampled), at Kalshi
perps taker costs. Every trade is also scored on spot, a 15-minute and an hourly Kalshi
binary (cryptobot.daytrade.score): 24 cells x 4 instruments = 96 trials.
Per cell: trades, net bp a trade, t clustered by day,
halves, win rate, exit mix, by window; DSR at the 24 trials.

    python -m cryptobot.daytrade_study --scratch <dir> --fetch     # --fetch pulls the candles first (about 10 minutes)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

from .binary_tails_study import cluster_t
from .daytrade import INSTRUMENTS, VARIANTS, backtest, cost_bp, resample, score, spot_cost_bp
from .stats import dsr

ASSETS = ("BTC", "ETH", "SOL", "DOGE")
FRAMES = (("15m", 900), ("30m", 1800))


def fetch(scratch: Path, days: int = 730) -> None:
    """Two years of Coinbase public 15-minute candles per asset, to scratch dt/<COIN>_15m.json."""
    import time
    import httpx
    out_dir = scratch / "dt"
    out_dir.mkdir(parents=True, exist_ok=True)
    end = int(time.time()) // 900 * 900
    with httpx.Client(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"}) as c:
        for a in ASSETS:
            rows, t = {}, end - days * 86400
            while t < end:
                t2 = min(end, t + 300 * 900)
                for attempt in range(5):
                    r = c.get(f"https://api.exchange.coinbase.com/products/{a}-USD/candles",
                              params={"granularity": 900, "start": dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(),
                                      "end": dt.datetime.fromtimestamp(t2, dt.timezone.utc).isoformat()})
                    if r.status_code == 200:
                        break
                    time.sleep(2 ** attempt)
                r.raise_for_status()
                for x in r.json():
                    rows[int(x[0])] = [int(x[0]), float(x[3]), float(x[2]), float(x[1]), float(x[4]), float(x[5])]
                t = t2
                time.sleep(0.15)
            (out_dir / f"{a}_15m.json").write_text(json.dumps([rows[k] for k in sorted(rows)]))
            print(f"{a}: {len(rows)} bars")


def load(scratch: Path, asset: str):
    p = scratch / "dt" / f"{asset}_15m.json"
    return [tuple(r) for r in json.loads(p.read_text())] if p.exists() else []


def summarize(tr: list[dict], key: str = "net_bp", windows: tuple = ("bull", "bear")) -> dict:
    tr = [t for t in tr if t.get(key) is not None]
    if len(tr) < 5:
        return {"n": len(tr)}
    nets = [t[key] for t in tr]
    days = [dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).date().isoformat() for t in tr]
    mid = sorted(days)[len(days) // 2]
    out = {"n": len(tr), "net": statistics.fmean(nets), "gross": statistics.fmean(t["gross_bp"] for t in tr),
           "t": cluster_t(nets, days), "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
           "h1": statistics.fmean([x for x, d in zip(nets, days) if d < mid] or [0.0]),
           "h2": statistics.fmean([x for x, d in zip(nets, days) if d >= mid] or [0.0]),
           "sr": statistics.fmean(nets) / statistics.pstdev(nets) if statistics.pstdev(nets) > 0 else 0.0,
           "exits": {k: sum(1 for t in tr if t["reason"] == k) / len(tr) for k in ("target", "stop", "flat_out_of_hours")}}
    for w in windows:
        x = [t[key] for t in tr if t["window"] == w]
        out[w] = (len(x), statistics.fmean(x) if x else None)
    out["per_day"] = len(tr) / max(1, len(set(days)))
    return out


def run(scratch: Path) -> dict:
    cells = {}
    combos = {}
    for asset in ASSETS:
        b15 = load(scratch, asset)
        if not b15:
            continue
        by_ts = {int(b[0]): b for b in b15}
        for fname, sec in FRAMES:
            bars = b15 if sec == 900 else resample(b15, sec)
            for v in VARIANTS:
                tr = backtest(bars, v, asset)
                for t in tr:
                    t.update({f"i_{k}": x for k, x in score(t, by_ts).items()})
                for ins in INSTRUMENTS:
                    k = f"i_{ins}"
                    cells[(v, fname, asset, ins)] = {"summary": summarize(tr, k),
                                                     "returns": [t[k] / 1e4 for t in tr if t.get(k) is not None]}
                combos[(v, fname, asset)] = tr
    srs = [c["summary"]["sr"] for c in cells.values() if c["summary"].get("n", 0) >= 5]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    n_trials = max(1, len(cells))
    for c in cells.values():
        r = c.pop("returns")
        c["summary"]["dsr"] = dsr(r, n_trials, var_sr) if len(r) >= 20 else None
    cands, by_variant = [], {}
    for (v, f, a, ins), c in cells.items():
        s = c["summary"]
        if ins == "perp":
            by_variant.setdefault(v, []).append(s.get("net", 0.0))
        if (s.get("n", 0) >= 200 and s["net"] >= 5 and s["t"] >= 2.5 and s["h1"] > 0 and s["h2"] > 0
                and (s["dsr"] or 0) >= 0.95):
            cands.append(f"{v} {f} {a} {ins}")
    killed = [v for v, nets in by_variant.items() if nets and all(x < 0 for x in nets)]
    # the combination: per cell, the best instrument for longs and for shorts, chosen in sample (a selection, reported only)
    best = {}
    for (v, f, a), tr in combos.items():
        pick = {}
        for side in (1, -1):
            x = [t for t in tr if t["side"] == side]
            opts = {ins: statistics.fmean([t[f"i_{ins}"] for t in x if t.get(f"i_{ins}") is not None])
                    for ins in INSTRUMENTS if sum(1 for t in x if t.get(f"i_{ins}") is not None) >= 20}
            if opts:
                k = max(opts, key=opts.get)
                pick[side] = (k, len(x), opts[k])
        best[f"{v}|{f}|{a}"] = pick
    return {"cells": {f"{v}|{f}|{a}|{i}": c["summary"] for (v, f, a, i), c in cells.items()}, "candidates": cands,
            "killed_variants": killed, "trials": n_trials, "best_combo": best}


def render(res: dict) -> str:
    o = ["day trading bot, time-block scalper, Coinbase 15m candles (30m resampled); round trips: perps "
         + ", ".join(f"{a} {cost_bp(a):.1f}" for a in ASSETS) + " bp; spot (longs only) "
         + ", ".join(f"{a} {spot_cost_bp(a):.1f}" for a in ASSETS) + " bp; binaries bought at 0.51 + fee (per dollar staked)"]
    o.append(f"  {'cell':16s} {'trades':>6s} {'/day':>5s} {'gross':>7s} {'net bp':>7s} {'t':>5s} {'win':>4s} {'halves':>13s} {'DSR':>5s}  bull window / bear window (n, net)   exits tgt/stop/flat")
    for k, s in res["cells"].items():
        v, f, a, ins = k.split("|")
        a = f"{a:5s}{ins:6s}"
        if s.get("n", 0) < 5:
            o.append(f"  {v} {f} {a} n {s.get('n', 0)}")
            continue
        bu, be = s["bull"], s["bear"]
        ex = s["exits"]
        o.append(f"  {v} {f} {a} {s['n']:6d} {s['per_day']:5.2f} {s['gross']:+7.1f} {s['net']:+7.1f} {s['t']:+5.1f} {s['hit']:4.0%} "
                 f"{s['h1']:+6.1f}/{s['h2']:+6.1f} {s['dsr'] if s['dsr'] is not None else 0:5.2f}  "
                 f"{bu[0]} {bu[1] if bu[1] is not None else 0:+.1f} / {be[0]} {be[1] if be[1] is not None else 0:+.1f}   "
                 f"{ex['target']:.0%}/{ex['stop']:.0%}/{ex['flat_out_of_hours']:.0%}")
    o.append("best instrument per cell, chosen in sample (a selection, not a test): longs / shorts")
    for k, pick in res.get("best_combo", {}).items():
        o.append("  " + k.replace("|", " ") + ": " + " / ".join(
            f"{pick[s][0]} n {pick[s][1]} {pick[s][2]:+.1f} bp" if s in pick else "-" for s in (1, -1)))
    o.append(f"verdict: candidates {res['candidates'] or 'none'}; variants killed (negative on every cell) {res['killed_variants'] or 'none'}; {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--fetch", action="store_true", help="pull the candles first")
    a = ap.parse_args(argv)
    if a.fetch:
        fetch(a.scratch)
    res = run(a.scratch)
    print(render(res))
    (a.scratch / "daytrade_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
