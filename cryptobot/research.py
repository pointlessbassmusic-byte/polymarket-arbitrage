"""Signal research: is there an edge in this data big enough to clear friction?

`cryptobot.study` answers "do the detectors as built make money" — no,
because their gross edge (~0.8%/trade) is smaller than the DEX round trip
(~1.2%). Tuning cannot close that. This module answers the prior question:
does a tradeable edge exist in the price data *at all*, independent of any
strategy?

It measures the only outcome a stop-and-target trader cares about — does
price reach +T before -S — for every candle, then asks whether any feature
bucket lifts the hit rate above break-even:

    p_breakeven = (S + cost) / (T + S)

Three modes, in order of how much they can fool you:

  buckets  hit rate per feature quantile vs break-even. In-sample only,
           so a good-looking bucket here proves nothing on its own.
  sweep    the same across a grid of barrier geometries and horizons,
           to rule out "the target/stop was just wrong".
  validate the one that matters. Rules are ranked on the first half of
           the data and scored on the second, measured as LIFT OVER THE
           CONTEMPORANEOUS BASELINE. Raw out-of-sample hit rates are
           worthless here: a market that rallies in the second half lifts
           every rule at once. If the correlation between in-sample lift
           and out-of-sample lift is not positive, feature selection is
           fitting noise and no strategy built on these features will
           hold up.

Intra-candle order is unknown, so a candle touching both barriers counts
as the LOSS — the same conservative convention the backtester uses.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import math
import pickle
import statistics
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

WARMUP = 288          # one day of 5m candles before any feature is valid
PER_HOUR = 12
STEP = 3              # sample every 3rd candle: adjacent ones overlap heavily
MIN_CELL = 250        # a bucket smaller than this is not worth scoring

FEATURES = ("move_5m", "move_30m", "move_1h", "move_24h",
            "vol_surge", "realized_vol_30m", "zscore_5m")


@dataclass(frozen=True)
class Barrier:
    target: float
    stop: float

    def breakeven(self, cost: float) -> float:
        """Hit rate at which target/stop trading exactly pays for itself."""
        return (self.stop + cost) / (self.target + self.stop)

    def gross(self, p: float) -> float:
        """Expected gross return per trade at hit rate p."""
        return p * self.target - (1.0 - p) * self.stop

    def __str__(self) -> str:
        return f"+{100 * self.target:.1f}%/-{100 * self.stop:.1f}%"


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) if b > 0 else 0.0


def features_at(closes, vols, i) -> dict:
    """The features the live scanner could actually see at candle i."""
    c = closes[i]

    def back(n):
        return _pct(c, closes[i - n]) if i >= n else 0.0

    vol_1h = sum(vols[i - PER_HOUR + 1:i + 1])
    vol_24h = sum(vols[i - WARMUP + 1:i + 1])
    surge = (vol_1h / (vol_24h / 24.0)) if vol_24h > 0 else 0.0
    rets = [math.log(closes[j] / closes[j - 1])
            for j in range(i - 5, i + 1)
            if j > 0 and closes[j] > 0 and closes[j - 1] > 0]
    rvol = statistics.pstdev(rets) if len(rets) > 2 else 0.0
    hist = [_pct(closes[j], closes[j - 1]) for j in range(i - WARMUP + 1, i)]
    mean = statistics.mean(hist) if hist else 0.0
    sd = statistics.pstdev(hist) if len(hist) > 2 else 0.0
    return {
        "move_5m": back(1),
        "move_30m": back(6),
        "move_1h": back(PER_HOUR),
        "move_24h": back(WARMUP),
        "vol_surge": surge,
        "realized_vol_30m": rvol,
        "zscore_5m": (back(1) - mean) / max(sd, 1e-4),
    }


def barrier_outcome(highs, lows, i, entry, bar: Barrier, horizon: int) -> int:
    """1 = target reached first, 0 = stop first or horizon expired."""
    up, dn = entry * (1 + bar.target), entry * (1 - bar.stop)
    for j in range(i + 1, min(i + 1 + horizon, len(highs))):
        if lows[j] <= dn:           # stop checked first: conservative
            return 0
        if highs[j] >= up:
            return 1
    return 0


def collect(pools, bar: Barrier, horizon: int, step: int = STEP) -> list[dict]:
    """Feature vector + barrier outcome + timestamp for sampled candles."""
    rows: list[dict] = []
    for _, (meta, candles) in pools.items():
        if len(candles) < WARMUP + horizon + 10:
            continue
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        vols = [c.volume_usd for c in candles]
        for i in range(WARMUP, len(candles) - horizon, step):
            if closes[i] <= 0:
                continue
            row = features_at(closes, vols, i)
            row["win"] = barrier_outcome(highs, lows, i, closes[i], bar, horizon)
            row["ts"] = candles[i].ts
            row["symbol"] = meta.symbol
            rows.append(row)
    rows.sort(key=lambda r: r["ts"])
    return rows


def hit_rate(rows) -> float:
    return sum(r["win"] for r in rows) / len(rows) if rows else 0.0


def quantiles(rows, feature, n) -> list[float]:
    vals = sorted(r[feature] for r in rows)
    return [vals[int(len(vals) * k / n)] for k in range(1, n)]


def bucket_of(value, cuts) -> int:
    return next((k for k, c in enumerate(cuts) if value < c), len(cuts))


def bucket_report(rows, bar: Barrier, cost: float, n_buckets=5,
                  features=FEATURES) -> dict:
    """Hit rate per feature quantile against break-even. In-sample only."""
    be = bar.breakeven(cost)
    out = {"n": len(rows), "breakeven": be, "base_rate": hit_rate(rows),
           "features": {}}
    for feat in features:
        cuts = quantiles(rows, feat, n_buckets)
        groups: list[list] = [[] for _ in range(n_buckets)]
        for r in rows:
            groups[bucket_of(r[feat], cuts)].append(r)
        cells = []
        for k, grp in enumerate(groups):
            if len(grp) < MIN_CELL:
                continue
            p = hit_rate(grp)
            se = math.sqrt(max(p * (1 - p), 1e-9) / len(grp))
            cells.append({"bucket": k, "lo": cuts[k - 1] if k else float("-inf"),
                          "n": len(grp), "p": p, "se": se,
                          "gross": bar.gross(p), "net": bar.gross(p) - cost,
                          "t": (p - be) / se if se else 0.0})
        out["features"][feat] = cells
    return out


def candidate_rules(rows, n_bands=3, features=FEATURES):
    """Every two-feature cell, as (name, predicate) built on THESE rows' cuts."""
    cuts = {f: quantiles(rows, f, n_bands) for f in features}
    rules = []
    for f1, f2 in itertools.combinations(features, 2):
        for b1 in range(n_bands):
            for b2 in range(n_bands):
                def pred(r, f1=f1, b1=b1, f2=f2, b2=b2):
                    return (bucket_of(r[f1], cuts[f1]) == b1
                            and bucket_of(r[f2], cuts[f2]) == b2)
                rules.append((f"{f1}[{b1}] & {f2}[{b2}]", pred))
    return rules


