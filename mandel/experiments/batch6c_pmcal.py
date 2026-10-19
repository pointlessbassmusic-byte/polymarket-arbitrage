"""
Batch 6c, group ``pmcal``: prediction-market calibration and market-structure claims on the Polymarket and Kalshi
histories fetched by ``mandel.data.pm_history`` (2026-10-15) and the legacy polymarket-* bundles.
=====================================================================================================================

Six claims, each tested on its own claim, trial.pass and trial.min_n as worded (MANDEL.md section 2, rules 1-12):

  * T-12   Brier skill per volume quartile at the 7-day horizon rises monotonically and the top-bottom gap's interval
           excludes 0. The quartiles are by POINT-IN-TIME volume at the decision (close - 7 d): cumulative taker shares
           from ``polymarket-volume-hourly-<M>`` (hours ending at or before the decision; or volumeNum minus the hours
           after it when the fetch log says the market is complete from an earlier hour). Gamma volumeNum is an
           end-of-life value (the registry's own stated leak) and is reported as a sensitivity only. The scored
           population is the fetcher's unbiased hash sample (fetch-log reason 'sample'): the scheduled-event family
           markets are topic-selected, high-volume by construction and predictable a week before a scheduled print, so
           the family-inclusive mixture is a reported sensitivity; long-lived (>= 100 d) markets have no point-in-time
           volume and are absent (stated). Per-quartile and adjacent-increment intervals, the zero-volume (quote-skill)
           share of Q1 and the age-at-decision confound are reported with the primary.
  * T-378  Favorite bought at its first observed price in [0.95, 0.99] with 1-60 days to resolution, one observation per
           market per horizon bucket (1-7, 8-30, 31-60 d), Polymarket and Kalshi (KXCPI, KXFED, KXFEDDECISION,
           KXPAYROLLS daily candles, bought at the ask). Market-level annualized net return minus the hurdle. Days to
           resolution for the window and the bucket are measured from the resolution date known at the decision (the
           scheduled endDate / Kalshi close_time); payoff and hold run to the realized resolution; the realized-close
           construction and the hold <= 2 d observations' weight in the equal-weighted mean are reported.
  * T-31   Walk-forward log loss of a small MLP against logistic regression on (logit price, log point-in-time volume,
           log days to the scheduled end), decisions at 1, 3, 7 and 30 days before close, folds by close date with an
           embargo.
  * T-32   Effective rank (entropy of normalised eigenvalues) of the correlation matrix of daily price changes across
           concurrent markets, one market per event (the same-event control), against the Marchenko-Pastur bound.
  * T-359  Leading side priced in [0.90, 0.98] at the scheduled end date minus 3, 2 or 1 days (first qualifying day),
           bought at p + 0.01 + the market's own fee, held to resolution; the horizon contrast is the same rule executed
           unconditionally at end - 14 d (every market qualifying then; the pairing on markets qualifying at both horizons
           conditions on a future path and is a sensitivity); calibration slope of outcome on the final-3-day price over
           every resolved market.
  * T-316  2.5-sd daily logit shock (trailing 30-day sd, >= 20 changes) in markets priced in [0.15, 0.85]; buy the
           shock direction at the next daily snapshot, exit three days later or at resolution; 2-cent round trip;
           price- and days-to-end-matched non-shock control days; Kalshi macro candles as the replication set.

Data (every bundle through ``archive.load``; month bundles are probed through ``archive.entries`` and are optional)
  * Polymarket metadata: ``polymarket-closed-markets-<YYYY-MM>`` (2023-01 .. 2026-10; 2025-10 is not archived) and
    the legacy ``polymarket-closed-markets``, slimmed to the fields used and restricted to markets with daily
    history. Rows are end-of-life Gamma snapshots (available_at = fetch time); only fields fixed at listing (endDate,
    startDate, events, fee fields) or revealed at resolution (outcomePrices, closedTime) are read, and ``endDate`` may
    have been edited after listing (every row has hasReviewedDates True, so umaEndDate != endDate is the only edit
    signal; T-359 reports the sensitivity).
  * Daily prices: ``polymarket-price-history-daily-<YYYY-MM>`` plus the legacy bundle: {market_id, token, p, t}; a
    point is the YES price prevailing AT t (about 00:00 UTC; available_at = t), so the price "h days before close"
    is the last point at or before close - h d, at most 3 days stale (the T-01 convention, ``markets.price_at_horizons``).
    close = min(closedTime, endDate) (``markets.resolved_outcomes``); a cutoff after endDate is a post-event price and
    is skipped. Selection: every market living >= 100 days, every scheduled-event family market and a hash sample of
    200 per month of the rest, within the universe volumeNum >= $10k and lifetime >= 3 days (``polymarket-fetch-log``
    gives each market's reason; the legacy 399 are the volume-selected top). The reasons are reported, not filtered.
  * Point-in-time volume: ``polymarket-volume-hourly-<YYYY-MM>`` (taker-only trades by hour; available_at = hour end)
    with completeness from the fetch log ('trades:<id>': complete, complete_from_hour, volumeNum).
  * Open markets (T-32 only): ``polymarket-open-markets`` and ``polymarket-open-price-history-daily`` (one hash-chosen
    market per event, alive on 2026-10-16: survival to the snapshot is a selection, stated).
  * Kalshi: ``kalshi-settled-markets-<S>`` (result yes/no, close_time, settlement_ts, event_ticker) and
    ``kalshi-candles-daily-<S>`` (yes_bid / yes_ask / price close; available_at = candle end). Illiquid candles
    (bid 0 or a wide spread) are filtered as the fetcher advises.
  * Rates: ``fred-DTB3`` as a 91-day discount yield, r = -ln(1 - d/100 * 91/360) / (91/365), known from its
    available_at (rule 7). The T-378 hurdle is the library rule's own proxy, box = DTB3 + 35 bp (the archived
    box-rates-bdg ends 2018-03; ``daily-history-BOXX``, when archived, gives a reported sensitivity).

Conventions
  * Point in time (rules 4, 12). Every decision reads the daily snapshot at or before the decision time and the volume
    of hours ending at or before it; forward windows start after the decision; the days-to-end feature uses the
    scheduled endDate, never closedTime. T-316 detects the shock on snapshot t and fills at snapshot t+1.
  * Costs as stated (rule 9). Polymarket fee = rate x p x (1 - p) per share with the rate of the market's feeType
    (crypto 0.07, sports / economics / culture / weather 0.05, politics / finance / mentions / tech 0.04,
    geopolitics 0; library notes), charged only when feesEnabled (T-359 "any market fee", T-378 "venue fees"; the
    schedule applied to every market is a reported sensitivity). Kalshi taker fee 0.07 x p x (1 - p) per contract,
    none at settlement. T-359 spread 1 cent; T-316 2 cents round trip.
  * Intervals (rule 6). Percentile bootstrap of the (ratio) mean with whole clusters resampled: clusters are Gamma
    events[0].id (else negRiskMarketID, else the market; ``markets.event_clusters`` keys) on Polymarket and
    event_ticker on Kalshi; T-316 clusters by market as its trial says. 2,000 draws, seed 0, two-sided 95%; "lower
    95% bound" is the lower end of the two-sided interval; a bootstrap p-value is the share of bootstrap means on the
    wrong side of 0. Differences (vs matched controls, vs the day-14 entry, MLP vs logit) are paired per unit.
  * Rule 11. T-378's trial clusters "by event and resolution day": both constructions must pass and a disagreement
    is undecided. T-359's null names the Bernoulli(p) parametric bootstrap beside the cluster bootstrap: both must
    give p < 0.05. T-32's window statistic is pooled over every window start (rule 10) and the per-window range is
    reported.
  * Below min_n (rule 5): never supported; a failing criterion counts only when its interval lies wholly on the wrong
    side (or the failure cannot be cured by more data); any other failure is undecided.
  * DSR: ``backtest_eval.deflated_sharpe_ratio`` on the per-unit returns in time order with the trial's n_trials and
    the iid-null variance floor (no per-trial Sharpes are recorded).

Verdicts use ``underlying2._verdict``; stat dicts are JSON-serialisable (NaN / inf -> None); ``n`` is in the claim's
own units (markets, entries or events) and every reason states the numbers that decide each criterion.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.markets import resolved_outcomes
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio
from mandel.validation.scoring import murphy_decomposition

DAY = 86_400.0
N_BOOT = 2000
SEED = 0
FEE_RATES = {"crypto": 0.07, "sports": 0.05, "economics": 0.05, "culture": 0.05, "weather": 0.05,
             "politics": 0.04, "finance": 0.04, "mentions": 0.04, "tech": 0.04, "geopolitics": 0.0}
FEE_DEFAULT = 0.05
KALSHI_FEE = 0.07
BOX_SPREAD = 0.0035            # library rule: box rate = DTB3 + 35 bp until enough T-186 captures exist
HURDLE_PREMIUM = 0.02
KALSHI_SERIES = ("KXCPI", "KXFED", "KXFEDDECISION", "KXPAYROLLS")
LEGACY_MARKETS = "polymarket-closed-markets"
LEGACY_DAILY = "polymarket-price-history-daily"
FETCH_LOG = "polymarket-fetch-log"
OPEN_MARKETS = "polymarket-open-markets"
OPEN_DAILY = "polymarket-open-price-history-daily"
DTB3_B = "fred-DTB3"
BOXX_B = "daily-history-BOXX"
MONTH_MARKETS_RE = r"polymarket-closed-markets-\d{4}-\d{2}"
MONTH_DAILY_RE = r"polymarket-price-history-daily-\d{4}-\d{2}"
MONTH_VOLUME_RE = r"polymarket-volume-hourly-\d{4}-\d{2}"
VOLUME_FAMILY = "polymarket-volume-hourly-<YYYY-MM>"


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


def _bundle_names(archive, pattern: str) -> list[str]:
    """Archived bundle names matching ``pattern`` (full match), sorted; [] when the archive cannot list."""
    try:
        names = [e.name for e in archive.entries()]
    except Exception:
        return []
    return sorted(n for n in names if re.fullmatch(pattern, n))


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ts(s) -> Optional[float]:
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        d = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _h01(key: str) -> float:
    """Uniform in [0, 1) fixed by ``key``: deterministic selection independent of prices, volumes and outcomes."""
    return int(hashlib.sha256(("mandel-pmcal:" + str(key)).encode()).hexdigest()[:13], 16) / 16 ** 13


def _clean(x):
    """JSON-safe copy: numpy scalars to Python, NaN / inf to None."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _slim(m: dict) -> dict:
    ev = m.get("events")
    if isinstance(ev, str):
        try:
            ev = json.loads(ev)
        except ValueError:
            ev = None
    eid = ev[0].get("id") if isinstance(ev, list) and ev and isinstance(ev[0], dict) else None
    return {"id": str(m.get("id")), "umaResolutionStatus": m.get("umaResolutionStatus"), "outcomePrices": m.get("outcomePrices"),
            "outcomes": m.get("outcomes"), "closedTime": m.get("closedTime"), "endDate": m.get("endDate"), "startDate": m.get("startDate"),
            "volumeNum": m.get("volumeNum"), "question": m.get("question", ""), "negRisk": m.get("negRisk"),
            "negRiskMarketID": m.get("negRiskMarketID"), "event_id": None if eid is None else str(eid),
            "feesEnabled": bool(m.get("feesEnabled")), "feeType": m.get("feeType"), "umaEndDate": m.get("umaEndDate")}


def cluster_key(s: dict) -> str:
    """Dependence cluster of a slim market: event, else negRisk group, else the market (``markets.event_clusters`` keys)."""
    if s.get("event_id") is not None:
        return f"event:{s['event_id']}"
    if s.get("negRiskMarketID"):
        return f"negrisk:{s['negRiskMarketID']}"
    return f"market:{s['id']}"


def _daily_series(archive) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """market id -> (t sorted, YES price) from every daily month bundle plus the legacy bundle (union, de-duplicated by t)."""
    def load():
        by: dict[str, dict[float, float]] = defaultdict(dict)
        names = _bundle_names(archive, MONTH_DAILY_RE) + ([LEGACY_DAILY] if _has(archive, LEGACY_DAILY) else [])
        for name in names:
            for r in archive.load(name):
                v = r["value"]
                p = _num(v.get("p")); t = _num(v.get("t"))
                if p is None or t is None:
                    continue
                by[str(v["market_id"])][t] = min(max(p, 0.0), 1.0)
        out = {}
        for mid, d in by.items():
            ts = np.array(sorted(d)); out[mid] = (ts, np.array([d[t] for t in ts]))
        return out
    return _cached(archive, "daily", load)


def _closed_meta(archive) -> dict[str, dict]:
    """Slim metadata of every closed market that has daily history (month bundles first, the legacy bundle for the rest)."""
    def load():
        ids = set(_daily_series(archive))
        out: dict[str, dict] = {}
        names = _bundle_names(archive, MONTH_MARKETS_RE) + ([LEGACY_MARKETS] if _has(archive, LEGACY_MARKETS) else [])
        for name in names:
            for r in archive.load(name):
                m = r.get("value") or {}
                mid = str(m.get("id"))
                if mid in ids and mid not in out:
                    out[mid] = _slim(m)
        return out
    return _cached(archive, "closed_meta", load)


def _outcomes(archive) -> dict[str, dict]:
    """``markets.resolved_outcomes`` on the slim metadata: binary markets resolved 0/1 with close = min(closedTime, endDate)."""
    return _cached(archive, "outcomes", lambda: resolved_outcomes([{"value": s} for s in _closed_meta(archive).values()]))


