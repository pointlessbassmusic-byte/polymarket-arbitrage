"""
Batch 13, group ``gaps_fx``: four FX claims pre-registered from the 2026-10-20 web sweep (cluster "fximplied"): global
FX realised volatility timing the dollar basket (T-719), the US equity variance risk premium timing the dollar basket
(T-720), FX volatility innovations timing G10 carry (T-725) and the VIX-beta currency sort (T-728).
=====================================================================================================================

  * T-719  Month-end decisions 2013-01..2026-06. GV_t = mean over the 9 non-USD G10 currencies of sqrt(252 x mean
           squared daily log noon-fix change) over the 21 most recent common sessions PUBLISHED by H.10 at the decision.
           Target: the 3-month DOL excess return, mean log spot change of the 9 vs USD from the first common fix of t+1
           to the first common fix of t+4 plus 3/12 of the month t-1 OECD AFD (flagged approximation). Expanding OLS
           from 2002-06 (each fit uses only targets whose end fix H.10 had published by the decision), 162 forecasts.
           Pass: Clark-West one-sided p < 0.05 (Newey-West lag 2), OOS R^2 > 0 (claim and null), the forecast-sign DOL
           rule's net Sharpe > 0 over the whole window (the claim) and in 2013-2019 and in 2020-2026, DSR >= 0.95 over
           the 6-trial DOL family. min_n 150.
  * T-720  Month-end decisions at the month's last NYSE session t, 2012-01..2026-08. VP_t = VIX_t^2/12 - 10,000 x the
           sum of squared ^GSPC daily log returns over the 21 sessions ending at t (monthly %^2). Target: the next-month
           DOL excess return, mean log spot change from the first common fix after t to the first common fix after the
           next month's last session, plus 1/12 of the month t-1 AFD. Pass: post-sample slope on standardised VP > 0
           with Newey-West (lag 2) one-sided p < 0.05; Clark-West one-sided p < 0.05 for the expanding OLS (from
           2002-06); OOS R^2 > 0 (null); slope > 0 in 2012-2018 and 2019-2026; DSR >= 0.95 over the same 6-trial DOL
           family (judged on the registered trading arm). min_n 170.
  * T-725  Holding months 2013-01..2026-09. Base: T-368's G10 carry book (USD in the universe, top 3 minus bottom 3,
           equal weight, 2 bp per unit traded and 1%/yr per non-USD leg) ranked on 3-month rates known at each
           decision. GV_t = mean over the 9 of the average |daily log change| over the common sessions of month t
           published by H.10 by the decision; u_t = its real-time AR(1) residual (expanding from 1999-06); weight 0 in
           month t+1 when u_t exceeds its expanding 80th percentile, else 1; switches at the first common fix of t+1 at
           2 bp per leg per switch on top of T-368's costs. Pass: Sharpe(timed) - Sharpe(untimed) > 0 with paired
           stationary-bootstrap (mean block 12, 5,000 draws) one-sided p < 0.05; gain > 0 in 2013-2019 and 2020-2026;
           timed Sharpe above the VIX > 30 filter on the same base; DSR >= 0.95 over 12 trials. min_n 150.
  * T-728  Holding months 2013-01..2026-09, 11 currencies (9 G10 + MXN + ZAR) vs USD. Beta_c = OLS slope of the
           currency's monthly excess return (month-end common fixes) on the monthly change in the month-end VIX close
           over the 60 months ending t-1. Long the 3 lowest, short the 3 highest betas, filled at the first common fix
           of t+1, held to the first common fix of t+2; T-368/T-431 costs. Pass: net Sharpe > 0.3; stationary-bootstrap
           95% lower bound > 0; alpha HAC t > 2 vs carry (T-368 construction on point-in-time rates) and DOL; both halves
           (2013-2019, 2020-2026) positive; DSR > 0.95 over 27 trials (T-368 6, T-431 4, T-478 16, this one). min_n 150.

Readings fixed before any run (the registrations are silent or ambiguous, or the registered data are missing; each is
the conservative reading and is repeated in the reasons):
  * H.10 publication (T-719, T-720 controls, T-725, T-728). FRED's daily H.10 rows are archived available the same day,
    but H.10 is a WEEKLY release: a fix is treated as public only from the Monday after its week (16:15 ET), moved to
    the next federal business day when that Monday is a federal holiday (``h10_release``), for the whole sample (the
    registered rule; if the rates were public sooner in early years this is only stricter). A fix released on the
    decision day counts (the month-end decision is taken after the close; VIX itself is public at 21:30 UTC).
    Expanding fits use a target only once its END fix is published by the decision. Execution prices (the fill and
    exit fixes) are observed at the trade, as every FX harness here assumes.
  * Common sessions: every FX statistic uses the days on which every currency of its universe prints ("only months in
    which all currencies print"); a month without the needed common fixes is skipped.
  * Point-in-time 3-month rates. The registrations require ALFRED vintages of the OECD IR3TIB01 rates; they are NOT
    archived (only the IRLTLT01 10-year vintages are). When ``alfred-IR3TIB01*`` bundles for all 10 G10 rates exist the
    harnesses use them (the vintage in force at the decision, ``batch6c_rates.Vintages``). Otherwise a PROXY: the rate
    of country-month m counts as known from the first ALFRED release of the same country-month's IRLTLT01 (for months
    before ALFRED's 2013-06-03 start, the fetcher's period-end + 45 days rule), with the latest-vintage IR3TIB01 value
    (revisions unmeasured; EUR is clocked by Germany's release). IRLTLT01 is a different OECD MEI series and its first
    releases need not coincide with IR3TIB01's: the proxy can run AHEAD of the real IR3TIB01 publication as well as
    behind it (at capture, fx-rates-3m JPY ends at 2026-07 while IRLTLT01JP 2026-08 had already been first-released;
    US/DE IRLTLT01 months in 2015-2016 often first-print within 3 days of month-end, and no IR3TIB01 vintage exists to
    confirm the same). So the proxy is not a point-in-time clock in either direction. A criterion that rests on those
    ranks (T-725's base book; T-728's carry alpha) can then FAIL but never PASS: a pass on the proxy reads undecided and
    an explicit "registered vintages" row stays undecided, so the verdict is at best inconclusive. Beside the proxy, a
    fixed rank lag is reported (``LagRates``: the month t-2 rate at a month-t decision, latest vintage; report only)
    for T-725's books and T-728's carry control. T-719 and T-720 need the vintages only for their reported AFD
    controls (the same proxy clock).
  * Rate accruals are outcomes, not signals: T-719 and T-720 add the month t-1 OECD averages (T-719's registration and
    T-605's precedent); T-725 and T-728 use T-368's leg convention (the average of the month that ends just before the
    position opens). EUR and GBP stop printing after 2026-01 (JPY after 2026-07): accruals forward-fill at most 12
    months, the affected months are counted and a through-2026-01 figure is reported. The accrual stands in for the
    forward points, a market price known when each position opens, so inside T-728's beta window (a signal) the past
    months' accruals use the same averages; only RANKS on rates (T-725's book, T-728's carry control) need the
    publication clock.
  * Costs. T-719 / T-720 sign rules: 2 bp per unit of notional traded (2 bp entry, 4 bp on a long/short flip, 2 bp
    final close) plus 1 bp a month roll while invested (the per-switch reading; T-605 charged every leg monthly because
    its registration said "per rebalance"). T-725: T-368's turnover cost on the timed weights plus 2 bp on every
    non-USD leg's notional at each switch (on or off), the VIX > 30 control paying the same; no switch charge at the
    window's first month. T-728: "Costs as in T-368/T-431" (2 bp per unit traded on G10 legs, 5 bp on MXN/ZAR; 1%/yr
    per leg, 2% for ZAR); the claim's flat 2 bp / 1%/yr reading is reported.
  * T-719: the sign rule re-reads the 3-month forecast's sign every month and holds one month (first fix of t+1 to the
    first fix of t+2) - the claim's "per switch" costs imply a monthly re-decision. The claim's full-sample net Sharpe
    and the registered halves are all criteria. The overlapping 3-month-tranche reading (each month's sign held 3
    months in thirds, ``tranche_positions``) is reported beside it. "Halves" = decision months 2013-2019 / 2020-2026.
    The Hodrick (1992) t uses the 1-month log excess returns summed over 3 months; EVZ is not
    archived, so the EVZ variant is not computed. The encompassing regression is the in-sample OLS over the forecast
    decisions of the 3-month target on GV, the point-in-time AFD and the VIX level (NW lag 2).
  * T-720: the target window starts at the first common fix strictly after t and ends at the first common fix strictly
    after the next decision session (so Good-Friday month-ends start the hold on Good Friday, which H.10 prints). The
    slope's VP is standardised over the 2012-01..2026-08 decisions; halves 2012-2018 / 2019-2026 by decision. The Clark-
    West t uses Newey-West lag 2, as the slope. The registration's only trading strategy is the reported 60-month-median
    arm (long DOL when VP_t exceeds the median of VP over the 60 previous decisions, else short), so its net return is
    the DSR series; the 3-month horizon trial's Sharpe is the same signal held in three overlapping one-third tranches.
    "Last-month DOL return (published fixes)" = the basket log change between the last fixes H.10 had published at the
    previous decision and at this one. The accrual's US leg is the month t-1 OECD IR3TIB01 US rate from fx-rates-3m
    (fixed before the first run: the same interbank series and month as the foreign legs and T-719's registered
    "month t-1 OECD averages"). The registration's data line also names fred-DTB3, so the DTB3 reading (the month t-1
    average of the daily DTB3 prints, all public by the decision) is reported beside every judged figure; it is not
    judged. The per-currency panel with currency fixed effects is reported as a pooled within-currency slope with SEs
    clustered by month (``fe_panel_slope``), beside the nine per-currency Newey-West slopes.
  * DOL-target DSR family (T-719, T-720; 6 trials): T-605's two dollar-carry books (``batch13_crossasset_a``), T-575 in
    its trading form (long the 9-currency basket on the last two trading days of each month, monthly sums), T-720's 1-
    and 3-month arms and T-719's rule; per-period Sharpes; trial-Sharpe variance floored at 1/(T-1)
    (``batch6c_mom.family_dsr``).
  * T-725: GV averages the published sessions' absolute daily log changes (a session's change is from the previous
    common session, which may lie in month t-1). u_t is the residual at t of the AR(1) fitted on the pairs (GV_{s-1},
    GV_s), s = 1999-06..t; the residual history behind the percentile is each month's own real-time residual (fits of
    at least 24 pairs), u_t included. The base and timed books are both held from the first common fix of month H to
    the first common fix of H+1 (the switch date the registration names; T-368's own month-end-fix book is reported
    beside them as "the frozen non-vintage book"). The VIX > 30 control uses the last VIX close dated on or before the
    decision day. The Sharpe-difference p is the centred paired stationary bootstrap (H0: difference <= 0), 5,000 draws
    per seed, escalated by seeds while its Monte Carlo band straddles 0.05. The DSR family's T-682 Sharpe is not a
    monthly return series and is not computed: the DSR is judged at the most favourable trial-Sharpe variance that the
    missing member allows (it can fail, never pass). The random-switch placebo keeps the number of flat months and
    redraws their positions (1,000 draws, costs recomputed). A Sharpe gain (each half, each placebo draw, the
    through-2026-01 figure) exists only when both Sharpes do; otherwise it is undecided (None), never 0. Beside the
    proxy book, the same rule on fixed month t-2 ranks (``LagRates``) is reported. Bakshi-Panayotov (reported): expanding OLS of the next
    month's base-book net return on the change in GV and DBC's month-t return (DBC used only when its close precedes the
    fill day), Clark-West vs the prevailing mean.
  * T-728: monthly excess returns run month-end common fix to month-end common fix; dVIX = change in the VIX close of the
    month's last session. Betas need all 60 months. "Alpha HAC t > 2 vs carry and DOL" is judged under every reading
    (rule 11): the two-factor regression and each single-factor one, at the automatic Newey-West lag and at lag 12; the
    carry factor is T-368's book on point-in-time ranks held on the T-728 calendar, gross of costs (its costs would only
    add to alpha; the alpha against a carry factor ranked on fixed month t-2 rates is reported); DOL is the
    equal-weight 11-currency basket (the 9-currency G10 DOL is reported). The holding month H's betas are row H-1 of
    ``rolling_betas`` (``t728_decision_beta``): the 60 months H-61..H-2, a one-month skip. "DSR counting ..."
    uses the house bar > 0.95. Controls (reported): the static full-sample beta ranking, the shuffled-VIX placebo (dVIX
    permuted across months, 1,000 draws), the claim-literal costs, rank correlation of betas with month t-1 rate ranks.
    A fail on the VIX-change proxy does not refute the paper's put-based factor.
  * DSR families with a member this module cannot compute (T-682's DiD is not a monthly return series; T-431's "+KRW"
    trial has no archived KRW) are judged by ``family_dsr_row``: the DSR at the lowest trial-Sharpe variance the
    missing members allow (the 1/(T-1) floor, or the computed variance shrunk as if every missing Sharpe sat at the
    computed mean) bounds it from above, so the criterion can fail but never pass (T-725, T-728). T-719 / T-720's
    6-trial DOL family is fully computed.
  * Added after the 2026-10-21 review (each only adds a criterion the claim names or a reported figure; none changes a
    judged construction or threshold): T-719's full-sample rule Sharpe row and tranche reading; T-720's DTB3 reading and
    pooled fixed-effects slope; the fixed month t-2 rank-lag sensitivity (T-725, T-728); None instead of 0 for a gain
    whose Sharpe is undefined (T-725), and for a placebo draw with zero variance (T-725, T-728).
  * House rule 10: every claim names a calendar (month-ends), so there is no free grid phase. No cross-sectional stock
    universe is used (no survivorship issue). Below trial.min_n the verdict is never supported and a failing criterion
    counts only when decisive (``batch6c_cal._judge``, house rule 5).
"""

from __future__ import annotations

import bisect
import calendar
import math
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch11_xasset as X11
from mandel.experiments import batch13_crossasset_a as XA
from mandel.experiments import batch13_implied_b as IB
from mandel.experiments import batch5_fx as FX
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch6c_rates as RATES
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()

SPOT_B = "fx-spot-g10"
RATE_B = "fx-rates-3m"
VIX_B = "cboe-VIX-history"
GSPC_B = "daily-history--GSPC"
DBC_B = "daily-history-DBC"
EVZ_B = "cboe-EVZ-history"
DTB3_B = "fred-DTB3"
RANK_LAG = 2                              # the fixed rank-lag sensitivity: month t-2 rates at a month-t decision

G9 = ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")
EM2 = ("MXN", "ZAR")
U11 = G9 + EM2
G10U = tuple(FX.G10)                      # T-368's universe with USD, in its tie order

