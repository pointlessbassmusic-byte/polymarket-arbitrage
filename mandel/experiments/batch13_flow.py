"""
Batch 13, group ``flow``: SPXW expiry dampening, single-stock opex pinning, the rebuilt DIX and Deribit signed delta
flow (T-632, T-633, T-639, T-638), 2026-10-20 web sweep, cluster "flow".
=====================================================================================================================

  * T-632  ^GSPC sessions 2014-01..2026-10. y_t = ln(Parkinson sigma_t / (VIX_{t-1}/100/sqrt 252)), Parkinson sigma_t =
           |ln(H_t/L_t)| / (2 sqrt(ln 2)). OLS y_t = beta Expiry_t + weekday FE + year-month FE. Expiry_t = 1 on a
           session with a PM-settled SPXW expiry: every Friday; Wednesdays from 2016-03-02 and Mondays from 2016-08-22
           (Cboe RG16-024 and the 2016-07-11 Monday notice); Tuesdays from 2022-04-26 and Thursdays from 2022-05-19 (the
           registration). Dropped: monthly opex days, month-end sessions, pre-switch holiday-shifted expiry days, FOMC
           decision days, CPI and NFP days, early closes, bars with H <= L or a stale open (open = previous close).
           Pass (>= 2,000 sessions): beta < 0 with one-sided p < 0.05 (studentized circular block bootstrap of the
           slope's influence series, 10-session blocks, 10,000 draws); beta < 0 (point) in 2014-01..2018-02 and in
           2020-04..2024-05; the model-priced 1-day ATM short-straddle P&L per unit premium (sigma = VIX_{t-1}, settled
           close to close) has a coefficient > 0 (point); and the placebo (the dummy one session later) is not
           significant at 5% (two-sided). Reported: the 2022-05..2022-12 drop, the drop-Friday check, VIX1D/VIX 2023+.
  * T-633  Point-in-time S&P 500 members, raw (split-unadjusted) closes, 2005-01..2026-10. h = share of name-days with
           |P - nearest strike| / spacing <= 0.05 on the declared grid ($2.50 below $25, $5 to $200, $10 above).
           R = [h(opex day) / h(its Thursday)] / [h(other Fri) / h(other Thu)]. Pass (>= 200 opex dates): R > 1.05 with
           permutation p < 0.05 (opex label permuted across Fridays within each calendar year, 10,000 draws; the
           registered studentized block bootstrap over months is the second reading); R > 1 in 2005-2015 and in
           2016-2026; R in the top dollar-volume tercile > R in the bottom tercile. Reported: the finer grid, by-year R
           and coverage by year.
  * T-639  Rebuilt DIX_t = sum_i short_i x P_i / sum_i total_i x P_i (FINRA CNMS, point-in-time S&P 500 members, P the
           daily-history close). Signal: DIX_t at or above the 80th percentile of the 252 file days ending at t (t
           included); the rule enters SPY at the t+1 close on the first day of a run at or above it and holds 60
           sessions, no new entry while a position is open. Pass (>= 15 windows): rule-window mean 60-session SPY log
           return net of 2 bps minus the mean over windows started on non-signal days > 0 with Holm one-sided p < 0.05
           over 3 arms (studentized circular block bootstrap of the daily exposure series, 60-session blocks, 10,000
           draws); minus the drawdown-placebo rule (first 5% drawdown from the 60-session high) > 0; the primary
           difference > 0 in 2019-08..2021-12 and in 2022-01..2026-10. Provisional; forward checkpoint at 40 windows.
  * T-638  S_d = sum(sign x amount x delta) / sum |amount x delta| over Deribit BTC option trades on UTC day d in expiries
           0-8 days out (Black-76 delta at the trade's iv, index_price as forward, expiry 08:00 UTC), complete days only.
           Target: Coinbase BTC-USD close of the 23:59 bar of d+1 / that of d - 1. Pass (>= 800 days): Spearman IC > 0 and
           the IC of S residualised on day d's own return > 0 (HAC t, 5 lags); the rule (long when S_d above its
           trailing 60-day median, else short) earns a mean daily return net of 10 bps a round trip and the perpetual
           funding > 0 at deflated p < 0.05 over the 6 registered trials (3 normalisations x 2 horizons) and at the
           registered studentized block bootstrap (5-day blocks) p < 0.05; IC, residual IC and rule net positive in both
           halves (2024-03..2025-06, 2025-07..2026-10); rule net > 0 at 20 bps a round trip.

Conventions and declared readings (fixed before any run)
  * Data (rule 9). Bundles through ``archive.load``; a row counts only when its ``available_at`` is not after the
    bundle's capture time. Daily bars are keyed by the UTC date of Yahoo's bar stamp and are known at their close.
  * Rules 11/12. Where the registration admits more than one reading, every reading is computed and a criterion
    passes only when all of them pass, fails only when all of them fail, and is undecided (None) otherwise.
  * Monte-Carlo precision. Criterion bootstrap p's are means over 5 seeds of 2,000 studentized circular block-bootstrap
    resamples (10,000 draws, ``backtest_eval.block_bootstrap_pvalue``'s construction, Bartlett LRV with bandwidth = block)
    escalated one seed at a time to 50 while the Monte-Carlo band of the p straddles its alpha; permutation p's use
    10,000 draws escalated in batches of 10,000 to 100,000 (``batch6c_cal``).
  * T-632. The expiry calendar is pinned from Cboe documents before any outcome is read: RG16-024 (2016-02-01) lists
    the first Wednesday SPXW expiries as 2016-03-02 and 2016-03-09 and moves a holiday Wednesday to the preceding
    Tuesday; the 2016-07-11 notice plans the first Monday expiries for 2016-08-22 and 2016-08-29; Tuesday 2022-04-26 and
    Thursday 2022-05-19 are the registration's dates. "Pre-switch holiday-shifted expiry days" are the sessions that
    carried an expiry moved off an exchange holiday onto a weekday that had no expiry of its own yet: a holiday Friday,
    Wednesday, Tuesday or Thursday moves to the preceding session, a holiday Monday to the Tuesday of the week (the
    procedure Cboe's Monday Weeklys follow), and an unscheduled closure (2018-12-05) drops both neighbours (the move is
    not documented here: the conservative reading). Monthly opex = the third Friday, or the session before it when the
    Friday is a holiday. Month-end = the last NYSE session of the calendar month (rule calendar). FOMC = every decision
    day (scheduled and unscheduled); CPI and NFP = the first session on or after the 08:30 ET release day; early
    closes are the NYSE 13:00 ET rules (July 3 and December 24 Monday-Thursday, the day after Thanksgiving). A stale open
    is open equal to the previous close (1e-9 relative). VIX_{t-1} is the previous session's Cboe close (16:15 ET,
    archived at 21:30 UTC), known before session t opens; a row whose previous bar is not the previous NYSE session is
    dropped. The slope's inference uses its Frisch-Waugh influence series psi_t = beta + x~_t e_t / mean(x~^2) (x~ the
    expiry dummy residualised on the fixed effects; mean(psi) = beta exactly). Each switch episode is re-estimated
    with its own fixed effects. The straddle is Black-Scholes at the money on the previous close, r = q = 0 (the one-
    day carry of the index is ~1e-5 of spot and its dividend yield is not archived: fred-DTB3 and SPY, listed in the
    registration's data, are therefore not used), tau = 1/252, P&L per unit premium = 1 - |S_t/S_{t-1} - 1| / premium.
    The placebo is a criterion (the registration says it "must not be significant at 5%"; read two-sided, the
    conservative reading). VIX1D before its 2023-04-24 launch is a backfill: reported from 2023-01 (registered) and
    from the launch.
  * T-633. Membership: fja05680 change-date snapshots in force on the date, then the Wikipedia changes table after the
    file's last date (``batch6c_events.membership_snapshots``); a pair needs the name to be a member on both days.
    Index tickers map to Yahoo spellings (BRK.B -> BRK-B); a series is used only when Yahoo's meta says EQUITY and its
    long name matches one of the index's names for that ticker when both exist (reused tickers: S is SentinelOne, not
    Sprint). Raw close = daily-history close x the product of the daily-events split ratios with an ex-date after the
    day. "Priced at least $10" is read on the Thursday (base-day) raw close, fixed before the Friday. The pair is
    (Friday, the calendar Thursday before it), both sessions with closes; the holiday-shifted opex day (Thursday) is
    paired with the session before it; an opex Friday whose Thursday is a holiday (2025-06-20) has no pair and is
    skipped (counted). Dollar-volume terciles: within each date, the 20-session mean of close x volume through the
    base-day close (NaN-aware, >= 10 sessions). The month bootstrap tests H0: R <= 1.05 on the delta-method influence
    series of ln R (12-month blocks, declared here: the registration states no block length).
  * T-639. The DIX construction is ``batch13_short_a``'s (T-674): ``dw_ratio`` over point-in-time members with an
    archived close whose Yahoo series is an EQUITY and passes the FINRA-volume identity check; two price readings (rule
    12): (a) Yahoo's split-adjusted close, literally "the daily-history close" (it embeds splits after t), and (b) the
    as-traded close known at t (x the split factor after t). "First reaches" = the first file day of a run at or above
    the percentile (the previous file day below it). "Windows started on non-signal days" is read two ways (rule 12):
    (A) windows entered the session after a file day whose DIX is below its percentile and (B) windows entered after
    every eligible file day that is not a rule entry. A window is close(s) -> close(s + 60) of SPY's total-return close,
    s the first session after file day t; only complete windows count. The daily exposure series is x_d = T r_d
    (w_rule(d) - w_ctrl(d)) - 2e-4, r_d the session log return and w(d) the share of each group's windows holding day
    d, so mean(x) is exactly the net difference; it is bootstrapped in 60-session blocks. Holm over 3 arms: the vendor
    DIX percentile and high-DIX-with-low-GEX arms need SqueezeMetrics files that are not archived, so they enter Holm as
    p = 1 (the conservative reading: the primary's Holm p is 3 x its p) and the vendor correlation is not computed. The
    drawdown placebo: the first session SPY's total-return close is >= 5% below its 60-session high (t included), entry
    at the next close, 60-session hold, no overlap, entries inside the DIX rule's eligible entry span; costs (2 bps) on
    both rules. The rule trades on its own event calendar, so rule 10 has no grid phase.
  * T-638. Sign: +1 taker buy, -1 taker sell; amount in BTC. Black-76 delta N(d1) (call) or N(d1) - 1 (put), T from the
    trade time to 08:00 UTC of the expiry date in years of 365 days. Trades with a non-positive iv, T, price or amount
    are skipped (counted). A day is used only when its sample-day row says complete. The trailing 60-day median (and
    the 60-day z-score normalisation) use the 60 complete days ending at d (d included). Entry price, two readings (rule
    12): (a) the registered target, the close of the 23:59 Coinbase bar (the day's last print when the bar is missing),
    and (b) the first print at or after 24:00 UTC (the open of the first bar at or after it), which no Deribit trade of
    day d post-dates. Funding, two readings: (s) symmetric, pos x the Deribit BTC-PERPETUAL funding summed over the
    holding day's hourly interest_1h (long pays, short receives), and (c) cost only, |pos x funding|. A holding day
    needs >= 20 hourly funding rows (the sum is scaled to 24 hours). Costs: 5 bps a side on |change in position| (a
    long-short flip is one 10 bp round trip), 10 bps a side at the 20 bp sensitivity. The 3-day horizon holds three
    overlapping thirds (position = mean of the last three signs: every entry phase pooled, rule 10). The deflated p is
    1 - DSR(6 trials) with the trial-Sharpe variance max(observed variance of the 6 trial Sharpes, 1/(T-1)) (the
    zero-skill floor: the conservative reading); the registered block bootstrap p is required as well (rule 11). "IC >
    0" and "residual IC > 0" are read with their HAC t one-sided p < 0.05 (the null names IC <= 0); "both halves
    positive" is read on IC, residual IC and rule net together. The residual is from the full-sample OLS of S on day
    d's own return.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

import numpy as np
from scipy.special import erf, ndtr
from scipy.stats import rankdata

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch13_short_a as SA
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_cryptovenue import early_close
from mandel.experiments.batch6c_rates import hac_mean
from mandel.experiments.panel_cache import daily_panel
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
N_BOOT = CAL.N_BOOT
N_SEEDS = CAL.N_SEEDS
MAX_SEEDS = CAL.MAX_SEEDS
ALPHA = 0.05

# ---- bundles
GSPC_B = "daily-history--GSPC"
SPY_B = "daily-history-SPY"
VIX_B = "cboe-VIX-history"
VIX1D_B = "cboe-VIX1D-history"
FOMC_B = "fomc-meetings"
CPI_B = "macro-release-cpi"
NFP_B = "macro-release-employment-situation"
DTB3_B = "fred-DTB3"
FJA_B = "fja-sp500-components"
CHG_B = "wikipedia-sp500-changes"
CONS_B = "wikipedia-sp500-constituents"
DRB_PREFIX = "deribit-option-trades-near-BTC-"
CB_PREFIX = "coinbase-1m-BTC-USD-"
FUND_B = "deribit-funding-BTC-PERPETUAL"
DVOL_B = "deribit-dvol-BTC-history"

# ---- T-632
T632_START, T632_END = "2014-01-01", "2026-10-31"
T632_FIRST_EXPIRY = {0: "2016-08-22",    # Monday SPXW: first expiries 2016-08-22 / 08-29 (Cboe notice 2016-07-11)
                     1: "2022-04-26",    # Tuesday (registration)
                     2: "2016-03-02",    # Wednesday SPXW: first expiries 2016-03-02 / 03-09 (Cboe RG16-024)
                     3: "2022-05-19",    # Thursday (registration)
                     4: "2005-01-01"}    # every Friday of the 2014+ sample (weeklies since 2005)
T632_BLOCK = 10
T632_MIN_N = 2000
T632_EPISODES = (("2014-01-01", "2018-02-28"), ("2020-04-01", "2024-05-31"))
T632_SENS_DROP = ("2022-05-01", "2022-12-31")
T632_TAU = 1.0 / 252
T632_VIX1D_FROM = ("2023-01-01", "2023-04-24")
PARK = 2.0 * math.sqrt(math.log(2.0))

# ---- T-633
T633_START, T633_END = "2005-01-01", "2026-10-31"
T633_BAND = 0.05
T633_PRICE_MIN = 10.0
T633_BAR = 1.05
T633_SPLIT = "2016-01-01"
T633_MIN_N = 200
T633_DV_WIN = 20
T633_DV_MIN = 10
T633_BLOCK = 12                # months

# ---- T-639
T639_WIN = 252
T639_PCT = 80.0
T639_H = 60
T639_COST = 2e-4               # 2 bps a round trip, per window
T639_BLOCK = 60
T639_MIN_N = 15
T639_SPLIT = "2022-01-01"
T639_ARMS = 3
T639_DD = 0.05
T639_DD_WIN = 60
T639_CHECKPOINT = 40

# ---- T-638
T638_SPLIT = "2025-07-01"
T638_COST_SIDE = 5e-4          # 10 bps a round trip
T638_COST_SIDE_HI = 10e-4      # 20 bps a round trip (sensitivity criterion)
T638_WIN = 60
T638_HAC_LAG = 5
T638_BLOCK = 5
T638_MIN_N = 800
T638_TRIALS = 6
T638_MAX_DTE = 8
T638_FUND_MIN_ROWS = 20
YEAR_S = 365.0 * 86400.0
DAY_S = 86400


# ================================================================================================= statistics ==

def two_sided(pg, pl) -> Optional[float]:
    return None if pg is None or pl is None else float(min(1.0, 2.0 * min(pg, pl)))


def boot_p(d, block: int, stop: Callable, n_boot: Optional[int] = None, seed: int = SEED, n_seeds: int = N_SEEDS,
           max_seeds: int = MAX_SEEDS) -> tuple:
    """(p_greater, p_less, draws) of mean(d) pooled over seeds seed, seed + 1, ... (``batch13_short_a.stud_p``: one set
    of studentized circular block-bootstrap draws per seed); ``n_seeds`` first, then one more seed while ``stop(pg, pl,
    draws)`` is False, up to ``max_seeds``."""
    nb = CAL._nb(n_boot)
    ps = []
    while True:
        ps.append(SA.stud_p(d, block, nb, seed + len(ps)))
        if ps[0][0] is None:
            return None, None, nb * len(ps)
        if len(ps) < max(1, n_seeds):
            continue
        pg = float(np.mean([p[0] for p in ps])); pl = float(np.mean([p[1] for p in ps]))
        nd = nb * len(ps)
        if len(ps) >= max_seeds or stop(pg, pl, nd):
            return pg, pl, nd


def stop_side(side: str, alpha: float = ALPHA) -> Callable:
    return lambda pg, pl, nd: CAL.decide_p(pg if side == "greater" else pl, nd, alpha) is not None


def stop_two(alpha: float = ALPHA) -> Callable:
    return lambda pg, pl, nd: CAL.decide_p(two_sided(pg, pl), nd, alpha) is not None


def never_stop(pg, pl, nd) -> bool:
    return False


def fe_design(days: Sequence[str]) -> np.ndarray:
    """Weekday and year-month fixed effects (one column per weekday present, one per year-month but the first)."""
    wd = np.array([date.fromisoformat(d).weekday() for d in days])
    ym = np.array([d[:7] for d in days])
    cols = [(wd == k).astype(float) for k in np.unique(wd)]
    cols += [(ym == m).astype(float) for m in np.unique(ym)[1:]]
    return np.column_stack(cols)


def fe_slope(y, x, D) -> dict:
    """OLS slope of y on x with the fixed effects D (Frisch-Waugh) and its influence series psi (mean = slope)."""
    y = np.asarray(y, float); x = np.asarray(x, float)
    bx, *_ = np.linalg.lstsq(D, x, rcond=None)
    xt = x - D @ bx
    by, *_ = np.linalg.lstsq(D, y, rcond=None)
    yt = y - D @ by
    q = float(np.mean(xt * xt))
    if not q > 1e-10:
        return {"beta": None, "psi": None, "n": int(y.size), "identifying": 0}
    beta = float(np.sum(xt * yt) / np.sum(xt * xt))
    e = yt - beta * xt
    return {"beta": beta, "psi": beta + xt * e / q, "n": int(y.size), "identifying": int(np.sum(np.abs(xt) > 1e-8))}


def _fmt(x, nd: int = 4) -> str:
    return SA._fmt(x, nd)


def _bp(x, nd: int = 1) -> str:
    return B7C._bp(x, nd)


def _pf(p) -> str:
    return "n/a" if p is None or not np.isfinite(p) else f"{p:.4f}"


# ================================================================================ T-632 SPXW expiry dampening ==

def is_expiry(d: date) -> bool:
    """A PM-settled SPXW expiry is scheduled on weekday ``d`` (the pinned calendar)."""
    wd = d.weekday()
    return wd <= 4 and d.isoformat() >= T632_FIRST_EXPIRY[wd]


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def opex_day(y: int, m: int) -> date:
    """Monthly expiration: the third Friday, or the session before it when the Friday is a holiday."""
    tf = third_friday(y, m)
    return tf if CAL.is_nyse_session(tf) else CAL.prev_session(tf)


def holiday_shifted_controls(first: str, last: str) -> dict:
    """{ISO session: why} of the sessions in [first, last] that carried an SPXW expiry moved off an exchange closure onto a
    weekday with no expiry of its own yet (the pre-switch holiday-shifted expiry days)."""
    lo = (date.fromisoformat(first) - timedelta(days=10)).isoformat()
    hi = (date.fromisoformat(last) + timedelta(days=10)).isoformat()
    hol = list(CAL.scheduled_holidays(lo, hi))
    hol += [(date.fromisoformat(k), v) for k, v in CAL.UNSCHEDULED_CLOSURES.items() if lo <= k <= hi]
    out = {}
    for h, name in sorted(hol):
        if h.weekday() > 4 or not is_expiry(h):
            continue
        if h.isoformat() in CAL.UNSCHEDULED_CLOSURES:
            cands = (CAL.prev_session(h), CAL.next_session(h))
        elif h.weekday() == 0:
            cands = (CAL.next_session(h),)
        else:
            cands = (CAL.prev_session(h),)
        for s in cands:
            if not is_expiry(s) and first <= s.isoformat() <= last:
                out[s.isoformat()] = f"{name} {h.isoformat()}"
    return out


def _session_on_or_after(d: str) -> Optional[str]:
    dd = date.fromisoformat(d)
    if dd.year < CAL.SCHEDULE_FROM:
        return None
    return (dd if CAL.is_nyse_session(dd) else CAL.next_session(dd)).isoformat()


def event_sessions(archive) -> dict:
    """FOMC decision sessions and the first session on or after each CPI / NFP release day (sets of ISO days)."""
    def days(name, field):
        out = set()
        for r in CAL._rows(archive, name):
            v = (r.get("value") or {}).get(field)
            s = _session_on_or_after(v) if v else None
            if s:
                out.add(s)
        return out
    return {"fomc": days(FOMC_B, "decision_day"), "cpi": days(CPI_B, "day"), "nfp": days(NFP_B, "day")}


def gspc_ohlc(archive) -> dict:
    def load():
        by = {}
        for r in CAL._rows(archive, GSPC_B):
            v = r.get("value") or {}
            t = EV._num(v.get("t"))
            if t is None:
                continue
            d = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
            vals = []
            for k in ("open", "high", "low", "close"):
                x = EV._num(v.get(k))
                vals.append(x if x is not None and x > 0 else float("nan"))
            by[d] = vals
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 4)
        return {"days": days, "open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2], "close": arr[:, 3]}
    return CAL._cached(archive, ("b13f_gspc",), load)


def atm_straddle(sigma, tau: float = T632_TAU) -> np.ndarray:
    """Black-Scholes ATM straddle per unit spot at r = q = 0: 2 (2 N(sigma sqrt(tau) / 2) - 1)."""
    s = np.asarray(sigma, float)
    return 2.0 * erf(s * math.sqrt(tau) / (2.0 * math.sqrt(2.0)))


def t632_rows(days, o, h, l, c, vix: dict, events: dict, start: str = T632_START, end: str = T632_END) -> dict:
    """The regression sample: per kept session t, y_t (log Parkinson / VIX_{t-1}-implied daily sigma), the straddle P&L
    per unit premium, Expiry_t and the placebo Expiry_{t-1} (the previous NYSE session's flag); exclusion counts (a row
    can carry several reasons). Every input of row t is known by the close of t; VIX enters at t-1."""
    shifted = holiday_shifted_controls(start, end)
    keep, y, pnl, E, P = [], [], [], [], []
    drop = defaultdict(int)
    for i in range(1, len(days)):
        d = days[i]
        if not (start <= d <= end):
            continue
        dd = date.fromisoformat(d)
        why = []
        if not CAL.is_nyse_session(dd):
            why.append("bar_on_closed_day")
        elif days[i - 1] != CAL.prev_session(dd).isoformat():
            why.append("previous_session_missing")
        if dd == opex_day(dd.year, dd.month):
            why.append("monthly_opex")
        if CAL.next_session(dd).month != dd.month:
            why.append("month_end")
        if d in shifted:
            why.append("holiday_shifted_expiry")
        for k in ("fomc", "cpi", "nfp"):
            if d in events.get(k, ()):
                why.append(k)
        if early_close(d):
            why.append("early_close")
        hi, lo, op, cl, pc = h[i], l[i], o[i], c[i], c[i - 1]
        if not all(np.isfinite(v) and v > 0 for v in (hi, lo, op, cl, pc)):
            why.append("missing_ohlc")
        else:
            if hi <= lo:
                why.append("high_le_low")
            if abs(op - pc) <= 1e-9 * pc:
                why.append("stale_open")
        vp = vix.get(days[i - 1])
        if not (vp is not None and vp > 0):
            why.append("no_prior_vix")
        if why:
            for w in why:
                drop[w] += 1
            drop["any"] += 1
            continue
        sig_imp = vp / 100.0 / math.sqrt(252.0)
        keep.append(d)
        y.append(math.log(math.log(hi / lo) / PARK / sig_imp))
        prem = float(atm_straddle(vp / 100.0))
        pnl.append((prem - abs(cl / pc - 1.0)) / prem)
        E.append(1.0 if is_expiry(dd) else 0.0)
        P.append(1.0 if is_expiry(CAL.prev_session(dd)) else 0.0)
    return {"days": keep, "y": np.array(y), "pnl": np.array(pnl), "E": np.array(E), "P": np.array(P),
            "drop": dict(drop), "shifted": shifted}


def _sub_beta(days, y, x, mask) -> Optional[float]:
    m = np.asarray(mask, bool)
    if m.sum() < 20:
        return None
    ds = [d for d, k in zip(days, m) if k]
    return fe_slope(np.asarray(y)[m], np.asarray(x)[m], fe_design(ds))["beta"]


def b13_flow_spxw_expiry_dampening(archive):
    """T-632."""
    miss = B7C._missing(archive, [GSPC_B, VIX_B, FOMC_B, CPI_B, NFP_B])
    if miss:
        return miss
    g = gspc_ohlc(archive)
    vix = CAL._series(archive, VIX_B)
    R = t632_rows(g["days"], g["open"], g["high"], g["low"], g["close"], vix, event_sessions(archive))
    days, y, pnl, E, P = R["days"], R["y"], R["pnl"], R["E"], R["P"]
    n = len(days)
    if n < 30:
        rows = [("enough sessions to estimate the regression", None, False)]
        v, why, crit = CAL._judge(rows, n, T632_MIN_N, "sessions")
        return _out({"n": n, "drop": R["drop"], "criteria": crit}, n, v, f"only {n} usable sessions — {why}")
    D = fe_design(days)
    main = fe_slope(y, E, D)
    pg, pl, nd = boot_p(main["psi"], T632_BLOCK, stop_side("less"))
    darr = np.array(days)
    eps = [_sub_beta(days, y, E, (darr >= a) & (darr <= b)) for a, b in T632_EPISODES]
    sec = fe_slope(pnl, E, D)
    plc = fe_slope(y, P, D)
    ppg, ppl, pnd = (boot_p(plc["psi"], T632_BLOCK, stop_two()) if plc["beta"] is not None else (None, None, 0))
    p2 = two_sided(ppg, ppl)
    sig_plc = CAL.decide_p(p2, pnd)
    b = main["beta"]
    rows = [((f"beta < 0 with one-sided p < 0.05 (beta {_fmt(b)}, studentized 10-session block bootstrap p "
              f"{CAL._mc(pl, nd)})"), SA.sig(b, pl, nd, ALPHA, "neg"), CAL.decide_p(pg, nd) is True),
            (f"beta < 0 in the 2014-01..2018-02 switch episode (point {_fmt(eps[0])})",
             None if eps[0] is None else bool(eps[0] < 0), False),
            (f"beta < 0 in the 2020-04..2024-05 switch episode (point {_fmt(eps[1])})",
             None if eps[1] is None else bool(eps[1] < 0), False),
            (f"straddle P&L per unit premium coefficient > 0 (point {_fmt(sec['beta'])})",
             None if sec["beta"] is None else bool(sec["beta"] > 0), False),
            ((f"placebo (expiry dummy one session later) not significant at 5% two-sided (beta {_fmt(plc['beta'])}, "
              f"p {CAL._mc(p2, pnd)})"), None if sig_plc is None else (not sig_plc), sig_plc is True)]
    verdict, why, crit = CAL._judge(CAL._undecided(rows), n, T632_MIN_N, "sessions")

    # ---- reported only
    rep = {}
    keep = ~((darr >= T632_SENS_DROP[0]) & (darr <= T632_SENS_DROP[1]))
    wd = np.array([date.fromisoformat(d).weekday() for d in days])
    for key, m in (("drop_2022_05_12", keep), ("drop_fridays", wd != 4)):
        ds = [d for d, k in zip(days, m) if k]
        f = fe_slope(y[m], E[m], fe_design(ds))
        q = boot_p(f["psi"], T632_BLOCK, never_stop, max_seeds=N_SEEDS) if f["beta"] is not None else (None, None, 0)
        rep[key] = {"n": int(m.sum()), "beta": f["beta"], "p_less": q[1]}
    rep["secondary_straddle"] = {"beta": sec["beta"],
                                 "p_greater": boot_p(sec["psi"], T632_BLOCK, never_stop, max_seeds=N_SEEDS)[0]
                                 if sec["beta"] is not None else None}
    rep["episodes"] = {f"{a}..{b_}": v for (a, b_), v in zip(T632_EPISODES, eps)}
    rep["episode_straddle"] = {f"{a}..{b_}": _sub_beta(days, pnl, E, (darr >= a) & (darr <= b_)) for a, b_ in T632_EPISODES}
    cells = {}
    for k, nm in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri")):
        m = wd == k
        cells[nm] = {"n_expiry": int((m & (E == 1)).sum()), "n_no_expiry": int((m & (E == 0)).sum()),
                     "mean_y_expiry": float(y[m & (E == 1)].mean()) if (m & (E == 1)).any() else None,
                     "mean_y_no_expiry": float(y[m & (E == 0)].mean()) if (m & (E == 0)).any() else None}
    rep["weekday_cells"] = cells
    v1 = CAL._series(archive, VIX1D_B) if B7C._has(archive, VIX1D_B) else {}
    gd = g["days"]
    desc = {}
    for lab, frm in zip(("from_2023_01", "from_launch_2023_04_24"), T632_VIX1D_FROM):
        by = defaultdict(list)
        for i in range(1, len(gd)):
            if gd[i] >= frm and gd[i - 1] in v1 and vix.get(gd[i - 1]):
                by[date.fromisoformat(gd[i]).weekday()].append(v1[gd[i - 1]] / vix[gd[i - 1]])
        desc[lab] = {nm: (float(np.mean(by[k])) if by[k] else None) for k, nm in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri"))}
    rep["vix1d_over_vix_by_weekday_of_t"] = desc
    rep["holiday_shifted_dropped"] = R["shifted"]
    ex = R["drop"]
    reason = (f"^GSPC {days[0]}..{days[-1]}, {n} sessions after exclusions ({ex.get('any', 0)} dropped: monthly opex "
              f"{ex.get('monthly_opex', 0)}, month-end {ex.get('month_end', 0)}, holiday-shifted expiry {ex.get('holiday_shifted_expiry', 0)}, "
              f"FOMC {ex.get('fomc', 0)}, CPI {ex.get('cpi', 0)}, NFP {ex.get('nfp', 0)}, early close {ex.get('early_close', 0)}, "
              f"stale open {ex.get('stale_open', 0)}, H<=L {ex.get('high_le_low', 0)}, no prior VIX {ex.get('no_prior_vix', 0)}; "
              f"reasons overlap). y = ln(Parkinson / (VIX_(t-1)/100/sqrt 252)) on Expiry (Fri always; Wed from 2016-03-02, Mon "
              f"from 2016-08-22, Tue from 2022-04-26, Thu from 2022-05-19) with weekday and year-month FE: beta {_fmt(b)} "
              f"(p_less {CAL._mc(pl, nd)}); episodes 2014-01..2018-02 {_fmt(eps[0])}, 2020-04..2024-05 {_fmt(eps[1])}; "
              f"straddle P&L per unit premium beta {_fmt(sec['beta'])}; placebo beta {_fmt(plc['beta'])} (two-sided p "
              f"{_pf(p2)}). Reported: dropping 2022-05..2022-12 beta {_fmt(rep['drop_2022_05_12']['beta'])} (p "
              f"{_pf(rep['drop_2022_05_12']['p_less'])}); dropping Fridays {_fmt(rep['drop_fridays']['beta'])} (p "
              f"{_pf(rep['drop_fridays']['p_less'])}); VIX1D/VIX (t-1) by weekday of t from 2023-04-24: "
              + ", ".join(f"{k} {_pf(v)}" for k, v in desc["from_launch_2023_04_24"].items()))
    stat = {"n": n, "beta": b, "p_less": pl, "p_greater": pg, "draws": nd, "episodes": eps, "straddle_beta": sec["beta"],
            "placebo_beta": plc["beta"], "placebo_p_two_sided": p2, "placebo_draws": pnd, "exclusions": ex,
            "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# =========================================================================== T-633 single-stock opex pinning ==

def coarse_spacing(p) -> np.ndarray:
    p = np.asarray(p, float)
    return np.where(p < 25.0, 2.5, np.where(p < 200.0, 5.0, 10.0))


def fine_spacing(p) -> np.ndarray:
    p = np.asarray(p, float)
    return np.where(p < 50.0, 1.0, np.where(p < 100.0, 2.5, 5.0))


def band_hits(p, spacing: Callable = coarse_spacing, band: float = T633_BAND) -> np.ndarray:
    """|p - nearest multiple of the local spacing| / spacing <= band."""
    p = np.asarray(p, float)
    s = spacing(p)
    return np.abs(p - s * np.round(p / s)) / s <= band + 1e-9


def t633_pairs(start: str = T633_START, end: str = T633_END) -> tuple:
    """([(day, base day, is_opex)], [skipped (day, why, is_opex)]): every Friday session with its calendar Thursday a
    session, and the holiday-shifted opex Thursday with the session before it."""
    pairs, skipped = [], []
    d = date.fromisoformat(start)
    d += timedelta(days=(4 - d.weekday()) % 7)
    e = date.fromisoformat(end)
    while d <= e:
        od = opex_day(d.year, d.month)
        if CAL.is_nyse_session(d):
            th = d - timedelta(days=1)
            if CAL.is_nyse_session(th):
                pairs.append((d.isoformat(), th.isoformat(), d == od))
            else:
                skipped.append((d.isoformat(), "its Thursday is a holiday", d == od))
        elif d == third_friday(d.year, d.month):
            pairs.append((od.isoformat(), CAL.prev_session(od).isoformat(), True))
        d += timedelta(days=7)
    return pairs, skipped


def trailing_mean(X: np.ndarray, win: int = T633_DV_WIN, min_obs: int = T633_DV_MIN) -> np.ndarray:
    """Per column, the NaN-aware mean of the last ``win`` rows ending at each row (row included); NaN with fewer than
    ``min_obs`` finite values. Row r uses rows r - win + 1 .. r only."""
    X = np.asarray(X, float)
    ok = np.isfinite(X)
    S = np.vstack([np.zeros((1, X.shape[1])), np.cumsum(np.where(ok, X, 0.0), axis=0)])
    N = np.vstack([np.zeros((1, X.shape[1])), np.cumsum(ok, axis=0)])
    lo = np.maximum(np.arange(X.shape[0]) + 1 - win, 0)
    s = S[1:] - S[lo]
    c = N[1:] - N[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c >= min_obs, s / np.where(c > 0, c, 1.0), np.nan)


def split_factors(splits: Sequence[tuple], days: Sequence[str]) -> np.ndarray:
    """Per day, the product of the split ratios with an ex-date after it (raw close = split-adjusted close x this)."""
    f = np.ones(len(days))
    dd = np.array(days)
    for ex, ratio in splits:
        f[dd < ex] *= ratio
    return f


def _splits(archive, sym: str) -> list:
    name = "daily-events-" + sym
    if not B7C._has(archive, name):
        return []
    out = []
    for r in SX._stream(archive, name):
        v = r.get("value") or {}
        if (r.get("kind") or v.get("type")) != "split":
            continue
        nu, de = EV._num(v.get("numerator")), EV._num(v.get("denominator"))
        ex = v.get("ex_date")
        if ex and nu and de and nu > 0 and de > 0:
            out.append((str(ex)[:10], nu / de))
    return sorted(out)


def ratio_R(hf, hb, opex, mask=None) -> Optional[float]:
    """[sum hf / sum hb over opex] / [sum hf / sum hb over other] on ``mask``."""
    hf, hb, o = np.asarray(hf, float), np.asarray(hb, float), np.asarray(opex, bool)
    m = np.ones(o.size, bool) if mask is None else np.asarray(mask, bool)
    a, b = hf[m & o].sum(), hb[m & o].sum()
    c, d = hf[m & ~o].sum(), hb[m & ~o].sum()
    if min(a, b, c, d) <= 0:
        return None
    return float((a / b) / (c / d))


def perm_R(hf, hb, opex, years, obs: float, n_perm: Optional[int] = None, seed: int = SEED) -> tuple:
    """(p_greater, p_less, draws) of R with the opex label permuted across dates within each calendar year."""
    hf, hb = np.asarray(hf, float), np.asarray(hb, float)
    lab = np.asarray(opex, bool).astype(np.int8)
    HF, HB = hf.sum(), hb.sum()

    def batch(j):
        dr = []
        for L in CAL.permuted_labels(lab, years, n_perm, seed + j):
            Lf = L.astype(float)
            a, b = Lf @ hf, Lf @ hb
            with np.errstate(invalid="ignore", divide="ignore"):
                dr.append((a / b) / ((HF - a) / (HB - b)))
        d = np.concatenate(dr)
        return CAL._perm_p(obs, d[np.isfinite(d)])

    return CAL.escalate_p(batch, CAL._np(n_perm), 1, CAL.MAX_PERM_BATCHES)


def month_psi(hf, hb, opex, months, bar: float = T633_BAR) -> np.ndarray:
    """Per month, the delta-method influence series of ln R minus ln(bar): its mean is ln R - ln(bar) exactly."""
    hf, hb, o = np.asarray(hf, float), np.asarray(hb, float), np.asarray(opex, bool)
    um, inv = np.unique(np.asarray(months), return_inverse=True)
    a = np.bincount(inv, weights=np.where(o, hf, 0.0), minlength=um.size)
    b = np.bincount(inv, weights=np.where(o, hb, 0.0), minlength=um.size)
    c = np.bincount(inv, weights=np.where(~o, hf, 0.0), minlength=um.size)
    d = np.bincount(inv, weights=np.where(~o, hb, 0.0), minlength=um.size)
    lr = math.log((a.sum() / b.sum()) / (c.sum() / d.sum()))
    return lr - math.log(bar) + a / a.mean() - b / b.mean() - c / c.mean() + d / d.mean()


def pin_panel(archive) -> dict:
    """Per (day, base day) pair: band hits on both days (declared and finer grid), name counts, dollar-volume tercile
    hits, members and priced members; plus the universe table."""
    def load():
        P = daily_panel(archive)
        fja = EV._rows(archive, FJA_B)
        chg = [r.get("value") or {} for r in EV._rows(archive, CHG_B)]
        cons = [r.get("value") or {} for r in EV._rows(archive, CONS_B)] if B7C._has(archive, CONS_B) else []
        snaps = EV.membership_snapshots(fja, chg)
        refs = EV._ref_names(cons, chg)
        pairs, skipped = t633_pairs()
        last = str(P.days[-1])
        pairs = [p for p in pairs if p[0] <= last]
        tick = set()
        j0 = bisect.bisect_right([s[0] for s in snaps], EV._ed("2004-12-01")) - 1
        for e, s in snaps[max(j0, 0):]:              # the snapshot in force on 2004-12-01 and every later one
            tick |= s
        pcol = {s: j for j, s in enumerate(P.symbols.tolist())}
        status, use = {}, {}
        for t in sorted(tick):
            s = EV.ysym(t)
            if s not in pcol:
                status[t] = "no archived daily history"
                continue
            meta = SX._meta(archive, "daily-history-" + s)
            if meta.get("instrumentType") != "EQUITY":
                status[t] = "Yahoo series is not an EQUITY (reused ticker)"
                continue
            nm = meta.get("longName") or ""
            rf = [r for r in refs.get(t, []) if r]
            if nm and rf and not any(EV.name_match(nm, r, t) for r in rf):
                status[t] = "Yahoo name does not match the index's (reused ticker)"
                continue
            status[t] = "ok"
            use[t] = s
        tk = sorted(use)
        cols = np.array([pcol[use[t]] for t in tk], int)
        tpos = {t: k for k, t in enumerate(tk)}
        sess_rows = np.array([i for i, d in enumerate(P.days.tolist()) if d >= "2004-10-01" and CAL.is_nyse_session(d)], int)
        sdays = P.days[sess_rows].tolist()
        spos = {d: k for k, d in enumerate(sdays)}
        Cl = P.close[np.ix_(sess_rows, cols)]
        DV = trailing_mean(Cl * P.volume[np.ix_(sess_rows, cols)])
        need = sorted({d for p in pairs for d in p[:2]})
        npos = {d: k for k, d in enumerate(need)}
        Fm = np.ones((len(need), len(tk)))
        for k, t in enumerate(tk):
            sp = _splits(archive, use[t])
            if sp:
                Fm[:, k] = split_factors(sp, need)
        eds = [s[0] for s in snaps]

        def members(d):
            j = bisect.bisect_right(eds, EV._ed(d)) - 1
            return snaps[j][1] if j >= 0 else frozenset()
        rec = defaultdict(list)
        for f, b, o in pairs:
            if f not in spos or b not in spos:
                continue
            mf, mb = members(f), members(b)
            both = mf & mb
            idx = np.array(sorted(tpos[t] for t in both if t in tpos), int)
            pf = Cl[spos[f], idx] * Fm[npos[f], idx] if idx.size else np.zeros(0)
            pb = Cl[spos[b], idx] * Fm[npos[b], idx] if idx.size else np.zeros(0)
            ok = np.isfinite(pf) & np.isfinite(pb) & (pb >= T633_PRICE_MIN)
            pf, pb = pf[ok], pb[ok]
            hf, hb = band_hits(pf), band_hits(pb)
            dv = DV[spos[b], idx][ok]
            fin = np.isfinite(dv)
            top = np.zeros(ok.sum(), bool); bot = np.zeros(ok.sum(), bool)
            if fin.sum() >= 3:
                q1, q2 = np.quantile(dv[fin], [1 / 3, 2 / 3])
                top, bot = fin & (dv > q2), fin & (dv <= q1)
            rec["day"].append(f); rec["base"].append(b); rec["opex"].append(bool(o))
            rec["members"].append(len(both)); rec["priced"].append(int(np.sum(np.isfinite(Cl[spos[b], idx])))
                                                                  if idx.size else 0)
            rec["n"].append(int(ok.sum())); rec["hf"].append(int(hf.sum())); rec["hb"].append(int(hb.sum()))
            hf2, hb2 = band_hits(pf, fine_spacing), band_hits(pb, fine_spacing)
            rec["hf_fine"].append(int(hf2.sum())); rec["hb_fine"].append(int(hb2.sum()))
            rec["hf_top"].append(int((hf & top).sum())); rec["hb_top"].append(int((hb & top).sum()))
            rec["hf_bot"].append(int((hf & bot).sum())); rec["hb_bot"].append(int((hb & bot).sum()))
        out = {k: np.array(v) for k, v in rec.items()}
        out["status"] = status
        out["skipped"] = skipped
        return out
    return CAL._cached(archive, ("b13f_pin",), load)


def b13_flow_opex_strike_pinning(archive):
    """T-633."""
    miss = B7C._missing(archive, [FJA_B, CHG_B, "daily-history-AAPL", "daily-events-AAPL"])
    if miss:
        return miss
    T = pin_panel(archive)
    day, o = T["day"], T["opex"].astype(bool)
    hf, hb = T["hf"].astype(float), T["hb"].astype(float)
    n = int(o.sum())
    years = np.array([int(d[:4]) for d in day])
    months = np.array([d[:7] for d in day])
    R = ratio_R(hf, hb, o)
    if R is None:
        rows = [("R computable (band hits on both groups)", None, False)]
        v, why, crit = CAL._judge(rows, n, T633_MIN_N, "opex dates")
        return _out({"n": n, "criteria": crit}, n, v, f"R not computable — {why}")
    pg, pl, nd = perm_R(hf, hb, o, years, R)
    psi = month_psi(hf, hb, o, months)
    bg, bl, bd = boot_p(psi, T633_BLOCK, stop_side("greater"))
    early = np.array([d < T633_SPLIT for d in day])
    R1, R2 = ratio_R(hf, hb, o, early), ratio_R(hf, hb, o, ~early)
    Rt = ratio_R(T["hf_top"], T["hb_top"], o)
    Rb = ratio_R(T["hf_bot"], T["hb_bot"], o)
    perm_ok = SA.sig(R - T633_BAR, pg, nd, ALPHA, "pos")
    boot_ok = SA.sig(R - T633_BAR, bg, bd, ALPHA, "pos")
    rows = [((f"R > 1.05 with permutation p < 0.05 (R {_fmt(R)}, within-year permutation p {CAL._mc(pg, nd)}; "
              f"registered month block bootstrap of H0 R <= 1.05, 12-month blocks, p {CAL._mc(bg, bd)}: both readings)"),
             CAL._agree([perm_ok, boot_ok]),
             bool(CAL.decide_p(pl, nd) is True and CAL.decide_p(bl, bd) is True)),
            (f"R > 1 in 2005-2015 and in 2016-2026 ({_fmt(R1)} / {_fmt(R2)})",
             None if R1 is None or R2 is None else bool(R1 > 1 and R2 > 1), False),
            (f"R in the top dollar-volume tercile above R in the bottom tercile ({_fmt(Rt)} vs {_fmt(Rb)})",
             None if Rt is None or Rb is None else bool(Rt > Rb), False)]
    verdict, why, crit = CAL._judge(CAL._undecided(rows), n, T633_MIN_N, "opex dates")

    # ---- reported
    by_year = {}
    for y_ in sorted(set(years.tolist())):
        m = years == y_
        by_year[str(y_)] = {"R": ratio_R(hf, hb, o, m), "opex_dates": int((m & o).sum()), "other_fridays": int((m & ~o).sum()),
                            "mean_members": float(T["members"][m].mean()), "mean_priced_members": float(T["priced"][m].mean()),
                            "mean_names_used": float(T["n"][m].mean()),
                            "coverage_priced_over_members": float(T["priced"][m].sum() / max(T["members"][m].sum(), 1))}
    h_rates = {"opex_day": float(hf[o].sum() / T["n"][o].sum()), "opex_base": float(hb[o].sum() / T["n"][o].sum()),
               "other_fri": float(hf[~o].sum() / T["n"][~o].sum()), "other_thu": float(hb[~o].sum() / T["n"][~o].sum())}
    R_fine = ratio_R(T["hf_fine"], T["hb_fine"], o)
    dpos = {d: i for i, d in enumerate(day.tolist())}
    placebo = {}
    for shift in (-14, -7, 7):                      # the Friday 2 / 1 weeks before and 1 week after each opex Friday
        lab = np.zeros(o.size, bool)
        for d in day[o].tolist():
            k = dpos.get((date.fromisoformat(d) + timedelta(days=shift)).isoformat())
            if k is not None:
                lab[k] = True
        placebo[f"{shift:+d}d"] = {"n": int((lab & ~o).sum()), "R": ratio_R(hf[~o], hb[~o], lab[~o])}
    qtr = np.array([int(d[5:7]) in (3, 6, 9, 12) for d in day])
    split_q = {"quarterly_opex": ratio_R(hf[qtr | ~o], hb[qtr | ~o], o[qtr | ~o]),
               "monthly_only_opex": ratio_R(hf[~qtr | ~o], hb[~qtr | ~o], o[~qtr | ~o])}
    blocks = {f"{k}m": boot_p(psi, k, never_stop, max_seeds=N_SEEDS)[0] for k in (1, 3, 6, 24)}
    p_vs_1 = boot_p(month_psi(hf, hb, o, months, bar=1.0), T633_BLOCK, never_stop, max_seeds=N_SEEDS)[0]
    st = T["status"]
    stc = {k: sum(1 for v in st.values() if v == k) for k in sorted(set(st.values()))}
    yrs_pos = sum(1 for v in by_year.values() if v["R"] is not None and v["R"] > 1)
    cov = [v["coverage_priced_over_members"] for v in by_year.values()]
    reason = (f"{n} monthly opex dates and {int((~o).sum())} other Fridays {day[0]}..{day[-1]} (point-in-time S&P 500 members "
              f"priced >= $10 on the Thursday, raw closes rebuilt from splits; grid $2.50/<$25, $5/<$200, $10 above; band "
              f"0.05 of the spacing). Band-hit shares: opex day {h_rates['opex_day']:.4f} vs its Thursday "
              f"{h_rates['opex_base']:.4f}; other Fridays {h_rates['other_fri']:.4f} vs Thursdays {h_rates['other_thu']:.4f}; "
              f"R {_fmt(R)} (within-year permutation p {_pf(pg)}, month bootstrap vs 1.05 p {_pf(bg)}); 2005-2015 "
              f"{_fmt(R1)}, 2016-2026 {_fmt(R2)}; top / bottom dollar-volume tercile {_fmt(Rt)} / {_fmt(Rb)}; finer grid "
              f"($1/<$50, $2.50/<$100, $5 above, sensitivity) {_fmt(R_fine)}; R > 1 in {yrs_pos} of {len(by_year)} years. "
              f"Reported (not criteria): placebo labels on the Fridays " + ", ".join(f"{k} R {_fmt(v['R'])}" for k, v in placebo.items())
              + f" of each opex; quarterly opex R {_fmt(split_q['quarterly_opex'])}, monthly-only {_fmt(split_q['monthly_only_opex'])}; "
              f"month bootstrap vs 1.05 at other block lengths " + ", ".join(f"{k} p {_pf(v)}" for k, v in blocks.items())
              + f" (12 months declared); vs R = 1 p {_pf(p_vs_1)}. "
              f"SURVIVORSHIP: prices come from the archive's 901-symbol daily-history set (today's universe): "
              f"{stc.get('ok', 0)} of {len(st)} tickers that were members since 2005 are usable, priced members per date "
              f"{min(cov) * 100:.0f}%..{max(cov) * 100:.0f}% of members by year (lowest early); leavers are under-represented")
    stat = {"n": n, "n_other": int((~o).sum()), "R": R, "perm_p_greater": pg, "perm_draws": nd, "boot_p_greater": bg,
            "boot_draws": bd, "R_halves": [R1, R2], "R_top": Rt, "R_bottom": Rb, "R_fine_grid": R_fine, "h_rates": h_rates,
            "by_year": by_year, "ticker_status": stc, "skipped_pairs": T["skipped"], "criteria": crit,
            "reported": {"placebo_weeks": placebo, "quarterly_split": split_q, "boot_p_other_blocks": blocks,
                         "boot_p_vs_1": p_vs_1}}
    return _out(stat, n, verdict, reason + " — " + why)


# ===================================================================================== T-639 rebuilt DIX, SPY ==

def pct_flag_incl(x, win: int = T639_WIN, pct: float = T639_PCT) -> tuple:
    """(flag, defined): x_t at or above the ``pct`` percentile (numpy linear) of the ``win`` finite values ending at t
    (t included); defined from the ``win``-th finite value."""
    x = np.asarray(x, float)
    flag = np.zeros(x.size, bool)
    dfd = np.zeros(x.size, bool)
    idx = np.flatnonzero(np.isfinite(x))
    v = x[idx]
    for k in range(win - 1, idx.size):
        w = v[k - win + 1:k + 1]
        dfd[idx[k]] = True
        flag[idx[k]] = v[k] >= np.percentile(w, pct)
    return flag, dfd


def first_crossings(flag, defined) -> np.ndarray:
    """The first day of each run of ``flag``: flagged, with the previous defined day defined and not flagged."""
    flag, defined = np.asarray(flag, bool), np.asarray(defined, bool)
    out = np.zeros(flag.size, bool)
    prev = None
    for k in np.flatnonzero(defined):
        if prev is not None and flag[k] and not flag[prev]:
            out[k] = True
        prev = k
    return out


def rule_entries(trig, s_idx, H: int, ncal: int) -> np.ndarray:
    """Positions k (in time order) of the triggers entered: entry session s_idx[k], exit s_idx[k] + H < ncal, and no
    position open (the previous exit at or before the entry)."""
    trig = np.asarray(trig, bool)
    s_idx = np.asarray(s_idx)
    out, free = [], -1
    for k in np.flatnonzero(trig):
        s = int(s_idx[k])
        if s < 0 or s + H >= ncal:
            continue
        if s >= free:
            out.append(k)
            free = s + H
    return np.array(out, int)


def window_returns(adj, s_idx, H: int = T639_H) -> np.ndarray:
    adj = np.asarray(adj, float)
    s = np.asarray(s_idx)
    out = np.full(s.size, np.nan)
    ok = (s >= 0) & (s + H < adj.size)
    out[ok] = np.log(adj[s[ok] + H] / adj[s[ok]])
    return out


def exposure_series(adj, starts_a, starts_b, H: int = T639_H, cost: float = T639_COST) -> tuple:
    """(x, span) with mean(x) = mean window log return of group a - cost - that of group b (window = close s -> close
    s + H, covering session returns s + 1 .. s + H), over the sessions from the first window's first day to the last
    window's last day."""
    adj = np.asarray(adj, float)
    lr = np.full(adj.size, np.nan)
    lr[1:] = np.log(adj[1:] / adj[:-1])
    ca = np.zeros(adj.size + H + 2)
    cb = np.zeros(adj.size + H + 2)
    for s in starts_a:
        ca[s + 1] += 1; ca[s + H + 1] -= 1
    for s in starts_b:
        cb[s + 1] += 1; cb[s + H + 1] -= 1
    wa = np.cumsum(ca)[:adj.size] / max(len(starts_a), 1)
    wb = np.cumsum(cb)[:adj.size] / max(len(starts_b), 1)
    allst = np.concatenate([np.asarray(starts_a, int), np.asarray(starts_b, int)])
    lo, hi = int(allst.min()) + 1, int(allst.max()) + H
    T = hi - lo + 1
    x = T * lr[lo:hi + 1] * (wa[lo:hi + 1] - wb[lo:hi + 1]) - cost
    return x, (lo, hi)


