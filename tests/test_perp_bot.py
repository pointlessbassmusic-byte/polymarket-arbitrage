"""Tests for the daily bounce-short perp bot and its execution leg."""

import asyncio
import os
from pathlib import Path

import pytest

from cryptobot.backtest import Candle
from cryptobot.costs import CostModel
from cryptobot.data.hyperliquid import MEMECOINS
from cryptobot.execution.perp_exchange import PerpExecConfig, PerpExecutor
from cryptobot.models import Side, Signal, SignalType
from cryptobot.perp_bot import (CHAIN, PerpBot, PerpBotConfig, fit_cuts,
                                perp_cost_model, rule_fires)
from cryptobot.portfolio import Portfolio
from cryptobot.protections import ProtectionConfig
from cryptobot.risk import RiskConfig
from cryptobot import perp_bot as PB

DAY = 86400


def _sig(price=100.0, side=Side.SHORT, stop=0.10, target=0.20, t=1_800_000_000.0):
    return Signal(ts=t, type=SignalType.BOUNCE_SHORT, key=f"{CHAIN}:X", chain=CHAIN,
                  symbol="X", side=side, price_usd=price, confidence=0.4,
                  expected_move=target, stop_loss_pct=stop, take_profit_pct=target,
                  risk_reward=target / stop, liquidity_usd=5e6, reason="t")


class TestShortPortfolio:
    def test_short_stop_is_above_and_target_below(self):
        pf = Portfolio()
        pos = pf.open_from_signal(_sig(), 50.0)
        assert pos.stop_loss == pytest.approx(110.0)
        assert pos.take_profit == pytest.approx(80.0)

    def test_short_exits_on_the_right_sides(self):
        pf = Portfolio()
        pf.open_from_signal(_sig(), 50.0)
        assert pf.check_exit(f"{CHAIN}:X", 105.0) is None
        assert pf.check_exit(f"{CHAIN}:X", 90.0) is None
        assert pf.check_exit(f"{CHAIN}:X", 111.0) == "stop_loss"
        pf2 = Portfolio()
        pf2.open_from_signal(_sig(), 50.0)
        assert pf2.check_exit(f"{CHAIN}:X", 79.0) == "take_profit"

    def test_short_pnl_and_costs_on_close(self):
        cm = perp_cost_model()
        pf = Portfolio(cost_model=cm)
        pf.open_from_signal(_sig(), 100.0)          # qty 1 @ 100
        trade = pf.close(f"{CHAIN}:X", 80.0, "take_profit")
        costs = cm.round_trip_usd(100.0, 5e6, CHAIN)
        assert 0.17 < costs < 0.18                  # fees + slippage + a sliver of impact
        assert trade.pnl_usd == pytest.approx(20.0 - costs, abs=1e-9)

    def test_short_breakeven_ratchet_moves_stop_down(self):
        pf = Portfolio(cost_model=perp_cost_model())
        pf.open_from_signal(_sig(), 100.0)
        key = f"{CHAIN}:X"
        assert pf.check_exit(key, 95.0) is None      # 5% in profit > 2x costs + 1%
        pos = pf.positions[key]
        assert pos.breakeven_set and 99.0 < pos.stop_loss < 100.0
        assert pf.check_exit(key, 99.9) == "breakeven_stop"

    def test_ratchet_can_be_disabled(self):
        pf = Portfolio(cost_model=perp_cost_model(), breakeven_ratchet=False)
        pf.open_from_signal(_sig(), 100.0)
        key = f"{CHAIN}:X"
        assert pf.check_exit(key, 95.0) is None
        assert not pf.positions[key].breakeven_set
        assert pf.positions[key].stop_loss == pytest.approx(110.0)
        assert pf.check_exit(key, 100.5) is None       # still open: no ratchet

    def test_coin_is_ineligible_for_hold_days_after_entry(self, monkeypatch):
        client = FakeClient({"A": _series(bounce=True), "B": _series(), "C": _series(),
                             "D": _series(), "E": _series(), "F": _series()},
                            {"A": 100.0})
        t0 = client.t0 + 400 * DAY + 3600
        monkeypatch.setattr(PB, "now", lambda: t0)
        bot = _bot(client)
        asyncio.run(bot.run_daily())
        entry = bot.books["sim"].portfolio.positions[f"{CHAIN}:A"].entry_price
        # stop out on day 2, then the pattern fires again: refused until day 14
        client.mids["A"] = entry * 1.11
        monkeypatch.setattr(PB, "now", lambda: t0 + 2 * DAY)
        asyncio.run(bot.monitor())
        assert f"{CHAIN}:A" not in bot.books["sim"].portfolio.positions
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert f"{CHAIN}:A" not in bot.books["sim"].portfolio.positions
        assert bot.journal.recent(3)[0]["stage"] == "cooldown"
        monkeypatch.setattr(PB, "now", lambda: t0 + 14 * DAY + 1)
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert f"{CHAIN}:A" in bot.books["sim"].portfolio.positions

    def test_perp_books_run_without_the_ratchet(self, monkeypatch):
        client = FakeClient({"A": _series(bounce=True), "B": _series(), "C": _series(),
                             "D": _series(), "E": _series(), "F": _series()}, {})
        monkeypatch.setattr(PB, "now", lambda: client.t0 + 400 * DAY + 3600)
        bot = _bot(client)
        assert not bot.books["sim"].portfolio.breakeven_ratchet
        assert not bot.books["real"].portfolio.breakeven_ratchet

    def test_short_never_trails(self):
        pf = Portfolio()
        pf.open_from_signal(_sig(), 50.0)
        assert pf.positions[f"{CHAIN}:X"].trail_pct is None

    def test_long_behaviour_unchanged(self):
        pf = Portfolio()
        pos = pf.open_from_signal(_sig(side=Side.LONG), 50.0)
        assert pos.stop_loss == pytest.approx(90.0) and pos.take_profit == pytest.approx(120.0)
        assert pf.check_exit(f"{CHAIN}:X", 89.0) == "stop_loss"

    def test_short_survives_a_save_and_load(self, tmp_path):
        f = tmp_path / "p.json"
        pf = Portfolio(state_file=f)
        pf.open_from_signal(_sig(), 50.0)
        pf2 = Portfolio(state_file=f)
        assert pf2.positions[f"{CHAIN}:X"].side == Side.SHORT


