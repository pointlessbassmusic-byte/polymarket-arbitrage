"""Coinbase Derivatives venue: whole-contract sizing, fill parsing, arming
and the market-data adapter's seeded history."""
import os
import pickle
import time

import pytest

from cryptobot.data.coinbase_futures import CoinbaseMarketData
from cryptobot.data.hyperliquid import Candle
from cryptobot.execution.coinbase_futures import (
    CONTRACTS, US_COINS, CoinbaseExecConfig, CoinbaseFuturesExecutor, SizeTooSmall)


class FakeClient:
    def __init__(self, filled="2", price="0.20"):
        self.orders = []
        self.filled, self.price = filled, price

    def market_order_sell(self, client_order_id, product_id, base_size):
        self.orders.append(("sell", product_id, base_size))
        return {"success": True, "success_response": {"order_id": "o1"}}

    def close_position(self, client_order_id, product_id, size):
        self.orders.append(("close", product_id, size))
        return {"success": True, "success_response": {"order_id": "o2"}}

    def get_order(self, order_id):
        return {"order": {"filled_size": self.filled, "average_filled_price": self.price,
                          "status": "FILLED"}}

    def preview_market_order_sell(self, product_id, base_size):
        return {"order_total": "477.5", "commission_total": "0.48", "errs": [], "warning": [],
                "base_size": base_size, "order_margin_total": "120.1"}

    def get_product(self, product_id, get_tradability_status=False):
        return {"product_id": product_id, "status": "online", "trading_disabled": False}

    def get_futures_balance_summary(self):
        return {"balance_summary": {"total_usd_balance": {"value": "1500.5"},
                                    "cfm_usd_balance": {"value": "1000"},
                                    "available_margin": {"value": "900"},
                                    "unrealized_pnl": {"value": "0"},
                                    "initial_margin": {"value": "100"}}}


def armed_executor(monkeypatch, client, **kw):
    monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
    monkeypatch.setenv("CRYPTOBOT_COINBASE_KEY_NAME", "organizations/x/apiKeys/y")
    monkeypatch.setenv("CRYPTOBOT_COINBASE_KEY_SECRET", "-----BEGIN EC PRIVATE KEY-----\\nabc\\n-----END EC PRIVATE KEY-----")
    return CoinbaseFuturesExecutor(CoinbaseExecConfig(live=True, **kw), client=client)


def test_contract_rounding_floors_and_caps(monkeypatch):
    ex = armed_executor(monkeypatch, FakeClient(), max_trade_usd=1000)
    # DOGE at $0.20 → $1,000 per contract; $2,500 slot → 2 contracts under the $1,000 cap → 1
    assert ex.contracts_for("DOGE", 2500, 0.20) == 1
    ex2 = armed_executor(monkeypatch, FakeClient(), max_trade_usd=5000)
    assert ex2.contracts_for("DOGE", 2500, 0.20) == 2
    assert ex2.contracts_for("DOGE", 999, 0.20) == 0


@pytest.mark.asyncio
async def test_open_short_rejects_sub_contract_slot(monkeypatch):
    fake = FakeClient()
    ex = armed_executor(monkeypatch, fake, max_trade_usd=5000)
    with pytest.raises(SizeTooSmall):
        await ex.open_short("DOGE", 300, 0.20)
    assert fake.orders == []


@pytest.mark.asyncio
async def test_open_short_and_close_report_units_not_contracts(monkeypatch):
    fake = FakeClient(filled="2", price="0.21")
    ex = armed_executor(monkeypatch, fake, max_trade_usd=5000)
    fill = await ex.open_short("DOGE", 2500, 0.20)
    assert fake.orders[0] == ("sell", "DOP-20DEC30-CDE", "2")
    assert fill.qty == pytest.approx(2 * 5000.0) and fill.price == pytest.approx(0.21)
    assert fill.side == "short" and not fill.dry_run
    fill = await ex.close("DOGE", 10_000.0, 0.21)
    assert fake.orders[1] == ("close", "DOP-20DEC30-CDE", "2")
    assert fill.qty == pytest.approx(10_000.0)


