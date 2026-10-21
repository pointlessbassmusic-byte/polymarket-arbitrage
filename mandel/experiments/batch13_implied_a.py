"""
Batch 13, group ``implied_a``: VX roll carry, the model-based VIX futures premium, VVIX-timed SPY put returns and the
BTC VRP by DVOL tercile (T-651, T-652, T-654, T-655), pre-registered from the 2026-10-20 web sweep (cluster "implied").
=====================================================================================================================

  * T-651  Cboe VX 2013-05-20..2026-10-14: F1 = the nearest monthly VX with >= 10 trading days to final settlement,
           roll_t = (F1 settle_t - VIX close_t) / trading days to F1's settlement. Short one F1 when roll_t > +0.10, buy one
           when < -0.10; enter at the t+1 settle, exit at the t+6 settle in the same contract; SPY hedge at a ratio fixed per
           trade from an OLS of daily F1 settle changes on SPY % changes and SPY % changes x trading days to settlement over
           the 252 sessions before entry. Pass: pooled (5 offsets) mean net P&L per trade after $140 > 0 with one-sided
           p < 0.05 by Newey-West AND the studentized CBB (12-trade blocks); both halves (split 2019-12-31) > 0; DSR >= 0.95
           over the 7-trial VX family. min_n 150 trades.
  * T-652  Once per VX cycle, the first session with <= 21 trading days to F1's final settlement: P_t = F1 settle_t -
           E_t[VIX at settlement] (AR(1) on daily log VIX plus log(VIX/VIX3M), expanding from 2009-09-18, iterated to the
           settlement date, lognormal half-variance correction). Pass, in 2013-05..2019-12 AND 2020-01..2026-10: (a) the
           short-futures return F1_t - FinalSettle has slope > 0 on P_t with one-sided p < 0.05 and 1 inside the 95% CI
           (Newey-West lag 1 and a studentized cycle bootstrap); (b) P_t's slopes on standardised VVIX and on standardised
           trailing 21-session SPY RV, each alone, are <= 0. min_n 150 cycles.
  * T-654  Weekly on dolt-chain-SPY 2019-02..2026-10 (entry = each week's last quote day, exit = the next week's last
           quote day, the same contracts mid-to-mid): (a) the delta-hedged return of 0.90-0.95 K/S puts in the expiry nearest
           30 DTE (14-60) falls with z(VVIX) given z(VIX) and RV21, confirmation 2023-2026, one-sided p < 0.05 (NW lag 2);
           (b) the 5%/10% OTM short put spread at bid/ask only in z(VVIX)'s 2019-2022 top tercile earns > 0 per unit max
           loss and more than the other weeks (bootstrap lower bounds > 0); DSR >= 0.95 over 4 trials. min_n 150 weeks.
  * T-655  Daily entries D = 2022-03-24..2026-09-14 at D+1 00:00 UTC: ratio = 1 - RV_fwd / (DVOL_D / 100)^2, RV_fwd =
           (365/30) x the sum of the 30 squared log returns of Coinbase BTC-USD closes from bar D through bar D+30. Pass:
           the bottom-minus-top (DVOL_D vs its trailing 365 days) tercile mean ratio has a studentized CBB (90-day blocks)
           lower 95% bound > 0, and both halves (2022-03-24..2024-06-30, 2024-07-01..2026-09-14) are positive. min_n 45.

Readings fixed before any run (each registration is silent or ambiguous here; the conservative reading is taken and the
reason line names it):
  * Trading days (T-651, T-652). The calendar is cboe-VIX-history's days that are NYSE sessions: from 2022 Cboe prints
    VIX on NYSE holidays (global trading hours; 32 such days by 2026-10), on which no VX settles and SPY does not trade,
    so they are not trading days. Trading days to settlement = sessions d with t < d <= expiry (the expiry day counts; on
    it the contract's row is its final settlement value); past the archive's last VIX day the NYSE calendar continues it.
  * T-651 grid (house rule 10). Decision days on offset o are the sessions o, o + 5, ... from 2013-05-20; a trade entered
    at the t+1 settle exits at the t+6 settle, the next grid entry, so trades on one offset never overlap and "no new
    entry while a trade is open" never binds. The pooled estimate is every signal day (all 5 offsets); the NW lag and
    the bootstrap block are 12 pooled trades (>= 2x the up-to-4-trade overlap), and the mean row needs both tests
    (``and_rows``: it fails when either fails). n = the fewest signal trades on any
    offset (a single offset's non-overlapping count; the pooled count is reported). The hedge regression uses the 252
    sessions ending at t (the changes into t-251..t, each in the contract that was F1 on its previous session, with its
    trading days to settlement on that session), so the ratio is known before the t+1 entry; all 252 changes must be
    valid, so trades start once VX settles have 252 sessions of history (2014-05). The ratio is b1 + b2 x tau at
    entry; the SPY position is -side x $1,000 x that ratio in dollars at the t+1 close, held to the t+6 close (adjclose,
    dividends included, no financing: the cash-financed reading SPY - DTB3 is a reported sensitivity, as are ES=F and
    $60). The DSR row is judged per offset on its non-overlapping trades (overlapping pooled trades would overstate T):
    only this trial's Sharpe is computed, so with the 1/(T-1) floor as the most favourable trial-Sharpe variance it can
    fail (every offset's bound below 0.95) but never pass (``dsr_vs_uncomputed_family``, as batch13_implied_b T-653).
    The ETP form uses an OLS beta of the ETP's daily returns on SPY's over the same 252 sessions, close t+1 to close t+6.
    "Excluding 2018-02 and 2020-03" drops trades whose entry or exit falls in those months.
  * T-652. The model is a VAR(1) on z = [log VIX, log(VIX/VIX3M)] (its log-VIX equation is the claim's AR(1) on log VIX
    plus log(VIX/VIX3M); the ratio's own equation is what iterating to the settlement date needs), fitted by OLS on the
    VIX/VIX3M common days from 2009-09-18 through t and iterated h = trading days to settlement steps; E[VIX_T] =
    exp(m_h + v_h / 2), v_h the iterated residual variance of log VIX. The cycle's t is the first session after the
    previous expiry with <= 21 trading days to F1's expiry (one per cycle, its window ends at the final settlement, so
    windows never overlap: no grid phase, rule 10); a cycle whose t lacks an input is skipped and counted. "Standardised"
    VVIX / RV21 is undefined, so (b) is judged under both readings (rule 11: it passes only when both do): the
    within-half z (a linear rescale, the slope's sign is that of the raw level) and the trailing 252-session z
    (T-654's definition). (a) is judged under Newey-West (lag 1) and the studentized pairs bootstrap of cycles (HC1
    studentizer, 5 seeds of 2,000), both registered: it passes only when both pass and fails when either fails
    (``and_rows``, a conjunction, not rule 11). The secondary Sharpe difference enters at the t+1 settle (P_t uses the
    16:15 ET VIX close, after the t settle) and gates on P_t above the median of >= 12 earlier cycles' P. E_t is
    iterated h = trading days to the expiry-day close; the final settlement is the expiry-morning SOQ, so the h - 1
    iteration is a reported sensitivity.
  * T-654 is unobservable as registered on this chain: DoltHub quotes a 2/4/8-week expiry ladder and a fixed K/S strike
    ladder (0.875, 0.90, 0.92, 0.94, ...) re-centred on each day's close, so the entry contract is seldom quoted a week
    later. The harness implements the registered trade (exit at the next week's last quote day, or the first quote day
    within 3 sessions after it that quotes the position's contracts, otherwise the week is skipped and counted) and
    reports what the observable weeks give, but every criterion is None (rule 9 data limit, as batch7_vol T-550) and the
    verdict is inconclusive: the observable weeks are selected by the vendor's listing pattern, not the claim's sample.
    fred-DTB3 is required (the registered hedged return is net of the bill rate, never silently gross). The registered
    controls (every-week short spread, VIX-only and SKEW-only terciles, a random-tercile placebo, unhedged returns) and
    the VVIX-on-VIX residual trial of the DSR set are computed on the same weeks and reported only.
  * T-655. Terciles: the share of the trailing 365 DVOL closes (bars D-364..D, all known at D+1 00:00) strictly below
    DVOL_D; bottom < 1/3, top >= 2/3. The bound is the lower end of the two-sided studentized 95% CI (the stricter
    reading of "lower 95% bound"), Monte Carlo resolved over 5 (25 when unresolved) seeds. n = the distinct 30-day holds
    the pooled entries span (batch6_xc's n_holds, the house unit for pooled daily entries); the 30-day blocks holding
    bottom and top entries are reported. The T-255 straddle is batch6_xc.hedged_straddle on Coinbase closes at DVOL
    (r = 0; the signed perpetual funding when deribit-funding-BTC-PERPETUAL is archived), P&L per unit of entry vega in
    vol points; DTB3 is not needed. The ETH control needs ETH prices the data list lacks: coinbase-daily-ETH-USD.
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive (``CAL._judge``,
    house rule 5). Bundles the judged statistic needs are required (rule 9); a control's missing bundle only drops it.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6_surf as SURF
from mandel.experiments import batch6_xc as XC
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6b_dolt as DOLT
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_hedge import vx_curve
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()

VX_B = "cboe-vx-futures"
VIX_B = "cboe-VIX-history"
VIX3M_B = "cboe-VIX3M-history"
VVIX_B = "cboe-VVIX-history"
SKEW_B = "cboe-SKEW-history"
SPY_B = "daily-history-SPY"
SVXY_B = "daily-history-SVXY"
VXX_B = "daily-history-VXX"
ESF_B = "daily-history-ES-F"
DTB3_B = "fred-DTB3"
CHAIN_B = "dolt-chain-SPY"
DVOL_B = "deribit-dvol-BTC-history"
DVOL_ETH_B = "deribit-dvol-ETH-history"
CB_BTC_B = "coinbase-daily-BTC-USD"
CB_ETH_B = "coinbase-daily-ETH-USD"
FUND_B = "deribit-funding-BTC-PERPETUAL"

# T-651
T651_START, T651_END = "2013-05-20", "2026-10-14"
T651_SPLIT = "2019-12-31"
T651_MIN_DAYS = 10
T651_THR = 0.10
T651_HOLD = 5
T651_WIN = 252
T651_WIN_MIN = 252               # every change in the window valid: the window lies inside the settle history
T651_MULT = 1000.0
T651_COST = 140.0
T651_COST_SENS = 60.0
T651_BLOCK = 12
T651_NW_LAG = 12
T651_FAMILY = 7                 # T-160, T-379, T-435, T-242, this row, T-652, T-653
T651_MIN_N = 150
T651_ETP_COST = 5e-4
T651_EXCL = ("2018-02", "2020-03")
# T-652
T652_FIT_FROM = "2009-09-18"
T652_START = "2013-05-20"
T652_HALVES = (("2013-05-01", "2019-12-31"), ("2020-01-01", "2026-10-31"))
T652_TAU = 21
T652_NW_LAG = 1
T652_MIN_N = 150
T652_Z_WIN = 252
T652_RV_WIN = 21
T652_MIN_PRIOR = 12
T652_COST = 140.0
T652_EX2020 = ("2020-02", "2020-03", "2020-04")
# T-654
T654_START, T654_END = "2019-02-01", "2026-10-31"
T654_DISC = ("2019-01-01", "2022-12-31")
T654_CONF = ("2023-01-01", "2026-10-31")
T654_DTE = (14, 60)
T654_TARGET = 30
T654_BIN = (0.90, 0.95)
T654_LEGS = (0.95, 0.90)
T654_MONEY_TOL = 0.02
T654_Z_WIN = 252
T654_RV_WIN = 21
T654_FALLBACK = 3
T654_NW_LAG = 2
T654_BLOCK = 8
T654_MIN_N = 150
T654_TRIALS = 4
# T-655
T655_START, T655_END = "2022-03-24", "2026-09-14"
T655_SPLIT = "2024-07-01"
T655_WIN = 365
T655_HOLD = 30
T655_BLOCK = 90
T655_MIN_N = 45
T655_GATE = 5.0
T655_PLACEBO = 1000


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


def dsr_vs_uncomputed_family(x, n_total: int, label: str) -> tuple:
    """DSR of ``x`` over ``n_total`` trials when only this trial's Sharpe is computed (as batch13_implied_b): the most
    favourable trial-Sharpe variance is the zero-skill floor 1/(T-1), so the DSR is at most its value there; fails when
    even that bound misses 0.95 (decisive when PSR vs 0 <= 0.05), undecided otherwise. ((name, ok, decisive), info)."""
    x = np.asarray(x, float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_upper_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_total, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_upper_bound": hi, "var_floor": floor, "psr0": psr0, "n_total": int(n_total), "sharpe_pp": float(sharpe_ratio(x)),
            "n": int(x.size)}
    txt = f"{label} (at most {hi:.3f} at {n_total} trials; PSR vs 0 {psr0:.3f})"
    if hi < DSR_PASS:
        return (txt + " [fails whatever the other trials' Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + f" [the other {n_total - 1} family Sharpes are not computed here: cannot pass]", None, False), info


def and_rows(rows: Sequence[tuple], label: str) -> tuple:
    """A registered conjunction of tests ('p < 0.05 by Newey-West AND the bootstrap'): passes only when every test
    passes, fails when any test fails (decisively when a failing test is decisive), and is undecided only when none fails
    and one is unresolved. Not rule 11: the tests are joint requirements, not alternative readings of an undefined term
    (``BW.all_constructions`` stays for those, e.g. T-652 (b)'s two standardisations)."""
    oks = [r[1] for r in rows]
    ok = False if any(o is False for o in oks) else (True if all(o is True for o in oks) else None)
    dec = bool(ok is False and any(r[1] is False and bool(r[2]) for r in rows))
    return f"{label}: " + "; ".join(r[0] for r in rows), ok, dec


def mean_rows(x, block: int, lag: int, label: str, n_boot: Optional[int] = None) -> tuple:
    """'mean > 0 with one-sided p < 0.05 by Newey-West and the bootstrap': both registered tests are required, so the
    row fails when either fails (``and_rows``); (row, info)."""
    x = np.asarray(x, float)
    nw = nw_mean(x, lag)
    t = nw["t"]
    p_nw = float(1.0 - _N.cdf(t)) if math.isfinite(t) else None
    nw_row = (f"Newey-West lag {lag}: t {_s(t, 2)}, one-sided p {_f(p_nw, 4)}",
              None if p_nw is None else bool(nw["mean"] > 0 and p_nw < ALPHA),
              bool(math.isfinite(t) and _N.cdf(t) < ALPHA))
    pg, pl, dr = CAL.studentized_p_escalated(x, block, n_boot, SEED, B7C.N_SEEDS)
    bt_row = (f"studentized CBB ({block}-period blocks): p {CAL._mc(pg, dr)}", B7C._sig_crit(nw["mean"], pg, dr),
              CAL.decide_p(pl, dr) is True)
    row = and_rows([nw_row, bt_row], label)
    return row, {"mean": nw["mean"], "nw_t": t, "nw_p": p_nw, "boot_p": pg, "boot_p_less": pl, "draws": dr, "n": int(x.size)}


def mdd(x) -> float:
    """Maximum drawdown of the cumulative sum of a P&L sequence (a positive number)."""
    c = np.cumsum(np.asarray(x, float))
    if c.size == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[0.0], c]))[1:]
    return float(np.max(peak - c))


