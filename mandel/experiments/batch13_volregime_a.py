"""
Batch 13, group ``volregime_a``: four volatility-regime claims from the 2026-10-20 web sweep (cluster "volregime").
=================================================================================================================

  * T-679  SPY volatility targeting, monthly, real time and after costs (Moreira-Muir / Harvey et al.). At the last
           close of month t, sigma_t = sqrt(252) x the sd of the 21 daily SPY excess returns ending at that close;
           w_t = min(1.5, 0.15 / sigma_t), filled at the next session's close, the rest in bills, leverage financed at
           the bill + 50 bp, 2 bp per unit of turnover |w_target - w_drifted|. Hold months 2000-01..2026-09 (fill to
           fill). Pass: Sharpe(managed) - Sharpe(buy-and-hold) on monthly excess returns, lower 95% bound > 0 (paired
           studentized circular block bootstrap, 12-month blocks, 10,000 draws per seed); the 2015-01..2026-09 point
           estimate > 0; DSR > 0.95 over 40 trials (the 18 declared here + T-310's 20 + T-562's 2). min_n 300 months.
  * T-681  Volatility-scaled UMD after Barroso-Santa-Clara's sample. French daily Mom; at month-end t, sigma_t =
           realised volatility of the 126 daily returns through t (sqrt(252 x mean r^2)); w_t = min(2, 0.12 / sigma_t)
           applied to month t+1's compounded return, 20 bp per unit |w_t - w_{t-1}|. Hold months 2012-01..2026-08.
           Pass: Sharpe-difference lower 95% bound > 0 (paired studentized CBB, 12-month blocks), the scaled
           annualised net mean > 0, DSR > 0.95 over 62 trials (T-311's 24, T-446's 34, the 4 variants here). min_n 170.
  * T-684  Statistical jump model de-risking of SPY (Shu-Yu-Mulvey 2024). Features from ^GSPC price returns minus the
           DTB3 accrual from 1970: EWM downside deviation (half-life 10) and EWM Sortino ratios (half-lives 20, 60),
           standardised on the training window; a two-state jump model (loss 0.5 ||x - theta||^2 plus lambda per
           switch, coordinate descent, 10 k-means++ starts, lowest objective kept) trained on the prior 3,000 sessions
           and refitted every six months (first sessions of January and July); the state at t from a forward pass over
           the trailing 3,000 sessions ending at t (the last state of that window's optimal path, never a smoothed
           path); lambda re-chosen at the start of every month as the grid value with the best Sharpe of the 0/1 rule
           over the preceding 8 years (^GSPC excess, same delay, 10 bp per switch). Live: SPY adjclose when the state
           at t is the good one, bills otherwise, traded at the close of t+1, 10 bp per one-way switch. Pass over
           1994-01..2026-09 (daily): Sharpe-difference lower 95% bound > 0 (paired studentized CBB, 63-day blocks);
           the 2015-01..2026-09 point estimate > 0; DSR > 0.95 over 101 trials (delays t+1 / t+5, T-561's 1, T-562's
           2, T-301's 96). min_n 6000 days.
  * T-685  The variance risk premium VRP_t = (VIX_t/100)^2/12 - sum of squared daily ^GSPC log returns over the 21
           sessions ending at month-end t predicts the SPY excess log return over the 63 sessions from the next
           session's close. Decisions 2010-01..2026-06. Pass: slope on standardised VRP > 0 with one-sided Hodrick
           (1992) p < 0.05; expanding-window OOS R^2 against the prevailing mean > 0 with one-sided Clark-West p < 0.05
           (HAC). min_n 190 decisions.

Readings fixed before any run (each registration is silent or ambiguous on these; the conservative reading is taken
and repeated in the harness reasons):
  * Bills (house rule 7, the registrations' "bond-equivalent, prior print", as T-373): DTB3 converted to the
    investment yield i = 365 d / (360 - 91 d), compounded daily at i/365 over calendar days, each day at the print
    dated strictly before it (``batch6c_rates.Accrual(conv="bey")``).
  * "Lower 95% bound" of a Sharpe difference or mean = the lower end of the two-sided 95% interval (the house
    convention, stricter than a one-sided 95% bound); interval ends are averaged over 5 bootstrap seeds and escalated
    to 25 seeds when Monte Carlo error cannot resolve them (``batch6b_bw.mc_escalate``).
  * DSR (T-679, T-681, T-684): "DSR of the strategy" can mean its own excess series or its timing component, so both
    are judged and the criterion passes only when both pass (rule 11 spirit, as T-373 and T-649): (a) the strategy's
    excess return; (b) the strategy minus the same asset held at the strategy's own average exposure. Trial-Sharpe
    variance = the computed trials' observed variance floored at 1/(T-1) (``batch6c_mom.family_dsr``); the counted
    trials that are other theories' (T-310, T-562, T-311, T-446, T-561, T-301) enter only the trial count.
  * T-679: hold month = fill (first session of month M) to the next fill, labelled M; buy-and-hold uses the same
    fills. Turnover uses the weight drifted since the last fill. The Moreira-Muir trial's constant c_t = sd(f) /
    sd(f / RV21) over the hold months completed by the decision close (at least 24; before that the trial holds 1x),
    so the managed series matches buy-and-hold's volatility on data through t. The VIX trial uses the VIX close of
    the decision day (16:15 ET, archived 21:30 UTC), filled at the next close; a missing print falls back to the last
    earlier one. Weekly trials decide at the last session of each ISO week and are scored on the same monthly
    fill-to-fill grid. The minimum detectable Sharpe difference at 80% power, (1.96 + 0.84) x the bootstrap SE (sd of
    the resampled difference, the same 12-month-block resamples), is computed and printed before the result.
  * T-681: realised volatility = sqrt(252 x mean of squared daily returns) over the window (BSC's estimator, no
    demeaning). Rule 12: the French factor for day t is archived at 21:00 UTC, after the month-end close the weight
    trades at, so the claim (126 returns through t, the live proxy) is read together with the previous-close reading
    (126 returns through t-1); every criterion needs both. The registration's pass says "the scaled annualised net
    mean > 0" and its null "scaled net mean <= 0": read as a test, the lower 95% bound of the net mean > 0 (the
    stricter reading; the point estimate is reported). UMD is a zero-investment return, so no bill is subtracted
    (fred-DTB3, in the data list, is probed but not used). The first scaled month pays the cost of entering from 0.
  * T-684: the registration declares no penalty grid, so the grid is fixed here before any run: lambda in {0, 5, 10,
    15, 25, 35, 50, 70, 100, 150} (the paper's illustrated values 0, 5, 15, 35, 70, 150 and its example 50, plus 10,
    25, 100). Downside deviation = sqrt(EWM of min(r, 0)^2) (the Sortino ratio's denominator; no log transform, none
    registered); EWM weights are pandas' adjust=True form with alpha = 1 - 0.5^(1/half-life); features are used
    after a 60-session warm-up. Good state = the state with the higher cumulative excess return over its training
    window; a fit whose training path uses one state only is a one-regime model (always invested). Validation runs
    on ^GSPC price excess returns (SPY starts 1993), with the trial's own delay and 10 bp per switch; ties go to the
    smaller lambda. The state at t uses lambda chosen at the start of t's month (data through the previous month);
    the position for the return of session u is the good flag at u - 2 (t+1 fill) or u - 6 (t+5). Costs are charged
    on the first return at the new position.
  * T-685: SPY starts 1993-01-29, so "expanding OLS fitted from 1990-02" cannot use SPY targets before 1993-01. Two
    readings are judged and the OOS criteria need both (rule 11 spirit): (a) SPY-only, the fit starting with the
    1993-01 decision; (b) spliced, the ^GSPC price excess target for the 1990-02..1992-12 decisions (dividends
    missing there). The OOS R^2 is unrestricted (Campbell-Thompson's slope / sign restrictions are not registered;
    the restricted one is reported). Clark-West uses a Newey-West lag of 3 months (63 sessions). Hodrick (1992) 1B
    standard errors are computed exactly for the session-defined windows: under the null the 63-session target is a
    sum of daily excess log returns u_s, so X'e = sum_s u_s q_s with q_s the sum of the regressors of every decision
    whose window holds session s, and V = (X'X)^-1 [sum_s u_s^2 q_s q_s'] (X'X)^-1. The VRP is standardised over the
    regression sample (sign and t are unchanged by it). A month whose VIX print is missing is skipped.
  * Rule 10: every claim names its calendar (month-ends, ISO week-ends, or a daily state), so there is no free grid
    phase. Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from datetime import date, datetime, timezone
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch6c_rates as RATES
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch13_implied_b as IMP
from mandel.experiments import hmm_states as MK
from mandel.experiments.batch6_surf import _out
from mandel.validation.backtest_eval import sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()
Z975, Z80 = 1.959964, 0.841621

SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
VIX_B = "cboe-VIX-history"
DTB3_B = "fred-DTB3"
FF3_B = "french-ff3-daily"
MOM_B = "french-momentum-daily"
UMC_B = "alfred-UMCSENT"

# T-679
T679_WIN = ("2000-01", "2026-09")
T679_LATE = "2015-01"
T679_TARGET = 0.15
T679_CAP = 1.5
T679_COST = 2e-4
T679_SPREAD = 0.005
T679_RV = 21
T679_MM_MIN = 24
T679_NBOOT = 10000
T679_BLOCK = 12
T679_MIN_N = 300
T679_TRIALS = 40
T679_SCALERS = ("rv", "mm", "vix")
T679_CAPS = (1.0, 1.5, 2.0)
T679_FREQS = ("monthly", "weekly")
T679_PRIMARY = ("rv", 1.5, "monthly")
T679_FF_WIN = ("1927-01", "1999-12")
T679_REGIMES = ("2008", "2020", "2022")
T679_CED_MIN = 60

# T-681
T681_WIN = ("2012-01", "2026-08")
T681_REPL = ("1927-01", "2011-12")
T681_CRASH = ("2009-01", "2011-12")
T681_TARGET = 0.12
T681_LOOK = 126
T681_CAP = 2.0
T681_COST = 0.0020
T681_COSTS_REP = (0.0010, 0.0030, 0.0050)
T681_VARIANTS = tuple((lk, cp) for lk in (21, 126) for cp in (1.0, 2.0))
T681_TRIALS = 24 + 34 + 4
T681_MIN_N = 170
T681_BLOCK = 12
T681_NBOOT = 5000

# T-684
T684_FEAT_FROM = "1970-01-01"
T684_WARMUP = 60
T684_TRAIN = 3000
T684_VAL_YEARS = 8
T684_LAMBDAS = (0.0, 5.0, 10.0, 15.0, 25.0, 35.0, 50.0, 70.0, 100.0, 150.0)
T684_N_INIT = 10
T684_MAX_ITER = 100
T684_COST = 1e-3
T684_DELAYS = (1, 5)
T684_WIN = ("1994-01-01", "2026-09-30")
T684_LATE = "2015-01-01"
T684_POST = "2024-01-01"
T684_REPL_END = "2023-12-31"
T684_BLOCK = 63
T684_MIN_N = 6000
T684_TRIALS = 2 + 1 + 2 + 96
T684_HMM_FROM = "1990-01-02"
T684_SMA_COST = 2e-4
T684_NULL_PATHS = 2000

# T-685
T685_WIN = ("2010-01-01", "2026-06-30")
T685_FIT_FROM = ("1990-02-01", "1993-01-01")      # (b) spliced, (a) SPY-only
T685_H = 63
T685_H_REP = 21
T685_CW_LAG = 3
T685_MIN_N = 190
T685_EX2020 = ("2020-03-01", "2020-06-30")
T685_TERC_MIN = 36
T685_ARM_W = (0.5, 1.0, 1.5)
T685_ARM_COST = 2e-4


# ================================================================================================ small helpers ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, names)


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _ci(ci, nd: int = 3) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "[n/a]"
    return f"[{ci[0]:+.{nd}f}, {ci[1]:+.{nd}f}]"


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _sr(x, ppy: float) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(sharpe_ratio(x, ppy)) if x.size > 2 and x.std() > 0 else None


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _sdiff(a, b, ppy: float) -> Optional[float]:
    sa, sb = _sr(a, ppy), _sr(b, ppy)
    return None if sa is None or sb is None else sa - sb


def bill_index(days: Sequence[str], acc) -> np.ndarray:
    """Cumulative bill growth on a session calendar (B[0] = 1): each calendar day at the print dated before it."""
    c = np.array([acc._c(_ord(d)) for d in days], float)
    return np.exp(c - c[0])


def cal_gaps(days: Sequence[str]) -> np.ndarray:
    o = np.array([_ord(d) for d in days], float)
    return np.r_[0.0, np.diff(o)]


def month_ends(days: Sequence[str]) -> np.ndarray:
    """Positions of each calendar month's last session; the data's final (possibly incomplete) month is dropped."""
    return IMP.month_end_pos(days)


def week_ends(days: Sequence[str]) -> np.ndarray:
    """Positions of each ISO week's last session; the data's final (possibly incomplete) week is dropped."""
    wk = [date.fromisoformat(d).isocalendar()[:2] for d in days]
    return np.array([i for i in range(len(days) - 1) if wk[i] != wk[i + 1]], int)


def rolling_sd(x, win: int) -> np.ndarray:
    """sd (ddof 1) of x[i - win + 1 .. i] at every i (NaN when the window holds a NaN or runs before the data)."""
    x = np.asarray(x, float)
    n = x.size
    ok = np.isfinite(x)
    x0 = np.where(ok, x, 0.0)
    c1 = np.r_[0.0, np.cumsum(x0)]
    c2 = np.r_[0.0, np.cumsum(x0 * x0)]
    cn = np.r_[0, np.cumsum(ok.astype(int))]
    out = np.full(n, np.nan)
    i = np.arange(win - 1, n)
    s1 = c1[i + 1] - c1[i + 1 - win]
    s2 = c2[i + 1] - c2[i + 1 - win]
    good = (cn[i + 1] - cn[i + 1 - win]) == win
    var = (s2 - s1 * s1 / win) / (win - 1)
    out[i[good]] = np.sqrt(np.maximum(var[good], 0.0))
    return out


def simulate(ra, rb, gap, fills: dict, cost: float, spread: float) -> np.ndarray:
    """NAV at each close BEFORE any rebalance at that close, for a portfolio of one risky asset (daily simple returns
    ``ra``) and bills (``rb``), rebalanced at the closes in ``fills`` {session index: target weight}. Between fills the
    weight drifts; a fill pays ``cost`` per unit |target - drifted weight|; a negative bill position (weight > 1)
    accrues the bill return plus ``spread`` a year over the calendar days ``gap``. Starts in cash."""
    n = len(ra)
    S, C = 0.0, 1.0
    vpre = np.empty(n)
    for k in range(n):
        if k:
            S *= 1.0 + ra[k]
            C *= (1.0 + rb[k]) if C >= 0 else (1.0 + rb[k] + spread * gap[k] / 365.0)
        V = S + C
        vpre[k] = V
        w = fills.get(k)
        if w is not None:
            V *= 1.0 - cost * abs(w - S / V)
            S = w * V
            C = V - S
    return vpre


def period_excess(vpre, B, F) -> np.ndarray:
    """Excess return over bills between consecutive fills F[j] -> F[j + 1] (pre-rebalance NAVs, so each fill's cost
    falls in the period it opens)."""
    F = np.asarray(F, int)
    return vpre[F[1:]] / vpre[F[:-1]] - B[F[1:]] / B[F[:-1]]


def sharpe_pair(a, b, ppy: int, block: int, n_boot: int, reps: Optional[int] = None) -> dict:
    """Paired studentized CBB of annualised Sharpe(a) - Sharpe(b) (``batch6b_bw.sharpe_diff_test``) over 5 seeds,
    escalated to 25 when the lower end cannot be resolved against 0."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return BW.mc_escalate(lambda seed: BW.sharpe_diff_test(a, b, ppy, block, n_boot, seed),
                          lambda t: BW._ci_crit(t, "gt", 0.0, "")[1], reps, SEED)


