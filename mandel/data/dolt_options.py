"""
DoltHub options history: daily option chains and volatility history since 2019, free and keyless.
=================================================================================================

Source: the public DoltHub SQL API on the ``post-no-preference/options`` database (no key, read only):
  GET https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q=<SQL>
Licence: CC BY-SA 4.0 (LICENSE.md in the database's ``dolt_docs`` table). Redistribution is allowed with attribution
("post-no-preference via DoltHub") under the same licence (ShareAlike), so both bundles may be in git; their recipes carry
the attribution, the list of changes and the ShareAlike note (``LICENCE_NOTE``), and their tags include ``cc-by-sa-4.0``.
Tables:
  * ``option_chain(date, act_symbol, expiration, strike, call_put, bid, ask, vol, delta, gamma, theta, vega, rho)``:
    a thin end-of-day chain per symbol (SPY: 3-4 expiries at 11-66 DTE, about 11-27 strikes each side, 60-210 rows per
    date). Quotes and model greeks only: no trades, volume or open interest.
  * ``volatility_history(date, act_symbol, hv_current, hv_week_ago, hv_month_ago, hv_year_high, hv_year_high_date,
    hv_year_low, hv_year_low_date, iv_current, iv_week_ago, iv_month_ago, iv_year_high, iv_year_high_date, iv_year_low,
    iv_year_low_date)``.
  Coverage (probed 2026-10-15): about 1,500 US stocks plus SPDR ETFs only (SPY, DIA, MDY, the XL* sectors, XBI, XHB,
  XOP, XRT, KRE). QQQ, IWM, GLD, TLT, SLV and USO are NOT in the database on any date sampled from 2019 to 2026.
  Dates run from 2019-02-09 to the latest close: Saturdays only in 2019, Mon/Wed/Fri 2020-2023 (some Tue/Thu from
  mid-2024), every trading day from 2025.

API behaviour (probed 2026-10-15):
  * every response is capped at 1000 rows (status ``RowLimit``); a query running longer than about 55 s fails with
    status ``Error`` / ``context deadline exceeded`` (sometimes after returning a partial prefix of rows).
  * both primary keys start with ``date``, so a symbol filter over a date range, ``MIN(date)``, ``DISTINCT date`` and
    multi-day aggregates time out. Point lookups on ``(date, act_symbol)`` are fast (about 2 s), even with a long
    ``IN`` list. The fetchers therefore walk the calendar in windows,
    ``act_symbol IN (...) AND date IN (<every calendar day of the window>)``: non-trading days cost nothing, no date
    enumeration is needed, and a window that hits the row cap or the deadline is halved and retried.
  * the commit log (``dolt_log``, about 2,150 commits) names each daily load ``<table> <date> update``; since 2021-04-20
    these land at about 06:35 UTC the next morning. Reading it costs about 30-35 calls and 10-15 minutes (one pass reads
    both tables and is cached for an hour). Every date before 2021-04-20 came from a bulk import between 2021-04-20T23:20Z
    and 2021-04-21T01:12:31Z (commits named '2019-03-01', '2019-04-01' and '2021-04-20 update', whose names do not match
    the dates they loaded), so all of them get ``BULK_IMPORT_AT`` = 2021-04-21T01:13Z.

Point in time. ``date`` is the snapshot date, not always the quote date. Measured 2026-10-15:
  * volatility_history: ``hv_current`` equals the 30-session sample standard deviation of log close-to-close returns
    x sqrt(252) ending on the last NYSE trading day on or before the snapshot date, to all 4 decimals, for 592 of 595
    SPY snapshots (2019-2026; every weekday and all 47 Saturdays), and likewise for the sector SPDRs.
  * option_chain: put-call parity on near-ATM strikes (spot = (K + (C_mid - P_mid) e^{rT}) e^{-(r-q)T}, two nearest
    expiries, DTB3 rates) against SPY closes: on dates where the neighbouring sessions' closes differ from the rule's
    close by >= 0.5%, the rule's session is the best match for 96.6% (112 of 116); the misses are previous-session or
    intraday captures, or noise.
So ``quote_date`` = the last NYSE trading day on or before ``snapshot_date`` (a Saturday or holiday snapshot quotes the
previous session) unless the stale check below moves it, and ``available_at`` = 22:00 UTC (after the 16:15 ET options
close) on the later of the snapshot date and the quote date. The quotes were publicly knowable to market participants
at that close, so DoltHub's publication time is provenance, not a point-in-time constraint, and never moves
``available_at``:
  * ``dolt_commit_at`` = the LAST named ``<table> <date> update`` commit for the snapshot date (a re-run replaces a date's
    rows: SPY 2021-07-09 had no rows at the on-time 2021-07-10T06:45Z commit and was loaded by the re-run at
    2021-07-14T21:47Z); ``BULK_IMPORT_AT`` before 2021-04-20; None when no commit names a live-era date or the log was
    not read.
  * ``backfilled`` = that commit came after the next session's 13:30 UTC open (True/False); False for the bulk era;
    None (unknown) when ``dolt_commit_at`` is None. It is per date and per table, not per symbol.
  Known gaps in that provenance (AS OF scan by the checker, 2026-10-15): 24 live-era SPY dates have no named commit, and
  16 of them were first published late by a commit named for another date (2021-05-17, 2021-05-27, 2021-06-02,
  2021-08-16, 2021-09-22, 2023-03-08, 2023-03-15, 2024-02-07, 2024-05-15, 2025-02-26, 2025-03-21, 2025-08-13,
  2025-10-08/09/10 at 2025-10-14T19:34Z, 2026-08-31), 18 hours to 6 days after the snapshot. Their content is still
  dated correctly (hv_current matches the rule session on all of them). The module does not run that ~105-call scan.
``observed_at`` is when Mandel fetched the row.

Stale-snapshot check (``stale``, ``stale_basis``). Some snapshots quote another session (about 2-4% of chain dates:
stale previous-session or intraday captures). Each snapshot is compared with the raw (split-adjusted) closes of the
previous, rule and next NYSE sessions, from the archive's ``daily-history-<SYM>`` bundle (read only) or passed in:
  * option_chain: the parity spot (DTB3 rate from ``fred-DTB3`` on the rule session, dividend yield ``div_yield``,
    default 1.3% for SPY) is matched to the nearest close. When that close is not the rule session's, the snapshot is
    moved only when the match is decisive: every other candidate close is at least ``MIN_GAP`` (0.5%) away from the
    matched close, and the parity noise (the larger of the match error and the per-expiry estimates' deviation from
    their median) is at most ``NOISE_FRAC`` (one third) of that gap, so the matched close fits at least twice as well
    as any other.
  * volatility_history: ``hv_current`` must equal the 30-session close-to-close vol ending on exactly one candidate
    session (within ``HV_TOL``, the source's 4-decimal rounding). Rows whose symbol has no daily-history bundle are not
    checked.
  A decisive non-rule match sets ``quote_date`` to that session, ``stale`` = True and a ``stale_basis`` text, and
  ``available_at`` follows the rule above (a next-session match moves it to that session's evening; a previous-session
  match leaves it on the snapshot evening). A rule-session match or an undecidable one keeps the rule (``stale`` =
  False); ``stale`` = None means not checked (no closes or no usable quotes). The flag is a fetch-time data-quality
  label computed with closes up to the next session: do not use it as a signal on the snapshot date.
  Replayed offline on 2026-10-15 recordings: of 472 SPY chain snapshots (2019-2026) it moved 3 to the previous session
  (2025-03-24, 2026-06-11, 2026-06-16), matched the rule on 364 and kept the rule on 105 undecidable ones (mostly closes
  under 0.5% apart; also intraday captures such as 2026-03-13, which sits between the prior close and the next one); of
  1,183 vol rows (SPY and the 9 sector SPDRs) it moved none: the rule session matched 1,177 and 6 matched no candidate.
"""

