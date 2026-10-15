"""
Batch 6b, group ``drb``: eleven Deribit options-library claims (T-222, T-197, T-223, T-263, T-268, T-269, T-195, T-196,
T-260, T-257, T-262), each tested on its own claim, trial.pass and trial.min_n (house rules, MANDEL.md section 2).
=====================================================================================================================

What the archive holds and what each claim needs
  * T-197  quarterly basis vs the 3-month bill: TESTABLE NOW. ``deribit-quarterly-futures-btc`` (daily chart closes of every
           expired and live quarterly; the 1D bars open at 08:00 UTC and close 24 h later, checked against the index: the
           median |F/index - 1| over the last three days before expiry is 5 bp at bar open + 24 h and 80-150 bp at the other
           alignments) and the Deribit BTC index at the same tick (``deribit-funding-BTC-PERPETUAL`` hourly ``index_price``,
           from 2019-05-01).
  * T-223  8-hour Friday settlement straddle: TESTABLE NOW. The claim's procedure names BTC-PERPETUAL hourly candles "as a
           proxy for the settlement index"; the archive holds better: the Deribit BTC index itself at 00:00 UTC (funding
           history ``index_price``) and the actual 08:00 UTC settlement (``deribit-delivery-prices-btc``, the 30-minute
           TWAP every Deribit option settles on). Yahoo ``hourly-BTC-USD`` (2024-10 on) is the cross-check.
  * T-269  CME (Section 1256) vs IBIT covered call after tax: TESTABLE NOW (model-priced at DVOL, basis from the Deribit
           quarterlies, statutory rates).
  * T-222  catalyst strangle: the 21 stored catalyst windows of ``deribit-option-trades-catalysts`` (488,977 trades); only
           windows whose catalyst was verifiably known at the entry may be used (window ``available_at`` <= entry), which
           leaves 9 windows / 7 catalysts; of those, 3 are timed from a realised block height (only a few-day estimate at
           the entry), so the primary statistic uses the 6 windows / 4 catalysts timed from a date known ex ante, against
           min_n 20 catalysts.
  * DECLARED BUNDLES (not archived; harnesses run on synthetic data in the tests and return inconclusive here, naming the
    bundle and the request that fills it, see ``REQUESTS``): T-263 ``deribit-option-trades-fomc``, T-268
    ``deribit-dvol-futures-trades``, T-257 / T-262 ``deribit-option-trades-daily-BTC``, T-195 / T-196
    ``deribit-book-hourly-BTC`` (the two daily ``deribit-book-BTC-<date>`` captures are used as partial evidence), T-260
    ``deribit-box-monthly`` (fetcher ``mandel.data.options_misc.fetch_tardis_box_monthly``, blocked from this host) plus the
    daily book captures.

Conventions
  * Rows are used only when ``available_at`` is not after the bundle's capture time. Times are UTC; Deribit options and
    futures expire at 08:00 UTC; monthly expiries are the last Friday of the month, quarterlies the last Friday of
    Mar/Jun/Sep/Dec.
  * DVOL: daily bars open at 00:00 UTC and are known at the close (next 00:00), so a decision at day D 00:00 (or later on
    D) uses the close of the bar opened on D-1.
  * Rates (rule 7): the archive has FRED DTB3, not DGS3MO; DTB3 is the 3-month bill as a 91-day discount yield, converted to
    a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365). A decision on day d uses the print dated before d; a same-day
    comparison (T-197, T-196, T-260 are comparisons, not trades) uses the print dated on or before the day. Crypto years
    are 365 days.
  * Fees (rule 9, the schedule assumed for every year): Deribit option taker fee 0.03% of the underlying per contract
    (0.0003 coin) capped at 12.5% of the option price; dated futures taker 0.05% of notional; option delivery 0.015% with
    the same cap. Earlier years had other schedules; this one is applied throughout.
  * Inverse options: Deribit premiums are in coin; a USD value is coin price x index at the same print. Deribit marks are
    Black-76 on the expiry forward with r = 0, so C_btc - P_btc = 1 - K/F and F_impl = K / (1 - (C_btc - P_btc)).
  * Model pricing (rule 8): T-223 and T-269 are Black-Scholes at DVOL (MODEL-PRICED, IV-scale sensitivities reported);
    T-257 / T-262 price legs by Black-Scholes at IVs fitted to trade prints (MODEL-PRICED at trade-fitted IVs). T-222 uses
    Deribit's own mark at real prints (a re-mark by model only as a labelled fallback).
  * Intervals (rule 6): two-sided 95% unless a pass says otherwise; block lengths as each trial names, at least as long as
    any overlap; differences are resampled paired on their shared timeline.
  * Calendars (rule 10): T-223 and T-269 use Deribit's named calendars (Fridays; monthly = last Friday). T-257 and T-262
    have conditional entries with a hold (30 and 14 days) and no named calendar, so the pooled estimate over every signal
    day (overlapping holds, circular block bootstrap on the daily timeline with blocks of 2 x the longest actual hold) is
    primary; n is the count of non-overlapping holds (greedy from the first signal) and the per-start range over every
    start offset (as many as the longest hold) is reported. T-257 holds exactly 30 calendar days (re-marked on that day's
    fitted smile; an expiry inside the 30 days settles at delivery), the claim's 30-day P&L. T-222, T-263 and T-268 are event studies on named event calendars.
  * Below trial.min_n (rule 5) the verdict is never supported and a failing criterion counts only when it fails
    decisively (its bound at the pass's own confidence wholly on the wrong side, or the failure would persist at min_n).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
(None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.options import bs

N_BOOT = 2000
SEED = 0
MP = "MODEL-PRICED"
UTC = timezone.utc
DAY_MS = 86_400_000
HOUR_MS = 3_600_000

# ------------------------------------------------------------------------------------------------- bundles --
CAT_B = "deribit-option-trades-catalysts"
QF_B = "deribit-quarterly-futures-btc"
FUND_B = "deribit-funding-BTC-PERPETUAL"
DELIV_B = "deribit-delivery-prices-btc"
DVOL_B = {"BTC": "deribit-dvol-BTC-history", "ETH": "deribit-dvol-ETH-history"}
DTB3_B = "fred-DTB3"
FOMC_B = "fomc-meetings"
CPI_B = "macro-release-cpi"
HOURLY_B = {"BTC": "hourly-BTC-USD", "ETH": "hourly-ETH-USD"}
BTC_DAILY_B = "daily-history-BTC-USD"
BOOK_PREFIX = "deribit-book-BTC-"
BOOK_FIRST_DAY = "2026-10-14"
# declared, not yet archived
FOMC_TRADES_B = "deribit-option-trades-fomc"
DVOLF_B = "deribit-dvol-futures-trades"
DAILY_TRADES_B = "deribit-option-trades-daily-BTC"
HOURLY_BOOK_B = "deribit-book-hourly-BTC"
BOX_MONTHLY_B = "deribit-box-monthly"

HIST = "https://history.deribit.com/api/v2/public/"
LIVE = "https://www.deribit.com/api/v2/public/"
REQUESTS = {
    FOMC_TRADES_B: (
        f"GET {HIST}get_last_trades_by_currency_and_time?currency=BTC&kind=option&start_timestamp=<decision_ms - 86400000>"
        f"&end_timestamp=<decision_ms - 1>&count=1000&include_old=true&sorting=asc, paged forward, for every scheduled FOMC "
        f"decision 2022-01-26..2026-09 in fomc-meetings (decision_ms = 14:00 America/New_York on decision_day), keeping the "
        f"first expiry after the decision listed by then (listing = min creation_timestamp from {HIST}get_instruments?"
        f"currency=BTC&kind=option&expired=true and expired=false); rows: kind option-trade value = the raw trade + "
        f"{{decision_day, currency, expiry, expiry_code, strike, type}}, available_at = trade time, and kind fomc-window value "
        f"= {{decision_day, decision_time, currency, target_expiry, target_expiry_code, target_listed_at, window_start, "
        f"window_end, complete}} (mandel.data.options_misc.trades_in_window / catalyst_windows do this with before_days=1)"),
    DVOLF_B: (
        f"GET {HIST}get_instruments?currency=USDC&kind=future&expired=true (keep BTCDVOL_USDC-*), then per instrument GET "
        f"{HIST}get_last_trades_by_instrument_and_time?instrument_name=BTCDVOL_USDC-<DDMMMYY>&start_timestamp=<expiry_ms - "
        f"8*86400000>&end_timestamp=<expiry_ms>&count=1000&include_old=true&sorting=asc and the settlement GET "
        f"{LIVE}get_last_settlements_by_instrument?instrument_name=BTCDVOL_USDC-<DDMMMYY>&type=delivery; rows: kind "
        f"future-trade value = {{instrument_name, expiry (ISO UTC), timestamp, price, mark_price, index_price, amount, "
        f"direction}}, available_at = trade time; kind future-settlement value = {{instrument_name, expiry, delivery_price}}, "
        f"available_at = expiry"),
    DAILY_TRADES_B: (
        f"GET {HIST}get_last_trades_by_currency_and_time?currency=BTC&kind=option&start_timestamp=<day 07:00 UTC ms>"
        f"&end_timestamp=<day 09:00 UTC ms - 1>&count=1000&include_old=true&sorting=asc, paged forward, for every day "
        f"2021-12-01..2026-10-14 (about 1,780 days, on the order of 10^4 pages); rows: kind option-trade value = the raw "
        f"trade {{trade_id, timestamp, instrument_name, price, mark_price, iv, index_price, amount, direction}} + "
        f"{{currency, expiry, expiry_code, strike, type}}, available_at = trade time"),
    HOURLY_BOOK_B: (
        f"history.deribit.com serves trades, not order books, so no history request can fill it: poll "
        f"GET {LIVE}get_book_summary_by_currency?currency=BTC&kind=option and &kind=future every hour on the hour (T-195: 7 "
        f"days = 168 snapshots; T-196: 14 days = 336), or take the ticker channel of a free Tardis first-of-month day "
        f"(https://api.tardis.dev/v1/data-feeds/deribit?from=<YYYY-MM-01>, 24 hourly snapshots per day); rows: kind option "
        f"value = {{capture_ts, instrument, expiry, strike, type, bid, ask, mark, mark_iv, oi, volume, underlying, "
        f"underlying_index, index_price, interest_rate}}, kind future value = {{capture_ts, instrument, expiry, bid, ask, mark, "
        f"index_price}}, available_at = capture time"),
    BOX_MONTHLY_B: (
        "mandel.data.options_misc.fetch_tardis_box_monthly (Tardis keyless first-of-month ticker feed, minute 00:00-00:01 UTC, "
        "2019-04..2026-10, about 91 capture days; blocked from this shared host by the per-IP transfer budget, run it from a "
        "host with its own IP); the daily deribit-book-BTC-<date> captures accumulate from 2026-10-14"),
}

# --------------------------------------------------------------------------------------------------- fees --
OPT_TAKER = 0.0003            # 0.03% of the underlying per option contract
OPT_CAP = 0.125               # capped at 12.5% of the option price
FUT_TAKER = 0.0005            # dated futures taker, 0.05% of notional
OPT_DELIVERY = 0.00015        # option delivery fee, 0.015%, same cap
FEE_TXT = ("Deribit fee schedule assumed for every year: option taker 0.03% of the underlying (0.0003 coin per contract) "
           "capped at 12.5% of the option price; dated futures taker 0.05%")

# ----------------------------------------------------------------------------------------- trial constants --
T197_MIN_N, T197_THR, T197_BLOCK = 500, 0.01, 20
T223_MIN_N, T223_HOURS, T223_BLOCK = 60, 8, 4
T269_MIN_N = 5
T269_ORD, T269_LT = 0.37, 0.20
T269_1256 = 0.6 * T269_LT + 0.4 * T269_ORD          # 26.8% blended
T269_FIRST, T269_LAST = 2021, 2025
T269_BASIS_GRID = (0.0, 0.025, 0.05, 0.075, 0.10, 0.15)
T222_MIN_N, T222_TAU = 20, 12
REALISED_TIME = "realised (ex post)"
T263_MIN_N = 16
T268_MIN_N = 12
T195_MIN_N, T195_MNY, T195_DTE = 500, 0.10, (7.0, 180.0)
T196_MIN_N, T196_THR, T196_MNY = 200, 0.01, 0.20
T260_MIN_N, T260_THR, T260_FRAC = 60, 0.02, 0.70
T257_MIN_N, T257_THR, T257_HOLD = 40, 0.05, 30
T262_MIN_N, T262_THR, T262_HOLD = 30, 0.05, 14
CLAIM_START, CLAIM_END = "2022-01-01", "2026-12-31"   # "2022-2026"


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
    """Inconclusive result naming the missing bundles (and, for a declared bundle, the request that fills it)."""
    miss = [n for n in names if not _has(archive, n)]
    if not miss:
        return None
    v, why = _verdict([(f"data bundles {miss} archived", None)])
    fill = "; ".join(f"{n}: {REQUESTS[n]}" for n in miss if n in REQUESTS)
    return ({"missing_bundles": miss, "requests": {n: REQUESTS[n] for n in miss if n in REQUESTS}}, 0, v,
            f"missing data bundles {miss}: the claim cannot be tested until they are archived"
            + (f" (fill: {fill})" if fill else "") + f" — {why}")


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _dated(archive, prefix: str, first: str = BOOK_FIRST_DAY) -> list[str]:
    """Names of the dated bundles ``prefix<YYYY-MM-DD>`` (from the archive listing, else probed day by day)."""
    pat = re.compile("^" + re.escape(prefix) + r"\d{4}-\d{2}-\d{2}$")
    ents = getattr(archive, "entries", None)
    if callable(ents):
        try:
            return sorted({e.name for e in ents() if pat.match(getattr(e, "name", ""))})
        except Exception:                                  # noqa: BLE001 - fall back to probing
            pass
    out, d, end = [], date.fromisoformat(first), datetime.now(UTC).date()
    while d <= end:
        if _has(archive, prefix + d.isoformat()):
            out.append(prefix + d.isoformat())
        d += timedelta(days=1)
    return out


def _fred(archive, name: str = DTB3_B) -> dict:
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            try:
                x = float(v.get("value"))
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("fred", name), load)


def _dvol(archive, cur: str = "BTC") -> dict:
    """{bar-open UTC day: DVOL close}; the close is known at the next 00:00 UTC."""
    def load():
        out = {}
        for r in _rows(archive, DVOL_B[cur]):
            v = r["value"]
            try:
                out[_dday(int(v["ts_ms"]))] = float(v["close"])
            except (TypeError, ValueError, KeyError):
                continue
        return out
    return _cached(archive, ("dvol", cur), load)


def _index_hourly(archive) -> dict:
    """{ms: Deribit BTC index} from the funding history (hourly, from 2019-05-01)."""
    def load():
        out = {}
        for r in _rows(archive, FUND_B):
            v = r["value"]
            try:
                x = float(v["index_price"])
            except (TypeError, ValueError, KeyError):
                continue
            if x > 0:
                out[int(v["timestamp"])] = x
        return out
    return _cached(archive, ("index",), load)


def _delivery(archive) -> dict:
    def load():
        out = {}
        for r in _rows(archive, DELIV_B):
            v = r["value"]
            try:
                x = float(v["delivery_price"])
            except (TypeError, ValueError, KeyError):
                continue
            if x > 0:
                out[v["date"]] = x
        return out
    return _cached(archive, ("delivery",), load)


def _hourly_bars(archive, cur: str = "BTC") -> dict:
    """{bar start ms (on the hour): (open, close)} of a Yahoo 1h bundle."""
    def load():
        out = {}
        for r in _rows(archive, HOURLY_B[cur]):
            v = r["value"]
            try:
                t = int(float(v["t"])) * 1000
                o, c = float(v["open"]), float(v["close"])
            except (TypeError, ValueError, KeyError):
                continue
            if t % HOUR_MS == 0 and o > 0 and c > 0:
                out[t] = (o, c)
        return out
    return _cached(archive, ("hourly", cur), load)


def _fomc_days(archive) -> list[str]:
    def load():
        return sorted({r["value"]["decision_day"] for r in _rows(archive, FOMC_B)
                       if r["value"].get("decision_day") and not r["value"].get("future") and r["value"].get("scheduled", True)})
    return _cached(archive, ("fomc",), load)


# ======================================================================================================= utils ==

def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _out(rep: dict):
    return _clean(rep["stat"]), int(rep["n"]), rep["verdict"], rep["reason"]


def _f(x, nd=3, pct=False, sign=False) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    x = float(x) * (100 if pct else 1)
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s + ("%" if pct else "")


def _bp(x, nd=0, sign=True) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return (f"{x * 1e4:+.{nd}f}" if sign else f"{x * 1e4:.{nd}f}") + " bp"


def _ci(c, nd=3, pct=False) -> str:
    if c is None or c[0] is None:
        return "[n/a]"
    return f"[{_f(c[0], nd, pct, True)}, {_f(c[1], nd, pct, True)}]"


def _cib(c) -> str:
    if c is None or c[0] is None:
        return "[n/a]"
    return f"[{_bp(c[0])}, {_bp(c[1])}]"


def _ms(iso: str) -> int:
    s = iso.replace("Z", "+00:00")
    if len(s) == 10:
        s += "T00:00:00+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return int(round(d.timestamp() * 1000))


def _iso(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()


def _dday(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).date().isoformat()


def _add(day: str, k: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=k)).isoformat()


MONTHS3 = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_CODE = re.compile(r"^(\d{1,2})([A-Z]{3})(\d{2})$")


def code_date(code: str) -> Optional[str]:
    """'25DEC26' -> '2026-12-25'."""
    m = _CODE.match(code or "")
    if not m or m.group(2) not in MONTHS3:
        return None
    try:
        return date(2000 + int(m.group(3)), MONTHS3.index(m.group(2)) + 1, int(m.group(1))).isoformat()
    except ValueError:
        return None


def expiry_ms(day: str) -> int:
    return _ms(day[:10] + "T08:00:00+00:00")


def last_friday(y: int, m: int) -> date:
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def is_last_friday(day: str) -> bool:
    d = date.fromisoformat(day)
    return d.weekday() == 4 and d == last_friday(d.year, d.month)


def is_quarterly(day: str) -> bool:
    return is_last_friday(day) and int(day[5:7]) in (3, 6, 9, 12)


def dtb3_cont(d_pct: float) -> float:
    """Continuous rate from a 91-day bill discount yield in percent (FRED DTB3), house rule 7."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


