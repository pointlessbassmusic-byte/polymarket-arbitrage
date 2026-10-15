"""
Batch 6a, group ``surf``: surface and index relative value.
===========================================================

Ten options-library claims, each tested on its own claim, trial.pass and trial.min_n as worded:

  * T-159  VIX/VIX3M regime filter: within each VIX tercile, the 21-day SPY variance risk premium is higher on contango days
           (VIX/VIX3M < 0.95) than on backwardation days (> 1.05). Each tercile is a criterion (the claim's "each"), plus
           the pass rule's 2 of 3. Data-only; a MODEL-PRICED short strangle is reported as the trial's secondary.
  * T-227  SKEW and realised left tails: windows starting with SKEW above its trailing 80th percentile do NOT carry 1 pp or
           more extra 21-day ^GSPC returns below -2 VIX-implied sigma, against windows starting below its 20th percentile.
  * T-228  The SKEW-implied 2-sigma probability (white-paper mapping 0.0228 + 0.0270 (SKEW - 100) / 10) exceeds the realised
           frequency of 21-day -2 VIX-sigma drops by more than 2 pp on average.
  * T-229  MODEL-PRICED 30-DTE 25d/10d SPX put spread: payoff / debit when bought in cheap-SKEW months against every month.
  * T-237  VXN - VIX 60-day z-score extremes: s [(VXN - VIX) - (RV_QQQ - RV_SPY)] over the next 21 days is positive,
           pooled AND on each side (wide z > +2 and narrow z < -2 are both asserted by the claim).
  * T-239  MODEL-PRICED rolling 25-delta VIX call overlay (Black-76 on a VIX3M/VIX forward, VVIX as IV) on a 1%/yr budget
           cuts SPY's maximum drawdown by more than 25%. Drawdowns on DAILY equity (the calls marked to model daily).
  * T-240  VVIX exceeds the realised 21-day vol of daily log changes in spot VIX in more than 70% of non-overlapping months.
  * T-249  The 1-to-3-month forward variance premium fraction exceeds the spot 30-day premium fraction.
  * T-511  SPY Friday-to-Monday close variance is below 1.5 x the weekday single-night variance (the data-only part).
  * T-538  COR1M exceeds the realised average pairwise correlation of the index constituents (only a sector-SPDR proxy is
           archived; see the harness for why that caps the verdict).

Conventions (house rules)
  * Point in time. A decision at a close uses index closes of that day (CBOE indices are final at the close) and the prior
    FRED DTB3 print (published the next day), converted from the 91-day discount yield to a continuous rate
    r = -ln(1 - d/100 * 91/360) / (91/365). Forward windows start with the next day's return. Rows that were not yet
    available when their bundle was captured are dropped. Trailing percentiles use the 252 values BEFORE the decision day.
  * Realised variance is the sum of squared daily log returns annualised with 252 / window (no mean removed); realised vol
    in vol points is 100 sqrt(that). Equity realised variance uses dividend-adjusted closes (an ex-dividend price drop is not
    volatility). ^GSPC is a price index (no dividends), so its close is used as is. Option payoffs settle on RAW closes.
  * SPY options (T-159 secondary, T-239 put control) are priced on the dividend forward S - PV(D) when an ex-date falls in
    the option's life: D is derived from the adjclose/close ratio step, its amount forecast point in time as the last
    dividend gone ex at or before the decision (ex-dates follow SPY's fixed quarterly schedule). SPX options (T-229) carry
    a continuous yield q: SPY's trailing-12-month dividends over its close, known at the decision. Before that is
    computable (SPY's first full year ends 1994-01-31) no point-in-time S&P 500 yield is archived, so the 1991-01..1994-01
    entries use an ASSUMED constant q = 3.0% (PRE_YIELD, stated ex ante), never a value computed from later dividends.
  * MODEL-PRICED results price legs at the IV proxy the claim names and say so in the reason; the archive has only two
    captured chain days, so no traded version can be tested here.
  * ^GSPC claims (T-227, T-228, T-229) run on the index's OWN trading calendar: a "21-trading-day" window is 21 ^GSPC
    sessions, and SKEW and VIX enter as the last print at or before each session (point in time; a print older than 15
    calendar days is not used). The S&P 500 index itself is used for the whole sample, as the claims word it; T-228
    reports the SPY splice (SPY closes from 1993-01-29) as a sensitivity.

Entry calendars (house rule 10: a verdict must not depend on an arbitrary grid phase)
  (a) A claim that names a calendar is tested on it. T-229's "monthly 30-DTE" SPX spread uses SPX's standard monthly
      expiry (the third Friday, or the prior session when it is a holiday), bought at the close of the session nearest 30
      calendar days before it (ties to the earlier session), or at the previous expiry's close when that comes later
      (holds never overlap). T-239's "rolling 1-month" VIX calls follow the VIX monthly expiry (the Wednesday 30 days
      before the next month's third Friday; holiday rules as CBOE's), each bought at one expiry's close and held to the
      next; its SPY-put control rolls on the SPX monthly expiries the same way. T-240's "non-overlapping months" are
      calendar months, each entered at its first session (its secondary VIX call ratio rolls on the VIX expiries).
  (b) A plain non-overlapping k-session grid (T-228 and T-538: 21 sessions; T-249: 63) has k equally valid start
      offsets. The claimed statistic is computed on EVERY offset and on the POOLED overlapping daily entries of all
      offsets, whose studentized circular block bootstrap uses blocks of max(2, the module's cycle block) holds (126
      sessions here, >= 2 x hold). The pooled estimate is the primary statistic of every criterion; the reason reports
      the per-offset range of the statistic and of its bound and how many offsets pass. n stays in the claim's units:
      the number of distinct holds the pooled entries span (the cycle count of the densest non-overlapping grid).
      T-159's MODEL-PRICED strangle secondary and T-239's grid sensitivity are reported the same way.
  (c) Daily series and event entries have no grid phase: T-159's and T-227's daily-start windows (the trials' own
      design; their 42-session-block sensitivities are reported), T-237's z-score events (data-determined dates), and
      T-511's weekly statistics are unaffected.

Statistics
  * Intervals are circular block bootstraps (2000 resamples, seed 0) of the statistic the claim names. Means use the
    studentized (bootstrap-t) form: each resample's mean is studentized by its own Bartlett long-run s.e. with bandwidth =
    block (as backtest_eval.block_bootstrap_pvalue). A difference of two group means on one timeline is bootstrapped PAIRED:
    blocks of the shared timeline are resampled, each day keeping its labels, studentized by the long-run s.e. of the
    difference's influence function. Ratios (drawdown ratio, variance ratio) and proportions use percentile intervals.
    Overlapping windows use blocks at least as long as the overlap.
  * "Lower/upper 95% bound" in a pass rule is read as a ONE-SIDED 95% confidence bound (the test of the stated null at 5%);
    "95% CI" is two-sided. Every reason also prints the two-sided interval. A trial that names deflation over a declared
    set of variants applies Bonferroni over that set to the level or the p-value.
  * min_n is counted in the claim's own units. Below min_n a claim cannot be supported, and a failing criterion counts only
    when it fails decisively (its interval wholly on the wrong side); otherwise it is reported as not decisive.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented ->
at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from mandel.experiments.options_market import _binom_two_sided_ci
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, index_closes
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

PPY = 252
MONTH = 21
N_BOOT = 2000
SQRT2 = math.sqrt(2.0)
MP = "MODEL-PRICED"

SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
QQQ_B = "daily-history-QQQ"
IWM_B = "daily-history-IWM"
VIX_B = "cboe-VIX-history"
VIX3M_B = "cboe-VIX3M-history"
VVIX_B = "cboe-VVIX-history"
SKEW_B = "cboe-SKEW-history"
VXN_B = "cboe-VXN-history"
RVX_B = "cboe-RVX-history"
COR1M_B = "cboe-COR1M-history"
DTB3_B = "fred-DTB3"
SPX_CHAIN_P = "options-chain-SPX-"
SMILE_P = "spy-smile-"
KAPPA_CHAIN = "options-chain-SPX-2026-10-14"          # T-229: kappa is calibrated once, on this capture
SECTORS_ALL = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
SECTORS_LEGACY = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")   # listed 1998; XLRE 2015, XLC 2018
PRE_YIELD = 0.03        # T-229: assumed S&P 500 dividend yield (stated ex ante) before SPY's trailing yield is computable


# =================================================================================================== statistics ==

def _lrv(x, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance, identical to backtest_eval._hac_var (bandwidth ``bw``). Long bandwidths (the
    pooled overlapping series use 126 sessions) take the autocovariances from an FFT: the same sums at O(n log n)."""
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


