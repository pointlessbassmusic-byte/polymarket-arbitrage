"""Shadow replay of the live bounce-short on public prices, so the weekly
check does not need the desk's server: every signal the rule would have
taken on DOGE and kSHIB since go-live (Hyperliquid daily candles, the
same history the rule was validated on), each trade's path and exit, and
the closed trades against the backtest benchmark (cryptobot.review).

It is what the desk SHOULD have done; the desk's own books (./desk.sh
review on the server) are what it DID. A gap between them is an
execution or data problem worth chasing.

    python -m cryptobot.shadow_replay [--since 2026-10-09]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt

from .review import compare, load_bench

GO_LIVE = dt.date(2026, 10, 9)
TARGET, STOP, HOLD = 0.20, 0.10, 14
COST = 0.0018


def replay(candles: dict[str, list], since: dt.date = GO_LIVE) -> list[dict]:
    trades = []
    for coin, cs in candles.items():
        closes = [c.close for c in cs]
        highs = [c.high for c in cs]
        lows = [c.low for c in cs]
        one, three, busy = [], [], -1
        for i in range(3, len(cs)):
            m1 = closes[i] / closes[i - 1] - 1
            m3 = closes[i] / closes[i - 3] - 1
            day = dt.datetime.fromtimestamp(cs[i].ts, dt.timezone.utc).date()
            if day >= since and len(one) >= 60 and i > busy:
                o, t = sorted(one), sorted(three)
                if m1 >= o[2 * len(o) // 3] and m3 <= t[len(t) // 3]:
                    entry = closes[i]
                    exit_reason, ret, end = None, None, None
                    for j in range(i + 1, min(i + HOLD, len(cs) - 1) + 1):
                        if highs[j] >= entry * (1 + STOP):        # conservative: the stop first
                            exit_reason, ret, end = "stop_loss", -STOP, j
                            break
                        if lows[j] <= entry * (1 - TARGET):
                            exit_reason, ret, end = "take_profit", TARGET, j
                            break
                    if exit_reason is None and i + HOLD <= len(cs) - 1:
                        exit_reason, end = "time_exit", i + HOLD
                        ret = -(closes[end] / entry - 1)
                    open_ret = -(closes[-1] / entry - 1)
                    trades.append({"coin": coin, "entry_day": day.isoformat(), "entry": entry,
                                   "exit_reason": exit_reason or "open",
                                   "exit_day": dt.datetime.fromtimestamp(cs[end].ts, dt.timezone.utc).date().isoformat() if end else None,
                                   "ret": (ret - COST) if ret is not None else None, "open_ret": open_ret,
                                   "time_exit_due": (day + dt.timedelta(days=HOLD)).isoformat()})
                    busy = end if end else len(cs)
            one.append(m1)
            three.append(m3)
    return sorted(trades, key=lambda t: t["entry_day"])


def render(trades: list[dict], bench: dict, today: dt.date) -> str:
    o = [f"shadow replay of the live bounce-short {today} (public Hyperliquid daily candles; what the desk should have done)"]
    if not trades:
        o.append(f"  no signals since {GO_LIVE}")
    for t in trades:
        if t["exit_reason"] == "open":
            o.append(f"  {t['coin']:5s} short from {t['entry_day']} at {t['entry']:.6g}: OPEN, {t['open_ret']:+.1%} so far, time exit due {t['time_exit_due']}")
        else:
            o.append(f"  {t['coin']:5s} short from {t['entry_day']}: {t['exit_reason']} on {t['exit_day']}, net {t['ret']:+.1%}")
    closed = [{"pnl_usd": 100 * t["ret"], "size_usd": 100.0, "exit_reason": t["exit_reason"]} for t in trades if t["ret"] is not None]
    c = compare(closed, bench)
    if c.get("n"):
        o.append(f"  closed: {c['n']}, mean {c['mean']:+.2%} a trade, win rate {c['hit']:.0%} vs backtest {bench['mean']:+.2%} and {bench['hit']:.0%}; "
                 f"chance the backtest does this badly or worse {c['p_low']:.0%} -> {c['status']}")
    else:
        o.append(f"  closed: none yet (backtest: {bench['mean']:+.2%} a trade, {bench['hit']:.0%} winners)")
    return "\n".join(o)


def fetch(coins=("DOGE", "kSHIB")) -> dict[str, list]:
    from .data.hyperliquid import HyperliquidClient

    async def go():
        c = HyperliquidClient()
        try:
            return {coin: await c.candles(coin, "1d", start_ms=int(dt.datetime(2022, 1, 1).timestamp() * 1000)) for coin in coins}
        finally:
            await c.close()
    return asyncio.run(go())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default=GO_LIVE.isoformat())
    a = ap.parse_args(argv)
    print(render(replay(fetch(), dt.date.fromisoformat(a.since)), load_bench(), dt.date.today()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
