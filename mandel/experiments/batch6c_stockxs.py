"""
Batch 6c, group ``stockxs``: four single-stock cross-sectional claims on the FINRA, SEC EDGAR, fja05680 and Yahoo
single-stock bundles.
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-375  FINRA days-to-cover deciles, May 2020..Sep 2026: the top decile underperforms the bottom decile by more than
           0.83% per month over the following month; p < 0.05 in the equal- AND value-weighted versions (Newey-West t
           and the block bootstrap by period, both named: rule 11), the same sign in >= 5 of the 7 calendar years, DSR
           (n_trials = 3) > 0.95; min_n 120 formation dates.
  * T-393  top-1000 US stocks by point-in-time market cap, bottom minus top days-to-cover decile over each release
           period after borrow, 2017-12..2026-09: lower 95% bound > 0 over >= 150 release dates, FF5 alpha t >= 2, and
           the lower bound > 0 without the Jan-Mar 2021 squeeze; min_n 150 release dates.
  * T-451  Piotroski F-score 8-9 minus 0-2 within the top book-to-market quintile, 12 months after each 10-K acceptance,
           calendar-time months 2011..2026-09: lower 95% bound > 0 over >= 150 months and FF5 alpha t >= 2 (at both
           ends of the stated 10-20 bp per side); min_n 150 months.
  * T-473  Avellaneda-Lee sector-ETF s-score statistical arbitrage on S&P 500 point-in-time members with Yahoo prices,
           2010..2026: 95% lower bound of the annualised net Sharpe > 0 (stationary bootstrap, mean block 20 days), DSR >
           0.95 and CSCV PBO < 0.5 over the 5 declared variants; min_n 2,000 trading days.

Data (every bundle through ``archive.load``; a row counts only when its ``available_at`` is not after the bundle's
capture time)
  * Prices: Yahoo ``daily-history-<TICKER>`` (open/high/low/close split-adjusted, adjclose split and dividend adjusted:
    total return) with splits from ``daily-events-<TICKER>``. Raw prices (the $5 filters, dollar volume) are close x
    the product of the split ratios with an ex-date after the bar. Market cap = split-adjusted close x reported shares x
    the split factor after the shares' as-of date (so a split between the cover date and the decision is honoured). The
    SEC cover count sums an issuer's share classes, so for T-375 and T-393 each listed class (the FINRA stock rows of
    the same CIK) gets an equal part of it at its own price (GOOG and GOOGL are not each counted at Alphabet's cap), and
    no cap when the issuer's classes trade more than 2x apart (BRK-A / BRK-B). A stock without a usable cap is never
    given a silent zero weight or dropped from a ranking: it leaves T-375's VW criteria and every T-393 criterion NOT
    JUDGED (rule 9), like an unpriced name. A
    Yahoo series is a stock only when its recipe meta says instrumentType EQUITY (13 reused S&P tickers now name ETFs:
    FB, EMC, INFO, ...). The session calendar is SPY's bars.
  * SURVIVORSHIP. Yahoo answers 404 for delisted tickers, so only the names still quoted have prices (about 640 single
    stocks, all drawn from the fja05680 S&P 500 ticker list). T-375, T-393 and T-451 are defined on universes that
    include the delisted, the small and the non-S&P names: every harness measures the share of its point-in-time
    universe without a usable price and, whenever that share is above zero, returns None for every criterion whose
    answer depends on those names (all of their return criteria: decile and quintile breakpoints, legs and means all
    move with the missing names, whose returns are unbounded above). Everything is still computed on the priced
    subset and reported as a SURVIVOR-ONLY diagnostic, never as the claim's statistic. T-473's claim is itself defined
    on "members with Yahoo prices", so its survivorship is the claim's and every criterion is judged (the reason states
    the bias and the share of member-days without prices).
  * Identity checks. A FINRA row is matched to a Yahoo series by its symbol (class shares BRKB -> BRK-B) only when the
    FINRA issue name (point in time) agrees with a name the instrument has carried: Yahoo's longName or the SEC conformed
    or former names of the ticker's current CIK (renames such as Cliffs Natural Resources -> Cleveland-Cliffs keep
    their history). Names agree on their first significant word (on the first two when the first is generic:
    'American', 'First', ...), prefix-tolerant for FINRA's 30-character truncation. This rejects reused tickers whose
    Yahoo history belongs to another company (CPWR is now Ocean Thermal with bars from 2006, EP Empire Petroleum, KG
    Kestrel). For T-473 a current member (Wikipedia's constituents) needs no check; a removed member's Wikipedia removal
    name must agree the same way.
  * FINRA short interest (``finra-short-interest-<settlement>``): days to cover = currentShortPositionQuantity /
    averageDailyVolumeQuantity, the library's definition (FINRA's own daysToCoverQuantity is floored at 1.00 and capped
    at 999.99). Stocks = the fetcher's company market classes (NYSE, Nasdaq tiers, NYSE American, TXSE; Arca, BZX and
    IEX listings are funds) minus fund/warrant/unit/right/note/preferred names (fund sponsors that also name operating
    companies, Invesco and Vanguard, mark a fund only as the first word of a name without a corporate ending, so
    Invesco Ltd and American Vanguard stay stocks). Available at the end of the 8th NYSE
    business day after settlement (the fetcher's rule, one day after FINRA's usual publication), so the first fill is
    the close of the next session; the filters and value weights use the previous close and the shares known at that
    session's open (one information set, rule 12). The expected settlement dates come from the fetcher's own calendar
    rule (``finra_si_calendar``), so a missing bundle is named.
  * SEC: ``sec-company-tickers`` (current ticker -> CIK), ``sec-companyfacts-b<NNN>`` (XBRL facts with their accession
    and available_at = min(acceptance, filed date 22:00 ET); point in time = the filing's acceptance, never the period
    end), ``sec-submissions-b<NNN>`` (company profile: SIC for removed S&P members). Shares = dei
    EntityCommonStockSharesOutstanding (the values of one accession and cover date summed across share classes),
    us-gaap CommonStockSharesOutstanding when an accession has no cover value; at most 15 months old. XBRL begins in
    2009-2011, so fundamentals before a filer's first XBRL filing do not exist (None, never back-filled).
  * Factors: ``french-ff5-daily`` (percent; through 2026-08-31, so later periods have no alpha observation), bills
    ``fred-DTB3`` (rule 7: discount yield -> continuous rate, the print dated before each day), VIX ``cboe-VIX-history``.

Statistics (rule 6)
  * Means: studentized circular block bootstrap (Bartlett-HAC s.e., bandwidth = block; batch6b_bw._stud), 5,000 draws
    per seed averaged over 5 seeds with their Monte Carlo s.e. (escalated to 25 seeds when 5 cannot resolve a bound).
    "Lower 95% bound" is the lower end of the two-sided 95% interval (house convention). Blocks: T-375 4 formation
    dates (>= twice its 2-date overlap), T-393 6 release periods (the trial's), T-451 12 months (>= the 12-month hold).
  * Newey-West: Bartlett weights 1 - l/(L+1); T-375 L = max(2, floor(4 (n/100)^(2/9))) (>= its overlap); alphas use
    L = 6 periods (T-393) and 12 months (T-451). FF5 alpha = the intercept of the period return on the five factors
    summed (T-393) or compounded (T-451) over the same days.
  * T-473 Sharpe: stationary bootstrap (Politis-Romano, mean block 20 days, the trial's) percentile interval of the
    annualised Sharpe of daily net excess returns (rule 7: 252 days, bills subtracted). DSR via batch6c_mom.family_dsr
    (trial-Sharpe variance = the 5 variants' observed variance floored at 1/(T-1)); PBO = overfit.pbo_cscv on the 5
    variants' daily returns (its default 8 partitions).
  * Rule 5: below min_n a failing criterion counts only when it fails decisively (the bound at the pass's own confidence
    wholly on the wrong side, or a count that would still fail if every missing year went the claim's way).

Claim-specific choices (declared before any result)
  * T-375: hold = one calendar month from the fill (the claim's "over the following month"), one cohort per FINRA
    formation, so consecutive cohorts overlap by half; the library's hold-to-next-publication is a family member.
    Universe: raw price > $5 and dollar ADV (FINRA ADV x price) > $5m at the previous close. Deciles: floor(n/10) names
    per tail, names tied at a boundary share its slots. Costs 10 bp per side on each leg's entry and exit (40 bp per
    unit-long/unit-short cohort; gross reported). Statistic x = (bottom - top) net - 0.83% per period (pro rata 0.83% x
    days/30.44 for the half-month member). Years = calendar years of the fill. DSR family (3): 1-month DTC sort
    (primary), hold to the next publication, short-interest change (changePercent) sort. The 2021 meme squeeze (fills
    Jan-Mar 2021) is reported with and without; the -30% delisting sensitivity applies to priced names whose series ends
    inside a hold (whole paths of delisted names are missing, so it cannot repair the survivorship).
  * T-393: entry at the first close after publication, hold to the next entry; universe = the 1,000 largest priced
    stocks by market cap at the previous close with raw price >= $5, then DTC > 10 dropped (the library's hard-to-borrow
    proxy); equal-weight bottom (long) and top (short) DTC deciles, dollar-neutral, rebalanced each release with drift-
    adjusted turnover at 5 bp per side; borrow on the short leg 1%/yr, "higher for DTC 5-10" read as 3%/yr (stated; 1%
    and 10% reported). The squeeze criterion drops every period whose hold touches 2021-01-01..2021-03-31. The rule's
    5% vol-target sizing is not in the claim or the trial's statistic and is not applied.
  * T-451: F-score (Piotroski 2000) from the 10-K's own accession for fiscal years t and t-1 and the prior 10-K for the
    t-2 assets (both known at acceptance): ROA = NI / beginning assets > 0; CFO / beginning assets > 0; dROA > 0;
    CFO > NI (scaled); d(long-term debt / average assets) < 0 (missing debt = 0); d current ratio > 0; no common
    issuance (ProceedsFromIssuanceOfCommonStock > 0 = issued; missing = none); d gross margin > 0; d asset turnover > 0.
    Every signal must be computable (banks without current ratios drop out). Book equity = stockholders' equity minus
    preferred stock. Entry at the first close after acceptance, price >= $5 at the previous close; top quintile =
    B/M at or above the 80th percentile of the priced 10-K filers' B/M at the previous month-end (latest 10-K book
    equity, positive only). Hold 12 months; a newer 10-K of the same firm replaces the position. Calendar-time legs
    are equal-weight daily (cost per side charged on entry and exit days, none for a firm that stays in its leg; the
    short position's costs are added to the short leg's return, so both legs' costs lower the L/S); a month is an
    observation when both legs hold at least one name on every session of the month.
  * T-473: daily on each signal close t: OLS of each member's last 60 daily returns on its sector SPDR's (intercept
    included, so the cumulative residual X ends at 0), AR(1) X_{k+1} = a + b X_k on the 60 points, kappa = -ln(b) x 252,
    m = a/(1-b), sigma_eq = sqrt(var(zeta)/(1-b^2)), s = (X_t - (m - mean m))/sigma_eq (cross-sectional mean of m over
    the day's valid fits). Open long s < -1.25 / short s > +1.25 only when kappa > 252/30; close longs at s > -0.5,
    shorts at s < +0.75 (closes need only 0 < b < 1; a member without a valid 60-day window or out of the index is
    closed). Trades at the next close (signal close t, fill close t+1). Each position 2% of capital (Avellaneda-Lee's
    Lambda), scaled down equally when more than 100 are open so the stock gross never exceeds 2x; each hedged with
    -beta units of its ETF (netted per ETF). 5 bp per side per trade, read two ways that must agree (every criterion
    passes or fails only when both readings do; a disagreement is undecided, rule 11/12 spirit): (a) every traded dollar
    against the drifted holdings (daily rebalancing to equal dollars and hedge-ratio updates are trades), (b) Avellaneda-
    Lee's own equity equation, eps x sum |Q(t+1) - Q(t)| on the target notionals (drift not charged). 50 bp/yr borrow on
    short notional (stocks and ETFs), daily excess return = sum of holdings x (return - bill return). Sectors: Wikipedia GICS for current members (Real Estate -> XLRE, XLF before XLRE has a 60-day window;
    Communication Services -> XLC, before XLC: XLK for telecom and interactive media, else XLY; the current GICS is ex
    post), SEC SIC for removed members (declared map ``sic_etf``; 6798 REITs XLRE/XLF; publishing, broadcasting,
    advertising and film XLC/XLY; telephone XLC/XLK). Variants (5, the library's): sector-ETF (primary); 15-factor PCA
    (eigenportfolios v/sigma of the trailing-252-day correlation matrix of members with a full window, re-estimated
    daily, hedged in the eigenportfolios' stocks); volume "trading time" (stock returns x trailing 10-day mean volume /
    that day's volume, in the regression and the s-score only); thresholds 1.0/0.25/0.25; VIX-conditioned (new
    entries only when VIX at the signal close is above its trailing-252-session median). Membership: fja05680
    (effective dates) with later Wikipedia changes; halves 2010-2017 and 2018-2026, 2020-03 and 2022 reported.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing ->
not_supported; any criterion not implemented (None) -> at best inconclusive; supported needs every criterion
implemented and passing.
"""

from __future__ import annotations

import bisect
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.data.public_history import FINRA_COMPANY_CLASSES, finra_si_calendar
from mandel.experiments.batch6b_bw import (Bills, _ci_crit, _clean, _decide, _mean_stat, _stud, all_constructions,
                                           mc_escalate, resolve)
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import sharpe_ratio

N_BOOT = 5000
REPS = 5
SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
_N = NormalDist()
UTC = timezone.utc
NY = ZoneInfo("America/New_York")

SPY_B = "daily-history-SPY"
DTB3_B = "fred-DTB3"
VIX_B = "cboe-VIX-history"
FF5_B = "french-ff5-daily"
FJA_B = "fja-sp500-components"
WIKI_B = "wikipedia-sp500-constituents"
WIKI_CH_B = "wikipedia-sp500-changes"
SEC_TICK_B = "sec-company-tickers"
FINRA_PREFIX = "finra-short-interest-"
FACTS_PREFIX = "sec-companyfacts-"
SUBS_PREFIX = "sec-submissions-"
SEC_BUCKET = 50_000
SHARES_MAX_AGE = 456          # days: cover shares older than about 15 months are stale
CLASS_PRICE_RATIO = 2.0       # an issuer's cover count is split across its listed classes only when they trade this close
CAL_START = "2008-01-01"
SECTOR_ETFS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC")
FF5_COLS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
NOT_STOCK = re.compile(r"(?i)\b(ETF|ETN|FUND|FD|WARRANTS?|WTS?|RIGHTS?|UNITS?|PREFERRED|PFD|NOTES?|DEBENTURES?|BONDS?|"
                       r"TRUST UNITS|INDEX|ISHARES|PROSHARES|DIREXION|SPDR)\b|%")
# Fund sponsors whose name is also an operating company's (Invesco Ltd, Invesco Mortgage Capital Inc., American Vanguard
# Corp): a fund marker only as the name's first word and when the name does not end in a corporate form (FINRA's
# 30-character names truncate the fund words: 'Invesco BulletShares 2025 Corp', 'Vanguard Scottsdale Funds Vang').
FUND_SPONSOR = re.compile(r"(?i)^\W*(INVESCO|VANGUARD)\b(?!.*\b(INC|INCORPORATED|LTD|LIMITED|PLC)\W*$)")


