"""Your Polymarket US record (polymarket.us, the CFTC-regulated exchange),
read from its authenticated Portfolio API, and what the opposite side of
every bet would have earned.

Needs an API key from polymarket.us/developer in the environment:
POLYMARKET_US_KEY_ID and POLYMARKET_US_SECRET (desk.sh polyus stores
them in .env without echoing). Only GET requests are made: the
activities and positions endpoints. Nothing here places or cancels
orders. Polymarket US keys are not scoped, so the key itself can
trade; keep it in .env only and revoke it at polymarket.us/developer
when the analysis is done.

Per market: dollars staked (opening cost basis), realised P&L (closing
trades plus settlement), the average price paid for the side held,
long or short, the share of fills where you were the maker (the API's
isAggressor flag), category and month. Then the same breakdowns and
inverse as cryptobot.polymarket_history, plus maker vs taker.

    python -m cryptobot.polymarket_us_history [--out record.json]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import httpx

from .polymarket_history import bucket, category, render as render_wallet, summarize

API = "https://api.polymarket.us"
UA = {"User-Agent": "cryptobot-research/0.1", "Accept": "application/json"}


def _amt(x) -> Optional[float]:
    if isinstance(x, dict):
        x = x.get("value")
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


class Client:
    def __init__(self, key_id: str, secret_b64: str, client=None):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        self.key_id = key_id.strip()
        self._sk = ed25519.Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret_b64.strip())[:32])
        self.c = client or httpx.Client(timeout=30, headers=UA)

    def _headers(self, method: str, path: str) -> dict:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(self._sk.sign(f"{ts}{method}{path}".encode())).decode()
        return {"X-PM-Access-Key": self.key_id, "X-PM-Timestamp": ts, "X-PM-Signature": sig}

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        for attempt in range(6):
            r = self.c.get(API + path, params=params, headers=self._headers("GET", path))
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 401:
                raise PermissionError("401 from Polymarket US: check POLYMARKET_US_KEY_ID / POLYMARKET_US_SECRET "
                                      "(same sign-in method as the app; the secret is shown once)")
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"{path}: throttled")

    def pages(self, path: str, key: str, params: Optional[dict] = None, limit: int = 100) -> list[dict]:
        out, cursor = [], None
        for _ in range(10_000):
            q = dict(params or {}, limit=limit)
            if cursor:
                q["cursor"] = cursor
            j = self.get(path, q)
            out.extend(j.get(key) or [])
            cursor = j.get("nextCursor")
            if j.get("eof") or not cursor or not j.get(key):
                break
            time.sleep(0.2)
        return out

    def fetch(self) -> dict:
        return {"activities": self.pages("/v1/portfolio/activities", "activities"),
                "positions": self.pages("/v1/portfolio/positions", "positions")}


def markets(raw: dict) -> list[dict]:
    """One row per market from trades and settlements."""
    m: dict[str, dict] = defaultdict(lambda: {"stake": 0.0, "qty_open": 0.0, "pnl": 0.0, "fills": 0, "maker": 0,
                                              "first": None, "title": "", "side": None, "resolved": False, "kind": "closed"})
    for a in raw.get("activities", []):
        t = a.get("type")
        if t == "ACTIVITY_TYPE_TRADE" and a.get("trade"):
            tr = a["trade"]
            if tr.get("state") in ("TRADE_STATE_BUSTED", "TRADE_STATE_REJECTED"):
                continue
            r = m[tr.get("marketSlug") or "?"]
            q = float(tr.get("qtyDecimal") or tr.get("qty") or 0)
            cb, rp = _amt(tr.get("costBasis")), _amt(tr.get("realizedPnl"))
            r["fills"] += 1
            r["maker"] += 0 if tr.get("isAggressor") else 1
            if rp is not None and rp != 0:
                r["pnl"] += rp                      # a closing fill
            elif cb is not None and cb > 0:
                r["stake"] += cb                    # an opening fill
                r["qty_open"] += q
            ts = tr.get("createTime")
            if ts and (r["first"] is None or ts < r["first"]):
                r["first"] = ts
        elif t == "ACTIVITY_TYPE_POSITION_RESOLUTION" and a.get("positionResolution"):
            pr = a["positionResolution"]
            r = m[pr.get("marketSlug") or "?"]
            b, af = pr.get("beforePosition") or {}, pr.get("afterPosition") or {}
            rb, ra = _amt(b.get("realized")) or 0.0, _amt(af.get("realized")) or 0.0
            r["pnl"] += ra - rb
            r["resolved"] = True
            r["side"] = {"POSITION_RESOLUTION_SIDE_LONG": "long", "POSITION_RESOLUTION_SIDE_SHORT": "short"}.get(pr.get("side"), r["side"])
            md = b.get("marketMetadata") or af.get("marketMetadata") or {}
            r["title"] = md.get("title") or r["title"]
    for p in raw.get("positions", []):
        slug = (p.get("marketMetadata") or {}).get("slug") or p.get("marketSlug")
        if slug in m and not m[slug]["resolved"]:
            m[slug]["kind"] = "open"
            m[slug]["pnl"] += _amt(p.get("cashValue")) or 0.0       # unrealised, marked to market
            m[slug]["title"] = (p.get("marketMetadata") or {}).get("title") or m[slug]["title"]
    rows = []
    for slug, r in m.items():
        if r["stake"] <= 0 or r["qty_open"] <= 0:
            continue
        entry = r["stake"] / r["qty_open"]           # price paid per contract for the side held
        if not 0 < entry < 1:
            continue
        rows.append({"kind": r["kind"], "slug": slug, "title": r["title"], "category": category(slug, r["title"]),
                     "entry": entry, "stake": r["stake"], "pnl": r["pnl"], "ret": r["pnl"] / r["stake"],
                     "resolved": r["resolved"], "side": r["side"] or "?",
                     "maker_share": r["maker"] / r["fills"] if r["fills"] else 0.0,
                     "month": r["first"][:7] if r["first"] else "?"})
    return rows


def analyse(raw: dict) -> dict:
    rows = markets(raw)
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
    big = q[int(0.8 * len(q))]
    res["by_size"] = summarize(rows, lambda r: "top 20% by stake" if r["stake"] >= big else "other 80%")
    res["by_maker"] = summarize(rows, lambda r: "mostly maker fills" if r["maker_share"] >= 0.5 else "mostly taker fills")
    res["by_side"] = summarize(rows, lambda r: r["side"])
    rules = []
    for k, v in res["by_cat_price"].items():
        if v["n"] >= 20 and v["pnl"] < 0 and v["inverse_pnl"][0.02] > 0:
            rules.append({"cell": k, "n": v["n"], "your_ret": v["ret"], "your_t": v["t"], "inverse_pnl_2c": v["inverse_pnl"][0.02], "stake": v["stake"]})
    res["rules"] = sorted(rules, key=lambda x: x["your_ret"])
    return res


def render(res: dict) -> str:
    out = render_wallet(res).replace("Polymarket record:", "Polymarket US record:")
    extra = []
    for title, key in (("by maker vs taker (majority of a market's fills)", "by_maker"), ("by side held", "by_side")):
        d = res.get(key) or {}
        if d:
            extra.append(f"  {title}")
            for k, v in d.items():
                extra.append(f"    {k[:28]:28s} {v['n']:5d} {v['stake']:10,.0f} {v['pnl']:+10,.0f} {v['ret']:+7.1%} {v['t']:+5.1f} {v['hit']:4.0%} "
                             f"{v['inverse_pnl'][0.0]:+12,.0f} {v['inverse_pnl'][0.02]:+10,.0f}")
    return out + ("\n" + "\n".join(extra) if extra else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None, help="also save the raw activity and the analysis as JSON")
    a = ap.parse_args(argv)
    kid, sec = os.environ.get("POLYMARKET_US_KEY_ID"), os.environ.get("POLYMARKET_US_SECRET")
    if not kid or not sec:
        print("set POLYMARKET_US_KEY_ID and POLYMARKET_US_SECRET (./desk.sh polyus stores them in .env)")
        return 1
    raw = Client(kid, sec).fetch()
    res = analyse(raw)
    print(render(res))
    if a.out:
        a.out.write_text(json.dumps({"raw": raw, "result": res}, default=str))
        print(f"saved {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
