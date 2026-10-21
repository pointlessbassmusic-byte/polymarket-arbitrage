"""
Batch 13, group ``calendar_b``: four calendar / flow claims from the 2026-10-20 web sweep (cluster "calendar"), 2026-10-20.
=======================================================================================================================

  * T-586  Threshold rebalancing signal (Harvey-Mazzoleni-Melone, NBER w33554). 26 simulated 60/40 SPY/IEF portfolios,
           bands delta = 0.0%..2.5% in 0.1% steps: each drifts with SPY and IEF adjclose returns and is reset to 60/40 at a
           close where |w - 0.6| >= delta. Signal = the mean over the bands of the deviation w - 0.6 at the close (before
           that close's reset: the deviation the reset trades away, see readings below). Dependent: the close t -> t+1
           return of SPY - k IEF, k the trailing 252-session OLS hedge ratio cov(SPY, IEF) / var(IEF) (the "beta-neutral
           ratio") known at the signal close. Holdout 2023-03-18..2026-10. Rule 12: (b) signal at close t-1, position close
           t -> t+1 (primary); (a) signal at close t (MOC-optimistic). Pass: slope < 0 with one-sided p < 0.05 under (b)
           and the same sign under (a); the partial coefficient over the T-345 dummy and the T-59 turn-of-month dummies
           negative with p < 0.05; the 4-6% placebo bands weaker; the secondary trigger (-sign(signal) x spread when
           |signal| > its trailing 252-day 80th percentile, net of 2 bps per leg) mean > 0. min_n 150 holdout days.
  * T-584  Post-FOMC Treasury yield drift (Brooks-Katz-Lustig, NBER w25127). Scheduled FOMC statement days t, 2008-11..
           2026-10: s = DTB3(t) - DTB3(previous print); y = DGS10(t+22) - DGS10(t+2) (sessions). OLS slope of y on s
           (Newey-West lag 1 meeting); a studentized bootstrap over meetings and a permutation of s (10,000 draws each).
           Trade: an IEF position proportional to -s (in units of the point-in-time sd of s, capped at +/-2), scaled to a
           constant duration, entered at the t+2 close and held 20 sessions, net of 2 bps a round trip. Pass: slope > 0
           with one-sided p < 0.05 under both nulls, positive in 2008-11..2017-12 and 2018-01..2026-10, trade mean net > 0,
           with >= 60 holdout meetings outside the ZLB (DFF > 0.25%); fewer -> inconclusive.
  * T-585  Dash for cash under the settlement shift (Etula-Rinne-Suominen-Vaittinen, RFS 2020). T = the last session of
           the month; rho = the Pearson correlation across months of SPY's r(T-3) and r(T-2). Statistic rho(T+2 era,
           2017-09-05..2024-05-24) - rho(T+3 era, 1995-07..2017-09-01). Pass: < 0 with one-sided p < 0.05 under a month
           bootstrap within regime and a permutation of regime labels (10,000 draws each); IWM the same sign; the IEF
           difference not significant (two-sided p > 0.1); mean r(T-3) T+2 minus T+3 negative. min_n 80 T+2-era months.
  * T-590  Payday (16th) anomaly. SPY's return on the first session on or after the 16th (close of the last session
           before the 16th to its close) minus the mean return of the other sessions, both outside T-59's turn-of-month
           window (the last 4 and first 3 sessions of each month), 2011-01..2026-10. Pass: > 2 bps with one-sided p < 0.05
           (studentized circular block bootstrap, 21 sessions, 5 seeds), both halves (2011-2018 / 2019-2026) positive,
           the 2018-10..2026-10 mean difference > 0, IWM and QQQ the same sign after Holm. min_n 180 16th sessions.

Conventions (and every reading taken before any run; the harness reasons repeat the binding ones)
  * Data. ``batch6c_cal._daily`` (Yahoo adjclose = total return; a row is used only when available at capture) and
    ``batch6c_cal._series`` (FRED ``{day: value}``). Two-asset statistics use the pair's common sessions. Month positions
    come from the NYSE rule calendar (``batch6c_cal``: scheduled holidays plus the known unscheduled closures), which
    the bars match exactly for every series used here (``calendar_check``: no unexplained gaps, no bars on closed days);
    in the data's final, incomplete month a bar's distance to the month end counts the scheduled sessions still to come,
    so no bar is mistaken for a month-end session.
  * Costs as registered: T-590 charges 2 bps per round trip on each 16th session and the bar is tested on the NET
    difference (gross - 2 bps > 2 bps: the cost and the claim's 2 bp bar are both charged, the conservative reading);
    T-586's trigger pays 2 bps per leg per triggered day on each leg's notional, at least 2 bps a leg (2 bps x (1 +
    max(1, |k|))); T-584 pays 2 bps per round trip on the position's notional; T-585 is a statistic, no cost.
  * Inference. Every resampled p is pooled over seeds and escalated while its Monte-Carlo band straddles 0.05
    (``batch6c_cal.escalate_p``; ``decide_p``), so a seed never decides a criterion. Where a criterion names two nulls or
    two readings it passes only when both pass and fails only when both fail (``_agree``), else it is undecided.
  * Rule 10: no claim here holds on a fixed grid with a free phase: T-590's session and T-585's month-end positions are
    the calendars the claims name, T-584's holds are anchored on FOMC statement days, T-586 trades every session.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from datetime import date, timedelta
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch4_ohlc import ex_dividends
from mandel.experiments.batch6_surf import _out

SEED = 0
N_BOOT = 2000                    # bootstrap resamples per seed (5 seeds -> 10,000 draws)
N_DRAWS = 10000                  # "10,000 draws" for T-584's permutation and T-585's bootstrap / permutation
_NORM = NormalDist()

SPY_B, IEF_B, TLT_B = "daily-history-SPY", "daily-history-IEF", "daily-history-TLT"
IWM_B, QQQ_B = "daily-history-IWM", "daily-history-QQQ"
DGS10_B, DGS2_B, DTB3_B, DFF_B = "fred-DGS10", "fred-DGS2", "fred-DTB3", "fred-DFF"
FOMC_B, CPI_B = "fomc-meetings", "macro-release-cpi"

# T-586
T586_HOLD = "2023-03-18"                                  # after the paper's sample
T586_BANDS = tuple(round(i * 0.001, 4) for i in range(26))          # 0.0% .. 2.5% in 0.1% steps (26 bands)
T586_PLACEBO = tuple(round(0.040 + i * 0.001, 4) for i in range(21))  # 4.0% .. 6.0%
T586_TARGET = 0.6
T586_BETA_WIN = 252
T586_PCTL, T586_PCTL_WIN = 0.80, 252
T586_COST_LEG = 2e-4
T586_BLOCK = 10                                           # stationary bootstrap mean block
T586_MIN_N = 150
T586_FLAG_MONTHS = ("2020-03",)
T586_FLAG_YEARS = ("2022",)
# T-584
T584_START, T584_END = "2008-11-01", "2026-10-31"
T584_SPLIT = "2018-01-01"                                 # halves 2008-11..2017-12 / 2018-01..2026-10
T584_PAPER = ("1994-01-01", "2008-10-31")                 # in-paper replication (the archive's meetings start 1994)
T584_LAG, T584_H = 2, 20                                  # entry at the t+2 close, hold 20 sessions
T584_ALT_H = (10, 50)
T584_COST = 2e-4                                          # 2 bps a round trip
T584_CAP = 2.0
T584_ZLB = 0.25                                           # DFF above 0.25% = outside the ZLB
T584_MIN_N = 60
T584_DUR_WIN = 252
T584_D_REF = 7.5                                          # constant target duration (years) of the scaled IEF position
# T-585
T585_ERAS = {"T+3": ("1995-07-01", "2017-09-01"), "T+2": ("2017-09-05", "2024-05-24"), "T+1": ("2024-05-28", "9999-12-31")}
T585_IN_PAPER_END = "2013-12"                             # T+3 months 1995-2013 in-paper, 2014-2017 reported separately
T585_MIN_N = 80
# T-590
T590_START, T590_END = "2011-01-01", "2026-10-31"
T590_SPLIT = "2019-01-01"                                 # halves 2011-2018 / 2019-2026
T590_POST = "2018-10-01"                                  # post-SSRN subsample
T590_BAR = 2e-4
T590_COST = 2e-4
T590_BLOCK = 21
T590_MIN_N = 180


# ================================================================================================ shared helpers ==

def _missing(archive, names):
    return B7C._missing(archive, names)


def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f}"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _mc(p, draws) -> str:
    return CAL._mc(p, draws)


def _rule_sessions(y: int, m: int, with_unscheduled: bool = True) -> list:
    """NYSE rule-calendar sessions of a month (scheduled holidays removed; the known unscheduled closures removed too
    unless ``with_unscheduled`` is False, i.e. the calendar as it was scheduled in advance)."""
    if y < CAL.SCHEDULE_FROM:
        return []
    hol = CAL.nyse_scheduled_holidays(y)
    d, out = date(y, m, 1), []
    while d.month == m:
        if d.weekday() < 5 and d not in hol and not (with_unscheduled and d.isoformat() in CAL.UNSCHEDULED_CLOSURES):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def month_positions(days: Sequence[str]) -> tuple:
    """(from_start, from_end, complete) per bar: 1-based position from its month's first session and from its last
    session (1 = the last session), both on the NYSE rule calendar (bars on a day the rules close fall back to bar
    counting), and whether the bar's month is complete in the data (its first and last rule sessions both have bars).
    A bar of the final, incomplete month counts the scheduled sessions still to come, so it is never read as a
    month-end session; the calendar is scheduled in advance."""
    n = len(days)
    fs, fe, comp = np.zeros(n, int), np.zeros(n, int), np.zeros(n, bool)
    by = defaultdict(list)
    for i, d in enumerate(days):
        by[d[:7]].append(i)
    for m, idx in by.items():
        rule = _rule_sessions(int(m[:4]), int(m[5:7]))
        pos = {d: k for k, d in enumerate(rule)}
        first, last = days[idx[0]], days[idx[-1]]
        complete = bool(rule) and first <= rule[0] and last >= rule[-1]
        for k, i in enumerate(idx):
            if days[i] in pos:
                fs[i] = pos[days[i]] + 1
                fe[i] = len(rule) - pos[days[i]]
            else:
                fs[i] = k + 1
                fe[i] = len(idx) - k
            comp[i] = complete or not rule
    return fs, fe, comp


def tom_flags(days: Sequence[str], before: int = 4, after: int = 3) -> np.ndarray:
    """T-59's window on the return day (a session's close-to-close return ends on it): the last ``before`` and first
    ``after`` sessions of each month, by rule-calendar position."""
    fs, fe, _ = month_positions(days)
    return (fs <= after) | (fe <= before)


def _asof(keys: list, vals: list, day: str, strict: bool = False):
    """Latest value dated on or before ``day`` (strictly before when ``strict``); None before the first print."""
    j = (bisect.bisect_left(keys, day) if strict else bisect.bisect_right(keys, day)) - 1
    return vals[j] if j >= 0 else None


def _ordered(series: dict) -> tuple:
    k = sorted(series)
    return k, [series[d] for d in k]


def ols_hac(y, X, lag: int) -> dict:
    """OLS of y on [1, X] with Newey-West (Bartlett, ``lag``) standard errors: coef / se / t lists (intercept first)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    n = y.size
    Z = np.column_stack([np.ones(n), X])
    if n <= Z.shape[1] + 1:
        return {"coef": None, "se": None, "t": None, "n": int(n), "lag": int(lag)}
    A = np.linalg.pinv(Z.T @ Z)
    b = A @ Z.T @ y
    e = y - Z @ b
    u = Z * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    se = np.sqrt(np.maximum(np.diag(A @ S @ A), 0.0))
    return {"coef": [float(v) for v in b], "se": [float(v) for v in se],
            "t": [float(c / s) if s > 0 else float("nan") for c, s in zip(b, se)], "n": int(n), "lag": int(lag)}


