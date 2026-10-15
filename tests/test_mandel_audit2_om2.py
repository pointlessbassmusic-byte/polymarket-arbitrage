"""Audit round 2, group om2: T-231 (term_vs_spot_premium) applies trial.min_n (70 cycles) on both sides, all on synthetic data.

Below min_n the verdict cannot be supported, and a failing criterion decides only when it fails decisively (the main premium's 95% CI
wholly at or below 0, or a conditional half significantly negative). A non-significant shortfall below min_n, or a sample under 8 cycles
where no bootstrap runs, is inconclusive. At or above min_n every failing criterion counts.

The series are built so each 63-day cycle has exactly the designed premia: VIX = 20 and VIX3M = 22.5 (ratio 1.125, so every cycle is in
the VIX3M/VIX > 1.10 conditional set), and alternating +-a returns give exact realised variances over days 1-21 and 22-63.
"""

import datetime as dt
import math
from datetime import date, timedelta

import numpy as np

from mandel.experiments import options_market as om

VIX, V3 = 20.0, 22.5
F2 = (3 * (V3 / 100) ** 2 - (VIX / 100) ** 2) / 2


def _weekdays(start, n):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _alternating(var, length):
    a = math.sqrt(var / 252)
    return [a if i % 2 == 0 else -a for i in range(length)]


def _run(d, fwd):
    """One cycle per element: d = (F^2 - RV[22..63]) - (VIX^2 - RV[1..21]) and fwd = F^2 - RV[22..63] exactly."""
    rets = []
    for dd, f in zip(d, fwd):
        rv1, rv2 = (VIX / 100) ** 2 + dd - f, F2 - f
        assert rv1 > 0 and rv2 > 0
        rets += _alternating(rv1, 21) + _alternating(rv2, 42)
    rets.append(0.0)                                             # len(r) = 63 C + 1 -> exactly C cycles
    closes = 100 * np.exp(np.concatenate([[0.0], np.cumsum(rets)]))
    days = _weekdays("2007-01-02", len(closes))
    idx = lambda v: [{"value": {"day": x, "close": v}} for x in days]
    px = [{"value": {"symbol": "SPY", "t": dt.datetime.fromisoformat(x + "T20:00:00+00:00").timestamp(), "close": float(c)}} for x, c in zip(days, closes)]
    return om.term_vs_spot_premium(idx(VIX), idx(V3), px)


def _noise(n, sd, seed):
    z = np.random.default_rng(seed).normal(0, sd, n)
    return z - z.mean()


def test_series_builder_reproduces_the_designed_premia():
    d, fwd = 0.004 + _noise(40, 0.008, 1), np.full(40, 0.006)
    rep = _run(d, fwd)
    assert rep["n_cycles"] == 40 and rep["n_conditional"] == 40
    assert abs(rep["mean_term_minus_spot_var"] - 0.004) < 1e-9
    assert all(abs(h - 0.006) < 1e-9 for h in rep["conditional_forward_premium_halves"])


def test_om2_t231_below_min_n_non_significant_positive_mean_is_inconclusive():
    """The archived case in miniature: below min_n, positive mean, p far above 0.025, halves positive -> inconclusive (was not_supported)."""
    rep = _run(0.0015 + _noise(40, 0.01, 2), np.full(40, 0.006))
    assert rep["n_cycles"] == 40 < om.T231_MIN_CYCLES
    assert rep["mean_term_minus_spot_var"] > 0 and rep["p_value"] > 0.1
    assert rep["verdict"] == "inconclusive"
    crit = dict((c.split(" (")[0], ok) for c, ok in rep["criteria"])
    assert crit["forward premium > spot premium, 95% CI excluding 0"] is None
    assert crit["conditional"] is True


def test_om2_t231_below_min_n_significantly_negative_mean_is_not_supported():
    """Below min_n but the 95% CI lies wholly below 0 (one-sided p >= 0.975): a decisive failure -> not_supported."""
    rep = _run(-0.01 + _noise(40, 0.005, 3), np.full(40, 0.006))
    assert rep["n_cycles"] < om.T231_MIN_CYCLES and rep["mean_term_minus_spot_var"] < 0 and rep["p_value"] > 0.975
    assert rep["verdict"] == "not_supported"
    assert ["forward premium > spot premium, 95% CI excluding 0", False] in rep["criteria"]


def test_om2_t231_under_8_cycles_placeholder_p_never_decides():
    """The checker's 6-cycle repro: no bootstrap runs, p is reported as None, and the verdict is inconclusive whatever the mean's sign."""
    pos = _run(0.019 + _noise(6, 0.005, 4), np.full(6, 0.006))
    neg = _run(-0.019 + _noise(6, 0.005, 5), np.full(6, 0.006))
    for rep in (pos, neg):
        assert rep["n_cycles"] == 6 and rep["p_value"] is None and rep["verdict"] == "inconclusive"
    assert "p n/a" in pos["reason"]


def test_om2_t231_below_min_n_conditional_half_decisive_only_when_significantly_negative():
    """Main premium passes; the second conditional half is negative. Significantly negative -> not_supported; barely negative -> inconclusive."""
    d = 0.01 + _noise(40, 0.005, 6)
    sig = _run(d, np.concatenate([np.full(20, 0.006), -0.01 + _noise(20, 0.004, 7)]))
    weak = _run(d, np.concatenate([np.full(20, 0.006), -0.0005 + _noise(20, 0.01, 8)]))
    for rep in (sig, weak):
        assert rep["p_value"] < 0.025 and rep["conditional_forward_premium_halves"][1] < 0
    assert sig["verdict"] == "not_supported"
    assert weak["verdict"] == "inconclusive"


def test_om2_t231_at_min_n_non_significant_mean_is_not_supported_and_clear_pass_supported():
    """At or above min_n every failing criterion counts; a clear pass is supported."""
    weak = _run(0.0015 + _noise(75, 0.01, 9), np.full(75, 0.006))
    assert weak["n_cycles"] == 75 and weak["p_value"] > 0.025 and weak["mean_term_minus_spot_var"] > 0
    assert weak["verdict"] == "not_supported"
    clear = _run(0.01 + _noise(75, 0.005, 10), np.full(75, 0.006))
    assert clear["p_value"] < 0.025 and clear["verdict"] == "supported"
    short = _run(0.01 + _noise(40, 0.005, 10), np.full(40, 0.006))
    assert short["p_value"] < 0.025 and short["verdict"] == "inconclusive"