def _safe(sym: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def dh(sym: str) -> str:
    return "daily-history-" + _safe(sym)


def de(sym: str) -> str:
    return "daily-events-" + _safe(sym)


def ysym(t: str) -> str:
    """fja05680 / Wikipedia / SEC spelling (BRK.B, BRK-B) -> Yahoo (BRK-B)."""
    return t.strip().upper().replace(".", "-").replace("/", "-")


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
        v, why = _verdict([(f"data bundles {miss[:12]}{' ...' if len(miss) > 12 else ''} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss[:12]}{f' and {len(miss) - 12} more' if len(miss) > 12 else ''}: the claim "
                f"cannot be tested until they are archived — {why}")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _stream(archive, name: str):
    """Stream a large bundle's rows (not cached), with the same capture-time filter."""
    cap = getattr(archive.get(name), "created_at", None)
    for r in archive.load(name):
        if not (cap and r.get("available_at") and r["available_at"] > cap):
            yield r


def _entry_names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if e.name.startswith(prefix))


def _meta(archive, name: str) -> dict:
    try:
        rec = archive.get(name).recipe or ""
    except (KeyError, AttributeError):
        return {}
    m = re.search(r"meta (\{[^{}]*\})", rec)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except ValueError:
        return {}


# ============================================================================================= time and calendar ==

def _ts(s: str) -> float:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp()


def _et_ts(day: str, hh: int, mm: int) -> float:
    y, m, d = int(day[:4]), int(day[5:7]), int(day[8:10])
    return datetime(y, m, d, hh, mm, tzinfo=NY).timestamp()


def _add_months(day: str, k: int) -> str:
    y, m, d = int(day[:4]), int(day[5:7]), int(day[8:10])
    m0 = m - 1 + k
    y, m = y + m0 // 12, m0 % 12 + 1
    for dd in (d, 30, 29, 28):
        try:
            return date(y, m, min(d, dd)).isoformat()
        except ValueError:
            continue
    return date(y, m, 28).isoformat()


class Cal:
    """Session calendar (SPY's bars): days, ordinals, 16:00 ET close and 09:30 ET open epoch seconds."""

    def __init__(self, days: Sequence[str]):
        self.days = list(days)
        self.pos = {d: i for i, d in enumerate(self.days)}
        self.ords = np.array([date.fromisoformat(d).toordinal() for d in self.days], np.int64)
        self.close = np.array([_et_ts(d, 16, 0) for d in self.days], float)
        self.open = np.array([_et_ts(d, 9, 30) for d in self.days], float)

    def __len__(self):
        return len(self.days)

    def entry_after(self, ts: float) -> int:
        """Index of the first session whose close is strictly after ``ts`` (len when none)."""
        return int(np.searchsorted(self.close, ts, side="right"))

    def on_or_before(self, day: str) -> int:
        return bisect.bisect_right(self.days, day) - 1

    def on_or_after(self, day: str) -> int:
        return bisect.bisect_left(self.days, day)


def _bar_day(t) -> str:
    return datetime.fromtimestamp(float(t), tz=UTC).strftime("%Y-%m-%d")


def _sessions(archive, start: str = CAL_START) -> Cal:
    def load():
        days = set()
        for r in _rows(archive, SPY_B):
            v = r.get("value") or {}
            try:
                if float(v.get("close")) > 0:
                    days.add(_bar_day(v["t"]))
            except (TypeError, ValueError, KeyError):
                continue
        return Cal(sorted(d for d in days if d >= start))
    return _cached(archive, ("cal", start), load)


def _closes(archive, name: str, field: str = "value") -> dict:
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r.get("value") or {}
            d = v.get("day")
            x = v.get(field) if field in v else v.get("close")
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if d and math.isfinite(x):
                out[d] = x
        return out
    return _cached(archive, ("closes", name, field), load)


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_closes(archive, DTB3_B)))


def _ff5(archive) -> dict:
    """{day: (Mkt-RF, SMB, HML, RMW, CMA) in decimals}."""
    def load():
        out = {}
        for r in _rows(archive, FF5_B):
            v = r.get("value") or {}
            try:
                out[v["day"]] = tuple(float(v[c]) / 100.0 for c in FF5_COLS)
            except (KeyError, TypeError, ValueError):
                continue
        return out
    return _cached(archive, ("ff5",), load)


def _vix(archive) -> dict:
    def load():
        out = {}
        for r in _rows(archive, VIX_B):
            v = r.get("value") or {}
            try:
                x = float(v.get("close"))
            except (TypeError, ValueError):
                continue
            if v.get("day") and x > 0:
                out[v["day"]] = x
        return out
    return _cached(archive, ("vix",), load)


# ================================================================================================ single stocks ==

def split_factor(splits: Sequence[tuple], day: str) -> float:
    """Shares today per share held on ``day``: the product of the split ratios with an ex-date after ``day``."""
    f = 1.0
    for ex, ratio in splits:
        if ex > day:
            f *= ratio
    return f


def _stock(archive, sym: str) -> Optional[dict]:
    """A Yahoo daily series {days, close (split-adjusted), adj (total return), vol, F (split factor per bar), splits,
    meta}; None when the bundle is not archived or has no usable bar."""
    def load():
        name = dh(sym)
        if not _has(archive, name):
            return None
        by = {}
        for r in _stream(archive, name):
            v = r.get("value") or {}
            try:
                c = float(v.get("close"))
                d = _bar_day(v["t"])
            except (TypeError, ValueError, KeyError):
                continue
            if not (c > 0 and math.isfinite(c)):
                continue
            try:
                a = float(v.get("adjclose"))
                a = a if a > 0 and math.isfinite(a) else float("nan")
            except (TypeError, ValueError):
                a = float("nan")
            try:
                vol = float(v.get("volume"))
                vol = vol if math.isfinite(vol) else float("nan")
            except (TypeError, ValueError):
                vol = float("nan")
            by[d] = (c, a, vol)
        if not by:
            return None
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 3)
        close, adj, vol = arr[:, 0], arr[:, 1].copy(), arr[:, 2]
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        splits = []
        if _has(archive, de(sym)):
            for r in _stream(archive, de(sym)):
                v = r.get("value") or {}
                if r.get("kind") != "split" and v.get("type") != "split":
                    continue
                try:
                    num, den = float(v.get("numerator")), float(v.get("denominator"))
                    ex = v.get("ex_date") or _bar_day(v["t"])
                except (TypeError, ValueError, KeyError):
                    continue
                if num > 0 and den > 0 and ex:
                    splits.append((ex, num / den))
        splits.sort()
        exs = [s[0] for s in splits]
        suffix = [1.0] * (len(splits) + 1)
        for k in range(len(splits) - 1, -1, -1):
            suffix[k] = suffix[k + 1] * splits[k][1]
        F = np.array([suffix[bisect.bisect_right(exs, d)] for d in days], float)
        return {"sym": sym, "days": days, "close": close, "adj": adj, "vol": vol, "F": F, "splits": splits,
                "meta": _meta(archive, name)}
    return _cached(archive, ("stock", sym), load)


def is_equity(st: Optional[dict]) -> bool:
    """A stock series: Yahoo's meta says EQUITY (a series without meta is not trusted to be a stock)."""
    return bool(st) and (st.get("meta") or {}).get("instrumentType") == "EQUITY"


class Panel:
    """Single stocks aligned on a session calendar. A: total-return price forward-filled after the first bar; C:
    split-adjusted close forward-filled; RAW: raw price (C x split factor, NaN where no bar); real: a bar on the day;
    first/last: first and last real bar index (-1 when none)."""

    def __init__(self, cal: Cal, series: Sequence[dict]):
        D, N = len(cal), len(series)
        self.cal, self.syms = cal, [s["sym"] for s in series]
        self.col = {s: j for j, s in enumerate(self.syms)}
        self.series = list(series)
        A = np.full((D, N), np.nan)
        C = np.full((D, N), np.nan)
        RAW = np.full((D, N), np.nan)
        V = np.full((D, N), np.nan)
        for j, s in enumerate(series):
            idx = np.array([cal.pos.get(d, -1) for d in s["days"]], int)
            ok = idx >= 0
            A[idx[ok], j] = s["adj"][ok]
            C[idx[ok], j] = s["close"][ok]
            RAW[idx[ok], j] = (s["close"] * s["F"])[ok]
            V[idx[ok], j] = s["vol"][ok]
        self.real = np.isfinite(A)
        anyb = self.real.any(axis=0)
        self.first = np.where(anyb, self.real.argmax(axis=0), -1)
        self.last = np.where(anyb, D - 1 - self.real[::-1].argmax(axis=0), -1)
        self.A, self.C = _ffill(A), _ffill(C)
        self.RAW, self.V = RAW, V

    def hold_return(self, cols: np.ndarray, e: int, x: int) -> tuple:
        """Total return from the close of e to the close of x (to the last bar when the series ends first) and whether
        it ended inside the hold."""
        cols = np.asarray(cols, int)
        if cols.size == 0:
            return np.zeros(0), np.zeros(0, bool)
        xe = np.minimum(x, self.last[cols])
        with np.errstate(invalid="ignore", divide="ignore"):
            r = self.A[xe, cols] / self.A[e, cols] - 1.0
        return r, self.last[cols] < x

    def mcap(self, j: int, i: int, shares: float, shares_end: str) -> float:
        """Market cap at session i: split-adjusted close x reported shares x the split factor after the shares' date."""
        s = self.series[j]
        return float(self.C[i, j]) * shares * split_factor(s["splits"], shares_end)


