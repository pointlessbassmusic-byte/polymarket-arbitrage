"""
Deribit trade history for the declared batch-6b bundles of T-263, T-268 and T-257 / T-262.
==========================================================================================

All three come from Deribit's public history API (no key; per-IP rate limits; ``get_instruments`` is limited to
1 request/second), the same tape, paging and conventions as ``mandel.data.options_misc`` section 3, whose helpers this
module imports (``trades_in_window``, ``deribit_option_instruments``, ``expiry_listings``, ``parse_instrument``,
``_get`` with its retries and Retry-After handling). Bundle names and row schemas are the ones declared in
``mandel.experiments.batch6b_drb.REQUESTS``; the harness readers (``fomc_inputs``, ``dvolf_inputs``, ``daily_smiles``)
are run on these rows in the tests.

1. ``deribit-option-trades-fomc`` (T-263). For every scheduled FOMC decision 2022-2026 in the ``fomc-meetings`` bundle
   whose statement time has passed: decision time = 14:00 America/New_York on the decision day (the statement time of
   every scheduled meeting 2022-2026; 18:00 or 19:00 UTC). Window [decision - 24 h, decision):
   ``GET {HIST}get_last_trades_by_currency_and_time?currency=BTC&kind=option&start_timestamp=<decision_ms - 86400000>
   &end_timestamp=<decision_ms - 1>&count=1000&include_old=true&sorting=asc``, paged forward (``trades_in_window``).
   Only trades in the target expiry are kept: the first expiry after the decision whose first instrument was created
   before the decision (listing = min ``creation_timestamp`` over ``get_instruments?currency=BTC&kind=option``,
   expired=true and false, about 77 MB). With daily expiries this is the next day's 08:00 UTC expiry.
   Rows: kind ``option-trade``, value = the raw trade + {decision_day, currency, expiry, expiry_code, strike, type},
   available_at = trade time; kind ``fomc-window``, value = {decision_day, decision_time, currency, target_expiry,
   target_expiry_code, target_listed_at, window_start, window_end, complete} + fetch metadata {trades_seen,
   trades_kept, pages} (not market information) + available_basis; available_at = the later of the meeting's
   ``fomc-meetings`` available_at (the meeting start for scheduled meetings) and the target expiry's listing time: the
   row names the decision time and the target expiry, and nobody knew the target before it was listed.

2. ``deribit-dvol-futures-trades`` (T-268). ``GET {HIST}get_instruments?currency=USDC&kind=future&expired=true`` and
   keep ``BTCDVOL_USDC-*`` (42 monthly futures expiring 2023-04-26 .. 2026-09-30 on 2026-10-15, all 08:00 UTC). Per
   instrument ``GET {HIST}get_last_trades_by_instrument_and_time?instrument_name=<name>&start_timestamp=<expiry_ms -
   8 d>&end_timestamp=<expiry_ms>&count=1000&include_old=true&sorting=asc``, paged forward like ``trades_in_window``.
   Settlement: the declared ``{LIVE}get_last_settlements_by_instrument?type=delivery`` answers 400 "instrument is not
   active" for every expired instrument (probed 2026-10-15), so the delivery price comes from the DVOL index's own
   delivery prices, ``GET {LIVE}get_delivery_prices?index_name=btcdvol_usdc`` (100 per page, about 10 pages, every
   expiry present); the futures settle at exactly that price (BTCDVOL_USDC-30SEP26 delivered at mark 35.5011 =
   the 2026-09-30 index delivery price). An expiry missing there falls back to
   ``{LIVE}get_last_settlements_by_currency?currency=USDC&type=delivery`` around the expiry. The monthly DVOL futures
   trade thinly (BTCDVOL_USDC-30SEP26: 68 trades over its life, none in its last 8 days).
   Rows: kind ``future-trade`` value = {instrument_name, expiry (ISO UTC), timestamp, price, mark_price, index_price,
   amount, direction}, available_at = trade time; kind ``future-settlement`` value = {instrument_name, expiry,
   delivery_price}, available_at = expiry; kind ``future-window`` (fetch metadata, ignored by the harness) value =
   {instrument_name, expiry, listed_at, window_start, window_end, trades_seen, pages, complete, settlement_source},
   available_at = expiry.

3. ``deribit-option-trades-daily-BTC`` (T-257, T-262). For every UTC day 2021-12-01 .. 2026-10-14 (the harness's
   range; ``first``/``last`` reach back to 2019, when the tape has tens of trades per window), the window
   [D 07:00, D 09:00) UTC that ``batch6b_drb.daily_smiles`` samples: ``GET {HIST}get_last_trades_by_currency_and_time?
   currency=BTC&kind=option&start_timestamp=<D 07:00 ms>&end_timestamp=<D 09:00 ms - 1>&count=1000&include_old=true
   &sorting=asc``, paged forward. Kept: the expiries the smiles can use, 1-400 calendar days after D (daily_smiles drops
   T < 1 day, i.e. the same-day 08:00 expiry, and T > 400 days); about 97% of the window's trades.
   Rows: kind ``option-trade`` value = {trade_id, timestamp, instrument_name, price, mark_price, iv, index_price, amount,
   direction} (the raw trade's fields the harness declares) + {currency, expiry, expiry_code, strike, type},
   available_at = trade time; kind ``sample-day`` (fetch metadata; the harness keeps only option-trade rows) value =
   {day, currency, window_start, window_end, hours, dte_days, trades_seen, trades_kept, pages, complete}, available_at
   = window end. A day with no trades is stored as a complete sample-day row with trades_kept 0.

Storage. Every bundle is local disk only (``in_git=False``, always: Deribit states no data licence, so there is no
redistribution right and the repo is public; adding the bundle files to .gitignore is the lead's job). A window (FOMC
decision, DVOL instrument, sample day) is stored only when its paging completed; a failed, interrupted or preview
(``max_pages``) window is never stored and never replaces a stored one. New windows merge into the stored bundle, and
the stored rows of other windows are kept. The merge streams: the stored bundle is copied byte for byte to a temporary
file and merged row by row with the new rows (both sorted), so memory stays at one chunk whatever the bundle size; a
write that fails before the INDEX is updated puts the previous bundle file back. The daily bundle is stored in chunks
of ``chunk_days`` complete days, spilled to a temporary gzip file while they are fetched, and on an interrupt the
complete days fetched so far are stored. ``skip_stored`` skips windows already stored complete (resume a long run).

Estimates (``dry_run=True`` puts the plan in ``report['_plan']``; per-window trade counts measured 2026-10-15):
  * fomc: 38 decisions 2022-01-26 .. 2026-09-16, ~26k BTC option trades per 24 h window (sampled 2022-06-15,
    2024-09-18, 2026-09-16), ~1,000 pages + 2 instrument calls (~77 MB each), ~10 minutes; ~6% of trades are in
    the next-day expiry, about 60k rows, ~3 MB gzip.
  * dvol: ~53 calls (1 instrument list, 42 instruments, ~10 delivery-price pages), < 1 minute, a few hundred rows.
  * daily: 1,779 days, ~1,100-3,300 trades per window (2 pages on a typical day), ~3,900 pages, ~2.9 M rows,
    ~105 MB gzip, ~45-60 minutes including the chunk merges (chunk_days 90).

Each ``fetch_*`` takes ``store`` (an Archive, an ObservationStore whose ``.archive`` is used, or None to only return the
rows), ``limit``, ``dry_run``, ``max_pages``, ``skip_stored`` and a ``report`` dict, as in options_misc. Command line:
``python3 -m mandel.data.deribit_history {fomc,dvol,daily} [--dry-run] [--preview DIR] [--skip-stored] ...``.
"""

