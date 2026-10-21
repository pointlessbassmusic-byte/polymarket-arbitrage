"""
Batch 13, group ``intraday_a``: four intraday / overnight claims from the 2026-10-20 web sweep (cluster "intraday"),
2026-10-21.
=====================================================================================================================

  * T-659  ES 02:00-03:00 ET drift after closing-hour selling (Boyarchenko-Larsen-Whelan, NY Fed SR 917). Local Yahoo
           60m ES_F bars 2024-05-29..2026-10 (NQ_F and RTY_F replications): long one micro contract from the open to the
           close of the 02:00 ET bar on nights after the ES bar stamped 15:00 ET of the preceding US session closed below
           its open (known at 16:00). Cost = (1 tick + $1.00 / point value) / entry price. Excluded: DST-asynchronous
           weeks (New York - London offset 4 h, reported separately with the 03:00 and 04:00 ET hours), contract-roll
           dates, Sunday reopenings, CME holiday / early-close sessions, stale bars (open = high = low = close). Pass: on
           ES the one-sided 95% lower bound of the mean net > 0 (studentized circular block bootstrap, block 5, and HAC
           t), NQ the same sign, the ES mean net positive in both halves, and the conditional mean above the complement-
           night mean. min_n 250 trades.
  * T-669  VIX1D-open FOMC-session variance ratio. R = SPY open-to-close realised variance (7 returns of the 60m bars
           from the 09:30 open to the official close) / ((VIX1D open / 100)^2 x 390 / 525,600), 2023-11-21..2026-10.
           Statistic: mean log R on scheduled FOMC decision days minus matched non-event days (up to 3 per event: same
           weekday, within +/-10 sessions, not OPEX / FOMC / CPI / NFP / early close). Pass: difference > 0.2 with
           one-sided p < 0.05 under a day-level stationary bootstrap (mean block 5) and a permutation over the matched
           sets, a lower 95% bound above 0, and the CPI/NFP placebo difference not significantly different from 0.
           min_n 20 FOMC days. Any pass is partly in-sample (T-529).
  * T-660  Overnight-return persistence in point-in-time S&P 500 members (Lou-Polk-Skouras). At each month-end session
           the value-weighted top decile by the sum of the past 21 overnight returns (through that session's open) is
           held overnight only (MOC buy, next MOO sell) for the following month, against SPY overnight-only; costs 3 bp
           per side per auction for the stocks, 1 bp for SPY. Pass: mean monthly net excess > 0 with one-sided deflated
           p < 0.05 over the 12 registered cells, positive in 2014-2019 and 2020-2026, and the 90% coverage gate met
           (else capped at inconclusive). min_n 140 months (2014-01..2026-09).
  * T-664  Closing-auction deviation reversal on the equity symbols with local 60m bars, 2023-11-21..2026-10: the next
           close-to-open log return on dev = log(official close / close of the 15:30 ET bar), day fixed effects. Pass:
           slope < -0.5 with one-sided day-clustered wild-bootstrap p < 0.05 (Rademacher, 9,999 draws, null imposed),
           slope < 0 in both halves of the sessions, stocks-only slope < 0. min_n 20,000 symbol-days. No costs.

Conventions (every reading fixed before any run; the reasons repeat the binding ones)
  * Data. Archive bundles through ``archive.load`` with the capture-time filter (``batch6c_cal._rows`` / ``_daily``,
    ``batch4_ohlc._bars``); local Yahoo bars through ``mandel.ml.features.load_bars`` (stamped by bar OPEN, so a bar is
    known at stamp + its length). Multi-symbol daily data come from ``panel_cache.daily_panel`` (value-identical to
    ``_daily``) or ``batch13_crossasset_a.xs_base`` (the shared point-in-time S&P panel built on it). Each harness probes
    the archive bundles the registration names and returns inconclusive (rule 9) when one is missing.
  * Point in time. T-659: the condition bar (15:00 ET) closes at 16:00; the trade opens at 02:00 the next morning; the
    VIX diagnostic uses the close of the session before the condition session (``daily-history--VIX`` rows are
    available a day after their bar). T-669: VIX1D is used only at its open; matched days are chosen by calendar rules
    (weekday, session distance, event and OPEX calendars, all scheduled in advance) and never by R. T-660: the signal
    uses overnight returns through the formation session's open, membership as of that session (fja effective dates are
    available at 09:30), SEC cover shares accepted before 09:30 ET of that session, and the previous close. T-664: dev is
    known at the official close; the dependent return starts there.
  * Inference. Resampled p's are pooled over seeds and escalated while their Monte-Carlo band straddles alpha
    (``batch6c_cal.escalate_p`` / ``decide_p``), so a seed never decides a criterion. Where a criterion names two tests
    or admits two registered readings it passes only when both pass and fails only when both fail (``_agree``,
    rule 11). Below min_n a failure counts only when decisive (``batch6c_cal._judge``, rule 5).
  * Rule 10. No claim holds on a free grid phase: T-659 trades every eligible night, T-669 is event-anchored, T-664
    uses every session, and T-660's month-end formation is the registered calendar (the registration fixes the month-
    end formation; there is no other entry phase to pool).

Claim-specific readings (declared before any return was computed)
  * T-659. Nights D -> D+1 with D Monday-Thursday and both days full NYSE sessions (no Sunday reopening, no holiday
    session; D or D+1 an early close is excluded). "Contract-roll dates" = the window from CME's roll Thursday to the
    Monday after expiry, every quarter: the Yahoo continuous series switches contract at the expiry-Friday 16:00 bar and
    on the adjacent Sundays and alternates between contracts bar by bar inside expiry weeks (seen on bar-to-bar price
    gaps only, before any trade return), so a single date would leave mixed-contract bars in. The complement is "closing
    hour not down" (a flat bar counts there). The NQ replication is read two ways that must agree: NQ's own 15:00 bar,
    and ES's. Costs per micro contract: MES 0.25 tick and $5/pt, MNQ 0.25 and $2/pt, M2K 0.10 and $5/pt (1 tick + $1).
    The lower bound must clear 0 under the studentized circular block bootstrap (blocks of 5 consecutive trades) and the
    HAC t (one-sided 1.645). Halves split at 2025-08-09, the calendar midpoint of the bars. Maker variant (report only):
    a bid one tick under the 02:00 open fills only if the low trades through it, exit at the close paying half a tick +
    $1. The VIX diagnostic uses the session before D. The Dukascopy extension is not archived (reported).
  * T-669. RV starts at the 09:30 60m bar's open; the last of the 7 returns runs from the 14:30 bar's close (15:30) to
    the official close (``daily-history-SPY``). The archived ``hourly-SPY`` bundle is used (identical to the local 60m
    file on every overlapping bar). Matching: nearest same-weekday sessions by session distance, ties to the earlier
    date, a non-event day matched to at most one event (events in date order); the matched mean is pooled over matched
    days. The stationary bootstrap is studentized, on the flagged series of the event and matched days in date order;
    the permutation moves the event label within each set under the shifted null (event values - 0.2). "Lower 95%
    bound" = the lower end of the two-sided 95% interval (one-sided p vs 0 at 0.025; the bootstrap-t interval is
    reported). The placebo is CPI and Employment Situation days (FOMC days removed) matched by the same rules, read as
    two-sided p >= 0.05 under both nulls.
  * T-660. Ticker reuse: a fja spell is kept only when the Yahoo series' firstTradeDate is at most 10 days after the
    spell's start and, for an earlier spell of a ticker with several, a Wikipedia removal within 10 days of its end names
    the same company; unverifiable earlier spells are refused; T-473's EQUITY and removed-name filters apply
    (``xs_base``). Cover shares at most 15 months old (``batch6c_stockxs`` convention), split equally across an issuer's
    member classes and scaled by later splits. VW names without shares hold the equal weight 1/k, the rest share the
    remainder by cap. Decile = floor(n/10) names, ties sharing the boundary slots. Nightly weights are fixed at formation
    and renormalised over names with a return that night. "Deflated p" is read two ways that must agree: 1 - DSR over
    the 12 cells (trial-Sharpe variance floored at 1/(T-1)) and the Bonferroni-adjusted NW(3) p. Coverage = fja member
    counts at the month-end sessions of 2014-01..2026-09 against members with a spell-checked series and a close; below
    90% the gate is a None criterion (the house cap: it never turns a failing criterion into inconclusive).
  * T-664. 52 symbols: FXI, ARKK and SMH have no daily-history (no official open/close or dividends) and GLD is not an
    equity symbol. Official prices from ``daily-history`` (through 2026-10-14; the local 1d bars carry no dividends or
    adjclose after the capture, so they are not used). Dividends from ``daily-events`` (the adjclose factor for ETFs
    without one). "Equal" = within 1e-6 relative. Halves split at the median session. The control's 20 bp winsorisation
    is ambiguous between the primary and a robustness reading, so every criterion is read raw and winsorised and must
    agree. Wild bootstrap: null slope -0.5 imposed, cluster-robust t with G / (G - 1), escalated in batches of 9,999.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch5_macro import release_days_from_rows
from mandel.experiments.batch6_surf import _out

SEED = 0
N_BOOT = 2000
N_SEEDS = 5
ALPHA = 0.05
Z1 = 1.6448536269514722            # one-sided 5% normal quantile
NY = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")
UTC = timezone.utc

SPY_B, VIXY_B, VIX1D_B = "daily-history-SPY", "daily-history--VIX", "cboe-VIX1D-history"
HSPY_B = "hourly-SPY"
FOMC_B, CPI_B, NFP_B = "fomc-meetings", "macro-release-cpi", "macro-release-employment-situation"
FJA_B, SPELLS_B = "fja-sp500-components", "fja-sp500-ticker-spells"
FACTS_PREFIX = "sec-companyfacts-"

# T-659
T659_START, T659_END = "2024-05-29", "2026-10-31"
T659_SPLIT = "2025-08-09"          # calendar midpoint of 2024-05-29..2026-10-20 (the local bars' span)
T659_COND_HOUR, T659_TRADE_HOUR = 15, 2
T659_BLOCK = 5
T659_MIN_N = 250
T659_COMM = 1.00                   # $ per round trip
T659_SPEC = {"ES_F": (0.25, 5.0), "NQ_F": (0.25, 2.0), "RTY_F": (0.10, 5.0)}   # (tick in points, micro $ per point)
T659_HOURS = (16, 17, 18, 19, 20, 21, 22, 23) + tuple(range(0, 16))           # the 24 ET hours after the condition
T659_RANK_MIN = 30                 # an hour enters the rank table with at least 30 conditional observations
# T-669
T669_START, T669_END = "2023-11-21", "2026-10-31"
T669_BAR = 0.2
T669_MATCH = 3
T669_WINDOW = 10
T669_BLOCK = 5.0
T669_MIN_N = 20
T669_IV_SCALE = 390.0 / 525600.0
T669_N_PERM = 10000
T669_RANDOM = 1000
T669_BAR_TIMES = ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")
# T-660
T660_START_HOLD, T660_END_HOLD = "2014-01", "2026-09"
T660_REPL = ("2000-01", "2013-12")
T660_SPLIT = "2020-01"             # halves 2014-2019 / 2020-2026
T660_COST_STOCK = 3e-4             # per side per auction
T660_COST_SPY = 1e-4
T660_LOOKBACKS = (5, 21, 63)
T660_PRIMARY = (21, "VW", 10)
T660_CELLS = 12
T660_NW_LAG = 3
T660_MIN_N = 140
T660_COVER = 0.90
T660_SPELL_TOL = 10                # days: a series must exist within 10 days of its member spell's start
T660_SHARES_MAX_AGE = SX.SHARES_MAX_AGE
T660_LOCAL_STOCKS = ("AAPL", "ADBE", "AMD", "AMZN", "AVGO", "BAC", "COIN", "COST", "CRM", "CVX", "GOOGL", "HD", "INTC",
                     "JPM", "LLY", "META", "MSFT", "MSTR", "MU", "NFLX", "NVDA", "ORCL", "PLTR", "SMCI", "TSLA", "UNH",
                     "WMT", "XOM")
# T-664
T664_START = "2023-11-21"
T664_BETA0 = -0.5
T664_N_WILD = 9999
T664_MAX_BATCHES = 10
T664_WINSOR = 20e-4
T664_MIN_N = 20000
T664_STOCKS = T660_LOCAL_STOCKS
T664_SECTORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
T664_OTHER_ETFS = ("SPY", "QQQ", "IWM", "DIA", "MDY", "EEM", "EFA", "EWJ", "EWZ", "FXI", "ARKK", "SMH", "GDX", "VNQ",
                   "TQQQ", "SQQQ")
T664_SEEN = ("SPY", "QQQ", "IWM", "GLD")
T664_EQ_TOL = 1e-6                 # relative: the 15:30 bar close 'equals' the official close


# ================================================================================================ shared helpers ==

_LOCAL: dict = {}


def _local(interval: str, sym: str):
    """Local Yahoo bars (``mandel.ml.features.load_bars``), cached per process; None when absent."""
    key = (interval, sym)
    if key not in _LOCAL:
        try:
            from mandel.ml.features import load_bars
            _LOCAL[key] = load_bars(interval, sym)
        except Exception:  # pragma: no cover - optional local data
            _LOCAL[key] = None
    return _LOCAL[key]


def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, names)


def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f} bp"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pf(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.4f}"


def _mc(p, draws) -> str:
    return CAL._mc(p, draws)


def _sig(point, p, draws, side: str = "greater", alpha: float = ALPHA, bar: float = 0.0) -> Optional[bool]:
    """'point > bar (side greater) / < bar (less) with one-sided p < alpha': False when the point is on the wrong side
    of the bar, else the Monte-Carlo-banded decision of p."""
    if point is None or not np.isfinite(point):
        return None
    if (point <= bar) if side == "greater" else (point >= bar):
        return False
    return CAL.decide_p(p, draws, alpha)


def boot_mean(x, block: int) -> dict:
    """Mean with the studentized circular block-bootstrap one-sided p's (escalated) and the HAC (Newey-West) t."""
    x = np.asarray(x, float)
    out = {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "pg": None, "pl": None, "draws": 0,
           "t": None, "se": None}
    if x.size < 8:
        return out
    pg, pl, nd = CAL.studentized_p_escalated(x, block, N_BOOT, SEED, N_SEEDS)
    h = SX.nw_mean(x, SX.nw_lag(x.size))
    out.update(pg=pg, pl=pl, draws=nd, t=h["t"], se=h["se"], lag=h["lag"])
    return out


