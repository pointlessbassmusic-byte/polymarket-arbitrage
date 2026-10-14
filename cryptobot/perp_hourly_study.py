"""`kalshi-perps-hourly-rules`: many small trades a day on Kalshi's perps.
Do hourly reversal, momentum or hour-of-day rules clear the round trip?

Costs are the desk's measured ones on Kalshi: 4 bp taker a side and
4-5 bp from mid for a $50-500 order, so 18 bp a round trip; 8 bp is the
maker-fill sensitivity. The rule grid is fixed in the registry before
running: direction (reversal, momentum) x window (1h, 24h) x k (1.5,
2.0, 3.0 sigma) x hold (1h, 4h), plus the best long hour and the best
short hour of the day, 26 trials. One position per coin at a time, all
perps pooled, t-statistics clustered by entry hour because the coins
move together. The walk-forward series trades, each calendar month, the
rule that was best net on every month before it.

    python -m cryptobot.perp_hourly_study --state state [--fetch] [--cost-bp 18]
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from . import stats as S
from .data.nasdaq import read_jsonl

ROUND_TRIP_BP = 18.0
SENSITIVITY_BP = 8.0
KS = (1.5, 2.0, 3.0)
HOLDS = (1, 4)
WINDOWS = (1, 24)
SIGMA_HOURS = 168               # a week of hourly returns behind every sigma
MIN_HOURS = 24 * 14


def load(state_dir: Path, min_hours: int = MIN_HOURS) -> dict[str, list[tuple[int, float]]]:
    """ticker -> [(end_ts, close)], hourly, deduplicated and sorted."""
    d = Path(state_dir) / "kalshi_hourly"
    out = {}
    for p in sorted(d.glob("*.jsonl")) if d.exists() else []:
        rows = {int(r["end_ts"]): float(r["close"]) for r in read_jsonl(p) if r.get("close")}
        series = sorted(rows.items())
        if len(series) >= min_hours:
            out[p.stem] = series
    return out


def rules() -> list[dict]:
    out = []
    for direction in ("reversal", "momentum"):
        for window in WINDOWS:
            for k in KS:
                for hold in HOLDS:
                    out.append({"name": f"{direction}-{window}h-k{k:g}-hold{hold}h", "direction": direction,
                                "window": window, "k": k, "hold": hold})
    return out


def _features(series: list[tuple[int, float]]) -> list[dict]:
    """Per bar: the 1h and 24h log returns ending there and the sigma of
    each over the prior SIGMA_HOURS bars (not including the bar itself),
    rolling in one pass."""
    closes = [c for _, c in series]
    n = len(closes)
    r1 = [None] + [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]
    r24 = [None] * 24 + [math.log(closes[i] / closes[i - 24]) for i in range(24, n)]

    def rolling_sd(xs):
        out = [None] * n
        q = []
        sm = sq = 0.0
        for i in range(n):
            if len(q) > 20:
                mean = sm / len(q)
                out[i] = math.sqrt(max(sq / len(q) - mean * mean, 0.0))
            x = xs[i]
            if x is not None:
                q.append(x)
                sm += x
                sq += x * x
                if len(q) > SIGMA_HOURS:
                    y = q.pop(0)
                    sm -= y
                    sq -= y * y
        return out
    s1, s24 = rolling_sd(r1), rolling_sd(r24)
    return [{"i": i, "ts": ts, "close": c, "r1": r1[i], "r24": r24[i], "s1": s1[i], "s24": s24[i]}
            for i, (ts, c) in enumerate(series)]


def rule_trades(series: list[tuple[int, float]], rule: dict, cost_bp: float, ticker: str = "",
                feats: Optional[list[dict]] = None) -> list[dict]:
    """Signals at a bar's close, entered at that close, exited `hold` bars
    later at the close; one position per coin at a time."""
    feats = feats if feats is not None else _features(series)
    closes = [c for _, c in series]
    out = []
    busy_until = -1
    w = rule["window"]
    for f in feats:
        i = f["i"]
        if i <= busy_until or i + rule["hold"] >= len(closes):
            continue
        r = f["r1"] if w == 1 else f["r24"]
        s = f["s1"] if w == 1 else f["s24"]
        if r is None or not s:
            continue
        if r >= rule["k"] * s:
            side = "short" if rule["direction"] == "reversal" else "long"
        elif r <= -rule["k"] * s:
            side = "long" if rule["direction"] == "reversal" else "short"
        else:
            continue
        gross = math.log(closes[i + rule["hold"]] / closes[i]) * (1 if side == "long" else -1)
        out.append({"ticker": ticker, "rule": rule["name"], "entry_ts": f["ts"], "side": side,
                    "gross_bp": gross * 1e4, "net_bp": gross * 1e4 - cost_bp})
        busy_until = i + rule["hold"]
    return out


def grid_trades(data: dict[str, list], cost_bp: float) -> dict[str, list[dict]]:
    """Every rule's trades over every coin, features computed once per coin."""
    feats = {tk: _features(s) for tk, s in data.items()}
    return {r["name"]: [t for tk, s in data.items() for t in rule_trades(s, r, cost_bp, tk, feats[tk])] for r in rules()}


