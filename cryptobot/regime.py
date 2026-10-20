"""Regime study: does the MARKET state predict forward returns?

`cryptobot.research` established that per-token price features carry no
repeatable information over 21 days, but that the market-wide baseline
swung +20.8pp between halves — three times any feature effect. Twenty-one
days holds ~14 regime episodes, too few to test. This module runs the
same question on a longer history (hourly or daily candles).

Market state at time t is measured cross-sectionally:

    breadth_N   fraction of tokens whose close is above their close N
                hours earlier
    median_N    median N-hour return across tokens

Two questions, answered on the second half of the data using cuts fitted
on the first half:

  persistence   is breadth at t related to breadth at t+H? A regime
                signal is only tradeable if the state lasts longer than
                the trade.
  prediction    conditional on breadth at t, what is the average forward
                outcome? Reported as hit rate of a +T/-S barrier and as
                plain forward return.

Statistics: tokens at the same timestamp share the market move, so the
unit of observation is the TIMESTAMP (cross-sectional mean of outcomes),
not the token. Sampling is non-overlapping (step = horizon) so consecutive
observations do not share forward windows.
"""

from __future__ import annotations

import argparse
import logging
import math
import pickle
import statistics
from pathlib import Path

from cryptobot.research import Barrier

logger = logging.getLogger(__name__)

MIN_TOKENS = 6          # a cross-section thinner than this is not a market
MIN_OBS = 20            # per bucket, in timestamps


