"""House rule 5, round 2, in batch5_hourly, batch5_fx and batch5_macro, on synthetic data. Below the trial's min_n a
one-sided 95% pass criterion fails decisively only when it fails at the SAME confidence: the one-sided 95% bound on the
other side (not a two-sided 95% interval, which is one-sided 97.5%).

  * T-427 deflated p (DSR > 0.95): the PSR against a zero Sharpe is <= 0.05.
  * T-368/T-431/T-478 'DSR > 0.95': the PSR against a zero Sharpe is <= 0.05 with the Newey-West t <= -1.645 (the
    monthly books are serially correlated, so the PSR alone would overstate its confidence).
  * T-343 / T-208 / T-219 one-sided p < 0.05: the same test in the opposite direction on the same draws gives p < 0.05.

At or above min_n nothing changes. No archive, no network."""

import numpy as np
import pytest

from mandel.experiments import batch5_fx as fx
from mandel.experiments import batch5_hourly as bh
from mandel.experiments import batch5_macro as bm

from tests.test_mandel_batch5_fx import G10_RATES, make_market
from tests.test_mandel_batch5_hourly import sessions
from tests.test_mandel_batch5_macro import _closes, _days, _release_world


def _decisive_only(rep, *names):
    """not_supported below min_n, and exactly ``names`` fail decisively."""
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert sorted(rep["rule5"]["decisive_failures"]) == sorted(names), rep["rule5"]["decisive_failures"]
    assert "house rule 5" in rep["reason"]


# ---------------------------------------------------------------------------------- T-427 deflated p (hourly) --
# 300 sessions, below min_n 500; QQQ/IWM not supplied (that criterion is not implemented)

def _intraday(seed, **kw):
    s, _ = sessions(n=300, seed=seed, mom=-0.0002)
    rep = bh.intraday_momentum(s, None, n_boot=300, **kw)
    assert rep["n"] == 300
    return rep


def test_intraday_deflated_p_fails_decisively_on_psr_vs_zero_when_mean_ci_straddles_zero():
    rep = _intraday(14)
    lo, hi = rep["ci95_mean_net_bps"]
    assert lo < 0 < hi                                              # the two-sided 95% mean CI alone decides nothing
    psr = rep["rule5"]["psr_vs_zero_sharpe"]
    assert psr <= 0.05 and psr == pytest.approx(0.015, abs=0.002)
    _decisive_only(rep, "deflated p < 0.05 over 60 cells")
    assert "PSR against a zero Sharpe 0.015" in rep["reason"]
    assert ["SPY mean net return > 0 (fails, not decisively, below min_n: undecided)", None] in rep["rule5"]["criteria"]


def test_intraday_deflated_p_stays_undecided_when_psr_vs_zero_is_above_005():
    rep = _intraday(9)
    assert rep["rule5"]["psr_vs_zero_sharpe"] > 0.05 and rep["ci95_mean_net_bps"][1] > 0
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


def test_intraday_at_min_n_is_judged_at_face_value_without_the_psr():
    rep = _intraday(14, min_n=300)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep
    assert "PSR against a zero Sharpe" not in rep["reason"] and "house rule 5" not in rep["reason"]


# --------------------------------------------------------------------------------- T-368 / T-431 FX carry DSR --
# test window 2013-01..2019-12: 84 months, below min_n 150. Spot falls 1.1x the carry (UIP overshoots).

@pytest.fixture(scope="module")
def carry_overshoot():
    spot, _ = make_market({c: 1.1 * r for c, r in G10_RATES.items()}, uip=True, seed=2)
    return fx.build_panel(spot, make_market(G10_RATES, seed=2)[1], fill_to="2026-08")


def _carry(panel, **kw):
    cb, ad = fx.g10_costs()
    return fx.carry_report(panel, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10",
                           test=kw.pop("test", ("2013-01", "2019-12")), n_boot=1000, **kw)


def test_carry_dsr_fails_decisively_on_psr_vs_zero_when_sharpe_interval_straddles_zero(carry_overshoot):
    rep = _carry(carry_overshoot)
    assert rep["n"] == 84 and rep["boot_lo"] < 0 < rep["boot_hi"] < 0.3
    r5 = rep["rule5"]
    assert r5["psr_vs_zero_sharpe"] <= 0.05 and r5["nw_t_vs_zero"] <= -1.645
    # the Sharpe bar decides through the interval; the DSR now decides at its own (one-sided 95%) confidence
    _decisive_only(rep, "test-window net Sharpe > 0.3", "DSR > 0.95 with n_trials = 6")
    assert "PSR against a zero Sharpe" in rep["reason"] and "Newey-West t" in rep["reason"]


