"""House rule 5 in batch4_carry, on synthetic data: below the trial's min_n (in the claim's own units) a decisive failure
(the criterion's 95% interval wholly on the wrong side of the claimed bound, or a failure that would persist at min_n
whatever the missing observations are) is not_supported, a non-decisive failure is inconclusive, and a pass is
inconclusive. At or above min_n every criterion is judged at face value. No archive, no network."""

from datetime import date

import numpy as np
import pytest

from mandel.experiments import batch4_carry as cy
from mandel.experiments.underlying2 import _verdict

from tests.test_mandel_batch4_carry import (_cme_setup, _contracts, _days, _hedged_setup, _hours, _quarterly_setup,
                                            _trend_setup)

NB = 300


def _decisive(rep):
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"], rep["rule5"]
    assert "fails decisively below min_n" in rep["reason"] and "house rule 5" in rep["reason"]
    assert any(ok is None for c, ok in rep["criteria"] if "min_n" in c or ">=" in c)        # the min_n row is unmet


def _undecided(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    assert "fails, not decisively, below min_n: undecided" in rep["reason"] and "house rule 5" in rep["reason"]
    assert any(ok is False for _, ok in rep["rule5"]["criteria_at_face_value"])           # it failed at face value


def _pass_below(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == [] and "house rule 5" in rep["reason"]
    assert not any(ok is False for _, ok in rep["rule5"]["criteria_at_face_value"])
    assert not any("below min_n" in c for c, _ in rep["criteria"])


# ----------------------------------------------------------------------------------------------- the helper --

def test_rule5_helper():
    crit = [("n >= 10 (min_n)", None), ("mean > 0", False), ("p < 0.05", False), ("halves", True)]
    v, why, judged, r5 = cy._rule5(crit, 5, 10, "trades", lambda: [False, True, False, False])
    assert v == "not_supported" and r5["decisive_failures"] == ["mean > 0"]
    assert judged == [("n >= 10 (min_n)", None), ("mean > 0 (fails decisively below min_n)", False),
                      ("p < 0.05 (fails, not decisively, below min_n: undecided)", None), ("halves", True)]
    assert "only 5 trades, below the trial's min_n 10" in why and "criteria at face value: not_supported" in why
    v, _, _, r5 = cy._rule5(crit, 5, 10, "trades", lambda: [False] * 4)
    assert v == "inconclusive" and r5["decisive_failures"] == []
    # at or above min_n: judged at face value, exactly _verdict, and decisive() is never called
    full = [("n >= 10 (min_n)", True)] + crit[1:]
    assert cy._rule5(full, 10, 10, "trades", lambda: 1 / 0) == (*_verdict(full), full, None)


def test_interval_helpers():
    assert cy._ci_below([-2.0, -1.0], 0.0) and cy._ci_below([-2.0, 0.0], 0.0) and not cy._ci_below([-2.0, 0.0], 0.0, strict=True)
    assert not cy._ci_below([-1.0, 1.0], 0.0) and not cy._ci_below([None, None], 0.0)
    assert not cy._ci_below([0.0, 0.0], 0.0)                     # zero width (constant data) decides nothing
    assert cy._ci_above([0.5, 1.0], 0.0) and cy._ci_above([-0.01, 0.0], -0.02, strict=True) and not cy._ci_above([-1.0, 1.0], 0.0)


# -------------------------------------------------------------------------- T-198 funding vs quarterly basis --

def test_t198_rule5():
    # min_n raised to 40 windows: the archive-like sample has 28
    fts, i1, idx, fut = _quarterly_setup(0.0, 0.08, seed=1)        # no funding, 8%/yr basis paid: every window loses
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=40)
    assert rep["n"] == 28 and rep["share"] == 0.0 and rep["ci95"][1] < 0
    _decisive(rep)                                                  # 0 + 12 missing wins < 20 of 40; CI wholly below 0
    assert len(rep["rule5"]["decisive_failures"]) == 2
    fts, i1, idx, fut = _quarterly_setup(0.04 * 90 / 365 / 2160, 0.04, seed=3)   # funding prices the basis exactly
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=40)
    assert rep["ci95"][0] < 0 < rep["ci95"][1]
    _undecided(rep)
    fts, i1, idx, fut = _quarterly_setup(3e-5, 0.01)
    _pass_below(cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=40))


def test_t198_share_fails_decisively_only_when_min_n_cannot_rescue_it():
    # 0 wins in 28 windows: with min_n 40, 0 + 12 missing wins is 30% < 50% (decisive); with min_n 56, 0 + 28 missing
    # wins is exactly 50% (the share could still pass at min_n, so its failure is undecided)
    share = "share of windows with funding_90d > basis_90d >= 50%"
    fts, i1, idx, fut = _quarterly_setup(0.0, 0.08, seed=1)
    assert share in cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=40)["rule5"]["decisive_failures"]
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=56)
    assert rep["rule5"]["decisive_failures"] == ["mean difference's 95% block-bootstrap CI above 0"]
    assert (share + " (fails, not decisively, below min_n: undecided)", None) in rep["criteria"]
    assert rep["verdict"] == "not_supported"                                    # the CI still fails decisively


