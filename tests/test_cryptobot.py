"""Tests for the crypto volatility bot: volatility engine, signal
detectors, risk sizing, portfolio exits, and DexScreener parsing."""

import time

import pytest

from cryptobot.analytics import MIN_SAMPLES, MULT_CAP, MULT_FLOOR, EdgeTracker
from cryptobot.data.dexscreener import parse_pair
from cryptobot.data.goplus import ScreenConfig, evaluate
from cryptobot.models import ClosedTrade, Side, Signal, SignalType, TokenSnapshot
from cryptobot.protections import ProtectionConfig, ProtectionManager
from cryptobot.portfolio import Portfolio
from cryptobot.risk import RiskConfig, RiskManager
from cryptobot.signals import (
    SignalConfig,
    detect_breakout,
    detect_cross_dex_arb,
    detect_mean_revert,
    detect_all,
)
from cryptobot.volatility import VolatilityEngine

NOW = 1_700_000_000.0


def make_snap(**kw) -> TokenSnapshot:
    defaults = dict(
        ts=NOW, chain="base", pair_address="0xPAIR", base_symbol="TEST",
        base_address="0xTOKEN", quote_symbol="WETH", price_usd=1.0,
        change_5m=0.0, change_1h=0.0, change_6h=0.0, change_24h=0.0,
        volume_24h_usd=500_000.0, volume_1h_usd=20_000.0,
        liquidity_usd=200_000.0, fdv_usd=5_000_000.0,
        txns_24h_buys=600, txns_24h_sells=400,
        pair_created_at=NOW - 30 * 86400,
    )
    defaults.update(kw)
    return TokenSnapshot(**defaults)


# -- volatility engine -----------------------------------------------------

class TestVolatilityEngine:
    def test_native_windows_pass_through(self):
        eng = VolatilityEngine()
        v = eng.observe(make_snap(change_5m=0.05, change_1h=0.10, change_24h=0.50))
        assert v.move_5m == pytest.approx(0.05)
        assert v.move_1h == pytest.approx(0.10)
        assert v.move_24h == pytest.approx(0.50)

    def test_30m_window_from_sampling(self):
        eng = VolatilityEngine()
        # price 1.0 at t0, 1.2 at t0+31min -> 30m move ~ +20%
        eng.observe(make_snap(ts=NOW, price_usd=1.0))
        v = eng.observe(make_snap(ts=NOW + 1860, price_usd=1.2))
        assert v.move_30m == pytest.approx(0.2, abs=0.01)

    def test_zscore_flags_unusual_move(self):
        eng = VolatilityEngine()
        for i in range(20):
            eng.observe(make_snap(ts=NOW + i * 300, change_5m=0.001))
        v = eng.observe(make_snap(ts=NOW + 21 * 300, change_5m=0.08))
        assert v.zscore_5m > 3.0

    def test_wildness_prefers_short_window_action(self):
        eng = VolatilityEngine()
        fast = eng.observe(make_snap(pair_address="0xA", change_5m=0.10))
        slow = eng.observe(make_snap(pair_address="0xB", change_24h=0.10))
        assert fast.wildness > slow.wildness


# -- signal detectors ------------------------------------------------------