class TestRule:
    def test_fit_and_fire(self):
        hist = [{"move_1d": i / 100, "move_3d": -i / 100} for i in range(100)]
        cuts = fit_cuts(hist, (("move_1d", 2), ("move_3d", 0)))
        assert rule_fires({"move_1d": 0.9, "move_3d": -0.9}, cuts, (("move_1d", 2), ("move_3d", 0)))
        assert not rule_fires({"move_1d": 0.1, "move_3d": -0.9}, cuts, (("move_1d", 2), ("move_3d", 0)))


class FakeClient:
    """Serves synthetic daily candles, mids and funding; records nothing else."""

    def __init__(self, series: dict[str, list[float]], mids: dict[str, float],
                 t0: float = 1_800_000_000.0 - 400 * DAY, funding=None):
        self.series, self.mids, self.t0 = series, mids, t0
        self.funding = funding or {}

    async def funding_rates(self):
        return dict(self.funding)

    async def candles(self, coin, interval="1d", **kw):
        closes = self.series[coin]
        return [Candle(ts=self.t0 + i * DAY, open=c, high=c, low=c, close=c,
                       volume_usd=1000.0) for i, c in enumerate(closes)]

    async def all_mids(self):
        return dict(self.mids)

    async def close(self):
        pass


class FakeExecutor:
    def __init__(self, armed=True, fail=False):
        self.armed, self.fail, self.calls = armed, fail, []

    async def open_short(self, coin, notional, mid):
        self.calls.append(("short", coin, notional))
        if self.fail:
            raise RuntimeError("rejected")
        from cryptobot.execution.perp_exchange import Fill
        return Fill(coin, "short", notional / (mid * 1.002), mid * 1.002)   # worse fill

    async def close(self, coin, qty, mid):
        self.calls.append(("close", coin, qty))
        from cryptobot.execution.perp_exchange import Fill
        return Fill(coin, "close", qty, mid)


