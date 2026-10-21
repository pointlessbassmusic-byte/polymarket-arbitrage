"""
Batch 13, group ``intraday_b``: four intraday-timing claims from the 2026-10-20 web sweep (cluster "intraday").
=====================================================================================================================

  * T-671  Attention open pressure. Point-in-time S&P 500 members with archived prices, decisions 2018-08..2026-09:
           abnormal volume AV(t-1) = log(V(t-1) / mean V over its trailing 20 sessions); the equal-weighted top AV
           decile's day-t intraday return (official open -> official close) minus the equal-weighted intraday return
           of the other ranked members. Pass (>= 1,800 days): mean < -10 bp with Holm one-sided p < 0.05 over the
           registered 6 cells (Newey-West 5 lags), negative in 2018-08..2022-06 and 2022-07..2026-09, the t-2 volume
           robustness of the same sign, and >= 90% of member-days priced.
  * T-662  End-of-day reversal on the 28 single stocks with local 60m bars, 2023-11-21..2026-10: ROD3 = log(close of
           the 13:30 ET bar / dividend-adjusted prior official close); the equal-weighted bottom ROD3 quintile from the
           15:30 bar open to the official close, net of 1 bp half-spread + 1 bp at entry and the SEC Section 31 fee on
           the sale, minus the equal-weighted 28-stock universe (gross). Pass (>= 600 days): mean net excess > 0 with
           one-sided deflated p < 0.05 (6 cells), positive in each half (split 2025-05), negative Fama-MacBeth slope of
           r(15:30 -> close) on ROD3.
  * T-663  Point-in-time S&P 500 members, 2018-01..2026-09: the equal-weighted high-minus-low FINRA days-to-cover
           decile spread (formed at each FINRA publication, entered at the first open after it, held to the next),
           daily overnight (dividend-adjusted prior close -> open) minus intraday (open -> close). Pass (>= 1,500
           days): > 2 bp/day with Holm one-sided p < 0.05 over the 2 family members (DTC; trailing-60-day
           idiosyncratic volatility against SPY), Newey-West 10 lags; positive in 2018-2021 and 2022-2026; positive
           without Jan-Mar 2021; >= 90% of member-days priced.
  * T-665  Yahoo 60m FX bars 2024-01..2026-10, equal-weight USD-vs-7 basket (EUR, GBP, AUD, NZD, JPY, CAD, CHF; sign
           aligned, positive = USD up): Tokyo pre-T [17:00 New York -> 01:00 UTC] minus post-T [01:00 UTC -> 08:00
           Berlin]; Europe pre-E [08:00 -> 14:00 Berlin] minus post-L [16:00 London -> 17:00 New York]. Pass (>= 600
           days): for both fixes (pre - post) > 0 with Holm one-sided p < 0.05 (over the 2 fixes, Newey-West 5 lags),
           positive in both halves, and at least 5 of 7 currencies positive.

Conventions shared by every harness (declared before any run)
  * Data (rule 9). Every archive bundle through ``archive.load``; a row counts only when its ``available_at`` is not
    after the bundle's capture. Daily prices come from the shared ``panel_cache.daily_panel`` (value-identical to
    ``batch6c_cal._daily``; opens and closes split-adjusted as Yahoo prints them, adjclose total return); dividends and
    splits from each symbol's ``daily-events`` bundle (amounts on the same split basis as the closes). The session
    calendar is SPY's daily bars. Local 60m Yahoo bars (``mandel.ml.features.load_bars``) are stamped by their OPEN in
    UTC; the price at a bar's stamp is its open and the price one hour later its close.
  * Tests of a mean (rule 6 / 11). Each registered "mean with a Newey-West t (L lags)" criterion is judged under two
    constructions that must agree (``batch6b_bw.all_constructions``): the registered Newey-West (Bartlett, L lags)
    t with its one-sided normal p, and the house studentized circular block bootstrap (``block_bootstrap_pvalue``,
    blocks of 2L sessions, 2,000 resamples a seed averaged over 5 seeds, escalated one seed at a time to 50 while the
    Monte-Carlo band of the p straddles its Holm threshold). Holm step-down decisions (``holm_decide``) compare each
    p with alpha / (m - rank); a Monte-Carlo p decides only when its band clears that threshold. A criterion with a
    bar compares the mean with the bar (H0 on the wrong side of it). "Positive / negative in a half" and "of the same
    sign" are point signs. Rule 5 (below min_n): a failing criterion counts only when the mirror one-sided 5% test
    from the same draws rejects (``batch6c_cal._judge``).
  * House rule 10: every series here is daily (one observation per session or FX day) or follows FINRA's publication
    calendar (T-663, set by FINRA), so there is no free entry phase.

T-671 declared readings
  * Universe at day t: the fja05680 change-date snapshot in force at the t open (then the Wikipedia changes table by
    effective date after the file's last date, ``batch6c_events.membership_snapshots``); a member counts as priced
    when its Yahoo series is an EQUITY (recipe meta) and, for a member no longer in the index, a name the instrument
    has carried agrees with its Wikipedia removal name (``batch6c_stockxs.names_ok``; T-473's reused-ticker filter).
    SURVIVORSHIP: the archive's 901-symbol daily-history set is TODAY's universe, so removed, acquired and renamed
    members without a Yahoo series are absent; the claim is itself defined on members with archived prices and the
    coverage gate measures the share missing.
  * AV(t-1) = log(V(t-1) / mean of V over the 20 sessions t-21..t-2) (the trailing mean BEFORE the measured day,
    the standard abnormal-volume form), at least 15 of the 20 with a positive volume and V(t-1) > 0; V = Yahoo daily
    volume (a split-adjusted series, so the ratio is on one basis). The procedure admits t-1 volume for the day-t open
    (published by about 20:00 ET on t-1), overriding the archive's +24h stamp; the t-2 robustness uses AV(t-2) =
    log(V(t-2) / mean V(t-22..t-3)).
  * Ranked set: members at t with a finite AV. Top decile = the floor(n/10) highest (ties share the boundary slots,
    ``batch6c_stockxs.tail_fractions``); the rest = every other ranked member (fractional complements). Intraday
    return = close(t) / open(t) - 1 from daily-history; a ranked name without a day-t bar drops out of that day's
    means. d(t) = EW top - EW rest.
  * Holm over the registered 6 cells: the other five cells (t-2 robustness, off-exchange variant, overnight-minus-
    intraday, the tradable form, the StockTwits variant) are secondaries with nulls of their own, so the primary is
    adjusted with them ranked last (p = 1, the conservative convention of ``batch6c_cal._holm``): threshold 0.05 / 6.
  * Coverage gate: member-days priced (an accepted series with a day-t bar) over member-days in force, on the decision
    days; below 90% the criterion is a data limit (None, inconclusive), never a pass.
  * Off-exchange variant (reported with its p): OX = finra-regsho-cnms total_volume / Yahoo as-traded volume (volume
    / the split factor after the day) on file day t-1, z-scored against the mean and sd of OX over the 60 file days
    t-61..t-2 (>= 40 present); a CNMS series is used only when it passes the FINRA-volume identity check
    (``batch6c_events.finra_identity``). Tradable form (reported): the top decile by AV(t-2) among the members at t-1,
    bought at the t-1 close and sold at the t open, (open(t) + dividend(t)) / close(t-1) - 1 minus 3 bp per side.
    Secondaries reported: top-minus-rest (overnight - intraday) with the overnight from the t-1 close (descriptive:
    t-1's volume is not final at that close), the bottom-decile placebo. Not computed (reported-only items): earnings
    days (no earnings calendar is archived; sec-submissions filing rows carry no 8-K item codes) and the StockTwits
    variant (the intensity bundles sample a few dozen symbols a week from 2025-W43: no S&P cross-section).

T-662 declared readings
  * Bars: for each of the 28 names (``T662_SYMS``, the local 60m single-stock set) and session t: P(14:30) = close of
    the bar stamped 13:30 ET, entry = open of the bar stamped 15:30 ET, exit = the daily-history close (the official
    close; the 16:00 stub is never used). The 14:30 bar is skipped. Early closes (a 13:00 tick and no 15:30 bar on any
    name) are excluded and counted; a name missing a needed bar or close that day drops out of it. A day needs >= 10
    usable names.
  * ROD3 = log(P(14:30) / (C(t-1) - D(t))), D(t) the daily-events dividend with ex-date t (declared weeks ahead).
  * Bottom quintile = the floor(n/5) lowest ROD3 (ties share slots); long-leg net return per name = r - 2 bp (1 bp
    half-spread + 1 bp at entry) - fee x (1 + r), r = C(t) / O(15:30) - 1; the exit at the official close crosses
    no spread. SEC Section 31 fee: the highest rate in force in the window, $27.80 per million of sale proceeds, on
    every sale (the conservative reading; the rate fell to $0 in May 2025). Excess = EW net long minus the EW gross
    return of every usable name.
  * "One-sided deflated p < 0.05 (6 cells)" is read three ways that must agree (rule 11): 1 - DSR at 6 trials with the
    house default zero-skill trial-Sharpe variance 1/(T-1) (``deflated_sharpe_ratio``, the batch5/batch13 reading of
    "deflated p"), and Bonferroni x 6 on the Newey-West (5 lags) and on the studentized CBB one-sided p's.
  * Fama-MacBeth: the daily cross-sectional OLS slope of r(15:30 -> close) on ROD3 over the usable names, averaged
    (Newey-West 5 lags reported); "negative" = the point mean < 0. Halves: days before / from 2025-05-01.
  * Reported, not judged: long-only absolute net; hedged (long bottom quintile, short equal dollars of QQQ over the
    same half-hour, the short also paying 2 bp at entry and the fee on its sale); mirror (top quintile); placebo (a
    random floor(n/5) names a day, 1,000 draws); FINRA days-to-cover (latest release published before t) and CNMS
    off-exchange-share (file day t-1) interactions, splitting each day's bottom quintile at the 28-name median.

T-663 declared readings
  * DTC = currentShortPositionQuantity / averageDailyVolumeQuantity of the member's FINRA row (index ticker BRK.B ->
    FINRA BRKB), used only when the FINRA issue name agrees with a name the instrument has carried
    (``batch13_short_b.ident_ok``); ADV > 0. A release enters at the first session whose 09:30 ET open is strictly
    after its available_at (end of the 8th NYSE business day after settlement); members are those in force at that
    open; a name is priced when it has a close the session before. Deciles: floor(n/10) highest and lowest (ties
    share). The formed sets are held unchanged to the next release's entry open: day t's intraday component belongs
    to the sets entered at or before the t open, the overnight component (close t-1 -> open t) to the sets held over
    that night, so a hold ends with the overnight into the next entry open. Legs are equal-weighted each day over
    the names with a return that day. Overnight = (open(t) + D(t)) / close(t-1) - 1 with D from daily-events.
  * Second family member: deciles on the sd of OLS residuals of the member's 60 daily total returns (adjclose) ending
    at the close before the entry on SPY's (>= 50 paired returns), at the same publication entries.
  * Holm over the 2 members per construction. "Positive in 2018-2021 / 2022-2026" and "without Jan-Mar 2021" (days
    2021-01-01..2021-03-31 dropped) are point means > 0 of the same daily series. Coverage gate as T-671 on the
    2018-01..2026-09 days. SURVIVORSHIP as T-671.
  * Reported, not judged: the overnight and intraday spread legs, the high-DTC intraday leg (the registration's
    pre-build bar for an intraday-only short: about 4 bp/day plus the locate), the middle-decile placebo (decile 6
    minus decile 5 by rank), the two-sided p, and the 28-stock 60m descriptive (names above the 28-name median DTC
    minus those below, 15:30 bar open -> official close). The value-weighted version is not computed (no point-in-
    time share counts are wired here; reported-only).

T-665 declared readings
  * Window edges are built per day in local time with zoneinfo and mapped to UTC hour stamps (every edge falls on a
    whole UTC hour). A window [a, b) uses the bars stamped a, a+1h, ..., b-1h: it is complete only when every one of
    them is present and none is stale (open = high = low = close); its return is log(close of the bar stamped b-1h /
    open of the bar stamped a), times -1 for EURUSD, GBPUSD, AUDUSD, NZDUSD (USD up = positive). An incomplete or
    stale window drops that currency-day (the procedure's rule extended to absent bars).
  * Day d = the date of the Tokyo morning / European session (Monday-Friday). pre-T runs from 17:00 New York on the
    previous calendar day, so a Monday's pre-T starts at the Sunday open, before Yahoo's first Sunday bar (19:00 ET):
    Mondays have no complete pre-T and drop out of the Tokyo arm (a data limit, counted).
  * Basket day: every one of the 7 currencies complete in both windows of the fix (a fixed equal-weight basket);
    per-currency means use each currency's own complete days. "At least 5 of 7 currencies with the same sign" = at
    least 5 per-currency mean (pre - post) > 0. Halves: the fix's usable days split at their median day.
  * n for min_n is the smaller of the two fixes' basket days (the pass needs both fixes).
  * Reported, not judged: the trading rule's net (long USD pre, short USD post: 4 sides a day at 1 bp EURUSD/USDJPY,
    2 bp the others); placebo windows of the same lengths shifted +6 h and -6 h; the E-L window [14:00 Berlin -> 16:00
    London] (expected flat); DXY (DX-Y.NYB, from 2024-05-29); Japanese holidays (no Tokyo fix) and month-end days
    (the last two weekdays of a month, T-575) apart; the fx-spot-g10 cross-check (correlation of the daily change in
    the price at the 12:00 ET bar open with the FRED noon rate's).
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import panel_cache as PC
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_bw import all_constructions
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio

SEED = 0
ALPHA = 0.05
UTC = timezone.utc
NY = ZoneInfo("America/New_York")

SPY_B = "daily-history-SPY"
QQQ_B = "daily-history-QQQ"
FJA_B = "fja-sp500-components"
SPELLS_B = "fja-sp500-ticker-spells"
CHG_B = "wikipedia-sp500-changes"
WIKI_B = "wikipedia-sp500-constituents"
TICK_B = "sec-company-tickers"
SI_FIRST_B = "finra-short-interest-2017-12-29"
CNMS_FIRST_B = "finra-regsho-cnms-2018-08"
FX_B = "fx-spot-g10"

PANEL_START = "2017-06-01"       # 60 sessions of history before the first T-663 entry (2018-01)
UNIV_END = "2026-12-31"
COVERAGE = 0.90

T671_START, T671_END = "2018-08-01", "2026-09-30"
T671_SPLIT = "2022-07-01"
T671_BAR = -10e-4
T671_LAG = 5
T671_BLOCK = 10
T671_CELLS = 6
T671_MIN_N = 1800
T671_WIN = 20
T671_MIN_WIN = 15
T671_OX_WIN = 60
T671_OX_MIN = 40
T671_COST = 3e-4                 # per side, tradable form

T662_SYMS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX", "JPM", "BAC", "XOM", "CVX",
             "UNH", "LLY", "COST", "WMT", "HD", "PLTR", "COIN", "MSTR", "SMCI", "INTC", "MU", "ORCL", "CRM", "ADBE")
T662_START, T662_END = "2023-11-21", "2026-10-31"
T662_SPLIT = "2025-05-01"
T662_ENTRY_COST = 2e-4           # 1 bp half-spread + 1 bp, at entry
T662_SEC_FEE = 27.80e-6          # $27.80 per million of sale proceeds (highest rate in force in the window)
T662_LAG = 5
T662_BLOCK = 10
T662_CELLS = 6
T662_MIN_N = 600
T662_MIN_NAMES = 10
T662_PLACEBO = 1000

T663_START, T663_END = "2018-01-01", "2026-09-30"
T663_SPLIT = "2022-01-01"
T663_EXCL = ("2021-01-01", "2021-03-31")
T663_BAR = 2e-4
T663_LAG = 10
T663_BLOCK = 20
T663_MIN_N = 1500
T663_IVOL_WIN = 60
T663_IVOL_MIN = 50

T665_START, T665_END = "2024-01-01", "2026-10-31"
T665_LAG = 5
T665_BLOCK = 10
T665_MIN_N = 600
T665_NEED = 5
# (currency, local 60m symbol, sign to USD-up, cost per side)
T665_CCY = (("EUR", "EURUSD=X", -1.0, 1e-4), ("GBP", "GBPUSD=X", -1.0, 2e-4), ("AUD", "AUDUSD=X", -1.0, 2e-4),
            ("NZD", "NZDUSD=X", -1.0, 2e-4), ("JPY", "USDJPY=X", 1.0, 1e-4), ("CAD", "USDCAD=X", 1.0, 2e-4),
            ("CHF", "USDCHF=X", 1.0, 2e-4))
# window edges: (time zone, hour, calendar-day offset from day d)
PRE_T = (("America/New_York", 17, -1), ("UTC", 1, 0))
POST_T = (("UTC", 1, 0), ("Europe/Berlin", 8, 0))
PRE_E = (("Europe/Berlin", 8, 0), ("Europe/Berlin", 14, 0))
POST_L = (("Europe/London", 16, 0), ("America/New_York", 17, 0))
E_L = (("Europe/Berlin", 14, 0), ("Europe/London", 16, 0))
# Japanese national holidays and the bank holidays (31 Dec - 3 Jan) on weekdays, 2024-2026: no Tokyo fix
JP_HOLIDAYS = frozenset((
    "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-08", "2024-02-12", "2024-02-23", "2024-03-20", "2024-04-29",
    "2024-05-03", "2024-05-06", "2024-07-15", "2024-08-12", "2024-09-16", "2024-09-23", "2024-10-14", "2024-11-04",
    "2024-12-31",
    "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-13", "2025-02-11", "2025-02-24", "2025-03-20", "2025-04-29",
    "2025-05-05", "2025-05-06", "2025-07-21", "2025-08-11", "2025-09-15", "2025-09-23", "2025-10-13", "2025-11-03",
    "2025-11-24", "2025-12-31",
    "2026-01-01", "2026-01-02", "2026-02-11", "2026-02-23", "2026-03-20", "2026-04-29", "2026-05-04", "2026-05-05",
    "2026-05-06", "2026-07-20", "2026-08-11", "2026-09-21", "2026-09-22", "2026-09-23", "2026-10-12", "2026-11-03",
    "2026-11-23", "2026-12-31"))


# ================================================================================================= small helpers ==

def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not B7C._has(archive, n)]
    return _out({"missing": miss}, 0, "inconclusive", f"missing bundles: {', '.join(miss)} (rule 9)") if miss else None


def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f} bp"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def nw(x, lag: int) -> dict:
    """Mean and Newey-West (Bartlett 1 - l/(L+1)) standard error of a series (finite values only)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 3:
        return {"mean": None, "se": None, "t": None, "n": int(n)}
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 0.0) / n)
    return {"mean": float(x.mean()), "se": se, "t": float(x.mean() / se) if se > 0 else None, "n": int(n)}


