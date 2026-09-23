"""Tests for the regime study, against synthetic markets with known answers."""

import math
import random

import pytest

from cryptobot.backtest import Candle, PoolMeta
from cryptobot.research import Barrier
from cryptobot import regime as G

H = 3600


def _meta(sym):
    return PoolMeta(chain="base", pair_address=f"0x{sym}", symbol=sym,
                    token_address="0xtok", liquidity_usd=1e6, fdv_usd=None)


def _pool(sym, closes, start=1_700_000_000, highs=None, lows=None):
    highs = highs or closes
    lows = lows or closes
    return (_meta(sym), [Candle(ts=start + H * i, open=c, high=highs[i], low=lows[i],
                                close=c, volume_usd=1.0) for i, c in enumerate(closes)])


def _market(n_tokens=8, n_hours=2000, seed=1, drift_fn=None):
    """Tokens sharing a common regime factor plus idiosyncratic noise."""
    rng = random.Random(seed)
    common = [0.0]
    for t in range(1, n_hours):
        d = drift_fn(t) if drift_fn else 0.0
        common.append(common[-1] + d + rng.gauss(0, 0.004))
    pools = {}
    for k in range(n_tokens):
        px, closes = 100.0, []
        for t in range(n_hours):
            px *= math.exp((common[t] - common[t - 1] if t else 0.0) + rng.gauss(0, 0.006))
            closes.append(px)
        pools[str(k)] = _pool(f"T{k}", closes)
    return pools


class TestAlign:
    def test_pools_are_indexed_by_bucketed_timestamp(self):
        pools = {"a": _pool("A", [1.0, 2.0, 3.0])}
        stamps, by_sym = G.align(pools, candle_hours=1)
        assert len(stamps) == 3
        assert by_sym["A"][stamps[1]][0] == 2.0

    def test_zero_closes_are_dropped(self):
        pools = {"a": _pool("A", [1.0, 0.0, 3.0])}
        _, by_sym = G.align(pools, candle_hours=1)
        assert len(by_sym["A"]) == 2


class TestForward:
    def _series(self, closes, highs=None, lows=None):
        highs = highs or closes
        lows = lows or closes
        return {i * H: (closes[i], highs[i], lows[i]) for i in range(len(closes))}

    def test_target_first_is_a_win(self):
        s = self._series([100, 100, 105, 100])
        win, ret = G._forward(s, 0, H, 3, Barrier(0.04, 0.02))
        assert win == 1 and ret == pytest.approx(0.0)

    def test_stop_first_blocks_a_later_target(self):
        s = self._series([100, 97, 110, 110])
        win, _ = G._forward(s, 0, H, 3, Barrier(0.04, 0.02))
        assert win == 0

    def test_same_candle_touching_both_is_a_loss(self):
        s = self._series([100, 100], highs=[100, 110], lows=[100, 90])
        win, _ = G._forward(s, 0, H, 1, Barrier(0.04, 0.02))
        assert win == 0

    def test_plain_return_uses_last_available_close(self):
        s = self._series([100, 101, 102])
        _, ret = G._forward(s, 0, H, 2, Barrier(0.04, 0.02))
        assert ret == pytest.approx(0.02)

    def test_missing_forward_data_returns_none(self):
        s = self._series([100])
        assert G._forward(s, 0, H, 5, Barrier(0.04, 0.02)) is None


class TestObservations:
    def test_windows_do_not_overlap(self):
        pools = _market(n_tokens=6, n_hours=600)
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=Barrier(0.04, 0.02))
        gaps = {b["ts"] - a["ts"] for a, b in zip(rows, rows[1:])}
        assert gaps and min(gaps) >= 24 * H

    def test_thin_cross_sections_are_skipped(self):
        pools = _market(n_tokens=3, n_hours=600)   # below MIN_TOKENS
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=Barrier(0.04, 0.02))
        assert rows == []

    def test_breadth_is_one_when_every_token_rose(self):
        pools = {str(k): _pool(f"T{k}", [100.0 * 1.001 ** i for i in range(200)])
                 for k in range(6)}
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=Barrier(0.04, 0.02))
        assert rows and all(r["breadth"] == 1.0 for r in rows)