from __future__ import annotations

import argparse
import gzip
import heapq
import json
import math
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional
from zoneinfo import ZoneInfo

import httpx

from mandel.data.fetch import Throttle, now_iso
from mandel.data.options_misc import (DAY_MS, DERIBIT_HISTORY, PAGE_SECONDS, _archive, _cap, _client, _get, _iso_ms, _ms,
                                      compact_instrument, deribit_option_instruments, expiry_code, expiry_listings,
                                      parse_instrument, trades_in_window)

LIVE = "https://www.deribit.com/api/v2/public/"
HOUR_MS = 3_600_000
LICENCE_NOTE = ("Deribit states no data licence (no redistribution right) and the repo is public: local disk only "
                "(in_git=False), rebuild from this recipe")
ROW_GZ_BYTES = 37                   # gzip bytes per stored option-trade row (catalyst bundle 36; daily preview 2026-10-15)
MERGE_SECONDS_PER_ROW = 12e-6       # one streamed re-write of a stored row (gunzip, parse, dump, gzip -9), measured locally


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _day_of(ms: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=int(ms) // DAY_MS)).isoformat()


def _line(r: dict) -> str:
    return json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str)


def _read_gz(path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


# ================================================================================= streamed merge into a bundle ==

def _bundle_snapshot(archive, name: str, tmp_dir: Optional[str] = None) -> tuple[Optional[str], Optional[Path]]:
    """(temporary copy of the stored bundle, the archive file it was copied from). The file is copied byte for byte
    when it sits where ``Archive.store`` writes it (``<root>/data/<name>.jsonl.gz``), else streamed through
    ``archive.load``. (None, None) when nothing is stored or the bundle is not on this machine."""
    try:
        archive.get(name)
    except (KeyError, AttributeError):
        return None, None
    src = Path(getattr(archive, "root", ".")) / "data" / f"{name}.jsonl.gz"
    fd, tmp = tempfile.mkstemp(prefix=f"{name}-", suffix=".jsonl.gz", dir=tmp_dir)
    os.close(fd)
    if src.exists():
        shutil.copyfile(src, tmp)
        return tmp, src
    try:
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=1) as f:
            for r in archive.load(name):
                f.write(_line(r) + "\n")
        return tmp, None
    except (KeyError, FileNotFoundError, OSError, ValueError):
        os.unlink(tmp)
        return None, None


def _merge_store(archive, name: str, fresh: Iterable[dict], done: set, group: Callable[[dict], str],
                 sort_key: Callable[[dict], tuple], recipe: str, tags: list[str], schema: str,
                 tmp_dir: Optional[str] = None):
    """Store ``name`` as the stored rows whose group is not in ``done`` merged with ``fresh`` (rows of the ``done``
    groups, sorted by ``sort_key``), streamed: one row in memory at a time. Always ``in_git=False``. A write that fails
    before the INDEX entry changes restores the previous bundle file."""
    tmp, src = _bundle_snapshot(archive, name, tmp_dir)
    old_sha = archive.get(name).sha256 if tmp else None
    old = (r for r in _read_gz(tmp) if group(r) not in done) if tmp else iter(())
    try:
        return archive.store(name, kind="data", rows=heapq.merge(old, fresh, key=sort_key), recipe=recipe, tags=tags,
                             schema=schema, in_git=False)
    except BaseException:
        if tmp and src is not None and archive.get(name).sha256 == old_sha:
            shutil.copyfile(tmp, src)
        raise
    finally:
        if hasattr(old, "close"):
            old.close()
        if tmp:
            os.unlink(tmp)


def _scan(archive, name: str, kinds: tuple, group: Callable[[dict], str]) -> dict[str, dict[str, bool]]:
    """{kind: {group: complete}} over the stored rows of ``kinds`` (one streamed pass; empty when nothing is stored)."""
    out: dict[str, dict[str, bool]] = {k: {} for k in kinds}
    if archive is None:
        return out
    try:
        archive.get(name)
        for r in archive.load(name):
            if r.get("kind") in out:
                out[r["kind"]][group(r)] = bool((r.get("value") or {}).get("complete", True))
    except (KeyError, FileNotFoundError, OSError, ValueError):
        pass
    return out


class _Spill:
    """Rows of complete windows, written to a temporary gzip JSONL file while a long run proceeds."""

    def __init__(self, tmp_dir: Optional[str] = None):
        fd, self.path = tempfile.mkstemp(prefix="deribit-spill-", suffix=".jsonl.gz", dir=tmp_dir)
        os.close(fd)
        self._f = gzip.open(self.path, "wt", encoding="utf-8", compresslevel=1)
        self.n = 0

    def write(self, rows: Iterable[dict]) -> None:
        for r in rows:
            self._f.write(_line(r) + "\n")
            self.n += 1

    def rows(self) -> Iterator[dict]:
        self._f.close()
        return _read_gz(self.path)

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()
        if os.path.exists(self.path):
            os.unlink(self.path)


def _abort_info(info: dict) -> Optional[dict]:
    err = info.get("error") or {}
    return {"retry_after_s": err["retry_after"], "body": err.get("body")} if err.get("retry_after") else None


# ============================================================================ 1. FOMC windows (T-263) ==

FOMC_BUNDLE = "deribit-option-trades-fomc"
FOMC_MEETINGS = "fomc-meetings"
FOMC_FIRST, FOMC_LAST = "2022-01-01", "2026-12-31"
FOMC_TZ = ZoneInfo("America/New_York")
FOMC_STATEMENT = (14, 0)                       # 2:00 pm Eastern: the statement time of every scheduled decision 2022-2026
FOMC_HOURS_BEFORE = 24
# BTC option trades in the 24 h before the decision, sampled 2026-10-15 (2022-06-15, 2024-09-18, 2026-09-16 windows);
# used only for the dry-run estimate.
FOMC_WINDOW_TRADES = {2022: 26000, 2023: 22000, 2024: 30000, 2025: 28000, 2026: 22000}
FOMC_KEEP_SHARE = 0.06                         # share of the window's trades in the next-day expiry (same samples)
FOMC_SCHEMA = ("kind option-trade: value = raw Deribit trade {trade_id, trade_seq, timestamp (ms), instrument_name, price (coin), "
               "mark_price, iv, index_price, amount, contracts?, direction, tick_direction, block_trade_id?} + {decision_day, currency, "
               "expiry, expiry_code, strike, type}; only the target expiry; available_at = trade time | kind fomc-window: value = "
               "{decision_day, decision_time (14:00 America/New_York, ISO UTC), currency, target_expiry, target_expiry_code, "
               "target_listed_at, window_start, window_end (= decision_time, exclusive), complete, trades_seen, trades_kept, pages "
               "(these four are fetch metadata, not market information), available_basis}; available_at = max(fomc-meetings "
               "available_at of the meeting, target_listed_at)")


