"""
Binance BTCUSDT 1-minute klines around every Polymarket "Bitcoin above" resolution time (T-337's resolution source).
=====================================================================================================================

Why. T-337 (``mandel.experiments.batch6c_pmxv.b6c_pmxv_pm_vs_deribit_digital``) prices Polymarket "Bitcoin above K"
markets against Deribit-implied digitals; the Deribit smile lives on the Deribit BTC index while the markets resolve on
Binance BTC/USDT, and the trial's resolution-source basis control (Binance vs the Deribit index) was None (rule 9)
because no Binance price was archived. This module stores the minimum that control needs plus a documented margin.

The resolution rule, from the stored market descriptions (``polymarket-events-btc-above``, 7,782 parsed markets at 686
distinct resolution times 2024-03-15 .. 2026-10-15, every one on the hour in UTC):
  * daily / weekly noon-ET markets (4,532 markets, 490 times at 12:00 ET): 'This market will resolve to "Yes" if the
    Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final
    "Close" price higher than the price specified in the title.' (2026-10 wording: '... 1 minute candle for BTC/USDT
    closing at 12:00 in the ET timezone ...'; 2024 wording: '... 1 minute candle for BTCUSDT 16 Aug '24 12:00 in the ET
    timezone (noon) has a final "Close" price of 60,000.01 or higher'). Source: 'Binance, specifically the BTC/USDT
    "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected'.
  * the 5 pm-ET variant (3,250 markets, 196 times at 17:00 ET, from 2026-03): 'the "Close" price for the BTC/USDT
    1 hour candle that ends on the time and date specified in the title is higher than the price specified in the
    title' ("1h" candles selected). The close of the hour candle ending at 17:00 ET is the close of the 1-minute candle
    opening at 16:59 ET, so 1-minute klines serve both variants.

What is stored: ``binance-1m-BTCUSDT-btc-above``, one bundle, the BTCUSDT 1-minute klines whose open lies in
[t_res - BEFORE_MIN, t_res + AFTER_MIN] minutes (default 60 and 60: 121 bars) for every resolution time t_res, plus one
``window`` row per resolution time (fetch metadata). The margin is documented, not arbitrary: (a) "the 1 minute candle
for 12:00" reads either as the candle opening at 12:00:00 or as the one closing at 12:00:00 (the 2026-10 wording), so
both are held and the harness audits the Gamma outcomes against both; (b) the 1-hour candle of the 5 pm variant opens at
t_res - 60 min; (c) the basis the control needs is Binance against the Deribit index AT THE SAME MINUTE, and the
harness's index observation is the latest Deribit trade before t_res, which falls in the hour before t_res (the harness's
``last_idx``), so the hour before t_res must be covered minute by minute; (d) the hour after covers a resolution-time
misparse of one hour in either direction and a late print. Resolution times of one day are 12:00 and 17:00 ET, 5 hours
apart, so the default windows never overlap; with margins wider than 150 minutes a minute can appear in two windows
(each row names the window it serves in ``value.res``; readers keyed by minute see one identical close).

Why 1-minute windows rather than hourly klines over the whole span (2024-03 .. 2026-10, ~23k bars, 23 calls): the
criterion reads the resolution-minute close (an hourly close is a different price: BTC moves ~0.3% in an hour, the basis
being measured is ~0.01-0.1%), and the basis must be measured minute-matched to the Deribit index observation; hourly
bars cannot serve either. The windows cost 686 calls (one per resolution time: 121 klines, 1,000 per call) for ~84k
rows, ~6 MB gzip, ~4 minutes (dry run 2026-10-19: 686 windows, 83,692 rows, 3.7 min at PACE).

Endpoint. ``GET https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=<ms>&endTime=<ms>
&limit=1000`` (Binance's public market-data mirror; the same /api/v3 kline rows as api.binance.com, which answers 451
from this host; probed 2026-10-19: 200, x-mbx-used-weight-1m headers, exchangeInfo advertises REQUEST_WEIGHT 6000 per
minute; the klines request weighs 2). Pace ``PACE`` = 0.3 s between calls (400 weight/min, well under the ~1,200/min a
shared egress address should keep to). 429 and 5xx are retried with Retry-After honoured (``options_misc._get``); a
Retry-After beyond ``_get``'s max_wait, a 418 (IP ban), 451 or 403 ends the run (``aborted``), and no window of a failed
or cut-short call is stored. Fallback venue, NOT mixed into this bundle: https://api.binance.us/api/v3/klines answers
200 from this host too, but Binance.US is a different order book with its own BTCUSDT prints; the markets name
Binance.com. If the mirror ever closes, store a Binance.US bundle under its own name and say so in the harness.

Rows. kind ``bar1m``: value = {symbol, t (open, unix s), open, high, low, close, volume (BTC), quote_volume (USDT),
trades, taker_buy_volume, taker_buy_quote_volume, close_time (ms, open + 59,999), res (the resolution time the window
serves, unix s)}; key = BTCUSDT:<t>; observed_at = open; available_at = open + 60 s (a candle is known at its close).
kind ``window``: value = {res, res_iso, et (HH:MM America/New_York), variant (noon | 5pm), markets, start, end (opens of
the first and last bar), bars_expected, bars, missing (opens of absent minutes: Binance has none for BTCUSDT in normal
operation), complete (every call answered), calls}; key = res:<res>; observed_at = res; available_at = end + 60 s.

Storage. Local disk only (``in_git=False``, always: Binance's terms of use grant no redistribution right and the repo
is public); the .gitignore line is ``GITIGNORE_LINE`` (= mandel/archive/data/binance-1m-BTCUSDT-btc-above.jsonl.gz);
the INDEX entry and recipe are committed so any machine rebuilds it. Windows are fetched in order of resolution time and
stored in chunks of ``chunk`` complete windows through ``deribit_history._merge_store`` (streamed merge into the stored
bundle; rows of other windows kept); on an interrupt the complete windows fetched so far are stored; ``skip_stored``
skips windows already stored complete (resume), ``refresh`` fetches them again. A window still open (its last bar has
not closed) is never fetched. One writer at a time: ``run_lock`` (``<archive root>/binance_klines.run.lock``) refuses a
second storing run on the same archive, and ``_index_check`` compares the stored entry with a fresh read of INDEX.json.

Resolution times come from the archived ``polymarket-events-btc-above`` through the harness's own parser
(``batch6c_pmxv.btc_market_spec``, imported lazily), so the fetcher's t_res is the one the harness looks up; ``times``
overrides them (tests, ad-hoc windows). ``fetch_binance_resolution_klines`` takes ``store`` (an Archive, an
ObservationStore whose ``.archive`` is used, or None to store nothing), ``limit`` (windows), ``first`` / ``last``
(resolution days), ``dry_run`` (no request: the plan with calls, rows, gzip MB and minutes in ``report['_plan']``),
``skip_stored``, ``refresh``, ``max_calls`` (preview), ``report`` and ``rows_out``. Command line:
``python3 -m mandel.data.binance_klines [--dry-run] [--preview DIR] [--limit N] [--first DAY] [--last DAY]
[--before-min N] [--after-min N] [--max-calls N] [--refresh] [--min-interval S] [--chunk N]``.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import gzip
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import httpx

from mandel.data.deribit_history import _line, _merge_store, _scan
from mandel.data.fetch import Throttle
from mandel.data.options_misc import _archive, _get
from mandel.data.options_misc import _client as _om_client
from mandel.data.store import iso

UTC = timezone.utc
ET = ZoneInfo("America/New_York")

BASE = "https://data-api.binance.vision/api/v3"          # public market-data mirror of api.binance.com (451 from this host)
BINANCE_US = "https://api.binance.us/api/v3"             # answers 200 here, but a different venue: never mixed in (see above)
SYMBOL = "BTCUSDT"
INTERVAL = "1m"
KLINES_MAX = 1000                                        # klines per request
KLINE_WEIGHT = 2                                         # request weight of GET /api/v3/klines
BUNDLE = "binance-1m-BTCUSDT-btc-above"
EVENTS_BUNDLE = "polymarket-events-btc-above"
BEFORE_MIN = 60                                          # the documented margin: see the module docstring
AFTER_MIN = 60
PACE = 0.3                                               # seconds between calls: 400 weight/min
LATENCY = 0.25                                           # measured mirror round trip (2026-10-19 probe)
ROW_GZ = 75                                              # gzip bytes per stored row (compresslevel 9; 73 measured on the 2026-10-19 previews)
MERGE_SECONDS_PER_ROW = 40e-6                            # deribit_history's streamed re-write cost per stored row
CHUNK_WINDOWS = 100                                      # windows per merge-store (the resume point)
RUN_LOCK = "binance_klines.run.lock"                     # in the archive root; gitignored by mandel/**/*.lock
GITIGNORE_LINE = f"mandel/archive/data/{BUNDLE}.jsonl.gz"
LICENCE = "Binance public market data: Binance's terms of use grant no redistribution right"
LOCAL_ONLY = "The repo is public, so the bundle is local disk only (in_git=False); rebuild it from this recipe."
SCHEMA = ("kind bar1m: value = {symbol, t (open, unix s), open, high, low, close, volume (BTC), quote_volume (USDT), trades, "
          "taker_buy_volume, taker_buy_quote_volume, close_time (ms), res (the resolution time this window serves, unix s)}; "
          "observed_at = open; available_at = open + 60 s (the candle is known at its close) | kind window: value = {res, res_iso, "
          "et (HH:MM America/New_York), variant, markets, start, end (opens of the first and last bar), bars_expected, bars, missing "
          "(opens of absent minutes), complete, calls} (fetch metadata); observed_at = res; available_at = end + 60 s")
TAGS = ["binance", "prices", "1m", "btc-above", "resolution"]
_sleep = time.sleep                                      # patched in tests


def _now_s() -> int:                                     # patched in tests
    return int(time.time())


def _client() -> httpx.Client:                           # patched in tests
    return _om_client(timeout=60)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).date().isoformat()


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _failure(info: dict) -> dict:
    return {k: info[k] for k in ("url", "status", "error", "body", "retry_after", "attempts") if k in info}


def recipe(before_min: int = BEFORE_MIN, after_min: int = AFTER_MIN) -> str:
    return (f"GET {BASE}/klines?symbol={SYMBOL}&interval={INTERVAL}&startTime=<t_res - {before_min} min, ms>&endTime=<t_res + {after_min} min "
            f"+ 59,999 ms>&limit={KLINES_MAX} for every distinct resolution time t_res of the 'Bitcoin above' markets in "
            f"{EVENTS_BUNDLE} (mandel.experiments.batch6c_pmxv.btc_market_spec: noon ET daily / weekly, 17:00 ET -5pm-et variant; barrier "
            f"and range markets excluded); via mandel.data.binance_klines.fetch_binance_resolution_klines. Licence: {LICENCE}. {LOCAL_ONLY}")


# ============================================================================================ resolution times ==

def _event_rows(archive, bundle: str = EVENTS_BUNDLE) -> list[dict]:
    """The stored Gamma event rows: through ``archive`` when given, else read-only from the repo's archive file."""
    if archive is not None:
        try:
            archive.get(bundle)
            return list(archive.load(bundle))
        except (KeyError, FileNotFoundError, OSError, ValueError, AttributeError):
            return []
    from mandel.archive import ARCHIVE_ROOT
    path = ARCHIVE_ROOT / "data" / f"{bundle}.jsonl.gz"
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def resolution_times(archive=None, bundle: str = EVENTS_BUNDLE) -> list[dict]:
    """[{res (unix s), variant, markets, slugs}] of the distinct resolution times of the archived 'Bitcoin above'
    markets, through the harness's own parser so the fetched minute is the one the harness looks up."""
    from mandel.experiments.batch6c_pmxv import btc_market_spec        # lazy: the data layer does not load the harnesses otherwise
    acc: dict[int, dict] = {}
    for r in _event_rows(archive, bundle):
        ev = r.get("value") or {}
        slug = str(ev.get("slug") or "")
        if not ("bitcoin" in slug or "btc" in slug):
            continue
        for mk in ev.get("markets") or []:
            mm = dict(mk)
            mm["_event_slug"] = ev.get("slug")
            mm["_event_end"] = ev.get("endDate")
            mm["_event_description"] = ev.get("description")
            s = btc_market_spec(mm)
            if s is None:
                continue
            a = acc.setdefault(int(s["t_res"]), {"res": int(s["t_res"]), "variant": s["variant"], "markets": 0, "slugs": set()})
            a["markets"] += 1
            a["slugs"].add(s["slug"])
    return [dict(a, slugs=sorted(a["slugs"])[:3]) for _, a in sorted(acc.items())]


