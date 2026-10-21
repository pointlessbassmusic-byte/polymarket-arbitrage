"""
Batch 13, group ``short_a``: aggregate shorting flow and short interest as SPY timing signals (T-673, T-674, T-672),
2026-10-20 web sweep, cluster "short".
=====================================================================================================================

  * T-673  FINRA CNMS off-exchange short-volume ratio, equal-weighted over point-in-time S&P 500 members (x_t = mean_i
           short_volume / total_volume over members with total_volume > 0; a file day with fewer than 450 members in
           the file is skipped and counted), z_t over the trailing 60 file days (t included). Target: SPY open(t+1) ->
           open(t+11) minus continuous DTB3. Statistic: pooled OLS slope over every daily start, with and without the
           trailing 10-session SPY return (close t-10 -> close t) as a control, studentized circular block bootstrap
           with 20-session blocks. Pass (>= 1,500 file days): slope < 0 with one-sided p < 0.0125 (0.05 Bonferroni over
           the 4 CNMS cells) with AND without the control, AND negative in both halves (2018-08..2022-09, 2022-10..
           2026-10). Reported: Clark-West OOS R^2 (expanding from 250 file days), the non-backfilled-days rerun, the EW
           60-session and dollar-weighted 10-session cells, the unconditional mean, the regime exclusions and a
           bills-when-z>+1 timing rule at 1 bp per side.
  * T-674  "DIX": dollar-weighted CNMS ratio sum short_volume x close / sum total_volume x close over point-in-time
           members with an archived close (others dropped from both sums; their share of off-exchange volume reported).
           Signal: DIX_t at or above the 80th percentile of the 252 file days before t. Dip days: SPY close(t)/close(t-5)
           in the bottom quintile of the 252 sessions before t. Target: SPY open(t+1) -> open(t+61) minus DTB3. Pass
           (>= 1,500 eligible file days): signal-minus-all-eligible AND signal-minus-dip-day mean differences, net of
           1 bp per side, > 0 with one-sided p < 0.0125 (studentized circular block bootstrap, 120-session blocks); both
           positive in both halves by entry date (2019-08..2022-12, 2023-01..2026-08) and excluding 2020-02..2020-06;
           and the EW 60-session cell of the same sign.
  * T-672  Aggregate short-interest index from FINRA rows alone: x_r = mean log(1 + currentShortPositionQuantity /
           averageDailyVolumeQuantity) over listed rows with ADV >= 100,000 shares whose issueName does not match one
           pre-declared fund/SPAC/ADR/warrant/unit/right/preferred/note regex; volume placebo v_r = mean log ADV of the
           same rows; each recursively detrended (OLS line on releases 1..r) and z-scored by the residual sd up to r.
           Decision at the release's available_at, entry at the next SPY close, y_r = log SPY total return entry r ->
           entry r+1 minus DTB3. Pass (>= 120 OOS releases, first forecast after 72): Clark-West (NW 2 lags) one-sided
           p < 0.05 vs the expanding prevailing mean; Clark-West p < 0.05 of the index-plus-placebo forecast vs the
           placebo-only forecast; the recursive slope negative in both OOS halves (2020-12..2023-10, 2023-11..2026-09).

Conventions and declared readings (fixed before any run)
  * Data (rule 9). Every bundle through ``archive.load``; a row counts only when its ``available_at`` is not after the
    bundle's capture time (``batch6c_events._avail_filter``). CNMS file days are the ``file-day`` rows with status ok;
    a ``short-volume`` row counts when total_volume > 0. FINRA symbols are mapped to the index spelling (BRK/B ->
    BRK.B, ``batch6c_events.ntick``).
  * Membership (T-673, T-674). fja05680 change-date snapshots in force at day t 09:30 ET (the latest snapshot dated on
    or before t), then the Wikipedia changes table by effective date after the file's last date 2026-08-18
    (``batch6c_events.membership_snapshots``, the T-394 construction). The Wikipedia current-constituents snapshot is
    not used (the registration names the changes table only).
  * Point in time. The day-t CNMS file is available at the end of day t (live files ~17:20 ET); z_t, the DIX rank and
    the dip flag use data through the close of t (the rank and the dip breakpoints use the 252 values BEFORE t); the
    entry is the next session's open. SPY opens are on the total-return basis (open x adjclose / close). DTB3 is the
    print dated strictly before the decision day (``batch6c_cal.Bills``), converted to a continuous rate; the bill
    return over a hold is exp(r x calendar days / 365) - 1 (T-673, T-674) or r x days / 365 in logs (T-672).
    FINRA short interest enters at its available_at (end of the 8th NYSE business day after settlement); the entry is
    the first SPY 16:00 ET close strictly after it. T-672 fits only on pairs whose y was realised (exit close) before
    the decision time available_at r -- the conservative reading of "realised by entry r" (the pair ending at the
    entry close itself is not used); T-673/T-674's reported OOS forecasts likewise use only targets whose exit open is
    on or before day t.
  * Statistics. Slopes (T-673) are tested through their influence series psi_t = b + z~_t e_t / mean(z~^2) (z~ = z
    residualised on the intercept and the control, e the full-regression residual), whose mean is exactly the OLS
    slope; mean differences (T-674) through the series whose mean is exactly the difference (signal minus all
    eligible: y (s / p_s - 1); signal minus dip, groups overlapping: (m_s - m_d) + s (y - m_s) / p_s - d (y - m_d) /
    p_d). Each is tested with the studentized circular block bootstrap of ``block_bootstrap_pvalue`` (Bartlett LRV,
    bandwidth = block), 2,000 resamples a seed averaged over 5 seeds and escalated one seed at a time to 50 while
    the Monte-Carlo band of the criterion's p straddles its alpha (0.0125 for the CNMS cells: ``batch6c_cal.decide_p``
    with that alpha). Clark-West: f = e_bench^2 - (e_model^2 - (f_bench - f_model)^2), Newey-West t of mean f, one-
    sided normal p (T-672: 2 lags as registered; reported daily cells: lag max(h, automatic)).
  * Costs as registered: T-674 charges 1 bp per side (2 bp a round trip) to the signal leg of both comparisons (the
    baselines gross: the conservative reading); T-673's and T-672's timing rules are reported at 1 bp per side and 2
    bp per switch.
  * Rule 10. T-673 and T-674 pool every daily start (overlapping holds; blocks of 20 and 120 sessions, twice the
    hold), so there is no grid phase. T-672 trades on FINRA's release calendar (event-driven, set by FINRA), so there
    is no free phase either.
  * Survivorship. T-673 and T-672 use no single-stock prices (the FINRA rows include later-delisted names and the
    target is SPY). T-674's dollar weights need member closes, which come from the archive's 901-symbol daily-history
    set: TODAY's universe, so removed, acquired and renamed members are under-represented in the weights (the unpriced
    share of member off-exchange volume is reported). The registration's pre-run fetch of the missing members Yahoo
    still serves has not been done (this harness may not write the archive), so T-674 carries one criterion that is
    not implemented: at best inconclusive until that fetch, and a failing criterion still fails.
  * Declared readings (rules 11/12: a criterion passes only when every reading passes, fails only when every reading
    fails, else undecided). T-674 "close_i = split-adjusted daily-history close": (a) literally Yahoo's split-adjusted
    close (which embeds splits after t) and (b) the as-traded close known at t (split-adjusted close x the split
    factor after t, ``batch6c_stockxs._stock``). A member's Yahoo series is used only when Yahoo's meta says EQUITY and
    its as-traded volume agrees with FINRA's (``batch6c_events.finra_identity``; reused tickers fail it). T-672 "each
    is detrended by an OLS line on releases 1..r and z-scored by the residual sd up to r": (A) at each forecast origin
    r the whole history 1..r is re-detrended on the line fitted to 1..r (the regression is fitted on those values) and
    (B) each release's value is fixed when it is published (line and sd on 1..s for release s).
  * Other declared choices. Percentiles are numpy's linear interpolation. Halves are by file day (T-673), entry day
    (T-674) and settlement date (T-672). "Excluding 2020-02..2020-06" (T-674, a criterion) drops every start whose hold
    touches 2020-02-01..2020-06-30 (the house convention of T-393's squeeze criterion). T-674's "the EW 60-session
    cell has the same sign (reported, not tested)" is read as a sign criterion with no significance test (it sits in
    the AND chain of the pass). T-672's claim reads "positive Clark-West OOS R^2", so the point OOS R^2 > 0 is a
    criterion beside the Clark-West p; "the recursive slope negative in both halves" is read as negative at every OOS
    origin of each half (the strict reading). T-672's universe is every row of the listed-mode bundle (FINRA's listed
    classes) minus the regex; the company-class-only universe is reported.
"""

from __future__ import annotations

import bisect
import math
import re
from datetime import date
from typing import Optional, Sequence

import numpy as np

from mandel.data.public_history import FINRA_COMPANY_CLASSES
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_rates import hac_mean
from mandel.validation.backtest_eval import _hac_var

SEED = 0
N_BOOT = CAL.N_BOOT
N_SEEDS = CAL.N_SEEDS
MAX_SEEDS = CAL.MAX_SEEDS