def boot_se_sharpe_diff(a, b, ppy: int, block: int, n_boot: int, seed: int = SEED) -> float:
    """Bootstrap SE of the annualised Sharpe difference: sd of the difference over paired circular-block resamples."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = a.size
    rng = np.random.default_rng(seed)
    out, done = [], 0
    while done < n_boot:
        k = min(max(1, 2_000_000 // max(n, 1)), n_boot - done)
        idx = CAL._boot_idx(rng, n, block, k)
        A, Bm = a[idx], b[idx]
        sa = A.mean(1) / np.maximum(A.std(1, ddof=1), 1e-300)
        sb = Bm.mean(1) / np.maximum(Bm.std(1, ddof=1), 1e-300)
        out.append((sa - sb) * math.sqrt(ppy))
        done += k
    return float(np.concatenate(out).std(ddof=1))


def worst_k(x, k: int = 3) -> Optional[float]:
    """Worst compounded return over k consecutive periods."""
    x = np.asarray(x, float)
    if x.size < k:
        return None
    L = np.r_[0.0, np.cumsum(np.log1p(np.maximum(x, -0.999999)))]
    return float(np.expm1((L[k:] - L[:-k]).min()))


def _dsr_pair(series: dict, primary, n_trials: int, label: str, names: tuple) -> tuple:
    """Rule 11 over the two DSR readings: series {key: {'ex': ..., 'active': ...}}; returns (row, {reading: dsr})."""
    p = series[primary]
    d_ex = MOM.family_dsr(p["ex"], [_sr_pp(v["ex"]) for v in series.values()], n_trials)
    d_ac = MOM.family_dsr(p["active"], [_sr_pp(v["active"]) for v in series.values()], n_trials)
    row = BW.all_constructions([MOM.dsr_row(d_ex, names[0]), MOM.dsr_row(d_ac, names[1])], label)
    return row, {"excess": d_ex, "active": d_ac}


def _dsr_brief(d: dict) -> str:
    return "n/a" if d.get("dsr") is None else f"{d['dsr']:.3f} (PSR vs 0 {_f(d.get('psr0'))})"


# ========================================================================================== T-679 vol target ==

def vix_asof(vix: dict, days: Sequence[str]) -> np.ndarray:
    """VIX close dated on or before each day (the print of the decision day, else the last earlier one)."""
    ks = sorted(vix)
    vs = [vix[k] for k in ks]
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        j = bisect_right(ks, d) - 1
        if j >= 0:
            out[i] = vs[j]
    return out


def mm_constants(dec, sig2, f_hold, F, min_hist: int = T679_MM_MIN) -> np.ndarray:
    """Moreira-Muir c at each monthly decision t: sd(f) / sd(f / sigma^2) over the hold months j completed by the
    decision close (fill F[j + 1] <= dec[t]); f = buy-and-hold excess of hold j, sigma^2 the RV at decision j."""
    dec = np.asarray(dec, int)
    M = dec.size
    nh = len(f_hold)
    c = np.full(M, np.nan)
    u = f_hold / sig2[:nh]
    for t in range(M):
        jmax = int(np.searchsorted(F[1:nh + 1], dec[t], side="right"))   # holds j with F[j + 1] <= dec[t]
        if jmax >= min_hist:
            ff, uu = f_hold[:jmax], u[:jmax]
            ok = np.isfinite(ff) & np.isfinite(uu)
            if ok.sum() >= min_hist and uu[ok].std(ddof=1) > 0:
                c[t] = float(ff[ok].std(ddof=1) / uu[ok].std(ddof=1))
    return c


def vt_weights(scaler: str, cap: float, dec, sd_all, vix_d, c_dec, target: float = T679_TARGET) -> np.ndarray:
    """Target weights at the decision sessions ``dec`` (NaN where the scaler is not yet defined)."""
    sig = sd_all[dec] * math.sqrt(252.0)
    if scaler == "rv":
        return np.minimum(cap, target / sig)
    if scaler == "vix":
        return np.minimum(cap, target / (vix_d / 100.0))
    if scaler == "mm":
        w = np.minimum(cap, c_dec / (sig * sig))
        return np.where(np.isfinite(sig) & ~np.isfinite(c_dec), 1.0, w)
    raise ValueError(scaler)


def vol_target_family(days: Sequence[str], adj, B, vix: dict, win: tuple = T679_WIN) -> dict:
    """T-679 core: the 18 declared trials, buy-and-hold and constant-weight controls on one monthly fill grid."""
    days = list(days)
    n = len(days)
    adj = np.asarray(adj, float)
    ra = np.r_[np.nan, adj[1:] / adj[:-1] - 1.0]
    rb = np.r_[np.nan, B[1:] / B[:-1] - 1.0]
    gp = cal_gaps(days)
    e = ra - rb
    sd_all = rolling_sd(e, T679_RV)
    mdec = month_ends(days)
    mdec = mdec[mdec + 1 < n]
    F = mdec + 1
    lab = [days[f][:7] for f in F]
    nh = F.size - 1
    hold_lab = lab[:nh]
    f_hold = adj[F[1:]] / adj[F[:-1]] - B[F[1:]] / B[F[:-1]]
    sig_m = sd_all[mdec] * math.sqrt(252.0)
    c_m = mm_constants(mdec, sig_m ** 2, f_hold, F)
    wdec = week_ends(days)
    wdec = wdec[wdec + 1 < n]
    c_w = np.full(wdec.size, np.nan)
    for i, d in enumerate(wdec):
        t = int(np.searchsorted(mdec, d, side="right")) - 1
        if t >= 0:
            c_w[i] = c_m[t]
    grids = {"monthly": (mdec, c_m), "weekly": (wdec, c_w)}
    vixd = {k: vix_asof(vix, [days[i] for i in g[0]]) for k, g in grids.items()}
    inwin = np.array([win[0] <= m <= win[1] for m in hold_lab])
    win_lo, win_hi = F[np.where(inwin)[0][0]], F[np.where(inwin)[0][-1] + 1]
    fam = {}
    for sc in T679_SCALERS:
        for cap in T679_CAPS:
            for fq in T679_FREQS:
                dec, cdec = grids[fq]
                w = vt_weights(sc, cap, dec, sd_all, vixd[fq], cdec)
                ok = np.isfinite(w)
                fills = {int(d + 1): float(x) for d, x in zip(dec[ok], w[ok])}
                ex = period_excess(simulate(ra, rb, gp, fills, T679_COST, T679_SPREAD), B, F)
                if fills:
                    ex = np.where(F[:-1] >= min(fills), ex, np.nan)          # holds before the first fill sat in cash
                in_w = ok & (dec + 1 >= win_lo) & (dec + 1 < win_hi)
                wbar = float(w[in_w].mean())
                cfill = {int(f): wbar for f in F}
                const = period_excess(simulate(ra, rb, gp, cfill, T679_COST, T679_SPREAD), B, F)
                fam[(sc, cap, fq)] = {"ex": ex[inwin], "const": const[inwin], "active": ex[inwin] - const[inwin],
                                      "wbar": wbar, "w_dec": w, "dec": dec, "ex_all": ex}
    return {"fam": fam, "bh": f_hold[inwin], "bh_all": f_hold, "labels": [m for m, k in zip(hold_lab, inwin) if k],
            "hold_lab": hold_lab, "F": F, "mdec": mdec, "sd_all": sd_all, "c_m": c_m, "inwin": inwin}


def cederburg_combo(m_all, u_all, inwin, min_hist: int = T679_CED_MIN) -> np.ndarray:
    """Real-time mean-variance mix of managed and unmanaged excess returns: for hold j the tangency weights
    Sigma^-1 mu from holds completed by its decision (j - 2 and earlier: hold j - 1 is still open at the decision
    close), scaled to the unmanaged leg's estimated variance; NaN until ``min_hist`` holds exist."""
    m_all, u_all = np.asarray(m_all, float), np.asarray(u_all, float)
    out = np.full(m_all.size, np.nan)
    for j in np.where(inwin)[0]:
        hi = j - 1
        ok = np.isfinite(m_all[:hi]) & np.isfinite(u_all[:hi])
        if ok.sum() < min_hist:
            continue
        X = np.column_stack([m_all[:hi][ok], u_all[:hi][ok]])
        mu = X.mean(0)
        S = np.cov(X.T)
        try:
            x = np.linalg.solve(S, mu)
        except np.linalg.LinAlgError:
            continue
        v = float(x @ S @ x)
        if not v > 0:
            continue
        k = math.sqrt(S[1, 1] / v)
        out[j] = k * (x[0] * m_all[j] + x[1] * u_all[j])
    return out[np.asarray(inwin, bool)]