class Bills:
    """FRED DTB3 as a continuous rate: ``rate(day)`` uses the print dated before ``day`` (a decision), ``same_day(day)``
    the print dated on or before it (a contemporaneous comparison)."""

    def __init__(self, dtb3: dict):
        self.k = sorted(dtb3)
        if not self.k:
            raise ValueError("no DTB3 prints")
        self.r = [dtb3_cont(float(dtb3[d])) for d in self.k]

    def rate(self, day: str) -> float:
        return float(self.r[max(bisect.bisect_left(self.k, day) - 1, 0)])

    def same_day(self, day: str) -> float:
        return float(self.r[max(bisect.bisect_right(self.k, day) - 1, 0)])


# -------------------------------------------------------------------------------------------- Black-Scholes --

def _N(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bs_price(S: float, K: float, T: float, sig: float, kind: str, r: float = 0.0) -> float:
    if T <= 0 or sig <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    v = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / v
    d2 = d1 - v
    if kind == "call":
        return S * _N(d1) - K * math.exp(-r * T) * _N(d2)
    return K * math.exp(-r * T) * _N(-d2) - S * _N(-d1)


def bs_delta(S: float, K: float, T: float, sig: float, kind: str, r: float = 0.0) -> float:
    if T <= 0 or sig <= 0:
        if kind == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return _N(d1) if kind == "call" else _N(d1) - 1.0


def option_fee(price: float) -> float:
    """Taker fee in coin per coin-notional contract (the assumed Deribit schedule)."""
    return min(OPT_TAKER, OPT_CAP * max(float(price), 0.0))


# ---------------------------------------------------------------------------------------------- bootstrap --

def _nb(n_boot: Optional[int]) -> int:
    return N_BOOT if n_boot is None else int(n_boot)


def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    """k circular block-bootstrap index rows of length n."""
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def mean_ci(x, block: int = 1, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> tuple:
    """Two-sided percentile circular block-bootstrap CI of the mean (iid when block = 1)."""
    n_boot = _nb(n_boot)
    x = np.asarray(x, float)
    if x.size < 2:
        return (None, None)
    rng = np.random.default_rng(seed)
    m = np.empty(n_boot)
    for s in range(0, n_boot, 500):
        k = min(500, n_boot - s)
        m[s:s + k] = x[_boot_idx(rng, x.size, block, k)].mean(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def timeline_mean_ci(days: Sequence[str], vals, block: int, n_boot: Optional[int] = None, seed: int = SEED,
                     level: float = 0.95) -> tuple:
    """Percentile CI of the mean of entries placed on their daily calendar (one value per day, NaN on days without
    one), circular block bootstrap of calendar days with ``block``-day blocks (rule 10 pooled estimator)."""
    n_boot = _nb(n_boot)
    vals = np.asarray(vals, float)
    if vals.size < 2:
        return (None, None)
    d0 = date.fromisoformat(min(days))
    idx = np.array([(date.fromisoformat(d) - d0).days for d in days])
    g = np.full(int(idx.max()) + 1, np.nan)
    g[idx] = vals
    ok = np.isfinite(g)
    gz = np.where(ok, g, 0.0)
    rng = np.random.default_rng(seed)
    out = []
    for s in range(0, n_boot, 250):
        k = min(250, n_boot - s)
        ii = _boot_idx(rng, g.size, block, k)
        cnt = ok[ii].sum(axis=1)
        sm = gz[ii].sum(axis=1)
        out.append(sm[cnt > 0] / cnt[cnt > 0])
    m = np.concatenate(out)
    if m.size < 10:
        return (None, None)
    a = (1 - level) / 2
    return float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def sign_test(k: int, n: int) -> tuple:
    """Exact binomial sign test: (one-sided P(X >= k), two-sided p) under p = 1/2."""
    if n <= 0:
        return 1.0, 1.0
    tail = lambda j: sum(math.comb(n, i) for i in range(j, n + 1)) / 2 ** n
    return float(tail(k)), float(min(1.0, 2 * tail(max(k, n - k))))


def _binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    for i in range(0, k + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, tot)


def clopper_pearson(k: int, n: int, level: float = 0.95) -> tuple:
    """Exact two-sided binomial interval (bisection on the binomial CDF)."""
    if n <= 0:
        return (0.0, 1.0)
    a = (1 - level) / 2

    def solve(f, lo=0.0, hi=1.0):
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if f(mid):
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)
    lo = 0.0 if k == 0 else solve(lambda p: 1 - _binom_cdf(k - 1, n, p) >= a)
    hi = 1.0 if k == n else solve(lambda p: _binom_cdf(k, n, p) <= a)
    return lo, hi


def _agree(oks: list) -> Optional[bool]:
    """True when every variant passes, False when none does, None (MARGINAL) when they disagree."""
    oks = [bool(o) for o in oks]
    if not oks:
        return None
    return True if all(oks) else False if not any(oks) else None


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n (rule 5) a pass is not enough for supported and a failing criterion
    counts only when it fails decisively; otherwise it is reported as undecided (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


def _greedy(days: Sequence[str], exits: Sequence[str], start: Optional[str] = None) -> list[int]:
    """Indices of non-overlapping entries: the first entry on or after ``start``, then the first entry after each held
    position's exit day."""
    out, free = [], start or ""
    for i, (d, x) in enumerate(zip(days, exits)):
        if d >= free and (not out or d > exits[out[-1]]):
            out.append(i)
            free = x
    return out


def _per_start(days: Sequence[str], exits: Sequence[str], vals, hold: int) -> dict:
    """Rule 10: the greedy non-overlapping walk started at each of ``hold`` offsets from the first signal day."""
    if not days:
        return {}
    v = np.asarray(vals, float)
    res = []
    for o in range(hold):
        idx = _greedy(days, exits, _add(days[0], o))
        if idx:
            res.append((len(idx), float(v[idx].mean())))
    if not res:
        return {}
    ns, ms = [r[0] for r in res], [r[1] for r in res]
    return {"offsets": len(res), "n_min": min(ns), "n_max": max(ns), "mean_min": min(ms), "mean_max": max(ms),
            "offsets_positive": int(sum(m > 0 for m in ms))}


# ============================================================================== T-197 quarterly basis vs bill ==

def basis_days(fut_rows: Sequence[dict], index: dict) -> list[dict]:
    """One row per daily quarterly-futures bar close (bar open + 24 h, 08:00 UTC) at which the Deribit index is known:
    the nearest and second-nearest live quarterlies (expiry after the close), their annualised log basis over the
    index at the same tick and their DTE."""
    by = defaultdict(dict)
    for v in fut_rows:
        try:
            t = int(v["ts_ms"]) + DAY_MS
            e = expiry_ms(v["expiry"])
            c = float(v["close"])
        except (TypeError, ValueError, KeyError):
            continue
        if t < e and c > 0:
            by[t][v["instrument"]] = (e, c)
    out = []
    for t in sorted(by):
        S = index.get(t)
        if not S:
            continue
        live = sorted(by[t].items(), key=lambda kv: kv[1][0])
        if len(live) < 2:
            continue
        (n1, (e1, c1)), (n2, (e2, c2)) = live[0], live[1]
        d1, d2 = (e1 - t) / DAY_MS, (e2 - t) / DAY_MS
        out.append({"day": _dday(t), "t": t, "q1": n1, "q2": n2, "dte1": d1, "dte2": d2, "S": S, "F1": c1, "F2": c2,
                    "basis1": math.log(c1 / S) * 365.0 / d1, "basis2": math.log(c2 / S) * 365.0 / d2})
    return out


def median_ci_t(x, block: int, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> dict:
    """Median with a studentized (bootstrap-t) circular block-bootstrap CI. The studentizer is the standard error of the
    mean of the medians of consecutive ``block``-day batches (a constant-factor proxy for the s.e. of the median; the
    constant cancels in the bootstrap-t), recomputed on the resampled blocks. The percentile CI is reported."""
    n_boot = _nb(n_boot)
    x = np.asarray(x, float)
    n = x.size
    m = float(np.median(x)) if n else float("nan")
    nb = n // block
    if nb < 3:
        return {"median": m, "ci": None, "ci_pct": None, "se": None, "n": int(n), "block": block}
    se = float(np.std(np.median(x[:nb * block].reshape(nb, block), axis=1), ddof=1) / math.sqrt(nb))
    rng = np.random.default_rng(seed)
    tb, mb = [], []
    for s in range(0, n_boot, 250):
        k = min(250, n_boot - s)
        xb = x[_boot_idx(rng, n, block, k)]
        mm = np.median(xb, axis=1)
        bm = np.median(xb[:, :nb * block].reshape(k, nb, block), axis=2)
        ss = np.std(bm, axis=1, ddof=1) / math.sqrt(nb)
        good = ss > 0
        tb.append((mm[good] - m) / ss[good])
        mb.append(mm)
    tb, mb = np.concatenate(tb), np.concatenate(mb)
    a = (1 - level) / 2
    if se <= 0 or tb.size < 10:
        return {"median": m, "ci": None, "ci_pct": [float(np.quantile(mb, a)), float(np.quantile(mb, 1 - a))], "se": se,
                "n": int(n), "block": block}
    return {"median": m, "ci": [m - float(np.quantile(tb, 1 - a)) * se, m - float(np.quantile(tb, a)) * se],
            "ci_pct": [float(np.quantile(mb, a)), float(np.quantile(mb, 1 - a))], "se": se, "n": int(n), "block": block}


def judge_basis(excess, days: Sequence[str], thr: float = T197_THR, min_n: int = T197_MIN_N, block: int = T197_BLOCK,
                 overlap: Optional[int] = None, n_boot: Optional[int] = None, min_year_days: int = 30) -> tuple:
    """T-197 criteria on the daily excess (basis of the second quarterly minus the bill): median > thr; block-bootstrap
    95% CI lower bound > thr, decided only on blocks at least as long as the longest forward window a day's basis spans
    (``overlap`` days, rule 6; the trial's ``block``-day blocks when that is shorter or no overlap is given): the
    studentized and percentile constructions on those blocks must agree (MARGINAL, None, when they disagree). A trial
    block shorter than the rule-6 minimum is reported, never deciding (as batch4_carry T-364). The yearly median > thr in
    a majority of calendar years. Returns (verdict, why, details)."""
    x = np.asarray(excess, float)
    n = int(x.size)
    if n == 0:
        v, why = _decide([("median excess computable", None, False)], 0, min_n, "days")
        return v, why, {"n": 0}
    dblock = max(block, int(overlap)) if overlap else block
    blocks = [block] + ([dblock] if dblock > block else [])
    tests = {b: median_ci_t(x, b, n_boot) for b in blocks}
    t, td = tests[block], tests[dblock]
    yrs = defaultdict(list)
    for d, e in zip(days, x):
        yrs[d[:4]].append(e)
    ymed = {y: float(np.median(v)) for y, v in sorted(yrs.items()) if len(v) >= min_year_days}
    above = sum(v > thr for v in ymed.values())
    cis = {nm: c for nm, c in (("studentized", td["ci"]), ("percentile", td["ci_pct"])) if c is not None}
    ci_ok = _agree([c[0] > thr for c in cis.values()]) if len(cis) == 2 else None
    ci_dec = bool(cis) and all(c[1] < thr for c in cis.values())
    rep = (f"; the trial's {block}-day blocks, shorter than the rule-6 minimum, give lower {_bp((t['ci'] or [None])[0])}, "
           "not deciding" if dblock > block else "")
    crit = [(f"median excess > {thr * 1e4:.0f} bp (median {_bp(t['median'])})", t["median"] > thr, ci_dec),
            (f"block-bootstrap 95% CI excludes {thr * 1e4:.0f} bp on the upper side on {dblock}-day blocks (lower "
             + ", ".join(f"{_bp(c[0])} {nm}" for nm, c in cis.items()) + rep + ")"
             + (" [MARGINAL: studentized and percentile disagree]" if ci_ok is None and len(cis) == 2 else ""),
             ci_ok, ci_dec),
            (f"yearly median > {thr * 1e4:.0f} bp in a majority of calendar years ({above} of {len(ymed)})",
             None if not ymed else above > len(ymed) / 2, False)]
    v, why = _decide(crit, n, min_n, "days")
    return v, why, {"n": n, "test": t, "tests": tests, "year_median": ymed, "years_above": above, "blocks": blocks,
                    "decision_block": dblock}


def basis_claim(rows: list[dict], bills: Bills, n_boot: Optional[int] = None, extended: Optional[list] = None) -> dict:
    if not rows:
        v, why = _decide([("second-quarterly basis days", None, False)], 0, T197_MIN_N, "days")
        return {"stat": {"n": 0}, "n": 0, "verdict": v,
                "reason": f"T-197: no day with two live quarterlies and the Deribit index at the bar close — {why}"}
    days = [r["day"] for r in rows]
    bill = np.array([bills.same_day(d) for d in days])
    b2 = np.array([r["basis2"] for r in rows])
    ex = b2 - bill
    overlap = int(math.ceil(max(r["dte2"] for r in rows)))
    verdict, why, det = judge_basis(ex, days, overlap=overlap, n_boot=n_boot)
    n = det["n"]
    keep7 = np.array([r["dte1"] > 7 for r in rows])
    y22 = np.array([d.startswith("2022") for d in days])
    ex1 = np.array([r["basis1"] for r in rows]) - bill
    ctl = {"excluding_final_7_days_of_q1": {"n": int(keep7.sum()), "median": float(np.median(ex[keep7])) if keep7.any() else None},
           "year_2022": {"n": int(y22.sum()), "median": float(np.median(ex[y22])) if y22.any() else None},
           "nearest_quarterly_median": float(np.median(ex1)),
           "median_basis2": float(np.median(b2)), "median_bill": float(np.median(bill)),
           "share_days_above_thr": float((ex > T197_THR).mean()), "share_days_above_0": float((ex > 0).mean())}
    if extended:
        xe = np.array([r["basis2"] - bills.same_day(r["day"]) for r in extended])
        ctl["with_2018_09_to_2019_04_on_yahoo_close"] = {"n": int(xe.size), "first": extended[0]["day"],
                                                        "median": float(np.median(xe))}
    t = det["test"]
    stat = {"n": n, "min_n": T197_MIN_N, "first": days[0], "last": days[-1], "median_excess": t["median"],
            "ci_studentized": {str(b): tt["ci"] for b, tt in det["tests"].items()},
            "ci_percentile": {str(b): tt["ci_pct"] for b, tt in det["tests"].items()}, "blocks": det["blocks"],
            "decision_block": det["decision_block"],
            "year_median": det["year_median"], "years_above": det["years_above"], "controls": ctl,
            "dte2_range": [float(min(r["dte2"] for r in rows)), float(max(r["dte2"] for r in rows))]}
    yr = ", ".join(f"{y} {_bp(m)}" for y, m in det["year_median"].items())
    cis = "; ".join(f"{b}-day blocks {_cib(tt['ci'])} (percentile {_cib(tt['ci_pct'])})" for b, tt in det["tests"].items())
    ext = ctl.get("with_2018_09_to_2019_04_on_yahoo_close")
    reason = (
        f"T-197 daily {days[0]}..{days[-1]}, n = {n} days: annualised log basis of the second-nearest live Deribit BTC "
        f"quarterly (deribit-quarterly-futures-btc 1D chart close, 08:00 UTC) over the Deribit BTC index at the same tick "
        f"(funding-history index_price; the index is archived from 2019-05-01), ln(F/S) x 365/DTE "
        f"({_f(stat['dte2_range'][0], 0)}-{_f(stat['dte2_range'][1], 0)} DTE), minus the same-day 3-month bill (FRED DTB3 "
        f"discount yield converted to a continuous rate per rule 7; the archive has no DGS3MO). Median excess "
        f"{_bp(t['median'])} (median basis {_bp(ctl['median_basis2'], sign=False)}, bill {_bp(ctl['median_bill'], sign=False)}). "
        f"Studentized circular block bootstrap 95% CI: {cis}. The trial names 20-day blocks; each day's basis is a quote "
        f"on a forward window of up to {overlap} days, so rule 6 requires blocks at least that long: the CI criterion is "
        f"decided on {det['decision_block']}-day blocks only (studentized and percentile must agree) and the 20-day CI is "
        f"reported, not deciding (a trial block below the rule minimum is replaced, as in T-364). Yearly medians: {yr}. Controls: excluding the final 7 days before each nearest-quarterly expiry "
        f"{_bp(ctl['excluding_final_7_days_of_q1']['median'])}; 2022 alone {_bp(ctl['year_2022']['median'])}; nearest "
        f"quarterly {_bp(ctl['nearest_quarterly_median'])}; share of days above 100 bp {ctl['share_days_above_thr']:.0%}"
        + (f"; with the {ext['first']}..2019-04 bars on the Yahoo daily close as spot (8 h before the futures close) "
           f"{_bp(ext['median'])} over {ext['n']} days" if ext else "")
        + "; ETH replication not run (no ETH quarterly bundle)")
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason + f" — {why}"}


def b6b_drb_quarterly_basis(archive):
    """T-197: median annualised basis of the second-nearest Deribit BTC quarterly over the index minus the 3-month bill."""
    miss = _missing(archive, [QF_B, FUND_B, DTB3_B])
    if miss:
        return miss
    fut = [r["value"] for r in _rows(archive, QF_B)]
    idx = _index_hourly(archive)
    rows = basis_days(fut, idx)
    ext = None
    if _has(archive, BTC_DAILY_B) and rows:
        yc = {}
        for r in _rows(archive, BTC_DAILY_B):
            v = r["value"]
            try:
                yc[int(float(v["t"])) * 1000 + DAY_MS + 8 * HOUR_MS] = float(v["close"])  # day D close (24:00) -> D+1 08:00 tick
            except (TypeError, ValueError, KeyError):
                continue
        early = {t: x for t, x in yc.items() if t < rows[0]["t"]}
        ext = basis_days(fut, {**early, **idx}) if early else None
    return _out(basis_claim(rows, Bills(_fred(archive)), extended=ext))


# ================================================================== T-223 Friday 00:00-08:00 settlement straddle ==

def fridays(first: str, last: str) -> list[str]:
    d = date.fromisoformat(first)
    d += timedelta(days=(4 - d.weekday()) % 7)
    out = []
    while d.isoformat() <= last:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def friday_straddles(s00: dict, s08: dict, dvol: dict, bills: Optional[Bills], days: Sequence[str],
                     iv_scale: float = 1.0, hours: int = T223_HOURS) -> tuple:
    """MODEL-PRICED short ATM straddle sold at 00:00 UTC on each Friday in ``days`` (K = S_00, Black-Scholes at DVOL known
    at 00:00 = the close of Thursday's DVOL bar, T = hours / (24 x 365), r = DTB3 known that day) and settled at the 08:00
    price ``s08[day]``. Returns (rows, skipped days with the missing input)."""
    T = hours / (24.0 * 365.0)
    rows, skipped = [], []
    for d in days:
        S0, S8, iv = s00.get(d), s08.get(d), dvol.get(_add(d, -1))
        if not S0 or not S8 or not iv:
            skipped.append(d)
            continue
        r = bills.rate(d) if bills is not None else 0.0
        sig = iv / 100.0 * iv_scale
        prem = bs_price(S0, S0, T, sig, "call", r) + bs_price(S0, S0, T, sig, "put", r)
        pnl = prem - abs(S8 - S0)
        rows.append({"day": d, "monthly": is_last_friday(d), "quarterly": is_quarterly(d), "S0": S0, "S8": S8, "iv": iv,
                     "prem": prem, "pnl_usd": pnl, "pnl": pnl / S0, "absret": abs(S8 / S0 - 1.0)})
    return rows, skipped


def group_diff_ci(x, m, block: int, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> tuple:
    """Difference of group means (m minus not m) with a paired circular block bootstrap on the shared timeline."""
    n_boot = _nb(n_boot)
    x, m = np.asarray(x, float), np.asarray(m, bool)
    if m.sum() < 2 or (~m).sum() < 2:
        return float("nan"), (None, None)
    obs = float(x[m].mean() - x[~m].mean())
    rng = np.random.default_rng(seed)
    out = []
    for s in range(0, n_boot, 500):
        k = min(500, n_boot - s)
        ii = _boot_idx(rng, x.size, block, k)
        xm, mm = x[ii], m[ii]
        c1, c0 = mm.sum(axis=1), (~mm).sum(axis=1)
        good = (c1 > 0) & (c0 > 0)
        out.append(((xm * mm).sum(axis=1)[good] / c1[good]) - ((xm * ~mm).sum(axis=1)[good] / c0[good]))
    d = np.concatenate(out)
    a = (1 - level) / 2
    return obs, (float(np.quantile(d, a)), float(np.quantile(d, 1 - a)))


def perm_test(x, m, n_perm: int = 2000, seed: int = SEED) -> dict:
    x, m = np.asarray(x, float), np.asarray(m, bool)
    if m.sum() < 1 or (~m).sum() < 1:
        return {"diff": None, "p_one": None, "p_two": None}
    obs = float(x[m].mean() - x[~m].mean())
    rng = np.random.default_rng(seed)
    k = int(m.sum())
    ds = np.empty(n_perm)
    for i in range(n_perm):
        p = rng.permutation(x.size)[:k]
        mk = np.zeros(x.size, bool)
        mk[p] = True
        ds[i] = x[mk].mean() - x[~mk].mean()
    return {"diff": obs, "p_one": float((1 + (ds >= obs).sum()) / (n_perm + 1)),
            "p_two": float((1 + (np.abs(ds) >= abs(obs)).sum()) / (n_perm + 1))}


def judge_friday(rows: list[dict], min_n: int = T223_MIN_N, block: int = T223_BLOCK, n_boot: Optional[int] = None) -> tuple:
    """T-223: monthly-expiry minus other-Friday mean P&L > 0 with the 95% CI excluding 0, decided only when the P&L per
    unit spot and the P&L in USD per straddle agree (the claim does not say which). n = monthly-expiry Fridays."""
    m = np.array([r["monthly"] for r in rows], bool)
    n = int(m.sum())
    det = {}
    oks, decs = [], []
    for unit, key in (("per unit spot", "pnl"), ("USD per 1-BTC straddle", "pnl_usd")):
        x = np.array([r[key] for r in rows])
        d, ci = group_diff_ci(x, m, block, n_boot)
        det[unit] = {"diff": d, "ci": list(ci), "mean_monthly": float(x[m].mean()) if n else None,
                     "mean_other": float(x[~m].mean()) if (~m).any() else None}
        if ci[0] is None:
            continue
        oks.append(d > 0 and ci[0] > 0)
        decs.append(ci[1] <= 0)
    u1, u2 = det["per unit spot"], det["USD per 1-BTC straddle"]
    crit = [(f"monthly-expiry minus other-Friday mean P&L > 0 with 95% CI excluding 0 (per unit spot {_bp(u1['diff'], 2)} "
             f"{_cib(u1['ci'])}; USD {_f(u2['diff'], 1, sign=True)} {_ci(u2['ci'], 1)}; {block}-Friday blocks; both units "
             f"must agree)", _agree(oks) if len(oks) == 2 else None, bool(decs) and all(decs))]
    v, why = _decide(crit, n, min_n, "monthly-expiry Fridays")
    return v, why, det


def friday_claim(rows: list[dict], skipped: list, extra: dict, n_boot: Optional[int] = None) -> dict:
    if len(rows) < 4:
        v, why = _decide([("Friday straddles priced", None, False)], 0, T223_MIN_N, "monthly-expiry Fridays")
        return {"stat": {"n": 0, "skipped": skipped}, "n": 0, "verdict": v,
                "reason": f"T-223 {MP}: fewer than 4 Fridays with index, DVOL and settlement — {why}"}
    verdict, why, det = judge_friday(rows, n_boot=n_boot)
    m = np.array([r["monthly"] for r in rows], bool)
    n = int(m.sum())
    perm = perm_test([r["absret"] for r in rows], m)
    q = np.array([r["quarterly"] for r in rows], bool)
    sub = {}
    if q.any():
        x = np.array([r["pnl"] for r in rows])
        sub["quarterly_minus_other_non_monthly"] = float(x[q].mean() - x[~m].mean())
        sub["monthly_non_quarterly_minus_other"] = float(x[m & ~q].mean() - x[~m].mean()) if (m & ~q).any() else None
    stat = {"label": MP, "n": n, "n_fridays": len(rows), "min_n": T223_MIN_N, "first": rows[0]["day"], "last": rows[-1]["day"],
            "judge": det, "abs_return_permutation": perm, "split": sub, "skipped": skipped, **extra}
    u = det["per unit spot"]
    sens = extra.get("iv_scale", {})
    ctl = extra.get("controls", {})
    reason = (
        f"T-223 {MP} (Black-Scholes, K = S_00, IV = BTC DVOL known at 00:00 UTC, T = 8/(24 x 365), r = DTB3 continuous): "
        f"short ATM straddle sold at Friday 00:00 UTC on the Deribit BTC index (funding-history index_price; the claim's "
        f"procedure names BTC-PERPETUAL candles as a proxy for that index) and settled at the actual 08:00 UTC Deribit "
        f"delivery price (30-minute TWAP; deribit-delivery-prices-btc), {len(rows)} Fridays {rows[0]['day']}..{rows[-1]['day']}, "
        f"n = {n} monthly-expiry (last) Fridays vs {len(rows) - n} other Fridays. Mean P&L per unit spot monthly "
        f"{_bp(u['mean_monthly'], 2)} vs other {_bp(u['mean_other'], 2)}: difference {_bp(u['diff'], 2)} 95% CI "
        f"{_cib(u['ci'])} (paired circular block bootstrap over the Friday timeline, {T223_BLOCK}-Friday blocks); in USD "
        f"{_f(det['USD per 1-BTC straddle']['diff'], 1, sign=True)} {_ci(det['USD per 1-BTC straddle']['ci'], 1)}. Mean "
        f"|00-08 return| monthly minus other {_bp(perm['diff'], 2)} (permutation p one-sided {_f(perm['p_one'], 3)}). "
        f"IV-scale sensitivity (difference per unit spot): "
        + ", ".join(f"x{k} {_bp(v, 2)}" for k, v in sens.items())
        + ". Controls: " + "; ".join(f"{k} {v}" for k, v in ctl.items())
        + (f"; quarterly-expiry Fridays minus non-monthly Fridays {_bp(sub.get('quarterly_minus_other_non_monthly'), 2)}, "
           f"non-quarterly monthly minus non-monthly {_bp(sub.get('monthly_non_quarterly_minus_other'), 2)} (every Friday is "
           f"a weekly expiry)" if sub else "")
        + (f"; {len(skipped)} Fridays skipped for a missing index, DVOL or settlement" if skipped else ""))
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason + f" — {why}"}


def b6b_drb_expiry_friday_straddle(archive):
    """T-223: MODEL-PRICED 8-hour ATM BTC short straddle (DVOL), monthly-expiry Fridays vs other Fridays."""
    miss = _missing(archive, [FUND_B, DELIV_B, DVOL_B["BTC"], DTB3_B])
    if miss:
        return miss
    idx, deliv, dvol = _index_hourly(archive), _delivery(archive), _dvol(archive, "BTC")
    bills = Bills(_fred(archive))
    s00 = {}
    for t, x in idx.items():
        if t % DAY_MS == 0:
            s00[_dday(t)] = x
    first = _add(min(dvol), 1)
    last = max(deliv)
    days = fridays(first, last)
    rows, skipped = friday_straddles(s00, deliv, dvol, bills, days)
    sens, ctl = {}, {}
    if len(rows) >= 4:
        for s in (0.9, 1.1):
            r2, _ = friday_straddles(s00, deliv, dvol, bills, days, iv_scale=s)
            m = np.array([r["monthly"] for r in r2], bool)
            x = np.array([r["pnl"] for r in r2])
            sens[s] = float(x[m].mean() - x[~m].mean())
        # FOMC / CPI coincidences (CPI prints at 12:30 UTC, after settlement; FOMC on Wednesdays) excluded
        ev = set()
        if _has(archive, FOMC_B):
            for d in _fomc_days(archive):
                ev.update({d, _add(d, 1)})
        if _has(archive, CPI_B):
            ev.update(r["value"]["day"] for r in _rows(archive, CPI_B) if r["value"].get("day"))
        keep = [r for r in rows if r["day"] not in ev]
        mk = np.array([r["monthly"] for r in keep], bool)
        xk = np.array([r["pnl"] for r in keep])
        ctl["excluding FOMC/CPI-coincident Fridays"] = (f"{len(rows) - len(keep)} dropped, difference "
                                                       f"{_bp(float(xk[mk].mean() - xk[~mk].mean()), 2)}" if mk.any() and (~mk).any() else "n/a")
        # 08:00 index point value instead of the TWAP settlement
        s08i = {_dday(t): x for t, x in idx.items() if t % DAY_MS == 8 * HOUR_MS}
        r3, _ = friday_straddles(s00, s08i, dvol, bills, days)
        m3 = np.array([r["monthly"] for r in r3], bool)
        x3 = np.array([r["pnl"] for r in r3])
        ctl["settled on the 08:00 index print"] = f"difference {_bp(float(x3[m3].mean() - x3[~m3].mean()), 2)}"
        for cur in ("BTC", "ETH"):
            if not (_has(archive, HOURLY_B[cur]) and _has(archive, DVOL_B[cur])):
                ctl[f"Yahoo hourly {cur}"] = "not archived"
                continue
            bars = _hourly_bars(archive, cur)
            y00 = {_dday(t): o for t, (o, c) in bars.items() if t % DAY_MS == 0}
            y08 = {_dday(t): c for t, (o, c) in bars.items() if t % DAY_MS == 7 * HOUR_MS}
            r4, _ = friday_straddles(y00, y08, _dvol(archive, cur), bills, days)
            m4 = np.array([r["monthly"] for r in r4], bool)
            if m4.sum() >= 2 and (~m4).sum() >= 2:
                x4 = np.array([r["pnl"] for r in r4])
                d4, ci4 = group_diff_ci(x4, m4, T223_BLOCK)
                ctl[f"Yahoo hourly {cur} (00:00 open, 07:00-bar close, {cur} DVOL)"] = (
                    f"{len(r4)} Fridays {r4[0]['day']}..{r4[-1]['day']}, {int(m4.sum())} monthly, difference {_bp(d4, 2)} {_cib(ci4)}")
    return _out(friday_claim(rows, skipped, {"iv_scale": sens, "controls": ctl}))


# ===================================================================== T-269 CME (1256) vs IBIT covered call ==

def deribit_monthly_expiries(first: str, last: str) -> list[str]:
    d0, d1 = date.fromisoformat(first), date.fromisoformat(last)
    out, y, m = [], d0.year, d0.month
    while date(y, m, 1) <= d1:
        f = last_friday(y, m)
        if d0 <= f <= d1:
            out.append(f.isoformat())
        y, m = (y + (m == 12), m % 12 + 1)
    return out


def covered_call_cycles(expiries: Sequence[str], spot: dict, dvol: dict, bills: Bills, basis: dict,
                        delta: float = 0.25, iv_scale: float = 1.0) -> list[dict]:
    """MODEL-PRICED monthly 25-delta covered call on 1 BTC on Deribit's last-Friday calendar: written at one expiry's
    08:00 settlement price, settled at the next. IV = DVOL known at the entry (Thursday's bar close), T = calendar days /
    365, r = DTB3 known at entry. ``basis`` = {entry day: annualised futures basis known at the entry}."""
    out = []
    for e0, e1 in zip(expiries[:-1], expiries[1:]):
        S0, ST, iv = spot.get(e0), spot.get(e1), dvol.get(_add(e0, -1))
        if not S0 or not ST or not iv:
            continue
        T = (date.fromisoformat(e1) - date.fromisoformat(e0)).days / 365.0
        r = bills.rate(e0)
        sig = iv / 100.0 * iv_scale
        K = float(bs.strike_for_delta(S0, T, r, sig, delta, "call"))
        C = bs_price(S0, K, T, sig, "call", r)
        b = basis.get(e0)
        out.append({"entry": e0, "expiry": e1, "year": int(e1[:4]), "S0": S0, "ST": ST, "K": K, "prem": C, "iv": iv, "T": T,
                    "r": r, "opt": C - max(ST - K, 0.0), "share": ST - S0, "basis": b,
                    "basis_cost": S0 * (math.exp(b * T) - 1.0) if b is not None else None,
                    "bill_income": S0 * (math.exp(r * T) - 1.0)})
    return out


def annual_tax(cycles: list[dict], flat_basis: Optional[float] = None, collateral_interest: bool = False,
               first: int = T269_FIRST, last: int = T269_LAST) -> dict:
    """Per calendar year (cycles assigned to their expiry year): pre-tax option, share and basis-cost P&L over the
    year's starting spot, the IBIT after-tax return (option P&L short-term at 37%, share P&L long-term at 20% on a
    liquidation basis) and the CME after-tax return (long future pays the basis; all P&L 60/40 = 26.8%, marked at year
    end); symmetric: losses earn the tax rate (offset against other gains)."""
    by = defaultdict(list)
    for c in cycles:
        if first <= c["year"] <= last:
            by[c["year"]].append(c)
    out = {}
    for y in sorted(by):
        cs = by[y]
        S = cs[0]["S0"]
        o = sum(c["opt"] for c in cs) / S
        s = sum(c["share"] for c in cs) / S
        if flat_basis is None:
            if any(c["basis_cost"] is None for c in cs):
                continue
            b = sum(c["basis_cost"] for c in cs) / S
        else:
            b = sum(c["S0"] * (math.exp(flat_basis * c["T"]) - 1.0) for c in cs) / S
        bi = sum(c["bill_income"] for c in cs) / S if collateral_interest else 0.0
        ibit = (o + s) - (T269_ORD * o + T269_LT * s)
        cme_pre = o + s - b
        cme = cme_pre * (1 - T269_1256) + bi * (1 - T269_ORD)
        out[y] = {"cycles": len(cs), "first_entry": cs[0]["entry"], "last_expiry": cs[-1]["expiry"], "opt": o, "share": s,
                  "basis_cost": b, "pre_tax": o + s, "ibit_after": ibit, "cme_pre": cme_pre, "cme_after": cme,
                  "diff": cme - ibit}
    return out


def carry_losses(years: dict) -> dict:
    """Control: no outside gains to offset. CME: a net Section 1256 loss is carried back up to three years against
    earlier net 1256 gains (refund at 26.8%), the rest forward; IBIT: short- and long-term capital results netted, net
    losses carried forward only (the $3,000 ordinary offset ignored)."""
    ys = sorted(years)
    cme_gain_hist: dict[int, float] = {}
    cme_cf, st_cf, lt_cf = 0.0, 0.0, 0.0
    out = {}
    for y in ys:
        v = years[y]
        g = v["cme_pre"] + cme_cf
        cme_cf = 0.0
        if g >= 0:
            tax_c = T269_1256 * g
            cme_gain_hist[y] = g
        else:
            loss, refund = -g, 0.0
            for yb in (y - 3, y - 2, y - 1):
                take = min(loss, cme_gain_hist.get(yb, 0.0))
                if take > 0:
                    cme_gain_hist[yb] -= take
                    refund += T269_1256 * take
                    loss -= take
            tax_c = -refund
            cme_cf = -loss
        st, lt = v["opt"] + st_cf, v["share"] + lt_cf
        st_cf = lt_cf = 0.0
        if st < 0 < lt:
            lt, st = lt + st, 0.0
        elif lt < 0 < st:
            st, lt = st + lt, 0.0
        if st < 0:
            st_cf, st = st, 0.0
        if lt < 0:
            lt_cf, lt = lt, 0.0
        tax_i = T269_ORD * max(st, 0.0) + T269_LT * max(lt, 0.0)
        cme = v["cme_pre"] - tax_c
        ibit = v["pre_tax"] - tax_i
        out[y] = {"cme_after": cme, "ibit_after": ibit, "diff": cme - ibit}
    return out


def judge_tax(diffs, min_n: int = T269_MIN_N, n_boot: Optional[int] = None) -> tuple:
    d = np.asarray(diffs, float)
    n = int(d.size)
    if n < 2:
        v, why = _decide([("annual differences", None, False)], n, min_n, "years")
        return v, why, {"n": n}
    lo, hi = mean_ci(d, 1, n_boot)
    crit = [(f"mean annual after-tax difference CME - IBIT > 0 (mean {_f(float(d.mean()), 2, True, True)})", d.mean() > 0,
             hi is not None and hi <= 0),
            (f"bootstrap over years 95% CI excludes 0 on the upper side (lower {_f(lo, 2, True, True)})", lo > 0,
             hi is not None and hi <= 0)]
    v, why = _decide(crit, n, min_n, "years")
    return v, why, {"n": n, "mean": float(d.mean()), "ci": [lo, hi]}


def tax_claim(cycles: list[dict], n_boot: Optional[int] = None, iv_cycles: Optional[dict] = None) -> dict:
    years = annual_tax(cycles)
    if not years:
        v, why = _decide([("annual returns 2021-2025", None, False)], 0, T269_MIN_N, "years")
        return {"stat": {"n": 0}, "n": 0, "verdict": v,
                "reason": f"T-269 {MP}: no year 2021-2025 with priced cycles and a known futures basis — {why}"}
    ys = sorted(years)
    diffs = [years[y]["diff"] for y in ys]
    verdict, why, det = judge_tax(diffs, n_boot=n_boot)
    sens = {f"{b:.1%}": float(np.mean([v["diff"] for v in annual_tax(cycles, flat_basis=b).values()])) for b in T269_BASIS_GRID}
    coll = annual_tax(cycles, collateral_interest=True)
    carry = carry_losses(years)
    ivs = {}
    for s, cyc in (iv_cycles or {}).items():
        yy = annual_tax(cyc)
        ivs[s] = float(np.mean([v["diff"] for v in yy.values()])) if yy else None
    zero = float(np.mean([-(v["basis_cost"]) * (1 - T269_1256) for v in years.values()]))
    stat = {"label": MP, "n": det["n"], "min_n": T269_MIN_N, "years": years, "mean_diff": det.get("mean"), "ci": det.get("ci"),
            "rates": {"ordinary": T269_ORD, "long_term": T269_LT, "sec1256_blended": T269_1256},
            "basis_sensitivity_mean_diff": sens,
            "with_collateral_bill_interest_mean_diff": float(np.mean([v["diff"] for v in coll.values()])),
            "loss_carry_control": carry, "loss_carry_mean_diff": float(np.mean([v["diff"] for v in carry.values()])),
            "zero_return_year_diff": zero, "iv_scale_mean_diff": ivs, "partial_first_year": years[ys[0]]["first_entry"]}
    yr = "; ".join(f"{y}: pre-tax {_f(v['pre_tax'], 1, True, True)} (calls {_f(v['opt'], 1, True, True)}, BTC "
                   f"{_f(v['share'], 1, True, True)}, basis {_f(v['basis_cost'], 1, True)}), IBIT {_f(v['ibit_after'], 1, True, True)}, "
                   f"CME {_f(v['cme_after'], 1, True, True)}, diff {_f(v['diff'], 1, True, True)}" for y, v in years.items())
    reason = (
        f"T-269 {MP} (Black-Scholes at BTC DVOL known at entry, no skew): 25-delta call written on 1 BTC at each Deribit "
        f"monthly expiry (last Friday 08:00 UTC delivery price) and settled at the next, {len(cycles)} cycles; years by "
        f"expiry, {ys[0]} starts at {years[ys[0]]['first_entry']} (DVOL begins 2021-03-24, so 2021 is April-December). "
        f"Returns are over each year's starting spot. Tax (statutory, NIIT ignored): IBIT call P&L short-term at 37%, IBIT "
        f"share P&L long-term at 20% (liquidation basis; held > 1 year as the claim states; qualified-covered-call and "
        f"straddle rules not modelled), CME all P&L 60/40 = 26.8% marked at year end; losses earn the rate (offset against "
        f"other gains). CME carry = the Deribit dated-futures basis (nearest quarterly with >= 7 days, ln(F/index) x "
        f"365/DTE at the entry tick) paid for each cycle; the futures collateral earns nothing (as the trial models it). "
        f"IBIT did not exist before 2024-01-11 and its 0.25% fee is not charged (costs as the claim states). {yr}. Mean "
        f"difference {_f(det.get('mean'), 2, True, True)}, bootstrap over years 95% CI {_ci(det.get('ci'), 2, True)}. "
        f"Sensitivity, mean difference at a flat basis: " + ", ".join(f"{k} {_f(v, 2, True, True)}" for k, v in sens.items())
        + f"; with the bill earned on CME collateral (taxed at 37%) {_f(stat['with_collateral_bill_interest_mean_diff'], 2, True, True)}; "
        f"loss-carry control (no outside gains; 1256 three-year carryback) {_f(stat['loss_carry_mean_diff'], 2, True, True)}; "
        f"zero-return-year control (difference = -basis x 0.732) {_f(zero, 2, True, True)}; IV-scale sensitivity "
        + ", ".join(f"x{k} {_f(v, 2, True, True)}" for k, v in ivs.items())
        + f". Identity: diff = 0.102 x calls - 0.068 x BTC - 0.732 x basis per year")
    return {"stat": stat, "n": det["n"], "verdict": verdict, "reason": reason + f" — {why}"}


def entry_basis(fut_rows: Sequence[dict], index: dict, days: Sequence[str], min_dte: float = 7.0) -> dict:
    """{day: annualised log basis of the nearest Deribit quarterly with >= min_dte days left, from the 1D bar closing at
    that day's 08:00 UTC and the index at the same tick}."""
    want = {expiry_ms(d): d for d in days}
    by = defaultdict(list)
    for v in fut_rows:
        try:
            t = int(v["ts_ms"]) + DAY_MS
            if t in want:
                by[t].append((expiry_ms(v["expiry"]), float(v["close"])))
        except (TypeError, ValueError, KeyError):
            continue
    out = {}
    for t, xs in by.items():
        S = index.get(t)
        live = sorted((e, c) for e, c in xs if (e - t) / DAY_MS >= min_dte and c > 0)
        if S and live:
            e, c = live[0]
            out[want[t]] = math.log(c / S) * 365.0 / ((e - t) / DAY_MS)
    return out


def b6b_drb_cme_ibit_tax(archive):
    """T-269: after-tax CME futures covered call (Section 1256, pays the futures basis) vs IBIT covered call, 2021-2025."""
    miss = _missing(archive, [DELIV_B, DVOL_B["BTC"], DTB3_B, QF_B, FUND_B])
    if miss:
        return miss
    spot, dvol = _delivery(archive), _dvol(archive, "BTC")
    bills = Bills(_fred(archive))
    first = _add(min(dvol), 1)
    exps = deribit_monthly_expiries(first, f"{T269_LAST}-12-31")
    basis = entry_basis([r["value"] for r in _rows(archive, QF_B)], _index_hourly(archive), exps)
    cyc = covered_call_cycles(exps, spot, dvol, bills, basis)
    ivc = {s: covered_call_cycles(exps, spot, dvol, bills, basis, iv_scale=s) for s in (0.9, 1.1)}
    return _out(tax_claim(cyc, iv_cycles=ivc))


# ================================================================================= T-222 catalyst strangle ==

def catalyst_inputs(rows: Sequence[dict]) -> tuple:
    """(windows {key: value + available_at}, trades {key: [trade values sorted by time]}) of the catalyst bundle."""
    wins, trades = {}, defaultdict(list)
    for r in rows:
        v = r["value"]
        if r.get("kind") == "catalyst-window":
            wins[f"{v['catalyst']}:{v['currency']}"] = {**v, "available_at": r.get("available_at")}
        elif r.get("kind") == "option-trade":
            try:
                v["_ts"] = int(v["timestamp"])
            except (TypeError, ValueError, KeyError):
                continue
            trades[f"{v.get('catalyst')}:{v.get('currency')}"].append(v)
    for k in trades:
        trades[k].sort(key=lambda t: t["_ts"])
    return wins, dict(trades)


def _yr(ms_span: float) -> float:
    return ms_span / DAY_MS / 365.0


def _snapshot(trades: Sequence[dict], tau: int, lookback: int = DAY_MS, min_ts: int = 0) -> tuple:
    """Latest print per instrument in [tau - lookback, tau) (and >= min_ts), and the index at the last print before tau."""
    lo = max(tau - lookback, min_ts)
    last, S = {}, None
    for t in trades:
        if t["_ts"] >= tau:
            break
        if t["_ts"] >= lo:
            last[t["instrument_name"]] = t
            try:
                S = float(t["index_price"])
            except (TypeError, ValueError, KeyError):
                pass
    return last, S


def _smile_from_prints(prints: Sequence[dict], S: float, T: float) -> Optional[dict]:
    pts = []
    for t in prints:
        try:
            pts.append((float(t["strike"]), float(t["iv"]) / 100.0, 1.0))
        except (TypeError, ValueError, KeyError):
            continue
    return smile_fit(pts, S, T)


def choose_strangle(last: dict, S: float, T: float, target: float = 0.25) -> Optional[tuple]:
    """(call print, put print, call delta, put delta) nearest +-``target`` delta at the decision (Black-Scholes, r = 0, on
    the index with each print's IV), among out-of-the-money candidates with |delta| in [0.10, 0.40]."""
    best = {"call": None, "put": None}
    for t in last.values():
        try:
            K, iv, kind = float(t["strike"]), float(t["iv"]) / 100.0, t["type"]
        except (TypeError, ValueError, KeyError):
            continue
        if iv <= 0 or kind not in best:
            continue
        dl = bs_delta(S, K, T, iv, kind)
        if kind == "call" and K > S and 0.10 <= dl <= 0.40:
            gap = abs(dl - target)
        elif kind == "put" and K < S and -0.40 <= dl <= -0.10:
            gap = abs(dl + target)
        else:
            continue
        if best[kind] is None or gap < best[kind][0]:
            best[kind] = (gap, t, dl)
    if best["call"] is None or best["put"] is None:
        return None
    return best["call"][1], best["put"][1], best["call"][2], best["put"][2]


def leg_value(trades: Sequence[dict], inst: str, tau: int, end: int, expiry: int, side: Optional[str] = None,
              taker: bool = False) -> Optional[dict]:
    """Value of one option leg at a decision ``tau``: the first print of the instrument in [tau, end) (Deribit mark at
    that print, or the trade price of the first print on the aggressor ``side`` when ``taker``); else a re-mark at tau of
    its latest print in the previous 24 h (Black-Scholes, r = 0, its own IV on the index at tau); else the expiry's
    trade-print smile at tau. Returns {coin, S, how} or None."""
    for t in trades:
        if t["_ts"] < tau:
            continue
        if t["_ts"] >= end:
            break
        if t["instrument_name"] != inst:
            continue
        if taker and t.get("direction") != side:
            continue
        try:
            px = float(t["price"] if taker else t["mark_price"])
            return {"coin": px, "S": float(t["index_price"]), "how": "taker print" if taker else "mark at next print",
                    "ts": t["_ts"]}
        except (TypeError, ValueError, KeyError):
            continue
    last, S = _snapshot(trades, tau)
    if not S:
        return None
    T = _yr(expiry - tau)
    p = last.get(inst)
    if p is not None:
        try:
            iv = float(p["iv"]) / 100.0
            return {"coin": bs_price(S, float(p["strike"]), T, iv, p["type"]) / S, "S": S, "how": "re-marked own IV", "ts": tau}
        except (TypeError, ValueError, KeyError):
            pass
    meta = _parse_name(inst)
    fit = _smile_from_prints(list(last.values()), S, T)
    if fit is None or meta is None:
        return None
    iv = smile_iv(fit, meta[0])
    return {"coin": bs_price(S, meta[0], T, iv, meta[1]) / S, "S": S, "how": "smile re-mark", "ts": tau}


def _parse_name(inst: str) -> Optional[tuple]:
    m = re.match(r"^[A-Z]+-\d{1,2}[A-Z]{3}\d{2}-(\d+(?:d\d+)?)-([CP])$", inst or "")
    if not m:
        return None
    return float(m.group(1).replace("d", ".")), "call" if m.group(2) == "C" else "put"


def _atm_iv(last: dict, S: float) -> Optional[float]:
    ks = defaultdict(list)
    for t in last.values():
        try:
            ks[float(t["strike"])].append(float(t["iv"]))
        except (TypeError, ValueError, KeyError):
            continue
    if not ks:
        return None
    k = min(ks, key=lambda x: abs(x - S))
    return float(np.mean(ks[k]))


def strangle_window(w: dict, trades: Sequence[dict], tau_hour: int = T222_TAU, taker: bool = False,
                    fees: bool = True) -> dict:
    """One catalyst window: buy the 25-delta strangle of the target expiry at ``tau_hour``:00 UTC on the entry day (event
    - 21 d), sell it at the same hour on the exit day (event - 1 d). Strikes from the latest prints before the entry
    decision; each leg filled at the first print after the decision (Deribit mark) on that day, else re-marked. Fees per
    leg and side at the assumed schedule. Returns the USD and coin returns on debit (net of fees)."""
    tau_e = _ms(w["entry_day"] + f"T{tau_hour:02d}:00:00+00:00")
    tau_x = _ms(w["exit_day"] + f"T{tau_hour:02d}:00:00+00:00")
    listed = _ms(w["target_listed_at"]) if w.get("target_listed_at") else 0
    exp = expiry_ms(w["target_expiry"])
    ev = _ms(w["event_time"])
    res = {"window": f"{w['catalyst']}:{w['currency']}", "catalyst": w["catalyst"], "currency": w["currency"],
           "category": w.get("category"), "entry": _iso(tau_e), "exit": _iso(tau_x), "target": w.get("target_expiry_code")}
    last, S = _snapshot(trades, tau_e, min_ts=listed)
    if not S or not last:
        return {**res, "ok": False, "why": "no target-expiry print in the 24 h before the entry decision"}
    T = _yr(exp - tau_e)
    pick = choose_strangle(last, S, T)
    if pick is None:
        return {**res, "ok": False, "why": "no 0.10-0.40 delta call and put printed in the 24 h before entry"}
    c, p, dc, dp = pick
    end_e = min(_ms(_add(w["entry_day"], 1)), ev)
    end_x = min(_ms(_add(w["exit_day"], 1)), ev)
    legs = []
    for t in (c, p):
        ent = leg_value(trades, t["instrument_name"], tau_e, end_e, exp, "buy", taker)
        ext = leg_value(trades, t["instrument_name"], tau_x, end_x, exp, "sell", taker)
        if ent is None or ext is None:
            return {**res, "ok": False, "why": f"{t['instrument_name']} could not be valued at entry or exit"}
        legs.append({"instrument": t["instrument_name"], "entry": ent, "exit": ext})
    fe = [option_fee(L["entry"]["coin"]) if fees else 0.0 for L in legs]
    fx = [option_fee(L["exit"]["coin"]) if fees else 0.0 for L in legs]
    debit = sum((L["entry"]["coin"] + f) * L["entry"]["S"] for L, f in zip(legs, fe))
    proceeds = sum((L["exit"]["coin"] - f) * L["exit"]["S"] for L, f in zip(legs, fx))
    debit_c = sum(L["entry"]["coin"] + f for L, f in zip(legs, fe))
    proc_c = sum(L["exit"]["coin"] - f for L, f in zip(legs, fx))
    last_x, Sx = _snapshot(trades, tau_x)
    return {**res, "ok": debit > 0, "ret": proceeds / debit - 1.0 if debit > 0 else None,
            "ret_coin": proc_c / debit_c - 1.0 if debit_c > 0 else None, "delta_call": dc, "delta_put": dp,
            "legs": [{"instrument": L["instrument"], "entry_coin": L["entry"]["coin"], "exit_coin": L["exit"]["coin"],
                      "entry_how": L["entry"]["how"], "exit_how": L["exit"]["how"]} for L in legs],
            "S_entry": S, "S_exit": Sx, "atm_iv_entry": _atm_iv(last, S), "atm_iv_exit": _atm_iv(last_x, Sx) if Sx else None,
            "fees_usd": sum(f * L["entry"]["S"] for L, f in zip(legs, fe)) + sum(f * L["exit"]["S"] for L, f in zip(legs, fx))}


def pit_window(w: dict, tau_hour: int = T222_TAU) -> bool:
    """Point in time: the window row (verified known_since and the target expiry's listing) available by the entry."""
    av = w.get("available_at")
    return bool(av) and _ms(av) <= _ms(w["entry_day"] + f"T{tau_hour:02d}:00:00+00:00")


def by_catalyst(results: Sequence[dict], key: str = "ret") -> dict:
    """One observation per catalyst: the mean over its currencies (the claim's unit is catalysts)."""
    g = defaultdict(list)
    for r in results:
        if r.get("ok") and r.get(key) is not None:
            g[r["catalyst"]].append(r[key])
    return {k: float(np.mean(v)) for k, v in sorted(g.items())}


def judge_catalyst(rets, min_n: int = T222_MIN_N, n_boot: Optional[int] = None) -> tuple:
    """T-222: exact sign test p < 0.05 (one-sided, positive) and mean > 0 with the 95% CI excluding 0, once n >= 20."""
    x = np.asarray(rets, float)
    n = int(x.size)
    if n == 0:
        v, why = _decide([("catalyst returns", None, False)], 0, min_n, "catalysts")
        return v, why, {"n": 0}
    k = int((x > 0).sum())
    p1, p2 = sign_test(k, n)
    best = sign_test(k + max(min_n - n, 0), max(n, min_n))[0]
    lo, hi = mean_ci(x, 1, n_boot) if n >= 2 else (None, None)
    crit = [(f"exact sign test p < 0.05 ({k} of {n} positive, one-sided p {p1:.3f}; at best {best:.3f} at n = {max(n, min_n)})",
             p1 < 0.05, best >= 0.05),
            (f"mean return on debit > 0 with 95% CI excluding 0 (mean {_f(float(x.mean()), 1, True, True)}, CI "
             f"{_ci((lo, hi), 1, True)})", None if lo is None else bool(x.mean() > 0 and lo > 0),
             hi is not None and hi <= 0)]
    v, why = _decide(crit, n, min_n, "catalysts")
    return v, why, {"n": n, "positive": k, "p_one": p1, "p_two": p2, "p_best_at_min_n": best, "mean": float(x.mean()),
                    "ci": [lo, hi]}


def ex_ante_timed(w: dict) -> bool:
    """Rule 4: the window's entry, exit and target expiry come from an event time known at the entry decision. A window
    timed from a realised block height (event_time_basis 'realised (ex post)') is not: at the entry that time was only
    an estimate (a few days for the halvings), so it is reported apart from the primary statistic."""
    return w.get("event_time_basis") != REALISED_TIME


def catalyst_claim(wins: dict, trades: dict, dvol: dict, n_boot: Optional[int] = None) -> dict:
    keys = sorted(wins)
    pit_all = [k for k in keys if pit_window(wins[k])]
    pit = [k for k in pit_all if ex_ante_timed(wins[k])]
    real = [k for k in pit_all if not ex_ante_timed(wins[k])]

    def run(ks, **kw):
        return [strangle_window(wins[k], trades.get(k, []), **kw) for k in ks]
    res = run(pit)
    res_real = run(real)
    per = by_catalyst(res)
    verdict, why, det = judge_catalyst(list(per.values()), n_boot=n_boot)
    n = det["n"]
    # reported statistics and controls
    spread = []
    for r in res:
        if not r.get("ok") or r.get("atm_iv_entry") is None or r.get("atm_iv_exit") is None:
            continue
        dv = dvol.get(r["currency"], {})
        a, b = dv.get(_add(r["entry"][:10], -1)), dv.get(_add(r["exit"][:10], -1))
        if a is not None and b is not None:
            spread.append((r["window"], (r["atm_iv_exit"] - r["atm_iv_entry"]) - (b - a)))
    taker = by_catalyst(run(pit, taker=True))
    gross = by_catalyst(run(pit, fees=False))
    coin = by_catalyst(res, "ret_coin")
    tau = {h: by_catalyst(run([k for k in keys if pit_window(wins[k], h) and ex_ante_timed(wins[k])], tau_hour=h))
           for h in (8, 16)}
    nonpit = by_catalyst(run(keys))
    with_real = by_catalyst(res + res_real)
    cats = defaultdict(list)
    for r in res:
        if r.get("ok"):
            cats[r.get("category")].append(r["ret"])
    hows = defaultdict(int)
    for r in res:
        for L in r.get("legs", []):
            hows[L["entry_how"]] += 1
            hows[L["exit_how"]] += 1
    m = lambda d: (f"{_f(float(np.mean(list(d.values()))), 1, True, True)} over {len(d)}" if d else "n/a")
    stat = {"n": n, "min_n": T222_MIN_N, "windows_total": len(keys), "windows_pit": len(pit_all),
            "windows_primary": len(pit), "windows_realised_event_time": real,
            "windows": [{k: v for k, v in r.items() if k != "legs"} | {"legs": r.get("legs")} for r in res],
            "realised_event_time_windows": {r["window"]: r.get("ret") for r in res_real},
            "per_catalyst": per, "judge": det, "iv_minus_dvol_change": dict(spread),
            "iv_minus_dvol_mean": float(np.mean([s for _, s in spread])) if spread else None,
            "taker_prints": taker, "gross_of_fees": gross, "coin_terms": coin, "tau_sensitivity": tau,
            "all_windows_not_point_in_time": nonpit, "pit_including_realised_event_time": with_real,
            "by_category": {k: float(np.mean(v)) for k, v in cats.items()}, "valuation": dict(hows)}
    drop = [r for r in res if not r.get("ok")]
    rl = "; ".join(f"{r['window']} {_f(r['ret'], 1, True, True)}" for r in res if r.get("ok"))
    rr = "; ".join(f"{r['window']} {_f(r['ret'], 1, True, True)}" for r in res_real if r.get("ok"))
    reason = (
        f"T-222 on Deribit trade prints (deribit-option-trades-catalysts, the first expiry after each event listed by the "
        f"entry): long 25-delta strangle bought at {T222_TAU}:00 UTC 21 days before and sold at {T222_TAU}:00 UTC 1 day "
        f"before. Point in time: of {len(keys)} stored windows only the {len(pit_all)} whose window row (verified known_since "
        f"and the target listing) was available by the entry qualify; the others carry no verified fixing date before "
        f"the entry. Of those, {len(real)} are timed from a realised block height (entry, exit and 'first expiry after the "
        f"event' from the realised time, at the entry only a few-day estimate; the bundle stores no estimate as of the "
        f"entry), so the primary statistic uses the {len(pit)} windows timed from a date known ex ante (rule 4). Strikes: the out-of-the-money call and put nearest 0.25 |delta| (Black-Scholes, r = 0, index and each "
        f"print's IV) among the latest prints in the 24 h before the decision; each leg filled at the first print at or "
        f"after the decision that day (Deribit mark_price x index; a leg without one is re-marked at the decision from its "
        f"own last IV or the expiry's print smile: {dict(hows)}); {FEE_TXT}, both sides. Windows: {rl}"
        + (f"; realised block-height windows (reported, not in the primary statistic): {rr}" if rr else "")
        + (f"; dropped {[r['window'] + ' (' + r['why'] + ')' for r in drop]}" if drop else "")
        + f". One observation per catalyst (BTC and ETH windows of one catalyst averaged): n = {n} catalysts, "
        f"{det.get('positive', 0)} positive, mean return on debit {_f(det.get('mean'), 1, True, True)}, 95% iid bootstrap CI "
        f"{_ci(det.get('ci'), 1, True)}, sign test p {_f(det.get('p_one'), 3)}. Reported: event-expiry ATM IV change "
        f"minus DVOL change {_f(stat['iv_minus_dvol_mean'], 2, sign=True)} vol points over {len(spread)} windows (DVOL from "
        f"2021-03); taker prints (buy-side fill in, sell-side out) {m(taker)}; gross of fees {m(gross)}; coin terms {m(coin)}; "
        f"decision at 08:00 {m(tau[8])}, at 16:00 {m(tau[16])}; with the {len(real)} realised block-height windows added "
        f"(NOT point in time: timed from the realised event) {m(with_real)}; "
        f"all {len(keys)} windows ignoring point in time (NOT a test: uses catalysts not verifiably known at entry) "
        f"{m(nonpit)}; by category " + ", ".join(f"{k} {_f(float(np.mean(v)), 1, True, True)} ({len(v)})" for k, v in
                                                 sorted(cats.items(), key=lambda kv: str(kv[0])))
        + f". Non-catalyst 21-day windows and Polymarket odds need trades outside the stored windows: not run")
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason + f" — {why}"}


def b6b_drb_catalyst_strangle(archive):
    """T-222: 25-delta strangle in the first expiry after a hard-dated BTC/ETH catalyst, bought 21 d before, sold 1 d before."""
    miss = _missing(archive, [CAT_B])
    if miss:
        return miss
    wins, trades = _cached(archive, ("catalyst",), lambda: catalyst_inputs(_rows(archive, CAT_B)))
    dvol = {c: _dvol(archive, c) for c in ("BTC", "ETH") if _has(archive, DVOL_B[c])}
    return _out(catalyst_claim(wins, trades, dvol))


# ============================================================================== trade-print smiles (T-257/262) ==

def smile_fit(points: Sequence[tuple], S: float, T: float, min_strikes: int = 4) -> Optional[dict]:
    """Quadratic smile IV(x) = a + b x + c x^2 in standardised moneyness x = ln(K/S)/sqrt(T), weighted least squares over
    strikes (per-strike mean IV of the prints, weight = log(1 + prints)); needs ``min_strikes`` strikes with at least one
    on each side of S. Flat beyond the outermost strikes."""
    if not S or S <= 0 or T <= 0:
        return None
    ks = defaultdict(list)
    for K, iv, w in points:
        if K > 0 and iv and iv > 0 and math.isfinite(iv):
            ks[float(K)].append(iv)
    if len(ks) < min_strikes:
        return None
    K = np.array(sorted(ks))
    x = np.log(K / S) / math.sqrt(T)
    if not (x.min() < 0 < x.max()):
        return None
    y = np.array([np.mean(ks[k]) for k in K])
    w = np.log1p(np.array([len(ks[k]) for k in K], float))
    A = np.vstack([np.ones_like(x), x, x * x]).T * np.sqrt(w)[:, None]
    coef, *_ = np.linalg.lstsq(A, y * np.sqrt(w), rcond=None)
    n = sum(len(v) for v in ks.values())
    return {"a": float(coef[0]), "b": float(coef[1]), "c": float(coef[2]), "xmin": float(x.min()), "xmax": float(x.max()),
            "S": float(S), "T": float(T), "strikes": [float(k) for k in K], "n": int(n)}


def smile_iv(fit: dict, K: float, S: Optional[float] = None) -> float:
    S = fit["S"] if S is None else S
    x = math.log(K / S) / math.sqrt(fit["T"])
    x = min(max(x, fit["xmin"]), fit["xmax"])
    return max(fit["a"] + fit["b"] * x + fit["c"] * x * x, 0.05)


def delta_strike(fit: dict, target: float, kind: str, margin: float = 0.1) -> Optional[tuple]:
    """(K, IV) where the Black-Scholes delta (r = 0, at the smile IV of K) equals ``target``; None when that strike lies
    more than ``margin`` (standardised moneyness) outside the printed strikes."""
    S, T = fit["S"], fit["T"]
    sq = math.sqrt(T)

    def f(x):
        K = S * math.exp(x * sq)
        return bs_delta(S, K, T, smile_iv(fit, K), kind) - target
    lo, hi = fit["xmin"] - margin, fit["xmax"] + margin
    flo, fhi = f(lo), f(hi)
    if not (flo > 0 > fhi):
        return None
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    K = S * math.exp(0.5 * (lo + hi) * sq)
    return K, smile_iv(fit, K)


def daily_smiles(trades: Sequence[dict], hours: tuple = (7, 9), max_dte: float = 400.0) -> dict:
    """{day: {S, fits: {expiry: fit}}} from the day's sampled prints (``hours`` UTC): S = median index of the sample, one
    smile per expiry at T = (expiry 08:00 - day 08:00) / 365 d."""
    by = defaultdict(lambda: defaultdict(list))
    idx = defaultdict(list)
    for t in trades:
        try:
            ts = int(t["timestamp"])
            h = (ts % DAY_MS) // HOUR_MS
            if not (hours[0] <= h < hours[1]):
                continue
            d = _dday(ts)
            e = t.get("expiry") or code_date(t["instrument_name"].split("-")[1])
            by[d][e[:10]].append((float(t["strike"]), float(t["iv"]) / 100.0, float(t.get("amount") or 1.0)))
            idx[d].append(float(t["index_price"]))
        except (TypeError, ValueError, KeyError, AttributeError, IndexError):
            continue
    out = {}
    for d in sorted(by):
        S = float(np.median(idx[d]))
        fits = {}
        for e, pts in by[d].items():
            T = (expiry_ms(e) - _ms(d + "T08:00:00+00:00")) / DAY_MS / 365.0
            if 1.0 / 365 <= T <= max_dte / 365:
                f = smile_fit(pts, S, T)
                if f is not None:
                    fits[e] = f
        out[d] = {"S": S, "fits": fits}
    return out


def _dte(day: str, e: str) -> float:
    return (expiry_ms(e) - _ms(day + "T08:00:00+00:00")) / DAY_MS


# ======================================================================================== T-257 RR skew harvest ==

def rr_at(fit: dict) -> Optional[tuple]:
    """(RR = call IV - put IV, (K_call, IV_call), (K_put, IV_put)) at 25 delta; cached on the fit."""
    if "_rr" not in fit:
        c = delta_strike(fit, 0.25, "call")
        p = delta_strike(fit, -0.25, "put")
        fit["_rr"] = None if c is None or p is None else (c[1] - p[1], c, p)
    return fit["_rr"]


def rr30(sm: dict, day: str, target: float = 30.0) -> Optional[float]:
    """25-delta RR (call IV - put IV) at ``target`` DTE, linear in DTE between the nearest expiries on either side."""
    pts = []
    for e, f in sm["fits"].items():
        r = rr_at(f)
        if r is not None:
            pts.append((_dte(day, e), r[0]))
    below = [p for p in pts if p[0] <= target]
    above = [p for p in pts if p[0] >= target]
    if not below or not above:
        return None
    (d1, r1), (d2, r2) = max(below), min(above)
    return r1 if d2 == d1 else r1 + (r2 - r1) * (target - d1) / (d2 - d1)


def rr_trade(day: str, smiles: dict, settle: dict, rr: float, iv_scale: float = 1.0, slip: float = 0.0,
             fees: bool = False, dte_band: tuple = (21.0, 45.0), hold: int = T257_HOLD) -> Optional[dict]:
    """Delta-hedged 25-delta risk reversal selling the richer wing (short call / long put when RR > 0), in the listed
    expiry nearest 30 DTE, priced by Black-Scholes at the fitted IVs (USD per 1-coin legs), hedged once a day at the
    sample index with deltas at that day's fitted IV of each strike. The claim's 30-day P&L: held ``hold`` calendar days
    and re-marked at that day's fitted smile of the expiry (the latest smile day in hold-2..hold with a fit; slippage
    and taker fees on the close), or, when the expiry falls within the hold, settled at its delivery price. The hold
    never exceeds ``hold`` days. Returns {pnl (/ entry S), exit day} or None."""
    sm = smiles[day]
    last = _add(day, hold)
    cands = []
    for e, f in sm["fits"].items():
        dte = _dte(day, e)
        if dte_band[0] <= dte <= dte_band[1] and (e in settle or e > last):
            r = rr_at(f)
            if r is not None:
                cands.append((abs(dte - 30.0), -dte, e, r))
    if not cands:
        return None
    _, _, e, (_, (Kc, ivc), (Kp, ivp)) = min(cands)
    x = e if e <= last else next((d for d in (_add(day, k) for k in range(hold, hold - 3, -1))
                                  if d in smiles and e in smiles[d]["fits"]), None)
    if x is None:
        return None
    S0 = sm["S"]
    sc = -1.0 if rr > 0 else 1.0                      # short the call wing when calls are rich
    legs = [("call", Kc, ivc * iv_scale, sc), ("put", Kp, ivp * iv_scale, -sc)]
    T0 = _dte(day, e) / 365.0
    prem = 0.0
    fee = 0.0
    for kind, K, iv, sg in legs:
        ivx = iv - slip if sg < 0 else iv + slip         # 1-vol-point slippage against us
        p = bs_price(S0, K, T0, max(ivx, 0.01), kind)
        prem += sg * p
        if fees:
            fee += min(OPT_TAKER * S0, OPT_CAP * p)
    hedge, S_prev = 0.0, S0
    pos = -sum(sg * bs_delta(S0, K, T0, iv, kind) for kind, K, iv, sg in legs)
    cur_iv = {kind: iv for kind, K, iv, sg in legs}
    d = _add(day, 1)
    while d < x:
        s = smiles.get(d)
        if s is not None:
            St = s["S"]
            hedge += pos * (St - S_prev)
            S_prev = St
            f = s["fits"].get(e)
            Tt = _dte(d, e) / 365.0
            for kind, K, iv, sg in legs:
                if f is not None:
                    cur_iv[kind] = smile_iv(f, K, St) * iv_scale
            pos = -sum(sg * bs_delta(St, K, Tt, cur_iv[kind], kind) for kind, K, iv, sg in legs)
        d = _add(d, 1)
    if x == e:                                       # the expiry falls within the hold: delivery-price settlement
        ST = settle[e]
        hedge += pos * (ST - S_prev)
        pay = sum(sg * (max(ST - K, 0.0) if kind == "call" else max(K - ST, 0.0)) for kind, K, iv, sg in legs)
        if fees:
            fee += sum(min(OPT_DELIVERY * ST, OPT_CAP * (max(ST - K, 0.0) if kind == "call" else max(K - ST, 0.0)))
                       for kind, K, iv, sg in legs)
    else:                                            # re-marked on day x at that day's fitted smile, closed as taker
        s = smiles[x]
        Sx, f, Tx = s["S"], s["fits"][e], _dte(x, e) / 365.0
        hedge += pos * (Sx - S_prev)
        pay = 0.0
        for kind, K, iv, sg in legs:
            ivx = smile_iv(f, K, Sx) * iv_scale
            p = bs_price(Sx, K, Tx, max(ivx + slip if sg < 0 else ivx - slip, 0.01), kind)
            pay += sg * p
            if fees:
                fee += min(OPT_TAKER * Sx, OPT_CAP * p)
    pnl = pay - prem + hedge - fee
    return {"day": day, "exit": x, "expiry": e, "pnl": pnl / S0, "rr": rr, "short": "call" if sc < 0 else "put"}


def signal_trades(smiles: dict, settle: dict, start: str = CLAIM_START, end: str = CLAIM_END, thr: float = T257_THR,
                  **kw) -> list[dict]:
    out = []
    for d in sorted(smiles):
        if not (start <= d <= end):
            continue
        r = rr30(smiles[d], d)
        if r is None or abs(r) <= thr:
            continue
        t = rr_trade(d, smiles, settle, r, **kw)
        if t is not None:
            out.append(t)
    return out


def judge_pooled(trades: list[dict], hold: int, min_n: int, hit_thr: Optional[float], n_boot: Optional[int] = None,
                 unit: str = "non-overlapping entries") -> tuple:
    """Pooled all-signal-day estimate (rule 10): mean P&L CI > 0 (blocks of 2 x hold days on the daily timeline, the hold
    being the longer of ``hold`` and the longest actual entry-to-exit span) and, when ``hit_thr`` is set, hit rate >
    hit_thr. n = greedy non-overlapping count; the per-start range runs over as many offsets as that hold."""
    if not trades:
        v, why = _decide([("signal entries", None, False)], 0, min_n, unit)
        return v, why, {"n": 0, "entries": 0}
    days = [t["day"] for t in trades]
    x = np.array([t["pnl"] for t in trades])
    g = _greedy(days, [t["exit"] for t in trades])
    n = len(g)
    held = max((date.fromisoformat(t["exit"]) - date.fromisoformat(t["day"])).days for t in trades)
    hold = max(int(hold), int(held))
    lo, hi = timeline_mean_ci(days, x, 2 * hold, n_boot)
    hit = float((x > 0).mean())
    crit = [(f"pooled mean P&L 95% CI > 0 (mean {_f(float(x.mean()), 2, True, True)} of S over {len(x)} signal-day entries, "
             f"CI {_ci((lo, hi), 2, True)}, {2 * hold}-day blocks)", None if lo is None else lo > 0, hi is not None and hi <= 0)]
    if hit_thr is not None:
        gw = int((x[g] > 0).sum())
        crit.append((f"hit rate > {hit_thr:.0%} (pooled {hit:.0%}; non-overlapping {gw} of {n})", hit > hit_thr,
                     (gw + max(min_n - n, 0)) / max(min_n, n) <= hit_thr))
    v, why = _decide(crit, n, min_n, unit)
    return v, why, {"n": n, "entries": int(len(x)), "mean": float(x.mean()), "ci": [lo, hi], "hit": hit, "hold": hold,
                    "longest_hold": int(held), "block": 2 * hold, "nonoverlap_mean": float(x[g].mean()),
                    "per_start": _per_start(days, [t["exit"] for t in trades], x, hold)}


def rr_claim(smiles: dict, settle: dict, n_boot: Optional[int] = None) -> dict:
    tr = signal_trades(smiles, settle)
    verdict, why, det = judge_pooled(tr, T257_HOLD, T257_MIN_N, 0.55, n_boot)
    n = det["n"]
    days_in = [d for d in smiles if CLAIM_START <= d <= CLAIM_END]
    ctl = {}
    if tr:
        net = signal_trades(smiles, settle, slip=0.01, fees=True)
        ctl["fees + 1 vol point slippage per leg"] = float(np.mean([t["pnl"] for t in net])) if net else None
        for s in (0.9, 1.1):
            z = signal_trades(smiles, settle, iv_scale=s)
            ctl[f"IV x{s}"] = float(np.mean([t["pnl"] for t in z])) if z else None
        rng = np.random.default_rng(SEED)
        pool = [d for d in days_in if rr30(smiles[d], d) is not None]
        pick = sorted(rng.choice(pool, size=min(len(tr), len(pool)), replace=False)) if pool else []
        rnd = [rr_trade(d, smiles, settle, 1.0 if rng.random() < 0.5 else -1.0) for d in pick]
        rnd = [t for t in rnd if t is not None]
        ctl["random entry days, random wing"] = float(np.mean([t["pnl"] for t in rnd])) if rnd else None
    stat = {"label": MP, "n": n, "min_n": T257_MIN_N, "smile_days": len(days_in), "judge": det, "controls": ctl,
            "short_call_entries": sum(t["short"] == "call" for t in tr), "short_put_entries": sum(t["short"] == "put" for t in tr)}
    ps = det.get("per_start") or {}
    reason = (
        f"T-257 {MP} at trade-fitted IVs: daily BTC smiles from the 07:00-09:00 UTC trade sample "
        f"({DAILY_TRADES_B}; quadratic in ln(K/S)/sqrt(T) per expiry, S = median sample index), 25-delta RR (call IV - put "
        f"IV) interpolated to 30 DTE between the bracketing expiries; on every day {CLAIM_START}..{CLAIM_END} with |RR30| > 5 "
        f"vol points, sell the richer 25-delta wing and buy the other in the listed expiry nearest 30 DTE (21-45), "
        f"Black-Scholes at the fitted IVs, delta-hedged once a day at the sample index (the 'close'); the claim's 30-day "
        f"P&L: held {T257_HOLD} calendar days and re-marked at that day's fitted smile of the expiry (the latest smile day "
        f"in days {T257_HOLD - 2}-{T257_HOLD} with a fit; slippage and fees on the close), an expiry inside the hold settled "
        f"at the Deribit delivery price. {len(days_in)} smile days, {det.get('entries', 0)} signal-day entries "
        f"({stat['short_call_entries']} short call, {stat['short_put_entries']} short put); pooled mean "
        f"{_f(det.get('mean'), 2, True, True)} of S, 95% CI {_ci(det.get('ci'), 2, True)} ({det.get('block', 2 * T257_HOLD)}-day "
        f"blocks, twice the longest hold of {det.get('longest_hold')} days), hit "
        f"rate {_f(det.get('hit'), 2)}; n = {n} non-overlapping entries (per-start range over {ps.get('offsets', 0)} offsets: "
        f"n {ps.get('n_min')}-{ps.get('n_max')}, mean {_f(ps.get('mean_min'), 2, True, True)} to "
        f"{_f(ps.get('mean_max'), 2, True, True)}). Controls: " + "; ".join(f"{k} {_f(v, 2, True, True)}" for k, v in ctl.items()))
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason + f" — {why}"}


def _daily_inputs(archive):
    return _cached(archive, ("daily_smiles",), lambda: daily_smiles([r["value"] for r in _rows(archive, DAILY_TRADES_B)
                                                                     if r.get("kind", "option-trade") == "option-trade"]))


def b6b_drb_rr_skew_harvest(archive):
    """T-257: delta-hedged 30-day 25-delta BTC risk reversal selling the richer wing when |RR25| > 5 vol points, 2022-2026."""
    miss = _missing(archive, [DAILY_TRADES_B, DELIV_B])
    if miss:
        return miss
    return _out(rr_claim(_daily_inputs(archive), _delivery(archive)))


# =================================================================================== T-262 calendar on inversion ==

def calendar_trade(day: str, smiles: dict, settle: dict, slip: float = 0.0, iv_scale: float = 1.0,
                   hold: int = T262_HOLD, thr: float = T262_THR) -> Optional[dict]:
    """Long ATM call calendar (buy the ~90-DTE call, sell the 7-30 DTE call, same strike) entered when the front ATM IV
    exceeds the back by more than ``thr``; front = the 7-30 DTE expiry with the most sample prints, back = the 60-120
    DTE expiry nearest 90; K = the front's printed strike nearest S. Re-marked ``hold`` days later (first smile day in
    hold..hold+2) at each leg's own fitted IV; a front that expired by then is worth its settlement intrinsic."""
    sm = smiles[day]
    S = sm["S"]
    fr = [(f["n"], _dte(day, e), e) for e, f in sm["fits"].items() if 7 <= _dte(day, e) <= 30]
    bk = [(abs(_dte(day, e) - 90), e) for e, f in sm["fits"].items() if 60 <= _dte(day, e) <= 120]
    if not fr or not bk:
        return None
    ef = max(fr)[2]
    eb = min(bk)[1]
    ff, fb = sm["fits"][ef], sm["fits"][eb]
    inv = smile_iv(ff, S) - smile_iv(fb, S)
    if inv <= thr:
        return None
    K = min(ff["strikes"], key=lambda k: abs(k - S))
    Tf, Tb = _dte(day, ef) / 365, _dte(day, eb) / 365
    cf0 = bs_price(S, K, Tf, max(smile_iv(ff, K) * iv_scale - slip, 0.01), "call")
    cb0 = bs_price(S, K, Tb, smile_iv(fb, K) * iv_scale + slip, "call")
    x = None
    for k in range(hold, hold + 3):
        d = _add(day, k)
        if d in smiles and eb in smiles[d]["fits"]:
            x = d
            break
    if x is None:
        return None
    s2 = smiles[x]
    S2 = s2["S"]
    if ef <= x:
        if ef not in settle:
            return None
        vf = max(settle[ef] - K, 0.0)
    else:
        f2 = s2["fits"].get(ef)
        if f2 is None:
            return None
        vf = bs_price(S2, K, _dte(x, ef) / 365, max(smile_iv(f2, K, S2) * iv_scale + slip, 0.01), "call")
    vb = bs_price(S2, K, _dte(x, eb) / 365, max(smile_iv(s2["fits"][eb], K, S2) * iv_scale - slip, 0.01), "call")
    pnl = (vb - vf) - (cb0 - cf0)
    return {"day": day, "exit": x, "pnl": pnl / S, "inversion": inv, "front": ef, "back": eb, "debit": (cb0 - cf0) / S}


def calendar_claim(smiles: dict, settle: dict, n_boot: Optional[int] = None) -> dict:
    def run(**kw):
        return [t for t in (calendar_trade(d, smiles, settle, **kw) for d in sorted(smiles) if CLAIM_START <= d <= CLAIM_END)
                if t is not None]
    tr = run()
    verdict, why, det = judge_pooled(tr, T262_HOLD, T262_MIN_N, None, n_boot)
    n = det["n"]
    ctl = {}
    if tr:
        z = run(slip=0.01)
        ctl["1 vol point slippage per leg"] = float(np.mean([t["pnl"] for t in z])) if z else None
        for s in (0.9, 1.1):
            z = run(iv_scale=s)
            ctl[f"IV x{s}"] = float(np.mean([t["pnl"] for t in z])) if z else None
        z = [t for t in (calendar_trade(d, smiles, settle, thr=-1.0) for d in sorted(smiles) if CLAIM_START <= d <= CLAIM_END)
             if t is not None]
        ctl["every day (no inversion gate)"] = float(np.mean([t["pnl"] for t in z])) if z else None
    stat = {"label": MP, "n": n, "min_n": T262_MIN_N, "judge": det, "controls": ctl,
            "smile_days": sum(CLAIM_START <= d <= CLAIM_END for d in smiles)}
    ps = det.get("per_start") or {}
    reason = (
        f"T-262 {MP} at trade-fitted IVs: daily BTC smiles from the 07:00-09:00 UTC trade sample ({DAILY_TRADES_B}); ATM "
        f"IV = smile at K = S. On every day {CLAIM_START}..{CLAIM_END} with front (7-30 DTE, most prints) ATM IV above back "
        f"(60-120 DTE, nearest 90) by more than 5 vol points: buy the back ATM call, sell the front, same strike, Black-Scholes "
        f"at each leg's fitted IV; re-marked 14 days later at that day's fitted IVs (a front expired by then at its "
        f"delivery intrinsic). {det.get('entries', 0)} signal-day entries, pooled mean {_f(det.get('mean'), 2, True, True)} "
        f"of S, 95% CI {_ci(det.get('ci'), 2, True)} ({det.get('block', 2 * T262_HOLD)}-day blocks), hit rate {_f(det.get('hit'), 2)}; n = {n} "
        f"non-overlapping 14-day holds (per-start range over {ps.get('offsets', 0)} offsets: n {ps.get('n_min')}-"
        f"{ps.get('n_max')}, mean {_f(ps.get('mean_min'), 2, True, True)} to {_f(ps.get('mean_max'), 2, True, True)}). "
        f"Controls: " + "; ".join(f"{k} {_f(v, 2, True, True)}" for k, v in ctl.items())
        + "; SPY VIX/VIX3M analogue not run here")
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason + f" — {why}"}


