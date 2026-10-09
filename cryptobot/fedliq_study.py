"""Pre-registered test `fed-liquidity-equities`: does a Fed money
injection predict US equity returns?

Net liquidity = Fed total assets (WALCL) - Treasury General Account
(WTREGEN) - overnight reverse repo (RRPONTSYD, Wednesday value), weekly
on the H.4.1 Wednesday. The signal is known at Thursday's release and is
applied from the following Friday close: next-week, 4-week and 13-week
S&P 500 returns conditional on the sign and decile of the 1-week and
4-week change in net liquidity; by era; and a long-only rule (hold the
index only after a rise) against buy-and-hold, with the week of the
operator's question as the worked example.

Data: FRED CSVs in --dir (WALCL, WTREGEN, RRPONTSYD, WRESBAL, DFF, SP500)
and, when present, Stooq spx.csv for history before FRED's 10-year S&P
window.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics
from pathlib import Path
from typing import Optional

from .stats import psr

WEEK = 7


def read_fred(path: Path) -> dict[dt.date, float]:
    out = {}
    with path.open() as f:
        for row in csv.reader(f):
            if len(row) < 2 or row[0] in ("observation_date", "DATE"):
                continue
            try:
                out[dt.date.fromisoformat(row[0])] = float(row[1])
            except ValueError:
                continue
    return out


def read_stooq(path: Path) -> dict[dt.date, float]:
    out = {}
    if not path.exists():
        return out
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                out[dt.date.fromisoformat(row["Date"])] = float(row["Close"])
            except (KeyError, ValueError):
                continue
    return out


def on_or_before(series: dict[dt.date, float], day: dt.date, max_back: int = 7) -> Optional[float]:
    for k in range(max_back + 1):
        v = series.get(day - dt.timedelta(days=k))
        if v is not None:
            return v
    return None


def on_or_after(series: dict[dt.date, float], day: dt.date, max_fwd: int = 7) -> Optional[tuple[dt.date, float]]:
    for k in range(max_fwd + 1):
        d = day + dt.timedelta(days=k)
        v = series.get(d)
        if v is not None:
            return d, v
    return None


def net_liquidity(d: Path) -> dict[dt.date, float]:
    walcl, tga, rrp = read_fred(d / "WALCL.csv"), read_fred(d / "WTREGEN.csv"), read_fred(d / "RRPONTSYD.csv")
    out = {}
    for day, assets in walcl.items():
        t = tga.get(day)
        r = on_or_before(rrp, day, 3)
        if t is None:
            continue
        out[day] = assets - t - (r or 0.0) * 1000.0          # RRP is in billions; WALCL/TGA in millions
    return out


def index_prices(d: Path, index: str = "SP500") -> dict[dt.date, float]:
    px = read_stooq(d / "spx.csv") if index == "SP500" else {}
    px.update(read_fred(d / f"{index}.csv"))              # FRED where it overlaps
    return px


def build_rows(d: Path, index: str = "SP500") -> list[dict]:
    """One row per H.4.1 Wednesday with the liquidity changes and the
    index returns from the next Friday's close."""
    nl = net_liquidity(d)
    px = index_prices(d, index)
    weds = sorted(nl)
    rows = []
    for i, w in enumerate(weds):
        if i < 4:
            continue
        prev, prev4 = nl.get(weds[i - 1]), nl.get(weds[i - 4])
        if prev is None or prev4 is None or prev <= 0:
            continue
        friday = w + dt.timedelta(days=2)
        p0 = on_or_before(px, friday, 3)
        if p0 is None:
            continue
        fwd = {}
        for weeks in (1, 4, 13):
            hit = on_or_before(px, friday + dt.timedelta(days=7 * weeks), 3)
            if hit is None:
                continue
            fwd[weeks] = hit / p0 - 1.0
        if 1 not in fwd:
            continue
        rows.append({"date": w, "year": w.year, "nl": nl[w], "d1": nl[w] / prev - 1.0, "d4": nl[w] / prev4 - 1.0,
                     "d1_usd": (nl[w] - prev) / 1000.0, **{f"r{k}": v for k, v in fwd.items()}})
    return rows


ERAS = (("2009-2014", 2009, 2014), ("2015-2019", 2015, 2019), ("2020-2021", 2020, 2021), ("2022-2026", 2022, 2026))


def _stats(xs: list[float]) -> dict:
    if len(xs) < 3:
        return {"n": len(xs), "mean": 0.0, "sd": 0.0, "t": 0.0}
    m, sd = statistics.mean(xs), statistics.stdev(xs)
    return {"n": len(xs), "mean": m, "sd": sd, "t": (m / sd * math.sqrt(len(xs))) if sd else 0.0}


