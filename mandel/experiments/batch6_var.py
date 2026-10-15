"""
Batch 6a, group ``var``: variance risk premium and short-premium claims on SPY and the S&P 500.
==============================================================================================

Nine options-library claims, each tested against its claim, trial.pass and trial.min_n as worded.

Model-free (VIX as the variance-swap strike, no option prices):
  * T-540 short 30-day variance struck at VIX^2, settled on the next 21 SPY close-to-close returns (%^2 per month);
  * T-234 the win rate of VIX^2 over the next 21-day ^GSPC realised variance (> 75% of non-overlapping calendar months);
  * T-235 a short variance position scaled by max(z, 0), z the z-score of VIX minus a walk-forward HAR(1,5,22) forecast,
    on calendar-month cycles;
  * T-529 the VIX1D-implied next-day variance, (VIX1D/100)^2/365, against the next ^GSPC squared log return.

MODEL-PRICED (Black-Scholes legs at a stated multiple of VIX/100; every result is labelled MODEL-PRICED):
  * T-101 30-DTE ATM short straddle at 0.90 x VIX: top-minus-bottom tercile of VIX - RV21 (SPY log returns), tercile
    cut-points from the training window of ``walk_forward_splits`` on SPY entries only and applied out of sample (min_n in
    out-of-sample cycles); the CI must exclude 0 whatever the bootstrap seed and block length (``robust_exclusion``);
  * T-123 30-DTE ATM long straddle at 0.90 x VIX, delta-hedged daily at the entry vol, 1 bp per share traded: P&L / vega;
  * T-233 the same straddle sold at 0.81 x VIX (and at the ATM-IV / VIX ratio measured on the captured SPY smile), hedged
    daily, after a 0.5 vol-point round trip, on SPY's monthly expiry calendar: P&L / premium;
  * T-156 45-DTE 0.16-delta short strangle at VIX on the monthly expiry calendar: 21-DTE exit vs hold to expiry, P&L per
    day in the trade;
  * T-157 weekly (Friday-expiry) ladder of quarter-size 0.16-delta short puts vs one full-size monthly-expiry entry, both
    entered at 45 DTE and managed at 50% of the credit or 21 DTE: ratio of maximum drawdowns.

Conventions (shared):
  * Entry calendar (house rule 10: no verdict may depend on an arbitrary grid phase).
    (a) A claim that names a calendar is tested on it. SPY's standard monthly expiry is the third Friday of the month, or
        the prior session when that Friday is a holiday; a weekly expiry is every Friday, same holiday rule. An option of
        stated DTE is entered at the session nearest DTE calendar days before its expiry (ties to the earlier session).
        T-233's 30-DTE monthly cycles never overlap: when that session precedes the previous monthly expiry, the cycle
        enters at the previous expiry's close (28 DTE). T-156 and T-157's single book enter 45 DTE before each monthly
        expiry; T-157's ladder enters 45 DTE before every weekly expiry. A claim on months (T-234, T-235) enters at the
        first session of each calendar month that has a VIX close.
    (b) A claim on a plain non-overlapping 21-trading-day grid (T-101, T-123, T-540) has 21 equally valid start offsets.
        The claimed statistic is computed on every offset (block 6 cycles) and on the POOLED overlapping daily entries of
        all offsets, whose studentized circular block bootstrap uses blocks of 6 holds (126 days, >= 2 x hold). The pooled
        estimate is the primary statistic of every criterion; the reason reports the per-offset range of the statistic
        and of its bound and how many offsets pass. n stays in the claim's units: the number of distinct 21-day holds the
        pooled entries span (equal to the offset-0 grid's cycle count).
    (c) Daily series and fixed-date statistics (T-529's one-day windows) are unaffected.
  * Cycles. A 21-trading-day cycle is entered at a close and expires 21 trading days later; T is the calendar time between
    the two closes / 365 (28-32 days, about 30). Calendar cycles carry their own expiry session. Off-calendar 45-DTE
    positions (the daily-entry checks) expire on the last trading day on or before entry + 45 calendar days.
  * Point in time. Entries use the VIX and SPY closes of the entry day (both known at the close; VIX closes at 16:15 ET,
    SPY at 16:00, a declared 15-minute mismatch; T-123 reports the prior-day VIX sensitivity); forward windows start with
    the next day's return. Index days without a VIX close stay in the calendar (returns are always between consecutive
    closes); no entry is taken on them and a daily mark uses the latest VIX close. The 3-month bill (FRED DTB3, a discount
    yield published the next day) enters as the prior print, converted to a continuous rate
    r = -ln(1 - d/100 * 91/360) / (91/365).
  * Options settle on RAW closes (close, not adjclose). SPY dividends come from the adjclose/close ratio step: on an ex-day
    i, D = close[i-1] * (1 - f[i-1]/f[i]) with f = adjclose/close. An option whose life spans an ex-date is priced on the
    dividend forward, S - PV(D), with the amount forecast point in time as the last dividend paid at or before the
    decision (none before the first ex-date) and the ex-date PROJECTED from SPY's quarterly schedule (the third Friday of
    March, June, September and December, prior session on a holiday: 135 of the 136 archived ex-dates), never read from
    the realised adjclose steps. A hedge that holds shares across an ex-date receives (or, short, pays) the actual
    dividend in cash on the actual ex-date. The hedged P&L runs through a cash account that earns the bill rate.
  * Realised variance is the sum of squared close-to-close log returns, annualised with 252 / window (no mean removed).
  * Intervals. Studentized (bootstrap-t) circular block bootstraps: the statistic is studentized by a Bartlett long-run
    s.e. with bandwidth = block (as in backtest_eval.block_bootstrap_pvalue; long bandwidths use the identical FFT form).
    Differences are bootstrapped PAIRED on a shared timeline. A drawdown ratio (T-157) has no closed-form s.e., so its
    interval is a percentile block bootstrap of paired daily P&L paths. Blocks cover the overlap of overlapping windows.
  * min_n is counted in the claim's own units (cycles, months, entries, days). Below min_n a claim cannot be supported,
    and a failing criterion counts only when it fails decisively (its interval wholly on the wrong side); otherwise the
    criterion is reported as not decisive and the verdict is inconclusive.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not implemented
gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, index_closes, variance_risk_premium
from mandel.options import bs
from mandel.validation.backtest_eval import (_hac_var, deflated_sharpe_ratio, kurtosis, sharpe_ratio, skewness,
                                             walk_forward_splits)

PPY = 252
HOLD = 21
SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
VIX_B = "cboe-VIX-history"
VIX1D_B = "cboe-VIX1D-history"
HOURLY_SPY_B = "hourly-SPY"
DTB3_B = "fred-DTB3"
SMILE_P = "spy-smile-"
SPX_CHAIN_P = "options-chain-SPX-"
EVENT_B = {"FOMC": "fomc-meetings", "CPI": "macro-release-cpi", "NFP": "macro-release-employment-situation"}
COMM_PER_SHARE = 0.65 / 100.0          # $0.65 per contract of 100 shares, per leg per fill
MP = "MODEL-PRICED"
TRADED_NOTE = "the traded version needs SPY chain history (2 capture days archived)"


# =================================================================================================== statistics ==

def _lrv(x, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance, identical to backtest_eval._hac_var (bandwidth ``bw``). Long bandwidths (the
    pooled overlapping series use 126 days) take the autocovariances from an FFT, the same sums at O(n log n)."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    bw = max(1, int(bw))
    if bw <= 24:
        return _hac_var(x, bw)
    n = x.shape[1]
    xc = x - x.mean(axis=1, keepdims=True)
    m = 1 << int(math.ceil(math.log2(2 * n)))
    f = np.fft.rfft(xc, m, axis=1)
    ac = np.fft.irfft(f * np.conj(f), m, axis=1)[:, :min(bw, n)]
    k = np.arange(ac.shape[1])
    w = np.where(k == 0, 1.0, 2.0 * (1.0 - k / bw))
    return np.maximum((ac * w).sum(axis=1) / n, 1e-300)


def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def _chunks(n_boot: int, n: int):
    k = max(1, min(n_boot, 2_000_000 // max(n, 1)))
    done = 0
    while done < n_boot:
        yield min(k, n_boot - done)
        done += k


def stud_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Two-sided studentized circular block-bootstrap CI of the mean at ``level``: (lo, hi), or (None, None) below 8
    observations. Each resample's mean is studentized by its own Bartlett long-run s.e. (bandwidth = block)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    v0 = float(_lrv(x[None, :], block)[0])
    if v0 <= 1e-30:
        return m, m
    se = math.sqrt(v0 / n)
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        xb = x[_boot_idx(rng, n, block, k)]
        ts.append((xb.mean(axis=1) - m) / np.sqrt(_lrv(xb, block) / n))
    t = np.concatenate(ts)
    a = (1.0 - level) / 2.0
    return m - float(np.quantile(t, 1.0 - a)) * se, m - float(np.quantile(t, a)) * se


def pct_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Percentile circular block-bootstrap CI of the mean (used for a proportion, whose s.e. vanishes near 0 or 1)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    ms = np.concatenate([x[_boot_idx(rng, n, block, k)].mean(axis=1) for k in _chunks(n_boot, n)])
    a = (1.0 - level) / 2.0
    return float(np.quantile(ms, a)), float(np.quantile(ms, 1.0 - a))


def stud_ci_group_diff(x, top, bot, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> dict:
    """mean(x | top) - mean(x | bot) for two disjoint groups of one timeline, with a studentized circular block-bootstrap
    CI: blocks of the shared timeline are resampled (each cycle keeps its label), and each resample is studentized by the
    Bartlett long-run s.e. of the difference's influence function psi_i = n (1top_i (x_i - m_top)/n_top -
    1bot_i (x_i - m_bot)/n_bot)."""
    x = np.asarray(x, dtype=float)
    top = np.asarray(top, dtype=bool)
    bot = np.asarray(bot, dtype=bool)
    n = x.size
    out = {"n": int(n), "n_top": int(top.sum()), "n_bottom": int(bot.sum()), "diff": None, "ci": [None, None],
           "mean_top": None, "mean_bottom": None}
    if top.sum() < 4 or bot.sum() < 4 or n < 8:
        return out
    block = max(1, min(int(block), n // 4))

    def stat(xb, tb, bb):
        nt, nbb = tb.sum(axis=1), bb.sum(axis=1)
        ok = (nt > 0) & (nbb > 0)
        nt, nbb = np.maximum(nt, 1), np.maximum(nbb, 1)
        mt = (xb * tb).sum(axis=1) / nt
        mb = (xb * bb).sum(axis=1) / nbb
        psi = n * (tb * (xb - mt[:, None]) / nt[:, None] - bb * (xb - mb[:, None]) / nbb[:, None])
        return mt - mb, np.sqrt(_lrv(psi, block) / n), ok, mt, mb

    d0, se0, _, mt0, mb0 = stat(x[None, :], top[None, :], bot[None, :])
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(diff=d0, mean_top=float(mt0[0]), mean_bottom=float(mb0[0]), se=se0)
    if se0 <= 1e-150:
        out["ci"] = [d0, d0]
        return out
    rng = np.random.default_rng(seed)
    ts, ds = [], []
    for k in _chunks(n_boot, n):
        idx = _boot_idx(rng, n, block, k)
        d, se, ok, _, _ = stat(x[idx], top[idx], bot[idx])
        ok &= se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
        ds.append(d[ok])
    t, dd = np.concatenate(ts), np.concatenate(ds)
    a = (1.0 - level) / 2.0
    out["ci"] = [d0 - float(np.quantile(t, 1.0 - a)) * se0, d0 - float(np.quantile(t, a)) * se0]
    out["ci_percentile"] = [float(np.quantile(dd, a)), float(np.quantile(dd, 1.0 - a))]
    return out


def mc_group_ci(x, top, bot, block: int, level: float = 0.95, n_boot: int = 20000, n_rep: int = 10, seed: int = 0) -> dict:
    """``stud_ci_group_diff`` repeated over ``n_rep`` independent replicates of ``n_boot`` draws (seeds seed .. seed+n_rep-1).
    The studentized and percentile bounds are the replicate means, reported with their Monte Carlo s.e. (replicate sd /
    sqrt(n_rep)), so a decision taken on them does not hinge on one seed."""
    n_rep = max(2, int(n_rep))
    reps = [stud_ci_group_diff(x, top, bot, block, level, n_boot, seed + k) for k in range(n_rep)]
    out = {k: v for k, v in reps[0].items() if k not in ("ci", "ci_percentile")}

    def agg(key):
        arr = np.array([[np.nan if b is None else b for b in r.get(key, (None, None))] for r in reps], dtype=float)
        if not np.isfinite(arr).all():
            return [None, None], [None, None]
        return [float(b) for b in arr.mean(axis=0)], [float(e) for e in arr.std(axis=0, ddof=1) / math.sqrt(n_rep)]

    out["ci"], out["ci_mc_se"] = agg("ci")
    out["ci_percentile"], out["ci_percentile_mc_se"] = agg("ci_percentile")
    out.update(block=int(block), n_rep=n_rep, n_boot_per_rep=int(n_boot), n_boot_total=int(n_boot) * n_rep,
               lower_by_replicate=[r["ci"][0] for r in reps])
    return out


def robust_exclusion(declared: dict, alternatives: dict, k_se: float = 2.0) -> tuple:
    """Decide 'the 95% CI excludes 0 on the positive side' so that neither the bootstrap seed nor an undeclared interval
    choice decides it. ``declared`` and each value of ``alternatives`` hold "ci" = [lo, hi] and "ci_mc_se" = [se_lo, se_hi]
    (Monte Carlo s.e. of the bounds). Returns (ok, decisive_fail, note):
      * (False, True)  the declared CI lies wholly below 0 beyond k_se Monte Carlo s.e. (a decisive failure);
      * (False, False) its lower bound is below 0 beyond k_se s.e. (the CI includes 0);
      * (None, False)  its lower bound is within k_se s.e. of 0 (the Monte Carlo error cannot resolve the sign), or it
                       excludes 0 while an alternative interval (percentile, other block lengths) does not: MARGINAL;
      * (True, False)  the declared and every alternative lower bound lie above 0 beyond k_se s.e."""
    lo, hi = declared.get("ci", (None, None))
    se_lo, se_hi = [e or 0.0 for e in declared.get("ci_mc_se", (None, None))]
    if lo is None or hi is None:
        return None, False, "the interval is not available"
    if hi < -k_se * se_hi:
        return False, True, "the declared CI lies wholly below 0"
    if lo < -k_se * se_lo:
        return False, False, "the declared CI includes 0"
    if lo <= k_se * se_lo:
        return None, False, (f"the declared lower bound {lo:+.4f} is within {k_se:g} Monte Carlo s.e. ({se_lo:.4f}) of 0: "
                             "the sign is not resolved")
    alt_in = [nm for nm, c in alternatives.items()
              if c.get("ci", (None, None))[0] is None
              or c["ci"][0] <= k_se * ((c.get("ci_mc_se") or (None, None))[0] or 0.0)]
    if alt_in:
        return None, False, ("MARGINAL: the declared interval excludes 0 but " + ", ".join(alt_in)
                             + " does not (the claim fixes no interval or block length)")
    return True, False, ""


def _sr_diff_and_se(a: np.ndarray, b: np.ndarray, bw: int):
    """Row-wise per-period Sharpe(a) - Sharpe(b) and its delta-method HAC s.e. (Ledoit and Wolf 2008)."""
    n = a.shape[1]
    mu_a, mu_b = a.mean(axis=1), b.mean(axis=1)
    g_a, g_b = (a * a).mean(axis=1), (b * b).mean(axis=1)
    va, vb = np.maximum(g_a - mu_a ** 2, 1e-300), np.maximum(g_b - mu_b ** 2, 1e-300)
    d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
    grad = (g_a / va ** 1.5, -g_b / vb ** 1.5, -mu_a / (2 * va ** 1.5), mu_b / (2 * vb ** 1.5))
    z = (grad[0][:, None] * (a - mu_a[:, None]) + grad[1][:, None] * (b - mu_b[:, None])
         + grad[2][:, None] * (a * a - g_a[:, None]) + grad[3][:, None] * (b * b - g_b[:, None]))
    return d, np.sqrt(_hac_var(z, bw) / n)


def sharpe_diff_test(a, b, block: int, n_boot: int = 2000, seed: int = 0) -> dict:
    """One-sided studentized circular block bootstrap of Sharpe(a) - Sharpe(b) on paired periods (H0: difference <= 0).
    Returns the per-period difference, its s.e., the p-value and a two-sided 95% CI."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = a.size
    if n < 8 or b.size != n:
        return {"diff": None, "se": None, "p": None, "ci": [None, None]}
    block = max(1, min(int(block), n // 4))
    d0, se0 = _sr_diff_and_se(a[None, :], b[None, :], block)
    d0, se0 = float(d0[0]), float(se0[0])
    if not se0 > 1e-150:
        return {"diff": d0, "se": 0.0, "p": 0.0 if d0 > 0 else 1.0, "ci": [d0, d0]}
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        d, se = _sr_diff_and_se(a[idx], b[idx], block)
        ok = se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
    t = np.concatenate(ts)
    t_obs = d0 / se0
    return {"diff": d0, "se": se0, "p": float((np.sum(t >= t_obs) + 1) / (t.size + 1)),
            "ci": [d0 - float(np.quantile(t, 0.975)) * se0, d0 - float(np.quantile(t, 0.025)) * se0]}


def _mdd_abs(pnl) -> np.ndarray:
    """Maximum drawdown (absolute, >= 0) of the additive equity curve cumsum(pnl) starting at 0, row-wise."""
    p = np.atleast_2d(np.asarray(pnl, dtype=float))
    eq = np.concatenate([np.zeros((p.shape[0], 1)), np.cumsum(p, axis=1)], axis=1)
    return (np.maximum.accumulate(eq, axis=1) - eq).max(axis=1)


def mdd_ratio_ci(pl_a, pl_b, block: int = 63, n_boot: int = 1000, seed: int = 0, level: float = 0.95) -> dict:
    """MDD(a) / MDD(b) of additive daily P&L paths, with a percentile CI over PAIRED circular block-bootstrap paths (the
    same day blocks for both books)."""
    a = np.asarray(pl_a, dtype=float)
    b = np.asarray(pl_b, dtype=float)
    n = a.size
    ma, mb = float(_mdd_abs(a)[0]), float(_mdd_abs(b)[0])
    out = {"n_days": int(n), "mdd_a": ma, "mdd_b": mb, "ratio": ma / mb if mb > 0 else None, "ci": [None, None]}
    if n < 8 * block // 4 or n < 8:
        return out
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    rs = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        da, db = _mdd_abs(a[idx]), _mdd_abs(b[idx])
        ok = db > 0
        rs.append(da[ok] / db[ok])
    r = np.concatenate(rs)
    if r.size:
        al = (1.0 - level) / 2.0
        out["ci"] = [float(np.quantile(r, al)), float(np.quantile(r, 1.0 - al))]
    return out


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (its
    interval wholly on the wrong side); otherwise it is reported as not decisive (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _ci_s(ci, nd: int = 2, scale: float = 1.0) -> str:
    lo, hi = ci
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


def _thirds(x) -> list:
    x = np.asarray(x, dtype=float)
    return [float(p.mean()) if p.size else None for p in np.array_split(x, 3)]


def _halves(x) -> list:
    x = np.asarray(x, dtype=float)
    h = x.size // 2
    return [float(x[:h].mean()) if h else None, float(x[h:].mean()) if x.size - h else None]


def _desc(x) -> dict:
    x = np.asarray(x, dtype=float)
    if x.size < 3:
        return {}
    return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)), "skew": float(skewness(x)), "kurtosis": float(kurtosis(x)),
            "min": float(x.min()), "max": float(x.max())}


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


