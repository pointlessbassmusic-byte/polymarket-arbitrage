"""Pre-registered test: BTC outside-US-hours seasonality.

Registry entry `btc-offhours-seasonality` (written before this ran):
buy BTC at the 16:00 ET hourly close, sell at the 10:00 ET hourly close
of the next weekday (Friday to Monday over weekends), one round trip per
holding, 1x. Compared with the US-session leg (10:00 to 16:00 ET the same
day) and buy-and-hold over the same days, by year, at a 0.08% (Kalshi
BTC perp) and 0.10% (Coinbase) round trip. Success criterion as
registered: net Sharpe > 0 with PSR >= 0.95 over 2021-2026 at 0.08% AND
positive net in the post-publication window 2024-11..2026-10.

Data: Coinbase public hourly BTC-USD candles. Rebuild with the fetch
script at the bottom of this file (`--fetch OUT.pkl`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from .stats import psr

ET = ZoneInfo("America/New_York")
ENTRY_HOUR, EXIT_HOUR = 16, 10
COSTS = (0.0008, 0.0010)


def hourly_closes(rows) -> dict[int, float]:
    """Close price keyed by the candle's END timestamp."""
    return {int(ts) + 3600: float(c) for ts, o, h, l, c, v in rows}


def _et(ts: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, ET)


def legs(closes: dict[int, float]) -> list[dict]:
    """One row per weekday holding: overnight (16:00 ET -> next weekday
    10:00 ET), session (10:00 -> 16:00 ET same day) and the matching
    close-to-close hold (16:00 ET -> next weekday 16:00 ET)."""
    by_local: dict[tuple, int] = {}
    for ts in closes:
        d = _et(ts)
        by_local[(d.date(), d.hour)] = ts
    days = sorted({k[0] for k in by_local})
    out = []
    for i, day in enumerate(days):
        if day.weekday() >= 5:
            continue
        nxt = next((x for x in days[i + 1:] if x.weekday() < 5), None)
        e_ts, x_ts = by_local.get((day, ENTRY_HOUR)), by_local.get((nxt, EXIT_HOUR)) if nxt else None
        s_ts, c_ts = by_local.get((day, EXIT_HOUR)), by_local.get((nxt, ENTRY_HOUR)) if nxt else None
        if not (e_ts and x_ts and s_ts and c_ts):
            continue
        out.append({"day": day, "year": day.year,
                    "overnight": closes[x_ts] / closes[e_ts] - 1.0,
                    "session": closes[e_ts] / closes[s_ts] - 1.0,
                    "hold": closes[c_ts] / closes[e_ts] - 1.0,
                    "weekend": (nxt - day).days > 1})
    return out


def _stats(xs: list[float]) -> dict:
    if len(xs) < 3:
        return {"n": len(xs), "mean": 0.0, "sum": 0.0, "sr": 0.0, "t": 0.0, "psr": 0.5}
    m, sd = statistics.mean(xs), statistics.stdev(xs)
    sr = m / sd if sd else 0.0
    return {"n": len(xs), "mean": m, "sum": sum(xs), "sr": sr, "t": sr * math.sqrt(len(xs)),
            "psr": psr(xs, 0.0) if sd else 0.5}


def report(rows: list[dict], cost: float, start: dt.date, end: dt.date, post_pub: dt.date) -> dict:
    sel = [r for r in rows if start <= r["day"] <= end]
    net = [r["overnight"] - cost for r in sel]
    out = {"cost": cost, "overall": _stats(net),
           "session": _stats([r["session"] - cost for r in sel]),
           "hold": _stats([r["hold"] for r in sel]),
           "post_pub": _stats([r["overnight"] - cost for r in sel if r["day"] >= post_pub]),
           "weekend": _stats([r["overnight"] - cost for r in sel if r["weekend"]]),
           "weekday": _stats([r["overnight"] - cost for r in sel if not r["weekend"]]),
           "by_year": {}}
    for y in sorted({r["year"] for r in sel}):
        g = [r for r in sel if r["year"] == y]
        out["by_year"][y] = {"overnight": _stats([r["overnight"] - cost for r in g]),
                             "session": _stats([r["session"] - cost for r in g]),
                             "hold": _stats([r["hold"] for r in g])}
    return out