# -------------------------------------------------------------------------- T-258 option-hedged funding carry --

def test_t258_rule5():
    # 12 months (2021-04..2022-03) against min_n 24
    fts, i1, deliv, dvol, rf = _hedged_setup(0.0, 0.3, seed=2)       # pays the premium, earns nothing
    rep = cy.funding_call_hedged(fts, i1, deliv, dvol, rf, start="2021-04", end="2022-03", n_boot=NB)
    assert rep["n"] == 12 and rep["ci95"][1] < 0 and rep["rule5"]["sharpe_excess_ci95"][1] <= 1
    _decisive(rep)
    assert "block-bootstrap 95% interval" in rep["reason"]
    fts, i1, deliv, dvol, rf = _hedged_setup(1e-5, 1.0, seed=2)      # volatile payoffs: the mean's CI straddles 0
    rep = cy.funding_call_hedged(fts, i1, deliv, dvol, rf, start="2021-04", end="2022-03", n_boot=NB)
    assert rep["ci95"][0] < 0 < rep["ci95"][1]
    _undecided(rep)
    fts, i1, deliv, dvol, rf = _hedged_setup(1.5e-4, 0.3)
    _pass_below(cy.funding_call_hedged(fts, i1, deliv, dvol, rf, start="2021-04", end="2022-03", n_boot=NB))


# ------------------------------------------------------------------------------- T-303 trend + funding filter --

def _trend_k(k, seed):
    """_trend_setup with the return during each crowding episode shifted by k (k < 0: small crashes)."""
    rng = np.random.default_rng(seed)
    days = _days("2019-01-01", "2026-10-01"); n = len(days)
    fts = cy._utc_ts(days[0]) + 3600 * np.arange(1, n * 24 + 1)
    lvl = 1e-4 + 2e-5 * rng.standard_normal(n)
    r = 0.003 + 0.035 * rng.standard_normal(n)
    for j, s in enumerate(range(420, n - 20, 100)):
        lvl[s - 8:s - 2] = 1e-4 * (8 + 2 * j) * np.linspace(0.6, 1.0, 6)
        lvl[s - 2:s + 8] = 2.5e-4
        r[s:s + 6] += k
    return days, 100 * np.cumprod(1 + r), fts, np.repeat(lvl, 24) + 1e-6 * rng.standard_normal(n * 24)


def test_t303_rule5():
    # 2020-03..2023-12: 1401 days against min_n 2000
    days, closes, fts, i8 = _trend_setup(False)                      # the filter only pays costs: interval below 0
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2023-12-31", n_boot=NB)
    assert rep["n"] == 1401 and rep["ci95"][1] < 0
    _decisive(rep)
    days, closes, fts, i8 = _trend_k(-0.005, 2)                       # weak effect: the interval straddles 0
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2023-12-31", n_boot=NB)
    assert rep["ci95"][0] < 0 < rep["ci95"][1]
    _undecided(rep)
    days, closes, fts, i8 = _trend_setup(True)
    _pass_below(cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2023-12-31", n_boot=NB))


def test_t303_placebo_interval_off_zero_is_decisive():
    days, closes, fts, i8 = _trend_k(-0.005, 3)
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2023-12-31", n_boot=NB)
    assert rep["placebo"]["ci95"][1] < 0 and rep["ci95"][0] < 0 < rep["ci95"][1]
    _decisive(rep)
    assert rep["rule5"]["decisive_failures"] == ["placebo (F lagged 30 days) 95% interval includes 0"]


def test_t303_under_three_blocks_is_inconclusive():
    days, closes, fts, i8 = _trend_setup(False)
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2020-04-30", n_boot=NB)
    assert rep["n"] < 90 and rep["verdict"] == "inconclusive" and "fewer than 3 blocks" in rep["reason"]


# ------------------------------------------------------------------------------------- T-329 CME basis spikes --

def _cme_noise(sd, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2018-01-02", "2026-09-30", weekdays_only=True); n = len(days)
    S = 10000 * np.exp(np.cumsum(0.02 * rng.standard_normal(n)))
    ex = cy.cme_expiries(2017, 2027)
    dte = np.array([(cy.front_expiry(d, ex) - date.fromisoformat(d)).days for d in days], dtype=float)
    return days, S * (1 + (0.05 + sd * rng.standard_normal(n)) * dte / 365), S, np.ones(n, dtype=bool), ex


def test_t329_rule5():
    days, F, S, std, ex = _cme_setup(False, seed=3)                    # quiet basis: every trade pays the 20 bp cost
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB)
    assert rep["n"] < 40 and rep["boot"]["ci95"][1] < 0
    _decisive(rep)
    assert "month-clustered 95% CIs" in rep["reason"]
    days, F, S, std, ex = _cme_noise(0.03)                             # reversion roughly pays a 15 bp cost
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB, cost_rt=0.0015)
    assert rep["n"] < 40 and rep["boot"]["ci95"][0] < 0 < rep["boot"]["ci95"][1]
    _undecided(rep)
    days, F, S, std, ex = _cme_setup(True)                             # 103 planted trades, min_n raised to 500
    _pass_below(cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB, min_n=500))