CLOCK_CC = {"USD": "US", "EUR": "DE", "GBP": "GB", "JPY": "JP", "CAD": "CA", "AUD": "AU", "CHF": "CH", "SEK": "SE",
            "NOK": "NO", "NZD": "NZ"}
VINT_SID = {"USD": "IR3TIB01USM156N", "EUR": "IR3TIB01EZM156N", "GBP": "IR3TIB01GBM156N", "AUD": "IR3TIB01AUM156N",
            "NZD": "IR3TIB01NZM156N", "JPY": "IR3TIB01JPM156N", "CHF": "IR3TIB01CHM156N", "CAD": "IR3TIB01CAM156N",
            "NOK": "IR3TIB01NOM156N", "SEK": "IR3TIB01SEM156N"}

LEG = 2e-4                                # sign rules: per unit of notional traded
ROLL = 1e-4                               # per month invested
MIN_TRAIN = 24
MAX_FILL = 12
STALE_THROUGH = "2026-01"

# T-719
T719_FIT_FROM = "2002-06"
T719_OOS = ("2013-01", "2026-06")
T719_RV_N = 21
T719_SPLIT = "2020-01"
T719_MIN_N = 150
T719_EXCL = tuple(XA.mrange("2008-09", "2009-03")) + ("2020-03",) + tuple(XA.mrange("2022-01", "2022-12"))
# T-720
T720_FIT_FROM = "2002-06"
T720_OOS = ("2012-01", "2026-08")
T720_SPLIT = "2019-01"
T720_MIN_N = 170
T720_MED_WIN = 60
T720_EXCL = tuple(XA.mrange("2008-09", "2009-03")) + tuple(XA.mrange("2020-03", "2020-06"))
T720_N_SHUF = 1000
DOL_N_TRIALS = 6
# T-725
T725_HOLD = ("2013-01", "2026-09")
T725_AR_FROM = "1999-06"
T725_PCT = 80.0
T725_SPLIT = "2020-01"
T725_MIN_N = 150
T725_N_TRIALS = 12
T725_UNCOMPUTED = ("T-682",)
T725_BLOCK = 12.0
T725_NBOOT = 5000
T725_N_PLACEBO = 1000
T725_SWITCH = 2e-4
T725_VIX_CUT = 30.0
T725_BP_FROM = "2002-06"
# T-728
T728_HOLD = ("2013-01", "2026-09")
T728_BETA_N = 60
T728_K = 3
T728_SR_BAR = 0.3
T728_T_BAR = 2.0
T728_SPLIT = "2020-01"
T728_MIN_N = 150
T728_N_TRIALS = 27
T728_N_PLACEBO = 1000

madd, mrange, _mi = XA.madd, XA.mrange, XA._mi
_f, _s, _pc = XA._f, XA._s, XA._pc


def month_end_day(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()


def _sr(x, ppy: int = 12) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x, ppy)) if x.size > 2 and x.std() > 0 else None


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


# ============================================================================================== H.10 calendar ==

@lru_cache(maxsize=None)
def federal_holidays(y: int) -> frozenset:
    """Observed US federal holidays dated in year ``y`` (a Saturday holiday is observed the Friday before, a Sunday one
    the Monday after): New Year's Day, King's Birthday (from 1986), Washington's Birthday, Memorial Day, Juneteenth (from
    2021), Independence Day, Labor Day, Columbus Day, Veterans Day, Thanksgiving and Christmas."""
    def obs(d: date) -> date:
        return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d
    hs = {obs(date(y, 1, 1)), CAL._nth_weekday(y, 2, 0, 3), CAL._last_weekday_of(y, 5, 0), obs(date(y, 7, 4)),
          CAL._nth_weekday(y, 9, 0, 1), CAL._nth_weekday(y, 10, 0, 2), obs(date(y, 11, 11)), CAL._nth_weekday(y, 11, 3, 4),
          obs(date(y, 12, 25)), obs(date(y + 1, 1, 1))}
    if y >= 1986:
        hs.add(CAL._nth_weekday(y, 1, 0, 3))
    if y >= 2021:
        hs.add(obs(date(y, 6, 19)))
    return frozenset(d for d in hs if d.year == y)


def is_fed_business(d: date) -> bool:
    return d.weekday() < 5 and d not in federal_holidays(d.year)


@lru_cache(maxsize=None)
def h10_release(day: str) -> str:
    """The H.10 weekly release that first carries the noon fix of ``day``: the Monday after the fix's week (16:15 ET), the
    next federal business day when that Monday is a federal holiday."""
    d = date.fromisoformat(day)
    r = d + timedelta(days=7 - d.weekday())
    while not is_fed_business(r):
        r += timedelta(days=1)
    return r.isoformat()


# ================================================================================================= data access ==

def _spot(archive) -> dict:
    """{ccy: {day: USD per unit}} of the H.10 noon fixes available when the bundle was captured."""
    def load():
        by: dict = defaultdict(dict)
        for r in CAL._rows(archive, SPOT_B):
            v = r.get("value") or {}
            try:
                x = float(v.get("usd_per_unit"))
            except (TypeError, ValueError):
                continue
            if v.get("ccy") and v.get("day") and math.isfinite(x) and x > 0:
                by[v["ccy"]][v["day"]] = x
        return dict(by)
    return CAL._cached(archive, ("b13_gaps_fx", "spot"), load)


def common_panel(spot: dict, ccys: Sequence[str]) -> dict:
    """Common-session panel of ``ccys``: days on which every currency prints, X (days x ccys) USD per unit, L = log X,
    rel = the H.10 release day of each row (non-decreasing), first / last row of each month."""
    ccys = tuple(ccys)
    sets = [set(spot.get(c, {})) for c in ccys]
    days = sorted(set.intersection(*sets)) if sets and all(sets) else []
    X = np.array([[spot[c][d] for c in ccys] for d in days], float).reshape(len(days), len(ccys))
    first, last = {}, {}
    for i, d in enumerate(days):
        first.setdefault(d[:7], i)
        last[d[:7]] = i
    return {"ccys": ccys, "days": days, "X": X, "L": np.log(X) if X.size else X, "rel": [h10_release(d) for d in days],
            "first": first, "last": last}


def _panel(archive, ccys: Sequence[str]) -> dict:
    return CAL._cached(archive, ("b13_gaps_fx", "panel", tuple(ccys)), lambda: common_panel(_spot(archive), ccys))


def pub_idx(P: dict, D: str) -> int:
    """Index of the last common session H.10 had published by day ``D`` (-1 when none)."""
    return bisect.bisect_right(P["rel"], D) - 1


def after_idx(P: dict, day: str) -> Optional[int]:
    """Index of the first common session strictly after ``day``."""
    i = bisect.bisect_right(P["days"], day)
    return i if i < len(P["days"]) else None


def _rates(archive) -> dict:
    """{ccy: (sorted months, {month: OECD 3-month rate, percent})}, latest vintage (``fx-rates-3m``)."""
    def load():
        by: dict = defaultdict(dict)
        for r in CAL._rows(archive, RATE_B):
            v = r.get("value") or {}
            try:
                x = float(v.get("rate3m"))
            except (TypeError, ValueError):
                continue
            if v.get("ccy") and v.get("month") and math.isfinite(x):
                by[v["ccy"]][v["month"]] = x
        return {c: (sorted(d), d) for c, d in by.items()}
    return CAL._cached(archive, ("b13_gaps_fx", "rates"), load)


def rate_at(R: dict, c: str, m: str, max_fill: int = MAX_FILL) -> tuple:
    """(rate of month m, forward-filled?): the latest print at or before m, at most ``max_fill`` months old."""
    ms, d = R.get(c, ([], {}))
    if m in d:
        return d[m], False
    i = bisect.bisect_right(ms, m) - 1
    if i < 0 or _mi(m) - _mi(ms[i]) > max_fill:
        return None, False
    return d[ms[i]], True


def rate_vec(R: dict, ccys: Sequence[str], m: str) -> np.ndarray:
    """Rates of month m (forward-filled at most 12 months), NaN where missing."""
    out = np.full(len(ccys), np.nan)
    for k, c in enumerate(ccys):
        v = rate_at(R, c, m)[0]
        if v is not None:
            out[k] = v
    return out


def afd_acc(R: dict, ccys: Sequence[str], m: str, us_rate: Optional[dict] = None) -> tuple:
    """(mean foreign minus US 3-month rate of month m in percent, forward-filled currencies) - an outcome accrual. The US
    leg is R's USD rate, or ``us_rate[m]`` ({month: percent}, e.g. the DTB3 monthly average) when given."""
    if us_rate is None:
        us, fu = rate_at(R, "USD", m)
    else:
        us, fu = us_rate.get(m), False
    vals, filled = [], ([] if not fu else ["USD"])
    for c in ccys:
        v, fl = rate_at(R, c, m)
        if v is None:
            return None, filled
        vals.append(v)
        if fl:
            filled.append(c)
    if us is None:
        return None, filled
    return float(np.mean(vals)) - float(us), filled


def month_avg(series: dict) -> dict:
    """{month: mean of the daily prints dated in that month} of a {day: value} series (e.g. FRED DTB3)."""
    acc: dict = defaultdict(list)
    for d, v in series.items():
        acc[d[:7]].append(float(v))
    return {m: float(np.mean(v)) for m, v in acc.items() if v}


def _dtb3_month(archive) -> Optional[dict]:
    """Month averages of fred-DTB3 (None when the bundle is missing)."""
    if not B7C._has(archive, DTB3_B):
        return None
    return CAL._cached(archive, ("b13_gaps_fx", "dtb3_month"), lambda: month_avg(CAL._series(archive, DTB3_B)))


# ---------------------------------------------------------------------------------------- point-in-time rates --

def _alfred_rows(archive, name: str) -> list:
    return CAL._cached(archive, ("b13_gaps_fx", "alfred", name), lambda: [r["value"] for r in CAL._rows(archive, name)])


def first_release_days(values: Sequence[dict]) -> dict:
    """{month: day of the first ALFRED release} (a first-vintage row counts from min(realtime_start, lag_rule_at))."""
    out: dict = {}
    for v in values:
        if not v.get("first_release") or not v.get("day") or not v.get("realtime_start"):
            continue
        rs, lag = str(v["realtime_start"])[:10], v.get("lag_rule_at")
        day = min(rs, str(lag)[:10]) if (v.get("first_vintage") and lag) else rs
        m = v["day"][:7]
        out[m] = min(out.get(m, "9999-12-31"), day)
    return out


def vintage_obs(values: Sequence[dict]) -> dict:
    """``batch6c_rates.Vintages`` input from ALFRED rows."""
    obs: dict = {}
    for v in values:
        if not v.get("day") or not v.get("realtime_start"):
            continue
        x = v.get("value")
        try:
            x = None if x is None else float(x)
        except (TypeError, ValueError):
            x = None
        lag = v.get("lag_rule_at")
        obs.setdefault(v["day"][:7], []).append((str(v["realtime_start"])[:10], str(v.get("realtime_end") or "9999-12-31")[:10],
                                                  x, bool(v.get("first_vintage")), str(lag)[:10] if lag else None))
    for m in obs:
        obs[m].sort()
    return obs


class PitRates:
    """3-month rates known at a day. mode 'vintage': the registered ALFRED IR3TIB01 vintages; 'proxy': the month known
    is the latest whose same-country IRLTLT01 first release is on or before the day (``rel`` {ccy: {month: day}}), with
    the latest-vintage ``fx-rates-3m`` value (forward-filled at most 12 months; flagged). IRLTLT01's release can lead
    IR3TIB01's as well as lag it, so the proxy is not point-in-time in either direction (it can refute, not support)."""

    def __init__(self, mode: str, R: dict, rel: Optional[dict] = None, vint: Optional[dict] = None):
        self.mode, self.R, self.vint = mode, R, vint or {}
        self._rd, self._mm = {}, {}
        for c, d in (rel or {}).items():
            items = sorted((day, m) for m, day in d.items())
            run, mm = "", []
            for _, m in items:
                run = max(run, m)
                mm.append(run)
            self._rd[c], self._mm[c] = [x[0] for x in items], mm

    def known(self, c: str, D: str) -> tuple:
        """(observation month, rate, stale?) known at day D."""
        if self.mode == "vintage":
            v = self.vint.get(c)
            if v is None:
                return None, None, False
            m, x = v.latest(D)
            return m, x, False
        rd = self._rd.get(c)
        if not rd:
            return None, None, False
        i = bisect.bisect_right(rd, D) - 1
        if i < 0:
            return None, None, False
        m = self._mm[c][i]
        x, filled = rate_at(self.R, c, m)
        return m, x, bool(filled)

    def afd(self, ccys: Sequence[str], D: str) -> Optional[float]:
        us = self.known("USD", D)[1]
        vals = [self.known(c, D)[1] for c in ccys]
        if us is None or any(v is None for v in vals):
            return None
        return float(np.mean(vals)) - float(us)


class LagRates:
    """Sensitivity clock (report only): at a decision day D in month t the rate known is month t - ``lag``'s
    latest-vintage ``fx-rates-3m`` value (forward-filled at most 12 months; flagged). Same interface as ``PitRates``."""

    def __init__(self, R: dict, lag: int = RANK_LAG):
        self.R, self.lag = R, int(lag)
        self.mode = f"fixed month t-{self.lag}"

    def known(self, c: str, D: str) -> tuple:
        m = madd(D[:7], -self.lag)
        x, filled = rate_at(self.R, c, m)
        return (m if x is not None else None), x, bool(filled)

    def afd(self, ccys: Sequence[str], D: str) -> Optional[float]:
        return PitRates.afd(self, ccys, D)


def _pit(archive) -> Optional[PitRates]:
    def load():
        R = _rates(archive)
        if all(B7C._has(archive, "alfred-" + VINT_SID[c]) for c in G10U):
            vint = {c: RATES.Vintages(vintage_obs(_alfred_rows(archive, "alfred-" + VINT_SID[c]))) for c in G10U}
            return PitRates("vintage", R, vint=vint)
        names = {c: f"alfred-IRLTLT01{CLOCK_CC[c]}M156N" for c in G10U}
        if all(B7C._has(archive, n) for n in names.values()):
            return PitRates("proxy", R, rel={c: first_release_days(_alfred_rows(archive, n)) for c, n in names.items()})
        return None
    return CAL._cached(archive, ("b13_gaps_fx", "pit"), load)


def clock_bundles() -> list:
    return [f"alfred-IRLTLT01{CLOCK_CC[c]}M156N" for c in G10U]


# ================================================================================================= statistics ==