def b6b_drb_calendar_inversion(archive):
    """T-262: long ATM BTC call calendar (7-30 / ~90 DTE) when front IV exceeds back by > 5 vol points, held 14 days."""
    miss = _missing(archive, [DAILY_TRADES_B, DELIV_B])
    if miss:
        return miss
    return _out(calendar_claim(_daily_inputs(archive), _delivery(archive)))


# ======================================================================================= T-263 FOMC implied move ==

def fomc_inputs(rows: Sequence[dict]) -> tuple:
    wins, trades = {}, defaultdict(list)
    for r in rows:
        v = r["value"]
        if r.get("kind") == "fomc-window":
            wins[f"{v['decision_day']}:{v.get('currency', 'BTC')}"] = {**v, "available_at": r.get("available_at")}
        elif r.get("kind") == "option-trade":
            try:
                v["_ts"] = int(v["timestamp"])
            except (TypeError, ValueError, KeyError):
                continue
            trades[f"{v.get('decision_day')}:{v.get('currency', 'BTC')}"].append(v)
    for k in trades:
        trades[k].sort(key=lambda t: t["_ts"])
    return wins, dict(trades)


def fomc_move(w: dict, trades: Sequence[dict], settle: dict, use: str = "mark_price") -> Optional[dict]:
    """ATM straddle-implied move from the last call and put prints at the strike nearest the index among strikes with
    both printed in the 24 h before the decision (first expiry after it), vs the realised |move| from the index at that
    measurement to the expiry's 08:00 UTC delivery price."""
    tau = _ms(w["decision_time"])
    exp = w.get("target_expiry")
    if not exp or exp[:10] not in settle:
        return None
    last, S = _snapshot(trades, tau)
    if not S:
        return None
    by = defaultdict(dict)
    for t in last.values():
        try:
            by[float(t["strike"])][t["type"]] = t
        except (TypeError, ValueError, KeyError):
            continue
    both = [k for k, v in by.items() if "call" in v and "put" in v]
    if not both:
        return None
    K = min(both, key=lambda k: abs(k - S))
    c, p = by[K]["call"], by[K]["put"]
    try:
        usd = float(c[use]) * float(c["index_price"]) + float(p[use]) * float(p["index_price"])
        ts = max(c["_ts"], p["_ts"])
        Sref = float((c if c["_ts"] >= p["_ts"] else p)["index_price"])
    except (TypeError, ValueError, KeyError):
        return None
    implied = usd / Sref
    realised = abs(settle[exp[:10]] / Sref - 1.0)
    return {"decision": w["decision_day"], "strike": K, "implied": implied, "realised": realised,
            "diff": implied - realised, "measured_at": _iso(ts), "expiry": exp[:10], "hours_to_expiry": (expiry_ms(exp) - ts) / HOUR_MS}