def boot_p(d, block: int, alphas: Sequence[float] = (ALPHA,)) -> tuple:
    """(p_greater, p_less, draws) of the studentized circular block bootstrap of mean(d) (H0 mean <= 0 / >= 0), the mean
    over seeds 0, 1, ... of 2,000 resamples each: 5 seeds, then one more at a time while either p is undecided
    (``batch6c_cal.decide_p``) at any of ``alphas``, up to 50 seeds. (None, None, 0) below 8 observations."""
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    nb = CAL.N_BOOT
    if d.size < 8:
        return None, None, 0
    z = np.zeros_like(d)
    ps = []
    while True:
        k = len(ps)
        ps.append((block_bootstrap_pvalue(d, z, n_boot=nb, block_len=block, seed=SEED + k),
                   block_bootstrap_pvalue(-d, z, n_boot=nb, block_len=block, seed=SEED + k)))
        if len(ps) < CAL.N_SEEDS:
            continue
        pg = float(np.mean([p[0] for p in ps]))
        pl = float(np.mean([p[1] for p in ps]))
        nd = nb * len(ps)
        done = all(CAL.decide_p(pg, nd, a) is not None and CAL.decide_p(pl, nd, a) is not None for a in alphas)
        if done or len(ps) >= CAL.MAX_SEEDS:
            return pg, pl, nd


def mean_test(x, bar: float, side: str, lag: int, block: int, m: int = 1) -> dict:
    """The mean of ``x`` against ``bar`` in the claimed direction (``side`` 'greater': H0 mean <= bar; 'less': H0
    mean >= bar): Newey-West (``lag``) t of x - bar with its one-sided normal p and the mirror p, and the studentized
    CBB (``block``) p's escalated at the Holm thresholds alpha / k, k = 1..m."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    out = {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "bar": bar, "side": side, "lag": lag,
           "block": block, "nw_t": None, "p_nw": None, "p_nw_opp": None, "p_bt": None, "p_bt_opp": None, "draws": 0}
    if x.size < 8:
        return out
    r = nw(x - bar, lag)
    t = r["t"]
    if t is not None:
        pg, pl = 1.0 - _phi(t), _phi(t)
        out.update(nw_t=t, nw_se=r["se"], p_nw=pg if side == "greater" else pl, p_nw_opp=pl if side == "greater" else pg)
    alphas = tuple(sorted({ALPHA / k for k in range(1, max(1, m) + 1)}))
    bg, bl, dr = boot_p(x - bar, block, alphas)
    out.update(p_bt=bg if side == "greater" else bl, p_bt_opp=bl if side == "greater" else bg, draws=dr)
    return out


def holm_decide(ps: Sequence[Optional[float]], draws: Sequence[Optional[int]], alpha: float = ALPHA) -> list:
    """Holm step-down decisions (True reject / False keep / None undecided) for p's; a None p ranks last as p = 1, an
    analytic p (draws None) is compared exactly, a Monte-Carlo p by ``batch6c_cal.decide_p`` at alpha / (m - rank).
    Once a hypothesis is kept every later one is kept; after an undecided one a later one is undecided unless it is
    kept on its own."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: 1.0 if ps[i] is None else float(ps[i]))
    out: list = [False] * m
    state: Optional[bool] = True
    for j, i in enumerate(order):
        thr = alpha / (m - j)
        p = ps[i]
        if p is None:
            own: Optional[bool] = False
        elif draws[i] is None:
            own = bool(p < thr)
        else:
            own = CAL.decide_p(p, draws[i], thr)
        if state is True:
            res = own
        elif state is None:
            res = False if own is False else None
        else:
            res = False
        out[i] = res
        state = res
    return out


def holm_adjusted(ps: Sequence[Optional[float]]) -> list:
    return B7C.holm(list(ps))


def sig_row(label: str, test: dict, nw_dec: Optional[bool], bt_dec: Optional[bool], adj_nw, adj_bt) -> tuple:
    """One registered significance criterion judged under the Newey-West and studentized CBB constructions (rule 11):
    the point on the claimed side of the bar AND the Holm decision; decisive (rule 5) when the mirror one-sided 5% test
    of the same construction rejects."""
    mu, bar, side = test["mean"], test["bar"], test["side"]
    point = mu is not None and ((mu > bar) if side == "greater" else (mu < bar))
    nw_ok = False if not point else nw_dec
    bt_ok = False if not point else bt_dec
    nw_opp = test["p_nw_opp"] is not None and test["p_nw_opp"] < ALPHA
    bt_opp = test["p_bt_opp"] is not None and CAL.decide_p(test["p_bt_opp"], test["draws"]) is True
    rows = [(f"Newey-West {test['lag']} lags t {_s(test['nw_t'])}, one-sided p {_f(test['p_nw'], 4)} (Holm-adjusted "
             f"{_f(adj_nw, 4)})", nw_ok, nw_opp),
            (f"studentized CBB {test['block']}-session blocks p {CAL._mc(test['p_bt'], test['draws'])} (Holm-adjusted "
             f"{_f(adj_bt, 4)})", bt_ok, bt_opp)]
    return all_constructions(rows, label)


