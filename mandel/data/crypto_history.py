"""
Crypto history for the batch-6c crypto claims: venue candles and trades, CoinMarketCap rank snapshots, CoinMetrics
community metrics, blockchain.info hash rate, DefiLlama yields and the iShares IBIT premium/NAV page.
=====================================================================================================================

Which claims need what (from the batch-6c triage, ``final`` entries whose fetch text names these hosts, and each
theory's ``trial.data`` in mandel/theories/registry.json):

  T-419  Coinbase daily BTC-USD, ETH-USD from 2015 (crypto volume bucket)          -> coinbase-daily-<PID>
  T-330  Coinbase daily USDT-USD (2021-); Kraken trades USDTZUSD / USDCUSD in each   -> coinbase-daily-USDT-USD,
         peg-episode window (signal day - 1 .. + 6 days)                                kraken-trades-stablecoin-episodes
  T-365, T-366  Coinbase daily CBETH-ETH 2023-04 .. 2026-09                         -> coinbase-daily-CBETH-ETH
  T-424  Coinbase product universe (online + delisted), daily candles of every       -> coinbase-products-<day>,
         USD product (point-in-time 30-day dollar-volume ranking), hourly candles       coinbase-daily-<PID>,
         2019-01 .. now for every product that ranks in the top HOURLY_TOP_K            coinbase-hourly-<PID>
  T-328  Coinbase hourly BTC-USD 2024-04 .. 2026-09; iShares IBIT NAV / premium      -> coinbase-hourly-BTC-USD,
                                                                                         ishares-ibit-*
  T-414  Coinbase hourly BTC/ETH/SOL/DOGE-USD for the crypto streams (2025-10 ..)    -> coinbase-hourly-<PID>
  T-331, T-425, T-465, T-337  Coinbase 1-minute BTC-USD 2022-01 .. now               -> coinbase-1m-BTC-USD-<YYYY-MM>
  T-331, T-425, T-465, T-459  Kraken XBTUSD public trades 2022-01 .. now, rebuilt    -> kraken-trades-1m-XBTUSD-<YYYY-MM>
         into 1-minute bars with exact aggressor-side volume
  T-459  (optional replication) Coinbase BTC-USD trades -> 1-minute signed volume    -> coinbase-trades-1m-BTC-USD-<YYYY-MM>
  T-314  CMC historical listings every Sunday and Monday 2017-12-03 .., top 500      -> cmc-historical-listings
  T-420, T-462 (and T-311's crypto variant)  CMC daily listings 2017-11 .., top 200  -> cmc-daily-listings-<YYYY>
         (trailing 30-day dollar volume, point-in-time, dead coins included); per-coin daily OHLCV is optional
                                                                                      -> cmc-coin-daily-<id> (optional)
  T-400  CoinMetrics btc / eth CapMVRVCur, PriceUSD from 2010-07                     -> coinmetrics-<asset>-daily
  T-402  CoinMetrics usdt, usdc, dai, busd, tusd SplyCur; btc CapMrktCurUSD          -> coinmetrics-<asset>-daily
  T-403  blockchain.info hash rate (all, unsampled); CoinMetrics btc HashRate, PriceUSD -> btc-hashrate-daily,
                                                                                         coinmetrics-btc-daily
  T-367  DefiLlama /pools dated snapshot and /chart/<pool> for the pre-registered     -> defillama-yields-pools-<day>,
         Ethereum USDC pools (Aave v3, Spark savings, Maple syrupUSDC; SparkLend too)   defillama-yields

Sources, endpoints and point-in-time rules (every row: {source, kind, key, observed_at, available_at, value}, ISO UTC):

1. Coinbase Exchange, ``https://api.exchange.coinbase.com`` (public, keyless; about 10 requests/s per IP).
   ``/products`` (842 products on 2026-10-15: 515 online, 327 delisted; 492 quoted in USD, 89 of them delisted).
   ``/products/<PID>/candles?granularity=<60|3600|86400>&start=<ISO>&end=<ISO>``: at most 300 buckets per request,
   rows ``[time, low, high, open, close, volume]`` newest first, ``time`` = bucket start; buckets without trades are
   omitted. Paged here in windows of exactly 300 buckets (``end`` inclusive). BTC-USD daily starts 2015-07-20.
   Delisted products keep their candles (MATIC-USD 2023 probe); an unknown product answers 404 NotFound.
   Rows follow the daily-history convention of ``mandel.data.social.collect_history`` exactly: value = {symbol, t,
   open, high, low, close, volume}, observed_at = bar start, available_at = bar start + bar length (a bar is known
   once it has closed: daily +24 h as in daily-history-<SYM>, hourly +1 h as in fetch_hourly, 1-minute +60 s). The
   bar still open at fetch time is never stored. Volume is in the base currency.
   ``/products/<PID>/trades?limit=1000&after=<trade_id>`` (optional, T-459 replication): pages backward by trade id;
   ``side`` is the MAKER's side, so the aggressor is the opposite side. The start of a window is found by bisecting
   the trade id (about 30 one-trade calls).
2. Kraken, ``https://api.kraken.com/0/public`` (public; about 1 request/s sustained per IP; rate errors arrive as
   HTTP 200 with ``error: ["EGeneral:Too many requests"]`` and are retried with backoff).
   ``/Trades?pair=<PAIR>&since=<unix ns>&count=1000``: rows ``[price, volume, time, side b/s, ordertype m/l, misc,
   trade_id]`` in time order, cursor ``last`` (ns). This is the only route to long Kraken history: ``/OHLC`` returns
   only the latest 720 bars per interval (USDTZUSD daily from 2024-10-25 on 2026-10-15), so OHLC history before that
   is UNREACHABLE through it and every Kraken bundle here is rebuilt from Trades. XBTUSD trade ids run from
   44,718,932 (2022-01-01) and 54,254,489 (2023-01-01) to 111,628,818 (2026-10-15): about 67k pages since 2022.
   1-minute bars (kraken-trades-1m-*): value = {symbol, t, open, high, low, close, volume, vwap, n, buy_vol,
   sell_vol, n_buy, n_sell, buy_hi, buy_lo, sell_hi, sell_lo, mkt_vol (market-order volume), first_ts, last_ts,
   last_id}; the minute before each hour mark (HH:59) also carries ``ticks`` = every trade [time, price, volume,
   side, ordertype, trade_id] so the last trade at or before mark - s (0 < s <= 60, T-331's staleness null) is exact.
   available_at = minute end; trades are public at execution. Stablecoin episodes keep raw trades (kind ``trade``,
   available_at = execution time) plus one ``episode-window`` row per window (available_at = the day after the signal
   day, when the Yahoo signal close is known).
3. CoinMarketCap data-api (keyless, undocumented; PUBLIC: answered 200 without a key on 2026-10-15):
   ``https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listings/historical?date=YYYY-MM-DD&start=1&limit=<n>
   &convertId=2781``: the point-in-time ranking for that date, dead coins included (BitConnect id 1513 on
   2018-01-07); limit=500 answered 500 rows. Rows: kind ``listing`` value = {date, id, symbol, slug, name, cmcRank,
   price, volume24h, marketCap, circulatingSupply, totalSupply, maxSupply, percentChange24h, percentChange7d,
   dateAdded, lastUpdated, platform, flags (the coin's tags that mark stablecoins / wrapped / tokenized / bridged /
   liquid-staking assets, for the declared exclusion lists)}, plus one kind ``snapshot`` row per date (n coins, depth).
   The snapshot price for date D is D's close (it equals CMC's daily OHLC close; checked on 2026-10-10..12), so
   observed_at = D 23:59:59 UTC and available_at = D + 1 day 00:00 UTC.
   CMC prices are cross-exchange VWAPs and volume24h includes wash trades; CMC can revise history (exchange
   removals), so these are near point in time, not vintage-stamped. ``.../data-api/v3.1/cryptocurrency/historical?
   id=<id>&convertId=2781&timeStart=<s>&timeEnd=<s>&interval=daily`` returns at most the latest 400 days of the range
   (probed) and nothing for some dead coins (BitConnect), so it is optional; the daily listings carry price and
   volume for every coin, dead or alive.
4. CoinMetrics community API ``https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=<a>&metrics=
   <m,..>&frequency=1d&start_time=2010-07-01&page_size=10000&paging_from=start&ignore_unsupported_errors=true``,
   following ``next_page_url``. Without paging_from=start the pages run from the END backward. A forbidden metric
   (e.g. SOPR) fails the whole request with 403, so a 403 falls back to one request per metric. Rows: kind ``metric``
   value = {asset, day, <metric>: float, ...}; observed_at = day 00:00 UTC, available_at = day + 1 (the metric
   covers the UTC day). Realised cap (MVRV) and hash rate are recomputed by Coin Metrics without vintages: these
   are the current vintage at fetch time (observed in the recipe), near point in time with the one-day lag.
5. blockchain.info ``https://api.blockchain.info/charts/hash-rate?timespan=all&format=json&sampled=false``: daily
   TH/s estimate from 2009-01-03 (one gap 2025-11-13 .. 15 on 2026-10-15). available_at = day + 1.
6. DefiLlama ``https://yields.llama.fi/pools`` (16,790 pools, 11.5 MB on 2026-10-15; frozen as a dated snapshot:
   dead pools are absent, the survivorship caveat of T-367) and ``https://yields.llama.fi/chart/<pool>`` (daily
   tvlUsd, apy, apyBase, apyReward, ... stamped about 23:01 UTC). available_at = the chart timestamp (the APY is on
   chain at that time); snapshot rows: available_at = fetch time.
7. iShares ``https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf`` (HTML; the JSON is
   HTML-escaped). The historical NAV xls (``1521942788811.ajax?fileType=xls&dataType=fund``) and the holdings CSV
   both answer the HTML product page (re-probed 2026-10-15), so there is no NAV history download. The page does
   embed (a) ``premiumDiscountChartData``: the official daily premium/discount of the closing price to NAV in
   percent, previous calendar year + year to date (2025-01-02 .. 2026-10-14, 447 days), so NAV = close /
   (1 + pct/100) with the archived daily-history-IBIT close; (b) the current NAV, closing price, shares outstanding
   and the Basket Bitcoin Amount (BTC per 40,000-share basket = the published bitcoin per share x 40,000);
   (c) ``performanceData``: month-end growth of $10,000 at NAV since 2023-12-31, so month-end NAVs back to 2024-01
   follow from one known NAV. Each run merges into the stored bundles, so the daily history accumulates.
   available_at: premium/discount for day D = 09:30 ET on the next NYSE session (sponsors post the prior day's
   premium/discount before the open; IBIT is a '33 Act trust, so this is sponsor practice, not a legal duty);
   growth-10k month ends = month end + 15 days; the current snapshot = min(fetch time, that next-session rule).

Licences. The GitHub repo is public and none of these sources is US federal public domain or under an open
redistribution licence: Coinbase, Kraken, CoinMarketCap, blockchain.com, DefiLlama and BlackRock grant no
redistribution right, and Coin Metrics community data is CC BY-NC 4.0 (non-commercial). Every bundle is therefore
local disk only (``in_git=False``, always); ``GITIGNORE_LINES`` lists the .gitignore lines (bundles are stored as
``mandel/archive/data/<name>.jsonl.gz``) and ``gitignore_line(name)`` maps a bundle to its line.

Resumability. Every fetcher skips bundles already stored complete (tag ``complete``) unless ``refresh=True``.
Month-chunked bundles are complete once their month has closed and every page succeeded; the open month is stored
with tag ``partial`` and fetched again on the next run. A bundle whose paging failed, or that a preview cut short
(``max_calls``), is never stored. Snapshot bundles (CMC, Kraken episodes, iShares) merge new dates into the stored
bundle with ``mandel.data.deribit_history._merge_store`` (streamed) and skip dates already stored. A long run can be
interrupted at any point: what was stored stays, and the next run continues.

Estimates (``dry_run``, 2026-10-15; gzip bytes per row measured on the live previews in fetch6c/crypto; minutes at ``PACE``):
  * coinbase-daily-*: ~493 bundles (492 USD products + CBETH-ETH), 6.9k calls, ~0.57M rows, ~16 MB, ~29 min.
  * coinbase-hourly-*: ~110 bundles (depends on the candidate ranking), ~12.5k calls, ~3.4M rows, ~125 MB, ~52 min.
  * coinbase-1m-BTC-USD-*: 58 bundles, 8.4k calls, 2.5M rows, ~83 MB, ~35 min.
  * kraken-trades-1m-XBTUSD-*: 58 bundles, ~67k calls, 2.5M rows, ~250 MB, ~18.6 h at 1 call/s (busy days page 4x more:
    2026-10-15 printed 166k trades in 19 hours). Run it as its own process next to the rest: the hosts differ and the
    archive serialises concurrent writers.
  * kraken-trades-stablecoin-episodes: ~200 calls, ~0.19M rows, ~6 MB, ~4 min (the 2023-03-11 USDC window pages more).
  * cmc-historical-listings: 926 calls, 0.46M rows, ~42 MB, ~19 min; cmc-daily-listings-*: 3,270 calls, 0.66M rows, ~68 MB,
    ~65 min.
  * coinmetrics-*-daily: 7 calls, 25k rows, ~1 MB; btc-hashrate-daily: 1 call, 6.5k rows; defillama: 5 calls (the /pools
    snapshot is 11.5 MB raw, 2.5 MB stored); ishares: 1 call.
  * Default total: ~99k calls, ~10.3M rows, ~595 MB gzip, ~22 hours (18.6 of them Kraken). Optional: cmc-coin-daily-*
    ~2.7k calls, ~41 MB, ~54 min; coinbase-trades-1m-BTC-USD-2025-01 ~14k calls, ~58 min.

Every ``fetch_*`` takes ``store`` (an Archive, an ObservationStore whose ``.archive`` is used, or None to store
nothing), ``limit`` (bundles, or snapshot dates for CMC), ``dry_run`` (no request: the plan with calls, rows, gzip MB
and minutes goes in ``report['_plan']``), ``skip_stored``, ``refresh``, ``max_calls`` (requests per bundle, for
previews), ``report`` and ``rows_out`` (a dict that receives each fetched bundle's rows). ``fetch_all_crypto`` runs
them in order. Command line: ``python3 -m mandel.data.crypto_history [--dry-run] [--preview DIR] [--limit N]
[--max-calls N] [--sources a,b] [--optional] [--refresh]``.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import math
import os
import re
import sys
import time
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import httpx

from mandel.data.deribit_history import _line, _merge_store
from mandel.data.dolt_options import next_session
from mandel.data.fetch import Throttle, now_iso
from mandel.data.options_misc import _archive, _get
from mandel.data.options_misc import _client as _om_client
from mandel.data.store import iso

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
DAY = 86_400
_sleep = time.sleep                                  # patched in tests


def _now_s() -> int:                                 # patched in tests
    return int(time.time())


def _client() -> httpx.Client:                       # patched in tests
    return _om_client(timeout=120)


# ====================================================================================================== helpers ==

def _ts(day: str) -> int:
    return int(datetime.fromisoformat(day[:10]).replace(tzinfo=UTC).timestamp())


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).date().isoformat()


def _iso_z(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _f(x) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _row(source: str, kind: str, key: str, observed_at: str, available_at: str, value: dict) -> dict:
    return {"source": source, "kind": kind, "key": key, "observed_at": observed_at, "available_at": available_at, "value": value}


def _et_iso(day: str, hh: int, mm: int) -> str:
    """``day`` at hh:mm America/New_York, as ISO UTC."""
    d = date.fromisoformat(day)
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC).isoformat()


def _months(first: str, last_s: int) -> list[tuple[str, int, int]]:
    """[(YYYY-MM, month start s, next month start s)] from ``first``'s month through the month holding ``last_s``."""
    d = date.fromisoformat(first[:7] + "-01")
    end = datetime.fromtimestamp(last_s, UTC).date()
    out = []
    while d <= end:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        out.append((d.isoformat()[:7], _ts(d.isoformat()), _ts(nxt.isoformat())))
        d = nxt
    return out


