"""`tsmom-kalshi-macro-perps`: time-series momentum on the instruments
Kalshi lists as perps (indices, metals, oil), on ten years of the ETFs
that stand in for them.

Rule (registered): at each month end, go long an instrument whose
trailing 12-month return is positive and short one whose is negative,
1/8 of the book each, hold a month. Costs: 8 bp a round trip on every
sign flip (Kalshi 4 bp a side) and a carry drag of 5% a year on the
whole book (perps funding, ETF expense) as the registered case.
Sensitivities, each a counted trial: lookbacks 1, 3, 6 months and the
long-only version.

    python -m cryptobot.tsmom_study --dir tsmom [--carry 0.05] [--cost-bp 8]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path
from typing import Optional

from . import stats as S

SYMBOLS = ("GLD", "SLV", "CPER", "PPLT", "PALL", "USO", "SPY", "QQQ")
LOOKBACKS = (12, 1, 3, 6)
ROUND_TRIP_BP = 8.0
CARRY = 0.05


def load(d: Path, symbols=SYMBOLS) -> dict[str, dict[dt.date, float]]:
    out = {}
    for sym in symbols:
        p = Path(d) / f"{sym}.json"
        if p.exists():
            out[sym] = {dt.date.fromisoformat(a): float(b) for a, b in json.loads(p.read_text())}
    return out


def month_ends(closes: dict[dt.date, float]) -> list[tuple[str, float]]:
    """(YYYY-MM, last close of the month), in order."""
    by: dict[str, tuple[dt.date, float]] = {}
    for d, c in closes.items():
        m = d.strftime("%Y-%m")
        if m not in by or d > by[m][0]:
            by[m] = (d, c)
    return [(m, by[m][1]) for m in sorted(by)]


def signals(mends: list[tuple[str, float]], lookback: int) -> dict[str, int]:
    """Sign of the trailing `lookback`-month return at each month end."""
    out = {}
    for i in range(lookback, len(mends)):
        r = mends[i][1] / mends[i - lookback][1] - 1.0
        out[mends[i][0]] = 1 if r > 0 else -1 if r < 0 else 0
    return out


def strategy(data: dict[str, dict], lookback: int, long_only: bool, cost_bp: float = ROUND_TRIP_BP,
             carry: float = CARRY) -> list[tuple[str, float]]:
    """Monthly net returns of the pooled book, 1/N per instrument."""
    series = {sym: month_ends(c) for sym, c in data.items()}
    sigs = {sym: signals(s, lookback) for sym, s in series.items()}
    months = sorted(set.intersection(*[set(m for m, _ in s) for s in series.values()]))
    n = len(data)
    out = []
    prev_pos = {sym: 0 for sym in data}
    for i in range(1, len(months)):
        m0, m1 = months[i - 1], months[i]
        total = 0.0
        ready = True
        for sym, s in series.items():
            px = dict(s)
            sig = sigs[sym].get(m0)
            if sig is None:
                ready = False
                break
            pos = max(sig, 0) if long_only else sig
            ret = px[m1] / px[m0] - 1.0
            flip = abs(pos - prev_pos[sym])            # 0, 1 or 2 units of trading
            total += (pos * ret - flip * cost_bp / 1e4 - abs(pos) * carry / 12.0) / n
            prev_pos[sym] = pos
        if ready:
            out.append((m1, total))
    return out


def summarize(ms: list[tuple[str, float]]) -> dict:
    xs = [v for _, v in ms]
    if len(xs) < 3:
        return {"months": len(xs)}
    sd = statistics.pstdev(xs)
    cum, peak, mdd = 1.0, 1.0, 0.0
    for v in xs:
        cum *= 1 + v
        peak = max(peak, cum)
        mdd = min(mdd, cum / peak - 1)
    by_year: dict[int, float] = {}
    for m, v in ms:
        by_year[int(m[:4])] = (1 + by_year.get(int(m[:4]), 0.0)) * (1 + v) - 1
    full = {y: v for y, v in by_year.items() if sum(1 for m, _ in ms if m.startswith(str(y))) >= 12}
    return {"months": len(xs), "mean_month": statistics.fmean(xs), "annual": statistics.fmean(xs) * 12,
            "sharpe": statistics.fmean(xs) / sd * math.sqrt(12) if sd > 0 else 0.0,
            "psr": S.psr(xs), "max_drawdown": mdd, "total": cum - 1, "by_year": by_year,
            "full_years": len(full), "positive_full_years": sum(1 for v in full.values() if v > 0), "monthly": xs}


def run(data: dict[str, dict], cost_bp: float = ROUND_TRIP_BP, carry: float = CARRY) -> dict:
    out = {"instruments": sorted(data), "variants": {}, "cost_bp": cost_bp, "carry": carry}
    for long_only in (False, True):
        for k in LOOKBACKS:
            name = f"{'long-only' if long_only else 'long-short'}-{k}m"
            out["variants"][name] = summarize(strategy(data, k, long_only, cost_bp, carry))
    out["trials"] = len(out["variants"])
    srs = [v["sharpe"] for v in out["variants"].values() if v.get("months")]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    for v in out["variants"].values():
        if v.get("months"):
            v["dsr"] = S.dsr(v["monthly"], out["trials"], var_sr)
    # per instrument, registered variant
    out["per_instrument"] = {}
    for sym in data:
        one = strategy({sym: data[sym]}, 12, False, cost_bp, carry)
        s = summarize(one)
        bh = summarize([(m, v) for m, v in _buy_and_hold(data[sym])])
        out["per_instrument"][sym] = {"annual": s.get("annual"), "sharpe": s.get("sharpe"),
                                      "buy_hold_annual": bh.get("annual"), "buy_hold_sharpe": bh.get("sharpe")}
    out["no_carry"] = summarize(strategy(data, 12, False, cost_bp, 0.0))
    out["verdict"] = passes(out["variants"]["long-short-12m"])
    return out


def _buy_and_hold(closes: dict[dt.date, float]) -> list[tuple[str, float]]:
    me = month_ends(closes)
    return [(me[i][0], me[i][1] / me[i - 1][1] - 1.0) for i in range(1, len(me))]


def passes(s: dict) -> tuple[str, str]:
    """Written before running: alive if net Sharpe >= 0.5, PSR >= 0.95, DSR
    >= 0.95 at the trial count and positive in at least 6 of the 9 full
    years; killed if net at or below zero; otherwise inconclusive."""
    if not s.get("months"):
        return "inconclusive", "no months"
    if s["mean_month"] <= 0:
        return "killed", f"net {s['annual']*100:+.1f}% a year"
    if s["sharpe"] >= 0.5 and s["psr"] >= 0.95 and s.get("dsr", 0.0) >= 0.95 and s["positive_full_years"] >= 6:
        return "alive", "clears the bar"
    return "inconclusive", (f"Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}, DSR {s.get('dsr', 0):.2f}, "
                            f"{s['positive_full_years']} of {s['full_years']} full years positive")


def render(res: dict) -> str:
    o = [f"time-series momentum on {', '.join(res['instruments'])}: {res['cost_bp']:.0f} bp a round trip, {res['carry']*100:.0f}%/yr carry drag"]

    def line(s):
        if not s.get("months"):
            return "no data"
        yrs = " ".join(f"{y}:{v*100:+.0f}" for y, v in sorted(s["by_year"].items()))
        return (f"{s['months']:3d} months: {s['annual']*100:+5.1f}%/yr, Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}"
                + (f", DSR {s['dsr']:.2f}" if "dsr" in s else "") + f", max DD {s['max_drawdown']*100:+.0f}%, "
                f"{s['positive_full_years']}/{s['full_years']} full years | {yrs}")
    for name, s in res["variants"].items():
        o.append(f"  {name:16s} {line(s)}" + ("   <- registered" if name == "long-short-12m" else ""))
    o.append(f"  registered, no carry drag: {line(res['no_carry'])}")
    o.append("  per instrument, registered rule vs buy-and-hold (annual, Sharpe):")
    for sym, v in res["per_instrument"].items():
        o.append(f"    {sym:5s} rule {v['annual']*100:+6.1f}% ({v['sharpe']:+.2f})   hold {v['buy_hold_annual']*100:+6.1f}% ({v['buy_hold_sharpe']:+.2f})")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path("tsmom"))
    ap.add_argument("--cost-bp", type=float, default=ROUND_TRIP_BP)
    ap.add_argument("--carry", type=float, default=CARRY)
    a = ap.parse_args(argv)
    data = load(a.dir)
    if len(data) < 2:
        print(f"no closes in {a.dir} (need <SYM>.json files)")
        return 1
    print(render(run(data, a.cost_bp, a.carry)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
