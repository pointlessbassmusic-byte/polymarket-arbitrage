"""
Batch 6c, group ``pairs``: five pairs / twin-spread claims of the underlying library on Yahoo daily histories (the
declared 51-ETF pairs universe and ETH/BTC, Brent/WTI front-month futures with the USO/BNO/UGA funds, and the ten
declared dual-class share pairs).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-321  GGR distance rule on the 51 ETFs (the 9 sector SPDRs, the 21 iShares country ETFs and SPY QQQ DIA IWM MDY EFA
           EEM VWO TLT IEF SHY LQD HYG GLD SLV GDX XOP KRE XHB VNQ IYR), trading 2008-01..2026-09: the 20 smallest-SSD
           pairs of normalized total-return indices over a 12-month formation, traded 6 months (open when the spread of
           prices rebased at the formation-end close exceeds 2 formation sds, long the laggard / short the leader in equal
           dollars; close at the next crossing or at the period end; every signal waits one day), six overlapping
           portfolios (one started each month), monthly return on committed capital ($1 per pair) net of 15 bps per leg
           per trade and 50 bps/yr borrow on the short leg. Pass: mean > 0 with the studentized block-bootstrap 95% CI
           excluding 0 (block 6, the trial's, and block 12 = 2 x the hold, rule 10: both must hold, rule 11), mean above
           the 95th percentile of 1,000 draws of 20 random pairs traded with the same rules, DSR > 0.95 at n_trials =
           6 variants x 2 thresholds = 12 (10 computed; the stock-universe variant is not runnable). min_n 120 months.
  * T-322  Engle-Granger selection (OLS of log A on log B over 12 months, ADF on the residual without deterministic
           terms, lag by AIC, MacKinnon (2010) finite-sample 5% critical value for 2 variables with a constant) with an
           AR(1) half-life of 2-30 days; persistence = the 6-month out-of-sample spread (beta, alpha frozen) rejects a
           unit root at 10% (ADF with a constant, lag by AIC, MacKinnon (2010) 1-variable critical value: the spread is a
           fixed combination, nothing is estimated on the trading sample). Windows start every month 2008-01..2026-04
           (the pooled all-start estimate of the semiannual grid, rule 10; per-phase range reported). Pass: 95% lower
           bound of the persistence share (circular block bootstrap over window months, 12-month blocks = 1 year = 2 x
           the hold) > 50% and > the random-pair share + 20 pp (1,000 draws of as many candidate pairs per window as
           were selected, same test). min_n 200 selected pairs (non-overlapping equivalents: pooled pair-windows / 6).
  * T-323  On T-322's selected pair-windows: Kalman time-varying hedge ratio (random-walk alpha and beta, state noise
           w = delta/(1 - delta) on both and observation noise R by EM on the formation window only, the filter run
           forward) against the static OLS hedge ratio, the same entry/exit rule on each estimator's standardized spread
           (|z| > 2 open, |z| < 0.5 close, |z| > 4 stop; Kalman z = innovation / sqrt(predicted variance)), hedge leg
           rebalanced only when beta moves > 5% (cost included). Pass: mean paired difference of per-window net Sharpe
           (Kalman minus static) > 0 with 95% CI excluding 0 in 2008-2016 AND 2017-2026 under both named constructions
           (block bootstrap over window months, 12-month blocks; Ledoit-Wolf (2008) test on the aggregate daily
           portfolios, rule 11) and DSR of the Kalman variant > 0.95 at the 4-cell delta x threshold grid. min_n 100
           pair-windows (non-overlapping equivalents).
  * T-468  s = ln(BZ=F) - ln(CL=F) front-month closes, z on the trailing 250 sessions (masked days excluded from the
           statistics), roll windows (+-5 sessions around each scheduled last trading day of either contract) and April
           2020 masked from signals; z > 2: long USO / short BNO, z < -2 the reverse, equal dollars at the next close;
           exit at z = 0 or after 60 sessions; 5 bps per leg per trade, 50 bps/yr borrow; entries 2011-01.., all closed
           by 2026-09-30. Pass: 95% lower bound of the mean net return per trade > 0 (trade bootstrap AND the trial's
           block-shifted signal null with block 60, rule 11), >= 20 trades, positive mean in >= 2 of 2011-2014,
           2015-2019 and 2020-2026. DSR over the 3 runnable variants is reported (procedure, not pass). min_n 20 trades.
  * T-470  Ten declared dual-class pairs, x = ln(A) - ln(k B) on adjusted closes, z on the trailing 60 sessions, |z| > 2:
           long the cheap class, short the rich class, equal dollars at the next close, exit at z = 0 or after 20
           sessions; 5 bps per leg per trade (the claim; the controls' 25 bps for the thin classes BF-A, LEN-B and HEI-A
           is the second cost reading and both must agree, rule 11) and 50 bps/yr borrow; entries 2014-01-01.. Pass:
           pooled 95% lower bound per trade > 0 (bootstrap clustered by pair-month), positive in >= 6 of 10 pairs, DSR
           > 0.95 over the 5 variants. LBRDK is not archived (Yahoo history starts 2026-07-17), so the LBRDK/LBRDA pair is
           None: the pooled mean and the DSR need all ten pairs and are not implemented (None, rule 9); the 6-of-10 count
           is decided from the nine archived pairs where the tenth cannot change it. min_n 200 trades.

Conventions
  * Data. Every bundle is read through ``archive.load``; a row is used only when its ``available_at`` is not after the
    bundle's capture time. Yahoo bars are keyed by the UTC date of their timestamp (ETF and stock bars 13:30/14:30 UTC,
    futures 04:00 UTC: the trading date; crypto 00:00 UTC: the UTC day). ETF and stock legs use ``adjclose`` (total
    return; Yahoo back-adjustment scales history by a constant, so normalized indices, log-price regressions on
    formation-rebased prices and z-scores are unaffected); the futures signal uses ``close`` (settlement). The ETF panel
    is on SPY's session calendar; a missing bar after a fund's first bar carries the previous close (flagged by count).
  * Point in time (rules 4, 12). Every formation statistic (SSD, sd, beta, alpha, EM parameters, the filter state) uses
    closes up to the formation-end close; every z-score is trailing or frozen; a decision at close t (its bar is
    stamped available the next session, before the next close) fills at close t + 1, the GGR one-day wait. An ETF
    enters a formation only with a bar on the formation's first session (12 months of history at its end). The
    dual-class pairs start when both classes trade as separate lines (GOOG class C 2014-04-03, Z 2015-08-03, UA
    2016-04-08, FOX 2019-03-19, NWS 2013-06-19).
  * Calendars (rule 10). T-321: the claim's own calendar (one portfolio started each month, six overlapping). T-322/T-323:
    windows start every month (the claim's 12- and 6-month units), i.e. the pooled all-start estimate of the semiannual
    grid with 12-month blocks; the six phases' values are reported. T-468/T-470: daily state machines on trailing
    statistics (no grid phase).
  * Intervals (rule 6). T-321: studentized circular block bootstrap (Bartlett-HAC, bandwidth = block) of the monthly mean.
    T-322/T-323: circular block bootstrap of ratio estimators over window-start months (12-month blocks), percentile.
    T-468: percentile bootstrap over trades (trades never overlap) and the block-shifted null (the masked signal
    circularly shifted by every multiple of 60 sessions against the fixed fund returns). T-470: percentile bootstrap
    clustered by pair-entry-month. A "95% lower bound > x" passes when the two-sided 95% lower end is above x, fails
    when even the one-sided 95% lower bound is not, and is otherwise undecided. Every decisive bootstrap end is averaged
    over REPS seeds with its Monte Carlo s.e. (REPS_MAX seeds when REPS cannot resolve it).
  * Costs (rule 9) as each claim states, per leg per trade on the traded value: T-321 15 bps + 50 bps/yr borrow on the
    short leg's value (calendar days); T-322/T-323 15 bps (ETFs) and 40 bps (crypto) per leg per trade including every
    hedge-leg rebalance, no borrow (none stated); T-468 5 bps + 50 bps/yr; T-470 5 bps (or 25 bps on BF-A, LEN-B, HEI-A
    legs) + 50 bps/yr. Returns are per $1 per leg (equal-dollar rules) or per $(1 + |beta|) of gross capital (hedged).
  * Below trial.min_n (rule 5) the verdict is never supported and a failing criterion counts only when it fails
    decisively (its interval wholly on the wrong side). Verdicts use ``underlying2._verdict`` through
    ``batch6b_bw._decide``.
"""

from __future__ import annotations

import bisect
import functools
import math
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import _clean, _decide, _mean_stat, _stud, all_constructions, lw_test, mc_reps, resolve
from mandel.experiments.batch6c_misc import dsr_family, dsr_row, pbo_fast
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import sharpe_ratio

N_BOOT = 2000                  # bootstrap draws per seed for interval ends (x REPS seeds)
REPS = 5                       # bootstrap seeds behind every decisive interval end
REPS_MAX = 25                  # seeds when REPS cannot resolve a bound against its threshold
SEED = 0
DSR_PASS = 0.95
N_RANDOM = 1000                # the trials' 1,000 random-pair draws
END = "2026-09-30"
Z95 = NormalDist().inv_cdf(0.975)

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
COUNTRY21 = ["EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWK", "EWL", "EWM", "EWN", "EWO", "EWP", "EWQ", "EWS", "EWT",
             "EWU", "EWW", "EWY", "EWZ", "EZA"]
OTHERS = ["SPY", "QQQ", "DIA", "IWM", "MDY", "EFA", "EEM", "VWO", "TLT", "IEF", "SHY", "LQD", "HYG", "GLD", "SLV", "GDX",
          "XOP", "KRE", "XHB", "VNQ", "IYR"]
UNIVERSE = SECTORS + COUNTRY21 + OTHERS                      # the declared 51 ETFs, in declared order
# Asset classes for the Do-Faff same-sector variant of T-321 (declared here; ETFs have no GICS industry).
ASSET_CLASS = {**{s: "us_equity" for s in SECTORS + ["SPY", "QQQ", "DIA", "IWM", "MDY", "XOP", "KRE", "XHB"]},
               **{s: "intl_equity" for s in COUNTRY21 + ["EFA", "EEM", "VWO"]},
               **{s: "bonds" for s in ["TLT", "IEF", "SHY", "LQD", "HYG"]},
               **{s: "metals" for s in ["GLD", "SLV", "GDX"]},
               **{s: "real_estate" for s in ["VNQ", "IYR"]}}
