"""Regression tests for the findings of the 2026-10-12 code review."""

import asyncio
import datetime as dt
import json

import httpx
import pytest

from cryptobot import vrp_collect as V
from cryptobot import pead_collect as C
from cryptobot import intraday_leadlag as L
from cryptobot.data import nasdaq as N
from cryptobot.execution.alpaca import AlpacaConfig, AlpacaExecutor
from tests.test_brokers import FakeHttp as AlpacaFake
from tests.test_vrp_collect import FakeClient, _chain, _closes_payload


def test_nasdaq_money_handles_display_strings():
    assert N.money("$671.23") == 671.23 and N.money("($0.13)") == -0.13 and N.money("1,000") == 1000.0
    assert N.money("-4.44%") == -4.44 and N.money("N/A") is None and N.money("--") is None
    rows = N.parse_history({"data": {"tradesTable": {"rows": [
        {"date": "10/09/2026", "close": "$671.23", "open": "$670.00", "high": "$672", "low": "$669", "volume": "1,000"}]}}})
    assert rows[0]["close"] == 671.23 and rows[0]["volume"] == 1000.0
    assert N.parse_closes({"data": {"tradesTable": {"rows": [{"date": "10/09/2026", "close": "$1.5"}]}}}) == \
        [(dt.date(2026, 10, 9), 1.5)]
    assert not N.payload_ok({"data": None, "status": {"rCode": 400}}) and N.payload_ok({"data": {"rows": []}})


def test_weekend_and_stale_quotes_are_never_stored(tmp_path):
    fake = FakeClient(_chain(), _closes_payload(), [])
    c = V.Collector(tmp_path, client=fake, now=lambda: dt.datetime(2026, 10, 12, 21, 15, tzinfo=dt.timezone.utc))
    assert asyncio.run(c.options_snapshot(dt.date(2026, 10, 10))) is None          # Saturday
    assert not c.options_file.exists() and not c.closes_file.exists()
    stale = {"timestamp": "2026-10-09T20:00:00", "data": _chain(asof=dt.date(2026, 10, 12))}
    assert asyncio.run(c.options_snapshot(dt.date(2026, 10, 12), chain=stale)) is None   # Friday's quotes on Monday
    assert not c.closes_file.exists()
    fresh = {"timestamp": "2026-10-12T20:05:00", "data": _chain(asof=dt.date(2026, 10, 12))}
    row = asyncio.run(c.options_snapshot(dt.date(2026, 10, 12), chain=fresh))
    assert row and row["date"] == "2026-10-12"
    assert V.read_jsonl(c.closes_file)[-1]["date"] == "2026-10-12"


class ThrottledNasdaq:
    """First N answers are Nasdaq's 200-with-data=null throttle."""

    def __init__(self, throttles: int, rows):
        self.left, self.rows, self.calls = throttles, rows, 0

    async def get(self, url, params=None):
        self.calls += 1

        class R:
            status_code = 200

            def __init__(self, b):
                self._b = b

            def json(self):
                return self._b
        if self.left > 0:
            self.left -= 1
            return R({"data": None, "status": {"rCode": 400}})
        if "calendar" in url:
            return R({"data": {"rows": self.rows}})
        return R({"data": {"tradesTable": {"rows": self.rows}}})

    async def aclose(self):
        pass


def test_throttled_calendar_day_is_retried_not_marked(tmp_path, monkeypatch):
    async def nosleep(*_a, **_k):
        return None
    monkeypatch.setattr(asyncio, "sleep", nosleep)
    rows = [{"symbol": "AAA", "eps": "$1", "epsForecast": "$0.9", "surprise": "11.1", "noOfEsts": "4", "marketCap": "$1,000"}]
    c = C.PeadCollector(tmp_path, client=ThrottledNasdaq(2, rows), pause_s=0.0)
    assert asyncio.run(c.calendar(dt.date(2026, 10, 9), dt.date(2026, 10, 9))) == 1
    assert c.days_done() == {"2026-10-09"}
    dead = C.PeadCollector(tmp_path / "b", client=ThrottledNasdaq(99, rows), pause_s=0.0)
    with pytest.raises(RuntimeError, match="gave up"):
        asyncio.run(dead.calendar(dt.date(2026, 10, 9), dt.date(2026, 10, 9)))
    assert dead.days_done() == set()


def test_failed_price_fetch_leaves_no_file_and_empty_days_can_be_refetched(tmp_path, monkeypatch):
    async def nosleep(*_a, **_k):
        return None
    monkeypatch.setattr(asyncio, "sleep", nosleep)
    c = C.PeadCollector(tmp_path, client=ThrottledNasdaq(99, []), pause_s=0.0)
    assert asyncio.run(c.prices(["AAA"])) == 0
    assert not (tmp_path / "earnings" / "prices" / "AAA.json").exists()
    c._mark_day(dt.date(2026, 10, 8))
    c._mark_day(dt.date(2026, 10, 9))
    C.append_jsonl(c.calendar_file, {"date": "2026-10-09", "symbol": "AAA"})
    assert c.empty_days() == ["2026-10-08"]
    c.unmark_days(["2026-10-08"])
    assert c.days_done() == {"2026-10-09"}


def test_alpaca_keeps_polling_through_partial_fills(monkeypatch):
    async def nosleep(*_a, **_k):
        return None
    monkeypatch.setattr(asyncio, "sleep", nosleep)
    polls = iter([{"status": "partially_filled", "filled_qty": "3"},
                  {"status": "partially_filled", "filled_qty": "7"},
                  {"status": "canceled", "filled_qty": "7", "filled_avg_price": "120.1"}])
    http = AlpacaFake({("POST", "/v2/orders"): {"id": "a1", "status": "accepted"},
                       ("GET", "/v2/orders/a1"): lambda _b: next(polls)})
    ex = AlpacaExecutor(AlpacaConfig(max_trade_usd=5000), http, key_id="k", secret="s")
    fill = asyncio.run(ex.open_long("QQQ", 1200.0, 120.0))
    assert fill.qty == 7 and fill.price == pytest.approx(120.1)


def test_kraken_close_sends_volume_zero_reduce_only(monkeypatch):
    from tests.test_kraken_margin import FakeKraken, _ex
    api = FakeKraken()
    ex = _ex(monkeypatch, api)
    api.orders.clear()
    asyncio.run(ex.close("kPEPE", 1.49999999, 0.003955))
    _, body = api.private[0]
    assert body["volume"] == "0" and body["reduce_only"] == "true" and body["type"] == "buy"


def test_follow_rule_is_flat_through_the_session():
    base = int(dt.datetime(2026, 10, 12, 0, 0, tzinfo=L.ET).timestamp())
    rows = []
    for h in range(48):
        ts = base + h * 3600
        rows.append({"ts": ts, "ra": 0.01, "rb": 0.0, "open": L.cash_open(ts), "ra_next": 0.0, "rb_next": 0.0})
    f = L.follow_rule(rows, "closed", cost_rt=0.001, threshold=0.001)
    closed_hours = [r for r in rows if not r["open"]]
    assert f["hours"] == len(closed_hours) and f["trades"] == len(closed_hours)
    # two evenings' worth of entries plus the exits at each session open: more than one round trip
    assert f["total"] < -0.001 * 1.5
