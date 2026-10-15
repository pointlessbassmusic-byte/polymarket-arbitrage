"""
Prediction-market history for the batch-6c claims: Polymarket (Gamma, CLOB, data-api) and Kalshi (trade-api v2).
================================================================================================================

Which claims need what (batch-6c triage ``final`` entries whose fetch text names gamma-api / clob / data-api
.polymarket.com or api.elections.kalshi.com, plus each theory's ``trial.data`` in mandel/theories/registry.json):

  T-12   more resolved markets 2024-26 with daily prices (n >= 400 at 7 d) and a     -> polymarket-closed-markets-<M>,
         point-in-time volume rank (Gamma volume is end-of-life)                        polymarket-price-history-daily-<M>,
                                                                                         polymarket-volume-hourly-<M>
  T-31   >= 500 markets with price, days to close and point-in-time log volume       -> same three families
  T-32   >= 50 distinct-event markets alive together for T >= 100 days               -> closed-markets (events[].id) +
                                                                                         daily (every market living >= 100 d)
  T-359  ~4,500+ resolved markets with daily history (9% qualify); Kalshi arm        -> closed-markets + daily; Kalshi
                                                                                         hourly candles (end - k days)
  T-378  >= 500 markets: Polymarket daily + Kalshi settled markets with daily        -> closed-markets + daily;
         yes_bid / yes_ask since 2021                                                   kalshi-settled-markets-<S>,
                                                                                         kalshi-candles-daily-<S>
  T-316  Kalshi replication set (daily bid/ask of liquid series); wider Polymarket   -> kalshi-candles-daily-<S>; daily
  T-358  Kalshi KXCPI, KXFED, KXFEDDECISION, KXPAYROLLS events 2021-07 .. with daily  -> kalshi-settled-markets-<S>,
         candles (p three trading days before); older Polymarket event markets          kalshi-candles-daily-<S>; daily
  T-360  Kalshi KXCPI markets 2021-07 .. and hourly candles (16:00 ET bar before     -> kalshi-settled-markets-KXCPI,
         each release)                                                                  kalshi-candles-hourly-KXCPI
  T-337  Polymarket "Bitcoin above" weekly (2024) and multi-strike daily (2025-26)   -> polymarket-events-btc-above,
         events with hourly prices                                                      polymarket-price-history-hourly-<M>
  T-336  hand-auditable Polymarket-Kalshi pairs (FOMC, CPI, BTC thresholds) with     -> pm-kalshi-pairs,
         hourly prices on both venues                                                   polymarket-price-history-hourly-<M>,
                                                                                         kalshi-candles-hourly-<S>
  T-409  >= 40 pairs (FOMC, CPI, 2024 election, BTC) with hourly prices and hourly   -> the T-336 families +
         Polymarket volume to pick the leader                                           polymarket-volume-hourly-<M>
  T-408  non-combo settled Kalshi markets with hourly bid/ask across many series;    -> kalshi-candles-hourly-<S>;
         Polymarket replication on the largest resolved markets                         polymarket-price-history-hourly-<M>
  T-411  Kalshi trades + hourly candles, >= 1,500 market-days                        -> kalshi-trades-<S>,
  T-463  Kalshi trades + hourly candles, >= 3,000 out-of-sample flow signals;           kalshi-candles-hourly-<S>;
         Polymarket taker-flow replication                                              polymarket-volume-hourly-<M>

Every row is {source, kind, key, observed_at, available_at, value} with ISO UTC times. <M> is a calendar month YYYY-MM
of the market's endDate (UTC); <S> a Kalshi series ticker (KXBTCD bundles are split by month: <S>-<M>).

Polymarket (keyless; paced at 0.5 s per request, 429 / 5xx retried with backoff and Retry-After via options_misc._get)
-----------------------------------------------------------------------------------------------------------------------
1. ``polymarket-closed-markets-<M>`` (same row schema as ``polymarket-closed-markets``: value = the raw Gamma market row,
   observed_at = closedTime (else endDate), available_at = fetch time: Gamma rows are end-of-life snapshots).
   ``GET {GAMMA}/markets/keyset?closed=true&limit=100&end_date_min=<D 00:00Z>&end_date_max=<D+1 00:00Z>
   &volume_num_min=10000&start_date_max=<D - 3 days 00:00Z>&after_cursor=<next_cursor>``, one UTC day D at a time
   (probed 2026-10-15: pages hold at most 100 rows whatever ``limit`` says, ~5 KB per row; plain /markets offset paging
   is refused beyond ~2,000 rows, so keyset is the only complete route). ``end_date_max`` is inclusive, so a row is kept
   only in the window that holds its endDate. The universe is fixed by rule: endDate 2023-01-01 .. yesterday, lifetime
   startDate -> endDate of at least 3 days (every market living >= 4 days is included; 58% of 2026-03's markets lived
   under 2 days: crypto up/down, single games, useless at daily horizons), volumeNum >= $10k (end-of-life volume: a
   selection on Gamma's final metadata, stated). Markets ending before 2023 are AMM-era: the CLOB has no history for
   them (probed: 2022-06 .. 2023-01 markets answer an empty history), so the window starts 2023-01. Measured sizes
   (volume >= $10k, no lifetime filter): 2023-03: 50 markets; 2024-03: 292; 2024-09: 1,168; 2025-03: 2,191;
   2025-09: ~7,500; 2026-09: > 15,000 at >= $50k. A month is complete once every day was fetched and 45 days have
   passed since month end (late resolutions); open months are stored with tag ``partial`` and fetched again.
2. ``polymarket-price-history-daily-<M>`` (same schema as ``polymarket-price-history-daily``: value = {market_id, token,
   p, t}, observed_at = available_at = t). ``GET {CLOB}/prices-history?market=<YES token>&interval=max&fidelity=1440``
   (one call per market; startTs/endTs spans of ~90 days at fidelity 1440 answer 400 'interval is too long'). Probed:
   the daily point at t equals the hourly point at the same t, and the hourly points of the following 22-24 hours equal
   the next daily point, so a point is the price prevailing AT t (a snapshot), not an aggregate of the day after it:
   available_at = t is point in time. Which markets: per month, every binary market of a scheduled-event family (FOMC,
   CPI / inflation, payrolls, GDP, US elections: T-358 and the pairs) and every market living >= 100 days (T-32), plus a
   deterministic hash sample (sha256 of the market id) of ``per_month`` (default 200) of the others. The hash sample
   does not depend on volume, price or outcome. ``polymarket-fetch-log`` records each market's selection reason and the
   month's sample rate (for reweighting); a harness wanting an unbiased population uses reason ``sample``.
3. ``polymarket-events-btc-above`` and ``polymarket-events-macro`` (kind ``event``, value = the raw Gamma event with its
   nested markets, observed_at = endDate, available_at = fetch time). ``GET {GAMMA}/public-search?q=<q>&events_status=
   closed&limit_per_type=50&page=<n>`` while pagination.hasMore ("bitcoin above": 5,521 events on 2026-10-15, hourly-ET
   variants such as bitcoin-above-on-april-6-2026-9pm-et included; macro: "fed decision", "fed interest rates",
   "inflation", "cpi", kept when the slug is a US FOMC / CPI template) and ``GET {GAMMA}/events?slug=<slug>`` for the two
   2024 election events (presidential-election-winner-2024, presidential-election-popular-vote-winner-2024).
4. ``polymarket-price-history-hourly-<M>`` (value = {market_id, token, p, t}, available_at = t). ``GET {CLOB}/
   prices-history?market=<YES token>&startTs=<s>&endTs=<e>&fidelity=60`` in windows of 14 days (probed: 14 days -> 335
   points; 21 and 30 days -> 400 'interval is too long'; interval=max at fidelity 60 is empty for resolved markets).
   Targets: (a) the BTC-above daily and weekly markets (T-337; hourly-ET variants excluded, they live one day),
   (b) every Polymarket leg of ``pm-kalshi-pairs`` (T-336 / T-409), (c) the 399 markets of the legacy
   polymarket-price-history-daily, last 56 days before close (T-408 replication).
5. ``polymarket-volume-hourly-<M>`` (kind ``volume``; value = {market_id, condition_id, t (hour start), n, shares, usd,
   o0, o1} with per-outcome-index {n_buy, n_sell, buy, sell, buy_usd, sell_usd, last_p}; observed_at = t, available_at
   = t + 1 h). ``GET {DATA}/trades?market=<conditionId>&limit=10000&takerOnly=true&end=<unix>``, paged backwards: the
   next page ends at the oldest timestamp seen (``end`` is inclusive: duplicates at the boundary are dropped). Probed
   2026-10-15: one row per taker order, and the taker sizes of market 516852 sum to 11,852.17 shares = its Gamma
   volumeNum exactly; takerOnly=false adds every maker fill (each fill twice, 23,704 shares), so taker-only rows are
   the complete, non-double-counted volume and carry the aggressor side (T-463). A page holds at most 10,000 trades
   (~0.9 KB each); ``offset`` is capped at 10,000 but ``end`` paging is not. Point-in-time volume at a decision time t =
   sum of shares over hours ending <= t (or volumeNum minus the shares after t, exact because volumeNum is the taker
   sum). A market capped by ``max_pages`` is paged newest first, so its hours from ``complete_from`` on are complete
   (the fetch log says so) and the subtraction route still works for horizons after that. data-api has no trades for
   2023 markets (triage probe), so targets end 2024-01-01 or later: the pair legs plus a hash sample (default 1,500)
   of the daily-history ``sample`` markets.

Kalshi (keyless; paced at 1.0 s per request because shared-host probes met 429 too_many_requests; Retry-After honoured)
-----------------------------------------------------------------------------------------------------------------------
``GET {KALSHI}/historical/cutoff`` gives the split between the historical and live stores (market_settled_ts and
trades_created_ts = 2026-08-16 on 2026-10-15); the historical routes serve what settled or traded before it.
6. ``kalshi-settled-markets-<S>`` (same row schema as ``kalshi-settled-markets``: value = raw market row, observed_at =
   settlement_ts (else close_time), available_at = fetch time). ``GET {KALSHI}/historical/markets?series_ticker=<S>
   &limit=1000&cursor=<c>`` plus ``GET {KALSHI}/markets?series_ticker=<S>&status=settled&limit=1000&cursor=<c>``,
   de-duplicated by ticker. Pre-2024 markets sit inside the KX series under legacy tickers (CPI-21JUN, FED-21JUL,
   FEDDECISION-23JUN, PROLLS-23SEP). KXMVE* combos are never fetched. KXBTCD is listed by event instead (the series has
   an event every hour with up to 188 strikes, most never traded, each living one hour): the daily 17:00 ET event
   ``KXBTCD-<YY><MON><DD>17`` (lives 25 h in 2024-11, 168 h in 2025-03) for every day from 2025-01-01, via
   ``/historical/markets?event_ticker=`` (or ``/markets?event_ticker=`` after the cutoff); only strikes with
   volume > 0 are kept, in monthly bundles ``kalshi-settled-markets-KXBTCD-<M>``.
7. ``kalshi-candles-daily-<S>`` / ``kalshi-candles-hourly-<S>`` (same row schema as ``kalshi-candles``: value =
   {ticker, period, candle (raw: end_period_ts, yes_bid / yes_ask OHLC, price OHLC + mean, volume, open_interest)},
   observed_at = available_at = end_period_ts: a candle is known once its period has closed). ``GET {KALSHI}/historical/
   markets/<T>/candlesticks?start_ts&end_ts&period_interval=<1440|60>`` for markets settled before the cutoff, else
   ``GET {KALSHI}/series/<S>/markets/<T>/candlesticks``; the other route is tried when the first is empty. At most 5,000
   candles per request (probed: a 303-day hourly span answers 400 'max candlesticks: 5000'), so windows hold 4,800
   periods. The two routes name the candle fields differently (historical: close, volume, open_interest; live:
   close_dollars, volume_fp, open_interest_fp); the raw candle is kept and ``candle_fields`` reads either.
   Hourly bars skip hours with no activity: forward-fill quotes in the harness. Illiquid hours quote bid 0 /
   ask 1: filter by spread. Daily candles: every traded market of KXCPI, KXFED, KXFEDDECISION, KXPAYROLLS (T-358,
   T-378, T-316). Hourly: every traded market of the macro and election series, a hash sample of 150 markets with
   volume >= 1,000 contracts per sports / weather series, and the 4 most traded strikes of each KXBTCD 17:00 event.
8. ``kalshi-trades-<S>`` (kind ``trade``, value = the raw trade {trade_id, ticker, created_time, yes_price_dollars,
   no_price_dollars, count_fp, taker_side, taker_outcome_side, taker_book_side, is_block_trade}, observed_at =
   available_at = created_time: a print is public at execution). ``GET {KALSHI}/historical/trades?ticker=<T>&limit=1000
   &cursor=<c>`` before the cutoff and ``GET {KALSHI}/markets/trades?ticker=<T>`` after it (both when a market spans
   it), newest first. Markets: the first 60 (macro) / 100 (others) of the hourly-candle hash order with volume >= 1,000
   contracts, so every traded market also has its candles; KXBTCD 10 per month. Pages are capped (``max_pages``, 15 =
   15,000 trades); a capped market is complete from ``complete_from`` on (fetch log).

Cross-venue pairs (no request: built from the stored listings) -> ``pm-kalshi-pairs``
--------------------------------------------------------------------------------------
Matching is templated and uses only fields fixed when the markets were listed (tickers, strikes, outcome labels, slugs,
end dates), never prices, volumes or outcomes, and the table is stored before any pair-leg price is fetched
(``frozen_at``), as T-409 requires. A pair is a linear relation: sum(sign x p_pm) = const + sum(sign x p_kalshi).
  * FOMC: Polymarket fed-decision-in-<month> / fed-interest-rates-<month>-<year> events against Kalshi KXFEDDECISION
    (legacy FEDDECISION) events of the same meeting month. Each outcome label maps to a set of move sizes (atoms
    -100+, -75, -50, -25, 0, +25, +50, +75, +100+ bps; '50+ bps decrease' = {-50, -75, -100+}, 'Cut >25bps' = the same,
    '25+ bps increase' = {+25 .. +100+}); a pair is a connected group of markets whose atom unions agree on both sides
    with no overlap within a side (e.g. PM '50 bps decrease' + '75+ bps decrease' = Kalshi 'Cut >25bps').
  * CPI: Polymarket <month>-inflation-us-monthly / -annual (2025: <month>-inflation-monthly / -annual) and
    core-cpi-mom / core-cpi-yoy-<month> bucket markets against Kalshi KXCPI / KXCPIYOY / KXCPICORE / KXCPICOREYOY
    'above x%' strikes of the same reference month (the release prints one decimal): '>= a' = K(above a - 0.1),
    '<= b' = 1 - K(above b), '= c' = K(above c - 0.1) - K(above c); the 2023 single markets 'US inflation >x% from
    <m1> to <m2> <year>' = K(above x). Events must name the BLS. Reference year = the slug's year, else the endDate year
    (previous year when the month name is not before the endDate month).
  * BTC: Polymarket bitcoin-above-on-<month>-<day>[-<year>]-5pm-et events against the Kalshi KXBTCD 17:00 ET event of
    that date, strike X = Kalshi floor_strike + 0.01. The resolution sources differ (Binance BTCUSDT candle close vs the
    CF Benchmarks BRTI 60-second average) and are flagged in ``basis_note``.
  * 2024 election: presidential-election-winner-2024 = PRES-2024 and presidential-election-popular-vote-winner-2024 =
    POPVOTE-24, by candidate name.
Point in time: available_at = the latest listing time of the legs (Polymarket startDate / createdAt, Kalshi open_time):
the relation exists once both venues list the contracts. Every pair is ``audited: False``: the hand audit of resolution
source, timing and strike wording (``pm_rules`` / ``kalshi_rules`` / ``timing_gap_hours`` are carried for it) is the
harness author's job.

Licences. Polymarket and Kalshi publish no open data licence (their terms grant no redistribution right) and the repo
is public, so every bundle here, the pairs table and both fetch logs included, is local disk only (``in_git=False``,
always); ``GITIGNORE_LINES`` lists the .gitignore lines (bundles are stored as mandel/archive/data/<name>.jsonl.gz) and
``gitignore_line(name)`` maps a bundle to its line. (The legacy polymarket-* / kalshi-* bundles from mandel.data.fetch
are in git; that is the lead's call and is not changed here.)

Resumability. Listing bundles (closed-markets months, Kalshi series, events, pairs) are skipped when stored complete
unless ``refresh``. Per-market products (daily, hourly, volume, candles, trades) skip every market already in the stored
bundle or recorded done in the fetch log (a market with no points is logged so it is not asked again), then store the
bundle whole (stored rows + new rows); a market whose request failed is not logged and is tried again next run. A
bundle cut short by ``max_calls`` (a preview) is never stored. A run can be interrupted anywhere: what was stored stays.

Budget (``fetch_all_pm(store, dry_run=True)``; paces 0.5 s Polymarket, 1.0 s Kalshi; estimates where listings are not stored):
  * Uncapped, the claims' universe would be ~88k resolved Polymarket markets 2023-01 .. 2026-10 (daily history ~12 h,
    trade paging for the 2024+ ones ~57 h and ~300 GB of downloads) and ~52k traded Kalshi markets in these series (hourly
    candles plus trades ~70 h): far beyond 6 hours, so the defaults are a cap.
  * Default (capped) pull, ~50k requests: Polymarket hosts ~5.6 h (closed markets 2,278 calls / 34 min, events 130 / 4 min,
    daily ~12k / 1.7 h, hourly ~11.3k / 1.6 h, trades ~3,850 pages / 1.7 h and ~16 GB downloaded), Kalshi ~5.2 h (listings
    770 / 12 min, daily candles 1,513 / 25 min, hourly candles ~8.9k / 2.5 h, trades ~7.4k pages / 2.1 h); ~690 MB gzip on
    disk. Run the two host groups as two processes (``--sources polymarket`` and ``--sources kalshi``): ~6 h wall time.
  * What the cap trims, and the claims it touches: the daily sample (``per_month`` 200 + every event-family and long-lived
    market, ~11.6k histories: T-12, T-31, T-316, T-359, T-378; T-32's long-lived and T-358's event markets are complete);
    the universe floor (volumeNum >= $10k, lifetime >= 3 days: T-378, T-359 lose one- and two-day markets); trade paging
    (1,500 sampled markets + every pair leg, 5 pages = 50k trades each: T-12, T-31, T-409, T-463); Kalshi samples (150
    hourly / 60-100 trade markets per non-macro series, 4 strikes per KXBTCD event, 15 trade pages: T-408, T-411, T-463,
    T-359's Kalshi arm); BTC pairs (latest 150 events: T-336, T-409). Each knob is a keyword (``options`` in fetch_all_pm).

Every ``fetch_*`` takes ``store`` (an Archive, an ObservationStore whose ``.archive`` is used, or None to store nothing),
``limit`` (bundles), ``dry_run`` (no request: the plan with calls, rows, gzip MB and minutes goes in ``report['_plan']``),
``skip_stored``, ``refresh``, ``max_calls`` (requests per bundle, previews), ``min_interval``, ``report``, ``rows_out``
(receives each bundle's rows) and ``log``. ``fetch_all_pm`` runs them in dependency order. Command line:
``python3 -m mandel.data.pm_history [--dry-run] [--preview DIR] [--sources a,b] [--limit N] [--max-calls N] [--refresh]``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Callable, Iterable, Optional

import httpx

from mandel.data.fetch import CLOB, GAMMA, KALSHI, Throttle, _tokens, now_iso
from mandel.data.options_misc import _archive, _get
from mandel.data.options_misc import _client as _om_client

UTC = timezone.utc
DAY = 86_400
HOUR = 3_600
DATA = "https://data-api.polymarket.com"
_sleep = time.sleep                                   # patched in tests (HTTP backoff sleeps live in options_misc._sleep)


def _now_s() -> int:                                  # patched in tests
    return int(time.time())


def _client() -> httpx.Client:                        # patched in tests
    return _om_client(timeout=120)


# ====================================================================================================== helpers ==

def _ts(s) -> Optional[int]:
    """Unix seconds from an ISO-like string ('2025-04-01 06:50:20+00', '2024-01-16T21:50:24.112Z') or a number."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return int(s)
    try:
        d = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return int((d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp())


def _iso_s(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


def _iso_z(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_iso(s, fallback: str) -> str:
    t = _ts(s)
    return _iso_s(t) if t is not None else fallback


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).date().isoformat()


def _day_ts(day: str) -> int:
    return int(datetime.fromisoformat(day[:10]).replace(tzinfo=UTC).timestamp())


def _month_of(ts: float) -> str:
    return _day(ts)[:7]


def _months(first_day: str, last_day: str) -> list[str]:
    out, d, end = [], date.fromisoformat(first_day[:7] + "-01"), date.fromisoformat(last_day[:10])
    while d <= end:
        out.append(d.isoformat()[:7])
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def _month_end(month: str) -> str:
    d = date.fromisoformat(month + "-01")
    return (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1)).isoformat()


def _month_days(month: str, first_day: str, last_day: str) -> list[str]:
    d, end = date.fromisoformat(max(month + "-01", first_day[:10])), date.fromisoformat(min(_month_end(month), last_day[:10]))
    out = []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _yesterday() -> str:
    return _day(_now_s() - DAY)


def _hash01(key: str) -> float:
    """A uniform number in [0, 1) fixed by ``key``: the selection order of every sample here (reproducible, resumable,
    and independent of volume, price and outcome)."""
    return int(hashlib.sha256(("mandel-pm-history:" + key).encode()).hexdigest()[:13], 16) / 16 ** 13


def _row(source: str, kind: str, key: str, observed_at: str, available_at: str, value: dict) -> dict:
    return {"source": source, "kind": kind, "key": key, "observed_at": observed_at, "available_at": available_at, "value": value}


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _json(r: Optional[httpx.Response], info: dict):
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        info["error"] = "not JSON: " + r.text[:120]
        return None


def _failure(info: dict) -> dict:
    return {k: info[k] for k in ("url", "status", "error", "body", "retry_after", "attempts") if k in info}


def _stored_entry(archive, name: str):
    try:
        return archive.get(name)
    except (KeyError, AttributeError):
        return None


def _stored_complete(archive, name: str) -> bool:
    e = _stored_entry(archive, name) if archive is not None else None
    return bool(e) and "complete" in (e.tags or [])


def _stored_rows(archive, name: str) -> list[dict]:
    if archive is None or _stored_entry(archive, name) is None:
        return []
    try:
        return list(archive.load(name))
    except (KeyError, FileNotFoundError, OSError, ValueError):
        return []


def _put(archive, name: str, rows: list[dict], recipe: str, tags: Iterable[str], schema: str, complete: bool):
    """Store a whole bundle, always local disk only; tag ``complete`` or ``partial`` drives skip_stored."""
    tg = sorted(set(tags) | {"complete" if complete else "partial"})
    return archive.store(name, kind="data", rows=rows, recipe=recipe, tags=tg, schema=schema, in_git=False)


def _setup(store, report: Optional[dict], client: Optional[httpx.Client], min_interval: float):
    archive = _archive(store)
    rep = report if report is not None else {}
    own = client is None
    c = client or _client()
    return archive, rep, c, own, Throttle(min_interval)


def _emit(rows_out: Optional[dict], name: str, rows: list[dict]) -> None:
    if rows_out is not None:
        rows_out[name] = rows


def _merge(stored: list[dict], new: list[dict], field: str) -> list[dict]:
    """The stored rows of every group (value[field]) not re-fetched, plus the new rows."""
    fresh = {str(r["value"].get(field)) for r in new}
    return [r for r in stored if str(r["value"].get(field)) not in fresh] + new


# --------------------------------------------------------------------------------------------- fetch logs --

PM_LOG = "polymarket-fetch-log"
K_LOG = "kalshi-fetch-log"
LOG_SCHEMA = ("kind fetch: key = <product>:<id>; value = {product (daily | hourly | trades | daily-sample | candles-60 | "
              "candles-1440 | trades), id, month / series, reason, points / n, calls, complete, complete_from?, ...}: fetch "
              "metadata (selection reason, sample rates, completeness), not market information; observed_at = available_at "
              "= fetch time")


def _log_load(archive, name: str) -> dict[str, dict]:
    return {r["key"]: r["value"] for r in _stored_rows(archive, name) if r.get("kind") == "fetch"}


def _log_store(archive, name: str, entries: dict[str, dict], source: str) -> None:
    if archive is None:
        return
    rows = [_row(source, "fetch", k, v.get("fetched_at") or now_iso(), v.get("fetched_at") or now_iso(), v) for k, v in sorted(entries.items())]
    archive.store(name, kind="data", rows=rows, recipe=f"mandel.data.pm_history fetch log ({source}): one row per market and product",
                  tags=[source, "fetch-log", "complete"], schema=LOG_SCHEMA, in_git=False)


# ============================================================================================ licences, families ==

LICENCE = {
    "polymarket": ("Polymarket Gamma / CLOB / data-api public endpoints: Polymarket's terms of use grant no redistribution "
                   "right and no open data licence"),
    "kalshi": "Kalshi trade-api v2 public market data: Kalshi's terms grant no redistribution right and no open data licence",
    "both": "derived from Polymarket and Kalshi listings, neither of which grants a redistribution right",
}
LOCAL_ONLY = "The repo is public, so the bundle is local disk only (in_git=False); rebuild it from this recipe."

# (bundle-name pattern, licence key, function, theories, available_at rule)
FAMILIES = [
    ("polymarket-closed-markets-*", "polymarket", "fetch_pm_markets", ["T-12", "T-31", "T-32", "T-316", "T-358", "T-359", "T-378"],
     "fetch time (end-of-life Gamma snapshot); observed_at = closedTime"),
    ("polymarket-price-history-daily-*", "polymarket", "fetch_pm_daily", ["T-12", "T-31", "T-32", "T-316", "T-358", "T-359", "T-378"],
     "t (the price prevailing at t)"),
    ("polymarket-events-btc-above", "polymarket", "fetch_pm_events", ["T-337", "T-336", "T-409"], "fetch time (end-of-life snapshot)"),
    ("polymarket-events-macro", "polymarket", "fetch_pm_events", ["T-336", "T-409", "T-358"], "fetch time (end-of-life snapshot)"),
    ("polymarket-price-history-hourly-*", "polymarket", "fetch_pm_hourly", ["T-337", "T-336", "T-409", "T-408"], "t (the price prevailing at t)"),
    ("polymarket-volume-hourly-*", "polymarket", "fetch_pm_trades", ["T-12", "T-31", "T-409", "T-463"], "hour end (trades public at execution)"),
    ("polymarket-fetch-log", "polymarket", "(every polymarket fetcher)", ["T-12", "T-31", "T-359", "T-409"], "fetch time (fetch metadata)"),
    ("pm-kalshi-pairs", "both", "build_pairs", ["T-336", "T-409"], "latest listing time of the legs"),
    ("kalshi-settled-markets-*", "kalshi", "fetch_kalshi_markets", ["T-358", "T-360", "T-378", "T-316", "T-359", "T-408", "T-411", "T-463", "T-336", "T-409"],
     "fetch time (end-of-life snapshot); observed_at = settlement_ts"),
    ("kalshi-candles-daily-*", "kalshi", "fetch_kalshi_candles", ["T-358", "T-378", "T-316"], "end_period_ts (candle close)"),
    ("kalshi-candles-hourly-*", "kalshi", "fetch_kalshi_candles", ["T-360", "T-336", "T-409", "T-408", "T-411", "T-463", "T-359"],
     "end_period_ts (candle close)"),
    ("kalshi-trades-*", "kalshi", "fetch_kalshi_trades", ["T-411", "T-463"], "created_time (trades public at execution)"),
    ("kalshi-fetch-log", "kalshi", "(every kalshi fetcher)", ["T-411", "T-463"], "fetch time (fetch metadata)"),
]
GITIGNORE_LINES = [f"mandel/archive/data/{p}.jsonl.gz" for p, *_ in FAMILIES]


def gitignore_line(name: str) -> Optional[str]:
    """The .gitignore line covering bundle ``name`` (the most specific family pattern that matches)."""
    hits = [p for p, *_ in FAMILIES if fnmatch(name, p)]
    return f"mandel/archive/data/{max(hits, key=len)}.jsonl.gz" if hits else None


def _family(name: str) -> Optional[tuple]:
    hits = [f for f in FAMILIES if fnmatch(name, f[0])]
    return max(hits, key=lambda f: len(f[0])) if hits else None


def _recipe(core: str, licence: str) -> str:
    return f"{core} Licence: {LICENCE[licence]}. {LOCAL_ONLY}"


# ============================================================================================== estimates ==

PACE = {"gamma": 0.5, "clob": 0.5, "data": 0.5, "kalshi": 1.0}
# seconds per request including transfer (2026-10-15 probes: a 100-row keyset page is ~520 KB; a 10k-trade page ~8.9 MB)
LATENCY = {"gamma": 0.9, "clob": 0.3, "data": 1.6, "kalshi": 0.4}
# gzip bytes per stored row (legacy bundles: closed markets 984, daily prices 14, Kalshi markets 272, candles 53)
ROW_GZ = {"pm_market": 984, "pm_price": 14, "pm_event": 6000, "pm_volume": 70, "pair": 450, "k_market": 272, "k_candle": 53,
          "k_trade": 75, "log": 60}
# Polymarket resolved markets per endDate month with volumeNum >= $10k and a lifetime >= 3 days; anchors interpolated
# linearly (dry-run estimate only): counts measured 2026-10-15 without the lifetime filter (2023-03: 50, 2024-03: 292,
# 2024-09: 1,168, 2025-03: 2,191, 2025-09 ~7,500) times the measured share living >= 3 days (~45%), and day samples
# with the filter (2026-03-10: 73; 2026-09-02: 504).
PM_MONTH_ANCHORS = [("2023-01", 35), ("2023-12", 60), ("2024-03", 200), ("2024-09", 700), ("2025-03", 1300), ("2025-09", 3400),
                    ("2026-03", 3000), ("2026-09", 8000), ("2026-12", 8000)]
PM_PRIORITY_SHARE = 0.06          # share of eligible markets in an event family or living >= 100 days (estimate)
PM_DAILY_POINTS = 25              # mean daily points per market of the sample (estimate)
BTC_ABOVE_EVENTS_EST = 5521       # public-search totalResults for "bitcoin above", closed, 2026-10-15
BTC_ABOVE_MARKETS_EST = 6200      # markets of the daily (noon) and weekly events, hourly-ET variants excluded (estimate)
PAIR_LEG_CALLS_EST = 3500         # 14-day windows over the Polymarket pair legs (FOMC ~120 legs x 8, CPI ~450 x 3, BTC 5pm)
PM_TRADES_PER_MARKET = 4000       # mean taker trades per sampled market (estimate; 516852 had 502, 508190 3,841)
PAIR_LEG_TRADE_PAGES_EST = 2050   # data-api pages over the ~1,200 pair legs: FOMC ~120 x 5 (capped), CPI ~340 x 2, BTC ~750 x 1
TRADE_KB = 0.9                    # KB downloaded per trade (the rows carry wallet profiles; probed)
KALSHI_EST = {"KXFEDDECISION": 145, "KXFED": 450, "KXCPI": 522, "KXCPIYOY": 671, "KXCPICORE": 467, "KXCPICOREYOY": 656,
              "KXPAYROLLS": 396, "KXU3": 300, "KXGDP": 120, "PRES": 8, "POPVOTE": 2}     # settled markets per series (listed 2026-10-15;
                                                                                         # KXFED, KXU3, KXGDP estimated)
KALSHI_EST_OTHER = 4000           # markets per sports / weather series (estimate)
KALSHI_BTC_KEPT = 35              # KXBTCD 17:00 strikes with volume > 0 per event (2025-03: ~15 of 50; 2026-09-28..30: 160 in 3 events)
KALSHI_HOURLY_CANDLES = 300       # mean hourly candles per market (estimate; bars skip quiet hours)
KALSHI_DAILY_CANDLES = 40
KALSHI_TRADE_PAGES = 4            # mean trade pages per sampled market (estimate)


def _item(name: str, host: str, calls: float, rows: float, row_key: str, pace: Optional[float] = None) -> dict:
    sec = max(PACE[host] if pace is None else pace, LATENCY[host])
    return {"bundle": name, "calls": int(math.ceil(calls)), "rows": int(rows), "gz_mb": round(rows * ROW_GZ[row_key] / 1e6, 2),
            "minutes": round(calls * sec / 60, 1)}


def _total(items: list[dict], **extra) -> dict:
    return {"bundles": len(items), "calls": sum(i["calls"] for i in items), "rows": sum(i["rows"] for i in items),
            "gz_mb": round(sum(i["gz_mb"] for i in items), 1), "minutes": round(sum(i["minutes"] for i in items), 1),
            "per_bundle": items, **extra}


def pm_month_estimate(month: str) -> int:
    """Expected resolved markets in ``month`` under the default universe rule (dry-run estimate only)."""
    def k(m):
        return int(m[:4]) * 12 + int(m[5:7]) - 1
    x = k(month)
    pts = [(k(m), n) for m, n in PM_MONTH_ANCHORS]
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return int(round(y0 + (y1 - y0) * (x - x0) / (x1 - x0)))
    return pts[-1][1]


# ================================================================================ 1. Polymarket closed markets ==

PM_FIRST_DAY = "2023-01-01"         # CLOB era; AMM-era markets have no CLOB price history
PM_VOLUME_MIN = 10_000
PM_MIN_LIFE_DAYS = 3
MONTH_COMPLETE_LAG_DAYS = 45        # a month's closed set is final this long after month end (late UMA resolutions)
GAMMA_MAX_PAGES_PER_DAY = 200
PM_MARKET_SCHEMA = "value = raw Gamma market row (as polymarket-closed-markets); observed_at = closedTime (else endDate); available_at = fetch time"


def gamma_day(client: httpx.Client, th: Throttle, day: str, volume_min: float = PM_VOLUME_MIN, min_life_days: float = PM_MIN_LIFE_DAYS,
              retries: int = 4, backoff: float = 1.0, max_calls: Optional[int] = None) -> tuple[Optional[list[dict]], int, dict]:
    """Every closed market whose endDate falls on UTC ``day`` (end_date_max is inclusive: a row is kept only in the window
    holding its endDate), with volumeNum >= ``volume_min`` and startDate <= day - ``min_life_days``. (rows, calls, info);
    rows is None when a page failed or ``max_calls`` cut the paging."""
    d0 = _day_ts(day)
    d1 = d0 + DAY
    params = {"closed": "true", "limit": 100, "end_date_min": _iso_z(d0), "end_date_max": _iso_z(d1), "volume_num_min": volume_min}
    if min_life_days:
        params["start_date_max"] = _iso_z(d0 - min_life_days * DAY)
    out: dict[str, dict] = {}
    cur, calls, info = None, 0, {}
    while calls < GAMMA_MAX_PAGES_PER_DAY:
        if max_calls is not None and calls >= max_calls:
            info["cut"] = "max_calls"
            return None, calls, info
        p = dict(params)
        if cur:
            p["after_cursor"] = cur
        r, info = _get(client, f"{GAMMA}/markets/keyset", th, params=p, retries=retries, backoff=backoff)
        calls += 1
        j = _json(r, info)
        if not isinstance(j, dict):
            return None, calls, info
        ms = j.get("markets") or []
        for m in ms:
            e = _ts(m.get("endDate"))
            if e is not None and d0 <= e < d1 and m.get("id") is not None:
                out[str(m["id"])] = m
        cur = j.get("next_cursor")
        if not cur or not ms:
            return list(out.values()), calls, info
    info["error"] = f"more than {GAMMA_MAX_PAGES_PER_DAY} pages for {day}"
    return None, calls, info


def _pm_market_row(m: dict, fetched_at: str) -> dict:
    return _row("polymarket", "market", str(m.get("id")), _norm_iso(m.get("closedTime") or m.get("endDate"), fetched_at), fetched_at, m)


def fetch_pm_markets(store=None, first: str = PM_FIRST_DAY, last: Optional[str] = None, volume_min: float = PM_VOLUME_MIN,
                     min_life_days: float = PM_MIN_LIFE_DAYS, limit: Optional[int] = None, dry_run: bool = False,
                     skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                     min_interval: float = PACE["gamma"], retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None,
                     rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``polymarket-closed-markets-<M>`` for every endDate month first .. last (default yesterday), one keyset walk per UTC
    day. ``limit`` caps the months fetched; ``max_calls`` the requests per month (a cut month is never stored)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_day = min(last or _yesterday(), _yesterday())
        months = _months(first, last_day)
        todo = [M for M in months if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"polymarket-closed-markets-{M}")]
        rep["_already_stored"] = len(months) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for M in todo:
                n = pm_month_estimate(M)
                days = len(_month_days(M, first, last_day))
                items.append(_item(f"polymarket-closed-markets-{M}", "gamma", days + n / 100, n, "pm_market", min_interval))
            rep["_plan"] = _total(items, note="rows from PM_MONTH_ANCHORS (estimate); calls = one keyset walk per day")
            return rep
        for i, M in enumerate(todo):
            name = f"polymarket-closed-markets-{M}"
            days = _month_days(M, first, last_day)
            got: dict[str, dict] = {}
            calls, failed = 0, None
            for d in days:
                ms, k, info = gamma_day(c, th, d, volume_min, min_life_days, retries, backoff,
                                        None if max_calls is None else max_calls - calls)
                calls += k
                if ms is None:
                    failed = {"day": d, **_failure(info), **({"cut": info["cut"]} if "cut" in info else {})}
                    break
                for m in ms:
                    got[str(m["id"])] = m
            fetched_at = now_iso()
            rows = [_pm_market_row(m, fetched_at) for m in sorted(got.values(), key=lambda m: (_ts(m.get("endDate")) or 0, str(m.get("id"))))]
            complete = (failed is None and days and days[0] == M + "-01" and days[-1] == _month_end(M)
                        and _day_ts(_month_end(M)) + MONTH_COMPLETE_LAG_DAYS * DAY <= _now_s())
            _emit(rows_out, name, rows)
            rep[name] = {"rows": len(rows), "calls": calls, "days": len(days), "complete": bool(complete)}
            if failed is not None:
                rep[name]["_error"] = failed
                rep[name]["stored"] = False
                continue
            if archive is not None:
                e = _put(archive, name, rows,
                         _recipe(f"GET {GAMMA}/markets/keyset?closed=true&limit=100&end_date_min=<D 00:00Z>&end_date_max=<D+1 00:00Z>"
                                 f"&volume_num_min={volume_min:g}&start_date_max=<D - {min_life_days:g} days>&after_cursor=<next_cursor> for "
                                 f"every UTC day D of {M} in {days[0]}..{days[-1]} (a row is kept in the window holding its endDate); "
                                 f"via mandel.data.pm_history.fetch_pm_markets. Universe: endDate {first}.., lifetime startDate->endDate "
                                 f">= {min_life_days:g} days, volumeNum >= ${volume_min:,.0f} (end-of-life volume). Same row schema as "
                                 "polymarket-closed-markets.", "polymarket"),
                         ["polymarket", "markets", "resolved", "history", M], PM_MARKET_SCHEMA, bool(complete))
                rep[name]["stored"] = e.rows
            if log and (i + 1) % 6 == 0:
                log(f"pm markets: {i + 1}/{len(todo)} months")
        return rep
    finally:
        if own:
            c.close()


def stored_pm_months(archive) -> list[str]:
    if archive is None:
        return []
    return sorted({e.name[len("polymarket-closed-markets-"):] for e in archive.entries()
                   if re.fullmatch(r"polymarket-closed-markets-\d{4}-\d{2}", e.name)})


# ========================================================================= 2. Polymarket daily price histories ==

PM_DAILY_PER_MONTH = 200
PM_LONG_LIVED_DAYS = 100
PM_FAMILY_RX = [
    ("fomc", re.compile(r"\bfed-(decision|interest-rates)\b|\b(fed|fomc|federal reserve)\b.{0,40}\b(decision|rates?|cut|cuts|hike|bps|meeting)\b", re.I)),
    ("cpi", re.compile(r"\b(cpi|inflation)\b", re.I)),
    ("payrolls", re.compile(r"\b(payrolls?|jobs report|nonfarm|unemployment rate)\b", re.I)),
    ("gdp", re.compile(r"\bgdp\b", re.I)),
    ("us-election", re.compile(r"\b(presidential election|popular vote|electoral college|senate control|house control|"
                               r"control (of )?the (us )?(senate|house)|midterms?)\b", re.I)),
]
PRICE_SCHEMA = ("value = {market_id, token (the YES / first-outcome CLOB token), p, t (unix)} (as polymarket-price-history-daily); "
                "observed_at = available_at = t: a point is the price prevailing at t")


def pm_family(m: dict) -> Optional[str]:
    """The scheduled-event family of a Gamma market (from question and slugs), or None."""
    ev = (m.get("events") or [{}])[0] or {}
    text = " ".join(str(x or "") for x in (m.get("question"), m.get("slug"), ev.get("slug"), ev.get("title")))
    for fam, rx in PM_FAMILY_RX:
        if rx.search(text):
            return fam
    return None


def _life_days(m: dict) -> Optional[float]:
    s, e = _ts(m.get("startDate") or m.get("createdAt")), _ts(m.get("endDate"))
    return (e - s) / DAY if s is not None and e is not None else None


def select_daily(markets: Iterable[dict], per_month: int = PM_DAILY_PER_MONTH, long_days: float = PM_LONG_LIVED_DAYS) -> tuple[list[tuple[dict, str]], dict]:
    """[(market, reason)] for one month: every binary market of an event family ('family:<name>') or living >= ``long_days``
    ('long-lived'), plus the first ``per_month`` of the others in hash order ('sample'). Never uses volume, price or outcome."""
    pri, rest, elig = [], [], 0
    for m in markets:
        if len(_tokens(m)) != 2:
            continue
        elig += 1
        fam = pm_family(m)
        life = _life_days(m)
        if fam:
            pri.append((m, f"family:{fam}"))
        elif life is not None and life >= long_days:
            pri.append((m, "long-lived"))
        else:
            rest.append(m)
    rest.sort(key=lambda m: (_hash01(f"pm:{m.get('id')}"), str(m.get("id"))))
    picked = [(m, "sample") for m in rest[:max(0, per_month)]]
    stats = {"eligible": elig, "priority": len(pri), "candidates": len(rest), "sampled": len(picked),
             "sample_rate": round(len(picked) / len(rest), 6) if rest else 1.0}
    return pri + picked, stats


def _price_rows(market_id: str, tok: str, hist: list[dict]) -> list[dict]:
    out, seen = [], set()
    for pt in hist:
        t, p = pt.get("t"), _f(pt.get("p"))
        if t is None or p is None or t in seen:
            continue
        seen.add(t)
        t = int(t)
        out.append(_row("polymarket", "price", tok, _iso_s(t), _iso_s(t), {"market_id": market_id, "token": tok, "p": p, "t": t}))
    return out


def _price_sort(r: dict) -> tuple:
    v = r["value"]
    return (str(v["market_id"]), str(v["token"]), int(v["t"]))


def fetch_pm_daily(store=None, months: Optional[Iterable[str]] = None, per_month: int = PM_DAILY_PER_MONTH, limit: Optional[int] = None,
                   dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                   min_interval: float = PACE["clob"], retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None,
                   rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``polymarket-price-history-daily-<M>`` for each stored closed-markets month (or ``months``): the ``select_daily``
    markets, one CLOB call each. Markets already stored or logged are skipped; the month is stored whole."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        ms = sorted(months) if months is not None else stored_pm_months(archive)
        if not ms and dry_run:
            items = []
            for M in _months(PM_FIRST_DAY, _yesterday()):
                n = pm_month_estimate(M)
                k = min(n, per_month) + PM_PRIORITY_SHARE * n
                items.append(_item(f"polymarket-price-history-daily-{M}", "clob", k, k * PM_DAILY_POINTS, "pm_price", min_interval))
            rep["_plan"] = _total(items[:limit] if limit else items, note="closed-markets months not stored yet: estimate")
            return rep
        todo = [M for M in ms if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"polymarket-price-history-daily-{M}")]
        rep["_already_stored"] = len(ms) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        plog = _log_load(archive, PM_LOG) if archive is not None else {}
        items = []
        for M in todo:
            name, src = f"polymarket-price-history-daily-{M}", f"polymarket-closed-markets-{M}"
            mrows = _stored_rows(archive, src)
            if not mrows and _stored_entry(archive, src) is None:
                rep[name] = {"skipped": f"{src} not stored"}
                continue
            sel, stats = select_daily((r["value"] for r in mrows), per_month)
            stored = [] if refresh else _stored_rows(archive, name)
            have = {str(r["value"]["market_id"]) for r in stored}
            if not refresh:
                have |= {v["id"] for k, v in plog.items() if v.get("product") == "daily" and v.get("complete") and v.get("month") == M}
            work = [(m, why) for m, why in sel if str(m.get("id")) not in have]
            if dry_run:
                items.append(_item(name, "clob", len(work), len(work) * PM_DAILY_POINTS, "pm_price", min_interval))
                continue
            new, failed, calls, cut, done = [], [], 0, False, 0
            fetched_at = now_iso()
            for m, why in work:
                if max_calls is not None and calls >= max_calls:
                    cut = True
                    break
                mid, tok = str(m["id"]), _tokens(m)[0]
                r, info = _get(c, f"{CLOB}/prices-history", th, params={"market": tok, "interval": "max", "fidelity": 1440},
                               retries=retries, backoff=backoff)
                calls += 1
                j = _json(r, info)
                if not isinstance(j, dict) or "history" not in j:
                    failed.append({"market_id": mid, **_failure(info)})
                    continue
                pts = _price_rows(mid, tok, j.get("history") or [])
                new += pts
                done += 1
                plog[f"daily:{mid}"] = {"product": "daily", "id": mid, "month": M, "token": tok, "reason": why, "points": len(pts),
                                        "calls": 1, "complete": True, "fetched_at": fetched_at}
            plog[f"daily-sample:{M}"] = {"product": "daily-sample", "id": M, "month": M, "per_month": per_month, **stats,
                                         "complete": True, "fetched_at": fetched_at}
            rows = sorted(_merge(stored, new, "market_id"), key=_price_sort)
            complete = not failed and not cut and _stored_complete(archive, src)
            _emit(rows_out, name, rows)
            rep[name] = {"markets": len(sel), "todo": len(work), "fetched": done, "calls": calls, **({"cut": "max_calls (not stored)"} if cut else {}),
                         "rows": len(rows), "complete": complete, **({"failed": failed[:5], "n_failed": len(failed)} if failed else {})}
            if archive is not None and not cut:
                _put(archive, name, rows,
                     _recipe(f"GET {CLOB}/prices-history?market=<YES token>&interval=max&fidelity=1440 for the markets of "
                             f"polymarket-closed-markets-{M} chosen by mandel.data.pm_history.select_daily(per_month={per_month}): every binary "
                             f"market of an event family (FOMC, CPI, payrolls, GDP, US elections) or living >= {PM_LONG_LIVED_DAYS} days, plus a "
                             f"sha256 hash sample of the rest (rate in polymarket-fetch-log 'daily-sample:{M}'; reasons per market). "
                             "Points are snapshots (the daily point at t equals the hourly point at t): available_at = t.", "polymarket"),
                     ["polymarket", "prices", "daily", "history", M], PRICE_SCHEMA, complete)
                _log_store(archive, PM_LOG, plog, "polymarket")
            if log:
                log(f"pm daily {M}: {rep[name]}")
        if dry_run:
            rep["_plan"] = _total(items, note="from the stored closed-markets months")
        return rep
    finally:
        if own:
            c.close()


# ===================================================================================== 3. Polymarket events ==

BTC_QUERY = "bitcoin above"
BTC_SLUG = re.compile(r"^bitcoin-above-")
BTC_HOURLY_ET = re.compile(r"-(\d{1,2})(am|pm)-et(?:-\d+)?$")
MACRO_QUERIES = ("fed decision", "fed interest rates", "inflation", "cpi")
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_MON = "|".join(MONTHS)
MACRO_SLUG = re.compile(rf"^(fed-decision-in-({_MON})|fed-interest-rates-({_MON})|({_MON})-inflation-(us-)?(monthly|annual)|"
                        rf"core-cpi-(ex-food-and-energy-)?(mom|yoy)-|us-inflation-)")
ELECTION_EVENTS = {"presidential-election-winner-2024": "PRES-2024", "presidential-election-popular-vote-winner-2024": "POPVOTE-24"}
SEARCH_MAX_PAGES = 200
SEARCH_PAGE_SECONDS = 2.0           # a 50-event search page with nested markets is ~2.6 MB (probed)
EVENT_SCHEMA = ("value = raw Gamma event with nested markets (clobTokenIds, outcomePrices, groupItemTitle, startDate, endDate, "
                "closedTime, description); observed_at = endDate; available_at = fetch time (end-of-life snapshot)")


def pm_search(client: httpx.Client, th: Throttle, q: str, status: str = "closed", per_page: int = 50, retries: int = 4,
              backoff: float = 1.0, max_calls: Optional[int] = None) -> tuple[Optional[list[dict]], int, dict]:
    """Every event of Gamma public-search for ``q`` (pages while pagination.hasMore). (events, calls, info)."""
    out: dict[str, dict] = {}
    page, calls, info = 1, 0, {}
    while page <= SEARCH_MAX_PAGES:
        if max_calls is not None and calls >= max_calls:
            return list(out.values()), calls, {**info, "cut": "max_calls"}
        r, info = _get(client, f"{GAMMA}/public-search", th, params={"q": q, "events_status": status, "limit_per_type": per_page, "page": page},
                       retries=retries, backoff=backoff)
        calls += 1
        j = _json(r, info)
        if not isinstance(j, dict):
            return None, calls, info
        evs = j.get("events") or []
        for e in evs:
            if e.get("id") is not None:
                out[str(e["id"])] = e
        if not (j.get("pagination") or {}).get("hasMore") or not evs:
            return list(out.values()), calls, info
        page += 1
    return list(out.values()), calls, info


def pm_event_by_slug(client: httpx.Client, th: Throttle, slug: str, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list[dict]], int, dict]:
    r, info = _get(client, f"{GAMMA}/events", th, params={"slug": slug}, retries=retries, backoff=backoff)
    j = _json(r, info)
    return (j if isinstance(j, list) else None), 1, info