def judge_mean_ci(x, min_n: int, unit: str, label: str, n_boot: Optional[int] = None, block: int = 1, pct: bool = True) -> tuple:
    x = np.asarray(x, float)
    n = int(x.size)
    if n < 2:
        v, why = _decide([(label + " computable", None, False)], n, min_n, unit)
        return v, why, {"n": n}
    lo, hi = mean_ci(x, block, n_boot)
    fmt = (lambda z: _f(z, 2, True, True)) if pct else (lambda z: _f(z, 2, sign=True))
    crit = [(f"{label} > 0 with 95% CI excluding 0 (mean {fmt(float(x.mean()))}, CI [{fmt(lo)}, {fmt(hi)}])",
             bool(x.mean() > 0 and lo > 0), hi <= 0)]
    v, why = _decide(crit, n, min_n, unit)
    k = int((x > 0).sum())
    return v, why, {"n": n, "mean": float(x.mean()), "ci": [lo, hi], "hit": k / n, "sign_p_one": sign_test(k, n)[0]}


def dvol_fomc_control(dvol: dict, decisions: Sequence[str]) -> dict:
    """DVOL change from the close before the decision day to the decision day's close (reported control)."""
    ch = []
    for d in decisions:
        a, b = dvol.get(_add(d, -1)), dvol.get(d)
        if a is not None and b is not None:
            ch.append(b - a)
    if not ch:
        return {"n": 0}
    x = np.array(ch)
    return {"n": int(x.size), "mean": float(x.mean()), "falls": int((x < 0).sum()), "ci": list(mean_ci(x, 1))}