def ff_long_check(ff_mkt: dict, ff_rf: dict, win: tuple = T679_FF_WIN) -> dict:
    """The frozen primary rule on French Mkt-RF + RF daily (revised series; reported only)."""
    ds = sorted(set(ff_mkt) & set(ff_rf))
    mk = np.array([ff_mkt[d] for d in ds]) / 100.0
    rf = np.array([ff_rf[d] for d in ds]) / 100.0
    ra = np.r_[np.nan, (mk + rf)[1:]]
    rb = np.r_[np.nan, rf[1:]]
    B = np.r_[1.0, np.cumprod(1.0 + rf[1:])]
    A = np.r_[1.0, np.cumprod(1.0 + ra[1:])]
    gp = cal_gaps(ds)
    sd = rolling_sd(np.r_[np.nan, mk[1:]], T679_RV)
    mdec = month_ends(ds)
    mdec = mdec[mdec + 1 < len(ds)]
    F = mdec + 1
    w = np.minimum(T679_CAP, T679_TARGET / (sd[mdec] * math.sqrt(252.0)))
    ok = np.isfinite(w)
    ex = period_excess(simulate(ra, rb, gp, {int(d + 1): float(x) for d, x in zip(mdec[ok], w[ok])}, T679_COST, T679_SPREAD), B, F)
    bh = A[F[1:]] / A[F[:-1]] - B[F[1:]] / B[F[:-1]]
    lab = [ds[f][:7] for f in F[:-1]]
    m = np.array([win[0] <= x <= win[1] for x in lab]) & np.isfinite(ex)
    t = BW.sharpe_diff_test(ex[m], bh[m], 12, T679_BLOCK, T679_NBOOT, SEED)
    return {"n": int(m.sum()), "span": [lab[np.where(m)[0][0]], lab[np.where(m)[0][-1]]] if m.any() else None,
            "sharpe_managed": t.get("sharpe_a"), "sharpe_bh": t.get("sharpe_b"), "diff": t.get("diff"), "ci": t.get("ci"),
            "mean_weight": float(w[ok].mean())}


def umcsent_first_releases(rows) -> list:
    """[(available_at, observation month, value)] of first-release UMCSENT prints; ALFRED's first-vintage rows count
    from their ``lag_rule_at`` (the fetcher's approximation of the original release)."""
    out = []
    for r in rows:
        v = r.get("value") or {}
        if not v.get("first_release") or v.get("value") is None:
            continue
        at = v.get("lag_rule_at") if v.get("first_vintage") and v.get("lag_rule_at") else r.get("available_at")
        out.append((str(at), v["day"], float(v["value"])))
    return sorted(out)


def sentiment_flags(rel: list, dec_days: Sequence[str]) -> np.ndarray:
    """+1 high / -1 low / 0 unknown at each decision: the latest first-release value available by 20:00 UTC of the
    decision day against the median of every first-release value available by then."""
    ats = [a for a, _, _ in rel]
    out = np.zeros(len(dec_days), int)
    for i, d in enumerate(dec_days):
        k = bisect_right(ats, f"{d}T20:00:00+00:00")
        if k < 12:
            continue
        av = rel[:k]
        cur = max(av, key=lambda z: z[1])[2]
        med = float(np.median([z[2] for z in av]))
        out[i] = 1 if cur > med else -1
    return out


def b13_volregime_a_vol_target_spy(archive):
    """T-679: SPY volatility targeting (min(1.5, 0.15/sigma_RV21), monthly, next-close fill) vs buy-and-hold Sharpe."""
    miss = _missing(archive, [SPY_B, DTB3_B, VIX_B])
    if miss:
        return miss
    days, adj = CAL._daily(archive, SPY_B, "adjclose")
    acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
    B = bill_index(days, acc)
    vix = CAL._series(archive, VIX_B)
    R = vol_target_family(days, adj, B, vix)
    fam, bh, labels = R["fam"], R["bh"], R["labels"]
    P = fam[T679_PRIMARY]
    ex = P["ex"]
    n = int(ex.size)
    # power, computed before the test is run or read
    se_b = boot_se_sharpe_diff(ex, bh, 12, T679_BLOCK, T679_NBOOT, SEED)
    mde = (Z975 + Z80) * se_b
    sd = sharpe_pair(ex, bh, 12, T679_BLOCK, T679_NBOOT)
    late = np.array([m >= T679_LATE for m in labels])
    late_d = _sdiff(ex[late], bh[late], 12)
    dsr_row, dsr = _dsr_pair(fam, T679_PRIMARY, T679_TRIALS,
                             f"DSR > {DSR_PASS} over the {T679_TRIALS} counted trials (18 here + T-310's 20 + T-562's 2) "
                             f"under both readings (rule 11)",
                             ("managed monthly excess return", "managed minus constant-weight SPY at its mean weight"))
    rows = [BW._ci_crit(sd, "gt", 0.0, "Sharpe(managed) - Sharpe(buy-and-hold), monthly excess returns 2000-01..2026-09, "
                                      "lower 95% bound > 0 (paired studentized CBB, 12-month blocks, 10,000 draws a seed)"),
            (f"2015-01..2026-09 point estimate > 0 ({_s(late_d)})", None if late_d is None else late_d > 0,
             late_d is not None and late_d <= 0),
            dsr_row]
    v, why, crit = CAL._judge(rows, n, T679_MIN_N, "months")
    # reported
    cst = BW.sharpe_diff_test(ex, P["const"], 12, T679_BLOCK, T679_NBOOT, SEED)
    ann = lambda x: (float(np.mean(x) * 12), float(np.std(x, ddof=1) * math.sqrt(12)))
    m_mu, m_vol = ann(ex)
    b_mu, b_vol = ann(bh)
    c_mu, c_vol = ann(P["const"])
    var_only = (sd.get("diff") or 0) > 0 and m_mu < b_mu
    ced = cederburg_combo(P["ex_all"], R["bh_all"], R["inwin"])
    okc = np.isfinite(ced)
    ced_t = BW.sharpe_diff_test(ced[okc], bh[okc], 12, T679_BLOCK, T679_NBOOT, SEED) if okc.sum() > 24 else {}
    ff = None
    if B7C._has(archive, FF3_B):
        ff = ff_long_check(CAL._series(archive, FF3_B, "Mkt-RF"), CAL._series(archive, FF3_B, "RF"))
    sent = None
    if B7C._has(archive, UMC_B):
        rel = umcsent_first_releases(CAL._rows(archive, UMC_B))
        dec_days = [days[R["mdec"][j]] for j in np.where(R["inwin"])[0]]
        fl = sentiment_flags(rel, dec_days)
        sent = {}
        for nm, k in (("high", 1), ("low", -1)):
            m = fl == k
            sent[nm] = {"n": int(m.sum()), "sharpe_diff": _sdiff(ex[m], bh[m], 12),
                        "mean_diff_ann": float((ex[m] - bh[m]).mean() * 12) if m.any() else None}
    reg = {}
    for y in T679_REGIMES:
        m = np.array([x[:4] == y for x in labels])
        reg[y] = {"managed": float(np.prod(1 + ex[m]) - 1), "bh": float(np.prod(1 + bh[m]) - 1),
                  "mean_w": float(np.mean([P["w_dec"][j] for j in range(len(P["w_dec"]))
                                           if j < R["inwin"].size and R["inwin"][j] and R["hold_lab"][j][:4] == y]))}
    famtab = {f"{k[0]}|{k[1]}|{k[2]}": {"sharpe": _sr(f_["ex"], 12), "diff_vs_bh": _sdiff(f_["ex"], bh, 12), "wbar": f_["wbar"]}
              for k, f_ in fam.items()}
    stat = {"n_months": n, "window": [labels[0], labels[-1]], "power": {"boot_se": se_b, "mde_80": mde},
            "sharpe_diff": {k: sd.get(k) for k in ("diff", "ci", "ci_mc_se", "sharpe_a", "sharpe_b", "se", "reps")},
            "late_diff": late_d, "legs": {"managed": [m_mu, m_vol], "bh": [b_mu, b_vol], "const": [c_mu, c_vol]},
            "mean_weight": P["wbar"], "const_diff": {k: cst.get(k) for k in ("diff", "ci")}, "variance_only_gain": var_only,
            "cederburg": {k: ced_t.get(k) for k in ("diff", "ci", "sharpe_a", "sharpe_b", "n")}, "ff_1927_1999": ff,
            "umcsent": sent, "regimes": reg, "family": famtab, "dsr": dsr, "criteria": crit,
            "rule10": "calendar named by the claim (month-end decisions; weekly trials at ISO week-ends)"}
    wv = P["w_dec"][np.isfinite(P["w_dec"])]
    reason = (f"POWER (computed before the result): bootstrap SE of the 2000-01..2026-09 Sharpe difference {se_b:.3f} "
              f"(12-month blocks, 10,000 paired resamples), so the minimum detectable difference at 80% power is "
              f"{mde:.3f} (two-sided 5%). RESULT: SPY adjclose, DTB3 bond-equivalent (prior print), w = min(1.5, 0.15 / "
              f"sigma_RV21) decided at each month's last close and filled at the next close, drift tracked, 2 bp per unit of "
              f"turnover, leverage at bills + 50 bp; {n} hold months {labels[0]}..{labels[-1]} (mean weight {P['wbar']:.2f}, "
              f"range {wv.min():.2f}..{wv.max():.2f}): Sharpe managed {_s(sd.get('sharpe_a'), 3)} vs buy-and-hold "
              f"{_s(sd.get('sharpe_b'), 3)}, difference {_s(sd.get('diff'), 3)} {_ci(sd.get('ci'))}; 2015-01..2026-09 "
              f"{_s(late_d)}; legs (annualised mean / vol) managed {_pc(m_mu)} / {_pc(m_vol)}, buy-and-hold {_pc(b_mu)} / "
              f"{_pc(b_vol)}, constant {P['wbar']:.2f}x {_pc(c_mu)} / {_pc(c_vol)} (managed - constant Sharpe "
              f"{_s(cst.get('diff'))} {_ci(cst.get('ci'))})"
              + ("; the gain is lower variance only (managed mean below buy-and-hold's)" if var_only else "")
              + f"; DSR (40 trials) excess {_dsr_brief(dsr['excess'])}, timing component {_dsr_brief(dsr['active'])}. "
              f"Reported only: Cederburg-style real-time mix minus unmanaged {_s(ced_t.get('diff'))} {_ci(ced_t.get('ci'))} "
              f"over {int(okc.sum())} months; "
              + (f"French Mkt-RF + RF {ff['span'][0]}..{ff['span'][1]} (revised series) {_s(ff['diff'])} {_ci(ff['ci'])}; "
                 if ff and ff.get("span") else "French check n/a; ")
              + (f"UMCSENT first-release high / low months {sent['high']['n']} / {sent['low']['n']}: Sharpe diff "
                 f"{_s(sent['high']['sharpe_diff'])} / {_s(sent['low']['sharpe_diff'])}; " if sent else "UMCSENT split n/a; ")
              + "regimes " + ", ".join(f"{y} managed {_pc(r_['managed'], 1)} vs {_pc(r_['bh'], 1)}" for y, r_ in reg.items())
              + "; family Sharpe differences " + ", ".join(f"{k} {_s(x['diff_vs_bh'], 2)}" for k, x in famtab.items())
              + " — " + why)
    return _out(stat, n, v, reason)


