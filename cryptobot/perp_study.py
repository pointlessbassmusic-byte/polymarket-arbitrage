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

from cryptobot.research import (Barrier, bucket_of, candidate_rules, hit_rate,
                                quantiles, validate, render_validate)
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
    oos = rows[cut:]
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
        # The clean number: only rows after the selection cut, with a
        # standard error on trading days rather than rows.
        g = [r for r in oos if pred(r)]
        days = len({r["ts"] for r in g})
        pnl = [r["pnl"] for r in g]
        net = (statistics.mean(pnl) - cost_fn(oos[-1]["year"])) if pnl else 0.0
        se = (statistics.pstdev(pnl) / math.sqrt(days)) if len(pnl) > 1 and days else 0.0
        out.append({"rule": name, "lift_in": lift, "years": cells,
                    "oos": {"n": len(g), "days": days, "net": net, "se": se}})
    return out


def render_rules(side: str, table: list[dict]) -> str:
    years = sorted({y for t in table for y in t["years"]})
    out = [f"== {side.upper()} top in-sample rules: net per trade by calendar year "
           f"(n trades), then out-of-sample only ==",
           f"{'rule':<34s} " + " ".join(f"{y:>13d}" for y in years)
           + f"  yrs+  {'OOS net':>14s} {'n':>5s}"]
    for t in table:
        cells = []
        for y in years:
            c = t["years"].get(y)
            cells.append(f"{100 * c['net']:>+7.2f}% ({c['n']:>3d})" if c else f"{'-':>13s}")
        pos = sum(c["net"] > 0 for c in t["years"].values())
        o = t["oos"]
        out.append(f"{t['rule']:<34s} " + " ".join(cells)
                   + f"  {pos}/{len(t['years'])}   "
                   f"{100 * o['net']:>+6.2f}%±{100 * o['se']:.2f} {o['n']:>5d}")
    return "\n".join(out)


def walk_forward_rule(rows, rule: tuple, cost_fn, *, min_fit_years: int = 2) -> list[dict]:
    """Expanding-window walk-forward for ONE two-feature rule.

    For each calendar year Y, the tercile cuts are fitted on every row
    before Y and the rule is traded through Y only. Nothing in year Y
    touches its own cuts. The benchmark is the unconditional side over
    the same year, so the table shows the rule's lift over "just trade
    this side every day", not its lift over zero.
    """
    (f1, b1), (f2, b2) = rule
    years = sorted({r["year"] for r in rows})
    out = []
    for y in years[min_fit_years:]:
        fit = [r for r in rows if r["year"] < y]
        test = [r for r in rows if r["year"] == y]
        if len(fit) < 250 or not test:
            continue
        cuts = {f: quantiles(fit, f, 3) for f in (f1, f2)}
        sel = [r for r in test if bucket_of(r[f1], cuts[f1]) == b1
               and bucket_of(r[f2], cuts[f2]) == b2]
        if len(sel) < 20:
            continue
        cost = cost_fn(y)
        pnl = [r["pnl"] for r in sel]
        days = len({r["ts"] for r in sel})
        net = statistics.mean(pnl) - cost
        se = statistics.pstdev(pnl) / math.sqrt(days) if days > 1 else 0.0
        bench = statistics.mean(r["pnl"] for r in test) - cost
        out.append({"year": y, "n": len(sel), "days": days, "fit_n": len(fit),
                    "net": net, "se": se, "bench": bench, "lift": net - bench,
                    "coins": len({r["symbol"] for r in sel})})
    return out


def render_walk_forward(side: str, bar: Barrier, rule: tuple, table: list[dict]) -> str:
    name = f"{rule[0][0]}[{rule[0][1]}] & {rule[1][0]}[{rule[1][1]}]"
    out = [f"== WALK-FORWARD {side.upper()} {bar}: {name} ==",
           "cuts refitted each year on prior years only; benchmark = unconditional "
           f"{side} over the same year",
           f"{'year':>5s} {'fit_n':>6s} {'coins':>5s} {'n':>5s} {'days':>5s} "
           f"{'rule net':>14s} {'bench':>8s} {'lift':>8s}"]
    for r in table:
        out.append(f"{r['year']:>5d} {r['fit_n']:>6d} {r['coins']:>5d} {r['n']:>5d} {r['days']:>5d} "
                   f"{100 * r['net']:>+7.2f}%±{100 * r['se']:.2f} {100 * r['bench']:>+7.2f}% "
                   f"{100 * r['lift']:>+7.2f}%")
    if table:
        pos = sum(r["net"] > 0 for r in table)
        beat = sum(r["lift"] > 0 for r in table)
        tot_n = sum(r["n"] for r in table)
        w = sum(r["net"] * r["n"] for r in table) / tot_n
        out.append(f"net positive {pos}/{len(table)} years; beats benchmark {beat}/{len(table)}; "
                   f"trade-weighted net {100 * w:+.2f}% over {tot_n} trades")
    return "\n".join(out)


def parse_rule(text: str) -> tuple:
    """'move_7d[2]&rvol_7d[1]' -> (('move_7d', 2), ('rvol_7d', 1))."""
    parts = [p.strip() for p in text.split("&")]
    if len(parts) != 2:
        raise ValueError("rule must be 'feat[b] & feat[b]'")
    out = []
    for p in parts:
        name, _, rest = p.partition("[")
        out.append((name.strip(), int(rest.rstrip("]"))))
    return tuple(out)


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
    ap.add_argument("--walk-forward", metavar="SIDE:RULE",
                    help="yearly walk-forward of one rule, e.g. "
                         "'short:move_7d[2]&rvol_7d[1]'")
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
    if args.walk_forward:
        side, _, rule_text = args.walk_forward.partition(":")
        rule = parse_rule(rule_text)
        rows = collect(pools, bar, args.days, side)
        cost_fn = lambda y: round_trip_cost(args.days / 2, fy.get(y, 0.0), side)
        print(render_walk_forward(side, bar, rule,
                                  walk_forward_rule(rows, rule, cost_fn)))
        return 0
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
