"""
DoltHub options history: daily option chains and volatility history since 2019, free and keyless.
=================================================================================================

Source: the public DoltHub SQL API on the ``post-no-preference/options`` database (no key, read only):
  GET https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q=<SQL>
Tables:
  * ``option_chain(date, act_symbol, expiration, strike, call_put, bid, ask, vol, delta, gamma, theta, vega, rho)``:
    a thin end-of-day chain per symbol (SPY: 3 expiries, about 11-25 strikes each side, 60-150 rows per date).
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
  * the commit log (``dolt_log``) names each daily load ``option_chain <date> update``; since 2021-04-20 these land at
    about 06:35 UTC the next morning. Everything dated before 2021-04-20 arrived in one bulk import on 2021-04-20.

Point in time. ``date`` is the snapshot date, not always the quote date. Measured 2026-10-15:
  * volatility_history: ``hv_current`` equals the 30-session sample standard deviation of SPY log returns x sqrt(252)
    ending on the last NYSE trading day on or before the snapshot date, to all 4 decimals, for 592 of 595 SPY snapshots
    (2019-2026; every weekday and all 47 Saturdays); 2 misses match the previous session, 1 matches the next session
    by coincidence (it was committed before that session opened).
  * option_chain: put-call parity on near-ATM strikes (spot = (K + (C_mid - P_mid) e^{rT}) e^{-(r-q)T}, two nearest
    expiries, DTB3 rates) against SPY closes, over 397 sampled snapshots: on the 116 dates where the neighbouring
    sessions' closes differ from the rule's close by >= 0.5%, the rule's session is the best match for 112 (96.6%);
    at >= 0.3% separation, 164 of 178 (92.1%). Misses are previous-session or intraday captures (e.g. 2026-03-13 and
    2026-06-11 imply a spot between the prior close and that day's open) or noise; none is a credible later-session match.
So ``quote_date`` = the last NYSE trading day on or before ``snapshot_date`` (a Saturday or holiday snapshot quotes the
previous session), and ``available_at`` = 22:00 UTC (after the 16:15 ET options close) on the snapshot date, never
earlier than the evening of the quote date. The commit log shows each date since 2021-04-20 was published before the
next session opened, except four backfills (2021-05-26, 2022-12-12, 2024-06-11, 2025-10-12; only 2022-12-12 has SPY
rows, and its parity spot fits no nearby close well): for those ``backfilled`` is true and ``available_at`` is the
commit time. The 2019-2021 bulk import is not treated as a backfill: its parity and hv agreement match the live era.
``observed_at`` is when Mandel fetched the row; ``dolt_commit_at`` is when DoltHub first published that date
(BULK_IMPORT_AT for dates before 2021-04-20). Stale or intraday snapshots (about 2-4% of chain dates) carry older
information, so they cannot leak the future, but ``quote_date`` overstates their freshness; ``parity_check`` flags them.
"""

from __future__ import annotations

import bisect
import json
import math
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

import httpx

from mandel.data.fetch import Throttle, now_iso

UA = {"User-Agent": "mandel-substrate research bot (contact: https://github.com/pointlessbassmusic-byte/polymarket-arbitrage/issues)"}
DOLT = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"
FIRST_DAY = "2019-02-09"                       # the first date in either table
ROW_CAP = 1000                                 # DoltHub returns at most this many rows ('RowLimit')
BULK_IMPORT_AT = "2021-04-20T23:21:00+00:00"   # the commits that loaded every date before 2021-04-20 (23:20:00-23:20:57 UTC)
EVENING_UTC = "T22:00:00+00:00"                # after the 16:15 ET options close in both EST and EDT
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
    """{snapshot_date: first commit time (UTC ISO)} from ``dolt_log`` messages '<table> <date> update' (one pass reads
    both tables and is cached for an hour). Dates loaded by the 2021-04-20 bulk import are not listed; ``commit_time_for``
    maps them to BULK_IMPORT_AT. Returns what it has (possibly {}) when the log cannot be read."""
    hit = _COMMIT_CACHE.get("log")
    if hit and time.time() - hit[0] < max_age_s:
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
                if parts[1] not in tab or ts < tab[parts[1]]:
                    tab[parts[1]] = ts
        if len(res["rows"]) < size:
            complete = True
            break
        off += len(res["rows"])
    if complete:
        _COMMIT_CACHE["log"] = (time.time(), out)
    if stats is not None:
        stats["commit_log_complete"] = complete
    return dict(out.get(table, {}))