def fomc_claim(wins: dict, trades: dict, settle: dict, dvol_ctl: dict, n_boot: Optional[int] = None) -> dict:
    keys = sorted(k for k in wins if "2022-01-01" <= wins[k]["decision_day"] <= CLAIM_END)
    moves = [m for m in (fomc_move(wins[k], trades.get(k, []), settle) for k in keys) if m is not None]
    verdict, why, det = judge_mean_ci([m["diff"] for m in moves], T263_MIN_N, "decisions", "mean implied - realised move", n_boot)
    tp = [m for m in (fomc_move(wins[k], trades.get(k, []), settle, use="price") for k in keys) if m is not None]
    stat = {"n": det["n"], "min_n": T263_MIN_N, "judge": det, "moves": moves, "trade_price_mean_diff":
            float(np.mean([m["diff"] for m in tp])) if tp else None, "dvol_control": dvol_ctl}
    reason = (
        f"T-263 on Deribit trade prints ({FOMC_TRADES_B}): for each FOMC decision {CLAIM_START[:4]}-2026, the ATM straddle "
        f"(strike nearest the index with both legs printed in the 24 h before the decision, first expiry after it; Deribit "
        f"mark at the last print x index) over the index = implied move; realised = |delivery price at that expiry's 08:00 UTC "
        f"/ index at the measurement - 1|. {det['n']} decisions with prints of {len(keys)} windows; mean implied - realised "
        f"{_f(det.get('mean'), 2, True, True)}, 95% iid bootstrap CI {_ci(det.get('ci'), 2, True)}, hit rate "
        f"{_f(det.get('hit'), 2)}, sign p {_f(det.get('sign_p_one'), 3)}; at trade prices {_f(stat['trade_price_mean_diff'], 2, True, True)}. "
        f"Control (archived now): BTC DVOL change over the decision day {_f(dvol_ctl.get('mean'), 2, sign=True)} vol points "
        f"over {dvol_ctl.get('n', 0)} decisions ({dvol_ctl.get('falls', 0)} falls)")
    return {"stat": stat, "n": det["n"], "verdict": verdict, "reason": reason + f" — {why}"}