from __future__ import annotations

import bisect
import json
import math
import re
import statistics
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

import httpx

from mandel.data.fetch import Throttle, now_iso

UA = {"User-Agent": "mandel-substrate research bot (contact: https://github.com/pointlessbassmusic-byte/polymarket-arbitrage/issues)"}
DOLT = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"
DOLT_REPO = "https://www.dolthub.com/repositories/post-no-preference/options"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
LICENCE_NOTE = (f"Licence CC BY-SA 4.0 ({LICENCE_URL}; post-no-preference/options on DoltHub, LICENSE.md in dolt_docs). "
                f"Attribution: post-no-preference via DoltHub ({DOLT_REPO}). Changes: {{changes}}. ShareAlike: this bundle is an "
                "adaptation redistributed under CC BY-SA 4.0; anything shared that is built from it must carry the same licence and "
                "this attribution.")
FIRST_DAY = "2019-02-09"                       # the first date in either table
LIVE_START = "2021-04-20"                      # first date loaded by a daily commit; earlier dates came from the bulk import
ROW_CAP = 1000                                 # DoltHub returns at most this many rows ('RowLimit')
BULK_IMPORT_AT = "2021-04-21T01:13:00+00:00"   # after the last bulk-import commit (volatility_history, 2021-04-21T01:12:31Z)
EVENING_UTC = "T22:00:00+00:00"                # after the 16:15 ET options close in both EST and EDT
MIN_GAP = 0.005                                # stale check: candidate closes must be at least this far apart
NOISE_FRAC = 1 / 3                             # stale check: parity noise at most this fraction of the gap
HV_TOL = 0.00006                               # stale check: half a 4-decimal unit plus 1e-5 for close-price precision
HV_MOVE_MARGIN = 2 * HV_TOL                    # a vol row moves only when the rule session misses by more than this
DEFAULT_RATE = 0.02                            # parity rate when no DTB3 value is available
SPY_DIV_YIELD = 0.013
VOL_SYMBOLS = ["SPY", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "QQQ", "IWM", "GLD", "TLT", "SLV", "USO"]
NOT_COVERED = {"QQQ", "IWM", "GLD", "TLT", "SLV", "USO"}     # absent from both tables on every probed date (2019-2026)
CHAIN_COLUMNS = ("bid", "ask", "vol", "delta", "gamma", "theta", "vega", "rho")
VOL_NUMERIC = ("hv_current", "hv_week_ago", "hv_month_ago", "hv_year_high", "hv_year_low",
               "iv_current", "iv_week_ago", "iv_month_ago", "iv_year_high", "iv_year_low")
VOL_DATES = ("hv_year_high_date", "hv_year_low_date", "iv_year_high_date", "iv_year_low_date")
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.\-/]{0,11}$")
_sleep = time.sleep                            # patched in tests


def _client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=90, follow_redirects=True)


def _check_symbol(sym: str) -> str:
    s = (sym or "").strip().upper()
    if not _SYMBOL.match(s):
        raise ValueError(f"not a ticker: {sym!r}")
    return s


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ NYSE calendar --

UNSCHEDULED_CLOSURES = {"2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14", "2004-06-11", "2007-01-02",
                        "2012-10-29", "2012-10-30", "2018-12-05", "2025-01-09"}