@pytest.mark.asyncio
async def test_dry_run_when_not_armed(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    fake = FakeClient()
    ex = CoinbaseFuturesExecutor(CoinbaseExecConfig(live=True, max_trade_usd=5000), client=fake)
    assert not ex.armed
    fill = await ex.open_short("DOGE", 2500, 0.20)
    assert fill.dry_run and fake.orders == []


@pytest.mark.asyncio
async def test_balance_fields(monkeypatch):
    ex = armed_executor(monkeypatch, FakeClient())
    bal = await ex.balance()
    assert bal["total_usd_balance"] == pytest.approx(1500.5)


def test_us_universe_matches_contracts():
    assert set(US_COINS) == set(CONTRACTS) == {"DOGE", "kPEPE", "kSHIB"}


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeHttp:
    """Stands in for the Coinbase market endpoints."""
    def __init__(self, candles):
        self.candles = candles

    async def get(self, path, params=None):
        if path.endswith("/candles"):
            return Resp({"candles": [{"start": str(c[0]), "open": c[1], "high": c[2], "low": c[3],
                                      "close": c[4], "volume": c[5]} for c in self.candles]})
        return Resp({"products": [{"product_id": "DOP-20DEC30-CDE", "price": "0.2",
                                   "future_product_details": {"funding_rate": "0.0001"}}]})


class Meta:
    def __init__(self, symbol):
        self.symbol = symbol


@pytest.mark.asyncio
async def test_seed_history_prepends_before_first_coinbase_candle(tmp_path):
    day = 86400
    t0 = 1_700_000_000 - (1_700_000_000 % day)
    seed = {"DOGE": (Meta("DOGE"), [Candle(ts=t0 + i * day, open=0.1, high=0.11, low=0.09, close=0.1, volume_usd=1e6)
                                    for i in range(5)])}
    p = tmp_path / "seed.pkl"
    p.write_bytes(pickle.dumps(seed))
    cb = [(t0 + 3 * day, "0.2", "0.21", "0.19", "0.2", "100"), (t0 + 4 * day, "0.2", "0.22", "0.19", "0.21", "50")]
    md = CoinbaseMarketData(history_seed=p, client=FakeHttp(cb))
    out = await md.candles("DOGE")
    assert [c.ts for c in out] == [t0 + i * day for i in range(5)]
    assert out[2].close == pytest.approx(0.1) and out[3].close == pytest.approx(0.2)
    # volume: contracts × units × price
    assert out[3].volume_usd == pytest.approx(100 * 5000.0 * 0.2)
    rates = await md.funding_rates()
    assert rates["DOGE"] == pytest.approx(0.0001)
    assert (await md.all_mids())["DOGE"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_preview_prices_one_contract_without_arming(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    fake = FakeClient()
    ex = CoinbaseFuturesExecutor(CoinbaseExecConfig(), client=fake)
    p = await ex.preview("DOGE")
    assert p["order_total"] == pytest.approx(477.5) and p["commission"] == pytest.approx(0.48)
    assert p["tradable"] and p["errs"] == [] and fake.orders == []


def test_preview_checks_render_fee_or_rejection():
    from cryptobot.desk import preview_checks
    ok, bad = preview_checks([
        {"coin": "DOGE", "tradable": True, "errs": [], "order_total": 477.5, "commission": 0.48, "margin": 120.1},
        {"coin": "kPEPE", "tradable": False, "errs": ["PREVIEW_INSUFFICIENT_FUND"], "status": "online"}])
    assert ok[1] is True and "fee $0.48" in ok[2]
    assert bad[1] is False and "INSUFFICIENT_FUND" in bad[2]


@pytest.mark.asyncio
async def test_positions_are_signed_units(monkeypatch):
    fake = FakeClient()
    fake.list_futures_positions = lambda: {"positions": [
        {"product_id": "DOP-20DEC30-CDE", "side": "SHORT", "number_of_contracts": "2"},
        {"product_id": "SHP-20DEC30-CDE", "side": "LONG", "number_of_contracts": "3"},
        {"product_id": "BIP-20DEC30-CDE", "side": "SHORT", "number_of_contracts": "1"}]}
    ex = armed_executor(monkeypatch, fake)
    assert await ex.positions() == {"DOGE": -10_000.0, "kSHIB": 30_000.0}


@pytest.mark.asyncio
async def test_positions_accept_coinbase_side_enum(monkeypatch):
    fake = FakeClient()
    fake.list_futures_positions = lambda: {"positions": [
        {"product_id": "DOP-20DEC30-CDE", "side": "FUTURES_POSITION_SIDE_SHORT", "number_of_contracts": "2"}]}
    ex = armed_executor(monkeypatch, fake)
    assert await ex.positions() == {"DOGE": -10_000.0}


def test_contract_rounding_survives_float_noise(monkeypatch):
    ex = armed_executor(monkeypatch, FakeClient(), max_trade_usd=1e9)
    mid, units = 0.07, 5000.0
    slot = 3 * units * mid                       # exactly three contracts, as _consider sizes it
    assert ex.contracts_for("DOGE", slot, mid) == 3


@pytest.mark.asyncio
async def test_fill_polls_pending_order_then_uses_fill(monkeypatch):
    fake = FakeClient()
    seq = iter([{"order": {"status": "PENDING", "filled_size": "0"}},
                {"order": {"status": "FILLED", "filled_size": "2", "average_filled_price": "0.21"}}])
    fake.get_order = lambda order_id: next(seq)
    ex = armed_executor(monkeypatch, fake, max_trade_usd=5000, fill_poll_s=0.0)
    fill = await ex.open_short("DOGE", 2500, 0.20)
    assert fill.qty == pytest.approx(10_000.0) and fill.price == pytest.approx(0.21)


@pytest.mark.asyncio
async def test_fill_raises_on_terminal_unfilled_order(monkeypatch):
    fake = FakeClient()
    fake.get_order = lambda order_id: {"order": {"status": "CANCELLED", "filled_size": "0"}}
    ex = armed_executor(monkeypatch, fake, max_trade_usd=5000, fill_poll_s=0.0)
    with pytest.raises(RuntimeError, match="CANCELLED"):
        await ex.open_short("DOGE", 2500, 0.20)


@pytest.mark.asyncio
async def test_products_fetched_once_per_tick():
    calls = []
    class Http(FakeHttp):
        async def get(self, path, params=None):
            calls.append(path)
            return await super().get(path, params)
    md = CoinbaseMarketData(client=Http([]))
    await md.all_mids(); await md.funding_rates()
    assert len(calls) == 1


def test_effective_fee_floor_hits_small_contracts():
    from cryptobot.execution.coinbase_futures import effective_fee, TAKER_FEE
    assert effective_fee("DOGE", 0.085) == pytest.approx(TAKER_FEE)          # $425 contract: rate applies
    assert effective_fee("kSHIB", 0.0053) == pytest.approx(0.20 / 53.0)      # $53 contract: $0.20 floor


@pytest.mark.asyncio
async def test_margin_rates_read_overnight_short():
    class Http(FakeHttp):
        async def get(self, path, params=None):
            return Resp({"products": [{"product_id": "PEP-20DEC30-CDE", "price": "0.0038",
                                       "future_product_details": {"overnight_margin_rate": {"long_margin_rate": "0.54", "short_margin_rate": "1.143375"}}}]})
    md = CoinbaseMarketData(client=Http([]))
    assert await md.margin_rates() == {"kPEPE": pytest.approx(1.143375)}


def test_contract_units_match_coinbase_contract_size_field():
    """Coinbase's product endpoint reports contract_size in the quoted unit
    (DOGE, 1000PEPE, 1000SHIB), which is the bot's own price unit, so the
    two numbers must be identical. Recorded 2026-10-08: DOP 5000, PEP
    100000, SHP 10000. A 1000x slip here once sized a $1,000 slot as 2,600
    PEPE contracts."""
    api_contract_size = {"DOP-20DEC30-CDE": 5_000, "PEP-20DEC30-CDE": 100_000, "SHP-20DEC30-CDE": 10_000}
    for c in CONTRACTS.values():
        assert c.units_per_contract == api_contract_size[c.product_id]