def test_carry_at_min_n_is_judged_at_face_value_without_the_psr(carry_overshoot):
    rep = _carry(carry_overshoot, min_n=84)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "PSR against a zero Sharpe" not in rep["reason"]


def test_carry_under_48_months_reason_attaches_the_floor_to_the_test_months(carry_overshoot):
    rep = _carry(carry_overshoot, test=("2023-01", "2026-09"))
    n = rep["n"]
    assert n < 48 and rep["verdict"] == "inconclusive" and "rule5" not in rep
    assert f"dropped {len(rep['test_dropped'])} months; {n} test months is fewer than 48 (4 blocks of the 12-month bootstrap)" \
        in rep["reason"]
    assert "months, fewer than 48" not in rep["reason"]
    assert "need 150" in rep["reason"] and "no decisive failure below min_n (house rule 5)" in rep["reason"]


# ---------------------------------------------------------------------------------- T-478 FX momentum DSR --
# window 2010-01..2026-09: 201 months, below min_n 300

def _mom_panel(noise, seed):
    return fx.build_panel(*make_market(G10_RATES, noise_m=noise, seed=seed), fill_to="2026-08")


def _mom(panel, **kw):
    rep = fx.momentum_report(panel, window=("2010-01", "2026-09"), n_perm=200, n_boot=500, **kw)
    assert rep["n"] == 201
    return rep


def test_momentum_dsr_fails_decisively_on_psr_vs_zero_and_changes_the_verdict():
    rep = _mom(_mom_panel(0.015, 5))
    lo, hi = rep["ci_bps"]
    assert lo < 0 < hi and hi > rep["perm_q95_bps"]               # mean and permutation criteria: not decisive
    r5 = rep["rule5"]
    assert r5["psr_vs_zero_sharpe"] <= 0.05 and r5["nw_t_vs_zero"] <= -1.645
    _decisive_only(rep, "DSR > 0.95 with 16 trials")              # inconclusive under the old 97.5% mirror
    assert "PSR against a zero Sharpe" in rep["reason"]


def test_momentum_dsr_psr_needs_the_serial_correlation_robust_t_to_agree():
    rep = _mom(_mom_panel(0.02, 5))                                # PSR 0.046, but the books are autocorrelated
    r5 = rep["rule5"]
    assert r5["psr_vs_zero_sharpe"] <= 0.05 and r5["nw_t_vs_zero"] > -1.645
    assert rep["verdict"] == "inconclusive" and r5["decisive_failures"] == []


def test_momentum_at_min_n_is_judged_at_face_value_without_the_psr():
    rep = _mom(_mom_panel(0.015, 5), min_n=201)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "PSR against a zero Sharpe" not in rep["reason"]


def test_fx_psr_helper_is_never_decisive_with_a_positive_mean_or_too_few_months():
    rng = np.random.default_rng(0)
    up = rng.normal(0.01, 0.01, 120)
    assert fx._psr0_dec(up, 120)[2] is False
    down = -up
    psr, t, dec = fx._psr0_dec(down, 120)
    assert dec is True and psr < 0.05 and t < -1.645
    assert fx._psr0_dec(down[:40], 40)[2] is False                 # under 48 months nothing decides


# ----------------------------------------------------------------------------- T-343 studentized p (macro) --
# start 2008: about 590 release days, below min_n 600

def test_announcement_p_fails_decisively_on_the_opposite_studentized_p():
    days, c, cpi, es, fomc = _release_world(3, -3.5)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, start="2008-01-01", n_boot=200)
    assert rep["n"] < 600
    g = rep["net"]
    assert g["ci"][0] < 0 < g["ci"][1]                              # the two-sided 95% CI is not wholly below 0
    assert g["p_less"] < 0.05 and rep["rule5"]["p_opposite_studentized"] == g["p_less"]
    assert "studentized block-bootstrap p < 0.05" in rep["rule5"]["decisive_failures"]
    assert rep["verdict"] == "not_supported"
    assert "opposite one-sided studentized p (H0 diff >= 0)" in rep["reason"]


def test_announcement_at_min_n_is_judged_at_face_value():
    days, c, cpi, es, fomc = _release_world(3, -3.5)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, start="2008-01-01", n_boot=200, min_n=500)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "opposite one-sided" not in rep["reason"]


# -------------------------------------------------------------------------------- T-208 permutation p (macro) --
# end 2016: about 180 FOMC events, below min_n 200; about 57 OOS events

