"""
Market history for the batch-6c underlying claims: Yahoo daily and hourly bars with dividends and splits, FRED series
and ALFRED real-time vintages.
=====================================================================================================================

Sources (keyless; probed 2026-10-15 from this host):
  * Yahoo chart API ``https://query1.finance.yahoo.com/v8/finance/chart/<SYM>`` (``query2.finance.yahoo.com`` is the
    fallback when query1 throttles; on 2026-10-15 query1 answered 429 to browser user agents while query2 and the repo
    user agent worked). ``period1=-1400000000&period2=<now>&interval=1d&events=div|split`` returns the whole daily
    history (split-adjusted OHLC, adjclose) plus the dividend and split events in ONE call. ``range=max`` silently
    downgrades to monthly bars and is never used.
    Intraday depth (Yahoo's limits, not ours): 1h/60m bars reach back about 730 sessions (``range=730d``, the
    ``hourly-*`` recipe; hourly-SPY holds 730 gap-free sessions); 90m/30m/15m/5m/2m about 60 days; 1m about 30 days and
    at most 7-8 days per request. Anything older is unreachable from Yahoo. CAD=X 1h starts only 2023-12-29.
    Delisted tickers answer 404 'No data found, symbol may be delisted' (CELG); a reused ticker can resolve to another
    instrument (FB is now a Cboe ETF); LBRDK returns a single bar (Yahoo's history starts 2026-07-17), so it is
    reported as too short and not stored (DoltHub post-no-preference/stocks has it; another source group).
  * FRED graph CSV ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SID>`` (the latest vintage; the fred-DTB3
    recipe, parsed by ``mandel.data.options.fred_series``) and the series page ``https://fred.stlouisfed.org/series/
    <SID>``, whose schema.org block states the licence (``#copyright-public-domain``, ``#copyright-citation-required``,
    ``#copyright-pre-approval-required``) next to the Source and Release lines. FRED sometimes answers HTTP/2
    INTERNAL_ERROR or an empty body, so every call retries.
  * ALFRED ``https://alfred.stlouisfed.org/series/downloaddata?seid=<SID>``: the GET lists every vintage date; one POST
    of that form with every vintage selected, output 'Observations by Real-Time Period' and zipped CSV returns each
    observation's values with realtime_start/realtime_end (UNRATE: 800 vintages 1960-03-15..2026-10-02 in a 16 KB zip).

Bundles (``mandel/archive/data/<name>.jsonl.gz``; ``^`` and ``=`` become ``-`` as in ``Archive.store``):
  * ``daily-history-<SYM>``: exactly the rows ``mandel.data.social.collect_history`` writes (source yahoo, kind
    price, value {symbol, t, open, high, low, close, volume, adjclose?}, observed_at = bar time, available_at = bar time
    + 24 h: a daily bar is known after its session closes), the same tags and schema, so harnesses treat old and new
    symbols identically. One difference, which removes rows only: a bar whose available_at is later than the fetch time
    (today's bar, possibly still forming) is not stored; the next refresh adds it.
  * ``daily-events-<SYM>``: the same call's dividends and splits (kinds ``dividend`` / ``split``). Yahoo dates each event
    on its ex-date session (bar time); the declaration came earlier, so available_at = that ex-date bar time is a
    conservative bound. Dividend amounts are per share as Yahoo shows them today (adjusted for later splits). Kept
    apart from the price rows because harnesses read every daily-history row as a bar. Written even with no event (a
    zero-row bundle records that the history was checked and carries none).
  * ``hourly-<SYM>``: exactly the rows ``mandel.data.unlocks.fetch_hourly`` writes (kind bar1h, available_at = bar start
    + 1 h), merged with what is stored so history accumulates past Yahoo's 730-day window; a bar still in progress is
    not stored.
  * ``fred-<SID>``: the fred-DTB3 row shape (source fred, kind series, value {day, value}, observed_at = day 00:00 UTC).
    DAILY series keep the house rule exactly: available_at = day 20:00 UTC (note: Treasury posts the CMT curve in the
    evening, so this is up to a few hours early; it is the archived convention, kept so old and new series line up).
    NON-DAILY series are revised and published weeks after the period, so day 20:00 would leak: their rows hold the
    LATEST vintage and available_at = the publication time of that exact value (its ALFRED realtime_start, at the
    release time of day), with value.realtime_start and value.available_basis ``alfred-current-vintage``; a value
    ALFRED does not carry yet is stamped with the capture time (``capture``). Pre-ALFRED history therefore counts from
    the first ALFRED vintage that holds it: honest, but late. Use ``alfred-<SID>`` for forecasting.
  * ``alfred-<SID>``: every real-time period of every observation (kind vintage, value {day, value, realtime_start,
    realtime_end, first_release, first_vintage, lag_rule_at}), available_at = realtime_start at the release time of day
    (BLS 08:30 ET, Michigan 10:00 ET, Z.1 12:00 ET, otherwise the end of the UTC day). ``first_release`` marks the
    earliest non-blank period of an observation (the first-release value). ``first_vintage`` marks periods that start
    on the series' first ALFRED vintage: the true first release was earlier and is unknown; ``lag_rule_at`` is then the
    conservative release-lag estimate (``LAG_RULE_DAYS`` after the end of the period), a stated look-ahead
    approximation for harnesses that need pre-ALFRED history (T-398 before 2019), never used as available_at.

Licences (the repository is public): ``in_git=True`` only for FRED series whose page says public domain AND whose
source is a US federal agency (``FEDERAL_SOURCES``: Board of Governors H.15 and Z.1, BLS); the decision is read from
the series page at fetch time and falls back to False when the page cannot be read. Yahoo, Michigan (UMCSENT), Moody's
via St. Louis Fed (BAA10Y), OECD (IRLTLT01*) and St. Louis Fed's own NBER-based USREC are local-only (``in_git=False``),
and each needs its exact ``.gitignore`` line (``gitignore_line``). ALFRED bundles follow their series.

Resumable and safe to re-run: every fetcher stores a bundle as soon as its call returns, skips bundles already stored ON
THIS MACHINE (an INDEX entry whose file is missing, e.g. a local-only bundle on a fresh clone, is rebuilt), never stores
a failed, empty or non-daily answer, and with ``refresh=True`` replaces a daily history only when the new one has at
least ``REFRESH_MIN_FRACTION`` of the stored rows (hourly bundles merge). ``dry_run`` makes no request and returns the
plan with per-bundle estimates (calls, rows, gzip MB, minutes). ``limit`` keeps the first N bundles of each fetcher.
Entry point: ``fetch_all_yahoo_fred(store, dry_run=False, limit=None)``; command line ``python3 -m
mandel.data.market_history all [--dry-run] [--limit N] [--preview DIR]``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import httpx

from mandel.data.fetch import Throttle, now_iso
from mandel.data.options import fred_series
from mandel.data.options_misc import RETRY_STATUS, _archive, _client, _end_of_day, _get, _retry_after
from mandel.data.store import Observation, iso

YAHOO_HOSTS = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")
FRED_GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_PAGE = "https://fred.stlouisfed.org/series/{sid}"
ALFRED_DOWNLOAD = "https://alfred.stlouisfed.org/series/downloaddata"
PERIOD1 = -1400000000                         # 1925: the full-history start of the existing daily-history recipe
NY = ZoneInfo("America/New_York")
ARCHIVE_DATA_PREFIX = "mandel/archive/data/"  # Archive.store writes <root>/<kind>/<safe name>.jsonl.gz, root = mandel/archive
MIN_DAILY_BARS = 5                            # fewer bars is not a history (LBRDK answers one bar)
REFRESH_MIN_FRACTION = 0.9
YAHOO_INTERVAL = 2.0                          # seconds between Yahoo calls (<= 0.5 req/s; Yahoo throttled this host on 2026-10-15)
FRED_INTERVAL = 1.0
_sleep = time.sleep                           # patched in tests

# ------------------------------------------------------------------------------------------- house conventions --
# Copied from mandel.data.social.collect_history and mandel.data.unlocks.fetch_hourly so new bundles match the archived ones.
HISTORY_TAGS = ["prices", "daily", "history"]
HISTORY_SCHEMA = ("value = {symbol, t, open, high, low, close (split-adjusted), volume, adjclose (split and dividend adjusted, "
                  "when Yahoo provides it)}")
HOURLY_TAGS = ["prices", "hourly"]
HOURLY_SCHEMA = "value = {symbol, t (bar start, unix), open, high, low, close, volume}"
EVENTS_TAGS = ["prices", "daily", "events", "dividends", "splits"]
EVENTS_SCHEMA = ("kind dividend: value = {symbol, type, t (ex-date bar time, unix), ex_date, amount (per share as Yahoo shows it "
                 "today, adjusted for later splits)}; kind split: value = {symbol, type, t, ex_date, numerator, denominator, ratio}; "
                 "observed_at = available_at = the ex-date bar time (declared earlier, so conservative)")
YAHOO_LICENCE = "Yahoo Finance data: no redistribution licence (Yahoo terms of service), local disk only, never in git"
FRED_DAILY_TAGS = ["rates", "fred", "history"]

# ------------------------------------------------------------------------------------------------ universes --
COUNTRY16 = ["EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWK", "EWL", "EWN", "EWO", "EWP", "EWQ", "EWS", "EWU", "EWM"]
COUNTRY21 = ["EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWK", "EWL", "EWM", "EWN", "EWO", "EWP", "EWQ", "EWS", "EWT",
             "EWU", "EWW", "EWY", "EWZ", "EZA"]
PAIRS_EXTRA = ["DIA", "MDY", "EEM", "VWO", "SHY", "LQD", "HYG", "GDX", "XOP", "KRE", "XHB", "IYR"] + COUNTRY21
ISHARES_SECTORS = ["IYW", "IYF", "IYH", "IYE", "IYJ", "IYK", "IYC", "IDU", "IYM", "IYZ", "IYT"]
# T-420/T-462 declared list (>= 60 ETFs with history by 2006, PPLT from 2010): the 26 archived ETFs plus these 42.
ETF60_EXTRA = COUNTRY21 + ["EEM", "GDX", "IJH", "MDY", "DIA", "LQD", "TIP", "SHY", "IYR"] + ISHARES_SECTORS + ["PPLT"]
DUAL_CLASS = ["GOOG", "GOOGL", "BRK-A", "BRK-B", "BF-A", "BF-B", "LEN", "LEN-B", "HEI", "HEI-A", "ZG", "Z", "NWSA", "NWS",
              "UA", "UAA", "FOXA", "FOX", "LBRDA", "LBRDK"]
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
CANADA = ["RY", "TD", "BNS", "BMO", "ENB", "CNQ", "SU", "CP", "CNI", "SHOP"]
IRLTLT01 = [f"IRLTLT01{cc}M156N" for cc in ("US", "DE", "GB", "JP", "CA", "AU", "CH", "SE", "NO", "NZ")]

# What each theory needs from these hosts (triage6c final entries and the theories' trial.data). "stocks" names a
# single-stock universe whose ticker list comes from another source group (Wikipedia, fja05680, FINRA, SEC): pass the
# list to fetch_daily_histories / --symbols-file once that group has stored it.
THEORY_NEEDS: dict[str, dict] = {
    "T-309": {"daily": ["EEM"]},
    "T-325": {"daily": ["SSO", "SDS", "UPRO", "SPXU", "UVXY"], "hourly": ["TQQQ", "SQQQ"]},
    "T-370": {"daily": ["PL=F", "PA=F", "HG=F", "PPLT", "PALL", "CPER", "IAU", "MGC=F", "SIL=F"]},
    "T-405": {"daily": ["GDX"], "fred": ["DFII10"]},
    "T-432": {"daily": COUNTRY16},
    "T-458": {"fred": ["UMCSENT", "UNRATE", "CPIAUCSL"]},
    "T-468": {"daily": ["BZ=F", "BNO", "UGA"]},
    "T-476": {"daily": ["DBA"]},
    "T-381": {"daily": COUNTRY16 + ["LQD", "HYG", "IEI", "SGOV"], "fred": IRLTLT01 + ["BAA10Y", "USREC"]},
    "T-398": {"fred": ["BOGZ1FA653064100Q", "BOGZ1LM893064105Q"]},
    "T-419": {"daily": ["GDX"]},
    "T-433": {"fred": IRLTLT01},
    "T-470": {"daily": DUAL_CLASS},
    "T-479": {"daily": ["VWO", "BND", "VGK", "EWJ", "HYG", "LQD", "SHY"]},
    "T-319": {"daily": COUNTRY21},
    "T-328": {"daily": ["FBTC"], "hourly": ["IBIT", "FBTC"]},
    "T-373": {"daily": ["SHY", "IEI", "BIL", "SGOV"], "fred": ["DGS20", "DGS7", "DGS5", "DGS3", "DGS1"]},
    "T-420": {"daily": ETF60_EXTRA},
    "T-462": {"daily": ETF60_EXTRA},
    "T-471": {"daily": COUNTRY21},
    "T-313": {"daily": ["CPER", "UNG", "DBA", "DBB", "DBE", "PPLT", "PALL", "CORN", "WEAT", "SOYB"]},
    "T-321": {"daily": PAIRS_EXTRA},
    "T-322": {"daily": PAIRS_EXTRA},
    "T-323": {"daily": PAIRS_EXTRA},
    "T-330": {"daily": ["USDT-USD", "USDC-USD"]},
    "T-365": {"daily": ["STETH-USD"]},
    "T-366": {"daily": ["CBETH-USD"]},
    "T-374": {"daily": ["VYM", "SCHD", "SDY", "DVY"], "stocks": "about 400 current S&P 500 dividend payers (Wikipedia constituents table)"},
    "T-472": {"daily": ["PHYS", "PSLV"]},
    "T-482": {"daily": ["EEM"]},
    "T-375": {"stocks": "FINRA short-interest names passing price > $5 and ADV > $5m (Yahoo has survivors only)"},
    "T-393": {"stocks": "point-in-time top-1000 names from FINRA and SEC shares (Yahoo has survivors only)"},
    "T-451": {"daily": ["IWN"], "stocks": "value-quintile names from SEC companyfacts (Yahoo has survivors only)"},
    "T-473": {"daily": ["XLRE", "XLC"], "stocks": "fja05680 S&P 500 members since 2010 (about 1,262 tickers)"},
    "T-334": {"stocks": "S&P 500 additions 2010-2026 from fja05680, mapped to current tickers"},
    "T-394": {"stocks": "S&P 500 members since 2019 from fja05680"},
    "T-414": {"daily": ["TSLA", "NVDA", "AAPL", "GME", "AMC", "PLTR", "MSTR", "COIN", "SOL-USD", "DOGE-USD"],
              "hourly": ["SOL-USD", "DOGE-USD"]},
    "T-415": {"daily": ["AAPL", "AMZN", "GOOG", "GOOGL", "EEM"], "hourly": ["AAPL", "AMZN", "GOOG", "GOOGL", "USO", "EEM"] + SECTORS},
    "T-483": {"daily": ["SSO", "UPRO"]},
    "T-377": {"daily": ["SGOV", "BIL"]},
    "T-404": {"daily": ["IAU", "GLDM"], "fred": ["DFII10"]},
    "T-430": {"daily": ["LQD", "SGOV", "BIL", "HYG", "IEI"], "fred": ["BAA10Y"]},
    "T-467": {"hourly": CANADA + [f"{s}.TO" for s in CANADA] + ["CAD=X"]},
    "T-474": {"daily": ["SHY", "IEI", "TLH"], "fred": ["DGS5"]},
    "T-378": {"daily": ["BOXX"]},
}


def _union(kind: str) -> list[str]:
    out: list[str] = []
    for need in THEORY_NEEDS.values():
        for s in need.get(kind, []):
            if s not in out:
                out.append(s)
    return out


DAILY_SYMBOLS = _union("daily")
HOURLY_SYMBOLS = _union("hourly")
FRED_SERIES = _union("fred")


def theories_for(kind: str, item: str) -> list[str]:
    return sorted(t for t, need in THEORY_NEEDS.items() if item in need.get(kind, []))


# ---------------------------------------------------------------------------------------------- FRED metadata --
FEDERAL_SOURCES = {"Board of Governors of the Federal Reserve System (US)", "U.S. Bureau of Labor Statistics",
                   "U.S. Bureau of Economic Analysis", "U.S. Census Bureau", "U.S. Department of the Treasury. Fiscal Service",
                   "U.S. Energy Information Administration", "U.S. Department of Labor", "U.S. Department of the Treasury"}
PUBLIC_DOMAIN = "#copyright-public-domain"
# Expected licence per series (read from each series page on 2026-10-15); used for the dry-run plan only. The fetch decides
# from the live page and never sets in_git=True unless the page says public domain and the source is federal.
FRED_EXPECTED: dict[str, tuple[str, bool]] = {
    **{s: ("Board of Governors of the Federal Reserve System (US), H.15; public domain", True) for s in ("DFII10", "DGS20", "DGS7", "DGS5", "DGS3", "DGS1")},
    **{s: ("Board of Governors of the Federal Reserve System (US), Z.1 Financial Accounts; public domain", True)
       for s in ("BOGZ1FA653064100Q", "BOGZ1LM893064105Q")},
    "UNRATE": ("U.S. Bureau of Labor Statistics, Employment Situation; public domain", True),
    "CPIAUCSL": ("U.S. Bureau of Labor Statistics, Consumer Price Index; public domain", True),
    "UMCSENT": ("University of Michigan, Surveys of Consumers; copyrighted (citation required, 'Reprinted with permission')", False),
    "BAA10Y": ("Federal Reserve Bank of St. Louis from Moody's Baa yields; copyrighted (citation required)", False),
    "USREC": ("Federal Reserve Bank of St. Louis from NBER dates; not a federal-agency source", False),
    **{s: ("OECD Main Economic Indicators via FRED; copyrighted (OECD)", False) for s in IRLTLT01},
}
RELEASE_TIME_ET = {"UNRATE": "08:30", "CPIAUCSL": "08:30", "UMCSENT": "10:00", "BOGZ1FA653064100Q": "12:00", "BOGZ1LM893064105Q": "12:00"}
LAG_RULE_DAYS = {"UNRATE": 35, "CPIAUCSL": 35, "UMCSENT": 35, "BOGZ1FA653064100Q": 84, "BOGZ1LM893064105Q": 84,
                 **{s: 45 for s in IRLTLT01}}          # USREC: NBER dates come 6-21 months late; no lag rule
FRED_TAGS = {"UNRATE": "macro", "CPIAUCSL": "macro", "UMCSENT": "macro", "USREC": "macro", "BAA10Y": "credit",
             "BOGZ1FA653064100Q": "flows", "BOGZ1LM893064105Q": "flows"}


# ------------------------------------------------------------------------------------------------- utilities --

def safe_name(name: str) -> str:
    """The bundle name Archive.store writes (``^GSPC`` -> ``-GSPC``, ``GC=F`` -> ``GC-F``)."""
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in name)


def history_bundle(sym: str) -> str:
    return safe_name(f"daily-history-{sym}")


def events_bundle(sym: str) -> str:
    return safe_name(f"daily-events-{sym}")


def hourly_bundle(sym: str) -> str:
    return safe_name(f"hourly-{sym}")


def fred_bundle(sid: str) -> str:
    return safe_name(f"fred-{sid}")


def alfred_bundle(sid: str) -> str:
    return safe_name(f"alfred-{sid}")


def gitignore_line(name: str) -> str:
    """The exact .gitignore line for a local-only data bundle (path pattern of Archive.store under mandel/archive)."""
    return f"{ARCHIVE_DATA_PREFIX}{safe_name(name)}.jsonl.gz"


def yahoo_symbol(sym: str) -> str:
    """Exchange tickers to Yahoo's spelling: class shares use a dash (BRK.B -> BRK-B, BF.B -> BF-B); suffixes such as
    .TO and the ^ / =F / =X forms are kept."""
    s = (sym or "").strip().upper()
    if re.fullmatch(r"[A-Z]{1,5}[./][A-Z]", s):
        return s[:-2] + "-" + s[-1]
    return s


def read_symbols(path: str) -> list[str]:
    """Tickers from a text file: one per line, or a CSV whose first column is the ticker (a header row is skipped)."""
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        tok = line.split(",")[0].strip().strip('"')
        if not tok or tok.lower() in ("symbol", "ticker", "act_symbol"):
            continue
        s = yahoo_symbol(tok)
        if s not in out:
            out.append(s)
    return out


def symbols_from_bundle(store, name: str, field: Optional[str] = None) -> list[str]:
    """Tickers from an archived bundle another source group stored (e.g. a constituents list): ``value[field]`` when given,
    else the row key. Yahoo spelling, first-seen order, no duplicates. Empty when the bundle is not on this machine."""
    out: list[str] = []
    for r in _load(_archive(store), name):
        tok = (r.get("value") or {}).get(field) if field else r.get("key")
        if isinstance(tok, str) and tok.strip():
            s = yahoo_symbol(tok)
            if s not in out:
                out.append(s)
    return out


def _stored_here(archive, name: str) -> bool:
    """An INDEX entry whose file is on this machine (a local-only bundle on a fresh clone has an entry but no file)."""
    if archive is None:
        return False
    try:
        entry = archive.get(name)
    except KeyError:
        return False
    try:
        return archive._abs(entry.path).exists()
    except Exception:
        return False


def _load(archive, name: str) -> list[dict]:
    if archive is None:
        return []
    try:
        return list(archive.load(name))
    except (KeyError, FileNotFoundError, OSError, ValueError):
        return []


def _et_to_utc(day: str, hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    d = date.fromisoformat(day[:10])
    return datetime(d.year, d.month, d.day, h, m, tzinfo=NY).astimezone(timezone.utc).isoformat()


def release_at(sid: str, day: str) -> str:
    """When a FRED/ALFRED vintage dated ``day`` was public: the release time of day in New York when known, else the end
    of the UTC day (the time is not recorded, so the day's 00:00 could come before it)."""
    t = RELEASE_TIME_ET.get(sid)
    return _et_to_utc(day, t) if t else _end_of_day(day)


def _period_end(day: str, months: int) -> date:
    d = date.fromisoformat(day[:10])
    y, m = d.year + (d.month - 1 + months) // 12, (d.month - 1 + months) % 12 + 1
    return date(y, m, 1) - timedelta(days=1)


def lag_rule_at(sid: str, day: str, months: int) -> Optional[str]:
    lag = LAG_RULE_DAYS.get(sid)
    if lag is None:
        return None
    return _end_of_day((_period_end(day, months) + timedelta(days=lag)).isoformat())


def _store(archive, name: str, rows: list[dict], recipe: str, tags: list[str], schema: str, in_git: bool):
    return archive.store(name, kind="data", rows=rows, recipe=recipe, tags=tags, schema=schema, in_git=in_git)


def _post(client: httpx.Client, url: str, throttle: Throttle, data: dict, params: Optional[dict] = None, retries: int = 4,
          backoff: float = 1.0, max_wait: float = 120.0) -> tuple[Optional[httpx.Response], dict]:
    """POST twin of mandel.data.options_misc._get: retries 429/5xx and transport errors, honours Retry-After."""
    info: dict = {"url": url, "attempts": 0}
    for attempt in range(retries):
        throttle.wait()
        info["attempts"] = attempt + 1
        try:
            r = client.post(url, params=params, data=data)
        except httpx.HTTPError as e:
            info["error"] = repr(e)[:200]
            _sleep(backoff * 2 ** attempt)
            continue
        info["status"] = r.status_code
        if r.status_code == 200:
            info.pop("error", None)
            return r, info
        if r.status_code in RETRY_STATUS:
            ra = _retry_after(r)
            if ra is not None and ra > max_wait:
                info.update(retry_after=ra, body=r.text[:300])
                return None, info
            _sleep(max(backoff * 2 ** attempt, ra or 0.0))
            continue
        info["body"] = r.text[:300]
        return None, info
    return None, info


# ===================================================================================================== Yahoo ==

def _chart_error(body: str) -> Optional[str]:
    try:
        err = (json.loads(body).get("chart") or {}).get("error")
    except (ValueError, AttributeError):
        return None
    return f"{err.get('code')}: {err.get('description')}" if isinstance(err, dict) else None


def yahoo_chart(symbol: str, params: dict, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 2.0,
                hosts: Iterable[str] = YAHOO_HOSTS) -> tuple[Optional[dict], dict]:
    """One chart result. query1 first; when it fails without a Yahoo error body (429 after retries, 5xx, HTML, transport)
    the same request goes to query2. A Yahoo error body (404 'symbol may be delisted', 400 'Data doesn't exist') is final."""
    info: dict = {"symbol": symbol, "calls": 0}
    for host in hosts:
        r, i = _get(client, f"{host}/v8/finance/chart/{symbol}", throttle, params=params, retries=retries, backoff=backoff)
        info["calls"] += i.get("attempts", 0)
        info.update(host=host, status=i.get("status"))
        if r is None:
            err = _chart_error(i.get("body") or "")
            if err:
                info["error"] = err
                return None, info
            info["error"] = i.get("error") or (f"retry-after {i['retry_after']}s" if i.get("retry_after") else f"HTTP {i.get('status')}")
            continue
        if not r.headers.get("content-type", "").startswith("application/json"):
            info["error"] = "answer is not JSON"
            continue
        try:
            ch = r.json().get("chart") or {}
        except ValueError:
            info["error"] = "bad JSON"
            continue
        if ch.get("error"):
            info["error"] = f"{ch['error'].get('code')}: {ch['error'].get('description')}"
            return None, info
        res = (ch.get("result") or [None])[0]
        if not res:
            info["error"] = "empty result"
            return None, info
        info.pop("error", None)
        return res, info
    return None, info


def parse_daily(res: dict) -> list[dict]:
    """Bars exactly as mandel.data.social.yahoo_history builds them; [] when the answer is not daily or malformed."""
    try:
        if res.get("meta", {}).get("dataGranularity", "1d") != "1d":
            return []
        ts = res["timestamp"]; q = res["indicators"]["quote"][0]
        adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        return [{"t": t, "open": q["open"][i], "high": q["high"][i], "low": q["low"][i], "close": q["close"][i], "volume": q["volume"][i],
                 **({"adjclose": adj[i]} if adj and adj[i] is not None else {})}
                for i, t in enumerate(ts) if q["close"][i] is not None]
    except (KeyError, IndexError, TypeError, ValueError):
        return []


def parse_hourly(res: dict, sym: str) -> dict[int, dict]:
    """{bar start: value} exactly as mandel.data.unlocks.fetch_hourly builds them."""
    try:
        ts = res["timestamp"]; q = res["indicators"]["quote"][0]
        return {int(t): {"symbol": sym, "t": int(t), "open": q["open"][i], "high": q["high"][i], "low": q["low"][i], "close": q["close"][i],
                         "volume": q["volume"][i]} for i, t in enumerate(ts) if q["close"][i] is not None}
    except (KeyError, IndexError, TypeError, ValueError):
        return {}


def parse_events(res: dict) -> dict[str, list[dict]]:
    ev = res.get("events") or {}
    divs, splits = [], []
    for v in (ev.get("dividends") or {}).values():
        try:
            divs.append({"t": int(v["date"]), "amount": v.get("amount")})
        except (KeyError, TypeError, ValueError):
            continue
    for v in (ev.get("splits") or {}).values():
        try:
            splits.append({"t": int(v["date"]), "numerator": v.get("numerator"), "denominator": v.get("denominator"), "ratio": v.get("splitRatio")})
        except (KeyError, TypeError, ValueError):
            continue
    return {"dividends": sorted(divs, key=lambda x: x["t"]), "splits": sorted(splits, key=lambda x: x["t"])}


def history_rows(sym: str, bars: list[dict], cutoff: Optional[float] = None) -> list[dict]:
    """Archive rows exactly as collect_history writes them; bars not yet available at ``cutoff`` (unix) are dropped."""
    return [Observation("yahoo", "price", sym, observed_at=iso(b["t"]), available_at=iso(b["t"] + 86400), value={"symbol": sym, **b}).row()
            for b in bars if cutoff is None or b["t"] + 86400 <= cutoff]


def event_rows(sym: str, events: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for d in events.get("dividends", []):
        rows.append(Observation("yahoo", "dividend", sym, observed_at=iso(d["t"]), available_at=iso(d["t"]),
                                value={"symbol": sym, "type": "dividend", "t": d["t"], "ex_date": iso(d["t"])[:10], "amount": d["amount"]}).row())
    for s in events.get("splits", []):
        rows.append(Observation("yahoo", "split", sym, observed_at=iso(s["t"]), available_at=iso(s["t"]),
                                value={"symbol": sym, "type": "split", "t": s["t"], "ex_date": iso(s["t"])[:10], "numerator": s["numerator"],
                                       "denominator": s["denominator"], "ratio": s["ratio"]}).row())
    return sorted(rows, key=lambda r: (r["value"]["t"], r["kind"]))


def hourly_rows(values: dict[int, dict]) -> list[dict]:
    return [Observation("yahoo", "bar1h", v["symbol"], observed_at=iso(v["t"]), available_at=iso(v["t"] + 3600), value=v).row()
            for _, v in sorted(values.items())]


def _meta_text(meta: Optional[dict]) -> str:
    m = {k: (meta or {}).get(k) for k in ("currency", "exchangeName", "instrumentType", "firstTradeDate", "exchangeTimezoneName")}
    return json.dumps({k: v for k, v in m.items() if v is not None}, sort_keys=True)


def history_recipe(sym: str, meta: Optional[dict] = None) -> str:
    return (f"yahoo /v8/finance/chart/{sym}?period1=-1400000000 (1925)&period2=now&interval=1d&events=div|split (available_at = bar time + 24h: "
            f"a daily close is usable the next day); via mandel.data.market_history.fetch_daily_histories (query1, query2 fallback); bars not "
            f"yet available at the fetch are left out; dividends and splits in {events_bundle(sym)}; meta {_meta_text(meta)}. {YAHOO_LICENCE}")


def events_recipe(sym: str, meta: Optional[dict] = None) -> str:
    return (f"yahoo /v8/finance/chart/{sym}?period1=-1400000000&period2=now&interval=1d&events=div|split, chart.result[0].events "
            f"(dividends, splits; the same call as {history_bundle(sym)}); available_at = the ex-date bar time; meta {_meta_text(meta)}. "
            f"{YAHOO_LICENCE}")


def hourly_recipe(sym: str, meta: Optional[dict] = None) -> str:
    return (f"yahoo /v8/finance/chart/{sym}?range=730d&interval=1h, merged with earlier captures (bar time = bar start); via "
            f"mandel.data.market_history.fetch_hourly_histories; a bar still in progress at the fetch is left out; Yahoo serves 1h bars "
            f"for about 730 sessions only (730 calendar days for crypto); meta {_meta_text(meta)}. {YAHOO_LICENCE}")


# ------------------------------------------------------------------------------------------------ estimates --
# First trade dates (from the triage probes) for the row estimates only; unknown symbols use the class defaults.
FIRST_TRADE = {"EEM": "2003-04-14", "SSO": "2006-06-21", "SDS": "2006-07-13", "UPRO": "2009-06-25", "SPXU": "2009-06-25", "UVXY": "2011-10-04",
               "PL=F": "1997-10-01", "PA=F": "1998-09-01", "HG=F": "2000-08-30", "PPLT": "2010-01-08", "PALL": "2010-01-08", "CPER": "2011-11-15",
               "GDX": "2006-05-22", "EWT": "2000-06-23", "EWY": "2000-05-12", "EWZ": "2000-07-14", "EZA": "2003-02-07", "BZ=F": "2007-07-30",
               "BNO": "2010-06-02", "UGA": "2008-02-28", "DBA": "2007-01-05", "DBB": "2007-01-05", "DBE": "2007-01-05", "LQD": "2002-07-30",
               "HYG": "2007-04-11", "IEI": "2007-01-11", "SGOV": "2020-06-01", "VWO": "2005-03-10", "BND": "2007-04-10", "VGK": "2005-03-10",
               "SHY": "2002-07-30", "BIL": "2007-05-30", "FBTC": "2024-01-11", "UNG": "2007-04-18", "CORN": "2010-06-09", "WEAT": "2011-09-19",
               "SOYB": "2011-09-19", "USDT-USD": "2017-11-09", "USDC-USD": "2018-10-08", "STETH-USD": "2020-12-23", "CBETH-USD": "2022-08-24",
               "PHYS": "2010-02-26", "PSLV": "2010-10-28", "TIP": "2003-12-05", "XOP": "2006-06-22", "KRE": "2006-06-22", "XHB": "2006-02-06",
               "IAU": "2005-01-28", "GLDM": "2018-06-26", "MGC=F": "2010-09-27", "SIL=F": "2010-09-27", "TLH": "2007-01-11", "IWN": "2000-07-28",
               "XLRE": "2015-10-08", "XLC": "2018-06-19", "BOXX": "2022-12-28", "VYM": "2006-11-16", "SCHD": "2011-10-20", "SDY": "2005-11-15",
               "DVY": "2003-11-07", "SOL-USD": "2020-04-10", "DOGE-USD": "2017-11-09", "IYT": "2003-10-10", "IJH": "2000-05-26",
               "GOOG": "2004-08-19", "GOOGL": "2004-08-19", "ZG": "2011-07-20", "Z": "2015-08-03", "NWSA": "2013-06-19", "NWS": "2013-06-19",
               "UA": "2016-04-08", "UAA": "2005-11-18", "FOXA": "2019-03-12", "FOX": "2019-03-12", "LBRDA": "2014-11-05", "LBRDK": "2026-08-19",
               "PLTR": "2020-09-30", "COIN": "2021-04-14", "TSLA": "2010-06-29", "MSTR": "1998-06-11", "AMC": "2013-12-18", "IBIT": "2024-01-11",
               "TQQQ": "2010-02-11", "SQQQ": "2010-02-11"}
for _s in COUNTRY21:
    FIRST_TRADE.setdefault(_s, "1996-03-18")
for _s in ISHARES_SECTORS:
    FIRST_TRADE.setdefault(_s, "2000-06-16")
GZ_BYTES = {"daily": 40, "events": 25, "hourly": 38, "fred": 10, "alfred": 15}      # measured on archived bundles and the 2026-10-15 preview
# (fred-<SID> rows, alfred-<SID> rows): measured on the 2026-10-15 preview for DGS20, DFII10, BAA10Y, UMCSENT, USREC,
# BOGZ1FA653064100Q and IRLTLT01USM156N (UNRATE's ALFRED count from the probe); the others are extrapolated
FRED_ROWS_EST = {"DGS20": (14491, 0), "DGS7": (14300, 0), "DGS5": (16200, 0), "DGS3": (16200, 0), "DGS1": (16200, 0), "DFII10": (5950, 0),
                 "BAA10Y": (10195, 0), "UMCSENT": (676, 1083), "UNRATE": (945, 2200), "CPIAUCSL": (945, 12000),
                 "BOGZ1FA653064100Q": (304, 690), "BOGZ1LM893064105Q": (324, 720), "USREC": (2062, 2079),
                 **{s: (700, 2000) for s in IRLTLT01}, "IRLTLT01USM156N": (881, 2082)}


def _years_since(day: str) -> float:
    return max(0.0, (date.today() - date.fromisoformat(day)).days / 365.25)


def estimate_daily_rows(sym: str) -> int:
    crypto = sym.endswith("-USD")
    start = FIRST_TRADE.get(sym) or ("2018-01-01" if crypto else "2000-08-30" if sym.endswith("=F") else "2000-01-03")
    return int(_years_since(start) * (365 if crypto else 252))


def estimate_events(sym: str) -> int:
    if sym.endswith("-USD") or sym.endswith("=F") or sym.endswith("=X"):
        return 0
    return int(_years_since(FIRST_TRADE.get(sym, "2000-01-03")) * 4)


def estimate_hourly_rows(sym: str) -> int:
    if sym.endswith("-USD"):
        return 24 * 730
    if sym.endswith("=X"):
        return 24 * 5 * 145           # CAD=X 1h starts 2023-12-29: about 145 five-day weeks
    return 7 * 730                    # 09:30..15:30 bars on 730 sessions


def _minutes(calls: int, interval: float) -> float:
    return round(calls * (interval + 0.8) / 60, 2)


def _plan_row(name: str, function: str, theories: list[str], in_git: bool, licence: str, calls: int, rows: int, kind: str,
              interval: float, rule: str, stored: bool) -> dict:
    return {"name": name, "function": function, "theories": theories, "in_git": in_git, "licence": licence,
            "gitignore_line": "" if in_git else gitignore_line(name), "calls": 0 if stored else calls, "rows": rows,
            "gz_mb": round(rows * GZ_BYTES[kind] / 1e6, 3), "minutes": 0.0 if stored else _minutes(calls, interval),
            "available_at_rule": rule, "already_stored": stored}


DAILY_RULE = "bar time + 24h (session closed; collect_history convention); today's bar not stored"
EVENTS_RULE = "ex-date bar time (declared before the ex-date)"
HOURLY_RULE = "bar start + 1h (fetch_hourly convention); bar in progress not stored"
FRED_DAILY_RULE = "observation day 20:00 UTC (fred-DTB3 convention)"
FRED_REVISED_RULE = "ALFRED realtime_start of the stored (latest-vintage) value at the release time of day; capture time when ALFRED lacks it"
ALFRED_RULE = "realtime_start at the release time of day (BLS 08:30 ET, Michigan 10:00 ET, Z.1 12:00 ET, else 23:59:59 UTC)"


# ------------------------------------------------------------------------------------------------- fetchers --

def fetch_daily_histories(store=None, symbols: Optional[Iterable[str]] = None, dry_run: bool = False, limit: Optional[int] = None,
                          skip_stored: bool = True, refresh: bool = False, events: bool = True, min_interval: float = YAHOO_INTERVAL,
                          retries: int = 4, backoff: float = 2.0, client: Optional[httpx.Client] = None, report: Optional[dict] = None,
                          log=None) -> dict:
    """``daily-history-<SYM>`` and ``daily-events-<SYM>`` from one Yahoo call per symbol. ``symbols`` defaults to
    ``DAILY_SYMBOLS`` (every ETF, future, index and crypto pair the triage names); single-stock universes are passed in.
    Symbols whose history is already stored here are skipped (``refresh=True`` re-fetches them); with ``events=True`` a
    stored history with no events bundle gets its events from one call. Returns the report {bundle: info, '_plan': [...]};
    when ``store`` is None the rows are returned under each bundle's ``rows``."""
    syms = [yahoo_symbol(s) for s in (symbols if symbols is not None else DAILY_SYMBOLS)]
    syms = list(dict.fromkeys(syms))
    archive = _archive(store)
    rep = report if report is not None else {}
    todo, plan = [], []
    for s in syms:
        hb, eb = history_bundle(s), events_bundle(s)
        have_h, have_e = _stored_here(archive, hb), _stored_here(archive, eb)
        need_h = refresh or not (skip_stored and have_h)
        need_e = events and (refresh or not (skip_stored and have_e))
        if not need_h and not need_e:
            rep[hb] = {"skipped": "stored"}
            continue
        todo.append((s, need_h, need_e, have_h))
    if limit is not None:
        todo = todo[:limit]
    for s, need_h, need_e, have_h in todo:
        th_ = theories_for("daily", s)
        n = estimate_daily_rows(s)
        plan.append(_plan_row(history_bundle(s), "fetch_daily_histories", th_, False, "Yahoo Finance terms (no redistribution)",
                              1 if need_h else 0, n, "daily", min_interval, DAILY_RULE, not need_h))
        if events:
            plan.append(_plan_row(events_bundle(s), "fetch_daily_histories", th_, False, "Yahoo Finance terms (no redistribution)",
                                  0 if need_h else 1, estimate_events(s), "events", min_interval, EVENTS_RULE, not need_e))
    rep["_plan"] = plan
    if dry_run:
        return rep
    own = client is None
    c = client or _client(timeout=90)
    th = Throttle(min_interval)
    try:
        for s, need_h, need_e, have_h in todo:
            hb, eb = history_bundle(s), events_bundle(s)
            params = {"period1": PERIOD1, "period2": int(time.time()), "interval": "1d", "events": "div|split"}
            res, info = yahoo_chart(s, params, c, th, retries=retries, backoff=backoff)
            cutoff = time.time()
            if res is None:
                rep[hb] = info
                if log:
                    log(f"{s}: {info.get('error')}")
                continue
            bars = parse_daily(res)
            rows = history_rows(s, bars, cutoff)
            meta = res.get("meta") or {}
            info.update(granularity=meta.get("dataGranularity"), bars=len(rows), first=rows[0]["observed_at"][:10] if rows else None,
                        last=rows[-1]["observed_at"][:10] if rows else None, currency=meta.get("currency"),
                        instrument=meta.get("instrumentType"), first_trade=iso(meta["firstTradeDate"])[:10] if meta.get("firstTradeDate") else None)
            if len(rows) < MIN_DAILY_BARS:
                info["error"] = f"{len(rows)} daily bars (granularity {meta.get('dataGranularity')}): not stored"
                rep[hb] = info
                if log:
                    log(f"{s}: {info['error']}")
                continue
            ev = parse_events(res)
            erows = event_rows(s, ev)
            if archive is None:
                info["rows"] = rows
                rep[hb] = info
                if events:
                    rep[eb] = {"rows": erows}
                continue
            if need_h:
                old = len(_load(archive, hb)) if have_h else 0
                if have_h and len(rows) < REFRESH_MIN_FRACTION * old:
                    info["kept_stored"] = f"refresh returned {len(rows)} rows against {old} stored: kept the stored bundle"
                else:
                    e = _store(archive, hb, rows, history_recipe(s, meta), HISTORY_TAGS, HISTORY_SCHEMA, in_git=False)
                    info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            rep[hb] = info
            if events and need_e:
                e = _store(archive, eb, erows, events_recipe(s, meta), EVENTS_TAGS, EVENTS_SCHEMA, in_git=False)
                rep[eb] = {"stored": {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}, "dividends": len(ev["dividends"]), "splits": len(ev["splits"])}
            if log:
                log(f"{s}: {len(rows)} bars, {len(erows)} events")
    finally:
        if own:
            c.close()
    return rep


def fetch_hourly_histories(store=None, symbols: Optional[Iterable[str]] = None, dry_run: bool = False, limit: Optional[int] = None,
                           skip_stored: bool = True, refresh: bool = False, min_interval: float = YAHOO_INTERVAL, retries: int = 4,
                           backoff: float = 2.0, client: Optional[httpx.Client] = None, report: Optional[dict] = None, log=None) -> dict:
    """``hourly-<SYM>`` (Yahoo 1h, about 730 sessions), the fetch_hourly recipe and rows, merged with the stored bundle.
    Stored bundles are skipped unless ``refresh=True`` (then the fresh window is merged in)."""
    syms = list(dict.fromkeys(yahoo_symbol(s) for s in (symbols if symbols is not None else HOURLY_SYMBOLS)))
    archive = _archive(store)
    rep = report if report is not None else {}
    todo = []
    for s in syms:
        if skip_stored and not refresh and _stored_here(archive, hourly_bundle(s)):
            rep[hourly_bundle(s)] = {"skipped": "stored"}
            continue
        todo.append(s)
    if limit is not None:
        todo = todo[:limit]
    rep["_plan"] = [_plan_row(hourly_bundle(s), "fetch_hourly_histories", theories_for("hourly", s), False, "Yahoo Finance terms (no redistribution)",
                              1, estimate_hourly_rows(s), "hourly", min_interval, HOURLY_RULE, False) for s in todo]
    if dry_run:
        return rep
    own = client is None
    c = client or _client(timeout=90)
    th = Throttle(min_interval)
    try:
        for s in todo:
            name = hourly_bundle(s)
            res, info = yahoo_chart(s, {"range": "730d", "interval": "1h"}, c, th, retries=retries, backoff=backoff)
            cutoff = time.time()
            if res is None:
                rep[name] = info
                continue
            new = {t: v for t, v in parse_hourly(res, s).items() if t + 3600 <= cutoff}
            if not new:
                info["error"] = "no complete 1h bar: not stored"
                rep[name] = info
                continue
            fresh = len(new)
            for row in _load(archive, name) if archive is not None else []:
                new.setdefault(int(row["value"]["t"]), row["value"])
            rows = hourly_rows(new)
            info.update(fresh_bars=fresh, rows=len(rows), first=rows[0]["observed_at"][:10], last=rows[-1]["observed_at"][:10],
                        currency=(res.get("meta") or {}).get("currency"))
            if archive is None:
                info["rows"] = rows
            else:
                e = _store(archive, name, rows, hourly_recipe(s, res.get("meta")), HOURLY_TAGS, HOURLY_SCHEMA, in_git=False)
                info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            rep[name] = info
            if log:
                log(f"{s}: {len(rows)} hourly bars")
    finally:
        if own:
            c.close()
    return rep


# ====================================================================================================== FRED ==

def fred_meta(sid: str, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 2.0) -> dict:
    """Licence, source, release, title and frequency from the FRED series page."""
    r, info = _get(client, FRED_PAGE.format(sid=sid), throttle, retries=retries, backoff=backoff)
    out: dict = {"calls": info.get("attempts", 0)}
    if r is None:
        out["error"] = info.get("error") or f"HTTP {info.get('status')}"
        return out
    return {**out, **parse_fred_page(r.text)}


def parse_fred_page(text: str) -> dict:
    def grab(pat):
        m = re.search(pat, text, re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    out = {"license": grab(r'"license"\s*:\s*"([^"]+)"'),
           "title": grab(r'"license"\s*:\s*"[^"]+",\s*"name"\s*:\s*"([^"]+)"'),
           "source": grab(r"<strong>Source:</strong>\s*(?:<a[^>]*>)?\s*([^<]+?)\s*<"),
           "release": grab(r"<strong>Release:</strong>\s*(?:<a[^>]*>)?\s*([^<]+?)\s*<"),
           "frequency": (grab(r'series-meta-value-frequency">\s*([^<]+?)\s*<') or "").rstrip(", ") or None,
           "copyright": grab(r"(Copyright[^<\"]{0,160})")}
    return {k: v for k, v in out.items() if v}


def fred_in_git(meta: dict) -> bool:
    """True only for a public-domain series from a US federal agency, as the live page states it."""
    return bool(meta.get("license", "").endswith(PUBLIC_DOMAIN) and meta.get("source") in FEDERAL_SOURCES and not meta.get("error"))


def _licence_text(sid: str, meta: dict) -> str:
    if meta.get("error") or not meta.get("license"):
        return f"licence not read ({meta.get('error', 'no licence on the page')}); expected: {FRED_EXPECTED.get(sid, ('unknown', False))[0]}; kept out of git"
    return (f"licence {meta.get('license')}; source {meta.get('source')}; release {meta.get('release')}"
            + (f"; {meta['copyright']}" if meta.get("copyright") else "") + ("" if fred_in_git(meta) else "; not federal public domain: never in git"))


def fred_rows_retry(sid: str, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 2.0) -> tuple[list[dict], int]:
    """mandel.data.options.fred_series (the fred-DTB3 parser) with retries: FRED sometimes answers HTTP/2 errors or empty bodies."""
    calls = 0
    for attempt in range(retries):
        calls += 1
        try:
            rows = fred_series(sid, client, throttle)
        except httpx.HTTPError:
            rows = []
        if rows:
            return rows, calls
        _sleep(backoff * 2 ** attempt)
    return [], calls


def _is_daily(rows: list[dict], meta: dict) -> bool:
    f = (meta.get("frequency") or "").lower()
    if f:
        return f.startswith("daily")
    days = [date.fromisoformat(r["day"]) for r in rows[-60:]]
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    return bool(gaps) and gaps[len(gaps) // 2] <= 4


def _months_per_period(meta: dict, rows: list[dict]) -> int:
    f = (meta.get("frequency") or "").lower()
    if f.startswith("quarter"):
        return 3
    if f.startswith("annual"):
        return 12
    if f.startswith("month"):
        return 1
    days = [date.fromisoformat(r["day"]) for r in rows[-24:]]
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    g = gaps[len(gaps) // 2] if gaps else 31
    return 3 if g > 80 else 12 if g > 300 else 1


def alfred_realtime(sid: str, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 2.0) -> tuple[list[dict], dict]:
    """Every real-time period of every observation: [{day, value (None when blank), realtime_start, realtime_end (None when
    open)}], from the downloaddata form (GET for the vintage list, one POST for 'Observations by Real-Time Period')."""
    info: dict = {"calls": 0}
    r, i = _get(client, ALFRED_DOWNLOAD, throttle, params={"seid": sid}, retries=retries, backoff=backoff)
    info["calls"] += i.get("attempts", 0)
    if r is None:
        info["error"] = i.get("error") or f"HTTP {i.get('status')}"
        return [], info
    page = r.text
    vintages = sorted(set(re.findall(r'<option[^>]*value="(\d{4}-\d{2}-\d{2})"', page)))
    start = re.search(r'name="form\[obs_start_date\]"[^>]*value="([^"]+)"', page)
    end = re.search(r'name="form\[obs_end_date\]"[^>]*value="([^"]+)"', page)
    if not vintages or not start or not end:
        info["error"] = "no vintage list on the ALFRED page"
        return [], info
    info.update(vintages=len(vintages), first_vintage=vintages[0], last_vintage=vintages[-1])
    form = {"form[units]": "lin", "form[obs_start_date]": start.group(1), "form[obs_end_date]": end.group(1), "form[file_type]": "1",
            "form[file_format]": "csv", "form[entered_vintage_dates]": "", "form[download_data]": "", "form[selected_vintage_dates][]": vintages}
    r2, i2 = _post(client, ALFRED_DOWNLOAD, throttle, data=form, params={"seid": sid}, retries=retries, backoff=backoff)
    info["calls"] += i2.get("attempts", 0)
    if r2 is None:
        info["error"] = i2.get("error") or f"HTTP {i2.get('status')}"
        return [], info
    try:
        z = zipfile.ZipFile(io.BytesIO(r2.content))
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8", "replace")
    except (zipfile.BadZipFile, StopIteration, KeyError) as e:
        info["error"] = f"not a zipped CSV: {e!r}"[:200]
        return [], info
    return parse_alfred_csv(text, sid), info


def parse_alfred_csv(text: str, sid: str) -> list[dict]:
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        day = row.get("period_start_date") or row.get("observation_date")
        rs = row.get("realtime_start_date")
        if not day or not rs:
            continue
        v = row.get(sid)
        try:
            val = float(v) if v not in (None, "", ".") else None
        except ValueError:
            val = None
        out.append({"day": day, "value": val, "realtime_start": rs, "realtime_end": row.get("realtime_end_date") or None})
    return out


def alfred_rows(sid: str, periods: list[dict], months: int) -> list[dict]:
    first_vintage = min((p["realtime_start"] for p in periods), default=None)
    first_seen: dict[str, str] = {}
    for p in periods:
        if p["value"] is not None and (p["day"] not in first_seen or p["realtime_start"] < first_seen[p["day"]]):
            first_seen[p["day"]] = p["realtime_start"]
    rows = []
    for p in sorted(periods, key=lambda x: (x["day"], x["realtime_start"])):
        fv = p["realtime_start"] == first_vintage
        lag = lag_rule_at(sid, p["day"], months) if fv else None
        value = {"day": p["day"], "value": p["value"], "realtime_start": p["realtime_start"], "realtime_end": p["realtime_end"],
                 "first_release": p["value"] is not None and first_seen.get(p["day"]) == p["realtime_start"], "first_vintage": fv,
                 "lag_rule_at": lag if lag and lag < release_at(sid, p["realtime_start"]) else None}
        rows.append(Observation("alfred", "vintage", f"{sid}:{p['day']}:{p['realtime_start']}", observed_at=p["day"] + "T00:00:00+00:00",
                                available_at=release_at(sid, p["realtime_start"]), value=value).row())
    return rows


def fred_daily_rows(sid: str, rows: list[dict]) -> list[dict]:
    """Exactly the fred-DTB3 rows of mandel.data.options.collect_options_history."""
    return [Observation("fred", "series", sid, observed_at=r["day"] + "T00:00:00+00:00", available_at=r["day"] + "T20:00:00+00:00", value=r).row()
            for r in rows]


def fred_revised_rows(sid: str, rows: list[dict], periods: list[dict], captured: str) -> list[dict]:
    current = {p["day"]: p for p in periods if p["realtime_end"] is None and p["value"] is not None}
    out = []
    for r in rows:
        p = current.get(r["day"])
        if p is not None and abs(p["value"] - r["value"]) <= 1e-9 * max(1.0, abs(r["value"])):
            avail, basis, rs = release_at(sid, p["realtime_start"]), "alfred-current-vintage", p["realtime_start"]
        else:
            avail, basis, rs = captured, "capture", None
        out.append(Observation("fred", "series", sid, observed_at=r["day"] + "T00:00:00+00:00", available_at=avail,
                               value={**r, "realtime_start": rs, "available_basis": basis}).row())
    return out


def _fred_recipe(sid: str, meta: dict, daily: bool) -> str:
    base = f"{FRED_GRAPH}?id={sid}"
    if daily:
        return f"{base} (via mandel.data.market_history.fetch_fred_series; available_at = day 20:00 UTC, the fred-DTB3 convention). {_licence_text(sid, meta)}"
    return (f"{base} (latest vintage; REVISED series) joined to {ALFRED_DOWNLOAD}?seid={sid} 'Observations by Real-Time Period': available_at = "
            f"the release of the stored value (its ALFRED realtime_start, {RELEASE_TIME_ET.get(sid, 'end of the UTC day')} "
            f"{'ET' if sid in RELEASE_TIME_ET else ''}), capture time when ALFRED lacks it; first releases in {alfred_bundle(sid)}; via "
            f"mandel.data.market_history.fetch_fred_series. {_licence_text(sid, meta)}")


def _alfred_recipe(sid: str, meta: dict, ainfo: dict) -> str:
    return (f"POST {ALFRED_DOWNLOAD}?seid={sid} with every vintage date selected ({ainfo.get('vintages')} vintages {ainfo.get('first_vintage')}.."
            f"{ainfo.get('last_vintage')}), form[file_type]=1 (Observations by Real-Time Period), form[file_format]=csv; via "
            f"mandel.data.market_history.fetch_fred_series. available_at = realtime_start at {RELEASE_TIME_ET.get(sid, '23:59:59 UTC (time not recorded)')}"
            f"{' ET' if sid in RELEASE_TIME_ET else ''}. Observations dated before the first vintage carry first_vintage=true (true first release "
            f"unknown) and lag_rule_at = period end + {LAG_RULE_DAYS.get(sid, 'n/a')} days (an approximation, not point in time). {_licence_text(sid, meta)}")


ALFRED_SCHEMA = ("value = {day (period start), value (None = blank in that vintage), realtime_start, realtime_end (None = still current), "
                 "first_release (earliest non-blank period of the observation), first_vintage (period starts on the first ALFRED vintage), "
                 "lag_rule_at (release-lag estimate for first_vintage rows, look-ahead approximation)}")
FRED_REVISED_SCHEMA = "value = {day, value (latest vintage), realtime_start (ALFRED publication of this value), available_basis}"


def fetch_fred_series(store=None, series: Optional[Iterable[str]] = None, dry_run: bool = False, limit: Optional[int] = None,
                      skip_stored: bool = True, refresh: bool = False, alfred: bool = True, min_interval: float = FRED_INTERVAL,
                      retries: int = 4, backoff: float = 2.0, client: Optional[httpx.Client] = None, report: Optional[dict] = None,
                      log=None) -> dict:
    """``fred-<SID>`` for every series (the fred-DTB3 recipe) and, for non-daily (revised, released-later) series,
    ``alfred-<SID>`` with every real-time period. Licence and in_git come from the live series page."""
    sids = list(dict.fromkeys(series if series is not None else FRED_SERIES))
    archive = _archive(store)
    rep = report if report is not None else {}
    todo = []
    for sid in sids:
        daily_expected = sid.startswith("DGS") or sid in ("DFII10", "BAA10Y")
        have_f, have_a = _stored_here(archive, fred_bundle(sid)), _stored_here(archive, alfred_bundle(sid))
        if skip_stored and not refresh and have_f and (daily_expected or not alfred or have_a):
            rep[fred_bundle(sid)] = {"skipped": "stored"}
            continue
        todo.append((sid, daily_expected))
    if limit is not None:
        todo = todo[:limit]
    plan = []
    for sid, daily in todo:
        lic, git = FRED_EXPECTED.get(sid, ("unknown (read at fetch)", False))
        n, na = FRED_ROWS_EST.get(sid, (16000, 0) if daily else (1000, 3000))
        plan.append(_plan_row(fred_bundle(sid), "fetch_fred_series", theories_for("fred", sid), git, lic, 2, n, "fred", min_interval,
                              FRED_DAILY_RULE if daily else FRED_REVISED_RULE, False))
        if alfred and not daily:
            plan.append(_plan_row(alfred_bundle(sid), "fetch_fred_series", theories_for("fred", sid), git, lic, 2, na, "alfred", min_interval,
                                  ALFRED_RULE, False))
    rep["_plan"] = plan
    if dry_run:
        return rep
    own = client is None
    c = client or _client(timeout=180)
    th = Throttle(min_interval)
    try:
        for sid, _ in todo:
            meta = fred_meta(sid, c, th, retries=retries, backoff=backoff)
            rows, calls = fred_rows_retry(sid, c, th, retries=retries, backoff=backoff)
            captured = now_iso()
            info: dict = {"calls": meta.get("calls", 0) + calls, "license": meta.get("license"), "source": meta.get("source"),
                          "frequency": meta.get("frequency"), "in_git": fred_in_git(meta)}
            if meta.get("error"):
                info["meta_error"] = meta["error"]
            if not rows:
                info["error"] = "fredgraph.csv returned no rows"
                rep[fred_bundle(sid)] = info
                continue
            daily = _is_daily(rows, meta)
            info.update(daily=daily, rows=len(rows), first=rows[0]["day"], last=rows[-1]["day"])
            in_git = fred_in_git(meta)
            if daily:
                frows = fred_daily_rows(sid, rows)
                tags, schema = FRED_DAILY_TAGS if sid.startswith(("DGS", "DFII", "DTB", "DFF")) else ["fred", "history", FRED_TAGS.get(sid, "rates")], "value = {day, value}"
            else:
                periods, ainfo = alfred_realtime(sid, c, th, retries=retries, backoff=backoff) if alfred else ([], {"error": "alfred disabled"})
                info["alfred"] = {k: v for k, v in ainfo.items()}
                info["calls"] += ainfo.get("calls", 0)
                frows = fred_revised_rows(sid, rows, periods, captured)
                info["capture_stamped"] = sum(1 for r in frows if r["value"]["available_basis"] == "capture")
                tags, schema = ["fred", "history", "revised", FRED_TAGS.get(sid, "rates")], FRED_REVISED_SCHEMA
                if periods:
                    arows = alfred_rows(sid, periods, _months_per_period(meta, rows))
                    if archive is None:
                        rep[alfred_bundle(sid)] = {"rows": arows}
                    else:
                        e = _store(archive, alfred_bundle(sid), arows, _alfred_recipe(sid, meta, ainfo), ["alfred", "vintages", "history", FRED_TAGS.get(sid, "rates")],
                                   ALFRED_SCHEMA, in_git=in_git)
                        rep[alfred_bundle(sid)] = {"stored": {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}, **ainfo}
            if archive is None:
                info["rows"] = frows
            else:
                e = _store(archive, fred_bundle(sid), frows, _fred_recipe(sid, meta, daily), tags, schema, in_git=in_git)
                info["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git}
            rep[fred_bundle(sid)] = info
            if log:
                log(f"{sid}: {len(rows)} rows, daily={daily}, in_git={in_git}")
    finally:
        if own:
            c.close()
    return rep


# ============================================================================================== entry point ==

def fetch_all_yahoo_fred(store, dry_run: bool = False, limit: Optional[int] = None, stock_symbols: Optional[Iterable[str]] = None,
                         sources: Iterable[str] = ("daily", "hourly", "fred"), refresh: bool = False, yahoo_interval: float = YAHOO_INTERVAL,
                         fred_interval: float = FRED_INTERVAL, report: Optional[dict] = None, log=None) -> dict:
    """Every Yahoo and FRED/ALFRED bundle the yahoo_fred source group covers (``THEORY_NEEDS``), resumable: bundles stored
    on this machine are skipped. ``stock_symbols`` adds a single-stock universe (from another group's list) to the daily
    fetch. ``limit`` caps the bundles fetched per source. Returns {source: report} plus '_plan' (every bundle's estimate)
    and '_totals'."""
    rep = report if report is not None else {}
    src = set(sources)
    if "daily" in src:
        syms = DAILY_SYMBOLS + [yahoo_symbol(s) for s in (stock_symbols or [])]
        rep["daily"] = fetch_daily_histories(store, syms, dry_run=dry_run, limit=limit, refresh=refresh, min_interval=yahoo_interval, log=log)
    if "hourly" in src:
        rep["hourly"] = fetch_hourly_histories(store, HOURLY_SYMBOLS, dry_run=dry_run, limit=limit, refresh=refresh, min_interval=yahoo_interval, log=log)
    if "fred" in src:
        rep["fred"] = fetch_fred_series(store, FRED_SERIES, dry_run=dry_run, limit=limit, refresh=refresh, min_interval=fred_interval, log=log)
    plan = [p for k in ("daily", "hourly", "fred") if k in rep for p in rep[k].get("_plan", [])]
    rep["_plan"] = plan
    rep["_totals"] = {"bundles": len(plan), "calls": sum(p["calls"] for p in plan), "rows": sum(p["rows"] for p in plan),
                      "gz_mb": round(sum(p["gz_mb"] for p in plan), 2), "minutes": round(sum(p["minutes"] for p in plan), 1),
                      "local_only": sum(1 for p in plan if not p["in_git"])}
    return rep


def gitignore_block(plan: list[dict]) -> str:
    lines = [p["gitignore_line"] for p in plan if p.get("gitignore_line")]
    return "\n".join(dict.fromkeys(lines))


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m mandel.data.market_history",
                                description="Yahoo daily/hourly histories and FRED/ALFRED series for the batch-6c underlying claims.")
    p.add_argument("source", choices=["all", "daily", "hourly", "fred"])
    p.add_argument("--dry-run", action="store_true", help="no request: print the plan (calls, rows, gzip MB, minutes) and the .gitignore lines")
    p.add_argument("--preview", metavar="DIR", help="store into a scratch archive under DIR (DIR/archive, DIR/ledger.jsonl), not the real one")
    p.add_argument("--limit", type=int, help="first N bundles per source")
    p.add_argument("--refresh", action="store_true", help="re-fetch stored bundles (daily: replace; hourly: merge)")
    p.add_argument("--symbols", help="comma-separated Yahoo symbols (daily/hourly) or FRED ids (fred) instead of the default lists")
    p.add_argument("--symbols-file", help="extra single-stock tickers for the daily fetch (one per line or CSV first column)")
    p.add_argument("--symbols-bundle", metavar="NAME[:FIELD]", help="extra tickers for the daily fetch from an archived bundle (value[FIELD], else the row key)")
    p.add_argument("--yahoo-interval", type=float, default=YAHOO_INTERVAL)
    p.add_argument("--fred-interval", type=float, default=FRED_INTERVAL)
    a = p.parse_args(argv)
    from mandel.archive import Archive
    if a.preview:
        from mandel.ledger import Ledger
        root = Path(a.preview)
        store = Archive(root=root / "archive", ledger=Ledger(root / "ledger.jsonl"))
    else:
        store = Archive()
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    extra = read_symbols(a.symbols_file) if a.symbols_file else []
    if a.symbols_bundle:
        bname, _, field = a.symbols_bundle.partition(":")
        extra += [s for s in symbols_from_bundle(store, bname, field or None) if s not in extra]
    chosen = [x.strip() for x in a.symbols.split(",")] if a.symbols else None
    if a.source == "all":
        rep = fetch_all_yahoo_fred(store, dry_run=a.dry_run, limit=a.limit, stock_symbols=extra, refresh=a.refresh,
                                   yahoo_interval=a.yahoo_interval, fred_interval=a.fred_interval, log=log)
    elif a.source == "daily":
        rep = fetch_daily_histories(store, (chosen or DAILY_SYMBOLS) + extra, dry_run=a.dry_run, limit=a.limit, refresh=a.refresh,
                                    min_interval=a.yahoo_interval, log=log)
    elif a.source == "hourly":
        rep = fetch_hourly_histories(store, chosen, dry_run=a.dry_run, limit=a.limit, refresh=a.refresh, min_interval=a.yahoo_interval, log=log)
    else:
        rep = fetch_fred_series(store, chosen, dry_run=a.dry_run, limit=a.limit, refresh=a.refresh, min_interval=a.fred_interval, log=log)
    plan = rep.get("_plan", [])
    if a.preview:
        root = Path(a.preview)
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{a.source}.report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
        (root / f"{a.source}.gitignore.txt").write_text(gitignore_block(plan) + "\n", encoding="utf-8")
    summary = {k: v for k, v in rep.items() if k.startswith("_") and k != "_plan"}
    summary["plan_bundles"] = len(plan)
    summary["results"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("rows", "_plan")} if isinstance(v, dict) else v
                          for k, v in rep.items() if not k.startswith("_")}
    print(json.dumps(summary, indent=1, default=str)[:20000])
    if a.dry_run:
        print(gitignore_block(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
