"""
Batch 13, group ``short_b``: single-stock short interest and shorting flow cross-sections on point-in-time S&P 500
members (T-675, T-676, T-677), 2026-10-20 web sweep, cluster "short".
=====================================================================================================================

  * T-675  Low short interest, long-only. At every FINRA short-interest release with an entry 2018-01..2026-09: the
           eligible set = point-in-time members with a FINRA row, a cover-share value and an archived price, cut to the
           top half by trailing 60-session median dollar volume; the equal-weighted bottom quintile of SIR = short
           interest / split-adjusted SEC cover shares minus the equal-weighted eligible half, both rebalanced at the
           first close after the release's available_at and held to the next release's entry close, 10 bp per side on
           drift-adjusted turnover charged to both. Pass (>= 150 releases): one-sided 95% lower bound of the mean
           excess > 0 (studentized circular block bootstrap, 6-release blocks); FF5+UMD+BAB alpha NW t >= 2 on the
           daily long-minus-benchmark series through 2026-08; both halves (2018-01..2021-12, 2022-01..2026-09)
           positive; positive excluding 2021-01..2021-03; DSR >= 0.95 at 4 trials (EW/VW x SIR/DTC); absent portfolio
           names would need an excess worse than -5% per release to erase the pass.
  * T-676  Persistent off-exchange short-volume ratio. At each month-end close: SVR = mean over CNMS file days -65..-6
           of short / total volume (>= 40 present), residualised cross-sectionally on log 60-session median dollar
           volume; equal-weighted bottom-minus-top quintile, entered at the next session's close and held 21 sessions,
           10 bp per side and 0.3%/yr borrow on the short leg. Pass (>= 90 months): one-sided 95% lower bound > 0
           (3-month blocks); both halves positive; FF5+UMD alpha t >= 2; DSR >= 0.95 at 2 trials (EW, VW); no
           significant reversal over months 2-12; absent names would need worse than -5% per month to erase the pass.
  * T-677  Standardised unexpected short interest. At each month-end settlement release with an entry 2019-01..
           2026-09: SUSI = (SIR now - mean of the prior 24 releases' SIR) / their sd (>= 20 of 24 present), SIR with SI
           and cover shares on one split basis; equal-weighted bottom-minus-top decile, rebalanced at the first close
           after the release's available_at and held to the next month-end release's entry, 10 bp per side on
           turnover and 0.3%/yr borrow on the short leg. Pass (>= 84 months): one-sided 95% lower bound > 0 (3-month
           blocks); FF5+UMD alpha t >= 2; both halves (2019-01..2022-12, 2023-01..2026-09) positive; DSR >= 0.95 at 4
           trials (EW/VW x SUSI/changePercent); absent names would need worse than -5% per month to erase the pass.

Data and point in time (declared before any run)
  * Every bundle through ``archive.load``; a row counts only when its ``available_at`` is not after the bundle's
    capture. Session calendar = SPY's bars. Prices: the shared daily panel (``panel_cache.daily_panel``, value-identical
    to ``batch6c_cal._daily``) sliced to the members' Yahoo series whose recipe meta says EQUITY; close and volume are
    split-adjusted, so close x volume is the as-traded dollar volume; adjclose is the total-return price (forward-
    filled after the last bar: a series that ends inside a hold is cash from its last close). Splits from
    ``daily-events-<sym>``.
  * Membership: fja05680 change-date snapshots in force on the formation day, then the Wikipedia changes table by
    effective date after the file's last date (``batch6c_events.membership_snapshots``, the T-394/T-673 construction).
    Index tickers map to Yahoo by BRK.B -> BRK-B and to FINRA short-interest symbols by BRK.B -> BRKB; CNMS symbols are
    already in index spelling (``batch13_short_a.cnms_data``).
  * FINRA short interest enters at its available_at (end of the 8th NYSE business day after settlement); the fill is
    the first 16:00 ET close strictly after it (session e); the dollar-volume cut and the VW market caps use the
    previous close q = e - 1; SEC shares are those accepted before e's 09:30 ET open (one information set, rule 12).
  * Identity (reused tickers): a member's FINRA row is used with its Yahoo series and its current-map CIK only when the
    FINRA issue name (point in time) agrees with a name the instrument has carried (Yahoo longName, the SEC ticker name,
    the CIK's submissions name and formerNames), rejected only when both house matchers reject it
    (``batch6c_stockxs.names_ok``, None = not comparable = accepted, and ``batch6c_events.name_match``; the second was
    added after the first run because the first rejects FINRA's 'A.O. Smith' / 'J.M. Smucker' spellings). A
    disagreeing series is treated as absent (BBT, now Beacon Financial; LB, now LandBridge). REVIEW FIXES (adopted
    after the runs, verdicts unchanged): the second matcher no longer accepts a match on generic words alone
    (GENERIC_TOKENS: the BNY-fund 'New York', ARKO 'Petroleum', 'Fox' cases), and every FINRA row, member classes
    included, must be a stock row (``SX.is_stock_row``: no funds/ETFs such as the 2021 META ETF). APC and old FOX
    previously dropped out only for lack of bars, not by identity. CNMS symbols use the FINRA-volume identity check of T-673/T-674
    (``batch6c_events.finra_identity`` on as-traded Yahoo volume).
  * SEC cover shares (``sec-companyfacts``): the latest dei EntityCommonStockSharesOutstanding accession accepted before
    the decision (its latest cover date, summed across share classes); only when no dei value has been accepted, the
    latest us-gaap CommonStockSharesOutstanding. REVIEW FIX (after the runs): the count used is the accepted dei or
    us-gaap value with the latest as-of date, capped at the house SX.SHARES_MAX_AGE (456 days before settlement;
    stale = no shares); a us-gaap count is on its ACCEPTANCE-date basis (GOOGL's Q2-2022 10-Q is already split-
    restated), and only clean k/d splits (d <= 4) restate shares (``true_split``: spin-off price factors such as
    EXC 1.402 are not share splits). Shares are restated to
    the settlement date's basis by every split with an ex-date after the cover date and on or before settlement (and
    divided back when the cover date is after settlement), so a split between filing and settlement cannot fake an
    N-fold SIR (the verifier's NVDA trap). DECLARED READING for multi-class issuers (the cover count sums classes, the
    FINRA rows are per class): SIR = the issuer's short interest summed over its FINRA stock-class rows (same current-
    map CIK, names agreeing) over the issuer's cover shares, the same value for each listed member class (GOOG/GOOGL,
    FOX/FOXA, NWS/NWSA, BRK.B with BRK.A). DTC (T-675's SI/ADV variant) and changePercent are per class. VW market cap =
    split-adjusted close at q x cover shares x the split factor after the cover date / the issuer's listed classes.
    DATA VALIDITY (added after the first run, on inspecting the SIR cross-section, not to any return: recorded as a
    deviation): an SIR outside (0, 1] is not a usable ratio (Berkshire's companyfacts cover count is Class A-
    equivalent, so BRK.B reads 13x; FOX, FOXA, BKR and TRIP carry cover values off by orders of magnitude; a zero FINRA
    position on a member is a glitch): that release's ratio is treated as a missing cover-share value (excluded from
    the eligible set and from T-677's history, counted as 'bad_sir'). A cover count that is too LARGE (an SIR too low
    to flag) cannot be detected from the archived data.
  * CNMS (T-676): file days with status ok; a day is present for a symbol when total_volume > 0. Day 0 is the last file
    day on or before the month-end session (a missing month-end file moves the window earlier, never later); the window
    is file days -65..-6, so it ends at least 5 file days before formation (WYZ). The 60-session median dollar volume
    for the residualisation ends at the month-end close (the formation; the entry is the next close). A name needs >= 30
    bars in any 60-session dollar-volume window (declared).

Costs, holds and readings (declared, conservative where the registration is ambiguous)
  * T-675 and T-677 chain holds (each held to the next formation's entry), so 10 bp per side is charged on drift-
    adjusted turnover (sum |w_new - w_drifted|; the first entry and the final exit included), to both the portfolio and
    the benchmark (T-675) or both legs (T-677). T-676's 21-session holds do not chain onto the next month-end's entry,
    so each cohort pays a full round trip: 10 bp in and out on each leg (40 bp per month on the L/S); the turnover-
    netted reading is reported. Borrow (T-676, T-677): 0.3%/yr on the short leg's unit notional over calendar days.
  * Quintiles/deciles: floor(n/5) or floor(n/10) names per tail, names tied at a boundary share its slots
    (``batch6c_stockxs.tail_fractions``); the top half is the floor(n/2) highest dollar volumes.
  * Periods: T-675 entries in 2018-01-01..2026-09-30 whose next entry is inside the price data; T-676 month-end
    formations whose entry (the next session) falls in 2018-11..2026-09 (formations 2018-10-31..2026-08-31; the
    verifier's 'from late 2018-10'), halves by entry month 2018-11..2022-10 / 2022-11..2026-09; T-677 month-end
    settlement releases (settlement day >= 20) whose entry falls in 2019-01..2026-09, halves by entry date.
  * Alphas: T-675 regresses the DAILY net long-minus-benchmark series (rebalancing cost on each period's first day) on
    FF5 + UMD + AQR BAB daily, through 2026-08-31; T-676 and T-677 regress each period's net L/S on the factor sums
    over the same sessions (the T-393 convention), FF5 + UMD. Newey-West Bartlett lag floor(4 (n/100)^(2/9)) (daily)
    or max(3, that) (monthly).
  * "Positive" (halves, the 2021 exclusion) = the point mean > 0; the 2021 exclusion drops every period whose hold
    touches 2021-01-01..2021-03-31. T-676's "no significant reversal over months 2-12": the same formation's EW legs,
    rebalanced to equal weights at each event month's start, over event months 2..12 (21 sessions each); the sum of the
    gross monthly L/S returns over months 2-12 must not be significantly negative (studentized CBB, 12-month blocks,
    one-sided p_less < 0.05 is a reversal); only formations whose months 2-12 are complete enter.
  * DSR: ``batch6c_mom.family_dsr`` (trial-Sharpe variance = the computed variants' variance floored at 1/(T-1), the
    house convention) at the registered trial count. T-676's VW reading: the registered data list has no share counts
    (the verifier removed the CIK map), so VW weights are the 60-session median dollar volume (declared).
  * Absent names (survivorship). The price set is the archive's 901-symbol daily-history set: TODAY's universe, so
    removed, acquired and renamed members are missing. The registered pre-run fetch of every member Yahoo still serves
    has not been done (these harnesses may not write the archive): that criterion is NOT IMPLEMENTED (None), so every
    verdict is at best inconclusive until it is (a failing criterion still fails). The tipping-point criterion is
    implemented on all absent members (a member with a FINRA row / CNMS signal and no usable price series), under two
    readings that must agree (rules 11/12): (P) proportional, absent names take the portfolio/leg share A/U of the
    members with a row; (W) worst case, every absent member falls in the portfolio/leg, up to its size at the full
    universe's quantile count. Contamination: T-675 x' = (1 - w) x + w (-5%) (absent names in the benchmark are
    ignored, which is conservative for a negative excess); T-676/T-677 x' = x - 5% (w_long + w_short) (absent names
    5% worse than their leg on each side). The criterion passes when the lower bound, both halves (and T-675's 2021
    exclusion) still pass on x'. The tipping return itself is reported (HAC-normal bound, bisection).
  * Rule 10. T-675 and T-677 trade on FINRA's release calendar (event-driven, set by FINRA): no free phase; T-677's
    other monthly phase (the mid-month releases) is reported. T-676 names its calendar (month-end, WYZ), used as the
    primary; the 20 other entry offsets (formation 1..20 sessions before month-end) are reported.
  * Statistics: means use ``batch6c_cal.studentized_p_escalated`` (the house studentized circular block bootstrap,
    5 seeds of 2,000, escalated while the Monte-Carlo band straddles 0.05) and ``decide_p``; a lower-bound criterion
    passes when the point is positive and p_greater < 0.05 is decided, and fails decisively (rule 5) when p_less < 0.05.
    Verdicts via ``batch6c_cal._judge`` (rule 5 below min_n).
"""