CRYPTO = ("ETH-USD", "BTC-USD")                               # T-322/T-323's ETH/BTC candidate (ETH on BTC)


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
    """{'days', 'close', 'adj', 'vol'} of a Yahoo daily bundle (positive closes only); a bar without adjclose carries the
    previous adjclose/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r.get("value") or {}
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
            try:
                vol = float(v.get("volume") or 0.0)
            except (TypeError, ValueError):
                vol = 0.0
            by[d] = (c, a, vol)
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        vol = np.array([by[d][2] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "close": close, "adj": adj, "vol": vol}
    return _cached(archive, ("daily", name), load)


def panel(series: dict, cal: Sequence[str]) -> tuple:
    """(T, N) array of each symbol's value on calendar ``cal`` from {sym: (days, values)}, carried forward over a missing
    calendar day after the symbol's first bar (never before it, never past its last bar), and the count of carried
    days per symbol."""
    ix = {d: i for i, d in enumerate(cal)}
    T = len(cal)
    syms = list(series)
    out = np.full((T, len(syms)), np.nan)
    filled = {}
    for j, s in enumerate(syms):
        d, v = series[s]
        col = np.full(T, np.nan)
        for day, x in zip(d, v):
            i = ix.get(day)
            if i is not None and math.isfinite(float(x)) and float(x) > 0:
                col[i] = float(x)
        ok = np.where(np.isfinite(col))[0]
        n_f = 0
        if ok.size:
            for i in range(ok[0] + 1, ok[-1] + 1):
                if not np.isfinite(col[i]):
                    col[i] = col[i - 1]
                    n_f += 1
        out[:, j] = col
        filled[s] = n_f
    return out, filled


def month_bounds(days: Sequence[str]) -> tuple:
    """(month labels, month index per day, first day index per month, last day index per month)."""
    labels = sorted({d[:7] for d in days})
    pos = {m: k for k, m in enumerate(labels)}
    mi = np.array([pos[d[:7]] for d in days], int)
    first = np.full(len(labels), -1, int)
    last = np.full(len(labels), -1, int)
    for i, k in enumerate(mi):
        if first[k] < 0:
            first[k] = i
        last[k] = i
    return labels, mi, first, last


def _ord(d) -> int:
    return (date.fromisoformat(d) if isinstance(d, str) else d).toordinal()


def _dt(days: Sequence[str]) -> np.ndarray:
    o = np.array([_ord(d) for d in days], np.int64)
    return np.r_[1, np.diff(o)].astype(float)


def _ret(P: np.ndarray) -> np.ndarray:
    """Simple returns close t-1 -> close t (row 0 NaN)."""
    R = np.full(P.shape, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        R[1:] = P[1:] / P[:-1] - 1.0
    return R


# ============================================================================================ formatting, misc ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _pu(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bp"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _mc(fn: Callable, check: Callable, seed: int = SEED, keys: Sequence[str] = ("ci", "ci1")) -> dict:
    """``fn(seed=...)`` over REPS seeds (interval ends averaged, with Monte Carlo s.e.); REPS_MAX seeds when ``check`` (the
    resolved criterion, None = unresolved) cannot decide on REPS."""
    t = mc_reps(fn, REPS, seed, keys)
    if check(t) is None and REPS_MAX > REPS:
        t = mc_reps(fn, REPS_MAX, seed, keys)
    return t


def lb_check(t: dict, thr: float) -> tuple:
    """'95% lower bound > thr' on a {'ci': two-sided 95% [lo, hi], 'ci1': one-sided 95% [lo, hi]} result with Monte Carlo
    s.e.: passes when the two-sided lower end is above thr, fails when even the one-sided lower bound is not, else
    undecided. Returns (ok, decisive_fail, note); a failure is decisive when the two-sided upper end is below thr."""
    lo2 = (t.get("ci") or [None, None])[0]
    hi2 = (t.get("ci") or [None, None])[1]
    lo1 = (t.get("ci1") or [None, None])[0]
    if lo2 is None or lo1 is None:
        return None, False, " [interval not available]"
    se2 = (t.get("ci_mc_se") or [0.0, 0.0])
    se1 = (t.get("ci1_mc_se") or [0.0, 0.0])
    p2, n2 = resolve(lo2, se2[0], thr, "gt")
    p1, n1 = resolve(lo1, se1[0], thr, "gt")
    dec = hi2 is not None and resolve(hi2, se2[1], thr, "lt")[0] is True
    if p2 is True:
        return True, False, n2
    if p1 is False:
        return False, dec, n1
    return None, False, (n2 or n1 or " [the two-sided and one-sided 95% readings disagree: undecided]")


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _sr_ann(x, ppy: float) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, ppy)) if x.size > 2 and x.std() > 0 else None


def _q(x: np.ndarray, lv: float) -> float:
    return float(np.quantile(x, lv))


def _pct_ci(draws: np.ndarray) -> dict:
    """Two-sided 95% and one-sided 95% percentile bounds of bootstrap draws."""
    return {"ci": [_q(draws, 0.025), _q(draws, 0.975)], "ci1": [_q(draws, 0.05), _q(draws, 0.95)]}


# ======================================================================================== ADF and MacKinnon ==
# MacKinnon (2010), "Critical values for cointegration tests", Queen's Economics Department WP 1227, Table 1 (constant,
# no trend): crit(T) = tau_inf + b1/T + b2/T^2 + b3/T^3, for N = 1 (Dickey-Fuller) and N = 2 (Engle-Granger, 2 variables).
MK2010_C = {
    1: {0.01: (-3.43035, -6.5393, -16.786, -79.433), 0.05: (-2.86154, -2.8903, -4.234, -40.040),
        0.10: (-2.56677, -1.5384, -2.809, 0.0)},
    2: {0.01: (-3.89644, -10.9519, -33.527, 0.0), 0.05: (-3.33613, -6.1101, -6.823, 0.0),
        0.10: (-3.04445, -4.2412, -2.720, 0.0)},
}
# MacKinnon (1994) asymptotic p-value response surfaces (constant), as tabulated in statsmodels.tsa.adfvalues.
MK1994_C = {
    1: {"star": -1.61, "min": -18.83, "max": 2.74, "small": (2.1659, 1.4412, 3.8269e-2),
        "large": (1.7339, 9.3202e-1, -1.2745e-1, -1.0368e-2)},
    2: {"star": -2.62, "min": -18.86, "max": 0.92, "small": (2.92, 1.5012, 3.9796e-2),
        "large": (2.1945, 6.4695e-1, -2.9198e-1, -4.2377e-2)},
}


def mackinnon_crit(n_vars: int, level: float, nobs) -> np.ndarray:
    """MacKinnon (2010) finite-sample critical value (constant), vectorized over nobs."""
    b = MK2010_C[n_vars][level]
    T = np.asarray(nobs, float)
    return b[0] + b[1] / T + b[2] / T ** 2 + b[3] / T ** 3


def mackinnon_p(tau, n_vars: int) -> np.ndarray:
    """MacKinnon (1994) asymptotic p-value of a (residual-based) ADF tau with a constant, vectorized."""
    c = MK1994_C[n_vars]
    t = np.asarray(tau, float)
    small = c["small"][0] + c["small"][1] * t + c["small"][2] * t ** 2
    large = c["large"][0] + c["large"][1] * t + c["large"][2] * t ** 2 + c["large"][3] * t ** 3
    zz = np.where(t <= c["star"], small, large)
    p = np.array([0.5 * math.erfc(-v / math.sqrt(2.0)) if math.isfinite(v) else math.nan for v in np.ravel(zz)])
    p = p.reshape(np.shape(zz))
    p = np.where(t > c["max"], 1.0, np.where(t < c["min"], 0.0, p))
    return np.where(np.isfinite(t), p, np.nan)


def _batched_solve(G: np.ndarray, g: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(G, g[..., None])[..., 0]
    except np.linalg.LinAlgError:
        out = np.full(g.shape, np.nan)
        for i in range(G.shape[0]):
            try:
                out[i] = np.linalg.solve(G[i], g[i])
            except np.linalg.LinAlgError:
                out[i] = np.linalg.lstsq(G[i], g[i], rcond=None)[0]
        return out


def _adf_design(E: np.ndarray, dE: np.ndarray, p: int, maxlag: int, c: int) -> tuple:
    """Rows of the ADF regression on the sample that starts after ``maxlag`` lags: y (n, K) and Z (K, n, 1 + c + p)."""
    T = E.shape[0]
    n = T - 1 - maxlag
    y = dE[maxlag:]
    cols = [E[maxlag:T - 1]]
    if c:
        cols.append(np.ones_like(y))
    for i in range(1, p + 1):
        cols.append(dE[maxlag - i:T - 1 - i])
    Z = np.stack(cols, axis=2).transpose(1, 0, 2)
    return y, Z, n


def adf_batch(E, trend: str = "c", maxlag: Optional[int] = None) -> dict:
    """Augmented Dickey-Fuller tau of every column of E (T, K), as statsmodels' adfuller with autolag='AIC': the lag is
    chosen by AIC over 0..maxlag on the common sample (maxlag = ceil(12 (T/100)^(1/4)), capped at T//2 - c - 1), then the
    regression is re-run on the full sample for that lag. trend 'c' (constant) or 'n' (none: Engle-Granger residuals).
    Returns tau, lag and nobs (rows of the final regression) per column; tau is NaN for a degenerate column."""
    E = np.asarray(E, float)
    if E.ndim == 1:
        E = E[:, None]
    T, K = E.shape
    c = 1 if trend == "c" else 0
    if maxlag is None:
        maxlag = int(math.ceil(12.0 * (T / 100.0) ** 0.25))
        maxlag = max(0, min(T // 2 - c - 1, maxlag))
    dE = np.diff(E, axis=0)
    y, Z, n = _adf_design(E, dE, maxlag, maxlag, c)
    G = Z.transpose(0, 2, 1) @ Z
    g = np.einsum("knm,nk->km", Z, y)
    yy = (y * y).sum(axis=0)
    best = np.full(K, np.inf)
    lag = np.zeros(K, int)
    for p in range(maxlag + 1):
        m = 1 + c + p
        coef = _batched_solve(G[:, :m, :m], g[:, :m])
        ssr = np.maximum(yy - (coef * g[:, :m]).sum(axis=1), 1e-300)
        aic = n * np.log(ssr / n) + 2 * m
        better = aic < best
        best = np.where(better, aic, best)
        lag = np.where(better, p, lag)
    tau = np.full(K, np.nan)
    nobs = np.zeros(K, int)
    for p in np.unique(lag):
        ks = np.where(lag == p)[0]
        yp, Zp, n_p = _adf_design(E[:, ks], dE[:, ks], int(p), int(p), c)
        m = 1 + c + int(p)
        Gp = Zp.transpose(0, 2, 1) @ Zp
        gp = np.einsum("knm,nk->km", Zp, yp)
        coef = _batched_solve(Gp, gp)
        ssr = (yp * yp).sum(axis=0) - (coef * gp).sum(axis=1)
        s2 = ssr / max(n_p - m, 1)
        try:
            inv00 = np.linalg.inv(Gp)[:, 0, 0]
        except np.linalg.LinAlgError:
            inv00 = np.array([np.linalg.pinv(x)[0, 0] for x in Gp])
        with np.errstate(invalid="ignore", divide="ignore"):
            tt = coef[:, 0] / np.sqrt(s2 * inv00)
        tau[ks] = np.where(np.isfinite(tt) & (s2 > 1e-24), tt, np.nan)
        nobs[ks] = n_p
    return {"tau": tau, "lag": lag, "nobs": nobs}


def half_life(E: np.ndarray) -> np.ndarray:
    """AR(1) half-life (in periods) of every column: e_t = c + rho e_{t-1}; -ln 2 / ln rho for 0 < rho < 1, else inf."""
    e0, e1 = E[:-1], E[1:]
    d0 = e0 - e0.mean(axis=0)
    d1 = e1 - e1.mean(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = (d0 * d1).sum(axis=0) / (d0 * d0).sum(axis=0)
        hl = np.where((rho > 0) & (rho < 1), -math.log(2.0) / np.log(np.where((rho > 0) & (rho < 1), rho, 0.5)), np.inf)
    return hl


def ols_cols(Y: np.ndarray, X: np.ndarray) -> tuple:
    """Column-wise OLS y = a + b x: (a, b, residuals)."""
    xm, ym = X.mean(axis=0), Y.mean(axis=0)
    dx = X - xm
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (dx * (Y - ym)).sum(axis=0) / (dx * dx).sum(axis=0)
    a = ym - b * xm
    return a, b, Y - a - b * X


# ========================================================================================= vectorized spread sim ==

def spread_sim(z, beta, rA, rB, valid, entry: float, exit_z: float, stop: float = np.inf, cost_a=0.0, cost_b=0.0,
               borrow: float = 0.0, dt=None, wait: int = 1, rebalance: Optional[float] = None) -> dict:
    """Spread-reversion state machine over N rows at once (rows are pair-windows on their own offset-aligned columns).

    z, beta, rA, rB, valid, dt: (N, T). Row i trades on its valid columns (a contiguous range). rA/rB[:, t] are the legs'
    simple returns from close t-1 to close t; beta[:, t] is the hedge ratio known at close t (B dollars per $1 of A).
    A decision at close t uses z[:, t] (NaN: no decision) and fills at close t + wait (wait 0: the same close).
    Position +1 = long $1 A / short $beta B, taken when z < -entry; -1 = the reverse, when z > entry; a new position opens
    only while |z| < stop. Exit when z crosses back through -/+exit_z (+1: z >= -exit_z; -1: z <= exit_z) or at the stop
    (|z| >= stop on the adverse side; that side re-arms once |z| < entry). Positions open at a row's last valid close are
    closed there and no position opens at it. Costs: cost_a/cost_b per $ traded on each leg at every fill (open, close,
    hedge rebalance); borrow per year on the short legs' value over dt calendar days. rebalance: while held, when
    |beta_t - beta_held| > rebalance x |beta_held| at close t, the B leg is reset to -beta_t x (A value) at the next fill.
    Returns pnl (N, T) in $ per $1 of A at entry, n_open, n_rebalance and days_in (sessions held) per row."""
    z = np.asarray(z, float)
    N, T = z.shape
    beta = np.broadcast_to(np.asarray(beta, float), (N, T)) if np.ndim(beta) < 2 else np.asarray(beta, float)
    valid = np.asarray(valid, bool)
    dt = np.ones((N, T)) if dt is None else np.broadcast_to(np.asarray(dt, float), (N, T))
    ca = np.broadcast_to(np.asarray(cost_a, float), (N,)).astype(float)
    cb = np.broadcast_to(np.asarray(cost_b, float), (N,)).astype(float)
    has = valid.any(axis=1)
    last = np.where(has, T - 1 - np.argmax(valid[:, ::-1], axis=1), -1)
    pos = np.zeros(N)
    tgt = np.zeros(N)
    A = np.zeros(N)
    B = np.zeros(N)
    bdec = np.zeros(N)
    bh = np.zeros(N)
    reb = np.zeros(N, bool)
    arm_lo = np.ones(N, bool)
    arm_hi = np.ones(N, bool)
    pnl = np.zeros((N, T))
    n_open = np.zeros(N, int)
    n_reb = np.zeros(N, int)
    days_in = np.zeros(N, int)

    def fill(sel, t, islast):
        chg = sel & (tgt != pos)
        cl = chg & (pos != 0)
        if cl.any():
            pnl[cl, t] -= ca[cl] * np.abs(A[cl]) + cb[cl] * np.abs(B[cl])
            A[cl] = 0.0
            B[cl] = 0.0
            pos[cl] = 0.0
        op = chg & (tgt != 0)
        tgt[op & islast] = 0.0
        op &= ~islast
        if op.any():
            A[op] = tgt[op]
            B[op] = -tgt[op] * bdec[op]
            pnl[op, t] -= ca[op] + cb[op] * np.abs(B[op])
            pos[op] = tgt[op]
            bh[op] = bdec[op]
            n_open[op] += 1
        if rebalance is not None:
            rr = sel & reb & (pos != 0) & (tgt == pos) & ~islast & ~op
            if rr.any():
                nb = -bdec[rr] * A[rr]
                pnl[rr, t] -= cb[rr] * np.abs(nb - B[rr])
                B[rr] = nb
                bh[rr] = bdec[rr]
                n_reb[rr] += 1
            reb[sel] = False

    for t in range(T):
        v = valid[:, t]
        islast = last == t
        live = v & (pos != 0)
        if t > 0 and live.any():
            ra = np.nan_to_num(rA[:, t])
            rb = np.nan_to_num(rB[:, t])
            sh = np.maximum(-A, 0.0) + np.maximum(-B, 0.0)
            d = A * ra + B * rb - borrow * sh * dt[:, t] / 365.0
            pnl[live, t] += d[live]
            A[live] *= 1.0 + ra[live]
            B[live] *= 1.0 + rb[live]
            days_in += live
        if wait:
            fill(v, t, islast)
        fc = v & islast & (pos != 0)
        if fc.any():
            pnl[fc, t] -= ca[fc] * np.abs(A[fc]) + cb[fc] * np.abs(B[fc])
            A[fc] = 0.0
            B[fc] = 0.0
            pos[fc] = 0.0
            tgt[fc] = 0.0
        zt = z[:, t]
        dec = v & ~islast & np.isfinite(zt)
        if not dec.any():
            continue
        zt = np.where(dec, zt, 0.0)
        bt = beta[:, t]
        flat = dec & (tgt == 0)
        nl = flat & arm_lo & (zt < -entry) & (zt > -stop)
        ns = flat & arm_hi & (zt > entry) & (zt < stop)
        tgt[nl] = 1.0
        tgt[ns] = -1.0
        bdec[nl | ns] = bt[nl | ns]
        hl = dec & (tgt == 1.0) & ~nl
        hs = dec & (tgt == -1.0) & ~ns
        st_l = hl & (zt <= -stop)
        st_s = hs & (zt >= stop)
        ex_l = hl & ((zt >= -exit_z) | st_l)
        ex_s = hs & ((zt <= exit_z) | st_s)
        tgt[ex_l | ex_s] = 0.0
        arm_lo[st_l] = False
        arm_hi[st_s] = False
        if rebalance is not None:
            stay = ((hl & ~ex_l) | (hs & ~ex_s)) & (pos == tgt)
            mv = stay & (np.abs(bt - bh) > rebalance * np.abs(bh))
            reb[mv] = True
            bdec[mv] = bt[mv]
        arm_lo |= dec & (zt > -entry)
        arm_hi |= dec & (zt < entry)
        if not wait:
            fill(dec, t, islast)
    return {"pnl": pnl, "n_open": n_open, "n_rebalance": n_reb, "days_in": days_in}


def row_sharpe(pnl: np.ndarray, valid: np.ndarray, ppy) -> np.ndarray:
    """Annualized Sharpe (ddof 1) of each row's daily P&L over its valid columns; 0 when the row never moves."""
    v = np.asarray(valid, bool)
    n = v.sum(axis=1)
    x = np.where(v, pnl, 0.0)
    m = x.sum(axis=1) / np.maximum(n, 1)
    var = (np.where(v, (pnl - m[:, None]) ** 2, 0.0)).sum(axis=1) / np.maximum(n - 1, 1)
    sd = np.sqrt(var)
    ppy = np.broadcast_to(np.asarray(ppy, float), m.shape)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sd > 1e-14, m / np.where(sd > 1e-14, sd, 1.0) * np.sqrt(ppy), 0.0)


# ========================================================================================= block bootstraps ==

