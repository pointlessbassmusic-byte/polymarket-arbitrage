"""Round 3 for batch5_fx, batch5_hourly and batch5_macro (key b5, rule-5 key r5e3), on synthetic data. No archive, no
network.

Rule 5 residuals:
  * FX 'DSR > 0.95' (T-368/T-431/T-478) fails decisively below min_n on the pass statistic alone: the PSR against a zero
    Sharpe <= 0.05. The Newey-West t agreement gate is gone; the t is still reported.
  * T-428 'deflated (Sidak) one-sided p < alpha' also fails decisively below min_n when the same HAC t, tested in the
    opposite direction (H0 b <= 0), gives p < alpha (the pass's own level, 0.01), even when the slope's bootstrap CI
    straddles 0.

Rule 10: none of the nine harnesses rests on an arbitrary-phase grid. The FX books are calendar-month books (month-end
and first-of-month fixings), which the tests below pin: moving any fixing that is neither the first nor the last of its
month changes nothing."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch5_fx as fx
from mandel.experiments import batch5_hourly as bh
from mandel.experiments import batch5_macro as bm

from tests.test_mandel_batch5_fx import G10_RATES, make_market


def _decisive_only(rep, *names):
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert sorted(rep["rule5"]["decisive_failures"]) == sorted(names), rep["rule5"]["decisive_failures"]
    assert "house rule 5" in rep["reason"]


# ------------------------------------------------------------------------------- FX DSR: the PSR alone decides --

def _ar1(seed, n=120, phi=0.6, mu=-0.005, sd=0.02):
    """Positively autocorrelated monthly returns with mean ``mu``: the iid PSR is confident, the HAC t is not."""
    rng = np.random.default_rng(seed)
    e = rng.normal(0, sd, n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x - x.mean() + mu


def test_fx_psr_helper_decides_on_the_psr_alone_when_the_newey_west_t_disagrees():
    x = _ar1(0)
    psr, t, dec = fx._psr0_dec(x, x.size)
    assert psr <= 0.05 and t > -1.645                              # the old HAC gate would have kept this undecided
    assert dec is True
    assert t == pytest.approx(fx.nw_tstat(x, 6))                   # the t is still computed and returned


def test_fx_psr_helper_is_not_decisive_above_005_or_under_48_months_or_with_a_positive_mean():
    x = _ar1(0, mu=-0.001)
    psr, _, dec = fx._psr0_dec(x, x.size)
    assert psr > 0.05 and dec is False
    y = _ar1(0)
    assert fx._psr0_dec(y[:40], 40)[2] is False
    assert fx._psr0_dec(-y, y.size)[2] is False


def test_fx_psr_text_reports_the_t_as_a_value_not_a_gate():
    txt = fx._psr0_txt(0.031, -1.2)
    assert "PSR against a zero Sharpe 0.031" in txt and "Newey-West t -1.20 (reported only, not a decisive test)" in txt
    assert "-1.645" not in txt


def test_fx_momentum_null_world_seed5_now_fails_the_dsr_decisively():
    """The checker's world: PSR 0.046 <= 0.05, NW t -1.45, mean CI straddles 0. Inconclusive under the HAC gate,
    not_supported now, on the DSR criterion alone."""
    panel = fx.build_panel(*make_market(G10_RATES, noise_m=0.02, seed=5), fill_to="2026-08")
    rep = fx.momentum_report(panel, window=("2010-01", "2026-09"), n_perm=200, n_boot=500)
    assert rep["n"] == 201
    r5 = rep["rule5"]
    assert r5["psr_vs_zero_sharpe"] == pytest.approx(0.0463, abs=0.001) and r5["nw_t_vs_zero"] > -1.645
    lo, hi = rep["ci_bps"]
    assert lo < 0 < hi and hi > rep["perm_q95_bps"]
    _decisive_only(rep, "DSR > 0.95 with 16 trials")
    assert "Newey-West t -1.45 (reported only, not a decisive test)" in rep["reason"]


def test_fx_momentum_null_world_seed3_stays_undecided():
    panel = fx.build_panel(*make_market(G10_RATES, noise_m=0.02, seed=3), fill_to="2026-08")
    rep = fx.momentum_report(panel, window=("2010-01", "2026-09"), n_perm=200, n_boot=500)
    assert rep["rule5"]["psr_vs_zero_sharpe"] > 0.05
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


# ------------------------------------------------------------------ T-428: the opposite one-sided HAC p decides --

def _bdays(start, n):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _leverage_sessions(seed, sd_co, n=300, l_big=0.05, line=0.2, at=(100, 200)):
    """Sessions whose overnight return is noise except on two high-leverage days that sit on a +0.2 line: the HAC t of
    the slope is large while resamples that miss those days give a slope near 0, so the bootstrap CI straddles 0."""
    rng = np.random.default_rng(seed)
    L = rng.normal(0, 0.002, n)
    R = rng.normal(0, 0.006, n)
    y = rng.normal(0, sd_co, n)
    for j, i in enumerate(at):
        L[i] = l_big * (-1) ** j
        y[i] = line * L[i]
    o = np.full(n, 100.0)
    o3 = o * (1 + R)
    return {"days": _bdays("2024-01-02", n), "open": o, "o1530": o3, "close": o3 * (1 + L), "co_next": y,
            "excluded": {}, "hourly_first": None}


P_NAME = "deflated (Sidak, 32 cells) one-sided p < 0.01"


def test_reversal_deflated_p_fails_decisively_on_the_opposite_hac_p_when_the_slope_ci_straddles_zero():
    rep = bh.closing_reversal(_leverage_sessions(10, 0.006), n_boot=500)
    assert rep["n"] == 300
    lo, hi = rep["slope_ci95"]
    assert -0.2 > lo and hi > 0                                    # neither CI-based flag decides
    t = rep["slope_hac_t"]
    assert t > 2.326                                               # z(0.99): the pass's own level, alpha = 0.01
    p_opp = rep["rule5"]["p_opposite_hac"]
    assert p_opp == rep["p_opposite_hac"] == pytest.approx(1.0 - bh._phi(t)) and p_opp < 0.01
    _decisive_only(rep, P_NAME)                                    # inconclusive before (CI-only mirror)
    assert "opposite one-sided HAC p (H0 b <= 0, same t)" in rep["reason"]
    assert ["slope <= -0.2 (fails, not decisively, below min_n: undecided)", None] in rep["rule5"]["criteria"]


def test_reversal_opposite_hac_p_decides_at_alpha_not_at_005():
    """t between z(0.95) and z(0.99): the opposite p is under 0.05 but not under the claim's alpha 0.01, so nothing
    decides (a 1.645 cut would have)."""
    rep = bh.closing_reversal(_leverage_sessions(5, 0.008), n_boot=500)
    t = rep["slope_hac_t"]
    assert 1.645 < t < 2.326
    p_opp = rep["rule5"]["p_opposite_hac"]
    assert 0.01 < p_opp < 0.05
    assert rep["slope_ci95"][0] < 0 < rep["slope_ci95"][1]
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


def test_reversal_at_min_n_is_judged_at_face_value_without_the_opposite_p():
    rep = bh.closing_reversal(_leverage_sessions(10, 0.006), n_boot=500, min_n=300)
    assert "rule5" not in rep and "p_opposite_hac" not in rep and "opposite one-sided HAC p" not in rep["reason"]
    assert rep["verdict"] == "not_supported"


# ------------------------------------------------------------------------- rule 10: calendar-month FX books --

def _perturb_interior(spot, factor=1.07):
    """Spot rows with every fixing that is neither the first nor the last of its (currency, month) scaled by ``factor``."""
    by = {}
    for v in spot:
        by.setdefault((v["ccy"], v["day"][:7]), []).append(v["day"])
    edge = {(c, m): (min(ds), max(ds)) for (c, m), ds in by.items()}
    out = []
    for v in spot:
        a, b = edge[(v["ccy"], v["day"][:7])]
        x = v["usd_per_unit"] if v["day"] in (a, b) else v["usd_per_unit"] * factor
        out.append({**v, "usd_per_unit": x})
    return out


def test_fx_books_are_calendar_month_books_not_a_day_count_grid():
    spot, rates = make_market(G10_RATES, phi=0.5, mu_sd=0.01, seed=4)
    base = fx.build_panel(spot, rates, fill_to="2026-08")
    moved = fx.build_panel(_perturb_interior(spot), rates, fill_to="2026-08")
    cb, ad = fx.g10_costs()
    ms = fx.mrange("2005-01", "2026-08")
    c0 = fx.carry_backtest(base, fx.G10, ms, cost_bps=cb, admin=ad)
    c1 = fx.carry_backtest(moved, fx.G10, ms, cost_bps=cb, admin=ad)
    assert c0["months"] == c1["months"] == ms                     # one observation per calendar month
    np.testing.assert_array_equal(c0["net"], c1["net"])
    m0 = fx.momentum_backtest(base, fx.G10_FX, ms)
    m1 = fx.momentum_backtest(moved, fx.G10_FX, ms)
    assert m0["months"] == m1["months"] == ms
    np.testing.assert_array_equal(m0["net"], m1["net"])
    # sensitivity check: moving the month-end fixings does change the books
    last = {}
    for v in spot:
        k = (v["ccy"], v["day"][:7])
        last[k] = max(last.get(k, ""), v["day"])
    bumped = [{**v, "usd_per_unit": v["usd_per_unit"] * (1.03 if v["day"] == last[(v["ccy"], v["day"][:7])] else 1.0)}
              for v in spot]
    c2 = fx.carry_backtest(fx.build_panel(bumped, rates, fill_to="2026-08"), fx.G10, ms, cost_bps=cb, admin=ad)
    assert not np.array_equal(c0["net"], c2["net"])


def test_module_docstrings_state_the_rule10_status_per_harness():
    for mod, ids in ((fx, ("T-368", "T-431", "T-478")), (bh, ("T-427", "T-428")),
                     (bm, ("T-343", "T-224", "T-208", "T-219"))):
        doc = mod.__doc__
        assert "House rule 10" in doc
        for tid in ids:
            assert tid in doc.split("House rule 10", 1)[1], (mod.__name__, tid)
