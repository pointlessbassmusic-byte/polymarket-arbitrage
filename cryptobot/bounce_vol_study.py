"""`bounce-short-vol-scaled`: size the live bounce-short by the range
forecast. Direction is unpredictable; the next days' range is not (it
persists, t 5-33 across every dataset this month). The bounce-short's
barriers are fixed in percent, so a coin in a wide-range spell hits the
+10% stop on noise. Scaling the position by median range / current
range keeps the dollar risk per trade closer to constant.

    python -m cryptobot.bounce_vol_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import math
import pickle
import statistics
from pathlib import Path

from .data.hyperliquid import MEMECOINS
from .perp_study import outcome
from .research import Barrier

BAR = Barrier(target=0.20, stop=0.10)
HORIZON = 14
COST = 0.0018
WIN = 20
LIVE = ("DOGE", "kSHIB")


def candles(scratch: Path) -> dict[str, list]:
    d = pickle.load(open(scratch / "hl_all_daily.pkl", "rb"))
    out = {}
    for coin, v in d.items():
        cs = next((x for x in v if isinstance(x, list)), None) if isinstance(v, tuple) else v
        if cs:
            out[coin] = cs
    return out


def trades(cs: list) -> list[dict]:
    closes = [c.close for c in cs]
    highs = [c.high for c in cs]
    lows = [c.low for c in cs]
    opens = [c.open for c in cs]
    one, three, rng = [], [], []
    out = []
    busy_until = -1
    for i in range(1, len(cs)):
        if closes[i - 1] <= 0 or opens[i] <= 0:
            continue
        rng.append((highs[i] - lows[i]) / opens[i])
        if i < 60 or i + 1 >= len(cs):
            if i >= 3 and closes[i - 3] > 0:
                one.append(closes[i] / closes[i - 1] - 1)
                three.append(closes[i] / closes[i - 3] - 1)
            continue
        m1 = closes[i] / closes[i - 1] - 1
        m3 = closes[i] / closes[i - 3] - 1
        o, t = sorted(one), sorted(three)
        signal = m1 >= o[2 * len(o) // 3] and m3 <= t[len(t) // 3]
        one.append(m1)
        three.append(m3)
        if not signal or i <= busy_until:
            continue
        cur = statistics.fmean(rng[-WIN:])
        hist = sorted(statistics.fmean(rng[k - WIN:k]) for k in range(WIN, len(rng) - 1))
        med = hist[len(hist) // 2] if hist else cur
        w = min(2.0, max(0.25, med / cur)) if cur > 0 else 1.0
        win, pnl = outcome(highs, lows, closes, i, closes[i], BAR, HORIZON, "short")
        # holding period for the one-position rule: first barrier touch or the horizon
        end = i + HORIZON
        for j in range(i + 1, min(i + HORIZON, len(cs) - 1) + 1):
            if highs[j] >= closes[i] * (1 + BAR.stop) or lows[j] <= closes[i] * (1 - BAR.target):
                end = j
                break
        busy_until = end
        out.append({"date": dt.datetime.fromtimestamp(cs[i].ts, dt.timezone.utc).date().isoformat(),
                    "ret": pnl - COST, "w": w})
    return out


def stats(rows: list[dict], weighted: bool) -> dict:
    if len(rows) < 10:
        return {"n": len(rows)}
    rs = sorted(rows, key=lambda r: r["date"])
    xs = [r["ret"] * (r["w"] if weighted else 1.0) for r in rs]
    eq = 0.0; peak = 0.0; dd = 0.0
    for x in xs:
        eq += x
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    mid = rs[len(rs) // 2]["date"]
    def sh(v):
        return statistics.fmean(v) / statistics.pstdev(v) if len(v) > 2 and statistics.pstdev(v) > 0 else 0.0
    h1 = [x for x, r in zip(xs, rs) if r["date"] < mid]
    h2 = [x for x, r in zip(xs, rs) if r["date"] >= mid]
    scale = statistics.fmean(r["w"] for r in rs) if weighted else 1.0
    return {"n": len(xs), "mean": statistics.fmean(xs) / scale, "sharpe": sh(xs), "h1": sh(h1), "h2": sh(h2),
            "max_dd": dd / scale, "worst": min(xs) / scale}


def run(scratch: Path) -> dict:
    cs = candles(scratch)
    res = {}
    for label, coins in (("memecoins", MEMECOINS), ("live DOGE+kSHIB", LIVE)):
        rows = [t for c in coins if c in cs for t in trades(cs[c])]
        res[label] = {"equal": stats(rows, False), "vol_scaled": stats(rows, True),
                      "weight_mean": statistics.fmean(r["w"] for r in rows) if rows else None}
    m, l = res["memecoins"], res["live DOGE+kSHIB"]
    ok = (m["equal"].get("n", 0) >= 10 and m["vol_scaled"]["h1"] - m["equal"]["h1"] >= 0.05 and m["vol_scaled"]["h2"] - m["equal"]["h2"] >= 0.05
          and l["vol_scaled"].get("sharpe", 0) >= l["equal"].get("sharpe", 0) and m["vol_scaled"]["max_dd"] >= m["equal"]["max_dd"])
    res["verdict"] = "adopt" if ok else "killed"
    return res


def render(res: dict) -> str:
    o = ["bounce-short, equal size vs sized by median range / current 20-day range (0.25-2x); -20% target, +10% stop, 14 days, 18 bp"]
    for label in ("memecoins", "live DOGE+kSHIB"):
        r = res[label]
        for k in ("equal", "vol_scaled"):
            s = r[k]
            if s.get("n", 0) < 10:
                o.append(f"  {label:16s} {k:10s} n {s.get('n', 0)}")
                continue
            o.append(f"  {label:16s} {k:10s} n {s['n']:4d}  mean {s['mean']:+.2%}  Sharpe/trade {s['sharpe']:+.3f}  halves {s['h1']:+.3f}/{s['h2']:+.3f}  "
                     f"max drawdown {s['max_dd']:+.0%} of one unit-trade  worst {s['worst']:+.1%}")
        o.append(f"  {label:16s} mean weight {r['weight_mean']:.2f}")
    o.append(f"verdict: {res['verdict']}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    res = run(a.scratch)
    print(render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
