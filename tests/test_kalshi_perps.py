"""Kalshi perpetuals: signing, IOC order payloads and fills, positions,
balance, the market-data adapter and venue wiring."""
import json
import pickle

import pytest

from cryptobot.data.geckoterminal import Candle
from cryptobot.data.kalshi_perps import KalshiMarketData
from cryptobot.execution.kalshi_perps import (
    CONTRACTS, US_COINS, KalshiExecConfig, KalshiPerpsExecutor, SizeTooSmall, presign_text)


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
        self.content = json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes          # (method, path-suffix) -> body or callable(json)
        self.calls = []

    async def request(self, method, url, params=None, json=None, headers=None):
        self.calls.append((method, url, params, json, headers))
        for (m, suffix), body in self.routes.items():
            if m == method and url.endswith(suffix):
                return Resp(body(json) if callable(body) else body)
        return Resp({"error": "no route"}, 404)

    async def get(self, url, params=None):
        return await self.request("GET", url, params=params)

    async def aclose(self):
        pass


def armed(monkeypatch, http, **kw):
    monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
    return KalshiPerpsExecutor(KalshiExecConfig(live=True, **kw), client=http, key_id="kid",
                               key_pem="-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----")


def test_presign_text_drops_query_and_keeps_prefix():
    assert presign_text(1700000000000, "get", "/trade-api/v2/margin/orders?limit=5") == \
        "1700000000000GET/trade-api/v2/margin/orders"


def test_contract_units_match_kalshi_market_listing():
    """GET /margin/markets 2026-10-08: KXDOGEPERP contract_size 100 x 1,
    KXKSHIBPERP 1000 x 1000 (1K kSHIB = 1M SHIB), KXKPEPEPERP 1000 x 1000."""
    assert CONTRACTS["DOGE"].units_per_contract == 100.0
    assert CONTRACTS["kSHIB"].units_per_contract == 1_000.0
    assert CONTRACTS["kPEPE"].units_per_contract == 1_000.0
    assert CONTRACTS["US500"].units_per_contract == 0.001 and CONTRACTS["GOLD"].units_per_contract == 0.001
    assert CONTRACTS["BTC"].units_per_contract == 0.0001 and CONTRACTS["ETH"].units_per_contract == 0.001
    assert CONTRACTS["BTC"].ticker == "KXBTCPERP" and "BTC" not in US_COINS
    assert US_COINS == ("DOGE", "kSHIB")                                     # index/metals are not in the universe


@pytest.mark.asyncio
async def test_open_short_sends_ioc_ask_at_contract_price(monkeypatch):
    def create(body):
        assert body["side"] == "ask" and body["time_in_force"] == "immediate_or_cancel"
        assert body["count"] == "35" and body["reduce_only"] is False
        assert body["ticker"] == "KXDOGEPERP" and body["price"] == "8.3580"   # 8.40 contract x (1 - 0.5%)
        return {"order_id": "o1", "fill_count": "35.00", "remaining_count": "0.00",
                "average_fill_price": "8.3900", "average_fee_paid": "0.003356"}
    http = FakeHttp({("POST", "/margin/orders"): create})
    monkeypatch.setattr("cryptobot.execution.kalshi_perps.sign", lambda pem, msg: "sig")
    ex = armed(monkeypatch, http, max_trade_usd=5000)
    fill = await ex.open_short("DOGE", 300.0, 0.084)          # $300 / $8.40 = 35 contracts
    assert fill.qty == pytest.approx(3500.0) and fill.price == pytest.approx(0.0839)
    assert fill.fee_usd == pytest.approx(35 * 0.003356) and fill.order_id == "o1"
    headers = http.calls[0][4]
    assert headers["KALSHI-ACCESS-KEY"] == "kid" and headers["KALSHI-ACCESS-SIGNATURE"] == "sig"


