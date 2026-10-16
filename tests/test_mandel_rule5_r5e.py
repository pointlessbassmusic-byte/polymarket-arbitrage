"""House rule 5 in batch5_macro, batch5_fx and batch5_hourly, on synthetic data: below the trial's min_n a decisive failure
(the criterion's 95% interval wholly on the wrong side of the claimed bound) is not_supported, a non-decisive failure is
inconclusive, and a pass is inconclusive. At or above min_n every criterion is judged at face value. No archive, no
network."""

import numpy as np
import pytest

from mandel.experiments import batch5_fx as fx
from mandel.experiments import batch5_hourly as bh
from mandel.experiments import batch5_macro as bm

from tests.test_mandel_batch5_fx import G10_RATES, make_market
from tests.test_mandel_batch5_hourly import _ldec, sessions
from tests.test_mandel_batch5_macro import _closes, _days, _gld_world, _imhm_world, _release_world, _witching_world


def _decisive(rep, *names):
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"], rep["rule5"]
    for name in names:
        assert name in rep["rule5"]["decisive_failures"], rep["rule5"]["decisive_failures"]
    assert "fails decisively below min_n" in rep["reason"] and "house rule 5" in rep["reason"]


def _undecided(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    assert any(ok is False for _, ok in rep["rule5"]["criteria_at_face_value"])          # fails at face value
    assert "fails, not decisively, below min_n: undecided" in rep["reason"] and "house rule 5" in rep["reason"]


def _pass_below(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    crit = rep["rule5"]["criteria"]
    assert not any("below min_n" in c for c, _ in crit) and not any(ok is False for _, ok in crit)
    assert any("min_n" in c or "days (only" in c for c, ok in crit if ok is None)          # the unmet min_n criterion


# ------------------------------------------------------------------------------------------------ helpers --

def test_interval_helpers_ignore_missing_and_zero_width_intervals():
    assert bm._ci_below([-2.0, -1.0], 0.0) and not bm._ci_below([-2.0, 0.5], 0.0) and not bm._ci_below([None, None], 0.0)
    assert not bm._ci_below([-1.0, -1.0], 0.0) and not bm._ci_above([1.0, 1.0], 0.0)      # zero width decides nothing
    assert fx._ci_below(-0.5, 0.2, 0.3) and not fx._ci_below(-0.5, 0.4, 0.3) and not fx._ci_below(0.1, 0.1, 0.3)
    assert bh._ci_above((-0.1, 0.3), -0.2, strict=True) and not bh._ci_above((-0.2, 0.3), -0.2, strict=True)
    lo, hi = bm.spearman_ci(0.0, 103)
    assert lo == pytest.approx(-hi) and hi == pytest.approx(np.tanh(1.959964 / 10), rel=1e-9)
    assert bm.spearman_ci(None, 50) == [None, None] and bm.spearman_ci(0.5, 3) == [None, None]


def test_rule5_judges_each_criterion():
    v, why, r5 = bm._rule5([("a", True), ("b", False), ("c", False), ("d", None)], [False, True, False, False], 10, 100, "days")
    assert v == "not_supported" and r5["decisive_failures"] == ["b"]
    assert r5["criteria"] == [["a", True], ["b (fails decisively below min_n)", False],
                              ["c (fails, not decisively, below min_n: undecided)", None], ["d", None],
                              ["n >= trial min_n (10 days, need 100)", None]]
    v, why, r5 = bm._rule5([("a", True), ("c", False)], [False, False], 10, 100, "days")
    assert v == "inconclusive" and "Decisive failures: none" in why and "criteria at face value: not_supported" in why
    v, why, r5 = bm._rule5([("a", True)], [False], 10, 100, "days")
    assert v == "inconclusive" and "not implemented: n >= trial min_n (10 days, need 100)" in why


# ------------------------------------------------------------------------------ T-343 announcement premium --
# start 2008: about 590 release days, below min_n 600, with both halves present

def _premium(plant):
    days, c, cpi, es, fomc = _release_world(0, plant)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, start="2008-01-01", n_boot=200)
    assert rep["n"] < 600
    return rep


def test_announcement_premium_decisive_failure_below_min_n():
    rep = _premium(-60.0)                                           # release days lose 60 bps: every CI wholly below
    _decisive(rep, "net difference > 5 bps/day", "studentized block-bootstrap p < 0.05", "2010-2026 net difference > 0")
    assert rep["net"]["ci"][1] < 0


def test_announcement_premium_non_decisive_failure_below_min_n():
    rep = _premium(3.0)                                             # a small edge under the 5 bps bar, CIs straddle it
    _undecided(rep)
    assert rep["net"]["ci"][0] < 0 < 5e-4 < rep["net"]["ci"][1]


def test_announcement_premium_pass_below_min_n():
    _pass_below(_premium(40.0))


# ---------------------------------------------------------------------------------------- T-208 IM/HM filter --
# end 2016: about 180 FOMC events with IM and HM, below min_n 200; OOS 2010-2016

def _imhm_vix_scaled(seed, mult):
    """Event moves of ``mult`` x the VIX-implied daily sd: a high VIX (high IM/HM) underprices the straddle, so the long
    P&L rises with IM/HM (the claim reversed)."""
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-06-30")
    vixv = rng.uniform(10, 40, len(days))
    r = rng.normal(0, 0.01, len(days) - 1)
    ev_idx = list(range(20, len(days), 32))
    for i in ev_idx:
        r[i - 1] = rng.choice([-1, 1]) * mult * vixv[i - 1] / 100 / np.sqrt(252)
    return days, _closes(r), dict(zip(days, vixv)), [days[i] for i in ev_idx]


def _imhm(world):
    days, c, vix, ev = world
    rep = bm.im_hm_filter(days, c, vix, ev, end="2016-12-31", n_perm=1000, n_boot=500, n_placebo=0)
    assert rep["n"] < 200
    return rep


def test_im_hm_filter_decisive_failure_below_min_n():
    rep = _imhm(_imhm_vix_scaled(0, 3.0))
    _decisive(rep, "OOS Spearman rho < -0.1", "OOS one-sided permutation p < 0.05", "OOS Q1-Q5 95% CI excludes 0")
    assert rep["oos_spearman_rho_ci"][0] > 0.5


def test_im_hm_filter_non_decisive_failure_below_min_n():
    rep = _imhm(_imhm_world(0, False))                              # VIX is the true event vol: rho ~ 0
    _undecided(rep)
    lo, hi = rep["oos_spearman_rho_ci"]
    assert lo < -0.1 < hi


def test_im_hm_filter_pass_below_min_n():
    _pass_below(_imhm(_imhm_world(0, True)))


# --------------------------------------------------------------------------------- T-224 GLD event straddle --
# end 2014: about 100 FOMC/CPI days, below min_n 150

def _gld(mult, **kw):
    days, c, gvz, fomc, cpi = _gld_world(0, mult)
    return bm.gld_event_straddle(days, c, gvz, fomc, cpi, end="2014-12-31", n_boot=300, **kw)


def test_gld_event_straddle_decisive_failure_below_min_n():
    rep = _gld(0.2)                                                 # calm event days: the short straddle earns more there
    _decisive(rep, "event-minus-non-event short-straddle P&L < 0", "95% CI excludes 0 (upper bound < 0)")
    assert rep["n"] < 150 and rep["full"]["ci"][0] > 0


def test_gld_event_straddle_non_decisive_failure_below_min_n():
    rep = _gld(1.0)
    _undecided(rep)
    assert rep["full"]["ci"][0] < 0 < rep["full"]["ci"][1]


def test_gld_event_straddle_pass_below_min_n():
    _pass_below(_gld(2.5))


def test_gld_same_non_decisive_failure_at_min_n_is_judged_at_face_value():
    rep = _gld(1.0, min_n=50)
    assert rep["n"] >= 50 and rep["verdict"] == "not_supported" and "rule5" not in rep
    assert "house rule 5" not in rep["reason"] and rep["reason"].endswith("failed: event-minus-non-event short-straddle P&L < 0; "
                                                                           "95% CI excludes 0 (upper bound < 0)")


# ------------------------------------------------------------------------------------ T-219 triple witching --
# from 2005: about 87 witching Fridays, below min_n 100

def _witching(plant):
    days, c, vix = _witching_world(0, plant)
    rep = bm.witching_straddle(days, c, vix, start="2005-01-01", n_boot=300, n_perm=1000)
    assert rep["n"] < 100
    return rep


def test_witching_straddle_decisive_failure_below_min_n():
    rep = _witching(0.01)                                           # witching Fridays barely move: the long straddle loses
    _decisive(rep, "witching-minus-other mean long P&L > 0", "95% CI excludes 0 (lower bound > 0)", "permutation p < 0.05")


def test_witching_straddle_non_decisive_failure_below_min_n():
    rep = _witching(0.0)
    _undecided(rep)
    assert rep["full"]["ci"][0] < 0 < rep["full"]["ci"][1]


def test_witching_straddle_pass_below_min_n():
    _pass_below(_witching(2.5))


# ------------------------------------------------------------------------------------------- T-368 FX carry --
# test window 2013-01..2019-12: 84 months, below min_n 150 and above the 48-month floor

@pytest.fixture(scope="module")
def carry_panels():
    anti_spot, _ = make_market({c: 4 * r for c, r in G10_RATES.items()}, uip=True, seed=1)   # high yielders fall 4x their carry
    return {"planted": fx.build_panel(*make_market(G10_RATES, seed=1), fill_to="2026-08"),
            "uip": fx.build_panel(*make_market(G10_RATES, uip=True, seed=3), fill_to="2026-08"),
            "anti": fx.build_panel(anti_spot, make_market(G10_RATES, seed=1)[1], fill_to="2026-08")}


def _carry(panel, test=("2013-01", "2019-12")):
    cb, ad = fx.g10_costs()
    return fx.carry_report(panel, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", test=test, n_boot=1000)


def test_carry_decisive_failure_below_min_n(carry_panels):
    rep = _carry(carry_panels["anti"])
    _decisive(rep, "test-window net Sharpe > 0.3", "stationary-bootstrap lower bound > 0", "DSR > 0.95 with n_trials = 6")
    assert rep["n"] == 84 and rep["boot_hi"] < 0 and rep["criteria"] == rep["rule5"]["criteria"]


def test_carry_non_decisive_failure_below_min_n(carry_panels):
    rep = _carry(carry_panels["uip"])                               # UIP holds: net Sharpe slightly below 0, wide interval
    _undecided(rep)
    assert rep["boot_lo"] < 0 < 0.3 < rep["boot_hi"]


def test_carry_pass_below_min_n(carry_panels):
    rep = _carry(carry_panels["planted"])
    _pass_below(rep)
    assert "need 150" in rep["reason"]


def test_carry_under_four_bootstrap_blocks_is_inconclusive_without_statistics(carry_panels):
    rep = _carry(carry_panels["anti"], test=("2023-01", "2026-09"))
    assert rep["n"] < 48 and rep["verdict"] == "inconclusive" and "sharpe" not in rep and "rule5" not in rep
    assert "no decisive failure below min_n (house rule 5)" in rep["reason"] and "need 150" in rep["reason"]


def test_carry_at_min_n_is_judged_at_face_value(carry_panels):
    rep = _carry(carry_panels["uip"], test=("2013-01", "2026-09"))
    assert rep["n"] == 165 and rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]


# -------------------------------------------------------------------------------------- T-478 FX momentum --
# window 2010-01..2026-09: 201 months, below min_n 300

@pytest.fixture(scope="module")
def mom_panels():
    return {"planted": fx.build_panel(*make_market(G10_RATES, phi=0.9, mu_sd=0.015, noise_m=0.015, seed=3), fill_to="2026-08"),
            # seed 3 (PSR vs 0 0.18): seed 5 has PSR 0.046 <= 0.05, which now decides the DSR criterion (r5e3)
            "null": fx.build_panel(*make_market(G10_RATES, noise_m=0.02, seed=3), fill_to="2026-08"),
            "anti": fx.build_panel(*make_market(G10_RATES, phi=-0.9, mu_sd=0.015, noise_m=0.015, seed=3), fill_to="2026-08")}


def _mom(panel):
    rep = fx.momentum_report(panel, window=("2010-01", "2026-09"), n_perm=200, n_boot=500)
    assert rep["n"] == 201
    return rep


def test_momentum_decisive_failure_below_min_n(mom_panels):
    rep = _mom(mom_panels["anti"])                                  # monthly drifts reverse: momentum loses
    _decisive(rep, "mean net monthly excess return > 0 with block-bootstrap 95% CI excluding 0",
              "DSR > 0.95 with 16 trials", "mean above the permutation 95th percentile")
    assert rep["ci_bps"][1] < 0


def test_momentum_non_decisive_failure_below_min_n(mom_panels):
    rep = _mom(mom_panels["null"])
    _undecided(rep)
    assert rep["ci_bps"][0] < 0 < rep["ci_bps"][1] and rep["ci_bps"][1] > rep["perm_q95_bps"]


def test_momentum_pass_below_min_n(mom_panels):
    rep = _mom(mom_panels["planted"])
    _pass_below(rep)
    assert "need 300" in rep["reason"]


# ----------------------------------------------------------------------------------- T-427 hourly momentum --
# 300 sessions, below min_n 500 (the window is also short of the claimed 2023-11..2026-10)

def _intraday(mom):
    spy, _ = sessions(n=300, seed=1, mom=mom)
    qqq, _ = sessions(n=300, seed=2, mom=mom)
    iwm, _ = sessions(n=300, seed=3, mom=mom)
    rep = bh.intraday_momentum(spy, {"QQQ": qqq, "IWM": iwm}, n_boot=300)
    assert rep["n"] == 300
    return rep


def test_intraday_momentum_decisive_failure_below_min_n():
    rep = _intraday(-0.0015)                                        # the last half hour reverses the morning
    _decisive(rep, "SPY mean net return > 0", "deflated p < 0.05 over 60 cells",
              "same sign on QQQ and IWM (mean net return > 0 on both)")
    assert rep["ci95_mean_net_bps"][1] < 0 and "data limit" in rep["reason"]


def test_intraday_momentum_non_decisive_failure_below_min_n():
    rep = _intraday(0.0002)                                         # a 2 bps edge that just pays the 2 bps cost
    _undecided(rep)
    assert rep["ci95_mean_net_bps"][0] < 0 < rep["ci95_mean_net_bps"][1]


def test_intraday_momentum_pass_below_min_n():
    rep = _intraday(0.0015)
    _pass_below(rep)
    assert "at least 500 days (only 300: data limit)" in rep["reason"]


# ----------------------------------------------------------------------------------- T-428 closing reversal --

def _reversal(beta, sd_co):
    s, truth = sessions(n=300, seed=5, beta_rev=beta, sd_co=sd_co)
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=300)
    assert rep["n"] < 500
    return rep