# ========================================================================================== T-681 scaled UMD ==

def calendar_months(days: Sequence[str], r) -> tuple:
    """(month labels, last-day index of each month, compounded return of each month). The final month counts only when
    its last day is the month's last weekday (the data's final month may be incomplete)."""
    days = list(days)
    r = np.asarray(r, float)
    labs, last, R = [], [], []
    i0 = 0
    for i in range(1, len(days) + 1):
        if i == len(days) or days[i][:7] != days[i0][:7]:
            labs.append(days[i0][:7]); last.append(i - 1); R.append(float(np.prod(1.0 + r[i0:i]) - 1.0))
            i0 = i
    y, m = int(labs[-1][:4]), int(labs[-1][5:])
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    lastwd = np.busday_offset(np.datetime64(nxt) - np.timedelta64(1, "D"), 0, roll="backward")
    if str(lastwd) != days[-1]:
        labs, last, R = labs[:-1], last[:-1], R[:-1]
    return labs, np.array(last, int), np.array(R, float)


def umd_weights(r, last, look: int, cap: float, lag: int, target: float = T681_TARGET) -> np.ndarray:
    """Weight decided at each month-end: min(cap, target / RV), RV = sqrt(252 mean r^2) over the ``look`` daily returns
    ending ``lag`` sessions before the month's last session (lag 0 = through the month-end close)."""
    r = np.asarray(r, float)
    c2 = np.r_[0.0, np.cumsum(r * r)]
    w = np.full(len(last), np.nan)
    for k, i in enumerate(last):
        e = i - lag + 1
        s = e - look
        if s >= 0:
            rv = math.sqrt(252.0 * (c2[e] - c2[s]) / look)
            w[k] = min(cap, target / rv) if rv > 0 else cap
    return w


def scaled_returns(w, R, cost: float) -> np.ndarray:
    """Net return of hold month k + 1 = w_k R_{k+1} - cost |w_k - w_{k-1}| (entry from 0); aligned on months (index
    k + 1), NaN where no weight exists."""
    w = np.asarray(w, float)
    out = np.full(len(R), np.nan)
    prev = 0.0
    for k in range(len(R) - 1):
        if not np.isfinite(w[k]):
            continue
        out[k + 1] = w[k] * R[k + 1] - cost * abs(w[k] - prev)
        prev = w[k]
    return out


def bear_flags(mkt_days, mkt_r, labs) -> np.ndarray:
    """Daniel-Moskowitz bear state at each month-end: the trailing 24-month market total return < 0 (NaN if short)."""
    ml, _, mR = calendar_months(mkt_days, mkt_r)
    L = np.r_[0.0, np.cumsum(np.log1p(mR))]
    pos = {m: i for i, m in enumerate(ml)}
    out = np.full(len(labs), np.nan)
    for k, m in enumerate(labs):
        i = pos.get(m)
        if i is not None and i >= 23:
            out[k] = float(L[i + 1] - L[i - 23] < 0)
    return out


def umd_family(days, r, cost: float = T681_COST) -> dict:
    """Every variant (lookback x cap) under both rule-12 readings: {reading: {(look, cap): {'net', 'w'}}}."""
    labs, last, R = calendar_months(days, r)
    out = {"labs": labs, "R": R}
    for rd, lag in (("close", 0), ("prev", 1)):
        out[rd] = {}
        for lk, cp in T681_VARIANTS:
            w = umd_weights(r, last, lk, cp, lag)
            out[rd][(lk, cp)] = {"w": w, "net": scaled_returns(w, R, cost)}
    return out


def _umd_window(U: dict, win: tuple) -> np.ndarray:
    return np.array([win[0] <= m <= win[1] for m in U["labs"]])


def b13_volregime_a_vol_scaled_umd(archive):
    """T-681: Barroso-Santa-Clara volatility-scaled UMD (min(2, 0.12/RV126)) vs unscaled UMD, 2012-01..2026-08."""
    miss = _missing(archive, [MOM_B, FF3_B, DTB3_B])
    if miss:
        return miss
    mom = CAL._series(archive, MOM_B, "Mom")
    days = sorted(mom)
    r = np.array([mom[d] for d in days]) / 100.0
    U = umd_family(days, r)
    R = U["R"]
    m = _umd_window(U, T681_WIN)
    prim = (T681_LOOK, T681_CAP)
    raw = R[m]
    res, dsr_rows, dsrs = {}, [], {}
    for rd in ("close", "prev"):
        net = U[rd][prim]["net"][m]
        if not np.isfinite(net).all():
            return _out({"window": T681_WIN}, 0, "inconclusive", f"scaled series incomplete in the window ({rd} reading)")
        w_hold = U[rd][prim]["w"][np.where(m)[0] - 1]
        wbar = float(w_hold.mean())
        sd = sharpe_pair(net, raw, 12, T681_BLOCK, T681_NBOOT)
        mc = RATES.mean_ci(net, block=T681_BLOCK)
        fam = {}
        for key, v_ in U[rd].items():
            nx = v_["net"][m]
            wb = float(v_["w"][np.where(m)[0] - 1].mean())
            fam[key] = {"ex": nx, "active": nx - wb * raw}
        d_ex = MOM.family_dsr(fam[prim]["ex"], [_sr_pp(x["ex"]) for x in fam.values()], T681_TRIALS)
        d_ac = MOM.family_dsr(fam[prim]["active"], [_sr_pp(x["active"]) for x in fam.values()], T681_TRIALS)
        dsrs[rd] = {"excess": d_ex, "active": d_ac}
        lbl = "decision-close reading (as worded)" if rd == "close" else "previous-close reading"
        dsr_rows += [MOM.dsr_row(d_ex, f"{lbl}: scaled net"), MOM.dsr_row(d_ac, f"{lbl}: scaled net minus UMD at its mean weight")]
        res[rd] = {"sd": sd, "mean": mc, "wbar": wbar, "net": net, "fam": fam, "label": lbl}
    fmt_m = lambda x: "n/a" if x is None else f"{x * 1200:+.2f}%/yr"
    rows = [BW.all_constructions([BW._ci_crit(res[rd]["sd"], "gt", 0.0, res[rd]["label"]) for rd in ("close", "prev")],
                                 "Sharpe(scaled UMD net of 20 bp) - Sharpe(UMD) 2012-01..2026-08, lower 95% bound > 0 "
                                 "(paired studentized CBB, 12-month blocks) under both rule-12 readings"),
            BW.all_constructions([BW._ci_crit(res[rd]["mean"], "gt", 0.0, res[rd]["label"], fmt_m) for rd in ("close", "prev")],
                                 "scaled annualised net mean > 0, read as its lower 95% bound > 0 (studentized CBB, "
                                 "12-month blocks) under both rule-12 readings"),
            BW.all_constructions(dsr_rows, f"DSR > {DSR_PASS} over {T681_TRIALS} trials (T-311's 24 + T-446's 34 + 4 here), "
                                           f"both series, both rule-12 readings (rules 11, 12)")]
    n = int(m.sum())
    v, why, crit = CAL._judge(rows, n, T681_MIN_N, "months")
    # reported
    pc = res["close"]
    costs = {}
    for c in T681_COSTS_REP:
        nx = scaled_returns(U["close"][prim]["w"], R, c)[m]
        costs[f"{c * 1e4:.0f}bp"] = {"sharpe_diff": _sdiff(nx, raw, 12), "mean_ann": float(nx.mean() * 12)}
    subs = {}
    for nm, wn in (("1927-2011", T681_REPL), ("2009-2011", T681_CRASH)):
        mm = _umd_window(U, wn) & np.isfinite(U["close"][prim]["net"])
        nx, rr = U["close"][prim]["net"][mm], R[mm]
        t = BW.sharpe_diff_test(nx, rr, 12, T681_BLOCK, T681_NBOOT, SEED)
        subs[nm] = {"n": int(mm.sum()), "diff": t.get("diff"), "ci": t.get("ci"), "sharpe_scaled": t.get("sharpe_a"),
                    "sharpe_umd": t.get("sharpe_b"), "mean_scaled_ann": float(nx.mean() * 12), "mean_umd_ann": float(rr.mean() * 12)}
    ffm, ffr = CAL._series(archive, FF3_B, "Mkt-RF"), CAL._series(archive, FF3_B, "RF")
    fd = sorted(set(ffm) & set(ffr))
    mret = np.array([(ffm[d] + ffr[d]) / 100.0 for d in fd])
    bear = bear_flags(fd, mret, U["labs"])
    wb = np.where(np.isfinite(bear), 1.0 - bear, np.nan)
    bear_net = scaled_returns(wb, R, T681_COST)[m]
    rep = {"worst3": {"scaled": worst_k(pc["net"]), "umd": worst_k(raw), "bear_filter": worst_k(bear_net)},
           "bear_filter": {"sharpe": _sr(bear_net, 12), "share_out": float(np.nanmean(bear[np.where(m)[0] - 1])) if m.any() else None},
           "costs": costs, "subperiods": subs,
           "constant_weight": {"wbar": pc["wbar"], "mean_ann": float(pc["wbar"] * raw.mean() * 12), "sharpe": _sr(raw, 12)}}
    stat = {"n_months": n, "window": list(T681_WIN), "readings": {rd: {"sharpe_diff": {k: x["sd"].get(k) for k in ("diff", "ci", "ci_mc_se", "sharpe_a", "sharpe_b", "reps")},
                                                                      "mean_net": {k: x["mean"].get(k) for k in ("est", "ci", "ci_mc_se")},
                                                                      "wbar": x["wbar"]} for rd, x in res.items()},
            "dsr": dsrs, "reported": rep, "criteria": crit, "rule10": "calendar named by the claim (month-end decisions)"}
    sc, sp = pc["sd"], res["prev"]["sd"]
    reason = (f"French daily Mom (revised paper factor, not point in time; its own rebalancing uncosted in both legs), "
              f"{n} hold months {T681_WIN[0]}..{T681_WIN[1]}: w = min(2, 0.12 / RV126) (mean {pc['wbar']:.2f}), 20 bp per unit "
              f"weight change: Sharpe scaled {_s(sc.get('sharpe_a'), 3)} vs UMD {_s(sc.get('sharpe_b'), 3)}, difference "
              f"{_s(sc.get('diff'), 3)} {_ci(sc.get('ci'))} (previous-close reading {_s(sp.get('diff'), 3)} {_ci(sp.get('ci'))}); "
              f"scaled net mean {fmt_m(pc['mean'].get('est'))} [{fmt_m((pc['mean'].get('ci') or [None])[0])}, "
              f"{fmt_m((pc['mean'].get('ci') or [None, None])[1])}] vs UMD {raw.mean() * 1200:+.2f}%/yr; DSR (62 trials) "
              f"scaled {_dsr_brief(dsrs['close']['excess'])}, timing {_dsr_brief(dsrs['close']['active'])}. Reported: costs "
              + ", ".join(f"{k} diff {_s(x['sharpe_diff'])} mean {x['mean_ann'] * 100:+.2f}%" for k, x in costs.items())
              + f"; worst 3 months scaled {_pc(rep['worst3']['scaled'], 1)}, UMD {_pc(rep['worst3']['umd'], 1)}, bear filter "
              f"{_pc(rep['worst3']['bear_filter'], 1)} (bear-filter Sharpe {_s(rep['bear_filter']['sharpe'])}); "
              + "; ".join(f"{k} ({x['n']} months) diff {_s(x['diff'])} {_ci(x['ci'])}, means {x['mean_scaled_ann'] * 100:+.2f}% "
                          f"vs {x['mean_umd_ann'] * 100:+.2f}%" for k, x in subs.items())
              + " (2009 lies inside BSC's sample: not evidence here). A pass is a paper-factor result; fred-DTB3 is not used "
              f"(UMD is zero-investment) — {why}")
    return _out(stat, n, v, reason)