def sign_row(label: str, x, want_positive: bool, lag: int) -> tuple:
    """A point-sign criterion on the mean of ``x``; decisive (rule 5) when the Newey-West 95% interval lies wholly on
    the wrong side."""
    r = nw(x, lag)
    if r["mean"] is None:
        return (label + " (n/a)", None, False)
    ok = r["mean"] > 0 if want_positive else r["mean"] < 0
    t = r["t"]
    dec = t is not None and ((t <= -1.959964) if want_positive else (t >= 1.959964))
    return (f"{label} ({_bp(r['mean'])}, NW t {_s(t)})", bool(ok), bool(dec))


def _judge(rows, n: int, min_n: int, unit: str) -> tuple:
    v, why, crit = CAL._judge(rows, n, min_n, unit)
    return v, why, crit


def _iso_days(days) -> np.ndarray:
    return np.asarray([str(d) for d in days])


# ============================================================================================ shared daily data ==

def _snaps(archive) -> list:
    def load():
        fja = EV._rows(archive, FJA_B)
        chg = [r.get("value") or {} for r in EV._rows(archive, CHG_B)] if B7C._has(archive, CHG_B) else []
        return EV.membership_snapshots(fja, chg)
    return CAL._cached(archive, ("b13ib_snaps",), load)


def _members_in(snaps: Sequence[tuple], lo: str, hi: str) -> set:
    lo_e, hi_e = EV._ed(lo), EV._ed(hi)
    out = set(EV.members_at(snaps, lo_e))
    for e, s in snaps:
        if lo_e < e <= hi_e:
            out |= set(s)
    return out


def _events(archive, y: str) -> tuple:
    """({ex_date: dividend amount}, [(ex_date, split ratio)]) from a symbol's daily-events bundle."""
    name = SX.de(y)
    divs, splits = {}, []
    if not SX._has(archive, name):
        return divs, splits
    for r in SX._stream(archive, name):
        v = r.get("value") or {}
        kind = r.get("kind") or v.get("type")
        ex = str(v.get("ex_date") or (SX._bar_day(v["t"]) if v.get("t") is not None else ""))[:10]
        if not ex:
            continue
        if kind == "dividend":
            a = SX._num(v.get("amount"))
            if np.isfinite(a) and a > 0:
                divs[ex] = divs.get(ex, 0.0) + a
        elif kind == "split":
            num, den = SX._num(v.get("numerator")), SX._num(v.get("denominator"))
            if num > 0 and den > 0:
                splits.append((ex, num / den))
    return divs, sorted(splits)


def split_after(days: np.ndarray, splits: Sequence[tuple]) -> np.ndarray:
    """Per day: the product of the split ratios with an ex-date after it (as-traded volume = Yahoo volume / factor)."""
    f = np.ones(len(days))
    for ex, r in splits:
        f[days < ex] *= r
    return f


def _panel_slice(archive, days: np.ndarray, syms: Sequence[str], fields: Sequence[str]) -> dict:
    """{field: days x syms array} from the shared daily panel (NaN where a symbol has no bar or no series); the 1 GB
    panel is released afterwards."""
    P = PC.daily_panel(archive)
    pdays = np.asarray(P.days).astype(str)
    pos = np.minimum(np.searchsorted(pdays, days), pdays.size - 1)
    ok = pdays[pos] == days
    pcol = {str(s): j for j, s in enumerate(np.asarray(P.symbols).tolist())}
    cols = np.array([pcol.get(SX._safe(s), -1) for s in syms], int)
    out = {}
    for f in fields:
        M = getattr(P, f)
        A = np.full((len(days), len(syms)), np.nan)
        have = cols >= 0
        if have.any():
            sub = M[pos[ok]][:, cols[have]]
            tmp = np.full((int(ok.sum()), len(syms)), np.nan)
            tmp[:, have] = sub
            A[ok] = tmp
        out[f] = A
    out["has_series"] = cols >= 0
    del P
    PC._MEMO.clear()
    return out


