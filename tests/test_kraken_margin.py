"""Kraken Pro spot-margin venue: executor, data client, bot and desk wiring."""

import asyncio
import base64
import pickle
import urllib.parse

import httpx
import pytest

from cryptobot.execution.kraken_margin import (US_COINS, KrakenMarginConfig, KrakenMarginExecutor,
                                               parse_rollover, units)
from cryptobot.execution.perp_exchange import SizeTooSmall

SECRET = base64.b64encode(b"s" * 64).decode()
PAIRS = {
    "XDGUSD": {"wsname": "XDG/USD", "lot_decimals": 8, "pair_decimals": 7, "ordermin": "50"},
    "PEPEUSD": {"wsname": "PEPE/USD", "lot_decimals": 5, "pair_decimals": 9, "ordermin": "1500000"},
    "SHIBUSD": {"wsname": "SHIB/USD", "lot_decimals": 5, "pair_decimals": 9, "ordermin": "770000"},
}
TICKER = {"XDGUSD": ("0.0853", "0.0854"), "PEPEUSD": ("0.000003950", "0.000003960"),
          "SHIBUSD": ("0.000005450", "0.000005460")}


class FakeKraken:
    def __init__(self, fill_ratio=1.0, fee="0.05", error=None):
        self.fill_ratio, self.fee, self.error = fill_ratio, fee, error
        self.private = []          # (method, body)
        self.orders = {}

    def __call__(self, req):
        path = req.url.path
        if path.endswith("/AssetPairs"):
            return httpx.Response(200, json={"result": PAIRS})
        if path.endswith("/Ticker"):
            return httpx.Response(200, json={"result": {
                p: {"b": [b, "1", "1"], "a": [a, "1", "1"]} for p, (b, a) in TICKER.items()}})
        if path.endswith("/OHLC"):
            pair = req.url.params["pair"]
            rows = [[1790000000 + i * 86400, "0.0000039", "0.0000041", "0.0000038", "0.0000040",
                     "0.0000040", "1000000000", 10] for i in range(3)]
            return httpx.Response(200, json={"result": {pair: rows, "last": 0}})
        method = path.rsplit("/", 1)[-1]
        body = dict(urllib.parse.parse_qsl(req.content.decode()))
        self.private.append((method, body))
        assert req.headers["API-Key"] == "k" and req.headers["API-Sign"]
        if self.error and method == "AddOrder":
            return httpx.Response(200, json={"error": [self.error]})
        if method == "AddOrder":
            if body.get("validate") == "true":
                return httpx.Response(200, json={"error": [], "result": {"descr": {"order": "ok"}}})
            txid = f"O{len(self.orders) + 1}"
            self.orders[txid] = {"status": "closed", "vol_exec": str(float(body["volume"]) * self.fill_ratio),
                                 "price": body["price"], "fee": self.fee}
            return httpx.Response(200, json={"error": [], "result": {"txid": [txid]}})
        if method == "QueryOrders":
            return httpx.Response(200, json={"error": [], "result": {body["txid"]: self.orders[body["txid"]]}})
        if method == "OpenPositions":
            return httpx.Response(200, json={"error": [], "result": {
                "P1": {"pair": "PEPEUSD", "type": "sell", "vol": "3000000", "vol_closed": "500000",
                       "cost": "11.8", "fee": "0.02", "margin": "5.9", "net": "0.1", "time": "1790000000",
                       "terms": "0.0200% per 4 hours"},
                "P2": {"pair": "PEPEUSD", "type": "sell", "vol": "1500000", "vol_closed": "0",
                       "terms": "0.0300% per 4 hours"},
                "P3": {"pair": "XBTUSD", "type": "buy", "vol": "0.01", "vol_closed": "0"}}})
        if method == "TradeBalance":
            return httpx.Response(200, json={"error": [], "result": {
                "eb": "260", "tb": "250", "m": "12.5", "n": "-1.25", "e": "248.75", "mf": "236.25", "ml": "1990"}})
        return httpx.Response(404)


def _ex(monkeypatch, api, armed=True, **cfg):
    if armed:
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
    else:
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    monkeypatch.setattr(asyncio, "sleep", _nosleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(api), base_url="https://x")
    return KrakenMarginExecutor(KrakenMarginConfig(live=True, **cfg), client=client, key="k", secret=SECRET)


async def _nosleep(*_a, **_k):
    return None


def test_units_and_rollover_parsing():
    assert units("kPEPE") == 1000 and units("kSHIB") == 1000 and units("DOGE") == 1
    assert parse_rollover("0.0200% per 4 hours") == pytest.approx(0.0002)
    assert parse_rollover("") is None
    assert US_COINS == ("DOGE", "kPEPE", "kSHIB")