# ============================================================== rule 10: entry calendars and grid phases ==

POOL_HOLDS = 6               # pooled overlapping series: block = 6 holds (126 days >= 2 x hold), the span of a 6-cycle block


def pool_block_len(hold: int = HOLD) -> int:
    """Block length (days) of the pooled overlapping daily-entry bootstrap: max(2 x hold, 6 x hold)."""
    return max(2 * int(hold), POOL_HOLDS * int(hold))


def n_holds(idx, hold: int = HOLD) -> int:
    """Distinct ``hold``-day holds spanned by sorted entry indices: the cycle count of the densest non-overlapping grid."""
    idx = np.asarray(idx, dtype=np.int64)
    return 0 if idx.size == 0 else int((idx[-1] - idx[0]) // hold + 1)


def phase_summary(rows: list, side: int = 1, key: str = "mean") -> dict:
    """min/max of the per-offset statistic and of its bounds, and how many offsets pass (row["ok"] True)."""
    good = [r for r in rows if r.get(key) is not None and r.get("ci", (None, None))[0] is not None]
    out = {"n_offsets": len(rows), "n_pass": int(sum(1 for r in rows if r.get("ok"))),
           "n_min": min((r["n"] for r in rows), default=0), "n_max": max((r["n"] for r in rows), default=0)}
    if not good:
        return out | {k: None for k in ("stat_min", "stat_max", "lower_min", "lower_max", "upper_min", "upper_max",
                                         "bound_min", "bound_max")}
    lows, ups = [r["ci"][0] for r in good], [r["ci"][1] for r in good]
    b = lows if side > 0 else ups
    return out | {"stat_min": min(r[key] for r in good), "stat_max": max(r[key] for r in good),
                  "lower_min": min(lows), "lower_max": max(lows), "upper_min": min(ups), "upper_max": max(ups),
                  "bound_min": min(b), "bound_max": max(b)}


def phase_scan(idx, x, hold: int = HOLD, block: int = 6, n_boot: int = 2000, seed: int = 0, side: int = 1,
               level: float = 0.95, pool_n_boot: Optional[int] = None) -> dict:
    """Rule 10(b) for a mean. ``idx``: sorted entry sessions (every valid daily entry); ``x``: the claimed per-entry
    statistic. Offset k is the non-overlapping grid idx % hold == k (studentized CI, block ``block`` cycles); the pooled
    estimate uses every entry (studentized circular block bootstrap, block ``pool_block_len(hold)`` days) and is the
    primary statistic. side +1: a pass is lower bound > 0; side -1: upper bound < 0."""
    idx = np.asarray(idx, dtype=np.int64)
    x = np.asarray(x, dtype=float)
    rows = []
    for k in range(hold):
        sel = idx % hold == k
        xk = x[sel]
        lo, hi = stud_ci(xk, block, level, n_boot, seed)
        ok = None if lo is None else (bool(lo > 0) if side > 0 else bool(hi < 0))
        rows.append({"offset": k, "n": int(sel.sum()), "mean": float(xk.mean()) if xk.size else None, "ci": [lo, hi],
                     "ok": ok})
    pb = pool_block_len(hold)
    lo, hi = stud_ci(x, pb, level, pool_n_boot or n_boot, seed)
    pooled = {"n_entries": int(x.size), "n": n_holds(idx, hold), "mean": float(x.mean()) if x.size else None,
              "ci": [lo, hi], "block_days": pb}
    return {"pooled": pooled, "offsets": rows, "summary": phase_summary(rows, side), "block_cycles": int(block),
            "hold": int(hold)}


def _scaled_summary(summary: dict, scale: float) -> dict:
    """A ``phase_summary`` with its statistic and bound fields multiplied by ``scale`` (counts unchanged)."""
    return {k: (v * scale if v is not None and not k.startswith("n_") else v) for k, v in summary.items()}


def _phase_txt(ps: dict, side: int = 1, nd: int = 2, scale: float = 1.0, what: str = "mean") -> str:
    """'per offset (...): mean a to b, lower bound c to d, k/21 offsets pass' for a ``phase_scan`` result."""
    s = ps["summary"]
    if s.get("stat_min") is None:
        return "per-offset grids not available"
    b = "lower" if side > 0 else "upper"
    return (f"per grid offset ({s['n_offsets']} non-overlapping grids, n {s['n_min']}-{s['n_max']}, block "
            f"{ps['block_cycles']} cycles): {what} {s['stat_min'] * scale:+.{nd}f} to {s['stat_max'] * scale:+.{nd}f}, "
            f"{b} bound {s['bound_min'] * scale:+.{nd}f} to {s['bound_max'] * scale:+.{nd}f}, {s['n_pass']}/{s['n_offsets']} "
            f"offsets pass")


def _pool_txt(ps: dict, nd: int = 2, scale: float = 1.0, unit: str = "") -> str:
    p = ps["pooled"]
    return (f"POOLED over all {ps['hold']} grid offsets ({p['n_entries']} overlapping daily entries = {p['n']} distinct "
            f"{ps['hold']}-day holds; studentized circular block bootstrap, block {p['block_days']} days): mean "
            f"{_s(p['mean'] and p['mean'] * scale, nd)}{unit} ({_ci_s(p['ci'], nd, scale)})")


def _ords(days) -> np.ndarray:
    return np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)


def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def _scheduled_sessions(days, targets) -> np.ndarray:
    """Session index of each scheduled date: the date itself, or the prior session when it is a holiday (dates outside the
    data, or with no session in the 4 days before, are skipped)."""
    if not len(days):
        return np.zeros(0, dtype=np.int64)
    o = _ords(days)
    out = set()
    for t in targets:
        to = t.toordinal()
        if to < o[0] or to > o[-1]:
            continue
        j = int(np.searchsorted(o, to, side="right") - 1)
        if j >= 0 and to - o[j] <= 4:
            out.add(j)
    return np.array(sorted(out), dtype=np.int64)


def monthly_expiry_idx(days) -> np.ndarray:
    """SPY's standard monthly expiries: the third Friday of each month, or the prior session on a holiday."""
    if not len(days):
        return np.zeros(0, dtype=np.int64)
    y0, y1 = int(days[0][:4]), int(days[-1][:4])
    return _scheduled_sessions(days, [_third_friday(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)])


def weekly_expiry_idx(days) -> np.ndarray:
    """Weekly expiries: every Friday, or the prior session on a holiday."""
    if not len(days):
        return np.zeros(0, dtype=np.int64)
    d0, d1 = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    f, fr = d0 + timedelta(days=(4 - d0.weekday()) % 7), []
    while f <= d1:
        fr.append(f)
        f += timedelta(days=7)
    return _scheduled_sessions(days, fr)


def quarterly_ex_mask(days) -> np.ndarray:
    """SPY's quarterly ex-dividend schedule: the third Friday of Mar/Jun/Sep/Dec, or the prior session on a holiday."""
    m = np.zeros(len(days), dtype=bool)
    if len(days):
        y0, y1 = int(days[0][:4]), int(days[-1][:4])
        m[_scheduled_sessions(days, [_third_friday(y, q) for y in range(y0, y1 + 1) for q in (3, 6, 9, 12)])] = True
    return m


def calendar_entries(days, expiries, dte: int, non_overlap: bool = False, ok=None) -> tuple:
    """(entries, expiries) for options of ``dte`` calendar days on an expiry calendar: each entry is the session nearest
    expiry - dte (ties to the earlier, longer-dated session); an expiry whose entry date lies more than 4 days from any
    session (before the data) is skipped. ``non_overlap``: an entry before the previous expiry moves to that expiry's
    close. ``ok`` (bool per session): an entry on a session without it (no VIX close) is skipped."""
    o = _ords(days)
    ent, exp, prev = [], [], None
    for e in np.asarray(expiries, dtype=np.int64):
        t = o[e] - dte
        j = int(np.searchsorted(o, t))
        cands = [k for k in (j - 1, j) if 0 <= k < o.size]
        k = min(cands, key=lambda c: (abs(int(o[c]) - t), o[c])) if cands else None
        if k is not None and abs(int(o[k]) - t) <= 4:
            if non_overlap and prev is not None and k < prev:
                k = int(prev)
            if k < e and (ok is None or bool(ok[k])):
                ent.append(k)
                exp.append(int(e))
        prev = int(e)
    return np.array(ent, dtype=np.int64), np.array(exp, dtype=np.int64)


def _month_first(days, ok=None, start: str = "") -> np.ndarray:
    """First session of each calendar month (on or after ``start``) where ``ok`` holds (a VIX close)."""
    out, seen = [], set()
    for i, d in enumerate(days):
        if d < start or d[:7] in seen or (ok is not None and not ok[i]):
            continue
        seen.add(d[:7])
        out.append(i)
    return np.array(out, dtype=np.int64)


def _month_last(days, ok=None, start: str = "") -> np.ndarray:
    """Last session of each calendar month (on or after ``start``) where ``ok`` holds."""
    by = {}
    for i, d in enumerate(days):
        if d >= start and (ok is None or ok[i]):
            by[d[:7]] = i
    return np.array(sorted(by.values()), dtype=np.int64)


def _fwd_rv(closes, idx, hold: int = HOLD) -> np.ndarray:
    """Annualised realised variance of the ``hold`` close-to-close log returns after each entry (returns a+1..a+hold);
    NaN when a close in the window is missing or the window runs past the data."""
    c = np.asarray(closes, dtype=float)
    lr2 = np.full(c.size, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        lr2[1:] = np.log(c[1:] / c[:-1]) ** 2
    cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(lr2, nan=0.0))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(lr2))])
    idx = np.asarray(idx, dtype=np.int64)
    out = np.full(idx.size, np.nan)
    ok = idx + hold < c.size
    a = idx[ok]
    s = cs[a + hold + 1] - cs[a + 1]
    nb = bad[a + hold + 1] - bad[a + 1]
    out[ok] = np.where(nb == 0, PPY / hold * s, np.nan)
    return out


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
    """Bundle names starting with ``prefix`` (index lookup only)."""
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if getattr(e, "name", "").startswith(prefix))


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str, filtered: bool = True) -> list:
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured (a bar still open)."""
    cap = getattr(archive.get(name), "created_at", None) if filtered else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        if c is None or not float(c) > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float(c))
    days = sorted(by)
    return days, np.array([by[d][0] for d in days], dtype=float), np.array([by[d][1] for d in days], dtype=float)


def _daily(archive, name: str) -> tuple:
    """(days, raw close, adjclose) of a daily-history bundle, bars not yet available at capture dropped."""
    return _daily_from_rows(_rows(archive, name))


def _index(archive, name: str, filtered: bool = True) -> dict:
    return index_closes(_rows(archive, name, filtered))


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED series, missing prints skipped."""
    out = {}
    for r in _rows(archive, name):
        v = r["value"]
        x = v.get("value", v.get("close"))
        try:
            x = float(x)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out[v["day"]] = x
    return out


def _smile(archive) -> Optional[Smile]:
    rows = [r for nm in _names(archive, SMILE_P) for r in archive.load(nm)]
    try:
        return Smile(rows) if rows else None
    except (KeyError, TypeError, ValueError):
        return None


# ================================================================================================= market data ==

def dtb3_continuous(d_pct: float) -> float:
    """Continuous rate from a 91-day discount yield in percent."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def bill_rates(days: Sequence[str], dtb3: dict) -> np.ndarray:
    """Continuous bill rate known at each day's close: the DTB3 print dated strictly before the day (FRED publishes a day
    late); before the first print, the first print."""
    ks = sorted(dtb3)
    if not ks:
        return np.zeros(len(days))
    vals = [dtb3_continuous(dtb3[k]) for k in ks]
    return np.array([vals[max(bisect_left(ks, d) - 1, 0)] for d in days], dtype=float)


def dividends(close, adj) -> np.ndarray:
    """Cash dividend going ex on each day (0 otherwise) from the adjclose/close ratio step: D = close[i-1](1 - f[i-1]/f[i])."""
    close = np.asarray(close, dtype=float)
    f = np.asarray(adj, dtype=float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if f[i] > f[i - 1] * (1 + 1e-5):
            d = close[i - 1] * (1.0 - f[i - 1] / f[i])
            if 0 < d < 0.05 * close[i - 1]:
                out[i] = d
    return out


def div_forecast(div) -> np.ndarray:
    """Point-in-time forecast of an upcoming dividend at each close: the last dividend gone ex at or before that day; 0
    before the first ex-date (no dividend is known yet, so an option entered then is priced on the spot)."""
    div = np.asarray(div, dtype=float)
    out = np.zeros(div.size)
    last = 0.0
    for i in range(div.size):
        if div[i] > 0:
            last = float(div[i])
        out[i] = last
    return out


def _ffill(v) -> tuple:
    """(forward-filled values, mask of real prints); leading gaps take the first print."""
    v = np.asarray(v, dtype=float)
    has = np.isfinite(v) & (v > 0)
    if not has.any():
        return v.copy(), has
    i = np.where(has, np.arange(v.size), -1)
    i = np.maximum.accumulate(i)
    i = np.where(i < 0, int(np.argmax(has)), i)
    return v[i], has


def make_frame(days, close, vix, rate=None, div=None, adj=None, sched=None) -> dict:
    """Aligned daily arrays for the option engines: ISO days, ordinal dates, raw close, adjclose, cash dividend by
    ex-day, its point-in-time forecast, the projected ex-dividend schedule (``quarterly_ex_mask`` unless given), VIX close
    (vol points; a missing print - NaN - is marked by ``has_vix`` False and carries the latest print for marking) and the
    continuous bill rate known at each close."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = np.zeros(close.size) if div is None else np.asarray(div, dtype=float)
    vff, has = _ffill(vix)
    return {"days": days, "ords": _ords(days), "close": close,
            "adj": close.copy() if adj is None else np.asarray(adj, dtype=float),
            "div": div, "fc": div_forecast(div), "vix": vff, "has_vix": has,
            "sched": quarterly_ex_mask(days) if sched is None else np.asarray(sched, dtype=bool),
            "rate": np.zeros(close.size) if rate is None else np.asarray(rate, dtype=float)}


def _spy_frame(archive) -> dict:
    """Every SPY session (raw close, adjclose, dividends) with the VIX close (NaN where VIX has none: no entry there) and
    the prior-print bill rate."""
    days, close, adj = _daily(archive, SPY_B)
    vix = _index(archive, VIX_B)
    dtb3 = _series(archive, DTB3_B)
    return make_frame(days, close, [vix.get(d, np.nan) for d in days], rate=bill_rates(days, dtb3),
                      div=dividends(close, adj), adj=adj)


def _pv_divs(ex, fc, tt, r) -> np.ndarray:
    """PV at each column j of the forecast dividends going ex at columns k > j of the same path (rows = positions)."""
    m, w = ex.shape
    out = np.zeros((m, w))
    if not ex.any():
        return out
    for j in range(w - 1):
        for k in range(j + 1, w):
            hit = ex[:, k]
            if hit.any():
                out[:, j] += np.where(hit, fc * np.exp(-r * (tt[:, k] - tt[:, j]) / 365.0), 0.0)
    return out


# ============================================================================================ straddle engine ==

