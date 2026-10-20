"""`kalshi-btc-carry-etf-hedge`, the forward read: short KXBTCPERP against
a dollar-matched long IBIT while BTC funding runs positive.

Everything it needs is fetched at read time, so nothing has to be
collected in between: Kalshi's funding history (prints every 8 hours),
the perp's hourly candles (the close at 16:00 ET, matched to IBIT's
close) and IBIT's daily closes (Nasdaq data API).

Rule, fixed in the registry before any forward data: in position on a
day when the trailing 14 days of funding annualise above +4%; flat
otherwise. Per day in position, on the capital in both legs (one unit
short perp + one unit long IBIT, so returns are divided by 2):
funding collected - perp return + IBIT return - IBIT's 0.25%/yr fee;
each entry or exit costs 2 x 4 bp (perp) + 2 x 1 bp (IBIT spread).

The registered read is at 120 days from 2026-10-15 (2027-02-12);
--force reads earlier for a status check, labelled as such.

    python -m cryptobot.carry_forward
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
import time
from collections import defaultdict
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from .data.nasdaq import HEADERS as NASDAQ_UA, HIST_URL, parse_closes

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
START = dt.date(2026, 10, 15)
READ_AT = START + dt.timedelta(days=120)
THRESH = 0.04
TRAIL = 14
SWITCH_COST = 2 * 0.0004 + 2 * 0.0001
IBIT_FEE = 0.0025


def funding(c: httpx.Client, ticker: str = "KXBTCPERP", since: dt.date = START - dt.timedelta(days=TRAIL + 2)) -> dict[dt.date, float]:
    out: dict[dt.date, float] = defaultdict(float)
    cursor = None
    for _ in range(50):
        params = {"ticker": ticker, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        j = c.get(f"{KALSHI}/margin/funding_rates/historical", params=params).json()
        rows = j.get("funding_rates") or []
        for r in rows:
            t = dt.datetime.fromisoformat(r["funding_time"].replace("Z", "+00:00"))
            if t.date() >= since:
                out[t.astimezone(ET).date()] += float(r["funding_rate"] or 0)
        cursor = j.get("cursor")
        if not rows or not cursor or min(dt.datetime.fromisoformat(r["funding_time"].replace("Z", "+00:00")).date() for r in rows) < since:
            break
        time.sleep(0.3)
    return dict(out)


def perp_closes_4pm(c: httpx.Client, ticker: str = "KXBTCPERP", since: dt.date = START - dt.timedelta(days=3)) -> dict[dt.date, float]:
    out = {}
    t0 = int(dt.datetime.combine(since, dt.time(0), dt.timezone.utc).timestamp())
    now = int(time.time())
    while t0 < now:
        t1 = min(now, t0 + 3600 * 4000)
        j = c.get(f"{KALSHI}/margin/markets/{ticker}/candlesticks", params={"start_ts": t0, "end_ts": t1, "period_interval": 60}).json()
        for k in j.get("candlesticks") or []:
            end = dt.datetime.fromtimestamp(int(k["end_period_ts"]), dt.timezone.utc).astimezone(ET)
            if end.hour == 16 and end.minute == 0:
                out[end.date()] = float(k["price"]["close"])
        t0 = t1
        time.sleep(0.3)
    return out


def ibit_closes(since: dt.date = START - dt.timedelta(days=3)) -> dict[dt.date, float]:
    r = httpx.get(HIST_URL.format(symbol="IBIT"), headers=NASDAQ_UA, timeout=30,
                  params={"assetclass": "etf", "fromdate": since.isoformat(), "todate": dt.date.today().isoformat(), "limit": 9999})
    return dict(parse_closes(r.json()))


def simulate(fund: dict[dt.date, float], perp: dict[dt.date, float], ibit: dict[dt.date, float], start: dt.date = START) -> dict:
    days = sorted(d for d in ibit if d >= start and d in perp)
    rows, pos, prev = [], False, None
    for d in days:
        if prev is None:
            prev = d
            continue
        trail = sum(v for k, v in fund.items() if d - dt.timedelta(days=TRAIL) <= k < d) * 365 / TRAIL
        want = trail > THRESH
        r = 0.0
        if pos:
            f = sum(v for k, v in fund.items() if prev < k <= d)
            pr = perp[d] / perp[prev] - 1
            ir = ibit[d] / ibit[prev] - 1
            r = (f - pr + ir - IBIT_FEE * (d - prev).days / 365) / 2
        if want != pos:
            r -= SWITCH_COST / 2
            pos = want
        rows.append({"day": d, "ret": r, "in": pos, "trail": trail,
                     "track": (ibit[d] / ibit[prev]) - (perp[d] / perp[prev])})
        prev = d
    if not rows:
        return {"days": 0}
    span = (rows[-1]["day"] - start).days or 1
    total = math.prod(1 + r["ret"] for r in rows) - 1
    return {"days": len(rows), "span_days": span, "in_days": sum(1 for r in rows if r["in"]),
            "net_total": total, "net_ann": (1 + total) ** (365 / span) - 1,
            "track_sd": statistics.pstdev(r["track"] for r in rows) if len(rows) > 2 else None,
            "funding_ann": sum(v for k, v in fund.items() if k >= start) * 365 / span}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="read before the registered date (a status check, not the verdict)")
    a = ap.parse_args(argv)
    today = dt.date.today()
    if today < READ_AT and not a.force:
        print(f"kalshi-btc-carry-etf-hedge is read on {READ_AT} (120 days from {START}); {(READ_AT - today).days} days to go. "
              "--force prints a status check that is not the verdict.")
        return 0
    c = httpx.Client(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"})
    res = simulate(funding(c), perp_closes_4pm(c), ibit_closes())
    label = "VERDICT READ" if today >= READ_AT else "status check only (before the registered read)"
    if not res.get("days"):
        print(f"{label}: no overlapping days yet")
        return 0
    print(f"{label}: {res['days']} trading days from {START}, in position {res['in_days']}; "
          f"funding {res['funding_ann']:+.1%}/yr; pair net {res['net_total']:+.2%} ({res['net_ann']:+.1%}/yr on both legs' capital); "
          f"daily tracking error sd {res['track_sd'] * 100 if res['track_sd'] is not None else 0:.2f}%. "
          "Candidate at >= +2%/yr with tracking sd < 0.5%; killed below 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