def _cbb_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    st = rng.integers(0, n, size=(k, nb))
    return (st[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def cbb_ratio(num, den, block: int, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Circular block bootstrap (rows in time order, blocks of ``block`` rows) of sum(num) / sum(den): estimate and the
    two-sided / one-sided 95% percentile bounds."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    num, den = np.asarray(num, float), np.asarray(den, float)
    n = num.size
    est = float(num.sum() / den.sum()) if den.sum() > 0 else None
    if n < 8 or est is None:
        return {"est": est, "ci": [None, None], "ci1": [None, None], "n_rows": int(n)}
    bl = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < nb:
        k = min(nb - done, max(1, 2_000_000 // n))
        idx = _cbb_idx(rng, n, bl, k)
        dd = den[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append(np.where(dd > 0, num[idx].sum(axis=1) / np.where(dd > 0, dd, 1.0), np.nan))
        done += k
    d = np.concatenate(out)
    d = d[np.isfinite(d)]
    return {"est": est, **_pct_ci(d), "n_rows": int(n), "block": bl}


def cluster_ratio(num, den, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """IID bootstrap over clusters of sum(num) / sum(den) (num, den: one entry per cluster)."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    num, den = np.asarray(num, float), np.asarray(den, float)
    n = num.size
    est = float(num.sum() / den.sum()) if den.sum() > 0 else None
    if n < 8 or est is None:
        return {"est": est, "ci": [None, None], "ci1": [None, None], "n_clusters": int(n)}
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < nb:
        k = min(nb - done, max(1, 2_000_000 // n))
        idx = rng.integers(0, n, size=(k, n))
        dd = den[idx].sum(axis=1)
        out.append(num[idx].sum(axis=1) / np.where(dd > 0, dd, np.nan))
        done += k
    d = np.concatenate(out)
    d = d[np.isfinite(d)]
    return {"est": est, **_pct_ci(d), "n_clusters": int(n)}


def stud_mean(x, block: int, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Studentized circular block bootstrap (Bartlett-HAC, bandwidth = block) of the mean: two-sided 95% CI."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    r = _stud(_mean_stat, [np.asarray(x, float)], block, nb, seed)
    return {"est": r["est"], "se": r["se"], "ci": r["ci"], "p": r["p"], "block": r["block"]}


def _stud_row(x, block: int, label: str) -> tuple:
    """(name, ok, decisive) for 'mean > 0 with 95% CI excluding 0' under the studentized CBB with ``block``."""
    def check(t):
        lo = (t.get("ci") or [None])[0]
        return resolve(lo, (t.get("ci_mc_se") or [0.0])[0], 0.0, "gt")[0]
    t = _mc(lambda seed: stud_mean(x, block, seed=seed), check, keys=("ci",))
    lo, hi = t.get("ci") or (None, None)
    se = t.get("ci_mc_se") or [0.0, 0.0]
    ok, note = resolve(lo, se[0], 0.0, "gt")
    dec = hi is not None and resolve(hi, se[1], 0.0, "lt")[0] is True
    return (f"{label} block {t.get('block')} {_ci(t.get('ci'), 2, 1e4, ' bp')}{note}", ok, dec), t


# ============================================================================================= T-321 GGR distance ==

T321_MIN_N = 120
T321_FIRST = "2008-01"
T321_FORM = 12                 # formation months
T321_HOLD = 6                  # trading months (six overlapping portfolios)
T321_TOP = 20
T321_COST = 0.0015             # per leg per trade
T321_BORROW = 0.005            # per year on the short leg
T321_BLOCKS = (6, 12)          # the trial's block and rule 10's 2 x hold
T321_N_TRIALS = 12             # 6 declared variants x 2 thresholds (the stock-universe cells are not runnable)
T321_ZC_POOL = 100             # zero-crossing variant: the 20 most-crossing of the 100 smallest-SSD pairs
T321_PRIMARY = ("top20", 2.0, 1)
T321_CELLS = (T321_PRIMARY, ("top20", 1.5, 1), ("top5", 2.0, 1), ("top5", 1.5, 1), ("class", 2.0, 1), ("class", 1.5, 1),
              ("zc", 2.0, 1), ("zc", 1.5, 1), ("top20", 2.0, 0), ("top20", 1.5, 0))
T321_REGIMES = (("2008", "2014"), ("2015", "2026"))


def ggr_formation(Nf: np.ndarray) -> tuple:
    """Pairs (i < j) of the normalized formation indices Nf (T, n): their SSD and the sd (ddof 1) of the spread."""
    T, n = Nf.shape
    I, J = np.triu_indices(n, 1)
    G = Nf.T @ Nf
    d = np.diag(G)
    ssd = np.maximum(d[I] + d[J] - 2.0 * G[I, J], 0.0)
    mu = Nf.mean(axis=0)
    var = (ssd - T * (mu[I] - mu[J]) ** 2) / max(T - 1, 1)
    return I, J, ssd, np.sqrt(np.maximum(var, 0.0))


def ggr_select(I, J, ssd, sd, Nf, cls, top: int = T321_TOP) -> dict:
    """The declared selections (indices into the pair list): top-20 and top-5 smallest SSD, top-20 within an asset class
    (the Do-Faff same-sector variant) and the 20 most zero-crossing pairs of the 100 smallest SSD (ties by SSD). Pairs whose
    formation spread never moves (sd = 0) are not eligible."""
    ok = np.where(sd > 0)[0]
    order = ok[np.argsort(ssd[ok], kind="stable")]
    cls = np.asarray(cls)
    same = cls[I[order]] == cls[J[order]]
    pool = order[:T321_ZC_POOL]
    Sp = Nf[:, I[pool]] - Nf[:, J[pool]]
    sg = np.sign(Sp)
    zc = (sg[1:] * sg[:-1] < 0).sum(axis=0)
    zord = pool[np.lexsort((ssd[pool], -zc))]
    return {"top20": order[:top], "top5": order[:5], "class": order[same][:top], "zc": zord[:top]}


def _ggr_sim(P, R, DT, mi, ports, which, entry: float, wait: int, cost: float, borrow: float, batch: int = 16) -> list:
    """Simulate the pairs ``which[p]`` of every portfolio p (rows offset-aligned on its trading days): monthly P&L sums
    (len(which[p]), HOLD) per $1 per leg and opens per pair."""
    out = [None] * len(ports)
    for b0 in range(0, len(ports), batch):
        grp = list(range(b0, min(b0 + batch, len(ports))))
        sizes = [len(which[p]) for p in grp]
        N = int(sum(sizes))
        if N == 0:
            for p in grp:
                out[p] = {"pm": np.zeros((0, T321_HOLD)), "n_open": np.zeros(0, int)}
            continue
        Tm = max(ports[p]["tr1"] - ports[p]["tr0"] + 1 for p in grp)
        Z = np.full((N, Tm), np.nan)
        RA = np.zeros((N, Tm))
        RB = np.zeros((N, Tm))
        V = np.zeros((N, Tm), bool)
        D = np.ones((N, Tm))
        r = 0
        for p in grp:
            po, w = ports[p], which[p]
            n_t = po["tr1"] - po["tr0"] + 1
            sl = slice(po["tr0"], po["tr1"] + 1)
            I, J = po["I"][w], po["J"][w]
            Nt = P[sl] / P[po["f1"]]
            q = slice(r, r + len(w))
            Z[q, :n_t] = ((Nt[:, I] - Nt[:, J]) / po["sd"][w]).T
            RA[q, :n_t] = R[sl][:, I].T
            RB[q, :n_t] = R[sl][:, J].T
            V[q, :n_t] = True
            D[q, :n_t] = DT[sl]
            r += len(w)
        res = spread_sim(Z, 1.0, RA, RB, V, entry, 0.0, np.inf, cost, cost, borrow, D, wait)
        r = 0
        for p in grp:
            po, w = ports[p], which[p]
            n_t = po["tr1"] - po["tr0"] + 1
            mo = mi[po["tr0"]:po["tr1"] + 1] - po["k"]
            pm = np.zeros((len(w), T321_HOLD))
            blk = res["pnl"][r:r + len(w), :n_t]
            for o in range(T321_HOLD):
                cols = np.where(mo == o)[0]
                if cols.size:
                    pm[:, o] = blk[:, cols].sum(axis=1)
            out[p] = {"pm": pm, "n_open": res["n_open"][r:r + len(w)].copy()}
            r += len(w)
    return out


def ggr_run(days: Sequence[str], P: np.ndarray, names: Sequence[str], cls: Sequence[str], first: str = T321_FIRST,
            end: str = END, top: int = T321_TOP, cost: float = T321_COST, borrow: float = T321_BORROW,
            n_random: Optional[int] = None, seed: int = SEED, cells: Sequence[tuple] = T321_CELLS) -> dict:
    """T-321 machinery. P: (T, N) total-return closes on the session calendar ``days`` (NaN before a fund's first bar).
    One portfolio starts trading on the first session of every month; it is formed on the 12 calendar months before
    (funds with a bar on the formation's first session), trades 6 months (to ``end``) and its monthly return is the mean
    over its nominated pairs of each pair's P&L per $1 per leg. The strategy's month is the mean of the six portfolios
    trading in it. Returns the monthly series of every declared cell, the random-pair control's mean returns, the
    per-phase series and diagnostics."""
    nr = N_RANDOM if n_random is None else int(n_random)
    labels, mi, mfirst, mlast = month_bounds(days)
    R = _ret(P)
    DT = _dt(days)
    k_first = labels.index(first)
    k_end = max(k for k, m in enumerate(labels) if m <= end[:7])
    clsa = np.asarray(cls)
    ports = []
    for k in range(max(T321_FORM, k_first - (T321_HOLD - 1)), k_end + 1):
        f0, f1 = mfirst[k - T321_FORM], mlast[k - 1]
        tr0, tr1 = mfirst[k], mlast[min(k + T321_HOLD - 1, k_end)]
        elig = np.where(np.isfinite(P[f0]) & np.isfinite(P[tr1]))[0]
        if elig.size < top + 2:
            continue
        Nf = P[f0:f1 + 1, elig] / P[f0, elig]
        I, J, ssd, sd = ggr_formation(Nf)
        sel = ggr_select(I, J, ssd, sd, Nf, clsa[elig], top)
        ports.append({"k": k, "n_elig": int(elig.size), "I": elig[I], "J": elig[J], "ssd": ssd, "sd": np.where(sd > 0, sd, np.inf),
                      "sel": sel, "f1": f1, "tr0": tr0, "tr1": tr1, "ok": np.where(sd > 0)[0]})
    cfgs = sorted({(c[1], c[2]) for c in cells})
    prim_cfg = (T321_PRIMARY[1], T321_PRIMARY[2])
    sims, unions = {}, {}
    for cfg in cfgs:
        if cfg == prim_cfg:
            which = [po["ok"] for po in ports]
        else:
            which = [np.unique(np.concatenate([po["sel"][c[0]] for c in cells if (c[1], c[2]) == cfg])) for po in ports]
        unions[cfg] = which
        sims[cfg] = _ggr_sim(P, R, DT, mi, ports, which, cfg[0], cfg[1], cost, borrow)
    n_win = k_end - k_first + 1

    def series(port_month: list, keep=lambda po: True) -> tuple:
        s = np.zeros(n_win)
        c = np.zeros(n_win)
        for po, pmv in zip(ports, port_month):
            if pmv is None or not keep(po):
                continue
            for o in range(T321_HOLD):
                M = po["k"] + o
                if k_first <= M <= k_end and po["k"] + o <= k_end:
                    s[M - k_first] += pmv[o]
                    c[M - k_first] += 1
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(c > 0, s / np.maximum(c, 1), np.nan), c

    out_cells, trades = {}, {}
    for c in cells:
        cfg = (c[1], c[2])
        pmv = []
        opens = []
        for p, po in enumerate(ports):
            s_idx = po["sel"][c[0]]
            pos_ = np.searchsorted(unions[cfg][p], s_idx)
            pm = sims[cfg][p]["pm"][pos_]
            pmv.append(pm.mean(axis=0) if pm.shape[0] else None)
            opens.append(sims[cfg][p]["n_open"][pos_])
        x, cnt = series(pmv)
        out_cells[c] = {"x": x, "count": cnt, "port_month": pmv}
        trades[c] = opens
    prim = out_cells[T321_PRIMARY]
    keep = np.isfinite(prim["x"])
    months = [labels[k] for k in range(k_first, k_end + 1)]
    # random-pair control: 20 pairs drawn without replacement from every eligible pair of each formation, same rules
    rng = np.random.default_rng(seed)
    rs = np.zeros((nr, n_win))
    for p, po in enumerate(ports):
        pm = sims[prim_cfg][p]["pm"]
        K = pm.shape[0]
        if K < top:
            continue
        idx = np.argpartition(rng.random((nr, K)), top - 1, axis=1)[:, :top]
        vals = pm[idx].mean(axis=1)
        for o in range(T321_HOLD):
            M = po["k"] + o
            if k_first <= M <= k_end:
                rs[:, M - k_first] += vals[:, o]
    with np.errstate(invalid="ignore", divide="ignore"):
        rmonthly = rs / np.where(prim["count"] > 0, prim["count"], np.nan)
    rmeans = np.nanmean(rmonthly[:, keep], axis=1)
    phases = {}
    for ph in range(T321_HOLD):
        xp, cp = series(prim["port_month"], lambda po, ph=ph: po["k"] % T321_HOLD == ph)
        ok = np.isfinite(xp)
        phases[ph] = {"start_months": sorted({labels[po["k"]][5:] for po in ports if po["k"] % T321_HOLD == ph}),
                      "n_months": int(ok.sum()), "mean": float(xp[ok].mean()) if ok.any() else None}
    freq = {}
    for po in ports:
        for s_i in po["sel"]["top20"]:
            key = f"{names[po['I'][s_i]]}/{names[po['J'][s_i]]}"
            freq[key] = freq.get(key, 0) + 1
    top_pairs = sorted(freq.items(), key=lambda kv: -kv[1])[:12]
    op = np.concatenate([o for o in trades[T321_PRIMARY] if o.size]) if ports else np.zeros(0)
    return {"months": [m for m, k in zip(months, keep) if k], "x": prim["x"][keep],
            "cells": {"|".join(map(str, c)): v["x"][keep] for c, v in out_cells.items()},
            "count_min": int(prim["count"][keep].min()) if keep.any() else 0, "random_means": rmeans, "phases": phases,
            "top_pairs": top_pairs, "n_portfolios": len(ports),
            "universe": [ports[0]["n_elig"], ports[-1]["n_elig"]] if ports else None,
            "opens_per_pair": float(op.mean()) if op.size else None, "share_pairs_traded": float((op > 0).mean()) if op.size else None}


def ggr_judge(res: dict, min_n: int = T321_MIN_N) -> dict:
    x = np.asarray(res["x"], float)
    n = int(x.size)
    m = float(x.mean()) if n else None
    rows, ts = [], {}
    for bl in T321_BLOCKS:
        row, t = _stud_row(x, bl, "studentized CBB (Bartlett-HAC)")
        rows.append(row)
        ts[bl] = t
    c1 = all_constructions(rows, f"mean monthly net return {_bp(m)} > 0 with 95% CI excluding 0 (blocks {T321_BLOCKS[0]}, the "
                                 f"trial's, and {T321_BLOCKS[1]} = 2 x the 6-month hold, rule 10)")
    rm = np.asarray(res["random_means"], float)
    q95 = float(np.quantile(rm, 0.95)) if rm.size else None
    ok2 = None if q95 is None or m is None else m > q95
    c2 = (f"mean {_bp(m)} > 95th percentile of the random-pair control {_bp(q95)} ({rm.size} draws of 20 random pairs per "
          f"formation, same rules; control mean {_bp(float(rm.mean()) if rm.size else None)}, share of draws below the "
          f"strategy {_pu(float((rm < m).mean()) if rm.size and m is not None else None)})", ok2, ok2 is False)
    fam = {k: v for k, v in res["cells"].items()}
    fam_sr = [_sr_pp(v) for v in fam.values()]
    ds = dsr_family(x, fam_sr, T321_N_TRIALS)
    c3 = dsr_row(ds, f"DSR > {DSR_PASS} at {T321_N_TRIALS} trials (6 variants x 2 thresholds; {len(fam)} cells computed)")
    v, why = _decide([c1, c2, c3], n, min_n, "months")
    L = min(len(v_) for v_ in fam.values()) if fam else 0
    pbo = pbo_fast(np.column_stack([v_[:L] for v_ in fam.values()]), 16) if L >= 32 and len(fam) > 1 else None
    reg = {}
    for a, b in T321_REGIMES:
        k = np.array([a <= mm[:4] <= b for mm in res["months"]], bool)
        reg[f"{a}-{b}"] = {"n": int(k.sum()), "mean": float(x[k].mean()) if k.any() else None,
                           "sharpe_ann": _sr_ann(x[k], 12) if k.sum() > 2 else None}
    return {"n": n, "mean": m, "stud": ts, "q95_random": q95, "random_mean": float(rm.mean()) if rm.size else None,
            "dsr": ds, "pbo": pbo, "sharpe_ann": _sr_ann(x, 12), "regimes": reg,
            "family": {k: {"mean": float(np.mean(v_)), "sharpe_ann": _sr_ann(v_, 12)} for k, v_ in fam.items()},
            "criteria": [(c[0], c[1]) for c in (c1, c2, c3)], "verdict": v, "why": why}


# ================================================================================ T-322 cointegration persistence ==

T322_MIN_N = 200
T322_FIRST = "2008-01"
T322_FORM = 12
T322_HOLD = 6
T322_HL = (2.0, 30.0)
T322_BLOCK = 12                # window-start months: 1 year (the trial's), = 2 x the 6-month hold (rule 10)
T322_COST = {"etf": 0.0015, "crypto": 0.004}
T322_PPY = {"etf": 252, "crypto": 365}
T322_RULES = {"2/0.5/4": (2.0, 0.5, 4.0), "1.5/0/4": (1.5, 0.0, 4.0)}
T322_REGIMES = (("2008", "2009"), ("2020", "2020"), ("2022", "2022"))
_ROW_KEYS = ("cal", "k", "i", "j", "a", "b", "sd", "hl", "tau_f", "tau_o", "persist", "sel")


def coint_scan(days: Sequence[str], P: np.ndarray, cdays: Optional[Sequence[str]] = None, C: Optional[np.ndarray] = None,
               first: str = T322_FIRST, end: str = END) -> dict:
    """Engle-Granger selection and out-of-sample persistence for every window whose 6 trading months start at first..
    and end by ``end``'s month. Candidates: every pair (i < j in universe order; log i on log j) of the funds with a bar
    on the formation's first session, plus ETH on BTC (crypto calendar C: (Tc, 2) [ETH, BTC]) when both cover the
    formation. Log prices are rebased at the formation's first close. Returns per-window counts and the EG-passing
    pair-windows (with the half-life flag) for trading."""
    labels, mi, mf, ml = month_bounds(days)
    k_first = labels.index(first)
    k_end = max(k for k, m in enumerate(labels) if m <= end[:7])
    cpos = cmf = cml = None
    if cdays is not None and C is not None and len(cdays):
        clab, _, cmf, cml = month_bounds(cdays)
        cpos = {m: i for i, m in enumerate(clab)}
    wins = []
    rows = {k_: [] for k_ in _ROW_KEYS}
    for k in range(max(k_first, T322_FORM), k_end - T322_HOLD + 2):
        f0, f1, tr0, tr1 = mf[k - T322_FORM], ml[k - 1], mf[k], ml[k + T322_HOLD - 1]
        nf = f1 - f0 + 1
        elig = np.where(np.isfinite(P[f0]) & np.isfinite(P[tr1]))[0]
        parts = []
        if elig.size >= 2:
            I0, J0 = np.triu_indices(elig.size, 1)
            LP = np.log(P[f0:tr1 + 1][:, elig] / P[f0, elig])
            parts.append(("etf", elig[I0], elig[J0], LP[:nf, I0], LP[:nf, J0], LP[nf:, I0], LP[nf:, J0]))
        if cpos is not None and labels[k - T322_FORM] in cpos and labels[k + T322_HOLD - 1] in cpos:
            c0, c1 = cmf[cpos[labels[k - T322_FORM]]], cml[cpos[labels[k - 1]]]
            c3 = cml[cpos[labels[k + T322_HOLD - 1]]]
            if cdays[c0].endswith("-01") and np.isfinite(C[c0]).all() and np.isfinite(C[c3]).all():
                LC = np.log(C[c0:c3 + 1] / C[c0])
                n_c = c1 - c0 + 1
                parts.append(("crypto", np.array([0]), np.array([1]), LC[:n_c, :1], LC[:n_c, 1:2], LC[n_c:, :1], LC[n_c:, 1:2]))
        rec = {"k": k, "month": labels[k], "K": 0, "Q": 0, "n_sel": 0, "n_sel_per": 0, "n_eg": 0, "n_eg_per": 0,
               "n_sel_per_n2": 0, "crypto_sel": 0}
        for cal, I, J, Yf, Xf, Yt, Xt in parts:
            a, b, E = ols_cols(Yf, Xf)
            eg = adf_batch(E, "n")
            tau_f = eg["tau"]
            egok = np.isfinite(tau_f) & (tau_f < mackinnon_crit(2, 0.05, Yf.shape[0] - 1))
            hl = half_life(E)
            hlok = (hl >= T322_HL[0]) & (hl <= T322_HL[1])
            St = Yt - a - b * Xt
            oo = adf_batch(St, "c")
            per = np.isfinite(oo["tau"]) & (oo["tau"] < mackinnon_crit(1, 0.10, oo["nobs"]))
            per2 = np.isfinite(oo["tau"]) & (oo["tau"] < mackinnon_crit(2, 0.10, oo["nobs"]))
            sel = egok & hlok
            rec["K"] += int(I.size)
            rec["Q"] += int(per.sum())
            rec["n_sel"] += int(sel.sum())
            rec["n_sel_per"] += int((sel & per).sum())
            rec["n_eg"] += int(egok.sum())
            rec["n_eg_per"] += int((egok & per).sum())
            rec["n_sel_per_n2"] += int((sel & per2).sum())
            if cal == "crypto":
                rec["crypto_sel"] += int(sel.sum())
            ix = np.where(egok)[0]
            sd = E.std(axis=0, ddof=1)
            for key, val in (("cal", np.full(ix.size, cal, object)), ("k", np.full(ix.size, k)), ("i", I[ix]), ("j", J[ix]),
                             ("a", a[ix]), ("b", b[ix]), ("sd", sd[ix]), ("hl", hl[ix]), ("tau_f", tau_f[ix]),
                             ("tau_o", oo["tau"][ix]), ("persist", per[ix]), ("sel", sel[ix])):
                rows[key].append(val)
        wins.append(rec)
    rows = {k_: (np.concatenate(v) if v else np.zeros(0)) for k_, v in rows.items()}
    return {"windows": wins, "rows": rows, "labels": labels}


def persistence_judge(sc: dict, min_n: int = T322_MIN_N, n_random: Optional[int] = None, seed: int = SEED) -> dict:
    """T-322's criteria on a coint scan: the persistence share's 95% lower bound (circular block bootstrap over window
    months) > 50% and > the random-pair share + 20 pp (random draws of as many candidates per window as were selected:
    hypergeometric counts of persisting candidates)."""
    nr = N_RANDOM if n_random is None else int(n_random)
    W = sc["windows"]
    sel = np.array([w["n_sel"] for w in W], float)
    per = np.array([w["n_sel_per"] for w in W], float)
    K = np.array([w["K"] for w in W], int)
    Q = np.array([w["Q"] for w in W], int)
    tot = float(sel.sum())
    n = int(round(tot / T322_HOLD))
    rng = np.random.default_rng(seed)
    draws = np.zeros(nr)
    for kw, qw, sw in zip(K, Q, sel.astype(int)):
        if sw > 0 and kw > 0:
            draws += rng.hypergeometric(qw, kw - qw, min(sw, kw), size=nr)
    rshare = draws / tot if tot > 0 else draws * np.nan
    base = float(rshare.mean()) if tot > 0 else None
    thr2 = None if base is None else base + 0.20

    def chk(t):
        a = lb_check(t, 0.5)[0]
        b = lb_check(t, thr2)[0] if thr2 is not None else True
        return None if a is None or b is None else True
    t = _mc(lambda seed: cbb_ratio(per, sel, T322_BLOCK, seed=seed), chk) if tot > 0 else {"est": None, "ci": [None, None],
                                                                                          "ci1": [None, None]}
    share = t.get("est")
    o1, d1, n1 = lb_check(t, 0.5)
    o2, d2, n2 = lb_check(t, thr2) if thr2 is not None else (None, False, " [no selected pairs]")
    lo2, lo1 = (t.get("ci") or [None])[0], (t.get("ci1") or [None])[0]
    c1 = (f"95% lower bound of the persistence share > 50% (share {_pu(share)}, two-sided lower {_pu(lo2)}, one-sided lower "
          f"{_pu(lo1)}; circular block bootstrap over {len(W)} window months, {T322_BLOCK}-month blocks){n1}", o1, d1)
    c2 = (f"95% lower bound > random-pair share + 20 pp ({_pu(base)} + 20 pp = {_pu(thr2)}; {nr} draws of as many random "
          f"candidates per window as were selected, same test; 95th pct {_pu(float(np.quantile(rshare, .95)) if tot > 0 else None)})"
          f"{n2}", o2, d2)
    v, why = _decide([c1, c2], n, min_n, "selected pairs (non-overlapping equivalents: pooled pair-windows / 6)")
    exp = np.where(K > 0, sel * Q / np.maximum(K, 1), 0.0)
    td = _mc(lambda seed: cbb_ratio(per - exp, sel, T322_BLOCK, seed=seed), lambda t_: True) if tot > 0 else {}
    phases = {}
    for ph in range(T322_HOLD):
        kk = np.array([w["k"] % T322_HOLD == ph for w in W], bool)
        s_ = sel[kk].sum()
        phases[ph] = {"start_months": sorted({w["month"][5:] for w, k_ in zip(W, kk) if k_}), "n_sel": int(s_),
                      "share": float(per[kk].sum() / s_) if s_ > 0 else None}
    reg = {}
    for a_, b_ in T322_REGIMES:
        kk = np.array([a_ <= w["month"][:4] <= b_ for w in W], bool)
        s_ = sel[kk].sum()
        reg[f"{a_}-{b_}" if a_ != b_ else a_] = {"n_sel": int(s_), "share": float(per[kk].sum() / s_) if s_ > 0 else None}
    eg = np.array([w["n_eg"] for w in W], float)
    egp = np.array([w["n_eg_per"] for w in W], float)
    p2 = np.array([w["n_sel_per_n2"] for w in W], float)
    return {"n": n, "n_pair_windows": int(tot), "n_windows": len(W), "share": share, "boot": t, "random_share": base,
            "random_q95": float(np.quantile(rshare, 0.95)) if tot > 0 else None, "diff_vs_random": td,
            "candidate_share": float(Q.sum() / K.sum()) if K.sum() else None, "phases": phases, "regimes": reg,
            "share_no_hl_filter": float(egp.sum() / eg.sum()) if eg.sum() else None, "n_eg": int(eg.sum()),
            "share_n2_crit": float(p2.sum() / tot) if tot else None,
            "crypto_selected": int(sum(w["crypto_sel"] for w in W)), "criteria": [(c[0], c[1]) for c in (c1, c2)],
            "verdict": v, "why": why}


def pw_frame(sc: dict, mask: np.ndarray, cal: str, days: Sequence[str], P: np.ndarray, etf_days: Sequence[str]) -> Optional[dict]:
    """Arrays of the pair-windows ``mask`` (on the calendar ``cal`` with prices P on ``days``): formation log prices rebased
    at the formation's first close, left-padded so every formation ends at column F - 1 (Yf, Xf, Vf); trading log prices,
    leg returns, calendar-day gaps (Yt, Xt, RA, RB, DT, Vt; right-padded); the ETF-session index of every trading column
    (crypto days map to the first ETF session on or after them); OLS a, b, the formation residual sd, window k."""
    r = sc["rows"]
    ix = np.where(mask & (r["cal"] == cal))[0] if r["cal"].size else np.zeros(0, int)
    if ix.size == 0:
        return None
    labels, mi, mf, ml = month_bounds(days)
    lab_e = sc["labels"]
    R = _ret(P)
    DT = _dt(days)
    pos = {m: i for i, m in enumerate(labels)}
    spans = []
    for k in r["k"][ix]:
        lk = lab_e[int(k)]
        kk = pos[lk]
        f0 = mf[pos[lab_e[int(k) - T322_FORM]]]
        f1 = ml[kk - 1]
        tr0, tr1 = mf[kk], ml[pos[lab_e[int(k) + T322_HOLD - 1]]]
        spans.append((f0, f1, tr0, tr1))
    F = max(s[1] - s[0] + 1 for s in spans)
    Tt = max(s[3] - s[2] + 1 for s in spans)
    N = ix.size
    Yf = np.zeros((N, F))
    Xf = np.zeros((N, F))
    Vf = np.zeros((N, F), bool)
    Yt = np.zeros((N, Tt))
    Xt = np.zeros((N, Tt))
    RA = np.zeros((N, Tt))
    RB = np.zeros((N, Tt))
    DTt = np.ones((N, Tt))
    Vt = np.zeros((N, Tt), bool)
    DI = np.zeros((N, Tt), int)
    ed = np.array(etf_days)
    dmap = np.minimum(np.searchsorted(ed, np.array(days)), len(etf_days) - 1) if cal == "crypto" else np.arange(len(days))
    I, J = r["i"][ix].astype(int), r["j"][ix].astype(int)
    for q, (f0, f1, tr0, tr1) in enumerate(spans):
        i, j = I[q], J[q]
        nf, nt = f1 - f0 + 1, tr1 - tr0 + 1
        ly = np.log(P[f0:tr1 + 1, i] / P[f0, i])
        lx = np.log(P[f0:tr1 + 1, j] / P[f0, j])
        Yf[q, F - nf:] = ly[:nf]
        Xf[q, F - nf:] = lx[:nf]
        Vf[q, F - nf:] = True
        Yt[q, :nt] = ly[nf:]
        Xt[q, :nt] = lx[nf:]
        RA[q, :nt] = R[tr0:tr1 + 1, i]
        RB[q, :nt] = R[tr0:tr1 + 1, j]
        DTt[q, :nt] = DT[tr0:tr1 + 1]
        Vt[q, :nt] = True
        DI[q, :nt] = dmap[tr0:tr1 + 1]
        DI[q, nt:] = DI[q, nt - 1]
    return {"ix": ix, "cal": cal, "Yf": Yf, "Xf": Xf, "Vf": Vf, "Yt": Yt, "Xt": Xt, "RA": RA, "RB": RB, "DT": DTt, "Vt": Vt,
            "DI": DI, "a": r["a"][ix].astype(float), "b": r["b"][ix].astype(float), "sd": r["sd"][ix].astype(float),
            "k": r["k"][ix].astype(int), "ppy": T322_PPY[cal], "cost": T322_COST[cal]}


def static_sim(fr: dict, rule: tuple) -> dict:
    """Static OLS hedge: z = (spread - 0) / formation residual sd with beta and alpha frozen; P&L per $(1 + |beta|)."""
    z = (fr["Yt"] - fr["a"][:, None] - fr["b"][:, None] * fr["Xt"]) / fr["sd"][:, None]
    z = np.where(fr["Vt"], z, np.nan)
    res = spread_sim(z, fr["b"][:, None] * np.ones_like(z), fr["RA"], fr["RB"], fr["Vt"], rule[0], rule[1], rule[2],
                     fr["cost"], fr["cost"], 0.0, fr["DT"], 1)
    res["pnl"] = res["pnl"] / (1.0 + np.abs(fr["b"]))[:, None]
    return res


def aggregate(frames_pnl: Sequence[tuple], n_days: int) -> tuple:
    """Equal-weight daily portfolio of pair-windows on the ETF session calendar: [(pnl (N, T), valid (N, T), DI (N, T))]
    -> (daily return, active count) per ETF session (NaN where nothing is active)."""
    s = np.zeros(n_days)
    c = np.zeros(n_days)
    for pnl, V, DI in frames_pnl:
        np.add.at(s, DI[V], pnl[V])
        newday = V & np.c_[np.ones((V.shape[0], 1), bool), DI[:, 1:] != DI[:, :-1]]
        np.add.at(c, DI[newday], 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / np.maximum(c, 1), np.nan), c


# ============================================================================================ T-323 Kalman hedge ==

T323_MIN_N = 100
T323_EM_ITERS = 40
T323_DELTA_FIXED = 1e-4
T323_P0 = 1.0
T323_REBAL = 0.05
T323_SPLIT = "2017-01"
T323_LW_BLOCK = 21
T323_N_TRIALS = 4               # delta (EM, 1e-4) x entry (2, 1 innovation sd)
T323_KCELLS = {"EM, 2/0.5/4": ("em", (2.0, 0.5, 4.0)), "EM, 1/0": ("em", (1.0, 0.0, np.inf)),
               "delta 1e-4, 2/0.5/4": ("fixed", (2.0, 0.5, 4.0)), "delta 1e-4, 1/0": ("fixed", (1.0, 0.0, np.inf))}
T323_PRIMARY = "EM, 2/0.5/4"
T323_CHUNK = 3000


def kalman_pass(Y, X, V, w, R, m0, p0: float = T323_P0, store: bool = False) -> dict:
    """Kalman filter of y_t = alpha_t + beta_t x_t + v_t (var R) with (alpha, beta) a random walk of covariance w I, rows
    (N, T) at once; V masks missing observations (prediction only). Initial state m0 (N, 2) with covariance p0 I one step
    before the first column. Returns innovations e, their variances Q, the filtered alpha/beta and, with ``store``, the
    predicted and filtered moments for the smoother."""
    N, T = Y.shape
    a, b = m0[:, 0].astype(float).copy(), m0[:, 1].astype(float).copy()
    p11 = np.full(N, float(p0))
    p12 = np.zeros(N)
    p22 = np.full(N, float(p0))
    E = np.full((N, T), np.nan)
    Qv = np.full((N, T), np.nan)
    AF = np.zeros((N, T))
    BF = np.zeros((N, T))
    st = None
    if store:
        st = {k_: np.zeros((T, N)) for k_ in ("pa", "pb", "p11", "p12", "p22", "fa", "fb", "f11", "f12", "f22")}
    for t in range(T):
        p11 = p11 + w
        p22 = p22 + w
        if store:
            st["pa"][t], st["pb"][t], st["p11"][t], st["p12"][t], st["p22"][t] = a, b, p11, p12, p22
        v = V[:, t]
        x = np.where(v, X[:, t], 0.0)
        y = np.where(v, Y[:, t], 0.0)
        q = p11 + 2.0 * x * p12 + x * x * p22 + R
        e = y - a - b * x
        h0 = p11 + x * p12
        h1 = p12 + x * p22
        a = np.where(v, a + h0 / q * e, a)
        b = np.where(v, b + h1 / q * e, b)
        p11 = np.where(v, np.maximum(p11 - h0 * h0 / q, 1e-14), p11)
        p12n = np.where(v, p12 - h0 * h1 / q, p12)
        p22 = np.where(v, np.maximum(p22 - h1 * h1 / q, 1e-14), p22)
        p12 = p12n
        E[:, t] = np.where(v, e, np.nan)
        Qv[:, t] = np.where(v, q, np.nan)
        AF[:, t] = a
        BF[:, t] = b
        if store:
            st["fa"][t], st["fb"][t], st["f11"][t], st["f12"][t], st["f22"][t] = a, b, p11, p12, p22
    return {"e": E, "Q": Qv, "alpha": AF, "beta": BF, "st": st}


def kalman_em(Y, X, V, n_iter: int = T323_EM_ITERS, delta: Optional[float] = None, p0: float = T323_P0) -> dict:
    """EM (Shumway-Stoffer, RTS smoother with the lag-one covariance) for the state noise w (both states, w = delta /
    (1 - delta)) and the observation noise R of ``kalman_pass`` on each row's valid (formation) columns; ``delta`` fixes w
    and only R is estimated. Initial state: the row's OLS (alpha, beta). Returns w, R, delta and m0 per row."""
    Y, X, V = np.asarray(Y, float), np.asarray(X, float), np.asarray(V, bool)
    N, T = Y.shape
    nv = V.sum(axis=1)
    xm = np.where(V, X, 0).sum(axis=1) / np.maximum(nv, 1)
    ym = np.where(V, Y, 0).sum(axis=1) / np.maximum(nv, 1)
    dx = np.where(V, X - xm[:, None], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        b0 = (dx * np.where(V, Y - ym[:, None], 0.0)).sum(axis=1) / (dx * dx).sum(axis=1)
    b0 = np.nan_to_num(b0)
    a0 = ym - b0 * xm
    m0 = np.column_stack([a0, b0])
    res0 = np.where(V, Y - a0[:, None] - b0[:, None] * X, 0.0)
    R = np.maximum((res0 ** 2).sum(axis=1) / np.maximum(nv - 2, 1), 1e-12)
    w = np.full(N, (delta if delta is not None else 1e-4) / (1.0 - (delta if delta is not None else 1e-4)))
    trans = np.zeros((T, N), bool)
    trans[1:] = (V[:, 1:] & V[:, :-1]).T
    ntr = np.maximum(trans.sum(axis=0), 1)
    for _ in range(int(n_iter)):
        f = kalman_pass(Y, X, V, w, R, m0, p0, store=True)
        st = f["st"]
        sa, sb = st["fa"][T - 1].copy(), st["fb"][T - 1].copy()
        s11, s12, s22 = st["f11"][T - 1].copy(), st["f12"][T - 1].copy(), st["f22"][T - 1].copy()
        acc_w = np.zeros(N)
        xT = np.where(V[:, T - 1], X[:, T - 1], 0.0)
        acc_r = np.where(V[:, T - 1], (Y[:, T - 1] - sa - sb * xT) ** 2 + s11 + 2 * xT * s12 + xT * xT * s22, 0.0)
        for t in range(T - 2, -1, -1):
            q11, q12, q22 = st["p11"][t + 1], st["p12"][t + 1], st["p22"][t + 1]
            det = np.maximum(q11 * q22 - q12 * q12, 1e-300)
            i11, i12, i22 = q22 / det, -q12 / det, q11 / det
            f11, f12, f22 = st["f11"][t], st["f12"][t], st["f22"][t]
            j11 = f11 * i11 + f12 * i12
            j12 = f11 * i12 + f12 * i22
            j21 = f12 * i11 + f22 * i12
            j22 = f12 * i12 + f22 * i22
            c_tr = (s11 * j11 + s12 * j12) + (s12 * j21 + s22 * j22)       # tr(P_{t+1|T} J_t')
            da, db = sa - st["pa"][t + 1], sb - st["pb"][t + 1]
            na = st["fa"][t] + j11 * da + j12 * db
            nb = st["fb"][t] + j21 * da + j22 * db
            d11, d12, d22 = s11 - q11, s12 - q12, s22 - q22
            m11 = j11 * d11 + j12 * d12
            m12 = j11 * d12 + j12 * d22
            m21 = j21 * d11 + j22 * d12
            m22 = j21 * d12 + j22 * d22
            n11 = f11 + m11 * j11 + m12 * j12
            n12 = f12 + m11 * j21 + m12 * j22
            n22 = f22 + m21 * j21 + m22 * j22
            inc = (sa - na) ** 2 + (sb - nb) ** 2 + (s11 + s22) + (n11 + n22) - 2.0 * c_tr
            acc_w += np.where(trans[t + 1], inc, 0.0)
            sa, sb, s11, s12, s22 = na, nb, n11, n12, n22
            xt = np.where(V[:, t], X[:, t], 0.0)
            acc_r += np.where(V[:, t], (Y[:, t] - sa - sb * xt) ** 2 + s11 + 2 * xt * s12 + xt * xt * s22, 0.0)
        if delta is None:
            w = np.maximum(acc_w / (2.0 * ntr), 1e-14)
        R = np.maximum(acc_r / np.maximum(nv, 1), 1e-14)
    return {"w": w, "R": R, "delta": w / (1.0 + w), "m0": m0}


def kalman_frame(fr: dict, delta: Optional[float], n_iter: int = T323_EM_ITERS, chunk: int = T323_CHUNK) -> dict:
    """EM on each pair-window's formation, then the filter run forward through formation and trading with the formation
    parameters: trading-column standardized innovations z = e / sqrt(Q) and filtered betas (known at each close)."""
    N = fr["Yf"].shape[0]
    Tt = fr["Yt"].shape[1]
    Z = np.full((N, Tt), np.nan)
    Bt = np.zeros((N, Tt))
    dl = np.zeros(N)
    for c0 in range(0, N, chunk):
        q = slice(c0, min(N, c0 + chunk))
        em = kalman_em(fr["Yf"][q], fr["Xf"][q], fr["Vf"][q], n_iter, delta)
        Yc = np.concatenate([fr["Yf"][q], fr["Yt"][q]], axis=1)
        Xc = np.concatenate([fr["Xf"][q], fr["Xt"][q]], axis=1)
        Vc = np.concatenate([fr["Vf"][q], fr["Vt"][q]], axis=1)
        kp = kalman_pass(Yc, Xc, Vc, em["w"], em["R"], em["m0"])
        F = fr["Yf"].shape[1]
        with np.errstate(invalid="ignore", divide="ignore"):
            Z[q] = kp["e"][:, F:] / np.sqrt(kp["Q"][:, F:])
        Bt[q] = kp["beta"][:, F:]
        dl[q] = em["delta"]
    Z = np.where(fr["Vt"], Z, np.nan)
    return {"z": Z, "beta": Bt, "delta": dl}


def kalman_sim(fr: dict, kf: dict, rule: tuple) -> dict:
    res = spread_sim(kf["z"], kf["beta"], fr["RA"], fr["RB"], fr["Vt"], rule[0], rule[1], rule[2], fr["cost"], fr["cost"], 0.0,
                     fr["DT"], 1, rebalance=T323_REBAL)
    res["pnl"] = res["pnl"] / (1.0 + np.abs(fr["b"]))[:, None]
    return res


# ============================================================================== per-trade z rule (T-468, T-470) ==

def trade_rule(days: Sequence[str], z, rA, rB, entry: float = 2.0, exit_z: float = 0.0, max_hold: int = 20,
               cost_a: float = 0.0005, cost_b: float = 0.0005, borrow: float = 0.005, start: str = "", end: str = END,
               gate: Optional[Callable] = None) -> dict:
    """Equal-dollar z rule on one pair. z[t]: signal known at close t (NaN: no decision that close); rA/rB[t]: the legs'
    simple returns close t-1 -> t. z > entry: short $1 A / long $1 B; z < -entry: long A / short B; filled at close t + 1.
    Exit decided when z crosses back through +/-exit_z (short-A side: z <= exit_z; long-A side: z >= -exit_z) and filled at
    the next close, or the time stop fills at close e + max_hold (e = entry fill). Entry decisions only on closes dated >=
    ``start``; nothing fills after ``end`` and a position open then is closed at the last close <= end. ``gate(t, side)``
    (side -1 = short A) may veto an entry. Costs per $ traded per leg at each fill, borrow per year on the short leg's value
    (calendar days). Returns the trades (entry/exit dates, side, sessions held, net P&L per $1 per leg) and the daily net
    P&L over [first decision day, last close <= end]."""
    n = len(days)
    z = np.asarray(z, float)
    rA, rB = np.asarray(rA, float), np.asarray(rB, float)
    t_end = bisect.bisect_right(list(days), end) - 1
    t0 = bisect.bisect_left(list(days), start) if start else 0
    if t_end <= t0:
        return {"trades": [], "pnl": np.zeros(0), "days": [], "t0": t0}
    o = np.array([_ord(d) for d in days])
    dt = np.r_[1, np.diff(o)]
    pnl = np.zeros(t_end - t0 + 1)
    pos, tgt, e = 0, 0, -1
    A = B = 0.0
    trades, cur = [], None
    for t in range(t0, t_end + 1):
        k = t - t0
        if pos != 0 and t > e:
            sh = max(-A, 0.0) + max(-B, 0.0)
            pnl[k] += A * rA[t] + B * rB[t] - borrow * sh * dt[t] / 365.0
            A *= 1.0 + rA[t]
            B *= 1.0 + rB[t]
        if pos != 0 and (tgt == 0 or t - e >= max_hold or t == t_end):
            pnl[k] -= cost_a * abs(A) + cost_b * abs(B)
            cur.update(exit=days[t], days_held=t - e, pnl=float(pnl[e - t0:k + 1].sum()),
                       reason="time stop" if (tgt != 0 and t - e >= max_hold) else ("window end" if tgt != 0 else "z exit"))
            trades.append(cur)
            cur, pos, tgt, A, B = None, 0, 0, 0.0, 0.0
        elif pos == 0 and tgt != 0:
            if t == t_end:
                tgt = 0
            else:
                pos, e = tgt, t
                A, B = float(pos), float(-pos)
                pnl[k] -= cost_a + cost_b
                cur = {"entry": days[t], "decided": days[t - 1], "side": "long A/short B" if pos == 1 else "short A/long B"}
        zt = z[t]
        if t == t_end or not math.isfinite(zt):
            continue
        if pos == 0 and tgt == 0 and days[t] >= start:
            side = -1 if zt > entry else (1 if zt < -entry else 0)
            if side != 0 and (gate is None or gate(t, side)):
                tgt = side
        elif pos != 0 and tgt == pos:
            if (pos == -1 and zt <= exit_z) or (pos == 1 and zt >= -exit_z):
                tgt = 0
    return {"trades": trades, "pnl": pnl, "days": list(days[t0:t_end + 1]), "t0": t0}


def trailing_z_masked(s, ok, L: int, min_obs: int = 2) -> np.ndarray:
    """z_t = (s_t - mean) / sd (ddof 1) over the values with ``ok`` among the trailing L sessions t-L+1..t, defined only
    on ok sessions with at least ``min_obs`` such values."""
    s = np.where(ok, np.asarray(s, float), 0.0)
    okf = np.asarray(ok, bool).astype(float)
    n = s.size
    ref = float(s[okf > 0][0]) if okf.any() else 0.0
    c = np.where(okf > 0, s - ref, 0.0)
    cs = np.concatenate([[0.0], np.cumsum(okf)])
    s1 = np.concatenate([[0.0], np.cumsum(c)])
    s2 = np.concatenate([[0.0], np.cumsum(c * c)])
    hi = np.arange(1, n + 1)
    lo = np.maximum(hi - L, 0)
    cnt = cs[hi] - cs[lo]
    m1 = s1[hi] - s1[lo]
    m2 = s2[hi] - s2[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = m1 / cnt
        var = (m2 - cnt * mu * mu) / (cnt - 1)
        sd = np.sqrt(np.maximum(var, 0.0))
        z = (c - mu) / sd
    return np.where((okf > 0) & (cnt >= max(min_obs, 2)) & (sd > 1e-12), z, np.nan)


def _common(*series: tuple) -> tuple:
    common = set(series[0][0])
    for d, _ in series[1:]:
        common &= set(d)
    days = sorted(common)
    out = []
    for d, v in series:
        ix = {x: i for i, x in enumerate(d)}
        out.append(np.array([v[ix[x]] for x in days], float))
    return days, out


def _rets(x: np.ndarray) -> np.ndarray:
    return np.r_[0.0, x[1:] / x[:-1] - 1.0]


def trade_stats(trades: list) -> dict:
    p = np.array([t["pnl"] for t in trades], float)
    return {"n": int(p.size), "mean": float(p.mean()) if p.size else None, "win_rate": float((p > 0).mean()) if p.size else None,
            "sum": float(p.sum()) if p.size else 0.0}


# =========================================================================================== T-468 Brent-WTI ==

T468_MIN_N = 20
T468_START = "2011-01-01"
T468_L = 250
T468_MIN_OBS = 50              # unmasked values required in the trailing 250-session window
T468_ENTRY, T468_EXIT, T468_MAX_HOLD = 2.0, 0.0, 60
T468_COST = 0.0005
T468_BORROW = 0.005
T468_ROLL_WIN = 5
T468_SHIFT_BLOCK = 60
T468_N_TRIALS = 3
T468_SUBS = (("2011", "2014"), ("2015", "2019"), ("2020", "2026"))
T468_EXCLUDE = ("2020-04-01", "2020-04-30")


def _weekday_before(d: date, k: int) -> date:
    """The k-th weekday strictly before d."""
    out = d
    while k > 0:
        out -= timedelta(days=1)
        if out.weekday() < 5:
            k -= 1
    return out


def cl_last_trade(y: int, m: int) -> date:
    """NYMEX WTI (CL) last trading day of contract month (y, m): 3 business days before the 25th calendar day of the month
    before (4 when the 25th is not a business day). Weekdays only (exchange holidays not modelled)."""
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    d25 = date(py, pm, 25)
    return _weekday_before(d25, 3 if d25.weekday() < 5 else 4)


def bz_last_trade(y: int, m: int) -> date:
    """Brent (ICE Brent / NYMEX BZ) last trading day of contract month (y, m): from the March 2016 contract the last
    business day of the second month before; earlier, the business day before the 15th calendar day before the first day
    of the contract month (stepping back first when that day is a weekend). Weekdays only."""
    if (y, m) >= (2016, 3):
        py, pm = (y, m - 2) if m > 2 else (y - 1, m + 10)
        d = date(py + (pm == 12), pm % 12 + 1, 1) - timedelta(days=1)
        while d.weekday() > 4:
            d -= timedelta(days=1)
        return d
    d15 = date(y, m, 1) - timedelta(days=15)
    while d15.weekday() > 4:
        d15 -= timedelta(days=1)
    return _weekday_before(d15, 1)


def roll_mask(days: Sequence[str], window: int = T468_ROLL_WIN) -> np.ndarray:
    """True on the sessions within +-``window`` sessions of the scheduled last trading day of either front contract."""
    n = len(days)
    fl = np.zeros(n, bool)
    if not n:
        return fl
    y0, y1 = int(days[0][:4]), int(days[-1][:4]) + 1
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            for fn in (cl_last_trade, bz_last_trade):
                ltd = fn(y, m).isoformat()
                if ltd < days[0] or ltd > days[-1]:
                    continue
                j = bisect.bisect_right(days, ltd) - 1
                fl[max(0, j - window):min(n, j + window + 1)] = True
    return fl


def _shift_null(ed: Sequence[str], z: np.ndarray, rA, rB, kw: dict, block: int) -> dict:
    """Block-shifted signal null: the signal over the trading window circularly shifted by every multiple of ``block``
    sessions against the fixed fund returns; the null mean net return per trade of each shift."""
    t0 = bisect.bisect_left(list(ed), kw.get("start", "")) if kw.get("start") else 0
    t1 = bisect.bisect_right(list(ed), kw.get("end", END)) - 1
    seg = z[t0:t1 + 1]
    n = seg.size
    means = []
    for j in range(1, n // block):
        zz = z.copy()
        zz[t0:t1 + 1] = np.roll(seg, j * block)
        tr = trade_rule(ed, zz, rA, rB, **kw)["trades"]
        if tr:
            means.append(float(np.mean([t["pnl"] for t in tr])))
    return {"means": np.array(means), "n_shifts": n // block - 1}


def brent_wti(fut: dict, etf: dict, uga: Optional[tuple] = None, min_n: int = T468_MIN_N, start: str = T468_START,
              end: str = END) -> dict:
    """T-468 core. fut: {'BZ': (days, close), 'CL': (days, close)}; etf: {'USO': (days, adjclose), 'BNO': (days, adjclose)};
    uga: (days, adjclose) for the crack-spread variant. Signal on futures sessions, trades on the funds' common sessions
    (a decision on fund session D uses the futures z dated D; a session without a futures bar takes no decision)."""
    fd, (bz, cl) = _common(fut["BZ"], fut["CL"])
    okp = (bz > 0) & (cl > 0)
    excl = np.array([T468_EXCLUDE[0] <= d <= T468_EXCLUDE[1] for d in fd], bool)
    rm = roll_mask(fd)
    ok = okp & ~excl & ~rm
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(okp, np.log(np.where(okp, bz, 1.0) / np.where(okp, cl, 1.0)), np.nan)
    zf = trailing_z_masked(s, ok, T468_L, T468_MIN_OBS)
    zf_all = trailing_z_masked(s, okp & ~excl, T468_L, T468_MIN_OBS)          # sensitivity: stats over every session
    zf_all = np.where(ok, zf_all, np.nan)
    sd_ = np.where(okp, bz - cl, np.nan)
    zf_usd = trailing_z_masked(sd_, ok, T468_L, T468_MIN_OBS)
    ed, (uso, bno) = _common(etf["USO"], etf["BNO"])
    fpos = {d: i for i, d in enumerate(fd)}

    def onto(zz):
        return np.array([zz[fpos[d]] if d in fpos else np.nan for d in ed], float)

    ze = onto(zf)
    rU, rBn = _rets(uso), _rets(bno)
    kw = dict(entry=T468_ENTRY, exit_z=T468_EXIT, max_hold=T468_MAX_HOLD, cost_a=T468_COST, cost_b=T468_COST,
              borrow=T468_BORROW, start=start, end=end)
    prim = trade_rule(ed, ze, rBn, rU, **kw)            # A = BNO (Brent leg), B = USO (WTI leg): z > 2 -> long USO / short BNO
    tr = prim["trades"]
    pn = np.array([t["pnl"] for t in tr], float)
    n_tr = int(pn.size)
    mean = float(pn.mean()) if n_tr else None

    def boot(seed):
        return cluster_ratio(pn, np.ones_like(pn), seed=seed) if n_tr >= 8 else {"est": mean, "ci": [None, None], "ci1": [None, None]}
    tb = _mc(boot, lambda t: lb_check(t, 0.0)[0]) if n_tr >= 8 else boot(SEED)
    ok1, dec1, note1 = lb_check(tb, 0.0) if n_tr >= 8 else (None, False, " [fewer than 8 trades]")
    nul = _shift_null(ed, ze, rBn, rU, kw, T468_SHIFT_BLOCK)
    nm = nul["means"]
    p_null = float((1 + np.sum(nm >= mean)) / (1 + nm.size)) if (nm.size and mean is not None) else None
    okn = None if p_null is None else p_null < 0.05
    decn = p_null is not None and p_null >= 0.95
    c1 = all_constructions([(f"trade bootstrap (percentile, {n_tr} trades): two-sided lower {_bp(tb['ci'][0], 1)}, one-sided "
                             f"lower {_bp((tb.get('ci1') or [None])[0], 1)}{note1}", ok1, dec1),
                            (f"block-shifted signal null (every multiple of {T468_SHIFT_BLOCK} sessions, {nm.size} shifts "
                             f"with trades): one-sided p {_f(p_null)} < 0.05", okn, decn)],
                           f"95% lower bound of the mean net return per trade {_bp(mean, 1)} > 0")
    c2 = (f"at least 20 trades ({n_tr})", n_tr >= 20, n_tr < 20)
    subs = {}
    for a_, b_ in T468_SUBS:
        p_ = [t["pnl"] for t in tr if a_ <= t["entry"][:4] <= b_]
        subs[f"{a_}-{b_}"] = {"n": len(p_), "mean": float(np.mean(p_)) if p_ else None}
    npos = sum(1 for v_ in subs.values() if v_["mean"] is not None and v_["mean"] > 0)
    nund = sum(1 for v_ in subs.values() if v_["mean"] is None)
    ok3 = True if npos >= 2 else (False if npos + nund < 2 else None)
    c3 = ("positive mean per trade in >= 2 of 3 sub-periods (" + ", ".join(
        f"{k_} {_bp(v_['mean'], 1)} ({v_['n']} trades)" for k_, v_ in subs.items()) + ")", ok3, False)
    v, why = _decide([c1, c2, c3], n_tr, min_n, "trades")
    fam = {"USO/BNO on the log futures spread (primary)": prim["pnl"]}
    usd = trade_rule(ed, onto(zf_usd), rBn, rU, **kw)
    fam["USO/BNO on the dollar futures spread"] = usd["pnl"]
    var_uga = None
    if uga is not None:
        gd, (ug, us2) = _common(uga, etf["USO"])
        sg = np.log(ug / us2)
        zg = trailing_z_masked(sg, np.ones(len(gd), bool), T468_L, T468_MIN_OBS)
        rg = trade_rule(gd, zg, _rets(ug), _rets(us2), **kw)
        fam["UGA/USO crack-spread proxy"] = rg["pnl"]
        var_uga = trade_stats(rg["trades"])
    ds = dsr_family(prim["pnl"], [_sr_pp(x) for x in fam.values()], T468_N_TRIALS)
    sens = trade_stats(trade_rule(ed, onto(zf_all), rBn, rU, **kw)["trades"])
    hl = {}
    for a_, b_ in T468_SUBS:
        kk = np.array([a_ <= d[:4] <= b_ for d in fd], bool) & ok
        x_ = s[kk]
        if x_.size > 30:
            hl[f"{a_}-{b_}"] = float(half_life(x_[:, None])[0])
    s_etf = np.log(bno / uso)
    epos = {d: i for i, d in enumerate(ed)}
    both = [d for d in fd if d in epos]
    zfe = np.array([zf[fpos[d]] for d in both])
    ze2 = trailing_z_masked(s_etf, np.ones(len(ed), bool), T468_L, T468_MIN_OBS)
    zee = np.array([ze2[epos[d]] for d in both])
    m_ = np.isfinite(zfe) & np.isfinite(zee)
    corr = float(np.corrcoef(zfe[m_], zee[m_])[0, 1]) if m_.sum() > 10 else None
    return {"n": n_tr, "mean": mean, "boot": tb, "p_null": p_null, "null_mean": float(nm.mean()) if nm.size else None,
            "trades": tr, "subs": subs, "dsr": ds, "family": {k_: {"sharpe_pp": _sr_pp(x)} for k_, x in fam.items()},
            "usd_variant": trade_stats(usd["trades"]), "uga_variant": var_uga, "sens_stats_all_sessions": sens,
            "half_life": hl, "corr_z_futures_vs_etf": corr, "mask_share": float(rm.mean()), "n_signal_sessions": int(ok.sum()),
            "window": (prim["days"][0], prim["days"][-1]) if prim["days"] else None, "reasons": _tally(tr),
            "criteria": [(c[0], c[1]) for c in (c1, c2, c3)], "verdict": v, "why": why}


def _tally(trades: list) -> dict:
    out = {}
    for t in trades:
        out[t.get("reason", "?")] = out.get(t.get("reason", "?"), 0) + 1
    return out


# =========================================================================================== T-470 dual class ==

T470_MIN_N = 200
T470_START = "2014-01-01"
T470_END = "2026-12-31"
T470_L = 60
T470_ENTRY, T470_EXIT, T470_MAX_HOLD = 2.0, 0.0, 20
T470_COST = 0.0005
T470_COST_THIN = 0.0025
T470_THIN = ("BF-A", "LEN-B", "HEI-A")
T470_BORROW = 0.005
T470_N_TRIALS = 5
T470_LIQ_L = 60
# (A, B, k, first session both classes trade as separate lines); x = ln(A) - ln(k B)
T470_PAIRS = (("GOOGL", "GOOG", 1.0, "2014-04-03"), ("BRK-A", "BRK-B", 1500.0, "2010-01-21"), ("NWSA", "NWS", 1.0, "2013-06-19"),
              ("FOXA", "FOX", 1.0, "2019-03-19"), ("LBRDK", "LBRDA", 1.0, "2014-11-04"), ("BF-B", "BF-A", 1.0, ""),
              ("LEN", "LEN-B", 1.0, ""), ("HEI", "HEI-A", 1.0, ""), ("ZG", "Z", 1.0, "2015-08-03"), ("UA", "UAA", 1.0, "2016-04-08"))
T470_HALF = "2020-05-24"


def _trailing_median(x: np.ndarray, L: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for t in range(L - 1, x.size):
        out[t] = float(np.median(x[t - L + 1:t + 1]))
    return out


def dual_pair(dA: dict, dB: dict, k: float, first: str, costs: tuple, entry: float = T470_ENTRY, exit_z: float = T470_EXIT,
              liquidity: bool = False, start: str = T470_START, end: str = T470_END) -> dict:
    """One dual-class pair: dA/dB {'days', 'adj', 'close', 'vol'}. z on the trailing 60 sessions of x = ln(adjA) - ln(k adjB)
    from the pair's first separate-line session; trades per ``trade_rule``. liquidity: enter only when the class to be
    shorted has the higher trailing-60-session median dollar volume (through the decision close)."""
    days, (aA, aB, cA, cB, vA, vB) = _common((dA["days"], dA["adj"]), (dB["days"], dB["adj"]), (dA["days"], dA["close"]),
                                             (dB["days"], dB["close"]), (dA["days"], dA["vol"]), (dB["days"], dB["vol"]))
    keep = [i for i, d in enumerate(days) if d >= first] if first else list(range(len(days)))
    if len(keep) < T470_L + 5:
        return {"trades": [], "pnl": np.zeros(0), "days": [], "n_days": len(keep)}
    days = [days[i] for i in keep]
    aA, aB, cA, cB, vA, vB = (x[keep] for x in (aA, aB, cA, cB, vA, vB))
    x = np.log(aA) - np.log(k * aB)
    z = trailing_z_masked(x, np.ones(len(days), bool), T470_L, T470_L)
    gate = None
    if liquidity:
        mA = _trailing_median(cA * vA, T470_LIQ_L)
        mB = _trailing_median(cB * vB, T470_LIQ_L)
        gate = lambda t, side: bool(np.isfinite(mA[t]) and np.isfinite(mB[t]) and ((mA[t] > mB[t]) if side == -1 else (mB[t] > mA[t])))
    res = trade_rule(days, z, _rets(aA), _rets(aB), entry, exit_z, T470_MAX_HOLD, costs[0], costs[1], T470_BORROW, start, end,
                     gate)
    res["n_days"] = len(days)
    return res


def dual_class(data: dict, min_n: int = T470_MIN_N, start: str = T470_START, end: str = T470_END,
               pairs: Sequence[tuple] = T470_PAIRS) -> dict:
    """T-470 core. data: {ticker: _daily dict} (a pair with a missing ticker is reported as not archived). Runs every pair
    under both cost readings and the 5 declared variants; pools trades; judges the criteria."""
    readings = {"claim: 5 bps per leg": lambda s: T470_COST,
                "controls: 25 bps on BF-A/LEN-B/HEI-A legs": lambda s: T470_COST_THIN if s in T470_THIN else T470_COST}
    per_pair, missing = {}, []
    pooled = {r_: [] for r_ in readings}
    daily = {r_: {} for r_ in readings}
    var_daily = {"|z| > 1.5": {}, "exit at 0.5 sd": {}, "liquidity-ordered": {}}
    for A, B, k, first in pairs:
        name = f"{A}/{B}"
        if A not in data or B not in data:
            missing.append(name)
            per_pair[name] = None
            continue
        per_pair[name] = {}
        for r_, cf in readings.items():
            res = dual_pair(data[A], data[B], k, first, (cf(A), cf(B)), start=start, end=end)
            st = trade_stats(res["trades"])
            per_pair[name][r_] = {**st, "positive": bool(st["mean"] is not None and st["mean"] > 0)}
            for t in res["trades"]:
                pooled[r_].append({**t, "pair": name})
            daily[r_][name] = (res["days"], res["pnl"])
        cf0 = readings["claim: 5 bps per leg"]
        for vn, kw in (("|z| > 1.5", {"entry": 1.5}), ("exit at 0.5 sd", {"exit_z": 0.5}), ("liquidity-ordered", {"liquidity": True})):
            res = dual_pair(data[A], data[B], k, first, (cf0(A), cf0(B)), start=start, end=end, **kw)
            var_daily[vn][name] = (res["days"], res["pnl"])

    def pool_daily(dd: dict) -> np.ndarray:
        allp = sorted({d for ds_, _ in dd.values() for d in ds_})
        pos_ = {d: i for i, d in enumerate(allp)}
        s_ = np.zeros(len(allp))
        c_ = np.zeros(len(allp))
        for ds_, p_ in dd.values():
            ii = np.array([pos_[d] for d in ds_], int)
            s_[ii] += p_
            c_[ii] += 1
        return s_[c_ > 0] / c_[c_ > 0] if allp else np.zeros(0)

    out = {}
    rows2 = []
    for r_ in readings:
        tr = pooled[r_]
        pn = np.array([t["pnl"] for t in tr], float)
        cl = {}
        for t in tr:
            key = (t["pair"], t["entry"][:7])
            s0, c0 = cl.get(key, (0.0, 0))
            cl[key] = (s0 + t["pnl"], c0 + 1)
        num = np.array([v_[0] for v_ in cl.values()], float)
        den = np.array([v_[1] for v_ in cl.values()], float)
        tb = _mc(lambda seed: cluster_ratio(num, den, seed=seed), lambda t: lb_check(t, 0.0)[0]) if num.size >= 8 else \
            {"est": float(pn.mean()) if pn.size else None, "ci": [None, None], "ci1": [None, None]}
        npos = sum(1 for v_ in per_pair.values() if v_ is not None and v_[r_]["positive"])
        n_av = sum(1 for v_ in per_pair.values() if v_ is not None)
        n_miss = len(pairs) - n_av
        ok = True if npos >= 6 else (False if npos + n_miss < 6 else None)
        rows2.append((f"{r_}: {npos} of {n_av} archived pairs positive" + (f" ({n_miss} not archived)" if n_miss else ""), ok, False))
        halves = {}
        for lab, sel_ in (("first half", lambda d: d < T470_HALF), ("second half", lambda d: d >= T470_HALF)):
            p_ = [t["pnl"] for t in tr if sel_(t["entry"])]
            halves[lab] = {"n": len(p_), "mean": float(np.mean(p_)) if p_ else None}
        out[r_] = {"n": int(pn.size), "mean": float(pn.mean()) if pn.size else None, "boot": tb, "n_pos": npos, "halves": halves,
                   "n_clusters": int(num.size)}
    c2 = all_constructions(rows2, "positive mean net return per trade in >= 6 of 10 pairs (both cost readings)")
    claim = out["claim: 5 bps per leg"]
    thin = out["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]
    prim_daily = pool_daily(daily["claim: 5 bps per leg"])
    fam = {"all pairs pooled (primary)": prim_daily}
    g = daily["claim: 5 bps per leg"].get("GOOGL/GOOG")
    if g is not None:
        fam["GOOGL/GOOG only"] = g[1]
    for vn, dd in var_daily.items():
        fam[vn] = pool_daily(dd)
    ds = dsr_family(prim_daily, [_sr_pp(x) for x in fam.values()], T470_N_TRIALS) if prim_daily.size > 3 else {"dsr": None}
    miss_txt = ", ".join(missing) if missing else ""
    c1 = (f"pooled 95% lower bound of the mean net return per trade > 0 across the 10 declared pairs (NOT IMPLEMENTED: "
          f"{miss_txt or 'none'} not archived; on the {len(pairs) - len(missing)} archived pairs: claim costs "
          f"{_bp(claim['mean'], 2)} (two-sided lower {_bp(claim['boot']['ci'][0], 2)}, one-sided lower "
          f"{_bp((claim['boot'].get('ci1') or [None])[0], 2)}; {claim['n']} trades, {claim['n_clusters']} pair-month clusters), "
          f"thin-class costs {_bp(thin['mean'], 2)} (two-sided lower {_bp(thin['boot']['ci'][0], 2)}))",
          None if missing else _pool_ok(claim, thin)[0], False if missing else _pool_ok(claim, thin)[1])
    c3 = (f"DSR > {DSR_PASS} over the {T470_N_TRIALS} variants (NOT IMPLEMENTED: the pooled series needs {miss_txt or 'none'}; on "
          f"the archived pairs DSR {_f(ds.get('dsr'))})", None if missing else (ds.get("dsr") is not None and ds["dsr"] > DSR_PASS),
          False)
    n = claim["n"]
    v, why = _decide([c1, c2, c3], n, min_n, "trades")
    return {"n": n, "per_pair": per_pair, "missing": missing, "pooled": out, "dsr": ds,
            "family": {k_: {"sharpe_pp": _sr_pp(x), "n_days": int(len(x))} for k_, x in fam.items()},
            "criteria": [(c[0], c[1]) for c in (c1, c2, c3)], "verdict": v, "why": why}


def _pool_ok(claim: dict, thin: dict) -> tuple:
    rows = []
    for nm, d in (("claim costs", claim), ("thin-class costs", thin)):
        ok, dec, note = lb_check(d["boot"], 0.0)
        rows.append((nm + note, ok, dec))
    r = all_constructions(rows, "pooled lower bound")
    return r[1], r[2]


# ================================================================================== T-322 secondary, T-323 judge ==

_FRAME_KEYS = ("ix", "Yf", "Xf", "Vf", "Yt", "Xt", "RA", "RB", "DT", "Vt", "DI", "a", "b", "sd", "k")


def frame_subset(fr: dict, m: np.ndarray) -> Optional[dict]:
    if not np.any(m):
        return None
    out = dict(fr)
    for key in _FRAME_KEYS:
        out[key] = fr[key][m]
    return out


def coint_secondary(sc: dict, frames: Sequence[dict], n_days: int) -> dict:
    """T-322's reported (not pass) net trading results: static OLS spread trading of the selected pair-windows under the
    declared thresholds, with the half-life filter on and off; equal-weight daily portfolio Sharpe and DSR over the 4
    computed cells (the Johansen, monthly-beta and copula variants are not run)."""
    cells = {}
    sel_all = sc["rows"]["sel"].astype(bool)
    for rn, rule in T322_RULES.items():
        sims = [static_sim(fr, rule) for fr in frames]
        for hn, use_sel in (("half-life filter on", True), ("half-life filter off", False)):
            parts, opens, tot = [], 0, []
            for fr, sm in zip(frames, sims):
                m = sel_all[fr["ix"]] if use_sel else np.ones(fr["ix"].size, bool)
                parts.append((sm["pnl"][m], fr["Vt"][m], fr["DI"][m]))
                opens += int(sm["n_open"][m].sum())
                tot.append(np.where(fr["Vt"][m], sm["pnl"][m], 0.0).sum(axis=1))
            agg, _ = aggregate(parts, n_days)
            x = agg[np.isfinite(agg)]
            tw = np.concatenate(tot) if tot else np.zeros(0)
            cells[f"{hn}, {rn}"] = {"x": x, "sharpe_ann": _sr_ann(x, 252), "n_pair_windows": int(tw.size), "opens": opens,
                                    "mean_window_pnl": float(tw.mean()) if tw.size else None}
    prim = cells[f"half-life filter on, 2/0.5/4"]
    ds = dsr_family(prim["x"], [_sr_pp(c["x"]) for c in cells.values()], len(cells)) if prim["x"].size > 3 else {"dsr": None}
    return {"cells": {k: {kk: vv for kk, vv in v.items() if kk != "x"} for k, v in cells.items()}, "dsr": ds}


def kalman_study(sc: dict, frames: Sequence[dict], n_days: int, min_n: int = T323_MIN_N, em_iters: int = T323_EM_ITERS) -> dict:
    """T-323 on the selected pair-windows (frames): per-window paired net-Sharpe differences (Kalman minus static, same
    rule), judged in 2008-2016 and 2017-2026 under the window-month block bootstrap and the Ledoit-Wolf test on the
    aggregate daily portfolios (rule 11), and the DSR of the primary Kalman variant over the 4-cell grid."""
    labels = sc["labels"]
    rules = sorted({rule for _, rule in T323_KCELLS.values()})
    K_, SRs, SRk, PN_S, PN_K, V_, DI_, deltas, reb, opk, ops = [], {r: [] for r in rules}, {c: [] for c in T323_KCELLS}, \
        {r: [] for r in rules}, {c: [] for c in T323_KCELLS}, [], [], [], 0, 0, 0
    for fr in frames:
        kf = {"em": kalman_frame(fr, None, em_iters), "fixed": kalman_frame(fr, T323_DELTA_FIXED, em_iters)}
        deltas.append(kf["em"]["delta"])
        for r in rules:
            sm = static_sim(fr, r)
            SRs[r].append(row_sharpe(sm["pnl"], fr["Vt"], fr["ppy"]))
            PN_S[r].append(sm["pnl"])
            if r == T323_KCELLS[T323_PRIMARY][1]:
                ops += int(sm["n_open"].sum())
        for c, (mode, r) in T323_KCELLS.items():
            km = kalman_sim(fr, kf[mode], r)
            SRk[c].append(row_sharpe(km["pnl"], fr["Vt"], fr["ppy"]))
            PN_K[c].append(km["pnl"])
            if c == T323_PRIMARY:
                reb += int(km["n_rebalance"].sum())
                opk += int(km["n_open"].sum())
        K_.append(fr["k"])
        V_.append(fr["Vt"])
        DI_.append(fr["DI"])
    if not frames:
        v, why = _decide([("pair-windows selected", None)], 0, min_n, "pair-windows")
        return {"n": 0, "criteria": [], "verdict": v, "why": why}
    kk = np.concatenate(K_)
    n_rows = int(kk.size)
    n = int(round(n_rows / T322_HOLD))
    dcell = {}
    for c, (mode, r) in T323_KCELLS.items():
        dcell[c] = np.concatenate(SRk[c]) - np.concatenate(SRs[r])
    d = dcell[T323_PRIMARY]
    rp = T323_KCELLS[T323_PRIMARY][1]
    wk = np.array([w["k"] for w in sc["windows"]], int)
    wlab = [w["month"] for w in sc["windows"]]
    halves = {}
    crit = []
    for hn, test in (("2008-2016", lambda lab: lab < T323_SPLIT), ("2017-2026", lambda lab: lab >= T323_SPLIT)):
        wm = np.array([test(l_) for l_ in wlab], bool)
        ks = wk[wm]
        num = np.array([d[kk == k_].sum() for k_ in ks], float)
        den = np.array([(kk == k_).sum() for k_ in ks], float)
        rm = np.array([test(labels[k_]) for k_ in kk], bool)

        def chk(t):
            lo = (t.get("ci") or [None])[0]
            return resolve(lo, (t.get("ci_mc_se") or [0.0])[0], 0.0, "gt")[0]
        tb = _mc(lambda seed: cbb_ratio(num, den, T322_BLOCK, seed=seed), chk) if den.sum() >= 8 else {"est": None, "ci": [None, None]}
        lo, hi = tb.get("ci") or (None, None)
        se = tb.get("ci_mc_se") or [0.0, 0.0]
        okb, nb = resolve(lo, se[0], 0.0, "gt")
        decb = hi is not None and resolve(hi, se[1], 0.0, "lt")[0] is True
        parts_k, parts_s = [], []
        off = 0
        for fr, pk, ps in zip(frames, PN_K[T323_PRIMARY], PN_S[rp]):
            m = rm[off:off + fr["k"].size]
            off += fr["k"].size
            parts_k.append((pk[m], fr["Vt"][m], fr["DI"][m]))
            parts_s.append((ps[m], fr["Vt"][m], fr["DI"][m]))
        ak, ck = aggregate(parts_k, n_days)
        as_, cs = aggregate(parts_s, n_days)
        both = np.isfinite(ak) & np.isfinite(as_)
        xk, xs = ak[both], as_[both]
        if xk.size >= 8:
            tl = _mc(lambda seed: lw_test(xk, xs, 252, T323_LW_BLOCK, N_BOOT, seed), chk, keys=("ci",))
        else:
            tl = {"diff": None, "ci": [None, None]}
        lo2, hi2 = tl.get("ci") or (None, None)
        se2 = tl.get("ci_mc_se") or [0.0, 0.0]
        okl, nl = resolve(lo2, se2[0], 0.0, "gt")
        decl = hi2 is not None and resolve(hi2, se2[1], 0.0, "lt")[0] is True
        okl = okl if tl.get("diff") is not None else None
        crit.append(all_constructions(
            [(f"window-month block bootstrap ({T322_BLOCK}-month blocks, {int(den.sum())} pair-windows): mean "
              f"{_s(tb.get('est'), 3)} {_ci(tb.get('ci'), 3)}{nb}", okb if tb.get("est") is not None else None, decb),
             (f"{'Ledoit-Wolf (2008) test'} on the aggregate daily portfolios ({xk.size} sessions, block {T323_LW_BLOCK}): Sharpe "
              f"{_s(tl.get('diff'), 3)} {_ci(tl.get('ci'), 3)}{nl}", okl, decl)],
            f"{hn}: mean paired net-Sharpe difference (Kalman - static) > 0 with 95% CI excluding 0"))
        halves[hn] = {"n_rows": int(den.sum()), "mean": tb.get("est"), "ci": tb.get("ci"), "ci_mc_se": tb.get("ci_mc_se"),
                      "lw": {k_: tl.get(k_) for k_ in ("diff", "ci", "ci_mc_se", "p", "se")},
                      "sharpe_kalman_agg": _sr_ann(xk, 252), "sharpe_static_agg": _sr_ann(xs, 252)}
    fam = {}
    for c in T323_KCELLS:
        parts = [(pk, fr["Vt"], fr["DI"]) for fr, pk in zip(frames, PN_K[c])]
        a_, _ = aggregate(parts, n_days)
        fam[c] = a_[np.isfinite(a_)]
    xprim = fam[T323_PRIMARY]
    ds = dsr_family(xprim, [_sr_pp(x) for x in fam.values()], T323_N_TRIALS) if xprim.size > 3 else {"dsr": None, "psr0": None,
                                                                                                    "n_trials": T323_N_TRIALS,
                                                                                                    "var_trials_sr": 0.0}
    crit.append(dsr_row(ds, f"DSR of the Kalman variant > {DSR_PASS} at {T323_N_TRIALS} trials (delta EM / 1e-4 x entry 2 / 1 sd)"))
    v, why = _decide(crit, n, min_n, "pair-windows (non-overlapping equivalents: pooled pair-windows / 6)")
    yrs = {}
    for y in ("2020", "2022"):
        m = np.array([labels[k_][:4] == y for k_ in kk], bool)
        yrs[y] = {"n_rows": int(m.sum()), "mean_diff": float(d[m].mean()) if m.any() else None}
    dl = np.concatenate(deltas)
    return {"n": n, "n_pair_windows": n_rows, "mean_diff": float(d.mean()), "halves": halves, "dsr": ds,
            "cells": {c: {"mean_diff": float(x.mean()), "sharpe_kalman_agg": _sr_ann(fam[c], 252)} for c, x in dcell.items()},
            "breaks": yrs, "delta_em_median": float(np.median(dl)), "delta_em_q": [float(np.quantile(dl, .1)), float(np.quantile(dl, .9))],
            "rebalances": reb, "opens_kalman": opk, "opens_static": ops,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


# ===================================================================================================== harnesses ==

def _etf_data(archive) -> dict:
    def load():
        cal = _daily(archive, dh("SPY"))["days"]
        ser = {}
        for s in UNIVERSE:
            d = _daily(archive, dh(s))
            ser[s] = (d["days"], d["adj"])
        P, filled = panel(ser, cal)
        return {"days": cal, "P": P, "filled": filled}
    return _cached(archive, ("etf",), load)


def _crypto_data(archive) -> dict:
    def load():
        e, b = _daily(archive, dh("ETH-USD")), _daily(archive, dh("BTC-USD"))
        cal = sorted(set(e["days"]) & set(b["days"]))
        C, _ = panel({"ETH-USD": (e["days"], e["adj"]), "BTC-USD": (b["days"], b["adj"])}, cal)
        return {"days": cal, "C": C}
    return _cached(archive, ("crypto",), load)


def _coint(archive) -> dict:
    def load():
        e, c = _etf_data(archive), _crypto_data(archive)
        return coint_scan(e["days"], e["P"], c["days"], c["C"])
    return _cached(archive, ("coint",), load)


def _frames(archive, which: str) -> list:
    def load():
        sc = _coint(archive)
        r = sc["rows"]
        mask = np.ones(r["k"].size, bool) if which == "eg" else r["sel"].astype(bool)
        e, c = _etf_data(archive), _crypto_data(archive)
        out = []
        for cal, days, P in (("etf", e["days"], e["P"]), ("crypto", c["days"], c["C"])):
            fr = pw_frame(sc, mask, cal, days, P, e["days"])
            if fr is not None:
                out.append(fr)
        return out
    return _cached(archive, ("frames", which), load)


def b6c_pairs_distance(archive):
    """T-321."""
    need = [dh(s) for s in UNIVERSE]
    miss = _missing(archive, need)
    if miss:
        return miss
    e = _etf_data(archive)
    res = ggr_run(e["days"], e["P"], UNIVERSE, [ASSET_CLASS[s] for s in UNIVERSE])
    j = ggr_judge(res)
    t6, t12 = j["stud"][6], j["stud"][12]
    ph = [p["mean"] for p in res["phases"].values() if p["mean"] is not None]
    reason = (f"GGR distance rule on the declared 51 ETFs ({res['universe'][0]}..{res['universe'][1]} eligible per formation; "
              f"{res['n_portfolios']} portfolios, one starting each month, 12-month formation on total-return indices, 20 "
              f"smallest-SSD pairs, open beyond 2 formation sds of the spread rebased at the formation-end close, one-day wait "
              f"on every signal, close at the crossing or the period end; 15 bps per leg per trade, 50 bps/yr borrow; six "
              f"overlapping portfolios, return on committed capital), {res['months'][0]}..{res['months'][-1]} ({j['n']} months, "
              f"{res['count_min']}+ portfolios each). Mean monthly net return {_bp(j['mean'], 2)}, annualised Sharpe "
              f"{_s(j['sharpe_ann'], 2)}; studentized CBB block 6 {_ci(t6.get('ci'), 2, 1e4, ' bp')}, block 12 "
              f"{_ci(t12.get('ci'), 2, 1e4, ' bp')}. Random-pair control: mean {_bp(j['random_mean'], 2)}, 95th percentile "
              f"{_bp(j['q95_random'], 2)}. DSR {_f(j['dsr'].get('dsr'))} at {T321_N_TRIALS} trials (family: "
              + ", ".join(f"{k} {_bp(v['mean'], 1)}" for k, v in j["family"].items())
              + f"); CSCV PBO {_f((j['pbo'] or {}).get('pbo'))} (16 partitions, {len(j['family'])} cells). Regimes: "
              + ", ".join(f"{k} {_bp(v['mean'], 1)} (Sharpe {_s(v['sharpe_ann'], 2)})" for k, v in j["regimes"].items())
              + f". Per-phase range (each of the six non-overlapping start phases alone; reported): {_bp(min(ph), 1)} to "
              f"{_bp(max(ph), 1)}. Pairs traded: {_f(res['opens_per_pair'], 2)} openings per nominated pair, "
              f"{_pu(res['share_pairs_traded'])} of pairs opened at least once. Most selected (near-twins dominate the SSD "
              f"ranking; not same-index twins, so the declaration keeps them): "
              + ", ".join(f"{k} {v}" for k, v in res["top_pairs"][:6]) + " — " + j["why"])
    stat = {"n_months": j["n"], "window": [res["months"][0], res["months"][-1]], "mean_monthly_net": j["mean"],
            "sharpe_ann": j["sharpe_ann"], "stud_block6": t6, "stud_block12": t12, "random_mean": j["random_mean"],
            "random_q95": j["q95_random"], "dsr": j["dsr"], "pbo": j["pbo"], "family": j["family"], "regimes": j["regimes"],
            "per_phase": {str(k): v for k, v in res["phases"].items()}, "top_pairs": res["top_pairs"],
            "opens_per_pair": res["opens_per_pair"], "share_pairs_traded": res["share_pairs_traded"],
            "n_portfolios": res["n_portfolios"], "universe_size": res["universe"], "carried_bars": e["filled"],
            "criteria": j["criteria"],
            "rule10": "calendar named by the claim: one portfolio started each month, six overlapping (blocks 6 and 12)"}
    return _out(stat, j["n"], j["verdict"], reason)


def b6c_pairs_cointegration(archive):
    """T-322."""
    need = [dh(s) for s in UNIVERSE] + [dh(s) for s in CRYPTO]
    miss = _missing(archive, need)
    if miss:
        return miss
    sc = _coint(archive)
    j = persistence_judge(sc)
    e = _etf_data(archive)
    sec = _cached(archive, ("coint_secondary",), lambda: coint_secondary(sc, _frames(archive, "eg"), len(e["days"])))
    t = j["boot"]
    ph = [p["share"] for p in j["phases"].values() if p["share"] is not None]
    pc = sec["cells"]["half-life filter on, 2/0.5/4"]
    reason = (f"Engle-Granger on the declared 51 ETFs plus ETH/BTC, windows starting every month "
              f"{sc['windows'][0]['month']}..{sc['windows'][-1]['month']} ({j['n_windows']} windows; 12-month formation on "
              f"log prices, ADF on the OLS residual with AIC lags, MacKinnon (2010) 5% critical value for 2 variables, AR(1) "
              f"half-life 2-30 days): {j['n_pair_windows']} selected pair-windows ({j['crypto_selected']} ETH/BTC; {j['n']} "
              f"non-overlapping equivalents). Persistence (6-month out-of-sample spread with frozen beta and alpha rejects a "
              f"unit root at 10%: ADF with constant, AIC lags, MacKinnon (2010) 1-variable value): share {_pu(j['share'])} "
              f"(two-sided 95% {_pu(t['ci'][0] if t.get('ci') else None)} to {_pu(t['ci'][1] if t.get('ci') else None)}, "
              f"one-sided lower {_pu((t.get('ci1') or [None])[0])}); random-pair share {_pu(j['random_share'])} (95th pct "
              f"{_pu(j['random_q95'])}), all candidates {_pu(j['candidate_share'])}; selected minus random "
              f"{_pu((j['diff_vs_random'] or {}).get('est'))} {_ci((j['diff_vs_random'] or {}).get('ci'), 3)}. Per-phase "
              f"range (the six semiannual grids; reported): {_pu(min(ph))} to {_pu(max(ph))}. Regimes: "
              + ", ".join(f"{k} {_pu(v['share'])} of {v['n_sel']}" for k, v in j["regimes"].items())
              + f". Sensitivities: without the half-life filter {_pu(j['share_no_hl_filter'])} of {j['n_eg']}; with the "
              f"2-variable critical value out of sample {_pu(j['share_n2_crit'])}. Secondary (not a pass condition): static "
              f"spread trading |z| > 2 / < 0.5 / stop 4, 15 bps (40 bps crypto) per leg, equal-weight daily portfolio Sharpe "
              f"{_s(pc['sharpe_ann'], 2)} ({pc['opens']} openings), DSR {_f(sec['dsr'].get('dsr'))} over the 4 computed cells "
              f"(" + ", ".join(f"{k} {_s(v['sharpe_ann'], 2)}" for k, v in sec["cells"].items()) + ") — " + j["why"])
    stat = {"n": j["n"], "n_pair_windows": j["n_pair_windows"], "n_windows": j["n_windows"], "share": j["share"],
            "boot": {k: t.get(k) for k in ("est", "ci", "ci1", "ci_mc_se", "ci1_mc_se", "reps", "block")},
            "random_share": j["random_share"], "random_q95": j["random_q95"],
            "diff_vs_random": {k: (j["diff_vs_random"] or {}).get(k) for k in ("est", "ci", "ci1")},
            "candidate_share": j["candidate_share"], "per_phase": {str(k): v for k, v in j["phases"].items()},
            "regimes": j["regimes"], "share_no_hl_filter": j["share_no_hl_filter"], "share_n2_crit": j["share_n2_crit"],
            "crypto_selected": j["crypto_selected"], "secondary": sec, "criteria": j["criteria"],
            "rule10": "windows start every month: the pooled all-start estimate of the semiannual grid (12-month blocks), "
                      "per-phase range reported"}
    return _out(stat, j["n"], j["verdict"], reason)


def b6c_pairs_kalman(archive):
    """T-323."""
    need = [dh(s) for s in UNIVERSE] + [dh(s) for s in CRYPTO]
    miss = _missing(archive, need)
    if miss:
        return miss
    sc = _coint(archive)
    e = _etf_data(archive)
    frames = _frames(archive, "sel")
    j = kalman_study(sc, frames, len(e["days"]))
    if not j.get("halves"):
        return _out({"n": 0, "criteria": j["criteria"]}, 0, j["verdict"], "no selected pair-windows — " + j["why"])
    h1, h2 = j["halves"]["2008-2016"], j["halves"]["2017-2026"]
    reason = (f"Kalman (random-walk alpha/beta, delta and R by EM on each formation window, filter run forward) versus the "
              f"static OLS hedge on T-322's {j['n_pair_windows']} selected pair-windows ({j['n']} non-overlapping "
              f"equivalents), same rule on each standardized spread (|z| > 2 open, < 0.5 close, stop 4; Kalman z = "
              f"innovation / sqrt(predicted variance); hedge rebalanced when beta moves > 5%, {j['rebalances']} rebalances), "
              f"15 bps (40 bps crypto) per leg per trade, decisions at close t filled at t+1. Paired net-Sharpe difference "
              f"(annualised, per pair-window; Kalman minus static): all {_s(j['mean_diff'], 3)}; 2008-2016 "
              f"{_s(h1['mean'], 3)} {_ci(h1['ci'], 3)} (LW aggregate {_s(h1['lw']['diff'], 3)} {_ci(h1['lw']['ci'], 3)}); "
              f"2017-2026 {_s(h2['mean'], 3)} {_ci(h2['ci'], 3)} (LW aggregate {_s(h2['lw']['diff'], 3)} "
              f"{_ci(h2['lw']['ci'], 3)}). DSR of the Kalman variant {_f(j['dsr'].get('dsr'))} at {T323_N_TRIALS} trials "
              f"(cells: " + ", ".join(f"{k} diff {_s(v['mean_diff'], 3)}, aggregate Sharpe {_s(v['sharpe_kalman_agg'], 2)}"
                                     for k, v in j["cells"].items())
              + f"). EM delta median {j['delta_em_median']:.2e} (10-90% {j['delta_em_q'][0]:.2e}..{j['delta_em_q'][1]:.2e}); "
              f"openings Kalman {j['opens_kalman']}, static {j['opens_static']}. Breaks: "
              + ", ".join(f"{k} {_s(v['mean_diff'], 3)} ({v['n_rows']})" for k, v in j["breaks"].items()) + " — " + j["why"])
    stat = {k: j[k] for k in ("n", "n_pair_windows", "mean_diff", "halves", "dsr", "cells", "breaks", "delta_em_median",
                              "delta_em_q", "rebalances", "opens_kalman", "opens_static", "criteria")}
    stat["rule10"] = "T-322's monthly-start windows (pooled all-start, 12-month blocks over window months)"
    return _out(stat, j["n"], j["verdict"], reason)


def b6c_pairs_brent_wti(archive):
    """T-468."""
    need = [dh("BZ=F"), dh("CL=F"), dh("USO"), dh("BNO")]
    miss = _missing(archive, need)
    if miss:
        return miss
    bz, cl, us, bn = (_daily(archive, dh(s)) for s in ("BZ=F", "CL=F", "USO", "BNO"))
    uga = None
    if _has(archive, dh("UGA")):
        ug = _daily(archive, dh("UGA"))
        uga = (ug["days"], ug["adj"])
    j = brent_wti({"BZ": (bz["days"], bz["close"]), "CL": (cl["days"], cl["close"])},
                  {"USO": (us["days"], us["adj"]), "BNO": (bn["days"], bn["adj"])}, uga)
    tb = j["boot"]
    reason = (f"s = ln(BZ=F) - ln(CL=F) front-month closes; z on the trailing {T468_L} sessions over unmasked values (roll "
              f"windows +-{T468_ROLL_WIN} sessions around each scheduled CL and BZ last trading day, and April 2020, masked: "
              f"{_pu(j['mask_share'])} of sessions masked, {j['n_signal_sessions']} signal sessions); z > 2 long USO / short "
              f"BNO, z < -2 the reverse, equal dollars at the next close; exit at z = 0 or after {T468_MAX_HOLD} sessions; "
              f"5 bps per leg per trade, 50 bps/yr borrow; window {j['window'][0]}..{j['window'][1]}. {j['n']} trades "
              f"({', '.join(f'{k} {v}' for k, v in j['reasons'].items())}), mean net per trade {_bp(j['mean'], 1)} "
              f"({_ci(tb.get('ci'), 1, 1e4, ' bp')}); block-shifted null mean {_bp(j['null_mean'], 1)}, p {_f(j['p_null'])}. "
              f"Sub-periods: " + ", ".join(f"{k} {_bp(v['mean'], 1)} ({v['n']})" for k, v in j["subs"].items())
              + f". Reported: DSR {_f(j['dsr'].get('dsr'))} over {T468_N_TRIALS} variants (dollar spread: "
              f"{j['usd_variant']['n']} trades, {_bp(j['usd_variant']['mean'], 1)}; UGA/USO: "
              f"{(j['uga_variant'] or {}).get('n')} trades, {_bp((j['uga_variant'] or {}).get('mean'), 1)}); trailing statistics "
              f"over every session instead: {j['sens_stats_all_sessions']['n']} trades, "
              f"{_bp(j['sens_stats_all_sessions']['mean'], 1)}; AR(1) half-life of s by sub-period "
              + ", ".join(f"{k} {v:.0f}" for k, v in j["half_life"].items())
              + f" sessions; z(futures) vs z(ln BNO/USO) correlation {_f(j['corr_z_futures_vs_etf'], 2)}. USO's 2020 roll-"
              f"schedule change is a flagged structural break inside 2020-2026 — " + j["why"])
    stat = {k: j[k] for k in ("n", "mean", "p_null", "null_mean", "subs", "dsr", "family", "usd_variant", "uga_variant",
                              "sens_stats_all_sessions", "half_life", "corr_z_futures_vs_etf", "mask_share",
                              "n_signal_sessions", "window", "reasons", "criteria")}
    stat["boot"] = {k: tb.get(k) for k in ("est", "ci", "ci1", "ci_mc_se", "ci1_mc_se", "reps")}
    stat["trades"] = j["trades"]
    stat["rule10"] = "daily state machine on trailing statistics (no grid phase)"
    return _out(stat, j["n"], j["verdict"], reason)


def b6c_pairs_dual_class(archive):
    """T-470."""
    opt = ("LBRDK", "LBRDA")                    # probed only: LBRDK is not archived (Yahoo's history starts 2026-07-17)
    need = [dh(t) for p in T470_PAIRS for t in p[:2] if t not in opt]
    miss = _missing(archive, need)
    if miss:
        return miss
    use = [t for p in T470_PAIRS if all(_has(archive, dh(x)) for x in p[:2]) for t in p[:2]]
    data = {t: _daily(archive, dh(t)) for t in use}
    j = dual_class(data)
    pc = j["pooled"]
    cl, th = pc["claim: 5 bps per leg"], pc["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]
    pp = []
    for nm, v in j["per_pair"].items():
        if v is None:
            pp.append(f"{nm} not archived")
        else:
            a, b = v["claim: 5 bps per leg"], v["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]
            pp.append(f"{nm} {a['n']} trades {_bp(a['mean'], 1)}" + (f" / {_bp(b['mean'], 1)}" if b["mean"] != a["mean"] else ""))
    reason = (f"Ten declared dual-class pairs, x = ln(A) - ln(k B) on adjusted closes from each pair's first separate-line "
              f"session, z on the trailing {T470_L} sessions; |z| > 2: long the cheap class / short the rich class in equal "
              f"dollars at the next close; exit at z = 0 or after {T470_MAX_HOLD} sessions; 50 bps/yr borrow; entries "
              f"{T470_START}..data end. LBRDK is not archived (Yahoo's history starts 2026-07-17), so the LBRDK/LBRDA pair is "
              f"None. Pooled over the {10 - len(j['missing'])} archived pairs: {cl['n']} trades, mean "
              f"{_bp(cl['mean'], 2)} (5 bps/leg, {_ci(cl['boot'].get('ci'), 2, 1e4, ' bp')}, clustered by pair-month) and "
              f"{_bp(th['mean'], 2)} with 25 bps on the thin classes ({_ci(th['boot'].get('ci'), 2, 1e4, ' bp')}); halves "
              + ", ".join(f"{k} {_bp(v['mean'], 1)} ({v['n']})" for k, v in cl["halves"].items())
              + ". Per pair (5 bps / thin-class costs): " + "; ".join(pp)
              + f". DSR over the 5 variants on the archived pairs {_f(j['dsr'].get('dsr'))} (family Sharpe per session: "
              + ", ".join(f"{k} {_s(v['sharpe_pp'], 4)}" for k, v in j["family"].items()) + ") — " + j["why"])
    stat = {"n_trades": j["n"], "per_pair": j["per_pair"], "missing_pairs": j["missing"],
            "pooled": {k: {kk: (vv if kk != "boot" else {x: vv.get(x) for x in ("est", "ci", "ci1", "ci_mc_se", "ci1_mc_se")})
                           for kk, vv in v.items()} for k, v in pc.items()},
            "dsr_archived_pairs": j["dsr"], "family": j["family"], "criteria": j["criteria"],
            "not_archived": "daily-history-LBRDK (Yahoo history starts 2026-07-17; the LBRDK/LBRDA pair cannot be built)",
            "rule10": "daily state machine on trailing statistics (no grid phase)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_pairs_distance": b6c_pairs_distance,
    "b6c_pairs_cointegration": b6c_pairs_cointegration,
    "b6c_pairs_kalman": b6c_pairs_kalman,
    "b6c_pairs_brent_wti": b6c_pairs_brent_wti,
    "b6c_pairs_dual_class": b6c_pairs_dual_class,
}

THEORY_MAP = {
    "T-321": "b6c_pairs_distance",
    "T-322": "b6c_pairs_cointegration",
    "T-323": "b6c_pairs_kalman",
    "T-468": "b6c_pairs_brent_wti",
    "T-470": "b6c_pairs_dual_class",
}