def expanding_fc(X, y, kday, dday, train, origins, min_train: int = MIN_TRAIN) -> tuple:
    """Expanding OLS forecasts of y on [1, X] (X: one or more columns). At origin j the fit uses rows i with ``train``,
    finite X and y, and a target known by the decision (kday[i] <= dday[j], ISO days). Returns (model forecast,
    prevailing mean, first slope)."""
    X = np.asarray(X, float)
    X = X.reshape(X.shape[0], -1)
    y = np.asarray(y, float)
    M = y.size
    kd = np.array([k or "9999-12-31" for k in kday])
    fm, fb, sl = np.full(M, np.nan), np.full(M, np.nan), np.full(M, np.nan)
    fin = np.isfinite(X).all(axis=1)
    ok = np.asarray(train, bool) & fin & np.isfinite(y)
    for j in np.where(np.asarray(origins, bool) & fin)[0]:
        m = ok & (kd <= dday[j])
        if m.sum() < max(min_train, X.shape[1] + 3):
            continue
        Z = np.column_stack([np.ones(int(m.sum())), X[m]])
        b = np.linalg.lstsq(Z, y[m], rcond=None)[0]
        fb[j] = float(y[m].mean())
        sl[j] = float(b[1])
        fm[j] = float(b[0] + X[j] @ b[1:])
    return fm, fb, sl


def shift(x, k: int) -> np.ndarray:
    """x lagged k rows (NaN where undefined)."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    if k < x.size:
        out[k:] = x[:x.size - k]
    return out


def _gain(a, b) -> Optional[float]:
    """Sharpe(a) - Sharpe(b), annualised; None unless both Sharpes are defined (never a silent 0)."""
    sa, sb = _sr(a), _sr(b)
    return None if sa is None or sb is None else sa - sb


def tranche_positions(s, J) -> np.ndarray:
    """Overlapping 3-month tranches of a monthly sign ``s`` (one entry per decision row) at rows ``J``: the mean of the
    signs decided at rows j-2, j-1 and j (each held three months in thirds), NaN unless all three exist."""
    s = np.asarray(s, float)
    out = np.full(len(J), np.nan)
    for k, j in enumerate(J):
        if j >= 2 and np.isfinite(s[j - 2:j + 1]).all():
            out[k] = float(np.mean(s[j - 2:j + 1]))
    return out


def fe_panel_slope(Y, x) -> dict:
    """Pooled OLS slope of Y[j, c] on x[j] with currency fixed effects (each currency's y and x demeaned over its own
    finite rows), standard error clustered by row j (month; CR1 small-sample factor), one-sided p (H0: slope <= 0)."""
    Y, x = np.asarray(Y, float), np.asarray(x, float)
    ok = np.isfinite(Y) & np.isfinite(x)[:, None]
    keep = ok.sum(axis=0) >= 3
    ok = ok & keep[None, :]
    N, G, C = int(ok.sum()), int(ok.any(axis=1).sum()), int(keep.sum())
    out = {"n_obs": N, "n_months": G, "n_ccy": C, "b": None, "t": None, "p": None}
    if G < 12 or N < C + 4:
        return out
    Xb = np.where(ok, x[:, None], 0.0)
    Yb = np.where(ok, Y, 0.0)
    cnt = np.maximum(ok.sum(axis=0), 1)
    xd = np.where(ok, Xb - Xb.sum(axis=0) / cnt, 0.0)
    yd = np.where(ok, Yb - Yb.sum(axis=0) / cnt, 0.0)
    sxx = float((xd * xd).sum())
    if not sxx > 0:
        return out
    b = float((xd * yd).sum() / sxx)
    e = np.where(ok, yd - b * xd, 0.0)
    score = (xd * e).sum(axis=1)
    V = float(score @ score) / sxx ** 2 * G / (G - 1) * (N - 1) / max(1, N - C - 1)
    t = b / math.sqrt(V) if V > 0 else None
    out.update(b=b, t=t, p=None if t is None else float(1.0 - _N.cdf(t)))
    return out


def position_net(pos, ret, leg: float = LEG, roll: float = ROLL, roll_units=None) -> tuple:
    """(net, gross) of positions ``pos`` (units of notional, sign = direction) on period returns ``ret``: ``leg`` per unit
    of notional traded (entry, every change, the final close) and ``roll`` per unit held (``roll_units`` overrides)."""
    pos, ret = np.asarray(pos, float), np.asarray(ret, float)
    if pos.size == 0:
        return np.zeros(0), np.zeros(0)
    prev = np.r_[0.0, pos[:-1]]
    held = np.abs(pos) if roll_units is None else np.asarray(roll_units, float)
    cost = leg * np.abs(pos - prev) + roll * held
    cost[-1] += leg * abs(pos[-1])
    gross = pos * ret
    return gross - cost, gross


def hodrick_t(r1, x, k: int, mask=None) -> dict:
    """Hodrick (1992) 1B t of b in sum_{i<k} r1[j+i] = a + b x[j] + e over rows j (``mask``): the one-period residuals
    under the null (r1 demeaned) times the sum of the k lagged regressors."""
    r1, x = np.asarray(r1, float), np.asarray(x, float)
    n = r1.size
    mk = np.ones(n, bool) if mask is None else np.asarray(mask, bool)
    rows = [j for j in range(n) if mk[j] and np.isfinite(x[j]) and j + k <= n and np.isfinite(r1[j:j + k]).all()]
    if len(rows) < 12:
        return {"n": len(rows), "b": None, "t": None}
    J = np.array(rows)
    yk = np.array([r1[j:j + k].sum() for j in rows])
    Z = np.column_stack([np.ones(J.size), x[J]])
    b = np.linalg.lstsq(Z, yk, rcond=None)[0]
    srow = [j for j in rows if j - k + 1 >= 0 and np.isfinite(x[j - k + 1:j + 1]).all()]
    eps = r1[srow] - r1[srow].mean()
    W = np.array([[k, x[j - k + 1:j + 1].sum()] for j in srow])
    S = (W * (eps ** 2)[:, None]).T @ W / len(srow)
    Q = Z.T @ Z / J.size
    Qi = np.linalg.inv(Q)
    V = Qi @ S @ Qi / J.size
    se = math.sqrt(V[1, 1]) if V[1, 1] > 0 else float("nan")
    return {"n": int(J.size), "b": float(b[1]), "t": float(b[1] / se) if se > 0 else None}


def nw_slope(y, x, lag: int) -> dict:
    """OLS slope of y on [1, x] with its Newey-West t and one-sided p (H0: slope <= 0)."""
    r = XA.ols_nw_all(y, np.asarray(x, float), lag)
    if r.get("t") is None:
        return {"n": r["n"], "b": None, "t": None, "p": None}
    t = r["t"][1]
    return {"n": r["n"], "b": r["coef"][1], "t": t, "p": float(1.0 - _N.cdf(t)) if math.isfinite(t) else None}


def sb_ci(x, reps: int = 5) -> dict:
    """Stationary-bootstrap (mean block 12, 5,000 draws) 95% interval of the annualised Sharpe, seeds averaged."""
    return XA._sb_sharpe(np.asarray(x, float), reps)


def sb_sharpe_diff(a, b, mean_block: float = T725_BLOCK, n_boot: int = T725_NBOOT, seed: int = SEED,
                   n_seeds: int = 5) -> dict:
    """Annualised Sharpe(a) - Sharpe(b) with a paired stationary bootstrap (Politis-Romano, geometric blocks of mean
    ``mean_block``): one-sided centred p's (p: H0 diff <= 0; p_lt: H0 diff >= 0), ``n_boot`` draws per seed, escalated by
    seeds while either p is undecided (``batch6c_cal.escalate_p``); the percentile 95% interval of the first seed."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = a.size
    out = {"n": int(n), "diff": None, "p": None, "p_lt": None, "draws": 0, "ci": [None, None],
           "sharpe_a": _sr(a), "sharpe_b": _sr(b)}
    if n < 8 or out["sharpe_a"] is None or out["sharpe_b"] is None:
        return out
    d0 = out["sharpe_a"] - out["sharpe_b"]
    out["diff"] = d0
    keep = {}

    def batch(k):
        rng = np.random.default_rng(seed + k)
        idx = BW._stationary_idx(rng, n, mean_block, n_boot)
        A, B = a[idx], b[idx]
        sa, sb = A.std(axis=1, ddof=1), B.std(axis=1, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = (np.where(sa > 0, A.mean(axis=1) / np.where(sa > 0, sa, 1.0), 0.0)
                  - np.where(sb > 0, B.mean(axis=1) / np.where(sb > 0, sb, 1.0), 0.0)) * math.sqrt(12)
        if k == 0:
            keep["ci"] = [float(np.quantile(dd, 0.025)), float(np.quantile(dd, 0.975))]
        c = dd - d0
        return float((np.sum(c >= d0) + 1) / (n_boot + 1)), float((np.sum(c <= d0) + 1) / (n_boot + 1))

    pg, pl, nd = CAL.escalate_p(batch, n_boot, n_seeds, CAL.MAX_SEEDS)
    out.update(p=pg, p_lt=pl, draws=nd, ci=keep.get("ci", [None, None]))
    return out


def family_dsr_row(x, family_sharpes: Sequence, n_trials: int, n_extra_uncomputed: int, label: str,
                   ge: bool = True) -> tuple:
    """The DSR criterion over a trial family whose per-period Sharpes are ``family_sharpes`` (None = not computable)
    plus ``n_extra_uncomputed`` members not computed here. With every member computed: ``batch6c_mom.family_dsr`` (the
    1/(T-1) floor) judged at ``ge`` (>= 0.95) or > 0.95; otherwise ``dsr_partial``. Returns ((name, ok, decisive), info)."""
    fs = [float(s) for s in family_sharpes if s is not None and math.isfinite(s)]
    n_unc = int(n_extra_uncomputed) + (len(family_sharpes) - len(fs))
    if n_unc == 0:
        d = MOM.family_dsr(x, fs, n_trials)
        return (IB.dsr_row_ge(d, label) if ge else MOM.dsr_row(d, label)), d
    return dsr_partial(x, fs, n_trials, n_unc, label, strict=not ge)


def dsr_partial(x, family_sharpes: Sequence[float], n_trials: int, n_uncomputed: int, label: str,
                strict: bool = False) -> tuple:
    """'DSR >= 0.95' (``strict``: > 0.95) when ``n_uncomputed`` family Sharpes are not computed: the trial-Sharpe
    variance can be no lower than max(1/(T-1), v_c (m-1)/(m+u-1)) (the missing Sharpes all at the computed mean), so
    the DSR there bounds it from above. Fails when that bound misses the bar (decisive when PSR vs 0 <= 0.05);
    undecided otherwise. Returns ((name, ok, decisive), info)."""
    x = np.asarray(x, float)
    fs = np.array([s for s in family_sharpes if s is not None and math.isfinite(s)], float)
    if x.size < 4 or not x.std() > 0:
        return (f"{label} (n/a)", None, False), {"dsr_upper_bound": None}
    floor = 1.0 / max(1, x.size - 1)
    m = fs.size
    v_c = float(fs.var(ddof=1)) if m > 1 else 0.0
    v_min = max(floor, v_c * (m - 1) / max(1, m + n_uncomputed - 1))
    hi = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=v_min))
    at_c = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=max(floor, v_c)))
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1))
    info = {"dsr_upper_bound": hi, "dsr_computed_family": at_c, "var_min": v_min, "var_computed": v_c, "var_floor": floor,
            "n_computed": int(m), "n_uncomputed": int(n_uncomputed), "n_trials": int(n_trials), "psr0": psr0}
    txt = (f"{label} (at most {hi:.3f} at {n_trials} trials, var {v_min:.2e}; {at_c:.3f} on the {m} computed Sharpes; "
           f"PSR vs 0 {psr0:.3f})")
    if hi < DSR_PASS or (strict and hi <= DSR_PASS):
        return (txt + " [fails whatever the uncomputed Sharpes]", False, psr0 <= 1.0 - DSR_PASS), info
    return (txt + f" [{n_uncomputed} family Sharpe(s) not computed here: cannot pass]", None, False), info


def proxy_cap(row: tuple, pit: Optional[PitRates], what: str) -> tuple:
    """A criterion resting on point-in-time rate ranks: a pass on the IRLTLT01-release proxy reads undecided."""
    name, ok, dec = row
    if ok is True and (pit is None or pit.mode != "vintage"):
        return name + f" [{what} rests on the proxy rate clock, not the registered IR3TIB01 vintages: cannot pass]", None, False
    return row


def vintage_row(pit: Optional[PitRates], what: str) -> tuple:
    if pit is not None and pit.mode == "vintage":
        return (f"{what} ranked on the registered ALFRED IR3TIB01 vintages", True, False)
    return (f"{what} ranked on the registered ALFRED IR3TIB01 vintages (not archived: the harness ranks on the IRLTLT01 "
            f"release-calendar proxy, which can refute but not support)", None, False)


# ============================================================================================ DOL family (DSR) ==

def dol_family(archive) -> dict:
    """Per-period Sharpes of the 6 DOL-target trials (T-605 x2, T-575, T-719, T-720 x2)."""
    def run():
        out: dict = {}
        panel = FX._panel(archive, XA.T605_FILL_TO)
        for k, c in (("T-605:G10", XA.T605_G10), ("T-605:G10+MXN+ZAR", XA.T605_G10 + XA.T605_EM)):
            b = XA.t605_book(panel, c, XA.T605_FIRST, XA.T605_LAST)
            out[k] = _sr_pp(XA.t605_returns(b["rows"])["net"])
        days, x, _ = X11.basket_returns(archive, "2000-01-01", "2026-09-30")
        f = X11.last_n_flags(days, 2)
        by: dict = defaultdict(float)
        for d, r, fl in zip(days, x, f):
            if fl:
                by[d[:7]] += float(r)
        ms = sorted({d[:7] for d in days})
        out["T-575:long basket on the last two days (monthly)"] = _sr_pp([by.get(m, 0.0) for m in ms])
        c19 = t719_core(archive)
        out["T-719:forecast-sign rule"] = _sr_pp(c19["rule"]["net"]) if c19.get("ok") else None
        c20 = t720_core(archive)
        out["T-720:1-month arm"] = _sr_pp(c20["arm1"]["net"]) if c20.get("ok") else None
        out["T-720:3-month arm"] = _sr_pp(c20["arm3"]["net"]) if c20.get("ok") else None
        return out
    return CAL._cached(archive, ("b13_gaps_fx", "dol_family"), run)


# ============================================================================================ T-719 global RV ==