def _stationary_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (circular), k draws; mean_block 1 is the i.i.d. bootstrap."""
    p = 1.0 / max(float(mean_block), 1.0)
    new = rng.random((k, n)) < p
    new[:, 0] = True
    starts = rng.integers(0, n, (k, n))
    pos = np.arange(n)
    last = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
    st = np.take_along_axis(starts, last, axis=1)
    return (st + pos[None, :] - last) % n


def boot_coef_t(y, X, j: int, lag: int, mean_block: float, n_boot: int, seed: int, chunk: int = 200) -> tuple:
    """(p_greater, p_less) of coefficient ``j`` of X (0-based, intercept excluded) by a studentized (bootstrap-t)
    stationary bootstrap of the (y, X) rows: t* = (b* - b) / se*_HAC on each resample, p_greater = share of t* >= t,
    p_less = share of t* <= t (each with the +1 correction); HAC (Bartlett, ``lag``) on every resample."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    n = y.size
    Z = np.column_stack([np.ones(n), X])
    q = j + 1
    full = ols_hac(y, X, lag)
    if full["coef"] is None or not full["se"][q] > 0:
        return None, None
    b0, t0 = full["coef"][q], full["t"][q]
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        idx = _stationary_idx(rng, n, mean_block, k)
        Zb, yb = Z[idx], y[idx]
        Zt = np.transpose(Zb, (0, 2, 1))
        A = np.linalg.pinv(Zt @ Zb)
        B = (A @ (Zt @ yb[:, :, None]))[:, :, 0]
        e = yb - (Zb @ B[:, :, None])[:, :, 0]
        U = Zb * e[:, :, None]
        Ut = np.transpose(U, (0, 2, 1))
        S = Ut @ U
        for l in range(1, min(lag, n - 1) + 1):
            G = Ut[:, :, l:] @ U[:, :-l]
            S += (1.0 - l / (lag + 1.0)) * (G + np.transpose(G, (0, 2, 1)))
        V = A @ S @ A
        se = np.sqrt(np.maximum(V[:, q, q], 0.0))
        ok = se > 0
        ts.append((B[ok, q] - b0) / se[ok])
        done += k
    t = np.concatenate(ts)
    m = t.size
    return float((np.sum(t >= t0) + 1) / (m + 1)), float((np.sum(t <= t0) + 1) / (m + 1))


def coef_test(y, X, j: int, lag: int, mean_block: float, n_boot: int = N_BOOT, seed: int = SEED,
              n_seeds: int = CAL.N_SEEDS, max_seeds: Optional[int] = None) -> dict:
    """Coefficient ``j``: point, HAC t, HAC normal one-sided p's and the escalated studentized stationary-bootstrap p's."""
    full = ols_hac(y, X, lag)
    if full["coef"] is None:
        return {"coef": None, "t": None, "n": full["n"]}
    q = j + 1
    t = full["t"][q]
    pg, pl, dr = CAL.escalate_p(lambda k: boot_coef_t(y, X, j, lag, mean_block, n_boot, seed + k), n_boot, n_seeds,
                                CAL.MAX_SEEDS if max_seeds is None else max_seeds)
    return {"coef": full["coef"][q], "se": full["se"][q], "t": t, "n": full["n"], "lag": lag,
            "hac_p_less": float(_NORM.cdf(t)) if np.isfinite(t) else None,
            "hac_p_greater": float(1 - _NORM.cdf(t)) if np.isfinite(t) else None,
            "boot_p_greater": pg, "boot_p_less": pl, "boot_draws": dr}


def _sign_sig(test: dict, side: str) -> Optional[bool]:
    """'coef < 0 (side less) / > 0 (greater) with one-sided p < 0.05' under BOTH the HAC normal p and the stationary
    bootstrap p (rule 11): True when both pass, False when both fail, None when they disagree or are missing."""
    c = test.get("coef")
    if c is None or not np.isfinite(c):
        return None
    if (c >= 0) if side == "less" else (c <= 0):
        return False
    hp = test.get(f"hac_p_{side}")
    return CAL._agree([None if hp is None else hp < CAL.ALPHA, CAL.decide_p(test.get(f"boot_p_{side}"), test.get("boot_draws", 0))])


# ===================================================================================== T-586 threshold rebalancing ==

def band_deviations(rs, rb, deltas: Sequence[float], target: float = T586_TARGET) -> np.ndarray:
    """(n, bands) equity-weight deviations w - target of drifting 60/40 portfolios, one per band, at each close: row t
    applies day t's returns (rs[t], rb[t]: close t-1 -> t) to the weight carried from close t-1, records the deviation,
    then resets that band to the target when |w - target| >= delta. Row 0 (the start) is zero. Row t uses returns up
    to day t only."""
    rs, rb = np.asarray(rs, float), np.asarray(rb, float)
    dl = np.asarray(deltas, float)
    n = rs.size
    w = np.full(dl.size, target)
    out = np.zeros((n, dl.size))
    for t in range(1, n):
        gs, gb = 1.0 + rs[t], 1.0 + rb[t]
        w = w * gs / (w * gs + (1.0 - w) * gb)
        d = w - target
        out[t] = d
        w = np.where(np.abs(d) >= dl - 1e-12, target, w)
    return out


def rebal_signal(rs, rb, deltas: Sequence[float] = T586_BANDS, target: float = T586_TARGET) -> np.ndarray:
    """The threshold rebalancing signal at each close: the mean over the bands of the pre-reset deviation."""
    return band_deviations(rs, rb, deltas, target).mean(axis=1)


def trailing_beta(rs, rb, win: int = T586_BETA_WIN) -> np.ndarray:
    """k[t] = cov(rs, rb) / var(rb) over the ``win`` returns ending at day t (NaN before that), i.e. known at close t."""
    rs, rb = np.asarray(rs, float), np.asarray(rb, float)
    n = rs.size
    k = np.full(n, np.nan)
    if n <= win:
        return k
    cs = np.concatenate([[0.0], np.cumsum(rs)])
    cb = np.concatenate([[0.0], np.cumsum(rb)])
    csb = np.concatenate([[0.0], np.cumsum(rs * rb)])
    cbb = np.concatenate([[0.0], np.cumsum(rb * rb)])
    for t in range(win, n):                      # returns t-win+1 .. t (day 0 has no return)
        a, b = t - win + 1, t + 1
        ms, mb = (cs[b] - cs[a]) / win, (cb[b] - cb[a]) / win
        cov = (csb[b] - csb[a]) / win - ms * mb
        var = (cbb[b] - cbb[a]) / win - mb * mb
        k[t] = cov / var if var > 0 else np.nan
    return k


