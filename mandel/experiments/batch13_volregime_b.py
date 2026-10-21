"""
Batch 13, group ``volregime_b``: four volatility-regime claims from the 2026-10-20 web sweep (cluster "volregime").
=================================================================================================================

  * T-680  Downside-semivariance vs total-variance scaling of FF Mkt-RF, SMB, HML, RMW, CMA, UMD and AQR BAB (Wang-Yan).
           At each month-end t, w_t = min(3, c_t / RV_t) applied to month t+1's compounded return, RV the sum of
           squared (negative, for RVdown) daily factor returns over the 21 sessions ending at t, c_t from an expanding
           window (1963-07; BAB from its start) so that the managed series' volatility equals the unmanaged one's;
           10 bp per unit |w_t - w_{t-1}|. Hold months 2019-01..2026-07. Pass: pooled (equal-weight over the 7) Sharpe
           of downside-managed minus total-managed, lower 95% bound > 0 (paired studentized CBB, 12-month blocks, all
           factors jointly); pooled Sharpe of the 50/50 mix of downside-managed and unmanaged minus unmanaged > 0; DSR
           > 0.95 over 38 trials (7 x 2 x 2 here + T-388's 5 + T-389's 5). min_n 90 months.
  * T-682  Volatility-targeting gain by leverage effect. Position min(2, sigmaLR_t / sigma_t) (EWMA half-life 20 at
           close t over the asset's expanding-window realised vol), traded at close t+1 (FX: next noon print), 2 bp per
           unit of turnover for ETFs and 1 bp for FX, leverage at the bill rate. DiD = mean Sharpe gain over SPY, QQQ,
           IWM, EFA, EEM, HYG minus the mean over TLT, IEF, AGG, GLD, SLV, USO, DBC, DBA, UNG and one equal-weighted
           G10-vs-USD unit. Pass: DiD lower 95% bound > 0 over 2018-01..2026-09 (stationary 21-day time blocks drawn
           jointly x assets resampled within groups, 5,000 draws) and DiD > 0 over 2007-07..2017-12. min_n 2000 days.
  * T-683  SHAR vs EWMA(0.94) as the forecaster of a 10%-volatility target (cap 2x, decided at close t, traded at close
           t+1, 2 bp per unit of turnover) on SPY, QQQ, IWM, TLT, GLD, USO. Pass over 2015-01..2026-09: pooled 21-day
           QLIKE of SHAR below EWMA's with one-sided Diebold-Mariano p < 0.05; upper 95% bound of the pooled tracking
           loss [ln(21-session realised position vol / 0.10)]^2, SHAR minus EWMA, < 0 (paired studentized CBB,
           63-day blocks, assets jointly; Holm across SHAR, HAR, HAR-IV); pooled net Sharpe difference >= 0. min_n 2500.
  * T-690  Price-free ML on the ML program's non-leveraged US-listed ETFs: ridge and GBM refit each January, 63-session
           excess-return target, top-fifth minus bottom-fifth book in 3 overlapping monthly tranches, per-side costs
           and 50 bp a year borrow. Pass: some model with development DSR >= 0.95 (2019-01..2025-09, N = every ML
           program cell) AND a positive lockbox mean net return over 12 lockbox decisions from 2026-10. min_n 80.

Readings fixed before any run (each registration is silent or ambiguous on these; the conservative reading is taken
and repeated in the harness reasons):
  * "Lower 95% bound" / "upper 95% bound" = the end of the two-sided 95% interval (the house convention, stricter than
    a one-sided 95% bound). Studentized intervals are averaged over 5 bootstrap seeds and escalated to 25 seeds when
    Monte Carlo error cannot resolve them against the threshold (``batch6b_bw.mc_escalate``). Bills: DTB3 converted
    to its investment yield and accrued daily at the print dated strictly before each day (``batch6c_rates.Accrual``,
    "bey"), as in ``batch13_volregime_a``.
  * T-680: c_t is solved WITH the cap: the c for which sd(min(3, c / RV_j) x R_{j+1}) over the holds completed by t
    equals sd(R_{j+1}) over the same holds (bisection; a capped managed series is what the claim calls "the managed
    series"); at least 24 completed holds, else no weight. Rule 12: a French or AQR return for day t is archived at
    21:00 UTC, after the month-end close the weight trades at, so the claim (the 21 sessions through t, the live
    proxy; holds through month t in c_t) is read together with the previous-close reading (the 21 sessions through
    t-1; holds through month t-1); every criterion needs both. BAB's archive carries non-session weekdays (US
    holidays, about -1 bp each, the financing leg): a session is a CRSP trading day of the French momentum file, and
    a non-session return is compounded into the next session's, so monthly returns are unchanged. Each factor's first
    weight pays the cost of entering from 0. The pooled 50/50 mix = 0.5 x downside-managed net + 0.5 x unmanaged (its
    turnover is half the managed one's, charged through the managed leg). DSR is judged on two series and needs both
    (rule 11 spirit, as T-679): (a) the pooled downside-managed net book (equal-weight mean of the 7 managed series),
    (b) the pooled downside-minus-total net difference; trial-Sharpe variance = the 28 computed trials (7 factors x 2
    scalers x 2 cost levels) floored at 1/(T-1); T-388's and T-389's 10 enter the count only. The ETF arm (reported)
    decides at the month-end close and fills at the next close (drift tracked, bills at the bill rate).
  * T-682: daily rebalancing to the target; turnover |target - drifted weight|, charged on the first return at the new
    weight. sigma_t^2 = EWMA of squared daily excess returns (half-life 20, weights normalised from the asset's first
    return), sigmaLR_t^2 = the mean of every squared daily excess return through t (no demeaning, the same estimator
    as the EWMA's); both need 63 returns, before which the asset has no scaled (or unscaled) observation. The FX unit
    is read two ways and every criterion needs both (rule 11): (a) the equal-weighted nine-currency basket as one
    asset with its own scaler, (b) each currency scaled on its own volatility, the unit's gain = the mean of the nine
    currencies' gains. FX excess return on print day u = S_u / S_{u-1} - 1 + (r_ccy - r_USD)(M - 1) x calendar days /
    36500, M the month of u (the OECD monthly average of the previous month, one month lagged as T-368); EUR and GBP
    rates stop at 2026-01 and JPY at 2026-07, so later months carry the last print forward (flagged). Days where any
    of the nine prints is missing are dropped from the FX calendar. Every unit's daily series is compounded onto the
    NYSE session calendar of SPY for the joint bootstrap, and every Sharpe (252 a year) is taken on that calendar. The
    DiD interval is the percentile interval of the joint (stationary time blocks, mean 21, x assets with replacement
    within each group) bootstrap. The 2007-07..2017-12 DiD is the point estimate over each unit's defined days.
  * T-683: forecasts are of the summed squared close-to-close log returns (adjclose) over sessions t+1..t+21; HAR
    regressors r_t^2, the 5- and 22-session means of r^2; SHAR splits r_t^2 by the sign of r_t (Patton-Sheppard's
    daily-data form); HAR-IV adds (IV_t / 100)^2 x 21 / 252 for the matched Cboe index. OLS on levels, refitted at
    each month-end on every row s >= window start + 22 whose target ended by that close (s + 21 <= t); window start =
    max(2004-01-02, first bar); a fit needs 500 rows (HAR-IV 250 rows with the index, counted from the index's first
    print, else it falls back to HAR). Insanity filter (Bollerslev-Patton-Quaedvlieg): a forecast outside [min, max]
    of the fit's targets is replaced by their mean. EWMA(0.94) forecast = 21 x sigma^2_t (RiskMetrics, seeded with
    the first 22 sessions' mean). Position w_t = min(2, 0.10 / sqrt(252 F_t / 21)), held over session t+2 (filled at
    close t+1); excess return w x (simple excess over bills), leverage at the bill rate. Tracking: every 21-session
    window inside 2015-01..2026-09 (rule 10: the claim's non-overlapping grid has 21 phases, so all overlapping
    windows are pooled and the per-phase range reported; 63-day blocks exceed twice the overlap); realised position
    vol = sqrt(252 / 21 x sum (w x log return)^2). The tracking criterion needs BOTH the upper bound of the SHAR - EWMA
    interval < 0 AND its Holm-adjusted (SHAR, HAR, HAR-IV) one-sided studentized p < 0.05. QLIKE gate: every forecast
    origin in the window, pooled over assets per day, Diebold-Mariano with a Bartlett long-run variance at bandwidth
    63 (the primary's block length; conservative against the 21-day overlap). Reported only: MSM (T-569, k = 4)
    fitted once per asset on 2004..2014 and filtered forward (a monthly MSM refit is too slow here), Garman-Klass and
    60-minute-bar cross-checks, constant weight at each forecaster's mean exposure, the Bollerslev et al.
    quadratic-utility gain at SR 0.4 and risk aversion 2.
  * T-690: universe = mandel.ml.fetch's EQUITY_ETF + BOND_ETF + COMMOD_ETF less TQQQ, SQQQ, IBIT and ETHA (37), an
    ETF entering a decision once it has 252 local sessions and an entry open. On inspection the registered 20-day
    RegSHO short-volume ratio cannot be built: the finra-regsho-cnms bundles keep point-in-time S&P 500 members only,
    no ETF row. That input stays an all-missing (constant) column, and because the model tested is then narrower
    than the registered one, the development criterion is computed and reported but cannot decide (rule 9); the
    lockbox (12 decisions from the 2026-10 month-end) does not exist yet, so the verdict is inconclusive whatever
    the development numbers say. Nothing after 2025-12-31 is loaded (the T-578 window and the lockbox stay out).
    Decision time = the 16:00 New York close of each month's last session; FINRA short interest (log level,
    changePercent, days to cover) enters at its available_at (23:59:59 UTC of publication), a Cboe close at its
    21:30 UTC available_at (so the decision uses the previous day's index), FOMC (14:00 ET, scheduled meetings
    only) and CPI (08:30 ET) as calendar days to the next one after the decision, uncapped. Realised vol, downside
    semivariance (x 252/63) and skewness over 63 sessions; volume and dollar-volume z = (20-session mean of log(1 +
    v) - its 252-session mean) / its 252-session sd. Local bars are unadjusted, so two price readings are run and
    a model passes development only under both (rule 11): dividend-adjusted (opens and closes x the archived
    Yahoo adjclose/close factor; SMH, ARKK and FXI have no archived bundle and stay raw) and raw (as worded).
    Target = log(open[i+64] / open[i+1]) minus the DTB3 log accrual between those opens; the models
    (mandel.ml.train.make_model ridge / gbm, fixed hyperparameters) fit the target over its trailing scale
    (20-session sd x sqrt 63, clipped at +-10: T-578's convention) on every (session, ETF) row from 2018-01-01 whose
    exit open fell before 1 January of the decision year (purged); missing features take the training median. Book:
    long the top floor(N/5), short the bottom floor(N/5) by prediction; the tranche formed at decision k enters at
    the next open and exits at the open after decision k + 3, 1/3 of capital each, equal weight and buy-and-hold
    inside a leg; book month j = the open after decision j to the open after decision j + 1, labelled 2019-01..
    2025-09 (81); the first two months hold one and two tranches (the rest in cash) and the last two tranches'
    later months are not scored (they reach 2026). 1 bp per unit per side on both legs (entry 1/3 per leg, exit at
    the leg's value), borrow 50 bp a year on the short leg's value. DSR = mandel.ml.train.deflated_sharpe of the
    monthly per-period Sharpe at N = 766 with the book's skew and kurtosis (the ML program's estimator); the minimum
    annual Sharpe for 0.95 (skew 0, kurtosis 3) is computed before any fit. Reported: family ablations (no SI, no
    implied vol) as the net-contribution measure (no per-feature drop-one refits), GBM gain shares and ridge
    standardised coefficients of the 2025 fit, the always-long and days-to-cover (long the lowest fifth) baselines.
  * Rule 10: T-680 and T-690 decide at calendar month-ends (named by the claims), T-682 and T-683 daily; T-683's
    tracking windows pool every phase. Below trial.min_n the verdict is never supported and a failing criterion
    counts only when decisive (``batch6c_cal._judge``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from statistics import NormalDist

import numpy as np

from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch6c_rates as RATES
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch13_volregime_a as VRA
from mandel.experiments.batch6_surf import _out
from mandel.validation.backtest_eval import _hac_var, sharpe_ratio

SEED = 0
DSR_PASS = 0.95
_N = NormalDist()
Z975, Z80 = 1.959964, 0.841621

DTB3_B = "fred-DTB3"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
BAB_B = "aqr-bab-daily"
FXS_B = "fx-spot-g10"
FXR_B = "fx-rates-3m"


def dh(sym: str) -> str:
    return "daily-history-" + sym


def cboe(sym: str) -> str:
    return f"cboe-{sym}-history"


# T-680
T680_FACTORS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD", "BAB")
T680_WIN = ("2019-01", "2026-07")
T680_REPL = ("1963-08", "2018-12")
T680_START = "1963-07"
T680_CAP = 3.0
T680_RV = 21
T680_COST = 0.0010
T680_COST_REP = 0.0030
T680_MIN_HIST = 24
T680_BLOCK = 12
T680_NBOOT = 2000
T680_MIN_N = 90
T680_TRIALS = 28 + 5 + 5
T680_ETFS = ("SPY", "QQQ", "IWM")


# ================================================================================================ small helpers ==

_f, _s, _pc, _ci = VRA._f, VRA._s, VRA._pc, VRA._ci


def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, names)


def _sr(x, ppy: float) -> float | None:
    return VRA._sr(x, ppy)


def _sr_pp(x) -> float | None:
    return VRA._sr_pp(x)


def _pooled_sr_stat(k: int):
    """``batch6b_bw._stud`` statistic over 2k paired columns (A_1..A_k, B_1..B_k): the mean over i of per-period
    Sharpe(A_i) - Sharpe(B_i) (population moments) and its s.e. from the mean of the k delta-method influence series
    (fixed-bandwidth Bartlett long-run variance), so the k pairs are resampled jointly."""
    def stat(*args):
        cols, bw = args[:-1], args[-1]
        n = cols[0].shape[1]
        D = 0.0
        Z = 0.0
        for i in range(k):
            A, B = cols[i], cols[k + i]
            ma, mb = A.mean(axis=1), B.mean(axis=1)
            ga, gb = (A * A).mean(axis=1), (B * B).mean(axis=1)
            va, vb = np.maximum(ga - ma ** 2, 1e-300), np.maximum(gb - mb ** 2, 1e-300)
            D = D + (ma / np.sqrt(va) - mb / np.sqrt(vb)) / k
            Z = Z + ((ga / va ** 1.5)[:, None] * (A - ma[:, None]) - (ma / (2 * va ** 1.5))[:, None] * (A * A - ga[:, None])
                     - (gb / vb ** 1.5)[:, None] * (B - mb[:, None]) + (mb / (2 * vb ** 1.5))[:, None] * (B * B - gb[:, None])) / k
        return D, np.sqrt(_hac_var(Z, bw) / n)
    return stat


def pooled_sharpe_diff_test(A: Sequence, B: Sequence, ppy: int, block: int, n_boot: int, seed: int = SEED) -> dict:
    """Pooled (equal-weight mean over pairs) annualised Sharpe(A_i) - Sharpe(B_i) with a paired studentized circular
    block bootstrap of all pairs jointly: diff, se, two-sided 95% CI, p (H0: diff <= 0), p_lt (H0: diff >= 0)."""
    A = [np.asarray(a, float) for a in A]
    B = [np.asarray(b, float) for b in B]
    k, n = len(A), A[0].size
    out = {"n": int(n), "diff": float(np.mean([sharpe_ratio(a, ppy) - sharpe_ratio(b, ppy) for a, b in zip(A, B)])),
           "se": None, "ci": [None, None], "p": None, "p_lt": None}
    if n < 8:
        return out
    c = math.sqrt(ppy) * math.sqrt((n - 1) / n)
    r = BW._stud(_pooled_sr_stat(k), A + B, block, n_boot, seed)
    sc = lambda v: [None if x is None else x * c for x in v]
    out.update(diff=r["est"] * c, se=r["se"] * c, ci=sc(r["ci"]), ci_pct=sc(r.get("ci_pct", [None, None])), p=r["p"],
               p_lt=r["p_lt"], block=r["block"])
    return out


def pooled_boot_se(A: Sequence, B: Sequence, ppy: int, block: int, n_boot: int, seed: int = SEED) -> float:
    """sd of the pooled annualised Sharpe difference over joint circular-block resamples (the power calculation)."""
    A = np.stack([np.asarray(a, float) for a in A])
    B = np.stack([np.asarray(b, float) for b in B])
    n = A.shape[1]
    rng = np.random.default_rng(seed)
    idx = CAL._boot_idx(rng, n, block, n_boot)
    Ar, Br = A[:, idx], B[:, idx]
    sa = Ar.mean(-1) / np.maximum(Ar.std(-1, ddof=1), 1e-300)
    sb = Br.mean(-1) / np.maximum(Br.std(-1, ddof=1), 1e-300)
    return float(((sa - sb).mean(0) * math.sqrt(ppy)).std(ddof=1))


def pooled_sharpe_pair(A, B, ppy: int, block: int, n_boot: int, reps: int | None = None) -> dict:
    """``pooled_sharpe_diff_test`` over 5 seeds, escalated to 25 when the lower end cannot be resolved against 0."""
    return BW.mc_escalate(lambda seed: pooled_sharpe_diff_test(A, B, ppy, block, n_boot, seed),
                          lambda t: BW._ci_crit(t, "gt", 0.0, "")[1], reps, SEED)


def conj(rows: Sequence[tuple], label: str) -> tuple:
    """A criterion that needs every part: passes when all pass, fails when any part fails (decisive when a failing part
    is), undecided otherwise."""
    oks = [r[1] for r in rows]
    if any(o is False for o in oks):
        ok = False
    elif all(o is True for o in oks):
        ok = True
    else:
        ok = None
    dec = any(r[1] is False and bool(r[2]) for r in rows)
    return f"{label}: " + "; ".join(r[0] for r in rows), ok, dec


# ====================================================================================== T-680 downside scaling ==

def sessions_only(days: Sequence[str], r, sessions: set) -> tuple:
    """Restrict a daily return series to ``sessions``; a non-session day's return is compounded into the next
    session's (monthly compounded returns are unchanged unless a month ends on a non-session day)."""
    out_d, out_r = [], []
    carry = 1.0
    for d, x in zip(days, np.asarray(r, float)):
        if d in sessions:
            out_d.append(d)
            out_r.append(carry * (1.0 + x) - 1.0)
            carry = 1.0
        else:
            carry *= 1.0 + x
    return out_d, np.array(out_r, float)


