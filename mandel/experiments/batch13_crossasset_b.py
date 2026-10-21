"""
Batch 13, group ``crossasset_b``: four cross-asset claims pre-registered from the 2026-10-20 web sweep (cluster
"crossasset"): industry returns leading the market (T-597), SPY leading HYG on 60-minute bars (T-601), credit-market
changes predicting the equity premium (T-602) and the VIX-conditioned daily reversal in S&P 500 stocks (T-604).
=====================================================================================================================

  * T-597  French FF49 value-weighted daily returns compounded to calendar months; groups financial (EW of Banks, Insur,
           Fin), retail (Rtail), print (Books), real estate (RlEst), petroleum (Oil), metals (EW of Steel, Mines) and the
           expanding-window first principal component of the six (7 trials). Target Mkt-RF(t+1) compounded from
           french-ff5-daily. Expanding OLS from 1963-07; forecasts for target months 2003-01..2026-08 against the
           expanding historical mean. Pass: some trial with R2_OS > 0, Holm (7) Clark-West p < 0.05, R2_OS > 0 in
           2003-2014 and 2015-2026-08, R2_OS above the 95th percentile of the industry placebo, a long-SPY-or-bills
           switching rule (first session close of t+1, 2 bp per switch) whose Sharpe beats the historical-mean rule's
           (paired studentized block bootstrap, 12-month blocks, lower 95% bound > 0) and joint-family DSR > 0.95.
           min_n 240 forecasts.
  * T-601  Yahoo 60-minute bars (mandel/ml_data/bars/60m), 2025-10-01..2026-09-30: when |SPY's last completed bar
           return| exceeds the s.d. of SPY's bar returns over the trailing 20 sessions, hold HYG in its direction from
           the next bar's open to that bar's close; 2 bp per side. Pass: net mean per trade > 0 with one-sided p < 0.05
           (studentized circular bootstrap of the session series, 5-session blocks, >= 10,000 draws), both halves
           (2025-10..2026-03, 2026-04..2026-09) positive, positive on 2025-10..2026-07, above the 95th percentile of a
           random 30-stock basket leader placebo (1,000 draws), DSR > 0.95 with the 14 T-577/T-578 bond_etf F0F1 cells.
           min_n 300 trades.
  * T-602  Three pre-signed credit predictors of SPY's fill-to-fill excess return (first session close of t+1 to the
           first close of t+2, minus DTB3): month-t change in the BAA10Y month-end print (negative; target months
           2010-01..2026-09, training from 1993-02), duration-hedged LQD and HYG excess returns r_ETF(t) - beta_t
           r_IEF(t) with beta_t from the trailing 36 monthly returns known at t (positive; forecasts once 60 training
           pairs exist). Pass: some trial with R2_OS > 0, Holm (3) Clark-West p < 0.05, the pre-registered sign, R2_OS
           > 0 in both halves of its own window, a switching rule beating the historical-mean rule (paired lower bound
           > 0), joint-family DSR > 0.95. min_n 120 forecasts.
  * T-604  Point-in-time S&P 500 members (fja05680, later Wikipedia changes; T-473's usable-series filters) priced at
           >= $5 at close t-1: weights -(r_i - mean r) over a 1- or 5-session formation ending at close t-1, $1 long /
           $1 short, from the day-t open to the day-t close, 3 bp per side on gross turnover. Pass (2013-01..2026-09):
           HAC (lag 10) t of the slope of the daily net return on VIX(t-1) > 1.65, top trailing-252-session VIX tercile
           net mean > 0 with one-sided p < 0.05 (studentized circular block bootstrap, 20 days), both halves (2013-2019,
           2020-2026) positive, DSR > 0.95 with T-462's cells counted. Formation chosen on 2000-2012 net Sharpe.
           min_n 2,500 days.

Readings fixed before any run (the registrations are silent or ambiguous; each is the conservative one and is listed
in the reason):
  * Point in time. A daily bar is known at its close. FF49 / FF5 months are used at the month's last close, as the
    registration states (the series are 2026 vintages, revised over time: the Tse revision caveat is stated in the
    verdict). The T-597 expanding fit at the end of month t uses the pairs (x_j, Mkt-RF(j+1)) with j + 1 <= t; the
    PC1 loadings are estimated on months 1963-07..t only. T-602 pairs are realised at the first close of j + 2, so the
    fit at the end of month t uses predictor months j <= t - 2 (as the sibling ``crossasset_a`` predictor engine).
    BAA10Y (available 20:00 UTC on its day) enters as the month's last print, traded at the next session's close.
    DTB3 is the print dated strictly before the fill day (``batch6c_cal.Bills``). VIX closes (16:15 ET, archived 21:30
    UTC) enter at t-1 for a day-t open entry. The 60-minute bars are stamped at their open and known at their close;
    the 13:00 / 16:00 zero-length closing stubs are dropped and nothing on or after the 2026-10-01 lockbox is loaded.
  * T-597: groups are equal-weight means of their components' MONTHLY compounded returns; PC1 = covariance PCA of the
    six group returns on months 1963-07..t, loadings signed to a positive sum. "Forecast exceeds DTB3/12" is literal
    in the rule while the forecast is of an EXCESS return, so the switching criterion and the DSR are judged under
    both thresholds (DTB3/12 and 0; rule 11: pass only when both pass). The placebo "43 industries" cannot be formed:
    the six groups use nine industries, leaving 40; the placebo criterion is judged against both the 40 untouched
    industries and those 40 plus the five group components (Banks, Insur, Fin, Steel, Mines) taken singly (45), and
    passes only when both 95th percentiles are beaten. Clark-West p = the Newey-West (lag 12) one-sided normal p,
    Holm over the 7 trials. Sign-restricted forecasts are reported only.
  * T-602: training for the ETF trials starts at the first hedged month; the first forecast is the first origin with
    60 realised training pairs (LQD target months from 2010-09, HYG from 2015-06, against the registration's 'about
    2010-08' and 'about 2015-05'). The procedure names a studentized circular block bootstrap (12-month blocks) without
    saying for which statistic, so the Clark-West criterion is judged under both the Newey-West (lag 12) normal p and
    the bootstrap p of the CW series, each Holm-adjusted over the 3 trials (rule 11). "The pre-registered sign" =
    the OLS slope's point estimate on the evaluation window's pairs AND on every pair from the training start. Halves =
    the first and second halves of the trial's own forecasts. The switching rule is long SPY when the excess-return
    forecast is positive. EBP-change and bond-skewness trials are blocked (no first-release EBP vintages, no TRACE).
  * T-601: "bar return" is read two ways (rule 11, every criterion judged under both): the bar's own open-to-close
    return, and the close-to-close return (from the previous retained bar's close, so the 09:30 bar includes the
    overnight gap; the house ML convention). The threshold is the s.d. (ddof 1) of all the leader's bar returns in
    the 20 complete sessions before the signal bar's session. A signal needs the next bar 60 minutes later in the
    same session, so a session's last bar (the 15:30 half bar, or the last bar of an early close) never signals and
    nothing is held overnight. Every trade pays 2 bp at entry and 2 bp at exit (no netting of consecutive trades).
    The bootstrap series is the per-session sum of trade net returns over every window session (zero when no trade):
    its mean is positive exactly when the net mean per trade is. Placebo: the 60-minute store holds only 28 single
    stocks, so 30 distinct names cannot be drawn; the criterion is judged against both (a) 30 names drawn without
    replacement from the 28 plus the archive's 10 US-listed hourly stocks (BMO BNS CNI CNQ CP ENB RY SHOP SU TD; GOOG
    and the .TO lines excluded as duplicate issuers) and (b) 30 draws with replacement from the 28, the basket being
    the equal-weight mean of its members' bar returns (each draw with its own trailing-20-session threshold).
  * T-604: membership is the set effective at close t-1; T-473's usable-series filters (a Yahoo series exists, meta
    EQUITY, a removed member's Wikipedia removal name must match a name the instrument carried); T-473's sector
    assignment is a hedge choice, not a series filter, and is not applied. Raw price = split-adjusted close x the
    later split ratios. A name with no day-t open or close earns 0 and pays no cost (unfilled); costs = 3 bp x 2 sides
    x the filled gross (about 12 bp a day). The formation is selected under two readings of "2000-2012 net Sharpe"
    (every day, and top-tercile days); when they disagree both formations are judged (rule 11). "Both halves
    positive" = the VIX slope AND the top-tercile net mean positive in each half. The DSR is computed on the
    top-tercile days' net returns.
  * DSR when the family's other Sharpes are not computed here (every claim in this group): the DSR at the most
    favourable trial-Sharpe variance (the 1/(T-1) floor) and the smallest trial count the registration admits fails
    the criterion when it misses 0.95 (decisive when PSR vs 0 <= 0.05) and leaves it undecided otherwise, so it can
    refute but not support (``crossasset_a.dsr_bound``). Counts: T-597 at least 7 + 4 named predictors + 12 + 12 = 35
    (full 39); T-602 at least 3 + T-430 + T-481 + 4 cluster predictors = 9 (full 31); T-601 14 + 1 = 15; T-604 2 + 18
    T-462 cells = 20.
  * Survivorship: T-604 draws prices from the archive's 901-symbol daily-history set, TODAY's universe: removed,
    acquired and renamed members are under-represented (the share of member-days without a usable price is
    reported).
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``, house rule 5). House rule 10: every claim here names its own calendar (months, bars,
    sessions), so there is no free grid phase.
"""

from __future__ import annotations

import bisect
import math
import warnings
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_rates import hac_mean
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
NY = ZoneInfo("America/New_York")

SPY_B = "daily-history-SPY"
DTB3_B = "fred-DTB3"
FF5_B = "french-ff5-daily"
IND49_B = "french-industry49-daily"
BAA_B = "fred-BAA10Y"
HYG_B = "daily-history-HYG"
LQD_B = "daily-history-LQD"
IEF_B = "daily-history-IEF"
VIX_B = "cboe-VIX-history"
FJA_B = "fja-sp500-components"

CW_LAG = 12                     # Newey-West lag of the monthly Clark-West series
BLOCK_M = 12                    # monthly bootstrap blocks
SWITCH_COST = 2e-4              # per switch of the long-SPY-or-bills rules


# ================================================================================================= utilities ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, list(names))


def _b(x) -> Optional[bool]:
    return None if x is None else bool(x)