def _event_row(e: dict, fetched_at: str) -> dict:
    return _row("polymarket", "event", str(e.get("id")), _norm_iso(e.get("endDate"), fetched_at), fetched_at, e)


def is_hourly_et(slug: str) -> bool:
    return bool(BTC_HOURLY_ET.search(slug or ""))


def hourly_et_hour(slug: str) -> Optional[int]:
    """The ET hour (0-23) of an hourly-ET event slug ('...-5pm-et' -> 17), else None."""
    mm = BTC_HOURLY_ET.search(slug or "")
    return int(mm.group(1)) % 12 + (12 if mm.group(2) == "pm" else 0) if mm else None


def fetch_pm_events(store=None, sets: Iterable[str] = ("btc_above", "macro"), btc_hours: Iterable[int] = (17,), limit: Optional[int] = None,
                    dry_run: bool = False,
                    skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None, min_interval: float = PACE["gamma"],
                    retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                    client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``polymarket-events-btc-above`` (T-337 and the BTC pairs) and ``polymarket-events-macro`` (US FOMC / CPI templates and
    the two 2024 election events). Stored once (as of the fetch); ``refresh`` fetches them again. Of the hourly-ET BTC
    variants (24 a day since 2026-03, ~15 strikes each, about 90% of the 5,521 search results) only the ``btc_hours`` (ET)
    ones are kept: the 17:00 ET event pairs with Kalshi's daily KXBTCD 17:00 event; the others are not used."""
    sets = list(sets)
    btc_hours = set(btc_hours)
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        names = {"btc_above": "polymarket-events-btc-above", "macro": "polymarket-events-macro"}
        todo = [s for s in sets if refresh or not skip_stored or archive is None or not _stored_complete(archive, names[s])]
        rep["_already_stored"] = len(sets) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for s in todo:
                if s == "btc_above":
                    kept = BTC_ABOVE_EVENTS_EST // 10 + len(btc_hours) * BTC_ABOVE_EVENTS_EST // 24 // 10
                    items.append(_item(names[s], "gamma", BTC_ABOVE_EVENTS_EST / 50 + 1, kept, "pm_event", SEARCH_PAGE_SECONDS))
                else:
                    items.append(_item(names[s], "gamma", 4 * 4 + len(ELECTION_EVENTS), 250, "pm_event", SEARCH_PAGE_SECONDS))
            rep["_plan"] = _total(items)
            return rep
        for s in todo:
            name = names[s]
            fetched_at = now_iso()
            evs: dict[str, dict] = {}
            calls, failed = 0, None
            queries = [BTC_QUERY] if s == "btc_above" else list(MACRO_QUERIES)
            for q in queries:
                got, k, info = pm_search(c, th, q, retries=retries, backoff=backoff, max_calls=None if max_calls is None else max_calls - calls)
                calls += k
                if got is None or "cut" in info:
                    failed = {"query": q, **_failure(info), **({"cut": info["cut"]} if "cut" in info else {})}
                for e in got or []:
                    slug = e.get("slug") or ""
                    if s == "btc_above" and BTC_SLUG.search(slug) and (not is_hourly_et(slug) or hourly_et_hour(slug) in btc_hours):
                        evs[str(e["id"])] = e
                    elif s == "macro" and MACRO_SLUG.search(slug):
                        evs[str(e["id"])] = e
                if failed is not None:
                    break
            if s == "macro" and failed is None:
                for slug in ELECTION_EVENTS:
                    got, k, info = pm_event_by_slug(c, th, slug, retries, backoff)
                    calls += k
                    if got is None:
                        failed = {"slug": slug, **_failure(info)}
                        break
                    for e in got:
                        evs[str(e["id"])] = e
            rows = [_event_row(e, fetched_at) for e in sorted(evs.values(), key=lambda e: (_ts(e.get("endDate")) or 0, str(e.get("id"))))]
            _emit(rows_out, name, rows)
            rep[name] = {"events": len(rows), "calls": calls,
                         **({"hourly_et": sum(is_hourly_et(r["value"].get("slug")) for r in rows)} if s == "btc_above" else {})}
            if failed is not None:
                rep[name].update(_error=failed, stored=False)
                continue
            if archive is not None:
                q = " | ".join(f"q={x}" for x in queries)
                _put(archive, name, rows,
                     _recipe(f"GET {GAMMA}/public-search?{q}&events_status=closed&limit_per_type=50&page=<n> while pagination.hasMore"
                             + (f", slug ^bitcoin-above-, hourly-ET variants only at {sorted(btc_hours)} ET" if s == "btc_above" else
                                f", slug matching {MACRO_SLUG.pattern}; plus GET {GAMMA}/events?slug=<{', '.join(ELECTION_EVENTS)}>")
                             + f" (as of {fetched_at[:10]}); via mandel.data.pm_history.fetch_pm_events.", "polymarket"),
                     ["polymarket", "events", s.replace("_", "-")], EVENT_SCHEMA, True)
        return rep
    finally:
        if own:
            c.close()


# ===================================================================== 4. Polymarket hourly price histories ==

HOURLY_WINDOW_DAYS = 14
TOP_HOURLY_DAYS = 56
LEGACY_DAILY = "polymarket-price-history-daily"
LEGACY_MARKETS = "polymarket-closed-markets"
PAIRS = "pm-kalshi-pairs"


def _pm_end(m: dict, ev: Optional[dict] = None) -> Optional[int]:
    """The market's endDate, or its event's when that is later (some markets carry a stale endDate a month before their
    event's: january-inflation-annual 518808 says 2025-01-12, its event and its close 2025-02-12)."""
    ends = [x for x in (_ts(m.get("endDate")), _ts((ev or {}).get("endDate"))) if x is not None]
    return max(ends) if ends else None


def _pm_window(m: dict, ev: Optional[dict] = None) -> tuple[Optional[int], Optional[int]]:
    """[listing, resolution] of a market: startDate (else createdAt, else the event's), and closedTime capped at endDate + 2 d
    (else endDate + 1 d), endDate being the later of the market's and the event's."""
    s = _ts(m.get("startDate") or m.get("createdAt") or (ev or {}).get("startDate") or (ev or {}).get("createdAt"))
    e_end, e_close = _pm_end(m, ev), _ts(m.get("closedTime"))
    ends = [x for x in (e_close, e_end + 2 * DAY if e_end else None) if x is not None]
    e = min(ends) if ends else None
    if e is None and e_end is not None:
        e = e_end + DAY
    return s, e


def hourly_targets(archive, sets: Iterable[str] = ("btc_above", "pairs", "top"), top_days: int = TOP_HOURLY_DAYS) -> dict[str, dict[str, dict]]:
    """{month: {token: {market_id, token, start, end, sets}}} from the stored events bundle, the pairs table and the legacy
    daily set (read only). Month = the month of the window end."""
    out: dict[str, dict[str, dict]] = defaultdict(dict)

    def add(mid, tok, s, e, tag):
        if not tok or s is None or e is None or e <= s:
            return
        M = _month_of(e)
        t = out[M].get(tok)
        if t is None:
            out[M][tok] = {"market_id": str(mid), "token": tok, "start": int(s), "end": int(e), "sets": [tag]}
        else:
            t["start"], t["end"] = min(t["start"], int(s)), max(t["end"], int(e))
            if tag not in t["sets"]:
                t["sets"].append(tag)
    sets = set(sets)
    if "btc_above" in sets:
        for r in _stored_rows(archive, "polymarket-events-btc-above"):
            ev = r["value"]
            if is_hourly_et(ev.get("slug")):
                continue
            for m in ev.get("markets") or []:
                toks = _tokens(m)
                if len(toks) == 2:
                    s, e = _pm_window(m, ev)
                    add(m.get("id"), toks[0], s, e, "btc_above")
    if "pairs" in sets:
        for r in _stored_rows(archive, PAIRS):
            for leg in (r.get("value") or {}).get("pm") or []:
                add(leg.get("market_id"), leg.get("yes_token"), _ts(leg.get("start")), _ts(leg.get("end")), "pairs")
    if "top" in sets:
        ids = {str(r["value"]["market_id"]) for r in _stored_rows(archive, LEGACY_DAILY)}
        if ids:
            for r in _stored_rows(archive, LEGACY_MARKETS):
                m = r["value"]
                if str(m.get("id")) in ids and len(_tokens(m)) == 2:
                    s, e = _pm_window(m)
                    if e is not None:
                        add(m.get("id"), _tokens(m)[0], max(s or 0, e - top_days * DAY), e, "top")
    return dict(out)


def _hourly_windows(s: int, e: int, days: int = HOURLY_WINDOW_DAYS) -> list[tuple[int, int]]:
    out, a = [], int(s)
    while a < e:
        b = min(a + days * DAY, int(e))
        out.append((a, b))
        a = b
    return out


def pm_hourly_history(client: httpx.Client, th: Throttle, tok: str, s: int, e: int, retries: int = 4, backoff: float = 1.0,
                      depth: int = 0) -> tuple[Optional[list[dict]], int, dict]:
    """fidelity=60 points in [s, e] (one window; a 400 'interval is too long' is split in halves, at most 3 times)."""
    r, info = _get(client, f"{CLOB}/prices-history", th, params={"market": tok, "startTs": s, "endTs": e, "fidelity": 60},
                   retries=retries, backoff=backoff)
    if r is None and info.get("status") == 400 and "too long" in str(info.get("body", "")) and depth < 3 and e - s > HOUR:
        mid = (s + e) // 2
        a, ka, ia = pm_hourly_history(client, th, tok, s, mid, retries, backoff, depth + 1)
        if a is None:
            return None, 1 + ka, ia
        b, kb, ib = pm_hourly_history(client, th, tok, mid, e, retries, backoff, depth + 1)
        return (None if b is None else a + b), 1 + ka + kb, ib
    j = _json(r, info)
    if not isinstance(j, dict) or "history" not in j:
        return None, 1, info
    return j.get("history") or [], 1, info


def fetch_pm_hourly(store=None, sets: Iterable[str] = ("btc_above", "pairs", "top"), top_days: int = TOP_HOURLY_DAYS,
                    limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                    max_calls: Optional[int] = None, min_interval: float = PACE["clob"], retries: int = 4, backoff: float = 1.0,
                    report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                    log: Optional[Callable] = None, **_) -> dict:
    """``polymarket-price-history-hourly-<M>``: fidelity=60 points in 14-day windows for the ``hourly_targets`` tokens.
    Tokens already stored or logged are skipped; each month with new tokens is stored whole."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        targets = hourly_targets(archive, sets, top_days) if archive is not None else {}
        if not targets and dry_run:
            calls = BTC_ABOVE_MARKETS_EST * ("btc_above" in sets) + PAIR_LEG_CALLS_EST * ("pairs" in sets) + 399 * math.ceil(top_days / HOURLY_WINDOW_DAYS) * ("top" in sets)
            rep["_plan"] = _total([_item("polymarket-price-history-hourly-<~22 months>", "clob", calls, calls * 160, "pm_price", min_interval)],
                                  note="events / pairs not stored yet: estimate")
            return rep
        plog = _log_load(archive, PM_LOG) if archive is not None else {}
        months = sorted(targets)
        if limit is not None:
            months = months[:limit]
        items = []
        for M in months:
            name = f"polymarket-price-history-hourly-{M}"
            stored = [] if refresh else _stored_rows(archive, name)
            have = {str(r["value"]["token"]) for r in stored}
            if not refresh:
                have |= {v["token"] for v in plog.values() if v.get("product") == "hourly" and v.get("complete") and v.get("month") == M}
            work = [t for tok, t in sorted(targets[M].items()) if tok not in have]
            if not work:
                rep[name] = {"skipped": "every target stored"}
                continue
            if dry_run:
                k = sum(len(_hourly_windows(t["start"], t["end"])) for t in work)
                items.append(_item(name, "clob", k, sum((t["end"] - t["start"]) / HOUR for t in work), "pm_price", min_interval))
                continue
            new, failed, calls, cut, done = [], [], 0, False, 0
            fetched_at = now_iso()
            for t in work:
                pts, ok, k_all = [], True, 0
                for a, b in _hourly_windows(t["start"], t["end"]):
                    if max_calls is not None and calls >= max_calls:
                        cut = True
                        break
                    h, k, info = pm_hourly_history(c, th, t["token"], a, b, retries, backoff)
                    calls += k
                    k_all += k
                    if h is None:
                        ok = False
                        failed.append({"token": t["token"][:16], "window": [a, b], **_failure(info)})
                        break
                    pts += h
                if cut:
                    break
                if not ok:
                    continue
                rows = _price_rows(t["market_id"], t["token"], pts)
                new += rows
                done += 1
                plog[f"hourly:{t['token']}"] = {"product": "hourly", "id": t["market_id"], "token": t["token"], "month": M, "sets": t["sets"],
                                                "window": [_iso_s(t["start"]), _iso_s(t["end"])], "points": len(rows), "calls": k_all,
                                                "complete": True, "fetched_at": fetched_at}
            rows = sorted(_merge(stored, new, "token"), key=_price_sort)
            _emit(rows_out, name, rows)
            rep[name] = {"targets": len(targets[M]), "todo": len(work), "fetched": done, "calls": calls, "rows": len(rows),
                         **({"cut": "max_calls (not stored)"} if cut else {}), **({"failed": failed[:5], "n_failed": len(failed)} if failed else {})}
            if archive is not None and not cut and new:
                _put(archive, name, rows,
                     _recipe(f"GET {CLOB}/prices-history?market=<YES token>&startTs=<s>&endTs=<e>&fidelity=60 in {HOURLY_WINDOW_DAYS}-day "
                             f"windows (longer spans answer 400 'interval is too long') over [listing, resolution] of the targets of "
                             f"mandel.data.pm_history.hourly_targets(sets={sorted(sets)}): BTC-above daily / weekly markets "
                             "(polymarket-events-btc-above, hourly-ET variants excluded), the Polymarket legs of pm-kalshi-pairs, and the "
                             f"legacy polymarket-price-history-daily markets over their last {top_days} days. available_at = t (snapshot).",
                             "polymarket"),
                     ["polymarket", "prices", "hourly", "history", M], PRICE_SCHEMA, not failed)
            if archive is not None and not cut:
                _log_store(archive, PM_LOG, plog, "polymarket")
            if log:
                log(f"pm hourly {M}: {rep[name]}")
        if dry_run:
            rep["_plan"] = _total(items, note="from the stored events, pairs and legacy bundles")
        return rep
    finally:
        if own:
            c.close()


# ===================================================================== 5. Polymarket trades -> hourly volume ==

PM_TRADES_FIRST_DAY = "2024-01-01"     # data-api has no trades for 2023 markets (triage probe)
PM_TRADES_MARKETS = 1500
PM_TRADE_PAGE = 10_000                 # data-api serves at most 10,000 trades per request (probed)
PM_TRADE_MAX_PAGES = 5
VOLUME_SCHEMA = ("kind volume: value = {market_id, condition_id, t (hour start, unix), n (taker trades), shares (sum of taker size = "
                 "Gamma's volume unit), usd (sum of size x price), o0 / o1 (outcome index 0 / 1): {n_buy, n_sell, buy, sell (taker "
                 "shares bought / sold), buy_usd, sell_usd, last_p}}; observed_at = t, available_at = t + 1 h; only complete hours "
                 "(a market capped by max_pages starts at its first full hour after complete_from, polymarket-fetch-log)")


def pm_trades(client: httpx.Client, th: Throttle, condition_id: str, max_pages: int = PM_TRADE_MAX_PAGES, page: int = PM_TRADE_PAGE,
              retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list[dict]], dict]:
    """Every taker trade of a market, newest first, paging backwards with ``end`` = the oldest timestamp seen (inclusive,
    so the boundary second is de-duplicated). Returns (compact trades or None, meta {calls, complete, complete_from})."""
    seen: set = set()
    out: list[dict] = []
    end, calls, info = None, 0, {}
    while calls < max_pages:
        p = {"market": condition_id, "limit": page, "takerOnly": "true"}
        if end is not None:
            p["end"] = end
        r, info = _get(client, f"{DATA}/trades", th, params=p, retries=retries, backoff=backoff)
        calls += 1
        j = _json(r, info)
        if not isinstance(j, list):
            return None, {"calls": calls, "error": _failure(info) or {"body": str(j)[:200]}}
        new = 0
        for t in j:
            ts = t.get("timestamp")
            if ts is None:
                continue
            k = (t.get("transactionHash"), t.get("asset"), t.get("side"), t.get("size"), t.get("price"), ts, t.get("proxyWallet"))
            if k in seen:
                continue
            seen.add(k)
            new += 1
            out.append({"ts": int(ts), "side": str(t.get("side") or "").upper(), "oi": int(t.get("outcomeIndex") or 0),
                        "size": _f(t.get("size")) or 0.0, "price": _f(t.get("price")) or 0.0})
        if len(j) < page:
            return out, {"calls": calls, "complete": True, "complete_from": None}
        mn = min(int(t["timestamp"]) for t in j if t.get("timestamp") is not None)
        end = mn if new else mn - 1
    oldest = min((t["ts"] for t in out), default=None)
    return out, {"calls": calls, "complete": False, "complete_from": (oldest + 1) if oldest is not None else None}


def hourly_volume(trades: Iterable[dict], market_id: str, condition_id: str, from_ts: Optional[int] = None) -> list[dict]:
    """Hourly taker-volume rows; with ``from_ts`` only hours starting at or after it (complete hours of a capped market)."""
    b: dict[int, dict] = {}
    for t in trades:
        h = t["ts"] // HOUR * HOUR
        if from_ts is not None and h < from_ts:
            continue
        v = b.get(h)
        if v is None:
            v = b[h] = {"market_id": market_id, "condition_id": condition_id, "t": h, "n": 0, "shares": 0.0, "usd": 0.0,
                        "o0": {"n_buy": 0, "n_sell": 0, "buy": 0.0, "sell": 0.0, "buy_usd": 0.0, "sell_usd": 0.0, "last_p": None, "_lt": -1},
                        "o1": {"n_buy": 0, "n_sell": 0, "buy": 0.0, "sell": 0.0, "buy_usd": 0.0, "sell_usd": 0.0, "last_p": None, "_lt": -1}}
        o = v["o1" if t["oi"] == 1 else "o0"]
        usd = t["size"] * t["price"]
        v["n"] += 1
        v["shares"] += t["size"]
        v["usd"] += usd
        side = "buy" if t["side"] == "BUY" else "sell"
        o[f"n_{side}"] += 1
        o[side] += t["size"]
        o[f"{side}_usd"] += usd
        if t["ts"] >= o["_lt"]:
            o["_lt"], o["last_p"] = t["ts"], t["price"]
    rows = []
    for h in sorted(b):
        v = b[h]
        for k in ("o0", "o1"):
            v[k].pop("_lt", None)
            for f in ("buy", "sell", "buy_usd", "sell_usd"):
                v[k][f] = round(v[k][f], 6)
        v["shares"], v["usd"] = round(v["shares"], 6), round(v["usd"], 6)
        rows.append(_row("polymarket", "volume", f"{market_id}:{h}", _iso_s(h), _iso_s(h + HOUR), v))
    return rows


def trade_targets(archive, n_markets: int = PM_TRADES_MARKETS, first_day: str = PM_TRADES_FIRST_DAY,
                  per_month: int = PM_DAILY_PER_MONTH) -> dict[str, dict[str, dict]]:
    """{month: {market_id: {market_id, condition_id, volumeNum, reason}}}: every Polymarket pair leg ending on or after
    ``first_day`` plus, per stored closed-markets month from ``first_day``, the first ceil(n_markets / months) markets of the
    daily ``sample`` in hash order (so each has its daily history too)."""
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    f0 = _day_ts(first_day)
    for r in _stored_rows(archive, PAIRS):
        for leg in (r.get("value") or {}).get("pm") or []:
            e = _ts(leg.get("end"))
            if leg.get("condition_id") and e is not None and e >= f0:
                out[_month_of(e)][str(leg["market_id"])] = {"market_id": str(leg["market_id"]), "condition_id": leg["condition_id"],
                                                            "volumeNum": leg.get("volumeNum"), "reason": "pair"}
    months = [M for M in stored_pm_months(archive) if M >= first_day[:7]]
    quota = math.ceil(n_markets / len(months)) if months else 0
    for M in months:
        sel, _ = select_daily((r["value"] for r in _stored_rows(archive, f"polymarket-closed-markets-{M}")), per_month)
        for m, why in [x for x in sel if x[1] == "sample"][:quota]:
            if m.get("conditionId") and str(m["id"]) not in out[M]:
                out[M][str(m["id"])] = {"market_id": str(m["id"]), "condition_id": m["conditionId"], "volumeNum": _f(m.get("volumeNum")),
                                        "reason": "sample"}
    return dict(out)


def _volume_sort(r: dict) -> tuple:
    return (str(r["value"]["market_id"]), int(r["value"]["t"]))


def fetch_pm_trades(store=None, n_markets: int = PM_TRADES_MARKETS, max_pages: int = PM_TRADE_MAX_PAGES, first_day: str = PM_TRADES_FIRST_DAY,
                    per_month: int = PM_DAILY_PER_MONTH, limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                    max_calls: Optional[int] = None, min_interval: float = PACE["data"], retries: int = 4, backoff: float = 1.0,
                    report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                    log: Optional[Callable] = None, **_) -> dict:
    """``polymarket-volume-hourly-<M>``: taker trades of the ``trade_targets`` markets (data-api, end-paged) aggregated to
    hours. Markets already stored or logged are skipped; each month with new markets is stored whole."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        targets = trade_targets(archive, n_markets, first_day, per_month) if archive is not None else {}
        if not targets and dry_run:
            pages = n_markets * 1.2 + PAIR_LEG_TRADE_PAGES_EST
            gb = round((n_markets * PM_TRADES_PER_MARKET + PAIR_LEG_TRADE_PAGES_EST * 6000) * TRADE_KB / 1e6, 1)
            rep["_plan"] = _total([_item("polymarket-volume-hourly-<~34 months>", "data", pages, (n_markets + 1200) * 300, "pm_volume", min_interval)],
                                  note=f"{n_markets} sampled markets + ~1,200 pair legs (estimate); ~{gb} GB downloaded "
                                       f"(~{TRADE_KB} KB per trade, max_pages={max_pages} x {PM_TRADE_PAGE} trades per market)", download_gb=gb)
            return rep
        plog = _log_load(archive, PM_LOG) if archive is not None else {}
        months = sorted(targets)
        if limit is not None:
            months = months[:limit]
        items = []
        for M in months:
            name = f"polymarket-volume-hourly-{M}"
            stored = [] if refresh else _stored_rows(archive, name)
            have = {str(r["value"]["market_id"]) for r in stored}
            if not refresh:
                have |= {v["id"] for v in plog.values() if v.get("product") == "trades" and v.get("month") == M and "complete" in v}
            work = [t for mid, t in sorted(targets[M].items()) if mid not in have]
            if not work:
                rep[name] = {"skipped": "every target stored"}
                continue
            if dry_run:
                items.append(_item(name, "data", len(work) * min(max_pages, max(1, math.ceil(PM_TRADES_PER_MARKET / PM_TRADE_PAGE))),
                                   len(work) * 300, "pm_volume", min_interval))
                continue
            new, failed, calls, cut, done = [], [], 0, False, 0
            fetched_at = now_iso()
            for t in work:
                if max_calls is not None and calls + max_pages > max_calls:
                    cut = True
                    break
                trades, meta = pm_trades(c, th, t["condition_id"], max_pages=max_pages, retries=retries, backoff=backoff)
                calls += meta["calls"]
                if trades is None:
                    failed.append({"market_id": t["market_id"], **meta})
                    continue
                cf = meta.get("complete_from")
                from_h = (-(-cf // HOUR)) * HOUR if cf is not None else None      # the first full hour at or after complete_from
                rows = hourly_volume(trades, t["market_id"], t["condition_id"], from_h)
                new += rows
                done += 1
                shares = round(sum(x["size"] for x in trades), 6)
                vn = t.get("volumeNum")
                plog[f"trades:{t['market_id']}"] = {
                    "product": "trades", "id": t["market_id"], "condition_id": t["condition_id"], "month": M, "reason": t["reason"],
                    "n_trades": len(trades), "shares": shares, "volumeNum": vn,
                    "shares_over_volumeNum": round(shares / vn, 6) if vn else None,
                    "first_ts": min((x["ts"] for x in trades), default=None), "last_ts": max((x["ts"] for x in trades), default=None),
                    "calls": meta["calls"], "complete": bool(meta.get("complete")), "complete_from": cf,
                    "complete_from_hour": from_h, "fetched_at": fetched_at}
            rows = sorted(_merge(stored, new, "market_id"), key=_volume_sort)
            _emit(rows_out, name, rows)
            rep[name] = {"targets": len(targets[M]), "todo": len(work), "fetched": done, "calls": calls, "rows": len(rows),
                         **({"cut": "max_calls (not stored)"} if cut else {}), **({"failed": failed[:5], "n_failed": len(failed)} if failed else {})}
            if archive is not None and not cut and new:
                _put(archive, name, rows,
                     _recipe(f"GET {DATA}/trades?market=<conditionId>&limit={PM_TRADE_PAGE}&takerOnly=true&end=<oldest timestamp seen> "
                             f"(newest first, at most {max_pages} pages per market) for mandel.data.pm_history.trade_targets(n_markets="
                             f"{n_markets}, first_day={first_day}): the Polymarket legs of pm-kalshi-pairs plus a hash sample of the daily "
                             "'sample' markets; aggregated to hours. Taker-only rows: one per taker order, their sizes sum to Gamma's "
                             "volumeNum (probed), and they carry the aggressor side.", "polymarket"),
                     ["polymarket", "trades", "volume", "hourly", M], VOLUME_SCHEMA, not failed)
            if archive is not None and not cut:
                _log_store(archive, PM_LOG, plog, "polymarket")
            if log:
                log(f"pm trades {M}: {rep[name]}")
        if dry_run:
            rep["_plan"] = _total(items, note="from the stored pairs and closed-markets months")
        return rep
    finally:
        if own:
            c.close()


# =================================================================================================== Kalshi ==

KALSHI_CUTOFF_FALLBACK = {"market_settled_ts": "2026-08-16T00:00:00Z", "trades_created_ts": "2026-08-16T00:00:00Z"}
MACRO_SERIES = ("KXFEDDECISION", "KXFED", "KXCPI", "KXCPIYOY", "KXCPICORE", "KXCPICOREYOY", "KXPAYROLLS", "KXU3", "KXGDP")
DAILY_SERIES = ("KXCPI", "KXFED", "KXFEDDECISION", "KXPAYROLLS")
ELECTION_SERIES = ("PRES", "POPVOTE")
WEATHER_SERIES = ("KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS")
SPORTS_SERIES = ("KXNFLGAME", "KXNBAGAME", "KXMLBGAME", "KXNHLGAME", "KXATPMATCH", "KXWTAMATCH", "KXNCAAFGAME", "KXEPLGAME")
KALSHI_SERIES = MACRO_SERIES + ELECTION_SERIES + WEATHER_SERIES + SPORTS_SERIES
CRYPTO_DAILY = {"KXBTCD": 17}           # the daily 5 pm ET event KXBTCD-<YY><MON><DD>17
CRYPTO_FIRST_DAY = "2025-01-01"
KALSHI_HOURLY_CAP = 150                 # hash-sampled markets per sports / weather series for hourly candles
KALSHI_MIN_VOLUME = 1000                # contracts, for the sampled series and every trade sample
KALSHI_BTC_HOURLY_PER_EVENT = 4         # most traded strikes per KXBTCD 17:00 event
KALSHI_TRADES_CAP = {"macro": 60, "other": 100, "crypto_month": 10}
KALSHI_MAX_PAGES = 15
CANDLES_PER_CALL = 4800                 # the API refuses more than 5,000 candles per request (probed)
KALSHI_RETRIES, KALSHI_BACKOFF = 6, 1.5
MON3 = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
K_MARKET_SCHEMA = "value = raw Kalshi market row (as kalshi-settled-markets); observed_at = settlement_ts (else close_time); available_at = fetch time"
K_CANDLE_SCHEMA = ("value = {ticker, period (minutes), candle (raw: end_period_ts, yes_bid / yes_ask OHLC, price OHLC + mean + previous, "
                   "volume, open_interest; the live route names them close_dollars / volume_fp / open_interest_fp: read with "
                   "mandel.data.pm_history.candle_fields)} (as kalshi-candles); observed_at = available_at = end_period_ts (a candle is "
                   "known once its period closed); hourly bars skip hours without activity")
K_TRADE_SCHEMA = ("value = raw Kalshi trade {trade_id, ticker, created_time, yes_price_dollars, no_price_dollars, count_fp, taker_side, "
                  "taker_outcome_side, taker_book_side, is_block_trade}; observed_at = available_at = created_time")


def _kvol(m: dict) -> float:
    return _f(m.get("volume_fp")) or _f(m.get("volume")) or 0.0


def candle_fields(candle: dict) -> dict:
    """Normalised view of a raw Kalshi candle. The historical route names fields close / volume / open_interest, the live
    route close_dollars / volume_fp / open_interest_fp (both seen 2026-10-15); this reads either. Returns {end_period_ts,
    yes_bid_{open,high,low,close}, yes_ask_{...}, price_{open,high,low,close,mean}, volume, open_interest} as floats or None."""
    def g(d, k):
        d = d or {}
        return _f(d.get(k)) if d.get(k) is not None else _f(d.get(k + "_dollars"))
    out = {"end_period_ts": candle.get("end_period_ts")}
    for side in ("yes_bid", "yes_ask"):
        for k in ("open", "high", "low", "close"):
            out[f"{side}_{k}"] = g(candle.get(side), k)
    for k in ("open", "high", "low", "close", "mean"):
        out[f"price_{k}"] = g(candle.get("price"), k)
    out["volume"] = _f(candle.get("volume")) if candle.get("volume") is not None else _f(candle.get("volume_fp"))
    out["open_interest"] = _f(candle.get("open_interest")) if candle.get("open_interest") is not None else _f(candle.get("open_interest_fp"))
    return out


def _series_kind(s: str) -> str:
    base = s.split("-")[0]
    if base in MACRO_SERIES:
        return "macro"
    if base in ELECTION_SERIES:
        return "election"
    if base in CRYPTO_DAILY:
        return "crypto"
    return "other"


def kalshi_cutoff(client: httpx.Client, th: Throttle, retries: int = KALSHI_RETRIES, backoff: float = KALSHI_BACKOFF) -> dict:
    r, info = _get(client, f"{KALSHI}/historical/cutoff", th, retries=retries, backoff=backoff)
    j = _json(r, info)
    if isinstance(j, dict) and j.get("market_settled_ts"):
        return {"market_settled_ts": j["market_settled_ts"], "trades_created_ts": j.get("trades_created_ts") or j["market_settled_ts"], "source": "api"}
    return {**KALSHI_CUTOFF_FALLBACK, "source": "fallback"}


def kalshi_pages(client: httpx.Client, th: Throttle, path: str, params: dict, key: str, max_pages: int = 500, retries: int = KALSHI_RETRIES,
                 backoff: float = KALSHI_BACKOFF) -> tuple[Optional[list[dict]], dict]:
    """Every item under ``key`` of a cursor-paged Kalshi list. (items or None, meta {calls, complete})."""
    out, cursor, calls, info = [], None, 0, {}
    while calls < max_pages:
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        r, info = _get(client, f"{KALSHI}{path}", th, params=p, retries=retries, backoff=backoff)
        calls += 1
        j = _json(r, info)
        if not isinstance(j, dict) or key not in j:
            return None, {"calls": calls, "error": _failure(info) or {"body": str(j)[:200]}}
        out += j.get(key) or []
        cursor = j.get("cursor")
        if not cursor or not j.get(key):
            return out, {"calls": calls, "complete": True}
    return out, {"calls": calls, "complete": False}


def _k_market_row(m: dict, fetched_at: str) -> dict:
    return _row("kalshi", "market", m.get("ticker", ""), _norm_iso(m.get("settlement_ts") or m.get("close_time"), fetched_at), fetched_at, m)


def _k_sort(r: dict) -> tuple:
    v = r["value"]
    return (_ts(v.get("close_time")) or 0, str(v.get("ticker")))


def kxbtcd_event(day: str, hour: int, series: str = "KXBTCD") -> str:
    d = date.fromisoformat(day)
    return f"{series}-{d.year % 100:02d}{MON3[d.month - 1]}{d.day:02d}{hour:02d}"


def fetch_kalshi_markets(store=None, series: Iterable[str] = KALSHI_SERIES, crypto: Optional[dict] = None, crypto_first: str = CRYPTO_FIRST_DAY,
                         last: Optional[str] = None, limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True,
                         refresh: bool = False, max_calls: Optional[int] = None, min_interval: float = PACE["kalshi"],
                         retries: int = KALSHI_RETRIES, backoff: float = KALSHI_BACKOFF, report: Optional[dict] = None,
                         rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``kalshi-settled-markets-<S>`` per series (historical + live settled lists) and ``kalshi-settled-markets-<S>-<M>`` per
    month for the daily crypto events (``crypto`` {series: ET hour}, default KXBTCD 17:00; traded strikes only)."""
    crypto = CRYPTO_DAILY if crypto is None else crypto
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_day = min(last or _yesterday(), _yesterday())
        jobs = [("series", s, f"kalshi-settled-markets-{s}", None) for s in series if not s.startswith("KXMVE")]
        for s, hh in crypto.items():
            for M in _months(crypto_first, last_day):
                jobs.append(("crypto", s, f"kalshi-settled-markets-{s}-{M}", (M, hh)))
        todo = [j for j in jobs if refresh or not skip_stored or archive is None or not _stored_complete(archive, j[2])]
        rep["_already_stored"] = len(jobs) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for kind, s, name, extra in todo:
                if kind == "series":
                    n = KALSHI_EST.get(s, KALSHI_EST_OTHER)
                    items.append(_item(name, "kalshi", 2 * max(1, math.ceil(n / 1000)), n, "k_market", min_interval))
                else:
                    days = len(_month_days(extra[0], crypto_first, last_day))
                    items.append(_item(name, "kalshi", days, days * KALSHI_BTC_KEPT, "k_market", min_interval))
            rep["_plan"] = _total(items)
            return rep
        cutoff = kalshi_cutoff(c, th, retries, backoff)
        cut_s = _ts(cutoff["market_settled_ts"]) or 0
        rep["_cutoff"] = cutoff
        for i, (kind, s, name, extra) in enumerate(todo):
            fetched_at = now_iso()
            got: dict[str, dict] = {}
            calls, failed = 0, None
            if kind == "series":
                for path, params in (("/historical/markets", {"series_ticker": s, "limit": 1000}),
                                     ("/markets", {"series_ticker": s, "status": "settled", "limit": 1000})):
                    left = None if max_calls is None else max_calls - calls
                    if left is not None and left <= 0:
                        failed = {"cut": "max_calls"}
                        break
                    ms, meta = kalshi_pages(c, th, path, params, "markets", max_pages=500 if left is None else left, retries=retries, backoff=backoff)
                    calls += meta["calls"]
                    if ms is None or not meta.get("complete"):
                        failed = {"path": path, **meta}
                        break
                    for m in ms:
                        if m.get("ticker") and not str(m.get("ticker")).startswith("KXMVE"):
                            got[m["ticker"]] = m
                complete = failed is None
            else:
                M, hh = extra
                days = _month_days(M, crypto_first, last_day)
                for d in days:
                    if max_calls is not None and calls >= max_calls:
                        failed = {"cut": "max_calls"}
                        break
                    ev = kxbtcd_event(d, hh, s)
                    routes = ["/historical/markets", "/markets"] if _day_ts(d) + DAY < cut_s else ["/markets", "/historical/markets"]
                    ms = None
                    for path in routes:
                        ms, meta = kalshi_pages(c, th, path, {"event_ticker": ev, "limit": 1000}, "markets", max_pages=5, retries=retries, backoff=backoff)
                        calls += meta["calls"]
                        if ms is None:
                            failed = {"event": ev, **meta}
                            break
                        if ms:
                            break
                    if failed is not None:
                        break
                    for m in ms or []:
                        if m.get("ticker") and _kvol(m) > 0:
                            got[m["ticker"]] = m
                complete = (failed is None and days and days[0] == M + "-01" and days[-1] == _month_end(M)
                            and _day_ts(_month_end(M)) + 8 * DAY <= _now_s())
            rows = sorted((_k_market_row(m, fetched_at) for m in got.values()), key=_k_sort)
            _emit(rows_out, name, rows)
            rep[name] = {"markets": len(rows), "calls": calls, "complete": bool(complete)}
            if failed is not None:
                rep[name].update(_error=failed, stored=False)
                continue
            if archive is not None:
                if kind == "series":
                    core = (f"GET {KALSHI}/historical/markets?series_ticker={s}&limit=1000&cursor=<c> plus GET {KALSHI}/markets?series_ticker={s}"
                            f"&status=settled&limit=1000&cursor=<c>, de-duplicated by ticker (as of {fetched_at[:10]}); legacy pre-KX tickers "
                            "of the series included, KXMVE combos excluded")
                else:
                    core = (f"GET {KALSHI}/historical/markets?event_ticker={s}-<YY><MON><DD>{extra[1]:02d} (or /markets?event_ticker= after the "
                            f"cutoff) for every day of {extra[0]} from {crypto_first}: the daily {extra[1]}:00 ET event; strikes with volume_fp > 0 only")
                _put(archive, name, rows, _recipe(core + "; via mandel.data.pm_history.fetch_kalshi_markets. Same row schema as kalshi-settled-markets.",
                                                  "kalshi"),
                     ["kalshi", "markets", "settled", "history", s] + ([extra[0]] if extra else []), K_MARKET_SCHEMA, bool(complete))
                rep[name]["stored"] = len(rows)
            if log and (i + 1) % 10 == 0:
                log(f"kalshi markets: {i + 1}/{len(todo)} bundles")
        return rep
    finally:
        if own:
            c.close()


def stored_kalshi_listings(archive) -> list[str]:
    """Names of the stored kalshi-settled-markets-<S>[-<M>] bundles (the legacy kalshi-settled-markets excluded)."""
    if archive is None:
        return []
    return sorted(e.name for e in archive.entries() if e.name.startswith("kalshi-settled-markets-"))


def _listing_series(name: str) -> tuple[str, Optional[str]]:
    rest = name[len("kalshi-settled-markets-"):]
    m = re.fullmatch(r"(.+)-(\d{4}-\d{2})", rest)
    return (m.group(1), m.group(2)) if m else (rest, None)


def kalshi_select(markets: list[dict], series: str, period: int) -> list[dict]:
    """Markets that get candles of ``period`` minutes: daily, every traded market of DAILY_SERIES; hourly, every traded macro /
    election market, the KALSHI_BTC_HOURLY_PER_EVENT most traded strikes of each crypto event, and for the other series the
    first KALSHI_HOURLY_CAP markets with volume >= KALSHI_MIN_VOLUME in hash order."""
    kind = _series_kind(series)
    traded = [m for m in markets if _kvol(m) > 0 and m.get("open_time") and m.get("close_time")]
    if period == 1440:
        return traded if series in DAILY_SERIES else []
    if kind in ("macro", "election"):
        return traded
    if kind == "crypto":
        by_ev = defaultdict(list)
        for m in traded:
            by_ev[m.get("event_ticker")].append(m)
        out = []
        for ev in sorted(by_ev):
            out += sorted(by_ev[ev], key=lambda m: (-_kvol(m), m["ticker"]))[:KALSHI_BTC_HOURLY_PER_EVENT]
        return out
    pool = [m for m in traded if _kvol(m) >= KALSHI_MIN_VOLUME]
    return sorted(pool, key=lambda m: (_hash01("k:" + m["ticker"]), m["ticker"]))[:KALSHI_HOURLY_CAP]


def kalshi_trade_select(markets: list[dict], series: str) -> list[dict]:
    """Markets that get trades: the hourly selection with volume >= KALSHI_MIN_VOLUME (elections: all), in hash order, capped."""
    kind = _series_kind(series)
    sel = kalshi_select(markets, series, 60)
    if kind == "election":
        return sel
    pool = sorted((m for m in sel if _kvol(m) >= KALSHI_MIN_VOLUME), key=lambda m: (_hash01("k:" + m["ticker"]), m["ticker"]))
    cap = KALSHI_TRADES_CAP["macro" if kind == "macro" else "crypto_month" if kind == "crypto" else "other"]
    return pool[:cap]


def _k_routes(m: dict, cut_s: int) -> list[str]:
    settled = _ts(m.get("settlement_ts") or m.get("close_time")) or 0
    return ["hist", "live"] if settled < cut_s else ["live", "hist"]


def kalshi_candles(client: httpx.Client, th: Throttle, m: dict, series: str, period: int, cut_s: int, retries: int = KALSHI_RETRIES,
                   backoff: float = KALSHI_BACKOFF) -> tuple[Optional[list[dict]], dict]:
    """Candles over [open_time, close_time + one period] in windows of CANDLES_PER_CALL periods, from the route the cutoff
    points to (the other one when that is empty). (candles or None, meta {calls, route})."""
    t = m["ticker"]
    s, e = _ts(m["open_time"]), _ts(m["close_time"]) + period * 60
    s -= s % (period * 60)
    span = CANDLES_PER_CALL * period * 60
    calls = 0
    last_info: dict = {}
    for route in _k_routes(m, cut_s):
        path = f"/historical/markets/{t}/candlesticks" if route == "hist" else f"/series/{series.split('-')[0]}/markets/{t}/candlesticks"
        got: dict[int, dict] = {}
        ok = True
        a = s
        while a < e:
            b = min(a + span, e)
            r, info = _get(client, f"{KALSHI}{path}", th, params={"start_ts": a, "end_ts": b, "period_interval": period}, retries=retries, backoff=backoff)
            calls += 1
            j = _json(r, info)
            if not isinstance(j, dict) or "candlesticks" not in j:
                ok, last_info = False, info
                break
            for k in j.get("candlesticks") or []:
                if k.get("end_period_ts") is not None:
                    got[int(k["end_period_ts"])] = k
            a = b
        if ok and got:
            return [got[k] for k in sorted(got)], {"calls": calls, "route": route}
        if ok:
            last_info = {"empty": route}
    if last_info.get("empty") or last_info.get("status") == 404:
        return [], {"calls": calls, "route": None}
    return None, {"calls": calls, "error": _failure(last_info)}


def fetch_kalshi_candles(store=None, period: int = 60, series: Optional[Iterable[str]] = None, limit: Optional[int] = None,
                         dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                         min_interval: float = PACE["kalshi"], retries: int = KALSHI_RETRIES, backoff: float = KALSHI_BACKOFF,
                         report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                         log: Optional[Callable] = None, **_) -> dict:
    """``kalshi-candles-hourly-<S>`` (period 60) or ``kalshi-candles-daily-<S>`` (period 1440) for the ``kalshi_select``
    markets of every stored kalshi-settled-markets-<S>[-<M>] listing (or ``series``). Markets already stored or logged are
    skipped; each bundle with new markets is stored whole."""
    if period not in (60, 1440):
        raise ValueError("period must be 60 or 1440")
    tag = "hourly" if period == 60 else "daily"
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        listings = stored_kalshi_listings(archive)
        if series is not None:
            want = set(series)
            listings = [n for n in listings if _listing_series(n)[0] in want]
        if not listings and dry_run:
            items = []
            for s in (DAILY_SERIES if period == 1440 else KALSHI_SERIES):
                n = KALSHI_EST.get(s, KALSHI_EST_OTHER)
                k = n if _series_kind(s) in ("macro", "election") else KALSHI_HOURLY_CAP
                if period == 1440 and s not in DAILY_SERIES:
                    continue
                items.append(_item(f"kalshi-candles-{tag}-{s}", "kalshi", k * (1.2 if period == 60 and _series_kind(s) == "macro" else 1),
                                   k * (KALSHI_HOURLY_CANDLES if period == 60 else KALSHI_DAILY_CANDLES), "k_candle", min_interval))
            if period == 60:
                days = (_day_ts(_yesterday()) - _day_ts(CRYPTO_FIRST_DAY)) // DAY + 1
                k = days * KALSHI_BTC_HOURLY_PER_EVENT
                items.append(_item("kalshi-candles-hourly-KXBTCD-<months>", "kalshi", k, k * 60, "k_candle", min_interval))
            rep["_plan"] = _total(items, note="listings not stored yet: estimate")
            return rep
        if limit is not None:
            listings = listings[:limit]
        klog = _log_load(archive, K_LOG)
        cutoff = kalshi_cutoff(c, th, retries, backoff) if not dry_run else KALSHI_CUTOFF_FALLBACK
        cut_s = _ts(cutoff["market_settled_ts"]) or 0
        items = []
        for src in listings:
            s, M = _listing_series(src)
            name = f"kalshi-candles-{tag}-{s}" + (f"-{M}" if M else "")
            markets = [r["value"] for r in _stored_rows(archive, src)]
            sel = kalshi_select(markets, s, period)
            if not sel:
                continue
            stored = [] if refresh else _stored_rows(archive, name)
            have = {str(r["value"]["ticker"]) for r in stored}
            if not refresh:
                have |= {v["id"] for v in klog.values() if v.get("product") == f"candles-{period}" and v.get("complete")}
            work = [m for m in sel if m["ticker"] not in have]
            if not work:
                rep[name] = {"skipped": "every selected market stored"}
                continue
            if dry_run:
                k = sum(max(1, math.ceil(((_ts(m["close_time"]) or 0) - (_ts(m["open_time"]) or 0)) / (CANDLES_PER_CALL * period * 60))) for m in work)
                items.append(_item(name, "kalshi", k, len(work) * (KALSHI_HOURLY_CANDLES if period == 60 else KALSHI_DAILY_CANDLES), "k_candle", min_interval))
                continue
            new, failed, calls, cut, done = [], [], 0, False, 0
            fetched_at = now_iso()
            for m in work:
                if max_calls is not None and calls >= max_calls:
                    cut = True
                    break
                cs, meta = kalshi_candles(c, th, m, s, period, cut_s, retries, backoff)
                calls += meta["calls"]
                if cs is None:
                    failed.append({"ticker": m["ticker"], **meta})
                    continue
                for k in cs:
                    ts = int(k["end_period_ts"])
                    new.append(_row("kalshi", "candle", m["ticker"], _iso_s(ts), _iso_s(ts), {"ticker": m["ticker"], "period": period, "candle": k}))
                done += 1
                klog[f"candles-{period}:{m['ticker']}"] = {"product": f"candles-{period}", "id": m["ticker"], "series": s, "month": M,
                                                         "candles": len(cs), "route": meta.get("route"), "calls": meta["calls"],
                                                         "complete": True, "fetched_at": fetched_at}
            rows = sorted(_merge(stored, new, "ticker"), key=lambda r: (r["value"]["ticker"], int(r["value"]["candle"]["end_period_ts"])))
            _emit(rows_out, name, rows)
            rep[name] = {"selected": len(sel), "todo": len(work), "fetched": done, "calls": calls, "rows": len(rows),
                         **({"cut": "max_calls (not stored)"} if cut else {}), **({"failed": failed[:5], "n_failed": len(failed)} if failed else {})}
            if archive is not None and not cut:
                _put(archive, name, rows,
                     _recipe(f"GET {KALSHI}/historical/markets/<T>/candlesticks?start_ts&end_ts&period_interval={period} for markets settled "
                             f"before the historical cutoff ({cutoff['market_settled_ts']}), else GET {KALSHI}/series/{s}/markets/<T>/candlesticks "
                             f"(the other route when the first is empty), windows of {CANDLES_PER_CALL} periods over [open_time, close_time], for "
                             f"the markets of {src} chosen by mandel.data.pm_history.kalshi_select(period={period}). Same row schema as kalshi-candles.",
                             "kalshi"),
                     ["kalshi", "candles", tag, "history", s] + ([M] if M else []), K_CANDLE_SCHEMA, not failed and _stored_complete(archive, src))
                _log_store(archive, K_LOG, klog, "kalshi")
            if log:
                log(f"kalshi candles {period} {name}: {rep[name]}")
        if dry_run:
            rep["_plan"] = _total(items, note="from the stored listings")
        return rep
    finally:
        if own:
            c.close()


def kalshi_trades(client: httpx.Client, th: Throttle, m: dict, cut_s: int, max_pages: int = KALSHI_MAX_PAGES, retries: int = KALSHI_RETRIES,
                  backoff: float = KALSHI_BACKOFF) -> tuple[Optional[list[dict]], dict]:
    """Every print of a market (historical store before the trades cutoff, live after; both when it spans it), newest
    first, at most ``max_pages`` pages per route. (trades or None, meta {calls, complete, complete_from})."""
    open_s, settled = _ts(m.get("open_time")) or 0, _ts(m.get("settlement_ts") or m.get("close_time")) or 0
    routes = (["/historical/trades"] if settled < cut_s else ["/markets/trades"] if open_s >= cut_s else ["/markets/trades", "/historical/trades"])
    got: dict[str, dict] = {}
    calls, complete = 0, True
    for path in routes:
        ts, meta = kalshi_pages(client, th, path, {"ticker": m["ticker"], "limit": 1000}, "trades", max_pages=max_pages, retries=retries, backoff=backoff)
        calls += meta["calls"]
        if ts is None:
            return None, {"calls": calls, "error": meta.get("error")}
        complete = complete and bool(meta.get("complete"))
        for t in ts:
            if t.get("trade_id"):
                got[t["trade_id"]] = t
    out = sorted(got.values(), key=lambda t: (_ts(t.get("created_time")) or 0, t["trade_id"]))
    cf = None if complete or not out else _iso_s((_ts(out[0].get("created_time")) or 0) + 1)
    return out, {"calls": calls, "complete": complete, "complete_from": cf, "routes": routes}


def fetch_kalshi_trades(store=None, series: Optional[Iterable[str]] = None, max_pages: int = KALSHI_MAX_PAGES, limit: Optional[int] = None,
                        dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                        min_interval: float = PACE["kalshi"], retries: int = KALSHI_RETRIES, backoff: float = KALSHI_BACKOFF,
                        report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                        log: Optional[Callable] = None, **_) -> dict:
    """``kalshi-trades-<S>[-<M>]`` for the ``kalshi_trade_select`` markets of every stored listing (or ``series``). Markets
    already stored or logged are skipped; each bundle with new markets is stored whole."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        listings = stored_kalshi_listings(archive)
        if series is not None:
            want = set(series)
            listings = [n for n in listings if _listing_series(n)[0] in want]
        if not listings and dry_run:
            items = []
            for s in KALSHI_SERIES:
                kind = _series_kind(s)
                n = KALSHI_EST.get(s, 0) if kind == "election" else KALSHI_TRADES_CAP["macro" if kind == "macro" else "other"]
                items.append(_item(f"kalshi-trades-{s}", "kalshi", n * KALSHI_TRADE_PAGES, n * KALSHI_TRADE_PAGES * 700, "k_trade", min_interval))
            months = len(_months(CRYPTO_FIRST_DAY, _yesterday()))
            n = months * KALSHI_TRADES_CAP["crypto_month"]
            items.append(_item("kalshi-trades-KXBTCD-<months>", "kalshi", n * 2, n * 1500, "k_trade", min_interval))
            rep["_plan"] = _total(items, note="listings not stored yet: estimate")
            return rep
        if limit is not None:
            listings = listings[:limit]
        klog = _log_load(archive, K_LOG)
        cutoff = kalshi_cutoff(c, th, retries, backoff) if not dry_run else KALSHI_CUTOFF_FALLBACK
        cut_s = _ts(cutoff["trades_created_ts"]) or 0
        items = []
        for src in listings:
            s, M = _listing_series(src)
            name = f"kalshi-trades-{s}" + (f"-{M}" if M else "")
            sel = kalshi_trade_select([r["value"] for r in _stored_rows(archive, src)], s)
            if not sel:
                continue
            stored = [] if refresh else _stored_rows(archive, name)
            have = {str(r["value"].get("ticker")) for r in stored}
            if not refresh:
                have |= {v["id"] for v in klog.values() if v.get("product") == "trades" and "complete" in v}
            work = [m for m in sel if m["ticker"] not in have]
            if not work:
                rep[name] = {"skipped": "every selected market stored"}
                continue
            if dry_run:
                items.append(_item(name, "kalshi", len(work) * KALSHI_TRADE_PAGES, len(work) * KALSHI_TRADE_PAGES * 700, "k_trade", min_interval))
                continue
            new, failed, calls, cut, done = [], [], 0, False, 0
            fetched_at = now_iso()
            for m in work:
                if max_calls is not None and calls + max_pages > max_calls:
                    cut = True
                    break
                ts, meta = kalshi_trades(c, th, m, cut_s, max_pages, retries, backoff)
                calls += meta["calls"]
                if ts is None:
                    failed.append({"ticker": m["ticker"], **meta})
                    continue
                for t in ts:
                    ct = _norm_iso(t.get("created_time"), fetched_at)
                    new.append(_row("kalshi", "trade", t["trade_id"], ct, ct, t))
                done += 1
                klog[f"trades:{m['ticker']}"] = {"product": "trades", "id": m["ticker"], "series": s, "month": M, "n": len(ts),
                                                 "volume_fp": _kvol(m), "calls": meta["calls"], "complete": bool(meta["complete"]),
                                                 "complete_from": meta["complete_from"], "routes": meta["routes"], "fetched_at": fetched_at}
            rows = sorted(_merge(stored, new, "ticker"), key=lambda r: (str(r["value"].get("ticker")), r["observed_at"], r["key"]))
            _emit(rows_out, name, rows)
            rep[name] = {"selected": len(sel), "todo": len(work), "fetched": done, "calls": calls, "rows": len(rows),
                         **({"cut": "max_calls (not stored)"} if cut else {}), **({"failed": failed[:5], "n_failed": len(failed)} if failed else {})}
            if archive is not None and not cut:
                _put(archive, name, rows,
                     _recipe(f"GET {KALSHI}/historical/trades?ticker=<T>&limit=1000&cursor=<c> for prints before the trades cutoff "
                             f"({cutoff['trades_created_ts']}) and GET {KALSHI}/markets/trades?ticker=<T> after it (both when a market spans it), "
                             f"at most {max_pages} pages per route, for the markets of {src} chosen by mandel.data.pm_history.kalshi_trade_select "
                             "(a capped market is complete from complete_from on: kalshi-fetch-log).", "kalshi"),
                     ["kalshi", "trades", "history", s] + ([M] if M else []), K_TRADE_SCHEMA, not failed and _stored_complete(archive, src))
                _log_store(archive, K_LOG, klog, "kalshi")
            if log:
                log(f"kalshi trades {name}: {rep[name]}")
        if dry_run:
            rep["_plan"] = _total(items, note="from the stored listings")
        return rep
    finally:
        if own:
            c.close()


# ================================================================================================== pairs ==

FOMC_SIZES = (25, 50, 75, 100)        # 100 = 100 bps or more
PAIR_SCHEMA = ("kind pair: value = {pair_id, family (fomc | cpi_mom | cpi_yoy | core_cpi_mom | core_cpi_yoy | btc | election), key, "
               "template, relation 'sum(sign*p_pm) = const + sum(sign*p_kalshi)', const, pm [{market_id, condition_id, yes_token, label, "
               "sign, start, end, volumeNum (end-of-life, proxy only)}], kalshi [{ticker, event_ticker, series, label, sign, open_time, "
               "close_time, settlement_ts}], pm_rules, kalshi_rules, timing_gap_hours (PM endDate - Kalshi close_time), basis_note, "
               "audited (False: the hand audit is the harness's job), frozen_at}; observed_at = frozen_at; available_at = the latest "
               "listing time of the legs")
CPI_FAMILIES = {"cpi_mom": "KXCPI", "cpi_yoy": "KXCPIYOY", "core_cpi_mom": "KXCPICORE", "core_cpi_yoy": "KXCPICOREYOY"}
PAIR_KALSHI = ("KXFEDDECISION", "KXCPI", "KXCPIYOY", "KXCPICORE", "KXCPICOREYOY", "PRES", "POPVOTE")
BTC_PAIR_HOUR = 17
BTC_MAX_EVENTS = 150


def fomc_atoms(label: str) -> Optional[frozenset]:
    """The rate moves (bps, signed) an FOMC outcome label covers: 'No change' -> {0}; '25 bps decrease' -> {-25};
    '50+ bps decrease' / 'Cut >25bps' -> {-50, -75, -100}; '25+ bps increase' -> {25, 50, 75, 100}; None if unparseable."""
    s = (label or "").lower().replace("–", "-")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if re.search(r"no change|maintain|no cut|\bhold\b|unchanged", s) or (nums and max(nums) == 0):
        return frozenset({0})
    sign = -1 if re.search(r"cut|decrease|lower", s) else 1 if re.search(r"hike|increase|raise", s) else None
    if sign is None or not nums:
        return None
    n = nums[0]
    if re.search(r">\s*\d+", s):
        sizes = [a for a in FOMC_SIZES if a > n]
    elif re.search(r"\d+\s*\+|\d+\s*bps?\s*or more|at least", s):
        sizes = [a for a in FOMC_SIZES if a >= n]
    else:
        sizes = [min(n, 100)] if n in FOMC_SIZES or n > 100 else []
    return frozenset(sign * a for a in sizes) if sizes else None


def cpi_bucket(label: str) -> Optional[tuple[str, float]]:
    """('ge', a) for v >= a, ('le', b) for v <= b, ('eq', c) for v == c (one-decimal prints); None for ranges or text."""
    s = (label or "").strip().lower().replace(" ", "").replace("–", "-").replace("−", "-")
    m = re.fullmatch(r"(≤|<=|<|≥|>=|>)?(-?\d+(?:\.\d+)?)%?(\+|orhigher|ormore|orabove|orlower|orless|orbelow)?", s)
    if not m:
        return None
    pre, x, post = m.group(1), round(float(m.group(2)), 1) + 0.0, m.group(3)
    if pre in ("≤", "<=") or post in ("orlower", "orless", "orbelow"):
        return ("le", x)
    if pre == "<":
        return ("le", round(x - 0.1, 1) + 0.0)
    if pre in ("≥", ">=") or post in ("+", "orhigher", "ormore", "orabove"):
        return ("ge", x)
    if pre == ">":
        return ("ge", round(x + 0.1, 1) + 0.0)
    return ("eq", x)


def _k1(x: float) -> str:
    return f"{round(x, 1) + 0.0:.1f}"


def kalshi_strike(m: dict) -> Optional[float]:
    """The 'above x' threshold of a Kalshi market: floor_strike when strike_type is 'greater', else the ticker's -T<x>."""
    if m.get("strike_type") not in (None, "greater"):
        return None
    x = _f(m.get("floor_strike"))
    if x is None:
        mt = re.search(r"-T(-?\d+(?:\.\d+)?)$", str(m.get("ticker") or ""))
        x = float(mt.group(1)) if mt else None
    return x


def _event_month(event_ticker: str) -> Optional[tuple[int, int]]:
    m = re.search(r"-(\d{2})([A-Z]{3})$", event_ticker or "")
    return (2000 + int(m.group(1)), MON3.index(m.group(2)) + 1) if m and m.group(2) in MON3 else None


def _pm_leg(m: dict, sign: int, label: str, ev: Optional[dict] = None) -> dict:
    toks = _tokens(m)
    s, e = _pm_window(m, ev)
    end = _pm_end(m, ev)
    me, ee = _ts(m.get("endDate")), _ts((ev or {}).get("endDate"))
    return {"market_id": str(m.get("id")), "condition_id": m.get("conditionId"), "yes_token": toks[0] if toks else None, "label": label,
            "sign": sign, "start": m.get("startDate") or m.get("createdAt") or (ev or {}).get("startDate"), "end": _iso_s(e) if e else m.get("endDate"),
            "end_date": _iso_s(end) if end else m.get("endDate"), "market_end_date": m.get("endDate"),
            "end_date_mismatch_hours": round((ee - me) / HOUR, 2) if me is not None and ee is not None and abs(ee - me) > DAY else None,
            "volumeNum": _f(m.get("volumeNum"))}


def _k_leg(m: dict, sign: int) -> dict:
    return {"ticker": m.get("ticker"), "event_ticker": m.get("event_ticker"), "series": (m.get("event_ticker") or "").split("-")[0],
            "label": m.get("yes_sub_title") or m.get("subtitle"), "sign": sign, "open_time": m.get("open_time"), "close_time": m.get("close_time"),
            "settlement_ts": m.get("settlement_ts")}


def _pair(family: str, key: str, template: str, pm: list[dict], km: list[dict], const: float, pm_rules: str, k_rules: str,
          basis: str, frozen_at: str, n: int) -> dict:
    pm_end = max((_ts(l["end_date"]) or 0) for l in pm)
    k_close = max((_ts(l["close_time"]) or 0) for l in km)
    listed = [_ts(l["start"]) for l in pm] + [_ts(l["open_time"]) for l in km]
    av = _iso_s(max(x for x in listed if x is not None)) if any(x is not None for x in listed) else frozen_at
    v = {"pair_id": f"{family}:{key}:{n}", "family": family, "key": key, "template": template,
         "relation": "sum(sign*p_pm) = const + sum(sign*p_kalshi)", "const": const, "pm": pm, "kalshi": km,
         "pm_rules": (pm_rules or "")[:600], "kalshi_rules": (k_rules or "")[:600],
         "timing_gap_hours": round((pm_end - k_close) / HOUR, 2) if pm_end and k_close else None, "basis_note": basis,
         "audited": False, "frozen_at": frozen_at}
    return _row("mandel", "pair", v["pair_id"], frozen_at, min(av, frozen_at, key=_ts), v)


def _components(pm_items: list[tuple[dict, frozenset]], k_items: list[tuple[dict, frozenset]]) -> list[tuple[list, list]]:
    """Groups of PM and Kalshi outcomes linked by overlapping atoms whose atom unions agree, with disjoint atoms within each side."""
    nodes = [("p", i) for i in range(len(pm_items))] + [("k", i) for i in range(len(k_items))]
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, (_, a) in enumerate(pm_items):
        for j, (_, b) in enumerate(k_items):
            if a & b:
                parent[find(("p", i))] = find(("k", j))
    groups = defaultdict(list)
    for n in nodes:
        groups[find(n)].append(n)
    out = []
    for g in groups.values():
        ps = [pm_items[i] for t, i in g if t == "p"]
        ks = [k_items[i] for t, i in g if t == "k"]
        if not ps or not ks:
            continue
        ua, ub = frozenset().union(*(a for _, a in ps)), frozenset().union(*(b for _, b in ks))
        if ua != ub or sum(len(a) for _, a in ps) != len(ua) or sum(len(b) for _, b in ks) != len(ub):
            continue
        out.append(([m for m, _ in ps], [m for m, _ in ks]))
    return out


def _pm_ref_month(slug: str, end: Optional[str], mon: str) -> Optional[tuple[int, int]]:
    mi = MONTHS.index(mon) + 1
    y = re.search(r"-(20\d\d)(?:-|$)", slug or "")
    if y:
        return int(y.group(1)), mi
    e = _ts(end)
    if e is None:
        return None
    ed = datetime.fromtimestamp(e, UTC)
    return (ed.year if mi < ed.month else ed.year - 1), mi


def match_pairs(pm_events: Iterable[dict], kalshi_markets: Iterable[dict], btc_events: Iterable[dict] = (), frozen_at: Optional[str] = None,
                btc_hour: int = BTC_PAIR_HOUR, btc_max_events: int = BTC_MAX_EVENTS) -> list[dict]:
    """Templated Polymarket-Kalshi pairs (module docstring) from listing fields only. Returns pair rows."""
    frozen_at = frozen_at or now_iso()
    kms = [m for m in kalshi_markets if m.get("ticker")]
    k_by_event = defaultdict(list)
    for m in kms:
        k_by_event[m.get("event_ticker")].append(m)
    out, n = [], 0

    def k_events(series_prefixes: tuple, ym: tuple[int, int]) -> list[dict]:
        res = []
        for ev, ms in k_by_event.items():
            base = (ev or "").split("-")[0]
            if base in series_prefixes and _event_month(ev or "") == ym:
                res += ms
        return res

    fomc_rx = re.compile(rf"^fed-(?:decision-in|interest-rates)-({_MON})(?:-|$)")
    cpi_rx = [("cpi_mom", re.compile(rf"^({_MON})-inflation-(?:us-)?monthly")), ("cpi_yoy", re.compile(rf"^({_MON})-inflation-(?:us-)?annual")),
              ("core_cpi_mom", re.compile(rf"^core-cpi-(?:ex-food-and-energy-)?mom-({_MON})")),
              ("core_cpi_yoy", re.compile(rf"^core-cpi-(?:ex-food-and-energy-)?yoy-({_MON})"))]
    single_rx = re.compile(r"inflation\s*>\s*(-?\d+(?:\.\d+)?)%\s*from\s+([a-z]{3})[a-z]*\s+to\s+([a-z]{3})[a-z]*\s+(\d{4})", re.I)
    for ev in pm_events:
        slug = ev.get("slug") or ""
        markets = [m for m in ev.get("markets") or [] if len(_tokens(m)) == 2]
        if not markets:
            continue
        desc = " ".join(str(x or "") for x in [ev.get("description")] + [m.get("description") for m in markets[:1]])
        mf = fomc_rx.match(slug)
        if mf:
            e = _ts(ev.get("endDate") or markets[0].get("endDate"))
            if e is None:
                continue
            ed = datetime.fromtimestamp(e, UTC)
            ym = (ed.year, MONTHS.index(mf.group(1)) + 1)
            kk = k_events(("KXFEDDECISION", "FEDDECISION"), ym)
            pm_items = [(m, a) for m in markets if (a := fomc_atoms(m.get("groupItemTitle") or m.get("question") or ""))]
            k_items = [(m, a) for m in kk if (a := fomc_atoms(m.get("yes_sub_title") or m.get("subtitle") or ""))]
            for ps, ks in _components(pm_items, k_items):
                n += 1
                out.append(_pair("fomc", f"{ym[0]}-{ym[1]:02d}", "FOMC outcome atoms (bps move sets) equal on both sides",
                                 [_pm_leg(m, 1, m.get("groupItemTitle") or "", ev) for m in ps], [_k_leg(m, 1) for m in ks], 0.0, desc,
                                 ks[0].get("rules_primary"), "same FOMC statement; Kalshi settles on the target-range upper bound move",
                                 frozen_at, n))
            continue
        fam, mon = None, None
        for f, rx in cpi_rx:
            mm = rx.match(slug)
            if mm:
                fam, mon = f, mm.group(1)
                break
        single = None
        if fam is None and slug.startswith("us-inflation-") and len(markets) == 1:
            single = single_rx.search(markets[0].get("question") or ev.get("title") or "")
            if single:
                fam = "cpi_mom"
        if fam is None or not re.search(r"bureau of labor statistics|\bbls\b", desc, re.I):
            continue
        if single:
            m3 = single.group(3).lower()
            mi = next((i for i, x in enumerate(MONTHS) if x.startswith(m3)), None)
            if mi is None:
                continue
            ym = (int(single.group(4)), mi + 1)
        else:
            ym = _pm_ref_month(slug, ev.get("endDate") or markets[0].get("endDate"), mon)
            if ym is None:
                continue
        series = CPI_FAMILIES[fam]
        strikes = {}
        for m in k_events((series, series.replace("KX", "", 1)), ym):
            x = kalshi_strike(m)
            if x is not None:
                strikes[_k1(x)] = m
        for m in markets:
            if single:
                b = ("ge", round(float(single.group(1)) + 0.1, 1) + 0.0)
                lab = m.get("question") or ""
            else:
                lab = m.get("groupItemTitle") or ""
                b = cpi_bucket(lab)
            if b is None:
                continue
            kind, x = b
            if kind == "ge":
                need, const = [(_k1(x - 0.1), 1)], 0.0
            elif kind == "le":
                need, const = [(_k1(x), -1)], 1.0
            else:
                need, const = [(_k1(x - 0.1), 1), (_k1(x), -1)], 0.0
            if not all(k in strikes for k, _ in need):
                continue
            n += 1
            kl = [_k_leg(strikes[k], sg) for k, sg in need]
            out.append(_pair(fam, f"{ym[0]}-{ym[1]:02d}", f"CPI bucket {kind} {x:.1f} = {const:g} + " + " ".join(f"{'+' if sg > 0 else '-'}K(above {k})" for k, sg in need),
                             [_pm_leg(m, 1, lab, ev)], kl, const, desc, strikes[need[0][0]].get("rules_primary"),
                             "same BLS print (one decimal); check revisions and release-delay clauses", frozen_at, n))
    # BTC: Polymarket <date>-<h>pm-et events at btc_hour vs Kalshi KXBTCD <date><hour>
    btc_rx = re.compile(rf"^bitcoin-above-on-({_MON})-(\d{{1,2}})(?:-(20\d\d))?-(\d{{1,2}})(am|pm)-et(?:-\d+)?$")
    cands = []
    for ev in btc_events:
        mm = btc_rx.match(ev.get("slug") or "")
        if not mm:
            continue
        h = int(mm.group(4)) % 12 + (12 if mm.group(5) == "pm" else 0)
        if h != btc_hour:
            continue
        e = _ts(ev.get("endDate"))
        year = int(mm.group(3)) if mm.group(3) else (datetime.fromtimestamp(e, UTC).year if e else None)
        if year is None:
            continue
        try:
            d = date(year, MONTHS.index(mm.group(1)) + 1, int(mm.group(2)))
        except ValueError:
            continue
        cands.append((d, ev))
    for d, ev in sorted(cands, key=lambda x: x[0], reverse=True)[:btc_max_events]:
        kk = {}
        for m in k_by_event.get(kxbtcd_event(d.isoformat(), btc_hour), []):
            x = _f(m.get("floor_strike"))
            if x is not None and m.get("strike_type") in (None, "greater"):
                kk[round(x + 0.01, 2)] = m
        for m in ev.get("markets") or []:
            if len(_tokens(m)) != 2:
                continue
            g = (m.get("groupItemTitle") or "").replace(",", "").replace("$", "").strip()
            x = _f(g)
            if x is None:
                q = re.search(r"above \$?([\d,]+(?:\.\d+)?)", m.get("question") or "")
                x = _f(q.group(1).replace(",", "")) if q else None
            if x is None or round(x, 2) not in kk:
                continue
            km = kk[round(x, 2)]
            n += 1
            out.append(_pair("btc", f"{d.isoformat()}T{btc_hour:02d}ET", "PM above X at the hour = Kalshi above X - 0.01 at the same ET hour",
                             [_pm_leg(m, 1, m.get("groupItemTitle") or "", ev)], [_k_leg(km, 1)], 0.0, ev.get("description") or "",
                             km.get("rules_primary"), "resolution basis differs: Binance BTCUSDT candle close (PM) vs CF Benchmarks BRTI "
                             "60-second average (Kalshi); a print exactly at X differs", frozen_at, n))
    # 2024 election, by candidate name
    by_slug = {ev.get("slug"): ev for ev in pm_events}
    for slug, kev in ELECTION_EVENTS.items():
        ev = by_slug.get(slug)
        if not ev:
            continue
        kn = {re.sub(r"[^a-z]", "", (m.get("yes_sub_title") or "").lower()): m for m in k_by_event.get(kev, [])}
        for m in ev.get("markets") or []:
            key = re.sub(r"[^a-z]", "", (m.get("groupItemTitle") or "").lower())
            if key and key in kn and len(_tokens(m)) == 2:
                n += 1
                out.append(_pair("election", f"{kev}:{key}", "same race, same candidate", [_pm_leg(m, 1, m.get("groupItemTitle") or "", ev)],
                                 [_k_leg(kn[key], 1)], 0.0, m.get("description") or ev.get("description") or "", kn[key].get("rules_primary"),
                                 "PM resolves on the AP/Fox/NBC call; Kalshi on the certified winner: check the rules", frozen_at, n))
    return out


def build_pairs(store=None, btc_hour: int = BTC_PAIR_HOUR, btc_max_events: int = BTC_MAX_EVENTS, limit: Optional[int] = None,
                dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, report: Optional[dict] = None,
                rows_out: Optional[dict] = None, log: Optional[Callable] = None, **_) -> dict:
    """``pm-kalshi-pairs`` from the stored events and Kalshi listings (no request). Waits (stores nothing) until every
    needed listing is stored; kept frozen once stored (``refresh`` rebuilds it)."""
    archive = _archive(store)
    rep = report if report is not None else {}
    if dry_run:
        rep["_plan"] = _total([{"bundle": PAIRS, "calls": 0, "rows": 1000, "gz_mb": round(1000 * ROW_GZ["pair"] / 1e6, 2), "minutes": 0.1}])
        return rep
    if archive is None:
        rep["skipped"] = "no archive"
        return rep
    if skip_stored and not refresh and _stored_complete(archive, PAIRS):
        rep[PAIRS] = {"skipped": "stored (frozen); refresh=True rebuilds it"}
        return rep
    if hasattr(archive, "_reload_index"):
        archive._reload_index()                       # listings stored meanwhile by a parallel Kalshi process
    need = ["polymarket-events-macro"] + [f"kalshi-settled-markets-{s}" for s in PAIR_KALSHI]
    missing = [n for n in need if _stored_entry(archive, n) is None]
    if missing:
        rep[PAIRS] = {"waiting": missing}
        return rep
    pm_events = [r["value"] for r in _stored_rows(archive, "polymarket-events-macro")]
    btc_events = [r["value"] for r in _stored_rows(archive, "polymarket-events-btc-above")]
    kms = []
    for name in need[1:] + [n for n in stored_kalshi_listings(archive) if n.startswith("kalshi-settled-markets-KXBTCD-")]:
        kms += [r["value"] for r in _stored_rows(archive, name)]
    frozen = now_iso()
    rows = match_pairs(pm_events, kms, btc_events, frozen_at=frozen, btc_hour=btc_hour, btc_max_events=btc_max_events)
    by = defaultdict(int)
    for r in rows:
        by[r["value"]["family"]] += 1
    _emit(rows_out, PAIRS, rows)
    rep[PAIRS] = {"pairs": len(rows), "by_family": dict(by)}
    _put(archive, PAIRS, rows,
         _recipe("mandel.data.pm_history.match_pairs over polymarket-events-macro, polymarket-events-btc-above and "
                 f"kalshi-settled-markets-{{{','.join(PAIR_KALSHI)}}} plus kalshi-settled-markets-KXBTCD-<M> (no request): templated FOMC, CPI, "
                 f"BTC ({btc_hour}:00 ET, latest {btc_max_events} events) and 2024-election pairs from listing fields only (never prices, "
                 f"volumes or outcomes), frozen at {frozen} before any pair-leg price fetch. Not hand-audited.", "both"),
         ["pairs", "polymarket", "kalshi", "cross-venue"], PAIR_SCHEMA, True)
    return rep


# ======================================================================================== harness loaders ==

def load_pm_markets(archive, legacy: bool = True) -> list[dict]:
    """Closed-market rows from every polymarket-closed-markets-<M> (and the legacy bundle), one per market id (the monthly
    row wins). Read only."""
    out: dict[str, dict] = {}
    names = ([LEGACY_MARKETS] if legacy else []) + [f"polymarket-closed-markets-{M}" for M in stored_pm_months(archive)]
    for n in names:
        for r in _stored_rows(archive, n):
            out[str(r["value"].get("id"))] = r
    return list(out.values())


def load_pm_daily(archive, legacy: bool = True) -> list[dict]:
    """Daily price rows from every polymarket-price-history-daily-<M> (and the legacy bundle), one per (token, t). Read only."""
    out: dict[tuple, dict] = {}
    names = ([LEGACY_DAILY] if legacy else []) + sorted(e.name for e in archive.entries() if re.fullmatch(r"polymarket-price-history-daily-\d{4}-\d{2}", e.name))
    for n in names:
        for r in _stored_rows(archive, n):
            out[(str(r["value"]["token"]), int(r["value"]["t"]))] = r
    return sorted(out.values(), key=_price_sort)


# ============================================================================================== fetch_all ==

def _candles_daily(store=None, **kw):
    return fetch_kalshi_candles(store, period=1440, **kw)


def _candles_hourly(store=None, **kw):
    return fetch_kalshi_candles(store, period=60, **kw)


SOURCES: dict[str, Callable] = {
    "pm_markets": fetch_pm_markets, "pm_events": fetch_pm_events, "kalshi_markets": fetch_kalshi_markets, "pairs": build_pairs,
    "pm_daily": fetch_pm_daily, "pm_hourly": fetch_pm_hourly, "kalshi_candles_daily": _candles_daily,
    "kalshi_candles_hourly": _candles_hourly, "pm_trades": fetch_pm_trades, "kalshi_trades": fetch_kalshi_trades,
}
DEFAULT_SOURCES = tuple(SOURCES)
PM_SOURCES = ("pm_markets", "pm_events", "pm_daily", "pairs", "pm_hourly", "pm_trades")         # Polymarket hosts (+ pairs)
KALSHI_SOURCES = ("kalshi_markets", "kalshi_candles_daily", "kalshi_candles_hourly", "kalshi_trades")


def fetch_all_pm(store, dry_run: bool = False, limit: Optional[int] = None, sources: Optional[Iterable[str]] = None,
                 max_calls: Optional[int] = None, refresh: bool = False, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                 log: Optional[Callable] = None, min_interval: Optional[float] = None, options: Optional[dict] = None) -> dict:
    """Run the prediction-market fetchers in dependency order (listings first, then the pairs table, then per-market
    products). ``limit`` caps bundles per source; ``max_calls`` requests per bundle (previews: never stored); ``options``
    = {source: {kwarg: value}}; ``min_interval`` overrides every source's pace. ``dry_run`` makes no request. Polymarket
    and Kalshi are different hosts: run ``--sources`` PM_SOURCES and KALSHI_SOURCES as two processes to halve the wall
    time (pairs waits for the Kalshi listings and stores nothing until they exist). Returns {source: report} plus
    '_total' (dry run) and '_gitignore'."""
    names = list(sources) if sources is not None else list(DEFAULT_SOURCES)
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise ValueError(f"unknown sources: {unknown}; known: {sorted(SOURCES)}")
    out = report if report is not None else {}
    opts = options or {}
    for n in names:
        rep: dict = {}
        kw = {"dry_run": dry_run, "limit": limit, "refresh": refresh, "rows_out": rows_out, "log": log, **opts.get(n, {})}
        if n != "pairs":
            kw["max_calls"] = max_calls
            if min_interval is not None:
                kw["min_interval"] = min_interval
        t0 = time.time()
        try:
            SOURCES[n](store, report=rep, **kw)
        except KeyboardInterrupt:
            out[n] = {**rep, "_interrupted": True}
            raise
        rep["_seconds"] = round(time.time() - t0, 1)
        out[n] = rep
        if log:
            log(f"{n}: done in {rep['_seconds']} s")
    if dry_run:
        plans = [out[n]["_plan"] for n in names if "_plan" in out.get(n, {})]
        out["_total"] = {"calls": sum(p["calls"] for p in plans), "rows": sum(p["rows"] for p in plans),
                         "gz_mb": round(sum(p["gz_mb"] for p in plans), 1), "minutes": round(sum(p["minutes"] for p in plans), 1),
                         "minutes_by_host_group": {
                             "polymarket": round(sum(out[n]["_plan"]["minutes"] for n in names if n in PM_SOURCES and "_plan" in out.get(n, {})), 1),
                             "kalshi": round(sum(out[n]["_plan"]["minutes"] for n in names if n in KALSHI_SOURCES and "_plan" in out.get(n, {})), 1)}}
    out["_gitignore"] = GITIGNORE_LINES
    return out


def family_table(plan_report: dict) -> list[dict]:
    """One line per bundle family from a dry-run report: calls, rows, gzip MB, minutes, theories, licence, .gitignore line."""
    acc: dict[str, dict] = {}
    for src, rep in plan_report.items():
        if not isinstance(rep, dict) or "_plan" not in rep:
            continue
        for it in rep["_plan"]["per_bundle"]:
            name = it["bundle"]
            fam = _family(name) or _family(re.sub(r"<[^>]*>", "x", name))
            key = fam[0] if fam else name
            a = acc.setdefault(key, {"family": key, "function": fam[2] if fam else src, "theories": fam[3] if fam else [],
                                     "licence": LICENCE[fam[1]] if fam else "", "available_at": fam[4] if fam else "", "in_git": False,
                                     "gitignore_line": f"mandel/archive/data/{key}.jsonl.gz", "bundles": 0, "calls": 0, "rows": 0,
                                     "gz_mb": 0.0, "minutes": 0.0})
            a["bundles"] += 1
            for k in ("calls", "rows", "gz_mb", "minutes"):
                a[k] = round(a[k] + it[k], 2)
    return list(acc.values())


# ============================================================================================ command line ==

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m mandel.data.pm_history",
                                description="Fetch the batch-6c prediction-market bundles (Polymarket Gamma / CLOB / data-api, Kalshi) into the archive.")
    p.add_argument("--sources", help=f"comma-separated subset of {','.join(SOURCES)} (or 'polymarket' / 'kalshi')")
    p.add_argument("--dry-run", action="store_true", help="no request: print the plan (calls, rows, gzip MB, minutes)")
    p.add_argument("--preview", metavar="DIR", help="store into a scratch archive DIR/archive (ledger DIR/ledger.jsonl), not the repo's; "
                                                    "write DIR/report.json and DIR/<bundle>.sample.json")
    p.add_argument("--limit", type=int, help="bundles per source")
    p.add_argument("--max-calls", type=int, help="requests per bundle (preview; such bundles are never stored)")
    p.add_argument("--refresh", action="store_true", help="fetch again what is already stored")
    p.add_argument("--min-interval", type=float, help="seconds between requests for every source (default: PACE per host)")
    p.add_argument("--options", help='JSON {source: {kwarg: value}}, e.g. {"pm_daily": {"per_month": 50}}')
    a = p.parse_args(argv)
    from mandel.archive import Archive
    if a.preview:
        from mandel.ledger import Ledger
        os.makedirs(a.preview, exist_ok=True)
        store = Archive(root=os.path.join(a.preview, "archive"), ledger=Ledger(os.path.join(a.preview, "ledger.jsonl")))
    else:
        store = Archive()
    srcs = None
    if a.sources:
        srcs = list(PM_SOURCES) if a.sources == "polymarket" else list(KALSHI_SOURCES) if a.sources == "kalshi" else a.sources.split(",")
    rows_out: Optional[dict] = {} if a.preview else None
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    rep = fetch_all_pm(store, dry_run=a.dry_run, limit=a.limit, sources=srcs, max_calls=a.max_calls, refresh=a.refresh, rows_out=rows_out,
                       log=log, min_interval=a.min_interval, options=json.loads(a.options) if a.options else None)
    if a.dry_run:
        rep["_families"] = family_table(rep)
    if a.preview:
        for name, rows in (rows_out or {}).items():
            with open(os.path.join(a.preview, f"{name}.sample.json"), "w", encoding="utf-8") as f:
                json.dump({"rows": len(rows), "first": rows[:3], "last": rows[-2:]}, f, indent=1, default=str)
        with open(os.path.join(a.preview, "report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, default=str)
    print(json.dumps(rep if a.dry_run else {k: v for k, v in rep.items() if k != "_gitignore"}, indent=1, default=str)[:200000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