def _corr(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0] * len(vals)
    for pos, i in enumerate(order):
        out[i] = pos
    return out


def validate(rows, bar: Barrier, cost: float, n_bands=3,
             features=FEATURES) -> dict:
    """Rank rules on the first half, score them on the second.

    Scored as lift over each half's own baseline. A rising market lifts
    every rule's raw hit rate at once, so raw out-of-sample numbers say
    nothing about whether the rule works.
    """
    cut = len(rows) // 2
    in_s, out_s = rows[:cut], rows[cut:]
    base_in, base_out = hit_rate(in_s), hit_rate(out_s)
    scored = []
    for name, pred in candidate_rules(in_s, n_bands, features):
        gi = [r for r in in_s if pred(r)]
        go = [r for r in out_s if pred(r)]
        if len(gi) < MIN_CELL or len(go) < MIN_CELL:
            continue
        scored.append({"rule": name, "n_in": len(gi), "n_out": len(go),
                       "lift_in": hit_rate(gi) - base_in,
                       "lift_out": hit_rate(go) - base_out,
                       "p_out": hit_rate(go)})
    scored.sort(key=lambda s: -s["lift_in"])
    xs = [s["lift_in"] for s in scored]
    ys = [s["lift_out"] for s in scored]
    top = scored[:10]
    return {
        "n_rules": len(scored), "base_in": base_in, "base_out": base_out,
        "regime_swing": base_out - base_in,
        "span_in": (in_s[0]["ts"], in_s[-1]["ts"]) if in_s else (0, 0),
        "span_out": (out_s[0]["ts"], out_s[-1]["ts"]) if out_s else (0, 0),
        "pearson": _corr(xs, ys),
        "spearman": _corr(_ranks(xs), _ranks(ys)) if xs else 0.0,
        "top_lift_in": statistics.mean([s["lift_in"] for s in top]) if top else 0.0,
        "top_lift_out": statistics.mean([s["lift_out"] for s in top]) if top else 0.0,
        "rules": scored,
        "breakeven": bar.breakeven(cost),
    }


def sweep(pools, grid, horizons, cost: float) -> list[dict]:
    """Barrier geometry sweep: rules out 'the target/stop was just wrong'."""
    out = []
    for target, stop in grid:
        bar = Barrier(target, stop)
        for hours in horizons:
            rows = collect(pools, bar, int(hours * PER_HOUR))
            if not rows:
                continue
            p = hit_rate(rows)
            se = math.sqrt(max(p * (1 - p), 1e-9) / len(rows))
            be = bar.breakeven(cost)
            out.append({"barrier": str(bar), "hours": hours, "n": len(rows),
                        "p": p, "breakeven": be, "gross": bar.gross(p),
                        "net": bar.gross(p) - cost,
                        "t": (p - be) / se if se else 0.0})
    return out