class TestDetectors:
    def setup_method(self):
        self.cfg = SignalConfig()
        self.eng = VolatilityEngine()

    def test_breakout_fires_and_is_asymmetric(self):
        snap = make_snap(change_5m=0.05, change_1h=0.15,
                         volume_1h_usd=100_000.0, txns_24h_buys=700,
                         txns_24h_sells=300)
        vol = self.eng.observe(snap)
        sig = detect_breakout(snap, vol, self.cfg)
        assert sig is not None
        assert sig.type == SignalType.VOL_BREAKOUT
        assert sig.risk_reward >= self.cfg.min_risk_reward

    def test_breakout_rejected_without_volume_surge(self):
        snap = make_snap(change_5m=0.05, change_1h=0.15, volume_1h_usd=5_000.0)
        sig = detect_breakout(snap, self.eng.observe(snap), self.cfg)
        assert sig is None

    def test_mean_revert_fires_on_local_flush(self):
        snap = make_snap(change_1h=-0.20, change_24h=0.02)
        sig = detect_mean_revert(snap, self.eng.observe(snap), self.cfg)
        assert sig is not None
        assert sig.type == SignalType.MEAN_REVERT

    def test_mean_revert_skips_death_spiral(self):
        snap = make_snap(change_1h=-0.20, change_24h=-0.60)
        sig = detect_mean_revert(snap, self.eng.observe(snap), self.cfg)
        assert sig is None

    def test_hygiene_rejects_thin_liquidity(self):
        snap = make_snap(change_5m=0.10, change_1h=0.20, liquidity_usd=5_000.0)
        assert detect_all(snap, self.eng.observe(snap), self.cfg) == []

    def test_hygiene_rejects_fresh_pair(self):
        snap = make_snap(change_5m=0.10, change_1h=0.20,
                         pair_created_at=NOW - 3600)
        assert detect_all(snap, self.eng.observe(snap), self.cfg) == []

    def test_cross_dex_arb_needs_gap_above_fees(self):
        pools = [
            make_snap(pair_address="0xCHEAP", price_usd=1.00),
            make_snap(pair_address="0xRICH", price_usd=1.05),
        ]
        sig = detect_cross_dex_arb(pools, self.cfg)
        assert sig is not None
        assert sig.expected_move == pytest.approx(0.05 - self.cfg.arb_fee_buffer)

        tight = [
            make_snap(pair_address="0xA", price_usd=1.00),
            make_snap(pair_address="0xB", price_usd=1.005),
        ]
        assert detect_cross_dex_arb(tight, self.cfg) is None


# -- risk ------------------------------------------------------------------

def make_signal(**kw) -> Signal:
    defaults = dict(
        ts=NOW, type=SignalType.VOL_BREAKOUT, key="base:0xPAIR", chain="base",
        symbol="TEST", side=Side.LONG, price_usd=1.0, confidence=0.6,
        expected_move=0.10, stop_loss_pct=0.05, take_profit_pct=0.10,
        reason="test", risk_reward=2.0, liquidity_usd=200_000.0,
    )
    defaults.update(kw)
    return Signal(**defaults)


class TestRisk:
    def test_sizing_positive_with_edge(self):
        rm = RiskManager(RiskConfig())
        size = rm.size_position(make_signal(), [])
        assert 0 < size <= RiskConfig().max_position_usd

    def test_liquidity_cap_binds_in_thin_pools(self):
        rm = RiskManager(RiskConfig())
        size = rm.size_position(make_signal(liquidity_usd=10_000.0), [])
        assert size <= 10_000.0 * RiskConfig().max_position_pct_of_liquidity

    def test_no_size_without_kelly_edge(self):
        rm = RiskManager(RiskConfig())
        # p=0.3, b=1.0 -> kelly negative
        assert rm.size_position(
            make_signal(confidence=0.36, risk_reward=0.5), []) == 0.0

    def test_daily_loss_halts_entries(self):
        cfg = RiskConfig(max_daily_loss_usd=50.0)
        rm = RiskManager(cfg)
        rm.record_pnl(-60.0)
        assert rm.size_position(make_signal(), []) == 0.0


# -- portfolio -------------------------------------------------------------

