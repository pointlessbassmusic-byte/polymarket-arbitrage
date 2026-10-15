"""
Batch 6c, group ``misc``: six underlying-library claims on archived daily histories (a technical-rule reality check, a
gold/silver ratio rule, two futures-basis measurements, a crypto sentiment event study and a long-history bond TSMOM).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-318  control: on SPY 1994-2026 the frozen 88-rule long/flat universe (24 close>SMA, 29 SMA crosses, 25 Donchian
           breakouts, 10 Alexander filters; one-bar delay, 2 bps per switch, idle cash at DTB3) does not beat buy-and-
           hold: Hansen's SPA p > 0.05 (consistent p, stationary bootstrap mean block 20, 5,000 draws, loss = negative
           daily excess return), CSCV PBO > 0.5 (16 partitions), and the walk-forward-selected rule's out-of-sample
           excess Sharpe minus buy-and-hold has a 95% interval that includes or lies below 0. QQQ, GLD, BTC-USD
           replications, the DSR of the in-sample best rule at 88 trials and PBO per decade are reported.
  * T-326  GLD/SLV 500-day-anchor z-score rule (|z| > 2 entry at the next close, exit at z = 0, 120-day time stop, stop
           at |z| = 3.5; 20 bps per leg per trade, 50 bps/yr borrow on the short leg), 2008-04..2026-09: 95% lower bound
           of the mean daily net return > 0 (stationary bootstrap, mean block 60), DSR > 0.95 at 5 trials, and the same
           sign on the roll-adjusted GC=F/SI=F route (NOT IMPLEMENTED: see the roll note below).
  * T-370  gold implied financing (GC=F vs GLD-implied spot, the rule's ounces-per-share formula, d to the CME last
           trading day of the front active month, roll windows dropped) minus DTB3, 2005-01..2026-09: HAC (lag 21) 95%
           CI of the mean inside [-50, +50] bp, with the pass's 6 trials counted (Bonferroni). The claim is gold-only:
           silver (SI=F vs SLV) is a separate trial, computed and reported; platinum, palladium and copper (separate
           trials) are not archived and reported as such; the GLD-NAV robustness item is report-only (not archived).
  * T-372  ES=F vs ^GSPC implied financing with a prior-year SPY dividend forecast, calendar days 5-60 after each
           quarterly roll, 2010-01..2026-09: one-sided 95% lower bound of mean(r_imp - DTB3) > 20 bp, with the pass's 5
           trials counted (Bonferroni), under both the Newey-West HAC (lag 21) and a quarter-clustered bootstrap.
  * T-416  first crossings of the alternative.me Fear & Greed index to <= 20 (F above 20 the day before, no crossing in
           the prior 10 days), BTC entered at the close of the day F becomes known: regression coefficient of the 30-day
           forward log return on the event indicator controlling for the trailing 30-day return >= 5 points with one-
           sided stationary-bootstrap p < 0.05; >= 30 non-overlapping events; DSR >= 0.95 over the declared 72 cells;
           positive in both 2018-21 and 2022-26.
  * T-484  12-1 long/short TSMOM minus the historical-mean strategy on the synthetic constant-maturity 10-year Treasury
           excess return from fred-DGS10, 1963..2026: mean d > 0 with the studentized CBB 95% CI (12-month blocks, 5,000
           draws) excluding 0, DSR > 0.95 over 8 trials, d > 0 in >= 2 of 3 sub-periods, synthetic-vs-IEF monthly
           correlation > 0.95.

Conventions
  * Data. Bundles are read through ``archive.load``; a row is used only when its ``available_at`` is not after the
    bundle's capture time. Yahoo bars are keyed by the UTC date of their timestamp (ETF and index bars 13:30/14:30 UTC,
    futures 04:00 UTC: both the trading date; crypto 00:00 UTC: the UTC calendar day). ``close`` is split-adjusted,
    ``adjclose`` total return. SPY cash dividends are recovered from the adjclose/close step (batch6b_bw.spy_dividends).
  * Rates (rule 7). FRED DTB3 is a 91-day discount yield, converted to a continuous rate -ln(1 - d x 91/360)/(91/365).
    Trading decisions accrue cash at the print dated strictly before each calendar day (batch6b_bw.Bills). The two
    basis claims (T-370, T-372) are contemporaneous measurements, not decisions: each day's implied rate is compared with
    that day's DTB3 print (the latest earlier print when a day has none), and the implied rate is put on the same
    continuous basis, ln(F/S) x 365/d (the rule's simple (F/S - 1) x 365/d is reported). Sharpe ratios are on excess
    returns (252 a year; 365 for crypto).
  * Point in time (rules 4, 12). T-318 signals at close t are traded at close t+1 (one-bar delay; a daily bar is
    available the next day); a walk-forward re-selection that switches at close e ranks the rules on returns through
    close e - 1. T-326 decides at close t and fills at close t+1 on trailing statistics only. T-416: F for
    day t is available at 00:00 UTC on t+1 and BTC is bought at the close of t+1; the trailing-return control ends at
    that close. T-372's dividend forecast uses only SPY dividends that went ex at least a year before the window.
    T-484's 12-1 signal ends a month before the decision; DGS10 rows are used only when available by the next day.
  * Calendars (rule 10). T-318's walk-forward re-selects every 5 years on the claim's own calendar: calendar years
    from the claim's 1994 start (in-sample 1994-1998, trade 1999-2003, ...); the 60 monthly re-selection phases are
    pooled (equal-weight portfolio of the phase strategies) and their per-phase range reported, and the walk-forward
    criterion must hold for both the calendar and the pooled readings. T-326 is a daily state machine (no grid), T-370
    and T-372 daily measurements, T-416 an event study whose regression uses every day (the all-start estimator, so
    its stationary bootstrap is run with the trial's 30-day blocks AND rule-10's 60-day blocks, both must pass), T-484
    month-end decisions named by the claim.
  * Intervals (rule 6). T-318: SPA with Hansen's (2005) stationary-bootstrap kernel variance and consistent recentring
    (lower/upper p reported); walk-forward Sharpe difference by the paired studentized circular block bootstrap
    (batch6b_bw.sharpe_diff_test, 20-day blocks). T-326: stationary-bootstrap percentile interval of the mean (mean
    block 60; the null is two-sided, so the lower end of the two-sided 95% interval). T-370: Newey-West HAC (Bartlett,
    lag 21) two-sided, at 1 - 0.05/6. T-372: the null is one-sided (mean <= 20 bp), so one-sided lower bounds at
    1 - 0.05/5: HAC (lag 21) and a quarter-clustered percentile bootstrap. T-416: stationary bootstrap of the daily
    regression rows, percentile one-sided bounds (quantiles of b*) and p = P(b* <= 0). T-484: studentized CBB (12-month
    blocks). Every decisive bootstrap end is averaged over 5 seeds with its Monte Carlo
    s.e. (25 seeds when 5 cannot resolve it).
  * Costs (rule 9) as each claim states: T-318 2 bps SPY, 5 bps QQQ/GLD, 25 + 10 bps BTC per switch; T-326 20 bps per
    leg per trade + 50 bps/yr borrow on the short leg; T-484 2 bps per side; T-416 is a forecast claim (no costs; the
    rule Sharpe is reported at 0.5% and 1.2% round trip). T-370/T-372 are rate measurements (costs reported only).
  * Data limits (rule 9). T-326's GC/SI route needs CME active-month roll adjustment of Yahoo's continuous GC=F/SI=F;
    Yahoo serves no expired contracts, so the roll dates and contract identity cannot be reconstructed: the criterion is
    None and an approximate route (scheduled roll windows replaced by GLD/SLV returns) is reported only. T-370's
    platinum (PL=F/PPLT), palladium (PA=F/PALL) and copper (HG=F/CPER) trials and its GLD-NAV robustness check are not
    archived; they are separate trials / a report-only check, so they are reported, not None criteria.
  * Robustness items and trial counts (one convention for the module). A trial's 'Robustness: X instead of Y' (T-370's
    GLD NAV instead of the GLD close, T-372's realized instead of forecast dividends) is a report-only check, never a
    criterion: the claim's own rule decides (for T-370 the rule's S = GLD close / formula ounces, sponsor ounces only
    'where available'; the controls call the NAV check a noise check). Rule 11 applies where a trial names alternative
    procedures for the pass statistic itself (T-318's calendar and pooled walk-forward readings, T-416's 30-day blocks
    and rule 10's 60-day blocks). A pass judged by an interval that also says 'N trials counted' (T-370: 6, T-372: 5) is
    judged at the Bonferroni level 1 - 0.05/N (the house reading of a declared trial count, as batch6_surf); the
    unadjusted 95% bounds are reported. Where the trial count feeds a DSR (T-326, T-416, T-484), the DSR takes it.
  * Below trial.min_n (rule 5) the verdict is never supported and a failing criterion counts only when it fails
    decisively. T-416's trial also pre-registers that a non-rejection is "recorded as underpowered, not as a
    refutation": its coefficient and DSR criteria fail only decisively (the claimed 5-point effect itself rejected, or
    the PSR against zero <= 0.05); otherwise they are undecided.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import functools
import itertools
import math
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import (Bills, _clean, _decide, _mean_stat, _stationary_idx, _stud, all_constructions,
                                           dtb3_cont, mc_reps, resolve, sharpe_diff_test, spy_dividends)
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

N_BOOT = 2000                  # bootstrap draws per seed for interval ends (x REPS seeds)
SPA_BOOT = 5000                # the T-318 trial's 5,000 SPA draws
T416_BOOT = 5000               # the T-416 trial's 5,000 draws
T484_BOOT = 5000               # the T-484 trial's 5,000 draws
REPS = 5                       # bootstrap seeds behind every decisive interval end
REPS_MAX = 25                  # seeds when 5 cannot resolve a bound against its threshold
SEED = 0
DSR_PASS = 0.95
Z95 = NormalDist().inv_cdf(0.975)
Z95_1 = NormalDist().inv_cdf(0.95)

DTB3_B = "fred-DTB3"
DGS10_B = "fred-DGS10"
DGS2_B = "fred-DGS2"
FNG_B = "crypto-fear-greed-history"


def dh(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


# ================================================================================================= data access ==

_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _daily(archive, name: str) -> dict:
    """{'days', 'close', 'adj'} of a Yahoo daily bundle; a bar without adjclose carries the previous adjclose/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            try:
                c = float(v.get("close"))
            except (TypeError, ValueError):
                continue
            if not (c > 0 and math.isfinite(c)):
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            try:
                a = float(a) if a is not None and float(a) > 0 else float("nan")
            except (TypeError, ValueError):
                a = float("nan")
            by[d] = (c, a)
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "close": close, "adj": adj}
    return _cached(archive, ("daily", name), load)


def _fred_avail(archive, name: str) -> dict:
    """{day: (value, available_at)} of a FRED bundle; non-numeric prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            try:
                x = float(v.get("value"))
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = (x, r.get("available_at") or (v["day"] + "T20:00:00+00:00"))
        return out
    return _cached(archive, ("fred", name), load)


def _fred(archive, name: str) -> dict:
    return {d: v for d, (v, _) in _fred_avail(archive, name).items()}


def _fng(archive) -> dict:
    """{day: (F, available_at)} of the alternative.me Fear & Greed history."""
    def load():
        out = {}
        for r in _rows(archive, FNG_B):
            v = r.get("value") or {}
            try:
                x = float(v.get("value"))
            except (TypeError, ValueError):
                continue
            d = (r.get("observed_at") or "")[:10] or v.get("day")
            if d and math.isfinite(x):
                out[d] = (x, r.get("available_at") or (date.fromisoformat(d) + timedelta(days=1)).isoformat() + "T00:00:00+00:00")
        return out
    return _cached(archive, ("fng",), load)


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_fred(archive, DTB3_B)))


class SameDayRate:
    """DTB3 as a continuous rate for a contemporaneous measurement: the print dated on the day, else the latest earlier."""

    def __init__(self, dtb3: dict):
        self.k = sorted(dtb3)
        if not self.k:
            raise ValueError("no DTB3 prints")
        self.r = np.array([dtb3_cont(float(dtb3[d])) for d in self.k], float)

    def rate(self, day: str) -> float:
        j = bisect.bisect_right(self.k, day) - 1
        return float(self.r[max(j, 0)])

    def rates(self, days: Sequence[str]) -> np.ndarray:
        j = np.searchsorted(np.array(self.k), np.array(list(days)), side="right") - 1
        return self.r[np.maximum(j, 0)]


# ============================================================================================ formatting, misc ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bp"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _ord(d) -> int:
    return (date.fromisoformat(d) if isinstance(d, str) else d).toordinal()


def _month_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _mc(fn: Callable, check: Callable, seed: int = SEED, keys: Sequence[str] = ("ci", "ci_pct")) -> dict:
    """``fn(seed=...)`` over REPS seeds (interval ends averaged, with Monte Carlo s.e.); REPS_MAX seeds when ``check`` (the
    resolved criterion, None = unresolved) cannot decide on REPS."""
    t = mc_reps(fn, REPS, seed, keys)
    if check(t) is None and REPS_MAX > REPS:
        t = mc_reps(fn, REPS_MAX, seed, keys)
    return t


def hac_mean(x, lag: int = 21) -> dict:
    """Mean with a Newey-West (Bartlett, ``lag`` lags, weights 1 - l/(lag + 1)) standard error."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else None, "se": None, "n": int(n)}
    m = float(x.mean())
    z = x - m
    lrv = float(z @ z) / n
    for l in range(1, min(lag, n - 1) + 1):
        lrv += 2.0 * (1.0 - l / (lag + 1.0)) * float(z[l:] @ z[:-l]) / n
    return {"mean": m, "se": math.sqrt(max(lrv, 0.0) / n), "n": int(n)}


def dsr_family(x, family_sharpes: Sequence, n_trials: int) -> dict:
    """DSR of ``x`` against the best of ``n_trials`` trials; trial-Sharpe variance from the computed family (per-period
    Sharpes), floored at 1/(T-1); the PSR against a zero Sharpe is the decisive-failure check (<= 0.05)."""
    x = np.asarray(x, float)
    fs = np.array([s for s in family_sharpes if s is not None and math.isfinite(s)], float)
    v = float(fs.var(ddof=1)) if fs.size > 1 else 0.0
    v = max(v, 1.0 / max(1, x.size - 1))
    ok = x.size > 3 and x.std() > 0
    return {"dsr": float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=v)) if ok else None,
            "psr0": float(deflated_sharpe_ratio(x, n_trials=1)) if ok else None, "var_trials_sr": v, "n_trials": int(n_trials),
            "n_family_computed": int(fs.size), "sharpe_per_period": float(sharpe_ratio(x)) if ok else None}


def dsr_row(d: dict, label: str, decisive_only: bool = False) -> tuple:
    """(name, ok, decisive) for 'DSR > 0.95'. decisive_only: a non-decisive shortfall is undecided (None)."""
    if d.get("dsr") is None:
        return f"{label} (n/a)", None, False
    dec = d["psr0"] is not None and d["psr0"] <= 1.0 - DSR_PASS
    ok = d["dsr"] > DSR_PASS
    name = f"{label} ({d['dsr']:.3f} at {d['n_trials']} trials, var(trial SR) {d['var_trials_sr']:.2e}, PSR vs 0 {_f(d['psr0'])})"
    if decisive_only and not ok and not dec:
        return name + " [shortfall not decisive: recorded as underpowered]", None, False
    return name, ok, dec


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _sr_ann(x, ppy: float) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, ppy)) if x.size > 2 and x.std() > 0 else None


