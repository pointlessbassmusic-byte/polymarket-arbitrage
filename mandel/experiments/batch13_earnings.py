"""
Batch 13, group ``earnings``: the long-window FINRA shorting-flow level sort, the post-sample size premium net of junk
and the dividend-initiation drift (T-627, T-628, T-629), 2026-10-20 web sweep, cluster "earnings".
=====================================================================================================================

  * T-627  Point-in-time S&P 500 members, month-end formations whose entry falls in 2018-11..2026-09: SVR = the mean
           daily FINRA CNMS short_volume / total_volume over the 60 file days ending 5 file days before the month-end
           session t (>= 40 of 60 present); equal-weighted bottom-minus-top quintile held from the t+1 close to the t+21
           close, net of 10 bp round trip per leg and 1%/yr borrow on the short leg. Pass (>= 90 months): EW spread > 0
           with one-sided p < 0.05 (studentized circular block bootstrap, 6-month blocks, 5,000 draws); VW spread > 0
           (point-in-time SEC cover-share caps); FF5+UMD alpha NW(6) t >= 2 through 2026-08; both halves (2018-11..
           2022-09, 2022-10..2026-09) positive; survivorship unable to flip the bound; DSR > 0.95 at 5 trials (T-394's
           4 plus this one).
  * T-628  Monthly French SMB (FF5 2x3, compounded from the daily file) on Mkt-RF, lagged Mkt-RF, HML, RMW, CMA and UMD,
           2013-01..2026-08. Pass (>= 120 months): intercept NW(6) t >= 2; studentized block-bootstrap (12-month
           blocks) lower bound > 0; positive intercept in 2013-01..2019-10 and 2019-11..2026-08; DSR > 0.95 at 35
           trials (T-385's 34 plus this one).
  * T-629  Point-in-time S&P 500 members, 2005-01..2026-09: a cash-dividend ex-date after >= 730 calendar days without
           one (and >= 730 days of price history); SPY-adjusted buy-and-hold return over the 252 sessions from the
           ex-date close, net of 10 bp per side. Pass (>= 60 events after cleaning): one-sided lower 95% bound of the
           mean > 0 (bootstrap clustered by entry month, 10,000 draws); positive in 2005-2015 and 2016-2026;
           calendar-time FF5+UMD alpha NW(12) t >= 2 through 2026-08; survivorship unable to flip the bound.

Data and point in time (declared before any run)
  * Every bundle through ``archive.load``; a row counts only when its ``available_at`` is not after the bundle's capture.
    Prices: the shared daily panel (``panel_cache.daily_panel``, value-identical to ``batch6c_cal._daily``); adjclose is
    the total-return price, close and volume are split-adjusted. A daily bar is known at its close.
  * SURVIVORSHIP. The archive's 901-symbol daily-history set is TODAY's universe (Yahoo answers 404 for delisted names):
    removed, acquired and renamed members are missing. Each harness measures what is missing (T-627 the absent share of
    each quintile leg, exactly, because the CNMS files list delisted symbols; T-629 the point-in-time member-years with
    no usable archived history) and implements the registered "survivorship unable to flip the bound" criterion on it
    (below). The other criteria are judged on the priced names as the registrations design them.
  * Membership: fja05680 change-date snapshots in force on the decision day, then the Wikipedia changes table by
    effective date after the file's last date (``batch6c_events.membership_snapshots``; T-629 adds the current
    constituents snapshot and the 2010-06+ rename edges of ``batch6c_events._tables``).
  * T-627 / CNMS. ``batch13_short_a.cnms_data``: one consolidated row per symbol-day (FINRA's consolidated NMS file
    already sums its reporting facilities; the row's 'market' field lists the contributing ones; the 2018-2021 files are
    FINRA's re-posted sums of the per-facility files), symbols in index spelling (BRK/B -> BRK.B, the T-394 mapping);
    file days with status ok; present = total_volume > 0. The day-d file is available at the end of day d. DECLARED
    READING of "the 60 file days ending 5 file days before t": k = the last file day on or before the month-end session
    t (a missing month-end file moves the window earlier, never later), window = file days k-64..k-5 (60 days, the last
    one 5 file days before t). Quintiles: floor(n/5) names per tail over EVERY member with a signal (priced or not,
    the claim's universe), ties sharing the boundary slots (``batch6c_stockxs.tail_fractions``); leg returns over the
    priced names in each leg; the absent share of each leg is therefore known exactly. A CNMS member is priced when its
    Yahoo EQUITY series passes the FINRA-volume identity check of T-673/T-676 (``batch13_short_b.cnms_base``) and has a
    bar at the entry close. Entry e = t+1, exit x = t+21 (20 sessions), forward-filled total-return prices (a series that
    ends inside a hold is cash from its last close). Costs: 10 bp per leg per round trip (20 bp per month on the L/S, the
    registration's wording; the 10-bp-per-side reading, 40 bp, is reported); borrow 1%/yr x calendar days / 365 on the
    short leg.
  * T-627 VW caps (T-393 rules, ``batch6c_stockxs``): SEC cover shares (``shares_series``: per accession the dei
    EntityCommonStockSharesOutstanding of its latest cover date summed across classes, else us-gaap
    CommonStockSharesOutstanding) accepted before the entry session's 09:30 ET open and at most 15 months old
    (``shares_at``), restated to today's split basis (x the split ratios after the cover date) and multiplied by the
    split-adjusted close at t. DECLARED READING of the class split: the issuer's listed classes are the SEC current-map
    tickers of its CIK that have an archived Yahoo EQUITY bar at t (FINRA's 30-character issue names cannot separate
    preferred and note rows from common classes, so the FINRA row count of T-393 would split Arch Capital or DTE across
    their preferreds); the cover count is split equally across them, and no cap is given when they trade more than 2x
    apart (BRK-A / BRK-B). Names without a cap are left out of VW and counted.
  * T-627 turnover baseline (reported): the same sort on the 60-file-day mean of total off-exchange volume x the split
    factor after the day, over the cover shares on the same basis (per class as above). Sector-neutral version
    (reported): quintile tails within each sector (Wikipedia GICS for current members, SEC SIC via the declared
    ``sic_etf`` map otherwise, both ex post) over the priced members.
  * T-628. ``batch4_fact.ff_monthly``: FF5 + UMD + RF compounded from the daily files to calendar months (complete
    months, one method throughout); the lagged Mkt-RF of 2013-01 is 2012-12's. The bundle file dates and sha256 are
    recorded (French revises its history: the archived file is the vintage). The in-sample context starts 1963-08,
    the first month whose lagged Mkt-RF is in the file (the registration names 1963-07).
  * T-629 / events. Ex-dates and amounts from ``daily-events-<sym>`` (available at the ex-date's 09:30 ET open, so an
    entry at that session's close is point in time; declaration dates are not archived, so entry is later than the
    paper's, a conservative variant). An index ticker maps to its own Yahoo series when the archive has its EQUITY
    daily history and its daily events, the series does not fail the CNMS FINRA-volume identity check of T-394 /
    T-676 while the ticker was a member (2018-08+; this refuses Yahoo's PARA, now Banzai International, which the
    Wikipedia table gives no name to check), and, for a removed member, the Wikipedia name it left under agrees with
    Yahoo's or the SEC's names for the series (``batch13_short_b.ident_ok``; a current member needs no name check); a
    ticker without a usable own series follows the rename edges (old -> new before the rename date). Cash dividends
    (``cash_dividends``): rows with amount > 0, same-day rows summed, and a 'dividend' printed on the ex-date of a split
    row dropped as a reclassification (Transocean 2007-11-27: 0.6996 shares plus $33.03 merger cash; in the window it
    removes only that row). TWO READINGS that every criterion must agree on (rule 11 spirit; added after inspecting the
    detected ex-date list, before any return was computed, and recorded as a deviation): R = the rules above; M = R
    without three rows that are not cash dividends and carry no marker in the data (``T629_CORP_ACTIONS``: Agilent's
    2006 Verigy spin-off, AIG's January 2011 recapitalisation, NOV's 2009-11-30 row). An event is an ex-date
    (amount > 0) of a series whose previous ex-date is >= 730 calendar days earlier (or absent), whose first traded bar
    is >= 730 calendar days earlier, on which the series is a member, and which is an SPY session where the series has
    a traded bar (volume not <= 0); entry = that close, exit = 252 sessions later on SPY's calendar; a series that ends
    inside the window is reinvested in SPY at its last close (its abnormal return stops). Net = BHAR - 2 x 10 bp (the
    stock's round trip; the hedged reading with 10 bp per side on SPY too, 40 bp, is reported). Events whose 252-
    session window passes the last bar are counted and left out. Share classes of one issuer (same SEC CIK, ex-dates
    within 5 days) are merged into one event (the classes' mean). Special dividends are kept (entry cannot know them);
    the ex-post subset with a second ex-date inside the window is reported. Resumptions after a >= 730-day suspension
    satisfy the claim's definition and are events (the 2021-2024 cluster is also reported on its own).

Statistics and readings (declared, conservative where the registration is ambiguous)
  * T-627: ``batch6c_cal.studentized_p_escalated`` with 6-month blocks, 5 seeds x 1,000 resamples (the registered 5,000
    draws) escalated one seed at a time while the Monte-Carlo band of p straddles 0.05 (rule 11); the EW criterion
    passes when the point is positive and p < 0.05 is decided, and fails decisively when the mirror p_less < 0.05.
    Alpha: each month's net spread on the FF5 + UMD daily factors summed over the same sessions (the T-393 convention),
    Newey-West lag 6. Halves by entry date. DSR: ``batch6c_mom.family_dsr`` at 5 trials; only this trial is computed at
    a monthly frequency (T-394's are 5-day event returns), so the trial-Sharpe variance is the house 1/(T-1) floor.
    SURVIVORSHIP CRITERION: absent names in each leg are put DELTA = 5% per month worse than their leg (long leg lower,
    short leg higher), x' = x - DELTA (w_long + w_short) with the exact absent leg shares; T-627 names no tolerance, so
    the one the registry fixed for the same CNMS data and the same unknowns (T-676, 5% per month) is adopted. The row
    passes when the EW bound's side is the same on x' (for a pass) or on x + DELTA (w_long + w_short) (for a failure);
    otherwise it is undecided (rule 9: a data limit). The tipping DELTA (HAC-normal bound, bisection) is reported.
  * T-628: the intercept's studentized circular block bootstrap (12-month blocks): rows (y, X) resampled together, each
    draw re-estimated with its own NW(6) s.e.; "95% lower bound" is read as the lower end of the TWO-sided 95% interval
    (the conservative reading; equivalent to the one-sided p < 0.025), 5 seeds x 2,000 draws escalated while undecided.
    Halves re-estimate the regression. DSR: the monthly factor-hedged series h_t = SMB_t - X_t b (mean = the intercept)
    at 35 trials; trial-Sharpe variance = the larger of the 1/(T-1) floor and the variance of {this trial, the 14 daily
    size-family variants of ``batch4_fact.family_sharpes`` scaled to monthly per-period Sharpes by sqrt(21)} (declared
    conversion; the floor-only DSR is reported). The QMJ arm (a second trial) runs only when an AQR QMJ bundle is
    archived; it is not. Diagnostic (not a criterion): long IJR, long h QUAL, short (1 + h) SPY, h = - the in-sample
    (1963-07..2012-12) RMW loading of SMB, reset to targets on each month's first session at the prior close, 5 bp per
    reset and 0.3%/yr borrow on the short notional, monthly P&L on FF5 + UMD, 2013-08..2026-08.
  * T-629: ``batch7_cal.cluster_p`` (studentized cluster bootstrap) by calendar month of entry, 5 seeds x 2,000 = the
    registered 10,000 draws, escalated while undecided, read two ways that must agree (rule 11; rule 6 blocks at least
    as long as the 12-month overlap): (a) the registered i.i.d. resampling of entry-month clusters, (b) circular blocks
    of 12 consecutive entry-month clusters. "One-sided lower 95% bound > 0" = the point positive and p_greater < 0.05
    decided, in both readings. Halves by entry date (< 2016-01-01). Calendar-time portfolio: each day the equal-weight
    mean of the held events' returns (a merged event's classes share its weight), 10 bp charged on each event's first
    and last held day (weighted by 1 / the names held); a month is an observation when a name is held on every session;
    excess over French RF on FF5 + UMD, NW lag 12, through 2026-08. SURVIVORSHIP CRITERION (rule 9, the T-374 house
    rule "no plausible data could change it"): n_absent = round(events x absent member-years / priced member-years)
    events are added, each its own cluster, at the WORST included net return (for a passing bound) or the BEST (for a
    failing one); the row passes when the bound keeps its side, otherwise it is undecided.
  * Rule 10: T-627 names its calendar (month-end, WYZ): no free phase; the other 20 formation offsets (1..20 sessions
    before month-end) are reported. T-628 is calendar-month factor data; T-629 is event-driven.
  * Verdicts via ``batch6c_cal._judge`` (house rule 5 below min_n).
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch13_short_b as SB
from mandel.experiments import batch4_fact as FACT
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import panel_cache as PC
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.validation.backtest_eval import sharpe_ratio

SEED = 0
SPY_B = "daily-history-SPY"
IJR_B = "daily-history-IJR"
QUAL_B = "daily-history-QUAL"
FJA_B = "fja-sp500-components"
CHG_B = "wikipedia-sp500-changes"
CONS_B = "wikipedia-sp500-constituents"
TICK_B = "sec-company-tickers"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
CNMS_FIRST_B = "finra-regsho-cnms-2018-08"
QMJ_PREFIX = "aqr-qmj"
FACTOR_END = "2026-08-31"
FF6 = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD")

# ---- T-627
T627_ENTRY = ("2018-11-01", "2026-09-30")
T627_LO, T627_HI = 64, 5          # file days k-64..k-5
T627_MIN_PRESENT = 40
T627_HOLD = 21                    # exit at the t+21 close; entry at the t+1 close
T627_COST_RT = 10e-4              # per leg per round trip
T627_BORROW = 0.01                # per year on the short leg
T627_BLOCK = 6
T627_NBOOT, T627_SEEDS = 1000, 5  # 5,000 draws
T627_LAG = 6
T627_MIN_N = 90
T627_SPLIT = "2022-10-01"
T627_EXCL = ("2021-01-01", "2021-03-31")
T627_TRIALS = 5
T627_TIP = 0.05                   # adverse return of absent names per month (T-676's registered tolerance)
T627_OFFSETS = 20
CLASS_RATIO = 2.0

# ---- T-628
T628_OOS = ("2013-01", "2026-08")
T628_IS = ("1963-07", "2012-12")
T628_HALVES = (("2013-01", "2019-10"), ("2019-11", "2026-08"))
T628_LAG = 6
T628_BLOCK = 12
T628_NBOOT, T628_SEEDS = 2000, 5
T628_ALPHA = 0.025                # two-sided 95% interval's lower end
T628_MIN_N = 120
T628_TRIALS = 35
T628_DIAG = ("2013-08-01", "2026-08-31")
T628_DIAG_COST = 5e-4
T628_DIAG_BORROW = 0.003

# ---- T-629
T629_START, T629_END = "2005-01-01", "2026-09-30"
T629_GAP = 730
T629_HIST = 730
T629_H = 252
T629_COST = 10e-4                 # per side
T629_SPLIT = "2016-01-01"
T629_RESUME = ("2021-01-01", "2024-12-31")
T629_MIN_N = 60
T629_NBOOT, T629_SEEDS = 2000, 5  # 10,000 draws
T629_BLOCK_ALT = 12
T629_LAG = 12
T629_MERGE_DAYS = 5
T629_MDE = 0.074
T629_CAL_START = "2001-01-01"     # first session kept (730 days of history before a 2005 event, warm-up)
# Reading M (data validity, declared after inspecting the detected ex-date list, never a return): Yahoo dividend rows
# that are not cash dividends and carry no marker in the archive. Every T-629 criterion must agree between reading R
# (the objective rules only) and reading M (R minus these rows).
T629_CORP_ACTIONS = {
    ("A", "2006-11-01"): "Agilent's distribution of its remaining Verigy shares (spin-off); its first cash dividend is 2012",
    ("AIG", "2011-01-20"): "the warrant distribution of AIG's January 2011 recapitalisation (no cash dividend 2008-2013)",
    ("NOV", "2009-11-30"): "a row 11x the first regular dividend (2010-03-10) with no matching cash dividend",
}


# ================================================================================================= small helpers ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _vintage(archive, *names) -> dict:
    out = {}
    for nm in names:
        try:
            e = archive.get(nm)
            out[nm] = {"created_at": getattr(e, "created_at", None), "sha256": getattr(e, "sha256", None)}
        except (KeyError, AttributeError):
            out[nm] = None
    return out


def mean_test(x, block: int, n_boot: int, n_seeds: int) -> dict:
    """Mean with the house studentized-CBB one-sided p's (escalated while the Monte-Carlo band straddles 0.05) and a
    Newey-West t (lag = block)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    pg, pl, nd = CAL.studentized_p_escalated(x, block, n_boot, SEED, n_seeds)
    nw = SX.nw_mean(x, block)
    return {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "p_greater": pg, "p_less": pl, "draws": nd,
            "nw_t": nw.get("t"), "block": block}