def render(rep: dict) -> str:
    o = rep["overall"]
    lines = [f"round trip {100 * rep['cost']:.2f}%: overnight leg n={o['n']} mean {100 * o['mean']:+.3f}%/holding "
             f"sum {100 * o['sum']:+.1f}% SR/holding {o['sr']:+.3f} t={o['t']:+.2f} PSR={o['psr']:.3f}",
             f"   session leg: mean {100 * rep['session']['mean']:+.3f}% sum {100 * rep['session']['sum']:+.1f}% t={rep['session']['t']:+.2f}",
             f"   buy-and-hold same days: mean {100 * rep['hold']['mean']:+.3f}% sum {100 * rep['hold']['sum']:+.1f}% t={rep['hold']['t']:+.2f}",
             f"   weekend holdings: mean {100 * rep['weekend']['mean']:+.3f}% (n={rep['weekend']['n']}); "
             f"weekday: {100 * rep['weekday']['mean']:+.3f}% (n={rep['weekday']['n']})",
             f"   post-publication window: n={rep['post_pub']['n']} mean {100 * rep['post_pub']['mean']:+.3f}% "
             f"sum {100 * rep['post_pub']['sum']:+.1f}% t={rep['post_pub']['t']:+.2f} PSR={rep['post_pub']['psr']:.3f}",
             "   year   n  overnight(net)  session(net)  buy&hold"]
    for y, g in rep["by_year"].items():
        lines.append(f"   {y}  {g['overnight']['n']:3d}  {100 * g['overnight']['sum']:+8.1f}%      "
                     f"{100 * g['session']['sum']:+8.1f}%   {100 * g['hold']['sum']:+8.1f}%")
    return "\n".join(lines)


def verdict(rep08: dict) -> str:
    o, pp = rep08["overall"], rep08["post_pub"]
    if o["sr"] > 0 and o["psr"] >= 0.95 and pp["sum"] > 0:
        return "PASS the pre-registered criterion"
    if o["sum"] <= 0 and pp["sum"] <= 0:
        return "FAIL both legs of the criterion: killed"
    return "inconclusive: does not meet the pre-registered criterion"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hourly", type=Path, help="pickle of (ts, o, h, l, c, v) hourly rows")
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default="2026-12-31")
    ap.add_argument("--post-pub", default="2024-11-01")
    ap.add_argument("--fetch", type=Path, metavar="OUT", help="download Coinbase hourly BTC-USD to OUT and exit")
    args = ap.parse_args()
    if args.fetch:
        return fetch(args.fetch)
    rows = legs(hourly_closes(pickle.loads(args.hourly.read_bytes())))
    start, end, pp = (dt.date.fromisoformat(x) for x in (args.start, args.end, args.post_pub))
    first = None
    for cost in COSTS:
        rep = report(rows, cost, start, end, pp)
        first = first or rep
        print(render(rep))
    print("\n" + verdict(first))
    return 0


def fetch(out: Path) -> int:
    import asyncio
    import time

    import httpx
    api = "https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/candles"

    async def run():
        t, end, rows = int(dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc).timestamp()), int(time.time()), {}
        async with httpx.AsyncClient(timeout=30) as c:
            while t < end:
                t2 = min(t + 349 * 3600, end)
                r = await c.get(api, params={"start": str(t), "end": str(t2), "granularity": "ONE_HOUR"})
                r.raise_for_status()
                for row in r.json().get("candles", []):
                    rows[int(row["start"])] = tuple(float(row[k]) if k != "start" else int(row[k])
                                                    for k in ("start", "open", "high", "low", "close", "volume"))
                t = t2
                await asyncio.sleep(0.25)
        out.write_bytes(pickle.dumps([rows[k] for k in sorted(rows)]))
        print(len(rows), "hourly candles ->", out)
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
