"""Post-earnings-announcement drift, as pre-registered in `pead-revisit`.

Each calendar month, every announcement with at least `min_estimates`
analyst estimates and a market cap at or under `max_cap` is ranked by
its percentage EPS surprise. The top decile is bought at the open of
the session after the report date and held `hold_days` sessions; the
bottom decile is sold short the same way. Positions are equal-weight
within a cohort; cohorts overlap. Costs: `cost_side` per execution.

The benchmark is the equal-weight return of ALL qualifying announcers
over the same windows, which removes the announcement-period and size
effects and leaves the surprise signal. Monthly spread series feed the
Sharpe and PSR; by-year tables give the walk-forward view (the rule has
no fitted parameters).

    python -m cryptobot.pead_study --state state --max-cap 5e9
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

from . import stats as S
from .pead_collect import read_jsonl


def load_prices(d: Path, symbols: set[str]) -> dict[str, list[dict]]:
    out = {}
    for sym in symbols:
        p = d / f"{sym}.json"
        if p.exists():
            try:
                rows = json.loads(p.read_text())
            except ValueError:
                continue
            if rows:
                out[sym] = rows
    return out


def window_return(rows: list[dict], report_date: str, hold_days: int, cost_side: float) -> dict | None:
    """Open of the first session after `report_date` to the close
    `hold_days` sessions later, net of two executions."""
    dates = [r["date"] for r in rows]
    i = next((k for k, d in enumerate(dates) if d > report_date), None)
    if i is None or i + hold_days - 1 >= len(rows):
        return None
    entry = rows[i]["open"]
    exit_ = rows[i + hold_days - 1]["close"]
    if entry <= 0 or exit_ <= 0:
        return None
    gross = exit_ / entry - 1.0
    return {"entry_date": dates[i], "exit_date": dates[i + hold_days - 1], "gross": gross,
            "net_long": gross - 2 * cost_side, "net_short": -gross - 2 * cost_side}


def cohorts(cal: list[dict], min_estimates: int = 3, max_cap: float | None = None,
            min_names: int = 20) -> dict[str, list[dict]]:
    """Qualifying announcements by calendar month (YYYY-MM), ranked by surprise."""
    by: dict[str, list[dict]] = {}
    for r in cal:
        if r.get("surprise_pct") is None or (r.get("n_est") or 0) < min_estimates:
            continue
        if max_cap is not None and (r.get("market_cap") or float("inf")) > max_cap:
            continue
        by.setdefault(r["date"][:7], []).append(r)
    out = {}
    for m, rows in by.items():
        if len(rows) >= min_names:
            out[m] = sorted(rows, key=lambda r: r["surprise_pct"])
    return out


def coverage(months: dict[str, list[dict]], prices: dict[str, list[dict]]) -> dict:
    """Share of qualifying announcements whose symbol has a price history,
    by year. Nasdaq serves histories for CURRENT listings only, so names
    delisted since (acquisitions, bankruptcies) are missing: the panel has
    survivorship bias, worst for the bottom decile, and the share says how much."""
    by_year: dict[int, list[int]] = {}
    for m, rows in months.items():
        y = int(m[:4])
        b = by_year.setdefault(y, [0, 0])
        for r in rows:
            b[0] += 1
            b[1] += r["symbol"] in prices
    total = sum(v[0] for v in by_year.values())
    have = sum(v[1] for v in by_year.values())
    return {"announcements": total, "with_prices": have, "share": have / total if total else 0.0,
            "by_year": {y: (v[1] / v[0] if v[0] else 0.0) for y, v in sorted(by_year.items())}}


def run(cal: list[dict], prices: dict[str, list[dict]], *, hold_days: int = 20, cost_side: float = 0.0005,
        min_estimates: int = 3, max_cap: float | None = None, decile: float = 0.10) -> dict:
    months = cohorts(cal, min_estimates, max_cap)
    cov = coverage(months, prices)
    monthly = []
    for m in sorted(months):
        rows = months[m]
        n = max(1, int(len(rows) * decile))
        bottom, top = rows[:n], rows[-n:]
        rets = {}
        for label, group in (("top", top), ("bottom", bottom), ("all", rows)):
            vals = []
            for r in group:
                px = prices.get(r["symbol"])
                if not px:
                    continue
                w = window_return(px, r["date"], hold_days, cost_side)
                if w:
                    vals.append(w)
            rets[label] = vals
        if len(rets["top"]) < 3 or len(rets["all"]) < 10:
            continue
        top_net = statistics.fmean(v["net_long"] for v in rets["top"])
        all_net = statistics.fmean(v["net_long"] for v in rets["all"])
        bottom_short = statistics.fmean(v["net_short"] for v in rets["bottom"]) if rets["bottom"] else None
        monthly.append({"month": m, "n_top": len(rets["top"]), "n_all": len(rets["all"]),
                        "top_net": top_net, "all_net": all_net, "long_minus_all": top_net - all_net,
                        "long_short": (top_net + bottom_short) / 2 if bottom_short is not None else None})
    return {"months": monthly, "summary": summarize(monthly), "coverage": cov,
            "params": {"hold_days": hold_days, "cost_side": cost_side, "min_estimates": min_estimates, "max_cap": max_cap}}


def summarize(monthly: list[dict]) -> dict:
    if not monthly:
        return {"months": 0}
    spread = [m["long_minus_all"] for m in monthly]
    ls = [m["long_short"] for m in monthly if m["long_short"] is not None]
    by_year: dict[int, dict] = {}
    for m in monthly:
        y = int(m["month"][:4])
        b = by_year.setdefault(y, {"n": 0, "spread": 0.0, "top": 0.0, "all": 0.0})
        b["n"] += 1
        b["spread"] += m["long_minus_all"]
        b["top"] += m["top_net"]
        b["all"] += m["all_net"]

    def sr(xs):
        sd = statistics.pstdev(xs) if len(xs) > 2 else 0.0
        return statistics.fmean(xs) / sd * math.sqrt(12) if sd > 0 else 0.0
    recent = [m["long_minus_all"] for m in monthly if m["month"] >= "2022-01"]
    return {"months": len(monthly), "mean_spread_month": statistics.fmean(spread),
            "sharpe_spread": sr(spread), "psr_spread": S.psr(spread) if len(spread) > 2 else 0.0,
            "sharpe_long_short": sr(ls) if ls else None, "net_2022_on": sum(recent),
            "positive_years": sum(1 for b in by_year.values() if b["spread"] > 0), "years": len(by_year),
            "by_year": {y: by_year[y] for y in sorted(by_year)}}


def passes(s: dict) -> tuple[str, str]:
    """Written before running: long-only top decile beats the equal-weight
    announcer benchmark by >= 0.3 Sharpe with PSR >= 0.95 over 2015-2026
    and net positive in 2022-2026; otherwise inconclusive."""
    if s.get("months", 0) < 60:
        return "inconclusive", f"only {s.get('months', 0)} months"
    if s["net_2022_on"] <= 0:
        return "inconclusive", "spread not positive in 2022-2026"
    if s["sharpe_spread"] >= 0.3 and s["psr_spread"] >= 0.95:
        return "alive", "clears the bar"
    return "inconclusive", "positive but below the bar"


def render(res: dict) -> str:
    s = res["summary"]
    p = res["params"]
    if not s.get("months"):
        return "pead: no cohort months with prices yet"
    o = [f"PEAD (hold {p['hold_days']}d, {p['cost_side']*1e4:.0f} bp a side, >= {p['min_estimates']} estimates, "
         f"cap <= {p['max_cap'] if p['max_cap'] else 'any'}): {s['months']} months"]
    o.append(f"  top decile minus all announcers: {s['mean_spread_month']*100:+.2f}%/month, Sharpe {s['sharpe_spread']:+.2f}, "
             f"PSR {s['psr_spread']:.2f}; long-short Sharpe {s['sharpe_long_short']:+.2f}" if s["sharpe_long_short"] is not None
             else f"  top decile minus all announcers: {s['mean_spread_month']*100:+.2f}%/month, Sharpe {s['sharpe_spread']:+.2f}, PSR {s['psr_spread']:.2f}")
    o.append("  by year (spread / top / all, summed months): " + " ".join(
        f"{y}:{b['spread']*100:+.1f}/{b['top']*100:+.1f}/{b['all']*100:+.1f}%" for y, b in s["by_year"].items()))
    o.append(f"  2022 on: {s['net_2022_on']*100:+.1f}%; positive years {s['positive_years']}/{s['years']}")
    c = res.get("coverage") or {}
    if c:
        o.append(f"  price coverage {c['share']*100:.0f}% of {c['announcements']} qualifying announcements "
                 f"(current listings only: delisted names are missing, so the bottom decile is understated); by year "
                 + " ".join(f"{y}:{v*100:.0f}%" for y, v in c["by_year"].items()))
    v, why = passes(s)
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--hold-days", type=int, default=20)
    ap.add_argument("--cost-bp", type=float, default=5.0)
    ap.add_argument("--min-estimates", type=int, default=3)
    ap.add_argument("--max-cap", type=float, default=None)
    a = ap.parse_args(argv)
    d = Path(a.state) / "earnings"
    cal = read_jsonl(d / "calendar.jsonl")
    syms = {r["symbol"] for r in cal}
    prices = load_prices(d / "prices", syms)
    res = run(cal, prices, hold_days=a.hold_days, cost_side=a.cost_bp / 1e4,
              min_estimates=a.min_estimates, max_cap=a.max_cap)
    print(f"calendar rows {len(cal)}, symbols with prices {len(prices)} of {len(syms)}")
    print(render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