def _bot(client, executor=None, tmp=None, **cfg):
    sim = RiskConfig(bankroll_usd=200, max_position_usd=50, max_total_exposure_usd=400,
                     max_daily_loss_usd=20, min_position_usd=10, max_open_positions=8)
    real = RiskConfig(bankroll_usd=1000, max_position_usd=100, max_total_exposure_usd=500,
                      max_daily_loss_usd=100, min_position_usd=10)
    return PerpBot(PerpBotConfig(coins=tuple(client.series), state_dir=tmp,
                                 min_history_days=50, **cfg),
                   sim, real, ProtectionConfig(), PerpExecConfig(),
                   client=client, executor=executor or FakeExecutor(armed=False))


def _series(n=400, bounce=False):
    """Flat-ish path; optionally a 3-day slide then a sharp up-day at the end."""
    import random
    rng = random.Random(0)
    px, out = 100.0, []
    for _ in range(n):
        px *= 1 + rng.gauss(0, 0.02)
        out.append(px)
    if bounce:
        out[-4] = out[-5] * 0.90
        out[-3] = out[-4] * 0.92
        out[-2] = out[-3] * 0.95
        out[-1] = out[-2] * 1.12
    return out


class TestEvaluate:
    def test_fires_only_on_the_bounce_pattern(self, monkeypatch):
        client = FakeClient({"A": _series(bounce=True), "B": _series(),
                             "C": _series(), "D": _series(), "E": _series(),
                             "F": _series()}, {})
        monkeypatch.setattr(PB, "now", lambda: client.t0 + 400 * DAY + 3600)
        bot = _bot(client)
        sigs = asyncio.run(bot.evaluate())
        assert [s.symbol for s in sigs] == ["A"]
        s = sigs[0]
        assert s.side == Side.SHORT and s.type == SignalType.BOUNCE_SHORT
        assert s.stop_loss_pct == 0.10 and s.take_profit_pct == 0.20

    def test_todays_forming_candle_is_excluded(self, monkeypatch):
        closes = _series(bounce=True) + [1.0]        # absurd forming candle
        client = FakeClient({"A": closes, "B": _series(), "C": _series(),
                             "D": _series(), "E": _series(), "F": _series()}, {})
        # "now" is inside the last candle's day, so it is still forming
        monkeypatch.setattr(PB, "now", lambda: client.t0 + 400 * DAY + 3600)
        bot = _bot(client)
        sigs = asyncio.run(bot.evaluate())
        assert [s.symbol for s in sigs] == ["A"]
        assert sigs[0].price_usd != 1.0

    def test_too_little_history_does_not_fit(self):
        client = FakeClient({"A": _series(60, bounce=True)}, {})
        bot = _bot(client)
        assert asyncio.run(bot.evaluate()) == []
        assert bot.cuts == {}


