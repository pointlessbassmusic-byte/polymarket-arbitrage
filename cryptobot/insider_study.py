"""Insider purchases (SEC Form 4, code P), as pre-registered in
`insider-purchases` (cryptobot/hypotheses.yaml, 2026-10-14).

Every open-market purchase of at least $25,000 by an officer or director
becomes one event per (ticker, filing date). The event is bought at the
open of the first session after the FILING date, the day the purchase
became public, and held `hold` sessions at 10 bp a side.

The bar is the same name's placebo window: the same rule entered
`hold + 40` sessions after the filing. It shares the panel's
survivorship (Nasdaq serves current listings only), so the difference
cancels it. That is the lesson of `pead-revisit`, whose late placebo beat
its real entry. Also reported:

* event minus SPY, which carries the bias;
* the pre-filing window, entered `hold + 5` sessions BEFORE the filing:
  were these names already running?

Four trials were counted before running: {every purchase, cluster
purchases (>= 2 distinct insiders in the 30 days to the filing)} x
{hold 20, hold 60}.

Data: OpenInsider's screener, a public mirror of the SEC's Form 4
filings. The SEC's own data sets refuse this environment without a
declared contact; on the server set SEC_USER_AGENT and use those instead
if preferred. Prices come from the desk's Nasdaq feed.

    python -m cryptobot.insider_study collect --state state --start 2016-01 --end 2026-09
    python -m cryptobot.insider_study prices --state state
    python -m cryptobot.insider_study report --state state
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import logging
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

from . import stats as S
from .data.nasdaq import HEADERS, HIST_URL, money, parse_history
from .pead_study import price_before, window_return

logger = logging.getLogger(__name__)

SCREENER = "http://openinsider.com/screener"
COST_SIDE = 0.001
MIN_VALUE_K = 25
MIN_PRICE = 2.0
CLUSTER_DAYS = 30
TRIALS = (("every", 20), ("cluster", 20), ("every", 60), ("cluster", 60))


def screener_params(month: dt.date, page: int) -> dict:
    """Officer or director open-market purchases >= $25k filed in `month`."""
    last = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    p = {"s": "", "fd": "-1", "fdr": f"{month:%m/%d/%Y} - {last:%m/%d/%Y}", "td": "0", "xp": "1",
         "vl": str(MIN_VALUE_K), "sic1": "-1", "sicl": "100", "sich": "9999", "grp": "0",
         "sortcol": "0", "cnt": "1000", "page": str(page)}
    for flag in ("isofficer", "iscob", "isceo", "ispres", "iscoo", "iscfo", "isgc", "isvp", "isdirector"):
        p[flag] = "1"
    return p


def parse_screener(page: str) -> list[dict]:
    """Rows of the screener's result table; tolerant of its tooltip markup."""
    i = page.find('class="tinytable"')
    if i < 0:
        return []
    table = page[i:page.find("</table>", i)]
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 13:
            continue
        text = [_html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        link = re.findall(r'<a href="/([A-Za-z.\-]+)"', cells[3])
        ticker = (link[0] if link else text[3].split(">")[-1]).strip().upper()
        if not ticker or not text[7].startswith("P"):
            continue
        out.append({"flags": text[0], "filed": text[1][:10], "traded": text[2][:10], "ticker": ticker,
                    "insider": text[5], "title": text[6], "price": money(text[8]),
                    "qty": money(text[9]), "value": money(text[12])})
    return out


def _months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield dt.date(y, m, 1)
        m += 1
        if m > 12:
            y, m = y + 1, 1


def collect(state: Path, start: str, end: str, client=None, pause: float = 1.0, sleep=time.sleep) -> int:
    """One JSONL per month under state/insider/filings/; months on file are skipped."""
    import httpx
    c = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": HEADERS["User-Agent"]})
    d = state / "insider" / "filings"
    d.mkdir(parents=True, exist_ok=True)
    total = 0
    for month in _months(start, end):
        path = d / f"{month:%Y-%m}.jsonl"
        if path.exists():
            continue
        rows, page = [], 1
        while True:
            r = c.get(SCREENER, params=screener_params(month, page))
            r.raise_for_status()
            got = parse_screener(r.text)
            rows.extend(got)
            sleep(pause)
            if len(got) < 1000:
                break
            page += 1
        path.write_text("".join(json.dumps(x) + "\n" for x in rows))
        total += len(rows)
        logger.info("%s: %d purchases", f"{month:%Y-%m}", len(rows))
    return total


def load_filings(state: Path) -> list[dict]:
    rows = []
    for p in sorted((state / "insider" / "filings").glob("*.jsonl")):
        rows.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
    return rows


def fetch_prices(state: Path, symbols, client=None, years: int = 11, pause: float = 0.4,
                 sleep=time.sleep) -> int:
    """Nasdaq daily OHLC per symbol into state/insider/prices/ (on file: skipped)."""
    import httpx
    c = client or httpx.Client(timeout=60, headers=HEADERS)
    d = state / "insider" / "prices"
    d.mkdir(parents=True, exist_ok=True)
    end = dt.date.today()
    start = end.replace(year=end.year - years)
    got = 0
    todo = sorted(s for s in set(symbols) if not (d / f"{s}.json").exists())
    for i, sym in enumerate(todo):
        params = {"assetclass": "etf" if sym == "SPY" else "stocks", "fromdate": start.isoformat(),
                  "todate": end.isoformat(), "limit": 9999}
        try:
            r = c.get(HIST_URL.format(symbol=sym), params=params)
            rows = parse_history(r.json()) if r.status_code == 200 else []
        except Exception as exc:  # noqa: BLE001 — a failed symbol is retried next run
            logger.warning("prices %s: %s", sym, exc)
            sleep(pause)
            continue
        (d / f"{sym}.json").write_text(json.dumps(rows))
        got += 1
        if i % 200 == 0:
            logger.info("prices: %d of %d", i, len(todo))
        sleep(pause)
    return got


def events(filings: list[dict]) -> list[dict]:
    """One event per (ticker, filing date), with the cluster flag: >= 2
    distinct insiders buying the ticker in the 30 days up to the filing."""
    by_key: dict[tuple, dict] = {}
    for f in filings:
        if not f.get("filed") or not f.get("ticker"):
            continue
        k = (f["ticker"], f["filed"])
        e = by_key.setdefault(k, {"ticker": f["ticker"], "filed": f["filed"], "value": 0.0, "insiders": set()})
        e["value"] += f.get("value") or 0.0
        e["insiders"].add(f.get("insider") or "")
    by_ticker: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for f in filings:
        if f.get("filed") and f.get("ticker"):
            by_ticker[f["ticker"]].append((f["filed"], f.get("insider") or ""))
    out = []
    for e in by_key.values():
        day = dt.date.fromisoformat(e["filed"])
        lo = (day - dt.timedelta(days=CLUSTER_DAYS)).isoformat()
        names = {who for filed, who in by_ticker[e["ticker"]] if lo <= filed <= e["filed"]}
        out.append({**e, "insiders": len(e["insiders"]), "cluster": len(names) >= 2})
    out.sort(key=lambda e: (e["filed"], e["ticker"]))
    return out


def _net(px, date, hold, offset):
    w = window_return(px, date, hold, COST_SIDE, entry_offset=offset)
    return w["net_long"] if w else None


def evaluate(evs: list[dict], prices: dict[str, list[dict]], kind: str, hold: int) -> dict:
    spy = prices.get("SPY") or []
    placebo_off, pre_off = hold + 40, -(hold + 5)
    monthly: dict[str, list[float]] = defaultdict(list)
    rows = []
    for e in evs:
        if kind == "cluster" and not e["cluster"]:
            continue
        px = prices.get(e["ticker"])
        if not px:
            continue
        p0 = price_before(px, e["filed"])
        if p0 is None or p0 < MIN_PRICE:
            continue
        ev = _net(px, e["filed"], hold, 0)
        pl = _net(px, e["filed"], hold, placebo_off)
        if ev is None or pl is None:
            continue
        pre = _net(px, e["filed"], hold, pre_off)
        w = window_return(px, e["filed"], hold, COST_SIDE)
        sp = None
        if spy and w:
            i0 = next((k for k, r in enumerate(spy) if r["date"] >= w["entry_date"]), None)
            i1 = next((k for k, r in enumerate(spy) if r["date"] >= w["exit_date"]), None)
            if i0 is not None and i1 is not None:
                sp = spy[i1]["close"] / spy[i0]["open"] - 1.0
        rows.append({"filed": e["filed"], "event": ev, "placebo": pl, "pre": pre, "spy": sp})
        monthly[e["filed"][:7]].append(ev - pl)
    months = sorted(monthly)
    series = [statistics.mean(monthly[m]) for m in months]
    by_year: dict[str, list[float]] = defaultdict(list)
    for m, v in zip(months, series):
        by_year[m[:4]].append(v)
    out = {"kind": kind, "hold": hold, "events": len(rows), "months": len(series)}
    if len(series) >= 3:
        out.update(mean=statistics.mean(series), sharpe=S.sharpe(series), psr=S.psr(series),
                   years={y: statistics.mean(v) for y, v in sorted(by_year.items())},
                   recent=statistics.mean([v for m, v in zip(months, series) if m >= "2023-01"] or [float("nan")]))
        out["event_mean"] = statistics.mean(r["event"] for r in rows)
        out["placebo_mean"] = statistics.mean(r["placebo"] for r in rows)
        pres = [r["pre"] for r in rows if r["pre"] is not None]
        out["pre_mean"] = statistics.mean(pres) if pres else None
        ex = [r["event"] - r["spy"] for r in rows if r["spy"] is not None]
        out["event_minus_spy"] = statistics.mean(ex) if ex else None
    return out


def verdict(r: dict) -> str:
    """The pre-registered bar, for the primary rule (every purchase, hold 20)."""
    if r.get("mean") is None:
        return "no data"
    full = {y: v for y, v in r["years"].items() if "2017" <= y <= "2026"}
    pos = sum(1 for v in full.values() if v > 0)
    if r["mean"] <= 0:
        return "killed"
    if r["mean"] >= 0.01 and r["psr"] >= 0.95 and pos >= 7 and r["recent"] > 0:
        return "alive"
    return "inconclusive"


def report(state: Path) -> str:
    filings = load_filings(state)
    evs = events(filings)
    d = state / "insider" / "prices"
    prices = {}
    for p in d.glob("*.json"):
        try:
            rows = json.loads(p.read_text())
        except ValueError:
            continue
        if rows:
            prices[p.stem] = rows
    lines = [f"{len(filings)} purchase rows, {len(evs)} (ticker, filing date) events, "
             f"{sum(e['cluster'] for e in evs)} clusters; prices for {len(prices)} symbols"]
    for kind, hold in TRIALS:
        r = evaluate(evs, prices, kind, hold)
        if r.get("mean") is None:
            lines.append(f"{kind:7s} hold {hold:2d}: {r['events']} events, too few months")
            continue
        yrs = " ".join(f"{y[2:]}:{v * 100:+.1f}" for y, v in r["years"].items())
        lines.append(
            f"{kind:7s} hold {hold:2d}: {r['events']:6d} events {r['months']:3d} months | event-placebo "
            f"{r['mean'] * 100:+.2f}%/trade-month (Sharpe {r['sharpe']:.2f}, PSR {r['psr']:.2f}, 2023+ "
            f"{r['recent'] * 100:+.2f}%) | event {r['event_mean'] * 100:+.2f}% placebo {r['placebo_mean'] * 100:+.2f}% "
            f"pre-filing {(r['pre_mean'] or 0) * 100:+.2f}% event-SPY {(r['event_minus_spy'] or 0) * 100:+.2f}%"
            + (f" | VERDICT {verdict(r)}" if (kind, hold) == ("every", 20) else "")
            + f"\n          by year: {yrs}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("collect", "prices", "report"))
    ap.add_argument("--state", default="state")
    ap.add_argument("--start", default="2016-01")
    ap.add_argument("--end", default="2026-09")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state = Path(args.state)
    if args.cmd == "collect":
        print(collect(state, args.start, args.end))
    elif args.cmd == "prices":
        syms = {f["ticker"] for f in load_filings(state)} | {"SPY"}
        print(fetch_prices(state, syms))
    else:
        print(report(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
