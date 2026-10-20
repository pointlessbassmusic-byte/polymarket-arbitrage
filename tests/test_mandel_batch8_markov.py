"""Batch 8 (Markov models): the HMM recovers known regimes, is point in time, and the harness pieces behave."""

import numpy as np
import pytest

from mandel.experiments import batch8_markov as B
from mandel.experiments import hmm_states as MK


def _regimes(n=6000, seed=1):
    rng = np.random.default_rng(seed)
    s = np.zeros(n, int)
    for t in range(1, n):
        s[t] = s[t - 1] if rng.random() < 0.985 else 1 - s[t - 1]
    return s, rng.normal(0.0003, np.where(s == 1, 0.02, 0.007))


def test_hmm_recovers_states_and_orders_high_variance_last():
    s, x = _regimes()
    h = MK.fit(x)
    assert h.var[1] > h.var[0]
    assert np.sqrt(h.var[0]) == pytest.approx(0.007, rel=0.1) and np.sqrt(h.var[1]) == pytest.approx(0.02, rel=0.1)
    p = MK.filter_probs(x, h)
    assert np.mean((p > 0.5) == (s == 1)) > 0.9


def test_filter_is_point_in_time():
    _, x = _regimes(3000)
    h = MK.fit(x[:2000])
    full = MK.filter_probs(x, h)
    part = MK.filter_probs(x[:1500], h)
    assert np.allclose(full[:1500], part)                   # later returns never change an earlier probability


def test_yearly_refits_use_only_prior_years():
    _, x = _regimes(3000)
    days = [f"{2000 + i // 250:04d}-{1 + (i % 250) // 21:02d}-{1 + i % 21:02d}" for i in range(3000)]
    fits = MK.yearly_refits(days, x, 2004)
    assert min(fits) == 2004 and fits[2004].n == 1000         # 4 years x 250 before 2004-01-01


def test_one_step_sigma_between_state_vols():
    _, x = _regimes()
    h = MK.fit(x)
    lo, hi = np.sqrt(h.var)
    assert lo < MK.one_step_sigma(0.0, h) < MK.one_step_sigma(1.0, h) < hi + 1e-12


def test_markov_exit_closes_at_next_open_when_state_predicts_a_rise():
    n = 200
    days = [f"2022-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    # alternating returns: after a down day the next day is up -> a short is closed after the first down close
    C = np.cumprod(np.where(np.arange(n) % 2 == 0, 1.01, 0.99)) * 100
    bars = {"days": days, "open": C.copy(), "high": C * 1.001, "low": C * 0.999, "close": C}
    t = {"entry_day": days[150], "coin": "X"}
    m = B.markov_exit_trade(bars, t, hold=14)
    assert m["why"] == "markov" and m["held_days"] <= 2 and m["chain"]


def test_state_conditioned_holds_until_enough_history():
    class Bars:
        pass
    b = Bars()
    rng = np.random.default_rng(0)
    n = 400
    b.days = [f"2003-{1 + i // 28 % 12:02d}-{1 + i % 28:02d}" if i < 336 else f"2004-{1 + (i - 336) // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    b.open = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    b.close = b.open * np.exp(rng.normal(0, 0.005, n))
    b.adj = b.close.copy()
    r = B.state_conditioned(b, start="2003-01-01", end="2004-12-31", min_state=10_000)
    assert r["held"].all() and np.allclose(r["diff"], 0)