def trailing_vol_ratio(rs, rb, win: int = T586_BETA_WIN) -> np.ndarray:
    """sd(rs) / sd(rb) over the ``win`` returns ending at day t (reported sensitivity)."""
    rs, rb = np.asarray(rs, float), np.asarray(rb, float)
    n = rs.size
    k = np.full(n, np.nan)
    for t in range(win, n):
        a, b = t - win + 1, t + 1
        sb = rb[a:b].std()
        k[t] = rs[a:b].std() / sb if sb > 0 else np.nan
    return k


def trailing_quantile(x, q: float, win: int) -> np.ndarray:
    """The q-quantile of x over the ``win`` values strictly before each index (NaN before ``win`` values exist)."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    if x.size > win:
        from numpy.lib.stride_tricks import sliding_window_view
        out[win:] = np.quantile(sliding_window_view(x, win)[:-1], q, axis=1)
    return out


def t345_return_days(days: Sequence[str], spy, tlt) -> set:
    """T-345's calendar signal on the return-day calendar: the last two sessions of each month where SPY beat TLT
    month-to-date by more than 2 pp at the T-3 close (the 3rd-to-last session; ``batch6c_cal.month_end_table``)."""
    _, fe, _ = month_positions(days)
    last2 = defaultdict(list)
    for d, e in zip(days, fe):
        if e <= 2:
            last2[d[:7]].append(d)
    out = set()
    for r in CAL.month_end_table(days, spy, tlt, decision=3, lag=0):
        if r["S"] > CAL.T345_THR:
            out.update(last2[r["month"]])
    return out


def rebal_panel(days: Sequence[str], spy, ief, tlt=None, bond_syn=None) -> dict:
    """Per entry close t (position close t -> t+1): readings (a) signal / k at close t and (b) at close t-1, the spread
    y = r_SPY(t+1) - k r_IEF(t+1), placebo signals, the trigger's trailing 80th percentile of |signal|, the T-345 and
    T-59 dummies of return day t+1, and (when ``bond_syn`` is given) the synthetic-10Y signal lagged one more day."""
    days = list(days)
    spy, ief = np.asarray(spy, float), np.asarray(ief, float)
    n = len(days)
    rs = np.zeros(n); rb = np.zeros(n)
    rs[1:] = spy[1:] / spy[:-1] - 1
    rb[1:] = ief[1:] / ief[:-1] - 1
    S = rebal_signal(rs, rb, T586_BANDS)
    P = rebal_signal(rs, rb, T586_PLACEBO)
    k = trailing_beta(rs, rb)
    kv = trailing_vol_ratio(rs, rb)
    q80 = trailing_quantile(np.abs(S), T586_PCTL, T586_PCTL_WIN)
    fs, fe, _ = month_positions(days)
    t345 = t345_return_days(days, spy, tlt) if tlt is not None else None
    Ssyn = None
    if bond_syn is not None:
        rsyn = np.zeros(n)
        rsyn[1:] = np.asarray(bond_syn, float)[1:] / np.asarray(bond_syn, float)[:-1] - 1
        Ssyn = rebal_signal(rs, rsyn, T586_BANDS)
    t = np.arange(2, n - 1)                      # entry index; signal index t (a) or t - 1 (b); return day t + 1
    out = {"day": np.array([days[i] for i in t]), "ret_day": np.array([days[i + 1] for i in t]),
           "rs": rs[t + 1], "rb": rb[t + 1]}
    for lab, si in (("a", t), ("b", t - 1)):
        out[f"sig_{lab}"] = S[si]
        out[f"plc_{lab}"] = P[si]
        out[f"k_{lab}"] = k[si]
        out[f"y_{lab}"] = rs[t + 1] - k[si] * rb[t + 1]
        out[f"yv_{lab}"] = rs[t + 1] - kv[si] * rb[t + 1]
        out[f"q80_{lab}"] = q80[si]
    if Ssyn is not None:
        out["sig_syn"] = Ssyn[t - 2]
    out["tom"] = np.column_stack([fe[t + 1] == p for p in (4, 3, 2, 1)] + [fs[t + 1] == p for p in (1, 2, 3)]).astype(float)
    out["tom_any"] = out["tom"].max(axis=1)
    out["d345"] = None if t345 is None else np.array([d in t345 for d in out["ret_day"]], float)
    return out


def _both(oks) -> Optional[bool]:
    """Conjunction of sub-criteria (reading (b) and reading (a), or two assets): False when any fails, True when all
    pass, None otherwise (the conservative reading: a disagreement fails rather than staying undecided)."""
    oks = list(oks)
    if any(o is False for o in oks):
        return False
    if all(o is True for o in oks):
        return True
    return None


def _z(x):
    x = np.asarray(x, float)
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else x * 0.0


def trigger_pnl(sig, y, q80, k) -> np.ndarray:
    """Secondary trigger per day where |signal| > its trailing 80th percentile: -sign(signal) x spread, net of 2 bps per
    leg on each leg's notional, at least 2 bps a leg: 2 bps x (1 + max(1, |k|)). NaN on days without a trigger."""
    sig, y, q80, k = (np.asarray(v, float) for v in (sig, y, q80, k))
    on = np.isfinite(q80) & (np.abs(sig) > q80)
    cost = T586_COST_LEG * (1.0 + np.maximum(1.0, np.abs(k)))
    return np.where(on, -np.sign(sig) * y - cost, np.nan)


def rebal_test(P: dict, start: str = T586_HOLD, end: str = "9999-12-31", n_boot: int = N_BOOT, seed: int = SEED,
               min_n: int = T586_MIN_N, n_seeds: int = CAL.N_SEEDS) -> dict:
    """T-586 criteria over the entry days in [start, end] (each reading on its own valid days)."""
    base = (P["day"] >= start) & (P["day"] <= end)
    R = {}
    for lab in ("a", "b"):
        m = base & np.isfinite(P[f"k_{lab}"]) & np.isfinite(P[f"sig_{lab}"])
        y, z = P[f"y_{lab}"][m], _z(P[f"sig_{lab}"][m])
        L = CAL.nw_lags(int(m.sum()))
        r = {"n": int(m.sum()), "lag": L, "first": str(P["day"][m][0]) if m.any() else None,
             "last": str(P["ret_day"][m][-1]) if m.any() else None,
             "raw_slope": ols_hac(y, P[f"sig_{lab}"][m], L)["coef"][1] if m.sum() > 8 else None}
        if m.sum() < 30:
            R[lab] = r
            continue
        r["slope"] = coef_test(y, z, 0, L, T586_BLOCK, n_boot, seed, n_seeds)
        zp = _z(P[f"plc_{lab}"][m])
        r["placebo"] = coef_test(y, zp, 0, L, T586_BLOCK, n_boot, seed, n_seeds)
        if P["d345"] is not None:
            Xc = np.column_stack([z, P["d345"][m], P["tom"][m]])
            r["partial"] = coef_test(y, Xc, 0, L, T586_BLOCK, n_boot, seed, n_seeds)
            Xw = np.column_stack([z, P["d345"][m], P["tom_any"][m]])
            r["partial_one_window_dummy"] = {k_: v for k_, v in ols_hac(y, Xw, L).items() if k_ in ("coef", "t")}
            r["n_t345_days"] = int(P["d345"][m].sum())
        tp = trigger_pnl(P[f"sig_{lab}"][m], y, P[f"q80_{lab}"][m], P[f"k_{lab}"][m])
        tv = tp[np.isfinite(tp)]
        r["trigger"] = {"n": int(tv.size), "mean_net": float(tv.mean()) if tv.size else None,
                        "ci": CAL.mean_ci(tv, T586_BLOCK, n_boot, seed) if tv.size >= 2 else [None, None]}
        yv = P[f"yv_{lab}"][m]
        r["vol_ratio_spread"] = {k_: v for k_, v in ols_hac(yv, z, L).items() if k_ in ("coef", "t")}
        r["mean_k"] = float(np.mean(P[f"k_{lab}"][m]))
        R[lab] = r
    a, b = R["a"], R["b"]
    n = int(b["n"])
    if "slope" not in a or "slope" not in b:
        return {"readings": R, "n": n, "criteria": [("enough holdout days with SPY, IEF and the 252-day hedge ratio", None)]}
    c1 = _sign_sig(b["slope"], "less")
    c1a = None if a["slope"]["coef"] is None else a["slope"]["coef"] < 0
    c_main = c1 if c1 is not True else bool(c1a)
    dec_main = (_sign_sig(b["slope"], "greater") is True) or (c1 is True and c1a is False)
    if "partial" in b:
        cp = _sign_sig(b["partial"], "less")
        cpa = a["partial"]["coef"] < 0
        c_part = cp if cp is not True else bool(cpa)
        dec_part = _sign_sig(b["partial"], "greater") is True
    else:
        c_part, dec_part = None, False
    plc = [(R[l]["placebo"]["t"] > R[l]["slope"]["t"]) and (R[l]["placebo"]["coef"] > R[l]["slope"]["coef"]) for l in ("b", "a")]
    c_plc = CAL._agree(plc)
    tr = [R[l]["trigger"]["mean_net"] for l in ("b", "a")]
    c_trig = CAL._agree([None if v is None else v > 0 for v in tr])
    dec_trig = all(R[l]["trigger"]["ci"][1] is not None and R[l]["trigger"]["ci"][1] <= 0 for l in ("b", "a"))
    rows = [((f"holdout standardized slope < 0 with one-sided p < 0.05 under reading (b) (HAC normal p and stationary "
              f"bootstrap p, block {T586_BLOCK}, both) and the same sign under reading (a)"), c_main, dec_main),
            (("partial coefficient over the T-345 dummy and the seven T-59 turn-of-month day dummies < 0 with one-sided "
              "p < 0.05 under (b) (both p's) and the same sign under (a)"), c_part, dec_part),
            ("placebo bands 4-6% weaker (HAC t and standardized slope above the primary's) under (b) and (a)", c_plc, False),
            ("secondary trigger mean net of 2 bps per leg > 0 under (b) and (a)", c_trig, dec_trig)]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, min_n, "holdout days")
    return {"readings": R, "n": n, "criteria": [[c, ok] for c, ok in crit], "verdict": v, "why": why}


