"""
Batch 13, group ``crossasset_a``: five cross-asset claims pre-registered from the 2026-10-20 web sweep (cluster
"crossasset"): short-term momentum in high-turnover large caps (T-603), dollar carry on the average forward discount
(T-605), oil and the gold/platinum ratio as equity-premium predictors (T-598, T-600) and the within-industry
leader-follower lead-lag (T-596).
=====================================================================================================================

  * T-603  Point-in-time S&P 500 non-financial members (fja05680 + later Wikipedia changes, SEC SIC 6000-6999 excluded)
           with a usable Yahoo price and SEC shares (dei EntityCommonStockSharesOutstanding, else us-gaap
           CommonStockSharesOutstanding, available before the decision and at most 400 days old, times the daily-events
           split factor after the fact's date). Independent 2x2 sorts at the cross-sectional medians of month-t return
           and month-t share turnover (sum of Yahoo volume / adjusted shares); value-weighted (close x adjusted shares)
           long high-turnover winners, short high-turnover losers; 5 bp per side on actual weight changes. Trial (a):
           full-month formation, filled at the first session close of t+1, held to the first close of t+2 (primary).
           Trial (b): formation skipping the month's last 3 sessions, filled at the month-end close. Holding months
           2019-01..2026-09. Pass: net mean > 0 with one-sided p < 0.05 (Newey-West lag 3 AND the studentized block
           bootstrap with 6-month blocks, rule 11), both halves (2019-01..2022-10, 2022-11..2026-09) positive, FF5+UMD
           alpha > 0 (holds ending by 2026-08-31), above the 95th percentile of the shuffled-turnover placebo (1,000
           draws), DSR > 0.95 over the 2 trials. Pre-registered verdict map: a positive net mean with p >= 0.05 is
           inconclusive (power); a net mean <= 0 is not_supported. min_n 90 months.
  * T-605  Equal-weight basket of the 9 non-USD G10 currencies vs USD (FRED noon rates). AFD = mean foreign OECD
           3-month rate minus the US rate, month t-1 averages at the end of month t; long the basket when AFD > 0,
           short otherwise, filled at the first common noon fixing of t+1 and held to the first fixing of t+2; monthly
           return = sign x (mean basket spot change + AFD / 12). Holding months 2011-01..2026-09. Pass (primary G10):
           net Sharpe > 0.3, stationary-bootstrap (mean block 12, 5,000 draws) lower 95% bound > 0, both halves
           (2011-2018, 2019-2026) positive, above the 95th percentile of the regime-preserving shuffled-sign placebo
           (spells of the sign series shuffled in time, 1,000 draws) and DSR > 0.95 over 12 trials (these 2 plus T-368's
           6 and T-431's 4, whose family Sharpes are recomputed through ``batch5_fx``). Second trial: G10 + MXN + ZAR.
           min_n 150 months.
  * T-598  Oil month t = the sum of CL=F daily log changes over the month, roll-window days and changes touching a
           non-positive print excluded. Target: SPY adjclose return from the first session close of t+1 to the first
           session close of t+2 minus DTB3. Expanding OLS from oil month 2000-09; forecasts for target months
           2010-01..2026-09 against the expanding historical mean. Pass: R2_OS > 0, Clark-West one-sided p < 0.05, slope
           NW t < -1.65, R2_OS > 0 in 2010-2017 and 2018-2026, a long-SPY-or-bills switching rule (2 bp per switch) with
           a Sharpe above the historical-mean rule's (paired studentized block bootstrap, 12-month blocks, lower 95%
           bound > 0), and the joint-family DSR > 0.95. Trial 2 (fred-DCOILWTICO) is not archived. min_n 180.
  * T-600  GC=F and PL=F daily log changes, roll-window days masked, chained into level indices; log GP(t) = log mean
           gold index over month t - log mean platinum index over month t; predictor Delta log GP(t). Same target, fill
           and benchmark as T-598; forecasts for target months 2014-01..2026-09. Pass: R2_OS > 0, CW p < 0.05, slope NW
           t > 1.65, R2_OS > 0 in 2014-2019 and 2020-2026, the switching rule beating the historical mean (paired lower
           bound > 0), joint-family DSR > 0.95. The level trial is inconclusive by the pre-declared range rule (reported
           only), as are the 12-month horizon and the GLD/PPLT cross-check. min_n 150.
  * T-596  Weekly within 2-digit-SIC industries of point-in-time S&P 500 members with >= 6 usable names: leaders = the
           top tercile by trailing 60-session mean dollar volume (dollar-volume weighted, Friday-to-Friday return),
           followers = the bottom tercile (equal weight). Fama-MacBeth across industries each week of the followers'
           next-week return (Monday open to Friday close) on the leaders' week-t return, controlling for the followers'
           own week-t return (SPY's week-t return is common to every industry in a week, so the weekly intercept
           absorbs it exactly; a pooled regression with it is reported). Cross-industry quintile long-short of
           followers on the leader return, 5 bp per side plus half the trailing 20-session Corwin-Schultz spread.
           Target weeks 2002-01..2026-09. Pass: FM slope one-sided p < 0.05, net long-short mean > 0 with one-sided
           p < 0.05 (HAC t AND the 8-week block bootstrap), both halves (2002-2013, 2014-2026) positive, above the 95th
           percentile of the random-other-industry-leader placebo, and the DSR with T-424 and T-467 counted. min_n
           1,000 weeks.

Readings fixed before any run (the registrations are silent or ambiguous; each is the conservative one and is listed
in the reason):
  * Point in time. A daily bar is known at its close; Yahoo futures bars are stamped 04:00 UTC with the session date
    and available 24 h later, so a month's oil / metal statistic is complete after the month's last session and is
    traded at the NEXT SPY close (the first session of the next month). FRED DTB3 is the print dated strictly before
    the fill day (``batch6c_cal.Bills``), accrued over the hold's calendar days. The expanding fits at the end of
    month t use only pairs whose target ended by then (predictor months <= t - 2: the pair of month t - 1 ends at the
    first close of month t + 1). OECD monthly averages are taken with a one-month lag (month t-1 at the end of t; the
    bundle's same-month available_at is not trusted). SEC shares enter at their available_at (min of acceptance and
    the filing date's 22:00 ET) and must be available at the decision close (16:00 ET).
  * T-598 roll mask: "T-468's roll-window days" are read as T-468's windows for the CL contract (the series is CL=F;
    T-468 also masked Brent's windows because it traded the BZ-CL spread). T-468 itself left '+-5' ambiguous between
    sessions and calendar days, so every T-598 criterion is judged under both readings (rule 11: passes only when both
    pass, fails only when both fail). The literal CL+BZ mask (77% of sessions) is reported only. A daily change is also
    excluded when either of its closes is non-positive (2020-04-20) - the change is never bridged across the gap.
  * T-600 roll mask: the house metals convention (``batch6c_misc.roll_flags``: +-2 sessions around the last session
    before each active month's first notice day; GC Feb/Apr/Jun/Aug/Oct/Dec, PL Jan/Apr/Jul/Oct). Checked on the
    predictor data only (no outcome read): Yahoo's continuous volume jumps 2 sessions before first notice, inside the
    window. "Slope NW t" (T-598, T-600) is judged on the evaluation window's pairs AND on every pair from 2000-09 (rule
    11); Newey-West lag floor(4 (n/100)^(2/9)). CW p: the Newey-West (lag 12) normal p AND the studentized circular
    block bootstrap (12-month blocks) of the CW series, both < 0.05. "First forecast 2010-01 / 2014-01" is the first
    TARGET month.
  * Joint-family DSR (T-598, T-600) and T-596's DSR: the other family members' Sharpes are not computed here, so
    ``dsr bound``: the DSR at the most favourable trial-Sharpe variance (the 1/(T-1) floor) and the smallest trial
    count the registration admits (T-598/T-600: 2 own trials + the 4 named theories = 6; T-596: itself + T-424 + T-467
    = 3) fails the criterion when it misses 0.95 (decisive when PSR vs 0 <= 0.05) and leaves it undecided otherwise,
    so these three can be refuted but not supported here. The full counts (15; 1 + 14 + 4 = 19) are reported. For
    T-598 and T-600 the DSR is judged on two series (rule 11, the ``batch13_implied_b`` precedent): the switching rule's
    monthly excess return and the switching rule minus the historical-mean rule (the active return the predictor
    adds); a raw-excess DSR alone mostly measures the equity premium. (This second series was added after T-598's first
    run; it can only make the criterion harder to pass, and T-598's other criteria already failed under both readings.)
  * T-605 costs: "2 bps per leg per rebalance plus 1 bp a month roll" read as every leg re-established at each
    monthly rebalance (2 bp on the gross, 2 bp more to close the old side on a sign flip, the final close charged) plus
    1 bp roll: the most expensive reading; the traded-notional reading (2 bp on drift-adjusted |weight change|) is
    reported. The basket fixes on the first day of the month on which every basket currency prints. Rates
    forward-filled after a series' last print (EUR, GBP after 2026-01; JPY after 2026-07; at most 12 months, as T-368)
    are flagged, and the Sharpe through 2026-01 is reported. "Both halves positive" = the net mean of each half > 0.
    The placebo keeps each spell's length and sign, shuffles their order and recomputes carry and costs.
  * T-603: membership = fja05680 snapshots with Wikipedia changes after fja's last date (T-473's construction) at the
    decision session; T-473's reused-ticker filters (Yahoo meta EQUITY; a removed member's Wikipedia removal name must
    match a name the instrument carried). SIC is the current SEC profile; a name without a SIC is dropped. Multi-class
    issuers: the archived companyfacts carry no per-class dei counts (dimensioned facts are not in the API, and the
    bundle keeps one value per accession and cover date), so "sum the class counts when dei reports per class" can
    never apply and every issuer with two or more S&P member tickers (GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA, ...)
    is dropped (flagged). Formation needs a bar at both ends and a finite volume on every formation session; a name
    with no bar at the fill earns 0 (unfilled). Ties at a median join neither side. Costs: 5 bp x sum |w_new - drifted
    w_old| over both legs, the first entry and the final exit charged. The placebo permutes each stock's turnover
    across its eligible test-window months. FF5 and UMD daily factors are compounded over each hold. The trial (a)
    book is the claim's; trial (b) enters the DSR (2 trials, ``batch6c_mom.family_dsr``).
  * T-596: membership as T-603 at the Friday close (the week's last session); industry = the current 2-digit SIC
    (flagged); dollar volume needs 60 finite sessions; terciles = floor(n/3) names in each tail; quintiles =
    floor(n_ind/5) industries in each tail, each leg equal-weighted across its follower stocks; a follower with no bar
    at Monday's open is not entered; a series ending inside the week earns its return to the last bar. FM needs >= 5
    industries in a week. The placebo gives each industry the leader return of another industry (a random cyclic
    derangement, 1,000 draws) and must be beaten by BOTH the FM slope mean and the long-short net mean; "both halves
    positive" is likewise judged on both. The size split (dei shares, 2011+) is reported; the sector-SPDR 5-minute
    report is not computed (reported-only item, no bearing on the verdict).
  * Survivorship: T-603 and T-596 draw prices from the archive's 901-symbol daily-history set, which is TODAY's
    universe: removed, acquired and renamed members are under-represented (the share of member-months / member-weeks
    without a usable price is reported); SEC CIKs come from the current ticker map, so delisted names have no shares.
  * Below trial.min_n the verdict is never supported and a failing criterion counts only when decisive
    (``batch6c_cal._judge``, house rule 5). House rule 10: every claim here names a calendar (month-ends, ISO weeks),
    so there is no free grid phase.
"""

from __future__ import annotations

import bisect
import math
import warnings
from collections import defaultdict
from datetime import date
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch5_fx as FX
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_misc as MISC
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch6c_pairs as PAIRS
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch4_ohlc import corwin_schultz
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_rates import hac_mean
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
N_PLACEBO = 1000

SPY_B = "daily-history-SPY"
DTB3_B = "fred-DTB3"
CL_B = "daily-history-CL-F"
BZ_B = "daily-history-BZ-F"
GC_B = "daily-history-GC-F"
PL_B = "daily-history-PL-F"
GLD_B = "daily-history-GLD"
PPLT_B = "daily-history-PPLT"
WTI_SPOT_B = "fred-DCOILWTICO"
FX_SPOT_B = "fx-spot-g10"
FX_RATE_B = "fx-rates-3m"
FJA_B = "fja-sp500-components"
SPELLS_B = "fja-sp500-ticker-spells"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
SEC_TICK_B = "sec-company-tickers"
FACTS_PREFIX = "sec-companyfacts-"
SUBS_PREFIX = "sec-submissions-"

