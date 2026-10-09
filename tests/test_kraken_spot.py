"""Kraken spot executor and the carry bot's two-leg failure handling."""

import asyncio
import base64
import datetime as dt
import urllib.parse

import httpx
import pytest

from cryptobot.execution.kraken_spot import (KrakenSpotExecutor, SpotExecConfig, SpotFill,
                                             floor_to, sign)
from cryptobot.execution.perp_exchange import Fill, PerpExecConfig
from cryptobot import carry_bot as CB

KEY_ENV = {"CRYPTOBOT_ARM_LIVE": "yes", "CRYPTOBOT_KRAKEN_KEY": "k",
           "CRYPTOBOT_KRAKEN_SECRET": base64.b64encode(b"s" * 64).decode()}


class TestSigning:
    def test_matches_kraken_published_example(self):
        secret = ("kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5"
                  "nE9qa99HAZtuZuj6F1huXg==")
        data = {"nonce": "1616492376594", "ordertype": "limit", "pair": "XBTUSD",
                "price": "37500", "type": "buy", "volume": "1.25"}
        assert sign("/0/private/AddOrder", data, secret) == (
            "4/dpxb3iT4tp/ZCVEwSnEsLxx0bqyhLpdfOpc6fn7OR8+UClSV5n9E6aSS8MPtnRfp32bAb0nmbRn6H8ndwLUQ==")

    def test_floor_never_rounds_up(self):
        assert floor_to(1.23999, 2) == 1.23
        assert floor_to(5.0, 0) == 5.0

    def test_floor_tolerates_float_noise(self):
        assert floor_to(29 / 0.00001, 0) == 2_900_000