def month_rv(r, last, lag: int, look: int = T680_RV) -> dict:
    """{kind: RV at each month-end}: kind 'tot' = sum r^2, 'down' = sum r^2 [r < 0], 'up' = sum r^2 [r > 0] over the
    ``look`` daily returns ending ``lag`` sessions before the month's last session (NaN when the window runs before
    the data)."""
    r = np.asarray(r, float)
    sq = r * r
    cs = {"tot": np.r_[0.0, np.cumsum(sq)], "down": np.r_[0.0, np.cumsum(np.where(r < 0, sq, 0.0))],
          "up": np.r_[0.0, np.cumsum(np.where(r > 0, sq, 0.0))]}
    last = np.asarray(last, int)
    e = last - lag + 1
    s = e - look
    ok = s >= 0
    out = {}
    for k, c in cs.items():
        v = np.full(last.size, np.nan)
        v[ok] = c[e[ok]] - c[s[ok]]
        out[k] = v
    return out


def solve_c(U, Rn, j0: int, jmax, cap: float = T680_CAP, min_hist: int = T680_MIN_HIST, iters: int = 60) -> np.ndarray:
    """c at each decision m: the root of sd(min(cap, c U_j) Rn_j) = sd(Rn_j) over holds j0 <= j < jmax[m] with finite
    U and Rn (bisection in log c); NaN with fewer than ``min_hist`` such holds. U_j = 1 / RV at decision j, Rn_j the
    return of the hold that decision j opens."""
    U, Rn = np.asarray(U, float), np.asarray(Rn, float)
    jmax = np.asarray(jmax, int)
    J, M = U.size, jmax.size
    good = np.isfinite(U) & np.isfinite(Rn) & (U > 0)
    jj = np.arange(J)
    mask = (jj[None, :] >= j0) & (jj[None, :] < jmax[:, None]) & good[None, :]
    cnt = mask.sum(1)
    out = np.full(M, np.nan)
    rows = np.where(cnt >= min_hist)[0]
    if rows.size == 0:
        return out
    mk = mask[rows].astype(float)
    nk = cnt[rows].astype(float)
    U0 = np.where(good, U, 0.0)
    R0 = np.where(good, Rn, 0.0)

    def sd_rows(X):
        mu = (X * mk).sum(1) / nk
        return np.sqrt((((X - mu[:, None]) ** 2) * mk).sum(1) / (nk - 1.0))

    target = sd_rows(np.broadcast_to(R0, (rows.size, J)))
    umax = np.where(mk > 0, U0[None, :], 0.0).max(1)
    umin = np.where(mk > 0, U0[None, :], np.inf).min(1)
    lo = np.log(1e-6 * cap / umax)
    hi = np.log(10.0 * cap / umin)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        g = sd_rows(np.minimum(cap, np.exp(mid)[:, None] * U0[None, :]) * R0[None, :])
        up = g < target
        lo = np.where(up, mid, lo)
        hi = np.where(up, hi, mid)
    out[rows] = np.exp(0.5 * (lo + hi))
    return out


def managed_net(w, R, cost: float) -> np.ndarray:
    """Net return of hold month m + 1 = w_m R_{m+1} - cost |w_m - w_{m-1}| (entry from 0), aligned on months."""
    return VRA.scaled_returns(w, R, cost)


def factor_family(days: Sequence[str], r, start_month: str, costs: Sequence[float] = (T680_COST, T680_COST_REP)) -> dict:
    """One factor under both rule-12 readings: month labels, month returns R, and per reading and scaler the weights
    (decided at each month-end), c and the net series at each cost (aligned on hold months)."""
    labs, last, R = VRA.calendar_months(days, r)
    j0 = next((j for j, m in enumerate(labs) if m >= start_month), len(labs))
    out = {"labs": labs, "R": R, "last": last}
    J = len(labs)
    Rn = np.r_[R[1:], np.nan]                       # the hold month that decision j opens
    for rd, lag in (("close", 0), ("prev", 1)):
        rv = month_rv(r, last, lag)
        jmax = np.arange(J) - lag                     # holds j with j + 1 <= m - lag are complete at decision m
        out[rd] = {}
        for sc in ("down", "tot", "up"):
            with np.errstate(divide="ignore"):
                U = np.where(rv[sc] > 0, 1.0 / rv[sc], np.nan)
            c = solve_c(U, Rn, j0, jmax)
            w = np.minimum(T680_CAP, c * U)
            w = np.where(np.arange(J) >= j0, w, np.nan)
            out[rd][sc] = {"w": w, "c": c, "net": {cst: managed_net(w, R, cst) for cst in costs}}
    return out


def load_factors(archive) -> dict:
    """{factor: (days, daily decimal returns)}; BAB restricted to the French momentum file's sessions."""
    out = {}
    for f in ("Mkt-RF", "SMB", "HML", "RMW", "CMA"):
        s = CAL._series(archive, FF5_B, f)
        ds = sorted(s)
        out[f] = (ds, np.array([s[d] for d in ds]) / 100.0)
    m = CAL._series(archive, MOM_B, "Mom")
    md = sorted(m)
    out["UMD"] = (md, np.array([m[d] for d in md]) / 100.0)
    b = CAL._series(archive, BAB_B, "bab_usa")
    bd = sorted(b)
    out["BAB"] = sessions_only(bd, np.array([b[d] for d in bd]), set(md))
    return out


def _win_mask(labs: Sequence[str], win: tuple) -> np.ndarray:
    return np.array([win[0] <= m <= win[1] for m in labs])


def _aligned(fam: dict, rd: str, sc: str, cost: float, win: tuple) -> dict:
    """{factor: series over the window's hold months} plus the common labels (every factor must cover them)."""
    out = {}
    labs0 = None
    for f, F in fam.items():
        m = _win_mask(F["labs"], win)
        labs = [x for x, k in zip(F["labs"], m) if k]
        x = F["R"][m] if sc == "raw" else F[rd][sc]["net"][cost][m]
        out[f] = (labs, x)
        labs0 = labs if labs0 is None else labs0
    common = sorted(set.intersection(*(set(v[0]) for v in out.values())))
    res = {}
    for f, (labs, x) in out.items():
        pos = {l_: i for i, l_ in enumerate(labs)}
        res[f] = np.array([x[pos[l_]] for l_ in common], float)
    return {"labs": common, "x": res}


def etf_arm(days: Sequence[str], adj, B) -> dict:
    """Reported ETF arm: month-end decisions on the 21 daily excess returns through the decision close, filled at the
    next close (drift, 10 bp per unit of turnover, bill-rate leverage); c from holds completed by the decision."""
    adj = np.asarray(adj, float)
    n = len(days)
    ra = np.r_[np.nan, adj[1:] / adj[:-1] - 1.0]
    rb = np.r_[np.nan, B[1:] / B[:-1] - 1.0]
    e = ra - rb
    gp = VRA.cal_gaps(days)
    mdec = VRA.month_ends(days)
    mdec = mdec[mdec + 1 < n]
    F = mdec + 1
    f_hold = adj[F[1:]] / adj[F[:-1]] - B[F[1:]] / B[F[:-1]]
    lab = [days[f][:7] for f in F[:-1]]
    e0 = np.where(np.isfinite(e), e, 0.0)
    rv = month_rv(e0, mdec, 0)
    nh = f_hold.size
    jmax = np.array([int(np.searchsorted(F[1:nh + 1], d, side="right")) for d in mdec])
    out = {"labels": lab, "bh": f_hold}
    for sc in ("down", "tot"):
        with np.errstate(divide="ignore"):
            U = np.where(rv[sc] > 0, 1.0 / rv[sc], np.nan)
        c = solve_c(U[:nh], f_hold, 0, np.minimum(jmax, nh))
        w = np.minimum(T680_CAP, c * U)
        ok = np.isfinite(w)
        fills = {int(d + 1): float(x) for d, x in zip(mdec[ok], w[ok])}
        ex = VRA.period_excess(VRA.simulate(ra, rb, gp, fills, T680_COST, 0.0), B, F)
        if fills:
            ex = np.where(F[:-1] >= min(fills), ex, np.nan)
        out[sc] = ex
    return out


def semivar_scaling_test(fac: dict, etfs: dict | None = None, n_boot: int = T680_NBOOT, reps: int | None = None) -> dict:
    """T-680 core on {factor: (days, returns)} (and {sym: (days, adj, B)} for the reported ETF arm)."""
    fam = {f: factor_family(d, r, "0000-00" if f == "BAB" else T680_START) for f, (d, r) in fac.items()}
    names = list(fam)
    res = {}
    for rd in ("close", "prev"):
        dn = _aligned(fam, rd, "down", T680_COST, T680_WIN)
        tt = _aligned(fam, rd, "tot", T680_COST, T680_WIN)
        raw = _aligned(fam, rd, "raw", T680_COST, T680_WIN)
        if not (dn["labs"] == tt["labs"] == raw["labs"]):
            raise ValueError("factor windows disagree")
        bad = [f for f in names if not (np.isfinite(dn["x"][f]).all() and np.isfinite(tt["x"][f]).all())]
        A = [dn["x"][f] for f in names]
        Bt = [tt["x"][f] for f in names]
        U = [raw["x"][f] for f in names]
        res[rd] = {"labs": dn["labs"], "A": A, "B": Bt, "U": U, "bad": bad}
    n = len(res["close"]["labs"])
    if res["close"]["bad"] or res["prev"]["bad"] or n < 8:
        return {"n": n, "fail": f"managed series incomplete in the window: {res['close']['bad'] or res['prev']['bad']}"}
    # power, computed before the test is run or read
    se_b = pooled_boot_se(res["close"]["A"], res["close"]["B"], 12, T680_BLOCK, n_boot, SEED)
    mde = (Z975 + Z80) * se_b
    for rd, x in res.items():
        x["sd"] = pooled_sharpe_pair(x["A"], x["B"], 12, T680_BLOCK, n_boot, reps)
        mix = [0.5 * a + 0.5 * u for a, u in zip(x["A"], x["U"])]
        x["mix"] = float(np.mean([sharpe_ratio(m_, 12) - sharpe_ratio(u, 12) for m_, u in zip(mix, x["U"])]))
        x["pooled_sr"] = {k: float(np.mean([sharpe_ratio(v_, 12) for v_ in x[c_]])) for k, c_ in
                          (("down", "A"), ("tot", "B"), ("unmanaged", "U"))}
        book = np.mean(np.stack(x["A"]), 0)
        diff = np.mean(np.stack(x["A"]) - np.stack(x["B"]), 0)
        fam_sr = []
        for f in names:
            for sc in ("down", "tot"):
                for cst in (T680_COST, T680_COST_REP):
                    m = _win_mask(fam[f]["labs"], T680_WIN)
                    fam_sr.append(_sr_pp(fam[f][rd][sc]["net"][cst][m]))
        x["dsr_book"] = MOM.family_dsr(book, fam_sr, T680_TRIALS)
        x["dsr_diff"] = MOM.family_dsr(diff, fam_sr, T680_TRIALS)
        x["per"] = {}
        for f, a, b in zip(names, x["A"], x["B"]):
            t = BW.sharpe_diff_test(a, b, 12, T680_BLOCK, n_boot, SEED)
            x["per"][f] = {"diff": t.get("diff"), "p": t.get("p"), "sharpe_down": t.get("sharpe_a"), "sharpe_tot": t.get("sharpe_b")}
        hp = CAL._holm({f: v["p"] for f, v in x["per"].items()})
        for f in names:
            x["per"][f]["p_holm"] = hp[f]
    # reported: 30 bp, the upside placebo, the in-sample replication, the ETF arm
    c = res["close"]
    a30 = _aligned(fam, "close", "down", T680_COST_REP, T680_WIN)
    b30 = _aligned(fam, "close", "tot", T680_COST_REP, T680_WIN)
    rep = {"cost30": float(np.mean([sharpe_ratio(a30["x"][f], 12) - sharpe_ratio(b30["x"][f], 12) for f in names]))}
    up = _aligned(fam, "close", "up", T680_COST, T680_WIN)
    rep["placebo_up_minus_tot"] = float(np.mean([sharpe_ratio(up["x"][f], 12) - sharpe_ratio(c["B"][i], 12)
                                                 for i, f in enumerate(names)]))
    rd_ = _aligned(fam, "close", "down", T680_COST, T680_REPL)
    rt_ = _aligned(fam, "close", "tot", T680_COST, T680_REPL)
    ok = np.ones(len(rd_["labs"]), bool)
    for f in names:
        ok &= np.isfinite(rd_["x"][f]) & np.isfinite(rt_["x"][f])
    if ok.sum() > 24:
        t = pooled_sharpe_diff_test([rd_["x"][f][ok] for f in names], [rt_["x"][f][ok] for f in names], 12, T680_BLOCK,
                                    n_boot, SEED)
        lb = [l_ for l_, k in zip(rd_["labs"], ok) if k]
        rep["replication"] = {"n": int(ok.sum()), "span": [lb[0], lb[-1]], "diff": t["diff"], "ci": t["ci"],
                              "per": {f: _s(sharpe_ratio(rd_["x"][f][ok], 12) - sharpe_ratio(rt_["x"][f][ok], 12))
                                      for f in names}}
    if etfs:
        arms = {}
        for sym, (d, adj, Bi) in etfs.items():
            E = etf_arm(d, adj, Bi)
            m = _win_mask(E["labels"], T680_WIN) & np.isfinite(E["down"]) & np.isfinite(E["tot"])
            arms[sym] = {"n": int(m.sum()), "down": _sr(E["down"][m], 12), "tot": _sr(E["tot"][m], 12),
                         "bh": _sr(E["bh"][m], 12)}
        rep["etf"] = arms
    wd = {f: float(np.nanmean(fam[f]["close"]["down"]["w"][np.where(_win_mask(fam[f]["labs"], T680_WIN))[0] - 1]))
          for f in names}
    wt = {f: float(np.nanmean(fam[f]["close"]["tot"]["w"][np.where(_win_mask(fam[f]["labs"], T680_WIN))[0] - 1]))
          for f in names}
    capd = {f: float(np.nanmean(fam[f]["close"]["down"]["w"][np.where(_win_mask(fam[f]["labs"], T680_WIN))[0] - 1] >= T680_CAP - 1e-12))
            for f in names}
    return {"n": n, "labs": c["labs"], "power": {"boot_se": se_b, "mde_80": mde}, "res": res, "rep": rep, "names": names,
            "mean_w_down": wd, "mean_w_tot": wt, "cap_share_down": capd}


