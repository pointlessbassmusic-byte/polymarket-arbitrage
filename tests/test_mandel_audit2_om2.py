"""Audit round 2, group om2: T-231 (term_vs_spot_premium) applies trial.min_n (70 cycles) on both sides, all on synthetic data.

Below min_n the verdict cannot be supported, and a failing criterion decides only when it fails decisively (the main premium's 95% CI
wholly at or below 0, or a conditional half significantly negative). A non-significant shortfall below min_n, or a sample under 8 cycles
where no bootstrap runs, is inconclusive. At or above min_n every failing criterion counts.

Rule 10 rewrite: these tests used to build each 63-day cycle of the grid that starts on the first day (realised variance set separately
on its days 1-21 and 22-63), so the designed premia existed on that one grid start only, which rule 10 forbids the harness to rely on.
The series are now phase-free: |returns| are constant, so realised variance is exactly ``var`` over any window, and each daily entry t
gets its own VIX and VIX3M, which set its premium F^2 - VIX^2 and its forward premium F^2 - var exactly. Every start of the 63-day grid
sees the same design, and C cycles are 63 C daily entries.
"""

import datetime as dt
from datetime import date, timedelta

import numpy as np

from mandel.experiments import options_market as om

M = 63                                                           # daily entries per non-overlapping 63-day cycle


def _weekdays(start, n):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _world(vix2, f2, var):
    """Entry t has VIX^2 = vix2[t] and forward variance F^2 = f2[t] (VIX3M^2 = (2 F^2 + VIX^2) / 3); alternating +-sqrt(var/252)
    returns make realised variance exactly ``var`` over any window. Hence, on every daily entry: premium d = (F^2 - RV[22..63]) -
    (VIX^2 - RV[1..21]) = f2 - vix2, forward premium f2 - var, and VIX3M/VIX > 1.10 exactly when f2 > 1.315 vix2."""
    vix2, f2 = np.asarray(vix2, float), np.asarray(f2, float)
    assert (vix2 > 0).all() and (f2 > 0).all()
    m = vix2.size; n = m + 64                                    # len(r) = m + 63 -> exactly m daily entries
    days = _weekdays("2007-01-02", n)
    a = np.sqrt(var / 252)
    closes = 100 * np.exp(np.concatenate([[0.0], np.cumsum(np.where(np.arange(n - 1) % 2 == 0, a, -a))]))
    pad = np.full(64, 20.0)
    idx = lambda v: [{"value": {"day": x, "close": float(c)}} for x, c in zip(days, np.concatenate([v, pad]))]
    px = [{"value": {"symbol": "SPY", "t": dt.datetime.fromisoformat(x + "T20:00:00+00:00").timestamp(), "close": float(c)}}
          for x, c in zip(days, closes)]
    return om.term_vs_spot_premium(idx(100 * np.sqrt(vix2)), idx(100 * np.sqrt((2 * f2 + vix2) / 3)), px)


def _vix20(d):
    """VIX 20 and premium exactly d[t] on every entry (realised 15 vol). Entries with d > 0.0126 have VIX3M/VIX > 1.10, and their
    forward premium 0.0175 + d is positive; entries with d < 0 are never conditional."""
    d = np.asarray(d, float)
    return _world(np.full(d.size, 0.04), 0.04 + d, 0.0225)


def _noise(n, sd, seed):
    z = np.random.default_rng(seed).normal(0, sd, n)
    return z - z.mean()


def _crit(rep):
    return dict((c.split(" (")[0], ok) for c, ok in rep["criteria"])


MAIN = "forward premium > spot premium, 95% CI excluding 0"


def test_series_builder_reproduces_the_designed_premia_on_every_grid_start():
    """Premium 0.004 (+ noise) and forward premium 0.006 on every entry, all of them conditional (VIX3M/VIX = 1.20): the pooled mean and
    both conditional halves are exact, and every one of the 63 grid starts sees the design (the old builder's day-0 grid alone did)."""
    d = 0.004 + _noise(40 * M, 0.0003, 1)
    f2 = np.full(d.size, 0.006 + 0.004)                          # F^2 = forward premium + var
    rep = _world(f2 - d, f2, 0.004)
    assert rep["n_cycles"] == 40 and rep["n_entries"] == 40 * M
    assert rep["n_conditional"] == 40 and rep["n_conditional_entries"] == 40 * M
    assert abs(rep["mean_term_minus_spot_var"] - 0.004) < 1e-9
    assert all(abs(h - 0.006) < 1e-9 for h in rep["conditional_forward_premium_halves"])
    gs = rep["grid_starts"]
    assert gs["starts"] == 63 and gs["passing"] == 63 and 0.0037 < gs["range"][0] <= gs["range"][1] < 0.0043