def _rebal_window(P: dict, start: str, end: str, drop=None) -> dict:
    """Reported: slope and HAC t of each reading over [start, end] (optionally dropping a day mask)."""
    out = {}
    for lab in ("a", "b"):
        m = (P["day"] >= start) & (P["day"] <= end) & np.isfinite(P[f"k_{lab}"])
        if drop is not None:
            m &= ~drop
        if m.sum() < 30:
            out[lab] = {"n": int(m.sum()), "coef": None, "t": None}
            continue
        r = ols_hac(P[f"y_{lab}"][m], _z(P[f"sig_{lab}"][m]), CAL.nw_lags(int(m.sum())))
        out[lab] = {"n": int(m.sum()), "coef": r["coef"][1], "t": r["t"][1]}
    return out


def b13_calendar_b_threshold_rebalancing(archive):
    """T-586: the threshold rebalancing signal predicts the next-day SPY - k IEF return (negative slope), holdout 2023-03-18 on."""
    miss = _missing(archive, [SPY_B, IEF_B, TLT_B, DGS10_B])
    if miss:
        return miss
    days, (spy, ief, tlt) = CAL._align(CAL._daily(archive, SPY_B), CAL._daily(archive, IEF_B), CAL._daily(archive, TLT_B))
    syn = CAL.bond_proxy_index(days, CAL._series(archive, DGS10_B))
    P = rebal_panel(days, spy, ief, tlt, syn)
    rep = rebal_test(P)
    if "verdict" not in rep:
        _, why = CAL._verdict(rep["criteria"])
        return _out(rep, rep["n"], "inconclusive", f"too few holdout days with SPY, IEF and the hedge ratio (rule 9) — {why}")
    R = rep["readings"]
    paper = _rebal_window(P, "2003-01-01", "2023-03-17")
    flag = np.array([d[:7] in T586_FLAG_MONTHS or d[:4] in T586_FLAG_YEARS for d in P["ret_day"]])
    paper_x = _rebal_window(P, "2003-01-01", "2023-03-17", drop=flag)
    syn_rep = {}
    m = (P["day"] >= T586_HOLD) & np.isfinite(P["k_b"]) & np.isfinite(P["sig_syn"])
    if m.sum() >= 30:
        r = ols_hac(P["y_b"][m], _z(P["sig_syn"][m]), CAL.nw_lags(int(m.sum())))
        syn_rep = {"n": int(m.sum()), "coef": r["coef"][1], "t": r["t"][1],
                   "corr_with_ief_signal": float(np.corrcoef(P["sig_syn"][m], P["sig_b"][m])[0, 1])}
    rep.update(in_paper_2003_2023=paper, in_paper_excl_2020_03_and_2022=paper_x, synthetic_dgs10_check=syn_rep)

    def one(lab):
        r = R[lab]
        s, pl, pa, tg = r["slope"], r["placebo"], r.get("partial", {}), r["trigger"]
        tag = "b, primary: signal at close t-1" if lab == "b" else "a, MOC-optimistic: signal at the entry close t"
        return (f"({tag}) {r['n']} days {r['first']}..{r['last']}: slope {_bp(s['coef'])} bps per sd (HAC t {_f(s['t'], 2)}, "
                f"lag {r['lag']}; HAC p {_f(s['hac_p_less'], 4)}, stationary-bootstrap p {_mc(s['boot_p_less'], s['boot_draws'])}); "
                f"partial over T-345 + T-59 dummies {_bp(pa.get('coef'))} (t {_f(pa.get('t'), 2)}, boot p "
                f"{_mc(pa.get('boot_p_less'), pa.get('boot_draws', 0))}); placebo 4-6% {_bp(pl['coef'])} (t {_f(pl['t'], 2)}); "
                f"trigger {tg['n']} days, mean net {_bp(tg['mean_net'])} bps (95% CI {CAL._ci_bps(tg['ci'])})")
    reason = ("SPY - k IEF next-day spread (k = trailing 252-day OLS hedge ratio, mean "
              f"{R['b']['mean_k']:+.2f} in the holdout) on the 26-band 60/40 threshold signal: " + one("b") + "; " + one("a")
              + f"; reported: in-paper 2003..2023-03-17 slope (b) {_bp(paper['b']['coef'])} (t {_f(paper['b']['t'], 2)}), "
              f"(a) {_bp(paper['a']['coef'])} (t {_f(paper['a']['t'], 2)}); without 2020-03 and 2022 (b) t {_f(paper_x['b']['t'], 2)}; "
              f"DGS10 synthetic-leg signal lagged a further day (FRED posts next day) holdout slope {_bp(syn_rep.get('coef'))} "
              f"(t {_f(syn_rep.get('t'), 2)}); vol-ratio spread (b) t {_f(R['b']['vol_ratio_spread']['t'][1], 2)}; "
              f"T-345 signal days in the holdout {R['b'].get('n_t345_days', 'n/a')}")
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + rep["why"])


# ======================================================================================= T-584 post-FOMC drift ==

def fomc_scheduled(rows) -> list:
    return sorted({(r.get("value", r))["decision_day"] for r in rows if (r.get("value", r)).get("scheduled")})


def ief_duration(r_ief, dy, i: int, win: int = T584_DUR_WIN) -> Optional[float]:
    """Empirical IEF duration from the ``win`` sessions ending at index i: -cov(r_IEF, dy) / var(dy), dy the DGS10
    change in decimal (DGS10 as of each session)."""
    a = i - win + 1
    if a < 1:
        return None
    r, d = r_ief[a:i + 1], dy[a:i + 1]
    if not (np.isfinite(r).all() and np.isfinite(d).all()):
        return None
    v = d.var()
    return float(-np.cov(r, d, bias=True)[0, 1] / v) if v > 0 else None


def fomc_events(meetings: Sequence[str], sdays: Sequence[str], ief, dtb3: dict, dgs10: dict, dgs2: dict, dff: dict,
                cpi_days=(), horizons=(T584_H,) + T584_ALT_H, lag: int = T584_LAG) -> list:
    """One row per scheduled statement day t that is a session (``sdays``: the NYSE sessions) with a DTB3 print: s
    (DTB3(t) - previous DTB3 print, pp), s2 (the same on DGS2), DFF before t, y_h = DGS10 at session t+lag+h minus at
    t+lag (as-of values), the IEF total return and the bill growth over the hold (``ief`` aligned to ``sdays``, NaN
    where IEF has no bar), the empirical IEF duration known at the entry (sessions through t, whose DGS10 print is
    published before the t+2 close) and the month-ends and CPI days inside the 20-session hold."""
    sdays = list(sdays)
    pos = {d: i for i, d in enumerate(sdays)}
    ief = np.asarray(ief, float)
    k3, v3 = _ordered(dtb3)
    k10, v10 = _ordered(dgs10)
    k2, v2 = _ordered(dgs2)
    kf, vf = _ordered(dff)
    y10 = np.array([np.nan if (x := _asof(k10, v10, d)) is None else x for d in sdays])
    dy = np.zeros(len(sdays)); dy[1:] = np.diff(y10) / 100.0
    r = np.zeros(len(sdays)); r[1:] = ief[1:] / ief[:-1] - 1
    _, fe, _ = month_positions(sdays)
    cpi = sorted(cpi_days)
    bills = CAL.Bills(dtb3) if dtb3 else None
    out = []
    for t in meetings:
        if t not in pos or t not in dtb3:
            continue
        i = pos[t]
        p3 = _asof(k3, v3, t, strict=True)
        if p3 is None:
            continue
        ev = {"day": t, "s": float(dtb3[t] - p3), "dff_prev": _asof(kf, vf, t, strict=True),
              "s2": (float(dgs2[t] - _asof(k2, v2, t, strict=True)) if t in dgs2 and _asof(k2, v2, t, strict=True) is not None else None)}
        e = i + lag
        if e < len(sdays):
            ev["entry"] = sdays[e]
            ev["dur"] = ief_duration(r, dy, i)
            ev["y_entry"] = float(y10[e])
        for h in horizons:
            x = e + h
            if x < len(sdays) and np.isfinite(y10[e]) and np.isfinite(y10[x]):
                ev[f"y{h}"] = float(y10[x] - y10[e])
                if np.isfinite(ief[x]) and np.isfinite(ief[e]):
                    ev[f"r{h}"] = float(ief[x] / ief[e] - 1)
                    ev[f"bill{h}"] = bills.growth(sdays[e], sdays[x]) if bills else 0.0
                if h == T584_H:
                    ev["exit"] = sdays[x]
                    ev["month_ends_in_hold"] = int(sum(1 for j in range(e + 1, x + 1) if fe[j] == 1))
                    ev["cpi_in_hold"] = int(bisect.bisect_right(cpi, sdays[x]) - bisect.bisect_right(cpi, sdays[e]))
        out.append(ev)
    return out