def sp_panel(archive) -> dict:
    """Point-in-time S&P 500 members on SPY's sessions from PANEL_START: accepted Yahoo series (EQUITY, removed members'
    names agreeing with the Wikipedia removal name), their open / close / adjclose / volume, dividends and split
    factors, the member mask, the tickers in force per day and the acceptance status per ticker."""
    def load():
        cal = SX._sessions(archive)
        i0 = cal.on_or_after(PANEL_START)
        days = np.array(cal.days[i0:])
        open_ts = np.asarray(cal.open[i0:], float)
        snaps = _snaps(archive)
        tick = sorted(_members_in(snaps, PANEL_START, UNIV_END))
        wiki_now, removed = set(), {}
        if B7C._has(archive, WIKI_B):
            for r in SX._rows(archive, WIKI_B):
                v = r.get("value") or {}
                if v.get("symbol"):
                    wiki_now.add(SX.ysym(v["symbol"]))
        if B7C._has(archive, CHG_B):
            for v in sorted((r.get("value") or {} for r in SX._rows(archive, CHG_B)), key=lambda v: v.get("effective_date") or ""):
                if v.get("removed_ticker") and v.get("removed_security"):
                    removed[SX.ysym(v["removed_ticker"])] = v["removed_security"]
        sec_t = SX._sec_tickers(archive) if B7C._has(archive, TICK_B) else {}
        names_all = {str(e.name)[len(PC.PREFIX):] for e in archive.entries() if str(e.name).startswith(PC.PREFIX)}
        status, cand = {}, []
        for t in tick:
            y = SX.ysym(t)
            if SX._safe(y) not in names_all:
                status[t] = "no archived daily history"
                continue
            meta = SX._meta(archive, SX.dh(y)) or {}
            if meta.get("instrumentType") != "EQUITY":
                status[t] = "Yahoo series is not an EQUITY"
                continue
            cand.append((t, y, meta))
        ciks = {sec_t[y][0] for _, y, _ in cand if y in sec_t}
        comp = SX._company_rows(archive, ciks) if ciks else {}
        keep, alias = [], {}
        seen = set()
        for t, y, meta in cand:
            nm = [meta.get("longName") or ""]
            if y in sec_t:
                v = comp.get(sec_t[y][0]) or {}
                nm += [sec_t[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
            nm = [x for x in nm if x]
            if y not in wiki_now and y in removed and SX.names_ok(removed[y], nm) is False:
                status[t] = "name disagrees with the Wikipedia removal name (reused ticker)"
                continue
            status[t] = "ok"
            if y in seen:
                continue
            seen.add(y)
            keep.append((t, y))
            alias[y] = nm
        syms = [y for _, y in keep]
        sl = _panel_slice(archive, days, syms + ["SPY"], ("open", "close", "adjclose", "volume"))
        O, C, A, V = (sl[f][:, :-1] for f in ("open", "close", "adjclose", "volume"))
        spy_a = sl["adjclose"][:, -1]
        D, S = len(days), len(syms)
        DIV = np.zeros((D, S))
        F = np.ones((D, S))
        dpos = {d: i for i, d in enumerate(days.tolist())}
        for j, y in enumerate(syms):
            dv, sp = _events(archive, y)
            for ex, amt in dv.items():
                i = dpos.get(ex)
                if i is not None:
                    DIV[i, j] = amt
            F[:, j] = split_after(days, sp)
        col = {y: j for j, y in enumerate(syms)}
        ysym_of = {t: SX.ysym(t) for t in tick}
        eds = [s[0] for s in snaps]
        M = np.zeros((D, S), bool)
        n_force = np.zeros(D, int)
        cache: dict = {}
        for i, d in enumerate(days.tolist()):
            k = bisect.bisect_right(eds, EV._ed(d)) - 1
            if k < 0:
                continue
            if k not in cache:
                st = snaps[k][1]
                cache[k] = (len(st), sorted({col[ysym_of[t]] for t in st if status.get(t) == "ok" and ysym_of[t] in col}))
            n_force[i] = cache[k][0]
            M[i, cache[k][1]] = True
        priced = M & np.isfinite(C) & (C > 0)
        return {"days": days, "open_ts": open_ts, "syms": syms, "col": col, "alias": alias, "O": O, "C": C, "A": A,
                "V": V, "spy_a": spy_a, "DIV": DIV, "F": F, "M": M, "n_force": n_force, "priced": priced,
                "status": status, "snaps_last": EV._iso(snaps[-1][0]) if snaps else None}
    return CAL._cached(archive, ("b13ib_panel",), load)


def coverage(pan: dict, lo: str, hi: str) -> dict:
    """Share of member-days in force on the sessions in [lo, hi] that are priced (an accepted series with a bar)."""
    d = pan["days"]
    m = (d >= lo) & (d <= hi)
    force = int(pan["n_force"][m].sum())
    priced = int(pan["priced"][m].sum())
    status = pan["status"]
    why: dict = {}
    for t, s in status.items():
        if s != "ok":
            why[s] = why.get(s, 0) + 1
    return {"member_days": force, "priced": priced, "share": priced / force if force else None, "unpriced_tickers": why}


def day_returns(pan: dict) -> tuple:
    """(intraday close/open - 1, overnight (open + dividend) / previous close - 1), days x syms, NaN where undefined."""
    O, C, DIV = pan["O"], pan["C"], pan["DIV"]
    good_o = np.isfinite(O) & (O > 0)
    good_c = np.isfinite(C) & (C > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        ID = np.where(good_o & good_c, C / np.where(good_o, O, 1.0) - 1.0, np.nan)
        ON = np.full(O.shape, np.nan)
        prev = np.vstack([np.full((1, C.shape[1]), np.nan), C[:-1]])
        gp = np.isfinite(prev) & (prev > 0)
        ON = np.where(good_o & gp, (O + DIV) / np.where(gp, prev, 1.0) - 1.0, np.nan)
    return ID, ON


def _leg(w: np.ndarray, r: np.ndarray) -> float:
    ok = (w > 0) & np.isfinite(r)
    s = w[ok].sum()
    return float((w[ok] * r[ok]).sum() / s) if s > 0 else float("nan")


# ========================================================================================================= T-671 ==

def abnormal_volume(V: np.ndarray, lag: int, win: int = T671_WIN, min_win: int = T671_MIN_WIN) -> np.ndarray:
    """Row i: log(V[i - lag] / mean of the positive volumes in rows i-lag-win .. i-lag-1), NaN unless V[i - lag] > 0 and
    at least ``min_win`` of the ``win`` trailing volumes are positive. Row i uses no volume from rows after i - lag."""
    V = np.asarray(V, float)
    D = V.shape[0]
    Vp = np.where(np.isfinite(V) & (V > 0), V, np.nan)
    z = np.nan_to_num(Vp)
    c = np.isfinite(Vp).astype(float)
    cs = np.vstack([np.zeros((1,) + V.shape[1:]), np.cumsum(z, axis=0)])
    cc = np.vstack([np.zeros((1,) + V.shape[1:]), np.cumsum(c, axis=0)])
    out = np.full(V.shape, np.nan)
    i = np.arange(lag + win, D)
    if i.size == 0:
        return out
    r = i - lag
    s = cs[r] - cs[r - win]
    n = cc[r] - cc[r - win]
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(n >= min_win, s / np.where(n > 0, n, 1.0), np.nan)
        out[i] = np.log(Vp[r] / m)
    return out


def trailing_z(X: np.ndarray, lag: int, win: int = T671_OX_WIN, min_win: int = T671_OX_MIN) -> np.ndarray:
    """Row i: (X[i - lag] - mean) / sd over the finite values of rows i-lag-win .. i-lag-1 (>= ``min_win``, sd > 0)."""
    X = np.asarray(X, float)
    D = X.shape[0]
    z0 = np.nan_to_num(X)
    c = np.isfinite(X).astype(float)
    cs = np.vstack([np.zeros((1,) + X.shape[1:]), np.cumsum(z0, axis=0)])
    cq = np.vstack([np.zeros((1,) + X.shape[1:]), np.cumsum(z0 * z0, axis=0)])
    cc = np.vstack([np.zeros((1,) + X.shape[1:]), np.cumsum(c, axis=0)])
    out = np.full(X.shape, np.nan)
    i = np.arange(lag + win, D)
    if i.size == 0:
        return out
    r = i - lag
    s, q, n = cs[r] - cs[r - win], cq[r] - cq[r - win], cc[r] - cc[r - win]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = s / np.where(n > 0, n, 1.0)
        var = (q - n * mu * mu) / np.where(n > 1, n - 1, 1.0)
        sd = np.sqrt(np.maximum(var, 0.0))
        ok = (n >= min_win) & (sd > 0)
        out[i] = np.where(ok, (X[r] - mu) / np.where(ok, sd, 1.0), np.nan)
    return out


def decile_weights(score_row: np.ndarray, elig_row: np.ndarray, high: bool = True, q: int = 10) -> tuple:
    """(tail weights, rest weights, n ranked) of one day's cross-section: the floor(n/q) highest (``high``) or lowest
    eligible scores (ties share the boundary slots) and every other ranked name's complement."""
    elig = elig_row & np.isfinite(score_row)
    n = int(elig.sum())
    k = n // q
    w = SX.tail_fractions(score_row, elig, k, high) if k >= 1 else np.zeros(score_row.size)
    rest = np.where(elig, 1.0 - w, 0.0)
    return w, rest, n


def spread_series(score: np.ndarray, elig: np.ndarray, R: np.ndarray, rows: np.ndarray, high: bool = True) -> dict:
    """Per row in ``rows``: EW tail-decile return minus EW rest return, the two legs and the ranked count."""
    top = np.full(rows.size, np.nan)
    rest = np.full(rows.size, np.nan)
    nr = np.zeros(rows.size, int)
    for k, i in enumerate(rows):
        w, wr, n = decile_weights(score[i], elig[i], high)
        nr[k] = n
        if n < 10:
            continue
        top[k], rest[k] = _leg(w, R[i]), _leg(wr, R[i])
    return {"d": top - rest, "top": top, "rest": rest, "n_ranked": nr}


def offx_matrix(archive, pan: dict) -> dict:
    """CNMS off-exchange share OX = total_volume / Yahoo as-traded volume on the panel's sessions (NaN without a file
    or a bar), for CNMS symbols mapped to accepted panel series that pass the FINRA-volume identity check."""
    def load():
        from mandel.experiments import batch13_short_a as SA
        Cn = SA.cnms_data(archive)
        days = pan["days"]
        dpos = {d: i for i, d in enumerate(days.tolist())}
        rows = np.array([dpos.get(d, -1) for d in Cn["iso"]], int)
        have = rows >= 0
        OX = np.full(pan["V"].shape, np.nan)
        status = {"identity_failed": [], "ok": 0, "not_checkable": 0, "no_series": 0}
        for jc, s in enumerate(Cn["syms"]):
            y = SX.ysym(s)
            j = pan["col"].get(y)
            if j is None:
                status["no_series"] += 1
                continue
            tv = np.full(len(days), np.nan)
            tv[rows[have]] = Cn["TV"][have, jc]
            with np.errstate(invalid="ignore", divide="ignore"):
                yv = pan["V"][:, j] / pan["F"][:, j]
            chk = EV.finra_identity(tv, yv, pan["M"][:, j])
            if chk["ok"] is False:
                status["identity_failed"].append(y)
                continue
            status["ok" if chk["ok"] else "not_checkable"] += 1
            with np.errstate(invalid="ignore", divide="ignore"):
                OX[:, j] = np.where(np.isfinite(tv) & (tv > 0) & np.isfinite(yv) & (yv > 0), tv / np.where(yv > 0, yv, 1.0), np.nan)
        return {"OX": OX, "status": status, "first": Cn["iso"][0] if len(Cn["iso"]) else None,
                "last": Cn["iso"][-1] if len(Cn["iso"]) else None}
    return CAL._cached(archive, ("b13ib_offx",), load)


def t671_core(pan: dict, AV1: np.ndarray, AV2: np.ndarray, ID: np.ndarray, ON: np.ndarray, rows: np.ndarray) -> dict:
    """The T-671 daily series on decision rows ``rows``: primary (AV(t-1) top decile vs rest, intraday), t-2
    robustness, bottom-decile placebo, overnight-minus-intraday (top vs rest) and the tradable overnight form."""
    M = pan["M"]
    prim = spread_series(AV1, M, ID, rows, True)
    rob = spread_series(AV2, M, ID, rows, True)
    plac = spread_series(AV1, M, ID, rows, False)
    onid = spread_series(AV1, M, ON - ID, rows, True)
    trad = np.full(rows.size, np.nan)
    for k, i in enumerate(rows):
        if i < 1:
            continue
        w, _, n = decile_weights(AV2[i], M[i - 1], True)
        if n >= 10:
            trad[k] = _leg(w, ON[i]) - 2 * T671_COST
    return {"prim": prim, "rob": rob, "plac": plac, "onid": onid, "trad": trad}


def b13_intraday_b_attention_open(archive):
    """T-671."""
    miss = _missing(archive, [SPY_B, FJA_B, CHG_B, SI_FIRST_B, CNMS_FIRST_B])
    if miss:
        return miss
    pan = sp_panel(archive)
    days = pan["days"]
    rows = np.flatnonzero((days >= T671_START) & (days <= T671_END))
    ID, ON = day_returns(pan)
    AV1 = abnormal_volume(pan["V"], 1)
    AV2 = abnormal_volume(pan["V"], 2)
    core = t671_core(pan, AV1, AV2, ID, ON, rows)
    d = core["prim"]["d"]
    ok = np.isfinite(d)
    n = int(ok.sum())
    dd = days[rows][ok]
    x = d[ok]
    test = mean_test(x, T671_BAR, "less", T671_LAG, T671_BLOCK, m=T671_CELLS)
    ps_nw = [test["p_nw"]] + [None] * (T671_CELLS - 1)
    ps_bt = [test["p_bt"]] + [None] * (T671_CELLS - 1)
    nw_dec = holm_decide(ps_nw, [None] * T671_CELLS)[0]
    bt_dec = holm_decide(ps_bt, [test["draws"]] + [None] * (T671_CELLS - 1))[0]
    adj_nw, adj_bt = holm_adjusted(ps_nw)[0], holm_adjusted(ps_bt)[0]
    h1, h2 = x[dd < T671_SPLIT], x[dd >= T671_SPLIT]
    rob = core["rob"]["d"]
    cov = coverage(pan, T671_START, T671_END)
    cov_ok = None if cov["share"] is None or cov["share"] < COVERAGE else True
    rows_c = [sig_row(f"mean top-minus-rest intraday {_bp(test['mean'])} < -10 bp with Holm one-sided p < 0.05 over 6 cells",
                      test, nw_dec, bt_dec, adj_nw, adj_bt),
              sign_row(f"negative in {T671_START[:7]}..2022-06", h1, False, T671_LAG),
              sign_row(f"negative in 2022-07..{T671_END[:7]}", h2, False, T671_LAG),
              sign_row("t-2 volume robustness of the same sign (negative)", rob[np.isfinite(rob)], False, T671_LAG),
              (f"coverage gate: {_f(cov['share'], 4)} of {cov['member_days']} member-days priced (>= 0.90)", cov_ok, False)]
    rows_c = CAL._undecided(rows_c)
    v, why, crit = _judge(rows_c, n, T671_MIN_N, "decision days")
    # reported secondaries
    rep = {}
    for key, lab in (("rob", "t-2 robustness"), ("plac", "bottom-decile placebo"), ("onid", "overnight-minus-intraday, top minus rest")):
        s = core[key]["d"]
        r = nw(s, T671_LAG)
        rep[key] = {"label": lab, "mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    tr = nw(core["trad"], T671_LAG)
    tr_bt = boot_p(core["trad"], T671_BLOCK)
    rep["tradable"] = {"label": "buy top AV(t-2) decile at the t-1 close, sell at the t open, net of 3 bp/side",
                       "mean_bp": None if tr["mean"] is None else tr["mean"] * 1e4, "nw_t": tr["t"], "n": tr["n"],
                       "p_boot_gt0": tr_bt[0]}
    top_on = spread_series(AV1, pan["M"], ON, rows, True)
    rep["top_overnight_bp"] = None if not np.isfinite(top_on["top"]).any() else float(np.nanmean(top_on["top"]) * 1e4)
    rep["top_intraday_bp"] = float(np.nanmean(core["prim"]["top"]) * 1e4)
    rep["rest_intraday_bp"] = float(np.nanmean(core["prim"]["rest"]) * 1e4)
    # off-exchange share variant
    ox = offx_matrix(archive, pan)
    Z = trailing_z(ox["OX"], 1)
    oxs = spread_series(Z, pan["M"], ID, rows, True)
    oxd = oxs["d"][np.isfinite(oxs["d"])]
    ot = mean_test(oxd, T671_BAR, "less", T671_LAG, T671_BLOCK)
    rep["offx"] = {"mean_bp": None if ot["mean"] is None else ot["mean"] * 1e4, "n": ot["n"], "nw_t_vs_bar": ot["nw_t"],
                   "p_nw": ot["p_nw"], "p_bt": ot["p_bt"], "identity_failed": len(ox["status"]["identity_failed"]),
                   "cnms_span": [ox["first"], ox["last"]]}
    rep["not_computed"] = {"earnings_days": "no earnings calendar archived (sec-submissions filings carry no 8-K item codes)",
                           "stocktwits": "intensity bundles from 2025-W43 sample a few dozen symbols: no S&P cross-section"}
    nr = core["prim"]["n_ranked"][ok]
    reason = (f"point-in-time S&P 500 members with archived prices, decisions {dd[0] if n else 'n/a'}..{dd[-1] if n else 'n/a'} "
              f"({n} days, median {int(np.median(nr)) if n else 0} ranked names, top decile floor(n/10)): top AV(t-1) decile "
              f"intraday {_bp(rep['top_intraday_bp'] / 1e4)} vs rest {_bp(rep['rest_intraday_bp'] / 1e4)}, difference "
              f"{_bp(test['mean'])} (NW t vs -10 bp {_s(test['nw_t'])}, p {_f(test['p_nw'], 4)}; CBB p "
              f"{CAL._mc(test['p_bt'], test['draws'])}; Holm bound x6); halves {_bp(h1.mean() if h1.size else None)} / "
              f"{_bp(h2.mean() if h2.size else None)}; t-2 robustness {_bp(rep['rob']['mean_bp'] / 1e4 if rep['rob']['mean_bp'] is not None else None)}; "
              f"coverage {_f(cov['share'], 3)}. Reported: off-exchange-share variant {_bp(rep['offx']['mean_bp'] / 1e4 if rep['offx']['mean_bp'] is not None else None)} "
              f"(n {ot['n']}), bottom-decile placebo {_bp(rep['plac']['mean_bp'] / 1e4 if rep['plac']['mean_bp'] is not None else None)}, "
              f"top-minus-rest overnight-minus-intraday {_bp(rep['onid']['mean_bp'] / 1e4 if rep['onid']['mean_bp'] is not None else None)} "
              f"(top overnight {_bp(rep['top_overnight_bp'] / 1e4 if rep['top_overnight_bp'] is not None else None)}), tradable "
              f"t-1 MOC -> t MOO net {_bp(rep['tradable']['mean_bp'] / 1e4 if rep['tradable']['mean_bp'] is not None else None)} "
              f"(NW t {_s(tr['t'])}); earnings days and the StockTwits variant not computed. SURVIVORSHIP: prices are "
              f"the archive's 901-symbol daily-history set (today's universe); unpriced member tickers "
              f"{cov['unpriced_tickers']}")
    stat = {"n": n, "mean_bp": None if test["mean"] is None else test["mean"] * 1e4, "test": test,
            "holm_adjusted": {"nw": adj_nw, "boot": adj_bt}, "halves_bp": [float(h1.mean() * 1e4) if h1.size else None,
                                                                         float(h2.mean() * 1e4) if h2.size else None],
            "coverage": cov, "reported": rep, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ========================================================================================================= T-662 ==

def ny_bar_table(df) -> dict:
    """{New York day: {'HH:MM' bar start: (open, high, low, close)}} from a 60m frame indexed by UTC bar start."""
    if df is None or len(df) == 0:
        return {}
    idx = df.index.tz_convert("America/New_York")
    dd = idx.strftime("%Y-%m-%d")
    hm = idx.strftime("%H:%M")
    o, h, l, c = (df[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    out: dict = {}
    for k in range(len(df)):
        out.setdefault(dd[k], {})[hm[k]] = (o[k], h[k], l[k], c[k])
    return out


def t662_panel(bars: dict, days: Sequence[str], close: dict, divs: dict, syms: Sequence[str]) -> dict:
    """Day x name arrays on the session calendar ``days``: P(14:30) (close of the 13:30 bar), O(15:30) (open of the
    15:30 bar), official close C(t), prior close C(t-1), dividend D(t), ROD3 = log(P(14:30) / (C(t-1) - D(t))) and r =
    C(t) / O(15:30) - 1; early closes (a 13:00 tick and no 15:30 bar on any name) are flagged. ROD3 uses only bars
    that end by 14:30 and the prior close."""
    days = list(days)
    D, S = len(days), len(syms)
    P1430 = np.full((D, S), np.nan)
    O1530 = np.full((D, S), np.nan)
    C = np.full((D, S), np.nan)
    DIV = np.zeros((D, S))
    tick13 = np.zeros((D, S), bool)
    for j, s in enumerate(syms):
        b = bars.get(s) or {}
        c = np.asarray(close.get(s), float) if close.get(s) is not None else np.full(D, np.nan)
        C[:, j] = c
        dv = divs.get(s) or {}
        for i, d in enumerate(days):
            bd = b.get(d)
            if bd:
                if "13:30" in bd:
                    P1430[i, j] = bd["13:30"][3]
                if "15:30" in bd:
                    O1530[i, j] = bd["15:30"][0]
                tick13[i, j] = "13:00" in bd and "15:30" not in bd
            DIV[i, j] = dv.get(d, 0.0)
    CP = np.vstack([np.full((1, S), np.nan), C[:-1]])
    early = tick13.any(axis=1) & ~np.isfinite(O1530).any(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        base = CP - DIV
        ROD3 = np.where(np.isfinite(P1430) & (P1430 > 0) & np.isfinite(base) & (base > 0), np.log(P1430 / np.where(base > 0, base, 1.0)), np.nan)
        R = np.where(np.isfinite(O1530) & (O1530 > 0) & np.isfinite(C) & (C > 0), C / np.where(O1530 > 0, O1530, 1.0) - 1.0, np.nan)
    elig = np.isfinite(ROD3) & np.isfinite(O1530) & (O1530 > 0) & ~early[:, None]     # known at the 15:30 decision
    valid = elig & np.isfinite(R)
    return {"days": np.asarray(days), "syms": list(syms), "P1430": P1430, "O1530": O1530, "C": C, "CP": CP, "DIV": DIV,
            "ROD3": ROD3, "R": R, "elig": elig, "valid": valid, "early": early}


def quintile_weights(rod3_row: np.ndarray, valid_row: np.ndarray, high: bool = False) -> np.ndarray:
    """The floor(n/5) lowest (``high`` False) or highest ROD3 names among the day's usable names (ties share slots)."""
    n = int((valid_row & np.isfinite(rod3_row)).sum())
    k = n // 5
    return SX.tail_fractions(rod3_row, valid_row, k, high) if k >= 1 else np.zeros(rod3_row.size)


def net_long(r: np.ndarray, entry: float = T662_ENTRY_COST, fee: float = T662_SEC_FEE) -> np.ndarray:
    """Long-leg net return: entry cost, exit at the official close (no spread), Section 31 fee on the sale proceeds."""
    return r - entry - fee * (1.0 + r)


def t662_series(pn: dict, rows: np.ndarray, qqq: Optional[tuple] = None, extra: Optional[dict] = None) -> dict:
    """Daily T-662 series on usable rows: net excess (bottom quintile net minus EW universe gross), long-only net,
    hedged vs QQQ, mirror (top quintile), the Fama-MacBeth slope, and the interaction cells when ``extra`` holds day x
    name DTC and off-exchange arrays."""
    R, ROD, elig = pn["R"], pn["ROD3"], pn["elig"]
    out = {k: [] for k in ("day", "x", "long", "hedged", "mirror", "fm", "n")}
    cells = {k: [] for k in ("dtc_hi", "dtc_lo", "ox_hi", "ox_lo")}
    W = []
    for i in rows:
        v = elig[i]                                   # ranking: ROD3 and the 15:30 entry bar only
        n = int(v.sum())
        vr = v & np.isfinite(R[i])                    # returns: the names that also print an official close
        if n < T662_MIN_NAMES or vr.sum() < T662_MIN_NAMES:
            continue
        w = quintile_weights(ROD[i], v, False)
        wt = quintile_weights(ROD[i], v, True)
        rn = net_long(R[i])
        uni = float(R[i][vr].mean())
        lo = _leg(w, rn)
        out["day"].append(pn["days"][i])
        out["n"].append(n)
        out["x"].append(lo - uni)
        out["long"].append(lo)
        out["mirror"].append(_leg(wt, rn) - uni)
        xs, ys = ROD[i][vr], R[i][vr]
        vx = xs - xs.mean()
        out["fm"].append(float((vx * (ys - ys.mean())).sum() / (vx * vx).sum()) if (vx * vx).sum() > 0 else np.nan)
        if qqq is not None and np.isfinite(qqq[0][i]) and qqq[0][i] > 0 and np.isfinite(qqq[1][i]):
            rq = qqq[1][i] / qqq[0][i] - 1.0
            out["hedged"].append(lo - (rq + T662_ENTRY_COST + T662_SEC_FEE))
        else:
            out["hedged"].append(np.nan)
        W.append((i, w))
        if extra is not None:
            for key, X in (("dtc", extra.get("dtc")), ("ox", extra.get("ox"))):
                if X is None:
                    continue
                xv = X[i]
                ok = v & np.isfinite(xv)
                if ok.sum() < 4:
                    cells[key + "_hi"].append(np.nan)
                    cells[key + "_lo"].append(np.nan)
                    continue
                med = float(np.median(xv[ok]))
                hi = np.where(ok & (xv >= med), w, 0.0)
                lo_w = np.where(ok & (xv < med), w, 0.0)
                cells[key + "_hi"].append(_leg(hi, rn) - uni if hi.sum() > 0 else np.nan)
                cells[key + "_lo"].append(_leg(lo_w, rn) - uni if lo_w.sum() > 0 else np.nan)
    res = {k: np.asarray(v) for k, v in out.items()}
    res["cells"] = {k: np.asarray(v, float) for k, v in cells.items()}
    res["weights"] = W
    return res


def t662_placebo(pn: dict, rows_used: Sequence[int], draws: int = T662_PLACEBO, seed: int = SEED) -> np.ndarray:
    """Mean net excess of a random floor(n/5) names a day over the used rows, one value per draw."""
    rng = np.random.default_rng(seed)
    R, valid = pn["R"], pn["valid"]
    tot = np.zeros(draws)
    for i in rows_used:
        v = np.flatnonzero(valid[i])
        k = v.size // 5
        rn = net_long(R[i][v])
        uni = R[i][v].mean()
        pick = np.argsort(rng.random((draws, v.size)), axis=1)[:, :k]
        tot += rn[pick].mean(axis=1) - uni
    return tot / max(1, len(rows_used))


def _load_60m(sym: str):
    try:
        from mandel.ml.features import load_bars
    except Exception:  # pragma: no cover - optional local data
        return None
    try:
        return load_bars("60m", sym)
    except Exception:  # pragma: no cover
        return None


def finra_rows(archive, fsyms: frozenset) -> list:
    """Every archived FINRA short-interest release in settlement order: {settle, av (epoch of its available_at, the
    latest over its rows), rows {FINRA symbol: (issueName, short interest, ADV)}} for the requested symbols."""
    def load():
        out = []
        for nm in SX._entry_names(archive, SX.FINRA_PREFIX):
            av, rows = None, {}
            for r in SX._stream(archive, nm):
                try:
                    a = SX._ts(r["available_at"])
                    av = a if av is None else max(av, a)
                except (KeyError, TypeError, ValueError):
                    pass
                v = r.get("value") or {}
                sym = (v.get("symbolCode") or "").strip().upper()
                if sym in fsyms:
                    rows[sym] = (v.get("issueName") or "", SX._num(v.get("currentShortPositionQuantity")),
                                 SX._num(v.get("averageDailyVolumeQuantity")))
            if av is not None:
                out.append({"settle": nm[len(SX.FINRA_PREFIX):], "av": av, "rows": rows})
        return out
    return CAL._cached(archive, ("b13ib_finra", fsyms), load)


def finra_sym(t: str) -> str:
    """FINRA short-interest spelling of an index ticker (BRK.B -> BRKB)."""
    return str(t).replace(".", "").replace("/", "").replace("-", "").strip().upper()


def dtc_known(releases: list, open_ts: np.ndarray, fsyms: Sequence[str]) -> np.ndarray:
    """Day x symbol days-to-cover of the latest release whose available_at is before the day's 09:30 ET open."""
    D = open_ts.size
    out = np.full((D, len(fsyms)), np.nan)
    rel = sorted(releases, key=lambda r: r["av"])
    avs = np.array([r["av"] for r in rel])
    for i in range(D):
        k = int(np.searchsorted(avs, open_ts[i], side="left")) - 1
        if k < 0:
            continue
        rw = rel[k]["rows"]
        for j, s in enumerate(fsyms):
            row = rw.get(s)
            if row and np.isfinite(row[1]) and row[1] >= 0 and np.isfinite(row[2]) and row[2] > 0:
                out[i, j] = row[1] / row[2]
    return out


def t662_data(archive) -> dict:
    """The T-662 day x name panel (local 60m bars + daily-history closes + daily-events dividends) on SPY's sessions,
    QQQ's 15:30 open and close, and the interaction inputs (DTC known at the open; CNMS off-exchange share of t-1)."""
    def load():
        cal = SX._sessions(archive)
        i0 = max(0, cal.on_or_after(T662_START) - 1)
        days = np.array([d for d in cal.days[i0:] if d <= T662_END])
        syms = list(T662_SYMS)
        bars, missing = {}, []
        for s in syms + ["QQQ"]:
            df = _load_60m(s)
            if df is None or len(df) == 0:
                missing.append(s)
                continue
            bars[s] = ny_bar_table(df)
        sl = _panel_slice(archive, days, syms + ["QQQ"], ("close", "volume"))
        close = {s: sl["close"][:, j] for j, s in enumerate(syms)}
        divs, F = {}, np.ones((len(days), len(syms)))
        for j, s in enumerate(syms):
            dv, sp = _events(archive, s)
            divs[s] = dv
            F[:, j] = split_after(days, sp)
        pn = t662_panel(bars, days.tolist(), close, divs, syms)
        qb = bars.get("QQQ") or {}
        q_o = np.array([(qb.get(d) or {}).get("15:30", (np.nan,))[0] for d in days.tolist()], float)
        q_c = sl["close"][:, -1]
        fs = [finra_sym(s) for s in syms]
        rel = finra_rows(archive, frozenset(fs))
        open_ts = np.array([SX._et_ts(d, 9, 30) for d in days.tolist()], float)
        dtc = dtc_known(rel, open_ts, fs)
        ox = None
        try:
            from mandel.experiments import batch13_short_a as SA
            Cn = SA.cnms_data(archive)
            cpos = {s: k for k, s in enumerate(Cn["syms"])}
            dpos = {d: k for k, d in enumerate(Cn["iso"])}
            ox = np.full((len(days), len(syms)), np.nan)
            V = sl["volume"][:, :-1]
            for j, s in enumerate(syms):
                k = cpos.get(s)
                if k is None:
                    continue
                for i in range(1, len(days)):
                    r = dpos.get(days[i - 1])
                    if r is None:
                        continue
                    tv = Cn["TV"][r, k]
                    yv = V[i - 1, j] / F[i - 1, j]
                    if np.isfinite(tv) and tv > 0 and np.isfinite(yv) and yv > 0:
                        ox[i, j] = tv / yv
        except Exception:  # pragma: no cover - reported-only input
            ox = None
        return {"pn": pn, "qqq": (q_o, q_c), "missing": missing, "dtc": dtc, "ox": ox}
    return CAL._cached(archive, ("b13ib_t662",), load)


def b13_intraday_b_eod_reversal(archive):
    """T-662."""
    names = [B7C.dh(s) for s in T662_SYMS] + [SX.de(s) for s in T662_SYMS] + [QQQ_B, SPY_B]
    miss = _missing(archive, names)
    if miss:
        return miss
    data = t662_data(archive)
    if data["missing"] and set(data["missing"]) - {"QQQ"}:
        return _out({"missing_60m": data["missing"]}, 0, "inconclusive",
                    f"local 60m bars missing for {data['missing']} (rule 9): the 28-stock cross-section cannot be built")
    pn = data["pn"]
    days = pn["days"]
    rows = np.flatnonzero((days >= T662_START) & (days <= T662_END))
    S = t662_series(pn, rows, data["qqq"], {"dtc": data["dtc"], "ox": data["ox"]})
    x = S["x"]
    n = int(x.size)
    dd = S["day"]
    test = mean_test(x, 0.0, "greater", T662_LAG, T662_BLOCK, m=T662_CELLS)
    # deflated p read three ways (rule 11): 1 - DSR(6 trials), Bonferroni x 6 on the NW and on the CBB p
    dsr = float(deflated_sharpe_ratio(x, n_trials=T662_CELLS)) if n >= 8 else None
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1)) if n >= 8 else None
    p_dsr = None if dsr is None else 1.0 - dsr
    b_nw = None if test["p_nw"] is None else min(1.0, T662_CELLS * test["p_nw"])
    b_bt = None if test["p_bt"] is None else min(1.0, T662_CELLS * test["p_bt"])
    point = test["mean"] is not None and test["mean"] > 0
    nw_opp = test["p_nw_opp"] is not None and test["p_nw_opp"] < ALPHA
    bt_opp = test["p_bt_opp"] is not None and CAL.decide_p(test["p_bt_opp"], test["draws"]) is True
    sub = [(f"1 - DSR(6 trials) {_f(p_dsr, 4)} (PSR vs 0 {_f(psr0, 4)})",
            False if not point else (None if p_dsr is None else bool(p_dsr < ALPHA)), bool(psr0 is not None and psr0 <= ALPHA)),
           (f"Bonferroni x6 Newey-West 5 lags p {_f(b_nw, 4)} (t {_s(test['nw_t'])})",
            False if not point else (None if test["p_nw"] is None else bool(test["p_nw"] < ALPHA / T662_CELLS)), nw_opp),
           (f"Bonferroni x6 studentized CBB p {_f(b_bt, 4)} (raw {CAL._mc(test['p_bt'], test['draws'])})",
            False if not point else (None if test["p_bt"] is None else CAL.decide_p(test["p_bt"], test["draws"], ALPHA / T662_CELLS)),
            bt_opp)]
    r1 = all_constructions(sub, f"mean net excess {_bp(test['mean'])} > 0 with one-sided deflated p < 0.05 (6 cells)")
    h1, h2 = x[dd < T662_SPLIT], x[dd >= T662_SPLIT]
    fm = S["fm"][np.isfinite(S["fm"])]
    fmr = nw(fm, T662_LAG)
    r_fm = (f"Fama-MacBeth slope of r(15:30 -> close) on ROD3 {_s(fmr['mean'], 4)} < 0 (NW t {_s(fmr['t'])})",
            None if fmr["mean"] is None else bool(fmr["mean"] < 0), bool(fmr["t"] is not None and fmr["t"] >= 1.959964))
    rows_c = CAL._undecided([r1, sign_row(f"positive before {T662_SPLIT[:7]}", h1, True, T662_LAG),
                             sign_row(f"positive from {T662_SPLIT[:7]}", h2, True, T662_LAG), r_fm])
    v, why, crit = _judge(rows_c, n, T662_MIN_N, "days")
    rep = {}
    for key in ("long", "hedged", "mirror"):
        r = nw(S[key], T662_LAG)
        rep[key] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    used = [i for i, _ in S["weights"]]
    pl = t662_placebo(pn, used)
    rep["placebo"] = {"mean_bp": float(pl.mean() * 1e4), "p05_bp": float(np.quantile(pl, 0.05) * 1e4),
                      "p95_bp": float(np.quantile(pl, 0.95) * 1e4),
                      "share_ge_primary": float((pl >= (test["mean"] or 0.0)).mean())}
    for key, arr in S["cells"].items():
        r = nw(arr, T662_LAG)
        rep[f"cell_{key}"] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    early = int(pn["early"][rows].sum())
    gross = float((S["x"] + T662_ENTRY_COST).mean() * 1e4) if n else None
    reason = (f"28 local-60m single stocks, {dd[0] if n else 'n/a'}..{dd[-1] if n else 'n/a'} ({n} days, {early} early closes "
              f"excluded, median {int(np.median(S['n'])) if n else 0} names, bottom quintile floor(n/5)): bottom-ROD3 quintile "
              f"15:30 -> official close net excess over the EW universe {_bp(test['mean'])} (gross about {_bp(gross / 1e4 if gross is not None else None)}; "
              f"NW t {_s(test['nw_t'])}, p {_f(test['p_nw'], 4)}; CBB p {CAL._mc(test['p_bt'], test['draws'])}; 1 - DSR(6) "
              f"{_f(p_dsr, 4)}); halves {_bp(h1.mean() if h1.size else None)} / {_bp(h2.mean() if h2.size else None)}; "
              f"FM slope {_s(fmr['mean'], 4)} (t {_s(fmr['t'])}). Reported: long-only net {_bp(rep['long']['mean_bp'] / 1e4 if rep['long']['mean_bp'] is not None else None)}, "
              f"hedged vs QQQ {_bp(rep['hedged']['mean_bp'] / 1e4 if rep['hedged']['mean_bp'] is not None else None)} (t {_s(rep['hedged']['nw_t'])}), "
              f"mirror top quintile {_bp(rep['mirror']['mean_bp'] / 1e4 if rep['mirror']['mean_bp'] is not None else None)}, random-quintile placebo "
              f"{rep['placebo']['mean_bp']:+.2f} bp (5-95% {rep['placebo']['p05_bp']:+.2f}..{rep['placebo']['p95_bp']:+.2f}); "
              f"DTC cells hi/lo {_s(rep['cell_dtc_hi']['mean_bp'])}/{_s(rep['cell_dtc_lo']['mean_bp'])} bp, off-exchange cells "
              f"hi/lo {_s(rep['cell_ox_hi']['mean_bp'])}/{_s(rep['cell_ox_lo']['mean_bp'])} bp (about 3 names a cell, not judged). "
              f"The 28 names were chosen with hindsight (a pilot of the 500-name test)")
    stat = {"n": n, "mean_bp": None if test["mean"] is None else test["mean"] * 1e4, "test": test, "dsr6": dsr,
            "p_deflated_dsr": p_dsr, "p_bonferroni_nw": b_nw, "p_bonferroni_boot": b_bt,
            "halves_bp": [float(h1.mean() * 1e4) if h1.size else None, float(h2.mean() * 1e4) if h2.size else None],
            "fm": fmr, "early_closes": early, "reported": rep, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ========================================================================================================= T-663 ==

def entry_rows(open_ts: np.ndarray, avs: Sequence[float]) -> np.ndarray:
    """Index of the first session whose 09:30 ET open is strictly after each available_at."""
    return np.searchsorted(open_ts, np.asarray(avs, float), side="right")


def ivol_at(Rs: np.ndarray, Rm: np.ndarray, s: int, win: int = T663_IVOL_WIN, min_n: int = T663_IVOL_MIN) -> np.ndarray:
    """Per name: the sd (ddof 2) of the OLS residuals of its daily returns in rows s-win .. s-1 on the market's, over
    the rows where both are finite (>= ``min_n``); uses nothing from row s on."""
    lo = s - win
    if lo < 0:
        return np.full(Rs.shape[1], np.nan)
    Y = Rs[lo:s]
    x = Rm[lo:s][:, None]
    ok = np.isfinite(Y) & np.isfinite(x)
    n = ok.sum(axis=0).astype(float)
    xv = np.where(ok, x, 0.0)
    yv = np.where(ok, Y, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mx = xv.sum(axis=0) / n
        my = yv.sum(axis=0) / n
        sxx = (np.where(ok, (x - mx) ** 2, 0.0)).sum(axis=0)
        sxy = (np.where(ok, (x - mx) * (Y - my), 0.0)).sum(axis=0)
        b = sxy / sxx
        e = np.where(ok, Y - my - b * (x - mx), 0.0)
        sd = np.sqrt((e * e).sum(axis=0) / (n - 2))
    return np.where((n >= min_n) & np.isfinite(sd), sd, np.nan)


def t663_formations(pan: dict, releases: list) -> list:
    """One formation per release: entry row s (first open after available_at), DTC per accepted member at s with a
    close at s-1 and an identity-checked FINRA row, and the IVOL scores at s."""
    D = len(pan["days"])
    avs = [r["av"] for r in releases]
    ss = entry_rows(pan["open_ts"], avs)
    syms = pan["syms"]
    fs = [finra_sym(y.replace("-", ".")) for y in syms]
    A = pan["A"]
    with np.errstate(invalid="ignore", divide="ignore"):
        Rs = np.vstack([np.full((1, A.shape[1]), np.nan), A[1:] / A[:-1] - 1.0])
        sa = pan["spy_a"]
        Rm = np.concatenate([[np.nan], sa[1:] / sa[:-1] - 1.0])
    from mandel.experiments.batch13_short_b import ident_ok
    out = []
    for rel, s in zip(releases, ss):
        s = int(s)
        if s < 1 or s >= D:
            continue
        elig_base = pan["M"][s] & np.isfinite(pan["C"][s - 1]) & (pan["C"][s - 1] > 0)
        dtc = np.full(len(syms), np.nan)
        bad = 0
        for j in np.flatnonzero(elig_base):
            row = rel["rows"].get(fs[j])
            if not row:
                continue
            nm, si, adv = row
            if not (np.isfinite(si) and si >= 0 and np.isfinite(adv) and adv > 0):
                continue
            if not ident_ok(nm, pan["alias"].get(syms[j], []), fs[j]):
                bad += 1
                continue
            dtc[j] = si / adv
        iv = ivol_at(Rs, Rm, s)
        out.append({"settle": rel["settle"], "s": s, "dtc": dtc, "ivol": np.where(elig_base, iv, np.nan),
                    "elig": elig_base, "identity_rejected": bad})
    out.sort(key=lambda f: f["s"])
    ded = []
    for f in out:                                   # two releases entering at one open: the later settlement holds
        if ded and ded[-1]["s"] == f["s"]:
            ded[-1] = f
        else:
            ded.append(f)
    return ded


def rank_bucket(score: np.ndarray, elig: np.ndarray, lo_q: float, hi_q: float) -> np.ndarray:
    """0/1 weights of the eligible names whose rank percentile (rank - 0.5) / n lies in [lo_q, hi_q)."""
    ok = elig & np.isfinite(score)
    w = np.zeros(score.size)
    idx = np.flatnonzero(ok)
    if idx.size < 10:
        return w
    order = idx[np.argsort(score[idx], kind="stable")]
    pct = (np.arange(order.size) + 0.5) / order.size
    w[order[(pct >= lo_q) & (pct < hi_q)]] = 1.0
    return w


def hold_series(D: int, forms: list, key: str, ID: np.ndarray, ON: np.ndarray, mode: str = "spread") -> dict:
    """Daily overnight and intraday components of a formation-held portfolio: the intraday of row t from the sets
    entered at or before the t open, the overnight into row t from the sets held over that night (entered at or before
    row t-1). ``mode`` 'spread' = high decile minus low decile; 'placebo' = decile 6 minus decile 5 by rank."""
    W_hi, W_lo = [], []
    for f in forms:
        sc = f[key]
        el = f["elig"] & np.isfinite(sc)
        if mode == "spread":
            k = int(el.sum()) // 10
            if k >= 1:
                W_hi.append(SX.tail_fractions(sc, el, k, True))
                W_lo.append(SX.tail_fractions(sc, el, k, False))
            else:
                W_hi.append(np.zeros(sc.size))
                W_lo.append(np.zeros(sc.size))
        else:
            W_hi.append(rank_bucket(sc, el, 0.5, 0.6))
            W_lo.append(rank_bucket(sc, el, 0.4, 0.5))
    starts = np.array([f["s"] for f in forms], int)
    on = np.full(D, np.nan)
    idd = np.full(D, np.nan)
    hi_id = np.full(D, np.nan)
    for t in range(D):
        k = int(np.searchsorted(starts, t, side="right")) - 1          # set held during session t
        if k >= 0 and W_hi[k].sum() > 0:
            a, b = _leg(W_hi[k], ID[t]), _leg(W_lo[k], ID[t])
            idd[t] = a - b
            hi_id[t] = a
        if t >= 1:
            k2 = int(np.searchsorted(starts, t - 1, side="right")) - 1  # set held over the night into t
            if k2 >= 0 and W_hi[k2].sum() > 0:
                on[t] = _leg(W_hi[k2], ON[t]) - _leg(W_lo[k2], ON[t])
    return {"on": on, "id": idd, "d": on - idd, "hi_id": hi_id}


def b13_intraday_b_dtc_overnight(archive):
    """T-663."""
    miss = _missing(archive, [SPY_B, FJA_B, CHG_B, SI_FIRST_B])
    if miss:
        return miss
    pan = sp_panel(archive)
    days = pan["days"]
    D = len(days)
    fs = frozenset(finra_sym(y.replace("-", ".")) for y in pan["syms"])
    rel = finra_rows(archive, fs)
    forms = t663_formations(pan, rel)
    ID, ON = day_returns(pan)
    win = (days >= T663_START) & (days <= T663_END)
    fam = {}
    for key in ("dtc", "ivol"):
        h = hold_series(D, forms, key, ID, ON)
        ok = win & np.isfinite(h["d"])
        fam[key] = {"h": h, "ok": ok, "x": h["d"][ok], "days": days[ok],
                    "test": mean_test(h["d"][ok], T663_BAR, "greater", T663_LAG, T663_BLOCK, m=2)}
    T, Ti = fam["dtc"]["test"], fam["ivol"]["test"]
    dn = holm_decide([T["p_nw"], Ti["p_nw"]], [None, None])
    db = holm_decide([T["p_bt"], Ti["p_bt"]], [T["draws"], Ti["draws"]])
    an = holm_adjusted([T["p_nw"], Ti["p_nw"]])
    ab = holm_adjusted([T["p_bt"], Ti["p_bt"]])
    x, dd = fam["dtc"]["x"], fam["dtc"]["days"]
    n = int(x.size)
    h1 = x[dd < T663_SPLIT]
    h2 = x[dd >= T663_SPLIT]
    ex = x[~((dd >= T663_EXCL[0]) & (dd <= T663_EXCL[1]))]
    cov = coverage(pan, T663_START, T663_END)
    cov_ok = None if cov["share"] is None or cov["share"] < COVERAGE else True
    rows_c = [sig_row(f"DTC spread overnight-minus-intraday {_bp(T['mean'])} > 2 bp/day with Holm (2 members) one-sided p < 0.05",
                      T, dn[0], db[0], an[0], ab[0]),
              sign_row("positive in 2018-2021", h1, True, T663_LAG),
              sign_row("positive in 2022-2026", h2, True, T663_LAG),
              sign_row("positive without Jan-Mar 2021", ex, True, T663_LAG),
              (f"coverage gate: {_f(cov['share'], 4)} of {cov['member_days']} member-days priced (>= 0.90)", cov_ok, False)]
    rows_c = CAL._undecided(rows_c)
    v, why, crit = _judge(rows_c, n, T663_MIN_N, "days")
    h = fam["dtc"]["h"]
    ok = fam["dtc"]["ok"]
    rep = {"overnight_spread_bp": float(np.nanmean(h["on"][ok]) * 1e4), "intraday_spread_bp": float(np.nanmean(h["id"][ok]) * 1e4),
           "high_dtc_intraday_bp": float(np.nanmean(h["hi_id"][ok]) * 1e4),
           "two_sided_p_nw": None if T["p_nw"] is None else min(1.0, 2 * min(T["p_nw"], T["p_nw_opp"])),
           "ivol": {"mean_bp": None if Ti["mean"] is None else Ti["mean"] * 1e4, "nw_t_vs_bar": Ti["nw_t"], "p_nw": Ti["p_nw"],
                    "p_bt": Ti["p_bt"], "holm_nw": an[1], "n": Ti["n"]},
           "formations": len(forms), "identity_rejected": int(sum(f["identity_rejected"] for f in forms)),
           "median_dtc_names": int(np.median([int(np.isfinite(f["dtc"]).sum()) for f in forms])) if forms else 0}
    pl = hold_series(D, forms, "dtc", ID, ON, mode="placebo")
    pr = nw(pl["d"][win & np.isfinite(pl["d"])], T663_LAG)
    rep["placebo_middle"] = {"mean_bp": None if pr["mean"] is None else pr["mean"] * 1e4, "nw_t": pr["t"], "n": pr["n"]}
    rep["value_weighted"] = "not computed (no point-in-time share counts wired here; reported-only)"
    try:
        t6 = t662_data(archive)
        pn = t6["pn"]
        dtc28 = t6["dtc"]
        dif = []
        for i in np.flatnonzero((pn["days"] >= T662_START) & (pn["days"] <= T663_END)):
            okk = np.isfinite(pn["R"][i]) & np.isfinite(dtc28[i]) & ~pn["early"][i]
            if okk.sum() < 6:
                continue
            med = np.median(dtc28[i][okk])
            hi = okk & (dtc28[i] >= med)
            lo = okk & (dtc28[i] < med)
            if hi.any() and lo.any():
                dif.append(pn["R"][i][hi].mean() - pn["R"][i][lo].mean())
        rr = nw(np.asarray(dif), 5)
        rep["desc_28_last_half_hour_hi_minus_lo_dtc_bp"] = {"mean_bp": None if rr["mean"] is None else rr["mean"] * 1e4,
                                                            "nw_t": rr["t"], "n": rr["n"]}
    except Exception as e:  # pragma: no cover - descriptive only
        rep["desc_28_last_half_hour_hi_minus_lo_dtc_bp"] = f"not computed: {e}"
    desc = rep["desc_28_last_half_hour_hi_minus_lo_dtc_bp"]
    reason = (f"point-in-time S&P 500 members with archived prices, {dd[0] if n else 'n/a'}..{dd[-1] if n else 'n/a'} ({n} days, "
              f"{len(forms)} FINRA formations, median {rep['median_dtc_names']} names with a DTC, deciles floor(n/10)): "
              f"high-minus-low DTC overnight {_bp(rep['overnight_spread_bp'] / 1e4)}, intraday {_bp(rep['intraday_spread_bp'] / 1e4)}, "
              f"overnight-minus-intraday {_bp(T['mean'])}/day (NW 10 lags t vs 2 bp {_s(T['nw_t'])}, p {_f(T['p_nw'], 4)}, Holm "
              f"{_f(an[0], 4)}; CBB p {CAL._mc(T['p_bt'], T['draws'])}); 2018-2021 {_bp(h1.mean() if h1.size else None)}, 2022-2026 "
              f"{_bp(h2.mean() if h2.size else None)}, ex Jan-Mar 2021 {_bp(ex.mean() if ex.size else None)}; coverage "
              f"{_f(cov['share'], 3)}. IVOL member {_bp(Ti['mean'])} (t vs 2 bp {_s(Ti['nw_t'])}). Reported: high-DTC intraday "
              f"leg {_bp(rep['high_dtc_intraday_bp'] / 1e4)}/day (an intraday short must clear about 4 bp/day plus the locate), "
              f"middle-decile placebo {_bp(rep['placebo_middle']['mean_bp'] / 1e4 if rep['placebo_middle']['mean_bp'] is not None else None)}, "
              f"two-sided p {_f(rep['two_sided_p_nw'], 4)}, 28-stock 15:30->close high-minus-low DTC "
              f"{_s(desc['mean_bp']) if isinstance(desc, dict) else 'n/a'} bp; value-weighted not computed. SURVIVORSHIP: prices are "
              f"the archive's 901-symbol daily-history set (today's universe); unpriced member tickers {cov['unpriced_tickers']}")
    stat = {"n": n, "test": T, "test_ivol": Ti, "holm_nw": an, "holm_boot": ab,
            "halves_bp": [float(h1.mean() * 1e4) if h1.size else None, float(h2.mean() * 1e4) if h2.size else None],
            "ex_squeeze_bp": float(ex.mean() * 1e4) if ex.size else None, "coverage": cov, "reported": rep, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ========================================================================================================= T-665 ==

class HourSeries:
    """A 60m bar series on a whole-UTC-hour grid: presence, staleness (open = high = low = close) and window returns."""

    def __init__(self, t, o, h, l, c):
        t = np.asarray(t, np.int64)
        keep = (t % 3600) == 0
        t, o, h, l, c = t[keep], np.asarray(o, float)[keep], np.asarray(h, float)[keep], np.asarray(l, float)[keep], np.asarray(c, float)[keep]
        self.base = int(t.min()) if t.size else 0
        N = int((t.max() - self.base) // 3600 + 1) if t.size else 0
        k = (t - self.base) // 3600
        self.o = np.full(N, np.nan)
        self.c = np.full(N, np.nan)
        self.present = np.zeros(N, bool)
        self.stale = np.zeros(N, bool)
        good = np.isfinite(o) & np.isfinite(c) & (o > 0) & (c > 0)
        self.o[k[good]] = o[good]
        self.c[k[good]] = c[good]
        self.present[k[good]] = True
        self.stale[k[good]] = (o[good] == h[good]) & (h[good] == l[good]) & (l[good] == c[good])
        self.cp = np.concatenate([[0], np.cumsum(self.present)])
        self.cs = np.concatenate([[0], np.cumsum(self.stale)])
        self.N = N

    @classmethod
    def from_frame(cls, df):
        t = np.asarray(df.index.as_unit("s").asi8, np.int64)          # Yahoo bars load as datetime64[s]
        return cls(t, df["o"].to_numpy(float), df["h"].to_numpy(float), df["l"].to_numpy(float), df["c"].to_numpy(float))

    def window(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """log(close of the bar stamped b - 1h / open of the bar stamped a) for windows [a, b) (epoch seconds), NaN
        unless every bar in the window is present and none is stale. Uses no bar stamped at or after b."""
        a = np.asarray(a, np.int64)
        b = np.asarray(b, np.int64)
        ia = (a - self.base) // 3600
        ib = (b - self.base) // 3600
        out = np.full(a.size, np.nan)
        ok = (ia >= 0) & (ib <= self.N) & (ib > ia)
        if not ok.any():
            return out
        ia_, ib_ = ia[ok], ib[ok]
        full = (self.cp[ib_] - self.cp[ia_]) == (ib_ - ia_)
        fresh = (self.cs[ib_] - self.cs[ia_]) == 0
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.log(self.c[np.minimum(ib_ - 1, self.N - 1)] / self.o[np.minimum(ia_, self.N - 1)])
        out[ok] = np.where(full & fresh, r, np.nan)
        return out


def edge_ts(day: date, spec: tuple, shift_h: int = 0) -> int:
    tz, hh, off = spec
    d = day + timedelta(days=off)
    return int(datetime(d.year, d.month, d.day, hh, 0, tzinfo=ZoneInfo(tz)).timestamp()) + shift_h * 3600


def fx_days(start: str = T665_START, end: str = T665_END) -> list:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out, d = [], d0
    while d <= d1:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def window_table(series: dict, days: Sequence[date], win: tuple, shift_h: int = 0) -> np.ndarray:
    """Day x currency sign-aligned (USD up = positive) log returns of window ``win`` [(start spec), (end spec)]."""
    a = np.array([edge_ts(d, win[0], shift_h) for d in days], np.int64)
    b = np.array([edge_ts(d, win[1], shift_h) for d in days], np.int64)
    out = np.full((len(days), len(T665_CCY)), np.nan)
    for j, (ccy, _, sgn, _) in enumerate(T665_CCY):
        hs = series.get(ccy)
        if hs is not None:
            out[:, j] = sgn * hs.window(a, b)
    return out


def fix_stats(pre: np.ndarray, post: np.ndarray, days: Sequence[str]) -> dict:
    """Basket (pre - post) on the days every currency is complete in both windows, per-currency means and counts."""
    dc = pre - post
    allv = np.isfinite(dc).all(axis=1)
    per = {}
    for j, (ccy, *_rest) in enumerate(T665_CCY):
        v = dc[:, j][np.isfinite(dc[:, j])]
        per[ccy] = {"mean_bp": float(v.mean() * 1e4) if v.size else None, "n": int(v.size),
                    "nw_t": nw(v, T665_LAG)["t"]}
    dd = np.asarray([str(d) for d in days])
    return {"x": dc[allv].mean(axis=1), "days": dd[allv], "per": per, "dc": dc, "allv": allv,
            "pre": pre[allv].mean(axis=1), "post": post[allv].mean(axis=1)}


def _month_end_flags(days: Sequence[str]) -> np.ndarray:
    """The last two weekdays of each calendar month."""
    by: dict = {}
    for i, d in enumerate(days):
        by.setdefault(d[:7], []).append(i)
    f = np.zeros(len(days), bool)
    for idx in by.values():
        f[idx[-2:]] = True
    return f


def fred_check(archive, series: dict) -> dict:
    """Correlation of the daily change of the 12:00 ET bar open with the FRED noon rate's, per currency."""
    by: dict = {}
    for r in SX._rows(archive, FX_B):
        v = r.get("value") or {}
        if v.get("ccy") and v.get("usd_per_unit"):
            try:
                by.setdefault(v["ccy"], {})[v["day"]] = float(v["usd_per_unit"])
            except (TypeError, ValueError):
                continue
    out = {}
    days = [d for d in fx_days()]
    for ccy, _, sgn, _ in T665_CCY:
        hs = series.get(ccy)
        fr = by.get(ccy)
        if hs is None or not fr:
            out[ccy] = None
            continue
        ts = np.array([int(datetime(d.year, d.month, d.day, 12, 0, tzinfo=NY).timestamp()) for d in days], np.int64)
        k = (ts - hs.base) // 3600
        okk = (k >= 0) & (k < hs.N)
        px = np.full(len(days), np.nan)
        px[okk] = np.where(hs.present[k[okk]], hs.o[k[okk]], np.nan)
        usd_per = px if sgn < 0 else 1.0 / px        # EURUSD-style quotes are USD per unit already
        f = np.array([fr.get(d.isoformat(), np.nan) for d in days])
        a, b = np.log(usd_per), np.log(f)
        da, db = np.diff(a), np.diff(b)
        m = np.isfinite(da) & np.isfinite(db)
        out[ccy] = {"corr": float(np.corrcoef(da[m], db[m])[0, 1]) if m.sum() > 10 else None, "n": int(m.sum()),
                    "median_abs_level_diff_bp": float(np.nanmedian(np.abs(a - b)) * 1e4) if np.isfinite(a - b).any() else None}
    return out


def b13_intraday_b_usd_fix(archive):
    """T-665."""
    miss = _missing(archive, [FX_B])
    if miss:
        return miss
    series, missing = {}, []
    for ccy, sym, _, _ in T665_CCY:
        df = _load_60m(sym)
        if df is None or len(df) == 0:
            missing.append(sym)
            continue
        series[ccy] = HourSeries.from_frame(df)
    if missing:
        return _out({"missing_60m": missing}, 0, "inconclusive", f"local 60m FX bars missing for {missing} (rule 9)")
    days = fx_days()
    sdays = [d.isoformat() for d in days]
    tab = {k: window_table(series, days, w) for k, w in (("preT", PRE_T), ("postT", POST_T), ("preE", PRE_E),
                                                          ("postL", POST_L), ("EL", E_L))}
    fx = {"T": fix_stats(tab["preT"], tab["postT"], sdays), "E": fix_stats(tab["preE"], tab["postL"], sdays)}
    for k in ("T", "E"):
        f = fx[k]
        f["test"] = mean_test(f["x"], 0.0, "greater", T665_LAG, T665_BLOCK, m=2)
    TT, TE = fx["T"]["test"], fx["E"]["test"]
    dn = holm_decide([TT["p_nw"], TE["p_nw"]], [None, None])
    db = holm_decide([TT["p_bt"], TE["p_bt"]], [TT["draws"], TE["draws"]])
    an = holm_adjusted([TT["p_nw"], TE["p_nw"]])
    ab = holm_adjusted([TT["p_bt"], TE["p_bt"]])
    rows_c = []
    for j, (k, lab) in enumerate((("T", "Tokyo pre-T minus post-T"), ("E", "Europe pre-E minus post-L"))):
        f = fx[k]
        T_ = f["test"]
        rows_c.append(sig_row(f"{lab} {_bp(T_['mean'])} > 0 with Holm (2 fixes) one-sided p < 0.05", T_, dn[j], db[j], an[j], ab[j]))
        dd = f["days"]
        med = dd[len(dd) // 2] if len(dd) else "9999"
        f["split"] = med
        rows_c.append(sign_row(f"{lab} positive in the first half (< {med})", f["x"][dd < med], True, T665_LAG))
        rows_c.append(sign_row(f"{lab} positive in the second half (>= {med})", f["x"][dd >= med], True, T665_LAG))
        pos = sum(1 for c in f["per"].values() if c["mean_bp"] is not None and c["mean_bp"] > 0)
        neg_sig = sum(1 for c in f["per"].values() if c["nw_t"] is not None and c["nw_t"] <= -1.959964)
        f["n_pos"] = pos
        rows_c.append((f"{lab}: at least {T665_NEED} of 7 currencies positive ({pos}; "
                       + ", ".join(f"{c} {_s(v['mean_bp'])}" for c, v in f["per"].items()) + ")",
                       bool(pos >= T665_NEED), bool(len(T665_CCY) - neg_sig < T665_NEED)))
    rows_c = CAL._undecided(rows_c)
    nT, nE = int(fx["T"]["x"].size), int(fx["E"]["x"].size)
    n = min(nT, nE)
    v, why, crit = _judge(rows_c, n, T665_MIN_N, "days (the smaller fix)")
    # reported
    rep = {}
    mondays = sum(1 for d in days if d.weekday() == 0)
    rep["tokyo_mondays_excluded"] = mondays
    cost = np.array([c[3] for c in T665_CCY])
    for k in ("T", "E"):
        f = fx[k]
        net = (f["dc"][f["allv"]] - 4 * cost[None, :]).mean(axis=1)
        r = nw(net, T665_LAG)
        rep[f"rule_net_{k}"] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
        jp = np.array([d in JP_HOLIDAYS for d in f["days"]], bool)
        me = _month_end_flags(sdays)
        spos = {d: i for i, d in enumerate(sdays)}
        mef = np.array([me[spos[d]] for d in f["days"]], bool)
        rep[f"subsets_{k}"] = {"jp_holiday_bp": float(f["x"][jp].mean() * 1e4) if jp.any() else None, "n_jp": int(jp.sum()),
                               "month_end_bp": float(f["x"][mef].mean() * 1e4) if mef.any() else None, "n_me": int(mef.sum()),
                               "ex_jp_ex_me_bp": float(f["x"][~jp & ~mef].mean() * 1e4) if (~jp & ~mef).any() else None}
        for sh in (6, -6):
            w_pre = PRE_T if k == "T" else PRE_E
            w_post = POST_T if k == "T" else POST_L
            ps = fix_stats(window_table(series, days, w_pre, sh), window_table(series, days, w_post, sh), sdays)
            r = nw(ps["x"], T665_LAG)
            rep[f"placebo_{k}_{sh:+d}h"] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    el = tab["EL"]
    elb = el[np.isfinite(el).all(axis=1)].mean(axis=1)
    r = nw(elb, T665_LAG)
    rep["E_L_window"] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    dxy = _load_60m("DX-Y.NYB")
    if dxy is not None and len(dxy):
        hs = HourSeries.from_frame(dxy)
        for k, (wa, wb) in (("T", (PRE_T, POST_T)), ("E", (PRE_E, POST_L))):
            a1 = np.array([edge_ts(d, wa[0]) for d in days]); b1 = np.array([edge_ts(d, wa[1]) for d in days])
            a2 = np.array([edge_ts(d, wb[0]) for d in days]); b2 = np.array([edge_ts(d, wb[1]) for d in days])
            dx = hs.window(a1, b1) - hs.window(a2, b2)
            r = nw(dx[np.isfinite(dx)], T665_LAG)
            rep[f"dxy_{k}"] = {"mean_bp": None if r["mean"] is None else r["mean"] * 1e4, "nw_t": r["t"], "n": r["n"]}
    rep["fred_check"] = fred_check(archive, series)
    cc = rep["fred_check"]
    corr_txt = ", ".join(f"{c} {_f(x['corr'], 2)}" for c, x in cc.items() if x)
    f_T, f_E = fx["T"], fx["E"]
    reason = (f"7-currency USD basket on local 60m bars, {sdays[0]}..{sdays[-1]}: Tokyo {nT} basket days (Mondays drop out: "
              f"the pre-T window starts before Yahoo's first Sunday bar), pre-T {_bp(f_T['pre'].mean() if nT else None)} vs post-T "
              f"{_bp(f_T['post'].mean() if nT else None)}, difference {_bp(TT['mean'])} (NW t {_s(TT['nw_t'])}, p {_f(TT['p_nw'], 4)}, "
              f"Holm {_f(an[0], 4)}; CBB p {CAL._mc(TT['p_bt'], TT['draws'])}), {f_T['n_pos']}/7 currencies positive; Europe {nE} days, "
              f"pre-E {_bp(f_E['pre'].mean() if nE else None)} vs post-L {_bp(f_E['post'].mean() if nE else None)}, difference "
              f"{_bp(TE['mean'])} (NW t {_s(TE['nw_t'])}, p {_f(TE['p_nw'], 4)}, Holm {_f(an[1], 4)}; CBB p {CAL._mc(TE['p_bt'], TE['draws'])}), "
              f"{f_E['n_pos']}/7 positive. Reported: rule net T {_s(rep['rule_net_T']['mean_bp'])} / E {_s(rep['rule_net_E']['mean_bp'])} bp/day "
              f"(expected <= 0), +6h placebos T {_s(rep['placebo_T_+6h']['mean_bp'])} / E {_s(rep['placebo_E_+6h']['mean_bp'])} bp, E-L window "
              f"{_s(rep['E_L_window']['mean_bp'])} bp, DXY T {_s((rep.get('dxy_T') or {}).get('mean_bp'))} / E "
              f"{_s((rep.get('dxy_E') or {}).get('mean_bp'))} bp, Japanese holidays T {_s(rep['subsets_T']['jp_holiday_bp'])} bp "
              f"(n {rep['subsets_T']['n_jp']}); FRED noon cross-check corr {corr_txt}")
    stat = {"n": n, "n_tokyo": nT, "n_europe": nE, "tokyo": {"test": TT, "per": f_T["per"], "split": f_T.get("split")},
            "europe": {"test": TE, "per": f_E["per"], "split": f_E.get("split")}, "holm_nw": an, "holm_boot": ab,
            "reported": rep, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {
    "b13_intraday_b_attention_open": b13_intraday_b_attention_open,
    "b13_intraday_b_eod_reversal": b13_intraday_b_eod_reversal,
    "b13_intraday_b_dtc_overnight": b13_intraday_b_dtc_overnight,
    "b13_intraday_b_usd_fix": b13_intraday_b_usd_fix,
}
THEORY_MAP = {
    "T-671": "b13_intraday_b_attention_open",
    "T-662": "b13_intraday_b_eod_reversal",
    "T-663": "b13_intraday_b_dtc_overnight",
    "T-665": "b13_intraday_b_usd_fix",
}