# ---------------------------------------------------------------------------------------------------- T-605 --
T605_G10 = ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")
T605_EM = ("MXN", "ZAR")
T605_FIRST, T605_LAST = "2011-01", "2026-09"          # holding months
T605_PRE_FIRST = "1999-02"
T605_SPLIT = "2019-01"
T605_LEG = 2e-4
T605_ROLL = 1e-4
T605_SR_BAR = 0.3
T605_MEAN_BLOCK = 12.0
T605_NBOOT = 5000
T605_REPS = 5
T605_MIN_N = 150
T605_N_TRIALS = 12                                   # 2 + T-368's 6 + T-431's 4
T605_STALE_THROUGH = "2026-01"
T605_FILL_TO = "2026-08"

# -------------------------------------------------------------------------------------------- T-598 / T-600 --
EP_TRAIN_FROM = "2000-09"
EP_GAP = 2                       # a pair of predictor month j is realised at the first close of month j + 2
EP_MIN_TRAIN = 24
EP_BLOCK = 12
EP_CW_LAG = 12
EP_SWITCH = 2e-4
EP_T_BAR = 1.65
T598_FIRST_TARGET, T598_LAST_TARGET = "2010-01", "2026-09"
T598_SPLIT = "2018-01"
T598_MIN_N = 180
T598_ROLL_WIN = 5
T598_READINGS = (("CL windows +-5 sessions", "sessions"), ("CL windows +-5 calendar days", "days"))
T598_FAMILY_MIN, T598_FAMILY_FULL = 6, 15
T600_FIRST_TARGET, T600_LAST_TARGET = "2014-01", "2026-09"
T600_SPLIT = "2020-01"
T600_MIN_N = 150
T600_GC_MONTHS = MISC.GC_MONTHS
T600_PL_MONTHS = (1, 4, 7, 10)
T600_ROLL_WIN = 2
T600_RANGE_SPLIT = "2014-01"
T600_RANGE_RULE = 0.5
T600_FAMILY_MIN, T600_FAMILY_FULL = 6, 15

# ---------------------------------------------------------------------------------------------------- T-603 --
XS_START = "2000-06-01"
T603_FIRST, T603_LAST = "2019-01", "2026-09"          # holding months
T603_PRE = ("2010-01", "2018-12")
T603_SPLIT = "2022-11"
T603_COST = 5e-4
T603_NW_LAG = 3
T603_BLOCK = 6
T603_MIN_N = 90
T603_MAX_AGE = 400
T603_SKIP = 3
T603_FF_END = "2026-08-31"

# ---------------------------------------------------------------------------------------------------- T-596 --
T596_FIRST, T596_LAST = "2002-01-01", "2026-09-30"   # target (follower) weeks by their last session
T596_SPLIT = "2014-01-01"
T596_MIN_IND = 6
T596_MIN_FM = 5
T596_DV_WIN = 60
T596_CS_WIN = 20
T596_COST = 5e-4
T596_BLOCK = 8
T596_MIN_N = 1000
T596_SIZE_FROM = "2011-01-01"
T596_FAMILY_MIN, T596_FAMILY_FULL = 3, 19


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


def _t1(reg) -> Optional[float]:
    """The first slope's t of an ``ols_nw_all`` result (None when absent)."""
    t = (reg or {}).get("t")
    return t[1] if t else None


