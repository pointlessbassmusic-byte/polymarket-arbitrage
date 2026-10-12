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

CAL_URL = "https://api.nasdaq.com/api/calendar/earnings"
HIST_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}


def _money(s) -> Optional[float]:
    """'$1.72' -> 1.72, '($0.13)' -> -0.13, '' -> None."""
    if s in (None, "", "N/A"):
        return None
    t = str(s).replace("$", "").replace(",", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _num(s) -> Optional[float]:
    if s in (None, "", "N/A"):
        return None
    try:
        return float(str(s).replace(",", "").replace("%", ""))
    except ValueError:
        return None


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


def parse_history(payload: dict) -> list[dict]:
    out = []
    for r in ((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or []:
        try:
            day = dt.datetime.strptime(r["date"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        o, c = _money(r.get("open")), _money(r.get("close"))
        if o and c and o > 0 and c > 0:
            out.append({"date": day.isoformat(), "open": o, "close": c,
                        "high": _money(r.get("high")), "low": _money(r.get("low")),
                        "volume": _num(r.get("volume"))})
    out.sort(key=lambda x: x["date"])
    return out


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


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

    async def _get(self, url: str, params: Optional[dict] = None, tries: int = 4) -> dict:
        last: Exception | None = None
        for i in range(tries):
            try:
                r = await self._c.get(url, params=params)
                if r.status_code == 200:
                    return r.json()
                last = RuntimeError(f"{url.split('?')[0]} -> {r.status_code}")
            except Exception as exc:              # noqa: BLE001
                last = exc
            await asyncio.sleep(self.pause * (2 ** i))
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

    def symbols_needed(self, min_estimates: int = 3, max_cap: Optional[float] = None) -> list[str]:
        syms = set()
        for r in read_jsonl(self.calendar_file):
            if r.get("n_est", 0) >= min_estimates and r.get("surprise_pct") is not None:
                if max_cap is None or (r.get("market_cap") or 0) <= max_cap:
                    syms.add(r["symbol"])
        return sorted(syms)

    async def prices(self, symbols: list[str], years: int = 11, log_every: int = 100) -> int:
        d = self.state / "prices"
        d.mkdir(parents=True, exist_ok=True)
        got = 0
        end = dt.date.today()
        start = end.replace(year=end.year - years)
        for i, sym in enumerate(symbols, 1):
            p = d / f"{sym}.json"
            if p.exists():
                continue
            try:
                payload = await self._get(HIST_URL.format(symbol=sym),
                                          {"assetclass": "stocks", "fromdate": start.isoformat(),
                                           "todate": end.isoformat(), "limit": 9999})
                rows = parse_history(payload)
            except Exception as exc:              # noqa: BLE001
                logger.warning("prices %s: %s", sym, exc)
                rows = []
            p.write_text(json.dumps(rows))
            got += 1
            if i % log_every == 0:
                logger.info("prices: %d of %d symbols", i, len(symbols))
            await asyncio.sleep(self.pause)
        return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("calendar", "prices"))
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--min-estimates", type=int, default=3)
    ap.add_argument("--max-cap", type=float, default=None, help="only symbols at or under this market cap (USD)")
    ap.add_argument("--pause", type=float, default=0.3)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    async def go():
        c = PeadCollector(a.state, pause_s=a.pause)
        try:
            if a.what == "calendar":
                n = await c.calendar(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
                print(f"calendar: {n} rows added; {len(read_jsonl(c.calendar_file))} on file")
            else:
                syms = c.symbols_needed(a.min_estimates, a.max_cap)
                n = await c.prices(syms)
                print(f"prices: {n} symbols fetched of {len(syms)} needed")
        finally:
            await c.close()
    asyncio.run(go())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
