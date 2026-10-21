"""
Batch 13, group ``volume_b``: five volume claims pre-registered from the 2026-10-20 web sweep (cluster "volume"):
share-volume variability in value-weighted S&P 500 quintiles (T-695), volume-confirmed 52-week highs (T-697), SPY
intraday momentum conditioned on first-hour relative volume (T-699), same-slot intraday return continuation on the
local hourly bars (T-700) and the low-activity-loser reversal on the point-in-time Coinbase top 50 (T-702).
=====================================================================================================================

  * T-695  Point-in-time S&P 500 members with a Yahoo price and SEC shares, holding months 2010-01..2026-09. CV of the
           monthly split-adjusted share volume over the 36 months ending at the formation month-end (>= 24 valid
           months); value-weighted quintiles formed at the month-end, long lowest CV / short highest CV, filled at the
           next session's close and held to the next fill; 10 bp per side on traded weight, 1%/yr borrow on the short
           leg. Pass: >= 180 months, VW net mean > 0 with one-sided Newey-West (6) p < 0.05, both halves
           (2010-2017 / 2018-2026) positive, FF5+UMD alpha > 0, spread positive in >= 2 of 3 sequential volume-level
           terciles (36-month mean share volume).
  * T-697  Point-in-time S&P 500 members with prices, events 2005-01..2026-09: a split-adjusted close above the max of
           the previous 252 closes with no such crossing in the previous 60 sessions. AV = event-day volume / median
           volume of the previous 50 sessions; confirmed = AV above the 2/3 quantile of AV over all earlier events
           (unconfirmed = below the 1/3 quantile). 20-session beta-adjusted return (trailing 252-session beta vs SPY)
           from the next open, net of 10 bp. Pass: >= 500 confirmed events, confirmed mean net > 0 with a date-clustered
           95% lower bound > 0, confirmed minus unconfirmed >= 50 bp with lower bound > 0, matched placebo (same name,
           trailing 60-day vol and distance to the 252-day high within 0.25 sd, 2,000 draws) p < 0.05, both halves
           (2005-2015 / 2016-2026) positive, DSR >= 0.95 counting T-309's 8 and T-304's 60 trials plus this one (69).
  * T-699  SPY on archived 1h bars (hourly-SPY, bar-start stamps), 2023-11-15..2026-10, QQQ and IWM as replications:
           from the 15:30 bar's open to the official close in the sign of (15:30 open / previous official close - 1),
           2 bp round trip. RVOL = the 09:30 bar's volume / median of the same bar over the previous 20 sessions;
           high-RVOL sessions: RVOL above the 67th percentile of RVOL over the previous 60 sessions (low: below the
           33rd). Pass: >= 200 high-RVOL SPY sessions, high-RVOL mean net > 0 with one-sided weekly-block bootstrap p
           < 0.05, high minus low > 0 with p < 0.05, within-week random-tercile placebo p < 0.05, the same sign on QQQ
           and IWM, deflated p < 0.05 counting T-427's 60 cells (61 trials).
  * T-700  US single stocks and unlevered US equity ETFs in the local 60-minute bars (mandel/ml_data/bars/60m),
           2023-11..2026-10: per slot-day cross-sectional regressions of the slot-h return on day d on the name's mean
           slot-h return over the previous 20 sessions and on the mean of its other six slots over the same days.
           Pass: >= 450 trading days, mean same-slot minus other-slot slope > 0 with Newey-West t > 2 in each half
           (2023-11..2025-04 / 2025-05..2026-10). The top-minus-bottom quintile slot portfolio is reported net of 2 bp
           per side (ETFs) and 5 bp (stocks).
  * T-702  Point-in-time top 50 Coinbase USD products by trailing 30-day dollar volume (T-546's exclusions: stablecoins,
           wrapped / staked bases, BTC and ETH), entries 2019-01..2026-09: signals from the daily bars through
           Saturday's UTC bar, entry at the close of Sunday's bar, 7-day hold. Low-activity losers = bottom quintile of
           the prior-week return within the bottom tercile of prior-week volume relative to its trailing 30-day mean;
           equal-weighted, against the equal-weighted universe, 50 bp round trip on traded weight. Pass: >= 300 weeks,
           long-only excess net > 0 with a studentized CBB (8-week blocks) 95% lower bound > 0, both halves (split
           2022-11-17) positive, low-activity minus high-activity loser-minus-winner spread > 0 with one-sided p < 0.05,
           holds at the 100 bp stress, DSR >= 0.95 counting T-314's 24 and T-546's 1 trial plus this one (26).

Readings fixed before any run (the registrations are silent or ambiguous; each is the conservative one or is judged
under every permitted reading, rule 11):
  * Universe (T-695, T-697). ``batch13_volume_a.vbase``, the point-in-time S&P 500 panel shared with the volume
    cluster: fja05680 snapshots plus Wikipedia changes after fja's last date, Yahoo EQUITY series only, T-473's
    per-spell removed-name check and volume_a's size identity check (a member-day whose trailing 60-session median
    dollar volume is under 1/40 of the day's member median is another company's series), the ^GSPC session calendar.
    Prices are TODAY's 901-symbol daily-history set (``panel_cache``): delisted and acquired members are
    under-represented, which every reason states. Yahoo volume is split-adjusted to the fetch date (share volume).
  * T-695. The registration's "months t-36..t-1" is read with t = the holding month: the 36 calendar months ending at
    the formation month-end (the claim's "prior 36 months"). A valid month has a finite volume on every session of
    the month and a positive sum; CV = sample sd (ddof 1) / mean over the valid months, >= 24 required. Eligible = a
    member at the formation close with a bar there, a CV and a usable cap: SEC cover shares available by 16:00 ET of
    the formation day (acceptance time), no older than 456 days, split to Yahoo's fetch-date basis, T-393's
    share-class rule, and volume_a's XBRL unit filter (a count implying formation-month turnover outside
    [0.2%, 2,000%] is refused); members without a usable cap are excluded before the sort and their share is
    reported. Quintile breakpoints over the eligible names (long CV < 20th percentile, short > 80th); VW by the
    formation-close cap. Costs 10 bp x |w_new - drifted w_old| over both legs (first entry and final exit charged),
    borrow 1%/yr x the hold's calendar days / 365 (``batch13_volume_a.book``). FF5+UMD compounded over each hold,
    holds ending by the factor files' last day, Newey-West (6). Sequential sorts: terciles of the 36-month mean
    monthly share volume (respectively of the formation cap) among eligible names, CV quintiles within each, the same
    VW book and costs; "spread positive" = net mean > 0. Equal-weighted cell and cap terciles reported only. OSAP's
    long-short file is not archived: the decay row is not computed.
  * T-697. Highs on the split-adjusted close (Yahoo ``close``, not dividend-adjusted); the previous 252 and the
    previous 60 crossings require complete windows (312 consecutive bars). An event needs membership on the event day,
    a positive event-day volume (a zero-volume bar is a stale print) and 50 positive previous volumes. Breakpoints:
    AV of all events on strictly earlier days from 2005-01-01 (no same-day events), quantiles by linear interpolation;
    events start being classified once 100 earlier events exist (burn-in). Entry = the next session's open, exit = the
    open 20 sessions later (the last open at or before it for a series that stops trading), opens put on the adjclose
    basis by the same day's adjclose / close ratio (dividends); an event whose exit is past the data is dropped.
    Beta = OLS slope of daily adjclose returns on SPY's over the 252 sessions ending at the event day (>= 200 pairs);
    "beta-adjusted" = W - beta x SPY (the registration lists no bill series). Date clusters = the event day;
    difference bootstrap on the linearised contrast series (``batch6c_cal.flag_diff_series``) with the same date
    clusters (studentized, ``batch6c_pub.cluster_stud``). Placebo pool: the name's member-days in the window with both
    matching variables and a 20-session net return (its event day excluded); 0.25 sd = a quarter of each variable's sd
    over the pooled pool of all names; trailing 60-day vol = sd of the 60 daily returns ending on the day, distance =
    close / previous-252 max - 1; an event with no matched day leaves the placebo (counted); p = (1 + #{placebo mean
    >= observed}) / 2,001. DSR on the daily calendar-time portfolio of confirmed events (5 bp on the first and on the
    last interval), at 69 trials and the most favourable 1/(T-1) trial-Sharpe variance: T-309's and T-304's Sharpes
    are not on this series, so the criterion can fail here but cannot pass (``dsr_bound``). Lows (survivorship),
    5- / 60-session horizons, the top-decile AV cut, the |event-day return| > 3 trailing sigma news proxy and the
    coverage audit are reported only; the T-578 AV x distance interaction cell is not computed.
  * T-699. The archived ``hourly-SPY/QQQ/IWM`` bundles are the "archived 60-minute bars" (bar-start stamps, New York
    time via zoneinfo; the zero-volume 16:00 print bar is never a slot). Official open / close from daily-history; the
    previous close is put on day t's dividend basis as in T-427. Sessions: every daily session inside the hourly span
    and 2023-11-15..2026-10-31, minus early closes and sessions without the 09:30 or 15:30 bar (counted). RVOL's
    median uses the 20 most recent earlier sessions with a positive 09:30-bar volume (early-close mornings included,
    the bar exists); the percentile uses the 60 most recent earlier RVOL values (np.percentile, linear); high = RVOL >
    p67, low = RVOL < p33. A session with r = 0 does not trade. Weekly block bootstrap = studentized CBB with 5-session
    blocks on the session series (``flag_diff_series`` / ``contrast_series`` make the means the high mean and the
    high-minus-low difference). Placebo: tercile labels permuted within ISO weeks among the classified sessions, 2,000
    draws, judged on BOTH the high mean and the high-minus-low difference. "Same sign on QQQ and IWM": each one's own
    RVOL classes give a high mean > 0 and high minus low > 0. Deflated p = 1 - DSR at 61 trials (T-427's 60 cells plus
    this one) and the 1/(T-1) floor; T-427's 60 cells were never computed, so the criterion can fail here but cannot
    pass. The 2016-2023 minute-bar replication (required before any forward paper) is not available here.
  * T-700. Names: ``mandel.ml.fetch`` STOCKS (28) and EQUITY_ETF minus TQQQ / SQQQ (levered or inverse) and the crypto
    ETFs IBIT / ETHA, those with a local 60m file. Slots 09:30, 10:30, ..., 15:30 (bar-start, New York time); a
    name-day counts only with all seven bars; slot returns partition the open-to-close return: slot 1 = close / open
    of the 09:30 bar (no overnight), slot h = close_h / close_{h-1}. The calendar is SPY's full days; the 20-day
    lookbacks use the previous 20 calendar sessions, all present for the name. A regression needs >= 20 names.
    "Slope" is read two ways (rule 11): separate univariate regressions on the same-slot and the other-slot means, and
    one joint regression on both; Newey-West t two ways: on the slot-day series (lag floor(4 (n/100)^(2/9))) and on
    the daily means of the slot-day differences (the same rule on days). Each half's criterion passes only when every
    reading and both t's pass. Slot portfolio: top / bottom quintile of the same-slot mean, equal weight, a round trip
    per leg per slot.
  * T-702. Membership = ``batch6c_cryptovenue.cb_members`` on the entry day D (dollar volume summed over D-30..D-1,
    traded on D-1 = Saturday; dead products included), T-546's exclusion set (BTC and ETH out, as the claim's
    "T-546's exclusions"; the variant with both kept is reported). Prior-week return = last close at or before
    Saturday / the same a week earlier. "Volume" is read two ways (rule 11): base-currency volume and dollar volume;
    relative volume = mean daily volume of the 7 days to Saturday / mean of the 30 days to Saturday (days without
    trades count 0; the product must have traded 30 days before Saturday; the tercile order is the same as against the
    23 days before the week). Entry needs a traded Sunday bar; exit = the last close at or before the next Sunday.
    Terciles / quintiles by np.quantile with strict inequalities. Costs 25 bp per side x traded weight (drifted
    weights, first entry and final exit charged); the universe benchmark is uncosted. Spread difference judged gross
    and net of the same costs on every leg. "Holds at the 100 bp stress" = the long-only criterion (mean > 0 with the
    CBB lower bound > 0) at 50 bp per side. DSR at 26 trials and the 1/(T-1) floor; T-546's trial has no Sharpe on
    this series (T-314's 24 recorded weekly Sharpes are used in the reported family DSR), so the criterion can fail
    here but cannot pass. Rule 10: the registered phase is Sunday entry; the six other entry weekdays are reported.
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``, house rule 5). House rule 10: T-695 forms at month-ends and T-702 on Sundays, both named
    by the claims (T-702 reports every other weekday phase); T-697 is event-driven; T-699 and T-700 use every session.
"""

from __future__ import annotations

import bisect
import gc
import math
import warnings
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch13_volume_a as VA
from mandel.experiments import batch5_hourly as H5
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_cryptovenue as CV
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

SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
FJA_B = "fja-sp500-components"
SPELLS_B = "fja-sp500-ticker-spells"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
SEC_TICK_B = "sec-company-tickers"
DH_PREFIX = "daily-history-"
DE_PREFIX = "daily-events-"
FACTS_PREFIX = "sec-companyfacts-"
SUBS_PREFIX = "sec-submissions-"
FOMC_B = "fomc-meetings"
CPI_B = "macro-release-cpi"

# T-695
T695_FIRST, T695_LAST = "2010-01", "2026-09"
T695_SPLIT = "2018-01"
T695_WIN, T695_MIN_MONTHS = 36, 24
T695_Q = 0.2
T695_COST, T695_BORROW = 10e-4, 0.01
T695_NW_LAG = 6
T695_MIN_N = 180
T695_MIN_SORT = 10

# T-697
T697_START, T697_END = "2005-01-01", "2026-09-30"
T697_SPLIT = "2016-01-01"
T697_ROW0 = "2002-01-01"            # computation start: 252 + 60 sessions of warm-up before the first 2005 event
T697_HIGH_WIN = 252
T697_GAP = 60
T697_AV_WIN = 50
T697_HOLD = 20
T697_HOLDS_REP = (5, 60)
T697_BETA_WIN, T697_BETA_MIN = 252, 200
T697_VOL_WIN = 60
T697_NEWS_SIG = 3.0
T697_COST = 10e-4
T697_BAR = 50e-4
T697_BAND = 0.25
T697_N_PLACEBO = 2000
T697_BURN = 100
T697_TRIALS = 69                     # T-309's 8 + T-304's 60 + this one
T697_MIN_N = 500

# T-699
T699_START, T699_END = "2023-11-15", "2026-10-31"
T699_SYMS = ("SPY", "QQQ", "IWM")
T699_MED_WIN = 20
T699_PCT_WIN = 60
T699_HI, T699_LO = 67.0, 33.0
T699_COST = 2e-4
T699_BLOCK = 5
T699_N_PLACEBO = 2000
T699_TRIALS = 61                     # T-427's 60 cells + this one
T699_MIN_N = 200
T699_T428_SLOPE = -0.084

# T-700
T700_SLOTS = ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")
T700_LOOK = 20
T700_MIN_NAMES = 20
T700_SPLIT = "2025-05-01"
T700_T = 2.0
T700_COST_ETF, T700_COST_STOCK = 2e-4, 5e-4
T700_MIN_N = 450
T700_EXCLUDE_ETF = ("TQQQ", "SQQQ", "IBIT", "ETHA")

# T-702
T702_FIRST, T702_LAST = "2019-01-01", "2026-09-30"
T702_PANEL0 = "2018-10-01"
T702_SPLIT = "2022-11-17"
T702_TOP = 50
T702_RANK_DAYS = 30
T702_WEEK = 7
T702_RV_DAYS = 30
T702_COST_SIDE = 0.0025              # 50 bp round trip
T702_STRESS_SIDE = 0.005             # 100 bp round trip
T702_BLOCK = 8
T702_TRIALS = 26                     # T-314's 24 + T-546's 1 + this one
T702_MIN_N = 300
T702_PHASE = 6                       # entry weekday: Sunday (Monday = 0)
T702_EXCLUDE = CV.T424_STABLE | CV.T424_WRAPPED | frozenset({"BTC", "ETH"})
T702_EXCLUDE_INCL = (CV.T424_STABLE | CV.T424_WRAPPED) - frozenset({"BTC", "ETH"})
# T-314's 24 recorded weekly per-period trial Sharpes (experiment X-814a53e0), for the reported family DSR only
T314_SHARPES = (-0.11019906753325075, -0.09555804958004914, -0.12658732892934577, -0.10734593312090948,
                -0.06998733656283089, -0.11244199628406024, -0.09520903950856335, -0.06276295773329361,
                -0.08458054865505193, -0.09484263600288113, -0.037721343531495415, -0.10126474338007299,
                -0.07469931844153718, -0.06692865316149497, -0.08845622705671065, -0.07016775308211531,
                -0.0455589499495859, -0.0815788338642266, -0.09959198008346432, -0.0690419950796913,
                -0.07419575038540589, -0.07650093644763115, -0.031207137114450764, -0.09528306248812951)

_f, _s, _pc, _bp = VA._f, VA._s, VA._pc, VA._bp


# ================================================================================================= utilities ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, list(names))


def _prefix_missing(archive, prefixes: Sequence[str]):
    return VA._prefix_missing(archive, prefixes)


