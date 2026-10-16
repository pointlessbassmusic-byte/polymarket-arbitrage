"""House rule 5 in batch4_carry, round 2, on synthetic data: below the trial's min_n a failing criterion counts only when
it fails DECISIVELY at the SAME confidence as its pass. A one-sided 95% pass (a 95% lower bound, a one-sided p < 0.05) is
mirrored by the one-sided 95% bound on the other side from the same bootstrap draws, not by the two-sided 95% interval
(which is one-sided 97.5%). Each case below has a 95% bound on the wrong side while its 97.5% end is not, so it is
not_supported now and was undecided before. At or above min_n nothing changes, and the new bounds are never computed
there. No archive, no network."""

from datetime import date

import numpy as np
import pytest

from mandel.experiments import batch4_carry as cy
from mandel.experiments.underlying2 import _verdict

from tests.test_mandel_batch4_carry import _cme_setup, _contracts, _days, _hours
from tests.test_mandel_rule5_r5c import _cme_noise, _sentiment

NB = 1000


def _decisive_only(rep, name):
    """not_supported below min_n with ``name`` the only decisive failure."""
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == [name], rep["rule5"]["decisive_failures"]
    assert (name + " (fails decisively below min_n)", False) in rep["criteria"]
    assert "house rule 5" in rep["reason"]


def _face_value(rep):
    assert "rule5" not in rep and "house rule 5" not in rep["reason"]
    assert all("below min_n" not in c for c, _ in rep["criteria"])
    assert (rep["verdict"], rep["reason"].rsplit(" — ", 1)[1]) == _verdict(rep["criteria"])


# ----------------------------------------------------------------------------------------------- helpers --

def test_wide_interval_guard():
    assert cy._wide([-1.0, 1.0]) and not cy._wide([0.0, 0.0]) and not cy._wide([None, None]) and not cy._wide([1.0, -1.0])


def test_cluster_mean_ub95_is_the_95pct_quantile_of_the_same_draws():
    rng = np.random.default_rng(3)
    x = rng.normal(-0.001, 0.003, 30); cl = [f"2022-{1 + i // 2:02d}" for i in range(30)]
    b = cy.cluster_mean_boot(x, cl, NB, 7); ub = cy.cluster_mean_ub95(x, cl, NB, 7)
    keys = sorted(set(cl)); sums = np.array([x[np.array(cl) == k].sum() for k in keys]); cnt = np.array([cl.count(k) for k in keys])
    pick = np.random.default_rng(7).integers(0, len(keys), size=(NB, len(keys)))
    m = sums[pick].sum(axis=1) / cnt[pick].sum(axis=1)                    # cluster_mean_boot's draws, rebuilt
    assert ub == float(np.quantile(m, 0.95)) and b["lb95"] == float(np.quantile(m, 0.05))
    assert b["ci95"][0] < b["lb95"] < ub < b["ci95"][1]


def test_student_mean_ub95_mirrors_lb95():
    rng = np.random.default_rng(0)
    x = 0.2 + rng.standard_normal(40)
    ci = cy.student_mean_ci(x, 3, NB, 5); ub = cy.student_mean_ub95(x, 3, NB, 5)
    assert ci["ci95"][0] < ci["lb95"] < ci["mean"] < ub < ci["ci95"][1]
    # the same t* draws: ub - m and m - lb are the 5% and 95% quantiles of t* times se, the two-sided ends the 2.5/97.5%
    assert ub - ci["mean"] < ci["ci95"][1] - ci["mean"] and ci["mean"] - ci["lb95"] < ci["mean"] - ci["ci95"][0]
    assert cy.student_mean_ub95(np.zeros(10)) is None and cy.student_mean_ub95([1.0, 2.0, 3.0]) is None


def test_stationary_sharpe_ub95_is_from_the_same_draws():
    rng = np.random.default_rng(1)
    x = 0.001 + 0.02 * rng.standard_normal(120)
    st = cy.stationary_sharpe_ci(x, 14, NB, 2); ub = cy.stationary_sharpe_ub95(x, 14, NB, 2)
    v = cy._stationary_sharpe_draws(x, 14, NB, 2, cy.CRYPTO_PPY, 500)
    assert st["ci95"] == [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] and ub == float(np.quantile(v, 0.95))
    assert st["lb95"] < ub < st["ci95"][1] and cy.stationary_sharpe_ub95(x[:7]) is None


