"""
Batch 6c, group ``cal``: five calendar claims on the underlying (month-end rebalancing flows, the Friday-minus-Monday
speculative spread, the pre-holiday effect and the presidential cycle).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-345  SPY's return over the last two sessions of the month in months where SPY beat TLT month-to-date by more than
           2 pp at the T-3 close (the 3rd-to-last session), minus the same return in all other months, 2002-08..2026-09:
           < -15 bps net of 2 bps per leg, permutation p < 0.05 (and the 3-month block bootstrap the null also names,
           rule 11), the gap negative (net) in 2002-2013 and in 2014-2026; min_n 80 signal months.
  * T-450  OLS slope of SPY's 4-session excess return (the last 3 sessions of the month plus the first of the next, from
           the close 3 sessions before the last) on the month-to-date SPY-minus-AGG total-return differential at that
           close, 2003-10..2026-09: Newey-West t <= -2 over >= 250 monthly windows, negative slope in 2003-2014 and in
           2015-2026.
  * T-347  SPHB-minus-SPLV daily total-return spread, mean on Fridays minus mean on Mondays, 2011-05..2026-10: > 10 bps,
           p < 0.05 under both nulls the trial names (studentized 10-day block bootstrap of the day-flagged series AND a
           permutation of weekday labels within calendar weeks, rule 11), positive in 2011-2018 and in 2019-2026; min_n
           600 counted on the smaller of the Friday and Monday samples.
  * T-349  IWM's return on the last session before each scheduled NYSE holiday minus its mean on all other sessions,
           2000-05..2026-10: > 10 bps, studentized 10-day block-bootstrap p < 0.05, positive in 2000-2012 and 2013-2026;
           min_n 200 pre-holiday sessions.
  * T-357  The pre-registered year-3 test, exactly as registered: ^GSPC calendar-year price return in pre-election years
           (year 3 of the term) minus the mean of the other three cycle years, 1928-2025 complete years: > 5 pp,
           permutation p < 0.05 with the cycle label permuted within each 4-year block (10,000 draws), positive in
           1928-1976 and in 1977-2026; min_n 20 year-3 years. Its 5 other variants are not part of the test.

Conventions
  * Data. Bundles are read through ``archive.load``; a row is used only if its ``available_at`` is not after the
    bundle's capture time. ETF returns use Yahoo ``adjclose`` (split and dividend adjusted, i.e. total return); the
    indices (^GSPC, ^RUT) use ``close`` (price only: T-357 is a price-return claim, dividends excluded and flagged).
    A two-asset statistic uses the pair's common sessions.
  * NYSE schedule (T-349; rule-based, never inferred from price gaps). ``nyse_scheduled_holidays`` encodes the rules:
    New Year's Day (Sunday -> Monday; a Saturday New Year's is NOT moved to Friday 31 December, NYSE Rule 7.2's
    year-end exception), Martin Luther King Jr. Day (third Monday of January, from 1998), Washington's Birthday (third
    Monday of February), Good Friday (Easter Sunday - 2), Memorial Day (last Monday of May), Juneteenth (from 2022),
    Independence Day, Labor Day (first Monday of September), Thanksgiving (fourth Thursday of November) and Christmas;
    a Saturday holiday closes the Friday before, a Sunday holiday the Monday after. The rules are those in force since
    the 1971 Monday-holiday act and are refused for earlier years. ``UNSCHEDULED_CLOSURES`` lists the closures no one
    could schedule (Hurricane Gloria 1985, the Nixon funeral 1994, 11-14 September 2001, the Reagan funeral 2004, the
    Ford funeral 2007, Hurricane Sandy 2012, the G. H. W. Bush funeral 2018 and the Carter funeral 2025): they are not
    holidays, so the session before them is an ordinary day, but they are not sessions either. The pre-holiday session
    is the last rule-calendar session before a scheduled weekday holiday; a pre-holiday session whose bar is missing is
    counted and left out. The rule calendar is checked against the bars (weekdays with no bar that the rules leave open,
    bars on rule-closed days) and the check is reported.
  * Month-end windows (T-345, T-450; rule 10(a): the month-end calendar the claims name, so there is no grid phase).
    A month is used only when complete: the previous month supplies the base close (its last session) and a later month
    is in the data. T-345: decision at the T-3 close = the 3rd-to-last session; window = the last two sessions (T-3
    close to the last close). T-450: decision at the close 3 sessions before the last (the 4th-to-last session); window
    = that close to the first session of the next month (the last 3 sessions plus the first of the next month).
  * One information set (rules 4 and 12). The claims fix the signal at the decision close and the window from that
    close. The archive stamps a daily close available the next session, after a fill at that close, so each month-end
    claim is read twice: (a) the decision close as the live proxy for the signal (the claim as worded) and (b) the
    signal from the previous session's close, the window unchanged (the claims fix it). A criterion passes only when
    both readings pass, fails only when both fail, and is undecided (None) when they disagree. T-347, T-349 and T-357
    take no data-dependent decision (weekday, holiday and cycle calendars are known in advance).
  * Excess returns (T-450, rule 7). FRED DTB3 is a 91-day discount yield published a day late: at a decision on day d
    the rate is the print dated strictly before d, converted to r = -ln(1 - d/100 * 91/360) / (91/365); the window's
    bill return is exp(r * calendar days / 365) - 1.
  * Intervals and tests (rule 6). Difference-in-means statistics use the day- (or month-) flagged series whose mean is
    exactly the difference (``flag_diff_series``, ``contrast_series``), tested with the studentized circular block
    bootstrap of ``block_bootstrap_pvalue`` (blocks: 10 sessions for daily series, 3 months for T-345, as the trials
    state) and given a percentile block-bootstrap 95% CI. Permutation p-values are (#{draw at least as extreme} + 1) /
    (draws + 1), one-sided in the claimed direction. T-345 permutes the signal label across months; T-347 permutes
    weekday labels within calendar (ISO) weeks; T-357 permutes the cycle label within 4-year blocks. A "4-year block"
    is read two ways (the presidential term, years 1-4, and four-year blocks anchored on 1928, the anchor the library
    names); the permutation criterion passes only when both readings do (a borderline pass that flips under a permitted
    reading is not evidence, rule 11). T-450's slope uses the Newey-West (Bartlett) HAC t with the automatic lag
    floor(4 (n/100)^(2/9)); lags 0 and 12 are reported.
  * Monte-Carlo precision. A criterion's studentized bootstrap p is the mean over 5 seeds of 2000 resamples (the
    batch6b_bw convention); permutation p's use 10,000 draws. A resampled p decides "p < 0.05" only when its
    Monte-Carlo 95% band (p +/- 1.96 sqrt(p (1 - p) / draws)) lies on one side of 0.05; otherwise the criterion is
    undecided (None): a seed must not decide a verdict (rule 11, T-162). Reasons print each p with its band.
  * Costs (rule 9) as the claims state: T-345 charges 2 legs x 2 bps (4 bps) per signal month against the claim (net
    difference = gross + 4 bps) in the magnitude and both halves; T-347's net-of-cost Friday/Monday strategy (4 and 8 bps
    a week) and T-349's net-of-cost (2 bps per round trip) are reported, not criteria; T-450's threshold rule is reported
    net of 2 bps per active month.
  * Secondaries. Every declared variant the archive supports is reported with its p and Holm-adjusted p (variants
    whose data are missing count as p = 1 in the Holm ranking, the conservative choice); none is a pass criterion. A
    variant that needs an unarchived symbol (IWO, IWN, ARKK, FXI, EWY, INDA) is reported as None with what is missing,
    without capping the primary.
  * Below trial.min_n (rule 5) the verdict is never supported, and a failing criterion counts only when it fails
    decisively: its 95% interval lies wholly on the wrong side of the claimed bound, or, for a one-sided 5% test, the
    mirror one-sided test from the same draws rejects at 5% (for a t threshold, the mirror t beyond the threshold).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
(None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import block_bootstrap_pvalue

N_BOOT = 2000
N_PERM = 10000
N_SEEDS = 5                     # criterion bootstrap p's: the mean over 5 seeds of N_BOOT resamples (as batch6b_bw)
SEED = 0
ALPHA = 0.05
Z_MC = 1.959964                 # Monte-Carlo band of a resampled p: p +/- Z_MC * sqrt(p (1 - p) / draws)

SPY_B = "daily-history-SPY"
TLT_B = "daily-history-TLT"
AGG_B = "daily-history-AGG"
GLD_B = "daily-history-GLD"
SLV_B = "daily-history-SLV"
BTC_B = "daily-history-BTC-USD"
IWM_B = "daily-history-IWM"
RUT_B = "daily-history--RUT"
GSPC_B = "daily-history--GSPC"
SPHB_B = "daily-history-SPHB"
SPLV_B = "daily-history-SPLV"
USMV_B = "daily-history-USMV"
IWO_B = "daily-history-IWO"
IWN_B = "daily-history-IWN"
ARKK_B = "daily-history-ARKK"
VIX_B = "cboe-VIX-history"
DTB3_B = "fred-DTB3"
DGS10_B = "fred-DGS10"
FF3_B = "french-ff3-daily"

# T-345
T345_MIN_N = 80
T345_THR = 0.02                 # "more than 2 pp"
T345_BOUND = -0.0015            # "< -15 bps"
T345_COST = 2 * 0.0002          # "net of 2 bps per leg": 2 legs per signal month
T345_SPLIT = "2014-01"          # halves 2002-2013 / 2014-2026
T345_BLOCK = 3                  # "block bootstrap over months (block 3)"
T345_START, T345_END = "2002-01", "2026-12"
# T-450
T450_MIN_N = 250
T450_T = -2.0                   # "slope t <= -2"
T450_START, T450_END = "2003-10", "2026-09"
T450_SPLIT = "2015-01"          # halves 2003-2014 / 2015-2026
T450_THR = 0.02                 # the threshold rule (reported)
T450_RULE_COST = 0.0002         # "2 round trips/month at 1 bp" (reported)
# T-347
T347_MIN_N = 600
T347_BOUND = 0.0010             # "> 10 bps"
T347_SPLIT = "2019-01-01"       # halves 2011-2018 / 2019-2026
T347_BLOCK = 10
T347_COSTS = (0.0004, 0.0008)   # "about 4-8 bps/week" (reported)
# T-349
T349_MIN_N = 200
T349_BOUND = 0.0010             # "at least 10 bps"
T349_START = "2000-01-01"
T349_SPLIT = "2013-01-01"       # halves 2000-2012 / 2013-2026
T349_BLOCK = 10
T349_COST = 0.0002              # "10 round trips/yr at 1-2 bps" (reported)
# T-357
T357_MIN_N = 20
T357_BOUND = 0.05               # "> 5 percentage points"
T357_FIRST = 1928
T357_SPLIT = 1977               # halves 1928-1976 / 1977-2026
T357_LATE = 1990                # "1990-2026 reported separately"
FIRST_ELECTION = 1928           # 1928 was a presidential election year (year 4 of its term)


# ================================================================================================= data access ==

_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _daily(archive, name: str, field: str = "adjclose") -> tuple:
    """(days, values) of a Yahoo daily-history bundle: ``adjclose`` (a bar without one carries the previous
    adjclose/close ratio) or ``close``; bars with a non-positive or non-numeric close are skipped."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            try:
                c = float(v.get("close"))
            except (TypeError, ValueError):
                continue
            if not (c > 0 and math.isfinite(c)):
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            try:
                a = float(a)
            except (TypeError, ValueError):
                a = float("nan")
            by[d] = (c, a if a > 0 and math.isfinite(a) else float("nan"))
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, close, adj
    days, close, adj = _cached(archive, ("daily", name), load)
    return days, (adj if field == "adjclose" else close)