def _imhm_noisy(seed, mult):
    """Event moves of mult x the VIX-implied daily sd x a half-normal draw: the long P&L rises with IM/HM on average
    (the claim reversed), noisily."""
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-06-30")
    vixv = rng.uniform(10, 40, len(days))
    r = rng.normal(0, 0.01, len(days) - 1)
    ev_idx = list(range(20, len(days), 32))
    for i in ev_idx:
        r[i - 1] = rng.choice([-1, 1]) * mult * abs(rng.normal()) * vixv[i - 1] / 100 / np.sqrt(252)
    return days, _closes(r), dict(zip(days, vixv)), [days[i] for i in ev_idx]


def test_im_hm_permutation_criterion_fails_decisively_on_the_opposite_permutation_p():
    days, c, vix, ev = _imhm_noisy(9, 1.5)
    rep = bm.im_hm_filter(days, c, vix, ev, end="2016-12-31", n_perm=1000, n_boot=500, n_placebo=0)
    assert rep["n"] < 200
    lo, hi = rep["oos_spearman_rho_ci"]
    assert -0.1 < lo < 0 < hi                                       # the two-sided Fisher interval is not wholly >= 0
    p_g = rep["rule5"]["p_opposite_permutation"]
    assert p_g == rep["oos_perm_p_greater"] < 0.05
    assert p_g == bm.spearman_perm_p(*_oos_xy(rep, days, c, vix, ev), 1000, 0, "greater")
    assert "OOS one-sided permutation p < 0.05" in rep["rule5"]["decisive_failures"]
    assert "OOS Spearman rho < -0.1" in rep["rule5"]["decisive_failures"]        # the point criterion keeps the 95% CI
    assert "opposite one-sided permutation p (H0 rho <= 0)" in rep["reason"]


def _oos_xy(rep, days, c, vix, ev):
    """The OOS (IM/HM, long P&L) pairs the harness tested, rebuilt from its event table."""
    T = bm.event_move_table(days, c, vix, sorted(e for e in ev if e <= "2016-12-31"))
    m = T["days"] >= "2010-01-01"
    assert int(m.sum()) == rep["n_oos"]
    return T["ratio"][m], T["long"][m]


def test_im_hm_at_min_n_is_judged_at_face_value():
    days, c, vix, ev = _imhm_noisy(9, 1.5)
    rep = bm.im_hm_filter(days, c, vix, ev, end="2016-12-31", n_perm=1000, n_boot=500, n_placebo=0, min_n=100)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "oos_perm_p_greater" not in rep


# ------------------------------------------------------------------------------ T-219 permutation p (macro) --
# from 2005: about 87 witching Fridays, below min_n 100

def _witching_noisy(seed, k):
    """Witching Fridays move k x an ordinary Friday (random size): the long straddle loses there, noisily."""
    rng = np.random.default_rng(seed)
    days = _days("1993-01-04", "2026-09-30")
    vix = {d: 20.0 for d in days}
    r = rng.normal(0, 0.2 / np.sqrt(252), len(days) - 1)
    pos = {d: i for i, d in enumerate(days)}
    for w in bm.third_fridays(1993, 2026, bm.WITCHING_MONTHS):
        if w in pos:
            r[pos[w] - 1] *= k
    return days, _closes(r), vix


def test_witching_permutation_criterion_fails_decisively_on_the_opposite_permutation_p():
    days, c, vix = _witching_noisy(0, 0.9)
    rep = bm.witching_straddle(days, c, vix, start="2005-01-01", n_boot=300, n_perm=1000)
    assert rep["n"] < 100
    lo, hi = rep["full"]["ci"]
    assert lo < 0 < hi                                              # the CI decides nothing: inconclusive before
    p_less = rep["rule5"]["p_opposite_permutation"]
    assert p_less == rep["permutation_p_less"] < 0.05 and rep["permutation_p"] > 0.5
    _decisive_only(rep, "permutation p < 0.05")
    assert "opposite one-sided permutation p (H0 witching >= other)" in rep["reason"]


def test_witching_ci_wholly_below_zero_no_longer_labels_the_permutation_criterion_decisive():
    from tests.test_mandel_batch5_macro import _witching_world
    days, c, vix = _witching_world(3, 0.8)
    rep = bm.witching_straddle(days, c, vix, start="2005-01-01", n_boot=300, n_perm=1000)
    assert rep["full"]["ci"][1] < 0 and rep["permutation_p_less"] > 0.05
    _decisive_only(rep, "witching-minus-other mean long P&L > 0", "95% CI excludes 0 (lower bound > 0)")


def test_witching_at_min_n_is_judged_at_face_value():
    days, c, vix = _witching_noisy(0, 0.9)
    rep = bm.witching_straddle(days, c, vix, start="2005-01-01", n_boot=300, n_perm=1000, min_n=50)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "permutation_p_less" not in rep