def test_stationary_mean_draws_are_the_p_value_draws():
    rng = np.random.default_rng(4)
    g = 0.002 + 0.01 * rng.standard_normal(150)
    mb = cy._stationary_mean_draws(g, 7, NB, 3, 500); m = float(g.mean())
    assert cy.stationary_mean_p_less(g, 7, NB, 3) == (1 + int(np.sum(mb - m <= m))) / (1 + NB)
    assert cy.stationary_mean_ci(g, 7, NB, 3) == [float(np.quantile(mb, 0.025)), float(np.quantile(mb, 0.975))]


# ------------------------------------------------------------------------- T-329 CME basis spikes: the mean --

def test_t329_mean_upper_bound_at_or_below_zero_is_decisive():
    # 29 trades (min_n 40): the month-clustered 95% quantile of the mean is <= 0 but its 97.5% quantile is > 0
    days, F, S, std, ex = _cme_noise(0.03, 4)
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB, cost_rt=0.0021)
    b, r5 = rep["boot"], rep["rule5"]
    assert rep["n"] == 29 and b["clusters"] >= cy.MIN_DECISIVE_OBS and b["lb95"] <= 0
    assert r5["mean_ub95"] <= 0 < b["ci95"][1]
    assert not cy._ci_below(b["ci95"], 0.0)                                 # the two-sided (97.5%) mirror would not decide
    assert r5["mean_ub95"] == cy.cluster_mean_ub95([t["net"] for t in rep["trades"]], [t["entry"][:7] for t in rep["trades"]], NB, 0)
    _decisive_only(rep, "one-sided 95% lower bound of mean net return per trade > 0 (month-clustered bootstrap)")
    assert "one-sided 95% upper bound of the mean" in rep["reason"] and "month-clustered 95% CIs" in rep["reason"]
    assert set(r5["halves_month_clustered"]) == {"pre_2024", "post_2024"}   # halves still on two-sided CIs, not decisive


def test_t329_upper_bound_above_zero_stays_undecided():
    days, F, S, std, ex = _cme_noise(0.03, 4)
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB, cost_rt=0.0019)
    assert rep["boot"]["lb95"] <= 0 < rep["rule5"]["mean_ub95"]
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


# ----------------------------------------------------------------------------------- T-362 cash-and-carry --

@pytest.mark.parametrize("slip_mean,seed", [(0.006, 4), (0.01, 11)])
def test_t362_studentized_upper_bound_at_or_below_zero_is_decisive(slip_mean, seed):
    # 18 test contract-months (min_n 50): the one-sided 95% studentized upper bound is <= 0, the two-sided upper end > 0
    rep = cy.cme_cash_and_carry(_contracts(0.10, slip_mean=slip_mean, slip_sd=0.03, seed=seed), test=("2022-01", "2023-06"),
                                n_boot=2000)
    ci, ub = rep["ci"], rep["rule5"]["ub95"]
    assert rep["n"] == 18 and ci["se"] > 0 and ci["lb95"] < 0
    assert ub <= 0 < ci["ci95"][1] and ub == cy.student_mean_ub95([c["ann_excess"] for c in rep["contracts"]], 3, 2000, 0)
    assert "ub95" not in ci                                                  # the reported ci dict is unchanged
    _decisive_only(rep, "one-sided 95% studentized block-bootstrap lower bound of mean annualised excess > 0")
    assert f"one-sided 95% upper bound {cy._pp(ub)}%" in rep["reason"]
    if seed == 4:
        assert ub == pytest.approx(-0.0186, abs=5e-4) and ci["ci95"][1] == pytest.approx(0.0166, abs=5e-4)


def test_t362_never_entering_still_decides_nothing():
    rep = cy.cme_cash_and_carry(_contracts(0.03), test=("2022-01", "2023-06"), n_boot=NB)
    assert rep["entered"] == 0 and rep["ci"]["se"] == 0.0 and rep["rule5"]["ub95"] is None
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


# ----------------------------------------------------------------------------- T-363 thresholded perp carry --

