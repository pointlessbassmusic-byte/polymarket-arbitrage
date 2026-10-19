"""
Batch 6c, group ``cryptoxs``: crypto cross-section, on-chain and DeFi claims on the batch-6c crypto bundles.
==============================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-314  weekly top-tertile 3-week momentum on the point-in-time top 30 coins (CoinMarketCap market-cap ranks, Sunday
           snapshot, executed at the Monday close, held one week), 2018-01..2026-10, minus BTC after 40 + 10 bps per
           side: mean > 0 with the 95% interval excluding 0 (studentized circular block bootstrap, 8-week blocks, 5,000
           draws), DSR > 0.95 over the 24 declared trials, above the 95th percentile of 1,000 rank permutations.
  * T-420  6-month low-turnover-conditioned momentum minus unconditioned 6-month momentum (top-minus-bottom terciles,
           3-month overlapping holds) on the declared 68-ETF list, hold months 2007-01..2026-09: >= 200 monthly
           observations, out-of-sample (2017-04..2026-09, after the 2007-2016 selection sample and a one-quarter
           embargo) spread difference >= 1 point a quarter with HAC p < 0.05, DSR >= 0.95 and PBO < 0.3 over the 72
           declared cells (36 of them on the CoinMarketCap point-in-time crypto top 20 by trailing 30-day dollar volume).
  * T-400  BTC forward 90-day log return on days with MVRV < 1 minus days with MVRV > 3 (one-day lag), 2011-2026: 95%
           CI excluding 0 (circular block bootstrap of the daily timeline, 90-day blocks), >= 4 distinct episodes of
           each regime (the pre-registered park rule), the 100/50/0% rule beating buy-and-hold Sharpe in the held-out
           cycles, and a point-in-time MVRV (the controls' stored vintage), which Coin Metrics does not serve: None.
  * T-402  predictive slope of BTC's next-30-day log return on the 30-day growth of aggregate stablecoin supply (USDT,
           USDC, DAI, BUSD, TUSD; one-day lag), 2018-2026: HAC t >= 2 over >= 400 weekly observations, positive slope
           in 2018-2021 and in 2022-2026.
  * T-403  BTC forward 90-day log return after a hash-ribbon recovery-with-momentum signal minus the unconditional
           90-day forward return, 2011-2026: 95% CI excluding 0 over >= 15 signals, >= 60% of the post-publication
           (2019-08-) signals positive.
  * T-367  TVL-weighted mean spread of the 7-day base APY of the Ethereum USDC lending pools (Aave v3, Spark, Maple)
           over DTB3, 2023-02..2026-09: one-sided 95% upper bound below the 1.5% risk charge (block bootstrap, 30-day
           blocks, 5,000 draws) over >= 900 days, and every named pool's history inside the window archived: a pool
           whose DefiLlama chart opens already live (cut off) is a data gap, a None criterion (rule 9).

Conventions
  * Data. Every bundle is read through ``archive.load``; a row is used only when its ``available_at`` is not after the
    bundle's capture time. Bundles (mandel.data.crypto_history): ``cmc-historical-listings`` (every Sunday and Monday
    from 2017-12-03, top 500 by market cap, dead coins included; price = the date's close, available the next day
    00:00 UTC), ``cmc-daily-listings-<YYYY>`` (every day from 2017-11-01, same schema), ``coinmetrics-<asset>-daily``
    (day + 1; CURRENT VINTAGE: Coin Metrics recomputes realised cap without vintages), ``btc-hashrate-daily``
    (blockchain.info TH/s, day + 1, current vintage), ``defillama-yields`` (daily chart points stamped about 23:01 UTC,
    available at their timestamp). Yahoo ``daily-history-<SYM>`` bars are keyed by UTC day (crypto close 24:00 UTC;
    ETFs by session), with adjclose total-return prices and raw close x volume as dollar volume. FRED ``fred-DTB3``.
  * Crypto universes. Stablecoins, wrapped / bridged / staked copies, lending receipt tokens and gold tokens are
    excluded by a DECLARED list of CMC ids (EXCLUDE_IDS, written from coin names before any return was computed; the
    snapshot ``flags`` are snapshot-dated and are not used), declared slug prefixes (EXCLUDE_SLUG_PREFIXES) and a
    point-in-time peg screen: a coin whose every price in the trailing snapshots (weekly: the last 6 Sunday/Monday
    snapshots; daily: the last 14 days, at least 10 present) lies within 2% of 1 USD, or within 2% of BTC, ETH, BNB,
    SOL, TRX or HYPE, is a peg that day. The screen uses only past prices. The excluded ids are reported.
  * Depth. Both CMC bundles hold the top 500 by MARKET CAP. T-314 ranks by market cap (top 20/30/50 of 500: no cut).
    T-420's crypto top 20 ranks by trailing 30-day dollar volume, so the depth cuts any coin below market-cap rank 500
    whatever its volume (very small-cap, often wash-traded coins), and a held coin that falls below rank 500 has no
    exit price. Diagnostic: a month in which a member of the volume top 20 ranks 401-500 by market cap (within 100
    places of the cut) is one where coins just below the depth plausibly qualify too ('the depth binds'). When it binds
    in any month, every crypto-dependent family reading (DSR's trial-Sharpe variance, the 72-cell PBO) is treated as unknown:
    the DSR is judged from the bound over the 36 ETF cells (batch6c_xs.dsr_bound: fails if even the most favourable
    variance fails, else not implemented) and the 72-cell PBO reading is not implemented (None).
  * Snapshot integrity (both CMC bundles). A stored snapshot is corrupt when it shares under 80% of its ids with BOTH
    neighbouring snapshots while the neighbours share over 90% with each other, or when it lacks at least 3 coins that
    are in both neighbours' top 50 (CmcPanel's screen; it flags 2020-11-30 in both bundles and 2021-09-28 in the daily
    one). A flagged snapshot is treated as missing (a data limit, named in the reason): its rows are dropped, T-314 drops
    the weeks that need it (formation, formation start, entry or exit), and T-420 takes the month's last intact day as
    the month-end (volume universe and month-end prices), keeping the fill on the day after the month's last stored day.
  * Vanished coins (T-314's control). A held coin missing from the exit snapshot is marked at its last snapshot price
    (the latest snapshot at or before the exit holding it; 0 return when none after entry); the stress case marks it at
    that price minus 50% only when the coin is absent from every later snapshot (a coin that vanishes, i.e. delisted);
    a coin that only fell below the depth and came back keeps the last-price mark (both counts reported). T-420's
    crypto holds use the same last-price rule on the daily snapshots.
  * Calendars (rule 10). T-314 names the Sunday snapshot and the next day's close (its library rule and the trial's
    'snapshot ranks and prices as of t, trade t+1'): the weekly grid has no free phase; because the registry claim itself
    says only 'weekly', the primary trial on every formation weekday of the daily snapshots is reported (the per-start
    range of rule 10). T-420 names monthly J-month
    momentum: month-end decisions, fill at the next session's close (ETFs) or the next day's close (crypto),
    overlapping K-month cohorts (Jegadeesh-Titman, the pooled all-start estimator). T-400 and T-403 use every day
    (overlapping 90-day windows, 90-day bootstrap blocks = the overlap). T-402 names 'weekly sampling' without a
    weekday, so its primary statistic is the pooled all-start (daily) regression with Newey-West lag 60 days (2 x the
    30-day hold) and, as the trial's named robustness, Hansen-Hodrick lag 29; both must pass (rule 11); the seven
    weekday grids' weekly slopes and t's (Newey-West lag max(floor(4 (n/100)^(2/9)), 5) >= the 4-week overlap) are
    reported as the per-start range. T-367 is a daily descriptive spread (no decision grid).
  * Point in time (rules 4, 12). CMC snapshots are known the next day 00:00 UTC, before the next day's close (T-314,
    T-420 fills). Coin Metrics and blockchain.info values for day d are used from day d + 1: the T-400 / T-402 / T-403
    signal at day t reads day t - 1, and every forward window starts at the close of day t. T-403's price-momentum
    confirmation is read two ways (rule 12): at close t, the fill close (live proxy), and at close t - 1; both must
    agree. MVRV and hash rate are the current vintage (no past vintages exist): T-403 treats hash rate as near point in
    time, as the triage says, and cross-checks two independent estimates (blockchain.info and Coin Metrics) as its
    procedure names (both must pass); T-400's controls require the stored MVRV vintage, so that criterion is None.
  * Bills and Sharpe (rule 7). DTB3 is a 91-day discount yield; accruals use the continuous rate -ln(1 - d 91/360) /
    (91/365) of the print dated strictly before each day (batch6b_bw.Bills). T-367 compares annual yields: the APY
    against DTB3 as a bond-equivalent yield (365 d / (360 - 91 d), the trial's wording) AND as an effective annual
    yield ((1 - d 91/360)^(-365/91) - 1, the APY's own compounding); both must pass. Sharpe ratios are on excess
    returns, 365 periods a year for daily crypto, 12 monthly, 52 weekly.
  * Costs (rule 9) as each claim states, on drift-adjusted turnover: T-314 40 + 10 bps per side (BTC benchmark held
    without cost); T-420 5 and 10 bps per ETF leg, 50 and 100 bps per crypto leg (both ends run; every cost-dependent
    criterion must hold at both); T-400 10 and 60 bps per unit switched (both ends); T-403 and T-402 make no cost-bearing
    claim (T-403's 10-40 bps per switch is reported as the log cost of a round trip, two switches).
  * Intervals (rule 6). Means: studentized circular block bootstrap (batch6b_bw._stud, Bartlett-HAC s.e., bandwidth =
    block), 5,000 draws per seed, interval ends averaged over 5 seeds with their Monte Carlo s.e. (25 when 5 cannot
    resolve the bound). Conditional-mean differences (T-400, T-403): percentile circular block bootstrap of the daily
    timeline (90-day blocks, the overlap), same seeds. HAC: Newey-West (Bartlett). DSR: batch6c_mom.family_dsr (house
    1/(T-1) floor on the trial-Sharpe variance). PBO: overfit.pbo_cscv, 8 partitions.
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively.

Claim-specific choices (declared before any result)
  * T-314: trials = formation 1/2/3/4 weeks x tertile/quintile x top 20/30/50 = 24 (primary 3 weeks, tertile, 30);
    formation = Sunday price / Sunday price L weeks earlier - 1; a coin enters when it has both prices and a Monday entry
    price; the long book holds floor(n/q) names equal weight. Permutation null: in every week floor(n/3) of the
    primary's eligible coins at random, gross minus BTC, the strategy's own mean cost subtracted. Today's-top-30
    diagnostic: the top 30 non-excluded coins of the last Sunday snapshot, ranked the same way in every week they
    exist. Per cycle 2018-2020, 2021-2022, 2023-2026 reported.
  * T-420: J = 3/6/12-month return ending one month before the decision (the skip month); turnover = mean daily dollar
    volume over months t-2..t / over t-11..t (ETFs: raw close x volume, all 12 months listed; crypto: CMC volume24h, at
    least 20 and 60 days present). Sorts are sequential: momentum terciles (floor(n/3)), then within the winners the
    floor(k/3) lowest-turnover names long and within the losers the floor(k/3) highest-turnover names short (Lee-
    Swaminathan sign); confirmation sign reversed; unconditioned = winners minus losers; long-only = the long leg,
    fully invested, judged on excess return over bills. 72 cells = J x K (1/3/6) x sign x long-short/long-only x
    ETF/crypto; each cell's difference series is it minus its unconditioned counterpart. 'Quarterly' = 3 x the mean
    monthly difference of the overlapping books; HAC lag max(Newey-West rule, 2K). DSR >= 0.95 is judged on the claim
    cell's difference series AND its own long-short series, on the full 2007-2026 sample AND out of sample, at both
    cost ends (every reading must pass); PBO < 0.3 on the cells' own series AND difference series, over the 36 ETF
    cells (2007-2026) AND all 72 cells on their common months (2019-01..), at both cost ends. Crypto: decisions
    2018-12..2026-08 (the first month every J and the 12-month turnover exist), cohorts start then.
  * T-400: regime from MVRV of day t - 1; forward 90-day log return from close t (Coin Metrics PriceUSD before
    2014-09-17, Yahoo BTC-USD from then); episodes = runs of regime days merged across gaps of <= 30 days and <= 90 days
    (both must give >= 4 of each regime; n = the smaller 90-day-merge count); rule = 100% BTC when MVRV < 1, 0% when >
    3, else 50%, rebalanced on a regime switch at the daily close with a 7-day minimum hold, idle cash in bills; cycles
    = halving epochs, test cycles 3-4 read two ways (epochs after the 2012 halving: 2020-05-11..; epochs from genesis:
    2016-07-09..2024-04-19), both must agree; the held-out Sharpe difference is the point estimate over the held-out
    period (paired CBB interval reported). Vintage: Coin Metrics serves only the current vintage, so the vintage
    criterion is None (the verdict is at most inconclusive), and the difference and rule criteria are also judged with
    MVRV scaled by 0.9 and by 1.1 (an assumed restatement band): each passes or fails only when every scaling agrees,
    so a failure counts only when no plausible restatement could reverse it.
  * T-402: aggregate growth = sum over the coins present on both days of SplyCur(t-1) / SplyCur(t-31) - 1 (a coin's
    first appearance is not growth); decision days 2018-01-01.. with a complete 30-day forward window. The procedure's
    'walk-forward by year' is reported (not in the pass): expanding window, the slope fitted on the days whose 30-day
    forward window closed before 1 January of year y, predicting every day of y; out-of-sample R2 against the training
    mean and the sign hit rate per year, pooled OOS R2. The slopes fitted within each year are in-sample descriptions and
    are labelled so.
  * T-403: hash ribbons = 30- and 60-day calendar SMAs of the daily hash rate (>= 80% of days present); capitulation
    while SMA30 < SMA60 (data through t - 1); a recovery is the first day after a capitulation with SMA30 >= SMA60;
    the signal is the first day from the recovery on which the 10-day price SMA exceeds the 20-day one, cancelled by a
    new capitulation first; one signal per recovery; 'positive' = forward 90-day log return > 0. The controls' 'Multiple
    testing: 4 variants into DSR' (the library's variants: 30/60 cross + price confirmation = the primary; no price
    confirmation = entry at the recovery close; hold until MVRV > 3 = the primary's entries held until the first close
    whose MVRV of the day before exceeds 3; difficulty drop >= 5% as the capitulation) is reported (not in the pass): each
    variant is a daily-timeline event strategy on blockchain.info hash rate with the live momentum reading, whose daily
    return is the BTC log return minus its unconditional daily mean over the window on held days and 0 otherwise (gross;
    its mean is the share of held days x (held-day mean - unconditional mean), the claim's comparison), and the
    primary's DSR is batch6c_mom.family_dsr at 4 trials (house 1/(T-1) floor). No Bitcoin difficulty series is archived,
    so the difficulty variant is not computed: it enters the DSR only through the trial count (named in the reason).
  * T-367: pools fixed from the 2026-10-16 snapshot (mandel.data.crypto_history.LLAMA_POOLS): Aave v3 USDC, Spark
    savings USDC (the library's 'Spark savings USDC') and Maple syrupUSDC; SparkLend USDC in place of Spark savings is
    the second reading (both must pass). 7-day base APY = mean of the last 7 daily apyBase points (>= 5 present).
    'TVL-weighted mean daily spread' is read two ways and both must pass: the day's spread weights the pools by that
    day's tvlUsd and days weigh equally (the mean of daily TVL-weighted spreads), and every pool-day weighs by its tvlUsd
    (sum tvl x spread / sum tvl over all pool-days: a ratio of means, studentized through its linearised influence).
    DTB3 = the latest print available at the chart timestamp. DefiLlama's tvlUsd for a lending pool is its available
    liquidity, as the trial's chart field gives it. Chart starts: DefiLlama's chart of a pool begins when DefiLlama
    began tracking it, not necessarily at launch. A pool whose first chart point falls inside the window and already
    holds more than $50M TVL, or more than 10% of its set's TVL that day (when other members hold TVL), was live before
    it: its history from the window start to the day before is MISSING, a None criterion naming the span (rule 9), not
    'not yet launched'. A pool with no chart point in the window is missing over the whole window. Below both
    thresholds the first point is taken as the launch (Aave v3 USDC: $6.9M on 2023-02-06; SparkLend: $0 on 2023-08-11).
    The observed-data readings are still computed and judged. Sensitivity (reported): for a cut-off pool whose share
    token CMC prices (T367_SHARE_TOKENS: syrupUSDC), the share price at the first chart point is backed out from the
    first CMC price and the chart's base APY compounded between them (used only when the compounded APY matches the CMC
    price growth over the CMC span within 1%); the gap is then filled with a constant APY r from the inception the share
    price implies (price 1 at inception) and TVL ramping linearly from 0 to the first point's TVL (r = 6/8/10/12%; at
    10% also to 25/10/5% of it), and every reading's one-sided bound is recomputed (one seed, at most 1,000 draws).
    Other gaps stay unfilled in the scenarios.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import (Bills, _boot_idx, _chunks, _ci_crit, _clean, _decide, _mean_stat, _stud,
                                           all_constructions, mc_escalate, mc_reps, sharpe_diff_test)
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.experiments.batch6c_xs import CMC_NAME, U68, book, dsr_bound, month_panel, nw_lag, overlap
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

N_BOOT = 5000                  # the trials' 5,000 bootstrap draws
REPS = 5                       # bootstrap seeds behind every decisive interval end
SEED = 0
N_PERM = 1000                  # T-314's 1,000 permutations
ALPHA = 0.05
DSR_PASS = 0.95
PBO_PARTS = 8
_N = NormalDist()
_Z95 = _N.inv_cdf(0.95)

DTB3_B = "fred-DTB3"
CMC_W = "cmc-historical-listings"
CMC_D_PREFIX = "cmc-daily-listings-"
CMC_D_YEARS = tuple(range(2017, 2027))
CMC_D = tuple(f"{CMC_D_PREFIX}{y}" for y in CMC_D_YEARS)
BTC_Y = "daily-history-BTC-USD"
ETH_Y = "daily-history-ETH-USD"
HASH_B = "btc-hashrate-daily"
LLAMA_B = "defillama-yields"
STABLES = ("usdt", "usdc", "dai", "busd", "tusd")


def cm_b(asset: str) -> str:
    return f"coinmetrics-{asset}-daily"


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


def _iter(archive, name: str):
    """Rows of a bundle that were available when the bundle was captured (streamed, not cached)."""
    cap = getattr(archive.get(name), "created_at", None)
    for r in archive.load(name):
        if cap and r.get("available_at") and r["available_at"] > cap:
            continue
        yield r


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _utc_day(t) -> str:
    return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d")


def _yahoo(archive, name: str) -> dict:
    """{days, close (raw), adj (adjclose; a bar without one carries the previous ratio), vol} of a daily-history bundle."""
    def load():
        by = {}
        for r in _iter(archive, name):
            v = r["value"]
            c = _num(v.get("close"))
            if c is None or c <= 0:
                continue
            a = _num(v.get("adjclose"))
            vol = _num(v.get("volume"))
            by[_utc_day(v["t"])] = (c, a if (a is not None and a > 0) else float("nan"), vol if vol is not None else float("nan"))
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 3)
        close, adj, vol = arr[:, 0], arr[:, 1].copy(), arr[:, 2]
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "close": close, "adj": adj, "vol": vol}
    return _cached(archive, ("yahoo", name), load)


def _closes(archive, name: str) -> dict:
    y = _yahoo(archive, name)
    return dict(zip(y["days"], (float(x) for x in y["adj"])))


def _cm(archive, asset: str) -> dict:
    """{day: value dict} of a coinmetrics-<asset>-daily bundle."""
    def load():
        out = {}
        for r in _iter(archive, cm_b(asset)):
            v = r["value"]
            if v.get("day"):
                out[v["day"]] = v
        return out
    return _cached(archive, ("cm", asset), load)


def _fred(archive, name: str) -> dict:
    def load():
        out = {}
        for r in _iter(archive, name):
            v = r["value"]
            x = _num(v.get("value"))
            if x is not None and v.get("day"):
                out[v["day"]] = (x, r.get("available_at") or v["day"])
        return out
    return _cached(archive, ("fred", name), load)


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills({d: v for d, (v, _) in _fred(archive, DTB3_B).items()}))


def _metric(cm: dict, key: str) -> dict:
    return {d: float(v[key]) for d, v in cm.items() if _num(v.get(key)) is not None}


def _day_add(d: str, k: int) -> str:
    return date.fromordinal(date.fromisoformat(d).toordinal() + k).isoformat()


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _cal(a: str, b: str) -> list:
    o0, o1 = _ord(a), _ord(b)
    return [date.fromordinal(o).isoformat() for o in range(o0, o1 + 1)]


def splice_price(early: dict, late: dict, switch: str) -> dict:
    """``early`` closes before ``switch``, ``late`` closes from it (each {day: price})."""
    out = {d: p for d, p in early.items() if d < switch and p and p > 0}
    out.update({d: p for d, p in late.items() if d >= switch and p and p > 0})
    return out


# =========================================================================================== formatting helpers ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _pp(x, nd: int = 2) -> str:
    """A value already in percentage points."""
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f} pp"


def _ci_txt(ci, nd: int = 2, scale: float = 100.0, unit: str = "%") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _flag_txt(flagged: dict) -> str:
    """The snapshots failing the CMC integrity screen, with the numbers that flag them."""
    return "; ".join(f"{d} ({f['rows']} rows; shares {f['overlap_prev'] * 100:.0f}% of the ids of {f['prev']} and "
                     f"{f['overlap_next'] * 100:.0f}% of {f['next']}, which share {f['neighbours_overlap'] * 100:.0f}%; lacks "
                     f"{f['top50_missing']} of their common top 50)" for d, f in sorted(flagged.items()))


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _too_short(n: int, min_n: int, unit: str, what: str):
    v, why = _verdict([(f"n >= trial min_n ({n} of {min_n} {unit})", None)])
    return ({"too_short": True, "n": int(n), "min_n": int(min_n)}, int(n), v,
            f"{what}: only {n} {unit} can be formed from the archived data (the claim needs {min_n}); nothing is computed — {why}")


# ================================================================================================== statistics ==

def mean_test(x, block: int, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED,
              level: float = 0.95, side: str = "gt", thr: float = 0.0) -> dict:
    """Studentized circular block bootstrap of a mean (two-sided ``level`` interval; ends averaged over seeds with
    their Monte Carlo s.e.; escalated to more seeds when the end that decides ``side``/``thr`` is unresolved)."""
    x = np.asarray(x, float)
    nb = N_BOOT if n_boot is None else n_boot
    return mc_escalate(lambda seed: _stud(_mean_stat, [x], block, nb, seed, level=level),
                       lambda t: _ci_crit(t, side, thr, "")[1], REPS if reps is None else reps, seed)


def _diff_boot_once(y, a, b, block: int, n_boot: int, seed: int) -> dict:
    """Percentile circular block bootstrap of mean(y | a) - mean(y | b) over a daily timeline (a, b boolean masks);
    resamples with an empty side are dropped (counted)."""
    rng = np.random.default_rng(seed)
    n = y.size
    ds, dropped = [], 0
    for k in _chunks(n_boot, 3 * n):
        idx = _boot_idx(rng, n, block, k)
        Y, A, B = y[idx], a[idx], b[idx]
        ca, cb = A.sum(axis=1), B.sum(axis=1)
        ok = (ca > 0) & (cb > 0)
        dropped += int((~ok).sum())
        d = (Y * A).sum(axis=1)[ok] / ca[ok] - (Y * B).sum(axis=1)[ok] / cb[ok]
        ds.append(d)
    d = np.concatenate(ds) if ds else np.array([])
    if d.size < 10:
        return {"ci": [None, None], "dropped": dropped, "n_ok": int(d.size)}
    return {"ci": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))], "dropped": dropped, "n_ok": int(d.size)}


def diff_test(y, a, b, block: int = 90, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    y = np.asarray(y, float)
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    nb = N_BOOT if n_boot is None else n_boot
    est = float(y[a].mean() - y[b].mean()) if a.any() and b.any() else None
    t = mc_escalate(lambda seed: _diff_boot_once(y, a, b, block, nb, seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1],
                    REPS if reps is None else reps, seed)
    t["est"] = est
    t["block"] = int(block)
    return t


def _ratio_stat(Nm, Dm, bw):
    """Row-wise ratio of means mean(N) / mean(D) and its s.e. from the linearised influence (N - est D) / mean(D) with a
    Bartlett-HAC long-run variance (bandwidth ``bw``): the studentizer of ``ratio_test``."""
    n = Nm.shape[1]
    mN, mD = Nm.mean(axis=1), Dm.mean(axis=1)
    est = mN / mD
    z = (Nm - est[:, None] * Dm) / mD[:, None]
    return est, np.sqrt(_hac_var(z, bw) / n)


def ratio_test(num, den, block: int, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED,
               level: float = 0.95, side: str = "gt", thr: float = 0.0) -> dict:
    """Studentized circular block bootstrap of a ratio of means (paired daily columns), as ``mean_test``."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    nb = N_BOOT if n_boot is None else n_boot
    return mc_escalate(lambda seed: _stud(_ratio_stat, [num, den], block, nb, seed, level=level),
                       lambda t: _ci_crit(t, side, thr, "")[1], REPS if reps is None else reps, seed)