def size_positions(events: list, cap: float = T584_CAP, d_ref: float = T584_D_REF) -> None:
    """In place: pos = clip(-s / sd, -cap, cap), sd = the sd of s over every EARLIER scheduled meeting in ``events``
    (point in time; at least 8), notional = pos x d_ref / IEF duration known at entry."""
    ev = sorted(events, key=lambda e: e["day"])
    hist = []
    for e in ev:
        sd = float(np.std(hist, ddof=1)) if len(hist) >= 8 else None
        if sd and sd > 0 and e.get("dur") and e["dur"] > 0 and f"r{T584_H}" in e:
            e["pos"] = float(np.clip(-e["s"] / sd, -cap, cap))
            e["capped"] = abs(e["s"] / sd) > cap
            e["notional"] = e["pos"] * d_ref / e["dur"]
        hist.append(e["s"])


def _slope_nw1(s, y) -> dict:
    r = ols_hac(y, s, 1)
    return {"slope": r["coef"][1], "t": r["t"][1], "n": r["n"]} if r["coef"] else {"slope": None, "t": None, "n": r["n"]}


def meeting_boot(s, y, n_boot: int, seed: int) -> tuple:
    """Studentized i.i.d. bootstrap over meetings of the OLS slope (NW lag-1 s.e. on each resample): (p_greater, p_less)."""
    return boot_coef_t(y, s, 0, 1, 1.0, n_boot, seed)


def perm_slope(s, y, n_perm: int, seed: int) -> tuple:
    """Permutation of s across meetings: (p_greater, p_less) of the OLS slope."""
    s, y = np.asarray(s, float), np.asarray(y, float)
    sc, yc = s - s.mean(), y - y.mean()
    obs = float(sc @ yc)
    rng = np.random.default_rng(seed)
    draws, done = [], 0
    while done < n_perm:
        k = min(2000, n_perm - done)
        idx = np.argsort(rng.random((k, s.size)), axis=1)
        draws.append(sc[idx] @ yc)
        done += k
    d = np.concatenate(draws)
    return float((np.sum(d >= obs - 1e-15) + 1) / (d.size + 1)), float((np.sum(d <= obs + 1e-15) + 1) / (d.size + 1))