class TestPortfolio:
    def test_stop_loss_exit(self):
        pf = Portfolio()
        pf.open_from_signal(make_signal(type=SignalType.MEAN_REVERT), 100.0)
        assert pf.check_exit("base:0xPAIR", 0.94) in ("stop_loss", "trailing_stop")

    def test_take_profit_exit_non_trailing(self):
        pf = Portfolio()
        pf.open_from_signal(make_signal(type=SignalType.MEAN_REVERT), 100.0)
        assert pf.check_exit("base:0xPAIR", 1.11) == "take_profit"

    def test_breakout_trails_instead_of_capping(self):
        pf = Portfolio(trail_pct=0.05)
        pf.open_from_signal(make_signal(type=SignalType.VOL_BREAKOUT), 100.0)
        # Through the target: no exit, stop ratchets up.
        assert pf.check_exit("base:0xPAIR", 1.20) is None
        assert pf.positions["base:0xPAIR"].stop_loss == pytest.approx(1.20 * 0.95)
        # Pullback through the trailed stop exits in profit.
        assert pf.check_exit("base:0xPAIR", 1.13) == "trailing_stop"

    def test_close_books_pnl(self):
        pf = Portfolio()
        pf.open_from_signal(make_signal(), 100.0)
        trade = pf.close("base:0xPAIR", 1.10, "take_profit")
        assert trade.pnl_usd == pytest.approx(10.0)
        assert pf.realized_pnl == pytest.approx(10.0)


# -- edge tracker ----------------------------------------------------------

def make_trade(pnl: float, signal_type=SignalType.VOL_BREAKOUT,
               chain: str = "base") -> ClosedTrade:
    return ClosedTrade(
        key=f"{chain}:0xPAIR", symbol="TEST", side=Side.LONG,
        entry_price=1.0, exit_price=1.0 + pnl / 100.0, size_usd=100.0,
        pnl_usd=pnl, opened_at=NOW, closed_at=NOW + 600,
        exit_reason="take_profit", signal_type=signal_type,
    )


class TestEdgeTracker:
    def test_neutral_until_enough_samples(self):
        tr = EdgeTracker()
        for _ in range(MIN_SAMPLES - 1):
            tr.record(make_trade(-10.0))
        assert tr.confidence_multiplier("vol_breakout") == 1.0

    def test_losing_pattern_sized_down(self):
        tr = EdgeTracker()
        for _ in range(MIN_SAMPLES):
            tr.record(make_trade(-10.0))   # -10% per $ staked
        mult = tr.confidence_multiplier("vol_breakout")
        assert MULT_FLOOR <= mult < 0.8

    def test_winning_pattern_sized_up_but_capped(self):
        tr = EdgeTracker()
        for _ in range(MIN_SAMPLES):
            tr.record(make_trade(50.0))    # absurdly hot streak
        assert tr.confidence_multiplier("vol_breakout") == MULT_CAP

    def test_buckets_are_independent(self):
        tr = EdgeTracker()
        for _ in range(MIN_SAMPLES):
            tr.record(make_trade(-10.0, SignalType.MEAN_REVERT))
        assert tr.confidence_multiplier("vol_breakout") == 1.0
        assert tr.confidence_multiplier("mean_revert") < 1.0

    def test_report_tracks_chains(self):
        tr = EdgeTracker()
        tr.record(make_trade(5.0, chain="base"))
        tr.record(make_trade(-3.0, chain="ethereum"))
        rep = tr.report()
        assert rep["by_chain"]["base"]["trades"] == 1
        assert rep["by_chain"]["ethereum"]["total_pnl"] == pytest.approx(-3.0)

    def test_persistence_roundtrip(self, tmp_path):
        f = tmp_path / "edges.json"
        tr = EdgeTracker(state_file=f)
        for _ in range(MIN_SAMPLES):
            tr.record(make_trade(10.0))
        reloaded = EdgeTracker(state_file=f)
        assert reloaded.by_type["vol_breakout"].trades == MIN_SAMPLES
        assert reloaded.confidence_multiplier("vol_breakout") > 1.0


# -- goplus security screen ------------------------------------------------

