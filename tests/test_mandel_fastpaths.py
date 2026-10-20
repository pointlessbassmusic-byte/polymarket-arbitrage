"""The scalar Black-Scholes path and the structure harnesses' rate lookup are speed-ups only: same numbers, bit for bit."""

import math

import numpy as np
import pytest

from mandel.experiments.structures import _rate_on_or_before
from mandel.options import bs


def _array_price(S, K, T, r, sigma, kind="call", q=0.0):
    """The pre-fast-path price(): every input through numpy (0-d arrays for scalars)."""
    S, K, T = (np.asarray(a, dtype=float) for a in (S, K, T))
    d1, d2 = bs._d1d2(S, K, T, r, sigma, q)
    if kind == "call":
        val = S * np.exp(-q * T) * bs._ncdf(d1) - K * np.exp(-r * T) * bs._ncdf(d2)
        intrinsic = np.maximum(S - K, 0.0)
    else:
        val = K * np.exp(-r * T) * bs._ncdf(-d2) - S * np.exp(-q * T) * bs._ncdf(-d1)
        intrinsic = np.maximum(K - S, 0.0)
    return np.where(T <= 0, intrinsic, val)


def test_scalar_price_is_bit_identical_to_the_array_path():
    rng = np.random.default_rng(3)
    n = 20_000
    S = rng.uniform(5, 5000, n)
    K = S * rng.uniform(0.5, 1.6, n)
    T = rng.choice([0.0, -0.01, 1e-13, 1e-9, 1 / 365, 30 / 365, 0.5, 2.0], n) * rng.uniform(0.5, 1.5, n)
    r = rng.uniform(-0.01, 0.08, n)
    sig = rng.choice([0.0, 1e-13, 0.05, 0.2, 0.8, 2.5], n) * rng.uniform(0.5, 1.5, n)
    q = rng.uniform(0, 0.04, n)
    kinds = rng.choice(["call", "put"], n)
    for i in range(n):
        args = (float(S[i]), float(K[i]), float(T[i]), float(r[i]), float(sig[i]), str(kinds[i]), float(q[i]))
        assert float(bs.price(*args)) == float(_array_price(*args))


def test_array_inputs_keep_the_numpy_path_and_bad_kind_raises():
    v = bs.price(np.array([100.0, 110.0]), 100.0, 0.25, 0.03, 0.2, "call", 0.01)
    assert isinstance(v, np.ndarray) and v.shape == (2,)
    with pytest.raises(ValueError):
        bs.price(100.0, 100.0, 0.25, 0.03, 0.2, "straddle")


def test_rate_lookup_matches_the_linear_scan_and_raises_before_the_first_print():
    rates = {"2020-01-02": 1.5, "2020-01-06": 1.6, "2020-01-10": 1.7}
    days = sorted(rates)
    for d in ("2020-01-02", "2020-01-03", "2020-01-06", "2020-01-09", "2020-01-10", "2021-05-05"):
        assert _rate_on_or_before(rates, days, d) == rates.get(d, rates[max(k for k in rates if k <= d)])
    with pytest.raises(ValueError):
        _rate_on_or_before(rates, days, "2019-12-31")
