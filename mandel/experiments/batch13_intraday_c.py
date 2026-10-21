"""
Batch 13, group ``intraday_c``: four intraday claims from the 2026-10-20 web sweep (cluster "intraday"), 2026-10-21.
=====================================================================================================================

  * T-666  Same-hour return continuation (Heston-Korajczyk-Sadka) on the 28 single stocks and 11 sector SPDRs with local
           60m bars, 2023-11-21..2026-10. Per bar-day, a cross-sectional OLS of a name's demeaned hour-h return on the
           mean of its own demeaned hour-h returns over the previous 20 sessions, controlling for the two preceding
           intervals (09:30: the overnight return and the prior session's 15:30 bar). Statistic: the mean daily slope
           with a Newey-West (5 lags) t; lags 1 and 1-5 secondary. Pass: the 09:30 and 15:30 slopes > 0 with Holm
           one-sided p < 0.05 and positive in both halves. Placebos 11:30 / 12:30; stocks-only and ETFs-only splits.
           min_n 600 sessions.
  * T-657  T-427's rule (sign of the dividend-adjusted prior close -> 10:30 return, held from the 15:30 bar open to the
           official close, 2 bp round trip) on SPY days whose 09:30-bar volume ratio (over the trailing-20-session mean)
           is in the top tercile of its own expanding prior distribution (>= 60 sessions, 80-session burn-in);
           QQQ and IWM replications; second family member the 09:30-bar range. Pass: SPY mean net > 0 with one-sided
           deflated p < 0.05 (66 trials), QQQ and IWM the same sign, SPY's complement days not also > 0. min_n 200.
  * T-661  Negative daytime-reversal intensity (Akbas et al.) in point-in-time S&P 500 members, holding months
           2018-01..2026-09: NR = the month's share of days with overnight > 0 and intraday < 0 over the mean share of
           the prior 12 months; the equal-weight top quintile formed at each month-end close, filled at the next close,
           held a month, net of 10 bp per side on traded weight, minus the equal-weight member universe. Statistic:
           FF5+UMD monthly alpha, NW(3) t. Pass: alpha > 0 with one-sided deflated p < 0.05 (8 cells), positive in
           2018-2021 and 2022-2026, coverage gate met. min_n 100 months.
  * T-668  BTC 22:00-00:00 UTC block on Coinbase 1m BTC-USD 2022-01..2026-10 (Kraken 1m XBTUSD 2022-01..2025-12 second
           venue): the mean daily block log return minus the mean of the other eleven 2-hour UTC blocks > 5 bp/day.
           Studentized circular block bootstrap by day (7-day blocks), all 12 blocks with Holm. Pass: Holm one-sided
           p < 0.05, positive in both halves, both IBIT periods and on Kraken. min_n 1500 days.

Conventions (every reading fixed before any run; the reasons repeat the binding ones)
  * Data. Archive bundles through ``archive.load`` with the capture-time filter (``batch6c_cal._rows`` / ``_daily``,
    ``batch6c_stockxs._stream``); local Yahoo 60m bars through ``mandel.ml.features.load_bars`` (via
    ``batch13_intraday_a._local``), stamped by bar OPEN: a bar is known at its close, stamp + 60 min (the 15:30 bar is
    the last half hour). Multi-symbol daily prices come from ``panel_cache.daily_panel`` (value-identical to
    ``_daily``) restricted to NYSE sessions; T-661 reuses T-660's point-in-time S&P panel (``batch13_intraday_a.
    t660_inputs``: fja membership, the ticker-spell check, overnight / intraday returns with cash dividends added on
    ex-dates). Each harness probes the archive bundles the registration names and returns inconclusive (rule 9) when
    one is missing.
  * Point in time. T-666: every regressor of bar h on session d uses sessions before d, or bars of d that close before
    bar h opens (the overnight return is known at the 09:30 open); the dependent 15:30 return ends at the official close.
    T-657: the 09:30 bar closes at 10:30 and is the latest input; the volume ratio and both tercile cut-offs use earlier
    sessions only. T-661: NR uses returns through the month-end close; the fill is the NEXT session's close; size and
    FINRA days-to-cover (diagnostics) are those known before the formation (SEC shares accepted before that session's
    09:30, FINRA releases by available_at before its 16:00 ET close). T-668: a block is measured from minute closes
    inside it; the SPY diagnostic regresses on SPY's same-day close (16:00 ET, before 22:00 UTC).
  * Inference. Resampled p's are pooled over seeds and escalated while their Monte-Carlo band straddles alpha
    (``batch6c_cal.escalate_p`` / ``decide_p``); Holm decisions on such p's use ``batch13_intraday_b.holm_decide`` (each
    step's threshold through the MC band). Where a criterion names two tests or admits two registered readings it
    passes only when both pass and fails only when both fail (``_agree``, rule 11). Below min_n a failure counts only
    when decisive (``batch6c_cal._judge``, rule 5): a one-sided 5% test of the same construction in the opposite
    direction rejects.
  * Rule 10. T-666, T-657 and T-668 are daily series that use every eligible session (no grid phase). T-661's month-end
    formation of a calendar-month statistic is the calendar the registration names (rule 10(a)); there is no other
    phase without redefining NR.

Claim-specific readings (declared before any return was computed)
  * T-666. Universe: the 28 local single stocks (``batch13_intraday_a.T660_LOCAL_STOCKS``) and XLB XLC XLE XLF XLI XLK
    XLP XLRE XLU XLV XLY. Sessions: NYSE sessions 2023-11-21..2026-10-31 with bars; scheduled early closes and any day
    with a 13:00 tick are removed. Bar return = bar close / bar open - 1 (simple) for 09:30..14:30; the 15:30 bar =
    daily-history official close / 15:30 bar open - 1. Overnight = (official open + cash dividend on the ex-date) /
    previous official close - 1 (``daily-events``; the adjclose factor for the 9 SPDRs without an events bundle).
    Returns are demeaned per bar-day across the names of the universe being regressed (full, stocks-only, ETFs-only).
    "The mean over the previous 20 sessions" = the 20 most recent earlier sessions on which the name has that bar
    (two capture-gap days, 2026-01-30 and 2026-02-02, lack bars on every name; skipping them keeps 20 observations);
    the same for lags 1 and 1-5. Controls: 09:30 -> the overnight return and the previous session's 15:30 bar (only
    when the previous bar session is the previous NYSE session; after an early close the row is dropped); 11:30 ->
    10:30, 09:30; 12:30 -> 11:30, 10:30; 15:30 -> 14:30, 13:30. Cross-sectional OLS with an intercept on names with
    every input, at least max(8, ceil(N / 2)) names. Holm over the two claimed bars (m = 2; the four-bar Holm with
    the placebos is reported). Halves split at the median session of the bar calendar. n = the smaller of the two
    claimed bars' slope-day counts. No costs (the registration makes no trading claim).
  * T-657. Local 60m bars of SPY / QQQ / IWM and ``daily-history`` closes. The session sequence holds NYSE sessions in
    the window with a 09:30 bar of positive volume; scheduled early closes and days with a 13:00 tick are excluded from
    it entirely (from trading and from the trailing volume / range history). r1 = 09:30-bar close / (C(t-1) f(t-1) /
    f(t)) - 1 with f = adjclose / close (T-427's construction); the position sign(r1) from the 15:30 bar open to the
    official close; 2 bp per traded day. Volume ratio at session k = V_k / mean(V_{k-20..k-1}); range = (high - low) of
    the 09:30 bar / the previous official close. Cut-off = the 2/3 quantile (numpy linear) of the condition at every
    earlier session of the sequence, at least 60 values; top tercile = strictly above; the first 80 sessions are
    dropped for both conditions. Criterion 1 is read two ways that must agree: 1 - DSR over 66 trials (trial-Sharpe
    variance floored at 1/(T-1), T-427's construction) and the Holm-adjusted NW(5) one-sided p over the 6 cells (2
    conditions x 3 ETFs). QQQ / IWM use their own bars and volume. The complement = sessions whose ratio is evaluable
    and not in the top tercile; the placebo passes when SPY's complement mean net is <= 0. n = SPY condition days.
  * T-661. NR (and the placebo PR: overnight < 0 and intraday > 0) per stock-month from days with a finite overnight
    and intraday return, at least 15 such days; the denominator needs all 12 prior months valid (the strict reading of
    "12 prior months"). Eligible at formation f (the month's last session): a spell-checked member at f with NR and a
    close at f + 1. Hold from the close of f + 1 to the close of the first session of the month after (the next
    fill), total return from adjclose; a series that ends inside the hold exits at its last close. Top quintile =
    floor(n / 5) names, ties sharing boundary slots (``tail_fractions``), equal weights. Benchmark = equal weights over
    every spell-checked member at f with a close at f + 1 (the "member universe"; the NR-sortable universe is
    reported). Costs: 10 bp x the top quintile's traded weight, sum |w_new - w_drifted| (the first month buys 1.0); the
    benchmark is charged nothing (conservative). Factors: french-ff5-daily + french-momentum-daily compounded over the
    hold's sessions; months whose hold runs past the factor data (2026-08-31) leave the regression. Deflated p read two
    ways that must agree (T-660's convention): Bonferroni over 8 cells (8 x the NW(3) p) and 1 - DSR of the
    factor-hedged series (alpha + residuals) at 8 trials, the trial-Sharpe variance over the computed cells floored at
    1/(T-1). Halves: the alpha re-estimated on 2018-01..2021-12 and 2022-01..2026-09 holds. Coverage gate: T-660's
    (>= 90% of fja member-months at the formation month-ends 2017-12..2026-08 priced by a spell-checked series); unmet
    it is a None criterion (a cap that never turns a failure into inconclusive).
  * T-668. Each minute bundle is reduced to the last minute bar of every UTC hour; the close "of the HH:59 minute" is
    that bar's close, forward-filled from earlier hours when an hour has no trade. Block b (UTC hours 2b, 2b + 1) =
    log(close at (2b + 1):59 / close at (2b - 1):59), block 0 from the previous day's 23:59. A UTC day is used when its
    bundle covers it whole (span tag of a bundle tagged complete, or before the end of a partial bundle's span) and
    all 12 blocks exist. d_t = r_22 - mean of the other 11 blocks; each of the 12 blocks the same way against the
    5 bp bar. Multiplicity: Holm over the 12 blocks with Hurst's 478 coin-hour cells counted, m = 490 (the conservative
    reading of "the write-up counts Hurst's 478 coin-hour scan in the multiplicity"; the 12-block Holm is reported).
    Halves at the median day; IBIT split at 2024-01-11; Kraken positive (point) over the registered 2022-01..2025-12
    (later Kraken bundles exist and are not used). Costs reported: 2 bp (CME micro / Coinbase nano, to verify), 16 and
    18 bp (Kalshi perps) round trip, the Coinbase spot maker tier (Intro tier 0.40% per side, 80 bp round trip; the
    rate from ``batch6c_kraken.COINBASE_TIERS``) and the break-even cost. The registration's "ask Hurst first" step
    cannot be done by a harness: Hurst's per-cell values are not in the repo (only the aggregate 3 of 478). The main
    session must ask Hurst for its BTC 22:00 and 23:00 UTC cells before recording: if they cover Coinbase 2022-2026
    they are the record under this registration and this harness a replication; the stat carries the flag.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch13_intraday_a as IA
from mandel.experiments import batch13_intraday_b as IB
from mandel.experiments.batch6_surf import _out
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

SEED = 0
N_BOOT = 2000
N_SEEDS = 5
ALPHA = 0.05
Z95 = 1.959964
NY = ZoneInfo("America/New_York")
UTC = timezone.utc
BAR_TIMES = ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")
EARLY_TICK = "13:00"

# T-666
T666_START, T666_END = "2023-11-21", "2026-10-31"
T666_STOCKS = tuple(IA.T660_LOCAL_STOCKS)
T666_SECTORS = tuple(IA.T664_SECTORS)
T666_LAGS = (20, 1, 5)                 # primary 20; secondaries 1 and 1-5
T666_NW_LAG = 5
T666_MIN_N = 600
T666_PRIMARY = ("09:30", "15:30")
T666_PLACEBO = ("11:30", "12:30")
T666_CONTROLS = {"09:30": ("overnight", "prior 15:30"), "11:30": ("10:30", "09:30"), "12:30": ("11:30", "10:30"),
                 "15:30": ("14:30", "13:30")}
# T-657
T657_SYMS = ("SPY", "QQQ", "IWM")
T657_START, T657_END = "2023-11-21", "2026-10-31"
T657_VOL_WIN = 20
T657_MIN_HIST = 60
T657_BURN = 80
T657_Q = 2.0 / 3.0
T657_COST = 2e-4
T657_NW_LAG = 5
T657_TRIALS = 66
T657_MIN_N = 200
# T-661
T661_FIRST_HOLD, T661_LAST_HOLD = "2018-01", "2026-09"
T661_SPLIT = "2022-01"
T661_MIN_DAYS = 15
T661_PRIOR = 12
T661_Q = 5
T661_COST = 10e-4                      # per side on traded weight
T661_NW_LAG = 3
T661_CELLS = 8
T661_MIN_N = 100
T661_COVER = IA.T660_COVER
FF5_B, MOM_B = "french-ff5-daily", "french-momentum-daily"
FF5_COLS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
FINRA_FIRST_B = "finra-short-interest-2017-12-29"
# T-668
T668_CB, T668_KR = "coinbase-1m-BTC-USD-", "kraken-trades-1m-XBTUSD-"
T668_CB_SPAN = ("2022-01", "2026-10")
T668_KR_SPAN = ("2022-01", "2025-12")
T668_BLOCK_DAYS = 7
T668_BAR = 5e-4
T668_TARGET = 11                       # block index of 22:00-00:00 UTC
T668_HURST = 478
T668_MIN_N = 1500
T668_IBIT = "2024-01-11"
# Coinbase Advanced spot maker fee at the entry ("Intro ($0+)") volume tier, the tier a strategy of this size trades at:
# 0.40% per side (batch6c_kraken.COINBASE_TIERS, verified in the repo 2026-10-14), charged on entry and exit.
T668_CB_MAKER_TIER = "Intro ($0+)"
T668_CB_MAKER = 0.0040
T668_COSTS = (("CME micro / Coinbase nano, about 2 bp (to verify)", 2e-4), ("Kalshi perps 16 bp", 16e-4),
              ("Kalshi perps 18 bp", 18e-4),
              ((f"Coinbase spot maker tier ({T668_CB_MAKER_TIER}, {T668_CB_MAKER * 100:.2f}% per side x 2 = "
                f"{2 * T668_CB_MAKER * 1e4:.0f} bp; maker tiers fall to 0% only at $250M+ 30-day volume, to verify)"),
               2 * T668_CB_MAKER))


# ================================================================================================ shared helpers ==

def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f} bp"


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pf(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.4f}"


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _nw(x, lag: int) -> dict:
    """``batch6c_stockxs.nw_mean`` on the finite values: est, se, t, p (H0 mean <= 0), p_lt (H0 mean >= 0), n."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    r = SX.nw_mean(x, lag)
    r["n"] = int(x.size)
    return r