# ======================================================================================= T-684 jump model ==

def ewm(x, halflife: float) -> np.ndarray:
    """Exponentially weighted mean, pandas adjust=True: sum (1 - a)^i x_{t-i} / sum (1 - a)^i, a = 1 - 0.5^(1/h)."""
    q = 0.5 ** (1.0 / halflife)
    out = np.empty(len(x))
    num = den = 0.0
    for i, v in enumerate(np.asarray(x, float)):
        num = v + q * num
        den = 1.0 + q * den
        out[i] = num / den
    return out


def jm_features(x) -> np.ndarray:
    """(n, 3) features of daily excess returns x (x[0] unused): EWM downside deviation (h 10), EWM Sortino (h 20, 60).
    Row k uses x[1..k] only."""
    x = np.asarray(x, float)
    n = x.size
    F = np.full((n, 3), np.nan)
    r = x[1:]
    neg2 = np.minimum(r, 0.0) ** 2
    dd10 = np.sqrt(ewm(neg2, 10))
    s = []
    for h in (20, 60):
        dd = np.sqrt(ewm(neg2, h))
        with np.errstate(divide="ignore", invalid="ignore"):
            s.append(np.where(dd > 0, ewm(r, h) / dd, np.nan))
    F[1:, 0] = np.where(dd10 > 0, dd10, np.nan)
    F[1:, 1], F[1:, 2] = s
    return F


def kmeanspp2(Z, rng) -> np.ndarray:
    i0 = int(rng.integers(Z.shape[0]))
    d2 = ((Z - Z[i0]) ** 2).sum(1)
    i1 = int(rng.choice(Z.shape[0], p=d2 / d2.sum())) if d2.sum() > 0 else int(rng.integers(Z.shape[0]))
    return np.stack([Z[i0], Z[i1]])


def dp_path(dl, lam) -> np.ndarray:
    """Optimal two-state paths minimising sum loss(s_t) + lam #switches, rows independent: dl (M, T) = loss(1) -
    loss(0), lam (M,). D_t = V_t(1) - V_t(0) = dl_t + clip(D_{t-1}, -lam, lam); backtracking prefers staying."""
    dl = np.asarray(dl, float)
    lam = np.asarray(lam, float)
    M, T = dl.shape
    dT = np.ascontiguousarray(dl.T)
    Dh = np.empty((T, M))
    D = dT[0].copy()
    Dh[0] = D
    nl = -lam
    for t in range(1, T):
        D = dT[t] + np.minimum(np.maximum(D, nl), lam)
        Dh[t] = D
    s = np.empty((T, M), bool)
    cur = Dh[T - 1] < 0
    s[T - 1] = cur
    for t in range(T - 1, 0, -1):
        Dp = Dh[t - 1]
        cur = np.where(cur, Dp <= lam, Dp < nl)
        s[t - 1] = cur
    return s.T


def _losses(Z, th) -> np.ndarray:
    ZZ = (Z * Z).sum(1)
    return 0.5 * (ZZ[None, None, :] - 2.0 * np.einsum("tp,mkp->mkt", Z, th) + (th * th).sum(-1)[:, :, None])


def jm_fit(Z, lams: Sequence[float], n_init: int = T684_N_INIT, max_iter: int = T684_MAX_ITER, seed: int = SEED) -> dict:
    """Two-state statistical jump model on standardised features Z (T, p) for every penalty in ``lams``: coordinate
    descent (optimal path given centroids, centroids = state means given the path) from ``n_init`` k-means++ starts
    (shared across penalties); the start with the lowest objective is kept. Returns per penalty the centroids (L, 2, p),
    the training path (L, T) and the objective."""
    Z = np.asarray(Z, float)
    T = Z.shape[0]
    L = len(lams)
    rng = np.random.default_rng(seed)
    inits = np.stack([kmeanspp2(Z, rng) for _ in range(n_init)])
    th = np.tile(inits, (L, 1, 1))
    lam = np.repeat(np.asarray(lams, float), n_init)
    prev = None
    it = 0
    converged = False
    for it in range(1, max_iter + 1):
        loss = _losses(Z, th)
        s = dp_path(loss[:, 1] - loss[:, 0], lam)
        if prev is not None and np.array_equal(s, prev):
            converged = True
            break
        prev = s
        w1 = s.astype(float)
        n1 = w1.sum(1)
        n0 = T - n1
        c1 = w1 @ Z
        c0 = Z.sum(0)[None, :] - c1
        th = th.copy()
        ok1, ok0 = n1 > 0, n0 > 0
        th[ok1, 1] = c1[ok1] / n1[ok1, None]
        th[ok0, 0] = c0[ok0] / n0[ok0, None]
    loss = _losses(Z, th)
    s = dp_path(loss[:, 1] - loss[:, 0], lam)
    obj = np.where(s, loss[:, 1], loss[:, 0]).sum(1) + lam * np.abs(np.diff(s.astype(int), axis=1)).sum(1)
    obj = obj.reshape(L, n_init)
    best = obj.argmin(1)
    pick = np.arange(L) * n_init + best
    return {"theta": th[pick], "path": s[pick], "obj": obj[np.arange(L), best], "iters": it, "converged": converged}


def online_states(dl, lam, W: int, J: int) -> np.ndarray:
    """Online JM state at J consecutive days: day j's state is the last state of the optimal path over the trailing W
    sessions ending at it (a fresh forward pass from V = 0 at the window's first session). dl (L, W - 1 + J) covers the
    first window's start through the last day; returns (L, J) bool (True = state 1)."""
    dl = np.asarray(dl, float)
    lam = np.asarray(lam, float)[:, None]
    Lr, nwin = dl.shape
    if nwin != W - 1 + J:
        raise ValueError("dl must span W - 1 + J sessions")
    D = np.zeros((Lr, J))
    out = np.empty((Lr, J), bool)
    for u in range(nwin):
        lo = max(0, u - W + 1)
        hi_old = min(u - 1, J - 1)
        if hi_old >= lo:
            D[:, lo:hi_old + 1] = dl[:, u:u + 1] + np.minimum(np.maximum(D[:, lo:hi_old + 1], -lam), lam)
        if u < J:
            D[:, u] = dl[:, u]
        je = u - W + 1
        if 0 <= je < J:
            out[:, je] = D[:, je] < 0
    return out


def refit_points(days: Sequence[str], valid, train: int = T684_TRAIN) -> list:
    """Session indices of the first session of each January and July with ``train`` valid feature sessions before it."""
    days = list(days)
    valid = np.asarray(valid, bool)
    cv = np.r_[0, np.cumsum(valid.astype(int))]
    out = []
    for i in range(1, len(days)):
        if days[i][:7] != days[i - 1][:7] and days[i][5:7] in ("01", "07"):
            if i - train >= 0 and cv[i] - cv[i - train] == train:
                out.append(i)
    return out


def jm_good_flags(days: Sequence[str], x, lams: Sequence[float] = T684_LAMBDAS, train: int = T684_TRAIN,
                  warmup: int = T684_WARMUP, n_init: int = T684_N_INIT) -> dict:
    """Online good-state flags for every penalty: good (L, n) int8 (1 good, 0 bad, -1 undefined). Each half-year's fit
    is trained on the ``train`` sessions before its first session (features standardised on that window); the state on
    a day of that half-year comes from ``online_states`` over the trailing ``train`` sessions ending at it."""
    days = list(days)
    n = len(days)
    X = jm_features(x)
    valid = np.isfinite(X).all(1) & (np.arange(n) >= 1 + warmup)
    pts = refit_points(days, valid, train)
    L = len(lams)
    good = np.full((L, n), -1, np.int8)
    lamv = np.asarray(lams, float)
    info = []
    for f, r0 in enumerate(pts):
        r1 = pts[f + 1] if f + 1 < len(pts) else n
        tr = slice(r0 - train, r0)
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd = np.where(sd > 0, sd, 1.0)
        fit = jm_fit((X[tr] - mu) / sd, lams, n_init=n_init, seed=SEED + f)
        xt = np.asarray(x, float)[tr]
        gs, one = np.zeros(L, int), np.zeros(L, bool)
        for l in range(L):
            p = fit["path"][l]
            if p.all() or not p.any():
                one[l] = True
            else:
                gs[l] = 1 if xt[p].sum() > xt[~p].sum() else 0
        J = r1 - r0
        s0 = r0 - (train - 1)
        Zw = (X[s0:r1] - mu) / sd
        th = fit["theta"]
        lw = 0.5 * (((Zw[None, :, :] - th[:, 1, None, :]) ** 2).sum(-1) - ((Zw[None, :, :] - th[:, 0, None, :]) ** 2).sum(-1))
        bad = ~np.isfinite(Zw).all(1)
        lw = np.where(bad[None, :, None] if lw.ndim == 3 else bad[None, :], 0.0, lw)
        st = online_states(lw, lamv, train, J)
        g = (st == gs[:, None].astype(bool)).astype(np.int8)
        g[one] = 1
        # a day whose trailing window holds a non-finite feature row is undefined, never a silent 0/1
        cb = np.r_[0, np.cumsum(bad.astype(int))]
        win_bad = (cb[train - 1 + np.arange(J) + 1] - cb[np.arange(J)]) > 0
        g[:, win_bad] = -1
        good[:, r0:r1] = g
        info.append({"refit": days[r0], "iters": fit["iters"], "converged": fit["converged"], "one_regime": one.tolist()})
    return {"good": good, "refits": info, "first_refit": days[pts[0]] if pts else None, "features": X}


def lagged_positions(flags, delay: int) -> np.ndarray:
    """Position for the return of session u = flag at u - 1 - delay (trade at the close of t + delay); NaN where the
    flag is undefined (-1)."""
    flags = np.asarray(flags)
    one = flags.ndim == 1
    F = np.atleast_2d(flags).astype(float)
    F[F < 0] = np.nan
    P = np.full(F.shape, np.nan)
    k = 1 + delay
    P[:, k:] = F[:, :-k]
    return P[0] if one else P


def strat_excess(pos, x, cost: float) -> np.ndarray:
    """pos x excess - cost x |pos_u - pos_{u-1}| (NaN where a position or its predecessor is undefined)."""
    pos = np.asarray(pos, float)
    sw = np.abs(np.diff(pos, axis=-1, prepend=np.nan))
    return pos * x - cost * sw