def straddle_cycles(fr: dict, scale: float, side: int = -1, hold: int = HOLD, first: int = 0, hedge: bool = True,
                    hedge_every: int = 1, cost_bps: float = 0.0, vol_cost: float = 0.0, div_pricing: bool = True,
                    starts=None, ends=None, vix_lag: int = 0) -> dict:
    """ATM straddle cycles: entered at the close of session a (strike = that close), priced by Black-Scholes at
    sigma = scale * VIX / 100 on the dividend forward, expiring at the close of session e (raw close). Cycles are the
    non-overlapping grid a = first, first + hold, ... (e = a + hold) unless ``starts`` (and optionally ``ends``, for
    calendar cycles of varying length) are given; an entry without a VIX close (``has_vix``) is dropped. ``vix_lag`` = 1
    prices on the prior session's VIX close (a timing sensitivity). ``side`` +1 long, -1 short. With ``hedge`` the
    straddle delta (at the entry vol) is hedged at each close (every ``hedge_every`` days), 1 share = 1 unit;
    ``cost_bps`` is charged on the value of every share traded (opening, rebalancing and unwinding); ``vol_cost`` (vol,
    e.g. 0.005) is charged once as entry vega x vol_cost. P&L is the final value of a self-financing cash account
    (premium, hedge trades, dividends on hedge shares, interest at the entry bill rate) plus the payoff. Pricing projects
    ex-dates from ``fr["sched"]``; the hedge receives the actual dividend on the actual ex-date. ``rv``: total-return
    realised variance (what the hedge earns on); ``rv_px``: price-return (raw close) realised variance; ``var_term``: the
    gamma P&L 0.5 Gamma Sx^2 ((dSx/Sx)^2 - sigma^2 dt) on the dividend forward Sx, summed to expiry."""
    n = len(fr["days"])
    has = fr.get("has_vix", np.ones(n, dtype=bool))
    starts = np.arange(first, n - hold, hold) if starts is None else np.asarray(starts, dtype=np.int64)
    ends = starts + hold if ends is None else np.asarray(ends, dtype=np.int64)
    ok = (starts - vix_lag >= 0) & (ends < n) & (ends > starts)
    ok[ok] &= has[starts[ok] - vix_lag]
    starts, ends = starts[ok], ends[ok]
    keys = ("start", "end", "len", "pnl", "prem", "vega", "spot", "sig", "payoff", "rv", "rv_px", "var_term", "traded")
    if starts.size == 0:
        return {k: np.zeros(0) for k in keys} | {"day": []}
    m = starts.size
    L = ends - starts
    W = int(L.max())
    col = np.arange(W + 1)[None, :]
    live = col <= L[:, None]
    I = np.minimum(starts[:, None] + col, n - 1)
    S = fr["close"][I]
    tt = fr["ords"][I].astype(float)
    T = np.maximum(fr["ords"][ends].astype(float)[:, None] - tt, 0.0) / 365.0
    r = fr["rate"][starts]
    sig = np.maximum(scale * fr["vix"][starts - vix_lag] / 100.0, 0.01)
    K = S[:, 0].copy()
    D = np.where(live, fr["div"][I], 0.0)
    D[:, 0] = 0.0
    sched = fr.get("sched", fr["div"] > 0)
    ex = live & sched[I]
    ex[:, 0] = False
    pvd = _pv_divs(ex, fr["fc"][starts], tt, r) if div_pricing else np.zeros_like(S)
    Sx = S - pvd
    prem = bs.price(Sx[:, 0], K, T[:, 0], r, sig, "call") + bs.price(Sx[:, 0], K, T[:, 0], r, sig, "put")
    vega = 2.0 * bs.greeks(Sx[:, 0], K, T[:, 0], r, sig, "call")["vega"]
    rows = np.arange(m)
    payoff = np.abs(S[rows, L] - K)
    on = col[:, :W] < L[:, None]                                       # sessions with time left (hedged)
    g = bs.greeks(Sx[:, :W], K[:, None], np.where(on, T[:, :W], 1.0), r[:, None], sig[:, None], "call")
    gam = np.where(on, 2.0 * g["gamma"], 0.0)
    if hedge:
        delta = np.where(on, 2.0 * g["delta"] - 1.0, 0.0)              # call + put delta, q = 0 on the dividend forward
        if hedge_every > 1:
            delta = delta[:, (np.arange(W) // hedge_every) * hedge_every]
        h = -side * delta
    else:
        h = np.zeros((m, W))
    c = cost_bps / 1e4
    cash = -side * prem - h[:, 0] * S[:, 0] - c * np.abs(h[:, 0]) * S[:, 0]
    traded = np.abs(h[:, 0]).copy()
    for j in range(W):
        act = j < L
        dt = (tt[:, j + 1] - tt[:, j]) / 365.0
        cash = np.where(act, cash * np.exp(r * dt) + h[:, j] * D[:, j + 1], cash)
        if j + 1 < W:
            mid = (j + 1) < L
            dh = h[:, j + 1] - h[:, j]
            cash = np.where(mid, cash - dh * S[:, j + 1] - c * np.abs(dh) * S[:, j + 1], cash)
            traded = traded + np.where(mid, np.abs(dh), 0.0)
        fin = (j + 1) == L
        cash = np.where(fin, cash + h[:, j] * S[:, j + 1] - c * np.abs(h[:, j]) * S[:, j + 1], cash)
        traded = traded + np.where(fin, np.abs(h[:, j]), 0.0)
    pnl = cash + side * payoff - vol_cost * vega
    ret_on = col[:, 1:] <= L[:, None]                                  # returns 1..L
    lg = np.where(ret_on, np.log((S[:, 1:] + D[:, 1:]) / S[:, :-1]), 0.0)
    lp = np.where(ret_on, np.log(S[:, 1:] / S[:, :-1]), 0.0)
    rv = PPY / L * np.sum(lg ** 2, axis=1)
    rv_px = PPY / L * np.sum(lp ** 2, axis=1)
    dtm = (tt[:, 1:] - tt[:, :-1]) / 365.0
    rx = Sx[:, 1:] / Sx[:, :-1] - 1.0
    var_term = side * np.sum(np.where(on, 0.5 * gam * Sx[:, :W] ** 2 * (rx ** 2 - sig[:, None] ** 2 * dtm), 0.0), axis=1)
    return {"start": starts, "end": ends, "len": L, "day": [fr["days"][a] for a in starts], "pnl": pnl, "prem": prem,
            "vega": vega, "spot": K, "sig": sig, "payoff": payoff, "rv": rv, "rv_px": rv_px, "var_term": var_term,
            "traded": traded}


def trailing_rv_vol(logret_end: np.ndarray, idx, window: int = HOLD) -> np.ndarray:
    """Annualised realised vol of the ``window`` log returns ending at each close in ``idx`` (logret_end[k] = ln C_k/C_{k-1})."""
    out = np.full(len(idx), np.nan)
    for i, a in enumerate(idx):
        if a - window + 1 >= 1:
            seg = logret_end[a - window + 1:a + 1]
            out[i] = math.sqrt(PPY / window * float(np.sum(seg ** 2)))
    return out


def _logret_end(c) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    out = np.full(c.size, np.nan)
    out[1:] = np.log(c[1:] / c[:-1])
    return out


# ================================================================================ T-101 tercile short straddle ==

def tercile_oos(signal, x_by_scale: dict, n_pre: int, n_splits: int = 5, block: int = 6, n_boot: int = 2000, seed: int = 0,
                min_train_fallback: int = 60, min_pre: int = 24) -> dict:
    """Walk-forward tercile test. ``signal`` lists every entry in time order: ``n_pre`` training-only entries first (no
    P&L), then the P&L entries that ``x_by_scale[s]`` covers. Splits come from ``walk_forward_splits`` with min_train =
    n_pre (or ``min_train_fallback`` P&L entries when n_pre < ``min_pre``); in each split the 1/3 and 2/3 quantiles of the
    training window's signal label the test window (top: above the 2/3 cut; bottom: at or below the 1/3 cut). The pooled
    out-of-sample top-minus-bottom difference of mean x gets a studentized block-bootstrap CI per scale. Entries may be
    cycles (block in cycles) or overlapping daily entries (block in days, thresholds in days)."""
    signal = np.asarray(signal, dtype=float)
    n_all = signal.size
    min_train = n_pre if n_pre >= min_pre else max(n_pre, min_train_fallback)
    label = np.full(n_all, -1)
    cuts = []
    for tr, te in walk_forward_splits(n_all, n_splits, min_train):
        lo, hi = np.quantile(signal[tr], [1 / 3, 2 / 3])
        cuts.append([float(lo), float(hi)])
        label[te] = np.where(signal[te] > hi, 2, np.where(signal[te] <= lo, 0, 1))
    oos = np.nonzero(label >= 0)[0]
    pi = oos - n_pre
    top, bot = label[oos] == 2, label[oos] == 0
    res = {}
    for s, x in x_by_scale.items():
        xs = np.asarray(x, dtype=float)[pi]
        res[s] = stud_ci_group_diff(xs, top, bot, block, 0.95, n_boot, seed)
        res[s]["mean_middle"] = float(xs[label[oos] == 1].mean()) if (label[oos] == 1).any() else None
    return {"n_oos": int(oos.size), "n_pre": int(n_pre), "min_train": int(min_train), "n_splits": n_splits, "cuts": cuts,
            "by_scale": res, "oos_index": pi, "top": top, "bottom": bot}


T101_MIN_TRAIN = 60          # SPY cycles in the first walk-forward training window (5 years of monthly cycles)


def _t101_offsets(sig, x: dict, ent, scales, main, hold, n_splits, block, n_boot, seed, min_train) -> list:
    """T-101 on each non-overlapping grid offset (entries ent % hold == k): walk-forward terciles in cycles, studentized
    block-``block`` CI of the s = main difference; a pass is lower bound > 0 with the same sign at the other scales."""
    rows = []
    for k in range(hold):
        sel = np.asarray(ent) % hold == k
        try:
            tk = tercile_oos(sig[sel], {s: x[s][sel] for s in scales}, 0, n_splits, block, n_boot, seed,
                             min_train_fallback=min_train)
        except ValueError:
            rows.append({"offset": k, "n": 0, "diff": None, "ci": [None, None], "ok": None})
            continue
        ms = tk["by_scale"][main]
        same = all(tk["by_scale"][s]["diff"] is not None and tk["by_scale"][s]["diff"] > 0 for s in scales if s != main)
        ok = None if ms["ci"][0] is None else bool(ms["ci"][0] > 0 and same)
        ts = x[main][sel][tk["oos_index"]][tk["top"]]
        rows.append({"offset": k, "n": tk["n_oos"], "diff": ms["diff"], "ci": ms["ci"], "ok": ok,
                     "diff_by_scale": {str(s): tk["by_scale"][s]["diff"] for s in scales},
                     "dsr_top_tercile_n_trials_3": float(deflated_sharpe_ratio(ts, 3)) if ts.size > 3 else None})
    return rows


def straddle_tercile(fr: dict, pre_sensitivity=None, scales=(0.81, 0.90, 1.00), main: float = 0.90, n_splits: int = 5,
                     block: int = 6, n_boot: int = 5000, n_rep: int = 10, seed: int = 0, alt_blocks=(2, 3, 12),
                     haircut: float = 0.05, min_n: int = 390, min_train: int = T101_MIN_TRAIN,
                     sensitivity_note: str = "", offset_n_boot: int = 1000, hold: int = HOLD) -> dict:
    """T-101: short 30-DTE ATM SPY straddles at BS(s * VIX/100); mean P&L / premium, top minus bottom tercile of VIX - RV21
    (RV21 from SPY log returns) at entry, cut-points from walk-forward training windows of SPY entries only, applied out
    of sample. Pass: CI excludes 0 at s = 0.90 (on the claimed side, top higher) and the same sign at s = 0.81 and 1.00;
    min_n 390 counted in out-of-sample SPY cycles (distinct 21-day holds).

    Rule 10(b): the claim names no entry calendar, so the primary statistic pools all 21 grid offsets: every SPY session
    with a VIX close and a trailing RV21 is an entry (overlapping), the walk-forward runs on that daily sequence (first
    training window = ``min_train`` cycles x 21 sessions) and the s = 0.90 interval is the studentized circular block
    bootstrap with blocks of ``block`` holds (126 days), averaged over ``n_rep`` replicates of ``n_boot`` draws with its
    Monte Carlo s.e. ``robust_exclusion`` passes it only when its lower bound clears 0 by 2 Monte Carlo s.e. and the
    percentile interval and the studentized intervals at ``alt_blocks`` holds clear 0 too (the claim fixes no block
    length). Each of the 21 non-overlapping grids is reported (difference, lower bound, how many pass).

    ``pre_sensitivity``: daily signals of training-only entries before the first SPY entry (e.g. ^GSPC RV21 before SPY
    listed). They never enter the verdict or n; they feed a labelled sensitivity in which they form the first training
    window."""
    n_days = len(fr["days"])
    res = {s: straddle_cycles(fr, s, side=-1, hedge=False, starts=np.arange(hold, max(hold, n_days - hold))) for s in scales}
    ent = res[scales[0]]["start"]
    n_all = n_holds(ent, hold)
    if n_all < min_train + n_splits:
        return {"verdict": "inconclusive", "n": 0,
                "reason": f"only {n_all} distinct 21-day holds of SPY entries: too few for a {min_train}-cycle first "
                          f"training window and {n_splits} walk-forward test windows — not implemented: n >= trial min_n "
                          f"(0 of {min_n} out-of-sample SPY cycles)"}
    sig = fr["vix"][ent] - 100.0 * trailing_rv_vol(_logret_end(fr["adj"]), ent)
    x = {s: res[s]["pnl"] / res[s]["prem"] for s in scales}
    pb = block * hold
    t = tercile_oos(sig, x, 0, n_splits, pb, n_boot, seed, min_train_fallback=min_train * hold, min_pre=24 * hold)
    oi, top, bot = t["oos_index"], t["top"], t["bottom"]
    oos_ent = ent[oi]
    n = n_holds(oos_ent, hold)
    xo = x[main][oi]
    m = mc_group_ci(xo, top, bot, pb, 0.95, n_boot, n_rep, seed)
    m["mean_middle"] = t["by_scale"][main].get("mean_middle")
    t["by_scale"][main] = m
    n_alt_rep = max(2, n_rep // 2)
    alt_bl = sorted({max(2, int(b)) for b in alt_blocks} - {int(block)})
    alts = {"the percentile interval": {"ci": m["ci_percentile"], "ci_mc_se": m["ci_percentile_mc_se"]}}
    for b in alt_bl:
        alts[f"studentized block {b * hold} days"] = mc_group_ci(xo, top, bot, b * hold, 0.95, n_boot, n_alt_rep, seed)
    ok, dec, note = robust_exclusion(m, alts)
    lo, hi = m["ci"]
    crit = [(f"s={main:.2f}: pooled OOS top-bottom > 0 with 95% CI excluding 0 (declared studentized block {pb} days, "
             f"robust to the seed and the block)" + (f" [not decided: {note}]" if ok is None else ""), ok, dec)]
    for s in scales:
        if s == main:
            continue
        ms = t["by_scale"][s]
        crit.append((f"s={s:.2f}: same sign (pooled top-bottom > 0)", None if ms["diff"] is None else bool(ms["diff"] > 0),
                     ms["ci"][1] is not None and ms["ci"][1] < 0))
    offs = _t101_offsets(sig, x, ent, scales, main, hold, n_splits, block, offset_n_boot, seed, min_train)
    osum = phase_summary(offs, 1, key="diff")
    parts = []
    for s in scales:
        ms = t["by_scale"][s]
        parts.append(f"s={s:.2f}: top {_s(ms['mean_top'] and ms['mean_top'] * 100, 1)}% vs bottom "
                     f"{_s(ms['mean_bottom'] and ms['mean_bottom'] * 100, 1)}% of premium, diff "
                     f"{_s(ms['diff'] and ms['diff'] * 100, 1)} pts ({_ci_s(ms['ci'], 1, 100)}; entries top/bottom "
                     f"{ms['n_top']}/{ms['n_bottom']})")
    se_lo = m["ci_mc_se"][0]
    parts.append(f"s={main:.2f} declared interval: studentized block {pb} days, mean of {m['n_rep']} replicates x {n_boot} "
                 f"draws, lower bound {_s(lo and lo * 100, 2)} pts (Monte Carlo s.e. {_f(se_lo and se_lo * 100, 2)}); "
                 f"alternatives' lower bounds ({n_alt_rep} replicates each): "
                 + ", ".join(f"{k.replace('the ', '').replace('studentized ', '')} {_s(c['ci'][0] and c['ci'][0] * 100, 2)}"
                             for k, c in alts.items())
                 + (f"; {note}" if note else ""))
    if osum.get("stat_min") is not None:
        parts.append(f"per grid offset ({osum['n_offsets']} non-overlapping grids, {osum['n_min']}-{osum['n_max']} OOS "
                     f"cycles, block {block} cycles, {offset_n_boot} draws): s={main:.2f} diff {osum['stat_min'] * 100:+.1f} "
                     f"to {osum['stat_max'] * 100:+.1f} pts, lower bound {osum['lower_min'] * 100:+.1f} to "
                     f"{osum['lower_max'] * 100:+.1f}, {osum['n_pass']}/{osum['n_offsets']} offsets pass")
    sens = None
    pre = np.asarray([] if pre_sensitivity is None else pre_sensitivity, dtype=float)
    if pre.size:
        try:
            ts = tercile_oos(np.concatenate([pre, sig]), {main: x[main]}, pre.size, n_splits, pb, n_boot, seed,
                             min_train_fallback=min_train * hold, min_pre=24 * hold)
            mss = mc_group_ci(x[main][ts["oos_index"]], ts["top"], ts["bottom"], pb, 0.95, n_boot, n_alt_rep, seed)
            n_s = n_holds(ent[ts["oos_index"]], hold)
            sens = {"label": "SENSITIVITY, not in the verdict or n", "n_pre_training_entries": int(pre.size),
                    "n_oos": n_s, "n_oos_entries": int(ts["n_oos"]), "min_train_entries": ts["min_train"],
                    "diff": mss["diff"], "ci": mss["ci"], "ci_mc_se": mss["ci_mc_se"],
                    "ci_percentile": mss["ci_percentile"], "note": sensitivity_note.strip(" ;()")}
            parts.append(f"SENSITIVITY, not in the verdict or n{sensitivity_note}: {n_s} OOS cycles ({ts['n_oos']} entries), "
                         f"s={main:.2f} diff {_s(mss['diff'] and mss['diff'] * 100, 1)} pts ({_ci_s(mss['ci'], 2, 100)}, "
                         f"percentile {_ci_s(mss['ci_percentile'], 2, 100)})")
        except ValueError:
            pass
    # reported controls (the pooled marginal distribution; Sharpe-type and drawdown figures on the non-overlapping grids)
    xm = x[main]
    uncond = {s: {"mean": float(x[s].mean()), "ci": list(stud_ci(x[s], pb, 0.95, min(n_boot, 2000), seed))} for s in scales}
    spot_pnl = res[main]["pnl"] / res[main]["spot"]
    psr = [float(deflated_sharpe_ratio(xm[ent % hold == k], 1)) for k in range(hold) if (ent % hold == k).sum() > 3]
    mdd = [float(_mdd_abs(spot_pnl[ent % hold == k])[0] * 100) for k in range(hold) if (ent % hold == k).any()]
    dsr = [r["dsr_top_tercile_n_trials_3"] for r in offs if r.get("dsr_top_tercile_n_trials_3") is not None]
    extras = {"unconditional": uncond, "s_main_desc": _desc(xm),
              "psr_by_offset_range": [min(psr), max(psr)] if psr else None,
              "dsr_top_tercile_n_trials_3_by_offset_range": [min(dsr), max(dsr)] if dsr else None,
              "max_drawdown_pct_of_spot_by_offset_range": [min(mdd), max(mdd)] if mdd else None,
              "haircut_5pct": {"mean_top": None if m["mean_top"] is None else m["mean_top"] - haircut,
                               "mean_bottom": None if m["mean_bottom"] is None else m["mean_bottom"] - haircut,
                               "diff": m["diff"], "note": "a constant per-premium haircut leaves the tercile difference unchanged"}}
    hc = extras["haircut_5pct"]
    parts.append(f"5%-of-premium round-trip haircut: top {_s(hc['mean_top'] and hc['mean_top'] * 100, 1)}% vs bottom "
                 f"{_s(hc['mean_bottom'] and hc['mean_bottom'] * 100, 1)}% (difference unchanged)")
    pr = extras["psr_by_offset_range"] or [float("nan")] * 2
    md = extras["max_drawdown_pct_of_spot_by_offset_range"] or [float("nan")] * 2
    ds = extras["dsr_top_tercile_n_trials_3_by_offset_range"] or [float("nan")] * 2
    parts.append(f"unconditional mean at s={main:.2f} {xm.mean() * 100:+.1f}% of premium (pooled, "
                 f"{_ci_s(uncond[main]['ci'], 1, 100)}), skew {extras['s_main_desc'].get('skew', float('nan')):.2f}, kurtosis "
                 f"{extras['s_main_desc'].get('kurtosis', float('nan')):.1f}; across the {hold} grids PSR {pr[0]:.2f}-{pr[1]:.2f}, "
                 f"max drawdown {md[0]:.1f}-{md[1]:.1f}% of spot, DSR(top tercile, 3 trials) {ds[0]:.2f}-{ds[1]:.2f}")
    unit = "out-of-sample SPY cycles (distinct 21-day holds of the pooled entries)"
    if n < min_n:
        unit += (f"; the {min_n - n} missing cycles need SPY history before {fr['days'][0]} (the first archived SPY day) or "
                 f"about {(min_n - n) * HOLD / PPY:.1f} more years of SPY cycles")
    verdict, why = _decide(crit, n, min_n, unit)
    reason = (f"{MP} short 30-DTE ATM SPY straddle at s x VIX on the dividend forward, settled on raw closes; rule 10 (no "
              f"entry calendar in the claim): POOLED over all {hold} grid offsets, {oi.size} overlapping out-of-sample daily "
              f"entries = {n} OOS cycles of {n_all} ({t['n_splits']} walk-forward test windows; cut-points on the training "
              f"window's VIX - RV21 from SPY log returns, SPY entries only, the first {min_train} cycles ({t['min_train']} "
              f"entries) train the first cut-points; min_n counts out-of-sample cycles, the sample the pass statistic is "
              f"computed on): " + "; ".join(parts)
              + f"; the tercile spread is model-priced (IV level only scales premium; {TRADED_NOTE})" + f" — {why}")
    stat = {"model_priced": True, "rule10": "pooled all-offset estimate (no calendar in the claim)", "n_oos_cycles": n,
            "n_oos_entries": int(oi.size), "min_n_unit": "out-of-sample SPY cycles", "n_spy_cycles": n_all,
            "n_spy_entries": int(ent.size), "min_train": int(min_train), "min_train_entries": int(t["min_train"]),
            "cuts_by_split": t["cuts"], "n_boot_per_rep": n_boot, "n_rep": m["n_rep"], "block_days": pb,
            "main_criterion": {"ok": ok, "decisive_fail": dec, "note": note},
            "alternative_intervals": {k: {"ci": c["ci"], "ci_mc_se": c.get("ci_mc_se")} for k, c in alts.items()},
            "by_scale": {str(s): {k: v for k, v in t["by_scale"][s].items()} for s in scales}, **extras,
            "offsets": offs, "offsets_summary": osum, "gspc_pre_window_sensitivity": sens,
            "first_entry": fr["days"][ent[0]], "first_oos_entry": fr["days"][oos_ent[0]], "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ============================================================================== T-123 gamma scalping long straddle ==

BTZ_VRP = 18.3               # BTZ (2009, RFS) summary statistics: mean VIX^2 - RV (5-minute), monthly %^2, about 18


def _flip_scale(fr: dict, grid, cost_bps: float, starts=None) -> Optional[float]:
    """Smallest s on ``grid`` where mean hedged long-straddle P&L/vega crosses from positive to negative (interpolated),
    over the entries ``starts`` (the pooled daily entries) or the offset-0 grid."""
    ms = []
    for s in grid:
        r = straddle_cycles(fr, s, side=1, hedge=True, cost_bps=cost_bps, starts=starts)
        ms.append(float(np.mean(r["pnl"] / r["vega"])) if r["pnl"].size else float("nan"))
    for i in range(len(grid) - 1):
        a, b = ms[i], ms[i + 1]
        if math.isfinite(a) and math.isfinite(b) and a >= 0 > b:
            return float(grid[i] + (grid[i + 1] - grid[i]) * a / (a - b))
    return None


def vrp_anchor(days, closes, vix, start: str = "1990-01-01", end: str = "2007-12-31", hold: int = HOLD) -> Optional[dict]:
    """Mean (VIX^2 - RV21)/12 in %^2 per month (close-to-close price returns) over every daily entry in [start, end]
    (pooled over the grid offsets), with the per-offset range."""
    days = list(days)
    c = np.asarray(closes, dtype=float)
    v = np.asarray(vix, dtype=float)
    ent = np.array([i for i, d in enumerate(days) if start <= d <= end and np.isfinite(v[i]) and v[i] > 0], dtype=np.int64)
    if ent.size == 0:
        return None
    rv = _fwd_rv(c, ent, hold)
    ok = np.isfinite(rv)
    ent, rv = ent[ok], rv[ok]
    if ent.size < hold:
        return None
    x = (v[ent] ** 2 - rv * 1e4) / 12.0
    ph = [float(x[ent % hold == k].mean()) for k in range(hold) if (ent % hold == k).any()]
    return {"n_entries": int(ent.size), "n_cycles": n_holds(ent, hold), "first": days[ent[0]], "last": days[ent[-1]],
            "mean": float(x.mean()), "offset_min": min(ph), "offset_max": max(ph)}


def gamma_scalp(fr: dict, scales=(0.81, 0.90, 1.00), main: float = 0.90, cost_bps: float = 1.0, block: int = 6,
                n_boot: int = 2000, seed: int = 0, flip_grid=None, min_n: int = 390, anchor: Optional[dict] = None,
                hold: int = HOLD) -> dict:
    """T-123: long 30-DTE ATM SPY straddle bought at BS(s * VIX), delta-hedged at each close at the entry vol, 1 bp per share
    traded; mean P&L / vega. Pass: upper 95% CI < 0 at s = 0.90; min_n 390 cycles.

    Rule 10(b): the claim names no entry calendar, so the criterion is judged on the POOLED estimate over all 21 grid
    offsets (every SPY session with a VIX close is an entry; studentized circular block bootstrap, 126-day blocks); each
    non-overlapping grid is reported. n = distinct 21-day holds spanned. Secondary (as worded): corr(P&L, RV21 -
    (s VIX)^2) with RV21 from raw-close price returns, in dollars and per unit vega. Controls: q = 0 (spot, no dividend
    forward) and prior-day VIX (the 16:15 vs 16:00 close) with their CIs; the variance-term share of P&L; the BTZ
    anchor on ``anchor`` = {"days", "close", "vix", "label"} (^GSPC 1990-2007 as the control words it)."""
    n_days = len(fr["days"])
    cand = np.arange(0, max(0, n_days - hold))
    res = {s: straddle_cycles(fr, s, side=1, hedge=True, cost_bps=cost_bps, starts=cand) for s in scales}
    rm = res[main]
    ent = rm["start"]
    n = n_holds(ent, hold)
    if ent.size < 8 * hold:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {ent.size} daily entries ({n} cycles)"}
    pb = pool_block_len(hold)
    by, scans = {}, {}
    for s in scales:
        r = res[s]
        y = r["pnl"] / r["vega"]
        ps = phase_scan(r["start"], y, hold, block, n_boot, seed, side=-1)
        scans[s] = ps
        excess = r["rv_px"] - r["sig"] ** 2
        lo, hi = ps["pooled"]["ci"]
        by[s] = {"mean_vol_pts": float(y.mean() * 100), "ci_vol_pts": [None if lo is None else lo * 100, None if hi is None else hi * 100],
                 "offsets_summary_vol_pts": _scaled_summary(ps["summary"], 100.0),
                 "corr_pnl_usd_rv_minus_implied_var": float(np.corrcoef(r["pnl"], excess)[0, 1]),
                 "corr_pnl_per_vega_rv_minus_implied_var": float(np.corrcoef(y, excess)[0, 1]),
                 "mean_var_term_per_vega_vol_pts": float(np.mean(r["var_term"] / r["vega"]) * 100),
                 "mean_hedge_error_per_vega_vol_pts": float(np.mean((r["pnl"] - r["var_term"]) / r["vega"]) * 100),
                 "var_term_share_of_pnl": float(np.sum(r["var_term"]) / np.sum(r["pnl"])) if np.sum(r["pnl"]) != 0 else None,
                 "mean_shares_traded_per_cycle": float(r["traded"].mean()), "desc": _desc(y * 100),
                 "thirds_vol_pts": [v * 100 for v in _thirds(y)]}
    m = by[main]
    lo, hi = m["ci_vol_pts"]
    crit = [(f"s={main:.2f}: upper 95% CI of mean P&L/vega < 0 (pooled over the {hold} grid offsets)",
             None if hi is None else bool(hi < 0), lo is not None and lo > 0)]

    def pooled_ctl(r):
        y = r["pnl"] / r["vega"]
        a, b = stud_ci(y, pb, 0.95, n_boot, seed)
        return {"n_entries": int(y.size), "mean_vol_pts": float(y.mean() * 100),
                "ci_vol_pts": [None if a is None else a * 100, None if b is None else b * 100]}

    q0 = pooled_ctl(straddle_cycles(fr, main, side=1, hedge=True, cost_bps=cost_bps, div_pricing=False, starts=cand))
    lag = pooled_ctl(straddle_cycles(fr, main, side=1, hedge=True, cost_bps=cost_bps, starts=cand, vix_lag=1))
    grid = np.round(np.arange(0.50, 1.301, 0.02), 2) if flip_grid is None else np.asarray(flip_grid, dtype=float)
    flip = _flip_scale(fr, grid, cost_bps, starts=cand)
    btz = None
    if anchor is not None:
        btz = vrp_anchor(anchor["days"], anchor["close"], anchor["vix"], hold=hold)
        if btz is not None:
            btz["source"] = anchor.get("label", "")
    if btz is None:                                     # fall back to SPY entries to 2007
        sel = np.array([d <= "2007-12-31" for d in rm["day"]])
        if sel.any():
            xb = ((rm["sig"][sel] / main) ** 2 - rm["rv_px"][sel]) * 1e4 / 12.0
            btz = {"source": "SPY", "n_entries": int(sel.sum()), "n_cycles": n_holds(ent[sel], hold),
                   "first": rm["day"][int(np.argmax(sel))], "last": "2007-12-31", "mean": float(xb.mean()),
                   "offset_min": None, "offset_max": None}
    parts = [_pool_txt(scans[main], 2, 100, " vol pts per unit vega") + f" at s={main:.2f}",
             _phase_txt(scans[main], -1, 2, 100)]
    parts += [f"s={s:.2f}: pooled mean {by[s]['mean_vol_pts']:+.2f} ({_ci_s(by[s]['ci_vol_pts'])}), "
              f"{scans[s]['summary']['n_pass']}/{hold} offsets with upper bound < 0" for s in scales if s != main]
    parts.append("secondary corr(P&L, RV21 - (s VIX)^2), RV21 from raw-close price returns: "
                 + ", ".join(f"s={s:.2f} {by[s]['corr_pnl_usd_rv_minus_implied_var']:.2f} in $ "
                             f"({by[s]['corr_pnl_per_vega_rv_minus_implied_var']:.2f} per unit vega)" for s in scales))
    vs = m["var_term_share_of_pnl"]
    parts.append(f"variance term (0.5 Gamma Sx^2 ((dSx/Sx)^2 - sigma^2 dt) on the dividend forward) "
                 f"{m['mean_var_term_per_vega_vol_pts']:+.2f} vs hedging error and costs {m['mean_hedge_error_per_vega_vol_pts']:+.2f} "
                 f"vol pts per vega at s={main:.2f}: variance-term share of summed P&L {_f(vs, 2)}")
    parts.append(f"sign flips at s = {_f(flip, 3) if flip is not None else 'none on ' + str(grid[0]) + '-' + str(grid[-1])} "
                 f"(pooled entries)")
    parts.append(f"q=0 control (spot, no dividend forward) {q0['mean_vol_pts']:+.2f} ({_ci_s(q0['ci_vol_pts'])}); "
                 f"prior-day VIX close (VIX closes 16:15 ET, SPY 16:00) {lag['mean_vol_pts']:+.2f} ({_ci_s(lag['ci_vol_pts'])})")
    if btz is not None:
        rng_txt = ("" if btz.get("offset_min") is None else
                   f", grid offsets {btz['offset_min']:+.1f} to {btz['offset_max']:+.1f}")
        parts.append(f"BTZ anchor (monthly %^2): mean (VIX^2 - RV21)/12 on {btz['source']} close-to-close price returns, "
                     f"{btz['n_entries']} daily entries {btz['first']}..{btz['last']} ({btz['n_cycles']} cycles) "
                     f"{btz['mean']:+.1f}{rng_txt}, vs BTZ's published mean VRP of about {BTZ_VRP:.0f} (VIX^2 minus the realised "
                     f"variance of the month just ended from 5-minute returns inside the trading day: it leaves out the "
                     f"overnight return, so its RV is lower and its VRP higher than a close-to-close one)")
    unit = f"cycles (distinct {hold}-day holds of the pooled entries)"
    verdict, why = _decide(crit, n, min_n, unit)
    reason = (f"{MP} long 30-DTE ATM SPY straddle at s x VIX, delta-hedged daily at the entry vol on raw closes, ex-dates "
              f"projected from SPY's quarterly schedule, 1 bp per share traded, cash at the bill rate; rule 10 (no entry "
              f"calendar in the claim): {ent.size} daily entries {rm['day'][0]}..{rm['day'][-1]} = {n} cycles: "
              + "; ".join(parts) + f" — {why}")
    stat = {"model_priced": True, "rule10": "pooled all-offset estimate (no calendar in the claim)", "n_cycles": n,
            "n_entries": int(ent.size), "block_days": pb, "cost_bps_per_share": cost_bps,
            "by_scale": {str(s): by[s] for s in scales}, "offsets_main": scans[main]["offsets"],
            "sign_flip_scale": flip, "flip_grid": [float(grid[0]), float(grid[-1])], "q0_control": q0,
            "prior_day_vix_control": lag, "btz_anchor": btz, "btz_published_vrp": BTZ_VRP,
            "first_entry": rm["day"][0], "last_entry": rm["day"][-1], "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ========================================================================= T-233 hedged short straddle (VRP) ==

def spy_monthly_cycles(fr: dict, dte: int = 30, non_overlap: bool = True) -> tuple:
    """(entries, expiries) of ``dte``-DTE options on SPY's standard monthly expiry calendar (rule 10(a)): expiry on the
    third Friday (prior session on a holiday), entry at the session nearest dte calendar days before it with a VIX close;
    with ``non_overlap`` an entry before the previous expiry moves to that expiry's close."""
    return calendar_entries(fr["days"], monthly_expiry_idx(fr["days"]), dte, non_overlap, ok=fr.get("has_vix"))


def vrp_hedged_short(fr: dict, measured_scale: Optional[float], measured_note: str = "", main: float = 0.81,
                     vol_cost: float = 0.005, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300,
                     cycles: Optional[tuple] = None, dte: int = 30) -> dict:
    """T-233: short 30-DTE ATM SPY straddle at ATM IV = s x VIX, delta-hedged at each close, 0.5 vol-point round trip charged
    as entry vega x 0.005; mean cycle P&L / premium. Pass: mean > 0 with the 95% CI excluding 0 at s = 0.81 and at the
    scale measured on the capture; deflated Sharpe p < 0.05 (DSR > 0.95) over the IV scales and hedge frequencies tried;
    positive in all three thirds; min_n 300 cycles.

    Rule 10(a): 'per monthly cycle' of a 30-DTE option names SPY's monthly expiry calendar, so each cycle sells the
    straddle expiring on a monthly expiry, entered at the session nearest 30 calendar days before it and never before the
    previous expiry (cycles do not overlap: 28-30 DTE). ``cycles`` = (entries, expiries) overrides the calendar. The
    pooled 21-day-grid estimate at s = 0.81 is reported as a cross-check (not in the verdict)."""
    st, en = spy_monthly_cycles(fr, dte, True) if cycles is None else (np.asarray(cycles[0]), np.asarray(cycles[1]))
    scales = [main] + ([measured_scale] if measured_scale is not None else [])
    variants = {}
    for s in sorted(set([1.0, 0.9, main] + ([round(measured_scale, 4)] if measured_scale is not None else []))):
        for he in (1, 5):
            r = straddle_cycles(fr, s, side=-1, hedge=True, hedge_every=he, vol_cost=vol_cost, starts=st, ends=en)
            variants[(s, he)] = r["pnl"] / r["prem"] if r["pnl"].size else np.zeros(0)
    base = straddle_cycles(fr, main, side=-1, hedge=True, vol_cost=vol_cost, starts=st, ends=en)
    n = int(base["pnl"].size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} monthly-expiry cycles"}
    crit, parts, by = [], [], {}
    for j, s in enumerate(scales):
        y = variants[(round(s, 4) if j == 1 else s, 1)]
        lo, hi = stud_ci(y, block, 0.95, n_boot, seed)
        th = _thirds(y)
        by["measured" if j == 1 else f"{s:.4f}"] = {"scale": s, "mean": float(y.mean()), "ci": [lo, hi], "thirds": th, "desc": _desc(y)}
        tag = f"s={s:.3f}" + (" (measured on the capture)" if j == 1 else "")
        crit.append((f"{tag}: mean > 0 with 95% CI excluding 0", None if lo is None else bool(lo > 0), hi is not None and hi < 0))
        crit.append((f"{tag}: mean > 0 in all three thirds", all(v is not None and v > 0 for v in th), False))
        parts.append(f"{tag}: mean {y.mean() * 100:+.2f}% of premium ({_ci_s((lo, hi), 2, 100)}), thirds "
                     + "/".join(f"{v * 100:+.1f}%" for v in th))
    if measured_scale is None:
        crit.append(("s measured on the captured SPY smile: mean > 0 with CI excluding 0 and positive thirds", None, False))
        parts.append("no captured SPY smile: the measured ATM/VIX scale is not available")
    keys = sorted(variants)
    srs = [sharpe_ratio(variants[k]) for k in keys]
    dsr = float(deflated_sharpe_ratio(variants[(main, 1)], len(keys), trial_sharpes=srs))
    crit.append((f"deflated Sharpe p < 0.05 (DSR > 0.95; {len(keys)} variants: IV scales x hedge daily/weekly)", bool(dsr > 0.95), False))
    parts.append(f"DSR {dsr:.3f} over {len(keys)} variants")
    unhedged = straddle_cycles(fr, main, side=-1, hedge=False, vol_cost=vol_cost, starts=st, ends=en)
    uh = unhedged["pnl"] / unhedged["prem"]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(fr["vix"]))
    shuffled = dict(fr, vix=fr["vix"][perm], has_vix=fr["has_vix"][perm])
    pl = straddle_cycles(shuffled, main, side=-1, hedge=True, vol_cost=vol_cost, starts=st, ends=en)
    one_bp = straddle_cycles(fr, main, side=-1, hedge=True, vol_cost=vol_cost, cost_bps=1.0, starts=st, ends=en)
    sens = {f"{k[0]:.4f}/{'daily' if k[1] == 1 else 'weekly'}": float(v.mean()) for k, v in variants.items()}
    parts.append("IV-scale sensitivity (daily hedge, mean % of premium) " + ", ".join(
        f"s={k[0]:.2f} {variants[k].mean() * 100:+.1f}" for k in keys if k[1] == 1))
    parts.append(f"controls: unhedged {uh.mean() * 100:+.2f}%, shuffled-VIX placebo {np.mean(pl['pnl'] / pl['prem']) * 100:+.2f}%, "
                 f"+1 bp/share hedge cost {np.mean(one_bp['pnl'] / one_bp['prem']) * 100:+.2f}%")
    grid = straddle_cycles(fr, main, side=-1, hedge=True, vol_cost=vol_cost, starts=np.arange(0, max(0, len(fr["days"]) - HOLD)))
    check = None
    if grid["pnl"].size >= 8 * HOLD:
        xg = grid["pnl"] / grid["prem"]
        check = {"n_entries": int(xg.size), "mean": float(xg.mean()),
                 "ci": list(stud_ci(xg, pool_block_len(HOLD), 0.95, n_boot, seed))}
        parts.append(f"cross-check, not in the verdict: 21-day grid pooled over all offsets at s={main:.2f} "
                     f"{check['mean'] * 100:+.2f}% ({_ci_s(check['ci'], 2, 100)}, {xg.size} daily entries)")
    dte_days = fr["ords"][base["end"]] - fr["ords"][base["start"]]
    verdict, why = _decide(crit, n, min_n, "monthly-expiry cycles")
    reason = (f"{MP} short 30-DTE ATM SPY straddle, delta-hedged daily at the entry vol on raw closes, dividend forward "
              f"(ex-dates projected from SPY's quarterly schedule), 0.5 vol-pt round trip; rule 10 (the claim names monthly "
              f"cycles): {n} cycles on SPY's monthly expiry calendar (third Friday, prior session on a holiday; entered "
              f"{int(dte_days.min())}-{int(dte_days.max())} DTE, mean {dte_days.mean():.1f}, non-overlapping) "
              f"{base['day'][0]}..{base['day'][-1]}{measured_note}: " + "; ".join(parts)
              + f"; the edge hinges on the IV level ({TRADED_NOTE})" + f" — {why}")
    stat = {"model_priced": True, "rule10": "SPY monthly expiry calendar (claim: per monthly cycle)", "n_cycles": n,
            "dte_range": [int(dte_days.min()), int(dte_days.max())], "mean_dte": float(dte_days.mean()),
            "measured_scale": measured_scale, "by_scale": by, "dsr": dsr,
            "variant_means": sens, "unhedged_mean": float(uh.mean()), "shuffled_vix_placebo_mean": float(np.mean(pl["pnl"] / pl["prem"])),
            "hedge_cost_1bp_mean": float(np.mean(one_bp["pnl"] / one_bp["prem"])), "grid_pooled_cross_check": check,
            "first_entry": base["day"][0], "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ================================================================================== short option path engine ==

def _smile_ratio(smile: Smile, m, dte) -> np.ndarray:
    m, dte = np.broadcast_arrays(np.asarray(m, dtype=float), np.asarray(dte, dtype=float))
    keys = np.array(sorted(smile.curves), dtype=float)
    near = keys[np.argmin(np.abs(dte[..., None] - keys), axis=-1)]
    out = np.empty(m.shape)
    for t in keys:
        sel = near == t
        ks, rs = smile.curves[int(t)]
        out[sel] = np.interp(m[sel], ks, rs)
    return out


def short_option_paths(fr: dict, entries, legs, dte: int = 45, iv_scale: float = 1.0, smile: Optional[Smile] = None,
                       expiries=None) -> dict:
    """Short option legs entered at the close of each entry day, expiring at the session ``expiries`` gives (an expiry
    calendar) or, without it, on the last trading day on or before entry + ``dte`` calendar days. An entry without a VIX
    close is dropped. legs: [(kind, delta)]; strikes at the target BS delta on the dividend forward (ex-dates projected
    from ``fr["sched"]``) at sigma = iv_scale * VIX/100. Marked to model at every close at the same scale of that day's
    VIX (the latest print; or the captured smile level: VIX_j/100 x IV/VIX ratio at K/S_j) to expiry, where the mark is
    the intrinsic value on the raw close."""
    days, ords, n = fr["days"], fr["ords"], len(fr["days"])
    e = np.asarray(entries, dtype=np.int64)
    if expiries is None:
        xs = np.searchsorted(ords, ords[e] + dte, side="right") - 1
        ok = (xs > e) & (ords[e] + dte <= ords[-1])
    else:
        xs = np.asarray(expiries, dtype=np.int64)
        ok = (xs > e) & (xs < n)
    ok &= fr.get("has_vix", np.ones(n, dtype=bool))[e]
    e, xs = e[ok], xs[ok]
    if e.size == 0:
        return {"n": 0}
    W = int((xs - e).max())
    I = e[:, None] + np.arange(W + 1)[None, :]
    live = I <= xs[:, None]
    I = np.minimum(I, n - 1)
    S = fr["close"][I]
    tt = ords[I].astype(float)
    tx = ords[xs].astype(float)
    T = np.maximum(tx[:, None] - tt, 0.0) / 365.0
    r = fr["rate"][e]
    v = fr["vix"][I] / 100.0
    ex = live & fr.get("sched", fr["div"] > 0)[I]
    ex[:, 0] = False
    Sx = S - _pv_divs(ex, fr["fc"][e], tt, r)
    sig0 = np.maximum(iv_scale * v[:, 0], 0.01)
    marks = np.zeros(S.shape)
    strikes, itm = [], np.zeros(e.size, dtype=int)
    col_x = xs - e
    for kind, dl in legs:
        K = np.array([bs.strike_for_delta(Sx[i, 0], T[i, 0], r[i], sig0[i], dl, kind) for i in range(e.size)])
        if smile is None:
            sig = np.maximum(iv_scale * v, 0.01)
        else:
            sig = np.maximum(v * _smile_ratio(smile, K[:, None] / S, T * 365.0), 0.01)
        marks += bs.price(Sx, K[:, None], T, r[:, None], sig, kind)
        sx = S[np.arange(e.size), col_x]
        itm += ((sx - K) > 0 if kind == "call" else (K - sx) > 0).astype(int)
        strikes.append(K)
    credit = marks[:, 0].copy()
    return {"n": int(e.size), "entries": e, "xs": xs, "col_x": col_x, "I": I, "live": live, "tt": tt, "tx": tx,
            "marks": np.where(live, marks, np.nan), "credit": credit, "strikes": strikes, "spot": S[:, 0], "itm": itm,
            "n_legs": len(legs), "days": [days[a] for a in e]}


def _first_true(mask) -> np.ndarray:
    has = mask.any(axis=1)
    return np.where(has, mask.argmax(axis=1), -1)


def exit_columns(p: dict, exit_dte: int = 21, target: float = 0.5) -> dict:
    """Exit column per position for: hold (expiry), dte21 (first close with <= exit_dte calendar days left), target (first
    close at or below target x credit, else expiry), target_or_dte (the earlier of target and dte21)."""
    m, w = p["marks"].shape
    col = np.arange(w)[None, :]
    left = p["tx"][:, None] - p["tt"]
    before_x = col < p["col_x"][:, None]
    c21 = _first_true((left <= exit_dte) & p["live"] & (col >= 1))
    c21 = np.where(c21 < 0, p["col_x"], c21)
    with np.errstate(invalid="ignore"):
        hit = (p["marks"] <= target * p["credit"][:, None]) & p["live"] & (col >= 1) & before_x
    ctg = _first_true(hit)
    return {"hold": p["col_x"].copy(), "dte21": c21, "target50": np.where(ctg >= 0, ctg, p["col_x"]),
            "target50_or_dte21": np.where((ctg >= 0) & (ctg < c21), ctg, c21)}


def rule_pnl(p: dict, cols, comm: float = COMM_PER_SHARE) -> dict:
    """Per-position P&L (per share) of closing at ``cols``: credit - mark - commissions (open every leg; close every leg
    when exiting before expiry, only the in-the-money legs at expiry), days in the trade and P&L per day / entry spot."""
    rows = np.arange(p["n"])
    mark = p["marks"][rows, cols]
    early = cols < p["col_x"]
    n_close = np.where(early, p["n_legs"], p["itm"])
    pnl = p["credit"] - mark - comm * (p["n_legs"] + n_close)
    days_in = p["tt"][rows, cols] - p["tt"][:, 0]
    return {"pnl": pnl, "days": days_in, "ppd": pnl / p["spot"] / np.maximum(days_in, 1.0)}


# ===================================================================================== T-156 45-DTE strangle ==

def exit_rule_test(diff, n_rules: int = 3, block: int = 6, n_boot: int = 2000, seed: int = 0) -> dict:
    """Paired (by entry) difference of two exit rules: full-sample and per-half means with studentized block-bootstrap CIs at
    the Bonferroni level 1 - 0.05 / n_rules (the deflation for the rules compared)."""
    d = np.asarray(diff, dtype=float)
    level = 1.0 - 0.05 / n_rules
    h = d.size // 2
    out = {"level": level, "n": int(d.size), "mean": float(d.mean()) if d.size else None,
           "ci": list(stud_ci(d, block, level, n_boot, seed)), "halves": []}
    for part in (d[:h], d[h:]):
        out["halves"].append({"n": int(part.size), "mean": float(part.mean()) if part.size else None,
                              "ci": list(stud_ci(part, block, level, n_boot, seed))})
    out["dsr_n_trials"] = float(deflated_sharpe_ratio(d, n_rules)) if d.size > 3 else None
    return out


def _month_starts(days) -> np.ndarray:
    return np.array([i for i in range(len(days)) if i == 0 or days[i][:7] != days[i - 1][:7]], dtype=np.int64)


def _week_starts(days) -> np.ndarray:
    wk = [date.fromisoformat(d).isocalendar()[:2] for d in days]
    return np.array([i for i in range(len(days)) if i == 0 or wk[i] != wk[i - 1]], dtype=np.int64)


def theta_harvest(fr: dict, smile: Optional[Smile] = None, daily: bool = True, delta: float = 0.16, dte: int = 45,
                  block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300) -> dict:
    """T-156: 45-DTE 0.16-delta SPY short strangle priced and marked at VIX (flat). Statistic: mean P&L per day in the trade
    (P&L / entry spot / calendar days), 21-DTE exit minus hold to expiry, paired by entry. CIs on the monthly entries,
    Bonferroni level for the three rules. Pass: > 0 with the CI excluding 0 in both halves; min_n 300 monthly entries.
    Commissions $0.65 per contract.

    Rule 10(a): 'monthly' 45-DTE entries name SPY's monthly expiry calendar: each entry sells the strangle expiring on a
    monthly expiry (third Friday, prior session on a holiday) at the session nearest 45 calendar days before it (block 6
    covers the overlap of consecutive 45-day positions). The trial's daily entries (every session with a VIX close,
    expiring on the last session on or before entry + 45 days) are reported with a pooled CI (block 6 holds of 31
    sessions), not in the verdict."""
    legs = [("put", -delta), ("call", delta)]
    me, mx = calendar_entries(fr["days"], monthly_expiry_idx(fr["days"]), dte, False, ok=fr.get("has_vix"))

    def run(entries, scale=1.0, sm=None, expiries=None):
        p = short_option_paths(fr, entries, legs, dte, scale, sm, expiries=expiries)
        if p["n"] == 0:
            return p, {}
        cols = exit_columns(p)
        return p, {k: rule_pnl(p, c) for k, c in cols.items()}

    p, rules = run(me, expiries=mx)
    n = int(p.get("n", 0))
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} monthly-expiry entries"}
    diff = rules["dte21"]["ppd"] - rules["hold"]["ppd"]
    t = exit_rule_test(diff, 3, block, n_boot, seed)
    bp = 1e4
    crit, parts = [], []
    for i, hpart in enumerate(t["halves"]):
        lo, hi = hpart["ci"]
        crit.append((f"half {i + 1}: (21-DTE - hold) P&L/day > 0, {t['level'] * 100:.2f}% CI (Bonferroni, 3 rules) excludes 0",
                     None if lo is None else bool(lo > 0), hi is not None and hi < 0))
        parts.append(f"half {i + 1} ({hpart['n']} entries): {_s(hpart['mean'] and hpart['mean'] * bp, 3)} bp/day "
                     f"({_ci_s(hpart['ci'], 3, bp)})")
    means = {k: float(v["ppd"].mean() * bp) for k, v in rules.items()}
    sds = {k: float(v["ppd"].std(ddof=1) * bp) for k, v in rules.items()}
    parts.insert(0, f"full sample {t['mean'] * bp:+.3f} bp of spot per day ({_ci_s(t['ci'], 3, bp)}); P&L/day by rule (bp, sd): "
                 + ", ".join(f"{k} {means[k]:+.2f} ({sds[k]:.2f})" for k in ("hold", "dte21", "target50", "target50_or_dte21")))
    sens = {}
    for s in (0.81, 0.90):
        _, rr = run(me, s, expiries=mx)
        sens[f"{s:.2f}"] = float((rr["dte21"]["ppd"] - rr["hold"]["ppd"]).mean() * bp)
    if smile is not None:
        _, rr = run(me, 1.0, smile, expiries=mx)
        sens["captured_smile"] = float((rr["dte21"]["ppd"] - rr["hold"]["ppd"]).mean() * bp)
    parts.append("IV sensitivity of the mean difference (bp/day) " + ", ".join(f"{k} {v:+.3f}" for k, v in sens.items())
                 + ("" if smile is not None else "; captured-smile (skew) sensitivity not run: no spy-smile bundle"))
    daily_rep = None
    if daily:
        dent = np.nonzero(fr.get("has_vix", np.ones(len(fr["days"]), dtype=bool)))[0]
        _, rd = run(dent)
        if rd:
            dd = rd["dte21"]["ppd"] - rd["hold"]["ppd"]
            hs = int(round(dte * PPY / 365.0))
            pbd = pool_block_len(hs)
            lvl = t["level"]
            h = dd.size // 2
            daily_rep = {"n_entries": int(dd.size), "mean_bp": float(dd.mean() * bp), "block_days": pbd, "level": lvl,
                         "ci_bp": [None if b is None else b * bp for b in stud_ci(dd, pbd, lvl, n_boot, seed)],
                         "halves": [{"mean_bp": float(q.mean() * bp),
                                     "ci_bp": [None if b is None else b * bp for b in stud_ci(q, pbd, lvl, n_boot, seed)]}
                                    for q in (dd[:h], dd[h:])]}
            parts.append(f"trial's daily entries (reported, not in the verdict): {dd.size} entries, mean {daily_rep['mean_bp']:+.3f} "
                         f"bp/day ({_ci_s(daily_rep['ci_bp'], 3)}, block {pbd} days), halves "
                         + "/".join(f"{q['mean_bp']:+.3f} ({_ci_s(q['ci_bp'], 3)})" for q in daily_rep["halves"]))
    dte_days = p["tx"] - p["tt"][:, 0]
    verdict, why = _decide(crit, n, min_n, "monthly entries")
    reason = (f"{MP} 45-DTE 0.16-delta SPY short strangle at VIX on the dividend forward, marked daily at VIX, settled on raw "
              f"closes, $0.65/contract; rule 10 (the trial names monthly entries): {n} entries on SPY's monthly expiry "
              f"calendar (third Friday, prior session on a holiday; entered {int(dte_days.min())}-{int(dte_days.max())} DTE) "
              f"{p['days'][0]}..{p['days'][-1]}, P&L per day in bp of entry spot: "
              + "; ".join(parts) + f"; margin-time cost not charged (P&L per day already scales by time); {TRADED_NOTE}" + f" — {why}")
    stat = {"model_priced": True, "rule10": "SPY monthly expiry calendar (trial: monthly entries)", "n_monthly_entries": n,
            "dte_range": [int(dte_days.min()), int(dte_days.max())], "test": t, "mean_ppd_bp": means, "sd_ppd_bp": sds,
            "mean_days_in_trade": {k: float(v["days"].mean()) for k, v in rules.items()}, "iv_sensitivity_bp": sens,
            "daily_entries": daily_rep, "commission_per_contract": 0.65, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ======================================================================================= T-157 theta ladder ==

def put_book(fr: dict, entries, size: float, delta: float = -0.16, dte: int = 45, iv_scale: float = 1.0,
             comm: float = COMM_PER_SHARE, expiries=None) -> dict:
    """Daily P&L of a book of short puts (0.16 delta, 45 DTE - or the given ``expiries`` - closed at 50% of the credit or 21
    DTE), each sized at ``size`` units of strike notional (size / K shares). P&L per unit notional, marked to model at each
    close; commissions per share on every fill. Returns the daily P&L and open notional on the frame's calendar."""
    n = len(fr["days"])
    pnl = np.zeros(n)
    expo = np.zeros(n)
    p = short_option_paths(fr, entries, [("put", delta)], dte, iv_scale, expiries=expiries)
    if p["n"] == 0:
        return {"pnl": pnl, "exposure": expo, "n_positions": 0, "first": None, "last": None}
    cols = exit_columns(p)["target50_or_dte21"]
    q = size / p["strikes"][0]
    marks = np.where(p["live"], p["marks"], 0.0)
    w = marks.shape[1]
    col = np.arange(w)[None, :]
    step = np.zeros_like(marks)
    step[:, 1:] = -(marks[:, 1:] - marks[:, :-1])
    held = (col >= 1) & (col <= cols[:, None])
    daily = np.where(held, step, 0.0) * q[:, None]
    daily[:, 0] -= comm * q                                             # open
    rows = np.arange(p["n"])
    early = cols < p["col_x"]
    daily[rows, cols] -= comm * q * np.where(early, 1, p["itm"])         # close (expiry: only if in the money)
    np.add.at(pnl, p["I"].ravel(), daily.ravel())
    open_ = (col < cols[:, None]) & p["live"]
    np.add.at(expo, p["I"][open_], size)
    return {"pnl": pnl, "exposure": expo, "n_positions": int(p["n"]), "first": int(p["entries"][0]),
            "last": int((p["entries"] + cols).max()), "mean_moneyness": float(np.mean(p["strikes"][0] / p["spot"])),
            "trade_pnl_per_notional": (p["credit"] - p["marks"][rows, cols]) / p["strikes"][0]}


def ladder_verdict(pl_ladder, pl_single, block: int = 63, n_boot: int = 1000, seed: int = 0, bound: float = 0.85) -> dict:
    """Drawdown ratio (ladder / single) on the full span and in each half, with a paired percentile block-bootstrap CI.
    Criteria: in each half, ratio < ``bound`` and CI upper < 1."""
    a = np.asarray(pl_ladder, dtype=float)
    b = np.asarray(pl_single, dtype=float)
    h = a.size // 2
    full = mdd_ratio_ci(a, b, block, n_boot, seed)
    halves = [mdd_ratio_ci(a[:h], b[:h], block, n_boot, seed), mdd_ratio_ci(a[h:], b[h:], block, n_boot, seed)]
    crit = []
    for i, hv in enumerate(halves):
        ok = None if hv["ratio"] is None or hv["ci"][1] is None else bool(hv["ratio"] < bound and hv["ci"][1] < 1.0)
        dec = hv["ci"][0] is not None and hv["ci"][0] >= bound          # interval wholly at or above the bound
        crit.append((f"half {i + 1}: drawdown ratio < {bound} with bootstrap CI upper < 1", ok, dec))
    return {"full": full, "halves": halves, "crit": crit}


def ladder_calendars(fr: dict, dte: int = 45) -> dict:
    """Rule 10(a) entries for T-157: the single book sells the put expiring on each monthly expiry (third Friday), the
    ladder the put expiring on every weekly Friday expiry (prior session on a holiday for both), each entered at the
    session nearest ``dte`` calendar days before its expiry (both books enter on the same weekday)."""
    days, ok = fr["days"], fr.get("has_vix")
    sm, sx = calendar_entries(days, monthly_expiry_idx(days), dte, False, ok)
    lw, lx = calendar_entries(days, weekly_expiry_idx(days), dte, False, ok)
    return {"single": (sm, sx), "ladder": (lw, lx)}


def theta_ladder(fr: dict, block: int = 63, n_boot: int = 4000, seed: int = 0, min_n: int = 300, dte: int = 45) -> dict:
    """T-157: weekly ladder of quarter-size 0.16-delta short puts vs a full-size monthly entry, both 45 DTE and closed at 50%
    of the credit or 21 DTE, priced and marked at VIX. Pass: drawdown ratio < 0.85 with the bootstrap CI upper < 1 in both
    halves; min_n 300 months. Rule 10(a): 'weekly' rungs and the 'monthly' entry are built on SPY's weekly-Friday and
    monthly (third-Friday) expiry calendars, entered 45 DTE before each expiry (``ladder_calendars``); the previous
    first-session-of-month/week anchors are reported as a sensitivity."""
    cal = ladder_calendars(fr, dte)
    single = put_book(fr, cal["single"][0], 1.0, dte=dte, expiries=cal["single"][1])
    ladder = put_book(fr, cal["ladder"][0], 0.25, dte=dte, expiries=cal["ladder"][1])
    if single["first"] is None or ladder["first"] is None:
        return {"verdict": "inconclusive", "n": 0, "reason": "no complete positions"}
    a0 = min(single["first"], ladder["first"])
    a1 = max(single["last"], ladder["last"]) + 1
    L, S = ladder["pnl"][a0:a1], single["pnl"][a0:a1]
    months = len({d[:7] for d in fr["days"][a0:a1]})
    v = ladder_verdict(L, S, block, n_boot, seed)
    crit = v["crit"]
    sens = {}
    for s in (0.81, 0.90):
        s1 = put_book(fr, cal["single"][0], 1.0, dte=dte, iv_scale=s, expiries=cal["single"][1])
        l1 = put_book(fr, cal["ladder"][0], 0.25, dte=dte, iv_scale=s, expiries=cal["ladder"][1])
        mb = float(_mdd_abs(s1["pnl"][a0:a1])[0])
        sens[f"{s:.2f}"] = float(_mdd_abs(l1["pnl"][a0:a1])[0]) / mb if mb > 0 else None
    old = {}
    s0 = put_book(fr, _month_starts(fr["days"]), 1.0, dte=dte)
    l0 = put_book(fr, _week_starts(fr["days"]), 0.25, dte=dte)
    if s0["first"] is not None and l0["first"] is not None:
        b0, b1 = min(s0["first"], l0["first"]), max(s0["last"], l0["last"]) + 1
        v0 = ladder_verdict(l0["pnl"][b0:b1], s0["pnl"][b0:b1], block, max(200, n_boot // 4), seed)
        old = {"full_ratio": v0["full"]["ratio"], "half_ratios": [h["ratio"] for h in v0["halves"]],
               "half_ci_upper": [h["ci"][1] for h in v0["halves"]]}

    def monthly(pl, ex):
        ms = {}
        for d, x in zip(fr["days"][a0:a1], pl):
            ms[d[:7]] = ms.get(d[:7], 0.0) + x
        arr = np.array(list(ms.values()))
        m_ex = float(np.mean(ex[a0:a1]))
        return {"mean_per_margin": float(arr.mean() / m_ex) if m_ex > 0 else None,
                "sd_per_margin": float(arr.std(ddof=1) / m_ex) if m_ex > 0 else None, "mean_open_notional": m_ex}

    mo = {"ladder": monthly(L, ladder["exposure"]), "single": monthly(S, single["exposure"])}
    f = v["full"]
    parts = [f"full span ratio {_f(f['ratio'], 3)} (MDD ladder {f['mdd_a'] * 100:.1f}% vs single {f['mdd_b'] * 100:.1f}% of notional, "
             f"95% CI {_f(f['ci'][0], 2)}-{_f(f['ci'][1], 2)})"]
    for i, hv in enumerate(v["halves"]):
        parts.append(f"half {i + 1}: ratio {_f(hv['ratio'], 3)} (CI {_f(hv['ci'][0], 2)}-{_f(hv['ci'][1], 2)})")
    parts.append(f"mean monthly P&L per unit margin ladder {mo['ladder']['mean_per_margin'] * 100:+.2f}% (sd {mo['ladder']['sd_per_margin'] * 100:.2f}%) "
                 f"vs single {mo['single']['mean_per_margin'] * 100:+.2f}% (sd {mo['single']['sd_per_margin'] * 100:.2f}%); open notional "
                 f"{mo['ladder']['mean_open_notional']:.2f} vs {mo['single']['mean_open_notional']:.2f}")
    parts.append(f"delta-matched (both 0.16 at entry): mean K/S {ladder['mean_moneyness']:.3f} vs {single['mean_moneyness']:.3f}")
    parts.append("IV sensitivity of the full-span ratio " + ", ".join(f"s={k} {_f(x, 3)}" for k, x in sens.items()))
    if old:
        parts.append(f"sensitivity, first-session-of-month/week entries at entry + 45 days (the previous anchors): full ratio "
                     f"{_f(old['full_ratio'], 3)}, halves {_f(old['half_ratios'][0], 3)}/{_f(old['half_ratios'][1], 3)} (CI upper "
                     f"{_f(old['half_ci_upper'][0], 2)}/{_f(old['half_ci_upper'][1], 2)})")
    verdict, why = _decide(crit, months, min_n, "months")
    reason = (f"{MP} 0.16-delta 45-DTE SPY short puts at VIX on the dividend forward, marked daily, closed at 50% of credit or "
              f"21 DTE, $0.65/contract per fill (four times the fills for the ladder); rule 10 (the claim names weekly and "
              f"monthly entries): {ladder['n_positions']} ladder rungs on the weekly Friday expiry calendar vs "
              f"{single['n_positions']} entries on the monthly (third-Friday) expiry calendar, each entered 45 DTE before its "
              f"expiry, over {months} months {fr['days'][a0]}..{fr['days'][a1 - 1]}; drawdowns of the additive P&L per unit "
              f"notional, paired percentile block bootstrap (block {block} days): " + "; ".join(parts)
              + f"; {TRADED_NOTE}" + f" — {why}")
    stat = {"model_priced": True, "rule10": "SPY weekly-Friday and monthly expiry calendars (claim: weekly ladder vs monthly entry)",
            "n_months": months, "full": f, "halves": v["halves"], "monthly": mo, "iv_sensitivity_ratio": sens,
            "previous_anchor_sensitivity": old, "n_ladder_rungs": ladder["n_positions"],
            "n_single_entries": single["n_positions"], "block_days": block, "verdict": verdict}
    return {"verdict": verdict, "n": months, "reason": reason, "stat": stat}


# =============================================================================== model-free variance claims ==

def intraday_var_by_day(rows) -> dict:
    """{day: sum of squared hourly log returns inside the regular session} from an hourly bar bundle (the first bar from
    its open; the overnight return is left out, as in intraday-only realised variance)."""
    by: dict = {}
    for r in rows:
        v = r.get("value", {})
        o, c, t = v.get("open"), v.get("close"), v.get("t")
        if not o or not c or t is None or not (float(o) > 0 and float(c) > 0):
            continue
        d = datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d")
        by.setdefault(d, []).append((float(t), float(o), float(c)))
    out = {}
    for d, bars in by.items():
        bars.sort()
        s = math.log(bars[0][2] / bars[0][1]) ** 2
        for k in range(1, len(bars)):
            s += math.log(bars[k][2] / bars[k - 1][2]) ** 2
        out[d] = s
    return out


def short_variance_units(days, close, vix, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 390,
                         checks: Optional[dict] = None, intraday: Optional[dict] = None, hold: int = HOLD) -> dict:
    """T-540: short 30-day variance struck at VIX_t^2 settled on the next 21 close-to-close log returns; P&L = (VIX^2 -
    RV21) / 12 in %^2 per month. Pass: lower 95% studentized CI > 0; min_n 390 cycles.

    Rule 10(b): the claim's non-overlapping cycles have no calendar, so the criterion is judged on the POOLED estimate
    over all 21 grid offsets (every session with a VIX close is an entry; studentized circular block bootstrap, 126-day
    blocks); each offset is reported. ``days``/``close`` are the full index calendar (a session without a VIX close, NaN
    in ``vix``, takes no entry but stays in the returns). ``checks``: {label: closes aligned to ``days``} for basis
    checks on the same entries; ``intraday``: {day: intraday-only variance} for the partial 5-minute-RV control."""
    days = list(days)
    c = np.asarray(close, dtype=float)
    v = np.asarray(vix, dtype=float)
    cand = np.arange(0, max(0, c.size - hold))
    ent = cand[np.isfinite(v[cand]) & (v[cand] > 0)]
    rv = _fwd_rv(c, ent, hold)
    keep = np.isfinite(rv)
    ent, rv = ent[keep], rv[keep]
    n = n_holds(ent, hold)
    if ent.size < 8 * hold:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {ent.size} daily entries ({n} cycles)"}
    x = (v[ent] ** 2 - rv * 1e4) / 12.0
    ps = phase_scan(ent, x, hold, block, n_boot, seed, side=1)
    lo, hi = ps["pooled"]["ci"]
    worst = int(np.argmin(x))
    near = np.abs(ent - ent[worst]) < hold                       # every entry whose window overlaps the worst one
    ex_lo, ex_hi = stud_ci(x[~near], pool_block_len(hold), 0.95, n_boot, seed)
    exw = []
    for k in range(hold):
        xk = x[ent % hold == k]
        if xk.size > 1:
            exw.append(float(np.delete(xk, int(np.argmin(xk))).mean()))
    d = _desc(x)
    # units sensitivity: strike (VIX/100)^2 x 30/365 against the un-annualised sum of 21 squared returns
    x30 = v[ent] ** 2 * 30.0 / 365.0 - rv * hold / PPY * 1e4
    ps30 = phase_scan(ent, x30, hold, block, max(500, n_boot // 2), seed, side=1)
    rep = {}
    for lab, cc in (checks or {}).items():
        rv2 = _fwd_rv(np.asarray(cc, dtype=float), ent, hold)
        ok = np.isfinite(rv2)
        if ok.any():
            y = (v[ent[ok]] ** 2 - rv2[ok] * 1e4) / 12.0
            rep[lab] = {"n_entries": int(ok.sum()), "mean": float(y.mean())}
    intra = None
    if intraday:
        iv = np.array([intraday.get(dd, np.nan) for dd in days])
        cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(iv, nan=0.0))])
        bad = np.concatenate([[0], np.cumsum(~np.isfinite(iv))])
        okw = (bad[ent + hold + 1] - bad[ent + 1]) == 0
        if okw.sum() >= hold:
            e2 = ent[okw]
            rvi = PPY / hold * (cs[e2 + hold + 1] - cs[e2 + 1])
            xi = (v[e2] ** 2 - rvi * 1e4) / 12.0
            intra = {"n_entries": int(e2.size), "first": days[e2[0]], "last": days[e2[-1]],
                     "mean_close_to_close": float(x[okw].mean()), "mean_intraday": float(xi.mean()),
                     "rv_ratio_intraday_to_close": float(rvi.mean() / rv[okw].mean())}
    crit = [(f"lower 95% CI of mean (VIX^2 - RV21)/12 > 0 (pooled over the {hold} grid offsets)",
             None if lo is None else bool(lo > 0), hi is not None and hi < 0)]
    verdict, why = _decide(crit, n, min_n, f"cycles (distinct {hold}-day holds of the pooled entries)")
    parts = [_pool_txt(ps, 2, 1.0, " %^2/month"), _phase_txt(ps, 1, 2),
             f"skew {d['skew']:.2f}, kurtosis {d['kurtosis']:.1f}, worst cycle {x[worst]:+.1f} entered {days[ent[worst]]}; "
             f"ex-worst: pooled without the {int(near.sum())} entries overlapping it {x[~near].mean():+.2f} "
             f"({_ci_s((ex_lo, ex_hi))}), per offset without its own worst cycle {min(exw):+.2f} to {max(exw):+.2f}",
             f"units sensitivity (strike (VIX/100)^2 x 30/365 vs the un-annualised sum of 21 squared returns, %^2): pooled "
             f"{ps30['pooled']['mean']:+.2f} ({_ci_s(ps30['pooled']['ci'])}), {ps30['summary']['n_pass']}/{hold} offsets pass"]
    parts += [f"{k} basis {r['mean']:+.2f} (pooled, {r['n_entries']} entries)" for k, r in rep.items()]
    if intra:
        parts.append(f"close-to-close vs intraday RV (BTZ use 5-minute RV; not archived): on hourly SPY bars "
                     f"{intra['first']}..{intra['last']} ({intra['n_entries']} entries) intraday-only RV is "
                     f"{intra['rv_ratio_intraday_to_close']:.2f} x close-to-close and the mean P&L {intra['mean_intraday']:+.2f} vs "
                     f"{intra['mean_close_to_close']:+.2f}: close-to-close RV runs higher, so this test is conservative on the control")
    else:
        parts.append("close-to-close vs 5-minute RV: 5-minute RV is not archived (intraday RV leaves out the overnight return "
                     "and runs lower, so close-to-close is the conservative choice)")
    reason = (f"short variance struck at VIX^2, settled on SPY close-to-close returns; rule 10 (no entry calendar in the "
              f"claim): {ent.size} daily entries {days[ent[0]]}..{days[ent[-1]]} = {n} cycles: " + "; ".join(parts) + f" — {why}")
    stat = {"rule10": "pooled all-offset estimate (no calendar in the claim)", "n_cycles": n, "n_entries": int(ent.size),
            "mean_pct2_per_month": ps["pooled"]["mean"], "ci95": [lo, hi], "block_days": ps["pooled"]["block_days"],
            "offsets": ps["offsets"], "offsets_summary": ps["summary"], **{f"desc_{k}": val for k, val in d.items()},
            "worst_cycle": float(x[worst]), "worst_day": days[ent[worst]],
            "mean_ex_worst_window": float(x[~near].mean()), "ci_ex_worst_window": [ex_lo, ex_hi],
            "mean_ex_worst_by_offset_range": [min(exw), max(exw)], "share_positive": float((x > 0).mean()),
            "thirds": _thirds(x), "units_30_365": {"pooled": ps30["pooled"], "summary": ps30["summary"]},
            "checks": rep, "intraday_check": intra, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def _cp_ci(k: int, n: int, alpha: float = 0.05) -> tuple:
    """Clopper-Pearson interval: options_market._binom_two_sided_ci (bisection on the exact binomial tails), with the
    tails summed in log space by numpy so the many per-third and per-offset intervals stay fast."""
    k, n = int(k), int(n)
    i = np.arange(n + 1)
    lc = np.array([math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1) for j in i])

    def cdf(x, p):
        if p <= 0.0:
            return 1.0
        if p >= 1.0:
            return 1.0 if x >= n else 0.0
        j = i[:x + 1]
        return float(np.exp(lc[:x + 1] + j * math.log(p) + (n - j) * math.log1p(-p)).sum())

    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p) >= alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p) <= alpha / 2)
    return lower, upper


def _win_stats(win, block: int, n_boot: int, seed: int) -> dict:
    k, n = int(np.sum(win)), int(np.size(win))
    cp = _cp_ci(k, n) if n else (None, None)
    bb = pct_ci(np.asarray(win, dtype=float), block, 0.95, n_boot, seed)
    return {"wins": k, "n": n, "rate": k / n if n else None, "cp": list(cp), "bb": list(bb)}


def vix2_win_rate(days, close, vix, bound: float = 0.75, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300,
                  checks: Optional[dict] = None, truncation: Optional[list] = None, atm_scales: Optional[dict] = None,
                  start: str = "1990-01-01", hold: int = HOLD) -> dict:
    """T-234: share of non-overlapping months with (VIX_t/100)^2 > RV_{t,t+21}. Pass: lower 95% bound (exact
    Clopper-Pearson, two-sided, and the percentile block bootstrap) > 0.75, and the win rate > 0.75 in all three thirds
    (the reading applied: the point win rate in each third, the analogue of the original 'mean positive in each third';
    the per-third CIs are reported); min_n 300 months. The strip truncation error on the captured chain is reported, not
    part of the pass.

    Rule 10(a): 'months since 1990' names the calendar month: each month enters at the close of its first session with a
    VIX close and settles on the next 21 ^GSPC price returns. The month-end anchor and the 21-day grid (pooled and per
    offset) are reported. ``days``/``close`` are the full index calendar (NaN ``vix`` = no VIX close that day).
    ``atm_scales``: {label: s} for the MODEL-PRICED ATM-straddle-only control at ATM IV = s x VIX."""
    days = list(days)
    c = np.asarray(close, dtype=float)
    v = np.asarray(vix, dtype=float)
    okv = np.isfinite(v) & (v > 0)
    ent = _month_first(days, okv, start)
    rv = _fwd_rv(c, ent, hold)
    keep = np.isfinite(rv)
    ent, rv = ent[keep], rv[keep]
    n = int(ent.size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} months"}
    iv = (v[ent] / 100.0) ** 2
    win = (iv > rv).astype(float)
    ovl = int(np.max(np.maximum(ent[:-1] + hold - ent[1:], 0))) if n > 1 else 0
    w = _win_stats(win, block, n_boot, seed)
    k, cp, bb = w["wins"], w["cp"], w["bb"]
    th_parts = np.array_split(win, 3)
    thirds = [_win_stats(p, block, n_boot, seed) for p in th_parts]
    th = [t["rate"] for t in thirds]
    crit = [(f"exact binomial lower 95% bound > {bound}", bool(cp[0] > bound), cp[1] < bound),
            (f"block-bootstrap lower 95% bound > {bound}", None if bb[0] is None else bool(bb[0] > bound), bb[1] is not None and bb[1] < bound),
            (f"win rate > {bound} in all three thirds (point estimate)", all(t > bound for t in th), False)]
    strict = all(t["cp"][0] is not None and t["cp"][0] > bound and t["bb"][0] is not None and t["bb"][0] > bound for t in thirds)
    logr = np.log(np.maximum(rv, 1e-12) / iv)
    pnl_vega1 = (v[ent] ** 2 - rv * 1e4) / (2.0 * v[ent])          # short variance swap, vega notional 1 per vol point
    vrp = (v[ent] ** 2 - rv * 1e4) / 12.0
    # robustness: month-end anchor; the 21-day grid (pooled over offsets and per offset)
    ent_e = _month_last(days, okv, start)
    rv_e = _fwd_rv(c, ent_e, hold)
    ke = np.isfinite(rv_e)
    we = _win_stats(((v[ent_e[ke]] / 100.0) ** 2 > rv_e[ke]).astype(float), block, max(500, n_boot // 2), seed)
    cand = np.arange(0, max(0, c.size - hold))
    ge = cand[okv[cand] & (np.array(days)[cand] >= start)] if cand.size else cand
    grv = _fwd_rv(c, ge, hold)
    gk = np.isfinite(grv)
    ge, grv = ge[gk], grv[gk]
    gwin = ((v[ge] / 100.0) ** 2 > grv).astype(float)
    gcp = [_cp_ci(int(gwin[ge % hold == q].sum()), int((ge % hold == q).sum()))[0] for q in range(hold)
           if (ge % hold == q).any()]
    gpool = pct_ci(gwin, pool_block_len(hold), 0.95, max(500, n_boot // 2), seed)
    grid = {"pooled_rate": float(gwin.mean()) if gwin.size else None, "pooled_bb": list(gpool), "n_entries": int(gwin.size),
            "cp_lower_min": min(gcp) if gcp else None, "cp_lower_max": max(gcp) if gcp else None,
            "n_offsets_pass": int(sum(1 for x in gcp if x > bound)), "n_offsets": len(gcp)}
    rep = {}
    for lab, cc in (checks or {}).items():
        rv2 = _fwd_rv(np.asarray(cc, dtype=float), ent, hold)
        ok = np.isfinite(rv2)
        if ok.any():
            rep[lab] = {"n": int(ok.sum()), "win_rate": float(np.mean(iv[ok] > rv2[ok])), "win_rate_index_same_months": float(win[ok].mean())}
    atm = {}
    for lab, s in (atm_scales or {}).items():
        if s is None:
            continue
        ia = (s * v[ent] / 100.0) ** 2
        atm[lab] = {"scale": float(s), "win_rate": float(np.mean(ia > rv)), "mean_vrp": float(np.mean((s * s * v[ent] ** 2 - rv * 1e4) / 12.0))}
    rng = np.random.default_rng(seed)
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.log(c[1:] / c[:-1])
    okl = np.isfinite(lr)
    sh = np.zeros(lr.size)
    sh[okl] = rng.permutation(lr[okl])
    csh = np.concatenate([[0.0], np.cumsum(sh ** 2)])
    rv_sh = PPY / hold * (csh[ent + hold] - csh[ent])                # returns a+1..a+hold of the shuffled series
    placebo = float(np.mean(iv > rv_sh))
    parts = [f"win rate {k}/{n} = {k / n:.3f} (Clopper-Pearson {cp[0]:.3f}-{cp[1]:.3f}; block bootstrap {_f(bb[0], 3)}-{_f(bb[1], 3)})",
             "thirds " + ", ".join(f"{t['rate']:.3f} (CP {t['cp'][0]:.3f}-{t['cp'][1]:.3f}, bootstrap {_f(t['bb'][0], 3)}-{_f(t['bb'][1], 3)})"
                                   for t in thirds)
             + f" [reading applied: the point win rate > {bound} in each third; the stricter reading, every third's lower "
               f"bound > {bound}, {'also holds' if strict else 'does not hold'}]",
             f"mean ln(RV/VIX^2) {logr.mean():+.3f}, mean VRP {vrp.mean():+.2f} %^2/month, short var swap (vega notional 1) "
             f"{pnl_vega1.mean():+.2f} per cycle",
             f"robustness (not in the pass): month-end anchor {we['rate']:.3f} (CP lower {we['cp'][0]:.3f}, n {we['n']}); 21-day grid "
             f"pooled over all offsets {_f(grid['pooled_rate'], 3)} (bootstrap {_f(gpool[0], 3)}-{_f(gpool[1], 3)}, "
             f"{grid['n_entries']} entries), per-offset CP lower {_f(grid['cp_lower_min'], 3)} to {_f(grid['cp_lower_max'], 3)}, "
             f"{grid['n_offsets_pass']}/{grid['n_offsets']} offsets pass",
             f"shuffled-returns placebo win rate {placebo:.3f}"]
    parts += [f"{lab} check win rate {r['win_rate']:.3f} (n {r['n']}; index {r['win_rate_index_same_months']:.3f} on those months)"
              for lab, r in rep.items()]
    if atm:
        parts.append("ATM-straddle-only VRP control (MODEL-PRICED: no ATM-IV history is archived, so ATM IV = s x VIX; expected "
                     "smaller): " + ", ".join(f"{lab} s={a['scale']:.3f} win rate {a['win_rate']:.3f}, mean VRP {a['mean_vrp']:+.2f} "
                                              f"%^2/month" for lab, a in atm.items())
                     + f" vs VIX {k / n:.3f}, {vrp.mean():+.2f}")
    else:
        parts.append("ATM-straddle-only VRP control not run (no ATM-IV history and no scale given)")
    if truncation:
        tx = []
        for t in truncation:
            e = t.get("error")
            flag = "" if e is None or abs(e) < 0.05 else (" BREACHES the 5% tolerance" + (
                " (a positive error is the wrong sign for truncation, which drops wing strikes and biases the strip down)"
                if e > 0 else ""))
            tim = ""
            if t.get("captured_at"):
                g = t.get("implied_spot_vs_close")
                tim = (f" [capture {t['captured_at']} UTC"
                       + (" inside Cboe's overnight SPX session (20:15-09:15 ET): live overnight quotes, not the 16:15 ET "
                          "close the VIX prints" if t.get("overnight_session") else "")
                       + (f"; chain-implied spot {g * 100:+.2f}% vs the {t['quote_day']} close" if g is not None else "")
                       + "]")
            tx.append(f"{t['quote_day']} {_s(e and e * 100, 1)}%{flag}{tim}")
        parts.append("strip vs VIX^2 on the captured SPX chain (reported, not in the pass; tolerance < 5%): " + ", ".join(tx))
    else:
        parts.append("strip truncation check not run (no captured SPX chain)")
    verdict, why = _decide(crit, n, min_n, "months")
    reason = (f"model-free: (VIX/100)^2 vs next 21-day ^GSPC realised variance (price returns); rule 10 (the claim names "
              f"months): {n} calendar months entered at the first session with a VIX close, {days[ent[0]]}..{days[ent[-1]]} "
              f"(a 21-session window overlaps the next month's by at most {ovl} sessions in short months): "
              + "; ".join(parts) + f" — {why}")
    stat = {"rule10": "calendar month (claim: non-overlapping months)", "n_months": n, "max_window_overlap_sessions": ovl,
            "wins": k, "win_rate": k / n,
            "clopper_pearson": list(cp), "block_bootstrap": list(bb), "thirds": th, "thirds_detail": thirds,
            "thirds_strict_reading_holds": strict, "mean_log_rv_over_vix2": float(logr.mean()), "mean_vrp_pct2_month": float(vrp.mean()),
            "short_var_swap_vega1_mean": float(pnl_vega1.mean()), "month_end_anchor": we, "grid_21d": grid,
            "shuffled_returns_placebo": placebo, "checks": rep, "atm_straddle_control": atm, "truncation": truncation or [],
            "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def har_forecast(closes, refit_mask, min_obs: int = 500) -> np.ndarray:
    """Walk-forward HAR(1,5,22) forecast of the next-21-day annualised realised variance at each close. Regressors at close
    i: 252 r_i^2, 252 mean(r_{i-4..i}^2), 252 mean(r_{i-21..i}^2); target 252 mean(r_{i+1..i+21}^2). Refit (OLS, expanding
    window) at each day where ``refit_mask`` is True using only samples whose target window has closed (i + 21 <= refit
    day); a day's forecast uses the latest refit on or before it. NaN before the first refit with ``min_obs`` samples."""
    c = np.asarray(closes, dtype=float)
    n = c.size
    r2 = np.zeros(n)
    r2[1:] = np.log(c[1:] / c[:-1]) ** 2
    cs = np.concatenate([[0.0], np.cumsum(r2)])
    X = np.full((n, 4), np.nan)
    y = np.full(n, np.nan)
    for i in range(22, n):
        X[i] = [1.0, PPY * r2[i], PPY * (cs[i + 1] - cs[i - 4]) / 5.0, PPY * (cs[i + 1] - cs[i - 21]) / 22.0]
    for i in range(22, n - HOLD):
        y[i] = PPY * (cs[i + HOLD + 1] - cs[i + 1]) / HOLD
    valid = np.isfinite(y) & np.isfinite(X).all(axis=1)
    Xv = np.where(valid[:, None], X, 0.0)
    yv = np.where(valid, y, 0.0)
    cXX = np.cumsum(Xv[:, :, None] * Xv[:, None, :], axis=0)
    cXy = np.cumsum(Xv * yv[:, None], axis=0)
    cN = np.cumsum(valid)
    out = np.full(n, np.nan)
    beta = None
    for d in range(n):
        if refit_mask[d] and d - HOLD >= 0 and cN[d - HOLD] >= min_obs:
            try:
                beta = np.linalg.solve(cXX[d - HOLD], cXy[d - HOLD])
            except np.linalg.LinAlgError:
                pass
        if beta is not None and np.isfinite(X[d]).all():
            out[d] = float(X[d] @ beta)
    return out

def _t235_eval(starts, z, zv, vv, lr, block: int, n_boot: int, seed: int, with_pbo: bool = True, hold: int = HOLD) -> dict:
    """T-235 statistics on entries ``starts`` (z, zv: their z-scores): base P&L, the declared rules, the Sharpe-difference
    test and PBO."""
    rv = np.array([PPY / hold * float(np.sum(lr[a + 1:a + hold + 1] ** 2)) for a in starts])
    base = vv[starts] ** 2 - rv
    rules = {"linear max(z,0)": np.maximum(z, 0.0), "on/off z>0.5": (z > 0.5).astype(float), "on/off z>1": (z > 1.0).astype(float)}
    R = np.column_stack([w * base for w in rules.values()])
    t = sharpe_diff_test(R[:, 0], base, block, n_boot, seed)
    pbo = (pbo_cscv(R, 8) if starts.size >= 32 else {"pbo": None}) if with_pbo else {"pbo": None}
    return {"base": base, "rules": rules, "R": R, "t": t, "pbo": pbo}


def scaled_short_variance(days, closes, vix: dict, start: str = "1991-01-01", block: int = 6, n_boot: int = 2000, seed: int = 0,
                          min_n: int = 300, min_hist: int = 120, hold: int = HOLD) -> dict:
    """T-235: monthly (21-day) short variance P&L (VIX_t/100)^2 - RV_{t,t+21} on ^GSPC closes; scaled by N_t = max(z_t, 0)
    with z_t the expanding z-score of VIX/100 minus the walk-forward HAR vol forecast (history of daily spreads strictly
    before t). Pass: Sharpe(scaled) - Sharpe(constant) > 0 at one-sided p < 0.05 (studentized block bootstrap) and PBO < 0.3
    across the declared rules {linear max(z,0), on/off z > 0.5, on/off z > 1}; min_n 300 cycles.

    Rule 10(a): 'monthly cycles' over 'the same months' name the calendar month: each month enters at its first session
    with a VIX close and a HAR forecast (the HAR refits at month starts too). The month-end anchor and every offset of the
    21-day grid are reported (Sharpe difference and p), not in the verdict."""
    days = list(days)
    c = np.asarray(closes, dtype=float)
    refit = np.array([i == 0 or days[i][:7] != days[i - 1][:7] for i in range(len(days))])
    f = har_forecast(c, refit)
    has_v = np.array([d in vix for d in days])
    vv = np.array([vix.get(d, np.nan) for d in days], dtype=float) / 100.0
    spread = np.where(has_v & np.isfinite(f), vv - np.sqrt(np.maximum(f, 1e-8)), np.nan)
    lr = np.zeros(c.size)
    lr[1:] = np.log(c[1:] / c[:-1])
    first = next((i for i, d in enumerate(days) if d >= start), None)
    if first is None:
        return {"verdict": "inconclusive", "n": 0, "reason": f"no data after {start}"}
    # expanding z-scores of the spread and of the VIX level from the days strictly before each day
    sp_ok = np.isfinite(spread)
    s1 = np.concatenate([[0.0], np.cumsum(np.where(sp_ok, spread, 0.0))])
    s2 = np.concatenate([[0.0], np.cumsum(np.where(sp_ok, spread ** 2, 0.0))])
    cnt = np.concatenate([[0], np.cumsum(sp_ok)])
    vl = np.where(has_v, vv, np.nan)
    v_ok = np.isfinite(vl)
    v1 = np.concatenate([[0.0], np.cumsum(np.where(v_ok, vl, 0.0))])
    v2 = np.concatenate([[0.0], np.cumsum(np.where(v_ok, vl ** 2, 0.0))])
    vc = np.concatenate([[0], np.cumsum(v_ok)])
    N = c.size
    ka, kv = cnt[:N].astype(float), vc[:N].astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        m_s = s1[:N] / ka
        sd_s = np.sqrt(np.maximum(s2[:N] / ka - m_s ** 2, 1e-12))
        z_all = np.where((ka >= min_hist) & sp_ok, (spread - m_s) / sd_s, np.nan)
        m_v = v1[:N] / kv
        sd_v = np.sqrt(np.maximum(v2[:N] / kv - m_v ** 2, 1e-12))
        zv_all = np.where((kv >= min_hist) & v_ok, (vl - m_v) / sd_v, np.nan)
    good = has_v & np.isfinite(z_all)
    good[max(0, N - hold):] = False
    starts = _month_first(days, good, start)
    n = int(starts.size)
    if n < 16:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles with a HAR forecast and spread history"}
    z, zv = z_all[starts], zv_all[starts]
    ev = _t235_eval(starts, z, zv, vv, lr, block, n_boot, seed, True, hold)
    base, rules, R, t, pbo = ev["base"], ev["rules"], ev["R"], ev["t"], ev["pbo"]
    ppy = PPY / hold
    sr = {k: float(sharpe_ratio(R[:, i], ppy)) for i, k in enumerate(rules)}
    sr_c = float(sharpe_ratio(base, ppy))
    vix_only = np.maximum(np.nan_to_num(zv, nan=0.0), 0.0) * base
    rng = np.random.default_rng(seed)
    placebo = np.maximum(rng.permutation(z), 0.0) * base
    top = np.maximum(z, 0) * base
    q = np.quantile(z, 2 / 3)
    top_share = float(top[z > q].sum() / top.sum()) if top.sum() != 0 else None
    # robustness: month-end anchor and the 21-day grid offsets
    se = _month_last(days, good, start)
    rob = {}
    if se.size >= 16:
        te = _t235_eval(se, z_all[se], zv_all[se], vv, lr, block, max(500, n_boot // 2), seed, False, hold)["t"]
        rob["month_end"] = {"n": int(se.size), "diff": te["diff"], "p": te["p"]}
    offs = []
    for k in range(hold):
        g = np.arange(first + k, N - hold, hold)
        g = g[good[g]]
        if g.size >= 16:
            tk = _t235_eval(g, z_all[g], zv_all[g], vv, lr, block, max(500, n_boot // 2), seed, False, hold)["t"]
            offs.append({"offset": int(k), "n": int(g.size), "diff": tk["diff"], "p": tk["p"],
                         "ok": bool(tk["diff"] is not None and tk["diff"] > 0 and tk["p"] < 0.05)})
    rob["grid_offsets"] = offs
    crit = [("Sharpe(linear max(z,0)) - Sharpe(constant) > 0 at one-sided p < 0.05",
             None if t["p"] is None else bool(t["diff"] > 0 and t["p"] < 0.05), t["ci"][1] is not None and t["ci"][1] < 0),
            ("PBO < 0.3 across the three declared rules", None if pbo.get("pbo") is None else bool(pbo["pbo"] < 0.3), False)]
    verdict, why = _decide(crit, n, min_n, "monthly cycles")
    rob_txt = ""
    if "month_end" in rob:
        rob_txt += f"month-end anchor diff {_s(rob['month_end']['diff'], 3)} (p {_f(rob['month_end']['p'], 3)}); "
    if offs:
        ds = [o["diff"] for o in offs if o["diff"] is not None]
        rob_txt += (f"21-day grid offsets: diff {min(ds):+.3f} to {max(ds):+.3f}, p {min(o['p'] for o in offs):.3f} to "
                    f"{max(o['p'] for o in offs):.3f}, {sum(o['ok'] for o in offs)}/{len(offs)} pass")
    reason = (f"model-free short 21-day ^GSPC variance struck at VIX^2; rule 10 (the claim names monthly cycles): {n} calendar "
              f"months entered at the first session with a VIX close {days[starts[0]]}..{days[starts[-1]]}, HAR(1,5,22) refit "
              f"monthly on an expanding window: annualised Sharpe scaled {sr['linear max(z,0)']:.2f} vs constant "
              f"{sr_c:.2f} (per-cycle difference {_s(t['diff'], 3)}, studentized one-sided p {_f(t['p'], 3)}, 95% {_ci_s(t['ci'], 3)}); "
              f"on/off z>0.5 {sr['on/off z>0.5']:.2f}, z>1 {sr['on/off z>1']:.2f}; PBO {_f(pbo.get('pbo'), 3)}; controls: "
              f"VIX-level-only scaling Sharpe {sharpe_ratio(vix_only, ppy):.2f}, random-z placebo {sharpe_ratio(placebo, ppy):.2f}, "
              f"top-tercile-z share of scaled P&L {_f(top_share, 2)}; robustness (not in the verdict): {rob_txt}" + f" — {why}")
    stat = {"rule10": "calendar month (claim: monthly cycles over the same months)", "n_cycles": n, "sharpe_annual": sr,
            "sharpe_constant": sr_c, "sharpe_diff_test": t, "pbo": pbo.get("pbo"),
            "pbo_detail": pbo, "vix_level_only_sharpe": float(sharpe_ratio(vix_only, ppy)),
            "random_z_placebo_sharpe": float(sharpe_ratio(placebo, ppy)), "top_tercile_share": top_share,
            "mean_z": float(z.mean()), "share_z_positive": float((z > 0).mean()), "robustness": rob, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def vix1d_premium(days, closes, vix1d: dict, vix: Optional[dict] = None, events: Optional[dict] = None, block: int = 5,
                  n_boot: int = 2000, seed: int = 0, min_n: int = 500) -> dict:
    """T-529: x_t = (VIX1D_t/100)^2/365 - r_{t+1}^2 with r_{t+1} the next trading day's ^GSPC close-to-close log return.
    Pass: mean > 0 with the 95% studentized block-bootstrap CI (5-day blocks) excluding 0, and positive in both halves;
    min_n 500 one-day windows. /252 and VIX-implied daily variance ((VIX/100)^2 x 30/365 / 21) reported; event days
    (FOMC decision, CPI, employment report) reported separately."""
    days = list(days)
    c = np.asarray(closes, dtype=float)
    idx = [i for i in range(len(days) - 1) if days[i] in vix1d]
    if len(idx) < 8:
        return {"verdict": "inconclusive", "n": len(idx), "reason": f"only {len(idx)} VIX1D days with a next ^GSPC close"}
    ii = np.array(idx)
    v = np.array([vix1d[days[i]] for i in idx]) / 100.0
    r2 = np.log(c[ii + 1] / c[ii]) ** 2
    x = v ** 2 / 365.0 - r2
    x252 = v ** 2 / 252.0 - r2
    n = int(x.size)
    lo, hi = stud_ci(x, block, 0.95, n_boot, seed)
    hv = _halves(x)
    crit = [("mean > 0 with 95% CI excluding 0 (/365)", None if lo is None else bool(lo > 0), hi is not None and hi < 0),
            ("mean > 0 in both halves", all(h is not None and h > 0 for h in hv), False)]
    s = 1e4
    parts = [f"mean {x.mean() * s:+.4f} %^2 per day ({_ci_s((lo, hi), 4, s)}), halves {hv[0] * s:+.4f}/{hv[1] * s:+.4f}",
             f"/252 convention {x252.mean() * s:+.4f}", f"implied {np.mean(v ** 2 / 365) * s:.4f} vs realised {r2.mean() * s:.4f}"]
    rep = {}
    if vix:
        vx = np.array([vix.get(days[i], np.nan) for i in idx]) / 100.0
        ok = np.isfinite(vx)
        if ok.any():
            xv = vx[ok] ** 2 * (30.0 / 365.0) / HOLD - r2[ok]
            rep["vix_scaled_daily_premium"] = float(xv.mean())
            rep["vix1d_premium_same_days"] = float(x[ok].mean())
            parts.append(f"VIX-scaled 1-day premium {xv.mean() * s:+.4f} on the same {int(ok.sum())} days")
    if events:
        evd = set().union(*events.values()) if events else set()
        nxt = np.array([days[i + 1] in evd for i in idx])
        if nxt.any():
            rep["event_days"] = {"n": int(nxt.sum()), "mean": float(x[nxt].mean()), "non_event_mean": float(x[~nxt].mean())}
            lo2, hi2 = stud_ci(x[~nxt], block, 0.95, n_boot, seed)
            rep["ex_events_ci"] = [lo2, hi2]
            parts.append(f"next day an event ({'/'.join(sorted(events))}) on {int(nxt.sum())} days: mean {x[nxt].mean() * s:+.4f}; "
                         f"ex-events {x[~nxt].mean() * s:+.4f} ({_ci_s((lo2, hi2), 4, s)})")
    verdict, why = _decide(crit, n, min_n, "one-day windows")
    reason = (f"model-free: (VIX1D/100)^2/365 vs next-day ^GSPC squared log return, {n} days {days[idx[0]]}..{days[idx[-1]]} "
              f"(rule 10 does not apply: one-day windows have a single grid phase): "
              + "; ".join(parts) + f" — {why}")
    stat = {"rule10": "not applicable (one-day windows)", "n_days": n, "mean": float(x.mean()), "ci95": [lo, hi], "halves": hv,
            "mean_252": float(x252.mean()),
            "mean_implied": float(np.mean(v ** 2 / 365)), "mean_realised": float(r2.mean()), **rep, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ================================================================================ VIX strip on a captured chain ==

def strip_variance(chain_values, quote_day: str, r: float, target_days: int = 30, root: str = "SPXW") -> Optional[dict]:
    """CBOE VIX-method 30-day variance from one captured SPX chain (PM-settled ``root`` series): mid quotes of OTM options,
    strikes after two consecutive zero bids dropped, forward from the strike with the smallest |C - P|, near and next
    terms bracketing ``target_days`` interpolated in total variance. T in calendar days / 365 from the quote day close."""
    by: dict = {}
    for v in chain_values:
        sym = v.get("sym") or ""
        mt = re.match(r"([A-Z]+)", sym)
        if not mt or mt.group(1) != root:
            continue
        b, a = v.get("bid"), v.get("ask")
        if b is None or a is None or a <= 0:
            continue
        by.setdefault(v["expiry"], {}).setdefault(float(v["strike"]), {})[v["type"]] = ((float(b) + float(a)) / 2.0, float(b))
    q = date.fromisoformat(quote_day)
    terms = sorted(((date.fromisoformat(e) - q).days, e) for e in by if (date.fromisoformat(e) - q).days > 0)
    near = [t for t in terms if t[0] <= target_days]
    nxt = [t for t in terms if t[0] > target_days]
    if not near or not nxt:
        return None

    def one(e, nd):
        T = nd / 365.0
        rec = by[e]
        both = [K for K in sorted(rec) if "call" in rec[K] and "put" in rec[K] and rec[K]["call"][1] > 0 and rec[K]["put"][1] > 0]
        if not both:
            return None
        ks = min(both, key=lambda K: abs(rec[K]["call"][0] - rec[K]["put"][0]))
        F = ks + math.exp(r * T) * (rec[ks]["call"][0] - rec[ks]["put"][0])
        below = [K for K in sorted(rec) if K <= F]
        if not below:
            return None
        K0 = below[-1]
        sel = {}
        zeros = 0
        for K in sorted((K for K in rec if K < K0), reverse=True):
            p = rec[K].get("put")
            if p is None or p[1] <= 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            sel[K] = p[0]
        zeros = 0
        for K in sorted(K for K in rec if K > K0):
            cl = rec[K].get("call")
            if cl is None or cl[1] <= 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            sel[K] = cl[0]
        mids = [x[0] for x in (rec[K0].get("put"), rec[K0].get("call")) if x is not None]
        if not mids:
            return None
        sel[K0] = float(np.mean(mids))
        ks_sorted = sorted(sel)
        tot = 0.0
        for i, K in enumerate(ks_sorted):
            if len(ks_sorted) == 1:
                dk = 1.0
            elif i == 0:
                dk = ks_sorted[1] - K
            elif i == len(ks_sorted) - 1:
                dk = K - ks_sorted[i - 1]
            else:
                dk = (ks_sorted[i + 1] - ks_sorted[i - 1]) / 2.0
            tot += dk / K ** 2 * math.exp(r * T) * sel[K]
        return {"var": 2.0 / T * tot - (F / K0 - 1.0) ** 2 / T, "T": T, "forward": F, "n_strikes": len(sel), "expiry": e}

    a, b = one(near[-1][1], near[-1][0]), one(nxt[0][1], nxt[0][0])
    if a is None or b is None:
        return None
    n1, n2, n30 = near[-1][0], nxt[0][0], target_days
    w = (n2 - n30) / (n2 - n1)
    var30 = (a["T"] * a["var"] * w + b["T"] * b["var"] * (1 - w)) * 365.0 / n30
    return {"var30": var30, "vol30": math.sqrt(max(var30, 0.0)) * 100, "near": a, "next": b}


# =================================================================================================== harnesses ==

def _measured_scale(smile: Optional[Smile]) -> tuple:
    if smile is None or not smile.curves:
        return None, ""
    s = float(smile.ratio(1.0, 30))
    return s, f"; measured ATM IV / VIX = {s:.3f} at 30 DTE (mean of {smile.n_days} captured SPY smile quote days)"


def b6_var_short_straddle_tercile(archive):
    """T-101: tercile-conditioned short straddle (top minus bottom of VIX - RV21), walk-forward out of sample."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    fr = _spy_frame(archive)
    pre, note = None, ""
    if _has(archive, GSPC_B):                       # labelled sensitivity only: the claim names SPY log returns
        gd, gc, _ = _daily(archive, GSPC_B)
        vix = _index(archive, VIX_B)
        first = fr["days"][0] if fr["days"] else "9999"
        lr_end = _logret_end(gc)
        st = np.array([i for i, d in enumerate(gd) if d < first and d in vix and i >= HOLD], dtype=np.int64)
        if st.size > 2 * HOLD:
            pre = np.array([vix[gd[a]] for a in st]) - 100.0 * trailing_rv_vol(lr_end, st)
            note = (f" (first training window = the {st.size} pre-SPY daily entries {gd[st[0]]}..{gd[st[-1]]} with RV21 from "
                    f"^GSPC price returns, a series the claim does not name; SPY starts {first}; every SPY entry is then out "
                    f"of sample)")
    rep = straddle_tercile(fr, pre_sensitivity=pre, sensitivity_note=note)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_gamma_scalp_long_straddle(archive):
    """T-123: delta-hedged long straddle at 0.90 x VIX; mean P&L / vega, upper CI < 0."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    anchor = None
    if _has(archive, GSPC_B):                       # the BTZ control: ^GSPC 1990-2007 close-to-close
        gd, gc, _ = _daily(archive, GSPC_B)
        vix = _index(archive, VIX_B)
        anchor = {"days": gd, "close": gc, "vix": [vix.get(d, np.nan) for d in gd], "label": "^GSPC"}
    rep = gamma_scalp(_spy_frame(archive), anchor=anchor)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_theta_harvest_45dte(archive):
    """T-156: 45-DTE 0.16-delta strangle, 21-DTE exit vs hold, P&L per day."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    rep = theta_harvest(_spy_frame(archive), smile=_smile(archive))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_theta_ladder(archive):
    """T-157: 4-rung weekly quarter-size put ladder vs monthly full-size entry, drawdown ratio."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    rep = theta_ladder(_spy_frame(archive))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_vrp_short_straddle_hedged(archive):
    """T-233: daily delta-hedged short straddle at 0.81 x VIX (and the measured ATM/VIX scale), after 0.5 vol pt."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    s, note = _measured_scale(_smile(archive))
    rep = vrp_hedged_short(_spy_frame(archive), s, note)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def _overnight_capture(available_at: str) -> bool:
    """A capture inside Cboe's overnight (global trading hours) SPX session, 20:15-09:15 ET: 01:15-13:15 UTC under both
    EST and EDT. Its quotes are live overnight quotes, not the 16:15 ET close the VIX prints."""
    hhmm = (available_at or "")[11:16]
    return "01:15" <= hhmm < "13:15"


def _truncation_checks(archive, vix_full: dict, dtb3: dict, closes: Optional[dict] = None) -> list:
    """Strip vs VIX^2 on each captured SPX chain, with the capture timing: whether the capture falls in the overnight
    session, the latest trade time on the chain and the chain-implied spot (near-term forward discounted at the bill rate,
    dividends ignored, ~0.1%) against the quote day's index close."""
    out = []
    tdays = sorted(vix_full)
    for nm in _names(archive, SPX_CHAIN_P):
        rows = list(archive.load(nm))
        if not rows:
            continue
        qd = _quote_day(rows[0].get("available_at") or "", tdays)
        if qd is None or qd not in vix_full:
            continue
        r = float(bill_rates([qd], dtb3)[0])
        sv = strip_variance([x["value"] for x in rows], qd, r)
        if sv is None:
            cap = str(rows[0].get("available_at") or "")
            out.append({"bundle": nm, "quote_day": qd, "error": None, "captured_at": cap[:16].replace("T", " "),
                        "overnight_session": _overnight_capture(cap)})
            continue
        vx2 = (vix_full[qd] / 100.0) ** 2
        lt = max((str(x["value"].get("last_time") or "") for x in rows), default="")
        cap = str(rows[0].get("available_at") or "")
        cl = (closes or {}).get(qd)
        gap = (sv["near"]["forward"] * math.exp(-r * sv["near"]["T"]) / cl - 1.0) if cl else None
        out.append({"bundle": nm, "quote_day": qd, "vix": vix_full[qd], "strip_vol30": sv["vol30"], "error": sv["var30"] / vx2 - 1.0,
                    "captured_at": cap[:16].replace("T", " "), "overnight_session": _overnight_capture(cap),
                    "latest_trade": lt[:16].replace("T", " ") or None, "implied_spot_vs_close": gap,
                    "near": {k: sv["near"][k] for k in ("expiry", "n_strikes", "forward")},
                    "next": {k: sv["next"][k] for k in ("expiry", "n_strikes", "forward")}})
    return out


def b6_var_variance_strip_win_rate(archive):
    """T-234: VIX^2 > next 21-day ^GSPC realised variance in > 75% of non-overlapping months since 1990."""
    miss = _missing(archive, [GSPC_B, VIX_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    vix = _index(archive, VIX_B)
    i0 = max(0, bisect_left(gd, "1990-01-01") - 1)          # keep the prior close: the first month's returns start there
    days, close = gd[i0:], gc[i0:]
    checks = {}
    if _has(archive, SPY_B):
        sd, sc, sa = _daily(archive, SPY_B)
        spa, spc = dict(zip(sd, sa)), dict(zip(sd, sc))
        checks["dividend-adjusted SPY"] = np.array([spa.get(d, np.nan) for d in days])
        checks["SPY price-return (raw close)"] = np.array([spc.get(d, np.nan) for d in days])
    trunc = None
    if _names(archive, SPX_CHAIN_P):
        vix_full = _index(archive, VIX_B, filtered=False)
        gfull = _daily_from_rows(_rows(archive, GSPC_B, filtered=False))
        trunc = _truncation_checks(archive, vix_full, _series(archive, DTB3_B) if _has(archive, DTB3_B) else {},
                                   dict(zip(gfull[0], gfull[1])))
    ms, _ = _measured_scale(_smile(archive))
    atm = {"harness_short_straddle ratio": 0.81, "0.90": 0.90}
    if ms is not None:
        atm["measured on the captured SPY smile"] = ms
    rep = vix2_win_rate(days, close, [vix.get(d, np.nan) for d in days], checks=checks, truncation=trunc, atm_scales=atm)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_iv_rv_spread_scaled(archive):
    """T-235: short variance scaled by max(z, 0) of VIX minus a walk-forward HAR forecast vs constant notional."""
    miss = _missing(archive, [GSPC_B, VIX_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    rep = scaled_short_variance(gd, gc, _index(archive, VIX_B))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_variance_swap_units(archive):
    """T-540: short variance struck at VIX^2 settled on next-21-day SPY RV, %^2 per month."""
    miss = _missing(archive, [SPY_B, VIX_B])
    if miss:
        return miss
    spy_rows = _rows(archive, SPY_B)
    vix_rows = _rows(archive, VIX_B)
    sd, sc, sa = _daily_from_rows(spy_rows)
    vix = index_closes(vix_rows)
    checks = {"dividend-adjusted SPY": sa}
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        gp = dict(zip(gd, gc))
        checks["^GSPC (SPX vs SPY)"] = np.array([gp.get(d, np.nan) for d in sd])
    intra = intraday_var_by_day(_rows(archive, HOURLY_SPY_B)) if _has(archive, HOURLY_SPY_B) else None
    rep = short_variance_units(sd, sc, [vix.get(d, np.nan) for d in sd], checks=checks, intraday=intra)
    if "stat" in rep:
        ov = variance_risk_premium(vix_rows, spy_rows, window=HOLD, symbol="SPY")
        rep["stat"]["overlapping_vol_units_T48"] = {k: ov.get(k) for k in ("n", "vrp_vol_points", "vrp_variance_points", "p_value",
                                                                          "share_positive", "halves")}
        rep["reason"] = rep["reason"].replace(" — ", f"; overlapping daily windows (T-48 vol units) VRP {ov.get('vrp_vol_points', float('nan')) * 100:+.2f} vol pts, "
                                                     f"p {ov.get('p_value', float('nan')):.4f} (reported) — ", 1)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_vix1d_premium(archive):
    """T-529: (VIX1D/100)^2/365 exceeds the next day's squared ^GSPC log return on average."""
    miss = _missing(archive, [VIX1D_B, GSPC_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    vix = _index(archive, VIX_B) if _has(archive, VIX_B) else None
    events = {}
    for lab, nm in EVENT_B.items():
        if _has(archive, nm):
            ds = set()
            for r in _rows(archive, nm):
                v = r["value"]
                d = v.get("decision_day") or v.get("day")
                if d and not v.get("future"):
                    ds.add(d)
            events[lab] = ds
    rep = vix1d_premium(gd, gc, _index(archive, VIX1D_B), vix=vix, events=events or None)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


HARNESSES = {
    "b6_var_short_straddle_tercile": b6_var_short_straddle_tercile,
    "b6_var_gamma_scalp_long_straddle": b6_var_gamma_scalp_long_straddle,
    "b6_var_theta_harvest_45dte": b6_var_theta_harvest_45dte,
    "b6_var_theta_ladder": b6_var_theta_ladder,
    "b6_var_vrp_short_straddle_hedged": b6_var_vrp_short_straddle_hedged,
    "b6_var_variance_strip_win_rate": b6_var_variance_strip_win_rate,
    "b6_var_iv_rv_spread_scaled": b6_var_iv_rv_spread_scaled,
    "b6_var_variance_swap_units": b6_var_variance_swap_units,
    "b6_var_vix1d_premium": b6_var_vix1d_premium,
}

THEORY_MAP = {
    "T-101": "b6_var_short_straddle_tercile",
    "T-123": "b6_var_gamma_scalp_long_straddle",
    "T-156": "b6_var_theta_harvest_45dte",
    "T-157": "b6_var_theta_ladder",
    "T-233": "b6_var_vrp_short_straddle_hedged",
    "T-234": "b6_var_variance_strip_win_rate",
    "T-235": "b6_var_iv_rv_spread_scaled",
    "T-540": "b6_var_variance_swap_units",
    "T-529": "b6_var_vix1d_premium",
}
