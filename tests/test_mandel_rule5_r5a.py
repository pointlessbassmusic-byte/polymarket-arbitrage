"""House rule 5 in batch4_fomc and batch4_vx, on synthetic data: below the trial's min_n a decisive failure (the criterion's
95% interval wholly on the wrong side of the claimed bound) is not_supported, a non-decisive failure is inconclusive, and
a pass is inconclusive. At or above min_n every criterion is judged at face value. No archive, no network."""

import numpy as np
import pytest

from mandel.experiments import batch4_fomc as fm
from mandel.experiments import batch4_vx as vx

from tests.test_mandel_batch4_fomc import _btc_setup, _closes, _days, _drift_setup, _events, _spx_setup
from tests.test_mandel_batch4_vx import _flat_index, _vx_values, _vxx

NB = 300


def _decisive(rep):
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"], rep["rule5"]
    assert "fails decisively below min_n" in rep["reason"] and "house rule 5" in rep["reason"]


def _undecided(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    assert "fails, not decisively, below min_n: undecided" in rep["reason"] and "house rule 5" in rep["reason"]


def _pass_below(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    crit = rep["rule5"].get("criteria") or rep["criteria"]                  # batch4_fomc reports them under rule5
    assert not any("below min_n" in c[0] for c in crit) and not any(c[1] is False for c in crit)


# ------------------------------------------------------------------------------------------------ T-273 GVZ --

def _gvz(before, after, seed):
    """GVZ around ~35 FOMC days (2009-10..2013, below min_n 100): ``before`` is added on the 5 closes up to the event
    (an event premium that leaves after it), ``after`` on the 4 closes after it (a rise across the event)."""
    rng = np.random.default_rng(seed)
    days = _days("2009-09-01", "2014-01-31"); ev = [d for d in _events(days, 31) if "2009-10-01" <= d <= "2013-12-31"]
    x = 20 + rng.normal(0, 0.5, len(days)); pos = {d: i for i, d in enumerate(days)}
    for e in ev:
        i = pos[e]
        x[max(0, i - 4):i + 1] += before; x[i + 1:i + 5] += after
    return {d: float(v) for d, v in zip(days, x)}, ev


def test_gvz_rule5():
    g, ev = _gvz(0.0, 1.5, 0)                                   # GVZ rises across every event: CI wholly above 0
    rep = fm.gvz_fomc_change(g, ev, end="2013-12-31", n_boot=500)
    assert rep["n"] < 100 and rep["gvz"]["ci"][0] > 0
    _decisive(rep)
    g, ev = _gvz(0.0, 0.0, 1)                                   # noise: mean > 0, CI straddles 0
    rep = fm.gvz_fomc_change(g, ev, end="2013-12-31", n_boot=500)
    assert rep["gvz"]["ci"][0] < 0 < rep["gvz"]["ci"][1]
    _undecided(rep)
    g, ev = _gvz(1.5, 0.0, 0)                                   # the claimed fall
    _pass_below(fm.gvz_fomc_change(g, ev, end="2013-12-31", n_boot=500))


def test_gvz_at_or_above_min_n_is_judged_at_face_value():
    g, ev = _gvz(0.0, 0.0, 1)                                   # the undecided noise case, with min_n lowered below n
    rep = fm.gvz_fomc_change(g, ev, end="2013-12-31", n_boot=500, min_n=10)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]
    assert rep["reason"].endswith("failed: mean GVZ change < 0 with 95% CI excluding 0")


def test_gvz_tiny_sample_never_decides():
    g, ev = _gvz(0.0, 1.5, 0)
    rep = fm.gvz_fomc_change(g, ev[:5], end="2013-12-31", n_boot=500)   # 5 events: no usable bootstrap interval
    assert rep["n"] == 5 and rep["gvz"]["ci"][0] > 0 and rep["verdict"] == "inconclusive", rep["reason"]
    empty = fm.gvz_fomc_change(g, [], end="2013-12-31", n_boot=100)
    assert empty["n"] == 0 and empty["verdict"] == "inconclusive" and " — inconclusive" in empty["reason"]


# ------------------------------------------------------------------------------------------- T-215 pre-drift --

def test_pre_drift_rule5():
    window = ("2012-01-01", "2016-12-31")                       # ~40 FOMC days, below min_n 100
    days, c, ev = _drift_setup(-0.01, seed=0)
    rep = fm.pre_fomc_drift_oos(days, c, ev, test=window, n_boot=NB, n_placebo=100)
    assert rep["n"] < 100 and rep["test"]["ci"][1] < 0
    _decisive(rep)
    days, c, ev = _drift_setup(0.0, seed=4)
    _undecided(fm.pre_fomc_drift_oos(days, c, ev, test=window, n_boot=NB, n_placebo=100))
    days, c, ev = _drift_setup(0.01, seed=0)
    _pass_below(fm.pre_fomc_drift_oos(days, c, ev, test=window, n_boot=NB, n_placebo=100))


# ----------------------------------------------------------------------------------- T-214 / T-221 straddles --

def test_spx_straddle_rule5():
    days, c, vix, ev = _spx_setup(0.002)                        # calm FOMC days: short straddle earns MORE on them
    rep = fm.spx_event_straddle(days, c, vix, ev[:50], n_boot=200)
    assert rep["n"] == 50 and rep["halves"]["1994-2010"]["ci"][0] > 0 and rep["halves"]["2011-2026"]["diff"] is None
    _decisive(rep)
    days, c, vix, ev = _spx_setup(0.01, seed=1)
    _undecided(fm.spx_event_straddle(days, c, vix, ev[:50], n_boot=200))
    days, c, vix, ev = _spx_setup(0.03)
    _pass_below(fm.spx_event_straddle(days, c, vix, ev[:50], n_boot=200))


def test_btc_straddle_rule5():
    days, c, dvol, ev = _btc_setup(0.005)
    rep = fm.btc_event_straddle(days, c, dvol, ev, n_boot=200, min_n=100)
    assert rep["n"] < 100 and rep["full"]["ci"][0] > 0
    _decisive(rep)
    days, c, dvol, ev = _btc_setup(0.03, seed=3)
    _undecided(fm.btc_event_straddle(days, c, dvol, ev, n_boot=200, min_n=100))
    days, c, dvol, ev = _btc_setup(0.09)
    _pass_below(fm.btc_event_straddle(days, c, dvol, ev, n_boot=200, min_n=100))


# --------------------------------------------------------------------------------------- T-341 statement day --

def test_statement_day_rule5():
    def run(mu, seed):
        days, c, ev = _drift_setup(mu, seed=seed, start="2010-01-04")   # ~137 statement days, below min_n 200
        return fm.statement_day_effect(days, c, ev, start="2010-01-01", n_boot=NB)
    rep = run(-0.01, 0)
    assert rep["n"] < 200 and rep["sub_ci_bps"][1] < 0
    _decisive(rep)
    assert "2016-2026 net difference > 0" in rep["rule5"]["decisive_failures"]
    rep = run(0.0012, 1)                                         # +12 bps: short of 15 bps, CI reaching above it
    assert rep["net"]["ci"][0] < 0.0015 < rep["net"]["ci"][1]
    _undecided(rep)
    _pass_below(run(0.008, 3))


# ---------------------------------------------------------------------------------------- T-342 cycle weeks --

def _weeks(eff, seed):
    rng = np.random.default_rng(seed)
    days = _days("2018-01-02", "2022-12-30"); ev = _events(days, 33)        # ~1,285 cycle days, below min_n 1500
    w = fm.fomc_cycle_weeks(days, ev)[1:]
    r = rng.normal(0.0003, 0.01, len(days) - 1) + np.isin(w, fm.EVEN_WEEKS) * eff
    return fm.even_week_effect(days, _closes(r), ev, n_boot=NB, n_placebo=200)


def test_even_weeks_rule5():
    rep = _weeks(-0.003, 8)
    assert rep["n"] < 1500
    _decisive(rep)
    rep = _weeks(0.0004, 8)                                      # +4.5 bps/day, CI straddling 5 bps; placebo p > 0.05
    assert rep["placebo_p"] >= 0.05
    _undecided(rep)
    crit = dict((c.split(" (")[0], ok) for c, ok in rep["rule5"]["criteria"])
    assert crit["random-offset placebo p < 0.05"] is None                   # no interval: never decisive below min_n
    _pass_below(_weeks(0.003, 8))


# -------------------------------------------------------------------------------------- T-361 monetary momentum --

def _mm(drift, seed, base):
    """2 of every 5 meetings are surprises (about 107 enter the gap, below min_n 120)."""
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 32); pos = {d: i for i, d in enumerate(days)}
    lab = np.resize(np.array([-1, 0, 1, 0, 0]), len(ev)); level = 5.0; dgs2 = {}; m = dict(zip(ev, lab))
    for d in days:
        level += m.get(d, 0) * 0.10 + rng.normal(0, 0.005); dgs2[d] = level
    r = rng.normal(base, 0.01, len(days) - 1)
    for e, s in zip(ev, lab):
        i = pos[e] + 2
        if s != 0 and i + 15 < len(days):
            r[i:i + 15] += -s * drift
    return fm.monetary_momentum(days, _closes(r), dgs2, ev, n_perm=1000, n_boot=NB)