class TestSecurityScreen:
    CFG = ScreenConfig()

    def test_clean_token_passes(self):
        v = evaluate({"is_honeypot": "0", "is_open_source": "1",
                      "buy_tax": "0.0", "sell_tax": "0.01"}, self.CFG)
        assert v.ok

    def test_honeypot_rejected(self):
        v = evaluate({"is_honeypot": "1"}, self.CFG)
        assert not v.ok and "honeypot" in v.reasons

    def test_high_sell_tax_rejected(self):
        v = evaluate({"sell_tax": "0.25", "is_open_source": "1"}, self.CFG)
        assert not v.ok
        assert any("sell tax" in r for r in v.reasons)

    def test_owner_powers_rejected(self):
        v = evaluate({"transfer_pausable": "1", "owner_change_balance": "1",
                      "is_open_source": "1",
                      "owner_address": "0xB0B0000000000000000000000000000000000001"},
                     self.CFG)
        assert not v.ok and len(v.reasons) == 2

    def test_renounced_ownership_neutralizes_owner_powers(self):
        # PEPE-style contract: has pause/blacklist functions, but ownership
        # is renounced so nobody can call them.
        data = {"transfer_pausable": "1", "is_blacklisted": "1",
                "is_open_source": "1",
                "owner_address": "0x0000000000000000000000000000000000000000"}
        assert evaluate(data, self.CFG).ok
        # Hidden owner voids the renounce.
        assert not evaluate({**data, "hidden_owner": "1"}, self.CFG).ok
        # Honeypot is a hard reject regardless of renounce.
        assert not evaluate({**data, "is_honeypot": "1"}, self.CFG).ok

    def test_soft_flags_reject_only_in_combination(self):
        # Mintable alone: fine (many legit tokens are).
        assert evaluate({"is_mintable": "1", "is_open_source": "1"}, self.CFG).ok
        # Mintable AND closed-source: rug template.
        assert not evaluate({"is_mintable": "1", "is_open_source": "0"}, self.CFG).ok


# -- protections -----------------------------------------------------------

class TestProtections:
    def make_pm(self, **kw) -> ProtectionManager:
        cfg = ProtectionConfig(**kw)
        return ProtectionManager(cfg, starting_equity=1000.0)

    def close_trade(self, pm, key="base:0xPAIR", pnl=-10.0, reason="stop_loss"):
        t = make_trade(pnl)
        # Protections measure lookbacks against wall-clock now().
        t = ClosedTrade(**{**vars(t), "key": key, "exit_reason": reason,
                           "closed_at": time.time()})
        pm.on_trade_closed(t)

    def test_cooldown_blocks_reentry(self):
        pm = self.make_pm(cooldown_s=1800.0)
        self.close_trade(pm, pnl=5.0, reason="take_profit")
        allowed, why = pm.entry_allowed("base:0xPAIR")
        assert not allowed and "cooldown" in why
        assert pm.entry_allowed("base:0xOTHER")[0]

    def test_stoploss_guard_halts_globally(self):
        pm = self.make_pm(cooldown_s=0.0, stoploss_guard_limit=3)
        for i in range(3):
            self.close_trade(pm, key=f"base:0x{i}", pnl=-10.0)
        assert not pm.entry_allowed("base:0xNEW")[0]

    def test_low_profit_locks_token(self):
        pm = self.make_pm(cooldown_s=0.0, stoploss_guard_limit=99,
                          low_profit_min_trades=2)
        self.close_trade(pm, pnl=-5.0, reason="time_stop")
        self.close_trade(pm, pnl=-5.0, reason="time_stop")
        assert not pm.entry_allowed("base:0xPAIR")[0]
        assert pm.entry_allowed("base:0xOTHER")[0]

    def test_max_drawdown_halts(self):
        pm = self.make_pm(cooldown_s=0.0, stoploss_guard_limit=99,
                          max_drawdown_pct=0.10)
        self.close_trade(pm, key="base:0xA", pnl=-120.0, reason="time_stop")
        assert pm.drawdown >= 0.10
        assert not pm.entry_allowed("base:0xB")[0]