# ========================================================================================= stationary bootstrap ==

def sb_means(x, mean_block: float, n_boot: int, seed: int = SEED) -> np.ndarray:
    """Means of ``n_boot`` Politis-Romano stationary-bootstrap resamples of the rows of ``x`` ((n,) or (n, K)): circular
    blocks with uniform starts and geometric lengths of mean ``mean_block``, truncated to n rows. Returns (n_boot,) or
    (n_boot, K). Block sums come from prefix sums of the doubled series, so a draw costs O(n / mean_block)."""
    x = np.asarray(x, float)
    one = x.ndim == 1
    X = x[:, None] if one else x
    n, K = X.shape
    q = 1.0 / max(float(mean_block), 1.0)
    P = np.zeros((2 * n + 1, K))
    P[1:] = np.cumsum(np.vstack([X, X]), axis=0)
    rng = np.random.default_rng(seed)
    out = np.empty((n_boot, K))
    nb0 = int(n * q * 1.5) + 16
    for b in range(n_boot):
        L = rng.geometric(q, size=nb0)
        cs = np.cumsum(L)
        while cs[-1] < n:
            L = np.concatenate([L, rng.geometric(q, size=nb0)])
            cs = np.cumsum(L)
        m = int(np.searchsorted(cs, n)) + 1
        L = L[:m].copy()
        L[-1] -= int(cs[m - 1]) - n
        L = np.minimum(L, n)
        s = rng.integers(0, n, size=m)
        out[b] = (P[s + L] - P[s]).sum(axis=0) / n
    return out[:, 0] if one else out


