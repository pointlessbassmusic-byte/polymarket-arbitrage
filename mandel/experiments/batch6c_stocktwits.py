"""
Batch 6c, group ``stocktwits``: two StockTwits claims on the weekly backfill bundles of ``mandel.data.public_history``
(section 12): the pre-open bullish ratio as a directional signal (T-414) and message intensity as a predictor of
next-day realised volatility beyond lagged realised and same-day implied volatility (T-415).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-414  B = bullish / (bullish + bearish) over the user-tagged messages of the pre-open window (16:00 ET of the
           previous NYSE session .. 09:00 ET of day d) for the 14 declared streams (``ST_PREOPEN_SYMBOLS``), entry at the
           09:30 ET open of d, exit at the next session's open; min_n 1,200 symbol-days: accuracy >= 52% in the
           PRE-DECLARED follow direction AND permutation p < 0.01 after deflation over the 16 declared cells AND IC t > 3
           (both named constructions) AND the same sign in both halves of the sample.
  * T-415  z_t = the day's message intensity (``per_hour`` of the 10:00, 13:00 and 15:30 ET samples, averaged) standardised
           within symbol on the trailing 30 sampled days (strictly before t; >= 20 of them), for the 21 IV-covered streams
           (``ST_INTENSITY_SYMBOLS``); min_n 1,500 symbol-days: in the pooled HAR regression
           RV_{t+1} = a + b1 RV_t + b2 RV_week + b3 RV_month + b4 IV_t + c z_t the coefficient c has Driscoll-Kraay t > 3
           with incremental R^2 >= 2% AND the expanding walk-forward (5-day embargo) QLIKE of the model with z beats
           HAR+IV with Diebold-Mariano p < 0.05 after deflation over the 12 declared cells.

Data (every bundle through ``archive.load``; a row counts only when its ``available_at`` is not after the bundle's
capture time; the weeks stored are discovered from the archive's entry names at call time, so a backfill still running
is tested on what it has stored and the data limit is named)
  * ``stocktwits-preopen-<YYYY>-W<ww>``: kind ``message`` rows {stream, day, created_at, sentiment} and one kind ``window``
    row per stream x day {window_start, window_end, bullish, bearish, tagged, complete}. B is recomputed from the message
    rows created inside [window_start, window_end) (the fetcher's counts are cross-checked; mismatches reported); a
    window the fetcher could not complete drops out (counted). The library rule's filter (>= 20 tagged messages) is
    applied; the unfiltered accuracy is reported alongside.
  * ``stocktwits-intensity-<YYYY>-W<ww>``: kind ``intensity-sample`` rows {stream, day, sample_time, n, per_hour}; a day
    needs >= 2 of its 3 samples with a per_hour value (a sample with no message before its time has none).
  * Prices (T-414). Equities: Yahoo ``daily-history-<SYM>`` opens on the total-return basis (open x adjclose / close), so
    an ex-dividend between two opens does not count as a fall. Crypto streams (BTC.X, ETH.X, SOL.X, DOGE.X) trade 24/7
    and have no official open: the declared mark is the first archived trade at or after 09:30 ET, the open of the 09:30
    ET minute bar from ``coinbase-1m-<PID>-<YYYY-MM>`` when that month is archived, else the open of the first
    ``coinbase-hourly-<PID>`` bar starting at or after 09:30 ET (the 10:00 ET bar); the stat names each stream's mark.
    The exit mark is the same mark on the next NYSE session (a Friday window spans the weekend for crypto too, as the
    claim's open-to-next-open does). A stream without archived prices drops out with its count.
  * Realised variance (T-415), the asset's own calendar: equities RV_t = the sum of squared log returns across the
    session's Yahoo ``hourly-<SYM>`` bars starting in [09:30, 16:00) ET, chained from the first bar's open (>= 6 bars:
    early closes drop out; the spurious 16:00 bar Yahoo appends is excluded), i.e. the intraday (open-to-close) realised
    variance; crypto RV_t = the same over the 24 ``coinbase-hourly-<PID>`` bars of UTC day t (>= 20 bars; Yahoo
    ``hourly-<PID>`` as the fallback). An equity without hourly bars falls back to the Parkinson estimator
    ln(H/L)^2 / (4 ln 2) of its daily bar (also an intraday-variance estimator); the stat names each symbol's estimator.
    HAR_week / HAR_month = the means of the last 5 / 22 session RVs (7 / 30 calendar days for crypto), windows complete.
  * Implied variance (T-415), at the same close, in daily variance units (annualised IV^2 / 252, / 365 for crypto): Cboe
    ``cboe-<IDX>-history`` closes (VIX SPY, VXN QQQ, RVX IWM, VXAPL AAPL, VXAZN AMZN, VXGOG GOOG, GVZ GLD, OVX USO, VXEEM
    EEM, VXTLT TLT; available 21:30 UTC), DoltHub ``dolt-volhistory`` iv_current for the nine sector SPDRs (the earliest
    snapshot of each quote_date; available 22:00 UTC), Deribit ``deribit-dvol-<CCY>-history`` closes of UTC day t for
    BTC.X / ETH.X (available 00:00 UTC t+1, the crypto decision boundary). A symbol-day without IV drops out (counted).
  * Point in time (rule 4). T-414: only messages created before 09:00 ET enter B, the entry is the 09:30 open (crypto:
    the first trade at/after 09:30 ET), the forward return starts at the entry. T-415 equities: the decision is the
    16:00 ET close of t; z uses samples taken before it, IV is struck at that close (known by 18:00 ET), the target is
    the next session's intraday variance (from 09:30 ET t+1). Crypto: the decision is 00:00 UTC (the end of UTC day t,
    after the 15:30 ET sample); RV_t and DVOL_t are that day's, the target is UTC day t+1 (a Saturday after a Friday
    sample). z's trailing window ends the day before t.
  * The NYSE session calendar is SPY's daily bars. ``fomc-meetings`` decision days flag T-415 target days (the regression
    without them is reported). No earnings calendar is archived: the earnings flags both trials list as controls are
    reported as unavailable (a control, not a pass criterion).

Statistics
  * T-414 follow direction, declared here from the claim's wording and not fitted (``FOLLOW_CUT``): a bullish majority
    (B > 0.5) predicts an up open-to-next-open return, B < 0.5 a down one; B = 0.5 and zero returns make no prediction
    (counted out of the accuracy's denominator). The permutation null (the trial's): B shuffled across days within each
    symbol, 2,000 draws, p = (#draws with accuracy >= observed + 1) / (draws + 1); deflated over 16 cells by Sidak,
    1 - (1 - p)^16 < 0.01. IC (rule 11, both named constructions must pass t > 3): (a) the daily cross-sectional
    Spearman of B with the forward return (days with >= 5 streams), mean / Newey-West s.e.; (b) the pooled IC = Pearson
    correlation of the within-symbol fractional ranks of B and of the return, its t from the OLS slope of the return
    rank on the B rank with symbol-clustered s.e. (G/(G-1) (n-1)/(n-k) small-sample factor). Halves: the observations
    split at the median date; both the accuracy edge (accuracy - 50%) and the pooled IC must keep the claim's sign in
    both halves. Net return of the rule (a statistic, not a criterion): position = the predicted sign, round-trip cost
    charged on turnover, 1 bp SPY/QQQ, 5 bps every other stream (the claim names no crypto cost: 5 bps assumed and
    stated). VIX split: the previous session's VIX close above / below its sample median. The 16 declared cells
    (direction x signal form x horizon x weighting) are charged in the deflation; the computable variants are reported
    as a family (accuracies only), the claim's cell decides.
  * T-415 regression: the pooled HAR+IV in its log form (ln RV_{t+1} on ln RV_t, ln RV_week, ln RV_month, ln IV_t and
    z_t; Corsi's own scale-free variant and the standard for a panel of assets), pooled OLS with a common intercept and
    Driscoll-Kraay s.e. (per-day sums of the score, Bartlett kernel, lag max(nw_lag(T), horizon)). The variance levels
    of the 21 streams differ by a factor of about 60 (TLT 1e-5 a day, ETH 6e-4), so the literal levels regression is a
    scale artifact: its z coefficient is set by the crypto rows and pushes the low-volatility names' forecasts below
    zero (checked on the archive: floored forecasts rose from 17 to 91 of 3,422 and every one of the largest QLIKE
    losses was a sector SPDR with a negative z); it is reported as the ``levels`` diagnostic with its floor share, not
    judged. Incremental R^2 = R^2(with z) - R^2(HAR+IV) on the same rows (log variance). Two readings of the regressor,
    both judged and both must pass (the claim's own words name the abnormal flag, the trial's equation the score): z_t
    continuous and A_t = 1{z_t > 2}. Walk-forward: expanding window refit at every origin from the 60th sampled day,
    training rows whose target lies >= 5 sampled days before the origin (the embargo), forecast F = exp(fitted ln RV +
    s^2 / 2) with s^2 the training residual variance (the lognormal mean correction), QLIKE = RV/F - ln(RV/F) - 1; the
    Diebold-Mariano statistic is the mean over origins of the day's cross-sectional mean loss difference (HAR+IV minus
    HAR+IV+z) over its Newey-West s.e., one-sided p for an improvement; the trial's "12 cells deflated" is applied to
    this p by Sidak (1 - (1 - p)^12 < 0.05) and reported for the t-stat too (t > 3 already implies a Sidak-12 p below
    0.05: 1 - (1 - 0.00135)^12 = 0.016). The declared family (realised-vol estimator: hourly RV / Parkinson / daily
    squared return x horizon 1 / 5 days) is reported with its in-sample t and incremental R^2; the claim's cell (hourly
    RV, 1 day) decides.
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively: T-414's
    accuracy when its one-sided 99% upper bound (the pass's own confidence) is below 52%, T-414's and T-415's t when the
    estimate is decisively of the wrong sign (t < -3, the pass's own confidence); p-value, incremental-R^2 and sign
    criteria are never decisive.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.data.public_history import ST_INTENSITY_SYMBOLS, ST_PREOPEN_SYMBOLS
from mandel.experiments.batch6b_bw import _decide, _out
from mandel.experiments.underlying2 import _verdict

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
_N = NormalDist()
SEED = 0

SPY_B = "daily-history-SPY"
VIX_B = "cboe-VIX-history"
FOMC_B = "fomc-meetings"
DOLT_B = "dolt-volhistory"
PREOPEN_PREFIX = "stocktwits-preopen-"
INTENSITY_PREFIX = "stocktwits-intensity-"
CRYPTO_PID = {"BTC.X": "BTC-USD", "ETH.X": "ETH-USD", "SOL.X": "SOL-USD", "DOGE.X": "DOGE-USD"}

# ---- T-414 -------------------------------------------------------------------------------------------------------
T414_MIN_N = 1200
T414_CELLS = 16
T414_N_PERM = 2000
T414_ACC = 0.52
T414_P = 0.01
T414_IC_T = 3.0
T414_MIN_TAGGED = 20          # the library rule: skip symbol-days with fewer than 20 tagged messages
FOLLOW_CUT = 0.5              # PRE-DECLARED follow direction: B > 0.5 (a bullish majority) predicts up, B < 0.5 down
COST_RT = {"SPY": 1e-4, "QQQ": 1e-4}
COST_RT_DEFAULT = 5e-4        # single names (the claim); crypto streams unnamed by the claim: the same 5 bps, stated
MARK_HHMM = (9, 30)           # the entry mark, ET
MIN_CS = 5                    # streams a day needs for a cross-sectional IC
Z99 = _N.inv_cdf(0.99)

# ---- T-415 -------------------------------------------------------------------------------------------------------
T415_MIN_N = 1500
T415_CELLS = 12
Z_WINDOW = 30
Z_MIN_OBS = 20
Z_ABNORMAL = 2.0
T415_T = 3.0
T415_DR2 = 0.02
T415_DM_P = 0.05
EMBARGO = 5
MIN_TRAIN = 60
HAR_EQ = (5, 22)
HAR_CRYPTO = (7, 30)
MIN_SAMPLES = 2
MIN_BARS_EQ = 6
MIN_BARS_CRYPTO = 20
QLIKE_FLOOR_Q = 0.01
CBOE_IV = {"SPY": "VIX", "QQQ": "VXN", "IWM": "RVX", "AAPL": "VXAPL", "AMZN": "VXAZN", "GOOG": "VXGOG", "GLD": "GVZ",
           "USO": "OVX", "EEM": "VXEEM", "TLT": "VXTLT"}
DOLT_IV = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
DVOL_IV = {"BTC.X": "BTC", "ETH.X": "ETH"}


# ================================================================================================ small helpers ==

def _safe(sym: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def dh(sym: str) -> str:
    return "daily-history-" + _safe(sym)


def hourly_b(sym: str) -> str:
    return "hourly-" + _safe(sym)


def cboe_b(idx: str) -> str:
    return f"cboe-{idx}-history"


def dvol_b(ccy: str) -> str:
    return f"deribit-dvol-{ccy}-history"


def _ts(s: str) -> float:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp()


def _et_ts(day: str, hh: int, mm: int) -> float:
    return datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), hh, mm, tzinfo=NY).timestamp()


def _utc_day(t) -> str:
    return datetime.fromtimestamp(float(t), tz=UTC).strftime("%Y-%m-%d")


def _et_dt(t) -> datetime:
    return datetime.fromtimestamp(float(t), tz=NY)


def sidak(p: Optional[float], k: int) -> Optional[float]:
    """Probability that the smallest of ``k`` independent null p-values is <= p."""
    if p is None or not math.isfinite(p):
        return None
    return float(1.0 - (1.0 - min(max(p, 0.0), 1.0)) ** k)


def nw_lag(n: int) -> int:
    return int(math.floor(4.0 * (max(n, 1) / 100.0) ** (2.0 / 9.0)))


def _rank(a: np.ndarray) -> np.ndarray:
    """Average ranks 1..n (ties averaged)."""
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, float)
    ranks[order] = np.arange(1, a.size + 1)
    vals, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    if (counts > 1).any():
        sums = np.zeros(vals.size)
        np.add.at(sums, inv, ranks)
        ranks = (sums / counts)[inv]
    return ranks


def spearman(x, y) -> Optional[float]:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.size < 3:
        return None
    rx, ry = _rank(x), _rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def _lrv(x: np.ndarray, lag: int) -> float:
    """Bartlett (Newey-West, weights 1 - l/(L+1)) long-run variance of a 1-d series."""
    x = np.asarray(x, float)
    n = x.size
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(u[l:] @ u[:-l]) / n
    return max(s, 0.0)


def nw_t(x, lag: Optional[int] = None) -> Optional[float]:
    """Mean / Newey-West s.e. of a series (lag = nw_lag(n) by default)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return None
    lag = nw_lag(n) if lag is None else lag
    se = math.sqrt(_lrv(x, lag) / n)
    if se <= 0:
        return None
    return float(x.mean() / se)


