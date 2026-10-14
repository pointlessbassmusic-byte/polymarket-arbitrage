"""Your Polymarket record, read from the public data API by wallet address,
and what the opposite side of every bet would have earned.

Polymarket positions are public by proxy-wallet address (the 0x... in a
profile URL, polymarket.com/profile/0x...). No key or login is used or
needed; nothing here can trade.

For every closed (resolved or sold) position: entry price, dollars
staked, realised P&L, the market's category (from its slug: crypto
up/down, crypto price, sports, politics, ...), and the result. Then:

  * where the losses came from: P&L by entry-price bucket, category,
    side (first outcome vs second), stake size, month;
  * the inverse: the same bet on the OTHER outcome at the same moment.
    Its price is about 1 - entry + spread, so the inverse is charged a
    spread of 0, 1 and 2 cents. A held-to-resolution position's
    inverse wins exactly when the original lost. Positions sold before
    resolution are inverted as a short of the same token over the same
    window, which on a binary is the same as holding the other outcome;
  * which rule a stranger could run without your picks: the buckets
    where your losses concentrate, stated as a rule (e.g. "sell crypto
    up/down tokens priced under 20 cents"), to be tested on every
    market of that type, not only the ones you chose.

    python -m cryptobot.polymarket_history 0xYOURPROXYWALLET [--out file.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import httpx

DATA = "https://data-api.polymarket.com"
UA = {"User-Agent": "cryptobot-research/0.1", "Accept": "application/json"}
BUCKETS = ((0.0, 0.10), (0.10, 0.25), (0.25, 0.45), (0.45, 0.55), (0.55, 0.75), (0.75, 0.90), (0.90, 1.0001))
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


def category(slug: str, title: str = "") -> str:
    s = (slug or "").lower() + " " + (title or "").lower()
    if any(k in s for k in ("updown", "up-or-down", "up or down")):
        return "crypto up/down"
    if any(k in s for k in ("bitcoin", "btc", "ethereum", "eth-", "solana", "xrp", "doge", "crypto")):
        return "crypto price"
    if any(k in s for k in ("nfl", "nba", "mlb", "nhl", "epl", "uefa", "ufc", "atp", "wta", "itf", "cfb", "cbb", "fifa", "vs-", " vs ", "match", "game")):
        return "sports"
    if any(k in s for k in ("election", "president", "senate", "house", "trump", "biden", "governor", "mayor", "primary", "vote")):
        return "politics"
    if any(k in s for k in ("fed", "rate", "cpi", "inflation", "gdp", "jobs", "unemployment", "recession")):
        return "macro"
    return "other"


def bucket(p: float) -> str:
    for lo, hi in BUCKETS:
        if lo <= p < hi:
            return f"{lo:.2f}-{min(hi, 1):.2f}"
    return "?"


class History:
    def __init__(self, address: str, client=None, pace_s: float = 0.25):
        if not ADDR.match(address or ""):
            raise ValueError("expected a 0x... proxy-wallet address (40 hex characters)")
        self.addr = address
        self.c = client or httpx.Client(timeout=30, headers=UA)
        self.pace_s = pace_s

    def _pages(self, path: str, params: dict, limit: int = 500, max_rows: int = 200_000) -> list[dict]:
        out, offset = [], 0
        while offset < max_rows:
            q = dict(params, user=self.addr, limit=limit, offset=offset)
            for attempt in range(6):
                r = self.c.get(DATA + path, params=q)
                if r.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            if r.status_code != 200:
                break
            rows = r.json()
            if not isinstance(rows, list) or not rows:
                break
            out.extend(rows)
            if len(rows) < limit:
                break
            offset += limit
            time.sleep(self.pace_s)
        return out

    def fetch(self) -> dict:
        return {"closed": self._pages("/closed-positions", {}, limit=50),
                "open": self._pages("/positions", {"sizeThreshold": 0}, limit=500),
                "activity": self._pages("/activity", {}, limit=500)}


def positions(raw: dict) -> list[dict]:
    """One row per closed position (and open ones marked to market)."""
    rows = []
    first_buy: dict[str, float] = {}
    for a in raw.get("activity", []):
        if a.get("type") == "TRADE" and a.get("side") == "BUY":
            k = a.get("asset")
            first_buy[k] = min(first_buy.get(k, 1e18), float(a.get("timestamp") or 1e18))
    for kind in ("closed", "open"):
        for p in raw.get(kind, []):
            avg = float(p.get("avgPrice") or 0)
            bought = float(p.get("totalBought") or 0)          # shares
            stake = avg * bought
            if stake <= 0 or not (0 < avg < 1):
                continue
            pnl = float(p.get("realizedPnl") or 0) + (float(p.get("cashPnl") or 0) if kind == "open" else 0.0)
            cur = p.get("curPrice")
            resolved = cur is not None and float(cur) in (0.0, 1.0)
            ts = first_buy.get(p.get("asset"))
            rows.append({"kind": kind, "title": p.get("title"), "slug": p.get("slug") or p.get("eventSlug"),
                         "category": category(p.get("slug") or p.get("eventSlug") or "", p.get("title") or ""),
                         "outcome_index": p.get("outcomeIndex"), "entry": avg, "stake": stake, "pnl": pnl,
                         "ret": pnl / stake, "resolved": resolved, "won": (float(cur) == 1.0) if resolved else None,
                         "month": dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m") if ts else "?"})
    return rows


def inverse_ret(r: dict, spread: float) -> float:
    """Return per dollar of the opposite bet at the same moment.

    The original paid `entry` for a token that ended worth entry*(1+ret).
    The other outcome cost 1 - entry + spread and ended worth 1 - entry*(1+ret)."""
    p = r["entry"]
    end_value = p * (1 + r["ret"])                  # per share of the original token
    cost = 1 - p + spread
    if cost <= 0:
        return 0.0
    return ((1 - end_value) - cost) / cost


def summarize(rows: list[dict], key, spreads=(0.0, 0.01, 0.02)) -> dict:
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    out = {}
    for k, rs in sorted(g.items(), key=lambda kv: -sum(x["stake"] for x in kv[1])):
        stake = sum(x["stake"] for x in rs)
        pnl = sum(x["pnl"] for x in rs)
        inv = {}
        for s in spreads:
            # the inverse sized at the same dollars as the original
            inv[s] = sum(x["stake"] * inverse_ret(x, s) for x in rs)
        rets = [x["ret"] for x in rs]
        out[k] = {"n": len(rs), "stake": stake, "pnl": pnl, "ret": pnl / stake if stake else 0.0,
                  "hit": statistics.fmean(1.0 if x["pnl"] > 0 else 0.0 for x in rs),
                  "t": (statistics.fmean(rets) / (statistics.pstdev(rets) / len(rets) ** 0.5)) if len(rets) > 2 and statistics.pstdev(rets) > 0 else 0.0,
                  "inverse_pnl": inv}
    return out


def analyse(raw: dict) -> dict:
    rows = positions(raw)
    res = {"positions": len(rows), "closed": sum(1 for r in rows if r["kind"] == "closed"),
           "open": sum(1 for r in rows if r["kind"] == "open")}
    if not rows:
        return res
    res["total"] = summarize(rows, lambda r: "all")["all"]
    res["by_price"] = summarize(rows, lambda r: bucket(r["entry"]))
    res["by_category"] = summarize(rows, lambda r: r["category"])
    res["by_cat_price"] = summarize(rows, lambda r: f"{r['category']} @ {bucket(r['entry'])}")
    res["by_month"] = summarize(rows, lambda r: r["month"])
    q = sorted(r["stake"] for r in rows)
    big = q[int(0.8 * len(q))] if q else 0
    res["by_size"] = summarize(rows, lambda r: "top 20% by stake" if r["stake"] >= big else "other 80%")
    # candidate rules: category x price cells with >= 20 positions, losses, and a positive inverse at 2 cents
    rules = []
    for k, v in res["by_cat_price"].items():
        if v["n"] >= 20 and v["pnl"] < 0 and v["inverse_pnl"][0.02] > 0:
            rules.append({"cell": k, "n": v["n"], "your_ret": v["ret"], "your_t": v["t"], "inverse_pnl_2c": v["inverse_pnl"][0.02],
                          "stake": v["stake"]})
    res["rules"] = sorted(rules, key=lambda x: x["your_ret"])
    return res


def render(res: dict) -> str:
    if not res.get("positions"):
        return "no positions found for this address"
    t = res["total"]
    o = [f"Polymarket record: {res['closed']} closed and {res['open']} open positions; staked ${t['stake']:,.0f}, "
         f"P&L ${t['pnl']:+,.0f} ({t['ret']:+.1%} of stake), {t['hit']:.0%} of positions profitable",
         f"  the opposite of every bet, same dollars: ${t['inverse_pnl'][0.0]:+,.0f} at zero spread, "
         f"${t['inverse_pnl'][0.01]:+,.0f} at 1 cent, ${t['inverse_pnl'][0.02]:+,.0f} at 2 cents"]
    def table(title, d, limit=12):
        o.append(f"  {title}")
        o.append(f"    {'':28s} {'n':>5s} {'staked':>10s} {'P&L':>10s} {'ret':>7s} {'t':>5s} {'hit':>4s} {'inverse @0c':>12s} {'@2c':>10s}")
        for k, v in list(d.items())[:limit]:
            o.append(f"    {k[:28]:28s} {v['n']:5d} {v['stake']:10,.0f} {v['pnl']:+10,.0f} {v['ret']:+7.1%} {v['t']:+5.1f} {v['hit']:4.0%} "
                     f"{v['inverse_pnl'][0.0]:+12,.0f} {v['inverse_pnl'][0.02]:+10,.0f}")
    table("by entry price", dict(sorted(res["by_price"].items())))
    table("by category", res["by_category"])
    table("by stake size", res["by_size"])
    table("by month", dict(sorted(res["by_month"].items())), limit=24)
    o.append("  cells where you lost and the opposite side would have made money even after a 2-cent spread (>= 20 positions):")
    for r in res["rules"][:10]:
        o.append(f"    {r['cell']}: {r['n']} positions, your return {r['your_ret']:+.1%} (t {r['your_t']:+.1f}), inverse ${r['inverse_pnl_2c']:+,.0f}")
    if not res["rules"]:
        o.append("    none")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    raw = History(a.address).fetch()
    res = analyse(raw)
    print(render(res))
    if a.out:
        a.out.write_text(json.dumps({"raw": raw, "result": res}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
