"""Broker plumbing: Alpaca, tastytrade, the broker inventory, promo arithmetic."""

import asyncio
import datetime as dt
import json

import pytest

from cryptobot import brokers as B
from cryptobot import promos as P
from cryptobot.data.alpaca import AlpacaData
from cryptobot.execution.alpaca import AlpacaConfig, AlpacaExecutor, LIVE_URL, PAPER_URL, _limit
from cryptobot.execution.perp_exchange import SizeTooSmall
from cryptobot.execution.tastytrade import TastytradeClient, TastytradeConfig


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
        self.content = json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def request(self, method, url, params=None, json=None, headers=None, data=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json,
                           "headers": headers, "data": data})
        for (m, suffix), body in self.routes.items():
            if m == method and url.split("?")[0].endswith(suffix):
                out = body(json if json is not None else (data or params)) if callable(body) else body
                return out if isinstance(out, Resp) else Resp(out)
        return Resp({"message": "no route"}, 404)

    async def aclose(self):
        pass


async def _nosleep(*_a, **_k):
    return None


# -- Alpaca ----------------------------------------------------------------------

def test_alpaca_modes(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    assert AlpacaExecutor(AlpacaConfig(), FakeHttp({}), key_id="", secret="").mode == "dry-run"
    paper = AlpacaExecutor(AlpacaConfig(live=False), FakeHttp({}), key_id="k", secret="s")
    assert paper.mode == "paper" and paper.base == PAPER_URL and paper.sends_orders
    held = AlpacaExecutor(AlpacaConfig(live=True), FakeHttp({}), key_id="k", secret="s")
    assert held.mode == "dry-run" and not held.armed and not held.sends_orders   # live without the arm flag
    monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
    live = AlpacaExecutor(AlpacaConfig(live=True), FakeHttp({}), key_id="k", secret="s")
    assert live.mode == "live" and live.base == LIVE_URL and live.armed


def test_alpaca_limit_rounds_away_from_mid_to_the_cent():
    assert _limit(100.0, 0.002, "buy") == 100.20 and _limit(100.0, 0.002, "sell") == 99.80
    assert _limit(10.004, 0.0, "buy") == 10.01 and _limit(10.006, 0.0, "sell") == 10.0


def test_alpaca_ioc_long_in_whole_shares_and_fill_poll(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _nosleep)
    polls = iter([{"status": "new", "filled_qty": "0"},
                  {"status": "filled", "filled_qty": "4", "filled_avg_price": "120.05"}])
    http = FakeHttp({("POST", "/v2/orders"): {"id": "a1", "status": "accepted"},
                     ("GET", "/v2/orders/a1"): lambda _b: next(polls)})
    ex = AlpacaExecutor(AlpacaConfig(max_trade_usd=500), http, key_id="k", secret="s")
    fill = asyncio.run(ex.open_long("QQQ", 500.0, 120.0))
    body = http.calls[0]["json"]
    assert body["qty"] == "4" and body["time_in_force"] == "ioc" and body["type"] == "limit"
    assert body["side"] == "buy" and body["limit_price"] == "120.24"
    assert http.calls[0]["headers"]["APCA-API-KEY-ID"] == "k"
    assert fill.qty == 4 and fill.price == pytest.approx(120.05) and fill.order_id == "a1"


def test_alpaca_short_unfilled_and_too_small(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _nosleep)
    http = FakeHttp({("POST", "/v2/orders"): {"id": "a2", "status": "canceled", "filled_qty": "0"}})
    ex = AlpacaExecutor(AlpacaConfig(), http, key_id="k", secret="s")
    with pytest.raises(RuntimeError, match="did not fill"):
        asyncio.run(ex.open_short("SPY", 1000.0, 450.0))
    assert http.calls[0]["json"]["side"] == "sell" and http.calls[0]["json"]["qty"] == "1"
    with pytest.raises(SizeTooSmall):
        asyncio.run(ex.open_short("SPY", 100.0, 450.0))


def test_alpaca_close_flattens_through_positions_endpoint(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _nosleep)
    http = FakeHttp({("DELETE", "/v2/positions/QQQ"): {"id": "c1", "status": "accepted"},
                     ("GET", "/v2/orders/c1"): {"status": "filled", "filled_qty": "4", "filled_avg_price": "121"}})
    ex = AlpacaExecutor(AlpacaConfig(), http, key_id="k", secret="s")
    fill = asyncio.run(ex.close("QQQ", 4, 121.0))
    assert http.calls[0]["method"] == "DELETE" and fill.side == "close" and fill.qty == 4


def test_alpaca_dry_run_sends_nothing(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    http = FakeHttp({})
    ex = AlpacaExecutor(AlpacaConfig(), http, key_id="", secret="")
    assert asyncio.run(ex.open_long("QQQ", 500.0, 120.0)).dry_run
    assert asyncio.run(ex.close("QQQ", 4, 120.0)).dry_run
    assert http.calls == []


def test_alpaca_account_positions_and_mid():
    http = FakeHttp({
        ("GET", "/v2/account"): {"equity": "1010.5", "buying_power": "2021", "cash": "500", "status": "ACTIVE",
                                 "shorting_enabled": True, "pattern_day_trader": False, "daytrade_count": 2,
                                 "multiplier": "2"},
        ("GET", "/v2/positions"): [{"symbol": "QQQ", "qty": "4", "side": "long"},
                                   {"symbol": "SPY", "qty": "2", "side": "short"}],
        ("GET", "/v2/stocks/quotes/latest"): {"quotes": {"QQQ": {"bp": 120.0, "ap": 120.1}}}})
    ex = AlpacaExecutor(AlpacaConfig(), http, key_id="k", secret="s")
    b = asyncio.run(ex.balance())
    assert b["total_usd_balance"] == 1010.5 and b["available_margin"] == 2021 and b["daytrade_count"] == 2
    assert asyncio.run(ex.positions()) == {"QQQ": 4.0, "SPY": -2.0}
    assert asyncio.run(ex.mid("QQQ")) == pytest.approx(120.05)
    assert http.calls[-1]["params"]["feed"] == "iex"


def test_alpaca_bars_follow_page_tokens():
    pages = iter([
        {"bars": {"QQQ": [{"t": "2026-10-08T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]},
         "next_page_token": "p2"},
        {"bars": {"QQQ": [{"t": "2026-10-08T13:35:00Z", "o": 1.5, "h": 2, "l": 1, "c": 2, "v": 10}]},
         "next_page_token": None}])
    http = FakeHttp({("GET", "/v2/stocks/bars"): lambda _p: next(pages)})
    d = AlpacaData("k", "s", client=http)
    bars = asyncio.run(d.bars("QQQ", "5Min", start=dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)))
    assert [b.close for b in bars] == [1.5, 2.0] and bars[0].volume_usd == 150.0
    assert http.calls[0]["params"]["start"] == "2026-10-08T00:00:00Z"
    assert http.calls[1]["params"]["page_token"] == "p2"


# -- tastytrade ----------------------------------------------------------------------

def _tasty(http, now):
    return TastytradeClient(TastytradeConfig(), http, client_secret="cs", refresh_token="rt", now=now)


def test_tastytrade_token_is_cached_until_near_expiry():
    clock = [1000.0]
    http = FakeHttp({("POST", "/oauth/token"): {"access_token": "AT", "expires_in": 900},
                     ("GET", "/customers/me/accounts"): {"data": {"items": [{"account": {"account-number": "5WX1"}}]}}})
    cl = _tasty(http, lambda: clock[0])
    assert asyncio.run(cl.accounts()) == ["5WX1"]
    assert asyncio.run(cl.accounts()) == ["5WX1"]
    assert cl.token_refreshes == 1
    assert http.calls[0]["data"]["grant_type"] == "refresh_token"
    assert http.calls[1]["headers"]["Authorization"] == "Bearer AT"
    clock[0] += 900 - 30                                  # inside the 60 s safety margin
    asyncio.run(cl.accounts())
    assert cl.token_refreshes == 2


def test_tastytrade_balances_positions_and_micro_bitcoin():
    http = FakeHttp({
        ("POST", "/oauth/token"): {"access_token": "AT", "expires_in": 900},
        ("GET", "/accounts/5WX1/balances"): {"data": {"net-liquidating-value": "1000.25",
                                                      "derivative-buying-power": "800", "cash-balance": "1000"}},
        ("GET", "/accounts/5WX1/positions"): {"data": {"items": [
            {"symbol": "/MBTZ6", "instrument-type": "Future", "quantity": "1", "quantity-direction": "Short",
             "average-open-price": "82000"}]}},
        ("GET", "/instruments/futures"): {"data": {"items": [{"symbol": "/MBTZ6", "active": True},
                                                              {"symbol": "/MBTU6", "active": False}]}}})
    cl = _tasty(http, lambda: 0.0)
    b = asyncio.run(cl.balances("5WX1"))
    assert b["total_usd_balance"] == 1000.25 and b["available_margin"] == 800
    assert asyncio.run(cl.positions("5WX1"))[0]["qty"] == -1.0
    assert asyncio.run(cl.micro_bitcoin()) == ["/MBTZ6"]


def test_tastytrade_orders_dry_run_endpoint_and_unarmed_live(monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    http = FakeHttp({("POST", "/oauth/token"): {"access_token": "AT", "expires_in": 900},
                     ("POST", "/accounts/5WX1/orders/dry-run"): {"data": {"buying-power-effect": {}}}})
    cl = _tasty(http, lambda: 0.0)
    legs = [{"instrument-type": "Future", "symbol": "/MBTZ6", "action": "Sell to Open", "quantity": 1}]
    asyncio.run(cl.order("5WX1", legs, price=82000.0, price_effect="Credit"))
    assert http.calls[-1]["url"].endswith("/orders/dry-run") and http.calls[-1]["json"]["price"] == "82000.00"
    n = len(http.calls)
    r = asyncio.run(cl.order("5WX1", legs, dry_run=False))
    assert r["dry_run"] and len(http.calls) == n          # not armed: nothing sent


# -- broker inventory ------------------------------------------------------------------

def test_key_status_lists_missing_variables():
    rows = {r["broker"]: r for r in B.key_status({"CRYPTOBOT_ALPACA_KEY_ID": "k", "CRYPTOBOT_ALPACA_SECRET_KEY": "s",
                                                  "CRYPTOBOT_KALSHI_KEY_ID": "id"})}
    assert rows["alpaca"]["has_keys"] and not rows["kalshi"]["has_keys"]
    assert rows["kalshi"]["missing"] == ["CRYPTOBOT_KALSHI_KEY_PEM"]
    assert "fidelity" not in rows
    text = B.render_status(list(rows.values()))
    assert "missing: CRYPTOBOT_KALSHI_KEY_PEM" in text


class _FakeAlpaca:
    async def balance(self):
        return {"mode": "paper", "total_usd_balance": 100000.0, "available_margin": 200000.0, "status": "ACTIVE",
                "shorting_enabled": True, "pattern_day_trader": False, "daytrade_count": 0}

    async def clock(self):
        return {"is_open": False}

    async def close_client(self):
        pass


class _Boom:
    async def accounts(self):
        raise PermissionError("token revoked")

    async def close_client(self):
        pass


def test_probe_reads_accounts_with_keys_and_never_raises():
    env = {"CRYPTOBOT_ALPACA_KEY_ID": "k", "CRYPTOBOT_ALPACA_SECRET_KEY": "s",
           "CRYPTOBOT_TASTY_CLIENT_SECRET": "cs", "CRYPTOBOT_TASTY_REFRESH_TOKEN": "rt"}
    lines = asyncio.run(B.probe(env, factories={"alpaca": _FakeAlpaca, "tastytrade": _Boom}))
    assert any(l.startswith("alpaca") and "paper" in l and "$100,000.00" in l for l in lines)
    assert any(l.startswith("tastytrade") and "ERROR PermissionError" in l for l in lines)
    assert not any("rt" == tok or "cs" == tok for l in lines for tok in l.split())
    assert asyncio.run(B.probe({})) == ["no broker keys in the environment"]


# -- promotions ------------------------------------------------------------------------

def test_hedged_capture_arithmetic():
    r = P.hedged_capture(250, 1000, 30, funding_8h=0.0001, perp_fee=0.0004, spot_fee=0.0040, spread=0.0005)
    assert r["spot_cost"] == pytest.approx(1000 * 2 * 0.0045)
    assert r["hedge_cost"] == pytest.approx(1000 * (2 * 0.0009 + 0.0001 * 90))
    assert r["net"] == pytest.approx(250 - 9.0 - 10.8)
    assert r["annualised_on_capital"] == pytest.approx(r["net"] / (1000 * 30) * 365)
    cash = P.hedged_capture(10, 1000, 365, needs_price_exposure=False, tax_rate=0.3)
    assert cash["spot_cost"] == 0 and cash["hedge_cost"] == 0 and cash["net"] == pytest.approx(7.0)


def test_rank_uses_the_longer_of_hold_and_clawback():
    quick = P.Promo("quick", 50, 100, hold_days=30)
    locked = P.Promo("locked", 200, 10000, hold_days=0, clawback_days=730, kind="transfer",
                     needs_price_exposure=False)
    ranked = P.rank([locked, quick])
    assert [p.name for p, _ in ranked] == ["quick", "locked"]
    assert ranked[1][1]["annualised_on_capital"] == pytest.approx(200 / (10000 * 730) * 365)