def windows(times: Iterable, before_min: int = BEFORE_MIN, after_min: int = AFTER_MIN, now_s: Optional[int] = None,
            first: Optional[str] = None, last: Optional[str] = None) -> list[dict]:
    """One window per resolution time (an int, or a dict with ``res``): bars whose open lies in [res - before, res + after]
    minutes. Windows whose last bar has not closed by ``now_s`` are left out (never stored open); ``first`` / ``last``
    keep resolution days in that range."""
    now = _now_s() if now_s is None else now_s
    out = []
    for t in times:
        d = t if isinstance(t, dict) else {"res": int(t)}
        res = int(d["res"])
        res -= res % 60
        start, end = res - before_min * 60, res + after_min * 60
        day = _day(res)
        if end + 60 > now or (first and day < first[:10]) or (last and day > last[:10]):
            continue
        out.append({"res": res, "start": start, "end": end, "bars": (end - start) // 60 + 1, "variant": d.get("variant"),
                    "markets": d.get("markets"), "et": datetime.fromtimestamp(res, ET).strftime("%H:%M")})
    return out


# ===================================================================================================== klines ==

def klines(client: httpx.Client, th: Throttle, start_ms: int, end_ms: int, symbol: str = SYMBOL, interval: str = INTERVAL,
           limit: int = KLINES_MAX, base_url: str = BASE, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[list], dict]:
    """One request: the klines whose open time lies in [start_ms, end_ms] (at most ``limit``)."""
    r, info = _get(client, f"{base_url}/klines", th, params={"symbol": symbol, "interval": interval, "startTime": start_ms,
                                                              "endTime": end_ms, "limit": limit}, retries=retries, backoff=backoff)
    if r is None:
        return None, info
    try:
        j = r.json()
    except ValueError:
        info["error"] = "not JSON: " + r.text[:120]
        return None, info
    if not isinstance(j, list):
        info["error"] = str(j)[:200]
        return None, info
    return j, info