def b6b_drb_fomc_event_straddle(archive):
    """T-263: BTC ATM straddle-implied move before FOMC decisions vs the realised move to the first post-decision expiry."""
    ctl = {}
    if _has(archive, DVOL_B["BTC"]) and _has(archive, FOMC_B):
        ctl = dvol_fomc_control(_dvol(archive, "BTC"), [d for d in _fomc_days(archive) if "2022-01-01" <= d <= CLAIM_END])
    miss = _missing(archive, [FOMC_TRADES_B, DELIV_B])
    if miss:
        stat, n, v, why = miss
        stat["dvol_control"] = ctl
        return (_clean(stat), n, v, why.replace(" — ", f". Control (archived now): BTC DVOL change over the decision day "
                                                       f"{_f(ctl.get('mean'), 2, sign=True)} vol points, 95% CI "
                                                       f"{_ci(ctl.get('ci'), 2)}, over {ctl.get('n', 0)} decisions 2022-2026 "
                                                       f"({ctl.get('falls', 0)} falls) — ", 1))
    wins, trades = _cached(archive, ("fomc_trades",), lambda: fomc_inputs(_rows(archive, FOMC_TRADES_B)))
    return _out(fomc_claim(wins, trades, _delivery(archive), ctl))


# ==================================================================================== T-268 DVOL futures basis ==