def _iid_funding():
    fts = _hours("2022-09-01", "2023-06-30")
    return fts, 1.2e-4 * np.random.default_rng(5).standard_normal(len(fts))


def test_t363_lower_bound_row_decides_on_the_optimistic_upper_bound():
    # 36 in-position days (min_days 250): the optimistic Sharpe's 95% quantile <= 0.3 < its 97.5% quantile
    fts, i1 = _iid_funding()
    rep = cy.perp_funding_carry(fts, i1, {"2019-01-02": 2.0}, test=("2023-01-01", "2023-03-01"), n_boot=NB)
    ci, ub = rep["ci95"]["opt"], rep["rule5"]["opt_sharpe_ub95"]
    lb_row = "stationary-bootstrap one-sided 95% lower bound of Sharpe > 0.3 (spread-bounded)"
    assert rep["days_in_position"] == 36 and rep["lb95"]["opt"] <= 0.3
    assert ub <= 0.3 < ci[1] and not cy._ci_below(ci, 0.3)                  # undecided under the two-sided mirror
    assert lb_row in rep["rule5"]["decisive_failures"] and (lb_row + " (fails decisively below min_n)", False) in rep["criteria"]
    assert rep["verdict"] == "not_supported"
    assert "one-sided 95% upper bound" in rep["reason"] and "optimistic-spread Sharpe" in rep["reason"]
    # the Sharpe > 1 row keeps the two-sided interval: it is decisive here because the upper end is <= 1
    assert ci[1] <= 1.0 and "test Sharpe > 1.0 after costs and perp-spot spread (spread-bounded)" in rep["rule5"]["decisive_failures"]


# ------------------------------------------------------------------------------ T-364 basis as crash signal --

def _rally(up, seed):
    """Weekly basis with a rich (top-decile) week every 13 weeks, followed by a 30-day rally of ``up`` a day: the rally
    makes the forward drawdown after a rich week SHALLOWER, so the gap (top - bottom half) is negative."""
    rng = np.random.default_rng(seed)
    weeks = [d for d in _days("2017-12-04", "2026-09-28") if date.fromisoformat(d).weekday() == 0]
    b = 0.05 + 0.01 * rng.standard_normal(len(weeks))
    spikes = list(range(5, len(weeks), 13)); b[spikes] = 0.20
    pdays = _days("2017-11-01", "2026-12-31")
    r = 0.01 * rng.standard_normal(len(pdays)); pos = {d: i for i, d in enumerate(pdays)}
    for k in spikes:
        i = pos[weeks[k]]; r[i + 1:i + 31] += up
    return weeks, b, pdays, 100 * np.cumprod(1 + r)


def test_t364_permutation_row_decides_on_the_gap_upper_bound():
    # 265 weeks (min_n 350). The gap row's bound is lowered to -50 pp so it passes and only the permutation row (a
    # one-sided 5% test) can decide: the gap's 95% quantile is <= 0 while its 97.5% quantile is > 0
    rep = cy.basis_crash_predictor(*_rally(0.0025, 5), n_perm=NB, end="2023-12-31", gap_pp=-50.0)
    r5 = rep["rule5"]; ci = r5["gap_ci95_pp"]["all"]
    assert rep["n"] == 265 and rep["p_perm"] >= 0.05
    assert r5["gap_ub95_pp"] <= 0 < ci[1] and not cy._ci_below(ci, 0.0)
    assert not cy._ci_below(r5["gap_ci95_pp"]["first"], 0.0) and not cy._ci_below(r5["gap_ci95_pp"]["second"], 0.0)
    _decisive_only(rep, "block-permutation p < 0.05")
    assert "one-sided 95% upper bound of the gap" in rep["reason"]
    # at the trial's 10 pp the gap row (a point estimate, two-sided interval wholly below 10 pp) decides as well
    rep = cy.basis_crash_predictor(*_rally(0.0025, 5), n_perm=NB, end="2023-12-31")
    assert set(rep["rule5"]["decisive_failures"]) == {"depth gap (top decile - bottom half) >= 10 pp", "block-permutation p < 0.05"}