def fomc_drift_test(events: list, start: str = T584_START, end: str = T584_END, split: str = T584_SPLIT,
                    n_draws: int = N_DRAWS, seed: int = SEED, min_n: int = T584_MIN_N) -> dict:
    """T-584 primary over the scheduled meetings in [start, end] with a complete 20-session hold."""
    H = T584_H
    E = [e for e in events if start <= e["day"] <= end and f"y{H}" in e]
    n_all = len(E)
    nz = [e for e in E if e["dff_prev"] is not None and e["dff_prev"] > T584_ZLB]
    n = len(nz)
    out = {"n_meetings": n_all, "n_outside_zlb": n, "n_zlb": n_all - n}
    if n_all < 8:
        out["criteria"] = [("enough scheduled holdout meetings with a complete hold", None)]
        return out
    s = np.array([e["s"] for e in E]) * 100.0                       # bps
    y = np.array([e[f"y{H}"] for e in E]) * 100.0
    full = _slope_nw1(s, y)
    nb = max(1, n_draws // N_BOOT)
    bpg, bpl, bdr = CAL.escalate_p(lambda k: meeting_boot(s, y, N_BOOT, seed + k), N_BOOT, nb, CAL.MAX_SEEDS)
    ppg, ppl, pdr = CAL.escalate_p(lambda k: perm_slope(s, y, n_draws, seed + k), n_draws, 1, CAL.MAX_PERM_BATCHES)
    halves = {}
    for lab, m in (("first", np.array([e["day"] < split for e in E])), ("second", np.array([e["day"] >= split for e in E]))):
        halves[lab] = _slope_nw1(s[m], y[m]) if m.sum() >= 4 else {"slope": None, "t": None, "n": int(m.sum())}
    T = [e for e in E if "notional" in e]
    pnl = np.array([e["notional"] * e[f"r{H}"] - T584_COST * abs(e["notional"]) for e in T])
    pnl_x = np.array([e["notional"] * (e[f"r{H}"] - e[f"bill{H}"]) - T584_COST * abs(e["notional"]) for e in T])
    out.update(slope_bps_per_bp=full["slope"], t_nw1=full["t"], boot_p_greater=bpg, boot_p_less=bpl, boot_draws=bdr,
               perm_p_greater=ppg, perm_p_less=ppl, perm_draws=pdr, halves=halves, n_trades=int(len(T)),
               trade_mean_net=float(pnl.mean()) if len(T) else None, trade_mean_net_excess=float(pnl_x.mean()) if len(T) else None,
               trade_ci=CAL.mean_ci(pnl, 1, N_BOOT, seed) if len(T) >= 2 else [None, None],
               n_capped=int(sum(1 for e in T if e.get("capped"))), first=E[0]["day"], last=E[-1]["day"])
    c_sig = (False if not full["slope"] > 0 else
             CAL._agree([CAL.decide_p(bpg, bdr), CAL.decide_p(ppg, pdr)]))
    dec_sig = CAL.decide_p(bpl, bdr) is True and CAL.decide_p(ppl, pdr) is True
    c_h = [None if h["slope"] is None else h["slope"] > 0 for h in halves.values()]
    c_tr = CAL._agree([None if out["trade_mean_net"] is None else out["trade_mean_net"] > 0,
                       None if out["trade_mean_net_excess"] is None else out["trade_mean_net_excess"] > 0])
    rows = [("slope > 0 with one-sided p < 0.05 under the studentized meeting bootstrap AND the permutation of s", c_sig, dec_sig),
            (f"slope > 0 in {start[:7]}..2017-12", c_h[0], False),
            (f"slope > 0 in {split[:7]}..{end[:7]}", c_h[1], False),
            ("proportional IEF trade mean net of 2 bps a round trip > 0 (raw IEF return and excess over bills, both)", c_tr, False)]
    crit = [(nm, ok) for nm, ok, _ in CAL._undecided(rows)]
    if n < min_n:
        crit.append(((f">= {min_n} scheduled holdout meetings outside the ZLB (DFF > {T584_ZLB}%): {n} (the trial: with fewer "
                      "the verdict is inconclusive)"), None))
        v, why = CAL._verdict(crit)
        if v != "inconclusive":
            v, why = "inconclusive", f"only {n} meetings outside the ZLB, below the trial's {min_n}: inconclusive by the trial's rule ({why})"
    else:
        v, why = CAL._verdict(crit)
    out.update(criteria=[[c, ok] for c, ok in crit], verdict=v, why=why)
    return out


def fomc_reported(events: list) -> dict:
    """Reported: 10- and 50-session horizons, DGS2 surprise, the 1994-2008 in-paper replication, positive / negative s,
    outside-ZLB only, month-ends and CPI days in the holds."""
    out = {}
    hold = [e for e in events if T584_START <= e["day"] <= T584_END]
    for h, lag in ((10, 1), (50, 2)):
        E = [e for e in hold if f"y{h}" in e]
        if len(E) >= 8:
            r = ols_hac(np.array([e[f"y{h}"] for e in E]) * 100, np.array([e["s"] for e in E]) * 100, lag)
            out[f"h{h}"] = {"n": len(E), "slope": r["coef"][1], "t": r["t"][1], "lag": lag}
    E = [e for e in hold if f"y{T584_H}" in e]
    E2 = [e for e in E if e.get("s2") is not None]
    if len(E2) >= 8:
        out["dgs2_surprise"] = _slope_nw1(np.array([e["s2"] for e in E2]) * 100, np.array([e[f"y{T584_H}"] for e in E2]) * 100)
    P = [e for e in events if T584_PAPER[0] <= e["day"] <= T584_PAPER[1] and f"y{T584_H}" in e]
    if len(P) >= 8:
        out["in_paper_1994_2008"] = _slope_nw1(np.array([e["s"] for e in P]) * 100, np.array([e[f"y{T584_H}"] for e in P]) * 100)
    for lab, f in (("positive_s", lambda e: e["s"] > 0), ("negative_s", lambda e: e["s"] < 0)):
        G = [e for e in E if f(e)]
        out[lab] = {"n": len(G), "mean_dy_bps": float(np.mean([e[f"y{T584_H}"] for e in G]) * 100) if G else None,
                    **({k: v for k, v in _slope_nw1(np.array([e["s"] for e in G]) * 100,
                                                    np.array([e[f"y{T584_H}"] for e in G]) * 100).items() if k != "n"} if len(G) >= 4 else {})}
    NZ = [e for e in E if e["dff_prev"] is not None and e["dff_prev"] > T584_ZLB]
    if len(NZ) >= 8:
        out["outside_zlb_only"] = _slope_nw1(np.array([e["s"] for e in NZ]) * 100, np.array([e[f"y{T584_H}"] for e in NZ]) * 100)
    if E:
        out["month_ends_in_hold_mean"] = float(np.mean([e.get("month_ends_in_hold", 0) for e in E]))
        out["cpi_days_in_hold_mean"] = float(np.mean([e.get("cpi_in_hold", 0) for e in E]))
        out["holds_without_cpi"] = int(sum(1 for e in E if e.get("cpi_in_hold", 0) == 0))
    return out


def b13_calendar_b_post_fomc_drift(archive):
    """T-584: post-FOMC drift in DGS10 after the statement-day 3-month bill surprise, scheduled meetings 2008-11..2026-10."""
    miss = _missing(archive, [FOMC_B, DTB3_B, DGS2_B, DGS10_B, DFF_B, IEF_B, SPY_B])
    if miss:
        return miss
    sdays, _ = CAL._daily(archive, SPY_B)                  # the NYSE session calendar (IEF starts 2002-07-30)
    idays, iadj = CAL._daily(archive, IEF_B)
    at = {d: v for d, v in zip(idays, iadj)}
    ief = np.array([at.get(d, np.nan) for d in sdays])
    meetings = fomc_scheduled(CAL._rows(archive, FOMC_B))
    cpi = [r["value"]["day"] for r in CAL._rows(archive, CPI_B)] if B7C._has(archive, CPI_B) else []
    ev = fomc_events(meetings, sdays, ief, CAL._series(archive, DTB3_B), CAL._series(archive, DGS10_B),
                     CAL._series(archive, DGS2_B), CAL._series(archive, DFF_B), cpi)
    size_positions(ev)
    rep = fomc_drift_test(ev)
    if "verdict" not in rep:
        return _out(rep, rep.get("n_outside_zlb", 0), "inconclusive", "too few scheduled holdout meetings with a complete hold (rule 9)")
    rep["reported"] = rp = fomc_reported(ev)
    h = rep["halves"]

    def sl(d, k="slope"):
        return "n/a" if not d or d.get(k) is None else f"{d[k]:+.3f}"
    reason = (f"{rep['n_meetings']} scheduled meetings {rep['first']}..{rep['last']} ({rep['n_outside_zlb']} outside the ZLB, DFF > "
              f"{T584_ZLB}%): slope of dDGS10(t+2 -> t+22) on s = dDTB3(t) {sl(rep, 'slope_bps_per_bp')} bp per bp (NW-1 t "
              f"{_f(rep['t_nw1'], 2)}), meeting-bootstrap p {_mc(rep['boot_p_greater'], rep['boot_draws'])}, permutation p "
              f"{_mc(rep['perm_p_greater'], rep['perm_draws'])}; halves {sl(h['first'])} (n {h['first']['n']}) / {sl(h['second'])} "
              f"(n {h['second']['n']}); proportional IEF trade ({rep['n_trades']} meetings, {rep['n_capped']} capped) mean net "
              f"{_bp(rep['trade_mean_net'])} bps per meeting per unit position (excess over bills {_bp(rep['trade_mean_net_excess'])}, "
              f"95% CI {CAL._ci_bps(rep['trade_ci'])}); reported: 10-session slope {sl(rp.get('h10'))}, 50-session {sl(rp.get('h50'))} "
              f"(t {_f(rp.get('h50', {}).get('t'), 2)}), DGS2 surprise {sl(rp.get('dgs2_surprise'))} (t {_f(rp.get('dgs2_surprise', {}).get('t'), 2)}), "
              f"outside-ZLB only {sl(rp.get('outside_zlb_only'))} (t {_f(rp.get('outside_zlb_only', {}).get('t'), 2)}), in-paper 1994-2008 "
              f"{sl(rp.get('in_paper_1994_2008'))} (t {_f(rp.get('in_paper_1994_2008', {}).get('t'), 2)}, n "
              f"{rp.get('in_paper_1994_2008', {}).get('n', 'n/a')}); s > 0: {rp['positive_s']['n']} meetings, mean dy "
              f"{_f(rp['positive_s']['mean_dy_bps'], 2)} bps; s < 0: {rp['negative_s']['n']}, {_f(rp['negative_s']['mean_dy_bps'], 2)} bps; "
              f"holds carry {rp.get('month_ends_in_hold_mean', 0):.2f} month-ends and {rp.get('cpi_days_in_hold_mean', 0):.2f} CPI days on average")
    return _out(rep, rep["n_outside_zlb"], rep["verdict"], reason + " — " + rep["why"])


# ======================================================================================= T-585 dash for cash ==

def era_of(day: str) -> Optional[str]:
    for k, (a, b) in T585_ERAS.items():
        if a <= day <= b:
            return k
    return None


def month_end_panel(days: Sequence[str], closes) -> list:
    """Per complete month: the dates and returns of sessions T-3, T-2, T-1, T (T = the month's last session; r(T-j) the
    close-to-close return ending on that session) and whether the month's last five sessions are those of the calendar as
    scheduled in advance (False when an unscheduled closure moved them: the month is dropped)."""
    days = list(days)
    c = np.asarray(closes, float)
    _, _, comp = month_positions(days)
    by = defaultdict(list)
    for i, d in enumerate(days):
        by[d[:7]].append(i)
    out = []
    for m in sorted(by):
        idx = by[m]
        if not comp[idx[0]] or len(idx) < 6 or idx[0] == 0:
            continue
        last5 = [days[i] for i in idx[-5:]]
        sched = _rule_sessions(int(m[:4]), int(m[5:7]), with_unscheduled=False)[-5:]
        row = {"month": m, "sched_ok": last5 == sched}
        for j in range(4):
            i = idx[-1 - j]
            row[f"d{j}"] = days[i]
            row[f"r{j}"] = float(c[i] / c[i - 1] - 1)
        row["era"] = era_of(row["d3"]) if era_of(row["d3"]) == era_of(row["d2"]) else None
        out.append(row)
    return out


def _rowcorr(X, Y) -> np.ndarray:
    X = X - X.mean(axis=1, keepdims=True)
    Y = Y - Y.mean(axis=1, keepdims=True)
    den = np.sqrt((X * X).sum(axis=1) * (Y * Y).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return (X * Y).sum(axis=1) / den


def _corr(x, y, spearman: bool = False) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if spearman:
        from scipy.stats import rankdata
        x, y = rankdata(x), rankdata(y)
    return float(np.corrcoef(x, y)[0, 1])


def boot_rho_diff(x_new, y_new, x_old, y_old, n_boot: int, seed: int, spearman: bool = False) -> np.ndarray:
    """Month bootstrap within regime: draws of rho(new) - rho(old), months resampled with replacement in each regime."""
    rng = np.random.default_rng(seed)
    xs = [np.asarray(v, float) for v in (x_new, y_new, x_old, y_old)]
    out, done = [], 0
    while done < n_boot:
        k = min(2000, n_boot - done)
        i1 = rng.integers(0, xs[0].size, (k, xs[0].size))
        i0 = rng.integers(0, xs[2].size, (k, xs[2].size))
        A1, B1, A0, B0 = xs[0][i1], xs[1][i1], xs[2][i0], xs[3][i0]
        if spearman:
            from scipy.stats import rankdata
            A1, B1, A0, B0 = (rankdata(M, axis=1) for M in (A1, B1, A0, B0))
        out.append(_rowcorr(A1, B1) - _rowcorr(A0, B0))
        done += k
    d = np.concatenate(out)
    return d[np.isfinite(d)]


def perm_rho_diff(x, y, new, n_perm: int, seed: int) -> np.ndarray:
    """Permutation of the regime labels across the pooled months: draws of rho(new) - rho(old) (group sizes kept)."""
    x, y, new = np.asarray(x, float), np.asarray(y, float), np.asarray(new, bool)
    n, n1 = x.size, int(new.sum())
    n0 = n - n1
    rng = np.random.default_rng(seed)
    tot = [x.sum(), y.sum(), (x * x).sum(), (y * y).sum(), (x * y).sum()]
    out, done = [], 0

    def corr(sx, sy, sxx, syy, sxy, m):
        with np.errstate(invalid="ignore", divide="ignore"):
            return (sxy - sx * sy / m) / np.sqrt((sxx - sx * sx / m) * (syy - sy * sy / m))
    while done < n_perm:
        k = min(2000, n_perm - done)
        M = np.zeros((k, n))
        sel = np.argsort(rng.random((k, n)), axis=1)[:, :n1]
        np.put_along_axis(M, sel, 1.0, axis=1)
        s = [M @ x, M @ y, M @ (x * x), M @ (y * y), M @ (x * y)]
        r1 = corr(*s, n1)
        r0 = corr(*[t - v for t, v in zip(tot, s)], n0)
        out.append(r1 - r0)
        done += k
    d = np.concatenate(out)
    return d[np.isfinite(d)]


def rho_test(panel: list, new: str = "T+2", old: str = "T+3", a: str = "r3", b: str = "r2", n_draws: int = N_DRAWS,
             seed: int = SEED, keep=None, escalate: bool = True) -> dict:
    """rho(new) - rho(old) of the pair (a, b) across months, with the month bootstrap within regime and the regime-label
    permutation: one-sided p's (p_less tests H0 difference >= 0), each escalated while undecided."""
    rows = [r for r in panel if r["sched_ok"] and (keep is None or keep(r))]
    N = [r for r in rows if r["era"] == new]
    O = [r for r in rows if r["era"] == old]
    out = {"n_new": len(N), "n_old": len(O)}
    if len(N) < 8 or len(O) < 8:
        return out
    xn, yn = np.array([r[a] for r in N]), np.array([r[b] for r in N])
    xo, yo = np.array([r[a] for r in O]), np.array([r[b] for r in O])
    rn, ro = _corr(xn, yn), _corr(xo, yo)
    obs = rn - ro

    def bb(k):
        d = boot_rho_diff(xn, yn, xo, yo, n_draws, seed + k)
        return float((np.sum(d <= 0) + 1) / (d.size + 1)), float((np.sum(d >= 0) + 1) / (d.size + 1))

    xa, ya = np.concatenate([xn, xo]), np.concatenate([yn, yo])
    lab = np.r_[np.ones(len(N), bool), np.zeros(len(O), bool)]

    def pb(k):
        d = perm_rho_diff(xa, ya, lab, n_draws, seed + 100 + k)
        return float((np.sum(d >= obs - 1e-15) + 1) / (d.size + 1)), float((np.sum(d <= obs + 1e-15) + 1) / (d.size + 1))

    cap = CAL.MAX_PERM_BATCHES if escalate else 1
    bpg, bpl, bdr = CAL.escalate_p(bb, n_draws, 1, cap)
    ppg, ppl, pdr = CAL.escalate_p(pb, n_draws, 1, cap)
    out.update(rho_new=rn, rho_old=ro, diff=obs, boot_p_greater=bpg, boot_p_less=bpl, boot_draws=bdr,
               perm_p_greater=ppg, perm_p_less=ppl, perm_draws=pdr,
               spearman_new=_corr(xn, yn, True), spearman_old=_corr(xo, yo, True),
               mean_a_new=float(xn.mean()), mean_a_old=float(xo.mean()))
    out["spearman_diff"] = out["spearman_new"] - out["spearman_old"]
    return out


def _flag_days(panel: list, fomc: set, cpi: set, exdiv: set) -> None:
    for r in panel:
        hit = {r["d3"], r["d2"]}
        r["event"] = bool(hit & fomc or hit & cpi or hit & exdiv)


def b13_calendar_b_dash_for_cash(archive):
    """T-585: the cross-month correlation of SPY's r(T-3) and r(T-2) is lower in the T+2 era than in the T+3 era."""
    miss = _missing(archive, [SPY_B, IWM_B, IEF_B, FOMC_B, CPI_B])
    if miss:
        return miss
    days, close = CAL._daily(archive, SPY_B, "close")
    _, adj = CAL._daily(archive, SPY_B)
    exdiv = {d for d, x in zip(days, ex_dividends(close, adj)) if x > 0}
    fomc = set(fomc_scheduled(CAL._rows(archive, FOMC_B)))
    cpi = {r["value"]["day"] for r in CAL._rows(archive, CPI_B)}
    panels = {}
    for sym, bname in (("SPY", SPY_B), ("IWM", IWM_B), ("IEF", IEF_B)):
        d, c = CAL._daily(archive, bname)
        panels[sym] = month_end_panel(d, c)
        _flag_days(panels[sym], fomc, cpi, exdiv)
    spy = rho_test(panels["SPY"])
    n = spy.get("n_new", 0)
    if "diff" not in spy:
        return _out({"spy": spy}, n, "inconclusive", f"too few months in a regime (T+2 {spy.get('n_new')}, T+3 {spy.get('n_old')}) (rule 9)")
    iwm, ief = rho_test(panels["IWM"]), rho_test(panels["IEF"])
    rep = {"spy": spy, "iwm": iwm, "ief": ief,
           "dropped_unscheduled_closure_months": [r["month"] for r in panels["SPY"] if not r["sched_ok"]],
           "regimes": T585_ERAS}
    holm = CAL._holm({"SPY": spy["perm_p_less"], "IWM": iwm.get("perm_p_less")})
    rep["holm_perm_p_less"] = holm
    # reported arms (no escalation)
    rep["t3_in_paper_1995_2013"] = rho_test(panels["SPY"], keep=lambda r: r["era"] != "T+3" or r["month"] <= T585_IN_PAPER_END, escalate=False)
    rep["t3_2014_2017_only"] = rho_test(panels["SPY"], keep=lambda r: r["era"] != "T+3" or r["month"] > T585_IN_PAPER_END, escalate=False)
    rep["drop_event_months"] = rho_test(panels["SPY"], keep=lambda r: not r["event"], escalate=False)
    rep["drop_2020_03"] = rho_test(panels["SPY"], keep=lambda r: r["month"] != "2020-03", escalate=False)
    rep["fwd_t1_vs_t2_pair_T2_T1"] = rho_test(panels["SPY"], new="T+1", old="T+2", a="r2", b="r1", escalate=False)
    rep["fwd_t1_vs_t2_pair_T3_T2"] = rho_test(panels["SPY"], new="T+1", old="T+2", escalate=False)
    c1 = False if not spy["diff"] < 0 else CAL._agree([CAL.decide_p(spy["boot_p_less"], spy["boot_draws"]),
                                                        CAL.decide_p(spy["perm_p_less"], spy["perm_draws"])])
    d1 = CAL.decide_p(spy["boot_p_greater"], spy["boot_draws"]) is True and CAL.decide_p(spy["perm_p_greater"], spy["perm_draws"]) is True
    c2 = None if "diff" not in iwm else iwm["diff"] < 0
    if "diff" in ief:
        sig = [CAL.decide_p(min(ief["boot_p_less"], ief["boot_p_greater"]), ief["boot_draws"]),
               CAL.decide_p(min(ief["perm_p_less"], ief["perm_p_greater"]), ief["perm_draws"])]
        c3 = CAL._agree([None if s is None else not s for s in sig])
        ief["two_sided_boot_p"] = min(1.0, 2 * min(ief["boot_p_less"], ief["boot_p_greater"]))
        ief["two_sided_perm_p"] = min(1.0, 2 * min(ief["perm_p_less"], ief["perm_p_greater"]))
    else:
        c3 = None
    sec = spy["mean_a_new"] - spy["mean_a_old"]
    rep["t3_mean_diff"] = sec
    rows = [(("SPY rho(T+2) - rho(T+3) < 0 with one-sided p < 0.05 under the month bootstrap within regime AND the "
              "regime-label permutation"), c1, d1),
            ("IWM the same sign (rho difference < 0)", c2, False),
            ("IEF difference not significant (two-sided p > 0.1 under both nulls)", c3, False),
            ("mean r(T-3) in the T+2 era minus the T+3 era < 0", sec < 0, False)]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T585_MIN_N, "T+2-era months")
    rep.update(criteria=[[c, ok] for c, ok in crit], verdict=v)

    def rr(t, lab):
        if "diff" not in t:
            return f"{lab}: n/a (T+2 {t.get('n_new')} / T+3 {t.get('n_old')} months)"
        return (f"{lab}: rho T+2 {t['rho_new']:+.3f} ({t['n_new']} months) vs T+3 {t['rho_old']:+.3f} ({t['n_old']}), difference "
                f"{t['diff']:+.3f}, bootstrap p {_mc(t['boot_p_less'], t['boot_draws'])}, permutation p {_mc(t['perm_p_less'], t['perm_draws'])}, "
                f"Spearman difference {t['spearman_diff']:+.3f}")
    fw = rep["fwd_t1_vs_t2_pair_T2_T1"]
    reason = (rr(spy, "SPY") + "; " + rr(iwm, "IWM") + "; " + rr(ief, "IEF (no-shift control)")
              + (f" (two-sided p {ief.get('two_sided_boot_p', float('nan')):.3f} / {ief.get('two_sided_perm_p', float('nan')):.3f})" if "diff" in ief else "")
              + f"; SPY mean r(T-3) T+2 {_bp(spy['mean_a_new'])} vs T+3 {_bp(spy['mean_a_old'])} bps (difference {_bp(sec)}); reported: "
              f"T+3 in-paper 1995-2013 only, difference {_f(rep['t3_in_paper_1995_2013'].get('diff'))}; T+3 2014-2017 only "
              f"{_f(rep['t3_2014_2017_only'].get('diff'))} ({rep['t3_2014_2017_only'].get('n_old')} months); months with FOMC/CPI/ex-dividend on "
              f"T-3 or T-2 dropped {_f(rep['drop_event_months'].get('diff'))}; without 2020-03 {_f(rep['drop_2020_03'].get('diff'))}; forward "
              f"T+1 era ({fw.get('n_new')} months) rho(T-2, T-1) {_f(fw.get('rho_new'))} vs T+2 {_f(fw.get('rho_old'))}; dropped for an "
              f"unscheduled closure in the last five sessions: {', '.join(rep['dropped_unscheduled_closure_months']) or 'none'}; "
              "regime dates are the SEC compliance dates (T+3 Rule 15c6-1 from 1995-06-07, T+2 34-80295 from 2017-09-05, T+1 "
              "34-96930 from 2024-05-28); SPY ex-dividend days recovered from the adjclose/close factor (daily-events-SPY is not archived)")
    return _out(rep, n, v, reason + " — " + why)


# ======================================================================================= T-590 payday 16th ==

def payday_flags(days: Sequence[str]) -> np.ndarray:
    """The first session on or after the 16th of each month (calendar only: no price enters)."""
    f = np.zeros(len(days), bool)
    seen = set()
    for i, d in enumerate(days):
        if int(d[8:10]) >= 16 and d[:7] not in seen:
            seen.add(d[:7])
            f[i] = True
    return f


def third_friday_session(y: int, m: int) -> str:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7 + 14)
    while not CAL.is_nyse_session(d):
        d -= timedelta(days=1)
    return d.isoformat()


