import asyncio
import datetime as dt
import json
import math

import pytest

from cryptobot import vrp_collect as V


def test_parse_symbol():
    assert V.parse_symbol("IBIT261218P00060000") == (dt.date(2026, 12, 18), "P", 60.0)
    assert V.parse_symbol("IBIT261012C00030000") == (dt.date(2026, 10, 12), "C", 30.0)
    assert V.parse_symbol("SPY261218P00060000") is None
    assert V.parse_symbol("IBIT26121XP00060000") is None


def _chain(spot=46.6, asof=dt.date(2026, 10, 12)):
    opts = []
    for days, iv in ((18, 0.34), (46, 0.38)):
        exp = (asof + dt.timedelta(days=days)).strftime("%y%m%d")
        for k in (40, 44, 46, 47, 50, 55):
            d_call = max(0.02, min(0.98, 0.5 - (k - spot) * 0.08))
            opts.append({"option": f"IBIT{exp}C{int(k*1000):08d}", "bid": 1.0, "ask": 1.1, "iv": iv + 0.01 * abs(k - spot) / 5,
                         "delta": d_call, "open_interest": 10})
            opts.append({"option": f"IBIT{exp}P{int(k*1000):08d}", "bid": 1.0, "ask": 1.2, "iv": iv + 0.02 * abs(k - spot) / 5,
                         "delta": d_call - 1.0, "open_interest": 5})
    # an expired and a zero-IV contract are ignored
    opts.append({"option": "IBIT250101C00040000", "bid": 1, "ask": 1, "iv": 0.5, "delta": 0.5})
    opts.append({"option": f"IBIT{(asof + dt.timedelta(days=18)).strftime('%y%m%d')}C00030000", "bid": 16, "ask": 17,
                 "iv": 0.0, "delta": 1.0})
    return {"current_price": spot, "close": spot, "iv30": 36.4, "options": opts}


def test_surface_picks_atm_and_25_delta_per_expiry():
    s = V.surface(_chain(), dt.date(2026, 10, 12))
    assert s["spot"] == 46.6 and [e["days"] for e in s["expiries"]] == [18, 46]
    e = s["expiries"][0]
    assert e["atm_strike"] == 47 and abs(e["atm_iv"] - 0.3412) < 1e-3     # mean of call/put IV at 47
    assert e["skew25"] == pytest.approx(e["put25_iv"] - e["call25_iv"])
    assert e["atm_spread"] == pytest.approx(((0.1 / 1.05) + (0.2 / 1.1)) / 2)
    assert e["n"] == 12 and e["oi"] == 90


def test_interp_iv_is_variance_time_weighted():
    exps = [{"days": 18, "atm_iv": 0.34}, {"days": 46, "atm_iv": 0.38}]
    v = V.interp_iv(exps, 30)
    w = (30 - 18) / (46 - 18)
    assert v == pytest.approx(math.sqrt(((1 - w) * 0.34 ** 2 * 18 + w * 0.38 ** 2 * 46) / 30))
    assert V.interp_iv([{"days": 18, "atm_iv": 0.34}], 30) == 0.34        # one side only
    assert V.interp_iv([], 30) is None


def test_realised_vol_and_nasdaq_parse():
    closes = [100 * math.exp(0.01 * ((-1) ** i)) for i in range(40)]
    rv = V.realised_vol(closes, 20)
    assert rv == pytest.approx(0.02 * math.sqrt(252), rel=1e-6)
    assert V.realised_vol(closes[:10], 20) is None
    rows = V.parse_nasdaq_closes({"data": {"tradesTable": {"rows": [
        {"date": "10/09/2026", "close": "$46.55"}, {"date": "10/08/2026", "close": "46.00"}]}}})
    assert rows == [(dt.date(2026, 10, 8), 46.0), (dt.date(2026, 10, 9), 46.55)]