def test_block_gap_ub95_is_between_the_two_sided_ends():
    rng = np.random.default_rng(2)
    lab = rng.choice([0, 1, 2], size=200, p=[0.5, 0.4, 0.1]); dep = 10 + 3 * rng.standard_normal(200)
    lo, hi = cy.block_gap_ci(lab, dep, 8, NB, 1); ub = cy.block_gap_ub95(lab, dep, 8, NB, 1)
    g = cy._block_gap_draws(lab, dep, 8, NB, 1)
    assert lo < ub < hi and ub == float(np.quantile(g, 0.95))
    assert cy.block_gap_ub95(np.array([2, 2, 0, 0, 0]), np.arange(5.0), 2, NB) is None     # fewer than 4 top weeks


# ---------------------------------------------------------------------------------- T-423 funding sentiment --

def test_t423_p_row_decides_on_the_opposite_tail_p_of_the_same_draws(monkeypatch):
    # min_top raised to 1000 (the sample has 236 top-decile days). The -2 pp row's bound is raised to +50 pp so it
    # passes and only the p row (one-sided 5%, H0: diff >= 0) can decide: q05 >= 0 > q025 of the bootstrap means
    seen = {}
    real = cy._stationary_mean_draws

    def spy(x, *a):
        seen["mb"] = real(x, *a); return seen["mb"]

    monkeypatch.setattr(cy, "_stationary_mean_draws", spy)
    rep = cy.funding_sentiment(*_sentiment(0.0127, 2, sd=0.004), n_boot=NB, min_top=1000, gap=0.5)
    r5 = rep["rule5"]; lo, hi = r5["oos_diff_ci95"]; pg = r5["oos_p_greater"]
    q05 = float(np.quantile(seen["mb"], 0.05))
    assert rep["n_top"] < 1000 and rep["oos"]["p"] >= 0.05                   # the p criterion fails at face value
    assert lo < 0 <= q05 and not cy._ci_above([lo, hi], 0.0)                # the two-sided (97.5%) mirror would not decide
    assert pg < 0.05
    # p_less (the report's p) and p_greater count opposite tails of the SAME draws: with no ties they sum to (B+2)/(B+1)
    assert rep["oos"]["p"] + pg == pytest.approx((NB + 2) / (NB + 1), abs=1e-12)
    _decisive_only(rep, "out-of-sample stationary-bootstrap p < 0.05 (H0: difference >= 0)")
    assert "opposite-tail p" in rep["reason"]


def test_t423_opposite_tail_p_above_005_stays_undecided():
    rep = cy.funding_sentiment(*_sentiment(0.012, 2, sd=0.004), n_boot=NB, min_top=1000, gap=0.5)
    assert rep["oos"]["p"] >= 0.05 and rep["rule5"]["oos_p_greater"] >= 0.05
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []


# ------------------------------------------------------------------- at or above min_n: nothing new is computed --

def test_at_or_above_min_n_the_new_bounds_are_never_computed(monkeypatch):
    for nm in ("cluster_mean_ub95", "student_mean_ub95", "stationary_sharpe_ub95", "block_gap_ub95"):
        monkeypatch.setattr(cy, nm, lambda *a, **k: 1 / 0)
    monkeypatch.setattr(cy, "_stationary_mean_draws", lambda *a, **k: 1 / 0)    # T-423's below-min_n draws
    days, F, S, std, ex = _cme_setup(True)                                   # 103 trades >= 40
    _face_value(cy.cme_basis_spike(days, F, S, std, ex, n_boot=300))
    rep = cy.cme_cash_and_carry(_contracts(0.10, slip_mean=0.006, slip_sd=0.03, seed=4), n_boot=300)
    assert rep["n"] >= 50 and "ub95" not in rep["ci"]
    _face_value(rep)
    fts, i1 = _iid_funding()
    _face_value(cy.perp_funding_carry(fts, i1, {"2019-01-02": 2.0}, test=("2023-01-01", "2023-03-01"), n_boot=300, min_days=30))
    _face_value(cy.basis_crash_predictor(*_rally(0.0025, 5), n_perm=300, end="2023-12-31", min_n=200))
    rep = cy.funding_sentiment(*_sentiment(0.0127, 2, sd=0.004), n_boot=300)
    assert rep["n_top"] >= 200
    _face_value(rep)