def payday_sample(days: Sequence[str], closes, start: str = T590_START, end: str = T590_END) -> tuple:
    """(return days, returns, 16th flags, excluded-16th count) on the sessions in [start, end] of complete months
    outside T-59's window; a return is close(prev session) -> close(session)."""
    days = list(days)
    c = np.asarray(closes, float)
    fs, fe, comp = month_positions(days)
    tom = (fs <= 3) | (fe <= 4)
    f16 = payday_flags(days)
    keep = np.array([i > 0 and start <= days[i] <= end and comp[i] and not tom[i] for i in range(len(days))])
    excl = int(np.sum(f16 & tom & np.array([start <= d <= end for d in days])))
    r = np.zeros(len(days)); r[1:] = c[1:] / c[:-1] - 1
    ds = np.array(days)[keep]
    return ds, r[keep], f16[keep], excl


def payday_stats(ds, x, f, bar: float = T590_BAR, cost: float = T590_COST, block: int = T590_BLOCK, n_boot: int = N_BOOT,
                 seed: int = SEED, n_seeds: int = CAL.N_SEEDS, split: str = T590_SPLIT, post: str = T590_POST) -> dict:
    """Gross and net (gross - cost) 16th-minus-other difference; p (H0 net <= bar) and p0 (H0 net <= 0) from the
    studentized circular block bootstrap of the flagged series; halves and the post-publication subsample (net)."""
    x, f = np.asarray(x, float), np.asarray(f, bool)
    ds = np.asarray(ds)
    out = {"n16": int(f.sum()), "n_other": int((~f).sum())}
    if f.sum() < 4 or (~f).sum() < 4:
        return out
    gross = float(x[f].mean() - x[~f].mean())
    d = CAL.flag_diff_series(x, f) - cost
    pg, pl, dr = CAL.studentized_p_escalated(d - bar, block, n_boot, seed, n_seeds)
    p0g, p0l, d0 = CAL.studentized_p_escalated(d, block, n_boot, seed, n_seeds)
    sub = {}
    for lab, m in (("first_half", ds < split), ("second_half", ds >= split), ("post_publication", ds >= post)):
        sub[lab] = (float(x[m & f].mean() - x[m & ~f].mean() - cost) if (m & f).sum() and (m & ~f).sum() else None, int((m & f).sum()))
    out.update(gross=gross, net=gross - cost, mean16=float(x[f].mean()), mean_other=float(x[~f].mean()),
               p_bar=pg, p_bar_less=pl, draws_bar=dr, p0=p0g, p0_less=p0l, draws0=d0, ci_net=CAL.mean_ci(d, block, n_boot, seed),
               sub=sub, first=str(ds[0]), last=str(ds[-1]))
    return out


