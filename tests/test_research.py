"""Tests for the signal-research module.

The failure mode that matters here is a study that reports an edge which
is not there, so these tests check the measurements against hand-built
price paths whose answers are known by construction.
"""

import math

import pytest

from cryptobot.backtest import Candle, PoolMeta
from cryptobot import research as R


def _meta(symbol="TEST"):
    return PoolMeta(chain="base", pair_address="0xpair", symbol=symbol,
                    token_address="0xtok", liquidity_usd=500_000.0, fdv_usd=None)


def _candles(closes, *, highs=None, lows=None, vol=1000.0, start=1_700_000_000):
    highs = highs or closes
    lows = lows or closes
    return [Candle(ts=start + 300 * i, open=c, high=highs[i], low=lows[i],
                   close=c, volume_usd=vol)
            for i, c in enumerate(closes)]


class TestBarrier:
    def test_breakeven_matches_the_algebra(self):
        # +4%/-2% with 1.2% friction: (0.02+0.012)/(0.04+0.02) = 53.3%
        assert R.Barrier(0.04, 0.02).breakeven(0.012) == pytest.approx(0.5333, abs=1e-4)

    def test_breakeven_hit_rate_yields_exactly_zero_net(self):
        bar = R.Barrier(0.06, 0.02)
        cost = 0.012
        p = bar.breakeven(cost)
        assert bar.gross(p) - cost == pytest.approx(0.0, abs=1e-12)

    def test_zero_cost_breakeven_is_the_geometric_one(self):
        assert R.Barrier(0.03, 0.01).breakeven(0.0) == pytest.approx(0.25)


class TestBarrierOutcome:
    def test_target_reached_counts_as_a_win(self):
        highs = [100, 100, 105]
        lows = [100, 100, 100]
        assert R.barrier_outcome(highs, lows, 0, 100.0, R.Barrier(0.04, 0.02), 10) == 1

    def test_stop_reached_counts_as_a_loss(self):
        highs = [100, 100, 100]
        lows = [100, 100, 97]
        assert R.barrier_outcome(highs, lows, 0, 100.0, R.Barrier(0.04, 0.02), 10) == 0

    def test_candle_touching_both_barriers_is_scored_as_the_loss(self):
        # Intra-candle order is unknown; assuming the win would inflate
        # every hit rate in the study.
        highs = [100, 110]
        lows = [100, 90]
        assert R.barrier_outcome(highs, lows, 0, 100.0, R.Barrier(0.04, 0.02), 10) == 0

    def test_stop_hit_first_in_time_beats_a_later_target(self):
        highs = [100, 100, 110]
        lows = [100, 97, 100]
        assert R.barrier_outcome(highs, lows, 0, 100.0, R.Barrier(0.04, 0.02), 10) == 0

    def test_horizon_expiry_is_not_a_win(self):
        highs = [100] * 5 + [200]
        lows = [100] * 6
        # target is reached at index 5, outside a 3-candle horizon
        assert R.barrier_outcome(highs, lows, 0, 100.0, R.Barrier(0.04, 0.02), 3) == 0

    def test_running_off_the_end_of_the_series_is_not_a_win(self):
        assert R.barrier_outcome([100], [100], 0, 100.0, R.Barrier(0.04, 0.02), 50) == 0


class TestFeatures:
    def test_lookback_moves_use_the_right_offsets(self):
        closes = [100.0] * (R.WARMUP + 1)
        closes[-1] = 110.0           # i
        closes[-2] = 100.0           # i-1
        closes[-7] = 50.0            # i-6  (30m)
        i = len(closes) - 1
        f = R.features_at(closes, [1000.0] * len(closes), i)
        assert f["move_5m"] == pytest.approx(0.10)
        assert f["move_30m"] == pytest.approx(1.20)
        assert f["move_24h"] == pytest.approx(0.10)

    def test_volume_surge_is_one_when_volume_is_flat(self):
        n = R.WARMUP + 1
        f = R.features_at([100.0] * n, [500.0] * n, n - 1)
        assert f["vol_surge"] == pytest.approx(1.0, abs=1e-6)

    def test_volume_surge_rises_with_a_recent_burst(self):
        n = R.WARMUP + 1
        vols = [100.0] * n
        for k in range(n - R.PER_HOUR, n):
            vols[k] = 1000.0
        f = R.features_at([100.0] * n, vols, n - 1)
        assert f["vol_surge"] > 5.0

    def test_features_only_use_data_up_to_i(self):
        # A spike AFTER i must not change any feature at i.
        n = R.WARMUP + 20
        closes = [100.0] * n
        a = R.features_at(closes, [100.0] * n, R.WARMUP)
        closes[R.WARMUP + 5] = 10_000.0
        b = R.features_at(closes, [100.0] * n, R.WARMUP)
        assert a == b

    def test_zscore_is_zero_on_a_flat_series(self):
        n = R.WARMUP + 1
        f = R.features_at([100.0] * n, [100.0] * n, n - 1)
        assert f["zscore_5m"] == pytest.approx(0.0)

    def test_zero_prices_do_not_raise(self):
        n = R.WARMUP + 1
        closes = [0.0] * n
        closes[-1] = 100.0
        R.features_at(closes, [0.0] * n, n - 1)   # must not raise