def _nw_lag(n: int) -> int:
    return max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def dsr_bound(x, n_trials: int, label: str, family_note: str, strict: bool = False) -> tuple:
    """DSR criterion when the family's other trial Sharpes are not computed on this series: the most favourable
    trial-Sharpe variance (the 1/(T-1) floor) bounds the DSR from above. Fails when that bound misses the bar (>= 0.95;
    > 0.95 when ``strict``), decisively when the PSR against a zero Sharpe is <= 0.05; undecided otherwise (the
    uncomputed family Sharpes could only lower it)."""
    x = np.asarray(x, float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_bound": hi, "n_trials": n_trials, "var_floor": floor, "psr0": psr0, "sharpe_pp": float(sharpe_ratio(x)),
            "n_obs": int(x.size)}
    txt = f"{label} (at most {hi:.3f} at {n_trials} trials and the 1/(T-1) floor; PSR vs 0 {psr0:.3f})"
    miss = hi <= DSR_PASS if strict else hi < DSR_PASS
    if miss:
        return (txt + " [fails whatever the uncomputed family Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + f" [{family_note}: cannot pass here]", None, False), info


def cboot(x, labels, thr: float = 0.0) -> dict:
    """Cluster studentized bootstrap of a mean (``batch6c_pub.cluster_stud``) over REPS seeds, escalated when the
    two-sided 95% lower end cannot be resolved against ``thr``."""
    x = np.asarray(x, float)
    if x.size < 4:
        return {"est": float(x.mean()) if x.size else None, "ci": [None, None], "clusters": 0, "n": int(x.size)}
    labs = [str(v) for v in labels]

    def chk(t):
        ci, se = t.get("ci") or [None], t.get("ci_mc_se") or [0.0]
        return BW.resolve(ci[0], se[0], thr, "gt")[0]
    return BW.mc_escalate(lambda seed: cluster_stud(x, labs, None, seed), chk, None, SEED, keys=("ci", "ci90", "ci_pct"))


def _ci_txt(t: dict, fmt=None) -> str:
    fmt = fmt or (lambda v: _bp(v))
    lo, hi = (t.get("ci") or [None, None])[:2]
    return f"{fmt(lo)}..{fmt(hi)}"


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _p_crit(name: str, p: Optional[float], n_draw: int) -> tuple:
    """'placebo p < 0.05' resolved against its Monte Carlo error."""
    if p is None:
        return f"{name} (n/a)", None, False
    se = math.sqrt(max(p * (1 - p), 0.0) / max(n_draw, 1))
    ok, note = BW.resolve(p, se, ALPHA, "lt")
    return f"{name} (p {p:.4f}){note}", ok, False


def q_legs(score, el, lo: float = T695_Q, hi: float = 1 - T695_Q, min_n: int = 1) -> tuple:
    """(low mask, high mask): eligible names strictly below the ``lo`` quantile and strictly above the ``hi`` quantile
    of ``score`` over the eligible names (np.quantile, linear)."""
    el = np.asarray(el, bool) & np.isfinite(score)
    z = np.zeros(el.shape, bool)
    if el.sum() < max(min_n, 2):
        return z, z.copy()
    a, b = np.quantile(score[el], [lo, hi])
    with np.errstate(invalid="ignore"):
        return el & (score < a), el & (score > b)


def terciles(score, el) -> list:
    """[bottom, middle, top] tercile masks of ``score`` over the eligible names (strict outer cuts)."""
    el = np.asarray(el, bool) & np.isfinite(score)
    if el.sum() < 3:
        z = np.zeros(el.shape, bool)
        return [z, z.copy(), z.copy()]
    a, b = np.quantile(score[el], [1 / 3, 2 / 3])
    with np.errstate(invalid="ignore"):
        lo, hi = el & (score < a), el & (score > b)
    return [lo, el & ~lo & ~hi, hi]


# ====================================================================================================== T-695 ==

def month_index(days: Sequence[str]) -> tuple:
    """(months, first session row, last session row) of each calendar month of the session calendar."""
    months, s0 = [], []
    for i, d in enumerate(days):
        if not months or months[-1] != d[:7]:
            months.append(d[:7])
            s0.append(i)
    s0 = np.array(s0, int)
    s1 = np.append(s0[1:] - 1, len(days) - 1)
    return months, s0, s1


def monthly_volume(V: np.ndarray, s0: np.ndarray, s1: np.ndarray) -> tuple:
    """(MV, valid) month x name: the month's summed (split-adjusted) share volume, valid when every session of the
    month has a finite volume and the sum is positive (NaN otherwise)."""
    fin = np.isfinite(V)
    MV = np.add.reduceat(np.where(fin, V, 0.0), s0, axis=0)
    cnt = np.add.reduceat(fin.astype(np.int64), s0, axis=0)
    valid = (cnt == (s1 - s0 + 1)[:, None]) & (MV > 0)
    return np.where(valid, MV, np.nan), valid


def volume_cv(MV: np.ndarray, valid: np.ndarray, k: int, win: int = T695_WIN, min_months: int = T695_MIN_MONTHS) -> tuple:
    """(CV, mean) of each name's valid monthly volumes over months k-win+1..k (the ``win`` months ending at month k),
    NaN with fewer than ``min_months`` valid months. Uses no month after k."""
    N = MV.shape[1]
    lo = k - win + 1
    if lo < 0:
        return np.full(N, np.nan), np.full(N, np.nan)
    X = MV[lo:k + 1]
    cnt = valid[lo:k + 1].sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(X, axis=0)
        sd = np.nanstd(X, axis=0, ddof=1)
    ok = cnt >= min_months
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(ok, sd / m, np.nan), np.where(ok, m, np.nan)


def t695_inputs(archive) -> dict:
    """Formation rows for holding months 2010-01..2026-09: formation at month-end t = H - 1, fill at the next session's
    close, held to the next fill. Per row: CV and 36-month mean volume, cap, eligibility, hold returns, coverage."""
    def load():
        B = VA.vbase(archive)
        days = B["days"]
        A, C, V = B["adjclose"], B["close"], B["volume"]
        N = len(B["syms"])
        months, s0, s1 = month_index(days)
        mpos = {m: k for k, m in enumerate(months)}
        MV, valid = monthly_volume(V, s0, s1)
        sh, av = VA._cik_shares(archive, B)
        splits = VA.all_splits(archive, list(B["syms"]) + sorted(B["class_close"]))
        real = np.isfinite(A) & np.isfinite(C)
        Aff = VA._ffill(A)
        lastbar = np.where(real.any(axis=0), len(days) - 1 - real[::-1].argmax(axis=0), -1)
        rows = []
        for H in VA.mrange(T695_FIRST, T695_LAST):
            t, tp = VA.madd(H, -1), VA.madd(H, -2)
            if t not in mpos or tp not in mpos or H not in mpos:
                continue
            k = mpos[t]
            f, e_prev, e_h = int(s1[k]), int(s1[mpos[tp]]), int(s1[mpos[H]])
            entry, exit_ = f + 1, e_h + 1
            if exit_ >= len(days):
                continue
            mem = B["member"][f]
            okp = mem & real[f]
            adj = VA.adjusted_shares(B, sh, av, splits, f, np.flatnonzero(okp))
            adj, n_unit = VA.unit_filter(adj, V, e_prev, f)
            with np.errstate(invalid="ignore"):
                cap = C[f] * adj
            cv, mv = volume_cv(MV, valid, k)
            capok = np.isfinite(cap) & (cap > 0)
            el = okp & np.isfinite(cv) & capok
            with np.errstate(invalid="ignore", divide="ignore"):
                xe = np.minimum(exit_, lastbar)
                hr = np.where(real[entry] & (lastbar >= entry), Aff[np.maximum(xe, 0), np.arange(N)] / A[entry] - 1.0, 0.0)
            rows.append({"H": H, "f": f, "entry": entry, "exit": exit_, "cv": np.where(el, cv, np.nan),
                         "mv": np.where(el, mv, np.nan), "cap": np.where(el, cap, np.nan), "el": el,
                         "hr": np.where(el, np.nan_to_num(hr, nan=0.0), 0.0),
                         "n_members": int(B["n_members"][f]), "n_priced": int(okp.sum()), "n_cap": int((okp & capok).sum()),
                         "n_cv": int((okp & np.isfinite(cv)).sum()), "n_el": int(el.sum()), "n_unit": n_unit,
                         "days_held": (date.fromisoformat(days[exit_]) - date.fromisoformat(days[entry])).days})
        return {"rows": rows, "days": days, "info": B["info"]}
    return CAL._cached(archive, ("b13vb_t695",), load)


def t695_book(rows: list, weight: str = "vw", sub=None, cost: float = T695_COST, borrow: float = T695_BORROW) -> dict:
    """Long lowest-CV quintile, short highest-CV quintile among the eligible names (or the subset ``sub(row)``), value-
    (``vw``) or equal- (``ew``) weighted; ``batch13_volume_a.book`` charges costs and borrow."""
    M = len(rows)
    if not M:
        return {"net": np.zeros(0), "elig": np.zeros(0, bool), "months": []}
    N = rows[0]["cv"].size
    WL, WS = np.zeros((M, N)), np.zeros((M, N))
    elig = np.zeros(M, bool)
    for k, r in enumerate(rows):
        el = r["el"] if sub is None else sub(r)
        if el.sum() < T695_MIN_SORT:
            continue
        lm, sm = q_legs(r["cv"], el)
        if not lm.any() or not sm.any():
            continue
        if weight == "vw":
            WL[k], WS[k] = VA.vw_weights(lm, r["cap"]), VA.vw_weights(sm, r["cap"])
        else:
            WL[k], WS[k] = lm / lm.sum(), sm / sm.sum()
        elig[k] = WL[k].sum() > 0 and WS[k].sum() > 0
    HR = np.vstack([r["hr"] for r in rows])
    bk = VA.book(WL, WS, HR, elig, [r["days_held"] for r in rows], cost, borrow)
    bk["elig"] = elig
    bk["months"] = [r["H"] for r in rows]
    return bk


def _tercile_sub(key: str, j: int):
    return lambda r: terciles(r[key], r["el"])[j]


def b13_volume_b_volume_cv(archive):
    """T-695."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B, FF5_B, MOM_B, SEC_TICK_B]) or \
        _prefix_missing(archive, [DH_PREFIX, DE_PREFIX, FACTS_PREFIX, SUBS_PREFIX])
    if miss:
        return miss
    I = t695_inputs(archive)
    rows, days = I["rows"], I["days"]
    P = t695_book(rows, "vw")
    el = P["elig"]
    months = [m for m, e in zip(P["months"], el) if e]
    net = P["net"][el]
    n = int(net.size)
    if n < 8:
        return _out({"n": n, "n_formed": len(rows)}, n, "inconclusive", f"only {n} formation months could be formed")
    mean = float(net.mean())
    nw = hac_mean(net, T695_NW_LAG)
    mo = np.array(months)
    h1, h2 = net[mo < T695_SPLIT], net[mo >= T695_SPLIT]
    halves = [_mean(h1), _mean(h2)]
    rows_el = [r for r, e in zip(rows, el) if e]
    F, fok, fend = VA.factor_holds(archive, days, [(r["entry"], r["exit"]) for r in rows_el])
    reg = VA.ols_nw_all(net[fok], F[fok], T695_NW_LAG) if fok.sum() > 12 else {"coef": None, "t": None}
    alpha = reg["coef"][0] if reg.get("coef") else None
    alpha_t = reg["t"][0] if reg.get("t") else None
    vol_t = {}
    for j, nm in enumerate(("low", "mid", "high")):
        b = t695_book(rows, "vw", _tercile_sub("mv", j))
        x = b["net"][b["elig"]]
        vol_t[nm] = {"net_mean": _mean(x), "n": int(x.size), "nw_t": hac_mean(x, T695_NW_LAG)["t"] if x.size > 3 else None,
                     "gross_mean": _mean(b["gross"][b["elig"]])}
    n_pos = sum(1 for v in vol_t.values() if v["net_mean"] is not None and v["net_mean"] > 0)
    n_def = sum(1 for v in vol_t.values() if v["net_mean"] is not None)
    nw_ok = None if nw.get("p") is None else bool(mean > 0 and nw["p"] < ALPHA)
    crit = [(f"value-weighted net mean {_pc(mean, 3)}/month > 0 with one-sided Newey-West ({T695_NW_LAG}) p < 0.05 (t "
             f"{_s(nw.get('t'), 2)}, p {_f(nw.get('p'), 4)})", nw_ok, nw.get("t") is not None and nw["t"] < -1.645),
            (f"both halves positive ({T695_FIRST}..2017-12 {_pc(halves[0], 3)} over {h1.size}; {T695_SPLIT}..{T695_LAST} "
             f"{_pc(halves[1], 3)} over {h2.size})", None if None in halves else all(h > 0 for h in halves), False),
            (f"FF5+UMD alpha {_pc(alpha, 3) if alpha is not None else 'n/a'}/month > 0 (NW t {_s(alpha_t, 2)}, "
             f"{int(fok.sum())} holds ending by {fend})", None if alpha is None else bool(alpha > 0),
             alpha_t is not None and alpha_t < -1.645),
            (f"net spread positive in >= 2 of 3 sequential volume-level terciles (low {_pc(vol_t['low']['net_mean'], 3)}, "
             f"mid {_pc(vol_t['mid']['net_mean'], 3)}, high {_pc(vol_t['high']['net_mean'], 3)}: {n_pos} positive)",
             None if n_def < 3 else n_pos >= 2, False)]
    v, why, crit_j = CAL._judge(crit, n, T695_MIN_N, "months")
    # ---- reported
    ew = t695_book(rows, "ew")
    xew = ew["net"][ew["elig"]]
    cap_t = {}
    for j, nm in enumerate(("small", "mid", "large")):
        b = t695_book(rows, "vw", _tercile_sub("cap", j))
        x = b["net"][b["elig"]]
        cap_t[nm] = {"net_mean": _mean(x), "n": int(x.size)}
    cov = np.array([[r["n_members"], r["n_priced"], r["n_cap"], r["n_cv"], r["n_el"]] for r in rows_el], float)
    no_price = 1.0 - cov[:, 1] / cov[:, 0]
    no_cap = 1.0 - cov[:, 2] / np.maximum(cov[:, 1], 1)
    absent = 1.0 - cov[:, 4] / cov[:, 0]
    ci = SX.mean_ci(net, 12)
    names_el = cov[:, 4]
    stat = {"n": n, "n_formed": len(rows), "first": months[0], "last": months[-1], "net_mean": mean,
            "gross_mean": float(P["gross"][el].mean()), "cost_mean": float(P["cost"][el].mean()),
            "borrow_mean": float(P["borrow"][el].mean()), "turnover_mean": float(P["turnover"][el].mean()),
            "nw6": nw, "cbb12_ci": ci.get("ci"), "halves": halves, "halves_n": [int(h1.size), int(h2.size)],
            "alpha": alpha, "alpha_t": alpha_t, "alpha_coef": reg.get("coef"), "alpha_n": int(fok.sum()),
            "volume_terciles": vol_t, "cap_terciles": cap_t,
            "ew": {"net_mean": _mean(xew), "n": int(xew.size), "nw_t": hac_mean(xew, T695_NW_LAG)["t"] if xew.size > 3 else None},
            "legs_median": [int(np.median(P["n_long"][el])), int(np.median(P["n_short"][el]))],
            "eligible_names": [int(names_el.min()), int(np.median(names_el)), int(names_el.max())],
            "share_members_without_price": [float(no_price.min()), float(np.median(no_price)), float(no_price.max())],
            "share_priced_without_shares": [float(no_cap.min()), float(np.median(no_cap)), float(no_cap.max())],
            "share_members_absent": [float(absent.min()), float(np.median(absent)), float(absent.max())],
            "unit_filter_refused_median": float(np.median([r["n_unit"] for r in rows_el])),
            "osap_decay_row": "not computed: OSAP's long-short portfolio file is not archived",
            "base": {k: (len(x) if isinstance(x, list) else x) for k, x in I["info"].items()},
            "criteria": crit_j, "verdict": v}
    reason = (f"VW low-minus-high CV quintiles (CV of monthly split-adjusted share volume over the 36 months ending at the "
              f"formation month-end, >= 24 valid) on point-in-time S&P 500 members with a Yahoo price, a CV and SEC shares, "
              f"{n} holding months {months[0]}..{months[-1]}, {int(names_el.min())}-{int(names_el.max())} eligible names a "
              f"month (median legs {stat['legs_median'][0]} / {stat['legs_median'][1]}): net mean {_pc(mean, 3)}/month (gross "
              f"{_pc(stat['gross_mean'], 3)}, cost {_pc(stat['cost_mean'], 3)}, borrow {_pc(stat['borrow_mean'], 3)}), NW(6) "
              f"t {_s(nw.get('t'), 2)}, CBB(12) 95% CI {_pc((ci.get('ci') or [None])[0], 3)}..{_pc((ci.get('ci') or [None, None])[1], 3)}; "
              f"halves {_pc(halves[0], 3)} / {_pc(halves[1], 3)}; FF5+UMD alpha {_pc(alpha, 3) if alpha is not None else 'n/a'} "
              f"(t {_s(alpha_t, 2)}); volume-level terciles low / mid / high {_pc(vol_t['low']['net_mean'], 3)} / "
              f"{_pc(vol_t['mid']['net_mean'], 3)} / {_pc(vol_t['high']['net_mean'], 3)}. Reported: EW cell "
              f"{_pc(stat['ew']['net_mean'], 3)} (NW t {_s(stat['ew']['nw_t'], 2)}); cap terciles small / mid / large "
              f"{_pc(cap_t['small']['net_mean'], 3)} / {_pc(cap_t['mid']['net_mean'], 3)} / {_pc(cap_t['large']['net_mean'], 3)}. "
              f"Coverage: members without a price {np.median(no_price) * 100:.1f}% (median month), priced members without "
              f"usable SEC shares {np.median(no_cap) * 100:.1f}% (range {no_cap.min() * 100:.1f}-{no_cap.max() * 100:.1f}%), "
              f"all absent {np.median(absent) * 100:.1f}%. Survivorship: prices come from today's 901-symbol set (removed and "
              f"acquired members under-represented beyond the claim's own 'priced members' universe); CIKs from the current "
              f"SEC map. OSAP decay row not computed (file not archived)")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-697 ==

def trailing_extreme(C: np.ndarray, w: int, kind: str = "max", chunk: int = 64) -> np.ndarray:
    """X[i] = max (``kind`` 'max') or min of C over rows i-w..i-1 when all w are finite, NaN otherwise. Uses no row >= i."""
    C = np.asarray(C, float)
    D, N = C.shape
    fin = np.isfinite(C)
    cnt = VA.roll_sum(fin.astype(float), w, False)
    X = np.where(fin, C, -np.inf if kind == "max" else np.inf)
    out = np.full((D, N), np.nan)
    for a in range(w, D, chunk):
        b = min(D, a + chunk)
        W = np.lib.stride_tricks.sliding_window_view(X[a - w:b - 1], w, axis=0)     # window j = rows a-w+j .. a-1+j
        out[a:b] = W.max(axis=2) if kind == "max" else W.min(axis=2)
    out[~(cnt == w)] = np.nan
    return out


def first_crossings(C: np.ndarray, Hx: np.ndarray, gap: int, kind: str = "max") -> np.ndarray:
    """Day i is a crossing when C[i] is above (below, ``kind`` 'min') the previous-window extreme Hx[i]; an event is a
    crossing with no crossing on days i-gap..i-1, all of which must have a known extreme."""
    with np.errstate(invalid="ignore"):
        X = np.isfinite(C) & np.isfinite(Hx) & ((C > Hx) if kind == "max" else (C < Hx))
    prior = VA.roll_sum(X.astype(float), gap, False)
    known = VA.roll_sum(np.isfinite(Hx).astype(float), gap, False)
    with np.errstate(invalid="ignore"):
        return X & (prior == 0) & (known == gap)


def av_ratio(V: np.ndarray, w: int = T697_AV_WIN) -> np.ndarray:
    """AV[i] = V[i] / median of V over rows i-w..i-1 (all w positive and finite); NaN unless V[i] > 0."""
    V = np.asarray(V, float)
    with np.errstate(invalid="ignore"):
        Vp = np.where(np.isfinite(V) & (V > 0), V, np.nan)
    med = VA.roll_median(Vp, w)                                            # rows i-w+1..i
    base = np.full(V.shape, np.nan)
    base[1:] = med[:-1]                                                    # rows i-w..i-1
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(Vp) & (base > 0), Vp / base, np.nan)


def _q_sorted(s: list, p: float) -> float:
    """np.quantile(s, p) (linear) of an ascending list."""
    m = len(s)
    pos = p * (m - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, m - 1)
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


def expanding_classes(ev_day: np.ndarray, av: np.ndarray, burn: int = T697_BURN, qs=(1 / 3, 2 / 3, 0.9)) -> dict:
    """Breakpoints for each event from the AV of every event on a strictly earlier day (expanding); events before
    ``burn`` earlier events exist stay unclassified. Returns per event the quantiles, the earlier count and the class
    (2 = above the 2/3 quantile, 0 = below the 1/3, 1 = between, -1 = burn-in) and a top-decile flag."""
    ev_day = np.asarray(ev_day)
    av = np.asarray(av, float)
    n = av.size
    Q = np.full((n, len(qs)), np.nan)
    n_prior = np.zeros(n, int)
    order = np.argsort(ev_day, kind="stable")
    prior: list = []
    i = 0
    while i < n:
        j = i
        d = ev_day[order[i]]
        while j < n and ev_day[order[j]] == d:
            j += 1
        idx = order[i:j]
        n_prior[idx] = len(prior)
        if len(prior) >= max(burn, 2):
            Q[idx] = [_q_sorted(prior, q) for q in qs]
        for k in idx:
            bisect.insort(prior, float(av[k]))
        i = j
    cls = np.full(n, -1, int)
    ok = np.isfinite(Q[:, 0])
    cls[ok] = 1
    cls[ok & (av > Q[:, 1])] = 2
    cls[ok & (av < Q[:, 0])] = 0
    top10 = ok & (av > Q[:, 2])
    return {"q": Q, "n_prior": n_prior, "cls": cls, "top10": top10}


def daily_returns(A: np.ndarray) -> np.ndarray:
    R = np.full(A.shape, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        R[1:] = A[1:] / A[:-1] - 1.0
    return R


def roll_sd(R: np.ndarray, w: int) -> np.ndarray:
    """Sample sd of rows i-w+1..i (all finite), NaN otherwise."""
    fin = np.isfinite(R)
    x = np.where(fin, R, 0.0)
    n = VA.roll_sum(fin.astype(float), w, True)
    s1, s2 = VA.roll_sum(x, w, True), VA.roll_sum(x * x, w, True)
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - s1 * s1 / w) / (w - 1)
    return np.where(n == w, np.sqrt(np.maximum(var, 0.0)), np.nan)


def fwd_abnormal(AO: np.ndarray, MO: np.ndarray, beta: np.ndarray, h: int) -> np.ndarray:
    """[i]: entry at the adjusted open of row i+1 (a bar required), exit at the adjusted open of row i+1+h (the last
    open at or before it for a series that stops), minus beta[i] x SPY over the same opens; NaN past the data."""
    D = AO.shape[0]
    AOf = VA._ffill(AO)
    MOf = VA._ffill(MO[:, None])[:, 0]
    W = np.full(AO.shape, np.nan)
    M = np.full(D, np.nan)
    if D - 1 - h > 0:
        with np.errstate(invalid="ignore", divide="ignore"):
            W[:D - 1 - h] = AOf[1 + h:] / AO[1:D - h] - 1.0
            M[:D - 1 - h] = MOf[1 + h:] / MO[1:D - h] - 1.0
    return W - beta * M[:, None]


def calendar_portfolio(AO, MO, beta, ev_i, ev_j, hold: int, cost: float) -> np.ndarray:
    """Daily calendar-time portfolio: each session the equal-weighted mean over active events of the open-to-open
    abnormal return of interval k -> k+1 (k = i+1 .. i+hold), half the round trip charged on an event's first and on
    its last interval; sessions from the first active one to the last."""
    AOf = VA._ffill(AO)
    MOf = VA._ffill(MO[:, None])[:, 0]
    D = AO.shape[0]
    Rk = np.full(AO.shape, np.nan)
    Mk = np.full(D, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        Rk[:-1] = AOf[1:] / AOf[:-1] - 1.0
        Mk[:-1] = MOf[1:] / MOf[:-1] - 1.0
    tot, cnt = np.zeros(D), np.zeros(D)
    for i, j in zip(ev_i, ev_j):
        ks = np.arange(i + 1, i + 1 + hold)
        ks = ks[ks < D - 1]
        if not ks.size:
            continue
        a = np.nan_to_num(Rk[ks, j] - beta[i, j] * Mk[ks], nan=0.0)
        a[0] -= cost / 2.0
        a[-1] -= cost / 2.0
        tot[ks] += a
        cnt[ks] += 1
    act = np.flatnonzero(cnt > 0)
    if not act.size:
        return np.zeros(0)
    sl = slice(int(act[0]), int(act[-1]) + 1)
    return np.where(cnt[sl] > 0, tot[sl] / np.maximum(cnt[sl], 1), 0.0)


def matched_placebo(ev_i, ev_j, net, vol, dist, pool, band: float = T697_BAND, n_draw: int = T697_N_PLACEBO,
                    seed: int = SEED) -> dict:
    """Each event's net return is replaced by that of a random day of the same name whose trailing vol and distance to
    the 252-day high lie within ``band`` sd (pooled sd over ``pool``) of the event's; the event day itself is excluded.
    p = (1 + #{placebo mean >= observed mean}) / (1 + draws), over the events with at least one matched day."""
    sd_v = float(np.nanstd(vol[pool]))
    sd_d = float(np.nanstd(dist[pool]))
    rng = np.random.default_rng(seed)
    tot = np.zeros(n_draw)
    obs, n, n_none, n_cand = 0.0, 0, 0, []
    pool_idx = {}
    for i, j in zip(ev_i, ev_j):
        if j not in pool_idx:
            pool_idx[j] = np.flatnonzero(pool[:, j])
        P = pool_idx[j]
        m = ((np.abs(vol[P, j] - vol[i, j]) <= band * sd_v) & (np.abs(dist[P, j] - dist[i, j]) <= band * sd_d) & (P != i))
        c = net[P[m], j]
        if not c.size:
            n_none += 1
            continue
        tot += c[rng.integers(0, c.size, n_draw)]
        obs += float(net[i, j])
        n += 1
        n_cand.append(c.size)
    if not n:
        return {"p": None, "n_matched": 0, "n_unmatched": n_none}
    null = tot / n
    o = obs / n
    p = float((1 + np.sum(null >= o - 1e-15)) / (1 + n_draw))
    return {"p": p, "obs": o, "null_mean": float(null.mean()), "null_q95": float(np.quantile(null, 0.95)),
            "n_matched": n, "n_unmatched": n_none, "median_candidates": float(np.median(n_cand)), "sd_vol": sd_v,
            "sd_dist": sd_d, "n_draw": n_draw}


def t697_inputs(archive) -> dict:
    """Events (highs and lows), AV classes, 5/20/60-session net abnormal returns, matching variables, pool."""
    def load():
        B = VA.vbase(archive)
        days_all = B["days"]
        i0 = bisect.bisect_left(days_all, T697_ROW0)
        days = days_all[i0:]
        D = len(days)
        C = B["close"][i0:]
        O = B["open"][i0:]
        A = B["adjclose"][i0:]
        V = B["volume"][i0:]
        mem = B["member"][i0:]
        spy = B["mkt"]["SPY"]
        with np.errstate(invalid="ignore", divide="ignore"):
            AO = O * (A / C)
            MO = spy["open"][i0:] * (spy["adjclose"][i0:] / spy["close"][i0:])
        R = daily_returns(A)
        Rm = daily_returns(spy["adjclose"][i0:][:, None])[:, 0]
        beta = VA.roll_beta(R, Rm, T697_BETA_WIN, T697_BETA_MIN)
        win = np.array([T697_START <= d <= T697_END for d in days], bool)
        AV = av_ratio(V)
        out = {"days": days, "D": D, "win": win, "n_members": B["n_members"][i0:], "member": mem,
               "priced": mem & np.isfinite(C), "syms": B["syms"], "info": B["info"]}
        net = {h: fwd_abnormal(AO, MO, beta, h) - T697_COST for h in (T697_HOLD,) + T697_HOLDS_REP}
        vol = roll_sd(R, T697_VOL_WIN)
        vol_prev = np.full(vol.shape, np.nan)
        vol_prev[1:] = vol[:-1]
        for kind in ("max", "min"):
            Hx = trailing_extreme(C, T697_HIGH_WIN, kind)
            E = first_crossings(C, Hx, T697_GAP, kind) & mem & win[:, None] & np.isfinite(AV)
            if kind == "max":
                with np.errstate(invalid="ignore", divide="ignore"):
                    dist = C / Hx - 1.0
            ei, ej = np.nonzero(E)
            cl = expanding_classes(ei, AV[ei, ej])
            with np.errstate(invalid="ignore"):
                news = np.abs(R[ei, ej]) > T697_NEWS_SIG * vol_prev[ei, ej]
            out[kind] = {"i": ei, "j": ej, "av": AV[ei, ej], **cl, "news": news,
                         "net": {h: net[h][ei, ej] for h in net}, "n_crossings_member": int(E.sum())}
            del Hx, E
        pool = mem & win[:, None] & np.isfinite(vol) & np.isfinite(dist) & np.isfinite(net[T697_HOLD])
        hi = out["max"]
        sel = (hi["cls"] == 2) & np.isfinite(hi["net"][T697_HOLD])
        out["placebo"] = matched_placebo(hi["i"][sel], hi["j"][sel], net[T697_HOLD], vol, dist, pool)
        out["calendar"] = calendar_portfolio(AO, MO, beta, hi["i"][sel], hi["j"][sel], T697_HOLD, T697_COST)
        del AO, R, beta, vol, vol_prev, dist, pool, net, AV
        gc.collect()
        return out
    return CAL._cached(archive, ("b13vb_t697",), load)


def _event_set(I: dict, kind: str, h: int, mask=None) -> tuple:
    E = I[kind]
    x = E["net"][h]
    ok = np.isfinite(x) if mask is None else (np.isfinite(x) & mask)
    return x[ok], np.array([I["days"][i] for i in E["i"][ok]])


def b13_volume_b_confirmed_high(archive):
    """T-697."""
    miss = _missing(archive, [SPY_B, GSPC_B, FJA_B, SPELLS_B]) or _prefix_missing(archive, [DH_PREFIX])
    if miss:
        return miss
    I = t697_inputs(archive)
    E = I["max"]
    conf, unconf = E["cls"] == 2, E["cls"] == 0
    x, dd = _event_set(I, "max", T697_HOLD, conf)
    n = int(x.size)
    if n < 4:
        return _out({"n": n}, n, "inconclusive", f"only {n} confirmed 52-week-high events")
    bc = cboot(x, dd)
    xu, du = _event_set(I, "max", T697_HOLD, unconf)
    xa = np.concatenate([x, xu])
    fa = np.concatenate([np.ones(n, bool), np.zeros(xu.size, bool)])
    da = np.concatenate([dd, du])
    diff = float(x.mean() - xu.mean()) if xu.size else None
    bd = cboot(CAL.flag_diff_series(xa, fa), da) if xu.size >= 2 else {"ci": [None, None]}
    plc = I["placebo"]
    h1 = dd < T697_SPLIT
    halves = [_mean(x[h1]), _mean(x[~h1])]
    c_mean = BW._ci_crit(bc, "gt", 0.0, f"confirmed mean net {_bp(float(x.mean()))} > 0 with date-clustered 95% lower bound > 0",
                         lambda v: _bp(v))
    lo, hi = (bd.get("ci") or [None, None])[:2]
    se_lo, se_hi = (bd.get("ci_mc_se") or [0.0, 0.0])[:2]
    lo_ok = BW.resolve(lo, se_lo, 0.0, "gt")[0] if lo is not None else None
    d_ok = None if diff is None or lo_ok is None else bool(diff >= T697_BAR and lo_ok)
    if diff is not None and diff < T697_BAR:
        d_ok = False
    d_dec = hi is not None and BW.resolve(hi, se_hi, T697_BAR, "lt")[0] is True
    c_diff = (f"confirmed minus unconfirmed {_bp(diff)} >= +50 bp with date-clustered 95% lower bound > 0 (lower "
              f"{_bp(lo)}, upper {_bp(hi)}; {xu.size} unconfirmed events)", d_ok, d_dec)
    c_plc = _p_crit(f"matched placebo p < 0.05 ({plc.get('n_matched')} events matched, {plc.get('n_unmatched')} without a "
                    f"matched day, null mean {_bp(plc.get('null_mean'))})", plc.get("p"), T697_N_PLACEBO)
    c_h = (f"both halves positive (2005-2015 {_bp(halves[0])} over {int(h1.sum())}; 2016-2026 {_bp(halves[1])} over "
           f"{int((~h1).sum())})", None if None in halves else all(v_ > 0 for v_ in halves), False)
    c_dsr, dsr_info = dsr_bound(I["calendar"], T697_TRIALS, f"DSR >= {DSR_PASS} counting T-309's 8 and T-304's 60 trials "
                                f"plus this one (calendar-time daily net of confirmed events)",
                                "T-309's and T-304's trial Sharpes are not on this series")
    crit = [c_mean, c_diff, c_plc, c_h, c_dsr]
    v, why, crit_j = CAL._judge(crit, n, T697_MIN_N, "confirmed-high events")
    # reported only: the same bound on the date-ordered per-event series (overlapping events count as independent, so
    # it is the less conservative series; the criterion stays on the calendar-time portfolio fixed before the run)
    _, dsr_ev = dsr_bound(x[np.argsort(dd, kind="stable")], T697_TRIALS, "per-event", "")
    # ---- reported only
    rep = {}
    for h in T697_HOLDS_REP:
        xc, _ = _event_set(I, "max", h, conf)
        xu2, _ = _event_set(I, "max", h, unconf)
        rep[f"h{h}"] = {"confirmed": _mean(xc), "unconfirmed": _mean(xu2), "n": int(xc.size)}
    xt, _ = _event_set(I, "max", T697_HOLD, E["top10"])
    news_c, _ = _event_set(I, "max", T697_HOLD, conf & E["news"])
    quiet_c, _ = _event_set(I, "max", T697_HOLD, conf & ~E["news"])
    L = I["min"]
    xl, _ = _event_set(I, "min", T697_HOLD, L["cls"] == 2)
    xlu, _ = _event_set(I, "min", T697_HOLD, L["cls"] == 0)
    allh, _ = _event_set(I, "max", T697_HOLD)
    win = I["win"]
    nm = I["n_members"][win].astype(float)
    pr = I["priced"][win].sum(axis=1).astype(float)
    yrs = np.array([d[:4] for d in np.array(I["days"])[win]])
    cov_year = {y: float(pr[yrs == y].sum() / max(nm[yrs == y].sum(), 1)) for y in sorted(set(yrs.tolist()))}
    cov_all = float(pr.sum() / max(nm.sum(), 1))
    stat = {"n": n, "mean_net": float(x.mean()), "boot": {k: bc.get(k) for k in ("ci", "ci_mc_se", "clusters", "reps")},
            "n_unconfirmed": int(xu.size), "mean_unconfirmed": _mean(xu), "diff": diff,
            "diff_boot": {k: bd.get(k) for k in ("ci", "ci_mc_se", "clusters", "reps")}, "placebo": plc, "halves": halves,
            "halves_n": [int(h1.sum()), int((~h1).sum())], "dsr": dsr_info, "dsr_event_series_reported": dsr_ev, "n_events_all": int(E["i"].size),
            "n_burn_in": int((E["cls"] == -1).sum()), "mean_all_events": _mean(allh), "horizons": rep,
            "top_decile_av": {"n": int(xt.size), "mean": _mean(xt)},
            "news_proxy": {"confirmed_news": {"n": int(news_c.size), "mean": _mean(news_c)},
                           "confirmed_quiet": {"n": int(quiet_c.size), "mean": _mean(quiet_c)}},
            "lows_not_judged": {"confirmed": {"n": int(xl.size), "mean": _mean(xl)}, "unconfirmed": {"n": int(xlu.size), "mean": _mean(xlu)}},
            "coverage_priced_member_days": cov_all, "coverage_by_year": cov_year,
            "t578_side_cell": "not computed (an ML side cell outside the verdict)",
            "base": {k: (len(x_) if isinstance(x_, list) else x_) for k, x_ in I["info"].items()},
            "first": str(min(dd.tolist())), "last": str(max(dd.tolist())), "criteria": crit_j, "verdict": v}
    reason = (f"First 252-session closing highs (split-adjusted close, no crossing in the previous 60 sessions) on "
              f"point-in-time S&P 500 members with prices, {stat['first']}..{stat['last']}: {E['i'].size} events "
              f"({stat['n_burn_in']} in the 100-event burn-in), {n} confirmed (AV above the expanding 2/3 quantile of earlier "
              f"events) and {xu.size} unconfirmed (below 1/3). 20-session beta-adjusted return from the next open net of "
              f"10 bp: confirmed {_bp(float(x.mean()))} (date-clustered 95% CI {_ci_txt(bc)}, {bc.get('clusters')} dates), "
              f"unconfirmed {_bp(_mean(xu))}, difference {_bp(diff)} (CI {_ci_txt(bd)}); matched placebo p "
              f"{_f(plc.get('p'), 4)} (null mean {_bp(plc.get('null_mean'))}); halves {_bp(halves[0])} / {_bp(halves[1])}; "
              f"DSR bound {_f(dsr_info.get('dsr_bound'))} at {T697_TRIALS} trials (per-event series, reported only: "
              f"{_f(dsr_ev.get('dsr_bound'))}). Reported: 5 / 60 sessions confirmed "
              f"{_bp(rep['h5']['confirmed'])} / {_bp(rep['h60']['confirmed'])} (unconfirmed {_bp(rep['h5']['unconfirmed'])} / "
              f"{_bp(rep['h60']['unconfirmed'])}); top-decile AV {_bp(_mean(xt))} ({xt.size}); confirmed with a > 3 sigma "
              f"event-day move {_bp(_mean(news_c))} ({news_c.size}) vs without {_bp(_mean(quiet_c))}; lows (not judged, "
              f"survivorship) confirmed {_bp(_mean(xl))} ({xl.size}) / unconfirmed {_bp(_mean(xlu))}. Coverage audit: "
              f"{cov_all * 100:.1f}% of fja member-days {T697_START[:4]}-{T697_END[:4]} have a kept Yahoo price (lowest year "
              f"{min(cov_year, key=cov_year.get)} {min(cov_year.values()) * 100:.1f}%); prices are today's 901-symbol set, "
              f"so removed and acquired members are under-represented")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-699 ==

def t699_sessions(hourly_values, daily_values, start: str = T699_START, end: str = T699_END) -> dict:
    """Per hourly day (New York date with any 1h bar): the 09:30 bar's volume (NaN when absent or not positive), and
    for test sessions the previous official close (day t's dividend basis), the 15:30 bar open, the official open and
    close and the next close-to-open return. A test session is a daily session inside [start, end] with a previous
    daily bar, not an early close, with both the 09:30 and the 15:30 bar. The 16:00 print bar is never used."""
    bars = H5.ny_bars(hourly_values)
    dly = {}
    for v in daily_values:
        if v.get("open") is None or v.get("close") is None:
            continue
        o, c = float(v["open"]), float(v["close"])
        if not (o > 0 and c > 0):
            continue
        adj = v.get("adjclose")
        dly[H5._utc_day(v["t"])] = (o, c, float(adj) / c if adj is not None and float(adj) > 0 else 1.0)
    cal = sorted(dly)
    pos = {d: i for i, d in enumerate(cal)}
    hdays = sorted(bars)
    n = len(hdays)
    nan = float("nan")
    cols = {k: np.full(n, nan) for k in ("v0930", "prev_close", "o1530", "open", "close", "co_next")}
    test = np.zeros(n, bool)
    excl = {k: [] for k in ("early_close", "missing_0930_bar", "missing_1530_bar", "no_daily_bar")}
    for k, d in enumerate(hdays):
        b = bars[d]
        if H5.FIRST_BAR in b:
            vv = b[H5.FIRST_BAR].get("volume")
            if vv is not None and float(vv) > 0:
                cols["v0930"][k] = float(vv)
        if not (start <= d <= end):
            continue
        if d not in pos or pos[d] == 0:
            excl["no_daily_bar"].append(d)
            continue
        if H5.LAST_BAR not in b and H5.EARLY_CLOSE_TICK in b:
            excl["early_close"].append(d)
            continue
        if H5.FIRST_BAR not in b:
            excl["missing_0930_bar"].append(d)
            continue
        if H5.LAST_BAR not in b:
            excl["missing_1530_bar"].append(d)
            continue
        i = pos[d]
        o, c, f = dly[d]
        _, pc, pf = dly[cal[i - 1]]
        cols["prev_close"][k] = pc * pf / f
        cols["o1530"][k] = float(b[H5.LAST_BAR]["open"])
        cols["open"][k], cols["close"][k] = o, c
        if i + 1 < len(cal):
            no, _, nf = dly[cal[i + 1]]
            cols["co_next"][k] = no / (c * f / nf) - 1.0
        test[k] = True
    return {"days": hdays, "test": test, "excluded": excl, **cols}


def rvol_classes(v, med_win: int = T699_MED_WIN, pct_win: int = T699_PCT_WIN, hi: float = T699_HI, lo: float = T699_LO) -> dict:
    """ratio[j] = v[j] / median of the ``med_win`` most recent finite v before j; class[j] from the ``pct_win`` most
    recent finite ratios before j: 2 above their ``hi``-th percentile, 0 below the ``lo``-th, 1 between, -1 undefined.
    Uses nothing at or after j except v[j] itself (the 09:30 bar, complete at 10:30)."""
    v = np.asarray(v, float)
    n = v.size
    ratio = np.full(n, np.nan)
    hist: list = []
    for j in range(n):
        if len(hist) >= med_win and np.isfinite(v[j]):
            ratio[j] = v[j] / float(np.median(hist[-med_win:]))
        if np.isfinite(v[j]):
            hist.append(float(v[j]))
    cls = np.full(n, -1, int)
    p_lo, p_hi = np.full(n, np.nan), np.full(n, np.nan)
    rh: list = []
    for j in range(n):
        if len(rh) >= pct_win and np.isfinite(ratio[j]):
            a, b = np.percentile(rh[-pct_win:], [lo, hi])
            p_lo[j], p_hi[j] = a, b
            cls[j] = 2 if ratio[j] > b else 0 if ratio[j] < a else 1
        if np.isfinite(ratio[j]):
            rh.append(float(ratio[j]))
    return {"ratio": ratio, "cls": cls, "p_lo": p_lo, "p_hi": p_hi}


def momentum_net(S: dict, cost: float = T699_COST) -> dict:
    """Signed 15:30-open-to-official-close return in the sign of (15:30 open / previous close - 1), net of ``cost`` per
    traded session, on the test sessions."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r1 = S["o1530"] / S["prev_close"] - 1.0
        last = S["close"] / S["o1530"] - 1.0
    pos = np.sign(r1)
    gross = pos * last
    net = gross - cost * (pos != 0)
    return {"r1": r1, "last": last, "pos": pos, "gross": gross, "net": net}


def iso_week_ids(days: Sequence[str]) -> np.ndarray:
    keys, out = {}, []
    for d in days:
        y, w, _ = date.fromisoformat(d).isocalendar()
        out.append(keys.setdefault((y, w), len(keys)))
    return np.array(out, int)


def within_week_placebo(net, cls, weeks, n_draw: int = T699_N_PLACEBO, seed: int = SEED) -> dict:
    """Tercile labels permuted within ISO weeks: p of the high mean and of high minus low (one-sided, observed >=)."""
    net, cls = np.asarray(net, float), np.asarray(cls, int)
    hi_o = float(net[cls == 2].mean())
    hml_o = hi_o - float(net[cls == 0].mean())
    dh, dhl = [], []
    for Lb in CAL.permuted_labels(cls, weeks, n_draw, seed):
        h, l = (Lb == 2), (Lb == 0)
        mh = (h * net).sum(axis=1) / h.sum(axis=1)
        ml = (l * net).sum(axis=1) / l.sum(axis=1)
        dh.append(mh)
        dhl.append(mh - ml)
    dh, dhl = np.concatenate(dh), np.concatenate(dhl)
    return {"p_high": float((1 + np.sum(dh >= hi_o - 1e-15)) / (1 + dh.size)),
            "p_hml": float((1 + np.sum(dhl >= hml_o - 1e-15)) / (1 + dhl.size)), "n_draw": int(dh.size),
            "null_high_mean": float(dh.mean()), "null_hml_mean": float(dhl.mean())}


def t699_one(archive, sym: str) -> Optional[dict]:
    hb, db = B7C.hourly(sym), B7C.dh(sym)
    if not (B7C._has(archive, hb) and B7C._has(archive, db)):
        return None
    S = t699_sessions(H5._values(archive, hb), H5._values(archive, db))
    rv = rvol_classes(S["v0930"])
    mn = momentum_net(S)
    use = S["test"] & (rv["cls"] >= 0) & np.isfinite(mn["net"])
    days = [d for d, u in zip(S["days"], use) if u]
    net, cls = mn["net"][use], rv["cls"][use]
    out = {"S": S, "rv": rv, "mn": mn, "use": use, "days": days, "net": net, "cls": cls,
           "n_test": int(S["test"].sum()), "n_classified": int(use.sum())}
    for k, c in (("high", 2), ("mid", 1), ("low", 0)):
        x = net[cls == c]
        out[k] = {"n": int(x.size), "mean": _mean(x), "gross": _mean(mn["gross"][use][cls == c])}
    out["hml"] = None if out["high"]["mean"] is None or out["low"]["mean"] is None else out["high"]["mean"] - out["low"]["mean"]
    return out


def b13_volume_b_rvol_momentum(archive):
    """T-699."""
    miss = _missing(archive, [B7C.hourly("SPY"), B7C.dh("SPY")])
    if miss:
        return miss
    res = {s: t699_one(archive, s) for s in T699_SYMS}
    R = res["SPY"]
    net, cls, days = R["net"], R["cls"], R["days"]
    hi = cls == 2
    n = int(hi.sum())
    if n < 8 or (cls == 0).sum() < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} high-RVOL SPY sessions")
    p_high = 1.0 if not hi.any() else float(hi.mean())
    d_hi = np.where(hi, net / p_high, 0.0)
    pg, pl, dr = CAL.studentized_p_escalated(d_hi, T699_BLOCK, None, SEED, B7C.N_SEEDS)
    d_hml = CAL.contrast_series(net, hi, cls == 0)
    qg, ql, dq = CAL.studentized_p_escalated(d_hml, T699_BLOCK, None, SEED, B7C.N_SEEDS)
    wk = iso_week_ids(days)
    plc = within_week_placebo(net, cls, wk)
    m_hi, hml = R["high"]["mean"], R["hml"]
    c_hi = (f"high-RVOL mean net {_bp(m_hi, 2)} > 0 with one-sided weekly-block bootstrap p < 0.05 (p {B7C._mc(pg, dr)})",
            B7C._sig_crit(m_hi, pg, dr), CAL.decide_p(pl, dr) is True)
    c_hml = (f"high minus low {_bp(hml, 2)} > 0 with p < 0.05 (p {B7C._mc(qg, dq)}; low {_bp(R['low']['mean'], 2)} over "
             f"{R['low']['n']})", B7C._sig_crit(hml, qg, dq), CAL.decide_p(ql, dq) is True)
    r1 = _p_crit("within-week random-tercile placebo, high mean", plc["p_high"], plc["n_draw"])
    r2 = _p_crit("high minus low", plc["p_hml"], plc["n_draw"])
    c_plc = BW.all_constructions([r1, r2], f"placebo p < 0.05 ({plc['n_draw']} within-week permutations)")
    oth = {}
    for s in ("QQQ", "IWM"):
        o = res.get(s)
        oth[s] = None if o is None else {"high": o["high"], "low": o["low"], "hml": o["hml"]}
    so = []
    for s in ("QQQ", "IWM"):
        o = oth[s]
        so.append(None if o is None or o["high"]["mean"] is None or o["hml"] is None else bool(o["high"]["mean"] > 0 and o["hml"] > 0))
    c_same = ("same sign on QQQ and IWM (high mean > 0 and high minus low > 0: QQQ "
              + (f"{_bp(oth['QQQ']['high']['mean'], 2)} / {_bp(oth['QQQ']['hml'], 2)}" if oth["QQQ"] else "n/a")
              + "; IWM " + (f"{_bp(oth['IWM']['high']['mean'], 2)} / {_bp(oth['IWM']['hml'], 2)}" if oth["IWM"] else "n/a") + ")",
              None if None in so else all(so), False)
    c_dsr, dsr_info = dsr_bound(net[hi], T699_TRIALS, f"deflated p < 0.05 (DSR > {DSR_PASS}) counting T-427's 60 cells "
                                f"plus this one", "T-427's 60 cells were never computed", strict=True)
    crit = [c_hi, c_hml, c_plc, c_same, c_dsr]
    v, why, crit_j = CAL._judge(crit, n, T699_MIN_N, "high-RVOL SPY sessions")
    # ---- reported only
    S, use = R["S"], R["use"]
    reg = {}
    for nm, path in ((FOMC_B, "fomc"), (CPI_B, "cpi")):
        if not B7C._has(archive, nm):
            continue
        vals = H5._values(archive, nm)
        evd = ({x["decision_day"] for x in vals if x.get("scheduled")} if path == "fomc" else set(H5.cpi_release_days(vals)))
        f = np.array([d in evd for d in days], bool)
        reg[path] = {"n_high": int((f & hi).sum()), "mean_high": _mean(net[f & hi]), "mean_high_other": _mean(net[~f & hi]),
                     "n_all": int(f.sum()), "mean_all": _mean(net[f])}
    with np.errstate(invalid="ignore", divide="ignore"):
        Lr = (S["close"] / S["o1530"] - 1.0)[use]
        Rr = (S["o1530"] / S["open"] - 1.0)[use]
    y = S["co_next"][use]
    okf = hi & np.isfinite(y) & np.isfinite(Lr) & np.isfinite(Rr)
    fals = None
    if okf.sum() > 20:
        b, se = H5.ols_hac(y[okf], np.column_stack([np.ones(int(okf.sum())), Lr[okf], Rr[okf]]))
        fals = {"n": int(okf.sum()), "slope_last_half_hour": float(b[1]), "hac_t": float(b[1] / se[1]) if se[1] > 0 else None,
                "t428_full_sample_slope": T699_T428_SLOPE}
    stat = {"n": n, "first": days[0], "last": days[-1], "n_sessions_classified": len(days), "n_test_sessions": R["n_test"],
            "excluded": {k: len(x) for k, x in S["excluded"].items()}, "high": R["high"], "mid": R["mid"], "low": R["low"],
            "hml": hml, "p_high": pg, "p_hml": qg, "draws": [dr, dq], "placebo": plc, "others": oth, "dsr": dsr_info,
            "unconditional_mean_net": _mean(net), "regimes": reg, "falsification_t428": fals,
            "not_run": "2016-01..2023-10 minute-bar replication (required before any forward paper; no archived minute bars)",
            "criteria": crit_j, "verdict": v}
    reason = (f"SPY 15:30-open-to-close in the sign of the previous close to the 15:30 open, 2 bp round trip, on archived "
              f"1h bars: {len(days)} sessions {days[0]}..{days[-1]} with an RVOL class (of {R['n_test']} test sessions; "
              f"{len(S['excluded']['early_close'])} early closes, {len(S['excluded']['missing_0930_bar'])} without the 09:30 "
              f"bar, {len(S['excluded']['missing_1530_bar'])} without the 15:30 bar excluded; the first 80 sessions are RVOL "
              f"warm-up). High-RVOL {n} sessions mean net {_bp(m_hi, 2)} (gross {_bp(R['high']['gross'], 2)}), mid "
              f"{_bp(R['mid']['mean'], 2)} ({R['mid']['n']}), low {_bp(R['low']['mean'], 2)} ({R['low']['n']}); high minus "
              f"low {_bp(hml, 2)}; weekly-block p {_f(pg, 4)} / {_f(qg, 4)}; within-week placebo p {_f(plc['p_high'], 4)} / "
              f"{_f(plc['p_hml'], 4)}; QQQ high {_bp(oth['QQQ']['high']['mean'] if oth['QQQ'] else None, 2)} (hml "
              f"{_bp(oth['QQQ']['hml'] if oth['QQQ'] else None, 2)}), IWM high {_bp(oth['IWM']['high']['mean'] if oth['IWM'] else None, 2)} "
              f"(hml {_bp(oth['IWM']['hml'] if oth['IWM'] else None, 2)}); DSR bound {_f(dsr_info.get('dsr_bound'))} at 61 "
              f"trials. Reported: all classified sessions {_bp(_mean(net), 2)}; "
              + "; ".join(f"{k.upper()} days high-RVOL {_bp(r_['mean_high'], 2)} ({r_['n_high']})" for k, r_ in reg.items())
              + (f"; next close-to-open on the last half hour on high-RVOL days slope {fals['slope_last_half_hour']:+.3f} (HAC t "
                 f"{_s(fals['hac_t'], 2)}; T-428 full sample -0.084)" if fals else "")
              + ". Seen window: T-427 used these sessions; the 2016-2023 minute-bar replication is not run")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-700 ==

def epoch_seconds(index) -> np.ndarray:
    """UTC epoch seconds of a tz-aware DatetimeIndex whatever its resolution (``load_bars`` yields datetime64[s], where
    ``view('int64')`` is already seconds; a nanosecond index would need // 1e9)."""
    import pandas as pd
    return np.asarray((index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1), dtype=np.int64)


def t700_universe() -> list:
    from mandel.ml.fetch import EQUITY_ETF, STOCKS
    return [(s, "stock") for s in STOCKS] + [(s, "etf") for s in EQUITY_ETF if s not in T700_EXCLUDE_ETF]


def slot_day_returns(t_utc: np.ndarray, o: np.ndarray, c: np.ndarray) -> dict:
    """{New York day: 7 slot returns} for days with all seven bars 09:30..15:30 (bar-start stamps): slot 1 = close /
    open of the 09:30 bar, slot h = close_h / close_{h-1} - 1. Other bars (the 16:00 print, extended hours) are
    ignored."""
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    by = defaultdict(dict)
    for t, oo, cc in zip(t_utc, o, c):
        ts = datetime.fromtimestamp(int(t), tz=timezone.utc).astimezone(NY)
        hm = ts.strftime("%H:%M")
        if hm in T700_SLOTS and np.isfinite(oo) and np.isfinite(cc) and oo > 0 and cc > 0:
            by[ts.strftime("%Y-%m-%d")][hm] = (float(oo), float(cc))
    out = {}
    for d, b in by.items():
        if len(b) != len(T700_SLOTS):
            continue
        oc = [b[s] for s in T700_SLOTS]
        r = [oc[0][1] / oc[0][0] - 1.0] + [oc[h][1] / oc[h - 1][1] - 1.0 for h in range(1, len(oc))]
        out[d] = np.array(r, float)
    return out


def lookback_means(R: np.ndarray, k: int = T700_LOOK) -> tuple:
    """R (days, 7, names). (same, other): the mean of slot h over days d-k..d-1 and the mean of the other six slots
    over the same days; NaN unless the name has all k previous days. Uses no day >= d."""
    D, Hs, N = R.shape
    fin = np.isfinite(R).all(axis=1)                                   # day complete for the name
    Rz = np.where(np.isfinite(R), R, 0.0)
    cs = np.concatenate([np.zeros((1, Hs, N)), np.cumsum(Rz, axis=0)], axis=0)
    cf = np.concatenate([np.zeros((1, N)), np.cumsum(fin.astype(float), axis=0)], axis=0)
    same = np.full(R.shape, np.nan)
    other = np.full(R.shape, np.nan)
    if D > k:
        s = cs[k:D] - cs[:D - k]                                       # rows d = k..D-1: days d-k..d-1
        cnt = cf[k:D] - cf[:D - k]
        tot = s.sum(axis=1, keepdims=True)
        ok = (cnt == k)[:, None, :]
        same[k:] = np.where(ok, s / k, np.nan)
        other[k:] = np.where(ok, (tot - s) / (k * (Hs - 1)), np.nan)
    return same, other


def slot_regressions(R, same, other, min_names: int = T700_MIN_NAMES) -> dict:
    """Per slot-day cross-sectional regressions: 'uni' (separate univariate slopes on the same-slot and the other-slot
    mean) and 'joint' (one regression on both); returns the slope differences (same minus other) with their day and
    slot indices."""
    D, Hs, N = R.shape
    out = {"d": [], "h": [], "uni": [], "joint": [], "n": []}
    for d in range(D):
        for h in range(Hs):
            y, s, o = R[d, h], same[d, h], other[d, h]
            ok = np.isfinite(y) & np.isfinite(s) & np.isfinite(o)
            if ok.sum() < min_names:
                continue
            y_, s_, o_ = y[ok], s[ok], o[ok]
            vs, vo = s_.var(), o_.var()
            if not (vs > 0 and vo > 0):
                continue
            bs = float(((s_ - s_.mean()) * (y_ - y_.mean())).mean() / vs)
            bo = float(((o_ - o_.mean()) * (y_ - y_.mean())).mean() / vo)
            X = np.column_stack([np.ones(ok.sum()), s_, o_])
            b = np.linalg.lstsq(X, y_, rcond=None)[0]
            out["d"].append(d)
            out["h"].append(h)
            out["uni"].append(bs - bo)
            out["joint"].append(float(b[1] - b[2]))
            out["n"].append(int(ok.sum()))
    return {k: np.array(v) for k, v in out.items()}


def slot_portfolio(R, same, cost, min_names: int = T700_MIN_NAMES) -> dict:
    """Per slot-day: long the top, short the bottom quintile of the same-slot mean (equal weight), a round trip per leg
    per slot at each name's per-side cost; daily sums over the slots."""
    D, Hs, N = R.shape
    g, nt, dd = [], [], []
    for d in range(D):
        for h in range(Hs):
            y, s = R[d, h], same[d, h]
            ok = np.isfinite(y) & np.isfinite(s)
            if ok.sum() < min_names:
                continue
            lo, hi = q_legs(s, ok)
            if not lo.any() or not hi.any():
                continue
            gr = float(y[hi].mean() - y[lo].mean())
            g.append(gr)
            nt.append(gr - 2.0 * float(cost[hi].mean() + cost[lo].mean()))
            dd.append(d)
    g, nt, dd = np.array(g), np.array(nt), np.array(dd, int)
    days_u = np.unique(dd)
    daily = np.array([nt[dd == d].sum() for d in days_u]) if dd.size else np.zeros(0)
    return {"gross": g, "net": nt, "daily_net": daily, "n_slot_days": int(g.size)}


def t700_panel() -> dict:
    from mandel.ml.features import load_bars
    uni = t700_universe()
    per, kinds = {}, {}
    for sym, kind in uni:
        df = load_bars("60m", sym)
        if df is None or df.empty:
            continue
        t = epoch_seconds(df.index)
        per[sym] = slot_day_returns(t, df["o"].to_numpy(float), df["c"].to_numpy(float))
        kinds[sym] = kind
    if "SPY" not in per:
        return {"days": [], "syms": [], "R": np.zeros((0, len(T700_SLOTS), 0))}
    days = sorted(per["SPY"])
    syms = sorted(per)
    R = np.full((len(days), len(T700_SLOTS), len(syms)), np.nan)
    pos = {d: i for i, d in enumerate(days)}
    for j, s in enumerate(syms):
        for d, r in per[s].items():
            i = pos.get(d)
            if i is not None:
                R[i, :, j] = r
    return {"days": days, "syms": syms, "kinds": [kinds[s] for s in syms], "R": R}


def _local_check(archive, days_local: Sequence[str]) -> dict:
    """Close agreement of the local SPY 60m bars with the archived hourly-SPY bundle on common bar stamps."""
    from mandel.ml.features import load_bars
    df = load_bars("60m", "SPY")
    arch = {int(v["t"]): float(v["close"]) for v in H5._values(archive, B7C.hourly("SPY")) if v.get("close") is not None}
    t = epoch_seconds(df.index)
    c = df["c"].to_numpy(float)
    common = [(arch[int(tt)], cc) for tt, cc in zip(t, c) if int(tt) in arch]
    if not common:
        return {"common_bars": 0}
    a = np.array(common)
    rel = np.abs(a[:, 0] / a[:, 1] - 1.0)
    return {"common_bars": int(a.shape[0]), "share_within_1bp": float((rel < 1e-4).mean()), "max_rel_diff": float(rel.max())}


def b13_volume_b_same_slot(archive):
    """T-700."""
    miss = _missing(archive, [B7C.hourly("SPY"), B7C.dh("SPY")])
    if miss:
        return miss
    PNL = CAL._cached(archive, ("b13vb_t700_panel",), t700_panel)
    days, syms, R = PNL["days"], PNL["syms"], PNL["R"]
    if not days:
        return _out({"n": 0}, 0, "inconclusive", "no local 60m bars for SPY (mandel/ml_data/bars/60m): rule 9")
    same, other = lookback_means(R)
    G = slot_regressions(R, same, other)
    dd = G["d"]
    ud = np.unique(dd)
    n = int(ud.size)
    if n < 10:
        return _out({"n": n}, n, "inconclusive", f"only {n} regression days")
    dstr = np.array(days)[dd]
    rows, info = [], {}
    for half, mask_fn in (("first", lambda a: a < T700_SPLIT), ("second", lambda a: a >= T700_SPLIT)):
        cons = []
        for rd in ("uni", "joint"):
            x = G[rd]
            m = mask_fn(dstr)
            xs = x[m]
            dsel = dd[m]
            daily = np.array([xs[dsel == k].mean() for k in np.unique(dsel)]) if xs.size else np.zeros(0)
            t_s = hac_mean(xs, _nw_lag(xs.size)) if xs.size > 10 else {"t": None, "mean": None}
            t_d = hac_mean(daily, _nw_lag(daily.size)) if daily.size > 10 else {"t": None, "mean": None}
            info[f"{half}_{rd}"] = {"mean": _mean(xs), "n_slot_days": int(xs.size), "n_days": int(daily.size),
                                    "t_slotday": t_s.get("t"), "lag_slotday": t_s.get("lag"), "t_daily": t_d.get("t"),
                                    "lag_daily": t_d.get("lag")}
            for tn, tt in (("slot-day", t_s), ("daily", t_d)):
                ok = None if tt.get("t") is None else bool(tt["mean"] > 0 and tt["t"] > T700_T)
                cons.append((f"{rd} {tn} mean {_s(tt.get('mean'), 4)} t {_s(tt.get('t'), 2)}", ok,
                             tt.get("t") is not None and tt["t"] < -T700_T))
        lab = "2023-11..2025-04" if half == "first" else "2025-05..2026-10"
        rows.append(BW.all_constructions(cons, f"{half} half ({lab}): same-slot minus other-slot slope > 0 with NW t > {T700_T}"))
    v, why, crit_j = CAL._judge(rows, n, T700_MIN_N, "trading days")
    # ---- reported
    full = {}
    for rd in ("uni", "joint"):
        x = G[rd]
        daily = np.array([x[dd == k].mean() for k in ud])
        full[rd] = {"mean": float(x.mean()), "t_slotday": hac_mean(x, _nw_lag(x.size))["t"],
                    "t_daily": hac_mean(daily, _nw_lag(daily.size))["t"],
                    "by_slot": {T700_SLOTS[h]: _mean(x[G["h"] == h]) for h in range(len(T700_SLOTS))}}
    cost = np.array([T700_COST_ETF if k == "etf" else T700_COST_STOCK for k in PNL["kinds"]])
    sp = slot_portfolio(R, same, cost)
    sp_ci = SX.mean_ci(sp["daily_net"], 5) if sp["daily_net"].size >= 8 else {"ci": [None, None]}
    chk = _local_check(archive, days)
    n_st = sum(1 for k in PNL["kinds"] if k == "stock")
    stat = {"n": n, "first": days[int(ud[0])], "last": days[int(ud[-1])], "n_slot_regressions": int(dd.size),
            "names": len(syms), "stocks": n_st, "etfs": len(syms) - n_st, "median_names": float(np.median(G["n"])),
            "halves": info, "full": full,
            "slot_portfolio": {"mean_gross_slot": _mean(sp["gross"]), "mean_net_slot": _mean(sp["net"]),
                               "mean_net_daily": _mean(sp["daily_net"]), "ci_daily": sp_ci.get("ci"),
                               "n_slot_days": sp["n_slot_days"]},
            "local_vs_archive_spy": chk, "criteria": crit_j, "verdict": v}
    f1, f2 = info["first_uni"], info["second_uni"]
    j1, j2 = info["first_joint"], info["second_joint"]
    reason = (f"Same-slot continuation on {len(syms)} names ({n_st} US stocks, {len(syms) - n_st} unlevered US equity ETFs) "
              f"in the local 60m bars, {stat['first']}..{stat['last']}: {dd.size} slot-day regressions over {n} days "
              f"(median {stat['median_names']:.0f} names). Same-slot minus other-slot slope, univariate reading: full "
              f"{full['uni']['mean']:+.4f} (t {_s(full['uni']['t_slotday'], 2)} slot-day / {_s(full['uni']['t_daily'], 2)} "
              f"daily), first half {_s(f1['mean'], 4)} (t {_s(f1['t_slotday'], 2)} / {_s(f1['t_daily'], 2)}), second half "
              f"{_s(f2['mean'], 4)} (t {_s(f2['t_slotday'], 2)} / {_s(f2['t_daily'], 2)}); joint reading first "
              f"{_s(j1['mean'], 4)} (t {_s(j1['t_slotday'], 2)} / {_s(j1['t_daily'], 2)}), second {_s(j2['mean'], 4)} (t "
              f"{_s(j2['t_slotday'], 2)} / {_s(j2['t_daily'], 2)}). Reported: top-minus-bottom quintile slot portfolio gross "
              f"{_bp(stat['slot_portfolio']['mean_gross_slot'], 2)} per slot, net {_bp(stat['slot_portfolio']['mean_net_slot'], 2)} "
              f"(2 bp / 5 bp per side), daily net {_bp(stat['slot_portfolio']['mean_net_daily'], 2)}; local SPY bars agree "
              f"with hourly-SPY within 1 bp on {_f((chk.get('share_within_1bp') or 0) * 100, 1)}% of {chk.get('common_bars')} "
              f"common bars. Universe is today's names (no delisted stocks)")
    return _out(stat, n, v, reason + " — " + why)


# ====================================================================================================== T-702 ==

def _o(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _iso(o: int) -> str:
    return date.fromordinal(int(o)).isoformat()


def crypto_panel(daily: dict, first: str, last: str) -> dict:
    """Calendar-day grid: C (close, NaN = no trade), V (base volume, 0 = no trade), traded mask, first trade ordinal."""
    o0, o1 = _o(first), _o(last)
    T = o1 - o0 + 1
    pids = sorted(daily)
    C = np.full((len(pids), T), np.nan)
    V = np.zeros((len(pids), T))
    first_o = np.full(len(pids), np.iinfo(np.int64).max, np.int64)
    for i, p in enumerate(pids):
        for d, (c, v) in daily[p].items():
            od = _o(d)
            if c is None or not c > 0 or v is None or v < 0:
                continue
            first_o[i] = min(first_o[i], od)
            k = od - o0
            if 0 <= k < T:
                C[i, k] = c
                V[i, k] = v
    traded = np.isfinite(C)
    Cf = VA._ffill(C.T).T
    return {"pids": pids, "o0": o0, "T": T, "C": C, "V": V, "Cf": Cf, "traded": traded, "first_o": first_o}


def week_signals(Pn: dict, e: int, reading: str) -> dict:
    """Signals for the entry column ``e`` (the entry day's bar; the signal bar is e - 1, Saturday for a Sunday entry):
    prior-week return (last close at or before e-1 over the same at e-8), relative volume (mean of days e-7..e-1 over
    the mean of days e-30..e-1; base or dollar volume), and history validity (first trade on or before e-30). Uses no
    column >= e."""
    C, Cf, V = Pn["C"], Pn["Cf"], Pn["V"]
    s = e - 1
    with np.errstate(invalid="ignore", divide="ignore"):
        ret = Cf[:, s] / Cf[:, s - T702_WEEK] - 1.0
        X = V if reading == "base" else np.where(np.isfinite(C), C * V, 0.0)
        v7 = X[:, s - T702_WEEK + 1:s + 1].sum(axis=1) / T702_WEEK
        v30 = X[:, s - T702_RV_DAYS + 1:s + 1].sum(axis=1) / T702_RV_DAYS
        rv = np.where(v30 > 0, v7 / v30, np.nan)
    hist = Pn["first_o"] <= Pn["o0"] + s - T702_RV_DAYS + 1
    return {"ret": ret, "rv": rv, "hist": hist}


def t702_series(Pn: dict, members: dict, phase: int, reading: str, first: str = T702_FIRST, last: str = T702_LAST) -> dict:
    """Weekly rows for entries on weekday ``phase`` in [first, last]: legs (low-activity losers / winners, high-activity
    losers / winners) as equal-weight vectors, hold returns and the equal-weighted universe return."""
    pos = {p: i for i, p in enumerate(Pn["pids"])}
    P, T, o0 = len(Pn["pids"]), Pn["T"], Pn["o0"]
    rows = []
    o = _o(first)
    while date.fromordinal(o).weekday() != phase:
        o += 1
    while o <= _o(last):
        e, x = o - o0, o - o0 + T702_WEEK
        if x >= T or e - T702_RV_DAYS - 1 < 0:
            o += T702_WEEK
            continue
        mem = np.zeros(P, bool)
        for p in members.get(_iso(o), []):
            if p in pos:
                mem[pos[p]] = True
        univ = mem & Pn["traded"][:, e]
        with np.errstate(invalid="ignore", divide="ignore"):
            hold = np.where(univ, Pn["Cf"][:, x] / Pn["C"][:, e] - 1.0, 0.0)
        sg = week_signals(Pn, e, reading)
        sig = univ & np.isfinite(sg["ret"]) & np.isfinite(sg["rv"]) & sg["hist"]
        lo_t, _, hi_t = terciles(sg["rv"], sig)
        legs = {}
        for nm, grp in (("la", lo_t), ("ha", hi_t)):
            los, win = q_legs(sg["ret"], grp)
            legs[nm + "l"], legs[nm + "w"] = los, win
        rows.append({"day": _iso(o), "univ_n": int(univ.sum()), "sig_n": int(sig.sum()),
                     "univ_ret": float(hold[univ].mean()) if univ.any() else np.nan, "hold": hold, **legs})
        o += T702_WEEK
    return {"rows": rows}


def leg_book(rows: list, key: str, cost_side: float) -> dict:
    """Equal-weight long-only book of one leg: gross, net (``cost_side`` x traded weight, drifted weights, first entry
    and final exit charged; ``batch13_volume_a.book`` with an empty short leg), eligibility = a non-empty leg."""
    M = len(rows)
    if not M:
        return {"gross": np.zeros(0), "net": np.zeros(0), "turnover": np.zeros(0), "elig": np.zeros(0, bool)}
    P = rows[0]["hold"].size
    W = np.zeros((M, P))
    elig = np.zeros(M, bool)
    for k, r in enumerate(rows):
        m = r[key]
        if m.any() and np.isfinite(r["univ_ret"]):
            W[k] = m / m.sum()
            elig[k] = True
    HR = np.vstack([r["hold"] for r in rows])
    bk = VA.book(W, np.zeros_like(W), HR, elig, np.zeros(M), cost_side, 0.0)
    return {"gross": bk["gross"], "net": bk["net"], "turnover": bk["turnover"], "elig": elig}


def t702_stats(S: dict, cost_side: float) -> dict:
    rows = S["rows"]
    bks = {k: leg_book(rows, k, cost_side) for k in ("lal", "law", "hal", "haw")}
    U = np.array([r["univ_ret"] for r in rows], float)
    days = np.array([r["day"] for r in rows])
    el = bks["lal"]["elig"] & np.isfinite(U)
    ex = bks["lal"]["net"][el] - U[el]
    exg = bks["lal"]["gross"][el] - U[el]
    el4 = el & bks["law"]["elig"] & bks["hal"]["elig"] & bks["haw"]["elig"]
    sg = (bks["lal"]["gross"] - bks["law"]["gross"]) - (bks["hal"]["gross"] - bks["haw"]["gross"])
    sn = (bks["lal"]["net"] - bks["law"]["net"]) - (bks["hal"]["net"] - bks["haw"]["net"])
    return {"ex": ex, "ex_gross": exg, "days": days[el], "spread_gross": sg[el4], "spread_net": sn[el4], "days4": days[el4],
            "low_spread": (bks["lal"]["gross"] - bks["law"]["gross"])[el4], "high_spread": (bks["hal"]["gross"] - bks["haw"]["gross"])[el4],
            "turnover_lal": bks["lal"]["turnover"][el], "n_weeks": int(el.sum()), "n_formed": len(rows),
            "lal_size": np.array([int(r["lal"].sum()) for r in rows])[el], "univ_size": np.array([r["univ_n"] for r in rows])[el]}


def t702_inputs(archive) -> dict:
    def load():
        prods = CV._names(archive, CV.CB_PRODUCTS_PREFIX)
        names = [nm for nm in CV._names(archive, "coinbase-daily-") if nm.endswith("-USD")]
        stable_ids = set()
        for r in CV._stream(archive, prods[-1]):
            v = r.get("value") or {}
            if v.get("fx_stablecoin") and v.get("id"):
                stable_ids.add(v["id"])
        daily_all = {}
        for nm in names:
            pid = nm[len("coinbase-daily-"):]
            if pid in stable_ids:
                continue
            daily_all[pid] = CV._cb_daily_map(archive, pid)
        last = max((max(m) for m in daily_all.values() if m), default=None)
        out = {"n_bundles": len(names), "stable_ids": sorted(stable_ids), "last": last}
        for tag, excl in (("main", T702_EXCLUDE), ("incl", T702_EXCLUDE_INCL)):
            daily = {p: m for p, m in daily_all.items() if p.split("-")[0] not in excl and m}
            members = CV.cb_members(daily, _iso(_o(T702_FIRST) - 7), last, exclude=excl, top=T702_TOP,
                                    window=T702_RANK_DAYS, stable_ids=frozenset(stable_ids))
            Pn = crypto_panel(daily, T702_PANEL0, last)
            out[tag] = {"members": members, "panel": Pn, "n_products": len(daily)}
        return out
    return CAL._cached(archive, ("b13vb_t702",), load)


def b13_volume_b_crypto_lal(archive):
    """T-702."""
    prods = CV._names(archive, CV.CB_PRODUCTS_PREFIX)
    dn = [nm for nm in CV._names(archive, "coinbase-daily-") if nm.endswith("-USD")]
    miss = _missing(archive, ([] if prods else ["coinbase-products-<day>"]) + ([] if dn else ["coinbase-daily-<PID>"]))
    if miss:
        return miss
    I = t702_inputs(archive)
    M = I["main"]
    res = {}
    for rd in ("base", "dollar"):
        S = t702_series(M["panel"], M["members"], T702_PHASE, rd)
        res[rd] = {"S": S, "st": t702_stats(S, T702_COST_SIDE), "stress": t702_stats(S, T702_STRESS_SIDE)}
    n = min(res[rd]["st"]["n_weeks"] for rd in res)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} weeks with a low-activity-loser portfolio")
    R = {}
    for rd in res:
        st, ss = res[rd]["st"], res[rd]["stress"]
        R[rd] = {"mean": float(st["ex"].mean()), "ci": SX.mean_ci(st["ex"], T702_BLOCK),
                 "stress_mean": float(ss["ex"].mean()), "stress_ci": SX.mean_ci(ss["ex"], T702_BLOCK),
                 "halves": [_mean(st["ex"][st["days"] < T702_SPLIT]), _mean(st["ex"][st["days"] >= T702_SPLIT])],
                 "halves_n": [int((st["days"] < T702_SPLIT).sum()), int((st["days"] >= T702_SPLIT).sum())]}
        for k in ("spread_gross", "spread_net"):
            pg, pl, dr = CAL.studentized_p_escalated(st[k], T702_BLOCK, None, SEED, B7C.N_SEEDS)
            R[rd][k] = {"mean": _mean(st[k]), "p": pg, "p_less": pl, "draws": dr, "n": int(st[k].size)}
    fmt = lambda v: _pc(v, 3)
    c_lo = BW.all_constructions([VA._ci_lower_row(R[rd]["ci"], f"{rd} {_pc(R[rd]['mean'], 3)}") for rd in R],
                                f"long-only weekly excess net > 0 with studentized CBB ({T702_BLOCK}-week) 95% lower bound > 0")
    c_h = BW.all_constructions([(f"{rd} {_pc(R[rd]['halves'][0], 3)} / {_pc(R[rd]['halves'][1], 3)}",
                                 None if None in R[rd]["halves"] else all(h > 0 for h in R[rd]["halves"]), False) for rd in R],
                               f"both halves positive (split {T702_SPLIT})")
    sp_rows = []
    for rd in R:
        for k in ("spread_gross", "spread_net"):
            q = R[rd][k]
            sp_rows.append((f"{rd} {k.split('_')[1]} {_pc(q['mean'], 3)} (p {B7C._mc(q['p'], q['draws'])})",
                            B7C._sig_crit(q["mean"], q["p"], q["draws"]), CAL.decide_p(q["p_less"], q["draws"]) is True))
    c_sp = BW.all_constructions(sp_rows, "low-activity minus high-activity loser-minus-winner spread > 0 with one-sided p < 0.05")
    c_st = BW.all_constructions([VA._ci_lower_row(R[rd]["stress_ci"], f"{rd} {_pc(R[rd]['stress_mean'], 3)}") for rd in R],
                                "holds at the 100 bp stress (excess net > 0 with CBB 95% lower bound > 0)")
    drows, dinfo = [], {}
    for rd in R:
        r_, i_ = dsr_bound(res[rd]["st"]["ex"], T702_TRIALS, f"{rd}", "T-546's trial has no Sharpe on this series")
        drows.append(r_)
        dinfo[rd] = i_
    c_dsr = BW.all_constructions(drows, f"DSR >= {DSR_PASS} counting T-314's 24 and T-546's 1 trial plus this one (26)")
    crit = [c_lo, c_h, c_sp, c_st, c_dsr]
    v, why, crit_j = CAL._judge(crit, n, T702_MIN_N, "weeks")
    # ---- reported only
    fam = MOM.family_dsr(res["base"]["st"]["ex"], [sharpe_ratio(res["base"]["st"]["ex"])] + list(T314_SHARPES), T702_TRIALS)
    phases = {}
    for ph in range(7):
        if ph == T702_PHASE:
            continue
        S = t702_series(M["panel"], M["members"], ph, "base")
        st = t702_stats(S, T702_COST_SIDE)
        phases[["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][ph]] = {"n": st["n_weeks"], "mean": _mean(st["ex"])}
    S_in = t702_series(I["incl"]["panel"], I["incl"]["members"], T702_PHASE, "base")
    st_in = t702_stats(S_in, T702_COST_SIDE)
    stb = res["base"]["st"]
    y22 = np.array([d.startswith("2022") for d in stb["days"]], bool)
    stat = {"n": n, "first": str(stb["days"][0]), "last": str(stb["days"][-1]),
            "readings": {rd: {"mean_excess_net": R[rd]["mean"], "ci": R[rd]["ci"].get("ci"), "halves": R[rd]["halves"],
                              "halves_n": R[rd]["halves_n"], "stress_mean": R[rd]["stress_mean"],
                              "stress_ci": R[rd]["stress_ci"].get("ci"), "spread_gross": R[rd]["spread_gross"],
                              "spread_net": R[rd]["spread_net"], "mean_excess_gross": _mean(res[rd]["st"]["ex_gross"]),
                              "turnover_mean": _mean(res[rd]["st"]["turnover_lal"]), "n_weeks": res[rd]["st"]["n_weeks"],
                              "low_spread_gross": _mean(res[rd]["st"]["low_spread"]),
                              "high_spread_gross": _mean(res[rd]["st"]["high_spread"])} for rd in R},
            "dsr": dinfo, "family_dsr_reported": fam, "other_phases_base": phases,
            "btc_eth_included_base": {"n": st_in["n_weeks"], "mean": _mean(st_in["ex"])},
            "y2022_base": {"n": int(y22.sum()), "mean": _mean(stb["ex"][y22])},
            "lal_size_median": float(np.median(stb["lal_size"])), "universe_size": [int(stb["univ_size"].min()),
                                                                                    float(np.median(stb["univ_size"])),
                                                                                    int(stb["univ_size"].max())],
            "n_products_main": M["n_products"], "criteria": crit_j, "verdict": v}
    B_, D_ = R["base"], R["dollar"]
    reason = (f"Low-activity losers (bottom quintile of the prior-week return within the bottom tercile of relative "
              f"volume) on the point-in-time Coinbase top 50 (T-546's exclusions, {M['n_products']} USD products incl. "
              f"dead ones), Sunday-close entries {stat['first']}..{stat['last']}, {n} weeks (universe "
              f"{stat['universe_size'][0]}-{stat['universe_size'][2]} names, median portfolio {stat['lal_size_median']:.0f}): "
              f"weekly excess net of 50 bp over the EW universe base-volume {_pc(B_['mean'], 3)} (CBB 95% CI "
              f"{_ci_txt(B_['ci'], fmt)}), dollar-volume {_pc(D_['mean'], 3)} (CI {_ci_txt(D_['ci'], fmt)}); halves "
              f"{_pc(B_['halves'][0], 3)} / {_pc(B_['halves'][1], 3)} (dollar {_pc(D_['halves'][0], 3)} / {_pc(D_['halves'][1], 3)}); "
              f"low- minus high-activity loser-minus-winner spread gross {_pc(B_['spread_gross']['mean'], 3)} (p "
              f"{_f(B_['spread_gross']['p'], 4)}), net {_pc(B_['spread_net']['mean'], 3)}; dollar {_pc(D_['spread_gross']['mean'], 3)} / "
              f"{_pc(D_['spread_net']['mean'], 3)}; 100 bp stress {_pc(B_['stress_mean'], 3)} / {_pc(D_['stress_mean'], 3)}; "
              f"DSR bound {_f(dinfo['base'].get('dsr_bound'))} at 26 trials. Reported: gross excess "
              f"{_pc(stat['readings']['base']['mean_excess_gross'], 3)}; 2022 {_pc(stat['y2022_base']['mean'], 3)} "
              f"({stat['y2022_base']['n']} weeks); BTC/ETH kept {_pc(stat['btc_eth_included_base']['mean'], 3)}; other entry "
              f"weekdays " + ", ".join(f"{k} {_pc(x['mean'], 3)}" for k, x in phases.items())
              + "; family DSR with T-314's recorded Sharpes " + _f(fam.get("dsr")) + ". Seen data: T-546 used these "
              "2019-2026 candles under another conditional")
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {
    "b13_volume_b_volume_cv": b13_volume_b_volume_cv,
    "b13_volume_b_confirmed_high": b13_volume_b_confirmed_high,
    "b13_volume_b_rvol_momentum": b13_volume_b_rvol_momentum,
    "b13_volume_b_same_slot": b13_volume_b_same_slot,
    "b13_volume_b_crypto_lal": b13_volume_b_crypto_lal,
}
THEORY_MAP = {
    "T-695": "b13_volume_b_volume_cv",
    "T-697": "b13_volume_b_confirmed_high",
    "T-699": "b13_volume_b_rvol_momentum",
    "T-700": "b13_volume_b_same_slot",
    "T-702": "b13_volume_b_crypto_lal",
}