# ----------------------------------------------------------------------------------- T-362 cash-and-carry --

def test_t362_rule5():
    # test window 2022-01..2023-06: 18 contract-months against min_n 50
    rep = cy.cme_cash_and_carry(_contracts(0.15, slip_mean=0.03, slip_sd=0.003), test=("2022-01", "2023-06"), n_boot=NB)
    assert rep["n"] == 18 and rep["ci"]["ci95"][1] < 0
    _decisive(rep)
    assert "two-sided 95% CI" in rep["reason"]
    rep = cy.cme_cash_and_carry(_contracts(0.10, slip_sd=0.05, seed=1), test=("2022-01", "2023-06"), n_boot=NB)
    assert rep["ci"]["ci95"][0] < 0 < rep["ci"]["ci95"][1]
    _undecided(rep)
    _pass_below(cy.cme_cash_and_carry(_contracts(0.15, slip_sd=0.001), test=("2022-01", "2023-06"), n_boot=NB))


def test_t362_never_entering_below_min_n_is_inconclusive():
    # a zero-width CI (every month at 0) decides nothing below min_n; at 57 months it is not_supported (existing test)
    rep = cy.cme_cash_and_carry(_contracts(0.03), test=("2022-01", "2023-06"), n_boot=NB)
    assert rep["entered"] == 0 and rep["ci"]["ci95"] == [0.0, 0.0]
    _undecided(rep)


def test_t362_under_four_months_is_inconclusive():
    rep = cy.cme_cash_and_carry(_contracts(0.15, slip_mean=0.03), test=("2022-01", "2022-03"), n_boot=NB)
    assert rep["n"] == 3 and rep["verdict"] == "inconclusive" and "fewer than 4" in rep["reason"]


# ----------------------------------------------------------------------------- T-363 thresholded perp carry --

def _midnight_noise(ann, s0, seed):
    """Funding at ``ann`` a year plus noise on the 00:00 UTC prints (the spread mark-to-market reads them)."""
    rng = np.random.default_rng(seed)
    fts = _hours("2019-05-01", "2026-10-15")
    i1 = np.full(len(fts), ann / 8760)
    mid = (fts % 86400) == 0
    i1[mid] += s0 * rng.standard_normal(int(mid.sum()))
    return fts, i1


def test_t363_rule5():
    rng = np.random.default_rng(1)
    fts = _hours("2019-05-01", "2026-10-15")
    rep = cy.perp_funding_carry(fts, 1.5e-4 * rng.standard_normal(len(fts)), {"2019-01-02": 2.0},
                                test=("2023-01-01", "2023-06-30"), n_boot=NB)              # iid funding: costs dominate
    assert rep["days_in_position"] < 250 and rep["ci95"]["opt"][1] < 0.3
    _decisive(rep)
    assert len(rep["rule5"]["decisive_failures"]) == 2 and "optimistic-spread Sharpe" in rep["reason"]
    fts, i1 = _midnight_noise(0.12, 4e-4, 2)                                               # 2 months: a wide interval
    rep = cy.perp_funding_carry(fts, i1, {"2019-01-02": 2.0}, test=("2023-01-01", "2023-02-28"), n_boot=NB)
    assert rep["sharpe"]["opt"] < 1 < rep["ci95"]["opt"][1]
    _undecided(rep)
    rng = np.random.default_rng(0)
    rep = cy.perp_funding_carry(fts, 0.30 / 8760 + 2e-6 * rng.standard_normal(len(fts)), {"2019-01-02": 2.0},
                                test=("2023-01-01", "2023-06-30"), n_boot=NB)
    assert rep["days_in_position"] == 181
    _pass_below(rep)


# ------------------------------------------------------------------------------ T-364 basis as crash signal --