class TestCollect:
    def test_pools_shorter_than_warmup_plus_horizon_are_skipped(self):
        pools = {"a": (_meta(), _candles([100.0] * 50))}
        assert R.collect(pools, R.Barrier(0.04, 0.02), 12) == []

    def test_rows_come_back_in_timestamp_order(self):
        n = R.WARMUP + 200
        pools = {
            "a": (_meta("A"), _candles([100.0] * n, start=1_700_000_000)),
            "b": (_meta("B"), _candles([100.0] * n, start=1_700_000_000)),
        }
        rows = R.collect(pools, R.Barrier(0.04, 0.02), 12)
        assert rows
        assert [r["ts"] for r in rows] == sorted(r["ts"] for r in rows)

    def test_a_relentless_uptrend_wins_every_sample(self):
        n = R.WARMUP + 200
        closes = [100.0 * (1.01 ** i) for i in range(n)]
        pools = {"a": (_meta(), _candles(closes))}
        rows = R.collect(pools, R.Barrier(0.04, 0.02), 24)
        assert rows
        assert R.hit_rate(rows) == 1.0

    def test_a_relentless_downtrend_wins_nothing(self):
        n = R.WARMUP + 200
        closes = [100.0 * (0.99 ** i) for i in range(n)]
        pools = {"a": (_meta(), _candles(closes))}
        rows = R.collect(pools, R.Barrier(0.04, 0.02), 24)
        assert rows
        assert R.hit_rate(rows) == 0.0


class TestBuckets:
    def test_bucket_of_places_values_between_cuts(self):
        cuts = [0.0, 1.0]
        assert R.bucket_of(-5.0, cuts) == 0
        assert R.bucket_of(0.5, cuts) == 1
        assert R.bucket_of(99.0, cuts) == 2

    def test_quantile_cuts_split_evenly(self):
        rows = [{"x": float(i)} for i in range(100)]
        cuts = R.quantiles(rows, "x", 4)
        assert len(cuts) == 3
        assert cuts == [25.0, 50.0, 75.0]


class TestValidate:
    def _rows(self, n, *, win_fn):
        out = []
        for i in range(n):
            r = {f: (i % 7) / 7.0 for f in R.FEATURES}
            r["ts"] = 1_700_000_000 + 300 * i
            r["symbol"] = "X"
            r["win"] = win_fn(i, r)
            out.append(r)
        return out

    def test_regime_swing_reports_the_difference_between_halves(self):
        rows = self._rows(4000, win_fn=lambda i, r: 1 if i >= 2000 else 0)
        rep = R.validate(rows, R.Barrier(0.04, 0.02), 0.012)
        assert rep["base_in"] == pytest.approx(0.0)
        assert rep["base_out"] == pytest.approx(1.0)
        assert rep["regime_swing"] == pytest.approx(1.0)

    def test_lift_is_measured_against_each_half_own_baseline(self):
        # Every row wins in the second half. Measured as a raw hit rate
        # every rule would look brilliant out of sample; measured as lift
        # they are all exactly zero, which is the truth.
        rows = self._rows(4000, win_fn=lambda i, r: 1 if i >= 2000 else 0)
        rep = R.validate(rows, R.Barrier(0.04, 0.02), 0.012)
        assert rep["rules"]
        assert all(abs(s["lift_out"]) < 1e-9 for s in rep["rules"])

    def test_a_genuinely_predictive_feature_shows_positive_correlation(self):
        def win(i, r):
            return 1 if r["move_24h"] > 0.5 else 0
        rows = self._rows(6000, win_fn=win)
        rep = R.validate(rows, R.Barrier(0.04, 0.02), 0.012)
        assert rep["pearson"] > 0.5
        assert rep["top_lift_out"] > 0.0

    def test_pure_noise_shows_no_selection_correlation(self):
        import random
        rng = random.Random(7)
        rows = self._rows(6000, win_fn=lambda i, r: rng.random() < 0.4)
        rep = R.validate(rows, R.Barrier(0.04, 0.02), 0.012)
        assert abs(rep["pearson"]) < 0.5

    def test_rules_too_small_in_either_half_are_dropped(self):
        rows = self._rows(600, win_fn=lambda i, r: 0)
        rep = R.validate(rows, R.Barrier(0.04, 0.02), 0.012)
        for s in rep["rules"]:
            assert s["n_in"] >= R.MIN_CELL and s["n_out"] >= R.MIN_CELL


class TestRendering:
    def test_renderers_produce_text_without_raising(self):
        n = R.WARMUP + 400
        closes = [100.0 + math.sin(i / 10.0) for i in range(n)]
        pools = {"a": (_meta(), _candles(closes))}
        bar = R.Barrier(0.04, 0.02)
        rows = R.collect(pools, bar, 24)
        assert "break-even" in R.render_buckets(R.bucket_report(rows, bar, 0.012),
                                                bar, 0.012)
        assert "regime swing" in R.render_validate(R.validate(rows, bar, 0.012))
        swept = R.sweep(pools, [(0.04, 0.02)], [6], 0.012)
        assert "barrier" in R.render_sweep(swept, 0.012)

    def test_verdict_appears_when_selection_fails(self):
        rep = {"span_in": (1_700_000_000, 1_700_100_000),
               "span_out": (1_700_100_000, 1_700_200_000),
               "base_in": 0.3, "base_out": 0.3, "regime_swing": 0.0,
               "n_rules": 5, "pearson": -0.2, "spearman": -0.1,
               "top_lift_in": 0.05, "top_lift_out": -0.02, "rules": []}
        assert "VERDICT" in R.render_validate(rep)
