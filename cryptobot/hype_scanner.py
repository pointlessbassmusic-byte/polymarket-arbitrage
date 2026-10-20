"""Hype scanner: online attention and froth for the coins the desk can trade.

Once an hour, from public endpoints that allow automated access:

  * CoinGecko trending searches (the top coins people are searching for)
  * CoinGecko meme-token markets, top 100 by 24h volume
  * StockTwits message rate (messages per hour over the latest 30) and
    the bullish / bearish tags, per symbol
  * Fear & Greed index (alternative.me), daily

Rows go to state/hype/<day>.jsonl. `froth()` scores each tracked coin
on its message rate and 24h volume against their own trailing medians
plus whether it is trending. It is a data build: no rule trades on it
until `meme-froth` mention-rate claims are pre-registered and pass with
90 days on file. Reddit, Wikipedia pageviews, Google Trends and GDELT
refused automated requests from the desk and are not used.

    python -m cryptobot.hype_scanner --state state --once
    python -m cryptobot.hype_scanner --state state --status
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import math
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx

from .data.nasdaq import append_jsonl, read_jsonl

logger = logging.getLogger(__name__)

UA = {"User-Agent": "cryptobot-research/0.1", "Accept": "application/json"}
CG = "https://api.coingecko.com/api/v3"
ST = "https://api.stocktwits.com/api/2/streams/symbol/{}.json"
FNG = "https://api.alternative.me/fng/"
# coin on the desk -> (StockTwits symbol, CoinGecko symbol)
TRACKED = {"DOGE": ("DOGE.X", "doge"), "SHIB": ("SHIB.X", "shib"), "PEPE": ("PEPE.X", "pepe"), "BONK": ("BONK.X", "bonk"),
           "WIF": ("WIF.X", "wif"), "FLOKI": ("FLOKI.X", "floki"), "BTC": ("BTC.X", "btc"), "ETH": ("ETH.X", "eth"),
           "SOL": ("SOL.X", "sol"), "XRP": ("XRP.X", "xrp"), "HYPE": ("HYPE.X", "hype"), "ZEC": ("ZEC.X", "zec"),
           "WLD": ("WLD.X", "wld"), "SUI": ("SUI.X", "sui")}
TRAIL_ROWS = 24 * 7


def _f(x) -> Optional[float]:
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def message_rate(messages: list[dict]) -> dict:
    """Messages per hour over the span of the latest page, and tag shares."""
    if len(messages) < 2:
        return {"n": len(messages), "rate_per_h": None, "bull": 0, "bear": 0}
    ts = sorted(_ts(m["created_at"]) for m in messages)
    span_h = max((ts[-1] - ts[0]) / 3600.0, 1 / 60)
    tags = [((m.get("entities") or {}).get("sentiment") or {}).get("basic") for m in messages]
    return {"n": len(messages), "rate_per_h": (len(messages) - 1) / span_h,
            "bull": sum(1 for t in tags if t == "Bullish"), "bear": sum(1 for t in tags if t == "Bearish")}


class HypeScanner:
    def __init__(self, state_dir: Path, tracked: Optional[dict] = None, interval_s: float = 3600.0,
                 client=None, now=None, sleep=None, pace_s: float = 1.5):
        self.state = Path(state_dir)
        self.tracked = tracked or TRACKED
        self.interval_s = float(interval_s)
        self._c = client or httpx.AsyncClient(timeout=30, headers=UA)
        self._owns = client is None
        self._now = now or time.time
        self._sleep = sleep or asyncio.sleep
        self.pace_s = pace_s
        self.errors = 0

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    def file_for(self, ts: float) -> Path:
        return self.state / "hype" / f"{dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()}.jsonl"

    async def _json(self, url: str, params: Optional[dict] = None):
        r = await self._c.get(url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"{url} -> {r.status_code}")
        return r.json()

    async def snapshot(self) -> dict:
        ts = self._now()
        row: dict = {"ts": round(ts, 1), "trending": [], "memes": [], "twits": {}, "fng": None, "errors": []}
        try:
            j = await self._json(f"{CG}/search/trending")
            row["trending"] = [{"symbol": (c["item"].get("symbol") or "").upper(), "rank": k + 1,
                                "mcap_rank": c["item"].get("market_cap_rank")} for k, c in enumerate(j.get("coins", []))]
        except Exception as exc:                          # noqa: BLE001 - one source down must not stop the rest
            row["errors"].append(f"trending: {exc}")
        await self._sleep(self.pace_s)
        try:
            j = await self._json(f"{CG}/coins/markets", {"vs_currency": "usd", "category": "meme-token",
                                                          "order": "volume_desc", "per_page": 100, "page": 1})
            row["memes"] = [{"symbol": (m.get("symbol") or "").upper(), "price": _f(m.get("current_price")),
                             "vol24": _f(m.get("total_volume")), "chg24": _f(m.get("price_change_percentage_24h")),
                             "mcap": _f(m.get("market_cap"))} for m in j]
        except Exception as exc:                          # noqa: BLE001
            row["errors"].append(f"memes: {exc}")
        for coin, (st_sym, _) in self.tracked.items():
            await self._sleep(self.pace_s)
            try:
                j = await self._json(ST.format(st_sym))
                row["twits"][coin] = message_rate(j.get("messages", []))
            except Exception as exc:                      # noqa: BLE001
                row["errors"].append(f"stocktwits {coin}: {exc}")
        try:
            j = await self._json(FNG, {"limit": 1})
            row["fng"] = int(j["data"][0]["value"])
        except Exception as exc:                          # noqa: BLE001
            row["errors"].append(f"fng: {exc}")
        self.errors += len(row["errors"])
        append_jsonl(self.file_for(ts), row)
        return row

    async def run_forever(self) -> None:
        logger.info("hype scanner: %d coins every %.0fs", len(self.tracked), self.interval_s)
        while True:
            t0 = self._now()
            try:
                await self.snapshot()
            except Exception as exc:                      # noqa: BLE001
                logger.warning("hype scanner: %s", exc)
            await self._sleep(max(60.0, self.interval_s - (self._now() - t0)))


# ----------------------------------------------------------------- reading

def rows(state_dir: Path, days: int = 8) -> list[dict]:
    root = Path(state_dir) / "hype"
    if not root.exists():
        return []
    out = []
    for p in sorted(root.glob("*.jsonl"))[-days:]:
        out.extend(read_jsonl(p))
    return out


def froth(rs: list[dict], tracked: Optional[dict] = None) -> dict[str, dict]:
    """Per tracked coin: message rate and 24h volume against their trailing
    medians (log ratio), trending rank, and a froth score = sum of the two
    ratios plus 0.5 if trending. Higher = more attention than usual."""
    tracked = tracked or TRACKED
    if not rs:
        return {}
    last, hist = rs[-1], rs[:-1][-TRAIL_ROWS:]
    trend = {t["symbol"]: t["rank"] for t in last.get("trending", [])}
    out = {}
    for coin, (_, cg) in tracked.items():
        tw = (last.get("twits") or {}).get(coin) or {}
        rate = tw.get("rate_per_h")
        past = [((r.get("twits") or {}).get(coin) or {}).get("rate_per_h") for r in hist]
        past = [x for x in past if x]
        vol = next((m["vol24"] for m in last.get("memes", []) if m["symbol"] == cg.upper()), None)
        pv = [next((m["vol24"] for m in r.get("memes", []) if m["symbol"] == cg.upper()), None) for r in hist]
        pv = [x for x in pv if x]
        r_rate = math.log(rate / statistics.median(past)) if rate and len(past) >= 6 else None
        r_vol = math.log(vol / statistics.median(pv)) if vol and len(pv) >= 6 else None
        score = (r_rate or 0.0) + (r_vol or 0.0) + (0.5 if coin in trend else 0.0)
        tags = tw.get("bull", 0) + tw.get("bear", 0)
        out[coin] = {"rate_per_h": rate, "rate_ratio": r_rate, "vol24": vol, "vol_ratio": r_vol,
                     "trending_rank": trend.get(coin), "bull_share": tw.get("bull", 0) / tags if tags else None,
                     "score": score}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["score"]))


def status(state_dir: Path) -> dict:
    rs = rows(state_dir)
    if not rs:
        return {}
    root = Path(state_dir) / "hype"
    files = sorted(root.glob("*.jsonl"))
    last = rs[-1]
    return {"days": len(files), "rows": sum(1 for p in files for _ in p.open()), "first": files[0].stem,
            "last_ts": last.get("ts"), "fng": last.get("fng"),
            "trending": [t["symbol"] for t in last.get("trending", [])][:7],
            "froth": {k: v for k, v in list(froth(rs).items())[:6]}, "errors_last": len(last.get("errors", []))}


def render(st: dict) -> str:
    if not st:
        return "no hype rows yet"
    o = [f"hype scanner: {st['rows']} snapshots over {st['days']} days; Fear & Greed {st.get('fng')}; "
         f"trending {', '.join(st['trending'])}"]
    for coin, f in st["froth"].items():
        rr = f"{f['rate_ratio']:+.2f}" if f["rate_ratio"] is not None else "  - "
        vr = f"{f['vol_ratio']:+.2f}" if f["vol_ratio"] is not None else "  - "
        o.append(f"  {coin:5s} score {f['score']:+.2f}  msgs/h {f['rate_per_h'] or 0:7.1f} (log vs 7d {rr})  "
                 f"vol24 log vs 7d {vr}  bull {f['bull_share'] if f['bull_share'] is not None else 0:.0%}"
                 + (f"  trending #{f['trending_rank']}" if f["trending_rank"] else ""))
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.once:
        async def one():
            s = HypeScanner(a.state)
            try:
                return await s.snapshot()
            finally:
                await s.close()
        row = asyncio.run(one())
        print(f"snapshot: {len(row['trending'])} trending, {len(row['memes'])} meme markets, "
              f"{len(row['twits'])} StockTwits streams, F&G {row['fng']}, errors {row['errors']}")
    print(render(status(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