def dvolf_inputs(rows: Sequence[dict]) -> tuple:
    trades, settle = defaultdict(list), {}
    for r in rows:
        v = r["value"]
        if r.get("kind") == "future-trade":
            try:
                v["_ts"] = int(v["timestamp"])
            except (TypeError, ValueError, KeyError):
                continue
            trades[v["instrument_name"]].append(v)
        elif r.get("kind") == "future-settlement":
            try:
                settle[v["instrument_name"]] = float(v["delivery_price"])
            except (TypeError, ValueError, KeyError):
                continue
    for k in trades:
        trades[k].sort(key=lambda t: t["_ts"])
    return dict(trades), settle


def dvolf_points(trades: dict, settle: dict, lead_days: float = 7.0, tol_h: float = 24.0) -> tuple:
    """Per expired instrument: the mark of the trade nearest expiry - 7 d (within +-24 h) minus the settlement DVOL (the
    delivery price; else the DVOL index_price of the last trade within 6 h before expiry). Returns (points, dropped)."""
    pts, drop = [], []
    for inst, ts in sorted(trades.items()):
        if not ts:
            continue
        exp = _ms(ts[0]["expiry"]) if len(str(ts[0].get("expiry", ""))) > 10 else expiry_ms(str(ts[0].get("expiry")))
        tgt = exp - int(lead_days * DAY_MS)
        near = min(ts, key=lambda t: abs(t["_ts"] - tgt))
        if abs(near["_ts"] - tgt) > tol_h * HOUR_MS:
            drop.append((inst, "no trade within 24 h of T-7d"))
            continue
        s = settle.get(inst)
        how = "delivery price"
        if s is None:
            late = [t for t in ts if exp - 6 * HOUR_MS <= t["_ts"] <= exp]
            if late:
                s, how = float(late[-1]["index_price"]), "index at the last trade before expiry"
        if s is None:
            drop.append((inst, "no settlement"))
            continue
        try:
            F = float(near["mark_price"])
            pts.append({"instrument": inst, "expiry": _iso(exp), "F_T7": F, "settle": s, "diff": F - s, "settle_how": how,
                        "lag_h": (near["_ts"] - tgt) / HOUR_MS, "index_at_T7": float(near.get("index_price") or float("nan")),
                        "trade_minus_mark": float(near["price"]) - F})
        except (TypeError, ValueError, KeyError):
            drop.append((inst, "unparseable trade"))
    pts.sort(key=lambda p: p["expiry"])
    return pts, drop


def dvolf_claim(pts: list[dict], drop: list, n_boot: Optional[int] = None) -> dict:
    v, why, det = judge_mean_ci([p["diff"] for p in pts], T268_MIN_N, "expiries", "mean (F at T-7d - settlement DVOL)",
                                n_boot, pct=False)
    stat = {"n": det["n"], "min_n": T268_MIN_N, "judge": det, "points": pts, "dropped": drop,
            "target_2_vol_points_met": bool(det.get("mean") is not None and det["mean"] > 2.0),
            "median_abs_trade_minus_mark": float(np.median([abs(p["trade_minus_mark"]) for p in pts])) if pts else None}
    reason = (
        f"T-268 on BTCDVOL_USDC futures trades ({DVOLF_B}): mark of the trade nearest expiry - 7 d (within 24 h) minus the "
        f"DVOL settlement, {det['n']} expiries"
        + (f" {pts[0]['expiry'][:10]}..{pts[-1]['expiry'][:10]}" if pts else "")
        + f"; mean {_f(det.get('mean'), 2, sign=True)} vol points (target > 2 reported: {stat['target_2_vol_points_met']}), "
        f"95% iid bootstrap CI {_ci(det.get('ci'), 2)}, positive in {_f(det.get('hit'), 2)} of expiries; median |trade - "
        f"mark| {_f(stat['median_abs_trade_minus_mark'], 2)}" + (f"; dropped {drop}" if drop else ""))
    return {"stat": stat, "n": det["n"], "verdict": v, "reason": reason + f" — {why}"}


def b6b_drb_dvol_futures_basis(archive):
    """T-268: BTCDVOL futures mark 7 days before expiry minus DVOL at settlement, across expired futures."""
    miss = _missing(archive, [DVOLF_B])
    if miss:
        return miss
    trades, settle = dvolf_inputs(_rows(archive, DVOLF_B))
    pts, drop = dvolf_points(trades, settle)
    return _out(dvolf_claim(pts, drop))


# ============================================================================ book snapshots (T-195/196/260) ==

def book_snapshots(archive, index: Optional[dict] = None) -> tuple:
    """Snapshots from the declared hourly bundle (grouped by capture_ts) and from the daily deribit-book-BTC-<date>
    captures. Each: {ts, source, options: [{code, expiry, strike, type, bid, ask, mark, underlying, underlying_index,
    index_price, oi}], futures: {code: {bid, ask, mark}}, S}. The daily captures without index_price take the Deribit
    index of the last full hour before the capture (funding history)."""
    snaps = []
    names = []
    if _has(archive, HOURLY_BOOK_B):
        by = defaultdict(lambda: {"options": [], "futures": {}})
        for r in _rows(archive, HOURLY_BOOK_B):
            v = r["value"]
            ts = v.get("capture_ts") or r.get("available_at")
            if not ts:
                continue
            s = by[ts]
            code = str(v.get("expiry") or "")
            if r.get("kind") == "future":
                s["futures"][code] = {k: v.get(k) for k in ("bid", "ask", "mark", "index_price")}
            elif r.get("kind", "option") == "option":
                s["options"].append({**v, "code": code})
        for ts, s in by.items():
            snaps.append({"ts": _ms(ts), "source": HOURLY_BOOK_B, **s})
        names.append(HOURLY_BOOK_B)
    for nm in _dated(archive, BOOK_PREFIX):
        rows = _rows(archive, nm)
        if not rows:
            continue
        ts = max(r.get("observed_at") or r.get("available_at") for r in rows)
        snaps.append({"ts": _ms(ts), "source": nm, "options": [{**r["value"], "code": str(r["value"].get("expiry"))} for r in rows],
                      "futures": {}})
        names.append(nm)
    for s in snaps:
        S = None
        for o in s["options"]:
            if o.get("index_price"):
                S = float(o["index_price"])
                break
        if S is None:
            for f in s["futures"].values():
                if f.get("index_price"):
                    S = float(f["index_price"])
                    break
        if S is None and index:
            h = s["ts"] - s["ts"] % HOUR_MS
            S = index.get(h)
        s["S"] = S
    snaps.sort(key=lambda s: s["ts"])
    return snaps, names


def _q(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f > 0 and math.isfinite(f) else None


def _expiry_forward(s: dict, code: str) -> Optional[float]:
    f = s["futures"].get(code) or s["futures"].get(f"BTC-{code}")
    if f and _q(f.get("mark")):
        return _q(f["mark"])
    us = [_q(o.get("underlying")) for o in s["options"] if o["code"] == code]
    us = [u for u in us if u]
    return float(np.median(us)) if us else None


def _pairs(s: dict, code: str) -> dict:
    by = defaultdict(dict)
    for o in s["options"]:
        if o["code"] == code:
            try:
                by[float(o["strike"])][o["type"]] = o
            except (TypeError, ValueError, KeyError):
                continue
    return {k: v for k, v in by.items() if "call" in v and "put" in v}


def listed_future_codes(s: dict, quarterly_names: Optional[set] = None) -> set:
    """Expiry codes of the snapshot whose options reference a listed dated future (the trial: 'keep expiries whose
    underlying_index is a listed future (not SYN.)'): option rows whose underlying_index is BTC-<code>, futures rows of
    the snapshot and the archived quarterly futures; an option row whose underlying_index starts with 'SYN.' is never
    one."""
    codes = {o["code"] for o in s["options"]}
    syn = {o["code"] for o in s["options"] if str(o.get("underlying_index") or "").startswith("SYN.")}
    fut = {c.replace("BTC-", "") for c in s["futures"]}
    fut |= {c for c in codes if f"BTC-{c}" in (quarterly_names or set())}
    fut |= {o["code"] for o in s["options"] if str(o.get("underlying_index") or "") == f"BTC-{o['code']}"}
    return (codes & fut) - syn


def parity_obs(s: dict, codes: set) -> list[dict]:
    """T-195 observations of one snapshot: per (K, expiry) with two-sided call and put quotes, strikes within 10% of F,
    DTE 7-180: deviation |F_impl - F|/F at mids (F_impl = K / (1 - (C_mid - P_mid))) against the round-trip taker fees of
    the call, the put and the future; the executable reading uses bid/ask."""
    out = []
    S = s.get("S")
    for code in sorted(codes):
        e = code_date(code)
        if not e:
            continue
        dte = (expiry_ms(e) - s["ts"]) / DAY_MS
        if not (T195_DTE[0] <= dte <= T195_DTE[1]):
            continue
        F = _expiry_forward(s, code)
        if not F:
            continue
        fut = s["futures"].get(code) or s["futures"].get(f"BTC-{code}") or {}
        for K, legs in sorted(_pairs(s, code).items()):
            if abs(K / F - 1) > T195_MNY:
                continue
            c, p = legs["call"], legs["put"]
            cb, ca, pb, pa = _q(c.get("bid")), _q(c.get("ask")), _q(p.get("bid")), _q(p.get("ask"))
            if None in (cb, ca, pb, pa):
                continue
            cm, pm = (cb + ca) / 2, (pb + pa) / 2
            den = 1 - (cm - pm)
            if den <= 0:
                continue
            Fi = K / den
            scale = (S / F) if S else 1.0
            thr = 2 * (option_fee(cm) + option_fee(pm)) * scale + 2 * FUT_TAKER
            dev = abs(Fi - F) / F
            fa, fb = _q(fut.get("ask")) or F, _q(fut.get("bid")) or F
            sell_syn = K / (1 - (cb - pa)) if 1 - (cb - pa) > 0 else float("nan")
            buy_syn = K / (1 - (ca - pb)) if 1 - (ca - pb) > 0 else float("nan")
            ex = max((sell_syn - fa) / F, (fb - buy_syn) / F)
            out.append({"ts": s["ts"], "code": code, "K": K, "dte": dte, "F": F, "F_impl": Fi, "dev": dev, "thr": thr,
                        "exceed": dev > thr, "exec_edge": ex, "exec_exceed": bool(ex > thr)})
    return out


def persistence_hours(obs: list[dict]) -> Optional[float]:
    """Longest run (hours between first and last snapshot) of a (K, expiry) violation across consecutive hourly
    snapshots (50-70 minutes apart); None when no two snapshots are an hour apart."""
    ts = sorted({o["ts"] for o in obs})
    nxt = {a: b for a, b in zip(ts[:-1], ts[1:]) if 50 * 60_000 <= b - a <= 70 * 60_000}
    if not nxt:
        return None
    viol = {(o["ts"], o["code"], o["K"]) for o in obs if o["exceed"]}
    best = 0.0
    for t0, code, K in viol:
        prev = [a for a, b in nxt.items() if b == t0]
        if prev and (prev[0], code, K) in viol:
            continue
        t = t0
        while t in nxt and (nxt[t], code, K) in viol:
            t = nxt[t]
        best = max(best, (t - t0) / HOUR_MS)
    return best


def cluster_rate_ci(obs: list[dict], key: str = "exceed", n_boot: Optional[int] = None, seed: int = SEED) -> tuple:
    """Upper 95% bound of a rate by resampling UTC capture days (clusters); None with fewer than 3 days."""
    n_boot = _nb(n_boot)
    by = defaultdict(list)
    for o in obs:
        by[_dday(o["ts"])].append(bool(o[key]))
    days = sorted(by)
    if len(days) < 3:
        return None
    k = np.array([sum(by[d]) for d in days], float)
    n = np.array([len(by[d]) for d in days], float)
    rng = np.random.default_rng(seed)
    ii = rng.integers(0, len(days), size=(n_boot, len(days)))
    r = k[ii].sum(axis=1) / n[ii].sum(axis=1)
    return float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))


def judge_parity(obs: list[dict], min_n: int = T195_MIN_N, n_boot: Optional[int] = None) -> tuple:
    n = len(obs)
    if n == 0:
        v, why = _decide([("parity observations", None, False)], 0, min_n, "hourly (K, T) observations")
        return v, why, {"n": 0}
    k = sum(o["exceed"] for o in obs)
    rate = k / n
    cl = cluster_rate_ci(obs, n_boot=n_boot)
    cp = clopper_pearson(k, n)
    lo, hi = (cl if cl is not None else cp)
    how = "day-cluster bootstrap" if cl is not None else "exact binomial, iid (fewer than 3 capture days)"
    per = persistence_hours(obs)
    crit = [(f"exceedance rate < 1% ({k} of {n} = {rate:.2%})", rate < 0.01, lo is not None and lo >= 0.01),
            (f"95% upper bound < 1% ({hi:.2%}, {how})", hi < 0.01, lo is not None and lo >= 0.01),
            ("no violation persisting > 1 hour" + (f" (longest {per:.1f} h)" if per is not None else
                                                     " (not implementable: no two snapshots an hour apart)"),
             None if per is None else per <= 1.0 + 1e-9, per is not None and per > 1.0)]
    v, why = _decide(crit, n, min_n, "hourly (K, T) observations")
    devs = np.array([o["dev"] for o in obs])
    return v, why, {"n": n, "exceed": int(k), "rate": rate, "ci": [lo, hi], "ci_how": how, "persistence_h": per,
                    "p99_bp": float(np.quantile(devs, 0.99) * 1e4), "median_bp": float(np.median(devs) * 1e4),
                    "median_thr_bp": float(np.median([o["thr"] for o in obs]) * 1e4),
                    "exec_rate": float(np.mean([o["exec_exceed"] for o in obs]))}