SPY_B = "daily-history-SPY"
DTB3_B = "fred-DTB3"
FJA_B = "fja-sp500-components"
CHG_B = "wikipedia-sp500-changes"
CNMS_FMT = "finra-regsho-cnms-{}"
CNMS_FIRST = "2018-08"
CNMS_PROBE_LAST = "2030-12"
SI_PREFIX = "finra-short-interest-"
SI_FIRST_B = SI_PREFIX + "2017-12-29"

ALPHA_CELL = 0.0125            # 0.05 Bonferroni over the 4 CNMS cells (T-673, T-674)
ALPHA = 0.05

# T-673
T673_FLOOR = 450               # members in the file below which a file day is skipped
T673_WIN = 60                  # file days in the z window (t included)
T673_H = 10                    # sessions: open t+1 -> open t+11
T673_BLOCK = 20
T673_CTRL = 10                 # trailing SPY return control, close t-10 -> close t
T673_MIN_N = 1500
T673_SPLIT = "2022-10-01"
T673_OOS_START = 250
T673_COST = 1e-4               # timing rule, per side
T673_ZTHR = 1.0
T673_REGIMES = (("2020-02-01", "2020-06-30"), ("2021-01-01", "2021-03-31"))

# T-674
T674_RANK_WIN = 252
T674_PCT = 80.0
T674_DIP_LAG = 5
T674_DIP_PCT = 20.0
T674_H = 60
T674_H2 = 20
T674_BLOCK = 120
T674_COST = 2e-4               # 1 bp per side, a round trip, charged to the signal leg
T674_MIN_N = 1500
T674_SPLIT = "2023-01-01"
T674_LAST_ENTRY = "2026-08-31"
T674_EXCL = ("2020-02-01", "2020-06-30")
T674_LEVEL = 0.45
T674_OOS_START = 250

# T-672
SI_EXCLUDE = re.compile(r"(?i)\b(ETFS?|FUNDS?|ETNS?|TRUSTS?|ACQUISITIONS?|ADRS?|DEPOSITARY|WARRANTS?|UNITS?|RIGHTS?|"
                        r"PREFERRED|NOTES?)\b")
SI_ETF_DIAG = re.compile(r"(?i)\b(ETFS?|ETNS?|FUNDS?)\b")      # the ETF/fund rows the regex removes (diagnostic only)
SI_ADV_MIN = 100_000.0
SI_FIRST_OOS = 72              # the first forecast comes after 72 releases
SI_MIN_N = 120
SI_NW_LAG = 2
SI_BLOCK = 6
SI_SPLIT = "2023-11-01"        # OOS halves by settlement date: 2020-12..2023-10 and 2023-11..2026-09
SI_NEW_WIN = 24
SI_COST = 2e-4                 # timing rule, per switch
SI_ZTHR = 1.0
SI_HORIZONS = (21, 63)         # reported 1- and 3-month horizons, sessions
SI_EXCL = ("2020-02-01", "2020-06-30")


# ================================================================================================= statistics ==

