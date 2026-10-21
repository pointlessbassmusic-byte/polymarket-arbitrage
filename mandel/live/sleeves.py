"""
Paper-trading sleeves (forward tests T-559 and T-560). Pure decision logic: no I/O, no broker.
==============================================================================================

T-559, the calendar sleeve, combines four rules that Mandel's archive supports, each on its own capital slot:

  overnight  QQQM held from the close to the next open, every session (T-549: +3.4-3.6 bps a night net of 1 bp a
             side on QQQ/IWM, 1999-2026).
  ibs        SPYM bought at the close when the day's internal bar strength is below 0.2 and sold at the next close
             (T-332 on SPY, T-558 replication). Live, IBS is read from a 15:45 ET snapshot because closing-auction
             orders must be in by 15:50; the backtest read the official close, so the journal records both.
  tom        SPYM held over the return days -4..+3 of each month, i.e. from the close of the session before day -4
             to the close of day +3 (T-59: +6.3 bps a day).
  monthend   inside the tom slot, skip the last two return days (-2, -1) when SPY beat TLT month to date by more
             than 2 pp at the close of the session before day -3 (T-345's previous-close reading, -47.8 bps, both
             halves); re-enter at the close of day -1 for +1..+3.

SPYM (State Street's SPDR Portfolio S&P 500, ticker SPLG until 2025-10-31) and QQQM stand in for SPY and QQQ (the same indexes; whole-share closing-auction orders on a ~$1k account).

T-560, the put-spread sleeve, sells one defined-risk XSP put spread a month: the standard monthly expiry 30-45
days out, short strike the highest listed strike at or below 95% of spot, long strike WIDTH points lower, only
when SPY closed above its 10-month moving average at the last month-end (T-551's drawdown filter), closed at 50%
of the credit or at 21 days to expiry. This form is NOT backtested in the archive (the closest records are the
ATM putwrite index T-128/T-202 and the inconclusive quoted-exit test T-550); the forward test is its first test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Optional

IBS_CUT = 0.2
SPX_ETF = "SPYM"                # the S&P 500 leg (State Street renamed SPLG to SPYM on 2025-10-31; Alpaca rejects SPLG)
MONTHEND_GAP = 0.02            # SPY minus TLT month-to-date return, previous-close reading
TOM_DAYS_END = 4               # return days -4..-1
TOM_DAYS_START = 3             # return days +1..+3
SLOTS = {"overnight": 0.40, "ibs": 0.30, "tom": 0.30}
SPREAD_OTM = 0.95
SPREAD_WIDTH = 3.0             # XSP points; max loss (width - credit) x 100
SPREAD_DTE = (30, 45)
SPREAD_TAKE_PROFIT = 0.5       # close when the spread can be bought back for <= 50% of the credit
SPREAD_EXIT_DTE = 21


# ----------------------------------------------------------------------------------------------- calendar --

def month_index(day: date, sessions: list[date]) -> tuple[int, int]:
    """(k_start, k_end) of a session in its month: k_start = 1 for the first session, k_end = -1 for the last."""
    same = [s for s in sessions if (s.year, s.month) == (day.year, day.month)]
    i = same.index(day)
    return i + 1, i - len(same)


def next_session(day: date, sessions: list[date]) -> date:
    later = [s for s in sessions if s > day]
    if not later:
        raise ValueError(f"no session after {day} in the calendar")
    return later[0]


def in_tom_window(day: date, sessions: list[date]) -> bool:
    """True when ``day``'s return (close of the previous session to the close of ``day``) is a turn-of-month day."""
    k_start, k_end = month_index(day, sessions)
    return k_end >= -TOM_DAYS_END or k_start <= TOM_DAYS_START


def monthend_skip(ret_day: date, sessions: list[date], spy_mtd: Optional[float], tlt_mtd: Optional[float]) -> bool:
    """T-345 overlay: skip return days -2 and -1 when SPY beat TLT month to date by > 2 pp. The month-to-date returns
    must be read at the close of the session before day -3 (the previous-close reading), which the caller supplies."""
    _, k_end = month_index(ret_day, sessions)
    if k_end not in (-2, -1) or spy_mtd is None or tlt_mtd is None:
        return False
    return spy_mtd - tlt_mtd > MONTHEND_GAP


def ibs(high: float, low: float, last: float) -> Optional[float]:
    if high is None or low is None or last is None or high <= low:
        return None
    return (last - low) / (high - low)


@dataclass
class CloseDecision:
    """What to hold from today's close: target dollars per symbol, and the reasons (journalled)."""
    day: date
    targets: dict[str, float]
    reasons: dict[str, str] = field(default_factory=dict)