def _mi(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def madd(m: str, k: int) -> str:
    return _ms(_mi(m) + k)


def mrange(a: str, b: str) -> list:
    return [_ms(i) for i in range(_mi(a), _mi(b) + 1)]


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


def _nw(x, lag: int) -> dict:
    return hac_mean(np.asarray(x, float), lag)


def p_rows(point, d, block: int, nw_lag: int, label: str, n_boot: Optional[int] = None) -> tuple:
    """'mean > 0 with one-sided p < 0.05' under the two constructions the trial names (Newey-West t and the
    studentized circular block bootstrap; rule 11): (row, info). Decisive failure: the mirror one-sided test rejects
    at 5% under both."""
    d = np.asarray(d, float)
    nw = _nw(d, nw_lag)
    pg, pl, dr = CAL.studentized_p_escalated(d, block, n_boot, SEED, CAL.N_SEEDS)
    if point is None or not np.isfinite(point):
        return (f"{label} (n/a)", None, False), {"nw": nw, "boot_p": pg, "boot_p_lt": pl, "draws": dr}
    nw_ok = None if nw.get("p") is None else bool(point > 0 and nw["p"] < ALPHA)
    bs_ok = False if not point > 0 else CAL.decide_p(pg, dr)
    rows = [(f"Newey-West (lag {nw_lag}) t {_s(nw.get('t'), 2)}, p {_f(nw.get('p'), 4)}", nw_ok,
             nw.get("t") is not None and nw["t"] < -1.645),
            (f"studentized block bootstrap ({block}) p {CAL._mc(pg, dr)}", bs_ok, CAL.decide_p(pl, dr) is True)]
    return BW.all_constructions(rows, label), {"nw": nw, "boot_p": pg, "boot_p_lt": pl, "draws": dr}


def dsr_bound(x, n_min: int, n_full: int, label: str) -> tuple:
    """DSR criterion when the family's other Sharpes are not computed here: the most favourable trial-Sharpe variance
    (the 1/(T-1) floor) at the smallest admissible trial count bounds the DSR from above. Fails when that bound misses
    0.95 (decisive when PSR vs 0 <= 0.05); undecided otherwise. Returns (row, info)."""
    x = np.asarray(x, float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    hi = float(deflated_sharpe_ratio(x, n_trials=n_min, var_trials_sr=floor))
    full = float(deflated_sharpe_ratio(x, n_trials=n_full, var_trials_sr=floor))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_bound": hi, "dsr_full_count_floor": full, "n_min": n_min, "n_full": n_full, "var_floor": floor,
            "psr0": psr0, "sharpe_pp": float(sharpe_ratio(x))}
    txt = (f"{label} (at most {hi:.3f} at {n_min} trials and the 1/(T-1) floor; {full:.3f} at the full {n_full}; "
           f"PSR vs 0 {psr0:.3f})")
    if hi <= DSR_PASS:
        return (txt + " [fails whatever the uncomputed family Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + " [the other family Sharpes are not computed here: cannot pass]", None, False), info


def dsr_two(R: dict, n_min: int, n_full: int, tag: str) -> tuple:
    """The DSR criterion judged on two series (rule 11, as ``batch13_implied_b``): the switching rule's monthly excess
    return and the switching rule minus the historical-mean rule (the active return the predictor adds)."""
    if R.get("switch") is None:
        return [(f"{tag} DSR (too few forecasts)".strip(), None, False)], {}
    a, b = np.asarray(R["switch"], float), np.asarray(R["bench"], float)
    r1, i1 = dsr_bound(a, n_min, n_full, f"{tag} switching-rule excess return".strip())
    r2, i2 = dsr_bound(a - b, n_min, n_full, f"{tag} switching rule minus the historical-mean rule".strip())
    return [r1, r2], {"excess": i1, "active": i2}


def sharpe_diff(a, b, block: int = EP_BLOCK, ppy: int = 12) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return BW.mc_escalate(lambda seed: BW.sharpe_diff_test(a, b, ppy, block, None, seed),
                          lambda t: BW._ci_crit(t, "gt", 0.0, "")[1], None, SEED)


# ====================================================================================================== T-605 ==

def afd_at(rates: dict, ccys: Sequence[str], decision_month: str) -> Optional[float]:
    """AFD known at the end of ``decision_month``: mean foreign 3-month rate minus the US rate, both the month BEFORE
    the decision month (percent); None when any rate is missing."""
    m = madd(decision_month, -1)
    us = rates.get("USD", {}).get(m)
    vals = [rates.get(c, {}).get(m) for c in ccys]
    if us is None or any(v is None for v in vals):
        return None
    return float(np.mean(vals)) - float(us)


def common_first_fixings(daily: dict, ccys: Sequence[str]) -> dict:
    """{month: first day of the month on which every currency in ``ccys`` has a noon fixing}."""
    sets = [set(daily[c][0]) for c in ccys if c in daily]
    if len(sets) < len(ccys):
        return {}
    first = {}
    for d in sorted(set.intersection(*sets)):
        first.setdefault(d[:7], d)
    return first


def t605_book(panel: dict, ccys: Sequence[str], first: str, last: str) -> dict:
    """Holding months H in [first, last]: sign decided at the end of H-1 on AFD(H-2 rates), filled at the first common
    fixing of H, closed at the first common fixing of H+1. Months without every rate or fixing are skipped (listed)."""
    daily = panel["daily"]
    fix = common_first_fixings(daily, ccys)
    val = {c: dict(zip(daily[c][0], daily[c][1])) for c in ccys}
    filled = panel.get("filled", {})
    rows, skipped = [], []
    for H in mrange(first, last):
        a = afd_at(panel["rates"], ccys, madd(H, -1))
        d0, d1 = fix.get(H), fix.get(madd(H, 1))
        if a is None or d0 is None or d1 is None:
            skipped.append(H)
            continue
        r = np.array([val[c][d1] / val[c][d0] - 1.0 for c in ccys])
        rate_m = madd(H, -2)
        stale = sorted(c for c in list(ccys) + ["USD"] if rate_m in filled.get(c, []))
        rows.append({"H": H, "fill": d0, "exit": d1, "afd": a, "sign": 1.0 if a > 0 else -1.0, "r": r, "stale": stale})
    return {"rows": rows, "skipped": skipped}


def t605_returns(rows: list, signs=None) -> dict:
    """Gross and net monthly returns of the dollar-carry book for ``signs`` (default: the rule's). Net under the declared
    every-leg cost reading and, reported, the traded-notional reading."""
    n = len(rows)
    if n == 0:
        return {"gross": np.zeros(0), "net": np.zeros(0), "net_traded": np.zeros(0), "spot": np.zeros(0), "carry": np.zeros(0)}
    s = np.array([r["sign"] for r in rows]) if signs is None else np.asarray(signs, float)
    spot = np.array([float(np.mean(r["r"])) for r in rows])
    afd = np.array([r["afd"] for r in rows]) / 1200.0
    carry = s * afd
    gross = s * spot + carry
    flip = np.r_[0.0, (s[1:] != s[:-1]).astype(float)]
    cost = T605_LEG * (1.0 + flip) + T605_ROLL
    cost[-1] += T605_LEG                                        # the final close
    net = gross - cost
    # traded-notional reading (reported): 2 bp on drift-adjusted |weight change| + 1 bp roll
    tn = np.zeros(n)
    prev = None
    for k, r in enumerate(rows):
        m = r["r"].size
        w = np.full(m, s[k] / m)
        if prev is None:
            tn[k] = np.abs(w).sum()
        else:
            tn[k] = np.abs(w - prev).sum()
        prev = w * (1.0 + r["r"]) / (1.0 + float(np.mean(r["r"])))
    net_traded = gross - (T605_LEG * tn + T605_ROLL)
    net_traded[-1] -= T605_LEG * np.abs(prev).sum()
    return {"gross": gross, "net": net, "net_traded": net_traded, "spot": s * spot, "carry": carry, "sign": s}


def spell_shuffle(sign, n_draws: int, rng) -> np.ndarray:
    """(n_draws, n) sign paths: the maximal constant-sign spells of ``sign`` (lengths and signs kept) in random order."""
    s = np.asarray(sign, float)
    cuts = np.flatnonzero(np.r_[True, s[1:] != s[:-1]])
    spells = [(float(s[a]), int(b - a)) for a, b in zip(cuts, np.r_[cuts[1:], s.size])]
    out = np.empty((n_draws, s.size))
    for k in range(n_draws):
        order = rng.permutation(len(spells))
        out[k] = np.concatenate([np.full(spells[i][1], spells[i][0]) for i in order])
    return out


def _sb_sharpe(x, reps: int = T605_REPS) -> dict:
    """Stationary-bootstrap (mean block 12) 95% interval of the annualised Sharpe, ends averaged over ``reps`` seeds
    (5,000 draws each) with their Monte Carlo s.e."""
    los, his = [], []
    for k in range(reps):
        b = FX.stationary_boot_sharpe(x, 12, T605_MEAN_BLOCK, T605_NBOOT, SEED + k)
        los.append(float(np.quantile(b, 0.025)))
        his.append(float(np.quantile(b, 0.975)))
    return {"ci": [float(np.mean(los)), float(np.mean(his))],
            "ci_mc_se": [float(np.std(los, ddof=1) / math.sqrt(reps)), float(np.std(his, ddof=1) / math.sqrt(reps))]}


def t605_family_sharpes(archive, panel: dict) -> dict:
    """Per-period Sharpes of T-368's 6 and T-431's 4 declared trials, recomputed through ``batch5_fx`` on their own test
    window (the DSR family of T-605)."""
    vix = FX._vix(archive)
    test = FX.mrange(*FX.CARRY_TEST)
    cb, ad = FX.g10_costs()
    sel = FX.choose_weighting(panel, FX.G10, FX.CARRY_TRAIN, cb, ad, vix=vix)
    g = FX.g10_family(panel, sel["chosen"], test, vix)
    cbe, ade = FX.em_costs()
    sele = FX.choose_weighting(panel, list(FX.G10) + list(FX.EM), FX.CARRY_TRAIN, cbe, ade, vix=vix)
    e = FX.em_family(panel, sele["chosen"], test, vix)
    out = {}
    for pre, fam in (("T-368:", g), ("T-431:", e)):
        for k, v in fam.items():
            out[pre + k] = float(sharpe_ratio(v)) if v is not None and np.asarray(v).size > 2 else None
    return {"sharpes": out, "t368_base": g.get("base"), "t368_months": test}


def b13_crossasset_a_dollar_carry(archive):
    """T-605."""
    miss = _missing(archive, [FX_SPOT_B, FX_RATE_B, DTB3_B, SPY_B])
    if miss:
        return miss
    panel = FX._panel(archive, T605_FILL_TO)
    trials = {"G10": T605_G10, "G10+MXN+ZAR": T605_G10 + T605_EM}
    books = {k: t605_book(panel, c, T605_FIRST, T605_LAST) for k, c in trials.items()}
    R = {k: t605_returns(b["rows"]) for k, b in books.items()}
    rows = books["G10"]["rows"]
    net, gross = R["G10"]["net"], R["G10"]["gross"]
    n = int(net.size)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} holding months with every rate and fixing")
    months = [r["H"] for r in rows]
    sr = float(sharpe_ratio(net, 12))
    sb = _sb_sharpe(net)
    lo_ok, lo_note = BW.resolve(sb["ci"][0], sb["ci_mc_se"][0], 0.0, "gt")
    h1 = np.array([m < T605_SPLIT for m in months])
    halves = [float(net[h1].mean()), float(net[~h1].mean())]
    rng = np.random.default_rng(SEED)
    sign = R["G10"]["sign"]
    paths = spell_shuffle(sign, N_PLACEBO, rng)
    plac = np.array([t605_returns(rows, p)["net"].mean() for p in paths])
    p95 = float(np.percentile(plac, 95))
    n_distinct = int(np.unique(np.round(plac, 12)).size)
    fam = t605_family_sharpes(archive, panel)
    own = {k: float(sharpe_ratio(v["net"])) for k, v in R.items() if v["net"].size > 2}
    fam_sr = list(own.values()) + [s for s in fam["sharpes"].values() if s is not None]
    d = MOM.family_dsr(net, fam_sr, T605_N_TRIALS)
    n_reg = int(1 + np.sum(sign[1:] != sign[:-1]))
    crit = [(f"G10 net Sharpe {sr:.3f} > {T605_SR_BAR}", sr > T605_SR_BAR,
             sb["ci"][1] <= T605_SR_BAR),
            (f"stationary-bootstrap 95% lower bound {sb['ci'][0]:+.3f} > 0{lo_note}", lo_ok, sb["ci"][1] <= 0.0),
            (f"both halves positive (2011-2018 {_pc(halves[0], 3)}/month, 2019-2026 {_pc(halves[1], 3)}/month)",
             all(h > 0 for h in halves), False),
            (f"net mean {_pc(net.mean(), 3)}/month above the shuffled-sign placebo's 95th percentile {_pc(p95, 3)} "
             f"({N_PLACEBO} spell shuffles; {n_reg} sign regimes, so {n_distinct} distinct placebo orderings)",
             bool(net.mean() > p95), False),
            MOM.dsr_row(d, f"DSR > {DSR_PASS} at {T605_N_TRIALS} trials (2 own + T-368's 6 + T-431's 4)")]
    v, why, crit_j = CAL._judge(crit, n, T605_MIN_N, "holding months")
    # ---- reported
    spy_d, spy_a = CAL._daily(archive, SPY_B, "adjclose")
    spy_at = lambda day: spy_a[bisect.bisect_right(spy_d, day) - 1]
    spy_r = np.array([spy_at(r["exit"]) / spy_at(r["fill"]) - 1.0 for r in rows])
    corr_spy = float(np.corrcoef(net, spy_r)[0, 1])
    t368 = fam.get("t368_base")
    corr_368 = None
    if t368 is not None:
        m368 = dict(zip(fam["t368_months"], np.asarray(t368, float)))
        pairs = [(x, m368[m]) for m, x in zip(months, net) if m in m368]
        if len(pairs) > 10:
            a_, b_ = np.array(pairs).T
            corr_368 = float(np.corrcoef(a_, b_)[0, 1])
    always = {}
    for nm, sgn in (("always long USD", -1.0), ("always short USD", 1.0)):
        x = t605_returns(rows, np.full(n, sgn))["net"]
        always[nm] = {"sharpe": float(sharpe_ratio(x, 12)), "mean_pct": float(x.mean() * 100)}
    stale_m = [r["H"] for r in rows if r["stale"]]
    thr = np.array([m <= T605_STALE_THROUGH for m in months])
    sr_thr = float(sharpe_ratio(net[thr], 12)) if thr.sum() > 2 else None
    pre = t605_book(panel, T605_G10, T605_PRE_FIRST, madd(T605_FIRST, -1))
    pre_net = t605_returns(pre["rows"])["net"]
    em = R["G10+MXN+ZAR"]
    em_sr = float(sharpe_ratio(em["net"], 12)) if em["net"].size > 2 else None
    carry_share = float(R["G10"]["carry"].mean() / gross.mean()) if gross.mean() != 0 else None
    nw6 = FX.nw_tstat(net, 6)
    stat = {"n": n, "first": months[0], "last": months[-1], "skipped": books["G10"]["skipped"], "sharpe": sr,
            "sb_ci": sb["ci"], "sb_ci_mc_se": sb["ci_mc_se"], "mean_pct_month": float(net.mean() * 100),
            "gross_sharpe": float(sharpe_ratio(gross, 12)), "halves_mean": halves, "nw6_t": nw6,
            "hac_t_auto": _nw(net, CAL.nw_lags(n))["t"], "skew": FX.skewness(net), "mdd": FX._mdd(net) if hasattr(FX, "_mdd") else None,
            "placebo_p95": p95, "placebo_mean": float(plac.mean()), "placebo_pct_rank": float(np.mean(plac < net.mean())),
            "placebo_distinct_values": n_distinct,
            "n_regimes": n_reg, "share_long_basket": float(np.mean(sign > 0)), "carry_share": carry_share,
            "net_traded_reading_sharpe": float(sharpe_ratio(R["G10"]["net_traded"], 12)),
            "dsr": d, "own_sharpes_pp": own, "family_sharpes_pp": fam["sharpes"],
            "trial2_sharpe": em_sr, "trial2_n": int(em["net"].size), "corr_spy": corr_spy, "corr_t368": corr_368,
            "baselines": always, "stale_rate_months": stale_m, "sharpe_through_2026_01": sr_thr,
            "pre_2011": {"n": int(pre_net.size), "first": pre["rows"][0]["H"] if pre["rows"] else None,
                         "sharpe": float(sharpe_ratio(pre_net, 12)) if pre_net.size > 2 else None},
            "criteria": crit_j, "verdict": v}
    mdd = stat["mdd"]
    reason = (f"dollar carry on the AFD sign, equal-weight G10 basket vs USD, holding months {months[0]}..{months[-1]} "
              f"({n}; first common noon fixing of each month, sign from month t-1 OECD averages at the end of t): net "
              f"Sharpe {sr:.3f} (gross {stat['gross_sharpe']:.3f}), stationary-bootstrap 95% CI [{sb['ci'][0]:+.3f}, "
              f"{sb['ci'][1]:+.3f}], mean {_pc(net.mean(), 3)}/month (HAC t {_s(nw6, 2)}), skew {_s(stat['skew'], 2)}, "
              f"max drawdown {_pc(mdd, 1) if mdd is not None else 'n/a'}; halves {_pc(halves[0], 3)} / {_pc(halves[1], 3)}; "
              f"{n_reg} sign regimes, long the basket in {np.mean(sign > 0) * 100:.0f}% of months; carry share of the gross "
              f"mean {_f(carry_share, 2)}; placebo 95th pct {_pc(p95, 3)} (with {n_reg} regimes the spell shuffle has only "
              f"{n_distinct} distinct orderings, the rule's own among them, so it cannot be beaten strictly: the effective "
              f"sample is {n_reg} regime bets); DSR {_f(d.get('dsr'))} at {T605_N_TRIALS} trials. "
              f"Reported: trial 2 (G10 + MXN + ZAR) Sharpe {_f(em_sr)}; always long USD Sharpe "
              f"{always['always long USD']['sharpe']:+.3f}, always short USD {always['always short USD']['sharpe']:+.3f}; "
              f"correlation with SPY {corr_spy:+.2f}, with T-368's base book {_s(corr_368, 2)}; traded-notional cost reading "
              f"Sharpe {stat['net_traded_reading_sharpe']:.3f}; stale (forward-filled) rates enter {len(stale_m)} months "
              f"({stale_m[0] + '..' + stale_m[-1] if stale_m else 'none'}), Sharpe through {T605_STALE_THROUGH} {_f(sr_thr)}; "
              f"{pre['rows'][0]['H'] if pre['rows'] else 'n/a'}..2010-12 (reported only) Sharpe {_f(stat['pre_2011']['sharpe'])}. "
              f"Caveat: IR3TIB differentials are not the futures-implied forward discount after 2008 (CIP basis), so the "
              f"carry accrual is approximate; costs read as every leg re-established monthly (2 bp, 4 bp on a flip, final "
              f"close) plus 1 bp roll")
    return _out(stat, n, v, reason + " — " + why)


# ============================================================================================= T-598 / T-600 ==

def log_changes(close, mask=None) -> np.ndarray:
    """Daily log changes c_i / c_{i-1} (NaN at 0, where either close is non-positive or non-finite, and where ``mask``)."""
    c = np.asarray(close, float)
    ch = np.full(c.size, np.nan)
    if c.size > 1:
        a, b = c[:-1], c[1:]
        ok = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ch[1:] = np.where(ok, np.log(np.where(ok, b, 1.0) / np.where(ok, a, 1.0)), np.nan)
    if mask is not None:
        ch[np.asarray(mask, bool)] = np.nan
    return ch


def monthly_sum(days: Sequence[str], ch) -> dict:
    """{month: sum of the finite daily changes of that month's sessions} (NaN when none is finite)."""
    by = defaultdict(list)
    for d, x in zip(days, ch):
        by[d[:7]].append(x)
    out = {}
    for m, xs in by.items():
        a = np.asarray(xs, float)
        out[m] = float(np.nansum(a)) if np.isfinite(a).any() else float("nan")
    return out


def chained_monthly_mean(days: Sequence[str], close, mask) -> dict:
    """{month: mean of the chained level index over the month's sessions}; the index chains the unmasked daily log
    changes (a masked or invalid day leaves the index flat)."""
    ch = log_changes(close, mask)
    lvl = np.exp(np.cumsum(np.nan_to_num(ch, nan=0.0)))
    by = defaultdict(list)
    for d, x in zip(days, lvl):
        by[d[:7]].append(x)
    return {m: float(np.mean(v)) for m, v in by.items()}


def complete_months(days: Sequence[str]) -> set:
    """Months strictly after the series' first month and strictly before its last (the first and last months may be
    partial)."""
    ms = sorted({d[:7] for d in days})
    return set(ms[1:-1])


def spy_targets(spy_days: Sequence[str], spy_adj, bills, months: Sequence[str]) -> dict:
    """{predictor month t: (y, fill day, exit day)}: SPY adjclose simple return from the first session close of t+1 to
    the first session close of t+2, minus the bill return at the DTB3 rate known on the fill day."""
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


def expanding_oos(x, y, k0: int, k1: int, train0: int = 0, gap: int = EP_GAP, min_train: int = EP_MIN_TRAIN) -> dict:
    """Expanding one-regressor OLS forecasts of y_k from x_k for k in [k0, k1] (monthly positions): the fit uses the
    pairs j in [train0, k - gap] with finite x and y, the benchmark is their mean. Returns positions, y, forecasts and
    the fitted slope at each origin."""
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


def cw_series(y, fb, fm) -> np.ndarray:
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    return (y - fb) ** 2 - ((y - fm) ** 2 - (fb - fm) ** 2)


def r2_os(y, fb, fm) -> Optional[float]:
    y, fb, fm = (np.asarray(v, float) for v in (y, fb, fm))
    den = float(((y - fb) ** 2).sum())
    return 1.0 - float(((y - fm) ** 2).sum()) / den if den > 0 else None


def switching(y, f, cost: float = EP_SWITCH) -> np.ndarray:
    """Monthly excess return of long-SPY-or-bills on the forecast sign (in SPY when f > 0), ``cost`` per switch (the
    first entry from bills counts)."""
    pos = (np.asarray(f, float) > 0).astype(float)
    sw = np.abs(np.diff(np.r_[0.0, pos]))
    return pos * np.asarray(y, float) - cost * sw


def ep_reading(months: Sequence[str], x: dict, tgt: dict, first_target: str, last_target: str, split_target: str,
               want: str, train_from: str = EP_TRAIN_FROM, with_p: bool = True) -> dict:
    """One equity-premium predictor reading: expanding OOS record over target months [first, last], R2_OS overall and
    by half, Clark-West (NW lag 12 normal p and the 12-month block bootstrap p), slope NW t on the window's pairs and on
    every pair, switching-rule excess returns and the historical-mean rule's."""
    ms = mrange(train_from, madd(last_target, -1))
    X = np.array([x.get(m, np.nan) for m in ms], float)
    Y = np.array([tgt[m][0] if m in tgt else np.nan for m in ms], float)
    k0 = ms.index(madd(first_target, -1))
    rec = expanding_oos(X, Y, k0, len(ms) - 1)
    tm = [madd(ms[k], 1) for k in rec["k"]]
    yv, fb, fm = rec["y"], rec["fb"], rec["fm"]
    out = {"n": int(yv.size), "target_first": tm[0] if tm else None, "target_last": tm[-1] if tm else None}
    if yv.size < 10:
        return out
    cw = cw_series(yv, fb, fm)
    nwcw = _nw(cw, EP_CW_LAG)
    pg, pl, dr = CAL.studentized_p_escalated(cw, EP_BLOCK, None, SEED, CAL.N_SEEDS) if with_p else (None, None, 0)
    h1 = np.array([m < split_target for m in tm])
    halves = [r2_os(yv[h1], fb[h1], fm[h1]), r2_os(yv[~h1], fb[~h1], fm[~h1])]
    win = np.isfinite(X[rec["k"]])
    lagA = CAL.nw_lags(int(yv.size))
    ra = ols_nw_all(yv, X[rec["k"]], lagA)
    allm = np.isfinite(X) & np.isfinite(Y)
    lagB = CAL.nw_lags(int(allm.sum()))
    rb = ols_nw_all(Y[allm], X[allm], lagB)
    sw, sb = switching(yv, fm), switching(yv, fb)
    neg_share = float(np.mean(rec["slope"] < 0))
    out.update(months=tm, y=yv, fb=fb, fm=fm, cw=cw, r2=r2_os(yv, fb, fm), cw_nw=nwcw, cw_boot_p=pg, cw_boot_p_lt=pl,
               cw_draws=dr, halves=halves, slope_window=ra, slope_all=rb, switch=sw, bench=sb,
               origin_slope_neg_share=neg_share, origin_slope_last=float(rec["slope"][-1]), want=want, win=bool(win.all()))
    return out


def ep_rows(R: dict, want: str, t_bar: float, split_label: tuple) -> list:
    """Criterion rows (name, ok, decisive) of one reading, without the DSR."""
    if R.get("n", 0) < 10:
        return [("equity-premium reading (too few forecasts)", None, False)]
    sgn = -1.0 if want == "neg" else 1.0
    r2 = R["r2"]
    cwn = R["cw_nw"]
    cw_ok = bool(cwn["p"] is not None and cwn["p"] < ALPHA)
    bs_ok = CAL.decide_p(R["cw_boot_p"], R["cw_draws"])
    cw_row = BW.all_constructions(
        [(f"CW NW (lag {EP_CW_LAG}) t {_s(cwn['t'], 2)}, p {_f(cwn['p'], 4)}", cw_ok, cwn["t"] is not None and cwn["t"] < -1.645),
         (f"CW block bootstrap ({EP_BLOCK}) p {CAL._mc(R['cw_boot_p'], R['cw_draws'])}", bs_ok,
          CAL.decide_p(R["cw_boot_p_lt"], R["cw_draws"]) is True)], "Clark-West one-sided p < 0.05")
    ta = (R["slope_window"]["t"] or [None, None])[1]
    tb = (R["slope_all"]["t"] or [None, None])[1]
    sl_ok = lambda t: None if t is None or not np.isfinite(t) else bool(sgn * t > t_bar)
    sl_dec = lambda t: t is not None and np.isfinite(t) and sgn * t < -t_bar
    slope_row = BW.all_constructions(
        [(f"window pairs t {_s(ta, 2)} (lag {R['slope_window']['lag']})", sl_ok(ta), sl_dec(ta)),
         (f"all pairs from {EP_TRAIN_FROM} t {_s(tb, 2)} (lag {R['slope_all']['lag']})", sl_ok(tb), sl_dec(tb))],
        f"slope NW t {'<' if want == 'neg' else '>'} {'-' if want == 'neg' else ''}{t_bar}")
    h = R["halves"]
    sd = sharpe_diff(R["switch"], R["bench"])
    sname, sok, sdec = BW._ci_crit(sd, "gt", 0.0, f"switching-rule Sharpe {_f(sd.get('sharpe_a'))} minus the historical-"
                                                    f"mean rule's {_f(sd.get('sharpe_b'))} = {_s(sd.get('diff'))}, paired "
                                                    f"lower 95% bound > 0")
    R["sharpe_diff"] = sd
    return [(f"R2_OS {_s(r2, 4)} > 0", None if r2 is None else bool(r2 > 0), False),
            cw_row, slope_row,
            (f"R2_OS > 0 in both halves ({split_label[0]} {_s(h[0], 4)}, {split_label[1]} {_s(h[1], 4)})",
             None if any(v is None for v in h) else all(v > 0 for v in h), False),
            (sname, sok, sdec)]


def combine_readings(rowsets: list, names: Sequence[str]) -> list:
    """Rule 11 across readings: criterion j passes only when it passes in every reading (``BW.all_constructions``)."""
    out = []
    for j in range(len(rowsets[0])):
        rows = [(f"[{nm}] {rs[j][0]}", rs[j][1], rs[j][2]) for nm, rs in zip(names, rowsets)]
        out.append(BW.all_constructions(rows, f"criterion {j + 1}"))
    return out


def _futures(archive, name: str) -> tuple:
    days, close = CAL._daily(archive, name, "close")
    return list(days), np.asarray(close, float)


def _bills(archive):
    return CAL.Bills(CAL._series(archive, DTB3_B))


def oil_monthly(days: Sequence[str], close, mask) -> dict:
    """{month: summed CL=F daily log change over the month's unmasked sessions}, complete months only."""
    ms = monthly_sum(days, log_changes(close, mask))
    keep = complete_months(days)
    return {m: v for m, v in ms.items() if m in keep}


def b13_crossasset_a_oil_spy(archive):
    """T-598."""
    miss = _missing(archive, [CL_B, SPY_B, DTB3_B])
    if miss:
        return miss
    cd, cc = _futures(archive, CL_B)
    sd, sa = CAL._daily(archive, SPY_B, "adjclose")
    sd = list(sd)
    bills = _bills(archive)
    tgt = spy_targets(sd, sa, bills, mrange(EP_TRAIN_FROM, madd(T598_LAST_TARGET, -1)))
    readings = {}
    for nm, unit in T598_READINGS:
        mask = cl_roll_mask(cd, T598_ROLL_WIN, unit)
        x = oil_monthly(cd, cc, mask)
        readings[nm] = {"R": ep_reading(list(x), x, tgt, T598_FIRST_TARGET, T598_LAST_TARGET, T598_SPLIT, "neg"),
                        "masked_share": float(np.mean(mask)), "x": x}
    names = [nm for nm, _ in T598_READINGS]
    rowsets = [ep_rows(readings[nm]["R"], "neg", EP_T_BAR, ("2010-2017", "2018-2026")) for nm in names]
    crit = combine_readings(rowsets, names)
    dsr_rows, dsr_info = [], {}
    for nm in names:
        rows_, info = dsr_two(readings[nm]["R"], T598_FAMILY_MIN, T598_FAMILY_FULL, f"[{nm}]")
        dsr_rows += rows_
        dsr_info[nm] = info
    crit.append(BW.all_constructions(dsr_rows, f"joint-family DSR > {DSR_PASS} (2 trials + 4 named predictors; trial 2 "
                                                f"needs fred-DCOILWTICO, not archived)"))
    R0 = readings[names[0]]["R"]
    n = int(min(readings[nm]["R"]["n"] for nm in names))
    v, why, crit_j = CAL._judge(crit, n, T598_MIN_N, "monthly forecasts")
    # ---- reported: the literal CL + BZ mask, SPY's own month-t return as an extra regressor
    lit = oil_monthly(cd, cc, PAIRS.roll_mask(cd, T598_ROLL_WIN, "sessions"))
    Rlit = ep_reading(list(lit), lit, tgt, T598_FIRST_TARGET, T598_LAST_TARGET, T598_SPLIT, "neg", with_p=False)
    spy_m = spy_month_returns(sd, sa)
    x0 = readings[names[0]]["x"]
    ms = [m for m in mrange(EP_TRAIN_FROM, madd(T598_LAST_TARGET, -1)) if m in x0 and m in tgt and m in spy_m
          and np.isfinite(x0[m])]
    ctrl = ols_nw_all([tgt[m][0] for m in ms], np.column_stack([[x0[m] for m in ms], [spy_m[m] for m in ms]]),
                      CAL.nw_lags(len(ms)))
    stat = {"n": n, "readings": {nm: _ep_stat(readings[nm]["R"], readings[nm]["masked_share"], dsr_info[nm]) for nm in names},
            "literal_cl_bz_mask": _ep_stat(Rlit, None, None), "spy_control": ctrl, "trial2": "fred-DCOILWTICO not archived",
            "criteria": crit_j, "verdict": v}
    parts = []
    for nm in names:
        R = readings[nm]["R"]
        parts.append(f"[{nm}; {readings[nm]['masked_share'] * 100:.0f}% of sessions masked] R2_OS {_s(R.get('r2'), 4)}, "
                     f"CW t {_s(R['cw_nw']['t'], 2)} (boot p {_f(R['cw_boot_p'], 4)}), slope t {_s(_t1(R.get('slope_window')), 2)} "
                     f"(all pairs {_s(_t1(R.get('slope_all')), 2)}), halves {_s(R['halves'][0], 4)} / {_s(R['halves'][1], 4)}, "
                     f"switching Sharpe {_f(R['sharpe_diff'].get('sharpe_a'))} vs historical mean {_f(R['sharpe_diff'].get('sharpe_b'))}, "
                     f"negative expanding slope at {R['origin_slope_neg_share'] * 100:.0f}% of origins")
    cb = (ctrl.get("t") or [None, None, None])
    reason = (f"CL=F roll-masked monthly log change -> SPY excess return from the first close of t+1 to the first close of "
              f"t+2, expanding OLS from {EP_TRAIN_FROM}, target months {R0.get('target_first')}..{R0.get('target_last')} "
              f"({n} forecasts): " + "; ".join(parts) + f". Reported: literal T-468 CL+BZ mask R2_OS {_s(Rlit.get('r2'), 4)}, "
              f"slope t {_s(_t1(Rlit.get('slope_window')), 2)}; with SPY's own month-t return "
              f"as a second regressor the oil slope t is {_s(cb[1], 2)} (SPY t {_s(cb[2], 2)}). Trial 2 (WTI spot, "
              f"fred-DCOILWTICO) is not archived, so it is not computed; the joint-family DSR can fail but not pass here")
    return _out(stat, n, v, reason + " — " + why)


def cl_roll_mask(days: Sequence[str], window: int, unit: str) -> np.ndarray:
    """T-468's roll windows for the CL contract only: +-``window`` sessions (or calendar days) of each scheduled CL last
    trading day (``batch6c_pairs.cl_last_trade``)."""
    n = len(days)
    fl = np.zeros(n, bool)
    if not n:
        return fl
    od = np.array([date.fromisoformat(d).toordinal() for d in days])
    y0, y1 = int(days[0][:4]), int(days[-1][:4]) + 1
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            ltd = PAIRS.cl_last_trade(y, m)
            if unit == "days":
                fl |= np.abs(od - ltd.toordinal()) <= window
                continue
            lt = ltd.isoformat()
            if lt < days[0] or lt > days[-1]:
                continue
            j = bisect.bisect_right(days, lt) - 1
            fl[max(0, j - window):min(n, j + window + 1)] = True
    return fl


def spy_month_returns(days: Sequence[str], adj) -> dict:
    """{month: SPY total return from the previous month's last close to the month's last close}."""
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    ms = sorted(last)
    return {m: float(adj[last[m]] / adj[last[p]] - 1.0) for p, m in zip(ms[:-1], ms[1:])}


def _ep_stat(R: dict, masked: Optional[float], dsr: Optional[dict]) -> dict:
    keys = ("n", "target_first", "target_last", "r2", "cw_boot_p", "halves", "origin_slope_neg_share", "origin_slope_last")
    out = {k: R.get(k) for k in keys}
    if R.get("cw_nw"):
        out["cw_nw_t"], out["cw_nw_p"] = R["cw_nw"]["t"], R["cw_nw"]["p"]
    for k in ("slope_window", "slope_all"):
        if R.get(k):
            out[k] = {"coef": R[k]["coef"], "t": R[k]["t"], "lag": R[k]["lag"], "n": R[k]["n"]}
    if R.get("sharpe_diff"):
        sd = R["sharpe_diff"]
        out["sharpe_diff"] = {"switch": sd.get("sharpe_a"), "bench": sd.get("sharpe_b"), "diff": sd.get("diff"), "ci": sd.get("ci")}
    if R.get("switch") is not None:
        out["months_in_spy_share"] = float(np.mean(np.asarray(R["fm"]) > 0))
        out["bench_months_in_spy_share"] = float(np.mean(np.asarray(R["fb"]) > 0))
    out["masked_share"] = masked
    out["dsr"] = dsr
    return out


def gp_monthly(gd, gc, pd_, pc, gold_mask, plat_mask) -> dict:
    """{month: log mean(gold index) - log mean(platinum index)} over complete months of both series."""
    g = chained_monthly_mean(gd, gc, gold_mask)
    p = chained_monthly_mean(pd_, pc, plat_mask)
    keep = complete_months(gd) & complete_months(pd_)
    return {m: math.log(g[m]) - math.log(p[m]) for m in g if m in p and m in keep}


def delta(series: dict) -> dict:
    """{month: x(m) - x(m - 1)} where both exist."""
    return {m: v - series[madd(m, -1)] for m, v in series.items() if madd(m, -1) in series}


def raw_ratio_monthly(gd, gc, pd_, pc) -> dict:
    """{month: mean raw GC close / mean raw PL close} (the level rule's predictor-only check)."""
    def mm(days, c):
        by = defaultdict(list)
        for d, x in zip(days, c):
            by[d[:7]].append(x)
        return {m: float(np.mean(v)) for m, v in by.items()}
    g, p = mm(gd, gc), mm(pd_, pc)
    keep = complete_months(gd) & complete_months(pd_)
    return {m: g[m] / p[m] for m in g if m in p and m in keep}


def b13_crossasset_a_gold_platinum(archive):
    """T-600."""
    miss = _missing(archive, [GC_B, PL_B, SPY_B, DTB3_B])
    if miss:
        return miss
    gd, gc = _futures(archive, GC_B)
    pd_, pc = _futures(archive, PL_B)
    sd, sa = CAL._daily(archive, SPY_B, "adjclose")
    sd = list(sd)
    bills = _bills(archive)
    gm = MISC.roll_flags(gd, T600_GC_MONTHS, T600_ROLL_WIN)
    pm = MISC.roll_flags(pd_, T600_PL_MONTHS, T600_ROLL_WIN)
    lgp = gp_monthly(gd, gc, pd_, pc, gm, pm)
    pl_months = {d[:7] for d in pd_}
    pl_gaps = [m for m in mrange(EP_TRAIN_FROM, max(pl_months)) if m not in pl_months]
    x = delta(lgp)
    tgt = spy_targets(sd, sa, bills, mrange(EP_TRAIN_FROM, madd(T600_LAST_TARGET, -1)))
    R = ep_reading(sorted(x), x, tgt, T600_FIRST_TARGET, T600_LAST_TARGET, T600_SPLIT, "pos")
    crit = ep_rows(R, "pos", EP_T_BAR, ("2014-2019", "2020-2026"))
    drows, dinfo = dsr_two(R, T600_FAMILY_MIN, T600_FAMILY_FULL, "")
    crit.append(BW.all_constructions(drows, f"joint-family DSR > {DSR_PASS} (both GP trials + the 4 named predictors)"))
    n = int(R["n"])
    v, why, crit_j = CAL._judge(crit, n, T600_MIN_N, "monthly forecasts")
    # ---- reported: the level rule, the level trial, the 12-month horizon, the GLD/PPLT cross-check
    rr = raw_ratio_monthly(gd, gc, pd_, pc)
    pre = [v_ for m, v_ in rr.items() if m < T600_RANGE_SPLIT]
    post = [v_ for m, v_ in rr.items() if m >= T600_RANGE_SPLIT]
    outside = float(np.mean([(p_ < min(pre)) or (p_ > max(pre)) for p_ in post])) if pre and post else None
    lvl = {m: math.log(v_) for m, v_ in rr.items()}
    Rl = ep_reading(sorted(lvl), lvl, tgt, T600_FIRST_TARGET, T600_LAST_TARGET, T600_SPLIT, "pos", with_p=False)
    ann = annual_horizon(x, sd, sa, bills)
    xd, xa = CAL._daily(archive, GLD_B, "adjclose") if B7C._has(archive, GLD_B) else ([], [])
    yd, ya = CAL._daily(archive, PPLT_B, "adjclose") if B7C._has(archive, PPLT_B) else ([], [])
    cross = None
    if len(xd) and len(yd):
        etf = delta(gp_monthly(list(xd), np.asarray(xa, float), list(yd), np.asarray(ya, float), None, None))
        first_etf = min(etf)
        Re = ep_reading(sorted(etf), etf, tgt, T600_FIRST_TARGET, T600_LAST_TARGET, T600_SPLIT, "pos", train_from=first_etf,
                        with_p=False)
        cross = _ep_stat(Re, None, None)
        cross["train_from"] = first_etf
    stat = {"n": n, "primary": _ep_stat(R, None, dinfo), "level_rule": {"pre_months": len(pre), "post_months": len(post),
            "pre_range": [min(pre), max(pre)] if pre else None, "post_range": [min(post), max(post)] if post else None,
            "share_outside": outside, "rule": T600_RANGE_RULE}, "level_trial_reported": _ep_stat(Rl, None, None),
            "annual_horizon": ann, "gld_pplt": cross, "masked_share": {"gold": float(np.mean(gm)), "platinum": float(np.mean(pm))},
            "pl_months_without_bars": pl_gaps,
            "criteria": crit_j, "verdict": v}
    reason = (f"Delta log(gold/platinum) of monthly means of roll-masked chained GC=F / PL=F indices (gold "
              f"{np.mean(gm) * 100:.0f}% / platinum {np.mean(pm) * 100:.0f}% of sessions masked) -> SPY excess return from "
              f"the first close of t+1 to the first close of t+2, expanding OLS from {EP_TRAIN_FROM}, target months "
              f"{R.get('target_first')}..{R.get('target_last')} ({n} forecasts): R2_OS {_s(R.get('r2'), 4)}, CW t "
              f"{_s(R['cw_nw']['t'], 2)} (boot p {_f(R['cw_boot_p'], 4)}), slope t {_s(_t1(R.get('slope_window')), 2)} (all pairs "
              f"{_s(_t1(R.get('slope_all')), 2)}), halves {_s(R['halves'][0], 4)} / {_s(R['halves'][1], 4)}, switching Sharpe "
              f"{_f(R['sharpe_diff'].get('sharpe_a'))} vs historical mean {_f(R['sharpe_diff'].get('sharpe_b'))}, positive "
              f"expanding slope at {(1 - R['origin_slope_neg_share']) * 100:.0f}% of origins. Level trial inconclusive by the "
              f"pre-declared range rule ({_f(outside * 100 if outside is not None else None, 1)}% of {len(post)} post-2014 "
              f"monthly ratios outside the {len(pre)}-month 2000-2013 range [{_f(min(pre) if pre else None)}, "
              f"{_f(max(pre) if pre else None)}]; > {T600_RANGE_RULE * 100:.0f}%), reported only: R2_OS {_s(Rl.get('r2'), 4)}. "
              f"Reported: 12-month horizon on {ann.get('n')} non-overlapping years slope t {_s(ann.get('t'), 2)}; GLD/PPLT "
              f"cross-check R2_OS {_s((cross or {}).get('r2'), 4)}. PL=F has no bars in {len(pl_gaps)} months "
              f"({', '.join(pl_gaps[:3])}{', ...' if len(pl_gaps) > 3 else ''}; all in the training window): those months and "
              f"the next drop out of the fit. The sign is registered positive; the Xu-Li-Singh sign check "
              f"could not be read here")
    return _out(stat, n, v, reason + " — " + why)


def annual_horizon(x: dict, spy_days, spy_adj, bills) -> dict:
    """Reported: the December Delta log GP against the next 12 months' SPY excess return (first close of January to
    the first close of the next January), non-overlapping years."""
    first = {}
    for i, d in enumerate(spy_days):
        first.setdefault(d[:7], i)
    xs, ys = [], []
    for y in range(2001, 2030):
        m = f"{y}-12"
        a, b = first.get(f"{y + 1}-01"), first.get(f"{y + 2}-01")
        if m not in x or a is None or b is None:
            continue
        xs.append(x[m])
        ys.append(float(spy_adj[b] / spy_adj[a] - 1.0 - bills.growth(spy_days[a], spy_days[b])))
    if len(xs) < 6:
        return {"n": len(xs), "slope": None, "t": None}
    r = ols_nw_all(ys, xs, 1)
    return {"n": len(xs), "slope": r["coef"][1] if r["coef"] else None, "t": r["t"][1] if r["t"] else None}


# ================================================================================ cross-sectional stock base ==

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


def _ffill_rows(X: np.ndarray) -> np.ndarray:
    return SX._ffill(X)


def xs_base(archive) -> dict:
    """The shared point-in-time S&P 500 stock panel (T-603, T-596): sessions (SPY bars from 2000-06), membership,
    T-473's reused-ticker filters, SIC and CIK per kept symbol, and session x symbol price / volume matrices from the
    shared daily panel. Cached per archive."""
    def load():
        from mandel.experiments.panel_cache import daily_panel
        P = daily_panel(archive)
        pdays = P.days.astype(str)
        spy = P.col("SPY", "close")
        rows = np.flatnonzero(np.isfinite(spy) & (pdays >= XS_START))
        days = [str(d) for d in pdays[rows]]
        sets, n_wiki = SX._member_sets(archive)
        sdates = [d for d, _ in sets]
        k0 = max(0, bisect.bisect_right(sdates, days[0]) - 1)
        tick = set()
        for d, s in sets[k0:]:
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
        sec_t = SX._sec_tickers(archive) if B7C._has(archive, SEC_TICK_B) else {}
        pcol = {str(s): j for j, s in enumerate(P.symbols.tolist())}
        info = {"tickers": len(tick), "no_series": [], "not_equity": [], "name_mismatch": [], "no_cik": [], "no_sic": [],
                "wiki_changes_after_fja": n_wiki}
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
        keep = []
        for t, y, j, meta, cik in cand:
            if y not in wiki and removed.get(y):
                names = [meta.get("longName") or ""]
                if y in sec_t:
                    v = comp.get(sec_t[y][0]) or {}
                    names += [sec_t[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
                if SX.names_ok(removed[y], names) is False:
                    info["name_mismatch"].append(y)
                    continue
            keep.append((t, y, j, cik))
        syms = [y for _, y, _, _ in keep]
        tick_of = {}
        for t, y, _, _ in keep:
            tick_of.setdefault(y, set()).add(t)
        cols = np.array([j for _, _, j, _ in keep], int)
        ciks = [c for *_, c in keep]
        sic = []
        for y, c in zip(syms, ciks):
            s = None
            if c is not None and c in comp:
                try:
                    s = int(str(comp[c].get("sic") or "").strip())
                except ValueError:
                    s = None
            if c is None:
                info["no_cik"].append(y)
            if s is None:
                info["no_sic"].append(y)
            sic.append(s)
        by_cik = defaultdict(list)
        for y, c in zip(syms, ciks):
            if c is not None:
                by_cik[c].append(y)
        multi = {y for ys in by_cik.values() if len(ys) > 1 for y in ys}
        D, N = len(days), len(syms)
        mats = {f: np.ascontiguousarray(getattr(P, f)[np.ix_(rows, cols)]) for f in ("open", "high", "low", "close", "adjclose", "volume")}
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
        spells = {}
        if B7C._has(archive, SPELLS_B):
            for r in SX._rows(archive, SPELLS_B):
                v = r.get("value") or {}
                if r.get("kind") == "sp500-join" and v.get("ticker"):
                    spells[SX.ysym(v["ticker"])] = max(spells.get(SX.ysym(v["ticker"]), 0), int(v.get("spell") or 1))
        info["multi_spell_kept"] = sorted(y for y in syms if spells.get(y, 1) > 1)
        info["kept"] = N
        return {"days": days, "syms": syms, "ciks": ciks, "sic": sic, "multi": multi, "member": member,
                "n_members": n_members, "info": info, **mats}
    return CAL._cached(archive, ("b13xa_base",), load)


def share_series_by_cik(archive, ciks: set) -> dict:
    """{cik: ``batch6c_stockxs.shares_series``} from the companyfacts buckets that hold the wanted CIKs (share tags only;
    a fact counts from its available_at)."""
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
    return CAL._cached(archive, ("b13xa_shares", frozenset(ciks)), load)


def shares_known(series: Sequence[tuple], ts: float, day: str, max_age: int = T603_MAX_AGE) -> Optional[tuple]:
    """(shares, as-of date) of the latest accession available at ``ts`` when its cover date is at most ``max_age`` days
    before ``day``; None otherwise."""
    k = bisect.bisect_right(series, ts, key=lambda s: s[0]) - 1
    if k < 0:
        return None
    _, end, sh = series[k]
    if (date.fromisoformat(day) - date.fromisoformat(end)).days <= max_age:
        return sh, end
    return None


def month_last_sessions(days: Sequence[str]) -> dict:
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    return last


def week_last_sessions(days: Sequence[str]) -> list:
    """Index of the last session of each ISO week, in order."""
    out, prev = [], None
    for i, d in enumerate(days):
        y, w, _ = date.fromisoformat(d).isocalendar()
        if prev is not None and (y, w) != prev:
            out.append(i - 1)
        prev = (y, w)
    out.append(len(days) - 1)
    return out


# ====================================================================================================== T-603 ==

def formation(A, C, V, member_row, el_static, e_prev: int, f: int, adj_shares) -> dict:
    """One formation at session ``f`` (the decision close) from the previous month-end ``e_prev``: total return
    A[f] / A[e_prev] - 1 and turnover = sum of volume over sessions e_prev+1..f / adjusted shares, cap = close[f] x
    adjusted shares. Eligible: member at f, statically eligible, bars at e_prev and f, finite volume on every formation
    session, positive turnover and cap. Uses no data after session f."""
    a0, a1 = A[e_prev], A[f]
    vol = V[e_prev + 1:f + 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = a1 / a0 - 1.0
        to = vol.sum(axis=0) / adj_shares
        cap = C[f] * adj_shares
    ok = (member_row & el_static & np.isfinite(r) & np.isfinite(vol).all(axis=0) & np.isfinite(to) & (to > 0)
          & np.isfinite(cap) & (cap > 0))
    return {"r": np.where(ok, r, np.nan), "to": np.where(ok, to, np.nan), "cap": np.where(ok, cap, np.nan), "el": ok}


def stmom_legs(r, to, el, kind: str = "stmom") -> tuple:
    """(long mask, short mask) of one month's independent 2x2 median sorts. 'stmom': high-turnover winners / losers;
    'strev_star': low-turnover losers / winners; 'strev': losers / winners (all turnover). Ties at a median join neither
    side."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mr = np.nanmedian(np.where(el, r, np.nan))
        mt = np.nanmedian(np.where(el, to, np.nan))
    win, los = el & (r > mr), el & (r < mr)
    hi, lo = el & (to > mt), el & (to < mt)
    if kind == "stmom":
        return win & hi, los & hi
    if kind == "strev_star":
        return los & lo, win & lo
    return los, win


def book_returns(R, TO, CAP, EL, HR, kind: str = "stmom", cost: float = T603_COST) -> dict:
    """Monthly value-weighted long-short returns over formation rows (M, N): gross, cost (``cost`` x sum |w_new -
    drifted w_old| over both legs; first entry and final exit charged) and net."""
    M, N = R.shape
    WL = np.zeros((M, N))
    WS = np.zeros((M, N))
    for t in range(M):
        lm, sm = stmom_legs(R[t], TO[t], EL[t], kind)
        cl = np.where(lm, CAP[t], 0.0)
        cs = np.where(sm, CAP[t], 0.0)
        if cl.sum() > 0:
            WL[t] = cl / cl.sum()
        if cs.sum() > 0:
            WS[t] = cs / cs.sum()
    return _book_from_weights(WL, WS, HR, cost)


def _book_from_weights(WL, WS, HR, cost: float) -> dict:
    H = np.nan_to_num(HR, nan=0.0)
    gl = (WL * H).sum(axis=1)
    gs = (WS * H).sum(axis=1)
    def turnover(W, g):
        T = np.zeros(W.shape[0])
        prev = np.zeros(W.shape[1])
        for t in range(W.shape[0]):
            T[t] = np.abs(W[t] - prev).sum()
            prev = W[t] * (1.0 + H[t]) / (1.0 + g[t]) if (1.0 + g[t]) != 0 else W[t]
        T[-1] += np.abs(prev).sum()
        return T
    tl, ts = turnover(WL, gl), turnover(WS, gs)
    gross = gl - gs
    c = cost * (tl + ts)
    return {"gross": gross, "net": gross - c, "cost": c, "long": gl, "short": gs, "turnover": tl + ts,
            "n_long": (WL > 0).sum(axis=1), "n_short": (WS > 0).sum(axis=1)}


def t603_inputs(archive, trial: str, first_hold: str, last_hold: str) -> dict:
    """Formation matrices for holding months [first_hold, last_hold] of trial 'a' (full month, fill at the first close of
    t+1) or 'b' (skip the last 3 sessions, fill at the month-end close)."""
    B = xs_base(archive)
    days = B["days"]
    A, C, V = B["adjclose"], B["close"], B["volume"]
    N = len(B["syms"])
    last = month_last_sessions(days)
    sic = B["sic"]
    fin = np.array([s is not None and 6000 <= s <= 6999 for s in sic])
    nosic = np.array([s is None for s in sic])
    multi = np.array([y in B["multi"] for y in B["syms"]])
    el_static = ~fin & ~nosic & ~multi
    ciks = {c for c, ok in zip(B["ciks"], el_static) if c is not None and ok}
    sh = share_series_by_cik(archive, ciks)
    splits = CAL._cached(archive, ("b13xa_splits",), lambda: {y: stock_splits(archive, y) for y in B["syms"]})
    real = np.isfinite(A)
    Aff = _ffill_rows(A)
    lastbar = np.where(real.any(axis=0), len(days) - 1 - real[::-1].argmax(axis=0), -1)
    rows = []
    for H in mrange(first_hold, last_hold):
        t, tp = madd(H, -1), madd(H, -2)
        if t not in last or tp not in last or H not in last:
            continue
        e_t, e_prev, e_h = last[t], last[tp], last[H]
        if trial == "a":
            f, entry, exit_ = e_t, e_t + 1, e_h + 1
        else:
            f, entry, exit_ = e_t - T603_SKIP, e_t, e_h
        if exit_ >= len(days) or f <= e_prev:
            continue
        ts = SX._et_ts(days[f], 16, 0)
        adj = np.full(N, np.nan)
        cov = {"members": int(B["n_members"][f]), "priced_members": 0, "no_shares": 0, "financial": 0, "multi": 0, "no_sic": 0}
        mem = B["member"][f]
        for j in np.flatnonzero(mem & el_static):
            c = B["ciks"][j]
            s = shares_known(sh.get(c, ()), ts, days[f]) if c is not None else None
            if s is None:
                cov["no_shares"] += 1
                continue
            adj[j] = s[0] * SX.split_factor(splits.get(B["syms"][j], ()), s[1])
        cov["financial"] = int((mem & fin).sum())
        cov["multi"] = int((mem & multi).sum())
        cov["no_sic"] = int((mem & nosic).sum())
        fm = formation(A, C, V, mem, el_static, e_prev, f, adj)
        cov["priced_members"] = int((mem & real[f]).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            xe = np.minimum(exit_, lastbar)
            hr = np.where(real[entry] & (lastbar >= entry), Aff[np.maximum(xe, 0), np.arange(N)] / A[entry] - 1.0, 0.0)
        hr = np.where(fm["el"], np.nan_to_num(hr, nan=0.0), 0.0)
        rows.append({"H": H, "f": f, "entry": entry, "exit": exit_, **fm, "hr": hr, "cov": cov})
    return {"rows": rows, "days": days, "base_info": B["info"], "n_multi": int(multi.sum()), "n_fin": int(fin.sum())}


def _stack(rows: list, key: str) -> np.ndarray:
    return np.vstack([r[key] for r in rows]) if rows else np.zeros((0, 0))


def factor_holds(archive, days: Sequence[str], rows: list) -> tuple:
    """(F (M, 6) compounded FF5 + UMD over each hold (entry, exit], mask of holds fully covered and ending by
    2026-08-31)."""
    cols = SX.FF5_COLS
    f5 = {c: CAL._series(archive, FF5_B, c) for c in cols}
    um = CAL._series(archive, MOM_B, "Mom")
    F = np.full((len(rows), 6), np.nan)
    ok = np.zeros(len(rows), bool)
    for k, r in enumerate(rows):
        ds = days[r["entry"] + 1:r["exit"] + 1]
        if not ds or ds[-1] > T603_FF_END:
            continue
        try:
            vals = [[f5[c][d] / 100.0 for c in cols] + [um[d] / 100.0] for d in ds]
        except KeyError:
            continue
        F[k] = np.prod(1.0 + np.array(vals), axis=0) - 1.0
        ok[k] = True
    return F, ok


def b13_crossasset_a_stmom(archive):
    """T-603."""
    miss = _missing(archive, [SPY_B, FJA_B, SPELLS_B, FF5_B, MOM_B, SEC_TICK_B]) or \
        _prefix_missing(archive, ["daily-history-", "daily-events-", FACTS_PREFIX, SUBS_PREFIX])
    if miss:
        return miss
    books, inputs = {}, {}
    for trial in ("a", "b"):
        I = t603_inputs(archive, trial, T603_FIRST, T603_LAST)
        inputs[trial] = I
        rows = I["rows"]
        M = [_stack(rows, k) for k in ("r", "to", "cap", "el", "hr")]
        books[trial] = {k: book_returns(*M, kind=k) for k in ("stmom", "strev_star", "strev")}
        books[trial]["months"] = [r["H"] for r in rows]
        books[trial]["mats"] = M
    A = books["a"]
    rows_a = inputs["a"]["rows"]
    net = A["stmom"]["net"]
    n = int(net.size)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} holding months could be formed")
    months = A["months"]
    mean = float(net.mean())
    prow, pinf = p_rows(mean, net, T603_BLOCK, T603_NW_LAG, f"net mean {_pc(mean, 3)}/month > 0 with one-sided p < 0.05")
    h1 = np.array([m < T603_SPLIT for m in months])
    halves = [float(net[h1].mean()), float(net[~h1].mean())]
    F, fok = factor_holds(archive, inputs["a"]["days"], rows_a)
    reg = ols_nw_all(net[fok], F[fok], T603_NW_LAG) if fok.sum() > 12 else {"coef": None, "t": None}
    alpha = reg["coef"][0] if reg.get("coef") else None
    alpha_t = reg["t"][0] if reg.get("t") else None
    rng = np.random.default_rng(SEED)
    R_, TO_, CAP_, EL_, HR_ = A["mats"]
    plac = np.empty(N_PLACEBO)
    for k in range(N_PLACEBO):
        plac[k] = book_returns(R_, permute_cols(TO_, rng), CAP_, EL_, HR_)["net"].mean()
    p95 = float(np.percentile(plac, 95))
    net_b = books["b"]["stmom"]["net"]
    d = MOM.family_dsr(net, [float(sharpe_ratio(net)), float(sharpe_ratio(net_b))], 2)
    crit = [prow,
            (f"both halves positive (2019-01..2022-10 {_pc(halves[0], 3)}, 2022-11..2026-09 {_pc(halves[1], 3)})",
             all(h > 0 for h in halves), False),
            (f"FF5+UMD alpha {_pc(alpha, 3) if alpha is not None else 'n/a'}/month > 0 (NW t {_s(alpha_t, 2)}, "
             f"{int(fok.sum())} holds to {T603_FF_END})", None if alpha is None else bool(alpha > 0),
             alpha_t is not None and alpha_t < -1.645),
            (f"net mean above the shuffled-turnover placebo's 95th percentile {_pc(p95, 3)} ({N_PLACEBO} draws)",
             bool(mean > p95), False),
            MOM.dsr_row(d, f"DSR > {DSR_PASS} over the 2 trials")]
    v0, why0, crit_j = CAL._judge(crit, n, T603_MIN_N, "holding months")
    # the pre-registered verdict map
    v, why = v0, why0
    if mean <= 0:
        v, why = "not_supported", f"net mean {_pc(mean, 3)} <= 0 (pre-registered verdict map) — " + why0
    elif prow[1] is not True:
        v, why = "inconclusive", (f"net mean {_pc(mean, 3)} > 0 but its one-sided p is not below 0.05 under both named "
                                  f"constructions: inconclusive by the pre-registered verdict map (power; expected net t "
                                  f"about 1.2-1.8), a forward paper record next — criteria at face value: {v0}: {why0}")
    # ---- reported
    pre = t603_inputs(archive, "a", *T603_PRE)
    pre_net = book_returns(*[_stack(pre["rows"], k) for k in ("r", "to", "cap", "el", "hr")])["net"] if pre["rows"] else np.zeros(0)
    cov = [r["cov"] for r in rows_a]
    elig = np.array([int(r["el"].sum()) for r in rows_a])
    mem_tot = sum(c["members"] for c in cov)
    priced = sum(c["priced_members"] for c in cov)
    umd_m = F[fok, 5].mean() if fok.any() else None
    base = inputs["a"]["base_info"]
    stat = {"n": n, "first": months[0], "last": months[-1], "net_mean": mean, "gross_mean": float(A["stmom"]["gross"].mean()),
            "nw3": pinf["nw"], "boot_p": pinf["boot_p"], "halves": halves, "alpha": alpha, "alpha_t": alpha_t,
            "alpha_betas": reg.get("coef"), "alpha_n": int(fok.sum()), "placebo_p95": p95, "placebo_mean": float(plac.mean()),
            "placebo_rank": float(np.mean(plac < mean)), "dsr": d, "sharpe_ann": float(sharpe_ratio(net, 12)),
            "trial_b": {"net_mean": float(net_b.mean()), "sharpe_ann": float(sharpe_ratio(net_b, 12)), "n": int(net_b.size),
                        "nw3_t": _nw(net_b, T603_NW_LAG)["t"]},
            "strev_star_net_mean": float(A["strev_star"]["net"].mean()), "strev_net_mean": float(A["strev"]["net"].mean()),
            "umd_mean_hold": umd_m, "turnover_mean": float(A["stmom"]["turnover"].mean()),
            "cost_mean": float(A["stmom"]["cost"].mean()), "eligible_per_month": [int(elig.min()), int(np.median(elig)), int(elig.max())],
            "legs_median": [int(np.median(A["stmom"]["n_long"])), int(np.median(A["stmom"]["n_short"]))],
            "member_months": mem_tot, "member_months_priced_share": priced / mem_tot if mem_tot else None,
            "no_shares_member_months": sum(c["no_shares"] for c in cov), "financial_member_months": sum(c["financial"] for c in cov),
            "multi_class_member_months": sum(c["multi"] for c in cov), "no_sic_member_months": sum(c["no_sic"] for c in cov),
            "filters": {"no_series": len(base["no_series"]), "not_equity": len(base["not_equity"]),
                        "name_mismatch": base["name_mismatch"], "multi_spell_kept": len(base["multi_spell_kept"]),
                        "multi_class_dropped": inputs["a"]["n_multi"]},
            "pre_2019": {"n": int(pre_net.size), "net_mean": float(pre_net.mean()) if pre_net.size else None,
                         "nw3_t": _nw(pre_net, T603_NW_LAG)["t"] if pre_net.size > 3 else None},
            "criteria": crit_j, "verdict": v}
    reason = (f"STMOM (high-turnover winners minus high-turnover losers, VW, independent 2x2 median sorts) on point-in-time "
              f"S&P 500 non-financial members with Yahoo prices and SEC shares, trial (a) holding months {months[0]}..{months[-1]} "
              f"({n}; {elig.min()}-{elig.max()} eligible names a month, median legs {stat['legs_median'][0]} / "
              f"{stat['legs_median'][1]}): net mean {_pc(mean, 3)}/month (gross {_pc(stat['gross_mean'], 3)}, cost "
              f"{_pc(stat['cost_mean'], 3)}), NW(3) t {_s(pinf['nw']['t'], 2)}, bootstrap p {_f(pinf['boot_p'], 4)}; halves "
              f"{_pc(halves[0], 3)} / {_pc(halves[1], 3)}; FF5+UMD alpha {_pc(alpha, 3) if alpha is not None else 'n/a'} "
              f"(t {_s(alpha_t, 2)}); placebo 95th pct {_pc(p95, 3)} (observed at the {stat['placebo_rank'] * 100:.0f}th); "
              f"DSR {_f(d.get('dsr'))}. Reported: trial (b) skip-3 net mean {_pc(net_b.mean(), 3)} (t "
              f"{_s(stat['trial_b']['nw3_t'], 2)}); STREV* {_pc(stat['strev_star_net_mean'], 3)}, STREV "
              f"{_pc(stat['strev_net_mean'], 3)}, UMD {_pc(umd_m, 3) if umd_m is not None else 'n/a'} per hold; 2010-2018 "
              f"(overlaps the paper) net mean {_pc(stat['pre_2019']['net_mean'], 3) if pre_net.size else 'n/a'} over "
              f"{pre_net.size} months. Coverage: {_f(stat['member_months_priced_share'] * 100 if mem_tot else None, 1)}% of "
              f"member-months priced; member-months dropped for no fresh shares {stat['no_shares_member_months']}, financial "
              f"{stat['financial_member_months']}, multi-class {stat['multi_class_member_months']}, no SIC "
              f"{stat['no_sic_member_months']}; T-473 filters dropped {len(base['not_equity'])} non-EQUITY and "
              f"{len(base['name_mismatch'])} name-mismatched series, {len(base['no_series'])} member tickers have no archived "
              f"series. Survivorship: prices come from today's 901-symbol set and CIKs from the current SEC map, so removed "
              f"members are under-represented (direction unknown). Power stated in advance: at 0.42%/month and sd ~2.2%, "
              f"93 months give net t ~1.2-1.8")
    return _out(stat, n, v, reason + " — " + why)


def permute_cols(X: np.ndarray, rng) -> np.ndarray:
    """Each column's finite values shuffled across that column's finite positions (NaN positions kept)."""
    out = np.full_like(X, np.nan)
    fin = np.isfinite(X)
    for j in np.flatnonzero(fin.any(axis=0)):
        idx = np.flatnonzero(fin[:, j])
        out[idx, j] = X[rng.permutation(idx), j]
    return out


# ====================================================================================================== T-596 ==

def trailing_mean(X: np.ndarray, win: int, need: int) -> np.ndarray:
    """Trailing ``win``-row mean of the finite values ending at each row (row included); NaN with fewer than ``need``."""
    fin = np.isfinite(X)
    Z = np.where(fin, X, 0.0)
    cs = np.vstack([np.zeros((1, X.shape[1])), np.cumsum(Z, axis=0)])
    cn = np.vstack([np.zeros((1, X.shape[1]), int), np.cumsum(fin, axis=0)])
    i = np.arange(X.shape[0])
    lo = np.maximum(0, i - win + 1)
    s = cs[i + 1] - cs[lo]
    c = cn[i + 1] - cn[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c >= need, s / np.maximum(c, 1), np.nan)


def industry_week(r_week, dv, el, sic2, y_next, cost_next) -> dict:
    """One Friday's industry cross-section: for each 2-digit SIC with >= 6 eligible names, leaders = the top floor(n/3)
    by dollar volume (DV-weighted week return), followers = the bottom floor(n/3) (equal-weighted own week return); the
    followers' next-week returns and costs are summed for the legs. Uses only week-t data except ``y_next`` /
    ``cost_next`` (the target)."""
    idx = np.flatnonzero(el)
    out = {"ind": [], "L": [], "F": [], "Y": [], "nf": [], "sy": [], "sc": []}
    if idx.size == 0:
        return {k: np.array(v) for k, v in out.items()}
    codes = sic2[idx]
    for c in np.unique(codes):
        g = idx[codes == c]
        if g.size < T596_MIN_IND:
            continue
        k = g.size // 3
        o = g[np.argsort(dv[g], kind="stable")]
        fol, lead = o[:k], o[-k:]
        w = dv[lead]
        L = float((w * r_week[lead]).sum() / w.sum())
        Fo = float(r_week[fol].mean())
        yf = y_next[fol]
        ok = np.isfinite(yf)
        out["ind"].append(int(c)); out["L"].append(L); out["F"].append(Fo)
        out["Y"].append(float(yf[ok].mean()) if ok.any() else np.nan)
        out["nf"].append(int(ok.sum())); out["sy"].append(float(yf[ok].sum())); out["sc"].append(float(cost_next[fol][ok].sum()))
    return {k: np.array(v, float if k != "ind" else int) for k, v in out.items()}


def fm_slope(Y, L, Fo) -> Optional[float]:
    ok = np.isfinite(Y) & np.isfinite(L) & np.isfinite(Fo)
    if ok.sum() < T596_MIN_FM:
        return None
    Z = np.column_stack([np.ones(ok.sum()), L[ok], Fo[ok]])
    b, *_ = np.linalg.lstsq(Z, Y[ok], rcond=None)
    return float(b[1])


def ls_week(L, nf, sy, sc) -> Optional[tuple]:
    """(net, gross) of the quintile long-short of followers ranked on the leader return: long the top floor(n/5)
    industries' followers, short the bottom floor(n/5)'s, each leg equal-weighted across its follower stocks."""
    ok = np.isfinite(L) & (nf > 0)
    ii = np.flatnonzero(ok)
    q = ii.size // 5
    if q < 1:
        return None
    o = ii[np.argsort(-L[ii], kind="stable")]
    top, bot = o[:q], o[-q:]
    gl, gs = sy[top].sum() / nf[top].sum(), sy[bot].sum() / nf[bot].sum()
    cl, cs = sc[top].sum() / nf[top].sum(), sc[bot].sum() / nf[bot].sum()
    return float(gl - cl - gs - cs), float(gl - gs)


def t596_weeks(archive, size: bool = False) -> dict:
    """Weekly industry cross-sections over target weeks [2002-01, 2026-09] (``size``: terciles by market cap from SEC
    shares instead of dollar volume, from 2011)."""
    B = xs_base(archive)
    days = B["days"]
    A, C, O, Hh, Ll, V = (B[k] for k in ("adjclose", "close", "open", "high", "low", "volume"))
    D, N = A.shape
    real = np.isfinite(A)
    with np.errstate(invalid="ignore"):
        dvd = np.where(np.isfinite(C) & np.isfinite(V), C * V, np.nan)
    DV = trailing_mean(dvd, T596_DV_WIN, T596_DV_WIN)
    S = np.full((D, N), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        for j in range(N):                           # batch4_ohlc.corwin_schultz is 1-D
            S[:, j] = corwin_schultz(Hh[:, j], Ll[:, j], C[:, j])
    CS = trailing_mean(S, T596_CS_WIN, 1)
    Aff = _ffill_rows(A)
    lastbar = np.where(real.any(axis=0), D - 1 - real[::-1].argmax(axis=0), -1)
    sic2 = np.array([s // 100 if s is not None else -1 for s in B["sic"]])
    el_static = sic2 >= 0
    fr = week_last_sessions(days)
    sh, splits = None, None
    if size:
        el_static = el_static & np.array([y not in B["multi"] for y in B["syms"]])
        ciks = {c for c, ok in zip(B["ciks"], el_static) if c is not None and ok}
        sh = share_series_by_cik(archive, ciks)
        splits = CAL._cached(archive, ("b13xa_splits",), lambda: {y: stock_splits(archive, y) for y in B["syms"]})
    weeks = []
    cover_mem = cover_priced = 0
    first = T596_SIZE_FROM if size else T596_FIRST
    for w in range(1, len(fr) - 1):
        f0, f, f1 = fr[w - 1], fr[w], fr[w + 1]
        if not (first <= days[f1] <= T596_LAST):
            continue
        entry = f + 1
        with np.errstate(invalid="ignore", divide="ignore"):
            rw = A[f] / A[f0] - 1.0
            opn = O[entry] * A[entry] / C[entry]
            xe = np.minimum(f1, lastbar)
            yn = np.where(real[entry] & np.isfinite(opn) & (opn > 0) & (lastbar >= entry),
                          Aff[np.maximum(xe, 0), np.arange(N)] / opn - 1.0, np.nan)
        cs = CS[f]
        med = np.nanmedian(cs[np.isfinite(cs)]) if np.isfinite(cs).any() else 0.0
        cost = 2.0 * (T596_COST + 0.5 * np.where(np.isfinite(cs), cs, med))
        mem = B["member"][f]
        el = mem & el_static & np.isfinite(DV[f]) & real[f] & real[f0] & np.isfinite(rw)
        score = DV[f]
        if size:
            ts = SX._et_ts(days[f], 16, 0)
            cap = np.full(N, np.nan)
            for j in np.flatnonzero(el):
                s = shares_known(sh.get(B["ciks"][j], ()), ts, days[f]) if B["ciks"][j] is not None else None
                if s is not None:
                    cap[j] = C[f, j] * s[0] * SX.split_factor(splits.get(B["syms"][j], ()), s[1])
            el = el & np.isfinite(cap) & (cap > 0)
            score = cap
        cover_mem += int(B["n_members"][f])
        cover_priced += int((mem & real[f]).sum())
        iw = industry_week(rw, score, el, sic2, yn, cost)
        weeks.append({"t": days[f], "t1": days[f1], **iw})
    return {"weeks": weeks, "member_weeks": cover_mem, "priced_member_weeks": cover_priced, "info": B["info"],
            "spy_week": spy_week_returns(archive, days, fr)}


def spy_week_returns(archive, days: Sequence[str], fr: Sequence[int]) -> dict:
    sd, sa = CAL._daily(archive, SPY_B, "adjclose")
    pos = {d: i for i, d in enumerate(sd)}
    out = {}
    for a, b in zip(fr[:-1], fr[1:]):
        if days[a] in pos and days[b] in pos:
            out[days[b]] = float(sa[pos[days[b]]] / sa[pos[days[a]]] - 1.0)
    return out


def derange(n: int, P: int, rng) -> np.ndarray:
    """(P, n) index maps: each industry k takes the leader of another industry (a random cyclic derangement)."""
    perm = np.argsort(rng.random((P, n)), axis=1)
    src = np.empty((P, n), int)
    rows = np.arange(P)[:, None]
    src[rows, perm] = np.roll(perm, -1, axis=1)
    return src


def t596_series(weeks: list) -> dict:
    fm, ls, gross, wk = [], [], [], []
    for w in weeks:
        s = fm_slope(w["Y"], w["L"], w["F"])
        l = ls_week(w["L"], w["nf"], w["sy"], w["sc"]) if len(w["L"]) else None
        if s is None or l is None:
            continue
        fm.append(s); ls.append(l[0]); gross.append(l[1]); wk.append(w["t1"])
    return {"fm": np.array(fm), "ls": np.array(ls), "gross": np.array(gross), "weeks": wk}


def t596_placebo(weeks: list, keep_weeks: set, n_draws: int, rng) -> tuple:
    """Placebo means of the FM slope and the long-short net over the same weeks with each industry's leader return
    taken from a random other industry."""
    fm_sum = np.zeros(n_draws)
    ls_sum = np.zeros(n_draws)
    cnt = 0
    for w in weeks:
        if w["t1"] not in keep_weeks:
            continue
        L, Fo, Y, nf, sy, sc = w["L"], w["F"], w["Y"], w["nf"], w["sy"], w["sc"]
        n = L.size
        src = derange(n, n_draws, rng)
        Lp = L[src]
        ok = np.isfinite(Y)
        Z = np.column_stack([np.ones(ok.sum()), Fo[ok]])
        M = np.eye(ok.sum()) - Z @ np.linalg.pinv(Z)
        yt = M @ Y[ok]
        Lt = Lp[:, ok] @ M
        den = (Lt * Lt).sum(axis=1)
        fm_sum += np.where(den > 0, (Lt @ yt) / np.where(den > 0, den, 1.0), 0.0)
        okl = nf > 0
        ii = np.flatnonzero(okl)
        q = ii.size // 5
        o = ii[np.argsort(-Lp[:, ii], axis=1, kind="stable")]
        top, bot = o[:, :q], o[:, -q:]
        gl = sy[top].sum(axis=1) / nf[top].sum(axis=1)
        gs = sy[bot].sum(axis=1) / nf[bot].sum(axis=1)
        cl = sc[top].sum(axis=1) / nf[top].sum(axis=1)
        cs = sc[bot].sum(axis=1) / nf[bot].sum(axis=1)
        ls_sum += gl - cl - gs - cs
        cnt += 1
    return fm_sum / max(cnt, 1), ls_sum / max(cnt, 1)


def b13_crossasset_a_industry_leadlag(archive):
    """T-596."""
    miss = _missing(archive, [SPY_B, FJA_B, SPELLS_B, SEC_TICK_B]) or \
        _prefix_missing(archive, ["daily-history-", SUBS_PREFIX])
    if miss:
        return miss
    W = t596_weeks(archive)
    S = t596_series(W["weeks"])
    fm, ls = S["fm"], S["ls"]
    n = int(fm.size)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} weeks with a usable industry cross-section")
    lag = max(T596_BLOCK, CAL.nw_lags(n))
    nfm = _nw(fm, lag)
    fm_ok = bool(fm.mean() > 0 and nfm["p"] < ALPHA)
    fm_row = (f"Fama-MacBeth leader slope {fm.mean():+.4f} > 0 with one-sided p < 0.05 (NW lag {lag} t {_s(nfm['t'], 2)}, "
              f"p {_f(nfm['p'], 4)})", fm_ok, nfm["t"] < -1.645)
    ls_row, linf = p_rows(float(ls.mean()), ls, T596_BLOCK, lag, f"net long-short mean {_bp(ls.mean(), 2)}/week > 0 with "
                                                                  f"one-sided p < 0.05")
    h1 = np.array([d < T596_SPLIT for d in S["weeks"]])
    hf = [float(fm[h1].mean()), float(fm[~h1].mean())]
    hl = [float(ls[h1].mean()), float(ls[~h1].mean())]
    rng = np.random.default_rng(SEED)
    pf, pl = t596_placebo(W["weeks"], set(S["weeks"]), N_PLACEBO, rng)
    pf95, pl95 = float(np.percentile(pf, 95)), float(np.percentile(pl, 95))
    plac_row = BW.all_constructions(
        [(f"FM slope mean {fm.mean():+.4f} vs placebo 95th pct {pf95:+.4f}", bool(fm.mean() > pf95), False),
         (f"long-short net {_bp(ls.mean(), 2)} vs placebo 95th pct {_bp(pl95, 2)}", bool(ls.mean() > pl95), False)],
        f"above the 95th percentile of the random-other-industry-leader placebo ({N_PLACEBO} draws)")
    halves_row = (f"both halves positive (FM slope 2002-2013 {hf[0]:+.4f} / 2014-2026 {hf[1]:+.4f}; long-short "
                  f"{_bp(hl[0], 2)} / {_bp(hl[1], 2)})", all(v_ > 0 for v_ in hf + hl), False)
    drow, dinfo = dsr_bound(ls, T596_FAMILY_MIN, T596_FAMILY_FULL, f"DSR > {DSR_PASS} with T-424 and T-467 counted "
                                                                    f"(weekly long-short net)")
    crit = [fm_row, ls_row, halves_row, plac_row, drow]
    v, why, crit_j = CAL._judge(crit, n, T596_MIN_N, "weeks")
    # ---- reported: pooled regression with SPY's week-t return, the size split from 2011, coverage
    pooled = t596_pooled(W, set(S["weeks"]))
    Wz = t596_weeks(archive, size=True)
    Sz = t596_series(Wz["weeks"])
    size = {"n": int(Sz["fm"].size), "fm_mean": float(Sz["fm"].mean()), "fm_t": _nw(Sz["fm"], lag)["t"],
            "ls_mean": float(Sz["ls"].mean()), "ls_t": _nw(Sz["ls"], lag)["t"]} if Sz["fm"].size > 8 else {"n": int(Sz["fm"].size)}
    n_ind = [len(w["L"]) for w in W["weeks"]]
    gross = S["gross"]
    info = W["info"]
    stat = {"n": n, "first_week": S["weeks"][0], "last_week": S["weeks"][-1], "fm_mean": float(fm.mean()), "fm_nw": nfm,
            "ls_net_mean": float(ls.mean()), "ls_gross_mean": float(gross.mean()), "ls_nw": linf["nw"],
            "ls_boot_p": linf["boot_p"], "halves_fm": hf, "halves_ls": hl, "placebo": {"fm_p95": pf95, "ls_p95": pl95,
            "fm_rank": float(np.mean(pf < fm.mean())), "ls_rank": float(np.mean(pl < ls.mean()))}, "dsr": dinfo,
            "industries_per_week": [int(min(n_ind)), int(np.median(n_ind)), int(max(n_ind))],
            "member_weeks": W["member_weeks"], "member_weeks_priced_share": W["priced_member_weeks"] / max(W["member_weeks"], 1),
            "pooled_with_spy": pooled, "size_split_2011": size,
            "filters": {"no_series": len(info["no_series"]), "not_equity": len(info["not_equity"]),
                        "name_mismatch": len(info["name_mismatch"]), "no_sic": len(info["no_sic"])},
            "sector_spdr_5m": "not computed (reported-only item)", "criteria": crit_j, "verdict": v}
    reason = (f"within-2-digit-SIC leader (top DV tercile) -> follower (bottom tercile) lead-lag on point-in-time S&P 500 "
              f"members, target weeks {S['weeks'][0]}..{S['weeks'][-1]} ({n}; {min(n_ind)}-{max(n_ind)} industries with >= "
              f"{T596_MIN_IND} names, median {int(np.median(n_ind))}): FM leader slope {fm.mean():+.4f} (NW t {_s(nfm['t'], 2)}), "
              f"halves {hf[0]:+.4f} / {hf[1]:+.4f}; quintile long-short of followers net {_bp(ls.mean(), 2)}/week (gross "
              f"{_bp(gross.mean(), 2)}; HAC t {_s(linf['nw']['t'], 2)}, bootstrap p {_f(linf['boot_p'], 4)}), halves "
              f"{_bp(hl[0], 2)} / {_bp(hl[1], 2)}; placebo 95th pcts {pf95:+.4f} (FM) and {_bp(pl95, 2)} (LS). Reported: "
              f"pooled regression with SPY's week-t return, leader t {_s((pooled.get('t') or [None, None])[1], 2)}; size split "
              f"(SEC shares, 2011+) FM {_s(size.get('fm_mean'), 4)} (t {_s(size.get('fm_t'), 2)}), LS {_bp(size.get('ls_mean'), 2)}; "
              f"{stat['member_weeks_priced_share'] * 100:.1f}% of member-weeks priced. SIC is the current SEC profile (not "
              f"point in time); prices come from today's 901-symbol set (survivor-biased; the small, neglected followers the "
              f"published effect lives in are absent from an S&P universe); the sector-SPDR 5-minute report is not computed")
    return _out(stat, n, v, reason + " — " + why)


def t596_pooled(W: dict, keep: set) -> dict:
    """Reported: pooled OLS of the followers' next-week return on [leader week-t, followers' own week-t, SPY week-t]
    over all industry-weeks, standard errors clustered by week."""
    ys, X, g = [], [], []
    for k, w in enumerate(W["weeks"]):
        if w["t1"] not in keep or w["t"] not in W["spy_week"]:
            continue
        ok = np.isfinite(w["Y"])
        for i in np.flatnonzero(ok):
            ys.append(w["Y"][i]); X.append([w["L"][i], w["F"][i], W["spy_week"][w["t"]]]); g.append(k)
    if len(ys) < 50:
        return {"n": len(ys)}
    y = np.array(ys); Xm = np.column_stack([np.ones(len(ys)), np.array(X)]); g = np.array(g)
    XtXi = np.linalg.inv(Xm.T @ Xm)
    b = XtXi @ Xm.T @ y
    e = y - Xm @ b
    S = np.zeros((4, 4))
    for c in np.unique(g):
        u = (Xm[g == c] * e[g == c][:, None]).sum(axis=0)
        S += np.outer(u, u)
    se = np.sqrt(np.diag(XtXi @ S @ XtXi))
    return {"n": int(y.size), "coef": [float(v) for v in b], "t": [float(v) for v in b / se]}


HARNESSES = {
    "b13_crossasset_a_stmom": b13_crossasset_a_stmom,
    "b13_crossasset_a_dollar_carry": b13_crossasset_a_dollar_carry,
    "b13_crossasset_a_oil_spy": b13_crossasset_a_oil_spy,
    "b13_crossasset_a_gold_platinum": b13_crossasset_a_gold_platinum,
    "b13_crossasset_a_industry_leadlag": b13_crossasset_a_industry_leadlag,
}
THEORY_MAP = {
    "T-603": "b13_crossasset_a_stmom",
    "T-605": "b13_crossasset_a_dollar_carry",
    "T-598": "b13_crossasset_a_oil_spy",
    "T-600": "b13_crossasset_a_gold_platinum",
    "T-596": "b13_crossasset_a_industry_leadlag",
}