def gv_rv(P: dict, D: str, n: int = T719_RV_N) -> float:
    """T-719 GV at decision day D: mean over the panel's currencies of sqrt(252 x mean squared log change) over the
    ``n`` most recent common-session changes H.10 had published by D (NaN when fewer)."""
    p = pub_idx(P, D)
    if p < n:
        return float("nan")
    r = np.diff(P["L"][p - n:p + 1], axis=0)
    return float(np.mean(np.sqrt(252.0 * np.mean(r * r, axis=0))))


def _vix_arr(archive) -> tuple:
    vix = CAL._series(archive, VIX_B)
    vd = sorted(vix)
    return vd, np.array([vix[d] for d in vd], float), vix


def _last_on_or_before(days: Sequence[str], vals, D: str) -> float:
    i = bisect.bisect_right(days, D) - 1
    return float(vals[i]) if i >= 0 else float("nan")


def t719_frame(P: dict, R: dict, pit: Optional[PitRates], vd, vv, months: Sequence[str]) -> dict:
    """Monthly rows of T-719: decision day, GV, targets (h = 1, 3, 6 months, log, with the month t-1 AFD accrual), the
    H.10 release of each target's end fix, the simple 1-month basket return, VIX and the point-in-time AFD."""
    M = len(months)
    fr = {k: np.full(M, np.nan) for k in ("gv", "y1", "y3", "y6", "ret1", "vix", "afd_pit", "acc")}
    kd = {h: [None] * M for h in (1, 3, 6)}
    dday, filled = [], []
    L, X = P["L"], P["X"]
    for j, m in enumerate(months):
        D = month_end_day(m)
        dday.append(D)
        fr["gv"][j] = gv_rv(P, D)
        fr["vix"][j] = _last_on_or_before(vd, vv, D)
        a = pit.afd(G9, D) if pit is not None else None
        fr["afd_pit"][j] = np.nan if a is None else a
        acc, fl = afd_acc(R, G9, madd(m, -1))
        filled.append(fl)
        f = P["first"].get(madd(m, 1))
        if acc is None or f is None:
            continue
        fr["acc"][j] = acc
        for h in (1, 3, 6):
            e = P["first"].get(madd(m, 1 + h))
            if e is None:
                continue
            fr[f"y{h}"][j] = float(np.mean(L[e] - L[f])) + h * acc / 1200.0
            kd[h][j] = P["rel"][e]
            if h == 1:
                fr["ret1"][j] = float(np.mean(X[e] / X[f] - 1.0)) + acc / 1200.0
    fr.update(months=list(months), dday=dday, kd=kd, filled=filled)
    return fr


def t719_core(archive) -> dict:
    def run():
        P = _panel(archive, G9)
        if not P["days"]:
            return {"ok": False}
        R = _rates(archive)
        pit = _pit(archive)
        vd, vv, _ = _vix_arr(archive)
        months = mrange(T719_FIT_FROM, "2026-08")
        F = t719_frame(P, R, pit, vd, vv, months)
        ms = F["months"]
        dd = F["dday"]
        oos = np.array([T719_OOS[0] <= m <= T719_OOS[1] for m in ms])
        train = np.ones(len(ms), bool)
        excl = np.array([m in T719_EXCL for m in ms])
        cells, ev = {}, {}
        for nm, x, h, lag in (("gv", F["gv"], 3, 2), ("gv6", F["gv"], 6, 5), ("afd", F["afd_pit"], 3, 2),
                              ("vix", F["vix"], 3, 2), ("gv_shift12", shift(F["gv"], 12), 3, 2)):
            y = F[f"y{h}"]
            fm, fb, sl = expanding_fc(x, y, F["kd"][h], dd, train, oos)
            cells[nm] = (fm, fb, sl)
            ev[nm] = IB.oos_stats(y, fm, fb, oos & np.isfinite(fm), lag)
        fmx, fbx, _ = expanding_fc(F["gv"], F["y3"], F["kd"][3], dd, train & ~excl, oos & ~excl)
        ev["gv_excl"] = IB.oos_stats(F["y3"], fmx, fbx, oos & ~excl & np.isfinite(fmx), 2)
        fm3, fb3, sl3 = cells["gv"]
        use = oos & np.isfinite(fm3) & np.isfinite(F["y3"]) & np.isfinite(F["ret1"])
        J = np.where(use)[0]
        sign = np.where(fm3[J] > 0, 1.0, -1.0)
        net, gross = position_net(sign, F["ret1"][J])
        jm = [ms[j] for j in J]
        h1 = np.array([m < T719_SPLIT for m in jm])
        halves = [_sr(net[h1]), _sr(net[~h1])]
        # reported: the overlapping 3-month-tranche reading (each month's sign held three months in thirds)
        s_full = np.full(len(ms), np.nan)
        s_full[J] = sign
        tr = tranche_positions(s_full, J)
        okt = np.isfinite(tr)
        net3, gross3 = position_net(tr[okt], F["ret1"][J][okt], roll_units=np.ones(int(okt.sum())))
        h13 = h1[okt]
        tranche = {"n": int(okt.sum()), "sharpe": _sr(net3), "gross_sharpe": _sr(gross3),
                   "halves_sharpe": [_sr(net3[h13]), _sr(net3[~h13])]}
        base = {nm: _sr(position_net(np.full(J.size, s), F["ret1"][J])[0]) for nm, s in (("always_long_dol", 1.0),
                                                                                        ("always_short_dol", -1.0))}
        enc_X = np.column_stack([F["gv"], F["afd_pit"], F["vix"]])
        em = use & np.isfinite(enc_X).all(axis=1)
        enc = XA.ols_nw_all(F["y3"][em], enc_X[em], 2) if em.sum() > 10 else {}
        hod = hodrick_t(F["y1"], F["gv"], 3, oos)
        hv = {}
        for nm, msk in (("2013-2019", oos & np.array([m < T719_SPLIT for m in ms])),
                        ("2020-2026", oos & np.array([m >= T719_SPLIT for m in ms]))):
            hv[nm] = IB.oos_stats(F["y3"], fm3, fb3, msk & np.isfinite(fm3), 2)
        thr = oos & np.array([madd(m, -1) <= STALE_THROUGH for m in ms])
        ev["gv_through_2026_01_accrual"] = IB.oos_stats(F["y3"], fm3, fb3, thr & np.isfinite(fm3), 2)
        stale = [m for m, fl in zip(ms, F["filled"]) if fl and T719_OOS[0] <= m <= T719_OOS[1]]
        return {"ok": True, "n": int(ev["gv"]["n"]), "ev": ev, "halves_r2": hv, "rule": {"net": net, "gross": gross,
                "sign": sign, "months": jm, "halves_sharpe": halves, "sharpe": _sr(net), "gross_sharpe": _sr(gross),
                "share_long": float(np.mean(sign > 0)), "n_switch": int(np.sum(sign[1:] != sign[:-1]))},
                "tranche3": tranche, "baselines": base, "encompassing": enc, "hodrick": hod, "stale_accrual_months": stale,
                "gv_mean": float(np.nanmean(F["gv"][oos])), "slope_last": float(sl3[J[-1]]) if J.size else None,
                "first_last": [jm[0], jm[-1]] if jm else None, "pit_mode": pit.mode if pit else None}
    return CAL._cached(archive, ("b13_gaps_fx", "T-719"), run)


def b13_gaps_fx_global_rv_dol(archive):
    """T-719: global G10 FX realised volatility level predicts the 3-month DOL excess return (Clark-West)."""
    miss = B7C._missing(archive, [SPOT_B, RATE_B, VIX_B])
    if miss:
        return miss
    c = t719_core(archive)
    if not c.get("ok") or c["n"] < 8:
        return _out({"n": c.get("n", 0)}, c.get("n", 0), "inconclusive", "too few months with every fix and rate")
    ev = c["ev"]
    p = ev["gv"]
    fam = dol_family(archive)
    sb = sb_ci(c["rule"]["net"])
    dsr_row, d = family_dsr_row(c["rule"]["net"], list(fam.values()), DOL_N_TRIALS, 0,
                                f"DSR >= {DSR_PASS} over the {DOL_N_TRIALS} DOL-target trials (T-605 x2, T-575, T-720 x2, this)")
    h = c["rule"]["halves_sharpe"]
    srr = c["rule"]["sharpe"]
    rows = [IB._p_crit(p["cw_p"], p["cw_t"], "Clark-West one-sided p < 0.05 at 3 months (Newey-West lag 2)"),
            (f"3-month OOS R^2 > 0 (the claim and the null: {_s(p['oos_r2'], 4)})", None if p["oos_r2"] is None
             else p["oos_r2"] > 0, False),
            (f"forecast-sign DOL rule full-sample net Sharpe > 0 (the claim: {_s(srr, 3)})", None if srr is None
             else srr > 0, False),
            (f"forecast-sign DOL rule net Sharpe > 0 in 2013-2019 ({_s(h[0], 3)})", None if h[0] is None else h[0] > 0, False),
            (f"forecast-sign DOL rule net Sharpe > 0 in 2020-2026 ({_s(h[1], 3)})", None if h[1] is None else h[1] > 0, False),
            dsr_row]
    v, why, crit = CAL._judge(rows, c["n"], T719_MIN_N, "3-month forecasts")
    enc = c["encompassing"]
    enc_t = enc.get("t")
    evz = B7C._has(archive, EVZ_B)
    stat = {k: c[k] for k in ("n", "ev", "halves_r2", "baselines", "hodrick", "stale_accrual_months", "first_last",
                              "pit_mode", "slope_last")}
    stat.update(rule={k: c["rule"][k] for k in ("halves_sharpe", "sharpe", "gross_sharpe", "share_long", "n_switch")},
                rule_tranche3=c["tranche3"], rule_sb_ci=sb, encompassing=enc, dsr=d, family_sharpes_pp=fam, criteria=crit, verdict=v,
                evz_variant="EVZ archived but not computed" if evz else "EVZ not archived: not computed")
    r = c["rule"]
    reason = (f"GV = mean 21-session annualised RV of the 9 G10 noon fixes PUBLISHED by H.10 at each month-end (weekly "
              f"Monday release), target = 3-month DOL log excess return from the first common fix of t+1 (month t-1 OECD "
              f"AFD accrual, approximate), expanding OLS from 2002-06, {c['n']} forecasts {c['first_last'][0]}..{c['first_last'][1]}: "
              f"OOS R^2 {_s(p['oos_r2'], 4)}, Clark-West t {_s(p['cw_t'], 2)} (p {_f(p['cw_p'], 4)}); halves R^2 "
              f"{_s(c['halves_r2']['2013-2019']['oos_r2'], 4)} / {_s(c['halves_r2']['2020-2026']['oos_r2'], 4)}; forecast-sign "
              f"rule (long the basket {r['share_long']:.0%} of months, {r['n_switch']} switches) net Sharpe {_s(r['sharpe'], 3)} "
              f"(gross {_s(r['gross_sharpe'], 3)}; stationary-bootstrap 95% CI [{_s(sb['ci'][0], 2)}, {_s(sb['ci'][1], 2)}]), "
              f"halves {_s(h[0], 3)} / {_s(h[1], 3)}; DSR {_f(d.get('dsr'))} at {DOL_N_TRIALS} trials. Reported: the same "
              f"sign held 3 months in overlapping thirds, net Sharpe {_s(c['tranche3']['sharpe'], 3)} (halves "
              f"{_s(c['tranche3']['halves_sharpe'][0], 3)} / {_s(c['tranche3']['halves_sharpe'][1], 3)}); 6-month OOS "
              f"R^2 {_s(ev['gv6']['oos_r2'], 4)} (CW p {_f(ev['gv6']['cw_p'], 3)}); Hodrick t {_s(c['hodrick'].get('t'), 2)}; "
              f"controls AFD-only ({c['pit_mode'] or 'no'} point-in-time rates) R^2 {_s(ev['afd']['oos_r2'], 4)}, VIX-only "
              f"{_s(ev['vix']['oos_r2'], 4)}; encompassing GV coefficient t {_s(enc_t[1] if enc_t else None, 2)} (with AFD, VIX); "
              f"12-month-shifted placebo R^2 {_s(ev['gv_shift12']['oos_r2'], 4)}; excluding 2008-09..2009-03, 2020-03 and 2022 "
              f"R^2 {_s(ev['gv_excl']['oos_r2'], 4)} (CW p {_f(ev['gv_excl']['cw_p'], 3)}); always long / short DOL Sharpe "
              f"{_s(c['baselines']['always_long_dol'], 3)} / {_s(c['baselines']['always_short_dol'], 3)}; accruals forward-fill "
              f"EUR/GBP in {len(c['stale_accrual_months'])} decision months (R^2 with accruals through 2026-01 "
              f"{_s(ev['gv_through_2026_01_accrual']['oos_r2'], 4)}); {stat['evz_variant']}. Month-end calendar named by "
              f"the claim (rule 10) — {why}")
    return _out(stat, c["n"], v, reason)


# ============================================================================================ T-720 equity VRP ==

def vp_frame(days: Sequence[str], close, vix: dict, months_from: str, months_to: str) -> dict:
    """Month-end decision sessions (the last bar of each calendar month; the data's final month dropped) of a ^GSPC
    close history with VIX^2/12, 10,000 x the sum of squared log returns over the 21 sessions ending at t, and VP."""
    c = np.asarray(close, float)
    n = c.size
    r = np.full(n, np.nan)
    r[1:] = np.log(c[1:] / c[:-1])
    sq = np.where(np.isfinite(r), r * r, 0.0)
    cs = np.concatenate([[0.0], np.cumsum(sq)])
    pos = [int(i) for i in IB.month_end_pos(days) if months_from <= days[i][:7] <= months_to]
    rv = np.array([1e4 * (cs[i + 1] - cs[i - 20]) if i >= 21 else np.nan for i in pos])
    vx = np.array([vix.get(days[i], np.nan) for i in pos], float)
    v2 = vx ** 2 / 12.0
    return {"day": [days[i] for i in pos], "month": [days[i][:7] for i in pos], "vix": vx, "vix2": v2, "rv": rv,
            "vp": v2 - rv}