class TestBooks:
    def _fired_bot(self, monkeypatch, tmp=None, executor=None):
        client = FakeClient({"A": _series(bounce=True), "B": _series(), "C": _series(),
                             "D": _series(), "E": _series(), "F": _series()},
                            {"A": 100.0})
        monkeypatch.setattr(PB, "now", lambda: client.t0 + 400 * DAY + 3600)
        bot = _bot(client, executor=executor, tmp=tmp)
        return bot, client

    def test_sim_opens_a_short_and_journals_it(self, monkeypatch):
        bot, _ = self._fired_bot(monkeypatch)
        asyncio.run(bot.run_daily())
        pos = bot.books["sim"].portfolio.positions[f"{CHAIN}:A"]
        assert pos.side == Side.SHORT
        assert bot.journal.recent(5)[0]["action"] == "opened"
        assert not bot.books["real"].portfolio.positions

    def test_real_book_stays_dormant_until_mode_is_real(self, monkeypatch):
        ex = FakeExecutor(armed=True)
        bot, _ = self._fired_bot(monkeypatch, executor=ex)
        asyncio.run(bot.run_daily())
        assert not ex.calls
        ok, _ = bot.set_mode("real")
        assert ok
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert ex.calls and ex.calls[0][0] == "short"
        real_pos = bot.books["real"].portfolio.positions[f"{CHAIN}:A"]
        sim_pos = bot.books["sim"].portfolio.positions[f"{CHAIN}:A"]
        assert real_pos.entry_price > sim_pos.entry_price     # real records the fill

    def test_set_mode_refuses_real_when_not_armed(self, monkeypatch):
        bot, _ = self._fired_bot(monkeypatch)
        ok, why = bot.set_mode("real")
        assert not ok and "ARM_LIVE" in why

    def test_failed_real_order_opens_nothing(self, monkeypatch):
        ex = FakeExecutor(armed=True, fail=True)
        bot, _ = self._fired_bot(monkeypatch, executor=ex)
        bot.set_mode("real")
        asyncio.run(bot.run_daily())
        assert not bot.books["real"].portfolio.positions
        assert any(d["stage"] == "execution" for d in bot.journal.recent(10, book="real"))

    def test_monitor_closes_on_target_stop_and_time(self, monkeypatch):
        bot, client = self._fired_bot(monkeypatch)
        asyncio.run(bot.run_daily())
        entry = bot.books["sim"].portfolio.positions[f"{CHAIN}:A"].entry_price
        client.mids["A"] = entry * 0.95
        asyncio.run(bot.monitor())
        assert f"{CHAIN}:A" in bot.books["sim"].portfolio.positions
        client.mids["A"] = entry * 0.79
        asyncio.run(bot.monitor())
        closed = bot.books["sim"].portfolio.closed[-1]
        assert closed.exit_reason == "take_profit" and closed.pnl_usd > 0
        # time exit
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert f"{CHAIN}:A" not in bot.books["sim"].portfolio.positions   # cooldown
        bot.books["sim"].protections = __import__("cryptobot.protections", fromlist=["x"]).ProtectionManager(
            ProtectionConfig(cooldown_s=0), 200)
        bot.eligible_at.clear()
        asyncio.run(bot.run_daily())
        assert f"{CHAIN}:A" in bot.books["sim"].portfolio.positions
        client.mids["A"] = entry
        monkeypatch.setattr(PB, "now", lambda: client.t0 + 415 * DAY)
        asyncio.run(bot.monitor())
        assert bot.books["sim"].portfolio.closed[-1].exit_reason == "time_exit"

    def test_real_close_failure_keeps_the_position(self, monkeypatch):
        class Ex(FakeExecutor):
            async def close(self, coin, qty, mid):
                raise RuntimeError("down")
        ex = Ex(armed=True)
        bot, client = self._fired_bot(monkeypatch, executor=ex)
        bot.set_mode("real")
        asyncio.run(bot.run_daily())
        client.mids["A"] = 10.0
        asyncio.run(bot.monitor())
        assert f"{CHAIN}:A" in bot.books["real"].portfolio.positions
        assert f"{CHAIN}:A" not in bot.books["sim"].portfolio.positions

    def test_positions_survive_restart(self, monkeypatch, tmp_path):
        bot, client = self._fired_bot(monkeypatch, tmp=tmp_path)
        asyncio.run(bot.run_daily())
        bot2 = _bot(client, tmp=tmp_path)
        assert f"{CHAIN}:A" in bot2.books["sim"].portfolio.positions

    def test_daily_due_once_per_day_after_the_minute(self, monkeypatch):
        bot, client = self._fired_bot(monkeypatch)
        day0 = 1_800_000_000 // DAY * DAY
        bot.last_daily_run = day0 + 700
        assert not bot._daily_due(day0 + 5000)
        assert not bot._daily_due(day0 + DAY + 100)     # before 00:10
        assert bot._daily_due(day0 + DAY + 700)

    def test_state_is_json_serialisable_and_dashboard_renders(self, monkeypatch):
        import json
        from fastapi.testclient import TestClient
        from cryptobot.dashboard import create_app
        bot, client = self._fired_bot(monkeypatch)
        asyncio.run(bot.run_daily())
        asyncio.run(bot.monitor())
        json.dumps(bot.state())
        app = create_app(bot, token="t", extra_hosts={"testserver"})
        c = TestClient(app)
        assert c.get("/").status_code == 200
        r = c.get("/api/state", headers={"x-dashboard-token": "t"})
        assert r.status_code == 200
        assert r.json()["strategy"]["rule"] == "move_1d[2] & move_3d[0]"


