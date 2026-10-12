"""Opening-range breakout on QQQ, the pilot that decides whether the
"stocks in play" version is worth a broker and a full-market feed.

Pre-registered as `orb-qqq-pilot` (hypotheses.yaml). The rule, as
written there and in Zarattini & Aziz (2023): on each session, if the
first 5-minute bar (09:30-09:35 New York time) closes above its open, buy
at the open of the second bar; if it closes below, sell short; stop at
0.1 x the 14-day ATR from the entry; target 10 R (so most days end flat
at the close); size the position so a stop costs 1% of capital, capped
at 4x leverage. A doji first bar means no trade. Costs: `slip` dollars
per share on each of the two executions (1 c default, 2.2 c sensitivity
= the replications' break-even), no commission.

Data: 5-minute bars in the project's Candle shape, from Alpaca's free
IEX feed (paper keys work):

    python -m cryptobot.orb_study --fetch --cache qqq_5m.pkl      # needs CRYPTOBOT_ALPACA_KEY_ID/SECRET
    python -m cryptobot.orb_study --cache qqq_5m.pkl --slip 0.01
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import statistics
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from . import stats as S
from .data.geckoterminal import Candle

ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class OrbRule:
    atr_days: int = 14
    stop_atr: float = 0.10
    target_r: float = 10.0
    risk_per_day: float = 0.01
    max_leverage: float = 4.0


# ------------------------------------------------------------------ sessions

def sessions(bars: list[Candle]) -> dict[dt.date, list[Candle]]:
    """Regular-hours bars (09:30-16:00 New York) grouped by session date,
    sorted; a session needs its 09:30 bar to count."""
    out: dict[dt.date, list[Candle]] = {}
    for b in sorted(bars, key=lambda c: c.ts):
        t = dt.datetime.fromtimestamp(b.ts, dt.timezone.utc).astimezone(ET)
        minutes = t.hour * 60 + t.minute
        if 9 * 60 + 30 <= minutes < 16 * 60:
            out.setdefault(t.date(), []).append(b)
    return {d: bs for d, bs in out.items() if _minute_of(bs[0]) == 9 * 60 + 30}


def _minute_of(b: Candle) -> int:
    t = dt.datetime.fromtimestamp(b.ts, dt.timezone.utc).astimezone(ET)
    return t.hour * 60 + t.minute


def daily_ohlc(sess: dict[dt.date, list[Candle]]) -> list[dict]:
    out = []
    for d in sorted(sess):
        bs = sess[d]
        out.append({"day": d, "open": bs[0].open, "high": max(b.high for b in bs),
                    "low": min(b.low for b in bs), "close": bs[-1].close})
    return out


def atr(daily: list[dict], n: int) -> dict[dt.date, float]:
    """Wilder-free simple ATR: mean true range of the previous `n` sessions
    (yesterday back), so today's bars never enter today's stop."""
    trs = []
    out = {}
    for i, r in enumerate(daily):
        if i:
            p = daily[i - 1]["close"]
            trs.append(max(r["high"] - r["low"], abs(r["high"] - p), abs(r["low"] - p)))
        if len(trs) >= n:
            out[r["day"]] = statistics.fmean(trs[-n:])
    # the ATR known at the open of day d is the one computed through d-1
    days = sorted(out)
    return {days[i]: out[days[i - 1]] for i in range(1, len(days))}


# ------------------------------------------------------------------ the trade

def simulate_day(bars: list[Candle], atr_today: float, rule: OrbRule, slip: float, capital: float) -> dict | None:
    first = bars[0]
    if len(bars) < 3 or first.close == first.open or atr_today <= 0:
        return None
    side = 1.0 if first.close > first.open else -1.0
    entry = bars[1].open
    dist = rule.stop_atr * atr_today
    stop = entry - side * dist
    target = entry + side * rule.target_r * dist
    shares = min(rule.risk_per_day * capital / dist, rule.max_leverage * capital / entry)
    shares = math.floor(shares)
    if shares < 1:
        return None
    exit_px, reason = bars[-1].close, "close"
    for b in bars[1:]:
        if side > 0 and b.low <= stop:
            exit_px, reason = stop, "stop"
            break
        if side < 0 and b.high >= stop:
            exit_px, reason = stop, "stop"
            break
        if side > 0 and b.high >= target:
            exit_px, reason = target, "target"
            break
        if side < 0 and b.low <= target:
            exit_px, reason = target, "target"
            break
    gross = side * (exit_px - entry) * shares
    cost = 2 * slip * shares
    return {"side": side, "entry": entry, "exit": exit_px, "reason": reason, "shares": shares,
            "r": side * (exit_px - entry) / dist, "gross": gross, "cost": cost, "net": gross - cost,
            "net_pct": (gross - cost) / capital}


def run(bars: list[Candle], rule: OrbRule = OrbRule(), slip: float = 0.01, capital: float = 25_000.0,
        compound: bool = False) -> dict:
    sess = sessions(bars)
    daily = daily_ohlc(sess)
    atrs = atr(daily, rule.atr_days)
    trades = []
    equity = capital
    for d in sorted(sess):
        a = atrs.get(d)
        if a is None:
            continue
        t = simulate_day(sess[d], a, rule, slip, equity if compound else capital)
        if t:
            t["day"] = d
            trades.append(t)
            if compound:
                equity += t["net"]
    return summarize(trades, capital)


def summarize(trades: list[dict], capital: float) -> dict:
    rets = [t["net_pct"] for t in trades]
    by_year: dict[int, dict] = {}
    for t in trades:
        y = by_year.setdefault(t["day"].year, {"n": 0, "net_pct": 0.0, "gross_pct": 0.0, "wins": 0})
        y["n"] += 1
        y["net_pct"] += t["net_pct"]
        y["gross_pct"] += t["gross"] / capital
        y["wins"] += t["net"] > 0
    years = max((trades[-1]["day"] - trades[0]["day"]).days, 1) / 365.25 if len(trades) > 1 else 1.0
    sd = statistics.pstdev(rets) if len(rets) > 2 else 0.0
    return {"trades": len(trades), "by_year": by_year,
            "mean_r": statistics.fmean(t["r"] for t in trades) if trades else 0.0,
            "hit": sum(1 for t in trades if t["net"] > 0) / len(trades) if trades else 0.0,
            "ann_net_pct": sum(rets) / years, "sharpe": statistics.fmean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
            "psr": S.psr(rets) if len(rets) > 2 else 0.0,
            "exits": {r: sum(1 for t in trades if t["reason"] == r) for r in {t["reason"] for t in trades}},
            "positive_years": sum(1 for y in by_year.values() if y["net_pct"] > 0),
            "net_2023_on": sum(y["net_pct"] for yr, y in by_year.items() if yr >= 2023)}


def passes(m: dict) -> tuple[str, str]:
    """Written before running: net Sharpe > 0.5 at 1 c/share with PSR >= 0.95
    over 2016-2026 and net positive in 2023-2026 keeps the family open;
    net <= 0 at 1 c/share kills the QQQ version."""
    if m["trades"] < 100:
        return "inconclusive", "fewer than 100 sessions traded"
    if m["ann_net_pct"] <= 0:
        return "killed", "net <= 0 at 1 c/share"
    if m["sharpe"] > 0.5 and m["psr"] >= 0.95 and m["net_2023_on"] > 0:
        return "alive", "clears the bar"
    return "inconclusive", "positive but below the bar"


def render(label: str, m: dict) -> str:
    o = [f"{label}: {m['trades']} sessions, mean {m['mean_r']:+.2f} R, hit {m['hit']*100:.0f}%, "
         f"net {m['ann_net_pct']*100:+.1f}%/yr of capital, Sharpe {m['sharpe']:+.2f}, PSR {m['psr']:.2f}, exits {m['exits']}"]
    o.append("  " + " ".join(f"{y}:{v['net_pct']*100:+.0f}%({v['n']})" for y, v in sorted(m["by_year"].items())))
    return "\n".join(o)


# ------------------------------------------------------------------ data

async def fetch(cache: Path, symbol: str = "QQQ", start: dt.datetime | None = None) -> int:
    """Pull 5-minute bars from Alpaca's IEX feed into `cache` (pickle of Candles)."""
    from .data.alpaca import AlpacaData
    d = AlpacaData()
    if not d.has_key:
        raise RuntimeError("CRYPTOBOT_ALPACA_KEY_ID / CRYPTOBOT_ALPACA_SECRET_KEY are not set")
    try:
        bars = await d.bars(symbol, "5Min", start or dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc))
    finally:
        await d.close()
    cache.write_bytes(pickle.dumps(bars))
    return len(bars)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path("qqq_5m.pkl"))
    ap.add_argument("--symbol", default="QQQ")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--slip", type=float, default=0.01, help="dollars per share per execution")
    ap.add_argument("--capital", type=float, default=25_000.0)
    a = ap.parse_args(argv)
    if a.fetch:
        import asyncio
        n = asyncio.run(fetch(a.cache, a.symbol))
        print(f"fetched {n} bars into {a.cache}")
    if not a.cache.exists():
        print(f"{a.cache} missing: run with --fetch (needs Alpaca keys)")
        return 1
    bars = pickle.loads(a.cache.read_bytes())
    for slip, label in ((a.slip, f"{a.symbol} ORB at {a.slip*100:.1f} c/share"),
                        (0.022, f"{a.symbol} ORB at 2.2 c/share (replications' break-even)"),
                        (0.0, f"{a.symbol} ORB gross")):
        m = run(bars, slip=slip, capital=a.capital)
        print(render(label, m))
        if slip == a.slip:
            verdict, why = passes(m)
            print(f"  pre-registered verdict at {a.slip*100:.1f} c: {verdict} ({why})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
