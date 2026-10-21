"""
Batch 13, group ``implied_b``: option-implied predictors of the equity premium and of VX returns (T-649, T-650, T-653),
pre-registered from the 2026-10-20 web sweep (cluster "implied").
=====================================================================================================================

  * T-649  Monthly at each month's last NYSE session t: VRP_t = (VIX_t / 100)^2 / 12 minus the sum of squared ^GSPC daily
           log returns over the 21 sessions ending at t. Expanding OLS from 1990-01 (each fit uses only targets whose
           window has ended by t) of the ^GSPC price excess return over DTB3 from the close of t+1 over the next h
           sessions (h = 21, 63, 126) on VRP, against the prevailing mean; forecasts 2008-01..2026-06. Pass: Clark-West
           one-sided p < 0.05 at 63 sessions on the trailing-RV VRP; the SPY timing rule (weight clip(forecast /
           prevailing mean, 0, 1.5), rest in bills, 2 bp per rebalance, leverage at DTB3 + 50 bp) beats buy-and-hold
           with the Sharpe-difference lower 95% bound > 0 (studentized circular block bootstrap, 12-month blocks); DSR
           >= 0.95 over the 6 trials (3 horizons x {trailing RV, HAR(1,5,22) RV forecast refitted monthly on prior
           data}). Also criteria (the claim and the controls' "must"): the 63-session OOS R^2 > 0, and the VRP's OOS
           R^2 above the VIX-level-only and trailing-RV-only predictors'. min_n 220 forecasts.
  * T-650  Monthly at month-end t: COR1M_t forecasts the SPY adjclose total-return excess over DTB3 (daily excess
           returns compounded) from the close of t+1 over h = 63, 126 (primary), 252 sessions; expanding OLS from
           2006-01 with the Campbell-Thompson slope restriction (a fitted slope below zero is replaced by the prevailing
           mean); forecasts 2013-01..2026-03. Pass: Clark-West one-sided p < 0.05 at 126 (Newey-West lag 6 months =
           126 sessions); OOS R^2 > 0 over 2019-01..2026-03 (and, the claim, over 2013-01..2026-03); DSR >= 0.95 over
           6 trials (3 horizons x {COR1M, DSPX}; DSPX's own expanding window from 2014-06, out of sample from 2017-01).
           Reported: the encompassing test against the VRP-only forecast ("incremental to VRP" recorded only if it
           rejects at p < 0.05), VIX and VRP as competing predictors, the timing-rule Sharpe difference. min_n 150.
  * T-653  Daily 2013-05..2026-10: PC2 = the sign-normalised second principal component of standardised log VIX9D,
           VIX, VIX3M, VIX6M closes (PCA and standardisation on the expanding window from 2011-01 ending at t; sign so
           that loading(VIX6M) - loading(VIX9D) > 0). Quintiles from PC2 values before t. Targets: (i) the 30-day
           constant-maturity VX return from the t+1 settle to the t+6 settle; (ii) VXX adjclose from the t+1 close to
           the t+6 close. Pass, confirmation 2019-01..2026-10: lowest-minus-highest quintile mean > 0 with Bonferroni
           (x2 targets) one-sided Newey-West (lag 5) p < 0.05 for (i) or (ii); the PC2 slope negative with one-sided
           p < 0.05 controlling for log(VIX/VIX3M) and log VIX; trading-form DSR >= 0.95 over the VX family. min_n
           1500 days.

Readings fixed before any run (the registrations are silent or ambiguous; each is the conservative one and is listed
in the reason so a reviewer sees it):
  * Month-end calendar (T-649, T-650): the last bar of each calendar month in the ^GSPC (T-649) or SPY (T-650) daily
    history; the data's final, incomplete month is never a month-end. The claims name this calendar, so there is no
    grid phase (house rule 10). A month whose index print (VIX / COR1M / DSPX) is missing on that session is skipped.
  * Point in time. Index closes (VIX family, COR1M, DSPX) are 16:15 ET prints archived available at 21:30 UTC: they
    are used only at t, and every position and target starts at the close (settle) of the next session. A daily bar is
    known at its close. DTB3 is the print dated strictly before each day (``batch6c_cal.Bills``), accrued day by day.
    The expanding fit at t uses only months whose target window ended at or before the close of t.
  * T-649 targets are ^GSPC price returns (no dividends) minus the bill return over the window; the timing rule trades
    SPY adjclose. Newey-West lag of the Clark-West t = h / 21 months (1, 3, 6), the larger reading of "the overlap".
    The HAR(1,5,22) model regresses the next 21 sessions' summed squared ^GSPC log returns on r_t^2 and the 5- and
    22-session mean squared returns, by OLS on every day from 1953-01 (the five-day week) whose 21-session target
    ended by t, refitted at each month-end; VRP_HAR = VIX^2/12 - its forecast. Costs: 2 bp of NAV each month the
    weight changes (and on the first entry, also for buy-and-hold); a weight above 1 borrows the excess at DTB3 + 50
    bp; a prevailing mean <= 0 gives weight 0. The timing rule trades the forecasts of 2008-01..2026-06 (each held
    from the close of t+1 to the close after the next month-end).
  * T-650: Newey-West lag max(6, h / 21) months (6, 6, 12). The slope restriction is applied to every trial (COR1M and
    DSPX) and to the VIX / VRP control forecasts (both have a positive expected sign). The timing rule (reported, and the DSR's series) uses clip(forecast / prevailing mean, 0, 1.5) and, as in
    its sibling T-649, finances leverage at DTB3 + 50 bp; 2 bp per change. The VRP control uses SPY closes (T-650's
    data list has no ^GSPC). The encompassing test is Harvey-Leybourne-Newbold's (d = (e_vrp - e_cor) e_vrp, NW t).
  * DSR (T-649, T-650): rule 11, judged on two series and passing only when both pass: the primary trial's monthly
    excess return over bills and its return minus buy-and-hold at the same average exposure; trial-Sharpe variance
    from the 6 computed trials floored at 1/(T-1) (``batch6c_mom.family_dsr``); pass at >= 0.95; a failure is decisive
    when the PSR against zero is <= 0.05.
  * T-653: the CM VX target is the tradable daily-rebalanced 30-day constant-maturity return: on each settle day d the
    weights on F1 / F2 (the first two monthly expiries strictly after d) are w1 = clip((tau2 - 30) / (tau2 - tau1), 0,
    1), tau in calendar days, held to the next settle (the expiring leg marks at its final settlement); the 5-day
    return compounds the daily returns from the t+1 settle to the t+6 settle (the interpolated level's change is
    reported). The PC2 history behind the quintile cutoffs is each earlier day's own point-in-time PC2, defined once
    the expanding window holds 252 days, and a day gets a quintile once 252 such values precede it. The slope criterion
    uses Bonferroni over the two targets like the spread and must hold on a target whose spread criterion passes; the
    slope is fitted on the confirmation window. Trading form: short 1 CM VX contract-equivalent ($1,000 x the weighted
    settle change) over [settle t+1, settle t+2] when PC2 at t is in quintile 4 or 5, $70 a side ($140 a round trip),
    versus always short; judged on the confirmation window. Its DSR family is the 8 named VX theories plus this one (9
    trials); none of the other 8 Sharpes is computed here (T-651 and T-652 are untested, the rest are other series),
    so ``dsr_vs_uncomputed_family`` can fail it (when even the most favourable variance, the 1/(T-1) floor, misses
    0.95) but never pass it (undecided otherwise). Rule 11 again on two series: the gated P&L and gated minus always.
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``, house rule 5).
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from datetime import date
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_hedge import vx_curve
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()

GSPC_B = "daily-history--GSPC"
SPY_B = "daily-history-SPY"
VIX_B = "cboe-VIX-history"
DTB3_B = "fred-DTB3"
COR1M_B = "cboe-COR1M-history"
DSPX_B = "cboe-DSPX-history"
VIX9D_B = "cboe-VIX9D-history"
VIX3M_B = "cboe-VIX3M-history"
VIX6M_B = "cboe-VIX6M-history"
VX_B = "cboe-vx-futures"
VXX_B = "daily-history-VXX"
SVXY_B = "daily-history-SVXY"

MIN_TRAIN = 24                  # months of realised targets before an expanding fit forecasts
W_MAX = 1.5
SPREAD_LEV = 0.005              # leverage financed at DTB3 + 50 bp
COST_REBAL = 2e-4               # 2 bp per rebalance
BLOCK_M = 12                    # 12-month blocks

# T-649
T649_TRAIN = "1990-01-01"
T649_OOS = ("2008-01-01", "2026-06-30")
T649_H = (21, 63, 126)
T649_PRIMARY = 63
T649_HAR_FROM = "1953-01-01"
T649_HAR_MIN = 252
T649_MIN_N = 220
# T-650
T650_TRAIN = "2006-01-01"
T650_OOS = ("2013-01-01", "2026-03-31")
T650_LATE = "2019-01-01"
T650_DSPX_TRAIN = "2014-06-01"
T650_DSPX_OOS = "2017-01-01"
T650_H = (63, 126, 252)
T650_PRIMARY = 126
T650_MIN_N = 150
# T-653
T653_PCA_FROM = "2011-01-01"
T653_START, T653_END = "2013-05-01", "2026-10-31"
T653_DISC = ("2013-05-01", "2018-12-31")
T653_CONF = ("2019-01-01", "2026-10-31")
T653_MIN_PCA = 252
T653_MIN_HIST = 252
T653_HOLD = 5                   # t+1 settle to t+6 settle
T653_LAG = 5
T653_CM_DAYS = 30
T653_VX_MULT = 1000.0
T653_VX_SIDE = 70.0             # $140 per round trip
T653_ETP_SIDE = 2.5e-4          # 5 bp per round trip
T653_FAMILY = 9                 # 8 named VX theories + this one
T653_MIN_N = 1500
TENORS = ("VIX9D", "VIX", "VIX3M", "VIX6M")


# ================================================================================================ statistics ==

def nw_mean(x, lag: int) -> dict:
    """Mean of x with its Newey-West (Bartlett, ``lag``) standard error and t."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else float("nan"), "se": float("nan"), "t": float("nan"), "n": int(n)}
    m = float(x.mean())
    z = x - m
    s = float(z @ z) / n
    for l in range(1, min(int(lag), n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(z[l:] @ z[:-l]) / n
    se = math.sqrt(max(s, 0.0) / n)
    return {"mean": m, "se": se, "t": m / se if se > 0 else float("nan"), "n": int(n), "lag": int(lag)}


def ols_nw_multi(y, X, lag: int) -> dict:
    """OLS of y on X (X carries its own constant column) with Newey-West (Bartlett, ``lag``) HAC standard errors."""
    y = np.asarray(y, float); X = np.asarray(X, float)
    n = y.size
    xtx = np.linalg.inv(X.T @ X)
    b = xtx @ X.T @ y
    u = X * (y - X @ b)[:, None]
    S = u.T @ u
    for l in range(1, min(int(lag), n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    V = xtx @ S @ xtx
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    return {"beta": b, "se": se, "t": np.where(se > 0, b / np.where(se > 0, se, 1.0), np.nan), "n": int(n), "lag": int(lag)}


def oos_stats(y, fm, fb, mask, lag: int) -> dict:
    """Campbell-Thompson OOS R^2 of forecast fm against the prevailing mean fb, and the Clark-West MSPE-adjusted t
    (Newey-West ``lag``) with its one-sided p (H0: the model adds nothing)."""
    y, fm, fb = (np.asarray(v, float) for v in (y, fm, fb))
    ok = np.asarray(mask, bool) & np.isfinite(y) & np.isfinite(fm) & np.isfinite(fb)
    out = {"n": int(ok.sum()), "oos_r2": None, "cw_t": None, "cw_p": None, "mspe_model": None, "mspe_bench": None}
    if ok.sum() < 8:
        return out
    em, eb = y[ok] - fm[ok], y[ok] - fb[ok]
    f = eb ** 2 - (em ** 2 - (fb[ok] - fm[ok]) ** 2)
    nw = nw_mean(f, lag)
    t = nw["t"]
    out.update(oos_r2=float(1.0 - (em @ em) / (eb @ eb)), cw_t=float(t), cw_p=float(1.0 - _N.cdf(t)) if math.isfinite(t) else None,
               mspe_model=float((em @ em) / em.size), mspe_bench=float((eb @ eb) / eb.size), lag=int(lag))
    return out


def encompassing(y, f_base, f_new, mask, lag: int) -> dict:
    """Harvey-Leybourne-Newbold forecast-encompassing test, H0: ``f_base`` encompasses ``f_new``; d = (e_base -
    e_new) e_base, one-sided p of mean(d) > 0 (rejection: f_new carries information f_base lacks)."""
    y, a, b = (np.asarray(v, float) for v in (y, f_base, f_new))
    ok = np.asarray(mask, bool) & np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 8:
        return {"n": int(ok.sum()), "t": None, "p": None}
    ea, eb = y[ok] - a[ok], y[ok] - b[ok]
    nw = nw_mean((ea - eb) * ea, lag)
    return {"n": int(ok.sum()), "t": nw["t"], "p": float(1.0 - _N.cdf(nw["t"])) if math.isfinite(nw["t"]) else None}


def _p_crit(p: Optional[float], t: Optional[float], label: str) -> tuple:
    """'one-sided p < 0.05' from an analytic t: (name, ok, decisive); decisive when the mirror one-sided test rejects."""
    if p is None or t is None or not math.isfinite(t):
        return f"{label} (n/a)", None, False
    return f"{label} (t {t:+.2f}, one-sided p {p:.4f})", p < ALPHA, _N.cdf(t) < ALPHA


def dsr_row_ge(d: dict, label: str) -> tuple:
    """(name, ok, decisive) for 'DSR >= 0.95' (``batch6c_mom.family_dsr`` dict); decisive when PSR vs 0 <= 0.05."""
    if d.get("dsr") is None:
        return f"{label} (n/a)", None, False
    obs = "n/a" if d.get("var_observed") is None else f"{d['var_observed']:.2e}"
    name = (f"{label} ({d['dsr']:.3f} at {d['n_trials']} trials; var(trial SR) {d['var_trials_sr']:.2e} = {d['var_used']}; "
            f"observed {obs}; PSR vs 0 {d['psr0']:.3f})")
    return name, d["dsr"] >= DSR_PASS, d["psr0"] is not None and d["psr0"] <= 1.0 - DSR_PASS


def dsr_vs_uncomputed_family(x, n_total: int, label: str) -> tuple:
    """DSR of ``x`` over ``n_total`` trials when only this trial's Sharpe is computed. The most favourable trial-Sharpe
    variance is the zero-skill floor 1/(T-1) (the uncomputed Sharpes can only raise it), so the DSR is at most its
    value there: fails when even that bound misses 0.95 (decisive when PSR vs 0 <= 0.05), undecided otherwise.
    Returns ((name, ok, decisive), info)."""
    x = np.asarray(x, float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_upper_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_total, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_upper_bound": hi, "var_floor": floor, "psr0": psr0, "n_total": int(n_total), "sharpe_pp": float(sharpe_ratio(x))}
    txt = f"{label} (at most {hi:.3f} at {n_total} trials, the 1/(T-1) floor {floor:.2e}; PSR vs 0 {psr0:.3f})"
    if hi < DSR_PASS:
        return (txt + " [fails whatever the other trials' Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + f" [the other {n_total - 1} family Sharpes are not computed here: cannot pass]", None, False), info


def _sharpe_diff(a, b, n_boot: Optional[int], reps: Optional[int]) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return BW.mc_escalate(lambda seed: BW.sharpe_diff_test(a, b, 12, BLOCK_M, n_boot, seed),
                          lambda t: BW._ci_crit(t, "gt", 0.0, "")[1], reps, SEED)


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _share(x) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x:.0%}"


def _dsr_obs(d: dict) -> str:
    return "n/a" if d.get("dsr_observed") is None else f"{d['dsr_observed']:.3f}"


def _ann_sr(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, 12)) if x.size > 2 and x.std() > 0 else None


# ============================================================================== monthly forecasting machinery ==

def month_end_pos(days: Sequence[str]) -> np.ndarray:
    """Positions of each calendar month's last session; the final month is dropped (it may be incomplete)."""
    return np.array([i for i in range(len(days) - 1) if days[i][:7] != days[i + 1][:7]], int)


def bill_index(days: Sequence[str], bills: CAL.Bills) -> np.ndarray:
    """Cumulative DTB3 accrual over a session calendar: each close-to-close step at the rate known at its start."""
    B = np.ones(len(days))
    for k in range(1, len(days)):
        B[k] = B[k - 1] * (1.0 + bills.growth(days[k - 1], days[k]))
    return B


def window_targets(pos: np.ndarray, h: int, n: int, ratio_fn) -> tuple:
    """(y, end): the target over the window from the close of t+1 (pos + 1) to the close h sessions later (pos + 1 + h),
    ``ratio_fn(a, e)`` its value; NaN where the window runs past the data. ``end`` is the session the window ends on."""
    a, e = pos + 1, pos + 1 + h
    y = np.full(pos.size, np.nan)
    ok = e < n
    y[ok] = ratio_fn(a[ok], e[ok])
    return y, e


def expanding_ols(x, y, pos, end, train, origins, restrict: bool = False, min_train: int = MIN_TRAIN) -> tuple:
    """Expanding one-regressor OLS forecasts. At origin j the fit uses months m with ``train[m]``, finite x and y, and
    a target window that ended at or before the close of month-end j (end[m] <= pos[j]). Returns (model forecast,
    prevailing mean, fitted slope); ``restrict``: a slope below zero is replaced by the prevailing mean."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    M = x.size
    fm, fb, sl = np.full(M, np.nan), np.full(M, np.nan), np.full(M, np.nan)
    tr_ok = np.asarray(train, bool) & np.isfinite(x) & np.isfinite(y)
    for j in np.where(np.asarray(origins, bool) & np.isfinite(x))[0]:
        m = tr_ok & (end <= pos[j])
        if m.sum() < min_train:
            continue
        xx, yy = x[m], y[m]
        xc = xx - xx.mean()
        vx = float(xc @ xc)
        b = float(xc @ (yy - yy.mean())) / vx if vx > 0 else 0.0
        fb[j] = float(yy.mean())
        sl[j] = b
        fm[j] = fb[j] if (restrict and b < 0) else float(yy.mean() - b * xx.mean() + b * x[j])
    return fm, fb, sl


def timing_weights(fm, fb, w_max: float = W_MAX) -> np.ndarray:
    """clip(forecast / prevailing mean, 0, w_max); 0 where the prevailing mean is <= 0 or a forecast is missing."""
    fm, fb = np.asarray(fm, float), np.asarray(fb, float)
    ok = np.isfinite(fm) & np.isfinite(fb) & (fb > 0)
    w = np.zeros(fm.size)
    w[ok] = np.clip(fm[ok] / fb[ok], 0.0, w_max)
    return w


def timing_excess(w, rs, rb, cal_days, cost: float = COST_REBAL, spread: float = SPREAD_LEV) -> np.ndarray:
    """Monthly excess return over bills of weight w in SPY (rest in bills; w > 1 borrows at bills + spread), minus
    ``cost`` in every month the weight changes (the first entry included)."""
    w = np.asarray(w, float)
    R = w * rs + (1.0 - w) * rb - np.maximum(w - 1.0, 0.0) * spread * np.asarray(cal_days, float) / 365.0
    ch = np.abs(np.diff(np.concatenate([[0.0], w]))) > 1e-12
    return R - cost * ch - rb


def hold_returns(days: Sequence[str], pos: np.ndarray, j_idx: np.ndarray, px_by_day: dict, B: np.ndarray) -> tuple:
    """For each month j in ``j_idx``: (SPY return, bill return, calendar days) from the close of pos[j] + 1 to the close
    of pos[j + 1] + 1 (the session after the next month-end)."""
    rs, rb, cd = [], [], []
    for j in j_idx:
        a, b = pos[j] + 1, pos[j + 1] + 1
        pa, pb = px_by_day.get(days[a]), px_by_day.get(days[b])
        rs.append(pb / pa - 1.0 if pa and pb else float("nan"))
        rb.append(B[b] / B[a] - 1.0)
        cd.append((date.fromisoformat(days[b]) - date.fromisoformat(days[a])).days)
    return np.array(rs), np.array(rb), np.array(cd, float)


def rule_family(cells: dict, rs, rb, cd, primary) -> dict:
    """Timing rules for every trial cell {key: (fm, fb)} on the same holding months; the primary's Sharpe difference
    inputs and both DSR readings' series."""
    out = {}
    for k, (fm, fb) in cells.items():
        w = timing_weights(fm, fb)
        ex = timing_excess(w, rs, rb, cd)
        bh = timing_excess(np.ones_like(w), rs, rb, cd)
        wbar = float(w.mean())
        same = timing_excess(np.full_like(w, wbar), rs, rb, cd)
        out[k] = {"w": w, "ex": ex, "bh": bh, "same": same, "active": ex - same, "wbar": wbar,
                  "sr": _ann_sr(ex), "sr_bh": _ann_sr(bh), "sr_same": _ann_sr(same)}
    return out


def dsr_two_readings(fam: dict, primary, label: str) -> tuple:
    p = fam[primary]
    n = len(fam)
    d_ex = MOM.family_dsr(p["ex"], [float(sharpe_ratio(v["ex"])) for v in fam.values()], n)
    d_ac = MOM.family_dsr(p["active"], [float(sharpe_ratio(v["active"])) for v in fam.values()], n)
    row = BW.all_constructions([dsr_row_ge(d_ex, "timing-rule excess return"),
                                dsr_row_ge(d_ac, "timing rule minus buy-and-hold at its average exposure")],
                               f"{label} DSR >= {DSR_PASS} over the {n} trials under both readings (rule 11)")
    return row, {"excess": d_ex, "active": d_ac}


# ================================================================================================== T-649 VRP ==

def vrp_frame(days: Sequence[str], close, vix: dict, har_from: str = T649_HAR_FROM, har_min: int = T649_HAR_MIN) -> dict:
    """Month-end VRP inputs on a daily price history: VIX_t, trailing 21-session sum of squared log returns ending at
    t, VRP = (VIX/100)^2/12 - RV, and the HAR(1,5,22) variant VIX^2/12 - (HAR forecast of the next 21 sessions'
    summed squared returns, fitted on days from ``har_from`` whose target ended by t)."""
    c = np.asarray(close, float)
    n = c.size
    r = np.full(n, np.nan)
    r[1:] = np.log(c[1:] / c[:-1])
    sq = np.where(np.isfinite(r), r * r, 0.0)
    cs = np.concatenate([[0.0], np.cumsum(sq)])           # cs[i + 1] = sum sq[0..i]
    pos = month_end_pos(days)
    rv = np.array([cs[i + 1] - cs[i - 20] if i >= 21 else np.nan for i in pos])
    vx = np.array([vix.get(days[i], np.nan) for i in pos], float)
    har = har_forecasts(days, sq, pos, har_from, har_min)
    v2 = (vx / 100.0) ** 2 / 12.0
    return {"pos": pos, "day": [days[i] for i in pos], "vix": vx, "rv": rv, "vrp": v2 - rv, "har": har, "vrp_har": v2 - har}


def har_forecasts(days: Sequence[str], sq: np.ndarray, pos: np.ndarray, start: str, min_obs: int) -> np.ndarray:
    """HAR(1,5,22) forecast at each month-end of the next 21 sessions' summed squared returns, OLS on every day s from
    ``start`` whose target sessions s+1..s+21 ended by the month-end (s + 21 <= t)."""
    n = sq.size
    cs = np.concatenate([[0.0], np.cumsum(sq)])
    s0 = bisect_left(list(days), start) + 22
    s = np.arange(n)
    X = np.zeros((n, 4))
    ok = (s >= s0) & (s + 21 <= n - 1)
    si = s[ok]
    X[si, 0] = 1.0
    X[si, 1] = sq[si]
    X[si, 2] = (cs[si + 1] - cs[si - 4]) / 5.0
    X[si, 3] = (cs[si + 1] - cs[si - 21]) / 22.0
    T = np.zeros(n)
    T[si] = cs[si + 22] - cs[si + 1]
    PXX = np.cumsum(X[:, :, None] * X[:, None, :], axis=0)
    PXT = np.cumsum(X * T[:, None], axis=0)
    cnt = np.cumsum(ok.astype(int))
    out = np.full(pos.size, np.nan)
    for k, i in enumerate(pos):
        last = i - 21
        if last < 0 or cnt[last] < min_obs or i < s0:
            continue
        beta = np.linalg.solve(PXX[last], PXT[last])
        x_i = np.array([1.0, sq[i], (cs[i + 1] - cs[i - 4]) / 5.0, (cs[i + 1] - cs[i - 21]) / 22.0])
        out[k] = float(x_i @ beta)
    return out


def vrp_premium_test(gdays, gclose, vix: dict, spy_adj: dict, bills: CAL.Bills, n_boot: Optional[int] = None,
                     reps: Optional[int] = None) -> dict:
    """T-649 core."""
    gdays = list(gdays)
    n = len(gdays)
    P = np.asarray(gclose, float)
    B = bill_index(gdays, bills)
    fr = vrp_frame(gdays, P, vix)
    pos = fr["pos"]
    mdays = fr["day"]
    train = np.array([d >= T649_TRAIN for d in mdays])
    oos = np.array([T649_OOS[0] <= d <= T649_OOS[1] for d in mdays])
    preds = {"vrp": fr["vrp"], "vrp_har": fr["vrp_har"], "vix": fr["vix"], "rv": fr["rv"]}
    cells, ev, tg = {}, {}, {}
    for h in T649_H:
        y, end = window_targets(pos, h, n, lambda a, e: P[e] / P[a] - 1.0 - (B[e] / B[a] - 1.0))
        tg[h] = y
        for name, x in preds.items():
            fm, fb, sl = expanding_ols(x, y, pos, end, train, oos & np.isfinite(x))
            cells[(name, h)] = (fm, fb)
            ev[(name, h)] = oos_stats(y, fm, fb, oos, max(1, h // 21))
    prim = ev[("vrp", T649_PRIMARY)]
    n_fc = prim["n"]
    # sub-periods (reported)
    y63 = tg[T649_PRIMARY]
    fm63, fb63 = cells[("vrp", T649_PRIMARY)]
    late = oos & np.array([d >= "2015-01-01" for d in mdays])
    ex20 = oos & np.array([d[:4] != "2020" for d in mdays])
    sub = {"2015-2026": oos_stats(y63, fm63, fb63, late, 3), "ex-2020": oos_stats(y63, fm63, fb63, ex20, 3)}
    # timing rules over the forecast months 2008-01..2026-06
    j_idx = np.where(oos)[0]
    j_idx = j_idx[j_idx + 1 < pos.size]
    rs, rb, cd = hold_returns(gdays, pos, j_idx, spy_adj, B)
    fam_cells = {(nm, h): (cells[(nm, h)][0][j_idx], cells[(nm, h)][1][j_idx]) for nm in ("vrp", "vrp_har") for h in T649_H}
    fam = rule_family(fam_cells, rs, rb, cd, ("vrp", T649_PRIMARY))
    P0 = fam[("vrp", T649_PRIMARY)]
    sd = _sharpe_diff(P0["ex"], P0["bh"], n_boot, reps)
    sd_row = BW._ci_crit(sd, "gt", 0.0, "Sharpe(timing rule) - Sharpe(SPY buy-and-hold) lower 95% bound > 0 (studentized "
                                      "circular block bootstrap, 12-month blocks)")
    dsr_row, dsr = dsr_two_readings(fam, ("vrp", T649_PRIMARY), "timing-rule")
    r2v, r2x, r2r = prim["oos_r2"], ev[("vix", T649_PRIMARY)]["oos_r2"], ev[("rv", T649_PRIMARY)]["oos_r2"]
    beats = None if None in (r2v, r2x, r2r) else (r2v > r2x and r2v > r2r)
    rows = [_p_crit(prim["cw_p"], prim["cw_t"], "Clark-West one-sided p < 0.05 at 63 sessions, trailing-RV VRP"),
            (f"63-session OOS R^2 > 0 (the claim: {_s(r2v, 4)})", None if r2v is None else r2v > 0, False),
            (f"VRP beats the VIX-level-only and trailing-RV-only predictors at 63 sessions (OOS R^2 {_s(r2v, 4)} vs "
             f"{_s(r2x, 4)} and {_s(r2r, 4)}; the controls' 'must beat both')", beats, False),
            sd_row, dsr_row]
    v, why, crit = CAL._judge(rows, n_fc, T649_MIN_N, "63-session forecasts")
    wv = P0["w"]
    stat = {"n_forecasts": n_fc, "cells": {f"{k[0]}_h{k[1]}": v_ for k, v_ in ev.items()}, "subperiods_63": sub,
            "sharpe_diff": {k: sd.get(k) for k in ("diff", "ci", "ci_mc_se", "sharpe_a", "sharpe_b", "reps")},
            "timing": {f"{k[0]}_h{k[1]}": {"sr": f_["sr"], "sr_bh": f_["sr_bh"], "sr_same_exposure": f_["sr_same"], "wbar": f_["wbar"]}
                       for k, f_ in fam.items()},
            "weight_primary": {"mean": float(wv.mean()), "min": float(wv.min()), "max": float(wv.max()),
                               "share_zero": float((wv == 0).mean()), "share_levered": float((wv > 1).mean())},
            "dsr": dsr, "criteria": crit, "n_hold_months": int(j_idx.size),
            "first_last_forecast": [mdays[j_idx[0]], mdays[j_idx[-1]]] if j_idx.size else None}
    cl = lambda k: ev[k]
    reason = (f"^GSPC price excess return over DTB3 from the close of t+1, expanding OLS from 1990-01 on VRP = VIX^2/12 - "
              f"trailing 21-session RV, {n_fc} month-end forecasts {mdays[j_idx[0]][:7]}..{T649_OOS[1][:7]} at 63 sessions: "
              f"OOS R^2 {_s(r2v, 4)}, Clark-West t {_s(prim['cw_t'], 2)} (p {_f(prim['cw_p'], 4)}, NW lag 3); "
              f"21/126 sessions {_s(cl(('vrp', 21))['oos_r2'], 4)} / {_s(cl(('vrp', 126))['oos_r2'], 4)} (CW p "
              f"{_f(cl(('vrp', 21))['cw_p'], 3)} / {_f(cl(('vrp', 126))['cw_p'], 3)}); HAR-RV VRP at 63 "
              f"{_s(cl(('vrp_har', 63))['oos_r2'], 4)} (p {_f(cl(('vrp_har', 63))['cw_p'], 3)}); controls at 63: VIX-only "
              f"{_s(r2x, 4)}, RV-only {_s(r2r, 4)}; SPY timing rule (mean weight {wv.mean():.2f}, flat {(wv == 0).mean():.0%} "
              f"of months) Sharpe {_s(sd.get('sharpe_a'), 2)} vs buy-and-hold {_s(sd.get('sharpe_b'), 2)}, difference "
              f"{_s(sd.get('diff'), 3)} [95% CI {_s((sd.get('ci') or [None])[0], 3)}, {_s((sd.get('ci') or [None, None])[1], 3)}]; "
              f"same-average-exposure buy-and-hold {_s(P0['sr_same'], 2)}; DSR (6 trials) excess {_f(dsr['excess']['dsr'])}, "
              f"active {_f(dsr['active']['dsr'])} (observed trial-Sharpe variance instead of the 1/(T-1) floor: "
              f"{_dsr_obs(dsr['excess'])} / {_dsr_obs(dsr['active'])}); reported 2015-2026 OOS R^2 {_s(sub['2015-2026']['oos_r2'], 4)}, ex-2020 "
              f"{_s(sub['ex-2020']['oos_r2'], 4)} (not the verdict). VIX 1990-2003 is Cboe's reconstruction; the claim's "
              f"month-end calendar has no grid phase (rule 10); VIX enters at t (21:30 UTC), positions and targets at the "
              f"close of t+1 — {why}")
    return {"stat": stat, "n": n_fc, "verdict": v, "reason": reason}


def b13_implied_b_vrp_equity_premium(archive):
    """T-649: S&P variance risk premium forecasts the 63-session ^GSPC excess return out of sample (Clark-West), and its
    SPY timing rule beats buy-and-hold on Sharpe."""
    miss = B7C._missing(archive, [VIX_B, GSPC_B, SPY_B, DTB3_B])
    if miss:
        return miss

    def run():
        gd, gc = CAL._daily(archive, GSPC_B, "close")
        sd, sa = CAL._daily(archive, SPY_B, "adjclose")
        return vrp_premium_test(gd, gc, CAL._series(archive, VIX_B), dict(zip(sd, sa)),
                                CAL.Bills(CAL._series(archive, DTB3_B)))

    rep = CAL._cached(archive, ("b13_implied_b", "T-649"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


# ================================================================================================ T-650 COR1M ==

def cor1m_premium_test(sdays, sadj, sclose, cor: dict, dspx: dict, vix: dict, bills: CAL.Bills,
                       n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """T-650 core. SPY sessions (adjclose for the target and the rule, close for the VRP control's RV)."""
    sdays = list(sdays)
    n = len(sdays)
    A = np.asarray(sadj, float)
    B = bill_index(sdays, bills)
    ex = np.zeros(n)
    ex[1:] = A[1:] / A[:-1] - 1.0 - (B[1:] / B[:-1] - 1.0)
    E = np.cumprod(1.0 + ex)                                         # compounded daily excess return
    fr = vrp_frame(sdays, sclose, vix, har_min=10 ** 9)               # VRP from SPY closes (no HAR needed)
    pos = fr["pos"]
    mdays = fr["day"]
    xcor = np.array([cor.get(d, np.nan) for d in mdays], float)
    xdsp = np.array([dspx.get(d, np.nan) for d in mdays], float)
    preds = {"cor1m": (xcor, T650_TRAIN, T650_OOS[0]), "dspx": (xdsp, T650_DSPX_TRAIN, T650_DSPX_OOS),
             "vix": (fr["vix"], T650_TRAIN, T650_OOS[0]), "vrp": (fr["vrp"], T650_TRAIN, T650_OOS[0])}
    cells, ev, tg = {}, {}, {}
    hi = np.array([d <= T650_OOS[1] for d in mdays])
    late = np.array([d >= T650_LATE for d in mdays])
    for h in T650_H:
        y, end = window_targets(pos, h, n, lambda a, e: E[e] / E[a] - 1.0)
        tg[h] = y
        lag = max(6, h // 21)
        for name, (x, tr0, oo0) in preds.items():
            train = np.array([d >= tr0 for d in mdays])
            org = np.array([d >= oo0 for d in mdays]) & hi
            fm, fb, sl = expanding_ols(x, y, pos, end, train, org, restrict=True)
            cells[(name, h)] = (fm, fb, sl, org)
            ev[(name, h)] = oos_stats(y, fm, fb, org, lag)
            ev[(name, h)]["late"] = oos_stats(y, fm, fb, org & late, lag)
            ev[(name, h)]["share_slope_pos"] = float(np.mean(sl[org & np.isfinite(sl)] > 0)) if np.isfinite(sl[org]).any() else None
            ev[(name, h)]["missing_x_months"] = int((org & ~np.isfinite(x)).sum())
    prim = ev[("cor1m", T650_PRIMARY)]
    n_fc = prim["n"]
    fmc, fbc, _, orgc = cells[("cor1m", T650_PRIMARY)]
    fmv = cells[("vrp", T650_PRIMARY)][0]
    enc = encompassing(tg[T650_PRIMARY], fmv, fmc, orgc, 6)
    # timing rules (reported; the DSR's series)
    fam = {}
    rs_all = {}
    for name in ("cor1m", "dspx"):
        org = cells[(name, T650_PRIMARY)][3]
        j_idx = np.where(org)[0]
        j_idx = j_idx[j_idx + 1 < pos.size]
        rs, rb, cd = hold_returns(sdays, pos, j_idx, dict(zip(sdays, A)), B)
        rs_all[name] = (j_idx, rs, rb, cd)
    j_c, rs, rb, cd = rs_all["cor1m"]
    fam_c = rule_family({(nm, h): (cells[(nm, h)][0][rs_all[nm][0]], cells[(nm, h)][1][rs_all[nm][0]])
                         for nm in ("cor1m",) for h in T650_H}, rs, rb, cd, ("cor1m", T650_PRIMARY))
    j_d, rs_d, rb_d, cd_d = rs_all["dspx"]
    fam_d = rule_family({("dspx", h): (cells[("dspx", h)][0][j_d], cells[("dspx", h)][1][j_d]) for h in T650_H},
                        rs_d, rb_d, cd_d, ("dspx", T650_PRIMARY))
    fam = {**fam_c, **fam_d}
    P0 = fam[("cor1m", T650_PRIMARY)]
    sd = _sharpe_diff(P0["ex"], P0["bh"], n_boot, reps)
    dsr_row, dsr = dsr_two_readings(fam, ("cor1m", T650_PRIMARY), "COR1M-126 timing-rule")
    r2 = prim["oos_r2"]
    r2_late = prim["late"]["oos_r2"]
    rows = [_p_crit(prim["cw_p"], prim["cw_t"], "Clark-West one-sided p < 0.05 at 126 sessions for COR1M (NW lag 6 months)"),
            (f"OOS R^2 > 0 over 2013-01..2026-03 at 126 sessions (the claim: {_s(r2, 4)})", None if r2 is None else r2 > 0, False),
            (f"OOS R^2 > 0 over 2019-01..2026-03 at 126 sessions ({_s(r2_late, 4)}, {prim['late']['n']} forecasts)",
             None if r2_late is None else r2_late > 0, False),
            dsr_row]
    v, why, crit = CAL._judge(rows, n_fc, T650_MIN_N, "126-session forecasts")
    incr = enc["p"] is not None and enc["p"] < ALPHA
    stat = {"n_forecasts": n_fc, "cells": {f"{k[0]}_h{k[1]}": v_ for k, v_ in ev.items()},
            "encompassing_vs_vrp": enc, "incremental_to_vrp_recorded": bool(incr and v == "supported"),
            "sharpe_diff": {k: sd.get(k) for k in ("diff", "ci", "ci_mc_se", "sharpe_a", "sharpe_b", "reps")},
            "timing": {f"{k[0]}_h{k[1]}": {"sr": f_["sr"], "sr_bh": f_["sr_bh"], "sr_same_exposure": f_["sr_same"], "wbar": f_["wbar"]}
                       for k, f_ in fam.items()},
            "dsr": dsr, "criteria": crit}
    c = lambda k: ev[k]
    reason = (f"SPY adjclose excess over DTB3 compounded from the close of t+1, expanding OLS from 2006-01 on the month-end "
              f"COR1M close with the Campbell-Thompson slope restriction, {n_fc} forecasts 2013-01..2026-03 at 126 sessions: "
              f"OOS R^2 {_s(r2, 4)}, Clark-West t {_s(prim['cw_t'], 2)} (p {_f(prim['cw_p'], 4)}); 2019-01..2026-03 OOS R^2 "
              f"{_s(r2_late, 4)}; 63/252 sessions {_s(c(('cor1m', 63))['oos_r2'], 4)} / {_s(c(('cor1m', 252))['oos_r2'], 4)} "
              f"(CW p {_f(c(('cor1m', 63))['cw_p'], 3)} / {_f(c(('cor1m', 252))['cw_p'], 3)}); fitted slope positive in "
              f"{_share(prim['share_slope_pos'])} of fits; DSPX (from 2017-01) at 126 "
              f"{_s(c(('dspx', 126))['oos_r2'], 4)} (p {_f(c(('dspx', 126))['cw_p'], 3)}); controls at 126: VIX "
              f"{_s(c(('vix', 126))['oos_r2'], 4)}, VRP {_s(c(('vrp', 126))['oos_r2'], 4)}; HLN encompassing vs the "
              f"VRP-only forecast t {_s(enc['t'], 2)} (p {_f(enc['p'], 3)}: 'incremental to VRP' "
              f"{'would be' if incr else 'is not'} recordable); timing rule Sharpe {_s(sd.get('sharpe_a'), 2)} vs "
              f"buy-and-hold {_s(sd.get('sharpe_b'), 2)} (difference {_s(sd.get('diff'), 3)}, 95% CI "
              f"{_s((sd.get('ci') or [None])[0], 3)}..{_s((sd.get('ci') or [None, None])[1], 3)}, reported); DSR (6 trials) "
              f"excess {_f(dsr['excess']['dsr'])}, active {_f(dsr['active']['dsr'])} (observed trial-Sharpe variance: "
              f"{_dsr_obs(dsr['excess'])} / {_dsr_obs(dsr['active'])}). COR1M is Cboe's definition with its "
              f"pre-launch backfill; month-end calendar, no grid phase (rule 10); COR1M enters at t (21:30 UTC), targets "
              f"and positions at the close of t+1 — {why}")
    return {"stat": stat, "n": n_fc, "verdict": v, "reason": reason}


def b13_implied_b_cor1m_equity_premium(archive):
    """T-650: Cboe COR1M forecasts the 126-session SPY excess return out of sample (Clark-West, 2019+ OOS R^2 > 0)."""
    miss = B7C._missing(archive, [COR1M_B, DSPX_B, VIX_B, SPY_B, DTB3_B])
    if miss:
        return miss

    def run():
        sd, sa = CAL._daily(archive, SPY_B, "adjclose")
        _, sc = CAL._daily(archive, SPY_B, "close")
        return cor1m_premium_test(sd, sa, sc, CAL._series(archive, COR1M_B), CAL._series(archive, DSPX_B),
                                  CAL._series(archive, VIX_B), CAL.Bills(CAL._series(archive, DTB3_B)))

    rep = CAL._cached(archive, ("b13_implied_b", "T-650"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


# ================================================================================================ T-653 PC2 ==

def curve_pcs(days: Sequence[str], logs: np.ndarray, min_pca: int = T653_MIN_PCA) -> dict:
    """Point-in-time PC1 / PC2 of the standardised columns of ``logs`` (n x 4, ordered VIX9D, VIX, VIX3M, VIX6M):
    mean, s.d. and correlation matrix on the expanding window from the first row through t; PC2's sign fixed so that
    loading(VIX6M) - loading(VIX9D) > 0, PC1's so that its loadings sum > 0. Defined once the window holds
    ``min_pca`` rows."""
    X = np.asarray(logs, float)
    n, k = X.shape
    cnt = np.arange(1, n + 1, dtype=float)
    S1 = np.cumsum(X, axis=0)
    S2 = np.cumsum(X[:, :, None] * X[:, None, :], axis=0)
    mu = S1 / cnt[:, None]
    valid = cnt >= max(min_pca, 3)
    pc1, pc2 = np.full(n, np.nan), np.full(n, np.nan)
    load2 = np.full((n, k), np.nan)
    if valid.any():
        iv = np.where(valid)[0]
        c = cnt[iv]
        cov = (S2[iv] - c[:, None, None] * mu[iv][:, :, None] * mu[iv][:, None, :]) / (c - 1)[:, None, None]
        sd = np.sqrt(np.maximum(np.einsum("nii->ni", cov), 1e-300))
        corr = cov / (sd[:, :, None] * sd[:, None, :])
        _, vecs = np.linalg.eigh(corr)
        v1, v2 = vecs[:, :, -1], vecs[:, :, -2]
        s2 = np.where(v2[:, -1] - v2[:, 0] >= 0, 1.0, -1.0)
        s1 = np.where(v1.sum(axis=1) >= 0, 1.0, -1.0)
        v1, v2 = v1 * s1[:, None], v2 * s2[:, None]
        z = (X[iv] - mu[iv]) / sd
        pc1[iv], pc2[iv] = (z * v1).sum(axis=1), (z * v2).sum(axis=1)
        load2[iv] = v2
    return {"pc1": pc1, "pc2": pc2, "valid": valid, "load2": load2}


def expanding_quintiles(days: Sequence[str], x, valid, start: str, end: str, min_hist: int = T653_MIN_HIST) -> np.ndarray:
    """Quintile 1..5 of x[t] against the cutoffs (20/40/60/80th percentiles) of the valid values on days before t;
    0 where undefined (outside start..end, x[t] not valid, or fewer than ``min_hist`` earlier values)."""
    x = np.asarray(x, float)
    ok = np.asarray(valid, bool) & np.isfinite(x)
    hist = x[ok]
    before = np.concatenate([[0], np.cumsum(ok)[:-1]])            # valid values strictly before t
    q = np.zeros(x.size, int)
    for i in range(x.size):
        if not ok[i] or before[i] < min_hist or not (start <= days[i] <= end):
            continue
        cuts = np.quantile(hist[:before[i]], [0.2, 0.4, 0.6, 0.8])
        q[i] = 1 + int(np.searchsorted(cuts, x[i], side="right"))
    return q


def cm_vx_daily(curve: dict, target: int = T653_CM_DAYS) -> dict:
    """Daily-rebalanced constant-maturity VX: for each settle day d_k (all but the last), the weights on F1 / F2 (first
    two expiries strictly after d_k; w1 = clip((tau2 - target) / (tau2 - tau1), 0, 1), calendar days), the
    interpolated level at d_k, and the return / $ change (x 1,000) of that fixed-weight pair to the next settle d_{k+1}."""
    days = sorted(curve)
    m = len(days)
    ret, dol, lvl, w1s = np.full(m, np.nan), np.full(m, np.nan), np.full(m, np.nan), np.full(m, np.nan)
    for k in range(m):
        d0 = days[k]
        ex = sorted(e for e in curve[d0] if e > d0)[:2]
        if len(ex) < 2:
            continue
        e1, e2 = ex
        t0 = date.fromisoformat(d0)
        t1, t2 = (date.fromisoformat(e1) - t0).days, (date.fromisoformat(e2) - t0).days
        w1 = float(np.clip((t2 - target) / (t2 - t1), 0.0, 1.0))
        p0 = w1 * curve[d0][e1] + (1 - w1) * curve[d0][e2]
        lvl[k], w1s[k] = p0, w1
        if k + 1 < m:
            d1 = days[k + 1]
            if e1 in curve[d1] and e2 in curve[d1]:
                p1 = w1 * curve[d1][e1] + (1 - w1) * curve[d1][e2]
                ret[k], dol[k] = p1 / p0 - 1.0, T653_VX_MULT * (p1 - p0)
    return {"days": days, "ret": ret, "dollar": dol, "level": lvl, "w1": w1s}


def forward_returns(sig_days: Sequence[str], tdays: Sequence[str], step_ret: np.ndarray, hold: int = T653_HOLD) -> np.ndarray:
    """For each signal day t: the compounded return over ``hold`` steps starting at the first target day strictly after
    t (step k runs from tdays[k] to tdays[k + 1]); NaN when the window runs past the data or a step is missing."""
    g = np.where(np.isfinite(step_ret), 1.0 + step_ret, np.nan)
    lg = np.concatenate([[0.0], np.cumsum(np.log(np.where(np.isfinite(g), g, 1.0)))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(g))])
    out = np.full(len(sig_days), np.nan)
    for i, d in enumerate(sig_days):
        k1 = bisect_right(tdays, d)
        k2 = k1 + hold
        if k2 <= len(step_ret) and bad[k2] - bad[k1] == 0:
            out[i] = math.exp(lg[k2] - lg[k1]) - 1.0
    return out


def spread_test(y, q, mask, lag: int = T653_LAG) -> dict:
    """Lowest-minus-highest quintile mean of y on the masked days, with the Newey-West t of the contrast series."""
    y, q = np.asarray(y, float), np.asarray(q, int)
    m = np.asarray(mask, bool) & np.isfinite(y) & (q > 0)
    out = {"n": int(m.sum()), "spread": None, "t": None, "p": None, "quintile_means": None}
    a, b = (q[m] == 1), (q[m] == 5)
    if a.sum() < 2 or b.sum() < 2:
        return out
    d = CAL.contrast_series(y[m], a, b)
    nw = nw_mean(d, lag)
    out.update(spread=nw["mean"], t=nw["t"], p=float(1.0 - _N.cdf(nw["t"])) if math.isfinite(nw["t"]) else None,
               quintile_means=[float(y[m][q[m] == k].mean()) if (q[m] == k).any() else None for k in range(1, 6)],
               n_q1=int(a.sum()), n_q5=int(b.sum()))
    return out


def slope_test(y, pc2, ts, lv, mask, lag: int = T653_LAG) -> dict:
    """y on [1, PC2, log(VIX/VIX3M), log VIX] with Newey-West t; one-sided p of a negative PC2 slope."""
    y = np.asarray(y, float)
    m = np.asarray(mask, bool) & np.isfinite(y) & np.isfinite(pc2) & np.isfinite(ts) & np.isfinite(lv)
    if m.sum() < 20:
        return {"n": int(m.sum()), "b": None, "t": None, "p": None}
    X = np.column_stack([np.ones(m.sum()), np.asarray(pc2)[m], np.asarray(ts)[m], np.asarray(lv)[m]])
    r = ols_nw_multi(y[m], X, lag)
    t = float(r["t"][1])
    u = ols_nw_multi(y[m], X[:, :2], lag)
    return {"n": int(m.sum()), "b": float(r["beta"][1]), "t": t, "p": float(_N.cdf(t)),
            "b_ratio": float(r["beta"][2]), "t_ratio": float(r["t"][2]), "b_logvix": float(r["beta"][3]),
            "t_logvix": float(r["t"][3]), "b_alone": float(u["beta"][1]), "t_alone": float(u["t"][1])}


def gated_short_vx(cm: dict, sig_days: Sequence[str], gate, lo: str, hi: str) -> dict:
    """Daily $ P&L of short 1 CM VX contract-equivalent over [settle k, settle k+1] when the gate at the last signal day
    strictly before settle k is on (gated) and always (always), $70 a side; intervals with settle k in lo..hi."""
    days, dol = cm["days"], cm["dollar"]
    gate = np.asarray(gate, bool)
    idx = [k for k in range(len(days)) if lo <= days[k] <= hi and np.isfinite(dol[k])]
    pos_g = np.zeros(len(idx))
    for j, k in enumerate(idx):
        i = bisect_left(sig_days, days[k]) - 1
        pos_g[j] = 1.0 if i >= 0 and gate[i] else 0.0
    pnl = -np.array([dol[k] for k in idx])
    sw = np.abs(np.diff(np.concatenate([[0.0], pos_g, [0.0]])))
    g = pos_g * pnl - T653_VX_SIDE * sw[:-1]
    g[-1:] -= T653_VX_SIDE * sw[-1]
    a = pnl.copy()
    if a.size:
        a[0] -= T653_VX_SIDE
        a[-1] -= T653_VX_SIDE
    return {"gated": g, "always": a, "share_on": float(pos_g.mean()) if pos_g.size else None,
            "switches": int(sw.sum()), "days": [days[k] for k in idx]}


def gated_long_etp(edays: Sequence[str], eadj, sig_days: Sequence[str], gate, lo: str, hi: str) -> dict:
    """Long SVXY over [close k, close k+1] when the gate at the last signal day strictly before close k is on, 2.5 bp a
    side (5 bp per round trip), flat days 0; versus always long."""
    A = np.asarray(eadj, float)
    gate = np.asarray(gate, bool)
    idx = [k for k in range(len(edays) - 1) if lo <= edays[k] <= hi]
    r = np.array([A[k + 1] / A[k] - 1.0 for k in idx])
    on = np.array([1.0 if (bisect_left(sig_days, edays[k]) - 1) >= 0 and gate[bisect_left(sig_days, edays[k]) - 1] else 0.0
                   for k in idx])
    sw = np.abs(np.diff(np.concatenate([[0.0], on, [0.0]])))
    g = on * r - T653_ETP_SIDE * sw[:-1]
    if g.size:
        g[-1] -= T653_ETP_SIDE * sw[-1]
    return {"gated": g, "always": r, "share_on": float(on.mean()) if on.size else None}


def _sr_d(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, 252)) if x.size > 2 and x.std() > 0 else None


def vix_curve_test(idx: dict, curve: dict, vxx: tuple, svxy: tuple) -> dict:
    """T-653 core. idx: {tenor: {day: close}}; curve: {day: {expiry: settle}}; vxx / svxy: (days, adjclose)."""
    common = sorted(d for d in set.intersection(*(set(idx[t]) for t in TENORS)) if d >= T653_PCA_FROM
                    and all(idx[t][d] > 0 for t in TENORS))
    L = np.log(np.array([[idx[t][d] for t in TENORS] for d in common], float))
    pcs = curve_pcs(common, L)
    pc2, pc1, valid = pcs["pc2"], pcs["pc1"], pcs["valid"]
    q = expanding_quintiles(common, pc2, valid, T653_START, T653_END)
    ts = L[:, 1] - L[:, 2]                                        # log(VIX / VIX3M)
    lv = L[:, 1]
    cm = cm_vx_daily(curve)
    y1 = forward_returns(common, cm["days"], cm["ret"])
    lvl = cm["level"]
    lvl_step = np.full(len(cm["days"]), np.nan)
    lvl_step[:-1] = lvl[1:] / lvl[:-1] - 1.0
    y1_level = forward_returns(common, cm["days"], lvl_step)
    vd, va = vxx
    vstep = np.asarray(va[1:], float) / np.asarray(va[:-1], float) - 1.0
    y2 = forward_returns(common, list(vd), np.concatenate([vstep, [np.nan]]))
    inw = lambda lo, hi: np.array([lo <= d <= hi for d in common])
    conf, disc = inw(*T653_CONF), inw(*T653_DISC)
    full = inw(T653_START, T653_END)
    sp = {"i": spread_test(y1, q, conf), "ii": spread_test(y2, q, conf)}
    sl = {"i": slope_test(y1, pc2, ts, lv, conf & (q > 0)), "ii": slope_test(y2, pc2, ts, lv, conf & (q > 0))}
    padj = {k: (None if sp[k]["p"] is None else min(1.0, 2 * sp[k]["p"])) for k in sp}
    sadj = {k: (None if sl[k]["p"] is None else min(1.0, 2 * sl[k]["p"])) for k in sl}
    ok1 = {k: (None if padj[k] is None else bool(sp[k]["spread"] > 0 and padj[k] < ALPHA)) for k in sp}
    ok2 = {k: (None if sadj[k] is None else bool(sl[k]["b"] < 0 and sadj[k] < ALPHA)) for k in sl}
    n = sp["i"]["n"]
    # criterion 1
    if all(v is None for v in ok1.values()):
        r1 = ("confirmation spread > 0 with Bonferroni one-sided p < 0.05 for (i) or (ii) (n/a)", None, False)
    else:
        dec1 = all(sp[k]["t"] is not None and _N.cdf(sp[k]["t"]) * 2 < ALPHA for k in sp)
        r1 = (f"confirmation lowest-minus-highest PC2 quintile mean > 0 with Bonferroni one-sided p < 0.05 for (i) or (ii) "
              f"((i) CM VX {_pc(sp['i']['spread'])}, t {_s(sp['i']['t'], 2)}, adj p {_f(padj['i'], 4)}; "
              f"(ii) VXX {_pc(sp['ii']['spread'])}, t {_s(sp['ii']['t'], 2)}, adj p {_f(padj['ii'], 4)})",
              any(v is True for v in ok1.values()), dec1)
    # criterion 2: on a target whose spread passes (any target when none passes)
    cand = [k for k in ok1 if ok1[k]] or list(ok1)
    vals = [ok2[k] for k in cand if ok2[k] is not None]
    dec2 = all(sl[k]["t"] is not None and (1.0 - _N.cdf(sl[k]["t"])) * 2 < ALPHA for k in cand)
    r2 = (f"PC2 slope < 0 with Bonferroni one-sided p < 0.05 controlling for log(VIX/VIX3M) and log VIX, on a target "
          f"passing the spread ((i) b {_s(sl['i']['b'], 4)}, t {_s(sl['i']['t'], 2)}, adj p {_f(sadj['i'], 4)}; (ii) b "
          f"{_s(sl['ii']['b'], 4)}, t {_s(sl['ii']['t'], 2)}, adj p {_f(sadj['ii'], 4)})", (any(vals) if vals else None), dec2)
    # trading form on the confirmation window
    gate = q >= 4
    tf = gated_short_vx(cm, common, gate, *T653_CONF)
    (rg, ig) = dsr_vs_uncomputed_family(tf["gated"], T653_FAMILY, "gated short CM VX daily P&L")
    (ra, ia) = dsr_vs_uncomputed_family(tf["gated"] - tf["always"], T653_FAMILY, "gated minus always-short")
    r3 = BW.all_constructions([rg, ra], f"trading-form DSR >= {DSR_PASS} over the {T653_FAMILY}-trial VX family (rule 11)")
    tf_full = gated_short_vx(cm, common, gate, T653_START, T653_END)
    sv = gated_long_etp(list(svxy[0]), svxy[1], common, gate, *T653_CONF)
    rows = [r1, r2, r3]
    v, why, crit = CAL._judge(rows, n, T653_MIN_N, "confirmation days (target i)")
    # controls and reported readings
    rng = np.random.default_rng(SEED)
    qr = np.where(q > 0, rng.integers(1, 6, size=q.size), 0)
    ctrl = {"log_VIX3M_over_VIX": spread_test(y1, expanding_quintiles(common, -ts, valid, T653_START, T653_END), conf),
            "log_VIX": spread_test(y1, expanding_quintiles(common, lv, valid, T653_START, T653_END), conf),
            "PC1": spread_test(y1, expanding_quintiles(common, pc1, valid, T653_START, T653_END), conf),
            "random_placebo": spread_test(y1, qr, conf)}
    rep = {"discovery_i": spread_test(y1, q, disc), "full_i": spread_test(y1, q, full),
           "level_change_i_conf": spread_test(y1_level, q, conf),
           "slope_discovery_i": slope_test(y1, pc2, ts, lv, disc & (q > 0))}
    lc = pcs["load2"][np.where(np.array(common) <= T653_CONF[1])[0][-1]]
    stat = {"n_conf_i": n, "spread": sp, "spread_p_bonf": padj, "slope": sl, "slope_p_bonf": sadj, "controls": ctrl,
            "reported": rep, "trading": {"share_on": tf["share_on"], "switches": tf["switches"], "sr_gated": _sr_d(tf["gated"]),
                                          "sr_always": _sr_d(tf["always"]), "mean_gated_usd": float(tf["gated"].mean()),
                                          "mean_always_usd": float(tf["always"].mean()), "dsr_gated": ig, "dsr_active": ia,
                                          "full_sr_gated": _sr_d(tf_full["gated"]), "full_sr_always": _sr_d(tf_full["always"]),
                                          "svxy_sr_gated": _sr_d(sv["gated"]), "svxy_sr_always": _sr_d(sv["always"])},
            "pc2_loadings_last": {t: float(x) for t, x in zip(TENORS, lc)}, "first_signal_day": common[int(np.argmax(q > 0))],
            "criteria": crit}
    reason = (f"PC2 of standardised log VIX9D/VIX/VIX3M/VIX6M (expanding from {common[0]}, sign VIX6M - VIX9D > 0; last "
              f"loadings {', '.join(f'{t} {x:+.2f}' for t, x in zip(TENORS, lc))}), quintiles from earlier days' PC2, "
              f"confirmation 2019-01..2026-10 ({n} days, target i): 5-day CM VX return from the t+1 settle, Q1 "
              f"{_pc((sp['i']['quintile_means'] or [None] * 5)[0])} vs Q5 {_pc((sp['i']['quintile_means'] or [None] * 5)[4])}, "
              f"spread {_pc(sp['i']['spread'])} (NW t {_s(sp['i']['t'], 2)}); VXX "
              f"{_pc(sp['ii']['spread'])} (t {_s(sp['ii']['t'], 2)}); PC2 slope given log(VIX/VIX3M), log VIX: "
              f"(i) t {_s(sl['i']['t'], 2)}, (ii) t {_s(sl['ii']['t'], 2)}; discovery 2013-05..2018-12 (i) spread "
              f"{_pc(rep['discovery_i']['spread'])} (t {_s(rep['discovery_i']['t'], 2)}); controls (i) Q1-Q5: "
              f"log(VIX3M/VIX) {_pc(ctrl['log_VIX3M_over_VIX']['spread'])}, log VIX "
              f"{_pc(ctrl['log_VIX']['spread'])}, PC1 {_pc(ctrl['PC1']['spread'])}, random "
              f"{_pc(ctrl['random_placebo']['spread'])}; trading form (short CM VX in Q4-Q5, on "
              f"{_share(tf['share_on'])} of days, $140 per round trip) daily Sharpe x sqrt(252) "
              f"{_s(_sr_d(tf['gated']), 2)} vs always-short {_s(_sr_d(tf['always']), 2)}; SVXY mirror {_s(_sr_d(sv['gated']), 2)} "
              f"vs {_s(_sr_d(sv['always']), 2)} (reported). Every day is a signal day (overlapping 5-day windows pooled, NW lag 5; "
              f"the gate is daily), so there is no grid phase (rule 10). Four-tenor curve, not Johnson's SPX curve; index closes at 16:15 ET "
              f"enter at t, every return starts at the t+1 settle / close — {why}")
    return {"stat": stat, "n": n, "verdict": v, "reason": reason}


def b13_implied_b_vix_curve_pc2(archive):
    """T-653: the second principal component of the VIX9D/VIX/VIX3M/VIX6M curve predicts 5-day CM VX / VXX returns
    (lowest-minus-highest quintile > 0, negative slope given VIX/VIX3M and VIX)."""
    miss = B7C._missing(archive, [VIX9D_B, VIX_B, VIX3M_B, VIX6M_B, VX_B, VXX_B, SVXY_B])
    if miss:
        return miss

    def run():
        idx = {t: CAL._series(archive, b) for t, b in zip(TENORS, (VIX9D_B, VIX_B, VIX3M_B, VIX6M_B))}
        curve = vx_curve(CAL._rows(archive, VX_B))
        vxx = _etp(archive, VXX_B)
        svxy = _etp(archive, SVXY_B)
        return vix_curve_test(idx, curve, vxx, svxy)

    rep = CAL._cached(archive, ("b13_implied_b", "T-653"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


def _etp(archive, name: str) -> tuple:
    """(days, adjclose) of a Yahoo ETP history with zero-volume (stale) bars dropped."""
    from datetime import datetime, timezone
    by = {}
    for r in CAL._rows(archive, name):
        v = r["value"]
        if not v.get("volume"):
            continue
        c = v.get("adjclose") if v.get("adjclose") is not None else v.get("close")
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if c > 0 and math.isfinite(c):
            by[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = c
    ds = sorted(by)
    return ds, np.array([by[d] for d in ds], float)


HARNESSES = {"b13_implied_b_vrp_equity_premium": b13_implied_b_vrp_equity_premium,
             "b13_implied_b_cor1m_equity_premium": b13_implied_b_cor1m_equity_premium,
             "b13_implied_b_vix_curve_pc2": b13_implied_b_vix_curve_pc2}
THEORY_MAP = {"T-649": "b13_implied_b_vrp_equity_premium", "T-650": "b13_implied_b_cor1m_equity_premium",
              "T-653": "b13_implied_b_vix_curve_pc2"}