def _bucket_ts(ts: float, hours: int) -> int:
    return int(ts // (hours * 3600) * (hours * 3600))


def align(pools, candle_hours: int) -> tuple[list[int], dict[str, dict[int, tuple]]]:
    """Index every pool by bucketed timestamp -> (close, high, low)."""
    by_sym: dict[str, dict[int, tuple]] = {}
    for _, (meta, candles) in pools.items():
        d = {}
        for c in candles:
            if c.close > 0:
                d[_bucket_ts(c.ts, candle_hours)] = (c.close, c.high, c.low)
        if d:
            by_sym[meta.symbol] = d
    stamps = sorted(set().union(*[set(d) for d in by_sym.values()]))
    return stamps, by_sym


def _forward(series: dict[int, tuple], t: int, step: int, horizon: int,
             bar: Barrier) -> tuple[int, float] | None:
    """(barrier win, plain forward return) for one token from t."""
    entry = series[t][0]
    up, dn = entry * (1 + bar.target), entry * (1 - bar.stop)
    win = 0
    last = None
    for k in range(1, horizon + 1):
        row = series.get(t + k * step)
        if row is None:
            continue
        last = row[0]
        if win == 0:
            if row[2] <= dn:
                win = -1          # stopped: cannot win later
            elif row[1] >= up:
                win = 1
    if last is None:
        return None
    return (1 if win == 1 else 0), last / entry - 1.0


def observations(pools, *, candle_hours: int, lookback_hours: int,
                 horizon_hours: int, bar: Barrier) -> list[dict]:
    """One row per timestamp: market state + cross-sectional forward outcome."""
    step = candle_hours * 3600
    look = lookback_hours // candle_hours
    horizon = horizon_hours // candle_hours
    stamps, by_sym = align(pools, candle_hours)
    rows = []
    for t in stamps[::horizon]:                   # non-overlapping windows
        ups, rets, fwd_w, fwd_r = 0, [], [], []
        for sym, series in by_sym.items():
            now = series.get(t)
            then = series.get(t - look * step)
            if now is None or then is None:
                continue
            r = now[0] / then[0] - 1.0
            rets.append(r)
            ups += r > 0
            out = _forward(series, t, step, horizon, bar)
            if out is not None:
                fwd_w.append(out[0])
                fwd_r.append(out[1])
        if len(rets) < MIN_TOKENS or len(fwd_w) < MIN_TOKENS:
            continue
        rows.append({
            "ts": t, "n_tokens": len(rets),
            "breadth": ups / len(rets),
            "median": statistics.median(rets),
            "hit": sum(fwd_w) / len(fwd_w),
            "fwd": statistics.mean(fwd_r),
        })
    return rows


def _mean_se(xs) -> tuple[float, float]:
    if len(xs) < 2:
        return (xs[0] if xs else 0.0), 0.0
    return statistics.mean(xs), statistics.stdev(xs) / math.sqrt(len(xs))


def _corr(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def persistence(rows, key="breadth", *, lookback_hours: int = 24,
                horizon_hours: int = 24) -> dict:
    """Autocorrelation of the state across observations.

    Consecutive observations are `horizon` apart, but the state looks back
    `lookback`; when lookback > horizon the windows OVERLAP and share
    data, so even pure noise autocorrelates at roughly
    1 - horizon/lookback. That mechanical floor is reported as `null`,
    and `autocorr_clean` is measured at the first lag whose windows do
    not overlap, which is the number that says whether the state
    actually persists.
    """
    xs = [r[key] for r in rows]
    ac = _corr(xs[:-1], xs[1:])
    null = max(0.0, 1.0 - horizon_hours / lookback_hours)
    lag = max(1, math.ceil(lookback_hours / horizon_hours))
    clean = _corr(xs[:-lag], xs[lag:]) if len(xs) > lag + 2 else 0.0
    med = statistics.median(xs)
    runs, cur, last = [], 0, None
    for x in xs:
        s = x > med
        if s == last:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur, last = 1, s
    runs.append(cur)
    return {"autocorr": ac, "null": null, "lag": lag, "autocorr_clean": clean,
            "n": len(xs), "episodes": len(runs),
            "mean_run": statistics.mean(runs) if runs else 0.0}


def predict(rows, key: str, bar: Barrier, cost: float, n_buckets=4) -> dict:
    """Fit bucket cuts on the first half, score buckets on the second."""
    cut = len(rows) // 2
    fit, test = rows[:cut], rows[cut:]
    vals = sorted(r[key] for r in fit)
    # Dedupe: a state that sits at 0 or 1 most of the time (a strongly
    # regime-driven market) makes quantile cuts collide.
    cuts = sorted({vals[int(len(vals) * k / n_buckets)] for k in range(1, n_buckets)})
    n_buckets = len(cuts) + 1

    def which(v):
        return next((k for k, c in enumerate(cuts) if v < c), n_buckets - 1)

    def score(sample):
        groups: list[list] = [[] for _ in range(n_buckets)]
        for r in sample:
            groups[which(r[key])].append(r)
        base_hit, _ = _mean_se([r["hit"] for r in sample])
        base_fwd, _ = _mean_se([r["fwd"] for r in sample])
        cells = []
        for k, g in enumerate(groups):
            if len(g) < MIN_OBS:
                cells.append(None)
                continue
            hit, hit_se = _mean_se([r["hit"] for r in g])
            fwd, fwd_se = _mean_se([r["fwd"] for r in g])
            cells.append({"n": len(g), "hit": hit, "hit_se": hit_se,
                          "hit_lift": hit - base_hit,
                          "fwd": fwd, "fwd_se": fwd_se,
                          "fwd_lift": fwd - base_fwd,
                          "net": bar.gross(hit) - cost})
        return {"n": len(sample), "base_hit": base_hit, "base_fwd": base_fwd,
                "cells": cells}

    fit_s, test_s = score(fit), score(test)
    # does the bucket ORDER hold from fit to test?
    pairs = [(a["hit_lift"], b["hit_lift"]) for a, b in zip(fit_s["cells"], test_s["cells"])
             if a and b]
    return {"key": key, "cuts": cuts, "fit": fit_s, "test": test_s,
            "breakeven": bar.breakeven(cost),
            "order_corr": _corr([p[0] for p in pairs], [p[1] for p in pairs])}


def _day(ts) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def render(rows, pers: dict, preds: list[dict], bar: Barrier, cost: float,
           lookback_hours: int, horizon_hours: int) -> str:
    out = [f"{len(rows)} non-overlapping {horizon_hours}h observations, "
           f"{_day(rows[0]['ts'])} .. {_day(rows[-1]['ts'])}, "
           f"median cross-section {int(statistics.median(r['n_tokens'] for r in rows))} tokens",
           f"state lookback {lookback_hours}h; barrier {bar}; cost {100 * cost:.2f}%; "
           f"break-even hit {100 * bar.breakeven(cost):.1f}%", "",
           f"persistence of breadth: lag-1 autocorr {pers['autocorr']:+.3f} "
           f"(overlap null ~{pers['null']:+.2f}); non-overlapping lag-{pers['lag']} "
           f"autocorr {pers['autocorr_clean']:+.3f}; "
           f"{pers['episodes']} episodes above/below median, "
           f"mean run {pers['mean_run']:.1f} x {horizon_hours}h", ""]
    for p in preds:
        out.append(f"== conditional on {p['key']} (cuts fitted on first half) ==")
        for label, s in (("fit  ", p["fit"]), ("test ", p["test"])):
            out.append(f"  {label} n={s['n']:4d}  base hit {100 * s['base_hit']:5.1f}%  "
                       f"base fwd {100 * s['base_fwd']:+6.2f}%")
            for k, c in enumerate(s["cells"]):
                if c is None:
                    out.append(f"        q{k}: too few observations")
                    continue
                out.append(f"        q{k} n={c['n']:4d}  hit {100 * c['hit']:5.1f}% "
                           f"(lift {100 * c['hit_lift']:+5.1f}pp ±{100 * c['hit_se']:.1f})  "
                           f"fwd {100 * c['fwd']:+6.2f}% (lift {100 * c['fwd_lift']:+5.2f}pp "
                           f"±{100 * c['fwd_se']:.2f})  net {100 * c['net']:+6.2f}%")
        out.append(f"  bucket-order agreement fit->test: {p['order_corr']:+.2f}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--candle-hours", type=int, default=1)
    ap.add_argument("--lookback", type=int, default=24, help="state lookback, hours")
    ap.add_argument("--horizon", type=int, default=24, help="trade horizon, hours")
    ap.add_argument("--target", type=float, default=0.04)
    ap.add_argument("--stop", type=float, default=0.02)
    ap.add_argument("--cost", type=float, default=0.012)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pools = pickle.loads(args.cache.read_bytes())
    bar = Barrier(args.target, args.stop)
    rows = observations(pools, candle_hours=args.candle_hours,
                        lookback_hours=args.lookback, horizon_hours=args.horizon,
                        bar=bar)
    if len(rows) < 2 * MIN_OBS:
        print(f"only {len(rows)} usable observations")
        return 1
    preds = [predict(rows, k, bar, args.cost) for k in ("breadth", "median")]
    pers = persistence(rows, lookback_hours=args.lookback,
                       horizon_hours=args.horizon)
    print(render(rows, pers, preds, bar, args.cost, args.lookback, args.horizon))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