def bar_table(df) -> dict:
    """{New York day: {'HH:MM' bar start: (open, high, low, close, volume)}} of a local 60m frame (UTC bar-start
    index)."""
    if df is None or len(df) == 0:
        return {}
    idx = df.index.tz_convert("America/New_York")
    dd, hm = idx.strftime("%Y-%m-%d"), idx.strftime("%H:%M")
    cols = [df[k].to_numpy(float) for k in ("o", "h", "l", "c", "v")]
    out: dict = {}
    for k in range(len(df)):
        out.setdefault(dd[k], {})[hm[k]] = tuple(float(c[k]) for c in cols)
    return out


def _early(day: str, tables: Sequence[dict], ec: set) -> bool:
    """A scheduled early close, or a day whose bars show the 13:00 close tick without a 15:30 bar."""
    if day in ec:
        return True
    return any(EARLY_TICK in t.get(day, {}) and "15:30" not in t.get(day, {}) for t in tables)


def bar_calendar(tables: Sequence[dict], start: str, end: str) -> tuple:
    """(sessions, early closes removed): NYSE sessions in [start, end] with a bar in any table, early closes removed."""
    days = sorted({d for t in tables for d in t if start <= d <= end and CAL.is_nyse_session(d)})
    if not days:
        return [], []
    ec = IA.early_closes(int(days[0][:4]), int(days[-1][:4]))
    early = [d for d in days if _early(d, tables, ec)]
    es = set(early)
    return [d for d in days if d not in es], early


def _nyse_panel(archive, syms: Sequence[str], lo: str, hi: str) -> dict:
    """Session x symbol official open / close / adjclose from the shared daily panel on NYSE sessions in [lo, hi]."""
    from mandel.experiments.panel_cache import daily_panel
    P = daily_panel(archive)
    pdays = P.days.astype(str)
    rows = np.array([i for i, d in enumerate(pdays) if lo <= d <= hi and CAL.is_nyse_session(d)], int)
    days = [str(pdays[i]) for i in rows]
    have = set(P.symbols.tolist())
    out = {"days": days}
    for f in ("open", "close", "adjclose"):
        out[f] = np.column_stack([P.col(s, f)[rows] if s in have else np.full(rows.size, np.nan) for s in syms])
    return out


# =================================================================================== T-666 same-hour momentum ==

def same_hour_signal(X: np.ndarray, L: int) -> np.ndarray:
    """S[d, j] = mean of the L most recent finite X[d', j] with d' < d (NaN until L exist). Nothing from row d or later
    enters row d."""
    X = np.asarray(X, float)
    D, N = X.shape
    S = np.full((D, N), np.nan)
    rows = np.arange(D)
    for j in range(N):
        idx = np.flatnonzero(np.isfinite(X[:, j]))
        if idx.size < L:
            continue
        cs = np.concatenate([[0.0], np.cumsum(X[idx, j])])
        cnt = np.searchsorted(idx, rows, side="left")          # finite observations strictly before row d
        ok = cnt >= L
        S[ok, j] = (cs[cnt[ok]] - cs[cnt[ok] - L]) / L
    return S


def demean(X: np.ndarray, axis: int = -1) -> np.ndarray:
    """X minus its mean across names (finite values only) along ``axis``."""
    X = np.asarray(X, float)
    with np.errstate(invalid="ignore"):
        cnt = np.isfinite(X).sum(axis=axis, keepdims=True)
        m = np.where(cnt > 0, np.nansum(X, axis=axis, keepdims=True) / np.maximum(cnt, 1), np.nan)
    return X - m


def t666_design(Rdm: np.ndarray, ONdm: np.ndarray, prev_adj: np.ndarray, h: int, L: int) -> tuple:
    """(y, S, c1, c2) for bar index ``h`` (days x names): y the demeaned bar return, S the mean of the L most recent
    earlier demeaned returns of the same bar, c1 / c2 the two preceding intervals (09:30: the overnight return and the
    previous session's 15:30 bar, NaN when the previous bar session is not the previous NYSE session)."""
    y = Rdm[:, h, :]
    S = same_hour_signal(y, L)
    if h == 0:
        c1 = ONdm
        c2 = np.full_like(ONdm, np.nan)
        c2[1:] = Rdm[:-1, 6, :]
        c2[~np.asarray(prev_adj, bool)] = np.nan
    else:
        c1, c2 = Rdm[:, h - 1, :], Rdm[:, h - 2, :]
    return y, S, c1, c2


