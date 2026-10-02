"""Basis study: what does the perp-spot spread do to a carry trade?

`cryptobot.carry_study` scores carry on funding alone. A real position
is long spot on one venue and short the perp on another, so its P&L also
carries the change in the gap between them over the hold:

    basis = (spot_exit / spot_entry - 1) - (perp_exit / perp_entry - 1)

This prices every trade the carry simulator logs against daily closes
from both venues (00:00 UTC on each) and reports basis alongside the
funding the same trade collected.

It also catches a failure the funding data cannot: venues are matched by
ticker, and tickers collide. A median spot/perp price ratio far from 1
over a coin's shared history means the two legs are different assets.
"""

from __future__ import annotations

import argparse
import pickle
import statistics
from pathlib import Path

DAY = 86400


def unit_mult(coin: str) -> float:
    """Hyperliquid k-coins are priced per 1000 tokens."""
    return 1000.0 if coin.startswith("k") and coin[1:].isupper() else 1.0


def collisions(spots: dict, perps: dict, tol: float = 0.05) -> dict[str, float]:
    """{coin: median spot/perp ratio} for coins whose legs are not one asset."""
    out = {}
    for c, s in spots.items():
        p = perps.get(c, {})
        r = [s[d] * unit_mult(c) / p[d] for d in set(s) & set(p) if p[d] > 0]
        if r and abs(statistics.median(r) - 1.0) > tol:
            out[c] = statistics.median(r)
    return out


def price_trades(trades: list[dict], spots: dict, perps: dict) -> list[dict]:
    """Attach basis to each trade, using the closes at the entry and exit
    instants (the close of the day before each). Trades missing a price on
    either venue are dropped."""
    rows = []
    for t in trades:
        e, x = t["entry"] - DAY, t["exit"] - DAY
        s, p = spots.get(t["coin"], {}), perps.get(t["coin"], {})
        if not all(k in d for d in (s, p) for k in (e, x)):
            continue
        rows.append({**t,
                     "basis": (s[x] / s[e] - 1) - (p[x] / p[e] - 1),
                     "move": p[x] / p[e] - 1,
                     "days": (t["exit"] - t["entry"]) // DAY})
    return rows


def summary(rows: list[dict], round_trip: float) -> dict:
    b = [r["basis"] for r in rows]
    f = [r["funding"] for r in rows]
    net = [r["funding"] + r["basis"] - round_trip for r in rows]
    return {
        "n": len(rows),
        "funding_mean": statistics.mean(f), "funding_median": statistics.median(f),
        "basis_mean": statistics.mean(b), "basis_median": statistics.median(b),
        "basis_sd": statistics.stdev(b) if len(b) > 1 else 0.0,
        "basis_se": statistics.stdev(b) / len(b) ** 0.5 if len(b) > 1 else 0.0,
        "basis_worst": min(b),
        "net_mean": statistics.mean(net), "net_median": statistics.median(net),
        "net_positive": sum(x > 0 for x in net),
    }


def main() -> int:
    from cryptobot import carry_study as C
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--funding", type=Path, required=True, help="hourly funding pickle")
    ap.add_argument("--perps", type=Path, required=True, help="Hyperliquid daily candles pickle")
    ap.add_argument("--spots", type=Path, required=True,
                    help="pickle {coin: {day_ts: kraken close}}")
    args = ap.parse_args()
    spots = pickle.loads(args.spots.read_bytes())
    perps = {c: {int(x.ts // DAY) * DAY: x.close for x in cs}
             for c, (_, cs) in pickle.loads(args.perps.read_bytes()).items()}
    bad = collisions(spots, perps)
    for c, ratio in bad.items():
        print(f"EXCLUDED {c}: median spot/perp price ratio {ratio:.3f} — different assets")
    funding = {c: v for c, v in pickle.loads(args.funding.read_bytes()).items() if c not in bad}
    daily = C.daily_funding(funding)
    days = sorted({d for s in daily.values() for d in s})
    trades: list = []
    C.simulate(daily, C.CarryRule(3, 14, 0.0006, 3, 0.0), days[0] + 15 * DAY, days[-1],
               trades=trades)
    rows = price_trades(trades, spots, perps)
    s = summary(rows, C.ROUND_TRIP)
    print(f"{s['n']} trades priced on both venues")
    print(f"funding per trade : mean {100 * s['funding_mean']:+.2f}%  median {100 * s['funding_median']:+.2f}%")
    print(f"basis per trade   : mean {100 * s['basis_mean']:+.2f}% (se {100 * s['basis_se']:.2f})  "
          f"sd {100 * s['basis_sd']:.2f}%  worst {100 * s['basis_worst']:+.2f}%")
    print(f"net after {100 * C.ROUND_TRIP:.2f}% fees: mean {100 * s['net_mean']:+.2f}%  "
          f"median {100 * s['net_median']:+.2f}%  positive {s['net_positive']}/{s['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
