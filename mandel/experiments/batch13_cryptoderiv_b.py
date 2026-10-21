"""
Batch 13, group ``cryptoderiv_b``: four claims from the 2026-10-20 web sweep (cluster "cryptoderiv"), pre-registered
before any run (T-616, T-607, T-615, T-610).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (MANDEL.md section 2, house rules 1-12):

  * T-616  BTC 30-DTE 25-delta risk reversal from T-257's daily smile fits (``batch6b_drb.daily_smiles``: the 07:00-09:00
           UTC Deribit trade sample, quadratic in ln(K/S)/sqrt(T) per expiry, ``rr30`` interpolation to 30 DTE), known
           at 09:00 UTC. z = (RR - mean) / sd over the fitted RR of the 90 calendar days before (t-90..t-1, >= 60 fits);
           a day without a fit takes the previous day's z (1-day fill), else it is skipped. Target y7 = ln(P(t+7) /
           P(t)), P = Coinbase close of the hourly bar starting 08:00 UTC (ending 09:00). Controls: trailing 7- and
           30-day log returns to P(t), DVOL close of the daily candle stamped t-1 (closed at t 00:00), mean
           interest_8h of the funding rows stamped in [t 09:00 - 7 d, t 09:00). Pooled all-start daily regression (rule
           10; Newey-West lag 14 = 2 x the hold) with the seven weekday grids reported. Pass: the 2022-01..2024-12 slope
           positive; full-window (2022-01..2026-10) controlled NW t >= 2 after deflation (Bonferroni over 6 trials: 2
           horizons x 2 statistics + T-257's 2 pass statistics); Campbell-Thompson out-of-sample R2 (2025-01..2026-10,
           expanding OLS of y7 on z over targets complete by the forecast time vs the expanding mean) > 0; and the long
           when z > +1 rule (10 bp per switch, flat earns 0) with a daily Sharpe above buy-and-hold in the out-of-sample
           window (the seven weekday tranches pooled as one book). Reported: 30-day horizon with Hansen-Hodrick t,
           butterfly z as a placebo regressor, the 10:00 entry, 50 bp stress, the IBIT (US-session) vehicle, per phase.
  * T-607  Weekly CMC Sunday top-500 snapshot (cmc-historical-listings; 2020-11-30 missing, a snapshot older than 8 days
           at entry never used) x Coinbase USD spot (every coinbase-daily-<PID>-USD bundle; T-424's stablecoin and
           wrapped/staked bases with BTC kept, as T-608, and the fx_stablecoin ids of coinbase-products-2026-10-15).
           Eligible: mean daily Coinbase dollar volume >= $1m over the 30 daily bars ending by the snapshot's day
           (columns S-30..S-1), a Monday bar to enter on, matched to the snapshot by symbol (the same-symbol CMC id
           nearest in price to the Coinbase close, within 25% in log). Quintiles by marketCap; weeks with < 15 eligible
           dropped. Entry/exit at the close of the Monday bar (Tuesday 00:00 UTC); cap weights fixed at entry and
           drifting; 50 bp per side on drift-adjusted turnover; a coin that never trades again exits at its last close
           -50%. Statistic: mean weekly net VW Q1 - BTC. Pass: one-sided 95% lower bound > 0 (studentized 8-week circular
           block bootstrap, 5,000 draws per seed, escalated), both halves positive (split 2022-11-17), DSR > 0.95 at 27
           trials (T-314's 24, T-546, the 2 weightings). min_n 300 weeks.
  * T-615  Combined USDT + USDC SplyCur (Coin Metrics, current vintage); spike on day s = daily increase with z > 2
           against the 180 prior days' increases, known at s+2 00:00 UTC. Drawdown day D = Coinbase BTC 3-day close-to-
           close log return at or below the 10th percentile of the 365 prior days. Event = a spike day s with a drawdown
           day D in s-2..s, entry at the open of the daily bar starting s+2 (the first 00:00 after both are known),
           de-overlapped with a 5-day refractory period; control = a drawdown day D with no spike on D..D+2, entered at
           D+4 00:00 (the first 00:00 after the absence is known). Statistic: event minus control mean BTC log return
           over 3 days (open of the entry bar to the close 72 h later). Pass: >= 30 events, a week-clustered one-sided
           95% lower bound of (event - control - 0.50%) > 0 (5,000 draws per batch, escalated), positive in both halves
           (2019-2021 / 2022-2026) and, the claim's own wording, a one-sided 95% lower bound > 0 in each half.
  * T-610  Coinbase BTC-USD 1-minute bars (start-stamped; a missing minute is carried forward and counted), full NYSE
           sessions only (rule calendar, no early closes), DST-aware via America/New_York. Signal = sign of ln(P(10:00) /
           P(09:30)), P(T) the close of the bar ending at T. Trade: open of the bar starting 15:30 ET to the close of the
           bar ending 16:00 ET in the signal's direction, 10 bp round trip. Cells: all sessions; sessions whose 09:30-
           10:00 volume is above the 2/3 quantile of the 60 prior sessions'. Pass (main window 2024-01..2026-10, at least
           one cell): one-sided 95% lower bound of the net mean > 0 after Bonferroni over 2 cells (studentized weekly
           circular block bootstrap, 5 sessions, 5,000 draws per seed, escalated against 0.025), the 2022-2023 mean net
           > 0, and the mean above the 95th percentile of 1,000 random-sign placebos. min_n 200 trades.

Conventions
  * Data: bundles through ``archive.load`` with rows available after the bundle's capture dropped. A missing bundle the
    pass depends on is inconclusive and named (rule 9); one that only a reported arm needs is reported as not archived.
  * Point in time (rules 4, 12): T-616 decides at 09:00 UTC from the 07:00-09:00 trade sample, hourly bars ending by
    09:00, the DVOL candle that closed at 00:00 and funding rows stamped before 09:00. T-607 sorts on the Sunday
    snapshot (stamped 23:59:59, available Monday 00:00) with volume from bars ending by Sunday 00:00 and enters at
    Tuesday 00:00. T-615's supply day s enters only from s+2 00:00 and the drawdown day D from D+1 00:00; deciles and
    sigmas use prior days only. T-610 decides at 10:00 ET from bars ending by then and enters at 15:30 ET; the volume
    tercile uses prior sessions only.
  * Rule 5: below min_n never supported; a failing criterion counts only when it fails decisively (``batch6c_cal._judge``).
    T-615's registration says fewer than 30 events is inconclusive, so below 30 no failure is decisive.
  * Rule 10: T-616 pools the seven weekday grids (daily all-start regression, seven-tranche rule book) and reports each;
    T-607's Tuesday rebalance is fixed by the Sunday snapshot, the other six entry days that keep the snapshot within
    8 days are reported (per-start range); T-615 and T-610 are event / session driven: no free phase.
  * Monte Carlo (rule 11): resampled p's decide only when their 95% MC band clears the threshold, escalated up to
    ``batch6c_cal.MAX_SEEDS`` (``escalate_p``).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timezone
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6b_drb as B6B
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_cryptovenue as CV
from mandel.experiments import batch6c_cryptoxs as XS
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch13_cryptoderiv_a as CDA
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.validation.backtest_eval import sharpe_ratio

UTC = timezone.utc
H = 3600
DAY = 86400
SEED = 0
ALPHA = 0.05
EPOCH_ORD = date(1970, 1, 1).toordinal()
_N = NormalDist()
WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


# =========================================================================================================== shared ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, names)


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _iso(o: int) -> str:
    return date.fromordinal(int(o)).isoformat()


def _utc0_ord(o) -> np.ndarray:
    """POSIX seconds of 00:00 UTC of ordinal day(s) ``o``."""
    return (np.asarray(o, np.int64) - EPOCH_ORD) * DAY


def _bp(x, nd: int = 2) -> str:
    return B7C._bp(x, nd)


def _pc(x, nd: int = 2) -> str:
    return B7C._pc(x, nd)


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _u(x, nd: int = 1) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def _tdefl(t: Optional[float]) -> str:
    """A deflated t for a reason line ('-inf' when the Bonferroni p caps at 1)."""
    if t is None:
        return "n/a"
    return "-inf (Bonferroni p capped at 1)" if t == -math.inf else f"{t:+.2f}"


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _sr(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std(ddof=1) > 0 else None


def _ols(y, X, lag: int, kernel: str = "bartlett") -> dict:
    """OLS of y on [1, X] (X's first column the regressor of interest) with a Bartlett (Newey-West) or uniform
    (Hansen-Hodrick) HAC standard error of that slope (``batch6c_cryptoxs.ols_kernel``)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    if y.size < X.shape[1] + 5:
        return {"n": int(y.size), "slope": None, "t": None, "se": None, "lag": int(lag), "kernel": kernel}
    o = XS.ols_kernel(y, X, lag, kernel)
    return {"n": o["n"], "slope": o["beta"], "t": o["t"], "se": o["se"], "lag": o["lag"], "kernel": kernel}


def bonferroni_t(t: Optional[float], m: int) -> Optional[float]:
    """Deflated t: the one-sided normal p of ``t`` multiplied by ``m`` (capped at 1), mapped back to a t."""
    if t is None or not np.isfinite(t):
        return None
    p = min(1.0, m * (1.0 - _N.cdf(t)))
    return -math.inf if p >= 1.0 else float(_N.inv_cdf(1.0 - p))


def _fomc_cpi(archive) -> tuple:
    """(FOMC decision days, CPI release days) when archived (scheduled in advance: usable ahead)."""
    fomc, cpi = set(), set()
    if B7C._has(archive, "fomc-meetings"):
        for r in CAL._rows(archive, "fomc-meetings"):
            v = r.get("value") or {}
            if v.get("decision_day") and not v.get("future"):
                fomc.add(v["decision_day"])
    if B7C._has(archive, "macro-release-cpi"):
        for r in CAL._rows(archive, "macro-release-cpi"):
            d = (r.get("value") or {}).get("day")
            if d:
                cpi.add(d)
    return fomc, cpi


# ========================================================================== T-616 BTC RR25 z -> 7-day BTC return ==

T616_TRADES = "deribit-option-trades-daily-BTC"
T616_DVOL = "deribit-dvol-BTC-history"
T616_FUND = "deribit-funding-BTC-PERPETUAL"
T616_H = "coinbase-hourly-BTC-USD"
T616_IBIT = "daily-history-IBIT"
T616_START, T616_END = "2022-01-01", "2026-10-31"
T616_FIT_END = "2024-12-31"
T616_OOS_START = "2025-01-01"
T616_ZWIN = 90                       # calendar days before the decision day
T616_ZMIN = 60                       # fitted days needed in the window
T616_HOLD = 7
T616_HOLD_REP = 30
T616_ZTHR = 1.0
T616_COST = 0.0010                   # per switch
T616_STRESS = 0.0050                 # per switch (Coinbase stress)
T616_T = 2.0
T616_TRIALS = 2 * 2 + 2              # 2 horizons x 2 statistics + T-257's 2 pass statistics (CI and hit rate)
T616_NW_POOLED = 2 * T616_HOLD       # pooled all-start daily regression (T-402's 2 x hold convention)
T616_HH_POOLED = T616_HOLD_REP - 1
T616_HH_WEEKLY = math.ceil(T616_HOLD_REP / 7) - 1
T616_MIN_N = 80
T616_DEC_H = 9
T616_CONTROLS = ("ret7", "ret30", "dvol", "fund")


def bf_at(fit: dict) -> Optional[float]:
    """25-delta butterfly of one expiry's smile: mean of the 25-delta call and put IVs minus the IV at K = S."""
    r = B6B.rr_at(fit)
    if r is None:
        return None
    return 0.5 * (r[1][1] + r[2][1]) - B6B.smile_iv(fit, fit["S"])


def interp_dte(pts: Sequence[tuple], target: float = 30.0) -> Optional[float]:
    """Linear in DTE between the nearest expiries on either side of ``target`` (``batch6b_drb.rr30``'s rule)."""
    below = [p for p in pts if p[0] <= target]
    above = [p for p in pts if p[0] >= target]
    if not below or not above:
        return None
    (d1, r1), (d2, r2) = max(below), min(above)
    return r1 if d2 == d1 else r1 + (r2 - r1) * (target - d1) / (d2 - d1)


def bf30(sm: dict, day: str, target: float = 30.0) -> Optional[float]:
    pts = []
    for e, f in sm["fits"].items():
        b = bf_at(f)
        if b is not None:
            pts.append((B6B._dte(day, e), b))
    return interp_dte(pts, target)


def _t616_smiles(archive) -> dict:
    """{day: (RR30, BF30)} from T-257's daily smile fits (the 07:00-09:00 UTC trade sample)."""
    def load():
        sm = B6B.daily_smiles(B6B._stream_values(archive, T616_TRADES, "option-trade"))
        return {d: (B6B.rr30(s, d), bf30(s, d)) for d, s in sm.items()}
    return CAL._cached(archive, ("b13cdb_t616_smiles",), load)


def trailing_z(series: dict, win: int = T616_ZWIN, min_obs: int = T616_ZMIN) -> dict:
    """{day: z} on the days with a value: (v_t - mean) / sd (ddof 1) of the values on days t-win..t-1 (calendar),
    at least ``min_obs`` of them. Uses earlier days only."""
    days = sorted(d for d, v in series.items() if v is not None and np.isfinite(v))
    if not days:
        return {}
    o = np.array([_ord(d) for d in days], np.int64)
    v = np.array([series[d] for d in days], float)
    out = {}
    for i, d in enumerate(days):
        lo = int(np.searchsorted(o, o[i] - win, side="left"))
        w = v[lo:i]
        if w.size >= min_obs:
            sd = float(w.std(ddof=1))
            if sd > 0:
                out[d] = float((v[i] - w.mean()) / sd)
    return out


def signal_at(zd: dict, fitdays: set, day: str) -> tuple:
    """(z, filled): the day's own z; a day without a fit takes the previous day's z (never more than 1 day back)."""
    if day in zd:
        return zd[day], False
    if day not in fitdays:
        prev = _iso(_ord(day) - 1)
        if prev in zd:
            return zd[prev], True
    return None, False


def hour_marks(ts: np.ndarray, cl: np.ndarray, o0: int, o1: int, hour: int) -> tuple:
    """(prices, stale) on ordinal days o0..o1 at ``hour``:00 UTC: the close of the hourly bar ending then (the latest
    earlier bar within 6 h for a no-trade hour, counted stale)."""
    t_end = _utc0_ord(np.arange(o0, o1 + 1)) + hour * H
    return CDA.mark_at(ts, cl, t_end)


def funding_means(fts_ms: np.ndarray, fv: np.ndarray, t_dec_s: np.ndarray, days: int = 7, min_share: float = 0.5) -> np.ndarray:
    """Mean interest_8h over the funding rows stamped in [t_dec - days, t_dec) (strictly before the decision); NaN with
    fewer than ``min_share`` of the hourly rows."""
    t_dec = np.asarray(t_dec_s, np.int64) * 1000
    cs = np.concatenate([[0.0], np.cumsum(fv)])
    lo = np.searchsorted(fts_ms, t_dec - days * DAY * 1000, side="left")
    hi = np.searchsorted(fts_ms, t_dec, side="left")
    n = hi - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (cs[hi] - cs[lo]) / n
    return np.where(n >= min_share * days * 24, m, np.nan)


def t616_table(zd: dict, bzd: dict, fitdays: set, ts: np.ndarray, cl: np.ndarray, dvol: dict, fts_ms: np.ndarray,
               fv: np.ndarray, first: str = T616_START, last: Optional[str] = None) -> dict:
    """Arrays over the decision days first..last: z (1-day fill), bf z, controls and the targets (NaN where missing)."""
    o_first = _ord(first)
    o_last = _ord(last) if last else int(ts[-1] // DAY + EPOCH_ORD)
    g0, g1 = o_first - T616_HOLD_REP - 2, o_last + T616_HOLD_REP + 2
    p9, st9 = hour_marks(ts, cl, g0, g1, T616_DEC_H)
    p10, _ = hour_marks(ts, cl, g0, g1, T616_DEC_H + 1)
    od = np.arange(o_first, o_last + 1)
    days = [_iso(o) for o in od]
    i = od - g0

    def lr(a, b):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.log(a / b)
    z, bz, filled = np.full(od.size, np.nan), np.full(od.size, np.nan), np.zeros(od.size, bool)
    for k, d in enumerate(days):
        zz, fl = signal_at(zd, fitdays, d)
        if zz is not None:
            z[k], filled[k] = zz, fl
        bb, _ = signal_at(bzd, fitdays, d)
        if bb is not None:
            bz[k] = bb
    dv = np.array([dvol.get(_iso(o - 1), np.nan) for o in od], float)
    t_dec = _utc0_ord(od) + T616_DEC_H * H
    fund = funding_means(fts_ms, fv, t_dec)
    tab = {"days": days, "ord": od, "wd": np.array([date.fromordinal(int(o)).weekday() for o in od]), "z": z, "bfz": bz,
           "filled": filled, "ret7": lr(p9[i], p9[i - 7]), "ret30": lr(p9[i], p9[i - 30]), "dvol": dv, "fund": fund,
           "y7": lr(p9[i + T616_HOLD], p9[i]), "y30": lr(p9[i + T616_HOLD_REP], p9[i]),
           "y7_10": lr(p10[i + T616_HOLD], p10[i]), "p9": p9[i], "p9_next": p9[i + 1], "stale": int(st9[i].sum()),
           "r7": p9[i + T616_HOLD] / p9[i] - 1.0}
    return tab


def _X(tab: dict, lead: str = "z", extra: Sequence[str] = ()) -> np.ndarray:
    return np.column_stack([tab[lead]] + [tab[c] for c in T616_CONTROLS] + [tab[c] for c in extra])


def oos_r2(ords: np.ndarray, y: np.ndarray, X: np.ndarray, oos: np.ndarray, hold: int = T616_HOLD,
           min_train: int = 52, restrict_sign: bool = False) -> dict:
    """Campbell-Thompson out-of-sample R2: at each out-of-sample row i, OLS of y on [1, X] over the rows whose target
    completed by row i's decision (ord_j + hold <= ord_i), forecast y_i, against the mean of the same training targets.
    ``restrict_sign``: a negative slope on X's first column is replaced by the mean forecast (reported reading)."""
    ords, y = np.asarray(ords), np.asarray(y, float)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    em, eb, n = 0.0, 0.0, 0
    for i in np.flatnonzero(oos):
        k = int(np.searchsorted(ords, ords[i] - hold, side="right"))
        if k < min_train:
            continue
        Xc = np.column_stack([np.ones(k), X[:k]])
        beta = np.linalg.lstsq(Xc, y[:k], rcond=None)[0]
        bench = float(y[:k].mean())
        pred = float(beta[0] + X[i] @ beta[1:])
        if restrict_sign and beta[1] < 0:
            pred = bench
        em += (y[i] - pred) ** 2
        eb += (y[i] - bench) ** 2
        n += 1
    return {"n": n, "r2": (1.0 - em / eb) if eb > 0 else None}


def tranche_rule(tab: dict, lo: str, hi: str, cost: float, thr: float = T616_ZTHR) -> dict:
    """The rule's seven weekday tranches pooled as one book over the 09:00 UTC daily grid: each tranche decides on its
    weekday (long when z > thr, flat otherwise, flat when z is unknown), holds 7 days, and pays ``cost`` x |position
    change| / 7 at its decision; daily return = mean tranche position x the 09:00-to-09:00 BTC return. Window: from the
    day all seven tranches are active to the last day every tranche's hold has completed. Buy-and-hold is charged
    nothing. Returns daily Sharpes and their difference."""
    days, od = tab["days"], tab["ord"]
    dec = np.array([lo <= d <= hi for d in days]) & np.isfinite(tab["r7"])
    r1 = tab["p9_next"] / tab["p9"] - 1.0
    first = int(od[dec].min()) + 6 if dec.any() else None
    last_dec = {w: int(od[dec & (tab["wd"] == w)].max()) for w in range(7) if (dec & (tab["wd"] == w)).any()}
    if first is None or len(last_dec) < 7:
        return {"n_days": 0, "diff": None}
    last = min(last_dec.values()) + 6
    pos = np.full((7, od.size), np.nan)
    cst = np.zeros(od.size)
    for w in range(7):
        prev = 0.0
        for k in np.flatnonzero(dec & (tab["wd"] == w)):
            p = 1.0 if np.isfinite(tab["z"][k]) and tab["z"][k] > thr else 0.0
            cst[k] += cost * abs(p - prev) / 7.0
            prev = p
            pos[w, k:k + 7] = p
    sel = (od >= first) & (od <= last) & np.isfinite(r1)
    P = np.nanmean(np.where(np.isfinite(pos[:, sel]), pos[:, sel], 0.0), axis=0)
    rule = P * r1[sel] - cst[sel]
    bh = r1[sel]
    sr_r, sr_b = _sr(rule), _sr(bh)
    return {"n_days": int(sel.sum()), "first": _iso(first), "last": _iso(last), "sr_rule": sr_r, "sr_bh": sr_b,
            "diff": None if sr_r is None or sr_b is None else sr_r - sr_b, "share_long": float(P.mean()) if P.size else None,
            "mean_rule": _mean(rule), "mean_bh": _mean(bh)}


def phase_rule(tab: dict, w: int, lo: str, hi: str, cost: float, thr: float = T616_ZTHR, rets=None) -> dict:
    """One weekday grid's weekly rule vs buy-and-hold (weekly Sharpes), ``rets`` overriding the weekly returns."""
    m = np.array([lo <= d <= hi for d in tab["days"]]) & (tab["wd"] == w) & np.isfinite(tab["r7"] if rets is None else rets)
    r = (tab["r7"] if rets is None else rets)[m]
    pos = np.where(np.isfinite(tab["z"][m]) & (tab["z"][m] > thr), 1.0, 0.0)
    prev = np.concatenate([[0.0], pos[:-1]])
    rule = pos * r - cost * np.abs(pos - prev)
    sr_r, sr_b = _sr(rule), _sr(r)
    return {"n": int(m.sum()), "diff": None if sr_r is None or sr_b is None else sr_r - sr_b, "sr_rule": sr_r, "sr_bh": sr_b,
            "share_long": float(pos.mean()) if pos.size else None}


def ibit_weekly(tab: dict, bars: dict) -> np.ndarray:
    """IBIT vehicle (reported): from the open of the first US session on or after the decision day (09:30 ET, after the
    09:00 UTC decision) to the open of the first session on or after the decision day + 7 (split/dividend-adjusted
    opens); NaN before IBIT lists."""
    bd = bars["days"]
    ao = bars["aopen"]
    out = np.full(len(tab["days"]), np.nan)
    for k, d in enumerate(tab["days"]):
        j = int(np.searchsorted(bd, d))
        x = int(np.searchsorted(bd, _iso(_ord(d) + T616_HOLD)))
        if j < len(bd) and x < len(bd) and _ord(bd[j]) - _ord(d) <= 4 and np.isfinite(ao[j]) and np.isfinite(ao[x]):
            out[k] = ao[x] / ao[j] - 1.0
    return out


def rr_predict(tab: dict) -> dict:
    """T-616 criteria and reported arms on the decision-day table."""
    days = tab["days"]
    dd = np.array(days)
    win = (dd >= T616_START) & (dd <= T616_END)
    X = _X(tab)
    base = win & np.isfinite(X).all(axis=1) & np.isfinite(tab["y7"])
    fit = base & (dd <= T616_FIT_END)
    oos = base & (dd >= T616_OOS_START)
    full = _ols(tab["y7"][base], X[base], T616_NW_POOLED)
    fitr = _ols(tab["y7"][fit], X[fit], T616_NW_POOLED)
    t_defl = bonferroni_t(full["t"], T616_TRIALS)
    phases = {}
    for w in range(7):
        m = base & (tab["wd"] == w)
        lag = CAL.nw_lags(int(m.sum()))
        o = _ols(tab["y7"][m], X[m], lag)
        of = _ols(tab["y7"][m & fit], X[m & fit], lag)
        rs = oos_r2(tab["ord"][m], tab["y7"][m], tab["z"][m], oos[m], hold=T616_HOLD, min_train=26)
        phases[WD[w]] = {"n": int(m.sum()), "slope": o["slope"], "t": o["t"], "t_deflated": bonferroni_t(o["t"], T616_TRIALS),
                         "fit_slope": of["slope"], "lag": lag, "oos_r2": rs["r2"], "n_oos": int((m & oos).sum())}
    n = min(p["n"] for p in phases.values())
    ob = np.flatnonzero(base)
    r2 = oos_r2(tab["ord"][ob], tab["y7"][ob], tab["z"][ob], oos[ob])
    r2_ctl = oos_r2(tab["ord"][ob], tab["y7"][ob], X[ob], oos[ob])
    r2_sign = oos_r2(tab["ord"][ob], tab["y7"][ob], tab["z"][ob], oos[ob], restrict_sign=True)
    rule = tranche_rule(tab, T616_OOS_START, T616_END, T616_COST)
    stress = tranche_rule(tab, T616_OOS_START, T616_END, T616_STRESS)
    rows = [(f"sign fitted on 2022-01..2024-12 positive (controlled slope {_f(fitr['slope'], 4)}, NW t {_f(fitr['t'], 2)}, "
             f"n {fitr['n']} days)", None if fitr["slope"] is None else bool(fitr["slope"] > 0),
             fitr["t"] is not None and fitr["t"] <= -T616_T),
            (f"full-window (2022-01..2026-10) controlled NW (lag {T616_NW_POOLED}) t of the RR25-z slope >= {T616_T:g} after "
             f"deflation over {T616_TRIALS} trials (slope {_f(full['slope'], 4)}, raw t {_f(full['t'], 2)}, deflated t "
             f"{_tdefl(t_defl)}, n {full['n']} days)", None if t_defl is None else bool(t_defl >= T616_T),
             full["t"] is not None and full["t"] <= -T616_T),
            (f"Campbell-Thompson out-of-sample R2 (2025-01..2026-10, expanding OLS of y7 on z vs the expanding mean) "
             f"{_f(r2['r2'], 4)} > 0 ({r2['n']} forecasts)", None if r2["r2"] is None else bool(r2["r2"] > 0), False),
            (f"long-when-z>+1 rule (10 bp per switch, seven weekday tranches pooled) daily Sharpe {_f(rule.get('sr_rule'), 4)} "
             f"above buy-and-hold {_f(rule.get('sr_bh'), 4)} in the out-of-sample window ({rule.get('n_days')} days)",
             None if rule["diff"] is None else bool(rule["diff"] > 0), False)]
    v, why, crit = CAL._judge(rows, n, T616_MIN_N, "weekly observations (the shortest weekday grid)")
    # ------------------------------------------------------------------ reported
    rep = {}
    rep["no_controls"] = _ols(tab["y7"][base], tab["z"][base], T616_NW_POOLED)
    b10 = base & np.isfinite(tab["y7_10"])
    rep["entry_1000"] = _ols(tab["y7_10"][b10], X[b10], T616_NW_POOLED)
    bb = base & np.isfinite(tab["bfz"])
    rep["butterfly_placebo"] = _ols(tab["y7"][bb], _X(tab, "bfz")[bb], T616_NW_POOLED)
    joint = _ols(tab["y7"][bb], _X(tab, "z", ("bfz",))[bb], T616_NW_POOLED)
    jb = _ols(tab["y7"][bb], np.column_stack([tab["bfz"], tab["z"]] + [tab[c] for c in T616_CONTROLS])[bb], T616_NW_POOLED)
    rep["joint_rr_and_bf"] = {"t_rr": joint["t"], "t_bf": jb["t"], "n": joint["n"]}
    b30 = win & np.isfinite(X).all(axis=1) & np.isfinite(tab["y30"])
    rep["h30_pooled_hh"] = _ols(tab["y30"][b30], X[b30], T616_HH_POOLED, "uniform")
    rep["h30_pooled_nw"] = _ols(tab["y30"][b30], X[b30], 2 * T616_HOLD_REP)
    h30p = {}
    for w in range(7):
        m = b30 & (tab["wd"] == w)
        o = _ols(tab["y30"][m], X[m], T616_HH_WEEKLY, "uniform")
        h30p[WD[w]] = {"n": o["n"], "slope": o["slope"], "t_hh": o["t"]}
    rep["h30_phases_hh"] = h30p
    rep["oos_r2_controlled"] = r2_ctl
    rep["oos_r2_sign_restricted"] = r2_sign
    rep["rule_stress_50bp"] = {k: stress.get(k) for k in ("sr_rule", "sr_bh", "diff")}
    rep["rule_phases_oos"] = {WD[w]: phase_rule(tab, w, T616_OOS_START, T616_END, T616_COST) for w in range(7)}
    rep["rule_full_window"] = {k: tranche_rule(tab, T616_START, T616_END, T616_COST).get(k) for k in ("sr_rule", "sr_bh", "diff", "n_days")}
    rep["n_filled"] = int(tab["filled"][base].sum())
    rep["share_z_above_1_oos"] = float(np.mean(tab["z"][oos] > T616_ZTHR)) if oos.any() else None
    return {"verdict": v, "why": why, "criteria": crit, "n": n, "full": full, "fit": fitr, "t_deflated": t_defl,
            "oos_r2": r2, "rule": rule, "phases": phases, "reported": rep, "n_days": int(base.sum()),
            "first": days[int(np.flatnonzero(base)[0])] if base.any() else None,
            "last": days[int(np.flatnonzero(base)[-1])] if base.any() else None}


def b13_cryptoderiv_b_rr25_weekly(archive):
    """T-616: z of BTC's 30-DTE 25-delta risk reversal (trailing 90 days, 09:00 UTC) -> next-7-day Coinbase BTC return."""
    miss = _missing(archive, [T616_TRADES, T616_DVOL, T616_FUND, T616_H])
    if miss:
        return miss
    sm = _t616_smiles(archive)
    rr = {d: v[0] for d, v in sm.items()}
    bf = {d: v[1] for d, v in sm.items()}
    fitdays = {d for d, v in rr.items() if v is not None}
    zd, bzd = trailing_z(rr), trailing_z(bf)
    ts, _, cl = CDA._hourly_oc(archive, T616_H)
    dvol = {}
    for r in CV._stream(archive, T616_DVOL):
        v = r.get("value") or {}
        c = CV._num(v.get("close"))
        if c is not None and v.get("ts_ms") is not None:
            dvol[CV._dday(int(v["ts_ms"]) / 1000)] = c
    fr = sorted((int(v["timestamp"]), float(v["interest_8h"])) for v in
                (r.get("value") or {} for r in CV._stream(archive, T616_FUND))
                if v.get("timestamp") is not None and CV._num(v.get("interest_8h")) is not None)
    fts = np.array([a for a, _ in fr], np.int64)
    fv = np.array([b for _, b in fr], float)
    tab = t616_table(zd, bzd, fitdays, ts, cl, dvol, fts, fv)
    j = rr_predict(tab)
    rep = j["reported"]
    if B7C._has(archive, T616_IBIT):
        ib = ibit_weekly(tab, CV._bars(archive, T616_IBIT))
        ph = {WD[w]: phase_rule(tab, w, T616_OOS_START, T616_END, T616_COST, rets=ib) for w in range(7)}
        rep["ibit_vehicle_oos"] = {"phases": ph, "mean_diff": _mean([p["diff"] for p in ph.values() if p["diff"] is not None])}
    else:
        rep["ibit_vehicle_oos"] = "daily-history-IBIT not archived"
    f, ph, rl = j["full"], j["phases"], j["rule"]
    tr = [p["t"] for p in ph.values() if p["t"] is not None]
    n_pass_ph = sum(1 for p in ph.values() if p["t_deflated"] is not None and p["t_deflated"] >= T616_T)
    h30 = rep["h30_pooled_hh"]
    h30t = [p["t_hh"] for p in rep["h30_phases_hh"].values() if p["t_hh"] is not None]
    bfp, jt = rep["butterfly_placebo"], rep["joint_rr_and_bf"]
    rph = [p["diff"] for p in rep["rule_phases_oos"].values() if p["diff"] is not None]
    ibv = rep["ibit_vehicle_oos"]
    reason = (f"T-257's daily smiles (07:00-09:00 UTC Deribit trade sample): {len(sm)} smile days, {len(fitdays)} with a 30-DTE "
              f"RR25, z against the 90 prior days (>= {T616_ZMIN} fits); decision days {j['first']}..{j['last']} ({j['n_days']} with "
              f"z, controls and the 7-day target; {rep['n_filled']} on a 1-day fill; {tab['stale']} stale 09:00 marks). Pooled "
              f"all-start regression of the Coinbase 09:00->09:00 7-day log return on RR25-z with trailing 7/30-day returns, DVOL "
              f"(t-1 candle) and 7-day mean funding: slope {_f(f['slope'], 4)}, NW t {_f(f['t'], 2)} (deflated over {T616_TRIALS} "
              f"trials {_tdefl(j['t_deflated'])}); 2022-2024 slope {_f(j['fit']['slope'], 4)} (t {_f(j['fit']['t'], 2)}); out-of-sample "
              f"R2 2025-01.. {_f(j['oos_r2']['r2'], 4)} ({j['oos_r2']['n']} forecasts; with controls {_f(rep['oos_r2_controlled']['r2'], 4)}, "
              f"sign-restricted {_f(rep['oos_r2_sign_restricted']['r2'], 4)}). Rule long when z > +1 (OOS, seven tranches pooled, "
              f"{rl.get('n_days')} days, long {_pc(rl.get('share_long'), 0)}): daily Sharpe {_f(rl.get('sr_rule'), 4)} vs buy-and-hold "
              f"{_f(rl.get('sr_bh'), 4)}; at the 50 bp stress {_f(rep['rule_stress_50bp']['diff'], 4)}; per-phase weekly Sharpe "
              f"difference {_f(min(rph) if rph else None, 3)} to {_f(max(rph) if rph else None, 3)}; IBIT vehicle mean difference "
              + (f"{_f(ibv['mean_diff'], 3)}" if isinstance(ibv, dict) else str(ibv))
              + f". Weekday grids (rule 10): t {_f(min(tr) if tr else None, 2)} to {_f(max(tr) if tr else None, 2)}, {n_pass_ph}/7 with "
              f"deflated t >= 2 ("
              + ", ".join(f"{k} {_f(p['slope'], 4)} t {_f(p['t'], 2)} n {p['n']} OOS R2 {_f(p['oos_r2'], 3)}" for k, p in ph.items())
              + f"). Reported: no controls t {_f(rep['no_controls']['t'], 2)}; 10:00 UTC entry t {_f(rep['entry_1000']['t'], 2)}; "
              f"butterfly-z placebo slope {_f(bfp['slope'], 4)} (t {_f(bfp['t'], 2)}), jointly RR t {_f(jt['t_rr'], 2)} / BF t "
              f"{_f(jt['t_bf'], 2)}; 30-day horizon pooled slope {_f(h30['slope'], 4)} (Hansen-Hodrick lag {T616_HH_POOLED} t "
              f"{_f(h30['t'], 2)}; weekly grids HH lag {T616_HH_WEEKLY} t {_f(min(h30t) if h30t else None, 2)} to "
              f"{_f(max(h30t) if h30t else None, 2)}); full-window rule Sharpe difference {_f(rep['rule_full_window']['diff'], 4)}. "
              f"Priors: the SPX skew failures T-52 / T-138 / T-227 — " + j["why"])
    stat = {k: j[k] for k in ("n", "full", "fit", "t_deflated", "oos_r2", "rule", "phases", "criteria", "n_days", "first", "last")}
    stat.update(reported=rep, trials=T616_TRIALS, nw_lag_pooled=T616_NW_POOLED, smile_days=len(sm), rr_days=len(fitdays),
                stale_marks=tab["stale"], rule10="pooled all-start daily regression and seven-tranche rule book; the seven weekday "
                                                  "grids reported")
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================ T-607 crypto small-cap quintile vs BTC ==

T607_CMC = "cmc-historical-listings"
T607_PRODUCTS = "coinbase-products-2026-10-15"
T607_BTC = "coinbase-daily-BTC-USD"
T607_START, T607_END = "2019-01-01", "2026-09-30"   # entry Tuesdays (00:00 UTC)
T607_SPLIT = "2022-11-17"
T607_DV_FLOOR = 1e6                  # mean daily Coinbase dollar volume over the 30 bars before the snapshot day
T607_DV_WIN = 30
T607_MIN_ELIG = 15
T607_COST = 0.0050                   # per side
T607_DELIST = 0.50
T607_BLOCK = 8
T607_NBOOT = 5000
T607_TRIALS = 24 + 1 + 2             # T-314's 24, T-546, the 2 weighting variants
T607_MIN_N = 300
T607_MAX_AGE = 8                     # days from the snapshot to the entry
T607_BAD_SNAPS = frozenset({"2020-11-30"})
T607_PX_TOL = 0.25                   # |ln(CMC price / Coinbase close)| for a symbol match
T607_ALIASES = {"CGLD": "CELO", "RNDR": "RENDER", "MATIC": "POL"}   # reported variant only (Coinbase kept old tickers)


def cmc_sundays(P: XS.CmcPanel) -> list:
    """Intact Sunday snapshot dates (the integrity screen's flagged dates and T607_BAD_SNAPS are missing)."""
    return [d for d in P.dates if date.fromisoformat(d).weekday() == 6 and d not in P.flagged and d not in T607_BAD_SNAPS]


def snapshot_for(sundays, entry_day: str, max_age: int = T607_MAX_AGE) -> Optional[str]:
    """The latest Sunday snapshot dated at least 2 days before ``entry_day`` (entry at its 00:00 UTC; a snapshot is
    stamped 23:59:59 and available the next 00:00) and at most ``max_age`` days before it; None when there is none."""
    have = sundays if isinstance(sundays, (set, frozenset)) else set(sundays)
    o = _ord(entry_day)
    for a in range(2, max_age + 1):
        d = _iso(o - a)
        if d in have:
            return d
    return None


def cmc_symbol_map(P: XS.CmcPanel, snap: str) -> dict:
    """{SYMBOL: [(cmc id, price, marketCap)]} of one snapshot."""
    ids, px, _, _, mc = P.day(P.dpos[snap])
    out = defaultdict(list)
    for c, p, m in zip(ids.tolist(), px.tolist(), mc.tolist()):
        out[P.symbol(c).upper()].append((int(c), float(p), float(m)))
    return out


def match_cap(cands: Sequence[tuple], cb_px: float, tol: float = T607_PX_TOL) -> Optional[tuple]:
    """The same-symbol CMC entry nearest in log price to the Coinbase close, accepted within ``tol`` (and cap > 0)."""
    if not cands or not (cb_px and np.isfinite(cb_px) and cb_px > 0):
        return None
    best = min(cands, key=lambda z: abs(math.log(z[1] / cb_px)) if z[1] > 0 else math.inf)
    if best[1] > 0 and best[2] > 0 and abs(math.log(best[1] / cb_px)) <= tol:
        return best
    return None


def eligible_week(pan: dict, smap: dict, k_snap: int, k_entry: int, dv_floor_sum: float = T607_DV_FLOOR * T607_DV_WIN,
                  aliases: Optional[dict] = None) -> dict:
    """Eligible rows for one snapshot: dollar volume summed over columns k_snap-30..k_snap-1 >= the floor (bars ending
    by the snapshot day's 00:00), a close at the entry column, and a CMC match in the snapshot (price check against the
    Coinbase close of the snapshot day's bar). Returns rows, caps, and the unmatched bases."""
    if k_snap - T607_DV_WIN < 0:
        return {"rows": np.array([], int), "mc": np.array([]), "unmatched": [], "n_vol": 0}
    s = pan["cs"][:, k_snap] - pan["cs"][:, k_snap - T607_DV_WIN]
    cand = np.flatnonzero((s >= dv_floor_sum) & np.isfinite(pan["C"][:, k_entry]))
    rows, mc, unm = [], [], []
    for i in cand:
        b = pan["base"][i].upper()
        m = match_cap(smap.get(b, []), pan["Cf"][i, k_snap])
        if m is None and aliases and b in aliases:
            m = match_cap(smap.get(aliases[b], []), pan["Cf"][i, k_snap])
        if m is None:
            unm.append(pan["base"][i])
            continue
        rows.append(int(i))
        mc.append(m[2])
    return {"rows": np.array(rows, int), "mc": np.array(mc, float), "unmatched": unm, "n_vol": int(cand.size)}


def quintiles(mc: np.ndarray, pids: Sequence[str]) -> np.ndarray:
    """Quintile labels 0 (smallest cap) .. 4: floor(5 x rank / n), ranks ascending by cap (ties by product id)."""
    n = mc.size
    order = np.lexsort((np.array(pids), mc))
    q = np.empty(n, int)
    q[order] = (5 * np.arange(n)) // n
    return q


def hold_returns(pan: dict, rows: np.ndarray, k_entry: int, k_exit: int, haircut: float = T607_DELIST) -> tuple:
    """(return, delisted) from the close at column k_entry to the close at k_exit; a coin without a close at k_exit is
    marked at its last close, minus ``haircut`` when it never trades again."""
    e = pan["C"][rows, k_entry]
    x = pan["C"][rows, k_exit]
    last = pan["Cf"][rows, k_exit]
    gone = ~pan["traded"][rows, k_exit] & ~pan["later"][rows, k_exit]
    ex = np.where(np.isfinite(x), x, np.where(gone, last * (1.0 - haircut), last))
    return ex / e - 1.0, gone & ~np.isfinite(x)


BOOKS = ("vw_q1", "ew_q1", "vw_q5", "ew_q5", "ew_all")


def week_weights(q: np.ndarray, mc: np.ndarray) -> dict:
    out = {}
    for name, sel in (("vw_q1", q == 0), ("ew_q1", q == 0), ("vw_q5", q == 4), ("ew_q5", q == 4), ("ew_all", np.ones(q.size, bool))):
        w = np.zeros(q.size)
        if sel.any():
            w[sel] = mc[sel] / mc[sel].sum() if name.startswith("vw") else 1.0 / sel.sum()
        out[name] = w
    return out


def book_costs(weeks: Sequence[dict], book: str, cost: float = T607_COST, step: int = 7) -> None:
    """Drift-adjusted turnover of ``book`` against the previous week's drifted weights (full entry after a gap, full
    liquidation before one); sets q[book + '_to'] and q[book + '_net'] = gross - cost x turnover."""
    prev, prev_k = None, None
    for i, q in enumerate(weeks):
        rows, w, r = q["rows"], q["w"][book], q["r"]
        gross = float(np.dot(w, r))
        tw = dict(zip(rows.tolist(), w.tolist()))
        if prev is None or prev_k is None or q["k"] - prev_k != step:
            to = 1.0
        else:
            to = float(sum(abs(tw.get(c, 0.0) - prev.get(c, 0.0)) for c in set(tw) | set(prev)))
        nxt_ok = i + 1 < len(weeks) and weeks[i + 1]["k"] - q["k"] == step
        last = i + 1 == len(weeks)
        to_total = to + (0.0 if (nxt_ok or last) else 1.0)
        q[book + "_gross"], q[book + "_to"] = gross, to_total
        q[book + "_net"] = gross - cost * to_total
        den = 1.0 + gross if abs(1.0 + gross) > 1e-12 else 1e-12
        prev = {c: wi * (1.0 + ri) / den for c, wi, ri in zip(rows.tolist(), w.tolist(), r.tolist()) if wi > 0}
        prev_k = q["k"]


def size_weeks(pan: dict, P: XS.CmcPanel, sundays: Sequence[str], btc_row: int, phase: int = 1,
               dv_floor_sum: float = T607_DV_FLOOR * T607_DV_WIN, aliases: Optional[dict] = None,
               start: str = T607_START, end: str = T607_END) -> dict:
    """Weekly records for entry at the close of column snapshot + ``phase`` (1 = the Monday bar, Tuesday 00:00 UTC),
    exit 7 columns later, sorted on the latest Sunday snapshot within T607_MAX_AGE days of the entry."""
    o0 = pan["o0"]
    weeks, dropped, no_snap = [], [], 0
    maps = {}
    have = set(sundays)
    s0 = _ord(start) - 9
    s0 += (6 - date.fromordinal(s0).weekday()) % 7                      # the first Sunday on or after start - 9 days
    for so in range(s0, _ord(end) + 1, 7):
        k_entry = so - o0 + phase
        entry_day = _iso(so + phase + 1)                     # the entry is the close of column k_entry = next day 00:00
        if not (start <= entry_day <= end) or k_entry + 7 >= pan["T"] or k_entry < 0:
            continue
        snap = snapshot_for(have, entry_day)
        if snap is None:
            no_snap += 1
            continue
        k_snap = _ord(snap) - o0
        if snap not in maps:
            maps[snap] = cmc_symbol_map(P, snap)
        el = eligible_week(pan, maps[snap], k_snap, k_entry, dv_floor_sum, aliases)
        rows = el["rows"]
        if rows.size < T607_MIN_ELIG:
            dropped.append({"entry": entry_day, "n": int(rows.size)})
            continue
        q = quintiles(el["mc"], [pan["pids"][i] for i in rows])
        r, gone = hold_returns(pan, rows, k_entry, k_entry + 7)
        rb = pan["C"][btc_row, k_entry + 7] / pan["C"][btc_row, k_entry] - 1.0
        weeks.append({"k": k_entry, "entry": entry_day, "snap": snap, "rows": rows, "mc": el["mc"], "q": q, "r": r,
                      "w": week_weights(q, el["mc"]), "btc": float(rb), "n_delisted": int(gone.sum()),
                      "unmatched": el["unmatched"], "n_vol": el["n_vol"]})
    for b in BOOKS:
        book_costs(weeks, b)
    return {"weeks": weeks, "dropped": dropped, "no_snapshot": no_snap}


def _arr(weeks: Sequence[dict], key: str) -> np.ndarray:
    return np.array([q[key] for q in weeks], float)


def size_test(pan: dict, P: XS.CmcPanel, sundays: Sequence[str], btc_row: int, n_boot: int = T607_NBOOT) -> dict:
    res = size_weeks(pan, P, sundays, btc_row)
    W = res["weeks"]
    btc = _arr(W, "btc")
    d = _arr(W, "vw_q1_net") - btc
    d_ew = _arr(W, "ew_q1_net") - btc
    days = [q["entry"] for q in W]
    pg, pl, dr = CAL.studentized_p_escalated(d, T607_BLOCK, n_boot, SEED, 1)
    ci = CAL.mean_ci(d, T607_BLOCK, n_boot) if d.size > 2 else [None, None]
    first = np.array([x < T607_SPLIT for x in days])
    halves = [_mean(d[first]), _mean(d[~first])]
    dsr = family_dsr(d, [_sr(d), _sr(d_ew)], T607_TRIALS) if d.size > 3 else {"dsr": None}
    m = _mean(d)
    rows = [(f"mean weekly net VW Q1 - BTC {_pc(m, 3)} with a one-sided 95% lower bound > 0 (8-week blocks, p {CAL._mc(pg, dr)}; "
             f"95% CI {_pc(ci[0], 3)} to {_pc(ci[1], 3)})", B7C._sig_crit(m, pg, dr), CAL.decide_p(pl, dr) is True),
            (f"both halves positive (split {T607_SPLIT}: {_pc(halves[0], 3)} / {_pc(halves[1], 3)})",
             None if any(h is None for h in halves) else all(h > 0 for h in halves), False),
            dsr_row(dsr, f"DSR > 0.95 at {T607_TRIALS} trials (T-314's 24, T-546, the 2 weightings)")
            if dsr.get("dsr") is not None else ("DSR > 0.95 (n/a)", None, False)]
    v, why, crit = CAL._judge(rows, len(W), T607_MIN_N, "weeks")
    return {"verdict": v, "why": why, "criteria": crit, "n": len(W), "res": res, "d": d, "d_ew": d_ew, "p": pg, "draws": dr,
            "ci": ci, "halves": halves, "dsr": dsr, "mean": m, "days": days}


def b13_cryptoderiv_b_small_cap_quintile(archive):
    """T-607: value-weighted smallest CMC-cap quintile of liquid Coinbase USD coins minus BTC, Tuesday-to-Tuesday, net."""
    prods = CV._names(archive, CV.CB_PRODUCTS_PREFIX)
    daily_names = [nm for nm in CV._names(archive, "coinbase-daily-") if nm.endswith("-USD")]
    need = [T607_CMC, T607_BTC] + ([] if T607_PRODUCTS in prods else [T607_PRODUCTS]) + ([] if daily_names else ["coinbase-daily-<SYM>-USD"])
    miss = _missing(archive, need)
    if miss:
        return miss
    pan, info = CDA._t608_panel(archive)
    if "BTC-USD" not in pan["pids"]:
        return _missing(archive, [T607_BTC + " (BTC row)"])
    btc_row = pan["pids"].index("BTC-USD")
    P = CAL._cached(archive, ("b13cdb_cmcw",), lambda: XS.CmcPanel([XS._iter(archive, T607_CMC)]))
    sundays = cmc_sundays(P)
    j = size_test(pan, P, sundays, btc_row)
    W = j["res"]["weeks"]
    btc = _arr(W, "btc")
    rep = {}
    for b in BOOKS:
        rep[b] = {"gross": _mean(_arr(W, b + "_gross")), "net": _mean(_arr(W, b + "_net")), "turnover": _mean(_arr(W, b + "_to"))}
    rep["btc_mean"] = _mean(btc)
    rep["ew_q1_minus_btc_net"] = _mean(j["d_ew"])
    rep["q1_minus_q5"] = {"vw_gross": _mean(_arr(W, "vw_q1_gross") - _arr(W, "vw_q5_gross")),
                          "vw_net": _mean(_arr(W, "vw_q1_net") - _arr(W, "vw_q5_net")),
                          "ew_gross": _mean(_arr(W, "ew_q1_gross") - _arr(W, "ew_q5_gross")),
                          "ew_net": _mean(_arr(W, "ew_q1_net") - _arr(W, "ew_q5_net"))}
    rep["q1_minus_ew_universe"] = {"vw_gross": _mean(_arr(W, "vw_q1_gross") - _arr(W, "ew_all_gross")),
                                   "vw_net": _mean(_arr(W, "vw_q1_net") - _arr(W, "ew_all_net")),
                                   "ew_gross": _mean(_arr(W, "ew_q1_gross") - _arr(W, "ew_all_gross")),
                                   "ew_net": _mean(_arr(W, "ew_q1_net") - _arr(W, "ew_all_net"))}
    rep["names_per_quintile"] = {f"Q{k + 1}": _mean([int((q["q"] == k).sum()) for q in W]) for k in range(5)}
    rep["eligible_mean"] = _mean([q["rows"].size for q in W])
    unm = [len(q["unmatched"]) for q in W]
    cnt = defaultdict(int)
    for q in W:
        for b in q["unmatched"]:
            cnt[b] += 1
    rep["dropped_missing_cmc_cap"] = {"mean_per_week": _mean(unm), "total_coin_weeks": int(sum(unm)), "distinct": len(cnt),
                                      "top": sorted(cnt.items(), key=lambda kv: -kv[1])[:12]}
    rep["n_delisted_exits"] = int(sum(q["n_delisted"] for q in W))
    usd_list = [p for p in info["status"] if p.endswith("-USD")]
    rep["listed_usd_products_without_bundle"] = sorted(p for p in usd_list if p not in pan["pids"] and p not in info["excluded"])
    # bull / bear: BTC's Monday close vs its 200-day average (closes up to the entry)
    reg = []
    for q in W:
        k = q["k"]
        c = pan["C"][btc_row, max(0, k - 199):k + 1]
        reg.append(bool(pan["C"][btc_row, k] > np.nanmean(c)))
    reg = np.array(reg, bool)
    rep["btc_trend"] = {"above_200d": {"n": int(reg.sum()), "mean": _mean(j["d"][reg]) if reg.any() else None},
                        "below_200d": {"n": int((~reg).sum()), "mean": _mean(j["d"][~reg]) if (~reg).any() else None}}
    by_year = defaultdict(list)
    for q, x in zip(W, j["d"]):
        by_year[q["entry"][:4]].append(x)
    rep["by_year"] = {y: float(np.mean(v)) for y, v in sorted(by_year.items())}
    # rule 10: the other entry days that keep the Sunday snapshot within 8 days
    phases = {"Tue": j["mean"]}
    for ph, lab in zip(range(2, 8), ("Wed", "Thu", "Fri", "Sat", "Sun", "Mon")):
        rr = size_weeks(pan, P, sundays, btc_row, phase=ph)["weeks"]
        phases[lab] = _mean(_arr(rr, "vw_q1_net") - _arr(rr, "btc")) if rr else None
    rep["entry_phases"] = phases
    lit = size_weeks(pan, P, sundays, btc_row, dv_floor_sum=T607_DV_FLOOR)["weeks"]
    rep["literal_1m_30day_total_floor"] = {"n": len(lit), "mean": _mean(_arr(lit, "vw_q1_net") - _arr(lit, "btc")) if lit else None}
    al = size_weeks(pan, P, sundays, btc_row, aliases=T607_ALIASES)["weeks"]
    rep["ticker_alias_variant"] = {"aliases": T607_ALIASES, "n": len(al),
                                   "mean": _mean(_arr(al, "vw_q1_net") - _arr(al, "btc")) if al else None}
    excl = {s.upper() for s in XS.EXCLUDE_IDS.values()}
    rep["cmc_declared_excluded_members"] = sorted({pan["base"][i] for q in W for i in q["rows"] if pan["base"][i].upper() in excl})
    dr = j["res"]["dropped"]
    pv = [x for x in phases.values() if x is not None]
    reason = (f"{info['n_bundles']} coinbase-daily USD bundles ({len(info['excluded'])} excluded: T-424's stablecoin and wrapped/staked "
              f"bases with BTC kept, and {len(info['fx_stablecoin_ids'])} fx_stablecoin ids of {info['snapshot']}); CMC Sunday top-500 "
              f"snapshots ({len(sundays)} intact Sundays; 2020-11-30 missing); eligible = mean daily Coinbase dollar volume >= $1m over the "
              f"30 bars before the snapshot day, a Monday bar, a CMC symbol match within 25% in price. Entry Tuesdays {W[0]['entry'] if W else 'n/a'}.."
              f"{W[-1]['entry'] if W else 'n/a'}: {j['n']} weeks kept, {len(dr)} dropped with < {T607_MIN_ELIG} eligible"
              + (f" (last dropped {dr[-1]['entry']})" if dr else "") + f", {j['res']['no_snapshot']} without a snapshot within 8 days; "
              f"mean {_u(rep['eligible_mean'])} eligible, names per quintile "
              + ", ".join(f"{k} {_u(v_)}" for k, v_ in rep["names_per_quintile"].items())
              + f"; {_u(rep['dropped_missing_cmc_cap']['mean_per_week'])} coins a week dropped for no CMC cap "
              f"({rep['dropped_missing_cmc_cap']['distinct']} distinct; most often "
              + ", ".join(f"{b} {c}" for b, c in rep["dropped_missing_cmc_cap"]["top"][:6])
              + f"); {rep['n_delisted_exits']} delisted exits at last close -50%. Mean weekly net VW Q1 - BTC {_pc(j['mean'], 3)} (p "
              f"{CAL._mc(j['p'], j['draws'])}; 95% CI {_pc(j['ci'][0], 3)} to {_pc(j['ci'][1], 3)}); halves {_pc(j['halves'][0], 3)} / "
              f"{_pc(j['halves'][1], 3)}; DSR {_f(j['dsr'].get('dsr'), 3)}. Reported: EW Q1 - BTC {_pc(rep['ew_q1_minus_btc_net'], 3)}; "
              f"VW Q1 gross {_pc(rep['vw_q1']['gross'], 3)} / net {_pc(rep['vw_q1']['net'], 3)} (turnover {_u(rep['vw_q1']['turnover'], 2)} a "
              f"week), BTC {_pc(rep['btc_mean'], 3)}; Q1 - Q5 VW gross {_pc(rep['q1_minus_q5']['vw_gross'], 3)} / net "
              f"{_pc(rep['q1_minus_q5']['vw_net'], 3)}; Q1 - EW universe VW gross {_pc(rep['q1_minus_ew_universe']['vw_gross'], 3)} / net "
              f"{_pc(rep['q1_minus_ew_universe']['vw_net'], 3)} (EW Q1 net {_pc(rep['q1_minus_ew_universe']['ew_net'], 3)}); BTC above / "
              f"below its 200-day average {_pc(rep['btc_trend']['above_200d']['mean'], 3)} ({rep['btc_trend']['above_200d']['n']}) / "
              f"{_pc(rep['btc_trend']['below_200d']['mean'], 3)} ({rep['btc_trend']['below_200d']['n']}); by year "
              + ", ".join(f"{y} {_pc(v_, 2)}" for y, v_ in rep["by_year"].items())
              + f"; rule 10 entry days (same snapshot) {_pc(min(pv), 3) if pv else 'n/a'} to {_pc(max(pv), 3) if pv else 'n/a'}; the literal "
              f"$1m 30-day-total floor {_pc(rep['literal_1m_30day_total_floor']['mean'], 3)} ({rep['literal_1m_30day_total_floor']['n']} weeks); "
              f"ticker aliases {list(T607_ALIASES)} matched {_pc(rep['ticker_alias_variant']['mean'], 3)}; CMC-declared stable/wrapped "
              f"symbols among members {rep['cmc_declared_excluded_members']}. Survivorship: the Coinbase universe is today's product "
              f"list (online and delisted USD products; {len(rep['listed_usd_products_without_bundle'])} listed USD products lack a bundle), "
              f"products purged from the API are absent; CMC's top 500 is point in time — " + j["why"])
    stat = {k: j[k] for k in ("n", "mean", "p", "draws", "ci", "halves", "criteria")}
    stat.update(dsr={k: j["dsr"].get(k) for k in ("dsr", "psr0", "var_used", "n_trials")}, reported=rep,
                dropped_weeks=len(dr), no_snapshot_weeks=j["res"]["no_snapshot"], first_week=W[0]["entry"] if W else None,
                last_week=W[-1]["entry"] if W else None, cost_per_side=T607_COST,
                rule10="the Tuesday rebalance is fixed by the Sunday snapshot; the six other entry days within the 8-day snapshot age "
                       "are reported (per-start range), not judged")
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================== T-615 stablecoin mint after a BTC drawdown ==

T615_PAIR = ("usdt", "usdc")
T615_AGG = ("usdt", "usdc", "dai", "busd", "tusd")
T615_BTC = "coinbase-daily-BTC-USD"
T615_START, T615_END = "2019-01-01", "2026-09-30"      # entry days
T615_SPLIT = "2022-01-01"
T615_SIG_WIN = 180
T615_SIG_K = 2.0
T615_LAG = 2                         # supply day s known at s+2 00:00 UTC
T615_DD_WIN = 365
T615_DD_MIN = 300
T615_DD_Q = 0.10
T615_DD_RET = 3
T615_WITHIN = 2
T615_REFRACT = 5
T615_H = 3
T615_BAR = 0.0050
T615_COST = 0.0050                   # round trip
T615_CTRL_LAG = 4                    # control entry D+4: the first 00:00 after "no spike on D..D+2" is known
T615_NBOOT = 5000
T615_MIN_N = 30


def supply_grid(series: Sequence[dict], o0: int, o1: int) -> np.ndarray:
    """Summed SplyCur on ordinal days o0..o1 (a coin before its first observation counts 0; a gap after it is NaN)."""
    out = np.zeros(o1 - o0 + 1)
    for s in series:
        a = np.full(o1 - o0 + 1, np.nan)
        for d, v in s.items():
            k = _ord(d) - o0
            if 0 <= k < a.size:
                a[k] = v
        if s:
            k0 = _ord(min(s)) - o0
            a[:max(0, k0)] = 0.0
        out = out + a
    return out


def spike_flags(supply: np.ndarray, win: int = T615_SIG_WIN, k: float = T615_SIG_K) -> tuple:
    """(spike, z) per day: the daily increase dS_t = S_t - S_{t-1} > 0 with z = (dS_t - mean) / sd (ddof 1) > k over the
    ``win`` prior days' increases (all finite). Uses days up to t only."""
    dS = np.concatenate([[np.nan], np.diff(supply)])
    n = dS.size
    z = np.full(n, np.nan)
    ok = np.isfinite(dS)
    x = np.where(ok, dS, 0.0)
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x * x)])
    cn = np.concatenate([[0], np.cumsum(ok.astype(int))])
    for t in range(win, n):
        m = cn[t] - cn[t - win]
        if m < win or not ok[t]:
            continue
        s1, s2 = c1[t] - c1[t - win], c2[t] - c2[t - win]
        mu = s1 / m
        var = (s2 - m * mu * mu) / (m - 1)
        if var > 0:
            z[t] = (dS[t] - mu) / math.sqrt(var)
    spike = np.isfinite(z) & (z > k) & (dS > 0)
    return spike, z