class TestFunding:
    def test_short_receives_positive_funding_long_pays(self):
        pf = Portfolio()
        pos = pf.open_from_signal(_sig(t=0.0), 100.0)
        assert pos.accrue_funding(0.001, 3600 * 10) == pytest.approx(1.0)    # 10h x 0.1%
        assert pos.funding_usd == pytest.approx(1.0)
        assert pos.accrue_funding(0.001, 3600 * 12) == pytest.approx(0.2)    # only 2 more hours
        lp = Portfolio().open_from_signal(_sig(side=Side.LONG, t=0.0), 100.0)
        assert lp.accrue_funding(0.001, 3600) == pytest.approx(-0.1)

    def test_funding_flows_into_pnl_and_the_closed_trade(self):
        pf = Portfolio()
        pos = pf.open_from_signal(_sig(t=0.0), 100.0)
        pos.accrue_funding(0.002, 3600 * 5)                # +1.00
        assert pos.unrealized_pnl(100.0) == pytest.approx(1.0)
        trade = pf.close(f"{CHAIN}:X", 100.0, "time_exit")
        assert trade.funding_usd == pytest.approx(1.0)
        assert trade.pnl_usd == pytest.approx(1.0)

    def test_monitor_accrues_and_persists(self, monkeypatch, tmp_path):
        client = FakeClient({"A": _series(bounce=True), "B": _series(), "C": _series(),
                             "D": _series(), "E": _series(), "F": _series()},
                            {"A": 100.0}, funding={"A": 0.001})
        t0 = client.t0 + 400 * DAY + 3600
        monkeypatch.setattr(PB, "now", lambda: t0)
        bot = _bot(client, tmp=tmp_path)
        asyncio.run(bot.run_daily())
        pos = bot.books["sim"].portfolio.positions[f"{CHAIN}:A"]
        client.mids["A"] = pos.entry_price
        monkeypatch.setattr(PB, "now", lambda: t0 + 3600 * 24)
        asyncio.run(bot.monitor())
        assert pos.funding_usd == pytest.approx(pos.size_usd * 0.001 * 24)
        again = _bot(client, tmp=tmp_path)
        assert again.books["sim"].portfolio.positions[f"{CHAIN}:A"].funding_usd \
            == pytest.approx(pos.funding_usd)
        assert bot.state()["strategy"]["funding_hourly"]["A"] == 0.001

    def test_old_state_files_without_funding_fields_still_load(self, tmp_path):
        import json
        f = tmp_path / "p.json"
        pf = Portfolio(state_file=f)
        pf.open_from_signal(_sig(), 50.0)
        data = json.loads(f.read_text())
        for p in data["positions"]:
            p.pop("funding_usd"); p.pop("funding_accrued_at")
        f.write_text(json.dumps(data))
        assert Portfolio(state_file=f).positions[f"{CHAIN}:X"].funding_usd == 0.0


