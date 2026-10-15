"""
Batch 6c, group ``mom``: seven ETF momentum / trend / time-series-momentum claims on archived daily adjclose histories.
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-300  pooled 12-1 long/flat TSMOM minus the Huang-Li-Wang-Zhou historical-mean strategy on SPY, QQQ, GLD, SLV, EFA,
           AGG, TLT, DBC, BTC-USD, ETH-USD, 2000-01..: mean d > 0 (studentized CBB 95% CI, 12-month blocks), DSR(d) > 0.95
           at 104 trials (the 56-trial declared grid plus T-58's 48), post-2012 mean d >= 0 (a negative one = 'decayed').
  * T-301  SPY 10-month SMA long/flat, 1994-01..: maximum drawdown below the 5th percentile of spell-preserving random
           in/out paths (the claim's 1,000 paths; Holm over the 96 declared variants) and the Sharpe difference vs buy-and-
           hold with a lower 95% bound > -0.15.
  * T-308  top-3 residual momentum (36-month SPY betas) vs top-3 12-2 total-return momentum on the 9 original SPDRs:
           paired Sharpe difference CI > 0 and DSR > 0.95 over the 8 declared trials; rank-correlation power label.
  * T-310  difference-in-differences of the Sharpe gain from volatility scaling, TSMOM long/flat vs buy-and-hold, pooled
           over SPY, QQQ, GLD, SLV, EFA, TLT, BTC-USD, ETH-USD on daily returns: joint 60-day block bootstrap CI > 0, Holm
           over the 20 declared trials, positive in >= 2 of 3 decades.
  * T-311  bear-and-high-vol filter on the long/short 3/3 12-1 sector-SPDR portfolio, 2000-01..: worst rolling 3-month
           return better than 95% of 1,000 spell-preserving random filters (Holm over 24 trials), Sharpe difference lower
           bound > -0.1, >= 5 distinct activation episodes (fewer = inconclusive).
  * T-317  equal-risk 12-1 TSMOM long/short on 8 ETF sleeves: excess quadratic coefficient on quarterly SPY excess return
           over the mean coefficient of 1,000 driftless i.i.d.-by-month simulations, 95% CI > 0 (block bootstrap AND HAC),
           Holm over 8 trials, sign kept leaving out each of 4 crises.
  * T-481  SPY cross-asset long/flat rule max(0, (e + b)/2) vs SPY's own 12-1 long/flat TSMOM, 1994-02..: paired Sharpe
           difference CI > 0, DSR > 0.95 over 12 trials, placebo (bond signal lagged 12 months) CI includes 0.

Conventions
  * Data. ``daily-history-<SYM>`` bundles through ``archive.load``; a row is used only when its ``available_at`` is not
    after the bundle's capture time. Prices are Yahoo ``adjclose`` (split and dividend adjusted: total return); open/high/
    low are put on the same basis (x adjclose / close) for the Yang-Zhang estimator. ETF bars are keyed by their session
    date; crypto bars by the UTC calendar day (close 24:00 UTC).
  * Calendars (rule 10(a)). Every claim here names month-end rebalancing (its library rule: "at month-end t ... execute at
    the close of the first trading day of t+1"), so the decision is the month's last session close (crypto: the last
    calendar day) and the fill is the close of the next session (crypto: the next calendar day); a hold runs fill-to-fill.
    There is no free grid phase, so no pooled all-start estimator is needed. T-317's quarters are calendar quarters of the
    hold months. A month enters only when its hold is complete (the following month's fill exists).
  * Point in time (rules 4, 12). A daily bar is available the next day (available_at = bar + 24h), before the fill
    session's close; the signal, the volatility estimate and the fill price used at one decision are all known at that
    fill close (one information set). FRED prints are used on the day after their observation date at the earliest
    (Bills), DGS10 only when its available_at precedes the fill.
  * Bills and Sharpe (rule 7). FRED DTB3 is a 91-day discount yield: r = -ln(1 - d/100 x 91/360)/(91/365), accrued
    calendar day by calendar day at the print dated strictly before the day (batch6b_bw.Bills). Idle ETF cash earns it;
    crypto flat means USD (0), as the TSMOM library entry states. Sharpe ratios are on excess returns (mean/sd x sqrt(12)
    monthly, sqrt(252) for T-310's daily ETF calendar).
  * Costs (rule 9) as each claim states, charged on every change in weight (drift-adjusted turnover): T-300/T-310 2 bps
    per side SPY/QQQ, 5 bps other ETFs, 25 + 10 bps crypto; T-301 2 bps SPY, 5 bps other sleeves per switch; T-308 5 bps;
    T-311 5 bps plus 50 bps/yr borrow on shorts; T-317 5 bps plus 50 bps/yr borrow; T-481 2 bps.
  * Intervals (rule 6). Paired studentized circular block bootstrap (12-month blocks, 5,000 resamples per seed, the mean of
    5 seeds with Monte Carlo s.e.; batch6b_bw.sharpe_diff_test / _stud) for monthly means and Sharpe differences; T-310 a
    joint circular block bootstrap of the four daily series (60-day blocks, percentile); T-317 a circular block bootstrap
    of the quarterly regression pairs (4-quarter blocks, percentile) and a Newey-West HAC t (both named: rule 11). "CI
    excluding 0" is the two-sided 95% interval. Rule 11: where a trial names two constructions both must pass.
  * Families. Every Holm or DSR family is listed below exactly as the trial declares it, before any result: T-300 56 grid
    trials (+48 T-58 trials in the DSR count only), T-301 96, T-308 8, T-310 20, T-311 24, T-317 8, T-481 12. Where the
    trial's "DSR" could mean the strategy's own excess-return series or the paired difference series (T-308, T-481), both
    are computed and the criterion needs both (rule 11 spirit: a pass must not hinge on the reading).
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import (Bills, _ci_crit, _clean, _decide, _mean_stat, _stud, all_constructions,
                                           mc_escalate, resolve, sharpe_diff_test)
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, probabilistic_sharpe_ratio, sharpe_ratio, skewness, kurtosis

N_BOOT = 5000                  # the trials' 5,000 bootstrap draws
REPS = 5                       # bootstrap seeds behind every decisive interval end
SEED = 0
BLOCK = 12                     # months
PPY = 12
DSR_PASS = 0.95
ALPHA = 0.05

DTB3_B = "fred-DTB3"
DGS10_B = "fred-DGS10"
VIX_B = "cboe-VIX-history"
DVOL_B = "deribit-dvol-BTC-history"
CRYPTO = ("BTC-USD", "ETH-USD")
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def dh(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def _cost(sym: str, etf_big: float = 2e-4, etf: float = 5e-4, crypto: float = 35e-4) -> float:
    """Per-side cost of the TSMOM entries: 2 bps SPY/QQQ, 5 bps other ETFs, 25 + 10 bps crypto."""
    if sym in CRYPTO:
        return crypto
    return etf_big if sym in ("SPY", "QQQ") else etf


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
    """{'days', 'close', 'adj', 'open', 'high', 'low'} of a Yahoo daily bundle; O/H/L on the adjclose basis; a bar without
    adjclose carries the previous adjclose/close ratio."""
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
            ohl = []
            for k in ("open", "high", "low"):
                try:
                    x = float(v.get(k))
                    ohl.append(x if x > 0 and math.isfinite(x) else float("nan"))
                except (TypeError, ValueError):
                    ohl.append(float("nan"))
            by[d] = (c, a, *ohl)
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 5)
        close, adj = arr[:, 0], arr[:, 1].copy()
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        f = adj / close
        return {"days": days, "close": close, "adj": adj, "open": arr[:, 2] * f, "high": arr[:, 3] * f, "low": arr[:, 4] * f}
    return _cached(archive, ("daily", name), load)


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED (value) or Cboe/Deribit (close) bundle; non-numeric prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = v.get("value", v.get("close"))
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            d = v.get("day")
            if d is None and v.get("ts_ms") is not None:
                d = datetime.fromtimestamp(float(v["ts_ms"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if math.isfinite(x) and d:
                out[d] = x
        return out
    return _cached(archive, ("series", name), load)


def _fred_avail(archive, name: str) -> dict:
    """{day: (value, available_at)} of a FRED bundle."""
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


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_series(archive, DTB3_B)))


# ============================================================================================ calendars, bills ==

def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def bill_logcum(bills: Bills, days: Sequence[str]) -> np.ndarray:
    """Cumulative continuous bill accrual (log growth) at each day, so growth(d_i -> d_j) = exp(C[j] - C[i]); the same
    accrual as Bills.growth (rate known on each calendar day = the print dated strictly before it)."""
    o = np.array([_ord(d) for d in days], np.int64)
    lo, hi = bills.lo, bills.hi
    k = np.clip(o - lo, 0, hi - lo)
    c = bills.cum[k].astype(float)
    c = np.where(o <= lo, (o - lo) * float(bills.r[0]) / 365.0, c)
    c = np.where(o > hi, float(bills.cum[hi - lo]) + (o - hi) * float(bills.r[-1]) / 365.0, c)
    return c


def month_grid(days: Sequence[str]) -> dict:
    """Decision months of a daily calendar: for each month with a later bar, 'me' = index of its last bar (the decision
    close) and 'ex' = index of the next bar (the fill close). A hold for decision t runs ex[t] -> ex[t + 1]."""
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    ms = [m for m in sorted(last) if last[m] + 1 < len(days)]
    me = np.array([last[m] for m in ms], int)
    return {"months": ms, "me": me, "ex": me + 1}


def _month_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def drift_turnover(w: np.ndarray, R: np.ndarray, port_pre: np.ndarray) -> np.ndarray:
    """Turnover at each rebalance of target weights w (..., n, k) on asset hold returns R (..., n, k): sum |w_t -
    w_{t-1} (1 + R_{t-1}) / (1 + port_{t-1})|, with an empty book before the first period."""
    prev = np.zeros_like(w)
    den = (1.0 + port_pre)[..., :-1, None]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    prev[..., 1:, :] = w[..., :-1, :] * (1.0 + R[..., :-1, :]) / den
    return np.abs(w - prev).sum(axis=-1)


def _net_single(w: np.ndarray, R: np.ndarray, rf: np.ndarray, cost: float) -> np.ndarray:
    """Net return of a single-asset position path w (asset weight, the rest in cash at rf; negative = short with the
    collateral earning rf): rf + w (R - rf) - cost x drift-adjusted turnover."""
    pre = rf + w * (R - rf)
    to = drift_turnover(w[:, None], R[:, None], pre)
    return pre - cost * to


# =============================================================================================== statistics ==

def mean_test(x, n_boot: Optional[int] = None, seed: int = SEED, reps: Optional[int] = None, block: int = BLOCK) -> dict:
    """Studentized circular block bootstrap of a mean (Bartlett-HAC s.e., bandwidth = block): est, two-sided 95% CI with
    Monte Carlo s.e. over ``reps`` seeds, p (H0: mean <= 0)."""
    nb = N_BOOT if n_boot is None else n_boot
    x = np.asarray(x, float)
    return mc_escalate(lambda seed: _stud(_mean_stat, [x], block, nb, seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1],
                       REPS if reps is None else reps, seed)


def sharpe_test(a, b, n_boot: Optional[int] = None, seed: int = SEED, reps: Optional[int] = None, block: int = BLOCK,
                thr: float = 0.0) -> dict:
    """Annualised Sharpe(a) - Sharpe(b) with the paired studentized CBB (batch6b_bw.sharpe_diff_test), interval ends
    averaged over ``reps`` seeds (escalated when they cannot resolve against ``thr``)."""
    nb = N_BOOT if n_boot is None else n_boot
    a, b = np.asarray(a, float), np.asarray(b, float)
    return mc_escalate(lambda seed: sharpe_diff_test(a, b, PPY, block, nb, seed), lambda t: _ci_crit(t, "gt", thr, "")[1],
                       REPS if reps is None else reps, seed)


def family_dsr(x, family_sharpes: Sequence[float], n_trials: int) -> dict:
    """DSR of ``x`` against the best of ``n_trials`` trials, trial-Sharpe variance from the computed family (per-period
    Sharpes), floored at 1/(T-1); the PSR against a zero Sharpe decides a failure (one-sided 95%: <= 0.05)."""
    x = np.asarray(x, float)
    fs = np.array([s for s in family_sharpes if s is not None and math.isfinite(s)], float)
    v = float(fs.var(ddof=1)) if fs.size > 1 else 0.0
    v = max(v, 1.0 / max(1, x.size - 1))
    dsr = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=v)) if x.size > 3 else None
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1)) if x.size > 3 else None
    return {"dsr": dsr, "psr0": psr0, "var_trials_sr": v, "n_trials": int(n_trials), "n_family_computed": int(fs.size),
            "sharpe_per_period": float(sharpe_ratio(x)) if x.size > 1 else None}


def dsr_row(d: dict, label: str) -> tuple:
    """(name, ok, decisive) for 'DSR > 0.95'; decisive when the PSR against a zero Sharpe is <= 0.05."""
    if d.get("dsr") is None:
        return f"{label} (n/a)", None, False
    return (f"{label} ({d['dsr']:.3f} at {d['n_trials']} trials, var(trial SR) {d['var_trials_sr']:.2e})",
            d["dsr"] > DSR_PASS, d["psr0"] is not None and d["psr0"] <= 1.0 - DSR_PASS)


def holm_adjusted(ps: dict) -> dict:
    """Holm step-down adjusted p for every key of {key: p} (all finite)."""
    keys = sorted(ps, key=lambda k: ps[k])
    m = len(keys)
    out, run = {}, 0.0
    for j, k in enumerate(keys):
        run = max(run, min(1.0, (m - j) * float(ps[k])))
        out[k] = run
    return out


def holm_primary(ps: dict, key) -> dict:
    """Holm-adjusted p of ``key`` in the family {key: p or None}. With every p known it is exact; with some unknown
    (None) it is bounded: lower = the unknowns ranked last, upper = m x p (Holm never exceeds Bonferroni)."""
    m = len(ps)
    known = {k: v for k, v in ps.items() if v is not None and math.isfinite(v)}
    p0 = ps.get(key)
    if p0 is None or not math.isfinite(p0):
        return {"adj": None, "lo": None, "hi": None, "m": m, "n_known": len(known)}
    if len(known) == m:
        a = holm_adjusted(known)[key]
        return {"adj": a, "lo": a, "hi": a, "m": m, "n_known": m}
    # the adjusted p is at least the primary's own term (m - r + 1) p0 at its largest possible rank r (every unknown p
    # ranked before it), and never above Bonferroni m p0
    r_max = 1 + sum(1 for k, v in known.items() if k != key and v <= p0) + (m - len(known))
    lo = max(p0, p0 * (m - r_max + 1))
    return {"adj": None, "lo": float(min(1.0, lo)), "hi": float(min(1.0, m * p0)), "m": m, "n_known": len(known)}


def holm_row(h: dict, label: str, level: float = ALPHA) -> tuple:
    if h["adj"] is not None:
        return f"{label} (Holm-adjusted p {h['adj']:.4f} over {h['m']} trials)", h["adj"] < level, h["adj"] >= level
    if h["hi"] is not None and h["hi"] < level:
        return f"{label} (Holm-adjusted p <= {h['hi']:.4f}, {h['n_known']}/{h['m']} trials computed)", True, False
    if h["lo"] is not None and h["lo"] >= level:
        return f"{label} (Holm-adjusted p >= {h['lo']:.4f}, {h['n_known']}/{h['m']} trials computed)", False, True
    return f"{label} (Holm-adjusted p not resolved: {h['n_known']}/{h['m']} trials computed)", None, False


def mdd_depth(r: np.ndarray) -> np.ndarray:
    """Maximum drawdown depth (positive fraction) of each row of per-period returns (P, n)."""
    r = np.atleast_2d(np.asarray(r, float))
    L = np.concatenate([np.zeros((r.shape[0], 1)), np.cumsum(np.log1p(np.maximum(r, -0.999999)), axis=1)], axis=1)
    dd = (L - np.maximum.accumulate(L, axis=1)).min(axis=1)
    return 1.0 - np.exp(dd)


def runs(flags: np.ndarray) -> list:
    """(start, length) of each maximal run of True."""
    f = np.asarray(flags, bool)
    out, i, n = [], 0, f.size
    while i < n:
        if f[i]:
            j = i
            while j < n and f[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def episodes(flags: np.ndarray, max_gap: int = 2) -> list:
    """Runs of True merged across gaps of at most ``max_gap`` periods (the declared spell-merging rule)."""
    out = []
    for s, l in runs(flags):
        if out and s - (out[-1][0] + out[-1][1]) <= max_gap:
            out[-1] = (out[-1][0], s + l - out[-1][0])
        else:
            out.append((s, l))
    return out


def spell_paths(flags: np.ndarray, n_paths: int, rng, with_src: bool = True) -> tuple:
    """Random paths that re-place the True spells of ``flags`` (same number and lengths, random order, uniformly random
    positions, never adjacent so no two merge). Returns (paths (P, n) bool, src (P, n) int: the original index whose value
    a path position carries, -1 outside spells; None when ``with_src`` is False)."""
    f = np.asarray(flags, bool)
    n = f.size
    sp = runs(f)
    k = len(sp)
    P = int(n_paths)
    if k == 0:
        return np.zeros((P, n), bool), (np.full((P, n), -1, int) if with_src else None)
    lens = np.array([l for _, l in sp], int)
    orig = np.array([s for s, _ in sp], int)
    free = n - int(lens.sum()) - (k - 1)
    if free < 0:
        return np.repeat(f[None], P, axis=0), (np.where(f, np.arange(n), -1)[None].repeat(P, axis=0) if with_src else None)
    c = np.sort(rng.integers(0, free + 1, size=(P, k)), axis=1)
    perm = np.argsort(rng.random((P, k)), axis=1)
    L = lens[perm]
    O = orig[perm]
    starts = c + (np.cumsum(L, axis=1) - L) + np.arange(k)[None, :]
    ends = starts + L
    rows = np.repeat(np.arange(P), k)
    D = np.zeros((P, n + 1), np.int8)
    D[rows, starts.ravel()] = 1
    D[rows, ends.ravel()] = -1
    paths = np.cumsum(D, axis=1, dtype=np.int16)[:, :n] > 0
    if not with_src:
        return paths, None
    S = np.zeros((P, n + 1), np.int64)
    shift = (O - starts).ravel()
    S[rows, starts.ravel()] += shift
    S[rows, ends.ravel()] -= shift
    src = np.where(paths, np.arange(n)[None, :] + np.cumsum(S, axis=1)[:, :n], -1)
    return paths, src


def _fmt_bps(v) -> str:
    return "n/a" if v is None else f"{v * 1e4:+.1f} bps"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _sr_ann(x, ppy: int = PPY) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, ppy)) if x.size > 2 and x.std() > 0 else None


# ======================================================================================= T-300 TSMOM vs mean ==

T300_ASSETS = ("SPY", "QQQ", "GLD", "SLV", "EFA", "AGG", "TLT", "DBC", "BTC-USD", "ETH-USD")
T300_MIN_N = 300
T300_START = "2000-01"
T300_POST = "2013-01"          # the 2013-2026 post-publication window
T58_TRIALS = 48                # T-58's trials already run on overlapping assets: in the DSR count only
FORMATIONS = {"12-1": ((12, 1),), "6-1": ((6, 1),), "3-1": ((3, 1),), "1-0": ((1, 0),), "12-7": ((12, 7),),
              "6-2": ((6, 2),), "ens-1/3/12": ((1, 0), (3, 0), (12, 0))}
T300_FAMILY = tuple((f, pos, basis, rule) for f in FORMATIONS for pos in ("LF", "LS") for basis in ("excess", "raw")
                    for rule in ("sign", "trend"))            # 7 x 2 x 2 x 2 = 56 declared grid trials
T300_PRIMARY = ("12-1", "LF", "excess", "sign")
T300_N_TRIALS = len(T300_FAMILY) + T58_TRIALS                  # 104


def _prep_monthly(days: Sequence[str], adj: np.ndarray, bills: Bills, crypto: bool) -> dict:
    """Month-end grid, month-end-to-month-end returns, fill-to-fill holds and daily log-return prefix sums of one asset."""
    g = month_grid(days)
    me, ex = g["me"], g["ex"]
    C = bill_logcum(bills, days)
    adj = np.asarray(adj, float)
    lr = np.r_[0.0, np.diff(np.log(adj))]
    lrx = lr - np.r_[0.0, np.diff(C)]
    out = {"months": g["months"], "me": me, "ex": ex, "M": adj[me], "Cme": C[me], "T": len(me),
           "S1": {"raw": np.cumsum(lr), "excess": np.cumsum(lrx)}, "S2": {"raw": np.cumsum(lr * lr), "excess": np.cumsum(lrx * lrx)}}
    out["R"] = adj[ex[1:]] / adj[ex[:-1]] - 1.0                                          # hold of decision t, t = 0..T-2
    out["rf"] = np.zeros(len(me) - 1) if crypto else np.exp(C[ex[1:]] - C[ex[:-1]]) - 1.0
    out["labels"] = [days[i][:7] for i in ex[:-1]]
    M = out["M"]
    out["xm"] = {"raw": M[1:] / M[:-1] - 1.0, "excess": M[1:] / M[:-1] * np.exp(-(out["Cme"][1:] - out["Cme"][:-1])) - 1.0}
    return out


def _window_signal(A: dict, t: np.ndarray, a: int, b: int, basis: str, rule: str) -> np.ndarray:
    """Formation value over month-ends t-a .. t-b at decisions t: cumulative return (sign rule) or the t-statistic of the
    daily log returns in that window (Baltas-Kosowski TREND)."""
    M, me = A["M"], A["me"]
    if rule == "sign":
        cum = M[t - b] / M[t - a]
        if basis == "excess":
            cum = cum * np.exp(-(A["Cme"][t - b] - A["Cme"][t - a]))
        return cum - 1.0
    i0, i1 = me[t - a], me[t - b]
    S1, S2 = A["S1"][basis], A["S2"][basis]
    n = (i1 - i0).astype(float)
    s1, s2 = S1[i1] - S1[i0], S2[i1] - S2[i0]
    mu = s1 / n
    var = np.maximum((s2 - n * mu * mu) / np.maximum(n - 1, 1), 1e-18)
    return mu / np.sqrt(var / n)


def _position(val: np.ndarray, pos: str, rule: str) -> np.ndarray:
    if rule == "sign":
        return (val > 0).astype(float) if pos == "LF" else np.sign(val)
    if pos == "LF":
        return (val >= 1.0).astype(float)
    return np.where(val >= 1.0, 1.0, np.where(val <= -1.0, -1.0, 0.0))


def _hist_mean_pos(A: dict, t: np.ndarray, pos: str, basis: str) -> np.ndarray:
    """Huang et al. historical-mean strategy: long when the expanding mean of the asset's monthly returns (months 1..t,
    from its first archived month) is positive, else cash (LF) or short (LS)."""
    cs = np.cumsum(A["xm"][basis])
    mean = cs[t - 1] / t
    return np.where(mean > 0, 1.0, 0.0 if pos == "LF" else -1.0)


def tsmom_d_series(assets: dict, bills: Bills, variant: tuple, start: str = T300_START, costs: Optional[dict] = None,
                   prepared: Optional[dict] = None) -> dict:
    """Pooled monthly d = r(TSMOM variant) - r(historical-mean counterpart), equal weight over the assets active in each
    hold month (an asset is active from its 13th month-end). Returns labels, d, per-asset d by label."""
    form, pos, basis, rule = variant
    per, pool = {}, {}
    for sym, (days, adj) in assets.items():
        A = prepared[sym] if prepared and sym in prepared else _prep_monthly(days, adj, bills, sym in CRYPTO)
        T = A["T"]
        t = np.arange(12, T - 1)
        if t.size == 0:
            continue
        comps = [_position(_window_signal(A, t, a, b, basis, rule), pos, rule) for a, b in FORMATIONS[form]]
        wT = np.mean(comps, axis=0)
        wH = _hist_mean_pos(A, t, pos, basis)
        c = (costs or {}).get(sym, _cost(sym))
        R, rf = A["R"][t], A["rf"][t]
        d = _net_single(wT, R, rf, c) - _net_single(wH, R, rf, c)
        labs = [A["labels"][k] for k in t]
        per[sym] = {}
        for lab, x in zip(labs, d):
            if lab >= start:
                per[sym][lab] = float(x)
                pool.setdefault(lab, []).append(float(x))
    labels = sorted(pool)
    return {"labels": labels, "d": np.array([np.mean(pool[l]) for l in labels], float),
            "n_active": [len(pool[l]) for l in labels], "per_asset": per}


def tsmom_vs_hist_mean(assets: dict, bills: Bills, start: str = T300_START, min_n: int = T300_MIN_N,
                       vix: Optional[dict] = None, family: Optional[Sequence[tuple]] = None, n_trials: Optional[int] = None,
                       n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-300 core. ``assets``: {sym: (days, adjclose)}. Criteria: mean d > 0 with the studentized CBB 95% CI above 0;
    DSR(d) > 0.95 at ``n_trials`` with the variance of the computed family's per-period d Sharpes; post-2012 mean d >= 0."""
    family = T300_FAMILY if family is None else tuple(family)
    n_trials = T300_N_TRIALS if n_trials is None else n_trials
    prepared = {s: _prep_monthly(dd, a, bills, s in CRYPTO) for s, (dd, a) in assets.items()}
    fam = {v: tsmom_d_series(assets, bills, v, start, prepared=prepared) for v in family}
    P = fam[T300_PRIMARY] if T300_PRIMARY in fam else fam[family[0]]
    labels, d = P["labels"], P["d"]
    n = d.size
    mt = mean_test(d, n_boot, seed, reps) if n >= 8 else {"est": float(d.mean()) if n else None, "ci": [None, None]}
    fam_sr = [_sr_pp(f["d"]) for f in fam.values()]
    ds = family_dsr(d, fam_sr, n_trials)
    post = np.array([x for l, x in zip(labels, d) if l >= T300_POST])
    post_mean = float(post.mean()) if post.size else None
    crit = [_ci_crit(mt, "gt", 0.0, "mean d > 0 with studentized CBB 95% CI excluding 0", _fmt_bps) if n >= 8
            else ("mean d CI (fewer than 8 months)", None, False),
            dsr_row(ds, f"DSR(d) > {DSR_PASS}"),
            (f"post-2012 mean d >= 0 ({_fmt_bps(post_mean)} over {post.size} months; negative = 'decayed')",
             None if post_mean is None else post_mean >= 0, False)]
    v, why = _decide(crit, n, min_n, "calendar months")
    label = "decayed" if (post_mean is not None and post_mean < 0 and crit[0][1] and crit[1][1]) else None
    diag = {}
    by_dec = {}
    for l, x in zip(labels, d):
        by_dec.setdefault(l[:3] + "0s", []).append(x)
    diag["by_decade_bps"] = {k: float(np.mean(x) * 1e4) for k, x in sorted(by_dec.items())}
    diag["per_asset_mean_bps"] = {s: (float(np.mean(list(x.values())) * 1e4) if x else None) for s, x in P["per_asset"].items()}
    diag["per_asset_sign"] = {s: (None if b is None else ("+" if b > 0 else "-" if b < 0 else "0")) for s, b in diag["per_asset_mean_bps"].items()}
    loo = {}
    for drop in P["per_asset"]:
        pool = {}
        for s, x in P["per_asset"].items():
            if s != drop:
                for l, y in x.items():
                    pool.setdefault(l, []).append(y)
        loo[drop] = float(np.mean([np.mean(pool[l]) for l in sorted(pool)]) * 1e4) if pool else None
    diag["leave_one_asset_out_bps"] = loo
    if vix:
        vk = sorted(vix)
        spy = prepared.get("SPY")
        dec_day = {}
        if spy is not None:
            for k, l in enumerate(spy["labels"]):
                dec_day[l] = assets["SPY"][0][spy["me"][k]]
        vals = []
        for l in labels:
            dd = dec_day.get(l)
            j = np.searchsorted(vk, dd, side="right") - 1 if dd else -1
            vals.append(vix[vk[j]] if j >= 0 else np.nan)
        vals = np.array(vals, float)
        ok = np.isfinite(vals)
        if ok.sum() >= 9:
            q1, q2 = np.quantile(vals[ok], [1 / 3, 2 / 3])
            terc = {"low": d[ok & (vals <= q1)], "mid": d[ok & (vals > q1) & (vals <= q2)], "high": d[ok & (vals > q2)]}
            diag["vix_tercile_bps"] = {k: float(x.mean() * 1e4) if x.size else None for k, x in terc.items()}
    return {"n": int(n), "labels": [labels[0], labels[-1]] if labels else None, "mean": mt, "dsr": ds,
            "post_mean": post_mean, "post_n": int(post.size), "sharpe_d_ann": _sr_ann(d), "family_sharpes_pp": fam_sr,
            "n_active_range": [int(min(P["n_active"])), int(max(P["n_active"]))] if n else None, "diag": diag,
            "label": label, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_mom_tsmom_vs_hist_mean(archive):
    """T-300."""
    need = [dh(s) for s in T300_ASSETS] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    assets = {s: (_daily(archive, dh(s))["days"], _daily(archive, dh(s))["adj"]) for s in T300_ASSETS}
    vix = _series(archive, VIX_B) if _has(archive, VIX_B) else None
    j = tsmom_vs_hist_mean(assets, bills, vix=vix)
    mt, ds, dg = j["mean"], j["dsr"], j["diag"]
    reason = (f"12-1 long/flat TSMOM minus the historical-mean strategy, pooled equal weight over the active assets of "
              f"{', '.join(T300_ASSETS)} (each from its 13th month-end), hold months {j['labels'][0]}..{j['labels'][1]} "
              f"({j['n']} months, {j['n_active_range'][0]}-{j['n_active_range'][1]} assets active): signal on the "
              f"month-end close, filled at the next session's close, DTB3 cash (crypto flat = USD), 2/5/35 bps per side. "
              f"Mean d {_fmt_bps(mt.get('est'))}/month ({_ci(mt.get('ci'), 1, 1e4, ' bps')}, studentized CBB, 12-month "
              f"blocks), annualised Sharpe of d {_s(j['sharpe_d_ann'], 2)}; DSR(d) {_f(ds['dsr'])} at {ds['n_trials']} "
              f"trials ({len(T300_FAMILY)} declared grid trials computed + {T58_TRIALS} T-58 trials in the count only; "
              f"PSR vs 0 {_f(ds['psr0'])}); post-2012 mean d {_fmt_bps(j['post_mean'])} over {j['post_n']} months"
              + (" (DECAYED)" if j["label"] == "decayed" else "")
              + ". Diagnostics: by decade " + ", ".join(f"{k} {x:+.1f}" for k, x in dg["by_decade_bps"].items())
              + " bps; per-asset mean d " + ", ".join(f"{s} {x:+.1f}" for s, x in dg["per_asset_mean_bps"].items() if x is not None)
              + " bps; leave-one-asset-out pooled mean " + ", ".join(f"-{s} {x:+.1f}" for s, x in dg["leave_one_asset_out_bps"].items() if x is not None)
              + " bps" + (("; by VIX tercile at decision " + ", ".join(f"{k} {x:+.1f}" for k, x in dg['vix_tercile_bps'].items() if x is not None) + " bps")
                          if dg.get("vix_tercile_bps") else "")
              + ". Survivorship: surviving ETFs only (small upward bias, stated) — " + j["why"])
    stat = {"n_months": j["n"], "window": j["labels"], "mean_d": mt.get("est"), "ci": mt.get("ci"), "ci_mc_se": mt.get("ci_mc_se"),
            "sharpe_d_ann": j["sharpe_d_ann"], "dsr": ds, "post2012_mean_d": j["post_mean"], "post2012_n": j["post_n"],
            "label": j["label"], "diagnostics": dg, "family": [list(v) for v in T300_FAMILY], "n_trials": T300_N_TRIALS,
            "criteria": j["criteria"], "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ========================================================================================= T-301 SMA timing ==

T301_MIN_N = 380
T301_START = "1994-01"
T301_LOOKBACKS = (6, 8, 10, 12)
T301_BANDS = (0.0, 0.01, 0.03)
T301_MAS = ("SMA", "EMA")
T301_EVALS = ("monthly", "daily")
T301_UNIVS = ("SPY", "five-sleeve")
FIVE = ("SPY", "EFA", "IEF", "DBC", "VNQ")
T301_FAMILY = tuple((L, b, ma, ev, u) for u in T301_UNIVS for ev in T301_EVALS for ma in T301_MAS for L in T301_LOOKBACKS
                    for b in T301_BANDS)                 # 4 x 3 x 2 x 2 x 2 = 96 declared variants (the Holm family)
T301_PRIMARY = (10, 0.0, "SMA", "monthly", "SPY")
T301_N_NULL = 1000             # the claim's 1,000 matched random paths
T301_N_REFINE = 10000          # a 1,000-path p cannot go below 1/1001 > 0.05/96: candidates are re-estimated on 10,000
T301_DSR_TRIALS = 96 + 48      # reported deflation count (96 + T-58's 48); not a pass criterion
T301_SHARPE_THR = -0.15
T301_REGIMES = (("1994-01", "2008-12"), ("2009-01", "2021-12"), ("2022-01", "2026-12"))
DAYS_PER_MONTH = 21


def ma_state(x: np.ndarray, L: int, band: float, kind: str) -> np.ndarray:
    """In (1) / out (0) state of a price series against its L-point SMA or EMA with a hysteresis band: in when x >
    MA (1 + band), out when x < MA (1 - band), else unchanged; NaN until the MA is defined."""
    x = np.asarray(x, float)
    n = x.size
    ma = np.full(n, np.nan)
    if n >= L:
        if kind == "SMA":
            cs = np.r_[0.0, np.cumsum(x)]
            ma[L - 1:] = (cs[L:] - cs[:-L]) / L
        else:
            a = 2.0 / (L + 1.0)
            ma[L - 1] = x[:L].mean()
            for i in range(L, n):
                ma[i] = a * x[i] + (1 - a) * ma[i - 1]
    st = np.full(n, np.nan)
    prev = None
    for i in range(L - 1, n):
        if x[i] > ma[i] * (1 + band):
            s = 1.0
        elif x[i] < ma[i] * (1 - band):
            s = 0.0
        else:
            s = prev if prev is not None else float(x[i] > ma[i])
        st[i] = s
        prev = s
    return st


def _t301_sleeves(series: dict, bills: Bills, universe: str, ev: str, start: str) -> dict:
    """Per-sleeve price, log-return and log-cash arrays on the variant's evaluation grid and the window shared by every
    lookback, band and MA of that universe x evaluation (so the 24 variants of a cell are compared on one sample)."""
    syms = ("SPY",) if universe == "SPY" else FIVE
    Lmax = max(T301_LOOKBACKS)
    if ev == "monthly":
        per = {}
        for s in syms:
            days, adj = series[s]
            g = month_grid(days)
            C = bill_logcum(bills, days)
            me, ex = g["me"], g["ex"]
            labs = [days[i][:7] for i in ex[:-1]]
            per[s] = {"x": adj[me], "R": adj[ex[1:]] / adj[ex[:-1]] - 1, "rf": np.exp(C[ex[1:]] - C[ex[:-1]]) - 1,
                      "labels": labs, "first_ok": Lmax - 1}
        common = None
        for s in syms:
            ok = [l for k, l in enumerate(per[s]["labels"]) if k >= per[s]["first_ok"] and l >= start]
            common = set(ok) if common is None else common & set(ok)
        labels = sorted(common or ())
        out = {"labels": labels, "sleeves": {}, "ppy": 12, "seg_start": None}
        for s in syms:
            idx = {l: k for k, l in enumerate(per[s]["labels"])}
            ks = np.array([idx[l] for l in labels], int)
            R, rf = per[s]["R"][ks], per[s]["rf"][ks]
            out["sleeves"][s] = {"x": per[s]["x"], "R": R, "rf": rf, "lR": np.log1p(R), "lrf": np.log1p(rf), "dec": ks}
        return out
    common = None
    for s in syms:
        common = set(series[s][0]) if common is None else common & set(series[s][0])
    days = sorted(common)
    C = bill_logcum(bills, days)
    rf = np.r_[0.0, np.exp(np.diff(C)) - 1]
    g = month_grid(days)
    first_ex = None
    for e in g["ex"]:
        if days[e][:7] >= start:
            first_ex = int(e)
            break
    last_ex = int(g["ex"][-1])
    lo = max(first_ex + 1 if first_ex is not None else 0, Lmax * DAYS_PER_MONTH + 1)   # state at i-2 defined for every L
    n = last_ex + 1 - lo
    out = {"labels": [days[i][:7] for i in range(lo, last_ex + 1)], "days": days[lo:last_ex + 1], "sleeves": {}, "ppy": 252}
    for s in syms:
        idx = {d: k for k, d in enumerate(series[s][0])}
        x = np.array([series[s][1][idx[d]] for d in days], float)
        R, rfs = (x[1:] / x[:-1] - 1)[lo - 1:last_ex], rf[lo:last_ex + 1]
        out["sleeves"][s] = {"x": x, "R": R, "rf": rfs, "lR": np.log1p(R), "lrf": np.log1p(rfs), "lo": lo}
    exs = set(int(e) for e in g["ex"])
    seg = np.array([(i - 1) in exs for i in range(lo, last_ex + 1)], bool)        # rebalanced at each fill close
    seg[0] = True
    out["seg_start"] = seg
    out["sidx"] = np.maximum.accumulate(np.where(seg, np.arange(n), 0))
    out["seg_end"] = np.r_[seg[1:], True]
    return out


def _t301_positions(cell: dict, L: int, band: float, ma: str, ev: str) -> dict:
    """{sleeve: in-market flags (n,) bool} of a variant on its cell's window."""
    pos = {}
    for s, sl in cell["sleeves"].items():
        if ev == "monthly":
            st = ma_state(sl["x"], L, band, ma)
            pos[s] = st[sl["dec"]] > 0.5
        else:
            st = ma_state(sl["x"], L * DAYS_PER_MONTH, band, ma)
            lo, n = sl["lo"], sl["R"].size
            pos[s] = st[lo - 2:lo - 2 + n] > 0.5               # signal at close i-2, filled at close i-1, earns day i
    return pos


def _t301_logwealth(cell: dict, inm: dict, costs: dict) -> np.ndarray:
    """(P, n) log wealth after each period of in/out paths {sleeve: (P, n) bool}: the asset when in, DTB3 when out, a
    proportional cost (1 - c) at each switch (none before the first period); several sleeves at equal weight, rebalanced
    every period (monthly grid) or at each month's fill (daily grid)."""
    lrs = []
    for s, sl in cell["sleeves"].items():
        x = np.atleast_2d(inm[s])
        lr = np.where(x, sl["lR"][None, :], sl["lrf"][None, :])
        lr[:, 1:] += math.log1p(-costs[s]) * (x[:, 1:] != x[:, :-1])
        lrs.append(lr)
    if len(lrs) == 1:
        return np.cumsum(lrs[0], axis=1)
    if cell["seg_start"] is None:
        acc = np.exp(lrs[0])
        for lr in lrs[1:]:
            acc += np.exp(lr)
        return np.cumsum(np.log(acc / len(lrs)), axis=1)
    sidx = cell["sidx"]
    prev = np.maximum(sidx - 1, 0)
    has = (sidx > 0)[None, :]
    acc = None
    for lr in lrs:
        cl = np.cumsum(lr, axis=1)
        e = np.exp(cl - np.where(has, cl[:, prev], 0.0))
        acc = e if acc is None else acc + e
    logV = np.log(acc / len(lrs))
    cend = np.cumsum(np.where(cell["seg_end"][None, :], logV, 0.0), axis=1)
    return logV + np.where(has, cend[:, prev], 0.0)


def mdd_from_logwealth(L: np.ndarray) -> np.ndarray:
    """Maximum drawdown depth of each row of log wealth (P, n), starting from wealth 1 (log 0)."""
    L = np.atleast_2d(L)
    peak = np.maximum(np.maximum.accumulate(L, axis=1), 0.0)
    return 1.0 - np.exp(np.minimum((L - peak).min(axis=1), 0.0))


def _t301_null(cell: dict, pos: dict, costs: dict, n_paths: int, seed: int, chunk: int = 500) -> np.ndarray:
    """Null MDD depths: every sleeve's own out-of-market spells re-placed at random (spell-length preserving)."""
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < n_paths:
        k = min(chunk, n_paths - done)
        pp = {s: ~spell_paths(~pos[s], k, rng, with_src=False)[0] for s in cell["sleeves"]}
        out.append(mdd_from_logwealth(_t301_logwealth(cell, pp, costs)))
        done += k
    return np.concatenate(out)


def _mc_p(null: np.ndarray, depth: float) -> float:
    """Monte Carlo p-value: (1 + #{null depth <= rule depth}) / (paths + 1) (ties count against the rule)."""
    return float((1 + np.sum(null <= depth)) / (null.size + 1))


def sma_timing_vs_random(series: dict, bills: Bills, start: str = T301_START, min_n: int = T301_MIN_N,
                         family: Optional[Sequence[tuple]] = None, n_null: Optional[int] = None, n_refine: Optional[int] = None,
                         n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-301 core. ``series``: {sym: (days, adjclose)} for SPY (and the five sleeves when the family has them).

    Null: each sleeve's own out-of-market spells re-placed at random positions (count and lengths kept, never merging).
    p = (1 + #{null MDD <= rule MDD}) / (paths + 1). Every variant gets ``n_null`` paths; the primary is re-estimated on
    ``n_refine`` paths (a 1,000-path p cannot go below 1/1001 > 0.05/96). When the Holm decision is not already settled by
    the primary alone (p0 >= 0.05: fails; 96 p0 < 0.05: passes, Holm never exceeds Bonferroni), every variant whose
    1,000-path p is at or below p0 + 0.01 (it may rank before the primary) is re-estimated on ``n_refine`` paths too."""
    family = T301_FAMILY if family is None else tuple(family)
    n_null = T301_N_NULL if n_null is None else n_null
    n_refine = T301_N_REFINE if n_refine is None else n_refine
    costs = {s: (2e-4 if s == "SPY" else 5e-4) for s in FIVE}
    cells = {}
    res = {}
    for vi, v in enumerate(family):
        L, b, ma, ev, u = v
        key = (u, ev)
        if key not in cells:
            cells[key] = _t301_sleeves(series, bills, u, ev, start)
        cell = cells[key]
        pos = _t301_positions(cell, L, b, ma, ev)
        depth = float(mdd_from_logwealth(_t301_logwealth(cell, pos, costs))[0])
        null = _t301_null(cell, pos, costs, n_null, seed + 7919 * vi)
        res[v] = {"depth": depth, "null": null, "p": _mc_p(null, depth), "share_worse_1000": float(np.mean(null[:1000] > depth)),
                  "n_paths": int(null.size), "pos": pos, "cell": key, "time_in_market": float(np.mean([x.mean() for x in pos.values()])),
                  "vi": vi}

    def refine(v):
        r = res[v]
        if r["n_paths"] >= n_refine:
            return
        extra = _t301_null(cells[r["cell"]], r["pos"], costs, n_refine - r["n_paths"], seed + 104729 + 7919 * r["vi"])
        r["null"] = np.concatenate([r["null"], extra])
        r["n_paths"] = int(r["null"].size)
        r["p"] = _mc_p(r["null"], r["depth"])

    pk = T301_PRIMARY if T301_PRIMARY in res else family[0]
    prim = res[pk]
    m = len(family)
    refine(pk)
    p0 = prim["p"]
    # Holm-adjusted p of the primary lies in [(m - r + 1) p0, m p0], r = its rank. Variants whose 1,000-path p exceeds
    # p0 + 0.01 rank after it (their p's binomial s.e. at 1,000 paths is <= 0.003 near p0 < 0.05), so r <= 1 + #cand.
    cand = [v for v, r in res.items() if v != pk and r["p"] <= p0 + 0.01]
    lower = (m - len(cand)) * p0
    if p0 >= ALPHA:
        settled = "fail: raw p >= 0.05"
    elif m * p0 < ALPHA:
        settled = f"pass: Bonferroni {m * p0:.4f} < 0.05"
    elif lower >= ALPHA:
        settled = f"fail: at most {len(cand)} variants can rank before the primary, so Holm-adjusted p >= {m - len(cand)} x p = {lower:.4f}"
    else:
        settled = ""
        for v in cand:
            refine(v)
    ps = {v: r["p"] for v, r in res.items()}
    h = holm_primary(ps, pk)
    h["settled"] = settled
    h["n_candidates"] = len(cand)
    cell = cells[(pk[4], "monthly")] if (pk[4], "monthly") in cells else cells[prim["cell"]]
    sl = cell["sleeves"]["SPY"]
    rule = np.expm1(np.diff(np.r_[0.0, _t301_logwealth(cell, prim["pos"], costs)[0]]))
    rule_ex, bh_ex = rule - sl["rf"], sl["R"] - sl["rf"]
    n = rule.size
    sh = sharpe_test(rule_ex, bh_ex, n_boot, seed, reps, thr=T301_SHARPE_THR)
    w1000 = prim["share_worse_1000"]
    hname = f"rule MDD below the 5th percentile of the matched null, Holm over {m} variants (p {p0:.4f} on {prim['n_paths']} paths"
    if settled.startswith("fail"):
        hrow = (hname + f"; {settled[6:]})", False, True)
    elif settled.startswith("pass"):
        hrow = (hname + f"; Holm-adjusted p <= {settled[6:]})", True, False)
    else:
        hrow = holm_row(h, hname + f"; {len(cand)} contending variants re-estimated on {n_refine} paths)")
    crit = [(f"rule MDD smaller than at least 95% of the claim's 1,000 matched random paths ({w1000 * 100:.1f}% of them deeper)",
             w1000 >= 0.95, w1000 < 0.95 and n >= min_n),
            hrow,
            _ci_crit(sh, "gt", T301_SHARPE_THR, f"Sharpe difference (rule - buy-and-hold, excess returns) lower 95% bound > {T301_SHARPE_THR}")]
    v, why = _decide(crit, n, min_n, "months")
    labels = cell["labels"]
    regimes = {}
    for a, z in T301_REGIMES:
        msk = np.array([a <= l <= z for l in labels])
        if msk.sum() >= 6:
            regimes[f"{a[:4]}-{z[:4]}"] = {"n": int(msk.sum()), "mdd_rule": float(mdd_depth(rule[msk])[0]), "mdd_bh": float(mdd_depth(sl["R"][msk])[0]),
                                           "sharpe_diff": (_sr_ann(rule_ex[msk]) or 0) - (_sr_ann(bh_ex[msk]) or 0)}
    monthly_sr = []
    for vv, r in res.items():
        if vv[3] == "monthly":
            c_ = cells[r["cell"]]
            rr = np.expm1(np.diff(np.r_[0.0, _t301_logwealth(c_, r["pos"], costs)[0]]))
            monthly_sr.append(_sr_pp(rr - np.mean([x["rf"] for x in c_["sleeves"].values()], axis=0)))
    ds = family_dsr(rule_ex, monthly_sr, T301_DSR_TRIALS)
    return {"n": int(n), "labels": [labels[0], labels[-1]], "primary": {k: prim[k] for k in ("depth", "p", "share_worse_1000", "n_paths", "time_in_market")},
            "null_q05": float(np.quantile(prim["null"], 0.05)), "null_median": float(np.median(prim["null"])),
            "bh_depth": float(mdd_depth(sl["R"])[0]), "n_out_spells": len(runs(~prim["pos"]["SPY"])), "holm_settled": settled,
            "holm": h, "family_p": {"|".join(map(str, k)): r["p"] for k, r in res.items()},
            "family_paths": {"|".join(map(str, k)): r["n_paths"] for k, r in res.items()},
            "cells": {f"{u}/{ev}": {"window": [c["labels"][0], c["labels"][-1]] if c["labels"] else None, "n": len(c["labels"])} for (u, ev), c in cells.items()},
            "sharpe": sh, "regimes": regimes, "dsr_report": ds,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_mom_sma10_drawdown_vs_random(archive):
    """T-301."""
    need = [dh(s) for s in FIVE] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    series = {s: (_daily(archive, dh(s))["days"], _daily(archive, dh(s))["adj"]) for s in FIVE}
    j = sma_timing_vs_random(series, bills)
    pr, sh = j["primary"], j["sharpe"]
    fp = j["family_p"]
    n_sig = sum(1 for p in fp.values() if p < ALPHA)
    reason = (f"SPY 10-month SMA long/flat on month-end adjcloses, filled at the next session's close, DTB3 when out, 2 bps "
              f"per switch, hold months {j['labels'][0]}..{j['labels'][1]} ({j['n']} months, {pr['time_in_market'] * 100:.0f}% in "
              f"market, {j['n_out_spells']} out-of-market spells): MDD {pr['depth'] * 100:.1f}% vs buy-and-hold "
              f"{j['bh_depth'] * 100:.1f}%; matched null (spell-length-preserving re-placement of the rule's own out spells) "
              f"median {j['null_median'] * 100:.1f}%, 5th pct {j['null_q05'] * 100:.1f}%, {pr['share_worse_1000'] * 100:.1f}% of "
              f"the first 1,000 paths deeper, p {pr['p']:.4f} on {pr['n_paths']} paths; Holm over the {len(T301_FAMILY)} declared "
              f"variants (lookback 6/8/10/12 x band 0/1/3% x SMA/EMA x monthly/daily x SPY/five-sleeve; daily = 21 x L-session MA, "
              f"five-sleeve = SPY/EFA/IEF/DBC/VNQ at 20% rebalanced monthly; {n_sig}/{len(fp)} variants with raw p < 0.05, "
              f"{j['holm']['n_candidates']} with a 1,000-path p within 0.01 of the primary's) "
              + (f"settled by bounds ({j['holm_settled']})" if j["holm_settled"] else
                 (f"adjusted p {j['holm']['adj']:.4f}" if j['holm']['adj'] is not None else "bounded"))
              + f". Excess-return Sharpe rule {_s(sh.get('sharpe_a'), 2)} vs buy-and-hold {_s(sh.get('sharpe_b'), 2)}: "
              f"difference {_s(sh.get('diff'), 3)} ({_ci(sh.get('ci'))}, studentized paired CBB, 12-month blocks; need lower > "
              f"{T301_SHARPE_THR}). Regimes: " + "; ".join(f"{k} MDD {x['mdd_rule'] * 100:.0f}% vs {x['mdd_bh'] * 100:.0f}%, "
                                                          f"Sharpe diff {x['sharpe_diff']:+.2f}" for k, x in j["regimes"].items())
              + f". Reported only: DSR of the rule at {T301_DSR_TRIALS} trials (96 + T-58's 48) {_f(j['dsr_report']['dsr'])} — "
              + j["why"])
    stat = {"n_months": j["n"], "window": j["labels"], "mdd_rule": pr["depth"], "mdd_bh": j["bh_depth"], "null_median": j["null_median"],
            "null_q05": j["null_q05"], "share_null_deeper_1000": pr["share_worse_1000"], "p": pr["p"], "n_paths": pr["n_paths"],
            "holm": j["holm"], "holm_settled": j["holm_settled"], "family_p": fp, "family_paths": j["family_paths"], "cells": j["cells"],
            "sharpe_rule": sh.get("sharpe_a"), "sharpe_bh": sh.get("sharpe_b"), "sharpe_diff": sh.get("diff"), "sharpe_ci": sh.get("ci"),
            "regimes": j["regimes"], "dsr_report": j["dsr_report"], "family": [list(v) for v in T301_FAMILY],
            "criteria": j["criteria"], "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================ T-308 residual momentum ==

T308_MIN_N = 280
T308_FAMILY = tuple((w, sc, lg) for w in (36, 24) for sc in (True, False) for lg in ("top3", "ls33"))   # 8 trials
T308_PRIMARY = (36, True, "top3")
T308_COST = 5e-4
T308_LOWPOWER = 0.9


def _aligned(series: dict) -> tuple:
    """Common daily calendar of several (days, adj) series: (days, {sym: adj on it})."""
    common = None
    for days, _ in series.values():
        common = set(days) if common is None else common & set(days)
    days = sorted(common or ())
    out = {}
    for s, (dd, a) in series.items():
        idx = {d: k for k, d in enumerate(dd)}
        out[s] = np.array([a[idx[d]] for d in days], float)
    return days, out


def _basket_returns(W: np.ndarray, R: np.ndarray, rf: np.ndarray, cost: float, borrow: Optional[np.ndarray] = None) -> np.ndarray:
    """Net returns of target weights W (n, k) on asset holds R (n, k): rf + sum w (R - rf) - borrow - cost x turnover."""
    pre = rf + (W * (R - rf[:, None])).sum(axis=1)
    if borrow is not None:
        pre = pre - borrow
    return pre - cost * drift_turnover(W, R, pre)


def residual_vs_total(sectors: dict, spy: tuple, bills: Bills, min_n: int = T308_MIN_N, family: Optional[Sequence[tuple]] = None,
                      n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-308 core. Decision at month-end t: OLS of each sector's monthly excess returns on SPY's over months t-W..t-1;
    residuals of months t-12..t-2 (11 months); score sum(e)/sd(e) (or sum(e)); comparison: compounded total return of the
    same months t-12..t-2 (12-2). Top 3 equal weight (or long top 3 / short bottom 3), filled at the next close."""
    family = T308_FAMILY if family is None else tuple(family)
    names = list(sectors)
    days, P = _aligned({**sectors, "SPY": spy})
    g = month_grid(days)
    me, ex = g["me"], g["ex"]
    C = bill_logcum(bills, days)
    T = me.size
    M = {s: P[s][me] for s in P}
    bm = np.exp(np.diff(C[me])) - 1                                             # bill over month m (index m-1)
    ret = {s: M[s][1:] / M[s][:-1] - 1 for s in P}                             # ret[s][m-1] = return of month m
    ex_r = {s: ret[s] - bm for s in P}
    R = np.column_stack([P[s][ex[1:]] / P[s][ex[:-1]] - 1 for s in names])     # hold of decision t
    rf = np.exp(C[ex[1:]] - C[ex[:-1]]) - 1
    labels = [days[i][:7] for i in ex[:-1]]
    t0 = 37                                                                     # months t-36..t-1 need month 1 = t-36
    ts = np.arange(t0, T - 1)
    k = len(names)
    x_spy = ex_r["SPY"]
    Y = np.column_stack([ex_r[s] for s in names])
    TR = np.column_stack([ret[s] for s in names])

    def scores(t, W, scaled):
        lo = t - W                                                              # months lo..t-1 -> rows lo-1..t-2
        X = np.column_stack([np.ones(W), x_spy[lo - 1:t - 1]])
        coef, *_ = np.linalg.lstsq(X, Y[lo - 1:t - 1], rcond=None)
        rows = slice(t - 13, t - 2)                                             # months t-12..t-2
        e = Y[rows] - (coef[0][None, :] + np.outer(x_spy[rows], coef[1]))
        sc = e.sum(axis=0)
        return sc / e.std(axis=0, ddof=1) if scaled else sc

    def tot(t):
        return np.prod(1 + TR[t - 13:t - 2], axis=0) - 1

    def weights(sc, lg):
        order = np.argsort(-sc, kind="stable")
        w = np.zeros(k)
        w[order[:3]] = 1 / 3
        if lg == "ls33":
            w[order[-3:]] = -1 / 3
        return w

    rfs = rf[ts]
    Rs = R[ts]
    out = {}
    rho = []
    for v in family:
        W, scaled, lg = v
        Wr = np.array([weights(scores(t, W, scaled), lg) for t in ts])
        Wt = np.array([weights(tot(t), lg) for t in ts])
        res = _basket_returns(Wr, Rs, rfs, T308_COST)
        totr = _basket_returns(Wt, Rs, rfs, T308_COST)
        out[v] = {"res": res, "tot": totr, "res_ex": res - rfs, "tot_ex": totr - rfs}
        if v == T308_PRIMARY:
            for t in ts:
                a, b = np.argsort(np.argsort(scores(t, W, scaled))), np.argsort(np.argsort(tot(t)))
                rho.append(float(np.corrcoef(a, b)[0, 1]))
    pv = out[T308_PRIMARY] if T308_PRIMARY in out else out[family[0]]
    n = ts.size
    sh = sharpe_test(pv["res_ex"], pv["tot_ex"], n_boot, seed, reps)
    d_strat = family_dsr(pv["res_ex"], [_sr_pp(o["res_ex"]) for o in out.values()], len(family))
    d_diff = family_dsr(pv["res_ex"] - pv["tot_ex"], [_sr_pp(o["res_ex"] - o["tot_ex"]) for o in out.values()], len(family))
    mrho = float(np.mean(rho)) if rho else None
    crit = [_ci_crit(sh, "gt", 0.0, "Sharpe(residual) - Sharpe(total-return) > 0 with 95% CI excluding 0 (paired studentized CBB)"),
            all_constructions([dsr_row(d_strat, "residual-momentum excess returns"), dsr_row(d_diff, "residual minus total-return series")],
                              f"DSR > {DSR_PASS} over {len(family)} trials under both readings")]
    v, why = _decide(crit, n, min_n, "months")
    labs = [labels[t] for t in ts]

    def sub(a, z):
        m = np.array([a <= l <= z for l in labs])
        if m.sum() < 6:
            return None
        return {"n": int(m.sum()), "sharpe_res": _sr_ann(pv["res_ex"][m]), "sharpe_tot": _sr_ann(pv["tot_ex"][m]),
                "mean_res": float(pv["res"][m].mean()), "mean_tot": float(pv["tot"][m].mean())}

    def worst12(r):
        if r.size < 12:
            return None
        lg = np.r_[0.0, np.cumsum(np.log1p(r))]
        return float(np.exp((lg[12:] - lg[:-12]).min()) - 1)

    return {"n": int(n), "labels": [labs[0], labs[-1]] if labs else None, "sharpe": sh, "dsr_strategy": d_strat, "dsr_diff": d_diff,
            "mean_rank_corr": mrho, "low_power": bool(mrho is not None and mrho > T308_LOWPOWER),
            "worst12": {"residual": worst12(pv["res"]), "total": worst12(pv["tot"])},
            "regimes": {"2008-09": sub("2008-01", "2009-12"), "2020": sub("2020-01", "2020-12")},
            "reshuffle": {"pre-2015-10": sub("0000", "2015-09"), "2015-10..2018-09": sub("2015-10", "2018-09"), "2018-10-": sub("2018-10", "9999")},
            "family_sharpe_ann": {"|".join(map(str, k)): {"res": _sr_ann(o["res_ex"]), "tot": _sr_ann(o["tot_ex"])} for k, o in out.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_mom_residual_vs_total_momentum(archive):
    """T-308."""
    need = [dh(s) for s in SECTORS] + [dh("SPY"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    sec = {s: (_daily(archive, dh(s))["days"], _daily(archive, dh(s))["adj"]) for s in SECTORS}
    spy = (_daily(archive, dh("SPY"))["days"], _daily(archive, dh("SPY"))["adj"])
    j = residual_vs_total(sec, spy, bills)
    sh = j["sharpe"]
    rg = j["regimes"]
    lp = " LOW-POWER (mean rank correlation > 0.9)." if j["low_power"] else ""
    reason = (f"9 original SPDRs, decisions at month-ends from 2002-01 (36 months of SPY-beta history), hold months "
              f"{j['labels'][0]}..{j['labels'][1]} ({j['n']} months), filled at the next session's close, 5 bps per side on "
              f"drift-adjusted turnover. Top-3 residual momentum (OLS on SPY excess returns over months t-36..t-1, residual "
              f"sum / sd over months t-12..t-2) excess Sharpe {_s(sh.get('sharpe_a'), 2)} vs top-3 12-2 total-return "
              f"{_s(sh.get('sharpe_b'), 2)}: difference {_s(sh.get('diff'))} ({_ci(sh.get('ci'))}, paired studentized CBB, "
              f"12-month blocks, {N_BOOT:,} draws x {REPS} seeds); DSR over the 8 declared trials (window 36/24 x scaled/unscaled x "
              f"top-3/long-short 3/3): residual series {_f(j['dsr_strategy']['dsr'])}, difference series "
              f"{_f(j['dsr_diff']['dsr'])}. Mean Spearman correlation of the two rankings {_f(j['mean_rank_corr'], 2)}.{lp} "
              f"Worst 12-month return residual {_pc(j['worst12']['residual'])} vs total {_pc(j['worst12']['total'])}; "
              + "; ".join(f"{k}: Sharpe {_s(x['sharpe_res'], 2)} vs {_s(x['sharpe_tot'], 2)}" for k, x in {**rg, **j['reshuffle']}.items() if x)
              + " (reported, not criteria) — " + j["why"])
    stat = {"n_months": j["n"], "window": j["labels"], "sharpe_residual": sh.get("sharpe_a"), "sharpe_total": sh.get("sharpe_b"),
            "diff": sh.get("diff"), "ci": sh.get("ci"), "ci_mc_se": sh.get("ci_mc_se"), "dsr_strategy": j["dsr_strategy"],
            "dsr_diff": j["dsr_diff"], "mean_rank_corr": j["mean_rank_corr"], "label": "LOW-POWER" if j["low_power"] else None,
            "worst12": j["worst12"], "regimes": rg, "reshuffle": j["reshuffle"], "family_sharpe_ann": j["family_sharpe_ann"],
            "family": [list(v) for v in T308_FAMILY], "criteria": j["criteria"],
            "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-311 crash protection ==

T311_MIN_N = 300
T311_START = "2000-01"
T311_FAMILY = tuple((lb, q, act, kind) for lb in (12, 24) for q in (0.7, 0.8, 0.9) for act in ("both", "short") for kind in ("binary", "dm"))
T311_PRIMARY = (24, 0.8, "both", "binary")     # the claim's filter: short leg 0 and long leg halved
T311_N_NULL = 1000
T311_COST = 5e-4
T311_BORROW = 0.005
T311_MIN_EPISODES = 5
T311_MERGE_GAP = 2                             # activation runs separated by <= 2 inactive months are one episode
T311_SHARPE_THR = -0.1
T311_DM_MIN_ACTIVE = 3                         # DM regression needs >= 3 past activation months, else the binary action


def spy_vol126(spy_adj: np.ndarray) -> np.ndarray:
    """126-session realized volatility (sd of daily log returns, ddof 1) through each day; NaN until defined."""
    lr = np.r_[0.0, np.diff(np.log(np.asarray(spy_adj, float)))]
    cs, cs2 = np.r_[0.0, np.cumsum(lr)], np.r_[0.0, np.cumsum(lr * lr)]
    vol = np.full(lr.size, np.nan)
    i = np.arange(126, lr.size)
    s1, s2 = cs[i + 1] - cs[i - 125], cs2[i + 1] - cs2[i - 125]
    vol[i] = np.sqrt(np.maximum((s2 - s1 * s1 / 126) / 125, 0.0))
    return vol


def _spy_indicators(spy_days: Sequence[str], spy_adj: np.ndarray, dec_days: Sequence[str], lookback: int, q: float,
                    vol: Optional[np.ndarray] = None, vol_start: str = "1994-01-01") -> np.ndarray:
    """A_t = (SPY adjclose return over the past ``lookback`` months < 0) and (126-day realized vol at t above the ``q``
    quantile of its expanding daily distribution from 1994 through t)."""
    idx = {d: k for k, d in enumerate(spy_days)}
    last = {}
    for k, d in enumerate(spy_days):
        last[d[:7]] = k
    vol = spy_vol126(spy_adj) if vol is None else vol
    v0 = next((k for k, d in enumerate(spy_days) if d >= vol_start), 0)
    out = np.zeros(len(dec_days), bool)
    for j, d in enumerate(dec_days):
        i = idx[d]
        m0 = _month_add(d[:7], -lookback)
        i0 = last.get(m0)
        bear = i0 is not None and spy_adj[i] / spy_adj[i0] - 1 < 0
        hist = vol[v0:i + 1]
        hist = hist[np.isfinite(hist)]
        hv = hist.size >= 20 and np.isfinite(vol[i]) and vol[i] > np.quantile(hist, q)
        out[j] = bool(bear and hv)
    return out


def _dm_scale(A: np.ndarray, wml: np.ndarray) -> np.ndarray:
    """Daniel-Moskowitz past-only scale k_t in activation months: OLS of the base WML hold return on [1, A] over decisions
    s <= t-2 (holds realised by month-end t) gives mu_off = g0, mu_on = g0 + g1; k = clip(mu_on / mu_off, 0, 1) when
    mu_off > 0, else 0 if mu_on < 0 else 1; with fewer than 3 past activation months k = 0 (the binary action)."""
    k = np.ones(A.size)
    for t in range(A.size):
        if not A[t]:
            continue
        s = np.arange(0, t - 1)
        if s.size == 0 or A[s].sum() < T311_DM_MIN_ACTIVE or (~A[s]).sum() < 3:
            k[t] = 0.0
            continue
        mu_off, mu_on = wml[s][~A[s]].mean(), wml[s][A[s]].mean()
        if mu_off > 0:
            k[t] = float(np.clip(mu_on / mu_off, 0.0, 1.0))
        else:
            k[t] = 0.0 if mu_on < 0 else 1.0
    return k


def _t311_mults(flags: np.ndarray, kv: np.ndarray, act: str) -> tuple:
    """(long multiplier, short multiplier) for activation flags (..., n) carrying scale values kv (..., n) (0 = binary)."""
    kv = np.where(flags, kv, 1.0)
    if act == "both":
        mL = np.where(flags, (1.0 + kv) / 2.0, 1.0)
    else:
        mL = np.ones_like(kv)
    mS = np.where(flags, kv, 1.0)
    return mL, mS


def _t311_returns(mL: np.ndarray, mS: np.ndarray, bL: np.ndarray, bS: np.ndarray, R: np.ndarray, rf: np.ndarray,
                  dt: np.ndarray) -> np.ndarray:
    """Total returns (P, n) of the filtered long/short portfolio: rf + mL (R_L - rf) - mS (R_S - rf) - borrow - costs."""
    mL, mS = np.atleast_2d(mL), np.atleast_2d(mS)
    W = mL[:, :, None] * bL[None] - mS[:, :, None] * bS[None]
    pre = rf[None] + (W * (R - rf[:, None])[None]).sum(axis=2) - T311_BORROW * dt[None] * mS
    return pre - T311_COST * drift_turnover(W, np.broadcast_to(R[None], W.shape), pre)


def worst_k(r: np.ndarray, k: int = 3) -> np.ndarray:
    """Worst compounded k-period return of each row."""
    r = np.atleast_2d(r)
    lg = np.concatenate([np.zeros((r.shape[0], 1)), np.cumsum(np.log1p(np.maximum(r, -0.999999)), axis=1)], axis=1)
    return np.exp((lg[:, k:] - lg[:, :-k]).min(axis=1)) - 1


def crash_filter_vs_random(sectors: dict, spy: tuple, bills: Bills, start: str = T311_START, min_n: int = T311_MIN_N,
                           family: Optional[Sequence[tuple]] = None, n_null: Optional[int] = None, n_boot: Optional[int] = None,
                           reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-311 core. ``sectors``: {sym: (days, adj)}; ``spy``: (days, adj) from 1993 (indicator history)."""
    family = T311_FAMILY if family is None else tuple(family)
    n_null = T311_N_NULL if n_null is None else n_null
    names = list(sectors)
    days, P = _aligned(sectors)
    g = month_grid(days)
    me, ex = g["me"], g["ex"]
    C = bill_logcum(bills, days)
    T = me.size
    M = np.column_stack([P[s][me] for s in names])
    R_all = np.column_stack([P[s][ex[1:]] / P[s][ex[:-1]] - 1 for s in names])
    rf_all = np.exp(C[ex[1:]] - C[ex[:-1]]) - 1
    dt_all = np.array([(_ord(days[b]) - _ord(days[a])) / 365.0 for a, b in zip(ex[:-1], ex[1:])])
    labels = [days[i][:7] for i in ex[:-1]]
    ts = np.array([t for t in range(12, T - 1) if labels[t] >= start], int)
    n = ts.size
    mom = M[ts - 1] / M[ts - 12] - 1
    k = len(names)
    bL, bS = np.zeros((n, k)), np.zeros((n, k))
    for i in range(n):
        o = np.argsort(-mom[i], kind="stable")
        bL[i, o[:3]] = 1 / 3
        bS[i, o[-3:]] = 1 / 3
    R, rf, dt = R_all[ts], rf_all[ts], dt_all[ts]
    dec_days = [days[me[t]] for t in ts]
    base = _t311_returns(np.ones(n), np.ones(n), bL, bS, R, rf, dt)[0]
    base_w3 = float(worst_k(base)[0])
    wml = (bL * R).sum(axis=1) - (bS * R).sum(axis=1)
    ind = {}
    res = {}
    rng_seed = seed
    vol = spy_vol126(spy[1])
    for vi, v in enumerate(family):
        lb, q, act, kind = v
        if (lb, q) not in ind:
            ind[(lb, q)] = _spy_indicators(spy[0], np.asarray(spy[1], float), dec_days, lb, q, vol)
        A = ind[(lb, q)]
        kv = _dm_scale(A, wml) if kind == "dm" else np.zeros(n)
        mL, mS = _t311_mults(A, kv, act)
        filt = _t311_returns(mL, mS, bL, bS, R, rf, dt)[0]
        w3 = float(worst_k(filt)[0])
        rng = np.random.default_rng(rng_seed + 7919 * vi)
        nulls = []
        done = 0
        while done < n_null:
            c = min(250, n_null - done)
            fl, src = spell_paths(A, c, rng)
            kp = np.where(src >= 0, kv[np.maximum(src, 0)], 0.0)
            a_, b_ = _t311_mults(fl, kp, act)
            nulls.append(worst_k(_t311_returns(a_, b_, bL, bS, R, rf, dt)))
            done += c
        null = np.concatenate(nulls)
        p = float((1 + np.sum(null >= w3)) / (null.size + 1))
        p_worse = float((1 + np.sum(null <= w3)) / (null.size + 1))       # small = the filter is worse than random
        res[v] = {"filtered": filt, "worst3": w3, "null_q95": float(np.quantile(null, 0.95)) if null.size else None,
                  "share_better_than": float(np.mean(null < w3)) if null.size else None, "p": p, "p_worse": p_worse,
                  "n_episodes": len(episodes(A, T311_MERGE_GAP)), "n_runs": len(runs(A)), "active_months": int(A.sum()),
                  "kv": kv}
    pv = res[T311_PRIMARY] if T311_PRIMARY in res else res[family[0]]
    h = holm_primary({v: r["p"] for v, r in res.items()}, T311_PRIMARY if T311_PRIMARY in res else family[0])
    sh = sharpe_test(pv["filtered"] - rf, base - rf, n_boot, seed, reps, thr=T311_SHARPE_THR)
    A0 = ind[(T311_PRIMARY[0], T311_PRIMARY[1])] if T311_PRIMARY in res else ind[(family[0][0], family[0][1])]
    eps = episodes(A0, T311_MERGE_GAP)
    ne = len(eps)
    crit = [holm_row(h, f"worst 3-month return {_pc(pv['worst3'])} (base {_pc(base_w3)}) better than 95% of {n_null} "
                        f"spell-preserving random filters (null 95th pct {_pc(pv['null_q95'])}, raw p {pv['p']:.4f})"),
            _ci_crit(sh, "gt", T311_SHARPE_THR, f"Sharpe difference (filtered - base) lower 95% bound > {T311_SHARPE_THR}"),
            (f"at least {T311_MIN_EPISODES} distinct activation episodes ({ne}; fewer = inconclusive)", True if ne >= T311_MIN_EPISODES else None, False)]
    if ne < T311_MIN_EPISODES:
        # "fewer than 5 = inconclusive": the episode count is the trial's own power gate, so below it (as below min_n,
        # rule 5) a failure stands only when decisive at the pass's confidence: the filter ranks among the worst 5% of the
        # random filters (one-sided p_worse <= 0.05), or the Sharpe difference's upper bound lies below the guardrail.
        name, ok, _ = crit[0]
        dec = pv["p_worse"] <= ALPHA
        crit[0] = (name + f" [episode gate: decisive only if worse than 95% of random filters, p_worse {pv['p_worse']:.4f}]", ok, dec)
        crit = [(nm + " [fails, not decisively, below the 5-episode gate]", None, False) if (ok_ is not None and not ok_ and not dec_)
                else (nm, ok_, dec_) for nm, ok_, dec_ in crit]
    v, why = _decide(crit, n, min_n, "months")
    labs = [labels[t] for t in ts]
    ep_txt = [f"{labs[s]}..{labs[s + l - 1]}" for s, l in eps]
    return {"n": int(n), "labels": [labs[0], labs[-1]] if labs else None, "base_worst3": base_w3, "primary": {kk: pv[kk] for kk in ("worst3", "null_q95", "share_better_than", "p", "p_worse", "n_episodes", "n_runs", "active_months")},
            "episodes": ep_txt, "holm": h, "sharpe": sh,
            "family": {"|".join(map(str, kk)): {"p": r["p"], "worst3": r["worst3"], "episodes": r["n_episodes"]} for kk, r in res.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_mom_crash_filter_vs_random(archive):
    """T-311."""
    need = [dh(s) for s in SECTORS] + [dh("SPY"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    sec = {s: (_daily(archive, dh(s))["days"], _daily(archive, dh(s))["adj"]) for s in SECTORS}
    spy = (_daily(archive, dh("SPY"))["days"], _daily(archive, dh("SPY"))["adj"])
    j = crash_filter_vs_random(sec, spy, bills)
    pr, sh = j["primary"], j["sharpe"]
    fam = j["family"]
    reason = (f"Long top-3 / short bottom-3 12-1 sector-SPDR portfolio (dollar neutral on DTB3 collateral, 5 bps per side, "
              f"50 bps/yr borrow), hold months {j['labels'][0]}..{j['labels'][1]} ({j['n']} months). Filter at month-end t: "
              f"SPY 24-month return < 0 AND SPY 126-day vol above the 80th percentile of its expanding daily distribution from "
              f"1994 -> short leg 0, long leg halved for t+1: {pr['active_months']} activation months in {pr['n_runs']} runs, "
              f"{pr['n_episodes']} episodes after merging gaps <= {T311_MERGE_GAP} months ({', '.join(j['episodes']) or 'none'}). "
              f"Worst rolling 3-month return filtered {_pc(pr['worst3'])} vs base {_pc(j['base_worst3'])}; random filters "
              f"re-placing the filter's own spells: 95th pct {_pc(pr['null_q95'])}, filter better than "
              f"{_pc(pr['share_better_than'])} of them (raw p {pr['p']:.4f}); Holm over the 24 declared trials (bear 12/24 x vol "
              f"70/80/90 x both legs/short only x binary/Daniel-Moskowitz past-only scale; "
              f"{sum(1 for x in fam.values() if x['p'] < ALPHA)} with raw p < 0.05) "
              + (f"adjusted p {j['holm']['adj']:.4f}" if j['holm']['adj'] is not None else "bounded")
              + f". Excess Sharpe filtered {_s(sh.get('sharpe_a'), 2)} vs base {_s(sh.get('sharpe_b'), 2)}: difference "
              f"{_s(sh.get('diff'))} ({_ci(sh.get('ci'))}; need lower > {T311_SHARPE_THR}). The crypto variant (CMC point-in-"
              f"time listings, not archived) lies outside the claim and its 24-trial grid: not a criterion — " + j["why"])
    stat = {"n_months": j["n"], "window": j["labels"], "worst3_filtered": pr["worst3"], "worst3_base": j["base_worst3"],
            "null_q95": pr["null_q95"], "share_null_worse": pr["share_better_than"], "p": pr["p"], "holm": j["holm"],
            "episodes": j["episodes"], "n_episodes": pr["n_episodes"], "active_months": pr["active_months"],
            "sharpe_filtered": sh.get("sharpe_a"), "sharpe_base": sh.get("sharpe_b"), "sharpe_diff": sh.get("diff"),
            "sharpe_ci": sh.get("ci"), "family": fam, "crypto_variant": "not archived (CMC historical listings); outside the claim",
            "criteria": j["criteria"], "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-317 crisis-alpha smile ==

T317_SLEEVES = ("SPY", "QQQ", "EFA", "TLT", "IEF", "GLD", "SLV", "DBC")
T317_BTC = "BTC-USD"
T317_MIN_N = 100
T317_START = "2000-01"
T317_LAMBDA = 60.0 / 61.0      # EWMA with a 60-day centre of mass
T317_TARGET = 0.10
T317_CAP = 2.0
T317_COST = 5e-4
T317_BORROW = 0.005
T317_N_SIM = 1000
T317_QBLOCK = 4                # quarters
T317_MBLOCK = 12               # months (monthly-regression trials: the same 1-year span)
T317_FAMILY = tuple((freq, btc, pos) for freq in ("quarterly", "monthly") for btc in (False, True) for pos in ("LS", "LF"))
T317_PRIMARY = ("quarterly", False, "LS")
T317_CRISES = {"2000-02": ("2000", "2001", "2002"), "2008": ("2008",), "2020": ("2020",), "2022": ("2022",)}


def _t317_blocks(sleeves: dict, bills: Bills, master_days: Sequence[str]) -> dict:
    """Per-sleeve hold-block summaries on the master (SPY) calendar. Block j = sessions (ex_j, ex_{j+1}]: 'body' =
    (ex_j, me_{j+1}], 'last' = ex_{j+1}; all in daily EXCESS returns over DTB3."""
    days = list(master_days)
    g = month_grid(days)
    me, ex = g["me"], g["ex"]
    C = bill_logcum(bills, days)
    rfd = np.r_[np.nan, np.exp(np.diff(C)) - 1]
    X = {}
    for s, (dd, a) in sleeves.items():
        idx = {d: k for k, d in enumerate(dd)}
        px = np.full(len(days), np.nan)
        lastv = np.nan
        first = dd[0] if dd else "9999"
        for i, d in enumerate(days):
            if d in idx:
                lastv = a[idx[d]]
            px[i] = lastv if d >= first else np.nan
        X[s] = np.r_[np.nan, px[1:] / px[:-1] - 1] - rfd
    J = me.size - 1
    out = {"months": g["months"], "labels": [days[i][:7] for i in ex[:-1]], "J": J, "X": X, "me": me, "ex": ex, "days": days}
    out["body_idx"] = [(int(ex[j]) + 1, int(me[j + 1])) for j in range(J)]
    out["last_idx"] = [int(ex[j + 1]) for j in range(J)]
    out["head_idx"] = int(ex[0])
    return out


def _block_summary(x: np.ndarray, body_idx, last_idx, head_idx, lam: float) -> dict:
    """body return, last-day return, EWMA body accrual C = (1-lam) sum lam^(n-k) x_k^2, body length, head return."""
    J = len(body_idx)
    body, C, nb, last = np.empty(J), np.empty(J), np.empty(J, int), np.empty(J)
    for j, (a, b) in enumerate(body_idx):
        seg = x[a:b + 1]
        body[j] = np.prod(1 + seg) - 1 if seg.size else 0.0
        nb[j] = seg.size
        w = lam ** np.arange(seg.size - 1, -1, -1)
        C[j] = (1 - lam) * float((w * seg * seg).sum()) if seg.size else 0.0
        last[j] = x[last_idx[j]]
    return {"body": body, "C": C, "nb": nb, "last": last, "head": float(x[head_idx])}


def _t317_engine(S: dict, active: np.ndarray, pos: str, sig2_0: np.ndarray, lam: float = T317_LAMBDA) -> np.ndarray:
    """TSMOM 12-1 portfolio excess returns on block summaries. S: {'body','C','nb','last'} each (Q, J, K) and 'head' (Q, K);
    active (J, K) bool. Returns (Q, J) portfolio excess returns of each hold block (NaN when nothing is active)."""
    body, Cb, nb, last = S["body"], S["C"], S["nb"], S["last"]
    Q, J, K = body.shape
    # last_{j-1} = the return on fill day ex_j (for j = 0 the 'head', the first fill day's return)
    lastprev = np.concatenate([S["head"][:, None, :], last[:, :-1]], axis=1)
    # EWMA variance at decision close me_j: sig(me_0) = seed; sig(ex_j) = lam sig(me_j) + (1 - lam) last_{j-1}^2;
    # sig(me_{j+1}) = lam^{n_body_j} sig(ex_j) + C_body_j
    sig_me = np.empty((Q, J, K))
    sig_me[:, 0] = np.repeat(sig2_0[None, :], Q, axis=0)
    for j in range(J - 1):
        sig_ex = lam * sig_me[:, j] + (1 - lam) * lastprev[:, j] ** 2
        sig_me[:, j + 1] = (lam ** nb[:, j]) * sig_ex + Cb[:, j]
    # month-end log return me_j -> me_{j+1} = log(1 + last_{j-1}) + log(1 + body_j)
    lme = np.log1p(np.maximum(lastprev, -0.999999)) + np.log1p(np.maximum(body, -0.999999))   # month j+1 ME log return
    cs = np.concatenate([np.zeros((Q, 1, K)), np.cumsum(lme, axis=1)], axis=1)
    # 12-1 signal at decision j: ME months j-11..j-1 -> lme indices j-12..j-2
    sig = np.full((Q, J, K), np.nan)
    jj = np.arange(12, J)
    sig[:, jj] = cs[:, jj - 1] - cs[:, jj - 12]
    hold = (1 + body) * (1 + last) - 1
    vol = np.sqrt(np.maximum(sig_me, 1e-12) * 252.0)
    lev = np.minimum(T317_CAP, T317_TARGET / vol)
    s = np.where(sig > 0, 1.0, np.where(sig < 0, -1.0 if pos == "LS" else 0.0, 0.0))
    act = active[None] & np.isfinite(sig)
    N = act.sum(axis=2)
    w = np.where(act, s * lev, 0.0) / np.maximum(N, 1)[..., None]
    hold0 = np.where(np.isfinite(hold), hold, 0.0)
    pre = (w * hold0).sum(axis=2) - T317_BORROW * ((nb + 1) / 252.0)[..., 0] * np.where(w < 0, -w, 0.0).sum(axis=2)
    to = drift_turnover(w, hold0, pre)
    out = pre - T317_COST * to
    return np.where(N > 0, out, np.nan)


def _ols(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def _ols_nw(y: np.ndarray, X: np.ndarray, lag: int) -> tuple:
    """OLS coefficients and Newey-West (Bartlett, ``lag`` lags) standard errors."""
    n = y.size
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    u = X * e[:, None]
    S = u.T @ u
    for k in range(1, lag + 1):
        G = u[k:].T @ u[:-k]
        S += (1 - k / (lag + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    return b, np.sqrt(np.maximum(np.diag(V), 0.0))


def _gamma_rows(Y: np.ndarray, Xs: np.ndarray) -> np.ndarray:
    """Quadratic coefficient of each row's regression y = a + b x + g x^2 (batched normal equations)."""
    Y, Xs = np.atleast_2d(Y), np.atleast_2d(Xs)
    D = np.stack([np.ones_like(Xs), Xs, Xs * Xs], axis=2)
    A = np.einsum("qni,qnj->qij", D, D)
    bvec = np.einsum("qni,qn->qi", D, Y)
    try:
        sol = np.linalg.solve(A, bvec[..., None])[..., 0]
    except np.linalg.LinAlgError:
        sol = np.array([np.linalg.lstsq(A[i], bvec[i], rcond=None)[0] for i in range(A.shape[0])])
    return sol[:, 2]


def _aggregate(r: np.ndarray, labels: Sequence[str], freq: str, start: str) -> tuple:
    """(period keys, compounded returns (Q, nP)) of hold-block returns r (Q, J) over complete quarters or months."""
    groups = {}
    for j, l in enumerate(labels):
        if l < start:
            continue
        key = l if freq == "monthly" else f"{l[:4]}Q{(int(l[5:7]) - 1) // 3 + 1}"
        groups.setdefault(key, []).append(j)
    keys = [k for k in sorted(groups) if (freq == "monthly" or len(groups[k]) == 3)]
    lg = np.log1p(np.maximum(r, -0.999999))
    out = np.stack([np.expm1(lg[:, groups[k]].sum(axis=1)) for k in keys], axis=1) if keys else np.zeros((r.shape[0], 0))
    return keys, out


def _cbb_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def crisis_smile(sleeves: dict, bills: Bills, btc: Optional[tuple] = None, start: str = T317_START, min_n: int = T317_MIN_N,
                 family: Optional[Sequence[tuple]] = None, n_sim: Optional[int] = None, n_boot: Optional[int] = None,
                 reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-317 core. ``sleeves``: {sym: (days, adj)} including SPY (the master calendar and the regressor)."""
    family = T317_FAMILY if family is None else tuple(family)
    n_sim = T317_N_SIM if n_sim is None else n_sim
    nb_ = N_BOOT if n_boot is None else n_boot
    reps_ = REPS if reps is None else reps
    syms = list(sleeves)
    master = sleeves["SPY"][0]
    allsl = dict(sleeves)
    if btc is not None:
        allsl[T317_BTC] = btc
    B = _t317_blocks(allsl, bills, master)
    J = B["J"]
    summ = {s: _block_summary(np.nan_to_num(B["X"][s], nan=np.nan), B["body_idx"], B["last_idx"], B["head_idx"], T317_LAMBDA) for s in allsl}
    valid = {s: np.isfinite(summ[s]["body"]) & np.isfinite(summ[s]["last"]) for s in allsl}
    labels = B["labels"]

    def active_mask(names):
        A = np.zeros((J, len(names)), bool)
        for kk, s in enumerate(names):
            v = valid[s]
            for j in range(13, J):
                A[j, kk] = bool(v[j - 13:j + 1].all())
        return A

    def stack(names, src_summ, idx=None):
        f = lambda key: np.stack([src_summ[s][key] if idx is None else src_summ[s][key][idx] for s in names], axis=-1)
        return {"body": f("body"), "C": f("C"), "nb": f("nb"), "last": f("last")}

    def first_sig2(names):
        out = []
        for s in names:
            x = B["X"][s]
            ok = np.isfinite(x)
            out.append(float(np.mean(x[ok][:63] ** 2)) if ok.sum() else 1e-4)
        return np.array(out)

    def actual_run(names, pos):
        A = active_mask(names)
        S = stack(names, {s: {k: np.nan_to_num(v, nan=0.0) if isinstance(v, np.ndarray) else v for k, v in summ[s].items()} for s in names})
        S = {k: v[None] for k, v in S.items()}
        S["head"] = np.array([[np.nan_to_num(summ[s]["head"]) for s in names]])
        # each sleeve's EWMA starts at its own first block: zero accrual before, variance seeded at the first fill
        sig0 = first_sig2(names)
        r = _t317_engine(S, A, pos, sig0)
        # restart the EWMA properly for late sleeves: recompute with per-sleeve start by masking pre-start squares
        return r[0], A

    spy_hold = (1 + np.nan_to_num(summ["SPY"]["body"])) * (1 + np.nan_to_num(summ["SPY"]["last"])) - 1
    res = {}
    sims = {}
    for v in family:
        freq, with_btc, pos = v
        names = syms + ([T317_BTC] if with_btc and btc is not None else [])
        if with_btc and btc is None:
            res[v] = None
            continue
        r_act, A = actual_run(names, pos)
        ok_j = np.isfinite(r_act)
        r0 = np.where(ok_j, r_act, 0.0)
        keys, Y = _aggregate(r0[None], labels, freq, start)
        _, Xq = _aggregate(spy_hold[None], labels, freq, start)
        y, x = Y[0], Xq[0]
        lag = T317_QBLOCK if freq == "quarterly" else T317_MBLOCK
        D = np.column_stack([np.ones_like(x), x, x * x])
        coef, se = _ols_nw(y, D, lag)
        g_act = float(coef[2])
        # simulation null: i.i.d. resampling of whole hold blocks (all sleeves jointly), demeaned (driftless)
        skey = (tuple(names), pos)
        if skey not in sims:
            rng = np.random.default_rng(seed + (17 if with_btc else 0) + (1 if pos == "LF" else 0))
            pool = np.array([j for j in range(J) if all(valid[s][j] for s in names)], int)
            in_pool = np.zeros(len(B["days"]), bool)
            for j in pool:
                a_, b_ = B["body_idx"][j]
                in_pool[a_:b_ + 1] = True
                in_pool[B["last_idx"][j]] = True
            Xd, sig0 = {}, []
            for s in names:
                xx = B["X"][s]
                mu = float(np.nanmean(xx[in_pool])) if in_pool.any() else 0.0      # driftless: demean over the pool
                Xd[s] = xx - mu
                sig0.append(float(np.nanmean(Xd[s][in_pool] ** 2)) if in_pool.any() else 1e-4)
            sig0 = np.array(sig0)
            sd = {s: _block_summary(np.nan_to_num(Xd[s]), B["body_idx"], B["last_idx"], B["head_idx"], T317_LAMBDA) for s in names}
            if pool.size == 0:
                res[v] = None
                continue
            gs_q, gs_m, Ysims, Xsims = [], [], [], []
            done = 0
            while done < n_sim:
                c = min(100, n_sim - done)
                idx = pool[rng.integers(0, pool.size, size=(c, J))]
                S = {k: np.stack([sd[s][k][idx] for s in names], axis=-1) for k in ("body", "C", "nb", "last")}
                S["head"] = np.stack([sd[s]["last"][pool[rng.integers(0, pool.size, size=c)]] for s in names], axis=-1)
                rs = _t317_engine(S, A, pos, sig0)
                rs = np.where(np.isfinite(rs), rs, 0.0)
                spy_k = names.index("SPY")
                sh_ = (1 + S["body"][..., spy_k]) * (1 + S["last"][..., spy_k]) - 1
                Ysims.append(rs)
                Xsims.append(sh_)
                done += c
            sims[skey] = (np.concatenate(Ysims), np.concatenate(Xsims))
        Ysim_b, Xsim_b = sims[skey]
        _, Ys = _aggregate(Ysim_b, labels, freq, start)
        _, Xs = _aggregate(Xsim_b, labels, freq, start)
        g_sim = _gamma_rows(Ys, Xs)
        g_bar = float(g_sim.mean())
        se_sim = float(g_sim.std(ddof=1) / math.sqrt(g_sim.size)) if g_sim.size > 1 else 0.0
        # block bootstrap of the actual (y, x) pairs
        n = y.size
        blk = lag
        qs, ps = [], []
        for rep in range(reps_):
            rng = np.random.default_rng(seed + 1000 + rep)
            gb = []
            done = 0
            while done < nb_:
                c = min(1000, nb_ - done)
                ii = _cbb_idx(rng, n, blk, c)
                gb.append(_gamma_rows(y[ii], x[ii]))
                done += c
            gb = np.concatenate(gb)
            qs.append(np.quantile(gb, [0.025, 0.975]))
            ps.append(float((1 + np.sum(gb <= g_bar)) / (gb.size + 1)))
        qs = np.array(qs)
        ci_b = [float(qs[:, 0].mean() - g_bar), float(qs[:, 1].mean() - g_bar)]
        mc_b = float(qs[:, 0].std(ddof=1) / math.sqrt(reps_)) if reps_ > 1 else 0.0
        se_h = math.sqrt(float(se[2]) ** 2 + se_sim ** 2)
        z = NormalDist().inv_cdf(0.975)
        exc = g_act - g_bar
        ci_h = [exc - z * se_h, exc + z * se_h]
        p_h = 1 - NormalDist().cdf(exc / se_h) if se_h > 0 else (0.0 if exc > 0 else 1.0)
        res[v] = {"g": g_act, "g_sim": g_bar, "se_sim": se_sim, "excess": exc, "ci_boot": ci_b, "ci_boot_mc_se": math.sqrt(mc_b ** 2 + se_sim ** 2),
                  "p_boot": float(np.mean(ps)), "ci_hac": ci_h, "se_hac": float(se[2]), "p_hac": float(p_h), "n": int(n), "keys": keys,
                  "y": y, "x": x, "Ys": Ys, "Xs": Xs, "pct_in_sim": float(np.mean(g_sim < g_act)), "sim_sd": float(g_sim.std(ddof=1)) if g_sim.size > 1 else None}
    pk = T317_PRIMARY if res.get(T317_PRIMARY) else next(k for k in family if res.get(k))
    pv = res[pk]
    hb = holm_primary({k: (r["p_boot"] if r else None) for k, r in res.items()}, pk)
    hh = holm_primary({k: (r["p_hac"] if r else None) for k, r in res.items()}, pk)
    lo_b, se_b = pv["ci_boot"][0], pv["ci_boot_mc_se"]
    okb, nb_note = resolve(lo_b, se_b, 0.0, "gt")
    decb = resolve(pv["ci_boot"][1], se_b, 0.0, "lt")[0] is True
    okh = pv["ci_hac"][0] > 0
    dech = pv["ci_hac"][1] < 0
    c1 = all_constructions([(f"block bootstrap (4-quarter blocks) CI {_s(pv['ci_boot'][0], 2)} to {_s(pv['ci_boot'][1], 2)}{nb_note}", okb, decb),
                            (f"Newey-West HAC CI {_s(pv['ci_hac'][0], 2)} to {_s(pv['ci_hac'][1], 2)}", okh, dech)],
                           f"gamma minus simulated gamma ({_s(pv['excess'], 2)} = {_s(pv['g'], 2)} - {_s(pv['g_sim'], 2)}) > 0 with 95% CI excluding 0")
    c2 = all_constructions([holm_row(hb, "block-bootstrap p"), holm_row(hh, "HAC p")], f"Holm across the {len(family)} declared trials, adjusted p < 0.05")
    loco = {}
    yq, xq, keys = pv["y"], pv["x"], pv["keys"]
    for nm, yrs in T317_CRISES.items():
        keep = np.array([k[:4] not in yrs for k in keys])
        if keep.sum() < 8:
            loco[nm] = None
            continue
        ga = float(_gamma_rows(yq[keep][None], xq[keep][None])[0])
        gs = float(_gamma_rows(pv["Ys"][:, keep], pv["Xs"][:, keep]).mean())
        loco[nm] = ga - gs
    c3 = (f"leave-one-crisis-out keeps the sign (" + ", ".join(f"-{k} {_s(x_, 2)}" for k, x_ in loco.items() if x_ is not None) + ")",
          None if any(x_ is None for x_ in loco.values()) else all(x_ > 0 for x_ in loco.values()), False)
    v, why = _decide([c1, c2, c3], pv["n"], min_n, "quarters" if pk[0] == "quarterly" else "months")
    worst = None
    if yq.size >= 10:
        cut = np.quantile(xq, 0.1)
        worst = float(yq[xq <= cut].mean())
    crises = {nm: (float(yq[np.array([k[:4] in yrs for k in keys])].mean()) if any(k[:4] in yrs for k in keys) else None) for nm, yrs in T317_CRISES.items()}
    fam = {"|".join(map(str, k)): (None if r is None else {"excess": r["excess"], "p_boot": r["p_boot"], "p_hac": r["p_hac"], "n": r["n"]}) for k, r in res.items()}
    return {"n": pv["n"], "keys": [keys[0], keys[-1]] if keys else None, "primary": {k: pv[k] for k in ("g", "g_sim", "se_sim", "excess", "ci_boot", "ci_hac", "p_boot", "p_hac", "se_hac", "pct_in_sim", "sim_sd")},
            "holm_boot": hb, "holm_hac": hh, "loco": loco, "worst_decile_mean": worst, "crisis_means": crises, "family": fam,
            "criteria": [(c[0], c[1]) for c in (c1, c2, c3)], "verdict": v, "why": why}


def b6c_mom_trend_crisis_smile(archive):
    """T-317."""
    need = [dh(s) for s in T317_SLEEVES] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    sl = {s: (_daily(archive, dh(s))["days"], _daily(archive, dh(s))["adj"]) for s in T317_SLEEVES}
    btc = (_daily(archive, dh(T317_BTC))["days"], _daily(archive, dh(T317_BTC))["adj"]) if _has(archive, dh(T317_BTC)) else None
    j = crisis_smile(sl, bills, btc)
    p = j["primary"]
    reason = (f"12-1 TSMOM long/short on {', '.join(T317_SLEEVES)} (each from 13 complete hold months, 10% ex-ante vol from "
              f"a 60-day-centre-of-mass EWMA, cap 2x, equal risk across active sleeves, month-end signal filled at the next "
              f"close, 5 bps per side, 50 bps/yr borrow on shorts), quarterly excess returns {j['keys'][0]}..{j['keys'][1]} "
              f"({j['n']} quarters) on SPY's quarterly excess return and its square: gamma {_s(p['g'], 2)} (HAC s.e. "
              f"{_f(p['se_hac'], 2)}), mean gamma of {T317_N_SIM} driftless simulations (whole months of all sleeves' daily "
              f"excess returns resampled i.i.d. after demeaning: cross-correlation kept, autocorrelation removed) "
              f"{_s(p['g_sim'], 2)} (sd {_f(p['sim_sd'], 2)}; actual above {_pc(p['pct_in_sim'])} of them); excess "
              f"{_s(p['excess'], 2)}: block bootstrap {_ci(p['ci_boot'], 2)}, HAC {_ci(p['ci_hac'], 2)}; Holm over the 8 declared "
              f"trials (quarterly/monthly x with/without BTC x long-short/long-flat) "
              + (f"bootstrap-p adjusted {j['holm_boot']['adj']:.4f}, HAC-p adjusted {j['holm_hac']['adj']:.4f}" if j['holm_boot']['adj'] is not None and j['holm_hac']['adj'] is not None else "bounded")
              + "; leave-one-crisis-out excess " + ", ".join(f"-{k} {_s(x, 2)}" for k, x in j["loco"].items() if x is not None)
              + f". Diagnostics: mean portfolio return in SPY's worst-decile quarters {_pc(j['worst_decile_mean'], 2)}; crisis-year "
              f"means " + ", ".join(f"{k} {_pc(x, 2)}" for k, x in j["crisis_means"].items() if x is not None)
              + "; before 2002-08 only SPY and QQQ are active — " + j["why"])
    stat = {"n_quarters": j["n"], "window": j["keys"], **{k: p[k] for k in p}, "holm_boot": j["holm_boot"], "holm_hac": j["holm_hac"],
            "loco": j["loco"], "worst_decile_mean": j["worst_decile_mean"], "crisis_means": j["crisis_means"], "family": j["family"],
            "criteria": j["criteria"], "rule10": "calendar: month-end rebalancing, calendar quarters (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-310 vol-scaled trend DiD ==

T310_ASSETS = ("SPY", "QQQ", "GLD", "SLV", "EFA", "TLT", "BTC-USD", "ETH-USD")
T310_MIN_N = 300
T310_START = "1994-01"
T310_ESTIMATORS = ("ewma94", "rv21", "rv126", "yz21", "dvol_btc")
T310_FAMILY = tuple((e, tg, cap) for e in T310_ESTIMATORS for tg in (0.10, 0.15) for cap in (1.0, 2.0))   # 5 x 2 x 2 = 20
T310_PRIMARY = ("ewma94", 0.10, 2.0)
T310_CRYPTO_TARGET = 0.40
T310_CRYPTO_CAP = 1.0
T310_FIN_SPREAD = 0.005
T310_BLOCK = 60                # days
T310_N_BOOT_OTHER = 2000       # resamples behind the other 19 trials' Holm p-values (min p 1/2001 < 0.05/20)
T310_DECADES = (("1994", "2003"), ("2004", "2013"), ("2014", "2026"))
T310_REGIMES = ("2008", "2020", "2022")


def vol_estimates(dly: dict, crypto: bool, me_idx: np.ndarray, dvol: Optional[dict] = None) -> dict:
    """Annualised volatility estimates at each month-end index (own calendar) from returns through that day."""
    adj = dly["adj"]
    ppy = 365.0 if crypto else 252.0
    r = np.r_[np.nan, adj[1:] / adj[:-1] - 1]
    n = adj.size
    out = {}
    # EWMA 0.94, seeded with the mean square of the first 21 returns
    ew = np.full(n, np.nan)
    if n > 22:
        s2 = float(np.mean(r[1:22] ** 2))
        for i in range(1, n):
            s2 = 0.94 * s2 + 0.06 * r[i] * r[i] if i >= 22 else s2
            ew[i] = s2
    out["ewma94"] = np.sqrt(ew[me_idx] * ppy)
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(r))]
    cs2 = np.r_[0.0, np.cumsum(np.nan_to_num(r) ** 2)]
    for L, key in ((21, "rv21"), (126, "rv126")):
        v = np.full(me_idx.size, np.nan)
        for k, i in enumerate(me_idx):
            if i - L + 1 >= 1:
                s1, s2_ = cs[i + 1] - cs[i - L + 1], cs2[i + 1] - cs2[i - L + 1]
                v[k] = math.sqrt(max((s2_ - s1 * s1 / L) / (L - 1), 0.0) * ppy)
        out[key] = v
    o, h, lw, c = dly["open"], dly["high"], dly["low"], adj
    yz = np.full(me_idx.size, np.nan)
    L = 21
    kk = 0.34 / (1.34 + (L + 1) / (L - 1))
    with np.errstate(divide="ignore", invalid="ignore"):
        lo_ = np.log(o[1:] / c[:-1])
        lc_ = np.log(c[1:] / o[1:])
        u_ = np.log(h[1:] / o[1:])
        d_ = np.log(lw[1:] / o[1:])
    for k, i in enumerate(me_idx):
        a = i - L                                    # returns i-L+1..i -> arrays index i-L..i-1
        if a < 0:
            continue
        so, sc, su, sd = lo_[a:i], lc_[a:i], u_[a:i], d_[a:i]
        if not (np.isfinite(so).all() and np.isfinite(sc).all() and np.isfinite(su).all() and np.isfinite(sd).all()):
            continue
        rs = float(np.mean(su * (su - sc) + sd * (sd - sc)))
        yz[k] = math.sqrt(max(so.var(ddof=1) + kk * sc.var(ddof=1) + (1 - kk) * rs, 0.0) * ppy)
    out["yz21"] = yz
    out["dvol_btc"] = out["ewma94"].copy()
    if dvol is not None:
        days = dly["days"]
        for k, i in enumerate(me_idx):
            x = dvol.get(days[i])
            if x is not None and x > 0:
                out["dvol_btc"][k] = x / 100.0
    return out


def _t310_prepare(assets: dict, bills: Bills, master: Sequence[str], dvol: Optional[dict]) -> dict:
    days = list(master)
    g = month_grid(days)
    C = bill_logcum(bills, days)
    ords = np.array([_ord(d) for d in days], float)
    prep = {"days": days, "g": g, "C": C, "ords": ords, "assets": {}}
    for s, dly in assets.items():
        crypto = s in CRYPTO
        own = month_grid(dly["days"])
        est = vol_estimates(dly, crypto, own["me"], dvol if s == "BTC-USD" else None)
        Cown = bill_logcum(bills, dly["days"])
        M = dly["adj"][own["me"]]
        Cme = Cown[own["me"]]
        sig = np.full(own["me"].size, np.nan)
        for k in range(12, own["me"].size):
            sig[k] = M[k - 1] / M[k - 12] * math.exp(-(Cme[k - 1] - Cme[k - 12])) - 1
        idx = {d: k for k, d in enumerate(dly["days"])}
        px = np.full(len(days), np.nan)
        lastv = np.nan
        for i, d in enumerate(days):
            if d in idx:
                lastv = dly["adj"][idx[d]]
            px[i] = lastv if d >= dly["days"][0] else np.nan
        prep["assets"][s] = {"crypto": crypto, "own_month": {m: k for k, m in enumerate(own["months"])}, "est": est, "sig": sig, "px": px,
                             "cost": _cost(s)}
    return prep


def _t310_weights(prep: dict, kind: str, est: Optional[str], target: float, cap: float) -> tuple:
    """Per decision month k (master grid): {sym: weight} for 'tsmom' / 'bh', scaled when ``est`` is given."""
    g = prep["g"]
    W = []
    for k, m in enumerate(g["months"][:-1]):
        w = {}
        for s, A in prep["assets"].items():
            j = A["own_month"].get(m)
            if j is None or j < 12 or not np.isfinite(A["sig"][j]) or not np.isfinite(A["px"][g["ex"][k]]):
                continue
            base = (1.0 if A["sig"][j] > 0 else 0.0) if kind == "tsmom" else 1.0
            if est is not None:
                sg = A["est"][est][j]
                if not (np.isfinite(sg) and sg > 0):
                    sg = A["est"]["ewma94"][j]
                if not (np.isfinite(sg) and sg > 0):
                    continue
                tg, cp = (T310_CRYPTO_TARGET, T310_CRYPTO_CAP) if A["crypto"] else (target, cap)
                base *= min(cp, tg / sg)
            w[s] = base
        W.append(w)
    return W


def _t310_daily(prep: dict, W: list) -> tuple:
    """Daily portfolio returns and excess returns (master calendar) of monthly-rebalanced sleeves: each active sleeve
    holds 1/N of capital, w of it in the asset and 1 - w in cash (DTB3 for ETFs, USD for crypto) or borrowed at DTB3 + 50
    bps when w > 1; within the month the book drifts; costs on drift-adjusted turnover at each fill."""
    g, C, ords = prep["g"], prep["C"], prep["ords"]
    ex = g["ex"]
    rets, days_out, rfs = [], [], []
    prev_expo = {}
    for k in range(len(W)):
        a, b = int(ex[k]), int(ex[k + 1])
        w = W[k]
        seg = np.arange(a + 1, b + 1)
        bill = np.exp(C[seg] - C[a])
        borrow = bill * np.exp(T310_FIN_SPREAD * (ords[seg] - ords[a]) / 365.0)
        N = len(w)
        if N == 0:
            V = bill
            cost = 0.0
            new_expo = {}
        else:
            V = np.zeros(seg.size)
            new_expo = {}
            for s, ws in w.items():
                A = prep["assets"][s]
                G = A["px"][seg] / A["px"][a]
                cash = (np.ones(seg.size) if A["crypto"] else bill) if ws <= 1 else borrow
                V = V + (ws * G + (1 - ws) * cash) / N
                new_expo[s] = (ws / N, A["px"][b] / A["px"][a])
            cost = 0.0
            for s in set(w) | set(prev_expo):
                tgt = w.get(s, 0.0) / N
                old = prev_expo.get(s, 0.0)
                cost += prep["assets"][s]["cost"] * abs(tgt - old)
        Vp = np.r_[1.0, V[:-1]]
        r = V / Vp - 1
        r[0] = (1 + r[0]) * (1 - cost) - 1
        rets.append(r)
        rfs.append(np.exp(np.diff(np.r_[C[a], C[seg]])) - 1)
        days_out.extend(prep["days"][i] for i in seg)
        Vend = V[-1] if V.size else 1.0
        prev_expo = {s: e * gr / Vend for s, (e, gr) in new_expo.items()} if N else {}
    r = np.concatenate(rets) if rets else np.zeros(0)
    rf = np.concatenate(rfs) if rfs else np.zeros(0)
    return days_out, r, r - rf


def _prefix(x: np.ndarray, block: int) -> tuple:
    xx = np.r_[x, x[:block]]
    return np.r_[0.0, np.cumsum(xx)], np.r_[0.0, np.cumsum(xx * xx)]


def joint_sharpe_boot(series: Sequence[np.ndarray], block: int, n_boot: int, seed: int, ppy: float = 252.0) -> np.ndarray:
    """Circular block bootstrap (same blocks for every series, cut to n) of annualised Sharpe ratios: (n_boot, k)."""
    n = series[0].size
    nb = math.ceil(n / block)
    lens = np.full(nb, block)
    lens[-1] = n - block * (nb - 1)
    pre = [_prefix(np.asarray(x, float), block) for x in series]
    rng = np.random.default_rng(seed)
    out = np.empty((n_boot, len(series)))
    done = 0
    while done < n_boot:
        c = min(2000, n_boot - done)
        st = rng.integers(0, n, size=(c, nb))
        for q, (p1, p2) in enumerate(pre):
            s1 = (p1[st + lens[None]] - p1[st]).sum(axis=1)
            s2 = (p2[st + lens[None]] - p2[st]).sum(axis=1)
            mu = s1 / n
            var = np.maximum((s2 - n * mu * mu) / (n - 1), 1e-30)
            out[done:done + c, q] = mu / np.sqrt(var) * math.sqrt(ppy)
        done += c
    return out


def _did(sr: np.ndarray) -> np.ndarray:
    """[SR(scaled TSMOM) - SR(TSMOM)] - [SR(scaled B&H) - SR(B&H)] from columns (sT, uT, sB, uB)."""
    return (sr[..., 0] - sr[..., 1]) - (sr[..., 2] - sr[..., 3])


def vol_scaled_did(assets: dict, bills: Bills, dvol: Optional[dict] = None, start: str = T310_START, min_n: int = T310_MIN_N,
                   family: Optional[Sequence[tuple]] = None, n_boot: Optional[int] = None, n_boot_other: Optional[int] = None,
                   reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-310 core. ``assets``: {sym: daily dict (days, adj, open, high, low)} with SPY as the master calendar."""
    family = T310_FAMILY if family is None else tuple(family)
    nb_ = N_BOOT if n_boot is None else n_boot
    nbo = T310_N_BOOT_OTHER if n_boot_other is None else n_boot_other
    reps_ = REPS if reps is None else reps
    prep = _t310_prepare(assets, bills, assets["SPY"]["days"], dvol)
    months = prep["g"]["months"]
    ex = prep["g"]["ex"]
    W_bh = _t310_weights(prep, "bh", None, 0, 0)
    # first decision whose hold month is in the window and has at least one active asset
    keep_k = [k for k, m in enumerate(months[:-1]) if _month_add(m, 1) >= start and W_bh[k]]
    k0 = keep_k[0] if keep_k else 0
    keep_k = list(range(k0, len(months) - 1))
    a0 = int(ex[k0] - ex[0])                       # sessions of the holds before k0 (left out of every series)

    def run(kind, est, tg, cap):
        W = _t310_weights(prep, kind, est, tg, cap)
        for k in range(k0):
            W[k] = {}
        d, r, x = _t310_daily(prep, W)
        return d[a0:], r[a0:], x[a0:]

    days, _, uT = run("tsmom", None, 0, 0)
    _, _, uB = run("bh", None, 0, 0)
    res = {}
    for v in family:
        est, tg, cap = v
        _, _, sT = run("tsmom", est, tg, cap)
        _, _, sB = run("bh", est, tg, cap)
        S4 = [sT, uT, sB, uB]
        obs = float(_did(np.array([[_sr_ann(z, 252) or 0.0 for z in S4]]))[0])
        if v == T310_PRIMARY:
            qs, ps = [], []
            for rep in range(reps_):
                bs = _did(joint_sharpe_boot(S4, T310_BLOCK, nb_, seed + rep))
                qs.append(np.quantile(bs, [0.025, 0.975]))
                ps.append(float((1 + np.sum(bs <= 0)) / (bs.size + 1)))
            qs = np.array(qs)
            ci = [float(qs[:, 0].mean()), float(qs[:, 1].mean())]
            mc = [float(qs[:, 0].std(ddof=1) / math.sqrt(reps_)) if reps_ > 1 else 0.0, float(qs[:, 1].std(ddof=1) / math.sqrt(reps_)) if reps_ > 1 else 0.0]
            p = float(np.mean(ps))
        else:
            bs = _did(joint_sharpe_boot(S4, T310_BLOCK, nbo, seed + 50 + family.index(v)))
            ci = [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]
            mc = [0.0, 0.0]
            p = float((1 + np.sum(bs <= 0)) / (bs.size + 1))
        res[v] = {"did": obs, "ci": ci, "ci_mc_se": mc, "p": p, "series": S4,
                  "sharpes": [_sr_ann(z, 252) for z in S4]}
    pk = T310_PRIMARY if T310_PRIMARY in res else family[0]
    pv = res[pk]
    h = holm_primary({k: r["p"] for k, r in res.items()}, pk)
    yrs = np.array([d[:4] for d in days])
    dec = {}
    for a, z in T310_DECADES:
        m = (yrs >= a) & (yrs <= z)
        if m.sum() >= 250:
            dec[f"{a}-{z}"] = float(_did(np.array([[_sr_ann(s[m], 252) or 0.0 for s in pv["series"]]]))[0])
    reg = {}
    for y in T310_REGIMES:
        m = yrs == y
        if m.sum() >= 100:
            reg[y] = float(_did(np.array([[_sr_ann(s[m], 252) or 0.0 for s in pv["series"]]]))[0])
    ci_t = {"ci": pv["ci"], "ci_mc_se": pv["ci_mc_se"]}
    crit = [_ci_crit(ci_t, "gt", 0.0, f"DiD {_s(pv['did'])} > 0 with joint 60-day block-bootstrap 95% CI excluding 0"),
            holm_row(h, f"Holm-adjusted across the {len(family)} declared trials (raw p {pv['p']:.4f})"),
            (f"DiD positive in at least 2 of 3 decades ({', '.join(f'{k} {_s(x)}' for k, x in dec.items())})",
             None if len(dec) < 3 else sum(1 for x in dec.values() if x > 0) >= 2, False)]
    n_m = len(keep_k)
    v, why = _decide(crit, n_m, min_n, "months")
    fam_sr = [_sr_pp(r["series"][0]) for r in res.values()]
    ds = family_dsr(pv["series"][0], fam_sr, len(family) + T300_N_TRIALS)
    return {"n": int(n_m), "n_days": int(len(days)), "days": [days[0], days[-1]] if days else None, "primary": {k: pv[k] for k in ("did", "ci", "p", "sharpes")},
            "holm": h, "decades": dec, "regimes": reg, "dsr_report": ds,
            "family": {"|".join(map(str, k)): {"did": r["did"], "p": r["p"]} for k, r in res.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why, "prep": prep, "k0": k0}


def _t310_per_asset(j: dict) -> dict:
    """Per-asset DiD point estimates for the primary trial (diagnostic): each asset alone, from its own first month."""
    prep = j["prep"]
    out = {}
    for s in prep["assets"]:
        sub = {**prep, "assets": {s: prep["assets"][s]}}
        first = next((k for k, w in enumerate(_t310_weights(sub, "bh", None, 0, 0)) if w and k >= j["k0"]), None)
        if first is None:
            out[s] = None
            continue
        a0 = int(prep["g"]["ex"][first]) - int(prep["g"]["ex"][0])
        ser = []
        for kind, est in (("tsmom", T310_PRIMARY[0]), ("tsmom", None), ("bh", T310_PRIMARY[0]), ("bh", None)):
            W = _t310_weights(sub, kind, est, T310_PRIMARY[1], T310_PRIMARY[2])
            for k in range(first):
                W[k] = {}
            ser.append(_t310_daily(sub, W)[2][a0:])
        out[s] = float(_did(np.array([[_sr_ann(z, 252) or 0.0 for z in ser]]))[0]) if ser[0].size > 250 else None
    return out


def b6c_mom_vol_scaled_trend_did(archive):
    """T-310."""
    need = [dh(s) for s in T310_ASSETS] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    assets = {s: _daily(archive, dh(s)) for s in T310_ASSETS}
    dvol = _series(archive, DVOL_B) if _has(archive, DVOL_B) else None
    j = vol_scaled_did(assets, bills, dvol)
    pa = _t310_per_asset(j)
    p = j["primary"]
    sr = p["sharpes"]
    reason = (f"Pooled equal-capital sleeves of {', '.join(T310_ASSETS)} (each from its 13th month-end), month-end decisions "
              f"filled at the next SPY session's close, daily returns {j['days'][0]}..{j['days'][1]} ({j['n']} months, "
              f"{j['n_days']} sessions), DTB3 cash (crypto: USD), leverage above 1x at DTB3 + 50 bps, 2/5/35 bps per side on "
              f"all drift-adjusted turnover. Primary trial (EWMA 0.94, 10% target, cap 2x; crypto 40%, cap 1x): excess Sharpe "
              f"scaled TSMOM {_s(sr[0], 3)}, TSMOM {_s(sr[1], 3)}, scaled B&H {_s(sr[2], 3)}, B&H {_s(sr[3], 3)}: DiD "
              f"{_s(p['did'])} ({_ci(p['ci'])}, joint circular block bootstrap of the four daily series, 60-day blocks, {N_BOOT:,} "
              f"draws x {REPS} seeds), one-sided p {p['p']:.4f}; Holm over the 20 declared trials (EWMA/RV21/RV126/Yang-Zhang 21/"
              f"DVOL-for-BTC x target 10/15% x cap 1/2x; DVOL replaces BTC's EWMA from 2021-03-24 only) "
              + (f"adjusted p {j['holm']['adj']:.4f}" if j['holm']['adj'] is not None else "bounded")
              + f"; decades {', '.join(f'{k} {_s(x)}' for k, x in j['decades'].items())}. Reported: regimes "
              + ", ".join(f"{k} {_s(x)}" for k, x in j["regimes"].items()) + "; per-asset DiD "
              + ", ".join(f"{s} {_s(x, 2)}" for s, x in pa.items() if x is not None)
              + f"; DSR of scaled TSMOM at {j['dsr_report']['n_trials']} trials (20 + T-300's 104) {_f(j['dsr_report']['dsr'])} — " + j["why"])
    stat = {"n_months": j["n"], "n_days": j["n_days"], "window": j["days"], "did": p["did"], "ci": p["ci"], "p": p["p"],
            "sharpes_sT_uT_sB_uB": sr, "holm": j["holm"], "decades": j["decades"], "regimes": j["regimes"], "per_asset_did": pa,
            "dsr_report": j["dsr_report"], "family": j["family"], "dvol_archived": dvol is not None,
            "criteria": j["criteria"], "rule10": "calendar: month-end rebalancing named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-481 cross-asset TSMOM ==

T481_MIN_N = 380
T481_START = "1994-01"
T481_DURATION = 8.0            # the library's constant modified duration of the synthetic 10-year bond
T481_COST = 2e-4
T481_FAMILY = tuple((px, pos, lb) for px in ("IEF", "TLT", "synthetic") for pos in ("LF", "LS") for lb in (12, 6))   # 12
T481_PRIMARY = ("IEF", "LF", 12)
T481_REGIMES = (("1994-01", "2007-12"), ("2008-01", "2021-12"), ("2022-01", "2026-12"))


def par_duration(y_pct: float) -> float:
    """Modified duration of a 10-year par bond with semiannual coupons at yield y (sensitivity only)."""
    y = max(y_pct / 100.0, 1e-4)
    return (1 - (1 + y / 2) ** -20) / y


def synthetic_bond(y: np.ndarray, duration: Optional[float] = T481_DURATION) -> np.ndarray:
    """Monthly return of a constant-maturity 10-year bond from month-end yields (percent): carry y_{t-1}/12 minus
    duration x the yield change; ``duration`` None uses the yield-dependent par-bond duration."""
    y = np.asarray(y, float) / 100.0
    D = np.full(y.size - 1, duration) if duration is not None else np.array([par_duration(v * 100) for v in y[:-1]])
    return y[:-1] / 12.0 - D * np.diff(y)


def _t481_monthly(spy: tuple, ief: tuple, tlt: tuple, dgs10: dict, bills: Bills, duration: Optional[float] = T481_DURATION) -> dict:
    """Month-end calendar (SPY's last session; before SPY, DGS10's last print) with SPY/IEF/TLT month-end prices, the
    month-end 10-year yield known at the next session (available_at respected), bill growth and the bond proxies."""
    sd, sa = spy
    g = month_grid(sd)
    spy_me = {m: sd[i] for m, i in zip(g["months"], g["me"])}
    yk = sorted(dgs10)
    last_y = {}
    for d in yk:
        last_y[d[:7]] = d
    m0 = _month_add(min(spy_me), -24)
    months, m = [], m0
    endm = max(spy_me)
    while m <= endm:
        months.append(m)
        m = _month_add(m, 1)
    me_day = [spy_me.get(m) or last_y.get(m) for m in months]
    ok = [d is not None for d in me_day]
    months = [m for m, o in zip(months, ok) if o]
    me_day = [d for d in me_day if d is not None]
    yv = np.full(len(months), np.nan)
    for i, d in enumerate(me_day):
        j = np.searchsorted(yk, d, side="right") - 1
        while j >= 0:
            val, av = dgs10[yk[j]]
            nxt = date.fromordinal(_ord(d) + 4).isoformat()
            if av[:10] <= nxt:                              # known by the fill (next session, <= 4 calendar days)
                yv[i] = val
                break
            j -= 1
    C = bill_logcum(bills, me_day)
    bill = np.r_[np.nan, np.exp(np.diff(C)) - 1]

    def px(series):
        dd, a = series
        idx = {d: k for k, d in enumerate(dd)}
        return np.array([a[idx[d]] if d in idx else np.nan for d in me_day], float)

    P = {"SPY": px(spy), "IEF": px(ief), "TLT": px(tlt)}
    ret = {k: np.r_[np.nan, v[1:] / v[:-1] - 1] for k, v in P.items()}
    syn = np.r_[np.nan, synthetic_bond(yv, duration)]
    proxies = {"IEF": np.where(np.isfinite(ret["IEF"]), ret["IEF"], syn), "TLT": ret["TLT"], "synthetic": syn}
    return {"months": months, "me_day": me_day, "y": yv, "bill": bill, "ret": ret, "syn": syn, "proxies": proxies, "P": P}


def _cum_ex(r: np.ndarray, bill: np.ndarray, t: int, a: int, b: int) -> float:
    """Cumulative excess return over months t-a+1 .. t-b (month-end t-a to month-end t-b)."""
    seg = slice(t - a + 1, t - b + 1)
    rr, bb = r[seg], bill[seg]
    if rr.size == 0 or not (np.isfinite(rr).all() and np.isfinite(bb).all()):
        return float("nan")
    return float(np.prod(1 + rr) / np.prod(1 + bb) - 1)


def cross_asset_tsmom(spy: tuple, ief: tuple, tlt: tuple, dgs10: dict, bills: Bills, start: str = T481_START,
                      min_n: int = T481_MIN_N, family: Optional[Sequence[tuple]] = None, n_boot: Optional[int] = None,
                      reps: Optional[int] = None, seed: int = SEED, duration: Optional[float] = T481_DURATION) -> dict:
    """T-481 core. ``dgs10``: {day: (value %, available_at)}."""
    family = T481_FAMILY if family is None else tuple(family)
    D = _t481_monthly(spy, ief, tlt, dgs10, bills, duration)
    mi = {m: k for k, m in enumerate(D["months"])}
    sd, sa = spy
    g = month_grid(sd)
    C = bill_logcum(bills, sd)
    R = sa[g["ex"][1:]] / sa[g["ex"][:-1]] - 1
    rf = np.exp(C[g["ex"][1:]] - C[g["ex"][:-1]]) - 1
    labels = [sd[i][:7] for i in g["ex"][:-1]]
    spy_r, bill = D["ret"]["SPY"], D["bill"]

    def signals(px, lb, shift=0):
        """(e, b) at each SPY decision month; NaN when undefined."""
        e, b = [], []
        for t_spy, m in enumerate(g["months"][:-1]):
            t = mi.get(m)
            if t is None:
                e.append(np.nan); b.append(np.nan)
                continue
            ce = _cum_ex(spy_r, bill, t, lb, 1)
            tb = t - shift
            cb = _cum_ex(D["proxies"][px], bill, tb, lb, 1) if tb - lb >= 0 else float("nan")
            e.append(np.sign(ce) if np.isfinite(ce) else np.nan)
            b.append(np.sign(cb) if np.isfinite(cb) else np.nan)
        return np.array(e), np.array(b)

    def run(px, pos, lb, shift=0):
        e, b = signals(px, lb, shift)
        ok = np.isfinite(e) & np.isfinite(b) & np.array([l >= start for l in labels])
        idx = np.where(ok)[0]
        cross = (e[idx] + b[idx]) / 2
        own = e[idx].copy()
        if pos == "LF":
            cross, own = np.maximum(cross, 0), np.maximum(own, 0)
        rc = _net_single(cross, R[idx], rf[idx], T481_COST)
        ro = _net_single(own, R[idx], rf[idx], T481_COST)
        return {"idx": idx, "cross_ex": rc - rf[idx], "own_ex": ro - rf[idx], "pos": cross, "e": e[idx], "b": b[idx]}

    res = {v: run(*v) for v in family}
    pk = T481_PRIMARY if T481_PRIMARY in res else family[0]
    pv = res[pk]
    n = pv["idx"].size
    sh = sharpe_test(pv["cross_ex"], pv["own_ex"], n_boot, seed, reps)
    d_strat = family_dsr(pv["cross_ex"], [_sr_pp(r["cross_ex"]) for r in res.values()], len(family))
    d_diff = family_dsr(pv["cross_ex"] - pv["own_ex"], [_sr_pp(r["cross_ex"] - r["own_ex"]) for r in res.values()], len(family))
    pl = run(pk[0], pk[1], pk[2], shift=12)
    shp = sharpe_test(pl["cross_ex"], pl["own_ex"], n_boot, seed, reps)
    lo, hi = shp.get("ci") or (None, None)
    se_lo, se_hi = shp.get("ci_mc_se") or (0.0, 0.0)
    if lo is None:
        pl_ok = None
    else:
        lo_below = resolve(lo, se_lo, 0.0, "lt")[0]
        hi_above = resolve(hi, se_hi, 0.0, "gt")[0]
        lo_above = resolve(lo, se_lo, 0.0, "gt")[0]
        hi_below = resolve(hi, se_hi, 0.0, "lt")[0]
        pl_ok = True if (lo_below and hi_above) else (False if (lo_above or hi_below) else None)
    crit = [_ci_crit(sh, "gt", 0.0, "Sharpe(cross-asset) - Sharpe(own TSMOM) > 0 with 95% CI excluding 0 (paired studentized CBB)"),
            all_constructions([dsr_row(d_strat, "cross-asset excess returns"), dsr_row(d_diff, "cross-asset minus own series")],
                              f"DSR > {DSR_PASS} over {len(family)} trials under both readings"),
            (f"placebo (bond signal lagged 12 months) Sharpe difference {_s(shp.get('diff'))} with 95% CI including 0 ({_ci(shp.get('ci'))})",
             pl_ok, pl_ok is False and n >= min_n)]
    v, why = _decide(crit, n, min_n, "months")
    labs = [labels[i] for i in pv["idx"]]
    reg = {}
    for a, z in T481_REGIMES:
        m = np.array([a <= l <= z for l in labs])
        if m.sum() >= 12:
            reg[f"{a[:4]}-{z[:4]}"] = {"n": int(m.sum()), "diff": (_sr_ann(pv["cross_ex"][m]) or 0) - (_sr_ann(pv["own_ex"][m]) or 0)}
    # synthetic bond vs IEF, 2002-08 onwards
    ief_r, syn = D["ret"]["IEF"], D["syn"]
    both = np.isfinite(ief_r) & np.isfinite(syn)
    chk = {}
    if both.sum() >= 24:
        dlt = syn[both] - ief_r[both]
        chk = {"months": int(both.sum()), "corr": float(np.corrcoef(syn[both], ief_r[both])[0, 1]), "te_ann": float(dlt.std(ddof=1) * math.sqrt(12)),
               "mean_diff_ann": float(dlt.mean() * 12)}
        agree, tot = 0, 0
        for t in range(12, len(D["months"])):
            a_ = _cum_ex(ief_r, bill, t, 12, 1)
            b_ = _cum_ex(syn, bill, t, 12, 1)
            if np.isfinite(a_) and np.isfinite(b_):
                tot += 1
                agree += np.sign(a_) == np.sign(b_)
        chk["sign_agreement"] = float(agree / tot) if tot else None
    sens, b_flips = None, None
    if duration is not None:
        alt = cross_asset_tsmom(spy, ief, tlt, dgs10, bills, start, min_n, (pk,), 500, 1, seed, duration=None)
        sens = alt["sharpe"].get("diff")
        Da = _t481_monthly(spy, ief, tlt, dgs10, bills, None)
        b_flips = 0
        for i in pv["idx"]:
            t = mi.get(g["months"][i])
            x1 = _cum_ex(D["proxies"][pk[0]], bill, t, pk[2], 1) if t is not None else float("nan")
            x2 = _cum_ex(Da["proxies"][pk[0]], Da["bill"], t, pk[2], 1) if t is not None else float("nan")
            b_flips += int(np.isfinite(x1) and np.isfinite(x2) and np.sign(x1) != np.sign(x2))
    pos = pv["pos"]
    return {"n": int(n), "labels": [labs[0], labs[-1]] if labs else None, "sharpe": sh, "dsr_strategy": d_strat, "dsr_diff": d_diff,
            "placebo": shp, "regimes": reg, "synthetic_check": chk, "duration_sensitivity_diff": sens, "duration_b_flips": b_flips,
            "position_shares": {"1": float(np.mean(pos == 1)), "0.5": float(np.mean(pos == 0.5)), "0": float(np.mean(pos == 0))},
            "family": {"|".join(map(str, k)): {"n": int(r["idx"].size), "sharpe_cross": _sr_ann(r["cross_ex"]), "sharpe_own": _sr_ann(r["own_ex"])} for k, r in res.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_mom_cross_asset_tsmom(archive):
    """T-481."""
    need = [dh("SPY"), dh("IEF"), dh("TLT"), DGS10_B, DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    sp = _daily(archive, dh("SPY"))
    ie = _daily(archive, dh("IEF"))
    tl = _daily(archive, dh("TLT"))
    j = cross_asset_tsmom((sp["days"], sp["adj"]), (ie["days"], ie["adj"]), (tl["days"], tl["adj"]), _fred_avail(archive, DGS10_B), bills)
    sh, pl, ck = j["sharpe"], j["placebo"], j["synthetic_check"]
    ps = j["position_shares"]
    reason = (f"SPY at month-end t: e = sign of SPY's 12-1 excess return, b = sign of the 12-1 excess return of the 10-year "
              f"proxy (IEF adjclose from 2002-08, before that the synthetic constant-maturity return y_(t-1)/12 - "
              f"{T481_DURATION:g} x dy from fred-DGS10 month-end yields known by the fill), position max(0, (e + b)/2) "
              f"(1 / 0.5 / 0 in {ps['1'] * 100:.0f}/{ps['0.5'] * 100:.0f}/{ps['0'] * 100:.0f}% of months) vs own max(0, e), "
              f"filled at the next session's close, DTB3 cash, 2 bps per side; hold months {j['labels'][0]}..{j['labels'][1]} "
              f"({j['n']} months). Excess Sharpe cross-asset {_s(sh.get('sharpe_a'), 3)} vs own {_s(sh.get('sharpe_b'), 3)}: "
              f"difference {_s(sh.get('diff'))} ({_ci(sh.get('ci'))}, paired studentized CBB, 12-month blocks, {N_BOOT:,} draws x "
              f"{REPS} seeds); DSR over the 12 declared trials (IEF/TLT/synthetic proxy x long-flat/long-short x 12-1/6-1): strategy "
              f"{_f(j['dsr_strategy']['dsr'])}, difference series {_f(j['dsr_diff']['dsr'])}; placebo (b lagged 12 months) "
              f"difference {_s(pl.get('diff'))} ({_ci(pl.get('ci'))}). Regimes: "
              + ", ".join(f"{k} {x['diff']:+.3f}" for k, x in j["regimes"].items())
              + (f". Synthetic bond vs IEF over {ck['months']} months: correlation {ck['corr']:.3f}, tracking error "
                 f"{ck['te_ann'] * 100:.2f}%/yr, mean gap {ck['mean_diff_ann'] * 100:+.2f}%/yr, 12-1 sign agreement "
                 f"{_pc(ck['sign_agreement'])}" if ck else "")
              + f"; with the yield-dependent par-bond duration (1 - (1 + y/2)^-20)/y instead of the constant {T481_DURATION:g} "
              f"(a 10-year par bond's modified duration runs from about 6.5 at 9% yields to 9.3 at 1.5%) the bond signal flips in "
              f"{j['duration_b_flips']} of {j['n']} decision months and the primary difference is {_s(j['duration_sensitivity_diff'])} "
              f"(duration approximation, reported only). With e and b in {{-1, +1}}, (e + b)/2 takes -1/0/+1, so the clipped "
              f"rule holds SPY only when both signals are positive (the library's 0.5 states need a zero sign) — " + j["why"])
    stat = {"n_months": j["n"], "window": j["labels"], "sharpe_cross": sh.get("sharpe_a"), "sharpe_own": sh.get("sharpe_b"),
            "diff": sh.get("diff"), "ci": sh.get("ci"), "ci_mc_se": sh.get("ci_mc_se"), "dsr_strategy": j["dsr_strategy"],
            "dsr_diff": j["dsr_diff"], "placebo_diff": pl.get("diff"), "placebo_ci": pl.get("ci"), "regimes": j["regimes"],
            "synthetic_check": ck, "duration": T481_DURATION, "duration_sensitivity_diff": j["duration_sensitivity_diff"],
            "duration_b_flips": j["duration_b_flips"],
            "position_shares": ps, "family": j["family"], "criteria": j["criteria"],
            "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_mom_tsmom_vs_hist_mean": b6c_mom_tsmom_vs_hist_mean,
    "b6c_mom_sma10_drawdown_vs_random": b6c_mom_sma10_drawdown_vs_random,
    "b6c_mom_residual_vs_total_momentum": b6c_mom_residual_vs_total_momentum,
    "b6c_mom_crash_filter_vs_random": b6c_mom_crash_filter_vs_random,
    "b6c_mom_trend_crisis_smile": b6c_mom_trend_crisis_smile,
    "b6c_mom_vol_scaled_trend_did": b6c_mom_vol_scaled_trend_did,
    "b6c_mom_cross_asset_tsmom": b6c_mom_cross_asset_tsmom,
}

THEORY_MAP = {
    "T-300": "b6c_mom_tsmom_vs_hist_mean",
    "T-301": "b6c_mom_sma10_drawdown_vs_random",
    "T-308": "b6c_mom_residual_vs_total_momentum",
    "T-311": "b6c_mom_crash_filter_vs_random",
    "T-317": "b6c_mom_trend_crisis_smile",
    "T-310": "b6c_mom_vol_scaled_trend_did",
    "T-481": "b6c_mom_cross_asset_tsmom",
}