def ols_kernel(y, x, lag: int, kernel: str = "bartlett") -> dict:
    """OLS y = a + b x with a kernel HAC sandwich: Bartlett (Newey-West) or uniform (Hansen-Hodrick) weights up to
    ``lag``. A non-positive uniform-kernel variance is reported as None (the HH estimator is not guaranteed PSD)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size
    X = np.column_stack([np.ones(n), x])
    XtXi = np.linalg.inv(X.T @ X)
    coef = XtXi @ X.T @ y
    e = y - X @ coef
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        w = 1.0 - l / (lag + 1.0) if kernel == "bartlett" else 1.0
        G = u[l:].T @ u[:-l]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    vb = float(V[1, 1])
    se = math.sqrt(vb) if vb > 0 else None
    return {"alpha": float(coef[0]), "beta": float(coef[1]), "se": se, "t": (float(coef[1]) / se) if se else None,
            "lag": int(lag), "kernel": kernel, "n": int(n)}


def hac_mean_lag(x, lag: int) -> dict:
    """Mean with a Newey-West s.e. at ``lag``; t and one-sided p (H0: mean <= 0)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else None, "se": None, "t": None, "p": None, "lag": int(lag), "n": int(n)}
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 1e-300) / n)
    t = float(x.mean() / se)
    return {"mean": float(x.mean()), "se": se, "t": t, "p": 1.0 - _N.cdf(t), "lag": int(lag), "n": int(n)}


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 else None


def spells(mask: np.ndarray, gap: int) -> list:
    """[(start, end)] runs of True in a daily mask, merging runs separated by at most ``gap`` False days."""
    out = []
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return out
    s = e = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - e - 1 <= gap:
            e = i
        else:
            out.append((s, e))
            s = e = i
    out.append((s, e))
    return out


def holm(ps: dict) -> dict:
    keys = sorted(ps, key=lambda k: ps[k])
    m, run, out = len(keys), 0.0, {}
    for j, k in enumerate(keys):
        run = max(run, min(1.0, (m - j) * ps[k]))
        out[k] = run
    return out


# ============================================================================================= CMC snapshots ==

# Declared exclusions (CMC ids; names verified in the snapshots, and coin classification audited from names and price
# stability only, never from strategy returns). USD, EUR and CNY stablecoins, gold tokens, wrapped / bridged / staked
# copies.
EXCLUDE_IDS = {
    825: "USDT", 3408: "USDC", 4687: "BUSD", 4943: "DAI", 2308: "SAI", 2563: "TUSD", 3330: "USDP", 3306: "GUSD",
    4779: "HUSD", 5068: "USDN", 7129: "UST", 19891: "USDD", 26081: "FDUSD", 27772: "PYUSD", 29470: "USDe", 36148: "USD1",
    33793: "USDG", 34387: "RLUSD", 39120: "U", 6952: "FRAX", 2927: "sUSD", 9566: "LUSD", 33039: "USDS", 32307: "USD0",
    24927: "crvUSD", 18852: "USDC.e", 1312: "SBD", 2989: "EURS", 20641: "EURC", 624: "bitCNY",
    4705: "PAXG", 5176: "XAUt",
    3717: "WBTC", 4023: "BTCB", 18579: "WTRX", 5777: "renBTC", 2396: "WETH", 8085: "stETH", 12409: "wstETH",
    24760: "WBETH", 28695: "weETH", 32994: "cbBTC", 7192: "WBNB", 16116: "wrapped SOL", 35881: "WHYPE", 29520: "ezETH",
}
# Declared slug prefixes: wrapped / bridged / staked copies and lending receipt tokens (Venus vTokens, Compound cTokens,
# Aave aTokens; the governance tokens 'compound', 'aave' and 'lido-dao' are not matched; Lido's stETH / wstETH are
# declared by id).
EXCLUDE_SLUG_PREFIXES = ("wrapped-", "bridged-", "venus-", "compound-", "aave-", "staked-", "restaked-")
PEG_REFS = (1, 1027, 1839, 5426, 1958, 32196)          # BTC, ETH, BNB, SOL, TRX, HYPE
PEG_BAND = 0.02
BTC_ID = 1


def declared_excluded(cid: int, slug: Optional[str]) -> bool:
    if cid in EXCLUDE_IDS:
        return True
    s = (slug or "").lower()
    return any(s.startswith(p) for p in EXCLUDE_SLUG_PREFIXES) or "-bridged-" in s or "-wrapped-" in s


SNAP_OVERLAP = 0.80            # a snapshot sharing < 80% of its ids with both neighbours ...
SNAP_NEIGHBOURS = 0.90         # ... while the neighbours share > 90% with each other is corrupt,
SNAP_TOP = 50                  # ... as is one lacking >= 3 coins that are in both neighbours' top 50
SNAP_TOP_MISSING = 3


def snapshot_screen(dates: Sequence[str], ids: Sequence[np.ndarray], tops: Sequence[np.ndarray]) -> dict:
    """Integrity screen of date-ordered snapshots (``ids``: each snapshot's unique sorted ids; ``tops``: its top-50 ids,
    sorted): {date: diagnostics} of the snapshots that are corrupt (see SNAP_*). The first and last snapshots have one
    neighbour and are not screened."""
    out = {}
    for k in range(1, len(dates) - 1):
        s, a, b = ids[k], ids[k - 1], ids[k + 1]
        if s.size == 0 or a.size == 0 or b.size == 0:
            continue
        ov_a = np.intersect1d(s, a, assume_unique=True).size / a.size
        ov_b = np.intersect1d(s, b, assume_unique=True).size / b.size
        ov_ab = np.intersect1d(a, b, assume_unique=True).size / min(a.size, b.size)
        miss = int(np.setdiff1d(np.intersect1d(tops[k - 1], tops[k + 1], assume_unique=True), s, assume_unique=True).size)
        if (ov_a < SNAP_OVERLAP and ov_b < SNAP_OVERLAP and ov_ab > SNAP_NEIGHBOURS) or miss >= SNAP_TOP_MISSING:
            out[dates[k]] = {"rows": int(s.size), "overlap_prev": round(float(ov_a), 3), "overlap_next": round(float(ov_b), 3),
                             "neighbours_overlap": round(float(ov_ab), 3), "top50_missing": miss,
                             "prev": dates[k - 1], "next": dates[k + 1]}
    return out


class CmcPanel:
    """Compact CMC listings: per snapshot date, arrays (sorted by cmcRank) of id, price, volume24h, market cap, rank;
    per coin, its (date index, price) history for last-price marks; meta id -> (symbol, slug, name). Snapshots failing
    the integrity screen (``snapshot_screen``; ``flagged``: {date: diagnostics}) keep their date in the index, so
    calendars stay aligned, but hold no rows: they are treated as missing everywhere (prices, marks, peg windows)."""

    def __init__(self, rows_iterables: Sequence, screen: bool = True):
        cols = {k: [] for k in ("d", "id", "px", "vol", "mc", "rk")}
        meta = {}
        for rows in rows_iterables:
            for r in rows:
                if r.get("kind") != "listing":
                    continue
                v = r["value"]
                px = _num(v.get("price"))
                cid = v.get("id")
                if cid is None or px is None or px <= 0:
                    continue
                cols["d"].append(v["date"])
                cols["id"].append(int(cid))
                cols["px"].append(px)
                cols["vol"].append(_num(v.get("volume24h")) or 0.0)
                cols["mc"].append(_num(v.get("marketCap")) or 0.0)
                cols["rk"].append(int(v.get("cmcRank") or 10 ** 6))
                meta[int(cid)] = (v.get("symbol"), v.get("slug"), v.get("name"))
        self.dates = sorted(set(cols["d"]))
        self.dpos = {d: k for k, d in enumerate(self.dates)}
        di = np.array([self.dpos[d] for d in cols["d"]], np.int64)
        cid = np.array(cols["id"], np.int64)
        rk = np.array(cols["rk"], np.int64)
        o = np.lexsort((rk, di))
        self.di, self.cid, self.rk = di[o], cid[o], rk[o]
        self.px = np.array(cols["px"], float)[o]
        self.vol = np.array(cols["vol"], float)[o]
        self.mc = np.array(cols["mc"], float)[o]
        self.start = np.searchsorted(self.di, np.arange(len(self.dates) + 1))
        self.flagged: dict = {}
        if screen and len(self.dates) >= 3:
            sl = [self.cid[self.start[k]:self.start[k + 1]] for k in range(len(self.dates))]
            self.flagged = snapshot_screen(self.dates, [np.unique(z) for z in sl], [np.unique(z[:SNAP_TOP]) for z in sl])
        self.flagged_idx = {self.dpos[d] for d in self.flagged}
        if self.flagged_idx:
            keep = ~np.isin(self.di, np.array(sorted(self.flagged_idx), np.int64))
            self.di, self.cid, self.rk, self.px, self.vol, self.mc = (z[keep] for z in (self.di, self.cid, self.rk, self.px,
                                                                                       self.vol, self.mc))
            self.start = np.searchsorted(self.di, np.arange(len(self.dates) + 1))
        self.meta = meta
        oc = np.lexsort((self.di, self.cid))
        self._c_cid, self._c_di, self._c_px = self.cid[oc], self.di[oc], self.px[oc]
        u, first = np.unique(self._c_cid, return_index=True)
        last = np.append(first[1:], self._c_cid.size)
        self._coin = {int(c): (int(a), int(b)) for c, a, b in zip(u, first, last)}
        self._pm: dict = {}

    def day(self, k: int) -> tuple:
        a, b = int(self.start[k]), int(self.start[k + 1])
        return self.cid[a:b], self.px[a:b], self.vol[a:b], self.rk[a:b], self.mc[a:b]

    def price_map(self, k: int) -> dict:
        m = self._pm.get(k)
        if m is None:
            ids, px = self.day(k)[:2]
            m = dict(zip(ids.tolist(), px.tolist()))
            self._pm[k] = m
        return m

    def price(self, cid: int, k: int) -> Optional[float]:
        return self.price_map(k).get(cid)

    def last_price(self, cid: int, k: int, lo: int = -1) -> tuple:
        """(price, date index) of the coin's latest snapshot at or before date index k (and after ``lo``), or (None, None)."""
        span = self._coin.get(int(cid))
        if span is None:
            return None, None
        a, b = span
        j = int(np.searchsorted(self._c_di[a:b], k, side="right")) - 1
        if j < 0 or self._c_di[a + j] <= lo:
            return None, None
        return float(self._c_px[a + j]), int(self._c_di[a + j])

    def seen_after(self, cid: int, k: int) -> bool:
        """Whether the coin is in any (intact) snapshot after date index k."""
        span = self._coin.get(int(cid))
        return span is not None and int(self._c_di[span[1] - 1]) > k

    def slug(self, cid: int) -> Optional[str]:
        return (self.meta.get(int(cid)) or (None, None, None))[1]

    def symbol(self, cid: int) -> str:
        return str((self.meta.get(int(cid)) or ("?",))[0])

    def pegged(self, cids: Sequence[int], window: Sequence[int], min_present: int) -> set:
        """Coins whose every price over the snapshot indices ``window`` lies within PEG_BAND of 1 USD or of a reference
        coin's price on the same snapshot (at least ``min_present`` snapshots holding the coin)."""
        maps = [self.price_map(k) for k in window]
        out = set()
        for c in cids:
            if c in PEG_REFS:
                continue
            pts = [(m[c], m) for m in maps if c in m]
            if len(pts) < min_present:
                continue
            if all(abs(p - 1.0) <= PEG_BAND for p, _ in pts):
                out.add(c)
                continue
            for ref in PEG_REFS:
                ok = [m.get(ref) for _, m in pts]
                if all(r is not None for r in ok) and all(abs(p / r - 1.0) <= PEG_BAND for (p, _), r in zip(pts, ok)):
                    out.add(c)
                    break
        return out


def _cmc_weekly(archive) -> CmcPanel:
    return _cached(archive, ("cmcw",), lambda: CmcPanel([_iter(archive, CMC_W)]))


def _cmc_daily(archive) -> CmcPanel:
    return _cached(archive, ("cmcd",), lambda: CmcPanel([_iter(archive, n) for n in CMC_D]))


# ============================================================================== T-314 weekly crypto momentum ==

T314_MIN_N = 400
T314_COST = 0.0050             # 40 bps fee + 10 bps slippage per side
T314_BLOCK = 8                 # weeks
T314_N_TRIALS = 24
T314_GRID = tuple((L, q, N) for L in (1, 2, 3, 4) for q in (3, 5) for N in (20, 30, 50))
T314_PRIMARY = (3, 3, 30)
T314_START = "2018-01-01"      # first Monday entry
T314_CYCLES = (("2018-2020", "2018-01-01", "2020-12-31"), ("2021-2022", "2021-01-01", "2022-12-31"),
               ("2023-2026", "2023-01-01", "2026-12-31"))
T314_PEG_WINDOW = 6            # snapshots (3 weeks of Sunday + Monday)


