"""`daytrade-stocks`: the day trading bot's EMA 9/21 scalper on SPY, QQQ
and IWM inside the US session, at stock costs (and SPY also on Kalshi's
US500 perp).

Windows (New York time): 09:30-12:00 and 13:00-15:55, both directions,
flat between and at 15:55. V1: ATR(14) exits 1.5 / 3 ATR. V2: V1 plus the
opening-range filter (after 10:00, longs only above the 09:30-10:00 high,
shorts only below its low). Same engine as the crypto bot
(cryptobot.daytrade). 2 variants x 2 timeframes x 3 ETFs + 4 SPY-on-perp
cells = 16 trials.

Runs where the Alpaca paper keys are (the server):

    python -m cryptobot.daytrade_stocks_study --cache DIR --fetch
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import pickle
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from .daytrade import VARIANTS, backtest, resample, stock_window
from .daytrade_study import summarize
from .stats import dsr

ET = ZoneInfo("America/New_York")
SYMBOLS = ("SPY", "QQQ", "IWM")
STOCK_VARIANTS = ("V1", "V2")
FRAMES = (("15m", 900), ("30m", 1800))
HALF_SPREAD_BP = {"SPY": 0.3, "QQQ": 0.4, "IWM": 0.8}
SLIP_BP, SELL_FEES_BP = 1.0, 0.3
PERP_BP = 2 * (4.0 + 0.3)
START = dt.datetime(2024, 10, 1, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc)


def etf_cost_bp(sym: str) -> float:
    return 2 * (HALF_SPREAD_BP[sym] + SLIP_BP) + SELL_FEES_BP


async def fetch(cache: Path, symbols=SYMBOLS) -> None:
    from .data.alpaca import AlpacaData
    d = AlpacaData()
    if not d.has_key:
        raise RuntimeError("CRYPTOBOT_ALPACA_KEY_ID / CRYPTOBOT_ALPACA_SECRET_KEY are not set")
    cache.mkdir(parents=True, exist_ok=True)
    try:
        for s in symbols:
            bars = await d.bars(s, "5Min", START, END)
            (cache / f"{s}_5m.pkl").write_bytes(pickle.dumps(bars))
            print(f"{s}: {len(bars)} five-minute bars")
    finally:
        await d.close()


def regular_hours(candles) -> list[tuple]:
    """Candles -> (ts, o, h, l, c, v) tuples inside 09:30-16:00 New York, weekdays."""
    out = []
    for c in sorted(candles, key=lambda c: c.ts):
        t = dt.datetime.fromtimestamp(c.ts, ET)
        if t.weekday() < 5 and dt.time(9, 30) <= t.time() < dt.time(16, 0):
            out.append((int(c.ts), c.open, c.high, c.low, c.close, c.volume_usd))
    return out


def run(cache: Path) -> dict:
    cells, rets = {}, {}
    for sym in SYMBOLS:
        p = cache / f"{sym}_5m.pkl"
        if not p.exists():
            continue
        b5 = regular_hours(pickle.loads(p.read_bytes()))
        for fname, sec in FRAMES:
            bars = resample(b5, sec)
            for v in STOCK_VARIANTS:
                tr = backtest(bars, v, sym, window_fn=stock_window, cost=etf_cost_bp(sym))
                costs = [("etf", etf_cost_bp(sym))] + ([("perp", PERP_BP)] if sym == "SPY" else [])
                for ins, cost in costs:
                    for t in tr:
                        t["net_ins"] = t["gross_bp"] - cost
                    s = summarize(tr, "net_ins", windows=("am", "pm"))
                    for side, k in ((1, "long"), (-1, "short")):
                        x = [t["net_ins"] for t in tr if t["side"] == side]
                        s[k] = (len(x), statistics.fmean(x) if x else None)
                    key = (v, fname, sym, ins)
                    cells[key] = s
                    rets[key] = [t["net_ins"] / 1e4 for t in tr]
    srs = [c["sr"] for c in cells.values() if c.get("n", 0) >= 5]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    n_trials = max(1, len(cells))
    for k, c in cells.items():
        c["dsr"] = dsr(rets[k], n_trials, var_sr) if len(rets[k]) >= 20 else None
    cands, by_variant = [], {}
    for (v, f, sym, ins), s in cells.items():
        if ins == "etf":
            by_variant.setdefault(v, []).append(s.get("net", 0.0))
        if (s.get("n", 0) >= 200 and s["net"] >= 3 and s["t"] >= 2.5 and s["h1"] > 0 and s["h2"] > 0
                and (s["dsr"] or 0) >= 0.95):
            cands.append(f"{v} {f} {sym} {ins}")
    killed = [v for v, nets in by_variant.items() if nets and all(x < 0 for x in nets)]
    return {"cells": {"|".join(k): s for k, s in cells.items()}, "candidates": cands, "killed_variants": killed,
            "trials": n_trials}


def render(res: dict) -> str:
    o = ["day trading bot on US index ETFs (Alpaca IEX bars, regular hours); round trips: "
         + ", ".join(f"{s} {etf_cost_bp(s):.1f} bp" for s in SYMBOLS) + f"; SPY on the Kalshi US500 perp {PERP_BP:.1f} bp",
         f"  {'cell':22s} {'trades':>6s} {'/day':>5s} {'gross':>6s} {'net':>6s} {'t':>5s} {'win':>4s} {'halves':>13s} {'DSR':>5s}"
         "  am / pm (n, net)            long / short (n, net)        exits tgt/stop/flat"]
    for k, s in res["cells"].items():
        name = k.replace("|", " ")
        if s.get("n", 0) < 5:
            o.append(f"  {name:22s} n {s.get('n', 0)}")
            continue
        f = lambda p: f"{p[0]} {p[1] if p[1] is not None else 0:+.1f}"
        ex = s["exits"]
        o.append(f"  {name:22s} {s['n']:6d} {s['per_day']:5.2f} {s['gross']:+6.1f} {s['net']:+6.1f} {s['t']:+5.1f} {s['hit']:4.0%} "
                 f"{s['h1']:+6.1f}/{s['h2']:+6.1f} {s['dsr'] if s['dsr'] is not None else 0:5.2f}  "
                 f"{f(s['am']):>10s} / {f(s['pm']):<10s}   {f(s['long']):>10s} / {f(s['short']):<10s}   "
                 f"{ex['target']:.0%}/{ex['stop']:.0%}/{ex['flat_out_of_hours']:.0%}")
    o.append(f"verdict: candidates {res['candidates'] or 'none'}; variants killed (negative on every ETF cell) "
             f"{res['killed_variants'] or 'none'}; {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path("stocks_cache"))
    ap.add_argument("--fetch", action="store_true", help="pull the 5-minute bars first (Alpaca keys)")
    a = ap.parse_args(argv)
    if a.fetch:
        asyncio.run(fetch(a.cache))
    res = run(a.cache)
    if not res["cells"]:
        print(f"no bars in {a.cache}: run with --fetch (needs the Alpaca keys)")
        return 1
    print(render(res))
    (a.cache / "daytrade_stocks_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