def _fin(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _f(x, nd: int = 3) -> str:
    return f"{float(x):.{nd}f}" if _fin(x) else "n/a"


def _s(x, nd: int = 3) -> str:
    return f"{float(x):+.{nd}f}" if _fin(x) else "n/a"


def _pc(x, nd: int = 2) -> str:
    return f"{float(x) * 100:+.{nd}f}%" if _fin(x) else "n/a"


def _bp(x, nd: int = 2) -> str:
    return f"{float(x) * 1e4:+.{nd}f} bp" if _fin(x) else "n/a"


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > -99.0 else None          # French codes a missing return as -99.99


def _mi(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def madd(m: str, k: int) -> str:
    return _ms(_mi(m) + k)


def mrange(a: str, b: str) -> list:
    return [_ms(i) for i in range(_mi(a), _mi(b) + 1)]


def month_complete(last_day: str) -> bool:
    """Is the month of a series' last observation ``last_day`` complete (last_day at or after its last NYSE session)?"""
    d = date.fromisoformat(last_day)
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return d >= CAL.prev_session(nxt)


def ols_nw_all(y, X, lag: int) -> dict:
    """OLS y = a + X b with Newey-West (Bartlett 1 - l/(L+1)) standard errors for every coefficient (intercept first)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(y.size, -1)
    n, k = X.shape
    Z = np.column_stack([np.ones(n), X])
    out = {"n": int(n), "coef": None, "se": None, "t": None, "lag": int(lag)}
    if n < k + 4:
        return out
    try:
        ZtZi = np.linalg.inv(Z.T @ Z)
    except np.linalg.LinAlgError:
        return out
    b = ZtZi @ Z.T @ y
    e = y - Z @ b
    u = Z * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    V = ZtZi @ S @ ZtZi
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    t = np.where(se > 0, b / np.where(se > 0, se, 1.0), np.nan)
    out.update(coef=[float(v) for v in b], se=[float(v) for v in se], t=[float(v) for v in t])
    return out


def _okt(ok: Optional[bool]) -> str:
    return "pass" if ok is True else "FAIL" if ok is False else "undecided"


def and_rows(rows: Sequence[tuple], label: str) -> tuple:
    """A conjunction of criterion rows (name, ok, decisive): fails when any row fails (decisively when a failing row is
    decisive), passes when every row passes, undecided otherwise."""
    oks = [_b(r[1]) for r in rows]
    ok = False if any(o is False for o in oks) else True if all(o is True for o in oks) else None
    dec = bool(ok is False and any(_b(r[1]) is False and r[2] for r in rows))
    return f"{label}: " + "; ".join(f"{r[0]} [{_okt(_b(r[1]))}]" for r in rows), ok, dec


def any_rows(rows: Sequence[tuple], label: str) -> tuple:
    """'At least one trial passes': passes when any conjunction passes, fails only when every one fails (decisively
    only when every failure is decisive), undecided otherwise."""
    oks = [_b(r[1]) for r in rows]
    ok = True if any(o is True for o in oks) else False if all(o is False for o in oks) else None
    dec = bool(ok is False and all(r[2] for r in rows))
    return f"{label}: " + " || ".join(f"({r[0]}) [{_okt(_b(r[1]))}]" for r in rows), ok, dec


def per_reading(rowsets: Sequence[list], names: Sequence[str]) -> list:
    """Rule 11 across readings: criterion j passes only when it passes in every reading (``BW.all_constructions``)."""
    out = []
    for j in range(len(rowsets[0])):
        rows = [(f"[{nm}] {rs[j][0]}", _b(rs[j][1]), rs[j][2]) for nm, rs in zip(names, rowsets)]
        out.append(BW.all_constructions(rows, f"criterion {j + 1}"))
    return out


def dsr_bound(x, n_min: int, n_full: int, label: str) -> tuple:
    """DSR criterion when the family's other Sharpes are not computed here: the most favourable trial-Sharpe variance
    (the 1/(T-1) floor) at the smallest admissible trial count bounds the DSR from above. Fails when that bound misses
    0.95 (decisive when PSR vs 0 <= 0.05); undecided otherwise. Returns (row, info)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_min, var_trials_sr=floor))
    full = float(deflated_sharpe_ratio(x, n_trials=n_full, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_bound": hi, "dsr_full_count_floor": full, "n_min": n_min, "n_full": n_full, "var_floor": floor,
            "psr0": psr0, "sharpe_pp": float(sharpe_ratio(x)), "n": int(x.size)}
    txt = (f"{label} (at most {hi:.3f} at {n_min} trials and the 1/(T-1) floor; {full:.3f} at the full {n_full}; "
           f"PSR vs 0 {psr0:.3f})")
    if hi <= DSR_PASS:
        return (txt + " [fails whatever the uncomputed family Sharpes]", False, bool(psr0 <= 1.0 - DSR_PASS)), info
    return (txt + " [the other family Sharpes are not computed here: cannot pass]", None, False), info


def sharpe_diff(a, b, block: int = BLOCK_M, ppy: int = 12) -> dict:
    """Annualised Sharpe(a) - Sharpe(b), paired studentized circular block bootstrap, Monte-Carlo escalated."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return BW.mc_escalate(lambda seed: BW.sharpe_diff_test(a, b, ppy, block, None, seed),
                          lambda t: BW._ci_crit(t, "gt", 0.0, "")[1], None, SEED)


def switch_row(sd: dict, label: str) -> tuple:
    return BW._ci_crit(sd, "gt", 0.0, f"{label}: switching-rule Sharpe {_f(sd.get('sharpe_a'))} minus the historical-mean "
                                      f"rule's {_f(sd.get('sharpe_b'))} = {_s(sd.get('diff'))}, paired lower 95% bound > 0")


# ================================================================================= expanding predictor engine ==

def expanding_oos(x, y, k0: int, k1: int, train0: int = 0, gap: int = 1, min_train: int = 24) -> dict:
    """Expanding one-regressor OLS forecasts of y_k from x_k for k in [k0, k1] (monthly positions, y_k the target of
    predictor month k): the fit at origin k uses the pairs j in [train0, k - gap] with finite x and y; the benchmark is
    their mean. Returns positions, realised y, forecasts, benchmarks and the fitted slope at each origin."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ks, ys, fm, fb, sl = [], [], [], [], []
    for k in range(k0, k1 + 1):
        if not (np.isfinite(x[k]) and np.isfinite(y[k])):
            continue
        j = np.arange(train0, max(train0, k - gap + 1))
        j = j[np.isfinite(x[j]) & np.isfinite(y[j])]
        if j.size < min_train:
            continue
        xs, yv = x[j], y[j]
        xm = xs.mean()
        vx = float(((xs - xm) ** 2).sum())
        b = float(((xs - xm) * (yv - yv.mean())).sum() / vx) if vx > 0 else 0.0
        a = float(yv.mean() - b * xm)
        ks.append(k); ys.append(float(y[k])); fm.append(a + b * x[k]); fb.append(float(yv.mean())); sl.append(b)
    return {"k": np.array(ks, int), "y": np.array(ys), "fm": np.array(fm), "fb": np.array(fb), "slope": np.array(sl)}


def pc1_oos(G, y, k0: int, k1: int, gap: int = 1, min_train: int = 24) -> dict:
    """``expanding_oos`` on the expanding-window first principal component of the columns of G: at origin k the
    covariance PCA uses the months <= k with every column finite (loadings signed to a positive sum), the scores of
    those months are the regressor and the forecast uses month k's score."""
    G = np.asarray(G, float)
    y = np.asarray(y, float)
    rowok = np.isfinite(G).all(axis=1)
    ks, ys, fm, fb, sl, ld = [], [], [], [], [], []
    for k in range(k0, k1 + 1):
        if not (rowok[k] and np.isfinite(y[k])):
            continue
        w = np.flatnonzero(rowok[: k + 1])
        if w.size < max(min_train, G.shape[1] + 2):
            continue
        W = G[w]
        mu = W.mean(axis=0)
        _vals, vecs = np.linalg.eigh(np.cov(W - mu, rowvar=False))
        v = vecs[:, -1]
        if v.sum() < 0:
            v = -v
        s = np.full(G.shape[0], np.nan)
        s[w] = (W - mu) @ v
        j = w[w <= k - gap]
        j = j[np.isfinite(y[j])]
        if j.size < min_train:
            continue
        xs, yv = s[j], y[j]
        xm = xs.mean()
        vx = float(((xs - xm) ** 2).sum())
        b = float(((xs - xm) * (yv - yv.mean())).sum() / vx) if vx > 0 else 0.0
        a = float(yv.mean() - b * xm)
        ks.append(k); ys.append(float(y[k])); fm.append(a + b * s[k]); fb.append(float(yv.mean())); sl.append(b)
        ld.append(v.copy())
    return {"k": np.array(ks, int), "y": np.array(ys), "fm": np.array(fm), "fb": np.array(fb), "slope": np.array(sl),
            "loadings": np.array(ld)}


def cw_series(y, fb, fm) -> np.ndarray:
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    return (y - fb) ** 2 - ((y - fm) ** 2 - (fb - fm) ** 2)


def r2_os(y, fb, fm) -> Optional[float]:
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    if y.size == 0:
        return None
    den = float(((y - fb) ** 2).sum())
    return 1.0 - float(((y - fm) ** 2).sum()) / den if den > 0 else None


def switching(y, f, thr=0.0, cost: float = SWITCH_COST) -> np.ndarray:
    """Monthly excess return of long-SPY-or-bills (in SPY when the forecast f exceeds ``thr``), ``cost`` per switch (the
    first entry from bills counts)."""
    pos = (np.asarray(f, float) > np.asarray(thr, float)).astype(float)
    sw = np.abs(np.diff(np.r_[0.0, pos]))
    return pos * np.asarray(y, float) - cost * sw


def spy_targets(spy_days: Sequence[str], spy_adj, bills, months: Sequence[str]) -> dict:
    """{predictor month t: (excess, fill day, exit day)}: SPY adjclose return from the first session close of t+1 to the
    first session close of t+2, minus the bill return at the DTB3 rate known on the fill day."""
    first = {}
    for i, d in enumerate(spy_days):
        first.setdefault(d[:7], i)
    out = {}
    for t in months:
        i0, i1 = first.get(madd(t, 1)), first.get(madd(t, 2))
        if i0 is None or i1 is None:
            continue
        d0, d1 = spy_days[i0], spy_days[i1]
        out[t] = (float(spy_adj[i1] / spy_adj[i0] - 1.0 - bills.growth(d0, d1)), d0, d1)
    return out


def spy_month_returns(days: Sequence[str], adj) -> dict:
    """{month: SPY total return from the previous month's last close to the month's last close}."""
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    ms = sorted(last)
    return {m: float(adj[last[m]] / adj[last[p]] - 1.0) for p, m in zip(ms[:-1], ms[1:]) if madd(p, 1) == m}


def dtb3_before(keys: Sequence[str], vals: Sequence[float], day: str) -> float:
    """The DTB3 print (percent) dated strictly before ``day``."""
    j = bisect.bisect_left(keys, day) - 1
    return float(vals[max(j, 0)])


def _bills(archive):
    return CAL.Bills(CAL._series(archive, DTB3_B))


# ====================================================================================================== T-597 ==

T597_GROUPS = (("financial", ("Banks", "Insur", "Fin"), 1.0), ("retail", ("Rtail",), 1.0), ("print", ("Books",), 1.0),
               ("real_estate", ("RlEst",), 1.0), ("petroleum", ("Oil",), -1.0), ("metals", ("Steel", "Mines"), -1.0))
T597_PC = ("pc1", 1.0)
T597_TRAIN_FROM = "1963-07"
T597_FIRST_TARGET, T597_LAST_TARGET = "2003-01", "2026-08"
T597_SPLIT = "2015-01"
T597_MIN_N = 240
T597_MIN_TRAIN = 24
T597_FAMILY_MIN, T597_FAMILY_FULL = 35, 39
T597_THRESHOLDS = (("forecast > DTB3/12", "dtb3"), ("forecast > 0", "zero"))


def ff_monthly(rows) -> tuple:
    """({month: compounded Mkt-RF = R_m - R_f}, {month: compounded R_f}) from french-ff5-daily rows (percent); the last
    month only when complete."""
    acc = {}
    last = ""
    for r in rows:
        v = r.get("value") or {}
        d = v.get("day")
        mk, rf = _num(v.get("Mkt-RF")), _num(v.get("RF"))
        if not d or mk is None or rf is None:
            continue
        a = acc.setdefault(d[:7], [1.0, 1.0])
        a[0] *= 1.0 + (mk + rf) / 100.0
        a[1] *= 1.0 + rf / 100.0
        last = max(last, d)
    if last and not month_complete(last):
        acc.pop(last[:7], None)
    return {m: a[0] - a[1] for m, a in acc.items()}, {m: a[1] - 1.0 for m, a in acc.items()}


def ind_monthly(rows, names: Sequence[str]) -> dict:
    """{industry: {month: compounded daily value-weighted return}}; a month in which any session lacks the industry's
    return is NaN."""
    prod = {n: defaultdict(lambda: 1.0) for n in names}
    cnt = {n: defaultdict(int) for n in names}
    ndays = defaultdict(int)
    for r in rows:
        v = r.get("value") or {}
        d = v.get("day")
        if not d:
            continue
        m = d[:7]
        ndays[m] += 1
        for n in names:
            x = _num(v.get(n))
            if x is None:
                continue
            prod[n][m] *= 1.0 + x / 100.0
            cnt[n][m] += 1
    return {n: {m: (prod[n][m] - 1.0 if cnt[n][m] == nd else float("nan")) for m, nd in ndays.items()} for n in names}


def group_returns(ind: dict, comps: Sequence[str]) -> dict:
    """{month: equal-weight mean of the components' monthly returns} (NaN when any component is missing)."""
    months = set.intersection(*(set(ind[c]) for c in comps))
    return {m: float(np.mean([ind[c][m] for c in comps])) for m in months}


def t597_arrays(x: dict, y: dict) -> tuple:
    """Predictor months 1963-07..(last target - 1), the predictor and its target Mkt-RF(t+1) aligned by predictor month."""
    ms = mrange(T597_TRAIN_FROM, madd(T597_LAST_TARGET, -1))
    X = np.array([x.get(m, np.nan) for m in ms], float)
    Y = np.array([y.get(madd(m, 1), np.nan) for m in ms], float)
    return ms, X, Y


def t597_k0(ms: Sequence[str]) -> int:
    return ms.index(madd(T597_FIRST_TARGET, -1))


def t597_score(ms: Sequence[str], rec: dict, sign: float, tgt: dict, dtb3: tuple) -> dict:
    """R2_OS, halves, Clark-West (NW lag 12), sign-restricted R2 and both switching readings of one OOS record."""
    tm = [madd(ms[k], 1) for k in rec["k"]]
    y, fb, fm = rec["y"], rec["fb"], rec["fm"]
    out = {"n": int(y.size), "target_first": tm[0] if tm else None, "target_last": tm[-1] if tm else None}
    if y.size < 10:
        return out
    h1 = np.array([m < T597_SPLIT for m in tm])
    cw = cw_series(y, fb, fm)
    nw = hac_mean(cw, CW_LAG)
    fsr = np.where(np.sign(rec["slope"]) == sign, fm, fb)
    ym, thr = np.full(y.size, np.nan), np.full(y.size, np.nan)
    for i, k in enumerate(rec["k"]):
        t = ms[k]
        if t in tgt:
            e, d0, _ = tgt[t]
            ym[i] = e
            thr[i] = dtb3_before(dtb3[0], dtb3[1], d0) / 100.0 / 12.0
    ok = np.isfinite(ym)
    sw = {}
    for nm, key in T597_THRESHOLDS:
        th = thr[ok] if key == "dtb3" else 0.0
        sw[key] = {"rule": switching(ym[ok], fm[ok], th), "bench": switching(ym[ok], fb[ok], th),
                   "in_spy": float(np.mean(fm[ok] > th)), "bench_in_spy": float(np.mean(fb[ok] > th))}
    out.update(months=tm, y=y, fb=fb, fm=fm, r2=r2_os(y, fb, fm), halves=[r2_os(y[h1], fb[h1], fm[h1]),
               r2_os(y[~h1], fb[~h1], fm[~h1])], cw_t=nw["t"], cw_p=nw["p"], r2_sign_restricted=r2_os(y, fb, fsr),
               slope_last=float(rec["slope"][-1]), wrong_sign_share=float(np.mean(np.sign(rec["slope"]) != sign)),
               switch=sw, n_rule=int(ok.sum()))
    return out


def t597_r2(ms, X, Y) -> Optional[float]:
    rec = expanding_oos(X, Y, t597_k0(ms), len(ms) - 1, 0, 1, T597_MIN_TRAIN)
    return r2_os(rec["y"], rec["fb"], rec["fm"]) if rec["y"].size >= 10 else None


def b13_crossasset_b_industries_lead(archive):
    """T-597."""
    miss = _missing(archive, [IND49_B, FF5_B, SPY_B, DTB3_B])
    if miss:
        return miss
    ff_rows, ind_rows = CAL._rows(archive, FF5_B), CAL._rows(archive, IND49_B)
    mkt, _rf = ff_monthly(ff_rows)
    names = sorted({k for r in ind_rows[-5:] for k in (r.get("value") or {}) if k != "day"})
    ind = ind_monthly(ind_rows, names)
    sd, sa = CAL._daily(archive, SPY_B, "adjclose")
    sd = list(sd)
    bills = _bills(archive)
    dk = sorted(CAL._series(archive, DTB3_B))
    dv = [CAL._series(archive, DTB3_B)[k] for k in dk]
    ms_all = mrange(T597_TRAIN_FROM, madd(T597_LAST_TARGET, -1))
    tgt = spy_targets(sd, sa, bills, ms_all)
    used = sorted({c for _, cs, _ in T597_GROUPS for c in cs})
    other40 = [n for n in names if n not in used]
    set45 = other40 + [c for _, cs, _ in T597_GROUPS if len(cs) > 1 for c in cs]
    # ---- the 7 trials
    G = {g: group_returns(ind, cs) for g, cs, _ in T597_GROUPS}
    R = {}
    for g, _cs, sign in T597_GROUPS:
        ms, X, Y = t597_arrays(G[g], mkt)
        rec = expanding_oos(X, Y, t597_k0(ms), len(ms) - 1, 0, 1, T597_MIN_TRAIN)
        R[g] = t597_score(ms, rec, sign, tgt, (dk, dv)) | {"sign": sign}
    ms, _X, Y = t597_arrays({}, mkt)
    GM = np.column_stack([[G[g].get(m, np.nan) for m in ms] for g, _, _ in T597_GROUPS])
    prec = pc1_oos(GM, Y, t597_k0(ms), len(ms) - 1, 1, T597_MIN_TRAIN)
    R["pc1"] = t597_score(ms, prec, T597_PC[1], tgt, (dk, dv)) | {"sign": T597_PC[1]}
    R["pc1"]["loadings_last"] = prec["loadings"][-1].tolist() if len(prec["loadings"]) else None
    trials = [g for g, _, _ in T597_GROUPS] + ["pc1"]
    # ---- placebo industries
    plac = {}
    for nme in sorted(set(set45)):
        msn, Xn, Yn = t597_arrays(ind[nme], mkt)
        plac[nme] = t597_r2(msn, Xn, Yn)
    p40 = np.array([plac[n] for n in other40 if plac.get(n) is not None], float)
    p45 = np.array([plac[n] for n in set45 if plac.get(n) is not None], float)
    q40 = float(np.percentile(p40, 95)) if p40.size else None
    q45 = float(np.percentile(p45, 95)) if p45.size else None
    holm = CAL._holm({g: R[g].get("cw_p") for g in trials})
    trows, tinfo = [], {}
    for g in trials:
        r = R[g]
        if r.get("n", 0) < 10:
            trows.append((f"{g}: too few forecasts", None, False))
            continue
        rows = [(f"R2_OS {_s(r['r2'], 4)} > 0", _b(r["r2"] is not None and r["r2"] > 0), False),
                (f"Clark-West NW (lag {CW_LAG}) t {_s(r['cw_t'], 2)}, p {_f(r['cw_p'], 4)}, Holm (7) {_f(holm[g], 4)} < 0.05",
                 _b(holm[g] is not None and r["cw_t"] > 0 and holm[g] < ALPHA), bool(_fin(r["cw_t"]) and r["cw_t"] < -1.645)),
                (f"R2_OS > 0 in 2003-2014 ({_s(r['halves'][0], 4)}) and 2015-2026-08 ({_s(r['halves'][1], 4)})",
                 None if any(h is None for h in r["halves"]) else bool(all(h > 0 for h in r["halves"])), False),
                BW.all_constructions([(f"40 untouched industries' 95th percentile {_s(q40, 4)}",
                                       None if q40 is None or r["r2"] is None else bool(r["r2"] > q40), False),
                                      (f"45 (the 40 + the 5 group components) 95th percentile {_s(q45, 4)}",
                                       None if q45 is None or r["r2"] is None else bool(r["r2"] > q45), False)],
                                     "R2_OS above the industry placebo")]
        srows, drows, sinfo = [], [], {}
        for nm, key in T597_THRESHOLDS:
            s = r["switch"][key]
            sdf = sharpe_diff(s["rule"], s["bench"])
            srows.append(switch_row(sdf, nm))
            drow, dinf = dsr_bound(s["rule"], T597_FAMILY_MIN, T597_FAMILY_FULL, f"{nm} switching rule")
            drows.append(drow)
            sinfo[key] = {"sharpe_rule": sdf.get("sharpe_a"), "sharpe_bench": sdf.get("sharpe_b"), "diff": sdf.get("diff"),
                          "ci": sdf.get("ci"), "in_spy": s["in_spy"], "bench_in_spy": s["bench_in_spy"], "dsr": dinf}
        rows.append(BW.all_constructions(srows, "switching rule beats the historical-mean rule"))
        rows.append(BW.all_constructions(drows, f"joint-family DSR > {DSR_PASS}"))
        trows.append(and_rows(rows, g))
        tinfo[g] = sinfo
    crit = [any_rows(trows, "at least one of the 7 trials passes every criterion")]
    n = int(min(R[g].get("n", 0) for g in trials))
    v, why, crit_j = CAL._judge(crit, n, T597_MIN_N, "monthly forecasts")
    stat = {"n": n, "placebo_p95": {"40": q40, "45": q45}, "placebo_r2": plac, "criteria": crit_j, "verdict": v,
            "trials": {g: {k: R[g].get(k) for k in ("n", "target_first", "target_last", "r2", "halves", "cw_t", "cw_p",
                                                    "r2_sign_restricted", "slope_last", "wrong_sign_share", "sign")}
                       | {"holm_p": holm[g], "switch": tinfo.get(g)} for g in trials},
            "pc1_loadings_last": R["pc1"].get("loadings_last")}
    parts = []
    for g in trials:
        r, si = R[g], tinfo.get(g) or {}
        sw = si.get("dtb3") or {}
        parts.append(f"{g}: R2_OS {_s(r.get('r2'), 4)} (halves {_s((r.get('halves') or [None])[0], 4)} / "
                     f"{_s((r.get('halves') or [None, None])[1], 4)}; sign-restricted {_s(r.get('r2_sign_restricted'), 4)}), "
                     f"CW t {_s(r.get('cw_t'), 2)} Holm p {_f(holm[g], 3)}, switch SR {_f(sw.get('sharpe_rule'), 2)} vs "
                     f"{_f(sw.get('sharpe_bench'), 2)}, DSR <= {_f((sw.get('dsr') or {}).get('dsr_bound'), 3)}")
    reason = (f"FF49 groups -> Mkt-RF(t+1), expanding OLS from {T597_TRAIN_FROM}, target months "
              f"{R['financial'].get('target_first')}..{R['financial'].get('target_last')} ({n} forecasts): " + "; ".join(parts)
              + f". Placebo 95th percentiles of R2_OS: {_s(q40, 4)} (40 untouched industries), {_s(q45, 4)} (45). "
              f"The FF49 and Mkt-RF series are 2026 vintages revised over time (Tse's CRSP-revision caveat); the switching "
              f"rule trades SPY from the first close of t+1; the joint-family DSR can fail but not pass here")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-602 ==

T602_TRAIN_FROM_BAA = "1993-02"
T602_FIRST_TARGET_BAA = "2010-01"
T602_LAST_TARGET = "2026-09"
T602_BETA_WIN = 36
T602_MIN_TRAIN = 24
T602_ETF_MIN_TRAIN = 60
T602_GAP = 2
T602_MIN_N = 120
T602_FAMILY_MIN, T602_FAMILY_FULL = 9, 31
T602_TRIALS = (("dBAA10Y", -1.0), ("LQD", 1.0), ("HYG", 1.0))


def month_end_values(series: dict) -> dict:
    """{month: the last print dated in the month}; the month of the series' last print only when complete."""
    by = {}
    for d in sorted(series):
        by[d[:7]] = float(series[d])
    if series and not month_complete(max(series)):
        by.pop(max(series)[:7], None)
    return by


def month_changes(me: dict) -> dict:
    return {m: me[m] - me[madd(m, -1)] for m in me if madd(m, -1) in me}


def month_returns(days: Sequence[str], adj) -> dict:
    """{month: last close of the month / last close of the previous month - 1}; the last month only when complete."""
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    ms = sorted(last)
    out = {m: float(adj[last[m]] / adj[last[p]] - 1.0) for p, m in zip(ms[:-1], ms[1:]) if madd(p, 1) == m}
    if len(days) and not month_complete(days[-1]):
        out.pop(days[-1][:7], None)
    return out


def hedged_excess(re: dict, ri: dict, win: int = T602_BETA_WIN) -> tuple:
    """({month t: r_ETF(t) - beta_t r_IEF(t)}, {t: beta_t}) with beta_t the OLS slope of r_ETF on r_IEF over the 36
    months t-35..t (all known at the close of t)."""
    out, betas = {}, {}
    for m in sorted(re):
        ws = [madd(m, -k) for k in range(win - 1, -1, -1)]
        if not all(w in re and w in ri for w in ws):
            continue
        a = np.array([re[w] for w in ws])
        b = np.array([ri[w] for w in ws])
        vb = float(((b - b.mean()) ** 2).sum())
        if vb <= 0:
            continue
        beta = float(((b - b.mean()) * (a - a.mean())).sum() / vb)
        out[m] = re[m] - beta * ri[m]
        betas[m] = beta
    return out, betas


def t602_reading(x: dict, tgt: dict, train_from: str, first_target: str, last_target: str, min_train: int,
                 with_p: bool = True) -> dict:
    """One equity-premium predictor reading: expanding OOS record (gap 2), R2_OS overall and by half, Clark-West (NW lag
    12 normal p and the 12-month block bootstrap p), slope NW t on the window's pairs and on every pair, switching-rule
    excess returns and the historical-mean rule's."""
    ms = mrange(train_from, madd(last_target, -1))
    X = np.array([x.get(m, np.nan) for m in ms], float)
    Y = np.array([tgt[m][0] if m in tgt else np.nan for m in ms], float)
    k0 = max(0, _mi(first_target) - 1 - _mi(train_from))
    rec = expanding_oos(X, Y, k0, len(ms) - 1, 0, T602_GAP, min_train)
    tm = [madd(ms[k], 1) for k in rec["k"]]
    y, fb, fm = rec["y"], rec["fb"], rec["fm"]
    out = {"n": int(y.size), "target_first": tm[0] if tm else None, "target_last": tm[-1] if tm else None}
    if y.size < 10:
        return out
    cw = cw_series(y, fb, fm)
    nw = hac_mean(cw, CW_LAG)
    pg, pl, dr = CAL.studentized_p_escalated(cw, BLOCK_M, None, SEED, CAL.N_SEEDS) if with_p else (None, None, 0)
    h = y.size // 2
    allm = np.isfinite(X) & np.isfinite(Y)
    ra = ols_nw_all(y, X[rec["k"]], CAL.nw_lags(int(y.size)))
    rb = ols_nw_all(Y[allm], X[allm], CAL.nw_lags(int(allm.sum())))
    out.update(months=tm, y=y, fb=fb, fm=fm, xk=X[rec["k"]], r2=r2_os(y, fb, fm),
               halves=[r2_os(y[:h], fb[:h], fm[:h]), r2_os(y[h:], fb[h:], fm[h:])], half_split=tm[h],
               cw_mean=float(cw.mean()), cw_t=nw["t"], cw_p=nw["p"], cw_boot_p=pg, cw_boot_p_lt=pl, cw_draws=dr,
               slope_window=ra, slope_all=rb, switch=switching(y, fm, 0.0), bench=switching(y, fb, 0.0),
               in_spy=float(np.mean(fm > 0)), bench_in_spy=float(np.mean(fb > 0)))
    return out


def b13_crossasset_b_credit_premium(archive):
    """T-602."""
    miss = _missing(archive, [BAA_B, HYG_B, LQD_B, IEF_B, SPY_B, DTB3_B])
    if miss:
        return miss
    sd, sa = CAL._daily(archive, SPY_B, "adjclose")
    sd = list(sd)
    bills = _bills(archive)
    tgt = spy_targets(sd, sa, bills, mrange("1993-01", madd(T602_LAST_TARGET, -1)))
    baa = month_changes(month_end_values(CAL._series(archive, BAA_B)))
    rets = {}
    for s, b in (("LQD", LQD_B), ("HYG", HYG_B), ("IEF", IEF_B)):
        d, a = CAL._daily(archive, b, "adjclose")
        rets[s] = month_returns(list(d), np.asarray(a, float))
    preds, betas = {"dBAA10Y": baa}, {}
    for s in ("LQD", "HYG"):
        preds[s], betas[s] = hedged_excess(rets[s], rets["IEF"])
    R = {"dBAA10Y": t602_reading(baa, tgt, T602_TRAIN_FROM_BAA, T602_FIRST_TARGET_BAA, T602_LAST_TARGET, T602_MIN_TRAIN)}
    for s in ("LQD", "HYG"):
        f0 = min(preds[s])
        R[s] = t602_reading(preds[s], tgt, f0, madd(f0, 1), T602_LAST_TARGET, T602_ETF_MIN_TRAIN)
    names = [nm for nm, _ in T602_TRIALS]
    holm_nw = CAL._holm({nm: R[nm].get("cw_p") for nm in names})
    holm_bs = CAL._holm({nm: R[nm].get("cw_boot_p") for nm in names})
    trows, tinfo = [], {}
    for nm, sign in T602_TRIALS:
        r = R[nm]
        if r.get("n", 0) < 10:
            trows.append((f"{nm}: too few forecasts", None, False))
            continue
        draws = r["cw_draws"]
        cw_row = BW.all_constructions(
            [(f"NW (lag {CW_LAG}) t {_s(r['cw_t'], 2)}, p {_f(r['cw_p'], 4)}, Holm {_f(holm_nw[nm], 4)}",
              _b(holm_nw[nm] is not None and r["cw_t"] > 0 and holm_nw[nm] < ALPHA), bool(_fin(r["cw_t"]) and r["cw_t"] < -1.645)),
             (f"block bootstrap ({BLOCK_M}) p {CAL._mc(r['cw_boot_p'], draws)}, Holm {_f(holm_bs[nm], 4)}",
              B7C._sig_crit(r["cw_mean"], holm_bs[nm], draws), CAL.decide_p(r["cw_boot_p_lt"], draws) is True)],
            "Clark-West one-sided p < 0.05 after Holm over 3 trials")
        ca = (r["slope_window"].get("coef") or [None, None])[1]
        cb = (r["slope_all"].get("coef") or [None, None])[1]
        ta = (r["slope_window"].get("t") or [None, None])[1]
        tb = (r["slope_all"].get("t") or [None, None])[1]
        sg = "negative" if sign < 0 else "positive"
        sign_row = BW.all_constructions(
            [(f"window pairs slope {_s(ca, 4)} (NW t {_s(ta, 2)})", None if ca is None else bool(sign * ca > 0), False),
             (f"all pairs slope {_s(cb, 4)} (NW t {_s(tb, 2)})", None if cb is None else bool(sign * cb > 0), False)],
            f"pre-registered {sg} slope")
        sdf = sharpe_diff(r["switch"], r["bench"])
        drow, dinf = dsr_bound(r["switch"], T602_FAMILY_MIN, T602_FAMILY_FULL, f"joint-family DSR > {DSR_PASS} (switching rule)")
        rows = [(f"R2_OS {_s(r['r2'], 4)} > 0", _b(r["r2"] is not None and r["r2"] > 0), False), cw_row, sign_row,
                (f"R2_OS > 0 in both halves of {r['target_first']}..{r['target_last']} (split {r['half_split']}: "
                 f"{_s(r['halves'][0], 4)} / {_s(r['halves'][1], 4)})",
                 None if any(h is None for h in r["halves"]) else bool(all(h > 0 for h in r["halves"])), False),
                switch_row(sdf, "long SPY when the forecast is positive"), drow]
        trows.append(and_rows(rows, nm))
        tinfo[nm] = {"sharpe_rule": sdf.get("sharpe_a"), "sharpe_bench": sdf.get("sharpe_b"), "diff": sdf.get("diff"),
                     "ci": sdf.get("ci"), "in_spy": r["in_spy"], "bench_in_spy": r["bench_in_spy"], "dsr": dinf}
    crit = [any_rows(trows, "at least one of the 3 trials passes every criterion")]
    n = int(min(R[nm].get("n", 0) for nm in names))
    v, why, crit_j = CAL._judge(crit, n, T602_MIN_N, "monthly forecasts (the shortest trial)")
    # ---- reported: SPY's own month-t return as a control regressor; raw (unhedged) ETF returns
    spy_m = spy_month_returns(sd, sa)
    ctrl, raw = {}, {}
    for nm in names:
        r = R[nm]
        if r.get("n", 0) < 10:
            continue
        ms_ = [madd(m, -1) for m in r["months"]]
        ok = [i for i, m in enumerate(ms_) if m in spy_m]
        Xc = np.column_stack([r["xk"][ok], [spy_m[ms_[i]] for i in ok]])
        c = ols_nw_all(r["y"][ok], Xc, CAL.nw_lags(len(ok)))
        ctrl[nm] = {"t_pred": (c.get("t") or [None, None, None])[1], "t_spy": (c.get("t") or [None, None, None])[2]}
    for s in ("LQD", "HYG"):
        if R[s].get("n", 0) >= 10:
            rr = t602_reading(rets[s], tgt, min(rets[s]), R[s]["target_first"], T602_LAST_TARGET, T602_ETF_MIN_TRAIN, False)
            raw[s] = {"n": rr.get("n"), "r2": rr.get("r2"), "cw_t": rr.get("cw_t")}
    stat = {"n": n, "criteria": crit_j, "verdict": v, "holm_nw": holm_nw, "holm_boot": holm_bs, "spy_control": ctrl,
            "raw_unhedged": raw, "betas_last": {s: betas[s][max(betas[s])] for s in betas if betas[s]},
            "trials": {nm: {k: R[nm].get(k) for k in ("n", "target_first", "target_last", "r2", "halves", "half_split",
                                                      "cw_t", "cw_p", "cw_boot_p")}
                       | {"slope_window": (R[nm].get("slope_window") or {}).get("coef"),
                          "slope_all": (R[nm].get("slope_all") or {}).get("coef"), "switch": tinfo.get(nm)} for nm in names},
            "blocked_trials": ["EBP change (first-release vintages not archived)", "bond skewness (TRACE not archived)"]}
    parts = []
    for nm in names:
        r, si = R[nm], tinfo.get(nm) or {}
        if r.get("n", 0) < 10:
            parts.append(f"{nm}: {r.get('n', 0)} forecasts")
            continue
        parts.append(f"{nm} {r['target_first']}..{r['target_last']} ({r['n']}): R2_OS {_s(r['r2'], 4)} (halves "
                     f"{_s(r['halves'][0], 4)} / {_s(r['halves'][1], 4)}), CW t {_s(r['cw_t'], 2)} (Holm NW "
                     f"{_f(holm_nw[nm], 3)}, boot {_f(holm_bs[nm], 3)}), slope {_s((r['slope_window'].get('coef') or [0, None])[1], 4)} "
                     f"(t {_s((r['slope_window'].get('t') or [0, None])[1], 2)}), switch SR {_f(si.get('sharpe_rule'), 2)} vs "
                     f"{_f(si.get('sharpe_bench'), 2)} (in SPY {si.get('in_spy', 0) * 100:.0f}% vs "
                     f"{si.get('bench_in_spy', 0) * 100:.0f}%), DSR <= {_f((si.get('dsr') or {}).get('dsr_bound'), 3)}; "
                     f"with SPY's month-t return the predictor t is {_s((ctrl.get(nm) or {}).get('t_pred'), 2)}")
    rtxt = ", ".join(f"raw {s} R2_OS {_s(raw[s]['r2'], 4)} (CW t {_s(raw[s]['cw_t'], 2)})" for s in raw)
    reason = ("SPY fill-to-fill excess return (first close of t+1 to the first close of t+2, minus DTB3) on three "
              "pre-signed credit predictors, expanding OLS (gap 2): " + "; ".join(parts) + f". Reported: {rtxt}. The "
              "duration-hedged ETF returns are Mandel proxies, not the paper's TRACE moments (a null is weak evidence "
              "against the paper); the EBP-change and bond-skewness trials are blocked; the joint-family DSR can fail "
              "but not pass here")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-601 ==

T601_START, T601_END = "2025-10-01", "2026-09-30"
T601_SPLIT = "2026-04-01"
T601_SUB_END = "2026-07-31"
T601_PRE = ("2023-11-01", "2025-09-30")
T601_LOCKBOX = "2026-10-01"
T601_SD_SESS = 20
T601_COST_SIDE = 2e-4                 # 1 bp half-spread + 1 bp slippage
T601_BLOCK = 5
T601_NBOOT = 2000                     # x 5 seeds = 10,000 draws, escalated while undecided
T601_N_PLACEBO = 1000
T601_BASKET = 30
T601_MIN_N = 300
T601_TRIALS = 15                      # this rule + the 14 T-577/T-578 bond_etf F0F1 cells
T601_LOCAL_STOCKS = ("AAPL", "ADBE", "AMD", "AMZN", "AVGO", "BAC", "COIN", "COST", "CRM", "CVX", "GOOGL", "HD", "INTC",
                     "JPM", "LLY", "META", "MSFT", "MSTR", "MU", "NFLX", "NVDA", "ORCL", "PLTR", "SMCI", "TSLA", "UNH",
                     "WMT", "XOM")
T601_ARCHIVE_STOCKS = ("BMO", "BNS", "CNI", "CNQ", "CP", "ENB", "RY", "SHOP", "SU", "TD")
T601_READINGS = (("bar", "bar return = the bar's open to its close"),
                 ("c2c", "bar return = close to close (09:30 bar from the previous session's last close)"))


def bars_from_arrays(t, o, c) -> dict:
    """Regular-session 60-minute bars (stamped 09:30..15:30 ET at their open; the 13:00 / 16:00 zero-length closing
    stubs dropped) dated before the lockbox: {t (epoch s), day (ET), o, c}, sorted by time."""
    t = np.asarray(t, np.int64)
    o, c = np.asarray(o, float), np.asarray(c, float)
    order = np.argsort(t, kind="stable")
    t, o, c = t[order], o[order], c[order]
    keep_t, keep_d, keep_o, keep_c = [], [], [], []
    for ti, oi, ci in zip(t.tolist(), o.tolist(), c.tolist()):
        dt = datetime.fromtimestamp(ti, NY)
        d = dt.strftime("%Y-%m-%d")
        if dt.minute != 30 or not (9 <= dt.hour <= 15) or d >= T601_LOCKBOX:
            continue
        keep_t.append(ti); keep_d.append(d); keep_o.append(oi); keep_c.append(ci)
    t2 = np.array(keep_t, np.int64)
    _, first = np.unique(t2, return_index=True)
    return {"t": t2[first], "day": np.array(keep_d)[first], "o": np.array(keep_o, float)[first],
            "c": np.array(keep_c, float)[first]}


def bars_from_df(df) -> Optional[dict]:
    """``bars_from_arrays`` on a ``mandel.ml.features.load_bars`` frame (UTC DatetimeIndex of any unit)."""
    if df is None or df.empty:
        return None
    t = df.index.tz_convert(None).values.astype("datetime64[s]").astype(np.int64)     # unit-safe epoch seconds
    return bars_from_arrays(t, df["o"].to_numpy(float), df["c"].to_numpy(float))


def load_local_60m(sym: str) -> Optional[dict]:
    from mandel.ml.features import load_bars
    return bars_from_df(load_bars("60m", sym))


def load_archive_60m(archive, sym: str) -> Optional[dict]:
    name = "hourly-" + sym
    if not B7C._has(archive, name):
        return None
    rows = [r.get("value") or {} for r in CAL._rows(archive, name)]
    rows = [v for v in rows if v.get("t") is not None]
    if not rows:
        return None
    return bars_from_arrays([int(v["t"]) for v in rows], [_num(v.get("open")) or np.nan for v in rows],
                            [_num(v.get("close")) or np.nan for v in rows])


def grid_of(spy: dict) -> dict:
    """The master bar grid (SPY's bars): session index, session starts and whether the next bar is 60 minutes later in
    the same session."""
    t, day = spy["t"], spy["day"]
    sdays, sess = np.unique(day, return_inverse=True)
    nxt = np.zeros(t.size, bool)
    if t.size > 1:
        nxt[:-1] = (np.diff(t) == 3600) & (sess[1:] == sess[:-1])
    starts = np.flatnonzero(np.r_[True, sess[1:] != sess[:-1]]) if t.size else np.zeros(0, int)
    return {"t": t, "day": day, "sess": sess, "sdays": sdays, "n_sess": int(sdays.size), "starts": starts, "next_ok": nxt}


def align(grid_t, b: Optional[dict]) -> tuple:
    """(open, close) of bars ``b`` on the grid's timestamps (NaN where the symbol has no bar)."""
    o = np.full(grid_t.size, np.nan)
    c = np.full(grid_t.size, np.nan)
    if b is None or not b["t"].size:
        return o, c
    j = np.minimum(np.searchsorted(b["t"], grid_t), b["t"].size - 1)
    hit = b["t"][j] == grid_t
    o[hit], c[hit] = b["o"][j[hit]], b["c"][j[hit]]
    return o, c


def bar_ret(o, c, reading: str) -> np.ndarray:
    """A bar's return under ``reading`` ('bar': its own open to close; 'c2c': the previous grid bar's close to its close),
    known at the bar's close; NaN when an input is missing."""
    o, c = np.asarray(o, float), np.asarray(c, float)
    base = o if reading == "bar" else np.r_[np.nan, c[:-1]]
    r = np.full(c.size, np.nan)
    ok = np.isfinite(base) & (np.nan_to_num(base) > 0) & np.isfinite(c)
    r[ok] = c[ok] / base[ok] - 1.0
    return r


def next_bar_ret(o, c, next_ok) -> np.ndarray:
    """y[i] = the open-to-close return of bar i+1 when it is the next bar of the same session (NaN otherwise)."""
    o, c = np.asarray(o, float), np.asarray(c, float)
    y = np.full(o.size, np.nan)
    i = np.flatnonzero(next_ok)
    if i.size:
        oo, cc = o[i + 1], c[i + 1]
        ok = np.isfinite(oo) & (np.nan_to_num(oo) > 0) & np.isfinite(cc)
        y[i[ok]] = cc[ok] / oo[ok] - 1.0
    return y


def session_sd(R, starts, n_sess: int, win: int = T601_SD_SESS) -> np.ndarray:
    """Per session s (and per column of R): the s.d. (ddof 1) of the finite bar returns in sessions s-win..s-1; NaN for
    the first ``win`` sessions."""
    R = np.asarray(R, float)
    one = R.ndim == 1
    if one:
        R = R[:, None]
    F = np.isfinite(R)
    R0 = np.where(F, R, 0.0)
    S1 = np.add.reduceat(R0, starts, axis=0)
    S2 = np.add.reduceat(R0 * R0, starts, axis=0)
    SN = np.add.reduceat(F.astype(float), starts, axis=0)
    z = np.zeros((1, R.shape[1]))
    C1, C2, CN = (np.vstack([z, np.cumsum(S, axis=0)]) for S in (S1, S2, SN))
    sd = np.full((n_sess, R.shape[1]), np.nan)
    if n_sess > win:
        s = np.arange(win, n_sess)
        W1, W2, WN = C1[s] - C1[s - win], C2[s] - C2[s - win], CN[s] - CN[s - win]
        with np.errstate(invalid="ignore", divide="ignore"):
            var = (W2 - W1 * W1 / WN) / (WN - 1.0)
        sd[s] = np.where(WN >= 2, np.sqrt(np.maximum(var, 0.0)), np.nan)
    return sd[:, 0] if one else sd


def signals(r_lead, sd_sess, sess, next_ok) -> np.ndarray:
    """Direction at each bar's close: sign(r) when |r| exceeds the session's trailing s.d. and the next bar is in the
    same session, else 0."""
    r = np.asarray(r_lead, float)
    th = np.asarray(sd_sess, float)[sess]
    ok = next_ok & np.isfinite(r) & np.isfinite(th) & (np.abs(np.nan_to_num(r)) > np.nan_to_num(th, nan=np.inf))
    return np.where(ok, np.sign(np.nan_to_num(r)), 0.0)


def t601_book(r_lead, y_next, G: dict, lo: str, hi: str, cost_side: float = T601_COST_SIDE) -> dict:
    """The rule's trades over sessions [lo, hi]: bar index, direction, gross and net (2 sides x cost) per trade, and the
    per-session sum of net returns (zero on sessions without a trade)."""
    sd = session_sd(r_lead, G["starts"], G["n_sess"])
    sig = signals(r_lead, sd, G["sess"], G["next_ok"])
    inw = (G["day"] >= lo) & (G["day"] <= hi)
    take = (sig != 0) & np.isfinite(y_next) & inw
    idx = np.flatnonzero(take)
    gross = sig[idx] * y_next[idx]
    net = gross - 2.0 * cost_side
    xs = np.bincount(G["sess"][idx], weights=net, minlength=G["n_sess"])
    sw = (G["sdays"] >= lo) & (G["sdays"] <= hi)
    return {"idx": idx, "sig": sig[idx], "gross": gross, "net": net, "day": G["day"][idx], "sess_series": xs[sw],
            "n_sessions": int(sw.sum()), "sd": sd}


def placebo_means(Rst, counts, y_next, G: dict, lo: str, hi: str, cost_side: float = T601_COST_SIDE,
                  chunk: int = 200) -> np.ndarray:
    """Net mean per trade of the rule led by an equal-weight basket (columns of ``counts``: each stock's multiplicity in
    the basket of one draw), each draw with its own trailing-20-session threshold."""
    F = np.isfinite(Rst)
    R0 = np.where(F, Rst, 0.0)
    Ff = F.astype(float)
    inw = (G["day"] >= lo) & (G["day"] <= hi)
    yok = np.isfinite(y_next)
    y0 = np.nan_to_num(y_next)
    base = (G["next_ok"] & yok & inw)[:, None]
    out = []
    for c0 in range(0, counts.shape[1], chunk):
        Wc = counts[:, c0:c0 + chunk].astype(float)
        num, den = R0 @ Wc, Ff @ Wc
        B = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
        th = session_sd(B, G["starts"], G["n_sess"])[G["sess"]]
        ok = base & np.isfinite(B) & np.isfinite(th) & (np.abs(np.nan_to_num(B)) > np.nan_to_num(th, nan=np.inf))
        net = np.where(ok, np.sign(np.nan_to_num(B)) * y0[:, None] - 2.0 * cost_side, 0.0)
        k = ok.sum(axis=0)
        out.append(np.where(k > 0, net.sum(axis=0) / np.maximum(k, 1), np.nan))
    return np.concatenate(out) if out else np.zeros(0)


def draw_counts(n_pool: int, n_draws: int, size: int, replace: bool, seed: int = SEED) -> np.ndarray:
    """(n_pool x n_draws) multiplicities of ``size``-stock baskets drawn from a pool."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n_pool, n_draws), np.int64)
    for k in range(n_draws):
        idx = rng.integers(0, n_pool, size=size) if replace else rng.choice(n_pool, size=size, replace=False)
        np.add.at(out[:, k], idx, 1)
    return out


def t601_reading(name: str, R: dict, G: dict, Rpool_a, Rpool_b, cnt_a, cnt_b) -> tuple:
    """Criterion rows and statistics of one bar-return reading."""
    bk = t601_book(R["spy"], R["y_hyg"], G, T601_START, T601_END)
    net, days = bk["net"], bk["day"]
    n = int(net.size)
    m = float(net.mean()) if n else None
    pg, pl, dr = CAL.studentized_p_escalated(bk["sess_series"], T601_BLOCK, T601_NBOOT, SEED, B7C.N_SEEDS)
    h1 = days < T601_SPLIT
    hv = [float(net[h1].mean()) if h1.any() else None, float(net[~h1].mean()) if (~h1).any() else None]
    sub = days <= T601_SUB_END
    sv = float(net[sub].mean()) if sub.any() else None
    pa = placebo_means(Rpool_a, cnt_a, R["y_hyg"], G, T601_START, T601_END)
    pb = placebo_means(Rpool_b, cnt_b, R["y_hyg"], G, T601_START, T601_END)
    qa = float(np.nanpercentile(pa, 95)) if np.isfinite(pa).any() else None
    qb = float(np.nanpercentile(pb, 95)) if np.isfinite(pb).any() else None
    drow, dinf = dsr_bound(net, T601_TRIALS, T601_TRIALS, f"DSR > {DSR_PASS} with the 14 bond_etf cells (15 trials)")
    rows = [(f"net mean {_bp(m)} per trade > 0 with one-sided p < 0.05 (session-block bootstrap, {T601_BLOCK} sessions, "
             f"p {CAL._mc(pg, dr)})", B7C._sig_crit(m, pg, dr), CAL.decide_p(pl, dr) is True),
            (f"both halves positive ({_bp(hv[0])} / {_bp(hv[1])})", None if None in hv else bool(all(v > 0 for v in hv)), False),
            (f"2025-10..2026-07 alone positive ({_bp(sv)})", None if sv is None else bool(sv > 0), False),
            BW.all_constructions([(f"(a) 30 of 38 without replacement: 95th percentile {_bp(qa)}",
                                   None if qa is None or m is None else bool(m > qa), False),
                                  (f"(b) 30 draws with replacement from the 28: 95th percentile {_bp(qb)}",
                                   None if qb is None or m is None else bool(m > qb), False)],
                                 f"above the random-basket placebo ({T601_N_PLACEBO} draws)"),
            drow]
    # reported: lead regression, LQD follower, IWM leader, pre-period
    eg = G["next_ok"] & (G["day"] >= T601_START) & (G["day"] <= T601_END) & np.isfinite(R["y_hyg"]) \
        & np.isfinite(R["spy"]) & np.isfinite(R["hyg"])
    reg = ols_nw_all(R["y_hyg"][eg], np.column_stack([R["spy"][eg], R["hyg"][eg]]), CAL.nw_lags(int(eg.sum())))
    lqd = t601_book(R["spy"], R["y_lqd"], G, T601_START, T601_END)
    iwm = t601_book(R["iwm"], R["y_hyg"], G, T601_START, T601_END)
    pre = t601_book(R["spy"], R["y_hyg"], G, *T601_PRE)
    info = {"n": n, "net_bp": None if m is None else m * 1e4, "gross_bp": float(bk["gross"].mean() * 1e4) if n else None,
            "hit": float(np.mean(bk["gross"] > 0)) if n else None, "p": pg, "p_lt": pl, "draws": dr,
            "halves_bp": [None if v is None else v * 1e4 for v in hv], "sub_bp": None if sv is None else sv * 1e4,
            "placebo_p95_bp": {"a": None if qa is None else qa * 1e4, "b": None if qb is None else qb * 1e4},
            "placebo_mean_bp": {"a": float(np.nanmean(pa) * 1e4), "b": float(np.nanmean(pb) * 1e4)},
            "dsr": dinf, "regression": {"b_spy": (reg.get("coef") or [None] * 3)[1], "t_spy": (reg.get("t") or [None] * 3)[1],
                                        "c_hyg": (reg.get("coef") or [None] * 3)[2], "t_hyg": (reg.get("t") or [None] * 3)[2],
                                        "n": reg["n"]},
            "lqd_follower": {"n": int(lqd["net"].size), "net_bp": float(lqd["net"].mean() * 1e4) if lqd["net"].size else None},
            "iwm_leader": {"n": int(iwm["net"].size), "net_bp": float(iwm["net"].mean() * 1e4) if iwm["net"].size else None},
            "pre_period": {"n": int(pre["net"].size), "net_bp": float(pre["net"].mean() * 1e4) if pre["net"].size else None},
            "sessions": bk["n_sessions"], "idx": bk["idx"]}
    return rows, info


def open_print_check(archive, bundle: str, G: dict, o_grid) -> dict:
    """Yahoo daily open vs the 09:30 60-minute bar's open on window days (T-549's check). Report only."""
    daily = {}
    for r in CAL._rows(archive, bundle):
        v = r.get("value") or {}
        try:
            d = datetime.fromtimestamp(float(v["t"]), timezone.utc).strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError):
            continue
        x = _num(v.get("open"))
        if x:
            daily[d] = x
    diffs = []
    for i in np.flatnonzero((G["day"] >= T601_START) & (G["day"] <= T601_END)):
        if datetime.fromtimestamp(int(G["t"][i]), NY).strftime("%H:%M") != "09:30":
            continue
        d = G["day"][i]
        if d in daily and np.isfinite(o_grid[i]) and o_grid[i] > 0:
            diffs.append(daily[d] / o_grid[i] - 1.0)
    x = np.abs(np.array(diffs))
    if not x.size:
        return {"n_days": 0}
    return {"n_days": int(x.size), "median_abs_diff_bp": float(np.median(x) * 1e4), "share_gt_5bp": float(np.mean(x > 5e-4))}


def b13_crossasset_b_spy_leads_hyg(archive):
    """T-601."""
    miss = _missing(archive, [HYG_B, LQD_B])
    if miss:
        return miss
    bars = {s: load_local_60m(s) for s in ("SPY", "HYG", "LQD", "IWM")}
    gone = [s for s, b in bars.items() if b is None or not b["t"].size]
    if gone:
        return _out({"missing_60m": gone}, 0, "inconclusive",
                    f"60-minute bars for {gone} are not in mandel/ml_data/bars/60m: the claim cannot be tested (rule 9)")
    G = grid_of(bars["SPY"])
    O, C = {}, {}
    for s, b in bars.items():
        O[s], C[s] = align(G["t"], b)
    local = {s: load_local_60m(s) for s in T601_LOCAL_STOCKS}
    local = {s: b for s, b in local.items() if b is not None and b["t"].size}
    arch = {s: load_archive_60m(archive, s) for s in T601_ARCHIVE_STOCKS}
    arch = {s: b for s, b in arch.items() if b is not None and b["t"].size}
    pool_a = list(local) + list(arch)
    pool_b = list(local)
    SO, SC = {}, {}
    for s, b in {**local, **arch}.items():
        SO[s], SC[s] = align(G["t"], b)
    cnt_a = draw_counts(len(pool_a), T601_N_PLACEBO, T601_BASKET, replace=False, seed=SEED) if len(pool_a) >= T601_BASKET else None
    cnt_b = draw_counts(len(pool_b), T601_N_PLACEBO, T601_BASKET, replace=True, seed=SEED + 1) if pool_b else None
    if cnt_a is None or cnt_b is None:
        return _out({"pool_a": len(pool_a), "pool_b": len(pool_b)}, 0, "inconclusive",
                    f"only {len(pool_a)} stocks with 60-minute bars: the {T601_BASKET}-stock placebo cannot be drawn (rule 9)")
    rowsets, infos = [], {}
    for key, _desc in T601_READINGS:
        R = {"spy": bar_ret(O["SPY"], C["SPY"], key), "hyg": bar_ret(O["HYG"], C["HYG"], key),
             "iwm": bar_ret(O["IWM"], C["IWM"], key),
             "y_hyg": next_bar_ret(O["HYG"], C["HYG"], G["next_ok"]), "y_lqd": next_bar_ret(O["LQD"], C["LQD"], G["next_ok"])}
        Ra = np.column_stack([bar_ret(SO[s], SC[s], key) for s in pool_a])
        Rb = np.column_stack([bar_ret(SO[s], SC[s], key) for s in pool_b])
        rows, info = t601_reading(key, R, G, Ra, Rb, cnt_a, cnt_b)
        rowsets.append(rows)
        infos[key] = info
    names = [k for k, _ in T601_READINGS]
    crit = per_reading(rowsets, names)
    n = int(min(infos[k]["n"] for k in names))
    v, why, crit_j = CAL._judge(crit, n, T601_MIN_N, "trades (the smaller reading)")
    # stale-print check on the primary trades: entry open equal to the previous bar's close, and entering at that close
    ib = infos["bar"]["idx"]
    stale = float(np.mean(O["HYG"][ib + 1] == C["HYG"][ib])) if ib.size else None
    oq = {"HYG": open_print_check(archive, HYG_B, G, O["HYG"]), "LQD": open_print_check(archive, LQD_B, G, O["LQD"])}
    stat = {"n": n, "criteria": crit_j, "verdict": v, "readings": {k: {kk: vv for kk, vv in infos[k].items() if kk != "idx"}
                                                                   for k in names},
            "pool_a": pool_a, "pool_b": pool_b, "entry_open_equals_prev_close_share": stale, "open_quality": oq,
            "bars": int(G["t"].size), "sessions": int(G["n_sess"]), "lockbox_from": T601_LOCKBOX}
    parts = []
    for k, desc in T601_READINGS:
        i = infos[k]
        rg = i["regression"]
        parts.append(f"[{desc}] {i['n']} trades over {i['sessions']} sessions, net {_f(i['net_bp'], 2)} bp/trade (gross "
                     f"{_f(i['gross_bp'], 2)}, hit {_f(i['hit'], 3)}, p {_f(i['p'], 4)}), halves {_f(i['halves_bp'][0], 2)} / "
                     f"{_f(i['halves_bp'][1], 2)}, 2025-10..2026-07 {_f(i['sub_bp'], 2)}; placebo 95th pct "
                     f"{_f(i['placebo_p95_bp']['a'], 2)} (a) / {_f(i['placebo_p95_bp']['b'], 2)} (b); DSR <= "
                     f"{_f(i['dsr'].get('dsr_bound'), 3)}; HYG(h+1) on SPY(h) b t {_s(rg['t_spy'], 2)} (own lag t "
                     f"{_s(rg['t_hyg'], 2)}); LQD follower {_f(i['lqd_follower']['net_bp'], 2)} bp ({i['lqd_follower']['n']}), "
                     f"IWM leader {_f(i['iwm_leader']['net_bp'], 2)} bp ({i['iwm_leader']['n']}), pre-period 2023-11..2025-09 "
                     f"{_f(i['pre_period']['net_bp'], 2)} bp ({i['pre_period']['n']})")
    reason = (f"Yahoo 60-minute bars {T601_START}..{T601_END}, HYG held one bar in SPY's direction when |SPY bar| > its "
              f"trailing-20-session s.d., 2 bp per side: " + "; ".join(parts) + f". Entry open equal to the previous bar's "
              f"close on {_f(stale, 3)} of trades; Yahoo daily vs 09:30-bar open (HYG) median |diff| "
              f"{_f(oq['HYG'].get('median_abs_diff_bp'), 2)} bp. Opens are trade prints, not quotes; lockbox from "
              f"{T601_LOCKBOX} unread; placebo pools: (a) {len(pool_a)} names, (b) {len(pool_b)} names")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-604 ==

T604_START, T604_END = "2013-01-01", "2026-09-30"
T604_SEL = ("2000-01-01", "2012-12-31")
T604_SPLIT = "2020-01-01"
T604_FORMS = (1, 5)
T604_COST_SIDE = 3e-4
T604_PRICE_MIN = 5.0
T604_VIX_WIN = 252
T604_VIX_NEED = 200
T604_HAC_LAG = 10
T604_BLOCK = 20
T604_MIN_N = 2500
T604_TRIALS = 2 + 18                  # 2 formation lengths + T-462's 18 counted cells
T604_XS_START = "1999-06-01"
T604_FF_END = "2026-08-31"


def stock_splits(archive, sym: str) -> list:
    """[(ex_date, ratio)] from a symbol's daily-events bundle, parsed exactly as ``batch6c_stockxs._stock`` does."""
    name = SX.de(sym)
    if not B7C._has(archive, name):
        return []
    out = []
    for r in SX._stream(archive, name):
        v = r.get("value") or {}
        if r.get("kind") != "split" and v.get("type") != "split":
            continue
        try:
            num, den = float(v.get("numerator")), float(v.get("denominator"))
            ex = v.get("ex_date") or SX._bar_day(v["t"])
        except (TypeError, ValueError, KeyError):
            continue
        if num > 0 and den > 0 and ex:
            out.append((str(ex)[:10], num / den))
    return sorted(out)


