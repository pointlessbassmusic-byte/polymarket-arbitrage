import asyncio
import datetime as dt

import pytest

from cryptobot import orb_bot as O
from cryptobot.data.geckoterminal import Candle
from cryptobot.execution.perp_exchange import Fill
from cryptobot.orb_study import ET


def _ts(day, h, m):
    return int(dt.datetime.combine(day, dt.time(h, m), ET).timestamp())


class FakeFeed:
    def __init__(self, day, first_open, first_close):
        self.day = day
        self.first = Candle(ts=_ts(day, 9, 30), open=first_open, high=max(first_open, first_close) + 0.1,
                            low=min(first_open, first_close) - 0.1, close=first_close, volume_usd=1.0)

    async def daily(self, symbol, start=None):
        out = []
        for i in range(20, 0, -1):
            d = self.day - dt.timedelta(days=i)
            out.append(Candle(ts=_ts(d, 16, 0), open=400.0, high=404.0, low=396.0, close=400.0, volume_usd=1.0))
        return out                                                          # ATR 8.0 -> stop distance 0.8

    async def bars(self, symbol, timeframe="5Min", start=None, end=None):
        return [self.first]

    async def close(self):
        pass


class FakeExec:
    """Mids from a script; fills at the mid; records every order."""
    mode = "paper"

    def __init__(self, mids):
        self.mids, self.orders = list(mids), []

    async def mid(self, symbol):
        return self.mids.pop(0) if len(self.mids) > 1 else self.mids[0]

    async def open_long(self, symbol, notional, mid):
        self.orders.append(("buy", notional, mid))
        return Fill(symbol, "long", float(int(notional / mid)), mid)

    async def open_short(self, symbol, notional, mid):
        self.orders.append(("sell", notional, mid))
        return Fill(symbol, "short", float(int(notional / mid)), mid)

    async def close(self, symbol, qty, mid):
        self.orders.append(("close", qty, mid))
        return Fill(symbol, "close", qty, mid)

    async def clock(self):
        return {"is_open": True}

    async def close_client(self):
        pass


def _bot(tmp_path, feed, ex, times):
    it = iter(times)
    last = {"t": times[0]}

    def now():
        try:
            last["t"] = next(it)
        except StopIteration:
            pass
        return last["t"]

    async def sleep(_s):
        return None
    return O.OrbBot(tmp_path, {"capital_usd": 25_000, "poll_s": 1}, executor=ex, data=feed, now=now, sleep=sleep)


def _times(day, *hm):
    return [dt.datetime.combine(day, dt.time(h, m), ET).astimezone(dt.timezone.utc) for h, m in hm]


def test_long_day_stopped_out(tmp_path):
    day = dt.date(2026, 10, 14)
    feed = FakeFeed(day, 400.0, 401.0)                                     # first bar up -> long
    ex = FakeExec([401.0, 401.2, 400.1])                                   # entry 401, then 400.1 <= stop 400.2
    bot = _bot(tmp_path, feed, ex, _times(day, (9, 35), (9, 36), (9, 37), (9, 38), (9, 39)))
    rec = asyncio.run(bot.run_session(day))
    assert rec["side"] == 1 and rec["entry"] == 401.0 and rec["stop"] == pytest.approx(400.2)
    assert rec["shares"] == 249                                            # min(1% of 25k / 0.8 = 312, 4x cap 100k / 401 = 249)
    assert rec["reason"] == "stop" and rec["r"] == pytest.approx(-1.125) and rec["net"] < 0
    assert ex.orders[0][0] == "buy" and ex.orders[-1][0] == "close"
    assert O.report(tmp_path)["traded"] == 1


def test_short_day_hits_target_and_doji_skips(tmp_path):
    day = dt.date(2026, 10, 14)
    feed = FakeFeed(day, 400.0, 399.0)                                     # first bar down -> short
    ex = FakeExec([399.0, 398.0, 390.5])                                   # target = 399 - 8 = 391
    bot = _bot(tmp_path, feed, ex, _times(day, (9, 35), (9, 36), (9, 37), (9, 38)))
    rec = asyncio.run(bot.run_session(day))
    assert rec["side"] == -1 and rec["reason"] == "target" and rec["r"] > 10
    feed2 = FakeFeed(dt.date(2026, 10, 15), 400.0, 400.0)
    bot2 = _bot(tmp_path, feed2, FakeExec([400.0]), _times(dt.date(2026, 10, 15), (9, 35)))
    rec2 = asyncio.run(bot2.run_session(dt.date(2026, 10, 15)))
    assert rec2["reason"] == "doji" and rec2["side"] == 0
    s = O.report(tmp_path)
    assert s["sessions"] == 2 and s["traded"] == 1 and s["verdict"][0] == "collecting"
    assert "ORB paper pilot" in O.render(s)


