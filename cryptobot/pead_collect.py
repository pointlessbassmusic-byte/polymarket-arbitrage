"""Collectors for the post-earnings-announcement-drift test (`pead-revisit`).

Nasdaq's data API serves, for any past date, the day's earnings
calendar with the reported EPS, the consensus forecast, the percentage
surprise, the number of estimates and a market cap, and for any symbol
ten years of daily OHLC. Both are free and need no key, so the panel the
test needs can be assembled here, resumably:

    python -m cryptobot.pead_collect calendar --state state --start 2015-01-01   # one request a day
    python -m cryptobot.pead_collect prices --state state                         # one request a symbol

Rows go to state/earnings/calendar.jsonl and state/earnings/prices/<SYM>.json.
Known limits, recorded so the study states them: the calendar does not
say whether a past report was before or after the open ("time-not-
supplied"), so entries are taken at the open of the NEXT session, which
gives up day one for pre-market reporters; the market cap field is the
company's current one, not the cap on the report date, so it is a slow
size filter, not a point-in-time one.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

from .data.nasdaq import CAL_URL, HEADERS as UA, HIST_URL, append_jsonl, money as _money, parse_history, payload_ok, read_jsonl  # noqa: E402,F401

_num = _money


def parse_calendar(payload: dict, day: dt.date) -> list[dict]:
    rows = []
    for r in ((payload.get("data") or {}).get("rows") or []):
        sym = (r.get("symbol") or "").strip().upper()
        if not sym or not re.fullmatch(r"[A-Z.\-]{1,6}", sym):
            continue
        rows.append({"date": day.isoformat(), "symbol": sym, "name": r.get("name"),
                     "eps": _money(r.get("eps")), "forecast": _money(r.get("epsForecast")),
                     "surprise_pct": _num(r.get("surprise")), "n_est": int(_num(r.get("noOfEsts")) or 0),
                     "market_cap": _money(r.get("marketCap")), "time": r.get("time"),
                     "fiscal_quarter": r.get("fiscalQuarterEnding")})
    return rows




class UnknownSymbol(RuntimeError):
    """Nasdaq's definitive 'no such symbol' (data=null with rCode 400):
    a delisted name, not a throttle, so there is nothing to retry."""


class PeadCollector:
    def __init__(self, state_dir: Path, client: Optional[httpx.AsyncClient] = None, pause_s: float = 0.3):
        self.state = Path(state_dir) / "earnings"
        self.pause = pause_s
        self._c = client or httpx.AsyncClient(timeout=60, headers=UA)
        self._owns = client is None

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    @property
    def calendar_file(self) -> Path:
        return self.state / "calendar.jsonl"

    def days_done(self) -> set[str]:
        p = self.state / "calendar_days.txt"
        return set(p.read_text().split()) if p.exists() else set()

    def _mark_day(self, day: dt.date) -> None:
        p = self.state / "calendar_days.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(day.isoformat() + "\n")

    async def _get(self, url: str, params: Optional[dict] = None, tries: int = 5) -> dict:
        """A payload with data=null (Nasdaq's throttle and unknown-symbol
        answer) counts as a failure and is retried with backoff."""
        last: Exception | None = None
        for i in range(tries):
            try:
                r = await self._c.get(url, params=params)
                if r.status_code == 200:
                    payload = r.json()
                    if payload_ok(payload):
                        return payload
                    code = ((payload.get("status") or {}).get("rCode") if isinstance(payload, dict) else None)
                    if code == 400:
                        raise UnknownSymbol(f"{url.split('?')[0]} -> data=null (rCode 400)")
                    last = RuntimeError(f"{url.split('?')[0]} -> data=null (rCode {code})")
                else:
                    last = RuntimeError(f"{url.split('?')[0]} -> {r.status_code}")
            except UnknownSymbol:
                raise                             # definitive: no retry
            except Exception as exc:              # noqa: BLE001
                last = exc
            await asyncio.sleep(max(self.pause, 0.5) * (2 ** i))
        raise RuntimeError(f"gave up: {last}")

    async def calendar(self, start: dt.date, end: dt.date, log_every: int = 50) -> int:
        """Fetch every weekday's calendar in [start, end] not yet stored. Returns rows added."""
        done = self.days_done()
        added = 0
        day = start
        n = 0
        while day <= end:
            if day.weekday() < 5 and day.isoformat() not in done:
                payload = await self._get(CAL_URL, {"date": day.isoformat()})
                rows = parse_calendar(payload, day)
                if rows:
                    self.calendar_file.parent.mkdir(parents=True, exist_ok=True)
                    with self.calendar_file.open("a") as f:
                        for r in rows:
                            f.write(json.dumps(r) + "\n")
                self._mark_day(day)
                added += len(rows)
                n += 1
                if n % log_every == 0:
                    logger.info("calendar: %s, %d rows so far", day, added)
                await asyncio.sleep(self.pause)
            day += dt.timedelta(days=1)
        return added

    def empty_days(self) -> list[str]:
        """Weekdays marked done with no rows: holidays, or days a throttled
        answer was once mistaken for an empty calendar. `--refetch-empty`
        fetches them again; a real holiday just comes back empty."""
        have = {r["date"] for r in read_jsonl(self.calendar_file)}
        return sorted(d for d in self.days_done() if d not in have)

    def unmark_days(self, days: list[str]) -> None:
        keep = [d for d in sorted(self.days_done()) if d not in set(days)]
        (self.state / "calendar_days.txt").write_text("".join(d + "\n" for d in keep))

    def symbols_needed(self, min_estimates: int = 3, max_cap: Optional[float] = None) -> list[str]:
        syms = set()
        for r in read_jsonl(self.calendar_file):
            if r.get("n_est", 0) >= min_estimates and r.get("surprise_pct") is not None:
                if max_cap is None or (r.get("market_cap") or 0) <= max_cap:
                    syms.add(r["symbol"])
        return sorted(syms)

    async def prices(self, symbols: list[str], years: int = 11, log_every: int = 100, workers: int = 1) -> int:
        """Fetch ten years of daily OHLC per symbol not yet on file, `workers`
        requests in flight at once. A failed fetch writes nothing, so the
        next run retries it; [] is written only when Nasdaq has no rows."""
        d = self.state / "prices"
        d.mkdir(parents=True, exist_ok=True)
        end = dt.date.today()
        start = end.replace(year=end.year - years)
        todo = [sym for sym in symbols if not (d / f"{sym}.json").exists()]
        sem = asyncio.Semaphore(max(1, workers))
        done = {"n": 0, "got": 0}

        async def one(sym: str) -> None:
            async with sem:
                try:
                    payload = await self._get(HIST_URL.format(symbol=sym),
                                              {"assetclass": "stocks", "fromdate": start.isoformat(),
                                               "todate": end.isoformat(), "limit": 9999})
                except UnknownSymbol:
                    (d / f"{sym}.json").write_text("[]")      # delisted: no history exists; counted as missing
                    done["got"] += 1
                except Exception as exc:          # noqa: BLE001
                    logger.warning("prices %s: %s (will retry on the next run)", sym, exc)
                else:
                    (d / f"{sym}.json").write_text(json.dumps(parse_history(payload)))
                    done["got"] += 1
                done["n"] += 1
                if done["n"] % log_every == 0:
                    logger.info("prices: %d of %d symbols", done["n"], len(todo))
                await asyncio.sleep(self.pause)

        await asyncio.gather(*(one(sym) for sym in todo))
        return done["got"]