def at_cost(trades: list[dict], cost_bp: float) -> list[dict]:
    return [dict(t, net_bp=t["gross_bp"] - cost_bp) for t in trades]


def hour_of_day_trades(data: dict[str, list], cost_bp: float, train_until_ts: Optional[int] = None,
                       hold: int = 1) -> dict[str, list[dict]]:
    """The best long hour and the best short hour of the day (UTC) chosen
    on bars before `train_until_ts` (all bars when None), traded every
    day on every coin: the seasonality trials."""
    by_hour: dict[int, list[float]] = defaultdict(list)
    for series in data.values():
        for i in range(1, len(series) - hold):
            ts, c = series[i]
            if train_until_ts and ts >= train_until_ts:
                continue
            by_hour[dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour].append(math.log(series[i + hold][1] / c))
    means = {h: statistics.fmean(v) for h, v in by_hour.items() if len(v) >= 30}
    if not means:
        return {"hour-long": [], "hour-short": []}
    best_long = max(means, key=means.get)
    best_short = min(means, key=means.get)
    out = {"hour-long": [], "hour-short": []}
    for ticker, series in data.items():
        for i in range(1, len(series) - hold):
            ts, c = series[i]
            h = dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour
            g = math.log(series[i + hold][1] / c)
            if h == best_long:
                out["hour-long"].append({"ticker": ticker, "rule": f"hour-long@{best_long:02d}", "entry_ts": ts, "side": "long",
                                         "gross_bp": g * 1e4, "net_bp": g * 1e4 - cost_bp})
            if h == best_short:
                out["hour-short"].append({"ticker": ticker, "rule": f"hour-short@{best_short:02d}", "entry_ts": ts, "side": "short",
                                          "gross_bp": -g * 1e4, "net_bp": -g * 1e4 - cost_bp})
    return out


def cluster_t(xs: list[float], groups: list) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mu = statistics.fmean(xs)
    by: dict = defaultdict(float)
    for x, g in zip(xs, groups):
        by[g] += x - mu
    var = sum(v * v for v in by.values())
    g = len(by)
    if var <= 0 or g < 2:
        return 0.0
    return mu / (math.sqrt(var * g / (g - 1)) / n)


def summarize(ts: list[dict], days: float) -> dict:
    if not ts:
        return {"n": 0}
    gross = [t["gross_bp"] for t in ts]
    net = [t["net_bp"] for t in ts]
    return {"n": len(ts), "per_day": len(ts) / days if days else 0.0, "gross_bp": statistics.fmean(gross),
            "net_bp": statistics.fmean(net), "t_net": cluster_t(net, [t["entry_ts"] for t in ts]),
            "hit": statistics.fmean(1.0 if t["gross_bp"] > 0 else 0.0 for t in ts)}


def monthly(ts: list[dict]) -> list[tuple[str, float]]:
    by: dict[str, float] = defaultdict(float)
    for t in ts:
        by[dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).strftime("%Y-%m")] += t["net_bp"] / 1e4
    return sorted(by.items())