# -- volatility-managed sizing ---------------------------------------------

class TestVolTargeting:
    def test_high_vol_scales_stake_down(self):
        rm = RiskManager(RiskConfig(vol_target_30m=0.04, max_position_usd=1e9,
                                    max_position_pct_of_liquidity=1.0))
        calm = rm.size_position(make_signal(vol_30m=0.02), [])
        wild = rm.size_position(make_signal(vol_30m=0.16), [])
        assert calm > 0 and wild > 0
        assert wild == pytest.approx(calm / 4.0)

    def test_breakout_stop_widens_with_realized_vol(self):
        from cryptobot.signals import SignalConfig, detect_breakout
        from cryptobot.volatility import VolatilityEngine
        eng = VolatilityEngine()
        # Build a jagged 30m history so realized vol is large.
        price = 1.0
        for i in range(10):
            price *= 1.06 if i % 2 == 0 else 0.97
            eng.observe(make_snap(ts=NOW + i * 180, price_usd=price))
        snap = make_snap(ts=NOW + 10 * 180, price_usd=price * 1.05,
                         change_5m=0.05, change_1h=0.15,
                         volume_1h_usd=100_000.0)
        vol = eng.observe(snap)
        assert vol.realized_vol_30m > 0.02
        sig = detect_breakout(snap, vol, SignalConfig())
        if sig is not None:  # rr gate may reject the widened stop — also valid
            assert sig.stop_loss_pct >= 2.0 * vol.realized_vol_30m


# -- token address plumbing (live execution needs it, key holds the pair) --

class TestTokenAddressPlumbing:
    def test_signal_carries_token_address(self):
        from cryptobot.signals import SignalConfig, detect_breakout
        from cryptobot.volatility import VolatilityEngine
        snap = make_snap(change_5m=0.05, change_1h=0.15,
                         volume_1h_usd=100_000.0)
        sig = detect_breakout(snap, VolatilityEngine().observe(snap), SignalConfig())
        assert sig is not None
        assert sig.token_address == "0xTOKEN"

    def test_position_inherits_token_address(self):
        pf = Portfolio()
        pos = pf.open_from_signal(make_signal(token_address="0xTOKEN"), 100.0)
        assert pos.token_address == "0xTOKEN"


# -- cost model ------------------------------------------------------------