def test_monetary_momentum_rule5():
    rep = _mm(-0.003, 0, 0.0002)                                  # the gap reversed: every CI on the wrong side
    assert rep["n"] < 120 and rep["gap_ci_net_pp"][1] < 1
    _decisive(rep)
    assert rep["criteria_verdict_if_min_n_ignored"] == "not_supported"
    assert rep["reason"].startswith(f"only {rep['n']} expansionary+contractionary meetings (min_n 120)")
    rep = _mm(0.0, 1, 0.0)                                         # no effect: gap CI straddles 1 pp, Sharpe CI straddles 0
    assert rep["gap_ci_net_pp"][0] < 1 < rep["gap_ci_net_pp"][1] and rep["sharpe_diff_upper_95"] > 0
    _undecided(rep)
    rep = _mm(0.002, 14, 0.0002)
    assert rep["criteria_verdict_if_min_n_ignored"] == "supported"
    _pass_below(rep)


# ------------------------------------------------------------------------------------------- T-160 VX calendar --

def test_vx_calendar_rule5():
    def run(**kw):
        days, vals = _vx_values(400, **kw)                        # ~398 daily intervals, below min_n 2500
        return vx.vx_calendar(vx.vx_curve(vals), _flat_index(days, 15.0), _flat_index(days, 16.5), n_boot=400)
    rep = run(c=-1.0, noise=0.05, seed=3)                          # inverted curve: short M1 / long M2 loses every roll-down
    assert rep["n"] < 2500 and rep["ci95"][1] < 0
    _decisive(rep)
    rep = run(c=0.0, noise=0.0, rw=0.3, seed=5)                    # random walks: every CI straddles 0
    assert rep["ci95"][0] < 0 < rep["ci95"][1]
    _undecided(rep)
    rep = run(c=1.0, noise=0.05, seed=3)
    _pass_below(rep)
    assert "not implemented: n >= 2500" in rep["reason"]