def fomc_decision_ms(day: str) -> int:
    """14:00 America/New_York on ``day`` in UTC ms (18:00 UTC in summer time, 19:00 UTC in winter)."""
    d = date.fromisoformat(day[:10])
    return int(datetime(d.year, d.month, d.day, *FOMC_STATEMENT, tzinfo=FOMC_TZ).timestamp() * 1000)


def load_fomc_meetings(archive=None) -> list[dict]:
    """The ``fomc-meetings`` rows as {start, decision_day, scheduled, label, ..., available_at}: from ``archive`` when
    given, else read-only from the repo's archive file."""
    rows: list[dict] = []
    if archive is not None:
        try:
            archive.get(FOMC_MEETINGS)
            rows = list(archive.load(FOMC_MEETINGS))
        except (KeyError, FileNotFoundError, OSError, ValueError):
            rows = []
    else:
        from mandel.archive import ARCHIVE_ROOT
        path = ARCHIVE_ROOT / "data" / f"{FOMC_MEETINGS}.jsonl.gz"
        rows = list(_read_gz(path)) if path.exists() else []
    return [{**r["value"], "available_at": r.get("available_at")} for r in rows if isinstance(r.get("value"), dict)]


def fomc_windows(meetings: Iterable[dict], listings: Optional[dict[int, dict]] = None, first: str = FOMC_FIRST,
                 last: str = FOMC_LAST, currency: str = "BTC", hours_before: float = FOMC_HOURS_BEFORE,
                 now_ms: Optional[int] = None) -> list[dict]:
    """One window per scheduled decision day in [first, last] whose decision time has passed: [decision - hours_before,
    decision). With ``listings`` (``expiry_listings`` of the currency's options) the target is the first expiry after
    the decision whose first instrument was created before the decision."""
    now = _now_ms() if now_ms is None else now_ms
    out, seen = [], set()
    for m in sorted(meetings, key=lambda m: str(m.get("decision_day") or "")):
        day = m.get("decision_day")
        if not day or day in seen or not m.get("scheduled", True) or not (first <= day <= last):
            continue
        dms = fomc_decision_ms(day)
        if dms > now:
            continue
        seen.add(day)
        known = m.get("available_at") or ((m.get("start") or day)[:10] + "T00:00:00+00:00")
        w = {"decision_day": day, "decision_time": _iso_ms(dms), "currency": currency, "start_ms": dms - int(hours_before * HOUR_MS),
             "end_ms": dms, "meeting_available_at": known, "target": None}
        if listings is not None:
            cand = sorted(e for e, L in listings.items() if e > dms and L["listed_at"] < dms)
            if cand:
                e = cand[0]
                w["target"] = {"expiry_ts": e, "expiry": _iso_ms(e)[:10], "expiry_code": expiry_code(e),
                               "listed_at": _iso_ms(listings[e]["listed_at"]), "settlement_period": listings[e].get("settlement_period")}
        out.append(w)
    return out


def _fomc_group(r: dict) -> str:
    v = r.get("value") or {}
    return f"{v.get('decision_day')}:{v.get('currency')}"


def _fomc_sort(r: dict) -> tuple:
    v = r.get("value") or {}
    return (str(v.get("decision_day") or ""), str(v.get("currency") or ""), r.get("kind") != "fomc-window",
            int(v.get("timestamp") or 0), str(v.get("trade_id") or ""))


def _fomc_trade_row(t: dict, w: dict, observed_at: str) -> dict:
    p = parse_instrument(t.get("instrument_name", "")) or {}
    v = {"decision_day": w["decision_day"], "currency": w["currency"], "expiry": p.get("expiry"), "expiry_code": p.get("expiry_code"),
         "strike": p.get("strike"), "type": p.get("type"), **t}
    return {"source": "deribit-history", "kind": "option-trade", "key": f"{w['decision_day']}:{w['currency']}:{t.get('trade_id')}",
            "observed_at": observed_at, "available_at": _cap(_iso_ms(int(t["timestamp"])), observed_at), "value": v}


def _fomc_window_row(w: dict, info: dict, kept: int, observed_at: str) -> dict:
    tgt = w.get("target") or {}
    cands = [w["meeting_available_at"]] + ([tgt["listed_at"]] if tgt.get("listed_at") else [])
    av = max(cands, key=_ms)
    basis = ("fomc-meetings available_at (the meeting start)" if av == cands[0]
             else "target expiry listing time (after the meeting was known)")
    v = {"decision_day": w["decision_day"], "decision_time": w["decision_time"], "currency": w["currency"],
         "target_expiry": tgt.get("expiry"), "target_expiry_code": tgt.get("expiry_code"), "target_listed_at": tgt.get("listed_at"),
         "window_start": _iso_ms(w["start_ms"]), "window_end": _iso_ms(w["end_ms"]), "complete": bool(info.get("complete")),
         "trades_seen": info.get("seen"), "trades_kept": kept, "pages": info.get("pages"), "available_basis": basis}
    return {"source": "mandel-fomc", "kind": "fomc-window", "key": f"{w['decision_day']}:{w['currency']}", "observed_at": observed_at,
            "available_at": _cap(av, observed_at), "value": v}


def _fomc_plan(windows: list[dict], min_interval: float) -> dict:
    per, calls, seen = [], 0, 0
    for w in windows:
        yr = int(w["decision_day"][:4])
        n = FOMC_WINDOW_TRADES.get(yr) or FOMC_WINDOW_TRADES[min(max(yr, min(FOMC_WINDOW_TRADES)), max(FOMC_WINDOW_TRADES))]
        c = max(1, math.ceil(n / 1000))
        per.append({"decision_day": w["decision_day"], "est_trades": n, "est_calls": c})
        calls += c
        seen += n
    rows = int(seen * FOMC_KEEP_SHARE) + len(windows)
    return {"windows": len(windows), "est_trades_seen": seen, "est_calls": calls, "est_rows": rows,
            "est_gz_mb": round(rows * ROW_GZ_BYTES / 1e6, 1), "est_minutes": round(calls * max(min_interval, PAGE_SECONDS) / 60 + 1),
            "per_window": per}