def _lb_ok(b: dict) -> tuple:
    """(ok, decisive) for 'one-sided 95% lower bound of the mean > 0' read by the bootstrap and by the HAC t."""
    if b["mean"] is None or b["pg"] is None:
        return None, False
    boot = _sig(b["mean"], b["pg"], b["draws"])
    hac = None if b["t"] is None else bool(b["mean"] > 0 and b["t"] > Z1)
    dec = bool(CAL.decide_p(b["pl"], b["draws"]) is True and b["t"] is not None and b["t"] < -Z1)
    return CAL._agree([boot, hac]), dec


# ============================================================================================== calendars (NYSE) ==

def early_closes(first_year: int, last_year: int) -> set:
    """Scheduled NYSE 13:00 early closes: the day after Thanksgiving, Christmas Eve when it falls Monday-Thursday, and 3
    July when Independence Day falls Tuesday-Friday."""
    out = set()
    for y in range(first_year, last_year + 1):
        out.add((CAL._nth_weekday(y, 11, 3, 4) + timedelta(days=1)).isoformat())
        ce = date(y, 12, 24)
        if ce.weekday() <= 3:
            out.add(ce.isoformat())
        if 1 <= date(y, 7, 4).weekday() <= 4:
            out.add(date(y, 7, 3).isoformat())
    return out


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7 + 14)


def opex_days(first_year: int, last_year: int) -> set:
    """Monthly option expiries: the third Friday, or the session before it when that Friday is a holiday."""
    out = set()
    for y in range(first_year, last_year + 1):
        for m in range(1, 13):
            d = third_friday(y, m)
            while not CAL.is_nyse_session(d):
                d -= timedelta(days=1)
            out.add(d.isoformat())
    return out


def roll_windows(first_year: int, last_year: int) -> list:
    """Equity-index futures roll windows: from CME's roll date (8 days before the third Friday of Mar/Jun/Sep/Dec, a
    Thursday) through the Monday after expiry. The Yahoo continuous series switches contract at expiry and on the
    adjacent Sundays, and alternates between contracts bar by bar inside expiry weeks (checked on price gaps only)."""
    out = []
    for y in range(first_year, last_year + 1):
        for m in (3, 6, 9, 12):
            f = third_friday(y, m)
            out.append(((f - timedelta(days=8)).isoformat(), (f + timedelta(days=3)).isoformat()))
    return out


def in_windows(day: str, wins: Sequence[tuple]) -> bool:
    return any(a <= day <= b for a, b in wins)


def ny_london_offset(ts: float) -> float:
    """New York minus London UTC offset in hours at epoch ``ts``: -5 normally, -4 in the DST-asynchronous weeks."""
    dt = datetime.fromtimestamp(float(ts), tz=UTC)
    return (dt.astimezone(NY).utcoffset() - dt.astimezone(LON).utcoffset()).total_seconds() / 3600.0


def _fomc_days(archive) -> list:
    return sorted({(r.get("value") or {}).get("decision_day") for r in CAL._rows(archive, FOMC_B)
                   if (r.get("value") or {}).get("scheduled") and not r["value"].get("future")
                   and r["value"].get("decision_day")})


def _release_days(archive, name: str, kind: str) -> list:
    return release_days_from_rows(CAL._rows(archive, name), kind)[0]


# ===================================================================================================== T-659 ES ==

def et_bars(df) -> dict:
    """{(ET date, ET hour): (open, high, low, close, UTC epoch of the bar start)} of the on-the-hour 60m bars."""
    if df is None or len(df) == 0:
        return {}
    df = df[df.index.minute == 0]
    ny = df.index.tz_convert("America/New_York")
    ts = df.index.as_unit("s").asi8
    out = {}
    for d, h, o, hi, lo, c, t in zip(ny.strftime("%Y-%m-%d"), ny.hour, df["o"].to_numpy(float), df["h"].to_numpy(float),
                                    df["l"].to_numpy(float), df["c"].to_numpy(float), ts):
        out[(d, int(h))] = (float(o), float(hi), float(lo), float(c), float(t))
    return out


def _stale(b) -> bool:
    return b[0] == b[1] == b[2] == b[3]


def closing_hour_signal(bars: dict, day: str) -> Optional[dict]:
    """The condition of T-659 for the US session ``day``: the bar stamped 15:00 ET closed below its open. Uses only
    that bar, complete at 16:00 ET. None when the bar is missing."""
    b = bars.get((day, T659_COND_HOUR))
    if b is None:
        return None
    return {"down": bool(b[3] < b[0]), "ret": b[3] / b[0] - 1.0, "stale": _stale(b), "known_at": b[4] + 3600.0}


def t659_nights(bars: dict, sym: str, start: str = T659_START, end: str = T659_END, cond_bars: Optional[dict] = None,
                ec: Optional[set] = None, rolls: Optional[list] = None) -> list:
    """One row per candidate night D -> D+1 (D Monday-Thursday, so the overnight session is never a Sunday reopening):
    condition from ``cond_bars`` (default: the symbol's own bars), trade = the 02:00 ET bar of D+1, every exclusion
    flag, and the net returns of the 24 hourly bars after the condition (cost = (tick + $1 / point value) / open)."""
    tick, mult = T659_SPEC[sym]
    cost_pts = tick + T659_COMM / mult
    cb = bars if cond_bars is None else cond_bars
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    ec = early_closes(d0.year, d1.year) if ec is None else ec
    rolls = roll_windows(d0.year, d1.year) if rolls is None else rolls
    out = []
    d = d0
    while d <= d1:
        if d.weekday() <= 3:
            D, D1 = d.isoformat(), (d + timedelta(days=1)).isoformat()
            sig = closing_hour_signal(cb, D)
            tr = bars.get((D1, T659_TRADE_HOUR))
            if sig is not None and tr is not None:
                row = {"day": D, "trade_day": D1, "down": sig["down"], "cond_ret": sig["ret"],
                       "session": CAL.is_nyse_session(D) and CAL.is_nyse_session(D1),
                       "early": D in ec or D1 in ec, "roll": in_windows(D, rolls) or in_windows(D1, rolls),
                       "stale": sig["stale"] or _stale(tr), "async": ny_london_offset(tr[4]) > -4.5,
                       "o": tr[0], "h": tr[1], "l": tr[2], "c": tr[3], "tick": tick, "comm_pts": T659_COMM / mult}
                row["gross"] = tr[3] / tr[0] - 1.0
                row["net"] = row["gross"] - cost_pts / tr[0]
                hrs = {}
                for h in T659_HOURS:
                    b = bars.get((D, h)) if h >= 16 else bars.get((D1, h))
                    if b is not None and not _stale(b):
                        hrs[h] = b[3] / b[0] - 1.0 - cost_pts / b[0]
                row["hours"] = hrs
                row["eligible"] = row["session"] and not (row["early"] or row["roll"] or row["stale"])
                out.append(row)
        d += timedelta(days=1)
    return out


def maker_net(r: dict) -> Optional[float]:
    """Report-only maker entry: a resting bid one tick under the 02:00 open fills only when the bar trades through it
    (low < bid); exit at the close paying half a tick plus the $1 commission. None when unfilled."""
    bid = r["o"] - r["tick"]
    if not r["l"] < bid:
        return None
    return (r["c"] - r["tick"] / 2.0 - bid) / bid - r["comm_pts"] / bid


def spy_overnight(archive, nights: Sequence[dict]) -> dict:
    """T-549's construction on SPY (official close of D -> official open of D+1, dividend added back, 1 bp a side) on
    the given nights."""
    b = OHLC._bars(archive, "SPY")
    pos = {d: i for i, d in enumerate(b.days)}
    div = OHLC.ex_dividends(b.close, b.adj)
    out = []
    for r in nights:
        i, j = pos.get(r["day"]), pos.get(r["trade_day"])
        if i is None or j is None or j != i + 1:
            continue
        out.append(b.open[j] / b.close[i] - 1.0 + div[j] / b.close[i] - 2 * 1e-4)
    return {"n": len(out), "mean": float(np.mean(out)) if out else None}