def cs_slopes(y, S, c1, c2, min_names: int) -> tuple:
    """Daily cross-sectional OLS of y on [1, S, c1, c2] over names with every input: (slope on S per day, NaN when
    fewer than ``min_names`` names; names per day)."""
    D = y.shape[0]
    b = np.full(D, np.nan)
    k = np.zeros(D, int)
    for d in range(D):
        m = np.isfinite(y[d]) & np.isfinite(S[d]) & np.isfinite(c1[d]) & np.isfinite(c2[d])
        k[d] = int(m.sum())
        if k[d] < min_names:
            continue
        X = np.column_stack([np.ones(k[d]), S[d, m], c1[d, m], c2[d, m]])
        coef, *_ = np.linalg.lstsq(X, y[d, m], rcond=None)
        b[d] = coef[1]
    return b, k


def t666_panel(archive) -> dict:
    """Day x bar x name raw returns, the overnight return, the bar calendar and the previous-session flags. Cached."""
    def load():
        syms = list(T666_STOCKS) + list(T666_SECTORS)
        tables = [bar_table(IA._local("60m", s)) for s in syms]
        days, early = bar_calendar(tables, T666_START, T666_END)
        D, N = len(days), len(syms)
        cover = t666_bar_coverage(tables, days)
        unread = IA._unreadable("60m", syms)
        if not days:
            return {"syms": syms, "days": [], "early": early, "bar_sessions": cover, "unreadable": unread}
        O = np.full((D, 7, N), np.nan)
        C = np.full((D, 7, N), np.nan)
        for j, t in enumerate(tables):
            for i, d in enumerate(days):
                b = t.get(d)
                if not b:
                    continue
                for h, hm in enumerate(BAR_TIMES):
                    v = b.get(hm)
                    if v is not None and v[0] > 0 and v[3] > 0:
                        O[i, h, j], C[i, h, j] = v[0], v[3]
        lo = (date.fromisoformat(days[0]) - timedelta(days=30)).isoformat()
        dp = _nyse_panel(archive, syms, lo, T666_END)
        Oo, Co, Ao = dp["open"], dp["close"], dp["adjclose"]
        with np.errstate(invalid="ignore"):
            Oo = np.where(Oo > 0, Oo, np.nan)
            Co = np.where(Co > 0, Co, np.nan)
        Dv, _splits, fb = IA.div_matrix(archive, dp["days"], syms, Co, Ao)
        ONf = IA.overnight_returns(Oo, Co, Dv)
        pos = {d: i for i, d in enumerate(dp["days"])}
        ON = np.full((D, N), np.nan)
        Coff = np.full((D, N), np.nan)
        for i, d in enumerate(days):
            k = pos.get(d)
            if k is not None and k > 0 and dp["days"][k - 1] == CAL.prev_session(date.fromisoformat(d)).isoformat():
                ON[i], Coff[i] = ONf[k], Co[k]
            elif k is not None:
                Coff[i] = Co[k]
        with np.errstate(invalid="ignore", divide="ignore"):
            R = C / O - 1.0
            R[:, 6, :] = Coff / O[:, 6, :] - 1.0
        R[~np.isfinite(R)] = np.nan
        prev_adj = np.array([i > 0 and days[i - 1] == CAL.prev_session(date.fromisoformat(days[i])).isoformat()
                             for i in range(D)], bool)
        return {"syms": syms, "days": days, "early": early, "R": R, "ON": ON, "prev_adj": prev_adj,
                "div_fallback": fb, "daily_last": dp["days"][-1] if dp["days"] else None, "bar_sessions": cover,
                "unreadable": unread}
    return CAL._cached(archive, ("b13ic_t666",), load)


def t666_bar_coverage(tables: Sequence[dict], days: Sequence[str]) -> list:
    """Per name, the number of calendar sessions on which its local 60m table has any bar (0 = no bars in the window:
    a missing or unreadable file, which rule 9 must surface rather than let the universe shrink silently)."""
    return [int(sum(1 for d in days if t.get(d))) for t in tables]


def t666_missing_names(pan: dict) -> tuple | None:
    """(stat, n, 'inconclusive', reason) when any registered name has no 60m bar in the window (rule 9), else None."""
    syms, cover = pan["syms"], pan.get("bar_sessions") or [0] * len(pan["syms"])
    gone = [s for s, c in zip(syms, cover) if c == 0]
    if not gone:
        return None
    unread = pan.get("unreadable") or {}
    detail = "; ".join(f"{s} ({'unreadable: ' + unread[s] if s in unread else 'no file or no bars in the window'})"
                       for s in gone)
    return _out({"missing_names": gone, "unreadable": unread, "bar_sessions": dict(zip(syms, cover))}, 0, "inconclusive",
                f"{len(gone)} of the {len(syms)} registered names have no local 60m bar in {T666_START}..{T666_END}: "
                f"{detail}. A verdict on the remaining {len(syms) - len(gone)} names would not be the registered universe "
                f"(rule 9)")


def t666_run(pan: dict, cols: Sequence[int], bars: Sequence[str], lags: Sequence[int]) -> dict:
    """{(bar, L): {"b": daily slopes, "k": names per day}} for the universe ``cols``, demeaned within it."""
    cols = np.asarray(cols, int)
    R, ON = pan["R"][:, :, cols], pan["ON"][:, cols]
    Rdm = demean(R, axis=2)
    ONdm = demean(ON, axis=1)
    min_names = max(8, int(math.ceil(cols.size / 2)))
    out = {}
    for bar in bars:
        h = BAR_TIMES.index(bar)
        for L in lags:
            y, S, c1, c2 = t666_design(Rdm, ONdm, pan["prev_adj"], h, L)
            b, k = cs_slopes(y, S, c1, c2, min_names)
            out[(bar, L)] = {"b": b, "k": k, "min_names": min_names}
    return out


def _slope_summary(b: np.ndarray, days: Sequence[str], split: str) -> dict:
    ok = np.isfinite(b)
    darr = np.asarray(days)
    r = _nw(b, T666_NW_LAG)
    h1 = b[ok & (darr < split)]
    h2 = b[ok & (darr >= split)]
    first = str(darr[ok][0]) if ok.any() else None
    last = str(darr[ok][-1]) if ok.any() else None
    return {"n": int(ok.sum()), "mean": r["est"], "se": r["se"], "t": r["t"], "p": r["p"], "p_lt": r["p_lt"],
            "halves": [float(h1.mean()) if h1.size else None, float(h2.mean()) if h2.size else None],
            "first": first, "last": last}