def _series(archive, name: str, field: Optional[str] = None) -> dict:
    """{day: value} of a Cboe index (close), FRED series (value) or French factor (``field``) bundle; non-numeric
    prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = v.get(field) if field else v.get("close", v.get("value"))
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("series", name, field), load)


def _align(*series) -> tuple:
    """Common sessions of several (days, values) series: (days, [values...])."""
    common = sorted(set(series[0][0]).intersection(*(set(s[0]) for s in series[1:])))
    out = []
    for days, vals in series:
        pos = {d: i for i, d in enumerate(days)}
        out.append(np.array([vals[pos[d]] for d in common], float))
    return common, out


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, date):
        return x.isoformat()
    return x


def _nb(n):
    return N_BOOT if n is None else int(n)


def _np(n):
    return N_PERM if n is None else int(n)


def _bps(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.1f}"


def _pp(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.2f}"


def _p(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.4f}"


def _fx(x, fmt: str) -> str:
    return "n/a" if x is None or not np.isfinite(x) else format(float(x), fmt)


def _ci_bps(c) -> str:
    return "[n/a]" if c is None or c[0] is None else f"[{c[0] * 1e4:+.1f}, {c[1] * 1e4:+.1f}]"


# ======================================================================================================== bills ==

def dtb3_cont(d_pct: float) -> float:
    """Continuous rate from a 91-day bill discount yield in percent (FRED DTB3), house rule 7."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


class Bills:
    """FRED DTB3 as a continuous rate known on a day: the print dated strictly before it (FRED publishes a day late)."""

    def __init__(self, dtb3: dict):
        self.k = sorted(dtb3)
        if not self.k:
            raise ValueError("no DTB3 prints")
        self.r = [dtb3_cont(float(dtb3[d])) for d in self.k]

    def rate(self, day: str) -> float:
        j = bisect.bisect_left(self.k, day) - 1
        return float(self.r[max(j, 0)])

    def growth(self, d0: str, d1: str) -> float:
        """Bill return from the close of d0 to the close of d1 at the rate known on d0."""
        days = (date.fromisoformat(d1) - date.fromisoformat(d0)).days
        return math.exp(self.rate(d0) * days / 365.0) - 1.0


# ============================================================================================== NYSE calendar ==

SCHEDULE_FROM = 1971            # the Monday-holiday rules below are in force from 1971
UNSCHEDULED_CLOSURES = {
    "1985-09-27": "Hurricane Gloria",
    "1994-04-27": "President Nixon's funeral",
    "2001-09-11": "September 11 attacks", "2001-09-12": "September 11 attacks",
    "2001-09-13": "September 11 attacks", "2001-09-14": "September 11 attacks",
    "2004-06-11": "President Reagan's funeral",
    "2007-01-02": "President Ford's funeral",
    "2012-10-29": "Hurricane Sandy", "2012-10-30": "Hurricane Sandy",
    "2018-12-05": "President George H. W. Bush's funeral",
    "2025-01-09": "President Carter's funeral",
}