def stud_p(d, block: int, n_boot: Optional[int] = None, seed: int = SEED) -> tuple:
    """(p_greater, p_less) for H0 mean(d) <= 0 / >= 0 from ONE set of studentized circular block-bootstrap draws,
    exactly the construction of ``backtest_eval.block_bootstrap_pvalue`` (block capped at n // 4, Bartlett LRV with
    bandwidth = block); (None, None) below 8 periods."""
    d = np.asarray(d, float)
    n = d.size
    if n < 8 or not np.isfinite(d).all():
        return None, None
    nb = CAL._nb(n_boot)
    block = max(1, min(int(block), n // 4))
    obs = d.mean()
    t_obs = obs / math.sqrt(float(_hac_var(d[None, :], block)[0]) / n)
    rng = np.random.default_rng(seed)
    nblk = math.ceil(n / block)
    ge = le = 0
    done = 0
    while done < nb:
        k = min(500, nb - done)
        starts = rng.integers(0, n, size=(k, nblk))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n
        s = d[idx]
        tb = (s.mean(axis=1) - obs) / np.sqrt(_hac_var(s, block) / n)
        ge += int(np.sum(tb >= t_obs))
        le += int(np.sum(tb <= t_obs))
        done += k
    return float((ge + 1) / (nb + 1)), float((le + 1) / (nb + 1))


def p_escalated(d, block: int, alpha: float, side: str, n_boot: Optional[int] = None, seed: int = SEED,
                n_seeds: int = N_SEEDS, max_seeds: int = MAX_SEEDS) -> tuple:
    """(p_greater, p_less, draws) pooled (mean) over seeds seed, seed + 1, ...: ``n_seeds`` first, then one more seed at a
    time while the ``side`` p ('greater' | 'less') is undecided against ``alpha`` (``CAL.decide_p``), up to ``max_seeds``."""
    nb = CAL._nb(n_boot)
    ps = []
    while True:
        ps.append(stud_p(d, block, nb, seed + len(ps)))
        if ps[0][0] is None:
            return None, None, nb * len(ps)
        if len(ps) < max(1, n_seeds):
            continue
        pg = float(np.mean([p[0] for p in ps])); pl = float(np.mean([p[1] for p in ps]))
        nd = nb * len(ps)
        if len(ps) >= max_seeds or CAL.decide_p(pg if side == "greater" else pl, nd, alpha) is not None:
            return pg, pl, nd


def sig(point, p, draws, alpha: float, want: str) -> Optional[bool]:
    """'point on the claimed side with one-sided p < alpha': False when the point is on the wrong side, else the
    Monte-Carlo-banded decision."""
    if point is None or not np.isfinite(point):
        return None
    if (want == "neg" and not point < 0) or (want == "pos" and not point > 0):
        return False
    return None if p is None else CAL.decide_p(p, draws, alpha)


def slope_psi(y, z, ctrl=None) -> dict:
    """OLS of y on [1, z(, ctrl)]: the z slope, its influence series psi (mean = slope exactly) and a Newey-West t."""
    y = np.asarray(y, float); z = np.asarray(z, float)
    n = y.size
    C = np.ones((n, 1)) if ctrl is None else np.column_stack([np.ones(n), np.asarray(ctrl, float)])
    bz, *_ = np.linalg.lstsq(C, z, rcond=None)
    zt = z - C @ bz
    X = np.column_stack([C, z])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    q = float(np.mean(zt * zt))
    psi = beta[-1] + zt * e / q
    return {"slope": float(beta[-1]), "psi": psi, "n": int(n)}


def nw_t(psi, lag: int) -> Optional[float]:
    h = hac_mean(np.asarray(psi, float), lag)
    return h.get("t")


def slope_test(y, z, ctrl=None, block: int = T673_BLOCK, alpha: float = ALPHA_CELL, n_boot: Optional[int] = None,
               pvals: bool = True, escalate: bool = True) -> dict:
    """Slope < 0 test: slope, one-sided p's (a criterion p escalated on the 'less' side against ``alpha``; a reported p
    over N_SEEDS seeds only), NW t (lag = block)."""
    s = slope_psi(y, z, ctrl)
    out = {"slope": s["slope"], "n": s["n"], "nw_t": nw_t(s["psi"], block)}
    if pvals:
        pg, pl, nd = p_escalated(s["psi"], block, alpha, "less", n_boot, max_seeds=MAX_SEEDS if escalate else N_SEEDS)
        out.update(p_greater=pg, p_less=pl, draws=nd)
    return out


def diff_all_series(y, s) -> np.ndarray:
    """Series whose mean is mean(y[s]) - mean(y) (signal days minus all eligible days)."""
    y = np.asarray(y, float); s = np.asarray(s, bool)
    p = s.mean()
    return y * (s / p - 1.0)


def diff_overlap_series(y, a, b) -> np.ndarray:
    """Series whose mean is mean(y[a]) - mean(y[b]) for two day groups that may overlap."""
    y = np.asarray(y, float); a = np.asarray(a, bool); b = np.asarray(b, bool)
    pa, pb = a.mean(), b.mean()
    ma, mb = y[a].mean(), y[b].mean()
    return (ma - mb) + np.where(a, (y - ma) / pa, 0.0) - np.where(b, (y - mb) / pb, 0.0)


def cw_stats(y, fb, fm, lag: int) -> dict:
    """Campbell-Thompson OOS R^2 and the Clark-West MSPE-adjusted t (Newey-West ``lag``) of forecast fm vs fb."""
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    if y.size < 10:
        return {"n": int(y.size), "r2": None, "cw_t": None, "p": None, "lag": lag}
    e1, e2 = y - fb, y - fm
    f = e1 ** 2 - (e2 ** 2 - (fb - fm) ** 2)
    h = hac_mean(f, lag)
    den = float(e1 @ e1)
    return {"n": int(y.size), "r2": 1.0 - float(e2 @ e2) / den if den > 0 else None, "cw_t": h["t"], "p": h["p"],
            "lag": lag}


def r2_ci(e_bench, e_model, block: int, n_boot: Optional[int] = None, seed: int = SEED) -> list:
    """Studentized circular block-bootstrap 95% CI of R^2 = 1 - sum e_model^2 / sum e_bench^2 (delta-method
    influence series, Bartlett LRV with bandwidth = block, as ``block_bootstrap_pvalue`` studentizes)."""
    a = np.asarray(e_model, float) ** 2
    b = np.asarray(e_bench, float) ** 2
    n = a.size
    if n < 8:
        return [None, None]
    block = max(1, min(int(block), n // 4))

    def stat(A, B):
        ma, mb = A.mean(axis=-1), B.mean(axis=-1)
        r = 1.0 - ma / mb
        u = -(A - ma[..., None]) / mb[..., None] + (ma / mb ** 2)[..., None] * (B - mb[..., None])
        se = np.sqrt(_hac_var(u.reshape(-1, n), block) / n).reshape(np.shape(r))
        return r, se

    r0, se0 = stat(a[None, :], b[None, :])
    r0, se0 = float(r0[0]), float(se0[0])
    rng = np.random.default_rng(seed)
    nb = CAL._nb(n_boot)
    nblk = math.ceil(n / block)
    starts = rng.integers(0, n, size=(nb, nblk))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(nb, -1)[:, :n] % n
    rb, sb = stat(a[idx], b[idx])
    tb = (rb - r0) / sb
    lo, hi = np.quantile(tb, [0.025, 0.975])
    return [float(r0 - hi * se0), float(r0 - lo * se0)]


def expanding_oos(x, y, known_at, start: int, lag: int) -> dict:
    """Expanding-window one-variable OOS forecasts over decisions k >= ``start`` (by position): the forecast of y_k is
    the OLS of y_j on x_j over the pairs with known_at[j] <= k (both finite), against the prevailing mean of the same
    realised y_j. Returns the Clark-West record."""
    x = np.asarray(x, float); y = np.asarray(y, float); ka = np.asarray(known_at)
    rec_y, rec_b, rec_m = [], [], []
    for k in range(start, x.size):
        if not (np.isfinite(x[k]) and np.isfinite(y[k])):
            continue
        tr = (ka <= k) & np.isfinite(x) & np.isfinite(y)
        tr[k:] = False
        if tr.sum() < 30:
            continue
        xs, ys = x[tr], y[tr]
        xm = xs.mean(); vx = float(((xs - xm) ** 2).sum())
        b = float(((xs - xm) * (ys - ys.mean())).sum() / vx) if vx > 0 else 0.0
        a = ys.mean() - b * xm
        rec_y.append(y[k]); rec_b.append(ys.mean()); rec_m.append(a + b * x[k])
    return cw_stats(rec_y, rec_b, rec_m, lag)


# ================================================================================================ signal pieces ==

def ew_ratio(SV, TV, M, floor: int = T673_FLOOR) -> tuple:
    """(x, count): equal-weighted mean of short / total volume over members (M) with total_volume > 0 on each day; NaN
    on a day with fewer than ``floor`` such members."""
    ok = M & np.isfinite(SV) & np.isfinite(TV) & (TV > 0)
    cnt = ok.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.where(ok, SV / np.where(ok, TV, 1.0), 0.0)
        x = R.sum(axis=1) / np.maximum(cnt, 1)
    x = np.where(cnt >= floor, x, np.nan)
    return x, cnt


def dw_ratio(SV, TV, M, P) -> tuple:
    """(DIX, unpriced share): sum short x P / sum total x P over members with total_volume > 0 and a positive price P on
    the day; the share of those members' total (off-exchange) volume that has no price."""
    base = M & np.isfinite(SV) & np.isfinite(TV) & (TV > 0)
    ok = base & np.isfinite(P) & (P > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        num = np.where(ok, SV * np.where(ok, P, 0.0), 0.0).sum(axis=1)
        den = np.where(ok, TV * np.where(ok, P, 0.0), 0.0).sum(axis=1)
        tot = np.where(base, TV, 0.0).sum(axis=1)
        unp = np.where(base & ~ok, TV, 0.0).sum(axis=1)
        x = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
        share = np.where(tot > 0, unp / np.where(tot > 0, tot, 1.0), np.nan)
    return x, share, ok.sum(axis=1)


def trailing_z(x, win: int = T673_WIN) -> np.ndarray:
    """z_t of x_t against the last ``win`` finite values ending at t (t included; sd with ddof 1); NaN before ``win``
    values exist."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    idx = np.flatnonzero(np.isfinite(x))
    v = x[idx]
    for k in range(win - 1, idx.size):
        w = v[k - win + 1:k + 1]
        sd = w.std(ddof=1)
        if sd > 0:
            out[idx[k]] = (v[k] - w.mean()) / sd
    return out


def prior_pct_flag(x, win: int, pct: float, upper: bool) -> tuple:
    """(flag, defined, rank): x_t at or above (``upper``) / at or below the ``pct`` percentile (numpy linear) of the
    ``win`` finite values BEFORE t (t excluded); rank = share of those values strictly below x_t."""
    x = np.asarray(x, float)
    flag = np.zeros(x.size, bool)
    dfd = np.zeros(x.size, bool)
    rank = np.full(x.size, np.nan)
    idx = np.flatnonzero(np.isfinite(x))
    v = x[idx]
    for k in range(win, idx.size):
        w = v[k - win:k]
        q = np.percentile(w, pct)
        i = idx[k]
        dfd[i] = True
        flag[i] = v[k] >= q if upper else v[k] <= q
        rank[i] = float(np.mean(w < v[k]))
    return flag, dfd, rank


def fwd_open_excess(days, cal, opn, bills, h: int) -> tuple:
    """(y, entry idx, exit idx): SPY total-return open(t+1) -> open(t+1+h) simple return minus the bill return
    exp(r x calendar days / 365) - 1 at the DTB3 rate known on file day t; NaN when t is not a session or the exit is
    beyond the data."""
    days = np.asarray(days, np.int64)
    n = cal.size
    i = np.searchsorted(cal, days)
    on = (i < n) & (cal[np.minimum(i, n - 1)] == days)
    e0, e1 = i + 1, i + 1 + h
    y = np.full(days.size, np.nan)
    for k in np.flatnonzero(on & (e1 < n)):
        a, b = opn[e0[k]], opn[e1[k]]
        if not (np.isfinite(a) and np.isfinite(b) and a > 0):
            continue
        r = bills.rate(EV._iso(days[k]))
        y[k] = b / a - 1.0 - (math.exp(r * float(cal[e1[k]] - cal[e0[k]]) / 365.0) - 1.0)
    return y, np.where(on, e0, -1), np.where(on, e1, -1), np.where(on, i, -1)


def touches(e0, e1, cal, lo: str, hi: str) -> np.ndarray:
    """Holds (entry, exit session indices) that touch the calendar window [lo, hi]."""
    lo_e, hi_e = EV._ed(lo), EV._ed(hi)
    e0 = np.asarray(e0); e1 = np.asarray(e1)
    ok = (e0 >= 0) & (e1 >= 0) & (e1 < cal.size)
    out = np.zeros(e0.size, bool)
    out[ok] = (cal[e0[ok]] <= hi_e) & (cal[e1[ok]] >= lo_e)
    return out


# ================================================================================================ shared loads ==

def _bills(archive) -> CAL.Bills:
    return CAL._cached(archive, ("b13_bills",), lambda: CAL.Bills(CAL._series(archive, DTB3_B)))


def _spy(archive) -> dict:
    def load():
        b = EV._yahoo_bars(archive, SPY_B, EV._ed("2008-01-01"))
        return {"cal": b["ed"], "close": b["close"], "adj": b["adj"], "open": b["open"]}
    return CAL._cached(archive, ("b13_spy",), load)


def cnms_data(archive) -> dict:
    """CNMS file days (status ok) x symbols: short and total volume (float64), the backfilled flag per day, the months
    present and the months missing inside their span."""
    def load():
        months = [m for m in EV._months(CNMS_FIRST, CNMS_PROBE_LAST) if B7C._has(archive, CNMS_FMT.format(m))]
        fd, recs = {}, []
        for m in months:
            nm = CNMS_FMT.format(m)
            keep = EV._avail_filter(archive, nm)
            for r in archive.load(nm):
                if not keep(r):
                    continue
                v = r.get("value") or {}
                k = r.get("kind")
                if k == "file-day":
                    if v.get("status", "ok") == "ok" and v.get("day"):
                        fd[EV._ed(v["day"])] = bool(v.get("backfilled"))
                    continue
                if k != "short-volume":
                    continue
                sv, tv = EV._num(v.get("short_volume")), EV._num(v.get("total_volume"))
                if v.get("day") and v.get("symbol") and sv is not None and tv is not None and tv > 0:
                    recs.append((EV._ed(v["day"]), EV.ntick(v["symbol"]), sv, tv))
        days = np.array(sorted(fd), np.int64)
        di = {int(d): i for i, d in enumerate(days)}
        syms = sorted({s for _, s, _, _ in recs})
        si = {s: j for j, s in enumerate(syms)}
        SV = np.full((days.size, len(syms)), np.nan)
        TV = np.full((days.size, len(syms)), np.nan)
        for d, s, sv, tv in recs:
            i = di.get(d)
            if i is not None:
                SV[i, si[s]] = sv
                TV[i, si[s]] = tv
        span = EV._months(months[0], months[-1]) if months else []
        return {"days": days, "iso": [EV._iso(d) for d in days], "syms": syms, "SV": SV, "TV": TV,
                "backfilled": np.array([fd[int(d)] for d in days], bool), "months": months,
                "missing_months": [m for m in span if m not in set(months)]}
    return CAL._cached(archive, ("b13_cnms",), load)


def member_mask(archive, days, syms) -> tuple:
    """(mask days x syms of point-in-time S&P 500 members, last snapshot date): fja snapshots dated on or before t,
    then Wikipedia changes by effective date after the fja file's last date."""
    def load():
        fja = EV._rows(archive, FJA_B)
        chg = [r.get("value") or {} for r in EV._rows(archive, CHG_B)]
        snaps = EV.membership_snapshots(fja, chg)
        eds = [s[0] for s in snaps]
        col = {s: j for j, s in enumerate(syms)}
        M = np.zeros((len(days), len(syms)), bool)
        for i, d in enumerate(days):
            j = bisect.bisect_right(eds, int(d)) - 1
            if j >= 0:
                M[i, [col[s] for s in snaps[j][1] if s in col]] = True
        return M, (EV._iso(snaps[-1][0]) if snaps else None)
    return CAL._cached(archive, ("b13_members", len(days), len(syms)), load)


def base(archive) -> dict:
    """The CNMS panel, membership, the EW ratio, SPY targets (10, 20 and 60 sessions) and the trailing-return control,
    all on the CNMS file days."""
    def load():
        C = cnms_data(archive)
        M, last_snap = member_mask(archive, C["days"], C["syms"])
        x, cnt = ew_ratio(C["SV"], C["TV"], M)
        sp = _spy(archive)
        bills = _bills(archive)
        cal = sp["cal"]
        out = {"C": C, "M": M, "last_snap": last_snap, "x_ew": x, "cnt": cnt, "cal": cal}
        for h in (T673_H, T674_H2, T674_H):
            y, e0, e1, i = fwd_open_excess(C["days"], cal, sp["open"], bills, h)
            out[f"y{h}"], out[f"e0_{h}"], out[f"e1_{h}"] = y, e0, e1
        out["sess"] = i
        out["off_calendar"] = int((i < 0).sum())
        out["sess_sorted"] = np.maximum.accumulate(np.where(i >= 0, i, -1))
        ctrl = np.full(C["days"].size, np.nan)
        ok = (i >= T673_CTRL)
        ctrl[ok] = sp["adj"][i[ok]] / sp["adj"][i[ok] - T673_CTRL] - 1.0
        out["ctrl"] = ctrl
        q = np.full(cal.size, np.nan)
        q[T674_DIP_LAG:] = sp["close"][T674_DIP_LAG:] / sp["close"][:-T674_DIP_LAG]
        dip_s, dip_d, _ = prior_pct_flag(q, T674_RANK_WIN, T674_DIP_PCT, upper=False)
        out["dip"] = np.where(i >= 0, dip_s[np.maximum(i, 0)], False)
        out["dip_def"] = np.where(i >= 0, dip_d[np.maximum(i, 0)], False)
        return out
    return CAL._cached(archive, ("b13_base",), load)


def member_prices(archive) -> dict:
    """Per CNMS file day and symbol: Yahoo's split-adjusted close (NaN without a bar that day) and the split factor
    after the day (as-traded close = close x F), for symbols whose Yahoo series is an EQUITY and passes the FINRA-volume
    identity check; status per symbol."""
    def load():
        B = base(archive)
        C, M = B["C"], B["M"]
        D, S = C["days"].size, len(C["syms"])
        PA = np.full((D, S), np.nan)
        FF = np.ones((D, S))
        status = {}
        for j, s in enumerate(C["syms"]):
            st = SX._stock(archive, EV.ysym(s))
            if st is None:
                status[s] = "no archived daily history"
                continue
            if not SX.is_equity(st):
                status[s] = "Yahoo series is not an EQUITY (reused ticker)"
                continue
            pos = {d: k for k, d in enumerate(st["days"])}
            ks = np.array([pos.get(d, -1) for d in C["iso"]], int)
            ok = ks >= 0
            pa = np.full(D, np.nan); f = np.ones(D); yv = np.full(D, np.nan)
            pa[ok] = st["close"][ks[ok]]
            f[ok] = st["F"][ks[ok]]
            with np.errstate(invalid="ignore", divide="ignore"):
                yv[ok] = st["vol"][ks[ok]] / st["F"][ks[ok]]
            chk = EV.finra_identity(C["TV"][:, j], yv, M[:, j])
            if chk["ok"] is False:
                status[s] = "Yahoo volume disagrees with FINRA's (identity check)"
                continue
            PA[:, j], FF[:, j] = pa, f
            status[s] = "ok" if chk["ok"] else "ok (identity not checkable)"
        return {"PA": PA, "F": FF, "status": status}
    return CAL._cached(archive, ("b13_prices",), load)


# ================================================================================================ T-673 harness ==

def _fmt(x, nd: int = 4) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _bp(x, nd: int = 1) -> str:
    return B7C._bp(x, nd)


def timing_rule(z, days, cal, opn, bills, sess, thr: float, cost: float) -> dict:
    """Daily timing: at the end of file day t hold bills from open t+1 to open t+2 when z_t > thr, else SPY; ``cost``
    per side on each switch. Against buy-and-hold SPY on the same days (annualised over 252 sessions)."""
    r_s, r_b, pos = [], [], []
    for k in range(len(days)):
        i = sess[k]
        if i < 0 or i + 2 >= cal.size or not np.isfinite(z[k]):
            continue
        a, b = opn[i + 1], opn[i + 2]
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        r_s.append(b / a - 1.0)
        r_b.append(math.exp(bills.rate(EV._iso(days[k])) * float(cal[i + 2] - cal[i + 1]) / 365.0) - 1.0)
        pos.append(0.0 if z[k] > thr else 1.0)
    if not r_s:
        return {}
    r_s, r_b, pos = np.array(r_s), np.array(r_b), np.array(pos)
    sw = np.abs(np.diff(np.concatenate([[1.0], pos])))
    strat = pos * r_s + (1 - pos) * r_b - cost * sw
    ex_s, ex_bh = strat - r_b, r_s - r_b
    sh = lambda v: float(v.mean() / v.std(ddof=1) * math.sqrt(252)) if v.std(ddof=1) > 0 else None
    return {"days": int(r_s.size), "share_in_bills": float(1 - pos.mean()), "switches": int(sw.sum()),
            "ann_excess_rule": float(ex_s.mean() * 252), "ann_excess_buy_hold": float(ex_bh.mean() * 252),
            "sharpe_rule": sh(ex_s), "sharpe_buy_hold": sh(ex_bh)}


def b13_short_a_svr_spy_10d(archive):
    """T-673."""
    miss = B7C._missing(archive, [SPY_B, DTB3_B, FJA_B, CHG_B, CNMS_FMT.format(CNMS_FIRST)])
    if miss:
        return miss
    B = base(archive)
    C = B["C"]
    days, iso = C["days"], C["iso"]
    x, cnt = B["x_ew"], B["cnt"]
    skipped = int((cnt < T673_FLOOR).sum())
    z = trailing_z(x, T673_WIN)
    y, ctrl = B[f"y{T673_H}"], B["ctrl"]
    sel = np.isfinite(z) & np.isfinite(y) & np.isfinite(ctrl)
    n = int(sel.sum())
    if n < 30:
        return _out({"n": n}, n, "inconclusive", f"only {n} file days with z, target and control: nothing to test (rule 9)")
    d_sel = np.array(iso)[sel]
    t0 = slope_test(y[sel], z[sel], None)
    t1 = slope_test(y[sel], z[sel], ctrl[sel])
    h1 = np.array([d < T673_SPLIT for d in d_sel])
    halves = {}
    for lab, m in (("2018-08..2022-09", h1), ("2022-10..2026-10", ~h1)):
        halves[lab] = {"no_control": slope_psi(y[sel][m], z[sel][m])["slope"],
                       "control": slope_psi(y[sel][m], z[sel][m], ctrl[sel][m])["slope"], "n": int(m.sum())}
    ok0 = sig(t0["slope"], t0["p_less"], t0["draws"], ALPHA_CELL, "neg")
    ok1 = sig(t1["slope"], t1["p_less"], t1["draws"], ALPHA_CELL, "neg")
    hv = [v for h in halves.values() for v in (h["no_control"], h["control"])]
    rows = [(f"slope {t0['slope'] * 1e4:+.2f} bps per unit z < 0 with one-sided p < {ALPHA_CELL} (no control; p "
             f"{CAL._mc(t0['p_less'], t0['draws'])}, NW t {_fmt(t0['nw_t'], 2)})", ok0,
             CAL.decide_p(t0["p_greater"], t0["draws"], ALPHA_CELL) is True),
            (f"slope {t1['slope'] * 1e4:+.2f} bps per unit z < 0 with one-sided p < {ALPHA_CELL} (trailing 10-session SPY "
             f"return control; p {CAL._mc(t1['p_less'], t1['draws'])}, NW t {_fmt(t1['nw_t'], 2)})", ok1,
             CAL.decide_p(t1["p_greater"], t1["draws"], ALPHA_CELL) is True),
            ("slope negative in both halves with and without the control ("
             + "; ".join(f"{k}: {v['no_control'] * 1e4:+.2f} / {v['control'] * 1e4:+.2f} bps, {v['n']} days"
                         for k, v in halves.items()) + ")", all(v < 0 for v in hv), False)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T673_MIN_N, "file days")

    # ---- reported only
    rep = {}
    sp = _spy(archive)
    known = np.where(B[f"e1_{T673_H}"] >= 0, B[f"e1_{T673_H}"], 10 ** 9)
    # pair j is realised once its exit open has printed: on or before session i_t of decision t (by position)
    sess = B["sess"]
    ka = np.searchsorted(B["sess_sorted"], known, side="left")
    rep["clark_west"] = expanding_oos(z, y, ka, T673_OOS_START, max(T673_H, CAL.nw_lags(n)))
    rep["unconditional_mean_bps"] = float(np.nanmean(y[sel]) * 1e4)
    bf = C["backfilled"]
    xn = np.where(~bf, x, np.nan)
    zn = trailing_z(xn, T673_WIN)
    seln = np.isfinite(zn) & np.isfinite(y) & np.isfinite(ctrl) & ~bf
    rep["non_backfilled"] = ({**slope_test(y[seln], zn[seln], None, escalate=False), "first": str(np.array(iso)[seln][0]),
                              "ctrl_slope": slope_psi(y[seln], zn[seln], ctrl[seln])["slope"]}
                             if seln.sum() > 30 else {"n": int(seln.sum())})
    e0, e1 = B[f"e0_{T673_H}"], B[f"e1_{T673_H}"]
    cal = B["cal"]
    for lab, wins in (("excl_2020-02..06", [T673_REGIMES[0]]), ("excl_2021-01..03", [T673_REGIMES[1]]),
                      ("excl_both", list(T673_REGIMES))):
        keep = sel.copy()
        for lo, hi in wins:
            keep &= ~touches(e0, e1, cal, lo, hi)
        rep[lab] = {"n": int(keep.sum()), "slope": slope_psi(y[keep], z[keep])["slope"],
                    "ctrl_slope": slope_psi(y[keep], z[keep], ctrl[keep])["slope"]}
    y60 = B[f"y{T674_H}"]
    s60 = np.isfinite(z) & np.isfinite(y60)
    rep["cell_ew_60"] = slope_test(y60[s60], z[s60], None, block=2 * T674_H, escalate=False)
    pr = member_prices(archive)
    for lab, P in (("as_traded", pr["PA"] * pr["F"]), ("split_adjusted", pr["PA"])):
        xd, _, _ = dw_ratio(C["SV"], C["TV"], B["M"], P)
        zd = trailing_z(xd, T673_WIN)
        sd_ = np.isfinite(zd) & np.isfinite(y)
        rep[f"cell_dw_10_{lab}"] = slope_test(y[sd_], zd[sd_], None, escalate=False)
    rep["timing_rule"] = timing_rule(z, days, cal, sp["open"], _bills(archive), sess, T673_ZTHR, T673_COST)
    rep["ml_export"] = "not exported (z_t and its 5-day change for T-578 are outside this module)"

    cw = rep["clark_west"]
    nb = rep["non_backfilled"]
    reason = (f"EW off-exchange short-volume ratio over point-in-time S&P 500 members (fja05680 to {B['last_snap']} incl. "
              f"Wikipedia changes), {len(days)} CNMS file days {iso[0]}..{iso[-1]} ({int(C['backfilled'].sum())} "
              f"backfilled; {skipped} skipped below {T673_FLOOR} members; members in file min {int(cnt.min())}, median "
              f"{int(np.median(cnt))}); z over 60 file days; target SPY open(t+1)->open(t+11) minus DTB3, {n} daily starts "
              f"{d_sel[0]}..{d_sel[-1]}: slope {t0['slope'] * 1e4:+.2f} bps/z (p_less {CAL._mc(t0['p_less'], t0['draws'])}), "
              f"with the 10-session return control {t1['slope'] * 1e4:+.2f} (p_less {CAL._mc(t1['p_less'], t1['draws'])}); "
              f"reported: unconditional mean {rep['unconditional_mean_bps']:+.1f} bps; Clark-West OOS R^2 "
              f"{_fmt(cw.get('r2'))} (t {_fmt(cw.get('cw_t'), 2)}, {cw.get('n')} forecasts); non-backfilled days "
              f"{nb.get('n')} slope {_fmt((nb.get('slope') or float('nan')) * 1e4, 2)} bps; EW 60-session cell slope "
              f"{rep['cell_ew_60']['slope'] * 1e4:+.2f} bps (p_less {_fmt(rep['cell_ew_60'].get('p_less'))}); DW 10-session "
              f"cell (as-traded close) {rep['cell_dw_10_as_traded']['slope'] * 1e4:+.2f} bps (p_less "
              f"{_fmt(rep['cell_dw_10_as_traded'].get('p_less'))}); excluding both regimes slope "
              f"{rep['excl_both']['slope'] * 1e4:+.2f} bps; timing rule (bills when z > +1, 1 bp/side) annualised excess "
              f"{_fmt(rep['timing_rule'].get('ann_excess_rule'))} vs buy-and-hold {_fmt(rep['timing_rule'].get('ann_excess_buy_hold'))}")
    stat = {"n": n, "file_days": int(len(days)), "skipped_days": skipped, "backfilled_days": int(C["backfilled"].sum()),
            "members_in_file": {"min": int(cnt.min()), "median": float(np.median(cnt)), "max": int(cnt.max())},
            "missing_months": C["missing_months"], "primary": t0, "control": t1, "halves": halves,
            "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# ================================================================================================ T-674 harness ==

def dix_cell(y, flag, dip, elig, entry_iso, e0, e1, cal, cost: float = T674_COST, block: int = T674_BLOCK,
             pvals: bool = True) -> dict:
    """T-674 statistics on eligible days: signal minus all eligible and signal minus dip-day means, net of ``cost`` on
    the signal leg, with escalated one-sided p's (alpha 0.0125), halves by entry date and the 2020 exclusion."""
    y = np.asarray(y, float)
    m = np.asarray(elig, bool)
    ys, f, dp = y[m], np.asarray(flag, bool)[m], np.asarray(dip, bool)[m]
    ent = np.asarray(entry_iso)[m]
    out = {"n": int(m.sum()), "n_signal": int(f.sum()), "n_dip": int(dp.sum()), "n_both": int((f & dp).sum())}
    if f.sum() < 2 or dp.sum() < 2 or (~f).sum() < 2:
        return out

    def diffs(mask):
        yy, ff, dd = ys[mask], f[mask], dp[mask]
        if ff.sum() == 0 or dd.sum() == 0:
            return None, None
        return float(yy[ff].mean() - yy.mean() - cost), float(yy[ff].mean() - yy[dd].mean() - cost)

    d1, d2 = diffs(np.ones(ys.size, bool))
    out.update(mean_signal=float(ys[f].mean()), mean_all=float(ys.mean()), mean_dip=float(ys[dp].mean()),
               diff_all_net=d1, diff_dip_net=d2)
    if pvals:
        for key, s in (("all", diff_all_series(ys, f) - cost), ("dip", diff_overlap_series(ys, f, dp) - cost)):
            pg, pl, nd = p_escalated(s, block, ALPHA_CELL, "greater")
            out[f"p_{key}"], out[f"p_{key}_less"], out[f"draws_{key}"] = pg, pl, nd
    h1 = np.array([d < T674_SPLIT for d in ent])
    out["halves"] = {"2019-08..2022-12": diffs(h1), "2023-01..2026-08": diffs(~h1)}
    tch = touches(np.asarray(e0)[m], np.asarray(e1)[m], cal, *T674_EXCL)
    out["excl_2020"] = diffs(~tch)
    out["n_excl_2020"] = int((~tch).sum())
    return out


def _dix_rows(cell: dict) -> list:
    """(name, ok, decisive) rows of one reading."""
    r = []
    for key, lab in (("all", "signal minus all eligible days"), ("dip", "signal minus dip days")):
        pt = cell.get(f"diff_{key}_net")
        r.append((lab, sig(pt, cell.get(f"p_{key}"), cell.get(f"draws_{key}", 1), ALPHA_CELL, "pos"),
                  CAL.decide_p(cell.get(f"p_{key}_less"), cell.get(f"draws_{key}", 1), ALPHA_CELL) is True))
    hv = [v for pair in cell.get("halves", {}).values() for v in (pair or (None, None))]
    r.append(("halves", None if any(v is None for v in hv) or not hv else all(v > 0 for v in hv), False))
    ex = cell.get("excl_2020") or (None, None)
    r.append(("excl", None if any(v is None for v in ex) else all(v > 0 for v in ex), False))
    return r


def b13_short_a_dix_spy_60d(archive):
    """T-674."""
    miss = B7C._missing(archive, [SPY_B, DTB3_B, FJA_B, CHG_B, CNMS_FMT.format(CNMS_FIRST)])
    if miss:
        return miss
    B = base(archive)
    C = B["C"]
    cal = B["cal"]
    pr = member_prices(archive)
    y = B[f"y{T674_H}"]
    e0, e1 = B[f"e0_{T674_H}"], B[f"e1_{T674_H}"]
    entry_iso = [EV._iso(cal[k]) if k >= 0 and k < cal.size else "9999" for k in e0]
    readings, dix = {}, {}
    for lab, P in (("as_traded", pr["PA"] * pr["F"]), ("split_adjusted", pr["PA"])):
        xd, share, npriced = dw_ratio(C["SV"], C["TV"], B["M"], P)
        flag, dfd, rank = prior_pct_flag(xd, T674_RANK_WIN, T674_PCT, upper=True)
        elig = dfd & B["dip_def"] & np.isfinite(y) & np.array([d <= T674_LAST_ENTRY for d in entry_iso])
        readings[lab] = dix_cell(y, flag, B["dip"], elig, entry_iso, e0, e1, cal)
        dix[lab] = {"x": xd, "share": share, "npriced": npriced, "flag": flag, "dfd": dfd, "rank": rank, "elig": elig}
    n = min(r["n"] for r in readings.values())
    # the EW 60-session cell (the same rule on the EW ratio)
    fe, de_, _ = prior_pct_flag(B["x_ew"], T674_RANK_WIN, T674_PCT, upper=True)
    elig_e = de_ & B["dip_def"] & np.isfinite(y) & np.array([d <= T674_LAST_ENTRY for d in entry_iso])
    ew = dix_cell(y, fe, B["dip"], elig_e, entry_iso, e0, e1, cal, pvals=False)
    ra, rb = _dix_rows(readings["as_traded"]), _dix_rows(readings["split_adjusted"])
    A, Sd = readings["as_traded"], readings["split_adjusted"]

    def two(key):
        return f"as-traded {_bp(A.get(key))} / split-adjusted {_bp(Sd.get(key))}"

    names = [f"signal-day mean minus all-eligible mean, net of 1 bp per side, > 0 with one-sided p < {ALPHA_CELL} "
             f"({two('diff_all_net')}; p {CAL._mc(A.get('p_all'), A.get('draws_all', 1))} / "
             f"{CAL._mc(Sd.get('p_all'), Sd.get('draws_all', 1))})",
             f"signal-day mean minus dip-day mean, net, > 0 with one-sided p < {ALPHA_CELL} ({two('diff_dip_net')}; p "
             f"{CAL._mc(A.get('p_dip'), A.get('draws_dip', 1))} / {CAL._mc(Sd.get('p_dip'), Sd.get('draws_dip', 1))})",
             "both differences positive in both halves by entry date (as-traded "
             + "; ".join(f"{k}: {_bp(v[0]) if v else 'n/a'} / {_bp(v[1]) if v else 'n/a'}" for k, v in A.get("halves", {}).items())
             + "; split-adjusted "
             + "; ".join(f"{k}: {_bp(v[0]) if v else 'n/a'} / {_bp(v[1]) if v else 'n/a'}" for k, v in Sd.get("halves", {}).items()) + ")",
             f"both differences positive excluding holds touching 2020-02..2020-06 (as-traded "
             f"{' / '.join(_bp(v) for v in (A.get('excl_2020') or (None, None)))}; split-adjusted "
             f"{' / '.join(_bp(v) for v in (Sd.get('excl_2020') or (None, None)))})"]
    rows = [(nm, CAL._agree([a[1], b[1]]), bool(a[2] and b[2])) for nm, a, b in zip(names, ra, rb)]
    ew_ok = (None if ew.get("diff_all_net") is None else bool(ew["diff_all_net"] > 0 and ew["diff_dip_net"] > 0))
    rows.append((f"EW 60-session cell of the same sign, both differences > 0 (sign only; {_bp(ew.get('diff_all_net'))} / "
                 f"{_bp(ew.get('diff_dip_net'))})", ew_ok, False))
    st = pr["status"]
    unpriced = sorted(s for s, v in st.items() if not v.startswith("ok"))
    rows.append((f"registered pre-run fetch of the members Yahoo still serves ({len(unpriced)} of {len(st)} member "
                 f"symbols without a usable archived close) [NOT IMPLEMENTED: the archive lacks them and this harness "
                 f"does not fetch]", None, False))
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T674_MIN_N, "eligible file days")

    # ---- reported only
    rep = {"ew_60": ew}
    D = dix["as_traded"]
    sh = D["share"][D["elig"]]
    rep["unpriced_share_of_member_offexchange_volume"] = {
        "mean": float(np.nanmean(sh)), "median": float(np.nanmedian(sh)), "max": float(np.nanmax(sh)),
        "min": float(np.nanmin(sh))}
    rep["priced_members_per_day"] = {"min": int(D["npriced"][D["elig"]].min()), "median": float(np.median(D["npriced"][D["elig"]]))}
    rep["symbol_status"] = {k: sum(1 for v in st.values() if v == k) for k in sorted(set(st.values()))}
    rep["unpriced_symbols"] = unpriced
    y20 = B[f"y{T674_H2}"]
    rep["h20"] = {lab: dix_cell(y20, dix[lab]["flag"], B["dip"], dix[lab]["dfd"] & B["dip_def"] & np.isfinite(y20),
                                entry_iso, B[f"e0_{T674_H2}"], B[f"e1_{T674_H2}"], cal, pvals=False)
                  for lab in dix}
    lvl = np.isfinite(D["x"]) & (D["x"] >= T674_LEVEL)
    rep["level_45pct"] = dix_cell(y, lvl, B["dip"], D["elig"], entry_iso, e0, e1, cal, pvals=False)
    known = np.where(e1 >= 0, e1, 10 ** 9)
    ka = np.searchsorted(B["sess_sorted"], known, side="left")
    rk = np.where(D["elig"], D["rank"], np.nan)
    rep["clark_west_rank"] = expanding_oos(rk, y, ka, int(np.flatnonzero(D["elig"])[0]) + T674_OOS_START
                                           if D["elig"].any() else 0, max(T674_H, CAL.nw_lags(n)))
    rep["with_2020"] = {k: A.get(k) for k in ("diff_all_net", "diff_dip_net")}
    rep["without_2020"] = A.get("excl_2020")
    rep["squeezemetrics_dix_correlation"] = None
    rep["notes"] = ("SqueezeMetrics' published DIX is not archived (correlation not computed); the 45% level rule is "
                    "not transferable (CNMS adds ORF/ADF and keeps exempt volume)")
    first = next((d for d, e in zip(C["iso"], D["elig"]) if e), None)
    last = next((d for d, e in zip(reversed(C["iso"]), reversed(list(D["elig"]))) if e), None)
    reason = (f"dollar-weighted CNMS short-volume ratio ('DIX') over point-in-time S&P 500 members with an archived close, "
              f"{n} eligible file days {first}..{last} (trailing-252-file-day 80th-percentile rule; dip days = SPY 5-day "
              f"return in the bottom quintile of the prior 252 sessions); target SPY open(t+1)->open(t+61) minus DTB3. "
              f"As-traded close: {A.get('n_signal')} signal days, mean {_bp(A.get('mean_signal'))} vs all {_bp(A.get('mean_all'))} "
              f"vs dip {_bp(A.get('mean_dip'))}; net differences {_bp(A.get('diff_all_net'))} / {_bp(A.get('diff_dip_net'))} "
              f"(p {_fmt(A.get('p_all'))} / {_fmt(A.get('p_dip'))}); split-adjusted close {_bp(Sd.get('diff_all_net'))} / "
              f"{_bp(Sd.get('diff_dip_net'))}. EW 60-session cell {_bp(ew.get('diff_all_net'))} / {_bp(ew.get('diff_dip_net'))}. "
              f"SURVIVORSHIP: member closes come from the archive's 901-symbol daily-history set (today's universe): "
              f"{len(unpriced)} of {len(st)} member symbols have no usable close and are dropped from both sums, a median "
              f"{rep['unpriced_share_of_member_offexchange_volume']['median'] * 100:.1f}% (max "
              f"{rep['unpriced_share_of_member_offexchange_volume']['max'] * 100:.1f}%) of member off-exchange volume; the "
              f"registered pre-run fetch was not done. Reported: 20-session as-traded {_bp(rep['h20']['as_traded'].get('diff_all_net'))} / "
              f"{_bp(rep['h20']['as_traded'].get('diff_dip_net'))}; Clark-West OOS R^2 of the 60-session return on the trailing "
              f"rank {_fmt(rep['clark_west_rank'].get('r2'))} (t {_fmt(rep['clark_west_rank'].get('cw_t'), 2)}); 45% level rule "
              f"{rep['level_45pct'].get('n_signal')} days, {_bp(rep['level_45pct'].get('diff_all_net'))} / "
              f"{_bp(rep['level_45pct'].get('diff_dip_net'))}")
    stat = {"n": n, "readings": readings, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# ================================================================================================ T-672 harness ==

def si_releases(archive) -> list:
    """One dict per archived FINRA short-interest release (settlement order): available_at epoch, the universe means
    (x: mean log(1 + SI/ADV), v: mean log ADV) and their no-revision, company-class-only and ETF-diagnostic variants,
    the universe's symbols and row counts."""
    def load():
        out = []
        for nm in SX._entry_names(archive, SI_PREFIX):
            settle = nm[len(SI_PREFIX):]
            av = None
            acc = {k: ([], []) for k in ("all", "norev", "company", "etf")}
            syms = set()
            for r in SX._stream(archive, nm):
                v = r.get("value") or {}
                try:
                    a = SX._ts(r["available_at"])
                    av = a if av is None else max(av, a)
                except (KeyError, ValueError, TypeError):
                    pass
                si, adv = SX._num(v.get("currentShortPositionQuantity")), SX._num(v.get("averageDailyVolumeQuantity"))
                if not (adv >= SI_ADV_MIN and si >= 0):
                    continue
                name = v.get("issueName") or ""
                dtc, lv = math.log1p(si / adv), math.log(adv)
                if SI_EXCLUDE.search(name):
                    if SI_ETF_DIAG.search(name):
                        acc["etf"][0].append(dtc); acc["etf"][1].append(lv)
                    continue
                acc["all"][0].append(dtc); acc["all"][1].append(lv)
                syms.add((v.get("symbolCode") or "").strip().upper())
                if not v.get("revisionFlag"):
                    acc["norev"][0].append(dtc); acc["norev"][1].append(lv)
                if (v.get("marketClassCode") or "") in FINRA_COMPANY_CLASSES:
                    acc["company"][0].append(dtc); acc["company"][1].append(lv)
            rec = {"settle": settle, "av": av, "syms": frozenset(syms)}
            for k, (a_, b_) in acc.items():
                rec[f"x_{k}"] = float(np.mean(a_)) if a_ else float("nan")
                rec[f"v_{k}"] = float(np.mean(b_)) if b_ else float("nan")
                rec[f"n_{k}"] = len(a_)
            out.append(rec)
        return out
    return CAL._cached(archive, ("b13_si",), load)


def detrend_z(x) -> np.ndarray:
    """Residuals of x on an OLS line in the release index, divided by the residual sd (ddof 2): the reading-(A)
    transformation of x_1..x_r at origin r (NaN below 3 points)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return np.full(n, np.nan)
    t = np.arange(n, dtype=float)
    A = np.column_stack([np.ones(n), t])
    b, *_ = np.linalg.lstsq(A, x, rcond=None)
    e = x - A @ b
    sd = math.sqrt(float(e @ e) / (n - 2)) if n > 2 else 0.0
    return e / sd if sd > 0 else np.full(n, np.nan)


def realtime_z(x) -> np.ndarray:
    """Reading (B): z_s = the last element of ``detrend_z(x[:s + 1])``, fixed when release s is published."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    for s in range(2, x.size):
        out[s] = detrend_z(x[:s + 1])[-1]
    return out


def _ols_pred(Y, X, xnew) -> tuple:
    """(forecast, coefficients) of y = a + X b at xnew."""
    Z = np.column_stack([np.ones(Y.size), X])
    b, *_ = np.linalg.lstsq(Z, Y, rcond=None)
    return float(np.concatenate([[1.0], np.atleast_1d(xnew)]) @ b), b


def si_oos(x, v, y, av, real_ts, reading: str, start: int = SI_FIRST_OOS, train_drop=None) -> dict:
    """Recursive OOS forecasts of y_k at each origin k >= ``start`` with finite y_k: prevailing mean, the index
    (one-variable), the placebo (one-variable) and both. Training pairs: j < k with y_j realised before the decision
    (real_ts[j] < av[k]), not dropped by ``train_drop``. ``reading`` 'A' re-detrends 1..k at origin k, 'B' uses the
    values fixed at publication."""
    x, v, y = (np.asarray(a, float) for a in (x, v, y))
    av, real_ts = np.asarray(av, float), np.asarray(real_ts, float)
    zxB, zvB = (realtime_z(x), realtime_z(v)) if reading == "B" else (None, None)
    rec = []
    for k in range(start, y.size):
        if not np.isfinite(y[k]):
            continue
        if reading == "A":
            zx, zv = detrend_z(x[:k + 1]), detrend_z(v[:k + 1])
        else:
            zx, zv = zxB[:k + 1], zvB[:k + 1]
        tr = np.zeros(k + 1, bool)
        tr[:k] = (real_ts[:k] < av[k]) & np.isfinite(y[:k])
        if train_drop is not None:
            tr[:k] &= ~np.asarray(train_drop, bool)[:k]
        bench = float(y[:k + 1][tr].mean()) if tr.any() else float("nan")
        tm = tr & np.isfinite(zx) & np.isfinite(zv)
        if tm.sum() < 10 or not (np.isfinite(zx[k]) and np.isfinite(zv[k])):
            continue
        Y = y[:k + 1][tm]
        f1, b1 = _ols_pred(Y, zx[tm], zx[k])
        fp, _ = _ols_pred(Y, zv[tm], zv[k])
        f2, _ = _ols_pred(Y, np.column_stack([zx[tm], zv[tm]]), np.array([zx[k], zv[k]]))
        rec.append((k, float(y[k]), bench, f1, fp, f2, float(b1[1]), float(zx[k])))
    return {"rec": rec}


def si_eval(o: dict, settle: Sequence[str], lag: int = SI_NW_LAG, ci: bool = True) -> dict:
    rec = o["rec"]
    if len(rec) < 10:
        return {"n": len(rec)}
    arr = np.array([r[1:7] for r in rec], float)
    y, fb, f1, fp, f2, b1 = (arr[:, i] for i in range(6))
    cw1 = cw_stats(y, fb, f1, lag)
    cw2 = cw_stats(y, fp, f2, lag)
    ks = [r[0] for r in rec]
    h1 = np.array([settle[k] < SI_SPLIT for k in ks])
    out = {"n": len(rec), "cw_pm": cw1, "cw_placebo": cw2,
           "slopes": {"2020-12..2023-10": {"n": int(h1.sum()), "share_negative": float(np.mean(b1[h1] < 0)) if h1.any() else None,
                                           "mean": float(b1[h1].mean()) if h1.any() else None,
                                           "all_negative": bool(h1.any() and np.all(b1[h1] < 0))},
                      "2023-11..2026-09": {"n": int((~h1).sum()), "share_negative": float(np.mean(b1[~h1] < 0)) if (~h1).any() else None,
                                           "mean": float(b1[~h1].mean()) if (~h1).any() else None,
                                           "all_negative": bool((~h1).any() and np.all(b1[~h1] < 0))}},
           "first": settle[ks[0]], "last": settle[ks[-1]]}
    if ci:
        out["r2_ci"] = r2_ci(y - fb, y - f1, SI_BLOCK)
        out["r2_placebo_ci"] = r2_ci(y - fp, y - f2, SI_BLOCK)
    return out


def _si_rows(e: dict) -> list:
    c1, c2 = e.get("cw_pm") or {}, e.get("cw_placebo") or {}
    p1, p2 = c1.get("p"), c2.get("p")
    sl = e.get("slopes") or {}
    rows = [(None if p1 is None else bool(p1 < ALPHA), p1 is not None and (1 - p1) < ALPHA),
            (None if p2 is None else bool(p2 < ALPHA), p2 is not None and (1 - p2) < ALPHA),
            (None if not sl else all(h["all_negative"] for h in sl.values()), False),
            (None if c1.get("r2") is None else bool(c1["r2"] > 0),
             bool((e.get("r2_ci") or [None, None])[1] is not None and e["r2_ci"][1] < 0))]
    return rows


def si_targets(archive, recs: list, h: Optional[int] = None) -> dict:
    """Entry sessions (first SPY close strictly after available_at) and log excess returns: to the next release's entry
    (h None) or over h sessions; realised timestamps (the exit close, 16:00 ET)."""
    cal = SX._sessions(archive)
    days, adj = CAL._daily(archive, SPY_B, "adjclose")
    pos = {d: i for i, d in enumerate(days)}
    A = np.array([adj[pos[d]] if d in pos else np.nan for d in cal.days], float)
    bills = _bills(archive)
    R = len(recs)
    e = np.array([cal.entry_after(r["av"]) if r["av"] is not None else len(cal) for r in recs], int)
    y = np.full(R, np.nan)
    real = np.full(R, np.inf)
    ex = np.full(R, -1)
    for k in range(R):
        x1 = (e[k + 1] if k + 1 < R else len(cal)) if h is None else e[k] + h
        if e[k] < len(cal) and x1 < len(cal) and x1 > e[k] and np.isfinite(A[e[k]]) and np.isfinite(A[x1]):
            r = bills.rate(cal.days[e[k]])
            dd = (date.fromisoformat(cal.days[x1]) - date.fromisoformat(cal.days[e[k]])).days
            y[k] = math.log(A[x1] / A[e[k]]) - r * dd / 365.0
            real[k] = cal.close[x1]
            ex[k] = x1
    return {"y": y, "real": real, "entry": e, "exit": ex, "cal": cal}


def b13_short_a_aggregate_si(archive):
    """T-672."""
    miss = B7C._missing(archive, [SPY_B, DTB3_B, SI_FIRST_B])
    if miss:
        return miss
    recs = si_releases(archive)
    recs = [r for r in recs if r["av"] is not None and np.isfinite(r["x_all"])]
    R = len(recs)
    if R < SI_FIRST_OOS + 10:
        return _out({"releases": R}, 0, "inconclusive", f"only {R} usable FINRA releases: nothing to test (rule 9)")
    settle = [r["settle"] for r in recs]
    av = np.array([r["av"] for r in recs], float)
    x = np.array([r["x_all"] for r in recs]); v = np.array([r["v_all"] for r in recs])
    T = si_targets(archive, recs)
    y, real = T["y"], T["real"]
    ev = {}
    for rd in ("A", "B"):
        ev[rd] = si_eval(si_oos(x, v, y, av, real, rd), settle)
    n = min(e.get("n", 0) for e in ev.values())
    rA, rB = _si_rows(ev["A"]), _si_rows(ev["B"])
    EA, EB = ev["A"], ev["B"]

    def cwtxt(key):
        return " / ".join(f"t {_fmt((E.get(key) or {}).get('cw_t'), 2)}, p {_fmt((E.get(key) or {}).get('p'))}"
                          for E in (EA, EB))

    sl = lambda E: "; ".join(f"{k}: {h['share_negative'] * 100:.0f}% negative, mean {h['mean'] * 1e4:+.2f} bps/z"
                             for k, h in (E.get("slopes") or {}).items() if h.get("mean") is not None)
    names = [f"Clark-West one-sided p < 0.05 vs the prevailing mean (re-detrended A / fixed-at-publication B: {cwtxt('cw_pm')})",
             f"Clark-West one-sided p < 0.05 of index + volume placebo vs the placebo-only forecast ({cwtxt('cw_placebo')})",
             f"recursive slope negative at every OOS origin of both halves (A: {sl(EA)} | B: {sl(EB)})",
             f"OOS R^2 vs the prevailing mean > 0, the claim's 'positive OOS R^2' (A {_fmt((EA.get('cw_pm') or {}).get('r2'))} "
             f"CI {[round(c, 4) if c is not None else None for c in (EA.get('r2_ci') or [None, None])]} / B "
             f"{_fmt((EB.get('cw_pm') or {}).get('r2'))})"]
    rows = [(nm, CAL._agree([a[0], b[0]]), bool(a[1] and b[1])) for nm, a, b in zip(names, rA, rB)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, SI_MIN_N, "OOS releases")

    # ---- reported only
    rep = {}
    for lab in ("norev", "company"):
        xx = np.array([r[f"x_{lab}"] for r in recs]); vv = np.array([r[f"v_{lab}"] for r in recs])
        rep[lab] = si_eval(si_oos(xx, vv, y, av, real, "A"), settle, ci=False)
    xe = np.array([r["x_etf"] for r in recs]); ve = np.array([r["v_etf"] for r in recs])
    rep["etf_diagnostic"] = {"corr_level_with_index": float(np.corrcoef(xe, x)[0, 1]) if np.isfinite(xe).all() else None,
                             "corr_change_with_index": float(np.corrcoef(np.diff(xe), np.diff(x))[0, 1]) if np.isfinite(xe).all() else None,
                             "oos": si_eval(si_oos(xe, ve, y, av, real, "A"), settle, ci=False) if np.isfinite(xe).all() else None,
                             "rows_median": float(np.median([r["n_etf"] for r in recs]))}
    drop = np.array([T["exit"][k] >= 0 and T["cal"].days[T["entry"][k]] <= SI_EXCL[1] and T["cal"].days[T["exit"][k]] >= SI_EXCL[0]
                     for k in range(R)])
    rep["excl_2020_training"] = si_eval(si_oos(x, v, y, av, real, "A", train_drop=drop), settle, ci=False)
    for hh in SI_HORIZONS:
        Th = si_targets(archive, recs, hh)
        rep[f"h{hh}"] = si_eval(si_oos(x, v, Th["y"], av, Th["real"], "A"), settle,
                                lag=max(SI_NW_LAG, math.ceil(hh / 10)), ci=False)
    # timing rule over the OOS origins of reading A
    tr = []
    prev = 1.0
    sw = 0
    oA = si_oos(x, v, y, av, real, "A")
    bills = _bills(archive)
    for (k, yk, fb, f1, fp, f2, b1, zk) in oA["rec"]:
        e0, e1 = T["entry"][k], T["exit"][k]
        dd = (date.fromisoformat(T["cal"].days[e1]) - date.fromisoformat(T["cal"].days[e0])).days
        rb = bills.rate(T["cal"].days[e0]) * dd / 365.0
        pos = 0.0 if zk > SI_ZTHR else 1.0
        cost = SI_COST if pos != prev else 0.0
        sw += int(pos != prev)
        spy_log = yk + rb
        strat = math.log(pos * math.exp(spy_log) + (1 - pos) * math.exp(rb) - cost)
        tr.append((strat - rb, yk, pos))
        prev = pos
    if tr:
        t_ = np.array(tr)
        rep["timing_rule"] = {"periods": len(t_), "share_in_bills": float(1 - t_[:, 2].mean()), "switches": sw,
                              "sum_log_excess_rule": float(t_[:, 0].sum()), "sum_log_excess_buy_hold": float(t_[:, 1].sum())}
    nm_ = [r["n_all"] for r in recs]
    new_share, first_seen = [], {}
    for k, r in enumerate(recs):
        for s in r["syms"]:
            first_seen.setdefault(s, k)
        if k >= SI_NEW_WIN:
            new_share.append(float(np.mean([first_seen[s] > k - SI_NEW_WIN for s in r["syms"]])))
    gaps = np.diff([date.fromisoformat(s).toordinal() for s in settle])
    rep["names_per_release"] = {"min": int(min(nm_)), "median": float(np.median(nm_)), "max": int(max(nm_)),
                                "first": int(nm_[0]), "last": int(nm_[-1])}
    rep["share_first_seen_last_24"] = {"mean": float(np.mean(new_share)) if new_share else None,
                                       "last": new_share[-1] if new_share else None}
    rep["max_release_gap_days"] = int(gaps.max()) if gaps.size else None
    rep["sec_cover_shares_variant"] = "not computed (SEC cover-share mapping is outside this harness's 5-minute budget)"
    rep["goyal_sii_correlation"] = None
    reason = (f"FINRA aggregate short-interest index (mean log(1 + SI/ADV), raw fields, ADV >= 100k, fund/SPAC/ADR/"
              f"warrant/unit/right/preferred/note regex), {R} releases {settle[0]}..{settle[-1]} (names per release "
              f"{rep['names_per_release']['first']}..{rep['names_per_release']['last']}, max gap {rep['max_release_gap_days']} "
              f"days); y = SPY log excess return entry->next entry; {n} OOS releases from {EA.get('first')}: reading A "
              f"(re-detrended at each origin) CW vs prevailing mean t {_fmt((EA.get('cw_pm') or {}).get('cw_t'), 2)}, OOS R^2 "
              f"{_fmt((EA.get('cw_pm') or {}).get('r2'))}; vs placebo t {_fmt((EA.get('cw_placebo') or {}).get('cw_t'), 2)}; "
              f"reading B (fixed at publication) t {_fmt((EB.get('cw_pm') or {}).get('cw_t'), 2)} / "
              f"{_fmt((EB.get('cw_placebo') or {}).get('cw_t'), 2)}, R^2 {_fmt((EB.get('cw_pm') or {}).get('r2'))}. "
              f"Reported: no-revision rows t {_fmt((rep['norev'].get('cw_pm') or {}).get('cw_t'), 2)}; company classes t "
              f"{_fmt((rep['company'].get('cw_pm') or {}).get('cw_t'), 2)}; 1m t {_fmt((rep['h21'].get('cw_pm') or {}).get('cw_t'), 2)}, "
              f"3m t {_fmt((rep['h63'].get('cw_pm') or {}).get('cw_t'), 2)}; training without 2020-02..06 t "
              f"{_fmt((rep['excl_2020_training'].get('cw_pm') or {}).get('cw_t'), 2)}; timing rule log excess "
              f"{_fmt((rep.get('timing_rule') or {}).get('sum_log_excess_rule'))} vs buy-and-hold "
              f"{_fmt((rep.get('timing_rule') or {}).get('sum_log_excess_buy_hold'))}; no survivorship (FINRA rows include "
              f"later-delisted names; the target is SPY)")
    stat = {"n": n, "releases": R, "readings": ev, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


HARNESSES = {"b13_short_a_svr_spy_10d": b13_short_a_svr_spy_10d,
             "b13_short_a_dix_spy_60d": b13_short_a_dix_spy_60d,
             "b13_short_a_aggregate_si": b13_short_a_aggregate_si}
THEORY_MAP = {"T-673": "b13_short_a_svr_spy_10d", "T-674": "b13_short_a_dix_spy_60d",
              "T-672": "b13_short_a_aggregate_si"}