def b13_volregime_b_semivar_factors(archive):
    """T-680: downside-semivariance vs total-RV scaling of 7 factors (min(3, c/RV)), pooled Sharpe, 2019-01..2026-07."""
    miss = _missing(archive, [FF5_B, MOM_B, BAB_B, DTB3_B])
    if miss:
        return miss
    fac = load_factors(archive)
    etfs = {}
    acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
    for s in T680_ETFS:
        if B7C._has(archive, dh(s)):
            d, adj = CAL._daily(archive, dh(s), "adjclose")
            etfs[s] = (d, adj, VRA.bill_index(d, acc))
    R = semivar_scaling_test(fac, etfs)
    n = R["n"]
    if "fail" in R:
        return _out({"n": n}, n, "inconclusive", R["fail"])
    res, rep = R["res"], R["rep"]
    lbl = {"close": "decision-close reading (as worded)", "prev": "previous-close reading"}
    rows = [BW.all_constructions([BW._ci_crit(res[rd]["sd"], "gt", 0.0, lbl[rd]) for rd in ("close", "prev")],
                                 "pooled Sharpe(downside-managed) - Sharpe(total-managed), net of 10 bp per unit weight change, "
                                 "2019-01..2026-07, lower 95% bound > 0 (paired studentized CBB, 12-month blocks, 7 factors "
                                 "jointly) under both rule-12 readings"),
            BW.all_constructions([(f"{lbl[rd]} ({_s(res[rd]['mix'])})", res[rd]["mix"] > 0, res[rd]["mix"] <= 0)
                                  for rd in ("close", "prev")],
                                 "pooled Sharpe(50/50 downside-managed + unmanaged) - Sharpe(unmanaged) point estimate > 0 "
                                 "under both rule-12 readings"),
            BW.all_constructions([MOM.dsr_row(res[rd][k], f"{lbl[rd]}: {nm}") for rd in ("close", "prev")
                                  for k, nm in (("dsr_book", "pooled downside-managed book"),
                                                ("dsr_diff", "pooled downside-minus-total difference"))],
                                 f"DSR > {DSR_PASS} over {T680_TRIALS} trials (7 factors x 2 scalers x 2 costs + T-388's 5 + "
                                 f"T-389's 5), both series, both rule-12 readings (rules 11, 12)")]
    v, why, crit = CAL._judge(rows, n, T680_MIN_N, "months")
    c, p = res["close"], res["prev"]
    sdc, sdp = c["sd"], p["sd"]
    per = c["per"]
    stat = {"n_months": n, "window": [R["labs"][0], R["labs"][-1]], "power": R["power"],
            "readings": {rd: {"pooled_diff": {k: x["sd"].get(k) for k in ("diff", "ci", "ci_mc_se", "p", "p_lt", "reps")},
                              "mix_minus_unmanaged": x["mix"], "pooled_sharpe": x["pooled_sr"],
                              "dsr_book": x["dsr_book"], "dsr_diff": x["dsr_diff"],
                              "per_factor": x["per"]} for rd, x in res.items()},
            "mean_weight_down": R["mean_w_down"], "mean_weight_tot": R["mean_w_tot"], "cap_share_down": R["cap_share_down"],
            "reported": rep, "criteria": crit, "rule10": "calendar named by the claim (month-end decisions)"}
    repl = rep.get("replication") or {}
    etf = rep.get("etf") or {}
    reason = (f"POWER (computed before the result): bootstrap SE of the pooled 2019-01..2026-07 Sharpe difference "
              f"{R['power']['boot_se']:.3f} ({n} hold months, 12-month blocks), so the minimum detectable pooled difference "
              f"at 80% power is {R['power']['mde_80']:.3f}. RESULT: French FF5 + Mom and AQR BAB daily (revised paper "
              f"factors, not point in time; pre-cost portfolios, so only the scaling turnover is charged), w = min(3, c_t / RV) "
              f"with c_t solved on the capped series from an expanding window (1963-07; BAB from 1930-12): pooled Sharpe "
              f"downside-managed minus total-managed {_s(sdc.get('diff'))} {_ci(sdc.get('ci'))} (previous-close reading "
              f"{_s(sdp.get('diff'))} {_ci(sdp.get('ci'))}); per factor (Sharpe down / total, diff, Holm p) "
              + ", ".join(f"{f} {_s(x['sharpe_down'], 2)}/{_s(x['sharpe_tot'], 2)} {_s(x['diff'], 2)} p {_f(x['p_holm'], 2)}"
                          for f, x in per.items())
              + f"; pooled Sharpe downside-managed {_s(c['pooled_sr']['down'], 3)}, total-managed "
              f"{_s(c['pooled_sr']['tot'], 3)}, unmanaged {_s(c['pooled_sr']['unmanaged'], 3)}"
              f"; 50/50 mix minus unmanaged {_s(c['mix'])} (prev {_s(p['mix'])}); DSR (38 trials) downside book "
              f"{VRA._dsr_brief(c['dsr_book'])}, difference {VRA._dsr_brief(c['dsr_diff'])}; mean downside weight "
              + ", ".join(f"{f} {x:.2f}" for f, x in R["mean_w_down"].items())
              + " (share at the cap: " + ", ".join(f"{f} {x:.0%}" for f, x in R["cap_share_down"].items()) + "). Reported: "
              f"30 bp cost pooled difference {_s(rep['cost30'])}; upside-semivariance placebo minus total "
              f"{_s(rep['placebo_up_minus_tot'])}; in-sample "
              + (f"{repl['span'][0]}..{repl['span'][1]} ({repl['n']} months) pooled difference {_s(repl['diff'])} "
                 f"{_ci(repl['ci'])} (per factor " + ", ".join(f"{f} {x}" for f, x in repl["per"].items()) + ")"
                 if repl else "replication n/a")
              + "; ETF arm 2019-01..2026-07 (Sharpe down / total / buy-and-hold) "
              + (", ".join(f"{s_} {_s(x['down'], 2)}/{_s(x['tot'], 2)}/{_s(x['bh'], 2)}" for s_, x in etf.items()) or "n/a")
              + " — " + why)
    return _out(stat, n, v, reason)


# ===================================================================================== T-682 leverage-effect DiD ==

T682_RISK = ("SPY", "QQQ", "IWM", "EFA", "EEM", "HYG")
T682_NONRISK = ("TLT", "IEF", "AGG", "GLD", "SLV", "USO", "DBC", "DBA", "UNG")
T682_REPORT = ("LQD",)
G10 = ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")
T682_WIN = ("2018-01-01", "2026-09-30")
T682_PRE = ("2007-07-01", "2017-12-31")
T682_HL = 20
T682_CAP = 2.0
T682_COST_ETF = 2e-4
T682_COST_FX = 1e-4
T682_WARM = 63
T682_NBOOT = 5000
T682_MBLOCK = 21
T682_MIN_N = 2000
T682_SPREAD_REP = 0.005
T682_FIXED = 0.10
T682_CHUNK = 100
T682_FILL_MAX = 12


def ewma_var(e, halflife: float) -> np.ndarray:
    """EWMA of squared values with normalised weights (pandas adjust=True), NaN inputs skipped (carried)."""
    q = 0.5 ** (1.0 / halflife)
    e = np.asarray(e, float)
    out = np.full(e.size, np.nan)
    num = den = 0.0
    started = False
    for i, v in enumerate(e):
        if np.isfinite(v):
            num = v * v + q * num
            den = 1.0 + q * den
            started = True
        if started:
            out[i] = num / den
    return out


def expanding_ms(e) -> tuple:
    """(mean of squared values through each index, count of finite values through it)."""
    e = np.asarray(e, float)
    ok = np.isfinite(e)
    cs = np.cumsum(np.where(ok, e * e, 0.0))
    cn = np.cumsum(ok.astype(int))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cn > 0, cs / np.maximum(cn, 1), np.nan), cn


def vt_weights_daily(e, cap: float = T682_CAP, halflife: float = T682_HL, warm: int = T682_WARM,
                     target: float | None = None, ppy: int = 252) -> np.ndarray:
    """Target weight decided at each close t from the excess returns through t: min(cap, sigmaLR_t / sigma_t) (own
    expanding-window target), or min(cap, target / (sqrt(ppy) sigma_t)) for a fixed annual target; NaN before
    ``warm`` returns."""
    ew = ewma_var(e, halflife)
    lr, cn = expanding_ms(e)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.minimum(cap, np.sqrt(lr / ew)) if target is None else np.minimum(cap, target / np.sqrt(ppy * ew))
    return np.where((cn >= warm) & np.isfinite(w), w, np.nan)


def position_returns(w, e, r, rb, cost: float, gap=None, spread: float = 0.0) -> tuple:
    """Daily rebalanced position: the weight decided at close t is filled at close t + 1 and earns the return of
    session t + 2, p_u = w_{u-2}. Excess return x_u = p_u e_u - cost |p_u - drift_{u-1}| - spread on leverage, where
    drift_{u-1} = p_{u-1} (1 + r_{u-1}) / (1 + p_{u-1} r_{u-1} + (1 - p_{u-1}) rb_{u-1}) (the weight the previous
    position drifted to; the first position starts at its target). NaN where p is undefined. Returns (x, p, turnover)."""
    w, e, r, rb = (np.asarray(a, float) for a in (w, e, r, rb))
    n = e.size
    p = np.full(n, np.nan)
    p[2:] = w[:-2]
    with np.errstate(invalid="ignore"):
        drift = p * (1.0 + r) / (1.0 + p * r + (1.0 - p) * rb)
    prev = np.r_[np.nan, drift[:-1]]
    to = np.where(np.isfinite(prev), np.abs(p - prev), 0.0)
    x = p * e - cost * to
    if spread and gap is not None:
        x = x - np.maximum(p - 1.0, 0.0) * spread * np.asarray(gap, float) / 365.0
    return np.where(np.isfinite(p) & np.isfinite(e), x, np.nan), p, np.where(np.isfinite(p), to, np.nan)


def to_master(src_days: Sequence[str], x, master: Sequence[str]) -> np.ndarray:
    """Compound a daily series onto a master session calendar: master day d collects every source day in
    (previous master day, d]; NaN if any of them is NaN, 0 when none falls there inside the source's span (a series
    marked at its own prints does not move between prints), NaN outside that span."""
    x = np.asarray(x, float)
    md = np.array(master)
    k = np.searchsorted(md, np.array(src_days), side="left")
    keep = k < md.size
    k, xx = k[keep], x[keep]
    lg = np.where(np.isfinite(xx), np.log1p(np.maximum(xx, -0.999999)), 0.0)
    bad = (~np.isfinite(xx)).astype(float)
    S = np.bincount(k, weights=lg, minlength=md.size)
    Bd = np.bincount(k, weights=bad, minlength=md.size)
    C = np.bincount(k, minlength=md.size)
    out = np.expm1(S)
    out[Bd > 0] = np.nan
    if k.size:
        span = np.zeros(md.size, bool)
        span[k.min():k.max() + 1] = True
        out[(C == 0) & ~span] = np.nan
    else:
        out[:] = np.nan
    return out


def etf_unit(days: Sequence[str], adj, B, cost: float = T682_COST_ETF) -> dict:
    """Scaled / unscaled / variant daily excess series of one ETF on its own calendar."""
    adj = np.asarray(adj, float)
    r = np.r_[np.nan, adj[1:] / adj[:-1] - 1.0]
    rb = np.r_[np.nan, B[1:] / B[:-1] - 1.0]
    e = r - rb
    return _unit(list(days), e, r, rb, VRA.cal_gaps(days), cost)


def _unit(days, e, r, rb, gap, cost: float) -> dict:
    w = vt_weights_daily(e)
    xs, p, to = position_returns(w, e, r, rb, cost)
    xu = np.where(np.isfinite(xs), e, np.nan)
    xf, _, _ = position_returns(vt_weights_daily(e, target=T682_FIXED), e, r, rb, cost)
    xsp, _, _ = position_returns(w, e, r, rb, cost, gap, T682_SPREAD_REP)
    return {"days": days, "e": e, "r": r, "rb": rb, "w": w, "p": p, "to": to, "scaled": xs, "unscaled": xu,
            "fixed": np.where(np.isfinite(xs), xf, np.nan), "spread": xsp, "gap": gap, "cost": cost}


def const_series(u: dict, wbar: float) -> np.ndarray:
    """Constant weight ``wbar`` on the unit's identical fills (daily rebalanced back to wbar)."""
    w = np.where(np.isfinite(u["w"]), wbar, np.nan)
    x, _, _ = position_returns(w, u["e"], u["r"], u["rb"], u["cost"])
    return np.where(np.isfinite(u["scaled"]), x, np.nan)


def fx_panel(spot_rows, rate_rows, ccys: Sequence[str] = G10, max_fill: int = T682_FILL_MAX) -> dict:
    """Common noon-print days of every currency in ``ccys``, their USD-per-unit spots, and monthly 3-month rates
    (percent) per currency incl. USD, internal gaps and the tail forward-filled up to ``max_fill`` months (flagged)."""
    by = {c: {} for c in ccys}
    for v in spot_rows:
        c = v.get("ccy")
        x = v.get("usd_per_unit")
        if c in by and x is not None:
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and x > 0:
                by[c][v["day"]] = x
    days = sorted(set.intersection(*(set(s) for s in by.values())))
    S = {c: np.array([by[c][d] for d in days]) for c in ccys}
    rates, filled = {}, {}
    for v in rate_rows:
        c, m, x = v.get("ccy"), v.get("month"), v.get("rate3m")
        if c in tuple(ccys) + ("USD",) and m and x is not None and math.isfinite(float(x)):
            rates.setdefault(c, {})[m] = float(x)
    last_month = days[-1][:7] if days else None
    for c, rr in rates.items():
        ms = sorted(rr)
        fl = []
        cur, gap = None, 0
        for m in VRA_months(ms[0], max(ms[-1], last_month or ms[-1])):
            if m in rr:
                cur, gap = rr[m], 0
            else:
                gap += 1
                if gap <= max_fill and cur is not None:
                    rr[m] = cur
                    fl.append(m)
        filled[c] = fl
    return {"days": days, "S": S, "rates": rates, "filled": filled}