def _ffill(X: np.ndarray) -> np.ndarray:
    X = X.copy()
    D = X.shape[0]
    idx = np.where(np.isfinite(X), np.arange(D)[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    out = X[idx, np.arange(X.shape[1])[None, :]]
    seen = np.maximum.accumulate(np.isfinite(X), axis=0)
    out[~seen] = np.nan
    return out


def _equity_syms(archive) -> list:
    """Every archived Yahoo daily series whose meta says EQUITY (probed; none is required)."""
    def load():
        out = []
        for n in _entry_names(archive, "daily-history-"):
            if (_meta(archive, n) or {}).get("instrumentType") == "EQUITY":
                out.append(n[len("daily-history-"):])
        return out
    return _cached(archive, ("equity_syms",), load)


def _equity_panel(archive) -> Panel:
    def load():
        cal = _sessions(archive)
        ser = [s for s in (_stock(archive, y) for y in _equity_syms(archive)) if is_equity(s)]
        return Panel(cal, ser)
    return _cached(archive, ("equity_panel",), load)


# ================================================================================================ name matching ==

_STOP = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "COMPANIES", "LTD", "LIMITED", "PLC", "LLC", "LP",
         "L", "P", "HOLDINGS", "HOLDING", "HLDGS", "HLDG", "GROUP", "GRP", "THE", "CLASS", "CL", "COMMON", "COM", "STOCK",
         "SHARES", "SHS", "SH", "ORDINARY", "DE", "NV", "SA", "AG", "SE", "A", "B", "C", "N", "V", "AND", "OF",
         "ST", "CS", "ADR", "ADS", "DEPOSITARY", "REIT"}
_ABBR = {"INTL": "INTERNATIONAL", "INTERNATL": "INTERNATIONAL", "MGMT": "MANAGEMENT", "TECH": "TECHNOLOGIES",
         "TECHNOLOGY": "TECHNOLOGIES", "SYS": "SYSTEMS", "PHARM": "PHARMACEUTICALS", "FINL": "FINANCIAL",
         "BANCORPORATION": "BANCORP", "SVCS": "SERVICES", "COMMUNICATION": "COMMUNICATIONS"}
# a first word this common does not identify a company: the second word must agree too
_GENERIC = {"AMERICAN", "AMERICA", "AMERICAS", "FIRST", "UNITED", "GENERAL", "NATIONAL", "INTERNATIONAL", "SOUTHERN",
            "NORTHERN", "CENTRAL", "PACIFIC", "WESTERN", "EASTERN", "US", "U", "S", "CAPITAL", "BANK", "GLOBAL", "ADVANCED",
            "APPLIED", "NORTH", "SOUTH", "WEST", "EAST", "NEW", "CITY", "STANDARD", "CONTINENTAL", "ALLIED",
            "CONSOLIDATED", "DIGITAL", "ENERGY", "HEALTH", "HOME", "INTEGRATED", "PUBLIC", "ROYAL", "SECURITY",
            "SOUTHWEST", "STATE", "TEXAS", "UNION", "UNIVERSAL", "WORLD", "GOLDEN", "GREAT", "MID", "ATLANTIC"}


def name_tokens(s: str) -> list:
    s = (s or "").upper().replace("&", " AND ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b((?:[A-Z]\.){2,})", lambda g: g.group(1).replace(".", "") + " ", s)     # V.F. -> VF, J.B. -> JB
    toks = [_ABBR.get(t, t) for t in re.findall(r"[A-Z0-9]+", s)]
    return [t for t in toks if t not in _STOP]


def _tok_eq(x: str, y: str) -> bool:
    return x == y or (min(len(x), len(y)) >= 3 and (x.startswith(y) or y.startswith(x)))


def names_match(a: str, b: str) -> Optional[bool]:
    """Do two company names agree on their first significant word (and on the second when the first is generic,
    'American', 'First', ...)? A word may be a 3+ letter prefix of the other (FINRA truncates names). None when either
    name has no significant word."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return None
    if not _tok_eq(ta[0], tb[0]):
        return False
    if (ta[0] in _GENERIC or tb[0] in _GENERIC) and len(ta) > 1 and len(tb) > 1:
        return _tok_eq(ta[1], tb[1])
    return True


def names_ok(ref: str, names: Sequence[str]) -> Optional[bool]:
    """``ref`` against every name the instrument has carried (Yahoo's longName, the SEC conformed and former names of
    the ticker's current CIK): True when any agrees, False when every comparable one disagrees, None when none is
    comparable."""
    res = [names_match(ref, n) for n in names if n]
    if any(r is True for r in res):
        return True
    if any(r is False for r in res):
        return False
    return None


def _alias_names(archive, panel: "Panel") -> dict:
    """{column: [names]}: Yahoo's longName plus the SEC name and formerNames of the ticker's current CIK (renames such
    as Cliffs Natural Resources -> Cleveland-Cliffs keep their history; a reused ticker's new company does not carry the
    old name)."""
    def load():
        tick = _sec_tickers(archive) if _has(archive, SEC_TICK_B) else {}
        ciks = {tick[s][0] for s in panel.syms if s in tick}
        comp = _company_rows(archive, ciks) if ciks else {}
        out = {}
        for j, s in enumerate(panel.syms):
            nm = [(panel.series[j]["meta"] or {}).get("longName") or ""]
            if s in tick:
                c = tick[s][0]
                nm.append(tick[s][1])
                v = comp.get(c) or {}
                nm.append(v.get("name") or "")
                nm += [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
            out[j] = [x for x in nm if x]
        return out
    return _cached(archive, ("alias", id(panel)), load)


# ======================================================================================================= FINRA ==

def finra_name(d: str) -> str:
    return FINRA_PREFIX + d


def finra_expected(start: str, end: str) -> list:
    """Settlement dates (the fetcher's own calendar rule) whose publication falls in [start - 20 days, end]."""
    lo = (date.fromisoformat(start) - timedelta(days=40)).isoformat()
    return [d for d in finra_si_calendar("2017-12-29", end) if d >= lo]


def _finra(archive, d: str) -> dict:
    """{av (epoch of the latest available_at), rows: [(sym, name, cls, si, adv, chg_pct)]} of one settlement date's
    stock rows (streamed, not cached: the formations are)."""
    out, av = [], None
    for r in _stream(archive, finra_name(d)):
        v = r.get("value") or {}
        sym = (v.get("symbolCode") or "").strip().upper()
        if not sym:
            continue
        try:
            a = _ts(r["available_at"])
            av = a if av is None else max(av, a)
        except (KeyError, ValueError):
            pass
        nm, cls = v.get("issueName") or "", v.get("marketClassCode") or ""
        if not is_stock_row(cls, nm):
            continue
        out.append((sym, nm, cls, _num(v.get("currentShortPositionQuantity")), _num(v.get("averageDailyVolumeQuantity")),
                    _num(v.get("changePercent"))))
    return {"av": av, "rows": out}


def _num(x) -> float:
    try:
        f = float(x)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def is_stock_row(cls: str, name: str) -> bool:
    return cls in FINRA_COMPANY_CLASSES and not NOT_STOCK.search(name or "") and not FUND_SPONSOR.search(name or "")


def _finra_cands(sym: str) -> list:
    """Yahoo / SEC spellings of a FINRA symbol (class shares BRKB -> BRK-B)."""
    cands = [ysym(sym)]
    if len(sym) >= 3 and sym[-1] in "ABCK" and "-" not in sym and "." not in sym:
        cands.append(sym[:-1] + "-" + sym[-1])
    return cands


def match_symbol(panel: Panel, sym: str, issue: str, i: int, aliases: Optional[dict] = None) -> tuple:
    """(column or -1, why) of a FINRA row in the price panel at session i: the symbol (class shares BRKB -> BRK-B), a
    Yahoo EQUITY series with a bar at i, and the FINRA issue name agreeing with a name the instrument has carried."""
    for c in _finra_cands(sym):
        j = panel.col.get(c)
        if j is None:
            continue
        if not panel.real[i, j]:
            return -1, "no bar"
        names = (aliases or {}).get(j) or [(panel.series[j]["meta"] or {}).get("longName") or ""]
        if names_ok(issue, names) is False:
            return -1, "name"
        return j, "ok"
    return -1, "no series"


# ========================================================================================================= SEC ==

def sec_bucket(cik: int) -> str:
    return f"b{int(cik) // SEC_BUCKET:03d}"


def _sec_tickers(archive) -> dict:
    """{Yahoo-spelled ticker: (cik, name)} from the current SEC map (delisted tickers are absent)."""
    def load():
        out = {}
        for r in _rows(archive, SEC_TICK_B):
            v = r.get("value") or {}
            t = v.get("ticker")
            try:
                c = int(v.get("cik"))
            except (TypeError, ValueError):
                continue
            if t:
                out.setdefault(ysym(t), (c, v.get("name") or ""))
        return out
    return _cached(archive, ("sec_tickers",), load)


SHARE_TAGS = (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding"))
ANNUAL_TAGS = {
    "ni": ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "assets": ("Assets",),
    "ca": ("AssetsCurrent",),
    "cl": ("LiabilitiesCurrent",),
    "ltd": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "rev": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"),
    "gp": ("GrossProfit",),
    "cogs": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    "eq": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "pref": ("PreferredStockValue",),
    "iss": ("ProceedsFromIssuanceOfCommonStock",),
}
_ANNUAL_SET = {t for ts in ANNUAL_TAGS.values() for t in ts}
TENK_FORMS = ("10-K", "10-KT", "10-K405")


def _sec_facts(archive, ciks: frozenset) -> dict:
    """One pass over every archived sec-companyfacts bucket that holds a wanted CIK: {facts: {cik: [fact tuples]},
    filers: {year: set(cik)} (every CIK with a 10-K reporting Assets accepted in that year, priced or not), buckets
    present / absent}. Fact tuple: (taxonomy, tag, unit, start, end, val, accn, form, available_at epoch)."""
    def load():
        wanted_b = sorted({sec_bucket(c) for c in ciks})
        names = _entry_names(archive, FACTS_PREFIX)
        present = [FACTS_PREFIX + b for b in wanted_b if FACTS_PREFIX + b in names]
        absent = [FACTS_PREFIX + b for b in wanted_b if FACTS_PREFIX + b not in names]
        facts, filers = {}, {}
        for n in names:
            for r in _stream(archive, n):
                if r.get("kind") != "fact":
                    continue
                v = r.get("value") or {}
                try:
                    cik = int(v.get("cik"))
                except (TypeError, ValueError):
                    continue
                tag, tax, form = v.get("tag"), v.get("taxonomy"), v.get("form") or ""
                if tag == "Assets" and form in TENK_FORMS and r.get("available_at"):
                    filers.setdefault(r["available_at"][:4], set()).add(cik)
                if cik not in ciks:
                    continue
                if not ((tax, tag) in SHARE_TAGS or (tax == "us-gaap" and tag in _ANNUAL_SET)):
                    continue
                try:
                    val = float(v.get("val"))
                    av = _ts(r["available_at"])
                except (TypeError, ValueError, KeyError):
                    continue
                facts.setdefault(cik, []).append((tax, tag, v.get("unit"), v.get("start"), v.get("end"), val,
                                                  v.get("accn"), form, av))
        return {"facts": facts, "filers": filers, "present": present, "absent": absent, "names": names}
    return _cached(archive, ("sec_facts", ciks), load)


def shares_series(facts: Sequence[tuple]) -> list:
    """[(available_at epoch, as-of date, shares)] sorted by availability: per accession the dei cover values of its
    latest cover date summed across classes, else us-gaap CommonStockSharesOutstanding at its latest date."""
    by = {}
    for tax, tag, unit, start, end, val, accn, form, av in facts:
        if (tax, tag) not in SHARE_TAGS or not end or not (val > 0):
            continue
        k = 0 if tax == "dei" else 1
        by.setdefault(accn, {}).setdefault(k, {}).setdefault(end, []).append((val, av))
    out = []
    for accn, kinds in by.items():
        k = 0 if 0 in kinds else 1
        end = max(kinds[k])
        vals = kinds[k][end]
        tot = sum(v for v, _ in vals) if k == 0 else max(v for v, _ in vals)
        out.append((min(a for _, a in vals), end, tot))
    return sorted(out)


def shares_at(series: Sequence[tuple], ts: float, day: str) -> Optional[tuple]:
    """(shares, as-of date) known at ``ts`` and at most SHARES_MAX_AGE days old on ``day``."""
    k = bisect.bisect_right([s[0] for s in series], ts) - 1
    while k >= 0:
        av, end, sh = series[k]
        if (date.fromisoformat(day) - date.fromisoformat(end)).days <= SHARES_MAX_AGE:
            return sh, end
        return None
    return None


def _company_rows(archive, ciks: set) -> dict:
    """{cik: company profile} from the sec-submissions buckets holding them (probed)."""
    def load():
        names = set(_entry_names(archive, SUBS_PREFIX))
        out = {}
        for b in sorted({sec_bucket(c) for c in ciks}):
            n = SUBS_PREFIX + b
            if n not in names:
                continue
            for r in _stream(archive, n):
                if r.get("kind") != "company":
                    continue
                v = r.get("value") or {}
                try:
                    c = int(v.get("cik"))
                except (TypeError, ValueError):
                    continue
                if c in ciks:
                    out[c] = v
        return out
    return _cached(archive, ("companies", frozenset(ciks)), load)


# ================================================================================================== statistics ==

def nw_mean(x, lag: int) -> dict:
    """Mean with a Newey-West (Bartlett 1 - l/(L+1)) s.e.; p = one-sided P(H0: mean <= 0), p_lt for mean >= 0."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"est": None, "se": None, "t": None, "p": None, "p_lt": None, "lag": lag}
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 0.0) / n)
    t = float(x.mean()) / se if se > 0 else (math.inf if x.mean() > 0 else -math.inf)
    return {"est": float(x.mean()), "se": se, "t": t, "p": 1.0 - _N.cdf(t) if math.isfinite(t) else float(t < 0),
            "p_lt": _N.cdf(t) if math.isfinite(t) else float(t > 0), "lag": lag}


def nw_lag(n: int) -> int:
    return int(math.floor(4.0 * (max(n, 1) / 100.0) ** (2.0 / 9.0)))


def ols_nw(y, X, lag: int) -> dict:
    """OLS y = a + X b with Newey-West s.e. (Bartlett, ``lag``): intercept, its s.e. and t, slopes."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(y.size, -1)
    n, k = X.shape
    out = {"n": int(n), "alpha": None, "se": None, "t": None, "betas": None}
    if n < k + 4:
        return out
    Z = np.column_stack([np.ones(n), X])
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
    se = math.sqrt(max(float(V[0, 0]), 0.0))
    out.update(alpha=float(b[0]), se=se, t=float(b[0]) / se if se > 0 else None, betas=[float(v) for v in b[1:]])
    return out


def mean_ci(x, block: int, check_thr: float = 0.0) -> dict:
    """Studentized CBB of the mean over REPS seeds (escalated when the lower end cannot be resolved against
    ``check_thr``)."""
    x = np.asarray(x, float)
    fn = lambda seed: _stud(_mean_stat, [x], block, N_BOOT, seed)
    chk = lambda t: resolve((t.get("ci") or [None])[0], (t.get("ci_mc_se") or [0.0])[0], check_thr, "gt")[0]
    if x.size < 8:
        return {"est": float(x.mean()) if x.size else None, "ci": [None, None], "p": None, "n": int(x.size)}
    return mc_escalate(fn, chk, REPS, SEED, keys=("ci",))


def _stat_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """Vectorised Politis-Romano stationary bootstrap indices (circular), geometric blocks of mean ``mean_block``."""
    p = 1.0 / max(float(mean_block), 1.0)
    new = rng.random((k, n)) < p
    new[:, 0] = True
    starts = rng.integers(0, n, size=(k, n))
    pos = np.arange(n)
    bs = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
    s0 = np.take_along_axis(starts, bs, axis=1)
    return (s0 + (pos[None, :] - bs)) % n


def sharpe_boot(x, mean_block: float = 20.0, n_boot: Optional[int] = None, seed: int = SEED, ppy: int = 252,
                level: float = 0.95) -> dict:
    """Annualised Sharpe with its stationary-bootstrap percentile interval (two-sided ``level``) and the one-sided
    bootstrap p of H0: Sharpe <= 0."""
    x = np.asarray(x, float)
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    n = x.size
    out = {"est": None, "ci": [None, None], "p": None, "n": int(n), "block": mean_block}
    if n < 20 or not x.std(ddof=1) > 0:
        return out
    est = float(x.mean() / x.std(ddof=1) * math.sqrt(ppy))
    rng = np.random.default_rng(seed)
    srs = []
    k = max(1, min(n_boot, 2_000_000 // n))
    done = 0
    while done < n_boot:
        m = min(k, n_boot - done)
        X = x[_stat_idx(rng, n, mean_block, m)]
        sd = X.std(axis=1, ddof=1)
        srs.append(np.where(sd > 0, X.mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0) * math.sqrt(ppy))
        done += m
    s = np.concatenate(srs)
    a = (1.0 - level) / 2.0
    out.update(est=est, ci=[float(np.quantile(s, a)), float(np.quantile(s, 1.0 - a))],
               p=float((np.sum(s <= 0.0) + 1) / (s.size + 1)))
    return out


def tail_fractions(score: np.ndarray, elig: np.ndarray, k: int, high: bool) -> np.ndarray:
    """Membership fractions (summing to k) of the k highest (``high``) or lowest eligible scores; names tied at the
    boundary share its remaining slots equally, so no list order decides a tied name."""
    out = np.zeros(score.size)
    idx = np.flatnonzero(elig & np.isfinite(score))
    if k < 1 or idx.size < k:
        return out
    v = score[idx]
    o = np.argsort(-v if high else v, kind="stable")
    kth = v[o[k - 1]]
    strict = v > kth if high else v < kth
    tied = v == kth
    frac = np.zeros(idx.size)
    frac[strict] = 1.0
    frac[tied] = (k - strict.sum()) / tied.sum()
    out[idx] = frac
    return out


def _leg(frac: np.ndarray, r: np.ndarray, w: Optional[np.ndarray] = None) -> Optional[float]:
    wt = frac * (w if w is not None else 1.0)
    s = wt.sum()
    if not s > 0:
        return None
    return float((wt * np.nan_to_num(r)).sum() / s)


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _gate(rows: list, covered: bool, why: str, label: str = "universe not fully priced") -> list:
    """Criteria rows whose answers depend on unpriced names (or names without a market cap): None unless the universe is
    covered (the reason states the coverage once, in full)."""
    if covered:
        return rows
    return [(f"{name} [NOT JUDGED: {label}]", None, False) for name, _, _ in rows]


NOCAP_LABEL = "priced stocks without a usable market cap"


def _too_short(n: int, min_n: int, unit: str, what: str):
    v, why = _verdict([(f"n >= trial min_n ({n} of {min_n} {unit})", None)])
    return ({"too_short": True, "n": int(n), "min_n": int(min_n)}, int(n), v,
            f"{what}: only {n} {unit} can be formed from the archived data (the claim needs {min_n}); nothing is "
            f"computed — {why}")


# ================================================================== T-375 / T-393 FINRA formation builder ==

def _priced_ciks(archive, panel: Panel) -> frozenset:
    """CIKs (current SEC map) of the priced stocks: the only CIKs whose facts are kept in memory."""
    tick = _sec_tickers(archive) if _has(archive, SEC_TICK_B) else {}
    return frozenset(tick[s][0] for s in panel.syms if s in tick)


def finra_formations(archive, panel: Panel, dates: Sequence[str], need_mcap: bool = True) -> tuple:
    """One formation per archived settlement date: fill e = the first session closing after the publication
    (available_at), q = the session before (filters, weights), tau = e's 09:30 ET (shares known by then). Candidate names
    = every FINRA stock row; a candidate is priced when matched to a Yahoo EQUITY series with bars at q and e. Market cap
    per security: the issuer's SEC cover count (all classes summed) is split equally across its listed classes (the
    FINRA stock rows of the same CIK, priced or not), class cap = own price x that part; NaN when the issuer's priced
    classes trade more than CLASS_PRICE_RATIO apart or no usable shares are known. Returns (formations, coverage rows);
    cached per date list."""
    return _cached(archive, ("finra_forms", tuple(dates), need_mcap),
                   lambda: _finra_formations(archive, panel, dates, need_mcap))


def _finra_formations(archive, panel: Panel, dates: Sequence[str], need_mcap: bool) -> tuple:
    cal = panel.cal
    tick = _sec_tickers(archive) if need_mcap and _has(archive, SEC_TICK_B) else {}
    facts = _sec_facts(archive, _priced_ciks(archive, panel))["facts"] if need_mcap else {}
    aliases = _alias_names(archive, panel)
    sh_cache: dict = {}
    forms, cover = [], []
    for d in dates:
        if not _has(archive, finra_name(d)):
            continue
        f = _finra(archive, d)
        if f["av"] is None:
            continue
        e = cal.entry_after(f["av"])
        if e >= len(cal) or e < 1:
            continue
        q = e - 1
        tau = float(cal.open[e])
        cols, dtc, chg, price, adv, mc, names, mcik = [], [], [], [], [], [], [], []
        n_stock = n_priced = n_adv = n_adv_priced = 0
        why = {"no series": 0, "no bar": 0, "name": 0}
        matched = [match_symbol(panel, r[0], r[1], q, aliases) for r in f["rows"]]
        # listed classes per issuer: the SEC cover count covers every class, so each class gets an equal part of it
        n_cls: dict = {}
        if need_mcap:
            for (sym, nm, *_), (j, _w) in zip(f["rows"], matched):
                ck = tick.get(panel.syms[j]) if j >= 0 else next(
                    (tick[c] for c in _finra_cands(sym) if c in tick and names_match(nm, tick[c][1]) is not False), None)
                if ck:
                    n_cls[ck[0]] = n_cls.get(ck[0], 0) + 1
        for (sym, nm, cls, si, advq, cp), (j, w) in zip(f["rows"], matched):
            n_stock += 1
            big = advq >= 1e6
            n_adv += int(big)
            if j < 0 or not panel.real[e, j]:
                why[w if j < 0 else "no bar"] = why.get(w if j < 0 else "no bar", 0) + 1
                continue
            n_priced += 1
            n_adv_priced += int(big)
            px = float(panel.RAW[q, j])
            m, mk = float("nan"), None
            if need_mcap:
                ck = tick.get(panel.syms[j])
                if ck:
                    if ck[0] not in sh_cache:
                        sh_cache[ck[0]] = shares_series(facts.get(ck[0], ()))
                    sa = shares_at(sh_cache[ck[0]], tau, cal.days[q])
                    if sa:
                        m, mk = panel.mcap(j, q, sa[0], sa[1]) / max(1, n_cls.get(ck[0], 1)), ck[0]
            mcik.append(mk)
            cols.append(j)
            dtc.append(si / advq if advq > 0 else float("nan"))
            chg.append(cp)
            price.append(px)
            adv.append(advq * px if advq > 0 else 0.0)
            mc.append(m)
            names.append(sym)
        mc = np.array(mc, float)
        price_a = np.array(price, float)
        n_split = 0
        for ck in {c for c in mcik if c is not None and n_cls.get(c, 1) > 1}:
            ii = [k for k, c in enumerate(mcik) if c == ck]
            n_split += len(ii)
            p = price_a[ii]
            if p.max() > CLASS_PRICE_RATIO * p.min():
                mc[ii] = np.nan       # classes priced far apart (BRK-A / BRK-B): the summed cover count cannot be split
        forms.append({"settle": d, "label": cal.days[e], "e": e, "q": q, "cols": np.array(cols, int), "dtc": np.array(dtc, float),
                      "chg": np.array(chg, float), "price": price_a, "adv_usd": np.array(adv, float),
                      "mcap": mc, "syms": names, "n_split": n_split})
        cover.append({"settle": d, "fill": cal.days[e], "stocks": n_stock, "priced": n_priced,
                      "missing_share": 1.0 - n_priced / n_stock if n_stock else None, "adv1m": n_adv,
                      "adv1m_priced": n_adv_priced, "why": why})
    for k, f in enumerate(forms):
        f["e_next"] = forms[k + 1]["e"] if k + 1 < len(forms) else None
    return forms, cover


def _cover_summary(cover: list) -> dict:
    ms = [c["missing_share"] for c in cover if c["missing_share"] is not None]
    a1 = [1.0 - c["adv1m_priced"] / c["adv1m"] for c in cover if c["adv1m"]]
    why = {}
    for c in cover:
        for k, v in c["why"].items():
            why[k] = why.get(k, 0) + v
    return {"dates": len(cover), "missing_share_mean": float(np.mean(ms)) if ms else None,
            "missing_share_min": float(np.min(ms)) if ms else None, "missing_share_max": float(np.max(ms)) if ms else None,
            "stocks_mean": float(np.mean([c["stocks"] for c in cover])) if cover else None,
            "priced_mean": float(np.mean([c["priced"] for c in cover])) if cover else None,
            "missing_share_adv1m_mean": float(np.mean(a1)) if a1 else None, "unmatched": why}


# ================================================================================================ T-375 lending ==

T375_START, T375_END = "2020-05-01", "2026-09-30"
T375_MIN_N = 120
T375_FEE = 0.0083
T375_COST = 10e-4
T375_PRICE_MIN = 5.0
T375_ADV_MIN = 5e6
T375_BLOCK = 4
T375_DELIST = -0.30
T375_YEARS = tuple(range(2020, 2027))
T375_SQUEEZE = ("2021-01-01", "2021-03-31")
MONTH_DAYS = 30.4375


def t375_periods(panel: Panel, forms: Sequence[dict], cost: float = T375_COST, fee: float = T375_FEE,
                 hold: str = "month", sort: str = "dtc", delist: Optional[float] = None) -> dict:
    """Per formation: bottom-minus-top decile spread of the sort (``dtc``: days to cover; ``chg``: short-interest change)
    over the hold (``month``: one calendar month from the fill; ``next``: to the next formation's fill), equal- and
    value-weighted, net of ``cost`` per side on each leg's entry and exit, and x = net - fee (pro rata for ``next``).
    ``delist`` replaces the return of a name whose series ends inside the hold by (1 + r)(1 + delist) - 1."""
    cal = panel.cal
    out = {k: [] for k in ("label", "year", "gross_ew", "gross_vw", "net_ew", "net_vw", "x_ew", "x_vw", "n", "k",
                           "ended", "days")}
    for f in forms:
        e = f["e"]
        if hold == "month":
            tgt = _add_months(cal.days[e], 1)
            x = cal.on_or_before(tgt) if tgt <= cal.days[-1] else None
        else:
            x = f.get("e_next")
        if x is None or x <= e or x >= len(cal):
            continue
        cols = f["cols"]
        sc = f["dtc"] if sort == "dtc" else f["chg"]
        elig = (f["price"] > T375_PRICE_MIN) & (f["adv_usd"] > T375_ADV_MIN) & np.isfinite(sc)
        n = int(elig.sum())
        k = n // 10
        if k < 1:
            continue
        r, ended = panel.hold_return(cols, e, x)
        if delist is not None:
            r = np.where(ended & (panel.last[cols] < len(cal) - 1), (1.0 + r) * (1.0 + delist) - 1.0, r)
        bot = tail_fractions(sc, elig, k, high=False)
        top = tail_fractions(sc, elig, k, high=True)
        mc = np.where(np.isfinite(f["mcap"]) & (f["mcap"] > 0), f["mcap"], 0.0)
        gew = _leg(bot, r) - _leg(top, r)
        lb, lt = _leg(bot, r, mc), _leg(top, r, mc)
        gvw = (lb - lt) if (lb is not None and lt is not None) else float("nan")
        days = float(cal.ords[x] - cal.ords[e])
        hurdle = fee if hold == "month" else fee * days / MONTH_DAYS
        c4 = 4.0 * cost
        out["label"].append(cal.days[e])
        out["year"].append(int(cal.days[e][:4]))
        out["gross_ew"].append(gew)
        out["gross_vw"].append(gvw)
        out["net_ew"].append(gew - c4)
        out["net_vw"].append(gvw - c4)
        out["x_ew"].append(gew - c4 - hurdle)
        out["x_vw"].append(gvw - c4 - hurdle)
        out["n"].append(n)
        out["k"].append(k)
        out["ended"].append(int((ended & ((bot + top) > 0)).sum()))
        out["days"].append(days)
    for k in list(out):
        if k not in ("label",):
            out[k] = np.array(out[k], float)
    return out


def year_signs(x: np.ndarray, years: np.ndarray, want: Sequence[int]) -> dict:
    ok = np.isfinite(x)
    by = {y: float(x[ok & (years == y)].mean()) for y in want if np.any(ok & (years == y))}
    pos = sum(1 for v in by.values() if v > 0)
    return {"by_year": by, "positive": pos, "observed": len(by), "expected": len(want)}


def t375_judge(core: dict, fam: dict, covered: bool, why: str, n: int, min_n: int = T375_MIN_N,
               covered_vw: Optional[bool] = None) -> tuple:
    """Criteria rows (name, ok, decisive) and the mean tests. ``core``: t375_periods of the primary; ``fam``: {member:
    periods} of the 3-member DSR family (EW and VW x series). ``covered``: every FINRA stock priced (all criteria);
    ``covered_vw``: also every eligible stock has a usable market cap (the VW criteria; default = covered)."""
    rows, tests = [], {}
    wts = []                                   # the weighting of each row, for the gate
    lag = max(2, nw_lag(n))
    for w in ("ew", "vw"):
        x = core[f"x_{w}"]
        x = x[np.isfinite(x)]
        nw = nw_mean(x, lag)
        cb = mean_ci(x, T375_BLOCK)
        tests[w] = {"nw": nw, "cbb": {k: cb.get(k) for k in ("est", "ci", "ci_mc_se", "p", "p_mc_se", "p_lt", "block", "reps")},
                    "n": int(x.size), "mean_net": float(np.nanmean(core[f"net_{w}"])) if x.size else None,
                    "mean_gross": float(np.nanmean(core[f"gross_{w}"])) if x.size else None}
        p_cb, se_cb = cb.get("p"), cb.get("p_mc_se") or 0.0
        ok_cb = resolve(p_cb, se_cb, ALPHA, "lt")[0] if p_cb is not None else None
        r_nw = (f"Newey-West t {_s(nw['t'], 2)} (lag {lag}), p {_f(nw['p'], 4)}", None if nw["p"] is None else nw["p"] < ALPHA,
                nw["p_lt"] is not None and nw["p_lt"] < ALPHA)
        r_cb = (f"studentized CBB ({T375_BLOCK}-date blocks) p {_f(p_cb, 4)}", ok_cb,
                cb.get("p_lt") is not None and cb["p_lt"] < ALPHA)
        rows.append(all_constructions([r_nw, r_cb], f"{w.upper()} mean (bottom - top) net - 0.83%/month "
                                      f"{_pc(nw['est'], 3)} > 0 with p < 0.05"))
        wts.append(w)
    ys = {w: year_signs(core[f"x_{w}"], core["year"], T375_YEARS) for w in ("ew", "vw")}
    tests["years"] = ys
    for w in ("ew", "vw"):
        y = ys[w]
        miss = y["expected"] - y["observed"]
        rows.append((f"{w.upper()} same sign (x > 0) in >= 5 of 7 calendar years ({y['positive']} of {y['observed']} observed)",
                     y["positive"] >= 5 if miss == 0 else (True if y["positive"] >= 5 else None),
                     y["positive"] + miss < 5))
        wts.append(w)
    tests["dsr"] = {}
    for w in ("ew", "vw"):
        sh = [float(sharpe_ratio(v[np.isfinite(v)])) if np.isfinite(v).sum() > 2 else None for v in
              (fam[m][f"x_{w}"] for m in fam)]
        x = core[f"x_{w}"]
        d = family_dsr(x[np.isfinite(x)], sh, 3)
        tests["dsr"][w] = d
        rows.append(dsr_row(d, f"{w.upper()} DSR > 0.95 over the 3 declared trials"))
        wts.append(w)
    cov_vw = covered if covered_vw is None else (covered and covered_vw)
    out = []
    for w, r in zip(wts, rows):
        if not covered:
            out += _gate([r], False, why)
        elif w == "vw" and not cov_vw:
            out += _gate([r], False, why, NOCAP_LABEL)
        else:
            out.append(r)
    return out, tests


FINRA_ALL = ("2017-12-01", "2026-09-30")      # one formation set shared by T-375 and T-393 (each filters its window)


def _all_formations(archive, panel: Panel) -> tuple:
    return finra_formations(archive, panel, finra_expected(*FINRA_ALL), need_mcap=True)


def b6c_stockxs_lending_dtc_deciles(archive):
    """T-375."""
    dates = finra_expected(T375_START, T375_END)
    need = [SPY_B, SEC_TICK_B] + [finra_name(d) for d in dates]
    miss = _missing(archive, need)
    if miss:
        return miss
    panel = _equity_panel(archive)
    forms_all, cover_all = _all_formations(archive, panel)
    keep = [k for k, f in enumerate(forms_all) if T375_START <= f["label"] <= T375_END]
    forms = [forms_all[k] for k in keep]
    cover = [cover_all[k] for k in keep]
    core = t375_periods(panel, forms)
    n = len(core["label"])
    if n < 8:
        return _too_short(n, T375_MIN_N, "formation dates", "FINRA days-to-cover decile formations May 2020..Sep 2026")
    fam = {"dtc_1m": core, "dtc_to_next": t375_periods(panel, forms, hold="next"),
           "chg_1m": t375_periods(panel, forms, sort="chg")}
    cs = _cover_summary(cover)
    covered = cs["missing_share_max"] is not None and cs["missing_share_max"] <= 0.0
    why = (f"{_pc(cs['missing_share_mean'], 1)} of the point-in-time FINRA stock universe has no archived price (range "
           f"{_pc(cs['missing_share_min'], 1)}..{_pc(cs['missing_share_max'], 1)} over {cs['dates']} dates; "
           f"{_pc(cs['missing_share_adv1m_mean'], 1)} of the names trading >= 1m shares a day): Yahoo serves no delisted "
           "or non-archived names, so the decile breakpoints and both legs depend on the missing names")
    # value weights: an eligible stock without a usable class market cap leaves the VW criteria NOT JUDGED (never a
    # silent zero weight)
    nocap = [int(((f["price"] > T375_PRICE_MIN) & (f["adv_usd"] > T375_ADV_MIN)
                  & ~(np.isfinite(f["mcap"]) & (f["mcap"] > 0))).sum()) for f in forms]
    nsplit = [int(f.get("n_split", 0)) for f in forms]
    covered_vw = covered and max(nocap, default=0) == 0
    why_vw = (f"{_f(float(np.mean(nocap)) if nocap else None, 1)} eligible priced stocks per formation (max "
              f"{max(nocap, default=0)}) have no usable point-in-time market cap (no non-dimensional SEC cover shares within "
              f"15 months, or share classes trading more than {CLASS_PRICE_RATIO:g}x apart); "
              f"{_f(float(np.mean(nsplit)) if nsplit else None, 1)} priced share-class rows per formation split their "
              "issuer's cover count equally")
    rows, tests = t375_judge(core, fam, covered, why, n, covered_vw=covered_vw)
    v, expl = _decide(rows, n, T375_MIN_N, "formation dates")
    sq = np.array([not (T375_SQUEEZE[0] <= l <= T375_SQUEEZE[1]) for l in core["label"]], bool)
    ex_sq = {w: float(np.nanmean(core[f"x_{w}"][sq])) for w in ("ew", "vw")}
    dl = t375_periods(panel, forms, delist=T375_DELIST)
    t = tests
    head = ("SURVIVOR-ONLY DIAGNOSTIC (not the claim's universe)" if not covered else
            "the point-in-time FINRA stock universe is fully priced")
    tail = ("Every return criterion is therefore NOT JUDGED (rule 9: a data limit is inconclusive)" if not covered else
            "The EW criteria are judged; the VW criteria are NOT JUDGED (rule 9: a stock without a market cap is never "
            "given a silent zero weight)" if not covered_vw else "every criterion is judged")
    reason = (f"{head}: {n} FINRA formations with fills "
              f"{core['label'][0]}..{core['label'][-1]} (fill = first close after the end of the 8th NYSE business day after "
              f"settlement), stocks priced > $5 with ADV > $5m at the previous close among the {_f(cs['priced_mean'], 0)} "
              f"FINRA stocks per date that have Yahoo prices (of {_f(cs['stocks_mean'], 0)}), mean "
              f"{_f(float(np.mean(core['n'])), 0)} eligible, deciles of DTC = short interest / ADV, one-month hold, 10 bp per "
              f"side per leg: EW (bottom - top) gross {_pc(t['ew']['mean_gross'], 3)}, net {_pc(t['ew']['mean_net'], 3)} per "
              f"month, x = net - 0.83% {_pc(t['ew']['nw']['est'], 3)} (NW t {_s(t['ew']['nw']['t'], 2)}, CBB "
              f"{_ci(t['ew']['cbb'].get('ci'), 3, 100, '%')}); VW gross {_pc(t['vw']['mean_gross'], 3)}, x "
              f"{_pc(t['vw']['nw']['est'], 3)} (NW t {_s(t['vw']['nw']['t'], 2)}); positive years EW "
              f"{t['years']['ew']['positive']}/{t['years']['ew']['observed']}, VW {t['years']['vw']['positive']}/"
              f"{t['years']['vw']['observed']}; DSR (3 trials) EW {_f(t['dsr']['ew'].get('dsr'))}, VW "
              f"{_f(t['dsr']['vw'].get('dsr'))}; without the Jan-Mar 2021 fills x EW {_pc(ex_sq['ew'], 3)}, VW "
              f"{_pc(ex_sq['vw'], 3)}; -30% delisting sensitivity x EW {_pc(float(np.nanmean(dl['x_ew'])), 3)}. "
              f"Universe coverage: {why}. Value weights: {why_vw}. {tail} — {expl}")
    stat = {"label": "SURVIVOR-ONLY" if not covered else "FULL UNIVERSE", "n_formations": n, "fills": [core["label"][0], core["label"][-1]], "tests": tests,
            "coverage": cs, "covered": covered, "covered_vw": covered_vw,
            "vw_caps": {"nocap_eligible_mean": float(np.mean(nocap)) if nocap else None, "nocap_eligible_max": max(nocap, default=0),
                        "split_class_rows_mean": float(np.mean(nsplit)) if nsplit else None}, "ex_squeeze_x": ex_sq,
            "delist30_x_ew": float(np.nanmean(dl["x_ew"])), "family": {m: {"mean_x_ew": float(np.nanmean(v["x_ew"])),
                                                                             "mean_x_vw": float(np.nanmean(v["x_vw"])),
                                                                             "n": len(v["label"])} for m, v in fam.items()},
            "mean_eligible": float(np.mean(core["n"])), "criteria": [(r[0], r[1]) for r in rows]}
    return _out(stat, n, v, reason)


# ================================================================================================ T-393 DTC L/S ==

T393_START, T393_END = "2017-12-01", "2026-09-30"
T393_MIN_N = 150
T393_COST = 5e-4
T393_BORROW = 0.01
T393_BORROW_HI = 0.03
T393_TOP = 1000
T393_DTC_MAX = 10.0
T393_PRICE_MIN = 5.0
T393_BLOCK = 6
T393_LAG = 6
T393_SQUEEZE = ("2021-01-01", "2021-03-31")


def t393_book(panel: Panel, forms: Sequence[dict], cost: float = T393_COST, borrow: float = T393_BORROW,
              borrow_hi: float = T393_BORROW_HI, top_n: int = T393_TOP) -> dict:
    """Dollar-neutral equal-weight book: long the bottom and short the top DTC decile of the top_n stocks by market cap
    (price >= $5, DTC <= 10), rebalanced at each formation's fill and held to the next one; drift-adjusted turnover at
    ``cost`` per side (the final exit charged in the last period); borrow on the short leg pro rata over calendar days
    (``borrow_hi`` for DTC in (5, 10])."""
    cal = panel.cal
    out = {k: [] for k in ("label", "e", "x", "gross", "net", "cost", "borrow", "turnover", "n", "k", "ended")}
    pL, pS = {}, {}
    for kf, f in enumerate(forms):
        x = f.get("e_next")
        if x is None or x <= f["e"]:
            continue
        e, cols = f["e"], f["cols"]
        elig = (f["price"] >= T393_PRICE_MIN) & np.isfinite(f["mcap"]) & (f["mcap"] > 0) & np.isfinite(f["dtc"])
        idx = np.flatnonzero(elig)
        if idx.size > top_n:
            o = idx[np.argsort(-f["mcap"][idx], kind="stable")]
            keep = np.zeros(cols.size, bool)
            keep[o[:top_n]] = True
            elig &= keep
        elig &= f["dtc"] <= T393_DTC_MAX
        n = int(elig.sum())
        k = n // 10
        if k < 1:
            continue
        bot = tail_fractions(f["dtc"], elig, k, high=False) / k
        top = tail_fractions(f["dtc"], elig, k, high=True) / k
        r, ended = panel.hold_return(cols, e, x)
        r = np.nan_to_num(r)
        wL = {int(c): float(w) for c, w in zip(cols, bot) if w > 0}
        wS = {int(c): float(w) for c, w in zip(cols, top) if w > 0}
        rc = {int(c): float(v) for c, v in zip(cols, r)}
        to = sum(abs(wL.get(c, 0.0) - pL.get(c, 0.0)) for c in set(wL) | set(pL))
        to += sum(abs(wS.get(c, 0.0) - pS.get(c, 0.0)) for c in set(wS) | set(pS))
        rL = sum(w * rc[c] for c, w in wL.items())
        rS = sum(w * rc[c] for c, w in wS.items())
        days = float(cal.ords[x] - cal.ords[e])
        dtcs = {int(c): float(v) for c, v in zip(cols, f["dtc"])}
        bor = sum(w * (borrow_hi if dtcs[c] > 5.0 else borrow) for c, w in wS.items()) * days / 365.0
        pL = {c: w * (1.0 + rc[c]) / (1.0 + rL) for c, w in wL.items()} if abs(1.0 + rL) > 1e-12 else {}
        pS = {c: w * (1.0 + rc[c]) / (1.0 + rS) for c, w in wS.items()} if abs(1.0 + rS) > 1e-12 else {}
        c = cost * to
        out["label"].append(cal.days[e])
        out["e"].append(e)
        out["x"].append(x)
        out["gross"].append(rL - rS)
        out["cost"].append(c)
        out["borrow"].append(bor)
        out["net"].append(rL - rS - c - bor)
        out["turnover"].append(to)
        out["n"].append(n)
        out["k"].append(k)
        out["ended"].append(int(sum(1 for cc, en in zip(cols, ended) if en and (int(cc) in wL or int(cc) in wS))))
    if out["net"]:
        last_exit = cost * (sum(pL.values()) + sum(pS.values()))
        out["net"][-1] -= last_exit
        out["cost"][-1] += last_exit
    for k in list(out):
        if k != "label":
            out[k] = np.array(out[k], float)
    out["e_days"] = [cal.days[int(i)] for i in out["e"]]
    out["x_days"] = [cal.days[int(i)] for i in out["x"]]
    return out


def period_factors(cal: Cal, ff: dict, e: np.ndarray, x: np.ndarray) -> np.ndarray:
    """FF5 factor sums over the sessions after each e through x (NaN when any session lacks a factor row)."""
    out = np.full((len(e), len(FF5_COLS)), np.nan)
    for k, (a, b) in enumerate(zip(e.astype(int), x.astype(int))):
        rows = [ff.get(cal.days[i]) for i in range(a + 1, b + 1)]
        if rows and all(r is not None for r in rows):
            out[k] = np.sum(np.array(rows, float), axis=0)
    return out


def t393_judge(book: dict, F: np.ndarray, covered: bool, why: str, n: int, min_n: int = T393_MIN_N,
               label: str = "universe not fully priced") -> tuple:
    net = book["net"]
    ci = mean_ci(net, T393_BLOCK)
    sq = np.array([not (ed <= T393_SQUEEZE[1] and xd >= T393_SQUEEZE[0]) for ed, xd in zip(book["e_days"], book["x_days"])], bool)
    ci_x = mean_ci(net[sq], T393_BLOCK)
    ok = np.all(np.isfinite(F), axis=1)
    reg = ols_nw(net[ok], F[ok], T393_LAG)
    rows = [_ci_crit(ci, "gt", 0.0, f"lower 95% bound of the mean net long-short return per release period > 0 "
                     f"(mean {_pc(ci.get('est'), 3)})", lambda v: _pc(v, 3)),
            (f"FF5 alpha t >= 2 (alpha {_pc(reg['alpha'], 3)} per period, t {_s(reg['t'], 2)}, NW lag {T393_LAG}, "
             f"{reg['n']} periods with factors)", None if reg["t"] is None else reg["t"] >= 2.0,
             reg["t"] is not None and reg["t"] <= -2.0),
            _ci_crit(ci_x, "gt", 0.0, f"holds without the Jan-Mar 2021 squeeze ({int(sq.sum())} periods; mean "
                     f"{_pc(ci_x.get('est'), 3)})", lambda v: _pc(v, 3))]
    tests = {"mean": {k: ci.get(k) for k in ("est", "ci", "ci_mc_se", "p", "block", "reps")},
             "ex_squeeze": {k: ci_x.get(k) for k in ("est", "ci", "ci_mc_se", "p", "block", "reps")}, "alpha": reg,
             "hit_rate": float(np.mean(net > 0)) if net.size else None}
    return _gate(rows, covered, why, label), tests


def b6c_stockxs_short_interest_dtc(archive):
    """T-393."""
    dates = finra_expected(T393_START, T393_END)
    need = [SPY_B, SEC_TICK_B, FF5_B] + [finra_name(d) for d in dates]
    miss = _missing(archive, need)
    if miss:
        return miss
    panel = _equity_panel(archive)
    forms_all, cover_all = _all_formations(archive, panel)
    keep = [k for k, f in enumerate(forms_all) if T393_START <= f["label"] <= T393_END]
    # the last kept formation is held to the next fill (which may fall after the window end)
    forms = [forms_all[k] for k in keep]
    cover = [cover_all[k] for k in keep]
    book = t393_book(panel, forms)
    n = len(book["label"])
    if n < 8:
        return _too_short(n, T393_MIN_N, "release dates", "FINRA release periods 2017-12..2026-09")
    cal = panel.cal
    F = period_factors(cal, _ff5(archive), book["e"], book["x"])
    cs = _cover_summary(cover)
    n_mc, nocap = [], []
    for f in forms:
        hasp = f["price"] >= T393_PRICE_MIN
        ok = hasp & np.isfinite(f["mcap"]) & (f["mcap"] > 0)
        n_mc.append(int(ok.sum()))
        nocap.append(int((hasp & ~ok).sum()))
    bound = max(0.0, 1.0 - max(n_mc) / T393_TOP) if n_mc else None
    # the ranking needs every stock's market cap: a priced stock without a usable class cap is uncovered, never dropped
    priced_all = cs["missing_share_max"] is not None and cs["missing_share_max"] <= 0.0
    covered = priced_all and max(nocap, default=0) == 0
    why = (f"the top-1000 ranking needs the market cap of every US stock, but {_pc(cs['missing_share_mean'], 1)} of the "
           f"FINRA stock universe has no archived price and {_f(float(np.mean(nocap)) if nocap else None, 1)} priced stocks "
           f">= $5 per date (max {max(nocap, default=0)}) have no usable point-in-time market cap (no non-dimensional SEC "
           f"cover shares within 15 months, or share classes trading more than {CLASS_PRICE_RATIO:g}x apart; an issuer's "
           f"cover count is split equally across its listed classes). At most {max(n_mc) if n_mc else 0} stocks per date "
           f"have a price and a market cap, so at least {_pc(bound, 1)} of every date's top 1000 is unknown: the universe, "
           "the deciles and both legs depend on the missing names")
    rows, tests = t393_judge(book, F, covered, why, n, label="universe not fully priced" if not priced_all else NOCAP_LABEL)
    v, expl = _decide(rows, n, T393_MIN_N, "release dates")
    alt = {}
    for nm, b_hi in (("borrow_hi_1pct", T393_BORROW), ("borrow_hi_10pct", 0.10)):
        bb = t393_book(panel, forms, borrow_hi=b_hi)
        alt[nm] = float(np.mean(bb["net"])) if len(bb["net"]) else None
    t = tests
    head = ("SURVIVOR-ONLY DIAGNOSTIC (not the claim's universe)" if not priced_all else
            "DIAGNOSTIC WITH INCOMPLETE MARKET CAPS (the FINRA stock universe is fully priced)" if not covered else
            "the point-in-time FINRA stock universe is fully priced with market caps")
    tail = "Every criterion is therefore NOT JUDGED (rule 9)" if not covered else "every criterion is judged"
    reason = (f"{head}: {n} release periods with fills "
              f"{book['label'][0]}..{book['label'][-1]} (first close after publication, held to the next fill), the largest "
              f"{T393_TOP} priced stocks with point-in-time SEC shares (mean {_f(float(np.mean(n_mc)), 0)} available, so the "
              f"'top 1000' is every priced stock), price >= $5, DTC <= 10, mean {_f(float(np.mean(book['n'])), 0)} names: "
              f"bottom-minus-top DTC decile gross {_pc(float(np.mean(book['gross'])), 3)}, after 5 bp per side "
              f"({_pc(float(np.mean(book['cost'])), 3)}) and borrow ({_pc(float(np.mean(book['borrow'])), 3)}) net "
              f"{_pc(t['mean']['est'], 3)} per period ({_ci(t['mean'].get('ci'), 3, 100, '%')}, studentized CBB, 6-period "
              f"blocks), hit rate {_f(t['hit_rate'], 2)}; FF5 alpha {_pc(t['alpha']['alpha'], 3)} t {_s(t['alpha']['t'], 2)}; "
              f"without Jan-Mar 2021 {_pc(t['ex_squeeze']['est'], 3)} ({_ci(t['ex_squeeze'].get('ci'), 3, 100, '%')}); "
              f"DTC 5-10 borrow at 1%/yr {_pc(alt['borrow_hi_1pct'], 3)}, at 10%/yr {_pc(alt['borrow_hi_10pct'], 3)}. "
              f"Universe coverage: {why}. {tail} — {expl}")
    stat = {"label": "SURVIVOR-ONLY" if not priced_all else "INCOMPLETE CAPS" if not covered else "FULL UNIVERSE", "n_periods": n, "fills": [book["label"][0], book["label"][-1]], "tests": tests,
            "coverage": cs, "covered": covered, "top1000_unpriced_lower_bound": bound,
            "nocap_priced_mean": float(np.mean(nocap)) if nocap else None, "nocap_priced_max": max(nocap, default=0),
            "names_mean": float(np.mean(book["n"])),
            "gross_mean": float(np.mean(book["gross"])), "cost_mean": float(np.mean(book["cost"])),
            "borrow_mean": float(np.mean(book["borrow"])), "borrow_sensitivity": alt,
            "criteria": [(r[0], r[1]) for r in rows]}
    return _out(stat, n, v, reason)


# ============================================================================================== T-451 F-score ==

T451_START, T451_END = "2011-01", "2026-09"
T451_MIN_N = 150
T451_COSTS = (10e-4, 20e-4)
T451_BLOCK = 12
T451_LAG = 12
T451_PRICE_MIN = 5.0
T451_Q = 0.8


def fscore(cur: dict, prev: dict, prev2_assets: Optional[float]) -> Optional[dict]:
    """Piotroski's nine binary signals from fiscal year t (``cur``), t-1 (``prev``) and the t-2 total assets. Each dict:
    ni, cfo, assets, ltd, ca, cl, rev, gp (cur also iss: equity issued, bool). None when any signal is not computable."""
    try:
        a0, a1, a2 = cur["assets"], prev["assets"], prev2_assets
        if not (a0 and a1 and a2 and a0 > 0 and a1 > 0 and a2 > 0):
            return None
        roa, roa1 = cur["ni"] / a1, prev["ni"] / a2
        cfo = cur["cfo"] / a1
        lev = cur["ltd"] / ((a0 + a1) / 2.0)
        lev1 = prev["ltd"] / ((a1 + a2) / 2.0)
        if not (cur["cl"] > 0 and prev["cl"] > 0 and cur["rev"] > 0 and prev["rev"] > 0):
            return None
        cr, cr1 = cur["ca"] / cur["cl"], prev["ca"] / prev["cl"]
        gm, gm1 = cur["gp"] / cur["rev"], prev["gp"] / prev["rev"]
        tu, tu1 = cur["rev"] / a1, prev["rev"] / a2
    except (KeyError, TypeError, ZeroDivisionError):
        return None
    vals = [roa, roa1, cfo, lev, lev1, cr, cr1, gm, gm1, tu, tu1]
    if any(v is None or not math.isfinite(v) for v in vals):
        return None
    sig = {"roa": roa > 0, "cfo": cfo > 0, "droa": roa > roa1, "accrual": cfo > roa, "dlever": lev < lev1,
           "dliquid": cr > cr1, "eq_offer": not bool(cur.get("iss")), "dmargin": gm > gm1, "dturn": tu > tu1}
    return {"score": int(sum(sig.values())), "signals": sig}


def _pick(f: dict, tags: Sequence[str], end: date, dur: bool) -> Optional[float]:
    """The first tag with a value for the period ending within 10 days of ``end`` (duration facts: 330-400 days)."""
    for t in tags:
        for (start, e, val) in f.get(t, ()):
            de_ = abs((date.fromisoformat(e) - end).days)
            if de_ > 10:
                continue
            if dur:
                if not start:
                    continue
                ln = (date.fromisoformat(e) - date.fromisoformat(start)).days
                if not 330 <= ln <= 400:
                    continue
            elif start:
                continue
            return val
    return None


def tenk_events(facts: Sequence[tuple]) -> list:
    """Each 10-K accession of one CIK: {accn, av, E, fscore, book, shares, shares_end} from the accession's own facts
    (years t, t-1) and the t-2 assets of earlier annual accessions (known before)."""
    by = {}
    for tax, tag, unit, start, end, val, accn, form, av in facts:
        if tax != "us-gaap" or unit != "USD" or not end or not accn:
            continue
        g = by.setdefault(accn, {"form": form, "av": av, "f": {}})
        g["av"] = min(g["av"], av)
        g["f"].setdefault(tag, []).append((start, end, val))
    shares = {}
    for tax, tag, unit, start, end, val, accn, form, av in facts:
        if (tax, tag) == SHARE_TAGS[0] and end and val > 0:
            shares.setdefault(accn, {}).setdefault(end, 0.0)
            shares[accn][end] += val
    assets_hist = []                      # (av, end, val) of annual accessions
    for accn, g in by.items():
        for (start, e, val) in g["f"].get("Assets", ()):
            if not start and g["form"] in TENK_FORMS:
                assets_hist.append((g["av"], e, val))
    out = []
    for accn, g in sorted(by.items(), key=lambda kv: kv[1]["av"]):
        if g["form"] not in TENK_FORMS:
            continue
        ends = sorted({e for (s, e, v) in g["f"].get("Assets", ()) if not s})
        if not ends:
            continue
        E = date.fromisoformat(ends[-1])
        E1s = [date.fromisoformat(e) for e in ends if 300 <= (E - date.fromisoformat(e)).days <= 430]
        if not E1s:
            continue
        E1 = max(E1s)
        a2 = None
        for av2, e2, v2 in sorted(assets_hist):
            if av2 < g["av"] and 300 <= (E1 - date.fromisoformat(e2)).days <= 430:
                a2 = v2                    # the latest earlier filing that reported the t-2 year-end
        yrs = {}
        for key, end in (("cur", E), ("prev", E1)):
            d = {}
            for c, tags in ANNUAL_TAGS.items():
                dur = c in ("ni", "cfo", "rev", "gp", "cogs", "iss")
                d[c] = _pick(g["f"], tags, end, dur)
            if d["gp"] is None and d["rev"] is not None and d["cogs"] is not None:
                d["gp"] = d["rev"] - d["cogs"]
            if d["ltd"] is None:
                d["ltd"] = 0.0
            yrs[key] = d
        cur, prev = yrs["cur"], yrs["prev"]
        cur["iss"] = (cur.get("iss") or 0.0) > 0
        fs = fscore(cur, prev, a2) if all(cur.get(k) is not None for k in ("ni", "cfo", "assets", "ca", "cl", "rev", "gp")) \
            and all(prev.get(k) is not None for k in ("ni", "assets", "ca", "cl", "rev", "gp")) else None
        book = None
        if cur.get("eq") is not None:
            book = cur["eq"] - (cur.get("pref") or 0.0)
        sh = shares.get(accn) or {}
        se = max(sh) if sh else None
        out.append({"accn": accn, "av": g["av"], "E": E.isoformat(), "fscore": fs, "book": book,
                    "shares": sh[se] if se else None, "shares_end": se})
    return out


def calendar_ls(panel: Panel, positions: Sequence[tuple], months: Sequence[str], cost: float) -> dict:
    """Calendar-time equal-weight legs. positions: (col, e, x, leg) with leg +1 long / -1 short, held over the sessions
    e+1..x; cost per side is charged on the first held session (entry) and on x (exit), except where the same firm
    continues in the same leg. Monthly leg returns compound the daily ones; a month is observed when both legs hold a
    name on every session. ``long`` is the long position's return net of its costs; ``short`` is the shorted stocks'
    return plus the short position's costs (what the short loses), so ls = long - short pays the costs of both legs.
    Returns {months, ls, long, short, long_gross, short_gross (the legs' stock returns before costs), n_long, n_short}."""
    cal = panel.cal
    D, N = panel.A.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        R = panel.A[1:] / panel.A[:-1] - 1.0
    R = np.vstack([np.zeros((1, N)), np.nan_to_num(R)])
    M = {1: np.zeros((D, N)), -1: np.zeros((D, N))}
    Cst = {1: np.zeros((D, N)), -1: np.zeros((D, N))}
    pos = sorted(positions, key=lambda p: (p[0], p[1]))
    for k, (j, e, x, leg) in enumerate(pos):
        if x <= e:
            continue
        M[leg][e + 1:x + 1, j] = 1.0
        prev_same = k > 0 and pos[k - 1][0] == j and pos[k - 1][3] == leg and pos[k - 1][2] == e
        next_same = k + 1 < len(pos) and pos[k + 1][0] == j and pos[k + 1][3] == leg and pos[k + 1][1] == x
        if not prev_same:
            Cst[leg][e + 1, j] += cost
        if not next_same:
            Cst[leg][x, j] += cost
    out = {"months": [], "ls": [], "long": [], "short": [], "long_gross": [], "short_gross": [], "n_long": [],
           "n_short": []}
    mi = {}
    for i, d in enumerate(cal.days):
        mi.setdefault(d[:7], []).append(i)
    for m in months:
        ii = mi.get(m)
        if not ii:
            continue
        ii = np.array(ii, int)
        nl, ns = M[1][ii].sum(axis=1), M[-1][ii].sum(axis=1)
        if not (np.all(nl > 0) and np.all(ns > 0)):
            continue
        rl = (M[1][ii] * (R[ii] - Cst[1][ii])).sum(axis=1) / nl
        rs = (M[-1][ii] * (R[ii] + Cst[-1][ii])).sum(axis=1) / ns      # a short pays its costs too: they raise S
        L, S = float(np.prod(1.0 + rl) - 1.0), float(np.prod(1.0 + rs) - 1.0)
        out["months"].append(m)
        out["long"].append(L)
        out["short"].append(S)
        out["ls"].append(L - S)
        out["long_gross"].append(float(np.prod(1.0 + (M[1][ii] * R[ii]).sum(axis=1) / nl) - 1.0))
        out["short_gross"].append(float(np.prod(1.0 + (M[-1][ii] * R[ii]).sum(axis=1) / ns) - 1.0))
        out["n_long"].append(float(nl.mean()))
        out["n_short"].append(float(ns.mean()))
    for k in ("ls", "long", "short", "long_gross", "short_gross", "n_long", "n_short"):
        out[k] = np.array(out[k], float)
    return out


def month_factors(cal: Cal, ff: dict, months: Sequence[str]) -> np.ndarray:
    out = np.full((len(months), len(FF5_COLS)), np.nan)
    by = {}
    for d in cal.days:
        by.setdefault(d[:7], []).append(d)
    for k, m in enumerate(months):
        rows = [ff.get(d) for d in by.get(m, [])]
        if rows and all(r is not None for r in rows):
            out[k] = np.prod(1.0 + np.array(rows, float), axis=0) - 1.0
    return out


def _months(a: str, b: str) -> list:
    out, y, m = [], int(a[:4]), int(a[5:7])
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def t451_positions(panel: Panel, events: dict, colmap: dict, shares: dict) -> tuple:
    """Positions (col, e, x, leg) from 10-K events {cik: [event]}: entry at the first close after acceptance, price >= $5
    at the previous close, B/M at or above the previous month-end's 80th percentile of the priced filers' B/M; long F
    8-9, short F 0-2; hold 12 months, cut short by the firm's next 10-K. Also the month-end breakpoints."""
    cal = panel.cal
    me = {}
    for i, d in enumerate(cal.days):
        me[d[:7]] = i
    me_idx = sorted(me.values())
    evs = {c: sorted(v, key=lambda e: e["av"]) for c, v in events.items()}
    avs = {c: [e["av"] for e in lst] for c, lst in evs.items()}
    bps = {}
    for i in me_idx:
        ts = float(cal.close[i])
        bms = []
        for c, lst in evs.items():
            j = colmap.get(c)
            if j is None or not panel.real[i, j]:
                continue
            k = bisect.bisect_right(avs[c], ts) - 1
            if k < 0:
                continue
            ev = lst[k]
            if ts - ev["av"] > 400 * 86400 or not ev["book"] or ev["book"] <= 0:
                continue
            if not panel.RAW[i, j] >= T451_PRICE_MIN:
                continue
            sa = shares_at(shares.get(c, ()), ts, cal.days[i])
            if not sa:
                continue
            mc = panel.mcap(j, i, sa[0], sa[1])
            if mc > 0:
                bms.append(ev["book"] / mc)
        if len(bms) >= 5:
            bps[i] = float(np.quantile(bms, T451_Q))
    bp_keys = sorted(bps)
    positions, info = [], {"events": 0, "fscored": 0, "entered": 0, "value": 0, "long": 0, "short": 0}
    for c, lst in evs.items():
        j = colmap.get(c)
        if j is None:
            continue
        ents = []
        for ev in lst:
            info["events"] += 1
            if ev["fscore"] is None or not ev["book"] or ev["book"] <= 0:
                continue
            info["fscored"] += 1
            e = cal.entry_after(ev["av"])
            if e >= len(cal) or e < 1 or not panel.real[e, j] or not panel.real[e - 1, j]:
                continue
            q = e - 1
            if not panel.RAW[q, j] >= T451_PRICE_MIN:
                continue
            sa = shares_at(shares.get(c, ()), ev["av"], cal.days[q])
            if not sa:
                continue
            mc = panel.mcap(j, q, sa[0], sa[1])
            kb = bisect.bisect_left(bp_keys, e) - 1
            if not mc > 0 or kb < 0 or (cal.ords[e] - cal.ords[bp_keys[kb]]) > 45:
                continue
            info["entered"] += 1
            ents.append((e, ev, ev["book"] / mc >= bps[bp_keys[kb]]))
        for k, (e, ev, val) in enumerate(ents):
            x = cal.on_or_before(_add_months(cal.days[e], 12))
            if k + 1 < len(ents):
                x = min(x, ents[k + 1][0])
            x = min(x, int(panel.last[j]))
            if not val or x <= e:
                continue
            info["value"] += 1
            sc = ev["fscore"]["score"]
            if sc >= 8:
                positions.append((j, e, x, 1))
                info["long"] += 1
            elif sc <= 2:
                positions.append((j, e, x, -1))
                info["short"] += 1
    return positions, info, bps


def t451_judge(runs: dict, Fm: dict, covered: bool, why: str, n: int, min_n: int = T451_MIN_N) -> tuple:
    """runs: {cost: calendar_ls}; Fm: {cost: month factor matrix}. Both cost ends must pass (rule 11 spirit)."""
    ci_rows, al_rows, tests = [], [], {}
    for c, r in runs.items():
        ci = mean_ci(r["ls"], T451_BLOCK)
        ok = np.all(np.isfinite(Fm[c]), axis=1)
        reg = ols_nw(r["ls"][ok], Fm[c][ok], T451_LAG)
        tests[f"{c * 1e4:.0f}bp"] = {"mean": {k: ci.get(k) for k in ("est", "ci", "ci_mc_se", "p", "block", "reps")},
                                     "alpha": reg, "n": int(r["ls"].size)}
        ci_rows.append(_ci_crit(ci, "gt", 0.0, f"{c * 1e4:.0f} bp/side mean {_pc(ci.get('est'), 3)}", lambda v: _pc(v, 3)))
        al_rows.append((f"{c * 1e4:.0f} bp/side alpha {_pc(reg['alpha'], 3)}/month t {_s(reg['t'], 2)} ({reg['n']} months)",
                        None if reg["t"] is None else reg["t"] >= 2.0, reg["t"] is not None and reg["t"] <= -2.0))
    rows = [all_constructions(ci_rows, "lower 95% bound of the mean monthly calendar-time F 8-9 minus F 0-2 return > 0"),
            all_constructions(al_rows, f"FF5 alpha t >= 2 (NW lag {T451_LAG})")]
    return _gate(rows, covered, why), tests


def b6c_stockxs_piotroski_value(archive):
    """T-451."""
    need = [SPY_B, SEC_TICK_B, FF5_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    panel = _equity_panel(archive)
    tick = _sec_tickers(archive)
    colmap = {}
    for s, j in panel.col.items():
        ck = tick.get(s)
        if ck:
            colmap.setdefault(ck[0], j)
    sec = _sec_facts(archive, _priced_ciks(archive, panel))
    if not sec["names"]:
        return _missing(archive, [FACTS_PREFIX + "b<NNN>"])
    events = {c: tenk_events(sec["facts"].get(c, ())) for c in colmap}
    shares = {c: shares_series(sec["facts"].get(c, ())) for c in colmap}
    positions, info, bps = t451_positions(panel, events, colmap, shares)
    months = _months(T451_START, T451_END)
    runs = {c: calendar_ls(panel, positions, months, c) for c in T451_COSTS}
    r0 = runs[T451_COSTS[0]]
    n = int(r0["ls"].size)
    if n < 8:
        return _too_short(n, T451_MIN_N, "months", "calendar-time months with both F-score legs, 2011..2026-09")
    ff = _ff5(archive)
    Fm = {c: month_factors(panel.cal, ff, runs[c]["months"]) for c in T451_COSTS}
    # coverage: 10-K filers (Assets reported) by acceptance year vs those with a usable Yahoo price
    priced = set(colmap)
    yrs = [y for y in sorted(sec["filers"]) if "2011" <= y <= T451_END[:4]]
    tot = sum(len(sec["filers"][y]) for y in yrs)
    have = sum(len(sec["filers"][y] & priced) for y in yrs)
    miss_share = 1.0 - have / tot if tot else None
    covered = miss_share is not None and miss_share <= 0.0
    lg, sg = float(np.mean(r0["long_gross"])), float(np.mean(r0["short_gross"]))
    why = (f"{_pc(miss_share, 1)} of the 10-K filer-years {yrs[0] if yrs else '?'}..{yrs[-1] if yrs else '?'} in the "
           f"archived SEC XBRL facts ({tot} filer-years, {have} with a Yahoo price) have no archived price: the B/M "
           "breakpoints and both legs depend on the missing names. The survivor-only bias of the L/S has no known sign: "
           "distressed delistings fall mainly in the F 0-2 short leg, where dropping them raises the leg's return and so "
           "lowers the L/S, while long-leg delistings (acquisitions, failures) move it either way (survivor legs before "
           f"costs: long F 8-9 {_pc(lg, 3)}/month, short F 0-2 {_pc(sg, 3)}/month)")
    rows, tests = t451_judge(runs, Fm, covered, why, n)
    v, expl = _decide(rows, n, T451_MIN_N, "months")
    t0 = tests[f"{T451_COSTS[0] * 1e4:.0f}bp"]
    t1 = tests[f"{T451_COSTS[1] * 1e4:.0f}bp"]
    head = ("SURVIVOR-ONLY DIAGNOSTIC (not the claim's universe)" if not covered else
            "every archived 10-K filer is priced")
    tail = "Every criterion is therefore NOT JUDGED (rule 9)" if not covered else "every criterion is judged"
    reason = (f"{head}: {len(colmap)} priced stocks with a CIK; "
              f"{info['events']} 10-K events, {info['fscored']} with all nine F-score signals and positive book equity, "
              f"{info['entered']} enterable (price >= $5, shares, a month-end breakpoint), {info['value']} in the top B/M "
              f"quintile ({info['long']} F 8-9 long, {info['short']} F 0-2 short positions); {n} calendar-time months "
              f"{r0['months'][0]}..{r0['months'][-1]} with both legs held (mean {_f(float(np.mean(r0['n_long'])), 1)} long, "
              f"{_f(float(np.mean(r0['n_short'])), 1)} short names): mean L/S {_pc(t0['mean']['est'], 3)}/month at 10 bp "
              f"({_ci(t0['mean'].get('ci'), 3, 100, '%')}), {_pc(t1['mean']['est'], 3)} at 20 bp "
              f"({_ci(t1['mean'].get('ci'), 3, 100, '%')}), FF5 alpha t {_s(t0['alpha']['t'], 2)} / {_s(t1['alpha']['t'], 2)}. "
              f"Universe coverage: {why}. {tail} — {expl}")
    stat = {"label": "SURVIVOR-ONLY" if not covered else "FULL UNIVERSE", "n_months": n, "months": [r0["months"][0], r0["months"][-1]], "tests": tests,
            "events": info, "priced_ciks": len(colmap), "filer_years": tot, "filer_years_priced": have,
            "missing_share": miss_share, "covered": covered, "facts_buckets_absent": sec["absent"],
            "names_long_mean": float(np.mean(r0["n_long"])), "names_short_mean": float(np.mean(r0["n_short"])),
            "leg_gross_mean": {"long": lg, "short": sg}, "criteria": [(r[0], r[1]) for r in rows]}
    return _out(stat, n, v, reason)


# ======================================================================================= T-473 Avellaneda-Lee ==

T473_START, T473_END = "2010-01-01", "2026-12-31"
T473_MIN_N = 2000
T473_WIN = 60
T473_PCA_WIN = 252
T473_NPC = 15
T473_LAMBDA = 0.02
T473_CAP = 2.0
T473_COST = 5e-4
T473_BORROW = 0.005
T473_KAPPA = 252.0 / 30.0
T473_BLOCK = 20.0
T473_PBO_PARTS = 8
T473_SPLIT = "2018-01-01"
T473_VARIANTS = (
    {"name": "etf", "model": "etf", "volume": False, "open": 1.25, "close_long": 0.5, "close_short": 0.75, "vix": False},
    {"name": "pca15", "model": "pca", "volume": False, "open": 1.25, "close_long": 0.5, "close_short": 0.75, "vix": False},
    {"name": "etf_volume", "model": "etf", "volume": True, "open": 1.25, "close_long": 0.5, "close_short": 0.75, "vix": False},
    {"name": "etf_1.0/0.25/0.25", "model": "etf", "volume": False, "open": 1.0, "close_long": 0.25, "close_short": 0.25,
     "vix": False},
    {"name": "etf_vix", "model": "etf", "volume": False, "open": 1.25, "close_long": 0.5, "close_short": 0.75, "vix": True},
)

GICS_ETF = {"Materials": ("XLB", "XLB"), "Energy": ("XLE", "XLE"), "Financials": ("XLF", "XLF"),
            "Industrials": ("XLI", "XLI"), "Information Technology": ("XLK", "XLK"), "Consumer Staples": ("XLP", "XLP"),
            "Utilities": ("XLU", "XLU"), "Health Care": ("XLV", "XLV"), "Consumer Discretionary": ("XLY", "XLY"),
            "Real Estate": ("XLRE", "XLF")}
_TELECOM = re.compile(r"(?i)telecom|interactive media|wireless|alternative carriers")


def gics_etf(sector: str, sub: str = "") -> Optional[tuple]:
    """(ETF, fallback before the ETF has a 60-day window) for a GICS sector."""
    if sector == "Communication Services":
        return ("XLC", "XLK") if _TELECOM.search(sub or "") else ("XLC", "XLY")
    return GICS_ETF.get(sector)


def sic_etf(sic) -> Optional[tuple]:
    """Declared SEC SIC -> sector SPDR map for removed members (ETF, fallback)."""
    try:
        s = int(str(sic).strip())
    except (TypeError, ValueError):
        return None
    one = lambda e: (e, e)
    media, tele, reit = ("XLC", "XLY"), ("XLC", "XLK"), ("XLRE", "XLF")
    if 100 <= s <= 999:
        return one("XLP")
    if 1000 <= s <= 1099 or 1400 <= s <= 1499:
        return one("XLB")
    if 1200 <= s <= 1399:
        return one("XLE")
    if 1500 <= s <= 1799:
        return one("XLY") if 1520 <= s <= 1531 else one("XLI")
    if 2000 <= s <= 2199:
        return one("XLP")
    if 2200 <= s <= 2399 or 2500 <= s <= 2599 or 3100 <= s <= 3199:
        return one("XLY")
    if 2400 <= s <= 2499 or 2600 <= s <= 2699:
        return one("XLB")
    if 2700 <= s <= 2799:
        return media
    if 2800 <= s <= 2899:
        if 2833 <= s <= 2836:
            return one("XLV")
        if 2840 <= s <= 2844:
            return one("XLP")
        return one("XLB")
    if 2900 <= s <= 2999:
        return one("XLE")
    if 3000 <= s <= 3099 or 3200 <= s <= 3399:
        return one("XLB")
    if 3400 <= s <= 3499:
        return one("XLI")
    if 3500 <= s <= 3599:
        return one("XLK") if 3570 <= s <= 3579 else one("XLI")
    if 3600 <= s <= 3699:
        return one("XLY") if (3630 <= s <= 3639 or 3650 <= s <= 3652) else one("XLK")
    if 3700 <= s <= 3799:
        return one("XLY") if (3710 <= s <= 3716 or 3750 <= s <= 3751) else one("XLI")
    if 3800 <= s <= 3899:
        if 3840 <= s <= 3851:
            return one("XLV")
        return one("XLI") if s == 3812 else one("XLK")
    if 3900 <= s <= 3999:
        return one("XLY")
    if 4000 <= s <= 4799:
        return one("XLI")
    if 4800 <= s <= 4899:
        return media if 4830 <= s <= 4841 else tele
    if 4900 <= s <= 4999:
        return one("XLE") if 4922 <= s <= 4925 else one("XLU")
    if 5000 <= s <= 5199:
        if s == 5122:
            return one("XLV")
        return one("XLP") if (5140 <= s <= 5149 or 5180 <= s <= 5182) else one("XLI")
    if 5200 <= s <= 5999:
        return one("XLP") if (5400 <= s <= 5499 or s == 5912) else one("XLY")
    if 6000 <= s <= 6799:
        return reit if s == 6798 else one("XLF")
    if 7000 <= s <= 7999:
        if 7370 <= s <= 7379:
            return one("XLK")
        if 7310 <= s <= 7319 or 7800 <= s <= 7899:
            return media
        if 7000 <= s <= 7099 or 7200 <= s <= 7299 or 7900 <= s <= 7999:
            return one("XLY")
        return one("XLI")
    if 8000 <= s <= 8099 or s == 8731:
        return one("XLV")
    if 8200 <= s <= 8299:
        return one("XLY")
    if 8100 <= s <= 8999:
        return one("XLI")
    return None


def _win_valid(X: np.ndarray, w: int) -> np.ndarray:
    """valid[t] = the w values X[t-w+1..t] are all finite (False for t < w-1)."""
    fin = np.isfinite(X).astype(np.int32)
    cs = np.cumsum(fin, axis=0)
    out = np.zeros(X.shape, bool)
    if X.shape[0] >= w:
        cnt = cs[w - 1:].copy()
        cnt[1:] -= cs[:-w]
        out[w - 1:] = cnt == w
    return out


def ou_scores(eps: np.ndarray, kappa_min: float = T473_KAPPA) -> dict:
    """Avellaneda-Lee OU fit of the cumulative residual X = cumsum(eps) (W x n): AR(1) X_{k+1} = a + b X_k, m, sigma_eq,
    the raw score X_W - m (the caller centres m) and the validity flags."""
    X = np.cumsum(eps, axis=0)
    Xa, Xb = X[:-1], X[1:]
    ma, mb = Xa.mean(axis=0), Xb.mean(axis=0)
    va = ((Xa - ma) ** 2).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = ((Xa - ma) * (Xb - mb)).sum(axis=0) / va
        a = mb - b * ma
        z = Xb - a - b * Xa
        vz = (z * z).sum(axis=0) / max(Xa.shape[0] - 2, 1)
        ok = (va > 0) & (vz > 0) & (b > 0) & (b < 1)
        m = np.where(ok, a / (1.0 - b), np.nan)
        seq = np.where(ok, np.sqrt(vz / np.maximum(1.0 - b * b, 1e-12)), np.nan)
    kap = ok & (b < math.exp(-kappa_min / 252.0))
    return {"x_last": X[-1], "m": m, "seq": seq, "b": b, "ok": ok, "kappa_ok": kap}


def _scores(ou: dict) -> np.ndarray:
    m = ou["m"]
    mbar = float(np.nanmean(m[ou["ok"]])) if ou["ok"].any() else 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(ou["ok"], (ou["x_last"] - (m - mbar)) / ou["seq"], np.nan)


def etf_resid(Rw: np.ndarray, Fw: np.ndarray) -> tuple:
    """Column-wise OLS of Rw on Fw with an intercept: (beta, residuals)."""
    Fm, Rm = Fw.mean(axis=0), Rw.mean(axis=0)
    dF, dR = Fw - Fm, Rw - Rm
    vF = (dF * dF).sum(axis=0)
    beta = np.where(vF > 0, (dF * dR).sum(axis=0) / np.where(vF > 0, vF, 1.0), 0.0)
    return beta, dR - beta * dF


def pca_factors(Y_raw: np.ndarray, k: int) -> Optional[np.ndarray]:
    """Eigenportfolio weights Q (n x k) = top-k eigenvectors of the correlation matrix of Y_raw (T x n) divided by each
    stock's volatility (Avellaneda-Lee), via the T x T Gram matrix."""
    mu = Y_raw.mean(axis=0)
    sd = Y_raw.std(axis=0, ddof=1)
    if not np.all(sd > 0):
        return None
    Y = (Y_raw - mu) / sd
    G = Y @ Y.T
    w, U = np.linalg.eigh(G)
    k = min(k, Y.shape[0] - 1, Y.shape[1])
    w, U = w[::-1][:k], U[:, ::-1][:, :k]
    if not np.all(w > 1e-10):
        return None
    V = (Y.T @ U) / np.sqrt(w)
    return V / sd[:, None]


def al_backtest(inp: dict, variants: Sequence[dict] = T473_VARIANTS, win: int = T473_WIN, pca_win: int = T473_PCA_WIN,
                n_pc: int = T473_NPC, lam: float = T473_LAMBDA, cap: float = T473_CAP, cost: float = T473_COST,
                borrow: float = T473_BORROW, kappa_min: float = T473_KAPPA) -> dict:
    """Daily Avellaneda-Lee simulation of every variant on one panel. inp: R (D x N stock returns, NaN when a bar or its
    predecessor is missing), RP (D x N returns for P&L, 0 where unknown), E / EP (D x S ETF returns), member (D x N),
    etf_p / etf_f (N,) ETF column (primary, fallback), V (D x N volume, optional), vix_ok (D,), rf (D,) bill return
    over each day, hd (D,) calendar days per return day, t0 (first return day), t1 (last return day). Signal at close
    t -> trade at close t+1 -> earn from day t+2; costs of a trade charged on the first day it is held. Two cost
    accountings of the same trades: ``net`` charges every traded dollar against the drifted holdings (daily rebalancing
    to equal dollars is a trade); ``net_target`` is Avellaneda-Lee's own equity equation, cost = eps x sum |Q(t+1) -
    Q(t)| on the target notionals (drift is not charged). Returns {variant: {net, net_target, gross, cost, cost_target,
    borrow, n_open, gross_exposure}} over return days t0..t1."""
    R, RP, E, EP, member = inp["R"], inp["RP"], inp["E"], inp["EP"], inp["member"]
    D, N = R.shape
    S = E.shape[1]
    t0, t1 = int(inp["t0"]), int(inp["t1"])
    rf, hd = inp["rf"], inp["hd"]
    need_vol = any(v["volume"] for v in variants)
    need_pca = any(v["model"] == "pca" for v in variants)
    v60 = _win_valid(R, win)
    e60 = _win_valid(E, win)
    v252 = _win_valid(R, pca_win) if need_pca else None
    RV = None
    if need_vol:
        V = inp["V"]
        Vp = np.where(np.isfinite(V) & (V > 0), V, np.nan)
        cs = np.nancumsum(np.nan_to_num(Vp), axis=0)
        cnt = np.cumsum(np.isfinite(Vp), axis=0)
        s10 = cs.copy()
        s10[10:] -= cs[:-10]
        c10 = cnt.copy()
        c10[10:] -= cnt[:-10]
        with np.errstate(invalid="ignore", divide="ignore"):
            RV = np.where(c10 == 10, R * (s10 / 10.0) / Vp, np.nan)
        vv60 = _win_valid(RV, win)
    etf_p, etf_f = np.asarray(inp["etf_p"], int), np.asarray(inp["etf_f"], int)
    vix_ok = inp.get("vix_ok")
    if vix_ok is None:
        vix_ok = np.ones(D, bool)
    st = {v["name"]: np.zeros(N, np.int8) for v in variants}
    Hs = {v["name"]: np.zeros(N) for v in variants}
    He = {v["name"]: np.zeros(S) for v in variants}
    tgt = {v["name"]: None for v in variants}
    n_held = {v["name"]: 0 for v in variants}
    pend_cost = {v["name"]: 0.0 for v in variants}
    pend_cost_t = {v["name"]: 0.0 for v in variants}
    res = {v["name"]: {k: np.zeros(t1 - t0 + 1) for k in ("net", "gross", "cost", "borrow", "n_open", "gross_exposure",
                                                           "net_target", "cost_target")}
           for v in variants}
    ts0 = max(t0 - 2, win)
    for t in range(ts0, t1 + 1):
        # 1. realise day t on the holdings set at close t-1, then execute the targets of signal t-1 at close t
        if t >= t0:
            r = RP[t]
            e = EP[t]
            k = t - t0
            for v in variants:
                nm = v["name"]
                hs, he = Hs[nm], He[nm]
                gross = float(hs @ (r - rf[t]) + he @ (e - rf[t]))
                bor = borrow * (float(np.maximum(-hs, 0).sum()) + float(np.maximum(-he, 0).sum())) * hd[t] / 365.0
                res[nm]["gross"][k] = gross
                res[nm]["borrow"][k] = bor
                res[nm]["cost"][k] = pend_cost[nm]
                res[nm]["net"][k] = gross - bor - pend_cost[nm]
                res[nm]["cost_target"][k] = pend_cost_t[nm]
                res[nm]["net_target"][k] = gross - bor - pend_cost_t[nm]
                res[nm]["n_open"][k] = float(n_held[nm])
                res[nm]["gross_exposure"][k] = float(np.abs(hs).sum() + np.abs(he).sum())
        for v in variants:
            nm = v["name"]
            if tgt[nm] is None:
                continue
            ds = Hs[nm] * (1.0 + RP[t])
            dE = He[nm] * (1.0 + EP[t])
            ns, ne, nh = tgt[nm]
            pend_cost[nm] = cost * (float(np.abs(ns - ds).sum()) + float(np.abs(ne - dE).sum()))
            pend_cost_t[nm] = cost * (float(np.abs(ns - Hs[nm]).sum()) + float(np.abs(ne - He[nm]).sum()))
            Hs[nm], He[nm], n_held[nm] = ns, ne, nh
        if t >= t1:
            break
        # 2. signals at close t
        etf_t = np.where(e60[t, etf_p], etf_p, np.where(e60[t, etf_f], etf_f, -1))
        sig = {}
        for model, vol in {(v["model"], v["volume"]) for v in variants}:
            if model == "etf":
                RR = RV if vol else R
                valid = member[t] & (vv60[t] if vol else v60[t]) & (etf_t >= 0)
                cols = np.flatnonzero(valid)
                s = np.full(N, np.nan)
                beta = np.zeros(N)
                arok = np.zeros(N, bool)
                kap = np.zeros(N, bool)
                if cols.size >= 2:
                    Rw = RR[t - win + 1:t + 1, cols]
                    Fw = E[t - win + 1:t + 1][:, etf_t[cols]]
                    b, eps = etf_resid(Rw, Fw)
                    ou = ou_scores(eps, kappa_min)
                    s[cols] = _scores(ou)
                    beta[cols] = b
                    arok[cols] = ou["ok"]
                    kap[cols] = ou["kappa_ok"]
                sig[(model, vol)] = {"valid": valid, "s": s, "beta": beta, "arok": arok, "kap": kap, "etf": etf_t}
            else:
                valid = member[t] & v252[t]
                cols = np.flatnonzero(valid)
                s = np.full(N, np.nan)
                arok = np.zeros(N, bool)
                kap = np.zeros(N, bool)
                Q = B = None
                if cols.size > n_pc + 2:
                    Q = pca_factors(R[t - pca_win + 1:t + 1, cols], n_pc)
                if Q is not None:
                    Rw = R[t - win + 1:t + 1, cols]
                    Fk = Rw @ Q
                    Z = np.column_stack([np.ones(win), Fk])
                    coef = np.linalg.lstsq(Z, Rw, rcond=None)[0]
                    eps = Rw - Z @ coef
                    B = coef[1:].T
                    ou = ou_scores(eps, kappa_min)
                    s[cols] = _scores(ou)
                    arok[cols] = ou["ok"]
                    kap[cols] = ou["kappa_ok"]
                else:
                    valid = np.zeros(N, bool)
                sig[(model, vol)] = {"valid": valid, "s": s, "arok": arok, "kap": kap, "cols": cols, "Q": Q, "B": B}
        # 3. state machines and targets (executed at close t+1)
        for v in variants:
            nm = v["name"]
            g = sig[(v["model"], v["volume"])]
            x = st[nm].copy()
            valid, s = g["valid"], g["s"]
            x[~valid] = 0
            sok = valid & g["arok"]
            with np.errstate(invalid="ignore"):
                x[(x == 1) & sok & (s > -v["close_long"])] = 0
                x[(x == -1) & sok & (s < v["close_short"])] = 0
                can = (x == 0) & valid & g["kap"] & (bool(vix_ok[t]) if v["vix"] else True)
                x[can & (s < -v["open"])] = 1
                x[can & (s > v["open"])] = -1
            st[nm] = x
            n_open = int(np.count_nonzero(x))
            d = min(lam, cap / n_open) if n_open else 0.0
            q = x.astype(float) * d
            ne = np.zeros(S)
            ns = q.copy()
            if n_open:
                if v["model"] == "etf":
                    sel = np.flatnonzero(x)
                    np.add.at(ne, g["etf"][sel], -g["beta"][sel] * q[sel])
                else:
                    cols = g["cols"]
                    qc = q[cols]
                    ns[cols] += g["Q"] @ (-(g["B"].T @ qc))
            tgt[nm] = (ns, ne, n_open)
    return res


def _member_sets(archive) -> tuple:
    """[(effective date, set of tickers)] from fja05680, then Wikipedia changes after fja's last date."""
    rows = sorted((r["value"]["date"], set(r["value"]["tickers"])) for r in _rows(archive, FJA_B)
                  if (r.get("value") or {}).get("date"))
    if not rows:
        return [], 0
    last = rows[-1][0]
    cur = set(rows[-1][1])
    n_w = 0
    if _has(archive, WIKI_CH_B):
        chg = sorted(((r.get("value") or {}) for r in _rows(archive, WIKI_CH_B)),
                     key=lambda v: v.get("effective_date") or "")
        by = {}
        for v in chg:
            d = v.get("effective_date") or ""
            if d > last:
                by.setdefault(d, []).append(v)
        for d in sorted(by):
            for v in by[d]:
                if v.get("removed_ticker"):
                    cur.discard(v["removed_ticker"].strip())
                if v.get("added_ticker"):
                    cur.add(v["added_ticker"].strip())
                n_w += 1
            rows.append((d, set(cur)))
    return rows, n_w


def t473_inputs(archive) -> tuple:
    """Panel, membership, sectors and ETF returns for T-473, with the exclusion counts."""
    cal = _sessions(archive)
    sets, n_wiki = _member_sets(archive)
    dates = [d for d, _ in sets]
    D = len(cal)
    mem_idx = [bisect.bisect_right(dates, d) - 1 for d in cal.days]
    tick = set()
    for k in sorted(set(mem_idx)):
        if k >= 0:
            tick |= sets[k][1]
    wiki = {}
    if _has(archive, WIKI_B):
        for r in _rows(archive, WIKI_B):
            v = r.get("value") or {}
            if v.get("symbol"):
                wiki[ysym(v["symbol"])] = v
    removed_name = {}
    if _has(archive, WIKI_CH_B):
        for r in _rows(archive, WIKI_CH_B):
            v = r.get("value") or {}
            if v.get("removed_ticker") and v.get("removed_security"):
                removed_name[ysym(v["removed_ticker"])] = v["removed_security"]
    sec_t = _sec_tickers(archive) if _has(archive, SEC_TICK_B) else {}
    info = {"tickers": len(tick), "no_series": 0, "not_equity": [], "name_mismatch": [], "no_sector": [], "used": 0,
            "sector_from": {"gics": 0, "sic": 0}, "wiki_changes_after_fja": n_wiki}
    cand0 = []
    for t in sorted(tick):
        y = ysym(t)
        stk = _stock(archive, y)
        if stk is None:
            info["no_series"] += 1
            continue
        if not is_equity(stk):
            info["not_equity"].append(y)
            continue
        cand0.append((t, y, stk))
    need_sic = {sec_t[y][0] for t, y, _ in cand0 if y not in wiki and y in sec_t}
    comp = _company_rows(archive, need_sic) if need_sic else {}
    cand = []
    for t, y, stk in cand0:
        # a current member's Yahoo series is the current company (no check); a removed member's must carry its name
        if y not in wiki and removed_name.get(y):
            names = [(stk["meta"] or {}).get("longName") or ""]
            if y in sec_t:
                v = comp.get(sec_t[y][0]) or {}
                names += [sec_t[y][1], v.get("name") or ""] + [(f or {}).get("name") or "" for f in (v.get("formerNames") or [])]
            if names_ok(removed_name[y], names) is False:
                info["name_mismatch"].append(y)
                continue
        cand.append((t, y, stk))
    etf_cols = {s: k for k, s in enumerate(SECTOR_ETFS)}
    series, ep, ef, keep_t = [], [], [], []
    for t, y, stk in cand:
        sec = None
        if y in wiki:
            sec = gics_etf(wiki[y].get("gics_sector") or "", wiki[y].get("gics_sub_industry") or "")
            if sec:
                info["sector_from"]["gics"] += 1
        elif y in sec_t and sec_t[y][0] in comp:
            sec = sic_etf(comp[sec_t[y][0]].get("sic"))
            if sec:
                info["sector_from"]["sic"] += 1
        if not sec:
            info["no_sector"].append(y)
            continue
        series.append(stk)
        ep.append(etf_cols[sec[0]])
        ef.append(etf_cols[sec[1]])
        keep_t.append(t)
    info["used"] = len(series)
    panel = Panel(cal, series)
    Nn = len(series)
    member = np.zeros((D, Nn), bool)
    colof = {t: j for j, t in enumerate(keep_t)}
    for i, k in enumerate(mem_idx):
        if k < 0:
            continue
        js = [colof[t] for t in sets[k][1] if t in colof]
        member[i, js] = True
    # member-days without a usable price (2010+): every fja member, priced or not
    i0 = cal.on_or_after(T473_START)
    tot = sum(len(sets[mem_idx[i]][1]) for i in range(i0, D) if mem_idx[i] >= 0)
    priced = int((member[i0:] & panel.real[i0:]).sum())
    info["member_days"], info["member_days_priced"] = int(tot), priced
    Araw = np.full((D, Nn), np.nan)
    Araw[panel.real] = panel.A[panel.real]
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.full((D, Nn), np.nan)
        R[1:] = Araw[1:] / Araw[:-1] - 1.0
        RP = np.zeros((D, Nn))
        RP[1:] = np.nan_to_num(panel.A[1:] / panel.A[:-1] - 1.0)
    E = np.full((D, len(SECTOR_ETFS)), np.nan)
    EP = np.zeros((D, len(SECTOR_ETFS)))
    etf_have = []
    for k, s in enumerate(SECTOR_ETFS):
        st = _stock(archive, s)
        if st is None:
            continue
        etf_have.append(s)
        a = np.full(D, np.nan)
        for d, x in zip(st["days"], st["adj"]):
            i = cal.pos.get(d)
            if i is not None:
                a[i] = x
        with np.errstate(invalid="ignore", divide="ignore"):
            E[1:, k] = a[1:] / a[:-1] - 1.0
            af = _ffill(a[:, None])[:, 0]
            EP[1:, k] = np.nan_to_num(af[1:] / af[:-1] - 1.0)
    bills = _bills(archive)
    rf = np.zeros(D)
    hd = np.zeros(D)
    for i in range(1, D):
        rf[i] = bills.growth(cal.days[i - 1], cal.days[i]) - 1.0
        hd[i] = float(cal.ords[i] - cal.ords[i - 1])
    vix = _vix(archive)
    vv = np.array([vix.get(d, np.nan) for d in cal.days], float)
    vix_ok = np.zeros(D, bool)
    for i in range(251, D):
        w = vv[i - 251:i + 1]
        w = w[np.isfinite(w)]
        vix_ok[i] = bool(np.isfinite(vv[i]) and w.size >= 200 and vv[i] > np.median(w))
    inp = {"R": R, "RP": RP, "E": E, "EP": EP, "member": member, "etf_p": np.array(ep, int), "etf_f": np.array(ef, int),
           "V": panel.V, "vix_ok": vix_ok, "rf": rf, "hd": hd}
    info["etfs"] = etf_have
    return inp, panel, info


ACCOUNTINGS = ("drift", "target")
ACCOUNTING_NAMES = {"drift": "every traded dollar (drifted holdings)", "target": "Avellaneda-Lee equity equation (target changes)"}


def _t473_one(series: dict, primary: str) -> tuple:
    x = series[primary]
    sb = mc_escalate(lambda seed: sharpe_boot(x, T473_BLOCK, N_BOOT, seed), lambda t: resolve(
        (t.get("ci") or [None])[0], (t.get("ci_mc_se") or [0.0])[0], 0.0, "gt")[0], REPS, SEED, keys=("ci",))
    fam = [float(sharpe_ratio(v)) for v in series.values()]
    d = family_dsr(x, fam, len(series))
    M = np.column_stack([series[k] for k in series])
    pbo = pbo_cscv(M, T473_PBO_PARTS) if M.shape[0] >= 2 * T473_PBO_PARTS else None
    rows = [_ci_crit(sb, "gt", 0.0, f"Sharpe {_s(sb.get('est'), 3)} ({_ci(sb.get('ci'), 3)})", lambda v: _s(v, 3)),
            dsr_row(d, "DSR"),
            (f"PBO {_f(pbo['pbo'] if pbo else None, 3)} ({pbo['n_combinations'] if pbo else 0} combinations)",
             None if pbo is None else pbo["pbo"] < 0.5, False)]
    return rows, {"sharpe": {k: sb.get(k) for k in ("est", "ci", "ci_mc_se", "p", "reps", "block")}, "dsr": d, "pbo": pbo,
                  "family_sharpe_ann": {k: float(sharpe_ratio(v, 252)) for k, v in series.items()}}


def t473_judge(readings: dict, primary: str, n: int, min_n: int = T473_MIN_N) -> tuple:
    """readings: {accounting: {variant: daily net excess returns}}. Each criterion is judged under every cost
    accounting of the same trades and passes (fails) only when all of them pass (fail); a disagreement is undecided
    (rule 11 / rule 12 spirit: the verdict must not hinge on the bookkeeping convention)."""
    per = {a: _t473_one(s, primary) for a, s in readings.items()}
    k = len(next(iter(readings.values())))
    labels = (f"95% lower bound of the annualised net Sharpe > 0 (stationary bootstrap, mean block {T473_BLOCK:g} days)",
              f"DSR > 0.95 over the {k} declared variants", f"CSCV PBO < 0.5 over the {k} variants")
    rows = [all_constructions([(f"{a} {per[a][0][i][0]}", per[a][0][i][1], per[a][0][i][2]) for a in per], lab)
            for i, lab in enumerate(labels)]
    return rows, {a: per[a][1] for a in per}


def b6c_stockxs_avellaneda_lee(archive):
    """T-473."""
    need = [SPY_B, FJA_B, WIKI_B, DTB3_B, VIX_B] + [dh(s) for s in SECTOR_ETFS[:9]]
    miss = _missing(archive, need)
    if miss:
        return miss
    inp, panel, info = t473_inputs(archive)
    cal = panel.cal
    t0 = max(cal.on_or_after(T473_START), T473_PCA_WIN + 2)
    t1 = min(cal.on_or_before(T473_END), len(cal) - 1)
    n = t1 - t0 + 1
    if n < 30 or info["used"] < 20:
        return _too_short(max(n, 0), T473_MIN_N, "trading days", f"S&P 500 members with Yahoo prices ({info['used']} usable)")
    inp["t0"], inp["t1"] = t0, t1
    res = al_backtest(inp, T473_VARIANTS, T473_WIN, T473_PCA_WIN, T473_NPC, T473_LAMBDA, T473_CAP, T473_COST,
                      T473_BORROW, T473_KAPPA)
    readings = {"drift": {v["name"]: res[v["name"]]["net"] for v in T473_VARIANTS},
                "target": {v["name"]: res[v["name"]]["net_target"] for v in T473_VARIANTS}}
    primary = T473_VARIANTS[0]["name"]
    rows, tests = t473_judge(readings, primary, n)
    v, expl = _decide(rows, n, T473_MIN_N, "trading days")
    days = cal.days[t0:t1 + 1]
    lab = np.array(days)
    halves, reg = {}, {}
    for a in ACCOUNTINGS:
        x = readings[a][primary]
        for nm, msk in (("2010-2017", lab < T473_SPLIT), ("2018-2026", lab >= T473_SPLIT)):
            if msk.sum() >= 40:
                hb = sharpe_boot(x[msk], T473_BLOCK, N_BOOT, SEED)
                halves.setdefault(a, {})[nm] = {"sharpe": hb["est"], "ci": hb["ci"], "n": int(msk.sum())}
        for nm, msk in (("2020-03", np.char.startswith(lab, "2020-03")), ("2022", np.char.startswith(lab, "2022"))):
            if msk.any():
                reg.setdefault(a, {})[nm] = {"cum": float(np.prod(1.0 + x[msk]) - 1.0),
                                             "sharpe": float(sharpe_ratio(x[msk], 252))}
    p = res[primary]
    gsr = float(sharpe_ratio(p["gross"], 252))
    cov = 1.0 - info["member_days_priced"] / info["member_days"] if info["member_days"] else None

    def acc_txt(a):
        t = tests[a]
        cst = p["cost"] if a == "drift" else p["cost_target"]
        fam_txt = "; ".join(f"{k} {_s(s_, 2)}" for k, s_ in t["family_sharpe_ann"].items())
        return (f"[{ACCOUNTING_NAMES[a]}] cost {_pc(float(np.mean(cst)) * 252, 2)}/yr, net Sharpe "
                f"{_s(t['sharpe']['est'], 3)} ({_ci(t['sharpe'].get('ci'), 3)}), DSR {_f(t['dsr'].get('dsr'))}, PBO "
                f"{_f(t['pbo']['pbo'] if t['pbo'] else None)}; variants {fam_txt}; halves "
                + "; ".join(f"{k} {_s(h['sharpe'], 3)} ({_ci(h['ci'], 3)})" for k, h in halves.get(a, {}).items())
                + "; " + "; ".join(f"{k} cum {_pc(r_['cum'], 2)}" for k, r_ in reg.get(a, {}).items()))

    reason = (f"SURVIVORSHIP-BIASED BY THE CLAIM'S OWN DEFINITION (members with Yahoo prices; delisted members are absent, "
              f"so this is an upper bound): {info['used']} of {info['tickers']} fja05680 tickers in the index since "
              f"{cal.days[0]} usable ({info['no_series']} without a Yahoo series, {len(info['not_equity'])} reused as ETFs, "
              f"{len(info['name_mismatch'])} reused-ticker name mismatches, {len(info['no_sector'])} without a sector; "
              f"sectors {info['sector_from']['gics']} GICS, {info['sector_from']['sic']} SEC SIC), {_pc(cov, 1)} of "
              f"member-days {T473_START[:4]}+ without a usable price; return days {days[0]}..{days[-1]} ({n}). Sector-ETF "
              f"s-score (60-day OLS + AR(1), kappa > 252/30, open |s| > 1.25, close -0.5 / +0.75, next-close fills, 2% per "
              f"position, stock gross <= 2x, 5 bp per side per trade, 50 bp/yr borrow): gross excess Sharpe {_s(gsr, 3)}, "
              f"borrow {_pc(float(np.mean(p['borrow'])) * 252, 2)}/yr, mean {_f(float(np.mean(p['n_open'])), 1)} open "
              f"positions, gross exposure {_f(float(np.mean(p['gross_exposure'])), 2)}x; "
              + " ".join(acc_txt(a) for a in ACCOUNTINGS) + " — " + expl)
    stat = {"label": "SURVIVORSHIP-BIASED (members with Yahoo prices, as claimed)", "n_days": n,
            "window": [days[0], days[-1]], "tests": tests, "halves": halves, "regimes": reg, "gross_sharpe_ann": gsr,
            "cost_ann": {"drift": float(np.mean(p["cost"])) * 252, "target": float(np.mean(p["cost_target"])) * 252},
            "borrow_ann": float(np.mean(p["borrow"])) * 252,
            "open_mean": float(np.mean(p["n_open"])), "gross_exposure_mean": float(np.mean(p["gross_exposure"])),
            "universe": {k: info[k] for k in ("tickers", "no_series", "used", "sector_from", "member_days",
                                              "member_days_priced", "wiki_changes_after_fja", "etfs")},
            "not_equity": info["not_equity"], "name_mismatch": info["name_mismatch"], "no_sector": info["no_sector"],
            "member_days_unpriced_share": cov, "variants": [v_["name"] for v_ in T473_VARIANTS],
            "accountings": ACCOUNTING_NAMES, "criteria": [(r[0], r[1]) for r in rows]}
    return _out(stat, n, v, reason)


HARNESSES = {
    "b6c_stockxs_lending_dtc_deciles": b6c_stockxs_lending_dtc_deciles,
    "b6c_stockxs_short_interest_dtc": b6c_stockxs_short_interest_dtc,
    "b6c_stockxs_piotroski_value": b6c_stockxs_piotroski_value,
    "b6c_stockxs_avellaneda_lee": b6c_stockxs_avellaneda_lee,
}

THEORY_MAP = {
    "T-375": "b6c_stockxs_lending_dtc_deciles",
    "T-393": "b6c_stockxs_short_interest_dtc",
    "T-451": "b6c_stockxs_piotroski_value",
    "T-473": "b6c_stockxs_avellaneda_lee",
}