def test_open_short_sells_on_margin_in_coin_units_and_returns_bot_units(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api)
    mid = 0.003955                                        # kPEPE: $ per 1,000 PEPE
    fill = asyncio.run(ex.open_short("kPEPE", 100.0, mid))
    method, body = api.private[0]
    assert method == "AddOrder" and body["type"] == "sell" and body["pair"] == "PEPEUSD"
    assert body["leverage"] == "2" and body["timeinforce"] == "IOC" and "reduce_only" not in body
    assert float(body["volume"]) == pytest.approx(100.0 / (mid / 1000), rel=1e-6)   # ~25.3M PEPE
    assert float(body["price"]) == pytest.approx(mid / 1000 * 0.995, abs=1e-9)   # floored to 9 decimals
    assert float(body["price"]) <= mid / 1000 * 0.995
    assert fill.qty == pytest.approx(float(body["volume"]) / 1000)
    assert fill.price == pytest.approx(float(body["price"]) * 1000)
    assert fill.fee_usd == pytest.approx(0.05) and fill.order_id == "O1" and not fill.dry_run


def test_leverage_is_clamped_to_us_maximum_and_kraken_minimum(monkeypatch):
    ex = _ex(monkeypatch, FakeKraken(), leverage=20)
    assert ex._leverage_for("DOGE") == 10 and ex._leverage_for("kPEPE") == 5
    ex = _ex(monkeypatch, FakeKraken(), leverage=1)
    assert ex._leverage_for("DOGE") == 2


def test_close_is_a_reduce_only_buy(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api)
    fill = asyncio.run(ex.close("DOGE", 1170.0, 0.08535))
    _, body = api.private[0]
    assert body["type"] == "buy" and body["reduce_only"] == "true" and body["pair"] == "XDGUSD"
    assert float(body["volume"]) == pytest.approx(1170.0)
    assert float(body["price"]) == pytest.approx(0.08535 * 1.005, abs=1e-7)
    assert fill.side == "close" and fill.qty == pytest.approx(1170.0)


def test_below_minimum_raises_without_sending(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api)
    with pytest.raises(SizeTooSmall, match="minimum"):
        asyncio.run(ex.open_short("kPEPE", 3.0, 0.003955))   # 1.5M PEPE is ~$5.9
    assert api.private == []


def test_unarmed_is_a_dry_run_with_no_private_calls(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api, armed=False)
    assert not ex.armed and ex.has_key
    f = asyncio.run(ex.open_short("DOGE", 50.0, 0.0853))
    assert f.dry_run and api.private == []
    f = asyncio.run(ex.close("DOGE", 500.0, 0.0853))
    assert f.dry_run and api.private == []


def test_unfilled_ioc_raises(monkeypatch):
    ex = _ex(monkeypatch, FakeKraken(fill_ratio=0.0))
    with pytest.raises(RuntimeError, match="did not fill"):
        asyncio.run(ex.open_short("DOGE", 50.0, 0.0853))


def test_validate_short_checks_without_trading_and_reports_errors(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api, armed=False)              # validate needs a key, not arming
    r = asyncio.run(ex.validate_short("kSHIB", 50.0, 0.005455))
    assert r["ok"] and r["pair"] == "SHIBUSD"
    assert api.private[0][1]["validate"] == "true" and api.orders == {}
    bad = _ex(monkeypatch, FakeKraken(error="EGeneral:Permission denied"), armed=False)
    r = asyncio.run(bad.validate_short("DOGE", 50.0, 0.0853))
    assert not r["ok"] and "Permission denied" in r["error"]


def test_positions_sum_kraken_positions_into_signed_bot_units(monkeypatch):
    ex = _ex(monkeypatch, FakeKraken())
    pos = asyncio.run(ex.positions())
    assert pos == {"kPEPE": pytest.approx(-(2_500_000 + 1_500_000) / 1000)}   # XBT is not ours
    rows = asyncio.run(ex.open_positions())
    assert sorted(r["rollover_per_4h"] for r in rows) == pytest.approx([0.0002, 0.0003])


def test_balance_maps_trade_balance(monkeypatch):
    b = asyncio.run(_ex(monkeypatch, FakeKraken()).balance())
    assert b["total_usd_balance"] == 248.75 and b["available_margin"] == 236.25
    assert b["margin_used"] == 12.5 and b["margin_level"] == 1990.0


def test_close_client_releases_http_without_touching_positions(monkeypatch):
    api = FakeKraken()
    ex = _ex(monkeypatch, api)
    asyncio.run(ex.close_client())
    assert api.private == []


# -- data client ----------------------------------------------------------------

