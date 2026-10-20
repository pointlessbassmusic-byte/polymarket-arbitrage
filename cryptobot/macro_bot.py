"""Paper pilot for the one macro lead that cleared its bar: a steepening
2s10s curve leads bank stocks (`macro-relations-2026-10`, 2s10s 20-day
change -> XLF over 20 days, +109 bp a trade 2017-2026, best of 48
trials, so paper first).

Each weekday after FRED's update (21:30 UTC) the 20-day change in
DGS10 - DGS2 is placed against the terciles of its own trailing three
years. Top tercile: long XLF at the next open; bottom tercile: short;
middle: nothing new. One position at a time, held 20 trading days,
flattened at the open of the 21st. Alpaca PAPER only until the pilot's
bar is met: after 20 trades, mean net >= +50 bp a trade and net
positive is alive, mean <= 0 is killed.

    python -m cryptobot.macro_bot --state state --report
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import statistics
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from .data.macro import read_series, update as macro_update
from .data.nasdaq import append_jsonl, read_jsonl

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
EVAL_UTC = dt.time(21, 30)
EXEC_ET = dt.time(9, 31)
HOLD_SESSIONS = 20
WINDOW = 20
LOOKBACK_YEARS = 3
PILOT_TRADES = 20
BACKTEST_BP = 109.0


def trades_file(state_dir: Path) -> Path:
    return Path(state_dir) / "macro_bot" / "trades.jsonl"


def slope_changes(state_dir: Path) -> list[tuple[str, float]]:
    """(date, 20-day change in the 2s10s slope), oldest first."""
    a, b = dict(read_series(state_dir, "DGS10")), dict(read_series(state_dir, "DGS2"))
    days = sorted(d for d in a if d in b)
    slope = [a[d] - b[d] for d in days]
    return [(days[i], slope[i] - slope[i - WINDOW]) for i in range(WINDOW, len(days))]


def signal(changes: list[tuple[str, float]], asof: Optional[str] = None) -> Optional[dict]:
    """Tercile of the latest change against the trailing three years."""
    rows = [(d, v) for d, v in changes if asof is None or d <= asof]
    if len(rows) < 250:
        return None
    day, v = rows[-1]
    cutoff = (dt.date.fromisoformat(day) - dt.timedelta(days=365 * LOOKBACK_YEARS)).isoformat()
    hist = sorted(x for d, x in rows if d >= cutoff)
    lo, hi = hist[len(hist) // 3], hist[2 * len(hist) // 3]
    side = 1 if v >= hi else -1 if v <= lo else 0
    return {"date": day, "change": v, "lo": lo, "hi": hi, "side": side}


class MacroBot:
    def __init__(self, state_dir: Path, cfg: Optional[dict] = None, executor=None,
                 now: Optional[Callable[[], dt.datetime]] = None, sleep=None, fetch=None):
        cfg = cfg or {}
        self.state = Path(state_dir)
        self.symbol = cfg.get("symbol", "XLF")
        self.notional = float(cfg.get("notional_usd", 1000))
        self._ex = executor
        self._now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._sleep = sleep or asyncio.sleep
        self._fetch = fetch
        self.pending: Optional[dict] = None
        self.open: Optional[dict] = self._open_trade()

    def _executor(self):
        if self._ex is None:
            from .execution.alpaca import AlpacaConfig, AlpacaExecutor
            self._ex = AlpacaExecutor(AlpacaConfig(live=False, max_trade_usd=self.notional))
        return self._ex

    @property
    def mode(self) -> str:
        return getattr(self._executor(), "mode", "dry-run")

    def _open_trade(self) -> Optional[dict]:
        rows = read_jsonl(trades_file(self.state))
        return next((r for r in reversed(rows) if r.get("status") == "open"), None)

    def _save(self, rec: dict) -> None:
        rows = [r for r in read_jsonl(trades_file(self.state)) if r.get("id") != rec["id"]]
        p = trades_file(self.state)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(__import__("json").dumps(r) + "\n" for r in rows + [rec]))

    async def refresh(self) -> None:
        if self._fetch is not None:
            await self._fetch(self.state)
        else:
            await macro_update(self.state, fred_ids=("DGS10", "DGS2"), etfs=())

    async def evaluate(self) -> Optional[dict]:
        """After the close: refresh the curve and decide tomorrow's action."""
        await self.refresh()
        sig = signal(slope_changes(self.state))
        if sig is None:
            return None
        self.pending = sig
        logger.info("macro: 2s10s 20d change %+.3f (terciles %+.3f / %+.3f) -> %s", sig["change"], sig["lo"], sig["hi"],
                    {1: "long", -1: "short", 0: "none"}[sig["side"]])
        return sig

    async def execute(self) -> Optional[dict]:
        """At the open: flatten an expired position, then open on a pending signal."""
        ex = self._executor()
        today = self._now().astimezone(ET).date()
        out = None
        if self.open:
            self.open["sessions_held"] = self.open.get("sessions_held", 0) + 1
            if self.open["sessions_held"] >= HOLD_SESSIONS:
                mid = await ex.mid(self.symbol)
                fill = await ex.close(self.symbol, self.open["qty"], mid)
                side = self.open["side"]
                net_bp = side * (fill.price / self.open["entry"] - 1) * 1e4 - 8.0
                self.open.update(status="closed", exit=fill.price, exit_date=today.isoformat(), net_bp=net_bp)
                self._save(self.open)
                logger.info("macro: closed %s after %d sessions, %+.0f bp", self.symbol, HOLD_SESSIONS, net_bp)
                out = self.open
                self.open = None
            else:
                self._save(self.open)
        if self.open is None and hasattr(ex, "positions"):
            held = (await ex.positions()).get(self.symbol, 0.0)
            if held:                                       # a fill the pilot never recorded: flatten it
                out_px = (await ex.close(self.symbol, abs(held), await ex.mid(self.symbol))).price
                logger.warning("macro: flattened an unrecorded %s position of %+.0f shares at %.2f", self.symbol, held, out_px)
        if self.open is None and self.pending and self.pending["side"]:
            mid = await ex.mid(self.symbol)
            fill = await (ex.open_long if self.pending["side"] > 0 else ex.open_short)(self.symbol, self.notional, mid)
            self.open = {"id": f"{today.isoformat()}-{self.symbol}", "symbol": self.symbol, "side": self.pending["side"],
                         "signal_date": self.pending["date"], "change": self.pending["change"], "entry": fill.price,
                         "qty": fill.qty, "entry_date": today.isoformat(), "sessions_held": 0, "status": "open",
                         "mode": self.mode, "dry_run": bool(getattr(fill, "dry_run", False))}
            self._save(self.open)
            logger.info("macro: %s %s x%.0f at %.2f (%s)", "long" if self.pending["side"] > 0 else "short", self.symbol, fill.qty, fill.price, self.mode)
            out = self.open
        self.pending = None
        return out

    def _next(self, now: dt.datetime) -> tuple[str, dt.datetime]:
        """The next event: ('evaluate', t) at 21:30 UTC or ('execute', t) at 09:31 ET, weekdays."""
        cands = []
        for k in range(0, 4):
            day = (now + dt.timedelta(days=k)).date()
            if day.weekday() < 5:
                cands.append(("evaluate", dt.datetime.combine(day, EVAL_UTC, dt.timezone.utc)))
                cands.append(("execute", dt.datetime.combine(day, EXEC_ET, ET).astimezone(dt.timezone.utc)))
        return min((c for c in cands if c[1] > now), key=lambda c: c[1])

    async def run_forever(self) -> None:
        logger.info("macro pilot on %s: %s mode, $%.0f a position", self.symbol, self.mode, self.notional)
        while True:
            what, when = self._next(self._now())
            await self._sleep(max(1.0, (when - self._now()).total_seconds()))
            try:
                if what == "evaluate":
                    await self.evaluate()
                else:
                    clock = await self._executor().clock()
                    if clock and not clock.get("is_open", True):
                        continue
                    await self.execute()
            except Exception as exc:                      # noqa: BLE001
                logger.warning("macro %s failed: %s", what, exc)
                await self._sleep(60)

    async def close(self) -> None:
        if self._ex is not None and hasattr(self._ex, "close_client"):
            await self._ex.close_client()