def drawdown_flags(close: np.ndarray, win: int = T615_DD_WIN, q: float = T615_DD_Q, h: int = T615_DD_RET,
                   min_obs: int = T615_DD_MIN) -> tuple:
    """(flag, r3): r3_t = ln(C_t / C_{t-h}) at or below the ``q`` quantile of r3 over the ``win`` prior days (>= min_obs
    finite). Uses closes up to t only (known at the close of day t)."""
    n = close.size
    r = np.full(n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[h:] = np.log(close[h:] / close[:-h])
    flag = np.zeros(n, bool)
    for t in range(win, n):
        if not np.isfinite(r[t]):
            continue
        w = r[t - win:t]
        w = w[np.isfinite(w)]
        if w.size >= min_obs and r[t] <= np.quantile(w, q):
            flag[t] = True
    return flag, r


def stable_events(spike: np.ndarray, dd: np.ndarray, within: int = T615_WITHIN, lag: int = T615_LAG,
                  lo: int = 0, strict: bool = False) -> list:
    """Entry indices (grid days) of spike days s with a drawdown day in s-within..s (``strict``: s-within..s-1), entry
    at s + lag; not de-overlapped."""
    out = []
    first = 1 if strict else 0
    for s in np.flatnonzero(spike):
        if any(0 <= s - j < dd.size and dd[s - j] for j in range(first, within + 1)):
            out.append(int(s + lag))
    return sorted({e for e in out if e >= lo})


def control_days(spike: np.ndarray, dd: np.ndarray, within: int = T615_WITHIN, lag: int = T615_CTRL_LAG) -> list:
    """Entry indices of drawdown days D with no spike on D..D+within, entered at D + lag."""
    out = []
    for D in np.flatnonzero(dd):
        if D + within < spike.size and not spike[D:D + within + 1].any():
            out.append(int(D + lag))
    return out


def refractory(entries: Sequence[int], gap: int = T615_REFRACT) -> list:
    """Keep an entry only when it is at least ``gap`` days after the previous kept one."""
    out = []
    for e in sorted(entries):
        if not out or e - out[-1] >= gap:
            out.append(e)
    return out


def fwd_returns(op: np.ndarray, cl: np.ndarray, entries: Sequence[int], h: int) -> np.ndarray:
    """ln(close of bar e+h-1 / open of bar e): from 00:00 UTC of day e over h x 24 h (NaN when missing)."""
    e = np.asarray(entries, int)
    out = np.full(e.size, np.nan)
    ok = (e >= 0) & (e + h - 1 < cl.size)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[ok] = np.log(cl[e[ok] + h - 1] / op[e[ok]])
    return out


def _week_id(o: int) -> int:
    y, w, _ = date.fromordinal(int(o)).isocalendar()
    return y * 100 + w


def cluster_diff_draws(xe, ge, xc, gc, n_boot: int, seed: int) -> np.ndarray:
    """Week-cluster bootstrap draws of mean(events) - mean(controls): clusters (ISO weeks of the entry day) resampled
    with replacement, each draw keeping every observation of the drawn weeks."""
    xe, xc = np.asarray(xe, float), np.asarray(xc, float)
    weeks = np.unique(np.concatenate([np.asarray(ge), np.asarray(gc)]))
    pos = {w: i for i, w in enumerate(weeks.tolist())}
    G = weeks.size
    ie = np.array([pos[w] for w in np.asarray(ge).tolist()], int)
    ic = np.array([pos[w] for w in np.asarray(gc).tolist()], int)
    SE, NE = np.bincount(ie, xe, G), np.bincount(ie, None, G)
    SC, NC = np.bincount(ic, xc, G), np.bincount(ic, None, G)
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < n_boot:
        k = min(1000, n_boot - done)
        idx = rng.integers(0, G, size=(k, G))
        ne, nc = NE[idx].sum(axis=1), NC[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append(SE[idx].sum(axis=1) / ne - SC[idx].sum(axis=1) / nc)
        done += k
    d = np.concatenate(out)
    return d[np.isfinite(d)]


def cluster_diff_test(xe, ge, xc, gc, bar: float = 0.0, n_boot: int = T615_NBOOT) -> dict:
    """Point difference, 5th percentile (one-sided 95% lower bound) and the one-sided p's against ``bar``
    (p_greater = share of draws <= bar, H0 diff <= bar), escalated by batches of ``n_boot`` (``escalate_p``)."""
    xe, xc = np.asarray(xe, float), np.asarray(xc, float)
    if xe.size < 2 or xc.size < 2:
        return {"diff": None, "lb": None, "p_greater": None, "p_less": None, "draws": 0}
    diff = float(xe.mean() - xc.mean())
    first = {}

    def batch(k):
        d = cluster_diff_draws(xe, ge, xc, gc, n_boot, SEED + k)
        if k == 0:
            first["lb"] = float(np.quantile(d, 0.05)) if d.size else None
        if not d.size:
            return None, None
        return float((np.sum(d <= bar) + 1) / (d.size + 1)), float((np.sum(d >= bar) + 1) / (d.size + 1))

    pg, pl, nd = CAL.escalate_p(batch, n_boot, 1, CAL.MAX_SEEDS)
    return {"diff": diff, "lb": first.get("lb"), "p_greater": pg, "p_less": pl, "draws": nd}


def t615_series(supply: np.ndarray, op: np.ndarray, cl: np.ndarray, o0: int, start: str = T615_START, end: str = T615_END,
                h: int = T615_H, strict: bool = False, ctrl_lag: int = T615_CTRL_LAG) -> dict:
    """Events and controls on the common day grid from ordinal o0 (arrays indexed by day)."""
    spike, z = spike_flags(supply)
    dd, r3 = drawdown_flags(cl)
    lo, hi = _ord(start) - o0, _ord(end) - o0
    ev_all = [e for e in stable_events(spike, dd, strict=strict) if lo <= e <= hi]
    ev = refractory(ev_all)
    ct = [e for e in control_days(spike, dd, lag=ctrl_lag) if lo <= e <= hi]
    ye, yc = fwd_returns(op, cl, ev, h), fwd_returns(op, cl, ct, h)
    me, mc = np.isfinite(ye), np.isfinite(yc)
    ev = [e for e, m in zip(ev, me) if m]
    ct = [e for e, m in zip(ct, mc) if m]
    return {"spike": spike, "z": z, "dd": dd, "r3": r3, "ev": ev, "ct": ct, "ye": ye[me], "yc": yc[mc],
            "ge": [_week_id(o0 + e) for e in ev], "gc": [_week_id(o0 + e) for e in ct], "n_ev_raw": len(ev_all)}


def mint_test(supply: np.ndarray, op: np.ndarray, cl: np.ndarray, o0: int, n_boot: int = T615_NBOOT) -> dict:
    s = t615_series(supply, op, cl, o0)
    ev, ct = s["ev"], s["ct"]
    main = cluster_diff_test(s["ye"], s["ge"], s["yc"], s["gc"], T615_BAR, n_boot)
    split = _ord(T615_SPLIT) - o0
    he = [np.array([e < split for e in ev]), np.array([e >= split for e in ev])]
    hc = [np.array([e < split for e in ct]), np.array([e >= split for e in ct])]
    halves = []
    for a, b in zip(he, hc):
        if a.sum() >= 2 and b.sum() >= 2:
            halves.append(cluster_diff_test(s["ye"][a], np.array(s["ge"])[a], s["yc"][b], np.array(s["gc"])[b], 0.0, n_boot))
        else:
            halves.append({"diff": None, "lb": None, "p_greater": None, "p_less": None, "draws": 0,
                           "n_ev": int(a.sum()), "n_ct": int(b.sum())})
    n = len(ev)
    dec = n >= T615_MIN_N                   # the registration: fewer than 30 events gives inconclusive
    d = main["diff"]
    hd = [h["diff"] for h in halves]
    rows = [(f"event - control mean 3-day BTC log return {_pc(d)} > {T615_BAR * 100:.2f}% with a week-clustered one-sided 95% "
             f"lower bound above it (lower bound {_pc(main['lb'])}, p {CAL._mc(main['p_greater'], main['draws'])})",
             (None if d is None else B7C._sig_crit(d - T615_BAR, main["p_greater"], main["draws"])),
             dec and CAL.decide_p(main["p_less"], main["draws"]) is True),
            (f"positive in both halves (2019-2021 {_pc(hd[0])} / 2022-2026 {_pc(hd[1])})",
             None if any(x is None for x in hd) else all(x > 0 for x in hd), False),
            (f"the claim's wording: a one-sided 95% lower bound > 0 in both halves ({_pc(halves[0]['lb'])} / {_pc(halves[1]['lb'])}; "
             f"p {_f(halves[0]['p_greater'], 4)} / {_f(halves[1]['p_greater'], 4)})",
             None if any(h["diff"] is None for h in halves) else
             _all_or_none([B7C._sig_crit(h["diff"], h["p_greater"], h["draws"]) for h in halves]), False)]
    v, why, crit = CAL._judge(rows, n, T615_MIN_N, "events")
    return {"verdict": v, "why": why, "criteria": crit, "n": n, "main": main, "halves": halves, "s": s,
            "n_controls": len(ct), "mean_event": _mean(s["ye"]), "mean_control": _mean(s["yc"])}


def _all_or_none(oks: Sequence[Optional[bool]]) -> Optional[bool]:
    if any(o is False for o in oks):
        return False
    if all(o is True for o in oks):
        return True
    return None


def b13_cryptoderiv_b_stablecoin_mint(archive):
    """T-615: USDT+USDC issuance spike within 2 days after a bottom-decile BTC 3-day return -> 3-day BTC return vs controls."""
    need = [XS.cm_b(a) for a in T615_PAIR] + [T615_BTC]
    miss = _missing(archive, need)
    if miss:
        return miss
    cb = CV._bars(archive, T615_BTC)
    o0 = _ord(cb["days"][0])
    o1 = _ord(cb["days"][-1])
    op = np.full(o1 - o0 + 1, np.nan)
    cl = np.full(o1 - o0 + 1, np.nan)
    for d, o_, c_ in zip(cb["days"], cb["open"], cb["close"]):
        op[_ord(d) - o0], cl[_ord(d) - o0] = o_, c_
    sup = {a: XS._metric(XS._cm(archive, a), "SplyCur") for a in T615_AGG if B7C._has(archive, XS.cm_b(a))}
    supply = supply_grid([sup[a] for a in T615_PAIR], o0, o1)
    j = mint_test(supply, op, cl, o0)
    s = j["s"]
    rep = {}
    s1 = t615_series(supply, op, cl, o0, h=1)
    rep["h1"] = {"diff": _mean(s1["ye"]) - _mean(s1["yc"]) if s1["ye"].size and s1["yc"].size else None,
                 "mean_event": _mean(s1["ye"]), "mean_control": _mean(s1["yc"]), "n": len(s1["ev"])}
    lo, hi = _ord(T615_START) - o0, _ord(T615_END) - o0
    uncond = refractory([int(x + T615_LAG) for x in np.flatnonzero(s["spike"]) if lo <= x + T615_LAG <= hi])
    yu = fwd_returns(op, cl, uncond, T615_H)
    alld = fwd_returns(op, cl, list(range(lo, hi + 1)), T615_H)
    rep["unconditional_spikes"] = {"n": int(np.isfinite(yu).sum()), "mean": _mean(yu), "all_days_mean": _mean(alld)}
    rep["drawdown_only_controls"] = {"n": j["n_controls"], "mean": j["mean_control"]}
    for lag in (1, 2):
        sc = t615_series(supply, op, cl, o0, ctrl_lag=lag)
        rep[f"control_entry_D+{lag}"] = {"n": len(sc["ct"]), "mean": _mean(sc["yc"]),
                                         "diff": None if not sc["yc"].size else j["mean_event"] - _mean(sc["yc"])}
    ctr = refractory(s["ct"])
    yr = fwd_returns(op, cl, ctr, T615_H)
    rep["controls_deoverlapped"] = {"n": int(np.isfinite(yr).sum()), "mean": _mean(yr),
                                    "diff": None if j["mean_event"] is None or _mean(yr) is None else j["mean_event"] - _mean(yr)}
    st = t615_series(supply, op, cl, o0, strict=True)
    rep["strict_spike_after_drawdown_day"] = {"n": len(st["ev"]), "mean": _mean(st["ye"]),
                                             "diff": None if not st["ye"].size else _mean(st["ye"]) - _mean(st["yc"])}
    if all(a in sup for a in T615_AGG):
        sa = t615_series(supply_grid([sup[a] for a in T615_AGG], o0, o1), op, cl, o0)
        rep["aggregate_5_stablecoins"] = {"n": len(sa["ev"]), "mean": _mean(sa["ye"]),
                                          "diff": None if not sa["ye"].size else _mean(sa["ye"]) - _mean(sa["yc"])}
    else:
        rep["aggregate_5_stablecoins"] = f"not all of {list(T615_AGG)} archived"
    rep["event_net_of_50bp"] = None if j["mean_event"] is None else j["mean_event"] - T615_COST
    rep["events"] = [_iso(o0 + e) for e in s["ev"]]
    rep["events_by_year"] = {y: sum(1 for e in rep["events"] if e[:4] == y) for y in sorted({e[:4] for e in rep["events"]})}
    rep["n_events_before_refractory"] = s["n_ev_raw"]
    rep["n_spike_days"] = int(s["spike"][lo:hi + 1].sum())
    rep["n_drawdown_days"] = int(s["dd"][lo:hi + 1].sum())
    rep["chain_coverage_check"] = "no DefiLlama stablecoin-circulation bundle archived: Coin Metrics chain coverage not checked"
    rep["netflow_arm"] = "not run: no exchange netflow data archived (the registration runs it only once the data exist)"
    m, hv = j["main"], j["halves"]
    reason = (f"Coin Metrics SplyCur USDT + USDC (current vintage; day s usable from s+2 00:00 UTC), spike = daily increase with z > 2 "
              f"against the 180 prior days ({rep['n_spike_days']} spike days in the window); Coinbase BTC daily closes, drawdown = 3-day "
              f"log return in the bottom decile of the 365 prior days ({rep['n_drawdown_days']} days). Events (spike 0-2 days after a "
              f"drawdown day, entry at the open s+2, 5-day refractory): {j['n']} of {s['n_ev_raw']} ({rep['events_by_year']}); controls "
              f"(drawdown days with no spike on D..D+2, entry D+4): {j['n_controls']}. Mean 3-day log return events {_pc(j['mean_event'])} vs "
              f"controls {_pc(j['mean_control'])}: difference {_pc(m['diff'])} (week-clustered one-sided 95% lower bound {_pc(m['lb'])}; p "
              f"against the 0.50% bar {CAL._mc(m['p_greater'], m['draws'])}); halves {_pc(hv[0]['diff'])} (lower bound {_pc(hv[0]['lb'])}) "
              f"/ {_pc(hv[1]['diff'])} ({_pc(hv[1]['lb'])}). Reported: +1 day difference {_pc(rep['h1']['diff'])}; unconditional spike "
              f"events (T-402/T-464 base) {_pc(rep['unconditional_spikes']['mean'])} over {rep['unconditional_spikes']['n']} vs all days "
              f"{_pc(rep['unconditional_spikes']['all_days_mean'])}; drawdown-only controls (T-320 base) {_pc(rep['drawdown_only_controls']['mean'])}; "
              f"controls entered D+1 {_pc(rep['control_entry_D+1']['mean'])} / D+2 {_pc(rep['control_entry_D+2']['mean'])} (differences "
              f"{_pc(rep['control_entry_D+1']['diff'])} / {_pc(rep['control_entry_D+2']['diff'])}); de-overlapped controls difference "
              f"{_pc(rep['controls_deoverlapped']['diff'])}; spike strictly after the drawdown day {_pc(rep['strict_spike_after_drawdown_day']['diff'])} "
              f"({rep['strict_spike_after_drawdown_day']['n']} events); with DAI/BUSD/TUSD "
              + (f"{_pc(rep['aggregate_5_stablecoins']['diff'])} ({rep['aggregate_5_stablecoins']['n']} events)"
                 if isinstance(rep["aggregate_5_stablecoins"], dict) else rep["aggregate_5_stablecoins"])
              + f"; event mean net of the 50 bp round trip {_pc(rep['event_net_of_50bp'])}; {rep['chain_coverage_check']}; "
              f"{rep['netflow_arm']}; T-402 and T-464 counted as prior trials (context) — " + j["why"])
    stat = {k: j[k] for k in ("n", "main", "halves", "criteria", "n_controls", "mean_event", "mean_control")}
    stat.update(reported=rep, bar=T615_BAR, rule10="event-driven (spike days): no grid phase")
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================== T-610 BTC US-session half-hour momentum ==

T610_PREFIX = "coinbase-1m-BTC-USD-"
T610_MAIN = ("2024-01-01", "2026-10-31")
T610_AGREE = ("2022-01-01", "2023-12-31")
T610_COST = 0.0010
T610_STRESS = 0.0120                 # Coinbase retail taker 0.60% per side
T610_VOL_WIN = 60
T610_BLOCK = 5                       # sessions per week
T610_NBOOT = 5000
T610_NPLACEBO = 1000
T610_CELLS = 2
T610_MIN_N = 200
T610_NW_LAG = 5


def _t610_bars(archive, names: Sequence[str]) -> dict:
    """1-minute grid from the first bar start: close / open (NaN where no bar) and volume (0)."""
    def load():
        T, O, C, V = [], [], [], []
        for nm in names:
            for r in CV._stream(archive, nm):
                v = r.get("value") or {}
                c, o = CV._num(v.get("close")), CV._num(v.get("open"))
                if v.get("t") is None or c is None or c <= 0:
                    continue
                T.append(int(v["t"]))
                O.append(o if o and o > 0 else np.nan)
                C.append(c)
                V.append(CV._num(v.get("volume")) or 0.0)
        return grid_from(np.array(T, np.int64), np.array(O, float), np.array(C, float), np.array(V, float))
    return CAL._cached(archive, ("b13cdb_t610_1m", tuple(names)), load)


def grid_from(t: np.ndarray, o: np.ndarray, c: np.ndarray, v: np.ndarray) -> dict:
    order = np.argsort(t, kind="stable")
    t, o, c, v = t[order], o[order], c[order], v[order]
    g0 = int(t[0])
    n = int((t[-1] - g0) // 60) + 1
    idx = (t - g0) // 60
    C = np.full(n, np.nan)
    O = np.full(n, np.nan)
    V = np.zeros(n)
    C[idx], O[idx], V[idx] = c, o, v
    have = np.isfinite(C)
    pos = np.where(have, np.arange(n), -1)
    last = np.maximum.accumulate(pos)
    Cf = np.where(last >= 0, C[np.maximum(last, 0)], np.nan)
    return {"g0": g0, "n": n, "C": C, "O": O, "V": V, "Cf": Cf, "have": have}


def price_at(g: dict, T) -> tuple:
    """(price, carried) at instant(s) T (minute boundaries): the close of the bar starting T - 60 s, or the latest earlier
    close carried forward (flagged). NaN outside the grid."""
    T = np.atleast_1d(np.asarray(T, np.int64))
    k = (T - 60 - g["g0"]) // 60
    ok = (k >= 0) & (k < g["n"])
    kk = np.clip(k, 0, g["n"] - 1)
    p = np.where(ok, g["Cf"][kk], np.nan)
    return p, ok & ~g["have"][kk]


def open_at(g: dict, T) -> tuple:
    """(price, carried) at the open of the bar starting at T: its open, or (no bar) the latest close before T carried."""
    T = np.atleast_1d(np.asarray(T, np.int64))
    k = (T - g["g0"]) // 60
    ok = (k >= 0) & (k < g["n"])
    kk = np.clip(k, 0, g["n"] - 1)
    o = np.where(ok, g["O"][kk], np.nan)
    pc, _ = price_at(g, T)
    use = ok & ~np.isfinite(o)
    return np.where(use, pc, o), use


def full_sessions(first: str, last: str) -> list:
    """NYSE rule-calendar sessions with a full 09:30-16:00 ET day (early closes and closures excluded)."""
    out = []
    for o in range(_ord(first), _ord(last) + 1):
        d = _iso(o)
        if CAL.is_nyse_session(d) and not CV.early_close(d):
            out.append(d)
    return out


def session_trades(g: dict, days: Sequence[str], open_hm: str = "09:30", close_hm: str = "16:00", utc_clock: bool = False) -> dict:
    """Per day: first-half-hour log return r1 (P(open + 30 min) / P(open)), side = sign(r1), the trade from the open of
    the bar starting 30 minutes before the close to the price at the close, first-half-hour volume, carried marks.
    ``utc_clock``: the UTC-day clock (00:00-00:30 signal, 23:30-24:00 trade)."""
    if utc_clock:
        o = np.array([CDA._utc0(d) for d in days], np.int64)
        c = o + DAY
    else:
        o = np.array([int(CV.et_epoch(d, open_hm)) for d in days], np.int64)
        c = np.array([int(CV.et_epoch(d, close_hm)) for d in days], np.int64)
    p0, k0 = price_at(g, o)
    p30, k30 = price_at(g, o + 1800)
    pe, ke = open_at(g, c - 1800)
    px, kx = price_at(g, c)
    with np.errstate(invalid="ignore", divide="ignore"):
        r1 = np.log(p30 / p0)
        r2 = np.log(px / pe)
        move = px / pe - 1.0
    side = np.sign(r1)
    k = (o - g["g0"]) // 60
    vol = np.full(len(days), np.nan)
    for i, kk in enumerate(k):
        if 0 <= kk and kk + 30 <= g["n"]:
            vol[i] = g["V"][kk:kk + 30].sum()
    ok = np.isfinite(r1) & np.isfinite(move)
    return {"days": list(days), "r1": r1, "r2": r2, "move": move, "side": side, "ok": ok, "vol": vol,
            "carried": int((k0 | k30 | ke | kx)[ok].sum()), "carried_marks": {"open": int(k0[ok].sum()), "p30": int(k30[ok].sum()),
                                                                              "entry": int(ke[ok].sum()), "exit": int(kx[ok].sum())}}


def volume_flags(vol: np.ndarray, win: int = T610_VOL_WIN) -> tuple:
    """(flag, valid): first-half-hour volume above the 2/3 quantile of the ``win`` prior sessions' (all finite)."""
    vol = np.asarray(vol, float)
    flag, valid = np.zeros(vol.size, bool), np.zeros(vol.size, bool)
    for i in range(win, vol.size):
        w = vol[i - win:i]
        if np.isfinite(vol[i]) and np.isfinite(w).all():
            valid[i] = True
            flag[i] = vol[i] > np.quantile(w, 2.0 / 3.0)
    return flag, valid


def placebo_q95(move: np.ndarray, cost: float, n: int = T610_NPLACEBO, seed: int = SEED) -> Optional[float]:
    """95th percentile of the mean net of random-sign trades (each trade's sign drawn +-1 with equal odds)."""
    if move.size < 2:
        return None
    rng = np.random.default_rng(seed)
    s = rng.choice(np.array([-1.0, 1.0]), size=(n, move.size))
    return float(np.quantile((s * move[None, :]).mean(axis=1) - cost, 0.95))


def cell_eval(tr: dict, mask: np.ndarray, cost: float = T610_COST, alpha: float = ALPHA / T610_CELLS,
              n_boot: int = T610_NBOOT) -> dict:
    """Main-window and 2022-2023 statistics of one cell (rows of ``tr`` flagged by ``mask``, side != 0)."""
    dd = np.array(tr["days"])
    trade = mask & tr["ok"] & (tr["side"] != 0)
    main = trade & (dd >= T610_MAIN[0]) & (dd <= T610_MAIN[1])
    agree = trade & (dd >= T610_AGREE[0]) & (dd <= T610_AGREE[1])
    net = tr["side"] * tr["move"] - cost
    x = net[main]
    pg, pl, dr = CDA._esc_stud(x, T610_BLOCK, n_boot, alpha) if x.size >= 8 else (None, None, 0)
    q95 = placebo_q95(tr["move"][main], cost)
    m = _mean(x)
    ma = _mean(net[agree])
    sig = (False if m is None or not m > 0 else CAL.decide_p(pg, dr, alpha))
    agr = None if ma is None else bool(ma > 0)
    plc = None if q95 is None or m is None else bool(m > q95)
    oks = [sig, agr, plc]
    ok = False if any(o is False for o in oks) else (True if all(o is True for o in oks) else None)
    return {"n": int(main.sum()), "mean_net": m, "mean_gross": _mean(x + cost), "p_greater": pg, "p_less": pl, "draws": dr,
            "ci": CAL.mean_ci(x, T610_BLOCK, n_boot) if x.size > 2 else [None, None], "n_agree": int(agree.sum()),
            "mean_net_2022_2023": ma, "placebo_q95": q95, "sig": sig, "agree": agr, "placebo": plc, "ok": ok,
            "stress_net": _mean(net[main] + cost - T610_STRESS), "decisive": CAL.decide_p(pl, dr) is True if dr else False}


def momentum_test(tr: dict, n_boot: int = T610_NBOOT) -> dict:
    vf, vv = volume_flags(tr["vol"])
    cells = {"all_sessions": cell_eval(tr, np.ones(len(tr["days"]), bool), n_boot=n_boot),
             "top_tercile_volume": cell_eval(tr, vf & vv, n_boot=n_boot)}
    oks = [c["ok"] for c in cells.values()]
    ok = True if any(o is True for o in oks) else (False if all(o is False for o in oks) else None)
    parts = []
    for name, c in cells.items():
        parts.append(f"{name}: mean net {_bp(c['mean_net'])} (gross {_bp(c['mean_gross'])}, n {c['n']}), one-sided p "
                     f"{CAL._mc(c['p_greater'], c['draws'])} vs 0.025 -> {c['sig']}; 2022-2023 mean net {_bp(c['mean_net_2022_2023'])} "
                     f"(n {c['n_agree']}) > 0 -> {c['agree']}; above the random-sign placebo's 95th percentile {_bp(c['placebo_q95'])} "
                     f"-> {c['placebo']}")
    rows = [(f"in at least one cell: one-sided 95% lower bound of the net mean > 0 after Bonferroni over 2 cells, the 2022-2023 "
             f"mean of the same sign, and above the placebo's 95th percentile [{'; '.join(parts)}]", ok,
             all(c["decisive"] for c in cells.values()))]
    n = cells["all_sessions"]["n"]
    v, why, crit = CAL._judge(rows, n, T610_MIN_N, "trades (all-sessions cell, 2024-01..2026-10)")
    return {"verdict": v, "why": why, "criteria": crit, "n": n, "cells": cells, "n_vol_flag": int((vf & vv).sum())}


def b13_cryptoderiv_b_us_session_momentum(archive):
    """T-610: sign of BTC's first NYSE half-hour return -> Coinbase BTC over the session's last half hour, net of 10 bp."""
    names = CV._names(archive, T610_PREFIX)
    names = [nm for nm in names if nm[len(T610_PREFIX):][:4].isdigit()]
    miss = _missing(archive, names if names else ["coinbase-1m-BTC-USD-<YYYY-MM>"])
    if miss:
        return miss
    g = _t610_bars(archive, names)
    first = CV._dday(g["g0"])
    last = CV._dday(g["g0"] + 60 * (g["n"] - 1))
    days = full_sessions(first, last)
    tr = session_trades(g, days)
    j = momentum_test(tr)
    c_all, c_vol = j["cells"]["all_sessions"], j["cells"]["top_tercile_volume"]
    rep = {}
    dd = np.array(tr["days"])
    okm = tr["ok"] & (dd >= T610_MAIN[0])
    oka = tr["ok"] & (dd >= T610_AGREE[0]) & (dd <= T610_AGREE[1])
    rep["hac_slope_main"] = _ols(tr["r2"][okm], tr["r1"][okm], T610_NW_LAG)
    rep["hac_slope_2022_2023"] = _ols(tr["r2"][oka], tr["r1"][oka], T610_NW_LAG)
    cal = [_iso(o) for o in range(_ord(first) + 1, _ord(last))]
    utc = session_trades(g, cal, utc_clock=True)
    cu = cell_eval(utc, np.ones(len(cal), bool), alpha=ALPHA)
    rep["utc_day_clock"] = {k: cu[k] for k in ("n", "mean_net", "mean_gross", "p_greater", "draws", "mean_net_2022_2023", "placebo_q95")}
    fomc, cpi = _fomc_cpi(archive)
    if fomc or cpi:
        ev = np.array([d in fomc or d in cpi for d in tr["days"]])
        ce = cell_eval(tr, ev, n_boot=2000)
        cx = cell_eval(tr, ~ev, n_boot=2000)
        rep["fomc_cpi_sessions"] = {"n": ce["n"], "mean_net": ce["mean_net"], "excluded_mean_net": cx["mean_net"],
                                    "n_fomc": sum(1 for d in tr["days"] if d in fomc and d >= T610_MAIN[0]),
                                    "n_cpi": sum(1 for d in tr["days"] if d in cpi and d >= T610_MAIN[0])}
    else:
        rep["fomc_cpi_sessions"] = "fomc-meetings / macro-release-cpi not archived"
    edt = np.array([datetime.fromtimestamp(CV.et_epoch(d, "09:30"), tz=UTC).hour == 13 for d in tr["days"]])
    rep["dst_split_main"] = {"edt_13_30": cell_eval(tr, edt, n_boot=2000)["mean_net"], "est_14_30": cell_eval(tr, ~edt, n_boot=2000)["mean_net"]}
    by_year = defaultdict(list)
    net = tr["side"] * tr["move"] - T610_COST
    for d, x, ok_, s_ in zip(tr["days"], net, tr["ok"], tr["side"]):
        if ok_ and s_ != 0:
            by_year[d[:4]].append(x)
    rep["by_year_all_sessions"] = {y: float(np.mean(v)) for y, v in sorted(by_year.items())}
    rep["zero_signal_sessions"] = int((tr["ok"] & (tr["side"] == 0)).sum())
    rep["carried_marks"] = tr["carried_marks"]
    rep["sessions"] = len(days)
    hs, ha = rep["hac_slope_main"], rep["hac_slope_2022_2023"]
    fc = rep["fomc_cpi_sessions"]
    reason = (f"Coinbase BTC-USD 1-minute bars {first}..{last} ({g['n']} minutes on the grid, {int(g['have'].sum())} with a bar); "
              f"{len(days)} full NYSE sessions (rule calendar, early closes dropped, DST via America/New_York); {tr['carried']} of the "
              f"session marks carried forward from a no-trade minute ({rep['carried_marks']}); {rep['zero_signal_sessions']} zero-return "
              f"signals skipped. All sessions 2024-01..: mean net {_bp(c_all['mean_net'])} (gross {_bp(c_all['mean_gross'])}, n "
              f"{c_all['n']}, p {CAL._mc(c_all['p_greater'], c_all['draws'])}, 95% CI {_bp(c_all['ci'][0])} to {_bp(c_all['ci'][1])}); "
              f"2022-2023 {_bp(c_all['mean_net_2022_2023'])}; placebo 95th pct {_bp(c_all['placebo_q95'])}. Top-tercile first-half-hour "
              f"volume ({j['n_vol_flag']} sessions in all years): mean net {_bp(c_vol['mean_net'])} (gross {_bp(c_vol['mean_gross'])}, n "
              f"{c_vol['n']}, p {CAL._mc(c_vol['p_greater'], c_vol['draws'])}); 2022-2023 {_bp(c_vol['mean_net_2022_2023'])}; placebo "
              f"{_bp(c_vol['placebo_q95'])}. Reported: HAC (lag {T610_NW_LAG}) slope of the last-half-hour return on the first "
              f"{_f(hs['slope'], 4)} (t {_f(hs['t'], 2)}; 2022-2023 {_f(ha['slope'], 4)}, t {_f(ha['t'], 2)}); UTC-day clock (00:00-00:30 -> "
              f"23:30-24:00) mean net {_bp(rep['utc_day_clock']['mean_net'])} (gross {_bp(rep['utc_day_clock']['mean_gross'])}, n "
              f"{rep['utc_day_clock']['n']}); retail-taker stress (120 bp) all sessions {_bp(c_all['stress_net'])}, top tercile "
              f"{_bp(c_vol['stress_net'])}; "
              + (f"FOMC/CPI sessions mean net {_bp(fc['mean_net'])} (n {fc['n']}), others {_bp(fc['excluded_mean_net'])}; "
                 if isinstance(fc, dict) else f"{fc}; ")
              + f"EDT / EST sessions {_bp(rep['dst_split_main']['edt_13_30'])} / {_bp(rep['dst_split_main']['est_14_30'])}; by year "
              + ", ".join(f"{y} {_bp(v_)}" for y, v_ in rep["by_year_all_sessions"].items())
              + "; priors T-427 (SPY), T-577, Hurst's hourly rules — " + j["why"])
    stat = {"n": j["n"], "cells": j["cells"], "criteria": j["criteria"], "n_vol_flag": j["n_vol_flag"], "reported": rep,
            "cost_round_trip": T610_COST, "stress_round_trip": T610_STRESS, "window": list(T610_MAIN), "agree_window": list(T610_AGREE),
            "rule10": "session-driven (every full NYSE session): no grid phase"}
    return _out(stat, j["n"], j["verdict"], reason)


HARNESSES = {"b13_cryptoderiv_b_rr25_weekly": b13_cryptoderiv_b_rr25_weekly,
             "b13_cryptoderiv_b_small_cap_quintile": b13_cryptoderiv_b_small_cap_quintile,
             "b13_cryptoderiv_b_stablecoin_mint": b13_cryptoderiv_b_stablecoin_mint,
             "b13_cryptoderiv_b_us_session_momentum": b13_cryptoderiv_b_us_session_momentum}
THEORY_MAP = {"T-616": "b13_cryptoderiv_b_rr25_weekly", "T-607": "b13_cryptoderiv_b_small_cap_quintile",
              "T-615": "b13_cryptoderiv_b_stablecoin_mint", "T-610": "b13_cryptoderiv_b_us_session_momentum"}