def long_book(W: Sequence[dict], R: Sequence[dict], cost: float) -> dict:
    """Net returns of a fully invested long book: W[t] target weights {id: w} set at each rebalance, R[t] the hold
    returns {id: r} of every held id. Turnover against the previous weights drifted over their hold; net = (1 - cost x
    turnover)(1 + gross) - 1 (the batch6c_xs.book arithmetic)."""
    T = len(W)
    gross, net, cst, to = np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T)
    prev: dict = {}
    for t in range(T):
        w, r = W[t], R[t]
        g = sum(wi * r[c] for c, wi in w.items())
        keys = set(w) | set(prev)
        turn = sum(abs(w.get(c, 0.0) - prev.get(c, 0.0)) for c in keys)
        gross[t], to[t], cst[t] = g, turn, cost * turn
        net[t] = (1.0 - cost * turn) * (1.0 + g) - 1.0
        den = 1.0 + g if abs(1.0 + g) > 1e-12 else 1e-12
        prev = {c: wi * (1.0 + r[c]) / den for c, wi in w.items()}
    return {"gross": gross, "net": net, "cost": cst, "turnover": to}


def _weekly_calendar(P: CmcPanel, start: str, weekday: int = 6) -> dict:
    """Formation snapshots S_k on ``weekday`` (6 = Sunday) with their execution day M_k = S_k + 1 (both stored), and the
    weeks whose entry day is on or after ``start`` and whose exit day exists."""
    sun = [k for k, d in enumerate(P.dates) if date.fromisoformat(d).weekday() == weekday and _day_add(d, 1) in P.dpos]
    mon = [P.dpos[_day_add(P.dates[k], 1)] for k in sun]
    weeks = [i for i in range(len(sun) - 1) if P.dates[mon[i]] >= start]
    return {"sun": sun, "mon": mon, "weeks": weeks}


def _excluded_at(P: CmcPanel, k: int, cids: Sequence[int], window: Sequence[int], min_present: int) -> set:
    dec = {c for c in cids if declared_excluded(c, P.slug(c))}
    return dec | P.pegged([c for c in cids if c not in dec], window, min_present)


def hold_return(P: CmcPanel, c: int, k0: int, k1: int, stress: bool = False) -> float:
    """Hold return of coin c from snapshot k0 to k1: the exit price when the coin is in the exit snapshot, else its last
    snapshot price after k0 and at or before k1 (the entry price when none: 0 return). The stress case marks that price
    down 50% only when the coin is absent from every later snapshot (it vanished); a coin that fell below the depth and
    came back keeps the last-price mark."""
    p0 = P.price(c, k0)
    p1 = P.price(c, k1)
    if p1 is not None:
        return p1 / p0 - 1.0
    pl, _ = P.last_price(c, k1, lo=k0)
    pl = p0 if pl is None else pl
    gone = stress and not P.seen_after(c, k1)
    return (0.5 * pl if gone else pl) / p0 - 1.0


def xs_momentum_weekly(P: CmcPanel, start: str = T314_START, min_n: int = T314_MIN_N, grid: Sequence[tuple] = T314_GRID,
                       primary: tuple = T314_PRIMARY, n_trials: int = T314_N_TRIALS, cost: float = T314_COST,
                       peg_window: int = T314_PEG_WINDOW, weekday: int = 6, light: bool = False) -> dict:
    """T-314 core on a CMC panel holding the formation-day and next-day snapshots (the weekly bundle: Sunday and Monday).
    ``weekday`` moves the formation day (rule-10 robustness on the daily bundle); ``light`` returns only the primary
    trial's mean net excess. Weeks that need a snapshot flagged by the panel's integrity screen (formation, entry or
    exit; per trial also the formation start) are dropped and listed."""
    if light:
        grid = (primary,)
    cal = _weekly_calendar(P, start, weekday)
    sun, mon, weeks = cal["sun"], cal["mon"], cal["weeks"]
    Lmax = max(g[0] for g in grid)
    weeks = [i for i in weeks if i >= Lmax]
    bad = P.flagged_idx
    flag_drop = [P.dates[mon[i]] for i in weeks if {sun[i], mon[i], mon[i + 1]} & bad]
    weeks = [i for i in weeks if not ({sun[i], mon[i], mon[i + 1]} & bad)]
    if len(weeks) < 52:
        return {"too_short": True, "n": len(weeks)}
    Nmax = max(g[2] for g in grid)
    snaps = sorted(set(sun) | set(mon))
    spos = {k: j for j, k in enumerate(snaps)}
    universe, excl_seen = {}, {}
    for i in weeks:
        k = sun[i]
        ids, _, _, rk, _ = P.day(k)
        cand = ids[:Nmax + 60].tolist()
        win = snaps[max(0, spos[k] - peg_window + 1):spos[k] + 1]
        ex = _excluded_at(P, k, cand, win, min(peg_window, len(win)))
        for c in ex:
            excl_seen.setdefault(c, P.dates[k])
        universe[i] = [c for c in cand if c not in ex][:Nmax]
    btc = np.array([(P.price(BTC_ID, mon[i + 1]) or np.nan) / (P.price(BTC_ID, mon[i]) or np.nan) - 1.0 for i in weeks])
    if not np.isfinite(btc).all():
        bad = int((~np.isfinite(btc)).sum())
        raise ValueError(f"{bad} weeks without a BTC price in the Monday snapshots")

    def hold(c, i, stress: bool) -> float:
        return hold_return(P, c, mon[i], mon[i + 1], stress)

    vanished = {}
    drops = {"formation": 0, "entry": 0}

    def run(L, q, N, fixed: Optional[list] = None, stress: bool = False, keep_elig: bool = False, track: bool = False):
        keep = np.array([sun[i - L] not in bad for i in weeks], bool)      # formation start not a flagged snapshot
        W, R, elig_all = [], [], []
        for j, i in enumerate(weeks):
            if not keep[j]:
                continue
            k, k0, m = sun[i], sun[i - L], mon[i]
            pool = fixed if fixed is not None else universe[i][:N]
            el = []
            for c in pool:
                p, p0, pm = P.price(c, k), P.price(c, k0), P.price(c, m)
                if p is not None and p0 is not None and pm is not None:
                    el.append((c, p / p0 - 1.0))
                elif track:
                    drops["formation" if (p is None or p0 is None) else "entry"] += 1
            kk = len(el) // q
            if kk < 1:
                W.append({})
                R.append({})
                elig_all.append([])
                continue
            order = sorted(range(len(el)), key=lambda a: -el[a][1])      # stable: market-cap order on ties
            longs = [el[a][0] for a in order[:kk]]
            W.append({c: 1.0 / kk for c in longs})
            r = {}
            for c in longs:
                r[c] = hold(c, i, stress)
                if track and P.price(c, mon[i + 1]) is None:
                    vanished.setdefault((c, i), (P.symbol(c), P.dates[mon[i + 1]], P.seen_after(c, mon[i + 1])))
            R.append(r)
            if keep_elig:
                elig_all.append([(c, hold(c, i, stress)) for c, _ in el])
        b = long_book(W, R, cost)
        bt = btc[keep]
        return {"net": b["net"], "gross": b["gross"], "cost": b["cost"], "turnover": b["turnover"], "excess": b["net"] - bt,
                "btc": bt, "weeks": [i for i, ok in zip(weeks, keep) if ok],
                "dropped": [P.dates[mon[i]] for i, ok in zip(weeks, keep) if not ok],
                "n_long": np.array([len(w) for w in W]), "elig": elig_all if keep_elig else None}

    runs = {g: run(*g, keep_elig=(g == primary and not light), track=(g == primary)) for g in grid}
    pr = runs[primary]
    x = pr["excess"]
    btc_p = pr["btc"]
    labels = [P.dates[mon[i]] for i in pr["weeks"]]
    flag_dropped = sorted(set(flag_drop) | set(pr["dropped"]))
    if light:
        return {"n": int(x.size), "mean": float(x.mean()), "first": labels[0], "last": labels[-1], "flag_dropped": flag_dropped}
    mt = mean_test(x, T314_BLOCK)
    crit = [_ci_crit(mt, "gt", 0.0, f"mean weekly net excess over BTC > 0 with the 95% CI excluding 0 (studentized CBB, "
                                    f"{T314_BLOCK}-week blocks)", fmt=lambda v: _pc(v, 3))]
    fam = {g: _sr_pp(r["excess"]) for g, r in runs.items()}
    d = family_dsr(x, list(fam.values()), n_trials)
    crit.append(dsr_row(d, f"DSR > {DSR_PASS} over the {n_trials} declared trials"))
    # permutation null: floor(n/3) random eligible coins each week, gross minus BTC, minus the strategy's mean cost
    rng = np.random.default_rng(SEED)
    tot, cnt = np.zeros(N_PERM), 0
    q = primary[1]
    for j, el in enumerate(pr["elig"]):
        kk = len(el) // q
        if kk < 1:
            continue
        r = np.array([v for _, v in el], float)
        o = np.argsort(rng.random((N_PERM, r.size)), axis=1)[:, :kk]
        tot += r[o].mean(axis=1) - btc_p[j]
        cnt += 1
    null = tot / max(cnt, 1) - float(pr["cost"].mean())
    q95 = float(np.quantile(null, 0.95))
    p_perm = float((1 + np.sum(null >= x.mean())) / (null.size + 1))
    crit.append((f"above the 95th percentile of the {N_PERM:,}-draw rank-permutation null (net mean excess {_pc(x.mean(), 3)} vs "
                 f"null 95th pct {_pc(q95, 3)}; p {p_perm:.3f})", bool(x.mean() > q95), p_perm >= 0.95))
    v, why = _decide(crit, x.size, min_n, "weeks")
    # diagnostics
    st = run(*primary, stress=True)
    last_k = [k for k in sun if k not in bad][-1]
    ids_last = P.day(last_k)[0][:Nmax + 60].tolist()
    win = snaps[max(0, spos[last_k] - peg_window + 1):spos[last_k] + 1]
    exl = _excluded_at(P, last_k, ids_last, win, min(peg_window, len(win)))
    today = [c for c in ids_last if c not in exl][:primary[2]]
    td = run(primary[0], primary[1], primary[2], fixed=today)
    cyc = {}
    for nm, a, b in T314_CYCLES:
        m = np.array([a <= l <= b for l in labels])
        cyc[nm] = {"n": int(m.sum()), "mean": float(x[m].mean()) if m.any() else None}
    return {"n": int(x.size), "labels": labels, "excess": x, "mean_test": mt, "dsr": d, "family_sharpe_pp": {"|".join(map(str, g)): s for g, s in fam.items()},
            "perm": {"q95": q95, "p": p_perm, "null_mean": float(null.mean())}, "criteria": [(c[0], c[1]) for c in crit],
            "verdict": v, "why": why, "mean_cost": float(pr["cost"].mean()), "mean_turnover": float(pr["turnover"].mean()),
            "gross_excess_mean": float((pr["gross"] - btc_p).mean()), "btc_mean": float(btc_p.mean()),
            "stress_mean": float(st["excess"].mean()), "today_top30": [P.symbol(c) for c in today],
            "today_mean": float(td["excess"].mean()), "survivorship_inflation": float(td["excess"].mean() - x.mean()),
            "cycles": cyc, "n_vanished": len(vanished), "n_vanished_returned": sum(1 for v_ in vanished.values() if v_[2]),
            "n_vanished_gone": sum(1 for v_ in vanished.values() if not v_[2]),
            "vanished_examples": [f"{s_} {d_} ({'came back' if b_ else 'never seen again'})"
                                  for s_, d_, b_ in sorted(vanished.values(), key=lambda z: z[1])][:12],
            "n_long": {"mean": float(pr["n_long"].mean()), "min": int(pr["n_long"].min()), "max": int(pr["n_long"].max()),
                       "weeks_by_size": {str(int(s_)): int((pr["n_long"] == s_).sum()) for s_ in np.unique(pr["n_long"])[::-1]}},
            "dropped_coin_weeks": dict(drops), "flagged_snapshots": dict(P.flagged), "flag_dropped_weeks": flag_dropped,
            "excluded": {P.symbol(c): dday for c, dday in sorted(excl_seen.items(), key=lambda z: z[1])},
            "trial_means": {"|".join(map(str, g)): float(r["excess"].mean()) for g, r in runs.items()}}


