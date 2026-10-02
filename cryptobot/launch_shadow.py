"""Shadow test of a fresh-launch memecoin filter (the "FOMO desk" funnel).

Source: an X article (@savipww, 2026-09-23) describing a desk that scans
fresh launches every 15 minutes, kills most of them with hard numeric
thresholds, asks an LLM a few typed questions about the survivors, and
buys one. Its profit claims come with no trade log, and its thresholds
were "tuned over one week", so nothing about it is established. Its own
advice is the right one: run it in shadow for a week first.

This module does exactly that for the part public data can check. It
never trades. Every cycle it:

  1. pulls trending pools on solana / bsc / base from GeckoTerminal and
     keeps launches aged 15 minutes to 72 hours (the article's window);
  2. applies the article's HARD market-data thresholds verbatim (age,
     liquidity, 24h volume, market cap, 24h trades, no-sells trap);
  3. applies a stated, non-LLM stand-in for its "crowd" judgement:
     buys > sells in both the 30m and 1h windows, and the last hour is
     not more than half of the last six hours' volume (spread, not one
     spike);
  4. records the FIRST time each pool appears in each group: every fresh
     launch (the baseline), hard-pass, and hard+crowd pass, at the price
     it showed then;
  5. revisits recorded pools at +1h, +4h and +24h and stores the price.

What it cannot test: the holder checks (top wallet, top-10 share,
holder count), which the article reads from a logged-in FOMO session and
chain RPCs, and the LLM judgement itself. A filter only earns its place
if its group beats the baseline group observed over the same hours.

Run:  python -m cryptobot.launch_shadow --state launches.jsonl            (forever)
      python -m cryptobot.launch_shadow --state launches.jsonl --report   (results)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ("solana", "bsc", "base")
DURATIONS = ("5m", "1h", "6h", "24h")
PAGES = 3
CALL_PAUSE_S = 2.1                     # ~28 calls/min, under the free limit
HORIZONS_H = (1, 4, 24)

# The article's thresholds.py, HARD block, market-data part, verbatim.
HARD = {
    "min_age_minutes": 15,
    "max_age_hours": 72,
    "min_liquidity_usd": 12_000,
    "min_volume_h24": 40_000,
    "min_mcap_usd": 60_000,
    "max_mcap_usd": 8_000_000,
    "min_trades_h24": 150,
}

# Round trip assumed when reporting net returns: AMM fee each side plus
# price impact of a $50 ticket against the pool. Venue fees (FOMO's own)
# are not included and would come on top.
TICKET_USD = 50.0
AMM_FEE = 0.003


def _f(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def normalise(pool: dict, network: str, now_s: float) -> Optional[dict]:
    a = pool.get("attributes") or {}
    created = a.get("pool_created_at")
    price = _f(a.get("base_token_price_usd"))
    if not created or not price:
        return None
    age_min = (now_s - dt.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()) / 60
    tx = a.get("transactions") or {}
    vol = a.get("volume_usd") or {}

    def t(w, k):
        return int((tx.get(w) or {}).get(k) or 0)
    return {
        "net": network, "pool": a.get("address"), "name": a.get("name"),
        "price": price, "age_min": age_min,
        "liq": _f(a.get("reserve_in_usd")) or 0.0,
        "mcap": _f(a.get("market_cap_usd")) or _f(a.get("fdv_usd")) or 0.0,
        "vol_h24": _f(vol.get("h24")) or 0.0, "vol_h6": _f(vol.get("h6")) or 0.0,
        "vol_h1": _f(vol.get("h1")) or 0.0,
        "trades_h24": t("h24", "buys") + t("h24", "sells"),
        "buys_m30": t("m30", "buys"), "sells_m30": t("m30", "sells"),
        "buys_h1": t("h1", "buys"), "sells_h1": t("h1", "sells"),
    }


def in_window(p: dict) -> bool:
    return HARD["min_age_minutes"] <= p["age_min"] <= HARD["max_age_hours"] * 60


def hard_kill(p: dict) -> Optional[str]:
    """The article's free_kill + trade_kill, market-data part."""
    if not in_window(p):
        return "age"
    if p["liq"] < HARD["min_liquidity_usd"]:
        return "liquidity"
    if p["vol_h24"] < HARD["min_volume_h24"]:
        return "volume"
    if not HARD["min_mcap_usd"] <= p["mcap"] <= HARD["max_mcap_usd"]:
        return "mcap"
    if p["trades_h24"] < HARD["min_trades_h24"]:
        return "trades"
    if p["sells_h1"] == 0 and p["buys_h1"] > 20:
        return "no_sells"
    return None