# ---------------------------------------------------------------- rendering

def _day(ts) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def render_buckets(rep, bar: Barrier, cost: float) -> str:
    out = [f"barrier {bar}   cost {100 * cost:.2f}%   "
           f"break-even hit {100 * rep['breakeven']:.1f}%   "
           f"base hit {100 * rep['base_rate']:.1f}%   n={rep['n']}",
           f"gap any signal must close: "
           f"{100 * (rep['breakeven'] - rep['base_rate']):+.1f}pp", ""]
    for feat, cells in rep["features"].items():
        out.append(f"  {feat}")
        for c in cells:
            lo = "-inf" if c["lo"] == float("-inf") else f"{c['lo']:+.4f}"
            flag = "  <== clears break-even" if c["net"] > 0 else ""
            out.append(f"    q{c['bucket']} [{lo:>9s}..]  n={c['n']:5d}  "
                       f"hit {100 * c['p']:5.1f}%  gross {100 * c['gross']:+6.2f}%  "
                       f"net {100 * c['net']:+6.2f}%  t={c['t']:+6.2f}{flag}")
        out.append("")
    return "\n".join(out)


def render_sweep(rows, cost: float) -> str:
    out = [f"cost {100 * cost:.2f}% round trip", "",
           f"{'barrier':>14s} {'hrs':>4s} {'n':>6s} {'hit':>6s} {'BE':>6s} "
           f"{'gross':>7s} {'net':>7s}"]
    for r in rows:
        out.append(f"{r['barrier']:>14s} {r['hours']:>4.0f} {r['n']:>6d} "
                   f"{100 * r['p']:>5.1f}% {100 * r['breakeven']:>5.1f}% "
                   f"{100 * r['gross']:>+6.2f}% {100 * r['net']:>+6.2f}%")
    winners = [r for r in rows if r["net"] > 0]
    out.append("")
    out.append(f"{len(winners)} of {len(rows)} geometries are net positive "
               f"before any signal is applied")
    return "\n".join(out)


def render_validate(rep) -> str:
    out = [f"in-sample  {_day(rep['span_in'][0])}..{_day(rep['span_in'][1])}  "
           f"base hit {100 * rep['base_in']:.1f}%",
           f"out-sample {_day(rep['span_out'][0])}..{_day(rep['span_out'][1])}  "
           f"base hit {100 * rep['base_out']:.1f}%",
           f"regime swing between halves: {100 * rep['regime_swing']:+.1f}pp",
           "",
           f"{rep['n_rules']} rules scored in both halves",
           f"correlation of in-sample lift vs out-of-sample lift: "
           f"pearson {rep['pearson']:+.3f}  spearman {rep['spearman']:+.3f}",
           ""]
    out.append(f"{'rule':<42s} {'IS lift':>9s} {'OOS lift':>9s}")
    for s in rep["rules"][:10]:
        out.append(f"{s['rule']:<42s} {100 * s['lift_in']:>+8.1f}pp "
                   f"{100 * s['lift_out']:>+8.1f}pp")
    out.append("")
    out.append(f"top-10 by in-sample lift: {100 * rep['top_lift_in']:+.1f}pp in sample "
               f"-> {100 * rep['top_lift_out']:+.1f}pp out of sample")
    if rep["pearson"] <= 0.05:
        out.append("")
        out.append("VERDICT: selection does not survive. Ranking rules on past data "
                   "does not predict their future lift, so any strategy built by "
                   "picking among these features is fitting noise.")
    return "\n".join(out)


DEFAULT_GRID = [(0.02, 0.01), (0.03, 0.015), (0.04, 0.02), (0.04, 0.015),
                (0.05, 0.02), (0.06, 0.02), (0.06, 0.03), (0.08, 0.03),
                (0.10, 0.04)]
DEFAULT_HOURS = [6, 12, 24, 48]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("buckets", "sweep", "validate"))
    ap.add_argument("--cache", type=Path, required=True,
                    help="pickled {key: (PoolMeta, [Candle])} from the backtester")
    ap.add_argument("--target", type=float, default=0.04)
    ap.add_argument("--stop", type=float, default=0.02)
    ap.add_argument("--cost", type=float, default=0.012,
                    help="round-trip friction as a fraction (DEX ~0.012, CEX ~0.003)")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--buckets", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pools = pickle.loads(args.cache.read_bytes())
    bar = Barrier(args.target, args.stop)

    if args.mode == "sweep":
        print(render_sweep(sweep(pools, DEFAULT_GRID, DEFAULT_HOURS, args.cost),
                           args.cost))
        return 0

    rows = collect(pools, bar, int(args.hours * PER_HOUR))
    if not rows:
        print("no usable candles in cache")
        return 1
    if args.mode == "buckets":
        print(render_buckets(bucket_report(rows, bar, args.cost, args.buckets),
                             bar, args.cost))
    else:
        print(render_validate(validate(rows, bar, args.cost)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