def drawdown_triggers(adj, win: int = T639_DD_WIN, thr: float = T639_DD) -> np.ndarray:
    """First session of each run with the close >= thr below the max of the ``win`` closes ending at it (t included)."""
    adj = np.asarray(adj, float)
    n = adj.size
    cond = np.zeros(n, bool)
    dfd = np.zeros(n, bool)
    for i in range(win - 1, n):
        hi = np.nanmax(adj[i - win + 1:i + 1])
        dfd[i] = np.isfinite(adj[i])
        cond[i] = dfd[i] and adj[i] / hi - 1.0 <= -thr
    return first_crossings(cond, dfd)


def dix_reading(x, file_days, cal, adj, ctrl: str) -> dict:
    """One T-639 reading: DIX series ``x`` on the CNMS file days, control set 'A' (below-percentile days) or 'B' (every
    eligible day that is not an entry)."""
    flag, dfd = pct_flag_incl(x)
    ncal = cal.size
    s_idx = np.searchsorted(cal, np.asarray(file_days, np.int64), side="right")
    s_idx = np.where(s_idx < ncal, s_idx, -1)
    complete = (s_idx >= 0) & (s_idx + T639_H < ncal)
    elig = dfd & complete
    trig = first_crossings(flag, dfd) & elig
    ent = rule_entries(trig, s_idx, T639_H, ncal)
    emask = np.zeros(flag.size, bool); emask[ent] = True
    cmask = (elig & ~flag) if ctrl == "A" else (elig & ~emask)
    R = window_returns(adj, s_idx)
    out = {"n": int(ent.size), "n_triggers": int(trig.sum()), "n_control": int(cmask.sum()),
           "first_eligible": EV._iso(file_days[np.flatnonzero(elig)[0]]) if elig.any() else None,
           "last_eligible": EV._iso(file_days[np.flatnonzero(elig)[-1]]) if elig.any() else None,
           "entries": [(EV._iso(cal[s_idx[k]]), float(R[k])) for k in ent],
           "s_idx": s_idx, "elig": elig, "entry_idx": ent, "signal_share": float(flag[elig].mean()) if elig.any() else None}
    if ent.size < 2 or cmask.sum() < 2:
        return out
    mr, mc = float(R[ent].mean()), float(R[cmask].mean())
    out.update(mean_rule=mr, mean_rule_net=mr - T639_COST, mean_control=mc, diff_net=mr - T639_COST - mc)
    x_exp, span = exposure_series(adj, s_idx[ent], s_idx[cmask])
    out["exposure_mean_check"] = float(x_exp.mean())
    pg, pl, nd = boot_p(x_exp, T639_BLOCK, stop_side("greater", ALPHA / T639_ARMS))
    out.update(p_greater=pg, p_less=pl, draws=nd, p_holm=None if pg is None else min(1.0, T639_ARMS * pg),
               span=(EV._iso(cal[span[0]]), EV._iso(cal[span[1]])))
    ent_day = np.array([EV._iso(cal[s]) if s >= 0 else "9999" for s in s_idx])
    halves = {}
    for lab, m in (("2019-08..2021-12", ent_day < T639_SPLIT), ("2022-01..2026-10", ent_day >= T639_SPLIT)):
        a, c = ent[m[ent]], cmask & m
        halves[lab] = (float(R[a].mean() - T639_COST - R[c].mean()) if a.size and c.any() else None)
    out["halves"] = halves
    return out