def VRA_months(a: str, b: str) -> list:
    y, m = int(a[:4]), int(a[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _prev_month(m: str) -> str:
    y, mm = int(m[:4]), int(m[5:7])
    return f"{y - (mm == 1):04d}-{(mm - 2) % 12 + 1:02d}"


def fx_units(P: dict, cost: float = T682_COST_FX) -> dict:
    """{ccy: unit} for each currency and 'FX' for the equal-weighted basket: excess return on print day u =
    S_u / S_{u-1} - 1 + (r_ccy - r_USD)(month of u minus one) x calendar days / 36500."""
    days = P["days"]
    n = len(days)
    gap = VRA.cal_gaps(days)
    prev_m = [_prev_month(d[:7]) for d in days]
    usd = np.array([P["rates"].get("USD", {}).get(m, np.nan) for m in prev_m])
    rb = np.r_[np.nan, (usd[1:] / 100.0) * gap[1:] / 365.0]
    out, es, rs = {}, [], []
    for c in G10:
        S = P["S"][c]
        ic = np.array([P["rates"].get(c, {}).get(m, np.nan) for m in prev_m])
        r = np.r_[np.nan, S[1:] / S[:-1] - 1.0 + (ic[1:] / 100.0) * gap[1:] / 365.0]
        e = r - rb
        out[c] = _unit(days, e, r, rb, gap, cost)
        es.append(e)
        rs.append(r)
    eb = np.mean(np.stack(es), 0)
    rbk = np.mean(np.stack(rs), 0)
    out["FX"] = _unit(days, eb, rbk, rb, gap, cost)
    out["_n"] = n
    return out


def window_mask(master: Sequence[str], win: tuple) -> np.ndarray:
    return np.array([win[0] <= d <= win[1] for d in master])


def master_series(units: dict, master: Sequence[str], keys=("scaled", "unscaled", "fixed", "spread")) -> dict:
    return {nm: {k: to_master(u["days"], u[k], master) for k in keys} for nm, u in units.items()}


def gains(M: dict, mask, names, key: str = "scaled", base: str = "unscaled") -> dict:
    """Annualised Sharpe(key) - Sharpe(base) per unit over the masked master days where both are defined."""
    out = {}
    for nm in names:
        a, b = M[nm][key][mask], M[nm][base][mask]
        ok = np.isfinite(a) & np.isfinite(b)
        out[nm] = (None if ok.sum() < 30 else _sr(a[ok], 252) - _sr(b[ok], 252)) if ok.any() else None
    return out


def did(g: dict, risk, nonrisk, fx_reading: str) -> float | None:
    """Mean gain over the risk group minus the mean over the non-risk ETFs and the FX unit."""
    gr = [g[k] for k in risk]
    fxg = g["FX"] if fx_reading == "basket" else (None if any(g[c] is None for c in G10) else float(np.mean([g[c] for c in G10])))
    gn = [g[k] for k in nonrisk] + [fxg]
    if any(x is None for x in gr + gn):
        return None
    return float(np.mean(gr) - np.mean(gn))


def joint_boot_did(S: np.ndarray, U: np.ndarray, n_risk: int, n_non: int, n_boot: int, seed: int,
                   mean_block: float = T682_MBLOCK, chunk: int = T682_CHUNK) -> dict:
    """Percentile 95% interval of the DiD under the joint bootstrap: stationary time blocks (mean ``mean_block``) drawn
    once for every row, and the units resampled with replacement within each group. Rows of S (scaled) and U
    (unscaled): the n_risk risk units, then n_non non-risk ETF units, then the FX basket, then the nine currencies.
    Returns the intervals under the two FX readings ('basket', 'pairs') and the draws' sd."""
    rng = np.random.default_rng(seed)
    n = S.shape[1]
    nr, nn = n_risk, n_non
    out = {"basket": [], "pairs": []}
    done = 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        idx = BW._stationary_idx(rng, n, mean_block, k)
        Xs, Xu = S[:, idx], U[:, idx]
        g = (Xs.mean(-1) / Xs.std(-1, ddof=1) - Xu.mean(-1) / Xu.std(-1, ddof=1)) * math.sqrt(252.0)   # (rows, k)
        rd = rng.integers(0, nr, size=(k, nr))
        nd = rng.integers(0, nn + 1, size=(k, nn + 1))       # the FX unit is index nn of the non-risk group
        gr = np.take_along_axis(g[:nr].T, rd, axis=1).mean(1)
        for rdg, fxg in (("basket", g[nr + nn]), ("pairs", g[nr + nn + 1:].mean(0))):
            G = np.column_stack([g[nr:nr + nn].T, fxg])
            gn = np.take_along_axis(G, nd, axis=1).mean(1)
            out[rdg].append(gr - gn)
        done += k
    res = {}
    for rdg, v in out.items():
        d = np.concatenate(v)
        res[rdg] = {"ci": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))], "sd": float(d.std(ddof=1))}
    return res


def did_boot(S, U, n_risk, n_non, n_boot: int = T682_NBOOT, reps: int | None = None) -> dict:
    """``joint_boot_did`` over 5 seeds (interval ends averaged), escalated to 25 when an end cannot be resolved against
    0 under either FX reading; {reading: {'ci', 'ci_mc_se', 'sd', 'reps'}}."""
    def run(nreps):
        rs = [joint_boot_did(S, U, n_risk, n_non, n_boot, SEED + k) for k in range(nreps)]
        out = {}
        for rdg in ("basket", "pairs"):
            arr = np.array([r_[rdg]["ci"] for r_ in rs])
            out[rdg] = {"ci": [float(v) for v in arr.mean(0)],
                        "ci_mc_se": [float(v) for v in (arr.std(0, ddof=1) / math.sqrt(nreps) if nreps > 1 else np.zeros(2))],
                        "sd": float(np.mean([r_[rdg]["sd"] for r_ in rs])), "reps": nreps}
        return out
    reps = BW.REPS if reps is None else reps
    t = run(reps)
    if any(BW._ci_crit(t[r_], "gt", 0.0, "")[1] is None for r_ in t) and BW.REPS_MAX > reps:
        t = run(BW.REPS_MAX)
    return t


def leverage_coef(e, days, win: tuple) -> float | None:
    """corr(e_t, sum of e^2 over t+1..t+21) on the days of ``win`` (forward window inside the data)."""
    e = np.asarray(e, float)
    sq = np.where(np.isfinite(e), e * e, np.nan)
    n = e.size
    fwd = np.full(n, np.nan)
    c = np.r_[0.0, np.cumsum(np.nan_to_num(sq))]
    cnt = np.r_[0, np.cumsum(np.isfinite(sq).astype(int))]
    i = np.arange(n - 21)
    good = (cnt[i + 22] - cnt[i + 1]) == 21
    fwd[i[good]] = c[i[good] + 22] - c[i[good] + 1]
    m = np.array([win[0] <= d <= win[1] for d in days]) & np.isfinite(e) & np.isfinite(fwd)
    if m.sum() < 100:
        return None
    return float(np.corrcoef(e[m], fwd[m])[0, 1])


def _spearman(a, b) -> float | None:
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 4:
        return None
    ra = np.argsort(np.argsort(a[ok])).astype(float)
    rb = np.argsort(np.argsort(b[ok])).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def _cvar(x, q: float = 0.05) -> float | None:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 40:
        return None
    k = max(1, math.floor(q * x.size))
    return float(np.sort(x)[:k].mean())


def _volvol(x, w: int = 21) -> float | None:
    """sd of log realised vol over non-overlapping ``w``-day windows."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    m = x.size // w
    if m < 8:
        return None
    rv = np.sqrt((x[:m * w].reshape(m, w) ** 2).mean(1))
    rv = rv[rv > 0]
    return float(np.log(rv).std(ddof=1)) if rv.size > 4 else None


def leverage_did_test(etf_units: dict, fxu: dict, master: Sequence[str], n_boot: int = T682_NBOOT,
                      reps: int | None = None) -> dict:
    """T-682 core: units on their own calendars, compounded onto ``master``."""
    units = {**etf_units, **{k: v for k, v in fxu.items() if not k.startswith("_")}}
    M = master_series(units, master)
    wm, pm = window_mask(master, T682_WIN), window_mask(master, T682_PRE)
    names_all = list(T682_RISK) + list(T682_NONRISK) + ["FX"] + list(G10)
    rows_s = np.stack([M[k]["scaled"][wm] for k in names_all])
    rows_u = np.stack([M[k]["unscaled"][wm] for k in names_all])
    ok = np.isfinite(rows_s).all(0) & np.isfinite(rows_u).all(0)
    n = int(ok.sum())
    if n < 30:
        return {"n": n, "fail": "too few days with every unit defined in 2018-01..2026-09"}
    mdays = [d for d, k in zip([d for d, k in zip(master, wm) if k], ok) if k]
    g = gains(M, wm, names_all + [k for k in T682_REPORT if k in M])
    gpre = gains(M, pm, names_all + [k for k in T682_REPORT if k in M])
    est = {rdg: did(g, T682_RISK, T682_NONRISK, rdg) for rdg in ("basket", "pairs")}
    pre = {rdg: did(gpre, T682_RISK, T682_NONRISK, rdg) for rdg in ("basket", "pairs")}
    boot = did_boot(rows_s[:, ok], rows_u[:, ok], len(T682_RISK), len(T682_NONRISK), n_boot, reps)
    for rdg in boot:
        boot[rdg]["est"] = est[rdg]
    # reported
    gf = gains(M, wm, names_all, "fixed", "unscaled")
    gs = gains(M, wm, names_all, "spread", "unscaled")
    rep = {"fixed10": {rdg: did(gf, T682_RISK, T682_NONRISK, rdg) for rdg in ("basket", "pairs")},
           "bill_plus_50": {rdg: did(gs, T682_RISK, T682_NONRISK, rdg) for rdg in ("basket", "pairs")}}
    const_g, tails, wbar, turn = {}, {}, {}, {}
    for nm in names_all + [k for k in T682_REPORT if k in units]:
        u = units[nm]
        dm = np.array([T682_WIN[0] <= d <= T682_WIN[1] for d in u["days"]]) & np.isfinite(u["scaled"])
        if dm.sum() < 30:
            continue
        wbar[nm] = float(np.nanmean(u["p"][dm]))
        turn[nm] = float(np.nanmean(u["to"][dm]) * 252)
        cs = to_master(u["days"], const_series(u, wbar[nm]), master)[wm]
        sc = M[nm]["scaled"][wm]
        okc = np.isfinite(cs) & np.isfinite(sc)
        const_g[nm] = _sr(sc[okc], 252) - _sr(cs[okc], 252)
        un = M[nm]["unscaled"][wm]
        oku = np.isfinite(sc) & np.isfinite(un)
        cv_s, cv_u = _cvar(sc[oku]), _cvar(un[oku])
        vv_s, vv_u = _volvol(sc[oku]), _volvol(un[oku])
        tails[nm] = {"cvar5_change": None if cv_s is None or cv_u is None else cv_s - cv_u,
                     "volvol_change": None if vv_s is None or vv_u is None else vv_s - vv_u}
    rep["const"] = {"per": const_g, "did": {rdg: did({**{k: const_g.get(k) for k in names_all}}, T682_RISK, T682_NONRISK, rdg)
                                            for rdg in ("basket", "pairs")}}
    rep["tails"] = tails
    rep["wbar"] = wbar
    rep["turnover_ann"] = turn
    lev = {nm: leverage_coef(units[nm]["e"], units[nm]["days"], T682_PRE) for nm in
           list(T682_RISK) + list(T682_NONRISK) + [k for k in T682_REPORT if k in units] + ["FX"]}
    ks = [k for k in lev if lev[k] is not None and g.get(k) is not None]
    rep["leverage"] = {"coef": lev, "spearman_vs_gain": _spearman([lev[k] for k in ks], [g[k] for k in ks]), "n_assets": len(ks)}
    return {"n": n, "span": [mdays[0], mdays[-1]], "gains": g, "gains_pre": gpre, "est": est, "pre": pre, "boot": boot,
            "rep": rep}


def b13_volregime_b_leverage_did(archive):
    """T-682: vol-targeting Sharpe gain, risk assets minus non-risk assets (difference-in-differences), 2018-01..2026-09."""
    syms = list(T682_RISK) + list(T682_NONRISK) + list(T682_REPORT)
    miss = _missing(archive, [dh(s) for s in syms] + [FXS_B, FXR_B, DTB3_B])
    if miss:
        return miss
    acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
    eu = {}
    master = None
    for s in syms:
        d, adj = CAL._daily(archive, dh(s), "adjclose")
        eu[s] = etf_unit(d, adj, VRA.bill_index(d, acc))
        if s == "SPY":
            master = list(d)
    P = fx_panel([r["value"] for r in CAL._rows(archive, FXS_B)], [r["value"] for r in CAL._rows(archive, FXR_B)])
    fxu = fx_units(P)
    R = leverage_did_test(eu, fxu, master)
    n = R["n"]
    if "fail" in R:
        return _out({"n": n}, n, "inconclusive", R["fail"])
    boot, est, pre, g, rep = R["boot"], R["est"], R["pre"], R["gains"], R["rep"]
    lbl = {"basket": "FX unit = the equal-weighted basket scaled as one asset",
           "pairs": "FX unit = the mean gain of the nine currencies each scaled on its own volatility"}
    fmt = lambda x: _s(x, 3)
    rows = [BW.all_constructions([BW._ci_crit(boot[rdg], "gt", 0.0, f"{lbl[rdg]}: DiD {fmt(est[rdg])}", fmt)
                                  for rdg in ("basket", "pairs")],
                                 "DiD of the Sharpe gain (risk minus non-risk) 2018-01..2026-09, lower 95% bound > 0 (joint "
                                 "stationary 21-day time blocks x assets within groups, 5,000 draws a seed) under both FX "
                                 "readings (rule 11)"),
            BW.all_constructions([(f"{lbl[rdg]} ({fmt(pre[rdg])})", None if pre[rdg] is None else pre[rdg] > 0,
                                   pre[rdg] is not None and pre[rdg] <= 0) for rdg in ("basket", "pairs")],
                                 "the frozen rule's 2007-07..2017-12 DiD > 0 under both FX readings")]
    v, why, crit = CAL._judge(rows, n, T682_MIN_N, "days")
    used = {_prev_month(d[:7]) for d in P["days"] if T682_PRE[0] <= d <= T682_WIN[1]}
    filled = {c: sorted(m for m in fl if m in used) for c, fl in P["filled"].items() if c in G10 + ("USD",)}
    filled = {c: ", ".join(fl) for c, fl in filled.items() if fl}
    se = boot["basket"]["sd"]
    stat = {"n_days": n, "span": R["span"], "did": est, "did_pre": pre,
            "boot": {k: {kk: x.get(kk) for kk in ("ci", "ci_mc_se", "sd", "reps")} for k, x in boot.items()},
            "power": {"boot_sd_basket": se, "mde_80": (Z975 + Z80) * se}, "gains": g, "gains_pre": R["gains_pre"],
            "reported": rep, "fx_rates_filled": filled, "criteria": crit, "rule10": "daily decisions (no grid phase)"}
    gr = ", ".join(f"{k} {_s(g[k], 2)}" for k in T682_RISK)
    gn = ", ".join(f"{k} {_s(g[k], 2)}" for k in list(T682_NONRISK) + ["FX"])
    gfx = ", ".join(f"{k} {_s(g[k], 2)}" for k in G10)
    reason = (f"POWER: sd of the bootstrap DiD {se:.3f}, so the minimum detectable DiD at 80% power is "
              f"{(Z975 + Z80) * se:.3f}. RESULT: position min(2, sigmaLR / sigma_EWMA(hl 20)) on daily excess returns, "
              f"decided at close t and filled at close t+1 (FX: next noon print), rebalanced daily, 2 bp (FX 1 bp) per unit "
              f"of turnover, leverage at the bill rate; {n} sessions {R['span'][0]}..{R['span'][1]}: Sharpe gain (scaled - "
              f"unscaled) risk {gr}; non-risk {gn} (currencies {gfx}; LQD reported {_s(g.get('LQD'), 2)}); DiD basket "
              f"{fmt(est['basket'])} {_ci(boot['basket']['ci'])}, pairs {fmt(est['pairs'])} {_ci(boot['pairs']['ci'])}; "
              f"2007-07..2017-12 DiD basket {fmt(pre['basket'])}, pairs {fmt(pre['pairs'])}. Reported: fixed 10% target "
              f"DiD {fmt(rep['fixed10']['basket'])} / {fmt(rep['fixed10']['pairs'])}; bill + 50 bp financing "
              f"{fmt(rep['bill_plus_50']['basket'])} / {fmt(rep['bill_plus_50']['pairs'])}; scaled minus constant weight at "
              f"its mean weight DiD {fmt(rep['const']['did']['basket'])} / {fmt(rep['const']['did']['pairs'])}; mean "
              f"weights " + ", ".join(f"{k} {x:.2f}" for k, x in rep["wbar"].items() if k not in G10)
              + f"; leverage-effect coefficient (2007-07..2017-12) vs 2018-2026 gain Spearman "
              f"{_s(rep['leverage']['spearman_vs_gain'], 2)} over {rep['leverage']['n_assets']} assets; 5% CVaR change "
              + ", ".join(f"{k} {_pc(x['cvar5_change'], 2)}" for k, x in rep["tails"].items() if k not in G10)
              + "; vol-of-vol change " + ", ".join(f"{k} {_s(x['volvol_change'], 2)}" for k, x in rep["tails"].items()
                                                  if k not in G10)
              + ("; OECD rates carried forward (flagged): " + "; ".join(f"{c} {x}" for c, x in filled.items()) if filled else "")
              + ". ETF list chosen in 2026 (survivors; T-420 precedent) — " + why)
    return _out(stat, n, v, reason)


# ======================================================================================= T-683 SHAR vs EWMA target ==

T683_ASSETS = ("SPY", "QQQ", "IWM", "TLT", "GLD", "USO")
T683_IV = {"SPY": "VIX", "QQQ": "VXN", "IWM": "RVX", "TLT": "VXTLT", "GLD": "GVZ", "USO": "OVX"}
T683_WIN = ("2015-01-01", "2026-09-30")
T683_EARLY = ("2005-01-01", "2014-12-31")
T683_FIT_FROM = "2004-01-02"
T683_MIN_FIT = 500
T683_IV_ENTRY = 250
T683_H = 21
T683_TARGET = 0.10
T683_CAP = 2.0
T683_COST = 2e-4
T683_LAMBDA = 0.94
T683_BLOCK = 63
T683_DM_BW = 63
T683_NBOOT = 2000
T683_MIN_N = 2500
T683_FORECASTERS = ("SHAR", "HAR", "HARIV")
T683_SR_UTIL, T683_GAMMA = 0.4, 2.0
T683_MSM_TRAIN = ("2004-01-01", "2014-12-31")


def har_design(lr, kind: str, iv=None) -> np.ndarray:
    """Regressors at each close t (rows; NaN before 22 returns): HAR [1, r_t^2, mean5 r^2, mean22 r^2]; SHAR splits
    r_t^2 by the sign of r_t; HARIV appends (IV_t / 100)^2 x 21 / 252."""
    lr = np.asarray(lr, float)
    n = lr.size
    sq = np.where(np.isfinite(lr), lr * lr, np.nan)
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(sq))]
    cnt = np.r_[0, np.cumsum(np.isfinite(sq).astype(int))]
    i = np.arange(n)
    ok = (i >= 22) & (cnt[np.minimum(i + 1, n)] - cnt[np.maximum(i - 21, 0)] == 22)
    m5 = np.full(n, np.nan)
    m22 = np.full(n, np.nan)
    m5[ok] = (cs[i[ok] + 1] - cs[i[ok] - 4]) / 5.0
    m22[ok] = (cs[i[ok] + 1] - cs[i[ok] - 21]) / 22.0
    d = np.where(ok, sq, np.nan)
    cols = [np.where(ok, 1.0, np.nan)]
    if kind == "SHAR":
        cols += [np.where(lr > 0, d, np.where(ok, 0.0, np.nan)), np.where(lr < 0, d, np.where(ok, 0.0, np.nan))]
    else:
        cols += [d]
    cols += [m5, m22]
    if kind == "HARIV":
        cols.append((np.asarray(iv, float) / 100.0) ** 2 * T683_H / 252.0)
    return np.column_stack(cols)


def fwd_sum(sq, h: int = T683_H) -> np.ndarray:
    """sum of sq over t+1..t+h at each t (NaN when the window leaves the data or holds a NaN)."""
    sq = np.asarray(sq, float)
    n = sq.size
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(sq))]
    cnt = np.r_[0, np.cumsum(np.isfinite(sq).astype(int))]
    out = np.full(n, np.nan)
    i = np.arange(n - h)
    good = cnt[i + h + 1] - cnt[i + 1] == h
    out[i[good]] = cs[i[good] + h + 1] - cs[i[good] + 1]
    return out


def month_end_idx(days: Sequence[str]) -> np.ndarray:
    """Every calendar month's last session (the data's final session counts too: a refit there is harmless)."""
    return np.array([i for i in range(len(days)) if i == len(days) - 1 or days[i][:7] != days[i + 1][:7]], int)


def har_forecasts_daily(days: Sequence[str], X, T, start: int, min_rows: int, refits=None) -> tuple:
    """Daily forecasts x_t . beta, beta refitted at every month-end close e by OLS on rows s >= start whose target
    ended by e (s + 21 <= e), with at least ``min_rows`` of them; between refits the latest coefficients are used (the
    refit at close e already serves the forecast at e). Insanity filter: a forecast outside [min, max] of the fit's
    targets (or not positive) is replaced by their mean. Returns (forecasts, refit coverage)."""
    X, T = np.asarray(X, float), np.asarray(T, float)
    n = X.shape[0]
    row = np.isfinite(X).all(1) & np.isfinite(T) & (np.arange(n) >= start)
    Xz = np.where(row[:, None], X, 0.0)
    Tz = np.where(row, T, 0.0)
    PXX = np.cumsum(Xz[:, :, None] * Xz[:, None, :], axis=0)
    PXT = np.cumsum(Xz * Tz[:, None], axis=0)
    cnt = np.cumsum(row.astype(int))
    cs = np.cumsum(Tz)
    tmin = np.minimum.accumulate(np.where(row, T, np.inf))
    tmax = np.maximum.accumulate(np.where(row, T, -np.inf))
    out = np.full(n, np.nan)
    me = month_end_idx(days) if refits is None else np.asarray(refits, int)
    fits = 0
    for j, e in enumerate(me):
        last = e - T683_H
        if last < 0 or cnt[last] < min_rows:
            continue
        try:
            beta = np.linalg.solve(PXX[last], PXT[last])
        except np.linalg.LinAlgError:
            continue
        fits += 1
        hi = me[j + 1] if j + 1 < me.size else n - 1
        seg = np.arange(e, hi + (1 if j + 1 >= me.size else 0))
        if seg.size == 0:
            continue
        f = X[seg] @ beta
        lo_, hi_, mu = tmin[last], tmax[last], cs[last] / cnt[last]
        f = np.where(np.isfinite(f) & ((f < lo_) | (f > hi_) | (f <= 0)), mu, f)
        out[seg] = f
    return out, fits


def ewma_forecast(lr, lam: float = T683_LAMBDA, h: int = T683_H) -> np.ndarray:
    """RiskMetrics: s2_t = lam s2_{t-1} + (1 - lam) r_t^2, seeded at the 22nd return with the mean of the first 22
    squared returns; forecast of the next h sessions' summed variance = h s2_t."""
    lr = np.asarray(lr, float)
    n = lr.size
    out = np.full(n, np.nan)
    fin = np.where(np.isfinite(lr))[0]
    if fin.size < 23:
        return out
    i0 = fin[21]
    s2 = float(np.mean(lr[fin[:22]] ** 2))
    out[i0] = h * s2
    for i in range(i0 + 1, n):
        if np.isfinite(lr[i]):
            s2 = lam * s2 + (1.0 - lam) * lr[i] * lr[i]
        out[i] = h * s2
    return out