@pytest.mark.asyncio
async def test_unfilled_ioc_raises_and_close_is_reduce_only_bid(monkeypatch):
    http = FakeHttp({("POST", "/margin/orders"): lambda b: {"order_id": "o2", "fill_count": "0.00",
                                                              "remaining_count": "0.00"}})
    monkeypatch.setattr("cryptobot.execution.kalshi_perps.sign", lambda pem, msg: "sig")
    ex = armed(monkeypatch, http, max_trade_usd=5000)
    with pytest.raises(RuntimeError, match="did not fill"):
        await ex.close("DOGE", 3500.0, 0.084)
    body = http.calls[0][3]
    assert body["side"] == "bid" and body["reduce_only"] is True and body["count"] == "35"
    assert body["price"] == "8.4420"                                  # 8.40 x (1 + 0.5%)


@pytest.mark.asyncio
async def test_sub_contract_slot_raises_without_sending(monkeypatch):
    http = FakeHttp({})
    ex = armed(monkeypatch, http, max_trade_usd=5000)
    with pytest.raises(SizeTooSmall):
        await ex.open_short("DOGE", 5.0, 0.084)
    assert http.calls == []


@pytest.mark.asyncio
async def test_positions_and_balance(monkeypatch):
    http = FakeHttp({
        ("GET", "/margin/positions"): {"positions": [
            {"market_ticker": "KXDOGEPERP", "position": "-35.00", "entry_price": "8.39"},
            {"market_ticker": "KXKSHIBPERP", "position": "10.00"},
            {"market_ticker": "KXSOLPERP", "position": "-1.00"}]},   # not in the contract table: ignored
        ("GET", "/margin/balance"): {"settled_funds": "900.0000", "subaccount_balances": [
            {"subaccount": 0, "account_equity": "950.00", "available_balance": "600.00",
             "maintenance_margin": "120.00", "initial_margin": "300.00", "position_value": "-294.00"}]},
    })
    monkeypatch.setattr("cryptobot.execution.kalshi_perps.sign", lambda pem, msg: "sig")
    ex = armed(monkeypatch, http)
    assert await ex.positions() == {"DOGE": -3500.0, "kSHIB": 10_000.0}
    bal = await ex.balance()
    assert bal["total_usd_balance"] == 950.0 and bal["available_margin"] == 600.0


