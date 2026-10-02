"""Published crypto strategies, tested as published on Hyperliquid perps.

Every rule here comes from outside this project with its parameters
fixed in advance (a paper, a widely shared indicator, a common trading
claim). None is tuned on this data, so every year scored is out of sample
for it. That is the strongest test available here, and it is why the
parameters below are not swept.

  momentum    Liu & Tsyvinski (NBER w25882): each week, long the top
              quintile of trailing 1-week return, short the bottom.
              Later work: momentum in large/liquid coins, reversal in
              small/illiquid. Scored on both halves by 30-day dollar
              volume.
  crowding    "Persistently high funding precedes corrections": each
              week, long the bottom quintile of trailing 7-day funding,
              short the top.
  fomo        The open-source meme-coin buy signal: volume > 2x its
              10-day mean, SMA5 > SMA20, BTC above its SMA20. Long at the
              close, held 1 / 3 / 7 days, against an unconditional long
              on the same coins and days.
  listing     New Hyperliquid listings (first candle after 2023-07): the
              return from the first close to day 7 / 14 / 30.

Costs: perp taker 0.035% + 0.05% slippage per side on every leg, plus
realised funding (longs pay positive funding, shorts receive it).
Long-short books assume full weekly turnover, the conservative case.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import statistics
from pathlib import Path

from cryptobot.data.hyperliquid import TAKER_FEE

DAY = 86400
WEEK = 7 * DAY
SIDE_COST = TAKER_FEE + 0.0005
RT = 2 * SIDE_COST
LISTING_CUTOFF = int(dt.datetime(2023, 7, 1, tzinfo=dt.timezone.utc).timestamp())


# ------------------------------------------------------------------ data

class Panel:
    """Daily closes, dollar volumes and funding, keyed by (coin, day)."""

    def __init__(self, pools: dict, funding: dict | None = None):
        self.close: dict[str, dict[int, float]] = {}
        self.vol: dict[str, dict[int, float]] = {}
        self.first: dict[str, int] = {}
        for coin, (_, cs) in pools.items():
            c = {int(x.ts // DAY) * DAY: x.close for x in cs if x.close > 0}
            if not c:
                continue
            self.close[coin] = c
            self.vol[coin] = {int(x.ts // DAY) * DAY: x.volume_usd for x in cs}
            self.first[coin] = min(c)
        self.fund: dict[str, dict[int, float]] = {}
        for coin, rows in (funding or {}).items():
            d = self.fund.setdefault(coin, {})
            for r in rows:
                k = int(r.ts // DAY) * DAY
                d[k] = d.get(k, 0.0) + r.rate
        self.days = sorted({d for c in self.close.values() for d in c})

    def ret(self, coin: str, a: int, b: int) -> float | None:
        c = self.close.get(coin, {})
        return c[b] / c[a] - 1.0 if a in c and b in c else None

    def funding(self, coin: str, a: int, b: int) -> float:
        """Funding paid by a LONG holding from close a to close b."""
        f = self.fund.get(coin, {})
        return sum(f.get(d, 0.0) for d in range(a + DAY, b + DAY, DAY))

    def dollar_volume(self, coin: str, day: int, n: int = 30) -> float:
        v = self.vol.get(coin, {})
        return sum(v.get(day - k * DAY, 0.0) for k in range(n))

    def sma(self, coin: str, day: int, n: int) -> float | None:
        c = self.close.get(coin, {})
        xs = [c.get(day - k * DAY) for k in range(n)]
        return statistics.mean(xs) if all(x is not None for x in xs) else None


def _year(ts: int) -> int:
    return dt.datetime.utcfromtimestamp(ts).year


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "mean": 0.0, "t": 0.0}
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {"n": len(xs), "mean": m, "t": m / (sd / math.sqrt(len(xs))) if sd else 0.0}


# ------------------------------------------------------------- weekly L/S

def weekly_long_short(panel: Panel, score, *, start: int, quantile: float = 0.2,
                      min_history: int = 30, liquidity: str | None = None,
                      reverse: bool = False) -> list[dict]:
    """Each week: rank eligible coins by `score(coin, day)`, long the top
    quantile and short the bottom (or the reverse), hold one week.

    Returns one row per week with gross, cost, funding and net, per unit
    of capital on EACH side (a dollar long and a dollar short).
    """
    out = []
    week = start
    end = panel.days[-1]
    while week + WEEK <= end:
        elig = []
        for coin in panel.close:
            if week - panel.first[coin] < min_history * DAY:
                continue
            if panel.ret(coin, week, week + WEEK) is None:
                continue
            s = score(coin, week)
            if s is None:
                continue
            elig.append((s, coin, panel.dollar_volume(coin, week)))
        if liquidity and len(elig) >= 20:
            med = statistics.median(v for _, _, v in elig)
            elig = [e for e in elig if (e[2] >= med) == (liquidity == "liquid")]
        if len(elig) >= 10:
            elig.sort()
            k = max(1, int(len(elig) * quantile))
            low, high = [c for _, c, _ in elig[:k]], [c for _, c, _ in elig[-k:]]
            longs, shorts = (low, high) if reverse else (high, low)
            r_l = statistics.mean(panel.ret(c, week, week + WEEK) for c in longs)
            r_s = statistics.mean(panel.ret(c, week, week + WEEK) for c in shorts)
            f_l = statistics.mean(panel.funding(c, week, week + WEEK) for c in longs)
            f_s = statistics.mean(panel.funding(c, week, week + WEEK) for c in shorts)
            gross = r_l - r_s
            funding = -f_l + f_s
            cost = 2 * RT
            out.append({"week": week, "year": _year(week), "gross": gross,
                        "funding": funding, "cost": cost, "net": gross + funding - cost,
                        "n_side": k})
        week += WEEK
    return out


def momentum_score(panel: Panel):
    return lambda coin, day: panel.ret(coin, day - WEEK, day)


def crowding_score(panel: Panel):
    def s(coin, day):
        f = panel.fund.get(coin)
        if not f:
            return None
        xs = [f.get(day - k * DAY) for k in range(7)]
        return statistics.mean(xs) if all(x is not None for x in xs) else None
    return s


# ---------------------------------------------------------------- events

def fomo_events(panel: Panel, *, start: int, holds=(1, 3, 7)) -> dict:
    """Volume > 2x 10-day mean, SMA5 > SMA20, BTC close > BTC SMA20."""
    sig = {h: [] for h in holds}
    base = {h: [] for h in holds}
    for coin, closes in panel.close.items():
        if coin == "BTC":
            continue
        vol = panel.vol[coin]
        for day in sorted(closes):
            if day < start or day - panel.first[coin] < 30 * DAY:
                continue
            prev = [vol.get(day - k * DAY) for k in range(1, 11)]
            if any(v is None for v in prev):
                continue
            s5, s20 = panel.sma(coin, day, 5), panel.sma(coin, day, 20)
            b, b20 = panel.close["BTC"].get(day), panel.sma("BTC", day, 20)
            if None in (s5, s20, b, b20):
                continue
            fires = (vol.get(day, 0) > 2 * statistics.mean(prev) and s5 > s20 and b > b20)
            for h in holds:
                r = panel.ret(coin, day, day + h * DAY)
                if r is None:
                    continue
                net = r - panel.funding(coin, day, day + h * DAY) - RT
                base[h].append((day, net))
                if fires:
                    sig[h].append((day, net))
    return {"signal": sig, "baseline": base}


def listing_events(panel: Panel, holds=(7, 14, 30)) -> list[dict]:
    out = []
    for coin, first in panel.first.items():
        if first < LISTING_CUTOFF:
            continue
        row = {"coin": coin, "listed": first, "year": _year(first)}
        for h in holds:
            r = panel.ret(coin, first, first + h * DAY)
            if r is not None:
                # short return, net of costs; shorts receive funding
                row[h] = -r + panel.funding(coin, first, first + h * DAY) - RT
        out.append(row)
    return out


# ---------------------------------------------------------------- render

def by_year(rows: list[dict], key: str = "net") -> dict[int, dict]:
    ys: dict[int, list] = {}
    for r in rows:
        ys.setdefault(r["year"], []).append(r[key])
    return {y: _stats(v) for y, v in sorted(ys.items())}


def render_ls(name: str, rows: list[dict]) -> str:
    out = [f"== {name} ==  (weekly, per $1 each side; net = gross + funding - {100 * 2 * RT:.2f}% cost)"]
    for y, s in by_year(rows).items():
        gross = statistics.mean(r["gross"] for r in rows if r["year"] == y)
        out.append(f"  {y}: {s['n']:3d} wks  gross {100 * gross:+6.2f}%  net {100 * s['mean']:+6.2f}%/wk  t={s['t']:+5.2f}")
    s = _stats([r["net"] for r in rows])
    pos = sum(v["mean"] > 0 for v in by_year(rows).values())
    out.append(f"  all: {s['n']} wks  net {100 * s['mean']:+.2f}%/wk  t={s['t']:+.2f}  "
               f"years positive {pos}/{len(by_year(rows))}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perps", type=Path, required=True)
    ap.add_argument("--funding", type=Path, required=True)
    ap.add_argument("--start", default="2023-07-01")
    args = ap.parse_args()
    panel = Panel(pickle.loads(args.perps.read_bytes()), pickle.loads(args.funding.read_bytes()))
    start = int(dt.datetime.fromisoformat(args.start).replace(tzinfo=dt.timezone.utc).timestamp())
    start -= (start // DAY + 3) % 7 * DAY          # align to a Monday
    print(f"{len(panel.close)} coins, scoring from {dt.date.fromtimestamp(start)}\n")

    mom = momentum_score(panel)
    print(render_ls("momentum, all coins", weekly_long_short(panel, mom, start=start)))
    print(render_ls("momentum, liquid half", weekly_long_short(panel, mom, start=start, liquidity="liquid")))
    print(render_ls("reversal, illiquid half",
                    weekly_long_short(panel, mom, start=start, liquidity="illiquid", reverse=True)))
    print(render_ls("crowding: long low funding, short high funding",
                    weekly_long_short(panel, crowding_score(panel), start=start, reverse=True)))

    ev = fomo_events(panel, start=start)
    print("\n== fomo volume-spike breakout (long) ==")
    for h in ev["signal"]:
        for label, rows in (("signal", ev["signal"][h]), ("all days", ev["baseline"][h])):
            ys = {}
            for d, v in rows:
                ys.setdefault(_year(d), []).append(v)
            cells = "  ".join(f"{y}: {100 * statistics.mean(v):+5.2f}% (n={len(v)})" for y, v in sorted(ys.items()))
            print(f"  {h}d {label:8s} {cells}")

    lst = listing_events(panel)
    print(f"\n== new listings, short from first close ({len(lst)} listings) ==")
    for h in (7, 14, 30):
        xs = [r[h] for r in lst if h in r]
        s = _stats(xs)
        pos = sum(x > 0 for x in xs)
        print(f"  {h:2d}d: n={s['n']:3d}  mean {100 * s['mean']:+6.2f}%  median "
              f"{100 * statistics.median(xs):+6.2f}%  t={s['t']:+5.2f}  short wins {pos}/{len(xs)}")
        ys = {}
        for r in lst:
            if h in r:
                ys.setdefault(r["year"], []).append(r[h])
        print("       " + "  ".join(f"{y}: {100 * statistics.mean(v):+.1f}% (n={len(v)})" for y, v in sorted(ys.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
