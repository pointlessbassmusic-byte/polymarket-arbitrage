"""
Social / sentiment harnesses.
=============================

Two executable tests for the social layer. Both are written so they run honestly on one day of
collection (they return ``inconclusive`` with the sample shortfall) and become real as the daily
capture accumulates.

``attention_vs_abs_return``: does retail attention (mention count per ticker-day on Reddit and StockTwits,
standardised within ticker) rank-correlate with the next day's absolute return? Statistic: Spearman rho over
ticker-days whose price bar is available. Point in time: a derived row is used only if its capture
(available_at) is at or before close(day), the start of the close(day) -> close(day+1) return window (16:00
New York for equities, 24:00 UTC for crypto). One row per (ticker, day): each source's latest valid capture,
summed over Reddit and StockTwits. Null: permute the attention values within each ticker (keeps the return
series and the per-ticker counts). Requires at least ``min_days`` distinct capture days that contribute a
joined row.

``fear_greed_forward_returns``: after extreme fear (index <= low) is the forward h-day BTC log return
higher than unconditional, and after extreme greed (>= high) lower? Statistic: difference in mean
forward return, extreme minus all. Null: circular block shift of the Fear & Greed indicator against
the return series (keeps both autocorrelations, breaks their alignment). Point in time: the index for
day d is usable from d+1 and the forward return starts at the next daily close. The claim is a
conjunction: the fear side must be above and the greed side below the unconditional mean; the pass's
significance (p < 0.05, both halves agreeing in sign) must hold on at least one side.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import numpy as np

_NY = ZoneInfo("America/New_York")


def _day(ts_iso: str) -> str:
    return (ts_iso or "")[:10]


def _rank(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    vals, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    if (counts > 1).any():
        sums = np.zeros(len(vals)); np.add.at(sums, inv, ranks)
        ranks = (sums / counts)[inv]
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    rx, ry = _rank(np.asarray(x, float)), _rank(np.asarray(y, float))
    if rx.std() == 0 or ry.std() == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def daily_closes(price_rows: Iterable[dict]) -> dict[str, dict[str, float]]:
    """{symbol: {day: close}} from observation rows whose value has symbol, t, close."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in price_rows:
        v = r["value"]
        day = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        out[v["symbol"]][day] = float(v["close"])
    return out