def _p_one(t: Optional[float]) -> Optional[float]:
    """One-sided p for H0: effect <= 0 given a t statistic."""
    if t is None or not math.isfinite(t):
        return None
    return float(1.0 - _N.cdf(t))


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pu(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _g(x, nd: int = 4) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}g}"


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


def _cap(archive, name: str):
    try:
        return getattr(archive.get(name), "created_at", None)
    except (KeyError, AttributeError):
        return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = _cap(archive, name)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _stream(archive, name: str):
    """Stream a large bundle's rows (not cached), with the same capture-time filter."""
    cap = _cap(archive, name)
    for r in archive.load(name):
        if not (cap and r.get("available_at") and r["available_at"] > cap):
            yield r


def _entry_names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if e.name.startswith(prefix))


def _sessions(archive) -> list:
    """NYSE session days (SPY's daily bars), sorted."""
    return _cached(archive, "sessions", lambda: sorted({_utc_day(r["value"]["t"]) for r in _rows(archive, SPY_B)}))


def next_session(sessions: Sequence[str], day: str) -> Optional[str]:
    i = bisect.bisect_right(sessions, day)
    return sessions[i] if i < len(sessions) else None


def prev_session(sessions: Sequence[str], day: str) -> Optional[str]:
    i = bisect.bisect_left(sessions, day) - 1
    return sessions[i] if i >= 0 else None