def b13_flow_dix_rebuild_p80_60d(archive):
    """T-639."""
    miss = B7C._missing(archive, [SA.SPY_B, SA.DTB3_B, SA.FJA_B, SA.CHG_B, SA.CNMS_FMT.format(SA.CNMS_FIRST)])
    if miss:
        return miss
    B = SA.base(archive)
    C = B["C"]
    sp = SA._spy(archive)
    cal, adj = sp["cal"], sp["adj"]
    pr = SA.member_prices(archive)
    reads, dixes = {}, {}
    for plab, Pm in (("split_adjusted", pr["PA"]), ("as_traded", pr["PA"] * pr["F"])):
        xd, share, npriced = SA.dw_ratio(C["SV"], C["TV"], B["M"], Pm)
        dixes[plab] = {"x": xd, "share": share, "npriced": npriced}
        for ctrl in ("A", "B"):
            reads[f"{plab}/{ctrl}"] = dix_reading(xd, C["days"], cal, adj, ctrl)
    # drawdown placebo over the DIX rule's eligible entry span
    r0 = reads["as_traded/A"]
    lo_s = int(r0["s_idx"][np.flatnonzero(r0["elig"])[0]]) if r0["elig"].any() else 0
    hi_s = int(r0["s_idx"][np.flatnonzero(r0["elig"])[-1]]) if r0["elig"].any() else -1
    ddt = drawdown_triggers(adj)
    s_dd = np.arange(adj.size) + 1
    in_span = (s_dd >= lo_s) & (s_dd <= hi_s)
    dd_ent = rule_entries(ddt & in_span, np.where(s_dd < adj.size, s_dd, -1), T639_H, adj.size)
    Rdd = window_returns(adj, s_dd[dd_ent]) if dd_ent.size else np.zeros(0)
    dd_mean = float(Rdd.mean() - T639_COST) if Rdd.size else None
    sec = {}
    for plab in ("split_adjusted", "as_traded"):
        r = reads[f"{plab}/A"]
        sec[plab] = (None if dd_mean is None or r.get("mean_rule_net") is None else float(r["mean_rule_net"] - dd_mean))
    n = min(r["n"] for r in reads.values())
    keys = list(reads)
    alpha_h = ALPHA / T639_ARMS
    prim = [SA.sig(reads[k].get("diff_net"), reads[k].get("p_greater"), reads[k].get("draws", 1), alpha_h, "pos") for k in keys]
    prim_dec = all(CAL.decide_p(reads[k].get("p_less"), reads[k].get("draws", 1), alpha_h) is True for k in keys)
    halves_ok = []
    for k in keys:
        hv = list((reads[k].get("halves") or {}).values())
        halves_ok.append(None if len(hv) < 2 or any(v is None for v in hv) else all(v > 0 for v in hv))
    sec_ok = [None if v is None else bool(v > 0) for v in sec.values()]

    def cell(k, f):
        return f"{k} {f(reads[k])}"
    rows = [("rule-window mean minus non-signal-window mean, net of 2 bps, > 0 with Holm one-sided p < 0.05 over 3 arms "
             "(vendor-DIX and high-DIX/low-GEX arms not archived: p = 1, so Holm p = 3p; readings price/control: "
             + "; ".join(cell(k, lambda r: f"{_bp(r.get('diff_net'))}, Holm p {_pf(r.get('p_holm'))}") for k in keys) + ")",
             CAL._agree(prim), prim_dec),
            ("rule-window mean minus the drawdown-placebo rule's window mean > 0 ("
             + "; ".join(f"{k} {_bp(v)}" for k, v in sec.items()) + f"; placebo {dd_ent.size} windows)",
             CAL._agree(sec_ok), False),
            ("primary difference > 0 in 2019-08..2021-12 and 2022-01..2026-10 by entry date ("
             + "; ".join(cell(k, lambda r: " / ".join(_bp(v) for v in (r.get("halves") or {}).values())) for k in keys) + ")",
             CAL._agree(halves_ok), False)]
    verdict, why, crit = CAL._judge(CAL._undecided(rows), n, T639_MIN_N, "rule windows")

    # ---- reported
    D = dixes["as_traded"]
    el = reads["as_traded/A"]["elig"]
    sh = D["share"][el]
    st = pr["status"]
    unpriced = sorted(s for s, v in st.items() if not v.startswith("ok"))
    flat_any = {}
    for plab in ("split_adjusted", "as_traded"):
        flag, _ = pct_flag_incl(dixes[plab]["x"])
        r = reads[f"{plab}/A"]
        e2 = rule_entries(flag & r["elig"], r["s_idx"], T639_H, cal.size)
        R2 = window_returns(adj, r["s_idx"][e2])
        flat_any[plab] = {"n": int(e2.size), "mean_net": float(R2.mean() - T639_COST) if e2.size else None}
    rep = {"coverage_unpriced_share_of_member_offexchange_volume": {"median": float(np.nanmedian(sh)), "max": float(np.nanmax(sh))},
           "symbol_status": {k: sum(1 for v in st.values() if v == k) for k in sorted(set(st.values()))},
           "unpriced_symbols": unpriced, "drawdown_placebo": {"n": int(dd_ent.size), "mean_net": dd_mean,
                                                              "entries": [EV._iso(cal[s]) for s in s_dd[dd_ent]]},
           "any_signal_day_when_flat_variant": flat_any, "vendor_dix_correlation": None,
           "vendor_arms": "SqueezeMetrics DIX/GEX not archived: arms 2 and 3 not computed (Holm p = 1)",
           "provisional": f"forward checkpoint at {T639_CHECKPOINT} windows ({n} now)"}
    A = reads["as_traded/A"]
    reason = (f"rebuilt DIX (FINRA CNMS, dollar-weighted over point-in-time S&P 500 members with an archived close), "
              f"eligible file days {A.get('first_eligible')}..{A.get('last_eligible')}; rule (first day at/above the "
              f"trailing-252-file-day 80th percentile, t included; SPY at the t+1 close for 60 sessions, no overlap): "
              f"{A['n']} windows of {A['n_triggers']} triggers, mean net {_bp(A.get('mean_rule_net'))} vs non-signal "
              f"windows {_bp(A.get('mean_control'))} (as-traded close, control A), difference {_bp(A.get('diff_net'))} "
              f"(p {_pf(A.get('p_greater'))}, Holm x3 {_pf(A.get('p_holm'))}); other readings "
              + "; ".join(f"{k} {_bp(reads[k].get('diff_net'))}" for k in keys if k != "as_traded/A")
              + f"; drawdown placebo {dd_ent.size} windows mean net {_bp(dd_mean)}; halves (as-traded/A) "
              + " / ".join(f"{k} {_bp(v)}" for k, v in (A.get("halves") or {}).items())
              + f". Provisional: {n} windows, forward checkpoint at {T639_CHECKPOINT}. SURVIVORSHIP: member closes come "
              f"from the archive's 901-symbol daily-history set (today's universe); {len(unpriced)} of {len(st)} member "
              f"symbols lack a usable close and drop out of both sums (median {rep['coverage_unpriced_share_of_member_offexchange_volume']['median'] * 100:.1f}%, "
              f"max {rep['coverage_unpriced_share_of_member_offexchange_volume']['max'] * 100:.1f}% of member off-exchange "
              f"volume). Vendor DIX/GEX arms and the rebuilt-vs-vendor correlation need SqueezeMetrics files that are not "
              f"archived")
    clean = {k: {kk: vv for kk, vv in r.items() if kk not in ("s_idx", "elig", "entry_idx")} for k, r in reads.items()}
    stat = {"n": n, "readings": clean, "secondary_vs_drawdown": sec, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


# ============================================================================ T-638 Deribit signed delta flow ==

def b76_delta(F, K, T, sigma, is_put) -> np.ndarray:
    """Black-76 (undiscounted) delta: N(d1) for a call, N(d1) - 1 for a put."""
    F, K, T, s = (np.asarray(v, float) for v in (F, K, T, sigma))
    d1 = (np.log(F / K) + 0.5 * s * s * T) / (s * np.sqrt(T))
    return ndtr(d1) - np.asarray(is_put, float)


def flow_aggregate(ts_ms, iv_pct, F, K, is_put, sign, amount, expiry_ed) -> tuple:
    """Per UTC day of the trade: (days, N = sum sign a delta, A = sum |a delta|, C = sum a, count) over valid trades in
    expiries 0..8 days after the trade's day; and the count of skipped trades. Each day uses only its own trades."""
    ts = np.asarray(ts_ms, float)
    day = np.floor(ts / 86400000.0).astype(np.int64)
    exp_ed = np.asarray(expiry_ed, np.int64)
    T = ((exp_ed * DAY_S + 8 * 3600) - ts / 1000.0) / YEAR_S
    sig = np.asarray(iv_pct, float) / 100.0
    F, K, a = (np.asarray(v, float) for v in (F, K, amount))
    dte = exp_ed - day
    ok = (np.isfinite(sig) & (sig > 0) & np.isfinite(T) & (T > 0) & (F > 0) & (K > 0) & (a > 0)
          & (dte >= 0) & (dte <= T638_MAX_DTE))
    with np.errstate(invalid="ignore", divide="ignore"):
        dl = b76_delta(np.where(ok, F, 1.0), np.where(ok, K, 1.0), np.where(ok, T, 1.0), np.where(ok, sig, 1.0),
                       np.asarray(is_put, bool))
    ok &= np.isfinite(dl)
    if not ok.any():
        return np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, int), int((~ok).sum())
    ud, inv = np.unique(day[ok], return_inverse=True)
    ad = a[ok] * dl[ok]
    N = np.bincount(inv, weights=np.asarray(sign, float)[ok] * ad)
    A = np.bincount(inv, weights=np.abs(ad))
    Cn = np.bincount(inv, weights=a[ok])
    cnt = np.bincount(inv)
    return ud, N, A, Cn, cnt, int((~ok).sum())