def _kraken(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://x")


def _public(req):
    if req.url.path.endswith("/AssetPairs"):
        return httpx.Response(200, json={"result": {"PEPEUSD": {
            "wsname": "PEPE/USD", "lot_decimals": 0, "pair_decimals": 9, "ordermin": "100"}}})
    if req.url.path.endswith("/Ticker"):
        return httpx.Response(200, json={"result": {"PEPEUSD": {
            "b": ["0.000010", "1", "1"], "a": ["0.000010", "1", "1"]}}})
    return None


class TestExecutor:
    def test_unarmed_is_a_dry_run(self, monkeypatch):
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
        ex = KrakenSpotExecutor(SpotExecConfig(live=True), client=_kraken(_public))
        assert not ex.armed
        f = asyncio.run(ex.buy("kPEPE", 30.0))
        assert f.dry_run and f.volume == pytest.approx(3_000_000)

    def test_arming_needs_key_and_secret(self, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
        monkeypatch.setenv("CRYPTOBOT_KRAKEN_KEY", "k")
        monkeypatch.delenv("CRYPTOBOT_KRAKEN_SECRET", raising=False)
        assert not KrakenSpotExecutor(SpotExecConfig(live=True)).armed

    def test_armed_buy_signs_posts_and_reads_the_fill(self, monkeypatch):
        for k, v in KEY_ENV.items():
            monkeypatch.setenv(k, v)
        seen = []

        def handler(req):
            pub = _public(req)
            if pub:
                return pub
            body = dict(urllib.parse.parse_qsl(req.content.decode()))
            seen.append((req.url.path, body, req.headers))
            if req.url.path.endswith("/AddOrder"):
                return httpx.Response(200, json={"error": [], "result": {"txid": ["T1"]}})
            return httpx.Response(200, json={"error": [], "result": {"T1": {
                "status": "closed", "vol_exec": body and "2900000", "price": "0.0000101"}}})
        ex = KrakenSpotExecutor(SpotExecConfig(live=True, max_trade_usd=50),
                                client=_kraken(handler))
        f = asyncio.run(ex.buy("kPEPE", 29.0))
        path, body, headers = seen[0]
        assert path == "/0/private/AddOrder"
        assert body["type"] == "buy" and body["timeinforce"] == "IOC"
        assert body["volume"] == "2900000"                    # lot_decimals 0, floored
        assert float(body["price"]) == pytest.approx(0.0000101)   # mid +1%
        assert headers["API-Key"] == "k" and headers["API-Sign"]
        assert int(seen[1][1]["nonce"]) > int(body["nonce"])  # nonce strictly increases
        assert f.txid == "T1" and f.volume == 2_900_000 and not f.dry_run

    def test_notional_capped(self, monkeypatch):
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
        ex = KrakenSpotExecutor(SpotExecConfig(max_trade_usd=20), client=_kraken(_public))
        assert asyncio.run(ex.buy("kPEPE", 500.0)).notional == pytest.approx(20.0)

    def test_volume_under_minimum_is_refused(self, monkeypatch):
        for k, v in KEY_ENV.items():
            monkeypatch.setenv(k, v)
        ex = KrakenSpotExecutor(SpotExecConfig(live=True), client=_kraken(_public))
        with pytest.raises(ValueError, match="minimum"):
            asyncio.run(ex.sell("kPEPE", 50))

    def test_api_error_raises(self, monkeypatch):
        for k, v in KEY_ENV.items():
            monkeypatch.setenv(k, v)

        def handler(req):
            return _public(req) or httpx.Response(
                200, json={"error": ["EOrder:Insufficient funds"]})
        ex = KrakenSpotExecutor(SpotExecConfig(live=True), client=_kraken(handler))
        with pytest.raises(RuntimeError, match="Insufficient funds"):
            asyncio.run(ex.buy("kPEPE", 30.0))

    def test_unfilled_ioc_raises(self, monkeypatch):
        for k, v in KEY_ENV.items():
            monkeypatch.setenv(k, v)

        def handler(req):
            if _public(req):
                return _public(req)
            if req.url.path.endswith("/AddOrder"):
                return httpx.Response(200, json={"error": [], "result": {"txid": ["T"]}})
            return httpx.Response(200, json={"error": [], "result": {"T": {
                "status": "canceled", "vol_exec": "0"}}})
        ex = KrakenSpotExecutor(SpotExecConfig(live=True), client=_kraken(handler))
        with pytest.raises(RuntimeError, match="did not fill"):
            asyncio.run(ex.buy("kPEPE", 30.0))

    def test_unknown_pair_raises(self, monkeypatch):
        ex = KrakenSpotExecutor(SpotExecConfig(), client=_kraken(_public))
        with pytest.raises(ValueError, match="no Kraken USD pair"):
            asyncio.run(ex.buy("NOPE", 10.0))


class FakeKrakenAPI:
    """Order book + order lifecycle. `fills` decides each resting order's
    outcome in turn: a fraction of its volume that fills before cancel,
    or "reject" for a post-only order that would have crossed."""

    def __init__(self, fills, bid=0.000010, ask=0.0000102):
        self.fills, self.bid, self.ask = list(fills), bid, ask
        self.orders, self.added, self.cancelled = {}, [], []

    def __call__(self, req):
        pub = _public(req)
        if req.url.path.endswith("/Ticker"):
            return httpx.Response(200, json={"result": {"PEPEUSD": {
                "b": [str(self.bid), "1", "1"], "a": [str(self.ask), "1", "1"]}}})
        if pub:
            return pub
        body = dict(urllib.parse.parse_qsl(req.content.decode()))
        path = req.url.path
        if path.endswith("/AddOrder"):
            self.added.append(body)
            if body.get("oflags") == "post":
                outcome = self.fills.pop(0)
                if outcome == "reject":
                    return httpx.Response(200, json={"error": ["EOrder:Post only order"]})
            else:
                outcome = 1.0                        # taker IOC fills
            txid = f"T{len(self.added)}"
            vol = float(body["volume"])
            self.orders[txid] = {"status": "closed" if outcome == 1.0 else "open",
                                 "vol_exec": str(vol * outcome), "price": body["price"]}
            return httpx.Response(200, json={"error": [], "result": {"txid": [txid]}})
        if path.endswith("/CancelOrder"):
            self.cancelled.append(body["txid"])
            self.orders[body["txid"]]["status"] = "canceled"
            return httpx.Response(200, json={"error": [], "result": {"count": 1}})
        if path.endswith("/QueryOrders"):
            return httpx.Response(200, json={"error": [], "result": {
                body["txid"]: self.orders[body["txid"]]}})
        return httpx.Response(404)


class TestMakerLoop:
    def _ex(self, monkeypatch, api, **cfg):
        for k, v in KEY_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setattr(asyncio, "sleep", _nosleep)
        return KrakenSpotExecutor(SpotExecConfig(live=True, maker_wait_s=10, maker_poll_s=5,
                                                 maker_reprices=2, **cfg),
                                  client=_kraken(api))

    def test_full_maker_fill_at_the_bid(self, monkeypatch):
        api = FakeKrakenAPI([1.0])
        f = asyncio.run(self._ex(monkeypatch, api).buy_maker("kPEPE", 30.0))
        assert api.added[0]["oflags"] == "post"
        assert float(api.added[0]["price"]) == pytest.approx(0.000010)     # the bid
        assert f.maker_volume == f.volume and len(api.added) == 1

    def test_unfilled_rests_are_cancelled_repriced_then_taken(self, monkeypatch):
        api = FakeKrakenAPI([0.0, 0.0, 0.0])
        f = asyncio.run(self._ex(monkeypatch, api).buy_maker("kPEPE", 30.0))
        assert len(api.cancelled) == 3
        assert [a.get("oflags") for a in api.added] == ["post", "post", "post", None]
        assert api.added[-1]["timeinforce"] == "IOC"
        assert f.maker_volume == 0 and f.volume > 0

    def test_partial_maker_then_taker_for_the_rest(self, monkeypatch):
        api = FakeKrakenAPI([0.5, 0.0, 0.0])
        f = asyncio.run(self._ex(monkeypatch, api).buy_maker("kPEPE", 30.0))
        assert f.maker_volume == pytest.approx(f.volume * 0.5, rel=0.01)
        assert float(api.added[-1]["volume"]) == pytest.approx(f.volume * 0.5, rel=0.01)

    def test_post_only_rejection_is_a_zero_fill_not_an_error(self, monkeypatch):
        api = FakeKrakenAPI(["reject", 1.0])
        f = asyncio.run(self._ex(monkeypatch, api).buy_maker("kPEPE", 30.0))
        assert f.maker_volume == f.volume and len(api.added) == 2

    def test_maker_sell_rests_at_the_ask(self, monkeypatch):
        api = FakeKrakenAPI([1.0])
        asyncio.run(self._ex(monkeypatch, api).sell_maker("kPEPE", 3_000_000))
        assert api.added[0]["type"] == "sell"
        assert float(api.added[0]["price"]) == pytest.approx(0.0000102)

    def test_dry_run_reports_a_maker_fill(self, monkeypatch):
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
        ex = KrakenSpotExecutor(SpotExecConfig(), client=_kraken(FakeKrakenAPI([])))
        f = asyncio.run(ex.buy_maker("kPEPE", 30.0))
        assert f.dry_run and f.maker_volume == f.volume


_real_sleep = asyncio.sleep


async def _nosleep(*_a, **_k):
    await _real_sleep(0)


# --------------------------------------------------------------- two-leg logic

T0 = float(int(dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc).timestamp()))


class Perp:
    armed = True

    def __init__(self, fail_open=False, fail_close=False):
        self.fail_open, self.fail_close, self.calls = fail_open, fail_close, []

    async def open_short(self, coin, notional, mid):
        self.calls.append(("short", coin, notional))
        if self.fail_open:
            raise RuntimeError("perp down")
        return Fill(coin, "short", notional / mid, mid)

    async def close(self, coin, qty, mid):
        self.calls.append(("close", coin, qty))
        if self.fail_close:
            raise RuntimeError("perp close down")
        return Fill(coin, "close", qty, mid)


class Spot:
    armed = True

    def __init__(self, fail_buy=False, fail_sell=False):
        self.fail_buy, self.fail_sell, self.calls = fail_buy, fail_sell, []

    async def buy(self, coin, notional):
        self.calls.append(("buy", coin, notional))
        if self.fail_buy:
            raise RuntimeError("kraken down")
        return SpotFill("P", "buy", notional / 1.0, 1.0, "T")

    async def sell(self, coin, vol):
        self.calls.append(("sell", coin, vol))
        if self.fail_sell:
            raise RuntimeError("kraken down")
        return SpotFill("P", "sell", vol, 1.0, "T")

    async def buy_maker(self, coin, notional):
        self.calls.append(("buy_maker", coin, notional))
        if self.fail_buy:
            raise RuntimeError("kraken down")
        vol = self.partial * notional if hasattr(self, "partial") else notional
        return SpotFill("P", "buy", vol, 1.0, "T", maker_volume=vol)

    async def sell_maker(self, coin, vol):
        self.calls.append(("sell_maker", coin, vol))
        if self.fail_sell:
            raise RuntimeError("kraken down")
        return SpotFill("P", "sell", vol, 1.0, "T", maker_volume=vol)

    async def close(self):
        pass


def _bot(monkeypatch, perp, spot, maker=False):
    import sys
    sys.path.insert(0, "tests")
    from test_carry_bot import FakeHL, FakeKraken
    monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
    daily = {"A": 0.002}
    hl = FakeHL({"A": 1.0}, {"A": 0.0001}, daily)
    bot = CB.CarryBot(CB.CarryConfig(coins=("A",), maker_spot=maker), 200.0, 1000.0,
                      PerpExecConfig(), hl=hl, kraken=FakeKraken({"A": 1.0}),
                      executor=perp, spot_executor=spot)
    assert bot.set_mode("real")[0]
    return bot, hl


class TestTwoLegs:
    def test_both_legs_fill_and_record_quantities(self, monkeypatch):
        perp, spot = Perp(), Spot()
        bot, _ = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        pos = bot.books["real"].positions["A"]
        assert pos.perp_qty > 0 and pos.spot_volume > 0
        assert spot.calls[0][2] == pytest.approx(perp.calls[0][2])   # same notional

    def test_spot_failure_unwinds_the_perp(self, monkeypatch):
        perp, spot = Perp(), Spot(fail_buy=True)
        bot, _ = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        assert [c[0] for c in perp.calls] == ["short", "close"]
        assert "A" not in bot.books["real"].positions
        assert "A" in bot.books["sim"].positions                       # sim unaffected
        assert "unwound" in bot.journal.recent(5, book="real")[0]["reason"]

    def test_unwind_failure_is_recorded_not_hidden(self, monkeypatch):
        perp, spot = Perp(fail_close=True), Spot(fail_buy=True)
        bot, _ = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        pos = bot.books["real"].positions["A"]
        assert pos.spot_volume == 0.0 and pos.perp_qty > 0
        assert "NAKED SHORT" in bot.journal.recent(5, book="real")[0]["reason"]

    def test_perp_failure_never_buys_spot(self, monkeypatch):
        perp, spot = Perp(fail_open=True), Spot()
        bot, _ = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        assert spot.calls == [] and "A" not in bot.books["real"].positions

    def test_exit_closes_perp_first_and_queues_a_failed_spot_sell(self, monkeypatch):
        perp, spot = Perp(), Spot(fail_sell=True)
        bot, hl = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        hl.daily["A"] = -0.001
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert perp.calls[-1][0] == "close"
        assert "A" not in bot.books["real"].positions
        assert bot.books["real"].pending_spot_sells["A"] > 0
        spot.fail_sell = False
        asyncio.run(bot.monitor())
        assert bot.books["real"].pending_spot_sells == {}

    def test_perp_close_failure_keeps_both_legs(self, monkeypatch):
        perp, spot = Perp(), Spot()
        bot, hl = _bot(monkeypatch, perp, spot)
        asyncio.run(bot.run_daily())
        perp.fail_close = True
        hl.daily["A"] = -0.001
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert "A" in bot.books["real"].positions
        assert not [c for c in spot.calls if c[0] == "sell"]

    def test_real_mode_needs_both_legs_armed(self, monkeypatch):
        import sys
        sys.path.insert(0, "tests")
        from test_carry_bot import FakeHL, FakeKraken
        for perp_armed, spot_armed in ((True, False), (False, True)):
            p, s = Perp(), Spot()
            p.armed, s.armed = perp_armed, spot_armed
            bot = CB.CarryBot(CB.CarryConfig(coins=("A",)), 200.0, 1000.0, PerpExecConfig(),
                              hl=FakeHL({"A": 1.0}, {}, {}), kraken=FakeKraken({"A": 1.0}),
                              executor=p, spot_executor=s)
            ok, why = bot.set_mode("real")
            assert not ok and "BOTH legs" in why

    # --- maker path: spot first, perp for what filled -----------------------
    def test_maker_entry_buys_spot_first_then_shorts_the_filled_amount(self, monkeypatch):
        perp, spot = Perp(), Spot()
        spot.partial = 0.6                                    # only 60% filled
        bot, _ = _bot(monkeypatch, perp, spot, maker=True)
        asyncio.run(bot.run_daily())
        assert spot.calls[0][0] == "buy_maker" and perp.calls[0][0] == "short"
        assert perp.calls[0][2] == pytest.approx(0.6 * spot.calls[0][2])
        pos = bot.books["real"].positions["A"]
        assert pos.notional_usd == pytest.approx(0.6 * spot.calls[0][2])

    def test_maker_spot_failure_never_touches_the_perp(self, monkeypatch):
        perp, spot = Perp(), Spot(fail_buy=True)
        bot, _ = _bot(monkeypatch, perp, spot, maker=True)
        asyncio.run(bot.run_daily())
        assert perp.calls == [] and "A" not in bot.books["real"].positions

    def test_maker_perp_failure_sells_the_spot_back(self, monkeypatch):
        perp, spot = Perp(fail_open=True), Spot()
        bot, _ = _bot(monkeypatch, perp, spot, maker=True)
        asyncio.run(bot.run_daily())
        assert [c[0] for c in spot.calls] == ["buy_maker", "sell"]
        assert "A" not in bot.books["real"].positions
        assert "spot sold back" in bot.journal.recent(5, book="real")[0]["reason"]

    def test_maker_perp_failure_queues_spot_if_sellback_fails(self, monkeypatch):
        perp, spot = Perp(fail_open=True), Spot(fail_sell=True)
        bot, _ = _bot(monkeypatch, perp, spot, maker=True)
        asyncio.run(bot.run_daily())
        assert bot.books["real"].pending_spot_sells["A"] > 0

    def test_maker_exit_closes_perp_then_sells_spot_as_maker(self, monkeypatch):
        perp, spot = Perp(), Spot()
        bot, hl = _bot(monkeypatch, perp, spot, maker=True)
        asyncio.run(bot.run_daily())
        hl.daily["A"] = -0.001
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert perp.calls[-1][0] == "close" and spot.calls[-1][0] == "sell_maker"

    def test_maker_fees_in_the_round_trip(self):
        # Kraken tier 1 since 2026-07-09: 0.40% maker / 0.80% taker (was 0.16% / 0.26%)
        assert CB.round_trip_fraction(True) == pytest.approx(2 * (0.00035 + 0.0005) + 2 * 0.0040)
        assert CB.round_trip_fraction(False) == pytest.approx(2 * (0.00035 + 0.0005) + 2 * (0.0080 + 0.0005))

    def test_pending_sells_survive_restart(self, tmp_path):
        b = CB.CarryBook("real", 1000.0, executes=True, state_file=tmp_path / "r.json")
        b.pending_spot_sells["A"] = 123.0
        b.save()
        b2 = CB.CarryBook("real", 1000.0, executes=True, state_file=tmp_path / "r.json")
        b2.load()
        assert b2.pending_spot_sells == {"A": 123.0}
