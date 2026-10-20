"""Opening-range breakout paper pilot on Alpaca: step 2 of `orb-qqq-pilot`.

The backtest (cryptobot.orb_study, 2020-2026 on IEX bars) is alive; this
runs the same rule against live quotes on the Alpaca PAPER account, one
session a day, and keeps a record the backtest can be held against.
Paper only: it is leveraged day trading, which the pattern-day-trader
rule keeps out of accounts under 25,000 USD, and the desk never arms
Alpaca live here. Without a key it dry-runs at the quoted mid.

Each session (New York time):
  09:35:10  read the 09:30 five-minute bar and the 14-session ATR from
            daily bars; first bar up = long, down = short, doji = no trade
            entry at the quoted mid (IOC limit), stop 0.1 ATR away,
            target 10 R, shares so that the stop costs 1% of the paper
            capital, at most 4x
  every 30s the mid: stop or target touched -> flatten
  15:55     still open -> flatten
Every session goes to state/orb/sessions.jsonl.

    python -m cryptobot.orb_bot --state state --report     # the pilot so far, against the backtest
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import math
import statistics
from pathlib import Path
from typing import Callable, Optional

from .data.nasdaq import append_jsonl, read_jsonl
from .orb_study import ET, OrbRule

logger = logging.getLogger(__name__)

DECISION_ET = dt.time(9, 35, 10)
FLAT_ET = dt.time(15, 55)
PILOT_SESSIONS = 60
BACKTEST = {"mean_r": 0.26, "hit": 0.20, "net_pct_year": 0.326}      # orb_study 2020-2026 at 1 c/share


def sessions_file(state_dir: Path) -> Path:
    return Path(state_dir) / "orb" / "sessions.jsonl"


def atr_from_daily(daily, n: int = 14) -> Optional[float]:
    """Mean true range of the last `n` completed sessions (today excluded)."""
    rows = sorted(daily, key=lambda c: c.ts)
    trs = []
    for a, b in zip(rows, rows[1:]):
        trs.append(max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close)))
    if len(trs) < n:
        return None
    return statistics.fmean(trs[-n:])


class OrbBot:
    def __init__(self, state_dir: Path, cfg: Optional[dict] = None, executor=None, data=None,
                 now: Optional[Callable[[], dt.datetime]] = None, sleep=None):
        cfg = cfg or {}
        self.state = Path(state_dir)
        self.symbol = cfg.get("symbol", "QQQ")
        self.capital = float(cfg.get("capital_usd", 25_000))
        self.poll_s = float(cfg.get("poll_s", 30))
        self.rule = OrbRule()
        self._ex = executor
        self._data = data
        self._now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._sleep = sleep or asyncio.sleep
        self.last: Optional[dict] = None

    # -- wiring ---------------------------------------------------------------

    def _executor(self):
        if self._ex is None:
            from .execution.alpaca import AlpacaConfig, AlpacaExecutor
            self._ex = AlpacaExecutor(AlpacaConfig(live=False, max_trade_usd=self.rule.max_leverage * self.capital))
        return self._ex

    def _feed(self):
        if self._data is None:
            from .data.alpaca import AlpacaData
            self._data = AlpacaData()
        return self._data

    @property
    def mode(self) -> str:
        return getattr(self._executor(), "mode", "dry-run")

    # -- one session ----------------------------------------------------------

    async def run_session(self, day: Optional[dt.date] = None) -> Optional[dict]:
        ex, feed = self._executor(), self._feed()
        now_et = self._now().astimezone(ET)
        day = day or now_et.date()
        open_et = dt.datetime.combine(day, dt.time(9, 30), ET)
        daily = await feed.daily(self.symbol, start=open_et - dt.timedelta(days=40))
        daily = [c for c in daily if dt.datetime.fromtimestamp(c.ts, dt.timezone.utc).astimezone(ET).date() < day]
        a = atr_from_daily(daily, self.rule.atr_days)
        bars = await feed.bars(self.symbol, "5Min", start=open_et, end=open_et + dt.timedelta(minutes=5))
        first = next((b for b in bars if dt.datetime.fromtimestamp(b.ts, dt.timezone.utc).astimezone(ET).time() == dt.time(9, 30)), None)
        rec = {"day": day.isoformat(), "symbol": self.symbol, "mode": self.mode, "atr": a}
        if first is None or not a:
            rec.update(reason="no_bar" if first is None else "no_atr", side=0, net=0.0, net_pct=0.0, r=0.0)
            return self._record(rec)
        if first.close == first.open:
            rec.update(reason="doji", side=0, net=0.0, net_pct=0.0, r=0.0, first_open=first.open, first_close=first.close)
            return self._record(rec)
        side = 1 if first.close > first.open else -1
        mid = await ex.mid(self.symbol)
        held = (await ex.positions()).get(self.symbol, 0.0) if hasattr(ex, "positions") else 0.0
        if held:                                           # a leftover from an earlier session: flatten it first
            out = await ex.close(self.symbol, abs(held), mid)
            rec["flattened_leftover"] = {"shares": held, "price": out.price}
            logger.warning("orb: flattened a leftover %s position of %+.0f shares at %.2f", self.symbol, held, out.price)
        dist = self.rule.stop_atr * a
        shares = math.floor(min(self.rule.risk_per_day * self.capital / dist, self.rule.max_leverage * self.capital / mid))
        if shares < 1:
            rec.update(reason="too_small", side=side, net=0.0, net_pct=0.0, r=0.0)
            return self._record(rec)
        fill = await (ex.open_long if side > 0 else ex.open_short)(self.symbol, shares * mid, mid)
        entry, qty = fill.price, fill.qty
        stop = entry - side * dist
        target = entry + side * self.rule.target_r * dist
        rec.update(side=side, entry=entry, shares=qty, stop=stop, target=target, dry_run=bool(getattr(fill, "dry_run", False)))
        logger.info("orb %s %s x%.0f at %.2f, stop %.2f, target %.2f (%s)", self.symbol,
                    "long" if side > 0 else "short", qty, entry, stop, target, self.mode)
        reason, exit_px = "close", entry
        while True:
            await self._sleep(self.poll_s)
            px = await ex.mid(self.symbol)
            t = self._now().astimezone(ET).time()
            if (side > 0 and px <= stop) or (side < 0 and px >= stop):
                reason = "stop"
            elif (side > 0 and px >= target) or (side < 0 and px <= target):
                reason = "target"
            elif t >= FLAT_ET:
                reason = "close"
            else:
                continue
            out = await ex.close(self.symbol, qty, px)
            exit_px = out.price
            break
        gross = side * (exit_px - entry) * qty
        rec.update(exit=exit_px, reason=reason, r=side * (exit_px - entry) / dist, net=gross,
                   net_pct=gross / self.capital, exit_time=self._now().isoformat())
        return self._record(rec)

    def _record(self, rec: dict) -> dict:
        rec["recorded_at"] = self._now().isoformat()
        append_jsonl(sessions_file(self.state), rec)
        self.last = rec
        logger.info("orb session %s: %s r %+.2f net %+.2f", rec["day"], rec.get("reason"), rec.get("r", 0.0), rec.get("net", 0.0))
        return rec

    # -- the loop -------------------------------------------------------------

    def _next_decision(self, now_utc: dt.datetime) -> dt.datetime:
        et = now_utc.astimezone(ET)
        cand = dt.datetime.combine(et.date(), DECISION_ET, ET)
        if cand <= et:
            cand += dt.timedelta(days=1)
        while cand.weekday() >= 5:
            cand += dt.timedelta(days=1)
        return cand.astimezone(dt.timezone.utc)

    def _done_today(self, day: dt.date) -> bool:
        return any(r.get("day") == day.isoformat() for r in read_jsonl(sessions_file(self.state)))

    async def run_forever(self) -> None:
        logger.info("orb pilot on %s: %s mode, paper capital $%.0f", self.symbol, self.mode, self.capital)
        while True:
            nxt = self._next_decision(self._now())
            wait = (nxt - self._now()).total_seconds()
            if wait > 0:
                await self._sleep(wait)
            day = self._now().astimezone(ET).date()
            if self._done_today(day):
                await self._sleep(60)
                continue
            try:
                clock = await self._executor().clock()
                if clock and not clock.get("is_open", True):
                    logger.info("orb: market closed on %s, skipping", day)
                    self._record({"day": day.isoformat(), "symbol": self.symbol, "mode": self.mode,
                                  "reason": "holiday", "side": 0, "net": 0.0, "net_pct": 0.0, "r": 0.0})
                    continue
                await self.run_session(day)
            except Exception as exc:                      # noqa: BLE001 - a bad day must not stop the pilot
                logger.warning("orb session %s failed: %s", day, exc)
                self._record({"day": day.isoformat(), "symbol": self.symbol, "mode": self.mode,
                              "reason": f"error: {type(exc).__name__}", "error": str(exc)[:300], "side": 0, "net": 0.0, "net_pct": 0.0, "r": 0.0})
                await self._sleep(60)

    async def close(self) -> None:
        if self._ex is not None and hasattr(self._ex, "close_client"):
            await self._ex.close_client()
        if self._data is not None and hasattr(self._data, "close"):
            await self._data.close()

    def state(self) -> dict:
        return report(self.state) | {"mode": self.mode, "last": self.last}


async def check(bot: "OrbBot") -> list[tuple[str, bool, str]]:
    """Every call a session makes, one at a time, each pass/fail with
    Alpaca's own answer. While the market is open it also round-trips one
    share on the PAPER account (IOC buy, then flatten), the order path the
    09:35 session uses. Never runs against a live account."""
    out = []

    async def step(name, fn):
        try:
            msg = await fn()
            out.append((name, True, msg))
            return True
        except Exception as exc:                          # noqa: BLE001 - report every failure
            out.append((name, False, f"{type(exc).__name__}: {str(exc)[:300]}"))
            return False

    ex, feed = bot._executor(), bot._feed()
    st = {}

    async def account():
        b = await ex.balance()
        return (f"mode {b['mode']}, status {b['status']}, equity ${b['total_usd_balance']:,.0f}, buying power "
                f"${b['available_margin']:,.0f}, shorting {'on' if b['shorting_enabled'] else 'OFF'}, "
                f"pattern day trader {b['pattern_day_trader']}, day trades {b['daytrade_count']}")

    async def clock():
        c = await ex.clock()
        st["open"] = bool(c.get("is_open"))
        return f"market {'open' if st['open'] else 'closed'}, next open {c.get('next_open')}"

    async def daily():
        now = bot._now().astimezone(ET)
        d = await feed.daily(bot.symbol, start=now - dt.timedelta(days=40))
        d = [c for c in d if dt.datetime.fromtimestamp(c.ts, dt.timezone.utc).astimezone(ET).date() < now.date()]
        a = atr_from_daily(d, bot.rule.atr_days)
        if not d:
            raise RuntimeError("no daily bars")
        st["last_day"] = dt.datetime.fromtimestamp(d[-1].ts, dt.timezone.utc).astimezone(ET).date()
        return f"{len(d)} daily bars to {st['last_day']}, ATR {a}"

    async def first_bar():
        day = st.get("last_day") or bot._now().astimezone(ET).date()
        o = dt.datetime.combine(day, dt.time(9, 30), ET)
        bars = await feed.bars(bot.symbol, "5Min", start=o, end=o + dt.timedelta(minutes=5))
        f = next((b for b in bars if dt.datetime.fromtimestamp(b.ts, dt.timezone.utc).astimezone(ET).time() == dt.time(9, 30)), None)
        if f is None:
            raise RuntimeError(f"no 09:30 bar on {day} ({len(bars)} bars returned)")
        return f"09:30 bar on {day}: open {f.open} close {f.close}"

    async def quote():
        return f"mid {await ex.mid(bot.symbol):.2f}"

    async def order():
        if not st.get("open"):
            return "skipped: market closed (run this between 09:30 and 16:00 New York time to test orders)"
        if getattr(ex, "mode", "") != "paper":
            return f"skipped: mode {getattr(ex, 'mode', '?')}, orders are only tested on paper"
        mid = await ex.mid(bot.symbol)
        f = await ex.open_long(bot.symbol, mid * 1.01, mid)
        c = await ex.close(bot.symbol, f.qty, mid)
        return f"paper: bought {f.qty:.0f} at {f.price:.2f}, sold at {c.price:.2f}"

    async def positions():
        p = await ex.positions()
        return ", ".join(f"{k} {v:+.0f} shares" for k, v in p.items()) or "none"

    async def orders():
        rows = await ex._request("GET", "/v2/orders", params={"status": "all", "limit": 10, "direction": "desc"})
        if not rows:
            return "none"
        return " | ".join(f"{(r.get('submitted_at') or '')[:19]} {r.get('symbol')} {r.get('side')} {r.get('qty')} "
                          f"{r.get('type')}/{r.get('time_in_force')} limit {r.get('limit_price')} -> {r.get('status')}, "
                          f"filled {r.get('filled_qty')} at {r.get('filled_avg_price')}" for r in rows)

    for name, fn in (("account", account), ("open positions", positions), ("last 10 orders", orders), ("clock", clock), ("daily bars", daily),
                     ("09:30 five-minute bar", first_bar), ("quote", quote), ("paper order", order)):
        await step(name, fn)
    return out


# ------------------------------------------------------------------ scoring

def report(state_dir: Path) -> dict:
    rows = read_jsonl(sessions_file(state_dir))
    traded = [r for r in rows if r.get("side") and r.get("reason") in ("stop", "target", "close")]
    out = {"sessions": len(rows), "traded": len(traded), "first": rows[0]["day"] if rows else None,
           "last": rows[-1]["day"] if rows else None, "target_sessions": PILOT_SESSIONS, "backtest": BACKTEST}
    if traded:
        rs = [t["r"] for t in traded]
        nets = [t["net_pct"] for t in traded]
        out.update(mean_r=statistics.fmean(rs), hit=statistics.fmean(1.0 if r > 0 else 0.0 for r in rs),
                   net_pct=sum(nets), net_pct_year=sum(nets) * 252 / len(traded),
                   exits={k: sum(1 for t in traded if t["reason"] == k) for k in ("stop", "target", "close")})
    out["verdict"] = passes(out)
    return out


def passes(s: dict) -> tuple[str, str]:
    """Written before the pilot ran: after 60 traded sessions, mean R >= +0.10
    and net positive keeps it alive (the backtest's +0.26 R is the
    reference, half of it is the floor); mean R <= 0 over 60 kills it;
    before 60 sessions, collecting."""
    n = s.get("traded", 0)
    if n < PILOT_SESSIONS:
        return "collecting", f"{n} of {PILOT_SESSIONS} traded sessions"
    if s["mean_r"] <= 0:
        return "killed", f"mean {s['mean_r']:+.2f} R over {n} sessions"
    if s["mean_r"] >= 0.10 and s["net_pct"] > 0:
        return "alive", f"mean {s['mean_r']:+.2f} R, net {s['net_pct']*100:+.1f}% over {n} sessions"
    return "inconclusive", f"mean {s['mean_r']:+.2f} R over {n} sessions"


def render(s: dict) -> str:
    o = [f"ORB paper pilot: {s['sessions']} sessions on file ({s['first']} .. {s['last']}), {s['traded']} traded"]
    if s.get("traded"):
        o.append(f"  mean {s['mean_r']:+.2f} R (backtest {s['backtest']['mean_r']:+.2f}), hit {s['hit']*100:.0f}% "
                 f"(backtest {s['backtest']['hit']*100:.0f}%), net {s['net_pct']*100:+.2f}% of paper capital, "
                 f"{s['net_pct_year']*100:+.1f}%/yr at this rate (backtest {s['backtest']['net_pct_year']*100:+.1f}%); exits {s['exits']}")
    v, why = s["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--once", action="store_true", help="run one session now (paper or dry-run), for a manual check")
    ap.add_argument("--check", action="store_true", help="test every Alpaca call the session makes (paper only)")
    a = ap.parse_args(argv)
    if a.check:
        async def chk():
            bot = OrbBot(a.state)
            try:
                return await check(bot)
            finally:
                await bot.close()
        res = asyncio.run(chk())
        for name, ok, msg in res:
            print(f"[{'ok' if ok else 'FAIL'}] {name}: {msg}")
        return 0 if all(ok for _, ok, _ in res) else 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.once:
        async def once():
            bot = OrbBot(a.state)
            try:
                return await bot.run_session()
            finally:
                await bot.close()
        print(asyncio.run(once()))
        return 0
    print(render(report(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