def fetch_deribit_fomc_trades(store=None, meetings: Optional[list[dict]] = None, currency: str = "BTC", first: str = FOMC_FIRST,
                              last: str = FOMC_LAST, limit: Optional[int] = None, dry_run: bool = False, max_pages: Optional[int] = None,
                              client: Optional[httpx.Client] = None, instruments: Optional[list[dict]] = None,
                              hours_before: float = FOMC_HOURS_BEFORE, min_interval: float = 0.25, retries: int = 4, backoff: float = 1.0,
                              report: Optional[dict] = None, skip_stored: bool = False, now_ms: Optional[int] = None,
                              tmp_dir: Optional[str] = None, log: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Bundle ``deribit-option-trades-fomc`` (local disk only). Returns the archive rows of this run.

    ``meetings`` defaults to the ``fomc-meetings`` bundle (of ``store``'s archive, else the repo's archive file);
    ``instruments`` (the currency's compact option list) skips the two large get_instruments downloads; ``limit`` caps
    the number of windows; ``max_pages`` caps pages per window (a preview: never stored). Complete windows replace the
    same windows in the stored bundle, other stored windows are kept; the store also happens on an interrupt."""
    rep = report if report is not None else {}
    archive = _archive(store)
    name = FOMC_BUNDLE
    mts = meetings if meetings is not None else load_fomc_meetings(archive)
    windows = fomc_windows(mts, None, first, last, currency, hours_before, now_ms)
    stored = _scan(archive, name, ("fomc-window",), _fomc_group)["fomc-window"]
    if skip_stored:
        have = {k for k, ok in stored.items() if ok}
        rep["_already_stored"] = sorted(k for k in have if any(f"{w['decision_day']}:{currency}" == k for w in windows))
        windows = [w for w in windows if f"{w['decision_day']}:{currency}" not in have]
    if limit is not None:
        windows = windows[:limit]
    if dry_run:
        rep["_plan"] = {**_fomc_plan(windows, min_interval), "instrument_calls": 0 if instruments is not None else 2,
                        "instrument_mb_each": 77, "min_interval": min_interval}
        return []
    own = client is None
    c = client or _client()
    th = Throttle(min_interval)
    th_inst = Throttle(max(min_interval, 1.1))
    rows: list[dict] = []
    done: set[str] = set()
    try:
        insts = instruments if instruments is not None else deribit_option_instruments(currency, c, th_inst, retries=retries,
                                                                                         backoff=max(backoff, 1.0) if backoff else 0)
        listings = expiry_listings(insts) if insts else None
        windows = fomc_windows([{"decision_day": w["decision_day"], "available_at": w["meeting_available_at"]} for w in windows],
                               listings, first, last, currency, hours_before, now_ms)
        for w in windows:
            key = f"{w['decision_day']}:{currency}"
            tgt = w.get("target")
            if not tgt:
                rep[key] = {"skipped": "no expiry after the decision listed before it (instrument list missing or empty)"}
                continue
            kept, info = trades_in_window(currency, w["start_ms"], w["end_ms"], c, th,
                                          keep=lambda t, code=tgt["expiry_code"]: (parse_instrument(t.get("instrument_name", "")) or {}).get("expiry_code") == code,
                                          max_pages=max_pages, retries=retries, backoff=backoff)
            observed = now_iso()
            rows.extend(_fomc_trade_row(t, w, observed) for t in kept)
            rows.append(_fomc_window_row(w, info, len(kept), observed))
            rep[key] = {**info, "kept": len(kept), "target": tgt["expiry_code"]}
            if log:
                log(f"fomc {key}: {info.get('seen')} seen, {len(kept)} kept in {tgt['expiry_code']}, {info.get('pages')} pages, complete={info.get('complete')}")
            if info["complete"]:
                done.add(key)
            elif _abort_info(info):
                rep["_aborted"] = {"window": key, **_abort_info(info)}
                break
    finally:                                                # also on an interrupt: complete windows are kept
        if own:
            c.close()
        if archive is not None and done:
            keys = sorted({k for k, ok in stored.items() if ok} | done)
            fresh = sorted((r for r in rows if _fomc_group(r) in done), key=_fomc_sort)
            e = _merge_store(archive, name, fresh, done, _fomc_group, _fomc_sort, tags=["options", "crypto", "deribit", "trades", "events", "fomc", "T-263"],
                             schema=FOMC_SCHEMA, tmp_dir=tmp_dir,
                             recipe=(f"GET {DERIBIT_HISTORY}get_last_trades_by_currency_and_time?currency={currency}&kind=option&start_timestamp="
                                     f"<decision_ms - {int(hours_before * HOUR_MS)}>&end_timestamp=<decision_ms - 1>&count=1000&include_old=true&sorting=asc, "
                                     f"paged forward (mandel.data.options_misc.trades_in_window), for every scheduled FOMC decision {first}..{last} in "
                                     f"fomc-meetings whose statement time had passed (decision_ms = 14:00 America/New_York on decision_day), keeping only "
                                     f"the first expiry after the decision listed before it (listing = min creation_timestamp from {DERIBIT_HISTORY}"
                                     f"get_instruments?currency={currency}&kind=option, expired=true and false); via "
                                     f"mandel.data.deribit_history.fetch_deribit_fomc_trades; {min_interval}s pacing, {retries} tries with exponential "
                                     f"backoff on 429/5xx. Trade available_at = trade time; window available_at = max(meeting known, target listing). "
                                     f"Windows stored: {', '.join(keys)}. {LICENCE_NOTE}"))
            rep["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git, "windows": keys}
    return rows


# ====================================================================== 2. BTC DVOL futures (T-268) ==

DVOLF_BUNDLE = "deribit-dvol-futures-trades"
DVOLF_CURRENCY = "USDC"
DVOLF_PREFIX = "BTCDVOL_USDC-"
DVOL_INDEX = "btcdvol_usdc"
DVOLF_LEAD_DAYS = 8.0
DVOLF_EXPIRED = 42                  # expired BTCDVOL_USDC futures on 2026-10-15 (2023-04-26 .. 2026-09-30); dry-run estimate only
DVOL_DELIVERY_RECORDS = 989         # btcdvol_usdc delivery prices on 2026-10-15 (2023-03-24 on); dry-run estimate only
FUTURE_TRADE_FIELDS = ("timestamp", "price", "mark_price", "index_price", "amount", "direction")
_DVOL_ORDER = {"future-window": 0, "future-trade": 1, "future-settlement": 2}
DVOLF_SCHEMA = ("kind future-trade: value = {instrument_name, expiry (ISO UTC), timestamp (ms), price, mark_price, index_price (the "
                "BTC DVOL index), amount, direction}, available_at = trade time | kind future-settlement: value = {instrument_name, expiry, "
                "delivery_price}, available_at = expiry | kind future-window (fetch metadata, not market information): value = "
                "{instrument_name, expiry, listed_at, window_start, window_end, trades_seen, pages, complete, settlement_source}, "
                "available_at = expiry")


def dvol_future_instruments(client: httpx.Client, throttle: Throttle, retries: int = 3, backoff: float = 2.0,
                            currency: str = DVOLF_CURRENCY, prefix: str = DVOLF_PREFIX) -> list[dict]:
    """Compact expired futures of ``currency`` whose name starts with ``prefix``, by expiry (one ~0.9 MB call)."""
    r, _ = _get(client, DERIBIT_HISTORY + "get_instruments", throttle, params={"currency": currency, "kind": "future", "expired": "true"},
                retries=retries, backoff=backoff)
    if r is None:
        return []
    try:
        res = r.json().get("result") or []
    except ValueError:
        return []
    out = [compact_instrument(x) for x in res if str(x.get("instrument_name", "")).startswith(prefix)]
    return sorted(out, key=lambda x: (int(x.get("expiration_timestamp") or 0), x["instrument_name"]))


def instrument_trades(instrument: str, start_ms: int, end_ms: int, client: httpx.Client, throttle: Throttle,
                      max_pages: Optional[int] = None, retries: int = 4, backoff: float = 1.0) -> tuple[list[dict], dict]:
    """All trades of one instrument in [start_ms, end_ms), paged forward by the rules of
    ``options_misc.trades_in_window`` (next page from the last timestamp seen, de-duplicated by trade_id at the boundary,
    one millisecond further when a page brought nothing new). Returns (trades, info{pages, seen, complete, error?})."""
    out: list[dict] = []
    info: dict = {"pages": 0, "seen": 0, "complete": False}
    cursor, boundary = start_ms, set()
    while True:
        if max_pages is not None and info["pages"] >= max_pages:
            info["stopped"] = "max_pages"
            break
        r, ginfo = _get(client, DERIBIT_HISTORY + "get_last_trades_by_instrument_and_time", throttle,
                        params={"instrument_name": instrument, "start_timestamp": cursor, "end_timestamp": end_ms - 1, "count": 1000,
                                "include_old": "true", "sorting": "asc"}, retries=retries, backoff=backoff)
        if r is None:
            info["error"] = {k: ginfo.get(k) for k in ("status", "error", "body", "attempts", "retry_after") if ginfo.get(k) is not None}
            break
        try:
            res = r.json().get("result") or {}
        except ValueError:
            info["error"] = {"status": r.status_code, "error": "invalid JSON"}
            break
        trades = res.get("trades") or []
        info["pages"] += 1
        new = [t for t in trades if t.get("trade_id") not in boundary and start_ms <= int(t.get("timestamp", -1)) < end_ms]
        info["seen"] += len(new)
        out.extend(new)
        if not res.get("has_more") or not trades:
            info["complete"] = True
            break
        lastts = max(int(t["timestamp"]) for t in trades)
        nxt = lastts if (new and lastts > cursor) else lastts + 1
        if nxt >= end_ms:
            info["complete"] = True
            break
        boundary = {t.get("trade_id") for t in trades if int(t["timestamp"]) >= nxt}
        cursor = nxt
    return out, info


def delivery_prices(index_name: str, client: httpx.Client, throttle: Throttle, page: int = 100, max_pages: int = 200,
                    retries: int = 4, backoff: float = 1.0) -> tuple[dict[str, float], dict]:
    """{date: delivery_price} of a Deribit index (``get_delivery_prices``, newest first, ``page`` per call, paged by
    offset until records_total). Returns (prices, info{pages, records, complete, error?})."""
    out: dict[str, float] = {}
    info: dict = {"pages": 0, "complete": False}
    off = 0
    while info["pages"] < max_pages:
        r, ginfo = _get(client, LIVE + "get_delivery_prices", throttle, params={"index_name": index_name, "offset": off, "count": page},
                        retries=retries, backoff=backoff)
        if r is None:
            info["error"] = {k: ginfo.get(k) for k in ("status", "error", "body", "attempts", "retry_after") if ginfo.get(k) is not None}
            break
        try:
            res = r.json().get("result") or {}
        except ValueError:
            info["error"] = {"status": r.status_code, "error": "invalid JSON"}
            break
        data = res.get("data") or []
        info["pages"] += 1
        for x in data:
            try:
                out[str(x["date"])] = float(x["delivery_price"])
            except (KeyError, TypeError, ValueError):
                continue
        off += len(data)
        total = res.get("records_total")
        if not data or len(data) < page or (total is not None and off >= int(total)):
            info["complete"] = True
            break
    info["records"] = len(out)
    return out, info


def currency_settlement(instrument: str, expiry_ms: int, client: httpx.Client, throttle: Throttle, currency: str = DVOLF_CURRENCY,
                        count: int = 1000, max_pages: int = 3, retries: int = 4, backoff: float = 1.0) -> Optional[float]:
    """Delivery price of ``instrument`` from ``get_last_settlements_by_currency`` (type delivery, newest first from one
    hour after the expiry): the settlement's mark price, the price the position delivered at. None when not found."""
    params: dict = {"currency": currency, "type": "delivery", "count": count, "search_start_timestamp": expiry_ms + HOUR_MS}
    for _ in range(max_pages):
        r, _info = _get(client, LIVE + "get_last_settlements_by_currency", throttle, params=params, retries=retries, backoff=backoff)
        if r is None:
            return None
        try:
            res = r.json().get("result") or {}
        except ValueError:
            return None
        sets = res.get("settlements") or []
        for s in sets:
            if s.get("instrument_name") == instrument and abs(int(s.get("timestamp", 0)) - expiry_ms) <= HOUR_MS:
                try:
                    return float(s["mark_price"])
                except (KeyError, TypeError, ValueError):
                    return None
        cont = res.get("continuation")
        if not sets or not cont or cont == "none" or min(int(s.get("timestamp", 0)) for s in sets) < expiry_ms - HOUR_MS:
            return None
        params = {**params, "continuation": cont}
    return None


def _dvol_group(r: dict) -> str:
    return str((r.get("value") or {}).get("instrument_name"))


def _dvol_sort(r: dict) -> tuple:
    v = r.get("value") or {}
    return (str(v.get("expiry") or ""), str(v.get("instrument_name") or ""), _DVOL_ORDER.get(r.get("kind"), 3),
            int(v.get("timestamp") or 0), str(r.get("key") or ""))


def _future_trade_row(t: dict, expiry_iso: str, observed_at: str) -> dict:
    v = {"instrument_name": t.get("instrument_name"), "expiry": expiry_iso, **{k: t.get(k) for k in FUTURE_TRADE_FIELDS}}
    return {"source": "deribit-history", "kind": "future-trade", "key": f"{v['instrument_name']}:{t.get('trade_id')}",
            "observed_at": observed_at, "available_at": _cap(_iso_ms(int(t["timestamp"])), observed_at), "value": v}


def _settlement_row(inst: str, expiry_iso: str, price: float, source: str, observed_at: str) -> dict:
    return {"source": source, "kind": "future-settlement", "key": inst, "observed_at": observed_at,
            "available_at": _cap(expiry_iso, observed_at), "value": {"instrument_name": inst, "expiry": expiry_iso, "delivery_price": price}}


def _future_window_row(x: dict, start_ms: int, end_ms: int, info: dict, settlement_source: Optional[str], observed_at: str) -> dict:
    exp = _iso_ms(int(x["expiration_timestamp"]))
    v = {"instrument_name": x["instrument_name"], "expiry": exp,
         "listed_at": _iso_ms(int(x["creation_timestamp"])) if x.get("creation_timestamp") is not None else None,
         "window_start": _iso_ms(start_ms), "window_end": _iso_ms(end_ms - 1), "trades_seen": info.get("seen"), "pages": info.get("pages"),
         "complete": bool(info.get("complete")), "settlement_source": settlement_source}
    return {"source": "mandel-deribit-dvol", "kind": "future-window", "key": x["instrument_name"], "observed_at": observed_at,
            "available_at": _cap(exp, observed_at), "value": v}


def fetch_deribit_dvol_futures(store=None, limit: Optional[int] = None, dry_run: bool = False, max_pages: Optional[int] = None,
                               client: Optional[httpx.Client] = None, instruments: Optional[list[dict]] = None,
                               deliveries: Optional[dict[str, float]] = None, lead_days: float = DVOLF_LEAD_DAYS,
                               min_interval: float = 0.25, retries: int = 4, backoff: float = 1.0, report: Optional[dict] = None,
                               skip_stored: bool = False, now_ms: Optional[int] = None, tmp_dir: Optional[str] = None,
                               log: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Bundle ``deribit-dvol-futures-trades`` (local disk only): every expired BTCDVOL_USDC future's trades over
    [expiry - lead_days, expiry] and its delivery price. Returns the archive rows of this run. ``instruments`` (compact
    futures list) and ``deliveries`` ({date: btcdvol_usdc delivery price}) skip those downloads. An instrument is
    stored when its trade paging completed; ``skip_stored`` skips instruments stored complete with a settlement."""
    rep = report if report is not None else {}
    archive = _archive(store)
    name = DVOLF_BUNDLE
    now = _now_ms() if now_ms is None else now_ms
    sc = _scan(archive, name, ("future-window", "future-settlement"), _dvol_group)
    have = {k for k, ok in sc["future-window"].items() if ok and k in sc["future-settlement"]} if skip_stored else set()
    if dry_run:
        n = len([x for x in instruments if x["instrument_name"] not in have]) if instruments is not None else DVOLF_EXPIRED - len(have)
        n = min(n, limit) if limit is not None else n
        dcalls = 0 if deliveries is not None else math.ceil(DVOL_DELIVERY_RECORDS / 100)
        calls = (0 if instruments is not None else 1) + n + dcalls
        rep["_plan"] = {"instruments": n, "est_calls": calls, "est_rows": n * 12, "est_gz_mb": 0.1,
                        "est_minutes": round(calls * max(min_interval, PAGE_SECONDS) / 60 + 0.5, 1), "lead_days": lead_days}
        return []
    own = client is None
    c = client or _client()
    th = Throttle(min_interval)
    th_inst = Throttle(max(min_interval, 1.1))
    rows: list[dict] = []
    done: set[str] = set()
    try:
        insts = instruments if instruments is not None else dvol_future_instruments(c, th_inst, retries=retries, backoff=max(backoff, 1.0) if backoff else 0)
        insts = [x for x in insts if x.get("expiration_timestamp") is not None and int(x["expiration_timestamp"]) <= now
                 and str(x["instrument_name"]).startswith(DVOLF_PREFIX)]
        if have:
            rep["_already_stored"] = sorted(x["instrument_name"] for x in insts if x["instrument_name"] in have)
            insts = [x for x in insts if x["instrument_name"] not in have]
        if limit is not None:
            insts = insts[:limit]
        rep["_instruments"] = len(insts)
        if deliveries is None:
            deliveries, dinfo = delivery_prices(DVOL_INDEX, c, th, retries=retries, backoff=backoff)
            rep["_delivery_prices"] = dinfo
        for x in insts:
            inst, e = x["instrument_name"], int(x["expiration_timestamp"])
            exp = _iso_ms(e)
            start, end = e - int(lead_days * DAY_MS), e + 1               # end_timestamp = expiry_ms (inclusive)
            trades, info = instrument_trades(inst, start, end, c, th, max_pages=max_pages, retries=retries, backoff=backoff)
            price, source = deliveries.get(exp[:10]), "deribit-delivery-prices"
            if price is None:
                price, source = currency_settlement(inst, e, c, th, retries=retries, backoff=backoff), "deribit-settlements"
            observed = now_iso()
            rows.extend(_future_trade_row(t, exp, observed) for t in trades)
            rows.append(_future_window_row(x, start, end, info, source if price is not None else None, observed))
            if price is not None:
                rows.append(_settlement_row(inst, exp, price, source, observed))
            rep[inst] = {**info, "settlement": price, "settlement_source": source if price is not None else None}
            if log:
                log(f"dvol {inst}: {info.get('seen')} trades, settlement {price}, complete={info.get('complete')}")
            if info["complete"]:
                done.add(inst)
            elif _abort_info(info):
                rep["_aborted"] = {"instrument": inst, **_abort_info(info)}
                break
    finally:
        if own:
            c.close()
        if archive is not None and done:
            names = sorted({k for k, ok in sc["future-window"].items() if ok} | done)
            fresh = sorted((r for r in rows if _dvol_group(r) in done), key=_dvol_sort)
            e = _merge_store(archive, name, fresh, done, _dvol_group, _dvol_sort, tags=["crypto", "deribit", "dvol", "futures", "trades", "T-268"],
                             schema=DVOLF_SCHEMA, tmp_dir=tmp_dir,
                             recipe=(f"GET {DERIBIT_HISTORY}get_instruments?currency={DVOLF_CURRENCY}&kind=future&expired=true (keep {DVOLF_PREFIX}*), then "
                                     f"per instrument GET {DERIBIT_HISTORY}get_last_trades_by_instrument_and_time?instrument_name=<name>&start_timestamp="
                                     f"<expiry_ms - {lead_days:g}*86400000>&end_timestamp=<expiry_ms>&count=1000&include_old=true&sorting=asc, paged "
                                     f"forward; delivery price from GET {LIVE}get_delivery_prices?index_name={DVOL_INDEX} (paged by offset; "
                                     f"{LIVE}get_last_settlements_by_instrument answers 'instrument is not active' for expired instruments), else "
                                     f"{LIVE}get_last_settlements_by_currency?currency={DVOLF_CURRENCY}&type=delivery; via "
                                     f"mandel.data.deribit_history.fetch_deribit_dvol_futures; {min_interval}s pacing, {retries} tries with exponential "
                                     f"backoff. Trade available_at = trade time; settlement available_at = expiry. Instruments stored: "
                                     f"{names[0]}..{names[-1]} ({len(names)}). {LICENCE_NOTE}"))
            rep["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git, "instruments": len(names)}
    return rows


# =================================================================== 3. daily option-trade samples (T-257, T-262) ==

DAILY_PREFIX = "deribit-option-trades-daily-"
DAILY_FIRST, DAILY_LAST = "2021-12-01", "2026-10-14"
DAILY_HOURS = (7, 9)                    # [07:00, 09:00) UTC, the window batch6b_drb.daily_smiles samples
DAILY_DTE_DAYS = (1, 400)               # expiry date minus sample day: daily_smiles keeps 1/365 <= T <= 400/365
DAILY_CHUNK_DAYS = 90
DAILY_TRADE_FIELDS = ("trade_id", "timestamp", "instrument_name", "price", "mark_price", "iv", "index_price", "amount", "direction")
# BTC option trades in the 07:00-09:00 UTC window, mean of the days sampled 2026-10-15 (2019-06-03 .. 2026-10-14, 15 days);
# dry-run estimate only. A busy day (2024-03-01) had 3,343.
DAILY_WINDOW_TRADES = {2019: 60, 2020: 270, 2021: 1150, 2022: 1650, 2023: 1630, 2024: 2360, 2025: 1770, 2026: 1240}
DAILY_KEEP_SHARE = 0.97                 # share of the window's trades in expiries 1-400 days out (same samples)
DAILY_SCHEMA = ("kind option-trade: value = {trade_id, timestamp (ms), instrument_name, price (coin), mark_price, iv, index_price, amount, "
                "direction} (fields of the raw Deribit trade) + {currency, expiry, expiry_code, strike, type}; trades in [day 07:00, day 09:00) "
                "UTC in expiries 1-400 calendar days after the day; available_at = trade time | kind sample-day (fetch metadata, not market "
                "information; the harness reads option-trade rows only): value = {day, currency, window_start, window_end, hours, dte_days, "
                "trades_seen, trades_kept, pages, complete}, available_at = window end")


def daily_bundle(currency: str = "BTC") -> str:
    return f"{DAILY_PREFIX}{currency}"


def daily_window(day: str, hours: tuple = DAILY_HOURS) -> tuple[int, int]:
    d0 = _ms(day[:10])
    return d0 + int(hours[0] * HOUR_MS), d0 + int(hours[1] * HOUR_MS)


def sample_days(first: str = DAILY_FIRST, last: str = DAILY_LAST, hours: tuple = DAILY_HOURS, now_ms: Optional[int] = None) -> list[str]:
    """Every UTC day in [first, last] whose sample window has ended."""
    now = _now_ms() if now_ms is None else now_ms
    out, d, end = [], date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        if daily_window(d.isoformat(), hours)[1] <= now:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _dte_keep(day: str, dte_days: Optional[tuple]) -> Callable[[dict], bool]:
    d0 = date.fromisoformat(day)

    def keep(t: dict) -> bool:
        p = parse_instrument(t.get("instrument_name", ""))
        if p is None:
            return False
        if dte_days is None:
            return True
        k = (date.fromisoformat(p["expiry"]) - d0).days
        return dte_days[0] <= k <= dte_days[1]
    return keep


def _daily_group(r: dict) -> str:
    v = r.get("value") or {}
    return str(v["day"]) if r.get("kind") == "sample-day" else _day_of(int(v.get("timestamp") or 0))


def _daily_sort(r: dict) -> tuple:
    v = r.get("value") or {}
    return (_daily_group(r), r.get("kind") != "sample-day", int(v.get("timestamp") or 0), str(v.get("trade_id") or ""))


def _daily_trade_row(t: dict, currency: str, observed_at: str) -> dict:
    p = parse_instrument(t.get("instrument_name", "")) or {}
    v = {**{k: t.get(k) for k in DAILY_TRADE_FIELDS}, "currency": currency, "expiry": p.get("expiry"), "expiry_code": p.get("expiry_code"),
         "strike": p.get("strike"), "type": p.get("type")}
    return {"source": "deribit-history", "kind": "option-trade", "key": f"{currency}:{t.get('trade_id')}", "observed_at": observed_at,
            "available_at": _cap(_iso_ms(int(t["timestamp"])), observed_at), "value": v}


def _sample_row(day: str, currency: str, start_ms: int, end_ms: int, hours: tuple, dte_days: Optional[tuple], info: dict, kept: int,
                observed_at: str) -> dict:
    v = {"day": day, "currency": currency, "window_start": _iso_ms(start_ms), "window_end": _iso_ms(end_ms), "hours": list(hours),
         "dte_days": list(dte_days) if dte_days else None, "trades_seen": info.get("seen"), "trades_kept": kept, "pages": info.get("pages"),
         "complete": bool(info.get("complete"))}
    return {"source": "mandel-deribit-sample", "kind": "sample-day", "key": f"{currency}:{day}", "observed_at": observed_at,
            "available_at": _cap(_iso_ms(end_ms), observed_at), "value": v}


def _daily_plan(days: list[str], stored_rows: int, chunk_days: int, min_interval: float, hours: tuple) -> dict:
    span = (hours[1] - hours[0]) / 2.0
    lo, hi = min(DAILY_WINDOW_TRADES), max(DAILY_WINDOW_TRADES)
    calls = trades = 0
    by_year: dict[str, dict] = {}
    for d in days:
        n = int(DAILY_WINDOW_TRADES[min(max(int(d[:4]), lo), hi)] * span)
        k = max(1, math.ceil(n / 1000))
        calls += k
        trades += n
        y = by_year.setdefault(d[:4], {"days": 0, "est_calls": 0, "est_trades": 0})
        y["days"] += 1
        y["est_calls"] += k
        y["est_trades"] += n
    rows = int(trades * DAILY_KEEP_SHARE) + len(days)
    merges = max(1, math.ceil(len(days) / max(chunk_days, 1))) if days else 0
    merge_rows = merges * stored_rows + rows * (merges + 1) / 2                     # each merge re-writes the bundle so far
    fetch_min = calls * max(min_interval, PAGE_SECONDS) / 60
    merge_min = merge_rows * MERGE_SECONDS_PER_ROW / 60
    return {"days": len(days), "first": days[0] if days else None, "last": days[-1] if days else None, "est_calls": calls,
            "est_trades_seen": trades, "est_rows": rows, "est_gz_mb": round((rows + stored_rows) * ROW_GZ_BYTES / 1e6, 1),
            "merges": merges, "est_fetch_minutes": round(fetch_min), "est_merge_minutes": round(merge_min),
            "est_minutes": round(fetch_min + merge_min), "by_year": by_year}


def fetch_deribit_daily_trades(store=None, currency: str = "BTC", first: str = DAILY_FIRST, last: str = DAILY_LAST,
                               hours: tuple = DAILY_HOURS, dte_days: Optional[tuple] = DAILY_DTE_DAYS, days: Optional[list[str]] = None,
                               limit: Optional[int] = None, dry_run: bool = False, max_pages: Optional[int] = None,
                               client: Optional[httpx.Client] = None, min_interval: float = 0.25, retries: int = 4, backoff: float = 1.0,
                               report: Optional[dict] = None, skip_stored: bool = False, chunk_days: int = DAILY_CHUNK_DAYS,
                               keep_rows: Optional[bool] = None, now_ms: Optional[int] = None, tmp_dir: Optional[str] = None,
                               log: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Bundle ``deribit-option-trades-daily-<currency>`` (local disk only): each UTC day's [hours) window of option
    trades in expiries ``dte_days`` calendar days out. ``days`` replaces the [first, last] calendar; ``limit`` caps the
    number of days; ``max_pages`` caps pages per day (a preview: never stored).

    With ``store``, complete days are spilled to a temporary file and merged into the stored bundle every ``chunk_days``
    days and at the end (also on an interrupt), and the rows are not kept in memory: the return value is then empty
    unless ``keep_rows``. Without ``store`` the rows are returned. ``skip_stored`` skips days stored complete."""
    rep = report if report is not None else {}
    archive = _archive(store)
    name = daily_bundle(currency)
    keep_rows = (archive is None) if keep_rows is None else keep_rows
    cal = sorted(set(days)) if days is not None else sample_days(first, last, hours, now_ms)
    stored: dict[str, bool] = {}
    stored_rows = 0
    if archive is not None:
        stored = _scan(archive, name, ("sample-day",), _daily_group)["sample-day"]
        try:
            stored_rows = int(archive.get(name).rows)
        except (KeyError, AttributeError):
            stored_rows = 0
    if skip_stored:
        have = {d for d, ok in stored.items() if ok}
        rep["_already_stored"] = len([d for d in cal if d in have])
        cal = [d for d in cal if d not in have]
    if limit is not None:
        cal = cal[:limit]
    if dry_run:
        rep["_plan"] = {**_daily_plan(cal, stored_rows, chunk_days, min_interval, hours), "min_interval": min_interval,
                        "chunk_days": chunk_days, "hours": list(hours), "dte_days": list(dte_days) if dte_days else None}
        return []
    own = client is None
    c = client or _client()
    th = Throttle(min_interval)
    out: list[dict] = []
    state = {"spill": _Spill(tmp_dir) if archive is not None else None, "days": set()}
    stored_days = {d for d, ok in stored.items() if ok}
    tot = {"days": 0, "complete": 0, "pages": 0, "seen": 0, "kept": 0}
    rep["_incomplete"] = {}

    def flush() -> None:
        sp, dd = state["spill"], state["days"]
        if sp is None or not dd:
            return
        allday = sorted(stored_days | dd)
        e = _merge_store(archive, name, sp.rows(), set(dd), _daily_group, _daily_sort, tags=["options", "crypto", "deribit", "trades", "daily",
                         "smile", "T-257", "T-262"], schema=DAILY_SCHEMA, tmp_dir=tmp_dir,
                         recipe=(f"GET {DERIBIT_HISTORY}get_last_trades_by_currency_and_time?currency={currency}&kind=option&start_timestamp=<day "
                                 f"{hours[0]:02d}:00 UTC ms>&end_timestamp=<day {hours[1]:02d}:00 UTC ms - 1>&count=1000&include_old=true&sorting=asc, "
                                 f"paged forward (mandel.data.options_misc.trades_in_window), for every UTC day (the window batch6b_drb.daily_smiles "
                                 f"samples), keeping the expiries {dte_days[0] if dte_days else 0}-{dte_days[1] if dte_days else 'any'} calendar days "
                                 f"after the day; raw-trade fields {', '.join(DAILY_TRADE_FIELDS)}; via mandel.data.deribit_history."
                                 f"fetch_deribit_daily_trades, stored in chunks of {chunk_days} complete days (resume with skip_stored=True); "
                                 f"{min_interval}s pacing, {retries} tries with exponential backoff on 429/5xx. available_at = trade time. Days "
                                 f"stored: {allday[0]}..{allday[-1]} ({len(allday)} days; a day is stored only when its paging completed). "
                                 f"{LICENCE_NOTE}"))
        stored_days.update(dd)
        rep["stored"] = {"rows": e.rows, "bytes": e.bytes, "in_git": e.in_git, "days": len(stored_days)}
        if log:
            log(f"daily {name}: stored {len(dd)} days, bundle {e.rows} rows, {e.bytes / 1e6:.1f} MB, {len(stored_days)} days")
        sp.close()
        state["spill"], state["days"] = _Spill(tmp_dir), set()

    try:
        for day in cal:
            s, e = daily_window(day, hours)
            kept, info = trades_in_window(currency, s, e, c, th, keep=_dte_keep(day, dte_days), max_pages=max_pages,
                                          retries=retries, backoff=backoff)
            observed = now_iso()
            drows = sorted([_daily_trade_row(t, currency, observed) for t in kept]
                           + [_sample_row(day, currency, s, e, hours, dte_days, info, len(kept), observed)], key=_daily_sort)
            tot["days"] += 1
            tot["pages"] += info.get("pages", 0)
            tot["seen"] += info.get("seen", 0)
            tot["kept"] += len(kept)
            if keep_rows:
                out.extend(drows)
            if info["complete"]:
                tot["complete"] += 1
                if state["spill"] is not None:
                    state["spill"].write(drows)
                    state["days"].add(day)
            else:
                rep["_incomplete"][day] = {k: info.get(k) for k in ("pages", "seen", "stopped", "error") if info.get(k) is not None}
                if _abort_info(info):
                    rep["_aborted"] = {"day": day, **_abort_info(info)}
                    break
            if log and tot["days"] % 30 == 0:
                log(f"daily {day}: {tot['days']}/{len(cal)} days, {tot['pages']} pages, {tot['kept']} trades kept")
            if len(state["days"]) >= chunk_days:
                flush()
    finally:                                                # also on an interrupt: complete days are stored
        if own:
            c.close()
        rep["_totals"] = tot
        try:
            flush()
        finally:
            if state["spill"] is not None:
                state["spill"].close()
    return out


# ============================================================================================ command line ==

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m mandel.data.deribit_history",
                                description="Fetch the Deribit history bundles of T-263 (fomc), T-268 (dvol) and T-257/T-262 (daily).")
    p.add_argument("bundle", choices=["fomc", "dvol", "daily"])
    p.add_argument("--dry-run", action="store_true", help="no request: print the plan (calls, rows, gzip MB, minutes)")
    p.add_argument("--preview", metavar="DIR", help="do not store: write the rows to DIR/<bundle>.preview.jsonl.gz and the report to DIR")
    p.add_argument("--skip-stored", action="store_true", help="skip windows already stored complete (resume)")
    p.add_argument("--limit", type=int, help="first N windows / instruments / days only")
    p.add_argument("--max-pages", type=int, help="pages per window (preview; such windows are never stored)")
    p.add_argument("--first", help="first decision day / sample day (YYYY-MM-DD)")
    p.add_argument("--last", help="last decision day / sample day (YYYY-MM-DD)")
    p.add_argument("--days", help="comma-separated sample days (daily) instead of first..last")
    p.add_argument("--currency", default="BTC")
    p.add_argument("--chunk-days", type=int, default=DAILY_CHUNK_DAYS)
    p.add_argument("--min-interval", type=float, default=0.25)
    a = p.parse_args(argv)
    if a.preview:
        store = None
    else:
        from mandel.archive import Archive
        store = Archive()
    rep: dict = {}
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    kw = {"limit": a.limit, "dry_run": a.dry_run, "max_pages": a.max_pages, "min_interval": a.min_interval, "report": rep,
          "skip_stored": a.skip_stored, "log": log}
    if a.bundle == "fomc":
        name = FOMC_BUNDLE
        rows = fetch_deribit_fomc_trades(store, currency=a.currency, first=a.first or FOMC_FIRST, last=a.last or FOMC_LAST, **kw)
    elif a.bundle == "dvol":
        name = DVOLF_BUNDLE
        rows = fetch_deribit_dvol_futures(store, **kw)
    else:
        name = daily_bundle(a.currency)
        rows = fetch_deribit_daily_trades(store, currency=a.currency, first=a.first or DAILY_FIRST, last=a.last or DAILY_LAST,
                                          days=a.days.split(",") if a.days else None, chunk_days=a.chunk_days, **kw)
    if a.preview and not a.dry_run:
        os.makedirs(a.preview, exist_ok=True)
        with gzip.open(os.path.join(a.preview, f"{name}.preview.jsonl.gz"), "wt", encoding="utf-8") as f:
            for r in rows:
                f.write(_line(r) + "\n")
        with open(os.path.join(a.preview, f"{name}.report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, default=str)
    summary = {k: v for k, v in rep.items() if k.startswith("_") or k == "stored"}
    print(json.dumps({"bundle": name, "rows_returned": len(rows), **summary}, indent=1, default=str)[:20000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
