"""
Batch 6c, group ``xs``: seven cross-sectional ETF rank, reversal and momentum claims on the Yahoo ETF universes.
==================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-309  52-week-high nearness, 19 ETFs (9 SPDRs, SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, DBC, VNQ), hold months
           2004-01..2026-09: top-6 minus bottom-6 mean > 0 with the 95% CI excluding 0 (studentized CBB, 12-month
           blocks), above the 95th percentile of a 1,000-draw within-month rank-permutation null, DSR > 0.95 over the 8
           declared trials. Diagnostic: paired difference against the 12-1 ranking on the same universe (reported).
  * T-476  same-calendar-month seasonality, 14 ETFs (9 SPDRs, GLD, SLV, USO, DBA, TLT), hold months 2004-01..2026-09:
           top-4 minus bottom-4 mean > 0 with CI excluding 0, above the permutation 95th percentile, DSR > 0.95 over 8.
  * T-313  12-1 commodity-ETF momentum, 13 ETFs (GLD SLV CPER USO UNG DBA DBB DBE PPLT PALL CORN WEAT SOYB), hold
           months 2012-12..2026-09: top-third minus bottom-third mean > 0 with CI excluding 0, above the permutation
           95th percentile, DSR > 0.95 over 12 trials, positive in 2013-2019 and in 2020-2026.
  * T-482  frog-in-the-pan on the 21-asset panel (T-309's 19 ETFs + BTC-USD, ETH-USD), hold months 2004-01..2026-09:
           among positive-12-1 assets, low-ID half minus high-ID half (both after costs) mean > 0 with the CI
           excluding 0, DSR > 0.95 over 4 trials, the difference positive without crypto.
  * T-471  36-to-12-month reversal across the 21 iShares country ETFs, hold months 1999-04..2026-09, 12 overlapping
           cohorts: 95% lower bound of the mean > 0 (studentized CBB, 12-month blocks), positive in 1999-2012 and in
           2013-2026, DSR > 0.95 over the 4 declared variants.
  * T-319  weekly skip-a-day 1-week reversal on the declared 30 ETFs (9 SPDRs + 21 country ETFs), entries 2010-01..
           2026-09, quintile long/short scaled to 10% vol: 95% lower bound of the mean net weekly return > 0
           (studentized CBB, 8-week blocks), DSR > 0.95 over every variant run (9), CSCV PBO < 0.5, same sign in
           2010-2017 and 2018-2026.
  * T-462  weekly bottom-minus-top quintile reversal on the declared T-420/T-462 ETF list (68 ETFs), entries 2007-01..
           2026-09: the cell selected on 2007-2016 has an out-of-sample (2017-2026) net mean > 0 with HAC p < 0.05,
           DSR >= 0.95 over the 18 declared cells, and (the claim's own words) a higher net return when VIX is above its
           1-year median (HAC p < 0.05). The 10 crypto cells need the CoinMarketCap point-in-time universe
           (cmc-daily-listings-<YYYY>), which is not archived: the DSR is judged from bounds (below).

Conventions
  * Data. ``daily-history-<SYM>`` bundles through ``archive.load``; a row is used only when its ``available_at`` is not
    after the bundle's capture time. Prices are Yahoo ``adjclose`` (split and dividend adjusted: total return); opens
    are put on the same basis (open x adjclose / close). ETF bars are keyed by their session date, crypto bars by the
    UTC calendar day. VIX is ``cboe-VIX-history`` (close), bills ``fred-DTB3``.
  * Universes (no survivorship beyond the claims' own declared lists). Every universe is the claim's declared list,
    written here before any return is computed; an ETF enters only once it has the history the rule needs (T-309: 252
    sessions; T-476: 5 prior same-month returns; T-313 and T-482: a month-end 12 (or J) months back; T-471: a month-end
    36 months back; T-319: 60 sessions for the trailing book volatility; T-462: 22 sessions, the longest declared
    formation). Late listings (EEM 2003, GLD 2004, DBC 2006, the country ETFs EWT/EWY/EWZ 2000 and EZA 2003, PPLT
    2010, CPER 2011, BTC 2014, ETH 2017) join late. All names on these lists are 2026 survivors; Yahoo serves no
    delisted fund, so the declared lists are survivor-drawn (stated in each reason where the claim asks for it).
  * Calendars (rule 10(a)). Every monthly claim names month-end decisions ("at month-end t"): T-309, T-476, T-313,
    T-482 decide on the month's last session close and fill at the close of the next session (crypto: the next
    calendar day), holding fill to fill; T-471 trades at the month-end close itself, as its trial states ("the trade is
    at month-end t"; the signal ends 12 months earlier). The weekly claims name the last trading day of the week
    (T-319: "the close of t, the last trading day of the week"; T-462: "the Friday close"); a week whose Friday is a
    holiday ends on its last session. Holds run week-end to week-end. Overlapping multi-period holds (T-309's 6-month
    hold, T-471's 12-month cohorts, T-319's 4-week 1-month variant, T-471's 36-month 36-0 variant) average one cohort
    per decision (the pooled all-start estimator, Jegadeesh-Titman), so no grid phase is chosen; bootstrap blocks are
    12 months (>= every monthly overlap except the 36-0 variant, which feeds only the DSR/PBO family).
  * Point in time (rules 4, 12). A daily bar is available the next day (available_at = bar + 24 h), before the next
    session's close, so a month-end signal filled at the next close uses one information set. T-471's signal ends at
    t-12. T-319/T-462 skip-a-day cells use closes through t-1 for the signal, the trailing volatility and the VIX
    gate, and fill at close t; the no-skip cells use close t for all of them (the live proxy) and fill at close t;
    T-319's next-open variant forms at close t and trades at the next session's open. VIX closes are stamped 21:30 UTC
    on their own day, so a gate at day q reads VIX(q). T-476's seasonal scores use only same-month returns of earlier
    years.
  * Books and costs (rule 9) as each claim states, charged on drift-adjusted turnover at every rebalance (per unit of
    notional traded; costs are paid from capital: net = (1 - cost) x (1 + gross - borrow) - 1). Long/short books are
    zero-investment (one unit long, one short; the return is the spread, which is an excess return); long-only books
    are fully invested, with idle cash at DTB3 (T-313's absolute filter) and are judged on excess returns. Borrow is
    charged on the short notional pro rata over calendar days. T-309: 5 bps per side, 50 bps/yr borrow. T-476: 5 bps
    per side SPDRs (and TLT, a non-commodity ETF the claim does not price separately), 10 bps the commodity ETFs (GLD,
    SLV, USO, DBA), borrow on shorts at 50 bps/yr (the claim names borrow but no rate; 50 bps/yr is the sibling
    claims' rate, and 0 and 100 bps/yr are reported). T-313: the claim states ranges, so both ends are run and every
    cost-dependent criterion must hold under both (rule 11 spirit: a pass must not hinge on where in the stated range
    the cost lies): low = 10 bps per side on every name + 1%/yr borrow on UNG/USO shorts; high = 20 bps per side on the
    thin names (CPER, PALL, CORN, WEAT, SOYB), 10 bps on the others + 3%/yr on UNG/USO shorts. T-482: 5 bps ETFs, 25 +
    10 bps crypto per side, each half charged its own costs. T-471 and T-319: 10 bps per leg per trade + 50 bps/yr
    borrow on the short leg. T-462: 10 bps per ETF leg, no borrow (none stated).
  * Intervals (rule 6). Studentized circular block bootstrap of the mean (Bartlett-HAC s.e., bandwidth = block;
    batch6b_bw._stud), 5,000 draws per seed, interval ends averaged over 5 seeds with their Monte Carlo s.e. (25 seeds
    when 5 cannot resolve the bound). "95% interval excluding zero" and "95% lower bound" (two-sided nulls) are the
    two-sided 95% interval. Blocks: 12 months (monthly claims), 8 weeks (T-319, the trial's). T-462 names a HAC t:
    Newey-West (Bartlett, lag floor(4 (n/100)^(2/9))), one-sided p for its "net mean <= 0" null; the VIX difference is
    the slope of net return on the VIX-above-median dummy with the same HAC s.e.
  * Permutation nulls (T-309, T-476, T-313). Within every month the eligible names' ranks are permuted uniformly (the
    same number of longs and shorts); the null mean is the permuted books' gross mean minus the strategy's own mean cost
    and borrow (rank information only, as underlying2.sector_rotation), 1,000 permutations (the trials' count). The
    criterion is the observed net mean above the null's 95th percentile; p = (1 + #null >= observed) / 1001.
  * Families (multiple testing), declared before any result. T-309: k = 6/4 x hold 1/6 months x long-short/long-only
    top = 8. T-476: window all prior years (<= 20)/last 10 x k = 4/3 x long-short/long-only top = 8. T-313: 12-1/6-1/3-1
    x thirds/top-bottom 3 x long-short/long-only with an absolute filter = 12. T-482: 12-1/6-1 x median/terciles = 4.
    T-471: 36-12 with 12 overlapping cohorts (primary), 36-0 with 36 overlapping cohorts (the Richards/Quantpedia
    3-year hold, pooled over every start), the Balvers-Wu-Gilliland parametric deviation (weights proportional to minus
    the country's relative log price minus its own trailing 10-year mean, the stated 3-year half-life a constant scale
    that cancels in the normalised weights, monthly), long-only bottom quartile minus the equal-weight universe = 4.
    T-319: formation 1 week / 1 month (21 sessions, 4-week overlapping hold) x skip / no skip x VIX top-tercile gate
    off / on, plus the next-open variant of the primary = 9, every variant run (>= 8). T-462: lookback 1 week / 1 month
    x skip on / off x VIX doubling off / on (Nagel: double size when VIX > its trailing 252-session median) = the 8 ETF
    cells; the 10 crypto cells (8 crypto + 2 crypto-sign) need cmc-daily-listings-<YYYY>.
    DSR (rule 5 of section 2; batch6c_mom.family_dsr): per-period Sharpe of the tested series against the expected best
    of n_trials, trial-Sharpe variance = the computed family's observed variance floored at the zero-skill 1/(T-1)
    (house convention); reasons give both. T-462's DSR with 8 of 18 trial Sharpes known: the most favourable variance
    the 10 unknown Sharpes allow is max(1/(T-1), 7/17 x the 8-cell variance) (all unknowns at the 8-cell mean); a DSR
    below 0.95 even there fails whatever the crypto cells are, otherwise the criterion is not implemented (None). Its
    "DSR >= 0.95" is judged on the selected cell's full 2007-2026 series AND on its out-of-sample series (both readings
    must pass; rule 11 spirit). PBO (overfit.pbo_cscv, its default 8 partitions) is a criterion only for T-319; for
    T-462 (8 of 18 cells) and T-471 it is reported.
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively (CI wholly
    below zero; permutation p >= 0.95; PSR against zero <= 0.05).

Claim-specific choices (declared before any result)
  * T-309: nearness = adjclose_t / max(adjclose over the 252 sessions ending t); a month enters when >= 12 names are
    eligible. Long-only top-k is fully invested; the 6-month hold averages the last 6 monthly cohorts.
  * T-476: a same-month return is month-end(m) / month-end(m - 1) - 1 of the ETF's own bars (both month-ends must
    exist); the score averages the most recent (at most 20, or 10) earlier years, at least 5; a month enters when >= 8
    names have a score. Ex-energy (XLE, USO removed) and by-decade results are reported.
  * T-313: the claim fixes the window (holds 2012-12..2026-09); each formation uses the same months. Long-only with an
    absolute filter holds 1/k in each top-k name whose formation return is positive, the rest in bills. Ex-energy
    (USO, UNG, DBE removed), DBC's excess return (benchmark only), the USO 2020 restructuring months and the declared
    exclusions (the delisted commodity ETNs, among them several iPath notes, are outside the declared 13) are reported.
  * T-482: ID = sign(PRET) x (share of negative - share of positive daily returns) over the formation window's own
    sessions (all calendar days for crypto); the low-ID half is the floor(m/2) lowest, the high-ID half the floor(m/2)
    highest (the middle name of an odd count sits out); terciles use floor(m/3). A month with fewer than 2 positive
    formation returns has no observation (both halves flat; its exit costs are booked in it and it is left out of n).
  * T-471: quartile = floor(n/4) names per side (4 while 17 ETFs are eligible, 5 from 21); an ETF joins once it has a
    month-end 36 months back. Cohort returns are the active cohorts' average (fully invested during the 11-month
    ramp-up).
  * T-319: the vol target scales each week's book to 10% a year using the book's trailing 60 daily returns with the
    current weights (ex ante, through the signal close). The claim's sentence names the portfolio without the sizing
    while its procedure includes it, so every criterion is judged on the vol-targeted book (the rule) AND on the
    unscaled book (both must pass). The VIX gate trades only when VIX is above the 2/3 quantile of its trailing 252
    sessions. Halves: entries 2010-01..2017-12 and 2018-01..2026-09; VIX terciles and the break-even cost are reported.
  * T-462: the cell is selected by its 2007-2016 net Sharpe among the 8 ETF cells (the claim is "in the declared ETF
    universe"); the out-of-sample test uses that cell's 2017-2026 entries; the VIX criterion uses the selected cell's
    formation without VIX doubling (doubling would inflate it mechanically) over 2007-2026. 2008 and 2020 reported.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import (Bills, _ci_crit, _clean, _decide, _mean_stat, _stud, all_constructions,
                                           mc_escalate, ols_hac)
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

N_BOOT = 5000                  # bootstrap draws per seed (the trials' 5,000)
REPS = 5                       # bootstrap seeds behind every decisive interval end
SEED = 0
N_PERM = 1000                  # the trials' 1,000 within-month permutations
BLOCK_M = 12                   # months
BLOCK_W = 8                    # weeks (T-319's trial)
DSR_PASS = 0.95
ALPHA = 0.05
PBO_PARTS = 8                  # overfit.pbo_cscv default (the T-319 trial names overfit.pbo_cscv)
_N = NormalDist()

DTB3_B = "fred-DTB3"
VIX_B = "cboe-VIX-history"
CMC_NAME = "cmc-daily-listings-<YYYY> (2017..2026; CoinMarketCap point-in-time daily listings for the top-20 crypto universe)"
CMC_PREFIX = "cmc-daily-listings-"

SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
COUNTRY21 = ("EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWK", "EWL", "EWM", "EWN", "EWO", "EWP", "EWQ", "EWS", "EWT",
             "EWU", "EWW", "EWY", "EWZ", "EZA")
U19 = SECTORS + ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ")
U14 = SECTORS + ("GLD", "SLV", "USO", "DBA", "TLT")
U13 = ("GLD", "SLV", "CPER", "USO", "UNG", "DBA", "DBB", "DBE", "PPLT", "PALL", "CORN", "WEAT", "SOYB")
CRYPTO = ("BTC-USD", "ETH-USD")
U21 = U19 + CRYPTO
U30 = SECTORS + COUNTRY21
# T-420/T-462 declared list (mandel.data.market_history: "the 26 archived ETFs plus these 42", >= 60 with history by 2006,
# PPLT from 2010).
ARCHIVED26 = SECTORS + ("SPY", "QQQ", "IWM", "IJR", "IVV", "IWD", "IWF", "EFA", "AGG", "TLT", "IEF", "GLD", "SLV", "USO", "DBC",
                        "VNQ", "PKW")
ISHARES_SECTORS = ("IYW", "IYF", "IYH", "IYE", "IYJ", "IYK", "IYC", "IDU", "IYM", "IYZ", "IYT")
ETF60_EXTRA = COUNTRY21 + ("EEM", "GDX", "IJH", "MDY", "DIA", "LQD", "TIP", "SHY", "IYR") + ISHARES_SECTORS + ("PPLT",)
U68 = ARCHIVED26 + ETF60_EXTRA


def dh(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


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


def _daily(archive, name: str) -> tuple:
    """(days, adjclose, open on the adjclose basis) of a Yahoo daily bundle; a bar without adjclose carries the previous
    adjclose/close ratio; a missing open is NaN."""
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
            try:
                a = float(v.get("adjclose"))
                a = a if a > 0 and math.isfinite(a) else float("nan")
            except (TypeError, ValueError):
                a = float("nan")
            try:
                o = float(v.get("open"))
                o = o if o > 0 and math.isfinite(o) else float("nan")
            except (TypeError, ValueError):
                o = float("nan")
            by[d] = (c, a, o)
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 3)
        close, adj, opn = arr[:, 0], arr[:, 1].copy(), arr[:, 2]
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, adj, opn * adj / close
    return _cached(archive, ("daily", name), load)


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED (value) or Cboe (close) bundle; non-numeric prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = v.get("value", v.get("close"))
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("series", name), load)


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_series(archive, DTB3_B)))


def _load(archive, syms: Sequence[str]) -> dict:
    return {s: _daily(archive, dh(s)) for s in syms}


# ================================================================================================== calendars ==

def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _month_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _months(a: str, b: str) -> list:
    out, m = [], a
    while m <= b:
        out.append(m)
        m = _month_add(m, 1)
    return out


def month_panel(series: dict, first: str, last: str) -> dict:
    """Monthly panel on each asset's OWN bars. For asset i and month t: JME = index of its last bar in t (the decision
    close; -1 when it has none), PME its adjclose, PEX the adjclose of the next bar (the fill). R_ex[:, t] = PEX[t+1] /
    PEX[t] - 1 is the fill-to-fill hold of the decision at t; R_me[:, t] = PME[t+1] / PME[t] - 1 the month-end to
    month-end hold. ``ex_day``/``me_day``: the union calendar's fill and month-end days (bills, borrow days)."""
    labels = _months(first, last)
    pos = {m: t for t, m in enumerate(labels)}
    syms = list(series)
    N, T = len(syms), len(labels)
    JME = np.full((N, T), -1, int)
    PME, PEX = np.full((N, T), np.nan), np.full((N, T), np.nan)
    union = set()
    for i, s in enumerate(syms):
        days, adj = series[s][0], np.asarray(series[s][1], float)
        union.update(days)
        lastbar = {}
        for j, d in enumerate(days):
            lastbar[d[:7]] = j
        for m, j in lastbar.items():
            t = pos.get(m)
            if t is None:
                continue
            JME[i, t] = j
            PME[i, t] = adj[j]
            if j + 1 < len(days):
                PEX[i, t] = adj[j + 1]
    u = sorted(union)
    lu = {}
    for k, d in enumerate(u):
        lu[d[:7]] = k
    me_day = [u[lu[m]] if m in lu else None for m in labels]
    ex_day = [u[lu[m] + 1] if (m in lu and lu[m] + 1 < len(u)) else None for m in labels]
    R_ex, R_me = np.full((N, T), np.nan), np.full((N, T), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        R_ex[:, :-1] = PEX[:, 1:] / PEX[:, :-1] - 1
        R_me[:, :-1] = PME[:, 1:] / PME[:, :-1] - 1
    return {"labels": labels, "pos": pos, "syms": syms, "JME": JME, "PME": PME, "PEX": PEX, "R_ex": R_ex, "R_me": R_me,
            "me_day": me_day, "ex_day": ex_day}


def _period_bills(bills: Optional[Bills], d0: Sequence, d1: Sequence) -> tuple:
    """(bill return, calendar days) between paired days (None-safe: 0 / 30 when a day is missing)."""
    rf, nd = [], []
    for a, b in zip(d0, d1):
        if a is None or b is None:
            rf.append(0.0)
            nd.append(30.0)
            continue
        rf.append(bills.growth(a, b) - 1.0 if bills is not None else 0.0)
        nd.append(float(_ord(b) - _ord(a)))
    return np.array(rf, float), np.array(nd, float)


def daily_panel(series: dict, lo: str, hi: str) -> dict:
    """Master daily calendar (the days on which at least half of the already-listed ETFs have a bar, within [lo, hi]),
    adjclose matrix P forward-filled after each ETF's first bar (NaN before), adjusted opens O (NaN where no bar),
    real-bar flags, first-bar index and daily returns DR (row d = P[d] / P[d-1] - 1)."""
    syms = list(series)
    cnt, firsts = {}, []
    for s in syms:
        days = series[s][0]
        if days:
            firsts.append(days[0])
        for d in days:
            if lo <= d <= hi:
                cnt[d] = cnt.get(d, 0) + 1
    firsts.sort()
    days = [d for d in sorted(cnt) if cnt[d] >= 0.5 * bisect.bisect_right(firsts, d)]
    idx = {d: k for k, d in enumerate(days)}
    D, N = len(days), len(syms)
    P, O = np.full((D, N), np.nan), np.full((D, N), np.nan)
    real = np.zeros((D, N), bool)
    for i, s in enumerate(syms):
        dd, adj, opn = series[s][0], np.asarray(series[s][1], float), series[s][2] if len(series[s]) > 2 else None
        for j, d in enumerate(dd):
            k = idx.get(d)
            if k is None:
                continue
            P[k, i] = adj[j]
            real[k, i] = True
            if opn is not None:
                O[k, i] = opn[j]
    first = np.full(N, D, int)
    for i in range(N):
        nz = np.flatnonzero(real[:, i])
        if nz.size:
            first[i] = nz[0]
            col = P[:, i]
            k = np.where(np.isfinite(col), np.arange(D), -1)
            k = np.maximum.accumulate(k)
            P[:, i] = np.where(k >= 0, col[np.maximum(k, 0)], np.nan)
    DR = np.full((D, N), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        DR[1:] = P[1:] / P[:-1] - 1
    ords = np.array([_ord(d) for d in days], np.int64)
    return {"days": days, "syms": syms, "P": P, "O": O, "real": real, "first": first, "DR": DR, "ords": ords}


def week_ends(days: Sequence[str]) -> np.ndarray:
    """Index of the last master day of every ISO week (the week's last trading day)."""
    last = {}
    for i, d in enumerate(days):
        y, w, _ = date.fromisoformat(d).isocalendar()
        last[(y, w)] = i
    return np.array(sorted(last.values()), int)


class VixTool:
    """VIX close known at a master day (the last print on or before it) and trailing quantiles over its 252 prints."""

    def __init__(self, vix: dict, days: Sequence[str], window: int = 252):
        self.vd = sorted(vix)
        self.vv = np.array([vix[d] for d in self.vd], float)
        self.pos = np.array([bisect.bisect_right(self.vd, d) - 1 for d in days], int)
        self.window = window

    def level(self, q: int) -> float:
        p = self.pos[q]
        return float(self.vv[p]) if p >= 0 else float("nan")

    def trailing(self, q: int, quant: float) -> float:
        p = self.pos[q]
        if p < self.window - 1:
            return float("nan")
        return float(np.quantile(self.vv[p - self.window + 1:p + 1], quant))


# =============================================================================================== book arithmetic ==

def book(W, R, cost, borrow=None, hold_days=None, rf=None) -> dict:
    """Net returns of target weights W (T, N) (fractions of capital, set at each rebalance) on hold returns R (T, N).
    ``cost`` (N,) per side per unit traded; ``borrow`` (N,) annual rate on short notional over ``hold_days`` (T,)
    calendar days; ``rf`` (T,) cash return of a funded book (None = a zero-investment book: one unit long, one short).
    gross = sum W R (+ rf on the cash of a funded book), pre = gross - borrow, turnover against the previous weights
    drifted over their hold, net = (1 - cost x turnover) (1 + pre) - 1."""
    W = np.asarray(W, float)
    R = np.asarray(R, float)
    bad = (W != 0) & ~np.isfinite(R)
    if bad.any():
        raise ValueError("a held name has no hold return")
    R0 = np.where(np.isfinite(R), R, 0.0)
    T = W.shape[0]
    if rf is None:
        gross = (W * R0).sum(axis=1)
    else:
        rf = np.asarray(rf, float)
        gross = rf + (W * (R0 - rf[:, None])).sum(axis=1)
    bor = np.zeros(T)
    if borrow is not None:
        hd = np.asarray(hold_days, float)
        bor = (np.maximum(-W, 0.0) * np.asarray(borrow, float)[None, :]).sum(axis=1) * hd / 365.0
    pre = gross - bor
    prev = np.zeros_like(W)
    if T > 1:
        den = 1.0 + pre[:-1]
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        prev[1:] = W[:-1] * (1.0 + R0[:-1]) / den[:, None]
    to = np.abs(W - prev)
    c = (to * np.asarray(cost, float)[None, :]).sum(axis=1)
    net = (1.0 - c) * (1.0 + pre) - 1.0
    return {"net": net, "gross": gross, "borrow": bor, "cost": c, "turnover": to.sum(axis=1)}


def rank_weights(score: np.ndarray, elig: np.ndarray, k: int, long_high: bool = True, short: bool = True) -> np.ndarray:
    """One cohort's weights: +1/k on the k best scores (highest when ``long_high``, else lowest), -1/k on the k at the
    other end (``short``); stable order on ties; zeros when fewer than k (2k for long/short) names are eligible."""
    w = np.zeros(score.size)
    idx = np.flatnonzero(elig & np.isfinite(score))
    if k < 1 or idx.size < (2 * k if short else k):
        return w
    o = idx[np.argsort(-score[idx] if long_high else score[idx], kind="stable")]
    w[o[:k]] = 1.0 / k
    if short:
        w[o[-k:]] = -1.0 / k
    return w


def overlap(C: np.ndarray, H: int, t0: int = 0) -> np.ndarray:
    """Overlapping-cohort book: row t = mean of the cohort rows t-H+1..t that are at or after row t0 (Jegadeesh-Titman;
    fully invested while fewer than H cohorts exist)."""
    C = np.asarray(C, float)
    out = np.zeros_like(C)
    for t in range(C.shape[0]):
        lo = max(t0, t - H + 1)
        if t >= t0:
            out[t] = C[lo:t + 1].mean(axis=0)
    return out


# =============================================================================================== statistics ==

def mean_test(x, block: int = BLOCK_M, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """Studentized circular block bootstrap of a mean: est, two-sided 95% CI (interval ends averaged over seeds, with
    their Monte Carlo s.e.), p (H0: mean <= 0)."""
    x = np.asarray(x, float)
    nb = N_BOOT if n_boot is None else n_boot
    return mc_escalate(lambda seed: _stud(_mean_stat, [x], block, nb, seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1],
                       REPS if reps is None else reps, seed)


def perm_null(R: np.ndarray, elig: np.ndarray, k, n_perm: int, seed: int = SEED) -> np.ndarray:
    """Within-month rank permutation: in every row the eligible names' ranks are permuted uniformly; each draw's gross
    long/short return is mean(R of k random longs) - mean(R of k random shorts) (k an int or one per row, the
    strategy's own leg size). Returns the (n_perm,) null means over the rows that hold a book."""
    rng = np.random.default_rng(seed)
    ks = np.broadcast_to(np.asarray(k, int), (R.shape[0],))
    tot, cnt = np.zeros(n_perm), 0
    for t in range(R.shape[0]):
        idx = np.flatnonzero(elig[t])
        k = int(ks[t])
        if k < 1 or idx.size < 2 * k:
            continue
        r = R[t, idx]
        o = np.argsort(rng.random((n_perm, idx.size)), axis=1)
        rp = r[o]
        tot += rp[:, :k].mean(axis=1) - rp[:, -k:].mean(axis=1)
        cnt += 1
    return tot / max(cnt, 1)


def perm_row(obs_net: float, mean_cost: float, null_gross: np.ndarray, label: str) -> tuple:
    """(name, ok, decisive) for 'observed net mean above the 95th percentile of the cost-matched permutation null'."""
    null = null_gross - mean_cost
    q95 = float(np.quantile(null, 0.95))
    p = float((1 + np.sum(null >= obs_net)) / (null.size + 1))
    return (f"{label} (net mean {_pc(obs_net, 3)} vs null 95th pct {_pc(q95, 3)}; permutation p {p:.3f}, {null.size:,} "
            f"permutations)", bool(obs_net > q95), p >= 0.95), {"q95": q95, "p": p, "null_mean": float(null.mean())}


def nw_lag(n: int) -> int:
    return max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def hac_mean(x, lag: Optional[int] = None) -> dict:
    """Mean with a Newey-West (Bartlett) s.e.; t and one-sided p (H0: mean <= 0)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else None, "t": None, "p": None, "lag": None, "n": int(n)}
    L = nw_lag(n) if lag is None else int(lag)
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(L, n - 1) + 1):
        s += 2.0 * (1.0 - l / (L + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 1e-300) / n)
    t = float(x.mean() / se)
    return {"mean": float(x.mean()), "se": se, "t": t, "p": 1.0 - _N.cdf(t), "lag": L, "n": int(n)}


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 else None


def _sr_ann(x, ppy: float = 12.0) -> Optional[float]:
    s = _sr_pp(x)
    return None if s is None else s * math.sqrt(ppy)


def dsr_bound(x, known_sharpes: Sequence[float], n_total: int, label: str, thr: float = DSR_PASS, ge: bool = True) -> tuple:
    """DSR of ``x`` over ``n_total`` trials when only ``known_sharpes`` (m < n_total) are computed. The house variance is
    the trial Sharpes' observed variance floored at 1/(T-1); the unknown Sharpes can push it arbitrarily high (DSR -> 0)
    but no lower than (m-1)/(n_total-1) x the known variance (all unknowns at the known mean), so the DSR is at most
    its value at max(1/(T-1), that variance). Fails when even that bound misses ``thr``; otherwise not implemented.
    Returns ((name, ok, decisive), info)."""
    x = np.asarray(x, float)
    ks = np.array([s for s in known_sharpes if s is not None and math.isfinite(s)], float)
    m = ks.size
    floor = 1.0 / max(1, x.size - 1)
    if m >= n_total:
        d = family_dsr(x, list(ks), n_total)
        name, ok, dec = dsr_row(d, label)
        if ge and d.get("dsr") is not None:
            ok = d["dsr"] >= thr
        return (name, ok, dec), {"dsr": d.get("dsr"), "complete": True, "family": d}
    vk = float(ks.var(ddof=1)) if m > 1 else 0.0
    vmin = (m - 1) * vk / (n_total - 1) if m > 1 else 0.0
    vbest = max(vmin, floor)
    ok_n = x.size > 3
    hi = float(deflated_sharpe_ratio(x, n_trials=n_total, var_trials_sr=vbest)) if ok_n else None
    part = family_dsr(x, list(ks), n_total)
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1)) if ok_n else None
    info = {"dsr_upper_bound": hi, "var_best": vbest, "var_known": vk if m > 1 else None, "var_floor": floor, "n_known": int(m),
            "n_total": int(n_total), "dsr_partial": part.get("dsr"), "psr0": psr0, "complete": False}
    if hi is None:
        return (f"{label} (n/a)", None, False), info
    fails = hi < thr if ge else hi <= thr
    txt = (f"{label} (at most {hi:.3f} at {n_total} trials with {m} of {n_total} trial Sharpes computed: the most favourable "
           f"variance max(1/(T-1) {floor:.2e}, {m - 1}/{n_total - 1} x {vk:.2e}) = {vbest:.2e}; with the {m} computed cells' "
           f"variance floored, {_f(part.get('dsr'))})")
    if fails:
        return (txt + " [fails whatever the missing trials' Sharpes]", False, psr0 is not None and psr0 <= 1.0 - thr), info
    return (txt + f" [the other {n_total - m} trial Sharpes need {CMC_NAME}, not archived]", None, False), info


def _pbo(cols: Sequence[np.ndarray]) -> Optional[dict]:
    L = min(c.size for c in cols)
    if L < 2 * PBO_PARTS or len(cols) < 2:
        return None
    return pbo_cscv(np.column_stack([np.asarray(c, float)[-L:] for c in cols]), n_partitions=PBO_PARTS)


# ================================================================================================= formatting ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _ci(ci, nd: int = 2) -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * 100:+.{nd}f}% to {hi * 100:+.{nd}f}%"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _ci_row(t: dict, label: str) -> tuple:
    return _ci_crit(t, "gt", 0.0, label, fmt=lambda v: _pc(v, 3))


def _by_decade(x: np.ndarray, labels: Sequence[str]) -> dict:
    out = {}
    for dec in sorted({l[:3] for l in labels}):
        m = np.array([l[:3] == dec for l in labels])
        if m.sum() >= 6:
            out[f"{dec}0s"] = {"n": int(m.sum()), "mean": float(x[m].mean())}
    return out


def _sub_mean(x: np.ndarray, labels: Sequence[str], a: str, b: str) -> Optional[dict]:
    m = np.array([a <= l <= b for l in labels])
    if m.sum() < 3:
        return None
    return {"n": int(m.sum()), "mean": float(x[m].mean()), "sharpe_pp": _sr_pp(x[m]), "first": [l for l, k in zip(labels, m) if k][0],
            "last": [l for l, k in zip(labels, m) if k][-1]}


def same_sign(halves: dict) -> Optional[bool]:
    """'Same sign in both halves' as worded: both half means non-zero and of one sign (None when a half is empty). A
    supported claim also needs the full-sample bound above zero, so a pass here then means both halves positive."""
    if any(h is None for h in halves.values()):
        return None
    sg = {int(np.sign(h["mean"])) for h in halves.values()}
    return len(sg) == 1 and 0 not in sg


MIN_MONTHS = 24                # fewer sample months than this: nothing is computed (data limit, inconclusive)
MIN_WEEKS = 104


def _too_short(n: int, min_n: int, unit: str, what: str):
    v, why = _verdict([(f"n >= trial min_n ({n} of {min_n} {unit})", None)])
    return ({"too_short": True, "n": int(n), "min_n": int(min_n)}, int(n), v,
            f"{what}: only {n} {unit} can be formed from the archived histories (the claim needs {min_n}); nothing is "
            f"computed — {why}")


def _dsr_txt(d: dict) -> str:
    if d.get("dsr") is None:
        return "n/a"
    s = f"{d['dsr']:.3f} (trial-Sharpe var {d['var_trials_sr']:.2e}"
    if d.get("var_observed") is not None:
        s += f"; observed {d['var_observed']:.2e}, floor 1/(T-1) {d['var_floor']:.2e}"
    return s + ")"


def _fmt_family(fam: dict) -> str:
    return "; ".join(f"{k} {_s(v, 2)}" for k, v in fam.items() if v is not None)


# ============================================================================== monthly cross-sectional engine ==

def _monthly_ls_core(primary: dict, family: dict, n_trials: int, perm: Optional[tuple], min_n: int) -> dict:
    """Shared judging of the monthly long/short claims (T-309, T-476): mean CI, permutation, DSR."""
    x = primary["excess"]
    mt = mean_test(x, BLOCK_M)
    crit = [_ci_row(mt, "mean monthly net long/short return > 0 with the 95% CI excluding 0 (studentized CBB, 12-month blocks)")]
    pinfo = None
    if perm is not None:
        R, elig, k = perm
        null = perm_null(R, elig, k, N_PERM)
        row, pinfo = perm_row(float(primary["net"].mean()), float((primary["gross"] - primary["net"]).mean()), null,
                              "above the 95th percentile of the within-month rank-permutation null")
        crit.append(row)
    fam_sh = {k: _sr_pp(v["excess"]) for k, v in family.items()}
    d = family_dsr(x, list(fam_sh.values()), n_trials)
    crit.append(dsr_row(d, f"DSR > {DSR_PASS} over the {n_trials} declared trials"))
    v, why = _decide(crit, x.size, min_n, "months")
    return {"mean_test": mt, "perm": pinfo, "dsr": d, "family_sharpe_pp": fam_sh, "criteria": [(c[0], c[1]) for c in crit],
            "verdict": v, "why": why}


# ============================================================================================ T-309 52-week high ==

T309_MIN_N = 250
T309_START, T309_END = "2004-01", "2026-09"       # hold months
T309_MIN_NAMES = 12
T309_COST = 5e-4
T309_BORROW = 0.005
T309_FAMILY = tuple((k, H, kind) for k in (6, 4) for H in (1, 6) for kind in ("LS", "LO"))
T309_PRIMARY = (6, 1, "LS")


def _nearness(series: dict, PN: dict, t_idx: np.ndarray) -> np.ndarray:
    N = len(PN["syms"])
    near = np.full((t_idx.size, N), np.nan)
    for i, s in enumerate(PN["syms"]):
        adj = np.asarray(series[s][1], float)
        for r, t in enumerate(t_idx):
            j = PN["JME"][i, t]
            if j >= 251:
                near[r, i] = adj[j] / adj[j - 251:j + 1].max()
    return near


def fifty_two_week_high(series: dict, bills: Bills, start: str = T309_START, end: str = T309_END, min_n: int = T309_MIN_N,
                        family: Sequence[tuple] = T309_FAMILY) -> dict:
    """T-309 core. Month-end nearness ranking, fill at the next close, hold to the next fill."""
    family = tuple(family)
    PN = month_panel(series, _month_add(start, -14), _month_add(end, 1))
    labels = PN["labels"]
    T = len(labels)
    dec_all = np.array([t for t in range(T - 1) if start <= labels[t + 1] <= end], int)
    near_all = _nearness(series, PN, dec_all)
    R_all = PN["R_ex"][:, dec_all].T
    elig_all = np.isfinite(near_all) & np.isfinite(R_all)
    keep = elig_all.sum(axis=1) >= T309_MIN_NAMES
    dec, near, R, elig = dec_all[keep], near_all[keep], R_all[keep], elig_all[keep]
    hold = [labels[t + 1] for t in dec]
    if dec.size < MIN_MONTHS:
        return {"too_short": True, "n": int(dec.size)}
    rf, nd = _period_bills(bills, [PN["ex_day"][t] for t in dec], [PN["ex_day"][t + 1] for t in dec])
    N = len(PN["syms"])
    cost = np.full(N, T309_COST)
    borrow = np.full(N, T309_BORROW)
    out = {}
    for v in family:
        k, H, kind = v
        C = np.array([rank_weights(near[r], elig[r], k, True, kind == "LS") for r in range(dec.size)])
        W = overlap(C, H)
        b = book(W, R, cost, borrow, nd, rf=None if kind == "LS" else rf)
        b["excess"] = b["net"] if kind == "LS" else b["net"] - rf
        out[v] = b
    pv = out[T309_PRIMARY] if T309_PRIMARY in out else out[family[0]]
    core = _monthly_ls_core(pv, {"|".join(map(str, k)): o for k, o in out.items()}, len(family), (R, elig, T309_PRIMARY[0]), min_n)
    # diagnostic: the 12-1 ranking on the same eligible names (those with a month-end 12 months back)
    mom = np.full_like(near, np.nan)
    for r, t in enumerate(dec):
        if t - 12 >= 0:
            mom[r] = PN["PME"][:, t - 1] / PN["PME"][:, t - 12] - 1
    em = elig & np.isfinite(mom)
    Cm = np.array([rank_weights(mom[r], em[r], 6, True, True) for r in range(dec.size)])
    bm = book(Cm, R, cost, borrow, nd)
    diff = pv["net"] - bm["net"]
    dt = mean_test(diff, BLOCK_M)
    counts = elig.sum(axis=1)
    full = [hold[r] for r in range(dec.size) if counts[r] == len(PN["syms"])]
    return {**core, "n": int(dec.size), "labels": hold, "net": pv["net"], "gross_mean": float(pv["gross"].mean()),
            "cost_mean": float(pv["cost"].mean()), "borrow_mean": float(pv["borrow"].mean()),
            "turnover_mean": float(pv["turnover"].mean()), "names_first": int(counts[0]) if counts.size else 0,
            "all_names_from": full[0] if full else None, "decade": _by_decade(pv["net"], hold),
            "vs_12_1": {"mean_diff": float(diff.mean()), "ci": dt.get("ci"), "mom_mean": float(bm["net"].mean())},
            "family_sharpe_ann": {"|".join(map(str, k)): _sr_ann(o["excess"]) for k, o in out.items()},
            "months_dropped_below_12_names": int((~keep).sum())}


def b6c_xs_fifty_two_week_high(archive):
    """T-309."""
    need = [dh(s) for s in U19] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    j = fifty_two_week_high(_load(archive, U19), _bills(archive))
    if j.get("too_short"):
        return _too_short(j["n"], T309_MIN_N, "months", f"hold months {T309_START}..{T309_END} with >= 12 eligible ETFs")
    mt, p, d = j["mean_test"], j["perm"], j["dsr"]
    reason = (f"19 declared ETFs ({', '.join(U19)}; an ETF joins once it has 252 sessions: {j['names_first']} names at the "
              f"first decision, all 19 from hold month {j['all_names_from']}), month-end decisions filled at the next "
              f"session's close, hold months {j['labels'][0]}..{j['labels'][-1]} ({j['n']} months), top-6 minus bottom-6 "
              f"52-week-high nearness (adjclose / max of the 252 sessions ending t), zero-investment, 5 bps per side on "
              f"drift-adjusted turnover ({_pc(j['cost_mean'], 3)}/month) + 50 bps/yr borrow on the short leg: net mean "
              f"{_pc(mt.get('est'), 3)}/month ({_ci(mt.get('ci'), 3)}, studentized CBB, 12-month blocks, {N_BOOT:,} draws x "
              f"{REPS} seeds); within-month rank-permutation null ({N_PERM:,}, cost-matched): 95th pct {_pc(p['q95'], 3)}, "
              f"p {p['p']:.3f}; DSR over the 8 declared trials (k 6/4 x hold 1/6 x long-short/long-only) {_dsr_txt(d)}. "
              f"Diagnostic (not a criterion): nearness minus 12-1 long/short {_pc(j['vs_12_1']['mean_diff'], 3)}/month "
              f"({_ci(j['vs_12_1']['ci'], 3)}); by decade " + "; ".join(f"{k} {_pc(v['mean'], 3)} ({v['n']})" for k, v in j["decade"].items())
              + f". Annualised trial Sharpes: {_fmt_family(j['family_sharpe_ann'])} — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]], "mean": mt.get("est"), "ci": mt.get("ci"),
            "ci_mc_se": mt.get("ci_mc_se"), "gross_mean": j["gross_mean"], "cost_mean": j["cost_mean"], "borrow_mean": j["borrow_mean"],
            "turnover_mean": j["turnover_mean"], "perm": j["perm"], "dsr": j["dsr"], "vs_12_1": j["vs_12_1"], "decade": j["decade"],
            "family": [list(v) for v in T309_FAMILY], "family_sharpe_ann": j["family_sharpe_ann"],
            "names_first": j["names_first"], "all_names_from": j["all_names_from"], "criteria": j["criteria"],
            "rule10": "month-end decisions named by the claim (rule 10(a)); the 6-month variant pools 6 overlapping cohorts"}
    return _out(stat, j["n"], j["verdict"], reason)


# ========================================================================================= T-476 seasonality ==

T476_MIN_N = 260
T476_START, T476_END = "2004-01", "2026-09"
T476_MIN_YEARS = 5
T476_MIN_NAMES = 8
T476_COMMODITY = ("GLD", "SLV", "USO", "DBA")
T476_COST_SPDR = 5e-4
T476_COST_COMM = 10e-4
T476_BORROW = 0.005
T476_FAMILY = tuple((win, k, kind) for win in (20, 10) for k in (4, 3) for kind in ("LS", "LO"))
T476_PRIMARY = (20, 4, "LS")
T476_ENERGY = ("XLE", "USO")


def seasonal_scores(PN: dict, dec: np.ndarray, max_years: int, min_years: int = T476_MIN_YEARS) -> np.ndarray:
    """Score at decision t for the coming month t+1: mean same-calendar-month return (own month-ends) over the most
    recent ``max_years`` earlier years with that month's return defined, NaN with fewer than ``min_years``."""
    labels = PN["labels"]
    pos = PN["pos"]
    N = len(PN["syms"])
    Rm = PN["R_me"]                                # Rm[:, s] = month s+1's return (month-end s -> s+1)
    out = np.full((dec.size, N), np.nan)
    for r, t in enumerate(dec):
        m = labels[t + 1]
        y, mo = int(m[:4]), m[5:7]
        vals = []
        for yy in range(y - 1, y - 1 - 60, -1):
            lab = f"{yy:04d}-{mo}"
            s = pos.get(lab)
            if s is None or s - 1 < 0:
                if lab < labels[0]:
                    break
                continue
            vals.append(Rm[:, s - 1])
        if not vals:
            continue
        V = np.array(vals)                         # most recent first
        for i in range(N):
            vi = V[:, i][np.isfinite(V[:, i])][:max_years]
            if vi.size >= min_years:
                out[r, i] = vi.mean()
    return out


def return_seasonality(series: dict, bills: Bills, start: str = T476_START, end: str = T476_END, min_n: int = T476_MIN_N,
                       family: Sequence[tuple] = T476_FAMILY, borrow_rate: float = T476_BORROW) -> dict:
    """T-476 core."""
    family = tuple(family)
    PN = month_panel(series, "1990-01", _month_add(end, 1))
    labels = PN["labels"]
    syms = PN["syms"]
    T = len(labels)
    dec = np.array([t for t in range(T - 1) if start <= labels[t + 1] <= end], int)
    R = PN["R_ex"][:, dec].T
    scores = {w: seasonal_scores(PN, dec, w) for w in sorted({v[0] for v in family})}
    elig_p = np.isfinite(scores[T476_PRIMARY[0] if T476_PRIMARY in family else family[0][0]]) & np.isfinite(R)
    keep = elig_p.sum(axis=1) >= T476_MIN_NAMES
    dec, R = dec[keep], R[keep]
    scores = {w: s[keep] for w, s in scores.items()}
    hold = [labels[t + 1] for t in dec]
    if dec.size < MIN_MONTHS:
        return {"too_short": True, "n": int(dec.size)}
    rf, nd = _period_bills(bills, [PN["ex_day"][t] for t in dec], [PN["ex_day"][t + 1] for t in dec])
    cost = np.array([T476_COST_COMM if s in T476_COMMODITY else T476_COST_SPDR for s in syms])
    out = {}
    for v in family:
        win, k, kind = v
        el = np.isfinite(scores[win]) & np.isfinite(R)
        W = np.array([rank_weights(scores[win][r], el[r], k, True, kind == "LS") for r in range(dec.size)])
        b = book(W, R, cost, np.full(len(syms), borrow_rate), nd, rf=None if kind == "LS" else rf)
        b["excess"] = b["net"] if kind == "LS" else b["net"] - rf
        out[v] = b
    pkey = T476_PRIMARY if T476_PRIMARY in out else family[0]
    pv = out[pkey]
    elp = np.isfinite(scores[pkey[0]]) & np.isfinite(R)
    core = _monthly_ls_core(pv, {"|".join(map(str, k)): o for k, o in out.items()}, len(family), (R, elp, pkey[1]), min_n)
    # sensitivities and regimes (reported)
    Wp = np.array([rank_weights(scores[pkey[0]][r], elp[r], pkey[1], True, True) for r in range(dec.size)])
    sens = {f"{int(bb * 1e4)}bps": float(book(Wp, R, cost, np.full(len(syms), bb), nd)["net"].mean()) for bb in (0.0, 0.01)}
    ex = np.array([s not in T476_ENERGY for s in syms])
    Wx = np.array([rank_weights(scores[pkey[0]][r], elp[r] & ex, pkey[1], True, True) for r in range(dec.size)])
    bx = book(Wx, R, cost, np.full(len(syms), borrow_rate), nd)
    counts = elp.sum(axis=1)
    entry = {}
    for i, s in enumerate(syms):
        nz = np.flatnonzero(elp[:, i])
        entry[s] = hold[nz[0]] if nz.size else None
    return {**core, "n": int(dec.size), "labels": hold, "net": pv["net"], "gross_mean": float(pv["gross"].mean()),
            "cost_mean": float(pv["cost"].mean()), "borrow_mean": float(pv["borrow"].mean()), "borrow_sensitivity": sens,
            "ex_energy_mean": float(bx["net"].mean()), "decade": _by_decade(pv["net"], hold), "names_first": int(counts[0]) if counts.size else 0,
            "entry": entry, "family_sharpe_ann": {"|".join(map(str, k)): _sr_ann(o["excess"]) for k, o in out.items()},
            "months_dropped": int((~keep).sum())}


def b6c_xs_return_seasonality(archive):
    """T-476."""
    need = [dh(s) for s in U14] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    j = return_seasonality(_load(archive, U14), _bills(archive))
    if j.get("too_short"):
        return _too_short(j["n"], T476_MIN_N, "months", f"hold months {T476_START}..{T476_END} with >= 8 scored ETFs")
    mt, p, d = j["mean_test"], j["perm"], j["dsr"]
    late = ", ".join(f"{s} {e}" for s, e in j["entry"].items() if e and e > j["labels"][0])
    reason = (f"14 declared ETFs ({', '.join(U14)}; a name is scored once it has {T476_MIN_YEARS} earlier same-month returns, "
              f"at most 20 most recent: {j['names_first']} names in the first month, late entries {late}), month-end "
              f"decisions for the coming calendar month, filled at the next session's close, hold months "
              f"{j['labels'][0]}..{j['labels'][-1]} ({j['n']} months), top-4 minus bottom-4, zero-investment, 5 bps per side "
              f"SPDRs and TLT / 10 bps GLD SLV USO DBA ({_pc(j['cost_mean'], 3)}/month) + borrow 50 bps/yr on shorts (the "
              f"claim names no rate; 0 / 100 bps/yr give {_pc(j['borrow_sensitivity']['0bps'], 3)} / "
              f"{_pc(j['borrow_sensitivity']['100bps'], 3)}): net mean {_pc(mt.get('est'), 3)}/month ({_ci(mt.get('ci'), 3)}, "
              f"studentized CBB, 12-month blocks, {N_BOOT:,} draws x {REPS} seeds); within-month rank-permutation null "
              f"({N_PERM:,}, cost-matched): 95th pct {_pc(p['q95'], 3)}, p {p['p']:.3f}; DSR over the 8 declared trials "
              f"(window all/last 10 years x k 4/3 x long-short/long-only) {_dsr_txt(d)}. Reported: ex-energy (XLE, USO "
              f"removed) {_pc(j['ex_energy_mean'], 3)}/month; by decade "
              + "; ".join(f"{k} {_pc(v['mean'], 3)} ({v['n']})" for k, v in j["decade"].items())
              + f"; annualised trial Sharpes: {_fmt_family(j['family_sharpe_ann'])} — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]], "mean": mt.get("est"), "ci": mt.get("ci"),
            "ci_mc_se": mt.get("ci_mc_se"), "gross_mean": j["gross_mean"], "cost_mean": j["cost_mean"], "borrow_mean": j["borrow_mean"],
            "borrow_sensitivity": j["borrow_sensitivity"], "perm": j["perm"], "dsr": j["dsr"], "ex_energy_mean": j["ex_energy_mean"],
            "decade": j["decade"], "entry": j["entry"], "family": [list(v) for v in T476_FAMILY], "family_sharpe_ann": j["family_sharpe_ann"],
            "criteria": j["criteria"], "rule10": "month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================ T-313 commodity-ETF momentum ==

T313_MIN_N = 160
T313_START, T313_END = "2012-12", "2026-09"
T313_MIN_NAMES = 12
T313_THIN = ("CPER", "PALL", "CORN", "WEAT", "SOYB")
T313_BORROWED = ("UNG", "USO")
T313_COSTS = {"low": {"cost": 10e-4, "thin": 10e-4, "borrow": 0.01}, "high": {"cost": 10e-4, "thin": 20e-4, "borrow": 0.03}}
T313_FAMILY = tuple((J, sel, kind) for J in (12, 6, 3) for sel in ("thirds", "3") for kind in ("LS", "LO"))
T313_PRIMARY = (12, "thirds", "LS")
T313_ENERGY = ("USO", "UNG", "DBE")
T313_SUBS = (("2013-2019", "2013-01", "2019-12"), ("2020-2026", "2020-01", "2026-12"))


def _t313_vectors(syms: Sequence[str], reading: str) -> tuple:
    c = T313_COSTS[reading]
    cost = np.array([c["thin"] if s in T313_THIN else c["cost"] for s in syms])
    borrow = np.array([c["borrow"] if s in T313_BORROWED else 0.0 for s in syms])
    return cost, borrow


def commodity_momentum(series: dict, bills: Bills, start: str = T313_START, end: str = T313_END, min_n: int = T313_MIN_N,
                       family: Sequence[tuple] = T313_FAMILY, bench: Optional[tuple] = None) -> dict:
    """T-313 core. Month-end J-1 ranking, next-close fill, both ends of the claim's cost ranges."""
    family = tuple(family)
    PN = month_panel(series, _month_add(start, -15), _month_add(end, 1))
    labels, syms = PN["labels"], PN["syms"]
    T = len(labels)
    dec = np.array([t for t in range(T - 1) if start <= labels[t + 1] <= end and t - 12 >= 0], int)
    R = PN["R_ex"][:, dec].T

    def signal(J):
        return np.array([PN["PME"][:, t - 1] / PN["PME"][:, t - J] - 1 for t in dec]) if dec.size else np.zeros((0, len(syms)))

    sig = {J: signal(J) for J in sorted({v[0] for v in family} | {12})}
    e12 = np.isfinite(sig[12]) & np.isfinite(R)
    keep = e12.sum(axis=1) >= T313_MIN_NAMES
    dec, R = dec[keep], R[keep]
    sig = {J: s[keep] for J, s in sig.items()}
    hold = [labels[t + 1] for t in dec]
    if dec.size < MIN_MONTHS:
        return {"too_short": True, "n": int(dec.size)}
    rf, nd = _period_bills(bills, [PN["ex_day"][t] for t in dec], [PN["ex_day"][t + 1] for t in dec])
    N = len(syms)

    def weights(v, mask=None):
        J, sel, kind = v
        el = np.isfinite(sig[J]) & np.isfinite(R)
        if mask is not None:
            el = el & mask[None, :]
        rows = []
        for r in range(dec.size):
            n = int(el[r].sum())
            k = n // 3 if sel == "thirds" else 3
            if kind == "LS":
                rows.append(rank_weights(sig[J][r], el[r], k, True, True))
            else:
                w = rank_weights(sig[J][r], el[r], k, True, False)
                w[sig[J][r] <= 0] = 0.0                          # absolute filter: the losers' slots stay in bills
                rows.append(w)
        return np.array(rows).reshape(dec.size, N)

    res = {}
    for reading in T313_COSTS:
        cost, borrow = _t313_vectors(syms, reading)
        out = {}
        for v in family:
            W = weights(v)
            b = book(W, R, cost, borrow, nd, rf=None if v[2] == "LS" else rf)
            b["excess"] = b["net"] if v[2] == "LS" else b["net"] - rf
            out[v] = b
        res[reading] = out
    pkey = T313_PRIMARY if T313_PRIMARY in family else family[0]
    Wp = weights(pkey)
    elp = np.isfinite(sig[pkey[0]]) & np.isfinite(R)
    kr = (elp.sum(axis=1) // 3) if pkey[1] == "thirds" else np.full(dec.size, 3)
    k0 = int(kr[0]) if dec.size else 0
    null = perm_null(R, elp, kr, N_PERM)
    rows_ci, rows_dsr, rows_sub, tests, dsrs, subs = [], [], [], {}, {}, {}
    for reading, out in res.items():
        pv = out[pkey]
        mt = mean_test(pv["excess"], BLOCK_M)
        tests[reading] = mt
        rows_ci.append(_ci_row(mt, f"{reading} costs"))
        d = family_dsr(pv["excess"], [_sr_pp(o["excess"]) for o in out.values()], len(family))
        dsrs[reading] = d
        rows_dsr.append(dsr_row(d, f"{reading} costs"))
        sm = {nm: _sub_mean(pv["net"], hold, a, b) for nm, a, b in T313_SUBS}
        subs[reading] = sm
        ok = all(x is not None for x in sm.values()) and all(x["mean"] > 0 for x in sm.values())
        okv = None if any(x is None for x in sm.values()) else ok
        rows_sub.append((f"{reading} costs: " + ", ".join(f"{nm} {_pc(x['mean'], 3) if x else 'n/a'}" for nm, x in sm.items()), okv, False))
    pl = res["low"][pkey]
    prow, pinfo = perm_row(float(pl["net"].mean()), float((pl["gross"] - pl["net"]).mean()), null,
                           "above the 95th percentile of the within-month rank-permutation null (cost-matched, so the same at both cost ends)")
    crit = [all_constructions(rows_ci, "mean monthly net return > 0 with the 95% CI excluding 0 (studentized CBB, 12-month blocks)"),
            prow,
            all_constructions(rows_dsr, f"DSR > {DSR_PASS} over the {len(family)} declared trials"),
            all_constructions(rows_sub, "positive in both sub-periods")]
    v, why = _decide(crit, dec.size, min_n, "months")
    # reported items
    ex = np.array([s not in T313_ENERGY for s in syms])
    cost_h, borrow_h = _t313_vectors(syms, "high")
    elx = elp & ex[None, :]
    Wx = np.array([rank_weights(sig[pkey[0]][r], elx[r], int(elx[r].sum()) // 3, True, True) for r in range(dec.size)]).reshape(dec.size, N)
    ex_mean = float(book(Wx, R, cost_h, borrow_h, nd)["net"].mean()) if dec.size else None
    uso = syms.index("USO") if "USO" in syms else None
    uso2020 = {hold[r]: float(Wp[r, uso]) for r in range(dec.size) if uso is not None and hold[r][:4] == "2020" and Wp[r, uso] != 0}
    bench_mean = None
    if bench is not None and dec.size:
        BP = month_panel({"DBC": bench}, labels[0], labels[-1])
        rb = BP["R_ex"][0, dec]
        okb = np.isfinite(rb)
        bench_mean = float((rb[okb] - rf[okb]).mean()) if okb.any() else None
    return {"n": int(dec.size), "labels": hold, "tests": tests, "dsr": dsrs, "subs": subs, "perm": pinfo, "k": k0,
            "means": {r: float(o[pkey]["net"].mean()) for r, o in res.items()},
            "cost_means": {r: float(o[pkey]["cost"].mean() + o[pkey]["borrow"].mean()) for r, o in res.items()},
            "family_sharpe_ann": {r: {"|".join(map(str, k)): _sr_ann(o["excess"]) for k, o in out.items()} for r, out in res.items()},
            "ex_energy_mean": ex_mean, "uso_2020": uso2020, "dbc_excess_mean": bench_mean,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_xs_commodity_etf_momentum(archive):
    """T-313."""
    need = [dh(s) for s in U13] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bench = None
    if _has(archive, dh("DBC")):                        # benchmark only (reported, never a criterion)
        dd, aa, _ = _daily(archive, dh("DBC"))
        bench = (dd, aa)
    j = commodity_momentum(_load(archive, U13), _bills(archive), bench=bench)
    if j.get("too_short"):
        return _too_short(j["n"], T313_MIN_N, "months", f"hold months {T313_START}..{T313_END} with >= 12 ranked ETFs")
    t, d, s, p = j["tests"], j["dsr"], j["subs"], j["perm"]

    def side(r):
        return (f"{r} costs: mean {_pc(t[r].get('est'), 3)}/month ({_ci(t[r].get('ci'), 3)}), DSR {_dsr_txt(d[r])}, "
                + ", ".join(f"{nm} {_pc(x['mean'], 3) if x else 'n/a'}" for nm, x in s[r].items()))
    reason = (f"13 declared commodity ETFs ({', '.join(U13)}; DBC benchmark only; delisted commodity ETNs, among them "
              f"several iPath notes, are outside the declared 2026-survivor list and excluded by declaration), month-end "
              f"12-1 adjclose ranking, filled at the next session's close, hold months {j['labels'][0]}..{j['labels'][-1]} "
              f"({j['n']} months), top-{j['k']} minus bottom-{j['k']} (thirds), zero-investment. The claim states cost "
              f"ranges, so both ends are run and must agree (low: 10 bps per side, 1%/yr borrow on UNG/USO shorts; high: "
              f"20 bps CPER/PALL/CORN/WEAT/SOYB, 10 bps others, 3%/yr UNG/USO). {side('low')}; {side('high')} (studentized "
              f"CBB, 12-month blocks, {N_BOOT:,} draws x {REPS} seeds; DSR over the 12 declared trials 12-1/6-1/3-1 x "
              f"thirds/3 x long-short/long-only absolute filter). Within-month rank-permutation null ({N_PERM:,}, "
              f"cost-matched): 95th pct {_pc(p['q95'], 3)}, p {p['p']:.3f}. Reported: ex-energy (USO, UNG, DBE removed, "
              f"high costs) {_pc(j['ex_energy_mean'], 3)}/month; DBC excess {_pc(j['dbc_excess_mean'], 3)}/month; USO 2020 "
              f"(April restructuring flagged) weights " + (", ".join(f"{k} {w:+.2f}" for k, w in j["uso_2020"].items()) or "none")
              + " — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]], "means": j["means"], "cost_means": j["cost_means"],
            "tests": {r: {"est": x.get("est"), "ci": x.get("ci"), "ci_mc_se": x.get("ci_mc_se")} for r, x in t.items()},
            "dsr": d, "subs": s, "perm": p, "k": j["k"], "family": [list(v) for v in T313_FAMILY],
            "family_sharpe_ann": j["family_sharpe_ann"], "ex_energy_mean": j["ex_energy_mean"], "uso_2020": j["uso_2020"],
            "dbc_excess_mean": j["dbc_excess_mean"], "cost_readings": T313_COSTS, "criteria": j["criteria"],
            "exclusions": "delisted commodity ETNs (several iPath notes) excluded by declaration; DBC benchmark only",
            "rule10": "month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ==================================================================================== T-482 frog in the pan ==

T482_MIN_N = 250
T482_START, T482_END = "2004-01", "2026-09"
T482_COST_ETF = 5e-4
T482_COST_CRYPTO = 35e-4
T482_FAMILY = tuple((J, split) for J in (12, 6) for split in ("median", "tercile"))
T482_PRIMARY = (12, "median")


def info_discreteness(adj: np.ndarray, j0: int, j1: int) -> tuple:
    """(PRET, ID) over the bars j0 -> j1 of one asset: PRET = adj[j1] / adj[j0] - 1; ID = sign(PRET) x (share of negative
    - share of positive daily returns over bars j0+1..j1)."""
    a = np.asarray(adj[j0:j1 + 1], float)
    pret = a[-1] / a[0] - 1.0
    r = a[1:] / a[:-1] - 1.0
    if r.size == 0:
        return pret, float("nan")
    return pret, float(np.sign(pret) * ((r < 0).mean() - (r > 0).mean()))


def frog_in_pan(series: dict, start: str = T482_START, end: str = T482_END, min_n: int = T482_MIN_N,
                family: Sequence[tuple] = T482_FAMILY, crypto: Sequence[str] = CRYPTO) -> dict:
    """T-482 core: continuous (low-ID) half minus discrete (high-ID) half among positive J-1 formation returns."""
    family = tuple(family)
    PN = month_panel(series, _month_add(start, -15), _month_add(end, 1))
    labels, syms = PN["labels"], PN["syms"]
    T, N = len(labels), len(syms)
    dec = np.array([t for t in range(T - 1) if start <= labels[t + 1] <= end and t - 12 >= 0], int)
    if dec.size < MIN_MONTHS:
        return {"too_short": True, "n": int(dec.size)}
    R = PN["R_ex"][:, dec].T
    cost = np.array([T482_COST_CRYPTO if s in crypto else T482_COST_ETF for s in syms])
    is_c = np.array([s in crypto for s in syms])
    hold = [labels[t + 1] for t in dec]

    def run(v, mask):
        J, split = v
        Wc, Wd = np.zeros((dec.size, N)), np.zeros((dec.size, N))
        obs = np.zeros(dec.size, bool)
        for r, t in enumerate(dec):
            cand = []
            for i in range(N):
                if not mask[i]:
                    continue
                j0, j1 = PN["JME"][i, t - J], PN["JME"][i, t - 1]
                if j0 < 0 or j1 < 0 or j1 <= j0 or PN["JME"][i, t] < 0 or not np.isfinite(R[r, i]):
                    continue
                pret, idv = info_discreteness(series[syms[i]][1], j0, j1)
                if pret > 0 and np.isfinite(idv):
                    cand.append((idv, i))
            m = len(cand)
            k = m // 2 if split == "median" else m // 3
            if k < 1:
                continue
            cand.sort(key=lambda z: z[0])               # stable: ties keep the declared panel order
            lo = [i for _, i in cand[:k]]
            hi = [i for _, i in cand[-k:]]
            Wc[r, lo] = 1.0 / k
            Wd[r, hi] = 1.0 / k
            obs[r] = True
        bc, bd = book(Wc, R, cost), book(Wd, R, cost)
        d = bc["net"] - bd["net"]
        return {"d": d[obs], "obs": obs, "cont": bc["net"][obs], "disc": bd["net"][obs], "labels": [h for h, o in zip(hold, obs) if o]}

    allm = np.ones(N, bool)
    out = {v: run(v, allm) for v in family}
    pkey = T482_PRIMARY if T482_PRIMARY in out else family[0]
    pv = out[pkey]
    x = pv["d"]
    if x.size < MIN_MONTHS:
        return {"too_short": True, "n": int(x.size)}
    mt = mean_test(x, BLOCK_M)
    d = family_dsr(x, [_sr_pp(o["d"]) for o in out.values()], len(family))
    noc = run(pkey, ~is_c)
    crit = [_ci_row(mt, "continuous minus discrete half mean > 0 with the 95% CI excluding 0 (studentized CBB, 12-month blocks)"),
            dsr_row(d, f"DSR > {DSR_PASS} over the {len(family)} declared trials (difference series)"),
            (f"sign holds without crypto (ETF-only mean difference {_pc(float(noc['d'].mean()) if noc['d'].size else None, 3)} over "
             f"{noc['d'].size} months)", bool(noc["d"].size > 0 and noc["d"].mean() > 0), False)]
    v, why = _decide(crit, x.size, min_n, "months")
    nt = mean_test(noc["d"], BLOCK_M) if noc["d"].size > 8 else {}
    return {"n": int(x.size), "labels": pv["labels"], "mean_test": mt, "dsr": d, "no_crypto": {"n": int(noc["d"].size),
            "mean": float(noc["d"].mean()) if noc["d"].size else None, "ci": nt.get("ci")},
            "cont_mean": float(pv["cont"].mean()) if x.size else None, "disc_mean": float(pv["disc"].mean()) if x.size else None,
            "months_without_split": [h for h, o in zip(hold, pv["obs"]) if not o], "decade": _by_decade(x, pv["labels"]),
            "family_sharpe_ann": {"|".join(map(str, k)): _sr_ann(o["d"]) for k, o in out.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_xs_frog_in_the_pan(archive):
    """T-482."""
    need = [dh(s) for s in U21]
    miss = _missing(archive, need)
    if miss:
        return miss
    series = {s: _daily(archive, dh(s))[:2] for s in U21}
    j = frog_in_pan(series)
    if j.get("too_short"):
        return _too_short(j["n"], T482_MIN_N, "months", f"hold months {T482_START}..{T482_END} with >= 2 positive formation returns")
    mt, d = j["mean_test"], j["dsr"]
    reason = (f"21-asset panel ({', '.join(U21)}; an asset joins once it has a month-end 12 months back), month-end "
              f"decisions, 12-1 formation return and information discreteness on the window's own sessions (crypto every "
              f"calendar day), filled at the next session's close (crypto: next UTC day), hold months "
              f"{j['labels'][0]}..{j['labels'][-1]} ({j['n']} months with >= 2 positive formation returns; without a split: "
              f"{', '.join(j['months_without_split']) or 'none'}), each half after its own costs (5 bps ETFs, 25 + 10 bps "
              f"crypto per side): continuous half {_pc(j['cont_mean'], 3)}, discrete half {_pc(j['disc_mean'], 3)}/month, "
              f"difference {_pc(mt.get('est'), 3)} ({_ci(mt.get('ci'), 3)}, studentized CBB, 12-month blocks, {N_BOOT:,} draws "
              f"x {REPS} seeds); DSR over the 4 declared trials (12-1/6-1 x median/terciles) {_dsr_txt(d)}; without crypto "
              f"{_pc(j['no_crypto']['mean'], 3)} over {j['no_crypto']['n']} months ({_ci(j['no_crypto']['ci'], 3)}). By decade "
              + "; ".join(f"{k} {_pc(v['mean'], 3)} ({v['n']})" for k, v in j["decade"].items())
              + f"; annualised trial Sharpes {_fmt_family(j['family_sharpe_ann'])} — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]] if j["labels"] else None, "mean": mt.get("est"),
            "ci": mt.get("ci"), "ci_mc_se": mt.get("ci_mc_se"), "cont_mean": j["cont_mean"], "disc_mean": j["disc_mean"],
            "dsr": d, "no_crypto": j["no_crypto"], "months_without_split": j["months_without_split"], "decade": j["decade"],
            "family": [list(v) for v in T482_FAMILY], "family_sharpe_ann": j["family_sharpe_ann"], "criteria": j["criteria"],
            "rule10": "month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================= T-471 long-horizon country reversal ==

T471_MIN_N = 300
T471_START, T471_END = "1999-04", "2026-09"
T471_COST = 10e-4
T471_BORROW = 0.005
T471_FAMILY = ("36-12", "36-0", "parametric", "long-only")
T471_PRIMARY = "36-12"
T471_HALVES = (("1999-2012", "1999-01", "2012-12"), ("2013-2026", "2013-01", "2026-12"))
T471_HALF_LIFE = 36.0           # months (the library's 3-year half-life; a constant scale in the normalised weights)


def country_reversal(series: dict, start: str = T471_START, end: str = T471_END, min_n: int = T471_MIN_N,
                     family: Sequence[str] = T471_FAMILY) -> dict:
    """T-471 core: month-end trades, signals from month-ends t-36 .. t-12, overlapping cohorts."""
    family = tuple(family)
    PN = month_panel(series, _month_add(start, -40), end)
    labels, syms = PN["labels"], PN["syms"]
    T, N = len(labels), len(syms)
    dec = np.array([t for t in range(T - 1) if start <= labels[t + 1] <= end and t - 36 >= 0], int)
    R = PN["R_me"][:, dec].T
    P = PN["PME"]
    _, nd = _period_bills(None, [PN["me_day"][t] for t in dec], [PN["me_day"][t + 1] for t in dec])
    el = np.array([(PN["JME"][:, t - 36] >= 0) & np.isfinite(P[:, t]) for t in dec]).reshape(dec.size, N) & np.isfinite(R)
    has = el.sum(axis=1) >= 8                              # two names per quartile at least
    dec, R, el = dec[has], R[has], el[has]
    hold = [labels[t + 1] for t in dec]
    nd = nd[has]
    if dec.size < MIN_MONTHS:
        return {"too_short": True, "n": int(dec.size)}
    with np.errstate(invalid="ignore", divide="ignore"):
        s3612 = np.array([P[:, t - 12] / P[:, t - 36] - 1 for t in dec]).reshape(dec.size, N)
        s360 = np.array([P[:, t] / P[:, t - 36] - 1 for t in dec]).reshape(dec.size, N)
    cost = np.full(N, T471_COST)
    borrow = np.full(N, T471_BORROW)
    kq = lambda r: int(el[r].sum()) // 4
    out = {}
    if "36-12" in family:
        C = np.array([rank_weights(s3612[r], el[r], kq(r), False, True) for r in range(dec.size)]).reshape(dec.size, N)
        out["36-12"] = book(overlap(C, 12), R, cost, borrow, nd)
    if "36-0" in family:
        C = np.array([rank_weights(s360[r], el[r], kq(r), False, True) for r in range(dec.size)]).reshape(dec.size, N)
        out["36-0"] = book(overlap(C, 36), R, cost, borrow, nd)
    if "parametric" in family:
        out["parametric"] = book(_balvers_weights(PN, dec, el), R, cost, borrow, nd)
    if "long-only" in family:
        C = np.array([rank_weights(s3612[r], el[r], kq(r), False, False) for r in range(dec.size)]).reshape(dec.size, N)
        b = book(overlap(C, 12), R, cost, rf=np.zeros(dec.size))
        ew = np.array([R[r, el[r]].mean() if el[r].any() else 0.0 for r in range(dec.size)])
        b = {**b, "net": b["net"] - ew}
        out["long-only"] = b
    for b in out.values():
        b["excess"] = b["net"]
    pkey = T471_PRIMARY if T471_PRIMARY in out else family[0]
    pv = out[pkey]
    x = pv["net"]
    mt = mean_test(x, BLOCK_M)
    halves = {nm: _sub_mean(x, hold, a, b) for nm, a, b in T471_HALVES}
    okh = same_sign(halves)
    d = family_dsr(x, [_sr_pp(o["net"]) for o in out.values()], len(family))
    crit = [_ci_row(mt, "95% lower bound of the mean monthly net return > 0 (studentized CBB, 12-month blocks)"),
            ("same sign in both halves: " + ", ".join(f"{nm} {_pc(h['mean'], 3) if h else 'n/a'}" for nm, h in halves.items()),
             okh, False),
            dsr_row(d, f"DSR > {DSR_PASS} over the {len(family)} declared variants")]
    v, why = _decide(crit, x.size, min_n, "months")
    pbo = _pbo([o["net"] for o in out.values()])
    counts = el.sum(axis=1)
    entry = {}
    for i, s in enumerate(syms):
        nz = np.flatnonzero(el[:, i])
        entry[s] = hold[nz[0]] if nz.size else None
    return {"n": int(x.size), "labels": hold, "mean_test": mt, "halves": halves, "dsr": d, "pbo": pbo,
            "sharpe_ann": _sr_ann(x), "cost_mean": float(pv["cost"].mean()), "borrow_mean": float(pv["borrow"].mean()),
            "gross_mean": float(pv["gross"].mean()), "names_first": int(counts[0]) if counts.size else 0, "entry": entry,
            "regimes": {y: _sub_mean(x, hold, f"{y}-01", f"{y}-12") for y in ("2008", "2020")},
            "family_sharpe_ann": {k: _sr_ann(o["net"]) for k, o in out.items()},
            "family_mean": {k: float(o["net"].mean()) for k, o in out.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _balvers_weights(PN: dict, dec: np.ndarray, el: np.ndarray) -> np.ndarray:
    """Balvers-Wu-Gilliland parametric variant: y_i = cumulative log return of country i relative to the equal-weight
    universe since its first month-end; deviation = y_i(t) - mean of y_i over its trailing (up to 120) month-ends;
    weights proportional to minus the cross-sectionally demeaned deviation, one unit long and one short (the 3-year
    half-life scale cancels), held one month."""
    P = PN["PME"]
    N, T = P.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.log(P[:, 1:] / P[:, :-1])                  # lr[:, s-1] = log return of month s
    Y = np.full((N, T), np.nan)
    for s in range(1, T):
        ok = np.isfinite(lr[:, s - 1])
        ew = lr[ok, s - 1].mean() if ok.any() else 0.0
        for i in range(N):
            if ok[i]:
                Y[i, s] = (Y[i, s - 1] if np.isfinite(Y[i, s - 1]) else 0.0) + lr[i, s - 1] - ew
            elif np.isfinite(P[i, s]) and not np.isfinite(Y[i, s - 1]):
                Y[i, s] = 0.0                                # first month-end of a new listing
    W = np.zeros((dec.size, N))
    lam = 1.0 - 0.5 ** (1.0 / T471_HALF_LIFE)
    for r, t in enumerate(dec):
        dev = np.full(N, np.nan)
        for i in range(N):
            if not el[r, i]:
                continue
            hist = Y[i, max(0, t - 119):t + 1]
            hist = hist[np.isfinite(hist)]
            if hist.size >= 36:
                dev[i] = Y[i, t] - hist.mean()
        ok = np.isfinite(dev)
        if ok.sum() < 2:
            continue
        f = -lam * (dev[ok] - dev[ok].mean())
        g = np.abs(f).sum()
        if g > 0:
            W[r, ok] = 2.0 * f / g
    return W


def b6c_xs_country_long_reversal(archive):
    """T-471."""
    need = [dh(s) for s in COUNTRY21]
    miss = _missing(archive, need)
    if miss:
        return miss
    series = {s: _daily(archive, dh(s))[:2] for s in COUNTRY21}
    j = country_reversal(series)
    if j.get("too_short"):
        return _too_short(j["n"], T471_MIN_N, "months", f"hold months {T471_START}..{T471_END} with >= 8 eligible country ETFs")
    mt, d, h = j["mean_test"], j["dsr"], j["halves"]
    late = ", ".join(f"{s} {e}" for s, e in j["entry"].items() if e and e > j["labels"][0])
    pbo = j["pbo"]
    reason = (f"21 iShares country ETFs (none delisted; an ETF joins once it has a month-end 36 months back: "
              f"{j['names_first']} names in the first month, late entries {late}), month-end trades, signal = total return "
              f"from month-end t-36 to t-12, long the bottom quartile and short the top quartile (floor(n/4) names), 12 "
              f"overlapping monthly cohorts, hold months {j['labels'][0]}..{j['labels'][-1]} ({j['n']} months), 10 bps per leg "
              f"per trade ({_pc(j['cost_mean'], 3)}/month) + 50 bps/yr borrow on the short leg: net mean "
              f"{_pc(mt.get('est'), 3)}/month ({_ci(mt.get('ci'), 3)}, studentized CBB, 12-month blocks, {N_BOOT:,} draws x "
              f"{REPS} seeds), annualised Sharpe {_s(j['sharpe_ann'], 2)}; halves "
              + ", ".join(f"{nm} {_pc(x['mean'], 3) if x else 'n/a'}" for nm, x in h.items())
              + f"; DSR over the 4 declared variants (36-12, 36-0 with 36 overlapping cohorts, Balvers parametric, long-only "
              f"bottom quartile minus equal weight) {_dsr_txt(d)}. Reported: PBO over the 4 variants "
              f"{_f(pbo['pbo'] if pbo else None, 2)}; 2008 {_pc((j['regimes']['2008'] or {}).get('mean'), 3)}, 2020 "
              f"{_pc((j['regimes']['2020'] or {}).get('mean'), 3)}/month; variant means "
              + "; ".join(f"{k} {_pc(v, 3)}" for k, v in j["family_mean"].items())
              + ". LOW POWER: about 27 years against a 3-year half-life (fewer than 10 independent reversion cycles) — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]], "mean": mt.get("est"), "ci": mt.get("ci"),
            "ci_mc_se": mt.get("ci_mc_se"), "sharpe_ann": j["sharpe_ann"], "halves": h, "dsr": d, "pbo": pbo,
            "cost_mean": j["cost_mean"], "borrow_mean": j["borrow_mean"], "gross_mean": j["gross_mean"], "entry": j["entry"],
            "regimes": j["regimes"], "family": list(T471_FAMILY), "family_sharpe_ann": j["family_sharpe_ann"],
            "family_mean": j["family_mean"], "criteria": j["criteria"], "label": "LOW-POWER",
            "rule10": "month-end trades named by the claim (rule 10(a)); cohorts overlap (12-month blocks)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================== weekly reversal engine ==

def weekly_book(dp: dict, e: np.ndarray, ws: np.ndarray, L: int, skip: int, H: int = 1, exec_open: bool = False,
                min_back: int = 60, cost: float = 10e-4, borrow: float = 0.0, vol_target: Optional[float] = None,
                gate: Optional[Callable] = None) -> dict:
    """Quintile reversal book on the weekly grid. ``e``: week-end master indices; ``ws``: sample weeks (indices into e,
    each with e[w + 1] (and the session after it for exec_open) in the panel). Week w: formation return over L sessions
    ending at q = e[w] - skip (q = e[w] for exec_open); eligible ETFs have a bar at e[w], a first bar at or before q -
    min_back, (an open at e[w] + 1 for exec_open); long the floor(n/5) lowest, short the floor(n/5) highest, equal
    weight; H > 1 averages the cohorts of weeks w-H+1..w. ``gate(q) -> multiplier`` (VIX). The vol target scales the
    (ungated) book to ``vol_target`` a year from its trailing 60 daily returns through q with the current weights."""
    P, O, real, first, DR = dp["P"], dp["O"], dp["real"], dp["first"], dp["DR"]
    D, N = P.shape
    w_lo = max(0, int(ws[0]) - H + 1)
    C = {}
    for w in range(w_lo, int(ws[-1]) + 1):
        q = int(e[w]) - (0 if exec_open else skip)
        c = np.zeros(N)
        if q - max(L, min_back) >= 0:
            with np.errstate(invalid="ignore", divide="ignore"):
                ret = P[q] / P[q - L] - 1.0
            el = (first <= q - min_back) & real[e[w]] & np.isfinite(ret)
            if exec_open:
                el &= np.isfinite(O[int(e[w]) + 1]) if int(e[w]) + 1 < D else False
            n = int(el.sum())
            c = rank_weights(ret, el, n // 5, long_high=False, short=True)
        C[w] = c
    Wb = np.array([np.mean([C[w - h] for h in range(H) if (w - h) in C], axis=0) for w in ws]).reshape(len(ws), N)
    qs = np.array([int(e[w]) - (0 if exec_open else skip) for w in ws], int)
    scale = np.ones(len(ws))
    if vol_target is not None:
        DRz = np.nan_to_num(DR)
        for r, q in enumerate(qs):
            x = DRz[q - 59:q + 1] @ Wb[r]
            sd = float(x.std(ddof=1)) * math.sqrt(252.0)
            scale[r] = vol_target / sd if sd > 1e-12 else 0.0
    mult = np.array([gate(int(q)) for q in qs], float) if gate is not None else np.ones(len(ws))
    W = Wb * (scale * mult)[:, None]
    e0 = e[ws].astype(int)
    e1 = e[ws + 1].astype(int)
    if exec_open:
        o0, o1 = O[np.minimum(e0 + 1, D - 1)], O[np.minimum(e1 + 1, D - 1)]
        o1 = np.where(np.isfinite(o1), o1, P[np.minimum(e1 + 1, D - 1)])
        with np.errstate(invalid="ignore", divide="ignore"):
            R = o1 / o0 - 1.0
    else:
        R = P[e1] / P[e0] - 1.0
    hold_days = (dp["ords"][e1] - dp["ords"][e0]).astype(float)
    b = book(W, R, np.full(N, cost), np.full(N, borrow) if borrow else None, hold_days if borrow else None)
    b.update(scale=scale, mult=mult, q=qs, W=W)
    return b


def _week_sample(dp: dict, e: np.ndarray, a: str, z: str, need_after: int = 1) -> np.ndarray:
    days = dp["days"]
    D = len(days)
    return np.array([w for w in range(len(e) - 1) if a <= days[e[w]] <= z and e[w + 1] + need_after < D], int)


# ================================================================================= T-319 weekly reversal ==

T319_MIN_N = 500
T319_START, T319_END = "2010-01-01", "2026-09-30"
T319_COST = 10e-4
T319_BORROW = 0.005
T319_TARGET = 0.10
T319_MIN_BACK = 60
T319_FAMILY = (("1w", 1, False, "close"), ("1w", 0, False, "close"), ("1w", 1, True, "close"), ("1w", 0, True, "close"),
               ("1m", 1, False, "close"), ("1m", 0, False, "close"), ("1m", 1, True, "close"), ("1m", 0, True, "close"),
               ("1w", 0, False, "open"))
T319_PRIMARY = ("1w", 1, False, "close")
T319_HALVES = (("2010-2017", "2010-01-01", "2017-12-31"), ("2018-2026", "2018-01-01", "2026-12-31"))


def _t319_cell(dp, e, ws, v, vt, vixt: Optional[VixTool]):
    form, skip, vix_on, ex = v
    L, H = (5, 1) if form == "1w" else (21, 4)
    gate = None
    if vix_on:
        if vixt is None:
            raise ValueError("VIX needed")
        gate = lambda q: 1.0 if vixt.level(q) > vixt.trailing(q, 2.0 / 3.0) else 0.0
    return weekly_book(dp, e, ws, L, skip, H, ex == "open", T319_MIN_BACK, T319_COST, T319_BORROW, vt, gate)


def xs_short_term_reversal(series: dict, vix: dict, start: str = T319_START, end: str = T319_END, min_n: int = T319_MIN_N,
                           family: Sequence[tuple] = T319_FAMILY) -> dict:
    """T-319 core."""
    family = tuple(family)
    lo = (date.fromisoformat(start).replace(day=1).toordinal() - 500)
    dp = daily_panel(series, date.fromordinal(lo).isoformat(), "9999-12-31")
    e = week_ends(dp["days"])
    ws = _week_sample(dp, e, start, end, need_after=1)
    days = dp["days"]
    ws = np.array([w for w in ws if int(e[w]) - 1 - T319_MIN_BACK >= 0 and
                   int(((dp["first"] <= int(e[w]) - 1 - T319_MIN_BACK) & dp["real"][e[w]]).sum()) >= 5], int)
    if ws.size < MIN_WEEKS:
        return {"too_short": True, "n": int(ws.size)}
    vixt = VixTool(vix, dp["days"])
    labels = [days[e[w]] for w in ws]
    readings = {"vol-targeted": T319_TARGET, "unscaled": None}
    res = {rd: {v: _t319_cell(dp, e, ws, v, vt, vixt) for v in family} for rd, vt in readings.items()}
    pkey = T319_PRIMARY if T319_PRIMARY in family else family[0]
    rows = {"ci": [], "dsr": [], "pbo": [], "half": []}
    info = {}
    for rd, out in res.items():
        x = out[pkey]["net"]
        mt = mean_test(x, BLOCK_W)
        rows["ci"].append(_ci_row(mt, rd))
        d = family_dsr(x, [_sr_pp(o["net"]) for o in out.values()], len(family))
        rows["dsr"].append(dsr_row(d, rd))
        pb = _pbo([o["net"] for o in out.values()])
        rows["pbo"].append((f"{rd} {_f(pb['pbo'] if pb else None, 3)}", None if pb is None else pb["pbo"] < 0.5, False))
        hv = {nm: _sub_mean(x, labels, a, b) for nm, a, b in T319_HALVES}
        okh = same_sign(hv)
        rows["half"].append((f"{rd} " + ", ".join(f"{nm} {_pc(h['mean'], 3) if h else 'n/a'}" for nm, h in hv.items()), okh, False))
        g = out[pkey]
        tom = float(g["turnover"].mean())
        gm = float((g["gross"] - g["borrow"]).mean())
        q = g["q"]
        vl = np.array([vixt.level(int(qq)) for qq in q])
        terc = np.nanquantile(vl, [1 / 3, 2 / 3]) if np.isfinite(vl).any() else [np.nan, np.nan]
        vt_ = {nm: (float(x[m].mean()) if m.any() else None) for nm, m in
               (("low", vl <= terc[0]), ("mid", (vl > terc[0]) & (vl <= terc[1])), ("high", vl > terc[1]))}
        info[rd] = {"mean_test": mt, "dsr": d, "pbo": pb, "halves": hv, "sharpe_ann": _sr_ann(x, 52.0), "mean": float(x.mean()),
                    "gross_mean": float(g["gross"].mean()), "cost_mean": float(g["cost"].mean()), "borrow_mean": float(g["borrow"].mean()),
                    "turnover_mean": tom, "break_even_cost_bps": (gm / tom * 1e4) if tom > 0 else None, "vix_terciles": vt_,
                    "scale_mean": float(g["scale"].mean()), "scale_max": float(g["scale"].max()),
                    "family_sharpe_ann": {"|".join(map(str, k)): _sr_ann(o["net"], 52.0) for k, o in out.items()}}
    crit = [all_constructions(rows["ci"], "95% lower bound of the mean net weekly return > 0 (studentized CBB, 8-week blocks)"),
            all_constructions(rows["dsr"], f"DSR > {DSR_PASS} over the {len(family)} variants run"),
            all_constructions(rows["pbo"], f"CSCV PBO < 0.5 over the {len(family)} variants ({PBO_PARTS} partitions)"),
            all_constructions(rows["half"], "same sign in both halves")]
    n = int(len(ws))
    v, why = _decide(crit, n, min_n, "weeks")
    counts = [int(((dp["first"] <= int(e[w]) - 1 - T319_MIN_BACK) & dp["real"][e[w]]).sum()) for w in ws[:1]]
    return {"n": n, "labels": labels, "info": info, "names_first": counts[0] if counts else 0,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_xs_weekly_etf_reversal(archive):
    """T-319."""
    need = [dh(s) for s in U30] + [VIX_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    j = xs_short_term_reversal(_load(archive, U30), _series(archive, VIX_B))
    if j.get("too_short"):
        return _too_short(j["n"], T319_MIN_N, "weeks", f"weekly entries {T319_START[:7]}..{T319_END[:7]} with >= 5 eligible ETFs")
    a, u = j["info"]["vol-targeted"], j["info"]["unscaled"]

    def side(nm, x):
        mt = x["mean_test"]
        return (f"{nm}: mean {_pc(mt.get('est'), 3)}/week ({_ci(mt.get('ci'), 3)}), annualised Sharpe {_s(x['sharpe_ann'], 2)}, "
                f"DSR {_dsr_txt(x['dsr'])}, PBO {_f(x['pbo']['pbo'] if x['pbo'] else None, 3)}, halves "
                + ", ".join(f"{k} {_pc(h['mean'], 3) if h else 'n/a'}" for k, h in x["halves"].items())
                + f"; gross {_pc(x['gross_mean'], 3)}, costs {_pc(x['cost_mean'], 3)}, borrow {_pc(x['borrow_mean'], 4)}/week, "
                f"break-even {_f(x['break_even_cost_bps'], 1)} bps per unit traded; VIX terciles "
                + "/".join(_pc(x["vix_terciles"][k], 3) for k in ("low", "mid", "high")))
    reason = (f"declared 30 ETFs (9 SPDRs + 21 iShares country ETFs; {j['names_first']} eligible in the first week; EZA "
              f"from 2003, EWT/EWY/EWZ from 2000; survivor list, none delisted), weekly at the last trading day's close, "
              f"5-session total return ending at close t-1, long the bottom quintile and short the top quintile "
              f"(floor(n/5) each), hold to the next week's last close, entries {j['labels'][0]}..{j['labels'][-1]} "
              f"({j['n']} weeks), 10 bps per leg per trade + 50 bps/yr borrow. Both readings must pass (the rule's 10% vol "
              f"target from the book's trailing 60 sessions, and the unscaled book): {side('vol-targeted', a)} (scale mean "
              f"{_f(a['scale_mean'], 2)}, max {_f(a['scale_max'], 2)}); {side('unscaled', u)}. Studentized CBB, 8-week "
              f"blocks, {N_BOOT:,} draws x {REPS} seeds; DSR and CSCV PBO over the 9 variants run (1-week / 1-month "
              f"(21 sessions, 4-week overlapping hold) x skip / no skip x VIX top-tercile gate off/on, and the next-open "
              f"variant); annualised variant Sharpes (vol-targeted) {_fmt_family(a['family_sharpe_ann'])}. Country-ETF "
              f"asynchrony (premium reversion) is part of what this tests (flagged); the S&P 500 stock variant is outside "
              f"the ETF claim — " + j["why"])
    stat = {"n_weeks": j["n"], "window": [j["labels"][0], j["labels"][-1]],
            "readings": {k: {kk: vv for kk, vv in x.items() if kk != "mean_test"} | {"ci": x["mean_test"].get("ci"),
                         "ci_mc_se": x["mean_test"].get("ci_mc_se"), "est": x["mean_test"].get("est")} for k, x in j["info"].items()},
            "family": [list(v) for v in T319_FAMILY], "names_first": j["names_first"], "criteria": j["criteria"],
            "rule10": "weekly calendar named by the claim (last trading day of the week, rule 10(a)); the 1-month variant "
                      "pools 4 overlapping weekly cohorts"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-462 reversal and VIX ==

T462_MIN_N = 500
T462_START, T462_END = "2007-01-01", "2026-09-30"
T462_SPLIT = "2017-01-01"
T462_COST = 10e-4
T462_MIN_BACK = 22              # the longest declared formation (21 sessions) + the skip day
T462_CELLS = tuple((L, skip, vix) for L in ("1w", "1m") for skip in (1, 0) for vix in (False, True))
T462_N_TRIALS = 18
T462_YEARS = ("2008", "2020")


def _t462_cell(dp, e, ws, v, vixt: VixTool):
    L, skip, vix_on = v
    gate = (lambda q: 2.0 if vixt.level(q) > vixt.trailing(q, 0.5) else 1.0) if vix_on else None
    return weekly_book(dp, e, ws, 5 if L == "1w" else 21, skip, 1, False, T462_MIN_BACK, T462_COST, 0.0, None, gate)


def reversal_liquidity(series: dict, vix: dict, start: str = T462_START, end: str = T462_END, split: str = T462_SPLIT,
                       min_n: int = T462_MIN_N, cells: Sequence[tuple] = T462_CELLS, n_trials: int = T462_N_TRIALS) -> dict:
    """T-462 core over the ETF cells (the crypto cells are not archived)."""
    cells = tuple(cells)
    lo = date.fromordinal(date.fromisoformat(start).toordinal() - 500).isoformat()
    dp = daily_panel(series, lo, "9999-12-31")
    e = week_ends(dp["days"])
    ws = _week_sample(dp, e, start, end, need_after=1)
    days = dp["days"]
    ws = np.array([w for w in ws if int(e[w]) - 1 - T462_MIN_BACK >= 0 and
                   int(((dp["first"] <= int(e[w]) - 1 - T462_MIN_BACK) & dp["real"][e[w]]).sum()) >= 5], int)
    labels = [days[e[w]] for w in ws]
    ins = np.array([l < split for l in labels], bool)
    if ws.size < MIN_WEEKS or ins.sum() < 52 or (~ins).sum() < 52:
        return {"too_short": True, "n": int(ws.size)}
    vixt = VixTool(vix, dp["days"])
    out = {v: _t462_cell(dp, e, ws, v, vixt) for v in cells}
    is_sh = {v: _sr_pp(o["net"][ins]) for v, o in out.items()}
    sel = max(cells, key=lambda v: (is_sh[v] if is_sh[v] is not None else -1e9))
    x = out[sel]["net"]
    oos = x[~ins]
    h = hac_mean(oos)
    full_sh = [_sr_pp(o["net"]) for o in out.values()]
    oos_sh = [_sr_pp(o["net"][~ins]) for o in out.values()]
    row_full, info_full = dsr_bound(x, full_sh, n_trials, "selected cell, 2007-2026 series")
    row_oos, info_oos = dsr_bound(oos, oos_sh, n_trials, "selected cell, out-of-sample series")
    base = (sel[0], sel[1], False)
    bx = out[base]["net"] if base in out else _t462_cell(dp, e, ws, base, vixt)["net"]
    qs = out[sel]["q"]
    hi = np.array([vixt.level(int(q)) > vixt.trailing(int(q), 0.5) for q in qs])
    reg = ols_hac(bx, hi.astype(float), nw_lag(bx.size)) if hi.any() and (~hi).any() else None
    t_v = reg["beta"] / reg["se_beta"] if reg and reg["se_beta"] > 0 else None
    p_v = 1.0 - _N.cdf(t_v) if t_v is not None else None
    crit = [(f"out-of-sample ({split[:4]}-2026) net mean > 0 with HAC p < 0.05 ({_pc(h['mean'], 3)}/week, t {_s(h['t'], 2)}, p "
             f"{_f(h['p'], 4)}, Newey-West lag {h['lag']}, {h['n']} weeks)", None if h["p"] is None else bool(h["mean"] > 0 and h["p"] < ALPHA),
             bool(h["t"] is not None and h["t"] < -_N.inv_cdf(1 - ALPHA))),
            all_constructions([row_full, row_oos], f"DSR >= {DSR_PASS} over the {n_trials} declared cells"),
            (f"higher when VIX is above its 1-year median (selected formation without doubling, 2007-2026: high-minus-low "
             f"{_pc(reg['beta'] if reg else None, 3)}/week, HAC t {_s(t_v, 2)} (Newey-West lag {nw_lag(bx.size)}), p {_f(p_v, 4)})",
             None if p_v is None else bool(reg["beta"] > 0 and p_v < ALPHA), bool(t_v is not None and t_v < -_N.inv_cdf(1 - ALPHA)))]
    v, why = _decide(crit, len(ws), min_n, "weeks")
    pbo = _pbo([o["net"] for o in out.values()])
    yrs = {y: _sub_mean(x, labels, f"{y}-01-01", f"{y}-12-31") for y in T462_YEARS}
    n0 = int(((dp["first"] <= int(e[ws[0]]) - 1 - T462_MIN_BACK) & dp["real"][e[ws[0]]]).sum()) if len(ws) else 0
    n1 = int(((dp["first"] <= int(e[ws[-1]]) - 1 - T462_MIN_BACK) & dp["real"][e[ws[-1]]]).sum()) if len(ws) else 0
    return {"n": int(len(ws)), "n_oos": int((~ins).sum()), "labels": labels, "selected": sel, "is_sharpe": is_sh,
            "oos": h, "dsr_full": info_full, "dsr_oos": info_oos, "vix_diff": {"beta": reg["beta"] if reg else None, "t": t_v,
            "p": p_v, "high_share": float(hi.mean()) if hi.size else None}, "pbo_etf_cells": pbo, "years": yrs,
            "full_mean": float(x.mean()), "names_first": n0, "names_last": n1,
            "cell_sharpe_ann": {"|".join(map(str, k)): _sr_ann(o["net"], 52.0) for k, o in out.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_xs_reversal_vix_liquidity(archive):
    """T-462."""
    need = [dh(s) for s in U68] + [VIX_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    j = reversal_liquidity(_load(archive, U68), _series(archive, VIX_B))
    if j.get("too_short"):
        return _too_short(j["n"], T462_MIN_N, "weeks", f"weekly entries {T462_START[:7]}..{T462_END[:7]} (52+ weeks on each side of {T462_SPLIT[:4]})")
    try:                                                   # optional probe: the crypto half's universe
        cmc = [x.name for x in archive.entries(kind="data") if x.name.startswith(CMC_PREFIX)]
    except Exception:
        cmc = []
    cmc_note = (f"{len(cmc)} cmc-daily-listings bundles are archived but the crypto cells are not implemented here"
                if cmc else f"the 10 crypto cells need {CMC_NAME}, not archived")
    s, o = j["selected"], j["oos"]
    vd = j["vix_diff"]
    reason = (f"declared T-420/T-462 ETF list ({len(U68)} ETFs: the 26 archived ETFs with history by 2006 plus the 42 of "
              f"mandel.data.market_history.ETF60_EXTRA; survivor-drawn, as volume-conditioned-momentum states; an ETF joins "
              f"once it has 22 sessions: {j['names_first']} eligible in the first week, {j['names_last']} in the last), "
              f"weekly at the last trading day's close, bottom-minus-top quintile (floor(n/5) names each side), hold one "
              f"week, 10 bps per leg on drift-adjusted turnover, entries {j['labels'][0]}..{j['labels'][-1]} ({j['n']} weeks). "
              f"Selected on 2007-2016 net Sharpe among the 8 ETF cells: lookback {s[0]}, skip {'on' if s[1] else 'off'}, VIX "
              f"doubling {'on' if s[2] else 'off'} (in-sample weekly Sharpes "
              + "; ".join(f"{'|'.join(map(str, k))} {_s(v, 3)}" for k, v in j["is_sharpe"].items())
              + f"). Out-of-sample {_pc(o['mean'], 3)}/week over {j['n_oos']} weeks (HAC t {_s(o['t'], 2)}, p {_f(o['p'], 4)}); "
              f"DSR at 18 trials: 2007-2026 series at most {_f(j['dsr_full'].get('dsr_upper_bound'))}, out-of-sample at most "
              f"{_f(j['dsr_oos'].get('dsr_upper_bound'))} ({cmc_note}); VIX above its trailing 252-session median "
              f"({_pc(vd['high_share'], 1)} of weeks): high-minus-low {_pc(vd['beta'], 3)}/week (HAC t {_s(vd['t'], 2)}). "
              f"Reported: PBO over the 8 ETF cells {_f(j['pbo_etf_cells']['pbo'] if j['pbo_etf_cells'] else None, 2)} (the "
              f"declared 18-cell PBO needs the crypto cells); 2008 {_pc((j['years']['2008'] or {}).get('mean'), 3)}, 2020 "
              f"{_pc((j['years']['2020'] or {}).get('mean'), 3)}/week; annualised cell Sharpes {_fmt_family(j['cell_sharpe_ann'])} — "
              + j["why"])
    stat = {"n_weeks": j["n"], "n_oos_weeks": j["n_oos"], "window": [j["labels"][0], j["labels"][-1]], "selected": list(s),
            "is_sharpe": {"|".join(map(str, k)): v for k, v in j["is_sharpe"].items()}, "oos": o, "dsr_full": j["dsr_full"],
            "dsr_oos": j["dsr_oos"], "vix_diff": vd, "pbo_etf_cells": j["pbo_etf_cells"], "years": j["years"],
            "cell_sharpe_ann": j["cell_sharpe_ann"], "cells": [list(c) for c in T462_CELLS], "n_trials": T462_N_TRIALS,
            "crypto_cells": cmc_note, "universe": list(U68), "criteria": j["criteria"],
            "rule10": "weekly calendar named by the claim (the Friday close, rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_xs_fifty_two_week_high": b6c_xs_fifty_two_week_high,
    "b6c_xs_return_seasonality": b6c_xs_return_seasonality,
    "b6c_xs_weekly_etf_reversal": b6c_xs_weekly_etf_reversal,
    "b6c_xs_reversal_vix_liquidity": b6c_xs_reversal_vix_liquidity,
    "b6c_xs_country_long_reversal": b6c_xs_country_long_reversal,
    "b6c_xs_commodity_etf_momentum": b6c_xs_commodity_etf_momentum,
    "b6c_xs_frog_in_the_pan": b6c_xs_frog_in_the_pan,
}

THEORY_MAP = {
    "T-309": "b6c_xs_fifty_two_week_high",
    "T-476": "b6c_xs_return_seasonality",
    "T-319": "b6c_xs_weekly_etf_reversal",
    "T-462": "b6c_xs_reversal_vix_liquidity",
    "T-471": "b6c_xs_country_long_reversal",
    "T-313": "b6c_xs_commodity_etf_momentum",
    "T-482": "b6c_xs_frog_in_the_pan",
}