def _blk(block: int, n: int) -> int:
    return max(1, min(int(block), n // 4))


def stud_mean(x, block: int, n_boot: int = N_BOOT, seed: int = 0) -> Optional[dict]:
    """Studentized circular block bootstrap of a mean: {est, se, t (bootstrap t-statistics), n, block}; None below 8 obs.
    ``t`` is None when the series is constant (no sampling variation)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None
    b = _blk(block, n)
    m = float(x.mean())
    se = math.sqrt(float(_lrv(x[None, :], b)[0]) / n)
    out = {"est": m, "se": se, "t": None, "n": int(n), "block": b}
    if not se > 1e-14:
        out["se"] = 0.0
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        xb = x[_boot_idx(rng, n, b, k)]
        ts.append((xb.mean(axis=1) - m) / np.sqrt(_lrv(xb, b) / n))
    out["t"] = np.concatenate(ts)
    return out


def stud_group(x, a, b, block: int, n_boot: int = N_BOOT, seed: int = 0, min_count: int = 4) -> Optional[dict]:
    """mean(x | a) - mean(x | b) for two masks on ONE timeline (they may overlap: a subset against all). Blocks of the
    shared timeline are resampled with their labels (paired), and each resample is studentized by the Bartlett long-run
    s.e. of the influence function psi_i = n (a_i (x_i - m_a) / n_a - b_i (x_i - m_b) / n_b)."""
    x = np.asarray(x, dtype=float)
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    n = x.size
    if n < 8 or a.sum() < min_count or b.sum() < min_count:
        return None
    bl = _blk(block, n)

    def stat(xb, ab, bb):
        ca, cb = ab.sum(axis=1), bb.sum(axis=1)
        na, nb = np.maximum(ca, 1), np.maximum(cb, 1)
        ma = (xb * ab).sum(axis=1) / na
        mb = (xb * bb).sum(axis=1) / nb
        psi = n * (ab * (xb - ma[:, None]) / na[:, None] - bb * (xb - mb[:, None]) / nb[:, None])
        return ma - mb, np.sqrt(_lrv(psi, bl) / n), (ca > 0) & (cb > 0), ma, mb

    d0, se0, _, ma0, mb0 = stat(x[None, :], a[None, :], b[None, :])
    out = {"est": float(d0[0]), "se": float(se0[0]), "t": None, "n": int(n), "block": bl, "n_a": int(a.sum()),
           "n_b": int(b.sum()), "mean_a": float(ma0[0]), "mean_b": float(mb0[0])}
    if not out["se"] > 1e-14:
        out["se"] = 0.0
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        idx = _boot_idx(rng, n, bl, k)
        d, se, ok, _, _ = stat(x[idx], a[idx], b[idx])
        ok &= se > 1e-14
        ts.append((d[ok] - out["est"]) / se[ok])
    out["t"] = np.concatenate(ts)
    return out


def lower_bound(bt: Optional[dict], level: float = 0.95) -> Optional[float]:
    """One-sided lower confidence bound at ``level`` from a studentized bootstrap."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return bt["est"]
    return bt["est"] - float(np.quantile(bt["t"], level)) * bt["se"]


def upper_bound(bt: Optional[dict], level: float = 0.95) -> Optional[float]:
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return bt["est"]
    return bt["est"] - float(np.quantile(bt["t"], 1.0 - level)) * bt["se"]


def two_sided(bt: Optional[dict], level: float = 0.95) -> tuple:
    a = (1.0 - level) / 2.0
    return lower_bound(bt, 1.0 - a), upper_bound(bt, 1.0 - a)


def p_greater(bt: Optional[dict], c: float = 0.0) -> Optional[float]:
    """One-sided bootstrap-t p-value for H0: true value <= c."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return 0.0 if bt["est"] > c else 1.0
    t_obs = (bt["est"] - c) / bt["se"]
    return float((np.sum(bt["t"] >= t_obs) + 1) / (bt["t"].size + 1))


def p_less(bt: Optional[dict], c: float = 0.0) -> Optional[float]:
    """One-sided bootstrap-t p-value for H0: true value >= c."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return 0.0 if bt["est"] < c else 1.0
    t_obs = (bt["est"] - c) / bt["se"]
    return float((np.sum(bt["t"] <= t_obs) + 1) / (bt["t"].size + 1))


def pct_means(x, block: int, n_boot: int = N_BOOT, seed: int = 0) -> np.ndarray:
    """Percentile circular block-bootstrap distribution of a mean (for proportions)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    b = _blk(block, n)
    rng = np.random.default_rng(seed)
    return np.concatenate([x[_boot_idx(rng, n, b, k)].mean(axis=1) for k in _chunks(n_boot, n)])


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively; otherwise
    it is reported as not decisive (None). Appends the min_n criterion."""
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
    return f"95% CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


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


def _bt_summary(bt: Optional[dict]) -> dict:
    if bt is None:
        return {}
    return {k: v for k, v in bt.items() if k != "t"}


# ============================================================== rule 10: entry calendars and grid phases ==

POOL_HOLDS = 6          # default cycle block of the module's non-overlapping grids (6 holds)


def pool_block_len(hold: int, block_cycles: int = POOL_HOLDS) -> int:
    """Block length (sessions) of a pooled overlapping daily-entry bootstrap: ``block_cycles`` holds, at least 2 holds."""
    return max(2 * int(hold), int(block_cycles) * int(hold))


def n_holds(idx, hold: int) -> int:
    """Distinct ``hold``-session holds spanned by sorted entry indices: the cycle count of the densest non-overlapping
    grid through them (the claim's unit for a pooled estimate)."""
    idx = np.asarray(idx, dtype=np.int64)
    return 0 if idx.size == 0 else int((idx[-1] - idx[0]) // int(hold) + 1)


def _ords(days) -> np.ndarray:
    return np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)


def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def _on_or_before(ords: np.ndarray, target: int, max_back: int = 4) -> Optional[int]:
    """Index of the last session at or before ordinal ``target`` (None when none lies within ``max_back`` days)."""
    j = int(np.searchsorted(ords, target, side="right") - 1)
    return j if j >= 0 and target - int(ords[j]) <= max_back else None


def monthly_expiry_dates(cal_days) -> list:
    """SPX/SPY standard monthly expiries on an exchange calendar: the third Friday of each month, or the prior session
    when that Friday is a holiday (not a session of ``cal_days``). Only dates inside the calendar are returned."""
    cal_days = sorted(cal_days)
    if not cal_days:
        return []
    o = _ords(cal_days)
    out = set()
    for y in range(int(cal_days[0][:4]), int(cal_days[-1][:4]) + 1):
        for m in range(1, 13):
            f = _third_friday(y, m).toordinal()
            if o[0] <= f <= o[-1]:
                j = _on_or_before(o, f)
                if j is not None:
                    out.add(cal_days[j])
    return sorted(out)


def vix_expiry_dates(cal_days) -> list:
    """VIX standard monthly expiries (CBOE): the Wednesday 30 calendar days before the third Friday of the following month;
    when that Friday is a holiday, 30 days before the session preceding it; a Wednesday that is a holiday moves to the
    prior session (2024-06-18 for Juneteenth; 2025-03-18 for the Good Friday 2025-04-18). Holidays are the weekdays
    missing from ``cal_days``; only dates inside the calendar are returned."""
    cal_days = sorted(cal_days)
    if not cal_days:
        return []
    o = _ords(cal_days)
    out = set()
    for y in range(int(cal_days[0][:4]), int(cal_days[-1][:4]) + 1):
        for m in range(1, 13):
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            f = _third_friday(ny, nm).toordinal()
            if f <= o[-1]:
                j = _on_or_before(o, f)
                if j is None:
                    continue
                f = int(o[j])
            w = f - 30
            if o[0] <= w <= o[-1]:
                j = _on_or_before(o, w)
                if j is not None:
                    out.add(cal_days[j])
    return sorted(out)


def sessions_for(days, dates, max_back: int = 4) -> np.ndarray:
    """Index in ``days`` of each date: the date itself, or the prior session within ``max_back`` calendar days (a date
    missing from an aligned calendar because one series has no print falls back to the last session with all of them)."""
    if not len(days):
        return np.zeros(0, dtype=np.int64)
    o = _ords(days)
    out = set()
    for d in dates:
        t = date.fromisoformat(d).toordinal()
        if o[0] <= t:
            j = _on_or_before(o, t, max_back)
            if j is not None:
                out.add(j)
    return np.array(sorted(out), dtype=np.int64)


def rolling_cycles(expiries) -> np.ndarray:
    """(start, end) session pairs of a position rolled at each expiry: bought at expiry k's close, held to expiry k+1."""
    e = np.asarray(expiries, dtype=np.int64)
    return np.stack([e[:-1], e[1:]], axis=1) if e.size >= 2 else np.zeros((0, 2), dtype=np.int64)


def grid_cycles(n: int, hold: int, offset: int = 0) -> np.ndarray:
    """(start, end) pairs of the non-overlapping ``hold``-session grid starting at session ``offset``."""
    ts = np.arange(int(offset), n - hold, hold, dtype=np.int64)
    return np.stack([ts, ts + hold], axis=1) if ts.size else np.zeros((0, 2), dtype=np.int64)


def calendar_entries(days, expiries, dte: int, non_overlap: bool = True, ok=None) -> tuple:
    """(entries, expiries) for options of ``dte`` calendar days on an expiry calendar: each entry is the session nearest
    expiry - dte (ties to the earlier, longer-dated session); an expiry whose entry date lies more than 4 days from any
    session is skipped. ``non_overlap``: an entry before the previous expiry moves to that expiry's close. ``ok`` (bool
    per session): an entry on a session without it is skipped."""
    o = _ords(days)
    ent, exp, prev = [], [], None
    for e in np.asarray(expiries, dtype=np.int64):
        t = int(o[e]) - int(dte)
        j = int(np.searchsorted(o, t))
        cands = [k for k in (j - 1, j) if 0 <= k < o.size]
        k = min(cands, key=lambda c: (abs(int(o[c]) - t), int(o[c]))) if cands else None
        if k is not None and abs(int(o[k]) - t) <= 4:
            if non_overlap and prev is not None and k < prev:
                k = int(prev)
            if k < e and (ok is None or bool(ok[k])):
                ent.append(int(k))
                exp.append(int(e))
        prev = int(e)
    return np.array(ent, dtype=np.int64), np.array(exp, dtype=np.int64)


def month_first(days, ok=None, start: str = "") -> np.ndarray:
    """First session of each calendar month (on or after ``start``) where ``ok`` holds."""
    out, seen = [], set()
    for i, d in enumerate(days):
        if d < start or d[:7] in seen or (ok is not None and not ok[i]):
            continue
        seen.add(d[:7])
        out.append(i)
    return np.array(out, dtype=np.int64)


def offset_of(idx, hold: int) -> np.ndarray:
    """Grid offset of each entry: offset 0 is the grid through the first entry (the grid the claim's start date gives)."""
    idx = np.asarray(idx, dtype=np.int64)
    return (idx - idx[0]) % int(hold) if idx.size else idx


def _rng(vals, nd: int = 2, scale: float = 1.0) -> str:
    v = [x * scale for x in vals if x is not None and math.isfinite(x)]
    return "n/a" if not v else f"{min(v):+.{nd}f} to {max(v):+.{nd}f}"


def asof_series(days, series: dict, max_age: int = 15) -> tuple:
    """(values, fresh) on ``days``: the last print of ``series`` at or before each day (point in time; NaN before the
    first print or when the last print is more than ``max_age`` calendar days old) and whether the day has its own."""
    ks = sorted(series)
    ko = _ords(ks) if ks else np.zeros(0, dtype=np.int64)
    o = _ords(days)
    vals = np.full(len(days), np.nan)
    fresh = np.zeros(len(days), dtype=bool)
    for i, d in enumerate(days):
        j = bisect_right(ks, d) - 1
        if j >= 0 and o[i] - ko[j] <= max_age:
            vals[i] = series[ks[j]]
            fresh[i] = ks[j] == d
    return vals, fresh


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
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
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured."""
    cap = getattr(archive.get(name), "created_at", None) if filtered else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    """(days, raw close, adjclose); a bar without adjclose carries the previous adj/close ratio."""
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        if c is None or not float(c) > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float("nan"))
    days = sorted(by)
    close = np.array([by[d][0] for d in days], dtype=float)
    adj = np.array([by[d][1] for d in days], dtype=float)
    ratio = 1.0
    for i in range(len(days)):
        if np.isfinite(adj[i]):
            ratio = adj[i] / close[i]
        else:
            adj[i] = close[i] * ratio
    return days, close, adj


def _daily(archive, name: str) -> tuple:
    return _daily_from_rows(_rows(archive, name))


def _index(archive, name: str, filtered: bool = True) -> dict:
    return index_closes(_rows(archive, name, filtered))


def _series(archive, name: str) -> dict:
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
    """Point-in-time forecast of the next dividend: the last one gone ex at or before each day (the first before any)."""
    div = np.asarray(div, dtype=float)
    nz = np.nonzero(div > 0)[0]
    out = np.zeros(div.size)
    if nz.size == 0:
        return out
    last = float(div[nz[0]])
    for i in range(div.size):
        if div[i] > 0:
            last = float(div[i])
        out[i] = last
    return out


def trailing_yield(days: Sequence[str], close, adj, pre: Optional[float] = None) -> np.ndarray:
    """Trailing-12-month cash dividends / close, known at each close. Before one full year of dividend history the yield is
    not yet computable: those days get ``pre``, a constant stated ex ante (default ``PRE_YIELD``), never a later value."""
    pre = PRE_YIELD if pre is None else float(pre)
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = dividends(close, adj)
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    cum = np.concatenate([[0.0], np.cumsum(div)])
    out = np.full(len(days), np.nan)
    j = 0
    for i in range(len(days)):
        while ords[j] <= ords[i] - 365:
            j += 1
        if ords[i] - ords[0] >= 365:
            out[i] = (cum[i + 1] - cum[j]) / close[i]
    out[~np.isfinite(out)] = pre            # point in time: no back-fill from the first full-year value
    return out


def make_frame(days, close, adj=None, vix=None, rate=None, div=None, extra: Optional[dict] = None) -> dict:
    """Aligned daily arrays: ISO days, ordinals, raw close, adjclose, cash dividend by ex-day and its point-in-time
    forecast, VIX (vol points), continuous bill rate; ``extra`` arrays are carried as given."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = np.zeros(close.size) if div is None else np.asarray(div, dtype=float)
    fr = {"days": days, "ords": np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64),
          "close": close, "adj": close.copy() if adj is None else np.asarray(adj, dtype=float), "div": div,
          "fc": div_forecast(div), "vix": np.full(close.size, np.nan) if vix is None else np.asarray(vix, dtype=float),
          "rate": np.zeros(close.size) if rate is None else np.asarray(rate, dtype=float)}
    for k, v in (extra or {}).items():
        fr[k] = np.asarray(v, dtype=float)
    return fr


def frame_on(days, close, adj, keep: Sequence[str], dtb3: Optional[dict] = None, indices: Optional[dict] = None) -> dict:
    """A make_frame restricted to the days in ``keep`` (sorted subset of ``days``); a dividend going ex on a dropped day is
    paid on the next kept day. ``indices`` maps a name to a {day: close} dict; 'vix' fills the frame's vix."""
    keep_set = set(keep)
    div_full = dividends(close, adj)
    sel, div, carry = [], [], 0.0
    for i, d in enumerate(days):
        carry += div_full[i]
        if d in keep_set:
            sel.append(i)
            div.append(carry)
            carry = 0.0
    d2 = [days[i] for i in sel]
    idx = indices or {}
    extra = {k: [v[d] for d in d2] for k, v in idx.items() if k != "vix"}
    vix = [idx["vix"][d] for d in d2] if "vix" in idx else None
    return make_frame(d2, np.asarray(close)[sel], adj=np.asarray(adj)[sel], vix=vix,
                      rate=bill_rates(d2, dtb3) if dtb3 else None, div=np.array(div), extra=extra)


def _pv_div(fr: dict, t: int, e: int, r: float) -> float:
    """PV at day t of the dividends going ex on days t+1..e, each at the amount forecast at t."""
    ex = np.nonzero(fr["div"][t + 1:e + 1] > 0)[0] + t + 1
    return float(sum(fr["fc"][t] * math.exp(-r * (fr["ords"][k] - fr["ords"][t]) / 365.0) for k in ex))


def _fwd_rv(lr: np.ndarray, n: int, a: int, b: int, ppy: int = PPY) -> np.ndarray:
    """For t in 0..n-1: annualised realised variance of the daily log returns of days t+a .. t+b (inclusive), where
    lr[i] is the return from day i to day i+1."""
    c = np.concatenate([[0.0], np.cumsum(np.asarray(lr, dtype=float) ** 2)])
    t = np.arange(n)
    return (c[t + b] - c[t + a - 1]) * ppy / (b - a + 1)


def trailing_pctl(x, q: float, lookback: int = 252) -> np.ndarray:
    """q-quantile of the ``lookback`` values strictly before each day; nan for the first ``lookback`` days."""
    x = np.asarray(x, dtype=float)
    n = x.size
    out = np.full(n, np.nan)
    if n > lookback:
        w = sliding_window_view(x[:-1], lookback)
        out[lookback:] = np.quantile(w, q, axis=1)
    return out


def rolling_z(x, window: int) -> np.ndarray:
    """(x_t - mean) / sd (ddof 1) over the ``window`` values ending at t (t included: known at that close)."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.size, np.nan)
    if x.size >= window:
        w = sliding_window_view(x, window)
        sd = w.std(axis=1, ddof=1)
        z = np.where(sd > 0, (x[window - 1:] - w.mean(axis=1)) / np.where(sd > 0, sd, 1.0), np.nan)
        out[window - 1:] = z
    return out


def _roll_skew(lr: np.ndarray, n: int, window: int) -> np.ndarray:
    """Sample skewness (population moments, as backtest_eval.skewness) of the returns of days t+1..t+window."""
    w = sliding_window_view(np.asarray(lr, dtype=float), window)[:n]
    d = w - w.mean(axis=1, keepdims=True)
    s2 = (d ** 2).mean(axis=1)
    s3 = (d ** 3).mean(axis=1)
    return np.where(s2 > 0, s3 / np.where(s2 > 0, s2, 1.0) ** 1.5, 0.0)


def _align(*dicts) -> list:
    keys = set(dicts[0])
    for d in dicts[1:]:
        keys &= set(d)
    return sorted(keys)


def gspc_calendar(gd, gc, skew: dict, vix: dict) -> tuple:
    """(days, close, skew, vix, fresh) on the ^GSPC sessions from the first day with both a SKEW and a VIX print: SKEW and
    VIX as of each session (``asof_series``); ``fresh`` = both printed that session."""
    if not skew or not vix:
        return [], np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, dtype=bool)
    first = max(min(skew), min(vix))
    keep = [i for i, d in enumerate(gd) if d >= first]
    days = [gd[i] for i in keep]
    sk, fs = asof_series(days, skew)
    vx, fv = asof_series(days, vix)
    return days, np.asarray(gc, dtype=float)[keep], sk, vx, fs & fv


# ========================================================================================== option pricing ==

def _N(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def _bs(S: float, K: float, T: float, r: float, q: float, sig: float, kind: str) -> float:
    if T <= 0 or sig <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    d2 = d1 - sq
    if kind == "call":
        return S * math.exp(-q * T) * _N(d1) - K * math.exp(-r * T) * _N(d2)
    return K * math.exp(-r * T) * _N(-d2) - S * math.exp(-q * T) * _N(-d1)


def _bs_delta(S: float, K: float, T: float, r: float, q: float, sig: float, kind: str) -> float:
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    return math.exp(-q * T) * (_N(d1) if kind == "call" else _N(d1) - 1.0)


def strike_for_delta_smile(S: float, T: float, r: float, q: float, sig_fn: Callable[[float], float], target: float, kind: str,
                           lo: float, hi: float, iters: int = 80) -> Optional[float]:
    """Strike whose Black-Scholes delta at its own smile vol sig_fn(K) equals ``target``; None without a sign change."""
    def f(K):
        return _bs_delta(S, K, T, r, q, sig_fn(K), kind) - target
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def b76_call(F: float, K: float, T: float, r: float, sig: float) -> float:
    """Black-76 call on a forward F."""
    if T <= 0 or sig <= 0:
        return math.exp(-r * max(T, 0.0)) * max(F - K, 0.0)
    sq = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / sq
    return math.exp(-r * T) * (F * _N(d1) - K * _N(d1 - sq))


def b76_call_strike(F: float, T: float, sig: float, delta: float) -> float:
    """Strike of a Black-76 call with forward delta N(d1) = ``delta``."""
    from mandel.options.bs import _ninv
    sq = sig * math.sqrt(T)
    return F * math.exp(-_ninv(delta) * sq + 0.5 * sig * sig * T)


# ================================================================================ T-159: VRP by term regime ==

def vrp_regime(days, px, vix, vix3m, lo: float = 0.95, hi: float = 1.05, window: int = MONTH, block: int = 21,
               min_n: int = 60, n_thresholds: int = 4, min_half: int = 21, n_boot: int = N_BOOT, n_shift: int = 1000,
               seed: int = 0, excl_year: str = "2020") -> dict:
    """T-159. VRP_t = (VIX_t/100)^2 - RV(t+1..t+21) on aligned daily arrays (px dividend-adjusted). Within each VIX tercile
    (full-sample cut points: a stratification, not a signal): contango (VIX/VIX3M < lo) minus backwardation (> hi) mean
    VRP. Per tercile: studentized paired block bootstrap (block 21) p and the trial's block-shift null (the regime label
    circularly shifted against the VRP series) p; the larger, x ``n_thresholds`` (Bonferroni over the declared thresholds
    0.90/0.95/1.00/1.05), must be < 0.05, the difference > 0 in both walk-forward halves (a half with < ``min_half`` days in
    either cell is not testable). Criteria: EACH tercile passes (the claim: "within each VIX-level tercile"; an untestable
    tercile is a criterion not implemented, a testable one that fails is a failure) and >= 2 of 3 terciles pass (the pass
    rule). A tercile with < ``min_n`` days in either regime is not testable. n = backwardation days (the scarce regime).
    Rule 10(c): daily entries (the trial's design) have no grid phase; the studentized p with 2 x ``window``-day blocks
    is reported per tercile as a block-length sensitivity."""
    days = list(days)
    px, vix, vix3m = (np.asarray(a, dtype=float) for a in (px, vix, vix3m))
    n = len(days) - window
    if n < 100:
        return {"n": max(n, 0), "verdict": "inconclusive", "reason": f"only {max(n, 0)} aligned days with a forward window — too few to test"}
    lr = np.diff(np.log(px))
    rv = _fwd_rv(lr, n, 1, window)
    vrp = (vix[:n] / 100.0) ** 2 - rv
    vrp_vol = vix[:n] - 100.0 * np.sqrt(rv)
    ratio = vix[:n] / vix3m[:n]
    q1, q2 = np.quantile(vix[:n], [1 / 3, 2 / 3])
    terc = np.digitize(vix[:n], [q1, q2])
    con, bwd = ratio < lo, ratio > hi
    rng = np.random.default_rng(seed + 7)
    shifts = rng.integers(window + 1, max(window + 2, n - window - 1), n_shift)
    h = n // 2
    first = np.arange(n) < h
    keep_ex = np.array([not d.startswith(excl_year) for d in days[:n]])
    rows = []
    for k in range(3):
        tk = terc == k
        a, b = con & tk, bwd & tk
        na, nb = int(a.sum()), int(b.sum())
        row = {"tercile": ["low", "mid", "high"][k], "vix_range": [float(vix[:n][tk].min()), float(vix[:n][tk].max())],
               "n_contango": na, "n_backwardation": nb, "testable": na >= min_n and nb >= min_n,
               "diff_var": float(vrp[a].mean() - vrp[b].mean()) if na and nb else None,
               "diff_volpts": float(vrp_vol[a].mean() - vrp_vol[b].mean()) if na and nb else None,
               "diff_var_ex_" + excl_year: (float(vrp[a & keep_ex].mean() - vrp[b & keep_ex].mean())
                                           if (a & keep_ex).any() and (b & keep_ex).any() else None)}
        if not row["testable"]:
            row["pass"] = None
            rows.append(row)
            continue
        bt = stud_group(vrp, a, b, block, n_boot, seed)
        d0 = bt["est"]
        p_st = p_greater(bt)
        p_2h = p_greater(stud_group(vrp, a, b, 2 * window, n_boot, seed))
        null = []
        for s in shifts:
            rs = np.roll(ratio, int(s))
            a_s, b_s = (rs < lo) & tk, (rs > hi) & tk
            if a_s.any() and b_s.any():
                null.append(vrp[a_s].mean() - vrp[b_s].mean())
        null = np.asarray(null)
        p_sh = float((np.sum(null >= d0) + 1) / (null.size + 1)) if null.size else 1.0
        p_defl = min(1.0, n_thresholds * max(p_st, p_sh))
        halves = []
        for m in (first, ~first):
            aa, bb = a & m, b & m
            halves.append(float(vrp[aa].mean() - vrp[bb].mean()) if aa.sum() >= min_half and bb.sum() >= min_half else None)
        halves_ok = None if any(x is None for x in halves) else all(x > 0 for x in halves)
        comps = [d0 > 0, p_defl < 0.05, halves_ok]
        ok = False if any(c is False for c in comps) else (None if any(c is None for c in comps) else True)
        row.update({"ci_var": list(two_sided(bt)), "p_studentized": p_st, "p_block_shift": p_sh, "p_deflated": p_defl,
                    "p_studentized_2hold_blocks": p_2h, "halves_var": halves, "pass": ok})
        rows.append(row)
    n_true = sum(r["pass"] is True for r in rows)
    n_none = sum(r["pass"] is None for r in rows)
    terc_ok = True if n_true >= 2 else (False if n_true + n_none < 2 else None)
    n_bwd = int(bwd.sum())

    def _status(r):
        if not r["testable"]:
            return f"{r['tercile']} not testable ({r['n_backwardation']} backwardation / {r['n_contango']} contango days, need {min_n} each)"
        return f"{r['tercile']} " + {True: "passes", False: "fails", None: "undecided (a half not testable)"}[r["pass"]]
    # The claim says "within EACH VIX tercile": every tercile is a criterion (None when it cannot be tested: < min_n days in
    # a regime, or a half without min_half days). A testable tercile has >= min_n backwardation days, so its failure counts.
    # The pass rule's ">= 2 of 3 terciles" is kept as an additional criterion.
    crit = [(f"{r['tercile']} VIX tercile: contango-minus-backwardation VRP > 0 with deflated p < 0.05 and > 0 in both halves"
             + (f" [not testable: {r['n_backwardation']} backwardation / {r['n_contango']} contango days, need {min_n} each]"
                if not r["testable"] else (" [a half not testable]" if r["pass"] is None else f" ({r['tercile']} {'passes' if r['pass'] else 'fails'})")),
             r["pass"], False) for r in rows]
    crit.append(("at least 2 of 3 VIX terciles pass (" + "; ".join(_status(r) for r in rows) + ")", terc_ok, False))
    verdict, why = _decide(crit, n_bwd, min_n, "backwardation days")

    def _row_s(r):
        if r["diff_var"] is None:
            return f"{r['tercile']} (VIX {r['vix_range'][0]:.1f}-{r['vix_range'][1]:.1f}): {r['n_contango']} contango / {r['n_backwardation']} backwardation days, no difference"
        s = (f"{r['tercile']} (VIX {r['vix_range'][0]:.1f}-{r['vix_range'][1]:.1f}; {r['n_contango']}/{r['n_backwardation']} days) "
             f"diff {r['diff_var']*1e4:+.1f} %^2 ({r['diff_volpts']:+.2f} vol pts)")
        if not r["testable"]:
            return s + f" [not testable: < {min_n} days in a regime]"
        hv = "/".join("n/a" if x is None else f"{x*1e4:+.1f}" for x in r["halves_var"])
        return s + (f", {_ci_s(r['ci_var'], 1, 1e4)}, p stud {r['p_studentized']:.3f} / block-shift {r['p_block_shift']:.3f}"
                    f" -> deflated x{n_thresholds} {r['p_deflated']:.3f}, halves {hv} -> {'pass' if r['pass'] else ('n/a' if r['pass'] is None else 'fail')}"
                    f" (p stud with {2 * window}-day blocks {_f(r['p_studentized_2hold_blocks'], 3)}, reported)")
    return {"n": n_bwd, "min_n": min_n, "n_days": int(n), "first_day": days[0], "last_entry": days[n - 1], "lo": lo, "hi": hi,
            "tercile_cuts": [float(q1), float(q2)], "terciles": rows, "share_backwardation": float(bwd.mean()),
            "share_contango": float(con.mean()), "terciles_passing": n_true, "verdict": verdict,
            "reason_core": "; ".join(_row_s(r) for r in rows), "why": why}


def short_strangle_cycles(fr: dict, scale: float = 1.0, delta: float = 0.16, hold: int = MONTH, starts=None) -> dict:
    """MODEL-PRICED short 16-delta strangle, entered at a close, expiring at the close ``hold`` sessions later (T =
    calendar days / 365), legs at sigma = scale * VIX / 100 (flat smile) on the dividend forward; premium earns the bill
    to expiry; settles on the raw close. Entries: ``starts`` (session indices; every daily entry for the rule-10 pooled
    estimate) or the non-overlapping grid from session 0. Returns entry indices and P&L / spot."""
    n = len(fr["days"])
    grid = range(0, n - hold, hold) if starts is None else [int(t) for t in starts if 0 <= int(t) < n - hold]
    starts, pnl = [], []
    for t in grid:
        e = t + hold
        S = float(fr["close"][t])
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        r = float(fr["rate"][t])
        sig = max(scale * float(fr["vix"][t]) / 100.0, 0.01)
        Sx = S - _pv_div(fr, t, e, r)
        Kc = strike_for_delta_smile(Sx, T, r, 0.0, lambda K: sig, delta, "call", Sx, 3 * Sx)
        Kp = strike_for_delta_smile(Sx, T, r, 0.0, lambda K: sig, -delta, "put", 0.2 * Sx, Sx)
        if Kc is None or Kp is None:
            continue
        prem = _bs(Sx, Kc, T, r, 0.0, sig, "call") + _bs(Sx, Kp, T, r, 0.0, sig, "put")
        S1 = float(fr["close"][e])
        pay = max(S1 - Kc, 0.0) + max(Kp - S1, 0.0)
        starts.append(t)
        pnl.append((prem * math.exp(r * T) - pay) / S)
    return {"start": np.array(starts, dtype=int), "pnl": np.array(pnl, dtype=float)}


# ================================================================= T-227: SKEW percentile and realised left tails ==

def skew_tail_frequency(days, close, skew, vix, start: str = "1991-01-01", window: int = MONTH, cut: tuple = (0.80, 0.20),
                        alt_cut: tuple = (0.90, 0.10), bound: float = 0.01, n_cuts: int = 2, split: str = "2009-01-01",
                        block: int = 21, lookback: int = 252, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300,
                        excl_months: tuple = ("2008-10", "2020-03"), n_placebo: int = 200, fresh=None) -> dict:
    """T-227 on aligned daily arrays (^GSPC close on its own sessions, SKEW and VIX as of each session; ``fresh`` marks
    sessions with their own prints, for the report). Windows start every day from ``start`` (trailing percentiles
    need ``lookback`` prior values). y_t = 1{ln(S_{t+21}/S_t) < -2 (VIX_t/100) sqrt(21/252)}. High: SKEW_t above the q_hi
    quantile of the prior 252 SKEW values; low: below q_lo. Pass: one-sided upper bound of freq_high - freq_low at 1 - 0.05 /
    ``n_cuts`` (95% deflated for the 80/20 and 90/10 cut pairs) < ``bound``; and in both halves (before / from ``split``)
    the realised-21d-skewness difference high - low is not significantly negative (one-sided p > 0.1). Bootstraps are
    studentized, paired on the timeline, block 21 (the window overlap). n = min(high, low) windows.
    Rule 10(c): daily-start windows are the trial's own design (no grid phase). Reported: the same test with 2 x window
    session blocks, and each of the ``window`` non-overlapping grids (block 6 windows): range of the difference and of
    its upper bound, and how many grids would pass the frequency criterion."""
    days = list(days)
    close, skew, vix = (np.asarray(a, dtype=float) for a in (close, skew, vix))
    n = len(days) - window
    lr = np.diff(np.log(close))
    r_w = np.log(close[window:] / close[:n])
    thr = -2.0 * (vix[:n] / 100.0) * math.sqrt(window / PPY)
    y = (r_w < thr).astype(float)
    sk_w = _roll_skew(lr, n, window)
    dd = np.array(days[:n])
    valid = (np.arange(n) >= lookback) & (dd >= start)
    idx = np.nonzero(valid)[0]
    if idx.size < 50:
        return {"n": 0, "verdict": "inconclusive", "reason": f"only {idx.size} windows from {start} with {lookback} prior SKEW values — too few to test"}
    level = 1.0 - 0.05 / n_cuts

    def groups(sig, q_hi, q_lo):
        ph, pl = trailing_pctl(sig, q_hi, lookback)[:n], trailing_pctl(sig, q_lo, lookback)[:n]
        with np.errstate(invalid="ignore"):
            return sig[:n] > ph, sig[:n] < pl

    def freq_test(hi_m, lo_m, sel):
        bt = stud_group(y[sel], hi_m[sel], lo_m[sel], block, n_boot, seed)
        return bt

    hi_m, lo_m = groups(skew, *cut)
    bt = freq_test(hi_m, lo_m, idx)
    if bt is None:
        return {"n": 0, "verdict": "inconclusive", "reason": "a SKEW group has fewer than 4 windows — too few to test"}
    ub = upper_bound(bt, level)
    ci = two_sided(bt)
    n_hi, n_lo = int(hi_m[idx].sum()), int(lo_m[idx].sum())
    n_min = min(n_hi, n_lo)
    sk_rows = []
    y_split = int(split[:4])
    labels = (f"{days[idx[0]][:4]}-{y_split - 1}", f"{y_split}-{days[idx[-1]][:4]}")
    for lab, m in ((labels[0], dd < split), (labels[1], dd >= split)):
        sel = idx[m[idx]]
        bts = stud_group(sk_w[sel], hi_m[sel], lo_m[sel], block, n_boot, seed) if sel.size >= 8 else None
        bth = stud_group(y[sel], hi_m[sel], lo_m[sel], block, n_boot, seed) if sel.size >= 8 else None
        sk_rows.append({"half": lab, "n_windows": int(sel.size), "skew_diff": None if bts is None else bts["est"],
                        "p_negative": p_less(bts), "skew_diff_ci": list(two_sided(bts)),
                        "freq_diff": None if bth is None else bth["est"], "freq_diff_upper": upper_bound(bth, level)})
    alt_hi, alt_lo = groups(skew, *alt_cut)
    bt_alt = freq_test(alt_hi, alt_lo, idx)
    bt_2h = stud_group(y[idx], hi_m[idx], lo_m[idx], 2 * window, n_boot, seed)
    ub_2h = upper_bound(bt_2h, level)
    offs = []
    for k in range(window):
        sel = idx[offset_of(idx, window) == k]
        b_k = stud_group(y[sel], hi_m[sel], lo_m[sel], 6, n_boot, seed) if sel.size >= 8 else None
        if b_k is not None:
            u_k = upper_bound(b_k, level)
            offs.append({"offset": k, "n": int(sel.size), "n_min_group": int(min(hi_m[sel].sum(), lo_m[sel].sum())),
                         "diff": b_k["est"], "upper": u_k, "pass": bool(u_k < bound)})
    n_stale = None if fresh is None else int((~np.asarray(fresh, dtype=bool)[idx]).sum())
    # controls
    mon = np.array([d[:7] for d in days])
    bad = np.isin(mon, list(excl_months)).astype(int)
    cb = np.concatenate([[0], np.cumsum(bad)])
    touches = (cb[np.arange(n) + window + 1] - cb[np.arange(n)]) > 0
    sel_ex = idx[~touches[idx]]
    bt_ex = freq_test(hi_m, lo_m, sel_ex)
    dsk = np.full(len(days), np.nan)
    dsk[window:] = skew[window:] - skew[:-window]
    ch_hi, ch_lo = groups(np.where(np.isfinite(dsk), dsk, np.nanmedian(dsk)), *cut)
    sel_ch = idx[idx >= lookback + window]
    bt_ch = freq_test(ch_hi, ch_lo, sel_ch)
    vq = np.quantile(vix[idx], [1 / 3, 2 / 3])
    vt = np.digitize(vix[:n], vq)
    strat = []
    for k in range(3):
        m = idx[vt[idx] == k]
        h_, l_ = hi_m[m], lo_m[m]
        strat.append(float(y[m][h_].mean() - y[m][l_].mean()) if h_.any() and l_.any() else None)
    rng = np.random.default_rng(seed + 11)
    plc = []
    for _ in range(n_placebo):
        s = int(rng.integers(lookback, max(lookback + 1, idx.size - lookback)))
        hh, ll = np.roll(hi_m[idx], s), np.roll(lo_m[idx], s)
        if hh.any() and ll.any():
            plc.append(y[idx][hh].mean() - y[idx][ll].mean())
    plc = np.asarray(plc)
    crit = [(f"freq_high - freq_low one-sided {level:.1%} upper bound (95% deflated for {n_cuts} cut pairs) < {bound:.2f}",
             ub < bound, lower_bound(bt, level) >= bound)]
    for r in sk_rows:
        p = r["p_negative"]
        crit.append((f"realised-21d-skewness difference not significantly negative in {r['half']} (one-sided p > 0.1)",
                     None if p is None else p > 0.1, False))
    verdict, why = _decide(crit, n_min, min_n, "windows in the smaller SKEW group")
    reason = (f"^GSPC 21d log return below -2 VIX-sigma: high-SKEW (> trailing p{int(cut[0]*100)}) {bt['mean_a']*100:.2f}% of "
              f"{n_hi} windows vs low-SKEW (< p{int(cut[1]*100)}) {bt['mean_b']*100:.2f}% of {n_lo} ({days[idx[0]]}..{days[idx[-1]]}, "
              f"daily overlapping starts); difference {bt['est']*100:+.2f} pp, one-sided {level:.1%} upper bound {ub*100:+.2f} pp "
              f"(two-sided {_ci_s(tuple(x*100 for x in ci), 2)}) vs the {bound*100:.0f} pp margin; realised-skewness difference "
              + "; ".join(f"{r['half']} {_s(r['skew_diff'], 3)} (one-sided p for negative {_f(r['p_negative'], 3)})" for r in sk_rows)
              + f". Controls: halves' frequency difference " + "/".join(_s(None if r['freq_diff'] is None else r['freq_diff'] * 100, 2) for r in sk_rows)
              + f" pp; 90/10 cut {_s(bt_alt['est']*100 if bt_alt else None, 2)} pp (upper {_s(upper_bound(bt_alt, level)*100 if bt_alt else None, 2)});"
              f" excluding windows touching {'/'.join(excl_months)} {_s(bt_ex['est']*100 if bt_ex else None, 2)} pp (upper {_s(upper_bound(bt_ex, level)*100 if bt_ex else None, 2)});"
              f" 21-day SKEW change instead of level {_s(bt_ch['est']*100 if bt_ch else None, 2)} pp (upper {_s(upper_bound(bt_ch, level)*100 if bt_ch else None, 2)});"
              f" within VIX terciles " + "/".join(_s(None if x is None else x * 100, 2) for x in strat) + " pp;"
              f" shifted-SKEW placebo mean {_s(float(plc.mean())*100 if plc.size else None, 2)} pp. Rule 10 (daily starts are the "
              f"trial's design, no grid phase): with {2 * window}-session blocks the upper bound is {_s(None if ub_2h is None else ub_2h * 100, 2)} pp; "
              f"the {len(offs)} non-overlapping {window}-session grids (block 6 windows, {_rng([o['n_min_group'] for o in offs], 0).replace('+', '')} "
              f"windows in the smaller group) give differences {_rng([o['diff'] for o in offs], 2, 100)} pp, upper bounds "
              f"{_rng([o['upper'] for o in offs], 2, 100)} pp, {sum(o['pass'] for o in offs)}/{len(offs)} below the margin (reported)"
              + (f". Calendar: 21 ^GSPC sessions per window; SKEW/VIX as of each session ({n_stale} of {idx.size} entries on a "
                 "carried print)" if n_stale is not None else ""))
    return {"n": n_min, "min_n": min_n, "n_high": n_hi, "n_low": n_lo, "freq_high": bt["mean_a"], "freq_low": bt["mean_b"],
            "diff": bt["est"], "upper_bound": ub, "bound_level": level, "ci95": list(ci), "halves": sk_rows,
            "alt_cut_diff": None if bt_alt is None else bt_alt["est"], "alt_cut_upper": upper_bound(bt_alt, level),
            "excl_months_diff": None if bt_ex is None else bt_ex["est"], "excl_months_upper": upper_bound(bt_ex, level),
            "skew_change_diff": None if bt_ch is None else bt_ch["est"], "skew_change_upper": upper_bound(bt_ch, level),
            "vix_tercile_diffs": strat, "placebo_mean": float(plc.mean()) if plc.size else None,
            "upper_bound_2hold_blocks": ub_2h, "grid_offsets": offs, "entries_on_carried_print": n_stale,
            "first_window": days[idx[0]], "last_window": days[idx[-1]], "verdict": verdict, "reason": reason + " — " + why}


# ===================================================================== T-228: SKEW-implied tail vs realised ==

def skew_tail_prob(skew) -> np.ndarray:
    """CBOE white-paper Gram-Charlier mapping: P(30-day log return < -2 sigma) = 0.0228 + 0.0270 (SKEW - 100) / 10."""
    return 0.0228 + 0.0270 * (np.asarray(skew, dtype=float) - 100.0) / 10.0


def skew_implied_gap(days, close, skew, vix, start: str = "1990-01-01", window: int = MONTH, margin: float = 0.02,
                     block: int = 6, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300,
                     thresholds: tuple = (125, 130, 135, 140), secondary: int = 135, table_max: float = 145.0,
                     n_placebo: int = 1000, fresh=None, alt_close: Optional[dict] = None, index_label: str = "^GSPC") -> dict:
    """T-228 on aligned daily arrays on the index's own trading calendar (SKEW and VIX as of each session; ``fresh`` marks
    sessions with their own prints). gap_t = P_SKEW(t) - y_t, y_t = 1{ln(S_{t+21}/S_t) < -2 (VIX_t/100) sqrt(21/252)}.

    Rule 10(b): the claim's non-overlapping 21-session grid has ``window`` equally valid start offsets. The primary
    statistic is the POOLED mean gap over every daily entry from ``start`` (studentized circular block bootstrap, block
    pool_block_len(window, block) = 126 sessions); each offset's grid (studentized, block ``block`` windows) is reported:
    range of its mean and of its lower bound, and how many offsets pass. Criteria, on the pooled series: the one-sided 95%
    lower bound > ``margin`` (the pass rule); the gap positive in EACH of three equal sub-periods (the procedure's
    requirement, stricter than the pass rule's "at least 2 of 3", which is kept as its own criterion). n = the distinct
    21-session holds the entries span (the claim's non-overlapping windows).

    Controls (not criteria): the constant-normal benchmark (P = 2.28%); whether SKEW carries information about the
    REALISED tail, i.e. the realised frequency above vs below SKEW ``secondary`` against circular shifts of the SKEW label
    (permuting SKEW over the GAP would be uninformative: P is an increasing function of SKEW); the SKEW > thresholds
    conditional gaps with PBO; SKEW above the white-paper table; ``alt_close`` ({label: closes aligned with days, NaN
    where absent}) re-measures y on another price series where it exists (the SPY splice)."""
    days = list(days)
    close, skew, vix = (np.asarray(a, dtype=float) for a in (close, skew, vix))
    N = len(days)
    t0 = next((i for i, d in enumerate(days) if d >= start), N)
    cand = np.arange(t0, max(t0, N - window), dtype=np.int64)
    with np.errstate(invalid="ignore", divide="ignore"):
        r_all = np.log(close[cand + window] / close[cand]) if cand.size else np.zeros(0)
    ok = np.isfinite(skew[cand]) & np.isfinite(vix[cand]) & np.isfinite(r_all)
    idx, r_w = cand[ok], r_all[ok]
    n = n_holds(idx, window)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} {window}-session holds — too few to test"}
    thr_t = -2.0 * (vix[idx] / 100.0) * math.sqrt(window / PPY)
    y = (r_w < thr_t).astype(float)
    sk = skew[idx]
    P = skew_tail_prob(sk)
    gap = P - y
    pb = pool_block_len(window, block)
    bt = stud_mean(gap, pb, n_boot, seed)
    lb, ub = lower_bound(bt, 0.95), upper_bound(bt, 0.95)
    ci = two_sided(bt)
    parts = np.array_split(np.arange(idx.size), 3)
    thirds = [float(gap[p].mean()) for p in parts]
    third_lab = [f"{days[idx[p[0]]][:4]}-{days[idx[p[-1]]][:4]}" for p in parts]
    n_pos = sum(t > 0 for t in thirds)
    # rule 10(b): every grid offset
    offs = []
    off = offset_of(idx, window)
    for k in range(window):
        sel = off == k
        g = gap[sel]
        b_k = stud_mean(g, block, n_boot, seed)
        if b_k is None:
            continue
        l_k = lower_bound(b_k, 0.95)
        th = [float(q.mean()) for q in np.array_split(g, 3)]
        offs.append({"offset": k, "first": days[idx[sel][0]], "n": int(g.size), "mean": b_k["est"], "lower": l_k,
                     "thirds": th, "pass_bound": bool(l_k > margin), "pass": bool(l_k > margin and all(x > 0 for x in th))})
    # controls
    bt_norm = stud_mean(0.0228 - y, pb, n_boot, seed)
    lb_norm = lower_bound(bt_norm, 0.95)
    cond = {}
    for thr in thresholds:
        m = sk > thr
        cond[str(thr)] = {"n": int(m.sum()), "gap": float(gap[m].mean()) if m.any() else None}
    above = sk > table_max
    R = gap[:, None] * (sk[:, None] > np.array(thresholds)[None, :])
    try:
        pbo = pbo_cscv(R, 8) if R.shape[0] >= 16 else None
    except (ValueError, ZeroDivisionError, FloatingPointError):
        pbo = None
    hi = sk > secondary
    info = {"n_high": int(hi.sum()), "freq_high": float(y[hi].mean()) if hi.any() else None,
            "freq_low": float(y[~hi].mean()) if (~hi).any() else None, "diff": None, "placebo_p": None}
    if hi.any() and (~hi).any():
        d_obs = info["freq_high"] - info["freq_low"]
        m_ = idx.size
        lo_s, hi_s = min(252, m_ // 4), max(min(252, m_ // 4) + 1, m_ - min(252, m_ // 4))
        rng = np.random.default_rng(seed + 3)
        null = []
        for sh in rng.integers(lo_s, hi_s, n_placebo):
            hs = np.roll(hi, int(sh))
            if hs.any() and (~hs).any():
                null.append(y[hs].mean() - y[~hs].mean())
        null = np.asarray(null)
        info["diff"] = float(d_obs)
        info["placebo_p"] = float((np.sum(null >= d_obs) + 1) / (null.size + 1)) if null.size else None
    alt = {}
    for lab, ac in (alt_close or {}).items():
        ac = np.asarray(ac, dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            ra = np.log(ac[idx + window] / ac[idx])
        use = np.isfinite(ra)
        y2 = (np.where(use, ra, r_w) < thr_t).astype(float)
        b2 = stud_mean(P - y2, pb, max(500, n_boot // 2), seed)
        alt[lab] = {"from": days[idx[use][0]] if use.any() else None, "n_entries_on_it": int(use.sum()),
                    "realised_freq": float(y2.mean()), "mean_gap": b2["est"], "lower": lower_bound(b2, 0.95)}
    n_stale = None if fresh is None else int((~np.asarray(fresh, dtype=bool)[idx]).sum())
    crit = [(f"POOLED mean gap one-sided 95% lower bound > {margin:.2f}", lb > margin, ub <= margin),
            ("POOLED gap positive in EACH of the 3 sub-periods (the procedure's requirement; stricter than the pass rule)",
             n_pos == 3, False),
            ("POOLED gap positive in at least 2 of 3 sub-periods (the pass rule)", n_pos >= 2, False)]
    verdict, why = _decide(crit, n, min_n, f"non-overlapping {window}-session windows (distinct holds)")
    sec = cond.get(str(secondary), {})
    n_off = len(offs)
    reason = (f"{index_label} (the S&P 500 itself, as the claim words it, for the whole sample; each window is {window} sessions "
              f"of its own calendar, SKEW and VIX the last print at or before the entry"
              + (f", {n_stale} of {idx.size} entries on a carried print" if n_stale is not None else "")
              + f"): SKEW-implied P(21d < -2 VIX-sigma) averages {P.mean()*100:.2f}% vs realised {y.mean()*100:.2f}%. POOLED over "
              f"all {window} grid offsets ({idx.size} overlapping daily entries {days[idx[0]]}..{days[idx[-1]]} = {n} distinct "
              f"{window}-session holds; studentized circular block bootstrap, block {pb} sessions): mean gap {bt['est']*100:+.2f} pp, "
              f"one-sided 95% lower bound {lb*100:+.2f} pp (two-sided {_ci_s(tuple(x*100 for x in ci), 2)}) vs the {margin*100:.0f} "
              f"pp margin; sub-period gaps " + "/".join(f"{l} {x*100:+.2f}" for l, x in zip(third_lab, thirds))
              + f" pp ({n_pos} of 3 positive; the procedure requires all 3, the pass rule 2). Per grid offset ({n_off} "
              f"non-overlapping grids, n {_rng([o['n'] for o in offs], 0).replace('+', '')} windows, block {block}): mean gap "
              f"{_rng([o['mean'] for o in offs], 2, 100)} pp, one-sided lower bound {_rng([o['lower'] for o in offs], 2, 100)} pp; "
              f"{sum(o['pass_bound'] for o in offs)}/{n_off} offsets clear the margin and {sum(o['pass'] for o in offs)}/{n_off} also "
              f"have all three thirds positive. Controls: constant-normal benchmark (P = 2.28%) gap {bt_norm['est']*100:+.2f} pp "
              f"(lower {_s(None if lb_norm is None else lb_norm * 100, 2)} pp) is "
              + ("BELOW" if bt_norm["est"] <= margin else "above")
              + f" the {margin*100:.0f} pp margin, so " + ("the excess over the margin comes from the SKEW level mapping (P_SKEW "
                                                          "averages above 2.28%), not from realised tails being rarer than normal; "
                                                          if bt_norm["est"] <= margin else "realised tails alone are rarer than normal by more than the margin; ")
              + f"SKEW information on the REALISED tail: frequency {_f(None if info['freq_high'] is None else info['freq_high'] * 100, 2)}% "
              f"with SKEW > {secondary} (n={info['n_high']}) vs {_f(None if info['freq_low'] is None else info['freq_low'] * 100, 2)}% "
              f"otherwise, difference {_s(None if info['diff'] is None else info['diff'] * 100, 2)} pp, circular SKEW-shift placebo "
              f"p={_f(info['placebo_p'], 3)} (one-sided: higher SKEW, more realised tails); SKEW > {secondary} conditional gap "
              f"{_s(None if sec.get('gap') is None else sec['gap']*100, 2)} pp (n={sec.get('n', 0)} entries); PBO across thresholds "
              f"{'/'.join(map(str, thresholds))} {_f(pbo['pbo'] if pbo else None, 2)}; SKEW > {table_max:.0f} (beyond the "
              f"white-paper table, formula extrapolated) {int(above.sum())} entries, gap "
              f"{_s(float(gap[above].mean())*100 if above.any() else None, 2)} pp"
              + "".join(f"; {lab} (from {v['from']}, {v['n_entries_on_it']} entries on it): realised {v['realised_freq']*100:.2f}%, "
                        f"pooled gap {v['mean_gap']*100:+.2f} pp, lower {_s(None if v['lower'] is None else v['lower'] * 100, 2)} pp"
                        for lab, v in alt.items()))
    return {"n": n, "min_n": min_n, "n_entries": int(idx.size), "block_days": pb, "mean_p_skew": float(P.mean()),
            "realised_freq": float(y.mean()), "mean_gap": bt["est"], "lower_bound_95_one_sided": lb, "ci95": list(ci),
            "thirds": thirds, "thirds_labels": third_lab, "grid_offsets": offs,
            "normal_benchmark_gap": bt_norm["est"], "normal_benchmark_lower": lb_norm, "conditional": cond, "pbo": pbo,
            "skew_information": info, "n_above_table": int(above.sum()),
            "gap_above_table": float(gap[above].mean()) if above.any() else None, "alt_series": alt,
            "entries_on_carried_print": n_stale, "first_window": days[idx[0]], "last_window": days[idx[-1]],
            "verdict": verdict, "reason": reason + " — " + why}


# ======================================================== T-229: SKEW-gated 25d/10d SPX put spread (model) ==

def _root(sym: str) -> str:
    return sym[:-15] if len(sym) > 15 else sym


def _chain_by_strike(vals, expiry: str, roots=("SPXW", "SPX")) -> tuple:
    """{strike: {'call': row, 'put': row}} for one expiry, preferring the first root in ``roots`` that lists it."""
    rows = [v for v in vals if v.get("expiry") == expiry]
    have = {_root(v.get("sym", "")) for v in rows}
    root = next((r for r in roots if r in have), None)
    out = {}
    for v in rows:
        if root is not None and _root(v.get("sym", "")) != root:
            continue
        out.setdefault(float(v["strike"]), {})[v["type"]] = v
    return root, out


def _mid(row) -> Optional[float]:
    if not row:
        return None
    b, a = row.get("bid") or 0.0, row.get("ask") or 0.0
    return 0.5 * (b + a) if b > 0 and a >= b else None


def _parity_forward(by: dict, T: float, r: float) -> Optional[tuple]:
    best = None
    for K, d in by.items():
        c, p = _mid(d.get("call")), _mid(d.get("put"))
        if c is None or p is None:
            continue
        if best is None or abs(c - p) < best[0]:
            best = (abs(c - p), K, c, p)
    if best is None:
        return None
    _, K, c, p = best
    return K + math.exp(r * T) * (c - p), K


def calibrate_skew_slope(vals, quote_day: str, r: float, vix_q: float, skew_q: float, target_dte: int = 30,
                         dmin: float = 0.08, dmax: float = 0.30) -> Optional[dict]:
    """T-229 calibration on one captured SPX chain: the expiry nearest ``target_dte`` calendar days from the quote day; F by
    put-call parity; ATM IV interpolated at F from the chain's put and call IVs; the slope of put IV on ln(K/F) through the
    ATM point (least squares) over puts with chain delta in [-dmax, -dmin] (the 25d..10d region the spread uses). Returns
    the ATM-to-VIX ratio and kappa = -slope / (SKEW_q - 100)."""
    qd = date.fromisoformat(quote_day)
    exps = sorted({v.get("expiry") for v in vals if v.get("expiry")})
    cands = [e for e in exps if (date.fromisoformat(e) - qd).days >= 7]
    if not cands:
        return None
    exp = min(cands, key=lambda e: abs((date.fromisoformat(e) - qd).days - target_dte))
    dte = (date.fromisoformat(exp) - qd).days
    T = dte / 365.0
    root, by = _chain_by_strike(vals, exp)
    fw = _parity_forward(by, T, r)
    if fw is None:
        return None
    F, _ = fw
    ks = sorted(K for K, d in by.items() if all((d.get(k) or {}).get("iv", 0) > 0 for k in ("call", "put")))
    if len(ks) < 2:
        return None
    j = bisect_left(ks, F)
    if j <= 0 or j >= len(ks):
        return None
    k0, k1 = ks[j - 1], ks[j]
    iv = lambda K: 0.5 * (by[K]["call"]["iv"] + by[K]["put"]["iv"])
    w = (math.log(F) - math.log(k0)) / (math.log(k1) - math.log(k0))
    atm = (1 - w) * iv(k0) + w * iv(k1)
    pts = [(math.log(K / F), d["put"]["iv"] - atm) for K, d in by.items()
           if d.get("put") and (d["put"].get("iv") or 0) > 0 and d["put"].get("delta") is not None
           and -dmax <= float(d["put"]["delta"]) <= -dmin]
    if len(pts) < 3:
        return None
    x = np.array([p[0] for p in pts])
    yv = np.array([p[1] for p in pts])
    slope = float((x * yv).sum() / (x * x).sum())
    rmse = float(np.sqrt(np.mean((yv - slope * x) ** 2)))
    return {"quote_day": quote_day, "expiry": exp, "root": root, "dte": dte, "forward": F, "atm_iv": atm, "vix": vix_q,
            "atm_ratio": atm / (vix_q / 100.0), "skew": skew_q, "slope": slope, "kappa": -slope / (skew_q - 100.0),
            "n_points": len(pts), "fit_rmse": rmse}


def put_spread_cycle(S: float, S1: float, T: float, r: float, q: float, sig_atm: float, slope: float,
                     d_long: float = -0.25, d_short: float = -0.10) -> Optional[tuple]:
    """One MODEL-PRICED put spread: long the ``d_long`` put, short the ``d_short`` put, legs at sigma(K) = sig_atm + slope
    ln(K/F) (floored at 1%), strikes solved at their own smile vol; returns (debit, payoff, K_long, K_short)."""
    F = S * math.exp((r - q) * T)
    sig = lambda K: max(sig_atm + slope * math.log(K / F), 0.01)
    k_long = strike_for_delta_smile(S, T, r, q, sig, d_long, "put", 0.15 * F, F)
    k_short = strike_for_delta_smile(S, T, r, q, sig, d_short, "put", 0.15 * F, F)
    if k_long is None or k_short is None or not k_short < k_long:
        return None
    debit = _bs(S, k_long, T, r, q, sig(k_long), "put") - _bs(S, k_short, T, r, q, sig(k_short), "put")
    if not debit > 0:
        return None
    payoff = max(k_long - S1, 0.0) - max(k_short - S1, 0.0)
    return debit, payoff, k_long, k_short


def put_spread_skew(days, spx, skew, vix, rate, qy, atm_ratio: float, kappa: float, start: str = "1991-01-01",
                    dte: int = 30, lookback: int = 252, pct: float = 0.20, mults: tuple = (0.5, 1.0, 2.0),
                    block: int = 6, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300, min_low: int = 60,
                    n_placebo: int = 2000, q_assumed=None, fresh=None, entries=None, expiries=None) -> dict:
    """T-229 on aligned daily arrays on the index's own sessions (^GSPC close, SKEW, VIX, continuous bill rate, dividend
    yield). Rule 10(a): "monthly 30-DTE" names SPX's standard monthly expiry calendar. Each expiry is the third Friday of
    the month (the prior session when it is a holiday); the spread is bought at the close of the session nearest ``dte``
    calendar days before it (ties to the earlier session), or at the previous expiry's close when that comes later (holds
    never overlap), and settles on the ^GSPC close of the expiry session (T = calendar days / 365). ``entries`` /
    ``expiries`` (aligned session indices) override the calendar. Entries need ``lookback`` prior SKEW values and a date
    >= ``start``. ATM IV = VIX/100 x atm_ratio; slope = -kappa x mult x (SKEW - 100). Statistic: mean(payoff / debit |
    SKEW_t < trailing p20) - mean(payoff / debit | all), studentized paired block bootstrap (block 6 entries). Pass: > 0
    with the two-sided 95% CI excluding zero, >= ``min_low`` low-SKEW entries, and > 0 at kappa x0.5 and x2.
    ``q_assumed`` (bool, aligned with days) marks days whose yield is an assumed constant; their entries are counted."""
    days = list(days)
    spx, skew, vix, rate, qy = (np.asarray(a, dtype=float) for a in (spx, skew, vix, rate, qy))
    ords = _ords(days)
    p_lo = trailing_pctl(skew, pct, lookback)
    t0 = max(lookback, next((i for i, d in enumerate(days) if d >= start), len(days)))
    if entries is None:
        ent, exp = calendar_entries(days, sessions_for(days, monthly_expiry_dates(days)), dte, non_overlap=True)
    else:
        ent, exp = np.asarray(entries, dtype=np.int64), np.asarray(expiries, dtype=np.int64)
    sel = (ent >= t0) & (exp < len(days))
    ent, exp = ent[sel], exp[sel]
    sel = np.isfinite(p_lo[ent]) & np.isfinite(skew[ent]) & np.isfinite(vix[ent]) & np.isfinite(spx[exp])
    ent, exp = ent[sel], exp[sel]
    if ent.size < 8:
        return {"n": int(ent.size), "verdict": "inconclusive", "reason": f"only {ent.size} monthly entries — too few to test"}
    res = {m: np.full(ent.size, np.nan) for m in mults}
    debits = {m: np.full(ent.size, np.nan) for m in mults}
    for i, (t, e) in enumerate(zip(ent, exp)):
        T = (ords[e] - ords[t]) / 365.0
        for m in mults:
            c = put_spread_cycle(spx[t], spx[e], T, rate[t], qy[t], vix[t] / 100.0 * atm_ratio, -kappa * m * (skew[t] - 100.0))
            if c is not None:
                res[m][i] = c[1] / c[0]
                debits[m][i] = c[0] / spx[t]
    ok = np.all([np.isfinite(res[m]) for m in mults], axis=0)
    ts, te = ent[ok], exp[ok]
    low_all = (skew < p_lo)[ts] if ok.any() else np.zeros(0, bool)
    n = int(ts.size)
    n_drop = int((~ok).sum())
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} priceable monthly entries — too few to test"}
    dtes = ords[te] - ords[ts]
    held = te - ts
    n_stale = None if fresh is None else int((~np.asarray(fresh, dtype=bool)[ts]).sum())
    qa = np.zeros(len(days), dtype=bool) if q_assumed is None else np.asarray(q_assumed, dtype=bool)
    n_qa = int(qa[ts].sum())
    allm = np.ones(n, dtype=bool)
    out_m = {}
    for m in mults:
        x = res[m][ok]
        bt = stud_group(x, low_all, allm, block, n_boot, seed)
        out_m[m] = {"diff": None if bt is None else bt["est"], "ci": list(two_sided(bt)),
                    "mean_low": None if bt is None else bt["mean_a"], "mean_all": float(x.mean()),
                    "mean_debit_pct_spot": float(np.nanmean(debits[m][ok]) * 100)}
    base = res[1.0][ok] if 1.0 in res else res[mults[0]][ok]
    b0 = out_m.get(1.0, out_m[mults[0]])
    n_low = int(low_all.sum())
    lo, hi = b0["ci"]
    others = [m for m in mults if m != 1.0]
    sens_ok = all(out_m[m]["diff"] is not None and out_m[m]["diff"] > 0 for m in others)
    # controls
    rng = np.random.default_rng(seed + 5)
    plc_p = None
    if 0 < n_low < n and b0["diff"] is not None:
        null = np.array([base[rng.choice(n, n_low, replace=False)].mean() - base.mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= b0["diff"]) + 1) / (n_placebo + 1))
    v15 = vix[ts] < 15
    bt15 = stud_group(base, v15, allm, block, n_boot, seed) if v15.sum() >= 4 else None
    vq = np.quantile(vix[ts], [1 / 3, 2 / 3])
    vt = np.digitize(vix[ts], vq)
    strat = [float(base[(vt == k) & low_all].mean() - base[vt == k].mean()) if ((vt == k) & low_all).any() else None for k in range(3)]
    try:
        dsr = float(deflated_sharpe_ratio(base[low_all] - 1.0, n_trials=2)) if n_low >= 8 else None
    except (ValueError, ZeroDivisionError):
        dsr = None
    crit = [("mean(payoff/debit | SKEW < trailing p20) - mean(all) > 0 with the two-sided 95% CI excluding zero",
             None if lo is None else (b0["diff"] > 0 and lo > 0), hi is not None and hi < 0),
            (f"at least {min_low} low-SKEW entries ({n_low})", n_low >= min_low, False),
            ("difference > 0 (sign unchanged) at kappa " + " and ".join(f"x{m}" for m in others), sens_ok,
             all(out_m[m]["ci"][1] is not None and out_m[m]["ci"][1] < 0 for m in others))]
    verdict, why = _decide(crit, n, min_n, "monthly entries")
    reason = (f"{MP} (BS legs: ATM IV = VIX x {atm_ratio:.3f}, put skew slope = -kappa (SKEW - 100) per unit ln(K/F), kappa "
              f"{kappa:.5f}, held fixed through history; payoff on ^GSPC closes; no transaction costs, none stated in the claim): {n} monthly entries on "
              f"SPX's standard monthly expiry calendar (third Friday, prior session on a holiday; bought at the close nearest {dte} calendar "
              f"days before it, or at the previous expiry's close when later, so holds never overlap: {int(dtes.min())}-{int(dtes.max())} DTE, "
              f"{int(held.min())}-{int(held.max())} sessions held; settled on the expiry session's close as the proxy for the AM settlement; "
              f"{days[ts[0]]}..{days[te[-1]]}"
              + (f"; {n_drop} unpriceable dropped" if n_drop else "")
              + (f"; {n_stale} entries on a carried SKEW/VIX print" if n_stale else "")
              + (f"; {n_qa} entries up to {days[ts[qa[ts]][-1]]} price on an ASSUMED dividend yield, see q" if n_qa else "")
              + f"), {n_low} with SKEW below its trailing 20th percentile; "
              f"mean payoff/debit low-SKEW {_f(b0['mean_low'], 3)} vs all {_f(b0['mean_all'], 3)}: difference {_s(b0['diff'], 3)} "
              f"({_ci_s(b0['ci'], 3)}); kappa sensitivity " + ", ".join(f"x{m} {_s(out_m[m]['diff'], 3)} ({_ci_s(out_m[m]['ci'], 3)})" for m in others)
              + f". Controls: random-timing placebo p={_f(plc_p, 3)}; VIX < 15 gate difference {_s(None if bt15 is None else bt15['est'], 3)}"
              f" (n={int(v15.sum())}); within VIX terciles " + "/".join(_s(x, 3) for x in strat)
              + f"; deflated Sharpe (2 gates) of the low-SKEW per-entry return {_f(dsr, 3)}. The debit hinges on the IV proxy; "
              "the traded version needs SPX chain history (2 capture days archived)")
    return {"n": n, "min_n": min_n, "n_low": n_low, "by_kappa_mult": {str(m): v for m, v in out_m.items()}, "atm_ratio": atm_ratio,
            "kappa": kappa, "placebo_p": plc_p, "vix15_diff": None if bt15 is None else bt15["est"], "vix_tercile_diffs": strat,
            "dsr_low_skew": dsr, "dropped_entries": n_drop, "entries_assumed_q": n_qa, "first_entry": days[ts[0]], "last_entry": days[ts[-1]],
            "calendar": "SPX monthly expiry (third Friday), entered ~30 DTE, non-overlapping", "dte_range": [int(dtes.min()), int(dtes.max())],
            "sessions_held_range": [int(held.min()), int(held.max())], "last_expiry": days[te[-1]], "entries_on_carried_print": n_stale,
            "verdict": verdict, "reason": reason + " — " + why}


# ============================================================= T-237: VXN - VIX z-score vs realised spread ==

def vol_spread_events(days, iv_a, iv_b, px_a, px_b, window: int = 60, thr: float = 2.0, hold: int = MONTH, block: int = 2,
                      n_declared: int = 3) -> dict:
    """Event series for T-237 on aligned daily arrays: x = iv_a - iv_b; z = rolling z of x over ``window`` days (t
    included); an event is the first close where |z| passes ``thr`` (|z_{t-1}| <= thr < |z_t|) while no hold is open; s =
    sign(z). stat_t = s [x_t - (RV_a - RV_b)(t+1..t+hold)], realised vols in vol points from dividend-adjusted closes."""
    iv_a, iv_b, px_a, px_b = (np.asarray(v, dtype=float) for v in (iv_a, iv_b, px_a, px_b))
    n = len(days) - hold
    x = iv_a - iv_b
    rv_a = 100 * np.sqrt(_fwd_rv(np.diff(np.log(px_a)), max(n, 0), 1, hold)) if n > 0 else np.zeros(0)
    rv_b = 100 * np.sqrt(_fwd_rv(np.diff(np.log(px_b)), max(n, 0), 1, hold)) if n > 0 else np.zeros(0)
    stat_all = x[:max(n, 0)] - (rv_a - rv_b)
    z = rolling_z(x, window)
    ev_t, ev_s = [], []
    free = 0
    for t in range(max(window, 1), max(n, 0)):
        if t < free or not (np.isfinite(z[t]) and np.isfinite(z[t - 1])):
            continue
        if abs(z[t]) > thr and abs(z[t - 1]) <= thr:
            ev_t.append(t)
            ev_s.append(1 if z[t] > 0 else -1)
            free = t + hold
    ev_t, ev_s = np.array(ev_t, dtype=int), np.array(ev_s, dtype=int)
    return {"t": ev_t, "s": ev_s, "stat": ev_s * stat_all[ev_t] if ev_t.size else np.zeros(0), "stat_all": stat_all, "z": z}


def vol_spread_test(days, iv_a, iv_b, px_a, px_b, window: int = 60, alt_windows: tuple = (40, 120), thr: float = 2.0,
                    hold: int = MONTH, block: int = 2, win_req: float = 0.6, n_boot: int = N_BOOT, seed: int = 0,
                    min_n: int = 30, n_placebo: int = 2000, label: str = "VXN-VIX / QQQ-SPY") -> dict:
    """T-237. Pass: mean event statistic > 0 with the CI excluding zero (two-sided, Bonferroni over the 3 declared
    z-windows: 98.3%), win rate > 0.6, mean > 0 in both halves of the event sequence. The claim also asserts each side
    ("the realised spread falls short of an extreme-wide implied spread AND exceeds an extreme-narrow one"), so the mean
    of s*stat must be > 0 on the wide events (z > +thr) and on the narrow events (z < -thr), each side with >= ``min_n``
    events; below min_n a side cannot pass and fails only decisively (its 98.3% CI wholly below zero). n = events.
    Rule 10(c): events sit on data-determined dates (the z crossing), not on a grid, so there is no phase to vary; the
    unconditional overlapping-daily control uses 2 x ``hold``-session blocks."""
    days = list(days)
    ev = vol_spread_events(days, iv_a, iv_b, px_a, px_b, window, thr, hold, block)
    x = ev["stat"]
    n = int(x.size)
    n_decl = 1 + len(alt_windows)
    level = 1.0 - 0.05 / n_decl
    bt = stud_mean(x, block, n_boot, seed)
    ci_d = two_sided(bt, level)
    ci95 = two_sided(bt)
    wr = float((x > 0).mean()) if n else None
    halves = [float(p.mean()) if p.size else None for p in np.array_split(x, 2)] if n >= 2 else [None, None]
    sides = {}
    for lab, msk in (("wide", ev["s"] > 0), ("narrow", ev["s"] < 0)):
        xs = x[msk] if n else np.zeros(0)
        bts = stud_mean(xs, block, n_boot, seed)
        sides[lab] = {"n": int(xs.size), "mean": float(xs.mean()) if xs.size else None, "ci95": list(two_sided(bts)),
                      "ci_deflated": list(two_sided(bts, level)), "win_rate": float((xs > 0).mean()) if xs.size else None}
    alt = {}
    for w in alt_windows:
        e2 = vol_spread_events(days, iv_a, iv_b, px_a, px_b, w, thr, hold, block)
        st2, s2 = e2["stat"], e2["s"]
        alt[str(w)] = {"n": int(st2.size), "mean": float(st2.mean()) if st2.size else None,
                       "n_wide": int((s2 > 0).sum()), "mean_wide": float(st2[s2 > 0].mean()) if (s2 > 0).any() else None,
                       "n_narrow": int((s2 < 0).sum()), "mean_narrow": float(st2[s2 < 0].mean()) if (s2 < 0).any() else None}
    sa = ev["stat_all"]
    bt_u = stud_mean(sa, 2 * hold, n_boot, seed) if sa.size >= 8 else None
    plc_p = None
    if n >= 2 and sa.size > n:
        rng = np.random.default_rng(seed + 9)
        sg = ev["s"]
        null = np.array([(sg * sa[rng.choice(sa.size, n, replace=False)]).mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= x.mean()) + 1) / (n_placebo + 1))
    wins = int((x > 0).sum())
    crit = [(f"mean > 0 with the {level:.1%} CI excluding zero (95% deflated for {n_decl} declared z-windows)",
             None if ci_d[0] is None else (bt["est"] > 0 and ci_d[0] > 0), ci_d[1] is not None and ci_d[1] < 0),
            (f"win rate > {win_req}", None if wr is None else wr > win_req, (wins + max(min_n - n, 0)) <= win_req * max(min_n, n)),
            ("mean > 0 in both halves", None if None in halves else all(h > 0 for h in halves), False)]
    for lab, cond, claim_s in (("wide", f"z > +{thr}, s = +1", "realised spread falls short of the extreme-wide implied spread"),
                               ("narrow", f"z < -{thr}, s = -1", "realised spread exceeds the extreme-narrow implied spread")):
        sd_ = sides[lab]
        if sd_["n"] >= min_n:
            ok = sd_["mean"] > 0
        elif sd_["n"] and sd_["ci_deflated"][1] is not None and sd_["ci_deflated"][1] < 0:
            ok = False                                   # below min_n: a decisive failure still counts
        else:
            ok = None                                    # below min_n: cannot pass; a non-decisive shortfall is not a failure
        crit.append((f"{lab} side ({cond}): mean s*stat > 0 with >= {min_n} events, i.e. the {claim_s} ({sd_['n']} events, "
                     f"mean {_s(sd_['mean'], 2)})" + ("" if sd_["n"] >= min_n else " [below min_n]"), ok, True))
    verdict, why = _decide(crit, n, min_n, "events")
    first = days[ev["t"][0]] if n else None
    last = days[ev["t"][-1]] if n else None
    side_s = "; ".join(f"{lab} side {v['n']} events, mean {_s(v['mean'], 2)} vol pts ({_ci_s(v['ci95'], 2)}; {level:.1%} "
                       f"{_s(v['ci_deflated'][0], 2)} to {_s(v['ci_deflated'][1], 2)}), win rate {_f(v['win_rate'], 2)}"
                       for lab, v in sides.items())
    reason = (f"{label}: {n} events ({first}..{last}; z-window {window}, |z| > {thr}, non-overlapping {hold}d holds, "
              f"{sides['wide']['n']} wide / {sides['narrow']['n']} narrow); mean s[(implied spread) - (realised spread)] "
              f"{_s(bt['est'] if bt else None, 2)} vol pts, {level:.1%} CI {_s(ci_d[0], 2)} to {_s(ci_d[1], 2)} (95% {_s(ci95[0], 2)} to "
              f"{_s(ci95[1], 2)}); win rate {_f(wr, 2)}; halves {_s(halves[0], 2)}/{_s(halves[1], 2)}. By side (each a criterion): "
              f"{side_s}. Controls: unconditional "
              f"implied-minus-realised spread {_s(bt_u['est'] if bt_u else None, 2)} vol pts ({_ci_s(two_sided(bt_u), 2)}, "
              f"{2 * hold}-session blocks); "
              f"random-entry placebo (matched count and signs) p={_f(plc_p, 3)}; other declared z-windows "
              + ", ".join(f"{w}d {_s(v['mean'], 2)} (n={v['n']}; wide {_s(v['mean_wide'], 2)} n={v['n_wide']}, narrow "
                          f"{_s(v['mean_narrow'], 2)} n={v['n_narrow']})" for w, v in alt.items())
              + ". Rule 10: event entries on data-determined dates, no grid phase")
    return {"n": n, "min_n": min_n, "mean": bt["est"] if bt else None, "ci_deflated": list(ci_d), "ci95": list(ci95),
            "ci_level": level, "win_rate": wr, "halves": halves, "sides": sides, "alt_windows": alt,
            "unconditional_mean": bt_u["est"] if bt_u else None,
            "placebo_p": plc_p, "first_event": first, "last_event": last, "verdict": verdict, "reason": reason + " — " + why}


# ======================================================================== T-239: VIX call overlay (model) ==

def _mdd_rows(R) -> np.ndarray:
    """Maximum drawdown (positive fraction) of compounded per-period returns, row-wise (the equity curve starts at 1)."""
    R = np.atleast_2d(np.asarray(R, dtype=float))
    eq = np.concatenate([np.ones((R.shape[0], 1)), np.cumprod(1.0 + R, axis=1)], axis=1)
    return (1.0 - eq / np.maximum.accumulate(eq, axis=1)).max(axis=1)


def _as_paths(x) -> np.ndarray:
    """(n, h) within-cycle value paths (value j+1 sessions into cycle k / value at the cycle's start); a 1-D array of
    per-cycle returns is the h = 1 case (cycle-end points only)."""
    x = np.asarray(x, dtype=float)
    return (1.0 + x)[:, None] if x.ndim == 1 else x


def _mdd_paths(P) -> np.ndarray:
    """Maximum drawdown (positive fraction) of the equity curve chained from within-cycle value paths, row-wise. P has
    shape (rows, n, h) or (n, h); the curve starts at 1 and cycle k starts at the product of the earlier cycles' end
    values, so with daily paths every session's equity is a point of the curve."""
    P = np.asarray(P, dtype=float)
    if P.ndim == 2:
        P = P[None]
    g = P[:, :, -1]
    start = np.concatenate([np.ones((P.shape[0], 1)), np.cumprod(g, axis=1)[:, :-1]], axis=1)
    eq = np.concatenate([np.ones((P.shape[0], 1)), (start[:, :, None] * P).reshape(P.shape[0], -1)], axis=1)
    return (1.0 - eq / np.maximum.accumulate(eq, axis=1)).max(axis=1)


def _mdd_span(P) -> tuple:
    """(mdd, peak position, trough position) on the chained equity curve of one (n, h) path set; position 0 is the
    first cycle's start, position k h + j + 1 is session j + 1 of cycle k."""
    P = _as_paths(P)
    start = np.concatenate([[1.0], np.cumprod(P[:, -1])[:-1]])
    eq = np.concatenate([[1.0], (start[:, None] * P).ravel()])
    dd = 1.0 - eq / np.maximum.accumulate(eq)
    j = int(np.argmax(dd))
    return float(dd[j]), int(np.argmax(eq[:j + 1])), j


def mdd_reduction_boot(r_hedged, r_base, block: int = 12, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """1 - MDD(hedged)/MDD(base) and its PAIRED percentile circular block bootstrap (the same cycle blocks for both).
    Inputs are per-cycle returns (n,) or daily within-cycle value paths (n, h); with paths the drawdown is measured on the
    daily equity curve and a resample keeps each cycle's whole daily path."""
    a, b = _as_paths(r_hedged), _as_paths(r_base)
    n = a.shape[0]
    ma, mb = float(_mdd_paths(a)[0]), float(_mdd_paths(b)[0])
    out = {"mdd_hedged": ma, "mdd_base": mb, "reduction": 1.0 - ma / mb if mb > 0 else None, "lower_one_sided": None,
           "ci95": [None, None], "block": None}
    if n < 8:
        return out
    bl = _blk(block, n)
    rng = np.random.default_rng(seed)
    red = []
    for k in _chunks(n_boot, 2 * a.size):
        idx = _boot_idx(rng, n, bl, k)
        da, db = _mdd_paths(a[idx]), _mdd_paths(b[idx])
        okm = db > 0
        red.append(1.0 - da[okm] / db[okm])
    red = np.concatenate(red)
    if red.size:
        out.update(lower_one_sided=float(np.quantile(red, 0.05)), ci95=[float(np.quantile(red, 0.025)), float(np.quantile(red, 0.975))])
    out["block"] = bl
    return out


def _vix_fwd(fr: dict, u: int, T: float, vvix_scale: float) -> tuple:
    """(F_adj, sigma, floored) at day u for a VIX option with T years left: F_adj = sqrt((93 VIX3M^2 - 30 VIX^2)/63)
    exp(-sigma^2 T / 2), sigma = vvix_scale x VVIX / 100 (floored at 5%); spot VIX when the forward variance is <= 0."""
    v, v3, vv = float(fr["vix"][u]), float(fr["vix3m"][u]), float(fr["vvix"][u])
    sig = max(vvix_scale * vv / 100.0, 0.05)
    fv = (93.0 * v3 * v3 - 30.0 * v * v) / 63.0
    floored = fv <= 0
    return math.sqrt(v * v if floored else fv) * math.exp(-0.5 * sig * sig * T), sig, floored


def _pad_paths(paths: list) -> np.ndarray:
    """(n, hmax) array of ragged within-cycle value paths, each padded with its last (cycle-end) value: a flat tail adds
    no peak and no trough, so drawdowns of the chained curve are unchanged and each row still ends at the cycle's value."""
    if not paths:
        return np.ones((0, 1))
    h = max(len(p) for p in paths)
    return np.array([np.concatenate([p, np.full(h - len(p), p[-1])]) for p in paths], dtype=float)


def _pos_day(cyc: np.ndarray, h: int, pos: int) -> int:
    """Session index of position ``pos`` on the chained padded curve (0 = the first cycle's start)."""
    if pos <= 0:
        return int(cyc[0][0])
    k, j = divmod(pos - 1, h)
    return int(min(cyc[k][0] + j + 1, cyc[k][1]))


def vix_call_overlay(fr: dict, budget: float = 0.01, hold: int = MONTH, delta: float = 0.25, vvix_scale: float = 1.0,
                     cycles=None) -> dict:
    """Per-cycle returns of SPY (total return) and of SPY with a rolling MODEL-PRICED 25-delta VIX call overlay. ``fr`` needs
    vix, vix3m, vvix, adj, rate, ords. ``cycles``: (start, end) session pairs (the VIX expiry calendar in the harness);
    default the non-overlapping ``hold``-session grid. Each cycle (T = calendar days / 365): F_adj = sqrt((93 VIX3M^2 -
    30 VIX^2)/63) exp(-sigma^2 T / 2), sigma = vvix_scale x VVIX / 100, Black-76 call at forward delta ``delta``, payoff
    on spot VIX at the end session (SOQ proxy). A fraction b = budget x T (1%/yr prorated by calendar time) of the
    portfolio buys calls, the rest holds SPY. ``path_spy`` / ``path_hedged`` (cycles x longest cycle, ragged cycles padded
    with their end value) are the DAILY values relative to each cycle's start: the held call is marked each session with
    the same pricer at that day's VIX, VIX3M, VVIX and bill rate (same strike, T left), and is worth its payoff on the
    end session, so each path ends at the cycle's return."""
    n = len(fr["days"])
    cyc = grid_cycles(n, hold) if cycles is None else np.asarray(cycles, dtype=np.int64).reshape(-1, 2)
    out = {k: [] for k in ("start", "end", "r_spy", "r_hedged", "rf", "prem", "strike", "fwd", "payoff", "fwd_floored",
                           "budget_per_cycle")}
    p_spy, p_hed = [], []
    for t, e in cyc:
        t, e = int(t), int(e)
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        b = budget * T
        r = float(fr["rate"][t])
        fwd, sig, floored = _vix_fwd(fr, t, T, vvix_scale)
        K = b76_call_strike(fwd, T, sig, delta)
        prem = b76_call(fwd, K, T, r, sig)
        pay = max(float(fr["vix"][e]) - K, 0.0)
        r_spy = float(fr["adj"][e] / fr["adj"][t] - 1.0)
        n_calls = b / prem if prem > 0 else 0.0
        ps, ph = np.empty(e - t), np.empty(e - t)
        for j in range(1, e - t + 1):
            u = t + j
            if u < e:
                Tu = (fr["ords"][e] - fr["ords"][u]) / 365.0
                fu, su, _ = _vix_fwd(fr, u, Tu, vvix_scale)
                cu = b76_call(fu, K, Tu, float(fr["rate"][u]), su)
            else:
                cu = pay
            ps[j - 1] = fr["adj"][u] / fr["adj"][t]
            ph[j - 1] = (1.0 - b) * ps[j - 1] + n_calls * cu
        p_spy.append(ps)
        p_hed.append(ph)
        out["start"].append(t)
        out["end"].append(e)
        out["r_spy"].append(r_spy)
        out["r_hedged"].append((1.0 - b) * (1.0 + r_spy) + (b * pay / prem if prem > 0 else 0.0) - 1.0)
        out["rf"].append(math.exp(r * T) - 1.0)
        out["prem"].append(prem)
        out["strike"].append(K)
        out["fwd"].append(fwd)
        out["payoff"].append(pay)
        out["fwd_floored"].append(bool(floored))
        out["budget_per_cycle"].append(b)
    res = {k: np.array(v) for k, v in out.items()}
    res["start"], res["end"] = res["start"].astype(np.int64), res["end"].astype(np.int64)
    res["path_spy"], res["path_hedged"] = _pad_paths(p_spy), _pad_paths(p_hed)
    return res


def put_hedge_overlay(fr: dict, smile: Optional[Smile], budget: float = 0.01, hold: int = MONTH, delta: float = -0.10,
                      cycles=None) -> dict:
    """Control for T-239: the same budget (budget x T) on a MODEL-PRICED 10-delta SPY put held over each (start, end) cycle
    (the SPX monthly expiries in the harness; default the ``hold``-session grid), sigma(K) = VIX/100 x the captured SPY
    smile ratio at K/S and the days to expiry (flat VIX/100 without a smile), priced on the dividend forward, settled on
    the raw close. ``path_hedged`` / ``path_spy`` are daily values relative to each cycle's start (ragged cycles padded with
    their end value), the put marked each session with the same pricer."""
    n = len(fr["days"])
    cyc = grid_cycles(n, hold) if cycles is None else np.asarray(cycles, dtype=np.int64).reshape(-1, 2)

    def sig_fn(V, S, dte):
        return (lambda K: max(V * smile.ratio(K / S, dte), 0.01)) if smile is not None else (lambda K: max(V, 0.01))
    rh, ru, ph_all, ps_all = [], [], [], []
    for t, e in cyc:
        t, e = int(t), int(e)
        S = float(fr["close"][t])
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        b = budget * T
        r = float(fr["rate"][t])
        V = float(fr["vix"][t]) / 100.0
        Sx = S - _pv_div(fr, t, e, r)
        sig = sig_fn(V, S, int(fr["ords"][e] - fr["ords"][t]))
        K = strike_for_delta_smile(Sx, T, r, 0.0, sig, delta, "put", 0.2 * Sx, Sx)
        r_spy = float(fr["adj"][e] / fr["adj"][t] - 1.0)
        ps = np.array([fr["adj"][t + j] / fr["adj"][t] for j in range(1, e - t + 1)])
        prem = None if K is None else _bs(Sx, K, T, r, 0.0, sig(K), "put")
        if K is None:
            rh.append(r_spy)
            ph = ps.copy()
        else:
            pay = max(K - float(fr["close"][e]), 0.0)
            rh.append((1.0 - b) * (1.0 + r_spy) + (b * pay / prem if prem > 0 else 0.0) - 1.0)
            n_puts = b / prem if prem > 0 else 0.0
            ph = np.empty(e - t)
            for j in range(1, e - t + 1):
                u = t + j
                if u < e:
                    Su, ru_ = float(fr["close"][u]), float(fr["rate"][u])
                    Tu = (fr["ords"][e] - fr["ords"][u]) / 365.0
                    pu = _bs(Su - _pv_div(fr, u, e, ru_), K, Tu, ru_, 0.0,
                             sig_fn(float(fr["vix"][u]) / 100.0, Su, int(fr["ords"][e] - fr["ords"][u]))(K), "put")
                else:
                    pu = pay
                ph[j - 1] = (1.0 - b) * ps[j - 1] + n_puts * pu
        ru.append(r_spy)
        ph_all.append(ph)
        ps_all.append(ps)
    return {"r_hedged": np.array(rh), "r_spy": np.array(ru), "path_hedged": _pad_paths(ph_all), "path_spy": _pad_paths(ps_all)}


def vix_hedge_test(fr: dict, smile: Optional[Smile] = None, budget: float = 0.01, hold: int = MONTH, target: float = 0.25,
                   block: int = 12, scales: tuple = (0.8, 1.2), n_boot: int = N_BOOT, seed: int = 0, min_n: int = 180,
                   cal_days=None, cycles=None, put_cycles=None, grid_sensitivity: bool = True) -> dict:
    """T-239. Rule 10(a): the "rolling 1-month" VIX call follows the VIX monthly expiry calendar (``vix_expiry_dates`` on
    ``cal_days``, the exchange calendar used to find holidays, default the frame's days): bought at one expiry's close,
    held to the next (28 or 35 calendar days), paid on spot VIX at that expiry's close. The SPY-put control rolls on SPX's
    monthly expiries (third Fridays) the same way. ``cycles`` / ``put_cycles`` override the calendars. Pass: one-sided 95%
    lower bound of 1 - MDD(hedged)/MDD(SPY) > ``target``. Both maximum drawdowns are measured on DAILY equity (the
    overlay marked to model every session), and the paired percentile bootstrap resamples 12-cycle blocks of the daily
    paths (the same blocks for both series). The Sharpe difference (excess of the bill, on cycle returns) is reported,
    not required. Reported: the same overlay on each of the ``hold`` offsets of a ``hold``-session grid (point
    reductions: range and how many exceed the target). n = monthly cycles."""
    days = fr["days"]
    nd = len(days)
    cal = days if cal_days is None else cal_days
    if cycles is None:
        cycles = rolling_cycles(sessions_for(days, vix_expiry_dates(cal)))
    if put_cycles is None:
        put_cycles = rolling_cycles(sessions_for(days, monthly_expiry_dates(cal)))
    cycles = np.asarray(cycles, dtype=np.int64).reshape(-1, 2)
    cycles = cycles[(cycles[:, 0] >= 0) & (cycles[:, 1] < nd) & (cycles[:, 1] > cycles[:, 0])]
    ov = vix_call_overlay(fr, budget, hold, cycles=cycles)
    n = int(ov["start"].size)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} monthly cycles — too few to test"}
    mr = mdd_reduction_boot(ov["path_hedged"], ov["path_spy"], block, n_boot, seed)

    def red(ph, ps):
        base = float(_mdd_paths(ps)[0])
        return float(1.0 - _mdd_paths(ph)[0] / base) if base > 0 else None
    red_cycle_end = red(_as_paths(ov["r_hedged"]), _as_paths(ov["r_spy"]))     # cycle-end sampling, reported only
    lens = (ov["end"] - ov["start"]).astype(float)
    ppy = PPY / float(lens.mean())
    sh_h, sh_u = sharpe_ratio(ov["r_hedged"] - ov["rf"], ppy), sharpe_ratio(ov["r_spy"] - ov["rf"], ppy)
    bpc = ov["budget_per_cycle"]
    hedge_pnl = bpc * (ov["payoff"] / ov["prem"] - 1.0)
    sens = {}
    for sc in scales:
        o2 = vix_call_overlay(fr, budget, hold, vvix_scale=sc, cycles=cycles)
        sens[str(sc)] = red(o2["path_hedged"], o2["path_spy"])
    pc = np.asarray(put_cycles, dtype=np.int64).reshape(-1, 2)
    pc = pc[(pc[:, 0] >= 0) & (pc[:, 1] < nd) & (pc[:, 1] > pc[:, 0])]
    ph = put_hedge_overlay(fr, smile, budget, hold, cycles=pc) if pc.shape[0] else None
    put_red = red(ph["path_hedged"], ph["path_spy"]) if ph is not None else None
    H = ov["path_spy"].shape[1]
    acc = np.array([[math.exp(float(fr["rate"][t]) * (fr["ords"][min(t + j, e)] - fr["ords"][t]) / 365.0) for j in range(1, H + 1)]
                    for t, e in zip(ov["start"], ov["end"])])
    cash_red = red((1.0 - bpc[:, None]) * ov["path_spy"] + bpc[:, None] * acc, ov["path_spy"])
    grid = []
    if grid_sensitivity:
        for k in range(hold):
            gc = grid_cycles(nd, hold, k)
            if gc.shape[0] >= 8:
                og = vix_call_overlay(fr, budget, hold, cycles=gc)
                grid.append({"offset": k, "n": int(gc.shape[0]), "reduction": red(og["path_hedged"], og["path_spy"])})
    gred = [g["reduction"] for g in grid if g["reduction"] is not None]
    lb, ci = mr["lower_one_sided"], mr["ci95"]
    crit = [(f"one-sided 95% lower bound of the drawdown reduction (daily equity) > {target:.0%}", None if lb is None else lb > target,
             ci[1] is not None and ci[1] < target)]
    verdict, why = _decide(crit, n, min_n, "monthly cycles")
    cyc = np.stack([ov["start"], ov["end"]], axis=1)
    _, sp, st = _mdd_span(ov["path_spy"])
    _, hp, ht = _mdd_span(ov["path_hedged"])
    dd = lambda pos: days[_pos_day(cyc, H, pos)]
    reason = (f"{MP} (Black-76 on F_adj = sqrt((93 VIX3M^2 - 30 VIX^2)/63) exp(-VVIX^2 T/2), sigma = VVIX/100, 25-delta strike, "
              f"marked daily with the same pricer, payoff on spot VIX at expiry; no transaction costs, none stated in the claim): {n} monthly cycles "
              f"on the VIX expiry calendar (the Wednesday 30 days before the next month's third Friday, CBOE holiday rules; bought at one "
              f"expiry's close and held to the next, {int(lens.min())}-{int(lens.max())} sessions) {days[int(ov['start'][0])]}..{days[int(ov['end'][-1])]}, "
              f"budget {budget:.0%}/yr prorated by calendar time ({bpc.mean()*100:.3f}% per cycle on average); maximum drawdown on DAILY equity: SPY "
              f"total return {mr['mdd_base']*100:.1f}% ({dd(sp)}..{dd(st)}) vs hedged {mr['mdd_hedged']*100:.1f}% "
              f"({dd(hp)}..{dd(ht)}): reduction {_s(None if mr['reduction'] is None else mr['reduction']*100, 1)}%, one-sided 95% "
              f"lower bound {_s(None if lb is None else lb*100, 1)}% (two-sided {_ci_s(tuple(None if x is None else x*100 for x in ci), 1)}; "
              f"12-cycle blocks of daily paths, paired) vs {target:.0%}; on cycle-end points only the reduction would be "
              f"{_s(None if red_cycle_end is None else red_cycle_end * 100, 1)}% (reported). Sharpe (excess of the bill) hedged {sh_h:.2f} vs SPY {sh_u:.2f} (difference "
              f"{sh_h - sh_u:+.2f}, reported); hedge P&L {hedge_pnl.mean()*1e4:+.2f} bp of the portfolio per cycle, calls paid in "
              f"{int((ov['payoff'] > 0).sum())} of {n} cycles. IV-scale sensitivity (daily MDD; VVIX x "
              + ", ".join(f"{k}: {_s(None if v is None else v * 100, 1)}%" for k, v in sens.items())
              + f"). Rule 10 grid sensitivity (reported): the same overlay on the {len(grid)} offsets of a {hold}-session grid gives "
              f"reductions {_rng(gred, 1, 100)}%, {sum(1 for x in gred if x > target)}/{len(grid)} above {target:.0%}. Controls (daily MDD): 10-delta SPY put "
              f"same budget rolled on the SPX monthly expiries ({pc.shape[0]} cycles; {'captured SPY smile' if smile is not None else 'flat VIX'}, marked daily) reduction "
              f"{_s(None if put_red is None else put_red * 100, 1)}%; cash drag at the same budget "
              f"{_s(None if cash_red is None else cash_red * 100, 1)}%" + (f"; {int(ov['fwd_floored'].sum())} cycles with a negative forward variance used VIX" if ov['fwd_floored'].any() else "")
              + ". The traded version needs VIX option chain history (2 capture days archived)")
    return {"n": n, "min_n": min_n, "reduction": mr["reduction"], "lower_one_sided": lb, "ci95": ci, "mdd_spy": mr["mdd_base"],
            "mdd_hedged": mr["mdd_hedged"], "mdd_spy_span": [dd(sp), dd(st)], "mdd_hedged_span": [dd(hp), dd(ht)],
            "mdd_measure": "daily equity", "calendar": "VIX monthly expiry, rolled at each expiry",
            "first_cycle": days[int(ov["start"][0])], "last_expiry": days[int(ov["end"][-1])],
            "cycle_sessions_range": [int(lens.min()), int(lens.max())],
            "reduction_cycle_end_sampling": red_cycle_end, "sharpe_hedged": sh_h, "sharpe_spy": sh_u,
            "hedge_pnl_per_cycle": float(hedge_pnl.mean()), "scale_sensitivity": sens, "put_control_reduction": put_red,
            "put_control_cycles": int(pc.shape[0]), "cash_drag_reduction": cash_red, "grid_offsets": grid,
            "block": mr["block"], "verdict": verdict, "reason": reason + " — " + why}


# =========================================================================== T-240: VVIX vs realised VIX vol ==

def vvix_win_rate(days, vvix, vix, window: int = MONTH, bound: float = 0.70, block: int = 6, n_boot: int = N_BOOT,
                  seed: int = 0, min_n: int = 200, spx=None, n_placebo: int = 1000, start: str = "2006-01-01",
                  entries=None) -> dict:
    """T-240 on daily arrays on a TRADING calendar (``days``: ^GSPC sessions in the harness; ``vix`` as of each session,
    ``vvix`` NaN on a session without its own print). Rule 10(a): "non-overlapping months since 2006" names the calendar
    month: each month enters at its first session with a VVIX print on or after ``start`` (``entries`` overrides), and
    win_t = 1{VVIX_t > 100 sqrt(252) sd(dlnVIX over t..t+21)} (21 daily changes of spot VIX on the trading calendar,
    ddof 1). Months have 19-23 sessions, so a window can run a session or two into the next month (more where VVIX's
    first print of a month comes late, as in 2006); the overlap is reported. Pass: the one-sided 95% lower
    bound of the win rate > ``bound`` under BOTH the exact binomial (Clopper-Pearson) and a percentile block bootstrap
    (block 6 months); mean premium VVIX - realised > 0 in both halves. Reported: the 21-session grid, pooled over every
    daily entry (percentile bootstrap, 126-session blocks) and on each of its 21 offsets (Clopper-Pearson lower bounds).
    ``spx`` (aligned closes) adds the SPX VRP win-rate control. n = months."""
    days = list(days)
    vvix, vix = np.asarray(vvix, dtype=float), np.asarray(vix, dtype=float)
    N = len(days)
    m_all = N - window
    if m_all < 8:
        return {"n": max(m_all, 0), "verdict": "inconclusive", "reason": f"only {max(m_all, 0)} sessions with a forward window"}
    lr = np.diff(np.log(vix))
    rv_all = 100.0 * math.sqrt(PPY) * sliding_window_view(lr, window)[:m_all].std(axis=1, ddof=1)
    okv = np.isfinite(vvix) & (vvix > 0)
    okv[:m_all] &= np.isfinite(rv_all)
    okv[m_all:] = False
    ts = month_first(days, ok=okv, start=start) if entries is None else np.asarray(entries, dtype=np.int64)
    ts = ts[(ts < m_all) & okv[np.minimum(ts, N - 1)]]
    if ts.size < 8:
        return {"n": int(ts.size), "verdict": "inconclusive", "reason": f"only {ts.size} months — too few to test"}
    rv = rv_all[ts]
    win = (vvix[ts] > rv).astype(float)
    k, n = int(win.sum()), int(ts.size)
    cp1 = _binom_two_sided_ci(k, n, 0.10)
    cp2 = _binom_two_sided_ci(k, n, 0.05)
    boot = pct_means(win, block, n_boot, seed)
    b_lo1 = float(np.quantile(boot, 0.05))
    lb = min(cp1[0], b_lo1)
    prem = vvix[ts] - rv
    halves = [float(p.mean()) for p in np.array_split(prem, 2)]
    hw = [float(p.mean()) for p in np.array_split(win, 2)]
    ovl_all = np.maximum(ts[:-1] + window - ts[1:], 0)
    ovl, n_ovl3 = int(ovl_all.max()), int((ovl_all > 2).sum())
    # rule 10: the 21-session grid (reported)
    gi = np.arange(int(ts[0]), m_all, dtype=np.int64)
    gi = gi[okv[gi]]
    gwin = (vvix[gi] > rv_all[gi]).astype(float)
    gb = pct_means(gwin, pool_block_len(window, block), max(500, n_boot // 2), seed)
    g_lo = float(np.quantile(gb, 0.05))
    goff = offset_of(gi, window)
    gcp = []
    for q in range(window):
        wq = gwin[goff == q]
        if wq.size:
            gcp.append({"offset": q, "n": int(wq.size), "rate": float(wq.mean()),
                        "cp_lower": float(_binom_two_sided_ci(int(wq.sum()), int(wq.size), 0.10)[0])})
    spx_wr = None
    if spx is not None:
        lrs = np.diff(np.log(np.asarray(spx, dtype=float)))
        rvs = np.array([float(np.sum(lrs[t:t + window] ** 2)) * PPY / window for t in ts])
        oks = np.isfinite(rvs)
        spx_wr = float(((vix[ts] / 100.0) ** 2 > rvs)[oks].mean()) if oks.any() else None
    rng = np.random.default_rng(seed + 13)
    plc = float(np.mean([(rng.permutation(vvix[ts]) > rv).mean() for _ in range(n_placebo)]))
    crit = [(f"one-sided 95% lower bound of the win rate > {bound:.2f} (min of Clopper-Pearson and block bootstrap)", lb > bound,
             max(cp1[1], float(np.quantile(boot, 0.95))) < bound),
            ("mean premium VVIX - realised > 0 in both halves", all(h > 0 for h in halves), False)]
    verdict, why = _decide(crit, n, min_n, "calendar months")
    reason = (f"VVIX above the realised 21d vol of daily log changes in spot VIX in {k} of {n} calendar months, each entered at "
              f"its first session with a VVIX print ({days[ts[0]]}..{days[ts[-1]]}; spot-VIX changes over 21 sessions of the "
              f"trading calendar; a window runs at most {ovl} session(s) into the next month's, {n_ovl3} by more than 2, all where "
              f"VVIX's history is sparse): win rate {k/n:.3f}, one-sided 95% lower bound Clopper-Pearson {cp1[0]:.3f} / "
              f"block bootstrap {b_lo1:.3f} (two-sided exact {cp2[0]:.3f}-{cp2[1]:.3f}) vs {bound:.2f}; mean premium "
              f"{prem.mean():+.1f} vol pts, halves {halves[0]:+.1f}/{halves[1]:+.1f} (win rates {hw[0]:.2f}/{hw[1]:.2f}). Rule 10 "
              f"grid sensitivity (reported): all {gi.size} daily entries pooled win rate {gwin.mean():.3f} (one-sided lower "
              f"{g_lo:.3f}, {pool_block_len(window, block)}-session blocks); the {len(gcp)} offsets of the {window}-session grid give "
              f"win rates {_rng([g['rate'] for g in gcp], 3)}, Clopper-Pearson lower bounds {_rng([g['cp_lower'] for g in gcp], 3)}, "
              f"{sum(g['cp_lower'] > bound for g in gcp)}/{len(gcp)} above {bound:.2f}. Controls: "
              f"SPX VRP win rate (VIX^2 > RV) in the same months {_f(spx_wr, 3)}; shuffled-VVIX placebo win rate {plc:.3f}. "
              "Spot VIX moves more than the futures VVIX refers to, so the comparison is conservative for the claim")
    return {"n": n, "min_n": min_n, "wins": k, "win_rate": k / n, "cp_lower_one_sided": cp1[0], "cp_two_sided": list(cp2),
            "boot_lower_one_sided": b_lo1, "lower_bound": lb, "mean_premium": float(prem.mean()), "premium_halves": halves,
            "win_rate_halves": hw, "spx_vrp_win_rate": spx_wr, "placebo_win_rate": plc, "first_window": days[ts[0]],
            "last_window": days[ts[-1]], "calendar": "calendar months, first session with a VVIX print",
            "max_window_overlap": ovl, "windows_overlapping_over_2": n_ovl3,
            "grid_pooled_rate": float(gwin.mean()), "grid_pooled_lower": g_lo, "grid_offsets": gcp,
            "verdict": verdict, "reason": reason + " — " + why}


def vix_call_ratio_secondary(days, vix, vix3m, vvix, rate, hold: int = MONTH, k1_off: float = 4.0, k2_off: float = 10.0,
                             block: int = 6, n_boot: int = N_BOOT, seed: int = 0, cal_days=None, cycles=None) -> dict:
    """T-240 secondary: MODEL-PRICED 1x2 VIX call ratio (long 1 at F_adj + 4, short 2 at K1 + 10), Black-76 on F_adj with
    VVIX as IV, settled on spot VIX; P&L in VIX points per cycle (premium received / paid carried at the bill). Rule 10(a):
    cycles roll on the VIX monthly expiries (``vix_expiry_dates`` on ``cal_days``, default ``days``); ``cycles`` overrides."""
    days = list(days)
    ords = _ords(days)
    if cycles is None:
        cycles = rolling_cycles(sessions_for(days, vix_expiry_dates(days if cal_days is None else cal_days)))
    pnl = []
    for t, e in np.asarray(cycles, dtype=np.int64).reshape(-1, 2):
        T = (ords[e] - ords[t]) / 365.0
        sig = max(vvix[t] / 100.0, 0.05)
        fv = (93.0 * vix3m[t] ** 2 - 30.0 * vix[t] ** 2) / 63.0
        F = math.sqrt(fv if fv > 0 else vix[t] ** 2) * math.exp(-0.5 * sig * sig * T)
        k1 = F + k1_off
        k2 = k1 + k2_off
        debit = b76_call(F, k1, T, rate[t], sig) - 2.0 * b76_call(F, k2, T, rate[t], sig)
        V = vix[e]
        pnl.append(max(V - k1, 0.0) - 2.0 * max(V - k2, 0.0) - debit * math.exp(rate[t] * T))
    x = np.array(pnl)
    bt = stud_mean(x, block, n_boot, seed)
    return {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "ci95": list(two_sided(bt)),
            "calendar": "VIX monthly expiry, rolled at each expiry"}


# ==================================================================== T-249: forward vs spot variance premium ==

def forward_variance_premium(days, px, vix, vix3m, cycle: int = 63, block_daily: int = 63, block_cycle: int = 2,
                             n_boot: int = N_BOOT, seed: int = 0, min_n: int = 60, excl_year: str = "2020",
                             n_shift: int = 500) -> dict:
    """T-249 on aligned daily arrays (px dividend-adjusted). F^2 = (93 VIX3M^2 - 30 VIX^2)/63; forward premium fraction
    (F^2 - RV(22..63))/F^2, spot (VIX^2 - RV(1..21))/VIX^2; d = forward - spot, per daily start with F^2 > 0.

    Rule 10(b): the trial's non-overlapping 63-session grid has 63 equally valid offsets. Primary statistic: the POOLED
    mean of d over every daily start (studentized circular block bootstrap, block pool_block_len(cycle, block_cycle) =
    126 sessions = 2 holds). Criteria: (1) the pooled difference > 0 with the two-sided 95% CI excluding zero (the pass
    rule, on the rule-10 primary statistic); (2) the trial's own all-daily-starts test with ``block_daily``-session
    blocks. Each offset's grid (studentized, block ``block_cycle`` cycles) is reported: range of its mean and CI bounds
    and how many offsets pass. The forward win rate (> 0.7) is reported, as the pass rule marks it. n = the distinct
    63-session holds the daily starts span (the cycle count of the claim's non-overlapping grid)."""
    days = list(days)
    px, vix, vix3m = (np.asarray(a, dtype=float) for a in (px, vix, vix3m))
    n_all = len(days) - 63
    if n_all < 100:
        return {"n": 0, "verdict": "inconclusive", "reason": f"only {max(n_all, 0)} aligned days with a 63-day forward window — too few to test"}
    lr = np.diff(np.log(px))
    rv_s, rv_f = _fwd_rv(lr, n_all, 1, 21), _fwd_rv(lr, n_all, 22, 63)

    def parts(v3):
        v2 = (vix[:n_all] / 100.0) ** 2
        f2 = (93.0 * (v3[:n_all] / 100.0) ** 2 - 30.0 * v2) / 63.0
        okm = f2 > 0
        pf = np.where(okm, (f2 - rv_f) / np.where(okm, f2, 1.0), np.nan)
        ps = (v2 - rv_s) / v2
        return f2, v2, okm, pf, ps

    f2, v2, okm, pf, ps = parts(vix3m)
    d = pf - ps
    didx = np.nonzero(okm)[0]
    dd = d[didx]
    n = n_holds(didx, cycle)
    pb = pool_block_len(cycle, block_cycle)
    bt_p = stud_mean(dd, pb, n_boot, seed)
    bt_d = stud_mean(dd, block_daily, n_boot, seed)
    ci_p, ci_d = two_sided(bt_p), two_sided(bt_d)
    offs = []
    off = offset_of(didx, cycle)
    for k in range(cycle):
        sel = didx[off == k]
        b_k = stud_mean(d[sel], block_cycle, n_boot, seed)
        if b_k is None:
            continue
        lo_k, hi_k = two_sided(b_k)
        offs.append({"offset": k, "n": int(sel.size), "first": days[sel[0]], "mean": b_k["est"], "ci": [lo_k, hi_k],
                     "pass": bool(b_k["est"] > 0 and lo_k is not None and lo_k > 0)})
    win = float((f2[didx] > rv_f[didx]).mean())
    halves = [float(p.mean()) for p in np.array_split(dd, 2)]
    keep = np.array([not days[i].startswith(excl_year) for i in didx], dtype=bool)
    ex = float(dd[keep].mean()) if keep.any() else None
    lvl = (f2 - rv_f) - (v2 - rv_s)
    bt_l = stud_mean(lvl[didx], pb, n_boot, seed)
    rng = np.random.default_rng(seed + 17)
    null = []
    for _ in range(n_shift):
        sh = int(rng.integers(252, max(253, len(days) - 252)))
        _, _, ok2, pf2, ps2 = parts(np.roll(vix3m, sh))
        if ok2.any():
            null.append(float(np.mean(pf2[ok2] - ps2[ok2])))
    null = np.asarray(null)
    plc_p = float((np.sum(null >= bt_p["est"]) + 1) / (null.size + 1)) if (null.size and bt_p) else None
    crit = [(f"POOLED over all {cycle} grid offsets ({pb}-session blocks): paired difference > 0 with the 95% CI excluding zero",
             None if ci_p[0] is None else (bt_p["est"] > 0 and ci_p[0] > 0), ci_p[1] is not None and ci_p[1] < 0),
            (f"all daily starts with {block_daily}-session blocks (the trial's procedure): paired difference > 0 with the 95% CI excluding zero",
             None if ci_d[0] is None else (bt_d["est"] > 0 and ci_d[0] > 0), ci_d[1] is not None and ci_d[1] < 0)]
    verdict, why = _decide(crit, n, min_n, f"non-overlapping {cycle}d cycles (distinct holds)")
    n_off = len(offs)
    reason = (f"forward premium fraction (F^2 - RV22..63)/F^2 minus spot (VIX^2 - RV1..21)/VIX^2. POOLED over all {cycle} grid "
              f"offsets ({didx.size} daily starts {days[didx[0]]}..{days[didx[-1]]} = {n} distinct {cycle}-session holds; studentized "
              f"circular block bootstrap, block {pb} sessions): mean {_s(bt_p['est'] if bt_p else None, 3)} ({_ci_s(ci_p, 3)}); with the "
              f"trial's {block_daily}-session blocks {_ci_s(ci_d, 3)}. Per grid offset ({n_off} non-overlapping {cycle}d grids, n "
              f"{_rng([o['n'] for o in offs], 0).replace('+', '')} cycles, block {block_cycle}): mean {_rng([o['mean'] for o in offs], 3)}, "
              f"lower CI bound {_rng([o['ci'][0] for o in offs], 3)}, upper {_rng([o['ci'][1] for o in offs], 3)}; "
              f"{sum(o['pass'] for o in offs)}/{n_off} offsets pass, {sum(o['ci'][1] is not None and o['ci'][1] < 0 for o in offs)}/{n_off} "
              f"fail decisively. Mean forward fraction {np.nanmean(pf[didx]):+.3f} vs spot {np.mean(ps[didx]):+.3f}; forward win rate "
              f"(F^2 > RV22..63) {_f(win, 2)} (reported; the pass marks the 0.7 line as reported). Walk-forward halves "
              f"{_s(halves[0], 3)}/{_s(halves[1], 3)}; excluding {excl_year} {_s(ex, 3)}; level version (variance units) "
              f"{_s(bt_l['est'] if bt_l else None, 4)} ({_ci_s(two_sided(bt_l), 4)}); shifted-VIX3M placebo p={_f(plc_p, 3)}"
              + (f"; {int((~okm).sum())} days with F^2 <= 0 excluded" if (~okm).any() else ""))
    return {"n": n, "min_n": min_n, "n_daily": int(didx.size), "block_days": pb, "mean_pooled": bt_p["est"] if bt_p else None,
            "ci_pooled": list(ci_p), "mean_daily": bt_d["est"] if bt_d else None, "ci_daily": list(ci_d),
            "grid_offsets": offs, "forward_win_rate": win, "halves": halves, "excl_year_mean": ex,
            "level_mean": bt_l["est"] if bt_l else None, "level_ci": list(two_sided(bt_l)), "placebo_p": plc_p,
            "first_start": days[didx[0]], "last_start": days[didx[-1]], "verdict": verdict, "reason_core": reason, "why": why}


def variance_strip(vals, expiry: str, quote_day: str, r: float, roots=("SPXW", "SPX")) -> Optional[dict]:
    """Model-free (CBOE VIX-method) implied variance of one captured expiry: F by put-call parity, K0 the first strike at or
    below F, out-of-the-money mids walked outward until two consecutive zero bids, sigma^2 = 2/T sum dK/K^2 e^{rT} Q(K) -
    (F/K0 - 1)^2 / T. T = calendar days / 365 from the quote day (settlement-time detail ignored)."""
    T = (date.fromisoformat(expiry) - date.fromisoformat(quote_day)).days / 365.0
    if T <= 0:
        return None
    root, by = _chain_by_strike(vals, expiry, roots)
    fw = _parity_forward(by, T, r)
    if fw is None:
        return None
    F, _ = fw
    ks = sorted(by)
    below = [K for K in ks if K <= F]
    if not below:
        return None
    K0 = below[-1]
    sel = {}
    for side, seq in (("put", [K for K in reversed(ks) if K < K0]), ("call", [K for K in ks if K > K0])):
        zeros = 0
        for K in seq:
            row = by[K].get(side)
            if not row or not (row.get("bid") or 0) > 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            m = _mid(row)
            if m is not None:
                sel[K] = m
    c0, p0 = _mid(by[K0].get("call")), _mid(by[K0].get("put"))
    if c0 is None or p0 is None:
        return None
    sel[K0] = 0.5 * (c0 + p0)
    kk = sorted(sel)
    if len(kk) < 5:
        return None
    tot = 0.0
    for i, K in enumerate(kk):
        dK = (kk[min(i + 1, len(kk) - 1)] - kk[max(i - 1, 0)]) / (2.0 if 0 < i < len(kk) - 1 else 1.0)
        tot += dK / (K * K) * math.exp(r * T) * sel[K]
    var = 2.0 / T * tot - (F / K0 - 1.0) ** 2 / T
    return {"expiry": expiry, "root": root, "T": T, "days": int(round(T * 365)), "forward": F, "K0": K0, "n_strikes": len(kk), "var": var}


def _bracket(strips: list, target: int) -> tuple:
    lo = [s["days"] for s in strips if s["days"] <= target]
    hi = [s["days"] for s in strips if s["days"] >= target]
    return tuple(x for x in (lo[-1] if lo else None, hi[0] if hi else None) if x is not None)


def strip_check(vals, quote_day: str, r: float, vix_q: Optional[float], vix3m_q: Optional[float]) -> Optional[dict]:
    """Strip discretisation check (T-249 procedure): strip variances interpolated (CBOE's linear-in-time total variance) to
    30 and 93 calendar days and compared with the VIX and VIX3M closes of the quote day, plus the 30-to-93-day forward."""
    qd = date.fromisoformat(quote_day)
    exps = sorted({v.get("expiry") for v in vals if v.get("expiry") and (date.fromisoformat(v["expiry"]) - qd).days >= 7})
    strips = [s for s in (variance_strip(vals, e, quote_day, r) for e in exps if (date.fromisoformat(e) - qd).days <= 130) if s and s["var"] > 0]

    def interp(target):
        lo = [s for s in strips if s["days"] <= target]
        hi = [s for s in strips if s["days"] >= target]
        if not lo or not hi:
            return None
        a, b = lo[-1], hi[0]
        if a["days"] == b["days"]:
            return a["var"]
        w = (b["days"] - target) / (b["days"] - a["days"])
        return (a["T"] * a["var"] * w + b["T"] * b["var"] * (1 - w)) * 365.0 / target
    v30, v93 = interp(30), interp(93)
    if v30 is None or v93 is None:
        return None
    out = {"quote_day": quote_day, "n_expiries": len(strips), "strip_30": 100 * math.sqrt(v30), "strip_93": 100 * math.sqrt(v93),
           "vix": vix_q, "vix3m": vix3m_q,
           "strikes_30": [s["n_strikes"] for s in strips if s["days"] in _bracket(strips, 30)],
           "strikes_93": [s["n_strikes"] for s in strips if s["days"] in _bracket(strips, 93)]}
    out["err_30"] = None if vix_q is None else out["strip_30"] - vix_q
    out["err_93"] = None if vix3m_q is None else out["strip_93"] - vix3m_q
    f2_s = (93 * v93 - 30 * v30) / 63
    out["fwd_strip"] = 100 * math.sqrt(f2_s) if f2_s > 0 else None
    if vix_q is not None and vix3m_q is not None:
        f2_i = (93 * vix3m_q ** 2 - 30 * vix_q ** 2) / 63
        out["fwd_index"] = math.sqrt(f2_i) if f2_i > 0 else None
    return out


# ======================================================================== T-511: weekend vs weekday variance ==

def _week_stats(days, px, winsor: Optional[float] = None) -> dict:
    """Per-ISO-week sufficient statistics of SPY close-to-close log returns labelled by calendar gap: weekend (Fri -> Mon,
    3 days) and weekday single nights (gap 1, starting Mon..Thu); holiday gaps are excluded. A return belongs to the week
    of its end day. With ``winsor`` the returns are clipped at that quantile of |r| (over the labelled returns)."""
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    lr = np.diff(np.log(np.asarray(px, dtype=float)))
    gap = np.diff(ords)
    wd0 = np.array([date.fromordinal(int(o)).weekday() for o in ords[:-1]])
    we = (gap == 3) & (wd0 == 4)
    wk = (gap == 1) & (wd0 <= 3)
    hol = (gap >= 4) & (gap <= 5)
    used = we | wk
    if winsor is not None and used.any():
        cap = float(np.quantile(np.abs(lr[used]), winsor))
        lr = np.clip(lr, -cap, cap)
    keys = [date.fromordinal(int(o)).isocalendar()[:2] for o in ords[1:]]
    uk = sorted(set(keys[i] for i in np.nonzero(used)[0]))
    pos = {k: i for i, k in enumerate(uk)}
    W = len(uk)
    S = np.zeros((W, 15))      # weekend n, s, ss; then weekday k=0..3: n, s, ss
    for i in np.nonzero(used)[0]:
        w = pos[keys[i]]
        c = 0 if we[i] else 3 + 3 * int(wd0[i])
        S[w, c] += 1.0
        S[w, c + 1] += lr[i]
        S[w, c + 2] += lr[i] ** 2
    return {"S": S, "weeks": uk, "n_weekend": int(we.sum()), "n_weekday": int(wk.sum()),
            "holiday_var": float(np.var(lr[hol], ddof=1)) if hol.sum() > 1 else None, "n_holiday": int(hol.sum())}


def _ratio_from(S) -> np.ndarray:
    """Variance ratio from summed sufficient statistics (rows): Var(weekend) / mean over k of Var(weekday k)."""
    S = np.atleast_2d(S)

    def var(n, s, ss):
        return (ss - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1)
    num = var(S[:, 0], S[:, 1], S[:, 2])
    den = np.mean([var(S[:, 3 + 3 * k], S[:, 4 + 3 * k], S[:, 5 + 3 * k]) for k in range(4)], axis=0)
    return num / np.where(den > 0, den, np.nan)


def weekend_ratio_boot(S: np.ndarray, block: int = 4, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """R and its percentile circular block bootstrap over weeks (blocks of ``block`` weeks)."""
    W = S.shape[0]
    R = float(_ratio_from(S.sum(axis=0))[0]) if W else None
    out = {"R": R, "ci95": [None, None], "n_weeks": int(W)}
    if W < 8:
        return out
    b = _blk(block, W)
    rng = np.random.default_rng(seed)
    rs = []
    for k in _chunks(n_boot, W):
        idx = _boot_idx(rng, W, b, k)
        cnt = np.zeros((k, W))
        np.add.at(cnt, (np.repeat(np.arange(k), W), idx.ravel()), 1.0)
        rs.append(_ratio_from(cnt @ S))
    rs = np.concatenate(rs)
    rs = rs[np.isfinite(rs)]
    if rs.size:
        out["ci95"] = [float(np.quantile(rs, 0.025)), float(np.quantile(rs, 0.975))]
    return out


def weekend_variance_ratio(days, px, bound: float = 1.5, block_weeks: int = 4, n_boot: int = N_BOOT, seed: int = 0,
                           min_n: int = 1500, winsor: float = 0.99, raw_px=None) -> dict:
    """T-511. R = Var(Fri close -> Mon close) / mean over Mon..Thu starts of Var(single-night close -> next close). Pass:
    the upper end of the two-sided 95% CI of R < ``bound`` overall (the claim) and in both walk-forward halves (the pass
    rule); percentile bootstrap of 4-week blocks of weeks. n = weekend returns."""
    days = list(days)
    st = _week_stats(days, px)
    S = st["S"]
    W = S.shape[0]
    if W < 16:
        return {"n": st["n_weekend"], "verdict": "inconclusive", "reason": f"only {W} weeks of labelled returns — too few to test"}
    full = weekend_ratio_boot(S, block_weeks, n_boot, seed)
    h = W // 2
    hs = [weekend_ratio_boot(S[:h], block_weeks, n_boot, seed), weekend_ratio_boot(S[h:], block_weeks, n_boot, seed)]
    hl = [f"{st['weeks'][0][0]}w{st['weeks'][0][1]}..{st['weeks'][h - 1][0]}w{st['weeks'][h - 1][1]}",
          f"{st['weeks'][h][0]}w{st['weeks'][h][1]}..{st['weeks'][-1][0]}w{st['weeks'][-1][1]}"]
    one = weekend_ratio_boot(S, 1, n_boot, seed)
    wz = _week_stats(days, px, winsor)
    r_w = float(_ratio_from(wz["S"].sum(axis=0))[0])
    r_raw = None
    if raw_px is not None:
        r_raw = float(_ratio_from(_week_stats(days, raw_px)["S"].sum(axis=0))[0])
    tot = S.sum(axis=0)
    wd_var = float(np.mean([(tot[5 + 3 * k] - tot[4 + 3 * k] ** 2 / tot[3 + 3 * k]) / (tot[3 + 3 * k] - 1) for k in range(4)]))
    hol_ratio = st["holiday_var"] / wd_var if st["holiday_var"] is not None and wd_var > 0 else None
    n = st["n_weekend"]

    def crit_for(lab, b):
        lo, hi = b["ci95"]
        return (f"{lab}: upper end of the 95% CI of R < {bound}", None if hi is None else hi < bound, lo is not None and lo >= bound)
    crit = [crit_for("full sample (the claim)", full), crit_for(f"first half {hl[0]}", hs[0]), crit_for(f"second half {hl[1]}", hs[1])]
    verdict, why = _decide(crit, n, min_n, "Fri->Mon weekend returns")
    reason = (f"SPY (dividend-adjusted) Fri->Mon variance / mean Mon..Thu single-night variance: R {full['R']:.3f} "
              f"({_ci_s(full['ci95'], 3)}) over {n} normal weekends and {st['n_weekday']} weekday nights ({days[0]}..{days[-1]}, "
              f"holiday gaps excluded); halves {hs[0]['R']:.3f} ({_ci_s(hs[0]['ci95'], 3)}) and {hs[1]['R']:.3f} ({_ci_s(hs[1]['ci95'], 3)}) "
              f"vs {bound} (blocks of {block_weeks} weeks; with 1-week blocks the full-sample {_ci_s(one['ci95'], 3)}). Robustness: top "
              f"{100 - winsor * 100:.0f}% |returns| winsorised R {r_w:.3f}; raw closes R {_f(r_raw, 3)}; "
              f"holiday gaps (4-5 days, n={st['n_holiday']}) variance ratio {_f(hol_ratio, 3)}. Calendar-day pricing charges 3x; whether "
              "listed options do is the separate capture-driven check (Friday-close vs Monday ATM straddle marks), not tested here")
    return {"n": n, "min_n": min_n, "R": full["R"], "ci95": full["ci95"], "halves": [{"label": l, **b} for l, b in zip(hl, hs)],
            "n_weekday": st["n_weekday"], "ci95_one_week_blocks": one["ci95"], "R_winsorised": r_w, "R_raw": r_raw, "holiday_ratio": hol_ratio,
            "verdict": verdict, "reason": reason + " — " + why}


# ============================================================ T-538: implied vs realised average correlation ==

def realised_avg_corr(R: np.ndarray, w: Optional[np.ndarray] = None) -> float:
    """sum_{i != j} w_i w_j s_i s_j rho_ij / sum_{i != j} w_i w_j s_i s_j over the columns of R (rows = days): the
    realised analogue of the CBOE implied-correlation formula with the index variance of the w-weighted basket."""
    R = np.asarray(R, dtype=float)
    k = R.shape[1]
    w = np.full(k, 1.0 / k) if w is None else np.asarray(w, dtype=float)
    C = np.cov(R, rowvar=False, ddof=1)
    s = np.sqrt(np.diag(C))
    ws = w * s
    num = float(w @ C @ w - np.sum(ws ** 2))
    den = float(np.sum(ws) ** 2 - np.sum(ws ** 2))
    return num / den if den > 0 else float("nan")


def implied_vs_realised_corr(days, cor1m, comps: np.ndarray, names: Sequence[str], hold: int = MONTH, block: int = 6,
                             n_boot: int = N_BOOT, seed: int = 0, min_n: int = 240, start: str = "2006-01-01",
                             constituents: bool = False) -> dict:
    """T-538 on aligned daily arrays: COR1M (index points) and component closes (k x n, dividend-adjusted). gap_t =
    COR1M_t/100 - realised average correlation over t+1..t+21 (equal weights). Rule 10(b): the procedure's monthly
    non-overlapping 21-session grid has 21 equally valid offsets; the primary statistic is the POOLED mean gap over
    every daily start from ``start`` (studentized circular block bootstrap, block pool_block_len(hold, block) = 126
    sessions), each offset's grid (block ``block`` windows) reported. With ``constituents`` False the components are a
    proxy, and the claim's statistic (the index constituents) and its straddle-book clause are not implemented; the
    proxy's interval is reported as a one-sided bound. n = distinct 21-session holds the entries span."""
    days = list(days)
    cor1m = np.asarray(cor1m, dtype=float)
    comps = np.asarray(comps, dtype=float)
    lr = np.diff(np.log(comps), axis=1)
    N = len(days)
    t0 = next((i for i, d in enumerate(days) if d >= start), N)
    cand = np.arange(t0, max(t0, N - hold), dtype=np.int64)
    rho_all = np.array([realised_avg_corr(lr[:, t:t + hold].T) for t in cand]) if cand.size else np.zeros(0)
    gap_all = cor1m[cand] / 100.0 - rho_all if cand.size else np.zeros(0)
    ok = np.isfinite(gap_all)
    idx, gap, rho = cand[ok], gap_all[ok], rho_all[ok]
    n = n_holds(idx, hold)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} monthly windows — too few to test"}
    pb = pool_block_len(hold, block)
    bt = stud_mean(gap, pb, n_boot, seed)
    ci = two_sided(bt)
    halves = [float(p.mean()) for p in np.array_split(gap, 2)]
    offs = []
    off = offset_of(idx, hold)
    for k in range(hold):
        g = gap[off == k]
        b_k = stud_mean(g, block, n_boot, seed)
        if b_k is None:
            continue
        lo_k, hi_k = two_sided(b_k)
        offs.append({"offset": k, "n": int(g.size), "mean": b_k["est"], "ci": [lo_k, hi_k],
                     "pass": bool(lo_k is not None and lo_k > 0)})
    if constituents:
        crit = [("POOLED lower 95% CI bound of mean(COR1M - realised constituent correlation) > 0", ci[0] > 0, ci[1] < 0)]
    else:
        crit = [(f"proxy ({len(names)} sector SPDRs) POOLED lower 95% CI bound > 0 (a sector proxy bounds the claim from one side "
                 "only: sector correlations exceed constituent ones, so a proxy shortfall is not a failure)",
                 True if ci[0] > 0 else None, False),
                ("realised average correlation of the index constituents (COR1M's top-50 S&P 500 names, cap-weighted): "
                 "constituent closes and weights are not archived", None, False)]
    crit.append(("vega-neutral short-index / long-constituent straddle book has positive mean P&L: needs index and "
                 "single-stock chain history", None, False))
    verdict, why = _decide(crit, n, min_n, "monthly windows (distinct 21-session holds)")
    n_off = len(offs)
    reason = (f"COR1M averages {cor1m[idx].mean():.1f} vs realised equal-weight average pairwise correlation of "
              f"{'the constituents' if constituents else 'the ' + str(len(names)) + ' sector SPDRs (' + '/'.join(names) + ')'} "
              f"{rho.mean()*100:.1f}. POOLED over all {hold} grid offsets ({idx.size} daily starts {days[idx[0]]}..{days[idx[-1]]} = "
              f"{n} distinct {hold}-session holds; studentized circular block bootstrap, block {pb} sessions): mean gap "
              f"{bt['est']*100:+.1f} pts ({_ci_s(tuple(x*100 for x in ci), 1)}), halves {halves[0]*100:+.1f}/{halves[1]*100:+.1f}. Per "
              f"grid offset ({n_off} non-overlapping grids, n {_rng([o['n'] for o in offs], 0).replace('+', '')} windows, block {block}): "
              f"mean gap {_rng([o['mean'] for o in offs], 1, 100)} pts, lower bound {_rng([o['ci'][0] for o in offs], 1, 100)} pts, "
              f"{sum(o['pass'] for o in offs)}/{n_off} offsets with the lower bound > 0")
    if not constituents:
        reason += (". Proxy verdict: NOT an acceptable stand-in under the claim's wording ('the index constituents'): sector "
                   "baskets diversify away idiosyncratic risk, so their pairwise correlation is far above single-stock "
                   "correlation (the gap above is dominated by that bias, not by the correlation premium); XLC/XLRE and "
                   "cap weights are also missing, so the verdict is capped at inconclusive")
    return {"n": n, "min_n": min_n, "n_entries": int(idx.size), "block_days": pb, "mean_cor1m": float(cor1m[idx].mean() / 100),
            "mean_realised": float(rho.mean()), "mean_gap": bt["est"], "ci95": list(ci), "halves": halves,
            "grid_offsets": offs, "components": list(names), "proxy": not constituents,
            "first_window": days[idx[0]], "last_window": days[idx[-1]], "verdict": verdict, "reason": reason + " — " + why}


# ==================================================================================================== harnesses ==

def b6_surf_vrp_term_regime(archive):
    """T-159: within each VIX tercile, SPY 21-day VRP higher in contango (< 0.95) than backwardation (> 1.05)."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B, DTB3_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    vix, v3 = _index(archive, VIX_B), _index(archive, VIX3M_B)
    keep = [d for d in sd if d in vix and d in v3 and d >= "2007-12-04"]
    pos = {d: i for i, d in enumerate(sd)}
    adj = np.array([sa[pos[d]] for d in keep])
    rep = vrp_regime(keep, adj, [vix[d] for d in keep], [v3[d] for d in keep])
    if "reason_core" not in rep:
        return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])
    fr = frame_on(sd, sc, sa, keep, _series(archive, DTB3_B), {"vix": vix})
    ratio = np.array([vix[d] / v3[d] for d in keep])
    sec = {}
    for s in (1.0, 0.81):
        # rule 10(b): the strangle's 21-session grid has 21 offsets; pooled over every daily entry, per offset reported
        cy = short_strangle_cycles(fr, s, starts=np.arange(len(keep) - MONTH))
        st, pnl = cy["start"], cy["pnl"]
        rr = ratio[st]
        con, bwd = rr < 0.95, rr > 1.05
        off = offset_of(st, MONTH)
        diffs = [float(pnl[(off == k) & con].mean() - pnl[(off == k) & bwd].mean()) * 1e4
                 for k in range(MONTH) if ((off == k) & con).any() and ((off == k) & bwd).any()]
        sec[str(s)] = {"n_contango": int(con.sum()), "n_backwardation": int(bwd.sum()), "n_entries": int(st.size),
                       "mean_contango_bp": float(pnl[con].mean() * 1e4) if con.any() else None,
                       "mean_backwardation_bp": float(pnl[bwd].mean() * 1e4) if bwd.any() else None,
                       "offset_diff_bp": diffs}
    rep["strangle_secondary"] = sec
    s1, s8 = sec["1.0"], sec["0.81"]
    reason = (f"21d SPY VRP (VIX^2 - next-21d realised variance) by VIX/VIX3M regime within VIX terciles, {rep['n_days']} daily "
              f"entries {rep['first_day']}..{rep['last_entry']} (the archive's VIX3M starts 2009-09-18, so the procedure's "
              f"2007-12-04..2009-09-17, including 2008, is not in the sample; the 'with 2008' control cannot be run); backwardation "
              f"(> 1.05) on {rep['share_backwardation']*100:.1f}% of days, contango (< 0.95) on {rep['share_contango']*100:.1f}%. "
              f"{rep['reason_core']}. Excluding 2020: " + "/".join(_s(None if r.get('diff_var_ex_2020') is None else r['diff_var_ex_2020'] * 1e4, 1) for r in rep['terciles'])
              + f" %^2. Secondary ({MP} short 16-delta 30-DTE strangle, flat smile, no costs, P&L per spot; POOLED over every daily "
              f"entry = all {MONTH} offsets of the 21-session grid, rule 10): contango "
              f"{_s(s1['mean_contango_bp'], 1)} bp (n={s1['n_contango']} entries) vs backwardation {_s(s1['mean_backwardation_bp'], 1)} bp "
              f"(n={s1['n_backwardation']}) at IV = VIX, per-offset contango-minus-backwardation {_rng(s1['offset_diff_bp'], 1)} bp "
              f"({sum(x > 0 for x in s1['offset_diff_bp'])}/{len(s1['offset_diff_bp'])} offsets > 0); at 0.81 x VIX "
              f"{_s(s8['mean_contango_bp'], 1)} vs {_s(s8['mean_backwardation_bp'], 1)} bp (per offset {_rng(s8['offset_diff_bp'], 1)} bp) "
              f"(the short-premium level hinges on the IV scale; the traded version needs SPY chain history). Rule 10: the VRP itself "
              f"is a daily series (no grid phase)")
    rep.pop("reason_core")
    why = rep.pop("why")
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + why)


def _gspc_skew_vix(archive):
    """(days, close, skew, vix, fresh) on ^GSPC's own sessions, SKEW and VIX as of each session (``gspc_calendar``)."""
    gd, gc, _ = _daily(archive, GSPC_B)
    return gspc_calendar(gd, gc, _index(archive, SKEW_B), _index(archive, VIX_B))


def b6_surf_skew_tail_frequency(archive):
    """T-227: high-SKEW windows do not carry >= 1 pp more -2 VIX-sigma 21-day ^GSPC drops than low-SKEW windows."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B])
    if miss:
        return miss
    days, c, sk, vx, fresh = _gspc_skew_vix(archive)
    rep = skew_tail_frequency(days, c, sk, vx, fresh=fresh)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_skew_implied_tail_gap(archive):
    """T-228: SKEW-implied 2-sigma probability exceeds the realised 21-day frequency by more than 2 pp."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B])
    if miss:
        return miss
    days, c, sk, vx, fresh = _gspc_skew_vix(archive)
    alt = None
    if _has(archive, SPY_B):
        sd, sc, sa = _daily(archive, SPY_B)
        raw, adj = dict(zip(sd, sc)), dict(zip(sd, sa))
        alt = {"SPY raw-close splice": np.array([raw.get(d, np.nan) for d in days]),
               "SPY adjusted-close splice": np.array([adj.get(d, np.nan) for d in days])}
    rep = skew_implied_gap(days, c, sk, vx, fresh=fresh, alt_close=alt)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_skew_cheap_put_spread(archive):
    """T-229: MODEL-PRICED 25d/10d SPX put spread bought in cheap-SKEW months vs every month (payoff / debit)."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B, DTB3_B, SPY_B, KAPPA_CHAIN])
    if miss:
        return miss
    days, c, sk, vx, fresh = _gspc_skew_vix(archive)
    dtb3 = _series(archive, DTB3_B)
    rate = bill_rates(days, dtb3)
    sd, sc, sa = _daily(archive, SPY_B)
    qy_spy = trailing_yield(sd, sc, sa)                  # PRE_YIELD (assumed, ex ante) until a full year of SPY dividends
    qy = np.array([qy_spy[max(bisect_right(sd, d) - 1, 0)] for d in days])      # SPY's yield known at that close
    o0 = date.fromisoformat(sd[0]).toordinal()
    q_known = next((d for d in sd if date.fromisoformat(d).toordinal() - o0 >= 365), None)
    q_assumed = np.array([q_known is None or d < q_known for d in days])
    chain = _rows(archive, KAPPA_CHAIN, filtered=False)
    qd = _quote_day(chain[0].get("available_at", "") if chain else "", days)
    sk_all, vx_all = _index(archive, SKEW_B, filtered=False), _index(archive, VIX_B, filtered=False)
    cal = None
    if qd and qd in sk_all and qd in vx_all:
        cal = calibrate_skew_slope([r["value"] for r in chain], qd, float(bill_rates([qd], dtb3)[0]), vx_all[qd], sk_all[qd])
    if cal is None or not cal["kappa"] > 0:
        return _out({"calibration": cal}, 0, "inconclusive",
                    f"the 30-DTE SPX smile could not be calibrated from {KAPPA_CHAIN} (quote day {qd}): kappa needs the chain's put IVs "
                    "and the quote day's VIX and SKEW — the claim's model-priced debit is undefined without it")
    rep = put_spread_skew(days, c, sk, vx, rate, qy, cal["atm_ratio"], cal["kappa"], q_assumed=q_assumed, fresh=fresh)
    rep["calibration"] = cal
    rep["dividend_yield"] = {"source": "SPY trailing-12-month dividends / close, known at each close", "known_from": q_known,
                             "assumed_before": PRE_YIELD}
    flat = put_spread_skew(days, c, sk, vx, rate, qy, 1.0, cal["kappa"], mults=(1.0,), n_boot=1000, n_placebo=10)
    fd = (flat.get("by_kappa_mult") or {}).get("1.0", {})
    rep["atm_ratio_1_sensitivity"] = fd
    spot = float(c[days.index(qd)]) if qd in days else None
    reason = (f"calibration on {KAPPA_CHAIN} (captured {chain[0].get('available_at', '')[:16]} UTC, before the US open: quote day "
              f"{cal['quote_day']}; the parity forward {cal['forward']:.1f} vs that day's ^GSPC close {_f(spot, 1)} suggests "
              f"extended-hours quotes; {cal['root']} {cal['expiry']}, {cal['dte']} DTE): ATM IV at the forward "
              f"{cal['atm_iv']*100:.2f} vs VIX {cal['vix']:.2f} (ratio {cal['atm_ratio']:.3f}), put slope {cal['slope']:+.3f} per unit "
              f"ln(K/F) over {cal['n_points']} puts (10-30 delta, rmse {cal['fit_rmse']*100:.2f} vol pts) at SKEW {cal['skew']:.2f} -> "
              f"kappa {cal['kappa']:.5f}. Dividend yield q: SPY's trailing 12-month yield from {q_known} (when it first becomes "
              f"computable); entries before that use an ASSUMED constant q = {PRE_YIELD:.1%} stated ex ante (no point-in-time S&P 500 "
              f"yield is archived). " + rep["reason"].replace(" — ", f"; ATM-ratio sensitivity (IV = VIX, ratio 1.0): difference "
              f"{_s(fd.get('diff'), 3)} ({_ci_s(tuple(fd.get('ci') or (None, None)), 3)}) — ", 1))
    return _out(rep, rep.get("n", 0), rep["verdict"], reason)


def b6_surf_cross_index_vol_spread(archive):
    """T-237: after the 60-day VXN-VIX z-score passes +/-2, s[(VXN-VIX) - (RV_QQQ - RV_SPY)] over 21 days is positive."""
    miss = _missing(archive, [SPY_B, QQQ_B, VIX_B, VXN_B])
    if miss:
        return miss
    sd, _, sa = _daily(archive, SPY_B)
    qd_, _, qa = _daily(archive, QQQ_B)
    vix, vxn = _index(archive, VIX_B), _index(archive, VXN_B)
    spy, qqq = dict(zip(sd, sa)), dict(zip(qd_, qa))
    days = _align(spy, qqq, vix, vxn)
    rep = vol_spread_test(days, [vxn[d] for d in days], [vix[d] for d in days], [qqq[d] for d in days], [spy[d] for d in days])
    if _has(archive, RVX_B) and _has(archive, IWM_B):
        idd, _, ia = _daily(archive, IWM_B)
        rvx, iwm = _index(archive, RVX_B), dict(zip(idd, ia))
        d2 = _align(spy, iwm, vix, rvx)
        rr = vol_spread_test(d2, [rvx[d] for d in d2], [vix[d] for d in d2], [iwm[d] for d in d2], [spy[d] for d in d2],
                             n_boot=1000, n_placebo=500, label="RVX-VIX / IWM-SPY")
        rep["rvx_replication"] = {k: rr.get(k) for k in ("n", "mean", "ci95", "win_rate", "halves", "sides")}
        rep["reason"] = rep["reason"].replace(" — ", f"; RVX-VIX / IWM replication: {rr.get('n')} events, mean {_s(rr.get('mean'), 2)} "
                                              f"(95% {_s(rr.get('ci95', [None])[0], 2)} to {_s(rr.get('ci95', [None, None])[1], 2)}), "
                                              f"win rate {_f(rr.get('win_rate'), 2)} — ", 1)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_vix_call_hedge(archive):
    """T-239: MODEL-PRICED 25-delta VIX call overlay at 1%/yr cuts SPY's maximum drawdown by more than 25%."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B, VVIX_B, DTB3_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    vix, v3, vv = _index(archive, VIX_B), _index(archive, VIX3M_B), _index(archive, VVIX_B)
    keep = [d for d in sd if d in vix and d in v3 and "2009-09-01" <= d and d >= min(vv)]
    vvf, _ = asof_series(keep, vv)                    # VVIX misses 2 SPY sessions after 2009: the last print, point in time
    keep = [d for d, x in zip(keep, vvf) if math.isfinite(x)]
    vv_on = {d: x for d, x in zip(keep, asof_series(keep, vv)[0])}
    fr = frame_on(sd, sc, sa, keep, _series(archive, DTB3_B), {"vix": vix, "vix3m": v3, "vvix": vv_on})
    rep = vix_hedge_test(fr, _smile(archive), cal_days=sd)      # SPY's sessions = the exchange calendar for holidays
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_vvix_vs_realised(archive):
    """T-240: VVIX exceeds the realised 21-day vol of spot-VIX log changes in > 70% of non-overlapping months."""
    miss = _missing(archive, [VVIX_B, VIX_B])
    if miss:
        return miss
    vix, vv = _index(archive, VIX_B), _index(archive, VVIX_B)
    spx = None
    first = min(vv) if vv else ""
    if _has(archive, GSPC_B):                    # the trading calendar: ^GSPC's sessions (VIX also prints on some holidays)
        gd, gc, _ = _daily(archive, GSPC_B)
        days = [d for d in gd if d >= first]
        g = dict(zip(gd, gc))
        spx = [g[d] for d in days]
    else:
        days = [d for d in sorted(vix) if d >= first]
    vx_on, _ = asof_series(days, vix)
    vv_on = np.array([vv.get(d, np.nan) for d in days])
    rep = vvix_win_rate(days, vv_on, vx_on, spx=spx)
    if _has(archive, VIX3M_B) and _has(archive, DTB3_B) and "reason" in rep:
        v3 = _index(archive, VIX3M_B)
        d3 = [d for d in days if d in v3 and d >= "2009-09-18"]
        if len(d3) > 100:
            vv3, _ = asof_series(d3, vv)
            sec = vix_call_ratio_secondary(d3, asof_series(d3, vix)[0], np.array([v3[d] for d in d3]), vv3,
                                           bill_rates(d3, _series(archive, DTB3_B)), cal_days=days)
            rep["call_ratio_secondary"] = sec
            rep["reason"] = rep["reason"].replace(" — ", f". Secondary ({MP} 1x2 VIX call ratio, long F_adj+4 / short 2x at +14, "
                                                  f"Black-76 at VVIX, {sec['n']} cycles rolled on the VIX monthly expiries from {d3[0]}): "
                                                  f"mean P&L {_s(sec['mean'], 2)} VIX pts ({_ci_s(sec['ci95'], 2)}) — ", 1)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_forward_variance_premium(archive):
    """T-249: the 1-3 month forward variance premium fraction exceeds the spot 30-day premium fraction."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B])
    if miss:
        return miss
    sd, _, sa = _daily(archive, SPY_B)
    vix, v3 = _index(archive, VIX_B), _index(archive, VIX3M_B)
    spy = dict(zip(sd, sa))
    days = _align(spy, vix, v3)
    rep = forward_variance_premium(days, [spy[d] for d in days], [vix[d] for d in days], [v3[d] for d in days])
    if "reason_core" not in rep:
        return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])
    checks = []
    if _has(archive, DTB3_B):
        dtb3 = _series(archive, DTB3_B)
        vx_all, v3_all = _index(archive, VIX_B, filtered=False), _index(archive, VIX3M_B, filtered=False)
        cal_days = sorted(set(sd) | set(vx_all))
        for nm in _names(archive, SPX_CHAIN_P):
            rows = _rows(archive, nm, filtered=False)
            if not rows:
                continue
            qd = _quote_day(rows[0].get("available_at", ""), cal_days)
            if not qd:
                continue
            try:
                chk = strip_check([r["value"] for r in rows], qd, float(bill_rates([qd], dtb3)[0]), vx_all.get(qd), v3_all.get(qd))
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                chk = None
            if chk:
                chk["bundle"] = nm
                checks.append(chk)
    rep["strip_checks"] = checks
    if checks:
        strip_s = "; ".join(f"{c['bundle']} (quotes {c['quote_day']}): 30d strip {c['strip_30']:.2f} vs VIX {_f(c['vix'], 2)} "
                            f"({_s(c['err_30'], 2)}; strikes {'/'.join(map(str, c['strikes_30']))}), 93d strip {c['strip_93']:.2f} vs "
                            f"VIX3M {_f(c['vix3m'], 2)} ({_s(c['err_93'], 2)}; strikes {'/'.join(map(str, c['strikes_93']))}), "
                            f"forward {_f(c['fwd_strip'], 2)} vs index {_f(c.get('fwd_index'), 2)}" for c in checks)
        strip_s += (" (both captures precede the US open, so their quotes may be extended-hours quotes rather than the quote "
                    "day's close; zero bids truncate the strip, which is part of the error measured)")
    else:
        strip_s = "no SPX chain capture could be stripped"
    reason = rep.pop("reason_core") + f". Strip discretisation (captured SPX chains, reported): {strip_s}"
    why = rep.pop("why")
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + why)


def b6_surf_weekend_variance(archive):
    """T-511 (data-only part): SPY Fri->Mon variance < 1.5 x the weekday single-night variance."""
    miss = _missing(archive, [SPY_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    rep = weekend_variance_ratio(sd, sa, raw_px=sc)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_implied_correlation(archive):
    """T-538: COR1M exceeds the realised average pairwise correlation of the index constituents (sector-SPDR proxy)."""
    legacy = [f"daily-history-{s}" for s in SECTORS_LEGACY]
    miss = _missing(archive, [COR1M_B] + legacy)
    if miss:
        return miss
    cor = _index(archive, COR1M_B)
    px = {}
    for s in SECTORS_LEGACY:
        d, _, a = _daily(archive, f"daily-history-{s}")
        px[s] = dict(zip(d, a))
    days = _align(cor, *px.values())
    comps = np.array([[px[s][d] for d in days] for s in SECTORS_LEGACY])
    rep = implied_vs_realised_corr(days, [cor[d] for d in days], comps, SECTORS_LEGACY)
    absent = [s for s in SECTORS_ALL if s not in SECTORS_LEGACY]
    rep["sectors_not_used"] = {s: ("archived but listed only from 2015/2018" if _has(archive, f"daily-history-{s}") else "not archived") for s in absent}
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


HARNESSES = {
    "b6_surf_vrp_term_regime": b6_surf_vrp_term_regime,
    "b6_surf_skew_tail_frequency": b6_surf_skew_tail_frequency,
    "b6_surf_skew_implied_tail_gap": b6_surf_skew_implied_tail_gap,
    "b6_surf_skew_cheap_put_spread": b6_surf_skew_cheap_put_spread,
    "b6_surf_cross_index_vol_spread": b6_surf_cross_index_vol_spread,
    "b6_surf_vix_call_hedge": b6_surf_vix_call_hedge,
    "b6_surf_vvix_vs_realised": b6_surf_vvix_vs_realised,
    "b6_surf_forward_variance_premium": b6_surf_forward_variance_premium,
    "b6_surf_weekend_variance": b6_surf_weekend_variance,
    "b6_surf_implied_correlation": b6_surf_implied_correlation,
}

THEORY_MAP = {
    "T-159": "b6_surf_vrp_term_regime",
    "T-227": "b6_surf_skew_tail_frequency",
    "T-228": "b6_surf_skew_implied_tail_gap",
    "T-229": "b6_surf_skew_cheap_put_spread",
    "T-237": "b6_surf_cross_index_vol_spread",
    "T-239": "b6_surf_vix_call_hedge",
    "T-240": "b6_surf_vvix_vs_realised",
    "T-249": "b6_surf_forward_variance_premium",
    "T-511": "b6_surf_weekend_variance",
    "T-538": "b6_surf_implied_correlation",
}