def test_dry_run_without_arming(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    ex = KalshiPerpsExecutor(KalshiExecConfig(live=True), client=FakeHttp({}), key_id="k", key_pem="p")
    assert not ex.armed and ex.has_key


def test_sign_round_trip_with_ed25519_key():
    """Skips where the cryptography build is unusable (missing cffi; the
    failure there is a Rust panic, not a Python exception)."""
    import base64
    pytest.importorskip("_cffi_backend")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        key = ed25519.Ed25519PrivateKey.generate()
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        from cryptobot.execution.kalshi_perps import sign
        sig = sign(pem, "1700000000000POST/trade-api/v2/margin/orders")
    except Exception as exc:
        pytest.skip(f"cryptography unusable here: {exc}")
    key.public_key().verify(base64.b64decode(sig), b"1700000000000POST/trade-api/v2/margin/orders")


class Meta:
    def __init__(self, symbol):
        self.symbol = symbol


MARKETS = {"markets": [
    {"ticker": "KXDOGEPERP", "status": "active", "bid": "8.4446", "ask": "8.4513", "price": "8.4406"},
    {"ticker": "KXKSHIBPERP", "status": "active", "bid": "5.3164", "ask": "5.3199", "price": "5.3183"},
    {"ticker": "KXKPEPEPERP", "status": "inactive", "bid": "0", "ask": "0", "price": "0"}]}


@pytest.mark.asyncio
async def test_market_data_divides_contract_prices_and_seeds_history(tmp_path):
    day = 86400
    t0 = 1_780_000_000 - (1_780_000_000 % day)
    seed = {"DOGE": (Meta("DOGE"), [Candle(ts=t0 + i * day, open=0.1, high=0.11, low=0.09, close=0.1, volume_usd=1e6)
                                    for i in range(5)])}
    p = tmp_path / "seed.pkl"
    p.write_bytes(pickle.dumps(seed))
    http = FakeHttp({
        ("GET", "/margin/markets"): MARKETS,
        ("GET", "/candlesticks"): {"candlesticks": [
            {"end_period_ts": t0 + 4 * day, "price": {"open": "8.0", "high": "8.5", "low": "7.9", "close": "8.4"},
             "volume_notional_value_dollars": "100000"},
            {"end_period_ts": t0 + 5 * day, "price": {"open": "8.4", "high": "8.6", "low": "8.3", "close": "8.5"},
             "volume_notional_value_dollars": "120000"}]},
        ("GET", "/margin/funding_rates/estimate"): {"funding_rate": 0.00024, "market_ticker": "KXDOGEPERP"},
    })
    md = KalshiMarketData(history_seed=p, client=http)
    cs = await md.candles("DOGE")
    assert [c.ts for c in cs] == [t0 + i * day for i in range(5)]       # 3 seed days + 2 Kalshi days
    assert cs[3].close == pytest.approx(0.084) and cs[3].volume_usd == 100000.0
    mids = await md.all_mids()
    assert mids["DOGE"] == pytest.approx((8.4446 + 8.4513) / 2 / 100) and "kPEPE" not in mids
    assert mids["kSHIB"] == pytest.approx((5.3164 + 5.3199) / 2 / 1000)
    assert await md.universe() == ["DOGE", "kSHIB"]
    rates = await md.funding_rates()
    assert rates["DOGE"] == pytest.approx(0.00024 / 8)
    assert await md.margin_rates() == {}


def test_build_kalshi_venue(tmp_path, monkeypatch):
    from cryptobot import perp_bot as PB
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    bot = PB.build({"perp": {"venue": "kalshi"}, "allocation": {"carry": 0.0, "bounce_short": 1.0}}, tmp_path)
    assert tuple(bot.cfg.coins) == US_COINS
    assert isinstance(bot.executor, KalshiPerpsExecutor) and isinstance(bot.client, KalshiMarketData)
    assert bot.cfg.taker_fee == 0.0004 and bot.cfg.min_fee_per_lot == 0.0
    assert bot.cfg.contract_units == {"DOGE": 100.0, "kSHIB": 1000.0}


def test_kalshi_preflight_lines():
    from cryptobot import desk as D
    cfg = {"perp": {"venue": "kalshi", "live": True, "max_trade_usd": 500},
           "allocation": {"carry": 0.0, "bounce_short": 1.0}, "risk": {"bankroll_usd": 200}}
    env = {"CRYPTOBOT_ARM_LIVE": "yes", "CRYPTOBOT_KALSHI_KEY_ID": "k", "CRYPTOBOT_KALSHI_KEY_PEM": "p"}
    plan = D.capital_plan(cfg)
    assert plan["kalshi_usd"] == 200 and plan["coinbase_usd"] == 0 and plan["bounce_slot"] == 100
    checks = D.preflight(cfg, env, {"kalshi_usd": 250.0},
                         {"DOGE": 8.44, "kSHIB": 5.32, "_inactive": ["kPEPE"], "_enabled": True})
    names = {n: ok for n, ok, _ in checks}
    assert names["Kalshi API key id + private key PEM"] is True
    assert names["each live slot ($50 at 50% deployed) buys at least one contract"] is True
    assert names["Kalshi perps enabled for this account"] is True
    assert names["kalshi_usd >= $200.00"] is True
    assert not any("Coinbase" in n or "Hyperliquid" in n for n in names)


@pytest.mark.asyncio
async def test_signed_path_tolerates_trailing_slash_in_base_url(monkeypatch):
    seen = {}
    def fake_sign(pem, msg):
        seen["msg"] = msg
        return "sig"
    monkeypatch.setattr("cryptobot.execution.kalshi_perps.sign", fake_sign)
    http = FakeHttp({("GET", "/margin/enabled"): {"enabled": True}})
    ex = armed(monkeypatch, http, base_url="https://external-api.demo.kalshi.co/trade-api/v2/")
    assert await ex.enabled() is True
    assert seen["msg"].endswith("GET/trade-api/v2/margin/enabled")
    assert http.calls[0][1] == "https://external-api.demo.kalshi.co/trade-api/v2/margin/enabled"


def test_size_too_small_is_shared_across_venues():
    from cryptobot.execution import coinbase_futures, kalshi_perps, perp_exchange
    assert coinbase_futures.SizeTooSmall is kalshi_perps.SizeTooSmall is perp_exchange.SizeTooSmall