def commit_time_for(snapshot_date: str, commits: dict[str, str]) -> Optional[str]:
    if snapshot_date in commits:
        return commits[snapshot_date]
    if commits and snapshot_date < "2021-04-20":
        return BULK_IMPORT_AT
    return None


def is_backfill(snapshot_date: str, commit_at: Optional[str]) -> bool:
    """True when a date after the bulk import was first published after the next session opened (13:30 UTC), so its
    content could in principle postdate the snapshot date."""
    if not commit_at or snapshot_date < "2021-04-20":
        return False
    d = date.fromisoformat(snapshot_date) + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return commit_at > d.isoformat() + "T13:30:00+00:00"


def _pit(snap: str, commits: Optional[dict]) -> tuple[str, str, Optional[str], bool]:
    q = quote_date_for(snap)
    ca = commit_time_for(snap, commits or {})
    back = is_backfill(snap, ca)
    avail = available_at_for(snap, q)
    return q, (max(avail, ca) if back else avail), ca, back


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
         "dolt_commit_at": ca, "backfilled": back}
    return {"source": "dolthub", "kind": "option", "key": f"{v['symbol']}:{snap}:{v['expiry']}:{v['type'][:1].upper()}{r['strike']}",
            "observed_at": fetched_at, "available_at": avail, "value": v}


def vol_row(r: dict, fetched_at: str, commits: Optional[dict] = None) -> dict:
    snap = r["date"]
    q, avail, ca, back = _pit(snap, commits)
    v = {"symbol": r["act_symbol"], "snapshot_date": snap, "quote_date": q}
    v.update({k: _num(r.get(k)) for k in VOL_NUMERIC})
    v.update({k: r.get(k) for k in VOL_DATES})
    v["dolt_commit_at"], v["backfilled"] = ca, back
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


# ---------------------------------------------------------------------- fetchers --

def fetch_dolt_chains(store, symbol: str, start: Optional[str] = None, end: Optional[str] = None, limit_days: Optional[int] = None,
                      pace: float = 1.0, dry_run: bool = False, with_commits: bool = True, in_git: Optional[bool] = None,
                      stats: Optional[dict] = None) -> list[dict]:
    """Every option_chain row for ``symbol`` from ``start`` (default 2019-02-09) to ``end`` (default today), as archive
    rows; stored as bundle ``dolt-chain-<SYM>`` (merged with what is already there) unless ``store`` is None or
    ``dry_run``. ``limit_days`` caps the number of snapshot dates fetched (previews)."""
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
    snaps = sorted({r["value"]["snapshot_date"] for r in rows})
    st.update({"symbol": sym, "rows": len(rows), "snapshot_dates": len(snaps), "first": snaps[0] if snaps else None,
               "last": snaps[-1] if snaps else None, "commit_dates": len(commits), "wall_seconds": round(time.time() - t0, 1)})
    if store is not None and not dry_run and rows:
        span = (start, st.get("last_day") or end)
        e = _merge_store(store, f"dolt-chain-{sym}", rows, span, {sym}, failed_days=st.get("failed_days", ()),
                         recipe=(f"GET {DOLT}?q=SELECT * FROM option_chain WHERE act_symbol = '{sym}' AND date IN (<every calendar day of an "
                                 f"adaptive 1-31 day window>), walked {start}..{span[1]}; a window that hits the 1000-row cap or "
                                 "'context deadline exceeded' is halved; commit times from SELECT date, message FROM dolt_log LIMIT/OFFSET pages. "
                                 f"Rebuild: mandel.data.dolt_options.fetch_dolt_chains(store, '{sym}', pace={pace})"),
                         tags=["options", "chain", "history", "dolthub", sym.lower()],
                         schema=("value = {symbol, snapshot_date (DoltHub date), quote_date (close quoted: last NYSE trading day <= snapshot_date, "
                                 "checked by put-call parity against SPY closes), expiry, strike, type, bid, ask, iv (source column vol), delta, gamma, "
                                 "theta, vega, rho, dolt_commit_at (first DoltHub publication; bulk import 2021-04-20 for earlier dates), backfilled}; "
                                 "observed_at = fetch time; available_at = 22:00 UTC on the snapshot date, or the commit time for a backfilled date"),
                         in_git=in_git)
        st["bundle_rows"], st["bundle_bytes"] = e.rows, e.bytes
    return rows