def parity_claim(snaps: list[dict], qnames: set, names: list, hourly: bool, n_boot: Optional[int] = None) -> dict:
    obs = [o for s in snaps for o in parity_obs(s, listed_future_codes(s, qnames))]
    v, why, det = judge_parity(obs, n_boot=n_boot)
    settle = [o for o in obs if not (7 * 60 <= (o["ts"] % DAY_MS) // 60_000 < 8 * 60 + 30)]
    stat = {"n": det["n"], "min_n": T195_MIN_N, "judge": det, "snapshots": len(snaps), "sources": names,
            "excluding_settlement_window_rate": float(np.mean([o["exceed"] for o in settle])) if settle else None,
            "expiries": sorted({o["code"] for o in obs})}
    miss = "" if hourly else (f" The claim's data ({HOURLY_BOOK_B}, hourly polls for 7 days) is not archived: {REQUESTS[HOURLY_BOOK_B]}."
                              f" These {len(snaps)} daily captures are partial evidence only.")
    reason = (
        f"T-195 put-call parity vs the listed dated future on {len(snaps)} Deribit BTC book snapshot(s) ({', '.join(names) or 'none'}): "
        f"expiries whose options reference a listed future ({', '.join(stat['expiries']) or 'none'}; an option underlying_index "
        f"BTC-<expiry>, a futures row of the snapshot or an archived quarterly in {QF_B}, never a SYN. underlying), strikes within 10% of F (the expiry's "
        f"underlying/future mark), DTE 7-180, two-sided quotes. |F_impl - F|/F at mids (F_impl = K/(1 - (C_mid - P_mid))) "
        f"vs round-trip taker fees of the three legs ({FEE_TXT}; median threshold {_f(det.get('median_thr_bp'), 1)} bp): "
        f"{det.get('exceed', 0)} of {det['n']} observations exceed ({_f(det.get('rate'), 2, True)}; 95% "
        f"{_ci(det.get('ci'), 2, True)} {det.get('ci_how', '')}); median deviation {_f(det.get('median_bp'), 1)} bp, 99th "
        f"percentile {_f(det.get('p99_bp'), 1)} bp; executable bid/ask exceedance {_f(det.get('exec_rate'), 2, True)}; "
        f"outside 07:00-08:30 UTC {_f(stat['excluding_settlement_window_rate'], 2, True)}; ETH replication not run." + miss)
    return {"stat": stat, "n": det["n"], "verdict": v, "reason": reason + f" — {why}"}


def _quarterly_names(archive) -> set:
    if not _has(archive, QF_B):
        return set()
    return _cached(archive, ("qnames",), lambda: {r["value"]["instrument"] for r in _rows(archive, QF_B)})


def b6b_drb_parity_violations(archive):
    """T-195: share of hourly (K, T) observations where the option-implied forward deviates from the future by more
    than round-trip taker fees."""
    snaps, names = book_snapshots(archive, _index_hourly(archive) if _has(archive, FUND_B) else None)
    if not snaps:
        return _missing(archive, [HOURLY_BOOK_B])
    return _out(parity_claim(snaps, _quarterly_names(archive), names, _has(archive, HOURLY_BOOK_B)))


# ---------------------------------------------------------------------------------------------------- boxes --

def box_rates(s: dict, code: str, pairs: Optional[list] = None, mny: float = T196_MNY) -> list[dict]:
    """Long-box USD rates of one expiry in one snapshot: for each strike pair (K1 < K2; all pairs with both strikes
    within ``mny`` of F, or the given pairs): executable debit = C1 ask - C2 bid + P2 ask - P1 bid plus taker fees on the
    four legs (coin), mid debit at mids; USD debit = coin x index; r = ln((K2 - K1) / debit_usd) / T."""
    e = code_date(code)
    S = s.get("S")
    F = _expiry_forward(s, code)
    if not e or not S or not F:
        return []
    T = (expiry_ms(e) - s["ts"]) / DAY_MS / 365.0
    if T <= 0:
        return []
    legs = _pairs(s, code)
    q = {}
    for K, v in legs.items():
        c, p = v["call"], v["put"]
        vals = (_q(c.get("bid")), _q(c.get("ask")), _q(p.get("bid")), _q(p.get("ask")))
        if None not in vals:
            q[K] = vals
    if pairs is None:
        ks = sorted(k for k in q if abs(k / F - 1) <= mny)
        pairs = [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]]
    out = []
    for K1, K2 in pairs:
        if K1 not in q or K2 not in q:
            continue
        cb1, ca1, pb1, pa1 = q[K1]
        cb2, ca2, pb2, pa2 = q[K2]
        ex = (ca1 - cb2 + pa2 - pb1) + sum(option_fee(x) for x in (ca1, cb2, pa2, pb1))
        mid = ((cb1 + ca1) - (cb2 + ca2) + (pb2 + pa2) - (pb1 + pa1)) / 2
        bor = (cb1 - ca2 + pb2 - pa1) - sum(option_fee(x) for x in (cb1, ca2, pb2, pa1))   # short box proceeds
        rec = {"code": code, "K1": K1, "K2": K2, "T": T, "basis": math.log(F / S) / T}
        for nm, deb in (("r_exec", ex), ("r_mid", mid), ("r_borrow", bor)):
            rec[nm] = math.log((K2 - K1) / (deb * S)) / T if deb > 0 else None
        out.append(rec)
    return out


def quarterly_codes(s: dict) -> list[str]:
    """Quarterly expiry codes of the snapshot (last Friday of Mar/Jun/Sep/Dec), most open interest first."""
    oi = defaultdict(float)
    for o in s["options"]:
        e = code_date(o["code"])
        if e and is_quarterly(e):
            oi[o["code"]] += float(o.get("oi") or 0.0)
    return [c for c, _ in sorted(oi.items(), key=lambda kv: -kv[1])]


def judge_box(vals, days: Sequence[str], thr: float = T196_THR, min_n: int = T196_MIN_N, n_boot: Optional[int] = None) -> tuple:
    x = np.asarray(vals, float)
    n = int(x.size)
    if n == 0:
        v, why = _decide([("box snapshots", None, False)], 0, min_n, "hourly snapshots")
        return v, why, {"n": 0}
    med = float(np.median(x))
    nd = len(set(days))
    ci = None
    if nd >= 3:
        block = max(1, int(round(n / nd)))
        rng = np.random.default_rng(SEED)
        mb = np.median(x[_boot_idx(rng, n, block, _nb(n_boot))], axis=1)
        ci = [float(np.quantile(mb, 0.025)), float(np.quantile(mb, 0.975))]
    crit = [(f"median r_box_exec - bill > {thr * 1e4:.0f} bp (median {_bp(med)})", med > thr, ci is not None and ci[1] < thr),
            (f"95% CI excludes {thr * 1e4:.0f} bp on the upper side ({_cib(ci)}, day blocks)" if ci else
             f"95% CI excludes {thr * 1e4:.0f} bp (not computable from {nd} capture day(s))", None if ci is None else ci[0] > thr,
             ci is not None and ci[1] < thr)]
    v, why = _decide(crit, n, min_n, "hourly snapshots")
    return v, why, {"n": n, "median": med, "ci": ci, "days": nd}


def box_claim(snaps: list[dict], bills: Bills, names: list, hourly: bool, n_boot: Optional[int] = None) -> dict:
    per, dd, extra = [], [], []
    for s in snaps:
        codes = quarterly_codes(s)[:2]
        rs = [b for c in codes for b in box_rates(s, c)]
        ex = [b["r_exec"] for b in rs if b["r_exec"] is not None]
        if not ex:
            continue
        day = _dday(s["ts"])
        bill = bills.same_day(day)
        per.append(float(np.median(ex)) - bill)
        dd.append(day)
        mids = [b["r_mid"] for b in rs if b["r_mid"] is not None]
        extra.append({"ts": _iso(s["ts"]), "expiries": codes, "boxes": len(rs), "median_exec": float(np.median(ex)),
                      "max_exec": float(max(ex)), "median_mid": float(np.median(mids)) if mids else None, "bill": bill,
                      "basis": float(np.median([b["basis"] for b in rs])),
                      "exec_minus_basis": float(np.median(ex)) - float(np.median([b["basis"] for b in rs])),
                      "iqr_exec": [float(np.quantile(ex, 0.25)), float(np.quantile(ex, 0.75))]})
    v, why, det = judge_box(per, dd, n_boot=n_boot)
    stat = {"n": det["n"], "min_n": T196_MIN_N, "judge": det, "snapshots": extra, "sources": names}
    miss = "" if hourly else (f" The claim's data ({HOURLY_BOOK_B}, hourly polls for 14 days) is not archived: "
                              f"{REQUESTS[HOURLY_BOOK_B]}. These daily captures are partial evidence only.")
    sn = "; ".join(f"{e['ts'][:16]} {'/'.join(e['expiries'])}: {e['boxes']} boxes, median exec {_bp(e['median_exec'], sign=False)} "
                   f"(IQR [{_bp(e['iqr_exec'][0], sign=False)}, {_bp(e['iqr_exec'][1], sign=False)}], best {_bp(e['max_exec'], sign=False)}), "
                   f"mid {_bp(e['median_mid'], sign=False)}, basis {_bp(e['basis'], sign=False)}, bill {_bp(e['bill'], sign=False)}"
                   for e in extra)
    reason = (
        f"T-196 executable long-box USD lending rate on the two quarterly expiries with the most open interest, all strike "
        f"pairs within 20% of F with two-sided quotes on all four legs (C1 ask - C2 bid + P2 ask - P1 bid + four taker "
        f"fees; {FEE_TXT}), debit in USD at the index, r = ln((K2 - K1)/debit)/T; per snapshot the median over boxes minus "
        f"the 3-month bill (DTB3, continuous, rule 7; no DGS3MO in the archive). {det['n']} snapshot(s): {sn or 'none'}. "
        f"Median excess {_bp(det.get('median'))}." + miss)
    return {"stat": stat, "n": det["n"], "verdict": v, "reason": reason + f" — {why}"}


def b6b_drb_quarterly_box_rate(archive):
    """T-196: median executable long-box USD lending rate (two most liquid BTC quarterlies) minus the 3-month bill."""
    miss = _missing(archive, [DTB3_B])
    if miss:
        return miss
    snaps, names = book_snapshots(archive, _index_hourly(archive) if _has(archive, FUND_B) else None)
    if not snaps:
        return _missing(archive, [HOURLY_BOOK_B])
    return _out(box_claim(snaps, Bills(_fred(archive)), names, _has(archive, HOURLY_BOOK_B)))


# ----------------------------------------------------------------------------------------- T-260 capture days --

def tardis_snapshots(rows: Sequence[dict]) -> list[dict]:
    """Capture-day snapshots of the Tardis box bundle (the 'first' ticker message of each leg)."""
    by = defaultdict(lambda: {"options": [], "futures": {}, "S": None, "ts": None})
    for r in rows:
        v = r["value"]
        if r.get("kind") != "option-ticker" or v.get("snap", "first") != "first":
            continue
        tk = v.get("ticker") or {}
        s = by[v["capture_day"]]
        s["ts"] = _ms(v["capture_day"])
        s["options"].append({"code": v.get("expiry_code"), "strike": v.get("strike"), "type": v.get("type"),
                             "bid": tk.get("best_bid_price"), "ask": tk.get("best_ask_price"), "mark": tk.get("mark_price"),
                             "underlying": tk.get("underlying_price"), "index_price": tk.get("index_price"),
                             "underlying_index": tk.get("underlying_index")})
        if s["S"] is None and _q(tk.get("index_price")):
            s["S"] = _q(tk.get("index_price"))
    return [{**s, "source": BOX_MONTHLY_B} for d, s in sorted(by.items())]


def capture_day_rate(s: dict, n_side: int = 2) -> Optional[dict]:
    """T-260 rate of one capture day: expiries 30-90 calendar days out; strikes bracketing the index (n_side below and
    above with both quotes); every bracketing pair; median mid-price box rate (also executable lend and borrow)."""
    S = s.get("S")
    if not S:
        return None
    d0 = date.fromisoformat(_dday(s["ts"]))
    rs = []
    for code in sorted({o["code"] for o in s["options"] if o.get("code")}):
        e = code_date(code)
        if not e or not (30 <= (date.fromisoformat(e) - d0).days <= 90):
            continue
        ks = sorted(k for k, v in _pairs(s, code).items()
                    if all(_q(v[t].get(x)) for t in ("call", "put") for x in ("bid", "ask")))
        below, above = [k for k in ks if k <= S][-n_side:], [k for k in ks if k > S][:n_side]
        rs += box_rates(s, code, pairs=[(a, b) for a in below for b in above])
    mid = [b["r_mid"] for b in rs if b["r_mid"] is not None]
    if not mid:
        return None
    ex = [b["r_exec"] for b in rs if b["r_exec"] is not None]
    bo = [b["r_borrow"] for b in rs if b["r_borrow"] is not None]
    return {"day": d0.isoformat(), "source": s.get("source"), "r_mid": float(np.median(mid)), "boxes": len(rs),
            "r_exec": float(np.median(ex)) if ex else None, "r_borrow": float(np.median(bo)) if bo else None,
            "expiries": sorted({b["code"] for b in rs})}


def basis_control(rows: list[dict], bills: Bills, days: Optional[set] = None) -> dict:
    """Futures-basis implied rate on capture days (or on the first of each month): the 30-90 DTE quarterly (nearest 60)."""
    hit, tot, ex = 0, 0, []
    for r in rows:
        if days is not None and r["day"] not in days:
            continue
        if days is None and not r["day"].endswith("-01"):
            continue
        cands = [(abs(r["dte1"] - 60), r["basis1"]) if 30 <= r["dte1"] <= 90 else None,
                 (abs(r["dte2"] - 60), r["basis2"]) if 30 <= r["dte2"] <= 90 else None]
        cands = [c for c in cands if c]
        if not cands:
            continue
        b = min(cands)[1] - bills.same_day(r["day"])
        ex.append(b)
        tot += 1
        hit += b > T260_THR
    return {"days": tot, "fraction_above_200bp": hit / tot if tot else None, "median_excess": float(np.median(ex)) if ex else None}


def judge_capture(rates: list[dict], bills: Bills, min_n: int = T260_MIN_N) -> tuple:
    n = len(rates)
    if n == 0:
        v, why = _decide([("capture days with a 30-90 DTE box", None, False)], 0, min_n, "capture days")
        return v, why, {"n": 0}
    ex = np.array([r["r_mid"] - bills.same_day(r["day"]) for r in rates])
    k = int((ex > T260_THR).sum())
    frac = k / n
    lo, hi = clopper_pearson(k, n)
    crit = [(f"fraction of capture days with r_mid - bill > 200 bp > 70% ({k} of {n} = {frac:.0%}; exact 95% "
             f"[{lo:.0%}, {hi:.0%}])", frac > T260_FRAC, hi <= T260_FRAC)]
    v, why = _decide(crit, n, min_n, "capture days")
    return v, why, {"n": n, "above": k, "fraction": frac, "ci": [lo, hi], "median_spread": float(np.median(ex)),
                    "exec_lend_median": float(np.median([r["r_exec"] - bills.same_day(r["day"]) for r in rates if r["r_exec"] is not None]))
                    if any(r["r_exec"] is not None for r in rates) else None}


def capture_claim(snaps: list[dict], bills: Bills, names: list, tardis: bool, basis_rows: list[dict]) -> dict:
    rates = [r for r in (capture_day_rate(s) for s in snaps) if r is not None]
    v, why, det = judge_capture(rates, bills)
    ctl_days = basis_control(basis_rows, bills, {r["day"] for r in rates}) if basis_rows else {}
    ctl_month = basis_control(basis_rows, bills) if basis_rows else {}
    stat = {"n": det["n"], "min_n": T260_MIN_N, "judge": det, "days": rates, "sources": names,
            "futures_basis_same_days": ctl_days, "futures_basis_first_of_month_proxy": ctl_month}
    miss = "" if tardis else f" Not archived: {BOX_MONTHLY_B} ({REQUESTS[BOX_MONTHLY_B]})."
    dl = "; ".join(f"{r['day']} {'/'.join(r['expiries'])} mid {_bp(r['r_mid'], sign=False)} (lend exec "
                   f"{_bp(r['r_exec'], sign=False)}, borrow exec {_bp(r['r_borrow'], sign=False)}), bill "
                   f"{_bp(bills.same_day(r['day']), sign=False)}" for r in rates)
    reason = (
        f"T-260 option-implied USD rate from boxes bracketing the index (2 strikes below and 2 above with two-sided quotes, "
        f"every bracketing pair) on expiries 30-90 calendar days out, mid prices, r = ln((K2 - K1)/(debit x index))/T, vs "
        f"the 3-month bill (DTB3 continuous, rule 7; the archive has no DGS3MO): {det['n']} capture day(s) from "
        f"{', '.join(names) or 'none'}: {dl or 'none'}. Median spread {_bp(det.get('median_spread'))}; executable lending "
        f"spread {_bp(det.get('exec_lend_median'))}. Control, futures-basis implied rate (30-90 DTE quarterly, "
        f"{QF_B}): same days {_f(ctl_days.get('fraction_above_200bp'), 2)} above 200 bp; first of each month 2019-05..2026-10 "
        f"proxy {_f(ctl_month.get('fraction_above_200bp'), 2)} of {ctl_month.get('days', 0)} days above 200 bp (median "
        f"{_bp(ctl_month.get('median_excess'))}; not the claim's option box)." + miss)
    return {"stat": stat, "n": det["n"], "verdict": v, "reason": reason + f" — {why}"}


def b6b_drb_box_rate_capture_days(archive):
    """T-260: share of capture days where the 30-90 DTE BTC box rate (mid) exceeds the 3-month bill by > 200 bp."""
    miss = _missing(archive, [DTB3_B])
    if miss:
        return miss
    idx = _index_hourly(archive) if _has(archive, FUND_B) else None
    snaps, names = book_snapshots(archive, idx)
    tardis = _has(archive, BOX_MONTHLY_B)
    if tardis:
        snaps = tardis_snapshots(_rows(archive, BOX_MONTHLY_B)) + snaps
        names = [BOX_MONTHLY_B] + names
    if not snaps:
        return _missing(archive, [BOX_MONTHLY_B])
    # one snapshot per capture day (the earliest)
    seen, uniq = set(), []
    for s in sorted(snaps, key=lambda s: s["ts"]):
        d = _dday(s["ts"])
        if d not in seen:
            seen.add(d)
            uniq.append(s)
    brows = basis_days([r["value"] for r in _rows(archive, QF_B)], idx) if (idx and _has(archive, QF_B)) else []
    return _out(capture_claim(uniq, Bills(_fred(archive)), names, tardis, brows))


# ================================================================================================== registry ==

HARNESSES: dict[str, Callable] = {
    "b6b_drb_catalyst_strangle": b6b_drb_catalyst_strangle,
    "b6b_drb_quarterly_basis": b6b_drb_quarterly_basis,
    "b6b_drb_expiry_friday_straddle": b6b_drb_expiry_friday_straddle,
    "b6b_drb_fomc_event_straddle": b6b_drb_fomc_event_straddle,
    "b6b_drb_dvol_futures_basis": b6b_drb_dvol_futures_basis,
    "b6b_drb_cme_ibit_tax": b6b_drb_cme_ibit_tax,
    "b6b_drb_parity_violations": b6b_drb_parity_violations,
    "b6b_drb_quarterly_box_rate": b6b_drb_quarterly_box_rate,
    "b6b_drb_box_rate_capture_days": b6b_drb_box_rate_capture_days,
    "b6b_drb_rr_skew_harvest": b6b_drb_rr_skew_harvest,
    "b6b_drb_calendar_inversion": b6b_drb_calendar_inversion,
}

THEORY_MAP = {
    "T-222": "b6b_drb_catalyst_strangle",
    "T-197": "b6b_drb_quarterly_basis",
    "T-223": "b6b_drb_expiry_friday_straddle",
    "T-263": "b6b_drb_fomc_event_straddle",
    "T-268": "b6b_drb_dvol_futures_basis",
    "T-269": "b6b_drb_cme_ibit_tax",
    "T-195": "b6b_drb_parity_violations",
    "T-196": "b6b_drb_quarterly_box_rate",
    "T-260": "b6b_drb_box_rate_capture_days",
    "T-257": "b6b_drb_rr_skew_harvest",
    "T-262": "b6b_drb_calendar_inversion",
}