def target_weights(F, target: float = T683_TARGET, cap: float = T683_CAP, h: int = T683_H) -> np.ndarray:
    F = np.asarray(F, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.minimum(cap, target / np.sqrt(252.0 * F / h))
    return np.where(np.isfinite(w) & (F > 0), w, np.nan)


def tracking_losses(p, lr, h: int = T683_H, target: float = T683_TARGET) -> np.ndarray:
    """[ln(realised position vol / target)]^2 of the window starting at each session s (sessions s..s+h-1), realised
    vol = sqrt(252 / h x sum (p_u lr_u)^2); NaN when the window holds an undefined position or leaves the data."""
    x = np.asarray(p, float) * np.asarray(lr, float)
    sq = x * x
    n = sq.size
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(sq))]
    cnt = np.r_[0, np.cumsum(np.isfinite(sq).astype(int))]
    out = np.full(n, np.nan)
    s = np.arange(n - h + 1)
    good = cnt[s + h] - cnt[s] == h
    v = cs[s[good] + h] - cs[s[good]]
    with np.errstate(divide="ignore"):
        out[s[good]] = np.log(np.sqrt(252.0 / h * v) / target) ** 2
    out[~np.isfinite(out)] = np.nan
    return out


def realised_ratio(p, lr, h: int = T683_H, target: float = T683_TARGET) -> np.ndarray:
    x = np.asarray(p, float) * np.asarray(lr, float)
    sq = x * x
    n = sq.size
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(sq))]
    cnt = np.r_[0, np.cumsum(np.isfinite(sq).astype(int))]
    out = np.full(n, np.nan)
    s = np.arange(n - h + 1)
    good = cnt[s + h] - cnt[s] == h
    out[s[good]] = np.sqrt(252.0 / h * (cs[s[good] + h] - cs[s[good]])) / target
    return out