def payday_dummies(ds, x, f, opex: set, cpi: set, fomc: set) -> dict:
    """Reported: overlaps of 16th sessions with OPEX Fridays, CPI days and FOMC statement days; the 16th coefficient in a
    dummy regression (HAC); the difference with overlapping 16th sessions left out."""
    ds = list(ds)
    x, f = np.asarray(x, float), np.asarray(f, bool)
    D = {k: np.array([d in s for d in ds], float) for k, s in (("opex", opex), ("cpi", cpi), ("fomc", fomc))}
    ov = {k: int((v.astype(bool) & f).sum()) for k, v in D.items()}
    X = np.column_stack([f.astype(float), D["opex"], D["cpi"], D["fomc"]])
    r = ols_hac(x, X, CAL.nw_lags(len(x)))
    any_ov = np.zeros(len(x), bool)
    for v in D.values():
        any_ov |= v.astype(bool)
    keep = ~(f & any_ov)
    clean = float(x[keep & f].mean() - x[keep & ~f].mean()) if (keep & f).sum() else None
    return {"overlaps": ov, "coef_16th": r["coef"][1] if r["coef"] else None, "t_16th": r["t"][1] if r["coef"] else None,
            "diff_without_overlapping_16ths": clean, "n16_clean": int((keep & f).sum())}


def b13_calendar_b_payday_16th(archive):
    """T-590: SPY's 16th-session return minus the other non-turn-of-month sessions > 2 bps, 2011-01..2026-10."""
    miss = _missing(archive, [SPY_B, IWM_B, QQQ_B, CPI_B, FOMC_B])
    if miss:
        return miss
    res = {}
    for sym, bname in (("SPY", SPY_B), ("IWM", IWM_B), ("QQQ", QQQ_B)):
        d, c = CAL._daily(archive, bname)
        ds, x, f, excl = payday_sample(d, c)
        res[sym] = payday_stats(ds, x, f)
        res[sym]["excluded_16ths_in_tom"] = excl
        if sym == "SPY":
            spy_sample = (ds, x, f)
    S = res["SPY"]
    n = S.get("n16", 0)
    if "gross" not in S:
        return _out(res, n, "inconclusive", "too few 16th sessions (rule 9)")
    ds, x, f = spy_sample
    yrs = range(int(ds[0][:4]), int(ds[-1][:4]) + 1)
    opex = {third_friday_session(y, m) for y in yrs for m in range(1, 13)}
    cpi = {r["value"]["day"] for r in CAL._rows(archive, CPI_B)}
    fomc = set(fomc_scheduled(CAL._rows(archive, FOMC_B)))
    res["dummies"] = dm = payday_dummies(ds, x, f, opex, cpi, fomc)
    holm = CAL._holm({k: res[k].get("p0") for k in ("IWM", "QQQ")})
    res["holm_secondary_p"] = holm
    c1 = False if not S["net"] > T590_BAR else CAL.decide_p(S["p_bar"], S["draws_bar"])
    d1 = CAL.decide_p(S["p_bar_less"], S["draws_bar"]) is True
    h1, h2 = S["sub"]["first_half"][0], S["sub"]["second_half"][0]
    c2 = None if h1 is None or h2 is None else (h1 > 0 and h2 > 0)
    pp = S["sub"]["post_publication"][0]
    c3 = None if pp is None else pp > 0
    sec = []
    for k in ("IWM", "QQQ"):
        r = res[k]
        sec.append(None if "net" not in r else (False if not r["net"] > 0 else
                                                (None if holm[k] is None else CAL.decide_p(holm[k], r["draws0"]))))
    c4 = _both(sec)
    rows = [((f"SPY 16th-minus-other difference net of the 2 bp round trip > {T590_BAR * 1e4:.0f} bps with one-sided "
              f"p < 0.05 (studentized circular block bootstrap, {T590_BLOCK} sessions, 5 seeds escalated)"), c1, d1),
            ("both halves positive, net (2011-2018 / 2019-2026)", c2, False),
            ("2018-10..2026-10 mean difference > 0, net", c3, False),
            ("IWM and QQQ the same sign after Holm (net difference > 0 with Holm-adjusted one-sided p < 0.05, H0 net <= 0)", c4, False)]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T590_MIN_N, "16th sessions")
    res.update(criteria=[[c, ok] for c, ok in crit], verdict=v)

    def one(k):
        r = res[k]
        return (f"{k} 16th {_bp(r.get('mean16'))} vs other {_bp(r.get('mean_other'))} bps, gross {_bp(r.get('gross'))}, net "
                f"{_bp(r.get('net'))} (p net > 0 {_mc(r.get('p0'), r.get('draws0', 0))}, Holm {_f(holm.get(k), 4)})")
    reason = (f"SPY {S['first']}..{S['last']}, {S['n16']} 16th sessions vs {S['n_other']} other sessions outside T-59's -4..+3 window "
              f"({S['excluded_16ths_in_tom']} 16ths in the window excluded): 16th {_bp(S['mean16'])} vs other {_bp(S['mean_other'])} bps, "
              f"gross difference {_bp(S['gross'])}, net of 2 bps {_bp(S['net'])} bps (95% CI {CAL._ci_bps(S['ci_net'])}); p (H0 net <= 2 bps) "
              f"{_mc(S['p_bar'], S['draws_bar'])}; halves net {_bp(h1)} / {_bp(h2)} bps; 2018-10..2026-10 net {_bp(pp)} bps "
              f"({S['sub']['post_publication'][1]} sessions); " + one("IWM") + "; " + one("QQQ")
              + f"; reported: 16ths on OPEX Fridays {dm['overlaps']['opex']}, CPI days {dm['overlaps']['cpi']}, FOMC days "
              f"{dm['overlaps']['fomc']}; dummy-regression 16th coefficient {_bp(dm['coef_16th'])} bps (HAC t {_f(dm['t_16th'], 2)}); "
              f"without overlapping 16ths {_bp(dm['diff_without_overlapping_16ths'])} bps gross ({dm['n16_clean']} sessions); no other "
              "day of the month inspected")
    return _out(res, n, v, reason + " — " + why)


HARNESSES = {"b13_calendar_b_threshold_rebalancing": b13_calendar_b_threshold_rebalancing,
             "b13_calendar_b_post_fomc_drift": b13_calendar_b_post_fomc_drift,
             "b13_calendar_b_dash_for_cash": b13_calendar_b_dash_for_cash,
             "b13_calendar_b_payday_16th": b13_calendar_b_payday_16th}
THEORY_MAP = {"T-586": "b13_calendar_b_threshold_rebalancing", "T-584": "b13_calendar_b_post_fomc_drift",
              "T-585": "b13_calendar_b_dash_for_cash", "T-590": "b13_calendar_b_payday_16th"}