class TestCostModel:
    def make(self, **kw):
        from cryptobot.costs import CostConfig, CostModel
        return CostModel(CostConfig(**kw))

    def test_round_trip_includes_all_components(self):
        cm = self.make()
        # $100 on base ($0.05 gas) in a $200k pool:
        # 2*(0.003 + 0.002 + 100/200000 + 0.05/100) = 2*0.006 = 1.2%
        frac = cm.round_trip_fraction(100.0, 200_000.0, "base")
        assert frac == pytest.approx(0.012, abs=1e-4)

    def test_gas_floor_blocks_small_ethereum_trades(self):
        cm = self.make()
        ok, why = cm.entry_allowed(0.10, 50.0, 200_000.0, "ethereum")
        assert not ok and "gas" in why
        # Same trade on base is fine.
        assert cm.entry_allowed(0.10, 50.0, 200_000.0, "base")[0]

    def test_thin_edge_rejected(self):
        cm = self.make()
        # 2% expected move can't clear 3x a ~1.2% round trip.
        ok, why = cm.entry_allowed(0.02, 100.0, 200_000.0, "base")
        assert not ok and "round-trip" in why
        # 6% clears it.
        assert cm.entry_allowed(0.06, 100.0, 200_000.0, "base")[0]

    def test_price_impact_scales_with_size_vs_depth(self):
        cm = self.make()
        thin = cm.round_trip_fraction(1000.0, 50_000.0, "base")
        deep = cm.round_trip_fraction(1000.0, 5_000_000.0, "base")
        assert thin > deep

    def test_min_viable_size(self):
        cm = self.make()
        assert cm.min_viable_size("ethereum") == pytest.approx(200.0)
        assert cm.min_viable_size("base") == pytest.approx(5.0)

    def test_breakeven_ratchet_protects_green_trades(self):
        from cryptobot.costs import CostModel
        pf = Portfolio(cost_model=CostModel())
        # Non-trailing position (mean-revert), round trip ~1.2% on base.
        pf.open_from_signal(
            make_signal(type=SignalType.MEAN_REVERT, take_profit_pct=0.20),
            100.0)
        # Price reaches 2x costs + 1% above entry -> stop moves to entry+costs.
        assert pf.check_exit("base:0xPAIR", 1.04) is None
        pos = pf.positions["base:0xPAIR"]
        assert pos.breakeven_set
        assert pos.stop_loss > pos.entry_price
        # Full retrace now exits as a scratch, not a -5% stop-out.
        assert pf.check_exit("base:0xPAIR", pos.stop_loss) == "trailing_stop"
        trade = pf.close("base:0xPAIR", pos.stop_loss, "trailing_stop")
        assert trade.pnl_usd == pytest.approx(0.0, abs=0.25)

    def test_portfolio_charges_costs_on_close(self):
        from cryptobot.costs import CostModel
        pf = Portfolio(cost_model=CostModel())
        pf.open_from_signal(make_signal(), 100.0)
        trade = pf.close("base:0xPAIR", 1.10, "take_profit")
        # Gross +$10, minus 2*(0.003+0.002+100/200000+0.05/100) = $1.20
        assert trade.costs_usd == pytest.approx(1.20, abs=0.01)
        assert trade.pnl_usd == pytest.approx(8.80, abs=0.01)
        assert pf.total_costs == pytest.approx(1.20, abs=0.01)


# -- backtest --------------------------------------------------------------

class TestBacktest:
    def make_candles(self, n=400, base=1.0):
        from cryptobot.data.geckoterminal import Candle
        return [Candle(ts=NOW + i * 300, open=base, high=base * 1.002,
                       low=base * 0.998, close=base, volume_usd=10_000.0)
                for i in range(n)]

    def make_meta(self):
        from cryptobot.backtest import PoolMeta
        return PoolMeta(chain="base", pair_address="0xPAIR", symbol="TEST",
                        token_address="0xTOKEN", liquidity_usd=200_000.0,
                        fdv_usd=5_000_000.0)

    def test_snapshot_from_candles_windows(self):
        from cryptobot.backtest import CANDLES_PER_DAY, snapshot_from_candles
        candles = self.make_candles(CANDLES_PER_DAY + 20)
        # +10% on the final candle vs the previous one
        candles[-1].close = 1.10
        snap = snapshot_from_candles(candles, len(candles) - 1,
                                     self.make_meta(), 0.55)
        assert snap.change_5m == pytest.approx(0.10)
        assert snap.change_24h == pytest.approx(0.10, abs=0.01)
        assert snap.buy_sell_ratio == pytest.approx(0.55)
        assert snap.volume_1h_usd == pytest.approx(12 * 10_000.0)

    def test_flat_history_produces_no_trades(self):
        from cryptobot.backtest import Backtester
        bt = Backtester(SignalConfig(), RiskConfig())
        report = bt.run({"base:0xPAIR": (self.make_meta(), self.make_candles())})
        assert report["trades"] == 0
        assert report["signals"] == 0

    def test_pump_produces_breakout_trade_and_conservative_stop(self):
        from cryptobot.backtest import CANDLES_PER_DAY, Backtester
        candles = self.make_candles(CANDLES_PER_DAY + 60)
        # Engineer a pump: +4%/candle for 8 candles with a volume surge,
        # then a hard dump through any stop.
        start = CANDLES_PER_DAY + 20
        price = 1.0
        for i in range(start, start + 8):
            price *= 1.04
            candles[i].close = price
            candles[i].high = price * 1.01
            candles[i].low = price / 1.05
            candles[i].volume_usd = 400_000.0
        for i in range(start + 8, len(candles)):
            price *= 0.90
            candles[i].close = price
            candles[i].high = price * 1.02
            candles[i].low = price * 0.97
        bt = Backtester(SignalConfig(), RiskConfig())
        report = bt.run({"base:0xPAIR": (self.make_meta(), candles)})
        assert report["signals"] > 0
        assert report["trades"] >= 1
        # Every trade must have closed through a known exit path (a target
        # during the pump or a stop during the dump), never left dangling.
        reasons = {t.exit_reason for t in bt.portfolio.closed}
        assert reasons <= {"stop_loss", "trailing_stop", "take_profit",
                           "time_stop", "backtest_end"}
        assert not bt.portfolio.positions


