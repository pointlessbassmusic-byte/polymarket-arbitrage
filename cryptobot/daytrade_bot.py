"""Day trading bot: paper trading of the time-block scalper
(`daytrade-timeblock`), every variant side by side, inside the desk.

Every 15 minutes (20 s after the bar closes) it reads the latest closed
15-minute candles from Coinbase's public API for each asset, feeds them
to one cryptobot.daytrade.Engine per (asset, variant), and logs every
closed paper trade to state/daytrade/trades.jsonl with its P&L at a fixed
paper notional. On start it replays the last 3 days of bars to rebuild
each engine's state, so an open paper position survives a restart; a
trade already logged is never logged twice.

PAPER ONLY. No order is ever sent: real money waits for the registered
backtest and 100 paper trades (see `daytrade-timeblock`).

    python -m cryptobot.daytrade_bot --state state --report
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

from .daytrade import VARIANTS, Engine, cost_bp

logger = logging.getLogger(__name__)

PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "DOGE": "DOGE-USD"}
BAR_S = 900
WARMUP_BARS = 288          # 3 days of 15-minute bars


def trades_file(state: Path) -> Path:
    return Path(state) / "daytrade" / "trades.jsonl"


class DayTradeBot:
    def __init__(self, state: Path, cfg: Optional[dict] = None, client=None, now=None, sleep=None):
        cfg = cfg or {}
        self.state = Path(state)
        self.assets = [a for a in cfg.get("assets", list(PRODUCTS)) if a in PRODUCTS]
        self.variants = [v for v in cfg.get("variants", list(VARIANTS)) if v in VARIANTS]
        self.notional = float(cfg.get("notional_usd", 250.0))
        self._c = client or httpx.AsyncClient(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"})
        self._now = now or time.time
        self._sleep = sleep or asyncio.sleep
        self.engines = {(a, v): Engine(v, a) for a in self.assets for v in self.variants}
        self.last_ts: dict[str, float] = {}
        self.started = self._now()
        self.logged = self._logged_keys()

    def _logged_keys(self) -> set:
        p = trades_file(self.state)
        keys = set()
        if p.exists():
            for line in p.open():
                try:
                    r = json.loads(line)
                    keys.add((r["asset"], r["variant"], r["entry_ts"]))
                except (ValueError, KeyError):
                    continue
        return keys

    async def candles(self, asset: str, start: float, end: float) -> list[tuple]:
        out = {}
        t = int(start // BAR_S * BAR_S)
        end = int(end)                       # whole seconds: a fractional end would loop forever on an empty range
        while t < end:
            t2 = min(end, t + 300 * BAR_S)
            r = await self._c.get(f"https://api.exchange.coinbase.com/products/{PRODUCTS[asset]}/candles",
                                  params={"granularity": BAR_S,
                                          "start": dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(),
                                          "end": dt.datetime.fromtimestamp(t2, dt.timezone.utc).isoformat()})
            r.raise_for_status()
            for c in r.json():
                out[int(c[0])] = (int(c[0]), float(c[3]), float(c[2]), float(c[1]), float(c[4]), float(c[5]))
            t = t2
        now = self._now()
        return [out[k] for k in sorted(out) if k + BAR_S <= now]          # closed bars only

    def _log(self, trade: dict) -> Optional[dict]:
        key = (trade["asset"], trade["variant"], trade["entry_ts"])
        if key in self.logged:
            return None
        self.logged.add(key)
        row = dict(trade, notional_usd=self.notional, pnl_usd=round(self.notional * trade["net_bp"] / 1e4, 4),
                   logged_at=round(self._now(), 1))
        p = trades_file(self.state)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(row) + "\n")
        logger.info("daytrade %s %s %s %s net %+.1f bp ($%+.2f)", trade["asset"], trade["variant"],
                    "long" if trade["side"] > 0 else "short", trade["reason"], trade["net_bp"], row["pnl_usd"])
        return row

    async def step(self) -> int:
        """Feed every new closed bar to every engine; log trades that closed."""
        n = 0
        now = self._now()
        for a in self.assets:
            start = self.last_ts.get(a, now - WARMUP_BARS * BAR_S - BAR_S) + 1
            try:
                bars = await self.candles(a, start, now)
            except Exception as exc:                      # one asset down must not stop the rest
                logger.warning("daytrade candles %s: %s", a, exc)
                continue
            for b in bars:
                if b[0] <= self.last_ts.get(a, -1):
                    continue
                for v in self.variants:
                    t = self.engines[(a, v)].on_bar(b)
                    # trades that closed during the warm-up replay before this bot started are history, not paper trades
                    if t and t["exit_ts"] + BAR_S >= self.started and self._log(t):
                        n += 1
                self.last_ts[a] = b[0]
        self.write_open()
        return n

    def write_open(self) -> None:
        rows = []
        for (a, v), e in self.engines.items():
            p = e.pos
            if p:
                rows.append({"asset": a, "variant": v, "side": p.side, "entry": p.entry, "stop": p.stop,
                             "target": p.target, "entry_ts": p.entry_ts, "window": p.window})
        d = self.state / "daytrade"
        d.mkdir(parents=True, exist_ok=True)
        (d / "open.json").write_text(json.dumps(rows))

    async def run_forever(self) -> None:
        logger.info("day trading bot (paper): %s x %s on 15m bars", ",".join(self.assets), ",".join(self.variants))
        while True:
            try:
                await self.step()
            except Exception as exc:                      # never let the bot kill the desk
                logger.warning("daytrade step failed: %s", exc)
            now = self._now()
            nxt = (now // BAR_S + 1) * BAR_S + 20
            await self._sleep(max(5.0, nxt - now))


def report(state: Path) -> dict:
    p = trades_file(state)
    rows = [json.loads(l) for l in p.open() if l.strip()] if p.exists() else []
    out = {"trades": len(rows), "by_variant": {}}
    for v in VARIANTS:
        x = [r for r in rows if r["variant"] == v]
        if x:
            nets = [r["net_bp"] for r in x]
            out["by_variant"][v] = {"n": len(x), "net_bp": statistics.fmean(nets), "pnl_usd": sum(r["pnl_usd"] for r in x),
                                    "win": statistics.fmean(1.0 if n > 0 else 0.0 for n in nets)}
    op = Path(state) / "daytrade" / "open.json"
    out["open"] = json.loads(op.read_text()) if op.exists() else []
    return out


def render(r: dict) -> str:
    o = [f"day trading bot (paper): {r['trades']} closed paper trades, {len(r['open'])} open"]
    for v, s in r["by_variant"].items():
        o.append(f"  {v}: {s['n']} trades, mean {s['net_bp']:+.1f} bp after costs, win {s['win']:.0%}, paper P&L ${s['pnl_usd']:+,.2f}")
    for p in r["open"]:
        o.append(f"  open {p['variant']} {p['asset']} {'long' if p['side'] > 0 else 'short'} from {p['entry']:.6g}, stop {p['stop']:.6g}, target {p['target']:.6g}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--once", action="store_true", help="one step against live candles (paper), then the report")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.once:
        async def one():
            bot = DayTradeBot(a.state)
            try:
                return await bot.step()
            finally:
                await bot._c.aclose()
        print(f"logged {asyncio.run(one())} paper trades")
    print(render(report(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