def lb_ok(t: dict, alpha: float = 0.05) -> Optional[bool]:
    """'lower bound > 0': the point positive and p_greater < alpha decided at its Monte-Carlo band."""
    if t.get("mean") is None or not t["mean"] > 0:
        return False
    return None if t.get("p_greater") is None else CAL.decide_p(t["p_greater"], t.get("draws", 1), alpha)


def lb_decisive(t: dict, alpha: float = 0.05) -> bool:
    return CAL.decide_p(t.get("p_less"), t.get("draws", 1), alpha) is True


def halves(x, labels: Sequence[str], split: str) -> list:
    x = np.asarray(x, float)
    h = np.array([d < split for d in labels], bool)
    return [_mean(x[h]), _mean(x[~h])]


def touches(e_days: Sequence[str], x_days: Sequence[str], lo: str, hi: str) -> np.ndarray:
    return np.array([ed <= hi and xd >= lo for ed, xd in zip(e_days, x_days)], bool)


# =============================================================================================== T-627 data ==

def class_columns(archive, pr: dict, sec: dict) -> dict:
    """Listed classes per priced-member CIK: the SEC current-map tickers of the CIK with an archived Yahoo EQUITY daily
    history, as ('m', member column) or ('x', column of XC, the extra classes' split-adjusted closes on pr's days) with
    XF their split factors after each day (raw close = close x factor). The panel is released afterwards."""
    by = defaultdict(list)
    for y, (c, _nm) in sec["tick"].items():
        if c in sec["ciks"]:
            by[c].append(y)
    extra = sorted({y for ys in by.values() for y in ys if y not in pr["col"]})
    days = np.asarray(pr["days"])
    P = PC.daily_panel(archive)
    pidx = {s: k for k, s in enumerate(np.asarray(P.symbols).tolist())}
    keep = [y for y in extra if SX._safe(y) in pidx
            and (SX._meta(archive, SX.dh(y)) or {}).get("instrumentType") == "EQUITY"]
    pdays = np.asarray(P.days)
    pos = np.minimum(np.searchsorted(pdays, days), pdays.size - 1)
    ok = pdays[pos] == days
    XC = np.full((days.size, len(keep)), np.nan)
    if keep:
        cols = np.array([pidx[SX._safe(y)] for y in keep], int)
        XC[ok] = P.close[pos[ok]][:, cols]
    del P
    PC._MEMO.clear()
    XF = np.ones_like(XC)
    for k, y in enumerate(keep):
        for ex, r in SB._splits(archive, y):
            XF[days < ex, k] *= r
    xk = {y: k for k, y in enumerate(keep)}
    cls = {c: [("m", pr["col"][y]) if y in pr["col"] else ("x", xk[y]) for y in sorted(ys) if y in pr["col"] or y in xk]
           for c, ys in by.items()}
    return {"cls": cls, "XC": XC, "XF": XF, "extra": keep}