def select_penalty(days: Sequence[str], good, x, delay: int, years: int = T684_VAL_YEARS, cost: float = T684_COST) -> dict:
    """Penalty chosen at the first session of every month: the grid index whose 0/1 rule (``delay``, ``cost``) had the
    best Sharpe on the excess returns ``x`` over the ``years`` years before that month (sessions strictly before its
    first session; ties to the smaller penalty). Then the live flag g[t] = good[chosen(month of t), t]."""
    days = list(days)
    n = len(days)
    E = strat_excess(lagged_positions(good, delay), np.asarray(x, float)[None, :], cost)
    ok = np.isfinite(E).all(0)
    E0 = np.where(np.isfinite(E), E, 0.0)
    c1 = np.concatenate([np.zeros((E.shape[0], 1)), np.cumsum(E0, 1)], 1)
    c2 = np.concatenate([np.zeros((E.shape[0], 1)), np.cumsum(E0 * E0, 1)], 1)
    cok = np.r_[0, np.cumsum(ok.astype(int))]
    choice = np.full(n, -1, int)
    months = []
    darr = np.array(days)
    starts = [k for k in range(1, n) if days[k][:7] != days[k - 1][:7]]
    for j, fm in enumerate(starts):
        d0 = date.fromisoformat(days[fm])
        try:
            lo_day = d0.replace(year=d0.year - years).isoformat()
        except ValueError:
            lo_day = d0.replace(year=d0.year - years, day=28).isoformat()
        lo = int(np.searchsorted(darr[:fm], lo_day, side="left"))
        m = fm - lo
        if m < 250 or cok[fm] - cok[lo] != m:
            continue
        s1 = c1[:, fm] - c1[:, lo]
        s2 = c2[:, fm] - c2[:, lo]
        var = (s2 - s1 * s1 / m) / (m - 1)
        sr = np.where(var > 1e-18, (s1 / m) / np.sqrt(np.maximum(var, 1e-300)), -np.inf)
        k = int(np.argmax(sr))
        end = starts[j + 1] if j + 1 < len(starts) else n
        choice[fm:end] = k
        months.append((days[fm][:7], k))
    g = np.full(n, -1, np.int8)
    has = choice >= 0
    g[has] = np.asarray(good)[choice[has], np.where(has)[0]]
    return {"g": g, "choice": choice, "months": months}


def hmm_daily_flags(gdays: Sequence[str], gclose, train_from: str = T684_HMM_FROM) -> np.ndarray:
    """T-561's HMM applied daily: 1 when the forward-filtered P(high-variance | ^GSPC log returns through t) < 0.5 under
    the fit of t's year (refitted every January 1 on returns before it, training from 1990-01-02), -1 undefined."""
    c = np.asarray(gclose, float)
    i0 = list(gdays).index(train_from) if train_from in gdays else int(np.searchsorted(np.array(gdays), train_from))
    rd = list(gdays[i0 + 1:])
    r = np.log(c[i0 + 1:] / c[i0:-1])
    fits = MK.yearly_refits(rd, r, int(train_from[:4]) + 3, train_from=train_from)
    ph = MK.filtered_high(rd, r, fits, train_from=train_from)
    return np.array([(-1 if d not in ph else int(ph[d] < 0.5)) for d in gdays], np.int8)


def sma_positions(days: Sequence[str], adj, k: int = 10) -> np.ndarray:
    """T-301: in when the month-end adjclose is above the mean of the last k month-end adjcloses, filled at the next
    session's close; position for each session's return (NaN before the first signal)."""
    adj = np.asarray(adj, float)
    n = len(days)
    me = month_ends(days)
    pos = np.full(n, np.nan)
    for j in range(k - 1, me.size):
        a = me[j] + 2
        b = (me[j + 1] + 2) if j + 1 < me.size else n
        pos[a:b] = float(adj[me[j]] > adj[me[j - k + 1:j + 1]].mean())
    return pos


def random_timing_mdd(pos, rs, rb, cost: float, n_paths: int, seed: int = SEED) -> dict:
    """Spell-preserving random-timing null (as T-301 / T-561): the rule's own out-of-market spells re-placed at random;
    p = (1 + #{null MDD <= rule MDD}) / (paths + 1)."""
    pos = np.asarray(pos, float)

    def mdd(P):
        sw = np.abs(np.diff(P, axis=1, prepend=P[:, :1]))
        R = P * rs[None, :] + (1 - P) * rb[None, :] - cost * sw
        return MOM.mdd_from_logwealth(np.cumsum(np.log1p(R), axis=1))

    rule = float(mdd(pos[None, :])[0])
    rng = np.random.default_rng(seed)
    out, done = [], 0
    while done < n_paths:
        k = min(250, n_paths - done)
        paths, _ = MOM.spell_paths(pos < 0.5, k, rng, with_src=False)
        out.append(mdd((~paths).astype(float)))
        done += k
    null = np.concatenate(out)
    return {"rule_mdd": rule, "null_median": float(np.median(null)), "null_q05": float(np.quantile(null, 0.05)),
            "p": float((1 + np.sum(null <= rule)) / (null.size + 1)), "n_paths": int(null.size)}


def jump_model_test(gdays, gclose, spy_adj_by_day: dict, B, n_boot: Optional[int] = None, reps: Optional[int] = None,
                    null_paths: int = T684_NULL_PATHS, with_hmm: bool = True) -> dict:
    """T-684 core on the ^GSPC session calendar (B = bill index on it)."""
    gdays = list(gdays)
    gc = np.asarray(gclose, float)
    i0 = max(0, int(np.searchsorted(np.array(gdays), T684_FEAT_FROM)) - 1)
    days = gdays[i0:]
    c = gc[i0:]
    Bf = np.asarray(B, float)[i0:]
    rb = np.r_[np.nan, Bf[1:] / Bf[:-1] - 1.0]
    xg = np.r_[np.nan, c[1:] / c[:-1] - 1.0] - rb
    J = jm_good_flags(days, xg)
    spy = np.array([spy_adj_by_day.get(d, np.nan) for d in days], float)
    rs = np.r_[np.nan, spy[1:] / spy[:-1] - 1.0]
    xs = rs - rb
    win = np.array([T684_WIN[0] <= d <= T684_WIN[1] for d in days])
    trials = {}
    for dly in T684_DELAYS:
        sel = select_penalty(days, J["good"], xg, dly)
        pos = lagged_positions(sel["g"], dly)
        ex = strat_excess(pos, xs, T684_COST)
        trials[dly] = {"sel": sel, "pos": pos, "ex": ex}
    P = trials[1]
    ok = win & np.isfinite(P["ex"]) & np.isfinite(xs) & np.isfinite(trials[5]["ex"])
    if ok.sum() < 10:
        return {"n": int(ok.sum()), "error": "no live window"}
    a, b = P["ex"][ok], xs[ok]
    wd = [d for d, k in zip(days, ok) if k]
    sd = sharpe_pair(a, b, 252, T684_BLOCK, BW.N_BOOT if n_boot is None else n_boot, reps)
    late = np.array([d >= T684_LATE for d in wd])
    late_d = _sdiff(a[late], b[late], 252)
    fam = {}
    for dly, t in trials.items():
        e_ = t["ex"][ok]
        tim = float(t["pos"][ok].mean())
        fam[dly] = {"ex": e_, "active": e_ - tim * b, "tim": tim}
    dsr_row, dsr = _dsr_pair(fam, 1, T684_TRIALS,
                             f"DSR > {DSR_PASS} over the {T684_TRIALS} counted trials (delays t+1/t+5, T-561's 1, T-562's 2, "
                             f"T-301's 96) under both readings (rule 11)",
                             ("JM-timed daily excess return", "JM-timed minus SPY at its average time in market"))
    rows = [BW._ci_crit(sd, "gt", 0.0, "Sharpe(JM-timed) - Sharpe(buy-and-hold), daily excess returns 1994-01..2026-09, lower "
                                      "95% bound > 0 (paired studentized CBB, 63-day blocks)"),
            (f"2015-01..2026-09 point estimate > 0 ({_s(late_d)})", None if late_d is None else late_d > 0,
             late_d is not None and late_d <= 0),
            dsr_row]
    v, why, crit = CAL._judge(rows, int(ok.sum()), T684_MIN_N, "days")
    # reported
    pos = P["pos"][ok]
    rsw, rbw = rs[ok], rb[ok]
    years = ok.sum() / 252.0
    sw = int(np.sum(np.abs(np.diff(pos)) > 0))
    tot = lambda e_: rbw + e_
    mdd_j = float(MOM.mdd_depth(tot(a)[None, :])[0])
    mdd_b = float(MOM.mdd_depth(rsw[None, :])[0])
    wins = {}
    for nm, lo, hi in (("1994-2023 (replication)", T684_WIN[0], T684_REPL_END), ("2015-2026", T684_LATE, T684_WIN[1]),
                       ("2024-2026 (post-publication)", T684_POST, T684_WIN[1])):
        m = np.array([lo <= d <= hi for d in wd])
        wins[nm] = {"n": int(m.sum()), "diff": _sdiff(a[m], b[m], 252), "sharpe_jm": _sr(a[m], 252), "sharpe_bh": _sr(b[m], 252)}
    d5 = _sdiff(fam[5]["ex"], b, 252)
    hmm = None
    if with_hmm:
        hf = hmm_daily_flags(days, c)
        hpos = lagged_positions(hf, 1)
        hex_ = strat_excess(hpos, xs, T684_COST)[ok]
        if np.isfinite(hex_).all():
            ht = BW.sharpe_diff_test(a, hex_, 252, T684_BLOCK, BW.N_BOOT, SEED)
            hmm = {"sharpe_hmm": _sr(hex_, 252), "diff_jm_minus_hmm": ht.get("diff"), "ci": ht.get("ci"),
                   "time_in_market": float(hpos[ok].mean())}
    sma = None
    spos = sma_positions(days, np.where(np.isfinite(spy), spy, np.nan))
    sex = strat_excess(spos, xs, T684_SMA_COST)[ok]
    if np.isfinite(sex).all():
        sma = {"sharpe": _sr(sex, 252), "mdd": float(MOM.mdd_depth(tot(sex)[None, :])[0])}
    null = random_timing_mdd(pos, rsw, rbw, T684_COST, null_paths) if null_paths else None
    lam_counts = {}
    for mth, k in P["sel"]["months"]:
        if T684_WIN[0][:7] <= mth <= T684_WIN[1][:7]:
            lam_counts[T684_LAMBDAS[k]] = lam_counts.get(T684_LAMBDAS[k], 0) + 1
    stat = {"n_days": int(ok.sum()), "window": [wd[0], wd[-1]], "first_refit": J["first_refit"], "n_refits": len(J["refits"]),
            "unconverged_refits": int(sum(not r_["converged"] for r_ in J["refits"])),
            "sharpe_diff": {k: sd.get(k) for k in ("diff", "ci", "ci_mc_se", "sharpe_a", "sharpe_b", "se", "reps")},
            "late_diff": late_d, "delay5_diff": d5, "windows": wins, "mdd": {"jm": mdd_j, "bh": mdd_b, "ratio": mdd_j / mdd_b if mdd_b else None},
            "switches_per_year": sw / years, "time_in_market": float(pos.mean()), "lambda_chosen_months": lam_counts,
            "hmm": hmm, "sma10": sma, "random_timing_null": null, "dsr": dsr, "criteria": crit, "lambda_grid": list(T684_LAMBDAS),
            "rule10": "daily state; no grid"}
    return {"stat": stat, "n": int(ok.sum()), "verdict": v, "why": why, "sd": sd, "wd": wd}