def test_data_client_units_seed_and_borrow_as_negative_funding(tmp_path):
    from cryptobot.backtest import PoolMeta
    from cryptobot.data.geckoterminal import Candle
    from cryptobot.data.kraken_margin import KrakenMarginData
    meta = PoolMeta(chain="hyperliquid", pair_address="kPEPE", symbol="kPEPE", token_address="",
                    liquidity_usd=0.0, fdv_usd=None)
    seed = tmp_path / "seed.pkl"
    old = [Candle(ts=1789000000 + i * 86400, open=1, high=1, low=1, close=0.004, volume_usd=0) for i in range(20)]
    pickle.dump({"kPEPE": (meta, old)}, seed.open("wb"))
    client = httpx.AsyncClient(transport=httpx.MockTransport(FakeKraken()), base_url="https://x/0/public")
    md = KrakenMarginData(history_seed=seed, client=client, borrow_per_4h={"DOGE": 0.0004})
    cs = asyncio.run(md.candles("kPEPE"))
    kraken_part = [c for c in cs if c.ts >= 1790000000]
    assert len(kraken_part) == 3 and kraken_part[0].close == pytest.approx(0.0040)   # x1000
    assert all(c.ts < 1790000000 for c in cs[:-3]) and len(cs) == 3 + sum(1 for c in old if c.ts < 1790000000)
    f = asyncio.run(md.funding_rates())
    assert f["DOGE"] == pytest.approx(-0.0001) and f["kPEPE"] == pytest.approx(-0.0003 / 4)
    mids = asyncio.run(md.all_mids())
    assert mids["kPEPE"] == pytest.approx(0.003955) and mids["DOGE"] == pytest.approx(0.08535)


# -- fees, bot and desk wiring -----------------------------------------------------

def test_fee_tiers_and_carry_round_trip_follow_the_july_2026_schedule():
    from cryptobot.carry_bot import round_trip_fraction
    from cryptobot.data.kraken import MAKER_FEE, TAKER_FEE, fees_for_tier, margin_fee_4h
    assert (MAKER_FEE, TAKER_FEE) == (0.0040, 0.0080)
    assert fees_for_tier(3) == (0.0022, 0.0038) and fees_for_tier(0) == fees_for_tier(1)
    assert fees_for_tier(99) == (0.0, 0.0010)
    assert margin_fee_4h("kSHIB") == pytest.approx(0.0003) and margin_fee_4h("BTC") == pytest.approx(0.00015)
    assert round_trip_fraction(maker_spot=True) > 0.009       # was 0.49% before the change


def test_kraken_costs_and_bot_build():
    from cryptobot import perp_bot as PB
    from cryptobot.data.kraken_margin import KrakenMarginData
    assert "kraken" in PB.VENUES
    fee, fund = PB.kraken_costs({})
    assert fee == pytest.approx(0.0080 + 0.00015) and fund == pytest.approx(-0.0018)
    fee12, _ = PB.kraken_costs({"kraken_fee_tier": 12, "kraken_rollover_4h": 0.0002})
    assert fee12 == pytest.approx(0.0010 + 0.0001)
    bot = PB.build({"perp": {"venue": "kraken"}, "risk": {"bankroll_usd": 250},
                    "allocation": {"carry": 0.0, "bounce_short": 1.0}}, None)
    assert isinstance(bot.executor, KrakenMarginExecutor) and isinstance(bot.client, KrakenMarginData)
    assert bot.cfg.coins == US_COINS and bot.cfg.taker_fee == pytest.approx(fee)
    assert bot.cfg.contract_units == {}
    assert asyncio.run(bot.client.funding_rates())["DOGE"] == pytest.approx(-0.0003 / 4)


def test_desk_plan_and_preflight_for_the_kraken_venue():
    from cryptobot.desk import capital_plan, preflight
    cfg = {"perp": {"venue": "kraken"}, "risk": {"bankroll_usd": 250},
           "allocation": {"carry": 0.0, "bounce_short": 1.0}}
    plan = capital_plan(cfg)
    assert plan["venue"] == "kraken" and plan["kraken_usd"] == pytest.approx(250.0)
    assert plan["bounce_slot"] == pytest.approx(250 / 3)
    sizes = {"DOGE": 4.27, "kPEPE": 5.94, "kSHIB": 4.21,
             "_costs": {"tier": 1, "fee": 0.00815, "borrow_day": 0.0018},
             "_validate": [{"coin": "DOGE", "ok": True, "error": ""},
                           {"coin": "kPEPE", "ok": False, "error": "EGeneral:Permission denied"}]}
    checks = {name: (ok, fix) for name, ok, fix in preflight(cfg, {"CRYPTOBOT_KRAKEN_KEY": "k",
                                                                     "CRYPTOBOT_KRAKEN_SECRET": "s"}, None, sizes)}
    assert checks["Kraken API key + secret for spot margin"][0]
    assert any("clears Kraken's order minimum" in n and ok for n, (ok, _) in checks.items())
    assert checks["Kraken accepts a margin short on DOGE (validate only, nothing traded)"][0]
    assert not checks["Kraken accepts a margin short on kPEPE (validate only, nothing traded)"][0]
    cost = [v for n, v in checks.items() if n.startswith("Kraken costs at tier 1")]
    assert cost and not cost[0][0] and "kalshi" in cost[0][1]
