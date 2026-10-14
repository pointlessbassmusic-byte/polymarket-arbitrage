"""Stale-quote recorder: Coinbase spot and the Kalshi perp book, sampled
together about once a second, to measure how long Kalshi's quotes lag
spot and whether crossing a stale quote pays after the 4 bp taker fee.

Rows to <dir>/lag/<TICKER>.jsonl: [t, spot, kalshi bid, kalshi ask, bid size, ask size].

    python -m cryptobot.lag_recorder --dir <dir> --minutes 90
    python -m cryptobot.lag_recorder --dir <dir> --report
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from pathlib import Path

import httpx

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
COINBASE = "https://api.exchange.coinbase.com/products/{}/ticker"
PAIRS = {"KXDOGEPERP": "DOGE-USD", "KXKSHIBPERP": "SHIB-USD", "KXBTCPERP": "BTC-USD"}
UA = {"User-Agent": "cryptobot-research/0.1"}
TAKER_BP = 4.0


def _best(levels, side):
    """Kalshi margin book levels are [[price, size], ...]."""
    if not levels:
        return None, None
    rows = [(float(p), float(s)) for p, s in levels]
    p = max(rows)[0] if side == "bid" else min(rows)[0]
    return p, sum(s for q, s in rows if q == p)


async def sample(c: httpx.AsyncClient, ticker: str, product: str):
    k, s = await asyncio.gather(c.get(f"{KALSHI}/margin/markets/{ticker}/orderbook", params={"depth": 3}),
                                c.get(COINBASE.format(product)))
    if k.status_code != 200 or s.status_code != 200:
        return None
    ob = k.json().get("orderbook") or {}
    bid, bs = _best(ob.get("bids") or ob.get("bid") or [], "bid")
    ask, as_ = _best(ob.get("asks") or ob.get("ask") or [], "ask")
    spot = float(s.json()["price"])
    if bid is None or ask is None:
        return None
    return [round(time.time(), 3), spot, bid, ask, bs, as_]


async def record(d: Path, minutes: float, pairs=PAIRS) -> int:
    (d / "lag").mkdir(parents=True, exist_ok=True)
    files = {t: (d / "lag" / f"{t}.jsonl").open("a") for t in pairs}
    n, end = 0, time.time() + minutes * 60
    async with httpx.AsyncClient(timeout=10, headers=UA) as c:
        while time.time() < end:
            t0 = time.time()
            res = await asyncio.gather(*(sample(c, t, p) for t, p in pairs.items()), return_exceptions=True)
            for (t, _), r in zip(pairs.items(), res):
                if isinstance(r, list):
                    files[t].write(json.dumps(r) + "\n")
                    n += 1
            for f in files.values():
                f.flush()
            await asyncio.sleep(max(0.0, 1.0 - (time.time() - t0)))
    return n


def analyse(rows: list[list], horizons=(5, 15, 30, 60)) -> dict:
    """Fair perp price = spot x rolling median basis (the prior 10 minutes).
    A stale ask: ask below fair by more than the taker fee (buy); a stale
    bid: bid above fair by more than the fee (sell). Markout: the Kalshi
    mid h seconds later against the price paid."""
    rows = sorted(rows)
    if len(rows) < 300:
        return {"n": len(rows)}
    basis = [r[2] / r[1] * 0 + ((r[2] + r[3]) / 2) / r[1] for r in rows]
    out = {"n": len(rows), "minutes": (rows[-1][0] - rows[0][0]) / 60,
           "spread_bp": statistics.median((r[3] - r[2]) / ((r[2] + r[3]) / 2) * 1e4 for r in rows)}
    ts = [r[0] for r in rows]
    import bisect
    trades = {h: [] for h in horizons}
    gaps = []
    j = 0
    for i, r in enumerate(rows):
        while ts[j] < r[0] - 600:
            j += 1
        if i - j < 60:
            continue
        b = statistics.median(basis[j:i])
        fair = r[1] * b
        gaps.append(((r[2] + r[3]) / 2 / fair - 1) * 1e4)
        edge_buy = (fair - r[3]) / fair * 1e4 - TAKER_BP
        edge_sell = (r[2] - fair) / fair * 1e4 - TAKER_BP
        if edge_buy <= 0 and edge_sell <= 0:
            continue
        side, price = (1, r[3]) if edge_buy > 0 else (-1, r[2])
        for h in horizons:
            k = bisect.bisect_left(ts, r[0] + h)
            if k < len(rows):
                mid = (rows[k][2] + rows[k][3]) / 2
                trades[h].append(side * (mid - price) / price * 1e4 - TAKER_BP)
    out["mid_vs_fair_sd_bp"] = statistics.pstdev(gaps) if gaps else None
    out["signals"] = len(trades[horizons[0]])
    out["markout"] = {h: {"n": len(v), "net_bp": statistics.fmean(v) if v else None,
                          "t": statistics.fmean(v) / (statistics.pstdev(v) / math.sqrt(len(v))) if len(v) > 2 and statistics.pstdev(v) > 0 else 0.0}
                      for h, v in trades.items()}
    # lead-lag: correlation of 1-second spot changes with Kalshi mid changes at lags 0..10 s
    sp = [math.log(rows[i][1] / rows[i - 1][1]) for i in range(1, len(rows))]
    km = [math.log(((rows[i][2] + rows[i][3]) / 2) / ((rows[i - 1][2] + rows[i - 1][3]) / 2)) for i in range(1, len(rows))]
    def corr(a, b):
        if len(a) < 30 or statistics.pstdev(a) == 0 or statistics.pstdev(b) == 0:
            return 0.0
        ma, mb = statistics.fmean(a), statistics.fmean(b)
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a) / (statistics.pstdev(a) * statistics.pstdev(b))
    out["lag_corr"] = {lag: corr(sp[:len(sp) - lag], km[lag:]) for lag in range(0, 11)}
    return out


def report(d: Path) -> str:
    o = ["stale-quote recorder: Coinbase spot vs Kalshi perp book; fair = spot x rolling 10-minute median basis; taker fee 4 bp"]
    for p in sorted((d / "lag").glob("*.jsonl")):
        rows = [json.loads(l) for l in p.open() if l.strip()]
        a = analyse(rows)
        if a.get("n", 0) < 300:
            o.append(f"  {p.stem}: {a.get('n', 0)} samples, too few")
            continue
        lc = a["lag_corr"]
        best = max(lc, key=lambda k: lc[k])
        o.append(f"  {p.stem}: {a['n']} samples over {a['minutes']:.0f} min; median spread {a['spread_bp']:.1f} bp; Kalshi mid vs fair sd {a['mid_vs_fair_sd_bp']:.1f} bp; "
                 f"stale quotes beyond the fee {a['signals']} times")
        o.append("    crossing them, net of 4 bp, Kalshi mid after " + ", ".join(
            f"{h}s {v['net_bp']:+.1f} bp (t {v['t']:+.1f}, n {v['n']})" if v["net_bp"] is not None else f"{h}s n 0" for h, v in a["markout"].items()))
        o.append("    corr(spot change, Kalshi mid change k s later): " + " ".join(f"{k}s {v:+.2f}" for k, v in lc.items()) + f"; peak at {best}s")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path("."))
    ap.add_argument("--minutes", type=float, default=90)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    if not a.report:
        print(f"recorded {asyncio.run(record(a.dir, a.minutes))} samples", flush=True)
    print(report(a.dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