def test_vx_calendar_at_or_above_min_n_is_judged_at_face_value():
    days, vals = _vx_values(400, c=0.0, noise=0.0, rw=0.3, seed=5)  # the undecided case, min_n lowered below n
    rep = vx.vx_calendar(vx.vx_curve(vals), _flat_index(days, 15.0), _flat_index(days, 16.5), n_boot=400, min_n=100)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]
    assert rep["criteria"][0] == ("n >= 100 daily observations (min_n)", True)


# ---------------------------------------------------------------------------------------------- T-242 VXX decay --

def test_vxx_decay_rule5():
    def run(mu, seed, **kw):
        d, c = _vxx(700, mu, seed=seed)                            # ~33 cycles, below min_n 80
        return vx.vxx_decay(d, c, _flat_index(d, 15.0), _flat_index(d, 18.0), n_boot=400, n_place=50, **kw)
    rep = run(0.004, 2)                                            # VXX rising: CI wholly above -3%
    assert rep["n"] < 80 and rep["ci95"][0] > -0.03
    _decisive(rep)
    rep = run(-0.0015, 4)                                          # about -3%: upper bound above -3%, CI reaching below it
    assert rep["ub95"] > -0.03 and rep["ci95"][0] < -0.03
    _undecided(rep)
    _pass_below(run(-0.004, 2))
    at = run(-0.0015, 4, min_n=20)                                 # the same undecided sample with min_n below n
    assert at["verdict"] == "not_supported" and "rule5" not in at and "house rule 5" not in at["reason"]


def test_vx_under_8_observations_stays_inconclusive():
    d, c = _vxx(120, 0.004, seed=2)
    rep = vx.vxx_decay(d, c, _flat_index(d, 15.0), _flat_index(d, 18.0), n_boot=100, n_place=10)
    assert rep["n"] < 8 and rep["verdict"] == "inconclusive"


@pytest.mark.parametrize("ok,dec,expect", [(True, False, True), (False, True, False), (False, False, None), (None, True, None)])
def test_rule5_row_mapping(ok, dec, expect):
    v, why, crit = fm._rule5([("c", ok, dec)], 5, 10, "events")
    assert crit[0][1] is expect and crit[-1] == ("n >= trial min_n (5 of 10 events)", None)
    assert v == ("not_supported" if expect is False else "inconclusive") and why.startswith(v)
    rows = vx._rule5_criteria("n >= 10 (min_n)", [("c", ok, dec)], 5, 10)
    assert rows[0] == ("n >= 10 (min_n)", None) and rows[1][1] is expect
    assert vx._rule5_criteria("n >= 10 (min_n)", [("c", ok, dec)], 10, 10) == [("n >= 10 (min_n)", True), ("c", ok)]