def _void_count(meta: dict) -> int:
    n = 0
    for s in meta.values():
        op = s.get("outcomePrices")
        try:
            op = json.loads(op) if isinstance(op, str) else op
        except (TypeError, ValueError):
            continue
        if op and len(op) == 2 and all(abs(float(x) - 0.5) < 1e-9 for x in op):
            n += 1
    return n


def _fetch_log(archive) -> dict:
    """{'daily': {id: reason}, 'trades': {id: {complete, complete_from_hour, volumeNum}}} from polymarket-fetch-log."""
    def load():
        daily, trades = {}, {}
        if _has(archive, FETCH_LOG):
            for r in archive.load(FETCH_LOG):
                v = r.get("value") or {}
                if v.get("product") == "daily":
                    daily[str(v.get("id"))] = v.get("reason")
                elif v.get("product") == "trades":
                    trades[str(v.get("id"))] = {"complete": bool(v.get("complete")), "complete_from_hour": _num(v.get("complete_from_hour")),
                                                "volumeNum": _num(v.get("volumeNum"))}
        return {"daily": daily, "trades": trades}
    return _cached(archive, "fetch_log", load)


def _volume(archive) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """market id -> (hour starts sorted, cumulative taker shares) from every polymarket-volume-hourly month."""
    def load():
        by: dict[str, dict[float, float]] = defaultdict(dict)
        for name in _bundle_names(archive, MONTH_VOLUME_RE):
            for r in archive.load(name):
                v = r["value"]
                t = _num(v.get("t")); sh = _num(v.get("shares"))
                if t is None or sh is None:
                    continue
                by[str(v["market_id"])][t] = by[str(v["market_id"])].get(t, 0.0) + sh
        out = {}
        for mid, d in by.items():
            hs = np.array(sorted(d)); out[mid] = (hs, np.cumsum([d[h] for h in hs]))
        return out
    return _cached(archive, "volume", load)


def pit_volume(hours: np.ndarray, cum: np.ndarray, t: float, log: Optional[dict]) -> Optional[float]:
    """Taker shares known at ``t``: the hours ENDING at or before t (an hour's row is available at its end, so the hour
    holding t is not yet known). The cumulative sum when the market's trades are complete, else volumeNum minus the
    shares of the hours ending after t when the fetch log says the history is complete from an hour at or before t
    (every later hour is then complete); None otherwise (point-in-time volume unknown)."""
    if log is None:
        return None
    k = int(np.searchsorted(hours, t - 3600.0, side="right"))        # hours starting at or before t - 1 h end by t
    if log.get("complete"):
        return float(cum[k - 1]) if k > 0 else 0.0
    cf, vn = log.get("complete_from_hour"), log.get("volumeNum")
    if cf is not None and vn is not None and cf <= t:
        after = float(cum[-1] - (cum[k - 1] if k > 0 else 0.0))
        return max(vn - after, 0.0)
    return None


def _price_before(ts: np.ndarray, ps: np.ndarray, cutoff: float, max_stale: float = 3 * DAY) -> tuple[Optional[float], Optional[float]]:
    i = int(np.searchsorted(ts, cutoff, side="right")) - 1
    if i < 0 or cutoff - ts[i] > max_stale:
        return None, None
    return float(ps[i]), float(ts[i])


def _dtb3(archive) -> Callable[[float], float]:
    """rate_at(ts): the continuously compounded 3-month bill rate known at ts (rule 7 conversion; the print whose
    available_at is at or before ts, the first print before that)."""
    def load():
        av, rt = [], []
        for r in archive.load(DTB3_B):
            d = _num((r.get("value") or {}).get("value")); a = _ts(r.get("available_at"))
            if d is None or a is None:
                continue
            av.append(a); rt.append(-math.log(1 - d / 100 * 91 / 360) / (91 / 365))
        o = np.argsort(av)
        return np.array(av)[o], np.array(rt)[o]
    av, rt = _cached(archive, "dtb3", load)

    def rate_at(ts: float) -> float:
        if av.size == 0:
            return 0.0
        i = int(np.searchsorted(av, ts, side="right")) - 1
        return float(rt[max(i, 0)])
    return rate_at


def _boxx_rate(archive) -> Optional[Callable[[float], Optional[float]]]:
    """Trailing one-year total return of the BOXX box-spread ETF known at ts (a market box-rate proxy), or None."""
    if not _has(archive, BOXX_B):
        return None

    def load():
        pts = {}
        for r in archive.load(BOXX_B):
            v = r.get("value") or {}
            c = _num(v.get("adjclose") if v.get("adjclose") is not None else v.get("close")); a = _ts(r.get("available_at")); t = _num(v.get("t"))
            if c is None or c <= 0 or t is None:
                continue
            pts[t] = (a if a is not None else t + DAY, c)
        ts = np.array(sorted(pts)); return ts, np.array([pts[t][0] for t in ts]), np.array([pts[t][1] for t in ts])
    ts, av, cl = _cached(archive, "boxx", load)

    def rate_at(t: float) -> Optional[float]:
        i = int(np.searchsorted(av, t, side="right")) - 1
        if i < 0:
            return None
        j = int(np.searchsorted(ts, ts[i] - 365 * DAY, side="left"))
        if j >= i or ts[i] - ts[j] < 300 * DAY:
            return None
        return float(math.log(cl[i] / cl[j]) / ((ts[i] - ts[j]) / (365 * DAY)))
    return rate_at


def _kalshi(archive, series: Sequence[str] = KALSHI_SERIES) -> dict:
    """{'markets': ticker -> {result, close_ts, settle_ts, event, open_ts}, 'candles': ticker -> (t_end, bid, ask, price)}
    for the archived series; a ticker needs a yes/no result and at least one candle."""
    def load():
        mk, cd = {}, defaultdict(list)
        for s in series:
            if _has(archive, f"kalshi-settled-markets-{s}"):
                for r in archive.load(f"kalshi-settled-markets-{s}"):
                    v = r.get("value") or {}
                    if str(v.get("result", "")).lower() not in ("yes", "no"):
                        continue
                    close = _ts(v.get("close_time")); settle = _ts(v.get("settlement_ts")) or _ts(v.get("expiration_time"))
                    if close is None:
                        continue
                    mk[str(v.get("ticker"))] = {"result": 1 if str(v["result"]).lower() == "yes" else 0, "close_ts": close,
                                                "settle_ts": max(settle, close) if settle else close, "event": str(v.get("event_ticker") or v.get("ticker")),
                                                "open_ts": _ts(v.get("open_time")), "series": s}
            if _has(archive, f"kalshi-candles-daily-{s}"):
                for r in archive.load(f"kalshi-candles-daily-{s}"):
                    v = r.get("value") or {}; c = v.get("candle") or {}
                    t = _num(c.get("end_period_ts"))
                    if t is None:
                        continue

                    def g(d, k):
                        d = d or {}
                        return _num(d.get(k)) if d.get(k) is not None else _num(d.get(k + "_dollars"))
                    cd[str(v.get("ticker"))].append((t, g(c.get("yes_bid"), "close"), g(c.get("yes_ask"), "close"), g(c.get("price"), "close")))
        candles = {}
        for tk, rows in cd.items():
            if tk not in mk:
                continue
            rows.sort()
            candles[tk] = (np.array([x[0] for x in rows]), np.array([np.nan if x[1] is None else x[1] for x in rows]),
                           np.array([np.nan if x[2] is None else x[2] for x in rows]), np.array([np.nan if x[3] is None else x[3] for x in rows]))
        return {"markets": {k: v for k, v in mk.items() if k in candles}, "candles": candles}
    return _cached(archive, ("kalshi", tuple(series)), load)


def _open_series(archive) -> dict[str, tuple[np.ndarray, np.ndarray, str]]:
    """market id -> (t, p, event id) for the open-market daily histories (one market per event by construction)."""
    def load():
        ev = {}
        if _has(archive, OPEN_MARKETS):
            for r in archive.load(OPEN_MARKETS):
                s = _slim(r.get("value") or {}); ev[s["id"]] = s["event_id"] or s["id"]
        by: dict[str, dict[float, float]] = defaultdict(dict)
        if _has(archive, OPEN_DAILY):
            for r in archive.load(OPEN_DAILY):
                v = r["value"]; p = _num(v.get("p")); t = _num(v.get("t"))
                if p is None or t is None:
                    continue
                by[str(v["market_id"])][t] = min(max(p, 0.0), 1.0)
        out = {}
        for mid, d in by.items():
            ts = np.array(sorted(d)); out[mid] = (ts, np.array([d[t] for t in ts]), str(ev.get(mid, mid)))
        return out
    return _cached(archive, "open", load)


# ============================================================================================== statistics ==

def _boot_weights(keys: Sequence, n_boot: int, seed: int):
    """Yields per-observation multiplicity weights of a cluster bootstrap (whole clusters drawn with replacement)."""
    _, inv = np.unique(np.asarray(list(keys), dtype=object).astype(str), return_inverse=True)
    G = int(inv.max()) + 1 if inv.size else 0
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        m = np.bincount(rng.integers(0, G, G), minlength=G)
        yield m[inv].astype(float)


def _n_clusters(keys: Sequence) -> int:
    return int(np.unique(np.asarray(list(keys), dtype=object).astype(str)).size)


def _wmean(e: np.ndarray, w: np.ndarray) -> float:
    s = w.sum()
    return float((w * e).sum() / s) if s > 0 else float("nan")