def b13_volregime_a_jump_model_spy(archive):
    """T-684: two-state statistical jump model (DD10, Sortino 20/60) de-risking SPY to bills vs buy-and-hold."""
    miss = _missing(archive, [GSPC_B, SPY_B, DTB3_B])
    if miss:
        return miss

    def run():
        gd, gc = CAL._daily(archive, GSPC_B, "close")
        sdays, sadj = CAL._daily(archive, SPY_B, "adjclose")
        acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
        return jump_model_test(gd, gc, dict(zip(sdays, sadj)), bill_index(gd, acc))

    J = CAL._cached(archive, ("t684",), run)
    if "error" in J:
        return _out(J, J["n"], "inconclusive", f"T-684: {J['error']}")
    s, sd = J["stat"], J["sd"]
    w, h, sm, nl = s["windows"], s["hmm"], s["sma10"], s["random_timing_null"]
    reason = (f"^GSPC price excess features from 1970 (dividends omitted from the features only), 3,000-session training "
              f"refitted every January / July ({s['n_refits']} fits from {s['first_refit']}, {s['unconverged_refits']} not "
              f"converged in {T684_MAX_ITER} iterations), online states from trailing 3,000-session forward passes, lambda "
              f"re-chosen monthly on 8-year validation (grid {list(T684_LAMBDAS)}, declared before running); SPY adjclose / "
              f"DTB3 bills, traded at the t+1 close, 10 bp per switch; {s['n_days']} days {s['window'][0]}..{s['window'][1]}: "
              f"Sharpe JM {_s(sd.get('sharpe_a'), 3)} vs buy-and-hold {_s(sd.get('sharpe_b'), 3)}, difference "
              f"{_s(sd.get('diff'), 3)} {_ci(sd.get('ci'))}; 2015-01..2026-09 {_s(s['late_diff'])}; time in market "
              f"{s['time_in_market']:.0%}, {s['switches_per_year']:.1f} switches a year, MDD {s['mdd']['jm'] * 100:.1f}% vs "
              f"{s['mdd']['bh'] * 100:.1f}%; DSR (101 trials) excess {_dsr_brief(s['dsr']['excess'])}, timing component "
              f"{_dsr_brief(s['dsr']['active'])}. Reported: "
              + "; ".join(f"{k} diff {_s(x['diff'])}" for k, x in w.items())
              + f"; t+5 delay diff {_s(s['delay5_diff'])}; "
              + (f"JM - T-561 HMM (daily, same lag) {_s(h['diff_jm_minus_hmm'])} {_ci(h['ci'])} (HMM Sharpe {_s(h['sharpe_hmm'])}); "
                 if h else "HMM control n/a; ")
              + (f"T-301 SMA10 Sharpe {_s(sm['sharpe'])}, MDD {sm['mdd'] * 100:.1f}%; " if sm else "SMA10 n/a; ")
              + (f"spell-preserving random-timing MDD null median {nl['null_median'] * 100:.1f}%, p {nl['p']:.4f} on "
                 f"{nl['n_paths']} paths; " if nl else "")
              + f"chosen lambda months {s['lambda_chosen_months']}. 1994-2023 overlaps the paper's test period (replication "
              f"window); a drawdown-only gain is a risk overlay, not an edge — {J['why']}")
    return _out(s, J["n"], J["verdict"], reason)


# ========================================================================================== T-685 VRP -> SPY ==