def sb_mean_ci(x, mean_block: float, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> dict:
    """Stationary-bootstrap percentile interval of the mean (two-sided ``level``)."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    x = np.asarray(x, float)
    if x.size < 8:
        return {"est": float(x.mean()) if x.size else None, "ci": [None, None]}
    m = sb_means(x, mean_block, nb, seed)
    a = (1 - level) / 2
    b = 1 - level
    return {"est": float(x.mean()), "ci": [float(np.quantile(m, a)), float(np.quantile(m, 1 - a))],
            "ci1": [float(np.quantile(m, b)), float(np.quantile(m, 1 - b))]}       # one-sided ``level`` bounds


# ============================================================================== T-318 TA rule reality check ==

T318_MIN_N = 8000
T318_COST = {"SPY": 2e-4, "QQQ": 5e-4, "GLD": 5e-4, "BTC-USD": 35e-4}
T318_REPL = ("QQQ", "GLD", "BTC-USD")
T318_WARMUP = 250              # the longest SMA / Donchian lookback
T318_SPA_BLOCK = 20
T318_PBO_S = 16
T318_WF_YEARS = 5
T318_WF_BLOCK = 20
T318_N_TRIALS = 88
T318_DECADES = (("1994", "2003"), ("2004", "2013"), ("2014", "2026"))


def rule_universe() -> list:
    """The frozen 88-rule universe: 24 close > SMA(L), 29 SMA(f) > SMA(s), 25 Donchian(N) with exit at the N/2 low, 10
    Alexander x% filters."""
    rules = [("sma", L) for L in range(20, 251, 10)]
    rules += [("cross", f, s) for f in (5, 10, 20, 30, 40, 50) for s in (50, 100, 150, 200, 250) if f < s]
    rules += [("donchian", N) for N in range(10, 251, 10)]
    rules += [("filter", x) for x in range(1, 11)]
    return rules


def rule_name(r: tuple) -> str:
    return {"sma": lambda: f"close>SMA{r[1]}", "cross": lambda: f"SMA{r[1]}>SMA{r[2]}",
            "donchian": lambda: f"Donchian{r[1]}/{r[1] // 2}", "filter": lambda: f"filter{r[1]}%"}[r[0]]()


def _sma(c: np.ndarray, L: int) -> np.ndarray:
    out = np.full(c.size, np.nan)
    if c.size >= L:
        cs = np.concatenate([[0.0], np.cumsum(c)])
        out[L - 1:] = (cs[L:] - cs[:-L]) / L
    return out


def _donchian(c: np.ndarray, N: int) -> np.ndarray:
    """Long when the close breaks above the highest of the prior N closes; flat when it breaks below the lowest of the
    prior N/2 closes."""
    from numpy.lib.stride_tricks import sliding_window_view
    n, h = c.size, N // 2
    out = np.zeros(n)
    if n <= N:
        return out
    mx = sliding_window_view(c, N).max(axis=1)
    mn = sliding_window_view(c, h).min(axis=1)
    state = 0.0
    for t in range(N, n):
        if state == 0.0 and c[t] > mx[t - N]:
            state = 1.0
        elif state == 1.0 and c[t] < mn[t - h]:
            state = 0.0
        out[t] = state
    return out


def _filter_rule(c: np.ndarray, x_pct: float) -> np.ndarray:
    """Alexander filter: long after a rise of x% from the latest trough, flat after a fall of x% from the latest peak."""
    x = x_pct / 100.0
    out = np.zeros(c.size)
    state, trough, peak = 0, float(c[0]), float(c[0])
    for t in range(c.size):
        p = float(c[t])
        if state == 0:
            trough = min(trough, p)
            if p >= trough * (1 + x):
                state, peak = 1, p
        else:
            peak = max(peak, p)
            if p <= peak * (1 - x):
                state, trough = 0, p
        out[t] = state
    return out


def rule_signals(c, rules: Optional[Sequence[tuple]] = None) -> np.ndarray:
    """(n, K) long (1) / flat (0) signal of each rule known at each close; 0 where the rule is not yet defined."""
    c = np.asarray(c, float)
    rules = rule_universe() if rules is None else list(rules)
    sm = {}

    def sma(L):
        if L not in sm:
            sm[L] = _sma(c, L)
        return sm[L]

    cols = []
    for r in rules:
        if r[0] == "sma":
            s = sma(r[1])
            cols.append(np.where(np.isfinite(s), (c > s).astype(float), 0.0))
        elif r[0] == "cross":
            a, b = sma(r[1]), sma(r[2])
            ok = np.isfinite(a) & np.isfinite(b)
            cols.append(np.where(ok, (np.where(ok, a, 0) > np.where(ok, b, 0)).astype(float), 0.0))
        elif r[0] == "donchian":
            cols.append(_donchian(c, r[1]))
        else:
            cols.append(_filter_rule(c, r[1]))
    return np.column_stack(cols)


def rule_returns(c, rf, cost: float, rules: Optional[Sequence[tuple]] = None) -> dict:
    """Daily net excess returns of every rule: the signal at close t is traded at close t+1 (one-bar delay), so the
    position earning the return over (t+1, t+2] is the close-t signal; idle cash earns ``rf``; ``cost`` per switch."""
    c = np.asarray(c, float)
    sig = rule_signals(c, rules)
    r = np.r_[0.0, c[1:] / c[:-1] - 1.0]
    xr = r - np.asarray(rf, float)
    pos = np.zeros_like(sig)
    pos[2:] = sig[:-2]
    turn = np.abs(np.diff(np.vstack([np.zeros((1, sig.shape[1])), pos]), axis=0))
    return {"ex": pos * xr[:, None] - cost * turn, "pos": pos, "xr": xr}


def spa_kernel_omega(d: np.ndarray, q: float) -> np.ndarray:
    """Hansen (2005) long-run s.d. of sqrt(n) x mean for each column: gamma_0 + 2 sum_i kappa(n, i) gamma_i with the
    stationary-bootstrap kernel kappa(n, i) = (n - i)/n (1 - q)^i + i/n (1 - q)^(n - i) (autocovariances by FFT)."""
    n, K = d.shape
    z = d - d.mean(axis=0)
    nfft = 1 << (2 * n - 1).bit_length()
    F = np.fft.rfft(z, nfft, axis=0)
    ac = np.fft.irfft(F * np.conj(F), nfft, axis=0)[:n] / n
    i = np.arange(1, n, dtype=float)
    kap = (n - i) / n * (1 - q) ** i + i / n * (1 - q) ** (n - i)
    w2 = ac[0] + 2.0 * (kap[:, None] * ac[1:]).sum(axis=0)
    return np.sqrt(np.maximum(w2, 1e-300))


def hansen_spa(d, mean_block: float = T318_SPA_BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Hansen's (2005) Superior Predictive Ability test. ``d``: (n, K) performance differentials of K models over the
    benchmark (benchmark loss minus model loss; here a rule's excess return minus buy-and-hold's). H0: max_k E[d_k] <= 0.
    Studentized statistic max(0, max_k sqrt(n) dbar_k / omega_k); stationary bootstrap (mean block ``mean_block``) with
    the lower (SPA_l), consistent (SPA_c, Hansen's recommended p) and upper (SPA_u = White's Reality Check) recentrings."""
    nb = SPA_BOOT if n_boot is None else int(n_boot)
    d = np.asarray(d, float)
    if d.ndim == 1:
        d = d[:, None]
    n, K = d.shape
    q = 1.0 / mean_block
    dbar = d.mean(axis=0)
    om = spa_kernel_omega(d, q)
    tk = math.sqrt(n) * dbar / om
    t_obs = max(0.0, float(tk.max()))
    M = sb_means(d, mean_block, nb, seed)
    A = np.sqrt(om ** 2 / n * 2.0 * math.log(math.log(n)))
    g = {"l": np.maximum(dbar, 0.0), "c": dbar * (dbar >= -A), "u": dbar}
    p = {}
    for key, gv in g.items():
        T = np.maximum(0.0, (math.sqrt(n) * (M - gv) / om).max(axis=1))
        p[key] = float(np.mean(T > t_obs))
    best = int(np.argmax(tk))
    return {"n": int(n), "K": int(K), "t_spa": t_obs, "p_l": p["l"], "p_c": p["c"], "p_u": p["u"], "n_boot": nb,
            "best": best, "best_dbar": float(dbar[best]), "n_positive": int((dbar > 0).sum()), "mean_block": mean_block}


def spa_resolved(d, mean_block: float = T318_SPA_BLOCK, n_boot: Optional[int] = None, seed: int = SEED, thr: float = 0.05) -> dict:
    """``hansen_spa`` with the consistent p resolved against ``thr`` beyond 2 binomial Monte Carlo s.e.; when it cannot be,
    four more seeds are pooled (5 x the draws)."""
    nb = SPA_BOOT if n_boot is None else int(n_boot)
    t = hansen_spa(d, mean_block, nb, seed)
    se = math.sqrt(max(t["p_c"] * (1 - t["p_c"]), 1e-12) / nb)
    if abs(t["p_c"] - thr) < 2 * se:
        runs = [t] + [hansen_spa(d, mean_block, nb, seed + k) for k in range(1, 5)]
        for key in ("p_l", "p_c", "p_u"):
            t[key] = float(np.mean([r[key] for r in runs]))
        t["n_boot"] = nb * len(runs)
        se = math.sqrt(max(t["p_c"] * (1 - t["p_c"]), 1e-12) / t["n_boot"])
    t["p_c_mc_se"] = se
    return t


def pbo_fast(R, n_partitions: int = 16) -> dict:
    """CSCV probability of backtest overfitting, identical to ``overfit.pbo_cscv`` (same partitions, ddof-1 Sharpe, rank
    and logit) but computed from per-block sums, so 16 partitions (12,870 splits) of 88 rules run in a second."""
    R = np.asarray(R, float)
    T, N = R.shape
    S = n_partitions if n_partitions % 2 == 0 else n_partitions + 1
    T = (T // S) * S
    R = R[:T]
    blocks = np.array_split(np.arange(T), S)
    s1 = np.array([R[b].sum(axis=0) for b in blocks])
    s2 = np.array([(R[b] ** 2).sum(axis=0) for b in blocks])
    cnt = np.array([b.size for b in blocks], float)
    combos = np.array(list(itertools.combinations(range(S), S // 2)))
    Mtr = np.zeros((combos.shape[0], S))
    Mtr[np.arange(combos.shape[0])[:, None], combos] = 1.0
    Mte = 1.0 - Mtr

    def sr(M):
        k = M @ cnt
        a, b = M @ s1, M @ s2
        mu = a / k[:, None]
        var = (b - k[:, None] * mu ** 2) / (k[:, None] - 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = np.where(var > 0, mu / np.sqrt(np.maximum(var, 1e-300)), 0.0)
        return out

    sr_is, sr_oos = sr(Mtr), sr(Mte)
    best = np.argmax(sr_is, axis=1)
    sb = sr_oos[np.arange(sr_oos.shape[0]), best]
    rank = ((sr_oos < sb[:, None]).sum(axis=1) + 0.5) / N
    rank = np.clip(rank, 1e-6, 1 - 1e-6)
    logits = np.log(rank / (1 - rank))
    return {"pbo": float(np.mean(logits <= 0)), "n_combinations": int(logits.size), "n_variants": int(N), "n_periods": int(T),
            "median_logit": float(np.median(logits))}


def _wf_boundaries(months: Sequence[str], phase: int, years: int, start_year: int) -> list:
    """Indices of the last day of each re-selection month: month (start_year + years - 1)-12 + phase, then every
    ``years`` years, while a later day exists."""
    last = {}
    for i, m in enumerate(months):
        last[m] = i
    out, b = [], _month_add(f"{start_year + years - 1:04d}-12", phase)
    while True:
        cand = [m for m in last if m <= b]
        if not cand or b >= months[-1]:
            break
        out.append((b, last[max(cand)]))
        b = _month_add(b, 12 * years)
    return out


def walk_forward(ex: np.ndarray, xr: np.ndarray, days: Sequence[str], cost: float, pos: Optional[np.ndarray] = None,
                 phase: int = 0, years: int = T318_WF_YEARS, start_year: Optional[int] = None) -> dict:
    """Walk-forward selection: at each re-selection month-end close e pick the rule with the best ddof-1 Sharpe of its net
    excess returns over the prior ``years`` x 12 months and trade it until the next re-selection. Point in time (the
    module's one-bar delay: a daily bar is available the next session): the switch is made at close e, so the selection
    window ends at the bar before it (ex[i0:e], returns through close e - 1) and the new rule earns the return (e, e+1]
    onwards. With ``pos`` the strategy's own position path is re-costed (a switch at a boundary pays ``cost``); without it
    the selected rule's net excess return is used. Returns the full-length series (NaN before the first out-of-sample
    day) and the selections."""
    n, K = ex.shape
    months = [d[:7] for d in days]
    bnd = _wf_boundaries(months, phase, years, int(days[0][:4]) if start_year is None else start_year)
    wf = np.full(n, np.nan)
    wpos = np.full(n, np.nan)
    sel = []
    for j, (bm, e) in enumerate(bnd):
        i0 = bisect.bisect_right(months, _month_add(bm, -12 * years))
        win = ex[i0:e]                                       # bars through close e - 1: known when switching at close e
        if win.shape[0] < 20:
            continue
        mu, sd = win.mean(axis=0), win.std(axis=0, ddof=1)
        srs = np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), -np.inf)
        k = int(np.argmax(srs))
        e2 = bnd[j + 1][1] if j + 1 < len(bnd) else n - 1
        seg = slice(e + 1, e2 + 1)
        if pos is None:
            wf[seg] = ex[seg, k]
        else:
            wpos[seg] = pos[seg, k]
        sel.append({"month": bm, "rule": k, "is_sharpe": float(srs[k]), "is_days": int(win.shape[0])})
    if pos is not None:
        ok = np.isfinite(wpos)
        if ok.any():
            f = int(np.argmax(ok))
            p = wpos[f:]
            turn = np.abs(np.diff(np.r_[0.0, p]))
            wf[f:] = p * xr[f:] - cost * turn
    return {"wf": wf, "selections": sel, "first": int(np.argmax(np.isfinite(wf))) if np.isfinite(wf).any() else None}


def _le_crit(t: dict, thr: float, label: str) -> tuple:
    """'the 95% interval includes or lies below thr': passes when the lower end is not above thr beyond Monte Carlo
    error; fails (decisively: the whole interval is above thr) when it is."""
    lo = (t.get("ci") or [None, None])[0]
    se = (t.get("ci_mc_se") or [0.0, 0.0])[0]
    above, note = resolve(lo, se, thr, "gt")
    ok = None if above is None else (not above)
    return f"{label} (lower {_s(lo)}){note}", ok, above is True


def reality_check(ex: np.ndarray, xr: np.ndarray, days: Sequence[str], cost: float, pos: Optional[np.ndarray] = None,
                  ppy: float = 252.0, min_n: int = T318_MIN_N, names: Optional[Sequence[str]] = None, n_phases: int = 60,
                  spa_boot: Optional[int] = None, n_boot: Optional[int] = None, seed: int = SEED, decades=T318_DECADES,
                  wf_ci: bool = True) -> dict:
    """T-318 core on an evaluation window: ``ex`` (n, K) daily net excess returns of the K rules, ``xr`` (n,) buy-and-
    hold's daily excess return, ``days`` the return days. Criteria (control confirmed): SPA p_c > 0.05, PBO > 0.5, and the
    walk-forward out-of-sample Sharpe difference's 95% interval includes or lies below 0 under both the calendar (phase
    0) and the pooled all-phase readings."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    ex, xr = np.asarray(ex, float), np.asarray(xr, float)
    n, K = ex.shape
    names = list(names) if names is not None else [f"rule{k}" for k in range(K)]
    spa = spa_resolved(ex - xr[:, None], T318_SPA_BLOCK, spa_boot, seed)
    pbo = pbo_fast(ex, T318_PBO_S)
    srs = np.array([_sr_pp(ex[:, k]) or 0.0 for k in range(K)])
    best = int(np.argmax(srs))
    dsr_best = float(deflated_sharpe_ratio(ex[:, best], n_trials=K, trial_sharpes=srs)) if K > 1 else None
    pbo_dec = {}
    for a, b in decades or ():
        m = np.array([a <= d[:4] <= b for d in days])
        if m.sum() >= 4 * T318_PBO_S:
            pbo_dec[f"{a}-{b}"] = pbo_fast(ex[m], T318_PBO_S)["pbo"]
    # walk-forward: phase 0 = the claim's calendar; phases 0..n_phases-1 pooled
    phases = [walk_forward(ex, xr, days, cost, pos, phase=p) for p in range(max(1, n_phases))]
    W0 = phases[0]
    wf = {"calendar": None, "pooled": None}
    per_phase = []
    if W0["first"] is not None:
        f0 = W0["first"]
        a0 = W0["wf"][f0:]
        b0 = xr[f0:]
        stack = np.vstack([P["wf"] for P in phases])
        pooled = np.nanmean(np.where(np.isfinite(stack), stack, np.nan)[:, f0:], axis=0)
        for P in phases:
            if P["first"] is not None and n - P["first"] > 60:
                per_phase.append((_sr_ann(P["wf"][P["first"]:], ppy) or 0.0) - (_sr_ann(xr[P["first"]:], ppy) or 0.0))
        for key, a in (("calendar", a0), ("pooled", pooled)):
            if wf_ci and a.size >= 8:
                t = _mc(lambda seed, a=a: sharpe_diff_test(a, b0, ppy, T318_WF_BLOCK, nb, seed),
                        lambda t: _le_crit(t, 0.0, "")[1], seed)
            else:
                t = {"diff": (_sr_ann(a, ppy) or 0.0) - (_sr_ann(b0, ppy) or 0.0), "ci": [None, None]}
            wf[key] = t
        wf_days = (days[f0], days[-1], int(a0.size))
    else:
        wf_days = None
    crit = [(f"Hansen SPA (consistent) p > 0.05 vs buy-and-hold over the {K}-rule universe (p_c {_f(spa['p_c'], 4)}, "
             f"MC s.e. {_f(spa['p_c_mc_se'], 4)}; p_l {_f(spa['p_l'], 4)}, p_u {_f(spa['p_u'], 4)})",
             resolve(spa["p_c"], spa["p_c_mc_se"], 0.05, "gt")[0], resolve(spa["p_c"], spa["p_c_mc_se"], 0.05, "lt")[0] is True),
            (f"CSCV PBO > 0.5 ({_f(pbo['pbo'])} over {pbo['n_combinations']} splits, {T318_PBO_S} partitions)",
             pbo["pbo"] > 0.5, False)]
    if wf["calendar"] is not None and wf_ci:
        rows = [_le_crit(wf["calendar"], 0.0, f"calendar 5-year re-selection ({days[0][:4]} + 5k)"),
                _le_crit(wf["pooled"], 0.0, f"pooled {len(phases)} monthly re-selection phases")]
        crit.append(all_constructions(rows, "walk-forward selected rule minus buy-and-hold out-of-sample excess Sharpe: 95% "
                                            "interval includes or lies below 0"))
    else:
        crit.append(("walk-forward out-of-sample Sharpe difference interval (not computable)", None, False))
    v, why = _decide(crit, n, min_n, "daily returns")
    surprise = bool(spa["p_c"] < 0.05 and pbo["pbo"] < 0.5)
    return {"n": int(n), "K": int(K), "spa": spa, "pbo": pbo, "pbo_by_decade": pbo_dec, "best_rule": names[best],
            "best_sharpe_ann": float(srs[best] * math.sqrt(ppy)), "dsr_best": dsr_best,
            "spa_best_rule": names[spa["best"]], "wf": wf, "wf_window": wf_days,
            "wf_selections": [{**s, "rule": names[s["rule"]]} for s in W0["selections"]],
            "wf_phase_range": [float(min(per_phase)), float(max(per_phase))] if per_phase else None,
            "wf_n_phases": len(per_phase), "surprise": surprise, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _t318_asset(archive, sym: str, bills: Bills, n_phases: int = 60, wf_ci: bool = True, spa_boot: Optional[int] = None) -> dict:
    D = _daily(archive, dh(sym))
    days, c = D["days"], D["adj"]
    rf = np.r_[0.0, [bills.growth(days[i - 1], days[i]) - 1.0 for i in range(1, len(days))]]
    rules = rule_universe()
    rr = rule_returns(c, rf, T318_COST[sym], rules)
    st = T318_WARMUP + 2
    ppy = 365.0 if sym == "BTC-USD" else 252.0
    sl = slice(st, None)
    names = [rule_name(r) for r in rules]
    j = reality_check(rr["ex"][sl], rr["xr"][sl], days[st:], T318_COST[sym], rr["pos"][sl], ppy=ppy, names=names,
                      n_phases=n_phases, spa_boot=spa_boot, wf_ci=wf_ci, decades=T318_DECADES if sym == "SPY" else ())
    j["window"] = (days[st], days[-1])
    sw = np.abs(np.diff(rr["pos"][sl], axis=0)).mean(axis=0) * ppy
    j["switches_per_year"] = {nm: float(s) for nm, s in zip(names, sw)}
    j["bh_sharpe_ann"] = _sr_ann(rr["xr"][sl], ppy)
    return j


def b6c_misc_ta_reality_check(archive):
    """T-318."""
    need = [dh("SPY"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    j = _t318_asset(archive, "SPY", bills)
    repl = {}
    for s in T318_REPL:
        if _has(archive, dh(s)):
            r = _t318_asset(archive, s, bills, n_phases=1, wf_ci=False)
            repl[s] = {"window": r["window"], "n": r["n"], "spa_p_c": r["spa"]["p_c"], "pbo": r["pbo"]["pbo"],
                       "wf_sharpe_diff": (r["wf"]["calendar"] or {}).get("diff"), "best_rule": r["best_rule"]}
        else:
            repl[s] = None
    spa, pbo, wf = j["spa"], j["pbo"], j["wf"]
    wc, wp = wf.get("calendar") or {}, wf.get("pooled") or {}
    sw = j["switches_per_year"]
    fast = sorted(sw.values())[-5:] if sw else []
    reason = (f"SPY adjclose {j['window'][0]}..{j['window'][1]} ({j['n']} daily returns after the 250-day warm-up): 88 long/"
              f"flat rules (signal at close t, traded at close t+1, idle cash at DTB3, 2 bps per switch; the fastest rules "
              f"switch {fast[0]:.0f}-{fast[-1]:.0f} times a year) vs buy-and-hold (excess Sharpe {_s(j['bh_sharpe_ann'], 3)}). "
              f"Hansen SPA (loss = negative daily excess return, stationary bootstrap mean block {T318_SPA_BLOCK}, "
              f"{spa['n_boot']} draws): T = {spa['t_spa']:.3f}, consistent p {spa['p_c']:.4f} (lower {spa['p_l']:.4f}, "
              f"upper/Reality Check {spa['p_u']:.4f}); {spa['n_positive']} of 88 rules have a positive mean differential, "
              f"the most significant {j['spa_best_rule']}. CSCV PBO {pbo['pbo']:.3f} ({pbo['n_combinations']} splits of "
              f"{T318_PBO_S} partitions; median logit {pbo['median_logit']:+.2f}); by decade "
              + ", ".join(f"{k} {v:.2f}" for k, v in j["pbo_by_decade"].items())
              + f". In-sample best {j['best_rule']} (annualised excess Sharpe {j['best_sharpe_ann']:.3f}) DSR at 88 trials "
              f"{_f(j['dsr_best'])}. "
              + ((f"Walk-forward (best prior-5-year Sharpe on returns through the close before each switch, re-selected every 5 years on the calendar {j['window'][0][:4]} + 5k; "
                  f"out of sample {j['wf_window'][0]}..{j['wf_window'][1]}, {j['wf_window'][2]} days; picks "
                  + ", ".join(f"{s['month']} {s['rule']}" for s in j["wf_selections"])
                  + f"): excess Sharpe minus buy-and-hold {_s(wc.get('diff'))} ({_ci(wc.get('ci'))}, paired studentized CBB, "
                  f"{T318_WF_BLOCK}-day blocks); pooled over {j['wf_n_phases']} monthly re-selection phases {_s(wp.get('diff'))} "
                  f"({_ci(wp.get('ci'))}); per-phase range {_s((j['wf_phase_range'] or [None])[0])} to "
                  f"{_s((j['wf_phase_range'] or [None, None])[1])}") if j["wf_window"] else
                 "Walk-forward: the window is shorter than one 5-year selection plus an out-of-sample day")
              + (". SURPRISE: SPA rejects and PBO < 0.5" if j["surprise"] else "")
              + ". Replications (reported only): "
              + "; ".join(f"{s} {r['window'][0][:4]}-{r['window'][1][:4]} SPA p_c {r['spa_p_c']:.3f}, PBO {r['pbo']:.2f}, "
                          f"walk-forward Sharpe diff {_s(r['wf_sharpe_diff'])}" if r else f"{s} not archived" for s, r in repl.items())
              + " — " + j["why"])
    stat = {"n_days": j["n"], "window": j["window"], "spa": spa, "pbo": pbo, "pbo_by_decade": j["pbo_by_decade"],
            "best_rule": j["best_rule"], "best_sharpe_ann": j["best_sharpe_ann"], "dsr_best_88": j["dsr_best"],
            "wf_calendar": {"diff": wc.get("diff"), "ci": wc.get("ci"), "ci_mc_se": wc.get("ci_mc_se")},
            "wf_pooled": {"diff": wp.get("diff"), "ci": wp.get("ci"), "ci_mc_se": wp.get("ci_mc_se")},
            "wf_phase_range": j["wf_phase_range"], "wf_selections": j["wf_selections"], "bh_sharpe_ann": j["bh_sharpe_ann"],
            "surprise": j["surprise"], "replications": repl, "criteria": j["criteria"],
            "rule10": "walk-forward re-selection on the claim's calendar (1994 + 5k years); all 60 monthly phases pooled "
                      "and their per-phase range reported; the criterion needs both readings"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================= T-326 gold/silver ratio reversion ==

T326_MIN_N = 2000
T326_END = "2026-09-30"
T326_GCSI_START = "2002-01-01"
T326_ANCHOR = 500
T326_ENTRY, T326_EXIT, T326_STOP = 2.0, 0.0, 3.5
T326_MAX_HOLD = 120
T326_COST_LEG = 0.002
T326_BORROW = 0.005
T326_SB_BLOCK = 60
T326_N_TRIALS = 5              # 4 anchor/route variants + T-61's tested variant
T326_REGIMES = (("2008", "2008"), ("2011", "2011"), ("2020", "2020"), ("2024", "2026"))
GC_MONTHS = (2, 4, 6, 8, 10, 12)
SI_MONTHS = (3, 5, 7, 9, 12)


def trailing_z(x, L: int) -> np.ndarray:
    """(x_t - mean(x_{t-L+1..t})) / sd(x_{t-L+1..t}) (ddof 1); NaN before L observations."""
    x = np.asarray(x, float)
    n = x.size
    z = np.full(n, np.nan)
    if n < L or L < 2:
        return z
    c = x - x[:L].mean()
    s1 = np.concatenate([[0.0], np.cumsum(c)])
    s2 = np.concatenate([[0.0], np.cumsum(c * c)])
    m = (s1[L:] - s1[:-L]) / L
    v = (s2[L:] - s2[:-L] - L * m * m) / (L - 1)
    sd = np.sqrt(np.maximum(v, 0.0))
    with np.errstate(invalid="ignore", divide="ignore"):
        z[L - 1:] = np.where(sd > 0, (c[L - 1:] - m) / np.where(sd > 0, sd, 1.0), np.nan)
    return z


def ratio_rule(days: Sequence[str], A, B, anchor: int = T326_ANCHOR, start: str = "", end: str = T326_END,
               max_hold: int = T326_MAX_HOLD, cost_leg: float = T326_COST_LEG, borrow: float = T326_BORROW,
               entry: float = T326_ENTRY, exit_z: float = T326_EXIT, stop: float = T326_STOP) -> dict:
    """The z-score rule on x = ln(A/B): z > entry -> long B / short A (equal dollars); z < -entry -> long A / short B; the
    decision at close t fills at close t+1. Exit at z crossing ``exit_z``, at the ``stop`` (|z| >= stop on the entry
    side) or after ``max_hold`` trading days. A side re-arms only once z is back inside +-entry (no re-entry into a
    stopped trade). Legs drift (no rebalancing); costs ``cost_leg`` x leg value per leg per trade; ``borrow`` a year on
    the short leg, accrued by calendar days. Returns the daily net return per unit of leg notional over the window."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    n = len(days)
    z = trailing_z(np.log(A / B), anchor)
    rA = np.r_[0.0, A[1:] / A[:-1] - 1.0]
    rB = np.r_[0.0, B[1:] / B[:-1] - 1.0]
    o = np.array([_ord(d) for d in days])
    dt = np.r_[0, np.diff(o)]
    t0 = next((t for t in range(n) if np.isfinite(z[t]) and days[t] >= start), None)
    t1 = max((t for t in range(n) if days[t] <= end), default=-1)
    if t0 is None or t1 <= t0:
        return {"n": 0, "net": np.array([]), "days": [], "trades": [], "pos": np.array([])}
    net = np.zeros(t1 - t0 + 1)
    held = np.zeros(t1 - t0 + 1)
    X, target, e, Lv, Sv = 0, 0, -1, 0.0, 0.0
    armed_up = armed_dn = True
    trades, cur = [], None
    for t in range(t0, t1 + 1):
        k = t - t0
        if X != 0 and t > t0:
            rl, rs = (rB[t], rA[t]) if X == 1 else (rA[t], rB[t])
            net[k] += Lv * rl - Sv * rs - borrow * Sv * dt[t] / 365.0
            Lv *= 1 + rl
            Sv *= 1 + rs
        if target != X:                                     # fill the previous close's decision at this close
            if X != 0:
                net[k] -= cost_leg * (Lv + Sv)
                cur.update(exit=days[t], days_held=t - e, pnl=float(net[e - t0:k + 1].sum()))
                trades.append(cur)
                cur = None
            if target != 0:
                net[k] -= cost_leg * 2.0
                X, e, Lv, Sv = target, t, 1.0, 1.0
                cur = {"side": "long B/short A" if target == 1 else "long A/short B", "entry": days[t]}
            else:
                X = 0
        held[k] = X
        zt = z[t]
        if not np.isfinite(zt):
            continue
        if target == 0:
            if armed_up and zt > entry:
                target = 1
            elif armed_dn and zt < -entry:
                target = -1
        elif target == 1:
            if zt <= exit_z or zt >= stop or (X == 1 and t + 1 - e >= max_hold):
                target = 0
                armed_up = False
        elif target == -1:
            if zt >= -exit_z or zt <= -stop or (X == -1 and t + 1 - e >= max_hold):
                target = 0
                armed_dn = False
        if zt <= entry:
            armed_up = True
        if zt >= -entry:
            armed_dn = True
    if cur is not None:
        cur.update(exit=None, days_held=t1 - e, pnl=float(net[e - t0:].sum()))
        trades.append(cur)
    return {"n": int(net.size), "net": net, "days": list(days[t0:t1 + 1]), "trades": trades, "pos": held,
            "z_last": float(z[t1]) if np.isfinite(z[t1]) else None}


def variance_ratio(x, q: int) -> dict:
    """Lo-MacKinlay variance ratio of the increments of ``x`` at horizon q (overlapping, bias-corrected) with the
    heteroskedasticity-robust z*."""
    x = np.asarray(x, float)
    dx = np.diff(x)
    n = dx.size
    if n <= 2 * q:
        return {"q": q, "vr": None, "z": None}
    mu = dx.mean()
    e = dx - mu
    s1 = float(e @ e) / (n - 1)
    xq = x[q:] - x[:-q] - q * mu
    m = q * (n - q + 1) * (1 - q / n)
    vr = float((xq @ xq) / m / s1)
    den = float(e @ e) ** 2
    theta = 0.0
    for j in range(1, q):
        dj = n * float((e[j:] ** 2) @ (e[:-j] ** 2)) / den
        theta += (2.0 * (q - j) / q) ** 2 * dj
    return {"q": q, "vr": vr, "z": math.sqrt(n) * (vr - 1) / math.sqrt(theta) if theta > 0 else None}


@functools.lru_cache(maxsize=None)
def _weekdays(y: int, m: int) -> tuple:
    d = date(y, m, 1)
    out = []
    while d.month == m:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return tuple(out)


def last_trade_day(y: int, m: int) -> date:
    """CME metals last trading day: the third-last business day of the contract month (weekdays; holidays not modelled)."""
    return _weekdays(y, m)[-3]


def first_notice_day(y: int, m: int) -> date:
    """CME metals first notice day: the last business day of the month before the contract month."""
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    return _weekdays(py, pm)[-1]


@functools.lru_cache(maxsize=None)
def front_contract(t: date, months: tuple) -> tuple:
    """The nearest active month whose first notice day is still ahead (positions roll before first notice)."""
    y, m = t.year, t.month
    for k in range(0, 30):
        mm = (m - 1 + k) % 12 + 1
        yy = y + (m - 1 + k) // 12
        if mm in months and t < first_notice_day(yy, mm):
            return yy, mm
    raise ValueError("no active month")


def roll_flags(days: Sequence[str], months: Sequence[int], window: int = 2) -> np.ndarray:
    """True on the sessions within +-``window`` sessions of each scheduled roll (the last session before each active
    month's first notice day)."""
    n = len(days)
    fl = np.zeros(n, bool)
    if n == 0:
        return fl
    y0, y1 = int(days[0][:4]), int(days[-1][:4]) + 1
    for y in range(y0, y1 + 1):
        for m in months:
            f = first_notice_day(y, m).isoformat()
            j = bisect.bisect_left(days, f) - 1
            if 0 <= j < n and days[j] >= days[0] and f <= days[-1]:
                fl[max(0, j - window):min(n, j + window + 1)] = True
    return fl


def roll_adjusted_index(days: Sequence[str], F, months: Sequence[int], etf: Optional[dict] = None, window: int = 2) -> np.ndarray:
    """APPROXIMATE roll adjustment of a Yahoo continuous futures close: daily returns inside the scheduled roll windows
    are replaced by the ETF's return that day ({day: adjclose}; 0 when absent). Contract identity is not known."""
    F = np.asarray(F, float)
    r = np.r_[0.0, F[1:] / F[:-1] - 1.0]
    fl = roll_flags(days, months, window)
    for i in np.where(fl)[0]:
        if i == 0:
            continue
        a, b = (etf or {}).get(days[i - 1]), (etf or {}).get(days[i])
        r[i] = b / a - 1.0 if a and b else 0.0
    return F[0] * np.cumprod(1.0 + r)


def _align(*series: tuple) -> tuple:
    """Common days of several (days, values) pairs and the aligned value arrays."""
    common = set(series[0][0])
    for d, _ in series[1:]:
        common &= set(d)
    days = sorted(common)
    out = []
    for d, v in series:
        ix = {x: i for i, x in enumerate(d)}
        out.append(np.array([v[ix[x]] for x in days], float))
    return days, out


def ratio_reversion(gld: tuple, slv: tuple, gcf: Optional[tuple] = None, scf: Optional[tuple] = None,
                    min_n: int = T326_MIN_N, n_boot: Optional[int] = None, seed: int = SEED, end: str = T326_END) -> dict:
    """T-326 core. ``gld``/``slv``: (days, adjclose); ``gcf``/``scf``: (days, close) of the continuous futures (optional,
    approximate route reported only). Criteria: stationary-bootstrap 95% lower bound of the mean daily net return > 0;
    DSR > 0.95 at 5 trials; same sign on the roll-adjusted GC/SI route (None: the exact CME roll is not reconstructible)."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    days, (A, B) = _align(gld, slv)
    P = ratio_rule(days, A, B, T326_ANCHOR, "", end)
    net = P["net"]
    n = P["n"]
    def lb_ok(t):
        """'95% lower bound > 0' must not hinge on the one- vs two-sided reading: passes when the two-sided 95% lower end
        is above 0, fails when even the one-sided 95% lower bound is not, else undecided."""
        lo2, lo1 = t["ci"][0], t["ci1"][0]
        se2, se1 = (t.get("ci_mc_se") or [0, 0])[0], (t.get("ci1_mc_se") or [0, 0])[0]
        p2, n2 = resolve(lo2, se2, 0.0, "gt")
        p1, n1 = resolve(lo1, se1, 0.0, "gt")
        if p2 is True:
            return True, n2
        if p1 is False:
            return False, n1
        return None, (n2 or n1 or " [the two-sided and one-sided readings disagree: undecided]")

    mt = _mc(lambda seed: sb_mean_ci(net, T326_SB_BLOCK, nb, seed), lambda t: lb_ok(t)[0], seed, keys=("ci", "ci1")) \
        if n >= 8 else {"est": float(net.mean()) if n else None, "ci": [None, None], "ci1": [None, None]}
    fam = {"GLD/SLV 500d (primary)": net}
    fam["GLD/SLV 1250d"] = ratio_rule(days, A, B, 1250, "", end)["net"]
    fam["T-61 proxy: GLD/SLV 250d, 21-day hold"] = ratio_rule(days, A, B, 250, "", end, max_hold=21)["net"]
    route = {"criterion": None}
    if gcf is not None and scf is not None:
        etf_g = dict(zip(*gld))
        etf_s = dict(zip(*slv))
        fd, (G, S_) = _align(gcf, scf)
        Ga = roll_adjusted_index(fd, G, GC_MONTHS, etf_g)
        Sa = roll_adjusted_index(fd, S_, SI_MONTHS, etf_s)
        R1 = ratio_rule(fd, Ga, Sa, T326_ANCHOR, T326_GCSI_START, end, borrow=0.0)
        R0 = ratio_rule(fd, G, S_, T326_ANCHOR, T326_GCSI_START, end, borrow=0.0)
        R20 = ratio_rule(fd, Ga, Sa, 5040, T326_GCSI_START, end, borrow=0.0)
        fam["GC/SI 500d (approximate roll)"] = R1["net"]
        fam["GC/SI 20-year (approximate roll)"] = R20["net"]
        route.update(adj_mean=float(R1["net"].mean()) if R1["n"] else None, adj_n=R1["n"], adj_trades=len(R1["trades"]),
                     raw_mean=float(R0["net"].mean()) if R0["n"] else None, window=(R1["days"][0], R1["days"][-1]) if R1["n"] else None)
    fam_sr = [_sr_pp(x) for x in fam.values() if len(x) > 2]
    ds = dsr_family(net, fam_sr, T326_N_TRIALS)
    lo, hi = mt.get("ci") or [None, None]
    se_lo, se_hi = mt.get("ci_mc_se") or [0.0, 0.0]
    ok1 = lb_ok(mt) if lo is not None else (None, " [fewer than 8 sessions]")
    crit = [(f"stationary-bootstrap (mean block {T326_SB_BLOCK}) 95% lower bound of the mean daily net return > 0 "
             f"(two-sided lower {_bp(lo, 2)}, one-sided lower {_bp((mt.get('ci1') or [None])[0], 2)}){ok1[1]}", ok1[0],
             hi is not None and resolve(hi, se_hi, 0.0, "lt")[0] is True),
            dsr_row(ds, f"DSR > {DSR_PASS} at {T326_N_TRIALS} trials"),
            ("same sign on the roll-adjusted GC=F/SI=F route (NOT IMPLEMENTED: the CME active-month roll of Yahoo's continuous "
             "series cannot be reconstructed, since Yahoo serves no expired contracts; approximate route reported only)", None, False)]
    v, why = _decide(crit, n, min_n, "trading days")
    reg = {}
    for a, b in T326_REGIMES:
        m = np.array([a <= d[:4] <= b for d in P["days"]])
        if m.any():
            reg[f"{a}-{b}" if a != b else a] = {"mean_bp": float(net[m].mean() * 1e4), "days_in_trade": int((P["pos"][m] != 0).sum())}
    x = np.log(A / B)
    i0 = days.index(P["days"][0]) if P["days"] else 0
    vr = {q: variance_ratio(x[i0:days.index(P["days"][-1]) + 1], q) for q in (20, 60, 250)} if P["days"] else {}
    return {"n": int(n), "window": (P["days"][0], P["days"][-1]) if n else None, "mean": mt, "sharpe_ann": _sr_ann(net, 252),
            "dsr": ds, "family_sharpes": dict(zip(fam.keys(), [_sr_pp(x) for x in fam.values()])), "trades": P["trades"],
            "n_trades": len(P["trades"]), "days_in_trade": int((P["pos"] != 0).sum()), "route": route, "regimes": reg,
            "vr": vr, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_misc_gold_silver_ratio(archive):
    """T-326."""
    need = [dh("GLD"), dh("SLV")]
    miss = _missing(archive, need)
    if miss:
        return miss
    g, s = _daily(archive, dh("GLD")), _daily(archive, dh("SLV"))
    fut = None
    if _has(archive, dh("GC=F")) and _has(archive, dh("SI=F")):
        gf, sf = _daily(archive, dh("GC=F")), _daily(archive, dh("SI=F"))
        fut = ((gf["days"], gf["close"]), (sf["days"], sf["close"]))
    j = ratio_reversion((g["days"], g["adj"]), (s["days"], s["adj"]), *(fut or (None, None)))
    mt, ds, rt = j["mean"], j["dsr"], j["route"]
    tr = j["trades"]
    wins = sum(1 for t in tr if t.get("pnl", 0) > 0)
    reason = (f"x = ln(GLD/SLV adjclose), z on the trailing 500 sessions; z > 2 long SLV/short GLD, z < -2 the reverse, filled "
              f"at the next close; exit at z = 0, 120-session time stop, stop at |z| = 3.5; 20 bps per leg per trade, 50 bps/yr "
              f"borrow on the short leg; window {j['window'][0]}..{j['window'][1]} ({j['n']} sessions, {j['n_trades']} trades, "
              f"{wins} winners, {j['days_in_trade']} sessions in a trade). Mean daily net return {_bp(mt.get('est'), 2)} "
              f"({_ci(mt.get('ci'), 2, 1e4, ' bp')}, stationary bootstrap mean block {T326_SB_BLOCK}, {N_BOOT} draws x {REPS}+ "
              f"seeds), annualised Sharpe {_s(j['sharpe_ann'])}; DSR {_f(ds['dsr'])} at {T326_N_TRIALS} trials (variance from "
              + ", ".join(f"{k} {_s(v, 4)}" for k, v in j["family_sharpes"].items())
              + " per-session Sharpes). GC=F/SI=F route (APPROXIMATE: scheduled CME roll windows replaced by GLD/SLV returns; "
              f"20 bps per leg, no borrow): mean {_bp(rt.get('adj_mean'), 2)} over {rt.get('adj_n')} sessions "
              f"({rt.get('adj_trades')} trades), unadjusted {_bp(rt.get('raw_mean'), 2)}; not a criterion value. Regimes: "
              + ", ".join(f"{k} {v['mean_bp']:+.2f} bp ({v['days_in_trade']} days in trade)" for k, v in j["regimes"].items())
              + ". Variance ratio of the log ratio: "
              + ", ".join(f"VR({q}) {_f(v['vr'])} (z* {_s(v['z'], 2)})" for q, v in j["vr"].items())
              + " — " + j["why"])
    stat = {"n_days": j["n"], "window": j["window"], "mean_daily_net": mt.get("est"), "ci": mt.get("ci"),
            "ci_mc_se": mt.get("ci_mc_se"), "sharpe_ann": j["sharpe_ann"], "dsr": ds, "family_sharpes": j["family_sharpes"],
            "n_trades": j["n_trades"], "trades": tr, "days_in_trade": j["days_in_trade"], "gc_si_route_approx": rt,
            "regimes": j["regimes"], "variance_ratio": {str(k): v for k, v in j["vr"].items()}, "criteria": j["criteria"],
            "rule10": "daily state machine on trailing statistics (no grid phase)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ====================================================================== T-370 metals cash-and-carry basis ==

T370_MIN_N = 4000
T370_START = "2005-01-01"
T370_END = "2026-09-30"
T370_BAND = 0.005
T370_LAG = 21
T370_JUMP_K = 5.0
T370_N_TRIALS = 6
GLD_FEE, GLD_LAUNCH, GLD_OZ0 = 0.004, date(2004, 11, 18), 0.1
SLV_FEE, SLV_LAUNCH, SLV_OZ0 = 0.005, date(2006, 4, 28), 1.0       # 10 oz at launch = 1 oz on Yahoo's split-adjusted close


def ounces_per_share(day: str, oz0: float, fee: float, launch: date) -> float:
    """The rule's ounces per share: oz0 x (1 - fee)^(years since launch) (sponsor-published values are not archived)."""
    return oz0 * (1.0 - fee) ** ((date.fromisoformat(day) - launch).days / 365.25)


def implied_financing(days: Sequence[str], F, etf_close, oz: Callable, months: Sequence[int], rate: Callable,
                      start: str = T370_START, end: str = T370_END, window: int = 2, jump_k: float = T370_JUMP_K) -> dict:
    """Daily implied financing i = ln(F/S) x 365/d (continuous; the rule's simple (F/S - 1) x 365/d also returned) with
    S = ETF close / ounces per share and d the calendar days to the last trading day of the front active month; the
    sessions within +-``window`` of each scheduled roll and of any jump in ln(F/S) beyond ``jump_k`` robust s.d. are
    dropped. ``rate(days)`` -> continuous DTB3 on each day."""
    F, E = np.asarray(F, float), np.asarray(etf_close, float)
    S = E / np.array([oz(d) for d in days])
    lb = np.log(F / S)
    n = len(days)
    drop = roll_flags(days, months, window)
    dl = np.diff(lb)
    if dl.size > 10:
        med = np.median(dl)
        sd = 1.4826 * np.median(np.abs(dl - med))
        for i in np.where(np.abs(dl - med) > jump_k * max(sd, 1e-4))[0]:          # robust s.d. floored at 1 bp
            drop[max(0, i + 1 - window):min(n, i + 1 + window + 1)] = True
    keep = np.array([start <= d <= end for d in days]) & ~drop
    dd = [days[i] for i in np.where(keep)[0]]
    months = tuple(months)
    d_exp = np.array([(last_trade_day(*front_contract(date.fromisoformat(d), months)) - date.fromisoformat(d)).days for d in dd], float)
    lbk = lb[keep]
    ic = lbk * 365.0 / d_exp
    isim = (np.exp(lbk) - 1.0) * 365.0 / d_exp
    rf = np.asarray(rate(dd), float)
    # level-free diagnostic: the carry implied by the decay of ln(F/S) between consecutive kept sessions in one contract
    # (an ounces-per-share level error cancels in the differences; roll jumps outside the dropped windows do not)
    kix = np.where(keep)[0]
    fc = [front_contract(date.fromisoformat(days[i]), months) for i in kix]
    num = den = rsum = 0.0
    for a_, b_ in zip(range(len(kix) - 1), range(1, len(kix))):
        i0, i1 = kix[a_], kix[b_]
        if i1 == i0 + 1 and fc[a_] == fc[b_]:
            cd = (date.fromisoformat(days[i1]) - date.fromisoformat(days[i0])).days
            num += lb[i1] - lb[i0]
            den += cd / 365.0
            rsum += rf[b_] * cd / 365.0
    decay = {"i": -num / den, "rf": rsum / den, "dev": -num / den - rsum / den, "years": den} if den > 0 else None
    return {"days": dd, "i": ic, "i_simple": isim, "rf": rf, "dev": ic - rf, "dev_simple": isim - (np.exp(rf * d_exp / 365.0) - 1) * 365.0 / d_exp,
            "d": d_exp, "n_dropped_roll": int((drop & np.array([start <= d <= end for d in days])).sum()),
            "daily_noise_bp": float(np.std(dl) * 1e4) if dl.size else None, "decay": decay}


def band_test(dev, band: float = T370_BAND, lag: int = T370_LAG, level: float = 0.95) -> dict:
    """HAC (Newey-West, lag ``lag``) two-sided interval of the mean deviation and the band criterion: inside [-band,
    +band] passes; wholly outside fails decisively; straddling a band edge fails (not decisively)."""
    h = hac_mean(dev, lag)
    if h["se"] is None:
        return {**h, "ci": [None, None], "ok": None, "decisive": False}
    z = NormalDist().inv_cdf(1 - (1 - level) / 2)
    lo, hi = h["mean"] - z * h["se"], h["mean"] + z * h["se"]
    ok = (lo > -band) and (hi < band)
    return {**h, "ci": [lo, hi], "ok": bool(ok), "decisive": bool(hi < -band or lo > band)}


def _band_summary(F: dict, label: str) -> Optional[dict]:
    if F["dev"].size < 3:
        return {"label": label, "n": int(F["dev"].size), "window": None, "mean": None, "se": None, "ci": [None, None],
                "ok": None, "decisive": False, "ci_bonf6": [None, None], "ok_bonf6": None, "decisive_bonf6": False, "decay": None}
    t = band_test(F["dev"])
    t6 = band_test(F["dev"], level=1 - 0.05 / T370_N_TRIALS)          # the pass's '6 trials counted' (Bonferroni)
    dv = F["dev"]
    reg = {}
    for nm, a, b in (("2005-2019", "2005", "2019-12-31"), ("2020-2026", "2020", "2026-12-31"),
                     ("2024-12..2025-04 EFP", "2024-12", "2025-04-30")):
        m = np.array([a <= d <= b for d in F["days"]])
        if m.sum() > 20:
            reg[nm] = {"mean": float(dv[m].mean()), "n": int(m.sum())}
    return {"label": label, "n": int(dv.size), "window": (F["days"][0], F["days"][-1]) if F["days"] else None,
            "mean": t["mean"], "se": t["se"], "ci": t["ci"], "ok": t["ok"], "decisive": t["decisive"], "ci_bonf6": t6["ci"],
            "ok_bonf6": t6["ok"], "decisive_bonf6": t6["decisive"],
            "sd": float(dv.std(ddof=1)) if dv.size > 1 else None, "share_i_neg": float(np.mean(F["i"] < 0)) if dv.size else None,
            "mean_simple": float(np.mean(F["dev_simple"])) if dv.size else None, "regimes": reg,
            "n_dropped_roll": F["n_dropped_roll"], "daily_noise_bp": F["daily_noise_bp"], "median_d": float(np.median(F["d"])) if dv.size else None,
            "s_sensitivity_bp": float(0.001 * 365.0 / np.median(F["d"]) * 1e4) if dv.size else None, "decay": F["decay"]}


T370_OTHER = (("platinum", "PL=F", "PPLT"), ("palladium", "PA=F", "PALL"), ("copper", "HG=F", "CPER"))


def band_row(x: Optional[dict], label: str) -> tuple:
    """(name, ok, decisive) for the T-370 pass: the HAC (lag 21) interval of mean(i - DTB3) at the 6-trial Bonferroni
    level (two-sided 1 - 0.05/6, the pass's '6 trials counted') inside [-50, +50] bp; wholly outside fails decisively. The
    unadjusted 95% interval is printed alongside."""
    if x is None or x.get("mean") is None:
        return (f"{label} (no usable days)", None, False)
    lv = 100.0 * (1.0 - 0.05 / T370_N_TRIALS)
    return (f"{label}: HAC (lag {T370_LAG}) {lv:.2f}% CI (95% Bonferroni over {T370_N_TRIALS} trials) of mean(i - DTB3) inside "
            f"+-50 bp (mean {_bp(x['mean'])}, {_ci(x['ci_bonf6'], 1, 1e4, ' bp')}; unadjusted 95% {_ci(x['ci'], 1, 1e4, ' bp')}; "
            f"{x['n']} days)", x["ok_bonf6"], bool(x["decisive_bonf6"]))


def metals_basis(gold: tuple, silver: Optional[tuple], rate: Callable, min_n: int = T370_MIN_N) -> dict:
    """T-370 core. ``gold`` = (days, GC=F close, GLD close), ``silver`` = (days, SI=F close, SLV close) or None.

    The claim and its pass are gold-only: the one criterion is the gold band test on the rule's construction (GLD close /
    fee-formula ounces, the sponsor's ounces being unavailable) at the 6-trial Bonferroni level. 'Each other metal is a
    separate trial' (silver computed and reported with the same test; platinum, palladium, copper not archived), and the
    trial's 'Robustness: GLD NAV instead of the GLD close' is report-only (module convention; not archived)."""
    gd, gf, ge = gold
    G = implied_financing(gd, gf, ge, lambda d: ounces_per_share(d, GLD_OZ0, GLD_FEE, GLD_LAUNCH), GC_MONTHS, rate)
    g = _band_summary(G, "gold")
    alt = implied_financing(gd, gf, ge, lambda d: ounces_per_share(d, GLD_OZ0, GLD_FEE, GLD_LAUNCH), (2, 4, 6, 8, 12), rate)
    g["alt_no_oct_mean"] = float(alt["dev"].mean()) if alt["dev"].size else None
    s = None
    if silver is not None:
        sd_, sf, se = silver
        Sv = implied_financing(sd_, sf, se, lambda d: ounces_per_share(d, SLV_OZ0, SLV_FEE, SLV_LAUNCH), SI_MONTHS, rate)
        s = _band_summary(Sv, "silver")
    crit = [band_row(g, "gold (GC=F vs GLD close / fee-formula ounces)")]
    v, why = _decide(crit, g["n"], min_n, "trading days")
    sep = {"silver": None if s is None else {"ok": s.get("ok_bonf6"), "decisive": bool(s.get("decisive_bonf6")),
                                             "row": band_row(s, "silver (SI=F vs SLV close / fee-formula ounces)")[0]}}
    for nm, fut, etf in T370_OTHER:
        sep[nm] = f"{fut} vs {etf}: not archived"
    return {"n": g["n"], "gold": g, "silver": s, "separate_trials": sep,
            "robustness_nav": "GLD NAV (LBMA PM) with sponsor ounces per share: not archived (report-only check, not run)",
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_misc_metals_basis(archive):
    """T-370."""
    need = [dh("GC=F"), dh("GLD"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    sr = SameDayRate(_fred(archive, DTB3_B))
    gf, ge = _daily(archive, dh("GC=F")), _daily(archive, dh("GLD"))
    gd, (F, E) = _align((gf["days"], gf["close"]), (ge["days"], ge["close"]))
    silver = None
    if _has(archive, dh("SI=F")) and _has(archive, dh("SLV")):
        sf, se = _daily(archive, dh("SI=F")), _daily(archive, dh("SLV"))
        sd_, (SF, SE) = _align((sf["days"], sf["close"]), (se["days"], se["close"]))
        silver = (sd_, SF, SE)
    j = metals_basis((gd, F, E), silver, sr.rates)
    g, s = j["gold"], j["silver"]

    def txt(x):
        if x is None:
            return "not archived"
        if not x["n"]:
            return "no usable days"
        return (f"{x['window'][0]}..{x['window'][1]}, {x['n']} days after dropping {x['n_dropped_roll']} roll-window/jump "
                f"days (median d {x['median_d']:.0f} calendar days; daily ln(F/S) noise {x['daily_noise_bp']:.0f} bp): mean(i - "
                f"DTB3) {_bp(x['mean'])} ({_ci(x['ci'], 1, 1e4, ' bp')}, HAC lag {T370_LAG}; 6-trial Bonferroni "
                f"{_ci(x['ci_bonf6'], 1, 1e4, ' bp')}), simple-rate form {_bp(x['mean_simple'])}, s.d. {x['sd'] * 100:.1f}%, i < 0 on "
                f"{x['share_i_neg'] * 100:.1f}% of days; "
                + ", ".join(f"{k} {_bp(r['mean'])} ({r['n']} d)" for k, r in x["regimes"].items())
                + f"; a 0.1% error in S moves i by {x['s_sensitivity_bp']:.0f} bp at the median d"
                + (f"; level-free diagnostic (decay of ln(F/S) between consecutive kept sessions of one contract, "
                   f"{x['decay']['years']:.1f} years): implied carry {_pc(x['decay']['i'])} vs DTB3 {_pc(x['decay']['rf'])}, "
                   f"deviation {_bp(x['decay']['dev'])} (reported only)" if x.get("decay") else ""))

    reason = (f"Implied financing i = ln(F/S) x 365/d (continuous; DTB3 converted the same way, same-day print), S = ETF close "
              f"/ ounces per share by the rule's fee formula, d to the CME last trading day (third-last weekday) of the front "
              f"active month (rolled at first notice), +-2 sessions around each scheduled roll and any > {T370_JUMP_K:g}-robust-"
              f"s.d. jump in ln(F/S) dropped. Gold (GC=F vs GLD): " + txt(g)
              + f"; with Oct skipped (Yahoo's observed 2025 practice) the gold mean would be {_bp(g.get('alt_no_oct_mean'))} "
              f"(sensitivity only). The claim is gold-only and is judged on the gold interval at the pass's 6-trial "
              f"Bonferroni level. Separate trials (reported, not this claim's criteria): silver (SI=F vs SLV, Mar/May/Jul/Sep/"
              f"Dec): " + txt(s)
              + "; platinum (PL=F vs PPLT), palladium (PA=F vs PALL) and copper (HG=F vs CPER) not archived. Measurement limits "
              "(rule 9): Yahoo's continuous contract identity and roll days are undocumented (expired contracts return 404), the "
              "GLD close trades at 16:00 ET against a 13:30 ET COMEX settle, and the fee formula stands in for the sponsor's "
              "ounces per share (the rule's own fallback), whose level error is amplified by 365/d; the trial's robustness check "
              "(GLD NAV, LBMA PM, instead of the GLD close; the controls' noise check) is report-only and cannot be run: the "
              "sponsor NAV / ounces-per-share history is not archived — " + j["why"])
    stat = {"n_days": j["n"], "gold": g, "silver": s, "band_bp": T370_BAND * 1e4, "hac_lag": T370_LAG,
            "n_trials": T370_N_TRIALS, "decision_level_two_sided": 1 - 0.05 / T370_N_TRIALS,
            "separate_trials": j["separate_trials"], "robustness_nav": j["robustness_nav"], "criteria": j["criteria"],
            "rule10": "daily measurement (no grid phase)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================== T-372 equity index futures basis ==

T372_MIN_N = 2500
T372_START = "2010-01-01"
T372_END = "2026-09-30"
T372_THR = 0.0020
T372_LAG = 21
T372_W = (5, 60)
T372_N_TRIALS = 5
ZIRP = (("2010-01-01", "2015-12-31"), ("2020-03-01", "2021-12-31"))


def quarterly_expiries(sessions: Sequence[str], y0: int, y1: int) -> list:
    """Third Fridays of Mar/Jun/Sep/Dec; when the Friday is not a session (exchange holiday) the previous session."""
    ss = set(sessions)
    out = []
    for y in range(y0, y1 + 1):
        for m in (3, 6, 9, 12):
            d = date(y, m, 1)
            tf = d + timedelta(days=(4 - d.weekday()) % 7 + 14)
            t = tf.isoformat()
            if sessions and t <= sessions[-1] and t not in ss:
                j = bisect.bisect_left(sessions, t) - 1
                if j >= 0:
                    t = sessions[j]
            out.append(t)
    return out


def dividend_accrual(ex_days: Sequence[str], amounts: Sequence[float]) -> Callable:
    """acc(a, b): SPY dividends accrued over calendar days (a, b], each quarterly dividend spread uniformly over its
    accrual period (previous ex-date, its ex-date] (the first one over the 91 days before it)."""
    E = [date.fromisoformat(d) for d in ex_days]
    A = list(map(float, amounts))
    per = []
    for k, (e, a) in enumerate(zip(E, A)):
        s = E[k - 1] if k > 0 else e - timedelta(days=91)
        per.append((s, e, a / max((e - s).days, 1)))

    def acc(a: str, b: str, known_before: Optional[str] = None) -> float:
        da, db = date.fromisoformat(a), date.fromisoformat(b)
        tot = 0.0
        for s, e, rate in per:
            if known_before is not None and e.isoformat() >= known_before:
                continue
            lo, hi = max(s, da), min(e, db)
            if hi > lo:
                tot += rate * (hi - lo).days
        return tot
    return acc


def es_basis(es: tuple, gspc: tuple, spy: tuple, rate: Callable, start: str = T372_START, end: str = T372_END,
             window: tuple = T372_W, reading: str = "calendar") -> dict:
    """Daily implied financing r = ln((F + D)/I) x 365/d on the window days after each quarterly roll (calendar days
    5-60, or the 5th-60th session for ``reading`` 'trading'), F = ES=F, I = ^GSPC, D = 10 x SPY dividends accrued over the
    same window a year earlier (forecast; point in time) and over the window itself (realized, ex post); d = calendar
    days to the next quarterly expiry. Roll day = the session from 2 before to 3 after each expiry with the largest
    basis jump."""
    days, (F, I) = _align(es, gspc)
    sd, sc, sa = spy
    div = spy_dividends(sc, sa)
    exd = [sd[i] for i in np.where(div > 0)[0]]
    acc = dividend_accrual(exd, div[div > 0])
    if not days:
        return {"n": 0}
    b = F / I - 1.0
    exps = quarterly_expiries(days, int(days[0][:4]), int(days[-1][:4]) + 1)
    rows = []
    for q, T in enumerate(exps[:-1]):
        k = bisect.bisect_left(days, T)
        cand = [i for i in range(k - 2, k + 4) if 1 <= i < len(days)]
        if not cand or days[cand[0]] > end or T < (date.fromisoformat(start) - timedelta(days=95)).isoformat():
            continue
        roll = max(cand, key=lambda i: abs(b[i] - b[i - 1]))
        Tn = exps[q + 1]
        rd = date.fromisoformat(days[roll])
        for j in range(roll + 1, len(days)):
            t = days[j]
            if t >= Tn:
                break
            dd = (date.fromisoformat(t) - rd).days
            if reading == "calendar":
                if dd < window[0]:
                    continue
                if dd > window[1]:
                    break
            else:
                if j - roll < window[0]:
                    continue
                if j - roll > window[1]:
                    break
            if not (start <= t <= end):
                continue
            rows.append((t, j, Tn, T))
    if not rows:
        return {"n": 0}
    tt = [r[0] for r in rows]
    idx = np.array([r[1] for r in rows])
    dte = np.array([(date.fromisoformat(r[2]) - date.fromisoformat(r[0])).days for r in rows], float)
    Dfc = np.array([10.0 * acc((date.fromisoformat(t) - timedelta(days=365)).isoformat(),
                               (date.fromisoformat(Tn) - timedelta(days=365)).isoformat(), known_before=t) for t, _, Tn, _ in rows])
    Drl = np.array([10.0 * acc(t, Tn) for t, _, Tn, _ in rows])
    exo = [(e_, float(a_)) for e_, a_ in zip(exd, div[div > 0])]

    def literal(t, Tn):
        a_ = (date.fromisoformat(t) - timedelta(days=365)).isoformat()
        b_ = (date.fromisoformat(Tn) - timedelta(days=365)).isoformat()
        return 10.0 * sum(v for e_, v in exo if a_ < e_ <= b_)
    Dlit = np.array([literal(t, Tn) for t, _, Tn, _ in rows])
    Fv, Iv = F[idx], I[idx]
    rf = np.asarray(rate(tt), float)
    r_c = np.log((Fv + Dfc) / Iv) * 365.0 / dte
    r_s = (Fv / Iv - 1.0 + Dfc / Iv) * 365.0 / dte
    r_real = np.log((Fv + Drl) / Iv) * 365.0 / dte
    r_lit = np.log((Fv + Dlit) / Iv) * 365.0 / dte
    rf_s = (np.exp(rf * dte / 365.0) - 1.0) * 365.0 / dte
    return {"n": len(rows), "days": tt, "quarter": [r[3] for r in rows], "spread": r_c - rf, "spread_simple": r_s - rf_s,
            "spread_realized": r_real - rf, "spread_literal": r_lit - rf, "share_literal_zero": float(np.mean(Dlit == 0)),
            "r_imp": r_c, "rf": rf, "d": dte, "D_fc": Dfc, "D_real": Drl}


def cluster_lower(x, clusters: Sequence, n_boot: Optional[int] = None, seed: int = SEED, q: float = 0.05) -> dict:
    """Quarter-clustered percentile bootstrap of the mean: whole clusters resampled with replacement; the q-quantile."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    x = np.asarray(x, float)
    keys = sorted(set(clusters))
    ix = {k: i for i, k in enumerate(keys)}
    cid = np.array([ix[c] for c in clusters])
    C = len(keys)
    s = np.bincount(cid, weights=x, minlength=C)
    c = np.bincount(cid, minlength=C).astype(float)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, C, size=(nb, C))
    m = s[draw].sum(axis=1) / c[draw].sum(axis=1)
    return {"est": float(x.mean()), "ci": [float(np.quantile(m, q)), float(np.quantile(m, 1 - q))], "n_clusters": C}


def es_financing(es: tuple, gspc: tuple, spy: tuple, rate: Callable, min_n: int = T372_MIN_N, n_boot: Optional[int] = None,
                 seed: int = SEED) -> dict:
    """T-372 core: lower one-sided bound of mean(r_imp - DTB3) > 20 bp under the HAC and the quarter-clustered bootstrap
    (both must pass), at the pass's 95% with its '5 trials counted' applied as Bonferroni (one-sided 1 - 0.05/5); the
    unadjusted one-sided 95% bounds are reported. Realized (ex-post) dividends are the trial's robustness item: reported
    only (module convention)."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    B = es_basis(es, gspc, spy, rate)
    n = B["n"]
    if n < 8:
        crit = [("mean spread lower bound (fewer than 8 window days)", None, False)]
        v, why = _decide(crit, n, min_n, "window days")
        return {"n": n, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why, "basis": B}
    sp = B["spread"]
    h = hac_mean(sp, T372_LAG)
    qb = 0.05 / T372_N_TRIALS                                          # the pass's '5 trials counted' (Bonferroni)
    zb = NormalDist().inv_cdf(1 - qb)
    h_lo, h_hi = h["mean"] - zb * h["se"], h["mean"] + zb * h["se"]
    h_lo95, h_hi95 = h["mean"] - Z95_1 * h["se"], h["mean"] + Z95_1 * h["se"]
    cl = _mc(lambda seed: cluster_lower(sp, B["quarter"], nb, seed, q=qb),
             lambda t: resolve(t["ci"][0], (t.get("ci_mc_se") or [0, 0])[0], T372_THR, "gt")[0], seed)
    cl95 = mc_reps(lambda seed: cluster_lower(sp, B["quarter"], nb, seed), REPS, seed, ("ci",))
    c_lo, c_hi = cl["ci"]
    c_se = (cl.get("ci_mc_se") or [0.0, 0.0])
    okc, notec = resolve(c_lo, c_se[0], T372_THR, "gt")
    lv = f"one-sided {100 * (1 - qb):g}% (95% Bonferroni over {T372_N_TRIALS} trials)"
    crit = [(f"HAC (Newey-West lag {T372_LAG}) {lv} lower bound of mean(r_imp - DTB3) > 20 bp (lower {_bp(h_lo)}; "
             f"unadjusted 95% {_bp(h_lo95)})", bool(h_lo > T372_THR), bool(h_hi < T372_THR)),
            (f"quarter-clustered bootstrap ({cl['n_clusters']} quarters) {lv} lower bound > 20 bp (lower {_bp(c_lo)}{notec}; "
             f"unadjusted 95% {_bp(cl95['ci'][0])})", okc, resolve(c_hi, c_se[1], T372_THR, "lt")[0] is True)]
    v, why = _decide(crit, n, min_n, "window days")
    T = es_basis(es, gspc, spy, rate, reading="trading")
    tr = None
    if T["n"] >= 8:
        th = hac_mean(T["spread"], T372_LAG)
        tr = {"n": T["n"], "mean": th["mean"], "hac_lower": th["mean"] - Z95_1 * th["se"]}
    reg = {}
    zm = np.array([any(a <= d <= b for a, b in ZIRP) for d in B["days"]])
    for nm, m in (("ZIRP (2010-15, 2020-03..2021)", zm), ("positive-rate", ~zm),
                  ("2022-2026", np.array([d >= "2022-01-01" for d in B["days"]])),
                  ("quarter-end weeks", np.array([d[5:7] in ("03", "06", "09", "12") and int(d[8:10]) >= 24 for d in B["days"]]))):
        if m.sum() > 10:
            reg[nm] = {"mean": float(sp[m].mean()), "n": int(m.sum())}
    hr = hac_mean(B["spread_realized"], T372_LAG)
    return {"n": int(n), "window": (B["days"][0], B["days"][-1]), "n_quarters": cl["n_clusters"], "mean": h["mean"],
            "hac_se": h["se"], "hac_lower": h_lo, "hac_upper": h_hi, "hac_lower95": h_lo95, "hac_upper95": h_hi95,
            "cluster": cl, "cluster95": {"ci": cl95["ci"], "ci_mc_se": cl95.get("ci_mc_se")}, "level_one_sided": 1 - qb,
            "simple_mean": float(B["spread_simple"].mean()),
            "realized": {"mean": hr["mean"], "hac_lower": hr["mean"] - Z95_1 * hr["se"]}, "trading_reading": tr,
            "literal": {"mean": float(B["spread_literal"].mean()), "share_D_zero": B["share_literal_zero"]},
            "regimes": reg, "median_d": float(np.median(B["d"])), "mean_D_fc_pts": float(B["D_fc"].mean()),
            "mean_D_real_pts": float(B["D_real"].mean()),
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_misc_es_basis(archive):
    """T-372."""
    need = [dh("ES=F"), dh("^GSPC"), dh("SPY"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    sr = SameDayRate(_fred(archive, DTB3_B))
    e, g, s = _daily(archive, dh("ES=F")), _daily(archive, dh("^GSPC")), _daily(archive, dh("SPY"))
    j = es_financing((e["days"], e["close"]), (g["days"], g["close"]), (s["days"], s["close"], s["adj"]), sr.rates)
    if j["n"] < 8:
        return _out({"n_days": j["n"], "criteria": j["criteria"]}, j["n"], j["verdict"],
                    f"only {j['n']} window days could be formed from ES=F, ^GSPC and SPY — " + j["why"])
    cl, tr = j["cluster"], j["trading_reading"]
    reason = (f"r_imp = ln((F + D)/I) x 365/d (continuous; DTB3 continuous, same-day print), F = ES=F close, I = ^GSPC close, "
              f"d = calendar days to the next quarterly expiry (median {j['median_d']:.0f}), D = 10 x SPY dividends (recovered "
              f"from close/adjclose) accrued uniformly over their quarters for the same window a year earlier (mean "
              f"{j['mean_D_fc_pts']:.1f} index points; the literal 'ex-dates in the window' reading is degenerate because SPY "
              f"goes ex on the expiry Friday itself, one day outside the shifted window in most years: D = 0 on "
              f"{j['literal']['share_D_zero'] * 100:.0f}% of days, mean spread {_bp(j['literal']['mean'])}, reported only); calendar days 5-60 after "
              f"each detected roll, {j['window'][0]}..{j['window'][1]}: {j['n']} days in {j['n_quarters']} quarters. Mean spread "
              f"{_bp(j['mean'])}; one-sided {j['level_one_sided'] * 100:g}% bounds (the pass's 95% with its {T372_N_TRIALS} "
              f"trials counted, Bonferroni): HAC (lag {T372_LAG}) lower {_bp(j['hac_lower'])} / upper {_bp(j['hac_upper'])}, "
              f"quarter-clustered bootstrap lower {_bp(cl['ci'][0])} / upper {_bp(cl['ci'][1])} (threshold +20 bp; unadjusted "
              f"one-sided 95% lower bounds: HAC {_bp(j['hac_lower95'])}, clustered {_bp(j['cluster95']['ci'][0])}). "
              f"Reported: simple-rate form {_bp(j['simple_mean'])}; realized (ex-post) dividends (the trial's robustness item, "
              f"report-only) mean {_bp(j['realized']['mean'])} "
              f"(HAC lower {_bp(j['realized']['hac_lower'])}); sessions 5-60 reading "
              + (f"{tr['n']} days, mean {_bp(tr['mean'])}, HAC lower {_bp(tr['hac_lower'])}" if tr else "n/a")
              + "; " + ", ".join(f"{k} {_bp(v['mean'])} ({v['n']} d)" for k, v in j["regimes"].items())
              + ". The 16:00 ET settle check needs hourly ES=F (not archived); NQ/NDX variants not archived — " + j["why"])
    stat = {"n_days": j["n"], "window": j["window"], "n_quarters": j["n_quarters"], "mean_spread": j["mean"],
            "hac_se": j["hac_se"], "level_one_sided": j["level_one_sided"], "hac_lower_bonf5": j["hac_lower"],
            "hac_upper_bonf5": j["hac_upper"], "cluster_bonf5": cl["ci"], "cluster_ci_mc_se": cl.get("ci_mc_se"),
            "hac_lower_1s95": j["hac_lower95"], "cluster_lower_1s95": j["cluster95"]["ci"][0],
            "simple_mean": j["simple_mean"], "realized": j["realized"],
            "trading_day_reading": tr, "regimes": j["regimes"], "mean_D_forecast_pts": j["mean_D_fc_pts"],
            "mean_D_realized_pts": j["mean_D_real_pts"], "literal_reading": j["literal"],
            "criteria": j["criteria"],
            "rule10": "daily measurement on the claim's roll calendar (days 5-60 after each quarterly roll)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ===================================================================================== T-416 Fear & Greed ==

T416_MIN_N = 30
T416_H = 30
T416_THR = 20.0
T416_EFFECT = 0.05
T416_REFRACTORY = 10
T416_BLOCKS = (30, 60)         # the trial's 30-day blocks and rule 10's 2 x hold
T416_N_CELLS = 72
T416_SUBS = (("2018-01-01", "2021-12-31"), ("2022-01-01", "2026-12-31"))
T416_HS = (30, 60, 90)
T416_THRS = (20.0, 25.0, "decile")


def _close_map(days: Sequence[str], close) -> dict:
    return {d: float(c) for d, c in zip(days, close)}


def fng_events(fng: dict, kind: str = "first", thr=T416_THR, H: int = T416_H, refractory: int = T416_REFRACTORY) -> dict:
    """Signal days t (F_t known at 00:00 UTC on t+1). 'first': F_t <= thr after F above thr at the previous observation
    and no such crossing in the prior ``refractory`` calendar days; 'level': every day with F_t <= thr. ``thr`` 'decile':
    the expanding 10th percentile of F before t (>= 365 observations). Non-overlapping events: greedy, entries >= H days
    apart. Returns {'all': [...], 'kept': [...]} of signal days."""
    ks = sorted(fng)
    vals = [fng[k][0] if isinstance(fng[k], tuple) else float(fng[k]) for k in ks]
    hist: list = []
    sig, last_cross = [], None
    for i, (d, f) in enumerate(zip(ks, vals)):
        if thr == "decile":
            th = hist[int(0.1 * (len(hist) - 1))] if len(hist) >= 365 else None
        else:
            th = float(thr)
        if th is not None:
            if kind == "level":
                if f <= th:
                    sig.append(d)
            elif i > 0 and f <= th < vals[i - 1]:
                o = _ord(d)
                if last_cross is None or o - last_cross > refractory:
                    sig.append(d)
                last_cross = o
        bisect.insort(hist, f)
    kept, last = [], None
    for d in sig:
        o = _ord(d)
        if last is None or o - last >= H:
            kept.append(d)
            last = o
    return {"all": sig, "kept": kept}


def _entry(d: str) -> str:
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def fng_panel(px: dict, fng: dict, H: int) -> dict:
    """Daily regression rows over the entry days e = t + 1 of every FNG day t: y = ln(C_{e+H}/C_e), x = ln(C_e/C_{e-30})."""
    rows = []
    for t in sorted(fng):
        e = _entry(t)
        a = px.get(e)
        f = px.get((date.fromisoformat(e) + timedelta(days=H)).isoformat())
        p = px.get((date.fromisoformat(e) - timedelta(days=30)).isoformat())
        if a and f and p:
            rows.append((t, e, math.log(f / a), math.log(a / p)))
    return {"sig": [r[0] for r in rows], "entry": [r[1] for r in rows], "y": np.array([r[2] for r in rows]),
            "x": np.array([r[3] for r in rows])}


def _ols3(y, I, x):
    X = np.column_stack([np.ones(y.size), I, x])
    try:
        return np.linalg.lstsq(X, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return np.full(3, np.nan)


def _boot_coef(y, I, x, mean_block: float, n_boot: int, seed: int) -> np.ndarray:
    """Stationary-bootstrap draws of the indicator coefficient (rows resampled jointly)."""
    n = y.size
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < n_boot:
        k = min(500, n_boot - done)
        idx = _stationary_idx(rng, n, mean_block, k)
        Y, Ii, Xx = y[idx], I[idx], x[idx]
        s = {"n": float(n), "I": Ii.sum(1), "x": Xx.sum(1), "II": (Ii * Ii).sum(1), "Ix": (Ii * Xx).sum(1), "xx": (Xx * Xx).sum(1),
             "y": Y.sum(1), "Iy": (Ii * Y).sum(1), "xy": (Xx * Y).sum(1)}
        M = np.empty((k, 3, 3))
        M[:, 0, 0] = n
        M[:, 0, 1] = M[:, 1, 0] = s["I"]
        M[:, 0, 2] = M[:, 2, 0] = s["x"]
        M[:, 1, 1] = s["II"]
        M[:, 1, 2] = M[:, 2, 1] = s["Ix"]
        M[:, 2, 2] = s["xx"]
        v = np.stack([s["y"], s["Iy"], s["xy"]], axis=1)
        good = s["I"] >= 1
        b = np.full(k, np.nan)
        if good.any():
            sol = np.linalg.solve(M[good], v[good][..., None])[..., 0]
            b[good] = sol[:, 1]
        out.append(b)
        done += k
    b = np.concatenate(out)
    return b[np.isfinite(b)]


def coef_test(y, I, x, mean_block: float, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """OLS coefficient of the event indicator (y on 1, I, x) with stationary-bootstrap PERCENTILE inference (rule 6): the
    one-sided 95% lower / upper bounds are the 5% / 95% quantiles of the resampled coefficients b*, and the one-sided p
    for H0: coef <= 0 is P(b* <= 0) (the level at which the percentile lower bound reaches 0)."""
    nb = T416_BOOT if n_boot is None else int(n_boot)
    y, I, x = (np.asarray(v, float) for v in (y, I, x))
    b = float(_ols3(y, I, x)[1])
    bs = _boot_coef(y, I, x, mean_block, nb, seed)
    return {"coef": b, "p": float((np.sum(bs <= 0.0) + 1) / (bs.size + 1)),
            "ci": [float(np.quantile(bs, 0.05)), float(np.quantile(bs, 0.95))],   # one-sided 95% lower / upper bounds
            "n_boot": int(bs.size), "mean_block": mean_block}


def _cell_events(px: dict, fng: dict, kind: str, thr, H: int) -> dict:
    """Per-event excess forward returns of one cell: raw = y - mean(y over all days); residual = y - (a + b x) from the
    regression of y on the trailing 30-day return over all days."""
    P = fng_panel(px, fng, H)
    if P["y"].size < 10:
        return {"raw": np.array([]), "residual": np.array([]), "n": 0}
    ev = set(fng_events(fng, kind, thr, H)["kept"])
    m = np.array([s in ev for s in P["sig"]])
    X = np.column_stack([np.ones(P["x"].size), P["x"]])
    a, b = np.linalg.lstsq(X, P["y"], rcond=None)[0]
    return {"raw": P["y"][m] - P["y"].mean(), "residual": P["y"][m] - (a + b * P["x"][m]), "n": int(m.sum())}


def fear_greed_study(btc: dict, eth: Optional[dict], fng: dict, min_n: int = T416_MIN_N, n_boot: Optional[int] = None,
                     seed: int = SEED, grid: bool = True) -> dict:
    """T-416 core. ``btc``/``eth``: {day: close}; ``fng``: {day: (F, available_at)}."""
    P = fng_panel(btc, fng, T416_H)
    E = fng_events(fng, "first", T416_THR, T416_H)
    ev = set(E["kept"])
    drop = set(E["all"]) - ev                                       # crossings that overlap a kept event leave the sample
    keep = np.array([s not in drop for s in P["sig"]])
    sig = [s for s, k in zip(P["sig"], keep) if k]
    y, x = P["y"][keep], P["x"][keep]
    I = np.array([1.0 if s in ev else 0.0 for s in sig])
    n_ev = int(I.sum())
    tests = {blk: _mc(lambda seed, blk=blk: coef_test(y, I, x, blk, n_boot, seed),
                      lambda t: resolve(t["p"], t.get("p_mc_se", 0.0), 0.05, "lt")[0], seed, keys=("ci",))
             for blk in T416_BLOCKS} if n_ev >= 2 else {}
    coef = float(_ols3(y, I, x)[1]) if n_ev >= 1 else None

    def coef_row():
        if not tests:
            return ("indicator coefficient >= 5 points with one-sided bootstrap p < 0.05 (fewer than 2 events)", None, False)
        rows = []
        for blk, t in tests.items():
            p_ok, note = resolve(t["p"], t.get("p_mc_se", 0.0), 0.05, "lt")
            up, up_se = t["ci"][1], (t.get("ci_mc_se") or [0.0, 0.0])[1]
            ok = None if p_ok is None else bool(t["coef"] >= T416_EFFECT and p_ok)
            dec = resolve(up, up_se, T416_EFFECT, "lt")[0] is True
            nm = f"{blk}-day blocks: p {t['p']:.4f}{note}, one-sided 95% upper bound {_pc(up, 1)}"
            rows.append((nm, ok, dec))
        nm, ok, dec = all_constructions(rows, f"coefficient {_pc(coef, 2)} >= 5 points with one-sided stationary-bootstrap p < 0.05")
        if ok is False and not dec:
            return nm + " [non-rejection not decisive: recorded as underpowered (trial power note)]", None, False
        return nm, ok, dec

    cells, fam_sr = {}, []
    if grid:
        for asset, px in (("BTC", btc), ("ETH", eth)):
            if px is None:
                continue
            for H in T416_HS:
                for thr in T416_THRS:
                    for kind in ("first", "level"):
                        ce = _cell_events(px, fng, kind, thr, H)
                        for meas in ("raw", "residual"):
                            e = ce[meas]
                            key = f"{asset}|H{H}|{thr}|{kind}|{meas}"
                            cells[key] = {"n": int(e.size), "mean": float(e.mean()) if e.size else None, "sharpe": _sr_pp(e) if e.size > 2 else None}
                            fam_sr.append(cells[key]["sharpe"])
    prim = _cell_events(btc, fng, "first", T416_THR, T416_H)["residual"]
    ds = dsr_family(prim, fam_sr, T416_N_CELLS) if prim.size > 3 else {"dsr": None, "psr0": None, "n_trials": T416_N_CELLS, "var_trials_sr": 0.0}
    subs = {}
    for a, b in T416_SUBS:
        m = np.array([a <= s <= b for s in sig])
        ne = int(I[m].sum())
        subs[f"{a[:4]}-{b[2:4]}"] = {"coef": float(_ols3(y[m], I[m], x[m])[1]) if ne >= 1 else None, "events": ne}
    sub_ok = None if any(v["coef"] is None for v in subs.values()) else all(v["coef"] > 0 for v in subs.values())
    crit = [coef_row(),
            dsr_row(ds, f"DSR >= {DSR_PASS} of the primary cell's per-event residual returns over the {T416_N_CELLS} cells",
                    decisive_only=True),
            ("same (positive) sign in 2018-21 and 2022-26 (" + ", ".join(f"{k} {_pc(v['coef'], 1)} on {v['events']} events" for k, v in subs.items()) + ")",
             sub_ok, False)]
    v, why = _decide(crit, n_ev, min_n, "non-overlapping first-crossing events at H = 30")
    label = "underpowered" if any(c[1] is None and "underpowered" in c[0] for c in crit) else None
    return {"label": label, "n_events": n_ev, "n_crossings": len(E["all"]), "events": E["kept"], "n_days": int(y.size), "coef": coef,
            "tests": {str(k): {kk: t.get(kk) for kk in ("coef", "p", "p_mc_se", "ci", "ci_mc_se", "n_boot", "reps")} for k, t in tests.items()},
            "dsr": ds, "cells": cells, "subsamples": subs, "uncond_mean": float(y.mean()) if y.size else None,
            "event_mean_raw": float(y[I == 1].mean()) if n_ev else None, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def rule_sharpe(btc: dict, fng: dict, bills: Optional[Bills], events: Sequence[str], H: int = T416_H, rt_cost: float = 0.01) -> dict:
    """Long BTC from the entry close for H days or until F >= 50 (known the next day, sold at that day's close); cash
    otherwise; ``rt_cost`` per round trip. Annualised excess Sharpe (365) of the rule and of buy-and-hold."""
    days = sorted(btc)
    if len(days) < 30:
        return {}
    c = np.array([btc[d] for d in days])
    ix = {d: i for i, d in enumerate(days)}
    pos = np.zeros(len(days))
    for t in events:
        e = ix.get(_entry(t))
        if e is None:
            continue
        stop = min(e + H, len(days) - 1)
        for j in range(e + 1, min(e + H, len(days) - 1) + 1):
            f = fng.get(days[j - 1])
            if f is not None and (f[0] if isinstance(f, tuple) else f) >= 50 and days[j - 1] > days[e]:
                stop = j
                break
        pos[e + 1:stop + 1] = 1.0
    r = np.r_[0.0, c[1:] / c[:-1] - 1.0]
    rf = np.r_[0.0, [bills.growth(days[i - 1], days[i]) - 1.0 for i in range(1, len(days))]] if bills else np.zeros(len(days))
    ent = np.r_[0.0, np.maximum(np.diff(pos), 0)]
    ex = pos * (r - rf) - rt_cost * ent
    lo = ix.get(_entry(min(fng))) or 0
    return {"rule": _sr_ann(ex[lo:], 365.0), "bh": _sr_ann((r - rf)[lo:], 365.0), "days_in": int(pos[lo:].sum())}


def b6c_misc_fear_greed_extremes(archive):
    """T-416."""
    need = [FNG_B, dh("BTC-USD")]
    miss = _missing(archive, need)
    if miss:
        return miss
    b = _daily(archive, dh("BTC-USD"))
    btc = _close_map(b["days"], b["close"])
    eth = None
    if _has(archive, dh("ETH-USD")):
        e = _daily(archive, dh("ETH-USD"))
        eth = _close_map(e["days"], e["close"])
    fng = _fng(archive)
    j = fear_greed_study(btc, eth, fng)
    bills = _bills(archive) if _has(archive, DTB3_B) else None
    rs = {c: rule_sharpe(btc, fng, bills, j["events"], rt_cost=c) for c in (0.005, 0.012)}
    t30, t60 = j["tests"].get("30", {}), j["tests"].get("60", {})
    ds = j["dsr"]
    reason = (f"alternative.me F&G {min(fng)}..{max(fng)} ({len(fng)} days; F for day t known at 00:00 UTC on t+1), BTC-USD "
              f"bought at the close of t+1: {j['n_crossings']} first crossings to <= 20 (F > 20 the previous day, none in the "
              f"prior 10 days), {j['n_events']} non-overlapping at 30 days. Regression of the 30-day forward log return on the "
              f"event indicator and the trailing 30-day log return over {j['n_days']} daily entry rows: coefficient "
              f"{_pc(j['coef'], 2)} (event raw mean {_pc(j['event_mean_raw'], 2)} vs unconditional {_pc(j['uncond_mean'], 2)}); "
              f"one-sided stationary-bootstrap percentile p = P(b* <= 0) {_f(t30.get('p'), 4)} (30-day blocks) / {_f(t60.get('p'), 4)} "
              f"(60-day blocks, rule 10), one-sided 95% percentile upper bounds {_pc((t30.get('ci') or [None, None])[1], 1)} / "
              f"{_pc((t60.get('ci') or [None, None])[1], 1)} ({T416_BOOT} draws "
              f"x {REPS} seeds). DSR of the primary cell's per-event residual returns {_f(ds.get('dsr'))} at {T416_N_CELLS} cells "
              f"(PSR vs 0 {_f(ds.get('psr0'))}; {sum(1 for c in j['cells'].values() if c['sharpe'] is not None)} cells computed). "
              f"Subsamples: " + ", ".join(f"{k} {_pc(v['coef'], 1)} ({v['events']} events)" for k, v in j["subsamples"].items())
              + f". Rule (30 days or F >= 50) excess Sharpe {_s(rs[0.005].get('rule'), 2)} at 0.5% / {_s(rs[0.012].get('rule'), 2)} "
              f"at 1.2% round trip vs buy-and-hold {_s(rs[0.005].get('bh'), 2)} (reported). Caveat: the F&G file is one current "
              f"download (no vintages) — " + j["why"])
    stat = {"label": j["label"], "n_events": j["n_events"], "n_crossings": j["n_crossings"], "events": j["events"], "n_days": j["n_days"],
            "coef": j["coef"], "tests": j["tests"], "dsr": ds, "subsamples": j["subsamples"], "cells": j["cells"],
            "uncond_mean": j["uncond_mean"], "event_mean_raw": j["event_mean_raw"],
            "rule_sharpe": {str(k): v for k, v in rs.items()}, "criteria": j["criteria"],
            "rule10": "event study; the regression uses every entry day (all-start), bootstrapped with 30- and 60-day blocks"}
    return _out(stat, j["n_events"], j["verdict"], reason)


# ============================================================================ T-484 bond TSMOM, FRED history ==

T484_MIN_N = 700
T484_START = "1963-01"
T484_END = "2026-09"
T484_COST = 2e-4
T484_BLOCK = 12
T484_CORR = 0.95
T484_SUBS = (("1963-01", "1981-12"), ("1982-01", "2020-12"), ("2021-01", "2026-12"))
T484_FAMILY = tuple((m, pos, lb) for m in (10, 2) for pos in ("LS", "LF") for lb in (12, 6))   # 8 declared trials
T484_PRIMARY = (10, "LS", 12)


def par_bond_dc(y_pct: float, maturity: int = 10) -> tuple:
    """Modified duration and convexity of a par bond with semiannual coupons at yield y (percent)."""
    y = max(y_pct / 100.0, 1e-6)
    n = 2 * maturity
    k = np.arange(1, n + 1, dtype=float)
    cf = np.full(n, y / 2.0)
    cf[-1] += 1.0
    v = 1.0 / (1.0 + y / 2.0)
    pv = cf * v ** k
    P = pv.sum()
    D = float((k / 2.0 * pv).sum() / P * v)
    C = float((pv * k * (k + 1) / 4.0).sum() * v ** 2 / P)
    return D, C


def synthetic_returns(y_pct, maturity: int = 10) -> np.ndarray:
    """Monthly total return of a constant-maturity par bond from month-end yields (percent): y_{t-1}/12 - D dy + C dy^2/2
    with D and C at y_{t-1}."""
    y = np.asarray(y_pct, float)
    out = np.full(y.size, np.nan)
    for t in range(1, y.size):
        if np.isfinite(y[t]) and np.isfinite(y[t - 1]):
            D, C = par_bond_dc(y[t - 1], maturity)
            dy = (y[t] - y[t - 1]) / 100.0
            out[t] = y[t - 1] / 100.0 / 12.0 - D * dy + 0.5 * C * dy * dy
    return out


def month_end_yields(fred: dict, cutoff_days: int = 1) -> dict:
    """{month: (day, value)} of the last print of each month whose available_at is within ``cutoff_days`` of its day."""
    out = {}
    for d in sorted(fred):
        v, av = fred[d] if isinstance(fred[d], tuple) else (fred[d], d)
        if (av or d)[:10] <= (date.fromisoformat(d) + timedelta(days=cutoff_days)).isoformat():
            out[d[:7]] = (d, float(v))
    return out


def bond_series(fred10: dict, bills: Bills, fred2: Optional[dict] = None) -> dict:
    """Monthly synthetic 10-year (and 2-year) excess returns over DTB3 accrued between the month-end print days."""
    me10 = month_end_yields(fred10)
    months = sorted(me10)
    full, m = [], months[0]
    while m <= months[-1]:
        full.append(m)
        m = _month_add(m, 1)
    out = {}
    for mat, me in ((10, me10), (2, month_end_yields(fred2) if fred2 else {})):
        y = np.array([me[k][1] if k in me else np.nan for k in full])
        dd = [me[k][0] if k in me else None for k in full]
        r = synthetic_returns(y, mat)
        bill = np.array([bills.growth(dd[i - 1], dd[i]) - 1.0 if i > 0 and dd[i] and dd[i - 1] else np.nan for i in range(len(full))])
        out[mat] = {"r": r, "bill": bill, "x": r - bill, "y": y}
    return {"months": full, **out}


def tsmom_vs_hist(x: np.ndarray, months: Sequence[str], pos: str, lb: int, cost: float = T484_COST,
                  start: str = T484_START, end: str = T484_END) -> dict:
    """Monthly d = r(TSMOM) - r(historical mean) on an excess-return series: at month-end t, TSMOM = sign of the
    cumulative excess return over months t-lb+1 .. t-1 (lb-1 skip; long/short or long/flat); historical mean = sign of
    the expanding mean of the series' monthly excess returns through t (from its first month). Net of ``cost`` per side
    on |change in position|; held over month t+1."""
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    first = int(np.argmax(ok)) if ok.any() else len(x)
    lab, rt, rh, wt_l, wh_l = [], [], [], [], []
    wt_prev = wh_prev = 0.0
    cs = np.cumsum(np.where(ok, x, 0.0))
    cnt = np.cumsum(ok.astype(float))
    for t in range(first + lb - 1, len(x) - 1):
        seg = x[t - lb + 1:t]                               # months t-lb+1 .. t-1 (the most recent month skipped)
        if seg.size != lb - 1 or not np.isfinite(seg).all() or not np.isfinite(x[t + 1]):
            continue
        cum = float(np.prod(1.0 + seg) - 1.0)
        wt = (1.0 if cum > 0 else -1.0) if pos == "LS" else (1.0 if cum > 0 else 0.0)
        hm = cs[t] / cnt[t] if cnt[t] > 0 else 0.0
        wh = (1.0 if hm > 0 else -1.0) if pos == "LS" else (1.0 if hm > 0 else 0.0)
        lab_t = months[t + 1]
        r_t = wt * x[t + 1] - cost * abs(wt - wt_prev)
        r_h = wh * x[t + 1] - cost * abs(wh - wh_prev)
        wt_prev, wh_prev = wt, wh
        if not (start <= lab_t <= end):
            continue
        lab.append(lab_t)
        rt.append(r_t)
        rh.append(r_h)
        wt_l.append(wt)
        wh_l.append(wh)
    rt, rh = np.array(rt), np.array(rh)
    return {"labels": lab, "tsmom": rt, "hist": rh, "d": rt - rh, "w_t": np.array(wt_l), "w_h": np.array(wh_l)}


def bond_tsmom(S: dict, ief: Optional[tuple] = None, bills: Optional[Bills] = None, min_n: int = T484_MIN_N,
               n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-484 core on ``bond_series`` output. ``ief``: (days, adjclose) for the validation."""
    nb = T484_BOOT if n_boot is None else int(n_boot)
    months = S["months"]
    fam = {}
    for v in T484_FAMILY:
        mat, pos, lb = v
        if mat in S and np.isfinite(S[mat]["x"]).sum() > 24:
            fam[v] = tsmom_vs_hist(S[mat]["x"], months, pos, lb)
    P = fam[T484_PRIMARY]
    d = P["d"]
    n = d.size
    mt = _mc(lambda seed: _stud(_mean_stat, [d], T484_BLOCK, nb, seed),
             lambda t: resolve(t["ci"][0], (t.get("ci_mc_se") or [0, 0])[0], 0.0, "gt")[0], seed) if n >= 8 else {"est": None, "ci": [None, None]}
    lo, hi = mt.get("ci") or [None, None]
    se_lo, se_hi = mt.get("ci_mc_se") or [0.0, 0.0]
    ok1, note1 = resolve(lo, se_lo, 0.0, "gt")
    d_d = dsr_family(d, [_sr_pp(f["d"]) for f in fam.values()], len(T484_FAMILY))
    d_s = dsr_family(P["tsmom"], [_sr_pp(f["tsmom"]) for f in fam.values()], len(T484_FAMILY))
    subs = {}
    for a, b in T484_SUBS:
        m = np.array([a <= l <= b for l in P["labels"]])
        subs[f"{a[:4]}-{b[:4]}"] = {"mean": float(d[m].mean()) if m.any() else None, "n": int(m.sum())}
    npos = sum(1 for v in subs.values() if v["mean"] is not None and v["mean"] > 0)
    nknown = sum(1 for v in subs.values() if v["mean"] is not None)
    sub_ok = True if npos >= 2 else (False if npos + (3 - nknown) < 2 else None)
    val = {}
    if ief is not None and bills is not None:
        idays, iadj = ief
        last = {}
        for dd, a in zip(idays, iadj):
            last[dd[:7]] = (dd, a)
        im = sorted(last)
        ir = {}
        for k in range(1, len(im)):
            if _month_add(im[k - 1], 1) == im[k]:
                d0, a0 = last[im[k - 1]]
                d1, a1 = last[im[k]]
                ir[im[k]] = a1 / a0 - 1.0 - (bills.growth(d0, d1) - 1.0)
        mi = {m: i for i, m in enumerate(months)}
        pairs = [(S[10]["x"][mi[m]], ir[m]) for m in sorted(ir) if m in mi and np.isfinite(S[10]["x"][mi[m]]) and m <= T484_END]
        if len(pairs) >= 24:
            a_, b_ = np.array(pairs).T
            val = {"months": len(pairs), "corr": float(np.corrcoef(a_, b_)[0, 1]), "te_ann": float(np.std(a_ - b_, ddof=1) * math.sqrt(12)),
                   "first": min(m for m in ir if m in mi)}
    crit = [(f"mean d > 0 with the studentized CBB ({T484_BLOCK}-month blocks) 95% CI excluding 0 (mean {_bp(mt.get('est'))}/month, "
             f"lower {_bp(lo)}){note1}", ok1, hi is not None and resolve(hi, se_hi, 0.0, "lt")[0] is True),
            all_constructions([dsr_row(d_d, "difference series d"), dsr_row(d_s, "TSMOM excess-return series")],
                              f"DSR > {DSR_PASS} over the {len(T484_FAMILY)} declared trials under both readings"),
            (f"d > 0 in at least 2 of 3 sub-periods (" + ", ".join(f"{k} {_bp(v['mean'])} over {v['n']} months" for k, v in subs.items()) + ")",
             sub_ok, False),
            (f"synthetic 10-year excess return vs IEF adjclose excess return monthly correlation > {T484_CORR} "
             f"({_f(val.get('corr'))} over {val.get('months', 0)} months)" if val else "synthetic-vs-IEF validation (IEF not available)",
             (val["corr"] > T484_CORR) if val else None, False)]
    v, why = _decide(crit, n, min_n, "months")
    return {"n": int(n), "window": (P["labels"][0], P["labels"][-1]) if n else None, "mean": mt, "dsr_d": d_d, "dsr_tsmom": d_s,
            "subs": subs, "validation": val, "sharpe_tsmom": _sr_ann(P["tsmom"], 12), "sharpe_hist": _sr_ann(P["hist"], 12),
            "share_long_t": float(np.mean(P["w_t"] > 0)) if n else None, "share_long_h": float(np.mean(P["w_h"] > 0)) if n else None,
            "family": {"|".join(map(str, k)): {"n": int(f["d"].size), "mean_d": float(f["d"].mean()) if f["d"].size else None,
                                               "sharpe_tsmom": _sr_ann(f["tsmom"], 12)} for k, f in fam.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_misc_bond_tsmom_fred(archive):
    """T-484."""
    need = [DGS10_B, DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    S = bond_series(_fred_avail(archive, DGS10_B), bills, _fred_avail(archive, DGS2_B) if _has(archive, DGS2_B) else None)
    ief = None
    if _has(archive, dh("IEF")):
        i = _daily(archive, dh("IEF"))
        ief = (i["days"], i["adj"])
    j = bond_tsmom(S, ief, bills)
    mt, val = j["mean"], j["validation"]
    reason = (f"Synthetic constant-maturity 10-year par-bond monthly total return from fred-DGS10 month-end prints (carry "
              f"y/12 - D dy + C dy^2/2, D and C of a semiannual par bond at the prior yield) minus DTB3 accrued between the "
              f"print days; at month-end t the 12-1 long/short TSMOM takes the sign of months t-11..t-1, the historical-mean "
              f"strategy the sign of the expanding mean since 1962-02; 2 bps per side; hold months {j['window'][0]}..{j['window'][1]} "
              f"({j['n']} months). Mean d {_bp(mt.get('est'))}/month ({_ci(mt.get('ci'), 1, 1e4, ' bp')}, studentized CBB, "
              f"{T484_BLOCK}-month blocks, {T484_BOOT} draws x {REPS}+ seeds); excess Sharpe TSMOM {_s(j['sharpe_tsmom'])} vs "
              f"historical mean {_s(j['sharpe_hist'])} (TSMOM long in {j['share_long_t'] * 100:.0f}%, historical mean long in "
              f"{j['share_long_h'] * 100:.0f}% of months); DSR at 8 trials: d {_f(j['dsr_d']['dsr'])}, TSMOM series "
              f"{_f(j['dsr_tsmom']['dsr'])}; sub-periods " + ", ".join(f"{k} {_bp(v['mean'])} ({v['n']} m)" for k, v in j["subs"].items())
              + (f"; synthetic vs IEF excess returns from {val['first']}: correlation {val['corr']:.3f} over {val['months']} months, "
                 f"tracking error {_pc(val['te_ann'])}/yr" if val else "; IEF validation not run")
              + ". Family (mean d, bp/month): " + ", ".join(f"{k} {_bp(v['mean_d'])}" for k, v in j["family"].items())
              + " — " + j["why"])
    stat = {"n_months": j["n"], "window": j["window"], "mean_d": mt.get("est"), "ci": mt.get("ci"), "ci_mc_se": mt.get("ci_mc_se"),
            "dsr_d": j["dsr_d"], "dsr_tsmom": j["dsr_tsmom"], "subperiods": j["subs"], "validation": val,
            "sharpe_tsmom": j["sharpe_tsmom"], "sharpe_hist": j["sharpe_hist"], "family": j["family"], "criteria": j["criteria"],
            "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_misc_ta_reality_check": b6c_misc_ta_reality_check,
    "b6c_misc_gold_silver_ratio": b6c_misc_gold_silver_ratio,
    "b6c_misc_es_basis": b6c_misc_es_basis,
    "b6c_misc_fear_greed_extremes": b6c_misc_fear_greed_extremes,
    "b6c_misc_bond_tsmom_fred": b6c_misc_bond_tsmom_fred,
    "b6c_misc_metals_basis": b6c_misc_metals_basis,
}

THEORY_MAP = {
    "T-318": "b6c_misc_ta_reality_check",
    "T-326": "b6c_misc_gold_silver_ratio",
    "T-372": "b6c_misc_es_basis",
    "T-416": "b6c_misc_fear_greed_extremes",
    "T-484": "b6c_misc_bond_tsmom_fred",
    "T-370": "b6c_misc_metals_basis",
}