from __future__ import annotations

import bisect
from datetime import date
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch13_short_a as SA
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
FJA_B = "fja-sp500-components"
CHG_B = "wikipedia-sp500-changes"
TICK_B = "sec-company-tickers"
FF5_B = "french-ff5-daily"
MOM_B = "french-momentum-daily"
BAB_B = "aqr-bab-daily"
SI_FIRST_B = "finra-short-interest-2017-12-29"
CNMS_FIRST_B = "finra-regsho-cnms-2018-08"
FACTS_PREFIX = "sec-companyfacts-"
SUBS_PREFIX = "sec-submissions-"
FF5_COLS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")

PANEL_START = "2016-06-01"     # first session of the price slice (60-session windows before 2018 and SIR history)
UNIV_END = "2026-12-31"
DV_WIN = 60
DV_MIN_BARS = 30
COST = 10e-4                   # per side, every harness
BORROW = 0.003                 # per year on the short leg (T-676, T-677)
TIP = 0.05                     # absent names' adverse return per period that must not erase the pass
FACTOR_END = "2026-08-31"

# T-675
T675_START, T675_END = "2018-01-01", "2026-09-30"
T675_SPLIT = "2022-01-01"
T675_EXCL = ("2021-01-01", "2021-03-31")
T675_BLOCK = 6
T675_MIN_N = 150
T675_TRIALS = 4

# T-676
T676_ENTRY = ("2018-11-01", "2026-09-30")
T676_LO, T676_HI = 65, 6       # CNMS file days -65..-6
T676_MIN_PRESENT = 40
T676_HOLD = 21
T676_BLOCK = 3
T676_MIN_N = 90
T676_SPLIT = "2022-11-01"
T676_REV_MONTHS = 12
T676_REV_BLOCK = 12
T676_BOOM = ("2020-01-01", "2021-12-31")
T676_TRIALS = 2
T676_OFFSETS = 20

# T-677
T677_ENTRY = ("2019-01-01", "2026-09-30")
T677_LOOK = 24
T677_MIN_HIST = 20
T677_BLOCK = 3
T677_MIN_N = 84
T677_SPLIT = "2023-01-01"
T677_TRIALS = 4
MONTH_END_DAY = 20             # a FINRA settlement on day >= 20 is the month-end release (mid-month: the 15th or before)
FILING_FORMS = ("10-Q", "10-K", "10-KT")
SIR_VALID = (0.0, 1.0)         # data validity: short interest over cover shares outside (0, 1] is not a usable ratio


# ================================================================================================= small helpers ==

def finra_sym(t: str) -> str:
    """FINRA short-interest spelling of an index ticker (BRK.B -> BRKB, BF.B -> BFB)."""
    return str(t).replace(".", "").replace("/", "").replace("-", "").strip().upper()


def ident_ok(issue: str, names: Sequence[str], ticker: str = "") -> bool:
    """Is a FINRA issue name the instrument behind ``names``? Rejected only when both house matchers reject it: the
    first-word rule of ``batch6c_stockxs.names_ok`` (False = every comparable name disagrees) and the shared-token /
    acronym rule of ``batch6c_events.name_match`` (FINRA's 'A.O. Smith Corporation' vs Yahoo's 'A. O. Smith
    Corporation' fails the first and passes the second; a reused ticker such as BBT, now Beacon Financial, fails both)."""
    if SX.names_ok(issue, names) is not False:
        return True
    for nm in names:
        if not nm or not EV.name_match(issue, nm, ticker):
            continue
        shared = EV._tokens(issue) & EV._tokens(nm)
        if shared and not (shared - GENERIC_TOKENS):
            continue                      # matched only on generic words ('New York', 'Petroleum', 'Fox'): rejected
        return True
    return False


# Review fix (adopted after a run, verdict-neutral): words too common in issuer names to identify a company alone.
GENERIC_TOKENS = frozenset({"new", "york", "petroleum", "fox", "american", "america", "national", "first", "united",
                            "general", "international", "energy", "financial", "group", "holdings", "holding", "bank",
                            "trust", "century", "twenty", "global", "capital", "resources", "income", "fund",
                            "municipal", "technologies", "systems", "services", "industries", "us", "usa"})


def true_split(r: float) -> bool:
    """A clean k/d share split or reverse split (d <= 4), not a spin-off price adjustment that Yahoo stores as a
    fractional 'split' (EXC 1.402, DELL 1.973): FINRA short interest does not change at a spin-off."""
    if not (r > 0):
        return False
    for x in (r, 1.0 / r):
        for d in (1, 2, 3, 4):
            if abs(x * d - round(x * d)) < 1e-3 and round(x * d) >= 1:
                return True
    return False


def share_splits(splits: Sequence[tuple]) -> list:
    return [(ex, r) for ex, r in splits if true_split(r)]


def split_adj(splits: Sequence[tuple], d_from: str, d_to: str) -> float:
    """Factor restating a share count dated ``d_from`` onto the ``d_to`` basis: the product of the split ratios with an
    ex-date in (d_from, d_to] (forward), or its inverse over (d_to, d_from] when d_to is earlier."""
    f = 1.0
    if d_to >= d_from:
        for ex, r in splits:
            if d_from < ex <= d_to:
                f *= r
        return f
    for ex, r in splits:
        if d_to < ex <= d_from:
            f /= r
    return f


def split_after(splits: Sequence[tuple], day: str) -> float:
    """Shares today per share held on ``day`` (the product of the ratios with an ex-date after ``day``)."""
    f = 1.0
    for ex, r in splits:
        if ex > day:
            f *= r
    return f


def share_series(facts: Sequence[tuple]) -> tuple:
    """(dei, gaap): per accession [(available_at epoch, cover/as-of date, shares)] sorted by availability. dei = the
    EntityCommonStockSharesOutstanding values of the accession's latest cover date summed across classes; gaap = us-gaap
    CommonStockSharesOutstanding at the accession's latest date (the largest value there)."""
    by = {0: {}, 1: {}}
    for tax, tag, unit, start, end, val, accn, form, av in facts:
        if (tax, tag) not in SX.SHARE_TAGS or not end or not (val > 0):
            continue
        k = 0 if tax == "dei" else 1
        by[k].setdefault(accn, {}).setdefault(end, []).append((val, av))
    out = []
    for k in (0, 1):
        ser = []
        for accn, ends in by[k].items():
            end = max(ends)
            vals = ends[end]
            tot = sum(v for v, _ in vals) if k == 0 else max(v for v, _ in vals)
            ser.append((min(a for _, a in vals), end, tot))
        out.append(sorted(ser))
    return out[0], out[1]


def shares_known(series: tuple, ts: float, day: Optional[str] = None) -> Optional[tuple]:
    """(shares, basis date, 'dei' | 'gaap') accepted at or before ``ts``: among the accepted dei and us-gaap accessions,
    the one with the latest as-of date (dei on ties). The basis date is the dei cover date, or for us-gaap the
    acceptance date (a balance-sheet count filed after a split is already restated, so only later splits apply).
    None when neither, or when the as-of date is more than SX.SHARES_MAX_AGE days before ``day`` (stale)."""
    best = None
    for k, ser in zip(("dei", "gaap"), series):
        acc = [s for s in ser if s[0] <= ts]
        if not acc:
            continue
        a, end, v = max(acc, key=lambda s: (s[1], s[0]))
        key = (end, 1 if k == "dei" else 0)
        if best is None or key > best[0]:
            basis = end if k == "dei" else _iso(a)
            best = (key, (v, basis, k), end)
    if best is None:
        return None
    if day is not None and (date.fromisoformat(day[:10]) - date.fromisoformat(best[2][:10])).days > SX.SHARES_MAX_AGE:
        return None
    return best[1]


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).date().isoformat()


def si_ratio(si_issuer: float, shares: float, cover: str, settle: str, splits: Sequence[tuple]) -> float:
    """Short interest at settlement over cover shares restated to the settlement basis (NaN when unusable)."""
    if not (np.isfinite(si_issuer) and si_issuer >= 0 and shares and shares > 0):
        return float("nan")
    return float(si_issuer / (shares * split_adj(share_splits(splits), cover, settle)))


def dollar_volume(C: np.ndarray, V: np.ndarray, i: int, win: int = DV_WIN, min_bars: int = DV_MIN_BARS) -> np.ndarray:
    """Per column: the median as-traded dollar volume (split-adjusted close x split-adjusted volume) over the ``win``
    sessions ending at row ``i`` (rows i-win+1..i only), NaN with fewer than ``min_bars`` bars."""
    lo = max(0, i - win + 1)
    X = C[lo:i + 1] * V[lo:i + 1]
    X = np.where(np.isfinite(X) & (X > 0), X, np.nan)
    cnt = np.isfinite(X).sum(axis=0)
    out = np.full(C.shape[1], np.nan)
    ok = cnt >= min_bars
    if ok.any():
        out[ok] = np.nanmedian(X[:, ok], axis=0)
    return out