def deribit_flow(archive) -> dict:
    """Daily flow aggregates over every near-expiry trade bundle, and the complete flag of each sample day."""
    def load():
        names = SX._entry_names(archive, DRB_PREFIX)
        complete = {}
        agg = defaultdict(lambda: np.zeros(4))
        skipped = bad = 0
        ecache = {}
        for nm in names:
            keep = EV._avail_filter(archive, nm)
            ts, iv, Fs, Ks, put, sg, am, ex = [], [], [], [], [], [], [], []
            for r in archive.load(nm):
                if not keep(r):
                    continue
                k = r.get("kind")
                v = r.get("value") or {}
                if k == "sample-day":
                    d = v.get("day")
                    if d:
                        complete[d] = complete.get(d, True) and bool(v.get("complete"))
                    continue
                if k != "option-trade":
                    continue
                dirn, typ, e = v.get("direction"), v.get("type"), v.get("expiry")
                t_, i_, f_, k_, a_ = (EV._num(v.get(f)) for f in ("timestamp", "iv", "index_price", "strike", "amount"))
                if dirn not in ("buy", "sell") or typ not in ("call", "put") or not e or None in (t_, i_, f_, k_, a_):
                    bad += 1
                    continue
                if e not in ecache:
                    ecache[e] = EV._ed(e[:10])
                ts.append(t_); iv.append(i_); Fs.append(f_); Ks.append(k_); am.append(a_)
                put.append(typ == "put"); sg.append(1.0 if dirn == "buy" else -1.0); ex.append(ecache[e])
            if not ts:
                continue
            ud, N, A, Cn, cnt, sk = flow_aggregate(ts, iv, Fs, Ks, put, sg, am, ex)
            skipped += sk
            for j, d in enumerate(ud.tolist()):
                agg[d] += np.array([N[j], A[j], Cn[j], cnt[j]])
        days = np.array(sorted(agg), np.int64)
        M = np.array([agg[d] for d in days.tolist()]).reshape(-1, 4)
        return {"days": days, "N": M[:, 0], "A": M[:, 1], "C": M[:, 2], "cnt": M[:, 3], "complete": complete,
                "skipped": skipped, "malformed": bad, "bundles": names}
    return CAL._cached(archive, ("b13f_flow",), load)