def qlike(rv, F) -> np.ndarray:
    rv, F = np.asarray(rv, float), np.asarray(F, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        q = rv / F - np.log(rv / F) - 1.0
    return np.where(np.isfinite(q) & (rv > 0) & (F > 0), q, np.nan)


def dm_test(d, bw: int = T683_DM_BW) -> dict:
    """Diebold-Mariano on a loss differential d (negative = the first forecaster better): mean, t with a Bartlett
    long-run variance at bandwidth ``bw``, one-sided p for H1 mean < 0."""
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    if d.size < 30:
        return {"n": int(d.size), "mean": None, "t": None, "p_less": None}
    lrv = float(_hac_var(d[None, :], bw)[0])
    t = float(d.mean() / math.sqrt(lrv / d.size))
    return {"n": int(d.size), "mean": float(d.mean()), "t": t, "p_less": float(_N.cdf(t))}


def mean_lt_test(d, block: int = T683_BLOCK, n_boot: int = T683_NBOOT, reps: int | None = None) -> dict:
    """Studentized CBB of mean(d): est, two-sided 95% CI and p_lt (H0: mean >= 0) over 5 seeds, escalated to 25
    when the upper end cannot be resolved against 0."""
    d = np.asarray(d, float)
    return BW.mc_escalate(lambda seed: BW._stud(BW._mean_stat, [d], block, n_boot, seed),
                          lambda t: BW._ci_crit(t, "lt", 0.0, "")[1], reps, SEED)


def msm_forecasts(lr, train_mask, k: int = 4, h: int = T683_H) -> np.ndarray:
    """Reported only: MSM (T-569) fitted once on the training returns (grid MLE), then filtered forward through every
    return with those parameters; forecast at t = pi_{t|t} (sum_{j=1..h} P^j) var."""
    from mandel.experiments import msm as MSM
    lr = np.asarray(lr, float)
    tr = lr[np.asarray(train_mask, bool) & np.isfinite(lr)]
    mu = float(tr.mean()) if tr.size else 0.0
    fit = MSM.fit_msm(tr - mu, k)
    _, prod = MSM._states(k, fit["m0"])
    var = fit["sigma"] ** 2 * prod
    P = MSM._transition(k, fit["gamma1"], fit["b"])
    acc = np.zeros(var.size)
    Pj = np.eye(var.size)
    for _ in range(h):
        Pj = Pj @ P
        acc = acc + Pj @ var
    pi = np.full(var.size, 1.0 / var.size)
    out = np.full(lr.size, np.nan)
    for t in range(lr.size):
        pred = pi @ P
        if np.isfinite(lr[t]):
            dens = np.exp(-0.5 * (lr[t] - mu) ** 2 / var) / np.sqrt(2 * math.pi * var)
            w_ = pred * dens
            s_ = w_.sum()
            pi = w_ / s_ if s_ > 0 and np.isfinite(s_) else pred
        else:
            pi = pred
        out[t] = float(pi @ acc)
    return out


def asset_forecasts(days: Sequence[str], adj, iv_close: dict | None, msm: bool = True) -> dict:
    """Every forecaster's daily 21-session variance forecast for one asset."""
    days = list(days)
    adj = np.asarray(adj, float)
    lr = np.r_[np.nan, np.log(adj[1:] / adj[:-1])]
    sq = lr * lr
    T = fwd_sum(sq)
    start = max(0, int(np.searchsorted(np.array(days), T683_FIT_FROM))) + 22
    out = {"lr": lr, "T": T, "EWMA": ewma_forecast(lr)}
    fits = {}
    for kind in ("HAR", "SHAR"):
        out[kind], fits[kind] = har_forecasts_daily(days, har_design(lr, kind), T, start, T683_MIN_FIT)
    if iv_close:
        ivd = VRA.vix_asof(iv_close, days)
        first = min(iv_close)
        i_first = int(np.searchsorted(np.array(days), first))
        Xiv = har_design(lr, "HARIV", ivd)
        Xiv[:i_first] = np.nan
        me = month_end_idx(days)
        me = me[(me >= i_first + T683_IV_ENTRY) & np.isfinite(out["HAR"][me])]   # the asset's own 500-row rule too
        fiv, fits["HARIV"] = har_forecasts_daily(days, Xiv, T, max(start, i_first), 1, refits=me)
        out["HARIV"] = np.where(np.isfinite(fiv), fiv, out["HAR"])
        out["iv_entry"] = days[me[0]] if me.size else None                         # the first HAR-IV refit
    else:
        out["HARIV"] = out["HAR"].copy()
        out["iv_entry"] = None
    if msm:
        tm = np.array([T683_MSM_TRAIN[0] <= d <= T683_MSM_TRAIN[1] for d in days])
        out["MSM"] = msm_forecasts(lr, tm)
    out["fits"] = fits
    return out


def risk_target_test(assets: dict, n_boot: int = T683_NBOOT, reps: int | None = None, win: tuple = T683_WIN,
                     early: tuple = T683_EARLY) -> dict:
    """T-683 core. assets {sym: {'days', 'adj', 'B', 'iv': {day: close} or None, 'F': forecasts or None}}."""
    per = {}
    fc_names = ("EWMA",) + T683_FORECASTERS + (("MSM",) if all("MSM" in (a.get("F") or {}) for a in assets.values()) else ())
    for sym, a in assets.items():
        days = list(a["days"])
        adj = np.asarray(a["adj"], float)
        Fz = a.get("F") or asset_forecasts(days, adj, a.get("iv"), msm=False)
        r = np.r_[np.nan, adj[1:] / adj[:-1] - 1.0]
        rb = np.r_[np.nan, a["B"][1:] / a["B"][:-1] - 1.0]
        e = r - rb
        lr = Fz["lr"]
        q = {}
        for fn in fc_names:
            if fn not in Fz:
                continue
            w = target_weights(Fz[fn])
            x, p, to = position_returns(w, e, r, rb, T683_COST)
            q[fn] = {"x": x, "p": p, "to": to, "loss": tracking_losses(p, lr), "ratio": realised_ratio(p, lr),
                     "ql": qlike(Fz["T"], Fz[fn]), "w": w}
        per[sym] = {"days": days, "q": q, "e": e, "r": r, "rb": rb, "lr": lr, "F": Fz}
    # common window-start calendar: days every asset has, windows fully inside the period
    def panel(period, key, fn):
        dsets = []
        for P_ in per.values():
            d = np.array(P_["days"])
            lastin = np.where(d <= period[1])[0]
            if lastin.size == 0:
                return [], None
            li = lastin[-1]
            v = P_["q"][fn][key]
            keep = (d >= period[0]) & (np.arange(d.size) + (T683_H - 1 if key in ("loss", "ratio") else T683_H) <= li)
            dsets.append({dd: vv for dd, vv, kk in zip(d, v, keep) if kk})
        common = sorted(set.intersection(*(set(s) for s in dsets)))
        M = np.array([[s_[dd] for dd in common] for s_ in dsets], float)
        return common, M

    res = {"win": {}, "early": {}}
    for tag, period in (("win", win), ("early", early)):
        R = res[tag]
        base_d, base_L = panel(period, "loss", "EWMA")
        _, base_Q = panel(period, "ql", "EWMA")
        R["n_windows"] = len(base_d)
        for fn in fc_names[1:]:
            _, L = panel(period, "loss", fn)
            _, Q = panel(period, "ql", fn)
            ok = np.isfinite(L).all(0) & np.isfinite(base_L).all(0)
            dl = (L - base_L)[:, ok].mean(0)
            okq = np.isfinite(Q).all(0) & np.isfinite(base_Q).all(0)
            dq = (Q - base_Q)[:, okq].mean(0)
            if fn == "SHAR":
                R["first_window"] = next((d for d, k in zip(base_d, ok) if k), None)
            ent = {"n": int(ok.sum()), "loss": float(np.nanmean(L[:, ok])), "loss_ewma": float(np.nanmean(base_L[:, ok])),
                   "diff": float(dl.mean()) if dl.size else None, "qlike": dm_test(dq),
                   "qlike_level": float(np.nanmean(Q[:, okq])), "qlike_ewma": float(np.nanmean(base_Q[:, okq]))}
            if tag == "win" or fn == "SHAR":
                ent["test"] = mean_lt_test(dl, T683_BLOCK, n_boot, reps if tag == "win" else 1)
            idx = np.array([i for i, k in enumerate(ok) if k])
            ph = [float(dl[np.arange(dl.size) % T683_H == k].mean()) for k in range(T683_H) if (np.arange(dl.size) % T683_H == k).any()]
            ent["phase_range"] = [min(ph), max(ph)] if ph else None
            ent["n_phase"] = int(idx.size // T683_H)
            R[fn] = ent
        # Sharpe (net), turnover, constant weight, utility
        R["sharpe"], R["turnover"], R["const"], R["util"] = {}, {}, {}, {}
        for fn in fc_names:
            srs, tos, cst, uls = [], [], [], []
            for sym, P_ in per.items():
                d = np.array(P_["days"])
                m = (d >= period[0]) & (d <= period[1])
                Q_ = P_["q"][fn]
                x = Q_["x"][m]
                ok = np.isfinite(x)
                srs.append(_sr(x[ok], 252) if ok.sum() > 30 else None)
                tos.append(float(np.nanmean(Q_["to"][m]) * 252))
                wbar = float(np.nanmean(Q_["p"][m]))
                wc = np.where(np.isfinite(Q_["w"]), wbar, np.nan)
                xc, pc, _ = position_returns(wc, P_["e"], P_["r"], P_["rb"], T683_COST)
                lc = tracking_losses(pc, P_["lr"])
                mm = m & np.isfinite(Q_["loss"]) & np.isfinite(lc)
                cst.append({"wbar": wbar, "sharpe": _sr(xc[m][np.isfinite(xc[m])], 252), "loss": float(np.nanmean(lc[mm])),
                            "loss_fc": float(np.nanmean(Q_["loss"][mm]))})
                rr = Q_["ratio"][m]
                rr = rr[np.isfinite(rr)]
                uls.append(T683_SR_UTIL ** 2 / (2 * T683_GAMMA) * float(np.mean((rr - 1.0) ** 2)) if rr.size else None)
            R["sharpe"][fn] = srs
            R["turnover"][fn] = float(np.mean(tos))
            R["const"][fn] = cst
            R["util"][fn] = None if any(u is None for u in uls) else float(np.mean(uls))
        for fn in fc_names[1:]:
            a_, b_ = R["sharpe"][fn], R["sharpe"]["EWMA"]
            R[fn]["sharpe_diff"] = None if any(x is None for x in a_ + b_) else float(np.mean(np.array(a_) - np.array(b_)))
            R[fn]["util_gain_bp"] = (None if R["util"][fn] is None or R["util"]["EWMA"] is None
                                     else (R["util"]["EWMA"] - R["util"][fn]) * 1e4)
    # Holm across the three trials on the tracking-loss p (H0: diff >= 0)
    ps = {fn: res["win"][fn]["test"].get("p_lt") for fn in T683_FORECASTERS}
    res["holm"] = CAL._holm(ps)
    res["holm_draws"] = n_boot * int(res["win"]["SHAR"]["test"].get("reps") or 1)
    res["fc_names"] = fc_names
    res["per"] = {s: {"fits": P_["F"].get("fits"), "iv_entry": P_["F"].get("iv_entry")} for s, P_ in per.items()}
    res["_per"] = per
    return res


def gk_and_intraday(per: dict, rows: dict, win: tuple = T683_WIN) -> dict:
    """Reported only: SHAR - EWMA pooled QLIKE under two other variance proxies. (a) Garman-Klass plus the squared
    overnight return, on sessions whose open is not stale (open equal to the previous close or outside [low, high]
    flags it; a 21-session target holding a flagged session is dropped); (b) 60-minute bars (local, 2023-11 on):
    the session's summed squared hourly log returns plus the squared overnight return."""
    from mandel.ml import features as FE
    out = {"gk": {}, "h60": {}}
    gk_d, h_d = [], []
    for sym, P_ in per.items():
        days = P_["days"]
        R = rows.get(sym) or {}
        o = np.array([R.get(d, {}).get("open", np.nan) for d in days], float)
        hi = np.array([R.get(d, {}).get("high", np.nan) for d in days], float)
        lo = np.array([R.get(d, {}).get("low", np.nan) for d in days], float)
        c = np.array([R.get(d, {}).get("close", np.nan) for d in days], float)
        a = np.array([R.get(d, {}).get("adjclose", np.nan) for d in days], float)
        fac = a / c
        with np.errstate(invalid="ignore", divide="ignore"):
            on = np.r_[np.nan, np.log(o[1:] * fac[1:] / (c[:-1] * fac[:-1]))]
            gk = 0.5 * np.log(hi / lo) ** 2 - (2 * math.log(2) - 1) * np.log(c / o) ** 2 + on ** 2
        stale = np.r_[True, (o[1:] == c[:-1])] | (o > hi) | (o < lo) | ~np.isfinite(gk)
        g = np.where(stale, np.nan, gk)
        Tg = fwd_sum(g)
        d = np.array(days)
        m = (d >= win[0]) & (d <= win[1])
        out["gk"][sym] = {"stale_share": float(stale[m].mean())}
        F = P_["F"]
        gk_d.append({dd: (qlike(Tg, F["SHAR"])[i] - qlike(Tg, F["EWMA"])[i]) for i, dd in enumerate(days) if m[i]})
        b = FE.load_bars("60m", sym)
        if b is None or b.empty:
            continue
        ny = b.index.tz_convert("America/New_York")
        lc = np.log(b["c"].astype(float).values)
        lo_ = np.log(b["o"].astype(float).values)
        dkey = np.array([t.strftime("%Y-%m-%d") for t in ny])
        rv = {}
        prev_close = None
        for dd in sorted(set(dkey)):
            idx = np.where(dkey == dd)[0]
            intr = np.diff(lc[idx])
            v = float(np.sum(intr ** 2)) + float((lc[idx[0]] - lo_[idx[0]]) ** 2)
            if prev_close is not None:
                v += float((lo_[idx[0]] - prev_close) ** 2)
            rv[dd] = v if prev_close is not None else np.nan
            prev_close = lc[idx[-1]]
        hv = np.array([rv.get(dd, np.nan) for dd in days], float)
        Th = fwd_sum(hv)
        h_d.append({dd: (qlike(Th, F["SHAR"])[i] - qlike(Th, F["EWMA"])[i]) for i, dd in enumerate(days)
                    if m[i] and np.isfinite(Th[i])})
    for tag, ds in (("gk", gk_d), ("h60", h_d)):
        if not ds:
            continue
        common = sorted(set.intersection(*({k for k, v in s_.items() if np.isfinite(v)} for s_ in ds)))
        dd = np.array([np.mean([s_[k] for s_ in ds]) for k in common])
        out[tag]["pooled"] = dm_test(dd)
        out[tag]["span"] = [common[0], common[-1]] if common else None
    return out


def b13_volregime_b_shar_risk_target(archive):
    """T-683: SHAR vs EWMA(0.94) forecasts sizing a 10% vol target on 6 ETFs: QLIKE gate, tracking loss, net Sharpe."""
    miss = _missing(archive, [dh(s) for s in T683_ASSETS] + [cboe(T683_IV[s]) for s in T683_ASSETS] + [DTB3_B])
    if miss:
        return miss
    acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
    assets, rows = {}, {}
    for s in T683_ASSETS:
        d, adj = CAL._daily(archive, dh(s), "adjclose")
        iv = CAL._series(archive, cboe(T683_IV[s]))
        F = asset_forecasts(d, adj, iv, msm=True)
        assets[s] = {"days": d, "adj": adj, "B": VRA.bill_index(d, acc), "iv": iv, "F": F}
        from datetime import datetime, timezone
        rows[s] = {datetime.fromtimestamp(float(r["value"]["t"]), tz=timezone.utc).strftime("%Y-%m-%d"): r["value"]
                   for r in CAL._rows(archive, dh(s))}
    R = risk_target_test(assets)
    W, E = R["win"], R["early"]
    S = W["SHAR"]
    n = int(S["n"])
    if n < 30 or S["qlike"].get("p_less") is None:
        return _out({"n": n}, n, "inconclusive", "too few tracking windows / forecast origins in 2015-01..2026-09")
    try:
        cross = gk_and_intraday(R["_per"], rows)
    except (ValueError, KeyError, OSError, TypeError, IndexError) as exc:  # reported-only cross-checks never decide
        cross = {"error": repr(exc)}
    q = S["qlike"]
    gate_ok = (q["mean"] < 0) and q["p_less"] < 0.05
    t = S["test"]
    ci_row = BW._ci_crit(t, "lt", 0.0, "upper 95% bound of the pooled tracking-loss difference (SHAR - EWMA) < 0 "
                                       "(paired studentized CBB, 63-day blocks, assets jointly; every overlapping "
                                       "21-session window, rule 10)")
    ph = R["holm"].get("SHAR")
    holm_ok = CAL.decide_p(ph, R["holm_draws"])
    holm_row = ((f"Holm-adjusted (SHAR, HAR, HAR-IV) one-sided p of the SHAR tracking-loss difference < 0.05 "
                 f"(p {_f(t.get('p_lt'), 4)}, adjusted {_f(ph, 4)})"), holm_ok, False)
    track = conj([ci_row, holm_row], "tracking criterion (interval and Holm both required)")
    sdiff = S["sharpe_diff"]
    rows_ = [((f"pooled 21-day QLIKE SHAR {_f(S['qlike_level'], 4)} < EWMA {_f(S['qlike_ewma'], 4)} with one-sided "
               f"Diebold-Mariano p < 0.05 (mean differential {_s(q['mean'], 4)}, t {_s(q['t'], 2)}, p {_f(q['p_less'], 4)}, "
               f"Bartlett bandwidth 63, {q['n']} origins)"), gate_ok, not gate_ok),
             track,
             (f"pooled net Sharpe difference (SHAR - EWMA) point estimate >= 0 ({_s(sdiff, 3)})",
              None if sdiff is None else sdiff >= 0, sdiff is not None and sdiff < 0)]
    v, why, crit = CAL._judge(rows_, n, T683_MIN_N, "windows")
    fcs = R["fc_names"]
    stat = {"n_windows": n, "window": list(T683_WIN), "assets": list(T683_ASSETS),
            "win": {fn: {k: W[fn].get(k) for k in ("n", "loss", "loss_ewma", "diff", "qlike", "qlike_level", "qlike_ewma",
                                                     "phase_range", "sharpe_diff", "util_gain_bp")}
                    | {"test": {k: W[fn].get("test", {}).get(k) for k in ("est", "ci", "ci_mc_se", "p_lt", "reps")}}
                    for fn in fcs[1:]},
            "early": {fn: {k: E[fn].get(k) for k in ("n", "diff", "qlike", "sharpe_diff", "util_gain_bp")}
                      | {"ci": E[fn].get("test", {}).get("ci")} for fn in fcs[1:]},
            "sharpe": W["sharpe"], "turnover": W["turnover"], "const": W["const"], "util": W["util"], "holm": R["holm"],
            "fits": R["per"], "cross_checks": cross, "criteria": crit,
            "rule10": "daily decisions; the 21-session tracking windows pool every one of the 21 phases"}
    def fc_txt(fn):
        x = W[fn]
        tt = x.get("test", {})
        return (f"{fn}: tracking loss {_f(x['loss'], 4)} vs EWMA {_f(x['loss_ewma'], 4)}, diff {_s(x['diff'], 4)} "
                f"{_ci(tt.get('ci'), 4)} (phases {_s(x['phase_range'][0], 4)}..{_s(x['phase_range'][1], 4)}), QLIKE "
                f"{_f(x['qlike_level'], 4)} vs {_f(x['qlike_ewma'], 4)} (DM t {_s(x['qlike']['t'], 2)}), net Sharpe diff "
                f"{_s(x['sharpe_diff'], 3)}, utility gain {_s(x['util_gain_bp'], 1)} bp/yr")
    cst = W["const"]
    reason = ("Six ETFs (adjclose; DTB3 bills), 10% target min(2, 0.10 / sqrt(252 F / 21)), decided at close t and "
              "filled at close t+1, 2 bp per unit of turnover; forecasters refitted at every month-end on expanding "
              "windows from 2004 (first bar + 500 rows; HAR-IV also from each index's first print + 250 sessions; first HAR-IV refits "
              + ", ".join(f"{s_} {R['per'][s_]['iv_entry']}" for s_ in T683_ASSETS)
              + f"); {n} overlapping 21-session windows {T683_WIN[0]}..{T683_WIN[1]}. " + fc_txt("SHAR") + "; "
              + "; ".join(fc_txt(fn) for fn in fcs[1:] if fn != "SHAR")
              + "; Holm-adjusted tracking p " + ", ".join(f"{k} {_f(x, 4)}" for k, x in R["holm"].items())
              + "; per-asset net Sharpe EWMA " + ", ".join(f"{s_} {_s(x, 2)}" for s_, x in zip(T683_ASSETS, W["sharpe"]["EWMA"]))
              + " / SHAR " + ", ".join(f"{s_} {_s(x, 2)}" for s_, x in zip(T683_ASSETS, W["sharpe"]["SHAR"]))
              + "; turnover a year " + ", ".join(f"{k} {x:.2f}" for k, x in W["turnover"].items())
              + "; constant weight at each forecaster's mean exposure (SHAR) tracking loss "
              + ", ".join(f"{s_} {x['loss']:.3f} vs {x['loss_fc']:.3f}" for s_, x in zip(T683_ASSETS, cst["SHAR"]))
              + f". Reported 2005-2014 (windows where all six have forecasts, from {E.get('first_window')}): SHAR tracking diff {_s(E['SHAR']['diff'], 4)} "
              f"{_ci(E['SHAR'].get('test', {}).get('ci'), 4)}, QLIKE DM t {_s(E['SHAR']['qlike']['t'], 2)}, net Sharpe diff "
              f"{_s(E['SHAR']['sharpe_diff'], 3)}"
              + ("; Garman-Klass proxy (stale opens " + ", ".join(f"{k} {x['stale_share']:.1%}" for k, x in cross["gk"].items()
                                                                   if isinstance(x, dict) and "stale_share" in x)
                 + f") QLIKE SHAR - EWMA {_s((cross['gk'].get('pooled') or {}).get('mean'), 4)} (t "
                 f"{_s((cross['gk'].get('pooled') or {}).get('t'), 2)}); 60-minute bars "
                 f"{(cross['h60'].get('span') or ['n/a', 'n/a'])[0]}..{(cross['h60'].get('span') or ['n/a', 'n/a'])[1]} "
                 f"{_s((cross['h60'].get('pooled') or {}).get('mean'), 4)} (t {_s((cross['h60'].get('pooled') or {}).get('t'), 2)})"
                 if "gk" in cross else f"; cross-checks failed ({cross.get('error')})")
              + ". A pass is risk control, not alpha — " + why)
    return _out(stat, n, v, reason)


# ================================================================================== T-690 price-free ETF ML book ==

T690_EXCLUDE = ("TQQQ", "SQQQ", "IBIT", "ETHA")
T690_H = 63
T690_HIST = 252
T690_TRAIN_FROM = "2018-01-01"          # the first year with FINRA short-interest publications
T690_DEV = ("2019-01", "2025-09")
T690_LOCKBOX_FROM = "2026-10"
T690_LOCKBOX_N = 12
T690_DATA_END = "2025-12-31"            # nothing later is loaded: the T-578 window (2026-01..09) and the lockbox stay out
T690_COST_SIDE = 1e-4                   # T-577's per-side ETF cost (mandel.ml.train.COST)
T690_BORROW = 0.005
T690_TRANCHES = 3
T690_CELLS = 764 + 2
T690_MIN_N = 80
T690_FEATS = ("si_log", "si_chg", "si_dtc", "regsho_svr20", "vol_z", "dvol_z", "rv63", "dsv63", "skew63", "iv_log",
              "fomc_days", "cpi_days")
T690_SI = ("si_log", "si_chg", "si_dtc")
T690_IVF = ("iv_log",)
T690_CLIP = 10.0
SI_PREFIX = "finra-short-interest-"
CNMS_PROBE = "finra-regsho-cnms-2018-08"
FOMC_B = "fomc-meetings"
CPI_B = "macro-release-cpi"


def t690_universe() -> list:
    from mandel.ml.fetch import BOND_ETF, COMMOD_ETF, EQUITY_ETF
    return [s for s in EQUITY_ETF if s not in T690_EXCLUDE] + list(BOND_ETF) + list(COMMOD_ETF)


def t690_iv_map(syms: Sequence[str]) -> dict:
    """The matched Cboe implied-vol index per ETF where one exists (the ML program's own map, mandel.ml.implied.OWN_IV,
    plus SPY -> VIX); ETFs without one get none."""
    from mandel.ml import implied as IM
    out = {}
    for s in syms:
        k = "VIX" if s == "SPY" else IM.OWN_IV.get(s)
        if k and not k.startswith("dvol"):
            out[s] = k
    return out


def close_ts(days: Sequence[str]) -> np.ndarray:
    """UTC epoch of 16:00 New York on each day (an ETF daily bar is known at its close)."""
    import pandas as pd
    t = pd.to_datetime(list(days)).tz_localize("America/New_York") + pd.Timedelta(hours=16)
    return t.tz_convert("UTC").as_unit("s").asi8.astype(np.int64)


def asof_values(ev_ts, ev_val, query_ts) -> np.ndarray:
    """Latest event value with timestamp <= each query time (NaN before the first)."""
    ev_ts = np.asarray(ev_ts, np.int64)
    o = np.argsort(ev_ts, kind="stable")
    ev_ts, ev_val = ev_ts[o], np.asarray(ev_val, float)[o]
    j = np.searchsorted(ev_ts, np.asarray(query_ts, np.int64), side="right") - 1
    out = np.full(len(query_ts), np.nan)
    ok = j >= 0
    out[ok] = ev_val[j[ok]]
    return out


def days_to_next(ev_ts, query_ts) -> np.ndarray:
    """Calendar days from each query time to the next event strictly after it (NaN when none is scheduled)."""
    ev = np.sort(np.asarray(ev_ts, np.int64))
    q = np.asarray(query_ts, np.int64)
    j = np.searchsorted(ev, q, side="right")
    out = np.full(q.size, np.nan)
    ok = j < ev.size
    out[ok] = (ev[j[ok]] - q[ok]) / 86400.0
    return out


def rolling_price_free(lr, v, dv) -> dict:
    """Per-column trailing features at each close i (windows end at i): rv63 = sd of 63 daily log returns x sqrt 252,
    dsv63 = 252/63 x sum of squared negative ones, skew63 = their skewness, vol_z / dvol_z = (20-session mean of
    log(1 + volume) [dollar volume] - its 252-session mean) / its 252-session sd."""
    import pandas as pd
    L = pd.DataFrame(lr)
    out = {"rv63": (L.rolling(63, min_periods=63).std() * math.sqrt(252.0)).values,
           "dsv63": ((L.where(L < 0, 0.0) ** 2).rolling(63, min_periods=63).sum() * 252.0 / 63.0).where(L.notna().rolling(63).sum() == 63).values,
           "skew63": L.rolling(63, min_periods=63).skew().values}
    for nm, x in (("vol_z", v), ("dvol_z", dv)):
        X = pd.DataFrame(np.log1p(np.asarray(x, float)))
        m20 = X.rolling(20, min_periods=20).mean()
        m252 = X.rolling(252, min_periods=252).mean()
        s252 = X.rolling(252, min_periods=252).std()
        out[nm] = ((m20 - m252) / s252.where(s252 > 0)).values
    return out


def fwd_open_target(O, bill_logc, h: int = T690_H) -> tuple:
    """y[i] = log(O[i + 1 + h] / O[i + 1]) - (bill log growth over the same opens); the target is realised at session
    i + 1 + h (returned as that index, -1 when beyond the data)."""
    O = np.asarray(O, float)
    n = O.shape[0]
    y = np.full(O.shape, np.nan)
    end = np.full(n, -1, int)
    if n > h + 1:
        a, b = np.arange(n - h - 1) + 1, np.arange(n - h - 1) + 1 + h
        with np.errstate(divide="ignore", invalid="ignore"):
            y[:n - h - 1] = np.log(O[b] / O[a]) - (bill_logc[b] - bill_logc[a])[:, None]
        end[:n - h - 1] = b
    return y, end


def load_si(archive, syms: Sequence[str]) -> dict:
    """{sym: (available_at epochs, log1p(SI), changePercent, daysToCover)} from every FINRA short-interest bundle,
    keyed by publication time; rows available after a bundle's capture are dropped."""
    from mandel.experiments import batch6c_stockxs as SX
    want = set(syms)
    acc = {s: [] for s in syms}
    for nm in SX._entry_names(archive, SI_PREFIX):
        for r in SX._stream(archive, nm):
            v = r.get("value") or {}
            s = (v.get("symbolCode") or "").strip().upper()
            if s not in want:
                continue
            try:
                av = int(SX._ts(r["available_at"]))
            except (KeyError, ValueError, TypeError):
                continue
            acc[s].append((av, math.log1p(max(SX._num(v.get("currentShortPositionQuantity")), 0.0)),
                           SX._num(v.get("changePercent")), SX._num(v.get("daysToCoverQuantity"))))
    out = {}
    for s, rows in acc.items():
        if rows:
            a = np.array(sorted(rows), float)
            out[s] = (a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3])
    return out


def load_iv_known(archive, sym: str) -> tuple | None:
    """(available_at epochs, log close) of a Cboe index history (closes are archived at 21:30 UTC)."""
    from mandel.experiments import batch6c_stockxs as SX
    nm = cboe(sym)
    if not B7C._has(archive, nm):
        return None
    ts, vals = [], []
    for r in CAL._rows(archive, nm):
        c = (r.get("value") or {}).get("close")
        try:
            c = float(c)
            a = int(SX._ts(r["available_at"]))
        except (TypeError, ValueError, KeyError):
            continue
        if c > 0:
            ts.append(a)
            vals.append(math.log(c))
    return (np.array(ts, np.int64), np.array(vals)) if ts else None


def adj_factors(archive, sym: str) -> dict | None:
    """{day: adjclose / close} from the archived Yahoo bundle (streamed, nothing cached): dividends for the local
    bars, which are unadjusted. A bar without adjclose carries the previous ratio, as batch6c_cal._daily."""
    from datetime import datetime, timezone

    from mandel.experiments import batch6c_stockxs as SX
    nm = dh(sym)
    if not B7C._has(archive, nm):
        return None
    by = {}
    for r in SX._stream(archive, nm):
        v = r.get("value") or {}
        try:
            c = float(v.get("close"))
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, KeyError):
            continue
        try:
            a = float(v.get("adjclose"))
        except (TypeError, ValueError):
            a = float("nan")
        if c > 0:
            by[d] = a / c if (a > 0 and math.isfinite(a)) else float("nan")
    out, ratio = {}, 1.0
    for d in sorted(by):
        if math.isfinite(by[d]):
            ratio = by[d]
        out[d] = ratio
    return out