def _stored_complete(archive, name: str) -> bool:
    try:
        return "complete" in (archive.get(name).tags or [])
    except (KeyError, AttributeError):
        return False


def _put(archive, name: str, rows: Iterable[dict], recipe: str, tags: Iterable[str], schema: str, complete: bool):
    """Store a whole bundle, always local disk only; tag ``complete`` or ``partial`` drives skip_stored."""
    tg = sorted(set(tags) | {"crypto", "complete" if complete else "partial"})
    return archive.store(name, kind="data", rows=rows, recipe=recipe, tags=tg, schema=schema, in_git=False)


def _stored_groups(archive, name: str, kind: str, group: Callable[[dict], str], need_complete: bool = False) -> set[str]:
    """Groups (dates, windows) of the stored rows of ``kind`` (one streamed pass; empty when nothing is stored)."""
    out: set[str] = set()
    if archive is None:
        return out
    try:
        archive.get(name)
        for r in archive.load(name):
            if r.get("kind") == kind and (not need_complete or (r.get("value") or {}).get("complete", True)):
                out.add(group(r))
    except (KeyError, FileNotFoundError, OSError, ValueError, AttributeError):
        pass
    return out


def _json(r: httpx.Response, info: dict):
    try:
        return r.json()
    except ValueError:
        info["error"] = "not JSON: " + r.text[:120]
        return None


def _failure(info: dict) -> dict:
    return {k: info[k] for k in ("url", "status", "error", "body", "retry_after", "attempts") if k in info}


# ============================================================================================ licences, families ==

LICENCE = {
    "coinbase": "Coinbase Exchange public market data: Coinbase's terms grant no redistribution right",
    "kraken": "Kraken public market data: Kraken's terms grant no redistribution right",
    "cmc": "CoinMarketCap data-api (undocumented, keyless): CMC's terms forbid redistribution without a licence",
    "coinmetrics": ("Coin Metrics Community data, CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/), attribution "
                    "'Coin Metrics Inc., coinmetrics.io': non-commercial only, not an open redistribution licence"),
    "blockchain": "Blockchain.com charts API: Blockchain.com terms, no open licence",
    "llama": "DefiLlama yields API: no stated redistribution licence for the yields data",
    "ishares": "BlackRock iShares product page: sponsor data under BlackRock's terms of use",
}
LOCAL_ONLY = "The repo is public, so the bundle is local disk only (in_git=False); rebuild it from this recipe."

# (bundle-name pattern, licence key, function, theories, available_at rule)
FAMILIES = [
    ("coinbase-products-*", "coinbase", "fetch_coinbase_products", ["T-424"], "fetch time (dated snapshot)"),
    ("coinbase-daily-*", "coinbase", "fetch_coinbase_daily", ["T-419", "T-330", "T-365", "T-366", "T-424"],
     "bar start + 24 h (daily-history convention)"),
    ("coinbase-hourly-*", "coinbase", "fetch_coinbase_hourly", ["T-424", "T-328", "T-414"], "bar start + 1 h"),
    ("coinbase-1m-*", "coinbase", "fetch_coinbase_1m", ["T-331", "T-425", "T-465", "T-337"], "bar start + 60 s"),
    ("coinbase-trades-1m-*", "coinbase", "fetch_coinbase_trades_1m", ["T-459"], "minute end (trades public at execution)"),
    ("kraken-trades-1m-*", "kraken", "fetch_kraken_trades_1m", ["T-331", "T-425", "T-465", "T-459"],
     "minute end (trades public at execution)"),
    ("kraken-trades-stablecoin-episodes", "kraken", "fetch_kraken_stablecoin_episodes", ["T-330"],
     "trade: execution time; episode-window: day after the signal day"),
    ("cmc-historical-listings", "cmc", "fetch_cmc_weekly_listings", ["T-314", "T-311"], "snapshot date + 1 day (00:00 UTC)"),
    ("cmc-daily-listings-*", "cmc", "fetch_cmc_daily_listings", ["T-420", "T-462", "T-311"], "snapshot date + 1 day (00:00 UTC)"),
    ("cmc-coin-daily-*", "cmc", "fetch_cmc_coin_history", ["T-420", "T-462"], "day end (timeClose)"),
    ("coinmetrics-*-daily", "coinmetrics", "fetch_coinmetrics", ["T-400", "T-402", "T-403"], "day + 1 (current vintage)"),
    ("btc-hashrate-daily", "blockchain", "fetch_btc_hashrate", ["T-403"], "day + 1 (current vintage)"),
    ("defillama-yields", "llama", "fetch_defillama_yields", ["T-367"], "chart timestamp; pool rows: fetch time"),
    ("defillama-yields-pools-*", "llama", "fetch_defillama_yields", ["T-367"], "fetch time (dated snapshot)"),
    ("ishares-ibit-premium-discount", "ishares", "fetch_ishares_ibit", ["T-328"],
     "premium: next NYSE session 09:30 ET; growth-10k: month end + 15 d"),
    ("ishares-ibit-snapshots", "ishares", "fetch_ishares_ibit", ["T-328"], "min(fetch time, next NYSE session 09:30 ET)"),
]
GITIGNORE_LINES = [f"mandel/archive/data/{p}.jsonl.gz" for p, *_ in FAMILIES]


def gitignore_line(name: str) -> Optional[str]:
    """The .gitignore line covering bundle ``name`` (the most specific family pattern that matches)."""
    hits = [(p, f"mandel/archive/data/{p}.jsonl.gz") for p, *_ in FAMILIES if fnmatch(name, p)]
    return max(hits, key=lambda h: len(h[0]))[1] if hits else None


def _family(name: str) -> Optional[tuple]:
    hits = [f for f in FAMILIES if fnmatch(name, f[0])]
    return max(hits, key=lambda f: len(f[0])) if hits else None


def _recipe(core: str, licence: str) -> str:
    return f"{core} Licence: {LICENCE[licence]}. {LOCAL_ONLY}"


# ============================================================================================== estimates ==

PACE = {"coinbase": 0.25, "kraken": 1.0, "cmc": 1.2, "coinmetrics": 0.7, "blockchain": 1.0, "llama": 0.5, "ishares": 2.0}
LATENCY = {"coinbase": 0.2, "kraken": 0.32, "cmc": 0.6, "coinmetrics": 0.6, "blockchain": 0.8, "llama": 1.2, "ishares": 0.9}
# gzip bytes per stored row (compresslevel 9), measured on the 2026-10-15 previews (fetch6c/crypto)
ROW_GZ = {"cb_daily": 28, "cb_hourly": 37, "cb_1m": 33, "kraken_1m": 100, "kraken_trade": 30, "cmc_weekly": 91, "cmc_daily": 104,
          "cm": 40, "hash": 25, "llama_chart": 33, "llama_pool": 148, "ishares": 25, "products": 19, "cmc_coin": 91}
CB_USD_PRODUCTS = 492               # USD-quoted products on 2026-10-15 (online + delisted); dry-run estimate only
CB_DAILY_ROWS_AVG = 1150            # mean daily bars per USD product (listing to delisting); dry-run estimate only
CB_HOURLY_CANDIDATES = 110          # products ever in the top HOURLY_TOP_K, 2019-2026; dry-run estimate only
CB_HOURLY_YEARS_AVG = 3.6           # mean years of hourly history per candidate inside 2019-01 .. now; estimate only
CB_TRADES_PER_DAY = 450_000         # Coinbase BTC-USD trades per day (about 300 a minute on 2026-10-14); estimate only
KRAKEN_TRADES_PER_DAY = {2022: 26_100, 2023: 32_600, 2024: 32_600, 2025: 51_500, 2026: 51_500}   # from trade ids by date
CMC_COINS_OPTIONAL = 300            # coins ever in the top 30 by volume24h (optional per-coin history); estimate only


def _item(name: str, src: str, calls: float, rows: float, row_key: str, pace: Optional[float] = None) -> dict:
    sec = max(PACE[src] if pace is None else pace, LATENCY[src])
    return {"bundle": name, "calls": int(math.ceil(calls)), "rows": int(rows), "gz_mb": round(rows * ROW_GZ[row_key] / 1e6, 2),
            "minutes": round(calls * sec / 60, 1)}


def _total(items: list[dict], **extra) -> dict:
    return {"bundles": len(items), "calls": sum(i["calls"] for i in items), "rows": sum(i["rows"] for i in items),
            "gz_mb": round(sum(i["gz_mb"] for i in items), 1), "minutes": round(sum(i["minutes"] for i in items), 1),
            "per_bundle": items, **extra}


def _setup(store, report, client, min_interval):
    rep = report if report is not None else {}
    own = client is None
    return _archive(store), rep, (client or _client()), own, Throttle(min_interval)


# =========================================================================================== 1. Coinbase ==

CB = "https://api.exchange.coinbase.com"
CB_FIRST_DAY = "2015-07-20"                  # the first BTC-USD daily candle (probe 2026-10-15)
CB_MAX = 300                                 # candles per request
CB_EXTRA_DAILY = ("CBETH-ETH",)              # non-USD products some claims name (T-365, T-366)
CB_PRIORITY = ("BTC-USD", "ETH-USD", "USDT-USD", "CBETH-ETH", "SOL-USD", "DOGE-USD")
CB_ALWAYS_HOURLY = ("BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD")     # T-328 (BTC), T-414 crypto streams, T-424 leader
CB_HOURLY_FIRST = "2019-01-01"               # T-424: fit 2019-22, test 2023-26
CB_1M_FIRST = "2022-01-01"                   # T-331 (2022-01 ..), T-425 / T-465 (2023-01 ..), T-337 (2024-03 ..)
HOURLY_TOP_K = 15                            # T-424's basket is the top 10 alts: fetch the top 15 for margin
RANK_WINDOW_DAYS = 30
# Fiat- and commodity-pegged bases left out of the hourly candidate ranking (Coinbase's fx_stablecoin flag covers most).
# Wrapped and staked tokens (WBTC, CBETH, LSETH, MSOL, ...) stay candidates: excluding them is the harness's declaration.
STABLE_BASES = frozenset({"USDT", "USDC", "DAI", "BUSD", "UST", "TUSD", "PAX", "USDP", "GUSD", "PYUSD", "EURC", "GYEN",
                          "MUSD", "USDS", "USD1", "PAXG", "XAUT", "RAI", "LUSD", "FRAX", "SUSD", "USDE"})
CB_DAILY_SCHEMA = ("value = {symbol (Coinbase product id), t (bar start, unix s), open, high, low, close, volume (base currency)}; "
                   "one row per UTC day with trades (days without trades are absent); observed_at = bar start; available_at = "
                   "bar start + 24 h (the daily-history-<SYM> convention)")
CB_HOURLY_SCHEMA = ("value = {symbol, t (bar start, unix s), open, high, low, close, volume (base currency)}; one row per UTC hour "
                    "with trades (no-trade hours are absent: align to a UTC grid); observed_at = bar start; available_at = bar start + 1 h")
CB_1M_SCHEMA = ("value = {symbol, t (bar start, unix s), open, high, low, close, volume (base currency)}; one row per minute with "
                "trades (a missing minute had no trade: treat as stale); close = last trade in the minute; observed_at = bar start; "
                "available_at = bar start + 60 s")
_KIND = {86400: "price", 3600: "bar1h", 60: "bar1m"}