def crowd_proxy(p: dict) -> bool:
    """Stand-in for the article's LLM 'crowd' answer. Stated, not tuned."""
    return (p["buys_m30"] > p["sells_m30"] and p["buys_h1"] > p["sells_h1"]
            and p["vol_h6"] > 0 and p["vol_h1"] <= 0.5 * p["vol_h6"])


def round_trip(liq: float) -> float:
    impact = TICKET_USD / liq if liq > 0 else 1.0
    return 2 * (AMM_FEE + impact)


# ------------------------------------------------------------------ state

class Ledger:
    """Append-only JSONL: one 'entry' per (pool, group), 'mark' rows for
    later prices. Reloads on start so a restart loses nothing."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[tuple, dict] = {}
        self.marks: dict[tuple, dict[int, Optional[float]]] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                key = (r["net"], r["pool"], r["group"])
                if r["kind"] == "entry":
                    self.entries.setdefault(key, r)
                elif r["kind"] == "mark":
                    self.marks.setdefault(key, {})[int(r["h"])] = r["price"]

    def _write(self, row: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def enter(self, p: dict, group: str, ts: float) -> bool:
        key = (p["net"], p["pool"], group)
        if key in self.entries:
            return False
        row = {"kind": "entry", "group": group, "ts": ts, **p}
        self.entries[key] = row
        self._write(row)
        return True

    def due(self, now_s: float) -> list[tuple]:
        """(key, horizon) pairs whose mark time has passed and is unrecorded."""
        out = []
        for key, e in self.entries.items():
            got = self.marks.get(key, {})
            for h in HORIZONS_H:
                if h not in got and now_s >= e["ts"] + h * 3600:
                    out.append((key, h))
        return out

    def mark(self, key: tuple, h: int, price: Optional[float]) -> None:
        self.marks.setdefault(key, {})[h] = price
        net, pool, group = key
        self._write({"kind": "mark", "net": net, "pool": pool, "group": group,
                     "h": h, "price": price, "ts": time.time()})


# ------------------------------------------------------------------ fetch

class Scanner:
    def __init__(self, ledger: Ledger, client: Optional[httpx.AsyncClient] = None):
        self.ledger = ledger
        self.c = client or httpx.AsyncClient(timeout=25, headers={"Accept": "application/json"})

    async def _get(self, path: str, params: dict | None = None) -> list:
        for attempt in range(3):
            try:
                r = await self.c.get(GT + path, params=params)
                if r.status_code == 429:
                    await asyncio.sleep(15 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json().get("data") or []
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                logger.warning("gt %s failed: %s", path, exc)
                await asyncio.sleep(3)
            finally:
                await asyncio.sleep(CALL_PAUSE_S)
        return []

    async def scan(self) -> dict:
        now_s = time.time()
        seen: dict[tuple, dict] = {}
        for net in NETWORKS:
            for dur in DURATIONS:
                for page in range(1, PAGES + 1):
                    for raw in await self._get(f"/networks/{net}/trending_pools",
                                               {"duration": dur, "page": page}):
                        p = normalise(raw, net, now_s)
                        if p and p["pool"]:
                            seen[(net, p["pool"])] = p
        stats = {"pools": len(seen), "fresh": 0, "hard": 0, "crowd": 0, "kills": {}}
        for p in seen.values():
            if not in_window(p):
                continue
            stats["fresh"] += 1
            self.ledger.enter(p, "fresh", now_s)
            k = hard_kill(p)
            if k:
                stats["kills"][k] = stats["kills"].get(k, 0) + 1
                continue
            stats["hard"] += 1
            self.ledger.enter(p, "hard", now_s)
            if crowd_proxy(p):
                stats["crowd"] += 1
                self.ledger.enter(p, "crowd", now_s)
        return stats

    async def revisit(self) -> int:
        """Price every due (pool, horizon) via the multi-pool endpoint."""
        due = self.ledger.due(time.time())
        by_net: dict[str, set] = {}
        for (net, pool, _), _h in due:
            by_net.setdefault(net, set()).add(pool)
        prices: dict[tuple, Optional[float]] = {}
        for net, pools in by_net.items():
            pools = sorted(pools)
            for i in range(0, len(pools), 30):
                chunk = pools[i:i + 30]
                rows = await self._get(f"/networks/{net}/pools/multi/{','.join(chunk)}")
                got = {(r.get("attributes") or {}).get("address"):
                       _f((r.get("attributes") or {}).get("base_token_price_usd")) for r in rows}
                for pool in chunk:
                    prices[(net, pool)] = got.get(pool)     # None = pool gone
        for (net, pool, group), h in due:
            self.ledger.mark((net, pool, group), h, prices.get((net, pool)))
        return len(due)

    async def close(self):
        await self.c.aclose()


# ----------------------------------------------------------------- report

def report(ledger: Ledger) -> str:
    out = []
    groups = ("fresh", "hard", "crowd")
    first = min((e["ts"] for e in ledger.entries.values()), default=None)
    if first is None:
        return "no observations yet"
    out.append(f"observing since {dt.datetime.utcfromtimestamp(first):%Y-%m-%d %H:%M} UTC; "
               f"net = price change - (2 x {100 * AMM_FEE:.1f}% AMM fee + ${TICKET_USD:.0f} impact "
               f"vs pool), venue fees excluded")
    out.append(f"{'group':6s} {'h':>3s} {'n':>4s} {'mean net':>9s} {'median':>8s} "
               f"{'>0':>5s} {'<=-50%':>7s} {'gone':>5s}")
    for g in groups:
        for h in HORIZONS_H:
            rets, gone = [], 0
            for key, e in ledger.entries.items():
                if key[2] != g:
                    continue
                m = ledger.marks.get(key, {})
                if h not in m:
                    continue
                if m[h] is None:
                    gone += 1
                    rets.append(-1.0)            # a pool that vanished is a total loss
                    continue
                rets.append(m[h] / e["price"] - 1 - round_trip(e["liq"]))
            if not rets:
                continue
            out.append(f"{g:6s} {h:>3d} {len(rets):>4d} {100 * statistics.mean(rets):>+8.1f}% "
                       f"{100 * statistics.median(rets):>+7.1f}% "
                       f"{sum(r > 0 for r in rets):>5d} {sum(r <= -0.5 for r in rets):>7d} {gone:>5d}")
    return "\n".join(out)


async def run(state: Path, cycle_s: int, cycles: Optional[int]) -> None:
    ledger = Ledger(state)
    sc = Scanner(ledger)
    n = 0
    try:
        while cycles is None or n < cycles:
            t0 = time.time()
            stats = await sc.scan()
            marked = await sc.revisit()
            logger.info("cycle %d: %s pools, %s fresh, %s hard, %s crowd, kills %s, %d marks",
                        n, stats["pools"], stats["fresh"], stats["hard"], stats["crowd"],
                        stats["kills"], marked)
            n += 1
            await asyncio.sleep(max(0, cycle_s - (time.time() - t0)))
    finally:
        await sc.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", type=Path, default=Path("launch_shadow.jsonl"))
    ap.add_argument("--cycle", type=int, default=900)
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.report:
        print(report(Ledger(args.state)))
        return 0
    asyncio.run(run(args.state, args.cycle, args.cycles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