def sector_labels(archive, pr: dict, sec: dict) -> dict:
    """{Yahoo symbol: sector SPDR label}: Wikipedia GICS for current members, SEC SIC (declared map) otherwise; ex post."""
    wiki = {}
    if SX._has(archive, CONS_B):
        for r in EV._rows(archive, CONS_B):
            v = r.get("value") or {}
            if v.get("symbol"):
                wiki[EV.ysym(EV.ntick(v["symbol"]))] = v
    comp = SX._company_rows(archive, sec["ciks"]) if sec["ciks"] else {}
    out = {}
    for y in pr["syms"]:
        s = None
        if y in wiki:
            s = SX.gics_etf(wiki[y].get("gics_sector") or "", wiki[y].get("gics_sub_industry") or "")
        elif y in sec["tick"] and sec["tick"][y][0] in comp:
            s = SX.sic_etf(comp[sec["tick"][y][0]].get("sic"))
        if s:
            out[y] = s[0]
    return out


def t627_base(archive) -> dict:
    """Prices, the CNMS panel with identity checks, SEC data, membership, the share series (T-393 rules), the listed
    classes, sectors and the CNMS file day -> session map (cached)."""
    def load():
        pr = SB.prices(archive)
        Bc = SB.cnms_base(archive)
        sec = SB.sec_data(archive, pr)
        snaps = SB._snaps(archive)
        facts = SX._sec_facts(archive, frozenset(sec["ciks"]))["facts"] if sec["ciks"] else {}
        ser = {c: SX.shares_series(facts.get(c, ())) for c in sec["ciks"]}
        cl = class_columns(archive, pr, sec)
        sect = sector_labels(archive, pr, sec)
        cal = pr["cal"]
        ci = np.array([cal.pos.get(d, -1) for d in Bc["C"]["iso"]], int)
        syms = Bc["C"]["syms"]
        ysyms = [EV.ysym(s) for s in syms]
        cik = np.array([sec["tick"].get(y, (-1,))[0] if Bc["pj"][k] >= 0 else -1 for k, y in enumerate(ysyms)], np.int64)
        sec_lab = np.array([sect.get(y, "") for y in ysyms], object)
        return {"pr": pr, "Bc": Bc, "sec": sec, "snaps": snaps, "ser": ser, "cl": cl, "ci": ci, "ysyms": ysyms,
                "cik": cik, "sector": sec_lab}
    return CAL._cached(archive, ("b13e_t627",), load)


def class_split(B: dict, c: int, q: int, own_j: int) -> Optional[int]:
    """Number of the issuer's listed classes with a bar at q (the member's own column counted), or None when they trade
    more than CLASS_RATIO apart (raw closes)."""
    pr, cl = B["pr"], B["cl"]
    prices = []
    seen_own = False
    for kind, j in cl["cls"].get(c, []):
        if kind == "m":
            v = pr["C"][q, j] * pr["F"][q, j]
            seen_own |= j == own_j
        else:
            v = cl["XC"][q, j] * cl["XF"][q, j]
        if np.isfinite(v) and v > 0:
            prices.append(float(v))
    if not seen_own:
        v = pr["C"][q, own_j] * pr["F"][q, own_j]
        if np.isfinite(v) and v > 0:
            prices.append(float(v))
    if not prices:
        return None
    if len(prices) > 1 and max(prices) > CLASS_RATIO * min(prices):
        return None
    return len(prices)


def caps_and_turnover(B: dict, q: int, tau: float, i0: int, idx: np.ndarray) -> tuple:
    """(cap, turnover) per CNMS symbol at decision q (NaN where unavailable): cap = split-adjusted close at q x cover
    shares known at ``tau`` (<= 15 months old) x the split ratios after the cover date / listed classes; turnover = the
    mean over file days k-64..k-5 of total volume x the split factor after the day, over the same per-class shares."""
    pr, Bc = B["pr"], B["Bc"]
    C = Bc["C"]
    S = len(C["syms"])
    cap = np.full(S, np.nan)
    shb = np.full(S, np.nan)
    day = pr["cal"].days[q]
    for k in idx:
        j, c = int(Bc["pj"][k]), int(B["cik"][k])
        if j < 0 or c < 0 or c not in B["ser"] or not np.isfinite(pr["C"][q, j]):
            continue
        sa = SX.shares_at(B["ser"][c], tau, day)
        if not sa:
            continue
        n_cls = class_split(B, c, q, j)
        if n_cls is None:
            continue
        basis = sa[0] * SB.split_after(pr["splits"].get(B["ysyms"][k], []), sa[1]) / n_cls
        shb[k] = basis
        cap[k] = float(pr["C"][q, j]) * basis
    a, b = max(0, i0 - T627_LO), i0 - T627_HI
    turn = np.full(S, np.nan)
    if b >= a:
        ci = B["ci"][a:b + 1]
        TV = C["TV"][a:b + 1]
        pj = Bc["pj"]
        j = np.where(pj >= 0, pj, 0)
        F = np.where(ci[:, None] >= 0, pr["F"][np.maximum(ci, 0)][:, j], np.nan)
        X = TV * F
        okd = np.isfinite(X) & (X > 0)
        cnt = okd.sum(axis=0)
        mean = np.where(okd, X, 0.0).sum(axis=0) / np.maximum(cnt, 1)
        good = (cnt >= T627_MIN_PRESENT) & np.isfinite(shb) & (shb > 0) & (pj >= 0)
        turn[good] = mean[good] / shb[good]
    return cap, turn


def sector_tails(sig: np.ndarray, elig: np.ndarray, sector: np.ndarray, high: bool) -> np.ndarray:
    """Quintile tail fractions formed within each sector (floor(n_s / 5) names per tail), summed across sectors."""
    out = np.zeros(sig.size)
    for s in sorted({x for x in sector[elig] if x}):
        m = elig & (sector == s)
        k = int((m & np.isfinite(sig)).sum()) // 5
        if k >= 1:
            out += SX.tail_fractions(sig, m, k, high)
    return out


def t627_formation(B: dict, m: int, hold: int = T627_HOLD, extras: bool = True) -> Optional[dict]:
    """One formation at the month-end session m (signal from file days k-64..k-5, members on m), entry e = m+1, exit
    x = m+hold. None when the hold leaves the data."""
    pr, Bc, snaps = B["pr"], B["Bc"], B["snaps"]
    C = Bc["C"]
    cal = pr["cal"]
    D = len(cal)
    e, x = m + 1, m + hold
    if m < 1 or x >= D:
        return None
    i0 = int(np.searchsorted(C["days"], EV._ed(cal.days[m]), side="right")) - 1
    sig, _cnt = SB.window_svr(C["SV"], C["TV"], i0, T627_LO, T627_HI, T627_MIN_PRESENT)
    mem = EV.members_at(snaps, EV._ed(cal.days[m]))
    ismem = np.array([s in mem for s in C["syms"]], bool)
    U = ismem & np.isfinite(sig)
    nU = int(U.sum())
    k = nU // 5
    fl = SX.tail_fractions(sig, U, k, high=False)
    fs = SX.tail_fractions(sig, U, k, high=True)
    pj = Bc["pj"]
    j = np.where(pj >= 0, pj, 0)
    priced = U & Bc["idok"] & (pj >= 0) & pr["real"][e, j]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(priced, pr["Af"][x, j] / pr["Af"][e, j] - 1.0, np.nan)
    wl_abs = float(fl[~priced].sum() / fl.sum()) if fl.sum() > 0 else float("nan")
    ws_abs = float(fs[~priced].sum() / fs.sum()) if fs.sum() > 0 else float("nan")
    win = (max(0, i0 - T627_LO), i0 - T627_HI)
    f = {"m": m, "e": e, "x": x, "label": cal.days[e], "exit": cal.days[x], "U": nU, "k": k, "fl": fl, "fs": fs,
         "priced": priced, "r": r, "wl_abs": wl_abs, "ws_abs": ws_abs, "n_priced": int(priced.sum()),
         "absent": int((U & ~priced).sum()), "sig": sig,
         "backfilled": bool(C["backfilled"][win[0]:win[1] + 1].any()) if win[1] >= win[0] else False,
         "cdays": (date.fromisoformat(cal.days[x]) - date.fromisoformat(cal.days[e])).days}
    if extras:
        cap, turn = caps_and_turnover(B, m, float(cal.open[e]), i0, np.flatnonzero(U | (ismem & Bc["idok"])))
        f["cap"] = np.where(priced, cap, np.nan)
        UT = ismem & np.isfinite(turn)
        kt = int(UT.sum()) // 5
        f["tl"] = SX.tail_fractions(turn, UT, kt, high=False)
        f["ts"] = SX.tail_fractions(turn, UT, kt, high=True)
        f["kt"] = kt
        el = U & priced & (B["sector"] != "")
        f["sl"] = sector_tails(sig, el, B["sector"], high=False)
        f["ss"] = sector_tails(sig, el, B["sector"], high=True)
    return f


def t627_ls(f: dict, legs: tuple = ("fl", "fs"), weight: str = "ew", cost_rt: float = T627_COST_RT) -> Optional[dict]:
    """Bottom-minus-top L/S of one cohort over the priced names of each leg: EW or cap-weighted (names without a cap
    left out); net = gross - a round trip on each leg - borrow on the short leg."""
    if f is None:
        return None
    fl, fs = f[legs[0]], f[legs[1]]
    pm = f["priced"].astype(float)
    r = np.nan_to_num(f["r"])
    wl, ws = fl * pm, fs * pm
    nocap = 0
    if weight == "vw":
        cap = np.where(np.isfinite(f["cap"]) & (f["cap"] > 0), f["cap"], 0.0)
        nocap = int(((wl > 0) & (cap == 0)).sum() + ((ws > 0) & (cap == 0)).sum())
        wl, ws = wl * cap, ws * cap
    if not (wl.sum() > 0 and ws.sum() > 0):
        return None
    RL, RS = float(wl @ r / wl.sum()), float(ws @ r / ws.sum())
    gross = RL - RS
    net = gross - 2.0 * cost_rt - T627_BORROW * f["cdays"] / 365.0
    return {"RL": RL, "RS": RS, "gross": gross, "net": net, "nocap": nocap}