class TestPersistence:
    def test_alternating_state_has_negative_autocorr(self):
        rows = [{"breadth": 1.0 if i % 2 else 0.0} for i in range(100)]
        assert G.persistence(rows)["autocorr"] < -0.9

    def test_overlapping_windows_report_their_mechanical_null(self):
        rows = [{"breadth": 0.5} for _ in range(50)]
        p = G.persistence(rows, lookback_hours=168, horizon_hours=24)
        assert p["null"] == pytest.approx(6 / 7)
        assert p["lag"] == 7

    def test_clean_autocorr_uses_non_overlapping_lag(self):
        # Noise smoothed over 7 samples: lag-1 is high, lag-7 is not.
        rng = random.Random(4)
        raw = [rng.random() for _ in range(2000)]
        rows = [{"breadth": sum(raw[i:i + 7]) / 7} for i in range(1990)]
        p = G.persistence(rows, lookback_hours=168, horizon_hours=24)
        assert p["autocorr"] > 0.7
        assert abs(p["autocorr_clean"]) < 0.15

    def test_slow_regime_has_positive_autocorr_and_few_episodes(self):
        rows = [{"breadth": 1.0 if (i // 25) % 2 else 0.0} for i in range(100)]
        p = G.persistence(rows)
        assert p["autocorr"] > 0.9
        assert p["episodes"] == 4


class TestPredict:
    def _rows(self, n, fn):
        return [{"ts": i * 24 * H, "n_tokens": 8, "breadth": (i % 10) / 10.0,
                 "median": 0.0, **fn(i)} for i in range(n)]

    def test_lift_is_relative_to_each_half_own_baseline(self):
        # Every outcome jumps in the second half; no bucket is informative.
        rows = self._rows(400, lambda i: {"hit": 1.0 if i >= 200 else 0.0,
                                          "fwd": 0.1 if i >= 200 else 0.0})
        p = G.predict(rows, "breadth", Barrier(0.04, 0.02), 0.012)
        for c in p["test"]["cells"]:
            assert c and abs(c["hit_lift"]) < 1e-9

    def test_a_real_relationship_keeps_its_bucket_order(self):
        rows = self._rows(400, lambda i: {"hit": (i % 10) / 10.0,
                                          "fwd": (i % 10) / 100.0})
        p = G.predict(rows, "breadth", Barrier(0.04, 0.02), 0.012)
        assert p["order_corr"] > 0.9
        lifts = [c["hit_lift"] for c in p["test"]["cells"]]
        assert lifts == sorted(lifts)

    def test_random_outcomes_show_no_stable_order(self):
        rng = random.Random(3)
        agree = []
        for seed in range(6):
            rng = random.Random(seed)
            rows = self._rows(400, lambda i: {"hit": rng.random(), "fwd": rng.gauss(0, 0.05)})
            agree.append(G.predict(rows, "breadth", Barrier(0.04, 0.02), 0.012)["order_corr"])
        assert abs(sum(agree) / len(agree)) < 0.6

    def test_cuts_come_from_first_half_only(self):
        rows = self._rows(400, lambda i: {"hit": 0.3, "fwd": 0.0})
        for r in rows[200:]:
            r["breadth"] = 5.0            # second half is wildly different
        p = G.predict(rows, "breadth", Barrier(0.04, 0.02), 0.012)
        assert max(p["cuts"]) < 1.0


class TestEndToEnd:
    def test_regime_driven_market_is_detected(self):
        # Common factor drifts up for 200h then down for 200h, repeating.
        pools = _market(n_tokens=8, n_hours=4800, seed=5,
                        drift_fn=lambda t: 0.003 if (t // 200) % 2 == 0 else -0.003)
        bar = Barrier(0.04, 0.02)
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=bar)
        pers = G.persistence(rows)
        assert pers["autocorr"] > 0.3
        p = G.predict(rows, "breadth", bar, 0.012)
        cells = [c for c in p["test"]["cells"] if c]
        assert len(cells) >= 2
        assert cells[-1]["fwd"] > cells[0]["fwd"]

    def test_driftless_market_shows_nothing(self):
        pools = _market(n_tokens=8, n_hours=4800, seed=11)
        bar = Barrier(0.04, 0.02)
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=bar)
        p = G.predict(rows, "breadth", bar, 0.012)
        for c in p["test"]["cells"]:
            if c:
                assert abs(c["fwd_lift"]) < 4 * c["fwd_se"] + 0.01

    def test_render_runs(self):
        pools = _market(n_tokens=8, n_hours=1500, seed=2)
        bar = Barrier(0.04, 0.02)
        rows = G.observations(pools, candle_hours=1, lookback_hours=24,
                              horizon_hours=24, bar=bar)
        text = G.render(rows, G.persistence(rows),
                        [G.predict(rows, "breadth", bar, 0.012)], bar, 0.012, 24, 24)
        assert "persistence of breadth" in text
