"""`hype-mention-fade`, the forward read, written 2026-10-19 before any of
the scanner's data was read, exactly as registered:

  * coins: the tracked coins Kalshi lists as perps;
  * score per coin-hour: cryptobot.hype_scanner.froth on the rows up to
    that hour (log message rate vs its 7-day median + log 24h volume vs
    its 7-day median + 0.5 if trending);
  * event: a coin-hour whose score is in the top 10% of all coin-hour
    scores BEFORE it (expanding, at least 200 prior scores), at most one
    per coin per 72 hours;
  * outcome: short the coin against BTC (BTC against ETH) for 24 and 72
    hours from the event hour, Coinbase hourly closes fetched at read
    time, net of 18 bp and 10%/yr of funding;
  * verdict: CANDIDATE at >= +1% per event, t >= 2.5 (clustered by day),
    >= 30 events, both halves positive; KILLED if the mean is >= 0 at
    both horizons (no fade); otherwise inconclusive.

    python -m cryptobot.hype_forward --state state            # refuses before 2027-01-12
    python -m cryptobot.hype_forward --state state --force    # a status count, not the verdict
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

import httpx

from .binary_tails_study import cluster_t
from .hype_scanner import TRACKED, froth, rows as hype_rows

READ_AT = dt.date(2027, 1, 12)
COINS = ("DOGE", "SHIB", "BTC", "ETH", "SOL", "XRP", "HYPE", "ZEC", "WLD", "SUI")
TOP = 0.10
MIN_PRIOR = 200
GAP_H = 72
HORIZONS = (24, 72)
COST = 0.0018
FUNDING = 0.10


def scores(rs: list[dict], coins=COINS) -> list[tuple[float, str, float]]:
    """(hour ts, coin, score) for every row and coin, using only rows up to that hour."""
    tracked = {c: TRACKED[c] for c in coins if c in TRACKED}
    out = []
    for i in range(1, len(rs)):
        f = froth(rs[max(0, i - 24 * 7):i + 1], tracked)
        for c, v in f.items():
            if v.get("rate_ratio") is None and v.get("vol_ratio") is None:
                continue
            out.append((rs[i]["ts"], c, v["score"]))
    return out


def events(sc: list[tuple[float, str, float]]) -> list[tuple[float, str, float]]:
    prior: list[float] = []
    last: dict[str, float] = {}
    ev = []
    by_hour = defaultdict(list)
    for t, c, s in sc:
        by_hour[t].append((c, s))
    for t in sorted(by_hour):
        if len(prior) >= MIN_PRIOR:
            cut = sorted(prior)[int((1 - TOP) * len(prior))]
            for c, s in by_hour[t]:
                if s > cut and t - last.get(c, -1e18) >= GAP_H * 3600:     # strictly above the 90th percentile, so ties at the cut do not all fire
                    ev.append((t, c, s))
                    last[c] = t
        prior.extend(s for _, s in by_hour[t])
    return ev


def coinbase_hourly(product: str, start: float, end: float, client=None) -> dict[int, float]:
    c = client or httpx.Client(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"})
    out, t = {}, int(start // 3600 * 3600)
    while t < end:
        t2 = min(int(end), t + 300 * 3600)
        for a in range(5):
            try:
                r = c.get(f"https://api.exchange.coinbase.com/products/{product}/candles",
                          params={"granularity": 3600, "start": dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(),
                                  "end": dt.datetime.fromtimestamp(t2, dt.timezone.utc).isoformat()})
                if r.status_code == 404:
                    return {}
                if r.status_code == 200:
                    for k in r.json():
                        out[int(k[0])] = float(k[4])
                    break
            except httpx.TransportError:
                pass
            time.sleep(1 + a)
        t = t2
        time.sleep(0.35)
    return out


def outcomes(ev, price: Callable[[str], dict[int, float]]) -> dict[int, list[dict]]:
    cache: dict[str, dict[int, float]] = {}
    def px(coin):
        if coin not in cache:
            cache[coin] = price(coin)
        return cache[coin]
    res = {h: [] for h in HORIZONS}
    for t, c, s in ev:
        hedge = "ETH" if c == "BTC" else "BTC"
        a, b = px(c), px(hedge)
        t0 = int(t // 3600 * 3600)
        for h in HORIZONS:
            t1 = t0 + h * 3600
            if t0 in a and t1 in a and t0 in b and t1 in b:
                rel = (a[t1] / a[t0] - 1) - (b[t1] / b[t0] - 1)
                res[h].append({"day": dt.datetime.fromtimestamp(t0, dt.timezone.utc).date().isoformat(), "coin": c,
                               "net": -rel - COST - FUNDING * h / 8760})
    return res


def summarize(rows: list[dict]) -> dict:
    if len(rows) < 3:
        return {"n": len(rows)}
    nets = [r["net"] for r in rows]
    ds = sorted(r["day"] for r in rows)
    mid = ds[len(ds) // 2]
    return {"n": len(rows), "mean": statistics.fmean(nets), "t": cluster_t(nets, [r["day"] for r in rows]),
            "h1": statistics.fmean([r["net"] for r in rows if r["day"] < mid] or [0.0]),
            "h2": statistics.fmean([r["net"] for r in rows if r["day"] >= mid] or [0.0]),
            "coins": len({r["coin"] for r in rows})}


def verdict(st: dict[int, dict]) -> str:
    for h in HORIZONS:
        s = st[h]
        if s.get("n", 0) >= 30 and s["mean"] >= 0.01 and s["t"] >= 2.5 and s["h1"] > 0 and s["h2"] > 0:
            return f"candidate ({h} h)"
    if all(st[h].get("n", 0) >= 3 and st[h]["mean"] >= 0 for h in HORIZONS):
        return "killed (no fade at either horizon)"
    return "inconclusive"


def run(state: Path, price: Optional[Callable[[str], dict[int, float]]] = None) -> dict:
    rs = sorted(hype_rows(state, days=100000), key=lambda r: r["ts"])
    sc = scores(rs)
    ev = events(sc)
    if price is None and rs:
        lo, hi = rs[0]["ts"] - 3600, rs[-1]["ts"] + 80 * 3600
        price = lambda coin: coinbase_hourly(f"{coin}-USD", lo, hi)
    out = outcomes(ev, price) if ev else {h: [] for h in HORIZONS}
    st = {h: summarize(out[h]) for h in HORIZONS}
    return {"rows": len(rs), "first": rs[0]["ts"] if rs else None, "scores": len(sc), "events": len(ev),
            "by_horizon": st, "verdict": verdict(st)}


def render(res: dict, label: str) -> str:
    o = [f"hype-mention-fade, {label}: {res['rows']} hourly snapshots, {res['scores']} coin-hour scores, {res['events']} events"]
    for h, s in res["by_horizon"].items():
        if s.get("n", 0) < 3:
            o.append(f"  {h} h: n {s.get('n', 0)}")
            continue
        o.append(f"  {h} h: {s['n']} events ({s['coins']} coins), hedged short net {s['mean']:+.2%} (t {s['t']:+.1f}, halves {s['h1']:+.2%}/{s['h2']:+.2%})")
    o.append(f"verdict: {res['verdict']}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--force", action="store_true", help="count snapshots and events before the read date (no returns shown)")
    a = ap.parse_args(argv)
    today = dt.date.today()
    if today < READ_AT:
        if not a.force:
            print(f"hype-mention-fade is read on {READ_AT}; {(READ_AT - today).days} days to go. --force counts snapshots and events only.")
            return 0
        rs = sorted(hype_rows(a.state, days=100000), key=lambda r: r["ts"])
        ev = events(scores(rs))
        print(f"status only (before {READ_AT}): {len(rs)} hourly snapshots, {len(ev)} events so far; returns are not computed before the read date")
        return 0
    print(render(run(a.state), "VERDICT READ"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