def _vix_split(archive, rows: Sequence[dict]) -> dict:
    """Diagnostic: conditional trades split by the VIX close of the session before D against its trailing 252-session
    median (both known before D's close)."""
    days, vix = CAL._daily(archive, VIXY_B, "close")
    out = {"high": [], "low": []}
    for r in rows:
        k = bisect.bisect_left(days, r["day"]) - 1
        if k < 252:
            continue
        med = float(np.median(vix[k - 252:k]))
        out["high" if vix[k] > med else "low"].append(r["net"])
    return {k: {"n": len(v), "mean": float(np.mean(v)) if v else None} for k, v in out.items()}


def b13_intraday_a_es_0200_drift(archive):
    """T-659."""
    miss = _missing(archive, [SPY_B, VIXY_B])
    if miss:
        return miss
    raw = {s: _local("60m", s) for s in T659_SPEC}
    if raw["ES_F"] is None or raw["NQ_F"] is None:
        absent = [s for s in ("ES_F", "NQ_F") if raw[s] is None]
        return _out({"missing_local": absent}, 0, "inconclusive",
                    f"local 60m bars {absent} are not on disk (mandel/ml_data/bars/60m): the claim cannot be tested (rule 9)")
    bars = {s: et_bars(df) for s, df in raw.items() if df is not None}
    last = max(d for d, _ in bars["ES_F"])
    end = min(T659_END, last)
    ny0 = date.fromisoformat(T659_START).year
    ec, rolls = early_closes(ny0, date.fromisoformat(end).year), roll_windows(ny0, date.fromisoformat(end).year)
    es = t659_nights(bars["ES_F"], "ES_F", end=end, ec=ec, rolls=rolls)
    elig = [r for r in es if r["eligible"] and not r["async"]]
    cond = [r for r in elig if r["down"]]
    comp = [r for r in elig if not r["down"]]
    x = np.array([r["net"] for r in cond])
    B = boot_mean(x, T659_BLOCK)
    lb_ok, lb_dec = _lb_ok(B)
    # NQ: two registered readings of the replication (its own closing hour; ES's closing hour), which must agree
    nq_reads = {}
    for tag, cbars in (("own", None), ("es", bars["ES_F"])):
        rows = [r for r in t659_nights(bars["NQ_F"], "NQ_F", end=end, cond_bars=cbars, ec=ec, rolls=rolls)
                if r["eligible"] and not r["async"] and r["down"]]
        nq_reads[tag] = boot_mean(np.array([r["net"] for r in rows]), T659_BLOCK)
    nq_ok = CAL._agree([None if v["mean"] is None else bool(v["mean"] > 0) for v in nq_reads.values()])
    nq_dec = all(v["mean"] is not None and v["mean"] < 0 and CAL.decide_p(v["pl"], v["draws"]) is True
                 for v in nq_reads.values())
    halves = [float(np.mean(v)) if len(v) else None for v in
              ([r["net"] for r in cond if r["day"] < T659_SPLIT], [r["net"] for r in cond if r["day"] >= T659_SPLIT])]
    half_ok = None if any(h is None for h in halves) else all(h > 0 for h in halves)
    xa = np.array([r["net"] for r in elig])
    flag = np.array([r["down"] for r in elig])
    G = CAL.group_test(xa, flag, T659_BLOCK, N_BOOT, SEED, N_SEEDS, max_seeds=CAL.MAX_SEEDS) if flag.any() and (~flag).any() else None
    comp_ok = None if G is None or G["diff"] is None else bool(G["diff"] > 0)
    comp_dec = bool(G is not None and G["diff"] is not None and G["diff"] < 0 and CAL.decide_p(G["p_less"], G["draws"]) is True)
    rows = [(f"ES conditional mean net {_bp(B['mean'])} with one-sided 95% lower bound > 0 (studentized CBB block "
             f"{T659_BLOCK}: p {_mc(B['pg'], B['draws'])}; HAC t {_f(B['t'], 2)} at lag {B.get('lag')})", lb_ok, lb_dec),
            ("NQ conditional mean net > 0 (same sign; readings own closing hour / ES closing hour: "
             + " / ".join(f"{_bp(v['mean'])} (n {v['n']})" for v in nq_reads.values()) + ")", nq_ok, nq_dec),
            (f"ES mean net > 0 in both halves (split {T659_SPLIT}: {' / '.join(_bp(h) for h in halves)})", half_ok, False),
            (f"conditional mean above the complement-night mean ({_bp(B['mean'])} vs "
             f"{_bp(float(np.mean([r['net'] for r in comp])) if comp else None)}; difference {_bp(G['diff'] if G else None)}, "
             f"p_less {_mc(G['p_less'] if G else None, G['draws'] if G else 0)})", comp_ok, comp_dec)]
    v, why, crit = CAL._judge(rows, len(cond), T659_MIN_N, "conditional ES nights")
    # ---- reported
    unc = float(np.mean(xa)) if xa.size else None
    rank_tab = {}
    for h in T659_HOURS:
        vals = [r["hours"][h] for r in cond if h in r["hours"]]
        if len(vals) >= T659_RANK_MIN:
            rank_tab[h] = float(np.mean(vals))
    order = sorted(rank_tab, key=lambda h: -rank_tab[h])
    rank = order.index(T659_TRADE_HOUR) + 1 if T659_TRADE_HOUR in rank_tab else None
    adj = {h: rank_tab.get(h) for h in (1, 3)}
    asyn = [r for r in es if r["eligible"] and r["async"] and r["down"]]
    asyn_rep = {}
    for h in (2, 3, 4):
        vals = [r["hours"][h] for r in asyn if h in r["hours"]]
        asyn_rep[h] = {"n": len(vals), "mean": float(np.mean(vals)) if vals else None}
    mk = [maker_net(r) for r in cond]
    filled = [m for m in mk if m is not None]
    spy_c, spy_all = spy_overnight(archive, cond), spy_overnight(archive, elig)
    vixd = _vix_split(archive, cond)
    rty = None
    if "RTY_F" in bars:
        rr = [r["net"] for r in t659_nights(bars["RTY_F"], "RTY_F", end=end, ec=ec, rolls=rolls)
              if r["eligible"] and not r["async"] and r["down"]]
        rty = {"n": len(rr), "mean": float(np.mean(rr)) if rr else None}
    excl = {k: int(sum(1 for r in es if r[k])) for k in ("early", "roll", "stale", "async")}
    excl["not_session"] = int(sum(1 for r in es if not r["session"]))
    reason = (f"ES_F 60m {es[0]['day'] if es else 'n/a'}..{end}: {len(es)} candidate Mon-Thu nights, {len(elig)} eligible "
              f"(excluded: {excl}; early-close days carry no on-the-hour overnight bars in the Yahoo series, so they never form a candidate night); {len(cond)} nights after a down 15:00 ET bar: 02:00-03:00 ET mean net "
              f"{_bp(B['mean'])} after (0.25 + 0.20) points / level (gross {_bp(float(np.mean([r['gross'] for r in cond])) if cond else None)}); "
              f"complement {len(comp)} nights {_bp(float(np.mean([r['net'] for r in comp])) if comp else None)}; unconditional "
              f"{_bp(unc)}; hour rank of 02:00 among {len(rank_tab)} conditional hourly means: {rank}; placebo hours 01:00 "
              f"{_bp(adj[1])}, 03:00 {_bp(adj[3])}; async weeks (reported) 02:00 {_bp(asyn_rep[2]['mean'])} "
              f"(n {asyn_rep[2]['n']}), 03:00 {_bp(asyn_rep[3]['mean'])}, 04:00 {_bp(asyn_rep[4]['mean'])}; maker variant "
              f"fill rate {len(filled)}/{len(cond)}, mean per fill {_bp(float(np.mean(filled)) if filled else None)}; SPY "
              f"overnight-only baseline (T-549) {_bp(spy_c['mean'])} on the conditional nights, {_bp(spy_all['mean'])} on all; "
              f"RTY replication {_bp(rty['mean'] if rty else None)} (n {rty['n'] if rty else 0}); VIX diagnostic (prior-"
              f"session VIX vs trailing median) high {_bp(vixd['high']['mean'])} / low {_bp(vixd['low']['mean'])}; the "
              f"Dukascopy 2012-2026 extension the controls require before any forward test is not archived (pilot sample, "
              f"as the verifier's power check says)")
    stat = {"n_candidates": len(es), "n_eligible": len(elig), "n_conditional": len(cond), "n_complement": len(comp),
            "excluded": excl, "es": {k: B[k] for k in ("mean", "pg", "pl", "draws", "t", "se")},
            "nq": {k: {kk: vv[kk] for kk in ("n", "mean", "pg", "pl", "draws", "t")} for k, vv in nq_reads.items()},
            "halves": halves, "complement_mean": float(np.mean([r["net"] for r in comp])) if comp else None,
            "group": None if G is None else {k: G[k] for k in ("diff", "ci", "p_greater", "p_less", "draws")},
            "unconditional_mean": unc, "hour_means": {str(h): m for h, m in rank_tab.items()}, "hour_rank_0200": rank,
            "async": {str(h): v2 for h, v2 in asyn_rep.items()}, "maker": {"filled": len(filled), "n": len(cond),
            "mean_per_fill": float(np.mean(filled)) if filled else None}, "spy_baseline": {"conditional": spy_c, "all": spy_all},
            "rty": rty, "vix_diag": vixd, "criteria": crit}
    return _out(stat, len(cond), v, reason + " — " + why)


# =================================================================================================== T-669 VIX1D ==

def _vix1d(archive) -> dict:
    """{day: (open, close)} of the Cboe VIX1D history (rows available at capture; positive values only)."""
    def load():
        out = {}
        for r in CAL._rows(archive, VIX1D_B):
            v = r.get("value") or {}
            try:
                o, c = float(v.get("open")), float(v.get("close"))
            except (TypeError, ValueError):
                continue
            if v.get("day") and o > 0 and c > 0:
                out[v["day"]] = (o, c)
        return out
    return CAL._cached(archive, ("b13ia_vix1d",), load)