def t720_targets(P: dict, R: dict, pit: Optional[PitRates], dec_days: Sequence[str],
                  us_rate: Optional[dict] = None) -> dict:
    """Per decision j: 1- and 3-month log DOL excess returns from the first common fix after day j to the first common
    fix after decision j+1 (j+3), with the month t-1 AFD accrual (US leg: R's OECD USD rate, or ``us_rate`` {month:
    percent}, e.g. the DTB3 month average); the simple 1-month return; per-currency 1-month log excess returns; release
    days of the end fixes; the point-in-time AFD and the last-month published DOL return."""
    M = len(dec_days)
    L, X, ccys = P["L"], P["X"], P["ccys"]
    out = {k: np.full(M, np.nan) for k in ("y1", "y3", "ret1", "afd_pit", "last_dol")}
    out["y1c"] = np.full((M, len(ccys)), np.nan)
    kd = {1: [None] * M, 3: [None] * M}
    filled = []
    for j, t in enumerate(dec_days):
        m = t[:7]
        a = pit.afd(ccys, t) if pit is not None else None
        out["afd_pit"][j] = np.nan if a is None else a
        p_now = pub_idx(P, t)
        if j > 0:
            p_prev = pub_idx(P, dec_days[j - 1])
            if p_now >= 0 and p_prev >= 0:
                out["last_dol"][j] = float(np.mean(L[p_now] - L[p_prev]))
        acc, fl = afd_acc(R, ccys, madd(m, -1), us_rate)
        filled.append(fl)
        s = after_idx(P, t)
        if acc is None or s is None:
            continue
        for h in (1, 3):
            if j + h >= M:
                continue
            e = after_idx(P, dec_days[j + h])
            if e is None:
                continue
            out[f"y{h}"][j] = float(np.mean(L[e] - L[s])) + h * acc / 1200.0
            kd[h][j] = P["rel"][e]
            if h == 1:
                out["ret1"][j] = float(np.mean(X[e] / X[s] - 1.0)) + acc / 1200.0
                us = rate_at(R, "USD", madd(m, -1))[0] if us_rate is None else us_rate.get(madd(m, -1))
                out["y1c"][j] = (L[e] - L[s]) + (rate_vec(R, ccys, madd(m, -1)) - us) / 1200.0
    out.update(kd=kd, filled=filled)
    return out


def median_arm(vp, oos, win: int = T720_MED_WIN) -> np.ndarray:
    """+1 when VP_j exceeds the median of the ``win`` previous decisions' VP, else -1 (NaN without a full window)."""
    vp = np.asarray(vp, float)
    s = np.full(vp.size, np.nan)
    for j in np.where(np.asarray(oos, bool))[0]:
        h = vp[max(0, j - win):j]
        if j >= win and np.isfinite(h).all() and np.isfinite(vp[j]):
            s[j] = 1.0 if vp[j] > float(np.median(h)) else -1.0
    return s


def t720_core(archive) -> dict:
    def run():
        P = _panel(archive, G9)
        if not P["days"]:
            return {"ok": False}
        R = _rates(archive)
        pit = _pit(archive)
        gd, gc = CAL._daily(archive, GSPC_B, "close")
        vix = CAL._series(archive, VIX_B)
        V = vp_frame(gd, gc, vix, "2001-05", "2026-09")
        T = t720_targets(P, R, pit, V["day"])
        ms, dd = V["month"], V["day"]
        M = len(ms)
        oos = np.array([T720_OOS[0] <= m <= T720_OOS[1] for m in ms])
        train = np.array([m >= T720_FIT_FROM for m in ms])
        excl = np.array([m in T720_EXCL for m in ms])
        cells, ev = {}, {}
        for nm, x, h in (("vp", V["vp"], 1), ("vix2", V["vix2"], 1), ("rv", V["rv"], 1), ("vp3", V["vp"], 3),
                         ("vp_shift12", shift(V["vp"], 12), 1)):
            y = T[f"y{h}"]
            fm, fb, sl = expanding_fc(x, y, T["kd"][h], dd, train, oos)
            cells[nm] = (fm, fb)
            ev[nm] = IB.oos_stats(y, fm, fb, oos & np.isfinite(fm), 2)
        fmx, fbx, _ = expanding_fc(V["vp"], T["y1"], T["kd"][1], dd, train & ~excl, oos & ~excl)
        ev["vp_excl"] = IB.oos_stats(T["y1"], fmx, fbx, oos & ~excl & np.isfinite(fmx), 2)
        use = oos & np.isfinite(V["vp"]) & np.isfinite(T["y1"])
        vz = np.full(M, np.nan)
        mu, sd = float(V["vp"][use].mean()), float(V["vp"][use].std(ddof=1))
        vz[np.isfinite(V["vp"])] = (V["vp"][np.isfinite(V["vp"])] - mu) / sd
        sl = nw_slope(T["y1"][use], vz[use], 2)
        h1 = use & np.array([m < T720_SPLIT for m in ms])
        h2 = use & np.array([m >= T720_SPLIT for m in ms])
        halves = [nw_slope(T["y1"][h1], vz[h1], 2), nw_slope(T["y1"][h2], vz[h2], 2)]
        ex = use & ~excl
        sl_ex = nw_slope(T["y1"][ex], vz[ex], 2)
        u3 = oos & np.isfinite(V["vp"]) & np.isfinite(T["y3"])
        sl3 = nw_slope(T["y3"][u3], vz[u3], 2)
        hod3 = hodrick_t(T["y1"], vz, 3, oos)
        Xc = np.column_stack([vz, T["afd_pit"], T["last_dol"], V["vix"]])
        cm = use & np.isfinite(Xc).all(axis=1)
        multi = XA.ols_nw_all(T["y1"][cm], Xc[cm], 2) if cm.sum() > 12 else {}
        rng = np.random.default_rng(SEED)
        yy, xx = T["y1"][use], vz[use]
        xc = xx - xx.mean()
        b_obs = float(xc @ (yy - yy.mean()) / (xc @ xc))
        perm = np.array([float(xc[p] @ (yy - yy.mean()) / (xc @ xc)) for p in (rng.permutation(xx.size) for _ in range(T720_N_SHUF))])
        per_c = {}
        for k, c in enumerate(P["ccys"]):
            yc = T["y1c"][:, k]
            mc = use & np.isfinite(yc)
            per_c[c] = nw_slope(yc[mc], vz[mc], 2)
        fe = fe_panel_slope(T["y1c"][use], vz[use])
        # trading arms (the registration's 60-month-median rule; 1- and 3-month holds)
        s = median_arm(V["vp"], oos)
        arm = oos & np.isfinite(s) & np.isfinite(T["ret1"])
        J = np.where(arm)[0]
        net1, gross1 = position_net(s[J], T["ret1"][J])
        tr = tranche_positions(s, J)
        okt = np.isfinite(tr)
        net3, _ = position_net(tr[okt], T["ret1"][J][okt], roll_units=np.ones(int(okt.sum())))
        stale = [m for m, fl in zip(ms, T["filled"]) if fl and T720_OOS[0] <= m <= T720_OOS[1]]
        thr = use & np.array([madd(m, -1) <= STALE_THROUGH for m in ms])
        sl_thr = nw_slope(T["y1"][thr], vz[thr], 2)
        # reported, not judged: the registration's data line names fred-DTB3, so the accrual's US leg as the month t-1
        # DTB3 average (public by the decision) beside the judged OECD IR3TIB01 US leg
        dtb = _dtb3_month(archive)
        alt = None
        if dtb is not None:
            T2 = t720_targets(P, R, pit, V["day"], us_rate=dtb)
            u2 = oos & np.isfinite(V["vp"]) & np.isfinite(T2["y1"])
            sp = np.array([m < T720_SPLIT for m in ms])
            fm2, fb2, _ = expanding_fc(V["vp"], T2["y1"], T2["kd"][1], dd, train, oos)
            a2 = oos & np.isfinite(s) & np.isfinite(T2["ret1"])
            J2 = np.where(a2)[0]
            gap = [rate_at(R, "USD", madd(m, -1))[0] - dtb[madd(m, -1)] for m in ms
                   if T720_OOS[0] <= m <= T720_OOS[1] and madd(m, -1) in dtb and rate_at(R, "USD", madd(m, -1))[0] is not None]
            alt = {"n_slope": int(u2.sum()), "slope": nw_slope(T2["y1"][u2], vz[u2], 2),
                   "halves": [nw_slope(T2["y1"][u2 & sp], vz[u2 & sp], 2), nw_slope(T2["y1"][u2 & ~sp], vz[u2 & ~sp], 2)],
                   "ev": IB.oos_stats(T2["y1"], fm2, fb2, oos & np.isfinite(fm2), 2),
                   "fe_panel": fe_panel_slope(T2["y1c"][u2], vz[u2]),
                   "arm1_sharpe": _sr(position_net(s[J2], T2["ret1"][J2])[0]),
                   "mean_oecd_minus_dtb3_pct": float(np.mean(gap)) if gap else None}
        return {"ok": True, "n": int(ev["vp"]["n"]), "ev": ev, "slope": sl, "halves": halves, "slope_excl": sl_ex,
                "slope_3m": sl3, "hodrick_3m": hod3, "multi": multi,
                "shuffle": {"b_obs": b_obs, "pct_rank": float(np.mean(perm < b_obs)), "p95": float(np.percentile(perm, 95))},
                "per_ccy": per_c, "fe_panel": fe, "dtb3_us_leg": alt, "arm1": {"net": net1, "gross": gross1, "months": [ms[j] for j in J],
                                           "share_long": float(np.mean(s[J] > 0)) if J.size else None},
                "arm3": {"net": net3}, "stale_accrual_months": stale, "slope_through_2026_01": sl_thr,
                "first_last": [ms[np.where(use)[0][0]], ms[np.where(use)[0][-1]]] if use.any() else None,
                "n_slope": int(use.sum()), "vp_mean": mu, "vp_sd": sd, "pit_mode": pit.mode if pit else None}
    return CAL._cached(archive, ("b13_gaps_fx", "T-720"), run)


def b13_gaps_fx_equity_vrp_dol(archive):
    """T-720: the US equity variance risk premium (VIX^2/12 - 21-session ^GSPC RV) predicts the next-month DOL excess
    return (Newey-West slope and Clark-West)."""
    miss = B7C._missing(archive, [SPOT_B, RATE_B, VIX_B, GSPC_B, DTB3_B])
    if miss:
        return miss
    c = t720_core(archive)
    if not c.get("ok") or c["n"] < 8:
        return _out({"n": c.get("n", 0)}, c.get("n", 0), "inconclusive", "too few months with every fix and rate")
    ev, sl, hv = c["ev"], c["slope"], c["halves"]
    fam = dol_family(archive)
    net = c["arm1"]["net"]
    dsr_row, d = family_dsr_row(net, list(fam.values()), DOL_N_TRIALS, 0,
                                f"DSR >= {DSR_PASS} over the {DOL_N_TRIALS} DOL-target trials on the registered "
                                f"60-month-median arm (1- and 3-month arms, T-605 x2, T-575, T-719)")
    sb = sb_ci(net)
    p = ev["vp"]
    rows = [IB._p_crit(sl["p"], sl["t"], f"post-sample slope on standardised VP > 0 with Newey-West (lag 2) one-sided "
                                         f"p < 0.05 ({c['n_slope']} decisions, slope {_s(sl['b'] * 1e4 if sl['b'] is not None else None, 1)} bp per sd)"),
            IB._p_crit(p["cw_p"], p["cw_t"], "Clark-West one-sided p < 0.05 (expanding OLS from 2002-06, NW lag 2)"),
            (f"OOS R^2 > 0 (the null: {_s(p['oos_r2'], 4)})", None if p["oos_r2"] is None else p["oos_r2"] > 0, False),
            (f"slope > 0 in 2012-2018 (t {_s(hv[0]['t'], 2)})", None if hv[0]["b"] is None else hv[0]["b"] > 0, False),
            (f"slope > 0 in 2019-2026 (t {_s(hv[1]['t'], 2)})", None if hv[1]["b"] is None else hv[1]["b"] > 0, False),
            dsr_row]
    v, why, crit = CAL._judge(rows, c["n"], T720_MIN_N, "monthly forecasts")
    mt = (c["multi"] or {}).get("t")
    beats = None if None in (p["oos_r2"], ev["vix2"]["oos_r2"], ev["rv"]["oos_r2"]) else bool(
        p["oos_r2"] > ev["vix2"]["oos_r2"] and p["oos_r2"] > ev["rv"]["oos_r2"])
    eur = c["per_ccy"].get("EUR", {})
    fe, alt = c["fe_panel"], c["dtb3_us_leg"]

    def outcomes(slope, halves_, ev_):
        return [None if slope["p"] is None else slope["p"] < ALPHA, None if ev_["cw_p"] is None else ev_["cw_p"] < ALPHA,
                None if ev_["oos_r2"] is None else ev_["oos_r2"] > 0] + [None if x["b"] is None else x["b"] > 0
                                                                         for x in halves_]
    dtb_agree = None if alt is None else outcomes(sl, hv, p) == outcomes(alt["slope"], alt["halves"], alt["ev"])
    stat = {k: c[k] for k in ("n", "ev", "slope", "halves", "slope_excl", "slope_3m", "hodrick_3m", "multi", "shuffle",
                              "per_ccy", "fe_panel", "dtb3_us_leg", "stale_accrual_months", "slope_through_2026_01",
                              "first_last", "n_slope", "vp_mean", "vp_sd", "pit_mode")}
    stat["dtb3_reading_same_criterion_outcomes"] = dtb_agree
    stat.update(arm1={"sharpe": _sr(net), "gross_sharpe": _sr(c["arm1"]["gross"]), "share_long": c["arm1"]["share_long"],
                      "sb_ci": sb}, arm3_sharpe=_sr(c["arm3"]["net"]), vp_beats_vix2_and_rv=beats, dsr=d,
                family_sharpes_pp=fam, criteria=crit, verdict=v)
    pcs = ", ".join(f"{k} {_s(x.get('t'), 1)}" for k, x in c["per_ccy"].items())
    if alt is None:
        dtb_txt = "fred-DTB3 US leg: not computed"
    else:
        ae = alt["ev"]
        dtb_txt = (f"with the US leg as the month t-1 fred-DTB3 average (registered data; OECD US minus DTB3 "
                   f"{_s(alt['mean_oecd_minus_dtb3_pct'], 2)} pt on average): slope NW t {_s(alt['slope']['t'], 2)} (p "
                   f"{_f(alt['slope']['p'], 4)}), halves t {_s(alt['halves'][0]['t'], 2)} / {_s(alt['halves'][1]['t'], 2)}, OOS "
                   f"R^2 {_s(ae['oos_r2'], 4)}, CW t {_s(ae['cw_t'], 2)} (p {_f(ae['cw_p'], 4)}), FE panel t "
                   f"{_s(alt['fe_panel']['t'], 2)}, arm Sharpe {_s(alt['arm1_sharpe'], 3)}; every judged criterion reads the "
                   f"same: {dtb_agree}")
    reason = (f"VP = VIX^2/12 - 21-session ^GSPC RV (monthly %^2) at each month's last NYSE session, next-month DOL log "
              f"excess return from the first common fix after t (month t-1 AFD accrual), decisions {c['first_last'][0]}.."
              f"{c['first_last'][1]}: slope {_s(sl['b'] * 1e4 if sl['b'] is not None else None, 1)} bp per sd of VP, NW t "
              f"{_s(sl['t'], 2)} (p {_f(sl['p'], 4)}); halves t {_s(hv[0]['t'], 2)} / {_s(hv[1]['t'], 2)}; expanding OLS from "
              f"2002-06, {c['n']} forecasts: OOS R^2 {_s(p['oos_r2'], 4)}, CW t {_s(p['cw_t'], 2)} (p {_f(p['cw_p'], 4)}); "
              f"60-month-median arm net Sharpe {_s(_sr(net), 3)} (long {c['arm1']['share_long'] or 0:.0%}; CI [{_s(sb['ci'][0], 2)}, "
              f"{_s(sb['ci'][1], 2)}]), 3-month arm {_s(_sr(c['arm3']['net']), 3)}; DSR {_f(d.get('dsr'))} at {DOL_N_TRIALS} "
              f"trials. Reported: VIX^2-only R^2 {_s(ev['vix2']['oos_r2'], 4)}, RV-only {_s(ev['rv']['oos_r2'], 4)} (VP beats "
              f"both: {beats}); VP t {_s(mt[1] if mt else None, 2)} with AFD ({c['pit_mode'] or 'no'} point-in-time), last-"
              f"month published DOL return and VIX; 12-month-shifted placebo R^2 {_s(ev['vp_shift12']['oos_r2'], 4)}; "
              f"shuffled-month slopes: observed at the {c['shuffle']['pct_rank']:.0%} rank; 3-month slope NW t "
              f"{_s(c['slope_3m']['t'], 2)}, Hodrick t {_s(c['hodrick_3m'].get('t'), 2)}, R^2 {_s(ev['vp3']['oos_r2'], 4)}; "
              f"excluding 2008-09..2009-03 and 2020-03..06: slope t {_s(c['slope_excl']['t'], 2)}, R^2 "
              f"{_s(ev['vp_excl']['oos_r2'], 4)}; per-currency slope t {pcs} (EUR, insignificant in the source: "
              f"{_s(eur.get('t'), 2)}); pooled currency-fixed-effects panel slope {_s(fe['b'] * 1e4 if fe['b'] is not None else None, 1)} "
              f"bp per sd, t {_s(fe['t'], 2)} clustered by month ({fe['n_obs']} currency-months, {fe['n_months']} months); "
              f"{dtb_txt}; EUR/GBP accruals forward-filled in {len(c['stale_accrual_months'])} months (slope t "
              f"through 2026-01 accruals {_s(c['slope_through_2026_01']['t'], 2)}). VIX enters at 21:30 UTC on t, the fill "
              f"is the next common noon fix — {why}")
    return _out(stat, c["n"], v, reason)


