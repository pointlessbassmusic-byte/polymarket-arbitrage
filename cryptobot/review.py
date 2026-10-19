"""Weekly review: is the live bounce-short trading like its backtest, and
where does every forward test stand?

1. Live vs backtest. The benchmark (cryptobot/data/bounce_benchmark.json)
   is every trade the live rule would have taken on DOGE and kSHIB from
   2022 on Hyperliquid daily candles, at Kalshi's 18 bp round trip, with
   its exit (take_profit / stop_loss / time_exit). The review reads the
   desk's books (state/cryptobot_{sim,real}_portfolio.json) and compares
   the closed trades' mean return, win rate and exit mix with it. The
   bootstrap p is the share of random same-size draws from the benchmark
   whose mean is at or below the live mean: under 5% is a warning that
   the live rule is doing worse than its history, not just unlucky.
2. Sim vs real: the per-trade gap is the execution cost the paper book
   does not pay.
3. The forward tests, with their read dates.

    python -m cryptobot.review --state state
    python -m cryptobot.review --build-benchmark hl_daily.pkl     # regenerate the benchmark
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import random
import statistics
from pathlib import Path
from typing import Optional

BENCH = Path(__file__).parent / "data" / "bounce_benchmark.json"
COST = 0.0018

# (registry id, what, read when) - kept in step with cryptobot/hypotheses.yaml
FORWARD = (
    ("btc-leads-us500-intraday", "BTC perp leads the US500 perp hour to hour", dt.date(2026, 11, 5), "500 consecutive shared hours (about 16 a day)"),
    ("kalshi-book-imbalance", "order-book imbalance on 8 perps", dt.date(2026, 11, 12), "30 days of books"),
    ("kalshi-btc-daily-favourite-oos", "daily BTC favourite at 11:00 ET", dt.date(2026, 12, 13), "60 independent days"),
    ("hype-mention-fade", "attention spikes fade on the Kalshi coins", dt.date(2027, 1, 12), "90 days of hype snapshots"),
    ("kalshi-btc-carry-etf-hedge", "short BTC perp vs long IBIT while funding > 4%/yr", dt.date(2027, 2, 12), "120 days"),
    ("btc-vrp-ladder-oos", "IBIT option ladder, out of sample", dt.date(2027, 10, 1), "12 months of IBIT rows"),
    ("orb-qqq-pilot", "QQQ opening-range paper pilot", None, "60 traded sessions"),
    ("macro pilot (2s10s -> XLF)", "macro paper pilot", None, "20 closed trades"),
)


def build_benchmark(pkl: Path, coins=("DOGE", "kSHIB")) -> dict:
    from .perp_study import outcome
    from .research import Barrier
    bar, horizon = Barrier(target=0.20, stop=0.10), 14
    d = pickle.load(open(pkl, "rb"))
    trades = []
    for coin in coins:
        v = d[coin]
        cs = next((x for x in v if isinstance(x, list)), None) if isinstance(v, tuple) else v
        closes = [c.close for c in cs]
        highs = [c.high for c in cs]
        lows = [c.low for c in cs]
        one, three, busy = [], [], -1
        for i in range(3, len(cs) - 1):
            m1 = closes[i] / closes[i - 1] - 1
            m3 = closes[i] / closes[i - 3] - 1
            if len(one) >= 60 and i > busy:
                o, t = sorted(one), sorted(three)
                if m1 >= o[2 * len(o) // 3] and m3 <= t[len(t) // 3] and i + horizon < len(cs):
                    win, pnl = outcome(highs, lows, closes, i, closes[i], bar, horizon, "short")
                    reason = "take_profit" if win else ("stop_loss" if abs(pnl + bar.stop) < 1e-12 else "time_exit")
                    end = i + horizon
                    for j in range(i + 1, i + horizon + 1):
                        if highs[j] >= closes[i] * (1 + bar.stop) or lows[j] <= closes[i] * (1 - bar.target):
                            end = j
                            break
                    busy = end
                    trades.append({"coin": coin, "date": dt.datetime.fromtimestamp(cs[i].ts, dt.timezone.utc).date().isoformat(),
                                   "ret": round(pnl - COST, 6), "exit": reason})
            one.append(m1)
            three.append(m3)
    rets = [t["ret"] for t in trades]
    return {"rule": "short when the 1-day move is in its top tercile and the 3-day move in its bottom tercile; -20% target, +10% stop, 14 days",
            "coins": list(coins), "cost": COST, "n": len(trades), "mean": statistics.fmean(rets),
            "hit": statistics.fmean(1.0 if r > 0 else 0.0 for r in rets),
            "exits": {k: sum(1 for t in trades if t["exit"] == k) / len(trades) for k in ("take_profit", "stop_loss", "time_exit")},
            "first": min(t["date"] for t in trades), "last": max(t["date"] for t in trades), "trades": trades}


def load_closed(state: Path, book: str) -> list[dict]:
    p = state / f"cryptobot_{book}_portfolio.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text()).get("closed", [])
    except (OSError, ValueError):
        return []


def compare(closed: list[dict], bench: dict, rng: Optional[random.Random] = None, draws: int = 5000) -> dict:
    rets = [t["pnl_usd"] / t["size_usd"] for t in closed if t.get("size_usd")]
    out = {"n": len(rets)}
    if not rets:
        return out
    mean = statistics.fmean(rets)
    out.update({"mean": mean, "hit": statistics.fmean(1.0 if r > 0 else 0.0 for r in rets),
                "exits": {k: sum(1 for t in closed if t.get("exit_reason") == k) / len(closed) for k in ("take_profit", "stop_loss", "time_exit")},
                "pnl_usd": sum(t["pnl_usd"] for t in closed)})
    pool = [t["ret"] for t in bench["trades"]]
    rng = rng or random.Random(11)
    below = sum(1 for _ in range(draws) if statistics.fmean(rng.choices(pool, k=len(rets))) <= mean)
    out["p_low"] = below / draws
    out["status"] = ("too few trades to judge" if len(rets) < 5 else
                     "WARNING: worse than the backtest beyond bad luck" if out["p_low"] < 0.05 else
                     "within the backtest's range")
    return out


def render(state: Path, bench: dict, today: Optional[dt.date] = None) -> str:
    today = today or dt.date.today()
    o = [f"weekly review {today}",
         f"benchmark: {bench['n']} backtest trades on {', '.join(bench['coins'])} {bench['first']} to {bench['last']}: "
         f"mean {bench['mean']:+.2%} a trade, win rate {bench['hit']:.0%}, exits "
         + ", ".join(f"{k} {v:.0%}" for k, v in bench["exits"].items())]
    per = {}
    for book in ("real", "sim"):
        closed = load_closed(state, book)
        c = compare(closed, bench)
        per[book] = c
        if not c["n"]:
            o.append(f"  {book}: no closed trades yet")
            continue
        o.append(f"  {book}: {c['n']} closed, P&L ${c['pnl_usd']:+,.2f}, mean {c['mean']:+.2%} a trade, win rate {c['hit']:.0%}, exits "
                 + ", ".join(f"{k} {v:.0%}" for k, v in c["exits"].items())
                 + f"; chance the backtest does this badly or worse {c['p_low']:.0%} -> {c['status']}")
    if per.get("real", {}).get("n") and per.get("sim", {}).get("n"):
        o.append(f"  real minus sim, per trade: {per['real']['mean'] - per['sim']['mean']:+.2%} (execution cost the paper book does not pay)")
    o.append("forward tests:")
    for rid, what, when, need in FORWARD:
        if when:
            left = (when - today).days
            o.append(f"  {what}: read {when} ({'due' if left <= 0 else f'{left} days'}), needs {need}  [{rid}]")
        else:
            o.append(f"  {what}: read after {need}  [{rid}]")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--build-benchmark", type=Path, default=None, help="Hyperliquid daily pickle with DOGE and kSHIB")
    a = ap.parse_args(argv)
    if a.build_benchmark:
        b = build_benchmark(a.build_benchmark)
        BENCH.parent.mkdir(parents=True, exist_ok=True)
        BENCH.write_text(json.dumps(b, indent=0))
        print(f"benchmark: {b['n']} trades, mean {b['mean']:+.2%}, win {b['hit']:.0%}, exits {b['exits']}, {b['first']} to {b['last']}")
        return 0
    print(render(a.state, json.loads(BENCH.read_text())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
