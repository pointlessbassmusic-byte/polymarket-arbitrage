"""Tests for the crypto volatility bot: volatility engine, signal
detectors, risk sizing, portfolio exits, and DexScreener parsing."""

import time

import pytest

from cryptobot.analytics import MIN_SAMPLES, MULT_CAP, MULT_FLOOR, EdgeTracker
from cryptobot.data.dexscreener import parse_pair
from cryptobot.models import ClosedTrade, Side, Signal, SignalType, TokenSnapshot
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