def walk_forward(data: dict[str, list], cost_bp: float, grid: Optional[dict[str, list[dict]]] = None) -> dict:
    """Each month trades the rule (grid or hour rule) that was best net per
    trade, with at least 30 trades, on every month before it."""
    all_trades = grid if grid is not None else grid_trades(data, cost_bp)
    months = sorted({dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m") for s in data.values() for ts, _ in s})
    chosen, series = [], []
    for m in months[1:]:
        m_start = int(dt.datetime.strptime(m, "%Y-%m").replace(tzinfo=dt.timezone.utc).timestamp())
        best, best_net = None, -1e9
        for name, ts in all_trades.items():
            prior = [t["net_bp"] for t in ts if t["entry_ts"] < m_start]
            if len(prior) >= 30 and statistics.fmean(prior) > best_net:
                best, best_net = name, statistics.fmean(prior)
        hod = hour_of_day_trades(data, cost_bp, train_until_ts=m_start)
        for name, ts in hod.items():
            prior = [t["net_bp"] for t in ts if t["entry_ts"] < m_start]
            if len(prior) >= 30 and statistics.fmean(prior) > best_net:
                best, best_net = name, statistics.fmean(prior)
        if best is None:
            continue
        pool = hod[best] if best in hod else all_trades[best]
        month_trades = [t for t in pool if dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).strftime("%Y-%m") == m]
        chosen.append((m, best, best_net, len(month_trades), sum(t["net_bp"] for t in month_trades) / 1e4))
        series.extend(month_trades)
    return {"chosen": chosen, "trades": series}


def run(data: dict[str, list], cost_bp: float = ROUND_TRIP_BP, sensitivity_bp: float = SENSITIVITY_BP) -> dict:
    first = min(ts for s in data.values() for ts, _ in s)
    last = max(ts for s in data.values() for ts, _ in s)
    days = (last - first) / 86400
    out = {"coins": len(data), "hours": sum(len(s) for s in data.values()), "first": first, "last": last, "days": days,
           "cost_bp": cost_bp, "rules": {}, "hours_of_day": {}}
    grid = grid_trades(data, cost_bp)
    for name, ts in grid.items():
        out["rules"][name] = summarize(ts, days)
    for name, ts in hour_of_day_trades(data, cost_bp).items():
        out["hours_of_day"][ts[0]["rule"] if ts else name] = summarize(ts, days)
    wf = walk_forward(data, cost_bp, grid)
    ms = monthly(wf["trades"])
    xs = [v for _, v in ms]
    out["walk_forward"] = {"chosen": wf["chosen"], "months": ms, "summary": summarize(wf["trades"], days),
                           "psr": S.psr(xs) if len(xs) > 2 else 0.0,
                           "last3_positive": sum(1 for v in xs[-3:] if v > 0)}
    out["trials"] = len(out["rules"]) + len(out["hours_of_day"])
    rule_srs = [S.sharpe([v for _, v in monthly(ts)]) for ts in grid.values() if len(monthly(ts)) > 2]
    var_sr = statistics.pvariance(rule_srs) if len(rule_srs) > 1 else 0.0
    out["walk_forward"]["dsr"] = S.dsr(xs, out["trials"], var_sr) if len(xs) > 2 else 0.0
    out["sensitivity"] = {name: summarize(at_cost(ts, sensitivity_bp), days) for name, ts in grid.items()}
    out["verdict"] = passes(out)
    return out


def passes(res: dict) -> tuple[str, str]:
    """Written before running: alive only if the walk-forward series is net
    positive with PSR >= 0.95 on monthly returns, DSR >= 0.95 at the trial
    count and positive in at least 2 of its last 3 months; every rule net
    negative at the full cost is killed; otherwise inconclusive."""
    wf = res["walk_forward"]
    allneg = all(s["net_bp"] < 0 for s in list(res["rules"].values()) + list(res["hours_of_day"].values()) if s.get("n"))
    if allneg:
        return "killed", f"every rule net negative at {res['cost_bp']:.0f} bp a round trip"
    s = wf["summary"]
    if not s.get("n"):
        return "inconclusive", "no walk-forward trades"
    if s["net_bp"] > 0 and wf["psr"] >= 0.95 and wf["dsr"] >= 0.95 and wf["last3_positive"] >= 2:
        return "alive", "walk-forward clears the bar"
    return "inconclusive", (f"walk-forward net {s['net_bp']:+.1f} bp/trade, PSR {wf['psr']:.2f}, DSR {wf['dsr']:.2f}, "
                            f"{wf['last3_positive']} of last 3 months positive")


def render(res: dict) -> str:
    f = dt.datetime.fromtimestamp(res["first"], dt.timezone.utc).date()
    l = dt.datetime.fromtimestamp(res["last"], dt.timezone.utc).date()
    o = [f"Kalshi perps, hourly rules: {res['coins']} coins, {res['hours']:,} hours, {f} .. {l}, {res['cost_bp']:.0f} bp a round trip"]

    def line(s):
        if not s.get("n"):
            return "no trades"
        return (f"n {s['n']:5d} ({s['per_day']:5.1f}/day): gross {s['gross_bp']:+6.1f} bp, net {s['net_bp']:+6.1f} bp/trade "
                f"(t {s['t_net']:+.1f}), hit {s['hit']*100:.0f}%")
    o.append("  grid (full sample, pooled across coins):")
    for name, s in res["rules"].items():
        o.append(f"    {name:32s} {line(s)}")
    for name, s in res["hours_of_day"].items():
        o.append(f"    {name:32s} {line(s)}")
    best = max((s for s in res["sensitivity"].values() if s.get("n")), key=lambda s: s["net_bp"], default=None)
    if best:
        bn = [n for n, s in res["sensitivity"].items() if s is best][0]
        o.append(f"  at 8 bp a round trip (maker fills, optimistic), best rule {bn}: {line(best)}")
    wf = res["walk_forward"]
    o.append(f"  walk-forward (each month trades the rule best on all prior months): {line(wf['summary'])}; "
             f"PSR {wf['psr']:.2f}, DSR {wf['dsr']:.2f} at {res['trials']} trials")
    for m, name, prior, n, pnl in wf["chosen"]:
        o.append(f"    {m}: {name} (prior {prior:+.1f} bp/trade) -> {n} trades, {pnl*100:+.2f}%")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--cost-bp", type=float, default=ROUND_TRIP_BP)
    ap.add_argument("--fetch", action="store_true", help="backfill every Kalshi perp's hourly candles first (public)")
    a = ap.parse_args(argv)
    if a.fetch:
        import asyncio
        from .vrp_collect import Collector

        async def go():
            c = Collector(a.state)
            try:
                r = await c._get_json("https://external-api.kalshi.com/trade-api/v2/margin/markets")
                tickers = tuple(m["ticker"] for m in (r.get("markets") or []) if m.get("ticker"))
                return await c.kalshi_hourly(tickers=tickers, hours=150 * 24)
            finally:
                await c.close()
        print("fetched", asyncio.run(go()))
    data = load(a.state)
    if not data:
        print("no hourly candles yet (run with --fetch)")
        return 1
    print(render(run(data, a.cost_bp)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