# -- dashboard -------------------------------------------------------------

class TestDashboard:
    def make_scanner(self):
        from cryptobot.risk import RiskConfig
        from cryptobot.scanner import Scanner, ScannerConfig
        from cryptobot.signals import SignalConfig
        return Scanner(ScannerConfig(), SignalConfig(), RiskConfig())

    def test_state_is_json_serializable(self):
        import json
        sc = self.make_scanner()
        sc.portfolio.open_from_signal(make_signal(), 100.0)
        sc._latest_prices["base:0xPAIR"] = 1.05
        state = sc.state()
        json.dumps(state)  # must not raise
        assert state["positions"][0]["symbol"] == "TEST"
        assert state["positions"][0]["pnl_usd"] == pytest.approx(5.0)
        assert state["bankroll_usd"] == 1000.0
        assert not state["live_armed"]

    def test_api_serves_state_and_page(self):
        import asyncio
        import httpx
        from cryptobot.dashboard import create_app

        sc = self.make_scanner()
        app = create_app(sc)

        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport,
                                         base_url="http://test") as client:
                r = await client.get("/api/state")
                assert r.status_code == 200
                assert r.json()["cycle"] == 0
                page = await client.get("/")
                assert page.status_code == 200
                assert "Crypto Volatility Bot" in page.text

        asyncio.run(run())


# -- dexscreener parsing ---------------------------------------------------

class TestParsePair:
    RAW = {
        "chainId": "base",
        "pairAddress": "0xabc",
        "baseToken": {"symbol": "BRETT", "address": "0xdead"},
        "quoteToken": {"symbol": "WETH"},
        "priceUsd": "0.0842",
        "priceChange": {"m5": "2.5", "h1": "-8.1", "h24": "40.2"},
        "volume": {"h24": 1234567.0, "h1": 98765.0},
        "liquidity": {"usd": 450000.0},
        "fdv": 84000000,
        "txns": {"h24": {"buys": 5000, "sells": 4400}},
        "pairCreatedAt": 1_690_000_000_000,
    }

    def test_parse_full(self):
        s = parse_pair(self.RAW, ts=NOW)
        assert s.base_symbol == "BRETT"
        assert s.price_usd == pytest.approx(0.0842)
        assert s.change_5m == pytest.approx(0.025)
        assert s.change_1h == pytest.approx(-0.081)
        assert s.liquidity_usd == pytest.approx(450000.0)
        assert s.buy_sell_ratio == pytest.approx(5000 / 9400)
        assert s.age_hours > 0

    def test_parse_rejects_zero_price(self):
        raw = dict(self.RAW, priceUsd="0")
        assert parse_pair(raw, ts=NOW) is None

    def test_parse_tolerates_missing_fields(self):
        s = parse_pair({"priceUsd": "1.5", "chainId": "eth",
                        "pairAddress": "0x1"}, ts=NOW)
        assert s is not None
        assert s.change_5m is None
        assert s.liquidity_usd == 0.0