def _ts(iso: str) -> Optional[float]:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def close_ts(sym: str, day: str) -> float:
    """Unix time of the daily close that starts the forward return window: 16:00 New York (20:00 or 21:00 UTC by DST) for
    equities, 24:00 UTC for crypto (Yahoo's X-USD daily bar runs 00:00-24:00 UTC)."""
    d = datetime.strptime(day, "%Y-%m-%d")
    if sym.endswith("-USD"):
        return (d.replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp()
    return d.replace(hour=16, tzinfo=_NY).timestamp()


def attention_ticker_days(derived_rows: Iterable[dict], closes: dict[str, dict[str, float]],
                          sources: Optional[tuple] = ("reddit", "stocktwits")) -> tuple[dict[tuple, dict], int]:
    """Point-in-time ticker-days: {(symbol, day): {mentions, abs_ret, captures}} and the number of rows dropped as known
    only after the decision time. A derived row counts only if captured at or before close(day); per (symbol, day, source)
    the latest such capture is kept, and mentions are summed over the sources. abs_ret is |log close(next day)/close(day)|."""
    next_day: dict[str, dict[str, str]] = {}
    for sym, d in closes.items():
        days = sorted(d)
        next_day[sym] = {days[i]: days[i + 1] for i in range(len(days) - 1)}
    latest: dict[tuple, tuple[float, float, str]] = {}
    n_after_close = 0
    for r in derived_rows:
        v = r["value"]
        if sources is not None and v.get("source") not in sources:
            continue
        t, day = v["ticker"], v["day"]
        sym = t if t in closes else (f"{t}-USD" if f"{t}-USD" in closes else None)     # crypto tickers quote as X-USD
        if not sym or day not in next_day.get(sym, {}) or closes[sym][day] <= 0:
            continue
        at = _ts(r.get("available_at", ""))
        if at is None or at > close_ts(sym, day):
            n_after_close += 1                         # backfilled or post-close: not known at the decision time
            continue
        key = (sym, day, v.get("source"))
        if key not in latest or at > latest[key][0]:
            latest[key] = (at, float(v["mentions"]), _day(r.get("available_at", "")))
    out: dict[tuple, dict] = {}
    for (sym, day, _src), (_at, m, cap) in latest.items():
        a = out.setdefault((sym, day), {"mentions": 0.0, "abs_ret": abs(math.log(closes[sym][next_day[sym][day]] / closes[sym][day])), "captures": set()})
        a["mentions"] += m; a["captures"].add(cap)
    return out, n_after_close


def attention_vs_abs_return(derived_rows: Iterable[dict], price_rows: Iterable[dict], min_days: int = 30, n_perm: int = 2000, seed: int = 0,
                            sources: Optional[tuple] = ("reddit", "stocktwits")) -> dict:
    closes = daily_closes(price_rows)
    joined, n_after_close = attention_ticker_days(derived_rows, closes, sources)
    by_ticker: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    captures = set()                                   # distinct capture days that contribute a joined row, the honest sample size
    for (sym, day), a in sorted(joined.items()):
        by_ticker[sym].append((day, a["mentions"], a["abs_ret"]))
        captures |= a["captures"]
    n_days = len(captures)
    xs, ys, groups = [], [], []
    for t, rows in by_ticker.items():
        m = np.array([x[1] for x in rows]); r = np.array([x[2] for x in rows])
        if len(m) < 2 or m.std() == 0:
            continue
        xs.append((m - m.mean()) / m.std()); ys.append(r); groups.append(len(m))
    out = {"n_days": n_days, "min_days": min_days, "n_tickers": len(groups), "n_ticker_days": int(sum(groups)),
           "n_rows_after_decision_time": n_after_close, "sources": list(sources) if sources is not None else None}
    if n_days < min_days or sum(groups) < 3 * max(1, len(groups)):
        out.update({"rho": None, "p_value": None, "verdict": "inconclusive", "reason": f"{n_days}/{min_days} capture days with a point-in-time joined row, {int(sum(groups))} usable ticker-days ({n_after_close} rows captured after close(day) dropped)"})
        return out
    x = np.concatenate(xs); y = np.concatenate(ys)
    rho = spearman(x, y)
    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for b in range(n_perm):
        xp = np.concatenate([rng.permutation(g) for g in xs])
        null[b] = spearman(xp, y)
    p = float((np.sum(null >= rho) + 1) / (n_perm + 1))
    out.update({"rho": rho, "p_value": p, "null_sd": float(null.std()),
                "verdict": "supported" if (p < 0.05 and rho > 0) else "not_supported",
                "reason": f"Spearman rho {rho:+.3f} between standardised mentions and next-day |return|, permutation p={p:.3f}"})
    return out


def fear_greed_forward_returns(fng_rows: Iterable[dict], price_rows: Iterable[dict], symbol: str = "BTC-USD", horizon_days: int = 7,
                               low: int = 25, high: int = 75, n_boot: int = 2000, seed: int = 0, min_extreme: int = 30, lag_days: int = 1) -> dict:
    """``lag_days`` shifts the entry close: the forward window starts at close(day[i + lag_days]), where close(d) is the
    close of the daily bar d (for BTC-USD, 24:00 UTC of d). The index for d is observed at d 00:00 and available 24 h
    later (= close(d)), so lag 0 already enters at the first close at or after available_at (point in time); 1 (the
    default, the registered T-41 alignment) is one day more conservative; -1 enters at close(d-1), the naive join on
    observed_at, and uses the index before it was published. Entries before the first price are skipped (no wrap)."""
    closes = daily_closes(price_rows).get(symbol, {})
    days = sorted(closes)
    idx = {d: i for i, d in enumerate(days)}
    fng = {}
    for r in fng_rows:
        fng[_day(r["observed_at"])] = float(r["value"]["value"])
    # align: index for day d (usable from d+lag) -> forward return from close(d+lag) to close(d+lag+h)
    f, fwd = [], []
    for d, val in sorted(fng.items()):
        i = idx.get(d)
        if i is None or i + lag_days < 0 or i + lag_days + horizon_days >= len(days):
            continue
        c0, c1 = closes[days[i + lag_days]], closes[days[i + lag_days + horizon_days]]
        if c0 > 0 and c1 > 0:
            f.append(val); fwd.append(math.log(c1 / c0))
    f = np.array(f); fwd = np.array(fwd)
    n = len(f)
    out = {"n": n, "horizon_days": horizon_days, "low": low, "high": high, "symbol": symbol, "lag_days": lag_days}
    if n < 200:
        out.update({"verdict": "inconclusive", "reason": f"only {n} aligned days"}); return out
    fear = f <= low; greed = f >= high
    out["n_fear"], out["n_greed"] = int(fear.sum()), int(greed.sum())
    if fear.sum() < min_extreme or greed.sum() < min_extreme:
        out.update({"verdict": "inconclusive", "reason": f"too few extreme days (fear {int(fear.sum())}, greed {int(greed.sum())}; need {min_extreme} each)"}); return out
    mu = fwd.mean()
    d_fear = float(fwd[fear].mean() - mu); d_greed = float(fwd[greed].mean() - mu)
    rng = np.random.default_rng(seed)
    nf = np.empty(n_boot); ng = np.empty(n_boot)
    for b in range(n_boot):
        k = int(rng.integers(horizon_days + 1, n - horizon_days - 1))
        fs = np.roll(f, k)
        nf[b] = fwd[fs <= low].mean() - mu; ng[b] = fwd[fs >= high].mean() - mu
    p_fear = float((np.sum(nf >= d_fear) + 1) / (n_boot + 1))
    p_greed = float((np.sum(ng <= d_greed) + 1) / (n_boot + 1))
    half = n // 2
    def _d(mask, lo, hi):
        sub = fwd[lo:hi]; m = mask[lo:hi]
        return float(sub[m].mean() - sub.mean()) if m.sum() >= 5 else float("nan")
    sign_fear = (_d(fear, 0, half) > 0) and (_d(fear, half, n) > 0)
    sign_greed = (_d(greed, 0, half) < 0) and (_d(greed, half, n) < 0)
    out.update({"d_fear": d_fear, "d_greed": d_greed, "p_fear": p_fear, "p_greed": p_greed,
                "d_fear_halves": [_d(fear, 0, half), _d(fear, half, n)], "d_greed_halves": [_d(greed, 0, half), _d(greed, half, n)],
                "mean_fwd": float(mu)})
    # The claim is a conjunction (fear above AND greed below the mean); the pass's significance + halves test must hold on
    # at least one side, and neither side's estimate may contradict the claim's direction.
    from mandel.experiments.underlying2 import _verdict
    out["verdict"], why = _verdict([
        ("after fear the mean forward return exceeds the unconditional mean", d_fear > 0),
        ("after greed the mean forward return falls short of the unconditional mean", d_greed < 0),
        ("p < 0.05 with both halves agreeing in sign on the fear or greed side", (p_fear < 0.05 and sign_fear) or (p_greed < 0.05 and sign_greed)),
    ])
    out["reason"] = (f"{horizon_days}d {symbol} log return after fear<={low}: {d_fear:+.4f} vs all (block-shift p={p_fear:.3f}, halves {out['d_fear_halves'][0]:+.4f}/{out['d_fear_halves'][1]:+.4f}); "
                     f"after greed>={high}: {d_greed:+.4f} (p={p_greed:.3f}, halves {out['d_greed_halves'][0]:+.4f}/{out['d_greed_halves'][1]:+.4f}); {why}")
    return out