def report(state_dir: Path) -> dict:
    rows = read_jsonl(trades_file(state_dir))
    closed = [r for r in rows if r.get("status") == "closed"]
    out = {"trades": len(rows), "closed": len(closed), "open": next((r for r in rows if r.get("status") == "open"), None),
           "target": PILOT_TRADES, "backtest_bp": BACKTEST_BP}
    if closed:
        nets = [r["net_bp"] for r in closed]
        out.update(mean_bp=statistics.fmean(nets), net_pct=sum(nets) / 1e4 * 100,
                   hit=statistics.fmean(1.0 if x > 0 else 0.0 for x in nets))
    out["verdict"] = passes(out)
    return out


def passes(s: dict) -> tuple[str, str]:
    n = s.get("closed", 0)
    if n < PILOT_TRADES:
        return "collecting", f"{n} of {PILOT_TRADES} trades"
    if s["mean_bp"] <= 0:
        return "killed", f"mean {s['mean_bp']:+.0f} bp over {n} trades"
    if s["mean_bp"] >= 50 and s["net_pct"] > 0:
        return "alive", f"mean {s['mean_bp']:+.0f} bp (backtest +109) over {n} trades"
    return "inconclusive", f"mean {s['mean_bp']:+.0f} bp over {n} trades"


def render(s: dict) -> str:
    o = [f"macro pilot (2s10s -> XLF, Alpaca paper): {s['closed']} closed of {s['target']} trades" + (", one open" if s.get("open") else "")]
    if s.get("closed"):
        o.append(f"  mean {s['mean_bp']:+.0f} bp a trade (backtest {s['backtest_bp']:+.0f}), hit {s['hit']*100:.0f}%, net {s['net_pct']:+.2f}% of a position")
    v, why = s["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--signal", action="store_true", help="refresh the curve and print today's signal")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.signal:
        bot = MacroBot(a.state)
        print(asyncio.run(bot.evaluate()))
        return 0
    print(render(report(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