def fetch_dolt_volhistory(store, symbols: Iterable[str] = VOL_SYMBOLS, start: Optional[str] = None, end: Optional[str] = None,
                          limit_days: Optional[int] = None, pace: float = 1.0, dry_run: bool = False, with_commits: bool = True,
                          stats: Optional[dict] = None) -> list[dict]:
    """volatility_history rows for all ``symbols`` from ``start`` (default 2019-02-09) to ``end`` (default today); stored as
    bundle ``dolt-volhistory`` (merged with what is there) unless ``store`` is None or ``dry_run``. Symbols the database
    does not carry come back empty and are listed in ``stats['missing']``."""
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
    have = {r["value"]["symbol"] for r in rows}
    snaps = sorted({r["value"]["snapshot_date"] for r in rows})
    st.update({"symbols": syms, "missing": [s for s in syms if s not in have], "rows": len(rows), "snapshot_dates": len(snaps),
               "first": snaps[0] if snaps else None, "last": snaps[-1] if snaps else None,
               "rows_by_symbol": {s: sum(1 for r in rows if r["value"]["symbol"] == s) for s in syms}, "wall_seconds": round(time.time() - t0, 1)})
    if store is not None and not dry_run and rows:
        span = (start, st.get("last_day") or end)
        e = _merge_store(store, "dolt-volhistory", rows, span, set(syms), failed_days=st.get("failed_days", ()),
                         recipe=(f"GET {DOLT}?q=SELECT * FROM volatility_history WHERE act_symbol IN ({_in(syms)}) AND date IN (<every calendar day "
                                 f"of an adaptive window, up to 92 days>), walked {start}..{span[1]}; windows halve on the 1000-row cap or "
                                 "'context deadline exceeded'. Rebuild: mandel.data.dolt_options.fetch_dolt_volhistory(store, symbols)"),
                         tags=["volatility", "history", "dolthub", "implied-vol", "realised-vol"],
                         schema=("value = {symbol, snapshot_date, quote_date (last NYSE trading day <= snapshot_date), hv_current, hv_week_ago, hv_month_ago, "
                                 "hv_year_high, hv_year_high_date, hv_year_low, hv_year_low_date, iv_current, iv_week_ago, iv_month_ago, iv_year_high, "
                                 "iv_year_high_date, iv_year_low, iv_year_low_date (decimals, annualised; hv_current = 30-session sample stdev of log "
                                 "returns x sqrt(252) to quote_date), dolt_commit_at, backfilled}; observed_at = fetch time; "
                                 "available_at = 22:00 UTC on the snapshot date, or the commit time for a backfilled date"))
        st["bundle_rows"], st["bundle_bytes"] = e.rows, e.bytes
    return rows


# ---------------------------------------------------------------- parity check --

def parity_spot(rows: list[dict], snapshot_date: str, rate: float = 0.02, div_yield: float = 0.013, n_expiries: int = 2) -> Optional[float]:
    """Spot implied by put-call parity on one snapshot's chain (archive rows or their values): for each of the nearest
    ``n_expiries`` expiries, average K + (C_mid - P_mid) e^{rT} over the two strikes with the smallest |C - P|, carry the
    forward back to spot with S = F e^{-(r - q)T}, and take the median across expiries."""
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
    if not ests:
        return None
    ests.sort()
    return ests[len(ests) // 2] if len(ests) % 2 else (ests[len(ests) // 2 - 1] + ests[len(ests) // 2]) / 2


def parity_check(rows: list[dict], closes: dict[str, float], rate: float = 0.02, clear_ratio: float = 2.0) -> list[dict]:
    """For each snapshot date: which close (previous trading day, same day, next trading day) the parity spot matches.
    ``closes`` = {trading day: close}. A match is 'clear' when the runner-up error is at least ``clear_ratio`` times the best."""
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