def build_t690_panel(bars: dict, factors: dict, si: dict, iv_known: dict, iv_map: dict, fomc_ts, cpi_ts, bill_logc_fn,
                     end: str = T690_DATA_END) -> dict:
    """Days x symbols matrices on the SPY session calendar (through ``end``): adjusted and raw opens, features at
    each close and the 63-session excess-return targets under both price readings. ``bars`` {sym: DataFrame o h l
    c v indexed by UTC bar stamp}; ``factors`` {sym: {day: adj/close} or None}."""
    syms = list(bars)
    ref = bars["SPY"] if "SPY" in bars else next(iter(bars.values()))
    days = sorted({t.strftime("%Y-%m-%d") for t in ref.index.tz_convert("America/New_York")})
    days = [d for d in days if d <= end]
    pos = {d: i for i, d in enumerate(days)}
    n, m = len(days), len(syms)
    O = np.full((n, m), np.nan)
    C = np.full((n, m), np.nan)
    V = np.full((n, m), np.nan)
    Fa = np.ones((n, m))
    for j, s in enumerate(syms):
        b = bars[s]
        dd = [t.strftime("%Y-%m-%d") for t in b.index.tz_convert("America/New_York")]
        for d, o, c, v in zip(dd, b["o"].values, b["c"].values, b["v"].values):
            i = pos.get(d)
            if i is not None:
                O[i, j], C[i, j], V[i, j] = o, c, v
        fct = factors.get(s)
        if fct:
            ks = sorted(fct)
            vals = np.array([fct[k] for k in ks])
            jj = np.searchsorted(np.array(ks), np.array(days), side="right") - 1
            Fa[:, j] = np.where(jj >= 0, vals[np.maximum(jj, 0)], 1.0)
    cts = close_ts(days)
    bill = np.array([bill_logc_fn(d) for d in days])
    hist = np.cumsum(np.isfinite(C).astype(int), axis=0)
    feats = {}
    for rd, (Ox, Cx) in (("adj", (O * Fa, C * Fa)), ("raw", (O, C))):
        with np.errstate(divide="ignore", invalid="ignore"):
            lr = np.vstack([np.full((1, m), np.nan), np.log(Cx[1:] / Cx[:-1])])
        f = rolling_price_free(lr, V, C * V)
        f["vn"] = np.asarray(__import__("pandas").DataFrame(lr).rolling(20, min_periods=20).std().values) * math.sqrt(T690_H)
        y, yend = fwd_open_target(Ox, bill)
        feats[rd] = {"f": f, "y": y, "O": Ox}
    common = {k: np.full((n, m), np.nan) for k in ("si_log", "si_chg", "si_dtc", "regsho_svr20", "iv_log")}
    for j, s in enumerate(syms):
        if s in si:
            a, lv, ch, dtc = si[s]
            common["si_log"][:, j] = asof_values(a, lv, cts)
            common["si_chg"][:, j] = asof_values(a, ch, cts)
            common["si_dtc"][:, j] = asof_values(a, dtc, cts)
        k = iv_map.get(s)
        if k and iv_known.get(k) is not None:
            a, lv = iv_known[k]
            common["iv_log"][:, j] = asof_values(a, lv, cts)
    common["fomc_days"] = np.repeat(days_to_next(fomc_ts, cts)[:, None], m, 1)
    common["cpi_days"] = np.repeat(days_to_next(cpi_ts, cts)[:, None], m, 1)
    return {"days": days, "syms": syms, "hist": hist, "common": common, "read": feats, "yend": yend, "close_ts": cts}


def _feature_stack(Pn: dict, rd: str, cols: Sequence[str], rows) -> np.ndarray:
    """(rows, features) of the (day, sym) index pairs ``rows``."""
    i, j = rows
    src = {**Pn["common"], **Pn["read"][rd]["f"]}
    return np.column_stack([src[c][i, j] for c in cols])


def fit_predict_year(Pn: dict, rd: str, cols: Sequence[str], kind: str, year: int, dec_idx) -> dict:
    """Fit on every (session, ETF) row from T690_TRAIN_FROM with >= 252 sessions of history whose target was realised
    before 1 January of ``year`` (purged), on the target divided by its trailing scale (clipped at +-10, the ML
    program's convention); predict the excess return at the decision sessions ``dec_idx``. Missing features take the
    training median (an all-missing column is constant)."""
    import warnings

    from mandel.ml import train as TR
    days = np.array(Pn["days"])
    R = Pn["read"][rd]
    y, vn = R["y"], R["f"]["vn"]
    fit_date = f"{year}-01-01"
    yend = Pn["yend"]
    end_day = np.where(yend >= 0, days[np.maximum(yend, 0)], "9999-99-99")
    rowmask = (days[:, None] >= T690_TRAIN_FROM) & (end_day[:, None] < fit_date) & (Pn["hist"] >= T690_HIST) \
        & np.isfinite(y) & np.isfinite(vn) & (vn > 0)
    ti, tj = np.where(rowmask)
    if ti.size < 500:
        return {"ok": False, "n_train": int(ti.size)}
    X = _feature_stack(Pn, rd, cols, (ti, tj))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)              # the all-missing RegSHO column
        med = np.nanmedian(np.where(np.isfinite(X), X, np.nan), axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    X = np.where(np.isfinite(X), X, med)
    yn = np.clip(y[ti, tj] / vn[ti, tj], -T690_CLIP, T690_CLIP)
    model = TR.make_model(kind)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, yn)
    preds = {}
    for i in dec_idx:
        js = np.where((Pn["hist"][i] >= T690_HIST) & np.isfinite(vn[i]) & (vn[i] > 0))[0]
        if js.size == 0:
            continue
        Xi = _feature_stack(Pn, rd, cols, (np.full(js.size, i), js))
        Xi = np.where(np.isfinite(Xi), Xi, med)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p = model.predict(Xi)
        preds[int(i)] = (js, p * vn[i, js])
    imp = None
    if kind == "gbm":
        imp = dict(zip(cols, (model.booster_.feature_importance("gain") / max(1e-12, model.booster_.feature_importance("gain").sum())).tolist()))
    else:
        coef = model[-1].coef_
        imp = dict(zip(cols, coef.tolist()))
    return {"ok": True, "n_train": int(ti.size), "preds": preds, "importance": imp}


def month_end_sessions(days: Sequence[str]) -> np.ndarray:
    """Each calendar month's last session (the final month only when the next session exists)."""
    return np.array([i for i in range(len(days) - 1) if days[i][:7] != days[i + 1][:7]], int)


def _leg_value(O, idx, e0: int, t: int) -> float:
    """Equal-weight buy-and-hold leg value at session t per unit invested at the open of session e0."""
    return float(np.mean(O[t, idx] / O[e0, idx])) if len(idx) else 0.0


