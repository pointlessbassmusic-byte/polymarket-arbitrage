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
# A mark taken this far past its horizon (e.g. the logger was down) is
# recorded as missed rather than passed off as the horizon's price.
LATE_FACTOR = 1.5

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
    """Fees plus price impact, capped: a ticket into an empty pool loses
    the ticket, it cannot lose a million percent of it."""
    impact = min(1.0, TICKET_USD / liq) if liq > 0 else 1.0
    return min(1.0, 2 * (AMM_FEE + impact))


def net_return(entry_price: float, exit_price: Optional[float], liq: float) -> float:
    """Price change minus round trip, floored at -100%. A vanished pool is -100%."""
    if exit_price is None:
        return -1.0
    return max(-1.0, exit_price / entry_price - 1 - round_trip(liq))


# ------------------------------------------------------------------ state

class Ledger:
    """Append-only JSONL: one 'entry' per (pool, group), 'mark' rows for
    later prices. Reloads on start so a restart loses nothing."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[tuple, dict] = {}
        self.marks: dict[tuple, dict[int, Optional[float]]] = {}
        self.missed: dict[tuple, set] = {}
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
                    late = r.get("late")
                    if late is None and key in self.entries:
                        late = r["ts"] > self.entries[key]["ts"] + int(r["h"]) * 3600 * LATE_FACTOR
                    if late:
                        self.missed.setdefault(key, set()).add(int(r["h"]))
                        self.marks.setdefault(key, {}).setdefault(int(r["h"]), None)
                        continue
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

    def mark(self, key: tuple, h: int, price: Optional[float],
             at: Optional[float] = None) -> None:
        at = time.time() if at is None else at
        late = at > self.entries[key]["ts"] + h * 3600 * LATE_FACTOR
        self.marks.setdefault(key, {})[h] = None if late else price
        if late:
            self.missed.setdefault(key, set()).add(h)
        net, pool, group = key
        self._write({"kind": "mark", "net": net, "pool": pool, "group": group,
                     "h": h, "price": price, "ts": at, "late": late})


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


# ------------------------------------------------------------ exit replay

EXIT_GRID = [(tp, sl, h) for tp in (0.2, 0.5, 1.0, None)
             for sl in (0.15, 0.30, None) for h in (1, 4, 24)]


def exit_trade(candles, entry_ts: float, entry_price: float, liq: float,
               tp: Optional[float], sl: Optional[float], max_h: float) -> Optional[float]:
    """Replay one long from `entry_price` through 5-minute candles.

    Stop is checked before target in each candle (the conservative order
    when a candle touches both). A candle that OPENS through a barrier
    fills at its open: memecoins gap, and assuming a clean fill at the
    stop would flatter every stop rule. With no barrier hit, the trade
    exits at the last close at or before the time limit. Returns net of
    the round trip, floored at -100%, or None with no candles to replay.
    """
    stop = entry_price * (1 - sl) if sl is not None else None
    target = entry_price * (1 + tp) if tp is not None else None
    deadline = entry_ts + max_h * 3600
    last = None
    for c in candles:
        if c.ts < entry_ts:
            continue
        if c.ts > deadline:
            break
        if stop is not None and c.open <= stop:
            return max(-1.0, c.open / entry_price - 1 - round_trip(liq))
        if stop is not None and c.low <= stop:
            return max(-1.0, -sl - round_trip(liq))
        if target is not None and c.open >= target:
            return c.open / entry_price - 1 - round_trip(liq)
        if target is not None and c.high >= target:
            return tp - round_trip(liq)
        last = c.close
    if last is None:
        return None
    return max(-1.0, last / entry_price - 1 - round_trip(liq))


def exit_scaled(candles, entry_ts: float, entry_price: float, liq: float, *,
                take_mult: float, take_frac: float, sl: Optional[float],
                trail: Optional[float], max_h: float) -> Optional[float]:
    """Scale-out exit (the "moonbag" rule): sell `take_frac` of the position
    at `take_mult` x entry; the rest rides until the time limit, or until
    it falls `trail` from its peak. Before the take, an optional stop `sl`
    closes everything. Gaps fill at the candle open, stops before targets
    within a candle, as in exit_trade. Returns net of one round trip on
    the whole position, floored at -100%."""
    stop = entry_price * (1 - sl) if sl is not None else None
    target = entry_price * take_mult
    deadline = entry_ts + max_h * 3600
    taken = 0.0              # fraction already sold
    proceeds = 0.0           # value received per unit of entry notional
    peak = None
    last = None
    for c in candles:
        if c.ts < entry_ts:
            continue
        if c.ts > deadline:
            break
        rest = 1.0 - taken
        if taken == 0.0:
            if stop is not None and c.open <= stop:
                return max(-1.0, c.open / entry_price - 1 - round_trip(liq))
            if stop is not None and c.low <= stop:
                return max(-1.0, -sl - round_trip(liq))
            if c.high >= target:
                px = max(c.open, target)
                proceeds += take_frac * px / entry_price
                taken = take_frac
                if taken >= 1.0:
                    return proceeds - 1 - round_trip(liq)
                peak = c.high
                last = c.close
                continue
        else:
            if trail is not None:
                floor_px = peak * (1 - trail)
                if c.open <= floor_px:
                    return proceeds + rest * c.open / entry_price - 1 - round_trip(liq)
                if c.low <= floor_px:
                    return proceeds + rest * floor_px / entry_price - 1 - round_trip(liq)
            peak = max(peak, c.high)
        last = c.close
    if last is None:
        return None
    rest = 1.0 - taken
    return max(-1.0, proceeds + rest * last / entry_price - 1 - round_trip(liq))


SCALED_GRID = [dict(take_mult=m, take_frac=f, sl=sl, trail=tr, max_h=h)
               for m in (2.0, 3.0) for f in (0.5, 0.6, 1.0) for sl in (0.30, None)
               for tr in (None, 0.5) for h in (4, 24)
               if not (f == 1.0 and tr is not None)]


def scaled_name(r: dict) -> str:
    return (f"sell {int(r['take_frac'] * 100)}% at {r['take_mult']:.0f}x, "
            f"stop {('-' + str(int(r['sl'] * 100)) + '%') if r['sl'] else 'none'}, "
            f"bag {'trail ' + str(int(r['trail'] * 100)) + '%' if r['trail'] else 'held'}, "
            f"{r['max_h']}h")


def scaled_results(ledger: "Ledger", candles: dict, group: str, rule: dict,
                   day: Optional[str] = None) -> list:
    out = []
    for key, e in ledger.entries.items():
        if key[2] != group:
            continue
        if day and dt.datetime.utcfromtimestamp(e["ts"]).strftime("%Y-%m-%d") != day:
            continue
        cs = candles.get((key[0], key[1], int(e["ts"])))
        if not cs:
            continue
        r = exit_scaled(cs, e["ts"], e["price"], e["liq"], **rule)
        if r is not None:
            out.append(r)
    return out


def scaled_report(ledger: "Ledger", candles: dict) -> str:
    """Moonbag rules vs all-out rules: pick on day one by mean, test on the rest."""
    days = sorted({dt.datetime.utcfromtimestamp(e["ts"]).strftime("%Y-%m-%d")
                   for k, e in ledger.entries.items()
                   if (k[0], k[1], int(e["ts"])) in candles})
    if len(days) < 2:
        return "need two days of entries"
    pick, tests = days[0], days[1:]
    out = [f"scale-out ('moonbag') exits, {len(SCALED_GRID)} rules; pick on {pick} by mean, "
           f"test on {', '.join(tests)}"]
    for group in ("fresh", "hard"):
        scored = []
        for rule in SCALED_GRID:
            r = scaled_results(ledger, candles, group, rule, pick)
            if len(r) >= 5:
                scored.append((statistics.mean(r), rule))
        scored.sort(key=lambda t: t[0], reverse=True)
        best = scored[0][1]
        best_all_out = next(r for _, r in scored if r["take_frac"] == 1.0)
        out.append(f"\n== {group}")
        for label, rule in (("best overall", best), ("best all-out", best_all_out)):
            out.append(f"  {label}: {scaled_name(rule)}")
            out.append(f"    picked {pick}: {_summ(scaled_results(ledger, candles, group, rule, pick))}")
            for d in tests:
                out.append(f"    tested {d}: {_summ(scaled_results(ledger, candles, group, rule, d))}")
        bags = [(m, r) for m, r in scored if r["take_frac"] < 1.0]
        outs = [(m, r) for m, r in scored if r["take_frac"] == 1.0]
        out.append(f"  on {pick}: moonbag rules mean of means {100 * statistics.mean(m for m, _ in bags):+.1f}% "
                   f"vs all-out {100 * statistics.mean(m for m, _ in outs):+.1f}%")
    return "\n".join(out)


def rule_name(tp, sl, h) -> str:
    return (f"tp {'+' + str(int(tp * 100)) + '%' if tp else 'none':>5s}  "
            f"sl {'-' + str(int(sl * 100)) + '%' if sl else 'none':>5s}  {h:>2d}h")


def exit_results(ledger: "Ledger", candles: dict, group: str, rule, day: Optional[str] = None):
    """Net returns of `rule` over one group's entries (optionally one UTC day)."""
    out = []
    for key, e in ledger.entries.items():
        if key[2] != group:
            continue
        if day and dt.datetime.utcfromtimestamp(e["ts"]).strftime("%Y-%m-%d") != day:
            continue
        cs = candles.get((key[0], key[1], int(e["ts"])))
        if not cs:
            continue
        r = exit_trade(cs, e["ts"], e["price"], e["liq"], *rule)
        if r is not None:
            out.append(r)
    return out