def easter_sunday(y: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(y, month, day + 1)


def _nth_weekday(y: int, month: int, wd: int, n: int) -> date:
    d = date(y, month, 1)
    return d + timedelta(days=(wd - d.weekday()) % 7 + 7 * (n - 1))


def _last_weekday_of(y: int, month: int, wd: int) -> date:
    d = date(y + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def _observed(d: date) -> date:
    """NYSE observance: a Saturday holiday closes the Friday before, a Sunday holiday the Monday after."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


@lru_cache(maxsize=None)
def nyse_scheduled_holidays(year: int) -> dict:
    """{date: holiday} of the scheduled weekday NYSE closures in ``year`` under the rules in the module docstring
    (unscheduled closures are not holidays and are not included)."""
    if year < SCHEDULE_FROM:
        raise ValueError(f"the NYSE holiday rules are encoded from {SCHEDULE_FROM}; {year} is earlier")
    h = {}
    ny = date(year, 1, 1)
    if ny.weekday() < 5:
        h[ny] = "New Year's Day"
    elif ny.weekday() == 6:
        h[date(year, 1, 2)] = "New Year's Day"
    # a Saturday New Year's Day is not observed on Friday 31 December (NYSE Rule 7.2: end of the yearly accounting period)
    if year >= 1998:
        h[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    h[_nth_weekday(year, 2, 0, 3)] = "Washington's Birthday"
    h[easter_sunday(year) - timedelta(days=2)] = "Good Friday"
    h[_last_weekday_of(year, 5, 0)] = "Memorial Day"
    if year >= 2022:
        h[_observed(date(year, 6, 19))] = "Juneteenth"
    h[_observed(date(year, 7, 4))] = "Independence Day"
    h[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    h[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving Day"
    h[_observed(date(year, 12, 25))] = "Christmas Day"
    return h


def nyse_closure(day) -> Optional[str]:
    """Why the NYSE was closed on ``day`` (weekend, scheduled holiday or unscheduled closure), or None on a session."""
    d = date.fromisoformat(day) if isinstance(day, str) else day
    if d.weekday() >= 5:
        return "weekend"
    why = UNSCHEDULED_CLOSURES.get(d.isoformat())
    return why if why else nyse_scheduled_holidays(d.year).get(d)


def is_nyse_session(day) -> bool:
    return nyse_closure(day) is None


def prev_session(d: date) -> date:
    d = d - timedelta(days=1)
    while not is_nyse_session(d):
        d -= timedelta(days=1)
    return d


def next_session(d: date) -> date:
    d = d + timedelta(days=1)
    while not is_nyse_session(d):
        d += timedelta(days=1)
    return d


def scheduled_holidays(first: str, last: str) -> list:
    """Scheduled weekday holidays dated in [first, last], in order: [(date, name)]."""
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    out = []
    for y in range(a.year, b.year + 1):
        out += [(d, n) for d, n in nyse_scheduled_holidays(y).items() if a <= d <= b]
    return sorted(out)


def pre_holiday_sessions(first: str, last: str) -> dict:
    """{ISO session: holiday} of the last rule-calendar session before each scheduled holiday, for sessions in
    [first, last] (holidays up to two weeks past ``last`` are considered, so a pre-holiday ``last`` is caught)."""
    out = {}
    end = (date.fromisoformat(last) + timedelta(days=14)).isoformat()
    for h, name in scheduled_holidays(first, end):
        s = prev_session(h).isoformat()
        if first <= s <= last:
            out.setdefault(s, name)
    return out


def post_holiday_sessions(first: str, last: str) -> dict:
    """{ISO session: holiday} of the first rule-calendar session after each scheduled holiday, in [first, last]."""
    out = {}
    start = (date.fromisoformat(first) - timedelta(days=14)).isoformat()
    for h, name in scheduled_holidays(start, last):
        s = next_session(h).isoformat()
        if first <= s <= last:
            out.setdefault(s, name)
    return out


def calendar_check(days: Sequence[str]) -> dict:
    """The rule calendar against a bar series over [first bar, last bar]: weekdays without a bar that the rules leave
    open (unexplained gaps), bars on rule-closed days, and the gaps that are scheduled holidays / unscheduled closures."""
    if not days:
        return {"unexplained_gaps": [], "bars_on_closed_days": [], "scheduled_holiday_gaps": 0, "unscheduled_closure_gaps": 0}
    have = set(days)
    d, end = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    gaps, closed_bars, sched, unsched = [], [], 0, 0
    while d <= end:
        iso = d.isoformat()
        if d.weekday() < 5:
            why = nyse_closure(d)
            if iso in have and why is not None:
                closed_bars.append(iso)
            elif iso not in have and why is None:
                gaps.append(iso)
            elif iso not in have:
                if iso in UNSCHEDULED_CLOSURES:
                    unsched += 1
                else:
                    sched += 1
        d += timedelta(days=1)
    return {"unexplained_gaps": gaps, "bars_on_closed_days": closed_bars, "scheduled_holiday_gaps": sched,
            "unscheduled_closure_gaps": unsched}


# ================================================================================================= statistics ==

def flag_diff_series(x, flag) -> np.ndarray:
    """Day-flagged series whose mean is mean(x[flag]) - mean(x[~flag]) and whose block-resampled mean carries the
    within-group sampling spread of that difference."""
    x = np.asarray(x, float); f = np.asarray(flag, bool)
    p = f.mean()
    me, mo = x[f].mean(), x[~f].mean()
    w = np.where(f, 1.0 / p, -1.0 / (1.0 - p))
    return (me - mo) + w * (x - np.where(f, me, mo))


def contrast_series(x, fa, fb) -> np.ndarray:
    """Flagged series whose mean is mean(x[fa]) - mean(x[fb]) for two disjoint day groups (other days weigh 0)."""
    x = np.asarray(x, float); a = np.asarray(fa, bool); b = np.asarray(fb, bool)
    n = len(x); pa, pb = a.sum() / n, b.sum() / n
    ma, mb = x[a].mean(), x[b].mean()
    return (ma - mb) + np.where(a, (x - ma) / pa, 0.0) - np.where(b, (x - mb) / pb, 0.0)


def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def mean_ci(d, block: int, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> list:
    """Two-sided percentile circular block-bootstrap CI of the mean of d."""
    d = np.asarray(d, float)
    if d.size < 2:
        return [None, None]
    rng = np.random.default_rng(seed)
    nb, out, done = _nb(n_boot), [], 0
    while done < nb:
        k = min(500, nb - done)
        out.append(d[_boot_idx(rng, d.size, block, k)].mean(axis=1)); done += k
    m = np.concatenate(out)
    q = (1 - level) / 2
    return [float(np.quantile(m, q)), float(np.quantile(m, 1 - q))]


def studentized_p(d, block: int, n_boot: Optional[int] = None, seed: int = SEED, n_seeds: int = 1) -> tuple:
    """(p_greater, p_less): studentized circular block-bootstrap one-sided p-values for H0 mean(d) <= 0 and H0 mean(d)
    >= 0 (``block_bootstrap_pvalue``), each the mean over ``n_seeds`` seeds (seed, seed + 1, ...); (None, None) below
    its 8-period minimum."""
    d = np.asarray(d, float)
    if d.size < 8 or not np.isfinite(d).all():
        return None, None
    z = np.zeros_like(d)
    nb = _nb(n_boot)
    pg = [block_bootstrap_pvalue(d, z, n_boot=nb, block_len=block, seed=seed + k) for k in range(n_seeds)]
    pl = [block_bootstrap_pvalue(-d, z, n_boot=nb, block_len=block, seed=seed + k) for k in range(n_seeds)]
    return float(np.mean(pg)), float(np.mean(pl))


def decide_p(p: Optional[float], draws: int, alpha: float = ALPHA) -> Optional[bool]:
    """A resampled p decides 'p < alpha' only when its Monte-Carlo 95% band lies on one side of alpha: True when
    p + Z_MC * se < alpha, False when p - Z_MC * se >= alpha, None (undecided at this precision) otherwise; se =
    sqrt(p (1 - p) / draws). A seed must not decide a verdict (rule 11: a borderline result that flips under a
    permitted alternative is not evidence)."""
    if p is None or not np.isfinite(p):
        return None
    se = math.sqrt(max(p * (1 - p), 0.0) / max(int(draws), 1))
    if p + Z_MC * se < alpha:
        return True
    if p - Z_MC * se >= alpha:
        return False
    return None


def _mc(p: Optional[float], draws: int) -> str:
    """p with its Monte-Carlo 95% half-width."""
    if p is None or not np.isfinite(p):
        return "n/a"
    return f"{p:.4f} (MC +/-{Z_MC * math.sqrt(max(p * (1 - p), 0.0) / max(int(draws), 1)):.4f})"


def permuted_labels(labels, groups=None, n_perm: Optional[int] = None, seed: int = SEED, chunk: int = 500):
    """Yields (k x n) arrays of ``labels`` permuted within ``groups`` (integer ids; the whole sample when None)."""
    labels = np.asarray(labels)
    n = labels.size
    g = np.zeros(n) if groups is None else np.asarray(groups, float)
    order = np.argsort(g, kind="stable")
    gs, ls = g[order], labels[order]
    rng = np.random.default_rng(seed)
    total, done = _np(n_perm), 0
    while done < total:
        k = min(chunk, total - done)
        pos = np.argsort(gs[None, :] + rng.random((k, n)), axis=1)    # random order inside each contiguous group
        out = np.empty((k, n), dtype=labels.dtype)
        out[:, order] = ls[pos]
        yield out
        done += k


def _perm_p(obs: float, draws: np.ndarray) -> tuple:
    """(p_greater, p_less) of an observed statistic against permutation draws."""
    n = draws.size
    return float((np.sum(draws >= obs - 1e-15) + 1) / (n + 1)), float((np.sum(draws <= obs + 1e-15) + 1) / (n + 1))


def label_perm_diff(x, flag, groups=None, n_perm: Optional[int] = None, seed: int = SEED) -> tuple:
    """Permutation null of mean(x[flag]) - mean(x[~flag]) with the flag permuted (within ``groups`` if given):
    (observed, p_greater, p_less)."""
    x = np.asarray(x, float); f = np.asarray(flag, bool)
    k, n = int(f.sum()), f.size
    obs = float(x[f].mean() - x[~f].mean())
    tot = x.sum()
    draws = []
    for L in permuted_labels(f.astype(np.int8), groups, n_perm, seed):
        s = L.astype(float) @ x
        draws.append(s / k - (tot - s) / (n - k))
    pg, pl = _perm_p(obs, np.concatenate(draws))
    return obs, pg, pl


def _holm(ps: dict, m: Optional[int] = None) -> dict:
    """Holm step-down adjusted p-values; entries whose p is None rank last as p = 1 (``m`` defaults to len(ps))."""
    items = sorted(((k, 1.0 if v is None else float(v)) for k, v in ps.items()), key=lambda kv: kv[1])
    m = len(items) if m is None else m
    out, run = {}, 0.0
    for j, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - j) * p))
        out[k] = None if ps[k] is None else run
    return out


def _agree(oks) -> Optional[bool]:
    """Rules 11/12: True only when every reading passes, False only when every reading fails, else None (undecided)."""
    oks = list(oks)
    if any(o is None for o in oks):
        return None
    if all(oks):
        return True
    if not any(oks):
        return False
    return None


UNDECIDED = ("undecided: the rule-11/12 readings disagree or a Monte-Carlo band of p straddles 0.05, so the criterion is "
             "computed but not decided")


def _undecided(rows, note: str = UNDECIDED) -> list:
    """Marks the criteria that were computed but came out undecided (None), so the verdict text does not read as
    'not implemented'."""
    return [(name + f" ({note})" if ok is None else name, ok, dec) for name, ok, dec in rows]


def _judge(rows, n: int, min_n: int, unit: str) -> tuple:
    """Verdict over ``rows`` [(name, ok True/False/None, decisive bool)]: at face value at or above min_n; below it
    house rule 5 (never supported; a failure counts only when decisive, any other failure is undecided). Returns
    (verdict, _verdict explanation, criteria list)."""
    if n >= min_n:
        crit = [(name, ok) for name, ok, _ in rows]
        v, why = _verdict(crit)
        return v, why, crit
    crit = [(name, None) if ok is None else (name, True) if ok else (name + " (fails decisively below min_n)", False) if dec
            else (name + " (fails, not decisively, below min_n: undecided)", None) for name, ok, dec in rows]
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", None))
    v, why = _verdict(crit)
    return v, (f"only {n} {unit}, below the trial's min_n {min_n}: never supported and a failing criterion counts only "
               f"when it fails decisively (house rule 5): {why}"), crit


def group_test(x, flag, block: int, n_boot: Optional[int] = None, seed: int = SEED, n_seeds: int = 1,
               pvals: bool = True) -> dict:
    """Flagged-minus-other difference in means: point, percentile 95% CI and (``pvals``) studentized one-sided
    p-values over ``n_seeds`` seeds (``draws`` = the resamples behind each p)."""
    x = np.asarray(x, float); f = np.asarray(flag, bool)
    out = {"n_event": int(f.sum()), "n_other": int((~f).sum()), "diff": None, "ci": [None, None],
           "p_greater": None, "p_less": None, "mean_event": None, "mean_other": None, "draws": _nb(n_boot) * n_seeds}
    if f.sum() < 2 or (~f).sum() < 2:
        return out
    d = flag_diff_series(x, f)
    pg, pl = studentized_p(d, block, n_boot, seed, n_seeds) if pvals else (None, None)
    out.update(diff=float(d.mean()), ci=mean_ci(d, block, n_boot, seed), p_greater=pg, p_less=pl,
               mean_event=float(x[f].mean()), mean_other=float(x[~f].mean()))
    return out


def _two_sided(pg, pl):
    return None if pg is None or pl is None else float(min(1.0, 2 * min(pg, pl)))


def _point_diff(x, f) -> Optional[float]:
    x = np.asarray(x, float); f = np.asarray(f, bool)
    if f.sum() == 0 or (~f).sum() == 0:
        return None
    return float(x[f].mean() - x[~f].mean())


# ============================================================================================ month-end windows ==

def month_sessions(days: Sequence[str]) -> tuple:
    """(months in order, {month: [session indexes]})."""
    by = {}
    for i, d in enumerate(days):
        by.setdefault(d[:7], []).append(i)
    return sorted(by), by


def month_end_table(days: Sequence[str], a, b=None, decision: int = 3, lag: int = 0, exit_next: bool = False,
                    first: str = "0000-00", last: str = "9999-99", base: str = "month") -> list:
    """Per complete month m in [first, last] (a previous month gives the base close, a later month is in the data):
    the decision session is the ``decision``-th-to-last session of m, the signal session ``lag`` sessions before it
    (rule 12's previous-close reading when lag = 1). S = to-date return of ``a`` at the signal close minus that of ``b``
    (``a`` alone when b is None), from the last close of the previous month (``base`` = "quarter": of the previous
    quarter). Window: decision close to the last close of m, or (``exit_next``) to the first close of the next month.
    Rows: dict(month, signal_day, decision_day, exit_day, S, ra, rb)."""
    a = np.asarray(a, float); b = None if b is None else np.asarray(b, float)
    months, by = month_sessions(days)
    out = []
    for j in range(1, len(months) - 1):
        m = months[j]
        if not (first <= m <= last):
            continue
        idx = by[m]
        if len(idx) < decision + lag + 1:
            continue
        if base == "quarter":
            qs = (int(m[5:7]) - 1) // 3 * 3 + 1           # the quarter's first month
            prev = _prev_month(f"{m[:4]}-{qs:02d}")
            if prev not in by:
                continue
            bi = by[prev][-1]
        else:
            if months[j - 1] != _prev_month(m):
                continue
            bi = by[months[j - 1]][-1]
        di = idx[-decision]
        si = di - lag
        ei = by[months[j + 1]][0] if exit_next else idx[-1]
        if exit_next and months[j + 1] != _next_month(m):
            continue
        s = a[si] / a[bi] - 1 - (0.0 if b is None else b[si] / b[bi] - 1)
        out.append({"month": m, "signal_day": days[si], "decision_day": days[di], "exit_day": days[ei], "S": float(s),
                    "ra": float(a[ei] / a[di] - 1), "rb": None if b is None else float(b[ei] / b[di] - 1)})
    return out


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"


# ====================================================================================== T-345 rebalancing flow ==

def conditional_month_test(x, flag, months, split: str, cost: float = 0.0, block: int = T345_BLOCK,
                           n_perm: Optional[int] = None, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Signal-month mean of x minus other-month mean, gross and net (net = gross + cost: a cost charged against a claimed
    negative gap); permutation of the signal label across months (p_less: H0 no difference vs a negative gap); the
    studentized month-block bootstrap of the flagged series; halves split at ``split`` (net, with block CIs)."""
    x = np.asarray(x, float); f = np.asarray(flag, bool); ms = np.asarray(months)
    out = {"n_signal": int(f.sum()), "n_other": int((~f).sum()), "diff": None, "net": None}
    if f.sum() < 2 or (~f).sum() < 2 or x.size < 8:
        return out
    obs, ppg, ppl = label_perm_diff(x, f, None, n_perm, seed)
    g = group_test(x, f, block, n_boot, seed, N_SEEDS)
    halves = {}
    for lab, m in (("first", ms < split), ("second", ms >= split)):
        if f[m].sum() >= 2 and (~f[m]).sum() >= 2:
            gh = group_test(x[m], f[m], block, n_boot, seed, pvals=False)
            halves[lab] = {"n_signal": int(f[m].sum()), "n_other": int((~f[m]).sum()), "diff": gh["diff"],
                           "net": gh["diff"] + cost, "net_ci": [c + cost for c in gh["ci"]] if gh["ci"][0] is not None else [None, None]}
        else:
            halves[lab] = {"n_signal": int(f[m].sum()), "n_other": int((~f[m]).sum()), "diff": None, "net": None, "net_ci": [None, None]}
    out.update(diff=obs, net=obs + cost, mean_signal=float(x[f].mean()), mean_other=float(x[~f].mean()),
               perm_p_less=ppl, perm_p_greater=ppg, boot_p_less=g["p_less"], boot_p_greater=g["p_greater"],
               perm_draws=_np(n_perm), boot_draws=g["draws"],
               net_ci=[c + cost for c in g["ci"]] if g["ci"][0] is not None else [None, None], halves=halves)
    return out


def rebalancing_flow(spy, tlt, threshold: float = T345_THR, bound: float = T345_BOUND, cost: float = T345_COST,
                     first: str = T345_START, last: str = T345_END, split: str = T345_SPLIT, min_n: int = T345_MIN_N,
                     n_perm: Optional[int] = None, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-345 primary. ``spy``/``tlt``: (days, total-return closes). Signal month: SPY minus TLT month-to-date > threshold
    at the T-3 close; x = SPY's return from the T-3 close to the last close. Criteria (each under both rule-12
    readings): net difference < bound; permutation p < 0.05 and month-block bootstrap p < 0.05 (rule 11); the net gap
    negative in each half."""
    days, (a, b) = _align(spy, tlt)
    readings = {}
    for lab, lag in (("entry close", 0), ("previous close", 1)):
        tab = month_end_table(days, a, b, decision=3, lag=lag, first=first, last=last)
        if len(tab) < 8:
            readings[lab] = {"n_signal": 0, "n_months": len(tab)}
            continue
        x = np.array([r["ra"] for r in tab]); f = np.array([r["S"] > threshold for r in tab])
        mo = [r["month"] for r in tab]
        t = conditional_month_test(x, f, mo, split, cost, T345_BLOCK, n_perm, n_boot, seed)
        sp = np.array([r["ra"] - r["rb"] for r in tab])
        t.update(n_months=len(tab), first_month=mo[0], last_month=mo[-1],
                 spread_signal_mean=float(sp[f].mean()) if f.any() else None,
                 spread_signal_p_less=studentized_p(sp[f], T345_BLOCK, n_boot, seed)[1] if f.sum() >= 8 else None,
                 signal_months_2008_2020_2022=[m for m, s in zip(mo, f) if s and m[:4] in ("2008", "2020", "2022")])
        readings[lab] = t
    out = {"readings": readings}
    prim = readings["entry close"]
    n = int(prim.get("n_signal", 0))
    if any(r.get("diff") is None for r in readings.values()):
        v, why = _verdict([("enough complete months with both SPY and TLT to test", None)])
        out.update(n=n, verdict=v, reason=f"too few complete months with SPY and TLT ({prim.get('n_months', 0)}) — {why}")
        return out
    R = list(readings.values())
    c_mag = _agree([r["net"] < bound for r in R])
    c_sig = _agree([_agree([decide_p(r["perm_p_less"], r["perm_draws"]), decide_p(r["boot_p_less"], r["boot_draws"])]) for r in R])
    c_h1 = _agree([None if r["halves"]["first"]["net"] is None else r["halves"]["first"]["net"] < 0 for r in R])
    c_h2 = _agree([None if r["halves"]["second"]["net"] is None else r["halves"]["second"]["net"] < 0 for r in R])
    dec = [all(r["net_ci"][0] is not None and r["net_ci"][0] >= bound for r in R),
           all(decide_p(r["perm_p_greater"], r["perm_draws"]) is True and decide_p(r["boot_p_greater"], r["boot_draws"]) is True for r in R),
           all(r["halves"]["first"]["net_ci"][0] is not None and r["halves"]["first"]["net_ci"][0] >= 0 for r in R),
           all(r["halves"]["second"]["net_ci"][0] is not None and r["halves"]["second"]["net_ci"][0] >= 0 for r in R)]
    y1 = int(split[:4]) - 1
    names = [f"net difference < {bound * 1e4:+.0f} bps (net of {cost * 1e4:.0f} bps) under both rule-12 readings",
             "p < 0.05 under the label permutation and the 3-month block bootstrap (rule 11), both readings",
             f"net gap < 0 in {first[:4]}-{y1} (both readings)", f"net gap < 0 in {split[:4]}-{last[:4]} (both readings)"]
    rows = _undecided(list(zip(names, [c_mag, c_sig, c_h1, c_h2], dec)))
    v, why, crit = _judge(rows, n, min_n, "signal months")
    out.update(n=n, criteria=[[c, ok] for c, ok in crit], verdict=v)

    def one(lab, r):
        h1, h2 = r["halves"]["first"], r["halves"]["second"]
        return (f"{lab}: {r['n_signal']} signal of {r['n_months']} months ({r['first_month']}..{r['last_month']}), SPY "
                f"last-2-day {_bps(r['mean_signal'])} vs {_bps(r['mean_other'])} bps, gross {_bps(r['diff'])}, net "
                f"{_bps(r['net'])} bps (95% CI {_ci_bps(r['net_ci'])}), permutation p {_mc(r['perm_p_less'], r['perm_draws'])}, "
                f"block-bootstrap p {_mc(r['boot_p_less'], r['boot_draws'])}; halves net {_bps(h1['net'])} ({h1['n_signal']} signal) / {_bps(h2['net'])} "
                f"({h2['n_signal']} signal) bps")
    out["reason"] = "; ".join(one(k, r) for k, r in readings.items()) + f" — {why}"
    return out


def _tq_flags(S: np.ndarray, min_hist: int = 24) -> tuple:
    """Top-quartile variant: S > 0 and |S| at or above the 75th percentile of |S| over the prior months (expanding,
    at least ``min_hist`` months, point in time). Returns (usable mask, flag)."""
    use = np.zeros(S.size, bool); f = np.zeros(S.size, bool)
    for i in range(min_hist, S.size):
        q = np.quantile(np.abs(S[:i]), 0.75)
        use[i] = True; f[i] = S[i] > 0 and abs(S[i]) >= q
    return use, f


def rebalancing_grid(spy, tlt, gld=None, btc=None, n_perm: Optional[int] = None, n_boot: Optional[int] = None,
                     seed: int = SEED, first: str = T345_START, last: str = T345_END) -> dict:
    """T-345's declared 10-trial grid (reported, Holm over 10): thresholds 1 pp / 2 pp / top quartile of |S| x decision
    at T-3 / T-2 (the window runs from the decision close to the last close), quarter-end months only, the equity leg
    alone (SPY's last-2-day mean in signal months < 0, one-sample block bootstrap), and GLD / BTC month-to-date
    reversal analogues (own MTD > 2 pp at T-3 -> own last-two-day return lower)."""
    days, (a, b) = _align(spy, tlt)
    res = {}
    for dec in (3, 2):
        tab = month_end_table(days, a, b, decision=dec, first=first, last=last)
        if len(tab) < 8:
            continue
        S = np.array([r["S"] for r in tab]); x = np.array([r["ra"] for r in tab])
        for thr_lab, thr in (("1pp", 0.01), ("2pp", 0.02), ("top quartile", None)):
            if thr is None:
                use, f = _tq_flags(S)
                xs, fs = x[use], f[use]
            else:
                xs, fs = x, S > thr
            key = f"{thr_lab}, T-{dec}"
            if fs.sum() >= 2 and (~fs).sum() >= 2:
                obs, _, pl = label_perm_diff(xs, fs, None, n_perm, seed)
                res[key] = {"diff": obs, "p": pl, "n_signal": int(fs.sum())}
            else:
                res[key] = {"diff": None, "p": None, "n_signal": int(fs.sum())}
        if dec == 3:
            q = np.array([r["month"][5:7] in ("03", "06", "09", "12") for r in tab]); fq = (S > T345_THR) & q
            if fq.sum() >= 2 and (q & ~fq).sum() >= 2:
                obs, _, pl = label_perm_diff(x[q], fq[q], None, n_perm, seed)
                res["quarter-end, 2pp, T-3"] = {"diff": obs, "p": pl, "n_signal": int(fq.sum())}
            else:
                res["quarter-end, 2pp, T-3"] = {"diff": None, "p": None, "n_signal": int(fq.sum())}
            fe = S > T345_THR
            pe = studentized_p(x[fe], T345_BLOCK, n_boot, seed)[1] if fe.sum() >= 8 else None
            res["equity leg (SPY mean in signal months < 0)"] = {"mean": float(x[fe].mean()) if fe.any() else None, "p": pe, "n_signal": int(fe.sum())}
    for lab, ser in (("GLD analogue", gld), ("BTC analogue", btc)):
        if ser is None:
            res[lab] = {"diff": None, "p": None, "n_signal": 0, "note": "bundle not archived"}
            continue
        tab = month_end_table(ser[0], ser[1], None, decision=3, first=first, last=last)
        if len(tab) < 8:
            res[lab] = {"diff": None, "p": None, "n_signal": 0}
            continue
        x = np.array([r["ra"] for r in tab]); f = np.array([r["S"] > T345_THR for r in tab])
        if f.sum() >= 2 and (~f).sum() >= 2:
            obs, _, pl = label_perm_diff(x, f, None, n_perm, seed)
            res[lab] = {"diff": obs, "p": pl, "n_signal": int(f.sum()), "first_month": tab[0]["month"]}
        else:
            res[lab] = {"diff": None, "p": None, "n_signal": int(f.sum())}
    holm = _holm({k: v["p"] for k, v in res.items()}, m=10)
    for k in res:
        res[k]["p_holm"] = holm.get(k)
    return res


def b6c_cal_month_end_rebalancing(archive):
    """T-345: SPY last-two-day return after SPY beat TLT month-to-date by > 2 pp at the T-3 close."""
    miss = _missing(archive, [SPY_B, TLT_B])
    if miss:
        return miss
    spy, tlt = _daily(archive, SPY_B), _daily(archive, TLT_B)
    gld = _daily(archive, GLD_B) if _has(archive, GLD_B) else None
    btc = _daily(archive, BTC_B) if _has(archive, BTC_B) else None
    rep = rebalancing_flow(spy, tlt, n_perm=N_PERM, n_boot=N_BOOT)
    if rep.get("criteria") is not None:
        grid = rebalancing_grid(spy, tlt, gld, btc, n_perm=N_PERM, n_boot=N_BOOT)
        rep["declared_grid"] = grid
        g = grid.get("2pp, T-3", {})
        prim = rep["readings"]["entry close"]
        head, tail = rep["reason"].rsplit(" — ", 1)
        rep["reason"] = (head + f"; secondary: SPY-minus-TLT 2-day spread in signal months {_bps(prim.get('spread_signal_mean'))} bps "
                         f"(p {_p(prim.get('spread_signal_p_less'))}); declared 10-trial grid Holm p for the primary "
                         f"{_p(g.get('p_holm'))} (reported, the pass names the unadjusted p) — " + tail)
    rep["label"] = "SPY/TLT adjclose (total return); month-end calendar (rule 10a); signal at the T-3 close"
    return _clean(rep), int(rep["n"]), rep["verdict"], rep["reason"]


# ====================================================================================== T-450 pension flow =====

def ols_nw(y, x, lags: int) -> dict:
    """OLS of y on [1, x] with the Newey-West (Bartlett, ``lags``) HAC standard error of the slope."""
    y = np.asarray(y, float); x = np.asarray(x, float); n = y.size
    X = np.column_stack([np.ones(n), x])
    xtx = np.linalg.inv(X.T @ X)
    beta = xtx @ X.T @ y
    e = y - X @ beta
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, lags + 1):
        if l >= n:
            break
        G = u[l:].T @ u[:-l]
        S += (1 - l / (lags + 1)) * (G + G.T)
    V = xtx @ S @ xtx
    se = math.sqrt(V[1, 1]) if V[1, 1] > 0 else float("nan")
    return {"slope": float(beta[1]), "intercept": float(beta[0]), "se": se, "t": float(beta[1] / se) if se > 0 else float("nan"),
            "n": int(n), "lags": int(lags)}


def nw_lags(n: int) -> int:
    return int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def flow_windows(days, spy, bond, bills: Optional[Bills], lag: int = 0, first: str = T450_START, last: str = T450_END,
                 base: str = "month", excess=None) -> list:
    """T-450 windows: decision at the close 3 sessions before the month's last session (the 4th-to-last), the signal at
    ``lag`` sessions before it, X = month-to-date (``base`` "quarter": quarter-to-date) SPY minus bond total return, and y
    = SPY's return from the decision close to the first close of the next month minus the bill return (``bills``) or
    minus the ``excess`` deflator index's return (a cumulative risk-free index on the same days)."""
    tab = month_end_table(days, spy, bond, decision=4, lag=lag, exit_next=True, first=first, last=last, base=base)
    if excess is not None:
        pos = {d: i for i, d in enumerate(days)}
        for r in tab:
            r["y"] = r["ra"] - (excess[pos[r["exit_day"]]] / excess[pos[r["decision_day"]]] - 1)
    else:
        for r in tab:
            r["y"] = r["ra"] - bills.growth(r["decision_day"], r["exit_day"])
    return tab


def _slope_rep(tab, split: str) -> dict:
    if len(tab) < 8:
        return {"n": len(tab), "slope": None, "t": None}
    x = np.array([r["S"] for r in tab]); y = np.array([r["y"] for r in tab]); mo = np.array([r["month"] for r in tab])
    L = nw_lags(len(tab))
    full = ols_nw(y, x, L)
    rep = {**full, "first_month": str(mo[0]), "last_month": str(mo[-1]), "t_lag0": ols_nw(y, x, 0)["t"], "t_lag12": ols_nw(y, x, 12)["t"]}
    for lab, m in (("first_half", mo < split), ("second_half", mo >= split)):
        if m.sum() >= 8:
            h = ols_nw(y[m], x[m], nw_lags(int(m.sum())))
            rep[lab] = {"n": int(m.sum()), "slope": h["slope"], "t": h["t"]}
        else:
            rep[lab] = {"n": int(m.sum()), "slope": None, "t": None}
    keep = np.array([m_[:4] not in ("2008", "2020", "2022") for m_ in mo])
    if keep.sum() >= 8:
        e = ols_nw(y[keep], x[keep], nw_lags(int(keep.sum())))
        rep["excluding_2008_2020_2022"] = {"n": int(keep.sum()), "slope": e["slope"], "t": e["t"]}
    return rep


def pension_flow(spy, agg, bills: Bills, first: str = T450_START, last: str = T450_END, split: str = T450_SPLIT,
                 t_bound: float = T450_T, min_n: int = T450_MIN_N, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-450 primary: slope of the 4-session SPY excess return on the month-to-date SPY-minus-AGG differential (HAC t
    <= -2 over >= 250 windows), negative in each half; each criterion under both rule-12 readings. The threshold rule
    (short SPY when X > 2%, long when X < -2%, net of 2 bps per active month) is reported with a 3-month block CI."""
    days, (a, b) = _align(spy, agg)
    readings = {}
    for lab, lag in (("entry close", 0), ("previous close", 1)):
        tab = flow_windows(days, a, b, bills, lag=lag, first=first, last=last)
        readings[lab] = _slope_rep(tab, split)
        if lab == "entry close":
            prim_tab = tab
    prim = readings["entry close"]
    n = int(prim["n"])
    out = {"readings": readings}
    if any(r.get("slope") is None for r in readings.values()):
        v, why = _verdict([("enough complete monthly windows with SPY, AGG and bills", None)])
        out.update(n=n, verdict=v, reason=f"too few monthly windows ({n}) — {why}")
        return out
    x = np.array([r["S"] for r in prim_tab]); y = np.array([r["y"] for r in prim_tab])
    pos = np.where(x > T450_THR, -1.0, np.where(x < -T450_THR, 1.0, 0.0))
    pnl = pos * y - np.abs(pos) * T450_RULE_COST
    out["threshold_rule"] = {"n_short": int((pos < 0).sum()), "n_long": int((pos > 0).sum()),
                             "mean_per_month": float(pnl.mean()), "ci_per_month": mean_ci(pnl, 3, n_boot, seed),
                             "mean_per_active_month": float(pnl[pos != 0].mean()) if (pos != 0).any() else None,
                             "ci_per_active_month": mean_ci(pnl[pos != 0], 3, n_boot, seed) if (pos != 0).sum() >= 2 else [None, None]}
    R = list(readings.values())
    c_t = _agree([r["t"] <= t_bound for r in R])
    c_h1 = _agree([None if r["first_half"]["slope"] is None else r["first_half"]["slope"] < 0 for r in R])
    c_h2 = _agree([None if r["second_half"]["slope"] is None else r["second_half"]["slope"] < 0 for r in R])
    dec = [all(r["t"] >= -t_bound for r in R),
           all(r["first_half"]["t"] is not None and r["first_half"]["t"] > 1.959964 for r in R),
           all(r["second_half"]["t"] is not None and r["second_half"]["t"] > 1.959964 for r in R)]
    y1 = int(split[:4]) - 1
    names = [f"slope HAC t <= {t_bound:g} (Newey-West, lag {prim['lags']}) under both rule-12 readings",
             f"slope < 0 in {first[:4]}-{y1} (both readings)", f"slope < 0 in {split[:4]}-{last[:4]} (both readings)"]
    v, why, crit = _judge(_undecided(list(zip(names, [c_t, c_h1, c_h2], dec)), "undecided: the rule-12 readings disagree"), n, min_n, "monthly windows")
    out.update(n=n, criteria=[[c, ok] for c, ok in crit], verdict=v)

    def one(lab, r):
        h1, h2 = r["first_half"], r["second_half"]
        return (f"{lab}: {r['n']} windows {r['first_month']}..{r['last_month']}, slope {_fx(r['slope'], '+.4f')} (HAC t "
                f"{_fx(r['t'], '+.2f')}; lag 0 {_fx(r['t_lag0'], '+.2f')}, lag 12 {_fx(r['t_lag12'], '+.2f')}), halves "
                f"{_fx(h1['slope'], '+.4f')} (t {_fx(h1['t'], '+.2f')}, n {h1['n']}) / {_fx(h2['slope'], '+.4f')} "
                f"(t {_fx(h2['t'], '+.2f')}, n {h2['n']})")
    tr = out["threshold_rule"]
    out["reason"] = ("; ".join(one(k, r) for k, r in readings.items())
                     + f"; threshold rule (reported) {_bps(tr['mean_per_month'])} bps/month (95% CI {_ci_bps(tr['ci_per_month'])}) "
                     f"over {tr['n_short']} short / {tr['n_long']} long months — {why}")
    return out


def _ff_indices(archive) -> Optional[tuple]:
    """Long-history inputs from French daily factors: (days, market total-return index, risk-free index)."""
    mkt, rf = _series(archive, FF3_B, "Mkt-RF"), _series(archive, FF3_B, "RF")
    days = sorted(set(mkt) & set(rf))
    if len(days) < 300:
        return None
    rm = np.array([(mkt[d] + rf[d]) / 100 for d in days]); rr = np.array([rf[d] / 100 for d in days])
    return days, np.cumprod(1 + rm), np.cumprod(1 + rr)


def bond_proxy_index(days: Sequence[str], dgs10: dict) -> np.ndarray:
    """10-year par-bond total-return proxy from FRED DGS10 on ``days``: day t earns y(t-1)/252 carry minus modified
    duration D(y(t-1)) = (1 - (1 + y/2)^-20) / y times the yield change; a day without a print carries the last yield."""
    ks = sorted(dgs10)
    vals = [dgs10[k] / 100 for k in ks]
    ys = []
    for d in days:
        j = bisect.bisect_right(ks, d) - 1
        ys.append(vals[j] if j >= 0 else (vals[0] if vals else float("nan")))
    ys = np.array(ys)
    r = np.zeros(len(days))
    for t in range(1, len(days)):
        y0 = ys[t - 1]
        dur = (1 - (1 + y0 / 2) ** -20) / y0 if y0 > 0 else 10.0
        r[t] = y0 / 252 - dur * (ys[t] - y0)
    return np.cumprod(1 + r)


def b6c_cal_pension_rebalancing(archive):
    """T-450: 4-session SPY excess return vs the month-to-date SPY-minus-AGG differential."""
    miss = _missing(archive, [SPY_B, AGG_B, DTB3_B])
    if miss:
        return miss
    spy, agg = _daily(archive, SPY_B), _daily(archive, AGG_B)
    bills = Bills(_series(archive, DTB3_B))
    rep = pension_flow(spy, agg, bills, n_boot=N_BOOT)
    if rep.get("criteria") is not None:
        days, (a, b) = _align(spy, agg)
        sens = {}
        qe = [r for r in flow_windows(days, a, b, bills) if r["month"][5:7] in ("03", "06", "09", "12")]
        qq = [r for r in flow_windows(days, a, b, bills, base="quarter") if r["month"][5:7] in ("03", "06", "09", "12")]
        for lab, tab in (("quarter-end, month-to-date", qe), ("quarter-end, quarter-to-date", qq)):
            s = _slope_rep(tab, T450_SPLIT)
            sens[lab] = {"n": s["n"], "slope": s.get("slope"), "t": s.get("t")}
        if _has(archive, TLT_B):
            dt, (at, bt) = _align(spy, _daily(archive, TLT_B))
            s = _slope_rep(flow_windows(dt, at, bt, bills), T450_SPLIT)
            sens["SPY minus TLT differential"] = {"n": s["n"], "slope": s.get("slope"), "t": s.get("t")}
        if _has(archive, FF3_B) and _has(archive, DGS10_B):
            ff = _ff_indices(archive)
            if ff is not None:
                fd, mi, ri = ff
                bi = bond_proxy_index(fd, _series(archive, DGS10_B))
                tab = flow_windows(fd, mi, bi, None, first="1962-02", last="2026-12", excess=ri)
                s = _slope_rep(tab, "1994-01")
                sens["long history (French market, DGS10 duration proxy)"] = {
                    "n": s["n"], "slope": s.get("slope"), "t": s.get("t"), "first_month": s.get("first_month"), "last_month": s.get("last_month")}
        rep["sensitivities"] = sens
        head, tail = rep["reason"].rsplit(" — ", 1)
        rep["reason"] = head + "; reported: " + ", ".join(
            f"{k} slope {_fx(v['slope'], '+.4f')} (t {_fx(v['t'], '+.2f')}, n {v['n']})" for k, v in sens.items() if v.get("slope") is not None) + " — " + tail
    rep["label"] = "SPY/AGG adjclose (total return), excess over DTB3 known at the decision; month-end calendar (rule 10a)"
    return _clean(rep), int(rep["n"]), rep["verdict"], rep["reason"]


# ============================================================================ T-347 Friday-minus-Monday spread ==

def _weekdays(days) -> np.ndarray:
    return np.array([date.fromisoformat(d).weekday() for d in days])


def _iso_week_ids(days) -> np.ndarray:
    keys = [date.fromisoformat(d).isocalendar()[:2] for d in days]
    uniq = {k: i for i, k in enumerate(sorted(set(keys)))}
    return np.array([uniq[k] for k in keys])


def spread_returns(spec, safe) -> tuple:
    """(days, daily spec-minus-safe return) on the pair's common sessions, each return ending on its day."""
    days, (a, b) = _align(spec, safe)
    return days[1:], (a[1:] / a[:-1] - 1) - (b[1:] / b[:-1] - 1)


def weekday_contrast(days, x, wa: int = 4, wb: int = 0, block: int = T347_BLOCK, n_boot: Optional[int] = None,
                     seed: int = SEED, permute: bool = True, n_perm: Optional[int] = None, n_seeds: int = 1,
                     pvals: bool = True) -> dict:
    """Mean of x on weekday ``wa`` minus weekday ``wb``: point, percentile CI and (``pvals``) studentized p's of the
    contrast series (block ``block``, mean over ``n_seeds`` seeds) and, with ``permute``, the within-ISO-week
    weekday-label permutation p's."""
    x = np.asarray(x, float); wd = _weekdays(days)
    fa, fb = wd == wa, wd == wb
    out = {"n_a": int(fa.sum()), "n_b": int(fb.sum()), "diff": None, "boot_draws": _nb(n_boot) * n_seeds, "perm_draws": _np(n_perm)}
    if fa.sum() < 2 or fb.sum() < 2:
        return out
    d = contrast_series(x, fa, fb)
    pg, pl = studentized_p(d, block, n_boot, seed, n_seeds) if pvals else (None, None)
    out.update(diff=float(x[fa].mean() - x[fb].mean()), mean_a=float(x[fa].mean()), mean_b=float(x[fb].mean()),
               ci=mean_ci(d, block, n_boot, seed), boot_p_greater=pg, boot_p_less=pl)
    if permute:
        draws = []
        Fa, Fb = fa.sum(), fb.sum()
        for L in permuted_labels(wd.astype(np.int8), _iso_week_ids(days), n_perm, seed):
            draws.append((L == wa).astype(float) @ x / Fa - (L == wb).astype(float) @ x / Fb)
        out["perm_p_greater"], out["perm_p_less"] = _perm_p(out["diff"], np.concatenate(draws))
    return out


def speculative_spread(spec, safe, bound: float = T347_BOUND, split: str = T347_SPLIT, min_n: int = T347_MIN_N,
                       n_perm: Optional[int] = None, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-347 primary: Friday-minus-Monday mean of the spec-minus-safe daily spread > bound, p < 0.05 under both named
    nulls (rule 11), positive in both halves; n = the smaller of the Friday and Monday counts."""
    days, s = spread_returns(spec, safe)
    if len(days) < 40:
        v, why = _verdict([("enough common sessions to build the spread", None)])
        return {"n": 0, "verdict": v, "reason": f"only {len(days)} common sessions — {why}"}
    full = weekday_contrast(days, s, n_boot=n_boot, seed=seed, n_perm=n_perm, n_seeds=N_SEEDS)
    ds = np.array(days)
    halves = {}
    for lab, m in (("first", ds < split), ("second", ds >= split)):
        h = weekday_contrast(list(ds[m]), s[m], n_boot=n_boot, seed=seed, permute=False, pvals=False) if m.sum() >= 40 else {"diff": None, "n_a": 0, "n_b": 0, "ci": [None, None]}
        halves[lab] = {"diff": h["diff"], "ci": h.get("ci", [None, None]), "n_fri": h["n_a"], "n_mon": h["n_b"]}
    n = int(min(full["n_a"], full["n_b"]))
    rep = {"n": n, "n_fridays": full["n_a"], "n_mondays": full["n_b"], "first_day": days[0], "last_day": days[-1],
           "contrast": full, "halves": halves,
           "net_of_cost_per_week": {f"{c * 1e4:.0f}bps": (None if full["diff"] is None else full["diff"] - c) for c in T347_COSTS}}
    if full["diff"] is None:
        v, why = _verdict([("Fridays and Mondays in the sample", None)])
        rep.update(verdict=v, reason=f"no Friday/Monday contrast computable — {why}")
        return rep
    c_mag = full["diff"] > bound
    c_sig = _agree([decide_p(full["boot_p_greater"], full["boot_draws"]), decide_p(full["perm_p_greater"], full["perm_draws"])])
    c_h1 = None if halves["first"]["diff"] is None else halves["first"]["diff"] > 0
    c_h2 = None if halves["second"]["diff"] is None else halves["second"]["diff"] > 0
    dec = [full["ci"][1] is not None and full["ci"][1] <= bound,
           decide_p(full["boot_p_less"], full["boot_draws"]) is True and decide_p(full["perm_p_less"], full["perm_draws"]) is True,
           halves["first"]["ci"][1] is not None and halves["first"]["ci"][1] <= 0,
           halves["second"]["ci"][1] is not None and halves["second"]["ci"][1] <= 0]
    y1 = int(split[:4]) - 1
    names = [f"Friday-minus-Monday contrast > {bound * 1e4:.0f} bps",
             "p < 0.05 under the 10-day studentized block bootstrap and the within-week weekday permutation (rule 11)",
             f"contrast > 0 in {days[0][:4]}-{y1}", f"contrast > 0 in {split[:4]}-{days[-1][:4]}"]
    v, why, crit = _judge(_undecided(list(zip(names, [c_mag, c_sig, c_h1, c_h2], dec))), n, min_n, "Fridays/Mondays (the smaller count)")
    rep.update(criteria=[[c, ok] for c, ok in crit], verdict=v)
    h1, h2 = halves["first"], halves["second"]
    rep["reason"] = (f"spread Fridays {_bps(full['mean_a'])} vs Mondays {_bps(full['mean_b'])} bps over {full['n_a']} Fridays / "
                     f"{full['n_b']} Mondays {days[0]}..{days[-1]}: contrast {_bps(full['diff'])} bps (95% CI {_ci_bps(full['ci'])}), "
                     f"block-bootstrap p {_mc(full['boot_p_greater'], full['boot_draws'])}, within-week permutation p "
                     f"{_mc(full['perm_p_greater'], full['perm_draws'])}; halves "
                     f"{_bps(h1['diff'])} ({h1['n_fri']}/{h1['n_mon']}) / {_bps(h2['diff'])} ({h2['n_fri']}/{h2['n_mon']}) bps; "
                     f"net of 4/8 bps a week (reported) {_bps(rep['net_of_cost_per_week']['4bps'])}/{_bps(rep['net_of_cost_per_week']['8bps'])} bps — {why}")
    return rep


def b6c_cal_weekday_speculative_spread(archive):
    """T-347: SPHB-minus-SPLV spread, Fridays minus Mondays."""
    miss = _missing(archive, [SPHB_B, SPLV_B])
    if miss:
        return miss
    sphb, splv = _daily(archive, SPHB_B), _daily(archive, SPLV_B)
    rep = speculative_spread(sphb, splv, n_perm=N_PERM, n_boot=N_BOOT)
    if rep.get("criteria") is not None:
        start = rep["first_day"]
        sec = {}

        def contrast_pair(spec_b, safe_b, label):
            if not (_has(archive, spec_b) and _has(archive, safe_b)):
                miss_ = [x for x in (spec_b, safe_b) if not _has(archive, x)]
                sec[label] = {"diff": None, "p": None, "note": f"not archived: {', '.join(miss_)}"}
                return
            d, x = spread_returns(_daily(archive, spec_b), _daily(archive, safe_b))
            keep = [i for i, dd in enumerate(d) if dd >= start]
            w = weekday_contrast([d[i] for i in keep], x[keep], n_boot=N_BOOT, permute=False)
            sec[label] = {"diff": w["diff"], "p": w.get("boot_p_greater"), "n_fri": w["n_a"], "n_mon": w["n_b"], "first_day": d[keep[0]] if keep else None}

        contrast_pair(SPHB_B, USMV_B, "SPHB-USMV (USMV as the safe leg)")
        contrast_pair(IWO_B, IWN_B, "IWO-IWN (small growth minus small value)")
        contrast_pair(ARKK_B, SPLV_B, "ARKK-SPLV (ARKK chosen with hindsight, flagged)")
        metals = {}
        for b_ in (GLD_B, SLV_B):
            if _has(archive, b_):
                d, c = _daily(archive, b_)
                r = c[1:] / c[:-1] - 1; dd = d[1:]
                keep = np.array([x >= start for x in dd])
                g = group_test(r[keep], _weekdays(np.array(dd)[keep]) == 0, T347_BLOCK, N_BOOT)
                metals[b_.split("-")[-1]] = {"diff": g["diff"], "p_two_sided": _two_sided(g["p_greater"], g["p_less"])}
        if len(metals) == 2:
            sec["GLD/SLV Monday vs rest (two-sided, Bonferroni over the two)"] = {
                "per_metal": metals, "p": min(1.0, 2 * min(v["p_two_sided"] for v in metals.values())) if all(v["p_two_sided"] is not None for v in metals.values()) else None}
        else:
            sec["GLD/SLV Monday vs rest (two-sided, Bonferroni over the two)"] = {"p": None, "note": "GLD or SLV not archived"}
        if _has(archive, VIX_B):
            vx = _series(archive, VIX_B)
            vd = sorted(k for k in vx if k >= start and vx[k] > 0)
            lv = np.log(np.array([vx[k] for k in vd]))
            w = weekday_contrast(vd[1:], np.diff(lv), n_boot=N_BOOT, permute=False)
            sec["VIX log change, Friday minus Monday (two-sided)"] = {"diff": w["diff"], "p": _two_sided(w.get("boot_p_greater"), w.get("boot_p_less")),
                                                                     "n_fri": w["n_a"], "n_mon": w["n_b"]}
        else:
            sec["VIX log change, Friday minus Monday (two-sided)"] = {"p": None, "note": "cboe-VIX-history not archived"}
        holm = _holm({k: v.get("p") for k, v in sec.items()}, m=5)
        for k in sec:
            sec[k]["p_holm"] = holm.get(k)
        rep["secondary_holm"] = sec
        head, tail = rep["reason"].rsplit(" — ", 1)
        rep["reason"] = head + "; secondaries (Holm over 5, not criteria): " + ", ".join(
            f"{k.split(' (')[0]} " + (f"Holm p {_p(v['p_holm'])}" if v.get("p") is not None else f"None ({v.get('note', 'n/a')})")
            for k, v in sec.items()) + " — " + tail
    rep["label"] = "SPHB/SPLV adjclose (total return); weekday of the return's end session"
    return _clean(rep), int(rep["n"]), rep["verdict"], rep["reason"]


# ============================================================================================ T-349 pre-holiday ==

def day_returns(days, closes, start: str = "0000-00-00", end: str = "9999-99-99") -> tuple:
    c = np.asarray(closes, float)
    r = c[1:] / c[:-1] - 1
    ds = list(days[1:])
    keep = [i for i, d in enumerate(ds) if start <= d <= end]
    return [ds[i] for i in keep], r[keep]


def pre_holiday_effect(days, closes, start: str = T349_START, split: str = T349_SPLIT, bound: float = T349_BOUND,
                       min_n: int = T349_MIN_N, block: int = T349_BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-349 primary: return on rule-calendar pre-holiday sessions minus the mean on all other sessions > bound,
    studentized block-bootstrap p < 0.05, positive in both halves."""
    ds, r = day_returns(days, closes, start)
    if len(ds) < 40:
        v, why = _verdict([("enough sessions in the sample", None)])
        return {"n": 0, "verdict": v, "reason": f"only {len(ds)} sessions — {why}"}
    pre = pre_holiday_sessions(ds[0], ds[-1])
    have = set(ds)
    f = np.array([d in pre for d in ds])
    rep = {"n": int(f.sum()), "first_day": ds[0], "last_day": ds[-1], "n_sessions": len(ds),
           "pre_holiday_sessions_without_a_bar": sorted(d for d in pre if d not in have),
           "by_holiday": {}}
    g = group_test(r, f, block, n_boot, seed, N_SEEDS)
    rep["test"] = g
    names_by = {}
    for d, h in pre.items():
        names_by.setdefault(h, []).append(d)
    for h, dl in sorted(names_by.items()):
        dset = set(dl)
        m = np.array([d in dset for d in ds])
        rep["by_holiday"][h] = {"n": int(m.sum()), "mean": float(r[m].mean()) if m.any() else None}
    dsa = np.array(ds)
    halves = {}
    for lab, m in (("first", dsa < split), ("second", dsa >= split)):
        gh = group_test(r[m], f[m], block, n_boot, seed, pvals=False) if m.sum() >= 40 else {"diff": None, "ci": [None, None], "n_event": int(f[m].sum())}
        halves[lab] = {"diff": gh["diff"], "ci": gh["ci"], "n_pre": gh["n_event"]}
    rep["halves"] = halves
    rep["net_of_cost_diff"] = None if g["diff"] is None else g["diff"] - T349_COST
    if g["diff"] is None:
        v, why = _verdict([("pre-holiday sessions in the sample", None)])
        rep.update(verdict=v, reason=f"no pre-holiday sessions with returns — {why}")
        return rep
    c = [g["diff"] > bound, decide_p(g["p_greater"], g["draws"]),
         None if halves["first"]["diff"] is None else halves["first"]["diff"] > 0,
         None if halves["second"]["diff"] is None else halves["second"]["diff"] > 0]
    dec = [g["ci"][1] <= bound, decide_p(g["p_less"], g["draws"]) is True,
           halves["first"]["ci"][1] is not None and halves["first"]["ci"][1] <= 0,
           halves["second"]["ci"][1] is not None and halves["second"]["ci"][1] <= 0]
    y1 = int(split[:4]) - 1
    names = [f"pre-holiday minus other sessions > {bound * 1e4:.0f} bps",
             "studentized block-bootstrap (block 10) p < 0.05",
             f"difference > 0 in {ds[0][:4]}-{y1}", f"difference > 0 in {split[:4]}-{ds[-1][:4]}"]
    v, why, crit = _judge(_undecided(list(zip(names, c, dec)), "undecided: its Monte-Carlo band straddles 0.05, so the computed p "
                                                                "does not decide the criterion"), rep["n"], min_n, "pre-holiday sessions")
    rep.update(criteria=[[a, ok] for a, ok in crit], verdict=v)
    h1, h2 = halves["first"], halves["second"]
    rep["reason"] = (f"{rep['n']} pre-holiday sessions (rule calendar) {ds[0]}..{ds[-1]}: {_bps(g['mean_event'])} vs "
                     f"{_bps(g['mean_other'])} bps on {g['n_other']} other sessions, difference {_bps(g['diff'])} bps "
                     f"(95% CI {_ci_bps(g['ci'])}, p {_mc(g['p_greater'], g['draws'])}, {N_SEEDS} seeds x {_nb(n_boot)}); halves {_bps(h1['diff'])} ({h1['n_pre']}) / "
                     f"{_bps(h2['diff'])} ({h2['n_pre']}) bps; net of 2 bps (reported) {_bps(rep['net_of_cost_diff'])} bps — {why}")
    return rep


def holiday_week_flags(ds: Sequence[str]) -> np.ndarray:
    """Thanksgiving week (Monday through the Friday after Thanksgiving) and the Christmas-New Year stretch (the last
    session before Christmas through 31 December), from the rule calendar."""
    out = np.zeros(len(ds), bool)
    if not ds:
        return out
    years = range(int(ds[0][:4]), int(ds[-1][:4]) + 1)
    spans = []
    for y in years:
        tg = _nth_weekday(y, 11, 3, 4)
        spans.append((tg - timedelta(days=3), tg + timedelta(days=1)))
        spans.append((prev_session(_observed(date(y, 12, 25))), date(y, 12, 31)))
    for i, d in enumerate(ds):
        x = date.fromisoformat(d)
        out[i] = any(a <= x <= b for a, b in spans)
    return out


def pre_holiday_secondaries(iwm, rut=None, spy=None, btc=None, start: str = T349_START, n_boot: Optional[int] = None,
                            seed: int = SEED) -> dict:
    """T-349's six declared Holm secondaries (reported, not criteria)."""
    sec = {}
    if rut is not None:
        ds, r = day_returns(rut[0], rut[1], "1987-01-01")
        pre = pre_holiday_sessions(ds[0], ds[-1])
        g = group_test(r, np.array([d in pre for d in ds]), T349_BLOCK, n_boot, seed)
        sec["^RUT 1987-2026 pre-holiday"] = {"diff": g["diff"], "p": g["p_greater"], "n_pre": g["n_event"], "first_day": ds[0],
                                             "calendar_check": _check_summary(calendar_check(list(rut[0])))}
    else:
        sec["^RUT 1987-2026 pre-holiday"] = {"p": None, "note": "daily-history--RUT not archived"}
    if spy is not None:
        ds, r = day_returns(spy[0], spy[1], start)
        pre = pre_holiday_sessions(ds[0], ds[-1])
        g = group_test(r, np.array([d in pre for d in ds]), T349_BLOCK, n_boot, seed)
        sec["SPY pre-holiday (expected-null control)"] = {"diff": g["diff"], "p": g["p_greater"], "n_pre": g["n_event"]}
    else:
        sec["SPY pre-holiday (expected-null control)"] = {"p": None, "note": "daily-history-SPY not archived"}
    ds, r = day_returns(iwm[0], iwm[1], start)
    post = post_holiday_sessions(ds[0], ds[-1])
    g = group_test(r, np.array([d in post for d in ds]), T349_BLOCK, n_boot, seed)
    sec["IWM post-holiday session (two-sided)"] = {"diff": g["diff"], "p": _two_sided(g["p_greater"], g["p_less"]), "n_post": g["n_event"]}
    fw = holiday_week_flags(ds)
    g = group_test(r, fw, T349_BLOCK, n_boot, seed)
    sec["IWM Thanksgiving week and Christmas-New Year stretch"] = {"diff_per_session": g["diff"], "p": g["p_greater"], "n_sessions": g["n_event"],
                                                                  "mean_summed_return_per_year": float(np.sum(r[fw]) / max(1, len({d[:4] for d, x in zip(ds, fw) if x}))) if fw.any() else None}
    sec["Cultural New Year month in FXI/EWY/INDA"] = {"p": None, "note": "not archived: daily-history-FXI, daily-history-EWY, daily-history-INDA; no declared Lunar New Year/Diwali date table"}
    if btc is not None:
        bd, br = day_returns(btc[0], btc[1])
        wk = np.array([date.fromisoformat(d).weekday() < 5 for d in bd])
        hol = np.array([nyse_closure(d) not in (None, "weekend") and d not in UNSCHEDULED_CLOSURES for d in bd])
        normal = wk & ~hol & np.array([is_nyse_session(d) for d in bd])
        keep = hol | normal
        gr = group_test(br[keep], hol[keep], T349_BLOCK, n_boot, seed)
        gv = group_test(np.abs(br[keep]), hol[keep], T349_BLOCK, n_boot, seed)
        pr, pv = _two_sided(gr["p_greater"], gr["p_less"]), _two_sided(gv["p_greater"], gv["p_less"])
        sec["BTC on NYSE holidays vs NYSE sessions (two-sided return and |return|, Bonferroni over the two)"] = {
            "return_diff": gr["diff"], "abs_return_diff": gv["diff"], "n_holidays": gr["n_event"],
            "p": None if pr is None or pv is None else min(1.0, 2 * min(pr, pv))}
    else:
        sec["BTC on NYSE holidays vs NYSE sessions (two-sided return and |return|, Bonferroni over the two)"] = {"p": None, "note": "daily-history-BTC-USD not archived"}
    holm = _holm({k: v.get("p") for k, v in sec.items()}, m=6)
    for k in sec:
        sec[k]["p_holm"] = holm.get(k)
    return sec


def _check_summary(ch: dict) -> dict:
    return {"unexplained_gaps": len(ch["unexplained_gaps"]), "bars_on_closed_days": len(ch["bars_on_closed_days"]),
            "scheduled_holiday_gaps": ch["scheduled_holiday_gaps"], "unscheduled_closure_gaps": ch["unscheduled_closure_gaps"],
            "examples": (ch["unexplained_gaps"][:5] + ch["bars_on_closed_days"][:5])}


def b6c_cal_pre_holiday(archive):
    """T-349: IWM on the last session before scheduled NYSE holidays."""
    miss = _missing(archive, [IWM_B])
    if miss:
        return miss
    iwm = _daily(archive, IWM_B)
    rep = pre_holiday_effect(iwm[0], iwm[1], n_boot=N_BOOT)
    rep["calendar_check"] = _check_summary(calendar_check(list(iwm[0])))
    if rep.get("criteria") is not None:
        rut = _daily(archive, RUT_B, "close") if _has(archive, RUT_B) else None
        spy = _daily(archive, SPY_B) if _has(archive, SPY_B) else None
        btc = _daily(archive, BTC_B) if _has(archive, BTC_B) else None
        sec = pre_holiday_secondaries(iwm, rut, spy, btc, n_boot=N_BOOT)
        rep["secondary_holm"] = sec
        cc = rep["calendar_check"]
        head, tail = rep["reason"].rsplit(" — ", 1)
        rep["reason"] = (head + f"; rule calendar vs IWM bars: {cc['unexplained_gaps']} unexplained gaps, {cc['bars_on_closed_days']} "
                         f"bars on closed days, {cc['scheduled_holiday_gaps']} holiday and {cc['unscheduled_closure_gaps']} unscheduled-closure gaps"
                         "; secondaries (Holm over 6, not criteria): " + ", ".join(
                             f"{k.split(' (')[0]} " + (f"{_bps(v.get('diff', v.get('diff_per_session', v.get('return_diff'))))} bps, Holm p {_p(v['p_holm'])}"
                                                      if v.get("p") is not None else f"None ({v.get('note', 'n/a')})")
                             for k, v in sec.items()) + " — " + tail)
    rep["label"] = "IWM adjclose (total return); rule-based NYSE holiday calendar"
    return _clean(rep), int(rep["n"]), rep["verdict"], rep["reason"]


# ==================================================================================== T-357 presidential cycle ==

def annual_returns(days, closes, first: int = T357_FIRST) -> tuple:
    """(years, calendar-year price returns) from the last close of y-1 to the last close of y, for complete years
    (a later year is in the data) from ``first``."""
    last = {}
    for d, c in zip(days, closes):
        last[int(d[:4])] = float(c)
    ys = sorted(last)
    yrs, ret = [], []
    for y in ys:
        if y < first or (y - 1) not in last or (y + 1) not in last:
            continue
        yrs.append(y); ret.append(last[y] / last[y - 1] - 1)
    return np.array(yrs, int), np.array(ret, float)


def cycle_year(y) -> np.ndarray:
    """Year of the presidential term: 1 post-election, 2 midterm, 3 pre-election, 4 election year (1928 -> 4)."""
    return (np.asarray(y, int) - (FIRST_ELECTION + 1)) % 4 + 1


def presidential_year3(years, rets, bound: float = T357_BOUND, split: int = T357_SPLIT, late: int = T357_LATE,
                       min_n: int = T357_MIN_N, n_perm: Optional[int] = None, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-357 pre-registered test: mean year-3 return minus the mean of the other years > bound, one-sided permutation p
    < 0.05 with the cycle label permuted within 4-year blocks (term-aligned and 1928-anchored blocks must agree), the
    excess positive in [first, split) and [split, last]; 1990- reported. Rule-5 intervals: a bootstrap of whole terms."""
    yrs = np.asarray(years, int); r = np.asarray(rets, float)
    lab = cycle_year(yrs)
    f = lab == 3
    n = int(f.sum())
    rep = {"n": n, "n_years": int(yrs.size), "first_year": int(yrs[0]) if yrs.size else None, "last_year": int(yrs[-1]) if yrs.size else None}
    if f.sum() < 2 or (~f).sum() < 2:
        v, why = _verdict([("year-3 and other years in the sample", None)])
        rep.update(verdict=v, reason=f"only {n} year-3 years — {why}")
        return rep
    obs = float(r[f].mean() - r[~f].mean())
    perms = {}
    for blab, groups in (("term blocks (years 1-4)", (yrs - (FIRST_ELECTION + 1)) // 4),
                         ("1928-anchored blocks", (yrs - FIRST_ELECTION) // 4)):
        draws = []
        k = f.sum(); tot = r.sum()
        for L in permuted_labels(lab.astype(np.int8), groups, n_perm, seed):
            m3 = (L == 3)
            s = m3.astype(float) @ r; c3 = m3.sum(axis=1)
            draws.append(s / c3 - (tot - s) / (yrs.size - c3))
        pg, pl = _perm_p(obs, np.concatenate(draws))
        perms[blab] = {"p_greater": pg, "p_less": pl}
    # whole-term bootstrap for the rule-5 intervals and reporting
    terms = (yrs - (FIRST_ELECTION + 1)) // 4
    blocks = [np.where(terms == t)[0] for t in np.unique(terms)]
    rng = np.random.default_rng(seed)

    def term_ci(mask):
        bl = [b_[mask[b_]] for b_ in blocks if mask[b_].any()]
        if len(bl) < 2:
            return [None, None]
        vals = []
        for _ in range(_nb(n_boot)):
            idx = np.concatenate([bl[i] for i in rng.integers(0, len(bl), len(bl))])
            ff = f[idx]
            if ff.any() and (~ff).any():
                vals.append(r[idx][ff].mean() - r[idx][~ff].mean())
        return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))] if vals else [None, None]

    ci = term_ci(np.ones(yrs.size, bool))
    halves = {}
    for hl, m in (("first", yrs < split), ("second", yrs >= split)):
        d = _point_diff(r[m], f[m])
        halves[hl] = {"excess": d, "n_year3": int(f[m].sum()), "years": [int(yrs[m][0]), int(yrs[m][-1])] if m.any() else None,
                      "ci": term_ci(m) if d is not None else [None, None]}
    ml = yrs >= late
    rep.update(excess=obs, mean_year3=float(r[f].mean()), mean_other=float(r[~f].mean()), ci=ci, permutation=perms, halves=halves,
               by_cycle_year={int(k): float(r[lab == k].mean()) for k in (1, 2, 3, 4) if (lab == k).any()},
               late_period={"from": late, "excess": _point_diff(r[ml], f[ml]), "n_year3": int(f[ml].sum())},
               flags=["price return only (dividends excluded)", "before 1957 the series is the S&P 90 composite",
                      "the partial current year is excluded"])
    P = list(perms.values())
    nd = _np(n_perm)
    c = [obs > bound, _agree([decide_p(p["p_greater"], nd) for p in P]),
         None if halves["first"]["excess"] is None else halves["first"]["excess"] > 0,
         None if halves["second"]["excess"] is None else halves["second"]["excess"] > 0]
    dec = [ci[1] is not None and ci[1] <= bound, all(decide_p(p["p_less"], nd) is True for p in P),
           halves["first"]["ci"][1] is not None and halves["first"]["ci"][1] <= 0,
           halves["second"]["ci"][1] is not None and halves["second"]["ci"][1] <= 0]
    h1, h2 = halves["first"], halves["second"]
    names = [f"year-3 excess > {bound * 100:.0f} pp",
             "within-4-year-block permutation p < 0.05 (term-aligned and 1928-anchored blocks agree; Monte-Carlo band clears 0.05)",
             f"excess > 0 in {h1['years'][0] if h1['years'] else '?'}-{split - 1}", f"excess > 0 in {split}-{h2['years'][1] if h2['years'] else '?'}"]
    v, why, crit = _judge(_undecided(list(zip(names, c, dec))), n, min_n, "year-3 years")
    rep.update(criteria=[[a, ok] for a, ok in crit], verdict=v)
    pt = perms["term blocks (years 1-4)"]["p_greater"]; pa = perms["1928-anchored blocks"]["p_greater"]
    rep["reason"] = (f"^GSPC price return {rep['first_year']}-{rep['last_year']} ({rep['n_years']} complete years, {n} year-3): "
                     f"year 3 {_pp(rep['mean_year3'])}% vs other years {_pp(rep['mean_other'])}%, excess {_pp(obs)} pp (term-bootstrap "
                     f"95% CI {_pp(ci[0])} to {_pp(ci[1])}), permutation p {_mc(pt, nd)} (term blocks) / {_mc(pa, nd)} "
                     f"(1928-anchored), {nd} draws; "
                     f"halves {_pp(h1['excess'])} pp ({h1['n_year3']}) / {_pp(h2['excess'])} pp ({h2['n_year3']}); "
                     f"{late}- (reported) {_pp(rep['late_period']['excess'])} pp ({rep['late_period']['n_year3']}); "
                     f"price only, pre-1957 S&P 90 flagged — {why}")
    return rep


def b6c_cal_presidential_year3(archive):
    """T-357: pre-registered year-3 (pre-election year) test on ^GSPC price returns."""
    miss = _missing(archive, [GSPC_B])
    if miss:
        return miss
    days, close = _daily(archive, GSPC_B, "close")
    yrs, ret = annual_returns(days, close)
    rep = presidential_year3(yrs, ret, n_perm=N_PERM, n_boot=N_BOOT)
    rep["not_run"] = ["midterm October low to year-3 end", "Democratic vs Republican presidencies (inauguration dates)",
                      "Election Day to year end", "post-election return vs prediction-market surprise (n = 2)",
                      "IWM in year 3"]
    rep["not_run_reason"] = "the trial pre-registers the year-3 test alone; the 5 other variants are not part of it"
    rep["label"] = "^GSPC close (price only); calendar years; pre-registered single test"
    return _clean(rep), int(rep["n"]), rep["verdict"], rep["reason"]


# =================================================================================================== registry ==

HARNESSES: dict[str, Callable] = {
    "b6c_cal_month_end_rebalancing": b6c_cal_month_end_rebalancing,
    "b6c_cal_weekday_speculative_spread": b6c_cal_weekday_speculative_spread,
    "b6c_cal_pension_rebalancing": b6c_cal_pension_rebalancing,
    "b6c_cal_pre_holiday": b6c_cal_pre_holiday,
    "b6c_cal_presidential_year3": b6c_cal_presidential_year3,
}

THEORY_MAP = {
    "T-345": "b6c_cal_month_end_rebalancing",
    "T-347": "b6c_cal_weekday_speculative_spread",
    "T-450": "b6c_cal_pension_rebalancing",
    "T-349": "b6c_cal_pre_holiday",
    "T-357": "b6c_cal_presidential_year3",
}
