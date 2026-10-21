"""
Batch 13, group ``volume_a``: five volume claims pre-registered from the 2026-10-20 web sweep (cluster "volume"):
short-term momentum in high-turnover large caps (T-691), the daily return x abnormal-volume interaction by size
(T-698), the high-volume return premium on visibility weeks (T-692), aggregate Amihud illiquidity timing IWM (T-693)
and detrended aggregate turnover predicting the equal-weighted 12-month return (T-694).
=====================================================================================================================

  * T-691  Point-in-time S&P 500 members (fja05680 + later Wikipedia changes) with a Yahoo price and SEC shares. At each
           month-end, independent median splits on the month's total return and share turnover (split-adjusted volume /
           shares on the same basis); value-weighted long high-turnover winners, short high-turnover losers, filled at
           the next session's close, held to the next fill; 10 bp per side on traded weight, 0.5%/yr borrow on the short
           leg. Holding months 2010-01..2026-09; a month counts only when >= 80% of that day's members have a price and
           shares. Pass: >= 180 eligible months, net mean > 0 with one-sided Newey-West (6) p < 0.05, studentized CBB
           (12-month blocks) lower 95% bound > 0, mean > 0 over 2019-01..2026-09, both halves (2010-01..2017-12,
           2018-01..2026-09) positive, FF5+UMD alpha > 0, DSR >= 0.95 over the 4 declared trials (primary; skip-3 lag
           variant filled at the month-end close; STREV low-minus-high r(m); 12-1 momentum). MDE reported.
  * T-698  Daily Fama-MacBeth regressions within trailing-dollar-volume size terciles of point-in-time members,
           2005-01..2026-09: open(t+1)->open(t+2) return on r(t), r(t) x AV(t), AV(t), log trailing dollar volume and
           trailing 20-day volatility; AV = log volume minus its trailing 60-day mean, demeaned across the day's members.
           Pass: >= 4,000 regression days, top-tercile mean interaction < 0 with NW (5) t < -2.8 AND bottom-tercile > 0
           with t > 2.8, the same signs in 2005-2015 and 2016-2026.
  * T-692  Weekly visibility shocks on point-in-time members, 2008-01..2026-09: idiosyncratic volume surprise (log weekly
           volume minus its trailing 49-week mean, minus the week's cross-sectional mean) in the week's top decile with
           |weekly return| <= the trailing 52-week sigma. 20-session beta-adjusted return (trailing 252-session beta vs
           SPY) from the next week's first open, net of a 10 bp round trip. Pass: >= 800 events, mean net >= +50 bp with a
           date-clustered 95% lower bound > 0, block-shift placebo (2,000 within-name shifts) p < 0.01, calendar-time HAC
           t >= 2, both halves (2008-2016, 2017-2026) positive, DSR >= 0.95 counting T-419's 36 cells plus this one.
  * T-693  Log aggregate Amihud ILLIQ of point-in-time members (mean |r| / dollar volume in $m, >= 15 valid days, price
           > $5), scaled by ^GSPC(first month) / ^GSPC(m-1); expected ILLIQ = the expanding AR(1) forecast. Next-month IWM
           excess return on it, expanding fits from 1997 data, forecasts for target months 2005-01..2026-09. Pass: >= 240
           OOS months, IWM R2_OS > 0 with Clark-West p < 0.05 after Holm over the 3 targets (IWM, SPY, IWM-SPY) and the
           liquidity family (T-694, T-421), slope > 0 in both halves, and a hold-IWM-when-expected-ILLIQ-is-in-its-
           trailing-top-tercile rule (bills otherwise, 5 bp per switch) beating buy-and-hold IWM's net Sharpe with
           stationary-bootstrap (mean block 6) p < 0.05.
  * T-694  Detrended aggregate turnover: mean over members with 60 months of own volume history of log monthly volume
           minus the name's trailing 60-month mean of it, known at month-end. Target: the next 12 months' log excess
           return of the members' equal-weighted (monthly rebalanced) portfolio over DTB3. Pass: >= 200 OOS forecasts
           (first target month 2005-01), slope < 0 with Hodrick (1992) 1B p < 0.05, R2_OS > 0 with Clark-West p < 0.05
           after family Holm (T-693, T-398, T-449, T-458), and a negative slope excluding 2008-09 and excluding 2020.

Readings fixed before any run (the registrations are silent or ambiguous; each is the conservative one):
  * Universe (all five). Membership = fja05680 snapshots with Wikipedia changes after fja's last date, as of each
    session (T-473's construction, ``batch6c_stockxs._member_sets``). T-473's reused-ticker checks: a Yahoo series is a
    stock only when its meta says EQUITY; the ticker-spell check applies the removed-member name test PER SPELL
    (``fja-sp500-ticker-spells``): each spell that ended with a leave for which Wikipedia records a removal name within
    31 days must agree with a name the instrument carried (Yahoo longName, the SEC map and conformed / former names),
    otherwise that spell's member-days are unpriced (a reused ticker's earlier company is never priced with the current
    company's bars); spells without a recorded removal name are kept (as T-473). The session calendar is ^GSPC's bars
    from 1990 (identical to SPY's after 1993-02). Prices come from the shared daily panel (``panel_cache``), which is
    TODAY's 901-symbol universe: removed, acquired and renamed members are under-represented. Every reason states the
    share of member-days / months without a usable price. SEC CIKs come from the current SEC map (delisted names have
    none).
  * Point in time. A daily bar is known at its close. SEC shares enter at their available_at (min of acceptance and
    the filing date 22:00 ET) and must be available at the formation close (16:00 ET); the split factor after the
    fact's cover date puts them on Yahoo's fetch-date basis. Cboe VIX closes are never used for a same-day decision
    (T-693's VIX control uses the previous session's close). DTB3 is the print dated before each day
    (``batch6b_bw.Bills``).
  * T-691: "have both a price and shares" = a bar at the formation close and a usable cap; the 80% share's denominator
    is every fja member that day, priced or not. Multi-class issuers (T-393's rule): the listed classes of a CIK are
    the archived Yahoo EQUITY series the SEC map assigns to it; each gets an equal part of the cover count at its own
    price, and none gets a cap when the classes' raw prices are more than 2x apart (BRK-A / BRK-B). Ties at a median
    join neither side. Costs 10 bp x sum |w_new - drifted w_old| over both legs (first entry and final exit charged; a
    book is closed when the next month is ineligible, its exit cost charged to the last eligible month); borrow
    0.5%/yr x the hold's calendar days / 365 on the short leg. The 12-1 baseline: return from the end of m-12 to the
    end of m-1, the same median split and value weights. "CBB 95% lower bound" = the lower end of the studentized CBB
    two-sided 95% interval (5 seeds x 5,000 draws, escalated when Monte Carlo error cannot resolve it). FF5 + UMD
    compounded over each hold, holds ending by the factors' last day (2026-08-31). Flip bound: the long-short return
    the absent members (no price or no shares) would need, on their share of member-months, to bring the net mean to
    zero.
  * T-698: "trailing 60-day mean" of log volume = sessions t-60..t-1 (all 60 with positive volume); dollar volume =
    close x volume (split-invariant); size = the median over sessions t-59..t (all 60 finite); volatility = sd of the
    20 daily returns ending at t; the dependent return uses opens adjusted by the same day's adjclose/close ratio
    (dividends on ex-dates). Each tercile regression needs >= 30 names; a regression day is a day with both the top and
    the bottom tercile fitted. Decisive failure (rule 5): the opposite sign with |t| > 2.8.
  * T-692: weeks = ISO weeks of the session calendar; a week counts for a name with a bar and finite volume on every
    session of the week; weekly return = adjclose last close to last close; surprise and sigma use weeks w-49..w-1 /
    w-52..w-1 (all valid); the top decile = surprise >= the week's 90th percentile among members. Exit at the open 20
    sessions after the entry open; an event whose exit lies after the data end is dropped. Beta = OLS slope of daily
    close-to-close returns on SPY's over the 252 sessions ending at the event week's close (>= 200 valid pairs).
    "Beta-adjusted return" is read two ways (rule 11): W - beta x SPY and the CAPM form (W - rf) - beta (SPY - rf); a
    criterion passes only when both pass. Calendar-time portfolio: each session the equal-weighted mean of the active
    events' open-to-open abnormal returns (5 bp on the first and on the last interval), Newey-West lag 20 (the hold).
    The DSR counts T-419's 36 cells whose Sharpes are not computed here, so the criterion is ``dsr bound`` (fails when
    the DSR at the most favourable 1/(T-1) trial-Sharpe variance misses 0.95; undecided otherwise): this claim can be
    refuted but not supported here. Reported only: size terciles, the bottom-decile low-volume bucket, the share of
    events 5-35 days before a 10-Q/10-K acceptance, VIX > 30 weeks, 2020-21, coverage and the flip bound.
  * T-693: ILLIQ uses members at the month's last session; |r_d| from adjclose, dollar volume = split-adjusted close x
    split-adjusted volume; price > $5 = the raw price (close x later split factor) at the month's last session; the
    tickers must appear in the spells bundle. First month of the series: 1997-01. The AR(1) is refitted each month on
    months 1997-01..m; the predictive regression at the end of m uses the pairs (X_j, y_{j+1}) with j + 1 <= m, its
    benchmark their mean; at least 36 pairs. Clark-West: Newey-West lag 12. "Trailing top tercile": the expanding
    history of the real-time signal (X_m >= its 2/3 quantile over every month up to m). Sharpe difference p: stationary
    bootstrap (mean block 6, 5,000 draws) of the paired monthly series, p = share of centred draws >= the observed
    difference. External family p's (recorded results): T-421 0.373 (its shock coefficient p); T-694 computed here.
  * T-694: own history = 60 valid months before m (a valid month has a bar and finite volume on every session); the
    target is the sum of 12 monthly log excess returns (so Hodrick's 1B s.e. applies exactly); the EW portfolio is the
    members as of each month's start with a bar at both month-ends (a series ending inside a month earns its return to
    its last bar). Expanding fits use pairs whose target ended by the origin (j <= m - 12), >= 36 pairs. Clark-West
    Newey-West lag 12. "Same sign excluding 2008-09 / 2020" = the Hodrick slope over the claim window with every origin
    whose 12-month target overlaps the excluded period removed; both must be negative. Family Holm: T-693 computed
    here; recorded p's T-398 0.824 (its Hansen-Hodrick t +0.93 against the negative-slope claim), T-449 0.125 (normal p
    from its recorded mean and studentized CI, approximate), T-458 0.481 (its Holm-deflated Clark-West p; the raw 0.047
    is reported: a larger external p can only make the Holm criterion harder).
  * Data-validity filters added AFTER the first runs (disclosed; neither uses an outcome, and neither is a threshold of
    any registered rule). (a) T-691's first run used raw SEC cover counts: 149 jumps of more than 10x between
    consecutive filings are XBRL unit errors (EXC 2010-03 filed x1e6, PKG 2024-05 x1e3, FOXA's only fact '1.0'), which
    put EXC's cap at $25 quadrillion and made the value weights meaningless. ``unit_filter`` now refuses a share count
    whose implied formation-month turnover lies outside [0.2%, 2,000%] (point in time); first-run net mean +0.145%
    (78 months) -> +0.183% after it. (b) T-693's inspection of its ILLIQ cross-section showed reused tickers the
    name check cannot catch before 2007 (Wikipedia records few removals then): FCN (FTI Consulting standing in for
    First Chicago NBD), CCU, BBT, SNT, CSR, WEN before 2008, CNC, AIT, MCIC, PARA. ``identity_mask`` (in the shared
    base, so every harness) now unprices a member-day whose trailing 60-session median dollar volume is below 1/40 of
    that day's member median (genuine members' lowest ratio in 2010-2026 is about 1/28, NWS). T-698, T-692 and T-691
    were rerun with it: verdicts unchanged (T-698 bottom t -1.04 -> -1.36; T-692 plain -5.8 -> -6.7 bp; T-691
    +0.183% -> +0.185%).
  * Not computed (outside every verdict): T-691's and T-698's declared T-578 ML side cells (r1m x TO1m, r1 x
    lv_rel20). T-693 reports, unjudged, the 60-month trailing tercile rule and the market scaling the other way round
    (x ^GSPC(m-1) / ^GSPC(first), Acharya-Pedersen's orientation): the registration's own formula divides by ^GSPC(m-1),
    which steepens the downward trend of the series, so the expanding top tercile is almost never reached after 2005.
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``, house rule 5). House rule 10: every claim here names its calendar (month-ends, ISO weeks,
    every session), so there is no free grid phase.
"""

from __future__ import annotations

import bisect
import gc
import math
import warnings
from collections import defaultdict
from datetime import date, timedelta
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.batch6c_rates import hac_mean
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()
Z_MDE = 1.6448536269514722 + 0.8416212335729143      # one-sided 5%, 80% power

SPY_B = "daily-history-SPY"
IWM_B = "daily-history-IWM"
GSPC_B = "daily-history--GSPC"
DTB3_B = "fred-DTB3"
VIX_B = "cboe-VIX-history"
FJA_B = "fja-sp500-components"
SPELLS_B = "fja-sp500-ticker-spells"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
SEC_TICK_B = "sec-company-tickers"
CIK_LOOKUP_B = "sec-cik-lookup"
FACTS_PREFIX = "sec-companyfacts-"
SUBS_PREFIX = "sec-submissions-"
DH_PREFIX = "daily-history-"
DE_PREFIX = "daily-events-"

BASE_START = "1990-01-01"
ID_DV_WIN = 60                 # identity check: trailing median dollar volume window (sessions)
ID_DV_RATIO = 1.0 / 40.0       # ... below this fraction of the day's member median = another company's series
SPELL_TOL = 31                 # days between a spell's leave and a Wikipedia removal record

# T-691
T691_FIRST, T691_LAST = "2010-01", "2026-09"
T691_SPLIT = "2018-01"
T691_POST = "2019-01"
T691_COST = 10e-4
T691_COST_STRESS = 20e-4
T691_BORROW = 0.005
T691_NW_LAG = 6
T691_BLOCK = 12
T691_MIN_N = 180
T691_MAX_AGE = SX.SHARES_MAX_AGE          # 456 days: about 15 months
T691_SKIP = 3
T691_COVER = 0.80
T691_TRIALS = 4
TO_MIN, TO_MAX = 0.002, 20.0             # plausible monthly share turnover band (unit-error filter)
CLASS_RATIO = SX.CLASS_PRICE_RATIO

# T-698
T698_START, T698_END = "2005-01-01", "2026-09-30"
T698_SPLIT = "2016-01-01"
T698_AVWIN = 60
T698_DVWIN = 60
T698_VOLWIN = 20
T698_MIN_NAMES = 30
T698_NW_LAG = 5
T698_T = 2.8
T698_MIN_N = 4000

# T-692
T692_START, T692_END = "2008-01-01", "2026-09-30"
T692_SPLIT = "2017-01-01"
T692_VWIN = 49
T692_SWIN = 52
T692_HOLD = 20
T692_BWIN, T692_BMIN = 252, 200
T692_COST = 10e-4
T692_BAR = 50e-4
T692_P = 0.01
T692_T = 2.0
T692_NW_LAG = 20
T692_N_SHIFT = 2000
T692_TRIALS = 37                       # T-419's 36 cells plus this one
T692_MIN_N = 800