def _spy_hourly(archive) -> dict:
    """{ET day: {"HH:MM": (open, close)}} of the archived 60m SPY bars (stamped by bar start)."""
    def load():
        out = defaultdict(dict)
        for r in CAL._rows(archive, HSPY_B):
            v = r.get("value") or {}
            try:
                t, o, c = float(v["t"]), float(v["open"]), float(v["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (o > 0 and c > 0):
                continue
            dt = datetime.fromtimestamp(t, tz=UTC).astimezone(NY)
            out[dt.strftime("%Y-%m-%d")][dt.strftime("%H:%M")] = (o, c)
        return dict(out)
    return CAL._cached(archive, ("b13ia_hspy",), load)


def session_variance(hbars: dict, official_close: float) -> Optional[dict]:
    """The 7 log returns from the 09:30 bar's open through the bars' closes to the official close (the last spans the
    30-minute 15:30 bar); None unless the day has exactly the 7 regular bars."""
    if any(k not in hbars for k in T669_BAR_TIMES) or not (official_close > 0):
        return None
    pts = [hbars["09:30"][0]] + [hbars[k][1] for k in T669_BAR_TIMES[:-1]] + [official_close]
    r = np.diff(np.log(np.asarray(pts, float)))
    return {"r": r, "rv": float(np.sum(r ** 2)), "open": pts[0]}


def implied_session_var(vix1d_open: float) -> float:
    """(VIX1D open / 100)^2 x 390 / 525,600: the open's implied variance over one 390-minute session."""
    return (vix1d_open / 100.0) ** 2 * T669_IV_SCALE


def t669_days(archive, start: str = T669_START, end: str = T669_END) -> dict:
    """Per session in [start, end] with the 7 regular bars, a VIX1D open and an official close: log R, the
    close-to-close robustness ratio and the last-interval variance share."""
    sd, sc = CAL._daily(archive, SPY_B, "close")
    vx, hb = _vix1d(archive), _spy_hourly(archive)
    out = {}
    for i, d in enumerate(sd):
        if not (start <= d <= end) or d not in hb or d not in vx:
            continue
        sv = session_variance(hb[d], sc[i])
        if sv is None or not sv["rv"] > 0:
            continue
        row = {"logR": math.log(sv["rv"] / implied_session_var(vx[d][0])), "share_last": float(sv["r"][-1] ** 2 / sv["rv"]),
               "shares": (sv["r"] ** 2 / sv["rv"]).tolist(), "logR_cc": None}
        if i > 0 and sd[i - 1] in vx:
            rv_cc = math.log(sv["open"] / sc[i - 1]) ** 2 + sv["rv"]
            row["logR_cc"] = math.log(rv_cc / ((vx[sd[i - 1]][1] / 100.0) ** 2 / 365.0))
        out[d] = row
    return {"days": sd, "rows": out}


def match_sets(events: Sequence[str], sessions: Sequence[str], valid: set, excluded: set, k: int = T669_MATCH,
               window: int = T669_WINDOW) -> list:
    """Calendar-only matching: for each event (in date order) up to ``k`` valid sessions on the same weekday within
    +/-``window`` sessions, not excluded and not already matched to an earlier event, nearest first (ties: the earlier
    date). Returns [(event, [matched days])] for the events that are valid sessions."""
    pos = {d: i for i, d in enumerate(sessions)}
    used, out = set(), []
    for e in sorted(events):
        if e not in pos or e not in valid:
            continue
        i, wd = pos[e], date.fromisoformat(e).weekday()
        cand = []
        for j in range(max(0, i - window), min(len(sessions), i + window + 1)):
            s = sessions[j]
            if j == i or s in used or s in excluded or s not in valid or date.fromisoformat(s).weekday() != wd:
                continue
            cand.append((abs(j - i), s))
        pick = [s for _, s in sorted(cand)[:k]]
        used.update(pick)
        out.append((e, pick))
    return out


def set_arrays(sets: Sequence[tuple], vals: dict) -> tuple:
    """(x in date order, event flag, per-set (event value, matched values))."""
    days = sorted({e for e, _ in sets} | {m for _, ms in sets for m in ms})
    ev = {e for e, _ in sets}
    x = np.array([vals[d] for d in days], float)
    f = np.array([d in ev for d in days], bool)
    per = [(vals[e], np.array([vals[m] for m in ms], float)) for e, ms in sets if ms]
    return x, f, per


def stationary_t(d: np.ndarray, mean_block: float, n_boot: int, seed: int) -> tuple:
    """Studentized stationary bootstrap of the mean of ``d``: (mean, s.e., t-draws (mean* - mean) / se*)."""
    d = np.asarray(d, float)
    n = d.size
    m, se0 = float(d.mean()), float(d.std(ddof=1) / math.sqrt(n))
    rng = np.random.default_rng(seed)
    X = d[SX._stat_idx(rng, n, mean_block, n_boot)]
    sb = X.std(axis=1, ddof=1) / math.sqrt(n)
    ok = sb > 0
    return m, se0, (X.mean(axis=1)[ok] - m) / sb[ok]


def stationary_p(d, c: float, mean_block: float = T669_BLOCK, alpha: float = ALPHA) -> tuple:
    """(p_greater for H0 mean <= c, p_less for H0 mean >= c, draws): studentized stationary bootstrap, pooled over 5
    seeds and escalated one seed at a time while either p is undecided at ``alpha``."""
    d = np.asarray(d, float)
    if d.size < 8 or not d.std() > 0:
        return None, None, 0

    def batch(k):
        m, se0, t = stationary_t(d, mean_block, N_BOOT, SEED + k)
        t0 = (m - c) / se0
        return float((np.sum(t >= t0) + 1) / (t.size + 1)), float((np.sum(t <= t0) + 1) / (t.size + 1))
    ps = [batch(k) for k in range(N_SEEDS)]
    while True:
        pg, pl = float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))
        nd = N_BOOT * len(ps)
        if len(ps) >= CAL.MAX_SEEDS or (CAL.decide_p(pg, nd, alpha) is not None and CAL.decide_p(pl, nd, alpha) is not None):
            return pg, pl, nd
        ps.append(batch(len(ps)))


def set_perm_p(per: Sequence[tuple], shift: float, n_perm: int = T669_N_PERM, seed: int = SEED,
               alpha: float = ALPHA) -> tuple:
    """Permutation over the matched sets: within each set the event label moves uniformly to one of its days, the
    event value carrying -``shift`` (the shifted null D = shift). (observed D - shift, p_greater, p_less, draws)."""
    if not per:
        return None, None, None, 0
    vals = [np.concatenate([[e - shift], m]) for e, m in per]
    E, M = len(vals), sum(v.size - 1 for v in vals)
    tot = float(sum(v.sum() for v in vals))
    obs = float(sum(v[0] for v in vals)) / E - (tot - float(sum(v[0] for v in vals))) / M
    width = max(v.size for v in vals)
    V = np.full((E, width), np.nan)
    for i, v in enumerate(vals):
        V[i, :v.size] = v
    sizes = np.array([v.size for v in vals])

    def batch(k):
        rng = np.random.default_rng(seed + k)
        J = (rng.random((n_perm, E)) * sizes[None, :]).astype(int)
        S = V[np.arange(E)[None, :], J].sum(axis=1)
        st = S / E - (tot - S) / M
        return float((np.sum(st >= obs - 1e-15) + 1) / (n_perm + 1)), float((np.sum(st <= obs + 1e-15) + 1) / (n_perm + 1))
    ps = [batch(0)]
    while True:
        pg, pl = float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))
        nd = n_perm * len(ps)
        if len(ps) >= CAL.MAX_PERM_BATCHES or (CAL.decide_p(pg, nd, alpha) is not None and CAL.decide_p(pl, nd, alpha) is not None):
            return obs, pg, pl, nd
        ps.append(batch(len(ps)))


def event_contrast(sets: Sequence[tuple], vals: dict) -> dict:
    """D = mean over events - pooled mean over matched days, with the flagged series whose mean is D (events without a
    matched day drop out)."""
    sets = [(e, ms) for e, ms in sets if ms]
    x, f, per = set_arrays(sets, vals)
    if f.sum() < 2 or (~f).sum() < 2:
        return {"D": None, "n_event": int(f.sum()), "n_matched": int((~f).sum())}
    return {"D": float(x[f].mean() - x[~f].mean()), "n_event": int(f.sum()), "n_matched": int((~f).sum()),
            "d": CAL.flag_diff_series(x, f), "per": per, "x": x, "f": f}