class FakeClient:
    def __init__(self, chain, closes_payload, candles):
        self.chain, self.closes_payload, self.candles = chain, closes_payload, candles
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append(url)

        class R:
            status_code = 200

            def __init__(self, body):
                self._b = body

            def json(self):
                return self._b
        if "cboe" in url:
            return R(self.chain)
        if "nasdaq" in url:
            return R(self.closes_payload)
        return R({"candlesticks": self.candles})

    async def aclose(self):
        pass


def _closes_payload(n=60):
    rows = [{"date": (dt.date(2026, 10, 9) - dt.timedelta(days=i)).strftime("%m/%d/%Y"), "close": f"{46 + 0.1 * (i % 5):.2f}"}
            for i in range(n)]
    return {"data": {"tradesTable": {"rows": rows}}}


def test_snapshot_writes_once_per_day_and_gates_on_iv_minus_rv(tmp_path):
    candles = [{"end_period_ts": 1_000_000 + 3600 * i, "price": {"open": "1", "high": "1", "low": "1", "close": "1"},
                "volume": "5"} for i in range(3)]
    fake = FakeClient(_chain(), _closes_payload(), candles)
    after_close = dt.datetime(2026, 10, 12, 21, 15, tzinfo=dt.timezone.utc)
    c = V.Collector(tmp_path, client=fake, symbol="IBIT", now=lambda: after_close)
    asof = dt.date(2026, 10, 12)
    row = asyncio.run(c.options_snapshot(asof))
    assert row and row["date"] == "2026-10-12" and row["iv30_cboe"] == pytest.approx(0.364)
    assert 0.33 < row["iv30_atm"] < 0.40 and row["rv20"] is not None and row["gate_open"] is not None
    assert row["gate_open"] == (row["iv_minus_rv20"] >= 0.05)
    assert asyncio.run(c.options_snapshot(asof)) is None                    # same day: skipped
    assert len(V.read_jsonl(c.options_file)) == 1
    closes = V.read_jsonl(c.closes_file)
    assert closes[-1]["date"] == "2026-10-12" and closes[-1]["close"] == 46.6   # today's spot appended
    added = asyncio.run(c.kalshi_hourly(tickers=("KXBTCPERP",)))
    assert added == {"KXBTCPERP": 3}
    assert asyncio.run(c.kalshi_hourly(tickers=("KXBTCPERP",))) == {"KXBTCPERP": 0}   # deduplicated
    text = V.report(tmp_path)
    assert "1 days" in text and "2026-10-12" in text


def test_run_once_survives_a_failing_source(tmp_path):
    class Boom(FakeClient):
        async def get(self, url, params=None):
            if "cboe" in url:
                raise RuntimeError("down")
            return await super().get(url, params)
    c = V.Collector(tmp_path, client=Boom(_chain(), _closes_payload(), []))
    out = asyncio.run(c.run_once())
    assert out["options"].startswith("ERROR") and out["kalshi_hourly"]


def test_snapshot_waits_for_the_close_on_a_trading_day(tmp_path):
    fake = FakeClient(_chain(), _closes_payload(), [])
    mid_session = dt.datetime(2026, 10, 12, 15, 0, tzinfo=dt.timezone.utc)      # 11:00 New York
    c = V.Collector(tmp_path, client=fake, now=lambda: mid_session)
    assert asyncio.run(c.options_snapshot()) is None and not c.options_file.exists()
    assert not V.market_closed_for_today(mid_session)
    assert V.market_closed_for_today(dt.datetime(2026, 10, 12, 20, 6, tzinfo=dt.timezone.utc))   # 16:06 New York (EDT)
    assert V.market_closed_for_today(dt.datetime(2026, 10, 10, 15, 0, tzinfo=dt.timezone.utc))   # Saturday
    # yesterday's date can be stored at any hour (a catch-up run); the quote date must still match
    old_chain = {"timestamp": "2026-10-09T20:05:00", "data": _chain(asof=dt.date(2026, 10, 9))}
    row = asyncio.run(c.options_snapshot(dt.date(2026, 10, 9), chain=old_chain))
    assert row and row["date"] == "2026-10-09"