# ======================================================================================= T-725 FX-vol carry timing ==

def gv_abs(P: dict, m: str) -> float:
    """T-725 GV of month m: mean over the panel's currencies of the average |daily log change| over the common sessions
    of month m that H.10 had published by the month's last day (NaN when none)."""
    a, b = P["first"].get(m), P["last"].get(m)
    if a is None:
        return float("nan")
    b = min(b, pub_idx(P, month_end_day(m)))
    a = max(a, 1)
    if b < a:
        return float("nan")
    ch = np.abs(P["L"][a:b + 1] - P["L"][a - 1:b])
    return float(ch.mean(axis=0).mean())


def ar1_flags(gv, start: int, pct: float = T725_PCT, min_fit: int = MIN_TRAIN) -> dict:
    """Real-time AR(1) residuals u_t = gv_t - a_t - b_t gv_{t-1} with (a_t, b_t) fitted on the pairs s = start..t, and
    the flag u_t > the ``pct`` percentile of the real-time residuals up to t (u_t included)."""
    g = np.asarray(gv, float)
    n = g.size
    u = np.full(n, np.nan)
    thr = np.full(n, np.nan)
    flag = np.zeros(n, bool)
    sx = sy = sxx = sxy = 0.0
    k = 0
    hist = []
    for t in range(max(start, 1), n):
        x0, y0 = g[t - 1], g[t]
        if not (np.isfinite(x0) and np.isfinite(y0)):
            continue
        sx += x0; sy += y0; sxx += x0 * x0; sxy += x0 * y0; k += 1
        if k < min_fit:
            continue
        den = k * sxx - sx * sx
        b = (k * sxy - sx * sy) / den if den > 0 else 0.0
        a = (sy - b * sx) / k
        u[t] = y0 - a - b * x0
        hist.append(u[t])
        thr[t] = float(np.percentile(hist, pct))
        flag[t] = bool(u[t] > thr[t])
    return {"u": u, "thr": thr, "flag": flag}


def carry_weights(pit: PitRates, D: str, universe: Sequence[str] = G10U, k: int = 3) -> Optional[dict]:
    """T-368's top-k minus bottom-k equal weights on the 3-month rates known at day D (ties keep the universe order)."""
    sig = {}
    for c in universe:
        x = pit.known(c, D)[1]
        if x is None:
            return None
        sig[c] = x
    order = sorted(universe, key=lambda c: (-sig[c], list(universe).index(c)))
    w = dict.fromkeys(universe, 0.0)
    for c in order[:k]:
        w[c] += 1.0 / k
    for c in order[-k:]:
        w[c] -= 1.0 / k
    return w


def leg_returns(P: dict, R: dict, H: str, universe: Sequence[str]) -> Optional[dict]:
    """Excess return of a long position in each universe currency from the first common fix of H to the first common
    fix of H+1 plus one month of (r_c - r_USD) of month H-1 (T-368's leg convention); USD earns 0."""
    f, e = P["first"].get(H), P["first"].get(madd(H, 1))
    if f is None or e is None:
        return None
    M = madd(H, -1)
    us = rate_at(R, "USD", M)[0]
    if us is None:
        return None
    out = {}
    for c in universe:
        if c == "USD":
            out[c] = 0.0
            continue
        k = P["ccys"].index(c)
        rc = rate_at(R, c, M)[0]
        if rc is None:
            return None
        out[c] = float(P["X"][e, k] / P["X"][f, k] - 1.0) + (rc - us) / 1200.0
    return out


def carry_book(P: dict, R: dict, pit: PitRates, months: Sequence[str], universe: Sequence[str] = G10U) -> dict:
    """The point-in-time T-368 book over holding months: weights (decided at the end of H-1), leg returns, gross."""
    rows = []
    for H in months:
        w = carry_weights(pit, month_end_day(madd(H, -1)), universe)
        lr = leg_returns(P, R, H, universe)
        if w is None or lr is None:
            continue
        stale = [c for c in universe if pit.known(c, month_end_day(madd(H, -1)))[2]]
        rows.append({"H": H, "w": np.array([w[c] for c in universe]), "r": np.array([lr[c] for c in universe]),
                     "stale": stale})
    return {"rows": rows, "universe": tuple(universe)}


def book_net(rows: list, universe: Sequence[str], g=None, cost: Optional[dict] = None, admin: Optional[dict] = None,
             switch: float = 0.0) -> tuple:
    """(net, gross) of a carry book scaled by on/off weights ``g`` (default all on): T-368 turnover cost (``cost`` per unit
    traded, non-USD) and financing (``admin`` a year per unit held, non-USD) on the scaled weights, plus ``switch`` per
    unit of non-USD notional on every on/off change (after the first month)."""
    n = len(rows)
    g = np.ones(n) if g is None else np.asarray(g, float)
    cost = cost or {c: FX.G10_COST_BPS / 1e4 for c in universe if c != "USD"}
    admin = admin or {c: FX.ADMIN for c in universe if c != "USD"}
    cv = np.array([cost.get(c, 0.0) if c != "USD" else 0.0 for c in universe])
    av = np.array([admin.get(c, 0.0) if c != "USD" else 0.0 for c in universe])
    fxm = np.array([c != "USD" for c in universe], float)
    net, gross = np.zeros(n), np.zeros(n)
    prev = np.zeros(len(universe))
    for k, r in enumerate(rows):
        w = g[k] * r["w"]
        gr = float(w @ r["r"])
        tc = float(np.abs(w - prev) @ cv)
        fc = float(np.abs(w) @ av) / 12.0
        sc = 0.0
        if k > 0 and g[k] != g[k - 1]:
            legs = r["w"] if g[k] > g[k - 1] else rows[k - 1]["w"]
            sc = switch * float(np.abs(legs) @ fxm)
        gross[k] = gr
        net[k] = gr - tc - fc - sc
        prev = w
    return net, gross


def placebo_gains(rows: list, universe: Sequence[str], n_flat: int, sr_untimed: Optional[float], n_draws: int,
                  rng) -> np.ndarray:
    """Sharpe gains of random-switch books with ``n_flat`` flat months at random positions (costs recomputed); a draw
    whose Sharpe is undefined is NaN, and every draw is NaN when the untimed Sharpe is (never a silent 0)."""
    n = len(rows)
    out = np.full(n_draws, np.nan)
    if sr_untimed is None:
        return out
    for i in range(n_draws):
        g = np.ones(n)
        g[rng.choice(n, size=n_flat, replace=False)] = 0.0
        x = _sr(book_net(rows, universe, g, switch=T725_SWITCH)[0])
        if x is not None:
            out[i] = x - sr_untimed
    return out


def placebo_summary(plac, observed: Optional[float]) -> dict:
    """95th percentile, mean and the observed value's rank among the finite placebo draws (None when undefined)."""
    x = np.asarray(plac if plac is not None else [], float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0, "p95": None, "mean": None, "pct_rank": None}
    return {"n": int(x.size), "p95": float(np.percentile(x, 95)), "mean": float(x.mean()),
            "pct_rank": None if observed is None else float(np.mean(x < observed))}


def _pct0(x: Optional[float]) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.0%}"


def t725_core(archive) -> dict:
    def run():
        P = _panel(archive, G9)
        pit = _pit(archive)
        if not P["days"] or pit is None:
            return {"ok": False}
        R = _rates(archive)
        gmonths = mrange("1999-01", madd(T725_HOLD[1], -1))
        gv = np.array([gv_abs(P, m) for m in gmonths])
        fl = ar1_flags(gv, gmonths.index(T725_AR_FROM))
        gidx = {m: i for i, m in enumerate(gmonths)}
        hold = mrange(*T725_HOLD)
        B = carry_book(P, R, pit, hold)
        rows = B["rows"]
        Hs = [r["H"] for r in rows]
        g = np.array([0.0 if fl["flag"][gidx[madd(H, -1)]] else 1.0 for H in Hs])
        vd, vv, _ = _vix_arr(archive)
        gv30 = np.array([0.0 if _last_on_or_before(vd, vv, month_end_day(madd(H, -1))) > T725_VIX_CUT else 1.0 for H in Hs])
        un, ug = book_net(rows, G10U)
        tn, _ = book_net(rows, G10U, g, switch=T725_SWITCH)
        vn, _ = book_net(rows, G10U, gv30, switch=T725_SWITCH)
        sd = sb_sharpe_diff(tn, un)
        h1 = np.array([H < T725_SPLIT for H in Hs])
        halves = [_gain(tn[h1], un[h1]), _gain(tn[~h1], un[~h1])]
        rng = np.random.default_rng(SEED)
        n_flat = int((g == 0).sum())
        plac = (placebo_gains(rows, G10U, n_flat, _sr(un), T725_N_PLACEBO, rng) if 0 < n_flat < len(rows)
                else np.zeros(0))
        # reported: the same rule on fixed month t-2 ranks (the proxy clock may lead the IR3TIB01 release)
        lag = LagRates(R)
        rl = carry_book(P, R, lag, hold)["rows"]
        Hl = [r["H"] for r in rl]
        gl = np.array([0.0 if fl["flag"][gidx[madd(H, -1)]] else 1.0 for H in Hl])
        gl30 = np.array([0.0 if _last_on_or_before(vd, vv, month_end_day(madd(H, -1))) > T725_VIX_CUT else 1.0 for H in Hl])
        unl, _ = book_net(rl, G10U)
        tnl, _ = book_net(rl, G10U, gl, switch=T725_SWITCH)
        vnl, _ = book_net(rl, G10U, gl30, switch=T725_SWITCH)
        hl = np.array([H < T725_SPLIT for H in Hl])
        lagged = {"mode": lag.mode, "n": len(rl), "timed": tnl, "untimed": unl, "sharpe_vix30": _sr(vnl),
                  "sd": sb_sharpe_diff(tnl, unl), "halves": [_gain(tnl[hl], unl[hl]), _gain(tnl[~hl], unl[~hl])]}
        # T-368's frozen non-vintage book (its own month-end calendar and one-month-lagged ranks)
        panel = FX._panel(archive, XA.T605_FILL_TO)
        cb, ad = FX.g10_costs()
        frozen = FX.carry_backtest(panel, FX.G10, hold, weighting="equal", cost_bps=cb, admin=ad)
        # Bakshi-Panayotov (reported): next-month base-book net on dGV_t and DBC's month-t return
        bp_hold = mrange(T725_BP_FROM, T725_HOLD[1])
        BB = carry_book(P, R, pit, bp_hold)
        bnet, _ = book_net(BB["rows"], G10U)
        dbd, dbv = CAL._daily(archive, DBC_B, "adjclose") if B7C._has(archive, DBC_B) else ([], np.zeros(0))
        dbm = {}
        for i in range(1, len(dbd)):
            if dbd[i][:7] != (dbd[i + 1][:7] if i + 1 < len(dbd) else "9999-99"):
                dbm[dbd[i][:7]] = (dbd[i], float(dbv[i]))
        bx, by_, bkd, bdd = [], [], [], []
        for r, x in zip(BB["rows"], bnet):
            H = r["H"]
            t = madd(H, -1)
            i, i0 = gidx.get(t), gidx.get(madd(t, -1))
            d1, d0 = dbm.get(t), dbm.get(madd(t, -1))
            fill = P["days"][P["first"][H]]
            ok = i is not None and i0 is not None and d1 is not None and d0 is not None and d1[0] < fill
            bx.append([gv[i] - gv[i0], d1[1] / d0[1] - 1.0] if ok else [np.nan, np.nan])
            by_.append(x)
            bkd.append(P["rel"][P["first"][madd(H, 1)]])
            bdd.append(month_end_day(t))
        bx, by_ = np.array(bx, float), np.array(by_, float)
        boos = np.array([T725_HOLD[0] <= r["H"] <= T725_HOLD[1] for r in BB["rows"]])
        bfm, bfb, _ = expanding_fc(bx, by_, bkd, bdd, np.ones(len(by_), bool), boos)
        bp = IB.oos_stats(by_, bfm, bfb, boos & np.isfinite(bfm), 1)
        stale = [r["H"] for r in rows if r["stale"] or madd(r["H"], -1) > STALE_THROUGH]
        thr = np.array([madd(H, -1) <= STALE_THROUGH for H in Hs])
        return {"ok": True, "n": len(rows), "months": Hs, "timed": tn, "untimed": un, "untimed_gross": ug, "vix30": vn,
                "g": g, "g_vix30": gv30, "sd": sd, "halves": halves, "placebo": plac, "frozen_net": frozen["net"],
                "frozen_months": frozen["months"], "bp": bp, "stale_months": stale, "pit_mode": pit.mode,
                "gain_through_2026_01": _gain(tn[thr], un[thr]), "lagged_ranks": lagged,
                "u_last": float(fl["u"][gidx[madd(Hs[-1], -1)]]) if Hs else None}
    return CAL._cached(archive, ("b13_gaps_fx", "T-725"), run)