def b13_intraday_c_same_hour_xs(archive):
    """T-666."""
    syms = list(T666_STOCKS) + list(T666_SECTORS)
    miss = B7C._missing(archive, [B7C.dh(s) for s in syms])
    if miss:
        return miss
    pan = t666_panel(archive)
    gone = t666_missing_names(pan)
    if gone:
        return gone
    days = pan["days"]
    if len(days) < 40:
        return _out({"n_sessions": len(days)}, 0, "inconclusive", f"only {len(days)} bar sessions in the local 60m bars (rule 9)")
    split = days[len(days) // 2]
    ns, nt = len(T666_STOCKS), len(syms)
    unis = {"all": list(range(nt)), "stocks": list(range(ns)), "etfs": list(range(ns, nt))}
    bars = T666_PRIMARY + T666_PLACEBO
    res = {u: t666_run(pan, c, bars, T666_LAGS) for u, c in unis.items()}
    summ = {u: {f"{bar}/L{L}": _slope_summary(res[u][(bar, L)]["b"], days, split) for bar in bars for L in T666_LAGS}
            for u in unis}
    prim = {bar: summ["all"][f"{bar}/L20"] for bar in T666_PRIMARY}
    adj2 = B7C.holm([prim[b]["p"] for b in T666_PRIMARY])
    adj4 = B7C.holm([summ["all"][f"{b}/L20"]["p"] for b in bars])
    rows = []
    for k, bar in enumerate(T666_PRIMARY):
        s = prim[bar]
        ok = None if s["mean"] is None else bool(s["mean"] > 0 and adj2[k] is not None and adj2[k] < ALPHA)
        dec = bool(s["mean"] is not None and s["mean"] < 0 and s["p_lt"] is not None and s["p_lt"] < ALPHA)
        rows.append((f"{bar} bar mean daily slope {_f(s['mean'], 4)} > 0 with Holm one-sided p < 0.05 over the two claimed "
                     f"bars (NW(5) t {_f(s['t'])}, p {_pf(s['p'])}, Holm {_pf(adj2[k])}; {s['n']} sessions)", ok, dec))
    for bar in T666_PRIMARY:
        hv = prim[bar]["halves"]
        rows.append((f"{bar} slope positive in both halves (split {split}: {_f(hv[0], 4)} / {_f(hv[1], 4)})",
                     None if any(v is None for v in hv) else all(v > 0 for v in hv), False))
    n = int(min(prim[b]["n"] for b in T666_PRIMARY))
    v, why, crit = CAL._judge(rows, n, T666_MIN_N, "sessions")

    def cell(u, bar, L):
        s = summ[u][f"{bar}/L{L}"]
        return f"{_f(s['mean'], 3)} (t {_f(s['t'])})"

    tab = "; ".join(f"{bar}: L20 {cell('all', bar, 20)}, L1 {cell('all', bar, 1)}, L1-5 {cell('all', bar, 5)}, stocks "
                    f"{cell('stocks', bar, 20)}, ETFs {cell('etfs', bar, 20)}" for bar in bars)
    sizes = {u: int(np.median(res[u][(T666_PRIMARY[1], 20)]["k"][np.isfinite(res[u][(T666_PRIMARY[1], 20)]["b"])]))
             if np.isfinite(res[u][(T666_PRIMARY[1], 20)]["b"]).any() else 0 for u in unis}
    cover = pan["bar_sessions"]
    n_bars = sum(1 for c in cover if c > 0)
    thin = min(zip(cover, syms))
    reason = (f"{n_bars} of the {nt} registered names with local 60m bars ({ns} local single stocks + {nt - ns} sector "
              f"SPDRs, chosen with hindsight: today's large names, a survivor-biased breadth of {nt}; the thinnest, "
              f"{thin[1]}, has bars on {thin[0]} of {len(days)} sessions), local Yahoo 60m bars {days[0]}..{days[-1]} "
              f"({len(days)} bar sessions; "
              f"{len(pan['early'])} early closes dropped; official prices through {pan['daily_last']}, so the 15:30 bar and "
              f"the overnight control end there); Fama-MacBeth slope of the demeaned bar return on the mean of the name's "
              f"own demeaned same-bar returns over the previous 20 sessions, controls = the two preceding intervals, "
              f"intercept, at least {res['all'][(T666_PRIMARY[0], 20)]['min_names']} names (median {sizes['all']}); "
              f"Holm over the 4 bars (claimed + placebos) {', '.join(f'{b} {_pf(p)}' for b, p in zip(bars, adj4))}; per bar "
              f"(mean slope, NW(5) t): {tab}. Dividends from the adjclose factor for {pan['div_fallback']} SPDRs without "
              f"daily-events. No trading claim is made or tested: a pass is a feature / execution input only")
    stat = {"n_sessions": len(days), "split": split, "primary": prim, "holm_2": adj2, "holm_4": dict(zip(bars, adj4)),
            "summary": summ, "names_median": sizes, "early_closes": pan["early"], "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ==================================================================== T-657 volume-conditioned last half hour ==

def trailing_tercile(x: np.ndarray, min_hist: int = T657_MIN_HIST, burn: int = T657_BURN, q: float = T657_Q) -> tuple:
    """(top, evaluable, cut-off) per position k: the cut-off is the q-quantile of the finite x at positions < k (an
    expanding window, at least ``min_hist`` values); top = x[k] strictly above it; positions before ``burn`` are never
    evaluable. Nothing at position k or later enters the cut-off at k."""
    x = np.asarray(x, float)
    n = x.size
    top, ok, cut = np.zeros(n, bool), np.zeros(n, bool), np.full(n, np.nan)
    for k in range(burn, n):
        hist = x[:k]
        hist = hist[np.isfinite(hist)]
        if hist.size < min_hist or not np.isfinite(x[k]):
            continue
        c = float(np.quantile(hist, q))
        cut[k], ok[k], top[k] = c, True, bool(x[k] > c)
    return top, ok, cut


def volume_ratio(V: np.ndarray, win: int = T657_VOL_WIN) -> np.ndarray:
    """V[k] / mean(V[k-win..k-1]) (NaN until ``win`` earlier sessions with positive volume exist)."""
    V = np.asarray(V, float)
    out = np.full(V.size, np.nan)
    for k in range(win, V.size):
        w = V[k - win:k]
        if np.isfinite(w).all() and (w > 0).all() and np.isfinite(V[k]):
            out[k] = V[k] / w.mean()
    return out


def t657_sessions(archive, sym: str) -> dict:
    """The session sequence of ``sym`` (NYSE sessions with a 09:30 bar of positive volume, early closes removed) with
    the 09:30 bar, the 15:30 bar open, the official close and the previous official close (raw and dividend-adjusted)."""
    def load():
        tab = bar_table(IA._local("60m", sym))
        ddays, close = CAL._daily(archive, B7C.dh(sym), "close")
        _, adj = CAL._daily(archive, B7C.dh(sym), "adjclose")
        f = adj / close
        dpos = {d: i for i, d in enumerate(ddays)}
        cand = sorted(d for d in tab if T657_START <= d <= T657_END and CAL.is_nyse_session(d))
        ec = IA.early_closes(int(cand[0][:4]), int(cand[-1][:4])) if cand else set()
        cols = defaultdict(list)
        dropped = {"early_close": [], "no_0930_bar": []}
        for d in cand:
            b = tab[d]
            if _early(d, [tab], ec):
                dropped["early_close"].append(d)
                continue
            b9 = b.get("09:30")
            if b9 is None or not (b9[4] > 0):
                dropped["no_0930_bar"].append(d)
                continue
            i = dpos.get(d)
            pc = pca = cl = np.nan
            if i is not None:
                cl = close[i]
                if i > 0 and ddays[i - 1] == CAL.prev_session(date.fromisoformat(d)).isoformat():
                    pc, pca = close[i - 1], close[i - 1] * f[i - 1] / f[i]
            b15 = b.get("15:30")
            for k, val in (("day", d), ("v", b9[4]), ("h9", b9[1]), ("l9", b9[2]), ("p1030", b9[3]),
                           ("o1530", b15[0] if b15 else np.nan), ("close", cl), ("prev", pc), ("prev_adj", pca)):
                cols[k].append(val)
        out = {k: (np.array(v, float) if k != "day" else list(v)) for k, v in cols.items()}
        out["dropped"] = dropped
        return out
    return CAL._cached(archive, ("b13ic_t657", sym), load)


def t657_leg(s: dict, cost: float = T657_COST) -> dict:
    """T-427's rule per session: position sign(r1), r1 = 09:30-bar close / dividend-adjusted previous close - 1 (known at
    10:30), held from the 15:30 bar open to the official close; net = gross - cost on traded days."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r1 = s["p1030"] / s["prev_adj"] - 1.0
        last = s["close"] / s["o1530"] - 1.0
    valid = np.isfinite(r1) & np.isfinite(last) & (s["o1530"] > 0)
    pos = np.where(valid, np.sign(np.nan_to_num(r1)), 0.0)
    gross = np.where(valid, pos * np.nan_to_num(last), np.nan)
    net = np.where(valid, gross - cost * (pos != 0), np.nan)
    return {"r1": r1, "pos": pos, "gross": gross, "net": net, "valid": valid}


def t657_conditions(s: dict) -> dict:
    """Volume ratio and 09:30-bar range with their trailing top-tercile flags (80-session burn-in)."""
    ratio = volume_ratio(s["v"])
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = (s["h9"] - s["l9"]) / s["prev"]
    rng[~np.isfinite(rng)] = np.nan
    tv, okv, cv = trailing_tercile(ratio)
    tr, okr, cr = trailing_tercile(rng)
    return {"ratio": ratio, "range": rng, "volume": (tv, okv, cv), "range_cond": (tr, okr, cr)}


def _cell(net: np.ndarray, mask: np.ndarray) -> dict:
    x = net[mask & np.isfinite(net)]
    r = _nw(x, T657_NW_LAG)
    out = {"n": int(x.size), "mean": r["est"], "t": r["t"], "p": r["p"], "p_lt": r["p_lt"], "dsr": None, "p_defl": None}
    if x.size > 8 and np.std(x) > 0:
        d = float(deflated_sharpe_ratio(x, n_trials=T657_TRIALS))
        out.update(dsr=d, p_defl=1.0 - d)
    return out


def b13_intraday_c_volume_momentum(archive):
    """T-657."""
    miss = B7C._missing(archive, [B7C.dh(s) for s in T657_SYMS])
    if miss:
        return miss
    per = {}
    for sym in T657_SYMS:
        s = t657_sessions(archive, sym)
        if not s.get("day"):
            per[sym] = None
            continue
        leg, cond = t657_leg(s), t657_conditions(s)
        tv, okv, _ = cond["volume"]
        tr, okr, _ = cond["range_cond"]
        burn = np.arange(len(s["day"])) >= T657_BURN
        traded = leg["valid"] & burn
        per[sym] = {"days": s["day"], "dropped": s["dropped"], "leg": leg,
                    "vol": _cell(leg["net"], traded & okv & tv), "vol_comp": _cell(leg["net"], traded & okv & ~tv),
                    "rng": _cell(leg["net"], traded & okr & tr), "rng_comp": _cell(leg["net"], traded & okr & ~tr),
                    "uncond_post_burn": _cell(leg["net"], traded), "uncond_all": _cell(leg["net"], leg["valid"]),
                    "gross_vol": float(np.nanmean(leg["gross"][traded & okv & tv])) if (traded & okv & tv).any() else None,
                    "uncond_gross_all": float(np.nanmean(leg["gross"][leg["valid"]])) if leg["valid"].any() else None}
    if per.get("SPY") is None:
        return _out({"n": 0}, 0, "inconclusive", "no SPY sessions in the local 60m bars (rule 9)")
    fam = [(sym, c) for c in ("vol", "rng") for sym in T657_SYMS]
    ps = [per[sym][c]["p"] if per.get(sym) else None for sym, c in fam]
    adj = B7C.holm(ps)
    holm = {f"{sym}/{c}": a for (sym, c), a in zip(fam, adj)}
    sv = per["SPY"]["vol"]
    pos = sv["mean"] is not None and sv["mean"] > 0
    ok_dsr = None if sv["p_defl"] is None else bool(pos and sv["p_defl"] < ALPHA)
    ok_holm = None if holm["SPY/vol"] is None else bool(pos and holm["SPY/vol"] < ALPHA)
    dec1 = bool(sv["mean"] is not None and sv["mean"] < 0 and sv["p_lt"] is not None and sv["p_lt"] < ALPHA)
    oth = [per[s]["vol"] if per.get(s) else None for s in ("QQQ", "IWM")]
    same = None if any(o is None or o["mean"] is None for o in oth) else all(o["mean"] > 0 for o in oth)
    dec2 = any(o is not None and o["t"] is not None and o["t"] <= -Z95 for o in oth)
    comp = per["SPY"]["vol_comp"]
    plc = None if comp["mean"] is None else bool(comp["mean"] <= 0)
    dec3 = bool(comp["t"] is not None and comp["t"] >= Z95)
    rows = [(f"SPY top-tercile-volume days mean net {_bp(sv['mean'])} > 0 with one-sided deflated p < 0.05 over 66 trials "
             f"(1 - DSR {_pf(sv['p_defl'])}; Holm over 2 conditions x 3 ETFs of the NW(5) p {_pf(holm['SPY/vol'])}, NW t "
             f"{_f(sv['t'])}: both readings must agree)", CAL._agree([ok_dsr, ok_holm]), dec1),
            (f"QQQ and IWM the same sign on their own top-tercile-volume days (QQQ {_bp(oth[0]['mean'] if oth[0] else None)}, "
             f"IWM {_bp(oth[1]['mean'] if oth[1] else None)})", same, dec2),
            (f"placebo: SPY complement days' mean net not also > 0 ({_bp(comp['mean'])}, {comp['n']} days, NW t "
             f"{_f(comp['t'])})", plc, dec3)]
    n = int(sv["n"])
    v, why, crit = CAL._judge(rows, n, T657_MIN_N, "condition days")

    def line(sym):
        p = per.get(sym)
        if p is None:
            return f"{sym} n/a"
        c = lambda k: f"{_bp(p[k]['mean'])} (n {p[k]['n']}, t {_f(p[k]['t'])})"
        return (f"{sym}: volume top {c('vol')} / complement {c('vol_comp')}; range top {c('rng')} / complement "
                f"{c('rng_comp')}; unconditional after burn-in {c('uncond_post_burn')}, all days {c('uncond_all')} (gross "
                f"{_bp(p['uncond_gross_all'])})")

    sd = per["SPY"]["days"]
    reason = (f"local Yahoo 60m bars + daily-history official closes, SPY sessions {sd[0]}..{sd[-1]} ({len(sd)} with a 09:30 "
              f"bar; {len(per['SPY']['dropped']['early_close'])} early closes excluded; the first {T657_BURN} sessions are "
              f"the burn-in; official closes through the daily-history end); rule sign(prev close -> 10:30) held 15:30 bar "
              f"open -> official close at 2 bp round trip; trailing top-tercile cut-offs from earlier sessions only. "
              + "; ".join(line(s) for s in T657_SYMS)
              + f"; SPY top-volume gross {_bp(per['SPY']['gross_vol'])}; Holm-adjusted NW p's "
              + ", ".join(f"{k} {_pf(a)}" for k, a in holm.items())
              + ". T-427's recorded unconditional result: -0.09 bp gross, -2.09 bp net on 720 days. A positive subset of a "
                "flat base rule implies a negative complement (the verifier's forking-path warning)")
    stat = {"n": n, "per": {s: ({k: p[k] for k in ("vol", "vol_comp", "rng", "rng_comp", "uncond_post_burn", "uncond_all",
                                                    "gross_vol", "uncond_gross_all", "dropped")} if p else None)
                            for s, p in per.items()},
            "holm": holm, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ===================================================================== T-661 negative reversal intensity XS ==

def month_starts(days: Sequence[str]) -> tuple:
    """(months, first row index of each month) of a sorted session list."""
    months, starts = [], []
    for i, d in enumerate(days):
        if not months or months[-1] != d[:7]:
            months.append(d[:7])
            starts.append(i)
    return months, np.array(starts, int)


def reversal_shares(R: np.ndarray, RI: np.ndarray, starts: np.ndarray, min_days: int = T661_MIN_DAYS) -> tuple:
    """Month x name shares of valid days (finite overnight R and intraday RI) with R > 0 and RI < 0 (negative reversal)
    and with R < 0 and RI > 0 (the positive-reversal placebo); NaN below ``min_days`` valid days. Row m uses only the
    sessions of month m."""
    valid = np.isfinite(R) & np.isfinite(RI)
    with np.errstate(invalid="ignore"):
        neg = valid & (R > 0) & (RI < 0)
        pos = valid & (R < 0) & (RI > 0)
    nv = np.add.reduceat(valid.astype(np.int32), starts, axis=0)
    nn = np.add.reduceat(neg.astype(np.int32), starts, axis=0)
    npo = np.add.reduceat(pos.astype(np.int32), starts, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sn = np.where(nv >= min_days, nn / np.maximum(nv, 1), np.nan)
        sp = np.where(nv >= min_days, npo / np.maximum(nv, 1), np.nan)
    return sn, sp, nv


def intensity(share: np.ndarray, prior: int = T661_PRIOR) -> np.ndarray:
    """NR[m] = share[m] / mean(share[m-prior..m-1]); NaN unless share[m] and all ``prior`` earlier shares are finite and
    their mean is positive."""
    share = np.asarray(share, float)
    M, N = share.shape
    fin = np.isfinite(share)
    cs = np.vstack([np.zeros(N), np.cumsum(np.where(fin, share, 0.0), axis=0)])
    cf = np.vstack([np.zeros(N, int), np.cumsum(fin, axis=0)])
    out = np.full((M, N), np.nan)
    for m in range(prior, M):
        mean = (cs[m] - cs[m - prior]) / prior
        ok = (cf[m] - cf[m - prior] == prior) & fin[m] & (mean > 0)
        out[m, ok] = share[m, ok] / mean[ok]
    return out


def hold_returns(A: np.ndarray, s: int, e: int) -> np.ndarray:
    """A[e] / A[s] - 1 per name; a name without a price at e exits at its last price in (s, e]; NaN without either."""
    a0 = A[s]
    W = A[s + 1:e + 1]
    fin = np.isfinite(W)
    last = np.where(fin, np.arange(W.shape[0])[:, None], -1).max(axis=0)
    a1 = np.where(last >= 0, W[np.maximum(last, 0), np.arange(W.shape[1])], np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = a1 / a0 - 1.0
    r[~np.isfinite(r)] = np.nan
    return r


def _port(w: np.ndarray, r: np.ndarray) -> float | None:
    ok = (w > 0) & np.isfinite(r)
    if not ok.any():
        return None
    return float(w[ok] @ r[ok] / w[ok].sum())


def _drift(w: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Weights at the end of a hold: w (1 + r) renormalised over the names with a return (the rest were sold)."""
    out = np.zeros_like(w)
    ok = (w > 0) & np.isfinite(r)
    if ok.any():
        v = w[ok] * (1.0 + r[ok])
        if v.sum() > 0:
            out[ok] = v / v.sum()
    return out


def factor_table(archive) -> dict:
    """{day: FF5 + UMD daily returns in decimals} on the days every series prints."""
    def load():
        cols = [CAL._series(archive, FF5_B, c) for c in FF5_COLS] + [CAL._series(archive, MOM_B, "Mom")]
        days = set(cols[0])
        for c in cols[1:]:
            days &= set(c)
        return {d: np.array([c[d] / 100.0 for c in cols]) for d in days}
    return CAL._cached(archive, ("b13ic_factors",), load)


def window_factors(days: Sequence[str], fac: dict, s: int, e: int, fac_last: str) -> tuple:
    """Each factor compounded over the sessions s+1..e (the hold's daily returns); (NaN, missing) when the hold runs past
    the factor data; missing counts sessions inside the data span without a factor print."""
    if days[e] > fac_last:
        return np.full(6, np.nan), 0
    rows = [fac.get(days[t]) for t in range(s + 1, e + 1)]
    miss = sum(1 for r in rows if r is None)
    rows = [r for r in rows if r is not None]
    if not rows:
        return np.full(6, np.nan), miss
    return np.prod(1.0 + np.array(rows), axis=0) - 1.0, miss


def t661_formations(inp: dict, first_hold: str = T661_FIRST_HOLD, last_hold: str = T661_LAST_HOLD) -> list:
    """(formation row f, fill row s = f + 1, exit row e = the next fill, holding month) for holds in range."""
    days = inp["days"]
    me = IA.month_ends(days)
    out = []
    for a, b in zip(me[:-1], me[1:]):
        hm = days[a + 1][:7]
        if first_hold <= hm <= last_hold and b + 1 < len(days):
            out.append((a, a + 1, b + 1, hm))
    return out


def t661_scores(inp: dict) -> dict:
    """Month x name NR and PR (from the shares of month m and the 12 months before it) with each month's index."""
    months, st = month_starts(inp["days"])
    sn, sp, nv = reversal_shares(inp["R"], inp["RI"], st)
    return {"months": months, "mpos": {m: k for k, m in enumerate(months)}, "NR": intensity(sn), "PR": intensity(sp),
            "share_neg": sn, "n_valid": nv}


def t661_series(inp: dict, sc: dict, forms: list, score: str = "NR", universe: str = "members") -> dict:
    """Monthly series of the EW top quintile (net of 10 bp per side on traded weight), the bottom quintile (net), the
    EW benchmark (gross) and turnover, for the formations ``forms``. ``universe``: "members" (every spell-checked member
    with a fill price) or "sortable" (members with a score)."""
    A = inp["base"]["adjclose"]
    C = inp["C"]
    S = sc[score]
    out = defaultdict(list)
    w_top_prev = w_bot_prev = None
    r_top_prev = r_bot_prev = None
    for f, s, e, hm in forms:
        m = sc["mpos"][inp["days"][f][:7]]
        sc_row = S[m]
        mem = inp["VM"][f] & np.isfinite(C[s]) & np.isfinite(A[s])
        el = mem & np.isfinite(sc_row)
        n = int(el.sum())
        k = n // T661_Q
        r = hold_returns(A, s, e)
        if k < 1:
            continue
        ft = SX.tail_fractions(sc_row, el, k, True)
        fb = SX.tail_fractions(sc_row, el, k, False)
        wt, wb = ft / ft.sum(), fb / fb.sum()
        uni = el if universe == "sortable" else mem
        wu = uni.astype(float) / max(1, uni.sum())
        dt = _drift(w_top_prev, r_top_prev) if w_top_prev is not None else np.zeros_like(wt)
        db = _drift(w_bot_prev, r_bot_prev) if w_bot_prev is not None else np.zeros_like(wb)
        to_t, to_b = float(np.abs(wt - dt).sum()), float(np.abs(wb - db).sum())
        gt, gb, gu = _port(wt, r), _port(wb, r), _port(wu, r)
        if gt is None or gb is None or gu is None:
            continue
        out["month"].append(hm); out["f"].append(f); out["s"].append(s); out["e"].append(e)
        out["top_gross"].append(gt); out["top_net"].append(gt - T661_COST * to_t)
        out["bot_net"].append(gb - T661_COST * to_b); out["univ"].append(gu)
        out["turnover"].append(to_t); out["n_sort"].append(n); out["n_univ"].append(int(uni.sum()))
        out["no_exit_price"].append(int(((wt > 0) & ~np.isfinite(r)).sum()))
        w_top_prev, w_bot_prev, r_top_prev, r_bot_prev = wt, wb, r, r
    return {k: (np.array(v) if k != "month" else v) for k, v in out.items()}


def alpha_fit(y: np.ndarray, X: np.ndarray, lag: int = T661_NW_LAG) -> dict:
    """OLS y = a + X b with NW(lag) s.e.: alpha, t, one-sided p's and the factor-hedged series (a + residual)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(y.size, -1)
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    r = SX.ols_nw(y[ok], X[ok], lag)
    out = {"alpha": r.get("alpha"), "se": r.get("se"), "t": r.get("t"), "betas": r.get("betas"), "n": int(ok.sum()),
           "p": None, "p_lt": None, "hedged": None}
    if r.get("t") is not None:
        out["p"], out["p_lt"] = 1.0 - _phi(r["t"]), _phi(r["t"])
        out["hedged"] = y[ok] - X[ok] @ np.array(r["betas"])
    return out


def t661_dtc(archive, inp: dict, forms: list) -> np.ndarray | None:
    """Formation x name FINRA days to cover of the latest release published before each formation session's 16:00 ET
    close (diagnostic); None when the FINRA bundles are absent."""
    if not B7C._has(archive, FINRA_FIRST_B):
        return None
    syms = inp["syms"]
    fsyms = [IB.finra_sym(s) for s in syms]
    rel = IB.finra_rows(archive, frozenset(fsyms))
    ts = np.array([SX._et_ts(inp["days"][f], 16, 0) for f, *_ in forms])
    return IB.dtc_known(rel, ts, fsyms)


def _tercile_masks(x: np.ndarray, el: np.ndarray) -> list:
    """Three boolean masks of the eligible finite x by tercile (cut at the 1/3 and 2/3 quantiles)."""
    v = el & np.isfinite(x)
    if v.sum() < 15:
        return [np.zeros_like(v)] * 3
    q1, q2 = np.quantile(x[v], [1 / 3, 2 / 3])
    return [v & (x <= q1), v & (x > q1) & (x <= q2), v & (x > q2)]


def t661_tercile_diag(inp: dict, sc: dict, forms: list, Z: np.ndarray | None, label: str) -> dict:
    """Gross top-NR-quintile minus tercile-universe mean monthly excess within terciles of Z (formation x name)."""
    if Z is None:
        return {"label": label, "available": False}
    A = inp["base"]["adjclose"]
    res = [[], [], []]
    for k, (f, s, e, hm) in enumerate(forms):
        m = sc["mpos"][inp["days"][f][:7]]
        el = inp["VM"][f] & np.isfinite(inp["C"][s]) & np.isfinite(A[s]) & np.isfinite(sc["NR"][m])
        r = hold_returns(A, s, e)
        for t, mk in enumerate(_tercile_masks(Z[k], el)):
            n = int(mk.sum())
            if n // T661_Q < 1:
                continue
            ft = SX.tail_fractions(sc["NR"][m], mk, n // T661_Q, True)
            gt, gu = _port(ft / ft.sum(), r), _port(mk.astype(float) / n, r)
            if gt is not None and gu is not None:
                res[t].append(gt - gu)
    out = {"label": label, "available": True}
    for t, name in enumerate(("low", "mid", "high")):
        x = np.array(res[t])
        r = _nw(x, T661_NW_LAG)
        out[name] = {"n": int(x.size), "mean": r["est"], "t": r["t"]}
    return out


def t661_cover_text(cov: dict) -> str:
    """The coverage-gate criterion text: computed either way, met or not (unmet = a None cap, never 'not implemented')."""
    share = cov.get("share")
    pct = "n/a" if share is None else f"{share * 100:.1f}%"
    head = (f"coverage gate (>= {T661_COVER * 100:.0f}% of fja member-months at the formation month-ends priced by a "
            f"spell-checked series): {cov.get('priced')} of {cov.get('member_months')}, {pct}")
    if share is not None and share >= T661_COVER:
        return head + " - met"
    return (head + f" - NOT met ({pct} < {T661_COVER * 100:.0f}%; computed, not missing): support is impossible; a cap that "
            f"does not override a failing criterion")


def t661_why(why: str) -> str:
    """``_verdict`` labels every None criterion 'not implemented'; here a None row is a computed-but-unmet cap (the
    coverage gate) or two readings that disagree, so the label is replaced by what it means."""
    return (why.replace(" (not implemented: ", " (None criteria, capping the verdict below supported without overriding "
                                                "the failure: ")
               .replace("implemented criteria pass; not implemented: ", "implemented criteria pass; None criteria (capped "
                                                                         "at inconclusive): "))


def b13_intraday_c_reversal_intensity(archive):
    """T-661."""
    miss = B7C._missing(archive, ["daily-history-SPY", IA.FJA_B, IA.SPELLS_B, FF5_B, MOM_B])
    if miss:
        return miss
    inp = IA.t660_inputs(archive)
    sc = t661_scores(inp)
    forms = t661_formations(inp)
    fac = factor_table(archive)
    fac_last = max(fac) if fac else "0000-00-00"
    days = inp["days"]

    def fit(ser: dict, which: str) -> dict:
        y = ser["top_net"] - ser["univ"] if which == "lo" else ser["top_net"] - ser["bot_net"]
        X, miss_f = [], 0
        for s, e in zip(ser["s"], ser["e"]):
            x, mf = window_factors(days, fac, int(s), int(e), fac_last)
            X.append(x)
            miss_f += mf
        X = np.array(X).reshape(len(y), 6)
        a = alpha_fit(y, X)
        a["y"], a["X"], a["missing_factor_sessions"] = y, X, miss_f
        return a

    nr = t661_series(inp, sc, forms, "NR")
    if len(nr.get("month", [])) < 8:
        return _out({"n": len(nr.get("month", []))}, 0, "inconclusive", "fewer than 8 holding months could be formed (rule 9)")
    lo = fit(nr, "lo")
    ls = fit(nr, "ls")
    pr = t661_series(inp, sc, forms, "PR")
    pr_lo, pr_ls = fit(pr, "lo"), fit(pr, "ls")
    n = int(lo["n"])
    srs = [float(sharpe_ratio(c["hedged"])) for c in (lo, ls, pr_lo, pr_ls) if c["hedged"] is not None and c["hedged"].size > 2]
    var_obs = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    var_used = max(var_obs, 1.0 / max(1, n - 1))
    dsr = float(deflated_sharpe_ratio(lo["hedged"], n_trials=T661_CELLS, var_trials_sr=var_used)) if lo["hedged"] is not None else None
    p_dsr = None if dsr is None else 1.0 - dsr
    p_bonf = None if lo["p"] is None else min(1.0, T661_CELLS * lo["p"])
    a_pos = lo["alpha"] is not None and lo["alpha"] > 0
    ok_dsr = None if p_dsr is None else bool(a_pos and p_dsr < ALPHA)
    ok_bonf = None if p_bonf is None else bool(a_pos and p_bonf < ALPHA)
    dec1 = bool(lo["alpha"] is not None and lo["alpha"] < 0 and lo["p_lt"] is not None and lo["p_lt"] < ALPHA)
    months = np.array(nr["month"])
    halves = []
    for msk in (months < T661_SPLIT, months >= T661_SPLIT):
        h = alpha_fit(lo["y"][msk], lo["X"][msk])
        halves.append(h["alpha"])
    cov = IA.coverage(inp, CAL._prev_month(T661_FIRST_HOLD), CAL._prev_month(T661_LAST_HOLD))   # formation months
    cov_ok = True if cov["share"] is not None and cov["share"] >= T661_COVER else None
    rows = [(f"long-only top-NR-quintile minus EW member universe, net of 10 bp per side on traded weight: FF5+UMD monthly "
             f"alpha {_bp(lo['alpha'])} > 0 with one-sided deflated p < 0.05 over {T661_CELLS} cells (NW(3) t "
             f"{_f(lo['t'])}; Bonferroni-deflated p {_pf(p_bonf)}, 1 - DSR of the hedged series {_pf(p_dsr)}: both "
             f"readings must agree)", CAL._agree([ok_dsr, ok_bonf]), dec1),
            (f"alpha positive in 2018-2021 and in 2022-2026 ({_bp(halves[0])} / {_bp(halves[1])})",
             None if any(h is None for h in halves) else all(h > 0 for h in halves), False),
            (t661_cover_text(cov), cov_ok, False)]
    v, why, crit = CAL._judge(rows, n, T661_MIN_N, "holding months")
    why = t661_why(why)
    # ---- reported
    sort_u = t661_series(inp, sc, forms, "NR", universe="sortable")
    sort_lo = fit(sort_u, "lo") if len(sort_u.get("month", [])) > 8 else {"alpha": None, "t": None}
    caps = np.full((len(forms), len(inp["syms"])), np.nan)
    for k, (f, *_r) in enumerate(forms):
        cols = np.flatnonzero(inp["VM"][f])
        caps[k, cols] = IA.caps_at(inp, f, cols)
    size = t661_tercile_diag(inp, sc, forms, caps, "size (cap at formation)")
    dtc_error = None
    try:
        dtc = t661_dtc(archive, inp, forms)
    except (KeyError, TypeError, ValueError, OSError) as exc:  # pragma: no cover - a diagnostic never stops the test
        dtc, dtc_error = None, repr(exc)
    dtcd = t661_tercile_diag(inp, sc, forms, dtc, "FINRA days to cover (published before the formation close)")
    dtcd["error"] = dtc_error
    hv_ex = [float(np.mean(lo["y"][msk])) for msk in (months < T661_SPLIT, months >= T661_SPLIT)]

    def terc(dg):
        if not dg.get("available"):
            return f"{dg['label']}: not available"
        return f"{dg['label']}: " + ", ".join(f"{k} {_bp(dg[k]['mean'])} (t {_f(dg[k]['t'])}, {dg[k]['n']})" for k in ("low", "mid", "high"))

    sw = inp["spell_why"]
    reason = (f"point-in-time S&P 500 members (fja05680 + later Wikipedia changes, T-660's ticker-spell check) priced from "
              f"the 901-symbol Yahoo daily-history set, which is TODAY's universe: delisted members have no prices, so every "
              f"number is survivor-biased beyond what the coverage gate measures, and the universe is all large caps, where "
              f"the paper's effect is smallest (the verifier's power note: an alpha under ~0.2%/month is undetectable); "
              f"holding months {nr['month'][0]}..{nr['month'][-1]} ({len(nr['month'])} formed, {n} with factors through "
              f"{fac_last}); top quintile mean {np.mean(nr['n_sort']) / T661_Q:.0f} names of {np.mean(nr['n_sort']):.0f} "
              f"sortable ({np.mean(nr['n_univ']):.0f} in the member universe); mean monthly excess net {_bp(float(np.mean(lo['y'])))} "
              f"(gross top {_bp(float(np.mean(nr['top_gross'])))} vs universe {_bp(float(np.mean(nr['univ'])))}; mean traded "
              f"weight {np.mean(nr['turnover']):.2f} a month = {_bp(float(np.mean(nr['turnover'])) * T661_COST)} cost); "
              f"halves of the excess {_bp(hv_ex[0])} / {_bp(hv_ex[1])}; secondary top-minus-bottom alpha {_bp(ls['alpha'])} "
              f"(t {_f(ls['t'])}); placebo positive-reversal intensity: long-only alpha {_bp(pr_lo['alpha'])} (t "
              f"{_f(pr_lo['t'])}), long-short {_bp(pr_ls['alpha'])} (t {_f(pr_ls['t'])}); against the NR-sortable universe "
              f"alpha {_bp(sort_lo['alpha'])} (t {_f(sort_lo['t'])}); gross diagnostics within terciles: {terc(size)}; "
              f"{terc(dtcd)}; trial-Sharpe variance {var_obs:.4f} observed over {len(srs)} computed cells, {var_used:.4f} "
              f"used; ticker-reuse refusals {len(sw['late_series'])} later-series spells, {len(sw['unverified_earlier_spell'])} "
              f"unverified earlier spells; dividends from adjclose for {inp['div_fallback']} symbols; top-quintile names "
              f"without an exit price (exited at their last close) {int(np.sum(nr['no_exit_price']))} name-months; "
              f"sessions without a factor print inside the factor span {lo['missing_factor_sessions']}. The coverage gate was "
              f"computed ({'met' if cov_ok else 'NOT met'}); unmet, it is a None criterion: support is impossible, but as a "
              f"cap it does not override a failing criterion, so a failure elsewhere still gives not_supported")
    stat = {"n_months": n, "n_formed": len(nr["month"]), "alpha": {k: lo[k] for k in ("alpha", "se", "t", "p", "p_lt", "betas", "n")},
            "p_bonferroni": p_bonf, "dsr": dsr, "p_dsr": p_dsr, "var_trials_sr_observed": var_obs, "var_trials_sr_used": var_used,
            "halves_alpha": halves, "halves_excess": hv_ex, "coverage": cov,
            "long_short": {k: ls[k] for k in ("alpha", "t", "n")}, "placebo_pr": {"lo": {k: pr_lo[k] for k in ("alpha", "t", "n")},
            "ls": {k: pr_ls[k] for k in ("alpha", "t", "n")}}, "sortable_universe": {k: sort_lo.get(k) for k in ("alpha", "t")},
            "size_terciles": size, "dtc_terciles": dtcd, "mean_excess": float(np.mean(lo["y"])),
            "turnover_mean": float(np.mean(nr["turnover"])), "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ========================================================================================= T-668 BTC 22:00 UTC ==

def hour_last_closes(rows) -> dict:
    """{UTC hour index (t // 3600): (bar start t, close)} of the latest minute bar inside each hour."""
    out: dict = {}
    for r in rows:
        v = r.get("value") or {}
        try:
            t, c = int(v["t"]), float(v["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (c > 0 and math.isfinite(c)):
            continue
        h = t // 3600
        cur = out.get(h)
        if cur is None or t > cur[0]:
            out[h] = (t, c)
    return out


def hour_end_closes(hl: dict) -> tuple:
    """(first hour index h0, CE, empty hours): CE[k] = the close at minute :59 of hour h0 + k, forward-filled from the
    latest earlier minute bar when the hour has none."""
    if not hl:
        return None, np.array([]), 0
    hs = sorted(hl)
    h0 = hs[0]
    CE = np.full(hs[-1] - h0 + 1, np.nan)
    for h, (_t, c) in hl.items():
        CE[h - h0] = c
    empty = int((~np.isfinite(CE)).sum())
    idx = np.where(np.isfinite(CE), np.arange(CE.size), 0)
    np.maximum.accumulate(idx, out=idx)
    return h0, CE[idx], empty


def block_returns(h0: int, CE: np.ndarray, day_ids: Sequence[int]) -> np.ndarray:
    """Day x 12 log returns of the 2-hour UTC blocks: r[d, b] = log(CE[24 d + 2b + 1] / CE[24 d + 2b - 1]) (block 0 from
    the previous day's 23:59); NaN outside the data. ``day_ids`` are days since the epoch (UTC)."""
    out = np.full((len(day_ids), 12), np.nan)
    if h0 is None:
        return out
    for i, dd in enumerate(day_ids):
        for b in range(12):
            a, z = 24 * dd + 2 * b - 1 - h0, 24 * dd + 2 * b + 1 - h0
            if a >= 0 and z < CE.size:
                out[i, b] = math.log(CE[z] / CE[a])
    return out


def _span_days(entry) -> set:
    """UTC days a minute bundle covers whole: its span tag when tagged complete, else the span's days before its end."""
    tags = list(getattr(entry, "tags", []) or [])
    sp = next((t[5:] for t in tags if t.startswith("span:")), None)
    if not sp or ".." not in sp:
        return set()
    a, b = (date.fromisoformat(x) for x in sp.split(".."))
    if "complete" not in tags:
        b = b - timedelta(days=1)
    out, d = set(), a
    while d <= b:
        out.add(d.isoformat())
        d += timedelta(days=1)
    return out


def venue_blocks(archive, prefix: str, span: tuple) -> dict:
    """{days, R (day x 12 block log returns), empty_hours, bundles} from the venue's monthly minute bundles in ``span``.
    Cached."""
    def load():
        names = [n for n in SX._entry_names(archive, prefix) if span[0] <= n[len(prefix):] <= span[1]]
        hl, full = {}, set()
        for nm in names:
            full |= _span_days(archive.get(nm))
            hl.update({h: v for h, v in hour_last_closes(SX._stream(archive, nm)).items() if h not in hl or v[0] > hl[h][0]})
        h0, CE, empty = hour_end_closes(hl)
        days = sorted(full)
        ids = [date.fromisoformat(d).toordinal() - date(1970, 1, 1).toordinal() for d in days]
        R = block_returns(h0, CE, ids)
        ok = np.isfinite(R).all(axis=1)
        return {"days": [d for d, k in zip(days, ok) if k], "R": R[ok], "empty_hours": empty, "bundles": len(names),
                "h0": h0, "CE": CE}
    return CAL._cached(archive, ("b13ic_t668", prefix, span), load)


def block_minus_rest(R: np.ndarray, b: int) -> np.ndarray:
    """r_b minus the mean of the other 11 blocks, per day."""
    others = np.delete(R, b, axis=1)
    return R[:, b] - others.mean(axis=1)


def et_block_diffs(h0: int, CE: np.ndarray, days: Sequence[str], start_hour: int) -> np.ndarray:
    """Diagnostic: on each 24-hour New York day, the ET-anchored 2-hour block [start, start + 2) minus the mean of the
    other 11 blocks of the same 2-hour grid (grid phase start % 2); NaN on DST-change days and outside the data."""
    out = np.full(len(days), np.nan)
    ph = start_hour % 2
    for i, d in enumerate(days):
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        t0 = datetime(y, m, dd, 0, 0, tzinfo=NY).timestamp()
        t1 = (datetime(y, m, dd, 0, 0, tzinfo=NY) + timedelta(days=1)).timestamp()   # wall-clock next midnight
        if int(round(t1 - t0)) != 86400:                                              # a DST-change day
            continue
        H = int(t0 // 3600) - h0
        r = []
        for s in range(ph, 24 + ph, 2):
            a, z = H + s - 1, H + s + 1
            r.append(math.log(CE[z] / CE[a]) if 0 <= a and z < CE.size else np.nan)
        r = np.array(r)
        if not np.isfinite(r).all():
            continue
        k = (start_hour - ph) // 2
        out[i] = r[k] - np.delete(r, k).mean()
    return out


def b13_intraday_c_btc_2200_block(archive):
    """T-668."""
    miss = B7C._missing(archive, [T668_CB + "2022-01", T668_KR + "2022-01", "daily-history-SPY"])
    if miss:
        return miss
    from mandel.experiments.batch5_hourly import ols_hac
    cb = venue_blocks(archive, T668_CB, T668_CB_SPAN)
    kr = venue_blocks(archive, T668_KR, T668_KR_SPAN)
    days, R = cb["days"], cb["R"]
    n = len(days)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} complete Coinbase days (rule 9)")
    darr = np.asarray(days)
    tests = []
    for b in range(12):
        d = block_minus_rest(R, b)
        pg, pl, nd = CAL.studentized_p_escalated(d - T668_BAR, T668_BLOCK_DAYS, N_BOOT, SEED, N_SEEDS)
        tests.append({"block": f"{2 * b:02d}:00", "diff": float(d.mean()), "pg": pg, "pl": pl, "draws": nd,
                      "mean_block": float(R[:, b].mean())})
    ps, dr = [t["pg"] for t in tests], [t["draws"] for t in tests]
    dec490 = IB.holm_decide(ps + [None] * T668_HURST, dr + [None] * T668_HURST)[:12]
    dec12 = IB.holm_decide(ps, dr)
    adj12 = B7C.holm(ps)
    adj490 = CAL._holm({k: p for k, p in enumerate(ps)}, m=12 + T668_HURST)
    tg = tests[T668_TARGET]
    dtg = block_minus_rest(R, T668_TARGET)
    point = tg["diff"] > T668_BAR
    ok1 = False if not point else dec490[T668_TARGET]
    dec_1 = CAL.decide_p(tg["pl"], tg["draws"]) is True
    split = days[n // 2]
    halves = [float(dtg[darr < split].mean()), float(dtg[darr >= split].mean())]
    ibit = [float(dtg[darr < T668_IBIT].mean()), float(dtg[darr >= T668_IBIT].mean())]
    kd = block_minus_rest(kr["R"], T668_TARGET) if len(kr["days"]) else np.array([])
    kmean = float(kd.mean()) if kd.size else None
    rows = [(f"22:00-00:00 UTC block minus the other 11 blocks {_bp(tg['diff'])} > 5 bp/day with Holm one-sided p < 0.05 "
             f"(studentized CBB, 7-day blocks, p {CAL._mc(tg['pg'], tg['draws'])}; Holm over the 12 blocks with Hurst's 478 "
             f"coin-hour cells counted, m = 490: adjusted {_pf(adj490[T668_TARGET])})", ok1, dec_1),
            (f"positive in both halves (split {split}: {_bp(halves[0])} / {_bp(halves[1])})", all(h > 0 for h in halves), False),
            (f"positive before and after the IBIT launch {T668_IBIT} ({_bp(ibit[0])} / {_bp(ibit[1])})", all(h > 0 for h in ibit), False),
            (f"positive on Kraken 2022-01..2025-12 ({_bp(kmean)}, {kd.size} days)", None if kmean is None else bool(kmean > 0), False)]
    v, why, crit = CAL._judge(rows, n, T668_MIN_N, "days")
    # ---- reported
    wk = np.array([date.fromisoformat(d).weekday() >= 5 for d in days])
    split_wk = {"weekday": float(dtg[~wk].mean()), "weekend": float(dtg[wk].mean()), "n_weekend": int(wk.sum())}
    et = {}
    for sh in (17, 18):
        x = et_block_diffs(cb["h0"], cb["CE"], days, sh)
        r = _nw(x, CAL.nw_lags(int(np.isfinite(x).sum())))
        et[f"{sh:02d}:00-{sh + 2:02d}:00 ET"] = {"diff": r["est"], "t": r["t"], "n": r["n"]}
    sd, sc = CAL._daily(archive, "daily-history-SPY", "adjclose")
    spy_r = {sd[i]: sc[i] / sc[i - 1] - 1.0 for i in range(1, len(sd))}
    pos = {d: i for i, d in enumerate(days)}
    pairs = [(R[pos[d], T668_TARGET], spy_r[d]) for d in days if d in spy_r]
    reg = {"n": len(pairs), "slope": None, "t": None}
    if len(pairs) > 30:
        yy, xx = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
        b_, se_ = ols_hac(yy, np.column_stack([np.ones(yy.size), xx]))
        reg.update(slope=float(b_[1]), t=float(b_[1] / se_[1]) if se_[1] > 0 else None)
    gross = float(R[:, T668_TARGET].mean())
    nets = {lbl: gross - c for lbl, c in T668_COSTS}
    common = sorted(set(days) & set(kr["days"]))
    corr = None
    if len(common) > 30:
        a_ = np.array([R[pos[d], T668_TARGET] for d in common])
        kp = {d: i for i, d in enumerate(kr["days"])}
        b2 = np.array([kr["R"][kp[d], T668_TARGET] for d in common])
        corr = float(np.corrcoef(a_, b2)[0, 1])
    blk = ", ".join(f"{t['block']} {_bp(t['diff'], 1)} (p {_pf(t['pg'])})" for t in tests)
    reason = (f"Coinbase 1m BTC-USD {days[0]}..{days[-1]} ({n} complete UTC days, {cb['bundles']} bundles, {cb['empty_hours']} "
              f"hours without a trade forward-filled); Kraken 1m XBTUSD {kr['days'][0] if kr['days'] else 'n/a'}.."
              f"{kr['days'][-1] if kr['days'] else 'n/a'} ({len(kr['days'])} days); block = log(close of the last minute / close "
              f"of the minute before the block); per block, minus the other 11, one-sided p vs 5 bp: {blk}; 12-block Holm "
              f"decisions {['reject' if d else ('undecided' if d is None else 'keep') for d in dec12].count('reject')} reject "
              f"(22:00 adjusted {_pf(adj12[T668_TARGET])}); weekday {_bp(split_wk['weekday'])} / weekend {_bp(split_wk['weekend'])}; "
              f"ET-anchored diagnostics " + ", ".join(f"{k} {_bp(e['diff'])} (t {_f(e['t'])})" for k, e in et.items())
              + f"; block return on the same day's SPY close-to-close return: slope {_f(reg['slope'], 4)} (HAC t {_f(reg['t'])}, "
              f"{reg['n']} days); long-the-block mean gross {_bp(gross)} a day = the break-even round trip; net "
              + ", ".join(f"{k} {_bp(x)}" + (" (pre-registered as expected <= 0)" if i == 0 else "")
                          for i, (k, x) in enumerate(nets.items()))
              + f"; Coinbase-Kraken correlation of the block return {_f(corr, 3)}. The whole "
                f"sample is post-publication (SSRN 4081000, 2022). Hurst's BTC 22:00 / 23:00 UTC cells are not in the repo (only "
                f"the aggregate 3 of 478 coin-hours at |t| >= 2.5), so the registration's 'ask Hurst first' step was not done "
                f"by this harness: before recording, ask Hurst for those cells; if they cover Coinbase 2022-2026 they are the "
                f"record under T-668 and this result a replication, otherwise this result is the record")
    stat = {"n_days": n, "tests": tests, "holm_12": adj12, "holm_490": [adj490[k] for k in range(12)],
            "decisions_490": dec490, "decisions_12": dec12, "halves": halves, "split": split, "ibit": ibit,
            "kraken": {"n": int(kd.size), "diff": kmean}, "weekday_weekend": split_wk, "et_anchored": et, "spy_reg": reg,
            "gross_block": gross, "net": nets, "corr_cb_kr": corr, "empty_hours": cb["empty_hours"], "criteria": crit,
            "hurst_cells_pending": True}
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {"b13_intraday_c_same_hour_xs": b13_intraday_c_same_hour_xs,
             "b13_intraday_c_volume_momentum": b13_intraday_c_volume_momentum,
             "b13_intraday_c_reversal_intensity": b13_intraday_c_reversal_intensity,
             "b13_intraday_c_btc_2200_block": b13_intraday_c_btc_2200_block}
THEORY_MAP = {"T-666": "b13_intraday_c_same_hour_xs", "T-657": "b13_intraday_c_volume_momentum",
              "T-661": "b13_intraday_c_reversal_intensity", "T-668": "b13_intraday_c_btc_2200_block"}