def gspc_hilo(archive) -> dict:
    """{day: (high, low)} of ^GSPC bars available at capture."""
    out = {}
    for r in CAL._rows(archive, GSPC_B):
        v = r["value"]
        try:
            h, lo = float(v.get("high")), float(v.get("low"))
        except (TypeError, ValueError):
            continue
        if h > 0 and lo > 0 and math.isfinite(h) and math.isfinite(lo):
            out[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = (h, lo)
    return out


def window_sum_targets(pos, h: int, r) -> tuple:
    """(y, a, e): y_j = sum of the daily values r over sessions a_j + 1 .. e_j, a_j = pos_j + 1 (the next session's
    close), e_j = a_j + h; NaN where the window runs past the data or holds a NaN."""
    r = np.asarray(r, float)
    n = r.size
    a = np.asarray(pos, int) + 1
    e = a + h
    ok = np.isfinite(r)
    c = np.r_[0.0, np.cumsum(np.where(ok, r, 0.0))]
    cn = np.r_[0, np.cumsum(ok.astype(int))]
    y = np.full(a.size, np.nan)
    m = e <= n - 1
    am, em = a[m], e[m]
    full = (cn[em + 1] - cn[am + 1]) == h
    yy = c[em + 1] - c[am + 1]
    y[np.where(m)[0][full]] = yy[full]
    return y, a, e


def hodrick_ols(y, X, a, h: int, r) -> dict:
    """OLS of window-sum targets y on X (with its own constant) and Hodrick (1992) 1B standard errors computed on the
    sessions: under the null each target is the sum of its sessions' daily values u_s = r_s - mean, so X'e = sum_s u_s
    q_s with q_s = sum of X_j over the windows holding s; V = (X'X)^-1 [sum_s u_s^2 q_s q_s'] (X'X)^-1."""
    y, X, r = np.asarray(y, float), np.asarray(X, float), np.asarray(r, float)
    a = np.asarray(a, int)
    k = X.shape[1]
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    lo, hi = int(a.min()) + 1, int(a.max()) + h
    span = hi - lo + 1
    Q = np.zeros((span + 1, k))
    for j in range(a.size):
        Q[a[j] + 1 - lo] += X[j]
        Q[a[j] + h + 1 - lo] -= X[j]
    q = np.cumsum(Q, axis=0)[:span]
    rs = r[lo:hi + 1]
    cov = np.abs(q).sum(1) > 0
    u = rs - rs[cov].mean()
    u = np.where(cov, u, 0.0)
    S = (q * (u * u)[:, None]).T @ q
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    t = np.where(se > 0, beta / np.where(se > 0, se, 1.0), np.nan)
    return {"beta": beta, "se": se, "t": t, "n": int(y.size), "h": int(h)}


def _slope_hod(y, x, a, h, r, mask) -> dict:
    """Slope of y on standardised x over ``mask`` with Hodrick and Newey-West (lag h/21) t; one-sided p's."""
    m = np.asarray(mask, bool) & np.isfinite(y) & np.isfinite(x)
    if m.sum() < 12:
        return {"n": int(m.sum()), "slope": None, "t": None, "p": None}
    xm = x[m]
    z = (xm - xm.mean()) / xm.std(ddof=1)
    H = hodrick_ols(y[m], np.column_stack([np.ones(z.size), z]), a[m], h, r)
    nw = CAL.ols_nw(y[m], z, max(1, h // 21))
    t = float(H["t"][1])
    return {"n": int(m.sum()), "slope": float(H["beta"][1]), "se_hodrick": float(H["se"][1]), "t": t,
            "p": float(1.0 - _N.cdf(t)) if math.isfinite(t) else None, "t_nw": nw["t"],
            "p_nw": float(1.0 - _N.cdf(nw["t"])) if math.isfinite(nw["t"]) else None}


def vrp_spy_test(gdays, gclose, hilo: dict, vix: dict, spy_by_day: dict, B, n_boot: Optional[int] = None) -> dict:
    """T-685 core on the ^GSPC session calendar (B = the bill index on it)."""
    gdays = list(gdays)
    n = len(gdays)
    G = np.asarray(gclose, float)
    fr = IMP.vrp_frame(gdays, G, vix, har_min=10 ** 9)
    pos = fr["pos"]
    mdays = fr["day"]
    vrp, rv, v2 = fr["vrp"], fr["rv"], (fr["vix"] / 100.0) ** 2 / 12.0
    spy = np.array([spy_by_day.get(d, np.nan) for d in gdays], float)
    lb = np.r_[np.nan, np.log(B[1:] / B[:-1])]
    r_spy = np.r_[np.nan, np.log(spy[1:] / spy[:-1])] - lb
    r_gs = np.r_[np.nan, np.log(G[1:] / G[:-1])] - lb
    pk = np.array([(math.log(hilo[d][0] / hilo[d][1]) ** 2 / (4 * math.log(2))) if d in hilo else np.nan for d in gdays])
    cpk = np.r_[0.0, np.cumsum(np.where(np.isfinite(pk), pk, 0.0))]
    rv_pk = np.array([cpk[i + 1] - cpk[i - 20] if i >= 21 else np.nan for i in pos])
    y_spy, a, e = window_sum_targets(pos, T685_H, r_spy)
    y_gs, _, _ = window_sum_targets(pos, T685_H, r_gs)
    y_spl = np.where(np.isfinite(y_spy), y_spy, y_gs)
    dd = np.array(mdays)
    oos = (dd >= T685_WIN[0]) & (dd <= T685_WIN[1]) & np.isfinite(vrp)
    prim = _slope_hod(y_spy, vrp, a, T685_H, r_spy, oos)
    reads = {}
    for nm, y_, fit_from in (("spy_only", y_spy, T685_FIT_FROM[1]), ("spliced", y_spl, T685_FIT_FROM[0])):
        train = (dd >= fit_from) & np.isfinite(y_)
        fm, fb, sl = IMP.expanding_ols(vrp, y_, pos, e, train, oos)
        ev = IMP.oos_stats(y_spy if nm == "spy_only" else y_spl, fm, fb, oos, T685_CW_LAG)
        fmr, fbr, _ = IMP.expanding_ols(vrp, y_, pos, e, train, oos, restrict=True)
        ev["restricted_oos_r2"] = IMP.oos_stats(y_, fmr, fbr, oos, T685_CW_LAG)["oos_r2"]
        ev["slope_negative_share"] = float(np.mean(sl[oos & np.isfinite(sl)] < 0)) if np.isfinite(sl[oos]).any() else None
        reads[nm] = ev
    n_dec = int((oos & np.isfinite(y_spy)).sum())
    rows = [IMP._p_crit(prim["p"], prim["t"], f"slope of the 63-session SPY excess log return on standardised VRP > 0 with "
                                                f"one-sided Hodrick p < 0.05 (slope {_s(prim['slope'], 4)})"),
            BW.all_constructions([(f"{nm} fit: OOS R^2 {_s(ev['oos_r2'], 4)} > 0", None if ev["oos_r2"] is None else ev["oos_r2"] > 0, False)
                                  for nm, ev in reads.items()], "expanding-window OOS R^2 against the prevailing mean > 0 under "
                                                                "both fit readings (SPY-only from 1993-01, spliced from 1990-02)"),
            BW.all_constructions([IMP._p_crit(ev["cw_p"], ev["cw_t"], f"{nm} fit: Clark-West (NW lag {T685_CW_LAG})")
                                  for nm, ev in reads.items()], "Clark-West one-sided p < 0.05 under both fit readings")]
    v, why, crit = CAL._judge(rows, n_dec, T685_MIN_N, "decisions")
    # reported
    rep = {}
    spy_tr = (dd >= T685_FIT_FROM[1]) & np.isfinite(y_spy)
    for nm, x_ in (("vix2_only", v2), ("rv_only", rv), ("parkinson_vrp", v2 - rv_pk)):
        s_ = _slope_hod(y_spy, x_, a, T685_H, r_spy, oos)
        fm, fb, _ = IMP.expanding_ols(x_, y_spy, pos, e, spy_tr, oos & np.isfinite(x_))
        rep[nm] = {"slope": s_["slope"], "t": s_["t"], "oos_r2": IMP.oos_stats(y_spy, fm, fb, oos, T685_CW_LAG)["oos_r2"]}
    lab = {m[:7]: k for k, m in enumerate(mdays)}
    plc = np.array([vrp[lab[f"{int(m[:4]) - 1:04d}{m[4:7]}"]] if f"{int(m[:4]) - 1:04d}{m[4:7]}" in lab else np.nan for m in mdays])
    s_ = _slope_hod(y_spy, plc, a, T685_H, r_spy, oos)
    fm, fb, _ = IMP.expanding_ols(plc, y_spy, pos, e, spy_tr, oos & np.isfinite(plc))
    rep["placebo_12m"] = {"slope": s_["slope"], "t": s_["t"], "oos_r2": IMP.oos_stats(y_spy, fm, fb, oos, T685_CW_LAG)["oos_r2"]}
    ex20 = ~((dd >= T685_EX2020[0]) & (dd <= T685_EX2020[1]))
    s_ = _slope_hod(y_spy, vrp, a, T685_H, r_spy, oos & ex20)
    fm, fb, _ = IMP.expanding_ols(vrp, y_spy, pos, e, spy_tr & ex20, oos & ex20)
    rep["ex_2020_03_06"] = {"slope": s_["slope"], "t": s_["t"], "oos_r2": IMP.oos_stats(y_spy, fm, fb, oos & ex20, T685_CW_LAG)["oos_r2"]}
    y21, a21, e21 = window_sum_targets(pos, T685_H_REP, r_spy)
    s_ = _slope_hod(y21, vrp, a21, T685_H_REP, r_spy, oos)
    fm, fb, _ = IMP.expanding_ols(vrp, y21, pos, e21, (dd >= T685_FIT_FROM[1]) & np.isfinite(y21), oos)
    o21 = IMP.oos_stats(y21, fm, fb, oos, 1)
    rep["h21"] = {"slope": s_["slope"], "t": s_["t"], "oos_r2": o21["oos_r2"], "cw_p": o21["cw_p"]}
    early_spy = (dd >= T685_FIT_FROM[1]) & (dd < T685_WIN[0])
    rep["1993_2009_spy"] = _slope_hod(y_spy, vrp, a, T685_H, r_spy, early_spy)
    m_sp = (dd >= T685_FIT_FROM[0]) & (dd < T685_WIN[0])
    r_spl = np.where(np.isfinite(r_spy), r_spy, r_gs)
    rep["1990_2009_spliced"] = _slope_hod(y_spl, vrp, a, T685_H, r_spl, m_sp)
    # OOS R^2 decomposition (SPY-only fit): each decision's share of sum(em^2 - eb^2) / sum(eb^2)
    fm, fb, _ = IMP.expanding_ols(vrp, y_spy, pos, e, spy_tr, oos)
    ok_ = oos & np.isfinite(y_spy) & np.isfinite(fm) & np.isfinite(fb)
    dl_ = (y_spy - fm) ** 2 - (y_spy - fb) ** 2
    den_ = float(np.sum((y_spy[ok_] - fb[ok_]) ** 2))
    if ok_.any() and den_ > 0:
        cj = np.where(ok_, dl_, -np.inf)
        k_ = int(np.argmax(cj))
        tot_ = float(np.sum(dl_[ok_])) / den_
        rep["oos_decomposition"] = {"total_neg_r2": tot_, "top_decision": mdays[k_], "top_contrib": float(dl_[k_]) / den_,
                                    "top_share": (float(dl_[k_]) / den_ / tot_) if tot_ != 0 else None}
    else:
        rep["oos_decomposition"] = None
    ex20w = ~((dd >= "2020-01") & (dd < "2020-07"))
    s_ = _slope_hod(y_spy, vrp, a, T685_H, r_spy, oos & ex20w)
    fm, fb, _ = IMP.expanding_ols(vrp, y_spy, pos, e, spy_tr & ex20w, oos & ex20w)
    rep["ex_2020_target_overlap"] = {"slope": s_["slope"], "t": s_["t"],
                                     "oos_r2": IMP.oos_stats(y_spy, fm, fb, oos & ex20w, T685_CW_LAG)["oos_r2"]}
    both = (dd >= T685_FIT_FROM[1]) & (dd <= T685_WIN[1]) & np.isfinite(y_spy) & np.isfinite(vrp)
    zb = (vrp[both] - vrp[both].mean()) / vrp[both].std(ddof=1)
    post = (dd[both] >= T685_WIN[0]).astype(float)
    Hd = hodrick_ols(y_spy[both], np.column_stack([np.ones(zb.size), zb, post, zb * post]), a[both], T685_H, r_spy)
    rep["slope_difference_post_minus_pre"] = {"d": float(Hd["beta"][3]), "t_hodrick": float(Hd["t"][3])}
    # trading arm (reported): SPY weight by expanding VRP tercile
    first_spy = int(np.argmax(np.isfinite(spy)))
    ra = np.r_[np.nan, spy[1:] / spy[:-1] - 1.0]
    rbs = np.r_[np.nan, B[1:] / B[:-1] - 1.0]
    gp = cal_gaps(gdays)
    hist_ok = (dd >= T685_FIT_FROM[0]) & np.isfinite(vrp)
    fills, wts = {}, []
    jj = np.where(oos)[0]
    for j in jj:
        prior = vrp[:j][hist_ok[:j]]
        if prior.size < T685_TERC_MIN:
            continue
        lo_c, hi_c = np.quantile(prior, [1 / 3, 2 / 3])
        w_ = T685_ARM_W[0] if vrp[j] < lo_c else (T685_ARM_W[2] if vrp[j] > hi_c else T685_ARM_W[1])
        fills[int(pos[j] + 1)] = w_
        wts.append(w_)
    arm = None
    if len(fills) > 24:
        idx = np.arange(first_spy, n)
        ra_, rb_, gp_ = ra[idx], rbs[idx], gp[idx]
        fl = {k - first_spy: w_ for k, w_ in fills.items()}
        Fv = np.array(sorted(fl), int)
        Fv = Fv[Fv < idx.size]
        vp = simulate(np.where(np.isfinite(ra_), ra_, 0.0), np.where(np.isfinite(rb_), rb_, 0.0), gp_, fl, T685_ARM_COST, 0.005)
        Bs = B[idx] / B[idx[0]]
        ex_ = period_excess(vp, Bs, Fv)
        bh_ = spy[idx][Fv[1:]] / spy[idx][Fv[:-1]] - Bs[Fv[1:]] / Bs[Fv[:-1]]
        t_ = BW.sharpe_diff_test(ex_, bh_, 12, 12, 5000 if n_boot is None else n_boot, SEED)
        arm = {"n": int(ex_.size), "sharpe_arm": t_.get("sharpe_a"), "sharpe_bh": t_.get("sharpe_b"), "diff": t_.get("diff"),
               "ci": t_.get("ci"), "mean_w": float(np.mean(wts))}
    rep["trading_arm"] = arm
    stat = {"n_decisions": n_dec, "window": [mdays[jj[0]], mdays[jj[-1]]] if jj.size else None, "slope": prim,
            "oos": reads, "reported": rep, "criteria": crit,
            "btz_note": "BTZ's daily-RV version was weaker (quarterly t 2.34, R^2 4.45%), stated before reading"}
    reason = (f"Stated before reading: Bollerslev-Tauchen-Zhou's daily-RV version was weaker (quarterly t 2.34, R^2 4.45%). "
              f"VRP = (VIX/100)^2/12 - 21-session sum of squared ^GSPC log returns at each month-end (VIX at t, 21:30 UTC), "
              f"target = SPY adjclose excess log return over DTB3 (bond-equivalent, prior print) from the close of t+1 over 63 "
              f"sessions; {n_dec} decisions {T685_WIN[0][:7]}..{T685_WIN[1][:7]}: slope {_s(prim['slope'], 4)} per sd, Hodrick t "
              f"{_s(prim['t'], 2)} (one-sided p {_f(prim['p'], 4)}; NW t {_s(prim['t_nw'], 2)}); OOS R^2 SPY-only fit "
              f"{_s(reads['spy_only']['oos_r2'], 4)} (CW t {_s(reads['spy_only']['cw_t'], 2)}, p {_f(reads['spy_only']['cw_p'], 4)}), "
              f"spliced fit {_s(reads['spliced']['oos_r2'], 4)} (CW t {_s(reads['spliced']['cw_t'], 2)}, p "
              f"{_f(reads['spliced']['cw_p'], 4)}); Campbell-Thompson-restricted (reported) {_s(reads['spy_only']['restricted_oos_r2'], 4)}. "
              f"Reported: VIX^2 alone slope t {_s(rep['vix2_only']['t'], 2)} OOS {_s(rep['vix2_only']['oos_r2'], 4)}; RV alone t "
              f"{_s(rep['rv_only']['t'], 2)} OOS {_s(rep['rv_only']['oos_r2'], 4)}; Parkinson VRP t {_s(rep['parkinson_vrp']['t'], 2)}; "
              f"12-month placebo t {_s(rep['placebo_12m']['t'], 2)} OOS {_s(rep['placebo_12m']['oos_r2'], 4)}; ex 2020-03..06 t "
              f"{_s(rep['ex_2020_03_06']['t'], 2)} OOS {_s(rep['ex_2020_03_06']['oos_r2'], 4)}; 21 sessions t {_s(rep['h21']['t'], 2)} "
              f"OOS {_s(rep['h21']['oos_r2'], 4)}; 1993-2009 (SPY) slope {_s(rep['1993_2009_spy']['slope'], 4)} Hodrick t "
              f"{_s(rep['1993_2009_spy']['t'], 2)}; 1990-2009 spliced slope {_s(rep['1990_2009_spliced']['slope'], 4)} Hodrick t "
              f"{_s(rep['1990_2009_spliced']['t'], 2)} (one-sided p {_f(rep['1990_2009_spliced']['p'], 4)}; NW t "
              f"{_s(rep['1990_2009_spliced'].get('t_nw'), 2)}, secondary); "
              + (f"the SPY-only OOS R^2 is dominated by the {od['top_decision'][:7]} decision, which contributes "
                 f"{_s(-od['top_contrib'], 4)} of {_s(-od['total_neg_r2'], 4)} ({_f(100 * od['top_share'], 0)}%); "
                 if (od := rep['oos_decomposition']) and od['top_share'] is not None else "")
              + f"dropping every decision whose target overlaps 2020-03..06 (2020-01..06 decisions) t "
              f"{_s(rep['ex_2020_target_overlap']['t'], 2)} OOS {_s(rep['ex_2020_target_overlap']['oos_r2'], 4)}; post-minus-pre "
              f"slope (pooled sd units) {_s(rep['slope_difference_post_minus_pre']['d'], 4)} (Hodrick t "
              f"{_s(rep['slope_difference_post_minus_pre']['t_hodrick'], 2)}); "
              + (f"tercile trading arm Sharpe {_s(arm['sharpe_arm'])} vs {_s(arm['sharpe_bh'])}, diff {_s(arm['diff'])} {_ci(arm['ci'])}"
                 if arm else "trading arm n/a")
              + f". VIX 1990-2003 is Cboe's reconstruction; month-end calendar named by the claim (rule 10) — {why}")
    return {"stat": stat, "n": n_dec, "verdict": v, "reason": reason}


def b13_volregime_a_vrp_predicts_spy(archive):
    """T-685: month-end VRP (VIX^2/12 - RV21) predicts the 63-session SPY excess log return, 2010-01..2026-06 decisions."""
    miss = _missing(archive, [VIX_B, GSPC_B, SPY_B, DTB3_B])
    if miss:
        return miss

    def run():
        gd, gc = CAL._daily(archive, GSPC_B, "close")
        sdays, sadj = CAL._daily(archive, SPY_B, "adjclose")
        acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
        return vrp_spy_test(gd, gc, gspc_hilo(archive), CAL._series(archive, VIX_B), dict(zip(sdays, sadj)), bill_index(gd, acc))

    r = CAL._cached(archive, ("t685",), run)
    return _out(r["stat"], r["n"], r["verdict"], r["reason"])


HARNESSES = {"b13_volregime_a_vol_target_spy": b13_volregime_a_vol_target_spy,
             "b13_volregime_a_vol_scaled_umd": b13_volregime_a_vol_scaled_umd,
             "b13_volregime_a_jump_model_spy": b13_volregime_a_jump_model_spy,
             "b13_volregime_a_vrp_predicts_spy": b13_volregime_a_vrp_predicts_spy}
THEORY_MAP = {"T-679": "b13_volregime_a_vol_target_spy", "T-681": "b13_volregime_a_vol_scaled_umd",
              "T-684": "b13_volregime_a_jump_model_spy", "T-685": "b13_volregime_a_vrp_predicts_spy"}