def cvar(x, q: float = 0.01) -> Optional[float]:
    x = np.sort(np.asarray(x, float))
    if x.size == 0:
        return None
    k = max(1, int(math.ceil(q * x.size)))
    return float(x[:k].mean())


def _sr(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _usd(x, nd: int = 1) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"${x:+,.{nd}f}"


def _px(archive, name: str, field: str = "adjclose") -> dict:
    days, vals = CAL._daily(archive, name, field)
    return dict(zip(days, (float(v) for v in vals)))


# ====================================================================================== shared VX calendar ==

def trading_calendar(vix: dict, start: str = "") -> list:
    """cboe-VIX-history days that are NYSE sessions (the 2022+ VIX prints on NYSE holidays carry no VX settle)."""
    return [d for d in sorted(vix) if d >= start and CAL.is_nyse_session(d)]


def extended_calendar(cal: Sequence[str], last: str) -> list:
    """The calendar continued by NYSE sessions to ``last`` (expiries past the archive's last VIX day)."""
    out = list(cal)
    if not out:
        return out
    d = date.fromisoformat(out[-1])
    while True:
        d = CAL.next_session(d)
        if d.isoformat() > last:
            return out
        out.append(d.isoformat())


def sessions_to(ecal: Sequence[str], i: int, expiry: str) -> int:
    """Trading days from session i to the final settlement on ``expiry``: the sessions d with cal[i] < d <= expiry."""
    return bisect_right(ecal, expiry) - 1 - i


def front_contracts(ecal: Sequence[str], n: int, expiries, min_days: int) -> list:
    """For each session i < n: the nearest expiry with >= ``min_days`` trading days to its final settlement."""
    ex = sorted(set(expiries))
    eidx = [bisect_right(ecal, e) - 1 for e in ex]
    out, j = [], 0
    for i in range(n):
        while j < len(ex) and eidx[j] - i < min_days:
            j += 1
        out.append(ex[j] if j < len(ex) else None)
    return out


def curve_expiries(curve: dict) -> list:
    return sorted({e for d in curve for e in curve[d]})


# ============================================================================================ T-651 roll carry ==

def roll_at(curve: dict, vix: dict, cal: Sequence[str], ecal: Sequence[str], front: Sequence, i: int) -> Optional[tuple]:
    """(roll_t, F1 settle_t, tau_t) at the close of session i from that session's F1 settle and VIX close only."""
    c = front[i]
    if c is None:
        return None
    d = cal[i]
    s, v = curve.get(d, {}).get(c), vix.get(d)
    tau = sessions_to(ecal, i, c)
    if s is None or v is None or tau <= 0:
        return None
    return (s - v) / tau, s, tau


def daily_changes(cal: Sequence[str], ecal: Sequence[str], curve: dict, front: Sequence, px: dict) -> dict:
    """Per session s >= 1: dF = the settle change from s-1 to s of the contract that was F1 at s-1, tau = its trading
    days to settlement at s-1, r = the hedge instrument's % change close s-1 to close s; NaN where missing."""
    n = len(cal)
    dF, tau, r = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for s in range(1, n):
        c = front[s - 1]
        pa, pb = px.get(cal[s - 1]), px.get(cal[s])
        if pa and pb:
            r[s] = pb / pa - 1.0
        if c is None:
            continue
        a, b = curve.get(cal[s - 1], {}).get(c), curve.get(cal[s], {}).get(c)
        if a is not None and b is not None:
            dF[s] = b - a
        tau[s] = sessions_to(ecal, s - 1, c)
    return {"dF": dF, "tau": tau, "r": r}


def hedge_fit(ch: dict, i: int, win: int = T651_WIN, min_obs: int = T651_WIN_MIN) -> Optional[np.ndarray]:
    """OLS of dF on [1, r, r x tau] over the ``win`` sessions ending at session i (changes into i-win+1..i, all known at
    the close of i, before the t+1 entry); None with fewer than ``min_obs`` valid changes (T-651: all 252)."""
    lo = i - win + 1
    if lo < 1:
        return None
    y, r, t = ch["dF"][lo:i + 1], ch["r"][lo:i + 1], ch["tau"][lo:i + 1]
    ok = np.isfinite(y) & np.isfinite(r) & np.isfinite(t)
    if ok.sum() < min_obs:
        return None
    X = np.column_stack([np.ones(int(ok.sum())), r[ok], r[ok] * t[ok]])
    b, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    return b


def beta_fit(y_ret: np.ndarray, x_ret: np.ndarray, i: int, win: int = T651_WIN, min_obs: int = T651_WIN_MIN) -> Optional[float]:
    """OLS slope of y on x over the ``win`` sessions ending at i (ETP control's SPY hedge ratio)."""
    lo = i - win + 1
    if lo < 1:
        return None
    y, x = y_ret[lo:i + 1], x_ret[lo:i + 1]
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < min_obs:
        return None
    xc = x[ok] - x[ok].mean()
    v = float(xc @ xc)
    return float(xc @ (y[ok] - y[ok].mean()) / v) if v > 0 else None


def _ret_series(cal: Sequence[str], px: dict) -> np.ndarray:
    r = np.full(len(cal), np.nan)
    for s in range(1, len(cal)):
        a, b = px.get(cal[s - 1]), px.get(cal[s])
        if a and b:
            r[s] = b / a - 1.0
    return r


def t651_records(cal, ecal, curve, vix, spy: dict, start: str = T651_START, end: str = T651_END, hold: int = T651_HOLD,
                 thr: float = T651_THR, es: Optional[dict] = None, etps: Optional[dict] = None) -> tuple:
    """One record per decision session t in start..end whose t+1+hold session exists: the signal (from session t), the
    contract, the entry/exit settles, the SPY hedge ratio fixed at entry (and the ES=F / ETP sensitivities). Returns
    (records, counts)."""
    n = len(cal)
    front = front_contracts(ecal, n, curve_expiries(curve), T651_MIN_DAYS)
    ch = daily_changes(cal, ecal, curve, front, spy)
    ch_es = daily_changes(cal, ecal, curve, front, es) if es else None
    r_spy = ch["r"]
    r_etp = {k: _ret_series(cal, v) for k, v in (etps or {}).items()}
    i0 = bisect_left(cal, start)
    recs, cnt = [], Counter()
    for i in range(i0, n - hold - 1):
        if cal[i] > end or cal[i + 1 + hold] > end:
            break
        sig = roll_at(curve, vix, cal, ecal, front, i)
        if sig is None:
            cnt["no F1 settle or VIX close at t"] += 1
            continue
        roll, f_t, tau_t = sig
        side = -1 if roll > thr else (1 if roll < -thr else 0)
        c = front[i]
        e, x = i + 1, i + 1 + hold
        fe, fx = curve.get(cal[e], {}).get(c), curve.get(cal[x], {}).get(c)
        ae, ax = spy.get(cal[e]), spy.get(cal[x])
        b = hedge_fit(ch, i)
        if fe is None or fx is None:
            cnt["no settle at entry or exit"] += 1
            continue
        if not (ae and ax):
            cnt["no SPY close at entry or exit"] += 1
            continue
        if b is None:
            cnt["hedge window not 252 valid changes (before 2014-05)"] += 1
            continue
        tau_e = sessions_to(ecal, e, c)
        rec = {"i": i, "day": cal[i], "entry": cal[e], "exit": cal[x], "offset": (i - i0) % hold, "roll": roll,
               "side": side, "contract": c, "tau_t": tau_t, "tau_e": tau_e, "fe": fe, "fx": fx, "r_spy": ax / ae - 1.0,
               "beta": float(b[1] + b[2] * tau_e), "coef": [float(v) for v in b]}
        if ch_es is not None:
            be = hedge_fit(ch_es, i)
            ee, ex_ = es.get(cal[e]), es.get(cal[x])
            rec["beta_es"] = None if be is None or not (ee and ex_) else float(be[1] + be[2] * tau_e)
            rec["r_es"] = None if not (ee and ex_) else ex_ / ee - 1.0
        for k, px in (etps or {}).items():
            pe, pxx = px.get(cal[e]), px.get(cal[x])
            bb = beta_fit(r_etp[k], r_spy, i)
            rec["etp_" + k] = None if bb is None or not (pe and pxx) else (pxx / pe - 1.0) - bb * rec["r_spy"] - T651_ETP_COST
        recs.append(rec)
    return recs, cnt


def t651_pnl(recs: Sequence[dict], side=None, cost: float = T651_COST, hedge: str = "spy", bills=None) -> np.ndarray:
    """Net $ P&L per trade of one VX contract: side x $1,000 x (F_exit - F_entry), plus the hedge (-side x $1,000 x beta
    dollars of SPY, or ES=F with its own beta, or none), minus ``cost``. ``side`` overrides each record's side (always-
    short = -1); ``bills`` (CAL.Bills) turns the SPY hedge into its excess return over DTB3 (the financed reading)."""
    out = []
    for r in recs:
        s = r["side"] if side is None else side
        vx = s * T651_MULT * (r["fx"] - r["fe"])
        if hedge == "none":
            h = 0.0
        elif hedge == "es":
            if r.get("beta_es") is None or r.get("r_es") is None:
                out.append(np.nan)
                continue
            h = -s * T651_MULT * r["beta_es"] * r["r_es"]
        else:
            rr = r["r_spy"] - (bills.growth(r["entry"], r["exit"]) if bills is not None else 0.0)
            h = -s * T651_MULT * r["beta"] * rr
        out.append(vx + h - cost)
    return np.array(out, float)


def t651_test(recs: Sequence[dict], cnt: Counter, bills=None, n_boot: Optional[int] = None) -> dict:
    """T-651 core over the records of every decision session."""
    sig = [r for r in recs if r["side"] != 0]
    x = t651_pnl(sig)
    days = [r["day"] for r in sig]
    off = np.array([r["offset"] for r in sig], int)
    n_off = [int((off == o).sum()) for o in range(T651_HOLD)]
    n = min(n_off) if sig else 0
    row1, info = mean_rows(x, T651_BLOCK, T651_NW_LAG,
                           f"pooled mean net P&L {_usd(info_mean(x))} per trade > 0 with one-sided p < 0.05 by Newey-West "
                           f"and the bootstrap (both required)", n_boot)
    h1 = np.array([d <= T651_SPLIT for d in days], bool)
    halves = [float(x[h1].mean()) if h1.any() else None, float(x[~h1].mean()) if (~h1).any() else None]
    row2 = (f"both half means > 0 (2013-2019 {_usd(halves[0])}, 2020-2026 {_usd(halves[1])})",
            None if None in halves else bool(halves[0] > 0 and halves[1] > 0), False)
    dsr_rows, dsr_info = [], []
    for o in range(T651_HOLD):
        xo = x[off == o]
        rr, ii = dsr_vs_uncomputed_family(xo, T651_FAMILY, f"offset {o}")
        dsr_rows.append(rr)
        dsr_info.append(ii)
    row3 = BW.all_constructions(dsr_rows, f"DSR >= {DSR_PASS} over the {T651_FAMILY}-trial VX family on each offset's "
                                          f"non-overlapping trades")
    v, why, crit = CAL._judge([row1, row2, row3], n, T651_MIN_N, "signal trades on the thinnest offset")
    # legs, controls, sensitivities (reported)
    side = np.array([r["side"] for r in sig], int)
    legs = {}
    for nm, sd in (("short", -1), ("long", 1)):
        m = side == sd
        xs = x[m]
        nw = nw_mean(xs, T651_NW_LAG)
        legs[nm] = {"n": int(m.sum()), "n_per_offset": [int(((off == o) & m).sum()) for o in range(T651_HOLD)],
                    "mean": nw["mean"], "nw_t": nw["t"], "sharpe_per_trade": _sr(xs), "cvar_1pct": cvar(xs),
                    "mdd_per_offset": [mdd(x[(off == o) & m]) for o in range(T651_HOLD)],
                    "halves": [float(xs[h1[m]].mean()) if (h1[m]).any() else None,
                               float(xs[~h1[m]].mean()) if (~h1[m]).any() else None]}
    unh = t651_pnl(sig, hedge="none")
    always = t651_pnl(recs, side=-1)
    aoff = np.array([r["offset"] for r in recs], int)
    excl = np.array([not (r["entry"][:7] in T651_EXCL or r["exit"][:7] in T651_EXCL) for r in sig], bool)
    cheap = t651_pnl(sig, cost=T651_COST_SENS)
    fin = t651_pnl(sig, bills=bills) if bills is not None else None
    es = t651_pnl(sig, hedge="es") if sig and "beta_es" in sig[0] else None
    etp = {}
    for nm, key, sd in (("short signal: long SVXY", "etp_SVXY", -1), ("long signal: long VXX", "etp_VXX", 1)):
        vals = np.array([r.get(key) for r in sig if r["side"] == sd and r.get(key) is not None], float)
        etp[nm] = {"n": int(vals.size), "mean": float(vals.mean()) if vals.size else None,
                   "nw_t": nw_mean(vals, T651_NW_LAG)["t"] if vals.size > 3 else None}
    etp_all = np.array([(r.get("etp_SVXY") if r["side"] == -1 else r.get("etp_VXX")) for r in sig], dtype=object)
    etp_ok = np.array([v_ is not None for v_ in etp_all], bool)
    etp_x = np.array([float(v_) for v_ in etp_all[etp_ok]], float)
    rep = {"unhedged": nw_mean(unh, T651_NW_LAG), "always_short": nw_mean(always, T651_NW_LAG),
           "always_short_offset_means": [float(always[aoff == o].mean()) for o in range(T651_HOLD) if (aoff == o).any()],
           "ex_2018_02_2020_03": nw_mean(x[excl], T651_NW_LAG), "cost_60": nw_mean(cheap, T651_NW_LAG),
           "financed_hedge": None if fin is None else nw_mean(fin, T651_NW_LAG),
           "es_hedge": None if es is None else nw_mean(es[np.isfinite(es)], T651_NW_LAG),
           "etp": etp, "etp_pooled": nw_mean(etp_x, T651_NW_LAG) if etp_x.size > 3 else None,
           "offset_means": [float(x[off == o].mean()) if (off == o).any() else None for o in range(T651_HOLD)]}
    betas = np.array([r["beta"] for r in sig], float)
    stat = {"n_signal_trades_pooled": len(sig), "n_per_offset": n_off, "n_decision_days": len(recs),
            "skipped": dict(cnt), "mean": info["mean"], "nw_t": info["nw_t"], "nw_p": info["nw_p"], "boot_p": info["boot_p"],
            "boot_draws": info["draws"], "halves": halves, "sharpe_per_trade": _sr(x), "cvar_1pct": cvar(x), "legs": legs,
            "dsr": dsr_info, "reported": rep, "hedge_ratio": {"median": float(np.median(betas)) if betas.size else None,
                                                             "p10": float(np.quantile(betas, 0.1)) if betas.size else None,
                                                             "p90": float(np.quantile(betas, 0.9)) if betas.size else None},
            "first_last_trade": [days[0], days[-1]] if days else None, "criteria": crit}
    L = legs
    reason = (f"{len(sig)} pooled signal trades {days[0] if days else 'n/a'}..{days[-1] if days else 'n/a'} (per offset "
              f"{', '.join(map(str, n_off))}; short {L['short']['n']}, long {L['long']['n']}), SPY-hedged (median ratio "
              f"{_s(stat['hedge_ratio']['median'], 1)} VX pts per unit SPY return) at $140 a round trip: mean "
              f"{_usd(info['mean'])} per trade (NW t {_s(info['nw_t'], 2)}, bootstrap p {_f(info['boot_p'], 4)}); halves "
              f"{_usd(halves[0])} / {_usd(halves[1])}; short leg {_usd(L['short']['mean'])} (t {_s(L['short']['nw_t'], 2)}, "
              f"Sharpe/trade {_s(L['short']['sharpe_per_trade'], 3)}, 1% CVaR {_usd(L['short']['cvar_1pct'], 0)}, worst "
              f"offset MDD ${max(L['short']['mdd_per_offset']):,.0f}), long leg {_usd(L['long']['mean'])} (t "
              f"{_s(L['long']['nw_t'], 2)}, 1% CVaR {_usd(L['long']['cvar_1pct'], 0)}); DSR upper bounds by offset "
              f"{', '.join(_f(d.get('dsr_upper_bound')) for d in dsr_info)}; reported: unhedged "
              f"{_usd(rep['unhedged']['mean'])} (t {_s(rep['unhedged']['t'], 2)}), always-short hedged "
              f"{_usd(rep['always_short']['mean'])} (t {_s(rep['always_short']['t'], 2)}, n {len(recs)}), ex 2018-02/2020-03 "
              f"{_usd(rep['ex_2018_02_2020_03']['mean'])} (t {_s(rep['ex_2018_02_2020_03']['t'], 2)}), $60 costs "
              f"{_usd(rep['cost_60']['mean'])}, DTB3-financed hedge "
              f"{_usd(None if fin is None else rep['financed_hedge']['mean'])}, ES=F hedge "
              f"{_usd(None if es is None else rep['es_hedge']['mean'])}, ETP form "
              f"{_pc(None if rep['etp_pooled'] is None else rep['etp_pooled']['mean'], 3)} per trade (SVXY "
              f"n {etp['short signal: long SVXY']['n']}, VXX n {etp['long signal: long VXX']['n']}); offset means "
              f"{', '.join(_usd(m, 0) for m in rep['offset_means'])}. Calendar: VIX days that are NYSE sessions; the hedge "
              f"regression ends at t, so trades start once 252 sessions of settles exist; pooled over the 5 offsets (rule "
              f"10), n = the thinnest offset — {why}")
    return {"stat": stat, "n": n, "verdict": v, "reason": reason}


def info_mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(x.mean()) if x.size else None


def b13_implied_a_vx_roll_carry(archive):
    """T-651: SPY-hedged 5-day F1 VX trade on the daily roll (short above +0.10, long below -0.10), $140 a round trip."""
    miss = B7C._missing(archive, [VX_B, VIX_B, SPY_B])
    if miss:
        return miss

    def run():
        vix = CAL._series(archive, VIX_B)
        curve = vx_curve(CAL._rows(archive, VX_B))
        cal = trading_calendar(vix)
        ecal = extended_calendar(cal, max(curve_expiries(curve)))
        spy = _px(archive, SPY_B, "adjclose")
        es = _px(archive, ESF_B, "close") if B7C._has(archive, ESF_B) else None
        etps = {k: _px(archive, b, "adjclose") for k, b in (("SVXY", SVXY_B), ("VXX", VXX_B)) if B7C._has(archive, b)}
        bills = CAL.Bills(CAL._series(archive, DTB3_B)) if B7C._has(archive, DTB3_B) else None
        recs, cnt = t651_records(cal, ecal, curve, vix, spy, es=es, etps=etps)
        return t651_test(recs, cnt, bills)

    rep = CAL._cached(archive, ("b13_implied_a", "T-651"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


# ===================================================================================== T-652 VIX premium ==

def logvix_frame(vix: dict, vix3m: dict, start: str = T652_FIT_FROM) -> tuple:
    """(days, Z): the VIX/VIX3M common days from ``start`` with Z = [log VIX, log(VIX / VIX3M)]."""
    days = sorted(d for d in set(vix) & set(vix3m) if d >= start and vix[d] > 0 and vix3m[d] > 0)
    Z = np.array([[math.log(vix[d]), math.log(vix[d] / vix3m[d])] for d in days], float)
    return days, Z


def var1_forecast(Z: np.ndarray, j: int, h: int) -> Optional[tuple]:
    """VAR(1) z_s = c + A z_{s-1} + u_s fitted by OLS on the pairs (s-1, s) with s <= j, iterated ``h`` steps from z_j:
    (mean of log VIX at j + h, its forecast variance). Uses rows 0..j only."""
    if j < 30 or h < 1:
        return None
    Y, X = Z[1:j + 1], np.column_stack([np.ones(j), Z[:j]])
    B, *_ = np.linalg.lstsq(X, Y, rcond=None)
    U = Y - X @ B
    S = U.T @ U / max(1, j - 3)
    c, A = B[0], B[1:].T
    m, V = Z[j].copy(), np.zeros((2, 2))
    for _ in range(h):
        m = c + A @ m
        V = A @ V @ A.T + S
    return float(m[0]), float(V[0, 0])


def ar1_forecast(x: np.ndarray, j: int, h: int) -> Optional[tuple]:
    """AR(1) on log VIX alone (reported), rows 0..j only."""
    if j < 30 or h < 1:
        return None
    X = np.column_stack([np.ones(j), x[:j]])
    b, *_ = np.linalg.lstsq(X, x[1:j + 1], rcond=None)
    s2 = float(np.sum((x[1:j + 1] - X @ b) ** 2)) / max(1, j - 2)
    m, v = float(x[j]), 0.0
    for _ in range(h):
        m = b[0] + b[1] * m
        v = b[1] ** 2 * v + s2
    return m, v


def har_forecast(x: np.ndarray, j: int, h: int) -> Optional[tuple]:
    """HAR(1,5,22) on log VIX (the registered control), OLS on rows 0..j, iterated as its AR(22) form; variance from the
    MA weights."""
    if j < 60 or h < 1:
        return None
    s = np.arange(22, j + 1)
    cs = np.concatenate([[0.0], np.cumsum(x[:j + 1])])
    m5 = (cs[s] - cs[s - 5]) / 5.0
    m22 = (cs[s] - cs[s - 22]) / 22.0
    X = np.column_stack([np.ones(s.size), x[s - 1], m5, m22])
    b, *_ = np.linalg.lstsq(X, x[s], rcond=None)
    s2 = float(np.sum((x[s] - X @ b) ** 2)) / max(1, s.size - 4)
    phi = np.zeros(22)
    phi[0] += b[1]
    phi[:5] += b[2] / 5.0
    phi[:22] += b[3] / 22.0
    hist = list(x[j - 21:j + 1])
    for _ in range(h):
        nxt = b[0] + float(np.dot(phi, hist[::-1][:22]))
        hist.append(nxt)
    psi = [1.0]
    for k in range(1, h):
        psi.append(sum(phi[l - 1] * psi[k - l] for l in range(1, min(k, 22) + 1)))
    return float(hist[-1]), s2 * float(np.sum(np.square(psi)))


def premium_cycles(cal: Sequence[str], ecal: Sequence[str], curve: dict, start: str = T652_START, tau: int = T652_TAU) -> tuple:
    """[(t index, expiry, previous expiry, final settlement)]: per expiry with a final settlement row, the first session
    after the previous expiry with <= tau trading days to it. Cycles whose session precedes the VX data are dropped."""
    ex = curve_expiries(curve)
    out, cnt = [], Counter()
    for k in range(1, len(ex)):
        ep, e = ex[k - 1], ex[k]
        fs = curve.get(e, {}).get(e)
        if fs is None:
            cnt["no final settlement row"] += 1
            continue
        t = max(bisect_right(cal, ep), bisect_right(ecal, e) - 1 - tau)
        if t >= len(cal) or cal[t] >= e:
            cnt["no session in the cycle"] += 1
            continue
        if cal[t] < start:
            cnt["before the VX settle data"] += 1
            continue
        out.append((t, e, ep, float(fs)))
    return out, cnt


def trailing_z(days: Sequence[str], vals: np.ndarray, day: str, win: int) -> Optional[float]:
    """z of the last value at or before ``day`` against the ``win`` values ending there (that value included)."""
    k = bisect_right(days, day) - 1
    if k < win - 1:
        return None
    w = vals[k - win + 1:k + 1]
    sd = float(w.std(ddof=1))
    return float((vals[k] - w.mean()) / sd) if sd > 0 else None


def rv_series(days: Sequence[str], adj, win: int, ppy: int = 252) -> np.ndarray:
    """Annualised realised vol (vol points) of the ``win`` log returns ending at each close (known at that close)."""
    a = np.asarray(adj, float)
    lr = np.full(a.size, np.nan)
    lr[1:] = np.log(a[1:] / a[:-1])
    out = np.full(a.size, np.nan)
    sq = np.where(np.isfinite(lr), lr * lr, np.nan)
    for k in range(win, a.size):
        w = sq[k - win + 1:k + 1]
        if np.isfinite(w).all():
            out[k] = math.sqrt(ppy / win * float(w.sum())) * 100.0
    return out


def boot_slope(y, x, n_boot: int = 2000, seed: int = SEED) -> dict:
    """Studentized pairs bootstrap of the OLS slope of y on [1, x] (cycles resampled i.i.d., HC1 studentizer): p (H0
    slope <= 0), p_lt (H0 slope >= 0) and the two-sided 95% studentized CI."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size

    def fit(Y, Xv):
        xm = Xv.mean(axis=1, keepdims=True)
        xc = Xv - xm
        sxx = (xc * xc).sum(axis=1)
        b = (xc * (Y - Y.mean(axis=1, keepdims=True))).sum(axis=1) / np.where(sxx > 0, sxx, np.nan)
        a = Y.mean(axis=1) - b * xm[:, 0]
        e = Y - a[:, None] - b[:, None] * Xv
        se = np.sqrt(n / max(1, n - 2) * (xc * xc * e * e).sum(axis=1)) / np.where(sxx > 0, sxx, np.nan)
        return b, se

    b0, s0 = fit(y[None, :], x[None, :])
    b0, s0 = float(b0[0]), float(s0[0])
    out = {"b": b0, "se": s0, "p": None, "p_lt": None, "ci": [None, None]}
    if n < 8 or not s0 > 0:
        return out
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    bb, sb = fit(y[idx], x[idx])
    ok = np.isfinite(bb) & np.isfinite(sb) & (sb > 0)
    t = (bb[ok] - b0) / sb[ok]
    t0 = b0 / s0
    out.update(p=float((np.sum(t >= t0) + 1) / (t.size + 1)), p_lt=float((np.sum(t <= t0) + 1) / (t.size + 1)),
               ci=[b0 - float(np.quantile(t, 0.975)) * s0, b0 - float(np.quantile(t, 0.025)) * s0])
    return out


def slope_a_row(y, x, label: str, n_boot: Optional[int] = None) -> tuple:
    """(a) 'slope > 0 with one-sided p < 0.05 and 1 inside the 95% CI' under Newey-West lag 1 and the cycle bootstrap,
    both registered, so the row fails when either fails (``and_rows``). Returns (row, info)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    nw = CAL.ols_nw(y, x, T652_NW_LAG)
    b, se = nw["slope"], nw["se"]
    if not (math.isfinite(se) and se > 0):
        return (f"{label} (n/a)", None, False), {"nw": nw}
    p_nw = 1.0 - _N.cdf(b / se)
    lo, hi = b - 1.959964 * se, b + 1.959964 * se
    ok_nw = bool(b > 0 and p_nw < ALPHA and lo < 1.0 < hi)
    dec_nw = bool(_N.cdf(b / se) < ALPHA or not (lo < 1.0 < hi))
    nw_row = (f"Newey-West lag 1: slope {b:+.3f}, t {b / se:+.2f}, p {p_nw:.4f}, 95% CI [{lo:+.3f}, {hi:+.3f}]", ok_nw, dec_nw)
    nb = 2000 if n_boot is None else int(n_boot)

    def judge(bt):
        draws = nb * bt.get("reps", 1)
        pdec = CAL.decide_p(bt["p"], draws) if bt.get("p") is not None else None
        lo_b, hi_b = bt.get("ci") or (None, None)
        se_lo, se_hi = bt.get("ci_mc_se") or (0.0, 0.0)
        in_lo = BW.resolve(lo_b, se_lo, 1.0, "lt")[0]
        in_hi = BW.resolve(hi_b, se_hi, 1.0, "gt")[0]
        if not b > 0 or pdec is False or in_lo is False or in_hi is False:
            ok = False
        elif pdec is True and in_lo is True and in_hi is True:
            ok = True
        else:
            ok = None
        dec = bool((bt.get("p_lt") is not None and CAL.decide_p(bt["p_lt"], draws) is True) or in_lo is False or in_hi is False)
        return ok, dec, draws

    bt = BW.mc_escalate(lambda seed: boot_slope(y, x, nb, seed), lambda t: judge(t)[0], BW.REPS, SEED)
    ok_b, dec_b, draws = judge(bt)
    lo_b, hi_b = bt.get("ci") or (None, None)
    bt_row = (f"cycle bootstrap: p {CAL._mc(bt['p'], draws)}, 95% CI [{_s(lo_b)}, {_s(hi_b)}]", ok_b, dec_b)
    row = and_rows([nw_row, bt_row], label)
    return row, {"slope": b, "se_nw": se, "p_nw": p_nw, "ci_nw": [lo, hi], "p_boot": bt["p"], "ci_boot": bt["ci"],
                 "n": int(y.size)}


def premium_test(cyc: Sequence[dict], n_boot: Optional[int] = None) -> dict:
    """T-652 core on the per-cycle observations."""
    rows, info = [], {"a": {}, "b": {}}
    for h, (lo, hi) in enumerate(T652_HALVES):
        m = [c for c in cyc if lo <= c["day"] <= hi]
        y = np.array([c["y"] for c in m], float)
        P = np.array([c["P"] for c in m], float)
        lab = f"(a) {lo[:7]}..{hi[:7]}: slope of F1_t - FinalSettle on P_t > 0, one-sided p < 0.05, 1 inside the 95% CI"
        if y.size < 8:
            rows.append((lab + f" (n/a: {y.size} cycles)", None, False))
            continue
        r, ii = slope_a_row(y, P, lab, n_boot)
        rows.append(r)
        info["a"][f"h{h + 1}"] = ii
    for h, (lo, hi) in enumerate(T652_HALVES):
        m = [c for c in cyc if lo <= c["day"] <= hi]
        P = np.array([c["P"] for c in m], float)
        for var, lab in (("vvix", "VVIX"), ("rv", "trailing 21-session SPY RV")):
            sub = []
            for kind, key in (("within-half z", var), ("trailing 252-session z", var + "_z")):
                xv = np.array([c[key] if c[key] is not None else np.nan for c in m], float)
                ok = np.isfinite(xv)
                if ok.sum() < 8:
                    sub.append((f"{kind} (n/a)", None, False))
                    continue
                xs = xv[ok]
                z = (xs - xs.mean()) / xs.std(ddof=1) if kind.startswith("within") else xs
                fit = CAL.ols_nw(P[ok], z, T652_NW_LAG)
                info["b"][f"h{h + 1}_{var}_{'within' if kind.startswith('within') else 'trailing'}"] = fit
                sub.append((f"{kind} slope {fit['slope']:+.3f} (NW t {fit['t']:+.2f})", bool(fit["slope"] <= 0), False))
            rows.append(BW.all_constructions(sub, f"(b) {lo[:7]}..{hi[:7]}: slope of P_t on standardised {lab} <= 0"))
    v, why, crit = CAL._judge(rows, len(cyc), T652_MIN_N, "cycles")
    return {"rows": rows, "info": info, "verdict": v, "why": why, "crit": crit}


def build_premium_cycles(cal, ecal, curve, vix, vix3m, vvix, spy_days, spy_adj, model: str = "var",
                         h_shift: int = 0) -> tuple:
    """Per-cycle observations: day, y = F1_t - FinalSettle, P = F1_t - E_t[VIX_T] (``model``: var / ar1 / har / raw =
    the raw basis F1 - VIX), the t+1 settle return, VVIX and RV21 levels and their trailing 252-session z. The model is
    iterated h + ``h_shift`` steps (0 = the registered h; -1 = the expiry-morning SOQ sensitivity, reported only)."""
    cyc, cnt = premium_cycles(cal, ecal, curve)
    zd, Z = logvix_frame(vix, vix3m)
    zpos = {d: i for i, d in enumerate(zd)}
    vvd = sorted(d for d in vvix if CAL.is_nyse_session(d))
    vvv = np.array([vvix[d] for d in vvd], float)
    rv = rv_series(spy_days, spy_adj, T652_RV_WIN)
    rv_ok = np.isfinite(rv)
    rvd = [d for d, o in zip(spy_days, rv_ok) if o]
    rvv = rv[rv_ok]
    rvpos = {d: i for i, d in enumerate(spy_days)}
    out = []
    for t, e, ep, fs in cyc:
        d = cal[t]
        f1 = curve.get(d, {}).get(e)
        h = sessions_to(ecal, t, e)
        if f1 is None or d not in vix:
            cnt["no F1 settle or VIX at t"] += 1
            continue
        if model == "raw":
            ev = vix[d]
        else:
            j = zpos.get(d)
            if j is None:
                cnt["no VIX3M at t"] += 1
                continue
            hf = h + int(h_shift)
            if hf < 1:
                cnt["forecast horizon below one step"] += 1
                continue
            fc = (var1_forecast(Z, j, hf) if model == "var" else ar1_forecast(Z[:, 0], j, hf) if model == "ar1"
                  else har_forecast(Z[:, 0], j, hf))
            if fc is None:
                cnt["too little model history"] += 1
                continue
            ev = math.exp(fc[0] + 0.5 * fc[1])
        k = rvpos.get(d)
        if d not in vvix or k is None or not math.isfinite(rv[k]):
            cnt["no VVIX or SPY RV21 at t"] += 1
            continue
        f1n = curve.get(cal[t + 1], {}).get(e) if t + 1 < len(cal) and cal[t + 1] <= e else None
        out.append({"day": d, "expiry": e, "h": h, "f1": f1, "fs": fs, "vix": vix[d], "ev": ev, "P": f1 - ev, "y": f1 - fs,
                    "y_next": None if f1n is None else f1n - fs, "f1_next": f1n, "vvix": vvix[d],
                    "vvix_z": trailing_z(vvd, vvv, d, T652_Z_WIN), "rv": float(rv[k]),
                    "rv_z": trailing_z(rvd, rvv, d, T652_Z_WIN)})
    return out, cnt


def premium_secondary(cyc: Sequence[dict], cost: float = T652_COST) -> dict:
    """Short F1 at the t+1 settle held to final settlement, $1,000 x (F1_{t+1} - FinalSettle) - cost per cycle, gated
    on P_t above the median of >= 12 earlier cycles' P, against always short (reported)."""
    g, a = [], []
    for k, c in enumerate(cyc):
        if c["f1_next"] is None or k < T652_MIN_PRIOR:
            continue
        pnl = 1000.0 * (c["f1_next"] - c["fs"]) - cost
        med = float(np.median([q["P"] for q in cyc[:k]]))
        a.append(pnl)
        g.append(pnl if c["P"] > med else 0.0)
    g, a = np.array(g, float), np.array(a, float)
    if g.size < 8:
        return {"n": int(g.size)}
    sd = BW.sharpe_diff_test(g, a, 12, 3, 2000, SEED)
    return {"n": int(g.size), "share_on": float(np.mean(g != 0)), "sharpe_gated": sd["sharpe_a"], "sharpe_always": sd["sharpe_b"],
            "diff": sd["diff"], "ci": sd["ci"], "mean_gated": float(g.mean()), "mean_always": float(a.mean())}


def b13_implied_a_vix_premium_risk(archive):
    """T-652: the model-based VX premium P_t predicts F1_t - FinalSettle with slope in (0, 1-inclusive CI) and falls with
    VVIX and SPY RV21, in both halves."""
    miss = B7C._missing(archive, [VX_B, VIX_B, VIX3M_B, VVIX_B, SPY_B])
    if miss:
        return miss

    def run():
        vix = CAL._series(archive, VIX_B)
        vix3m = CAL._series(archive, VIX3M_B)
        vvix = CAL._series(archive, VVIX_B)
        curve = vx_curve(CAL._rows(archive, VX_B))
        cal = trading_calendar(vix)
        ecal = extended_calendar(cal, max(curve_expiries(curve)))
        sd, sa = CAL._daily(archive, SPY_B, "adjclose")
        args = (cal, ecal, curve, vix, vix3m, vvix, sd, sa)
        cyc, cnt = build_premium_cycles(*args, model="var")
        main = premium_test(cyc)
        ctrl = {}
        for m in ("raw", "har", "ar1"):
            cc, _ = build_premium_cycles(*args, model=m)
            ctrl[m] = premium_test(cc, n_boot=500)
        cc, _ = build_premium_cycles(*args, model="var", h_shift=-1)
        ctrl["var_h_minus_1"] = premium_test(cc, n_boot=500)
        ex20 = [c for c in cyc if c["day"][:7] not in T652_EX2020]
        ctrl["ex_2020_02_04"] = premium_test(ex20, n_boot=500)
        nxt = [dict(c, y=c["y_next"]) for c in cyc if c["y_next"] is not None]
        ctrl["t1_settle_entry"] = premium_test(nxt, n_boot=500)
        sec = premium_secondary(cyc)
        cont = [c for c in cyc if c["f1"] > c["vix"]]
        back = [c for c in cyc if c["f1"] <= c["vix"]]
        spike = [c for c in back if c["vix"] > 30]
        cons = {"contango_n": len(cont), "contango_share_final_below_f1": float(np.mean([c["fs"] < c["f1"] for c in cont])) if cont else None,
                "backwardation_n": len(back), "backwardation_share_final_below_f1": float(np.mean([c["fs"] < c["f1"] for c in back])) if back else None,
                "vix_gt30_backwardation_n": len(spike),
                "vix_gt30_backwardation_share_final_below_f1": float(np.mean([c["fs"] < c["f1"] for c in spike])) if spike else None}
        return {"cyc": cyc, "cnt": cnt, "main": main, "ctrl": ctrl, "sec": sec, "cons": cons}

    R = CAL._cached(archive, ("b13_implied_a", "T-652"), run)
    return _premium_out(R)


def _ctrl_txt(t: dict) -> str:
    a = t["info"]["a"]
    return (f"(a) slopes {_s(a.get('h1', {}).get('slope'), 2)} / {_s(a.get('h2', {}).get('slope'), 2)}, verdict "
            f"{t['verdict']}")


def _premium_out(R: dict):
    cyc, main, ctrl, sec, cons = R["cyc"], R["main"], R["ctrl"], R["sec"], R["cons"]
    a, b = main["info"]["a"], main["info"]["b"]
    P = np.array([c["P"] for c in cyc], float)
    y = np.array([c["y"] for c in cyc], float)
    bw = lambda k: b.get(k, {}).get("slope")
    stat = {"n_cycles": len(cyc), "skipped": dict(R["cnt"]), "first_last": [cyc[0]["day"], cyc[-1]["day"]] if cyc else None,
            "mean_P": float(P.mean()) if P.size else None, "mean_y": float(y.mean()) if y.size else None,
            "mean_raw_basis": float(np.mean([c["f1"] - c["vix"] for c in cyc])) if cyc else None,
            "a": a, "b": b, "controls": {k: {"verdict": v["verdict"], "a": v["info"]["a"],
                                             "b": {kk: vv.get("slope") for kk, vv in v["info"]["b"].items()}}
                                         for k, v in ctrl.items()},
            "secondary": sec, "t534_t535_consistency": cons, "criteria": main["crit"]}
    h1 = (T652_HALVES[0][0][:7], T652_HALVES[0][1][:7])
    reason = (f"{len(cyc)} VX cycles {cyc[0]['day'] if cyc else 'n/a'}..{cyc[-1]['day'] if cyc else 'n/a'} (t = the first "
              f"session after the previous expiry with <= 21 trading days to F1's), VAR(1) on log VIX and log(VIX/VIX3M) from "
              f"2009-09-18 to t: mean P_t {_s(stat['mean_P'], 2)} vol pts, mean F1_t - FinalSettle {_s(stat['mean_y'], 2)}; "
              f"(a) slope {h1[0]}..2019 {_s(a.get('h1', {}).get('slope'), 3)} (NW p {_f(a.get('h1', {}).get('p_nw'), 4)}, "
              f"CI [{_s((a.get('h1', {}).get('ci_nw') or [None])[0], 2)}, {_s((a.get('h1', {}).get('ci_nw') or [None, None])[1], 2)}]; "
              f"boot p {_f(a.get('h1', {}).get('p_boot'), 4)}), 2020..2026 {_s(a.get('h2', {}).get('slope'), 3)} (NW p "
              f"{_f(a.get('h2', {}).get('p_nw'), 4)}, CI [{_s((a.get('h2', {}).get('ci_nw') or [None])[0], 2)}, "
              f"{_s((a.get('h2', {}).get('ci_nw') or [None, None])[1], 2)}]; boot p {_f(a.get('h2', {}).get('p_boot'), 4)}); "
              f"(b) slopes on VVIX within-half z {_s(bw('h1_vvix_within'), 3)} / {_s(bw('h2_vvix_within'), 3)}, trailing z "
              f"{_s(bw('h1_vvix_trailing'), 3)} / {_s(bw('h2_vvix_trailing'), 3)}; on RV21 within-half z "
              f"{_s(bw('h1_rv_within'), 3)} / {_s(bw('h2_rv_within'), 3)}, trailing z {_s(bw('h1_rv_trailing'), 3)} / "
              f"{_s(bw('h2_rv_trailing'), 3)}; controls: raw basis {_ctrl_txt(ctrl['raw'])}; HAR {_ctrl_txt(ctrl['har'])}; "
              f"AR(1) on log VIX alone {_ctrl_txt(ctrl['ar1'])}; VAR iterated h - 1 steps (expiry-morning SOQ) "
              f"{_ctrl_txt(ctrl['var_h_minus_1'])}; ex 2020-02..04 {_ctrl_txt(ctrl['ex_2020_02_04'])}; t+1 "
              f"settle {_ctrl_txt(ctrl['t1_settle_entry'])}; secondary (short at the t+1 settle when P_t > the expanding "
              f"median, $140) annualised Sharpe {_s(sec.get('sharpe_gated'), 2)} vs always {_s(sec.get('sharpe_always'), 2)} "
              f"(diff {_s(sec.get('diff'), 2)}, reported); T-534/T-535: final below F1 in {_pc(cons['contango_share_final_below_f1'], 0)} "
              f"of {cons['contango_n']} contango cycles, {_pc(cons['backwardation_share_final_below_f1'], 0)} of "
              f"{cons['backwardation_n']} backwardated ({cons['vix_gt30_backwardation_n']} with VIX > 30). One observation per "
              f"cycle (no grid phase, rule 10); (b) judged under both standardisations (rule 11) — {main['why']}")
    return _out(stat, len(cyc), main["verdict"], reason)


# =========================================================================================== T-654 SPY puts ==

def iso_weeks(qdays: Sequence[str]) -> dict:
    wk = defaultdict(list)
    for d in qdays:
        y, w, _ = date.fromisoformat(d).isocalendar()
        wk[(y, w)].append(d)
    return {k: sorted(v) for k, v in wk.items()}


def index_frame(series: dict) -> tuple:
    """(days, values) of an index restricted to NYSE sessions."""
    ds = sorted(d for d in series if CAL.is_nyse_session(d))
    return ds, np.array([series[d] for d in ds], float)


def prior_session(day: str) -> str:
    """The NYSE session before ``day`` (the decision information set for an entry at ``day``'s close)."""
    return CAL.prev_session(date.fromisoformat(day)).isoformat()


def week_signals(entry: str, idx: dict, spy_days: Sequence[str], rv: np.ndarray, win: int = T654_Z_WIN) -> dict:
    """z(VVIX), z(VIX), z(SKEW), the VVIX-on-VIX residual z and RV21, all at the session before the entry quote day."""
    s = prior_session(entry)
    out = {k: trailing_z(d, v, s, win) for k, (d, v) in idx.items()}
    k = bisect_right(spy_days, s) - 1
    out["rv21"] = float(rv[k]) if k >= 0 and math.isfinite(rv[k]) else None
    dv, vv = idx["VVIX"]
    dx, vx = idx["VIX"]
    kv, kx = bisect_right(dv, s) - 1, bisect_right(dx, s) - 1
    out["vvix_resid"] = None
    if kv >= win - 1 and kx >= win - 1:
        common = sorted(set(dv[kv - win + 1:kv + 1]) & set(dx[kx - win + 1:kx + 1]))
        if len(common) >= win // 2 and common[-1] == dv[kv]:
            pv = {d: i for i, d in enumerate(dv)}
            px = {d: i for i, d in enumerate(dx)}
            yy = np.array([vv[pv[d]] for d in common]); xx = np.array([vx[px[d]] for d in common])
            X = np.column_stack([np.ones(xx.size), xx])
            bb, *_ = np.linalg.lstsq(X, yy, rcond=None)
            e = yy - X @ bb
            sd = float(e.std(ddof=2))
            out["vvix_resid"] = float(e[-1] / sd) if sd > 0 else None
    out["signal_session"] = s
    return out


def exit_candidates(chain: dict, qdays: Sequence[str], target: Optional[str], week_last_session: str, k: int = T654_FALLBACK) -> list:
    """The target exit quote day, then the quote days within the next k NYSE sessions after it (or after the next
    week's last session when that week has no quote day)."""
    base = target or week_last_session
    out = [target] if target else []
    d = date.fromisoformat(base)
    for _ in range(k):
        d = CAL.next_session(d)
        if d.isoformat() in chain:
            out.append(d.isoformat())
    return out


def _quoted(day: dict, expiry: str, strike: float) -> Optional[dict]:
    for l in day["exp"].get(expiry, {}).get("put", []):
        if abs(l["strike"] - strike) < 1e-9 and DOLT.usable(l):
            return l
    return None


def put_weeks(chain: dict, spy_raw: dict, spy_adj: dict, bills, start: str = T654_START, end: str = T654_END) -> tuple:
    """Per ISO week: the registered entry (the week's last quote day), expiry nearest 30 DTE in 14..60, the 0.90-0.95 K/S
    put bin and the 5%/10% OTM spread legs, and their exits (the next week's last quote day, else the first quote day
    within 3 sessions after it that quotes the contracts). ``bills`` (CAL.Bills on fred-DTB3) is required: the hedged
    return is net of the bill rate as registered, never silently gross. Returns (weeks, counts)."""
    if bills is None:
        raise ValueError("T-654's hedged return is net of the bill rate: fred-DTB3 is required")
    qdays = sorted(chain)
    wk = iso_weeks(qdays)
    keys = sorted(wk)
    out, cnt = [], Counter()
    for k in keys:
        ent = wk[k][-1]
        if not (start <= ent <= end):
            continue
        day = chain[ent]
        S = day["spot"]
        ae = spy_adj.get(ent)
        nk = (date.fromisocalendar(k[0], k[1], 1) + timedelta(days=7)).isocalendar()[:2]
        target = wk[nk][-1] if nk in wk else None
        last_sess = date.fromisocalendar(nk[0], nk[1], 5)
        while not CAL.is_nyse_session(last_sess):
            last_sess -= timedelta(days=1)
        cands = exit_candidates(chain, qdays, target, last_sess.isoformat())
        rec = {"entry": ent, "week": f"{k[0]}-W{k[1]:02d}", "bin": None, "spread": None, "bin_exit": None, "spread_exit": None}
        if S is None or ae is None:
            cnt["no SPY close at entry"] += 1
            out.append(rec)
            continue
        allowed = {x for x in day["exp"] if T654_DTE[0] <= DOLT.dte(x, ent) <= T654_DTE[1]}
        e = DOLT.pick_expiry(day, T654_TARGET, T654_DTE[1], allowed) if allowed else None
        if e is None:
            cnt["no expiry at 14-60 DTE"] += 1
            out.append(rec)
            continue
        rec["expiry"] = e
        puts = day["exp"][e]["put"]
        legs = [l for l in puts if T654_BIN[0] <= l["strike"] / S <= T654_BIN[1] and DOLT.usable(l) and l.get("delta") is not None]
        inside = e <= (target or last_sess.isoformat())          # an expiry inside the hold settles at intrinsic
        sx_e = spy_raw.get(e) if inside else None
        if inside and sx_e is None:
            cnt["expiry inside the hold without a SPY close"] += 1
            out.append(rec)
            continue
        # (a) the bin, mid-to-mid, delta-hedged with the vendor delta on SPY adjclose
        if not legs:
            cnt["no usable put in the 0.90-0.95 bin"] += 1
        else:
            ex = e if inside else next((c for c in cands if any(_quoted(chain[c], e, l["strike"]) for l in legs)), None)
            if ex is None:
                cnt["bin: entry contracts not quoted at the exit or within 3 sessions"] += 1
            else:
                ax, sx = spy_adj.get(ex), spy_raw.get(ex)
                if ax is None or sx is None:
                    cnt["no SPY close at exit"] += 1
                else:
                    g = bills.growth(ent, ex)                  # required: the registered return is net of bills
                    hr, ur = [], []
                    for l in legs:
                        if inside:
                            px = max(l["strike"] - sx, 0.0)
                        else:
                            q = _quoted(chain[ex], e, l["strike"])
                            if q is None:
                                continue
                            px = DOLT.mid(q)
                        pe = DOLT.mid(l)
                        hr.append((px - pe - l["delta"] * S * (ax / ae - 1.0)) / pe - g)
                        ur.append((px - pe) / pe)
                    rec.update(bin=float(np.mean(hr)), bin_unhedged=float(np.mean(ur)), bin_exit=ex,
                               bin_strikes=len(hr), bin_offered=len(legs), bin_fallback=ex != target)
        # (b) the 5%/10% OTM short put spread at bid/ask
        k5 = DOLT.pick_moneyness(puts, S, T654_LEGS[0], T654_MONEY_TOL)
        k10 = DOLT.pick_moneyness(puts, S, T654_LEGS[1], T654_MONEY_TOL)
        if k5 is None or k10 is None or not k10["strike"] < k5["strike"]:
            cnt["no 5%/10% OTM legs"] += 1
        else:
            credit = k5["bid"] - k10["ask"]
            width = k5["strike"] - k10["strike"]
            ml = width - credit
            if inside:
                ex = e
            else:
                ex = next((c for c in cands if _quoted(chain[c], e, k5["strike"]) and _quoted(chain[c], e, k10["strike"])), None)
            if credit <= 0 or ml <= 0:
                cnt["spread: no positive credit"] += 1
            elif ex is None:
                cnt["spread: legs not quoted at the exit or within 3 sessions"] += 1
            else:
                if inside:
                    debit = max(k5["strike"] - sx_e, 0.0) - max(k10["strike"] - sx_e, 0.0)
                else:
                    q5, q10 = _quoted(chain[ex], e, k5["strike"]), _quoted(chain[ex], e, k10["strike"])
                    debit = q5["ask"] - q10["bid"]
                pnl = credit - debit
                rec.update(spread=pnl / ml, spread_exit=ex, spread_comm=(pnl - 4 * DOLT.COMM) / ml)
        out.append(rec)
    return out, cnt


def b13_implied_a_vvix_put_hedge(archive):
    """T-654: VVIX-timed delta-hedged SPY OTM put returns and VVIX-gated short 5/10% put spreads on dolt-chain-SPY
    (registered weekly exits unobservable on the DoltHub ladders: computed on the observable weeks, inconclusive)."""
    miss = B7C._missing(archive, [CHAIN_B, VVIX_B, VIX_B, SPY_B, DTB3_B])     # DTB3: the registered bill-rate deduction
    if miss:
        return miss

    def run():
        sd, sc = CAL._daily(archive, SPY_B, "close")
        _, sa = CAL._daily(archive, SPY_B, "adjclose")
        raw, adj = dict(zip(sd, sc)), dict(zip(sd, sa))
        chain, info = DOLT.chain_days(CAL._rows(archive, CHAIN_B), raw)
        bills = CAL.Bills(CAL._series(archive, DTB3_B))
        idx = {"VVIX": index_frame(CAL._series(archive, VVIX_B)), "VIX": index_frame(CAL._series(archive, VIX_B))}
        if B7C._has(archive, SKEW_B):
            idx["SKEW"] = index_frame(CAL._series(archive, SKEW_B))
        rv = rv_series(sd, sa, T654_RV_WIN)
        weeks, cnt = put_weeks(chain, raw, adj, bills)
        for w in weeks:
            w.update(week_signals(w["entry"], idx, sd, rv))
        return t654_report(weeks, cnt, info)

    rep = CAL._cached(archive, ("b13_implied_a", "T-654"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


def _t654_reg(ws: Sequence[dict], key: str) -> dict:
    """OLS of the hedged bin return on [1, ``key``, z(VIX), RV21] with NW (lag 2): the ``key`` slope, t, one-sided p < 0."""
    if len(ws) < 8:
        return {"n": len(ws)}
    X = np.column_stack([np.ones(len(ws)), [w[key] for w in ws], [w["VIX"] for w in ws], [w["rv21"] for w in ws]])
    yv = np.array([w["bin"] for w in ws], float)
    try:
        r = ols_nw_multi(yv, X, T654_NW_LAG)
    except np.linalg.LinAlgError:
        return {"n": len(ws), "singular": True}
    return {"n": len(ws), "b_vvix": float(r["beta"][1]), "t_vvix": float(r["t"][1]), "p_neg": float(_N.cdf(r["t"][1]))}


def tercile_split(b_obs: Sequence[dict], disc: Sequence[dict], key: str) -> dict:
    """Short-spread P&L per max loss in ``key``'s top tercile vs the other weeks, the cut from its 2019-2022 weekly values
    (``disc``; at least 10), among the observable confirmation weeks ``b_obs`` (reported)."""
    dz = np.array([w[key] for w in disc if w.get(key) is not None], float)
    cut = float(np.quantile(dz, 2 / 3)) if dz.size >= 10 else None
    top = [w["spread"] for w in b_obs if cut is not None and w.get(key) is not None and w[key] >= cut]
    oth = [w["spread"] for w in b_obs if cut is not None and w.get(key) is not None and w[key] < cut]
    tm, om = (float(np.mean(top)) if top else None), (float(np.mean(oth)) if oth else None)
    return {"cut": cut, "n_top": len(top), "n_other": len(oth), "top_mean": tm, "other_mean": om,
            "diff": None if tm is None or om is None else tm - om, "top": top, "other": oth}


def tercile_placebo(top: Sequence[float], oth: Sequence[float], draws: int = 1000, seed: int = SEED) -> dict:
    """Random-tercile placebo: the top-minus-other difference with the top label permuted i.i.d. over the same weeks
    (group sizes kept); one-sided p = share of placebo differences >= the observed one (reported)."""
    x = np.asarray(list(top) + list(oth), float)
    k = len(top)
    if k < 1 or x.size - k < 1:
        return {"p": None, "draws": 0}
    obs = float(np.mean(top) - np.mean(oth))
    rng = np.random.default_rng(seed)
    perm = np.argsort(rng.random((int(draws), x.size)), axis=1)
    px = x[perm]
    d = px[:, :k].mean(axis=1) - px[:, k:].mean(axis=1)
    return {"p": float((np.sum(d >= obs - 1e-12) + 1) / (d.size + 1)), "draws": int(d.size), "observed": obs}


def t654_report(weeks: Sequence[dict], cnt: Counter, info: dict) -> dict:
    """T-654 on the observable weeks; every criterion None (rule 9 data limit), verdict inconclusive. The registered
    controls (every-week short spread, VIX-only and SKEW-only terciles, a random-tercile placebo, unhedged put returns)
    and the VVIX-on-VIX residual trial of the DSR set are computed and reported only."""
    inw = lambda w, lo, hi: lo <= w["entry"] <= hi
    tot = len(weeks)
    disc = [w for w in weeks if inw(w, *T654_DISC)]
    conf = [w for w in weeks if inw(w, *T654_CONF)]
    full = lambda w, key: w["bin"] is not None and None not in (w.get(key), w.get("VIX"), w.get("rv21"))
    a_obs = [w for w in conf if full(w, "VVIX")]
    a_disc = [w for w in disc if full(w, "VVIX")]
    reg = {"confirmation": _t654_reg(a_obs, "VVIX"), "discovery": _t654_reg(a_disc, "VVIX"),
           "confirmation_vvix_resid": _t654_reg([w for w in conf if full(w, "vvix_resid")], "vvix_resid")}
    b_obs = [w for w in conf if w["spread"] is not None]
    terc = {k: tercile_split(b_obs, disc, k) for k in ("VVIX", "VIX", "SKEW", "vvix_resid")}
    tv = terc["VVIX"]
    cut, top, oth = tv["cut"], tv["top"], tv["other"]
    every = [w["spread"] for w in b_obs]
    every_comm = [w["spread_comm"] for w in b_obs]
    placebo = tercile_placebo(top, oth)
    obs_bin = sum(1 for w in weeks if w["bin"] is not None)
    obs_sp = sum(1 for w in weeks if w["spread"] is not None)
    rows = [(f"(a) confirmation z(VVIX) slope < 0 with one-sided p < 0.05 given z(VIX) and RV21 (observable weeks "
             f"{reg['confirmation']['n']}: {_s(reg['confirmation'].get('b_vvix'), 4)}, t {_s(reg['confirmation'].get('t_vvix'), 2)}) "
             f"[rule 9 data limit: not judged]", None, False),
            (f"(b) top-tercile short-spread net P&L per max loss > 0 and above the other weeks, bootstrap lower bounds > 0 "
             f"({len(top)} top / {len(oth)} other observable weeks) [rule 9 data limit: not judged]", None, False),
            (f"DSR >= {DSR_PASS} over the {T654_TRIALS} trials [rule 9 data limit: not judged]", None, False),
            (f"the registered weekly exit quotes are observable (bin {obs_bin} of {tot} weeks, spread {obs_sp} of {tot})", None, False)]
    n = len(a_obs)
    v, why, crit = CAL._judge(rows, n, T654_MIN_N, "confirmation weeks with an observable hedged-put return")
    controls = {"every_week_short_spread": {"n": len(every), "mean": float(np.mean(every)) if every else None,
                                            "mean_after_commission": float(np.mean(every_comm)) if every_comm else None},
                "terciles": {k: {kk: vv for kk, vv in t.items() if kk not in ("top", "other")} for k, t in terc.items()},
                "random_tercile_placebo": placebo,
                "vvix_resid_regression": reg["confirmation_vvix_resid"]}
    stat = {"weeks": tot, "observable_bin_weeks": obs_bin, "observable_spread_weeks": obs_sp,
            "observable_confirmation_bin_weeks": n, "skipped": dict(cnt), "chain": info, "regression": reg,
            "tercile_cut_2019_2022": cut, "top_mean": tv["top_mean"], "other_mean": tv["other_mean"],
            "n_top": len(top), "n_other": len(oth), "controls": controls,
            "bin_fallback_exits": sum(1 for w in weeks if w.get("bin_fallback")),
            "mean_hedged_put_return": float(np.mean([w["bin"] for w in weeks if w["bin"] is not None])) if obs_bin else None,
            "mean_unhedged_put_return": float(np.mean([w["bin_unhedged"] for w in weeks if w["bin"] is not None])) if obs_bin else None,
            "criteria": crit}
    tt = lambda k: (f"{k} top {_pc(terc[k]['top_mean'])} (n {terc[k]['n_top']}) vs other {_pc(terc[k]['other_mean'])} "
                    f"(n {terc[k]['n_other']})")
    reason = (f"DATA LIMIT (rule 9): on dolt-chain-SPY ({info.get('quote_days')} quote days, {tot} ISO weeks "
              f"{weeks[0]['entry'] if weeks else 'n/a'}..{weeks[-1]['entry'] if weeks else 'n/a'}) the registered exit — the same "
              f"contract at the next week's last quote day, or within 3 sessions after it — is observable for the 0.90-0.95 "
              f"put bin in {obs_bin} of {tot} weeks and for both 5%/10% spread legs in {obs_sp}: DoltHub lists a 2/4/8-week "
              f"expiry ladder and a K/S strike ladder re-centred on each day's close, so a ~30-DTE contract is rarely quoted "
              f"a week later (skips: {', '.join(f'{k} {v_}' for k, v_ in sorted(cnt.items()))}). On the observable weeks: "
              f"mean hedged put return net of DTB3 {_pc(stat['mean_hedged_put_return'])} (unhedged "
              f"{_pc(stat['mean_unhedged_put_return'])}); confirmation regression n {reg['confirmation']['n']} (z(VVIX) slope "
              f"{_s(reg['confirmation'].get('b_vvix'), 4)}), discovery n {reg['discovery']['n']}, VVIX-residual n "
              f"{reg['confirmation_vvix_resid']['n']}; top-tercile spreads (cut z {_s(cut, 2)} from 2019-2022) mean "
              f"{_pc(stat['top_mean'])} over {len(top)} weeks vs {_pc(stat['other_mean'])} over {len(oth)}; controls "
              f"(reported): every-week short spread {_pc(controls['every_week_short_spread']['mean'])} over {len(every)} "
              f"weeks; {tt('VIX')}; {tt('SKEW')}; {tt('vvix_resid')}; random-tercile placebo p "
              f"{_f(placebo['p'], 3)} ({placebo['draws']} draws). These weeks are selected by the vendor's listing pattern, "
              f"not the claim's weekly sample, so no criterion is judged and the verdict is inconclusive until a chain "
              f"source quotes every contract weekly (signals: VVIX/VIX/SKEW z and RV21 from the session before entry; the "
              f"claim's weekly calendar, rule 10(a)) — {why}")
    return {"stat": stat, "n": n, "verdict": "inconclusive" if v == "supported" else v, "reason": reason}


# ======================================================================================= T-655 BTC VRP ratio ==

def daily_closes(rows, ts_key: str, scale: float = 1.0) -> dict:
    """{UTC day of the bar's start: close} from daily-bar rows keyed by ``ts_key`` (seconds x ``scale``)."""
    out = {}
    for r in rows:
        v = r.get("value") or {}
        ts, c = v.get(ts_key), v.get("close")
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if ts is None or not (c > 0 and math.isfinite(c)):
            continue
        out[datetime.fromtimestamp(float(ts) / scale, tz=timezone.utc).strftime("%Y-%m-%d")] = c
    return out


def day_frame(dvol: dict, px: dict) -> tuple:
    """(days, dvol, close) on the continuous calendar from the first to the last day either series has (NaN = missing)."""
    ks = sorted(set(dvol) | set(px))
    if not ks:
        return [], np.zeros(0), np.zeros(0)
    d0, d1 = date.fromisoformat(ks[0]), date.fromisoformat(ks[-1])
    days = [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
    return (days, np.array([dvol.get(d, np.nan) for d in days], float), np.array([px.get(d, np.nan) for d in days], float))


def tercile_labels(dv: np.ndarray, win: int = T655_WIN) -> np.ndarray:
    """Per day k: -1 bottom / 0 middle / +1 top tercile of dv[k] among dv[k-win+1..k] (the share strictly below it:
    < 1/3 bottom, >= 2/3 top), NaN when the window is incomplete. Uses dv up to k only."""
    dv = np.asarray(dv, float)
    out = np.full(dv.size, np.nan)
    for k in range(win - 1, dv.size):
        w = dv[k - win + 1:k + 1]
        if not np.isfinite(w).all():
            continue
        share = float(np.sum(w < dv[k])) / win
        out[k] = -1.0 if share < 1.0 / 3.0 else (1.0 if share >= 2.0 / 3.0 else 0.0)
    return out


def forward_rv(close: np.ndarray, hold: int = T655_HOLD) -> np.ndarray:
    """Per day k: (365 / hold) x the sum of the ``hold`` squared log returns of closes k..k+hold; NaN if any is missing."""
    c = np.asarray(close, float)
    lr = np.full(c.size, np.nan)
    lr[:-1] = np.log(c[1:] / c[:-1])
    out = np.full(c.size, np.nan)
    for k in range(c.size - hold):
        w = lr[k:k + hold]
        if np.isfinite(w).all():
            out[k] = 365.0 / hold * float(np.sum(w * w))
    return out


def vrp_frame(dvol: dict, px: dict, start: str = T655_START, end: str = T655_END) -> dict:
    days, dv, cb = day_frame(dvol, px)
    lab = tercile_labels(dv)
    rv = forward_rv(cb)
    iv2 = (dv / 100.0) ** 2
    ratio = 1.0 - rv / iv2
    ent = np.array([start <= d <= end for d in days], bool) & np.isfinite(lab) & np.isfinite(ratio)
    return {"days": days, "dv": dv, "cb": cb, "lab": lab, "rv": rv, "ratio": ratio, "var_gap": iv2 - rv, "ent": ent,
            "n_window": int(sum(start <= d <= end for d in days))}


def _contrast_ci(x, a, b, block: int, n_boot: Optional[int] = None) -> dict:
    nb = 2000 if n_boot is None else int(n_boot)

    def fn(seed):
        bt = SURF.stud_group(x, a, b, block, nb, seed)
        return {"ci": list(SURF.two_sided(bt)) if bt is not None else [None, None]}

    return BW.mc_escalate(fn, lambda t: BW._ci_crit(t, "gt", 0.0, "")[1])


def vrp_tercile_test(F: dict, straddle: Optional[dict] = None, eth: Optional[dict] = None, n_boot: Optional[int] = None) -> dict:
    """T-655 core on a vrp_frame."""
    days = [d for d, e in zip(F["days"], F["ent"]) if e]
    idx = np.where(F["ent"])[0]
    x = F["ratio"][idx]
    lab = F["lab"][idx]
    bot, top, mid = lab == -1, lab == 1, lab == 0
    diff = float(x[bot].mean() - x[top].mean()) if bot.any() and top.any() else None
    ci = _contrast_ci(x, bot, top, T655_BLOCK, n_boot)
    row1 = BW._ci_crit(ci, "gt", 0.0, f"bottom-minus-top tercile mean ratio {_s(diff, 4)}: studentized CBB (90-day blocks) "
                                      f"lower 95% bound > 0")
    hs = np.array([d < T655_SPLIT for d in days], bool)
    halves = []
    for m in (hs, ~hs):
        halves.append(float(x[m & bot].mean() - x[m & top].mean()) if (m & bot).any() and (m & top).any() else None)
    row2 = (f"both halves positive (2022-03..2024-06 {_s(halves[0], 4)}, 2024-07..2026-09 {_s(halves[1], 4)})",
            None if None in halves else bool(halves[0] > 0 and halves[1] > 0), False)
    n = XC.n_holds(idx, T655_HOLD)
    v, why, crit = CAL._judge([row1, row2], n, T655_MIN_N, "30-day holds spanned by the pooled entries")
    lo, hi = ci.get("ci") or (None, None)
    reverse = hi is not None and hi < 0
    # reported
    blocks = lambda m: len({(k - idx[0]) // T655_HOLD for k in idx[m]})
    rng = np.random.default_rng(SEED)
    plac = []
    for _ in range(T655_PLACEBO):
        pl = rng.permutation(lab)
        plac.append(x[pl == -1].mean() - x[pl == 1].mean())
    plac = np.array(plac)
    off = (idx - idx[0]) % T655_HOLD
    off_d = [float(x[(off == o) & bot].mean() - x[(off == o) & top].mean()) for o in range(T655_HOLD)
             if ((off == o) & bot).any() and ((off == o) & top).any()]
    vg = F["var_gap"][idx]
    rep = {"means": {"bottom": float(x[bot].mean()) if bot.any() else None, "middle": float(x[mid].mean()) if mid.any() else None,
                     "top": float(x[top].mean()) if top.any() else None},
           "counts": {"bottom": int(bot.sum()), "middle": int(mid.sum()), "top": int(top.sum())},
           "blocks_30d": {"bottom": blocks(bot), "top": blocks(top)},
           "var_gap_diff": float(vg[bot].mean() - vg[top].mean()) if bot.any() and top.any() else None,
           "var_gap_means": {"bottom": float(vg[bot].mean()), "top": float(vg[top].mean())} if bot.any() and top.any() else None,
           "placebo_p": float((np.sum(plac >= (diff if diff is not None else np.inf)) + 1) / (plac.size + 1)),
           "placebo_sd": float(plac.std()), "offset_diffs": {"min": min(off_d) if off_d else None, "max": max(off_d) if off_d else None,
                                                             "n_positive": sum(1 for d_ in off_d if d_ > 0), "n": len(off_d)},
           "reverse_finding": bool(reverse)}
    # Hurst's gate: DVOL - trailing 30-day RV >= 5 vol pts
    trv = XC.trailing_rv(F["cb"], idx, 30)
    gate = (F["dv"][idx] - trv) >= T655_GATE
    gate &= np.isfinite(trv)
    rep["gate_iv_rv_5"] = {"n_on": int(gate.sum()), "mean_on": float(x[gate].mean()) if gate.any() else None,
                           "mean_off": float(x[~gate].mean()) if (~gate).any() else None,
                           "bottom_minus_top_on": (float(x[gate & bot].mean() - x[gate & top].mean())
                                                   if (gate & bot).any() and (gate & top).any() else None)}
    if straddle is not None:
        rep["straddle"] = straddle
    if eth is not None:
        rep["eth"] = eth
    stat = {"n": n, "n_entries": int(idx.size), "first_last": [days[0], days[-1]] if days else None, "diff": diff,
            "ci": ci.get("ci"), "ci_mc_se": ci.get("ci_mc_se"), "reps": ci.get("reps"), "halves": halves, "reported": rep,
            "criteria": crit}
    return {"stat": stat, "n": n, "verdict": v, "why": why, "lab": lab, "idx": idx}


def straddle_by_tercile(F: dict, idx: np.ndarray, lab: np.ndarray, funding=None) -> dict:
    """T-255's MODEL-PRICED delta-hedged short 30-day ATM straddle (batch6_xc.hedged_straddle at DVOL, r = 0) entered on
    each pooled entry, P&L per unit of entry vega (vol points), by tercile; T-256's long straddle is its negative."""
    days, cb, dv = F["days"], F["cb"], F["dv"]
    ok = np.array([k + T655_HOLD < len(days) and np.isfinite(cb[k:k + T655_HOLD + 1]).all() and np.isfinite(dv[k:k + T655_HOLD + 1]).all()
                   for k in idx], bool)
    st = idx[ok]
    if st.size == 0:
        return {"n": 0}
    r = XC.hedged_straddle(days, np.nan_to_num(cb, nan=1.0), np.nan_to_num(dv, nan=50.0), starts=st, hold=T655_HOLD,
                           funding_rate=funding)
    T = T655_HOLD / 365.0
    sig = np.maximum(dv[st] / 100.0, 0.01)
    S = cb[st]
    vega = 2.0 * S * math.sqrt(T) * np.exp(-0.5 * (0.5 * sig * math.sqrt(T)) ** 2) / math.sqrt(2 * math.pi) / 100.0
    g, nt = r["gross"] / vega, r["net"] / vega
    L = lab[ok]
    out = {"n": int(st.size), "funding": "signed perpetual funding" if funding is not None else "1 bp/day"}
    for nm, v in (("bottom", -1), ("middle", 0), ("top", 1)):
        m = L == v
        out[nm] = {"n": int(m.sum()), "gross_per_vega": float(g[m].mean()) if m.any() else None,
                   "net_per_vega": float(nt[m].mean()) if m.any() else None}
    return out


def eth_check(dvol_eth: dict, px_eth: dict) -> dict:
    F = vrp_frame(dvol_eth, px_eth)
    idx = np.where(F["ent"])[0]
    if idx.size < 50:
        return {"n_entries": int(idx.size)}
    x, lab = F["ratio"][idx], F["lab"][idx]
    bot, top = lab == -1, lab == 1
    bt = SURF.stud_group(x, bot, top, T655_BLOCK, 2000, SEED)
    lo, hi = SURF.two_sided(bt) if bt is not None else (None, None)
    return {"n_entries": int(idx.size), "diff": float(x[bot].mean() - x[top].mean()) if bot.any() and top.any() else None,
            "ci": [lo, hi]}


def b13_implied_a_btc_vrp_ratio_tercile(archive):
    """T-655: BTC VRP as a fraction of implied variance, bottom minus top trailing-365-day DVOL tercile (pooled daily)."""
    miss = B7C._missing(archive, [DVOL_B, CB_BTC_B])
    if miss:
        return miss

    def run():
        dvol = daily_closes(CAL._rows(archive, DVOL_B), "ts_ms", 1000.0)
        px = daily_closes(CAL._rows(archive, CB_BTC_B), "t")
        F = vrp_frame(dvol, px)
        core = vrp_tercile_test(F)
        fund = None
        if B7C._has(archive, FUND_B):
            fund = XC.funding_rate_series(F["days"], XC._funding_by_day(CAL._rows(archive, FUND_B)))
        strad = straddle_by_tercile(F, core["idx"], core["lab"], fund)
        eth = None
        if B7C._has(archive, DVOL_ETH_B) and B7C._has(archive, CB_ETH_B):
            eth = eth_check(daily_closes(CAL._rows(archive, DVOL_ETH_B), "ts_ms", 1000.0),
                            daily_closes(CAL._rows(archive, CB_ETH_B), "t"))
        core["stat"]["reported"]["straddle"] = strad
        core["stat"]["reported"]["eth"] = eth
        return {"stat": core["stat"], "n": core["n"], "verdict": core["verdict"], "reason": _vrp_reason(core, strad, eth)}

    rep = CAL._cached(archive, ("b13_implied_a", "T-655"), run)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


def _vrp_reason(core: dict, strad: dict, eth: Optional[dict]) -> str:
    st = core["stat"]
    rp = st["reported"]
    lo, hi = st["ci"] or (None, None)
    g = rp["gate_iv_rv_5"]
    sb = lambda k: (strad.get(k) or {}).get("gross_per_vega")
    ethtxt = ("n/a" if not eth or eth.get("diff") is None else
              f"{_s(eth['diff'], 4)} [{_s(eth['ci'][0], 4)}, {_s(eth['ci'][1], 4)}] on {eth['n_entries']} entries")
    return (f"{st['n_entries']} daily entries {st['first_last'][0] if st['first_last'] else 'n/a'}..{st['first_last'][1] if st['first_last'] else 'n/a'} "
            f"(bottom {rp['counts']['bottom']}, middle {rp['counts']['middle']}, top {rp['counts']['top']}; 30-day blocks "
            f"holding bottom {rp['blocks_30d']['bottom']}, top {rp['blocks_30d']['top']}): mean ratio 1 - RV_fwd/IV^2 bottom "
            f"{_s(rp['means']['bottom'], 4)}, middle {_s(rp['means']['middle'], 4)}, top {_s(rp['means']['top'], 4)}; "
            f"bottom-minus-top {_s(st['diff'], 4)}, 95% CI [{_s(lo, 4)}, {_s(hi, 4)}] (studentized CBB, 90-day blocks, "
            f"{st['reps']} seeds); halves {_s(st['halves'][0], 4)} / {_s(st['halves'][1], 4)}"
            f"{'; REVERSE finding (top > bottom with the bound above 0), recorded, not a pass' if rp['reverse_finding'] else ''}; "
            f"variance units bottom-minus-top {_s(rp['var_gap_diff'], 4)}; shuffled-tercile placebo p {_f(rp['placebo_p'], 3)}; "
            f"per-offset differences {_s(rp['offset_diffs']['min'], 3)}..{_s(rp['offset_diffs']['max'], 3)} "
            f"({rp['offset_diffs']['n_positive']} of {rp['offset_diffs']['n']} positive); MODEL-PRICED T-255 hedged short "
            f"straddle per unit vega (vol pts, {strad.get('funding', 'n/a')}) bottom {_s(sb('bottom'), 2)}, middle "
            f"{_s(sb('middle'), 2)}, top {_s(sb('top'), 2)} (T-256's long straddle is the negative); IV - trailing RV >= 5 "
            f"gate on {g['n_on']} days: ratio {_s(g['mean_on'], 4)} vs {_s(g['mean_off'], 4)} off; ETH (Coinbase ETH-USD, "
            f"reported) {ethtxt}. Terciles from the trailing 365 DVOL closes known at D+1 00:00; RV from closes D..D+30; "
            f"pooled over all 30 offsets (rule 10), n = 30-day holds spanned — {core['why']}")


HARNESSES = {"b13_implied_a_vx_roll_carry": b13_implied_a_vx_roll_carry,
             "b13_implied_a_vix_premium_risk": b13_implied_a_vix_premium_risk,
             "b13_implied_a_vvix_put_hedge": b13_implied_a_vvix_put_hedge,
             "b13_implied_a_btc_vrp_ratio_tercile": b13_implied_a_btc_vrp_ratio_tercile}
THEORY_MAP = {"T-651": "b13_implied_a_vx_roll_carry", "T-652": "b13_implied_a_vix_premium_risk",
              "T-654": "b13_implied_a_vvix_put_hedge", "T-655": "b13_implied_a_btc_vrp_ratio_tercile"}
