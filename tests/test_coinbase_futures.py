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