def kline_row(k: list, res: int, symbol: str = SYMBOL) -> dict:
    t = int(k[0]) // 1000
    v = {"symbol": symbol, "t": t, "open": _f(k[1]), "high": _f(k[2]), "low": _f(k[3]), "close": _f(k[4]), "volume": _f(k[5]),
         "quote_volume": _f(k[7]) if len(k) > 7 else None, "trades": int(k[8]) if len(k) > 8 and k[8] is not None else None,
         "taker_buy_volume": _f(k[9]) if len(k) > 9 else None, "taker_buy_quote_volume": _f(k[10]) if len(k) > 10 else None,
         "close_time": int(k[6]) if len(k) > 6 and k[6] is not None else t * 1000 + 59_999, "res": int(res)}
    return {"source": "binance-vision", "kind": "bar1m", "key": f"{symbol}:{t}", "observed_at": iso(t), "available_at": iso(t + 60), "value": v}


def window_row(w: dict, bars: int, missing: list, calls: int, complete: bool) -> dict:
    v = {"res": w["res"], "res_iso": iso(w["res"]), "et": w.get("et"), "variant": w.get("variant"), "markets": w.get("markets"),
         "start": w["start"], "end": w["end"], "bars_expected": w["bars"], "bars": bars, "missing": missing, "complete": bool(complete), "calls": calls}
    return {"source": "binance-vision", "kind": "window", "key": f"res:{w['res']}", "observed_at": iso(w["res"]), "available_at": iso(w["end"] + 60), "value": v}