# T-693 / T-694
T693_FIRST_MONTH = "1997-01"
T693_FIRST_TARGET, T693_LAST_TARGET = "2005-01", "2026-09"
T693_SPLIT = "2016-01"
T693_MIN_DAYS = 15
T693_MIN_PRICE = 5.0
T693_MIN_TRAIN = 36
T693_CW_LAG = 12
T693_COST = 5e-4
T693_MEAN_BLOCK = 6.0
T693_NBOOT = 5000
T693_MIN_N = 240
T693_EXTERNAL = {"T-421": 0.3728135932033983}
T694_HIST = 60
T694_H = 12
T694_FIRST_ORIGIN, T694_LAST_ORIGIN = "2004-12", "2025-09"
T694_MIN_TRAIN = 36
T694_CW_LAG = 12
T694_COST = 5e-4
T694_MIN_N = 200
T694_EXTERNAL = {"T-398": 0.824, "T-449": 0.125, "T-458": 0.481}
T694_SEC_FROM = "2010-01"


# ================================================================================================= utilities ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, list(names))


def _prefix_missing(archive, prefixes: Sequence[str]):
    """Inconclusive when no bundle of a required family is archived (probes ``entries``)."""
    miss = [p + "*" for p in prefixes if not SX._entry_names(archive, p)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived (rule 9)")
    return None


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f} bp"