def coinbase_daily(archive, first_ed: int, last_ed: int) -> dict:
    """Per UTC day: close of the 23:59 bar (the day's last print when that bar is missing: stale), and the first print
    at or after 24:00 (open of the first bar at or after the day's end, within an hour)."""
    def load():
        months = []
        y, m = int(EV._iso(first_ed)[:4]), int(EV._iso(first_ed)[5:7]) - 1
        if m == 0:
            y, m = y - 1, 12
        while f"{y:04d}-{m:02d}" <= EV._iso(last_ed + 32)[:7]:
            months.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        t, op, cl = [], [], []
        for mo in months:
            nm = CB_PREFIX + mo
            if not B7C._has(archive, nm):
                continue
            keep = EV._avail_filter(archive, nm)
            for r in archive.load(nm):
                if not keep(r):
                    continue
                v = r.get("value") or {}
                a, o_, c_ = EV._num(v.get("t")), EV._num(v.get("open")), EV._num(v.get("close"))
                if a is None or not o_ or not c_:
                    continue
                t.append(int(a)); op.append(o_); cl.append(c_)
        t, op, cl = np.array(t, np.int64), np.array(op), np.array(cl)
        o = np.argsort(t, kind="stable")
        t, op, cl = t[o], op[o], cl[o]
        eds = np.arange(first_ed - 3, last_ed + 5, dtype=np.int64)
        close = np.full(eds.size, np.nan); opn = np.full(eds.size, np.nan); stale = np.zeros(eds.size, bool)
        for k, e in enumerate(eds.tolist()):
            end = (e + 1) * DAY_S
            i = int(np.searchsorted(t, end, side="left"))
            if i - 1 >= 0 and t[i - 1] >= e * DAY_S:
                close[k] = cl[i - 1]
                stale[k] = t[i - 1] != end - 60
            if i < t.size and t[i] < end + 3600:
                opn[k] = op[i]
        return {"eds": eds, "close": close, "open_after": opn, "stale": stale, "months": months}
    return CAL._cached(archive, ("b13f_cb", first_ed, last_ed), load)