def _group(r: dict) -> str:
    return str((r.get("value") or {}).get("res"))


def _sort(r: dict) -> tuple:
    v = r.get("value") or {}
    return (int(v.get("res") or 0), r.get("kind") != "window", int(v.get("t") or 0))


def fetch_window(client: httpx.Client, th: Throttle, w: dict, symbol: str = SYMBOL, base_url: str = BASE, retries: int = 4,
                 backoff: float = 1.0, max_calls: Optional[int] = None) -> tuple[Optional[list], dict]:
    """(rows of one window: its window row first, then its bars; None when a call failed or the preview cap cut it) and
    {calls, missing | failure fields, abort}."""
    bars: dict[int, list] = {}
    calls = 0
    t = w["start"]
    while t <= w["end"]:
        if max_calls is not None and calls >= max_calls:
            return None, {"calls": calls, "truncated": True}
        e = min(t + (KLINES_MAX - 1) * 60, w["end"])
        kl, info = klines(client, th, t * 1000, e * 1000 + 59_999, symbol, INTERVAL, KLINES_MAX, base_url, retries, backoff)
        calls += 1
        if kl is None:
            abort = bool(info.get("retry_after")) or info.get("status") in (403, 418, 451)
            return None, {"calls": calls, **_failure(info), "abort": abort}
        for k in kl:
            if isinstance(k, (list, tuple)) and len(k) >= 7 and t * 1000 <= int(k[0]) <= e * 1000:
                bars[int(k[0]) // 1000] = list(k)
        t = e + 60
    missing = [s for s in range(w["start"], w["end"] + 1, 60) if s not in bars]
    rows = [window_row(w, len(bars), missing, calls, True)] + [kline_row(bars[s], w["res"], symbol) for s in sorted(bars)]
    return rows, {"calls": calls, "missing": len(missing)}


# ====================================================================================================== fetch ==

def plan(wins: list[dict], min_interval: float = PACE, stored_rows: int = 0, chunk: int = CHUNK_WINDOWS) -> dict:
    """Dry-run plan: calls, rows, gzip MB and minutes for ``wins`` (a window costs ceil(bars / 1000) calls; the merges
    re-write the stored rows once per chunk)."""
    calls = sum(math.ceil(w["bars"] / KLINES_MAX) for w in wins)
    rows = sum(w["bars"] + 1 for w in wins)
    chunks = math.ceil(len(wins) / max(chunk, 1)) if wins else 0
    merge_s = sum((stored_rows + rows * (i + 1) / max(chunks, 1)) * MERGE_SECONDS_PER_ROW for i in range(chunks))
    return {"bundle": BUNDLE, "windows": len(wins), "calls": calls, "rows": rows, "gz_mb": round(rows * ROW_GZ / 1e6, 2),
            "minutes": round((calls * max(min_interval, LATENCY) + merge_s) / 60, 1), "weight_per_minute": round(KLINE_WEIGHT * 60 / max(min_interval, LATENCY)),
            "span": [_day(wins[0]["res"]), _day(wins[-1]["res"])] if wins else None,
            "by_variant": {k: sum(1 for w in wins if w.get("variant") == k) for k in sorted({w.get("variant") for w in wins}, key=str)}}


def fetch_binance_resolution_klines(store=None, times: Optional[Iterable] = None, before_min: int = BEFORE_MIN, after_min: int = AFTER_MIN,
                                    first: Optional[str] = None, last: Optional[str] = None, limit: Optional[int] = None,
                                    dry_run: bool = False, skip_stored: bool = True, refresh: bool = False, max_calls: Optional[int] = None,
                                    chunk: int = CHUNK_WINDOWS, min_interval: float = PACE, retries: int = 4, backoff: float = 1.0,
                                    report: Optional[dict] = None, rows_out: Optional[dict] = None, client: Optional[httpx.Client] = None,
                                    log: Optional[Callable] = None, base_url: str = BASE, now_s: Optional[int] = None, **_) -> dict:
    """``binance-1m-BTCUSDT-btc-above``: see the module docstring. Returns the report: ``_windows`` (closed windows of the
    resolution times), ``_already_stored``, ``_plan`` (dry run), ``<bundle>`` = {windows, calls, rows, failed, aborted?,
    truncated?, stored, chunks, first, last}, ``_gitignore``."""
    archive = _archive(store)
    rep = report if report is not None else {}
    tl = resolution_times(archive) if times is None else list(times)
    wins = windows(tl, before_min, after_min, now_s=now_s, first=first, last=last)
    stored = _scan(archive, BUNDLE, ("window",), _group)["window"] if archive is not None else {}
    todo = [w for w in wins if refresh or not skip_stored or not stored.get(str(w["res"]))]
    rep["_windows"] = len(wins)
    rep["_already_stored"] = len(wins) - len(todo)
    if limit is not None:
        todo = todo[:limit]
    rep["_gitignore"] = [GITIGNORE_LINE]
    if dry_run:
        stored_rows = 0
        if archive is not None:
            try:
                stored_rows = int(archive.get(BUNDLE).rows)
            except (KeyError, AttributeError, TypeError, ValueError):
                stored_rows = 0
        rep["_plan"] = plan(todo, min_interval, stored_rows, chunk)
        return rep
    own = client is None
    c = client or _client()
    th = Throttle(min_interval)
    st: dict = {"windows": 0, "calls": 0, "rows": 0, "failed": [], "stored": 0, "chunks": 0, "first": None, "last": None, "missing_minutes": 0}
    buf: list[dict] = []
    done: set[str] = set()
    out_rows: Optional[list] = [] if rows_out is not None else None
    rcp = recipe(before_min, after_min)

    def flush() -> None:
        if not buf:
            return
        buf.sort(key=_sort)
        if archive is not None:
            _merge_store(archive, BUNDLE, iter(buf), set(done), _group, _sort, rcp, TAGS, SCHEMA)
            st["stored"] += len(done)
            st["chunks"] += 1
        if out_rows is not None:
            out_rows.extend(buf)
        buf.clear()
        done.clear()

    try:
        for w in todo:
            left = None if max_calls is None else max_calls - st["calls"]
            if left is not None and left <= 0:
                st["truncated"] = True
                break
            rows, info = fetch_window(c, th, w, SYMBOL, base_url, retries, backoff, left)
            st["calls"] += info.get("calls", 0)
            if rows is None:
                if info.get("truncated"):
                    st["truncated"] = True
                    break
                st["failed"].append({"res": w["res"], "res_iso": iso(w["res"]), **{k: v for k, v in info.items() if k not in ("calls", "abort")}})
                if log:
                    log(f"binance 1m window {iso(w['res'])[:16]}: failed {info.get('status')} {info.get('error') or ''}")
                if info.get("abort"):
                    st["aborted"] = {k: v for k, v in info.items() if k not in ("calls", "abort")}
                    break
                continue
            buf.extend(rows)
            done.add(str(w["res"]))
            st["windows"] += 1
            st["rows"] += len(rows)
            st["missing_minutes"] += info.get("missing", 0)
            st["first"] = st["first"] or iso(w["res"])
            st["last"] = iso(w["res"])
            if log:
                log(f"binance 1m window {iso(w['res'])[:16]} ({w.get('et')} ET, {w.get('variant')}): {len(rows) - 1} bars, {info.get('missing', 0)} missing")
            if len(done) >= max(chunk, 1):
                flush()
        flush()
    except KeyboardInterrupt:
        flush()
        st["_interrupted"] = True
        rep[BUNDLE] = st
        raise
    finally:
        if own:
            c.close()
    if out_rows is not None:
        rows_out[BUNDLE] = out_rows
    rep[BUNDLE] = st
    return rep


# ============================================================================================ one writer, CLI ==

@contextlib.contextmanager
def run_lock(archive):
    """Exclusive, non-blocking lock ``<archive root>/binance_klines.run.lock`` for one storing run (two processes storing
    into one archive leave stale INDEX.json entries). No-op without an archive root."""
    root = getattr(archive, "root", None)
    if root is None:
        yield None
        return
    path = Path(root) / RUN_LOCK
    with open(path, "a+", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError(f"another binance_klines run holds {path}: run one storing process at a time per archive") from None
        try:
            yield path
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def index_check(archive) -> dict:
    """This process's INDEX entry of the bundle against a fresh read of INDEX.json (a mismatch means another process
    wrote the index from a stale view during the run)."""
    try:
        mine = archive.get(BUNDLE)
    except KeyError:
        return {"ok": True, "bundles": 0}
    disk = type(archive)(root=archive.root, ledger=archive.ledger)
    try:
        d = disk.get(BUNDLE)
    except KeyError:
        return {"ok": False, "bundles": 1, "mismatched": [{"bundle": BUNDLE, "index": None, "stored_rows": mine.rows}]}
    ok = (d.sha256, d.rows, d.bytes) == (mine.sha256, mine.rows, mine.bytes)
    out = {"ok": ok, "bundles": 1}
    if not ok:
        out["mismatched"] = [{"bundle": BUNDLE, "index_rows": d.rows, "stored_rows": mine.rows}]
        out["hint"] = "another process wrote INDEX.json from a stale view during this run; re-run with --refresh when nothing else is writing"
    return out


def run(store, **kw) -> dict:
    """``fetch_binance_resolution_klines`` under the run lock (storing runs) with the index check appended."""
    archive = _archive(store)
    if kw.get("dry_run") or archive is None:
        return fetch_binance_resolution_klines(store, **kw)
    with run_lock(archive):
        rep = fetch_binance_resolution_klines(store, **kw)
        if hasattr(archive, "root"):
            rep["_index_check"] = index_check(archive)
        return rep


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m mandel.data.binance_klines",
                                description="Fetch Binance BTCUSDT 1-minute klines around every Polymarket 'Bitcoin above' resolution time "
                                            f"(bundle {BUNDLE}; data-api.binance.vision) into the archive.")
    p.add_argument("--dry-run", action="store_true", help="no request: print the plan (windows, calls, rows, gzip MB, minutes)")
    p.add_argument("--preview", metavar="DIR", help="do not store: write the rows to DIR/<bundle>.preview.jsonl.gz and the report to DIR/report.json")
    p.add_argument("--limit", type=int, help="windows (resolution times) to fetch")
    p.add_argument("--first", help="first resolution day (YYYY-MM-DD)")
    p.add_argument("--last", help="last resolution day (YYYY-MM-DD)")
    p.add_argument("--before-min", type=int, default=BEFORE_MIN, help=f"minutes before the resolution time (default {BEFORE_MIN})")
    p.add_argument("--after-min", type=int, default=AFTER_MIN, help=f"minutes after the resolution time (default {AFTER_MIN})")
    p.add_argument("--max-calls", type=int, help="requests in all (preview; a window cut short is never stored)")
    p.add_argument("--refresh", action="store_true", help="fetch again windows already stored complete")
    p.add_argument("--min-interval", type=float, default=PACE, help=f"seconds between requests (default {PACE})")
    p.add_argument("--chunk", type=int, default=CHUNK_WINDOWS, help=f"windows per store (default {CHUNK_WINDOWS})")
    a = p.parse_args(argv)
    store = None
    if not a.preview:
        from mandel.archive import Archive
        store = Archive()
    rows_out: Optional[dict] = {} if a.preview else None
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    rep = run(store, dry_run=a.dry_run, limit=a.limit, first=a.first, last=a.last, before_min=a.before_min, after_min=a.after_min,
              max_calls=a.max_calls, refresh=a.refresh, min_interval=a.min_interval, chunk=a.chunk, rows_out=rows_out, log=log)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        for name, rows in (rows_out or {}).items():
            with gzip.open(os.path.join(a.preview, f"{name}.preview.jsonl.gz"), "wt", encoding="utf-8") as f:
                for r in rows:
                    f.write(_line(r) + "\n")
        with open(os.path.join(a.preview, "report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, default=str)
    print(json.dumps(rep, indent=1, default=str)[:200000])
    return 0 if (rep.get("_index_check") or {"ok": True})["ok"] and not rep.get(BUNDLE, {}).get("aborted") else 1


if __name__ == "__main__":
    sys.exit(main())