def t627_series(forms: Sequence[dict], legs: tuple = ("fl", "fs"), weight: str = "ew",
                cost_rt: float = T627_COST_RT) -> dict:
    keys = ("gross", "net", "RL", "RS", "e", "x", "wl_abs", "ws_abs", "U", "k", "absent", "backfilled", "nocap")
    out = {k: [] for k in keys}
    out["label"], out["exit"] = [], []
    for f in forms:
        c = t627_ls(f, legs, weight, cost_rt)
        if c is None:
            continue
        out["label"].append(f["label"]); out["exit"].append(f["exit"])
        for k in ("gross", "net", "RL", "RS", "nocap"):
            out[k].append(c[k])
        for k in ("e", "x", "wl_abs", "ws_abs", "U", "k", "absent", "backfilled"):
            out[k].append(f[k])
    for k in keys:
        out[k] = np.array(out[k], float)
    return out


def t627_survivorship(x: np.ndarray, w: np.ndarray, base_ok: Optional[bool], delta: float = T627_TIP) -> dict:
    """Rule 9 / the registered 'survivorship unable to flip the bound': absent names DELTA per month worse (pass) or
    better (failure) than their legs, x' = x -/+ DELTA w; ok when the EW bound keeps its side, else None."""
    out = {"delta": delta, "w_mean": float(np.mean(w)) if w.size else None}
    if base_ok is None:
        out.update(ok=None, note="the EW bound itself is undecided")
        return out
    xp = x - delta * w if base_ok else x + delta * w
    t = mean_test(xp, T627_BLOCK, T627_NBOOT, T627_SEEDS)
    o = lb_ok(t)
    out["shifted"] = {"mean": t["mean"], "p_greater": t["p_greater"], "draws": t["draws"], "lb_ok": o}
    out["ok"] = (o is True) if base_ok else (o is False)
    if o is None:
        out["ok"] = None
    if out["ok"] is False:
        out["ok"] = None                     # a data limit: the absent names could flip it (undecided, rule 9)
    tv = SB.tipping_value(lambda rr: x + rr * w, T627_BLOCK, -2.0, 2.0)
    out["tipping_delta"] = None if tv is None else -tv
    return out