def corr(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def conditional(rows: list[dict], key: str = "d1", horizon: str = "r1") -> dict:
    up = [r[horizon] for r in rows if r[key] > 0 and horizon in r]
    dn = [r[horizon] for r in rows if r[key] <= 0 and horizon in r]
    su, sd_ = _stats(up), _stats(dn)
    diff = su["mean"] - sd_["mean"]
    pooled = math.sqrt((su["sd"] ** 2 / max(su["n"], 1)) + (sd_["sd"] ** 2 / max(sd_["n"], 1))) if su["n"] > 2 and sd_["n"] > 2 else 0.0
    return {"up": su, "down": sd_, "diff": diff, "t_diff": (diff / pooled) if pooled else 0.0,
            "corr": corr([r[key] for r in rows if horizon in r], [r[horizon] for r in rows if horizon in r])}


def deciles(rows: list[dict], key: str = "d1", horizon: str = "r1") -> list[tuple]:
    xs = sorted((r for r in rows if horizon in r), key=lambda r: r[key])
    n = len(xs)
    out = []
    for q in range(5):
        g = xs[q * n // 5:(q + 1) * n // 5]
        if g:
            out.append((q + 1, len(g), statistics.mean(r[key] for r in g), statistics.mean(r[horizon] for r in g)))
    return out


def long_only_rule(rows: list[dict], key: str = "d1", cost: float = 0.0002) -> dict:
    """Hold the index for the next week only after a rise; by year."""
    by_year: dict[int, dict] = {}
    for r in rows:
        y = r["year"]
        g = by_year.setdefault(y, {"rule": [], "hold": []})
        g["hold"].append(r["r1"])
        g["rule"].append(r["r1"] - cost if r[key] > 0 else 0.0)
    return {y: {"rule": _stats(g["rule"]), "hold": _stats(g["hold"]),
                "rule_sum": sum(g["rule"]), "hold_sum": sum(g["hold"]),
                "weeks_in": sum(1 for r in rows if r["year"] == y and r[key] > 0)}
            for y, g in sorted(by_year.items())}


def sharpe(xs: list[float]) -> float:
    s = _stats(xs)
    return s["mean"] / s["sd"] * math.sqrt(52) if s["sd"] else 0.0


def render(rows: list[dict]) -> str:
    out = [f"{len(rows)} H.4.1 weeks {rows[0]['date']}..{rows[-1]['date']}"]
    for name, a, b in ERAS:
        g = [r for r in rows if a <= r["year"] <= b]
        if len(g) < 10:
            out.append(f"{name}: {len(g)} weeks (not enough data)")
            continue
        c1 = conditional(g, "d1", "r1")
        c4 = conditional(g, "d4", "r4")
        rule = [r["r1"] - 0.0002 if r["d1"] > 0 else 0.0 for r in g]
        hold = [r["r1"] for r in g]
        out.append(f"{name}: n={len(g)}  1w change -> next week: up {100 * c1['up']['mean']:+.2f}% (n={c1['up']['n']}) "
                   f"vs down {100 * c1['down']['mean']:+.2f}% (n={c1['down']['n']}), diff {100 * c1['diff']:+.2f}% t={c1['t_diff']:+.2f}, "
                   f"corr {c1['corr']:+.2f} | 4w change -> next 4w: diff {100 * c4['diff']:+.2f}% t={c4['t_diff']:+.2f} corr {c4['corr']:+.2f} "
                   f"| long-only-after-rise Sharpe {sharpe(rule):+.2f} vs buy&hold {sharpe(hold):+.2f}")
    out.append("quintiles of the 1-week change (all weeks) -> next-week return:")
    for q, n, dmean, rmean in deciles(rows, "d1", "r1"):
        out.append(f"   Q{q}: n={n:3d} liquidity change {100 * dmean:+.2f}%  next week {100 * rmean:+.2f}%")
    post = [r for r in rows if r["year"] >= 2015]
    c = conditional(post, "d1", "r1")
    out.append(f"2015-{rows[-1]['year']}: diff {100 * c['diff']:+.2f}% t={c['t_diff']:+.2f}; rule weekly PSR(SR>0)="
               f"{psr([r['r1'] - 0.0002 if r['d1'] > 0 else 0.0 for r in post]):.3f} vs hold PSR={psr([r['r1'] for r in post]):.3f}")
    by = long_only_rule(rows)
    out.append("year  weeks-in  rule(sum)  buy&hold(sum)")
    for y, g in by.items():
        if y >= 2015:
            out.append(f"{y}   {g['weeks_in']:3d}/{g['hold']['n']:3d}   {100 * g['rule_sum']:+7.1f}%   {100 * g['hold_sum']:+7.1f}%")
    last = rows[-1]
    out.append(f"latest H.4.1 week {last['date']}: net liquidity ${last['nl'] / 1e6:,.2f}T, 1w change {100 * last['d1']:+.2f}% "
               f"(${last['d1_usd']:+.0f}B), 4w change {100 * last['d4']:+.2f}%; next-week return realised so far {100 * last['r1']:+.2f}%"
               if rows else "")
    return "\n".join(out)


def worked_example(d: Path, asof: dt.date) -> str:
    nl = net_liquidity(d)
    weds = sorted(w for w in nl if w <= asof)
    if len(weds) < 5:
        return "no liquidity data"
    w, p, p4 = weds[-1], weds[-2], weds[-5]
    px = index_prices(d, "SP500")
    hit = on_or_before(px, asof, 5)
    prev = on_or_before(px, asof - dt.timedelta(days=7), 5)
    lines = [f"worked example, week of {asof}: H.4.1 {w}: net liquidity ${nl[w] / 1e6:,.3f}T, "
             f"1w {100 * (nl[w] / nl[p] - 1):+.2f}% (${(nl[w] - nl[p]) / 1000:+.0f}B), 4w {100 * (nl[w] / nl[p4] - 1):+.2f}% "
             f"(${(nl[w] - nl[p4]) / 1000:+.0f}B)"]
    if hit and prev:
        lines.append(f"   S&P 500 {asof - dt.timedelta(days=7)} -> latest close in data: {100 * (hit / prev - 1):+.2f}%")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--asof", default=dt.date.today().isoformat())
    ap.add_argument("--index", default="SP500", help="SP500 (FRED, 10 years) or NASDAQCOM (1971+)")
    args = ap.parse_args()
    rows = build_rows(args.dir, args.index)
    print(f"index: {args.index}")
    print(render(rows))
    print(worked_example(args.dir, dt.date.fromisoformat(args.asof)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