def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def _nth_weekday(y: int, m: int, wd: int, n: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(wd - d.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(y: int, m: int, wd: int) -> date:
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def nyse_holidays(year: int) -> set[date]:
    """Full-day NYSE closures by rule (New Year's Day is not moved back to a Friday when it falls on a Saturday),
    plus the unscheduled closures. Early closes are trading days."""
    h = set()
    ny = date(year, 1, 1)
    if ny.weekday() == 6:
        h.add(date(year, 1, 2))
    elif ny.weekday() < 5:
        h.add(ny)
    if year >= 1998:
        h.add(_nth_weekday(year, 1, 0, 3))
    h.add(_nth_weekday(year, 2, 0, 3))
    h.add(_easter(year) - timedelta(days=2))
    h.add(_last_weekday(year, 5, 0))
    if year >= 2022:
        h.add(_observed(date(year, 6, 19)))
    h.add(_observed(date(year, 7, 4)))
    h.add(_nth_weekday(year, 9, 0, 1))
    h.add(_nth_weekday(year, 11, 3, 4))
    h.add(_observed(date(year, 12, 25)))
    h |= {date.fromisoformat(d) for d in UNSCHEDULED_CLOSURES if d.startswith(str(year))}
    return h


_HOL_CACHE: dict[int, set[date]] = {}


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if d.year not in _HOL_CACHE:
        _HOL_CACHE[d.year] = nyse_holidays(d.year)
    return d not in _HOL_CACHE[d.year]


def quote_date_for(snapshot_date: str) -> str:
    """The session whose close a snapshot quotes: the last NYSE trading day on or before the snapshot date."""
    d = date.fromisoformat(snapshot_date)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d.isoformat()


def next_session(day: str) -> str:
    """The first NYSE trading day after ``day``."""
    d = date.fromisoformat(day) + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d.isoformat()


def prev_session(day: str) -> str:
    """The last NYSE trading day before ``day``."""
    return quote_date_for((date.fromisoformat(day) - timedelta(days=1)).isoformat())


def available_at_for(snapshot_date: str, quote_date: Optional[str] = None) -> str:
    """The evening of the later of the snapshot date and the quote date (never earlier than the quote date's close)."""
    q = quote_date or quote_date_for(snapshot_date)
    return max(snapshot_date, q) + EVENING_UTC


# ------------------------------------------------------------------ SQL transport --

def dolt_sql(sql: str, client: httpx.Client, throttle: Throttle, retries: int = 4, retry_deadline: bool = True) -> dict:
    """One query. Returns {"status": Success|RowLimit|Error, "message", "rows"}. HTTP errors and 429/5xx are retried
    with a growing backoff; 'context deadline exceeded' too unless ``retry_deadline`` is False (a caller that can split
    the query instead); other SQL errors return at once. An Error result may still carry a partial prefix of rows;
    callers must not treat it as complete."""
    last = {"status": "Error", "message": "no response", "rows": []}
    for attempt in range(retries):
        throttle.wait()
        try:
            r = client.get(DOLT, params={"q": sql})
            if r.status_code == 429 or r.status_code >= 500:
                last = {"status": "Error", "message": f"HTTP {r.status_code}", "rows": []}
                _sleep(3.0 * (attempt + 1))
                continue
            r.raise_for_status()
            j = r.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
            last = {"status": "Error", "message": f"{type(e).__name__}: {e}", "rows": []}
            _sleep(2.0 * (attempt + 1))
            continue
        out = {"status": j.get("query_execution_status") or "Error", "message": j.get("query_execution_message") or "", "rows": j.get("rows") or []}
        if out["status"] in ("Success", "RowLimit"):
            return out
        last = out
        if not retry_deadline or ("deadline" not in out["message"].lower() and "timeout" not in out["message"].lower()):
            return out
        _sleep(3.0 * (attempt + 1))
    return last


def _days(start: date, n: int) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _in(values: Iterable[str]) -> str:
    return ",".join(f"'{v}'" for v in values)


def walk_windows(client: httpx.Client, throttle: Throttle, make_sql: Callable[[list[str]], str], start: str, end: str,
                 window: int = 10, max_window: int = 31, target_rows: int = 700, limit_days: Optional[int] = None,
                 page_day: Optional[Callable[[str, int], str]] = None, stats: Optional[dict] = None) -> list[dict]:
    """Walk [start, end] in calendar windows; each query covers every calendar day of its window. A window that hits
    the row cap or fails is halved; a single day over the cap is paged with ``page_day(day, offset)`` when given.
    The next window is sized so its expected row count is about ``target_rows``. ``limit_days`` stops after that many
    distinct snapshot dates (rows beyond the first ``limit_days`` dates are dropped)."""
    st = stats if stats is not None else {}
    st.setdefault("calls", 0); st.setdefault("splits", 0); st.setdefault("failed_days", []); st.setdefault("windows", 0)
    cur, last = date.fromisoformat(start), date.fromisoformat(end)
    out: list[dict] = []
    order: dict[str, int] = {}                 # snapshot date -> order of first appearance
    w = max(1, window)
    while cur <= last:
        w = max(1, min(w, (last - cur).days + 1))
        days = _days(cur, w)
        res = dolt_sql(make_sql(days), client, throttle, retry_deadline=(w == 1)); st["calls"] += 1
        rows = res["rows"]
        capped = res["status"] == "RowLimit" or len(rows) >= ROW_CAP
        if res["status"] == "Error" or capped:
            if w > 1:
                w = max(1, w // 2); st["splits"] += 1
                continue
            if capped and page_day is not None:
                rows, off = [], 0
                while True:
                    pr = dolt_sql(page_day(days[0], off), client, throttle); st["calls"] += 1
                    if pr["status"] == "Error":
                        st["failed_days"].append(days[0]); rows = []
                        break
                    rows += pr["rows"]
                    if len(pr["rows"]) < ROW_CAP:
                        break
                    off += len(pr["rows"])
            elif res["status"] == "Error" or capped:
                st["failed_days"].append(days[0]); rows = []
        st["windows"] += 1
        for r in sorted(rows, key=lambda r: r.get("date", "")):
            d = r.get("date") or ""
            if d not in order:
                order[d] = len(order)
            if limit_days is not None and order[d] >= limit_days:
                continue
            out.append(r)
        if limit_days is not None and len(order) >= limit_days:
            st["last_day"] = max(d for d, i in order.items() if i < limit_days)
            return out
        st["last_day"] = days[-1]
        cur = date.fromisoformat(days[-1]) + timedelta(days=1)
        per_day = len(rows) / len(days)
        w = max(1, min(max_window, int(target_rows / per_day) if per_day > 0 else max_window))
    return out


# --------------------------------------------------------------------- commit log --

_COMMIT_CACHE: dict = {}


def dolt_commit_times(client: httpx.Client, throttle: Throttle, table: str = "option_chain", page: int = 300,
                      stats: Optional[dict] = None, max_age_s: float = 3600.0) -> dict[str, str]:
    """{snapshot_date: LAST commit time (UTC ISO)} from ``dolt_log`` messages '<table> <date> update'. The last one counts
    because a re-run replaces the date's rows (SPY 2021-07-09: no rows at the on-time commit, all 140 from the re-run five
    days later). One pass reads both tables; a complete log is cached for an hour with its ``complete`` flag, which goes
    into ``stats['commit_log_complete']`` on a cache hit too. Bulk-era dates are mapped by ``commit_time_for``. Returns
    what it has (possibly {}) when the log cannot be read in full. About 30-35 calls and 10-15 minutes uncached."""
    hit = _COMMIT_CACHE.get("log")
    if hit and time.time() - hit[0] < max_age_s:
        if stats is not None:
            stats["commit_log_complete"] = hit[2]
            stats["commit_log_cached"] = True
        return dict(hit[1].get(table, {}))
    out: dict[str, dict[str, str]] = {}
    off, size, complete = 0, page, False
    while True:
        res = dolt_sql(f"SELECT date, message FROM dolt_log LIMIT {size} OFFSET {off}", client, throttle, retry_deadline=size <= 50)
        if stats is not None:
            stats["calls"] = stats.get("calls", 0) + 1
        if res["status"] == "Error":
            if size > 50:
                size //= 2
                continue
            break
        for r in res["rows"]:
            parts = (r.get("message") or "").split()
            if len(parts) >= 2 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[1]) and parts[2:3] == ["update"]:
                ts = datetime.strptime(r["date"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
                tab = out.setdefault(parts[0], {})
                if parts[1] not in tab or ts > tab[parts[1]]:
                    tab[parts[1]] = ts
        if len(res["rows"]) < size:
            complete = True
            break
        off += len(res["rows"])
    if complete:
        _COMMIT_CACHE["log"] = (time.time(), out, complete)
    if stats is not None:
        stats["commit_log_complete"] = complete
        stats["commit_log_cached"] = False
    return dict(out.get(table, {}))


def commit_time_for(snapshot_date: str, commits: Optional[dict[str, str]]) -> Optional[str]:
    """Provenance: when DoltHub published the date. BULK_IMPORT_AT for every bulk-era date (the bulk commits' names do
    not match the dates they loaded), the last named commit for a live-era date, None when the log was not read or no
    commit names the date."""
    if not commits:
        return None
    if snapshot_date < LIVE_START:
        return BULK_IMPORT_AT
    return commits.get(snapshot_date)


def is_backfill(snapshot_date: str, commit_at: Optional[str]) -> Optional[bool]:
    """Provenance only (never moves available_at): True when a live-era date's last named commit came after the next
    session's 13:30 UTC open, False when before it or for the bulk era, None when the publication time is unknown."""
    if not commit_at:
        return None
    if snapshot_date < LIVE_START:
        return False
    return commit_at > next_session(snapshot_date) + "T13:30:00+00:00"


def _pit(snap: str, commits: Optional[dict]) -> tuple[str, str, Optional[str], Optional[bool]]:
    q = quote_date_for(snap)
    ca = commit_time_for(snap, commits)
    return q, available_at_for(snap, q), ca, is_backfill(snap, ca)


# ------------------------------------------------------------------- row shaping --

def chain_row(r: dict, fetched_at: str, commits: Optional[dict] = None) -> dict:
    """One archive row from one option_chain row. value keeps every source column (vol renamed iv, call_put -> type)."""
    snap = r["date"]
    q, avail, ca, back = _pit(snap, commits)
    cp = (r.get("call_put") or "").lower()
    v = {"symbol": r["act_symbol"], "snapshot_date": snap, "quote_date": q, "expiry": r["expiration"], "strike": _num(r["strike"]),
         "type": "call" if cp.startswith("c") else "put" if cp.startswith("p") else cp,
         "bid": _num(r.get("bid")), "ask": _num(r.get("ask")), "iv": _num(r.get("vol")),
         "delta": _num(r.get("delta")), "gamma": _num(r.get("gamma")), "theta": _num(r.get("theta")), "vega": _num(r.get("vega")), "rho": _num(r.get("rho")),
         "dolt_commit_at": ca, "backfilled": back, "stale": None, "stale_basis": None}
    return {"source": "dolthub", "kind": "option", "key": f"{v['symbol']}:{snap}:{v['expiry']}:{v['type'][:1].upper()}{r['strike']}",
            "observed_at": fetched_at, "available_at": avail, "value": v}


def vol_row(r: dict, fetched_at: str, commits: Optional[dict] = None) -> dict:
    snap = r["date"]
    q, avail, ca, back = _pit(snap, commits)
    v = {"symbol": r["act_symbol"], "snapshot_date": snap, "quote_date": q}
    v.update({k: _num(r.get(k)) for k in VOL_NUMERIC})
    v.update({k: r.get(k) for k in VOL_DATES})
    v["dolt_commit_at"], v["backfilled"], v["stale"], v["stale_basis"] = ca, back, None, None
    return {"source": "dolthub", "kind": "volatility", "key": f"{v['symbol']}:{snap}", "observed_at": fetched_at,
            "available_at": avail, "value": v}


def _sort_key(row: dict):
    v = row["value"]
    return (v["snapshot_date"], v["symbol"], v.get("expiry", ""), v.get("strike") or 0.0, v.get("type", ""))


def _merge_store(store, name: str, new_rows: list[dict], span: tuple[str, str], symbols: set[str],
                 failed_days: Iterable[str] = (), **kw):
    """Write ``name`` = existing rows outside the fetched span (or for other symbols, or on days whose query failed)
    + the new rows, so a partial or incremental fetch never truncates the one-bundle-per-symbol history."""
    arc = getattr(store, "archive", store)
    failed = set(failed_days)
    keep = []
    try:
        for r in arc.load(name):
            v = r.get("value", {})
            sd = v.get("snapshot_date", "")
            if span[0] <= sd <= span[1] and v.get("symbol") in symbols and sd not in failed:
                continue
            keep.append(r)
    except (KeyError, FileNotFoundError):
        pass
    rows = sorted(keep + new_rows, key=_sort_key)
    return arc.store(name, "data", rows, **kw)


# ---------------------------------------------------------------- stale check --

def _arc(store):
    return getattr(store, "archive", store)


def load_closes(store, symbol: str) -> dict[str, float]:
    """{session date: close} from the archive bundle ``daily-history-<SYM>`` (Yahoo split-adjusted closes; read only).
    {} when the store is None or has no such bundle on this machine."""
    if store is None:
        return {}
    try:
        rows = list(_arc(store).load(f"daily-history-{_check_symbol(symbol)}"))
    except (KeyError, FileNotFoundError, AttributeError):
        return {}
    out = {}
    for r in rows:
        v = r.get("value") or {}
        c = _num(v.get("close"))
        if v.get("t") is not None and c and c > 0:
            out[datetime.fromtimestamp(v["t"], timezone.utc).date().isoformat()] = c
    return out


def load_rates(store) -> dict[str, float]:
    """{day: 3-month T-bill rate as a decimal} from the archive bundle ``fred-DTB3`` (read only); {} when absent."""
    if store is None:
        return {}
    try:
        rows = list(_arc(store).load("fred-DTB3"))
    except (KeyError, FileNotFoundError, AttributeError):
        return {}
    out = {}
    for r in rows:
        v = r.get("value") or {}
        x = _num(v.get("value"))
        if v.get("day") and x is not None:
            out[v["day"]] = x / 100.0
    return out


def rate_on(rates: dict[str, float], day: str, default: float = DEFAULT_RATE, max_age_days: int = 10) -> float:
    """The latest rate on or before ``day`` (at most ``max_age_days`` old), else ``default``."""
    for k in range(max_age_days + 1):
        d = (date.fromisoformat(day) - timedelta(days=k)).isoformat()
        if d in rates:
            return rates[d]
    return default


def parity_estimates(rows: list[dict], snapshot_date: str, rate: float = DEFAULT_RATE, div_yield: float = SPY_DIV_YIELD,
                     n_expiries: int = 2) -> list[float]:
    """Spot implied by put-call parity for each of the nearest ``n_expiries`` expiries of one snapshot (archive rows or
    their values): the average of K + (C_mid - P_mid) e^{rT} over the two strikes with the smallest |C - P|, carried
    back to spot with S = F e^{-(r - q)T}. Quotes without a positive bid and ask are skipped."""
    vals = [r.get("value", r) for r in rows]
    d0 = date.fromisoformat(snapshot_date)
    by_exp: dict[str, dict[float, dict[str, float]]] = {}
    for v in vals:
        if v.get("snapshot_date") != snapshot_date or v.get("bid") is None or v.get("ask") is None or v["bid"] <= 0 or v["ask"] <= 0:
            continue
        by_exp.setdefault(v["expiry"], {}).setdefault(v["strike"], {})[v["type"]] = (v["bid"] + v["ask"]) / 2
    ests = []
    for exp in sorted(by_exp):
        T = (date.fromisoformat(exp) - d0).days / 365.0
        if T <= 0:
            continue
        pairs = sorted(((K, q["call"] - q["put"]) for K, q in by_exp[exp].items() if "call" in q and "put" in q), key=lambda p: abs(p[1]))[:2]
        if not pairs:
            continue
        F = sum(K + cp * math.exp(rate * T) for K, cp in pairs) / len(pairs)
        ests.append(F * math.exp(-(rate - div_yield) * T))
        if len(ests) >= n_expiries:
            break
    return ests


def parity_spot(rows: list[dict], snapshot_date: str, rate: float = DEFAULT_RATE, div_yield: float = SPY_DIV_YIELD,
                n_expiries: int = 2) -> Optional[float]:
    """The median of ``parity_estimates`` (None when no expiry has a call/put pair)."""
    ests = parity_estimates(rows, snapshot_date, rate=rate, div_yield=div_yield, n_expiries=n_expiries)
    return statistics.median(ests) if ests else None


def hv_close_to_close(closes: dict[str, float], end: str, n: int = 30, days: Optional[list[str]] = None) -> Optional[float]:
    """The ``n``-session sample standard deviation of log close-to-close returns ending on ``end``, x sqrt(252): the
    definition DoltHub's hv_current matches. None when ``end`` or the ``n`` sessions before it are not in ``closes``."""
    days = days if days is not None else sorted(closes)
    i = bisect.bisect_left(days, end)
    if i >= len(days) or days[i] != end or i < n:
        return None
    px = [closes[d] for d in days[i - n:i + 1]]
    return statistics.stdev([math.log(px[k + 1] / px[k]) for k in range(n)]) * math.sqrt(252)


def _unchecked(snap: str, rule: str, why: str, **extra) -> dict:
    return {"snapshot_date": snap, "rule_quote_date": rule, "quote_date": rule, "stale": None, "decision": "unchecked",
            "basis": why, **extra}


def stale_check_chain(rows: list[dict], closes: dict[str, float], rates: Optional[dict[str, float]] = None,
                      div_yield: float = SPY_DIV_YIELD, min_gap: float = MIN_GAP, noise_frac: float = NOISE_FRAC) -> dict[str, dict]:
    """{snapshot_date: verdict} for one symbol's chain rows. The parity spot is compared with the closes of the previous,
    rule and next NYSE sessions. ``decision`` is 'rule' (the rule session fits best), 'moved' (another session fits
    decisively: every other candidate close at least ``min_gap`` from it and parity noise at most ``noise_frac`` of
    that gap; ``quote_date`` is that session, ``stale`` True), 'undecidable' (the rule is kept) or 'unchecked'."""
    rates = rates or {}
    by_snap: dict[str, list[dict]] = {}
    for r in rows:
        v = r.get("value", r)
        by_snap.setdefault(v["snapshot_date"], []).append(v)
    out: dict[str, dict] = {}
    for snap, vals in sorted(by_snap.items()):
        rule = quote_date_for(snap)
        if not closes:
            out[snap] = _unchecked(snap, rule, "no closes for this symbol")
            continue
        r = rate_on(rates, rule)
        ests = parity_estimates(vals, snap, rate=r, div_yield=div_yield)
        if not ests:
            out[snap] = _unchecked(snap, rule, "no call/put pair with a positive bid and ask")
            continue
        S = statistics.median(ests)
        cands = {"prev": prev_session(rule), "rule": rule, "next": next_session(rule)}
        if rule not in closes:
            out[snap] = _unchecked(snap, rule, f"no close for the rule session {rule}", parity_spot=round(S, 4))
            continue
        errs = {k: abs(S / closes[d] - 1) for k, d in cands.items() if d in closes}
        best = min(errs, key=errs.get)
        noise = max([errs[best]] + [abs(e / S - 1) for e in ests])
        res = {"snapshot_date": snap, "rule_quote_date": rule, "quote_date": rule, "stale": False, "decision": "rule",
               "basis": None, "parity_spot": round(S, 4), "rate": r, "matched": best, "matched_day": cands[best],
               "errs": {k: round(e, 6) for k, e in errs.items()}, "noise": round(noise, 6), "gap": None}
        out[snap] = res
        if best == "rule":
            continue
        gap = min(abs(closes[cands[best]] / closes[cands[k]] - 1) for k in errs if k != best)
        res["gap"] = round(gap, 6)
        missing = [cands[k] for k in cands if cands[k] not in closes]
        if missing or gap < min_gap or noise > noise_frac * gap:
            res["decision"] = "undecidable"
            res["basis"] = (f"parity spot {S:.2f} is nearest the {cands[best]} close but not decisively: "
                            + (f"no close for {', '.join(missing)}" if missing else f"closes {gap:.2%} apart, parity noise {noise:.2%}"))
            continue
        res.update(decision="moved", stale=True, quote_date=cands[best],
                   basis=(f"put-call parity spot {S:.2f} (rate {r:.2%}) matches the {cands[best]} close {closes[cands[best]]:.2f} "
                          f"(off {errs[best]:.2%}), not the rule session {rule} close {closes[rule]:.2f} (off {errs['rule']:.2%}); "
                          f"other candidate closes are at least {gap:.2%} away, parity noise {noise:.2%}"))
    return out


def stale_check_vol(rows: list[dict], closes_by_symbol: dict[str, dict[str, float]], tol: float = HV_TOL) -> dict[tuple[str, str], dict]:
    """{(symbol, snapshot_date): verdict} for volatility_history rows: which of the previous, rule and next sessions'
    30-session close-to-close vol equals ``hv_current`` (within ``tol``). 'rule' when the rule session matches (alone
    or with a neighbour), 'moved' when exactly one other session matches, all three could be computed and the rule
    session misses by more than HV_MOVE_MARGIN (a near-miss is close-price rounding, not a stale snapshot), otherwise
    'undecidable'; 'unchecked' without closes or hv_current. On the full 2019-2026 history (12,884 rows) this moves 15
    rows (the 2020-06-09 and 2021-03-17 stale days plus one forward move), against 24 at the earlier 5e-5 tolerance."""
    days_by_symbol = {s: sorted(c) for s, c in closes_by_symbol.items()}
    hv_cache: dict[tuple[str, str], Optional[float]] = {}

    def hv(sym: str, d: str) -> Optional[float]:
        if (sym, d) not in hv_cache:
            hv_cache[(sym, d)] = hv_close_to_close(closes_by_symbol[sym], d, days=days_by_symbol[sym])
        return hv_cache[(sym, d)]

    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        v = r.get("value", r)
        sym, snap, h = v["symbol"], v["snapshot_date"], v.get("hv_current")
        rule = quote_date_for(snap)
        if not closes_by_symbol.get(sym):
            out[(sym, snap)] = _unchecked(snap, rule, f"no closes for {sym}", symbol=sym)
            continue
        if h is None:
            out[(sym, snap)] = _unchecked(snap, rule, "hv_current is null", symbol=sym)
            continue
        cands = {"prev": prev_session(rule), "rule": rule, "next": next_session(rule)}
        hvs = {k: hv(sym, d) for k, d in cands.items()}
        if hvs["rule"] is None:
            out[(sym, snap)] = _unchecked(snap, rule, f"too few closes to compute the vol ending {rule}", symbol=sym)
            continue
        hits = [k for k, x in hvs.items() if x is not None and abs(x - h) <= tol]
        res = {"symbol": sym, "snapshot_date": snap, "rule_quote_date": rule, "quote_date": rule, "stale": False,
               "decision": "rule", "basis": None, "hv_current": h, "hv": {k: (round(x, 6) if x is not None else None) for k, x in hvs.items()},
               "hits": hits}
        out[(sym, snap)] = res
        if "rule" in hits:
            continue
        if len(hits) == 1 and all(x is not None for x in hvs.values()) and abs(hvs["rule"] - h) > HV_MOVE_MARGIN:
            k = hits[0]
            res.update(decision="moved", stale=True, quote_date=cands[k],
                       basis=(f"hv_current {h:.4f} equals the 30-session close-to-close vol ending {cands[k]} ({hvs[k]:.4f}), "
                              f"not the rule session {rule} ({hvs['rule']:.4f}) or "
                              f"{', '.join(f'{cands[j]} ({hvs[j]:.4f})' for j in cands if j not in (k, 'rule'))}"))
        else:
            res["decision"] = "undecidable"
            res["basis"] = (f"hv_current {h:.4f} matches {', '.join(cands[k] for k in hits)}" if hits else
                            f"hv_current {h:.4f} matches no candidate session")
    return out


def apply_stale(row: dict, verdict: Optional[dict]) -> dict:
    """Write a verdict into an archive row: ``stale``; on a move also ``quote_date``, ``stale_basis`` and
    ``available_at`` (22:00 UTC on the later of the snapshot date and the new quote date)."""
    if not verdict:
        return row
    v = row["value"]
    v["stale"] = verdict["stale"]
    v["stale_basis"] = verdict["basis"] if verdict["stale"] else None
    if verdict["stale"]:
        v["quote_date"] = verdict["quote_date"]
        row["available_at"] = available_at_for(v["snapshot_date"], v["quote_date"])
    return row


def _stale_summary(verdicts: Iterable[dict]) -> dict:
    vs = list(verdicts)
    out = {k: sum(1 for x in vs if x["decision"] == k) for k in ("rule", "moved", "undecidable", "unchecked")}
    out["moved_dates"] = sorted({(x.get("symbol") + ":" if x.get("symbol") else "") + x["snapshot_date"] + "->" + x["quote_date"]
                                 for x in vs if x["decision"] == "moved"})
    return out


# ---------------------------------------------------------------------- fetchers --

def fetch_dolt_chains(store, symbol: str, start: Optional[str] = None, end: Optional[str] = None, limit_days: Optional[int] = None,
                      pace: float = 1.0, dry_run: bool = False, with_commits: bool = True, in_git: Optional[bool] = None,
                      stale_check: bool = True, closes: Optional[dict[str, float]] = None, rates: Optional[dict[str, float]] = None,
                      div_yield: float = SPY_DIV_YIELD, stats: Optional[dict] = None) -> list[dict]:
    """Every option_chain row for ``symbol`` from ``start`` (default 2019-02-09) to ``end`` (default today), as archive
    rows; stored as bundle ``dolt-chain-<SYM>`` (merged with what is already there) unless ``store`` is None or
    ``dry_run``. ``limit_days`` caps the number of snapshot dates fetched (previews). The stale check uses ``closes``
    ({session: close}) and ``rates`` ({day: decimal}) when given, else reads ``daily-history-<SYM>`` and ``fred-DTB3``
    from the store's archive (read only); ``div_yield`` is the symbol's dividend yield for the parity carry."""
    sym = _check_symbol(symbol)
    start = start or FIRST_DAY
    end = end or now_iso()[:10]
    st = stats if stats is not None else {}
    t0 = time.time()
    fetched_at = now_iso()
    with _client() as c:
        th = Throttle(pace)
        commits = dolt_commit_times(c, th, "option_chain", stats=st) if with_commits else {}
        raw = walk_windows(c, th, lambda days: f"SELECT * FROM option_chain WHERE act_symbol = '{sym}' AND date IN ({_in(days)})",
                           start, end, window=10, max_window=31, target_rows=700, limit_days=limit_days,
                           page_day=lambda day, off: (f"SELECT * FROM option_chain WHERE date = '{day}' AND act_symbol = '{sym}' "
                                                      f"ORDER BY expiration, strike, call_put LIMIT {ROW_CAP} OFFSET {off}"),
                           stats=st)
    rows = sorted((chain_row(r, fetched_at, commits) for r in raw), key=_sort_key)
    if stale_check and rows:
        cl = closes if closes is not None else load_closes(store, sym)
        rt = rates if rates is not None else load_rates(store)
        verdicts = stale_check_chain(rows, cl, rt, div_yield=div_yield)
        for r in rows:
            apply_stale(r, verdicts.get(r["value"]["snapshot_date"]))
        st["stale"] = dict(_stale_summary(verdicts.values()), closes_days=len(cl), rate_days=len(rt))
        st["stale_verdicts"] = [verdicts[d] for d in sorted(verdicts)]
    snaps = sorted({r["value"]["snapshot_date"] for r in rows})
    st.update({"symbol": sym, "rows": len(rows), "snapshot_dates": len(snaps), "first": snaps[0] if snaps else None,
               "last": snaps[-1] if snaps else None, "commit_dates": len(commits), "wall_seconds": round(time.time() - t0, 1)})
    if store is not None and not dry_run and rows:
        span = (start, st.get("last_day") or end)
        e = _merge_store(store, f"dolt-chain-{sym}", rows, span, {sym}, failed_days=st.get("failed_days", ()),
                         recipe=(f"GET {DOLT}?q=SELECT * FROM option_chain WHERE act_symbol = '{sym}' AND date IN (<every calendar day of an "
                                 f"adaptive 1-31 day window>), walked {start}..{span[1]}; a window that hits the 1000-row cap or "
                                 "'context deadline exceeded' is halved; commit times (provenance) from SELECT date, message FROM dolt_log "
                                 f"LIMIT/OFFSET pages; stale check against archive daily-history-{sym} closes and fred-DTB3 (read only). "
                                 f"Rebuild: mandel.data.dolt_options.fetch_dolt_chains(store, '{sym}', pace={pace}, in_git=True). "
                                 + LICENCE_NOTE.format(changes="vol renamed iv, call_put renamed type (call/put); added quote_date, "
                                                       "available_at, observed_at, dolt_commit_at, backfilled, stale and stale_basis")),
                         tags=["options", "chain", "history", "dolthub", sym.lower(), "cc-by-sa-4.0"],
                         schema=("value = {symbol, snapshot_date (DoltHub date), quote_date (close quoted: last NYSE trading day <= snapshot_date, "
                                 "or the session a decisive put-call parity match against the closes points to), expiry, strike, type, bid, ask, "
                                 "iv (source column vol), delta, gamma, theta, vega, rho, dolt_commit_at (last named DoltHub commit for the date; "
                                 f"{BULK_IMPORT_AT} for the bulk era; provenance), backfilled (that commit after the next session's open; None = "
                                 "unknown; provenance), stale (True = quote_date moved off the rule, None = not checked), stale_basis}; "
                                 "observed_at = fetch time; available_at = 22:00 UTC on the later of snapshot_date and quote_date"),
                         in_git=in_git)
        st["bundle_rows"], st["bundle_bytes"] = e.rows, e.bytes
    return rows


def fetch_dolt_volhistory(store, symbols: Iterable[str] = VOL_SYMBOLS, start: Optional[str] = None, end: Optional[str] = None,
                          limit_days: Optional[int] = None, pace: float = 1.0, dry_run: bool = False, with_commits: bool = True,
                          in_git: Optional[bool] = None, stale_check: bool = True, closes: Optional[dict[str, dict[str, float]]] = None,
                          stats: Optional[dict] = None) -> list[dict]:
    """volatility_history rows for all ``symbols`` from ``start`` (default 2019-02-09) to ``end`` (default today); stored as
    bundle ``dolt-volhistory`` (merged with what is there) unless ``store`` is None or ``dry_run``. Symbols the database
    does not carry come back empty and are listed in ``stats['missing']``. The stale check uses ``closes``
    ({symbol: {session: close}}) when given, else ``daily-history-<SYM>`` from the store's archive (read only)."""
    syms = sorted({_check_symbol(s) for s in symbols})
    start = start or FIRST_DAY
    end = end or now_iso()[:10]
    st = stats if stats is not None else {}
    t0 = time.time()
    fetched_at = now_iso()
    per_day = max(1, len(syms))
    with _client() as c:
        th = Throttle(pace)
        commits = dolt_commit_times(c, th, "volatility_history", stats=st) if with_commits else {}
        raw = walk_windows(c, th, lambda days: f"SELECT * FROM volatility_history WHERE act_symbol IN ({_in(syms)}) AND date IN ({_in(days)})",
                           start, end, window=max(1, min(92, 600 // per_day)), max_window=92, target_rows=700, limit_days=limit_days, stats=st)
    rows = sorted((vol_row(r, fetched_at, commits) for r in raw), key=_sort_key)
    have = sorted({r["value"]["symbol"] for r in rows})
    if stale_check and rows:
        cl = closes if closes is not None else {s: load_closes(store, s) for s in have}
        verdicts = stale_check_vol(rows, cl)
        for r in rows:
            apply_stale(r, verdicts.get((r["value"]["symbol"], r["value"]["snapshot_date"])))
        st["stale"] = dict(_stale_summary(verdicts.values()), closes_symbols=sorted(s for s in have if cl.get(s)))
        st["stale_verdicts"] = [verdicts[k] for k in sorted(verdicts)]
    snaps = sorted({r["value"]["snapshot_date"] for r in rows})
    st.update({"symbols": syms, "missing": [s for s in syms if s not in have], "rows": len(rows), "snapshot_dates": len(snaps),
               "first": snaps[0] if snaps else None, "last": snaps[-1] if snaps else None,
               "rows_by_symbol": {s: sum(1 for r in rows if r["value"]["symbol"] == s) for s in syms}, "wall_seconds": round(time.time() - t0, 1)})
    if store is not None and not dry_run and rows:
        span = (start, st.get("last_day") or end)
        e = _merge_store(store, "dolt-volhistory", rows, span, set(syms), failed_days=st.get("failed_days", ()),
                         recipe=(f"GET {DOLT}?q=SELECT * FROM volatility_history WHERE act_symbol IN ({_in(syms)}) AND date IN (<every calendar day "
                                 f"of an adaptive window, up to 92 days>), walked {start}..{span[1]}; windows halve on the 1000-row cap or "
                                 "'context deadline exceeded'; commit times (provenance) from dolt_log; stale check against archive "
                                 "daily-history-<SYM> closes (read only). Rebuild: mandel.data.dolt_options.fetch_dolt_volhistory(store, symbols, "
                                 "in_git=True). "
                                 + LICENCE_NOTE.format(changes="added quote_date, available_at, observed_at, dolt_commit_at, backfilled, "
                                                       "stale and stale_basis")),
                         tags=["volatility", "history", "dolthub", "implied-vol", "realised-vol", "cc-by-sa-4.0"],
                         schema=("value = {symbol, snapshot_date, quote_date (last NYSE trading day <= snapshot_date, or the one session whose "
                                 "30-session close-to-close vol equals hv_current), hv_current, hv_week_ago, hv_month_ago, "
                                 "hv_year_high, hv_year_high_date, hv_year_low, hv_year_low_date, iv_current, iv_week_ago, iv_month_ago, iv_year_high, "
                                 "iv_year_high_date, iv_year_low, iv_year_low_date (decimals, annualised; hv_current = 30-session sample stdev of log "
                                 "returns x sqrt(252) to quote_date), dolt_commit_at (last named commit; provenance), backfilled (provenance; None = "
                                 "unknown), stale (True = quote_date moved off the rule, None = not checked), stale_basis}; observed_at = fetch time; "
                                 "available_at = 22:00 UTC on the later of snapshot_date and quote_date"),
                         in_git=in_git)
        st["bundle_rows"], st["bundle_bytes"] = e.rows, e.bytes
    return rows


# ---------------------------------------------------------------- parity check --

def parity_check(rows: list[dict], closes: dict[str, float], rate: float = DEFAULT_RATE, clear_ratio: float = 2.0) -> list[dict]:
    """Diagnostic: for each snapshot date, which close (previous trading day, same day, next trading day) the parity spot
    matches. ``closes`` = {trading day: close}. A match is 'clear' when the runner-up error is at least ``clear_ratio``
    times the best. ``stale_check_chain`` is the decision rule the fetcher applies."""
    days = sorted(closes)
    out = []
    for snap in sorted({r.get("value", r)["snapshot_date"] for r in rows}):
        S = parity_spot(rows, snap, rate=rate)
        if not S:
            continue
        i = bisect.bisect_left(days, snap)                     # first trading day >= snapshot date
        same = snap if i < len(days) and days[i] == snap else None
        j = i + 1 if same else i
        cands = {"prev": days[i - 1] if i > 0 else None, "same": same, "next": days[j] if j < len(days) else None}
        errs = {k: abs(S / closes[d] - 1) for k, d in cands.items() if d}
        if not errs:
            continue
        best = min(errs, key=errs.get)
        others = sorted(e for k, e in errs.items() if k != best)
        out.append({"snapshot_date": snap, "weekday": date.fromisoformat(snap).strftime("%a"), "parity_spot": S, "best": best,
                    "matched_day": cands[best], "err": errs[best], "clear": bool(others) and others[0] >= clear_ratio * errs[best],
                    "rule_quote_date": quote_date_for(snap), "agrees_with_rule": cands[best] == quote_date_for(snap)})
    return out