def tranche_book(O, dec: Sequence[int], sel: dict, days: Sequence[str], cost: float = T690_COST_SIDE,
                 borrow: float = T690_BORROW, k_tr: int = T690_TRANCHES, long_only: bool = False, bill_logc=None) -> dict:
    """Jegadeesh-Titman book: the tranche formed at decision k (``sel[k]`` = (long indices, short indices)) enters at
    the open after decision k and exits at the open after decision k + k_tr, 1/k_tr of capital each (buy and hold
    inside the tranche); a missing tranche is cash. Book month j runs between the opens after decisions j and j + 1.
    Each side costs ``cost`` per unit traded (entry at 1/k_tr per leg, exit at the leg's value), the short leg pays
    ``borrow`` a year on its value. Long-short excess = the P&L per unit of capital (collateral at bills); long-only
    excess subtracts the bill accrual on the invested value. ``dec`` must extend k_tr decisions past the last tranche
    to score it fully; months are scored for the decisions with a following one."""
    O = np.asarray(O, float)
    dec = list(dec)
    E = [d + 1 for d in dec]
    M = len(dec) - 1
    out = np.full(M, np.nan)
    gross = np.zeros(M)
    w = 1.0 / k_tr
    for j in range(M):
        a, b = E[j], E[j + 1]
        if b >= O.shape[0]:
            break
        pnl, cst, brw = 0.0, 0.0, 0.0
        gap = (date.fromisoformat(days[b]) - date.fromisoformat(days[a])).days
        for k in range(j - k_tr + 1, j + 1):
            if k < 0 or k not in sel:
                continue
            L, S = sel[k]
            e0 = E[k]
            La, Lb = _leg_value(O, L, e0, a), _leg_value(O, L, e0, b)
            Sa, Sb = (0.0, 0.0) if long_only else (_leg_value(O, S, e0, a), _leg_value(O, S, e0, b))
            pnl += w * ((Lb - La) - (Sb - Sa))
            if long_only and bill_logc is not None:
                pnl -= w * La * (math.exp(bill_logc[b] - bill_logc[a]) - 1.0)
            if k == j:
                cst += cost * w * (1.0 + (0.0 if long_only else 1.0))
            if k == j - k_tr + 1:
                cst += cost * w * (Lb + Sb)
            brw += borrow * w * Sa * gap / 365.0
        gross[j] = pnl
        out[j] = pnl - cst - brw
    return {"net": out, "gross": gross}


def xs_select(js, score, frac: float = 0.2, low_is_long: bool = False) -> tuple:
    """(long, short) column indices: the top and bottom floor(frac x N) by ``score`` (ties by index)."""
    js, score = np.asarray(js), np.asarray(score, float)
    ok = np.isfinite(score)
    js, score = js[ok], score[ok]
    k = math.floor(frac * js.size)
    if k < 1:
        return np.array([], int), np.array([], int)
    o = np.argsort(score, kind="stable")
    lo, hi = js[o[:k]], js[o[-k:]]
    return (lo, hi) if low_is_long else (hi, lo)


def min_sharpe_for_dsr(n: int, n_trials: int, target: float = DSR_PASS) -> float:
    """Smallest per-period Sharpe with ML-program DSR >= target (skew 0, kurtosis 3), by bisection."""
    from mandel.ml import train as TR
    lo, hi = 0.0, 5.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if TR.deflated_sharpe(mid, n, n_trials) >= target:
            hi = mid
        else:
            lo = mid
    return hi


def _series_stats(x) -> dict:
    from mandel.ml import train as TR
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 4 or not x.std(ddof=1) > 1e-12:
        return {"n": int(x.size), "sr_m": None, "sr_ann": None, "mean_m": None, "dsr": None}
    sr = float(x.mean() / x.std(ddof=1))
    sk = float(((x - x.mean()) ** 3).mean() / x.std() ** 3)
    ku = float(((x - x.mean()) ** 4).mean() / x.std() ** 4)
    return {"n": int(x.size), "sr_m": sr, "sr_ann": sr * math.sqrt(12.0), "mean_m": float(x.mean()),
            "dsr": float(TR.deflated_sharpe(sr, int(x.size), T690_CELLS, sk, ku)), "skew": sk, "kurt": ku}


def ml_book_dev(Pn: dict, rd: str, cols: Sequence[str], kind: str) -> dict:
    """Development book of one model under one price reading: annual refits 2019..2025, decisions 2019-01..2025-09."""
    days = Pn["days"]
    me = month_end_sessions(days)
    dev = [i for i in me if T690_DEV[0] <= days[i][:7] <= T690_DEV[1]]
    if not dev:
        return {"ok": False}
    sel, imp, ntr = {}, {}, {}
    for year in sorted({int(days[i][:4]) for i in dev}):
        di = [i for i in dev if int(days[i][:4]) == year]
        fp = fit_predict_year(Pn, rd, cols, kind, year, di)
        ntr[year] = fp["n_train"]
        if not fp["ok"]:
            continue
        imp[year] = fp["importance"]
        O = Pn["read"][rd]["O"]
        for i, (js, p) in fp["preds"].items():
            ok = np.isfinite(O[i + 1, js]) if i + 1 < O.shape[0] else np.zeros(js.size, bool)
            sel[dev.index(i)] = xs_select(js[ok], p[ok])
    k0 = list(me).index(dev[0])
    dec = list(me[k0:k0 + len(dev) + 1])
    book = tranche_book(Pn["read"][rd]["O"], dec, sel, days)
    net = book["net"][:len(dev)]
    st = _series_stats(net)
    return {"ok": True, "net": net, "gross": book["gross"][:len(dev)], "stats": st, "n_dec": len(dev), "n_tranches": len(sel),
            "importance_last": imp.get(max(imp)) if imp else None, "n_train": ntr, "labels": [days[i][:7] for i in dev]}


def baseline_books(Pn: dict, rd: str = "adj") -> dict:
    """Always-long the ETF set and the single-feature days-to-cover sort (long the lowest fifth, short the highest)."""
    days = Pn["days"]
    me = month_end_sessions(days)
    dev = [i for i in me if T690_DEV[0] <= days[i][:7] <= T690_DEV[1]]
    k0 = list(me).index(dev[0])
    dec = list(me[k0:k0 + len(dev) + 1])
    O = Pn["read"][rd]["O"]
    sel_l, sel_d = {}, {}
    bill = Pn.get("bill")
    for k, i in enumerate(dev):
        js = np.where((Pn["hist"][i] >= T690_HIST) & np.isfinite(O[min(i + 1, O.shape[0] - 1)]))[0]
        sel_l[k] = (js, np.array([], int))
        sel_d[k] = xs_select(js, Pn["common"]["si_dtc"][i, js], low_is_long=True)
    al = tranche_book(O, dec, sel_l, days, long_only=True, bill_logc=bill)["net"][:len(dev)]
    dt = tranche_book(O, dec, sel_d, days)["net"][:len(dev)]
    return {"always_long": _series_stats(al), "dtc_sort": _series_stats(dt)}


def b13_volregime_b_ml_price_free_etf(archive):
    """T-690: price-free ridge / GBM on the ML program's non-leveraged ETFs, 63-session tranche book (dev + lockbox)."""
    from mandel.experiments import batch6c_stockxs as SX
    si_names = SX._entry_names(archive, SI_PREFIX)
    need = [DTB3_B, FOMC_B, CPI_B, CNMS_PROBE, cboe("VIX")]
    miss = _missing(archive, need)
    if miss:
        return miss
    if not si_names:
        return _out({"missing": [SI_PREFIX + "*"]}, 0, "inconclusive", "missing data bundles finra-short-interest-*: rule 9")
    from mandel.ml import swing as SW
    syms = t690_universe()
    bars = {}
    for s in syms:
        try:
            b = SW.load_daily(s)
        except ValueError:
            b = None
        if b is not None and len(b):
            bars[s] = b
    if "SPY" not in bars:
        return _out({"missing": ["mandel/ml_data/bars/1d"]}, 0, "inconclusive",
                    "local daily bars (mandel/ml_data/bars/1d) are not on this machine: rule 9")
    # RegSHO: the registered 20-day short-volume ratio needs ETF rows; probe what the archive holds
    cnms = [r.get("value", {}).get("symbol") for r in CAL._rows(archive, CNMS_PROBE) if r.get("kind") == "short-volume"]
    regsho_etfs = sorted(set(cnms) & set(syms))
    acc = RATES.Accrual(CAL._series(archive, DTB3_B), "bey")
    bill_fn = lambda d: acc._c(VRA._ord(d))
    fomc = [r["value"] for r in CAL._rows(archive, FOMC_B)]
    fomc_ts = close_ts([v["decision_day"] for v in fomc if v.get("scheduled")]) - 2 * 3600   # 14:00 ET statement
    cpi_ts = close_ts([r["value"]["day"] for r in CAL._rows(archive, CPI_B)]) - int(7.5 * 3600)   # 08:30 ET release
    ivm = t690_iv_map(list(bars))
    ivk = {k: load_iv_known(archive, k) for k in sorted(set(ivm.values()))}
    fac = {s: adj_factors(archive, s) for s in bars}
    si = load_si(archive, list(bars))
    Pn = build_t690_panel(bars, fac, si, ivk, ivm, fomc_ts, cpi_ts, bill_fn)
    Pn["bill"] = np.array([bill_fn(d) for d in Pn["days"]])
    del bars
    nd = 0
    days = Pn["days"]
    me = month_end_sessions(days)
    dev = [i for i in me if T690_DEV[0] <= days[i][:7] <= T690_DEV[1]]
    nd = len(dev)
    min_sr = min_sharpe_for_dsr(nd, T690_CELLS)            # stated before any model is fitted or read
    cols = list(T690_FEATS)
    res = {}
    for rd in ("adj", "raw"):
        for kind in ("ridge", "gbm"):
            res[(rd, kind)] = ml_book_dev(Pn, rd, cols, kind)
    abl = {}
    for nm, drop in (("no_si", T690_SI), ("no_iv", T690_IVF)):
        cc = [c for c in cols if c not in drop]
        for kind in ("ridge", "gbm"):
            r_ = ml_book_dev(Pn, "adj", cc, kind)
            abl[f"{nm}|{kind}"] = r_["stats"] if r_.get("ok") else None
    base = baseline_books(Pn)
    passes = {kind: all((res[(rd, kind)].get("stats") or {}).get("dsr") is not None
                        and res[(rd, kind)]["stats"]["dsr"] >= DSR_PASS for rd in ("adj", "raw")) for kind in ("ridge", "gbm")}
    any_dev = any(passes.values())
    cover = {k: int(np.isfinite(v).any(0).sum()) for k, v in Pn["common"].items()}
    last_day = days[-1]
    # criteria
    rows = [((f"every registered input archived for the universe: the 20-day RegSHO short-volume ratio has "
              f"{len(regsho_etfs)} of {len(Pn['syms'])} ETFs in finra-regsho-cnms (the bundles keep point-in-time "
              f"S&P 500 members only) — rule 9"), None if not regsho_etfs else True, False),
            ((f"some model with development DSR >= {DSR_PASS} (N = {T690_CELLS} ML-program cells, {nd} monthly decisions "
              f"{T690_DEV[0]}..{T690_DEV[1]}) under both price readings: "
              + "; ".join(f"{kind} adj {_f((res[('adj', kind)].get('stats') or {}).get('dsr'))} / raw "
                          f"{_f((res[('raw', kind)].get('stats') or {}).get('dsr'))}" for kind in ("ridge", "gbm"))
              + " [computed on the model without the unarchived RegSHO input, so it cannot decide: rule 9]"),
             None, False),
            ((f"a development survivor has a positive mean net return over the first {T690_LOCKBOX_N} lockbox decisions "
              f"from {T690_LOCKBOX_FROM} (sealed: 0 of {T690_LOCKBOX_N} lockbox decisions exist, the first is the "
              f"{T690_LOCKBOX_FROM} month-end; nothing after {T690_DATA_END} was loaded)"
              + ("" if any_dev else "; no model survives development, so the lockbox would not be opened")), None, False)]
    v, why, crit = CAL._judge(rows, nd, T690_MIN_N, "monthly decisions")
    st = lambda r_: r_.get("stats") or {}
    stat = {"n_decisions": nd, "dev": list(T690_DEV), "n_symbols": len(Pn["syms"]), "symbols": Pn["syms"],
            "min_annual_sharpe_for_dsr": min_sr * math.sqrt(12.0), "min_monthly_sharpe_for_dsr": min_sr,
            "models": {f"{rd}|{kind}": {"stats": st(r_), "n_tranches": r_.get("n_tranches"), "n_train": r_.get("n_train"),
                                        "importance_last_fit": r_.get("importance_last")} for (rd, kind), r_ in res.items()},
            "ablations": abl, "baselines": base, "dev_pass": passes, "regsho_etfs": regsho_etfs,
            "feature_coverage_symbols": cover, "iv_map": ivm, "no_dividend_factor": [s for s, f in fac.items() if not f],
            "data_end_loaded": last_day, "criteria": crit, "rule10": "calendar named by the claim (month-end decisions)"}
    def mtxt(rd, kind):
        s_ = st(res[(rd, kind)])
        return (f"{kind} {rd} Sharpe {_s(s_.get('sr_ann'), 2)} (mean {_pc(s_.get('mean_m'), 2)}/month, DSR "
                f"{_f(s_.get('dsr'))})")
    gimp = (res[("adj", "gbm")].get("importance_last") or {})
    reason = (f"STATED BEFORE ANY FIT: at N = {T690_CELLS} trials and {nd} monthly decisions a DSR of 0.95 needs an annual "
              f"Sharpe of at least {min_sr * math.sqrt(12.0):.2f} (skew 0, kurtosis 3). DEVELOPMENT ({len(Pn['syms'])} ETFs: "
              f"mandel.ml.fetch's equity, bond and commodity ETFs less TQQQ, SQQQ, IBIT, ETHA; local daily bars through "
              f"{last_day}, opens dividend-adjusted from the archived Yahoo factors except "
              f"{', '.join(stat['no_dividend_factor']) or 'none'} (not archived: raw), and the raw-price reading as worded): "
              f"features at each month-end close from values published by then (FINRA SI log level, change and days to "
              f"cover by publication time; 63-session realised vol, downside semivariance and skewness; 20-vs-252-session "
              f"volume and dollar-volume z-scores; the matched Cboe index's last close archived by the decision; days to "
              f"the next scheduled FOMC decision and CPI release), target the 63-session open-to-open log excess return "
              f"(vol-scaled, clipped), refit every January on rows from 2018 whose target ended before the fit; top "
              f"fifth minus bottom fifth in 3 monthly tranches, 1 bp a side both legs, 50 bp a year borrow: "
              + "; ".join(mtxt(rd, kind) for rd in ("adj", "raw") for kind in ("ridge", "gbm"))
              + ". Ablations (adj) Sharpe: " + ", ".join(f"{k} {_s((x or {}).get('sr_ann'), 2)}" for k, x in abl.items())
              + f"; baselines: always-long {_s(base['always_long'].get('sr_ann'), 2)}, days-to-cover sort "
              f"{_s(base['dtc_sort'].get('sr_ann'), 2)}; GBM gain shares (2025 fit) "
              + ", ".join(f"{k} {x:.2f}" for k, x in sorted(gimp.items(), key=lambda kv: -kv[1])[:6])
              + f". NOT JUDGED: the registered RegSHO input is absent for every ETF ({CNMS_PROBE} and its siblings keep "
              f"S&P 500 members only), so the development DSR above belongs to a narrower model; and the lockbox "
              f"({T690_LOCKBOX_FROM}..) has no decisions yet. The ETF list was chosen in 2026 (mild survivor bias). — " + why)
    return _out(stat, nd, v, reason)


HARNESSES = {"b13_volregime_b_semivar_factors": b13_volregime_b_semivar_factors,
             "b13_volregime_b_leverage_did": b13_volregime_b_leverage_did,
             "b13_volregime_b_shar_risk_target": b13_volregime_b_shar_risk_target,
             "b13_volregime_b_ml_price_free_etf": b13_volregime_b_ml_price_free_etf}
THEORY_MAP = {"T-680": "b13_volregime_b_semivar_factors", "T-682": "b13_volregime_b_leverage_did",
              "T-683": "b13_volregime_b_shar_risk_target", "T-690": "b13_volregime_b_ml_price_free_etf"}