class TestExecutor:
    def test_dry_run_without_arming(self, monkeypatch):
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
        monkeypatch.setenv("CRYPTOBOT_PRIVATE_KEY", "0x" + "1" * 64)
        ex = PerpExecutor(PerpExecConfig(live=True))
        assert not ex.armed
        fill = asyncio.run(ex.open_short("kPEPE", 30.0, 0.01))
        assert fill.dry_run and fill.qty == pytest.approx(3000.0)

    def test_live_without_key_is_dry_run(self, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
        monkeypatch.delenv("CRYPTOBOT_PRIVATE_KEY", raising=False)
        assert not PerpExecutor(PerpExecConfig(live=True)).armed

    def test_all_three_conditions_arm(self, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
        monkeypatch.setenv("CRYPTOBOT_PRIVATE_KEY", "0x" + "1" * 64)
        assert PerpExecutor(PerpExecConfig(live=True)).armed
        assert not PerpExecutor(PerpExecConfig(live=False)).armed

    def test_notional_is_capped(self, monkeypatch):
        monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
        ex = PerpExecutor(PerpExecConfig(max_trade_usd=20))
        fill = asyncio.run(ex.open_short("X", 500.0, 2.0))
        assert fill.qty == pytest.approx(10.0)

    def test_armed_order_parses_a_fill(self, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
        monkeypatch.setenv("CRYPTOBOT_PRIVATE_KEY", "0x" + "1" * 64)
        ex = PerpExecutor(PerpExecConfig(live=True))

        class FakeInfo:
            def meta(self):
                return {"universe": [{"name": "X", "szDecimals": 1}]}

        class FakeExchange:
            def __init__(self):
                self.orders = []

            def update_leverage(self, *a, **k):
                pass

            def order(self, coin, is_buy, sz, px, typ, reduce_only=False):
                self.orders.append((coin, is_buy, sz, px, reduce_only))
                return {"response": {"data": {"statuses": [
                    {"filled": {"totalSz": str(sz), "avgPx": str(px), "oid": 7}}]}}}
        ex._info, ex._exchange = FakeInfo(), FakeExchange()
        fill = asyncio.run(ex.open_short("X", 30.0, 2.0))
        assert fill.side == "short" and fill.order_id == 7 and not fill.dry_run
        coin, is_buy, sz, px, ro = ex._exchange.orders[0]
        assert not is_buy and not ro and sz == 15.0 and px == pytest.approx(1.98)
        asyncio.run(ex.close("X", 15.0, 2.0))
        assert ex._exchange.orders[1][1] is True and ex._exchange.orders[1][4] is True

    def test_rejected_order_raises(self, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_ARM_LIVE", "yes")
        monkeypatch.setenv("CRYPTOBOT_PRIVATE_KEY", "0x" + "1" * 64)
        ex = PerpExecutor(PerpExecConfig(live=True))

        class FakeInfo:
            def meta(self):
                return {"universe": [{"name": "X", "szDecimals": 1}]}

        class FakeExchange:
            def update_leverage(self, *a, **k):
                pass

            def order(self, *a, **k):
                return {"response": {"data": {"statuses": [{"error": "no margin"}]}}}
        ex._info, ex._exchange = FakeInfo(), FakeExchange()
        with pytest.raises(RuntimeError, match="no margin"):
            asyncio.run(ex.open_short("X", 30.0, 2.0))


class TestReplay:
    def test_replay_trades_the_bounce_and_reports_by_year(self):
        from cryptobot.backtest import PoolMeta
        import datetime as dt
        t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp()
        pools = {}
        for k in range(6):
            closes = _series(500, bounce=(k == 0))
            # put the bounce mid-series so the replay sees the exit too
            if k == 0:
                closes = closes[:-4] + closes[-4:] + [closes[-1] * 0.85] * 20
            meta = PoolMeta(chain="hyperliquid", pair_address=f"C{k}", symbol=f"C{k}",
                            token_address="", liquidity_usd=0.0, fdv_usd=None)
            pools[str(k)] = (meta, [Candle(ts=t0 + i * DAY, open=c, high=c * 1.01,
                                           low=c * 0.99, close=c, volume_usd=1.0)
                                    for i, c in enumerate(closes)])
        cfg = PerpBotConfig(coins=tuple(f"C{k}" for k in range(6)), min_history_days=50)
        rep = asyncio.run(PB.replay(pools, t0 + 470 * DAY, cfg))
        assert rep["trades"] >= 1
        assert set(rep["exits"]) <= {"take_profit", "stop_loss", "time_exit", "breakeven_stop"}
        assert set(rep["by_year"]) == {2025}          # historical clock, not today's


def test_build_coinbase_venue_uses_us_universe_and_whole_contract_executor(tmp_path, monkeypatch):
    from cryptobot.execution.coinbase_futures import CoinbaseFuturesExecutor, US_COINS
    from cryptobot.data.coinbase_futures import CoinbaseMarketData
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    cfg = {"perp": {"venue": "coinbase", "max_trade_usd": 500},
           "allocation": {"carry": 0.0, "bounce_short": 1.0},
           "sim": {"bankroll_usd": 200}, "risk": {"bankroll_usd": 1500}}
    bot = PB.build(cfg, tmp_path)
    assert tuple(bot.cfg.coins) == US_COINS
    assert isinstance(bot.executor, CoinbaseFuturesExecutor)
    assert isinstance(bot.client, CoinbaseMarketData)
    assert not bot.executor.armed


def test_build_rejects_unknown_venue(tmp_path):
    with pytest.raises(ValueError):
        PB.build({"perp": {"venue": "binance"}}, tmp_path)