def _daily(archive, sym: str) -> dict:
    """{day: {open (total-return basis), close (adjclose), raw_close, high, low}} from ``daily-history-<SYM>``."""
    def load():
        out = {}
        for r in _rows(archive, dh(sym)):
            v = r["value"]
            c = v.get("close")
            if c is None or float(c) <= 0:
                continue
            adj = v.get("adjclose")
            f = float(adj) / float(c) if adj is not None and float(adj) > 0 else 1.0
            o = v.get("open")
            out[_utc_day(v["t"])] = {"open": float(o) * f if o is not None and float(o) > 0 else None, "close": float(c) * f,
                                     "raw_close": float(c), "high": v.get("high"), "low": v.get("low")}
        return out
    return _cached(archive, ("daily", sym), load)


def _bars(archive, name: str) -> list:
    """Sorted (t, open, high, low, close) of a bar bundle."""
    def load():
        out = []
        for r in _rows(archive, name):
            v = r["value"]
            if v.get("t") is None or v.get("close") is None:
                continue
            out.append((float(v["t"]), float(v.get("open") if v.get("open") is not None else v["close"]),
                        float(v.get("high") if v.get("high") is not None else v["close"]),
                        float(v.get("low") if v.get("low") is not None else v["close"]), float(v["close"])))
        out.sort()
        return out
    return _cached(archive, ("bars", name), load)


def _vix_prev(archive, sessions: Sequence[str]) -> dict:
    """{session day: the previous session's VIX close} (known at the day's 09:00 ET)."""
    if not _has(archive, VIX_B):
        return {}
    close = {}
    for r in _rows(archive, VIX_B):
        v = r["value"]
        if v.get("close") is not None:
            close[v["day"]] = float(v["close"])
    out = {}
    for d in sessions:
        p = prev_session(sessions, d)
        if p in close:
            out[d] = close[p]
    return out


def _fomc_days(archive) -> set:
    if not _has(archive, FOMC_B):
        return set()
    return {r["value"].get("decision_day") for r in _rows(archive, FOMC_B)
            if r["value"].get("decision_day") and not r["value"].get("future")}


# ====================================================================================== T-414: pre-open ratio ==

def preopen_panel(message_rows: Sequence[dict], window_rows: Sequence[dict]) -> dict:
    """{(stream, day): {B, bullish, bearish, tagged, messages, complete, window_start, window_end, outside, mismatch}}
    with B recomputed from the message rows created inside [window_start, window_end)."""
    win = {}
    for r in window_rows:
        v = r.get("value") or {}
        if v.get("stream") and v.get("day"):
            win[(v["stream"], v["day"])] = v
    cnt: dict = defaultdict(lambda: {"bull": 0, "bear": 0, "msgs": 0, "outside": 0})
    for r in message_rows:
        v = r.get("value") or {}
        key = (v.get("stream"), v.get("day"))
        w = win.get(key)
        if w is None:
            continue
        t = _ts(v.get("created_at") or r.get("observed_at"))
        if not (_ts(w["window_start"]) <= t < _ts(w["window_end"])):
            cnt[key]["outside"] += 1
            continue
        cnt[key]["msgs"] += 1
        s = v.get("sentiment")
        if s == "Bullish":
            cnt[key]["bull"] += 1
        elif s == "Bearish":
            cnt[key]["bear"] += 1
    out = {}
    for key, w in win.items():
        c = cnt.get(key, {"bull": 0, "bear": 0, "msgs": 0, "outside": 0})
        tagged = c["bull"] + c["bear"]
        out[key] = {"B": c["bull"] / tagged if tagged else None, "bullish": c["bull"], "bearish": c["bear"], "tagged": tagged,
                    "messages": c["msgs"], "complete": bool(w.get("complete", True)), "window_start": w.get("window_start"),
                    "window_end": w.get("window_end"), "outside": c["outside"],
                    "mismatch": (w.get("bullish") is not None and (int(w.get("bullish") or 0) != c["bull"] or int(w.get("bearish") or 0) != c["bear"]))}
    return out


def _first_bar_at_or_after(archive, name: str, targets: Sequence[float], horizon: float) -> dict:
    """{target: open of the first bar with start in [target, target + horizon]} streaming ``name`` once."""
    ts = sorted(targets)
    out: dict = {}
    for r in _stream(archive, name):
        v = r.get("value") or {}
        t = v.get("t")
        if t is None or v.get("open") is None:
            continue
        t = float(t)
        i = bisect.bisect_right(ts, t) - 1
        if i < 0:
            continue
        tg = ts[i]
        if t - tg <= horizon and (tg not in out or t < out[tg][0]):
            out[tg] = (t, float(v["open"]))
    return {k: p for k, (_, p) in out.items()}


def crypto_open_marks(archive, pid: str, days: Sequence[str]) -> tuple:
    """({day: price at the declared crypto mark}, mark description, {day: source}). The mark is the first archived trade
    at or after 09:30 ET: the 09:30 minute bar's open (``coinbase-1m-<PID>-<YYYY-MM>``) when that month is archived, else
    the open of the first ``coinbase-hourly-<PID>`` bar starting at or after 09:30 ET (the 10:00 ET bar)."""
    targets = {d: _et_ts(d, *MARK_HHMM) for d in days}
    out, src = {}, {}
    months = sorted({d[:7] for d in days})
    for m in months:
        name = f"coinbase-1m-{pid}-{m}"
        if not _has(archive, name):
            continue
        tg = [targets[d] for d in days if d[:7] == m]
        got = _first_bar_at_or_after(archive, name, tg, 30 * 60)
        for d in days:
            if d[:7] == m and targets[d] in got:
                out[d] = got[targets[d]]
                src[d] = "1m"
    rest = [d for d in days if d not in out]
    hourly = f"coinbase-hourly-{pid}"
    if rest and _has(archive, hourly):
        got = _first_bar_at_or_after(archive, hourly, [targets[d] for d in rest], 90 * 60)
        for d in rest:
            if targets[d] in got:
                out[d] = got[targets[d]]
                src[d] = "1h"
    kinds = sorted(set(src.values()))
    desc = {"1m": "coinbase-1m open of the 09:30 ET minute bar", "1h": "coinbase-hourly open of the first bar at/after 09:30 ET (10:00 ET)"}
    return out, " / ".join(desc[k] for k in kinds) if kinds else "no archived bars", src


def _cluster_t(y: np.ndarray, x: np.ndarray, g: np.ndarray) -> Optional[float]:
    """t of the slope of y on x (intercept included) with cluster-robust s.e. by ``g`` (Liang-Zeger, small-sample factor)."""
    n = y.size
    Z = np.column_stack([np.ones(n), x])
    try:
        ZtZi = np.linalg.inv(Z.T @ Z)
    except np.linalg.LinAlgError:
        return None
    b = ZtZi @ Z.T @ y
    e = y - Z @ b
    groups, inv = np.unique(g, return_inverse=True)
    G = groups.size
    if G < 2:
        return None
    H = np.zeros((G, 2))
    np.add.at(H, inv, Z * e[:, None])
    S = H.T @ H * (G / (G - 1.0)) * ((n - 1.0) / max(n - 2.0, 1.0))
    V = ZtZi @ S @ ZtZi
    se = math.sqrt(max(float(V[1, 1]), 0.0))
    return float(b[1] / se) if se > 0 else None