def b13_gaps_fx_vol_innovation_carry(archive):
    """T-725: flat G10 carry in month t+1 when the AR(1) innovation of G10 FX volatility is above its expanding 80th
    percentile raises the book's net Sharpe."""
    miss = B7C._missing(archive, [SPOT_B, RATE_B, VIX_B] + clock_bundles())
    if miss:
        return miss
    c = t725_core(archive)
    if not c.get("ok") or c["n"] < 8:
        return _out({"n": c.get("n", 0)}, c.get("n", 0), "inconclusive", "too few holding months with every fix and rate")
    tn, un, vn, sd = c["timed"], c["untimed"], c["vix30"], c["sd"]
    panel = FX._panel(archive, XA.T605_FILL_TO)
    fam = XA.t605_family_sharpes(archive, panel)["sharpes"]
    dsr_row, dsr = family_dsr_row(tn, list(fam.values()) + [_sr_pp(tn)], T725_N_TRIALS, len(T725_UNCOMPUTED),
                                  f"DSR >= {DSR_PASS} at {T725_N_TRIALS} trials (T-368 6, T-431 4, T-682 1, this; T-682 "
                                  f"and T-431's KRW trial not computable here)")
    srt, sru, srv = _sr(tn), _sr(un), _sr(vn)
    pit = _pit(archive)
    p_ok = None if sd["diff"] is None else (False if not sd["diff"] > 0 else CAL.decide_p(sd["p"], sd["draws"]))
    rows = [proxy_cap((f"Sharpe(timed) - Sharpe(untimed) {_s(sd['diff'], 3)} > 0 with paired stationary-bootstrap one-sided "
                       f"p < 0.05 (p {CAL._mc(sd['p'], sd['draws'])})", p_ok,
                       CAL.decide_p(sd["p_lt"], sd["draws"]) is True), pit, "the base book"),
            proxy_cap((f"gain > 0 in 2013-2019 ({_s(c['halves'][0], 3)})", None if c["halves"][0] is None
                       else c["halves"][0] > 0, False), pit, "the base book"),
            proxy_cap((f"gain > 0 in 2020-2026 ({_s(c['halves'][1], 3)})", None if c["halves"][1] is None
                       else c["halves"][1] > 0, False), pit, "the base book"),
            proxy_cap((f"timed Sharpe {_s(srt, 3)} above the VIX > 30 filter's {_s(srv, 3)} on the same base",
                       None if srt is None or srv is None else srt > srv, False), pit, "the base book"),
            dsr_row,
            vintage_row(pit, "base book")]
    v, why, crit = CAL._judge(rows, c["n"], T725_MIN_N, "holding months")
    plac = c["placebo"]
    n_flat = int((c["g"] == 0).sum())
    fz = np.asarray(c["frozen_net"], float)
    bp = c["bp"]
    lg = c["lagged_ranks"]
    lsd = lg["sd"]
    _, ldsr = family_dsr_row(lg["timed"], list(fam.values()) + [_sr_pp(lg["timed"])], T725_N_TRIALS,
                             len(T725_UNCOMPUTED), "DSR (fixed month t-2 ranks)")
    lagged = {"mode": lg["mode"], "n": lg["n"], "sharpe_timed": _sr(lg["timed"]), "sharpe_untimed": _sr(lg["untimed"]),
              "sharpe_vix30": lg["sharpe_vix30"], "sharpe_diff": lsd, "halves_gain": lg["halves"],
              "dsr_upper_bound": ldsr.get("dsr_upper_bound")}
    stat = {"n": c["n"], "first_last": [c["months"][0], c["months"][-1]], "sharpe_timed": srt, "sharpe_untimed": sru,
            "sharpe_untimed_gross": _sr(c["untimed_gross"]), "sharpe_vix30": srv, "sharpe_diff": sd, "halves_gain": c["halves"],
            "n_flat": n_flat, "n_flat_vix30": int((c["g_vix30"] == 0).sum()),
            "mdd": {"timed": FX._mdd(tn) if hasattr(FX, "_mdd") else None, "untimed": FX._mdd(un) if hasattr(FX, "_mdd") else None},
            "skew": {"timed": FX.skewness(tn), "untimed": FX.skewness(un)},
            "placebo": placebo_summary(plac, sd["diff"]), "lagged_ranks_t_minus_2": lagged,
            "frozen_t368": {"n": int(fz.size), "sharpe": _sr(fz)}, "bakshi_panayotov": bp, "dsr": dsr,
            "family_sharpes_pp": fam, "stale_months": c["stale_months"], "gain_through_2026_01": c["gain_through_2026_01"],
            "pit_mode": c["pit_mode"], "criteria": crit, "verdict": v}
    reason = (f"T-368 G10 carry book (USD in the universe, top 3 minus bottom 3, 2 bp per unit traded, 1%/yr per leg) "
              f"ranked on 3-month rates known at each month-end ({c['pit_mode']} clock: IRLTLT01 first releases, the "
              f"registered IR3TIB01 vintages are not archived), held first common fix to first common fix, {c['n']} months "
              f"{c['months'][0]}..{c['months'][-1]}: untimed net Sharpe {_s(sru, 3)} (gross {_s(stat['sharpe_untimed_gross'], 3)}); "
              f"flat in {n_flat} months when the real-time AR(1) innovation of H.10-published G10 |daily change| exceeds its "
              f"expanding 80th percentile: timed {_s(srt, 3)}, gain {_s(sd['diff'], 3)} (paired stationary bootstrap p "
              f"{_f(sd['p'], 4)}, 95% CI [{_s(sd['ci'][0], 2)}, {_s(sd['ci'][1], 2)}]); halves {_s(c['halves'][0], 3)} / "
              f"{_s(c['halves'][1], 3)}; VIX > 30 filter ({stat['n_flat_vix30']} flat months) {_s(srv, 3)}; random-switch "
              f"placebo 95th pct gain {_s(stat['placebo']['p95'], 3)} (observed at the {_pct0(stat['placebo']['pct_rank'])} rank); "
              f"DSR bound {_f(dsr.get('dsr_upper_bound'))} at {T725_N_TRIALS} trials. Reported: on fixed month t-2 ranks "
              f"instead of the proxy clock (which can lead the IR3TIB01 release as well as lag it), {lagged['n']} months: "
              f"untimed {_s(lagged['sharpe_untimed'], 3)}, timed {_s(lagged['sharpe_timed'], 3)}, gain "
              f"{_s(lsd['diff'], 3)} (p {_f(lsd['p'], 4)}), halves {_s(lg['halves'][0], 3)} / {_s(lg['halves'][1], 3)}, VIX > 30 "
              f"{_s(lagged['sharpe_vix30'], 3)}, DSR bound {_f(lagged['dsr_upper_bound'])}; MDD timed "
              f"{_pc(stat['mdd']['timed'], 1)} vs untimed {_pc(stat['mdd']['untimed'], 1)}, skew {_s(stat['skew']['timed'], 2)} "
              f"vs {_s(stat['skew']['untimed'], 2)}; T-368's frozen non-vintage month-end book Sharpe {_s(stat['frozen_t368']['sharpe'], 3)}; "
              f"Bakshi-Panayotov (dGV, DBC) OOS R^2 {_s(bp.get('oos_r2'), 4)}, CW p {_f(bp.get('cw_p'), 3)}; stale rates "
              f"(ranks or accruals) in {len(c['stale_months'])} months, gain through 2026-01 {_s(c['gain_through_2026_01'], 3)}. "
              f"Costs: T-368's on the timed weights plus 2 bp per leg per switch — {why}")
    return _out(stat, c["n"], v, reason)


# ============================================================================================ T-728 VIX-beta sort ==

def monthly_excess(P: dict, R: dict, months: Sequence[str]) -> tuple:
    """(R (months x ccys), days): month-end common fix to month-end common fix simple returns plus one month of
    (r_c - r_USD) of the previous month (T-368's leg convention); NaN where a fix or rate is missing."""
    ccys = P["ccys"]
    out = np.full((len(months), len(ccys)), np.nan)
    for j, m in enumerate(months):
        a, b = P["last"].get(madd(m, -1)), P["last"].get(m)
        us = rate_at(R, "USD", madd(m, -1))[0]
        if a is None or b is None or us is None:
            continue
        out[j] = P["X"][b] / P["X"][a] - 1.0 + (rate_vec(R, ccys, madd(m, -1)) - us) / 1200.0
    return out


def vix_month_end(vd: Sequence[str], vv, months: Sequence[str]) -> np.ndarray:
    """VIX close of each month's last print (NaN when none)."""
    out = np.full(len(months), np.nan)
    for j, m in enumerate(months):
        i = bisect.bisect_right(vd, month_end_day(m)) - 1
        if i >= 0 and vd[i][:7] == m:
            out[j] = vv[i]
    return out


def rolling_betas(Rm, dv, n: int = T728_BETA_N) -> np.ndarray:
    """B[t] = OLS slopes of Rm[s] on dv[s] over the n rows s = t-n..t-1 (all finite), NaN otherwise. Rm: (T x k)."""
    Rm, dv = np.asarray(Rm, float), np.asarray(dv, float)
    T, k = Rm.shape
    B = np.full((T, k), np.nan)
    for t in range(n, T):
        r, v = Rm[t - n:t], dv[t - n:t]
        if not (np.isfinite(r).all() and np.isfinite(v).all()):
            continue
        vc = v - v.mean()
        vv = float(vc @ vc)
        if vv > 0:
            B[t] = vc @ (r - r.mean(axis=0)) / vv
    return B


def rolling_betas_draws(Rm, DV, n: int = T728_BETA_N) -> np.ndarray:
    """Vectorised ``rolling_betas`` for many dv paths DV (draws x T): (draws x T x k); rows must be finite."""
    Rm, DV = np.asarray(Rm, float), np.asarray(DV, float)
    T, k = Rm.shape
    D = DV.shape[0]
    cR = np.vstack([np.zeros((1, k)), np.cumsum(Rm, axis=0)])
    cV = np.hstack([np.zeros((D, 1)), np.cumsum(DV, axis=1)])
    cVV = np.hstack([np.zeros((D, 1)), np.cumsum(DV * DV, axis=1)])
    cRV = np.concatenate([np.zeros((D, 1, k)), np.cumsum(DV[:, :, None] * Rm[None, :, :], axis=1)], axis=1)
    out = np.full((D, T, k), np.nan)
    t = np.arange(n, T)
    sR = cR[t] - cR[t - n]
    sV = cV[:, t] - cV[:, t - n]
    sVV = cVV[:, t] - cVV[:, t - n]
    sRV = cRV[:, t] - cRV[:, t - n]
    var = sVV - sV * sV / n
    cov = sRV - sV[:, :, None] * sR[None, :, :] / n
    with np.errstate(divide="ignore", invalid="ignore"):
        out[:, t] = np.where(var[:, :, None] > 0, cov / var[:, :, None], np.nan)
    return out


def t728_betas(P: dict, R: dict, vd: Sequence[str], vv, months: Sequence[str]) -> tuple:
    """(Rm, dv, B) over ``months``: month-end-to-month-end excess returns, the month-end VIX change and the rolling
    60-month betas (B[j] from rows j-60..j-1)."""
    Rm = monthly_excess(P, R, months)
    vme = vix_month_end(vd, vv, months)
    dv = np.r_[np.nan, np.diff(vme)]
    return Rm, dv, rolling_betas(Rm, dv)


def t728_decision_beta(P: dict, B: np.ndarray, midx: dict, H: str) -> Optional[np.ndarray]:
    """Betas behind holding month H (decided at the end of t = H-1): row t of B, i.e. the 60 months H-61..H-2 (the
    one-month skip). None when not all finite, or when H.10 had not published the window's last month-end fix (month
    H-2's) by the decision day."""
    t = madd(H, -1)
    j = midx.get(t)
    if j is None or not np.isfinite(B[j]).all():
        return None
    lw = P["last"].get(madd(t, -1))
    if lw is None or P["rel"][lw] > month_end_day(t):
        return None
    return B[j]


def sort_weights(beta: np.ndarray, k: int = T728_K) -> np.ndarray:
    """+1/k on the k lowest betas, -1/k on the k highest (ties keep the universe order)."""
    order = np.argsort(beta, kind="stable")
    w = np.zeros(beta.size)
    w[order[:k]] = 1.0 / k
    w[order[-k:]] = -1.0 / k
    return w


def sort_net(W, Rh, cost, admin) -> tuple:
    """(net, gross) of weight rows W on holding returns Rh: ``cost`` per unit traded, ``admin`` a year per unit held."""
    W, Rh = np.asarray(W, float), np.asarray(Rh, float)
    prev = np.vstack([np.zeros((1, W.shape[-1])), W[:-1]])
    gross = (W * Rh).sum(axis=-1)
    tc = (np.abs(W - prev) * cost).sum(axis=-1)
    fc = (np.abs(W) * admin).sum(axis=-1) / 12.0
    return gross - tc - fc, gross