def test_closing_reversal_decisive_failure_below_min_n():
    rep = _reversal(0.5, 0.002)                                     # the overnight return continues the last half hour
    _decisive(rep, "slope <= -0.2", "deflated (Sidak, 32 cells) one-sided p < 0.01",
              "reversal-leg net Sharpe > 0.5 sized on the 15:45 state (needs sub-hourly bars)")
    assert rep["slope_ci95"][0] > 0 and rep["rule5"]["reversal_leg_sharpe_ci95"][1] < 0.5


def test_closing_reversal_non_decisive_failure_below_min_n():
    rep = _reversal(-0.1, 0.004)
    _undecided(rep)
    assert rep["slope_ci95"][0] < -0.2 and rep["slope_ci95"][1] > 0


def test_closing_reversal_pass_below_min_n():
    rep = _reversal(-0.5, 0.002)
    _pass_below(rep)
    assert "reversal-leg Sharpe 95% block-bootstrap interval" in rep["reason"]


def test_closing_reversal_without_1545_signal_keeps_leg_not_implemented_below_min_n():
    s, _ = sessions(n=300, seed=5, beta_rev=-0.1, sd_co=0.004)
    rep = bh.closing_reversal(s, n_boot=300)
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["reversal_leg_sharpe_ci95"] == [None, None]
    assert "not implemented" in rep["reason"] and "reversal-leg net Sharpe > 0.5" in rep["reason"]