def _mi(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def madd(m: str, k: int) -> str:
    return _ms(_mi(m) + k)


def mrange(a: str, b: str) -> list:
    return [_ms(i) for i in range(_mi(a), _mi(b) + 1)]


def month_last_sessions(days: Sequence[str]) -> dict:
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    return last


def month_first_sessions(days: Sequence[str]) -> dict:
    first = {}
    for i, d in enumerate(days):
        first.setdefault(d[:7], i)
    return first


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


def _ffill(X: np.ndarray) -> np.ndarray:
    return SX._ffill(X)


def roll_sum(X: np.ndarray, w: int, incl: bool) -> np.ndarray:
    """Rolling column sums over rows i-w..i-1 (``incl`` False) or i-w+1..i (True); NaN where the window starts before
    row 0. NaN entries must be zeroed by the caller (count them with a mask)."""
    X = np.asarray(X, float)
    D = X.shape[0]
    c = np.concatenate([np.zeros((1,) + X.shape[1:]), np.cumsum(X, axis=0)], axis=0)
    out = np.full(X.shape, np.nan)
    if incl:
        if D >= w:
            out[w - 1:] = c[w:] - c[:D - w + 1]
    elif D > w:
        out[w:] = c[w:D] - c[:D - w]
    return out


def roll_median(X: np.ndarray, w: int, chunk: int = 400) -> np.ndarray:
    """Median over rows i-w+1..i of each column, NaN unless all w values are finite (chunked to bound memory)."""
    X = np.asarray(X, float)
    D, N = X.shape
    out = np.full((D, N), np.nan)
    if D < w:
        return out
    for a in range(w - 1, D, chunk):
        b = min(D, a + chunk)
        W = np.lib.stride_tricks.sliding_window_view(X[a - w + 1:b], w, axis=0)   # (b-a, N, w)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.median(W, axis=2)
        out[a:b] = m
    return out


# ================================================================================ point-in-time stock base ==

def _spells(archive) -> dict:
    """{Yahoo-spelled ticker: [(join, leave or None, spell)]} from fja-sp500-ticker-spells."""
    joins, leaves = defaultdict(dict), defaultdict(dict)
    for r in SX._rows(archive, SPELLS_B):
        v = r.get("value") or {}
        t = v.get("ticker")
        if not t:
            continue
        y = SX.ysym(t)
        k = int(v.get("spell") or 1)
        if r.get("kind") == "sp500-join":
            joins[y][k] = str(v.get("date") or "")[:10]
        elif r.get("kind") == "sp500-leave":
            leaves[y][k] = str(v.get("date") or "")[:10]
            if v.get("start_date"):
                joins[y].setdefault(k, str(v["start_date"])[:10])
    out = {}
    for y in set(joins) | set(leaves):
        ks = sorted(set(joins[y]) | set(leaves[y]))
        out[y] = [(joins[y].get(k, ""), leaves[y].get(k), k) for k in ks]
    return out


def _days_apart(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def identity_mask(C, V, member) -> np.ndarray:
    """Member-days whose trailing ID_DV_WIN-session median dollar volume (close x volume, sessions i-59..i) is below
    ID_DV_RATIO of that day's median over members: another company's series under a reused ticker. Uses no data after
    day i."""
    with np.errstate(invalid="ignore"):
        dv = np.where(np.isfinite(V) & np.isfinite(C), C * V, np.nan)
    dvm = roll_median(dv, ID_DV_WIN)
    del dv
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cs = np.nanmedian(np.where(member & np.isfinite(dvm), dvm, np.nan), axis=1)
    with np.errstate(invalid="ignore"):
        return member & np.isfinite(dvm) & (dvm < cs[:, None] * ID_DV_RATIO)


def vbase(archive) -> dict:
    """The shared point-in-time S&P 500 stock panel: sessions (^GSPC bars from 1990 to SPY's last bar), membership with
    T-473's reused-ticker filters and the per-spell name check, CIKs, the archived share classes of each CIK, and
    session x symbol open / close / adjclose / volume matrices from the shared daily panel. Cached per archive."""
    def load():
        from mandel.experiments import panel_cache as PCM
        P = PCM.daily_panel(archive)
        pdays = P.days.astype(str)
        pcol = {str(s): j for j, s in enumerate(P.symbols.tolist())}
        g = P.close[:, pcol["-GSPC"]]
        spy = P.close[:, pcol["SPY"]]
        last_spy = int(np.flatnonzero(np.isfinite(spy))[-1])
        rows = np.flatnonzero(np.isfinite(g) & (pdays >= BASE_START) & (np.arange(len(pdays)) <= last_spy))
        days = [str(d) for d in pdays[rows]]
        sets, n_wiki = SX._member_sets(archive)
        sdates = [d for d, _ in sets]
        tick = set()
        for _, s in sets:
            tick |= set(s)
        wiki = {}
        if B7C._has(archive, SX.WIKI_B):
            for r in SX._rows(archive, SX.WIKI_B):
                v = r.get("value") or {}
                if v.get("symbol"):
                    wiki[SX.ysym(v["symbol"])] = v
        removals = defaultdict(list)
        if B7C._has(archive, SX.WIKI_CH_B):
            for r in SX._rows(archive, SX.WIKI_CH_B):
                v = r.get("value") or {}
                if v.get("removed_ticker") and v.get("removed_security") and v.get("effective_date"):
                    removals[SX.ysym(v["removed_ticker"])].append((str(v["effective_date"])[:10], v["removed_security"]))
        spells = _spells(archive)
        sec_t = SX._sec_tickers(archive) if B7C._has(archive, SEC_TICK_B) else {}
        info = {"tickers": len(tick), "no_series": [], "not_equity": [], "bad_spells": [], "no_cik": [],
                "wiki_changes_after_fja": n_wiki, "not_in_spells": []}
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
            cik = sec_t[y][0] if y in sec_t else None
            if cik is None and y in wiki:
                try:
                    cik = int(wiki[y].get("cik"))
                except (TypeError, ValueError):
                    cik = None
            cand.append((t, y, j, meta, cik))
        comp = SX._company_rows(archive, {c for *_, c in cand if c is not None}) if cand else {}
        keep, bad = [], {}
        for t, y, j, meta, cik in cand:
            names = [meta.get("longName") or ""]
            if y in sec_t:
                v = comp.get(sec_t[y][0]) or {}
                names += [sec_t[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
            sp = spells.get(y, [])
            if not sp:
                info["not_in_spells"].append(y)
            bad_sp = []
            for join, leave, k in sp:
                if leave is None:
                    continue                                    # an open spell: a current member
                recs = [nm for d, nm in removals.get(y, []) if _days_apart(d, leave) <= SPELL_TOL]
                if recs and all(SX.names_ok(nm, names) is False for nm in recs):
                    bad_sp.append((join, leave))
            if bad_sp:
                info["bad_spells"].append((y, bad_sp))
                bad[y] = bad_sp
            keep.append((t, y, j, cik))
        syms = [y for _, y, _, _ in keep]
        cols = np.array([j for _, _, j, _ in keep], int)
        ciks = [c for *_, c in keep]
        for y, c in zip(syms, ciks):
            if c is None:
                info["no_cik"].append(y)
        # archived EQUITY share classes of each kept CIK (T-393's listed classes, on the archived series)
        by_cik_t = defaultdict(list)
        for tk, (c, _nm) in sec_t.items():
            by_cik_t[c].append(tk)
        classes, extra = {}, {}
        for c in {c for c in ciks if c is not None}:
            cl = []
            for tk in sorted(by_cik_t.get(c, [])):
                jj = pcol.get(SX._safe(tk))
                if jj is None or (SX._meta(archive, SX.dh(tk)) or {}).get("instrumentType") != "EQUITY":
                    continue
                cl.append(tk)
                if tk not in syms and tk not in extra:
                    extra[tk] = np.ascontiguousarray(P.close[rows, jj])
            if len(cl) > 1:
                classes[c] = cl
        D, N = len(days), len(syms)
        mats = {f: np.ascontiguousarray(getattr(P, f)[np.ix_(rows, cols)]) for f in ("open", "close", "adjclose", "volume")}
        col = {y: k for k, y in enumerate(syms)}
        mem_idx = [bisect.bisect_right(sdates, d) - 1 for d in days]
        member = np.zeros((D, N), bool)
        n_members = np.zeros(D, int)
        cache = {}
        for i, k in enumerate(mem_idx):
            if k < 0:
                continue
            if k not in cache:
                cache[k] = [col[SX.ysym(t)] for t in sets[k][1] if SX.ysym(t) in col]
            member[i, cache[k]] = True
            n_members[i] = len(sets[k][1])
        dar = np.array(days)
        n_bad_days = 0
        for y, sps in bad.items():
            for join, leave in sps:
                m = (dar >= join) & (dar < leave)
                n_bad_days += int((member[m, col[y]]).sum())
                member[m, col[y]] = False
        info["bad_spell_member_days"] = n_bad_days
        # identity check by size: a member-day whose trailing 60-session median dollar volume is below 1/40 of that
        # day's median over priced members is another company's series under a reused ticker (FCN = FTI Consulting for
        # First Chicago NBD, CCU, BBT, SNT, WEN before 2008, CNC, AIT, ...); such member-days are unpriced
        tiny = identity_mask(mats["close"], mats["volume"], member)
        info["size_identity_member_days"] = int(tiny.sum())
        info["size_identity_symbols"] = sorted({syms[j] for j in np.flatnonzero(tiny.any(axis=0))})
        member &= ~tiny
        del tiny
        info["kept"] = N
        in_spells = np.array([y in spells for y in syms], bool)
        mkt = {m: {f: np.ascontiguousarray(getattr(P, f)[rows, pcol[m]]) for f in ("open", "close", "adjclose", "volume")}
               for m in ("SPY", "IWM", "-GSPC") if m in pcol}
        del P
        PCM._MEMO.clear()
        gc.collect()
        return {"days": days, "syms": syms, "ciks": ciks, "classes": classes, "class_close": extra, "member": member,
                "n_members": n_members, "in_spells": in_spells, "info": info, "mkt": mkt, **mats}
    return CAL._cached(archive, ("b13va_base",), load)


def stock_splits(archive, sym: str) -> list:
    """[(ex_date, ratio)] from a symbol's daily-events bundle, parsed as ``batch6c_stockxs._stock`` does."""
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


def all_splits(archive, syms: Sequence[str]) -> dict:
    return CAL._cached(archive, ("b13va_splits", tuple(syms)), lambda: {y: stock_splits(archive, y) for y in syms})


def split_factor_matrix(days: Sequence[str], syms: Sequence[str], splits: dict) -> np.ndarray:
    """F[i, j] = product of symbol j's split ratios with an ex-date after day i (raw price = split-adjusted x F)."""
    D = len(days)
    F = np.ones((D, len(syms)))
    for j, y in enumerate(syms):
        for ex, ratio in splits.get(y, ()):
            k = bisect.bisect_left(days, ex)               # days strictly before the ex-date carry the ratio
            F[:k, j] *= ratio
    return F


def share_series_by_cik(archive, ciks: set) -> dict:
    """{cik: ``batch6c_stockxs.shares_series``} from the companyfacts buckets holding the wanted CIKs (share tags only; a
    fact counts from its available_at)."""
    def load():
        names = set(SX._entry_names(archive, FACTS_PREFIX))
        facts = defaultdict(list)
        for b in sorted({SX.sec_bucket(c) for c in ciks}):
            n = FACTS_PREFIX + b
            if n not in names:
                continue
            for r in SX._stream(archive, n):
                if r.get("kind") != "fact":
                    continue
                v = r.get("value") or {}
                if (v.get("taxonomy"), v.get("tag")) not in SX.SHARE_TAGS:
                    continue
                try:
                    c = int(v.get("cik"))
                    if c not in ciks:
                        continue
                    val = float(v.get("val"))
                    av = SX._ts(r["available_at"])
                except (TypeError, ValueError, KeyError):
                    continue
                facts[c].append((v.get("taxonomy"), v.get("tag"), v.get("unit"), v.get("start"), v.get("end"), val,
                                 v.get("accn"), v.get("form") or "", av))
        return {c: SX.shares_series(f) for c, f in facts.items()}
    return CAL._cached(archive, ("b13va_shares", frozenset(ciks)), load)


def shares_known(series: Sequence[tuple], ts: float, day: str, max_age: int = T691_MAX_AGE) -> Optional[tuple]:
    """(shares, as-of date) of the latest accession available at ``ts`` when its cover date is at most ``max_age`` days
    before ``day``; None otherwise."""
    k = bisect.bisect_right([s[0] for s in series], ts) - 1
    if k < 0:
        return None
    _, end, sh = series[k]
    if (date.fromisoformat(day) - date.fromisoformat(end)).days <= max_age:
        return sh, end
    return None


def factor_holds(archive, days: Sequence[str], spans: Sequence[tuple]) -> tuple:
    """(F (M, 6) FF5 + UMD compounded over each hold (entry, exit], mask of holds fully covered by the factor files)."""
    cols = SX.FF5_COLS
    f5 = {c: CAL._series(archive, FF5_B, c) for c in cols}
    um = CAL._series(archive, MOM_B, "Mom")
    end = min(max(f5[cols[0]]), max(um)) if f5[cols[0]] and um else ""
    F = np.full((len(spans), 6), np.nan)
    ok = np.zeros(len(spans), bool)
    for k, (e, x) in enumerate(spans):
        ds = days[e + 1:x + 1]
        if not ds or ds[-1] > end:
            continue
        try:
            vals = [[f5[c][d] / 100.0 for c in cols] + [um[d] / 100.0] for d in ds]
        except KeyError:
            continue
        F[k] = np.prod(1.0 + np.array(vals), axis=0) - 1.0
        ok[k] = True
    return F, ok, end


# ====================================================================================================== T-691 ==

def form_month(A, C, V, member_row, e0: int, f: int, adj) -> dict:
    """One formation at session ``f`` from the previous formation base ``e0``: total return A[f] / A[e0] - 1, turnover =
    volume summed over sessions e0+1..f / adjusted shares, cap = close[f] x adjusted shares. Eligible: member at f, bars
    at e0 and f, finite volume on every formation session, positive turnover and cap. Uses no data after session f."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r = A[f] / A[e0] - 1.0
        vol = V[e0 + 1:f + 1]
        to = vol.sum(axis=0) / adj
        cap = C[f] * adj
    ok = (member_row & np.isfinite(r) & np.isfinite(vol).all(axis=0) & np.isfinite(to) & (to > 0) & np.isfinite(cap)
          & (cap > 0))
    return {"r": np.where(ok, r, np.nan), "to": np.where(ok, to, np.nan), "cap": np.where(ok, cap, np.nan), "el": ok}


def legs_2x2(r, to, el, kind: str) -> tuple:
    """(long mask, short mask) of one month's independent median sorts. 'stmom': high-turnover winners / high-turnover
    losers; 'strev': losers / winners (all turnover); 'mom': winners / losers on the 12-1 return. Ties at a median join
    neither side."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mr = np.nanmedian(np.where(el, r, np.nan))
        mt = np.nanmedian(np.where(el, to, np.nan))
    win, los = el & (r > mr), el & (r < mr)
    if kind == "stmom":
        hi = el & (to > mt)
        return win & hi, los & hi
    if kind == "strev":
        return los, win
    return win, los


def vw_weights(mask, cap) -> np.ndarray:
    c = np.where(mask, cap, 0.0)
    s = c.sum()
    return c / s if s > 0 else np.zeros_like(c)


def book(WL, WS, HR, elig, days_held, cost: float, borrow: float) -> dict:
    """Monthly long-short book over rows (M, N): gross, cost (``cost`` x sum |w_new - drifted w_old| over both legs) and
    borrow (``borrow`` per year on the short leg, pro rata the hold's calendar days); the first entry and every exit
    are charged (a book closed because the next month is ineligible pays its exit in the last eligible month)."""
    M = WL.shape[0]
    H = np.nan_to_num(HR, nan=0.0)
    gl = (WL * H).sum(axis=1)
    gs = (WS * H).sum(axis=1)

    def turnover(W, g):
        T = np.zeros(M)
        prev = np.zeros(W.shape[1])
        last_el = None
        for t in range(M):
            if not elig[t]:
                if last_el is not None:
                    T[last_el] += np.abs(prev).sum()
                prev = np.zeros(W.shape[1])
                last_el = None
                continue
            T[t] = np.abs(W[t] - prev).sum()
            prev = W[t] * (1.0 + H[t]) / (1.0 + g[t]) if (1.0 + g[t]) != 0 else W[t]
            last_el = t
        if last_el is not None:
            T[last_el] += np.abs(prev).sum()
        return T
    tl, ts = turnover(WL, gl), turnover(WS, gs)
    gross = np.where(elig, gl - gs, 0.0)
    c = cost * (tl + ts)
    bw = np.where(elig & (WS.sum(axis=1) > 0), borrow * np.asarray(days_held, float) / 365.0, 0.0)
    return {"gross": gross, "net": gross - c - bw, "cost": c, "borrow": bw, "turnover": tl + ts,
            "n_long": (WL > 0).sum(axis=1), "n_short": (WS > 0).sum(axis=1)}


def _cik_shares(archive, B) -> tuple:
    """Per-CIK share series and their availability arrays (for fast point-in-time lookups)."""
    ciks = {c for c in B["ciks"] if c is not None}
    sh = share_series_by_cik(archive, ciks)
    av = {c: np.array([s[0] for s in ser], float) for c, ser in sh.items()}
    return sh, av


def adjusted_shares(B, sh, av, splits, f: int, cols=None) -> np.ndarray:
    """Shares on Yahoo's fetch-date split basis known at the close of session ``f`` (NaN when none is fresh, or when the
    issuer's archived classes trade more than 2x apart); an issuer's cover count is split equally across its archived
    classes (T-393's rule)."""
    days = B["days"]
    N = len(B["syms"])
    ts = SX._et_ts(days[f], 16, 0)
    out = np.full(N, np.nan)
    idx = range(N) if cols is None else cols
    for j in idx:
        c = B["ciks"][j]
        if c is None or c not in sh:
            continue
        k = int(np.searchsorted(av[c], ts, side="right")) - 1
        if k < 0:
            continue
        _, end, s = sh[c][k]
        if (date.fromisoformat(days[f]) - date.fromisoformat(end)).days > T691_MAX_AGE:
            continue
        adj = s * SX.split_factor(splits.get(B["syms"][j], ()), end)
        cl = B["classes"].get(c)
        if cl:
            px = []
            for tk in cl:
                cc = B["close"][f, B["syms"].index(tk)] if tk in B["syms"] else B["class_close"][tk][f]
                if np.isfinite(cc) and cc > 0:
                    px.append(cc * SX.split_factor(splits.get(tk, ()), days[f]))
            if len(px) < len(cl) or max(px) > CLASS_RATIO * min(px):
                continue
            adj /= len(cl)
        out[j] = adj
    return out


def unit_filter(adj, V, e0: int, f: int) -> tuple:
    """SEC XBRL unit errors (cover counts filed x1,000 or x1,000,000 too large or small: EXC 2010-03, PKG 2024-05,
    FOXA's single '1.0' fact): a share count is unusable when the turnover it implies over the formation sessions
    e0+1..f (volume / shares) lies outside [TO_MIN, TO_MAX], orders of magnitude beyond any S&P 500 member's month.
    Point in time (the formation's own volume and shares). Returns (filtered shares, number rejected)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        to = np.nansum(V[e0 + 1:f + 1], axis=0) / adj
    bad = np.isfinite(adj) & ~((to >= TO_MIN) & (to <= TO_MAX))
    return np.where(bad, np.nan, adj), int(bad.sum())


def t691_inputs(archive) -> dict:
    """Formation rows for every holding month and trial: 'a' (full month, fill at the first close of the next month,
    held to the next fill) and 'b' (sessions 1..d-3, filled at the month-end close, held to the next month-end); the
    12-1 return on trial a's timing; coverage (members with a price and shares / every fja member) per formation."""
    def load():
        B = vbase(archive)
        days = B["days"]
        A, C, V = B["adjclose"], B["close"], B["volume"]
        N = len(B["syms"])
        last = month_last_sessions(days)
        sh, av = _cik_shares(archive, B)
        splits = all_splits(archive, list(B["syms"]) + sorted(B["class_close"]))
        real = np.isfinite(A)
        Aff = _ffill(A)
        lastbar = np.where(real.any(axis=0), len(days) - 1 - real[::-1].argmax(axis=0), -1)
        out = {"a": [], "b": []}
        for H in mrange(T691_FIRST, T691_LAST):
            t, tp = madd(H, -1), madd(H, -2)
            if t not in last or tp not in last or H not in last:
                continue
            e_t, e_prev, e_h = last[t], last[tp], last[H]
            for trial in ("a", "b"):
                if trial == "a":
                    f, entry, exit_ = e_t, e_t + 1, e_h + 1
                else:
                    f, entry, exit_ = e_t - T691_SKIP, e_t, e_h
                if exit_ >= len(days) or f <= e_prev:
                    continue
                mem = B["member"][f]
                adj = adjusted_shares(B, sh, av, splits, f, np.flatnonzero(mem & real[f]))
                adj, n_unit = unit_filter(adj, V, e_prev, f)
                fm = form_month(A, C, V, mem, e_prev, f, adj)
                n_mem = int(B["n_members"][f])
                n_ps = int((mem & real[f] & np.isfinite(adj)).sum())
                with np.errstate(invalid="ignore", divide="ignore"):
                    xe = np.minimum(exit_, lastbar)
                    hr = np.where(real[entry] & (lastbar >= entry), Aff[np.maximum(xe, 0), np.arange(N)] / A[entry] - 1.0, 0.0)
                row = {"H": H, "f": f, "entry": entry, "exit": exit_, **fm, "hr": hr, "n_members": n_mem, "n_unit": n_unit,
                       "n_priced": int((mem & real[f]).sum()), "n_price_shares": n_ps,
                       "cover": n_ps / n_mem if n_mem else 0.0,
                       "days_held": (date.fromisoformat(days[exit_]) - date.fromisoformat(days[entry])).days}
                if trial == "a":
                    m1, m12 = madd(t, -1), madd(t, -12)
                    if m1 in last and m12 in last:
                        i1, i12 = last[m1], last[m12]
                        with np.errstate(invalid="ignore", divide="ignore"):
                            r12 = A[i1] / A[i12] - 1.0
                        ok12 = fm["el"] & real[i1] & real[i12] & np.isfinite(r12)
                    else:
                        r12, ok12 = np.full(N, np.nan), np.zeros(N, bool)
                    row["r12"] = np.where(ok12, r12, np.nan)
                    row["el12"] = ok12
                out[trial].append(row)
        return {"rows": out, "days": days, "info": B["info"]}
    return CAL._cached(archive, ("b13va_t691",), load)


def t691_book(rows: list, kind: str, cost: float = T691_COST) -> dict:
    """The monthly book of one trial over its formation rows."""
    M = len(rows)
    if not M:
        return {"net": np.zeros(0), "elig": np.zeros(0, bool), "months": []}
    N = rows[0]["r"].size
    WL, WS = np.zeros((M, N)), np.zeros((M, N))
    elig = np.array([r["cover"] >= T691_COVER for r in rows], bool)
    for k, r in enumerate(rows):
        if not elig[k]:
            continue
        if kind == "mom":
            lm, sm = legs_2x2(r["r12"], r["to"], r["el12"], "mom")
        else:
            lm, sm = legs_2x2(r["r"], r["to"], r["el"], kind)
        WL[k], WS[k] = vw_weights(lm, r["cap"]), vw_weights(sm, r["cap"])
        if WL[k].sum() == 0 or WS[k].sum() == 0:
            elig[k] = False
            WL[k] = WS[k] = 0.0
    HR = np.vstack([np.where(r["el"], np.nan_to_num(r["hr"], nan=0.0), 0.0) for r in rows])
    bk = book(WL, WS, HR, elig, [r["days_held"] for r in rows], cost, T691_BORROW)
    bk["elig"] = elig
    bk["months"] = [r["H"] for r in rows]
    return bk


def _ci_lower_row(t: dict, label: str) -> tuple:
    return BW._ci_crit(t, "gt", 0.0, label, fmt=lambda v: _pc(v, 3))


def b13_volume_a_stmom(archive):
    """T-691."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B, FF5_B, MOM_B, SEC_TICK_B]) or \
        _prefix_missing(archive, [DH_PREFIX, DE_PREFIX, FACTS_PREFIX, SUBS_PREFIX])
    if miss:
        return miss
    I = t691_inputs(archive)
    rows_a, rows_b = I["rows"]["a"], I["rows"]["b"]
    days = I["days"]
    bk = {"primary": t691_book(rows_a, "stmom"), "lag": t691_book(rows_b, "stmom"),
          "strev": t691_book(rows_a, "strev"), "mom12_1": t691_book(rows_a, "mom")}
    P = bk["primary"]
    el = P["elig"]
    months = [m for m, e in zip(P["months"], el) if e]
    net = P["net"][el]
    n = int(net.size)
    n_formed = len(rows_a)
    if n < 8:
        cov = [r["cover"] for r in rows_a]
        return _out({"n": n, "n_formed": n_formed, "cover": [min(cov), max(cov)] if cov else None}, n, "inconclusive",
                    f"only {n} of {n_formed} holding months have >= 80% of members with a price and shares (the claim's "
                    f"eligibility rule; coverage {_f(min(cov) * 100 if cov else None, 1)}-{_f(max(cov) * 100 if cov else None, 1)}%): "
                    f"too few to test")
    mean = float(net.mean())
    nw = hac_mean(net, T691_NW_LAG)
    ci = SX.mean_ci(net, T691_BLOCK)
    mo = np.array(months)
    post = net[mo >= T691_POST]
    h1, h2 = net[mo < T691_SPLIT], net[mo >= T691_SPLIT]
    halves = [float(h1.mean()) if h1.size else None, float(h2.mean()) if h2.size else None]
    rows_el = [r for r, e in zip(rows_a, el) if e]
    F, fok, fend = factor_holds(archive, days, [(r["entry"], r["exit"]) for r in rows_el])
    reg = ols_nw_all(net[fok], F[fok], T691_NW_LAG) if fok.sum() > 12 else {"coef": None, "t": None}
    alpha = reg["coef"][0] if reg.get("coef") else None
    alpha_t = reg["t"][0] if reg.get("t") else None
    srs = {k: float(sharpe_ratio(b["net"][b["elig"]])) if b["elig"].sum() > 2 else None for k, b in bk.items()}
    d = MOM.family_dsr(net, [s for s in srs.values() if s is not None], T691_TRIALS)
    mde = Z_MDE * nw["se"] if nw.get("se") else None
    nw_ok = bool(mean > 0 and nw["p"] < ALPHA) if nw.get("p") is not None else None
    crit = [(f"primary net mean {_pc(mean, 3)}/month > 0 with one-sided Newey-West ({T691_NW_LAG}) p < 0.05 (t "
             f"{_s(nw.get('t'), 2)}, p {_f(nw.get('p'), 4)})", nw_ok, nw.get("t") is not None and nw["t"] < -1.645),
            _ci_lower_row(ci, f"studentized CBB ({T691_BLOCK}-month blocks) 95% lower bound of the net mean > 0"),
            (f"mean > 0 over {T691_POST}..{T691_LAST} ({_pc(post.mean() if post.size else None, 3)}, {post.size} months)",
             None if not post.size else bool(post.mean() > 0), False),
            (f"both halves positive ({T691_FIRST}..2017-12 {_pc(halves[0], 3)} over {h1.size}; 2018-01..{T691_LAST} "
             f"{_pc(halves[1], 3)} over {h2.size})", None if None in halves else all(h > 0 for h in halves), False),
            (f"FF5+UMD alpha {_pc(alpha, 3) if alpha is not None else 'n/a'}/month > 0 (NW t {_s(alpha_t, 2)}, "
             f"{int(fok.sum())} holds ending by {fend})", None if alpha is None else bool(alpha > 0),
             alpha_t is not None and alpha_t < -1.645),
            MOM.dsr_row(d, f"DSR >= {DSR_PASS} over the {T691_TRIALS} declared trials")]
    v, why, crit_j = CAL._judge(crit, n, T691_MIN_N, "eligible months")
    # ---- reported
    stress = t691_book(rows_a, "stmom", T691_COST_STRESS)
    net20 = stress["net"][stress["elig"]]
    cov = np.array([r["cover"] for r in rows_a])
    absent = float(1.0 - cov[el].mean())
    flip = -mean * (1.0 - absent) / absent if absent > 0 else None
    reg_y = {y: (float(net[np.array([m.startswith(y) for m in months])].mean())
                 if any(m.startswith(y) for m in months) else None) for y in ("2020", "2022")}
    ex = {k: {"net_mean": float(b["net"][b["elig"]].mean()) if b["elig"].any() else None, "n": int(b["elig"].sum()),
              "nw_t": hac_mean(b["net"][b["elig"]], T691_NW_LAG)["t"] if b["elig"].sum() > 3 else None,
              "sharpe_pp": srs[k]} for k, b in bk.items()}
    elig_names = np.array([int(r["el"].sum()) for r in rows_el])
    first_el = months[0]
    stat = {"n": n, "n_formed": n_formed, "first": first_el, "last": months[-1], "net_mean": mean,
            "gross_mean": float(P["gross"][el].mean()), "cost_mean": float(P["cost"][el].mean()),
            "borrow_mean": float(P["borrow"][el].mean()), "turnover_mean": float(P["turnover"][el].mean()),
            "nw6": nw, "cbb_ci": ci.get("ci"), "cbb_ci_mc_se": ci.get("ci_mc_se"), "post_2019": float(post.mean()) if post.size else None,
            "n_post": int(post.size), "halves": halves, "alpha": alpha, "alpha_t": alpha_t, "alpha_betas": reg.get("coef"),
            "alpha_n": int(fok.sum()), "dsr": d, "mde_month": mde, "trials": ex, "net_mean_20bp": float(net20.mean()) if net20.size else None,
            "cover_all": [float(cov.min()), float(np.median(cov)), float(cov.max())], "cover_months_ge_80": int((cov >= T691_COVER).sum()),
            "absent_share_eligible": absent, "flip_bound": flip, "regimes": reg_y,
            "eligible_names": [int(elig_names.min()), int(np.median(elig_names)), int(elig_names.max())],
            "legs_median": [int(np.median(P["n_long"][el])), int(np.median(P["n_short"][el]))],
            "monthly_absent_share": {r["H"]: round(1.0 - r["cover"], 4) for r in rows_a},
            "base": {k: (len(v) if isinstance(v, list) else v) for k, v in I["info"].items()}, "criteria": crit_j, "verdict": v}
    reason = (f"STMOM 2x2 (independent median splits on r(m) and turnover; VW long high-turnover winners, short "
              f"high-turnover losers; next-close fills) on point-in-time S&P 500 members with Yahoo prices and SEC shares: "
              f"{n} of {n_formed} holding months {T691_FIRST}..{T691_LAST} eligible (>= 80% of members with a price and "
              f"shares; coverage {cov.min() * 100:.1f}-{cov.max() * 100:.1f}%, median {np.median(cov) * 100:.1f}%; first "
              f"eligible {first_el}); {elig_names.min()}-{elig_names.max()} names a month, median legs "
              f"{stat['legs_median'][0]} / {stat['legs_median'][1]}: net mean {_pc(mean, 3)}/month (gross "
              f"{_pc(stat['gross_mean'], 3)}, cost {_pc(stat['cost_mean'], 3)} at 10 bp/side, borrow "
              f"{_pc(stat['borrow_mean'], 3)}), NW(6) t {_s(nw.get('t'), 2)}, CBB 95% CI "
              f"{_pc((ci.get('ci') or [None])[0], 3)}..{_pc((ci.get('ci') or [None, None])[1], 3)}; {T691_POST}+ "
              f"{_pc(stat['post_2019'], 3)}; halves {_pc(halves[0], 3)} / {_pc(halves[1], 3)}; FF5+UMD alpha "
              f"{_pc(alpha, 3) if alpha is not None else 'n/a'} (t {_s(alpha_t, 2)}); DSR {_f(d.get('dsr'))} over 4 trials; "
              f"MDE (80% power) {_pc(mde, 3)}/month. Reported: lag variant {_pc(ex['lag']['net_mean'], 3)} ({ex['lag']['n']} "
              f"months), STREV {_pc(ex['strev']['net_mean'], 3)}, 12-1 momentum {_pc(ex['mom12_1']['net_mean'], 3)}; at 20 "
              f"bp/side {_pc(stat['net_mean_20bp'], 3)}; 2020 {_pc(reg_y['2020'], 3)}, 2022 {_pc(reg_y['2022'], 3)}; absent "
              f"members (no price or no shares) {absent * 100:.1f}% of member-months in eligible months: they would need a "
              f"long-short return of {_pc(flip, 3) if flip is not None else 'n/a'}/month on that share to bring the mean to "
              f"zero. Survivorship: prices come from today's 901-symbol set (removed members under-represented, the claim's "
              f"own 'priced members' universe); CIKs from the current SEC map; {len(I['info']['bad_spells'])} tickers had a "
              f"spell refused by the name check")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-698 ==

def t698_features(A, C, O, V, member, i0: int) -> dict:
    """Day x name features known at the close of each day t (rows from ``i0``): r(t) close-to-close (adjclose), AV(t)
    = log V(t) minus the mean of log V over t-60..t-1 (all 60 positive), demeaned across the day's members with an AV;
    size = median dollar volume (close x volume) over t-59..t (all 60 finite); vol20 = sd of the 20 returns ending at
    t; and the dependent y(t) = AO(t+2) / AO(t+1) - 1 with AO = open x adjclose / close (dividend-adjusted opens)."""
    D, N = A.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.full((D, N), np.nan)
        r[1:] = A[1:] / A[:-1] - 1.0
        lv = np.where(np.isfinite(V) & (V > 0), np.log(np.where(V > 0, V, 1.0)), np.nan)
        okv = np.isfinite(lv)
        s = roll_sum(np.where(okv, lv, 0.0), T698_AVWIN, incl=False)
        c = roll_sum(okv.astype(float), T698_AVWIN, incl=False)
        av = np.where(c >= T698_AVWIN, lv - s / T698_AVWIN, np.nan)
        dv = np.where(np.isfinite(V) & np.isfinite(C), C * V, np.nan)
        size = roll_median(dv, T698_DVWIN)
        okr = np.isfinite(r)
        sr = roll_sum(np.where(okr, r, 0.0), T698_VOLWIN, incl=True)
        sr2 = roll_sum(np.where(okr, r * r, 0.0), T698_VOLWIN, incl=True)
        cr = roll_sum(okr.astype(float), T698_VOLWIN, incl=True)
        var = (sr2 - sr * sr / T698_VOLWIN) / (T698_VOLWIN - 1)
        vol = np.where(cr >= T698_VOLWIN, np.sqrt(np.maximum(var, 0.0)), np.nan)
        AO = O * (A / C)
        y = np.full((D, N), np.nan)
        y[:-2] = AO[2:] / AO[1:-1] - 1.0
    sl = slice(i0, D)
    feat = {"r": r[sl], "av": av[sl], "size": size[sl], "vol": vol[sl], "y": y[sl], "member": member[sl]}
    base = feat["member"] & np.isfinite(feat["r"]) & np.isfinite(feat["av"]) & np.isfinite(feat["size"]) & (feat["size"] > 0) \
        & np.isfinite(feat["vol"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mu = np.nanmean(np.where(base, feat["av"], np.nan), axis=1)
    feat["avd"] = feat["av"] - mu[:, None]
    feat["base"] = base
    return feat


def fm_day(r, avd, size, vol, y, base) -> dict:
    """One day's regressions within size terciles of the day's eligible members (terciles by rank of size): y on
    [1, r, r x AV, AV, log size, vol20]; a tercile needs T698_MIN_NAMES names with a finite y. Returns {tercile:
    coefficients (6,) or None} and the counts."""
    idx = np.flatnonzero(base)
    out = {"bottom": None, "middle": None, "top": None, "n": {}}
    if idx.size < 3 * T698_MIN_NAMES:
        return out
    o = idx[np.argsort(size[idx], kind="stable")]
    k = o.size
    parts = {"bottom": o[: k // 3], "middle": o[k // 3: 2 * k // 3], "top": o[2 * k // 3:]}
    for nm, ii in parts.items():
        ii = ii[np.isfinite(y[ii])]
        out["n"][nm] = int(ii.size)
        if ii.size < T698_MIN_NAMES:
            continue
        X = np.column_stack([np.ones(ii.size), r[ii], r[ii] * avd[ii], avd[ii], np.log(size[ii]), vol[ii]])
        b, *_ = np.linalg.lstsq(X, y[ii], rcond=None)
        out[nm] = b
    return out


T698_NAMES = ("const", "r", "r_x_av", "av", "log_dv", "vol20")


def t698_series(archive) -> dict:
    def load():
        B = vbase(archive)
        days = B["days"]
        i0 = bisect.bisect_left(days, "2004-06-01")
        F = t698_features(B["adjclose"], B["close"], B["open"], B["volume"], B["member"], i0)
        dd = days[i0:]
        rows = []
        for k, d in enumerate(dd):
            if not (T698_START <= d <= T698_END) or k + 2 >= len(dd):
                continue
            res = fm_day(F["r"][k], F["avd"][k], F["size"][k], F["vol"][k], F["y"][k], F["base"][k])
            rows.append((d, res, int(F["base"][k].sum()), int(B["n_members"][i0 + k])))
        cover = float(np.mean([b / m for _, _, b, m in rows if m])) if rows else None
        return {"rows": rows, "cover": cover}
    return CAL._cached(archive, ("b13va_t698",), load)


def b13_volume_a_return_volume(archive):
    """T-698."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B]) or _prefix_missing(archive, [DH_PREFIX])
    if miss:
        return miss
    S = t698_series(archive)
    rows = S["rows"]
    keep = [(d, res) for d, res, _, _ in rows if res["top"] is not None and res["bottom"] is not None]
    n = len(keep)
    if n < 10:
        return _out({"n": n}, n, "inconclusive", f"only {n} regression days could be formed")
    dts = np.array([d for d, _ in keep])
    coef = {t: np.vstack([res[t] for _, res in keep]) for t in ("top", "bottom")}
    mid_rows = [(d, res["middle"]) for d, res in keep if res["middle"] is not None]
    coef["middle"] = np.vstack([b for _, b in mid_rows]) if mid_rows else np.zeros((0, 6))
    J = T698_NAMES.index("r_x_av")
    st = {}
    for t in ("top", "middle", "bottom"):
        x = coef[t][:, J] if coef[t].size else np.zeros(0)
        st[t] = {"mean": float(x.mean()) if x.size else None, "nw": hac_mean(x, T698_NW_LAG) if x.size > 3 else {"t": None},
                 "coef_means": {nm: float(coef[t][:, k].mean()) for k, nm in enumerate(T698_NAMES)} if coef[t].size else {},
                 "coef_t": {nm: hac_mean(coef[t][:, k], T698_NW_LAG)["t"] for k, nm in enumerate(T698_NAMES)} if coef[t].size > 3 else {}}
    h1 = dts < T698_SPLIT
    halves = {t: [float(coef[t][h1, J].mean()), float(coef[t][~h1, J].mean())] for t in ("top", "bottom")}
    halves_t = {t: [hac_mean(coef[t][h1, J], T698_NW_LAG)["t"], hac_mean(coef[t][~h1, J], T698_NW_LAG)["t"]] for t in ("top", "bottom")}
    tt, tb = st["top"]["nw"]["t"], st["bottom"]["nw"]["t"]
    crit = [(f"top-tercile mean interaction {_s(st['top']['mean'], 4)} < 0 with NW ({T698_NW_LAG}) t < -{T698_T} (t {_s(tt, 2)})",
             None if tt is None else bool(st["top"]["mean"] < 0 and tt < -T698_T), tt is not None and tt > T698_T),
            (f"bottom-tercile mean interaction {_s(st['bottom']['mean'], 4)} > 0 with NW ({T698_NW_LAG}) t > {T698_T} (t {_s(tb, 2)})",
             None if tb is None else bool(st["bottom"]["mean"] > 0 and tb > T698_T), tb is not None and tb < -T698_T),
            (f"same signs in both halves (2005-2015 / 2016-2026: top {_s(halves['top'][0], 4)} / {_s(halves['top'][1], 4)} "
             f"< 0; bottom {_s(halves['bottom'][0], 4)} / {_s(halves['bottom'][1], 4)} > 0)",
             bool(all(h < 0 for h in halves["top"]) and all(h > 0 for h in halves["bottom"])), False)]
    v, why, crit_j = CAL._judge(crit, n, T698_MIN_N, "regression days")
    nn = {t: int(np.median([res["n"].get(t, 0) for _, res in keep])) for t in ("bottom", "middle", "top")}
    stat = {"n": n, "first": str(dts[0]), "last": str(dts[-1]), "terciles": st, "halves": halves, "halves_t": halves_t,
            "names_per_tercile_median": nn, "member_day_cover": S["cover"], "criteria": crit_j, "verdict": v}
    def tl(t):
        return f"{t} {_s(st[t]['mean'], 4)} (t {_s(st[t]['nw']['t'], 2)})"
    reason = (f"Daily Fama-MacBeth within trailing-60-day-median-dollar-volume terciles of point-in-time S&P 500 members "
              f"with prices, {dts[0]}..{dts[-1]} ({n} days; median names per tercile {nn['bottom']} / {nn['middle']} / "
              f"{nn['top']}): open(t+1)->open(t+2) return on r, r x AV, AV, log dollar volume and 20-day volatility; mean "
              f"interaction coefficient {tl('bottom')}, {tl('middle')}, {tl('top')}; halves top "
              f"{_s(halves['top'][0], 4)} (t {_s(halves_t['top'][0], 2)}) / {_s(halves['top'][1], 4)} (t "
              f"{_s(halves_t['top'][1], 2)}), bottom {_s(halves['bottom'][0], 4)} (t {_s(halves_t['bottom'][0], 2)}) / "
              f"{_s(halves['bottom'][1], 4)} (t {_s(halves_t['bottom'][1], 2)}); r coefficient (reversal) top "
              f"{_s(st['top']['coef_means'].get('r'), 4)} (t {_s(st['top']['coef_t'].get('r'), 2)}), bottom "
              f"{_s(st['bottom']['coef_means'].get('r'), 4)} (t {_s(st['bottom']['coef_t'].get('r'), 2)}). Coverage: "
              f"{_f(S['cover'] * 100 if S['cover'] is not None else None, 1)}% of member-days have every regressor (prices from "
              f"today's 901-symbol set: removed members under-represented; the size terciles are terciles of the priced "
              f"members). A slope is not a trade: no costs enter this claim")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-692 ==

def iso_weeks(days: Sequence[str]) -> tuple:
    """(first session index, last session index) of each ISO week of the calendar, in order."""
    s0, s1, prev = [], [], None
    for i, d in enumerate(days):
        y, w, _ = date.fromisoformat(d).isocalendar()
        if (y, w) != prev:
            if prev is not None:
                s1.append(i - 1)
            s0.append(i)
            prev = (y, w)
    s1.append(len(days) - 1)
    return np.array(s0, int), np.array(s1, int)


def roll_beta(R, M, w: int, min_obs: int) -> np.ndarray:
    """Rolling OLS slope of each column of R on the market column M over rows i-w+1..i (pairs with both finite)."""
    Mb = np.broadcast_to(M[:, None], R.shape)
    ok = np.isfinite(R) & np.isfinite(Mb)
    x, y = np.where(ok, Mb, 0.0), np.where(ok, R, 0.0)
    n = roll_sum(ok.astype(float), w, True)
    sx, sy = roll_sum(x, w, True), roll_sum(y, w, True)
    sxy, sxx = roll_sum(x * y, w, True), roll_sum(x * x, w, True)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (sxy - sx * sy / n) / (sxx - sx * sx / n)
    return np.where(n >= min_obs, b, np.nan)


def weekly_panel(A, V, member, s0, s1) -> dict:
    """Week x name: weekly volume (every session of the week with a finite volume), log volume, weekly adjclose
    return (last close to last close), the raw surprise (log volume minus its mean over the 49 previous weeks, all
    valid), the idiosyncratic surprise (minus the week's cross-sectional mean over members), the trailing 52-week sd
    of weekly returns (weeks w-52..w-1, all valid) and membership at the week's last session. Week w uses sessions up
    to s1[w] only."""
    Wk = s0.size
    cV = np.concatenate([np.zeros((1, V.shape[1])), np.cumsum(np.where(np.isfinite(V), V, 0.0), axis=0)])
    cN = np.concatenate([np.zeros((1, V.shape[1])), np.cumsum(np.isfinite(V), axis=0)])
    vol = cV[s1 + 1] - cV[s0]
    cnt = cN[s1 + 1] - cN[s0]
    full = cnt == (s1 - s0 + 1)[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.where(full & (vol > 0), np.log(np.where(vol > 0, vol, 1.0)), np.nan)
        Al = A[s1]
        ret = np.full(Al.shape, np.nan)
        ret[1:] = Al[1:] / Al[:-1] - 1.0
    okl = np.isfinite(lv)
    sl = roll_sum(np.where(okl, lv, 0.0), T692_VWIN, False)
    cl = roll_sum(okl.astype(float), T692_VWIN, False)
    raw = np.where(cl >= T692_VWIN, lv - sl / T692_VWIN, np.nan)
    okr = np.isfinite(ret)
    sr = roll_sum(np.where(okr, ret, 0.0), T692_SWIN, False)
    sr2 = roll_sum(np.where(okr, ret * ret, 0.0), T692_SWIN, False)
    cr = roll_sum(okr.astype(float), T692_SWIN, False)
    with np.errstate(invalid="ignore"):
        sig = np.where(cr >= T692_SWIN, np.sqrt(np.maximum((sr2 - sr * sr / T692_SWIN) / (T692_SWIN - 1), 0.0)), np.nan)
    mem = member[s1]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mu = np.nanmean(np.where(mem & np.isfinite(raw), raw, np.nan), axis=1)
    idio = np.where(mem, raw - mu[:, None], np.nan)
    return {"lv": lv, "ret": ret, "raw": raw, "idio": idio, "sig": sig, "mem": mem, "Wk": Wk}


def week_flags(W: dict, high: bool = True) -> np.ndarray:
    """Visibility events: the idiosyncratic surprise in the week's top decile (>= its 90th percentile among members;
    ``high`` False: the bottom decile, <= the 10th) and |weekly return| <= the trailing sigma."""
    idio, ret, sig = W["idio"], W["ret"], W["sig"]
    ok = np.isfinite(idio) & np.isfinite(ret) & np.isfinite(sig)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q = np.nanquantile(np.where(ok, idio, np.nan), 0.9 if high else 0.1, axis=1)
    with np.errstate(invalid="ignore"):
        tail = idio >= q[:, None] if high else idio <= q[:, None]
        return ok & tail & (np.abs(ret) <= sig)


def dedupe_events(F: np.ndarray, entry: np.ndarray, gap: int = T692_HOLD) -> np.ndarray:
    """Per name keep the first of repeat events whose entries are within ``gap`` sessions of the last kept one."""
    out = np.zeros_like(F)
    for j in range(F.shape[1]):
        last = -10 ** 9
        for w in np.flatnonzero(F[:, j]):
            if entry[w] - last >= gap:
                out[w, j] = True
                last = entry[w]
    return out


def t692_inputs(archive) -> dict:
    def load():
        B = vbase(archive)
        days = B["days"]
        i0 = bisect.bisect_left(days, "2005-01-01")
        dd = days[i0:]
        A, C, O, V = (B[k][i0:] for k in ("adjclose", "close", "open", "volume"))
        mem = B["member"][i0:]
        spy = {k: v[i0:] for k, v in B["mkt"]["SPY"].items()}
        D, N = A.shape
        s0, s1 = iso_weeks(dd)
        W = weekly_panel(A, V, mem, s0, s1)
        with np.errstate(invalid="ignore", divide="ignore"):
            R = np.full((D, N), np.nan)
            R[1:] = A[1:] / A[:-1] - 1.0
            m = spy["adjclose"]
            Mr = np.full(D, np.nan)
            Mr[1:] = m[1:] / m[:-1] - 1.0
        beta_d = roll_beta(R, Mr, T692_BWIN, T692_BMIN)
        del R
        with np.errstate(invalid="ignore", divide="ignore"):
            AO = O * (A / C)
            MO = spy["open"] * (spy["adjclose"] / spy["close"])
        Wk = s0.size
        entry = np.full(Wk, -1)
        entry[:-1] = s0[1:]
        exit_ = np.where(entry >= 0, entry + T692_HOLD, -1)
        okw = (entry >= 0) & (exit_ < D)
        e_, x_ = np.where(okw, entry, 0), np.where(okw, exit_, 0)
        bills = SX._bills(archive)
        with np.errstate(invalid="ignore", divide="ignore"):
            Wr = AO[x_] / AO[e_] - 1.0
            Mw = MO[x_] / MO[e_] - 1.0
        rf = np.array([bills.growth(dd[e], dd[x]) - 1.0 if ok else np.nan for e, x, ok in zip(e_, x_, okw)])
        beta_w = beta_d[s1]
        Wr[~okw] = np.nan
        plain = Wr - beta_w * Mw[:, None]
        capm = (Wr - rf[:, None]) - beta_w * (Mw - rf)[:, None]
        wdays = np.array([dd[i] for i in s1])
        inwin = (wdays >= T692_START) & (wdays <= T692_END)
        valid = W["mem"] & np.isfinite(plain) & np.isfinite(capm) & inwin[:, None]
        Fh = week_flags(W, True) & valid
        Fl = week_flags(W, False) & valid
        Eh, El = dedupe_events(Fh, entry), dedupe_events(Fl, entry)
        # calendar-time pieces: open-to-open interval returns from forward-filled adjusted opens
        AOf = _ffill(AO)
        MOf = _ffill(MO[:, None])[:, 0]
        # size at the week's close: median dollar volume over the 60 sessions ending there
        dv = np.where(np.isfinite(V) & np.isfinite(C), C * V, np.nan)
        size_w = roll_median(dv, 60)[s1]
        cover = {"member_weeks": int(W["mem"][inwin].sum()),
                 "member_weeks_all": int(sum(int(B["n_members"][i0 + i]) for i in s1[inwin])),
                 "with_surprise": int((W["mem"] & np.isfinite(W["idio"]) & np.isfinite(W["sig"]) & np.isfinite(W["ret"]))[inwin].sum())}
        return {"days": dd, "s0": s0, "s1": s1, "wdays": wdays, "entry": entry, "exit": exit_, "plain": plain,
                "capm": capm, "beta_w": beta_w, "valid": valid, "Eh": Eh, "El": El, "AOf": AOf, "MOf": MOf,
                "rf_daily": np.array([bills.growth(dd[k], dd[k + 1]) - 1.0 for k in range(D - 1)] + [0.0]),
                "size_w": size_w, "cover": cover, "syms": B["syms"], "ciks": B["ciks"], "ret_w": W["ret"],
                "idio": W["idio"], "sig": W["sig"]}
    return CAL._cached(archive, ("b13va_t692",), load)


def block_shift_p(E: np.ndarray, Y: np.ndarray, valid: np.ndarray, obs: float, n_shift: int = T692_N_SHIFT,
                  min_off: int = 5, seed: int = SEED) -> dict:
    """The block-shift placebo (T-419's): each name's event-week pattern shifted circularly by an independent random
    offset of at least ``min_off`` weeks either way, the pooled mean outcome over the shifted events that land on valid
    weeks recomputed; p = (1 + #{placebo mean >= observed}) / (1 + shifts). All offsets at once by FFT correlation."""
    Wk = E.shape[0]
    keep = E.any(axis=0)
    if not keep.any():
        return {"p": None, "n_shift": 0}
    Ef = np.fft.rfft(E[:, keep].astype(float), axis=0)
    Yv = np.where(valid[:, keep], np.nan_to_num(Y[:, keep]), 0.0)
    S = np.fft.irfft(np.conj(Ef) * np.fft.rfft(Yv, axis=0), Wk, axis=0)
    Cn = np.rint(np.fft.irfft(np.conj(Ef) * np.fft.rfft(valid[:, keep].astype(float), axis=0), Wk, axis=0))
    rng = np.random.default_rng(seed)
    k = rng.integers(min_off, Wk - min_off + 1, size=(n_shift, int(keep.sum())))
    cols = np.arange(int(keep.sum()))[None, :]
    num = S[k, cols].sum(axis=1)
    den = Cn[k, cols].sum(axis=1)
    ok = den > 0
    m = num[ok] / den[ok]
    return {"p": float((1 + np.sum(m >= obs)) / (1 + m.size)), "n_shift": int(m.size), "null_mean": float(m.mean()),
            "null_q99": float(np.quantile(m, 0.99))}


def calendar_time(I: dict, E: np.ndarray, reading: str, cost: float = T692_COST) -> dict:
    """Daily calendar-time portfolio: each session the equal-weighted mean over active events of the open-to-open
    abnormal return of interval k -> k+1 (W - beta x SPY, or the CAPM form), half the round trip charged on an event's
    first and on its last interval. Sessions from the first entry to the last exit."""
    AOf, MOf = I["AOf"], I["MOf"]
    D = AOf.shape[0]
    with np.errstate(invalid="ignore", divide="ignore"):
        Rk = np.full(AOf.shape, np.nan)
        Rk[:-1] = AOf[1:] / AOf[:-1] - 1.0
        Mk = np.full(D, np.nan)
        Mk[:-1] = MOf[1:] / MOf[:-1] - 1.0
    rf = I["rf_daily"]
    tot = np.zeros(D)
    cnt = np.zeros(D)
    ws, js = np.nonzero(E)
    for w, j in zip(ws, js):
        e = int(I["entry"][w])
        ks = np.arange(e, e + T692_HOLD)
        b = I["beta_w"][w, j]
        if reading == "plain":
            a = Rk[ks, j] - b * Mk[ks]
        else:
            a = (Rk[ks, j] - rf[ks]) - b * (Mk[ks] - rf[ks])
        a = np.nan_to_num(a, nan=0.0)
        a[0] -= cost / 2.0
        a[-1] -= cost / 2.0
        tot[ks] += a
        cnt[ks] += 1
    act = np.flatnonzero(cnt > 0)
    if not act.size:
        return {"net": np.zeros(0), "mean_active": 0.0}
    sl = slice(int(act[0]), int(act[-1]) + 1)
    x = np.where(cnt[sl] > 0, tot[sl] / np.maximum(cnt[sl], 1), 0.0)
    return {"net": x, "mean_active": float(cnt[sl].mean()), "days": int(x.size)}


def dsr_bound(x, n_min: int, n_full: int, label: str) -> tuple:
    """DSR criterion when the family's other Sharpes are not computed here: the most favourable trial-Sharpe variance
    (the 1/(T-1) floor) at the smallest admissible trial count bounds the DSR from above. Fails when that bound misses
    0.95 (decisive when PSR vs 0 <= 0.05); undecided otherwise."""
    x = np.asarray(x, float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_min, var_trials_sr=floor))
    full = float(deflated_sharpe_ratio(x, n_trials=n_full, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_bound": hi, "dsr_full_count_floor": full, "n_min": n_min, "n_full": n_full, "var_floor": floor,
            "psr0": psr0, "sharpe_pp": float(sharpe_ratio(x))}
    txt = f"{label} (at most {hi:.3f} at {n_min} trials and the 1/(T-1) floor; PSR vs 0 {psr0:.3f})"
    if hi <= DSR_PASS:
        return (txt + " [fails whatever the uncomputed family Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + " [T-419's 36 cell Sharpes are not computed here: cannot pass]", None, False), info


def sec_filing_days(archive, ciks: set, forms=("10-Q", "10-K", "10-KT", "10-Q/A", "10-K/A")) -> dict:
    """{cik: sorted acceptance dates (YYYY-MM-DD, available_at)} of the periodic reports in sec-submissions."""
    def load():
        names = set(SX._entry_names(archive, SUBS_PREFIX))
        out = defaultdict(list)
        for b in sorted({SX.sec_bucket(c) for c in ciks}):
            n = SUBS_PREFIX + b
            if n not in names:
                continue
            for r in SX._stream(archive, n):
                if r.get("kind") != "filing":
                    continue
                v = r.get("value") or {}
                if v.get("form") not in forms:
                    continue
                try:
                    c = int(v.get("cik"))
                except (TypeError, ValueError):
                    continue
                if c in ciks and r.get("available_at"):
                    out[c].append(str(r["available_at"])[:10])
        return {c: sorted(v) for c, v in out.items()}
    return CAL._cached(archive, ("b13va_filings", frozenset(ciks)), load)


def _ev_list(I, E, Y) -> tuple:
    ws, js = np.nonzero(E)
    return Y[ws, js] - T692_COST, ws, js


def b13_volume_a_visibility(archive):
    """T-692."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B, DTB3_B]) or _prefix_missing(archive, [DH_PREFIX, SUBS_PREFIX])
    if miss:
        return miss
    I = t692_inputs(archive)
    E = I["Eh"]
    readings = {}
    for rd in ("plain", "capm"):
        x, ws, js = _ev_list(I, E, I[rd])
        lab = [str(I["wdays"][w]) for w in ws]
        cs = cluster_stud(x, lab) if x.size >= 4 else {"ci": [None, None]}
        plc = block_shift_p(E, I[rd] - T692_COST, I["valid"], float(x.mean()) if x.size else 0.0)
        ct = calendar_time(I, E, rd)
        hac = hac_mean(ct["net"], T692_NW_LAG) if ct["net"].size > 30 else {"t": None}
        wd = I["wdays"][ws]
        h1 = wd < T692_SPLIT
        readings[rd] = {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "ci": cs.get("ci"),
                        "clusters": cs.get("clusters"), "placebo": plc, "ct_mean": float(ct["net"].mean()) if ct["net"].size else None,
                        "ct_t": hac.get("t"), "ct_days": ct.get("days"), "ct_active": ct.get("mean_active"),
                        "halves": [float(x[h1].mean()) if h1.any() else None, float(x[~h1].mean()) if (~h1).any() else None],
                        "halves_n": [int(h1.sum()), int((~h1).sum())], "ct_net": ct["net"], "x": x, "ws": ws, "js": js}
    n = readings["plain"]["n"]
    if n < 4:
        return _out({"n": n}, n, "inconclusive", f"only {n} visibility events")

    def both(fn):
        return CAL._agree([fn(readings[r]) for r in ("plain", "capm")])
    lab = lambda fmt: "; ".join(f"{r} {fmt(readings[r])}" for r in ("plain", "capm"))
    c_mean = (f"mean net 20-session beta-adjusted return >= +50 bp ({lab(lambda R: _bp(R['mean']))})",
              both(lambda R: R["mean"] >= T692_BAR), False)
    c_ci = (f"date-clustered 95% lower bound > 0 ({lab(lambda R: _bp((R['ci'] or [None])[0]))}; "
            f"{readings['plain']['clusters']} event weeks)", both(lambda R: None if (R["ci"] or [None])[0] is None else R["ci"][0] > 0),
            all((R["ci"] or [None, None])[1] is not None and R["ci"][1] < 0 for R in readings.values()))
    c_plc = (f"block-shift placebo ({T692_N_SHIFT} within-name shifts) p < {T692_P} ({lab(lambda R: _f(R['placebo'].get('p'), 4))})",
             both(lambda R: None if R["placebo"].get("p") is None else R["placebo"]["p"] < T692_P), False)
    c_ct = (f"calendar-time portfolio HAC (lag {T692_NW_LAG}) t >= {T692_T} ({lab(lambda R: _s(R['ct_t'], 2))})",
            both(lambda R: None if R["ct_t"] is None else R["ct_t"] >= T692_T),
            all(R["ct_t"] is not None and R["ct_t"] < -1.645 for R in readings.values()))
    c_h = (f"both halves positive (2008-2016 / 2017-2026: {lab(lambda R: _bp(R['halves'][0]) + ' / ' + _bp(R['halves'][1]))})",
           both(lambda R: None if None in R["halves"] else all(h > 0 for h in R["halves"])), False)
    c_dsr, dsr_info = dsr_bound(readings["plain"]["ct_net"], T692_TRIALS, T692_TRIALS,
                                f"DSR >= {DSR_PASS} counting T-419's 36 cells plus this one (calendar-time daily net)")
    crit = [c_mean, c_ci, c_plc, c_ct, c_h, c_dsr]
    v, why, crit_j = CAL._judge(crit, n, T692_MIN_N, "events")
    # ---- reported only
    P = readings["plain"]
    x, ws, js = P["x"], P["ws"], P["js"]
    sz = I["size_w"][ws, js]
    terc = {}
    for t, (a, b) in {"small": (0, 1 / 3), "mid": (1 / 3, 2 / 3), "large": (2 / 3, 1.01)}.items():
        sel = []
        for k in range(x.size):
            row = I["size_w"][ws[k]]
            okr = I["valid"][ws[k]] & np.isfinite(row)
            if not np.isfinite(sz[k]) or not okr.any():
                sel.append(False)
                continue
            q = float((row[okr] < sz[k]).mean())
            sel.append(a <= q < b)
        sel = np.array(sel, bool)
        terc[t] = {"n": int(sel.sum()), "mean": float(x[sel].mean()) if sel.any() else None}
    xl, _wl, _jl = _ev_list(I, I["El"], I["plain"])
    ciks = {c for c in I["ciks"] if c is not None}
    fil = sec_filing_days(archive, ciks)
    near = []
    for k in range(x.size):
        c = I["ciks"][js[k]]
        dd = date.fromisoformat(str(I["wdays"][ws[k]]))
        a, b = (dd + timedelta(days=5)).isoformat(), (dd + timedelta(days=35)).isoformat()
        lst = fil.get(c, [])
        i = bisect.bisect_left(lst, a)
        near.append(i < len(lst) and lst[i] <= b)
    near = np.array(near, bool)
    has_fil = np.array([I["ciks"][j] in fil for j in js], bool)
    vix = CAL._series(archive, VIX_B) if B7C._has(archive, VIX_B) else {}
    hv = np.array([(vix.get(str(I["wdays"][w])) or 0) > 30 for w in ws], bool)
    y2021 = np.array([str(I["wdays"][w])[:4] in ("2020", "2021") for w in ws], bool)
    cov = I["cover"]
    share_cov = cov["with_surprise"] / cov["member_weeks_all"] if cov["member_weeks_all"] else None
    rate = n / cov["with_surprise"] if cov["with_surprise"] else 0.0
    n_abs = rate * max(0, cov["member_weeks_all"] - cov["with_surprise"])
    flip0 = -n * P["mean"] / n_abs if n_abs > 0 else None
    flip50 = (T692_BAR * (n + n_abs) - n * P["mean"]) / n_abs if n_abs > 0 else None
    wsd = sorted(str(d) for d in I["wdays"][ws])
    stat = {"n": n, "first": wsd[0], "last": wsd[-1],
            "readings": {r: {k: R[k] for k in ("n", "mean", "ci", "clusters", "placebo", "ct_mean", "ct_t", "ct_days",
                                                "ct_active", "halves", "halves_n")} for r, R in readings.items()},
            "dsr": dsr_info, "size_terciles": terc,
            "low_volume_bucket": {"n": int(xl.size), "mean": float(xl.mean()) if xl.size else None},
            "earnings_window_share": float(near[has_fil].mean()) if has_fil.any() else None,
            "earnings_window_mean": {"near": float(x[near].mean()) if near.any() else None,
                                     "other": float(x[~near & has_fil].mean()) if (~near & has_fil).any() else None},
            "vix_gt_30": {"n": int(hv.sum()), "mean": float(x[hv].mean()) if hv.any() else None},
            "y2020_21": {"n": int(y2021.sum()), "mean": float(x[y2021].mean()) if y2021.any() else None},
            "coverage": cov, "member_weeks_covered_share": share_cov, "absent_events_est": n_abs,
            "flip_bound_zero": flip0, "flip_bound_50bp": flip50, "criteria": crit_j, "verdict": v}
    R1, R2 = readings["plain"], readings["capm"]
    reason = (f"Visibility weeks (idiosyncratic weekly volume surprise in the week's top decile, |return| <= trailing "
              f"52-week sigma) on point-in-time S&P 500 members with prices, event weeks {stat['first']}..{stat['last']}: "
              f"{n} events after keeping the first of repeats within 20 sessions; net 20-session beta-adjusted return from the "
              f"next week's first open (10 bp round trip): W - beta SPY {_bp(R1['mean'])} (date-clustered 95% CI "
              f"{_bp((R1['ci'] or [None])[0])}..{_bp((R1['ci'] or [None, None])[1])}), CAPM form {_bp(R2['mean'])}; "
              f"block-shift placebo p {_f(R1['placebo'].get('p'), 4)} / {_f(R2['placebo'].get('p'), 4)} (null mean "
              f"{_bp(R1['placebo'].get('null_mean'))}); calendar-time HAC t {_s(R1['ct_t'], 2)} / {_s(R2['ct_t'], 2)} "
              f"({R1['ct_days']} sessions, {_f(R1['ct_active'], 1)} events active on average); halves "
              f"{_bp(R1['halves'][0])} / {_bp(R1['halves'][1])}; DSR bound {_f(dsr_info.get('dsr_bound'))} at 37 trials. "
              f"Reported: size terciles small {_bp(terc['small']['mean'])} ({terc['small']['n']}), mid "
              f"{_bp(terc['mid']['mean'])} ({terc['mid']['n']}), large {_bp(terc['large']['mean'])} ({terc['large']['n']}); "
              f"bottom-decile low-volume bucket {_bp(stat['low_volume_bucket']['mean'])} ({xl.size} events; GKM predict "
              f"negative); {_f(stat['earnings_window_share'] * 100 if stat['earnings_window_share'] is not None else None, 1)}% "
              f"of events lie 5-35 days before a 10-Q/10-K acceptance (rough earnings flag; mean {_bp(stat['earnings_window_mean']['near'])} "
              f"vs {_bp(stat['earnings_window_mean']['other'])}); VIX > 30 weeks {_bp(stat['vix_gt_30']['mean'])} "
              f"({int(hv.sum())}); 2020-21 {_bp(stat['y2020_21']['mean'])} ({int(y2021.sum())}). Coverage: "
              f"{_f(share_cov * 100 if share_cov is not None else None, 1)}% of member-weeks priced with a surprise; about "
              f"{n_abs:.0f} absent events would need a mean of {_bp(flip0)} to bring the mean to zero ({_bp(flip50)} to bring "
              f"it below +50 bp). Survivorship (today's 901-symbol set; removed members absent) favours the claim, as the "
              f"registration states")
    return _out(stat, n, v, reason + " — " + why)


# ============================================================================================ T-693 / T-694 ==

def hodrick_ols(y, X, a, h: int, r) -> dict:
    """OLS of window-sum targets y (y_j = r[a_j+1] + ... + r[a_j+h]) on X (with its own constant) and Hodrick (1992) 1B
    standard errors: under the null each target is the sum of its periods' demeaned one-period values u_s, so X'e =
    sum_s u_s q_s with q_s = the sum of X_j over the windows holding s; V = (X'X)^-1 [sum_s u_s^2 q_s q_s'] (X'X)^-1."""
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


def cw_stats(y, fb, fm, lag: int) -> dict:
    """Campbell-Thompson R^2_OS of forecast fm against benchmark fb and the Clark-West MSPE-adjusted statistic with a
    Newey-West (``lag``) t; p = one-sided normal p for H0: no improvement."""
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    if y.size < 10:
        return {"n": int(y.size), "r2": None, "cw_t": None, "p": None, "lag": lag}
    e1, e2 = y - fb, y - fm
    f = e1 ** 2 - (e2 ** 2 - (fb - fm) ** 2)
    h = hac_mean(f, lag)
    den = float(e1 @ e1)
    return {"n": int(y.size), "r2": 1.0 - float(e2 @ e2) / den if den > 0 else None, "cw_t": h["t"], "p": h["p"], "lag": lag}


def _ols1(x, y) -> tuple:
    x, y = np.asarray(x, float), np.asarray(y, float)
    xm = x.mean()
    vx = float(((x - xm) ** 2).sum())
    b = float(((x - xm) * (y - y.mean())).sum() / vx) if vx > 0 else 0.0
    return float(y.mean() - b * xm), b


def months_base(archive) -> dict:
    """Month list of the session calendar with each month's first and last session index."""
    def load():
        B = vbase(archive)
        days = B["days"]
        first, last = month_first_sessions(days), month_last_sessions(days)
        ms = sorted(last)
        return {"months": ms, "first": np.array([first[m] for m in ms], int), "last": np.array([last[m] for m in ms], int)}
    return CAL._cached(archive, ("b13va_months",), load)


def month_returns(px: np.ndarray, last: np.ndarray) -> np.ndarray:
    """Month-end to month-end simple returns of one price series (NaN without both bars)."""
    p = px[last]
    out = np.full(last.size, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[1:] = p[1:] / p[:-1] - 1.0
    return out


def bill_months(archive, days, last) -> np.ndarray:
    """Bill growth - 1 over each month (previous month-end close to this one)."""
    bills = SX._bills(archive)
    out = np.full(last.size, np.nan)
    for k in range(1, last.size):
        out[k] = bills.growth(days[last[k - 1]], days[last[k]]) - 1.0
    return out


def aggregate_illiq(A, C, V, member, Fs, gs, fs, ls, k0: int, min_names: int = 30) -> tuple:
    """(L, L_ap, counts) by month: L_m = log(mean over members at the month's last session with >= T693_MIN_DAYS valid
    days and raw price > T693_MIN_PRICE of mean |r_d| / (close_d x volume_d / 1e6)) + log(^GSPC(first month) /
    ^GSPC(m-1)); L_ap the other scaling. Month m uses sessions up to its last session only."""
    D, N = A.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.full((D, N), np.nan)
        R[1:] = A[1:] / A[:-1] - 1.0
        DV = C * V / 1e6
        ratio = np.abs(R) / DV
    ok = np.isfinite(ratio) & (DV > 0)
    cr = np.concatenate([np.zeros((1, N)), np.cumsum(np.where(ok, ratio, 0.0), axis=0)])
    cn = np.concatenate([np.zeros((1, N)), np.cumsum(ok, axis=0)])
    del R, DV, ratio, ok
    g_first = gs[ls[k0]]
    M = len(ls)
    L, L_ap = np.full(M, np.nan), np.full(M, np.nan)
    counts = np.zeros(M, int)
    for k in range(max(k0, 1), M):
        a, b = fs[k], ls[k]
        s = cr[b + 1] - cr[a]
        c = cn[b + 1] - cn[a]
        with np.errstate(invalid="ignore"):
            raw = C[b] * Fs[b]
            el = member[b] & (c >= T693_MIN_DAYS) & np.isfinite(raw) & (raw > T693_MIN_PRICE)
        if el.sum() < min_names:
            continue
        illiq = float((s[el] / c[el]).mean())
        counts[k] = int(el.sum())
        L[k] = math.log(illiq * g_first / gs[ls[k - 1]])
        L_ap[k] = math.log(illiq * gs[ls[k - 1]] / g_first)
    return L, L_ap, counts


def ar1_expectation(L: np.ndarray, k0: int) -> tuple:
    """Real-time AR(1) expectation of L_{m+1} at the end of m, fitted on months k0..m (>= 24 pairs)."""
    X = np.full(L.size, np.nan)
    rho = np.full(L.size, np.nan)
    for k in range(k0 + 1, L.size):
        yy, xx = L[k0 + 1:k + 1], L[k0:k]
        m = np.isfinite(yy) & np.isfinite(xx)
        if m.sum() < 24 or not np.isfinite(L[k]):
            continue
        c0, c1 = _ols1(xx[m], yy[m])
        X[k] = c0 + c1 * L[k]
        rho[k] = c1
    return X, rho


def tercile_rule(X: np.ndarray, ks: np.ndarray, y: np.ndarray, window: Optional[int]) -> tuple:
    """In the asset when X_k is at or above the 2/3 quantile of its real-time history (all months up to k, or the
    last ``window`` months), bills otherwise; 5 bp per switch (the first entry counts). Returns (rule, positions)."""
    pos = np.zeros(ks.size)
    for i, k in enumerate(ks):
        h = X[:k + 1] if window is None else X[max(0, k + 1 - window):k + 1]
        h = h[np.isfinite(h)]
        pos[i] = float(X[k] >= np.quantile(h, 2.0 / 3.0)) if h.size >= 12 else 0.0
    sw = np.abs(np.diff(np.r_[0.0, pos]))
    return pos * y - T693_COST * sw, pos


def t693_signal(archive) -> dict:
    """Monthly log aggregate ILLIQ (members at the month's last session, >= 15 valid days, raw price > $5), scaled by
    ^GSPC(first month) / ^GSPC(m-1), from 1997-01; and the real-time expanding AR(1) expected value X_m."""
    def load():
        B = vbase(archive)
        MB = months_base(archive)
        days = B["days"]
        ms, fs, ls = MB["months"], MB["first"], MB["last"]
        A, C, V = B["adjclose"], B["close"], B["volume"]
        splits = all_splits(archive, list(B["syms"]) + sorted(B["class_close"]))
        Fs = split_factor_matrix(days, B["syms"], splits)
        gs = B["mkt"]["-GSPC"]["close"]
        k0 = ms.index(T693_FIRST_MONTH)
        L, L_ap, counts = aggregate_illiq(A, C, V, B["member"] & B["in_spells"][None, :], Fs, gs, fs, ls, k0)
        n_members = np.array([int(B["n_members"][b]) for b in ls])
        X, rho = ar1_expectation(L, k0)
        X_ap, _ = ar1_expectation(L_ap, k0)
        return {"months": ms, "L": L, "X": X, "rho": rho, "counts": counts, "n_members": n_members, "L_ap": L_ap,
                "X_ap": X_ap}
    return CAL._cached(archive, ("b13va_t693_sig",), load)


def expanding_1step(x, y, k0: int, k1: int, min_train: int) -> dict:
    """Forecasts of y[k+1] from x[k] at origins k in [k0, k1]: OLS on the pairs (x[j], y[j+1]) with j + 1 <= k, the
    benchmark their mean of y."""
    out = {"k": [], "y": [], "fm": [], "fb": [], "slope": []}
    for k in range(k0, k1 + 1):
        if k + 1 >= y.size or not (np.isfinite(x[k]) and np.isfinite(y[k + 1])):
            continue
        j = np.arange(0, k)
        j = j[np.isfinite(x[j]) & np.isfinite(y[j + 1])]
        if j.size < min_train:
            continue
        a, b = _ols1(x[j], y[j + 1])
        out["k"].append(k); out["y"].append(float(y[k + 1])); out["fm"].append(a + b * x[k])
        out["fb"].append(float(y[j + 1].mean())); out["slope"].append(b)
    return {k: np.array(v) for k, v in out.items()}


def stationary_sharpe_diff(a, b, mean_block: float = T693_MEAN_BLOCK, n_boot: int = T693_NBOOT, seed: int = SEED) -> dict:
    """Annualised Sharpe(a) - Sharpe(b) (monthly) with a paired stationary bootstrap: p = share of centred draws >= the
    observed difference (H0: difference <= 0)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = a.size
    sr = lambda x: float(sharpe_ratio(x, 12))
    d = sr(a) - sr(b)
    rng = np.random.default_rng(seed)
    idx = SX._stat_idx(rng, n, mean_block, n_boot)
    A, Bm = a[idx], b[idx]

    def srow(X):
        s = X.std(axis=1, ddof=1)
        return np.where(s > 0, X.mean(axis=1) / np.where(s > 0, s, 1.0), 0.0) * math.sqrt(12)
    db = srow(A) - srow(Bm)
    p = float((np.sum(db - d >= d) + 1) / (db.size + 1))
    return {"sharpe_a": sr(a), "sharpe_b": sr(b), "diff": d, "p": p, "ci": [float(np.quantile(db, 0.025)), float(np.quantile(db, 0.975))]}


def t693_core(archive) -> dict:
    def load():
        B = vbase(archive)
        MB = months_base(archive)
        S = t693_signal(archive)
        ms, ls = MB["months"], MB["last"]
        days = B["days"]
        rf = bill_months(archive, days, ls)
        iwm = month_returns(B["mkt"]["IWM"]["adjclose"], ls)
        spy = month_returns(B["mkt"]["SPY"]["adjclose"], ls)
        tg = {"IWM": iwm - rf, "SPY": spy - rf, "IWM-SPY": iwm - spy}
        k0, k1 = ms.index(madd(T693_FIRST_TARGET, -1)), ms.index(madd(T693_LAST_TARGET, -1))
        X = S["X"]
        res = {}
        for nm, y in tg.items():
            fc = expanding_1step(X, y, k0, k1, T693_MIN_TRAIN)
            cw = cw_stats(fc["y"], fc["fb"], fc["fm"], T693_CW_LAG)
            res[nm] = {"fc": fc, "cw": cw}
        return {"months": ms, "X": X, "targets": tg, "res": res, "signal": S, "rf": rf, "k0": k0, "k1": k1}
    return CAL._cached(archive, ("b13va_t693_core",), load)


def detrended_turnover(V, member, fs, ls, hist: int = T694_HIST, min_names: int = 30) -> tuple:
    """(S, names, log monthly volume, detrended) by month: a name-month is valid with a bar and finite volume on every
    session of the month; detrended = log volume minus the name's mean over the ``hist`` previous months (all valid);
    S_m = the mean over members at the month's last session. Month m uses sessions up to its last session only."""
    N = V.shape[1]
    cV = np.concatenate([np.zeros((1, N)), np.cumsum(np.where(np.isfinite(V), V, 0.0), axis=0)])
    cN = np.concatenate([np.zeros((1, N)), np.cumsum(np.isfinite(V), axis=0)])
    vol = cV[ls + 1] - cV[fs]
    cnt = cN[ls + 1] - cN[fs]
    full = cnt == (ls - fs + 1)[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.where(full & (vol > 0), np.log(np.where(vol > 0, vol, 1.0)), np.nan)
    ok = np.isfinite(lv)
    s = roll_sum(np.where(ok, lv, 0.0), hist, False)
    c = roll_sum(ok.astype(float), hist, False)
    det = np.where(c >= hist, lv - s / hist, np.nan)
    memm = member[ls]
    S = np.full(len(ls), np.nan)
    nS = np.zeros(len(ls), int)
    for k in range(len(ls)):
        m = memm[k] & np.isfinite(det[k])
        if m.sum() >= min_names:
            S[k] = float(det[k][m].mean())
            nS[k] = int(m.sum())
    return S, nS, lv, det


def t694_signal(archive) -> dict:
    """Monthly detrended aggregate turnover S_m and the members' equal-weighted monthly log excess return g_m."""
    def load():
        B = vbase(archive)
        MB = months_base(archive)
        days = B["days"]
        ms, fs, ls = MB["months"], MB["first"], MB["last"]
        A, V = B["adjclose"], B["volume"]
        D, N = A.shape
        Sx, nS, lv, det = detrended_turnover(V, B["member"], fs, ls)
        memm = B["member"][ls]
        real = np.isfinite(A)
        Aff = _ffill(A)
        lastbar = np.where(real.any(axis=0), D - 1 - real[::-1].argmax(axis=0), -1)
        rf = bill_months(archive, days, ls)
        ew = np.full(len(ms), np.nan)
        nE = np.zeros(len(ms), int)
        for k in range(1, len(ms)):
            a, b = ls[k - 1], ls[k]
            m = memm[k - 1] & real[a] & (lastbar > a)
            if m.sum() < 30:
                continue
            xe = np.minimum(b, lastbar)
            with np.errstate(invalid="ignore", divide="ignore"):
                r = Aff[xe, np.arange(N)] / A[a] - 1.0
            r = r[m & np.isfinite(r)]
            ew[k] = float(r.mean())
            nE[k] = int(r.size)
        g = np.log1p(ew) - np.log1p(rf)
        spy = month_returns(B["mkt"]["SPY"]["adjclose"], ls)
        gs = np.log1p(spy) - np.log1p(rf)
        return {"months": ms, "S": Sx, "nS": nS, "g": g, "g_spy": gs, "ew": ew, "rf": rf, "nE": nE,
                "n_members": B["n_members"][ls], "lv": lv, "det": det}
    return CAL._cached(archive, ("b13va_t694_sig",), load)


def window_sums(g, h: int) -> np.ndarray:
    """y[m] = g[m+1] + ... + g[m+h] (NaN unless all are finite)."""
    n = g.size
    y = np.full(n, np.nan)
    for m in range(n - h):
        w = g[m + 1:m + h + 1]
        if np.isfinite(w).all():
            y[m] = float(w.sum())
    return y


def expanding_h(x, y, k0: int, k1: int, h: int, min_train: int) -> dict:
    """Forecasts of the h-period target y[k] (realised at k + h) from x[k] at origins k in [k0, k1]: OLS on the pairs
    (x[j], y[j]) with j <= k - h (targets realised by the origin), the benchmark their mean."""
    out = {"k": [], "y": [], "fm": [], "fb": [], "slope": []}
    for k in range(k0, k1 + 1):
        if not (np.isfinite(x[k]) and np.isfinite(y[k])):
            continue
        j = np.arange(0, max(0, k - h + 1))
        j = j[np.isfinite(x[j]) & np.isfinite(y[j])]
        if j.size < min_train:
            continue
        a, b = _ols1(x[j], y[j])
        out["k"].append(k); out["y"].append(float(y[k])); out["fm"].append(a + b * x[k])
        out["fb"].append(float(y[j].mean())); out["slope"].append(b)
    return {k: np.array(v) for k, v in out.items()}


def t694_core(archive) -> dict:
    def load():
        S = t694_signal(archive)
        ms = S["months"]
        y = window_sums(S["g"], T694_H)
        y_spy = window_sums(S["g_spy"], T694_H)
        k0, k1 = ms.index(T694_FIRST_ORIGIN), ms.index(T694_LAST_ORIGIN)
        fc = expanding_h(S["S"], y, k0, k1, T694_H, T694_MIN_TRAIN)
        cw = cw_stats(fc["y"], fc["fb"], fc["fm"], T694_CW_LAG)
        fc_s = expanding_h(S["S"], y_spy, k0, k1, T694_H, T694_MIN_TRAIN)
        cw_s = cw_stats(fc_s["y"], fc_s["fb"], fc_s["fm"], T694_CW_LAG)
        return {"months": ms, "S": S, "y": y, "y_spy": y_spy, "k0": k0, "k1": k1, "fc": fc, "cw": cw, "fc_spy": fc_s, "cw_spy": cw_s}
    return CAL._cached(archive, ("b13va_t694_core",), load)


def hod_slope(S: np.ndarray, y: np.ndarray, g: np.ndarray, ks: np.ndarray, h: int = T694_H) -> dict:
    """Slope of y[k] on S[k] over origins ``ks`` with the Hodrick 1B t and one-sided p for a negative slope."""
    ks = np.asarray([k for k in ks if np.isfinite(S[k]) and np.isfinite(y[k])], int)
    if ks.size < 12:
        return {"n": int(ks.size), "slope": None, "t": None, "p": None, "se": None}
    X = np.column_stack([np.ones(ks.size), S[ks]])
    H = hodrick_ols(y[ks], X, ks, h, np.nan_to_num(g))
    t = float(H["t"][1])
    return {"n": int(ks.size), "slope": float(H["beta"][1]), "se": float(H["se"][1]), "t": t,
            "p": float(_N.cdf(t)) if math.isfinite(t) else None}


def _overlaps(months: Sequence[str], k: int, h: int, lo: str, hi: str) -> bool:
    a, b = months[k + 1] if k + 1 < len(months) else "9999", months[min(k + h, len(months) - 1)]
    return not (b < lo or a > hi)


def b13_volume_a_amihud_iwm(archive):
    """T-693."""
    miss = _missing(archive, [SPY_B, IWM_B, GSPC_B, FJA_B, SPELLS_B, DTB3_B, VIX_B]) or _prefix_missing(archive, [DH_PREFIX, DE_PREFIX])
    if miss:
        return miss
    C = t693_core(archive)
    ms, X = C["months"], C["X"]
    R = C["res"]
    fi = R["IWM"]["fc"]
    n = int(fi["k"].size)
    if n < 12:
        return _out({"n": n}, n, "inconclusive", f"only {n} out-of-sample months")
    c694 = t694_core(archive)
    ps = {"IWM": R["IWM"]["cw"]["p"], "SPY": R["SPY"]["cw"]["p"], "IWM-SPY": R["IWM-SPY"]["cw"]["p"],
          "T-694": c694["cw"]["p"], **T693_EXTERNAL}
    hp = MOM.holm_primary(ps, "IWM")
    cw = R["IWM"]["cw"]
    tg = C["targets"]["IWM"]
    ks = fi["k"]
    tm = [ms[k + 1] for k in ks]
    h1 = np.array([m < T693_SPLIT for m in tm])
    sl = []
    for msk in (h1, ~h1):
        sl.append(_ols1(X[ks[msk]], tg[ks[msk] + 1])[1] if msk.sum() > 5 else None)
    # timing rule: IWM when X_m is in the top tercile of its expanding real-time history, bills otherwise
    y = fi["y"]
    rule, pos = tercile_rule(X, ks, y, None)
    sw = np.abs(np.diff(np.r_[0.0, pos]))
    bh = y.copy()
    bh[0] -= T693_COST
    sd = stationary_sharpe_diff(rule, bh)
    holm_label = f"IWM Clark-West p < 0.05 after Holm over the 3 targets, T-694 and T-421 (raw p {_f(cw['p'], 4)}, CW t {_s(cw['cw_t'], 2)})"
    crit = [(f"IWM R2_OS {_pc(cw['r2'], 2)} > 0 over {n} OOS months", None if cw["r2"] is None else bool(cw["r2"] > 0), False),
            MOM.holm_row(hp, holm_label),
            (f"slope > 0 in both halves (target months 2005-2015 {_s(sl[0], 4)}, 2016-2026 {_s(sl[1], 4)})",
             None if None in sl else bool(all(s > 0 for s in sl)), False),
            (f"timing rule net Sharpe {_s(sd['sharpe_a'], 3)} beats buy-and-hold IWM {_s(sd['sharpe_b'], 3)} with "
             f"stationary-bootstrap (mean block {T693_MEAN_BLOCK:g}) p < 0.05 (diff {_s(sd['diff'], 3)}, p {_f(sd['p'], 4)})",
             bool(sd["diff"] > 0 and sd["p"] < ALPHA), False)]
    v, why, crit_j = CAL._judge(crit, n, T693_MIN_N, "out-of-sample months")
    # ---- reported
    vix = CAL._series(archive, VIX_B)
    days = vbase(archive)["days"]
    MB = months_base(archive)
    vix_prev = np.array([vix.get(days[MB["last"][k] - 1], np.nan) for k in ks], float)
    okv = np.isfinite(vix_prev)
    vreg = ols_nw_all(tg[ks[okv] + 1], np.column_stack([X[ks[okv]], vix_prev[okv]]), 6)
    ex = {}
    for nm, (lo, hi) in {"ex_2008_09": ("2008-01", "2009-12"), "ex_2020": ("2020-01", "2020-12")}.items():
        m = np.array([not (lo <= t <= hi) for t in tm])
        c2 = cw_stats(fi["y"][m], fi["fb"][m], fi["fm"][m], T693_CW_LAG)
        ex[nm] = {"r2": c2["r2"], "cw_t": c2["cw_t"], "slope": _ols1(X[ks[m]], tg[ks[m] + 1])[1]}
    full_slope = ols_nw_all(tg[ks + 1], X[ks], 6)
    # reported sensitivities (not judged): the 60-month trailing tercile, and the market-level scaling the other way
    # round (Acharya-Pedersen: x ^GSPC(m-1) / ^GSPC(first)); the registration's own formula is the judged one
    r60, p60 = tercile_rule(X, ks, y, 60)
    sd60 = stationary_sharpe_diff(r60, bh)
    fap = expanding_1step(C["signal"]["X_ap"], tg, C["k0"], C["k1"], T693_MIN_TRAIN)
    cap = cw_stats(fap["y"], fap["fb"], fap["fm"], T693_CW_LAG)
    t_mde = Z_MDE
    mde_r2 = t_mde ** 2 / (n + t_mde ** 2)
    sig = C["signal"]
    cnt = sig["counts"]
    kk0 = ms.index(T693_FIRST_MONTH)
    cn = cnt[kk0:]
    others = {nm: {"r2": R[nm]["cw"]["r2"], "cw_t": R[nm]["cw"]["cw_t"], "p": R[nm]["cw"]["p"]} for nm in ("SPY", "IWM-SPY")}
    stat = {"n": n, "first_target": tm[0], "last_target": tm[-1], "r2_os": cw["r2"], "cw_t": cw["cw_t"], "cw_p": cw["p"],
            "holm": hp, "family_p": ps, "other_targets": others, "half_slopes": sl, "timing": sd, "time_in_iwm": float(pos.mean()),
            "switches": int(sw.sum()), "vix_slope": vreg.get("coef"), "vix_t": vreg.get("t"), "exclusions": ex,
            "full_slope": full_slope.get("coef"), "full_slope_t": full_slope.get("t"), "mde_r2": mde_r2,
            "timing_trailing60": {"diff": sd60["diff"], "p": sd60["p"], "time_in_iwm": float(p60.mean())},
            "ap_scaling": {"r2": cap["r2"], "cw_t": cap["cw_t"], "n": cap["n"]},
            "members_used": {"min": int(cn[cn > 0].min()) if (cn > 0).any() else 0, "median": int(np.median(cn[cn > 0])) if (cn > 0).any() else 0,
                             "max": int(cn.max()), "1997-01": int(cnt[kk0]), "2005-01": int(cnt[ms.index("2005-01")]),
                             "2026-09": int(cnt[ms.index("2026-09")]) if "2026-09" in ms else None},
            "rho_last": float(sig["rho"][np.isfinite(sig["rho"])][-1]) if np.isfinite(sig["rho"]).any() else None,
            "members_monthly": {m: int(c) for m, c in zip(ms[kk0:], cn)},
            "criteria": crit_j, "verdict": v}
    reason = (f"Log aggregate Amihud ILLIQ of point-in-time S&P 500 members with prices (>= {T693_MIN_DAYS} valid days, raw "
              f"price > ${T693_MIN_PRICE:g}; {stat['members_used']['1997-01']} names in 1997-01, "
              f"{stat['members_used']['2005-01']} in 2005-01, {stat['members_used']['2026-09']} in 2026-09), ^GSPC-scaled, "
              f"expanding AR(1) expectation (last rho {_f(stat['rho_last'])}); next-month IWM excess return, target months "
              f"{tm[0]}..{tm[-1]} ({n}): R2_OS {_pc(cw['r2'], 2)}, CW t {_s(cw['cw_t'], 2)} (p {_f(cw['p'], 4)}; Holm "
              f"{_f(hp.get('adj'), 4) if hp.get('adj') is not None else 'bounded'} over 5); full-window slope "
              f"{_s((full_slope.get('coef') or [None, None])[1], 4)} (NW t {_s((full_slope.get('t') or [None, None])[1], 2)}); "
              f"halves {_s(sl[0], 4)} / {_s(sl[1], 4)}; SPY R2_OS {_pc(others['SPY']['r2'], 2)} (CW t {_s(others['SPY']['cw_t'], 2)}), "
              f"IWM-SPY {_pc(others['IWM-SPY']['r2'], 2)} (CW t {_s(others['IWM-SPY']['cw_t'], 2)}); top-tercile timing rule "
              f"(in IWM {pos.mean() * 100:.0f}% of months, {int(sw.sum())} switches) net Sharpe {_s(sd['sharpe_a'], 3)} vs "
              f"buy-and-hold {_s(sd['sharpe_b'], 3)} (p {_f(sd['p'], 4)}). Reported: VIX-controlled slope "
              f"{_s((vreg.get('coef') or [None, None])[1], 4)} (t {_s((vreg.get('t') or [None, None])[1], 2)}); excluding "
              f"2008-09 R2_OS {_pc(ex['ex_2008_09']['r2'], 2)}, excluding 2020 {_pc(ex['ex_2020']['r2'], 2)}; 60-month "
              f"trailing tercile rule (in IWM {p60.mean() * 100:.0f}% of months) Sharpe difference {_s(sd60['diff'], 3)} (p "
              f"{_f(sd60['p'], 4)}); market scaling the other way round (x ^GSPC(m-1) / ^GSPC(first), Acharya-Pedersen) "
              f"R2_OS {_pc(cap['r2'], 2)} (CW t {_s(cap['cw_t'], 2)}); MDE R2 "
              f"{_pc(mde_r2, 2)} at 80% power. Survivorship: members with prices from today's 901-symbol set, thin before "
              f"2008 (counts above)")
    return _out(stat, n, v, reason + " — " + why)


def t694_sec_check(archive, S: dict) -> dict:
    """Reported only: from 2010, the cross-sectional mean of log share turnover (monthly volume / acceptance-time SEC
    shares on the fetch-date split basis, unit-filtered) minus each name's own trailing mean over up to 60 previous
    months (>= 12), correlated with the volume-detrended signal."""
    B = vbase(archive)
    MB = months_base(archive)
    ms, fs, ls = MB["months"], MB["first"], MB["last"]
    sh, av = _cik_shares(archive, B)
    splits = all_splits(archive, list(B["syms"]) + sorted(B["class_close"]))
    k0 = ms.index(T694_SEC_FROM)
    V = B["volume"]
    N = V.shape[1]
    LT = np.full((len(ms), N), np.nan)
    for k in range(k0, len(ms)):
        f = int(ls[k])
        cols = np.flatnonzero(B["member"][f] | B["member"][max(0, f - 260)])
        adj = adjusted_shares(B, sh, av, splits, f, cols)
        adj, _ = unit_filter(adj, V, int(fs[k]) - 1, f)
        with np.errstate(invalid="ignore", divide="ignore"):
            LT[k] = np.log(np.exp(S["lv"][k]) / adj)
    agg = np.full(len(ms), np.nan)
    for k in range(k0 + 12, len(ms)):
        hist = LT[max(k0, k - 60):k]
        cnt = np.isfinite(hist).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mu = np.nanmean(hist, axis=0)
        m = B["member"][ls[k]] & np.isfinite(LT[k]) & (cnt >= 12)
        if m.sum() >= 30:
            agg[k] = float((LT[k][m] - mu[m]).mean())
    ok = np.isfinite(agg) & np.isfinite(S["S"])
    corr = float(np.corrcoef(agg[ok], S["S"][ok])[0, 1]) if ok.sum() > 12 else None
    return {"n": int(ok.sum()), "corr": corr, "first": ms[int(np.flatnonzero(ok)[0])] if ok.any() else None}


def b13_volume_a_turnover_ew12(archive):
    """T-694."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B, DTB3_B, SEC_TICK_B]) or \
        _prefix_missing(archive, [DH_PREFIX, DE_PREFIX, FACTS_PREFIX, SUBS_PREFIX])
    if miss:
        return miss
    C = t694_core(archive)
    S = C["S"]
    ms = C["months"]
    fc = C["fc"]
    n = int(fc["k"].size)
    if n < 12:
        return _out({"n": n}, n, "inconclusive", f"only {n} out-of-sample forecasts")
    ks_all = np.arange(C["k0"], C["k1"] + 1)
    hs = hod_slope(S["S"], C["y"], S["g"], ks_all)
    excl = {}
    for nm, (lo, hi) in {"ex_2008_09": ("2008-01", "2009-12"), "ex_2020": ("2020-01", "2020-12")}.items():
        kk = np.array([k for k in ks_all if not _overlaps(ms, k, T694_H, lo, hi)], int)
        excl[nm] = hod_slope(S["S"], C["y"], S["g"], kk)
    c693 = t693_core(archive)
    ps = {"T-694": C["cw"]["p"], "T-693": c693["res"]["IWM"]["cw"]["p"], **T694_EXTERNAL}
    hp = MOM.holm_primary(ps, "T-694")
    cw = C["cw"]
    crit = [(f"slope {_s(hs['slope'], 4)} < 0 with Hodrick 1B p < 0.05 (t {_s(hs['t'], 2)}, p {_f(hs['p'], 4)}, {hs['n']} "
             f"overlapping origins)", None if hs["t"] is None else bool(hs["slope"] < 0 and hs["p"] < ALPHA),
             hs["t"] is not None and hs["t"] > 1.645),
            (f"R2_OS {_pc(cw['r2'], 2)} > 0 over {n} OOS forecasts", None if cw["r2"] is None else bool(cw["r2"] > 0), False),
            MOM.holm_row(hp, f"Clark-West p < 0.05 after family Holm with T-693, T-398, T-449, T-458 (raw p {_f(cw['p'], 4)}, "
                             f"CW t {_s(cw['cw_t'], 2)})"),
            (f"same sign excluding 2008-09 ({_s(excl['ex_2008_09']['slope'], 4)}, t {_s(excl['ex_2008_09']['t'], 2)}) and "
             f"excluding 2020 ({_s(excl['ex_2020']['slope'], 4)}, t {_s(excl['ex_2020']['t'], 2)})",
             None if None in (excl["ex_2008_09"]["slope"], excl["ex_2020"]["slope"])
             else bool(excl["ex_2008_09"]["slope"] < 0 and excl["ex_2020"]["slope"] < 0), False)]
    v, why, crit_j = CAL._judge(crit, n, T694_MIN_N, "out-of-sample forecasts")
    # ---- reported
    annual = {}
    for mo in range(1, 13):
        kk = np.array([k for k in ks_all if int(ms[k][5:7]) == mo and np.isfinite(S["S"][k]) and np.isfinite(C["y"][k])], int)
        if kk.size >= 6:
            r = ols_nw_all(C["y"][kk], S["S"][kk], 0)
            annual[f"{mo:02d}"] = {"n": int(kk.size), "slope": r["coef"][1] if r["coef"] else None, "t": r["t"][1] if r["t"] else None}
    n_neg = sum(1 for a in annual.values() if a["slope"] is not None and a["slope"] < 0)
    hs_spy = hod_slope(S["S"], C["y_spy"], S["g_spy"], ks_all)
    # risk-off rule (reported): bills when S_m is in its expanding top decile, else the EW portfolio; monthly
    ew_x = S["ew"] - S["rf"]
    kr = [k for k in range(C["k0"], len(ms) - 1) if np.isfinite(S["S"][k]) and np.isfinite(ew_x[k + 1]) and ms[k + 1] <= T693_LAST_TARGET]
    pos = []
    for k in kr:
        h = S["S"][:k + 1]
        h = h[np.isfinite(h)]
        pos.append(0.0 if S["S"][k] >= np.quantile(h, 0.9) else 1.0)
    pos = np.array(pos)
    yx = np.array([ew_x[k + 1] for k in kr])
    rule = pos * yx - T694_COST * np.abs(np.diff(np.r_[1.0, pos]))
    sr_rule, sr_bh = float(sharpe_ratio(rule, 12)), float(sharpe_ratio(yx, 12))
    sec = CAL._cached(archive, ("b13va_t694_sec",), lambda: t694_sec_check(archive, S))
    mde = Z_MDE * hs["se"] if hs.get("se") else None
    nS = S["nS"][C["k0"]:C["k1"] + 1]
    stat = {"n": n, "first_origin": ms[int(fc["k"][0])], "last_origin": ms[int(fc["k"][-1])], "hodrick": hs, "r2_os": cw["r2"],
            "cw_t": cw["cw_t"], "cw_p": cw["p"], "holm": hp, "family_p": ps, "T-458_raw_cw_p": 0.0474, "exclusions": excl,
            "annual_by_start_month": annual, "annual_negative": n_neg, "spy": {"hodrick": hs_spy, "r2_os": C["cw_spy"]["r2"],
            "cw_t": C["cw_spy"]["cw_t"]}, "risk_off": {"sharpe_rule": sr_rule, "sharpe_ew": sr_bh, "months_in_bills": int((pos == 0).sum()),
            "n": int(pos.size)}, "sec_turnover_check": sec, "mde_slope": mde,
            "signal_names": {"min": int(nS.min()), "median": int(np.median(nS)), "max": int(nS.max())},
            "criteria": crit_j, "verdict": v}
    reason = (f"Detrended aggregate turnover (mean over priced point-in-time S&P 500 members with 60 months of own volume "
              f"history of log monthly volume minus its trailing 60-month mean; {stat['signal_names']['min']}-"
              f"{stat['signal_names']['max']} names) against the next 12 months' log excess return of the members' "
              f"equal-weighted portfolio, origins {stat['first_origin']}..{stat['last_origin']} ({n} OOS forecasts): slope "
              f"{_s(hs['slope'], 4)} (Hodrick 1B t {_s(hs['t'], 2)}, p {_f(hs['p'], 4)}; MDE {_f(mde, 4) if mde else 'n/a'} at "
              f"80% power); R2_OS {_pc(cw['r2'], 2)} (CW t {_s(cw['cw_t'], 2)}, p {_f(cw['p'], 4)}; family Holm "
              f"{_f(hp.get('adj'), 4) if hp.get('adj') is not None else 'bounded'}); excluding 2008-09 {_s(excl['ex_2008_09']['slope'], 4)}, "
              f"excluding 2020 {_s(excl['ex_2020']['slope'], 4)}. Reported: non-overlapping annual fits by start month "
              f"{n_neg} of {len(annual)} negative; SPY 12-month excess slope {_s(hs_spy['slope'], 4)} (t {_s(hs_spy['t'], 2)}), "
              f"R2_OS {_pc(C['cw_spy']['r2'], 2)}; risk-off rule (bills in the expanding top decile, 5 bp per switch) "
              f"Sharpe {_s(sr_rule, 3)} vs the EW portfolio {_s(sr_bh, 3)}; correlation with SEC-shares turnover from "
              f"{sec.get('first')} {_s(sec.get('corr'), 3)} ({sec.get('n')} months). Survivorship: members with prices from "
              f"today's 901-symbol set (thin before 2008); about 21 independent annual observations, so power is low")
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {
    "b13_volume_a_stmom": b13_volume_a_stmom,
    "b13_volume_a_return_volume": b13_volume_a_return_volume,
    "b13_volume_a_visibility": b13_volume_a_visibility,
    "b13_volume_a_amihud_iwm": b13_volume_a_amihud_iwm,
    "b13_volume_a_turnover_ew12": b13_volume_a_turnover_ew12,
}
THEORY_MAP = {
    "T-691": "b13_volume_a_stmom",
    "T-698": "b13_volume_a_return_volume",
    "T-692": "b13_volume_a_visibility",
    "T-693": "b13_volume_a_amihud_iwm",
    "T-694": "b13_volume_a_turnover_ew12",
}