def _summ(rets):
    if not rets:
        return "n=0"
    return (f"n={len(rets):3d}  median {100 * statistics.median(rets):+6.1f}%  "
            f"mean {100 * statistics.mean(rets):+7.1f}%  up {100 * sum(r > 0 for r in rets) / len(rets):3.0f}%")


def exit_report(ledger: "Ledger", candles: dict, by: str = "mean") -> str:
    """Pick the best rule on the first day by `by` (mean = what a trader
    keeps; median is misleading for take-profit rules, which cap every
    winner and say nothing about the size of the losers), then score it
    on the remaining days against the baseline under the same rule."""
    days = sorted({dt.datetime.utcfromtimestamp(e["ts"]).strftime("%Y-%m-%d")
                   for k, e in ledger.entries.items()
                   if (k[0], k[1], int(e["ts"])) in candles})
    out = [f"exit replay on 5-minute candles; days with data: {', '.join(days)}"]
    if len(days) < 2:
        out.append("need two days of entries to pick a rule on one and test it on the other")
        return "\n".join(out)
    pick_day, test_days = days[0], days[1:]
    for group in ("hard", "crowd"):
        scored = []
        for rule in EXIT_GRID:
            r = exit_results(ledger, candles, group, rule, pick_day)
            if len(r) >= 5:
                stat = statistics.mean(r) if by == "mean" else statistics.median(r)
                scored.append((stat, rule))
        if not scored:
            continue
        scored.sort(key=lambda t: t[0], reverse=True)      # ties keep grid order
        best = scored[0][1]
        out.append(f"\n== {group}: best of {len(EXIT_GRID)} rules on {pick_day} (by {by}) "
                   f"-> {rule_name(*best)}")
        out.append(f"  picked on {pick_day}:  {_summ(exit_results(ledger, candles, group, best, pick_day))}")
        for d in test_days:
            out.append(f"  tested on {d}:  {_summ(exit_results(ledger, candles, group, best, d))}")
            out.append(f"    baseline, same rule, {d}: "
                       f"{_summ(exit_results(ledger, candles, 'fresh', best, d))}")
        pos = sum(1 for m, _ in scored if m > 0)
        out.append(f"  rules with a positive {by} on {pick_day}: {pos} of {len(scored)}")
    return "\n".join(out)


