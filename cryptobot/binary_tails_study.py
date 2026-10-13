"""`kalshi-btc-hourly-tails`: on Kalshi's hourly BTC above/below markets,
is the favourite at 85-97 cents underpriced half an hour before the
print (the longshot bias the vol premium suggests), after the fee?

Registered rule: at the bar ending exactly 30 (and 15) minutes before
close, if the YES mid is at or under 15 cents buy NO at one minus the
YES bid, if it is at or above 85 cents buy YES at the ask; keep the
trade when the price paid is 0.85-0.97 and the quoted spread is at most
5 cents; settle on the result; pay 0.07 x price x (1 - price) a
contract. Every strike in an hour settles on one print, so t-statistics
are clustered by event. Variants, counted as trials: the mirror (buy
the longshot at its ask when it costs 3-15 cents), a resting bid one
cent under the favourite's ask filled only when the last trade later
goes through it (no fee), and the 0.97-0.99 bucket.

    python -m cryptobot.binary_tails_study --state state
"""
from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from . import stats as S
from .data.nasdaq import read_jsonl

DECISION_MINUTES = (30, 15)
FAV_LO, FAV_HI = 0.85, 0.97
LONG_LO, LONG_HI = 0.03, 0.15
MAX_SPREAD = 0.05
FEE_RATE = 0.07
BUCKETS = ((0.85, 0.90), (0.90, 0.95), (0.95, 0.97), (0.97, 0.99))


def fee(p: float) -> float:
    return FEE_RATE * p * (1.0 - p)


def load(state_dir: Path) -> tuple[list[dict], dict[str, list]]:
    d = Path(state_dir) / "kalshi_binaries"
    markets = read_jsonl(d / "markets.jsonl")
    bars: dict[str, list] = {}
    for p in sorted((d / "candles").glob("*.jsonl")) if (d / "candles").exists() else []:
        for r in read_jsonl(p):
            bars[r["ticker"]] = r["bars"]
    return [m for m in markets if m["ticker"] in bars], bars


def quote_at(bars: list, ts: int, tolerance_s: int = 300) -> Optional[tuple[float, float, Optional[float], int]]:
    """(yes bid, yes ask, last, index) of the bar ending at `ts`, or the
    last one before it within `tolerance_s`; None without a two-sided quote."""
    best = None
    for i, b in enumerate(bars):
        if b[0] <= ts and ts - b[0] <= tolerance_s:
            best = i
        elif b[0] > ts:
            break
    if best is None:
        return None
    _, bid, ask, last, _ = bars[best]
    if bid is None or ask is None or bid <= 0 or ask >= 1 or ask < bid:
        return None
    return bid, ask, last, best


def favourite(bid: float, ask: float) -> Optional[tuple[str, float, float]]:
    """(side, price paid, implied probability) for the favourite side."""
    mid = (bid + ask) / 2
    if mid <= 1 - FAV_LO:
        return "no", 1.0 - bid, 1.0 - mid
    if mid >= FAV_LO:
        return "yes", ask, mid
    return None


def longshot(bid: float, ask: float) -> Optional[tuple[str, float, float]]:
    mid = (bid + ask) / 2
    if mid <= 1 - FAV_LO:
        return "yes", ask, mid
    if mid >= FAV_LO:
        return "no", 1.0 - bid, 1.0 - mid
    return None


def trades(markets: list[dict], bars: dict[str, list], minutes_before: int, rule: str = "favourite",
           lo: float = FAV_LO, hi: float = FAV_HI) -> list[dict]:
    out = []
    pick = favourite if rule != "longshot" else longshot
    for m in markets:
        ts = m["close_ts"] - minutes_before * 60
        q = quote_at(bars[m["ticker"]], ts)
        if q is None:
            continue
        bid, ask, last, i = q
        if ask - bid > MAX_SPREAD:
            continue
        p = pick(bid, ask)
        if p is None:
            continue
        side, price, implied = p
        if not (lo <= price <= hi):
            continue
        if rule == "maker":
            bid_price = round(price - 0.01, 4)
            later = bars[m["ticker"]][i + 1:]
            yes_level = bid_price if side == "yes" else 1.0 - bid_price
            through = any(b[3] is not None and ((side == "yes" and b[3] <= yes_level - 0.01) or (side == "no" and b[3] >= yes_level + 0.01))
                          for b in later)
            if not through:
                continue
            price, cost = bid_price, bid_price
            f = 0.0
        else:
            cost, f = price, fee(price)
        win = m["result"] == side
        out.append({"event": m["event"], "ticker": m["ticker"], "ts": ts, "side": side, "price": price, "implied": implied,
                    "win": win, "net": ((1.0 if win else 0.0) - cost - f) / cost})
    return out


def cluster_t(xs: list[float], groups: list) -> float:
    """t of the mean with standard errors clustered by group."""
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
    se = math.sqrt(var * g / (g - 1)) / n
    return mu / se