def window_svr(SV: np.ndarray, TV: np.ndarray, i0: int, lo: int = T676_LO, hi: int = T676_HI,
               min_present: int = T676_MIN_PRESENT) -> tuple:
    """(signal, present count) per symbol: the mean of short / total volume over file days i0-lo..i0-hi (rows only;
    nothing after i0-hi enters), NaN with fewer than ``min_present`` present days (total_volume > 0)."""
    a, b = max(0, i0 - lo), i0 - hi
    if b < a:
        return np.full(SV.shape[1], np.nan), np.zeros(SV.shape[1], int)
    sv, tv = SV[a:b + 1], TV[a:b + 1]
    ok = np.isfinite(sv) & np.isfinite(tv) & (tv > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(ok, sv / np.where(ok, tv, 1.0), 0.0)
    cnt = ok.sum(axis=0)
    sig = np.where(cnt >= min_present, r.sum(axis=0) / np.maximum(cnt, 1), np.nan)
    return sig, cnt


def resid_on(x: np.ndarray, z: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Residual of x on [1, z] by cross-sectional OLS over ``mask`` (NaN outside)."""
    out = np.full(x.size, np.nan)
    m = mask & np.isfinite(x) & np.isfinite(z)
    if m.sum() < 3:
        return out
    X = np.column_stack([np.ones(int(m.sum())), z[m]])
    b, *_ = np.linalg.lstsq(X, x[m], rcond=None)
    out[m] = x[m] - X @ b
    return out


def susi_at(S: np.ndarray, t: int, look: int = T677_LOOK, min_hist: int = T677_MIN_HIST) -> np.ndarray:
    """SUSI per column at release row t: (S[t] - mean(S[t-look:t])) / sd(S[t-look:t], ddof 1), NaN with fewer than
    ``min_hist`` finite prior values or a zero sd. Rows after t never enter."""
    if t < 1:
        return np.full(S.shape[1], np.nan)
    H = S[max(0, t - look):t]
    fin = np.isfinite(H)
    cnt = fin.sum(axis=0)
    mu = np.where(fin, H, 0.0).sum(axis=0) / np.maximum(cnt, 1)
    dev = np.where(fin, H - mu[None, :], 0.0)
    sd = np.sqrt((dev ** 2).sum(axis=0) / np.maximum(cnt - 1, 1))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (S[t] - mu) / sd
    return np.where((cnt >= min_hist) & (sd > 0) & np.isfinite(S[t]), z, np.nan)


def leg_track(periods: Sequence[tuple], legs: Sequence, Af: np.ndarray, daily: bool = False) -> dict:
    """Chained holds of one leg. ``periods`` [(e, x)] with x = the next entry; ``legs`` aligned [(cols, weights summing
    to 1) or None]. R = hold return close e -> close x (forward-filled total-return prices: a series that ends is cash);
    TO = sum |w_new - w_drifted_prev| (the first entry counts 1); exit = the drifted weight left after the last period
    (1 when it holds names); daily = per-period arrays of daily returns e+1..x."""
    prev: dict = {}
    R, TO, D = [], [], []
    for (e, x), lg in zip(periods, legs):
        if lg is None or len(lg[0]) == 0:
            R.append(float("nan"))
            TO.append(float(sum(abs(v) for v in prev.values())))
            prev = {}
            D.append(None)
            continue
        cols, w = np.asarray(lg[0], int), np.asarray(lg[1], float)
        rel = Af[e:x + 1, cols] / Af[e, cols]
        rel = np.where(np.isfinite(rel), rel, 1.0)
        V = rel @ w
        new = dict(zip(cols.tolist(), w.tolist()))
        TO.append(float(sum(abs(new.get(c, 0.0) - prev.get(c, 0.0)) for c in set(new) | set(prev))))
        R.append(float(V[-1] - 1.0))
        prev = {c: float(wi * rel[-1, k] / V[-1]) for k, (c, wi) in enumerate(zip(cols.tolist(), w.tolist()))} \
            if V[-1] > 0 else {}
        D.append(V[1:] / V[:-1] - 1.0 if daily else None)
    return {"R": np.array(R, float), "TO": np.array(TO, float), "exit": float(sum(prev.values())), "daily": D}


def ew_weights(frac: np.ndarray) -> Optional[tuple]:
    idx = np.flatnonzero(frac > 0)
    if idx.size == 0:
        return None
    return idx, frac[idx] / frac[idx].sum()


def val_weights(frac: np.ndarray, size: np.ndarray) -> Optional[tuple]:
    w = frac * np.where(np.isfinite(size) & (size > 0), size, 0.0)
    idx = np.flatnonzero(w > 0)
    if idx.size == 0:
        return None
    return idx, w[idx] / w[idx].sum()


def touches(e_days: Sequence[str], x_days: Sequence[str], lo: str, hi: str) -> np.ndarray:
    return np.array([ed <= hi and xd >= lo for ed, xd in zip(e_days, x_days)], bool)


# ================================================================================================= statistics ==

def mean_test(x, block: int) -> dict:
    """Mean with escalated studentized-CBB one-sided p's and a Newey-West s.e. (lag = block)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    pg, pl, nd = CAL.studentized_p_escalated(x, block, None, SEED, CAL.N_SEEDS)
    nw = SX.nw_mean(x, block)
    return {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "p_greater": pg, "p_less": pl, "draws": nd,
            "nw_t": nw.get("t"), "block": block}


def lb_ok(t: dict) -> Optional[bool]:
    """'one-sided 95% lower bound > 0': the point positive and p_greater < 0.05 (Monte-Carlo-banded decision)."""
    return B7C._sig_crit(t.get("mean"), t.get("p_greater"), t.get("draws", 1))


def lb_decisive(t: dict) -> bool:
    return CAL.decide_p(t.get("p_less"), t.get("draws", 1)) is True


def hac_lb(x, lag: int) -> Optional[float]:
    """HAC-normal one-sided 95% lower bound of the mean (for the reported tipping returns)."""
    m = SX.nw_mean(np.asarray(x, float), lag)
    if m.get("se") is None:
        return None
    return m["est"] - 1.6448536 * m["se"]


def tipping_value(f, lag: int, lo: float = -2.0, hi: float = 2.0) -> Optional[float]:
    """The r at which the HAC lower bound of the mean of f(r) crosses zero (bisection; f increasing in r). None when it
    does not cross on [lo, hi]."""
    a, b = hac_lb(f(lo), lag), hac_lb(f(hi), lag)
    if a is None or b is None or a > 0 or b < 0:
        return None if a is None or b is None else (lo if a > 0 else hi)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if hac_lb(f(mid), lag) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def ols_alpha(y, F, lag: int) -> dict:
    y = np.asarray(y, float)
    F = np.asarray(F, float).reshape(y.size, -1)
    ok = np.isfinite(y) & np.all(np.isfinite(F), axis=1)
    r = SX.ols_nw(y[ok], F[ok], lag)
    return {"alpha": r.get("alpha"), "t": r.get("t"), "n": int(ok.sum()), "lag": lag, "betas": r.get("betas")}


def dsr_of(x, family: Sequence, n_trials: int, label: str) -> tuple:
    sh = [float(sharpe_ratio(v[np.isfinite(v)])) if np.isfinite(np.asarray(v, float)).sum() > 2 else None for v in family]
    x = np.asarray(x, float)
    d = family_dsr(x[np.isfinite(x)], sh, n_trials)
    name, ok, dec = dsr_row(d, label)
    if d.get("dsr") is not None:
        ok = bool(d["dsr"] >= 0.95)
    return d, (name, ok, dec)


def halves(x, labels: Sequence[str], split: str) -> list:
    x = np.asarray(x, float)
    h = np.array([d < split for d in labels], bool)
    out = []
    for m in (h, ~h):
        v = x[m & np.isfinite(x)]
        out.append(float(v.mean()) if v.size else None)
    return out


def _fmt(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 3) -> str:
    return B7C._pc(x, nd) if x is not None else "n/a"


# ================================================================================================= shared data ==

def _snaps(archive) -> list:
    def load():
        fja = EV._rows(archive, FJA_B)
        chg = [r.get("value") or {} for r in EV._rows(archive, CHG_B)]
        return EV.membership_snapshots(fja, chg)
    return CAL._cached(archive, ("b13sb_snaps",), load)


def members_in(snaps: Sequence[tuple], lo: str, hi: str) -> set:
    """Every index ticker in force on some day of [lo, hi]."""
    lo_e, hi_e = EV._ed(lo), EV._ed(hi)
    out = set(EV.members_at(snaps, lo_e))
    for e, s in snaps:
        if lo_e < e <= hi_e:
            out |= set(s)
    return out


def _splits(archive, y: str) -> list:
    name = SX.de(y)
    if not SX._has(archive, name):
        return []
    out = []
    for r in SX._stream(archive, name):
        v = r.get("value") or {}
        if r.get("kind") != "split" and v.get("type") != "split":
            continue
        try:
            num, den = float(v.get("numerator")), float(v.get("denominator"))
        except (TypeError, ValueError):
            continue
        ex = v.get("ex_date")
        if num > 0 and den > 0 and ex:
            out.append((str(ex)[:10], num / den))
    return sorted(out)


def prices(archive) -> dict:
    """The members' Yahoo EQUITY series on the SPY calendar from PANEL_START, sliced from the shared daily panel (which is
    released afterwards): C, V, Af (adjclose forward-filled), real, last, F (split factor after each day), splits, names."""
    def load():
        snaps = _snaps(archive)
        univ = sorted({EV.ysym(t) for t in members_in(snaps, PANEL_START, UNIV_END)})
        full = SX._sessions(archive)
        days = np.array(full.days[full.on_or_after(PANEL_START):])
        cal = SX.Cal(days.tolist())
        P = PC.daily_panel(archive)
        pdays = np.asarray(P.days)
        pos = np.minimum(np.searchsorted(pdays, days), pdays.size - 1)
        ok = pdays[pos] == days
        symidx = {s: j for j, s in enumerate(np.asarray(P.symbols).tolist())}
        syms, meta = [], {}
        for y in univ:
            if y not in symidx:
                continue
            mt = SX._meta(archive, SX.dh(y)) or {}
            if mt.get("instrumentType") != "EQUITY":
                continue
            syms.append(y)
            meta[y] = mt
        cols = np.array([symidx[y] for y in syms], int)
        D, S = days.size, len(syms)

        def take(M):
            out = np.full((D, S), np.nan)
            if S:
                out[ok] = M[pos[ok]][:, cols]
            return out
        C, A, V = take(P.close), take(P.adjclose), take(P.volume)
        del P
        PC._MEMO.clear()                      # the 1 GB panel is not needed again in this process
        real = np.isfinite(C)
        anyb = real.any(axis=0)
        last = np.where(anyb, D - 1 - real[::-1].argmax(axis=0), -1)
        Af = SX._ffill(A)
        sp = {y: _splits(archive, y) for y in syms}
        F = np.ones((D, S))
        for j, y in enumerate(syms):
            for ex, r in sp[y]:
                F[days < ex, j] *= r
        absent = sorted(t for t in members_in(snaps, PANEL_START, UNIV_END) if EV.ysym(t) not in set(syms))
        return {"cal": cal, "days": days, "syms": syms, "col": {y: j for j, y in enumerate(syms)}, "C": C, "V": V,
                "Af": Af, "real": real, "last": last, "F": F, "splits": sp, "meta": meta, "univ": univ,
                "unpriced_tickers": absent}
    return CAL._cached(archive, ("b13sb_prices",), load)


def sec_data(archive, pr: dict) -> dict:
    """Current SEC ticker map, the CIKs of the priced members, their profiles (names) and share series, and the name
    aliases per Yahoo symbol and per CIK."""
    def load():
        tick = SX._sec_tickers(archive) if SX._has(archive, TICK_B) else {}
        ciks = {tick[y][0] for y in pr["syms"] if y in tick}
        comp = SX._company_rows(archive, ciks) if ciks else {}
        facts = SX._sec_facts(archive, frozenset(ciks))["facts"] if ciks else {}
        ser = {c: share_series(facts.get(c, ())) for c in ciks}
        cik_names: dict = {}
        sym_names: dict = {}
        for y in pr["syms"]:
            nm = [(pr["meta"].get(y) or {}).get("longName") or ""]
            if y in tick:
                c = tick[y][0]
                v = comp.get(c) or {}
                extra = [tick[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
                nm += extra
                cik_names.setdefault(c, set()).update(x for x in extra + nm[:1] if x)
            sym_names[y] = [x for x in nm if x]
        cik_sym = {}
        for y in pr["syms"]:
            if y in tick:
                cik_sym.setdefault(tick[y][0], y)
        return {"tick": tick, "ciks": ciks, "ser": ser, "sym_names": sym_names,
                "cik_names": {c: sorted(v) for c, v in cik_names.items()}, "cik_sym": cik_sym}
    return CAL._cached(archive, ("b13sb_sec",), load)


def finra_releases(archive, pr: dict, sec: dict) -> list:
    """Every archived FINRA release (settlement order): settle, av (epoch of its available_at), and the rows of the
    member classes and of the other listed classes of member issuers: {symbol: (issueName, class, SI, ADV,
    changePercent, stockSplitFlag, revisionFlag, cik)}."""
    def load():
        tick = sec["tick"]
        mem_f = {finra_sym(t) for t in members_in(_snaps(archive), PANEL_START, UNIV_END)}
        ciks = sec["ciks"]
        cik_of: dict = {}
        out = []
        for nm in SX._entry_names(archive, SX.FINRA_PREFIX):
            settle = nm[len(SX.FINRA_PREFIX):]
            av, rows = None, {}
            for r in SX._stream(archive, nm):
                v = r.get("value") or {}
                sym = (v.get("symbolCode") or "").strip().upper()
                if not sym:
                    continue
                try:
                    a = SX._ts(r["available_at"])
                    av = a if av is None else max(av, a)
                except (KeyError, ValueError, TypeError):
                    pass
                if sym not in cik_of:
                    cik_of[sym] = next((tick[c][0] for c in SX._finra_cands(sym) if c in tick), None)
                ck = cik_of[sym]
                if sym not in mem_f and ck not in ciks:
                    continue
                rows[sym] = (v.get("issueName") or "", v.get("marketClassCode") or "",
                             SX._num(v.get("currentShortPositionQuantity")), SX._num(v.get("averageDailyVolumeQuantity")),
                             SX._num(v.get("changePercent")), bool(v.get("stockSplitFlag")), bool(v.get("revisionFlag")),
                             ck)
            out.append({"settle": settle, "av": av, "rows": rows})
        return out
    return CAL._cached(archive, ("b13sb_finra",), load)


def issuer_si(rel: dict, sec: dict, member_f: set) -> dict:
    """{cik: (summed SI, listed classes, symbols)} of one release: the FINRA rows mapped to a member CIK whose issue name
    agrees with the CIK's names; a non-member class must also be a stock row (no funds, preferreds, notes, units)."""
    out: dict = {}
    for sym, row in rel["rows"].items():
        nm, cls, si, *_rest, ck = row
        if ck is None or ck not in sec["ciks"] or not (np.isfinite(si) and si >= 0):
            continue
        if not SX.is_stock_row(cls, nm):     # review fix: member rows too (funds/ETFs reusing a member ticker)
            continue
        if not ident_ok(nm, sec["cik_names"].get(ck, []), sym):
            continue
        s, n, ss = out.get(ck, (0.0, 0, ()))
        out[ck] = (s + si, n + 1, ss + (sym,))
    return out


def factor_table(archive, bab: bool) -> dict:
    """{day: array of FF5 (+ UMD) (+ BAB) daily returns in decimals} on the days every series prints."""
    def load():
        cols = [CAL._series(archive, FF5_B, c) for c in FF5_COLS] + [CAL._series(archive, MOM_B, "Mom")]
        days = set(cols[0])
        for c in cols[1:]:
            days &= set(c)
        out = {d: np.array([c[d] / 100.0 for c in cols]) for d in days}
        if bab:
            b = CAL._series(archive, BAB_B, "bab_usa")
            out = {d: np.concatenate([v, [b[d]]]) for d, v in out.items() if d in b}
        return out
    return CAL._cached(archive, ("b13sb_factors", bab), load)


def period_factor_sums(days: Sequence[str], fac: dict, e: Sequence[int], x: Sequence[int], k: int) -> np.ndarray:
    out = np.full((len(e), k), np.nan)
    for i, (a, b) in enumerate(zip(e, x)):
        rows = [fac.get(days[t]) for t in range(int(a) + 1, int(b) + 1)]
        if rows and all(r is not None for r in rows):
            out[i] = np.sum(np.array(rows, float), axis=0)
    return out


# ============================================================================================ SI formations ==

def build_sir(pr: dict, sec: dict, rels: list, mem_f: set) -> dict:
    """Entries per release (the first close strictly after available_at), issuer SI, the shares known at each
    release's entry open, and the issuer SIR matrix (release x CIK) on each release's settlement basis."""
    cal = pr["cal"]
    ciks = sorted(sec["ciks"])
    kc = {c: k for k, c in enumerate(ciks)}
    R = len(rels)
    SIR = np.full((R, len(ciks)), np.nan)
    SHR = [{} for _ in range(R)]
    ISS = []
    for r, rel in enumerate(rels):
        e = cal.entry_after(rel["av"]) if rel["av"] is not None else len(cal)
        rel["e"] = e if 0 < e < len(cal) else None
        tau = float(cal.open[e]) if rel["e"] is not None else (rel["av"] or 0.0)
        iss = issuer_si(rel, sec, mem_f)
        ISS.append(iss)
        for ck, (si, _ncls, _ss) in iss.items():
            sh = shares_known(sec["ser"].get(ck, ([], [])), tau, rel["settle"])
            if sh is None:
                continue
            y = sec["cik_sym"].get(ck)
            SHR[r][ck] = sh
            v = si_ratio(si, sh[0], sh[1], rel["settle"], pr["splits"].get(y, []) if y else [])
            SIR[r, kc[ck]] = v if SIR_VALID[0] < v <= SIR_VALID[1] else np.nan
    return {"pr": pr, "sec": sec, "rels": rels, "iss": ISS, "SIR": SIR, "shr": SHR, "kc": kc, "mem_f": mem_f}


def si_base(archive) -> dict:
    """Prices, SEC, FINRA releases and ``build_sir`` on them (cached)."""
    def load():
        pr = prices(archive)
        sec = sec_data(archive, pr)
        rels = finra_releases(archive, pr, sec)
        mem_f = {finra_sym(t) for t in members_in(_snaps(archive), PANEL_START, UNIV_END)}
        return build_sir(pr, sec, rels, mem_f)
    return CAL._cached(archive, ("b13sb_si_base",), load)


def member_rows(B: dict, r: int, snaps: Sequence[tuple]) -> dict:
    """At release r's entry e: every point-in-time member classified (no FINRA row / absent price / no shares / no
    dollar volume / covered) and, for the covered ones, column, SIR, DTC, changePercent, flags, market cap and dollar
    volume (q = e - 1)."""
    pr, sec, rel = B["pr"], B["sec"], B["rels"][r]
    e = rel["e"]
    q = e - 1
    cal = pr["cal"]
    mem = EV.members_at(snaps, EV._ed(cal.days[e]))
    dv = dollar_volume(pr["C"], pr["V"], q)
    iss = B["iss"][r]
    out = {k: [] for k in ("col", "sym", "sir", "dtc", "chg", "sflag", "rflag", "mcap", "dv", "cik")}
    cnt = {"members": len(mem), "no_finra": 0, "finra": 0, "absent": 0, "no_shares": 0, "bad_sir": 0, "no_dv": 0,
           "covered": 0}
    absent = []
    for m in sorted(mem):
        row = rel["rows"].get(finra_sym(m))
        if row is None:
            cnt["no_finra"] += 1
            continue
        cnt["finra"] += 1
        y = EV.ysym(m)
        j = pr["col"].get(y)
        if (j is None or not pr["real"][e, j] or not pr["real"][q, j]
                or not ident_ok(row[0], sec["sym_names"].get(y, []), m)):
            cnt["absent"] += 1
            absent.append(m)
            continue
        ck = sec["tick"].get(y, (None,))[0]
        sh = B["shr"][r].get(ck) if ck is not None else None
        ent = iss.get(ck) if ck is not None else None
        if sh is None or ent is None or finra_sym(m) not in ent[2]:
            cnt["no_shares"] += 1
            continue
        if not np.isfinite(B["SIR"][r, B["kc"][ck]]):
            cnt["bad_sir"] += 1
            continue
        if not np.isfinite(dv[j]):
            cnt["no_dv"] += 1
            continue
        cnt["covered"] += 1
        si, adv = row[2], row[3]
        out["col"].append(j)
        out["sym"].append(m)
        out["sir"].append(B["SIR"][r, B["kc"][ck]])
        out["dtc"].append(si / adv if np.isfinite(si) and np.isfinite(adv) and adv > 0 else np.nan)
        out["chg"].append(row[4])
        out["sflag"].append(row[5])
        out["rflag"].append(row[6])
        out["mcap"].append(float(pr["C"][q, j]) * sh[0] * split_after(pr["splits"].get(y, []), sh[1]) / max(1, ent[1]))
        out["dv"].append(dv[j])
        out["cik"].append(ck)
    res = {k: np.array(v) for k, v in out.items()}
    res["col"] = res["col"].astype(int) if res["col"].size else np.zeros(0, int)
    for k in ("sir", "dtc", "chg", "mcap", "dv"):
        res[k] = res[k].astype(float) if res[k].size else np.zeros(0)
    for k in ("sflag", "rflag"):
        res[k] = res[k].astype(bool) if res[k].size else np.zeros(0, bool)
    res.update(cnt=cnt, absent=absent, e=e, q=q, settle=rel["settle"], label=cal.days[e])
    return res


def top_half(dv: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Mask of the floor(n/2) highest dollar volumes among ``keep``."""
    idx = np.flatnonzero(keep & np.isfinite(dv))
    out = np.zeros(dv.size, bool)
    k = idx.size // 2
    if k < 1:
        return out
    o = idx[np.argsort(-dv[idx], kind="stable")]
    out[o[:k]] = True
    return out


# =============================================================================================== T-675 harness ==

def t675_books(forms: Sequence[dict], Af: np.ndarray, days: Sequence[str], drop_flag: bool = False) -> dict:
    """Per period (formation k to formation k+1's entry): the four DSR variants' net excess (EW/VW x SIR/DTC) over the
    same-weighted eligible half, the primary's daily net excess, and the reported books (exclusion filter, DTC L/S)."""
    periods = [(f["e"], f["x"]) for f in forms]
    legs = {k: [] for k in ("p_sir_ew", "b_ew", "p_sir_vw", "b_vw", "p_dtc_ew", "p_dtc_vw", "excl", "dtc_hi")}
    meta = {"n_elig": [], "k": [], "n_cov": []}
    for f in forms:
        keep = np.ones(f["col"].size, bool)
        if drop_flag:
            keep &= ~f["sflag"]
        elig = top_half(f["dv"], keep)
        n = int(elig.sum())
        cols = f["col"]
        meta["n_elig"].append(n); meta["n_cov"].append(int(keep.sum()))
        k = n // 5
        meta["k"].append(k)
        fs = SX.tail_fractions(f["sir"], elig, k, high=False)
        el = elig.astype(float)
        fd = SX.tail_fractions(f["dtc"], elig, int((elig & np.isfinite(f["dtc"])).sum()) // 5, high=False)
        fdh = SX.tail_fractions(f["dtc"], elig, int((elig & np.isfinite(f["dtc"])).sum()) // 5, high=True)
        top10 = SX.tail_fractions(f["dtc"], elig, int((elig & np.isfinite(f["dtc"])).sum()) // 10, high=True)
        for key, w in (("p_sir_ew", ew_weights(fs)), ("b_ew", ew_weights(el)), ("p_sir_vw", val_weights(fs, f["mcap"])),
                       ("b_vw", val_weights(el, f["mcap"])), ("p_dtc_ew", ew_weights(fd)),
                       ("p_dtc_vw", val_weights(fd, f["mcap"])), ("excl", ew_weights(el * (1.0 - top10))),
                       ("dtc_hi", ew_weights(fdh))):
            legs[key].append(None if w is None or k < 1 else (cols[w[0]], w[1]))
    tr = {key: leg_track(periods, v, Af, daily=key in ("p_sir_ew", "b_ew")) for key, v in legs.items()}

    def excess(p, b):
        x = (tr[p]["R"] - COST * tr[p]["TO"]) - (tr[b]["R"] - COST * tr[b]["TO"])
        if x.size:
            x[-1] -= COST * (tr[p]["exit"] - tr[b]["exit"])
        return x
    out = {"x_sir_ew": excess("p_sir_ew", "b_ew"), "x_sir_vw": excess("p_sir_vw", "b_vw"),
           "x_dtc_ew": excess("p_dtc_ew", "b_ew"), "x_dtc_vw": excess("p_dtc_vw", "b_vw"),
           "x_excl": excess("excl", "b_ew"),
           "gross_sir_ew": tr["p_sir_ew"]["R"] - tr["b_ew"]["R"], "gross_excl": tr["excl"]["R"] - tr["b_ew"]["R"],
           "ls_dtc_gross": tr["p_dtc_ew"]["R"] - tr["dtc_hi"]["R"],
           "ls_dtc_net": (tr["p_dtc_ew"]["R"] - tr["dtc_hi"]["R"] - COST * (tr["p_dtc_ew"]["TO"] + tr["dtc_hi"]["TO"])),
           "to_p": tr["p_sir_ew"]["TO"], "to_b": tr["b_ew"]["TO"], "meta": meta}
    # the primary's daily net excess (sessions e+1..x of each period; the rebalancing costs on the period's first day)
    dd, dv = [], []
    for k, (e, x) in enumerate(periods):
        a, b = tr["p_sir_ew"]["daily"][k], tr["b_ew"]["daily"][k]
        if a is None or b is None:
            continue
        d = a - b
        d[0] -= COST * (tr["p_sir_ew"]["TO"][k] - tr["b_ew"]["TO"][k])
        dd += [days[t] for t in range(e + 1, x + 1)]
        dv.append(d)
    out["daily_days"] = dd
    out["daily_x"] = np.concatenate(dv) if dv else np.zeros(0)
    return out


def t675_absent_weights(forms: Sequence[dict], meta: dict) -> dict:
    """Absent-name portfolio shares per period: (P) A/U of the members with a FINRA row; (W) every absent member in the
    portfolio, up to the bottom-quintile size of the universe with the absent names added."""
    wp, ww = [], []
    for f, ncov in zip(forms, meta["n_cov"]):
        A, U = f["cnt"]["absent"], f["cnt"]["finra"]
        wp.append(A / U if U else 0.0)
        kq = ((ncov + A) // 2) // 5
        ww.append(min(A, kq) / kq if kq > 0 else 0.0)
    return {"P": np.array(wp), "W": np.array(ww)}


def tip_rows_ok(xp: np.ndarray, labels: Sequence[str], split: str, block: int, excl: Optional[np.ndarray]) -> dict:
    t = mean_test(xp, block)
    hv = halves(xp, labels, split)
    ex = float(np.nanmean(xp[~excl])) if excl is not None and (~excl).any() else None
    oks = [lb_ok(t), None if any(h is None for h in hv) else all(h > 0 for h in hv)]
    if excl is not None:
        oks.append(None if ex is None else ex > 0)
    ok = None if any(o is None for o in oks) else all(oks)
    return {"ok": ok, "mean": t["mean"], "p_greater": t["p_greater"], "draws": t["draws"], "halves": hv, "excl": ex}


def b13_short_b_low_si_long(archive):
    """T-675."""
    need = [SPY_B, FJA_B, CHG_B, TICK_B, FF5_B, MOM_B, BAB_B, SI_FIRST_B]
    need += [SX.finra_name(d) for d in SX.finra_expected(T675_START, T675_END)]
    miss = B7C._missing(archive, need)
    if miss:
        return miss
    if not SX._entry_names(archive, FACTS_PREFIX):
        return B7C._missing(archive, [FACTS_PREFIX + "b000"])
    B = si_base(archive)
    pr = B["pr"]
    days = pr["cal"].days
    snaps = _snaps(archive)
    rels = B["rels"]
    idx = [r for r, rel in enumerate(rels) if rel["e"] is not None]
    forms = []
    for a, b in zip(idx[:-1], idx[1:]):
        rel = rels[a]
        if not (T675_START <= days[rel["e"]] <= T675_END) or rels[b]["e"] <= rel["e"]:
            continue
        f = member_rows(B, a, snaps)
        f["x"] = rels[b]["e"]
        forms.append(f)
    n = len(forms)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} FINRA formations could be built (rule 9)")
    bk = t675_books(forms, pr["Af"], days)
    labels = [f["label"] for f in forms]
    x_days = [days[f["x"]] for f in forms]
    x = bk["x_sir_ew"]
    t = mean_test(x, T675_BLOCK)
    hv = halves(x, labels, T675_SPLIT)
    excl = touches(labels, x_days, *T675_EXCL)
    ex = float(np.nanmean(x[~excl]))
    fac = factor_table(archive, bab=True)
    dd, dx = bk["daily_days"], bk["daily_x"]
    keep = [i for i, d in enumerate(dd) if d <= FACTOR_END and d in fac]
    Fd = np.array([fac[dd[i]] for i in keep]) if keep else np.zeros((0, 7))
    alpha = ols_alpha(dx[keep], Fd, CAL.nw_lags(len(keep))) if keep else {"alpha": None, "t": None, "n": 0, "lag": 0}
    fam = [bk["x_sir_ew"], bk["x_sir_vw"], bk["x_dtc_ew"], bk["x_dtc_vw"]]
    dsr, dsr_r = dsr_of(x, fam, T675_TRIALS, "DSR >= 0.95 at 4 trials (EW/VW x SIR/DTC)")
    aw = t675_absent_weights(forms, bk["meta"])
    tips = {}
    for rd, w in aw.items():
        xp = (1.0 - w) * x + w * (-TIP)
        tips[rd] = tip_rows_ok(xp, labels, T675_SPLIT, T675_BLOCK, excl)
        tips[rd]["tipping_excess"] = tipping_value(lambda r, w=w: (1.0 - w) * x + w * r, T675_BLOCK)
        tips[rd]["w_mean"] = float(w.mean())
    tip_ok = CAL._agree([tips["P"]["ok"], tips["W"]["ok"]])
    n_unpriced = len(pr["unpriced_tickers"])
    rows = [(f"one-sided 95% lower bound of the mean net excess per release > 0 (mean {_pc(t['mean'])}, p "
             f"{CAL._mc(t['p_greater'], t['draws'])}, NW t {_fmt(t['nw_t'], 2)}, 6-release blocks)", lb_ok(t), lb_decisive(t)),
            (f"FF5+UMD+BAB alpha NW t >= 2 on the daily net long-minus-benchmark series through {FACTOR_END} (alpha "
             f"{_fmt(None if alpha['alpha'] is None else alpha['alpha'] * 1e4, 2)} bps/day, t {_fmt(alpha['t'], 2)}, "
             f"{alpha['n']} days, lag {alpha['lag']})", None if alpha["t"] is None else bool(alpha["t"] >= 2.0),
             alpha["t"] is not None and alpha["t"] <= -2.0),
            (f"both halves positive (2018-01..2021-12 {_pc(hv[0])}, 2022-01..2026-09 {_pc(hv[1])})",
             None if any(h is None for h in hv) else all(h > 0 for h in hv), False),
            (f"positive excluding holds touching 2021-01..2021-03 ({_pc(ex)}, {int((~excl).sum())} releases)", bool(ex > 0), False),
            dsr_r,
            (f"absent portfolio names would need an excess worse than -5% per release to erase the pass (lower bound, both "
             f"halves and the 2021 exclusion still pass with absent names at -5%: proportional reading (mean share "
             f"{tips['P']['w_mean'] * 100:.1f}%) {tips['P']['ok']}, worst case ({tips['W']['w_mean'] * 100:.1f}%) "
             f"{tips['W']['ok']}; absent-name excess per release at which the HAC lower bound crosses zero "
             f"{_pc(tips['P']['tipping_excess'])} / {_pc(tips['W']['tipping_excess'])}, positive = absent names would have "
             f"to beat the benchmark to create a pass)",
             tip_ok, False),
            (f"registered pre-run fetch of every member Yahoo still serves ({n_unpriced} member tickers 2016-06..2026-10 have "
             f"no archived EQUITY daily history) [NOT IMPLEMENTED: the archive lacks them and this harness does not fetch]",
             None, False)]
    rows = CAL._undecided(rows[:-1]) + rows[-1:]        # the not-implemented fetch row is not "undecided"
    verdict, why, crit = CAL._judge(rows, n, T675_MIN_N, "releases")

    # ---- reported only
    rep = {"variants": {k: {"mean": float(np.nanmean(bk[k])), "sharpe": float(sharpe_ratio(bk[k][np.isfinite(bk[k])]))}
                        for k in ("x_sir_ew", "x_sir_vw", "x_dtc_ew", "x_dtc_vw")}}
    rep["gross_mean"] = float(np.nanmean(bk["gross_sir_ew"]))
    rep["turnover_mean"] = {"portfolio": float(np.mean(bk["to_p"])), "benchmark": float(np.mean(bk["to_b"]))}
    sfl = t675_books(forms, pr["Af"], days, drop_flag=True)
    rep["split_flag_rows_excluded"] = {"mean": float(np.nanmean(sfl["x_sir_ew"])),
                                       "flagged_rows_mean": float(np.mean([int(f["sflag"].sum()) for f in forms]))}
    exf = mean_test(bk["x_excl"], T675_BLOCK)
    rep["exclusion_filter"] = {"net": exf, "gross_mean": float(np.nanmean(bk["gross_excl"]))}
    lsd = mean_test(bk["ls_dtc_net"], T675_BLOCK)
    rep["dtc_ls_for_T393"] = {"net": lsd, "gross_mean": float(np.nanmean(bk["ls_dtc_gross"]))}
    cnts = [f["cnt"] for f in forms]
    cov = {k: float(np.mean([c[k] for c in cnts])) for k in cnts[0]}
    cov["eligible_mean"] = float(np.mean(bk["meta"]["n_elig"]))
    cov["portfolio_mean"] = float(np.mean(bk["meta"]["k"]))
    cov["absent_share_of_finra_rows_max"] = float(max(c["absent"] / c["finra"] for c in cnts if c["finra"]))
    rep["coverage"] = cov
    rep["tipping"] = tips
    rep["unpriced_member_tickers"] = pr["unpriced_tickers"]
    reason = (f"{n} FINRA releases with entries {labels[0]}..{labels[-1]} (first close after available_at, held to the next "
              f"release's entry): point-in-time S&P 500 members with a FINRA row, split-adjusted SEC cover shares and an "
              f"archived price (mean {cov['covered']:.0f} of {cov['members']:.0f} members; {cov['absent']:.1f} with a FINRA "
              f"row but no usable price, {cov['no_shares']:.1f} without shares, {cov['bad_sir']:.1f} with an SIR outside (0, 1]), "
              f"top half by 60-session median dollar "
              f"volume (mean {cov['eligible_mean']:.0f}); EW bottom SIR quintile (mean {cov['portfolio_mean']:.0f} names) "
              f"minus the EW eligible half, 10 bp per side on drift-adjusted turnover of both (portfolio "
              f"{rep['turnover_mean']['portfolio']:.2f}, benchmark {rep['turnover_mean']['benchmark']:.2f} per release): "
              f"gross {_pc(rep['gross_mean'])}, net {_pc(t['mean'])} per release (p {CAL._p(t['p_greater'])}); halves "
              f"{_pc(hv[0])} / {_pc(hv[1])}; ex 2021-Q1 {_pc(ex)}; FF5+UMD+BAB daily alpha t {_fmt(alpha['t'], 2)}; DSR "
              f"{_fmt(dsr.get('dsr'))}; variants VW {_pc(rep['variants']['x_sir_vw']['mean'])}, DTC EW "
              f"{_pc(rep['variants']['x_dtc_ew']['mean'])}, DTC VW {_pc(rep['variants']['x_dtc_vw']['mean'])}; split-flag rows "
              f"excluded {_pc(rep['split_flag_rows_excluded']['mean'])}; exclusion filter (benchmark minus its top DTC "
              f"decile vs the benchmark) {_pc(exf['mean'])} net; DTC bottom-minus-top quintile (T-393 by-product) gross "
              f"{_pc(rep['dtc_ls_for_T393']['gross_mean'])}, net {_pc(lsd['mean'])}. SURVIVORSHIP: prices are the "
              f"archive's 901-symbol daily-history set (today's universe); {n_unpriced} member tickers have no archived "
              f"EQUITY series; the eligible set and the benchmark exclude them by construction and the tipping-point "
              f"bound covers them")
    stat = {"n": n, "primary": t, "halves": hv, "excl_2021q1": ex, "alpha": alpha, "dsr": dsr, "criteria": crit,
            "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# =============================================================================================== T-676 harness ==

def cnms_base(archive) -> dict:
    """CNMS panel, member mask, the price columns of the CNMS symbols and their FINRA-volume identity checks."""
    def load():
        C = SA.cnms_data(archive)
        M, last_snap = SA.member_mask(archive, C["days"], C["syms"])
        pr = prices(archive)
        cal = pr["cal"]
        ci = np.array([cal.pos.get(d, -1) for d in C["iso"]], int)
        pj = np.array([pr["col"].get(EV.ysym(s), -1) for s in C["syms"]], int)
        ident = {}
        idok = np.zeros(len(C["syms"]), bool)
        for k, s in enumerate(C["syms"]):
            j = pj[k]
            if j < 0:
                ident[s] = "no archived EQUITY daily history"
                continue
            yv = np.full(ci.size, np.nan)
            okd = ci >= 0
            with np.errstate(invalid="ignore", divide="ignore"):
                yv[okd] = pr["V"][ci[okd], j] / pr["F"][ci[okd], j]
            chk = EV.finra_identity(C["TV"][:, k], yv, M[:, k])
            if chk["ok"] is False:
                ident[s] = "Yahoo volume disagrees with FINRA's (identity check)"
                continue
            idok[k] = True
            ident[s] = "ok" if chk["ok"] else "ok (identity not checkable)"
        return {"C": C, "M": M, "last_snap": last_snap, "pj": pj, "idok": idok, "ident": ident}
    return CAL._cached(archive, ("b13sb_cnms",), load)


def month_ends(days: Sequence[str]) -> list:
    out = []
    for i in range(len(days) - 1):
        if days[i][:7] != days[i + 1][:7]:
            out.append(i)
    return out


def svr_formation(Bc: dict, pr: dict, snaps, m: int) -> Optional[dict]:
    """One T-676 formation at session m (decision at its close): signal, members, the price-backed eligible set, the
    residual and the legs; None when the hold (entry m+1, exit m+1+21) leaves the data."""
    C = Bc["C"]
    cal = pr["cal"]
    D = len(cal)
    if m + 1 + T676_HOLD >= D:
        return None
    i0 = int(np.searchsorted(C["days"], EV._ed(cal.days[m]), side="right")) - 1
    sig, _cnt = window_svr(C["SV"], C["TV"], i0)
    mem = EV.members_at(snaps, EV._ed(cal.days[m]))
    ismem = np.array([s in mem for s in C["syms"]], bool)
    U = ismem & np.isfinite(sig)
    pj = Bc["pj"]
    dvall = dollar_volume(pr["C"], pr["V"], m)
    j = np.where(pj >= 0, pj, 0)
    priced = U & Bc["idok"] & (pj >= 0) & pr["real"][m, j] & pr["real"][m + 1, j] & np.isfinite(dvall[j])
    dv = np.where(priced, dvall[j], np.nan)
    res = resid_on(sig, np.log(dv), priced)
    n = int(np.isfinite(res).sum())
    k = n // 5
    fl = SX.tail_fractions(res, priced, k, high=False)
    fs = SX.tail_fractions(res, priced, k, high=True)
    e, x = m + 1, m + 1 + T676_HOLD
    r = pr["Af"][x, j] / pr["Af"][e, j] - 1.0
    win = (max(0, i0 - T676_LO), i0 - T676_HI)
    return {"m": m, "e": e, "x": x, "label": cal.days[e], "U": int(U.sum()), "n": n, "k": k, "absent": int(U.sum()) - n,
            "fl": fl, "fs": fs, "elig": priced, "r": np.where(priced, r, np.nan), "dv": dv, "j": j,
            # review fix: a backfilled window = one ending before the 2021-05 restatement period ended (scattered later
            # flags no longer relabel post-2021 months)
            "backfilled": bool(C["days"][max(win[1], 0)] < EV._ed(BACKFILL_END)) if win[1] >= win[0] else False}


BACKFILL_END = "2021-05-01"


def ls_cohort(f: dict, weight: str = "ew", sign: float = 1.0) -> Optional[dict]:
    """Gross and net L/S of one cohort (long the bottom, short the top for sign +1): legs EW or weighted by dollar
    volume; net = gross - a full round trip on both legs (4 x 10 bp) - borrow on the short leg."""
    if f is None or f["k"] < 1:
        return None
    r = np.nan_to_num(f["r"])
    size = f["dv"] if weight == "vw" else None
    lw = f["fl"] * (size if size is not None else 1.0)
    sw = f["fs"] * (size if size is not None else 1.0)
    lw = np.where(np.isfinite(lw), lw, 0.0); sw = np.where(np.isfinite(sw), sw, 0.0)
    if not (lw.sum() > 0 and sw.sum() > 0):
        return None
    RL, RS = float(lw @ r / lw.sum()), float(sw @ r / sw.sum())
    if sign < 0:
        RL, RS = RS, RL
    return {"RL": RL, "RS": RS, "gross": RL - RS, "wl": lw / lw.sum(), "ws": sw / sw.sum()}


def t676_series(forms: Sequence[dict], cal, weight: str = "ew", sign: float = 1.0) -> dict:
    out = {k: [] for k in ("label", "gross", "net", "RL", "RS", "e", "x", "k", "n", "U", "absent", "backfilled", "ew_all")}
    for f in forms:
        c = ls_cohort(f, weight, sign)
        if c is None:
            continue
        days = (date.fromisoformat(cal.days[f["x"]]) - date.fromisoformat(cal.days[f["e"]])).days
        out["label"].append(f["label"]); out["gross"].append(c["gross"]); out["RL"].append(c["RL"]); out["RS"].append(c["RS"])
        out["net"].append(c["gross"] - 4 * COST - BORROW * days / 365.0)
        for key in ("e", "x", "k", "n", "U", "absent", "backfilled"):
            out[key].append(f[key])
        out["ew_all"].append(float(np.nanmean(f["r"][f["elig"]])))
    for key in list(out):
        if key != "label":
            out[key] = np.array(out[key], float)
    return out


def t676_netted(forms: Sequence[dict], Af: np.ndarray, cal) -> np.ndarray:
    """Reported cost reading: the cohorts chained (turnover against the previous cohort's weights drifted to its exit),
    10 bp per side on each leg's turnover, borrow as in the primary; final exit charged."""
    pL, pS = {}, {}
    net = []
    for f in forms:
        c = ls_cohort(f)
        if c is None:
            continue
        cols = f["j"]
        wl = {int(cols[i]): float(c["wl"][i]) for i in np.flatnonzero(c["wl"] > 0)}
        ws = {int(cols[i]): float(c["ws"][i]) for i in np.flatnonzero(c["ws"] > 0)}
        to = sum(abs(wl.get(k, 0) - pL.get(k, 0)) for k in set(wl) | set(pL))
        to += sum(abs(ws.get(k, 0) - pS.get(k, 0)) for k in set(ws) | set(pS))
        rel = lambda k: float(np.nan_to_num(Af[f["x"], k] / Af[f["e"], k], nan=1.0))
        dd = (date.fromisoformat(cal.days[f["x"]]) - date.fromisoformat(cal.days[f["e"]])).days
        net.append(c["gross"] - COST * to - BORROW * dd / 365.0)
        pL = {k: w * rel(k) / (1 + c["RL"]) for k, w in wl.items()}
        pS = {k: w * rel(k) / (1 + c["RS"]) for k, w in ws.items()}
    if net:
        net[-1] -= COST * (sum(pL.values()) + sum(pS.values()))
    return np.array(net, float)


def t676_path(forms: Sequence[dict], Af: np.ndarray) -> tuple:
    """Event-month gross L/S returns 1..12 of each formation (EW legs rebalanced at each month start); NaN past the
    data."""
    D = Af.shape[0]
    P = np.full((len(forms), T676_REV_MONTHS), np.nan)
    for i, f in enumerate(forms):
        c = ls_cohort(f)
        if c is None:
            continue
        L, S = np.flatnonzero(f["fl"] > 0), np.flatnonzero(f["fs"] > 0)
        for k in range(T676_REV_MONTHS):
            s = f["e"] + T676_HOLD * k
            t = s + T676_HOLD
            if t >= D:
                break
            rl = Af[t, f["j"][L]] / Af[s, f["j"][L]] - 1.0
            rs = Af[t, f["j"][S]] / Af[s, f["j"][S]] - 1.0
            wl, ws = f["fl"][L], f["fs"][S]
            okl, oks = np.isfinite(rl), np.isfinite(rs)
            if okl.any() and oks.any():
                P[i, k] = float((wl[okl] @ rl[okl]) / wl[okl].sum() - (ws[oks] @ rs[oks]) / ws[oks].sum())
    return P


def ls_absent_weights(U: np.ndarray, A: np.ndarray, n: np.ndarray, q: int) -> dict:
    """Absent-name leg shares (each leg): (P) A/U; (W) every absent member in the leg, up to floor((n + A)/q)."""
    U, A, n = (np.asarray(v, float) for v in (U, A, n))
    wp = np.where(U > 0, A / np.maximum(U, 1), 0.0)
    kq = np.floor((n + A) / q)
    ww = np.where(kq > 0, np.minimum(A, kq) / np.maximum(kq, 1), 0.0)
    return {"P": wp, "W": ww}


def b13_short_b_svr_xs_monthly(archive):
    """T-676."""
    miss = B7C._missing(archive, [SPY_B, FJA_B, CHG_B, CNMS_FIRST_B, FF5_B, MOM_B])
    if miss:
        return miss
    pr = prices(archive)
    Bc = cnms_base(archive)
    snaps = _snaps(archive)
    cal, days = pr["cal"], pr["cal"].days
    mes = month_ends(days)
    fo = [svr_formation(Bc, pr, snaps, m) for m in mes
          if m + 1 < len(days) and T676_ENTRY[0] <= days[m + 1] <= T676_ENTRY[1]]
    forms = [f for f in fo if f is not None and f["k"] >= 1]
    S = t676_series(forms, cal)
    n = len(S["label"])
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} month-end CNMS formations could be built (rule 9)")
    x = S["net"]
    labels = S["label"]
    t = mean_test(x, T676_BLOCK)
    hv = halves(x, labels, T676_SPLIT)
    fac = factor_table(archive, bab=False)
    Fm = period_factor_sums(days, fac, S["e"].astype(int), S["x"].astype(int), 6)
    alpha = ols_alpha(x, Fm, max(3, CAL.nw_lags(n)))
    V = t676_series(forms, cal, "vw")
    dsr, dsr_r = dsr_of(x, [x, V["net"]], T676_TRIALS, "DSR >= 0.95 at 2 trials (EW, VW by dollar volume)")
    P = t676_path(forms, pr["Af"])
    full = np.all(np.isfinite(P[:, 1:]), axis=1)
    car = P[full, 1:].sum(axis=1)
    rv = mean_test(car, T676_REV_BLOCK)
    if rv["mean"] is None:
        rev_ok, rev_txt = None, "no complete paths"
    elif rv["mean"] >= 0:
        rev_ok, rev_txt = True, "no reversal (the months 2-12 sum is not negative)"
    else:
        d = CAL.decide_p(rv["p_less"], rv["draws"])
        rev_ok = None if d is None else (not d)
        rev_txt = f"one-sided p_less {CAL._mc(rv['p_less'], rv['draws'])}"
    aw = ls_absent_weights(S["U"], S["absent"], S["n"], 5)
    tips = {}
    for rd, w in aw.items():
        xp = x - TIP * 2.0 * w
        tips[rd] = tip_rows_ok(xp, labels, T676_SPLIT, T676_BLOCK, None)
        tv = tipping_value(lambda r, w=w: x + r * 2.0 * w, T676_BLOCK, -2.0, 2.0)
        tips[rd]["tipping_delta"] = None if tv is None else -tv
        tips[rd]["w_mean"] = float(w.mean())
    tip_ok = CAL._agree([tips["P"]["ok"], tips["W"]["ok"]])
    unp = sorted(s for s, v in Bc["ident"].items() if not v.startswith("ok"))
    rows = [(f"one-sided 95% lower bound of the mean monthly net L/S > 0 (mean {_pc(t['mean'])}, p "
             f"{CAL._mc(t['p_greater'], t['draws'])}, NW t {_fmt(t['nw_t'], 2)}, 3-month blocks)", lb_ok(t), lb_decisive(t)),
            (f"both halves positive (entries 2018-11..2022-10 {_pc(hv[0])}, 2022-11..2026-09 {_pc(hv[1])})",
             None if any(h is None for h in hv) else all(h > 0 for h in hv), False),
            (f"FF5+UMD alpha NW t >= 2 (alpha {_pc(alpha['alpha'])} per month, t {_fmt(alpha['t'], 2)}, {alpha['n']} months, "
             f"lag {alpha['lag']})", None if alpha["t"] is None else bool(alpha["t"] >= 2.0),
             alpha["t"] is not None and alpha["t"] <= -2.0),
            dsr_r,
            (f"no significant reversal over months 2-12 (mean summed gross L/S {_pc(rv['mean'])} over {rv['n']} complete "
             f"paths; {rev_txt})", rev_ok, False),
            (f"absent names would need worse than -5% per month to erase the pass (lower bound and both halves still pass "
             f"with absent names 5% worse than their leg on both sides: proportional (mean leg share "
             f"{tips['P']['w_mean'] * 100:.1f}%) {tips['P']['ok']}, worst case ({tips['W']['w_mean'] * 100:.1f}%) "
             f"{tips['W']['ok']}; adverse return of absent names at which the HAC lower bound crosses zero "
             f"{_pc(tips['P']['tipping_delta'])} / {_pc(tips['W']['tipping_delta'])}, negative = they would have to beat "
             f"their leg to create a pass)", tip_ok, False),
            (f"registered pre-run fetch of the members Yahoo still serves ({len(unp)} of {len(Bc['ident'])} CNMS member "
             f"symbols without a usable archived price) [NOT IMPLEMENTED: the archive lacks them and this harness does not "
             f"fetch]", None, False)]
    rows = CAL._undecided(rows[:-1]) + rows[-1:]        # the not-implemented fetch row is not "undecided"
    verdict, why, crit = CAL._judge(rows, n, T676_MIN_N, "months")

    # ---- reported only
    rep = {"gross_mean": float(np.mean(S["gross"])), "vw": {"mean": float(np.mean(V["net"])), "n": int(V["net"].size)}}
    dix = t676_series(forms, cal, "ew", -1.0)
    rep["dix_reading_opposite_sign"] = {"net_mean": float(np.mean(dix["net"])), "gross_mean": float(np.mean(dix["gross"]))}
    bf = S["backfilled"].astype(bool)
    rep["backfilled_window_months"] = {"n": int(bf.sum()), "mean": float(np.mean(x[bf])) if bf.any() else None,
                                       "n_other": int((~bf).sum()), "mean_other": float(np.mean(x[~bf])) if (~bf).any() else None}
    boom = touches(labels, [days[int(i)] for i in S["x"]], *T676_BOOM)
    rep["retail_boom_2020_2021"] = {"with": t["mean"], "without": float(np.mean(x[~boom])) if (~boom).any() else None,
                                    "n_without": int((~boom).sum())}
    lvb = (S["RL"] - 2 * COST) - S["ew_all"]
    rep["long_leg_vs_ew_members"] = mean_test(lvb, T676_BLOCK)
    rep["cumulative_path_gross"] = [float(np.nanmean(np.nansum(P[:, :k + 1], axis=1)[np.all(np.isfinite(P[:, :k + 1]), axis=1)]))
                                    if np.all(np.isfinite(P[:, :k + 1]), axis=1).any() else None for k in range(T676_REV_MONTHS)]
    xn = t676_netted(forms, pr["Af"], cal)
    rep["netted_cost_reading"] = {**mean_test(xn, T676_BLOCK), "halves": halves(xn, labels, T676_SPLIT)}
    offs = {}
    for o in range(1, T676_OFFSETS + 1):
        fo_o = [svr_formation(Bc, pr, snaps, m - o) for m in mes
                if m + 1 < len(days) and T676_ENTRY[0] <= days[m + 1] <= T676_ENTRY[1]]
        so = t676_series([f for f in fo_o if f is not None and f["k"] >= 1], cal)
        offs[o] = float(np.mean(so["net"])) if so["net"].size else None
    ov = [v for v in offs.values() if v is not None]
    rep["entry_offsets"] = {"means": offs, "min": min(ov) if ov else None, "max": max(ov) if ov else None,
                            "positive": int(sum(v > 0 for v in ov)), "count": len(ov)}
    rep["tipping"] = tips
    rep["unpriced_symbols"] = unp
    rep["coverage"] = {"members_with_signal_mean": float(np.mean(S["U"])), "eligible_mean": float(np.mean(S["n"])),
                       "absent_mean": float(np.mean(S["absent"])), "leg_size_mean": float(np.mean(S["k"])),
                       "cnms_missing_months": Bc["C"]["missing_months"], "cnms_file_days": int(Bc["C"]["days"].size)}
    reason = (f"{n} month-end formations, entries {labels[0]}..{labels[-1]}: CNMS short/total volume over file days "
              f"-65..-6 (>= 40 present), residualised on log 60-session median dollar volume over point-in-time members "
              f"with an archived price (mean {rep['coverage']['eligible_mean']:.0f} of "
              f"{rep['coverage']['members_with_signal_mean']:.0f} members with a signal; {rep['coverage']['absent_mean']:.1f} "
              f"absent), EW bottom-minus-top quintile ({rep['coverage']['leg_size_mean']:.0f} names a leg) entered at the "
              f"next close, 21 sessions: gross {_pc(rep['gross_mean'])}, net of a 40 bp round trip and 0.3%/yr borrow "
              f"{_pc(t['mean'])} per month (p {CAL._p(t['p_greater'])}); halves {_pc(hv[0])} / {_pc(hv[1])}; FF5+UMD alpha "
              f"t {_fmt(alpha['t'], 2)}; DSR {_fmt(dsr.get('dsr'))}; months 2-12 summed gross {_pc(rv['mean'])}. Reported: VW "
              f"(dollar-volume weights) {_pc(rep['vw']['mean'])}; DIX reading (opposite sign) net "
              f"{_pc(rep['dix_reading_opposite_sign']['net_mean'])}; windows ending before 2021-05 (restated files) {bf.sum()} months "
              f"{_pc(rep['backfilled_window_months']['mean'])} vs {_pc(rep['backfilled_window_months']['mean_other'])}; "
              f"without 2020-2021 {_pc(rep['retail_boom_2020_2021']['without'])}; long leg vs EW members "
              f"{_pc(rep['long_leg_vs_ew_members']['mean'])}; turnover-netted costs {_pc(rep['netted_cost_reading']['mean'])} "
              f"(p {CAL._p(rep['netted_cost_reading']['p_greater'])}, halves "
              f"{' / '.join(_pc(h) for h in rep['netted_cost_reading']['halves'])}); "
              f"entry offsets 1..20 sessions before month-end net {_pc(rep['entry_offsets']['min'])}..{_pc(rep['entry_offsets']['max'])} "
              f"({rep['entry_offsets']['positive']} of {rep['entry_offsets']['count']} positive). SURVIVORSHIP: prices are the "
              f"archive's 901-symbol daily-history set (today's universe); {len(unp)} CNMS member symbols have no usable "
              f"price and are absent from both legs; the tipping-point bound covers them")
    stat = {"n": n, "primary": t, "halves": hv, "alpha": alpha, "dsr": dsr, "reversal": rv, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# =============================================================================================== T-677 harness ==

def filings(archive, ciks: set) -> dict:
    """{cik: sorted acceptance epochs of its 10-Q / 10-K filings} from the sec-submissions buckets (reported only)."""
    def load():
        out: dict = {}
        for nm in SX._entry_names(archive, SUBS_PREFIX):
            for r in SX._stream(archive, nm):
                if r.get("kind") != "filing":
                    continue
                v = r.get("value") or {}
                if v.get("form") not in FILING_FORMS:
                    continue
                try:
                    c = int(v.get("cik"))
                    a = SX._ts(v.get("acceptance_json") or r["available_at"])
                except (TypeError, ValueError, KeyError):
                    continue
                if c in ciks:
                    out.setdefault(c, []).append(a)
        return {c: np.array(sorted(v)) for c, v in out.items()}
    return CAL._cached(archive, ("b13sb_filings",), load)


def t677_formation(B: dict, r: int, snaps, drop_rev: bool = False) -> dict:
    """Members at release r's entry with a usable FINRA row, price and SUSI (issuer SIR history of >= 20 of the prior 24
    releases): columns, SUSI, changePercent, market cap, counts."""
    f = member_rows(B, r, snaps)
    S = susi_at(B["SIR"], r)
    su = np.array([S[B["kc"][c]] for c in f["cik"]], float) if f["cik"].size else np.zeros(0)
    keep = np.isfinite(su)
    if drop_rev:
        keep &= ~f["rflag"]
    f["susi"] = su
    f["elig"] = keep
    f["n"] = int(keep.sum())
    f["no_susi"] = int((~np.isfinite(su)).sum())
    return f


def t677_book(forms: Sequence[dict], Af: np.ndarray, cal, sig: str = "susi", weight: str = "ew") -> dict:
    periods = [(f["e"], f["x"]) for f in forms]
    L, S, ALL = [], [], []
    for f in forms:
        score = f[sig]
        el = f["elig"] & np.isfinite(score)
        k = int(el.sum()) // 10
        fl = SX.tail_fractions(score, el, k, high=False)
        fs = SX.tail_fractions(score, el, k, high=True)
        wl = ew_weights(fl) if weight == "ew" else val_weights(fl, f["mcap"])
        ws = ew_weights(fs) if weight == "ew" else val_weights(fs, f["mcap"])
        wa = ew_weights(f["elig"].astype(float))
        L.append(None if wl is None or k < 1 else (f["col"][wl[0]], wl[1]))
        S.append(None if ws is None or k < 1 else (f["col"][ws[0]], ws[1]))
        ALL.append(None if wa is None else (f["col"][wa[0]], wa[1]))
    tl, ts, ta = leg_track(periods, L, Af), leg_track(periods, S, Af), leg_track(periods, ALL, Af)
    dd = np.array([(date.fromisoformat(cal.days[x]) - date.fromisoformat(cal.days[e])).days for e, x in periods], float)
    net = tl["R"] - ts["R"] - COST * (tl["TO"] + ts["TO"]) - BORROW * dd / 365.0
    if net.size:
        net[-1] -= COST * (tl["exit"] + ts["exit"])
    longnet = tl["R"] - COST * tl["TO"]
    if longnet.size:
        longnet[-1] -= COST * tl["exit"]
    return {"net": net, "gross": tl["R"] - ts["R"], "RL": tl["R"], "RS": ts["R"], "long_vs_ew": longnet - ta["R"],
            "long_vs_ew_gross": tl["R"] - ta["R"], "TO": tl["TO"] + ts["TO"], "legs": (L, S)}


def t677_filing_split(forms: Sequence[dict], Af: np.ndarray, cal, fil: dict, legs: tuple) -> dict:
    """Reported: gross L/S on names whose holding window (close e, close x] contains a 10-Q/10-K acceptance vs names
    whose window does not (EW within each leg's subgroup)."""
    w_with, w_without = [], []
    for f, lg, sg in zip(forms, legs[0], legs[1]):
        if lg is None or sg is None:
            continue
        a, b = float(cal.close[f["e"]]), float(cal.close[f["x"]])
        col2cik = dict(zip(f["col"].tolist(), f["cik"].tolist()))

        def split(leg):
            cols = np.asarray(leg[0], int)
            r = Af[f["x"], cols] / Af[f["e"], cols] - 1.0
            flag = np.array([bool(((fil.get(col2cik[c], np.zeros(0)) > a) & (fil.get(col2cik[c], np.zeros(0)) <= b)).any())
                             for c in cols.tolist()], bool)
            return r, flag
        rl, fl = split(lg)
        rs, fs = split(sg)
        if fl.any() and fs.any():
            w_with.append(float(np.nanmean(rl[fl]) - np.nanmean(rs[fs])))
        if (~fl).any() and (~fs).any():
            w_without.append(float(np.nanmean(rl[~fl]) - np.nanmean(rs[~fs])))
    return {"with_filing": {"n": len(w_with), "mean": float(np.mean(w_with)) if w_with else None},
            "without_filing": {"n": len(w_without), "mean": float(np.mean(w_without)) if w_without else None}}


def t677_forms(B: dict, snaps, month_end: bool, drop_rev: bool = False) -> list:
    rels = B["rels"]
    days = B["pr"]["cal"].days
    idx = [r for r, rel in enumerate(rels) if rel["e"] is not None
           and ((int(rel["settle"][8:10]) >= MONTH_END_DAY) == month_end)]
    out = []
    for a, b in zip(idx[:-1], idx[1:]):
        rel = rels[a]
        if not (T677_ENTRY[0] <= days[rel["e"]] <= T677_ENTRY[1]) or rels[b]["e"] <= rel["e"]:
            continue
        f = t677_formation(B, a, snaps, drop_rev)
        f["x"] = rels[b]["e"]
        if f["n"] // 10 >= 1:
            out.append(f)
    return out


def b13_short_b_susi_monthly(archive):
    """T-677."""
    need = [SPY_B, FJA_B, CHG_B, TICK_B, FF5_B, MOM_B, SI_FIRST_B]
    need += [SX.finra_name(d) for d in SX.finra_expected(T677_ENTRY[0], T677_ENTRY[1])]
    miss = B7C._missing(archive, need)
    if miss:
        return miss
    if not SX._entry_names(archive, FACTS_PREFIX):
        return B7C._missing(archive, [FACTS_PREFIX + "b000"])
    B = si_base(archive)
    pr = B["pr"]
    cal, days = pr["cal"], pr["cal"].days
    snaps = _snaps(archive)
    forms = t677_forms(B, snaps, True)
    n = len(forms)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} month-end SUSI formations could be built (rule 9)")
    bk = t677_book(forms, pr["Af"], cal)
    x = bk["net"]
    labels = [f["label"] for f in forms]
    t = mean_test(x, T677_BLOCK)
    hv = halves(x, labels, T677_SPLIT)
    fac = factor_table(archive, bab=False)
    Fm = period_factor_sums(days, fac, [f["e"] for f in forms], [f["x"] for f in forms], 6)
    alpha = ols_alpha(x, Fm, max(3, CAL.nw_lags(n)))
    fam = {"susi_ew": x, "susi_vw": t677_book(forms, pr["Af"], cal, "susi", "vw")["net"],
           "chg_ew": t677_book(forms, pr["Af"], cal, "chg", "ew")["net"],
           "chg_vw": t677_book(forms, pr["Af"], cal, "chg", "vw")["net"]}
    dsr, dsr_r = dsr_of(x, list(fam.values()), T677_TRIALS, "DSR >= 0.95 at 4 trials (EW/VW x SUSI/changePercent)")
    U = np.array([f["cnt"]["finra"] for f in forms]); A = np.array([f["cnt"]["absent"] for f in forms])
    nn = np.array([f["n"] for f in forms])
    aw = ls_absent_weights(U, A, nn, 10)
    tips = {}
    for rd, w in aw.items():
        xp = x - TIP * 2.0 * w
        tips[rd] = tip_rows_ok(xp, labels, T677_SPLIT, T677_BLOCK, None)
        tv = tipping_value(lambda r, w=w: x + r * 2.0 * w, T677_BLOCK, -2.0, 2.0)
        tips[rd]["tipping_delta"] = None if tv is None else -tv
        tips[rd]["w_mean"] = float(w.mean())
    tip_ok = CAL._agree([tips["P"]["ok"], tips["W"]["ok"]])
    n_unpriced = len(pr["unpriced_tickers"])
    rows = [(f"one-sided 95% lower bound of the mean monthly net L/S > 0 (mean {_pc(t['mean'])}, p "
             f"{CAL._mc(t['p_greater'], t['draws'])}, NW t {_fmt(t['nw_t'], 2)}, 3-month blocks)", lb_ok(t), lb_decisive(t)),
            (f"FF5+UMD alpha NW t >= 2 (alpha {_pc(alpha['alpha'])} per month, t {_fmt(alpha['t'], 2)}, {alpha['n']} months, "
             f"lag {alpha['lag']})", None if alpha["t"] is None else bool(alpha["t"] >= 2.0),
             alpha["t"] is not None and alpha["t"] <= -2.0),
            (f"both halves positive (entries 2019-01..2022-12 {_pc(hv[0])}, 2023-01..2026-09 {_pc(hv[1])})",
             None if any(h is None for h in hv) else all(h > 0 for h in hv), False),
            dsr_r,
            (f"absent names would need worse than -5% per month to erase the pass (lower bound and both halves still pass "
             f"with absent names 5% worse than their leg on both sides: proportional (mean leg share "
             f"{tips['P']['w_mean'] * 100:.1f}%) {tips['P']['ok']}, worst case ({tips['W']['w_mean'] * 100:.1f}%) "
             f"{tips['W']['ok']}; adverse return of absent names at which the HAC lower bound crosses zero "
             f"{_pc(tips['P']['tipping_delta'])} / {_pc(tips['W']['tipping_delta'])}, negative = they would have to beat "
             f"their leg to create a pass)", tip_ok, False),
            (f"registered pre-run fetch of every member Yahoo still serves ({n_unpriced} member tickers 2016-06..2026-10 "
             f"have no archived EQUITY daily history) [NOT IMPLEMENTED: the archive lacks them and this harness does not "
             f"fetch]", None, False)]
    rows = CAL._undecided(rows[:-1]) + rows[-1:]        # the not-implemented fetch row is not "undecided"
    verdict, why, crit = CAL._judge(rows, n, T677_MIN_N, "monthly formations")

    # ---- reported only
    rep = {"gross_mean": float(np.mean(bk["gross"])), "turnover_mean": float(np.mean(bk["TO"])),
           "variants": {k: float(np.mean(v)) for k, v in fam.items()}}
    rep["long_bottom_decile_vs_ew_members"] = {"net": mean_test(bk["long_vs_ew"], T677_BLOCK),
                                               "gross_mean": float(np.mean(bk["long_vs_ew_gross"]))}
    fr = t677_forms(B, snaps, True, drop_rev=True)
    rep["revision_flag_rows_excluded"] = {"n": len(fr), "mean": float(np.mean(t677_book(fr, pr["Af"], cal)["net"])) if fr else None}
    mm = t677_forms(B, snaps, False)
    rep["mid_month_phase"] = mean_test(t677_book(mm, pr["Af"], cal)["net"], T677_BLOCK) if len(mm) >= 8 else {"n": len(mm)}
    fil = filings(archive, set(B["sec"]["ciks"]))
    rep["filing_window_interaction"] = t677_filing_split(forms, pr["Af"], cal, fil, bk["legs"])
    rep["coverage"] = {"members_mean": float(np.mean([f["cnt"]["members"] for f in forms])),
                       "finra_rows_mean": float(np.mean(U)), "absent_mean": float(np.mean(A)),
                       "no_shares_mean": float(np.mean([f["cnt"]["no_shares"] for f in forms])),
                       "bad_sir_mean": float(np.mean([f["cnt"]["bad_sir"] for f in forms])),
                       "no_susi_mean": float(np.mean([f["no_susi"] for f in forms])), "sorted_mean": float(np.mean(nn)),
                       "decile_mean": float(np.mean(nn // 10))}
    rep["tipping"] = tips
    rep["unpriced_member_tickers"] = pr["unpriced_tickers"]
    fw = rep["filing_window_interaction"]
    reason = (f"{n} month-end FINRA settlement releases with entries {labels[0]}..{labels[-1]} (first close after "
              f"available_at, held to the next month-end release's entry): SUSI = issuer SIR (split-adjusted SI over cover "
              f"shares) minus the mean of the prior 24 releases over their sd (>= 20 present), point-in-time members with a "
              f"usable FINRA row, shares and price (mean {rep['coverage']['sorted_mean']:.0f} of "
              f"{rep['coverage']['members_mean']:.0f}; {rep['coverage']['absent_mean']:.1f} absent, "
              f"{rep['coverage']['no_susi_mean']:.1f} without SUSI, {rep['coverage']['bad_sir_mean']:.1f} with an SIR outside "
              f"(0, 1]); EW bottom-minus-top decile "
              f"({rep['coverage']['decile_mean']:.0f} names a leg), 10 bp per side on turnover "
              f"({rep['turnover_mean']:.2f} per month, both legs) and 0.3%/yr borrow: gross {_pc(rep['gross_mean'])}, net "
              f"{_pc(t['mean'])} per month (p {CAL._p(t['p_greater'])}); halves {_pc(hv[0])} / {_pc(hv[1])}; FF5+UMD alpha "
              f"t {_fmt(alpha['t'], 2)}; DSR {_fmt(dsr.get('dsr'))}. Reported: SUSI VW {_pc(rep['variants']['susi_vw'])}, "
              f"changePercent EW {_pc(rep['variants']['chg_ew'])} / VW {_pc(rep['variants']['chg_vw'])}; long bottom decile vs "
              f"EW members net {_pc(rep['long_bottom_decile_vs_ew_members']['net']['mean'])}; revision-flag rows excluded "
              f"{_pc(rep['revision_flag_rows_excluded']['mean'])}; mid-month phase {_pc(rep['mid_month_phase'].get('mean'))}; "
              f"holds containing a 10-Q/10-K acceptance gross L/S {_pc(fw['with_filing']['mean'])} vs without "
              f"{_pc(fw['without_filing']['mean'])}. SURVIVORSHIP: prices are the archive's 901-symbol daily-history set "
              f"(today's universe); {n_unpriced} member tickers have no archived EQUITY series and are absent from both "
              f"legs; the tipping-point bound covers them")
    stat = {"n": n, "primary": t, "halves": hv, "alpha": alpha, "dsr": dsr, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


HARNESSES = {"b13_short_b_low_si_long": b13_short_b_low_si_long,
             "b13_short_b_svr_xs_monthly": b13_short_b_svr_xs_monthly,
             "b13_short_b_susi_monthly": b13_short_b_susi_monthly}
THEORY_MAP = {"T-675": "b13_short_b_low_si_long", "T-676": "b13_short_b_svr_xs_monthly",
              "T-677": "b13_short_b_susi_monthly"}