def _within_ranks(x: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Fractional ranks of x within each group g (ties averaged), in (0, 1]."""
    out = np.empty(x.size)
    for grp in np.unique(g):
        idx = np.where(g == grp)[0]
        out[idx] = _rank(x[idx]) / idx.size
    return out


def _accuracy(pred: np.ndarray, sgn: np.ndarray) -> tuple:
    valid = (pred != 0) & (sgn != 0)
    k = int(valid.sum())
    return (float((pred[valid] == sgn[valid]).mean()) if k else None), k


def _net_returns(obs: Sequence[dict], pred: np.ndarray) -> dict:
    """Mean gross and net daily return of the rule (position = predicted sign; the round-trip cost on turnover)."""
    by: dict = defaultdict(list)
    for o, p in zip(obs, pred):
        by[o["sym"]].append((o["day"], int(p), float(o["ret"]), float(o["cost"])))
    gross, net = [], []
    for sym, rows in by.items():
        rows.sort()
        prev = 0
        for _, p, r, c in rows:
            gross.append(p * r)
            net.append(p * r - c * abs(p - prev) / 2.0)
            prev = p
    if not net:
        return {"mean_gross_bps": None, "mean_net_bps": None, "n": 0}
    return {"mean_gross_bps": float(np.mean(gross)) * 1e4, "mean_net_bps": float(np.mean(net)) * 1e4, "n": len(net)}


def bullish_ratio_test(obs: Sequence[dict], n_perm: int = T414_N_PERM, seed: int = SEED, cells: int = T414_CELLS,
                       vix: Optional[dict] = None) -> dict:
    """The claim's statistics on observations {sym, day, B, ret, tagged, cost}: accuracy in the follow direction, the
    permutation null, both IC constructions, halves, the net return, the VIX split and the family of declared cells."""
    n = len(obs)
    out: dict = {"n": n, "follow_rule": f"B > {FOLLOW_CUT} predicts up, B < {FOLLOW_CUT} predicts down (pre-declared, not fitted)"}
    if n < 8:
        out.update(accuracy=None, n_predicted=0, p_perm=None, p_perm_deflated=None, ic=None, halves=None)
        return out
    sym = np.array([o["sym"] for o in obs])
    day = np.array([o["day"] for o in obs])
    B = np.array([float(o["B"]) for o in obs])
    ret = np.array([float(o["ret"]) for o in obs])
    sgn = np.sign(ret)
    gid = np.unique(sym, return_inverse=True)[1]
    pred = np.sign(B - FOLLOW_CUT)
    acc, k = _accuracy(pred, sgn)
    rB, rR = _within_ranks(B, gid), _within_ranks(ret, gid)
    ic_pooled = float(np.corrcoef(rB, rR)[0, 1]) if rB.std() > 0 and rR.std() > 0 else 0.0
    t_pooled = _cluster_t(rR, rB, gid) if rB.std() > 0 else None
    # daily cross-sectional IC
    cs = []
    for d in np.unique(day):
        m = day == d
        if m.sum() >= MIN_CS:
            v = spearman(B[m], ret[m])
            if v is not None:
                cs.append(v)
    cs = np.asarray(cs, float)
    ic_cs = float(cs.mean()) if cs.size else None
    t_cs = nw_t(cs) if cs.size >= 3 else None
    # permutation null: B shuffled across days within each symbol
    rng = np.random.default_rng(seed)
    groups = [np.where(gid == g)[0] for g in range(gid.max() + 1)]
    acc_ge, ic_ge = 0, 0
    for _ in range(n_perm):
        Bp, rBp = B.copy(), rB.copy()
        for idx in groups:
            pi = rng.permutation(idx.size)
            Bp[idx] = B[idx][pi]
            rBp[idx] = rB[idx][pi]
        a_p, _ = _accuracy(np.sign(Bp - FOLLOW_CUT), sgn)
        if a_p is not None and acc is not None and a_p >= acc - 1e-12:
            acc_ge += 1
        ic_p = float(np.corrcoef(rBp, rR)[0, 1]) if rBp.std() > 0 and rR.std() > 0 else 0.0
        if ic_p >= ic_pooled - 1e-12:
            ic_ge += 1
    p_acc = (acc_ge + 1.0) / (n_perm + 1.0) if acc is not None else None
    p_ic = (ic_ge + 1.0) / (n_perm + 1.0)
    # halves at the median date: the first day whose preceding observations make up at least half the sample
    udays = sorted(set(day.tolist()))
    cut, seen = udays[-1], 0
    for d in udays:
        if seen >= n / 2.0:
            cut = d
            break
        seen += int((day == d).sum())
    halves = {}
    for label, m in (("first", day < cut), ("second", day >= cut)):
        if m.sum() >= 3:
            a_h, k_h = _accuracy(pred[m], sgn[m])
            g_h = np.unique(sym[m], return_inverse=True)[1]
            rb, rr = _within_ranks(B[m], g_h), _within_ranks(ret[m], g_h)
            ic_h = float(np.corrcoef(rb, rr)[0, 1]) if rb.std() > 0 and rr.std() > 0 else 0.0
            halves[label] = {"n": int(m.sum()), "accuracy": a_h, "n_predicted": k_h, "ic_pooled": ic_h,
                             "days": [str(min(day[m])), str(max(day[m]))]}
        else:
            halves[label] = {"n": int(m.sum()), "accuracy": None, "n_predicted": 0, "ic_pooled": None, "days": None}
    # VIX split (previous session's close vs the sample median)
    vsplit = None
    if vix:
        vv = np.array([vix.get(o["day"], np.nan) for o in obs])
        if np.isfinite(vv).sum() >= 8:
            med = float(np.nanmedian(vv))
            vsplit = {"median_vix": med}
            for label, m in (("high_vix", vv > med), ("low_vix", vv <= med)):
                m = m & np.isfinite(vv)
                a_v, k_v = _accuracy(pred[m], sgn[m]) if m.sum() else (None, 0)
                vsplit[label] = {"n": int(m.sum()), "accuracy": a_v, "n_predicted": k_v,
                                 "ic_pooled": float(np.corrcoef(rB[m], rR[m])[0, 1]) if m.sum() >= 3 and rB[m].std() > 0 and rR[m].std() > 0 else None}
    # family of declared cells (accuracies; the claim's cell decides)
    fam = {}
    thr_pred = np.where(B > 0.7, 1.0, np.where(B < 0.4, -1.0, 0.0))
    med_cut = np.empty(n)
    for idx in groups:
        med_cut[idx] = np.median(B[idx])
    rel_pred = np.sign(B - med_cut)
    for name, pr in (("follow_level_0.5", pred), ("contrarian_level_0.5", -pred), ("follow_threshold_0.7_0.4", thr_pred),
                     ("contrarian_threshold_0.7_0.4", -thr_pred), ("follow_symbol_median", rel_pred), ("contrarian_symbol_median", -rel_pred)):
        a_f, k_f = _accuracy(pr, sgn)
        fam[name] = {"accuracy": a_f, "n_predicted": k_f}
    w = np.array([float(o.get("tagged") or 0) for o in obs])
    valid = (pred != 0) & (sgn != 0) & (w > 0)
    fam["follow_level_0.5_count_weighted"] = {"accuracy": float(np.average((pred[valid] == sgn[valid]), weights=w[valid])) if valid.any() else None,
                                              "n_predicted": int(valid.sum())}
    out.update(accuracy=acc, n_predicted=k, acc_se=(math.sqrt(acc * (1 - acc) / k) if acc is not None and k else None),
               p_perm=p_acc, p_perm_deflated=sidak(p_acc, cells), p_perm_ic=p_ic, p_perm_ic_deflated=sidak(p_ic, cells),
               ic={"pooled": ic_pooled, "pooled_t_symbol_clustered": t_pooled, "n_symbols": int(gid.max() + 1),
                   "cross_sectional_mean": ic_cs, "cross_sectional_t_nw": t_cs, "n_days_cs": int(cs.size), "lag_nw": nw_lag(cs.size)},
               halves=halves, halves_cut=str(cut), net=_net_returns(obs, pred), vix_split=vsplit, family=fam,
               cells_deflated=cells, n_perm=n_perm)
    return out


def t414_criteria(res: dict) -> list:
    """[(name, ok, decisive_fail)] from ``bullish_ratio_test``'s output (None = not computable)."""
    acc, k = res.get("accuracy"), res.get("n_predicted") or 0
    if acc is None or k < 8:
        return [(f"accuracy >= {T414_ACC:.0%} in the follow direction", None, False),
                (f"permutation p < {T414_P} after {T414_CELLS}-cell deflation", None, False),
                (f"IC t > {T414_IC_T:g} (daily cross-sectional NW t and pooled symbol-clustered t)", None, False),
                ("same sign in both halves (accuracy edge and pooled IC)", None, False)]
    se = res.get("acc_se") or 0.0
    ub99 = acc + Z99 * se
    ok_acc = acc >= T414_ACC
    pd_ = res.get("p_perm_deflated")
    ok_p = None if pd_ is None else pd_ < T414_P
    ic = res.get("ic") or {}
    t1, t2 = ic.get("cross_sectional_t_nw"), ic.get("pooled_t_symbol_clustered")
    ok_ic = None if (t1 is None or t2 is None) else (t1 > T414_IC_T and t2 > T414_IC_T)
    h = res.get("halves") or {}
    hv = [h.get("first") or {}, h.get("second") or {}]
    if all(x.get("accuracy") is not None and x.get("ic_pooled") is not None for x in hv):
        ok_h = all(x["accuracy"] > 0.5 and x["ic_pooled"] > 0 for x in hv)
    else:
        ok_h = None
    return [(f"accuracy >= {T414_ACC:.0%} in the follow direction (observed {_pu(acc)}, one-sided 99% upper bound {_pu(ub99)})", ok_acc, ub99 < T414_ACC),
            (f"permutation p < {T414_P} after {T414_CELLS}-cell Sidak deflation (raw {_f(res.get('p_perm'), 4)}, deflated {_f(pd_, 4)})", ok_p, False),
            (f"IC t > {T414_IC_T:g} in both named constructions (cross-sectional NW t {_s(t1, 2)}, pooled symbol-clustered t {_s(t2, 2)})", ok_ic,
             bool(t2 is not None and t2 < -T414_IC_T)),
            ("same sign in both halves (accuracy edge > 0 and pooled IC > 0 in each half)", ok_h, False)]


def b6c_stocktwits_bullish_ratio(archive):
    """T-414: pre-open StockTwits bullish ratio -> sign of the open-to-next-open return (follow direction)."""
    weeks = _entry_names(archive, PREOPEN_PREFIX)
    miss = _missing(archive, [SPY_B] + (weeks or [PREOPEN_PREFIX + "<YYYY>-W<ww> (no week archived yet)"]))
    if miss:
        return miss
    sessions = _sessions(archive)
    msgs, wins = [], []
    for w in weeks:
        for r in _rows(archive, w):
            (wins if r.get("kind") == "window" else msgs).append(r)
    panel = preopen_panel(msgs, wins)
    syms = list(ST_PREOPEN_SYMBOLS)
    days = sorted({d for (_, d) in panel})
    raw_counts = {s: sum(1 for (ss, _) in panel if ss == s) for s in syms}
    # price marks
    marks: dict = {}
    mark_desc: dict = {}
    price_missing = []
    for s in syms:
        need = sorted({d for (ss, d) in panel if ss == s} | {ns for (ss, d) in panel if ss == s for ns in [next_session(sessions, d)] if ns})
        if s in CRYPTO_PID:
            pid = CRYPTO_PID[s]
            if not (_has(archive, f"coinbase-hourly-{pid}") or any(_has(archive, f"coinbase-1m-{pid}-{m}") for m in {d[:7] for d in need})):
                price_missing.append(s)
                continue
            mk, desc, _ = crypto_open_marks(archive, pid, need)
            marks[s], mark_desc[s] = mk, desc
        else:
            if not _has(archive, dh(s)):
                price_missing.append(s)
                continue
            dly = _daily(archive, s)
            marks[s] = {d: dly[d]["open"] for d in need if d in dly and dly[d]["open"]}
            mark_desc[s] = "Yahoo daily open (total-return basis)"
    drops = defaultdict(int)
    per_sym = defaultdict(int)
    obs, mismatches, unfiltered = [], 0, []
    for (s, d), p in sorted(panel.items()):
        if s not in syms:
            drops["stream not declared"] += 1
            continue
        if p["mismatch"]:
            mismatches += 1
        if s in price_missing:
            drops["no archived prices"] += 1
            continue
        if not p["complete"]:
            drops["window incomplete"] += 1
            continue
        if p["B"] is None:
            drops["no tagged message"] += 1
            continue
        ns = next_session(sessions, d)
        if d not in sessions or ns is None:
            drops["not a session / no next session"] += 1
            continue
        p0, p1 = marks[s].get(d), marks[s].get(ns)
        if not p0 or not p1:
            drops["entry or exit mark missing"] += 1
            continue
        o = {"sym": s, "day": d, "B": p["B"], "ret": p1 / p0 - 1.0, "tagged": p["tagged"], "cost": COST_RT.get(s, COST_RT_DEFAULT)}
        unfiltered.append(o)
        if p["tagged"] < T414_MIN_TAGGED:
            drops[f"fewer than {T414_MIN_TAGGED} tagged messages"] += 1
            continue
        obs.append(o)
        per_sym[s] += 1
    n = len(obs)
    res = bullish_ratio_test(obs, n_perm=T414_N_PERM, vix=_vix_prev(archive, sessions)) if n else {"n": 0}
    unf = None
    if len(unfiltered) >= 8 and len(unfiltered) != n:
        pr = np.sign(np.array([o["B"] for o in unfiltered]) - FOLLOW_CUT)
        sg = np.sign(np.array([o["ret"] for o in unfiltered]))
        a_u, k_u = _accuracy(pr, sg)
        unf = {"n": len(unfiltered), "accuracy": a_u, "n_predicted": k_u}
    crit = t414_criteria(res)
    verdict, why = _decide(crit, n, T414_MIN_N, "symbol-days")
    stat = {"theory": "T-414", "weeks": weeks, "n_weeks": len(weeks), "days": [days[0], days[-1]] if days else None, "n_days": len(days),
            "symbol_days_raw": int(sum(raw_counts.values())), "symbol_days_used": n, "min_n": T414_MIN_N, "per_symbol_used": dict(per_sym),
            "per_symbol_raw": raw_counts, "drops": dict(drops), "price_missing": price_missing, "marks": mark_desc,
            "window_count_mismatches": mismatches, "unfiltered": unf, "min_tagged": T414_MIN_TAGGED,
            "costs_round_trip_bps": {"SPY": 1, "QQQ": 1, "other": COST_RT_DEFAULT * 1e4},
            "earnings_flag": None, "earnings_note": "no earnings calendar is archived; the earnings-day control is not available",
            "result": res, "criteria": [(c[0], c[1]) for c in crit]}
    ic = res.get("ic") or {}
    h = res.get("halves") or {}
    net = res.get("net") or {}
    vs = res.get("vix_split")
    reason = (f"T-414: {len(weeks)} pre-open week bundle(s) archived ({days[0] if days else 'n/a'}..{days[-1] if days else 'n/a'}, {len(days)} days, "
              f"{sum(raw_counts.values())} raw symbol-days); {n} symbol-days used of min_n {T414_MIN_N} after drops {dict(drops)}"
              f"{'; no prices for ' + ', '.join(price_missing) if price_missing else ''}. "
              f"Follow rule {res.get('follow_rule', 'n/a')}: accuracy {_pu(res.get('accuracy'))} on {res.get('n_predicted', 0)} predicted days "
              f"(unfiltered {_pu(unf['accuracy']) if unf else 'same'}), permutation p {_f(res.get('p_perm'), 4)} -> Sidak-{T414_CELLS} {_f(res.get('p_perm_deflated'), 4)}; "
              f"IC pooled {_s(ic.get('pooled'), 3)} (symbol-clustered t {_s(ic.get('pooled_t_symbol_clustered'), 2)}, permutation p {_f(res.get('p_perm_ic'), 4)}), "
              f"daily cross-sectional IC {_s(ic.get('cross_sectional_mean'), 3)} (NW t {_s(ic.get('cross_sectional_t_nw'), 2)} over {ic.get('n_days_cs', 0)} days); "
              f"halves accuracy {_pu((h.get('first') or {}).get('accuracy'))} / {_pu((h.get('second') or {}).get('accuracy'))}, "
              f"pooled IC {_s((h.get('first') or {}).get('ic_pooled'), 3)} / {_s((h.get('second') or {}).get('ic_pooled'), 3)}; "
              f"net {_s(net.get('mean_net_bps'), 2)} bps/day (gross {_s(net.get('mean_gross_bps'), 2)}); "
              f"VIX split accuracy high {_pu((vs or {}).get('high_vix', {}).get('accuracy'))} / low {_pu((vs or {}).get('low_vix', {}).get('accuracy'))}; "
              f"crypto marks {mark_desc.get('BTC.X', 'n/a')} (BTC.X); earnings flags not available — {why}")
    return _out(stat, n, verdict, reason)


# ================================================================================== T-415: intensity -> RV ==

def intensity_panel(rows: Sequence[dict], min_samples: int = MIN_SAMPLES) -> tuple:
    """({stream: {day: mean per_hour}}, {stream: days dropped for too few samples})."""
    acc: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        v = r.get("value") or {}
        if v.get("stream") and v.get("day") and v.get("per_hour") is not None:
            acc[v["stream"]][v["day"]].append(float(v["per_hour"]))
    out, dropped = {}, {}
    for s, by in acc.items():
        out[s] = {d: float(np.mean(x)) for d, x in by.items() if len(x) >= min_samples}
        dropped[s] = sum(1 for x in by.values() if len(x) < min_samples)
    return out, dropped


def zscore_trailing(days: Sequence[str], x: Sequence[float], window: int = Z_WINDOW, min_obs: int = Z_MIN_OBS) -> np.ndarray:
    """z_t = (x_t - mean(x_{t-window..t-1})) / sd(...) over the trailing ``window`` observations strictly before t
    (>= ``min_obs`` of them, sd > 0); NaN otherwise."""
    x = np.asarray(x, float)
    z = np.full(x.size, np.nan)
    for i in range(x.size):
        w = x[max(0, i - window):i]
        w = w[np.isfinite(w)]
        if w.size >= min_obs:
            sd = w.std(ddof=1)
            if sd > 0:
                z[i] = (x[i] - w.mean()) / sd
    return z


def rv_from_hourly(bars: Sequence[tuple], kind: str = "session") -> dict:
    """{day: realised variance} from (t, o, h, l, c) bars: ``session`` = ET day, bars starting in [09:30, 16:00) ET
    (>= MIN_BARS_EQ); ``utc`` = UTC day, all bars (>= MIN_BARS_CRYPTO). RV = sum of squared log returns chained from
    the first bar's open."""
    by: dict = defaultdict(list)
    for t, o, h, l, c in bars:
        if kind == "session":
            dt = _et_dt(t)
            hm = dt.hour * 60 + dt.minute
            if not (9 * 60 + 30 <= hm < 16 * 60):
                continue
            by[dt.strftime("%Y-%m-%d")].append((t, o, c))
        else:
            by[_utc_day(t)].append((t, o, c))
    need = MIN_BARS_EQ if kind == "session" else MIN_BARS_CRYPTO
    out = {}
    for d, b in by.items():
        b.sort()
        if len(b) < need:
            continue
        px = [b[0][1]] + [x[2] for x in b]
        if any(p is None or p <= 0 for p in px):
            continue
        lr = np.diff(np.log(np.asarray(px, float)))
        out[d] = float(lr @ lr)
    return out


def parkinson(daily: dict) -> dict:
    """{day: ln(H/L)^2 / (4 ln 2)} from ``_daily`` rows."""
    out = {}
    for d, v in daily.items():
        h, l = v.get("high"), v.get("low")
        if h is not None and l is not None and float(h) > 0 and float(l) > 0 and float(h) >= float(l):
            out[d] = float(math.log(float(h) / float(l)) ** 2 / (4.0 * math.log(2.0)))
    return out


def sq_ret(daily: dict) -> dict:
    """{day: squared close-to-close log return} from ``_daily`` rows (total-return closes)."""
    ds = sorted(daily)
    out = {}
    for a, b in zip(ds, ds[1:]):
        ca, cb = daily[a]["close"], daily[b]["close"]
        if ca and cb and ca > 0 and cb > 0:
            out[b] = float(math.log(cb / ca) ** 2)
    return out


def har_rows(sym: str, rv: dict, z: dict, iv: dict, w: int, m: int, horizon: int = 1, abn: Optional[dict] = None) -> list:
    """Panel rows {sym, day, target_day, y, rv, rvw, rvm, iv, z, abn} on the asset's own RV calendar: y = the mean RV
    over the next ``horizon`` RV days, rvw / rvm the means of the last w / m RV days including t (windows complete)."""
    cal = sorted(rv)
    vals = np.array([rv[d] for d in cal], float)
    cs = np.concatenate([[0.0], np.cumsum(vals)])
    pos = {d: i for i, d in enumerate(cal)}
    out = []
    for d, zt in z.items():
        i = pos.get(d)
        if i is None or not np.isfinite(zt) or i + 1 < m or i + horizon >= len(cal) or d not in iv:
            continue
        y = float((cs[i + 1 + horizon] - cs[i + 1]) / horizon)
        out.append({"sym": sym, "day": d, "target_day": cal[i + 1], "y": y, "rv": float(vals[i]), "rvw": float((cs[i + 1] - cs[i + 1 - w]) / w),
                    "rvm": float((cs[i + 1] - cs[i + 1 - m]) / m), "iv": float(iv[d]), "z": float(zt),
                    "abn": float(zt > Z_ABNORMAL) if abn is None else float(abn[d])})
    return out


def dk_ols(y, X, tidx, lag: int) -> Optional[dict]:
    """Pooled OLS y = a + X b with Driscoll-Kraay s.e.: the per-period sums of the score are HAC-smoothed (Bartlett,
    ``lag``). Returns {beta (with intercept first), se, t, r2, n, T}."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(y.size, -1)
    n, k = X.shape
    if n < k + 4:
        return None
    Z = np.column_stack([np.ones(n), X])
    try:
        ZtZi = np.linalg.inv(Z.T @ Z)
    except np.linalg.LinAlgError:
        return None
    b = ZtZi @ (Z.T @ y)
    e = y - Z @ b
    periods, inv = np.unique(np.asarray(tidx), return_inverse=True)
    H = np.zeros((periods.size, k + 1))
    np.add.at(H, inv, Z * e[:, None])
    S = H.T @ H
    for l in range(1, min(lag, periods.size - 1) + 1):
        G = H[l:].T @ H[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    V = ZtZi @ S @ ZtZi
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(e @ e) / tss if tss > 0 else 0.0
    t = np.array([bb / ss if ss > 0 else np.nan for bb, ss in zip(b, se)])
    return {"beta": b, "se": se, "t": t, "r2": r2, "n": int(n), "T": int(periods.size)}


_BASE = ("rv", "rvw", "rvm", "iv")


def _lg(v: float) -> float:
    return math.log(max(float(v), 1e-12))


def har_test(rows: Sequence[dict], zkey: str = "z", horizon: int = 1, cells: int = T415_CELLS, log: bool = True) -> dict:
    """c, its Driscoll-Kraay t and the incremental R^2 of ``zkey`` over HAR+IV on ``rows``: the log-HAR (the deciding
    form) or, with ``log=False``, the literal levels regression (a diagnostic)."""
    if len(rows) < 12:
        return {"n": len(rows), "c": None, "t": None, "dr2": None, "r2_full": None, "r2_base": None, "T": 0, "lag": None, "p_sidak": None}
    f = _lg if log else (lambda v: v)
    y = np.array([f(r["y"]) for r in rows])
    Xb = np.array([[f(r[c]) for c in _BASE] for r in rows])
    zc = np.array([r[zkey] for r in rows])
    tidx = np.array([r["day"] for r in rows])
    lag = max(nw_lag(np.unique(tidx).size), horizon)
    base = dk_ols(y, Xb, tidx, lag)
    full = dk_ols(y, np.column_stack([Xb, zc]), tidx, lag)
    if base is None or full is None:
        return {"n": len(rows), "c": None, "t": None, "dr2": None, "r2_full": None, "r2_base": None, "T": 0, "lag": lag, "p_sidak": None}
    t = float(full["t"][-1]) if np.isfinite(full["t"][-1]) else None
    return {"n": len(rows), "T": full["T"], "lag": lag, "c": float(full["beta"][-1]), "se": float(full["se"][-1]), "t": t,
            "p_one": _p_one(t), "p_sidak": sidak(_p_one(t), cells), "r2_full": full["r2"], "r2_base": base["r2"],
            "dr2": full["r2"] - base["r2"], "betas_full": [float(v) for v in full["beta"]], "betas_t": [float(v) if np.isfinite(v) else None for v in full["t"]]}


def qlike(rv: np.ndarray, f: np.ndarray) -> np.ndarray:
    r = rv / f
    return r - np.log(r) - 1.0


def walk_forward_qlike(rows: Sequence[dict], zkey: str = "z", min_train: int = MIN_TRAIN, embargo: int = EMBARGO,
                       cells: int = T415_CELLS, floor_q: float = QLIKE_FLOOR_Q, log: bool = True) -> dict:
    """Expanding walk-forward over sampled days: at each origin (from the ``min_train``-th day) HAR+IV and HAR+IV+z are
    fit on rows whose target lies >= ``embargo`` sampled days before the origin and forecast the origin's rows. Log form
    (deciding): F = exp(fitted ln RV + s^2/2), s^2 the training residual variance. Levels (diagnostic): forecasts floored
    at the ``floor_q`` quantile of the training targets (``floored_share`` reported). QLIKE per forecast; Diebold-Mariano
    on the daily cross-sectional mean loss difference (base - full), one-sided for an improvement, Sidak-deflated over
    ``cells``."""
    days = sorted({r["day"] for r in rows})
    pos = {d: i for i, d in enumerate(days)}
    horizon = 1
    rd = np.array([pos[r["day"]] for r in rows])
    tgt = rd + horizon
    y = np.array([r["y"] for r in rows])
    f = _lg if log else (lambda v: v)
    yy = np.array([f(v) for v in y])
    Xb = np.column_stack([np.ones(len(rows)), np.array([[f(r[c]) for c in _BASE] for r in rows])])
    Xf = np.column_stack([Xb, np.array([r[zkey] for r in rows])])
    diffs, lb, lf, n_fc, origins, floored = [], [], [], 0, [], 0
    for k in range(min_train, len(days)):
        tr = tgt <= k - embargo
        te = rd == k
        if tr.sum() < 12 or not te.any():
            continue
        try:
            bb = np.linalg.lstsq(Xb[tr], yy[tr], rcond=None)[0]
            bf = np.linalg.lstsq(Xf[tr], yy[tr], rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        if log:
            sb = float(np.var(yy[tr] - Xb[tr] @ bb))
            sf = float(np.var(yy[tr] - Xf[tr] @ bf))
            fb = np.exp(Xb[te] @ bb + sb / 2.0)
            ff = np.exp(Xf[te] @ bf + sf / 2.0)
        else:
            floor = max(float(np.quantile(y[tr], floor_q)), 1e-12)
            rb, rf = Xb[te] @ bb, Xf[te] @ bf
            floored += int((rf < floor).sum())
            fb, ff = np.maximum(rb, floor), np.maximum(rf, floor)
        qb, qf = qlike(y[te], fb), qlike(y[te], ff)
        diffs.append(float((qb - qf).mean()))
        lb.append(float(qb.mean()))
        lf.append(float(qf.mean()))
        n_fc += int(te.sum())
        origins.append(days[k])
    d = np.asarray(diffs, float)
    base = {"form": "log-HAR, F = exp(fit + s^2/2)" if log else "levels, forecasts floored", "n_origins": int(d.size), "n_forecasts": n_fc,
            "origins": [origins[0], origins[-1]] if origins else None, "embargo": embargo, "min_train": min_train,
            "floored_share": (floored / n_fc if (not log and n_fc) else None)}
    if d.size < 8:
        base.update(dm_t=None, dm_p=None, dm_p_sidak=None, qlike_base=None, qlike_full=None, share_days_improved=None)
        return base
    lag = nw_lag(d.size)
    t = nw_t(d, lag)
    base.update(dm_t=t, dm_p=_p_one(t), dm_p_sidak=sidak(_p_one(t), cells), dm_lag=lag, qlike_base=float(np.mean(lb)),
                qlike_full=float(np.mean(lf)), mean_diff=float(d.mean()), share_days_improved=float((d > 0).mean()))
    return base


def t415_criteria(z_in: dict, a_in: dict, z_wf: dict, a_wf: dict) -> list:
    """[(name, ok, decisive_fail)] for the two pass criteria, each judged on both readings (z continuous, A = 1{z > 2})."""
    def ok_reg(r):
        if r.get("t") is None or r.get("dr2") is None:
            return None
        return bool(r["t"] > T415_T and r["dr2"] >= T415_DR2)

    def ok_wf(w):
        if w.get("dm_p_sidak") is None or w.get("qlike_full") is None:
            return None
        return bool(w["dm_p_sidak"] < T415_DM_P and w["qlike_full"] < w["qlike_base"])
    o1, o2 = ok_reg(z_in), ok_reg(a_in)
    reg_ok = None if (o1 is None or o2 is None) else (o1 and o2)
    w1, w2 = ok_wf(z_wf), ok_wf(a_wf)
    wf_ok = None if (w1 is None or w2 is None) else (w1 and w2)
    return [(f"c Driscoll-Kraay t > {T415_T:g} with incremental R^2 >= {T415_DR2:.0%}, both readings (z: t {_s(z_in.get('t'), 2)}, dR2 {_pu(z_in.get('dr2'))}, "
             f"Sidak-{T415_CELLS} p {_f(z_in.get('p_sidak'), 4)}; 1{{z>2}}: t {_s(a_in.get('t'), 2)}, dR2 {_pu(a_in.get('dr2'))})", reg_ok,
             bool(z_in.get("t") is not None and z_in["t"] < -T415_T)),
            (f"out-of-sample QLIKE improvement with DM p < {T415_DM_P} after Sidak-{T415_CELLS} deflation, both readings (z: DM t {_s(z_wf.get('dm_t'), 2)}, "
             f"p {_f(z_wf.get('dm_p'), 4)} -> {_f(z_wf.get('dm_p_sidak'), 4)}; 1{{z>2}}: DM t {_s(a_wf.get('dm_t'), 2)}, p {_f(a_wf.get('dm_p'), 4)} -> "
             f"{_f(a_wf.get('dm_p_sidak'), 4)})", wf_ok, False)]


def _iv_series(archive, sym: str) -> tuple:
    """({day: implied DAILY variance}, source name) for an intensity symbol, or ({}, None)."""
    if sym in CBOE_IV:
        name = cboe_b(CBOE_IV[sym])
        if not _has(archive, name):
            return {}, None
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            if v.get("close") is not None and float(v["close"]) > 0:
                out[v["day"]] = (float(v["close"]) / 100.0) ** 2 / 252.0
        return out, name
    if sym in DVOL_IV:
        name = dvol_b(DVOL_IV[sym])
        if not _has(archive, name):
            return {}, None
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            if v.get("close") is not None and float(v["close"]) > 0 and v.get("ts_ms") is not None:
                out[_utc_day(float(v["ts_ms"]) / 1000.0)] = (float(v["close"]) / 100.0) ** 2 / 365.0
        return out, name
    if sym in DOLT_IV:
        if not _has(archive, DOLT_B):
            return {}, None
        def load():
            best: dict = {}
            for r in _rows(archive, DOLT_B):
                v = r["value"]
                if v.get("iv_current") is None or v.get("quote_date") is None:
                    continue
                key = (v["symbol"], v["quote_date"])
                snap = v.get("snapshot_date") or ""
                if key not in best or snap < best[key][0]:
                    best[key] = (snap, float(v["iv_current"]))
            out: dict = defaultdict(dict)
            for (s, d), (_, iv) in best.items():
                if iv > 0:
                    out[s][d] = iv ** 2 / 252.0
            return out
        return dict(_cached(archive, "dolt_iv", load).get(sym, {})), DOLT_B
    return {}, None


def _rv_series(archive, sym: str) -> tuple:
    """({day: RV}, estimator description) for an intensity symbol, or ({}, None)."""
    if sym in CRYPTO_PID:
        pid = CRYPTO_PID[sym]
        for name in (f"coinbase-hourly-{pid}", hourly_b(pid)):
            if _has(archive, name):
                return rv_from_hourly(_bars(archive, name), "utc"), f"hourly RV over the UTC day ({name})"
        return {}, None
    name = hourly_b(sym)
    if _has(archive, name):
        return rv_from_hourly(_bars(archive, name), "session"), f"intraday hourly RV 09:30-16:00 ET ({name})"
    if _has(archive, dh(sym)):
        return parkinson(_daily(archive, sym)), f"Parkinson high-low of the daily bar ({dh(sym)}; no hourly bars archived)"
    return {}, None


def build_t415_panel(archive, intensity: dict) -> dict:
    """Rows of the primary cell and the family cells per symbol, with the per-symbol bookkeeping."""
    syms = list(ST_INTENSITY_SYMBOLS)
    rows_primary, fam_rows, info = [], defaultdict(list), {}
    drops = defaultdict(int)
    for s in syms:
        days_x = sorted(intensity.get(s, {}))
        if not days_x:
            info[s] = {"used": 0, "reason": "no intensity samples"}
            drops["no intensity samples"] += 1
            continue
        z = zscore_trailing(days_x, [intensity[s][d] for d in days_x])
        zmap = {d: zz for d, zz in zip(days_x, z) if np.isfinite(zz)}
        rv, rv_src = _rv_series(archive, s)
        iv, iv_src = _iv_series(archive, s)
        if not rv:
            info[s] = {"used": 0, "reason": "no realised-variance source archived", "days_with_z": len(zmap)}
            drops["no RV source"] += 1
            continue
        if not iv:
            info[s] = {"used": 0, "reason": "no implied-volatility source archived", "days_with_z": len(zmap), "rv": rv_src}
            drops["no IV source"] += 1
            continue
        w, m = HAR_CRYPTO if s in CRYPTO_PID else HAR_EQ
        pr = har_rows(s, rv, zmap, iv, w, m, 1)
        rows_primary.extend(pr)
        fam_rows[("hourly", 5)].extend(har_rows(s, rv, zmap, iv, w, m, 5))
        if s not in CRYPTO_PID and _has(archive, dh(s)):
            dly = _daily(archive, s)
            for nm, est in (("parkinson", parkinson(dly)), ("sq_ret", sq_ret(dly))):
                for hz in (1, 5):
                    fam_rows[(nm, hz)].extend(har_rows(s, est, zmap, iv, w, m, hz))
        no_iv = sum(1 for d in zmap if d not in iv)
        no_rv = sum(1 for d in zmap if d in iv and d not in rv)
        info[s] = {"used": len(pr), "days_sampled": len(days_x), "days_with_z": len(zmap), "days_without_iv": no_iv, "days_without_rv": no_rv,
                   "rv": rv_src, "iv": iv_src, "har_lags": [w, m]}
    return {"rows": rows_primary, "family": dict(fam_rows), "info": info, "drops": dict(drops)}


def b6c_stocktwits_intensity_rv(archive):
    """T-415: abnormal StockTwits intensity (z) -> next-day realised variance beyond HAR lags and same-day IV."""
    weeks = _entry_names(archive, INTENSITY_PREFIX)
    miss = _missing(archive, [SPY_B] + (weeks or [INTENSITY_PREFIX + "<YYYY>-W<ww> (no week archived yet)"]))
    if miss:
        return miss
    _sessions(archive)
    rows = []
    for w in weeks:
        rows.extend(r for r in _rows(archive, w) if r.get("kind") == "intensity-sample")
    intensity, few = intensity_panel(rows)
    days = sorted({r["value"]["day"] for r in rows})
    P = build_t415_panel(archive, intensity)
    prow = P["rows"]
    n = len(prow)
    z_in = har_test(prow, "z", 1)
    a_in = har_test(prow, "abn", 1)
    z_lev = har_test(prow, "z", 1, log=False)
    z_wf = walk_forward_qlike(prow, "z") if n else {"n_origins": 0}
    a_wf = walk_forward_qlike(prow, "abn") if n else {"n_origins": 0}
    z_wf_lev = walk_forward_qlike(prow, "z", log=False) if n else {"n_origins": 0}
    fam = {f"{nm}_h{hz}": har_test(rs, "z", hz) for (nm, hz), rs in sorted(P["family"].items())}
    fam["hourly_h1"] = {k: z_in.get(k) for k in ("n", "T", "c", "t", "dr2", "p_sidak")}
    fomc = _fomc_days(archive)
    ex_fomc = har_test([r for r in prow if r["target_day"] not in fomc], "z", 1) if fomc else None
    crit = t415_criteria(z_in, a_in, z_wf, a_wf)
    verdict, why = _decide(crit, n, T415_MIN_N, "symbol-days")
    abn_share = float(np.mean([r["abn"] for r in prow])) if n else None
    per_sym = {s: v.get("used", 0) for s, v in P["info"].items()}
    stat = {"theory": "T-415", "weeks": [weeks[0], weeks[-1]] if weeks else None, "n_weeks": len(weeks), "days_sampled": [days[0], days[-1]] if days else None,
            "n_days_sampled": len(days), "symbol_days_used": n, "min_n": T415_MIN_N, "per_symbol": P["info"], "symbols_dropped": P["drops"],
            "days_with_too_few_samples": few, "z_window": Z_WINDOW, "z_min_obs": Z_MIN_OBS, "abnormal_share": abn_share,
            "specification": "pooled log-HAR+IV with Driscoll-Kraay s.e. (deciding); the literal levels regression is the 'levels' diagnostic",
            "in_sample": {"z": z_in, "abnormal": a_in, "levels_z": z_lev}, "walk_forward": {"z": z_wf, "abnormal": a_wf, "levels_z": z_wf_lev},
            "family": fam, "cells_deflated": T415_CELLS, "ex_fomc_target_days": ex_fomc, "n_fomc_days": len(fomc),
            "earnings_flag": None, "earnings_note": "no earnings calendar is archived; the earnings-day control is not available",
            "criteria": [(c[0], c[1]) for c in crit]}
    used = [s for s, k in per_sym.items() if k]
    dropped_txt = ", ".join(f"{s} ({v.get('reason')})" for s, v in P["info"].items() if not v.get("used"))
    reason = (f"T-415: {len(weeks)} intensity week bundle(s) ({days[0] if days else 'n/a'}..{days[-1] if days else 'n/a'}, {len(days)} sampled days); "
              f"{n} symbol-days in the regression of min_n {T415_MIN_N} over {len(used)} of {len(ST_INTENSITY_SYMBOLS)} streams"
              f"{' (dropped: ' + dropped_txt + ')' if dropped_txt else ''}; "
              f"z on the trailing {Z_WINDOW} sampled days, abnormal share {_pu(abn_share)}. In-sample pooled log-HAR+IV (Driscoll-Kraay lag {z_in.get('lag')}): "
              f"c t {_s(z_in.get('t'), 2)}, incremental R^2 {_pu(z_in.get('dr2'))} (R^2 {_f(z_in.get('r2_base'))} -> {_f(z_in.get('r2_full'))}); "
              f"1{{z>2}}: t {_s(a_in.get('t'), 2)}, dR2 {_pu(a_in.get('dr2'))}; literal levels diagnostic t {_s(z_lev.get('t'), 2)}, dR2 {_pu(z_lev.get('dr2'))}. "
              f"Walk-forward ({z_wf.get('n_origins', 0)} origins, {z_wf.get('n_forecasts', 0)} forecasts, embargo {EMBARGO}): QLIKE {_g(z_wf.get('qlike_base'))} -> "
              f"{_g(z_wf.get('qlike_full'))}, DM t {_s(z_wf.get('dm_t'), 2)}, p {_f(z_wf.get('dm_p'), 4)} -> Sidak-{T415_CELLS} {_f(z_wf.get('dm_p_sidak'), 4)}; "
              f"1{{z>2}} DM t {_s(a_wf.get('dm_t'), 2)}; levels diagnostic DM t {_s(z_wf_lev.get('dm_t'), 2)} with {_pu(z_wf_lev.get('floored_share'))} of forecasts floored. "
              f"Family (t, dR2): "
              + "; ".join(f"{k} {_s(v.get('t'), 2)}/{_pu(v.get('dr2'))}" for k, v in fam.items())
              + f". Ex-FOMC target days t {_s((ex_fomc or {}).get('t'), 2)}; earnings flags not available — {why}")
    return _out(stat, n, verdict, reason)


HARNESSES = {
    "b6c_stocktwits_bullish_ratio": b6c_stocktwits_bullish_ratio,
    "b6c_stocktwits_intensity_rv": b6c_stocktwits_intensity_rv,
}

THEORY_MAP = {
    "T-414": "b6c_stocktwits_bullish_ratio",
    "T-415": "b6c_stocktwits_intensity_rv",
}