def split_factors(days: Sequence[str], splits: Sequence[tuple]) -> np.ndarray:
    """Per day: the product of the split ratios with an ex-date after it (raw price = split-adjusted close x factor)."""
    if not splits:
        return np.ones(len(days))
    exs = np.array([s[0] for s in splits])
    suffix = np.ones(len(splits) + 1)
    for k in range(len(splits) - 1, -1, -1):
        suffix[k] = suffix[k + 1] * splits[k][1]
    return suffix[np.searchsorted(exs, np.asarray(days), side="right")]


def t604_base(archive) -> dict:
    """Point-in-time S&P 500 panel for T-604 (SPY sessions from 1999-06): membership (fja05680 + later Wikipedia
    changes), T-473's usable-series filters, open / close / adjclose / raw close matrices from the shared daily panel."""
    def load():
        from mandel.experiments.panel_cache import daily_panel
        P = daily_panel(archive)
        pdays = P.days.astype(str)
        spy_c = P.col("SPY", "close")
        rows = np.flatnonzero(np.isfinite(spy_c) & (pdays >= T604_XS_START) & (pdays <= T604_END))
        days = [str(d) for d in pdays[rows]]
        sets, n_wiki = SX._member_sets(archive)
        sdates = [d for d, _ in sets]
        k0 = max(0, bisect.bisect_right(sdates, days[0]) - 1)
        tick = set()
        for _, s in sets[k0:]:
            tick |= set(s)
        wiki = {}
        if B7C._has(archive, SX.WIKI_B):
            for r in SX._rows(archive, SX.WIKI_B):
                v = r.get("value") or {}
                if v.get("symbol"):
                    wiki[SX.ysym(v["symbol"])] = v
        removed = {}
        if B7C._has(archive, SX.WIKI_CH_B):
            for r in SX._rows(archive, SX.WIKI_CH_B):
                v = r.get("value") or {}
                if v.get("removed_ticker") and v.get("removed_security"):
                    removed[SX.ysym(v["removed_ticker"])] = v["removed_security"]
        sec_t = SX._sec_tickers(archive) if B7C._has(archive, SX.SEC_TICK_B) else {}
        pcol = {str(s): j for j, s in enumerate(P.symbols.tolist())}
        info = {"tickers": len(tick), "no_series": [], "not_equity": [], "name_mismatch": [], "wiki_changes_after_fja": n_wiki}
        cand = []
        for t in sorted(tick):
            y = SX.ysym(t)
            j = pcol.get(SX._safe(y))
            if j is None:
                info["no_series"].append(y)
                continue
            meta = SX._meta(archive, SX.dh(y)) or {}
            if meta.get("instrumentType") != "EQUITY":
                info["not_equity"].append(y)
                continue
            cand.append((y, j, meta))
        need = {sec_t[y][0] for y, _, _ in cand if y not in wiki and removed.get(y) and y in sec_t}
        comp = SX._company_rows(archive, need) if need else {}
        keep = []
        for y, j, meta in cand:
            if y not in wiki and removed.get(y):
                names = [meta.get("longName") or ""]
                if y in sec_t:
                    v = comp.get(sec_t[y][0]) or {}
                    names += [sec_t[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
                if SX.names_ok(removed[y], names) is False:
                    info["name_mismatch"].append(y)
                    continue
            keep.append((y, j))
        syms = [y for y, _ in keep]
        cols = np.array([j for _, j in keep], int)
        O, C, A = (np.ascontiguousarray(getattr(P, f)[np.ix_(rows, cols)]) for f in ("open", "close", "adjclose"))
        F = np.column_stack([split_factors(days, stock_splits(archive, y)) for y in syms])
        RAW = C * F
        del F
        col = {y: k for k, y in enumerate(syms)}
        D, N = len(days), len(syms)
        member = np.zeros((D, N), bool)
        n_set = np.zeros(D, int)
        cache = {}
        for i, d in enumerate(days):
            k = bisect.bisect_right(sdates, d) - 1
            if k < 0:
                continue
            if k not in cache:
                cache[k] = [col[SX.ysym(t)] for t in sets[k][1] if SX.ysym(t) in col]
            member[i, cache[k]] = True
            n_set[i] = len(sets[k][1])
        info.update(kept=N, member_days=int(n_set[np.array(days) >= T604_START].sum()),
                    member_days_priced=int((member & np.isfinite(C))[np.array(days) >= T604_START].sum()))
        spy_o, spy_cc = P.col("SPY", "open")[rows], spy_c[rows]
        return {"days": np.array(days), "syms": syms, "O": O, "C": C, "A": A, "RAW": RAW, "member": member,
                "spy_o": np.asarray(spy_o, float), "spy_c": np.asarray(spy_cc, float), "info": info}
    return CAL._cached(archive, ("t604_base",), load)


def eligible(member, raw, A, price_min: float = T604_PRICE_MIN) -> np.ndarray:
    """A name is eligible at close i when it is a member then, has a bar then and a raw close >= $5."""
    with np.errstate(invalid="ignore"):
        return member & np.isfinite(A) & np.isfinite(raw) & (np.nan_to_num(raw) >= price_min)


def reversal_weights(A, OK, L: int) -> np.ndarray:
    """W[t]: -(r - mean r) scaled to $1 long and $1 short over the names eligible at close t-1 (OK[t-1]), r the
    formation return from close t-1-L to close t-1 (bars needed at both ends). Row t uses rows <= t-1 only."""
    A = np.asarray(A, float)
    D, N = A.shape
    R = np.full((D, N), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        R[L:] = A[L:] / A[:-L] - 1.0
    RF = np.full((D, N), np.nan)
    RF[1:] = R[:-1]
    del R
    E = np.zeros((D, N), bool)
    E[1:] = OK[:-1]
    E &= np.isfinite(RF)
    cnt = E.sum(axis=1)
    mu = np.where(E, RF, 0.0).sum(axis=1) / np.maximum(cnt, 1)
    dev = np.where(E, RF - mu[:, None], 0.0)
    del RF
    g = np.abs(dev).sum(axis=1)
    good = (cnt >= 2) & (g > 0)
    W = np.where(good[:, None], -dev / np.where(good, g / 2.0, 1.0)[:, None], 0.0)
    return W


def day_returns(W, O, C, cost_side: float = T604_COST_SIDE) -> tuple:
    """(gross, net, filled gross) of the open-to-close book: a name with no day-t open or close is unfilled (0, no
    cost); cost = 2 sides x ``cost_side`` x the filled gross."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r = C / O - 1.0
    fill = np.isfinite(r) & (np.nan_to_num(O) > 0) & (W != 0)
    gross = np.where(fill, W * np.nan_to_num(r), 0.0).sum(axis=1)
    turn = np.where(fill, np.abs(W), 0.0).sum(axis=1)
    return gross, gross - 2.0 * cost_side * turn, turn


def vix_grid(vix: dict, days: Sequence[str]) -> np.ndarray:
    """Per session: the latest VIX close dated on or before it."""
    ks = sorted(vix)
    if not ks:
        return np.full(len(days), np.nan)
    vals = np.array([vix[k] for k in ks], float)
    j = np.searchsorted(np.array(ks), np.asarray(days), side="right") - 1
    return np.where(j >= 0, vals[np.maximum(j, 0)], np.nan)


def vix_terciles(vg) -> tuple:
    """For each day t: VIX(t-1) and the 1/3 and 2/3 quantiles of the 252 values VIX(t-252)..VIX(t-1) (NaN with fewer than
    200 finite values). Day t uses values dated <= t-1 only."""
    vg = np.asarray(vg, float)
    D = vg.size
    vp = np.r_[np.nan, vg[:-1]]
    q1, q2 = np.full(D, np.nan), np.full(D, np.nan)
    if D > T604_VIX_WIN:
        from numpy.lib.stride_tricks import sliding_window_view
        win = sliding_window_view(vg, T604_VIX_WIN)[: D - T604_VIX_WIN]       # row k = vg[k .. k+251], for day k + 252
        cnt = np.isfinite(win).sum(axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            qa = np.nanquantile(win, [1.0 / 3.0, 2.0 / 3.0], axis=1)
        t = np.arange(T604_VIX_WIN, D)
        okc = cnt >= T604_VIX_NEED
        q1[t] = np.where(okc, qa[0], np.nan)
        q2[t] = np.where(okc, qa[1], np.nan)
    return vp, q1, q2


def ff49_daily(rows, names: Sequence[str]) -> tuple:
    """(days, days x industries matrix of daily decimal returns; NaN where missing)."""
    days, M = [], []
    for r in rows:
        v = r.get("value") or {}
        if not v.get("day"):
            continue
        days.append(v["day"])
        M.append([(_num(v.get(n)) if _num(v.get(n)) is not None else np.nan) for n in names])
    order = np.argsort(days)
    return np.array(days)[order], np.array(M, float)[order] / 100.0


def ff49_reversal(fd, FM, L: int, days, vp, q2) -> dict:
    """The FF49 industry version (gross, costless diagnostic): weights -(r - mean r) over the L-session compounded
    industry returns ending at close t-1, held close t-1 to close t (French daily returns), 2013-01..2026-08."""
    lr = np.log1p(FM)
    fin = np.isfinite(lr)
    cs = np.vstack([np.zeros((1, FM.shape[1])), np.cumsum(np.where(fin, lr, 0.0), axis=0)])
    cf = np.vstack([np.zeros((1, FM.shape[1]), int), np.cumsum(fin, axis=0)])
    RFm = np.full_like(FM, np.nan)
    t = np.arange(L, FM.shape[0])
    okc = (cf[t] - cf[t - L]) == L                                  # rows t-L..t-1 all present
    RFm[t] = np.where(okc, np.expm1(cs[t] - cs[t - L]), np.nan)
    E2 = np.isfinite(RFm)
    mu = np.where(E2, RFm, 0.0).sum(1) / np.maximum(E2.sum(1), 1)
    dev = np.where(E2, RFm - mu[:, None], 0.0)
    gsum = np.abs(dev).sum(1)
    Wf = np.where((gsum > 0)[:, None], -dev / np.where(gsum > 0, gsum / 2, 1)[:, None], 0.0)
    gf = np.where(np.isfinite(FM), Wf * np.nan_to_num(FM), 0.0).sum(1)
    pos = np.searchsorted(days, fd).clip(0, len(days) - 1)
    aligned = np.asarray(days)[pos] == fd
    vpf, q2f = vp[pos], q2[pos]
    evf = aligned & (fd >= T604_START) & (fd <= T604_FF_END) & np.isfinite(vpf) & np.isfinite(q2f) & (gsum > 0)
    topf = evf & (vpf > np.nan_to_num(q2f, nan=np.inf))
    rf_ = ols_nw_all(gf[evf], vpf[evf], T604_HAC_LAG)
    return {"formation": L, "n": int(evf.sum()), "gross_bp": float(gf[evf].mean() * 1e4) if evf.any() else None,
            "top_gross_bp": float(gf[topf].mean() * 1e4) if topf.any() else None, "vix_slope_t": (rf_.get("t") or [None, None])[1],
            "weights": Wf, "gross": gf}


def t604_eval(net, vp, q2, days, ev) -> dict:
    """Slope of net on VIX(t-1) (HAC lag 10), top-tercile mean and halves over the evaluation days ``ev``."""
    top = ev & np.isfinite(q2) & (vp > np.nan_to_num(q2, nan=np.inf))
    reg = ols_nw_all(net[ev], vp[ev], T604_HAC_LAG)
    m = float(net[top].mean()) if top.any() else None
    share = top[ev].mean() if ev.any() else 0.0
    d = net[ev] * top[ev] / share if share > 0 else np.zeros(int(ev.sum()))
    pg, pl, dr = CAL.studentized_p_escalated(d, T604_BLOCK, None, SEED, CAL.N_SEEDS)
    halves = []
    for hm in (days < T604_SPLIT, days >= T604_SPLIT):
        e2, t2 = ev & hm, top & hm
        rr = ols_nw_all(net[e2], vp[e2], T604_HAC_LAG)
        halves.append({"slope": (rr.get("coef") or [None, None])[1], "t": (rr.get("t") or [None, None])[1],
                       "top_mean": float(net[t2].mean()) if t2.any() else None, "n": int(e2.sum()), "n_top": int(t2.sum())})
    return {"n": int(ev.sum()), "n_top": int(top.sum()), "slope": (reg.get("coef") or [None, None])[1],
            "slope_t": (reg.get("t") or [None, None])[1], "top_mean": m, "p": pg, "p_lt": pl, "draws": dr,
            "halves": halves, "top": top}


def t604_rows(E: dict, top_net) -> tuple:
    hv = E["halves"]
    ok_h = None if any(h["slope"] is None or h["top_mean"] is None for h in hv) else \
        bool(all(h["slope"] > 0 and h["top_mean"] > 0 for h in hv))
    drow, dinf = dsr_bound(top_net, T604_TRIALS, T604_TRIALS, f"DSR > {DSR_PASS} with T-462's 18 cells (20 trials, "
                                                               f"top-tercile days)")
    rows = [(f"VIX slope HAC (lag {T604_HAC_LAG}) t {_s(E['slope_t'], 2)} > 1.65",
             None if E["slope_t"] is None else bool(E["slope_t"] > 1.65), bool(_fin(E["slope_t"]) and E["slope_t"] < -1.645)),
            (f"top-tercile net mean {_bp(E['top_mean'])} > 0 with one-sided p < 0.05 ({E['n_top']} days, p "
             f"{CAL._mc(E['p'], E['draws'])})", B7C._sig_crit(E["top_mean"], E["p"], E["draws"]),
             CAL.decide_p(E["p_lt"], E["draws"]) is True),
            (f"both halves positive (slope {_s(hv[0]['slope'], 6)} / {_s(hv[1]['slope'], 6)}; top-tercile mean "
             f"{_bp(hv[0]['top_mean'])} / {_bp(hv[1]['top_mean'])})", ok_h, False),
            drow]
    return rows, dinf


def b13_crossasset_b_vix_reversal(archive):
    """T-604."""
    miss = _missing(archive, [FJA_B, VIX_B, SPY_B])
    if miss:
        return miss
    if not SX._entry_names(archive, "daily-history-"):
        return _out({"missing_bundles": ["daily-history-*"]}, 0, "inconclusive",
                    "missing data bundles daily-history-*: the claim cannot be tested until they are archived (rule 9)")
    B = t604_base(archive)
    days = B["days"]
    OK = eligible(B["member"], B["RAW"], B["A"])
    vg = vix_grid(CAL._series(archive, VIX_B), list(days))
    vp, q1, q2 = vix_terciles(vg)
    books = {}
    for L in T604_FORMS:
        W = reversal_weights(B["A"], OK, L)
        g, net, turn = day_returns(W, B["O"], B["C"])
        with np.errstate(invalid="ignore", divide="ignore"):
            rc = B["A"] / np.r_[np.full((1, B["A"].shape[1]), np.nan), B["A"][:-1]] - 1.0
        gcc = np.where(np.isfinite(rc) & (W != 0), W * np.nan_to_num(rc), 0.0).sum(axis=1)
        filled = (W != 0) & np.isfinite(B["O"]) & np.isfinite(B["C"])
        eqc = float(np.mean((B["O"] == B["C"])[filled & (days >= T604_START)[:, None]])) if filled.any() else None
        books[L] = {"gross": g, "net": net, "turn": turn, "gross_cc": gcc, "n_names": (W != 0).sum(axis=1),
                    "open_eq_close": eqc}
        del W, rc, filled
    base_ok = np.isfinite(vp) & np.isfinite(q2)
    sel = (days >= T604_SEL[0]) & (days <= T604_SEL[1]) & base_ok
    sel_sh = {}
    for L, bk in books.items():
        s = sel & (bk["turn"] > 0)
        topm = s & (vp > np.nan_to_num(q2, nan=np.inf))
        sel_sh[L] = {"all_days": float(sharpe_ratio(bk["net"][s], 252)), "top_days": float(sharpe_ratio(bk["net"][topm], 252)),
                     "n": int(s.sum()), "n_top": int(topm.sum())}
    pick_all = max(T604_FORMS, key=lambda L: sel_sh[L]["all_days"])
    pick_top = max(T604_FORMS, key=lambda L: sel_sh[L]["top_days"])
    judged = [pick_all] if pick_all == pick_top else list(T604_FORMS)
    rowsets, evals, dinfo = [], {}, {}
    for L in judged:
        bk = books[L]
        ev = (days >= T604_START) & (days <= T604_END) & base_ok & (bk["turn"] > 0)
        E = t604_eval(bk["net"], vp, q2, days, ev)
        rows, dinf = t604_rows(E, bk["net"][E["top"]])
        rowsets.append(rows)
        evals[L], dinfo[L] = E, dinf
    crit = per_reading(rowsets, [f"{L}-day formation" for L in judged]) if len(judged) > 1 else rowsets[0]
    n = int(min(evals[L]["n"] for L in judged))
    v, why, crit_j = CAL._judge(crit, n, T604_MIN_N, "trading days")
    # ---- reported: unconditional baseline, terciles, beta, close-to-close upper bound, FF49 industry version
    rep = {}
    for L in T604_FORMS:
        bk = books[L]
        ev = (days >= T604_START) & (days <= T604_END) & base_ok & (bk["turn"] > 0)
        x = bk["net"][ev]
        hm = hac_mean(x, T604_HAC_LAG)
        low = ev & (vp < np.nan_to_num(q1, nan=-np.inf))
        top = ev & (vp > np.nan_to_num(q2, nan=np.inf))
        mid = ev & ~low & ~top
        so = B["spy_c"] / B["spy_o"] - 1.0
        bb = ols_nw_all(x, so[ev], T604_HAC_LAG)
        cc_top = float(bk["gross_cc"][top].mean()) if top.any() else None
        rcc = ols_nw_all(bk["gross_cc"][ev], vp[ev], T604_HAC_LAG)
        rep[L] = {"uncond_net_bp": float(x.mean() * 1e4), "uncond_t": hm["t"], "gross_bp": float(bk["gross"][ev].mean() * 1e4),
                  "tercile_net_bp": {"low": float(bk["net"][low].mean() * 1e4) if low.any() else None,
                                     "mid": float(bk["net"][mid].mean() * 1e4) if mid.any() else None,
                                     "top": float(bk["net"][top].mean() * 1e4) if top.any() else None},
                  "beta_spy_o2c": (bb.get("coef") or [None, None])[1], "beta_t": (bb.get("t") or [None, None])[1],
                  "c2c_gross_bp": float(bk["gross_cc"][ev].mean() * 1e4), "c2c_gross_top_bp": None if cc_top is None else cc_top * 1e4,
                  "c2c_vix_slope_t": (rcc.get("t") or [None, None])[1], "mean_names": float(bk["n_names"][ev].mean()),
                  "open_eq_close_share": bk["open_eq_close"], "selection_sharpe": sel_sh[L]}
    ffrep = None
    if B7C._has(archive, IND49_B):
        rows49 = CAL._rows(archive, IND49_B)
        nm49 = sorted({k for r in rows49[-5:] for k in (r.get("value") or {}) if k != "day"})
        fd, FM = ff49_daily(rows49, nm49)
        ffrep = {L: ff49_reversal(fd, FM, L, days, vp, q2) for L in judged}
    info = B["info"]
    cov = info["member_days_priced"] / info["member_days"] if info["member_days"] else None
    stat = {"n": n, "criteria": crit_j, "verdict": v, "selection": {"all_days": pick_all, "top_days": pick_top, "judged": judged,
                                                                   "sharpe": sel_sh},
            "eval": {L: {k: vv for k, vv in evals[L].items() if k != "top"} | {"dsr": dinfo[L]} for L in judged},
            "reported": rep, "ff49_gross": None if not ffrep else {L: {k: vv for k, vv in fr.items() if k not in ("weights", "gross")} for L, fr in ffrep.items()}, "coverage_member_days_priced": cov,
            "universe": {k: (len(vv) if isinstance(vv, list) else vv) for k, vv in info.items()}}
    parts = []
    for L in judged:
        E, r = evals[L], rep[L]
        parts.append(f"{L}-day formation: {E['n']} days, VIX slope {_s(E['slope'], 6)} (HAC t {_s(E['slope_t'], 2)}), "
                     f"top-tercile net {_bp(E['top_mean'])} over {E['n_top']} days (p {_f(E['p'], 4)}), halves slope t "
                     f"{_s(E['halves'][0]['t'], 2)} / {_s(E['halves'][1]['t'], 2)}, top mean {_bp(E['halves'][0]['top_mean'])} / "
                     f"{_bp(E['halves'][1]['top_mean'])}; DSR <= {_f(dinfo[L].get('dsr_bound'), 3)}; unconditional net "
                     f"{_f(r['uncond_net_bp'], 2)} bp/day (gross {_f(r['gross_bp'], 2)}), terciles low/mid/top "
                     f"{_f(r['tercile_net_bp']['low'], 2)} / {_f(r['tercile_net_bp']['mid'], 2)} / {_f(r['tercile_net_bp']['top'], 2)} "
                     f"bp, beta to SPY open-to-close {_s(r['beta_spy_o2c'], 3)}, close-to-close gross (bounce-inflated upper "
                     f"bound) {_f(r['c2c_gross_bp'], 2)} bp, {r['mean_names']:.0f} names a day")
    ff_txt = "" if not ffrep else "; FF49 industry version (gross, costless) " + ", ".join(
        f"{L}-day {_f(fr['gross_bp'], 2)} bp/day (top tercile {_f(fr['top_gross_bp'], 2)}, VIX slope t {_s(fr['vix_slope_t'], 2)})"
        for L, fr in ffrep.items())
    reason = (f"dollar-neutral open-to-close reversal on point-in-time S&P 500 members >= $5, 3 bp per side on gross, "
              f"2013-01..2026-09; formation chosen on 2000-2012 net Sharpe ({pick_all}-day on every day "
              f"{sel_sh[pick_all]['all_days']:+.2f}, {pick_top}-day on top-tercile days {sel_sh[pick_top]['top_days']:+.2f}): "
              + "; ".join(parts) + ff_txt + f". SURVIVORSHIP: prices come from today's 901-symbol daily-history set, so "
              f"removed members are under-represented ({_f(cov, 3)} of 2013+ member-days priced; {len(info['no_series'])} "
              f"member tickers without a series, {len(info['name_mismatch'])} reused tickers dropped); the open print is a "
              f"trade, not a quote; the DSR can fail but not pass here")
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {
    "b13_crossasset_b_industries_lead": b13_crossasset_b_industries_lead,
    "b13_crossasset_b_spy_leads_hyg": b13_crossasset_b_spy_leads_hyg,
    "b13_crossasset_b_credit_premium": b13_crossasset_b_credit_premium,
    "b13_crossasset_b_vix_reversal": b13_crossasset_b_vix_reversal,
}
THEORY_MAP = {
    "T-597": "b13_crossasset_b_industries_lead",
    "T-601": "b13_crossasset_b_spy_leads_hyg",
    "T-602": "b13_crossasset_b_credit_premium",
    "T-604": "b13_crossasset_b_vix_reversal",
}