def b13_earnings_svr_quarterly_level(archive):
    """T-627."""
    miss = B7C._missing(archive, [SPY_B, FJA_B, CHG_B, CNMS_FIRST_B, TICK_B, FF5_B, MOM_B])
    if miss:
        return miss
    B = t627_base(archive)
    pr = B["pr"]
    days = pr["cal"].days
    mes = SB.month_ends(days)
    sel = [m for m in mes if m + 1 < len(days) and T627_ENTRY[0] <= days[m + 1] <= T627_ENTRY[1]]
    forms = [f for f in (t627_formation(B, m) for m in sel) if f is not None and f["k"] >= 1]
    S = t627_series(forms)
    n = len(S["label"])
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} month-end CNMS formations could be built (rule 9)")
    x, labels = S["net"], S["label"]
    t = mean_test(x, T627_BLOCK, T627_NBOOT, T627_SEEDS)
    ew_ok, ew_dec = lb_ok(t), lb_decisive(t)
    V = t627_series(forms, weight="vw")
    vw_mean = _mean(V["net"])
    hv = halves(x, labels, T627_SPLIT)
    fac = SB.factor_table(archive, bab=False)
    Fm = SB.period_factor_sums(days, fac, S["e"].astype(int), S["x"].astype(int), 6)
    alpha = SB.ols_alpha(x, Fm, T627_LAG)
    dsr, dsr_r = SB.dsr_of(x, [x], T627_TRIALS, "DSR > 0.95 at 5 trials (T-394's 4 + this one)")
    w_abs = S["wl_abs"] + S["ws_abs"]
    surv = t627_survivorship(x, w_abs, ew_ok)
    member_months = float(S["U"].sum())
    unpriced_mm = float(S["absent"].sum())
    rows = [(f"EW bottom-minus-top SVR quintile spread > 0 with one-sided p < 0.05 (mean {_pc(t['mean'], 3)} per month "
             f"net, p {CAL._mc(t['p_greater'], t['draws'])}, NW t {_f(t['nw_t'], 2)}, 6-month blocks)", ew_ok, ew_dec),
            (f"VW spread > 0 (SEC cover-share caps, T-393 rules: mean {_pc(vw_mean, 3)} over {V['net'].size} months; "
             f"{int(V['nocap'].sum())} leg-name-months without a cap left out)",
             None if vw_mean is None else bool(vw_mean > 0), False),
            (f"FF5+UMD alpha NW t >= 2 (alpha {_pc(alpha['alpha'], 3)} per month, t {_f(alpha['t'], 2)}, {alpha['n']} months "
             f"through 2026-08, lag {T627_LAG})", None if alpha["t"] is None else bool(alpha["t"] >= 2.0),
             alpha["t"] is not None and alpha["t"] <= -2.0),
            (f"both halves positive (entries 2018-11..2022-09 {_pc(hv[0], 3)}, 2022-10..2026-09 {_pc(hv[1], 3)})",
             None if any(h is None for h in hv) else all(h > 0 for h in hv), False),
            (f"survivorship unable to flip the bound (absent names, {surv['w_mean'] * 100:.1f}% of the two legs' weight on "
             f"average, put {T627_TIP:.0%} per month against the claim on each side: bound "
             f"{'still passes' if surv.get('ok') and ew_ok else 'still fails' if surv.get('ok') else 'flips or is undecided'}; "
             f"tipping adverse return {_pc(surv.get('tipping_delta'))} per month; {unpriced_mm:.0f} of {member_months:.0f} "
             f"member-months with a signal unpriced)", surv.get("ok"), False),
            dsr_r]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T627_MIN_N, "months")

    # ---- reported only
    rep = {"gross_mean": _mean(S["gross"]), "vw": {"mean": vw_mean, "n": int(V["net"].size),
                                                   "nocap_leg_name_months": int(V["nocap"].sum())}}
    per_side = t627_series(forms, cost_rt=2 * T627_COST_RT)
    rep["cost_10bp_per_side"] = {"mean": _mean(per_side["net"]),
                                 "p_greater": mean_test(per_side["net"], T627_BLOCK, T627_NBOOT, T627_SEEDS)["p_greater"]}
    ex = touches(labels, S["exit"], *T627_EXCL)
    rep["excluding_2021q1"] = {**mean_test(x[~ex], T627_BLOCK, T627_NBOOT, T627_SEEDS), "n_dropped": int(ex.sum())}
    bf = S["backfilled"].astype(bool)
    rep["backfilled_vintage"] = {"n": int(bf.sum()), "mean": _mean(x[bf]), "n_other": int((~bf).sum()),
                                 "mean_other": _mean(x[~bf])}
    T = t627_series(forms, legs=("tl", "ts"))
    rep["turnover_baseline"] = {**mean_test(T["net"], T627_BLOCK, T627_NBOOT, T627_SEEDS),
                                "leg_size_mean": float(np.mean([f["kt"] for f in forms]))}
    SN = t627_series(forms, legs=("sl", "ss"))
    rep["sector_neutral"] = mean_test(SN["net"], T627_BLOCK, T627_NBOOT, T627_SEEDS)
    offs = {}
    for o in range(1, T627_OFFSETS + 1):
        fo = [t627_formation(B, m - o, extras=False) for m in sel]
        so = t627_series([f for f in fo if f is not None and f["k"] >= 1])
        offs[o] = _mean(so["net"])
    ov = [v for v in offs.values() if v is not None]
    rep["entry_offsets"] = {"means": offs, "min": min(ov) if ov else None, "max": max(ov) if ov else None,
                            "positive": int(sum(v > 0 for v in ov)), "count": len(ov)}
    rep["survivorship"] = surv
    rep["coverage"] = {"members_with_signal_mean": float(np.mean(S["U"])), "leg_size_mean": float(np.mean(S["k"])),
                       "absent_per_formation_mean": float(np.mean(S["absent"])), "unpriced_member_months": unpriced_mm,
                       "member_months_with_signal": member_months,
                       "absent_leg_share_mean": {"long": float(np.mean(S["wl_abs"])), "short": float(np.mean(S["ws_abs"]))},
                       "cnms_missing_months": B["Bc"]["C"]["missing_months"], "cnms_file_days": int(B["Bc"]["C"]["days"].size),
                       "unpriced_symbols": sorted(s for s, v in B["Bc"]["ident"].items() if not v.startswith("ok"))}
    rep["leg_means"] = {"long": _mean(S["RL"]), "short": _mean(S["RS"])}
    reason = (f"{n} month-end formations, entries {labels[0]}..{labels[-1]}: CNMS short/total volume over file days "
              f"k-64..k-5 (>= 40 present) over point-in-time members (mean {rep['coverage']['members_with_signal_mean']:.0f} "
              f"with a signal, {rep['coverage']['leg_size_mean']:.0f} a leg, {rep['coverage']['absent_per_formation_mean']:.1f} "
              f"unpriced), EW bottom-minus-top quintile held t+1 close -> t+21 close: gross {_pc(rep['gross_mean'], 3)}, net "
              f"of 20 bp and 1%/yr borrow {_pc(t['mean'], 3)} per month (p {CAL._p(t['p_greater'])}); long leg "
              f"{_pc(rep['leg_means']['long'], 3)}, short leg {_pc(rep['leg_means']['short'], 3)}; VW {_pc(vw_mean, 3)}; "
              f"halves {_pc(hv[0], 3)} / {_pc(hv[1], 3)}; FF5+UMD alpha t {_f(alpha['t'], 2)}; DSR {_f(dsr.get('dsr'))}. "
              f"Reported: 10 bp per side {_pc(rep['cost_10bp_per_side']['mean'], 3)}; without Jan-Mar 2021 "
              f"{_pc(rep['excluding_2021q1']['mean'], 3)}; windows with backfilled FINRA files {bf.sum()} months "
              f"{_pc(rep['backfilled_vintage']['mean'], 3)} vs {_pc(rep['backfilled_vintage']['mean_other'], 3)}; turnover "
              f"baseline (off-exchange volume / shares) {_pc(rep['turnover_baseline']['mean'], 3)} (p "
              f"{CAL._p(rep['turnover_baseline']['p_greater'])}); sector-neutral {_pc(rep['sector_neutral']['mean'], 3)} (p "
              f"{CAL._p(rep['sector_neutral']['p_greater'])}); formation offsets 1..20 sessions before month-end "
              f"{_pc(rep['entry_offsets']['min'], 3)}..{_pc(rep['entry_offsets']['max'], 3)} "
              f"({rep['entry_offsets']['positive']} of {rep['entry_offsets']['count']} positive). SURVIVORSHIP: prices are the "
              f"archive's 901-symbol daily-history set (today's universe); {unpriced_mm:.0f} member-months with a CNMS signal "
              f"have no usable price (their quintile is known, their return is not)")
    stat = {"n": n, "primary": t, "halves": hv, "alpha": alpha, "dsr": dsr, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# =============================================================================================== T-628 harness ==

def t628_design(months: Sequence[str], fm: dict, lo: str, hi: str) -> tuple:
    """(months, y = SMB, X = [Mkt-RF, Mkt-RF lagged one calendar month, HML, RMW, CMA, UMD]) for months lo..hi whose
    previous calendar month is in the file."""
    rows = [i for i, mm in enumerate(months) if lo <= mm <= hi and i >= 1 and months[i - 1] == _prev_month(mm)]
    r = np.array(rows, int)
    if r.size == 0:
        return [], np.zeros(0), np.zeros((0, 6))
    X = np.column_stack([fm["Mkt-RF"][r], fm["Mkt-RF"][r - 1], fm["HML"][r], fm["RMW"][r], fm["CMA"][r], fm["UMD"][r]])
    return [months[i] for i in rows], np.asarray(fm["SMB"][r], float), X


def boot_intercept(y, X, block: int, lag: int, n_boot: int, seed: int) -> tuple:
    """Studentized circular block bootstrap of the OLS intercept (rows resampled together, each draw with its own NW
    s.e.): (p_greater for H0 a <= 0, p_less for H0 a >= 0, [2.5%, 97.5%] studentized interval)."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n = y.size
    r0 = SX.ols_nw(y, X, lag)
    a0, s0 = r0["alpha"], r0["se"]
    if a0 is None or not s0 or n < 16:
        return None, None, [None, None]
    rng = np.random.default_rng(seed)
    idx = CAL._boot_idx(rng, n, block, n_boot)
    ts = []
    for b in range(n_boot):
        rb = SX.ols_nw(y[idx[b]], X[idx[b]], lag)
        if rb["alpha"] is not None and rb["se"]:
            ts.append((rb["alpha"] - a0) / rb["se"])
    ts = np.array(ts, float)
    t0 = a0 / s0
    k = ts.size
    q_lo, q_hi = np.quantile(ts, [0.025, 0.975])
    return (float((np.sum(ts >= t0) + 1) / (k + 1)), float((np.sum(ts <= t0) + 1) / (k + 1)),
            [float(a0 - q_hi * s0), float(a0 - q_lo * s0)])


def boot_intercept_escalated(y, X, block: int = T628_BLOCK, lag: int = T628_LAG, n_boot: int = T628_NBOOT,
                             n_seeds: int = T628_SEEDS, alpha: float = T628_ALPHA) -> dict:
    """``boot_intercept`` pooled over seeds (seed, seed + 1, ...), one more seed at a time while either p's Monte-Carlo
    band straddles ``alpha``, up to CAL.MAX_SEEDS."""
    res = []
    while True:
        res.append(boot_intercept(y, X, block, lag, n_boot, SEED + len(res)))
        if res[0][0] is None:
            return {"p_greater": None, "p_less": None, "ci": [None, None], "draws": n_boot * len(res)}
        if len(res) < n_seeds:
            continue
        pg, pl = float(np.mean([r[0] for r in res])), float(np.mean([r[1] for r in res]))
        nd = n_boot * len(res)
        if len(res) >= CAL.MAX_SEEDS or (CAL.decide_p(pg, nd, alpha) is not None and CAL.decide_p(pl, nd, alpha) is not None):
            ci = [float(np.mean([r[2][0] for r in res])), float(np.mean([r[2][1] for r in res]))]
            return {"p_greater": pg, "p_less": pl, "ci": ci, "draws": nd}


def hedge_book(days: Sequence[str], rets: dict, w: dict, cost: float, borrow: float) -> np.ndarray:
    """Daily P&L per unit of a multi-leg book reset to target notionals ``w`` (negative = short) on the first session of
    each month (at the prior close); legs drift in between; ``cost`` per reset, ``borrow`` per year on the short
    notional. Net cash is sum(-w) = 0 for a self-financing book (none is earned)."""
    n = len(days)
    out = np.full(n, np.nan)
    pos = {k: 0.0 for k in w}
    for i in range(n):
        c = 0.0
        if i == 0 or days[i][:7] != days[i - 1][:7]:
            pos = dict(w)
            c = cost
        short = sum(-v for v in pos.values() if v < 0)
        out[i] = sum(pos[k] * rets[k][i] for k in w) - borrow * short / 252.0 - c
        for k in w:
            pos[k] *= 1.0 + rets[k][i]
    return out


def b13_earnings_smb_ex_junk_oos(archive):
    """T-628."""
    miss = B7C._missing(archive, [FF5_B, MOM_B])
    if miss:
        return miss
    months, fm = FACT.ff_monthly(archive)
    ms, y, X = t628_design(months, fm, *T628_OOS)
    n = len(ms)
    if n < 16:
        return _out({"n": n}, n, "inconclusive", f"only {n} out-of-sample months in the French files (rule 9)")
    reg = SX.ols_nw(y, X, T628_LAG)
    a, t_nw = reg["alpha"], reg["t"]
    bt = boot_intercept_escalated(y, X)
    if a is None or not a > 0:
        lb_pass = False
    else:
        lb_pass = None if bt["p_greater"] is None else CAL.decide_p(bt["p_greater"], bt["draws"], T628_ALPHA)
    lb_dec = CAL.decide_p(bt["p_less"], bt["draws"], T628_ALPHA) is True
    hv = []
    for lo, hi in T628_HALVES:
        _m, yh, Xh = t628_design(months, fm, lo, hi)
        hv.append(SX.ols_nw(yh, Xh, T628_LAG))
    h = y - X @ np.asarray(reg["betas"], float)                 # monthly factor-hedged SMB: mean = the intercept
    fam = {}
    try:
        fam = FACT.family_sharpes(archive)
    except (KeyError, FileNotFoundError, ValueError, IndexError):
        fam = {}
    fam_m = [float(v) * math.sqrt(21.0) for v in fam.values() if v is not None and math.isfinite(v)]
    sr_h = float(sharpe_ratio(h))
    d = family_dsr(h, [sr_h] + fam_m, T628_TRIALS)
    d_floor = family_dsr(h, [sr_h], T628_TRIALS)
    dname, dok, ddec = dsr_row(d, f"DSR > 0.95 at {T628_TRIALS} trials (T-385's 34 + this one) of the monthly "
                                  f"factor-hedged SMB")
    rows = [(f"intercept NW t >= 2 (alpha {_pc(a, 3)} per month, t {_f(t_nw, 2)}, lag {T628_LAG}, {n} months "
             f"{ms[0]}..{ms[-1]})", None if t_nw is None else bool(t_nw >= 2.0), t_nw is not None and t_nw <= -2.0),
            (f"studentized block-bootstrap lower bound > 0 (12-month blocks; two-sided 95% interval "
             f"[{_pc(bt['ci'][0], 3)}, {_pc(bt['ci'][1], 3)}], one-sided p {CAL._mc(bt['p_greater'], bt['draws'])} vs 0.025)",
             lb_pass, lb_dec),
            (f"positive intercept in both halves (2013-01..2019-10 {_pc(hv[0]['alpha'], 3)} t {_f(hv[0]['t'], 2)}, "
             f"2019-11..2026-08 {_pc(hv[1]['alpha'], 3)} t {_f(hv[1]['t'], 2)})",
             None if any(x["alpha"] is None for x in hv) else all(x["alpha"] > 0 for x in hv), False),
            (dname, dok, ddec)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T628_MIN_N, "months")

    # ---- reported only
    mi, yi, Xi = t628_design(months, fm, *T628_IS)
    ins = SX.ols_nw(yi, Xi, T628_LAG)
    names = ["Mkt-RF", "Mkt-RF(-1)", "HML", "RMW", "CMA", "UMD"]
    rep = {"in_sample": {"months": f"{mi[0]}..{mi[-1]}" if mi else None, "n": len(mi), "alpha": ins["alpha"], "t": ins["t"],
                         "betas": dict(zip(names, ins["betas"] or []))},
           "oos_betas": dict(zip(names, reg["betas"] or [])), "raw_smb_oos_mean": _mean(y),
           "raw_smb_oos_nw": SX.nw_mean(y, T628_LAG), "bootstrap": bt, "dsr_floor_only": d_floor, "dsr": d,
           "family_daily_sharpes": fam, "vintage": _vintage(archive, FF5_B, MOM_B)}
    qmj = SX._entry_names(archive, QMJ_PREFIX)
    rep["qmj_arm"] = ("not run: no AQR QMJ bundle is archived (the second trial runs when it is fetched)" if not qmj
                      else f"QMJ bundle(s) {qmj} archived but this harness does not implement the arm yet")
    diag = None
    hr = -(ins["betas"][3]) if ins["betas"] else None
    if hr is not None and all(B7C._has(archive, b) for b in (IJR_B, QUAL_B, SPY_B)):
        dd, (ri, rs, rq) = FACT.aligned_returns(FACT._etf(archive, "IJR"), FACT._etf(archive, "SPY"), FACT._etf(archive, "QUAL"))
        keep = [i for i, d0 in enumerate(dd) if T628_DIAG[0] <= d0 <= T628_DIAG[1]]
        dk = [dd[i] for i in keep]
        rets = {"IJR": ri[keep], "QUAL": rq[keep], "SPY": rs[keep]}
        pnl = hedge_book(dk, rets, {"IJR": 1.0, "QUAL": hr, "SPY": -(1.0 + hr)}, T628_DIAG_COST, T628_DIAG_BORROW)
        mm, ym = FACT.sum_monthly(dk, pnl)
        fi = {m0: i for i, m0 in enumerate(months)}
        kk = [i for i, m0 in enumerate(mm) if m0 in fi]
        Fd = np.column_stack([fm[c][[fi[mm[i]] for i in kk]] for c in FF6])
        rd = SX.ols_nw(ym[kk], Fd, T628_LAG)
        diag = {"hedge_ratio_qual": hr, "months": len(kk), "mean": _mean(ym[kk]), "alpha": rd["alpha"], "t": rd["t"],
                "betas": dict(zip(FF6, rd["betas"] or []))}
    rep["diagnostic_ijr_qual_spy"] = diag
    dtxt = ("n/a" if not diag else f"{_pc(diag['mean'], 3)} per month, FF5+UMD alpha {_pc(diag['alpha'], 3)} (t "
            f"{_f(diag['t'], 2)}) with {diag['hedge_ratio_qual']:.2f} QUAL per IJR over {diag['months']} months")
    reason = (f"French SMB (FF5, compounded monthly) on Mkt-RF, lagged Mkt-RF, HML, RMW, CMA, UMD over {n} months "
              f"{ms[0]}..{ms[-1]}: intercept {_pc(a, 3)} per month (NW t {_f(t_nw, 2)}; bootstrap two-sided 95% "
              f"[{_pc(bt['ci'][0], 3)}, {_pc(bt['ci'][1], 3)}]); RMW loading {_f(rep['oos_betas'].get('RMW'), 2)}; halves "
              f"{_pc(hv[0]['alpha'], 3)} / {_pc(hv[1]['alpha'], 3)}; DSR {_f(d.get('dsr'))} (floor-only "
              f"{_f(d_floor.get('dsr'))}); raw SMB {_pc(rep['raw_smb_oos_mean'], 3)} per month. Context: in-sample "
              f"{rep['in_sample']['months']} intercept {_pc(ins['alpha'], 3)} (t {_f(ins['t'], 2)}), RMW loading "
              f"{_f((rep['in_sample']['betas'] or {}).get('RMW'), 2)}. Diagnostic IJR+QUAL-SPY sleeve: {dtxt}. "
              f"{rep['qmj_arm']}. French file {rep['vintage'].get(FF5_B, {}).get('created_at') if rep['vintage'].get(FF5_B) else 'n/a'}. "
              f"Factor level: no survivorship issue; a pass is not a funding signal")
    stat = {"n": n, "alpha": a, "t": t_nw, "halves": [{"alpha": x["alpha"], "t": x["t"]} for x in hv], "criteria": crit,
            "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# =============================================================================================== T-629 data ==

def _span_index(snaps: Sequence[tuple], lo: int, hi: int) -> list:
    """[(from, to_exclusive, members)] of the snapshots in force over epoch days [lo, hi]."""
    eds = [s[0] for s in snaps]
    j0 = max(0, bisect.bisect_right(eds, lo) - 1)
    out = []
    for j in range(j0, len(snaps)):
        a = max(snaps[j][0], lo)
        b = min(snaps[j + 1][0] if j + 1 < len(snaps) else hi + 1, hi + 1)
        if a < b:
            out.append((a, b, snaps[j][1]))
    return out


def cash_dividends(rows) -> tuple:
    """([(ex-date epoch day, amount)] of a daily-events bundle's dividend rows with amount > 0 (same-day rows summed),
    [(ex-date, amount)] dropped as reclassifications): a 'dividend' printed on the ex-date of a split row is a merger
    reclassification or spin-off adjustment (Transocean 2007: 0.6996 shares plus $33.03 cash), not a cash dividend."""
    by = defaultdict(float)
    split_days = set()
    for r in rows:
        v = r.get("value") or {}
        kind = r.get("kind") or v.get("type")
        ex = v.get("ex_date")
        if kind == "split" and ex:
            split_days.add(EV._ed(str(ex)[:10]))
        if kind != "dividend":
            continue
        amt = EV._num(v.get("amount"))
        if amt is None or amt <= 0 or not ex:
            continue
        by[EV._ed(str(ex)[:10])] += amt
    rc = [(EV._iso(d), by.pop(d)) for d in sorted(set(by) & split_days)]
    return sorted(by.items()), rc


def resolve_series(t: str, ed: int, own: dict, succ: dict, depth: int = 0) -> Optional[str]:
    """The Yahoo series behind index ticker ``t`` on epoch day ``ed``: its own usable series, else (before a rename
    out of it) its successor's, recursively; None when neither exists."""
    if own.get(t):
        return own[t]
    if depth > 8:
        return None
    for e, y in sorted(succ.get(t, [])):
        if ed < e:
            return resolve_series(y, ed, own, succ, depth + 1)
    return None


def t629_base(archive) -> dict:
    """Membership, ticker -> series resolution, spells per series, absent member-days, prices on SPY's sessions from
    2001, first traded bars, dividends and CIKs (cached)."""
    def load():
        tb = EV._tables(archive)
        snaps = tb["snaps"]
        lo, hi = EV._ed(T629_START), EV._ed(T629_END)
        spans = _span_index(snaps, lo, hi)
        tickers = sorted(set().union(*[s[2] for s in spans])) if spans else []
        P = PC.daily_panel(archive)
        psym = {s: k for k, s in enumerate(np.asarray(P.symbols).tolist())}
        tick = SX._sec_tickers(archive) if SX._has(archive, TICK_B) else {}
        own, why = {}, {}
        cand = {}
        for t in tickers:
            y = EV.ysym(t)
            if SX._safe(y) not in psym:
                why[t] = "no archived daily history"
                continue
            mt = SX._meta(archive, SX.dh(y)) or {}
            if mt.get("instrumentType") != "EQUITY":
                why[t] = "Yahoo series is not an EQUITY"
                continue
            if not SX._has(archive, SX.de(y)):
                why[t] = "no archived daily events"
                continue
            cand[t] = (y, mt)
        need = {tick[y][0] for t, (y, _m) in cand.items() if t not in tb["current"] and y in tick}
        comp = SX._company_rows(archive, need) if need else {}
        vol_id = SB.cnms_base(archive)["ident"] if SX._has(archive, CNMS_FIRST_B) else {}
        for t, (y, mt) in cand.items():
            if "disagrees" in str(vol_id.get(t, "")):
                why[t] = "Yahoo volume disagrees with FINRA's CNMS volume while a member (T-394 identity check)"
                continue
            if t not in tb["current"]:
                refs = [r for r in (tb["refs"].get(t) or []) if r]
                names = [mt.get("longName") or ""]
                if y in tick:
                    v = comp.get(tick[y][0]) or {}
                    names += [tick[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
                names = [x for x in names if x]
                if refs and names and not any(SB.ident_ok(r, names, t) for r in refs):
                    why[t] = f"Yahoo/SEC names {names[:2]} disagree with the index's {refs[:2]}"
                    continue
            own[t] = y
        succ = defaultdict(list)
        for e, x, y, _w in tb["edges"]:
            succ[x].append((int(e), y))
        spells = defaultdict(list)
        absent_days = defaultdict(int)
        priced_days = 0
        for a, b, mem in spans:
            for t in mem:
                s = resolve_series(t, a, own, succ)
                if s is None:
                    absent_days[t] += b - a
                else:
                    spells[s].append((a, b))
                    priced_days += b - a
        series = sorted(spells)
        pdays = np.asarray(P.days)
        spy = psym["SPY"]
        sess = np.isfinite(P.adjclose[:, spy]) & (pdays >= T629_CAL_START)
        rows = np.flatnonzero(sess)
        cols = np.array([psym[SX._safe(s)] for s in series], int)
        first = {}
        for s, c in zip(series, cols):
            ok = np.isfinite(P.close[:, c]) & ~(P.volume[:, c] <= 0)
            first[s] = EV._ed(str(pdays[np.argmax(ok)])) if ok.any() else None
        A = P.adjclose[rows][:, cols] if cols.size else np.zeros((rows.size, 0))
        V = P.volume[rows][:, cols] if cols.size else np.zeros((rows.size, 0))
        spy_a = P.adjclose[rows, spy].copy()
        days = pdays[rows]
        del P
        PC._MEMO.clear()
        traded = np.isfinite(A) & ~(V <= 0)
        A = np.where(traded, A, np.nan)
        last = np.where(traded.any(axis=0), A.shape[0] - 1 - traded[::-1].argmax(axis=0), -1)
        Af = SX._ffill(A)
        divs, reclass = {}, []
        for s in series:
            divs[s], rc = cash_dividends(EV._rows(archive, SX.de(s)))
            reclass += [(s, d, amt) for d, amt in rc]
        cik = {s: (tick[s][0] if s in tick else None) for s in series}
        lens = sum(b - a for a, b, _m in spans)
        return {"series": series, "col": {s: k for k, s in enumerate(series)}, "spells": dict(spells), "first": first,
                "A": A, "Af": Af, "traded": traded, "last": last, "spy": spy_a, "days": [str(d) for d in days],
                "eds": np.array([EV._ed(str(d)) for d in days], np.int64), "divs": divs, "cik": cik,
                "absent_days": dict(absent_days), "priced_days": priced_days, "why": why, "own": own,
                "span_days": lens, "n_tickers": len(tickers), "edges": len(tb["edges"]), "reclassified": reclass}
    return CAL._cached(archive, ("b13e_t629",), load)


def is_member(spells: Sequence[tuple], ed: int) -> bool:
    return any(a <= ed < b for a, b in spells)


def detect_events(B: dict, lo: str = T629_START, hi: str = T629_END, excl=()) -> tuple:
    """Initiation events (one per series and ex-date) and the counts of ex-dates dropped at each rule; ``excl`` =
    (symbol, ex-date) dividend rows treated as absent (reading M)."""
    lo_e, hi_e = EV._ed(lo), EV._ed(hi)
    pos = {int(e): i for i, e in enumerate(B["eds"])}
    ev, cnt = [], defaultdict(int)
    excl = set(excl)
    for s in B["series"]:
        dv = [(d, a) for d, a in B["divs"].get(s, []) if (s, EV._iso(d)) not in excl]
        for k, (d, amt) in enumerate(dv):
            if not (lo_e <= d <= hi_e):
                continue
            prev = dv[k - 1][0] if k > 0 else None
            if prev is not None and d - prev < T629_GAP:
                continue
            cnt["gap_ok"] += 1
            f0 = B["first"].get(s)
            if f0 is None or d - f0 < T629_HIST:
                cnt["short_price_history"] += 1
                continue
            if not is_member(B["spells"].get(s, []), d):
                cnt["not_member_on_ex_date"] += 1
                continue
            i = pos.get(int(d))
            j = B["col"][s]
            if i is None or not B["traded"][i, j]:
                cnt["no_traded_bar_on_ex_date"] += 1
                continue
            nxt = [x for x, _a in dv[k + 1:]]
            ev.append({"sym": s, "ed": int(d), "day": EV._iso(d), "amount": float(amt), "prev": prev,
                       "e": i, "cik": B["cik"].get(s), "next_divs": nxt,
                       "price": float(B["A"][i, j]) if np.isfinite(B["A"][i, j]) else None})
    return ev, dict(cnt)


def merge_classes(events: Sequence[dict], days: int = T629_MERGE_DAYS) -> list:
    """Share classes of one issuer (same CIK, ex-dates within ``days``) become one event (its classes listed)."""
    out, used = [], set()
    evs = sorted(events, key=lambda v: (v["ed"], v["sym"]))
    for i, a in enumerate(evs):
        if i in used:
            continue
        grp = [a]
        used.add(i)
        if a["cik"] is not None:
            for j in range(i + 1, len(evs)):
                b = evs[j]
                if b["ed"] - a["ed"] > days:
                    break
                if j not in used and b["cik"] == a["cik"]:
                    grp.append(b)
                    used.add(j)
        out.append({**a, "classes": [g["sym"] for g in grp], "members": grp})
    return out


def bhar(Af: np.ndarray, spy: np.ndarray, last: int, e: int, h: int = T629_H) -> Optional[float]:
    """SPY-adjusted buy-and-hold return over sessions e..e+h of one series (None when the window passes the data);
    after the series' last bar the proceeds sit in SPY."""
    x = e + h
    if x >= spy.size or not np.isfinite(Af[e]) or Af[e] <= 0:
        return None
    if last >= x:
        g = Af[x] / Af[e]
    else:
        g = Af[last] / Af[e] * spy[x] / spy[last]
    return float(g - spy[x] / spy[e])


def event_returns(B: dict, events: Sequence[dict], offset: int = 0, cost_side: float = T629_COST) -> np.ndarray:
    """Net BHAR per (merged) event: the classes' mean of BHAR from the session ``offset`` after entry, minus 2 x
    cost_side; NaN when the window is incomplete (or, for a placebo, the series no longer trades at its entry)."""
    out = np.full(len(events), np.nan)
    for i, v in enumerate(events):
        vals = []
        for g in v["members"]:
            j = B["col"][g["sym"]]
            e = g["e"] + offset
            if offset and (e >= B["spy"].size or B["last"][j] < e):
                continue
            r = bhar(B["Af"][:, j], B["spy"], int(B["last"][j]), e)
            if r is not None:
                vals.append(r)
        if vals:
            out[i] = float(np.mean(vals)) - 2.0 * cost_side
    return out


def calendar_time(B: dict, events: Sequence[dict], months: Sequence[str], fm: dict, cost: float = T629_COST) -> dict:
    """Calendar-time EW portfolio of the held events (a merged event's classes share its weight; after a series' last
    bar its slot earns SPY); 10 bp on each slot's first and last held day; monthly excess over RF on FF5 + UMD."""
    D = B["spy"].size
    srt = np.full(D, np.nan)
    srt[1:] = B["spy"][1:] / B["spy"][:-1] - 1.0
    ret, cnt, cst = np.zeros(D), np.zeros(D), np.zeros(D)
    for v in events:
        w = 1.0 / len(v["members"])
        for g in v["members"]:
            j = B["col"][g["sym"]]
            e = g["e"]
            x = min(e + T629_H, D - 1)
            if x <= e:
                continue
            a = B["Af"][e:x + 1, j]
            rs = a[1:] / a[:-1] - 1.0
            L = int(B["last"][j])
            after = np.arange(e + 1, x + 1) > L
            rs = np.where(after, srt[e + 1:x + 1], rs)
            rs = np.where(np.isfinite(rs), rs, 0.0)
            ret[e + 1:x + 1] += w * rs
            cnt[e + 1:x + 1] += w
            cst[e + 1] += w * cost
            if e + T629_H <= D - 1:
                cst[e + T629_H] += w * cost
    held = cnt > 0
    R = np.where(held, (ret - cst) / np.where(held, cnt, 1.0), np.nan)
    by = defaultdict(list)
    for i, d in enumerate(B["days"]):
        by[d[:7]].append(i)
    fi = {m: i for i, m in enumerate(months)}
    ms, y, F = [], [], []
    for m in sorted(by):
        if m not in fi or m > FACTOR_END[:7]:
            continue
        idx = by[m]
        if not held[idx].all():
            continue
        ms.append(m)
        y.append(float(np.prod(1.0 + R[idx]) - 1.0) - float(fm["RF"][fi[m]]))
        F.append([float(fm[c][fi[m]]) for c in FF6])
    y = np.array(y, float)
    F = np.array(F, float).reshape(len(ms), len(FF6))
    reg = SX.ols_nw(y, F, T629_LAG) if len(ms) > len(FF6) + 4 else {"alpha": None, "t": None, "n": len(ms)}
    return {"months": len(ms), "first": ms[0] if ms else None, "last": ms[-1] if ms else None, "alpha": reg.get("alpha"),
            "t": reg.get("t"), "betas": dict(zip(FF6, reg.get("betas") or [])), "mean_excess": _mean(y),
            "series": {"months": ms, "excess": [float(v) for v in y]}}


def cluster_test(x, groups, block: int = 1) -> dict:
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    g = np.asarray(groups)[ok]
    pg, pl, nd = B7C.cluster_p(x[ok], g, T629_NBOOT, SEED, T629_SEEDS, block)
    _p1, _p2, ci = B7C.cluster_boot(x[ok], g, T629_NBOOT, SEED, block)
    return {"n": int(ok.sum()), "mean": _mean(x), "p_greater": pg, "p_less": pl, "draws": nd, "ci_pct": ci, "block": block}


def omission_events(B: dict, lo: str = T629_START, hi: str = T629_END) -> list:
    """Descriptive only: a regular payer (>= 3 ex-dates in the 730 days to its last one) with no ex-date in the 365
    days after it, known at last + 365 days; entry at the first session on or after, while a member."""
    lo_e, hi_e = EV._ed(lo), EV._ed(hi)
    eds = B["eds"]
    out = []
    for s in B["series"]:
        dv = [d for d, _a in B["divs"].get(s, [])]
        for k, d in enumerate(dv):
            nxt = dv[k + 1] if k + 1 < len(dv) else None
            known = d + 365
            if not (lo_e <= known <= hi_e) or (nxt is not None and nxt <= known):
                continue
            if sum(1 for z in dv[:k + 1] if d - z <= 730) < 3:
                continue
            i = int(np.searchsorted(eds, known))
            if i >= eds.size or not is_member(B["spells"].get(s, []), int(eds[i])):
                continue
            j = B["col"][s]
            if B["last"][j] < i:
                continue
            out.append({"sym": s, "ed": int(eds[i]), "day": EV._iso(int(eds[i])), "e": i, "cik": B["cik"].get(s),
                        "next_divs": [], "members": [{"sym": s, "e": i}]})
    return out


def t629_survivorship(x: np.ndarray, groups: np.ndarray, base_ok: Optional[bool], n_abs: int) -> dict:
    """Rule 9 (the T-374 rule): n_abs events added, each its own cluster, at the worst (pass) / best (failure) included
    net return; ok when the bound keeps its side in both cluster readings, else None (undecided)."""
    xs = x[np.isfinite(x)]
    out = {"n_absent_events": int(n_abs), "worst": float(xs.min()) if xs.size else None,
           "best": float(xs.max()) if xs.size else None}
    if base_ok is None or n_abs <= 0 or not xs.size:
        out["ok"] = None if base_ok is None else True
        return out
    val = out["worst"] if base_ok else out["best"]
    g0 = np.asarray(groups)[np.isfinite(x)]
    xa = np.concatenate([xs, np.full(n_abs, val)])
    ga = np.concatenate([g0.astype(object), np.array([f"absent-{k:03d}" for k in range(n_abs)], object)])
    res = []
    for blk in (1, T629_BLOCK_ALT):
        tt = cluster_test(xa, ga.astype(str), blk)
        res.append(lb_ok(tt))
        out[f"block{blk}"] = {"mean": tt["mean"], "p_greater": tt["p_greater"], "draws": tt["draws"]}
    keep = CAL._agree(res)
    out["ok"] = (keep is True) if base_ok else (keep is False)
    if keep is None or out["ok"] is False:
        out["ok"] = None
    m, n0 = float(xs.mean()), xs.size
    out["needed_mean_to_zero"] = float(-m * n0 / n_abs)
    return out


def t629_reading(B: dict, months: Sequence[str], fm: dict, excl=()) -> dict:
    """One event-set reading: detection (``excl`` rows treated as absent), class merge, net BHARs, the two cluster
    bootstraps, halves, the calendar-time alpha and the survivorship check."""
    raw, cnt = detect_events(B, excl=excl)
    evs = merge_classes(raw)
    x_all = event_returns(B, evs)
    done = np.isfinite(x_all)
    events = [v for v, ok in zip(evs, done) if ok]
    x = x_all[done]
    out = {"raw": raw, "counts": dict(cnt), "merged": evs, "events": events, "x": x, "n": int(x.size),
           "incomplete": int((~done).sum())}
    if x.size < 8:
        return out
    groups = np.array([v["day"][:7] for v in events])
    labels = [v["day"] for v in events]
    tA = cluster_test(x, groups, 1)
    tB = cluster_test(x, groups, T629_BLOCK_ALT)
    lb = CAL._agree([lb_ok(tA), lb_ok(tB)])
    yrs_abs = sum(B["absent_days"].values()) / 365.25
    yrs_pr = B["priced_days"] / 365.25
    n_abs = int(round(x.size * yrs_abs / yrs_pr)) if yrs_pr > 0 else 0
    out.update(groups=groups, labels=labels, tA=tA, tB=tB, lb=lb, lb_dec=lb_decisive(tA) and lb_decisive(tB),
               hv=halves(x, labels, T629_SPLIT), ct=calendar_time(B, evs, months, fm),
               surv=t629_survivorship(x, groups, lb, n_abs), yrs_abs=yrs_abs, yrs_pr=yrs_pr, n_abs=n_abs)
    return out


def _both(a: Optional[bool], b: Optional[bool]) -> Optional[bool]:
    return CAL._agree([a, b])


def b13_earnings_dividend_initiation(archive):
    """T-629."""
    miss = B7C._missing(archive, [SPY_B, FJA_B, CHG_B, CONS_B, TICK_B, FF5_B, MOM_B, SX.de("AAPL")])
    if miss:
        return miss
    B = t629_base(archive)
    months, fm = FACT.ff_monthly(archive)
    R = t629_reading(B, months, fm)
    Mr = t629_reading(B, months, fm, excl=set(T629_CORP_ACTIONS))
    n = R["n"]
    if n < 8 or Mr["n"] < 8:
        return _out({"n": n, "counts": R["counts"]}, n, "inconclusive", f"only {n} complete initiation events (rule 9)")
    x, tA, tB, hv, ct, surv = R["x"], R["tA"], R["tB"], R["hv"], R["ct"], R["surv"]

    def hv_ok(r):
        return None if any(h is None for h in r["hv"]) else all(h > 0 for h in r["hv"])

    def ct_ok(r):
        return None if r["ct"]["t"] is None else bool(r["ct"]["t"] >= 2.0)

    def ct_dec(r):
        return r["ct"]["t"] is not None and r["ct"]["t"] <= -2.0

    yrs_abs, yrs_pr = R["yrs_abs"], R["yrs_pr"]
    share_abs = yrs_abs / max(yrs_abs + yrs_pr, 1e-9)
    rows = [(f"one-sided lower 95% bound of the mean > 0 (R: mean net {_pc(tA['mean'])}, entry-month clusters i.i.d. p "
             f"{CAL._mc(tA['p_greater'], tA['draws'])}, 12-month cluster blocks p {CAL._mc(tB['p_greater'], tB['draws'])}; "
             f"M: mean {_pc(Mr['tA']['mean'])}, p {CAL._mc(Mr['tA']['p_greater'], Mr['tA']['draws'])} / "
             f"{CAL._mc(Mr['tB']['p_greater'], Mr['tB']['draws'])}; all four must agree)",
             _both(R["lb"], Mr["lb"]), R["lb_dec"] and Mr["lb_dec"]),
            (f"positive in both halves (R: 2005-2015 {_pc(hv[0])}, 2016-2026 {_pc(hv[1])}; M: {_pc(Mr['hv'][0])} / "
             f"{_pc(Mr['hv'][1])})", _both(hv_ok(R), hv_ok(Mr)), False),
            (f"calendar-time FF5+UMD alpha NW(12) t >= 2 (R: alpha {_pc(ct['alpha'], 3)} per month, t {_f(ct['t'], 2)}, "
             f"{ct['months']} months {ct['first']}..{ct['last']}; M: t {_f(Mr['ct']['t'], 2)})",
             _both(ct_ok(R), ct_ok(Mr)), ct_dec(R) and ct_dec(Mr)),
            (f"survivorship unable to flip the bound ({yrs_abs:.0f} of {yrs_abs + yrs_pr:.0f} point-in-time member-years "
             f"({share_abs * 100:.1f}%) have no usable archived history: about {R['n_abs']} events unseen, put at the "
             f"{'worst' if R['lb'] else 'best'} included net return "
             f"{_pc(surv.get('worst') if R['lb'] else surv.get('best'))}: R "
             f"{'keeps its side' if surv.get('ok') else 'could flip / undecided'}, M "
             f"{'keeps its side' if Mr['surv'].get('ok') else 'could flip / undecided'})",
             _both(surv.get("ok"), Mr["surv"].get("ok")), False)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T629_MIN_N, "events")

    # ---- reported only (reading R unless named)
    events, labels, groups = R["events"], R["labels"], R["groups"]
    rep = {"counts": {**R["counts"], "raw_events": len(R["raw"]), "merged_events": len(R["merged"]), "complete": n,
                      "incomplete_window": R["incomplete"], "reading_M_complete": Mr["n"]}}
    rep["gross_mean"] = _mean(x + 2 * T629_COST)
    rep["hedged_40bp_mean"] = _mean(x - 2 * T629_COST)
    rep["ci_pct_block1"] = tA["ci_pct"]
    rep["sd_per_event"] = float(np.std(x, ddof=1))
    rep["mde_stated"] = T629_MDE
    pl = event_returns(B, events, offset=T629_H)
    rep["placebo_post_window"] = cluster_test(pl, groups, 1) if np.isfinite(pl).sum() >= 8 else {"n": int(np.isfinite(pl).sum())}
    res = np.array([T629_RESUME[0] <= d <= T629_RESUME[1] for d in labels])
    rep["resumption_2021_2024"] = {"n": int(res.sum()), "mean": _mean(x[res]), "mean_other": _mean(x[~res])}
    exits = [B["days"][min(v["e"] + T629_H, len(B["days"]) - 1)] for v in events]
    second = np.array([any(EV._iso(z) <= xd for z in v["next_divs"]) for v, xd in zip(events, exits)])
    rep["second_dividend_in_window"] = {"n": int(second.sum()), "mean": _mean(x[second]), "n_other": int((~second).sum()),
                                        "mean_other": _mean(x[~second])}
    om = omission_events(B)
    xo = event_returns(B, om)
    rep["omission_leg_descriptive"] = {"n": int(np.isfinite(xo).sum()), "mean": _mean(xo)}
    rep["calendar_time"] = {"R": ct, "M": Mr["ct"]}
    rep["survivorship"] = {"R": surv, "M": Mr["surv"]}
    rep["reading_M"] = {"excluded_rows": {f"{k[0]} {k[1]}": v for k, v in T629_CORP_ACTIONS.items()},
                        "n": Mr["n"], "block1": Mr["tA"], "block12": Mr["tB"], "halves": Mr["hv"]}
    rep["reclassified_rows"] = [f"{s} {d} {a:g}" for s, d, a in B["reclassified"]]
    rep["coverage"] = {"index_tickers": B["n_tickers"], "series": len(B["series"]), "member_years_priced": yrs_pr,
                       "member_years_absent": yrs_abs, "tickers_without_series": len(B["why"]), "rename_edges": B["edges"],
                       "identity_refused": sorted(t for t, w in B["why"].items() if "disagree" in w)}
    rep["events"] = [{"sym": "/".join(v["classes"]), "day": v["day"], "amount": v["amount"],
                      "prev": EV._iso(v["prev"]) if v["prev"] else None, "net": float(r)} for v, r in zip(events, x)]
    reason = (f"{n} dividend initiations (ex-date after >= 730 days without one, >= 730 days of price history) on point-in-"
              f"time S&P 500 members, entries {labels[0]}..{labels[-1]} ({len(R['raw'])} raw, {len(R['merged'])} after merging "
              f"share classes, {R['incomplete']} with an incomplete 252-session window; reading M without "
              f"{len(T629_CORP_ACTIONS)} corporate-action rows: {Mr['n']}): mean SPY-adjusted 252-session BHAR net of 20 bp "
              f"{_pc(tA['mean'])} (gross {_pc(rep['gross_mean'])}, per-event s.d. {_pc(rep['sd_per_event'])}; registered MDE "
              f"about 7.4 pp); p {CAL._p(tA['p_greater'])} / {CAL._p(tB['p_greater'])}; halves {_pc(hv[0])} / {_pc(hv[1])}; "
              f"calendar-time FF5+UMD alpha {_pc(ct['alpha'], 3)} per month (t {_f(ct['t'], 2)}). Reported: 40 bp (hedged) "
              f"{_pc(rep['hedged_40bp_mean'])}; placebo (the next 252 sessions) {_pc(rep['placebo_post_window'].get('mean'))}; "
              f"2021-2024 resumptions {rep['resumption_2021_2024']['n']} at {_pc(rep['resumption_2021_2024']['mean'])} vs "
              f"{_pc(rep['resumption_2021_2024']['mean_other'])}; ex post with a second ex-date in the window "
              f"{rep['second_dividend_in_window']['n']} at {_pc(rep['second_dividend_in_window']['mean'])} vs "
              f"{_pc(rep['second_dividend_in_window']['mean_other'])}; omissions (descriptive) "
              f"{rep['omission_leg_descriptive']['n']} at {_pc(rep['omission_leg_descriptive']['mean'])}. SURVIVORSHIP: the "
              f"901-symbol daily-history set is today's universe; detection itself needs an archived history, so "
              f"{share_abs * 100:.1f}% of member-years are unseen")
    stat = {"n": n, "block1": tA, "block12": tB, "halves": hv, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


HARNESSES = {"b13_earnings_svr_quarterly_level": b13_earnings_svr_quarterly_level,
             "b13_earnings_smb_ex_junk_oos": b13_earnings_smb_ex_junk_oos,
             "b13_earnings_dividend_initiation": b13_earnings_dividend_initiation}
THEORY_MAP = {"T-627": "b13_earnings_svr_quarterly_level", "T-628": "b13_earnings_smb_ex_junk_oos",
              "T-629": "b13_earnings_dividend_initiation"}