def t728_core(archive) -> dict:
    def run():
        P = _panel(archive, U11)
        pit = _pit(archive)
        if not P["days"] or pit is None:
            return {"ok": False}
        R = _rates(archive)
        vd, vv, _ = _vix_arr(archive)
        last_full = madd(P["days"][-1][:7], -1)
        months = mrange("2002-06", last_full)
        Rm, dv, B = t728_betas(P, R, vd, vv, months)
        midx = {m: i for i, m in enumerate(months)}
        lag = LagRates(R)
        hold = mrange(*T728_HOLD)
        cb, ad = FX.em_costs()
        cost = np.array([cb[c] / 1e4 for c in U11])
        admin = np.array([ad[c] for c in U11])
        rows = []
        for H in hold:
            t = madd(H, -1)
            f, e = P["first"].get(H), P["first"].get(madd(H, 1))
            bj = t728_decision_beta(P, B, midx, H)
            if bj is None or f is None or e is None:
                continue                                   # incl. the beta window's last month-end fix not yet published
            j = midx[t]
            us = rate_at(R, "USD", t)[0]
            if us is None:
                continue
            rh = P["X"][e] / P["X"][f] - 1.0 + (rate_vec(R, U11, t) - us) / 1200.0
            if not np.isfinite(rh).all():
                continue
            wc = carry_weights(pit, month_end_day(t))
            lr = leg_returns(P, R, H, G10U)
            if wc is None or lr is None:
                continue
            carry = float(sum(wc[c] * lr[c] for c in G10U))
            wl = carry_weights(lag, month_end_day(t))
            carry_l = float(sum(wl[c] * lr[c] for c in G10U)) if wl is not None else float("nan")
            rk = rate_vec(R, U11, madd(t, -1))
            rows.append({"H": H, "j": j, "beta": bj.copy(), "rh": rh, "carry": carry, "carry_lag2": carry_l,
                         "dol": float(rh.mean()), "dol9": float(rh[:9].mean()), "rate_rank": rk})
        if not rows:
            return {"ok": False}
        W = np.array([sort_weights(r["beta"]) for r in rows])
        Rh = np.array([r["rh"] for r in rows])
        net, gross = sort_net(W, Rh, cost, admin)
        lit_net, _ = sort_net(W, Rh, np.full(len(U11), 2e-4), np.full(len(U11), 0.01))
        carry = np.array([r["carry"] for r in rows])
        dol = np.array([r["dol"] for r in rows])
        dol9 = np.array([r["dol9"] for r in rows])
        Hs = [r["H"] for r in rows]
        n = len(rows)
        lags = (CAL.nw_lags(n), 12)
        alphas = {}
        for nm, Xf in (("carry+DOL", np.column_stack([carry, dol])), ("carry", carry[:, None]), ("DOL", dol[:, None])):
            for lg in lags:
                r_ = XA.ols_nw_all(net, Xf, lg)
                alphas[f"{nm} lag {lg}"] = {"alpha_ann": 12 * r_["coef"][0] if r_.get("coef") else None,
                                            "t": r_["t"][0] if r_.get("t") else None}
        a9 = XA.ols_nw_all(net, np.column_stack([carry, dol9]), lags[0])
        # reported: carry ranked on fixed month t-2 rates (the proxy clock may lead the IR3TIB01 release)
        carry_l = np.array([r["carry_lag2"] for r in rows])
        okl = np.isfinite(carry_l)
        alphas_lag2 = {}
        for nm, Xf in (("carry+DOL", np.column_stack([carry_l, dol])), ("carry", carry_l[:, None])):
            for lg in lags:
                r_ = XA.ols_nw_all(net[okl], Xf[okl], lg)
                alphas_lag2[f"{nm} lag {lg}"] = {"t": r_["t"][0] if r_.get("t") else None, "n": int(okl.sum())}
        rcor = []
        for r in rows:
            if np.isfinite(r["rate_rank"]).all():
                a = np.argsort(np.argsort(r["beta"])).astype(float)
                b = np.argsort(np.argsort(r["rate_rank"])).astype(float)
                rcor.append(float(np.corrcoef(a, b)[0, 1]))
        # placebos
        jj = np.array([r["j"] for r in rows])
        span = slice(int(jj.min()) - T728_BETA_N, int(jj.max()))
        full_ok = np.isfinite(Rm[span]).all(axis=1) & np.isfinite(dv[span])
        Rs, Vs = Rm[span][full_ok], dv[span][full_ok]
        vc = Vs - Vs.mean()
        b_static = vc @ (Rs - Rs.mean(axis=0)) / (vc @ vc)
        Ws = np.tile(sort_weights(b_static), (n, 1))
        static_net, _ = sort_net(Ws, Rh, cost, admin)
        rng = np.random.default_rng(SEED)
        lo = int(jj.min()) - T728_BETA_N
        hi = int(jj.max())
        seg_ok = np.isfinite(Rm[lo:hi]).all() and np.isfinite(dv[lo:hi]).all()
        plac = None
        if seg_ok:
            # rows lo..hi-1 feed every window; one zero row is appended so the last decision (row hi) has an index
            Rseg = np.vstack([Rm[lo:hi], np.zeros((1, Rm.shape[1]))])
            Vseg = dv[lo:hi]
            DV = np.array([np.r_[rng.permutation(Vseg), 0.0] for _ in range(T728_N_PLACEBO)])
            Bd = rolling_betas_draws(Rseg, DV)
            tpos = jj - lo
            Bsel = Bd[:, tpos, :]
            order = np.argsort(Bsel, axis=2, kind="stable")
            Wd = np.zeros_like(Bsel)
            np.put_along_axis(Wd, order[:, :, :T728_K], 1.0 / T728_K, axis=2)
            np.put_along_axis(Wd, order[:, :, -T728_K:], -1.0 / T728_K, axis=2)
            prev = np.concatenate([np.zeros((Wd.shape[0], 1, Wd.shape[2])), Wd[:, :-1]], axis=1)
            pn = (Wd * Rh[None]).sum(axis=2) - (np.abs(Wd - prev) * cost).sum(axis=2) - (np.abs(Wd) * admin).sum(axis=2) / 12.0
            sd_ = pn.std(axis=1, ddof=1)
            plac = np.where(sd_ > 0, pn.mean(axis=1) / np.where(sd_ > 0, sd_, 1.0), np.nan) * math.sqrt(12)
        # 12-currency carry (reported)
        stale = [H for H in Hs if madd(H, -1) > STALE_THROUGH]
        thr = np.array([madd(H, -1) <= STALE_THROUGH for H in Hs])
        return {"ok": True, "n": n, "months": Hs, "net": net, "gross": gross, "lit_net": lit_net, "carry": carry,
                "dol": dol, "alphas": alphas, "alpha_dol9": {"t": a9["t"][0] if a9.get("t") else None},
                "alphas_carry_lag2": alphas_lag2, "carry_lag2_sharpe_gross": _sr(carry_l[okl]),
                "rank_corr_mean": float(np.mean(rcor)) if rcor else None, "static_net": static_net, "placebo": plac,
                "turnover": float(np.abs(np.diff(W, axis=0)).sum(axis=1).mean()) if n > 1 else None,
                "long_counts": {c: int((W[:, k] > 0).sum()) for k, c in enumerate(U11)},
                "short_counts": {c: int((W[:, k] < 0).sum()) for k, c in enumerate(U11)},
                "corr_carry": float(np.corrcoef(net, carry)[0, 1]), "corr_dol": float(np.corrcoef(net, dol)[0, 1]),
                "stale_months": stale, "sharpe_through_2026_01": _sr(net[thr]), "pit_mode": pit.mode}
    return CAL._cached(archive, ("b13_gaps_fx", "T-728"), run)


def b13_gaps_fx_vix_beta_sort(archive):
    """T-728: long low / short high 60-month VIX-change-beta currencies (11 vs USD) earns net Sharpe > 0.3 with alpha
    over carry and DOL (Fan-Londono-Xiao tail-factor proxy)."""
    miss = B7C._missing(archive, [SPOT_B, RATE_B, VIX_B] + clock_bundles())
    if miss:
        return miss
    c = t728_core(archive)
    if not c.get("ok") or c["n"] < 8:
        return _out({"n": c.get("n", 0)}, c.get("n", 0), "inconclusive", "too few holding months with every fix and rate")
    net, n = c["net"], c["n"]
    sr = _sr(net)
    sb = sb_ci(net)
    lo_ok, lo_note = BW.resolve(sb["ci"][0], sb["ci_mc_se"][0], 0.0, "gt")
    h1 = np.array([H < T728_SPLIT for H in c["months"]])
    halves = [float(net[h1].mean()), float(net[~h1].mean())]
    arows = [(f"{k} t {_s(v['t'], 2)}", None if v["t"] is None else v["t"] > T728_T_BAR,
              v["t"] is not None and v["t"] < -_N.inv_cdf(0.975)) for k, v in c["alphas"].items()]
    a_row = proxy_cap(BW.all_constructions(arows, f"alpha HAC t > {T728_T_BAR:g} vs carry (T-368 on point-in-time ranks) "
                                                  f"and DOL, every reading (rule 11)"), _pit(archive), "the carry control")
    panel = FX._panel(archive, XA.T605_FILL_TO)
    fam = dict(XA.t605_family_sharpes(archive, panel)["sharpes"])
    ms = FX.mrange(*FX.MOM_WINDOW)
    for f, s, dd in FX.MOM_FAMILY:
        x = FX.momentum_backtest(panel, FX.G10_FX, ms, f, s, dd, FX.MOM_COST_BPS, True)["net"]
        fam[f"T-478:f{f}_{s}_{'diff' if dd else 'spot'}"] = _sr_pp(x)
    fam["T-728:this"] = _sr_pp(net)
    dsr_row, d = family_dsr_row(net, list(fam.values()), T728_N_TRIALS, 0,
                                f"DSR > {DSR_PASS} at {T728_N_TRIALS} trials (T-368 6, T-431 4, T-478 16, this; T-431's KRW "
                                f"trial not computable here)", ge=False)
    rows = [(f"net Sharpe {_s(sr, 3)} > {T728_SR_BAR}", None if sr is None else sr > T728_SR_BAR,
             sb["ci"][1] is not None and sb["ci"][1] <= T728_SR_BAR),
            (f"stationary-bootstrap 95% lower bound {_s(sb['ci'][0], 3)} > 0{lo_note}", lo_ok,
             sb["ci"][1] is not None and sb["ci"][1] <= 0.0),
            a_row,
            (f"both halves positive (2013-2019 {_pc(halves[0], 3)}/month, 2020-2026 {_pc(halves[1], 3)}/month)",
             all(h > 0 for h in halves), False),
            dsr_row]
    v, why, crit = CAL._judge(rows, n, T728_MIN_N, "holding months")
    plac = c["placebo"]
    pl = None if plac is None else placebo_summary(plac, sr)
    stat = {"n": n, "first_last": [c["months"][0], c["months"][-1]], "sharpe": sr, "gross_sharpe": _sr(c["gross"]),
            "sb_ci": sb, "halves_mean": halves, "alphas": c["alphas"], "alpha_vs_carry_dol9_t": c["alpha_dol9"]["t"],
            "rank_corr_beta_rate_mean": c["rank_corr_mean"], "static_beta_sharpe": _sr(c["static_net"]),
            "shuffled_vix_placebo": pl, "claim_literal_cost_sharpe": _sr(c["lit_net"]), "turnover": c["turnover"],
            "long_counts": c["long_counts"], "short_counts": c["short_counts"], "corr_carry": c["corr_carry"],
            "corr_dol": c["corr_dol"], "carry_factor_sharpe_gross": _sr(c["carry"]), "dol_sharpe": _sr(c["dol"]),
            "alphas_vs_carry_lag2": c["alphas_carry_lag2"], "carry_lag2_sharpe_gross": c["carry_lag2_sharpe_gross"],
            "stale_accrual_months": c["stale_months"], "sharpe_through_2026_01": c["sharpe_through_2026_01"], "dsr": d,
            "family_sharpes_pp": fam, "pit_mode": c["pit_mode"], "criteria": crit, "verdict": v}
    at = c["alphas"]
    top = lambda cnt: ", ".join(f"{k} {x}" for k, x in sorted(cnt.items(), key=lambda kv: -kv[1])[:4])
    reason = (f"11 currencies (9 G10 + MXN + ZAR) vs USD, 60-month betas of month-end-to-month-end excess returns on the "
              f"month-end VIX change over the months ending t-1, long the 3 lowest / short the 3 highest, first common fix "
              f"of t+1 to the first of t+2, T-368/T-431 costs, {n} months {c['months'][0]}..{c['months'][-1]}: net Sharpe "
              f"{_s(sr, 3)} (gross {_s(stat['gross_sharpe'], 3)}), stationary-bootstrap 95% CI [{_s(sb['ci'][0], 3)}, "
              f"{_s(sb['ci'][1], 3)}]; halves {_pc(halves[0], 3)} / {_pc(halves[1], 3)} per month; alpha t vs carry + DOL "
              f"{_s(at[f'carry+DOL lag {CAL.nw_lags(n)}']['t'], 2)} (lag 12 {_s(at['carry+DOL lag 12']['t'], 2)}), vs carry "
              f"{_s(at[f'carry lag {CAL.nw_lags(n)}']['t'], 2)}, vs DOL {_s(at[f'DOL lag {CAL.nw_lags(n)}']['t'], 2)} (carry "
              f"ranked on the {c['pit_mode']} rate clock); DSR {_f(d.get('dsr', d.get('dsr_upper_bound')))} (an upper bound when a family Sharpe is uncomputable) at {T728_N_TRIALS} trials. Reported: "
              f"correlation with carry {c['corr_carry']:+.2f}, with DOL {c['corr_dol']:+.2f}; mean rank correlation of beta "
              f"with month t-1 rates {_s(c['rank_corr_mean'], 2)}; most often long {top(c['long_counts'])}, short "
              f"{top(c['short_counts'])}; static full-sample-beta placebo Sharpe {_s(stat['static_beta_sharpe'], 3)}; "
              f"shuffled-VIX placebo 95th pct {_s(pl['p95'] if pl else None, 3)} (observed at the "
              f"{_pct0(pl['pct_rank'] if pl else None)} rank); alpha t vs carry ranked on fixed month t-2 rates + DOL "
              f"{_s(c['alphas_carry_lag2'][f'carry+DOL lag {CAL.nw_lags(n)}']['t'], 2)} (vs that carry alone "
              f"{_s(c['alphas_carry_lag2'][f'carry lag {CAL.nw_lags(n)}']['t'], 2)}); claim-literal costs Sharpe "
              f"{_s(stat['claim_literal_cost_sharpe'], 3)}; EUR/GBP accruals forward-filled in {len(c['stale_months'])} "
              f"months (Sharpe through 2026-01 {_s(c['sharpe_through_2026_01'], 3)}). A VIX-change beta is a proxy for "
              f"the paper's put-based tail factor: a fail here does not refute it — {why}")
    return _out(stat, n, v, reason)


HARNESSES = {"b13_gaps_fx_global_rv_dol": b13_gaps_fx_global_rv_dol,
             "b13_gaps_fx_equity_vrp_dol": b13_gaps_fx_equity_vrp_dol,
             "b13_gaps_fx_vol_innovation_carry": b13_gaps_fx_vol_innovation_carry,
             "b13_gaps_fx_vix_beta_sort": b13_gaps_fx_vix_beta_sort}
THEORY_MAP = {"T-719": "b13_gaps_fx_global_rv_dol", "T-720": "b13_gaps_fx_equity_vrp_dol",
              "T-725": "b13_gaps_fx_vol_innovation_carry", "T-728": "b13_gaps_fx_vix_beta_sort"}