def cluster_mean(e: np.ndarray, keys: Sequence, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Mean, two-sided 95% cluster-bootstrap percentile interval, one-sided bootstrap p-values (share of bootstrap
    means <= 0 and >= 0) and the cluster count."""
    e = np.asarray(e, dtype=float)
    if e.size == 0:
        return {"n": 0, "mean": None, "ci": [None, None], "p_le0": None, "p_ge0": None, "n_clusters": 0}
    boots = np.array([_wmean(e, w) for w in _boot_weights(keys, n_boot, seed)])
    lo, hi = (float(x) for x in np.quantile(boots, [0.025, 0.975]))
    return {"n": int(e.size), "mean": float(e.mean()), "ci": [lo, hi], "p_le0": float(np.mean(boots <= 0)), "p_ge0": float(np.mean(boots >= 0)),
            "n_clusters": _n_clusters(keys)}


def cluster_mean_diff(a: np.ndarray, keys_a: Sequence, b: np.ndarray, keys_b: Sequence, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """mean(a) - mean(b) for two rules' per-unit returns on possibly different unit sets, with a cluster bootstrap over the
    union of their clusters (a cluster drawn k times weights its units k times in both means, so shared markets stay
    paired and the comparison is of the two rules as executed, not conditioned on a market qualifying under both)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size == 0 or b.size == 0:
        return {"n_a": int(a.size), "n_b": int(b.size), "mean_a": float(a.mean()) if a.size else None, "mean_b": float(b.mean()) if b.size else None,
                "diff": None, "ci": [None, None], "p_le0": None, "n_clusters": 0}
    keys = list(keys_a) + list(keys_b)
    boots = np.array([_wmean(a, w[:a.size]) - _wmean(b, w[a.size:]) for w in _boot_weights(keys, n_boot, seed)])
    boots = boots[np.isfinite(boots)]
    lo, hi = (float(x) for x in np.quantile(boots, [0.025, 0.975])) if boots.size else (float("nan"), float("nan"))
    return {"n_a": int(a.size), "n_b": int(b.size), "mean_a": float(a.mean()), "mean_b": float(b.mean()), "diff": float(a.mean() - b.mean()), "ci": [lo, hi],
            "p_le0": float(np.mean(boots <= 0)) if boots.size else None, "n_clusters": _n_clusters(keys)}


def _cluster_stat_ci(keys: Sequence, fn: Callable[[np.ndarray], float], n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    boots = np.array([fn(w) for w in _boot_weights(keys, n_boot, seed)])
    boots = boots[np.isfinite(boots)]
    if boots.size == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return float(lo), float(hi)


def _dsr(x: np.ndarray, n_trials: int) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    if x.size < 10 or x.std(ddof=1) == 0:
        return None
    try:
        return float(deflated_sharpe_ratio(x, n_trials=n_trials))
    except Exception:
        return None


def fee_rate(fee_type: Optional[str], default: float = FEE_DEFAULT) -> float:
    if fee_type:
        return FEE_RATES.get(str(fee_type).split("_")[0], default)
    return default


def pm_fee(q: float, fee_type: Optional[str], enabled: bool, schedule_all: bool = False) -> float:
    """Polymarket fee per share at price q: rate x q x (1 - q) when the market charges fees (or always, schedule_all)."""
    if not (enabled or schedule_all):
        return 0.0
    return fee_rate(fee_type) * q * (1 - q)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _logloss(p: np.ndarray, y: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(p, eps, 1 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _fmt(x, nd=3) -> str:
    return "None" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _below_min_n(n: int, min_n: int) -> str:
    return f"; below min_n {min_n} (n {n}): only decisive failures count, never supported" if n < min_n else ""


def _finish(crit: list, n: int, min_n: int, stat: dict, text: str):
    """Apply rule 5 and _verdict: below min_n, non-decisive failures become undecided and supported is impossible."""
    if n < min_n:
        judged = [(name, None if (ok is False and not decisive) else ok) for name, ok, decisive in crit]
        v, why = _verdict(judged)
        if v == "supported":
            v, why = "inconclusive", f"implemented criteria pass but n {n} < min_n {min_n}"
    else:
        judged = [(name, ok) for name, ok, _ in crit]
        v, why = _verdict(judged)
    stat["criteria"] = {name: (None if ok is None else bool(ok)) for name, ok in judged}
    stat["criteria_observed"] = {name: (None if ok is None else bool(ok)) for name, ok, _ in crit}
    stat["n"] = int(n); stat["min_n"] = int(min_n)
    return _clean(stat), int(n), v, text + _below_min_n(n, min_n) + " — " + why


# ====================================================================================== T-12 volume quartiles ==

def volume_quartile_skill(p: np.ndarray, o: np.ndarray, vol: np.ndarray, keys: Sequence, n_boot: int = N_BOOT, seed: int = SEED,
                          age: Optional[Sequence] = None) -> dict:
    """Brier skill vs the coin (1 - Brier / 0.25) per volume quartile (quartile labels fixed by the sample's volume ranks),
    monotonicity Q1 < Q2 < Q3 < Q4, and one cluster bootstrap giving the interval of skill(Q4) - skill(Q1), of every
    quartile's skill and of the three adjacent increments (Q2 - Q1, Q3 - Q2, Q4 - Q3), so that a strict ordering of four
    point estimates is not read as evidence when the increments include 0. ``age`` (days since listing at the decision,
    optional) is summarised per quartile: volume accrues with time since listing, the age confound of the ranking."""
    p = np.asarray(p, float); o = np.asarray(o, float); vol = np.asarray(vol, float); n = p.size
    order = np.argsort(vol, kind="stable"); q = np.empty(n, dtype=int); q[order] = (np.arange(n) * 4) // n
    sq = (p - o) ** 2

    def skills(w):
        out = []
        for k in range(4):
            m = q == k; s = (w[m]).sum()
            out.append(1 - float((w[m] * sq[m]).sum() / s) / 0.25 if s > 0 else float("nan"))
        return out
    ones = np.ones(n)
    sk = skills(ones)
    nan2 = [float("nan"), float("nan")]
    if n >= 8:
        boots = np.array([skills(w) for w in _boot_weights(keys, n_boot, seed)])        # n_boot x 4

        def ci(x):
            x = x[np.isfinite(x)]
            return [float(v) for v in np.quantile(x, [0.025, 0.975])] if x.size else list(nan2)
        gap_ci = ci(boots[:, 3] - boots[:, 0])
        skill_ci = [ci(boots[:, k]) for k in range(4)]
        inc_ci = [ci(boots[:, k + 1] - boots[:, k]) for k in range(3)]
    else:
        gap_ci = list(nan2); skill_ci = [list(nan2) for _ in range(4)]; inc_ci = [list(nan2) for _ in range(3)]
    lo, hi = gap_ci

    def reliability(m):
        try:
            return float(murphy_decomposition(p[m], o[m], n_bins=10).reliability) if m.sum() >= 10 else None
        except Exception:
            return None
    fin = all(math.isfinite(s) for s in sk)
    out = {"n": int(n), "skill": sk, "skill_ci": skill_ci, "n_per_quartile": [int((q == k).sum()) for k in range(4)],
           "increment": [float(sk[k + 1] - sk[k]) if fin else None for k in range(3)], "increment_ci": inc_ci,
           "volume_bounds": [float(vol[order][(n * k) // 4]) if n else None for k in range(4)] + [float(vol.max()) if n else None],
           "base_rate_per_quartile": [float(o[q == k].mean()) if (q == k).any() else None for k in range(4)],
           "share_zero_volume_per_quartile": [float((vol[q == k] == 0).mean()) if (q == k).any() else None for k in range(4)],
           "mean_abs_p_minus_half_per_quartile": [float(np.abs(p[q == k] - 0.5).mean()) if (q == k).any() else None for k in range(4)],
           "reliability_per_quartile": [reliability(q == k) for k in range(4)],
           "monotone": bool(all(sk[k] < sk[k + 1] for k in range(3))) if fin else False,
           "gap": float(sk[3] - sk[0]) if math.isfinite(sk[3]) and math.isfinite(sk[0]) else None, "gap_ci": [lo, hi],
           "n_clusters": _n_clusters(keys)}
    if age is not None:
        ag = np.array([np.nan if a is None else float(a) for a in age], float)
        out["median_age_days_per_quartile"] = [float(np.nanmedian(ag[q == k])) if np.isfinite(ag[q == k]).any() else None for k in range(4)]
        okv = np.isfinite(ag) & (vol > 0)
        out["corr_log_volume_log_age"] = float(np.corrcoef(np.log(vol[okv]), np.log1p(np.maximum(ag[okv], 0)))[0, 1]) if okv.sum() >= 8 else None
    return out


def _horizon_rows(archive, horizon_days: float, need_volume: bool) -> list[dict]:
    """One row per resolved market with a daily price at close - h (<= 3 d stale, cutoff not after endDate): p, outcome,
    cluster, cutoff, scheduled days to end, Gamma volume and (when need_volume) point-in-time taker shares at the cutoff."""
    series, meta, outs = _daily_series(archive), _closed_meta(archive), _outcomes(archive)
    vol, log = (_volume(archive), _fetch_log(archive)["trades"]) if need_volume else ({}, {})
    rows = []
    for mid, o in outs.items():
        if mid not in series:
            continue
        cutoff = o["close_ts"] - horizon_days * DAY
        if o.get("end_ts") is not None and cutoff > o["end_ts"]:
            continue
        ts, ps = series[mid]
        p, tp = _price_before(ts, ps, cutoff)
        if p is None:
            continue
        s = meta[mid]
        row = {"mid": mid, "p": p, "o": int(o["outcome"]), "cluster": cluster_key(s), "cutoff": cutoff, "price_ts": tp,
               "days_to_end": ((o["end_ts"] if o.get("end_ts") is not None else o["close_ts"]) - cutoff) / DAY,
               "gamma_volume": float(s.get("volumeNum") or 0.0), "close_ts": o["close_ts"],
               "age_days": None if o.get("start_ts") is None else (cutoff - o["start_ts"]) / DAY}
        if need_volume:
            v = vol.get(mid)
            row["pit_volume"] = pit_volume(v[0], v[1], cutoff, log.get(mid)) if v is not None else None
        rows.append(row)
    return rows


SAMPLE_REASON = "sample"
MIN_AGE_DAYS = 7.0


def _qs(res: dict) -> str:
    """'Q1..Q4 = s [lo, hi], ...' for a volume_quartile_skill result."""
    return ", ".join(f"{_fmt(s)} [{_fmt(c[0])}, {_fmt(c[1])}]" for s, c in zip(res["skill"], res["skill_ci"]))


def _vqs(rows: list[dict], key: str, n_boot: int, seed: int) -> Optional[dict]:
    return volume_quartile_skill([r["p"] for r in rows], [r["o"] for r in rows], [r[key] for r in rows], [r["cluster"] for r in rows], n_boot, seed,
                                 age=[r.get("age_days") for r in rows]) if len(rows) >= 8 else None


def b6c_pmcal_volume_calibration(archive, horizon: int = 7, min_n: int = 400, n_boot: int = N_BOOT, seed: int = SEED):
    """T-12: Brier skill per volume quartile at the 7-day horizon: monotone increase across quartiles and the top-bottom gap's
    event-clustered 95% interval excludes 0 (above it). Quartiles by point-in-time taker volume at close - 7 d from the
    trades-derived hourly bundle; markets whose trade history is not complete through the decision are left out.

    Population: the fetcher's unbiased hash sample (polymarket-fetch-log daily reason 'sample'; the fetcher's docstring:
    "a harness wanting an unbiased population uses reason sample"). The scheduled-event family markets (FOMC, CPI, ...) are
    selected by topic, carry high volume by construction and are highly predictable a week before a scheduled print, and
    the legacy 399 are the volume-selected top: they are 2-3x over-represented among the markets with point-in-time volume
    and are reported in the family-inclusive mixture as a sensitivity, never scored. The 'long-lived' markets (>= 100 d)
    have no point-in-time volume at all and are absent from the test (stated). Q1 holds the markets with no trade before
    the decision: their 'price' is a resting-book quote, so Q1's statistic is quote skill, and the ranking follows time
    since listing (volume accrues with age): the age >= 7 d sensitivity and the per-quartile / adjacent-increment
    intervals are reported beside the primary. The Gamma end-of-life volume quartiles are a reported sensitivity (the
    stated leak), never a criterion. n = markets of the primary population."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY, FETCH_LOG])
    if miss:
        return miss
    have_volume = bool(_bundle_names(archive, MONTH_VOLUME_RE))
    rows = _horizon_rows(archive, horizon, need_volume=have_volume)
    reasons = _fetch_log(archive)["daily"]
    pit = [r for r in rows if r.get("pit_volume") is not None]
    why_all = [str(reasons.get(r["mid"], "legacy")) for r in rows]
    why_in = [str(reasons.get(r["mid"], "legacy")) for r in pit]
    primary = [r for r, w in zip(pit, why_in) if w == SAMPLE_REASON]
    absent = sorted(set(why_all) - set(why_in))
    stat = {"horizon_days": horizon, "n_scored_at_horizon": len(rows), "n_with_pit_volume": len(pit), "n_primary": len(primary),
            "volume_bundles": len(_bundle_names(archive, MONTH_VOLUME_RE)),
            "population": f"polymarket-fetch-log daily reason '{SAMPLE_REASON}' (the fetcher's hash sample); family and legacy markets only in the mixture sensitivity",
            "selection_reasons_scored": {k: why_all.count(k) for k in sorted(set(why_all))},
            "selection_reasons_pit": {k: why_in.count(k) for k in sorted(set(why_in))},
            "selection_reasons_absent_from_test": absent}
    n = len(primary)
    if rows:
        allg = _vqs(rows, "gamma_volume", n_boot, seed)
        stat["gamma_volume_all_markets_LEAKY"] = allg
    names = ["skill rises monotonically across point-in-time volume quartiles (Q1 < Q2 < Q3 < Q4) on the hash-sample population",
             "top-bottom skill gap 95% event-clustered interval excludes 0 (lower bound > 0) on the hash-sample population"]
    if len(pit) < 8:
        crit = [(names[0], None, False), (names[1], None, False)]
        stat["missing"] = VOLUME_FAMILY
        text = (f"{len(rows)} markets scored at {horizon}d but {len(pit)} with point-in-time volume: {VOLUME_FAMILY} covers none of them, so the quartile "
                f"criteria cannot be computed point in time (the Gamma end-of-life quartiles are reported as the stated leak only)")
        return _finish(crit, n, min_n, stat, text)
    mix = _vqs(pit, "pit_volume", n_boot, seed)
    stat["family_inclusive_mixture_sensitivity"] = mix
    if n < 8:
        crit = [(names[0], None, False), (names[1], None, False)]
        stat["missing"] = f"{FETCH_LOG} daily reason '{SAMPLE_REASON}' markets with point-in-time volume"
        text = (f"{len(pit)} markets with point-in-time volume at {horizon}d but {n} of them in the fetcher's hash sample (reasons {stat['selection_reasons_pit']}): "
                f"the unbiased population cannot be formed; family-inclusive mixture Q1..Q4 = {_qs(mix)}, monotone {mix['monotone']}, gap {_fmt(mix['gap'])} "
                f"[{_fmt(mix['gap_ci'][0])}, {_fmt(mix['gap_ci'][1])}] (reported only)")
        return _finish(crit, n, min_n, stat, text)
    res = _vqs(primary, "pit_volume", n_boot, seed)
    leak = _vqs(primary, "gamma_volume", n_boot, seed)
    stat["pit_volume_quartiles"] = res; stat["gamma_volume_same_markets_LEAKY"] = leak
    traded = [r for r in primary if r["pit_volume"] > 0]
    nz = _vqs(traded, "pit_volume", n_boot, seed)
    stat["excluding_zero_volume_sensitivity"] = nz
    aged = [r for r in primary if r.get("age_days") is not None and r["age_days"] >= MIN_AGE_DAYS]
    ag = _vqs(aged, "pit_volume", n_boot, seed)
    stat["age_at_least_7d_sensitivity"] = ag
    stat["age_rule"] = f"markets listed at least {MIN_AGE_DAYS:.0f} d before the decision (close - {horizon} d)"
    lo, hi = res["gap_ci"]
    mono = res["monotone"]; gap_ok = bool(math.isfinite(lo) and lo > 0)
    # decisive failures below min_n: a gap interval wholly below 0; a monotonicity violation is undecided on thin data
    crit = [(names[0], mono, False), (names[1], gap_ok, bool(math.isfinite(hi) and hi < 0))]
    inc = ", ".join(f"{_fmt(d)} [{_fmt(c[0])}, {_fmt(c[1])}]" for d, c in zip(res["increment"], res["increment_ci"]))
    ages = res.get("median_age_days_per_quartile") or [None] * 4
    gone = ", ".join(f"{k} ({why_all.count(k)} scored)" for k in absent) if absent else "none"
    text = (f"{horizon}d horizon, primary population = the fetcher's hash sample (reason '{SAMPLE_REASON}'): {n} markets with point-in-time taker volume in "
            f"{res['n_clusters']} events ({len(pit)} with PIT volume in all, {len(rows)} scored; selection reasons with no PIT volume at all, absent from the test: {gone}): "
            f"Brier skill vs coin by PIT-volume quartile Q1..Q4 = {_qs(res)} (n {res['n_per_quartile']}), monotone {mono} (adjacent increments Q2-Q1, Q3-Q2, Q4-Q3 = {inc}); "
            f"Q4 - Q1 gap {_fmt(res['gap'])} [{_fmt(lo)}, {_fmt(hi)}]; Q1 is quote skill: {_fmt(res['share_zero_volume_per_quartile'][0], 2)} of its markets had no trade "
            f"before the decision (resting-book quotes, mean |p - 0.5| {_fmt(res['mean_abs_p_minus_half_per_quartile'][0], 2)} vs {_fmt(res['mean_abs_p_minus_half_per_quartile'][3], 2)} in Q4); "
            f"age confound: median days since listing at the decision Q1..Q4 = {', '.join(_fmt(a, 1) for a in ages)} (corr log volume, log age {_fmt(res.get('corr_log_volume_log_age'), 2)}); "
            f"reliability {', '.join(_fmt(x) for x in res['reliability_per_quartile'])}"
            + ("; the skill rise is resolution, not the reliability term, which does not fall with volume"
               if all(x is not None for x in res["reliability_per_quartile"]) and not all(res["reliability_per_quartile"][k] > res["reliability_per_quartile"][k + 1] for k in range(3)) else "")
            + (f"; markets >= {MIN_AGE_DAYS:.0f} d old at the decision ({ag['n']}): {', '.join(_fmt(s) for s in ag['skill'])}, monotone {ag['monotone']}, gap {_fmt(ag['gap'])} "
               f"[{_fmt(ag['gap_ci'][0])}, {_fmt(ag['gap_ci'][1])}]" if ag else "; age sensitivity not computable")
            + (f"; excluding zero-volume markets ({nz['n']}): {', '.join(_fmt(s) for s in nz['skill'])}, monotone {nz['monotone']}, gap {_fmt(nz['gap'])} "
               f"[{_fmt(nz['gap_ci'][0])}, {_fmt(nz['gap_ci'][1])}]" if nz else "")
            + f"; family-inclusive mixture ({mix['n']} markets, reasons {stat['selection_reasons_pit']}; family markets are topic-selected and high-volume by construction): "
            f"{', '.join(_fmt(s) for s in mix['skill'])}, monotone {mix['monotone']}, gap {_fmt(mix['gap'])} [{_fmt(mix['gap_ci'][0])}, {_fmt(mix['gap_ci'][1])}] (sensitivity, not scored)"
            + f"; LEAKY Gamma end-of-life quartiles on the primary markets {', '.join(_fmt(s) for s in leak['skill'])} "
            f"(gap {_fmt(leak['gap'])} [{_fmt(leak['gap_ci'][0])}, {_fmt(leak['gap_ci'][1])}]), on all {len(rows)} scored markets "
            f"{', '.join(_fmt(s) for s in stat['gamma_volume_all_markets_LEAKY']['skill'])}")
    return _finish(crit, n, min_n, stat, text)


# ===================================================================================== T-378 near-certain carry ==

def carry_observations_pm(outcomes: dict, series: dict, meta: dict, rate_at: Callable[[float], float], lo: float = 0.95, hi: float = 0.99,
                          schedule_all: bool = False, boxx_at: Optional[Callable] = None, days_basis: str = "scheduled") -> list[dict]:
    """Polymarket favorite-carry observations: per resolved market, the first daily point whose favorite side (max(p, 1-p))
    lies in [lo, hi] inside each horizon bucket of days to resolution (1-7, 8-30, 31-60), held to payout.

    ``days_basis`` (rule 4): 'scheduled' (primary) measures the 1-60 d eligibility window and the bucket from the market's
    scheduled endDate, the only resolution date known at t (markets without one are skipped); the payoff and the hold
    still run to the realized resolution (closedTime), so an early resolution shortens the hold and raises the annualized
    return without changing which observations a trader could have taken. 'realized' (sensitivity) measures them from
    close = min(closedTime, endDate), which for a market that resolved before its scheduled end is a date unknown at t
    and admits entries that were more than 60 d from the scheduled end with hindsight."""
    if days_basis not in ("scheduled", "realized"):
        raise ValueError(days_basis)
    obs = []
    for mid, o in outcomes.items():
        sv = series.get(mid)
        if sv is None:
            continue
        ts, ps = sv; close = o["close_ts"]; end = o.get("end_ts")
        if days_basis == "scheduled" and end is None:
            continue
        payout = max(o["closed_ts"] or close, close)
        s = meta.get(mid, {}); done = set()
        for t, p in zip(ts, ps):
            if t >= close or (end is not None and t > end):
                break
            days = ((end if days_basis == "scheduled" else close) - t) / DAY
            if days < 1 or days > 60:
                continue
            q = max(p, 1 - p); side = 1 if p >= 0.5 else 0
            if not (lo <= q <= hi):
                continue
            b = 0 if days <= 7 else (1 if days <= 30 else 2)
            if b in done:
                continue
            done.add(b)
            win = 1 if side == o["outcome"] else 0
            fee = pm_fee(q, s.get("feeType"), bool(s.get("feesEnabled")), schedule_all)
            hold = max((payout - t) / DAY, 1.0) if days_basis == "scheduled" else max((payout - t) / DAY, days, 1.0)
            rf = rate_at(t)
            r_ann = (win - fee - q) / q * 365.0 / hold
            net_ann = r_ann - rf                                   # forgone DTB3 on Polymarket collateral
            hurdle = rf + BOX_SPREAD + HURDLE_PREMIUM
            ob = {"venue": "polymarket", "mid": mid, "cluster": cluster_key(s) if s else f"market:{mid}", "res_day": _day_of(close), "t": float(t),
                  "q": float(q), "side": side, "win": win, "fee": fee, "days": float(days), "days_to_realized_close": float((close - t) / DAY),
                  "hold": float(hold), "bucket": b, "rf": rf, "r_ann": r_ann, "excess": net_ann - hurdle, "excess_single_rf": r_ann - hurdle,
                  "profit": win - fee - q, "year": int(_day_of(t)[:4]), "days_basis": days_basis}
            if boxx_at is not None:
                bx = boxx_at(t)
                ob["excess_boxx"] = None if bx is None else net_ann - (bx + HURDLE_PREMIUM)
            obs.append(ob)
    return obs


def carry_observations_kalshi(kalshi: dict, rate_at: Callable[[float], float], lo: float = 0.95, hi: float = 0.99, max_spread: float = 0.05) -> list[dict]:
    """Kalshi favorite-carry observations from daily candles: buy YES at the ask or NO at 1 - bid when that price is in
    [lo, hi] with 1-60 days to close, first entry per horizon bucket; taker fee 0.07 q (1 - q); payout at settlement.
    The 1-60 d window and the bucket use the market's close_time, the scheduled close known at t (the same reading as the
    Polymarket arm's scheduled endDate); the hold runs to the settlement timestamp."""
    obs = []
    for tk, m in kalshi["markets"].items():
        c = kalshi["candles"].get(tk)
        if c is None:
            continue
        close, settle = m["close_ts"], m["settle_ts"]; done = set()
        for t, bid, ask, _ in zip(*c):
            if t >= close:
                break
            if not (np.isfinite(bid) and np.isfinite(ask)) or bid <= 0 or ask - bid > max_spread:
                continue
            days = (close - t) / DAY
            if days < 1 or days > 60:
                continue
            if lo <= ask <= hi:
                q, side = float(ask), 1
            elif lo <= 1 - bid <= hi:
                q, side = float(1 - bid), 0
            else:
                continue
            b = 0 if days <= 7 else (1 if days <= 30 else 2)
            if b in done:
                continue
            done.add(b)
            win = 1 if side == m["result"] else 0
            fee = KALSHI_FEE * q * (1 - q)
            hold = max((settle - t) / DAY, days, 1.0)
            rf = rate_at(t)
            r_ann = (win - fee - q) / q * 365.0 / hold
            hurdle = rf + BOX_SPREAD + HURDLE_PREMIUM
            obs.append({"venue": "kalshi", "mid": tk, "cluster": f"kevent:{m['event']}", "res_day": _day_of(close), "t": float(t), "q": q, "side": side,
                        "win": win, "fee": fee, "days": float(days), "days_to_realized_close": float(days), "hold": float(hold), "bucket": b, "rf": rf,
                        "r_ann": r_ann, "excess": r_ann - hurdle, "excess_single_rf": r_ann - hurdle, "excess_apy": r_ann + 0.035 - hurdle,
                        "profit": win - fee - q, "year": int(_day_of(t)[:4]), "series": m["series"], "days_basis": "scheduled"})
    return obs


SHORT_HOLD_DAYS = 2.0


def short_hold_contribution(obs: list[dict], max_hold: float = SHORT_HOLD_DAYS) -> Optional[dict]:
    """Weight of the observations held at most ``max_hold`` days in the equal-weighted mean of annualized excess returns:
    a short hold annualizes a few cents of carry into a large rate, so a small share of observations can carry most of
    the pooled mean. contribution = sum of their excess / n (their part of the pooled mean)."""
    if not obs:
        return None
    ex = np.array([d["excess"] for d in obs]); hold = np.array([d["hold"] for d in obs]); m = hold <= max_hold
    return {"max_hold_days": float(max_hold), "n_obs": int(m.sum()), "share_of_obs": float(m.mean()), "mean_excess": float(ex[m].mean()) if m.any() else None,
            "contribution_to_pooled_mean": float(ex[m].sum() / ex.size), "pooled_mean": float(ex.mean()),
            "mean_excess_longer_holds": float(ex[~m].mean()) if (~m).any() else None}


def carry_stats(obs: list[dict], n_trials: int = 12, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Pooled mean annualized excess over the hurdle with event- and resolution-day-clustered intervals, the largest event
    cluster's share of gross profit, the DSR of the excess returns in entry order, per-venue / bucket / year summaries and
    the short-hold (<= 2 d) observations' weight in the equal-weighted mean."""
    if not obs:
        return {"n_obs": 0, "n_markets": 0}
    obs = sorted(obs, key=lambda d: d["t"])
    ex = np.array([d["excess"] for d in obs]); ev = [d["cluster"] for d in obs]; rd = [d["res_day"] for d in obs]
    by_event = cluster_mean(ex, ev, n_boot, seed); by_day = cluster_mean(ex, rd, n_boot, seed + 1)
    prof = defaultdict(float); gross = 0.0
    for d in obs:
        if d["profit"] > 0:
            prof[d["cluster"]] += d["profit"]; gross += d["profit"]
    top = max(prof.items(), key=lambda kv: kv[1]) if prof else (None, 0.0)
    out = {"n_obs": len(obs), "n_markets": len({d["mid"] for d in obs}), "mean_excess": float(ex.mean()), "by_event": by_event, "by_resolution_day": by_day,
           "largest_cluster": top[0], "largest_cluster_profit_share": float(top[1] / gross) if gross > 0 else None, "gross_profit_per_contract": gross,
           "dsr": _dsr(ex, n_trials), "n_trials": n_trials, "sharpe_per_obs": float(sharpe_ratio(ex)) if ex.size > 2 and ex.std() > 0 else None,
           "win_rate": float(np.mean([d["win"] for d in obs])), "mean_price": float(np.mean([d["q"] for d in obs])),
           "mean_hold_days": float(np.mean([d["hold"] for d in obs])), "mean_days_to_resolution": float(np.mean([d["days"] for d in obs])),
           "dollar_weighted_annual_excess": None, "mean_excess_single_rf": float(np.mean([d["excess_single_rf"] for d in obs]))}
    cap = sum(d["q"] * d["hold"] / 365.0 for d in obs)
    if cap > 0:
        out["dollar_weighted_annual_excess"] = float(sum(d["profit"] for d in obs) / cap - np.average([d["rf"] + BOX_SPREAD + HURDLE_PREMIUM + (d["rf"] if d["venue"] == "polymarket" else 0.0) for d in obs],
                                                                                                 weights=[d["q"] * d["hold"] for d in obs]))
    for key in ("venue", "bucket", "year"):
        grp = defaultdict(list)
        for d in obs:
            grp[str(d[key])].append(d)
        out[f"by_{key}"] = {k: {"n_obs": len(v), "n_markets": len({d['mid'] for d in v}), "mean_excess": float(np.mean([d['excess'] for d in v])),
                                "win_rate": float(np.mean([d['win'] for d in v])), "mean_price": float(np.mean([d['q'] for d in v]))} for k, v in sorted(grp.items())}
    bx = [d["excess_boxx"] for d in obs if d.get("excess_boxx") is not None]
    out["boxx_hurdle_sensitivity"] = {"n_obs": len(bx), "mean_excess": float(np.mean(bx))} if bx else None
    ka = [d["excess_apy"] for d in obs if d.get("excess_apy") is not None]
    out["kalshi_apy_credited_sensitivity"] = {"n_obs": len(ka), "mean_excess": float(np.mean(ka))} if ka else None
    out["short_hold"] = short_hold_contribution(obs)
    return out


def b6c_pmcal_near_certain_carry(archive, min_n: int = 500, n_boot: int = N_BOOT, seed: int = SEED):
    """T-378: pooled Polymarket + Kalshi favorite carry at the first price in [0.95, 0.99] with 1-60 days to resolution. Pass:
    lower 95% bound of the mean annualized net excess over the hurdle (DTB3 + 35 bp box proxy + 2%; Polymarket also net of
    forgone DTB3, as worded) > 0 under both named clusterings (event; resolution day: rule 11), no event cluster above half of
    gross profit, DSR > 0.95 with n_trials = 12. n = markets. Venues, buckets and years are reported separately.
    Rule 4: 'days before resolution' is measured from the resolution date known at the decision, the scheduled endDate on
    Polymarket (markets without one are skipped) and close_time on Kalshi; the payoff and the hold run to the realized
    resolution. The realized-close construction (eligibility and buckets from min(closedTime, endDate), which for early
    resolutions is a date unknown at t) is reported as a sensitivity, as is the weight of the hold <= 2 d observations
    in the equal-weighted annualized mean."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY, DTB3_B])
    if miss:
        return miss
    rate_at = _dtb3(archive); boxx_at = _boxx_rate(archive)
    outs, series, meta = _outcomes(archive), _daily_series(archive), _closed_meta(archive)
    pm = carry_observations_pm(outs, series, meta, rate_at, boxx_at=boxx_at)
    kal = _kalshi(archive)
    ka = carry_observations_kalshi(kal, rate_at) if kal["markets"] else []
    obs = pm + ka
    st = carry_stats(obs, 12, n_boot, seed)
    stat = {"pooled": st, "polymarket": carry_stats(pm, 12, n_boot, seed) if pm else None, "kalshi": carry_stats(ka, 12, n_boot, seed) if ka else None,
            "kalshi_series_archived": sorted({m["series"] for m in kal["markets"].values()}), "hurdle": "DTB3 (rule-7 continuous) + 35 bp box proxy + 2%",
            "fees": "Polymarket: the market's own fee schedule when feesEnabled; Kalshi: 0.07 q (1 - q) taker",
            "days_basis": "scheduled: 1-60 d window and bucket from the scheduled endDate (Polymarket) / close_time (Kalshi); payoff and hold at the realized resolution",
            "polymarket_fee_schedule_on_all_sensitivity": None, "realized_close_sensitivity": None}
    if pm:
        pm_all = carry_observations_pm(outs, series, meta, rate_at, schedule_all=True)
        stat["polymarket_fee_schedule_on_all_sensitivity"] = {"mean_excess": float(np.mean([d["excess"] for d in pm_all]))}
        pm_real = carry_observations_pm(outs, series, meta, rate_at, days_basis="realized")
        sr = carry_stats(pm_real + ka, 12, n_boot, seed)
        stat["realized_close_sensitivity"] = {"rule": "eligibility and bucket from close = min(closedTime, endDate), hold floored at those days (the realized resolution date, unknown at t for early resolutions)",
                                              **{k: sr.get(k) for k in ("n_obs", "n_markets", "mean_excess", "by_event", "by_resolution_day", "dsr", "win_rate", "mean_hold_days", "largest_cluster_profit_share")},
                                              "n_obs_polymarket": len(pm_real), "n_markets_polymarket": len({d["mid"] for d in pm_real}),
                                              "n_polymarket_markets_without_endDate": int(sum(1 for mid, o in outs.items() if mid in series and o.get("end_ts") is None))}
    n = st.get("n_markets", 0)
    if n == 0:
        crit = [("lower 95% bound of mean annualized net excess over hurdle > 0 (event and resolution-day clusters)", None, False),
                ("largest event cluster share of gross profit <= 0.5", None, False), ("DSR > 0.95 (n_trials 12)", None, False)]
        return _finish(crit, 0, min_n, stat, "no favorite in [0.95, 0.99] with 1-60 days to resolution in the archived histories")
    lb_e, ub_e = st["by_event"]["ci"]; lb_d, ub_d = st["by_resolution_day"]["ci"]
    c1 = True if (lb_e > 0 and lb_d > 0) else (False if (lb_e <= 0 and lb_d <= 0) else None)
    share = st["largest_cluster_profit_share"]; dsr = st["dsr"]
    crit = [("lower 95% bound of mean annualized net excess over hurdle > 0 under both event and resolution-day clustering", c1,
             bool(ub_e < 0 and ub_d < 0)),
            ("no single event cluster contributes more than half of gross profit", None if share is None else share <= 0.5, False),
            ("DSR > 0.95 with n_trials = 12", None if dsr is None else dsr > 0.95, False)]
    sh = st.get("short_hold"); sr = stat.get("realized_close_sensitivity")
    text = (f"{st['n_obs']} observations on {n} markets (Polymarket {len({d['mid'] for d in pm})}, Kalshi {len({d['mid'] for d in ka})}; 1-60 d window and buckets "
            f"from the scheduled endDate / close_time, payoff and hold at the realized resolution): mean annualized net "
            f"excess over hurdle {_fmt(st['mean_excess'], 2)} per year (win rate {_fmt(st['win_rate'])}, mean price {_fmt(st['mean_price'])}, mean hold "
            f"{_fmt(st['mean_hold_days'], 1)} d), event-clustered 95% [{_fmt(lb_e, 2)}, {_fmt(ub_e, 2)}] ({st['by_event']['n_clusters']} events), "
            f"resolution-day-clustered [{_fmt(lb_d, 2)}, {_fmt(ub_d, 2)}] ({st['by_resolution_day']['n_clusters']} days)"
            + ("; clusterings disagree: undecided" if c1 is None else "")
            + f"; largest event cluster {st['largest_cluster']} holds {_fmt(share)} of gross profit; DSR {_fmt(dsr)} (n_trials 12); "
            f"dollar-weighted annual excess {_fmt(st['dollar_weighted_annual_excess'], 3)}; single-rf reading {_fmt(st['mean_excess_single_rf'], 2)}; "
            + "; ".join(f"{k}: n {v['n_markets']} mean {_fmt(v['mean_excess'], 2)} win {_fmt(v['win_rate'])}" for k, v in st["by_venue"].items())
            + (f"; hold <= {sh['max_hold_days']:.0f} d: {sh['n_obs']} obs ({_fmt(sh['share_of_obs'], 3)} of the sample, mean excess {_fmt(sh['mean_excess'], 2)}) contribute "
               f"{_fmt(sh['contribution_to_pooled_mean'], 3)} of the {_fmt(sh['pooled_mean'], 3)} pooled mean (longer holds {_fmt(sh['mean_excess_longer_holds'], 3)})" if sh else "")
            + (f"; realized-close construction (sensitivity; eligibility from min(closedTime, endDate), unknown at t for early resolutions): {sr['n_obs']} obs on "
               f"{sr['n_markets']} markets, mean {_fmt(sr['mean_excess'], 2)}, event [{_fmt(sr['by_event']['ci'][0], 2)}, {_fmt(sr['by_event']['ci'][1], 2)}], "
               f"day [{_fmt(sr['by_resolution_day']['ci'][0], 2)}, {_fmt(sr['by_resolution_day']['ci'][1], 2)}], DSR {_fmt(sr['dsr'])}" if sr else ""))
    return _finish(crit, n, min_n, stat, text)


# ========================================================================================= T-31 MLP vs logit ==

def _fit_logit(X: np.ndarray, y: np.ndarray, ridge: float = 1e-3, iters: int = 30):
    Xb = np.hstack([np.ones((X.shape[0], 1)), X]); w = np.zeros(Xb.shape[1]); I = np.eye(Xb.shape[1]); I[0, 0] = 0
    for _ in range(iters):
        p = _sigmoid(Xb @ w); W = p * (1 - p) + 1e-9
        H = Xb.T @ (Xb * W[:, None]) + ridge * I; g = Xb.T @ (p - y) + ridge * (I @ w)
        step = np.linalg.solve(H, g); w -= step
        if np.abs(step).max() < 1e-8:
            break
    return lambda Z: _sigmoid(np.hstack([np.ones((Z.shape[0], 1)), Z]) @ w)


def _fit_mlp(X: np.ndarray, y: np.ndarray, hidden: int = 8, epochs: int = 400, lr: float = 0.01, l2: float = 1e-4, seed: int = 0):
    rng = np.random.default_rng(seed); n, d = X.shape
    W1 = rng.normal(0, 1 / math.sqrt(d), (d, hidden)); b1 = np.zeros(hidden); W2 = rng.normal(0, 1 / math.sqrt(hidden), hidden); b2 = np.zeros(1)
    params = [W1, b1, W2, b2]; m = [np.zeros_like(q) for q in params]; v = [np.zeros_like(q) for q in params]
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    for ep in range(1, epochs + 1):
        H = np.tanh(X @ W1 + b1); p = _sigmoid(H @ W2 + b2[0])
        g = (p - y) / n
        gW2 = H.T @ g + l2 * W2; gb2 = np.array([g.sum()])
        gz1 = np.outer(g, W2) * (1 - H ** 2)
        gW1 = X.T @ gz1 + l2 * W1; gb1 = gz1.sum(0)
        for i, grad in enumerate((gW1, gb1, gW2, gb2)):
            m[i] = beta1 * m[i] + (1 - beta1) * grad; v[i] = beta2 * v[i] + (1 - beta2) * grad ** 2
            params[i] -= lr * (m[i] / (1 - beta1 ** ep)) / (np.sqrt(v[i] / (1 - beta2 ** ep)) + eps)
    return lambda Z: _sigmoid(np.tanh(Z @ W1 + b1) @ W2 + b2[0])


def logit_vs_mlp(X: np.ndarray, y: np.ndarray, market: Sequence, close_ts: np.ndarray, keys: Sequence, n_folds: int = 5, embargo_days: float = 37.0,
                 hidden: int = 8, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Walk-forward comparison: markets sorted by close date are cut into n_folds + 1 contiguous blocks; each test block is
    predicted by models trained on markets that closed at least ``embargo_days`` before the block's first close (so every
    training outcome was known before every test decision, decisions being at most 30 d + 3 d stale before close).
    Returns the per-observation log losses of the MLP, the logit and the market price, the paired difference MLP - logit
    with its cluster-bootstrap interval, and per-fold means."""
    X = np.asarray(X, float); y = np.asarray(y, float); close_ts = np.asarray(close_ts, float); market = np.asarray(list(market), dtype=object).astype(str)
    keys = np.asarray(list(keys), dtype=object).astype(str)
    mk_close = {}
    for mkid, c in zip(market, close_ts):
        mk_close[mkid] = min(c, mk_close.get(mkid, c))
    mks = sorted(mk_close, key=lambda k: (mk_close[k], k))
    if len(mks) < (n_folds + 1) * 20:
        return {"n_markets_tested": 0, "note": f"too few markets ({len(mks)}) for {n_folds} walk-forward folds"}
    blocks = np.array_split(np.arange(len(mks)), n_folds + 1)
    ll_m = np.full(y.size, np.nan); ll_l = np.full(y.size, np.nan); fold_of = np.full(y.size, -1)
    folds = []
    for k in range(1, n_folds + 1):
        test_mks = {mks[i] for i in blocks[k]}
        start = min(mk_close[m_] for m_ in test_mks)
        tr = np.array([mk_close[m_] <= start - embargo_days * DAY for m_ in market]); te = np.array([m_ in test_mks for m_ in market])
        if tr.sum() < 50 or te.sum() == 0 or len(set(y[tr])) < 2:
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Ztr, Zte = (X[tr] - mu) / sd, (X[te] - mu) / sd
        f_l = _fit_logit(Ztr, y[tr]); f_m = _fit_mlp(Ztr, y[tr], hidden=hidden, seed=seed + k)
        ll_l[te] = _logloss(f_l(Zte), y[te]); ll_m[te] = _logloss(f_m(Zte), y[te]); fold_of[te] = k
        folds.append({"fold": k, "n_train": int(tr.sum()), "n_test": int(te.sum()), "n_test_markets": len(test_mks),
                      "logloss_logit": float(ll_l[te].mean()), "logloss_mlp": float(ll_m[te].mean()), "diff": float((ll_m[te] - ll_l[te]).mean())})
    ok = np.isfinite(ll_m) & np.isfinite(ll_l)
    if ok.sum() == 0:
        return {"n_markets_tested": 0, "note": "no fold could be trained", "folds": folds}
    d = ll_m[ok] - ll_l[ok]
    cm = cluster_mean(d, keys[ok], n_boot, seed)
    return {"n_obs_tested": int(ok.sum()), "n_markets_tested": len(set(market[ok])), "diff_mean": cm["mean"], "diff_ci": cm["ci"], "p_ge0": cm["p_ge0"],
            "n_clusters": cm["n_clusters"], "logloss_mlp": float(ll_m[ok].mean()), "logloss_logit": float(ll_l[ok].mean()),
            "logloss_market_price": float(_logloss(_sigmoid(X[ok, 0]), y[ok]).mean()), "folds": folds, "hidden": hidden, "embargo_days": embargo_days,
            "folds_mlp_better": int(sum(1 for f in folds if f["diff"] < 0)), "n_folds_run": len(folds)}


def b6c_pmcal_mlp_vs_logit(archive, horizons=(1, 3, 7, 30), min_n: int = 500, n_boot: int = N_BOOT, seed: int = SEED):
    """T-31: walk-forward log-loss difference (MLP - logit) < 0 with the event-clustered 95% interval excluding 0. Features at
    each decision (close - h d, h in 1, 3, 7, 30): logit of the daily snapshot price, log(1 + point-in-time taker volume),
    log(1 + days to the scheduled end). Markets without a complete point-in-time volume are left out (the registry's leak
    control). n = markets in the test folds."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY, FETCH_LOG])
    if miss:
        return miss
    have_volume = bool(_bundle_names(archive, MONTH_VOLUME_RE))
    rows = []
    for h in horizons:
        rows += [dict(r, h=h) for r in _horizon_rows(archive, h, need_volume=have_volume) if r.get("pit_volume") is not None]
    stat = {"horizons": list(horizons), "n_obs": len(rows), "n_markets": len({r["mid"] for r in rows}), "features": ["logit(p)", "log1p(pit taker shares)", "log1p(days to scheduled end)"]}
    if len(rows) < 120:
        crit = [("walk-forward log loss MLP - logit < 0 with interval excluding 0", None, False)]
        stat["missing"] = VOLUME_FAMILY if not have_volume or not rows else "enough markets with point-in-time volume"
        return _finish(crit, stat["n_markets"], min_n, stat, f"{len(rows)} observations with point-in-time volume: too few to train walk-forward folds ({VOLUME_FAMILY})")
    pc = np.clip(np.array([r["p"] for r in rows]), 1e-3, 1 - 1e-3)
    X = np.column_stack([np.log(pc / (1 - pc)), np.log1p(np.array([r["pit_volume"] for r in rows])), np.log1p(np.maximum(np.array([r["days_to_end"] for r in rows]), 0))])
    res = logit_vs_mlp(X, [r["o"] for r in rows], [r["mid"] for r in rows], [r["close_ts"] for r in rows], [r["cluster"] for r in rows], n_boot=n_boot, seed=seed)
    stat["walk_forward"] = res
    n = res.get("n_markets_tested", 0)
    if n == 0:
        return _finish([("walk-forward log loss MLP - logit < 0 with interval excluding 0", None, False)], 0, min_n, stat, res.get("note", "no test fold"))
    lo, hi = res["diff_ci"]
    ok = bool(res["diff_mean"] < 0 and hi < 0)
    crit = [("walk-forward log-loss difference MLP - logit < 0 with the event-clustered 95% interval excluding 0", ok, bool(lo > 0))]
    text = (f"{res['n_obs_tested']} test observations on {n} markets ({res['n_clusters']} events, {res['n_folds_run']} folds, embargo {res['embargo_days']:.0f} d): "
            f"log loss MLP {_fmt(res['logloss_mlp'], 4)} vs logit {_fmt(res['logloss_logit'], 4)} (market price {_fmt(res['logloss_market_price'], 4)}); "
            f"difference {_fmt(res['diff_mean'], 4)} [{_fmt(lo, 4)}, {_fmt(hi, 4)}], MLP better in {res['folds_mlp_better']}/{res['n_folds_run']} folds")
    return _finish(crit, n, min_n, stat, text)


# ============================================================================================ T-32 low rank ==

def effective_rank(C: np.ndarray) -> tuple[float, float]:
    """(entropy effective rank, top eigenvalue) of a symmetric PSD matrix."""
    lam = np.clip(np.linalg.eigvalsh(C), 0, None)
    s = lam.sum()
    if s <= 0:
        return float("nan"), float("nan")
    w = lam / s; w = w[w > 0]
    return float(math.exp(-(w * np.log(w)).sum())), float(lam.max())


def low_rank_windows(series: dict, start_day: int, end_day: int, T: int = 120, step: int = 30, cap: int = 60, min_markets: int = 50,
                     min_active: int = 10, trim_days: int = 3, draws: int = 5) -> dict:
    """``series``: unit (one per event) -> (day index array sorted, price array, close day or None). For every window start
    (step days apart) the units alive over the whole window (first day <= start, last day >= end, end <= close - trim) with
    >= min_active nonzero daily changes are the candidates; windows with fewer than min_markets are skipped; up to ``draws``
    disjoint hash-ordered subsets of ``cap`` units (q = n / (T - 1) stays below 1) give the effective-rank ratio and the top
    eigenvalue against the Marchenko-Pastur edge (1 + sqrt(q))^2. Pooled over windows (rule 10) with the per-window range."""
    keys = list(series)
    order = sorted(keys, key=_h01)
    wins = []
    for s in range(start_day, end_day - T + 2, step):
        e = s + T - 1
        grid = np.arange(s, e + 1)
        cands = []
        for k in order:
            days, ps, close = series[k]
            if days.size == 0 or days[0] > s or days[-1] < e or (close is not None and e > close - trim_days):
                continue
            idx = np.searchsorted(days, grid, side="right") - 1
            x = np.diff(ps[idx])
            if np.count_nonzero(x) < min_active or x.std() == 0:
                continue
            cands.append(x)
        if len(cands) < min_markets:
            wins.append({"start_day": int(s), "n_candidates": len(cands), "skipped": True})
            continue
        n_draw = max(1, min(draws, len(cands) // cap)) if len(cands) >= cap else 1
        res = []
        for j in range(n_draw):
            sub = cands[j * cap:(j + 1) * cap] if len(cands) >= cap else cands
            M = np.array(sub); n = M.shape[0]
            C = np.corrcoef(M)
            er, lam1 = effective_rank(C)
            q = n / (T - 1); lam_plus = (1 + math.sqrt(q)) ** 2
            res.append({"n": n, "eff_rank": er, "ratio": er / n, "lam1": lam1, "lam_plus": lam_plus, "lam1_over_plus": lam1 / lam_plus})
        wins.append({"start_day": int(s), "n_candidates": len(cands), "skipped": False, "n": int(np.mean([r["n"] for r in res])),
                     "ratio": float(np.mean([r["ratio"] for r in res])), "eff_rank": float(np.mean([r["eff_rank"] for r in res])),
                     "lam1_over_plus": float(np.mean([r["lam1_over_plus"] for r in res])), "lam_plus": res[0]["lam_plus"], "draws": n_draw})
    scored = [w for w in wins if not w["skipped"]]
    out = {"T_days": T, "step_days": step, "cap": cap, "n_windows": len(wins), "n_windows_scored": len(scored), "windows": wins}
    if scored:
        rat = np.array([w["ratio"] for w in scored]); top = np.array([w["lam1_over_plus"] for w in scored])
        out.update({"pooled_ratio": float(rat.mean()), "ratio_range": [float(rat.min()), float(rat.max())], "pooled_lam1_over_plus": float(top.mean()),
                    "lam1_over_plus_range": [float(top.min()), float(top.max())], "share_windows_top_outside_mp": float(np.mean(top > 1)),
                    "share_windows_ratio_below_0.1": float(np.mean(rat < 0.1)), "n_min": int(min(w["n"] for w in scored)), "n_median": float(np.median([w["n"] for w in scored]))})
    else:
        out.update({"pooled_ratio": None, "pooled_lam1_over_plus": None, "n_min": 0, "n_max_candidates": max((w["n_candidates"] for w in wins), default=0)})
    return out


def b6c_pmcal_low_rank(archive, T: int = 120, step: int = 30, cap: int = 60, min_n: int = 50):
    """T-32: effective rank of the correlation matrix of daily price changes across concurrent markets < 0.1 n and the top
    eigenvalue outside the Marchenko-Pastur bound. One market per event (resolved long-lived markets by hash, plus the open
    one-per-event histories), windows of T days at every 30-day start from 2024-01-01, the last 3 days before a market's
    close dropped, markets with fewer than 10 nonzero changes dropped; at most ``cap`` markets per window (T > 2n) so the
    matrix is not mechanically rank-deficient. The pooled all-start statistics are the criteria (rule 10). n = markets per window."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY])
    if miss:
        return miss
    series, meta, outs = _daily_series(archive), _closed_meta(archive), _outcomes(archive)
    units: dict[str, tuple] = {}
    for mid in sorted(series, key=_h01):                       # one market per event, chosen by hash (never by price or volume)
        s = meta.get(mid)
        if s is None:
            continue
        key = cluster_key(s)
        if key in units:
            continue
        ts, ps = series[mid]
        close = outs[mid]["close_ts"] if mid in outs else (_ts(s.get("closedTime")) or _ts(s.get("endDate")))
        units[key] = (np.floor(ts / DAY).astype(int), ps, None if close is None else int(close // DAY))
    n_closed = len(units)
    for mid, (ts, ps, eid) in _open_series(archive).items():
        key = f"event:{eid}"
        if key in units:
            continue
        units[key] = (np.floor(ts / DAY).astype(int), ps, None)
    last = max((u[0][-1] for u in units.values() if u[0].size), default=0)
    day0 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() // DAY)
    res = low_rank_windows(units, day0, int(last), T=T, step=step, cap=cap, min_markets=min_n)
    long = low_rank_windows(units, day0, int(last), T=250, step=50, cap=120, min_markets=min_n)
    stat = {"units_closed_one_per_event": n_closed, "units_open_one_per_event": len(units) - n_closed, "result": res,
            "longer_window_sensitivity": {k: long.get(k) for k in ("T_days", "cap", "n_windows_scored", "pooled_ratio", "ratio_range", "pooled_lam1_over_plus", "n_min", "n_median")},
            "mp_edge": "(1 + sqrt(n / (T - 1)))^2 for a correlation matrix", "changes": "daily probability-point changes, forward-filled on the calendar grid"}
    n = res.get("n_min", 0)
    if res["n_windows_scored"] == 0:
        crit = [("pooled effective rank < 0.1 n", None, False), ("top eigenvalue outside the MP bound", None, False)]
        return _finish(crit, 0, min_n, stat, f"no {T}-day window holds {min_n} concurrent distinct-event markets (most candidates {res.get('n_max_candidates')})")
    r = res["pooled_ratio"]; top = res["pooled_lam1_over_plus"]
    crit = [("pooled effective rank of the correlation matrix < 0.1 n", r < 0.1, bool(res["ratio_range"][0] >= 0.1)),
            ("top eigenvalue outside the Marchenko-Pastur bound (pooled lam1 / lam_plus > 1)", top > 1, bool(res["lam1_over_plus_range"][1] <= 1))]
    text = (f"{res['n_windows_scored']} of {res['n_windows']} {T}-day windows scored with n {res['n_min']}..{int(max(w['n'] for w in res['windows'] if not w['skipped']))} "
            f"distinct-event markets each ({len(units)} units: {n_closed} resolved + {len(units) - n_closed} open): pooled effective rank / n {_fmt(r)} "
            f"(per-window {_fmt(res['ratio_range'][0])}..{_fmt(res['ratio_range'][1])}, {_fmt(res['share_windows_ratio_below_0.1'], 2)} of windows below 0.1); "
            f"pooled top eigenvalue / MP edge {_fmt(top, 2)} (range {_fmt(res['lam1_over_plus_range'][0], 2)}..{_fmt(res['lam1_over_plus_range'][1], 2)}, "
            f"outside the edge in {_fmt(res['share_windows_top_outside_mp'], 2)} of windows); 250-day windows with up to 120 markets: "
            f"{long['n_windows_scored']} windows, pooled ratio {_fmt(long.get('pooled_ratio'))}, top / edge {_fmt(long.get('pooled_lam1_over_plus'), 2)}")
    return _finish(crit, n, min_n, stat, text)


# ======================================================================================== T-359 late favorite ==

def late_favorite(outcomes: dict, series: dict, meta: dict, days: Sequence[int] = (3, 2, 1), lo: float = 0.90, hi: float = 0.98, spread: float = 0.01,
                  contrast_day: int = 14, max_stale: float = 1.5 * DAY, n_boot: int = N_BOOT, seed: int = SEED, fee_schedule_all: bool = False) -> dict:
    """Entries at the scheduled end date minus 3, 2 or 1 days (first qualifying), leading side in [lo, hi], cost = p + spread +
    the market's fee, payoff 1 / 0 at resolution; the calibration slope of outcome on the YES price at the first available of
    those days over every resolved market with an end date. The horizon contrast is the SAME RULE EXECUTED AT end - 14 d on
    every resolved market that qualifies then (unconditional), compared with the final-3-day rule by a cluster bootstrap of
    the two rules' means over the union of their markets; the pairing on markets qualifying at BOTH horizons conditions the
    day-14 arm on the price staying inside the bin for the next 11 days (a future path that excludes the crashes and the
    run-ups past ``hi``) and is reported only."""
    ent, slope_rows, d14_all = [], [], []
    for mid, o in outcomes.items():
        sv = series.get(mid); end = o.get("end_ts")
        if sv is None or end is None:
            continue
        ts, ps = sv; close = o["close_ts"]; s = meta.get(mid, {})
        ck = cluster_key(s) if s else f"market:{mid}"
        c14 = end - contrast_day * DAY
        p14, _ = _price_before(ts, ps, c14, max_stale) if c14 <= close else (None, None)
        d14 = None
        if p14 is not None:
            q14 = max(p14, 1 - p14); side14 = 1 if p14 >= 0.5 else 0
            if lo <= q14 <= hi:                                # the unconditional day-14 rule: every market qualifying at end - 14 d
                cost14 = q14 + spread + pm_fee(q14, s.get("feeType"), bool(s.get("feesEnabled")), fee_schedule_all)
                d14 = {"mid": mid, "cluster": ck, "ret14": ((1 if side14 == o["outcome"] else 0) - cost14) / cost14, "q14": q14}
                d14_all.append(d14)
        first_p = None
        for d in days:
            cutoff = end - d * DAY
            if cutoff > close:
                continue                                       # the market closed before this day: a post-outcome price
            p, _ = _price_before(ts, ps, cutoff, max_stale)
            if p is None:
                continue
            if first_p is None:
                first_p = p; slope_rows.append((p, o["outcome"], cluster_key(s) if s else f"market:{mid}"))
            q = max(p, 1 - p); side = 1 if p >= 0.5 else 0
            if lo <= q <= hi:
                fee = pm_fee(q, s.get("feeType"), bool(s.get("feesEnabled")), fee_schedule_all)
                cost = q + spread + fee; win = 1 if side == o["outcome"] else 0
                e = {"mid": mid, "cluster": ck, "close_ts": close, "q": q, "side": side, "day": d, "win": win, "fee": fee,
                     "ret": (win - cost) / cost, "edited_end": None}
                ue, ed = _ts(s.get("umaEndDate")), _ts(s.get("endDate"))
                e["edited_end"] = None if (ue is None or ed is None) else bool(abs(ue - ed) > DAY)
                if p14 is not None:
                    if d14 is not None:                        # both-horizons pairing (sensitivity: conditions on staying in the bin)
                        e["ret14"] = d14["ret14"]; e["q14"] = d14["q14"]
                    qs = p14 if side == 1 else 1 - p14          # sensitivity: the final-3-day side bought at day 14 (conditions on later information)
                    cs = qs + spread + pm_fee(qs, s.get("feeType"), bool(s.get("feesEnabled")), fee_schedule_all)
                    e["ret14_same_side"] = (win - cs) / cs
                ent.append(e)
                break
    out = {"n_entries": len(ent), "n_slope_markets": len(slope_rows)}
    if not ent:
        return out
    ret = np.array([e["ret"] for e in ent]); keys = [e["cluster"] for e in ent]
    cm = cluster_mean(ret, keys, n_boot, seed)
    rng = np.random.default_rng(seed + 7)
    qs = np.array([e["q"] for e in ent]); costs = qs + spread + np.array([e["fee"] for e in ent])
    null = np.array([(((rng.random(qs.size) < qs) - costs) / costs).mean() for _ in range(n_boot)])
    out.update({"mean_net_return": cm["mean"], "ci": cm["ci"], "p_cluster": cm["p_le0"], "n_clusters": cm["n_clusters"],
                "p_parametric_bernoulli": float(np.mean(null >= ret.mean())), "null_mean_bernoulli": float(null.mean()),
                "win_rate": float(np.mean([e["win"] for e in ent])), "mean_price": float(qs.mean()), "mean_fee": float(np.mean([e["fee"] for e in ent])),
                "entries_by_day": {str(d): int(sum(1 for e in ent if e["day"] == d)) for d in days},
                "side_yes_share": float(np.mean([e["side"] for e in ent]))})
    # halves by resolution date
    o_ = np.argsort([e["close_ts"] for e in ent]); h = len(ent) // 2
    halves = []
    for part in (o_[:h], o_[h:]):
        c = cluster_mean(ret[part], [keys[i] for i in part], n_boot, seed) if part.size else {"mean": None, "ci": [None, None], "n": 0}
        halves.append({"n": int(part.size), "mean": c["mean"], "ci": c["ci"], "first_close": _day_of(ent[int(part[0])]["close_ts"]) if part.size else None})
    out["halves"] = halves
    # day-14 contrast: the same rule executed unconditionally at end - 14 d, against the final-3-day rule (union of their markets)
    if d14_all:
        r14 = np.array([d["ret14"] for d in d14_all]); k14 = [d["cluster"] for d in d14_all]
        cd = cluster_mean_diff(ret, keys, r14, k14, n_boot, seed)
        ent_mids = {e["mid"] for e in ent}
        both = [d["ret14"] for d in d14_all if d["mid"] in ent_mids]; only14 = [d["ret14"] for d in d14_all if d["mid"] not in ent_mids]
        out["day14"] = {"n_day14": len(d14_all), "n_final3": len(ent), "mean_net_return_day14": cd["mean_b"], "mean_net_return_final3": cd["mean_a"],
                        "diff": cd["diff"], "diff_ci": cd["ci"], "p_le0": cd["p_le0"], "n_clusters_union": cd["n_clusters"],
                        "win_rate_day14": float(np.mean(r14 > 0)), "mean_price_day14": float(np.mean([d["q14"] for d in d14_all])),
                        "n_day14_also_final3": len(both), "mean_day14_also_final3": float(np.mean(both)) if both else None,
                        "n_day14_not_final3": len(only14), "mean_day14_not_final3": float(np.mean(only14)) if only14 else None,
                        "rule": "every resolved market whose leading side is in [lo, hi] at end - 14 d (not after its close), same costs; diff = final-3 mean - day-14 mean, "
                                "cluster bootstrap over the union of the two rules' markets"}
    else:
        out["day14"] = None
    # both-horizons pairing (sensitivity): conditions the day-14 arm on the price staying inside the bin until the final 3 days
    pair = [e for e in ent if "ret14" in e]
    if pair:
        dp = np.array([e["ret"] - e["ret14"] for e in pair]); c14 = cluster_mean(dp, [e["cluster"] for e in pair], n_boot, seed)
        out["day14_paired_sensitivity"] = {"n": len(pair), "mean_net_return_day14": float(np.mean([e["ret14"] for e in pair])),
                                           "mean_net_return_final3_same_markets": float(np.mean([e["ret"] for e in pair])),
                                           "paired_diff": c14["mean"], "paired_diff_ci": c14["ci"], "mean_price_day14": float(np.mean([e["q14"] for e in pair])),
                                           "note": "paired on markets qualifying at BOTH horizons: the day-14 arm is conditioned on the price staying in [lo, hi] "
                                                   "for the next 11 days (a future path that excludes crashes and run-ups past hi); reported only"}
    else:
        out["day14_paired_sensitivity"] = None
    same = [e for e in ent if "ret14_same_side" in e]
    out["day14_same_side_sensitivity"] = {"n": len(same), "mean_net_return_day14_same_side": float(np.mean([e["ret14_same_side"] for e in same])),
                                          "note": "buys the side that leads in the final 3 days at its day-14 price: conditions on later information, reported only"} if same else None
    # calibration slope of outcome on the YES price over every resolved market
    if len(slope_rows) >= 10:
        P = np.array([r[0] for r in slope_rows]); O = np.array([r[1] for r in slope_rows], float); K = [r[2] for r in slope_rows]

        def slope(w):
            mp, mo = _wmean(P, w), _wmean(O, w); vp = (w * (P - mp) ** 2).sum()
            return float((w * (P - mp) * (O - mo)).sum() / vp) if vp > 0 else float("nan")
        lo_s, hi_s = _cluster_stat_ci(K, slope, n_boot, seed)
        out["calibration_slope"] = {"slope": slope(np.ones(P.size)), "ci": [lo_s, hi_s], "n": int(P.size), "n_clusters": _n_clusters(K)}
    else:
        out["calibration_slope"] = None
    # sensitivities
    sens = {}
    unedited = [i for i, e in enumerate(ent) if e["edited_end"] is not True]
    if unedited and len(unedited) < len(ent):
        c = cluster_mean(ret[unedited], [keys[i] for i in unedited], n_boot, seed)
        sens["excluding_edited_end_dates"] = {"n": len(unedited), "mean": c["mean"], "ci": c["ci"], "n_edited": len(ent) - len(unedited)}
    else:
        sens["excluding_edited_end_dates"] = {"n": len(ent), "n_edited": 0}
    out["sensitivities"] = sens
    return out


def b6c_pmcal_late_favorite(archive, min_n: int = 400, n_boot: int = N_BOOT, seed: int = SEED):
    """T-359: leading side in [0.90, 0.98] at the scheduled end minus 3 / 2 / 1 days, bought at p + 0.01 + the market's fee, held
    to resolution. Pass: mean net return per dollar > 0 with cluster-bootstrap p < 0.05 (and the named Bernoulli(p) parametric
    bootstrap: rule 11), calibration slope of outcome on the final-3-day price > 1, both halves by resolution date positive,
    and beating the day-14 entry on the same markets. Voids (0.5 / 0.5) are counted and excluded. n = entries (one per market)."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY])
    if miss:
        return miss
    meta, outs, series = _closed_meta(archive), _outcomes(archive), _daily_series(archive)
    res = late_favorite(outs, series, meta, n_boot=n_boot, seed=seed)
    res["voids_counted_excluded"] = _void_count(meta); res["n_resolved_with_history"] = len(outs); res["n_markets_with_history"] = len(meta)
    res["postponed_flagged"] = int(sum(1 for o in outs.values() if o.get("postponed_flag")))
    stat = {"late_favorite": res, "fee_schedule_on_all_sensitivity": None}
    n = res.get("n_entries", 0)
    names = ["mean net return > 0 with cluster-bootstrap p < 0.05 (and Bernoulli(p) parametric p < 0.05)", "calibration slope of outcome on price in the final 3 days > 1",
             "both halves by resolution date positive", "beating the day-14 entry (the same rule executed unconditionally at end - 14 d)"]
    if n == 0:
        return _finish([(nm, None, False) for nm in names], 0, min_n, stat, "no leading side in [0.90, 0.98] within the final three days before the scheduled end")
    alt = late_favorite(outs, series, meta, n_boot=200, seed=seed, fee_schedule_all=True)
    stat["fee_schedule_on_all_sensitivity"] = {"mean_net_return": alt.get("mean_net_return"), "n": alt.get("n_entries")}
    lo, hi = res["ci"]; pc, pp = res["p_cluster"], res["p_parametric_bernoulli"]
    c1 = True if (res["mean_net_return"] > 0 and pc < 0.05 and pp < 0.05) else (False if (pc >= 0.05 and pp >= 0.05) or res["mean_net_return"] <= 0 else None)
    sl = res.get("calibration_slope")
    c2 = None if sl is None else bool(sl["slope"] > 1)
    hv = res["halves"]
    c3 = bool(all(h["mean"] is not None and h["mean"] > 0 for h in hv))
    d14 = res.get("day14"); pr = res.get("day14_paired_sensitivity")
    c4 = None if (d14 is None or d14["diff"] is None) else bool(d14["diff"] > 0)
    crit = [(names[0], c1, bool(hi < 0)), (names[1], c2, bool(sl is not None and math.isfinite(sl["ci"][1]) and sl["ci"][1] < 1)),
            (names[2], c3, bool(any(h["ci"][1] is not None and h["ci"][1] < 0 for h in hv))),
            (names[3], c4, bool(d14 is not None and d14["diff_ci"][1] is not None and d14["diff_ci"][1] < 0))]
    text = (f"{n} entries ({res['n_clusters']} events; {res['voids_counted_excluded']} voids counted and excluded, {res['n_resolved_with_history']} resolved markets with history): "
            f"mean net return per dollar {_fmt(res['mean_net_return'], 4)} [{_fmt(lo, 4)}, {_fmt(hi, 4)}], cluster p {_fmt(pc)}, Bernoulli(p) p {_fmt(pp)} "
            f"(win rate {_fmt(res['win_rate'])} at mean price {_fmt(res['mean_price'])}, mean fee {_fmt(res['mean_fee'], 4)})"
            + ("; the two named bootstraps disagree: undecided" if c1 is None else "")
            + (f"; calibration slope {_fmt(sl['slope'])} [{_fmt(sl['ci'][0])}, {_fmt(sl['ci'][1])}] on {sl['n']} markets" if sl else "; calibration slope not computable")
            + f"; halves {', '.join(_fmt(h['mean'], 4) for h in hv)}"
            + (f"; same rule executed unconditionally at day 14: {d14['n_day14']} markets qualify at end - 14 d, mean {_fmt(d14['mean_net_return_day14'], 4)} (win rate "
               f"{_fmt(d14['win_rate_day14'])}) vs the final-3 rule's {_fmt(d14['mean_net_return_final3'], 4)} on its {d14['n_final3']} entries, diff {_fmt(d14['diff'], 4)} "
               f"[{_fmt(d14['diff_ci'][0], 4)}, {_fmt(d14['diff_ci'][1], 4)}] (cluster bootstrap over the union); the {d14['n_day14_also_final3']} day-14 qualifiers that also "
               f"qualify in the final 3 days earn {_fmt(d14['mean_day14_also_final3'], 4)}, the {d14['n_day14_not_final3']} that leave the bin earn {_fmt(d14['mean_day14_not_final3'], 4)}"
               if d14 else "; no market qualifies under the same rule at day 14")
            + (f"; both-horizons pairing (sensitivity, conditions the day-14 arm on staying in the bin): day-14 {_fmt(pr['mean_net_return_day14'], 4)} vs final-3 "
               f"{_fmt(pr['mean_net_return_final3_same_markets'], 4)} on {pr['n']} markets, paired diff {_fmt(pr['paired_diff'], 4)} "
               f"[{_fmt(pr['paired_diff_ci'][0], 4)}, {_fmt(pr['paired_diff_ci'][1], 4)}]" if pr else "")
            + f"; excluding {res['sensitivities']['excluding_edited_end_dates'].get('n_edited', 0)} edited-end markets mean {_fmt(res['sensitivities']['excluding_edited_end_dates'].get('mean', res['mean_net_return']), 4)}")
    return _finish(crit, n, min_n, stat, text)


# ===================================================================================== T-316 shock continuation ==

def _bucket_p(p: float) -> int:
    return 0 if p < 0.30 else 1 if p < 0.45 else 2 if p < 0.55 else 3 if p < 0.70 else 4


def _bucket_days(d: Optional[float]) -> int:
    return 4 if d is None else 0 if d <= 7 else 1 if d <= 30 else 2 if d <= 90 else 3


def shock_events(series: dict, info: dict, sd_mult: float = 2.5, hold_days: int = 3, window_days: int = 30, min_obs: int = 20, lo: float = 0.15, hi: float = 0.85,
                 cost: float = 0.02, cost_fn: Optional[Callable[[float, float, bool], float]] = None, max_gap: float = 1.5 * DAY,
                 min_nonzero: int = 0) -> tuple[list[dict], dict]:
    """Shock events and control-cell means. ``series``: id -> (t, p); ``info``: id -> {close_ts, end_ts, outcome, cluster}.
    Logit change dx_t between consecutive snapshots at most max_gap apart; trailing sd over the changes of the previous
    window_days (>= min_obs); shock when |dx_t| > sd_mult sd and p_t in [lo, hi]; entry at snapshot t+1 (<= max_gap later),
    exit at the last snapshot at or before entry + hold_days or at the resolution payoff when the market closes first.
    Return = side price change in the shock direction minus cost (cost_fn(q_entry, q_exit, settled) when given). Shock
    positions never overlap within a market. Controls: every non-shock day (sd defined, dx != 0) traded the same way in the
    direction of its own change, pooled into cells (price bucket x days-to-end bucket). ``min_nonzero`` (sensitivity)
    additionally requires that many nonzero changes inside the trailing window, against stale snapshot runs."""
    events, cells = [], defaultdict(list)
    for mid, (ts, ps) in series.items():
        inf = info.get(mid)
        if inf is None or ts.size < min_obs + 3:
            continue
        close = inf["close_ts"]; end = inf.get("end_ts"); outcome = inf.get("outcome")
        pc = np.clip(ps, 0.005, 0.995); x = np.log(pc / (1 - pc))
        dx = np.diff(x); gap = np.diff(ts); valid = gap <= max_gap
        dxv = np.where(valid, dx, np.nan)
        # trailing sd of the valid changes dated at ts[1:], over the previous window_days, excluding the current change
        tch = ts[1:]; fin = np.isfinite(dxv)
        c1 = np.concatenate([[0.0], np.cumsum(np.where(fin, dxv, 0.0))]); c2 = np.concatenate([[0.0], np.cumsum(np.where(fin, dxv ** 2, 0.0))])
        cn = np.concatenate([[0], np.cumsum(fin.astype(int))])
        nz = np.concatenate([[0], np.cumsum((fin & (dxv != 0)).astype(int))])
        j0 = np.searchsorted(tch, tch - window_days * DAY, side="left")
        idx = np.arange(tch.size)
        cnt = cn[idx] - cn[j0]; s1 = c1[idx] - c1[j0]; s2 = c2[idx] - c2[j0]
        with np.errstate(invalid="ignore", divide="ignore"):
            var = np.where(cnt >= min_obs, (s2 - s1 ** 2 / np.maximum(cnt, 1)) / np.maximum(cnt - 1, 1), np.nan)
        sd = np.sqrt(np.clip(var, 0, None))
        p_t = ps[1:]
        ok = fin & np.isfinite(sd) & (sd > 0) & (p_t >= lo) & (p_t <= hi) & (ts[1:] < close) & ((nz[idx] - nz[j0]) >= min_nonzero)
        i_sig = np.arange(1, ts.size)                          # index of snapshot t in ts
        has_next = i_sig + 1 < ts.size
        nxt = np.minimum(i_sig + 1, ts.size - 1)
        ok &= has_next & ((ts[nxt] - ts[i_sig]) <= max_gap) & (ts[nxt] < close)
        if not ok.any():
            continue
        sel = np.where(ok)[0]
        direction = np.sign(dxv[sel]); shock = np.abs(dxv[sel]) > sd_mult * sd[sel]
        e_idx = nxt[sel]; t_entry = ts[e_idx]; target = t_entry + hold_days * DAY
        x_idx = np.searchsorted(ts, target, side="right") - 1
        settled = close <= target
        rets = np.empty(sel.size); q_in = np.empty(sel.size); q_out = np.empty(sel.size); keep = np.ones(sel.size, dtype=bool)
        for k in range(sel.size):
            d_ = direction[k]
            if d_ == 0:
                keep[k] = False; continue
            pe = ps[e_idx[k]]; qe = pe if d_ > 0 else 1 - pe
            if settled[k]:
                if outcome is None:
                    keep[k] = False; continue
                qx = float(outcome) if d_ > 0 else 1 - float(outcome)
            else:
                if x_idx[k] <= e_idx[k]:
                    keep[k] = False; continue
                px = ps[x_idx[k]]; qx = px if d_ > 0 else 1 - px
            c = cost_fn(qe, qx, bool(settled[k])) if cost_fn else cost
            rets[k] = qx - qe - c; q_in[k] = qe; q_out[k] = qx
        last_exit = -np.inf
        for k in range(sel.size):
            if not keep[k]:
                continue
            i = i_sig[sel[k]]; t_sig = ts[i]
            dte = None if end is None else (end - t_sig) / DAY
            cell = (_bucket_p(ps[i]), _bucket_days(dte))
            if shock[k]:
                if t_sig < last_exit:
                    continue
                exit_t = close if settled[k] else ts[x_idx[k]]
                last_exit = exit_t
                events.append({"mid": mid, "cluster": inf.get("cluster", f"market:{mid}"), "t": float(t_sig), "direction": int(direction[k]), "p": float(ps[i]),
                               "ret": float(rets[k]), "gross": float(rets[k] + (cost_fn(q_in[k], q_out[k], bool(settled[k])) if cost_fn else cost)),
                               "cell": cell, "days_to_end": dte, "settled": bool(settled[k]), "shock_sd": float(abs(dxv[sel[k]]) / sd[sel[k]]),
                               "hold_days": float((exit_t - t_entry[k]) / DAY)})
            else:
                cells[cell].append(rets[k])
    cell_means = {c: (float(np.mean(v)), len(v)) for c, v in cells.items()}
    return events, cell_means


def shock_stats(events: list[dict], cell_means: dict, n_trials: int = 36, min_cell: int = 20, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    if not events:
        return {"n_events": 0}
    ev = sorted(events, key=lambda d: d["t"])
    r = np.array([d["ret"] for d in ev]); keys = [d["cluster"] for d in ev]
    cm = cluster_mean(r, keys, n_boot, seed)
    diffs, dk, ctrl = [], [], []
    for d in ev:
        c = cell_means.get(d["cell"])
        if c and c[1] >= min_cell:
            diffs.append(d["ret"] - c[0]); dk.append(d["cluster"]); ctrl.append(c[0])
    cd = cluster_mean(np.array(diffs), dk, n_boot, seed + 1) if diffs else None
    by_dte = defaultdict(list)
    for d in ev:
        by_dte[_bucket_days(d["days_to_end"])].append(d["ret"])
    labels = {0: "<=7d", 1: "8-30d", 2: "31-90d", 3: ">90d", 4: "no end date"}
    return {"n_events": len(ev), "n_markets": len({d["mid"] for d in ev}), "mean_net": cm["mean"], "ci": cm["ci"], "p_le0": cm["p_le0"], "n_clusters": cm["n_clusters"],
            "mean_gross": float(np.mean([d["gross"] for d in ev])), "share_positive": float(np.mean(r > 0)), "share_settled_in_hold": float(np.mean([d["settled"] for d in ev])),
            "share_up_shocks": float(np.mean([d["direction"] > 0 for d in ev])), "mean_shock_sd": float(np.mean([d["shock_sd"] for d in ev])),
            "matched_controls": None if cd is None else {"n_events_matched": cd["n"], "mean_control_return": float(np.mean(ctrl)),
                                                         "mean_diff": cd["mean"], "diff_ci": cd["ci"], "n_cells": len(cell_means)},
            "dsr": _dsr(r, n_trials), "n_trials": n_trials,
            "by_days_to_end": {labels[k]: {"n": len(v), "mean_net": float(np.mean(v))} for k, v in sorted(by_dte.items())},
            "first_event": _day_of(ev[0]["t"]), "last_event": _day_of(ev[-1]["t"])}


def _kalshi_mid_series(kalshi: dict, max_spread: float = 0.10) -> tuple[dict, dict]:
    """Daily mid (bid + ask) / 2 series per Kalshi ticker where both quotes exist with a spread at most max_spread, plus info."""
    series, info = {}, {}
    for tk, (t, bid, ask, _) in kalshi["candles"].items():
        m = kalshi["markets"][tk]
        okq = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask - bid <= max_spread) & (t < m["close_ts"])
        if okq.sum() < 5:
            continue
        series[tk] = (t[okq], np.clip((bid[okq] + ask[okq]) / 2, 0, 1))
        info[tk] = {"close_ts": m["close_ts"], "end_ts": m["close_ts"], "outcome": m["result"], "cluster": f"kevent:{m['event']}"}
    return series, info


def _kalshi_cost(qe: float, qx: float, settled: bool) -> float:
    return KALSHI_FEE * qe * (1 - qe) + (0.0 if settled else KALSHI_FEE * qx * (1 - qx))


def b6c_pmcal_shock_continuation(archive, min_n: int = 300, n_boot: int = N_BOOT, seed: int = SEED):
    """T-316: 2.5-sd daily logit shock in markets priced in [0.15, 0.85], bought in the shock direction at the next snapshot and
    held 3 days (or to resolution), 2 cents round trip. Pass as worded: net mean > 0.02, market-clustered 95% interval excluding
    0 (the claim's own 'positive after cost' reading is the interval criterion), net mean above price- and days-to-end-matched
    non-shock control days, DSR > 0.95 with n_trials = 36, Kalshi replication (macro daily candles, fee formula) sign agrees.
    n = shock events."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY])
    if miss:
        return miss
    series, meta, outs = _daily_series(archive), _closed_meta(archive), _outcomes(archive)
    info = {mid: {"close_ts": o["close_ts"], "end_ts": o.get("end_ts"), "outcome": o["outcome"], "cluster": cluster_key(meta[mid])} for mid, o in outs.items()}
    pm_series = {m: series[m] for m in info if m in series}
    events, cells = shock_events(pm_series, info)
    st = shock_stats(events, cells, 36, n_boot=n_boot, seed=seed)
    ev_a, cells_a = shock_events(pm_series, info, min_nonzero=10)
    st_active = shock_stats(ev_a, cells_a, 36, n_boot=200, seed=seed)
    kal = _kalshi(archive)
    ks = None
    if kal["markets"]:
        kser, kinf = _kalshi_mid_series(kal)
        kev, kcells = shock_events(kser, kinf, cost_fn=_kalshi_cost)
        ks = shock_stats(kev, kcells, 36, n_boot=n_boot, seed=seed)
    stat = {"polymarket": st, "kalshi": ks, "active_markets_sensitivity": {"rule": ">= 10 nonzero changes in the trailing window", **{k: st_active.get(k) for k in ("n_events", "n_markets", "mean_net", "ci", "mean_gross")}},
            "rule": "shock |dlogit| > 2.5 x trailing 30-day sd (>= 20 changes), p_t in [0.15, 0.85], entry snapshot t+1, exit t+1 + 3 d or resolution payoff",
            "controls": "non-shock days traded in the direction of their own change, cells = price bucket (0.15-0.30-0.45-0.55-0.70-0.85) x days-to-end (<=7, 8-30, 31-90, >90, none)",
            "n_markets_with_history": len(meta)}
    n = st.get("n_events", 0)
    names = ["net mean 3-day post-shock return > 0.02 (pass as worded)", "market-clustered 95% interval of the net mean excludes 0 (positive after the 2-cent cost)",
             "net mean above price- and days-to-end-matched non-shock controls", "DSR > 0.95 with n_trials = 36", "Kalshi replication sign agrees"]
    if n == 0:
        return _finish([(nm, None, False) for nm in names], 0, min_n, stat, "no 2.5-sd shock events in the archived daily histories")
    lo, hi = st["ci"]; mc = st["matched_controls"]; dsr = st["dsr"]
    k_ok = None
    if ks and ks.get("n_events", 0) >= 30:
        k_ok = bool(np.sign(ks["mean_net"]) == np.sign(st["mean_net"]) and st["mean_net"] != 0)
    crit = [(names[0], st["mean_net"] > 0.02, bool(hi < 0.02)), (names[1], bool(lo > 0), bool(hi < 0)),
            (names[2], None if mc is None else bool(mc["mean_diff"] > 0), bool(mc is not None and mc["diff_ci"][1] < 0)),
            (names[3], None if dsr is None else bool(dsr > 0.95), False), (names[4], k_ok, False)]
    text = (f"{n} shock events in {st['n_markets']} markets ({st['first_event']}..{st['last_event']}): net mean {_fmt(st['mean_net'], 4)} (gross {_fmt(st['mean_gross'], 4)}), "
            f"market-clustered 95% [{_fmt(lo, 4)}, {_fmt(hi, 4)}], {_fmt(st['share_positive'], 2)} positive, {_fmt(st['share_settled_in_hold'], 2)} settled inside the hold"
            + (f"; matched controls {_fmt(mc['mean_control_return'], 4)} on {mc['n_events_matched']} matched events, diff {_fmt(mc['mean_diff'], 4)} [{_fmt(mc['diff_ci'][0], 4)}, {_fmt(mc['diff_ci'][1], 4)}]" if mc else "; no matched control cell")
            + f"; DSR {_fmt(dsr)} (n_trials 36); active-market sensitivity (>= 10 nonzero trailing changes) {st_active.get('n_events', 0)} events, net mean {_fmt(st_active.get('mean_net'), 4)}"
            + (f"; Kalshi replication {ks['n_events']} events in {ks['n_markets']} markets, net mean {_fmt(ks['mean_net'], 4)} [{_fmt(ks['ci'][0], 4)}, {_fmt(ks['ci'][1], 4)}]"
               + (" (fewer than 30 events: not scored)" if ks["n_events"] < 30 else "") if ks and ks.get("n_events") else "; Kalshi replication: no events in the archived macro candles (kalshi-candles-daily-<S>)"))
    return _finish(crit, n, min_n, stat, text)


# ======================================================================================================= map ==

HARNESSES = {
    "b6c_pmcal_volume_calibration": b6c_pmcal_volume_calibration,
    "b6c_pmcal_near_certain_carry": b6c_pmcal_near_certain_carry,
    "b6c_pmcal_mlp_vs_logit": b6c_pmcal_mlp_vs_logit,
    "b6c_pmcal_low_rank": b6c_pmcal_low_rank,
    "b6c_pmcal_late_favorite": b6c_pmcal_late_favorite,
    "b6c_pmcal_shock_continuation": b6c_pmcal_shock_continuation,
}

THEORY_MAP = {
    "T-12": "b6c_pmcal_volume_calibration",
    "T-378": "b6c_pmcal_near_certain_carry",
    "T-31": "b6c_pmcal_mlp_vs_logit",
    "T-32": "b6c_pmcal_low_rank",
    "T-359": "b6c_pmcal_late_favorite",
    "T-316": "b6c_pmcal_shock_continuation",
}