def funding_daily(archive) -> dict:
    """{epoch day D: (sum of interest_1h with timestamp in (D 00:00, D+1 00:00], rows)} of BTC-PERPETUAL."""
    def load():
        by = defaultdict(lambda: [0.0, 0])
        for r in CAL._rows(archive, FUND_B):
            v = r.get("value") or {}
            ts, x = EV._num(v.get("timestamp")), EV._num(v.get("interest_1h"))
            if ts is None or x is None:
                continue
            d = int((ts - 1) // 86400000)
            by[d][0] += x
            by[d][1] += 1
        return {d: (s, c) for d, (s, c) in by.items()}
    return CAL._cached(archive, ("b13f_fund",), load)


def dvol_daily(archive) -> dict:
    out = {}
    if not B7C._has(archive, DVOL_B):
        return out
    for r in CAL._rows(archive, DVOL_B):
        v = r.get("value") or {}
        ts, c = EV._num(v.get("ts_ms")), EV._num(v.get("close"))
        if ts is not None and c is not None:
            out[int(ts // 86400000)] = c
    return out


def trailing_median_sign(x, win: int = T638_WIN) -> np.ndarray:
    """+1 when x_d is above the median of the ``win`` finite values ending at d (d included), -1 otherwise; NaN before
    ``win`` values exist."""
    x = np.asarray(x, float)
    out = np.full(x.size, np.nan)
    idx = np.flatnonzero(np.isfinite(x))
    v = x[idx]
    for k in range(win - 1, idx.size):
        out[idx[k]] = 1.0 if v[k] > np.median(v[k - win + 1:k + 1]) else -1.0
    return out


def horizon_position(sign, h: int) -> np.ndarray:
    """Position held over day d+1: the mean of the last ``h`` signs (d, d-1, ...), NaN unless all are defined."""
    s = np.asarray(sign, float)
    if h == 1:
        return s.copy()
    out = np.full(s.size, np.nan)
    for k in range(h - 1, s.size):
        w = s[k - h + 1:k + 1]
        if np.isfinite(w).all():
            out[k] = float(w.mean())
    return out


def rule_net(pos, r_next, f_next, cost_side: float, funding: str) -> np.ndarray:
    """Daily net of the rule on the calendar grid: pos_d x r_{d+1} minus the funding charge over d+1 ('s': pos x f,
    'c': |pos x f|) minus cost_side x |pos_d - pos_{d-1}| (pos_{d-1} = 0 when undefined); NaN where undefined."""
    pos = np.asarray(pos, float)
    prev = np.concatenate([[0.0], np.where(np.isfinite(pos[:-1]), pos[:-1], 0.0)])
    fch = pos * f_next if funding == "s" else np.abs(pos * f_next)
    out = pos * r_next - fch - cost_side * np.abs(pos - prev)
    return np.where(np.isfinite(pos) & np.isfinite(r_next) & np.isfinite(f_next), out, np.nan)


def spearman_hac(x, y, lag: int = T638_HAC_LAG) -> dict:
    """Spearman IC as the mean of the product of standardised ranks, with its Newey-West t (``lag``)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return {"ic": None, "t": None, "p": None, "n": int(ok.sum())}
    rx, ry = rankdata(x[ok]), rankdata(y[ok])
    z = ((rx - rx.mean()) / rx.std()) * ((ry - ry.mean()) / ry.std())
    h = hac_mean(z, lag)
    return {"ic": float(z.mean()), "t": h["t"], "p": h["p"], "n": int(ok.sum())}


def residualise(s, r) -> np.ndarray:
    s, r = np.asarray(s, float), np.asarray(r, float)
    ok = np.isfinite(s) & np.isfinite(r)
    out = np.full(s.size, np.nan)
    if ok.sum() < 3:
        return out
    X = np.column_stack([np.ones(ok.sum()), r[ok]])
    b, *_ = np.linalg.lstsq(X, s[ok], rcond=None)
    out[ok] = s[ok] - X @ b
    return out


def flow_grid(archive) -> dict:
    """Everything on a contiguous UTC calendar grid: flows (NaN off complete days), Coinbase closes and post-midnight
    prints, funding over each day, DVOL."""
    def load():
        fl = deribit_flow(archive)
        comp = fl["complete"]
        keep = np.array([bool(comp.get(EV._iso(d))) for d in fl["days"].tolist()], bool) & (fl["cnt"] > 0)
        d0, d1 = int(fl["days"][keep].min()), int(fl["days"][keep].max())
        grid = np.arange(d0, d1 + 1, dtype=np.int64)
        pos = {int(d): i for i, d in enumerate(grid)}
        N, A, Cn = (np.full(grid.size, np.nan) for _ in range(3))
        for j in np.flatnonzero(keep):
            i = pos[int(fl["days"][j])]
            N[i], A[i], Cn[i] = fl["N"][j], fl["A"][j], fl["C"][j]
        cb = coinbase_daily(archive, d0, d1)
        cpos = {int(e): k for k, e in enumerate(cb["eds"])}

        def at(arr, shift):
            return np.array([arr[cpos[int(d) + shift]] if int(d) + shift in cpos else np.nan for d in grid])
        fd = funding_daily(archive)

        def fund(shift):
            out = np.full(grid.size, np.nan)
            for i, d in enumerate(grid.tolist()):
                s, c = fd.get(d + shift, (0.0, 0))
                if c >= T638_FUND_MIN_ROWS:
                    out[i] = s * 24.0 / c
            return out
        dv = dvol_daily(archive)
        return {"grid": grid, "N": N, "A": A, "C": Cn,
                "Cm1": at(cb["close"], -1), "C0": at(cb["close"], 0), "C1": at(cb["close"], 1), "C3": at(cb["close"], 3),
                "Em1": at(cb["open_after"], -1), "E0": at(cb["open_after"], 0), "E1": at(cb["open_after"], 1),
                "E3": at(cb["open_after"], 3), "stale0": at(cb["stale"].astype(float), 0),
                "f0": fund(0), "f1": fund(1), "dvol": np.array([dv.get(int(d), np.nan) for d in grid]),
                "n_complete": int(keep.sum()), "n_days_in_bundles": int(fl["days"].size), "skipped": fl["skipped"],
                "malformed": fl["malformed"], "incomplete_days": sorted(d for d, c in comp.items() if not c)}
    return CAL._cached(archive, ("b13f_grid",), load)


def t638_signals(G: dict) -> dict:
    """The three normalisations of the flow on the grid (each known at the end of its day)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        s_abs = np.where(G["A"] > 0, G["N"] / G["A"], np.nan)
        s_con = np.where(G["C"] > 0, G["N"] / G["C"], np.nan)
    return {"abs": s_abs, "contracts": s_con, "z60": SA.trailing_z(G["N"], T638_WIN)}


def _returns(G: dict, reading: str) -> dict:
    if reading == "a":
        c_m1, c0, c1, c3 = G["Cm1"], G["C0"], G["C1"], G["C3"]
    else:
        c_m1, c0, c1, c3 = G["Em1"], G["E0"], G["E1"], G["E3"]
    return {"own": c0 / c_m1 - 1.0, "next": c1 / c0 - 1.0, "next3": c3 / c0 - 1.0}


def _halves_mask(grid) -> np.ndarray:
    return np.asarray(grid) < EV._ed(T638_SPLIT)


def t638_reading(G: dict, sig: dict, price: str, funding: str) -> dict:
    """IC, residual IC and the 6 trials for one price / funding reading."""
    r = _returns(G, price)
    f1 = G["f1"]
    h1 = _halves_mask(G["grid"])
    out = {"ic": spearman_hac(sig["abs"], r["next"]), "ic_3d": spearman_hac(sig["abs"], r["next3"])}
    res = residualise(sig["abs"], r["own"])
    out["res_ic"] = spearman_hac(res, r["next"])
    out["ic_halves"] = [spearman_hac(np.where(m, sig["abs"], np.nan), r["next"])["ic"] for m in (h1, ~h1)]
    out["res_ic_halves"] = [spearman_hac(np.where(m, res, np.nan), r["next"])["ic"] for m in (h1, ~h1)]
    trials, nets = {}, {}
    for nm, s in sig.items():
        sgn = trailing_median_sign(s)
        for h in (1, 3):
            pos = horizon_position(sgn, h)
            net = rule_net(pos, r["next"], f1, T638_COST_SIDE, funding)
            x = net[np.isfinite(net)]
            nets[(nm, h)] = net
            trials[f"{nm}/{h}d"] = {"n": int(x.size), "mean": float(x.mean()) if x.size else None,
                                    "sharpe": float(sharpe_ratio(x)) if x.size > 2 else None}
    prim = nets[("abs", 1)]
    x = prim[np.isfinite(prim)]
    srs = [t["sharpe"] for t in trials.values() if t["sharpe"] is not None]
    var_obs = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    floor = 1.0 / max(1, x.size - 1)
    var_used = max(var_obs, floor)
    dsr = float(deflated_sharpe_ratio(x, n_trials=T638_TRIALS, var_trials_sr=var_used)) if x.size > 3 else None
    psr0 = float(deflated_sharpe_ratio(x, n_trials=1)) if x.size > 3 else None
    pg, pl, nd = boot_p(x, T638_BLOCK, stop_side("greater")) if x.size >= 8 else (None, None, 0)
    sgn = trailing_median_sign(sig["abs"])
    hi = rule_net(sgn, r["next"], f1, T638_COST_SIDE_HI, funding)
    halves = [float(np.nanmean(np.where(m, prim, np.nan))) if np.isfinite(np.where(m, prim, np.nan)).any() else None
              for m in (h1, ~h1)]
    out.update(trials=trials, n=int(x.size), mean_net=float(x.mean()) if x.size else None, dsr=dsr,
               p_deflated=None if dsr is None else 1.0 - dsr, psr0=psr0, var_trials_sr_observed=var_obs,
               var_trials_sr_used=var_used, var_floor=floor, p_boot=pg, p_boot_less=pl, draws=nd,
               mean_net_20bp=float(np.nanmean(hi)) if np.isfinite(hi).any() else None, rule_halves=halves,
               net=prim, sign=sgn)
    return out


def _baselines(G, price: str, funding: str) -> dict:
    r = _returns(G, price)
    own = r["own"]
    out = {}
    for nm, pos in (("buy_and_hold", np.where(np.isfinite(own), 1.0, np.nan)), ("momentum_1d", np.sign(own)),
                    ("reversal_1d", -np.sign(own))):
        net = rule_net(pos, r["next"], G["f1"], T638_COST_SIDE, funding)
        out[nm] = float(np.nanmean(net)) if np.isfinite(net).any() else None
    return out


def b13_flow_deribit_signed_delta_flow(archive):
    """T-638."""
    miss = B7C._missing(archive, [DRB_PREFIX + "2024-03", CB_PREFIX + "2024-03", FUND_B])
    if miss:
        return miss
    G = flow_grid(archive)
    sig = t638_signals(G)
    reads = {f"{p}/{f}": t638_reading(G, sig, p, f) for p in ("a", "b") for f in ("s", "c")}
    n = min(r["n"] for r in reads.values())
    ic_keys = ("a/s", "b/s")                      # IC depends only on the price reading

    def ic_ok(d):
        if d["ic"] is None or d["p"] is None:
            return None
        return bool(d["ic"] > 0 and d["p"] < ALPHA)

    def ic_dec(d):
        return d["t"] is not None and d["t"] <= -1.6448536269514722
    rows = [("IC > 0 with HAC (5 lags) one-sided p < 0.05 ("
             + "; ".join(f"price {k[0]}: IC {_fmt(reads[k]['ic']['ic'])}, t {_fmt(reads[k]['ic']['t'], 2)}" for k in ic_keys) + ")",
             CAL._agree([ic_ok(reads[k]["ic"]) for k in ic_keys]), all(ic_dec(reads[k]["ic"]) for k in ic_keys)),
            ("residual IC (flow residualised on day d's return) > 0 with HAC one-sided p < 0.05 ("
             + "; ".join(f"price {k[0]}: {_fmt(reads[k]['res_ic']['ic'])}, t {_fmt(reads[k]['res_ic']['t'], 2)}" for k in ic_keys) + ")",
             CAL._agree([ic_ok(reads[k]["res_ic"]) for k in ic_keys]), all(ic_dec(reads[k]["res_ic"]) for k in ic_keys))]
    rule_oks, rule_dec = [], []
    for r in reads.values():
        if r["mean_net"] is None or r["p_deflated"] is None:
            rule_oks.append(None)
            rule_dec.append(False)
            continue
        if not (r["mean_net"] > 0 and r["p_deflated"] < ALPHA):
            rule_oks.append(False)
        else:                                       # both the deflated p and the registered bootstrap p must pass
            rule_oks.append(CAL.decide_p(r["p_boot"], r["draws"]))
        rule_dec.append(bool(r["mean_net"] < 0 and r["psr0"] is not None and r["psr0"] <= ALPHA))
    rows.append(("rule (abs-delta, 1 day) mean net of 10 bps/round trip and funding > 0 at deflated p < 0.05 over 6 trials "
                 "and block-bootstrap p < 0.05 (readings price/funding: "
                 + "; ".join(f"{k} {_bp(r['mean_net'], 2)}/day, deflated p {_pf(r['p_deflated'])}, boot p {_pf(r['p_boot'])}"
                             for k, r in reads.items()) + ")", CAL._agree(rule_oks), all(rule_dec)))
    hv = []
    for r in reads.values():
        vals = list(r["rule_halves"]) + list(r["ic_halves"]) + list(r["res_ic_halves"])
        hv.append(None if any(v is None for v in vals) else all(v > 0 for v in vals))
    rows.append(("IC, residual IC and rule net > 0 in both halves (2024-03..2025-06 / 2025-07..2026-10; "
                 + "; ".join(f"{k}: net {' / '.join(_bp(v, 2) for v in r['rule_halves'])}, IC "
                             f"{' / '.join(_fmt(v, 3) for v in r['ic_halves'])}, res IC {' / '.join(_fmt(v, 3) for v in r['res_ic_halves'])}"
                             for k, r in reads.items()) + ")", CAL._agree(hv), False))
    rows.append(("rule mean net > 0 at 20 bps a round trip ("
                 + "; ".join(f"{k} {_bp(r['mean_net_20bp'], 2)}" for k, r in reads.items()) + ")",
                 CAL._agree([None if r["mean_net_20bp"] is None else bool(r["mean_net_20bp"] > 0) for r in reads.values()]),
                 False))
    verdict, why, crit = CAL._judge(CAL._undecided(rows), n, T638_MIN_N, "days")

    # ---- reported
    A = reads["a/s"]
    net, grid = A["net"], G["grid"]
    hold_fri = np.array([date.fromisoformat(EV._iso(d + 1)).weekday() == 4 for d in grid.tolist()])
    f0 = G["f0"]
    fmed = float(np.nanmedian(f0)) if np.isfinite(f0).any() else float("nan")
    dv = G["dvol"]
    q = np.nanquantile(dv, [1 / 3, 2 / 3]) if np.isfinite(dv).any() else [np.nan, np.nan]

    def mn(m):
        x = net[np.asarray(m, bool) & np.isfinite(net)]
        return {"n": int(x.size), "mean_net": float(x.mean()) if x.size else None}
    splits = {"hold_day_friday": mn(hold_fri), "hold_day_other": mn(~hold_fri),
              "funding_above_median": mn(f0 > fmed), "funding_below_median": mn(f0 <= fmed),
              "dvol_low": mn(dv <= q[0]), "dvol_mid": mn((dv > q[0]) & (dv <= q[1])), "dvol_high": mn(dv > q[1])}
    rep = {"baselines_a_s": _baselines(G, "a", "s"), "baselines_b_s": _baselines(G, "b", "s"), "splits_a_s": splits,
           "trials": {k: r["trials"] for k, r in reads.items()}, "ic_3d": {k: reads[k]["ic_3d"] for k in ic_keys},
           "complete_days": G["n_complete"], "incomplete_days": G["incomplete_days"], "trades_skipped": G["skipped"],
           "malformed_rows": G["malformed"], "stale_23_59_bars": int(np.nansum(G["stale0"]))}
    reason = (f"Deribit BTC near-expiry (0-8 days) taker flow, {G['n_complete']} complete UTC days "
              f"{EV._iso(grid[0])}..{EV._iso(grid[-1])} ({G['skipped']} trades skipped for iv/T/price); S = net signed "
              f"Black-76 delta / absolute delta volume. IC vs next-day Coinbase return {_fmt(A['ic']['ic'])} (HAC t "
              f"{_fmt(A['ic']['t'], 2)}, n {A['ic']['n']}), residual IC {_fmt(A['res_ic']['ic'])} (t {_fmt(A['res_ic']['t'], 2)}); "
              f"post-midnight prices IC {_fmt(reads['b/s']['ic']['ic'])}. Rule (long above the trailing-60-day median, short "
              f"otherwise, 10 bps/round trip, funding charged): {A['n']} days, mean net {_bp(A['mean_net'], 2)}/day "
              f"(boot p {_pf(A['p_boot'])}, DSR over 6 trials {_pf(A['dsr'])}); cost-only funding "
              f"{_bp(reads['a/c']['mean_net'], 2)}; 20 bps {_bp(A['mean_net_20bp'], 2)}; halves "
              f"{' / '.join(_bp(v, 2) for v in A['rule_halves'])}. Baselines (a/s): "
              + ", ".join(f"{k} {_bp(v, 2)}" for k, v in rep["baselines_a_s"].items())
              + "; trials (a/s): " + ", ".join(f"{k} {_bp(t['mean'], 2)}" for k, t in A["trials"].items())
              + ". Executed as CDE nano BTC futures (spot return as the proxy, Deribit perpetual funding as the carry)")
    clean = {k: {kk: vv for kk, vv in r.items() if kk not in ("net", "sign")} for k, r in reads.items()}
    stat = {"n": n, "readings": clean, "criteria": crit, "reported": rep}
    return _out(stat, n, verdict, reason + " — " + why)


HARNESSES = {"b13_flow_spxw_expiry_dampening": b13_flow_spxw_expiry_dampening,
             "b13_flow_opex_strike_pinning": b13_flow_opex_strike_pinning,
             "b13_flow_dix_rebuild_p80_60d": b13_flow_dix_rebuild_p80_60d,
             "b13_flow_deribit_signed_delta_flow": b13_flow_deribit_signed_delta_flow}
THEORY_MAP = {"T-632": "b13_flow_spxw_expiry_dampening", "T-633": "b13_flow_opex_strike_pinning",
              "T-639": "b13_flow_dix_rebuild_p80_60d", "T-638": "b13_flow_deribit_signed_delta_flow"}