async def fetch_candles(ledger: "Ledger", path: Path) -> dict:
    """5-minute candles for each (pool, entry) from entry to +24h; cached."""
    from cryptobot.data.geckoterminal import GeckoTerminalClient
    import pickle
    out = pickle.loads(path.read_bytes()) if path.exists() else {}
    gt = GeckoTerminalClient()
    try:
        for (net, pool, _), e in ledger.entries.items():
            key = (net, pool, int(e["ts"]))
            end = int(e["ts"]) + 24 * 3600 + 600
            if key in out or end > time.time():
                continue
            try:
                cs = await gt.ohlcv(net, pool, timeframe="minute", aggregate=5,
                                    limit=300, before_ts=end)
            except Exception as exc:
                logger.warning("ohlcv %s failed: %s", pool[:10], exc)
                cs = []
            out[key] = [c for c in cs if c.ts >= e["ts"] - 300]
            path.write_bytes(pickle.dumps(out))
            await asyncio.sleep(CALL_PAUSE_S)
    finally:
        await gt.close()
    return out


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
    missed = sum(len(v) for v in ledger.missed.values())
    if missed:
        out.append(f"{missed} marks missed (taken > {LATE_FACTOR}x their horizon, logger down) "
                   f"and excluded")
    out.append(f"{'group':6s} {'h':>3s} {'n':>4s} {'mean net':>9s} {'median':>8s} "
               f"{'>0':>5s} {'<=-50%':>7s} {'gone':>5s}")
    for g in groups:
        for h in HORIZONS_H:
            rets, gone = [], 0
            for key, e in ledger.entries.items():
                if key[2] != g:
                    continue
                m = ledger.marks.get(key, {})
                if h not in m or h in ledger.missed.get(key, ()):
                    continue
                if m[h] is None:
                    gone += 1
                rets.append(net_return(e["price"], m[h], e["liq"]))
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
    ap.add_argument("--exits", type=Path, metavar="CANDLE_CACHE",
                    help="fetch 5m candles into this cache and replay the exit grid")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.exits:
        led = Ledger(args.state)
        candles = asyncio.run(fetch_candles(led, args.exits))
        print(exit_report(led, candles, by="mean"))
        print()
        print(scaled_report(led, candles))
        return 0
    if args.report:
        print(report(Ledger(args.state)))
        return 0
    asyncio.run(run(args.state, args.cycle, args.cycles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