def merge_state(into: Path, other: Path) -> dict:
    """Fold another state directory's earnings panel into `into` (parallel
    collection streams): calendar rows deduplicated on (date, symbol),
    done-days unioned, price files copied where missing."""
    a, b = Path(into) / "earnings", Path(other) / "earnings"
    a.mkdir(parents=True, exist_ok=True)
    have = {(r["date"], r["symbol"]) for r in read_jsonl(a / "calendar.jsonl")}
    added = 0
    for r in read_jsonl(b / "calendar.jsonl"):
        if (r["date"], r["symbol"]) not in have:
            append_jsonl(a / "calendar.jsonl", r)
            have.add((r["date"], r["symbol"]))
            added += 1
    days_a = set((a / "calendar_days.txt").read_text().split()) if (a / "calendar_days.txt").exists() else set()
    days_b = set((b / "calendar_days.txt").read_text().split()) if (b / "calendar_days.txt").exists() else set()
    (a / "calendar_days.txt").write_text("".join(d + "\n" for d in sorted(days_a | days_b)))
    copied = 0
    if (b / "prices").exists():
        (a / "prices").mkdir(exist_ok=True)
        for f in (b / "prices").glob("*.json"):
            dst = a / "prices" / f.name
            if not dst.exists():
                dst.write_bytes(f.read_bytes())
                copied += 1
    return {"calendar_rows_added": added, "days": len(days_a | days_b), "prices_copied": copied}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("calendar", "prices", "merge"))
    ap.add_argument("--from-state", type=Path, help="merge: the other state directory to fold in")
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--min-estimates", type=int, default=3)
    ap.add_argument("--max-cap", type=float, default=None, help="only symbols at or under this market cap (USD)")
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--refetch-empty", action="store_true", help="calendar: fetch again the days that came back empty")
    ap.add_argument("--workers", type=int, default=1, help="prices: requests in flight at once")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if a.what == "merge":
        if not a.from_state:
            ap.error("merge needs --from-state")
        print(merge_state(a.state, a.from_state))
        return 0

    async def go():
        c = PeadCollector(a.state, pause_s=a.pause)
        try:
            if a.what == "calendar":
                if a.refetch_empty:
                    empty = c.empty_days()
                    c.unmark_days(empty)
                    print(f"refetching {len(empty)} empty days")
                n = await c.calendar(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
                print(f"calendar: {n} rows added; {len(read_jsonl(c.calendar_file))} on file")
            else:
                syms = c.symbols_needed(a.min_estimates, a.max_cap)
                n = await c.prices(syms, workers=a.workers)
                print(f"prices: {n} symbols fetched of {len(syms)} needed")
        finally:
            await c.close()
    asyncio.run(go())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
