"""Multi-year perp study: long AND short, by year, at exchange friction.

Every study so far ran on DEX candles over at most a year, long-only, at
~1.2% round-trip friction. Three things were left open: whether the edge
looks different at exchange fees (~0.2% round trip), whether the short
side carries the edge the long side lacks, and whether anything is
repeatable ACROSS market regimes rather than within one.

Hyperliquid's public API supplies daily perp candles back to 2023 for the
same memecoins, plus funding history. This module runs, per side:

  by year     unconditional barrier hit rate and net return, so a result
              has to hold in the 2024 mania and the 2025-26 collapse both
  features    the same in-sample / out-of-sample selection test as
              `cryptobot.research`, on daily-scale features
  funding     the carry a short pays or receives, averaged per year

Costs: taker fee both ways plus a slippage allowance, plus funding for
the expected holding period (paid by longs when positive, received by
shorts). Barrier outcomes use the same conservative convention as the
rest of the project: a candle touching both barriers is the loss.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import math
import pickle
import statistics
from pathlib import Path

from cryptobot.research import (Barrier, candidate_rules, hit_rate, validate,
                                render_validate)
from cryptobot.data.hyperliquid import TAKER_FEE

logger = logging.getLogger(__name__)

WARMUP_DAYS = 30
SLIPPAGE = 0.0005          # per side, for liquid perps
DAILY_FEATURES = ("move_1d", "move_3d", "move_7d", "move_30d",
                  "vol_surge_7d", "rvol_7d", "drawdown_30d")


def _pct(a, b):
    return (a / b - 1.0) if b > 0 else 0.0


def daily_features(closes, vols, i) -> dict:
    c = closes[i]
    rets = [math.log(closes[j] / closes[j - 1]) for j in range(i - 6, i + 1)
            if j > 0 and closes[j] > 0 and closes[j - 1] > 0]
    v7 = sum(vols[i - 6:i + 1])
    v30 = sum(vols[i - 29:i + 1])
    peak = max(closes[i - 29:i + 1])
    return {
        "move_1d": _pct(c, closes[i - 1]),
        "move_3d": _pct(c, closes[i - 3]),
        "move_7d": _pct(c, closes[i - 7]),
        "move_30d": _pct(c, closes[i - 30]),
        "vol_surge_7d": (v7 / (v30 * 7 / 30)) if v30 > 0 else 0.0,
        "rvol_7d": statistics.pstdev(rets) if len(rets) > 2 else 0.0,
        "drawdown_30d": _pct(c, peak),
    }


def outcome(highs, lows, closes, i, entry, bar: Barrier, horizon: int,
            side: str) -> tuple[int, float]:
    """(win, realized return) for one trade on `side` from candle i.

    Target reached first: win, +target. Stop reached first: loss, -stop.
    Neither within the horizon: not a win, and the realized return is the
    plain move to the horizon close — NOT a stop-loss. Scoring a timeout
    as a full stop overstates losses badly on daily candles with wide
    barriers, where most trades time out.
    """
    sign = 1.0 if side == "long" else -1.0
    win_px = entry * (1 + sign * bar.target)
    stop_px = entry * (1 - sign * bar.stop)
    last = min(i + horizon, len(closes) - 1)
    for j in range(i + 1, last + 1):
        stop_hit = lows[j] <= stop_px if side == "long" else highs[j] >= stop_px
        win_hit = highs[j] >= win_px if side == "long" else lows[j] <= win_px
        if stop_hit:                       # conservative: stop before target
            return 0, -bar.stop
        if win_hit:
            return 1, bar.target
    return 0, sign * _pct(closes[last], entry)


def collect(pools, bar: Barrier, horizon: int, side: str) -> list[dict]:
    rows = []
    for _, (meta, candles) in pools.items():
        if len(candles) < WARMUP_DAYS + horizon + 5:
            continue
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        vols = [c.volume_usd for c in candles]
        for i in range(WARMUP_DAYS, len(candles) - horizon):
            r = daily_features(closes, vols, i)
            r["win"], r["pnl"] = outcome(highs, lows, closes, i, closes[i], bar,
                                         horizon, side)
            r["fwd"] = _pct(closes[i + horizon], closes[i])
            r["ts"] = candles[i].ts
            r["symbol"] = meta.symbol
            r["year"] = dt.datetime.utcfromtimestamp(candles[i].ts).year
            rows.append(r)
    rows.sort(key=lambda r: r["ts"])
    return rows


def funding_by_year(funding: dict) -> dict[int, float]:
    """Mean daily funding rate per year across coins (hourly rows × 24)."""
    per_year: dict[int, list[float]] = {}
    for rows in funding.values():
        for f in rows:
            per_year.setdefault(dt.datetime.utcfromtimestamp(f.ts).year, []).append(f.rate)
    return {y: statistics.mean(v) * 24 for y, v in per_year.items() if v}


def round_trip_cost(hold_days: float, daily_funding: float, side: str) -> float:
    """Fees + slippage both ways, plus funding over the hold. Longs pay
    positive funding; shorts receive it."""
    fees = 2 * (TAKER_FEE + SLIPPAGE)
    carry = daily_funding * hold_days
    return fees + (carry if side == "long" else -carry)


def by_year(rows, bar: Barrier, cost_fn) -> list[dict]:
    out = []
    for y in sorted({r["year"] for r in rows}):
        g = [r for r in rows if r["year"] == y]
        p = hit_rate(g)
        stamps = len({r["ts"] for r in g})
        pnl = [r["pnl"] for r in g]
        gross = statistics.mean(pnl)
        # SE of the mean realized return, on timestamps not rows: coins at
        # the same date share the market move.
        se = (statistics.pstdev(pnl) / math.sqrt(max(stamps, 1))) if len(pnl) > 1 else 0.0
        cost = cost_fn(y)
        out.append({"year": y, "n": len(g), "days": stamps, "hit": p, "se": se,
                    "gross": gross, "cost": cost, "net": gross - cost,
                    "fwd": statistics.mean(r["fwd"] for r in g),
                    "coins": len({r["symbol"] for r in g})})
    return out


def rule_by_year(rows, bar: Barrier, cost_fn, top_k: int = 5,
                 features=DAILY_FEATURES) -> list[dict]:
    """Take the top rules by IN-SAMPLE lift (first half) and show how each
    did in every calendar year of the full data. A rule that only works
    in the years that match the out-of-sample regime is not repeatable;
    one that clears cost in a mania year and a collapse year might be."""
    cut = len(rows) // 2
    in_s = rows[:cut]
    base_in = hit_rate(in_s)
    scored = []
    for name, pred in candidate_rules(in_s, 3, features):
        g = [r for r in in_s if pred(r)]
        if len(g) < 250:
            continue
        scored.append((hit_rate(g) - base_in, name, pred))
    scored.sort(key=lambda t: -t[0])
    out = []
    years = sorted({r["year"] for r in rows})
    for lift, name, pred in scored[:top_k]:
        cells = {}
        for y in years:
            g = [r for r in rows if r["year"] == y and pred(r)]
            base = [r for r in rows if r["year"] == y]
            if len(g) < 30:
                continue
            p = hit_rate(g)
            cells[y] = {"n": len(g), "hit": p, "lift": p - hit_rate(base),
                        "net": statistics.mean(r["pnl"] for r in g) - cost_fn(y)}
        out.append({"rule": name, "lift_in": lift, "years": cells})
    return out


def render_rules(side: str, table: list[dict]) -> str:
    years = sorted({y for t in table for y in t["years"]})
    out = [f"== {side.upper()} top in-sample rules, by calendar year (net per trade) ==",
           f"{'rule':<40s} " + " ".join(f"{y:>8d}" for y in years) + "   yrs+"]
    for t in table:
        cells = []
        for y in years:
            c = t["years"].get(y)
            cells.append(f"{100 * c['net']:>+7.2f}%" if c else f"{'-':>8s}")
        pos = sum(c["net"] > 0 for c in t["years"].values())
        out.append(f"{t['rule']:<40s} " + " ".join(cells) + f"   {pos}/{len(t['years'])}")
    return "\n".join(out)


def render_years(side: str, bar: Barrier, table: list[dict]) -> str:
    out = [f"== {side.upper()} {bar} ==",
           f"{'year':>5s} {'coins':>5s} {'days':>5s} {'n':>6s} {'hit':>5s} "
           f"{'gross':>13s} {'cost':>6s} {'net':>7s} {'fwd/hold':>9s}"]
    for r in table:
        out.append(f"{r['year']:>5d} {r['coins']:>5d} {r['days']:>5d} {r['n']:>6d} "
                   f"{100 * r['hit']:>4.1f}% "
                   f"{100 * r['gross']:>+6.2f}%±{100 * r['se']:.2f} {100 * r['cost']:>5.2f}% "
                   f"{100 * r['net']:>+6.2f}% {100 * r['fwd']:>+8.2f}%")
    pos = sum(r["net"] > 0 for r in table)
    out.append(f"net positive in {pos} of {len(table)} years")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--funding", type=Path)
    ap.add_argument("--target", type=float, default=0.10)
    ap.add_argument("--stop", type=float, default=0.05)
    ap.add_argument("--days", type=int, default=7, help="horizon in days")
    ap.add_argument("--validate", action="store_true",
                    help="also run the feature-selection test per side")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pools = pickle.loads(args.cache.read_bytes())
    funding = pickle.loads(args.funding.read_bytes()) if args.funding else {}
    fy = funding_by_year(funding)
    bar = Barrier(args.target, args.stop)
    span = [c.ts for _, cs in pools.values() for c in cs]
    print(f"{len(pools)} coins, {dt.datetime.utcfromtimestamp(min(span)):%Y-%m-%d} .. "
          f"{dt.datetime.utcfromtimestamp(max(span)):%Y-%m-%d}; horizon {args.days}d; "
          f"fees {100 * 2 * (TAKER_FEE + SLIPPAGE):.2f}% round trip + funding")
    if fy:
        print("mean daily funding by year: " +
              ", ".join(f"{y}: {100 * v:+.3f}%" for y, v in sorted(fy.items())))
    print()
    for side in ("long", "short"):
        rows = collect(pools, bar, args.days, side)
        cost_fn = lambda y, s=side: round_trip_cost(args.days / 2, fy.get(y, 0.0), s)
        print(render_years(side, bar, by_year(rows, bar, cost_fn)))
        print()
        if args.validate:
            mean_cost = round_trip_cost(args.days / 2, statistics.mean(fy.values()) if fy else 0.0, side)
            print(render_validate(validate(rows, bar, mean_cost, features=DAILY_FEATURES)))
            print()
            print(render_rules(side, rule_by_year(rows, bar, cost_fn)))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