def b6c_cryptoxs_xs_momentum_weekly(archive):
    """T-314."""
    miss = _missing(archive, [CMC_W])
    if miss:
        return miss
    P = _cmc_weekly(archive)
    j = xs_momentum_weekly(P)
    if j.get("too_short"):
        return _too_short(j["n"], T314_MIN_N, "weeks", "weekly entries 2018-01..")
    xc = None
    if _has(archive, BTC_Y):                                    # optional cross-check: Yahoo BTC-USD Monday closes
        yb = _closes(archive, BTC_Y)
        cal = _weekly_calendar(P, T314_START)
        pairs = []
        for i in cal["weeks"]:
            a, b = P.dates[cal["mon"][i]], P.dates[cal["mon"][i + 1]]
            if a in yb and b in yb and P.price(BTC_ID, cal["mon"][i]) and P.price(BTC_ID, cal["mon"][i + 1]):
                pairs.append((P.price(BTC_ID, cal["mon"][i + 1]) / P.price(BTC_ID, cal["mon"][i]) - 1, yb[b] / yb[a] - 1))
        if len(pairs) > 10:
            pa = np.array(pairs)
            xc = {"n": len(pairs), "corr": float(np.corrcoef(pa[:, 0], pa[:, 1])[0, 1]), "mean_abs_diff": float(np.abs(pa[:, 0] - pa[:, 1]).mean())}
    wk = None
    if all(_has(archive, n) for n in CMC_D):                     # optional rule-10 robustness: every formation weekday
        D = _cmc_daily(archive)
        wk = {}
        for w in range(7):
            o = xs_momentum_weekly(D, weekday=w, light=True)
            if not o.get("too_short"):
                wk[("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[w]] = o
    mt, d = j["mean_test"], j["dsr"]
    cy = "; ".join(f"{k} {_pc(c['mean'], 2)} ({c['n']} weeks)" for k, c in j["cycles"].items())
    nl, dr = j["n_long"], j["dropped_coin_weeks"]
    sizes = ", ".join(f"{s_} names in {c_} weeks" for s_, c_ in nl["weeks_by_size"].items())
    lim = (f" Data limit: the weekly snapshots {_flag_txt(j['flagged_snapshots'])} fail the integrity screen and are treated "
           f"as missing, so the {len(j['flag_dropped_weeks'])} weeks that need them (entries {', '.join(j['flag_dropped_weeks'])}) "
           f"are dropped." if j["flagged_snapshots"] else "")
    dflag = sorted(D.flagged) if wk is not None else []
    reason = (f"Top-tertile 3-week momentum of the point-in-time top 30 coins by CMC market cap (Sunday snapshot, stablecoins, "
              f"wrapped/staked copies and gold tokens excluded by the declared list and the point-in-time peg screen: "
              f"{len(j['excluded'])} coins excluded at some point), long the top third (floor(n/3)) of the n top-30 coins with "
              f"a price 3 weeks earlier and at the Monday close, equal weight (book size mean {nl['mean']:.2f} names, min "
              f"{nl['min']}, max {nl['max']}: {sizes}; top-30 coin-weeks dropped for a missing formation price 3 weeks "
              f"earlier {dr['formation']}, for a missing Monday entry price {dr['entry']}), held one "
              f"week, {T314_COST * 1e4:.0f} bps per side on drift-adjusted turnover (mean turnover {j['mean_turnover']:.2f}/week, "
              f"cost {_pc(j['mean_cost'], 3)}/week), minus BTC (Monday to Monday): entries {j['labels'][0]}..{j['labels'][-1]} "
              f"({j['n']} weeks).{lim} Mean net excess {_pc(mt['est'], 3)}/week ({_ci_txt(mt['ci'], 3)}, gross {_pc(j['gross_excess_mean'], 3)}); "
              f"DSR {_f(d['dsr'])} over {T314_N_TRIALS} trials (trial-Sharpe var {d['var_trials_sr']:.2e}, {d['var_used']}); "
              f"permutation p {j['perm']['p']:.3f} (null 95th pct {_pc(j['perm']['q95'], 3)}). Reported: vanished-coin stress "
              f"(last price - 50% for a held coin absent from every later snapshot) {_pc(j['stress_mean'], 3)}/week; "
              f"{j['n_vanished']} held coin-weeks without an exit snapshot: {j['n_vanished_gone']} never seen again (marked "
              f"down in the stress), {j['n_vanished_returned']} fell below the depth and came back (last-price mark kept); "
              f"today's-top-30 universe {_pc(j['today_mean'], 3)}/week, survivorship inflation {_pc(j['survivorship_inflation'], 3)}/week; "
              f"per cycle {cy}"
              + (f"; Yahoo BTC-USD cross-check: weekly return correlation {xc['corr']:.4f} over {xc['n']} weeks" if xc else "")
              + (f"; rule-10 robustness on the daily snapshots, primary trial by formation weekday: "
                 + ", ".join(f"{k} {_pc(o['mean'], 3)} ({o['n']} weeks)" for k, o in wk.items())
                 + (f" (data limit: the daily snapshots {', '.join(dflag)} fail the integrity screen and are treated as missing; "
                    f"the weeks that need them are dropped)" if dflag else "") if wk else "")
              + " — " + j["why"])
    stat = {k: j[k] for k in ("n", "mean_test", "dsr", "family_sharpe_pp", "perm", "criteria", "mean_cost", "mean_turnover",
                              "gross_excess_mean", "btc_mean", "stress_mean", "today_top30", "today_mean", "survivorship_inflation",
                              "cycles", "n_vanished", "n_vanished_returned", "n_vanished_gone", "vanished_examples", "excluded",
                              "trial_means", "n_long", "dropped_coin_weeks", "flagged_snapshots", "flag_dropped_weeks")}
    stat.update(window=[j["labels"][0], j["labels"][-1]], primary=list(T314_PRIMARY), cost_side=T314_COST, yahoo_crosscheck=xc,
                by_formation_weekday=wk, daily_flagged_snapshots=dict(D.flagged) if wk is not None else None,
                rule10="named calendar: Sunday CMC snapshot, Monday close execution (library rule; trial 'trade t+1'); every "
                       "formation weekday on the daily snapshots reported")
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================ T-420 volume-conditioned momentum ==

T420_MIN_N = 200
T420_J = (3, 6, 12)
T420_K = (1, 3, 6)
T420_SIGNS = ("ls", "conf")
T420_KINDS = ("LS", "LO")
T420_CLAIM = ("etf", 6, 3, "ls", "LS")
T420_N_TRIALS = 72
T420_THR_Q = 0.01              # 1 percentage point per quarter
T420_PBO_MAX = 0.3
T420_ETF_COST = (0.0005, 0.0010)
T420_CRYPTO_COST = (0.0050, 0.0100)
T420_EVAL = ("2007-01", "2026-09")          # hold months
T420_IS = ("2007-01", "2016-12")
T420_OOS = ("2017-04", "2026-09")           # after the one-quarter embargo 2017-01..03
T420_ETF_COHORT0 = "2006-07"                # decisions from here so that K = 6 is full at the first hold month
T420_CRYPTO_DEC0 = "2018-12"                # first decision with every J and the 12-month turnover
T420_TOP = 20
T420_PEG_DAYS = 14
DEPTH_BAND = 400               # a volume top-20 member ranked below 400 by market cap sits near the depth-500 cut


def _mlabel_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _mrange(a: str, b: str) -> list:
    out, m = [], a
    while m <= b:
        out.append(m)
        m = _mlabel_add(m, 1)
    return out


def _turnover(sums: np.ndarray, cnts: np.ndarray, t: int, min3: int, min12: int, need_all: bool) -> np.ndarray:
    """Mean daily dollar volume over months t-2..t / over t-11..t, per asset (NaN when the history is too short)."""
    N = sums.shape[0]
    out = np.full(N, np.nan)
    if t < 11:
        return out
    s3, c3 = sums[:, t - 2:t + 1].sum(axis=1), cnts[:, t - 2:t + 1].sum(axis=1)
    s12, c12 = sums[:, t - 11:t + 1].sum(axis=1), cnts[:, t - 11:t + 1].sum(axis=1)
    ok = (c3 >= min3) & (c12 >= min12) & (s12 > 0)
    if need_all:
        ok &= (cnts[:, t - 11:t + 1] > 0).all(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[ok] = (s3[ok] / c3[ok]) / (s12[ok] / c12[ok])
    return out


def etf_panel(series: dict, bills: Bills, first: str = "2005-01", last: str = "2026-09") -> dict:
    """Monthly panel for T-420 from {sym: {days, close, adj, vol}}: decision month-end prices P, hold returns R (fill t
    -> fill t+1), turnover TURN at t, eligibility ELIG, bill return rf over each hold."""
    syms = list(series)
    PN = month_panel({s: (series[s]["days"], series[s]["adj"]) for s in syms}, first, last)
    labels = PN["labels"]
    pos = PN["pos"]
    N, T = len(syms), len(labels)
    sums, cnts = np.zeros((N, T)), np.zeros((N, T))
    for i, s in enumerate(syms):
        z = series[s]
        dv = np.asarray(z["close"], float) * np.where(np.isfinite(z["vol"]), z["vol"], 0.0)
        for d, x in zip(z["days"], dv):
            t = pos.get(d[:7])
            if t is not None:
                sums[i, t] += x
                cnts[i, t] += 1
    TURN = np.full((N, T), np.nan)
    for t in range(T):
        TURN[:, t] = _turnover(sums, cnts, t, 1, 1, True)
    R = PN["R_ex"]
    ELIG = np.isfinite(PN["PEX"]) & np.isfinite(PN["PME"]) & np.isfinite(R)
    rf = np.zeros(T)
    for t in range(T - 1):
        a, b = PN["ex_day"][t], PN["ex_day"][t + 1]
        rf[t] = bills.growth(a, b) - 1.0 if (a and b) else 0.0
    return {"labels": labels, "syms": syms, "P": PN["PME"], "R": R, "TURN": TURN, "ELIG": ELIG, "rf": rf}


def crypto_panel(C: CmcPanel, bills: Optional[Bills], first: str = "2017-11", last: str = "2026-09", top: int = T420_TOP,
                 peg_days: int = T420_PEG_DAYS) -> dict:
    """Monthly panel for T-420's crypto cells from the daily CMC snapshots: universe at month-end t = the top ``top``
    non-excluded coins by summed volume24h over the 30 days ending t; P = month-end price; R = last-price change from
    the fill day (t's month-end + 1) to the next fill day; TURN from monthly volume24h sums; depth diagnostic. A month
    whose last stored day fails the integrity screen takes its last intact day as the month-end (universe and P; the
    fill stays the day after the last stored day); flagged days are left out of the volume and peg windows."""
    labels = _mrange(first, last)
    me, fill = [None] * len(labels), [None] * len(labels)
    bad = C.flagged_idx
    by_month = defaultdict(list)
    for k, d in enumerate(C.dates):
        by_month[d[:7]].append(k)
    subst = {}
    for t, m in enumerate(labels):
        ks = by_month.get(m)
        if not ks:
            continue
        intact = [k for k in ks if k not in bad]
        if not intact:
            continue
        k = intact[-1]                      # the month's last intact day (a flagged last day is treated as missing)
        if k != ks[-1]:
            subst[m] = {"stored_last_day": C.dates[ks[-1]], "month_end_used": C.dates[k]}
        me[t] = k
        f = C.dpos.get(_day_add(C.dates[ks[-1]], 1))
        fill[t] = f if f not in bad else None
    uni, depth_hits, top_ranks = {}, [], []
    for t, k in enumerate(me):
        if k is None or fill[t] is None:
            continue
        d0 = C.dates[k]
        lo = _day_add(d0, -29)
        ks = [C.dpos[d] for d in _cal(lo, d0) if d in C.dpos and C.dpos[d] not in bad]
        if len(ks) < 20:
            continue
        agg = defaultdict(float)
        for kk in ks:
            ids, _, vol, _, _ = C.day(kk)
            for c, v in zip(ids.tolist(), vol.tolist()):
                agg[c] += v
        ids_k, _, _, rk_k, _ = C.day(k)
        rank_k = dict(zip(ids_k.tolist(), rk_k.tolist()))
        present = [c for c in rank_k]
        cand = sorted(present, key=lambda c: -agg.get(c, 0.0))[:top + 80]
        win = [C.dpos[d] for d in _cal(_day_add(d0, -(peg_days - 1)), d0) if d in C.dpos and C.dpos[d] not in bad]
        ex = _excluded_at(C, k, cand, win, min(10, len(win)))
        fm = C.price_map(fill[t])
        members = [c for c in cand if c not in ex and c in fm][:top]
        if len(members) < top:
            continue
        uni[t] = members
        deepest = max(rank_k[c] for c in members)
        depth_hits.append((labels[t], bool(deepest > DEPTH_BAND)))
        top_ranks.append(deepest)
    ids = sorted({c for v in uni.values() for c in v})
    ipos = {c: i for i, c in enumerate(ids)}
    N, T = len(ids), len(labels)
    P = np.full((N, T), np.nan)
    R = np.full((N, T), np.nan)
    ELIG = np.zeros((N, T), bool)
    for t in range(T):
        if me[t] is not None:
            pm = C.price_map(me[t])
            for c in ids:
                p = pm.get(c)
                if p is not None:
                    P[ipos[c], t] = p
        if t + 1 < T and fill[t] is not None and fill[t + 1] is not None:
            for c in ids:
                p0, _ = C.last_price(c, fill[t])
                p1, _ = C.last_price(c, fill[t + 1])
                if p0 is not None and p1 is not None:
                    R[ipos[c], t] = p1 / p0 - 1.0
        if t in uni and t + 1 < T and fill[t + 1] is not None:
            for c in uni[t]:
                ELIG[ipos[c], t] = True
    # monthly volume sums for the turnover proxy
    sums, cnts = np.zeros((N, T)), np.zeros((N, T))
    mpos = {m: t for t, m in enumerate(labels)}
    dmon = np.array([mpos.get(d[:7], -1) for d in C.dates], np.int64)
    sel = np.isin(C.cid, np.array(ids, np.int64)) if ids else np.zeros(C.cid.size, bool)
    if sel.any():
        ii = np.array([ipos[int(c)] for c in C.cid[sel]], np.int64)
        tt = dmon[C.di[sel]]
        okm = tt >= 0
        np.add.at(sums, (ii[okm], tt[okm]), C.vol[sel][okm])
        np.add.at(cnts, (ii[okm], tt[okm]), 1.0)
    TURN = np.full((N, T), np.nan)
    for t in range(T):
        TURN[:, t] = _turnover(sums, cnts, t, 20, 60, False)
    rf = np.zeros(T)
    for t in range(T - 1):
        if bills is not None and fill[t] is not None and fill[t + 1] is not None:
            rf[t] = bills.growth(C.dates[fill[t]], C.dates[fill[t + 1]]) - 1.0
    binds = [m for m, h in depth_hits if h]
    return {"labels": labels, "syms": [C.symbol(c) for c in ids], "P": P, "R": R, "TURN": TURN, "ELIG": ELIG, "rf": rf,
            "depth": {"months_checked": len(depth_hits), "months_binding": len(binds), "binding_examples": binds[:8],
                      "max_member_rank_median": float(np.median(top_ranks)) if top_ranks else None,
                      "max_member_rank_max": int(max(top_ranks)) if top_ranks else None},
            "n_universe_months": len(uni), "flagged_snapshots": dict(C.flagged), "substituted_month_ends": subst}


def cohort_weights(mom: np.ndarray, turn: np.ndarray, elig: np.ndarray, sign: Optional[str], kind: str) -> np.ndarray:
    """One cohort: momentum terciles (floor(n/3)); unconditioned (sign None) = winners minus losers; conditioned:
    within the winners the floor(k/3) lowest-turnover names long ('ls'; highest for 'conf'), within the losers the
    floor(k/3) highest-turnover names short ('ls'; lowest for 'conf'). 'LO' keeps the long leg only."""
    w = np.zeros(mom.size)
    idx = np.flatnonzero(elig & np.isfinite(mom) & np.isfinite(turn))
    k = idx.size // 3
    if k < (3 if sign else 1):
        return w
    o = idx[np.argsort(-mom[idx], kind="stable")]
    win, los = o[:k], o[-k:]
    if sign is None:
        lg, sh = win, los
    else:
        s = k // 3
        wt = win[np.argsort(turn[win], kind="stable")]
        lt = los[np.argsort(turn[los], kind="stable")]
        lg, sh = (wt[:s], lt[-s:]) if sign == "ls" else (wt[-s:], lt[:s])
    w[lg] = 1.0 / lg.size
    if kind == "LS":
        w[sh] = -1.0 / sh.size
    return w


def cohort_weights_indep(mom, turn, elig, sign, kind) -> np.ndarray:
    """Independent 3 x 3 sort (Lee-Swaminathan's construction): winners and losers by momentum terciles, low and high
    turnover by turnover terciles of the whole cross-section; reported as a sensitivity."""
    w = np.zeros(mom.size)
    idx = np.flatnonzero(elig & np.isfinite(mom) & np.isfinite(turn))
    k = idx.size // 3
    if k < 3:
        return w
    om = idx[np.argsort(-mom[idx], kind="stable")]
    ot = idx[np.argsort(turn[idx], kind="stable")]
    win, los, low, high = set(om[:k]), set(om[-k:]), set(ot[:k]), set(ot[-k:])
    lg = sorted(win & (low if sign == "ls" else high))
    sh = sorted(los & (high if sign == "ls" else low))
    if not lg or (kind == "LS" and not sh):
        return w
    w[lg] = 1.0 / len(lg)
    if kind == "LS":
        w[sh] = -1.0 / len(sh)
    return w


def run_cell(PNL: dict, J: int, K: int, sign: Optional[str], kind: str, cost: float, dec0: int, dec1: int,
             weights: Callable = cohort_weights) -> dict:
    """Overlapping-cohort book of one cell on decisions dec0..dec1 (cohorts from dec0): net (LS) or excess (LO) returns
    of the holds of decisions dec0..dec1; hold-month labels."""
    P, R, TURN, ELIG, rf = PNL["P"], PNL["R"], PNL["TURN"], PNL["ELIG"], PNL["rf"]
    N = P.shape[0]
    ts = list(range(dec0, dec1 + 1))
    C = np.zeros((len(ts), N))
    for r_, t in enumerate(ts):
        if t - 1 - J < 0:
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            mom = P[:, t - 1] / P[:, t - 1 - J] - 1.0
        C[r_] = weights(mom, TURN[:, t], ELIG[:, t], sign, kind)
    W = overlap(C, K, 0)
    Rh = R[:, ts].T.copy()
    bad = (W != 0) & ~np.isfinite(Rh)
    n_bad = int(bad.sum())
    Rh[bad] = 0.0
    costv = np.full(N, cost)
    if kind == "LS":
        b = book(W, Rh, costv)
        own = b["net"]
    else:
        b = book(W, Rh, costv, rf=rf[ts])
        own = b["net"] - rf[ts]
    hold = [_mlabel_add(PNL["labels"][t], 1) for t in ts]
    return {"own": own, "labels": hold, "n_bad": n_bad, "names": (np.abs(C) > 0).sum(axis=1)}


def _sub(series: np.ndarray, labels: Sequence[str], a: str, b: str) -> np.ndarray:
    m = np.array([a <= l <= b for l in labels], bool)
    return series[m]


def _pbo_of(cols: Sequence[np.ndarray]) -> Optional[dict]:
    L = min(c.size for c in cols)
    if L < 2 * PBO_PARTS or len(cols) < 2:
        return None
    return pbo_cscv(np.column_stack([np.asarray(c, float)[-L:] for c in cols]), n_partitions=PBO_PARTS)


def volume_momentum(etf: dict, crypto: Optional[dict], min_n: int = T420_MIN_N, n_trials: int = T420_N_TRIALS,
                    etf_cost: tuple = T420_ETF_COST, crypto_cost: tuple = T420_CRYPTO_COST, eval_win: tuple = T420_EVAL,
                    is_win: tuple = T420_IS, oos_win: tuple = T420_OOS, cohort0: str = T420_ETF_COHORT0,
                    crypto_dec0: str = T420_CRYPTO_DEC0) -> dict:
    """T-420 core over an ETF monthly panel and (optionally) a crypto monthly panel."""
    lab = etf["labels"]
    lp = {m: t for t, m in enumerate(lab)}
    e_dec0 = lp.get(cohort0, 0)
    e_first = lp.get(_mlabel_add(eval_win[0], -1))
    e_last = lp.get(_mlabel_add(eval_win[1], -1))
    if e_first is None or e_last is None:
        return {"too_short": True, "n": 0}
    cells = [(J, K, s, kd) for J in T420_J for K in T420_K for s in T420_SIGNS for kd in T420_KINDS]
    have_c = crypto is not None and crypto.get("n_universe_months", 0) >= 24
    if have_c:
        clp = {m: t for t, m in enumerate(crypto["labels"])}
        c_dec0 = clp.get(crypto_dec0)
        c_last = clp.get(_mlabel_add(eval_win[1], -1))
        have_c = c_dec0 is not None and c_last is not None and c_last - c_dec0 >= 24
    out = {}
    for ci_, (ce, cc) in enumerate(zip(etf_cost, crypto_cost)):
        res = {}
        base = {}
        for (J, K, s, kd) in cells:
            for uni in (("etf",) + (("crypto",) if have_c else ())):
                if uni == "etf":
                    r = run_cell(etf, J, K, s, kd, ce, e_dec0, e_last)
                    if (J, K, kd, uni) not in base:
                        base[(J, K, kd, uni)] = run_cell(etf, J, K, None, kd, ce, e_dec0, e_last)
                    keep = lambda z: _sub(z, r["labels"], eval_win[0], eval_win[1])
                else:
                    r = run_cell(crypto, J, K, s, kd, cc, c_dec0, c_last)
                    if (J, K, kd, uni) not in base:
                        base[(J, K, kd, uni)] = run_cell(crypto, J, K, None, kd, cc, c_dec0, c_last)
                    keep = lambda z: _sub(z, r["labels"], "0000", eval_win[1])
                b = base[(J, K, kd, uni)]
                labs = [l for l in r["labels"] if (eval_win[0] <= l <= eval_win[1]) or uni == "crypto"]
                own, bo = keep(r["own"]), keep(b["own"])
                res[(uni, J, K, s, kd)] = {"own": own, "diff": own - bo, "base": bo, "labels": labs, "n_bad": r["n_bad"] + b["n_bad"]}
        out[ci_] = res
    claim = T420_CLAIM
    lab_e = out[0][claim]["labels"]
    n = len(lab_e)
    rows_oos, rows_dsr, rows_pbo, info = [], [], [], {}
    depth_binds = bool(have_c and crypto.get("depth", {}).get("months_binding", 0) > 0)
    use_c = have_c and not depth_binds
    for ci_, nm in ((0, "low cost"), (1, "high cost")):
        res = out[ci_]
        cl = res[claim]
        K = claim[2]
        x_oos = _sub(cl["diff"], cl["labels"], *oos_win)
        h = hac_mean_lag(x_oos, max(nw_lag(x_oos.size), 2 * K))
        q = 3 * h["mean"]
        ub = 3 * (h["mean"] + _Z95 * h["se"]) if h["se"] else None
        rows_oos.append((f"{nm}: {_pc(q, 2)}/quarter (3 x {_pc(h['mean'], 3)}/month), HAC t {_s(h['t'], 2)}, p {_f(h['p'], 4)}, "
                         f"Newey-West lag {h['lag']}, {h['n']} months",
                         bool(q >= T420_THR_Q and h["p"] is not None and h["p"] < ALPHA), bool(ub is not None and ub < T420_THR_Q)))
        info[nm] = {"oos": h, "oos_quarterly": q, "full_quarterly": 3 * float(cl["diff"].mean()),
                    "is_quarterly": 3 * float(_sub(cl["diff"], cl["labels"], *is_win).mean())}
        for ser in ("diff", "own"):
            for win_nm, (a, b) in (("2007-2026", eval_win), ("out-of-sample", oos_win)):
                x = _sub(cl[ser], cl["labels"], a, b)
                fam_e = [_sr_pp(_sub(v[ser], v["labels"], a, b)) for k, v in res.items() if k[0] == "etf"]
                fam_c = [_sr_pp(_sub(v[ser], v["labels"], a, b)) for k, v in res.items() if k[0] == "crypto"]
                label = f"{nm}, {'difference' if ser == 'diff' else 'own long-short'} series, {win_nm}"
                if use_c:
                    dd = family_dsr(x, fam_e + fam_c, n_trials)
                    nm_, ok, dec = dsr_row(dd, label)
                    ok = None if dd.get("dsr") is None else bool(dd["dsr"] >= DSR_PASS)
                    rows_dsr.append((nm_, ok, dec))
                    info.setdefault("dsr", {})[label] = dd
                else:
                    row, inf = dsr_bound(x, fam_e, n_trials, label)
                    if depth_binds:
                        row = (row[0].replace(f"need {CMC_NAME}, not archived",
                                              "are not used: the depth-500 market-cap snapshots can cut the volume top 20"),
                               row[1], row[2])
                    rows_dsr.append(row)
                    info.setdefault("dsr", {})[label] = inf
        for ser in ("own", "diff"):
            cols_e = [v[ser] for k, v in res.items() if k[0] == "etf"]
            pe = _pbo_of(cols_e)
            rows_pbo.append((f"{nm}, {ser} series, 36 ETF cells 2007-2026: PBO {_f(pe['pbo'] if pe else None)}",
                             None if pe is None else bool(pe["pbo"] < T420_PBO_MAX), False))
            info.setdefault("pbo", {})[f"{nm}|{ser}|etf36"] = pe
            if have_c:
                cm = [v for k, v in res.items() if k[0] == "crypto"]
                first_c = max(v["labels"][0] for v in cm)
                cols_all = [_sub(v[ser], v["labels"], first_c, eval_win[1]) for v in res.values()]
                pa = _pbo_of(cols_all)
                info["pbo"][f"{nm}|{ser}|all72"] = pa
                if use_c:
                    rows_pbo.append((f"{nm}, {ser} series, all 72 cells {first_c}..{eval_win[1]}: PBO {_f(pa['pbo'] if pa else None)}",
                                     None if pa is None else bool(pa["pbo"] < T420_PBO_MAX), False))
                else:
                    rows_pbo.append((f"{nm}, {ser} series, all 72 cells: PBO {_f(pa['pbo'] if pa else None)} computed but not used (the "
                                     f"depth-500 market-cap snapshots can cut the crypto volume top 20)", None, False))
            else:
                rows_pbo.append((f"{nm}, {ser} series, all 72 cells: the 36 crypto cells need cmc-daily-listings-<YYYY>", None, False))
    crit = [all_constructions(rows_oos, f"out-of-sample ({oos_win[0]}..{oos_win[1]}) spread difference >= 1 point a quarter with HAC "
                                        f"p < 0.05, at both cost ends"),
            all_constructions(rows_dsr, f"DSR >= {DSR_PASS} over the {n_trials} declared cells (every reading)"),
            all_constructions(rows_pbo, f"PBO < {T420_PBO_MAX} (CSCV, {PBO_PARTS} partitions; every reading)")]
    v, why = _decide(crit, n, min_n, "monthly observations")
    # reported: in-sample selection among the ETF cells (difference Sharpe, low cost), crash years, independent sort
    res0 = out[0]
    is_sh = {k: _sr_pp(_sub(r["diff"], r["labels"], *is_win)) for k, r in res0.items() if k[0] == "etf"}
    sel = max(is_sh, key=lambda k: is_sh[k] if is_sh[k] is not None else -1e9)
    sel_oos = 3 * float(_sub(res0[sel]["diff"], res0[sel]["labels"], *oos_win).mean())
    cl0 = res0[claim]
    yrs = {y: 3 * float(_sub(cl0["diff"], cl0["labels"], f"{y}-01", f"{y}-12").mean()) for y in ("2009", "2020")}
    ind = run_cell(etf, 6, 3, "ls", "LS", etf_cost[0], e_dec0, e_last, weights=cohort_weights_indep)
    indb = run_cell(etf, 6, 3, None, "LS", etf_cost[0], e_dec0, e_last)
    ind_d = _sub(ind["own"] - indb["own"], ind["labels"], *oos_win)
    names = res0[claim]
    return {"n": n, "labels": lab_e, "info": info, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why,
            "selected_is": "|".join(map(str, sel)), "selected_is_oos_quarterly": sel_oos, "is_sharpe_selected": is_sh[sel],
            "claim_is_rank": sorted(is_sh, key=lambda k: -(is_sh[k] or -1e9)).index(claim) + 1, "crash_years_quarterly": yrs,
            "indep_sort_oos_quarterly": 3 * float(ind_d.mean()) if ind_d.size else None, "have_crypto": have_c,
            "depth_binds": depth_binds, "depth": crypto.get("depth") if crypto else None,
            "crypto_window": [max(v["labels"][0] for k, v in res0.items() if k[0] == "crypto"), eval_win[1]] if have_c else None,
            "n_bad_returns": int(sum(r["n_bad"] for r in res0.values())), "claim_full_quarterly": 3 * float(cl0["diff"].mean()),
            "claim_base_full_quarterly": 3 * float(cl0["base"].mean()), "claim_own_full_quarterly": 3 * float(cl0["own"].mean())}


def b6c_cryptoxs_volume_conditioned_momentum(archive):
    """T-420."""
    need = [dh(s) for s in U68] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    etf = _cached(archive, ("t420etf",), lambda: etf_panel({s: _yahoo(archive, dh(s)) for s in U68}, bills))
    cmc_ok = all(_has(archive, n) for n in CMC_D)
    crypto = _cached(archive, ("t420cr",), lambda: crypto_panel(_cmc_daily(archive), bills)) if cmc_ok else None
    j = volume_momentum(etf, crypto)
    if j.get("too_short"):
        return _too_short(j["n"], T420_MIN_N, "monthly observations", "hold months 2007-01..2026-09")
    lo, hi = j["info"]["low cost"], j["info"]["high cost"]
    dep = j.get("depth") or {}
    dtxt = (f"crypto universe: CMC daily snapshots (depth 500 by market cap), top 20 by trailing 30-day volume24h after the "
            f"declared exclusions and the peg screen, hold months {j['crypto_window'][0]}..{j['crypto_window'][1]}; median "
            f"deepest member rank {_f(dep.get('max_member_rank_median'), 0)} (max {dep.get('max_member_rank_max')}); a member "
            f"ranked 401-500 by market cap in {dep.get('months_binding')} of {dep.get('months_checked')} months"
            + (" (the depth binds: crypto-dependent family readings are treated as unknown)" if j["depth_binds"] else " (the depth does not bind)")
            + (f"; data limit: the daily snapshots {_flag_txt(crypto['flagged_snapshots'])} fail the integrity screen and are "
               f"treated as missing" + ("; month-end substituted: " + ", ".join(
                   f"{m_} {v_['month_end_used']} for {v_['stored_last_day']}" for m_, v_ in sorted(crypto["substituted_month_ends"].items()))
                   if crypto["substituted_month_ends"] else "") if crypto.get("flagged_snapshots") else "")
            if j["have_crypto"] else "the 36 crypto cells need the cmc-daily-listings-<YYYY> bundles")
    dsr_vals = [(k, (x.get("dsr") if isinstance(x, dict) and "dsr" in x else x.get("dsr_upper_bound"))) for k, x in j["info"].get("dsr", {}).items()]
    pbo_vals = [(k, (x or {}).get("pbo")) for k, x in j["info"].get("pbo", {}).items()]
    reason = (f"Declared 68-ETF list (the T-420/T-462 list of batch6c_xs.U68; survivor-drawn), month-end decisions filled at the "
              f"next session's close, 6-month momentum skipping the decision month, turnover = 3-month / 12-month mean daily "
              f"dollar volume, sequential tercile sorts, 3-month overlapping cohorts, {T420_ETF_COST[0] * 1e4:.0f} and "
              f"{T420_ETF_COST[1] * 1e4:.0f} bps per leg: hold months {j['labels'][0]}..{j['labels'][-1]} ({j['n']} months). "
              f"Low-turnover-conditioned minus unconditioned spread: full sample {_pc(j['claim_full_quarterly'], 2)}/quarter "
              f"(conditioned {_pc(j['claim_own_full_quarterly'], 2)}, unconditioned {_pc(j['claim_base_full_quarterly'], 2)}); "
              f"2007-2016 {_pc(lo['is_quarterly'], 2)}; out of sample {_pc(lo['oos_quarterly'], 2)}/quarter at low cost (HAC t "
              f"{_s(lo['oos']['t'], 2)}, p {_f(lo['oos']['p'], 4)}) and {_pc(hi['oos_quarterly'], 2)} at high cost (t "
              f"{_s(hi['oos']['t'], 2)}, p {_f(hi['oos']['p'], 4)}). DSR readings: "
              + "; ".join(f"{k} {_f(v)}" for k, v in dsr_vals)
              + ". PBO readings: " + "; ".join(f"{k} {_f(v)}" for k, v in pbo_vals)
              + f". {dtxt}. Reported: the 2007-2016 selection among the 36 ETF cells picks {j['selected_is']} (claim cell ranked "
              f"{j['claim_is_rank']}), whose out-of-sample difference is {_pc(j['selected_is_oos_quarterly'], 2)}/quarter; "
              f"independent 3 x 3 sort out of sample {_pc(j['indep_sort_oos_quarterly'], 2)}/quarter; 2009 "
              f"{_pc(j['crash_years_quarterly']['2009'], 2)}, 2020 {_pc(j['crash_years_quarterly']['2020'], 2)}/quarter — " + j["why"])
    stat = {"n_months": j["n"], "window": [j["labels"][0], j["labels"][-1]], "info": j["info"], "criteria": j["criteria"],
            "selected_is": j["selected_is"], "selected_is_oos_quarterly": j["selected_is_oos_quarterly"], "claim_is_rank": j["claim_is_rank"],
            "crash_years_quarterly": j["crash_years_quarterly"], "indep_sort_oos_quarterly": j["indep_sort_oos_quarterly"],
            "have_crypto": j["have_crypto"], "depth_binds": j["depth_binds"], "depth": j["depth"], "crypto_window": j["crypto_window"],
            "crypto_flagged_snapshots": crypto.get("flagged_snapshots") if crypto else None,
            "crypto_substituted_month_ends": crypto.get("substituted_month_ends") if crypto else None,
            "claim_full_quarterly": j["claim_full_quarterly"], "n_bad_returns": j["n_bad_returns"], "universe": list(U68),
            "cells": "J 3/6/12 x K 1/3/6 x sign ls/conf x long-short/long-only x ETF/crypto = 72",
            "rule10": "month-end decisions (named monthly J-month momentum); overlapping K-month cohorts (pooled all-start)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================================ T-400 MVRV ==

T400_MIN_N = 4                 # distinct episodes
T400_START = "2011-01-01"
T400_H = 90
T400_LO, T400_HI = 1.0, 3.0
T400_MERGES = (30, 90)
T400_COSTS = (0.0010, 0.0060)
T400_MIN_HOLD = 7
T400_BAND = (0.9, 1.1)         # assumed restatement band on the current-vintage MVRV (x 0.9, x 1.1)
HALVINGS = ("2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20")
T400_TEST = {"cycles after the 2012 halving (3-4 = 2020-05-11..)": ("2020-05-11", "9999-12-31"),
             "cycles from genesis (3-4 = 2016-07-09..2024-04-19)": ("2016-07-09", "2024-04-19")}


def mvrv_rule(sig: np.ndarray, r: np.ndarray, b: np.ndarray, lo: float, hi: float, cost: float,
              min_hold: int = T400_MIN_HOLD) -> tuple:
    """(daily returns, target BTC share) of the 100/50/0% rule: target from the signal known at close t (sig[t] =
    MVRV of day t-1, or its z), rebalanced at close t only on a regime switch and at least ``min_hold`` days after the
    last one; r[t], b[t] = BTC and bill returns over day t+1 (close t -> close t+1). Between switches the BTC share
    drifts. Entering the first target from cash costs cost x target."""
    n = sig.size
    out, tg = np.zeros(n), np.zeros(n)
    f = tgt = None
    last = -10 ** 9
    for t in range(n):
        s = sig[t]
        want = tgt
        if np.isfinite(s):
            want = 1.0 if s < lo else (0.0 if s > hi else 0.5)
        if want is None:
            want = 0.5
        c = 0.0
        if tgt is None:
            f, tgt, last = want, want, t
            c = cost * want
        elif want != tgt and t - last >= min_hold:
            c = cost * abs(want - f)
            f, tgt, last = want, want, t
        R = f * r[t] + (1.0 - f) * b[t]
        out[t] = (1.0 - c) * (1.0 + R) - 1.0
        tg[t] = tgt
        den = 1.0 + R if abs(1.0 + R) > 1e-12 else 1e-12
        f = f * (1.0 + r[t]) / den
    return out, tg


def mvrv_regime(mvrv: dict, price: dict, bills: Optional[Bills], start: str = T400_START, horizon: int = T400_H,
                lo: float = T400_LO, hi: float = T400_HI, min_n: int = T400_MIN_N, pit: bool = False,
                test_windows: dict = T400_TEST, costs: tuple = T400_COSTS, variants: bool = True,
                band: tuple = T400_BAND) -> dict:
    """T-400 core: {day: MVRV}, {day: close}. ``pit``: whether the MVRV series is point in time (vintage-stamped). Coin
    Metrics serves only the current vintage, so the harness passes False: the vintage criterion is then None, and the
    difference and rule criteria are also judged with the series scaled by each factor of ``band`` (an assumed
    restatement band): each passes only when every scaling passes, fails only when every scaling fails (rule 11's
    logic), else it is undecided."""
    days_p = sorted(price)
    if not days_p:
        return {"too_short": True, "n": 0}
    last = days_p[-1]
    cal = _cal(_day_add(start, -400), last)
    P = np.array([price.get(d, np.nan) for d in cal], float)
    Mv = np.array([mvrv.get(_day_add(d, -1), np.nan) for d in cal], float)      # signal at t = MVRV(t-1)
    ix0 = cal.index(start)
    T = len(cal)
    y = np.full(T, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        y[:T - horizon] = np.log(P[horizon:] / P[:T - horizon])
    samp = np.zeros(T, bool)
    samp[ix0:] = True
    samp &= np.isfinite(y) & np.isfinite(Mv)
    ii = np.flatnonzero(samp)
    if ii.size < 365:
        return {"too_short": True, "n": 0}
    a0, a1 = int(ii[0]), int(ii[-1])
    yy, ss = y[a0:a1 + 1], Mv[a0:a1 + 1]
    ok = np.isfinite(yy) & np.isfinite(ss)
    lab = cal[a0:a1 + 1]
    yz = np.where(ok, yy, 0.0)
    scales = (1.0,) if pit else (1.0,) + tuple(band)
    reg, rows_d = {}, []
    for sc in scales:
        low, high = ok & (ss * sc < lo), ok & (ss * sc > hi)
        eps = {g: (spells(low, g), spells(high, g)) for g in T400_MERGES}
        t = diff_test(yz, low, high, block=horizon)
        reg[sc] = {"low": low, "high": high, "eps": eps, "cnt": {g: (len(a), len(b)) for g, (a, b) in eps.items()}, "test": t,
                   "est": float(yy[low].mean() - yy[high].mean()) if low.any() and high.any() else None}
        nm = "current vintage" if sc == 1.0 else f"MVRV x {sc:g}"
        rows_d.append(_ci_crit(t, "gt", 0.0, f"{nm} {_s(reg[sc]['est'])}", fmt=lambda v: _s(v, 3)))
    R0 = reg[1.0]
    low, high, eps, cnt = R0["low"], R0["high"], R0["eps"], R0["cnt"]
    n = min(min(v) for v in cnt.values())
    lbl = (f"mean forward {horizon}-day log return (MVRV < {lo:g}) - (MVRV > {hi:g}) > 0 with the 95% CI excluding 0 (CBB of the "
           f"daily timeline, {horizon}-day blocks)")
    crit = [all_constructions(rows_d, lbl + ("" if pit else "; every scaling of the restatement band")) if len(rows_d) > 1
            else (lbl + " " + rows_d[0][0], rows_d[0][1], rows_d[0][2])]
    crit.append((f">= 4 distinct episodes of each regime (gaps <= 30 days merged: {cnt[30][0]} low / {cnt[30][1]} high; <= 90 days: "
                 f"{cnt[90][0]} / {cnt[90][1]})", True if n >= 4 else None, False))
    # the rule vs buy-and-hold in the held-out cycles
    r = np.full(T, np.nan)
    r[:-1] = P[1:] / P[:-1] - 1.0
    b = np.zeros(T)
    if bills is not None:
        for k in range(T - 1):
            b[k] = bills.growth(cal[k], cal[k + 1]) - 1.0
    fin = np.isfinite(r) & np.isfinite(P)
    r0 = np.where(fin, r, 0.0)
    k0 = int(np.flatnonzero(np.isfinite(P) & np.isfinite(Mv))[0])
    labs = cal[k0:]
    ex_bh = r0[k0:] - b[k0:]
    rule_rows, held = [], {}
    for sc in scales:
        for c in costs:
            rr, tg = mvrv_rule(Mv[k0:] * sc, r0[k0:], b[k0:], lo, hi, c)
            ex_rule = rr - b[k0:]
            for wn, (wa, wb) in test_windows.items():
                m = np.array([(wa <= l <= wb) for l in labs]) & fin[k0:]
                nm = f"{'current vintage' if sc == 1.0 else f'MVRV x {sc:g}'}, {c * 1e4:.0f} bps, {wn}"
                if m.sum() < 60:
                    rule_rows.append((f"{nm}: too few days", None, False))
                    continue
                sr_r, sr_b = sharpe_ratio(ex_rule[m], 365), sharpe_ratio(ex_bh[m], 365)
                per = {}
                for ci, (ca, cb) in enumerate(zip(("0000",) + HALVINGS, HALVINGS + ("9999",))):
                    mm = np.array([(ca <= l < cb) for l in labs]) & m
                    if mm.sum() > 60:
                        per[f"epoch {ci}"] = float(sharpe_ratio(ex_rule[mm], 365) - sharpe_ratio(ex_bh[mm], 365))
                h = {"sr_rule": float(sr_r), "sr_bh": float(sr_b), "diff": float(sr_r - sr_b), "per_epoch": per,
                     "share_days_at": {str(x): float(np.mean(tg[m] == x)) for x in (0.0, 0.5, 1.0)}}
                if sc == 1.0 and c == costs[0]:
                    sd = sharpe_diff_test(ex_rule[m], ex_bh[m], 365, horizon, min(N_BOOT, 2000), SEED)
                    h["ci"] = sd["ci"]
                held[nm] = h
                rule_rows.append((f"{nm}: Sharpe {sr_r:.3f} vs {sr_b:.3f} ({sr_r - sr_b:+.3f})", bool(sr_r - sr_b > 0), False))
    crit.append(all_constructions(rule_rows, "the 100/50/0% rule beats buy-and-hold Sharpe (excess returns) in the held-out cycles "
                                             "(both cost ends, both cycle numberings" + ("" if pit else ", every scaling") + ")"))
    crit.append(("MVRV point in time (the controls' stored Coin Metrics vintage): " + ("vintage-stamped series supplied" if pit else
                 "Coin Metrics serves only the current vintage (realised cap can be restated), so what was known at each "
                 "decision cannot be reconstructed"), True if pit else None, False))
    v, why = _decide(crit, n, min_n, "distinct episodes (the smaller of the low/high counts, gaps <= 90 days merged)")
    rg = ss[low | high]
    near = float(np.mean(np.where(rg < lo, np.abs(rg / lo - 1), np.abs(rg / hi - 1)) < 0.05)) if rg.size else None
    first_hi = eps[30][1][0] if eps[30][1] else None
    wo = None
    if first_hi is not None and first_hi[0] == 0:                     # the spell touching the window start (thin market)
        hh = high.copy()
        hh[first_hi[0]:first_hi[1] + 1] = False
        wo = {"est": float(yy[low].mean() - yy[hh].mean()) if hh.any() and low.any() else None,
              "episodes_high_30": len(spells(hh, 30)), "episodes_high_90": len(spells(hh, 90)),
              "spell": [lab[first_hi[0]], lab[first_hi[1]]]}
    var = {}
    if variants:
        z = np.full(T, np.nan)
        for k in range(365, T):
            w = Mv[k - 364:k + 1]
            w = w[np.isfinite(w)]
            if w.size > 300 and w.std() > 0:
                z[k] = (Mv[k] - w.mean()) / w.std()
        zz = z[a0:a1 + 1]
        for nm, (aa, bb) in {"NUPL < 0 vs NUPL > 0.75 (MVRV < 1 vs > 4)": (ok & (ss < 1.0), ok & (ss > 4.0)),
                             "MVRV z-score (365-day) < -2 vs > +2": (ok & (zz < -2), ok & (zz > 2))}.items():
            var[nm] = {"est": float(yy[aa].mean() - yy[bb].mean()) if aa.any() and bb.any() else None,
                       "episodes_90": [len(spells(aa, 90)), len(spells(bb, 90))]}
        sr = {}
        for nm, (sg, l_, h_) in {"MVRV 1/3": (Mv, lo, hi), "NUPL 0/0.75": (Mv, 1.0, 4.0), "z +-2": (z, -2.0, 2.0)}.items():
            sr[nm] = mvrv_rule(sg[k0:], r0[k0:], b[k0:], l_, h_, costs[0])[0] - b[k0:]
        L = min(x.size for x in sr.values())
        var["rule_sharpes_ann"] = {k: float(sharpe_ratio(x[-L:], 365)) for k, x in sr.items()}
        vs = max(float(np.var([sharpe_ratio(x[-L:]) for x in sr.values()], ddof=1)), 1.0 / (L - 1))
        var["dsr_primary_rule_4_trials"] = float(deflated_sharpe_ratio(sr["MVRV 1/3"][-L:], n_trials=4, var_trials_sr=vs))
        pb = _pbo_of([x[-L:] for x in sr.values()])
        var["pbo_rule_variants"] = pb["pbo"] if pb else None
    band_rep = {f"x{sc:g}": {"est": reg[sc]["est"], "ci": reg[sc]["test"].get("ci"), "episodes": reg[sc]["cnt"]} for sc in scales}
    return {"n": int(n), "labels": [lab[0], lab[-1]], "n_days": int(ok.sum()), "est": R0["est"], "test": R0["test"],
            "n_low_days": int(low.sum()), "n_high_days": int(high.sum()), "mean_low": float(yy[low].mean()) if low.any() else None,
            "mean_high": float(yy[high].mean()) if high.any() else None, "episodes": cnt, "band": band_rep,
            "episode_dates": {str(g): {"low": [[lab[a], lab[b_]] for a, b_ in eps[g][0]], "high": [[lab[a], lab[b_]] for a, b_ in eps[g][1]]} for g in eps},
            "held_out": held, "near_threshold_share": near, "without_first_high_spell": wo, "variants": var,
            "park_triggered": bool(n < 4), "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_cryptoxs_mvrv_regime(archive):
    """T-400."""
    miss = _missing(archive, [cm_b("btc"), BTC_Y, DTB3_B])
    if miss:
        return miss
    cm = _cm(archive, "btc")
    price = splice_price(_metric(cm, "PriceUSD"), _closes(archive, BTC_Y), "2014-09-17")
    j = mvrv_regime(_metric(cm, "CapMVRVCur"), price, _bills(archive), pit=False)
    if j.get("too_short"):
        return _too_short(j["n"], T400_MIN_N, "distinct episodes", "MVRV regime days 2011..")
    eth = None
    if _has(archive, cm_b("eth")) and _has(archive, ETH_Y):              # optional ETH variant (reported)
        ce = _cm(archive, "eth")
        pe = splice_price(_metric(ce, "PriceUSD"), _closes(archive, ETH_Y), "2017-11-09")
        je = mvrv_regime(_metric(ce, "CapMVRVCur"), pe, None, start="2016-01-01", pit=True, variants=False)
        if not je.get("too_short"):
            eth = {"est": je["est"], "ci": je["test"].get("ci"), "episodes": je["episodes"], "window": je["labels"]}
    t = j["test"]
    ho = "; ".join(f"{k}: {x['sr_rule']:.3f} vs {x['sr_bh']:.3f}" for k, x in j["held_out"].items() if k.startswith("current"))
    bd = "; ".join(f"{k}: {_s(x['est'])} ({_ci_txt(x['ci'], 3, 1.0, '')}), episodes {x['episodes'][30]}/{x['episodes'][90]}"
                   for k, x in j["band"].items() if k != "x1")
    wo = j["without_first_high_spell"]
    var = j["variants"]
    first_ho = next((x for k, x in j["held_out"].items() if k.startswith("current")), None)
    reason = (f"BTC (Coin Metrics PriceUSD to 2014-09-16, Yahoo BTC-USD from 2014-09-17), signal MVRV of day t-1 (CapMVRVCur, "
              f"current vintage), forward {T400_H}-day log return from close t, days {j['labels'][0]}..{j['labels'][1]} "
              f"({j['n_days']} days): MVRV < 1 on {j['n_low_days']} days (mean {_s(j['mean_low'])}), MVRV > 3 on "
              f"{j['n_high_days']} days (mean {_s(j['mean_high'])}); difference {_s(j['est'])} ({_ci_txt(t.get('ci'), 3, 1.0, '')}, "
              f"{t.get('reps')} seeds); restatement band {bd}. Episodes (low/high): gaps <= 30 days {j['episodes'][30][0]}/"
              f"{j['episodes'][30][1]}, <= 90 days {j['episodes'][90][0]}/{j['episodes'][90][1]}; the pre-registered park rule "
              f"('insufficient independent episodes, parked, revisit each cycle') "
              + ("IS triggered" if j["park_triggered"] else "does not trigger (>= 4 of each under both merges)")
              + f". Rule vs buy-and-hold excess-return Sharpe in the held-out cycles (current vintage; cost, numbering): {ho}"
              + (f" (share of held-out days at 0/50/100%: {', '.join(f'{v_ * 100:.0f}%' for v_ in first_ho['share_days_at'].values())})" if first_ho else "")
              + f". {_f(None if j['near_threshold_share'] is None else j['near_threshold_share'] * 100, 1)}% of regime days lie "
              f"within 5% of a threshold. "
              + (f"Without the first MVRV > 3 spell ({wo['spell'][0]}..{wo['spell'][1]}, thin market): difference {_s(wo['est'])}, "
                 f"{wo['episodes_high_30']}/{wo['episodes_high_90']} high episodes (30/90-day merge). " if wo else "")
              + "Variants (reported): " + "; ".join(f"{k} {_s(x['est'])} (episodes {x['episodes_90']})" for k, x in var.items() if isinstance(x, dict) and "est" in x)
              + (f"; rule Sharpes {', '.join(f'{k} {s:.3f}' for k, s in var['rule_sharpes_ann'].items())}, DSR of the 1/3 rule over 4 "
                 f"trials {_f(var['dsr_primary_rule_4_trials'])}, PBO {_f(var['pbo_rule_variants'])}" if "rule_sharpes_ann" in var else "")
              + (f"; ETH MVRV 1/3 difference {_s(eth['est'])} (episodes {eth['episodes']})" if eth else "")
              + " — " + j["why"])
    stat = {k: j[k] for k in ("n", "labels", "n_days", "est", "test", "n_low_days", "n_high_days", "mean_low", "mean_high", "episodes",
                              "band", "episode_dates", "held_out", "near_threshold_share", "without_first_high_spell", "variants",
                              "park_triggered", "criteria")}
    stat.update(eth=eth, vintage="current (Coin Metrics recomputes realised cap without vintages)",
                park_rule="'else insufficient independent episodes (parked, revisit each cycle)': " + ("triggered" if j["park_triggered"] else "not triggered"))
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================== T-402 stablecoin supply ==

T402_MIN_N = 400               # weekly observations
T402_START = "2018-01-01"
T402_H = 30
T402_HALVES = (("2018-2021", "2018-01-01", "2021-12-31"), ("2022-2026", "2022-01-01", "2026-12-31"))
T402_NW_LAG = 60               # 2 x the 30-day hold (rule 10 pooled all-start)
T402_HH_LAG = 29               # the 30-day overlap
T402_T = 2.0


def supply_growth(supply: dict, day: str, lag_days: int = 30, ex: Sequence[str] = ()) -> Optional[float]:
    """Same-coin aggregate growth of supply from day - 1 - lag_days to day - 1 (coins present on both days)."""
    d1, d0 = _day_add(day, -1), _day_add(day, -1 - lag_days)
    s1 = s0 = 0.0
    k = 0
    for c, ser in supply.items():
        if c in ex:
            continue
        a, b = ser.get(d0), ser.get(d1)
        if a is not None and b is not None and a > 0:
            s0 += a
            s1 += b
            k += 1
    return (s1 / s0 - 1.0) if k and s0 > 0 else None


def walk_forward_years(X: np.ndarray, Y: np.ndarray, D: Sequence[str], horizon: int = T402_H, min_train: int = 100) -> dict:
    """The trial's 'walk-forward by year' (expanding window): for every calendar year y after the first, OLS of Y on X
    fitted on the decision days whose forward window closed before y-01-01 (d + horizon < y-01-01), predicting every
    decision day of y. Per year: the fitted slope, out-of-sample R2 against the training mean (Campbell-Thompson), and the
    sign hit rate (forecast and realised return of the same sign; the training mean's hit rate alongside). Pooled: the
    out-of-sample R2 over every predicted day."""
    D = list(D)
    years = sorted({d[:4] for d in D})
    out, sm, sb = {}, 0.0, 0.0
    for y in years[1:]:
        tr = np.array([_day_add(d, horizon) < f"{y}-01-01" for d in D])
        te = np.array([d[:4] == y for d in D])
        if tr.sum() < min_train or te.sum() < 30:
            continue
        b, a = np.polyfit(X[tr], Y[tr], 1)
        pred, bench = a + b * X[te], float(Y[tr].mean())
        em, eb = float(np.sum((Y[te] - pred) ** 2)), float(np.sum((Y[te] - bench) ** 2))
        sm, sb = sm + em, sb + eb
        out[y] = {"n_train": int(tr.sum()), "n_test": int(te.sum()), "slope": float(b), "oos_r2": (1.0 - em / eb) if eb > 0 else None,
                  "hit_rate": float(np.mean(np.sign(pred) == np.sign(Y[te]))),
                  "hit_rate_mean": float(np.mean(np.sign(bench) == np.sign(Y[te])))}
    r2 = [v["oos_r2"] for v in out.values() if v["oos_r2"] is not None]
    return {"years": out, "pooled_oos_r2": (1.0 - sm / sb) if sb > 0 else None, "n_years": len(out),
            "n_negative_r2": int(sum(1 for v in r2 if v < 0)),
            "slope_range": [min(v["slope"] for v in out.values()), max(v["slope"] for v in out.values())] if out else None}


def stablecoin_predict(supply: dict, price: dict, start: str = T402_START, horizon: int = T402_H, min_n: int = T402_MIN_N,
                       mcap: Optional[dict] = None) -> dict:
    """T-402 core: supply {coin: {day: SplyCur}}, price {day: BTC close}."""
    days_p = sorted(price)
    if not days_p:
        return {"too_short": True, "n": 0}
    last = days_p[-1]
    end = _day_add(last, -horizon)
    days = [d for d in _cal(start, end)]
    X, Y, D = [], [], []
    for d in days:
        p0, p1 = price.get(d), price.get(_day_add(d, horizon))
        if not p0 or not p1:
            continue
        g = supply_growth(supply, d)
        if g is None:
            continue
        X.append(g)
        Y.append(math.log(p1 / p0))
        D.append(d)
    X, Y = np.array(X, float), np.array(Y, float)
    if X.size < 200:
        return {"too_short": True, "n": X.size // 7}
    nw = ols_kernel(Y, X, T402_NW_LAG, "bartlett")
    hh = ols_kernel(Y, X, T402_HH_LAG, "uniform")
    phases = {}
    for w in range(7):
        m = np.array([date.fromisoformat(d).weekday() == w for d in D])
        if m.sum() > 20:
            lag = max(nw_lag(int(m.sum())), 5)
            o = ols_kernel(Y[m], X[m], lag, "bartlett")
            phases[("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[w]] = {"n": int(m.sum()), "beta": o["beta"], "t": o["t"], "lag": lag}
    n_weeks = min(p["n"] for p in phases.values())
    rows_t = [(f"pooled all-start Newey-West lag {T402_NW_LAG}: slope {nw['beta']:+.3f}, t {_s(nw['t'], 2)}",
               None if nw["t"] is None else bool(nw["t"] >= T402_T), bool(nw["t"] is not None and nw["t"] < -T402_T)),
              (f"Hansen-Hodrick lag {T402_HH_LAG}: t {_s(hh['t'], 2)}" + (" [HH variance not positive]" if hh["t"] is None else ""),
               None if hh["t"] is None else bool(hh["t"] >= T402_T), bool(hh["t"] is not None and hh["t"] < -T402_T))]
    crit = [all_constructions(rows_t, f"HAC t >= {T402_T:g} for the slope of the next-{horizon}-day log return on 30-day supply growth")]
    halves = {}
    for nm, a, b in T402_HALVES:
        m = np.array([a <= d <= b for d in D])
        halves[nm] = ols_kernel(Y[m], X[m], T402_NW_LAG, "bartlett") if m.sum() > 50 else None
    hrow_ok = None if any(h is None for h in halves.values()) else all(h["beta"] > 0 for h in halves.values())
    crit.append(("positive slope in both halves (" + "; ".join(f"{k} {_s(h['beta'] if h else None)} (t {_s(h['t'] if h else None, 2)})"
                                                             for k, h in halves.items()) + ")", hrow_ok, False))
    v, why = _decide(crit, n_weeks, min_n, "weekly observations (the shortest weekday grid)")
    years = {}                                   # in-sample slope within each year (descriptive, not the walk-forward)
    for y in sorted({d[:4] for d in D}):
        m = np.array([d[:4] == y for d in D])
        if m.sum() > 100:
            years[y] = float(np.polyfit(X[m], Y[m], 1)[0])
    wf = walk_forward_years(X, Y, D, horizon)
    m_ex = np.array([not (d[:7] in ("2022-05", "2023-03")) for d in D])
    ex_o = ols_kernel(Y[m_ex], X[m_ex], T402_NW_LAG, "bartlett")
    Xu = []
    for d in D:
        Xu.append(supply_growth(supply, d, ex=("usdt",)))
    mu = np.array([x is not None for x in Xu])
    exu = ols_kernel(Y[mu], np.array([x for x in Xu if x is not None]), T402_NW_LAG, "bartlett") if mu.sum() > 200 else None
    ssr = None
    if mcap:
        zs, ys = [], []
        tot = {}
        for d in _cal(_day_add(start, -400), end):
            s = sum(ser.get(d, 0.0) for ser in supply.values())
            if s > 0 and mcap.get(d):
                tot[d] = math.log(mcap[d] / s)
        for d, y_ in zip(D, Y):
            hist = [tot.get(_day_add(d, -k)) for k in range(1, 366)]
            hist = [h for h in hist if h is not None]
            if len(hist) > 300 and np.std(hist) > 0 and tot.get(_day_add(d, -1)) is not None:
                zs.append((tot[_day_add(d, -1)] - np.mean(hist)) / np.std(hist))
                ys.append(y_)
        if len(zs) > 200:
            o = ols_kernel(np.array(ys), np.array(zs), T402_NW_LAG, "bartlett")
            ssr = {"beta": o["beta"], "t": o["t"], "n_days": len(zs)}
    ts = [p["t"] for p in phases.values() if p["t"] is not None]
    return {"n": int(n_weeks), "n_days": int(X.size), "window": [D[0], D[-1]], "nw": nw, "hh": hh, "phases": phases,
            "phase_t_range": [min(ts), max(ts)] if ts else None, "phases_passing": int(sum(1 for t in ts if t >= T402_T)),
            "halves": halves, "years": years, "walk_forward": wf, "without_2022_05_2023_03": ex_o, "ex_usdt": exu, "ssr_z": ssr,
            "x_mean": float(X.mean()), "x_sd": float(X.std()), "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_cryptoxs_stablecoin_supply_growth(archive):
    """T-402."""
    miss = _missing(archive, [cm_b(a) for a in STABLES] + [BTC_Y])
    if miss:
        return miss
    supply = {a: _metric(_cm(archive, a), "SplyCur") for a in STABLES}
    mcap = _metric(_cm(archive, "btc"), "CapMrktCurUSD") if _has(archive, cm_b("btc")) else None     # optional SSR variant
    j = stablecoin_predict(supply, _closes(archive, BTC_Y), mcap=mcap)
    if j.get("too_short"):
        return _too_short(j["n"], T402_MIN_N, "weekly observations", "decision days 2018..")
    ph = "; ".join(f"{k} {p['beta']:+.3f} (t {_s(p['t'], 2)}, {p['n']})" for k, p in j["phases"].items())
    yrs = ", ".join(f"{k} {v:+.2f}" for k, v in j["years"].items())
    wf = j["walk_forward"]
    wft = "; ".join(f"{y} slope {w['slope']:+.3f}, OOS R2 {_s(w['oos_r2'], 3)}, hit {w['hit_rate'] * 100:.0f}% (mean-only "
                    f"{w['hit_rate_mean'] * 100:.0f}%)" for y, w in wf["years"].items())
    reason = (f"Aggregate SplyCur of USDT, USDC, DAI, BUSD, TUSD (Coin Metrics, same-coin 30-day growth to day t-1; UST is not in "
              f"the community API), BTC next-30-day log return from close t (Yahoo BTC-USD), days {j['window'][0]}..{j['window'][1]} "
              f"({j['n_days']} days; growth mean {_pc(j['x_mean'], 2)}, sd {_pc(j['x_sd'], 2)}). Pooled all-start slope "
              f"{j['nw']['beta']:+.3f} (Newey-West lag {T402_NW_LAG} t {_s(j['nw']['t'], 2)}; Hansen-Hodrick lag {T402_HH_LAG} t "
              f"{_s(j['hh']['t'], 2)}); weekday grids (slope, t, weeks): {ph}; {j['phases_passing']}/7 grids have t >= 2. Halves: "
              + "; ".join(f"{k} {_s(h['beta'] if h else None)} (t {_s(h['t'] if h else None, 2)})" for k, h in j["halves"].items())
              + f". Reported: walk-forward by year (expanding window: the slope fitted on the days whose 30-day forward window "
              f"closed before 1 January, predicting the year; out-of-sample R2 against the training mean): {wft}; pooled OOS R2 "
              f"{_s(wf['pooled_oos_r2'], 3)}, negative in {wf['n_negative_r2']} of {wf['n_years']} years; in-sample slope within each "
              f"year {yrs}; without 2022-05 and 2023-03 slope {j['without_2022_05_2023_03']['beta']:+.3f} (t "
              f"{_s(j['without_2022_05_2023_03']['t'], 2)}); ex-USDT growth "
              + (f"{j['ex_usdt']['beta']:+.3f} (t {_s(j['ex_usdt']['t'], 2)})" if j["ex_usdt"] else "n/a")
              + (f"; SSR z-score (365-day) slope {j['ssr_z']['beta']:+.4f} (t {_s(j['ssr_z']['t'], 2)}; the dry-powder reading "
                 f"predicts a negative sign)" if j["ssr_z"] else "") + " — " + j["why"])
    stat = {k: j[k] for k in ("n", "n_days", "window", "nw", "hh", "phases", "phase_t_range", "phases_passing", "halves", "years",
                              "walk_forward", "without_2022_05_2023_03", "ex_usdt", "ssr_z", "x_mean", "x_sd", "criteria")}
    stat["rule10"] = "pooled all-start (daily) regression; the seven weekday grids reported"
    stat["years_label"] = "in-sample slope within each year (descriptive); the walk-forward is under walk_forward"
    return _out(stat, j["n"], j["verdict"], reason)


# ===================================================================================== T-403 hash ribbons ==

T403_MIN_N = 15                # signals
T403_START = "2011-01-01"
T403_H = 90
T403_PUB = "2019-08-01"
T403_SHARE = 0.60
T403_CHINA = ("2021-06-01", "2021-09-30")


def _sma(x: np.ndarray, w: int, min_frac: float = 0.8) -> np.ndarray:
    """Trailing calendar-day SMA over present values (NaN when fewer than min_frac x w are present)."""
    n = x.size
    v = np.where(np.isfinite(x), x, 0.0)
    c = np.isfinite(x).astype(float)
    cv, cc = np.concatenate([[0.0], np.cumsum(v)]), np.concatenate([[0.0], np.cumsum(c)])
    out = np.full(n, np.nan)
    for k in range(w - 1, n):
        cnt = cc[k + 1] - cc[k + 1 - w]
        if cnt >= min_frac * w:
            out[k] = (cv[k + 1] - cv[k + 1 - w]) / cnt
    return out


def ribbon_signals(hash_by_day: np.ndarray, P: np.ndarray, reading: str, min_cap: int = 1) -> tuple:
    """(signal indices, recovery indices) on a daily calendar. Hash ribbons from data through t - 1; price momentum
    through close t ('live') or t - 1 ('prev'). A capitulation shorter than ``min_cap`` days yields no recovery."""
    h30, h60 = _sma(hash_by_day, 30), _sma(hash_by_day, 60)
    a = np.full(h30.size, np.nan)
    a[1:] = h30[:-1] - h60[:-1]                       # known at t: data through t - 1
    p10, p20 = _sma(P, 10, 1.0), _sma(P, 20, 1.0)
    mom = p10 > p20
    if reading == "prev":
        mom = np.concatenate([[False], mom[:-1]])
    sig, rec = [], []
    cap_len, waiting = 0, False
    for t in range(1, a.size):
        if not np.isfinite(a[t]):
            cap_len = 0
            continue
        if a[t] < 0:
            cap_len += 1
            waiting = False
            continue
        if cap_len >= min_cap:
            rec.append(t)
            waiting = True
        cap_len = 0
        if waiting and mom[t]:
            sig.append(t)
            waiting = False
    return sig, rec


T403_VARIANTS = ("30/60 cross + price confirmation (primary)", "no price confirmation", "hold until MVRV > 3",
                  "difficulty drop >= 5% as capitulation")
T403_MVRV_EXIT = 3.0


def ribbon_variants(H: np.ndarray, P: np.ndarray, mv: Optional[np.ndarray], ix0: int, horizon: int = T403_H) -> dict:
    """The 4 declared variants as daily-timeline event strategies on one calendar (H hash rate, P price, mv MVRV by day
    or None; signals from index ix0): {variant: {signals, held-day share, daily series x, Sharpe}} or None when the
    variant cannot be computed. x[t] = lr[t] - mean(lr) on held days, 0 otherwise, lr[t] = log(P[t] / P[t-1]) over
    the window ix0 + 1..; a signal at close s holds days s+1..s+horizon (fixed exit) or s+1..e, e the first close after s
    with MVRV of day e - 1 above 3 (MVRV exit; held to the end when it never comes)."""
    T = P.size
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.concatenate([[np.nan], np.log(P[1:] / P[:-1])])
    win = np.zeros(T, bool)
    win[ix0 + 1:] = True
    win &= np.isfinite(lr)
    mu = float(lr[win].mean())
    sig, rec = ribbon_signals(H, P, "live")
    sig, rec = [s for s in sig if s >= ix0], [r for r in rec if r >= ix0]

    def fixed(ss):
        h = np.zeros(T, bool)
        for s in ss:
            h[s + 1:s + 1 + horizon] = True
        return h

    def mvrv_exit(ss):
        h = np.zeros(T, bool)
        for s in ss:
            e = s + 1
            while e < T and not (np.isfinite(mv[e - 1]) and mv[e - 1] > T403_MVRV_EXIT):
                e += 1
            h[s + 1:min(e, T - 1) + 1] = True
        return h

    holds = {T403_VARIANTS[0]: (sig, fixed(sig)), T403_VARIANTS[1]: (rec, fixed(rec)),
             T403_VARIANTS[2]: (sig, mvrv_exit(sig)) if mv is not None else None, T403_VARIANTS[3]: None}
    out = {}
    for nm, hv in holds.items():
        if hv is None:
            out[nm] = None
            continue
        ss, h = hv
        x = np.where(h & win, lr - mu, 0.0)[win]
        out[nm] = {"signals": len(ss), "held_share": float((h & win)[win].mean()), "x": x,
                   "mean_daily": float(x.mean()), "sharpe_daily": _sr_pp(x),
                   "sharpe_ann": (_sr_pp(x) * math.sqrt(365.0)) if _sr_pp(x) is not None else None}
    return out


def hash_ribbons(hashes: dict, price: dict, start: str = T403_START, horizon: int = T403_H, min_n: int = T403_MIN_N,
                 pub: str = T403_PUB, mvrv: Optional[dict] = None) -> dict:
    """T-403 core: hashes {source: {day: hash rate}}, price {day: BTC close}, mvrv {day: MVRV} (optional: the MVRV-exit
    variant of the reported DSR)."""
    days_p = sorted(price)
    if not days_p:
        return {"too_short": True, "n": 0}
    first = min(min(h) for h in hashes.values() if h)
    cal = _cal(max(first, _day_add(start, -200)), days_p[-1])
    T = len(cal)
    P = np.array([price.get(d, np.nan) for d in cal], float)
    y = np.full(T, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        y[:T - horizon] = np.log(P[horizon:] / P[:T - horizon])
    ix0 = cal.index(start) if start in cal else 0
    base = np.zeros(T, bool)
    base[ix0:] = True
    base &= np.isfinite(y)
    yz = np.where(base, y, 0.0)
    res, rows_ci, rows_sh = {}, [], []
    for src, hs in hashes.items():
        H = np.array([hs.get(d, np.nan) for d in cal], float)
        for rd in ("live", "prev"):
            sig, rec = ribbon_signals(H, P, rd)
            sig = [s for s in sig if base[s]]
            m = np.zeros(T, bool)
            m[sig] = True
            t = diff_test(yz, m, base, block=horizon)
            ys = y[sig]
            post = [s for s in sig if cal[s] >= pub]
            share = float(np.mean(y[post] > 0)) if post else None
            nm = f"{src}, momentum read at {'close t (live proxy)' if rd == 'live' else 'close t-1'}"
            res[nm] = {"signals": [cal[s] for s in sig], "n": len(sig), "est": t["est"], "ci": t.get("ci"), "reps": t.get("reps"),
                       "mean_signal": float(ys.mean()) if len(sig) else None, "n_post": len(post), "post_share_positive": share,
                       "recoveries": [cal[r] for r in rec if r >= ix0], "fwd": {cal[s]: float(y[s]) for s in sig}}
            rows_ci.append(_ci_crit(t, "gt", 0.0, nm, fmt=lambda v: _s(v, 3)))
            # decisive (rule 5): the share stays below the threshold even if every signal missing to min_n were a
            # positive post-publication one
            add = max(0, min_n - len(sig))
            npos = int(np.sum(y[post] > 0)) if post else 0
            dec = bool(len(post) + add > 0 and (npos + add) / (len(post) + add) < T403_SHARE)
            rows_sh.append((f"{nm}: {len(post)} post-publication signals, {_f(None if share is None else share * 100, 0)}% positive",
                            None if share is None else bool(share >= T403_SHARE), dec))
    n = min(r["n"] for r in res.values())
    uncond = float(y[base].mean())
    crit = [all_constructions(rows_ci, f"mean forward {horizon}-day log return after a signal - unconditional > 0 with the 95% CI "
                                       f"excluding 0 (CBB of the daily timeline, {horizon}-day blocks; every source and reading)"),
            all_constructions(rows_sh, f">= {T403_SHARE * 100:.0f}% of post-publication ({pub[:7]}-) signals with a positive forward "
                                       f"return (every source and reading)")]
    v, why = _decide(crit, n, min_n, "signals (the fewest over sources and readings)")
    srcs = list(hashes)
    agree = None
    if len(srcs) == 2:
        ra = res[f"{srcs[0]}, momentum read at close t (live proxy)"]["recoveries"]
        rb = res[f"{srcs[1]}, momentum read at close t (live proxy)"]["recoveries"]
        ob = [_ord(d) for d in rb]
        agree = {"n_a": len(ra), "n_b": len(rb), "share_a_within_3d": float(np.mean([min((abs(_ord(d) - o) for o in ob), default=999) <= 3 for d in ra])) if ra else None}
    prim = res[f"{srcs[0]}, momentum read at close t (live proxy)"]
    sg = prim["signals"]
    wo = [d for d in sg if not (T403_CHINA[0] <= d <= T403_CHINA[1])]
    wo_est = float(np.mean([prim["fwd"][d] for d in wo]) - uncond) if wo else None
    ins = [d for d in sg if d < pub]
    caps7 = None
    H0 = np.array([hashes[srcs[0]].get(d, np.nan) for d in cal], float)
    s7, _ = ribbon_signals(H0, P, "live", min_cap=7)
    s7 = [s for s in s7 if base[s]]
    if s7:
        caps7 = {"n": len(s7), "est": float(y[s7].mean() - uncond)}
    return {"n": int(n), "window": [cal[ix0], cal[int(np.flatnonzero(base)[-1])]], "uncond": uncond, "res": res, "agree": agree,
            "china_signals": [d for d in sg if T403_CHINA[0] <= d <= T403_CHINA[1]], "without_china_est": wo_est,
            "in_sample_est": float(np.mean([prim["fwd"][d] for d in ins]) - uncond) if ins else None,
            "post_est": float(np.mean([prim["fwd"][d] for d in sg if d >= pub]) - uncond) if any(d >= pub for d in sg) else None,
            "cap7": caps7, "round_trip_cost_log": float(2 * math.log(1 - 0.004)),             # 40 bps per switch, 2 switches
            "round_trip_cost_log_10": float(2 * math.log(1 - 0.001)),                            # 10 bps per switch
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_cryptoxs_hash_ribbons(archive):
    """T-403."""
    miss = _missing(archive, [HASH_B, cm_b("btc"), BTC_Y])
    if miss:
        return miss
    bci = {}
    for r in _iter(archive, HASH_B):
        v = r["value"]
        x = _num(v.get("hash_rate_ths"))
        if x is not None and v.get("day"):
            bci[v["day"]] = x
    cm = _cm(archive, "btc")
    hashes = {"blockchain.info": bci, "Coin Metrics HashRate": _metric(cm, "HashRate")}
    price = splice_price(_metric(cm, "PriceUSD"), _closes(archive, BTC_Y), "2014-09-17")
    j = hash_ribbons(hashes, price)
    if j.get("too_short"):
        return _too_short(j["n"], T403_MIN_N, "signals", "hash-ribbon signals 2011..")
    rs = "; ".join(f"{k}: {r['n']} signals, mean after signal {_s(r['mean_signal'])}, difference {_s(r['est'])} "
                   f"({_ci_txt(r['ci'], 3, 1.0, '')}), post-publication {r['n_post']} signals, "
                   f"{_f(None if r['post_share_positive'] is None else r['post_share_positive'] * 100, 0)}% positive"
                   for k, r in j["res"].items())
    ag = j["agree"]
    reason = (f"Hash ribbons (30/60-day calendar SMAs of the daily hash rate, data through t-1) recovery after a capitulation, "
              f"entry at the first close with the 10-day price SMA above the 20-day; BTC price Coin Metrics PriceUSD to "
              f"2014-09-16, Yahoo BTC-USD from 2014-09-17; forward {T403_H}-day log return from the entry close; days "
              f"{j['window'][0]}..{j['window'][1]}, unconditional mean {_s(j['uncond'])}. {rs}. Reported: "
              + (f"recovery dates agree within 3 days for {_f(None if ag['share_a_within_3d'] is None else ag['share_a_within_3d'] * 100, 0)}% "
                 f"of the {ag['n_a']} blockchain.info recoveries ({ag['n_b']} Coin Metrics); " if ag else "")
              + f"2011-2019-07 (author's in-sample) difference {_s(j['in_sample_est'])}, post-publication {_s(j['post_est'])}; "
              f"China mining-ban signals {j['china_signals'] or 'none'} (difference without them {_s(j['without_china_est'])}); "
              f"capitulations >= 7 days: {j['cap7']['n'] if j['cap7'] else 0} signals, difference {_s(j['cap7']['est'] if j['cap7'] else None)}; "
              f"a round trip at 40 bps per switch (80 bps) costs {j['round_trip_cost_log']:+.4f} in log return and one at 10 bps "
              f"per switch (20 bps) {j['round_trip_cost_log_10']:+.4f}; hash rates are the providers' current "
              f"estimates (near point in time with the one-day lag, as the triage says) — " + j["why"])
    stat = {k: j[k] for k in ("n", "window", "uncond", "res", "agree", "china_signals", "without_china_est", "in_sample_est", "post_est",
                              "cap7", "round_trip_cost_log", "round_trip_cost_log_10", "criteria")}
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================== T-367 DeFi lending carry ==

T367_MIN_N = 900               # days
T367_CHARGE = 1.5              # percent per year
T367_WIN = ("2023-02-01", "2026-09-30")
T367_BLOCK = 30
AAVE = "aa70268e-4b52-42bf-a116-608b370f9501"
SPARK_SAV = "c5c74dd1-995c-4445-9d84-3e710bad7d52"
MAPLE = "43641cf5-a92e-416b-bce9-27113d3c0db6"
SPARKLEND = "65ce8276-b4d9-41ba-9f6f-21fc374cf9bc"
POOL_NAMES = {AAVE: "Aave v3 USDC", SPARK_SAV: "Spark savings USDC", MAPLE: "Maple syrupUSDC", SPARKLEND: "SparkLend USDC"}
T367_SETS = {"Spark = Spark savings USDC": (AAVE, SPARK_SAV, MAPLE), "Spark = SparkLend USDC": (AAVE, SPARKLEND, MAPLE)}
T367_CUT_TVL = 50e6            # a first in-window chart point holding > $50M TVL ...
T367_CUT_SHARE = 0.10          # ... or > 10% of its set's TVL that day was live before it: a cut-off chart (a data gap)
T367_SHARE_TOKENS = {MAPLE: 38779}          # CMC id of the share token (syrupUSDC: its CMC price is the vault share price)
T367_SCEN_RATES = (0.06, 0.08, 0.10, 0.12)  # sensitivity: constant accrual / APY in the missing span
T367_SCEN_RAMPS = (0.25, 0.10, 0.05)        # ... and, at 10%/yr, TVL ramps ending at these fractions of the first point's TVL
T367_SCEN_BOOT = 1000


def chart_starts(pools: dict, sets: dict = T367_SETS, win: tuple = T367_WIN, cut_tvl: float = T367_CUT_TVL,
                 cut_share: float = T367_CUT_SHARE) -> dict:
    """{pool: start} for every member of every set: the first chart point, its TVL, base APY and largest share of a set's
    TVL that day (None when no other member holds TVL then), and whether the chart is CUT OFF (the pool was live before
    its first point, so its history from the window start to the day before is missing) rather than starting at launch."""
    out = {}
    for p in [q for q in POOL_NAMES if any(q in m for m in sets.values())]:
        pts = {d: v for d, v in pools.get(p, {}).items() if d <= win[1]}
        if not pts:
            out[p] = {"first": None, "tvl": None, "apy": None, "share_of_set": None, "cut": True, "gap": [win[0], win[1]]}
            continue
        first = min(pts)
        tvl, apy = pts[first][1], pts[first][0]
        shares = []
        for m in sets.values():
            if p in m:
                others = sum((pools.get(q, {}).get(first) or (0.0, 0.0))[1] or 0.0 for q in m if q != p)
                if others > 0:
                    shares.append(tvl / (tvl + others))
        share = max(shares) if shares else None
        cut = first > win[0] and (tvl > cut_tvl or (share is not None and share > cut_share))
        out[p] = {"first": first, "tvl": tvl, "apy": apy, "share_of_set": share, "cut": bool(cut),
                  "gap": [win[0], _day_add(first, -1)] if cut else None}
    return out


def _compound(apy_pts: dict, a: str, b: str) -> float:
    """Growth of a share accruing the chart's daily base APY (% a year, the last point carried over missing days) over
    the days (a, b]."""
    g, last = 1.0, None
    for d in _cal(_day_add(a, 1), b) if b > a else []:
        last = apy_pts.get(d, last)
        if last is not None:
            g *= (1.0 + last / 100.0) ** (1.0 / 365.0)
    return g


def implied_share_price(apy_pts: dict, first: str, cmc_px: dict, tol: float = 0.01) -> Optional[dict]:
    """The share price on the pool's first chart day, backed out from the share token's first CMC price and the chart's
    base APY compounded in between; usable only when the compounded APY matches the CMC price growth over the CMC span
    within ``tol`` (the CMC price is the share price)."""
    ds = sorted(d for d in cmc_px if d >= first)
    if len(ds) < 2:
        return None
    d0, d1 = ds[0], ds[-1]
    cg, lg = cmc_px[d1] / cmc_px[d0], _compound(apy_pts, d0, d1)
    return {"cmc_first": d0, "cmc_last": d1, "cmc_price_first": cmc_px[d0], "cmc_growth": cg, "chart_growth": lg,
            "consistent": bool(abs(lg / cg - 1.0) <= tol), "pps_first": cmc_px[d0] / _compound(apy_pts, first, d0)}


def gap_fill(pts: dict, first: str, inception: str, apy_pct: float, end_tvl: float) -> dict:
    """``pts`` with the days from ``inception`` to the day before ``first`` filled: constant base APY, TVL ramping
    linearly from 0 at inception to ``end_tvl`` at ``first`` (a scenario, not data)."""
    out = dict(pts)
    span = _ord(first) - _ord(inception)
    for k in range(1, span + 1):
        d = _day_add(first, -k)
        tvl = end_tvl * (span - k) / span
        if tvl > 0:
            out[d] = (float(apy_pct), float(tvl), d + "T23:01:00+00:00")
    return out


def _set_series(pools: dict, members: Sequence[str], days: Sequence[str], bill_asof: Callable) -> tuple:
    """A pool set's daily series: (days, TVL-weighted 7-day base APY, DTB3 discount yield at the chart timestamp,
    sum TVL x APY, sum TVL)."""
    apy_pts = {p: {d: v[0] for d, v in pools.get(p, {}).items()} for p in members}
    ser, dl = [], []
    for d in days:
        num = den = 0.0
        ts = None
        for p in members:
            pt = pools.get(p, {}).get(d)
            if pt is None:
                continue
            a = apy7(apy_pts[p], d)
            if a is None or not pt[1] or pt[1] <= 0:
                continue
            num += pt[1] * a
            den += pt[1]
            ts = max(ts or pt[2], pt[2])
        if den <= 0:
            continue
        b = bill_asof(ts)
        if b is None:
            continue
        ser.append((num / den, b, num, den))
        dl.append(d)
    arr = np.array(ser, float).reshape(-1, 4)
    return dl, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]


def _light_bounds(pools: dict, bill_asof: Callable, days: Sequence[str], sets: dict, n_boot: int) -> dict:
    """Every reading's mean and one-sided 95% upper bound (one seed, ``n_boot`` draws): the gap-scenario sensitivity."""
    out = {}
    for sn, members in sets.items():
        dl, A, Bd, NA, DN = _set_series(pools, members, days, bill_asof)
        if not dl:
            continue
        for cn, fn in T367_CONV.items():
            bl_ = np.array([fn(x) for x in Bd])
            sp = A - bl_
            out[f"{sn}, DTB3 {cn}"] = {"mean": float(sp.mean()),
                                       "ub95": _stud(_mean_stat, [sp], T367_BLOCK, n_boot, SEED, level=0.90)["ci"][1]}
            r = _stud(_ratio_stat, [NA - DN * bl_, DN], T367_BLOCK, n_boot, SEED, level=0.90)
            out[f"{sn}, DTB3 {cn}, pool-days weighted"] = {"mean": r["est"], "ub95": r["ci"][1]}
    return out


def gap_scenarios(pools: dict, bill_asof: Callable, starts: dict, share_prices: dict, win: tuple = T367_WIN,
                  charge: float = T367_CHARGE, sets: dict = T367_SETS) -> dict:
    """Sensitivity of every reading to the missing history of each cut-off pool with a usable share price: the gap
    filled from the inception the share price implies (price 1 at inception, accruing r a year) with a constant APY r and
    TVL ramping from 0 to the first point's TVL (r in T367_SCEN_RATES), and at 10%/yr with ramps ending at
    T367_SCEN_RAMPS of it. Outcome: 'pass' when every reading's bound is below the charge, 'fail' when none is."""
    days = _cal(*win)
    nb = min(N_BOOT, T367_SCEN_BOOT)
    out = {}
    for p, sp in share_prices.items():
        st = starts.get(p) or {}
        if not st.get("cut") or not st.get("first") or not sp or not sp.get("consistent") or sp["pps_first"] <= 1.0:
            continue
        first, tvl0 = st["first"], st["tvl"]
        scen = [(r, 1.0) for r in T367_SCEN_RATES] + [(0.10, f) for f in T367_SCEN_RAMPS]
        rows = []
        for r, frac in scen:
            inc = _day_add(first, -int(round(math.log(sp["pps_first"]) / math.log(1.0 + r) * 365.0)))
            filled = dict(pools)
            filled[p] = gap_fill(pools[p], first, inc, 100.0 * r, frac * tvl0)
            b = _light_bounds(filled, bill_asof, days, sets, nb)
            ubs = [x["ub95"] for x in b.values() if x["ub95"] is not None]
            out_ = ("pass" if ubs and all(u < charge for u in ubs) else "fail" if ubs and all(u >= charge for u in ubs)
                    else "undecided")
            rows.append({"rate": r, "inception": inc, "ramp_end_tvl": frac * tvl0, "ramp_end_frac": frac,
                         "ub95_min": min(ubs) if ubs else None, "ub95_max": max(ubs) if ubs else None, "outcome": out_,
                         "readings": b})
        out[POOL_NAMES[p]] = {"pps_first": sp["pps_first"], "draws": nb, "scenarios": rows}
    return out


def bey(d_pct: float) -> float:
    """Bond-equivalent yield (percent) of a 91-day bill discount yield in percent."""
    d = d_pct / 100.0
    return 100.0 * 365.0 * d / (360.0 - 91.0 * d)


def eff_annual(d_pct: float) -> float:
    """Effective annual yield (percent) of a 91-day bill discount yield in percent."""
    d = d_pct / 100.0
    return 100.0 * ((1.0 - d * 91.0 / 360.0) ** (-365.0 / 91.0) - 1.0)


def apy7(points: dict, day: str, min_present: int = 5) -> Optional[float]:
    vals = [points.get(_day_add(day, -k)) for k in range(7)]
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if len(vals) >= min_present else None


T367_CONV = {"bond-equivalent": bey, "effective annual": eff_annual}


def gap_label(p: str, st: dict, sp: Optional[dict] = None) -> str:
    """The None criterion naming a cut-off pool's missing span."""
    nm = POOL_NAMES.get(p, p)
    if st.get("first") is None:
        return f"{nm} TVL and base APY {st['gap'][0]}..{st['gap'][1]} (no DefiLlama chart point archived in the window)"
    sh = "" if st.get("share_of_set") is None else f", {st['share_of_set'] * 100:.0f}% of its set's TVL"
    pp = (f", share price about {sp['pps_first']:.3f}" if sp and sp.get("consistent") else "")
    return (f"{nm} TVL and base APY {st['gap'][0][:7]}..{st['gap'][1]} (live at its first DefiLlama point {st['first']}: "
            f"${st['tvl'] / 1e9:.2f}B TVL{sh}, base APY {st['apy']:.2f}%{pp}; the chart is cut off, the history before it "
            f"is not archived)")


def defi_carry(pools: dict, bill_asof: Callable, win: tuple = T367_WIN, charge: float = T367_CHARGE, min_n: int = T367_MIN_N,
               sets: dict = T367_SETS, eth: Optional[dict] = None, share_prices: Optional[dict] = None) -> dict:
    """T-367 core: pools {pool: {day: (apyBase %, tvlUsd, timestamp)}}, bill_asof(timestamp) -> DTB3 discount yield %,
    share_prices {pool: implied_share_price(...)} for the gap sensitivity (optional)."""
    days = _cal(*win)
    conv = T367_CONV
    rows, out = [], {}
    for sn, members in sets.items():
        dl, A, Bd, NA, DN = _set_series(pools, members, days, bill_asof)
        if not dl:
            continue
        for cn, fn in conv.items():
            bl_ = np.array([fn(x) for x in Bd])
            sp = A - bl_
            t = mean_test(sp, T367_BLOCK, level=0.90, side="lt", thr=charge)
            nm = f"{sn}, DTB3 {cn}"
            name, ok, dec = _ci_crit(t, "lt", charge, f"{nm}, pools weighted within each day: mean {sp.mean():+.3f} pp",
                                     fmt=lambda v: _pp(v, 3))
            rows.append((name, ok, dec))
            out[nm] = {"n": int(sp.size), "mean": float(sp.mean()), "ub95_one_sided": t["ci"][1], "ci90": t["ci"], "reps": t.get("reps"),
                       "share_apy_above_bill": float(np.mean(sp > 0)), "p10": float(np.quantile(sp, 0.10)), "first": dl[0], "last": dl[-1],
                       "mean_apy": float(A.mean()), "mean_bill": float(bl_.mean()), "days": dl, "spread": sp}
            if len(rows) == 1:                     # the first reading: sensitivities (reported, one seed each)
                out[nm]["ub975_two_sided_block30"] = _stud(_mean_stat, [sp], T367_BLOCK, N_BOOT, SEED, level=0.95)["ci"][1]
                out[nm]["ub95_by_block"] = {str(bl): _stud(_mean_stat, [sp], bl, N_BOOT, SEED, level=0.90)["ci"][1] for bl in (60, 120)}
            # second reading of 'TVL-weighted mean daily spread': every pool-day weighted by its TVL (a ratio of means)
            NS = NA - DN * bl_
            tr = ratio_test(NS, DN, T367_BLOCK, level=0.90, side="lt", thr=charge)
            nm2 = f"{sn}, DTB3 {cn}, pool-days weighted"
            rows.append(_ci_crit(tr, "lt", charge, f"{sn}, DTB3 {cn}, every pool-day weighted by its TVL: mean {tr['est']:+.3f} pp",
                                 fmt=lambda v: _pp(v, 3)))
            out[nm2] = {"n": int(NS.size), "mean": float(tr["est"]), "ub95_one_sided": tr["ci"][1], "ci90": tr["ci"], "reps": tr.get("reps"),
                        "first": dl[0], "last": dl[-1]}
    if not rows:
        return {"too_short": True, "n": 0}
    n = min(o["n"] for o in out.values())
    crit = [all_constructions(rows, f"one-sided 95% bootstrap upper bound of the TVL-weighted mean spread < {charge:g}% on the "
                                    f"observed pool-days (studentized CBB, {T367_BLOCK}-day blocks; every weighting reading, Spark "
                                    f"reading and bill conversion)")]
    starts = chart_starts(pools, sets, win)
    share_prices = share_prices or {}
    for p, st in starts.items():             # rule 9: a named pool's missing in-window history is a data gap, not a launch
        if st["cut"]:
            crit.append((gap_label(p, st, share_prices.get(p)), None, False))
    v, why = _decide(crit, n, min_n, "days")
    scen = gap_scenarios(pools, bill_asof, starts, share_prices, win, charge, sets) if any(s["cut"] for s in starts.values()) else {}
    prim = out[f"{list(sets)[0]}, DTB3 bond-equivalent"]
    venues, ps = {}, {}
    for p, nm in POOL_NAMES.items():
        pts = pools.get(p, {})
        apy_pts = {d: v_[0] for d, v_ in pts.items()}
        sp = []
        for d in days:
            if d in pts:
                a = apy7(apy_pts, d)
                b = bill_asof(pts[d][2])
                if a is not None and b is not None:
                    sp.append(a - bey(b))
        if len(sp) >= 60:
            sp = np.array(sp)
            tt = mean_test(sp - charge, T367_BLOCK, level=0.90, side="gt", thr=0.0)
            venues[nm] = {"n": int(sp.size), "mean": float(sp.mean()), "lb95_one_sided": tt["ci"][0] + charge, "p_carry": tt.get("p"),
                          "venue_carry": bool(tt["ci"][0] > 0)}
            if tt.get("p") is not None and p != SPARKLEND:
                ps[nm] = tt["p"]
    for ch in (0.5, 1.5):
        tt = mean_test(prim["spread"] - ch, T367_BLOCK, level=0.90, side="gt", thr=0.0)
        if tt.get("p") is not None:
            ps[f"aggregate, charge {ch:g}%"] = tt["p"]
    hp = holm(ps) if ps else {}
    exm = []                                     # reported: without Maple (whether it is US-accessible is a policy call)
    apx = {p: {k: v_[0] for k, v_ in pools.get(p, {}).items()} for p in (AAVE, SPARK_SAV)}
    for d in days:
        num = den = 0.0
        ts = None
        for p in (AAVE, SPARK_SAV):
            pt = pools.get(p, {}).get(d)
            a = apy7(apx[p], d) if pt else None
            if a is not None and pt[1] and pt[1] > 0:
                num, den, ts = num + pt[1] * a, den + pt[1], max(ts or pt[2], pt[2])
        if den > 0 and bill_asof(ts) is not None:
            exm.append(num / den - bey(bill_asof(ts)))
    ex_maple = {"n": len(exm), "mean": float(np.mean(exm))} if exm else None
    eth_rep = None
    if eth:
        dl, sp = prim["days"], prim["spread"]
        r90, xs = [], []
        for d, s in zip(dl, sp):
            a, b = eth.get(_day_add(d, -1)), eth.get(_day_add(d, -91))
            if a and b:
                r90.append(a / b - 1)
                xs.append(s)
        q = defaultdict(list)
        for d, s in zip(dl, sp):
            q[(d[:4], (int(d[5:7]) - 1) // 3)].append(s)
        up, dn = [], []
        for (yy, qq), vals in q.items():
            m0 = f"{yy}-{3 * qq + 1:02d}-01"
            m1 = _day_add(f"{int(yy) + (qq == 3):04d}-{(3 * qq + 3) % 12 + 1:02d}-01", -1)
            a, b = eth.get(_day_add(m0, -1)), eth.get(m1)
            if a and b:
                (up if b > a else dn).append(float(np.mean(vals)))
        eth_rep = {"corr_trailing_90d": float(np.corrcoef(r90, xs)[0, 1]) if len(r90) > 30 else None,
                   "up_quarters": len(up), "up_mean": float(np.mean(up)) if up else None,
                   "down_quarters": len(dn), "down_mean": float(np.mean(dn)) if dn else None}
    for o in out.values():
        o.pop("days", None)
        o.pop("spread", None)
    return {"n": int(n), "out": out, "venues": venues, "holm": hp, "eth": eth_rep, "ex_maple": ex_maple, "criteria": [(c[0], c[1]) for c in crit],
            "starts": starts, "share_prices": share_prices, "gap_scenarios": scen, "verdict": v, "why": why}


def b6c_cryptoxs_defi_yield_carry(archive):
    """T-367."""
    miss = _missing(archive, [LLAMA_B, DTB3_B])
    if miss:
        return miss
    pools = defaultdict(dict)
    for r in _iter(archive, LLAMA_B):
        if r.get("kind") != "chart":
            continue
        v = r["value"]
        a, tv = _num(v.get("apyBase")), _num(v.get("tvlUsd"))
        if a is None or tv is None or v.get("pool") not in POOL_NAMES:
            continue
        ts = r.get("available_at") or v.get("timestamp")
        pools[v["pool"]][ts[:10]] = (a, tv, ts)
    fr = sorted(((av, x) for d, (x, av) in _fred(archive, DTB3_B).items()), key=lambda z: z[0])
    avs = [z[0] for z in fr]

    def bill_asof(ts):
        k = bisect.bisect_right(avs, ts) - 1
        return fr[k][1] if k >= 0 else None

    eth = _closes(archive, ETH_Y) if _has(archive, ETH_Y) else None           # optional: the reported ETH splits
    pools = dict(pools)
    share_prices = {}
    for p, st in chart_starts(pools).items():       # optional: the share price of a cut-off pool's token (the gap sensitivity)
        cid = T367_SHARE_TOKENS.get(p)
        if not st["cut"] or cid is None or st["first"] is None:
            continue
        px = {}
        for y in CMC_D_YEARS:
            if y >= int(st["first"][:4]) and _has(archive, f"{CMC_D_PREFIX}{y}"):
                for r in _iter(archive, f"{CMC_D_PREFIX}{y}"):
                    v = r.get("value") or {}
                    if r.get("kind") == "listing" and v.get("id") == cid and _num(v.get("price")) and v.get("date"):
                        px[v["date"]] = float(v["price"])
        sp = implied_share_price({d: x[0] for d, x in pools[p].items()}, st["first"], px)
        if sp:
            share_prices[p] = sp
    j = defi_carry(pools, bill_asof, eth=eth, share_prices=share_prices)
    if j.get("too_short"):
        return _too_short(j["n"], T367_MIN_N, "days", "pool days 2023-02..2026-09")
    st_txt = "; ".join(
        f"{POOL_NAMES[p]} " + ("no chart point in the window" if st["first"] is None else
                               f"chart from {st['first']} (${st['tvl'] / 1e6:,.1f}M TVL at its first point"
                               + ("" if st["share_of_set"] is None else f", {st['share_of_set'] * 100:.0f}% of its set")
                               + (": CUT OFF, live before it, history from the window start missing)" if st["cut"]
                                  else ": taken as the launch)" if st["first"] > T367_WIN[0] else ")"))
        for p, st in j["starts"].items())
    spt = "; ".join(f"{POOL_NAMES[p]} share token (CMC id {T367_SHARE_TOKENS[p]}) {x['cmc_price_first']:.4f} on {x['cmc_first']}, "
                    f"growth to {x['cmc_last']} {x['cmc_growth']:.4f} vs the chart's compounded base APY {x['chart_growth']:.4f} "
                    + (f"(consistent): share price at the first chart point about {x['pps_first']:.4f}" if x["consistent"]
                       else "(inconsistent: not used)") for p, x in j["share_prices"].items())
    sct = []
    for nm, g in j["gap_scenarios"].items():
        sct.append(f"{nm} gap filled (one seed, {g['draws']} draws; other gaps unfilled): " + "; ".join(
            f"{s_['rate'] * 100:.0f}%/yr from {s_['inception']}, TVL ramp to ${s_['ramp_end_tvl'] / 1e9:.2f}B: bounds "
            f"{_pp(s_['ub95_min'], 3)} to {_pp(s_['ub95_max'], 3)} ({s_['outcome']})" for s_ in g["scenarios"]))
    o = j["out"]
    ot = "; ".join(f"{k}: mean {x['mean']:+.3f} pp"
                   + (f" (APY {x['mean_apy']:.2f}% vs bill {x['mean_bill']:.2f}%)" if "mean_apy" in x else "")
                   + f", one-sided 95% upper bound {_pp(x['ub95_one_sided'], 3)}, {x['n']} days {x['first']}..{x['last']}"
                   for k, x in o.items())
    p0 = o[next(iter(o))]
    vt = "; ".join(f"{k} {x['mean']:+.2f} pp over {x['n']} days (lower bound {_pp(x['lb95_one_sided'], 2)}"
                   f"{', venue-specific carry' if x['venue_carry'] else ''})" for k, x in j["venues"].items())
    et = j["eth"]
    reason = (f"Ethereum USDC lending pools fixed from the 2026-10-16 DefiLlama snapshot ({st_txt}), 7-day mean base APY (no "
              f"rewards), TVL-weighted each day, minus DTB3 known at the chart timestamp; observed pool-days: {ot}. "
              + (f"Data gaps (rule 9): a first chart point above ${T367_CUT_TVL / 1e6:.0f}M TVL or {T367_CUT_SHARE * 100:.0f}% of its "
                 f"set's TVL means the pool was already live, so its history inside the window before that point is missing: "
                 + "; ".join(gap_label(p, st, j["share_prices"].get(p)) for p, st in j["starts"].items() if st["cut"])
                 + (f". Share price: {spt}" if spt else "")
                 + (f". Sensitivity: {'; '.join(sct)}" if sct else "") + ". " if any(st["cut"] for st in j["starts"].values()) else "")
              + f"Reported (first reading): two-sided 97.5% "
              f"end {_pp(p0.get('ub975_two_sided_block30'), 3)}; one-sided 95% bound with 60- / 120-day blocks "
              + " / ".join(_pp(v_, 3) for v_ in (p0.get("ub95_by_block") or {}).values())
              + (f" [FRAGILE: longer blocks than the trial's {T367_BLOCK} days put the bound above {T367_CHARGE:g}%; the spread is "
                 f"persistent beyond 30 days, so the pass rests on the pre-registered block length]"
                 if any(v_ is not None and v_ >= T367_CHARGE for v_ in (p0.get("ub95_by_block") or {}).values()) else "")
              + f"; share of days with APY above the "
              f"bill {p0['share_apy_above_bill'] * 100:.0f}%, 10th percentile {_pp(p0['p10'], 2)}; venues (BEY) {vt}; Holm over the 5 "
              f"declared trials " + ", ".join(f"{k} {v:.3f}" for k, v in j["holm"].items())
              + (f"; correlation with the trailing 90-day ETH return {_f(et['corr_trailing_90d'])}, ETH-up quarters "
                 f"{_pp(et['up_mean'])} ({et['up_quarters']}), down {_pp(et['down_mean'])} ({et['down_quarters']})" if et else "")
              + (f"; without Maple (BEY, pools weighted within each day) {_pp(j['ex_maple']['mean'], 3)}" if j.get("ex_maple") else "")
              + "; posted APY is not realised APY and dead pools are absent from /pools (survivorship) — " + j["why"])
    stat = {k: j[k] for k in ("n", "out", "venues", "holm", "eth", "ex_maple", "criteria", "starts", "share_prices", "gap_scenarios")}
    stat.update(charge_pct=T367_CHARGE, window=list(T367_WIN), pools=POOL_NAMES,
                fragile_block_length=bool(any(v_ is not None and v_ >= T367_CHARGE for v_ in (p0.get("ub95_by_block") or {}).values())))
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_cryptoxs_xs_momentum_weekly": b6c_cryptoxs_xs_momentum_weekly,
    "b6c_cryptoxs_volume_conditioned_momentum": b6c_cryptoxs_volume_conditioned_momentum,
    "b6c_cryptoxs_mvrv_regime": b6c_cryptoxs_mvrv_regime,
    "b6c_cryptoxs_stablecoin_supply_growth": b6c_cryptoxs_stablecoin_supply_growth,
    "b6c_cryptoxs_hash_ribbons": b6c_cryptoxs_hash_ribbons,
    "b6c_cryptoxs_defi_yield_carry": b6c_cryptoxs_defi_yield_carry,
}

THEORY_MAP = {
    "T-314": "b6c_cryptoxs_xs_momentum_weekly",
    "T-420": "b6c_cryptoxs_volume_conditioned_momentum",
    "T-400": "b6c_cryptoxs_mvrv_regime",
    "T-402": "b6c_cryptoxs_stablecoin_supply_growth",
    "T-403": "b6c_cryptoxs_hash_ribbons",
    "T-367": "b6c_cryptoxs_defi_yield_carry",
}
