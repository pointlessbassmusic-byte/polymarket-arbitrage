"""Funding-carry study: short the perp, long the spot, collect funding.

The position is market-neutral, so its return is funding received minus
fees paid to enter and exit, plus whatever the perp-spot basis does over
the hold (small on liquid coins, not zero, and not in this data — see
the README caveat). The question is purely one of selection and timing:
which coins, when to enter, when to leave.

Rule family:
    rank coins by trailing `lookback`-day mean funding
    hold the top N whose trailing rate exceeds `enter_min` per day
    exit a coin when its trailing `exit_lookback`-day rate falls below
    `exit_min`, or it drops below rank 2N

Every combination is scored per calendar year on realised hourly
funding, charging a round trip (perp taker both ways + spot taker both
ways) for each entry. Capital is deployed equally across held slots;
an empty slot earns nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import pickle
import statistics
from dataclasses import dataclass
from pathlib import Path

from cryptobot.data.hyperliquid import TAKER_FEE

KRAKEN_TAKER = 0.0026
SPOT_SLIPPAGE = 0.0005
ROUND_TRIP = 2 * (TAKER_FEE + SPOT_SLIPPAGE) + 2 * (KRAKEN_TAKER + SPOT_SLIPPAGE)


@dataclass(frozen=True)
class CarryRule:
    top_n: int = 3
    lookback: int = 7           # days of funding to rank on
    enter_min: float = 0.0003   # daily rate; 0.03%/day ~ 11%/yr
    exit_lookback: int = 3
    exit_min: float = 0.0

    def __str__(self) -> str:
        return (f"top{self.top_n} lb{self.lookback}d enter>{100 * self.enter_min:.3f}%/d "
                f"exit<{100 * self.exit_min:.3f}%/d({self.exit_lookback}d)")


def daily_funding(funding: dict) -> dict[str, dict[int, float]]:
    """{coin: {day_ts: sum of that day's hourly rates}}."""
    out: dict[str, dict[int, float]] = {}
    for coin, rows in funding.items():
        d = out.setdefault(coin, {})
        for r in rows:
            day = int(r.ts // 86400) * 86400
            d[day] = d.get(day, 0.0) + r.rate
    return out


def trailing(series: dict[int, float], day: int, n: int) -> float | None:
    vals = [series.get(day - k * 86400) for k in range(1, n + 1)]
    vals = [v for v in vals if v is not None]
    return statistics.mean(vals) if len(vals) >= max(1, n // 2) else None


def simulate(daily: dict[str, dict[int, float]], rule: CarryRule,
             start: int, end: int, round_trip: float = ROUND_TRIP) -> dict:
    """Walk day by day. Returns per-year net yield on capital and turnover."""
    held: dict[str, int] = {}                     # coin -> entry day
    per_year: dict[int, dict] = {}
    day = start
    while day < end:
        y = dt.datetime.utcfromtimestamp(day).year
        yr = per_year.setdefault(y, {"days": 0, "funding": 0.0, "fees": 0.0,
                                      "entries": 0, "slot_days": 0})
        # rank on yesterday's trailing window: today's funding is unknown
        ranked = sorted(((trailing(s, day, rule.lookback) or -1.0, c)
                         for c, s in daily.items()), reverse=True)
        eligible = [c for r, c in ranked if r > rule.enter_min]
        top = eligible[:rule.top_n]
        rank_of = {c: i for i, (_, c) in enumerate(ranked)}
        # exits
        for c in list(held):
            recent = trailing(daily[c], day, rule.exit_lookback)
            if (recent is not None and recent < rule.exit_min) or rank_of.get(c, 999) >= 2 * rule.top_n:
                del held[c]
        # entries into free slots
        for c in top:
            if len(held) >= rule.top_n:
                break
            if c not in held:
                held[c] = day
                yr["entries"] += 1
                yr["fees"] += round_trip / rule.top_n     # per-slot capital share
        # accrue today's realised funding on held slots
        for c in held:
            f = daily[c].get(day)
            if f is not None:
                yr["funding"] += f / rule.top_n
        yr["slot_days"] += len(held)
        yr["days"] += 1
        day += 86400
    out = {}
    for y, r in per_year.items():
        net = r["funding"] - r["fees"]
        out[y] = {"days": r["days"], "gross": r["funding"], "fees": r["fees"], "net": net,
                  "annualised": net * 365 / r["days"] if r["days"] else 0.0,
                  "entries": r["entries"],
                  "utilisation": r["slot_days"] / (r["days"] * rule.top_n) if r["days"] else 0.0}
    return out


def render(rule: CarryRule, res: dict) -> str:
    out = [f"== {rule} ==",
           f"{'year':>5s} {'days':>5s} {'gross':>7s} {'fees':>6s} {'net':>7s} {'annual':>7s} "
           f"{'entries':>7s} {'util':>5s}"]
    for y, r in sorted(res.items()):
        out.append(f"{y:>5d} {r['days']:>5d} {100 * r['gross']:>6.1f}% {100 * r['fees']:>5.1f}% "
                   f"{100 * r['net']:>+6.1f}% {100 * r['annualised']:>+6.1f}% {r['entries']:>7d} "
                   f"{100 * r['utilisation']:>4.0f}%")
    pos = sum(r["net"] > 0 for r in res.values())
    out.append(f"net positive {pos}/{len(res)} years")
    return "\n".join(out)


def sweep(daily, start, end):
    grid = itertools.product((1, 3, 5), (3, 7, 14), (0.0001, 0.0003, 0.0006), (0.0, 0.0001))
    rows = []
    for n, lb, em, xm in grid:
        rule = CarryRule(top_n=n, lookback=lb, enter_min=em, exit_min=xm)
        res = simulate(daily, rule, start, end)
        yrs = [r["annualised"] for y, r in sorted(res.items()) if r["days"] > 100]
        rows.append((min(yrs) if yrs else -9, statistics.mean(yrs) if yrs else -9,
                     sum(v > 0 for v in yrs), len(yrs), rule))
    rows.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--funding", type=Path, required=True)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--lookback", type=int, default=7)
    ap.add_argument("--enter-min", type=float, default=0.0003)
    ap.add_argument("--exit-min", type=float, default=0.0)
    args = ap.parse_args()
    funding = pickle.loads(args.funding.read_bytes())
    daily = daily_funding(funding)
    days = sorted({d for s in daily.values() for d in s})
    start, end = days[0] + 15 * 86400, days[-1]
    print(f"{len(daily)} coins, {dt.datetime.utcfromtimestamp(start):%Y-%m-%d} .. "
          f"{dt.datetime.utcfromtimestamp(end):%Y-%m-%d}; round trip {100 * ROUND_TRIP:.2f}% per entry")
    if args.sweep:
        print(f"\n{'worst yr':>9s} {'mean yr':>8s} {'yrs+':>5s}  rule")
        for worst, mean, pos, n, rule in sweep(daily, start, end)[:12]:
            print(f"{100 * worst:>+8.1f}% {100 * mean:>+7.1f}% {pos:>2d}/{n}  {rule}")
        return 0
    rule = CarryRule(args.top, args.lookback, args.enter_min, 3, args.exit_min)
    print(render(rule, simulate(daily, rule, start, end)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