def close_decision(day: date, sessions: list[date], capital: float, splg_bar: dict, spy_mtd: Optional[float],
                   tlt_mtd: Optional[float]) -> CloseDecision:
    """Targets for the holding from ``day``'s close. ``splg_bar`` is the 15:45 snapshot {high, low, last} of SPYM;
    ``spy_mtd`` / ``tlt_mtd`` are month-to-date returns at the PREVIOUS close (only used near month-end)."""
    nxt = next_session(day, sessions)
    reasons: dict[str, str] = {}
    targets = {"QQQM": capital * SLOTS["overnight"], SPX_ETF: 0.0}
    reasons["overnight"] = "hold QQQM close -> next open (every session)"
    x = ibs(splg_bar.get("high"), splg_bar.get("low"), splg_bar.get("last"))
    if x is not None and x < IBS_CUT:
        targets[SPX_ETF] += capital * SLOTS["ibs"]
        reasons["ibs"] = f"IBS {x:.3f} < {IBS_CUT} at the 15:45 snapshot: hold SPYM to the next close"
    else:
        reasons["ibs"] = f"IBS {x if x is None else round(x, 3)}: flat"
    if in_tom_window(nxt, sessions):
        if monthend_skip(nxt, sessions, spy_mtd, tlt_mtd):
            reasons["tom"] = (f"next session {nxt} is a turn-of-month day but SPY-TLT month to date "
                              f"{spy_mtd - tlt_mtd:+.4f} > {MONTHEND_GAP}: skip (T-345)")
        else:
            targets[SPX_ETF] += capital * SLOTS["tom"]
            reasons["tom"] = f"next session {nxt} is a turn-of-month return day: hold SPYM"
    else:
        reasons["tom"] = f"next session {nxt} outside the turn-of-month window: flat"
    return CloseDecision(day, targets, reasons)


def shares_for(target_usd: float, price: float) -> int:
    """Whole shares (closing/opening-auction orders take whole shares), rounded down."""
    if price <= 0:
        return 0
    return int(target_usd // price)


# --------------------------------------------------------------------------------------------- put spread --

def third_friday(y: int, m: int) -> date:
    d = date(y, m, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def monthly_expiry(today: date, expiries: Iterable[date]) -> Optional[date]:
    """The listed standard monthly expiry (third Friday, or the session before it) with DTE in SPREAD_DTE, nearest
    to the middle of the range."""
    lo, hi = SPREAD_DTE
    cands = []
    for e in expiries:
        tf = third_friday(e.year, e.month)
        if e in (tf, tf - timedelta(days=1)) and lo <= (e - today).days <= hi:
            cands.append(e)
    if not cands:
        return None
    mid = (lo + hi) / 2
    return min(cands, key=lambda e: abs((e - today).days - mid))


def trend_ok(month_end_closes: list[float]) -> Optional[bool]:
    """SPY above its 10-month simple moving average at the last month-end (closes oldest first, adjusted)."""
    if len(month_end_closes) < 10:
        return None
    last10 = month_end_closes[-10:]
    return month_end_closes[-1] > sum(last10) / 10


@dataclass
class SpreadPlan:
    expiry: date
    short_strike: float
    long_strike: float
    credit_mid: float
    max_loss: float          # dollars per spread
    reason: str


def plan_put_spread(today: date, spot: float, puts: dict[date, dict[float, tuple[float, float]]], risk_budget: float,
                    trend: Optional[bool]) -> tuple[Optional[SpreadPlan], str]:
    """``puts``: {expiry: {strike: (bid, ask)}}. Returns (plan or None, reason)."""
    if trend is not True:
        return None, f"trend filter {trend}: no new spread (SPY not above its 10-month SMA at the last month-end)"
    exp = monthly_expiry(today, puts)
    if exp is None:
        return None, f"no monthly expiry {SPREAD_DTE[0]}-{SPREAD_DTE[1]} days out"
    book = puts[exp]
    shorts = [k for k in book if k <= SPREAD_OTM * spot]
    if not shorts:
        return None, "no strike at or below 95% of spot"
    ks = max(shorts)
    kl = ks - SPREAD_WIDTH
    if kl not in book:
        return None, f"long strike {kl} not listed"
    (sb, sa), (lb, la) = book[ks], book[kl]
    if min(sb, sa, lb, la) < 0 or sb <= 0 or sa < sb or la < lb:
        return None, f"no two-sided quotes on {ks}/{kl}"
    credit = round((sb + sa) / 2 - (lb + la) / 2, 2)
    if credit <= 0:
        return None, f"non-positive mid credit {credit}"
    max_loss = round((SPREAD_WIDTH - credit) * 100, 2)
    if max_loss > risk_budget:
        return None, f"max loss ${max_loss} above the risk budget ${risk_budget}"
    return SpreadPlan(exp, ks, kl, credit, max_loss, f"{exp} {ks}/{kl} put spread, mid credit {credit}"), "open"


def spread_exit(today: date, expiry: date, credit: float, debit_to_close_mid: Optional[float]) -> Optional[str]:
    if (expiry - today).days <= SPREAD_EXIT_DTE:
        return f"{(expiry - today).days} days to expiry <= {SPREAD_EXIT_DTE}"
    if debit_to_close_mid is not None and debit_to_close_mid <= SPREAD_TAKE_PROFIT * credit:
        return f"buy-back mid {debit_to_close_mid} <= {SPREAD_TAKE_PROFIT:.0%} of the credit {credit}"
    return None


def occ_symbol(root: str, expiry: date, kind: str, strike: float) -> str:
    """OCC option symbol, e.g. XSP261120P00740000."""
    return f"{root}{expiry:%y%m%d}{kind.upper()[0]}{int(round(strike * 1000)):08d}"
