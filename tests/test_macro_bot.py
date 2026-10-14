import asyncio
import datetime as dt
import random

from cryptobot import macro_bot as M
from cryptobot.data import macro as D
from cryptobot.execution.perp_exchange import Fill


def _curve(tmp_path, n=1200, seed=1, steepen_last=0.0):
    rng = random.Random(seed)
    days, d = [], dt.date(2022, 1, 3)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += dt.timedelta(days=1)
    s10, s2 = 3.0, 2.5
    r10, r2 = [], []
    for i, day in enumerate(days):
        s10 += rng.gauss(0, 0.03) + (steepen_last if i >= n - 20 else 0.0)
        s2 += rng.gauss(0, 0.03)
        r10.append((day, s10)); r2.append((day, s2))
    D.write_series(tmp_path, "DGS10", r10)
    D.write_series(tmp_path, "DGS2", r2)
    return days


class FakeExec:
    mode = "paper"

    def __init__(self, mid=55.0):
        self.mid_px, self.orders = mid, []

    async def mid(self, symbol):
        return self.mid_px

    async def open_long(self, symbol, notional, mid):
        self.orders.append("buy"); return Fill(symbol, "long", float(int(notional / mid)), mid)

    async def open_short(self, symbol, notional, mid):
        self.orders.append("sell"); return Fill(symbol, "short", float(int(notional / mid)), mid)

    async def close(self, symbol, qty, mid):
        self.orders.append("close"); return Fill(symbol, "close", qty, mid)

    async def clock(self):
        return {"is_open": True}

    async def close_client(self):
        pass


def test_signal_terciles_from_trailing_years(tmp_path):
    _curve(tmp_path, steepen_last=0.05)
    ch = M.slope_changes(tmp_path)
    assert len(ch) > 1000
    sig = M.signal(ch)
    assert sig["side"] == 1 and sig["change"] > sig["hi"]
    assert M.signal(ch[:100]) is None


def test_trade_lifecycle_and_report(tmp_path):
    _curve(tmp_path, steepen_last=0.05)
    ex = FakeExec()
    clock = {"t": dt.datetime(2026, 10, 14, 21, 30, tzinfo=dt.timezone.utc)}

    async def no_fetch(state):
        return None
    bot = M.MacroBot(tmp_path, {"symbol": "XLF", "notional_usd": 1000}, executor=ex, now=lambda: clock["t"], fetch=no_fetch)
    sig = asyncio.run(bot.evaluate())
    assert sig["side"] == 1
    clock["t"] = dt.datetime(2026, 10, 15, 13, 31, tzinfo=dt.timezone.utc)
    opened = asyncio.run(bot.execute())
    assert opened["status"] == "open" and opened["qty"] == 18 and ex.orders == ["buy"]
    for k in range(M.HOLD_SESSIONS - 1):
        clock["t"] += dt.timedelta(days=1)
        assert asyncio.run(bot.execute()) is None
    ex.mid_px = 56.1
    clock["t"] += dt.timedelta(days=1)
    closed = asyncio.run(bot.execute())
    assert closed["status"] == "closed" and closed["net_bp"] > 150 and ex.orders[-1] == "close"
    rep = M.report(tmp_path)
    assert rep["closed"] == 1 and rep["verdict"][0] == "collecting" and "macro pilot" in M.render(rep)
    what, when = bot._next(dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc))
    assert what == "execute" and when.astimezone(M.ET).time() == M.EXEC_ET
    assert M.passes({"closed": 20, "mean_bp": 80.0, "net_pct": 1.6})[0] == "alive"
    assert M.passes({"closed": 20, "mean_bp": -5.0, "net_pct": -0.1})[0] == "killed"
