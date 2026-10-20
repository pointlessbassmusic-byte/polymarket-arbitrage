"""Audit round 2, group xa2 (mandel/experiments/cross_asset.py): regression tests on synthetic data, one block per item."""

import math
from datetime import date, timedelta

import numpy as np

from mandel.experiments import cross_asset as xa
from mandel.options import bs


def _days(n, start=date(2015, 1, 1)):
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _common_factor_data(n=3000, seed=1, regime=480, dip=0.8):
    """Trend regimes (|drift| 0.15%/day vs 0.6%/day, `regime` days each) set every straddle's payoff, conditional or not; the index sits
    at 50 except a dip to 50*dip at positions 70..84 of every 120 days, so low-index straddles are cheaper and beat the all-days mean
    by a steady margin. The regime swings dominate each mean on its own but cancel in the paired difference."""
    rng = np.random.default_rng(seed); days = _days(n); t = np.arange(n)
    g = np.where((t // regime) % 2 == 1, 0.006, 0.0015) * np.where((t // (2 * regime)) % 2 == 1, 1, -1)
    closes = 100 * np.exp(np.cumsum(g + rng.normal(0, 0.001, n)))
    p = t % 120
    iv = np.where((p >= 70) & (p < 85), 50 * dip, 50.0)
    return days, closes, {d: float(v) for d, v in zip(days, iv)}, {d: 2.0 for d in days}


def _returns(days, closes, idx, dte, hold, window, pct):
    """Independent re-pricing of every daily straddle return (flat 2% bill, as _common_factor_data supplies)."""
    iv = np.array([idx[d] for d in days]); T = dte / 365.0; r = math.log(1.02); x = []
    for i in range(window, len(closes) - hold):
        S, V = closes[i], iv[i] / 100
        prem = float(bs.price(S, S, T, r, V, "call")) + float(bs.price(S, S, T, r, V, "put"))
        x.append((abs(closes[i + hold] - S) - prem) / prem)
    return np.array(x)


# ---------------------------------------------- xa2 (XA-3 follow-up): paired block bootstrap of the difference (T-256, T-272) --

def test_xa2_conditional_straddle_ci_is_a_paired_bootstrap_of_the_difference():
    days, closes, idx, rates = _common_factor_data()
    hold, window = 60, 252
    rep = xa.conditional_straddle(days, closes, idx, rates, 60, hold, days[0], window, 0.20, "X", min_n=1)
    x = _returns(days, closes, idx, 60, hold, window, 0.20)
    pos = [days.index(d) - window for d in rep["entry_days"]]
    assert len(x) == rep["n_days"] and len(pos) == rep["n_entries"] >= 20
    assert np.isclose(rep["mean_all"], x.mean()) and np.isclose(rep["mean_low"], x[pos].mean())
    flag = np.zeros(len(x), bool); flag[pos] = True
    z = np.where(flag, x, 0.0) / flag.mean() - x
    assert np.isclose(z.mean(), rep["diff"])                                       # the paired series' mean is exactly the statistic
    paired = np.quantile(xa._block_mean_draws(z, 2 * hold, seed=0), [0.025, 0.975])  # default block = 2 -> 2*hold daily rows
    assert np.allclose(rep["ci"], paired)
    # was: independent bootstraps of the conditional entries (block 2) and of the daily series (block = hold), differenced. That drops
    # the positive covariance of the two means, so the common regime swings widen the interval past 0 and the planted edge read as
    # a decisive not_supported.
    old = np.quantile(xa._block_mean_draws(x[pos], 2, seed=0) - xa._block_mean_draws(x, hold, seed=1), [0.025, 0.975])
    assert old[0] < 0 < rep["ci"][0] and rep["ci"][1] - rep["ci"][0] < 0.5 * (old[1] - old[0])
    assert rep["verdict"] == "supported" and rep["conditional_mean_positive"]
    # the min_n cap is unchanged: below T-256's 25 entries the same evidence stays inconclusive
    dvol = xa.conditional_straddle(days, closes, idx, rates, 60, hold, days[0], window, 0.20, "DVOL")
    assert dvol["min_n"] == 25 and dvol["n_entries"] < 25 and dvol["verdict"] == "inconclusive" and np.allclose(dvol["ci"], rep["ci"])


def test_xa2_paired_ci_still_fails_a_null_edge():
    """No dip at all in the information (the low days are as rich as the rest): the paired CI must straddle 0, not manufacture support."""
    days, closes, idx, rates = _common_factor_data(dip=1.0)
    flat = {d: (49.9 if (i % 120) in range(70, 85) else 50.0) for i, d in enumerate(days)}   # a 0.2% dip: flagged, but no real edge
    rep = xa.conditional_straddle(days, closes, flat, rates, 60, 60, days[0], 252, 0.20, "X", min_n=1)
    assert rep["n_entries"] >= 20 and rep["ci"][0] < 0 and rep["verdict"] == "not_supported"