def _crash(drop, seed):
    rng = np.random.default_rng(seed)
    weeks = [d for d in _days("2017-12-04", "2026-09-28") if date.fromisoformat(d).weekday() == 0]
    b = 0.05 + 0.01 * rng.standard_normal(len(weeks))
    spikes = list(range(5, len(weeks), 13)); b[spikes] = 0.20
    pdays = _days("2017-11-01", "2026-12-31")
    r = 0.01 * rng.standard_normal(len(pdays)); pos = {d: i for i, d in enumerate(pdays)}
    for k in spikes:
        i = pos[weeks[k]]; r[i + 1:i + 11] += drop                  # ``drop`` a day for 10 days after a rich week
    return weeks, b, pdays, 100 * np.cumprod(1 + r)


def test_t364_rule5():
    # labelled weeks through 2023-12: 265 against min_n 350
    rep = cy.basis_crash_predictor(*_crash(0.0, 5), n_perm=NB, end="2023-12-31")
    assert rep["n"] == 265 and rep["rule5"]["gap_ci95_pp"]["all"][1] < 10
    _decisive(rep)
    assert rep["rule5"]["decisive_failures"] == ["depth gap (top decile - bottom half) >= 10 pp"]
    rep = cy.basis_crash_predictor(*_crash(-0.028, 1), n_perm=NB, end="2023-12-31")
    assert rep["gap_pp"] < 10 < rep["rule5"]["gap_ci95_pp"]["all"][1]
    _undecided(rep)
    _pass_below(cy.basis_crash_predictor(*_crash(-0.035, 0), n_perm=NB, end="2023-12-31"))


def test_t364_no_labelled_week_is_inconclusive():
    weeks, b, pdays, px = _crash(0.0, 5)
    rep = cy.basis_crash_predictor(weeks[:40], b[:40], pdays, px, n_perm=NB)      # fewer than the 52-week history
    assert rep["n"] == 0 and rep["verdict"] == "inconclusive"


# ---------------------------------------------------------------------------------- T-423 funding sentiment --

def _sentiment(effect, seed, sd=0.002):
    rng = np.random.default_rng(seed)
    days = _days("2019-06-01", "2026-10-31"); n = len(days)
    lvl = 1e-4 + 2e-5 * rng.standard_normal(n)
    spike = rng.random(n) < 0.12; lvl[spike] = 3e-4
    fts = cy._utc_ts(days[0]) + 3600 * np.arange(1, n * 24 + 1)
    lr = sd * rng.standard_normal(n * 24)
    for d in np.flatnonzero(spike):
        h0 = (d + 1) * 24; lr[h0:h0 + 7 * 24] += np.log(1 + effect) / (7 * 24)
    return fts, np.repeat(lvl, 24), 30000 * np.exp(np.cumsum(lr))


def test_t423_rule5():
    # min_top (the trial's min_n in top-decile days) raised to 1000; the samples have ~260
    rep = cy.funding_sentiment(*_sentiment(0.05, 0), n_boot=NB, min_top=1000)      # crowding precedes a +5% week
    assert rep["n_top"] < 1000 and rep["rule5"]["oos_diff_ci95"][0] > 0
    _decisive(rep)
    assert len(rep["rule5"]["decisive_failures"]) == 2                              # the -2 pp bound and the p-value
    rep = cy.funding_sentiment(*_sentiment(-0.017, 0, sd=0.004), n_boot=NB, min_top=1000)
    lo, hi = rep["rule5"]["oos_diff_ci95"]
    assert rep["oos"]["diff"] > -0.02 and lo < -0.02 < hi
    _undecided(rep)
    _pass_below(cy.funding_sentiment(*_sentiment(-0.05, 0), n_boot=NB, min_top=1000))


# ------------------------------------------------------------------------- at or above min_n: face value --

def test_at_or_above_min_n_is_face_value():
    fts, i1, idx, fut = _quarterly_setup(0.0, 0.08, seed=1)
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)                  # 28 windows >= 24
    assert "rule5" not in rep and rep["verdict"] == "not_supported" and "house rule 5" not in rep["reason"]
    assert (rep["verdict"], rep["reason"].rsplit(" — ", 1)[1]) == _verdict(rep["criteria"])
    days, closes, fts, i8 = _trend_k(-0.005, 3)                                      # placebo off 0, judged as it is
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2026-10-01", n_boot=NB, min_n=100)
    assert "rule5" not in rep and (rep["verdict"], rep["reason"].rsplit(" — ", 1)[1]) == _verdict(rep["criteria"])
    assert all("below min_n" not in c for c, _ in rep["criteria"])


@pytest.mark.parametrize("fn", ["perp_vs_quarterly_basis", "funding_call_hedged", "trend_funding_filter", "cme_basis_spike",
                                "cme_cash_and_carry", "perp_funding_carry", "basis_crash_predictor", "funding_sentiment"])
def test_every_harness_has_a_rule5_docstring(fn):
    assert "house rule 5" in " ".join(getattr(cy, fn).__doc__.split())
