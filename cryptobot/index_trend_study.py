"""Pre-registered test `index-trend-voltarget`: a long/flat, vol-targeted
trend rule on a US equity index, as a candidate stock sleeve.

Rule (fixed, no fitting): each day the position is the share of the
{50, 100, 200}-day moving averages the close sits above, scaled by
min(1, 12% / realised 20-day vol), applied from the next close; costs
8 bp per unit of position change. Reported by era against buy-and-hold.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
from pathlib import Path

from .fedliq_study import read_fred

LOOKBACKS = (50, 100, 200)
VOL_TARGET = 0.12
COST = 0.0008
ERAS = (("2009-2014", 2009, 2014), ("2015-2019", 2015, 2019), ("2020-2021", 2020, 2021), ("2022-2026", 2022, 2026))


def simulate(closes: list[tuple[dt.date, float]]) -> list[dict]:
    days = [d for d, _ in closes]
    px = [p for _, p in closes]
    rows = []
    pos_prev = 0.0
    for i in range(1, len(px)):
        r = px[i] / px[i - 1] - 1.0
        # signal known at close i-1, position held over day i
        j = i - 1
        if j < max(LOOKBACKS) or j < 21:
            rows.append({"date": days[i], "ret": r, "rule": 0.0, "pos": 0.0, "cost": 0.0})
            continue
        votes = sum(1 for k in LOOKBACKS if px[j] > statistics.mean(px[j - k + 1:j + 1])) / len(LOOKBACKS)
        rets20 = [px[t] / px[t - 1] - 1.0 for t in range(j - 19, j + 1)]
        vol = statistics.stdev(rets20) * math.sqrt(252) if len(rets20) > 2 else 0.0
        scale = min(1.0, VOL_TARGET / vol) if vol > 0 else 1.0
        pos = votes * scale
        cost = abs(pos - pos_prev) * COST
        rows.append({"date": days[i], "ret": r, "rule": pos * r - cost, "pos": pos, "cost": cost})
        pos_prev = pos
    return rows


def metrics(rets: list[float]) -> dict:
    if len(rets) < 20:
        return {"n": len(rets)}
    m, sd = statistics.mean(rets), statistics.stdev(rets)
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return {"n": len(rets), "ann_ret": (eq ** (252 / len(rets)) - 1.0), "ann_vol": sd * math.sqrt(252),
            "sharpe": (m / sd * math.sqrt(252)) if sd else 0.0, "max_dd": mdd, "total": eq - 1.0}


def by_era(rows: list[dict]) -> list[dict]:
    out = []
    for name, a, b in ERAS:
        g = [r for r in rows if a <= r["date"].year <= b]
        if len(g) < 60:
            continue
        rule, hold = metrics([r["rule"] for r in g]), metrics([r["ret"] for r in g])
        out.append({"era": name, "rule": rule, "hold": hold,
                    "time_in": statistics.mean(r["pos"] for r in g),
                    "costs": sum(r["cost"] for r in g)})
    return out


def render(index: str, eras: list[dict]) -> str:
    out = [f"{index}: era        rule ret/yr  vol   Sharpe  maxDD   | hold ret/yr  vol   Sharpe  maxDD   | in-market  costs"]
    better, dd_cut = 0, 0
    for e in eras:
        r, h = e["rule"], e["hold"]
        better += r["sharpe"] >= h["sharpe"]
        dd_cut += abs(r["max_dd"]) <= 0.7 * abs(h["max_dd"])
        out.append(f"   {e['era']}  {100 * r['ann_ret']:+6.1f}%  {100 * r['ann_vol']:4.1f}%  {r['sharpe']:+5.2f}  {100 * r['max_dd']:6.1f}%  | "
                   f"{100 * h['ann_ret']:+6.1f}%  {100 * h['ann_vol']:4.1f}%  {h['sharpe']:+5.2f}  {100 * h['max_dd']:6.1f}%  |   {100 * e['time_in']:3.0f}%     {100 * e['costs']:.1f}%")
    out.append(f"   Sharpe >= buy-and-hold in {better}/{len(eras)} eras; drawdown cut by >= 30% in {dd_cut}/{len(eras)}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, required=True)
    args = ap.parse_args()
    for index in ("SP500", "NASDAQCOM"):
        series = read_fred(args.dir / f"{index}.csv")
        closes = sorted(series.items())
        closes = [(d, p) for d, p in closes if d.year >= 2008]
        print(render(index, by_era(simulate(closes))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