def cb_products(client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    r, info = _get(client, f"{CB}/products", throttle, retries=retries, backoff=backoff)
    j = _json(r, info) if r is not None else None
    return (j if isinstance(j, list) else None), info


def cb_candles(product: str, start_s: int, end_s: int, granularity: int, client: httpx.Client, throttle: Throttle,
               retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    """One request for buckets [start_s, end_s] (both bucket starts, inclusive; at most 300 buckets)."""
    r, info = _get(client, f"{CB}/products/{product}/candles", throttle,
                   params={"granularity": granularity, "start": _iso_z(start_s), "end": _iso_z(end_s)}, retries=retries, backoff=backoff)
    if r is None:
        return None, info
    j = _json(r, info)
    if not isinstance(j, list):
        info.setdefault("error", str(j)[:200])
        return None, info
    return j, info


def _last_closed(granularity: int, now_s: Optional[int] = None) -> int:
    """Start of the last bar that has closed."""
    n = _now_s() if now_s is None else now_s
    return (n // granularity) * granularity - granularity


def cb_walk(product: str, first_s: int, last_s: int, granularity: int, client: httpx.Client, throttle: Throttle,
            max_calls: Optional[int] = None, retries: int = 4, backoff: float = 1.0) -> tuple[dict[int, list], dict]:
    """{bar start: raw candle} for buckets [first_s, last_s], in windows of 300 buckets."""
    first_s = (first_s // granularity) * granularity
    bars: dict[int, list] = {}
    st: dict = {"calls": 0, "failed": [], "not_found": False, "truncated": False}
    t = first_s
    while t <= last_s:
        if max_calls is not None and st["calls"] >= max_calls:
            st["truncated"] = True
            break
        e = min(t + (CB_MAX - 1) * granularity, last_s)
        rows, info = cb_candles(product, t, e, granularity, client, throttle, retries, backoff)
        st["calls"] += 1
        if rows is None:
            if info.get("status") == 404:
                st["not_found"] = True
                break
            st["failed"].append({"start": _iso_z(t), "end": _iso_z(e), **_failure(info)})
            if info.get("retry_after"):
                st["aborted"] = _failure(info)
                break
        else:
            for b in rows:
                if isinstance(b, (list, tuple)) and len(b) >= 6 and t <= int(b[0]) <= e:
                    bars[int(b[0])] = list(b)
        t = e + granularity
    return bars, st


def cb_row(product: str, b: list, granularity: int) -> dict:
    t = int(b[0])
    return _row("coinbase", _KIND[granularity], product, iso(t), iso(t + granularity),
                {"symbol": product, "t": t, "open": float(b[3]), "high": float(b[2]), "low": float(b[1]),
                 "close": float(b[4]), "volume": float(b[5])})


def _cb_series(archive, name: str, product: str, first_s: int, last_s: int, granularity: int, closed: bool, recipe: str,
               schema: str, tags: list[str], client, th, max_calls, retries, backoff, rep: dict, rows_out: Optional[dict]) -> dict:
    bars, st = cb_walk(product, first_s, last_s, granularity, client, th, max_calls=max_calls, retries=retries, backoff=backoff)
    rows = [cb_row(product, bars[t], granularity) for t in sorted(bars)]
    ok = not st["failed"] and not st["truncated"] and not st.get("aborted")
    info = {"calls": st["calls"], "rows": len(rows), "first": rows[0]["observed_at"][:16] if rows else None,
            "last": rows[-1]["observed_at"][:16] if rows else None, "complete": ok and closed}
    for k in ("failed", "aborted", "not_found", "truncated"):
        if st.get(k):
            info[k] = st[k]
    if rows_out is not None:
        rows_out[name] = rows
    if archive is not None and ok:
        note = " The product answered 404 NotFound (stored empty)." if st["not_found"] else ""
        e = _put(archive, name, rows, recipe + note, tags, schema, complete=closed)
        info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
    elif archive is not None:
        info["not_stored"] = "truncated preview" if st["truncated"] else "a page failed; fetched again on the next run"
    rep[name] = info
    return info


def _stored_products(archive) -> Optional[list[dict]]:
    """The products of the latest stored coinbase-products-<day> snapshot, or None."""
    if archive is None:
        return None
    try:
        names = sorted(e.name for e in archive.entries(kind="data") if e.name.startswith("coinbase-products-"))
    except AttributeError:
        return None
    for n in reversed(names):
        try:
            return [r["value"] for r in archive.load(n)]
        except (KeyError, FileNotFoundError, OSError, ValueError):
            continue
    return None


def daily_products(products: Iterable[dict], extra: Iterable[str] = CB_EXTRA_DAILY) -> list[str]:
    """Every USD-quoted product (online or delisted) plus ``extra``, the claims' named products first."""
    ids = {p["id"] for p in products if p.get("quote_currency") == "USD" and p.get("id")}
    ids |= set(extra)
    pri = [p for p in CB_PRIORITY if p in ids]
    return pri + sorted(ids - set(pri))


def fetch_coinbase_products(store=None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                            day: Optional[str] = None, min_interval: float = PACE["coinbase"], retries: int = 4, backoff: float = 1.0,
                            report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                            **_) -> Optional[list[dict]]:
    """Dated snapshot ``coinbase-products-<day>`` of /products (survivorship record for T-424; listing date = first candle).
    Returns the product list (the stored one when today's snapshot is already stored)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    day = day or _day(_now_s())
    name = f"coinbase-products-{day}"
    try:
        if dry_run:
            rep["_plan_products"] = _total([_item(name, "coinbase", 1, 842, "products")])
            return _stored_products(archive)
        if archive is not None and skip_stored and not refresh and _stored_complete(archive, name):
            rep[name] = {"skipped": "stored complete"}
            return _stored_products(archive)
        prods, info = cb_products(c, th, retries, backoff)
        if prods is None:
            rep[name] = {"error": _failure(info)}
            return _stored_products(archive)
        fetched = now_iso()
        rows = [_row("coinbase", "product", p.get("id", ""), fetched, fetched, p) for p in sorted(prods, key=lambda p: p.get("id", ""))]
        rep[name] = {"calls": 1, "rows": len(rows), "usd": sum(p.get("quote_currency") == "USD" for p in prods),
                     "delisted": sum(p.get("status") == "delisted" for p in prods)}
        if rows_out is not None:
            rows_out[name] = rows
        if archive is not None:
            e = _put(archive, name, rows, _recipe(f"GET {CB}/products on {day} (raw rows; status online/delisted), via "
                                                  "mandel.data.crypto_history.fetch_coinbase_products.", "coinbase"),
                     ["coinbase", "products", "snapshot", day], "value = raw Coinbase product {id, base_currency, quote_currency, status, "
                     "fx_stablecoin, trading_disabled, ...}; observed_at = available_at = fetch time", complete=True)
            rep[name]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return prods
    finally:
        if own:
            c.close()


def fetch_coinbase_daily(store=None, products: Optional[Iterable[str]] = None, first: str = CB_FIRST_DAY, last: Optional[str] = None,
                         limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                         max_calls: Optional[int] = None, min_interval: float = PACE["coinbase"], retries: int = 4,
                         backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                         client: Optional[httpx.Client] = None, product_list: Optional[list[dict]] = None,
                         log: Optional[Callable] = None, **_) -> dict:
    """``coinbase-daily-<PID>``: daily candles first..last (default: the last closed day) for every USD product plus
    CBETH-ETH, or for ``products``. The whole range is scanned for every product (a delisted or halted product's candles
    sit anywhere in it: XRP-USD halted 2021-01 .. 2023-07), 14 requests per product."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        pl = product_list if product_list is not None else _stored_products(archive)
        if products is None and pl is None and not dry_run:
            pl, info = cb_products(c, th, retries, backoff)
            if pl is None:
                rep["_error"] = {"products": _failure(info)}
                return rep
        pids = list(products) if products is not None else (daily_products(pl) if pl is not None else None)
        last_s = min(_ts(last), _last_closed(DAY)) if last else _last_closed(DAY)
        first_s = _ts(first)
        n_days = (last_s - first_s) // DAY + 1
        calls_each = math.ceil(n_days / CB_MAX)
        if pids is None:                                    # dry run without a product list: family estimate
            n = CB_USD_PRODUCTS + len(CB_EXTRA_DAILY)
            rep["_plan"] = _total([_item(f"coinbase-daily-<{n} products>", "coinbase", calls_each * n, CB_DAILY_ROWS_AVG * n, "cb_daily",
                                         min_interval)], note=f"{n} bundles of {calls_each} requests each; product list not known yet")
            return rep
        todo = [p for p in pids if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"coinbase-daily-{p}")]
        rep["_already_stored"] = len(pids) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            rep["_plan"] = _total([_item(f"coinbase-daily-{p}", "coinbase", calls_each,
                                         n_days if p == "BTC-USD" else min(n_days, CB_DAILY_ROWS_AVG), "cb_daily", min_interval) for p in todo])
            return rep
        for i, p in enumerate(todo):
            _cb_series(archive, f"coinbase-daily-{p}", p, first_s, last_s, DAY, True,
                       _recipe(f"GET {CB}/products/{p}/candles?granularity=86400&start=<ISO>&end=<ISO> in windows of 300 days, "
                               f"{_day(first_s)}..{_day(last_s)} (the whole range scanned); via mandel.data.crypto_history.fetch_coinbase_daily.",
                               "coinbase"),
                       CB_DAILY_SCHEMA, ["coinbase", "prices", "daily", "history"], c, th, max_calls, retries, backoff, rep, rows_out)
            if log and (i + 1) % 25 == 0:
                log(f"coinbase daily: {i + 1}/{len(todo)} products")
        return rep
    finally:
        if own:
            c.close()


def load_daily(archive, product: str) -> dict[str, tuple[float, float]]:
    """{day: (close, volume)} from ``coinbase-daily-<product>`` (read only); {} when absent."""
    out = {}
    try:
        for r in archive.load(f"coinbase-daily-{product}"):
            v = r["value"]
            out[_day(v["t"])] = (float(v["close"]), float(v["volume"]))
    except (KeyError, FileNotFoundError, OSError, ValueError, AttributeError, TypeError):
        pass
    return out


def hourly_candidates(daily: dict[str, dict[str, tuple[float, float]]], first: str, last: str, top_k: int = HOURLY_TOP_K,
                      window: int = RANK_WINDOW_DAYS, exclude: frozenset = STABLE_BASES,
                      stable_ids: Iterable[str] = ()) -> dict[str, dict]:
    """Products that rank in the top ``top_k`` by trailing ``window``-day Coinbase dollar volume (sum of close x volume
    over the days d - window + 1 .. d) on any day d in [first - 1, last], among USD products whose base is not in
    ``exclude`` (nor in ``stable_ids``). Any harness top-N (N <= top_k) on the same definition, or on a subset of these
    products, is a subset of the result. Returns {product: {days_in_top, best_rank, first_top, last_top}}."""
    skip = set(stable_ids)
    series = {}
    for pid, d in daily.items():
        base, _, quote = pid.partition("-")
        if quote != "USD" or base in exclude or pid in skip or not d:
            continue
        days = sorted(d)
        pre = [0.0]
        for x in days:
            c, v = d[x]
            pre.append(pre[-1] + c * v)
        series[pid] = (days, pre)
    out: dict[str, dict] = {}
    d0 = date.fromisoformat(first) - timedelta(days=1)
    d1 = date.fromisoformat(last)
    while d0 <= d1:
        hi = d0.isoformat()
        lo = (d0 - timedelta(days=window)).isoformat()
        scores = []
        for pid, (days, pre) in series.items():
            j = bisect_left(days, hi)
            j = j + 1 if j < len(days) and days[j] == hi else j     # days <= hi
            i = bisect_left(days, lo)
            i = i + 1 if i < len(days) and days[i] == lo else i     # days > lo
            s = pre[j] - pre[i]
            if s > 0:
                scores.append((s, pid))
        scores.sort(reverse=True)
        for rank, (_, pid) in enumerate(scores[:top_k], 1):
            o = out.setdefault(pid, {"days_in_top": 0, "best_rank": rank, "first_top": hi, "last_top": hi})
            o["days_in_top"] += 1
            o["best_rank"] = min(o["best_rank"], rank)
            o["last_top"] = hi
        d0 += timedelta(days=1)
    return out


def fetch_coinbase_hourly(store=None, products: Optional[Iterable[str]] = None, first: str = CB_HOURLY_FIRST, last: Optional[str] = None,
                          top_k: int = HOURLY_TOP_K, limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True,
                          refresh: bool = False, max_calls: Optional[int] = None, min_interval: float = PACE["coinbase"],
                          retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                          client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``coinbase-hourly-<PID>``: hourly candles from max(first, the product's first daily bar) to the last closed hour, or
    to its last daily bar + 1 day when that bar is more than 7 days older than the daily bundle (delisted or halted).
    Without ``products``: CB_ALWAYS_HOURLY plus ``hourly_candidates`` computed from the stored coinbase-daily-* bundles
    (fetch those first)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_s = min(_ts(last) + DAY - 3600, _last_closed(3600)) if last else _last_closed(3600)
        last_day = _day(last_s)
        spans: dict[str, tuple[int, int]] = {}
        if products is None:
            daily: dict[str, dict] = {}
            if archive is not None:
                try:
                    names = [e.name for e in archive.entries(kind="data") if e.name.startswith("coinbase-daily-")]
                except AttributeError:
                    names = []
                prods = _stored_products(archive) or []
                stable_ids = {p["id"] for p in prods if p.get("fx_stablecoin")}
                for n in names:
                    pid = n[len("coinbase-daily-"):]
                    daily[pid] = load_daily(archive, pid)
                cand = hourly_candidates(daily, first, last_day, top_k=top_k, stable_ids=stable_ids)
                rep["_candidates"] = {"n": len(cand), "from_daily_bundles": len(daily)}
            else:
                cand = {}
            pids = list(dict.fromkeys(list(CB_ALWAYS_HOURLY) + sorted(cand, key=lambda p: (cand[p]["best_rank"], p))))
            for p in pids:
                d = daily.get(p) or {}
                if d:
                    try:
                        fetched = datetime.fromisoformat(archive.get(f"coinbase-daily-{p}").created_at).timestamp()
                    except (KeyError, AttributeError, ValueError):
                        fetched = _now_s()
                    trading = _ts(max(d)) >= fetched - 7 * DAY      # still trading when the daily bundle was fetched
                    spans[p] = (max(_ts(first), _ts(min(d))), last_s if trading else min(last_s, _ts(max(d)) + DAY - 3600))
        else:
            pids = list(products)
        family_estimate = products is None and archive is None or (products is None and not spans and dry_run)
        todo = [p for p in pids if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"coinbase-hourly-{p}")]
        rep["_already_stored"] = len(pids) - len(todo)
        if limit is not None:
            todo = todo[:limit]

        def span(p):
            return spans.get(p, (_ts(first), last_s))
        if dry_run:
            items = []
            for p in todo:
                a, b = span(p)
                hrs = max(0, (b - a) // 3600 + 1)
                items.append(_item(f"coinbase-hourly-{p}", "coinbase", math.ceil(hrs / CB_MAX), hrs * 0.97, "cb_hourly", min_interval))
            extra = {}
            if family_estimate:
                hrs = CB_HOURLY_CANDIDATES * CB_HOURLY_YEARS_AVG * 8766
                items.append(_item(f"coinbase-hourly-<about {CB_HOURLY_CANDIDATES} candidates>", "coinbase", hrs / CB_MAX, hrs * 0.9,
                                   "cb_hourly", min_interval))
                extra["note"] = ("candidates come from the coinbase-daily-* bundles (fetch those first); the family line is an "
                                 "estimate, the always-fetched products are listed separately")
            rep["_plan"] = _total(items, **extra)
            return rep
        for i, p in enumerate(todo):
            a, b = span(p)
            if b < a:
                rep[f"coinbase-hourly-{p}"] = {"skipped": "no daily bars inside the hourly window"}
                continue
            _cb_series(archive, f"coinbase-hourly-{p}", p, a, b, 3600, True,
                       _recipe(f"GET {CB}/products/{p}/candles?granularity=3600&start=<ISO>&end=<ISO> in windows of 300 hours, "
                               f"{_iso_z(a)}..{_iso_z(b)}; candidates = {', '.join(CB_ALWAYS_HOURLY)} plus every USD product in the top "
                               f"{top_k} by trailing {RANK_WINDOW_DAYS}-day dollar volume (coinbase-daily-*, stablecoins excluded) on any "
                               f"day from {first}; via mandel.data.crypto_history.fetch_coinbase_hourly.", "coinbase"),
                       CB_HOURLY_SCHEMA, ["coinbase", "prices", "hourly", "history"], c, th, max_calls, retries, backoff, rep, rows_out)
            if log and (i + 1) % 10 == 0:
                log(f"coinbase hourly: {i + 1}/{len(todo)} products")
        return rep
    finally:
        if own:
            c.close()


def fetch_coinbase_1m(store=None, product: str = "BTC-USD", first: str = CB_1M_FIRST, last: Optional[str] = None,
                      limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                      max_calls: Optional[int] = None, min_interval: float = PACE["coinbase"], retries: int = 4, backoff: float = 1.0,
                      report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                      log: Optional[Callable] = None, **_) -> dict:
    """``coinbase-1m-<PID>-<YYYY-MM>``: 1-minute candles, one bundle per UTC month, first .. the last closed minute."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_s = min(_ts(last) + DAY - 60, _last_closed(60)) if last else _last_closed(60)
        months = _months(first, last_s)
        todo = [m for m in months if refresh or not skip_stored or archive is None
                or not _stored_complete(archive, f"coinbase-1m-{product}-{m[0]}")]
        rep["_already_stored"] = len(months) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for ym, a, b in todo:
                mins = (min(b - 60, last_s) - max(a, _ts(first))) // 60 + 1
                items.append(_item(f"coinbase-1m-{product}-{ym}", "coinbase", math.ceil(mins / CB_MAX), mins * 0.995, "cb_1m", min_interval))
            rep["_plan"] = _total(items)
            return rep
        for ym, a, b in todo:
            end = min(b - 60, last_s)
            _cb_series(archive, f"coinbase-1m-{product}-{ym}", product, max(a, _ts(first)), end, 60, b - 60 <= last_s,
                       _recipe(f"GET {CB}/products/{product}/candles?granularity=60&start=<ISO>&end=<ISO> in windows of 300 minutes "
                               f"over {ym} (UTC); via mandel.data.crypto_history.fetch_coinbase_1m.", "coinbase"),
                       CB_1M_SCHEMA, ["coinbase", "prices", "1m", "history", ym], c, th, max_calls, retries, backoff, rep, rows_out)
            if log:
                log(f"coinbase 1m {product} {ym}: {rep[f'coinbase-1m-{product}-{ym}'].get('rows')} bars")
        return rep
    finally:
        if own:
            c.close()


# --------------------------------------------------------------------- 1-minute bars from trades (shared) --

class MinuteAgg:
    """1-minute bars from trades in any order: OHLC by (time, trade id), volume and VWAP, exact aggressor-side volume
    (``side`` 'b' = buyer-initiated, 's' = seller-initiated), per-side price extremes (a later sell at or below a bid
    proves a resting bid would have filled), market-order volume and, in minute ``mark_minute`` of each hour, every trade."""

    def __init__(self, symbol: str, mark_minute: Optional[int] = 59):
        self.symbol, self.mark, self.m = symbol, mark_minute, {}

    def add(self, ts: float, price: float, vol: float, side: str, ordertype: Optional[str] = None, tid: Optional[int] = None) -> None:
        t = int(ts // 60) * 60
        key = (ts, tid if tid is not None else 0)
        a = self.m.get(t)
        if a is None:
            a = self.m[t] = {"o": price, "ok": key, "c": price, "ck": key, "h": price, "l": price, "v": 0.0, "pv": 0.0, "n": 0,
                             "vb": 0.0, "vs": 0.0, "nb": 0, "ns": 0, "bh": None, "bl": None, "sh": None, "sl": None,
                             "vm": 0.0 if ordertype is not None else None, "lid": tid, "ticks": [] if self.mark is not None and (t // 60) % 60 == self.mark else None}
        if key < a["ok"]:
            a["o"], a["ok"] = price, key
        if key > a["ck"]:
            a["c"], a["ck"] = price, key
        a["h"], a["l"] = max(a["h"], price), min(a["l"], price)
        a["v"] += vol
        a["pv"] += price * vol
        a["n"] += 1
        if side == "b":
            a["vb"] += vol; a["nb"] += 1
            a["bh"] = price if a["bh"] is None else max(a["bh"], price)
            a["bl"] = price if a["bl"] is None else min(a["bl"], price)
        else:
            a["vs"] += vol; a["ns"] += 1
            a["sh"] = price if a["sh"] is None else max(a["sh"], price)
            a["sl"] = price if a["sl"] is None else min(a["sl"], price)
        if ordertype == "m" and a["vm"] is not None:
            a["vm"] += vol
        if tid is not None and (a["lid"] is None or tid > a["lid"]):
            a["lid"] = tid
        if a["ticks"] is not None:
            a["ticks"].append([ts, price, vol, side, ordertype, tid])

    def __len__(self) -> int:
        return len(self.m)

    def rows(self, source: str) -> list[dict]:
        out = []
        for t in sorted(self.m):
            a = self.m[t]
            v = {"symbol": self.symbol, "t": t, "open": a["o"], "high": a["h"], "low": a["l"], "close": a["c"],
                 "volume": round(a["v"], 10), "vwap": round(a["pv"] / a["v"], 10) if a["v"] > 0 else None, "n": a["n"],
                 "buy_vol": round(a["vb"], 10), "sell_vol": round(a["vs"], 10), "n_buy": a["nb"], "n_sell": a["ns"],
                 "buy_hi": a["bh"], "buy_lo": a["bl"], "sell_hi": a["sh"], "sell_lo": a["sl"],
                 "mkt_vol": None if a["vm"] is None else round(a["vm"], 10), "first_ts": a["ok"][0], "last_ts": a["ck"][0], "last_id": a["lid"]}
            if a["ticks"] is not None:
                v["ticks"] = sorted(a["ticks"], key=lambda x: (x[0], x[5] or 0))
            out.append(_row(source, "bar1m", self.symbol, iso(t), iso(t + 60), v))
        return out


TRADE_1M_SCHEMA = ("value = {symbol, t (minute start, unix s), open, high, low, close (first / last trade by time and id), volume, vwap, "
                   "n, buy_vol, sell_vol, n_buy, n_sell (aggressor side: buy = buyer-initiated), buy_hi, buy_lo, sell_hi, sell_lo (price "
                   "range of each side's prints), mkt_vol (market-order volume; None when the venue does not say), first_ts, last_ts "
                   "(unix s, fractional), last_id, ticks (minute HH:59 only: every trade [time, price, volume, side b/s, ordertype m/l, "
                   "trade_id], so the last trade at or before an hour mark minus s seconds is exact)}; minutes without trades are absent; "
                   "observed_at = minute start; available_at = minute end")


# -------------------------------------------------------------------- Coinbase trades (optional, T-459) --

def cb_trades_page(product: str, after: Optional[int], client: httpx.Client, throttle: Throttle, limit: int = 1000,
                   retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    """Trades with trade_id < ``after`` (newest first), or the latest trades when ``after`` is None."""
    params = {"limit": limit}
    if after is not None:
        params["after"] = after
    r, info = _get(client, f"{CB}/products/{product}/trades", throttle, params=params, retries=retries, backoff=backoff)
    j = _json(r, info) if r is not None else None
    return (j if isinstance(j, list) else None), info


def _cb_trade_time(t: dict) -> float:
    return datetime.fromisoformat(t["time"].replace("Z", "+00:00")).timestamp()


def cb_trade_id_at(product: str, ts: float, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 1.0,
                   st: Optional[dict] = None) -> Optional[int]:
    """The id of the first trade at or after ``ts`` (bisection over trade ids, one 1-trade call per step)."""
    st = st if st is not None else {}
    st.setdefault("calls", 0)
    head, _ = cb_trades_page(product, None, client, throttle, limit=1, retries=retries, backoff=backoff)
    st["calls"] += 1
    if not head:
        return None
    lo, hi = 1, int(head[0]["trade_id"])
    if _cb_trade_time(head[0]) < ts:
        return hi + 1
    for _ in range(64):                      # invariant: every trade id < lo is before ts, trade hi is at or after ts
        if lo >= hi:
            break
        mid = (lo + hi) // 2
        page, _ = cb_trades_page(product, mid + 1, client, throttle, limit=1, retries=retries, backoff=backoff)
        st["calls"] += 1
        if not page:
            return None
        if _cb_trade_time(page[0]) < ts:      # the newest trade with id <= mid is before ts, so all ids <= mid are
            lo = mid + 1
        else:
            hi = max(lo, int(page[0]["trade_id"]))
    return lo


def fetch_coinbase_trades_1m(store=None, product: str = "BTC-USD", first: str = "2025-01-01", last: str = "2025-01-31",
                             limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                             max_calls: Optional[int] = None, min_interval: float = PACE["coinbase"], retries: int = 4,
                             backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                             client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """Optional (T-459 cross-venue replication): ``coinbase-trades-1m-<PID>-<YYYY-MM>``, Coinbase trades over
    [first, last] aggregated with ``MinuteAgg`` (aggressor = the opposite of Coinbase's maker ``side``). A full 2023-26
    pull is about 700k pages, so the default is one month."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_s = min(_ts(last) + DAY, _last_closed(60) + 60)
        months = [m for m in _months(first, last_s - 1)]
        todo = [m for m in months if refresh or not skip_stored or archive is None
                or not _stored_complete(archive, f"coinbase-trades-1m-{product}-{m[0]}")]
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for ym, a, b in todo:
                days = (min(b, last_s) - max(a, _ts(first))) / DAY
                items.append(_item(f"coinbase-trades-1m-{product}-{ym}", "coinbase", days * CB_TRADES_PER_DAY / 1000 + 60,
                                   days * 1440, "kraken_1m", min_interval))
            rep["_plan"] = _total(items, note="optional source; trades per day is a 2025 estimate")
            return rep
        for ym, ms, me in todo:
            name = f"coinbase-trades-1m-{product}-{ym}"
            a, b = max(ms, _ts(first)), min(me, last_s)
            closed = me <= last_s
            st: dict = {"calls": 0}
            agg = MinuteAgg(product)
            stop_id = cb_trade_id_at(product, a, c, th, retries, backoff, st)
            end_id = cb_trade_id_at(product, b, c, th, retries, backoff, st)
            ok, truncated = stop_id is not None and end_id is not None, False
            cursor = end_id
            while ok and cursor is not None and cursor > stop_id:
                if max_calls is not None and st["calls"] >= max_calls:
                    truncated = True
                    break
                page, info = cb_trades_page(product, cursor, c, th, retries=retries, backoff=backoff)
                st["calls"] += 1
                if page is None:
                    ok = False
                    st["error"] = _failure(info)
                    break
                if not page:
                    break
                for t in page:
                    tid = int(t["trade_id"])
                    if tid < stop_id:
                        continue
                    ts = _cb_trade_time(t)
                    if a <= ts < b:
                        agg.add(ts, float(t["price"]), float(t["size"]), "s" if t.get("side") == "buy" else "b", None, tid)
                cursor = min(int(t["trade_id"]) for t in page)
            rows = agg.rows("coinbase")
            info = {"calls": st["calls"], "rows": len(rows), "complete": ok and not truncated and closed}
            if st.get("error"):
                info["error"] = st["error"]
            if rows_out is not None:
                rows_out[name] = rows
            if archive is not None and ok and not truncated:
                e = _put(archive, name, rows, _recipe(f"GET {CB}/products/{product}/trades?limit=1000&after=<trade_id>, paged backward from "
                                                      f"the first trade at or after {_iso_z(b)} to the first at or after {_iso_z(a)} "
                                                      "(ids found by bisection); aggressor side = opposite of the maker side; aggregated "
                                                      "with mandel.data.crypto_history.MinuteAgg via fetch_coinbase_trades_1m.", "coinbase"),
                         ["coinbase", "trades", "1m", "signed-volume", ym], TRADE_1M_SCHEMA, complete=closed)
                info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            rep[name] = info
        return rep
    finally:
        if own:
            c.close()


# ============================================================================================= 2. Kraken ==

KRAKEN = "https://api.kraken.com/0/public"
KRAKEN_1M_FIRST = "2022-01-01"
KRAKEN_COUNT = 1000
_KRAKEN_RETRY = ("too many requests", "rate limit", "eservice:unavailable", "eservice:busy", "eapi:rate")


def _kraken_retryable(err: Iterable[str]) -> bool:
    return any(any(k in str(e).lower() for k in _KRAKEN_RETRY) for e in err)


def kraken_trades_page(pair: str, since_ns: int, client: httpx.Client, throttle: Throttle, count: int = KRAKEN_COUNT,
                       retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], Optional[int], dict]:
    """(trades, last cursor ns, info). Kraken's JSON errors (HTTP 200) are retried when they are rate or service errors."""
    info: dict = {}
    for attempt in range(retries):
        r, info = _get(client, f"{KRAKEN}/Trades", throttle, params={"pair": pair, "since": since_ns, "count": count},
                       retries=retries, backoff=backoff)
        if r is None:
            return None, None, info
        j = _json(r, info)
        if not isinstance(j, dict):
            return None, None, info
        err = j.get("error") or []
        if err:
            info["error"] = err
            if _kraken_retryable(err) and attempt < retries - 1:
                _sleep(max(3.0, backoff * 3 * 2 ** attempt))
                continue
            return None, None, info
        res = j.get("result") or {}
        keys = [k for k in res if k != "last"]
        try:
            last = int(res.get("last"))
        except (TypeError, ValueError):
            info["error"] = "no 'last' cursor"
            return None, None, info
        return (res[keys[0]] if keys else []), last, info
    return None, None, info


def kraken_walk(pair: str, start_ns: int, end_ns: int, client: httpx.Client, throttle: Throttle, sink: Callable[[list], None],
                max_calls: Optional[int] = None, retries: int = 4, backoff: float = 1.0, now_ns: Optional[int] = None) -> dict:
    """Page Trades from ``start_ns`` until a trade at or after ``end_ns`` (complete) or the head of the tape; trades in
    [start_ns, end_ns) go to ``sink`` page by page, de-duplicated by trade id. Reaching the head counts as complete only
    when ``end_ns`` is in the past (nothing traded between the last trade and the window end)."""
    now_ns = (_now_s() * 10**9) if now_ns is None else now_ns
    st = {"calls": 0, "trades": 0, "complete": False, "caught_up": False, "truncated": False}
    since, max_id = start_ns, -1
    while True:
        if max_calls is not None and st["calls"] >= max_calls:
            st["truncated"] = True
            break
        trades, last, info = kraken_trades_page(pair, since, client, throttle, retries=retries, backoff=backoff)
        st["calls"] += 1
        if trades is None:
            st["error"] = _failure(info)
            break
        batch, done = [], False
        for tr in trades:
            ts_ns = int(round(float(tr[2]) * 1e9))
            tid = int(tr[6]) if len(tr) > 6 and tr[6] is not None else None
            if tid is not None:
                if tid <= max_id:
                    continue
                max_id = tid
            if ts_ns >= end_ns:
                done = True
                break
            if ts_ns >= start_ns:
                batch.append(tr)
        if batch:
            sink(batch)
            st["trades"] += len(batch)
        if done:
            st["complete"] = True
            break
        if not trades or last is None or last <= since:
            st["caught_up"] = True
            st["complete"] = end_ns <= now_ns - 120 * 10**9
            break
        since = last
    return st


def _kraken_add(agg: MinuteAgg, batch: list) -> None:
    for tr in batch:
        agg.add(float(tr[2]), float(tr[0]), float(tr[1]), tr[3], tr[4] if len(tr) > 4 else None,
                int(tr[6]) if len(tr) > 6 and tr[6] is not None else None)


def fetch_kraken_trades_1m(store=None, pair: str = "XBTUSD", first: str = KRAKEN_1M_FIRST, last: Optional[str] = None,
                           limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                           max_calls: Optional[int] = None, min_interval: float = PACE["kraken"], retries: int = 4, backoff: float = 1.0,
                           report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                           log: Optional[Callable] = None, **_) -> dict:
    """``kraken-trades-1m-<PAIR>-<YYYY-MM>``: Kraken public trades paged by ``since`` (ns) over each UTC month, rebuilt into
    1-minute bars with exact aggressor-side volume (``MinuteAgg``). About 67k pages for XBTUSD 2022-01 .. 2026-10 at about
    1 page/s: run it last, it resumes month by month."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        now = _now_s()
        last_s = min(_ts(last) + DAY, now) if last else now
        months = _months(first, last_s - 1)
        todo = [m for m in months if refresh or not skip_stored or archive is None
                or not _stored_complete(archive, f"kraken-trades-1m-{pair}-{m[0]}")]
        rep["_already_stored"] = len(months) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            items = []
            for ym, a, b in todo:
                days = (min(b, last_s) - max(a, _ts(first))) / DAY
                tpd = KRAKEN_TRADES_PER_DAY.get(int(ym[:4]), 51_500)
                items.append(_item(f"kraken-trades-1m-{pair}-{ym}", "kraken", days * tpd / KRAKEN_COUNT + 1, days * 1440 * 0.995,
                                   "kraken_1m", min_interval))
            rep["_plan"] = _total(items, note="trades per day from XBTUSD trade ids at 2022-01-01, 2023-01-01, 2025-01-01, 2026-10-15")
            return rep
        for ym, ms, me in todo:
            name = f"kraken-trades-1m-{pair}-{ym}"
            a, b = max(ms, _ts(first)), min(me, last_s)
            agg = MinuteAgg(pair)
            st = kraken_walk(pair, a * 10**9, b * 10**9, c, th, lambda batch, agg=agg: _kraken_add(agg, batch),
                             max_calls=max_calls, retries=retries, backoff=backoff, now_ns=now * 10**9)
            rows = agg.rows("kraken")
            closed = me <= last_s and st["complete"]
            info = {"calls": st["calls"], "trades": st["trades"], "rows": len(rows), "complete": closed}
            for k in ("error", "truncated", "caught_up"):
                if st.get(k):
                    info[k] = st[k]
            if rows_out is not None:
                rows_out[name] = rows
            if archive is not None and not st.get("error") and not st["truncated"]:
                e = _put(archive, name, rows, _recipe(f"GET {KRAKEN}/Trades?pair={pair}&since=<ns cursor, from {_iso_z(a)}>&count=1000, "
                                                      f"paged on result.last until a trade at or after {_iso_z(b)}; trades de-duplicated by "
                                                      "trade id and aggregated with mandel.data.crypto_history.MinuteAgg via "
                                                      "fetch_kraken_trades_1m (Kraken's OHLC endpoint keeps only 720 bars, so history comes "
                                                      "from Trades).", "kraken"),
                         ["kraken", "trades", "1m", "signed-volume", ym], TRADE_1M_SCHEMA, complete=closed)
                info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            elif archive is not None:
                info["not_stored"] = "truncated preview" if st["truncated"] else "paging failed; fetched again on the next run"
            rep[name] = info
            if log:
                log(f"kraken {pair} {ym}: {st['calls']} pages, {st['trades']} trades, {len(rows)} minutes")
            if st.get("error") and (st["error"].get("retry_after") or st["error"].get("status") in (403, 429)):
                rep["_aborted"] = {"month": ym, **st["error"]}
                break
        return rep
    finally:
        if own:
            c.close()


# Stablecoin discount episodes of T-330 (the library rule on Yahoo daily closes: first close below 0.995 after at least
# 5 consecutive closes at or above 0.998), as recomputed in the batch-6c triage recheck on 2026-10-15.
EPISODES = [("USDT", "USDTZUSD", "2017-11-29"), ("USDT", "USDTZUSD", "2018-03-19"), ("USDT", "USDTZUSD", "2018-06-02"),
            ("USDT", "USDTZUSD", "2018-09-21"), ("USDT", "USDTZUSD", "2019-04-25"), ("USDT", "USDTZUSD", "2019-08-21"),
            ("USDT", "USDTZUSD", "2019-12-17"), ("USDT", "USDTZUSD", "2020-04-06"), ("USDT", "USDTZUSD", "2020-06-19"),
            ("USDC", "USDCUSD", "2020-03-17"), ("USDC", "USDCUSD", "2020-04-23"), ("USDC", "USDCUSD", "2023-03-11")]
EPISODE_PAIRS = {"USDT": "USDTZUSD", "USDC": "USDCUSD"}
EPISODE_BUNDLE = "kraken-trades-stablecoin-episodes"
EPISODE_TRADES_PER_DAY = {"USDT": 2000, "USDC": 1900}         # 2018 / 2020 probes (1,000 trades per 12-13 h); estimate only
EPISODE_SCHEMA = ("kind trade: value = {coin, pair, signal_day, price, volume, time (unix s), side (b = buyer-initiated), ordertype, "
                  "misc, trade_id}; available_at = execution time | kind episode-window: value = {coin, pair, signal_day, start, end, "
                  "trades, pages, complete, pre_window (signal before 2018), source ('triage' = frozen list, 'detected' = the rule on "
                  "the archived Yahoo closes)}; available_at = the day after the signal day 00:00 UTC (the signal close is known then). "
                  "Rebuild the 00:00 UTC executable closes from the last trade before each midnight")


def peg_episodes(closes: dict[str, float], below: float = 0.995, at_or_above: float = 0.998, run: int = 5) -> list[str]:
    """Signal days: the first close below ``below`` after at least ``run`` consecutive closes >= ``at_or_above``."""
    out, streak = [], 0
    for d in sorted(closes):
        x = closes[d]
        if x < below and streak >= run:
            out.append(d)
        streak = streak + 1 if x >= at_or_above else 0
    return out


def _yahoo_closes(archive, sym: str) -> dict[str, float]:
    out = {}
    try:
        for r in archive.load(f"daily-history-{sym}"):
            v = r.get("value") or {}
            if v.get("t") is not None and _f(v.get("close")):
                out[_day(v["t"])] = float(v["close"])
    except (KeyError, FileNotFoundError, OSError, ValueError, AttributeError):
        pass
    return out


def episode_windows(archive=None, episodes: Optional[Iterable[tuple]] = None, before_days: int = 1, after_days: int = 6,
                    detect: bool = True) -> list[dict]:
    """The frozen ``EPISODES`` (or ``episodes``) plus, when the archive holds daily-history-USDT-USD / USDC-USD, the
    episodes the rule finds there. Window = [signal day - before_days, signal day + after_days + 1) UTC days."""
    eps = {(c, d): {"coin": c, "pair": p, "signal_day": d, "source": "triage"} for c, p, d in (episodes or EPISODES)}
    if detect and archive is not None:
        for coin, pair in EPISODE_PAIRS.items():
            for d in peg_episodes(_yahoo_closes(archive, f"{coin}-USD")):
                eps.setdefault((coin, d), {"coin": coin, "pair": pair, "signal_day": d, "source": "detected"})
    out = []
    for (coin, d), e in sorted(eps.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        s = _ts(d) - before_days * DAY
        out.append({**e, "start_s": s, "end_s": _ts(d) + (after_days + 1) * DAY, "pre_window": d < "2018-01-01"})
    return out


def fetch_kraken_stablecoin_episodes(store=None, episodes: Optional[Iterable[tuple]] = None, before_days: int = 1, after_days: int = 6,
                                     limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                                     max_calls: Optional[int] = None, min_interval: float = PACE["kraken"], retries: int = 4,
                                     backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                                     client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``kraken-trades-stablecoin-episodes`` (T-330): raw Kraken trades of USDTZUSD / USDCUSD in each episode window,
    merged window by window into one bundle (complete windows only)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        wins = episode_windows(archive, episodes, before_days, after_days)
        group = lambda r: f"{r['value']['coin']}:{r['value']['signal_day']}"
        have = _stored_groups(archive, EPISODE_BUNDLE, "episode-window", group, need_complete=True) if (skip_stored and not refresh) else set()
        todo = [w for w in wins if f"{w['coin']}:{w['signal_day']}" not in have]
        rep["_already_stored"] = len(wins) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            calls = sum(math.ceil((w["end_s"] - w["start_s"]) / DAY * EPISODE_TRADES_PER_DAY[w["coin"]] / KRAKEN_COUNT) + 1 for w in todo)
            rows = sum((w["end_s"] - w["start_s"]) / DAY * EPISODE_TRADES_PER_DAY[w["coin"]] for w in todo)
            rep["_plan"] = _total([_item(EPISODE_BUNDLE, "kraken", calls, rows, "kraken_trade", min_interval)],
                                  windows=[f"{w['coin']}:{w['signal_day']}" for w in todo],
                                  note="2023-03-11 (USDC, SVB) trades far more than the estimate: about 30-60 extra pages")
            return rep
        fresh, done = [], set()
        for w in todo:
            key = f"{w['coin']}:{w['signal_day']}"
            got: list = []
            st = kraken_walk(w["pair"], w["start_s"] * 10**9, w["end_s"] * 10**9, c, th, got.extend, max_calls=max_calls,
                             retries=retries, backoff=backoff)
            obs = now_iso()
            for tr in got:
                ts = float(tr[2])
                tid = int(tr[6]) if len(tr) > 6 and tr[6] is not None else None
                fresh.append(_row("kraken", "trade", f"{w['pair']}:{tid if tid is not None else ts}", iso(ts), iso(ts),
                                  {"coin": w["coin"], "pair": w["pair"], "signal_day": w["signal_day"], "price": float(tr[0]),
                                   "volume": float(tr[1]), "time": ts, "side": tr[3], "ordertype": tr[4] if len(tr) > 4 else None,
                                   "misc": tr[5] if len(tr) > 5 else None, "trade_id": tid}))
            fresh.append(_row("kraken", "episode-window", key, obs, iso(_ts(w["signal_day"]) + DAY),
                              {"coin": w["coin"], "pair": w["pair"], "signal_day": w["signal_day"], "start": iso(w["start_s"]),
                               "end": iso(w["end_s"]), "trades": len(got), "pages": st["calls"], "complete": st["complete"],
                               "pre_window": w["pre_window"], "source": w["source"]}))
            rep[key] = {"pages": st["calls"], "trades": len(got), "complete": st["complete"], **({"error": st["error"]} if st.get("error") else {})}
            if st["complete"]:
                done.add(key)
            if log:
                log(f"kraken episode {key}: {st['calls']} pages, {len(got)} trades")
        mine = [r for r in fresh if group(r) in done]
        if rows_out is not None:
            rows_out[EPISODE_BUNDLE] = fresh
        if archive is not None and done:
            e = _merge_store(archive, EPISODE_BUNDLE, sorted(mine, key=_episode_sort), done, group, _episode_sort,
                             _recipe(f"GET {KRAKEN}/Trades?pair=<USDTZUSD|USDCUSD>&since=<ns>&count=1000 paged on result.last over each "
                                     f"window [signal day - {before_days} d, signal day + {after_days + 1} d) UTC of "
                                     "mandel.data.crypto_history.EPISODES (plus episodes detected on archived Yahoo closes), via "
                                     "fetch_kraken_stablecoin_episodes; complete windows only.", "kraken"),
                             ["crypto", "kraken", "trades", "stablecoin", "events", "T-330"], EPISODE_SCHEMA)
            rep["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git, "windows": sorted(done)}
        return rep
    finally:
        if own:
            c.close()


def _episode_sort(r: dict) -> tuple:
    v = r["value"]
    return (v["signal_day"], v["coin"], r["kind"] != "episode-window", v.get("time") or 0.0, v.get("trade_id") or 0)


# ======================================================================================== 3. CoinMarketCap ==

CMC_LISTINGS = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listings/historical"
CMC_COIN = "https://api.coinmarketcap.com/data-api/v3.1/cryptocurrency/historical"
CMC_USD = 2781
CMC_WEEKLY_BUNDLE = "cmc-historical-listings"
CMC_WEEKLY_FIRST = "2017-12-03"                  # T-314: every Sunday (formation) and Monday (execution) from 2017-12-03
CMC_WEEKLY_LIMIT = 500
CMC_DAILY_FIRST = "2017-11-01"                   # T-420 / T-462: 30 days of volume before the first 2017-12 formation
CMC_DAILY_LIMIT = 200
CMC_CHUNK = 60                                   # snapshot dates per merge
CMC_COIN_FIRST = "2017-11-01"
CMC_COIN_DAYS = 400                              # the v3.1 historical route returns at most the latest 400 days of a range
_CMC_FLAG = re.compile(r"stablecoin|wrapped|tokeni[sz]ed|pegged|bridged|liquid-staking|restaking", re.I)
CMC_SCHEMA = ("kind listing: value = {date (snapshot day), id, symbol, slug, name, cmcRank, price, volume24h, marketCap (USD), "
              "circulatingSupply, totalSupply, maxSupply, percentChange24h, percentChange7d, dateAdded, lastUpdated, platform (the "
              "token's chain, or None), flags (CMC tags marking stablecoins, wrapped, tokenized, staked or bridged assets)}; dead coins "
              "included (point-in-time ranking); price = the day's close (it equals CMC's daily OHLC close for the date; lastUpdated "
              "reads 23:59 UTC in 2017-2019 snapshots and 00:00 of the date in 2026 ones, a label quirk); observed_at = the date 23:59:59 "
              "UTC; available_at = the next day 00:00 UTC | kind snapshot: value = {date, n, limit}, one per date. CMC prices are cross-exchange VWAPs, "
              "volume24h includes wash trades, and CMC can revise history: near point in time, not vintage-stamped")


def cmc_listing(day: str, limit: int, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    r, info = _get(client, CMC_LISTINGS, throttle, params={"date": day, "start": 1, "limit": limit, "convertId": CMC_USD},
                   retries=retries, backoff=backoff)
    j = _json(r, info) if r is not None else None
    if not isinstance(j, dict):
        return None, info
    status = j.get("status") or {}
    if str(status.get("error_code", "0")) != "0" or not isinstance(j.get("data"), list):
        info["error"] = f"{status.get('error_code')}: {status.get('error_message')}"
        return None, info
    return j["data"], info


def cmc_rows(day: str, coins: list[dict], limit: int) -> list[dict]:
    avail = iso(_ts(day) + DAY)
    out = []
    for x in coins:
        q = next((q for q in (x.get("quotes") or []) if str(q.get("name")) == str(CMC_USD)), None) or ((x.get("quotes") or [None])[0]) or {}
        plat = x.get("platform")
        v = {"date": day, "id": x.get("id"), "symbol": x.get("symbol"), "slug": x.get("slug"), "name": x.get("name"),
             "cmcRank": x.get("cmcRank"), "price": _f(q.get("price")), "volume24h": _f(q.get("volume24h")),
             "marketCap": _f(q.get("marketCap")), "circulatingSupply": _f(x.get("circulatingSupply")),
             "totalSupply": _f(x.get("totalSupply")), "maxSupply": _f(x.get("maxSupply")),
             "percentChange24h": _f(q.get("percentChange24h")), "percentChange7d": _f(q.get("percentChange7d")),
             "dateAdded": x.get("dateAdded"), "lastUpdated": x.get("lastUpdated"),
             "platform": (plat.get("name") or plat.get("symbol")) if isinstance(plat, dict) else plat,
             "flags": sorted(t for t in (x.get("tags") or []) if isinstance(t, str) and _CMC_FLAG.search(t))}
        out.append(_row("coinmarketcap", "listing", f"{day}:{x.get('id')}", f"{day}T23:59:59+00:00", avail, v))
    out.append(_row("coinmarketcap", "snapshot", day, f"{day}T23:59:59+00:00", avail, {"date": day, "n": len(coins), "limit": limit}))
    return out


def _cmc_sort(r: dict) -> tuple:
    v = r["value"]
    return (v["date"], r["kind"] != "snapshot", v.get("cmcRank") or 10**9, v.get("id") or 0)


def _cmc_group(r: dict) -> str:
    return r["value"]["date"]


def weekly_days(first: str, last: str) -> list[str]:
    d, e, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= e:
        if d.weekday() in (6, 0):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _all_days(first: str, last: str) -> list[str]:
    d, e, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= e:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _cmc_snapshot_bundle(archive, name: str, days: list[str], depth: int, recipe: str, tags: list[str], c, th, retries, backoff,
                         rep: dict, rows_out: Optional[dict], log, abort_after: int = 5) -> dict:
    fresh, done, info = [], set(), {"dates": 0, "calls": 0, "failed": []}
    fails = 0

    def flush():
        nonlocal fresh, done
        if archive is not None and done:
            e = _merge_store(archive, name, sorted(fresh, key=_cmc_sort), set(done), _cmc_group, _cmc_sort, recipe, tags, CMC_SCHEMA)
            info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        if rows_out is not None:
            rows_out.setdefault(name, []).extend(fresh)
        fresh, done = [], set()

    try:
        for d in days:
            coins, ci = cmc_listing(d, depth, c, th, retries, backoff)
            info["calls"] += 1
            if coins is None:
                info["failed"].append({"date": d, **_failure(ci)})
                fails += 1
                if fails >= abort_after or ci.get("retry_after"):
                    info["aborted"] = f"{fails} consecutive failures"
                    break
                continue
            fails = 0
            fresh.extend(cmc_rows(d, coins, depth))
            done.add(d)
            info["dates"] += 1
            if len(done) >= CMC_CHUNK:
                flush()
                if log:
                    log(f"{name}: {info['dates']}/{len(days)} dates")
    finally:
        flush()
    rep[name] = info
    return info


def fetch_cmc_weekly_listings(store=None, first: str = CMC_WEEKLY_FIRST, last: Optional[str] = None, depth: int = CMC_WEEKLY_LIMIT,
                              limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                              max_calls: Optional[int] = None, min_interval: float = PACE["cmc"], retries: int = 4, backoff: float = 2.0,
                              report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                              log: Optional[Callable] = None, **_) -> dict:
    """``cmc-historical-listings`` (T-314's declared bundle): the top ``depth`` coins of every Sunday and Monday snapshot
    first .. last (default yesterday), merged into one bundle every CMC_CHUNK dates; stored dates are skipped."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last = last or _day(_now_s() - DAY)
        days = weekly_days(first, last)
        have = _stored_groups(archive, CMC_WEEKLY_BUNDLE, "snapshot", _cmc_group) if (skip_stored and not refresh) else set()
        todo = [d for d in days if d not in have]
        rep["_already_stored"] = len(days) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if max_calls is not None:
            todo = todo[:max_calls]
        if dry_run:
            rep["_plan"] = _total([_item(CMC_WEEKLY_BUNDLE, "cmc", len(todo), len(todo) * (depth + 1), "cmc_weekly", min_interval)],
                                  dates=len(todo), first=todo[0] if todo else None, last=todo[-1] if todo else None)
            return rep
        _cmc_snapshot_bundle(archive, CMC_WEEKLY_BUNDLE, todo, depth,
                             _recipe(f"GET {CMC_LISTINGS}?date=<YYYY-MM-DD>&start=1&limit={depth}&convertId={CMC_USD} for every Sunday and "
                                     f"Monday from {first} (keyless data-api), merged by date via mandel.data.crypto_history."
                                     "fetch_cmc_weekly_listings.", "cmc"),
                             ["crypto", "coinmarketcap", "listings", "point-in-time", "weekly", "T-314"], c, th, retries, backoff, rep,
                             rows_out, log)
        return rep
    finally:
        if own:
            c.close()


def fetch_cmc_daily_listings(store=None, first: str = CMC_DAILY_FIRST, last: Optional[str] = None, depth: int = CMC_DAILY_LIMIT,
                             limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                             max_calls: Optional[int] = None, min_interval: float = PACE["cmc"], retries: int = 4, backoff: float = 2.0,
                             report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                             log: Optional[Callable] = None, **_) -> dict:
    """``cmc-daily-listings-<YYYY>``: the top ``depth`` coins of every daily snapshot first .. last (default yesterday), one
    bundle per year (T-420 / T-462: trailing 30-day dollar volume and month-end prices of a point-in-time universe)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last = last or _day(_now_s() - DAY)
        by_year: dict[str, list[str]] = {}
        for d in _all_days(first, last):
            by_year.setdefault(d[:4], []).append(d)
        plan, left = [], limit
        work = []
        for y, days in sorted(by_year.items()):
            name = f"cmc-daily-listings-{y}"
            have = _stored_groups(archive, name, "snapshot", _cmc_group) if (skip_stored and not refresh) else set()
            todo = [d for d in days if d not in have]
            if left is not None:
                todo = todo[:left]
                left -= len(todo)
            if max_calls is not None:
                todo = todo[:max_calls]
            if todo:
                work.append((name, todo))
                plan.append(_item(name, "cmc", len(todo), len(todo) * (depth + 1), "cmc_daily", min_interval))
        if dry_run:
            rep["_plan"] = _total(plan)
            return rep
        for name, todo in work:
            _cmc_snapshot_bundle(archive, name, todo, depth,
                                 _recipe(f"GET {CMC_LISTINGS}?date=<YYYY-MM-DD>&start=1&limit={depth}&convertId={CMC_USD} for every day of "
                                         f"{name[-4:]} from {first} (keyless data-api), merged by date via mandel.data.crypto_history."
                                         "fetch_cmc_daily_listings.", "cmc"),
                                 ["crypto", "coinmarketcap", "listings", "point-in-time", "daily", "T-420", "T-462"], c, th, retries,
                                 backoff, rep, rows_out, log)
            if (rep.get(name) or {}).get("aborted"):
                rep["_aborted"] = name
                break
        return rep
    finally:
        if own:
            c.close()


def cmc_candidate_ids(archive, top: int = 30) -> list[int]:
    """Coins that rank in the top ``top`` by volume24h on any stored daily or weekly snapshot."""
    best: dict[int, int] = {}
    try:
        names = [e.name for e in archive.entries(kind="data") if e.name.startswith("cmc-daily-listings-") or e.name == CMC_WEEKLY_BUNDLE]
    except AttributeError:
        return []
    for n in names:
        by_day: dict[str, list] = {}
        for r in archive.load(n):
            if r.get("kind") == "listing":
                v = r["value"]
                by_day.setdefault(v["date"], []).append((v.get("volume24h") or 0.0, v.get("id")))
        for xs in by_day.values():
            for rank, (_, cid) in enumerate(sorted(xs, reverse=True)[:top], 1):
                best[cid] = min(best.get(cid, rank), rank)
    return sorted(best, key=lambda k: (best[k], k))


def fetch_cmc_coin_history(store=None, ids: Optional[Iterable[int]] = None, first: str = CMC_COIN_FIRST, last: Optional[str] = None,
                           limit: Optional[int] = None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                           max_calls: Optional[int] = None, min_interval: float = PACE["cmc"], retries: int = 4, backoff: float = 2.0,
                           report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                           log: Optional[Callable] = None, **_) -> dict:
    """Optional: ``cmc-coin-daily-<id>`` per-coin daily OHLCV (v3.1 historical, paged backward 400 days at a time) for
    ``ids`` or ``cmc_candidate_ids`` of the stored listings. Some dead coins return nothing; the listings cover them."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        last_s = min(_ts(last) + DAY - 1, _last_closed(DAY) + DAY - 1) if last else _last_closed(DAY) + DAY - 1
        first_s = _ts(first)
        cids = list(ids) if ids is not None else (cmc_candidate_ids(archive) if archive is not None else [])
        todo = [i for i in cids if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"cmc-coin-daily-{i}")]
        if limit is not None:
            todo = todo[:limit]
        calls_each = math.ceil((last_s - first_s) / DAY / CMC_COIN_DAYS)
        if dry_run:
            n = len(todo) if (ids is not None or archive is not None and cids) else CMC_COINS_OPTIONAL
            rep["_plan"] = _total([_item(f"cmc-coin-daily-<{n} coins>", "cmc", n * calls_each, n * 1500, "cmc_coin", min_interval)],
                                  note="optional; candidate ids come from the stored listings")
            return rep
        for cid in todo:
            name = f"cmc-coin-daily-{cid}"
            quotes, st, end, meta = {}, {"calls": 0}, last_s, {}
            ok, truncated = True, False
            while end > first_s:
                if max_calls is not None and st["calls"] >= max_calls:
                    truncated = True
                    break
                r, info = _get(c, CMC_COIN, th, params={"id": cid, "convertId": CMC_USD, "timeStart": first_s, "timeEnd": end,
                                                        "interval": "daily"}, retries=retries, backoff=backoff)
                st["calls"] += 1
                j = _json(r, info) if r is not None else None
                if not isinstance(j, dict) or str((j.get("status") or {}).get("error_code", "0")) != "0":
                    ok = False
                    st["error"] = _failure(info)
                    break
                data = j.get("data") or {}
                meta = {k: data.get(k) for k in ("id", "name", "symbol")}
                qs = data.get("quotes") or []
                if not qs:
                    break
                for q in qs:
                    quotes[q["timeOpen"][:10]] = q
                earliest = min(_ts(q["timeOpen"][:10]) for q in qs)
                if len(qs) < CMC_COIN_DAYS or earliest <= first_s or earliest - 1 >= end:
                    break                                   # a short page: the range start or the coin's first day
                end = earliest - 1
            rows = []
            for d in sorted(quotes):
                q = quotes[d]
                qq = q.get("quote") or {}
                rows.append(_row("coinmarketcap", "ohlcv", f"{cid}:{d}", f"{d}T00:00:00+00:00", iso(_ts(d) + DAY),
                                 {"id": cid, "symbol": meta.get("symbol"), "name": meta.get("name"), "day": d, "open": _f(qq.get("open")),
                                  "high": _f(qq.get("high")), "low": _f(qq.get("low")), "close": _f(qq.get("close")),
                                  "volume": _f(qq.get("volume")), "marketCap": _f(qq.get("marketCap")),
                                  "circulatingSupply": _f(qq.get("circulatingSupply")), "timeHigh": q.get("timeHigh"), "timeLow": q.get("timeLow")}))
            rep[name] = {"calls": st["calls"], "rows": len(rows), **({"error": st["error"]} if st.get("error") else {})}
            if rows_out is not None:
                rows_out[name] = rows
            if archive is not None and ok and not truncated:
                e = _put(archive, name, rows, _recipe(f"GET {CMC_COIN}?id={cid}&convertId={CMC_USD}&timeStart=<s>&timeEnd=<s>&interval=daily, "
                                                      f"paged backward {CMC_COIN_DAYS} days at a time from {_iso_z(last_s)} to {first}; via "
                                                      "mandel.data.crypto_history.fetch_cmc_coin_history.", "cmc"),
                         ["coinmarketcap", "ohlcv", "daily", "history"], "value = {id, symbol, name, day, open, high, low, close, volume, "
                         "marketCap, circulatingSupply, timeHigh, timeLow} (USD, CMC cross-exchange VWAP); observed_at = day 00:00 UTC; "
                         "available_at = day end (next day 00:00 UTC); empty for some dead coins", complete=True)
                rep[name]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return rep
    finally:
        if own:
            c.close()


# ========================================================================================= 4. CoinMetrics ==

CM = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
CM_FIRST = "2010-07-01"
CM_ASSETS = {
    "btc": ["PriceUSD", "CapMVRVCur", "HashRate", "CapMrktCurUSD", "SplyCur"],     # T-400, T-402 (SSR), T-403
    "eth": ["PriceUSD", "CapMVRVCur", "CapMrktCurUSD", "SplyCur"],                 # T-400 ETH variant
    "usdt": ["SplyCur", "PriceUSD"], "usdc": ["SplyCur", "PriceUSD"], "dai": ["SplyCur", "PriceUSD"],
    "busd": ["SplyCur", "PriceUSD"], "tusd": ["SplyCur", "PriceUSD"],              # T-402 (aggregate assets only, no per-chain)
}
CM_ROWS = {"btc": 5950, "eth": 4090}          # daily rows per asset (dry-run estimate; stablecoins about 2,900)


def cm_fetch(asset: str, metrics: list[str], start: str, client: httpx.Client, throttle: Throttle, page_size: int = 10000,
             max_calls: Optional[int] = None, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    """Every page of one asset-metrics request (paging_from=start, following next_page_url)."""
    url, params = CM, {"assets": asset, "metrics": ",".join(metrics), "frequency": "1d", "start_time": start, "page_size": page_size,
                       "paging_from": "start", "ignore_unsupported_errors": "true"}
    data, st = [], {"calls": 0}
    while True:
        if max_calls is not None and st["calls"] >= max_calls:
            st["truncated"] = True
            break
        r, info = _get(client, url, throttle, params=params, retries=retries, backoff=backoff)
        st["calls"] += 1
        j = _json(r, info) if r is not None else None
        if not isinstance(j, dict):
            st["error"] = _failure(info)
            return None, st
        data.extend(j.get("data") or [])
        nxt = j.get("next_page_url")
        if not nxt:
            break
        url, params = nxt, None
    return data, st


def fetch_coinmetrics(store=None, assets: Optional[dict[str, list[str]]] = None, first: str = CM_FIRST, limit: Optional[int] = None,
                      dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                      min_interval: float = PACE["coinmetrics"], retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None,
                      rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, log: Optional[Callable] = None, **_) -> dict:
    """``coinmetrics-<asset>-daily``: Coin Metrics community daily metrics per asset (all of an asset's metrics in one
    bundle). A 403 (a metric the community tier refuses) falls back to one request per metric."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        assets = assets or CM_ASSETS
        todo = [a for a in assets if refresh or not skip_stored or archive is None or not _stored_complete(archive, f"coinmetrics-{a}-daily")]
        if limit is not None:
            todo = todo[:limit]
        if dry_run:
            rep["_plan"] = _total([_item(f"coinmetrics-{a}-daily", "coinmetrics", 1, CM_ROWS.get(a, 2900), "cm", min_interval) for a in todo])
            return rep
        for a in todo:
            name = f"coinmetrics-{a}-daily"
            data, st = cm_fetch(a, assets[a], first, c, th, max_calls=max_calls, retries=retries, backoff=backoff)
            forbidden, calls = [], st["calls"]
            if data is None and (st.get("error") or {}).get("status") == 403:
                data = []
                for m in assets[a]:
                    d1, s1 = cm_fetch(a, [m], first, c, th, max_calls=max_calls, retries=retries, backoff=backoff)
                    calls += s1["calls"]
                    if d1 is None:
                        forbidden.append(m)
                    else:
                        data.extend(d1)
                    st["truncated"] = st.get("truncated") or s1.get("truncated")
                st.pop("error", None)
            if data is None:
                rep[name] = {"calls": calls, "error": st.get("error")}
                continue
            by_day: dict[str, dict] = {}
            for x in data:
                d = str(x.get("time", ""))[:10]
                if not d:
                    continue
                v = by_day.setdefault(d, {"asset": a, "day": d})
                for m in assets[a]:
                    if m in x and _f(x[m]) is not None:
                        v[m] = _f(x[m])
            rows = [_row("coinmetrics", "metric", f"{a}:{d}", f"{d}T00:00:00+00:00", iso(_ts(d) + DAY), by_day[d]) for d in sorted(by_day)]
            seen = sorted({m for v in by_day.values() for m in v if m not in ("asset", "day")})
            rep[name] = {"calls": calls, "rows": len(rows), "metrics": seen, "forbidden": forbidden,
                         "first": rows[0]["value"]["day"] if rows else None, "last": rows[-1]["value"]["day"] if rows else None}
            if rows_out is not None:
                rows_out[name] = rows
            if archive is not None and not st.get("truncated"):
                fetched = now_iso()
                e = _put(archive, name, rows, _recipe(f"GET {CM}?assets={a}&metrics={','.join(assets[a])}&frequency=1d&start_time={first}"
                                                      "&page_size=10000&paging_from=start&ignore_unsupported_errors=true, following "
                                                      f"next_page_url (one request per metric after a 403); fetched {fetched} (current "
                                                      "vintage: Coin Metrics recomputes realised cap and hash rate without vintages); via "
                                                      "mandel.data.crypto_history.fetch_coinmetrics.", "coinmetrics"),
                         ["coinmetrics", "onchain", "daily", "history", "cc-by-nc-4.0"],
                         f"value = {{asset, day, {', '.join(assets[a])} (floats; a metric absent on a day is left out)}}; observed_at = day "
                         "00:00 UTC; available_at = day + 1 (the metric covers the UTC day); current vintage, not point-in-time vintages"
                         + (f"; forbidden on the community tier: {', '.join(forbidden)}" if forbidden else ""), complete=True)
                rep[name]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return rep
    finally:
        if own:
            c.close()


# ===================================================================================== 5. blockchain.info ==

BCI_HASHRATE = "https://api.blockchain.info/charts/hash-rate"
HASH_BUNDLE = "btc-hashrate-daily"


def fetch_btc_hashrate(store=None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                       min_interval: float = PACE["blockchain"], retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None,
                       rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, limit: Optional[int] = None, **_) -> dict:
    """``btc-hashrate-daily`` (T-403): blockchain.info daily hash-rate estimate, the whole history in one request."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        skip = archive is not None and skip_stored and not refresh and _stored_complete(archive, HASH_BUNDLE)
        if dry_run:
            rep["_plan"] = _total([] if skip or limit == 0 else [_item(HASH_BUNDLE, "blockchain", 1, 6500, "hash", min_interval)])
            return rep
        if skip or limit == 0:
            rep[HASH_BUNDLE] = {"skipped": "stored complete"} if skip else {"skipped": "limit 0"}
            return rep
        r, info = _get(c, BCI_HASHRATE, th, params={"timespan": "all", "format": "json", "sampled": "false"}, retries=retries, backoff=backoff)
        j = _json(r, info) if r is not None else None
        if not isinstance(j, dict) or not isinstance(j.get("values"), list):
            rep[HASH_BUNDLE] = {"error": _failure(info)}
            return rep
        rows = []
        for p in j["values"]:
            if p.get("x") is None or _f(p.get("y")) is None:
                continue
            x = int(p["x"])
            rows.append(_row("blockchain.info", "hashrate", _day(x), iso(x), iso(x + DAY), {"day": _day(x), "t": x, "hash_rate_ths": _f(p["y"])}))
        rows.sort(key=lambda r: r["value"]["t"])
        rep[HASH_BUNDLE] = {"calls": 1, "rows": len(rows), "unit": j.get("unit"), "first": rows[0]["value"]["day"] if rows else None,
                            "last": rows[-1]["value"]["day"] if rows else None}
        if rows_out is not None:
            rows_out[HASH_BUNDLE] = rows
        if archive is not None:
            e = _put(archive, HASH_BUNDLE, rows, _recipe(f"GET {BCI_HASHRATE}?timespan=all&format=json&sampled=false (one request; fetched "
                                                         f"{now_iso()}); via mandel.data.crypto_history.fetch_btc_hashrate.", "blockchain"),
                     ["blockchain.info", "onchain", "hashrate", "daily", "history"],
                     f"value = {{day, t (day start, unix s), hash_rate_ths ({j.get('unit')}; an estimate from difficulty and block "
                     "counts, recomputed without vintages)}; observed_at = day start; available_at = day + 1", complete=True)
            rep[HASH_BUNDLE]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return rep
    finally:
        if own:
            c.close()


# ========================================================================================== 6. DefiLlama ==

LLAMA = "https://yields.llama.fi"
LLAMA_BUNDLE = "defillama-yields"
# Pre-registered Ethereum USDC lending pools of T-367 (pool ids from the 2026-10-15 /pools snapshot)
LLAMA_POOLS = {
    "aa70268e-4b52-42bf-a116-608b370f9501": "aave-v3 USDC (Ethereum)",
    "c5c74dd1-995c-4445-9d84-3e710bad7d52": "spark-savings USDC (Ethereum)",
    "43641cf5-a92e-416b-bce9-27113d3c0db6": "maple syrupUSDC (Ethereum)",
    "65ce8276-b4d9-41ba-9f6f-21fc374cf9bc": "sparklend USDC (Ethereum; the alternative 'Spark' the pre-registration must choose between)",
}
LLAMA_CHART_ROWS = {"aa70268e-4b52-42bf-a116-608b370f9501": 1350, "c5c74dd1-995c-4445-9d84-3e710bad7d52": 290,
                    "43641cf5-a92e-416b-bce9-27113d3c0db6": 450}


def _llama_ts(s: str) -> str:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC).isoformat()


def fetch_defillama_yields(store=None, pools: Optional[dict[str, str]] = None, day: Optional[str] = None, dry_run: bool = False,
                           skip_stored: bool = True, refresh: bool = False, min_interval: float = PACE["llama"], retries: int = 4,
                           backoff: float = 1.0, report: Optional[dict] = None, rows_out: Optional[dict] = None,
                           client: Optional[httpx.Client] = None, limit: Optional[int] = None, max_calls: Optional[int] = None, **_) -> dict:
    """``defillama-yields-pools-<day>`` (the dated /pools snapshot) and ``defillama-yields`` (the /chart history of each
    pre-registered pool plus that pool's snapshot row)."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        pools = pools or LLAMA_POOLS
        day = day or _day(_now_s())
        snap = f"defillama-yields-pools-{day}"
        skip_snap = archive is not None and skip_stored and not refresh and _stored_complete(archive, snap)
        skip_chart = archive is not None and skip_stored and not refresh and _stored_complete(archive, LLAMA_BUNDLE)
        if dry_run:
            items = ([] if skip_snap else [_item(snap, "llama", 1, 16800, "llama_pool", min_interval)])
            items += [] if skip_chart else [_item(LLAMA_BUNDLE, "llama", len(pools), sum(LLAMA_CHART_ROWS.get(p, 400) for p in pools) + len(pools),
                                                  "llama_chart", min_interval)]
            rep["_plan"] = _total(items)
            return rep
        if limit == 0:
            return rep
        meta: dict[str, dict] = {}
        fetched = now_iso()
        if skip_snap:
            rep[snap] = {"skipped": "stored complete"}
            for r in archive.load(snap):
                if r["key"] in pools:
                    meta[r["key"]] = r["value"]
        else:
            r, info = _get(c, f"{LLAMA}/pools", th, retries=retries, backoff=backoff)
            j = _json(r, info) if r is not None else None
            if not isinstance(j, dict) or not isinstance(j.get("data"), list):
                rep[snap] = {"error": _failure(info)}
            else:
                rows = [_row("defillama", "pool", str(p.get("pool")), fetched, fetched, p) for p in sorted(j["data"], key=lambda p: str(p.get("pool")))]
                meta = {p["pool"]: p for p in j["data"] if p.get("pool") in pools}
                rep[snap] = {"calls": 1, "rows": len(rows)}
                if rows_out is not None:
                    rows_out[snap] = rows
                if archive is not None:
                    e = _put(archive, snap, rows, _recipe(f"GET {LLAMA}/pools on {day} (raw rows; frozen to fix the pool ids: dead pools are "
                                                          "absent, a survivorship caveat); via mandel.data.crypto_history.fetch_defillama_yields.",
                                                          "llama"),
                             ["defillama", "yields", "pools", "snapshot", day], "value = raw DefiLlama pool {pool, chain, project, symbol, "
                             "tvlUsd, apyBase, apyReward, apy, stablecoin, ilRisk, exposure, poolMeta, underlyingTokens, apyMean30d, ...}; "
                             "observed_at = available_at = fetch time", complete=True)
                    rep[snap]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        if skip_chart:
            rep[LLAMA_BUNDLE] = {"skipped": "stored complete"}
            return rep
        rows, ok, calls = [], True, 0
        for pid, label in pools.items():
            if max_calls is not None and calls >= max_calls:
                ok = False
                break
            r, info = _get(c, f"{LLAMA}/chart/{pid}", th, retries=retries, backoff=backoff)
            calls += 1
            j = _json(r, info) if r is not None else None
            if not isinstance(j, dict) or not isinstance(j.get("data"), list):
                ok = False
                rep[f"{LLAMA_BUNDLE}:{pid}"] = {"error": _failure(info)}
                continue
            m = meta.get(pid, {})
            for x in j["data"]:
                if not x.get("timestamp"):
                    continue
                ts = _llama_ts(x["timestamp"])
                rows.append(_row("defillama", "chart", f"{pid}:{ts[:10]}", ts, ts,
                                 {"pool": pid, "label": label, "project": m.get("project"), "chain": m.get("chain"), "symbol": m.get("symbol"),
                                  "timestamp": ts, **{k: x.get(k) for k in ("tvlUsd", "apy", "apyBase", "apyReward", "il7d", "apyBase7d",
                                                                             "pricePerShare")}}))
            if m:
                rows.append(_row("defillama", "pool", pid, fetched, fetched, {**m, "label": label}))
        rows.sort(key=lambda r: (r["value"].get("pool", r["key"]), r["kind"] != "pool", r["observed_at"]))
        rep[LLAMA_BUNDLE] = {"calls": calls, "rows": len(rows), "complete": ok}
        if rows_out is not None:
            rows_out[LLAMA_BUNDLE] = rows
        if archive is not None and ok:
            e = _put(archive, LLAMA_BUNDLE, rows, _recipe(f"GET {LLAMA}/chart/<pool> for the pre-registered pools "
                                                          f"{', '.join(f'{k} ({v})' for k, v in pools.items())}, plus each pool's row of the "
                                                          f"{snap} snapshot; via mandel.data.crypto_history.fetch_defillama_yields.", "llama"),
                     ["defillama", "yields", "carry", "stablecoin", "T-367"],
                     "kind chart: value = {pool, label, project, chain, symbol, timestamp, tvlUsd, apy, apyBase, apyReward, il7d, apyBase7d, "
                     "pricePerShare} (APY in percent; one point a day, about 23:01 UTC); observed_at = available_at = timestamp | kind pool: "
                     "the pool's snapshot row; observed_at = available_at = fetch time", complete=True)
            rep[LLAMA_BUNDLE]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return rep
    finally:
        if own:
            c.close()


# ============================================================================================= 7. iShares ==

ISHARES_IBIT = "https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf"
ISH_PREMIUM = "ishares-ibit-premium-discount"
ISH_SNAP = "ishares-ibit-snapshots"
ISH_BASKET_SHARES = 40_000


def _ish_obj(text: str, name: str, need: Optional[str] = None) -> Optional[dict]:
    """The first JSON object ``"name": {...}`` in the (unescaped) page that holds key ``need``."""
    dec = json.JSONDecoder()
    for mt in re.finditer(r'"' + re.escape(name) + r'"\s*:\s*\{', text):
        try:
            obj, _ = dec.raw_decode(text, mt.end() - 1)
        except ValueError:
            continue
        if isinstance(obj, dict) and (need is None or need in obj):
            return obj
    return None


def _ish_date(s) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    for fmt in ("%b %d, %Y", "%a, %b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _num(s) -> Optional[float]:
    if s is None:
        return None
    return _f(re.sub(r"[^0-9.\-]", "", str(s)) or None)


def parse_ishares(page: str) -> dict:
    """{premium: [(day, pct)], growth: [(month_end, nav_growth, benchmark_growth)], snapshot: {...}} from the product page."""
    t = html.unescape(page)
    out: dict = {"premium": [], "growth": [], "snapshot": {}}
    pd = _ish_obj(t, "premiumDiscountChartData", "asOfDate")
    if pd and isinstance(pd.get("asOfDate"), list):
        for d, v in zip(pd["asOfDate"], pd.get("value") or []):
            day, x = _ish_date(d), _f(v)
            if day and x is not None:
                out["premium"].append((day, x))
    perf, bench = _ish_obj(t, "performanceData", "asOfDate"), _ish_obj(t, "benchmarkData", "asOfDate")
    if perf and isinstance(perf.get("asOfDate"), list):
        bmap = {}
        if bench and isinstance(bench.get("asOfDate"), list):
            bmap = {_ish_date(d): _f(v) for d, v in zip(bench["asOfDate"], bench.get("value") or [])}
        for d, v in zip(perf["asOfDate"], perf.get("value") or []):
            day = _ish_date(d)
            if day and _f(v) is not None:
                out["growth"].append((day, _f(v), bmap.get(day)))
    snap = out["snapshot"]
    nav = _ish_obj(t, "navAmount", "value")
    if nav:
        snap["nav"], snap["nav_as_of"] = _f(nav.get("value")), _ish_date(nav.get("asOfDate")) or _ish_date(nav.get("formattedAsOfDate"))
    for key, field in (("closingPrice", "closing_price"), ("sharesOutstanding", "shares_outstanding"),
                       ("premiumDiscountClosingPriceNavPercent", "premium_discount_pct"), ("basketAmt", "basket_btc"),
                       ("BasketBitcoinAmount", "basket_amount_usd")):
        o = _ish_obj(t, key, "formattedValue")
        if o:
            snap[field] = _num(o.get("formattedValue"))
            snap[field + "_as_of"] = _ish_date(o.get("formattedAsOfDate"))
            if key == "BasketBitcoinAmount":
                m = re.search(r"\(([\d,]+)\)", str(o.get("infoBubble") or ""))
                snap["basket_shares"] = int(m.group(1).replace(",", "")) if m else ISH_BASKET_SHARES
    if snap.get("basket_btc"):
        snap["btc_per_share"] = snap["basket_btc"] / (snap.get("basket_shares") or ISH_BASKET_SHARES)
    return out


def _ish_avail(day: str) -> str:
    """09:30 America/New_York on the NYSE session after ``day``."""
    return _et_iso(next_session(day), 9, 30)


def fetch_ishares_ibit(store=None, dry_run: bool = False, skip_stored: bool = True, refresh: bool = False,
                       min_interval: float = PACE["ishares"], retries: int = 4, backoff: float = 2.0, report: Optional[dict] = None,
                       rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None, limit: Optional[int] = None, **_) -> dict:
    """``ishares-ibit-premium-discount`` (daily official premium/discount, month-end growth of $10k) and
    ``ishares-ibit-snapshots`` (NAV, closing price, shares outstanding, basket bitcoin amount -> bitcoin per share), merged
    into the stored bundles by day, so a daily run accumulates history. One request; skipped when today's fetch is stored."""
    archive, rep, c, own, th = _setup(store, report, client, min_interval)
    try:
        today = _day(_now_s())
        have = _stored_groups(archive, ISH_SNAP, "snapshot", lambda r: r["value"].get("fetched_day", "")) if (skip_stored and not refresh) else set()
        skip = today in have
        if dry_run:
            rep["_plan"] = _total([] if skip else [_item(ISH_PREMIUM, "ishares", 1, 480, "ishares", min_interval),
                                                   _item(ISH_SNAP, "ishares", 0, 1, "ishares", min_interval)])
            return rep
        if skip or limit == 0:
            rep[ISH_SNAP] = {"skipped": f"fetched today ({today})"} if skip else {"skipped": "limit 0"}
            return rep
        r, info = _get(c, ISHARES_IBIT, th, retries=retries, backoff=backoff)
        if r is None:
            rep[ISH_PREMIUM] = {"error": _failure(info)}
            return rep
        p = parse_ishares(r.text)
        fetched = now_iso()
        prem = [_row("ishares", "premium-discount", d, _et_iso(d, 16, 0), _ish_avail(d),
                     {"day": d, "premium_discount_pct": x, "basis": "closing price vs NAV, percent of NAV (premiumDiscountChartData)"})
                for d, x in p["premium"]]
        prem += [_row("ishares", "growth-10k", m, _et_iso(m, 16, 0), _et_iso((date.fromisoformat(m) + timedelta(days=15)).isoformat(), 9, 30),
                      {"month_end": m, "growth_10k_nav": g, "growth_10k_benchmark": b}) for m, g, b in p["growth"]]
        s = p["snapshot"]
        snaps = []
        if s.get("nav_as_of"):
            snaps.append(_row("ishares", "snapshot", s["nav_as_of"], _et_iso(s["nav_as_of"], 16, 0),
                              min(_ish_avail(s["nav_as_of"]), fetched, key=lambda x: datetime.fromisoformat(x)),
                              {**s, "fetched_at": fetched, "fetched_day": today}))
        rep[ISH_PREMIUM] = {"calls": 1, "rows": len(prem), "premium_days": len(p["premium"]), "growth_months": len(p["growth"]),
                            "first": p["premium"][0][0] if p["premium"] else None, "last": p["premium"][-1][0] if p["premium"] else None}
        rep[ISH_SNAP] = {"rows": len(snaps), "snapshot": s}
        if rows_out is not None:
            rows_out[ISH_PREMIUM], rows_out[ISH_SNAP] = prem, snaps
        if archive is not None:
            grp = lambda r: f"{r['kind']}:{r['key']}"
            srt = lambda r: (r["kind"], r["key"])
            if prem:
                e = _merge_store(archive, ISH_PREMIUM, sorted(prem, key=srt), {grp(r) for r in prem}, grp, srt,
                                 _recipe(f"GET {ISHARES_IBIT} (HTML; JSON HTML-escaped): premiumDiscountChartData (previous year + YTD, "
                                         "official closing-price premium/discount to NAV) and performanceData/benchmarkData (month-end growth "
                                         "of $10,000), merged by day with earlier fetches via mandel.data.crypto_history.fetch_ishares_ibit. "
                                         "The historical NAV xls and holdings CSV answer the HTML page (no NAV history download).", "ishares"),
                                 ["crypto", "ishares", "ibit", "etf", "premium", "nav", "T-328"],
                                 "kind premium-discount: value = {day, premium_discount_pct (closing price / NAV - 1, percent), basis}; NAV = "
                                 "close / (1 + pct/100) with daily-history-IBIT; observed_at = day 16:00 ET; available_at = 09:30 ET on the next "
                                 "NYSE session | kind growth-10k: value = {month_end, growth_10k_nav, growth_10k_benchmark} (NAV total return "
                                 "since 2023-12-31; month-end NAV(m) = NAV(m0) x g(m) / g(m0)); available_at = month end + 15 days 09:30 ET")
                rep[ISH_PREMIUM]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            if snaps:
                e = _merge_store(archive, ISH_SNAP, snaps, {grp(r) for r in snaps}, grp, srt,
                                 _recipe(f"GET {ISHARES_IBIT}: fund header and key facts (navAmount, closingPrice, sharesOutstanding, "
                                         "premiumDiscountClosingPriceNavPercent, basketAmt = Basket Bitcoin Amount per 40,000-share basket, "
                                         "BasketBitcoinAmount = basket USD), one row per NAV date, merged via "
                                         "mandel.data.crypto_history.fetch_ishares_ibit.", "ishares"),
                                 ["crypto", "ishares", "ibit", "etf", "nav", "snapshot", "T-328"],
                                 "value = {nav, nav_as_of, closing_price, shares_outstanding, premium_discount_pct, basket_btc, basket_amount_usd, "
                                 "basket_shares, btc_per_share (= basket_btc / basket_shares, the published bitcoin per share), *_as_of, "
                                 "fetched_at, fetched_day}; observed_at = nav_as_of 16:00 ET; available_at = min(fetch time, 09:30 ET on the "
                                 "next NYSE session)")
                rep[ISH_SNAP]["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
        return rep
    finally:
        if own:
            c.close()


# ============================================================================================== fetch_all ==

SOURCES = {
    "coinbase_products": fetch_coinbase_products,
    "coinbase_daily": fetch_coinbase_daily,
    "coinbase_hourly": fetch_coinbase_hourly,
    "coinbase_1m": fetch_coinbase_1m,
    "kraken_episodes": fetch_kraken_stablecoin_episodes,
    "coinmetrics": fetch_coinmetrics,
    "btc_hashrate": fetch_btc_hashrate,
    "defillama": fetch_defillama_yields,
    "ishares": fetch_ishares_ibit,
    "cmc_weekly": fetch_cmc_weekly_listings,
    "cmc_daily": fetch_cmc_daily_listings,
    "kraken_1m": fetch_kraken_trades_1m,
    "cmc_coins": fetch_cmc_coin_history,                 # optional
    "coinbase_trades": fetch_coinbase_trades_1m,         # optional
}
DEFAULT_SOURCES = ("coinbase_products", "coinbase_daily", "coinbase_hourly", "coinbase_1m", "kraken_episodes", "coinmetrics",
                   "btc_hashrate", "defillama", "ishares", "cmc_weekly", "cmc_daily", "kraken_1m")
OPTIONAL_SOURCES = ("cmc_coins", "coinbase_trades")


def fetch_all_crypto(store, dry_run: bool = False, limit: Optional[int] = None, sources: Optional[Iterable[str]] = None,
                     include_optional: bool = False, max_calls: Optional[int] = None, refresh: bool = False,
                     report: Optional[dict] = None, rows_out: Optional[dict] = None, log: Optional[Callable] = None,
                     min_interval: Optional[float] = None) -> dict:
    """Run every crypto fetcher in order (cheap and dependency-first, the ~19-hour Kraken paging last). ``limit`` caps
    bundles (CMC: snapshot dates) per source; ``dry_run`` makes no request and returns per-source plans plus a total;
    ``min_interval`` (seconds between requests) overrides every source's default pace (``PACE``) when given.
    Returns {source: report}, with '_total' (dry run) and '_gitignore' (the .gitignore lines of every family)."""
    names = list(sources) if sources is not None else list(DEFAULT_SOURCES) + (list(OPTIONAL_SOURCES) if include_optional else [])
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise ValueError(f"unknown sources: {unknown}; known: {sorted(SOURCES)}")
    out = report if report is not None else {}
    kw = {"dry_run": dry_run, "limit": limit, "max_calls": max_calls, "refresh": refresh, "rows_out": rows_out, "log": log}
    if min_interval is not None:
        kw["min_interval"] = min_interval
    product_list = None
    for n in names:
        rep: dict = {}
        t0 = time.time()
        try:
            if n == "coinbase_products":
                product_list = fetch_coinbase_products(store, report=rep, **{k: v for k, v in kw.items() if k != "limit"})
                if dry_run:
                    rep["_plan"] = rep.pop("_plan_products")
            elif n == "coinbase_daily":
                SOURCES[n](store, report=rep, product_list=product_list, **kw)
            else:
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
                         "gz_mb": round(sum(p["gz_mb"] for p in plans), 1), "minutes": round(sum(p["minutes"] for p in plans), 1)}
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
                                     "licence": LICENCE[fam[1]] if fam else "", "available_at": fam[4] if fam else "",
                                     "in_git": False, "gitignore_line": f"mandel/archive/data/{key}.jsonl.gz",
                                     "bundles": 0, "calls": 0, "rows": 0, "gz_mb": 0.0, "minutes": 0.0})
            a["bundles"] += 1
            for k in ("calls", "rows", "gz_mb", "minutes"):
                a[k] = round(a[k] + it[k], 2)
    return list(acc.values())


# ============================================================================================ command line ==

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m mandel.data.crypto_history",
                                description="Fetch the batch-6c crypto history bundles (Coinbase, Kraken, CoinMarketCap, CoinMetrics, "
                                            "blockchain.info, DefiLlama, iShares) into the archive.")
    p.add_argument("--sources", help=f"comma-separated subset of {','.join(SOURCES)}")
    p.add_argument("--optional", action="store_true", help=f"also run {', '.join(OPTIONAL_SOURCES)}")
    p.add_argument("--dry-run", action="store_true", help="no request: print the plan (calls, rows, gzip MB, minutes)")
    p.add_argument("--preview", metavar="DIR", help="do not store: write each bundle's rows to DIR/<bundle>.preview.jsonl.gz and the report")
    p.add_argument("--limit", type=int, help="bundles (CMC: snapshot dates) per source")
    p.add_argument("--max-calls", type=int, help="requests per bundle (preview; such bundles are never stored)")
    p.add_argument("--refresh", action="store_true", help="fetch again bundles already stored complete")
    p.add_argument("--min-interval", type=float, help="seconds between requests for every source (default: PACE per source)")
    a = p.parse_args(argv)
    store = None
    if not a.preview:
        from mandel.archive import Archive
        store = Archive()
    rows_out: Optional[dict] = {} if a.preview else None
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    rep = fetch_all_crypto(store, dry_run=a.dry_run, limit=a.limit, sources=a.sources.split(",") if a.sources else None,
                           include_optional=a.optional, max_calls=a.max_calls, refresh=a.refresh, rows_out=rows_out, log=log,
                           min_interval=a.min_interval)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        for name, rows in (rows_out or {}).items():
            with gzip.open(os.path.join(a.preview, f"{name}.preview.jsonl.gz"), "wt", encoding="utf-8") as f:
                for r in rows:
                    f.write(_line(r) + "\n")
        with open(os.path.join(a.preview, "report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, default=str)
    if a.dry_run:
        rep["_families"] = family_table(rep)
    print(json.dumps(rep if a.dry_run else {k: v for k, v in rep.items() if k != "_gitignore"}, indent=1, default=str)[:200000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