def test_om2_t231_below_min_n_non_significant_positive_mean_is_inconclusive():
    """The archived case in miniature: below min_n, positive mean, p far above 0.025, halves positive -> inconclusive (was not_supported)."""
    rep = _vix20(0.00005 + _noise(40 * M, 0.005, 2))
    assert rep["n_cycles"] == 40 < om.T231_MIN_CYCLES
    assert rep["mean_term_minus_spot_var"] > 0 and rep["p_value"] > 0.1
    assert rep["n_conditional_entries"] > 0 and all(h > 0 for h in rep["conditional_forward_premium_halves"])
    assert rep["verdict"] == "inconclusive"
    crit = _crit(rep)
    assert crit[MAIN] is None
    assert crit["conditional"] is True


def test_om2_t231_below_min_n_significantly_negative_mean_is_not_supported():
    """Below min_n but the 95% CI lies wholly below 0 (one-sided p >= 0.975): a decisive failure -> not_supported. No entry is conditional
    here (the halves criterion is undecided), so the main criterion alone decides."""
    rep = _vix20(-0.01 + _noise(40 * M, 0.005, 3))
    assert rep["n_cycles"] < om.T231_MIN_CYCLES and rep["mean_term_minus_spot_var"] < 0 and rep["p_value"] > 0.975
    assert rep["verdict"] == "not_supported"
    assert [MAIN, False] in rep["criteria"] and _crit(rep)["conditional"] is None


def test_om2_t231_under_8_cycles_placeholder_p_never_decides():
    """The checker's 6-cycle repro: no bootstrap runs, p is reported as None, and the verdict is inconclusive whatever the mean's sign."""
    pos = _vix20(0.019 + _noise(6 * M, 0.005, 4))
    neg = _vix20(-0.019 + _noise(6 * M, 0.005, 5))
    for rep in (pos, neg):
        assert rep["n_cycles"] == 6 and rep["p_value"] is None and rep["verdict"] == "inconclusive"
    assert pos["mean_term_minus_spot_var"] > 0 > neg["mean_term_minus_spot_var"]
    assert "p n/a" in pos["reason"]


def test_om2_t231_below_min_n_conditional_half_decisive_only_when_significantly_negative():
    """Main premium passes; the second conditional half is negative. Significantly negative -> not_supported; barely negative ->
    inconclusive. VIX^2 = F^2 / 2 (+ noise) keeps every entry conditional (VIX3M/VIX ~ 1.29), so the halves are the first and second
    halves of the timeline: forward premium 0.006 exactly, then -0.01 (+ noise) or -0.0001 (+ noise)."""
    m = 40 * M; h = m // 2
    reps = []
    for late in (-0.01 + _noise(m - h, 0.004, 7), -0.0001 + _noise(m - h, 0.005, 8)):
        f2 = 0.06 + np.concatenate([np.full(h, 0.006), late])
        reps.append(_world(f2 / 2 + _noise(m, 0.002, 6), f2, 0.06))
    for rep in reps:
        assert rep["n_cycles"] < om.T231_MIN_CYCLES and rep["n_conditional_entries"] == m
        assert rep["p_value"] < 0.025 and rep["conditional_forward_premium_halves"][1] < 0 < rep["conditional_forward_premium_halves"][0]
    sig, weak = reps
    assert sig["verdict"] == "not_supported" and _crit(sig)["conditional"] is False
    assert weak["verdict"] == "inconclusive" and _crit(weak)["conditional"] is None


def test_om2_t231_at_min_n_non_significant_mean_is_not_supported_and_clear_pass_inconclusive():
    """At or above min_n every failing criterion counts; a clear pass stays inconclusive while the strategy clause is
    unimplemented (this test used to expect supported, which encoded that defect)."""
    weak = _vix20(0.00005 + _noise(75 * M, 0.005, 9))
    assert weak["n_cycles"] == 75 and weak["p_value"] > 0.025 and weak["mean_term_minus_spot_var"] > 0
    assert weak["verdict"] == "not_supported" and [MAIN, False] in weak["criteria"]
    clear = _vix20(0.01 + _noise(75 * M, 0.005, 10))
    assert clear["n_cycles"] == 75 and clear["p_value"] < 0.025 and clear["verdict"] == "inconclusive"
    short = _vix20(0.01 + _noise(40 * M, 0.005, 10))
    assert short["n_cycles"] == 40 and short["p_value"] < 0.025 and short["verdict"] == "inconclusive"