def test_flat_at_the_close_and_pilot_verdicts(tmp_path):
    day = dt.date(2026, 10, 14)
    feed = FakeFeed(day, 400.0, 401.0)
    ex = FakeExec([401.0, 401.5, 402.0])
    bot = _bot(tmp_path, feed, ex, _times(day, (9, 35), (9, 36), (15, 56), (15, 57)))
    rec = asyncio.run(bot.run_session(day))
    assert rec["reason"] == "close" and rec["r"] > 0
    assert O.passes({"traded": 10}) == ("collecting", "10 of 60 traded sessions")
    assert O.passes({"traded": 60, "mean_r": -0.1, "net_pct": -0.1})[0] == "killed"
    assert O.passes({"traded": 60, "mean_r": 0.2, "net_pct": 0.1})[0] == "alive"
    assert O.passes({"traded": 60, "mean_r": 0.05, "net_pct": 0.01})[0] == "inconclusive"


def test_next_decision_skips_weekends_and_done_days(tmp_path):
    bot = O.OrbBot(tmp_path, {}, executor=FakeExec([1.0]), data=None)
    fri_late = dt.datetime.combine(dt.date(2026, 10, 16), dt.time(16, 0), ET).astimezone(dt.timezone.utc)
    nxt = bot._next_decision(fri_late).astimezone(ET)
    assert nxt.date() == dt.date(2026, 10, 19) and nxt.time() == O.DECISION_ET        # Monday
    assert not bot._done_today(dt.date(2026, 10, 19))
    assert O.atr_from_daily([], 14) is None


def test_check_reports_each_call_and_the_failing_one(tmp_path):
    day = dt.date(2026, 10, 14)

    class Ex(FakeExec):
        async def positions(self):
            return {}

        async def _request(self, method, path, params=None):
            return [{"submitted_at": "2026-10-19T13:35:10Z", "symbol": "QQQ", "side": "buy", "qty": "139", "type": "limit",
                     "time_in_force": "ioc", "limit_price": "720.1", "status": "canceled", "filled_qty": "0"}]

        async def balance(self):
            return {"mode": "paper", "status": "ACTIVE", "total_usd_balance": 1e5, "available_margin": 2e5,
                    "shorting_enabled": True, "pattern_day_trader": False, "daytrade_count": 0}

    class BadFeed(FakeFeed):
        async def bars(self, symbol, timeframe="5Min", start=None, end=None):
            raise RuntimeError("alpaca data /v2/stocks/bars -> 403: forbidden")

    ex = Ex([401.0])
    bot = _bot(tmp_path, FakeFeed(day, 400.0, 401.0), ex, _times(day, (10, 0)))
    res = {n: (ok, m) for n, ok, m in asyncio.run(O.check(bot))}
    assert all(ok for ok, _ in res.values())
    assert res["paper order"][1].startswith("paper: bought 1")
    assert "-> canceled" in res["last 10 orders"][1] and res["open positions"][1] == "none"
    bot = _bot(tmp_path, BadFeed(day, 400.0, 401.0), Ex([401.0]), _times(day, (10, 0)))
    res = {n: (ok, m) for n, ok, m in asyncio.run(O.check(bot))}
    assert res["09:30 five-minute bar"] == (False, "RuntimeError: alpaca data /v2/stocks/bars -> 403: forbidden")
    assert res["quote"][0]


def test_session_flattens_a_leftover_position_first(tmp_path):
    day = dt.date(2026, 10, 19)

    class Ex(FakeExec):
        async def positions(self):
            return {"QQQ": 133.0}

    ex = Ex([401.0, 401.0, 402.0])                                         # short from 401, stopped at 402
    bot = _bot(tmp_path, FakeFeed(day, 400.0, 399.0), ex, _times(day, (9, 35), (9, 36), (9, 37), (9, 38)))
    rec = asyncio.run(bot.run_session(day))
    assert ex.orders[0] == ("close", 133.0, 401.0) and ex.orders[1][0] == "sell"
    assert rec["flattened_leftover"]["shares"] == 133.0