def summarize(ts: list[dict]) -> dict:
    if not ts:
        return {"n": 0}
    nets = [t["net"] for t in ts]
    events = sorted({t["event"] for t in ts})
    half = events[len(events) // 2] if events else None
    first = [t["net"] for t in ts if t["event"] < half]
    second = [t["net"] for t in ts if t["event"] >= half]
    per_event: dict = defaultdict(list)
    for t in ts:
        per_event[t["event"]].append(t["net"])
    ev_series = [statistics.fmean(v) for _, v in sorted(per_event.items())]
    buckets = {}
    for lo, hi in BUCKETS:
        sel = [t for t in ts if lo <= t["price"] < hi]
        if sel:
            buckets[f"{lo:.2f}-{hi:.2f}"] = {"n": len(sel), "implied": statistics.fmean(t["implied"] for t in sel),
                                               "hit": statistics.fmean(1.0 if t["win"] else 0.0 for t in sel),
                                               "net": statistics.fmean(t["net"] for t in sel)}
    return {"n": len(ts), "events": len(events), "net": statistics.fmean(nets),
            "t": cluster_t(nets, [t["event"] for t in ts]),
            "hit": statistics.fmean(1.0 if t["win"] else 0.0 for t in ts), "implied": statistics.fmean(t["implied"] for t in ts),
            "first_half": statistics.fmean(first) if first else None, "second_half": statistics.fmean(second) if second else None,
            "psr_events": S.psr(ev_series) if len(ev_series) > 2 else 0.0, "event_series": ev_series, "buckets": buckets}


def run(markets: list[dict], bars: dict[str, list]) -> dict:
    out = {"markets": len(markets), "events": len({m["event"] for m in markets}), "by_minute": {}}
    series_for_dsr = []
    for mins in DECISION_MINUTES:
        r = {"favourite": summarize(trades(markets, bars, mins, "favourite")),
             "longshot": summarize(trades(markets, bars, mins, "longshot", LONG_LO, LONG_HI)),
             "maker": summarize(trades(markets, bars, mins, "maker")),
             "fav_97_99": summarize(trades(markets, bars, mins, "favourite", 0.97, 0.99))}
        out["by_minute"][mins] = r
        series_for_dsr.extend(s for s in r.values() if s.get("n"))
    out["trials"] = 4 * len(DECISION_MINUTES)
    srs = [S.sharpe(s["event_series"]) for s in series_for_dsr if len(s["event_series"]) > 2]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    for mins in DECISION_MINUTES:
        f = out["by_minute"][mins]["favourite"]
        if f.get("n") and len(f["event_series"]) > 2:
            f["dsr_events"] = S.dsr(f["event_series"], out["trials"], var_sr)
    out["verdict"] = passes(out)
    return out


def passes(res: dict) -> tuple[str, str]:
    """Written before collecting: at both decision times, favourite net per
    dollar > 0 with cluster t >= 2.0 and positive in both halves;
    otherwise inconclusive; negative net at both is killed."""
    favs = [res["by_minute"][m]["favourite"] for m in DECISION_MINUTES]
    if any(not f.get("n") for f in favs):
        return "inconclusive", "no trades at one of the decision times"
    if all(f["net"] < 0 for f in favs):
        return "killed", "favourite net negative at both decision times"
    ok = all(f["net"] > 0 and f["t"] >= 2.0 and (f["first_half"] or 0) > 0 and (f["second_half"] or 0) > 0 for f in favs)
    if ok:
        low = min(f.get("dsr_events", 1.0) for f in favs)
        if low < 0.95:
            return "inconclusive", f"clears the bar but DSR {low:.2f} at {res['trials']} trials"
        return "alive", "clears the bar at both decision times"
    return "inconclusive", "; ".join(f"{m} min: net {f['net']*100:+.2f}% t {f['t']:+.1f}" for m, f in zip(DECISION_MINUTES, favs))


def render(res: dict) -> str:
    o = [f"Kalshi hourly BTC above/below: {res['markets']} traded markets in {res['events']} hours"]

    def line(s: dict) -> str:
        if not s.get("n"):
            return "no trades"
        halves = (f"halves {s['first_half']*100:+.2f}% / {s['second_half']*100:+.2f}%"
                  if s["first_half"] is not None and s["second_half"] is not None else "")
        return (f"n {s['n']:5d} in {s['events']:4d} hours: net {s['net']*100:+.2f}% per $ (cluster t {s['t']:+.1f}), "
                f"hit {s['hit']*100:.1f}% vs implied {s['implied']*100:.1f}%; {halves}"
                + (f"; DSR {s['dsr_events']:.2f}" if "dsr_events" in s else ""))
    for mins, r in res["by_minute"].items():
        o.append(f"  {mins} minutes before the print:")
        o.append(f"    favourite 0.85-0.97 at the ask, fee paid (registered): {line(r['favourite'])}")
        for k, s in r["favourite"].get("buckets", {}).items():
            o.append(f"      {k}: n {s['n']}, implied {s['implied']*100:.1f}%, hit {s['hit']*100:.1f}%, net {s['net']*100:+.2f}%")
        o.append(f"    longshot 0.03-0.15 at the ask (mirror):               {line(r['longshot'])}")
        o.append(f"    resting bid a cent under, filled through, no fee:      {line(r['maker'])}")
        o.append(f"    favourite 0.97-0.99 (sensitivity):                    {line(r['fav_97_99'])}")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    a = ap.parse_args(argv)
    markets, bars = load(a.state)
    if not markets:
        print("no settled markets with candles yet (python -m cryptobot.kalshi_binaries --state state)")
        return 1
    print(render(run(markets, bars)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
