"""`token-unlock-short`: short a token into its cliff unlock, hedged with BTC.

Circulating supply = CoinGecko market cap / price, daily, the free API's
last 365 days. An unlock event is a day the supply rises >= 1% (events
within 20 days merged), unless the jump reverses within 5 days (a data
fix). The hedged short's return over day -20 to day +10 is
-(token return - BTC return), less 2 x 18 bp on the token leg,
2 x 4 bp on BTC and 10%/yr of funding on the short for 30 days.

    python -m cryptobot.unlock_study --scratch <dir> --fetch
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import statistics
import time
from pathlib import Path

import httpx

from .binary_tails_study import cluster_t

COINS = ("sui", "aptos", "arbitrum", "optimism", "worldcoin-wld", "starknet", "celestia", "sei-network", "pyth-network",
         "jupiter-exchange-solana", "zksync", "wormhole", "ethena", "ondo-finance", "immutable-x", "dydx-chain",
         "avalanche-2", "near", "hyperliquid", "layerzero", "eigenlayer", "movement", "altlayer", "manta-network",
         "pixels", "portal-2", "aevo-exchange", "space-id", "the-sandbox", "axie-infinity", "apecoin", "stepn",
         "flow", "zcash", "berachain-bera", "story-2", "kaito", "pudgy-penguins", "ethena", "eigenlayer")
KALSHI = {"sui", "worldcoin-wld", "near", "hyperliquid", "zcash"}
PRE, POST = 20, 10
THRESH = 0.01
COST = 2 * 0.0018 + 2 * 0.0004 + 0.10 * (PRE + POST) / 365


def fetch(scratch: Path, coins=COINS) -> int:
    d = scratch / "unlocks"
    d.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"})
    n = 0
    for coin in dict.fromkeys(list(coins) + ["bitcoin"]):
        p = d / f"{coin}.json"
        if p.exists():
            continue
        for a in range(6):
            r = c.get(f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart",
                      params={"vs_currency": "usd", "days": "365", "interval": "daily"})
            if r.status_code == 429:
                time.sleep(20 + 10 * a)
                continue
            break
        if r.status_code == 200:
            p.write_text(r.text)
            n += 1
        time.sleep(7)
    return n


def series(p: Path) -> dict[str, tuple[float, float]]:
    j = json.loads(p.read_text())
    caps = {int(t): v for t, v in j.get("market_caps", [])}
    out = {}
    for t, px in j.get("prices", []):
        cap = caps.get(int(t))
        if px and cap:
            out[dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date().isoformat()] = (float(px), float(cap) / float(px))
    return out


def events(s: dict[str, tuple[float, float]]) -> list[str]:
    days = sorted(s)
    out = []
    for i in range(1, len(days) - 5):
        s0, s1 = s[days[i - 1]][1], s[days[i]][1]
        if s0 <= 0 or s1 / s0 - 1 < THRESH:
            continue
        if s[days[i + 5]][1] < s1 * (1 - THRESH / 2):          # reverses: a data fix, not an unlock
            continue
        if out and (dt.date.fromisoformat(days[i]) - dt.date.fromisoformat(out[-1])).days < PRE:
            continue
        out.append(days[i])
    return out


def window(s, btc, day: str):
    d0 = (dt.date.fromisoformat(day) - dt.timedelta(days=PRE)).isoformat()
    d1 = (dt.date.fromisoformat(day) + dt.timedelta(days=POST)).isoformat()
    if d0 not in s or d1 not in s or d0 not in btc or d1 not in btc:
        return None
    tok = s[d1][0] / s[d0][0] - 1
    b = btc[d1][0] / btc[d0][0] - 1
    return -(tok - b) - COST, tok - b


def run(scratch: Path) -> dict:
    d = scratch / "unlocks"
    btc = series(d / "bitcoin.json")
    rows, placebo = [], []
    rng = random.Random(7)
    for coin in dict.fromkeys(COINS):
        p = d / f"{coin}.json"
        if not p.exists():
            continue
        s = series(p)
        evs = events(s)
        for e in evs:
            w = window(s, btc, e)
            if w:
                rows.append({"coin": coin, "day": e, "net": w[0], "rel": w[1], "jump": s[e][1] / s[sorted(s)[sorted(s).index(e) - 1]][1] - 1})
        # placebo: random days at least 30 days from any event
        days = sorted(s)
        far = [x for x in days if all(abs((dt.date.fromisoformat(x) - dt.date.fromisoformat(e)).days) > 30 for e in evs)]
        for x in rng.sample(far, min(len(far), max(3, len(evs)))):
            w = window(s, btc, x)
            if w:
                placebo.append({"coin": coin, "day": x, "net": w[0], "rel": w[1]})
    def summ(rs):
        if len(rs) < 5:
            return {"n": len(rs)}
        nets = [r["net"] for r in rs]
        ds = sorted(r["day"] for r in rs)
        mid = ds[len(ds) // 2]
        return {"n": len(rs), "coins": len({r["coin"] for r in rs}), "mean": statistics.fmean(nets), "median": statistics.median(nets),
                "t": cluster_t(nets, [r["day"][:7] for r in rs]), "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
                "h1": statistics.fmean([r["net"] for r in rs if r["day"] < mid] or [0.0]),
                "h2": statistics.fmean([r["net"] for r in rs if r["day"] >= mid] or [0.0]),
                "rel_mean": statistics.fmean(r["rel"] for r in rs)}
    res = {"events": summ(rows), "kalshi": summ([r for r in rows if r["coin"] in KALSHI]), "placebo": summ(placebo),
           "big": summ([r for r in rows if r["jump"] >= 0.03]), "rows": rows}
    e, pl = res["events"], res["placebo"]
    ok = (e.get("n", 0) >= 30 and e["mean"] >= 0.03 and e["t"] >= 2.5 and e["h1"] > 0 and e["h2"] > 0
          and pl.get("n", 0) >= 5 and e["mean"] - pl["mean"] >= 0.03)
    res["verdict"] = "candidate" if ok else ("killed" if e.get("n", 0) >= 5 and e["mean"] < 0 else "inconclusive")
    return res


def render(res: dict) -> str:
    o = [f"token unlocks (supply +{THRESH:.0%} in a day), BTC-hedged short from day -{PRE} to +{POST}, net of {COST:.2%}"]
    for k, label in (("events", "all events"), ("big", "jumps >= 3%"), ("kalshi", "Kalshi-listed tokens"), ("placebo", "placebo, random days")):
        s = res[k]
        if s.get("n", 0) < 5:
            o.append(f"  {label:22s} n {s.get('n', 0)}")
            continue
        o.append(f"  {label:22s} n {s['n']:3d} ({s['coins']} coins)  net {s['mean']:+.2%}  median {s['median']:+.2%}  t {s['t']:+.1f}  "
                 f"hit {s['hit']:.0%}  halves {s['h1']:+.2%}/{s['h2']:+.2%}  token vs BTC {s['rel_mean']:+.2%}")
    o.append(f"verdict: {res['verdict']}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch:
        print(f"fetched {fetch(a.scratch)} coins", flush=True)
    print(render(run(a.scratch)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