def b13_intraday_a_vix1d_fomc_ratio(archive):
    """T-669."""
    miss = _missing(archive, [VIX1D_B, HSPY_B, SPY_B, FOMC_B, CPI_B, NFP_B])
    if miss:
        return miss
    T = t669_days(archive)
    rows, sessions = T["rows"], [d for d in T["days"] if T669_START <= d <= T669_END]
    if not rows:
        return _out({"n_days": 0}, 0, "inconclusive", "no session has the 7 regular SPY bars, a VIX1D open and a close (rule 9)")
    first, last = min(rows), max(rows)
    y0, y1 = int(first[:4]), int(last[:4])
    fomc = [d for d in _fomc_days(archive) if first <= d <= last]
    cpi = [d for d in _release_days(archive, CPI_B, "cpi") if first <= d <= last]
    nfp = [d for d in _release_days(archive, NFP_B, "employment") if first <= d <= last]
    opex, ec = opex_days(y0, y1), early_closes(y0, y1)
    excluded = set(fomc) | set(cpi) | set(nfp) | opex | ec
    valid = set(rows)
    vals = {d: r["logR"] for d, r in rows.items()}
    S_f = match_sets(fomc, sessions, valid, excluded)
    plc = sorted((set(cpi) | set(nfp)) - set(fomc))
    S_p = match_sets(plc, sessions, valid, excluded)
    C_f, C_p = event_contrast(S_f, vals), event_contrast(S_p, vals)
    n = C_f["n_event"]
    D = C_f["D"]
    if D is None:
        return _out({"n_fomc": n}, n, "inconclusive", f"only {n} FOMC days with matched days: nothing to compare (rule 9)")
    pg_b, pl_b, nd_b = stationary_p(C_f["d"], T669_BAR)
    obs_p, pg_p, pl_p, nd_p = set_perm_p(C_f["per"], T669_BAR)
    sig_b, sig_p = _sig(D, pg_b, nd_b, bar=T669_BAR), _sig(D, pg_p, nd_p, bar=T669_BAR)
    dec1 = bool(D < T669_BAR and CAL.decide_p(pl_b, nd_b) is True and CAL.decide_p(pl_p, nd_p) is True)
    pg0, pl0, nd0 = stationary_p(C_f["d"], 0.0, alpha=0.025)
    m_, se0, tdraw = stationary_t(C_f["d"], T669_BLOCK, N_BOOT * N_SEEDS, SEED)
    lb = m_ - float(np.quantile(tdraw, 0.975)) * se0
    ub = m_ - float(np.quantile(tdraw, 0.025)) * se0
    lb_ok = _sig(D, pg0, nd0, alpha=0.025)
    lb_dec = bool(D < 0 and CAL.decide_p(pl0, nd0, 0.025) is True)
    # placebo: not significantly different from 0, two-sided, under both nulls
    pl_rep = {"D": C_p["D"], "n": C_p["n_event"]}
    if C_p["D"] is not None:
        a, b_, ndp_b = stationary_p(C_p["d"], 0.0, alpha=0.025)
        _, c, d_, ndp_p = set_perm_p(C_p["per"], 0.0, alpha=0.025)
        two_b = CAL._two_sided(a, b_)
        two_p = CAL._two_sided(c, d_)
        db, dp = CAL.decide_p(two_b, ndp_b), CAL.decide_p(two_p, ndp_p)
        plc_ok = CAL._agree([None if db is None else not db, None if dp is None else not dp])
        plc_dec = bool(db is True and dp is True)
        pl_rep.update(p_two_boot=two_b, p_two_perm=two_p, draws_boot=ndp_b, draws_perm=ndp_p)
    else:
        plc_ok, plc_dec = None, False
    crit_rows = [(f"FOMC minus matched mean log R {_f(D)} > {T669_BAR} with one-sided p < 0.05 under the day-level stationary "
                  f"bootstrap (mean block {T669_BLOCK:g}: p {_mc(pg_b, nd_b)}) and the matched-set permutation (p "
                  f"{_mc(pg_p, nd_p)})", CAL._agree([sig_b, sig_p]), dec1),
                 (f"lower 95% bound of the FOMC difference above 0 (bootstrap-t interval [{_f(lb)}, {_f(ub)}]; one-sided p "
                  f"vs 0 {_mc(pg0, nd0)} at 0.025)", lb_ok, lb_dec),
                 (f"CPI/NFP placebo difference {_f(C_p['D'])} (n {C_p['n_event']}) not significantly different from 0 "
                  f"(two-sided p bootstrap {_pf(pl_rep.get('p_two_boot'))}, permutation {_pf(pl_rep.get('p_two_perm'))})",
                  plc_ok, plc_dec)]
    v, why, crit = CAL._judge(crit_rows, n, T669_MIN_N, "FOMC days")
    # ---- reported: close-to-close robustness, OPEX, random dates, diagnostic (b)
    vcc = {d: r["logR_cc"] for d, r in rows.items() if r["logR_cc"] is not None}
    S_cc = match_sets(fomc, sessions, set(vcc), excluded)
    D_cc = event_contrast(S_cc, vcc)["D"]
    opx = sorted((opex & valid) - set(fomc) - set(cpi) - set(nfp))
    S_o = match_sets(opx, sessions, valid, excluded)
    D_opex = event_contrast(S_o, vals)["D"]
    rng = np.random.default_rng(SEED)
    pool = defaultdict(list)
    for d in sorted(valid - excluded):
        pool[date.fromisoformat(d).weekday()].append(d)
    rnd = []
    for _ in range(T669_RANDOM):
        pseudo = set()
        for e, _ in S_f:
            cands = [d for d in pool[date.fromisoformat(e).weekday()] if d not in pseudo]
            if cands:
                pseudo.add(cands[int(rng.integers(0, len(cands)))])
        Sr = match_sets(sorted(pseudo), sessions, valid, excluded | pseudo)
        Dr = event_contrast(Sr, vals)["D"]
        if Dr is not None:
            rnd.append(Dr)
    rnd = np.array(rnd)
    share_rnd = float(np.mean(rnd >= D)) if rnd.size else None
    sh_f = float(np.mean([rows[e]["share_last"] for e, _ in S_f]))
    sh_m = float(np.mean([rows[m]["share_last"] for _, ms in S_f for m in ms]))
    prof = {}
    for y in range(y0, y1 + 1):
        ds = [d for d in rows if d[:4] == str(y)]
        if len(ds) >= 60:
            prof[str(y)] = np.mean([rows[d]["shares"] for d in ds], axis=0)
    yrs = sorted(prof)
    corr = {f"{a}-{b}": float(np.corrcoef(prof[a], prof[b])[0, 1]) for i, a in enumerate(yrs) for b in yrs[i + 1:]}
    fe = [rows[e]["logR"] for e, _ in S_f]
    ma = [rows[m]["logR"] for _, ms in S_f for m in ms]
    reason = (f"SPY 60m (archived hourly-SPY, identical to the local file) {first}..{last}: {len(rows)} sessions with the 7 "
              f"regular bars, a VIX1D open and an official close; {n} scheduled FOMC days matched to {C_f['n_matched']} "
              f"non-event days (same weekday, +/-{T669_WINDOW} sessions, OPEX/FOMC/CPI/NFP/early closes excluded): mean log "
              f"R {_f(float(np.mean(fe)))} vs {_f(float(np.mean(ma)))}, difference {_f(D)}; placebo CPI/NFP {_f(C_p['D'])} "
              f"(n {C_p['n_event']}); reported: close-to-close robustness (prior-close VIX1D /365, overnight + intraday RV) "
              f"{_f(D_cc)}, OPEX-day difference {_f(D_opex)} (n {len(S_o)}), random-date placebo share >= observed "
              f"{_pf(share_rnd)} over {rnd.size} draws (mean {_f(float(rnd.mean()) if rnd.size else None)}), last-interval RV "
              f"share FOMC {sh_f:.3f} vs matched {sh_m:.3f}, year-profile correlations {', '.join(f'{k} {v2:.2f}' for k, v2 in corr.items())}. "
              f"Partly in-sample (T-529 reported event VIX1D pricing over 2022-05..2026-10): any pass must be confirmed on the "
              f"next 8 FOMC days before it informs T-217/T-218; no trade is claimed")
    stat = {"n_sessions": len(rows), "n_fomc": n, "n_matched": C_f["n_matched"], "D": D, "boot": [pg_b, pl_b, nd_b],
            "perm": [obs_p, pg_p, pl_p, nd_p], "lower_bound_p": [pg0, pl0, nd0], "ci_boot_t": [lb, ub], "placebo": pl_rep,
            "D_cc": D_cc, "D_opex": D_opex, "random_share_ge": share_rnd, "random_n": int(rnd.size),
            "share_last": {"fomc": sh_f, "matched": sh_m}, "profile_corr": corr,
            "fomc_sets": [[e, ms] for e, ms in S_f], "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ========================================================================================= T-660 overnight XS ==

def overnight_returns(O: np.ndarray, C: np.ndarray, Dv: np.ndarray) -> np.ndarray:
    """r_night[i] = (open[i] + dividend[i]) / close[i-1] - 1 (NaN where either price is missing; row 0 NaN)."""
    R = np.full(O.shape, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        R[1:] = (O[1:] + Dv[1:]) / C[:-1] - 1.0
    R[~np.isfinite(R)] = np.nan
    return R


def overnight_signal(R: np.ndarray, f: int, L: int) -> np.ndarray:
    """Sum of the L overnight returns ending at session f's open (rows f-L+1..f); NaN unless all L are present. Uses
    nothing after session f's open."""
    if f - L + 1 < 1:
        return np.full(R.shape[1], np.nan)
    W = R[f - L + 1:f + 1]
    s = W.sum(axis=0)
    s[~np.isfinite(W).all(axis=0)] = np.nan
    return s


def _events(archive, sym: str) -> tuple:
    """(splits [(ex, ratio)], dividends {ex_date: amount}) from daily-events-<sym> (split-adjusted amounts, as the
    split-adjusted closes); (None, None) when the bundle is absent."""
    name = SX.de(sym)
    if not B7C._has(archive, name):
        return None, None
    sp, dv = [], defaultdict(float)
    for r in SX._stream(archive, name):
        v = r.get("value") or {}
        k = r.get("kind") or v.get("type")
        try:
            if k == "split":
                num, den = float(v.get("numerator")), float(v.get("denominator"))
                if num > 0 and den > 0:
                    sp.append((str(v.get("ex_date") or SX._bar_day(v["t"]))[:10], num / den))
            elif k == "dividend":
                a = float(v.get("amount"))
                if a > 0:
                    dv[str(v.get("ex_date") or SX._bar_day(v["t"]))[:10]] += a
        except (TypeError, ValueError, KeyError):
            continue
    return sorted(sp), dict(dv)


def div_matrix(archive, days: Sequence[str], syms: Sequence[str], close: np.ndarray, adj: np.ndarray) -> tuple:
    """Session x symbol cash dividends on ex-dates (daily-events; the adjclose/close factor where a symbol has no
    events bundle), the splits per symbol and the count of symbols on the adjclose fallback."""
    pos = {d: i for i, d in enumerate(days)}
    Dv = np.zeros(close.shape)
    splits, fb = {}, 0
    for j, s in enumerate(syms):
        sp, dv = _events(archive, s)
        if dv is None:
            fb += 1
            ok = np.isfinite(close[:, j]) & np.isfinite(adj[:, j])
            idx = np.flatnonzero(ok)
            if idx.size > 1:
                Dv[idx, j] = OHLC.ex_dividends(close[idx, j], adj[idx, j])
            splits[s] = []
            continue
        splits[s] = sp
        for d, a in dv.items():
            i = pos.get(d)
            if i is not None:
                Dv[i, j] = a
    return Dv, splits, fb


def spell_mask(archive, base: dict) -> tuple:
    """Member-day mask of the spells whose price series is the member's (T-660's ticker-reuse check) and the reasons
    spells were refused. A spell (fja-sp500-ticker-spells join/leave) is kept when the Yahoo series' firstTradeDate is
    at most 10 days after the spell's start and, for an earlier spell of a ticker with several, a Wikipedia removal
    within 10 days of its end names the same company (``batch6c_stockxs.names_ok``); unverifiable earlier spells of
    reused tickers are refused (the conservative reading of 'reused tickers are refused'). Member days outside every
    recorded spell are refused."""
    days, syms = base["days"], base["syms"]
    D, N = len(days), len(syms)
    spells = defaultdict(dict)
    for r in CAL._rows(archive, SPELLS_B):
        v = r.get("value") or {}
        if not v.get("ticker"):
            continue
        y, k = SX.ysym(v["ticker"]), int(v.get("spell") or 1)
        if r.get("kind") == "sp500-join":
            spells[y].setdefault(k, {})["start"] = v.get("date")
        elif r.get("kind") == "sp500-leave":
            spells[y].setdefault(k, {})["end"] = v.get("date")
            spells[y][k].setdefault("start", v.get("start_date"))
    removed = defaultdict(list)
    if B7C._has(archive, SX.WIKI_CH_B):
        for r in CAL._rows(archive, SX.WIKI_CH_B):
            v = r.get("value") or {}
            if v.get("removed_ticker") and v.get("removed_security") and v.get("effective_date"):
                removed[SX.ysym(v["removed_ticker"])].append((v["effective_date"], v["removed_security"]))
    multi = [y for y in syms if len(spells.get(y, {})) > 1]
    sec_t = SX._sec_tickers(archive) if B7C._has(archive, SX.SEC_TICK_B) else {}
    comp = SX._company_rows(archive, {sec_t[y][0] for y in multi if y in sec_t}) if multi else {}
    ok = np.zeros((D, N), bool)
    darr = np.array(days)
    why = {"late_series": [], "unverified_earlier_spell": [], "no_spell": 0}
    for j, y in enumerate(syms):
        meta = SX._meta(archive, SX.dh(y)) or {}
        ft = meta.get("firstTradeDate")
        first = datetime.fromtimestamp(float(ft), tz=UTC).date() if ft is not None else None
        sp = spells.get(y, {})
        lastk = max(sp) if sp else None
        names = [meta.get("longName") or ""]
        if y in sec_t:
            cv = comp.get(sec_t[y][0]) or {}
            names += [sec_t[y][1], cv.get("name") or ""] + [(fn or {}).get("name") or "" for fn in (cv.get("formerNames") or [])]
        for k, s in sp.items():
            st, en = s.get("start"), s.get("end")
            if not st:
                continue
            good = first is None or first <= date.fromisoformat(st) + timedelta(days=T660_SPELL_TOL)
            if not good:
                why["late_series"].append(f"{y}#{k}")
            if good and k != lastk:
                hit = [nm for d, nm in removed.get(y, []) if en and abs((date.fromisoformat(d) - date.fromisoformat(en)).days) <= T660_SPELL_TOL]
                good = bool(hit) and any(SX.names_ok(nm, names) is True for nm in hit)
                if not good:
                    why["unverified_earlier_spell"].append(f"{y}#{k}")
            if good:
                m = (darr >= st) & ((darr < en) if en else True)
                ok[m, j] = True
    mem = base["member"]
    why["no_spell"] = int((mem & ~np.isin(np.arange(N), [j for j, y in enumerate(syms) if spells.get(y)])[None, :]).sum())
    return ok & mem, why


def t660_inputs(archive) -> dict:
    """The point-in-time S&P panel (``batch13_crossasset_a.xs_base``), spell-checked membership, overnight / intraday
    returns with dividends, SPY overnight-only, cover shares by CIK and the coverage counts. Cached per archive."""
    def load():
        from mandel.experiments import batch13_crossasset_a as XA
        base = XA.xs_base(archive)
        days, syms = base["days"], base["syms"]
        O, C, A = base["open"], base["close"], base["adjclose"]
        with np.errstate(invalid="ignore"):
            O = np.where(O > 0, O, np.nan)
        Dv, splits, fb = div_matrix(archive, days, syms, C, A)
        R = overnight_returns(O, C, Dv)
        with np.errstate(invalid="ignore", divide="ignore"):
            RI = C / O - 1.0
        VM, spell_why = spell_mask(archive, base)
        b = OHLC._bars(archive, "SPY")
        sp = {d: i for i, d in enumerate(b.days)}
        sdiv = OHLC.ex_dividends(b.close, b.adj)
        rs = np.full(len(days), np.nan)
        for i in range(1, len(days)):
            a_, c_ = sp.get(days[i - 1]), sp.get(days[i])
            if a_ is not None and c_ is not None and c_ == a_ + 1:
                rs[i] = b.open[c_] / b.close[a_] - 1.0 + sdiv[c_] / b.close[a_]
        ciks = {c for c in base["ciks"] if c is not None}
        shares = XA.share_series_by_cik(archive, ciks) if ciks else {}
        return {"base": base, "days": days, "syms": syms, "O": O, "C": C, "R": R, "RI": RI, "VM": VM, "rs": rs,
                "splits": splits, "shares": shares, "div_fallback": fb, "spell_why": spell_why}
    return CAL._cached(archive, ("b13ia_t660",), load)


def month_ends(days: Sequence[str]) -> list:
    """Indexes of the last session of each calendar month (the final month only when a later session exists)."""
    return [i for i in range(len(days) - 1) if days[i][:7] != days[i + 1][:7]]


def caps_at(inp: dict, f: int, cols: np.ndarray) -> np.ndarray:
    """Market cap at formation f: previous close x the latest cover shares accepted before 09:30 ET of session f (at
    most 15 months old) x the split factor after the shares' date, split equally across an issuer's member classes; NaN
    when unknown."""
    base, days = inp["base"], inp["days"]
    ts = SX._et_ts(days[f], 9, 30)
    out = np.full(cols.size, np.nan)
    ncls = defaultdict(int)
    for j in cols:
        c = base["ciks"][j]
        if c is not None:
            ncls[c] += 1
    for k, j in enumerate(cols):
        c = base["ciks"][j]
        ser = inp["shares"].get(c) if c is not None else None
        if not ser:
            continue
        kk = bisect.bisect_right(ser, ts, key=lambda s: s[0]) - 1
        if kk < 0:
            continue
        _, end, sh = ser[kk]
        if (date.fromisoformat(days[f]) - date.fromisoformat(end)).days > T660_SHARES_MAX_AGE:
            continue
        px = inp["C"][f - 1, j]
        if np.isfinite(px) and px > 0:
            out[k] = px * sh * SX.split_factor(inp["splits"].get(inp["syms"][j], []), end) / ncls[c]
    return out


def portfolio_weights(score: np.ndarray, elig: np.ndarray, q: int, high: bool, caps: Optional[np.ndarray]) -> np.ndarray:
    """Top (``high``) or bottom 1/q of the eligible scores (``tail_fractions``: ties share the boundary slots); equal
    weights, or value weights where a cap is known with names lacking one at the equal weight 1/k."""
    n = int((elig & np.isfinite(score)).sum())
    k = n // q
    frac = SX.tail_fractions(score, elig, k, high)
    if frac.sum() <= 0:
        return frac
    if caps is None:
        return frac / frac.sum()
    has = np.isfinite(caps) & (caps > 0) & (frac > 0)
    w = np.where(frac > 0, frac / frac.sum(), 0.0)
    cap_mass = w[has].sum()
    vw = np.where(has, frac * np.nan_to_num(caps), 0.0)
    if vw.sum() > 0:
        w = np.where(has, cap_mass * vw / vw.sum(), w)
    return w


def hold_month(inp: dict, w: np.ndarray, rows: Sequence[int], cost_side: float) -> dict:
    """Overnight-only holding over the sessions ``rows``: each night the portfolio (weights renormalised over names
    with a return that night) earns sum w r - 2 x cost_side; compounded. Also the gross intraday leg."""
    R, RI = inp["R"], inp["RI"]
    on, idr, miss, nn = 1.0, 1.0, 0.0, 0
    for g in rows:
        r = R[g]
        ok = np.isfinite(r) & (w > 0)
        nn += 1
        if not ok.any():
            miss += 1.0
            continue
        s = w[ok].sum()
        miss += 1.0 - s / w.sum()
        on *= 1.0 + float(w[ok] @ r[ok]) / s - 2 * cost_side
        ri = RI[g]
        oki = np.isfinite(ri) & (w > 0)
        if oki.any():
            idr *= 1.0 + float(w[oki] @ ri[oki]) / w[oki].sum()
    return {"on": on - 1.0, "intraday": idr - 1.0, "missing_weight_nights": miss / max(1, nn)}


def t660_cells(inp: dict, first_hold: str, last_hold: str, keep: Optional[np.ndarray] = None, cells=None) -> dict:
    """Monthly series per cell (lookback, VW/EW, q, side) for holding months in [first_hold, last_hold]: net
    overnight-only return, SPY overnight-only net, excess, gross intraday leg."""
    days = inp["days"]
    me = month_ends(days)
    cells = cells or [(L, wt, q) for L in T660_LOOKBACKS for wt in ("VW", "EW") for q in (10, 5)]
    out = {c: {"month": [], "net": [], "spy": [], "excess": [], "intraday": [], "bottom_excess": [], "n_names": [],
               "no_cap_share": [], "missing": []} for c in cells}
    by_month = defaultdict(list)
    for i, d in enumerate(days):
        by_month[d[:7]].append(i)
    for f in me:
        hm = CAL._next_month(days[f][:7])
        if not (first_hold <= hm <= last_hold) or hm not in by_month:
            continue
        rows = by_month[hm]
        if rows[0] != f + 1:
            continue
        spy = 1.0
        for g in rows:
            if np.isfinite(inp["rs"][g]):
                spy *= 1.0 + inp["rs"][g] - 2 * T660_COST_SPY
        spy -= 1.0
        elig0 = inp["VM"][f] & np.isfinite(inp["C"][f - 1]) & np.isfinite(inp["O"][f])
        if keep is not None:
            elig0 = elig0 & keep
        cols = np.flatnonzero(elig0)
        caps_full = np.full(elig0.size, np.nan)
        caps_full[cols] = caps_at(inp, f, cols)
        sig_cache = {}
        for c in cells:
            L, wt, q = c
            if L not in sig_cache:
                sig_cache[L] = overnight_signal(inp["R"], f, L)
            S = sig_cache[L]
            el = elig0 & np.isfinite(S)
            caps = caps_full if wt == "VW" else None
            w = portfolio_weights(S, el, q, True, caps)
            if w.sum() <= 0:
                continue
            hw = hold_month(inp, w, rows, T660_COST_STOCK)
            wb = portfolio_weights(S, el, q, False, caps)
            hb = hold_month(inp, wb, rows, T660_COST_STOCK) if wb.sum() > 0 else None
            o = out[c]
            o["month"].append(hm); o["net"].append(hw["on"]); o["spy"].append(spy); o["excess"].append(hw["on"] - spy)
            o["intraday"].append(hw["intraday"]); o["bottom_excess"].append(None if hb is None else hb["on"] - spy)
            o["n_names"].append(int((w > 0).sum()))
            o["no_cap_share"].append(float(((w > 0) & ~np.isfinite(caps_full)).sum() / max(1, (w > 0).sum())) if wt == "VW" else 0.0)
            o["missing"].append(hw["missing_weight_nights"])
    return out


def coverage(inp: dict, first: str, last: str) -> dict:
    """Member-months (each month-end session's fja member count, every member priced or not) priced by a spell-checked
    series with a close that session."""
    base, days = inp["base"], inp["days"]
    tot = pr = 0
    for f in month_ends(days):
        if first <= days[f][:7] <= last:
            tot += int(base["n_members"][f])
            pr += int((inp["VM"][f] & np.isfinite(inp["C"][f])).sum())
    return {"member_months": tot, "priced": pr, "share": pr / tot if tot else None}


def _sharpe(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1)) if x.size > 2 and x.std(ddof=1) > 0 else None


def b13_intraday_a_overnight_persistence(archive):
    """T-660."""
    miss = _missing(archive, [SPY_B, FJA_B, SPELLS_B, FACTS_PREFIX + "b000"])
    if miss:
        return miss
    from mandel.validation.backtest_eval import deflated_sharpe_ratio
    inp = t660_inputs(archive)
    cells = t660_cells(inp, T660_START_HOLD, T660_END_HOLD)
    prim = cells[T660_PRIMARY]
    x = np.array(prim["excess"], float)
    n = int(x.size)
    if n < 8:
        return _out({"n": n}, n, "inconclusive", f"only {n} holding months could be formed (rule 9)")
    nw = SX.nw_mean(x, T660_NW_LAG)
    srs = [s for s in (_sharpe(cells[c]["excess"]) for c in cells) if s is not None]
    var_obs = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    var_used = max(var_obs, 1.0 / max(1, n - 1))
    dsr = float(deflated_sharpe_ratio(x, n_trials=T660_CELLS, var_trials_sr=var_used))
    p_dsr = 1.0 - dsr
    p_bonf = min(1.0, T660_CELLS * nw["p"]) if nw["p"] is not None else None
    ok_dsr = None if p_dsr is None else bool(nw["est"] > 0 and p_dsr < ALPHA)
    ok_bonf = None if p_bonf is None else bool(nw["est"] > 0 and p_bonf < ALPHA)
    dec1 = bool(nw["est"] < 0 and nw["p_lt"] is not None and nw["p_lt"] < ALPHA)
    months = prim["month"]
    h1 = [e for m, e in zip(months, x) if m < T660_SPLIT]
    h2 = [e for m, e in zip(months, x) if m >= T660_SPLIT]
    halves = [float(np.mean(h)) if h else None for h in (h1, h2)]
    cov = coverage(inp, T660_START_HOLD, T660_END_HOLD)
    cov_ok = True if cov["share"] is not None and cov["share"] >= T660_COVER else None
    rows = [(f"VW top decile (21 overnight returns) mean monthly net excess over SPY overnight-only {_bp(nw['est'])} > 0 "
             f"with one-sided deflated p < 0.05 over {T660_CELLS} cells (NW({T660_NW_LAG}) t {_f(nw['t'], 2)}; DSR-deflated p "
             f"{_pf(p_dsr)}, Bonferroni-deflated p {_pf(p_bonf)}: both readings must agree)", CAL._agree([ok_dsr, ok_bonf]), dec1),
            (f"positive in 2014-2019 and in 2020-2026 ({' / '.join(_bp(h) for h in halves)})",
             None if any(h is None for h in halves) else all(h > 0 for h in halves), False),
            (f"coverage gate: >= 90% of member-months 2014-2026 priced ({cov['priced']} of {cov['member_months']}, "
             f"{(cov['share'] or 0) * 100:.1f}%; below the gate the verdict is capped at inconclusive)", cov_ok, False)]
    v, why, crit = CAL._judge(rows, n, T660_MIN_N, "holding months")
    # ---- reported
    cell_tab = {f"L{c[0]}/{c[1]}/{'decile' if c[2] == 10 else 'quintile'}": {
        "mean_excess": float(np.mean(cells[c]["excess"])) if cells[c]["excess"] else None,
        "t": SX.nw_mean(np.array(cells[c]["excess"]), T660_NW_LAG)["t"] if len(cells[c]["excess"]) > 3 else None,
        "n": len(cells[c]["excess"])} for c in cells}
    intr = float(np.mean(prim["intraday"])) if prim["intraday"] else None
    bot = [b for b in prim["bottom_excess"] if b is not None]
    rep = t660_cells(inp, T660_REPL[0], T660_REPL[1], cells=[T660_PRIMARY])[T660_PRIMARY]
    rep_nw = SX.nw_mean(np.array(rep["excess"]), T660_NW_LAG) if len(rep["excess"]) > 3 else {"est": None, "t": None}
    me = [f for f in month_ends(inp["days"]) if "2013-12" <= inp["days"][f][:7] <= "2026-08"]
    keep = np.all(inp["VM"][me], axis=0) if me else None
    thr = t660_cells(inp, T660_START_HOLD, T660_END_HOLD, keep=keep, cells=[T660_PRIMARY])[T660_PRIMARY] if keep is not None else None
    spot = open_spot_check(archive)
    gross = float(np.mean(np.array(prim["net"]) - np.array(prim["spy"]))) if prim["net"] else None
    nights = float(np.mean([len([d for d in inp["days"] if d[:7] == m]) for m in months[:12]])) if months else None
    sw = inp["spell_why"]
    reason = (f"point-in-time S&P 500 members (fja05680 + later Wikipedia changes) priced from the 901-symbol Yahoo "
              f"daily-history set, which is TODAY's universe: delisted members have no prices, so every number below is "
              f"survivor-biased beyond what the registration's coverage gate measures; holding months {months[0]}..{months[-1]} "
              f"({n}); primary cell mean monthly net excess {_bp(nw['est'])} (NW t {_f(nw['t'], 2)}), decile net "
              f"{_bp(float(np.mean(prim['net'])))} vs SPY overnight-only net {_bp(float(np.mean(prim['spy'])))} at 3 bp per "
              f"side per auction (two auctions a night, ~{nights or 0:.0f} nights a month) and 1 bp for SPY; mean names "
              f"{np.mean(prim['n_names']):.0f}, names without SEC cover shares (equal-weighted) {np.mean(prim['no_cap_share']) * 100:.1f}%; "
              f"cells {', '.join(f'{k} {_bp(c2['mean_excess'], 1)}' for k, c2 in cell_tab.items())}; the decile's gross intraday "
              f"leg {_bp(intr)} a month (expected negative); bottom-decile mirror excess {_bp(float(np.mean(bot)) if bot else None)}; "
              f"names present throughout {int(keep.sum()) if keep is not None else 0}: excess {_bp(float(np.mean(thr['excess'])) if thr and thr['excess'] else None)}; "
              f"2000-2013 unjudged replication {_bp(rep_nw['est'])} (t {_f(rep_nw['t'], 2)}, {len(rep['excess'])} months); "
              f"ticker-reuse refusals: {len(sw['late_series'])} spells with a later series, {len(sw['unverified_earlier_spell'])} "
              f"unverified earlier spells; dividends from adjclose for {inp['div_fallback']} symbols without events; open "
              f"spot-check on {spot['n_syms']} stocks: median |Yahoo daily open - first 60m open| {spot['median_bp']} bp (mean "
              f"{spot['mean_bp']} bp, {(spot['share_over_5bp'] or 0) * 100:.1f}% of days above 5 bp); weight on names "
              f"without a return on a holding night (series ending inside the month, renormalised away) "
              f"{max(0.0, float(np.mean(prim['missing']))) * 100:.2f}% per night. The coverage gate is a None criterion (a cap): it "
              f"never turns a failing criterion into inconclusive (house convention)")
    stat = {"n_months": n, "primary": {"mean": nw["est"], "t": nw["t"], "p": nw["p"], "dsr": dsr, "p_dsr": p_dsr,
            "p_bonferroni": p_bonf, "var_trials_sr_observed": var_obs, "var_trials_sr_used": var_used},
            "halves": halves, "coverage": cov, "cells": cell_tab, "intraday_leg": intr, "gross_excess": gross,
            "bottom_mirror": float(np.mean(bot)) if bot else None, "throughout": {"n_names": int(keep.sum()) if keep is not None else 0,
            "mean_excess": float(np.mean(thr["excess"])) if thr and thr["excess"] else None},
            "replication_2000_2013": {"mean": rep_nw["est"], "t": rep_nw["t"], "n": len(rep["excess"])},
            "spells": {"late_series": len(sw["late_series"]), "unverified_earlier": len(sw["unverified_earlier_spell"]),
            "member_days_without_spell": sw["no_spell"]}, "open_spot_check": spot,
            "missing_weight_nights_mean": float(np.mean(prim["missing"])), "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


def open_spot_check(archive) -> dict:
    """Median |Yahoo daily open - the 09:30 60m bar's open| / daily open, in bp, over the 28 local single stocks (the
    shared daily panel; members or not)."""
    from mandel.experiments.panel_cache import daily_panel
    P = daily_panel(archive)
    pos = {d: i for i, d in enumerate(P.days.astype(str).tolist())}
    have = set(P.symbols.tolist())
    diffs, n_syms, mean_abs = [], 0, []
    for s in T660_LOCAL_STOCKS:
        df = _local("60m", s)
        if df is None or s not in have:
            continue
        O = P.col(s, "open")
        ny = df.index.tz_convert("America/New_York")
        m = (ny.hour == 9) & (ny.minute == 30)
        n_syms += 1
        for d, o in zip(ny[m].strftime("%Y-%m-%d"), df["o"].to_numpy(float)[m]):
            i = pos.get(d)
            if i is not None and np.isfinite(O[i]) and O[i] > 0 and o > 0:
                diffs.append(abs(O[i] - o) / O[i] * 1e4)
    d = np.array(diffs)
    return {"n_syms": n_syms, "n": int(d.size), "median_bp": round(float(np.median(d)), 2) if d.size else None,
            "mean_bp": round(float(d.mean()), 2) if d.size else None, "share_over_5bp": float(np.mean(d > 5)) if d.size else None}


# ====================================================================================== T-664 auction deviation ==

def t664_universe() -> tuple:
    return T664_STOCKS + T664_SECTORS + T664_OTHER_ETFS


def bar_1530(df) -> dict:
    """{ET day: close of the 60m bar stamped 15:30 ET} (the last regular trade before 16:00)."""
    if df is None or len(df) == 0:
        return {}
    ny = df.index.tz_convert("America/New_York")
    m = (ny.hour == 15) & (ny.minute == 30)
    return dict(zip(ny[m].strftime("%Y-%m-%d"), df["c"].to_numpy(float)[m]))


def auction_dev(close_1530: float, official_close: float) -> float:
    """dev = log(official close / close of the 15:30 bar): known at the official close."""
    return math.log(official_close / close_1530)


def new_counts(no_daily=()) -> dict:
    return {"symbol_days": 0, "equal_dropped": 0, "no_bar": 0, "early": 0, "no_next": 0, "no_dividend_data": [],
            "no_60m": [], "no_daily_history": list(no_daily), "abs_dev_gt_2pct": 0}


def new_rows() -> dict:
    return {k: [] for k in ("sym", "day", "dev", "y", "dev_prev", "stock", "month_end", "quad", "russell")}


def symbol_rows(s: str, sd: Sequence[str], oo, cc, dd, b15: dict, start: str, ec: set, qw: set, rus: set,
                out: dict, cnt: dict) -> None:
    """Append one symbol's rows to ``out``: for each session d (index k) with a 15:30 bar, not an early close, whose
    next bar is the next NYSE session: dev from the 15:30 bar close and the official close of d (both known at d's
    close), y = log((open[k+1] + dividend[k+1]) / close[k]), the previous session's dev (NaN unless consecutive)."""
    prev_dev = None
    for k in range(len(sd) - 1):
        d = sd[k]
        if d < start:
            continue
        nxt = CAL.next_session(date.fromisoformat(d)).isoformat()
        cur_dev = None
        if d in ec:
            cnt["early"] += 1
        elif d not in b15:
            cnt["no_bar"] += 1
        elif sd[k + 1] != nxt:
            cnt["no_next"] += 1
        else:
            cnt["symbol_days"] += 1
            B = b15[d]
            if abs(cc[k] - B) <= T664_EQ_TOL * cc[k]:
                cnt["equal_dropped"] += 1
            else:
                cur_dev = auction_dev(B, cc[k])
                if abs(cur_dev) > 0.02:
                    cnt["abs_dev_gt_2pct"] += 1
                out["sym"].append(s); out["day"].append(d); out["dev"].append(cur_dev)
                out["y"].append(math.log((oo[k + 1] + dd[k + 1]) / cc[k]))
                out["dev_prev"].append(prev_dev if prev_dev is not None else np.nan)
                out["stock"].append(s in T664_STOCKS)
                out["month_end"].append(d[:7] != nxt[:7]); out["quad"].append(d in qw); out["russell"].append(d in rus)
        prev_dev = cur_dev if sd[k + 1] == nxt else None


def t664_rows(archive, start: str = T664_START) -> dict:
    """Symbol-day rows: dev_t, the next close-to-open log return (dividend added back), the previous session's dev,
    flags; with the drop counts."""
    from mandel.experiments.panel_cache import daily_panel
    P = daily_panel(archive)
    pdays = P.days.astype(str)
    syms = [s for s in t664_universe() if s in set(P.symbols.tolist())]
    no_daily = [s for s in t664_universe() if s not in syms]
    ec = early_closes(int(start[:4]), int(pdays[-1][:4]))
    qw = {third_friday(y, m).isoformat() for y in range(int(start[:4]), int(pdays[-1][:4]) + 1) for m in (3, 6, 9, 12)}
    rus = {(date(y, 6, 30) - timedelta(days=(date(y, 6, 30).weekday() - 4) % 7)).isoformat()
           for y in range(int(start[:4]), int(pdays[-1][:4]) + 1)}
    out = new_rows()
    cnt = new_counts(no_daily)
    for s in syms:
        df = _local("60m", s)
        if df is None:
            cnt["no_60m"].append(s)
            continue
        b15 = bar_1530(df)
        o, c, a = P.col(s, "open"), P.col(s, "close"), P.col(s, "adjclose")
        ok = np.isfinite(o) & np.isfinite(c) & (o > 0) & (c > 0)
        idx = np.flatnonzero(ok)
        sd = pdays[idx]
        oo, cc, aa = o[idx], c[idx], a[idx]
        _, dv = _events(archive, s)
        if dv is None:
            if not np.isfinite(aa).all():
                cnt["no_dividend_data"].append(s)
                continue
            dd = OHLC.ex_dividends(cc, aa)
        else:
            dd = np.array([dv.get(d, 0.0) for d in sd], float)
        symbol_rows(s, sd, oo, cc, dd, b15, start, ec, qw, rus, out, cnt)
    arr = {k: np.array(v) for k, v in out.items()}
    return {"rows": arr, "counts": cnt, "syms": syms}


def fe_slope(x, y, g) -> dict:
    """Pooled OLS slope with day fixed effects (within-day demeaning; days with one observation drop out) and its
    day-clustered s.e. (G / (G - 1) factor)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    _, inv = np.unique(np.asarray(g), return_inverse=True)
    cnt = np.bincount(inv)
    keep = cnt[inv] >= 2
    x, y, inv = x[keep], y[keep], inv[keep]
    _, inv = np.unique(inv, return_inverse=True)
    cnt = np.bincount(inv)
    xt = x - (np.bincount(inv, x) / cnt)[inv]
    yt = y - (np.bincount(inv, y) / cnt)[inv]
    Sxx = float(xt @ xt)
    if not Sxx > 0:
        return {"slope": None, "n": int(x.size), "G": int(cnt.size)}
    b = float(xt @ yt) / Sxx
    G = cnt.size
    sc = np.bincount(inv, xt * (yt - b * xt), minlength=G)
    se = math.sqrt(G / (G - 1) * float(sc @ sc)) / Sxx
    return {"slope": b, "se": se, "n": int(x.size), "G": int(G), "xt": xt, "yt": yt, "inv": inv, "Sxx": Sxx}


def wild_cluster_p(fe: dict, beta0: float, n_boot: int = T664_N_WILD, seed: int = SEED,
                   max_batches: int = T664_MAX_BATCHES) -> tuple:
    """Day-clustered wild bootstrap (Rademacher, null beta = beta0 imposed) of the FE slope's cluster-robust t:
    (p_less for H0 slope >= beta0, p_greater, draws), escalated in batches of ``n_boot`` while undecided."""
    if fe.get("slope") is None:
        return None, None, 0
    xt, yt, inv, Sxx = fe["xt"], fe["yt"], fe["inv"], fe["Sxx"]
    G = int(inv.max()) + 1
    t0 = (fe["slope"] - beta0) / fe["se"]
    ur = yt - beta0 * xt
    A = np.bincount(inv, xt * ur, minlength=G)
    Bg = np.bincount(inv, xt * xt, minlength=G)
    c = G / (G - 1)

    def batch(k):
        rng = np.random.default_rng(seed + k)
        ts = []
        done = 0
        while done < n_boot:
            m = min(2000, n_boot - done)
            W = rng.integers(0, 2, size=(m, G)) * 2.0 - 1.0
            d = (W @ A) / Sxx
            S = W * A[None, :] - d[:, None] * Bg[None, :]
            se = np.sqrt(c * (S ** 2).sum(axis=1)) / Sxx
            ts.append(d / se)
            done += m
        t = np.concatenate(ts)
        return float((np.sum(t <= t0) + 1) / (t.size + 1)), float((np.sum(t >= t0) + 1) / (t.size + 1))
    pl, pg, nd = CAL.escalate_p(batch, n_boot, 1, max_batches)
    return pl, pg, nd


def _wins(x, cap: float = T664_WINSOR) -> np.ndarray:
    return np.clip(np.asarray(x, float), -cap, cap)


def b13_intraday_a_auction_reversal(archive):
    """T-664."""
    miss = _missing(archive, [SPY_B, "daily-history-AAPL", "daily-events-AAPL"])
    if miss:
        return miss
    if _local("60m", "SPY") is None:
        return _out({"missing_local": ["60m"]}, 0, "inconclusive", "local 60m bars are not on disk: the claim cannot be tested (rule 9)")
    T = t664_rows(archive)
    Rw, cnt = T["rows"], T["counts"]
    n = int(Rw["y"].size)
    if n < 100:
        return _out({"n": n, "counts": cnt}, n, "inconclusive", f"only {n} symbol-days (rule 9)")
    days = Rw["day"]
    sess = np.array(sorted(set(days.tolist())))
    mid = sess[len(sess) // 2]
    reads = {}
    for tag, xv in (("raw", Rw["dev"]), ("winsorised", _wins(Rw["dev"]))):
        fe = fe_slope(xv, Rw["y"], days)
        pl, pg, nd = wild_cluster_p(fe, T664_BETA0)
        h = [fe_slope(xv[m], Rw["y"][m], days[m])["slope"] for m in (days < mid, days >= mid)]
        st = fe_slope(xv[Rw["stock"]], Rw["y"][Rw["stock"]], days[Rw["stock"]])["slope"]
        reads[tag] = {"slope": fe["slope"], "se": fe["se"], "G": fe["G"], "n": fe["n"], "p_less": pl, "p_greater": pg,
                      "draws": nd, "halves": h, "stocks": st}
    ok1 = CAL._agree([_sig(r["slope"], r["p_less"], r["draws"], side="less", bar=T664_BETA0) for r in reads.values()])
    dec1 = all(r["slope"] is not None and r["slope"] > T664_BETA0 and CAL.decide_p(r["p_greater"], r["draws"]) is True
               for r in reads.values())
    ok2 = CAL._agree([None if any(h is None for h in r["halves"]) else all(h < 0 for h in r["halves"]) for r in reads.values()])
    ok3 = CAL._agree([None if r["stocks"] is None else bool(r["stocks"] < 0) for r in reads.values()])
    R0, RW = reads["raw"], reads["winsorised"]
    rows = [(f"pooled day-FE slope < {T664_BETA0} with one-sided day-clustered wild-bootstrap p < 0.05 (raw dev: slope "
             f"{_f(R0['slope'])}, p {_mc(R0['p_less'], R0['draws'])}; |dev| winsorised at 20 bp: {_f(RW['slope'])}, p "
             f"{_mc(RW['p_less'], RW['draws'])}; both readings must agree)", ok1, dec1),
            (f"slope < 0 in both halves of the sessions (split {mid}: raw {' / '.join(_f(h) for h in R0['halves'])}; "
             f"winsorised {' / '.join(_f(h) for h in RW['halves'])})", ok2, False),
            (f"stocks-only slope < 0 (raw {_f(R0['stocks'])}, winsorised {_f(RW['stocks'])})", ok3, False)]
    v, why, crit = CAL._judge(rows, n, T664_MIN_N, "symbol-days")
    # ---- reported
    x, y = Rw["dev"], Rw["y"]
    X = np.column_stack([np.ones(n), x])
    nofe = float(np.linalg.lstsq(X, y, rcond=None)[0][1])
    per = {}
    for s in T["syms"]:
        m = Rw["sym"] == s
        if m.sum() > 30 and np.var(x[m]) > 0:
            per[s] = float(np.cov(x[m], y[m])[0, 1] / np.var(x[m], ddof=1))
    ps = np.array(list(per.values()))
    unseen = ~np.isin(Rw["sym"], T664_SEEN)
    rob = fe_slope(x[unseen], y[unseen], days[unseen])["slope"]
    mp = np.isfinite(Rw["dev_prev"])
    plc = fe_slope(Rw["dev_prev"][mp], y[mp], days[mp])["slope"]
    flags = {}
    for k in ("month_end", "quad", "russell"):
        f = Rw[k].astype(bool)
        flags[k] = {"n": int(f.sum()), "slope_flagged": fe_slope(x[f], y[f], days[f])["slope"] if f.sum() > 50 else None,
                    "slope_other": fe_slope(x[~f], y[~f], days[~f])["slope"]}
    xc = check_5m(T["syms"])
    absdev = np.abs(x)
    share_eq = cnt["equal_dropped"] / cnt["symbol_days"] if cnt["symbol_days"] else None
    reason = (f"{len(T['syms']) - len(cnt['no_dividend_data']) - len(cnt['no_60m'])} equity symbols (28 stocks, 11 sector "
              f"SPDRs, other equity ETFs; FXI/ARKK/SMH have no daily-history, so no official open/close or dividend: "
              f"left out; GLD is not an equity symbol) {sess[0]}..{sess[-1]} ({len(sess)} sessions): {cnt['symbol_days']} "
              f"symbol-days with a 15:30 bar, {cnt['equal_dropped']} ({(share_eq or 0) * 100:.1f}%) dropped because that "
              f"bar's close equals the official close, {n} used; median |dev| {np.median(absdev) * 1e4:.2f} bp; "
              f"day-FE slope raw {_f(R0['slope'])} (cluster s.e. {_f(R0['se'])}, {R0['G']} days), winsorised "
              f"{_f(RW['slope'])}; reported: no-FE slope {_f(nofe)}, per-symbol slopes median {_f(float(np.median(ps)) if ps.size else None)} "
              f"({int((ps < 0).sum())} of {ps.size} negative, {int((ps < -0.5).sum())} below -0.5), excluding "
              f"SPY/QQQ/IWM (seen through T-428) {_f(rob)}, placebo previous-day dev {_f(plc)}, month-end "
              f"{_f(flags['month_end']['slope_flagged'])} vs {_f(flags['month_end']['slope_other'])}, quad witching "
              f"{_f(flags['quad']['slope_flagged'])}, Russell reconstitution {_f(flags['russell']['slope_flagged'])} (n "
              f"{flags['russell']['n']}); 5m cross-check: the 15:30 60m close equals the 15:55 5m close on "
              f"{xc['equal']}/{xc['n']} symbol-days; |dev| > 2% on {cnt['abs_dev_gt_2pct']} symbol-days (kept). No costs: a "
              f"cost diagnostic for MOC-based rules")
    stat = {"n": n, "counts": cnt, "share_equal_dropped": share_eq, "reads": reads, "no_fe_slope": nofe,
            "per_symbol": per, "ex_seen_slope": rob, "placebo_prev_dev_slope": plc, "flags": flags, "check_5m": xc,
            "median_abs_dev_bp": float(np.median(absdev) * 1e4), "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


def check_5m(syms: Sequence[str]) -> dict:
    """Overlap days of the local 5m bars: the 15:30 60m bar's close against the 15:55 5m bar's close."""
    n = eq = 0
    for s in syms:
        d60, d5 = _local("60m", s), _local("5m", s)
        if d60 is None or d5 is None:
            continue
        b60 = bar_1530(d60)
        ny = d5.index.tz_convert("America/New_York")
        m = (ny.hour == 15) & (ny.minute == 55)
        for d, c in zip(ny[m].strftime("%Y-%m-%d"), d5["c"].to_numpy(float)[m]):
            if d in b60:
                n += 1
                eq += int(abs(b60[d] - c) <= T664_EQ_TOL * c)
    return {"n": n, "equal": eq}


HARNESSES = {"b13_intraday_a_es_0200_drift": b13_intraday_a_es_0200_drift,
             "b13_intraday_a_vix1d_fomc_ratio": b13_intraday_a_vix1d_fomc_ratio,
             "b13_intraday_a_overnight_persistence": b13_intraday_a_overnight_persistence,
             "b13_intraday_a_auction_reversal": b13_intraday_a_auction_reversal}
THEORY_MAP = {"T-659": "b13_intraday_a_es_0200_drift", "T-669": "b13_intraday_a_vix1d_fomc_ratio",
              "T-660": "b13_intraday_a_overnight_persistence", "T-664": "b13_intraday_a_auction_reversal"}
