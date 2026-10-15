"""House rule 5 in batch4_ohlc, on synthetic data: below the trial's min_n (in the claim's own units) a decisive failure (the
criterion's 95% interval wholly on the wrong side of the claimed bound) is not_supported, a non-decisive failure is
inconclusive, and a pass is inconclusive. At or above min_n every criterion is judged at face value. No archive, no network."""

import numpy as np
import pytest

from mandel.experiments import batch4_ohlc as ob

from tests.test_mandel_batch4_ohlc import (_days, _gap_path, _ibs_bars, _night_day, _opex_closes, _path, _shock_bars,
                                           _trend_assets, _twins)

NB = 400


def _decisive(rep, *names):
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"], rep["rule5"]
    for nm in names:
        assert nm in rep["rule5"]["decisive_failures"], rep["rule5"]
    assert "fails decisively below min_n" in rep["reason"] and "house rule 5" in rep["reason"]
    assert rep["rule5"]["criteria"][-1][1] is None and rep["rule5"]["criteria"][-1][0].startswith("n >= trial min_n")


def _undecided(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    assert "fails, not decisively, below min_n" in rep["reason"] and "house rule 5" in rep["reason"]
    assert not any(ok is False for _, ok in rep["rule5"]["criteria"])


def _pass_below(rep):
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == []
    crit = rep["rule5"]["criteria"]
    assert all(ok is True for _, ok in crit[:-1]) and crit[-1][1] is None, crit
    assert not any("below min_n" in name for name, _ in crit) and "house rule 5" in rep["reason"]


# ------------------------------------------------------------------------------------------------ the rule itself --

def test_rule5_keeps_decisive_failures_and_undecides_the_rest():
    rows = [("a", True, False, ""), ("b", False, False, "wide"), ("c", None, False, "")]
    v, why, crit = ob._rule5(rows, 10, 100, "trades")
    assert v == "inconclusive" and crit[1] == ("b (fails, not decisively, below min_n: wide; undecided)", None)
    assert crit[-1] == ("n >= trial min_n (10 of 100 trades)", None) and "house rule 5" in why
    v, why, crit = ob._rule5(rows[:1] + [("b", False, True, "CI below")], 10, 100, "trades")
    assert v == "not_supported" and crit[1] == ("b (fails decisively below min_n: CI below)", False)
    v, _, _ = ob._rule5(rows[:1], 10, 100, "trades")
    assert v == "inconclusive"                                   # a pass below min_n is never supported


def test_an_interval_decides_only_on_enough_observations_and_resampling_units():
    f = lambda v: f"{v:+.2f}"
    assert ob._upper_dec(-1.0, 0.0, f, 50, 10)[0] is True
    assert ob._upper_dec(-1.0, 0.0, f, 7, 10)[0] is False             # under 8 observations
    assert ob._upper_dec(-1.0, 0.0, f, 50, 1)[0] is False             # one block: a rotation of the data, no interval
    assert ob._upper_dec(1.0, 1.0, f, 50, 10, strict=True)[0] is False and ob._upper_dec(1.0, 1.0, f, 50, 10)[0] is True
    rng = np.random.default_rng(0)
    assert ob._dsr_dec(rng.normal(-0.01, 0.01, 300), 300)[0] is True
    assert ob._dsr_dec(rng.normal(0.0, 0.01, 300), 300)[0] is False
    assert ob._dsr_dec(rng.normal(-0.01, 0.01, 300), 5)[0] is False   # 5 claim units cannot bound the Sharpe


# ------------------------------------------------------------------------------------- T-348 overnight vs intraday --

def _night(mu):
    days = _days("2006-01-02", "2013-12-31")                          # ~2090 days: below min_n 3000, both halves present
    night, day = _night_day(len(days) - 1, mu, seed=3)
    return days, *_path(night, day)


def test_overnight_intraday_decisive_failure_below_min_n():
    rep = ob.overnight_intraday(*_night(-0.001), n_boot=NB)
    assert rep["n"] < 3000 and rep["gap_ci_bps"][1] <= 3
    _decisive(rep, "gap > 3 bps/day", "gap positive in both halves")


def test_overnight_intraday_non_decisive_failure_below_min_n():
    rep = ob.overnight_intraday(*_night(0.0002), n_boot=NB)
    assert rep["p_gap_le_threshold"] >= 0.05 and rep["gap_ci_bps"][1] > 3
    _undecided(rep)


def test_overnight_intraday_pass_below_min_n():
    rep = ob.overnight_intraday(*_night(0.002), n_boot=NB)
    _pass_below(rep)


def test_overnight_intraday_at_min_n_is_judged_at_face_value():
    rep = ob.overnight_intraday(*_night(0.0002), n_boot=NB, min_n=1000)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]


def test_overnight_intraday_too_few_days_inconclusive():
    days = _days("2020-01-01", "2020-01-08")
    night, day = _night_day(len(days) - 1, -0.01)
    rep = ob.overnight_intraday(days, *_path(night, day))
    assert rep["verdict"] == "inconclusive" and "too few" in rep["reason"] and "min_n" in rep["reason"]


# ------------------------------------------------------------------------------------------------ T-333 gap fade --

VARIANTS = [0.0, 0.01, 0.02, -0.01, 0.0, 0.01]


def _fade(beta, cost):
    days, O, C = _gap_path(beta, seed=1)
    return ob.gap_fade(days, O, C, start="2010-01-01", end="2012-12-31", split="2011-07-01", cost_rt=cost, n_boot=NB,
                       variant_sharpes=VARIANTS)


def test_gap_fade_decisive_failure_below_min_n():
    rep = _fade(0.0, 0.002)                                          # no reversal, 20 bps a round trip
    assert rep["n"] < 500 and rep["ci_bps"][1] <= 0
    _decisive(rep, "95% lower bound of mean net per trade > 0")


def test_gap_fade_non_decisive_failure_below_min_n():
    _undecided(_fade(0.0, 0.0002))


def test_gap_fade_pass_below_min_n():
    _pass_below(_fade(-0.5, 0.0002))


# ---------------------------------------------------------------------------------------------- T-332 IBS reversal --

def _ibs(effect, seed):
    days, H, L, C = _ibs_bars(effect, seed=seed)
    return ob.ibs_reversal(days, H, L, C, C, start="2010-01-01", end="2015-12-31", split="2013-01-01", n_boot=NB,
                           grid_sharpes=[0.01] * 12)


def test_ibs_decisive_failure_below_min_n():
    rep = _ibs(-0.004, 2)                                            # momentum after a low-IBS close, not reversal
    assert rep["n"] < 2000 and rep["ci_bps"][1] <= 2
    _decisive(rep, "95% lower bound of the difference > 2 bps")


def test_ibs_non_decisive_failure_below_min_n():
    _undecided(_ibs(0.0003, 3))


def test_ibs_pass_below_min_n():
    _pass_below(_ibs(0.004, 2))


# --------------------------------------------------------------------------------------- T-421 CS spread shocks --

def _shock(drift):
    days, H, L, C, vix = _shock_bars(drift, seed=1)
    return ob.spread_shock(days, H, L, C, C, vix, start="2019-01-01", n_boot=NB)


def test_spread_shock_decisive_failure_below_min_n():
    rep = _shock(-0.003)                                             # the forward return falls after a shock
    assert rep["n"] < 60 and rep["coef_ci"][1] < 0.01
    _decisive(rep, "shock coefficient >= 1 point", "p < 0.05 (H0 coefficient <= 0)")


def test_spread_shock_non_decisive_failure_below_min_n():
    _undecided(_shock(0.0))


def test_spread_shock_pass_below_min_n():
    _pass_below(_shock(0.002))


# --------------------------------------------------------------------------------------- T-304 Donchian breakout --

def _revert_assets(phi=0.98, n_assets=3, seed=0):
    """Mean-reverting prices: a breakout buys near a local high, so the rule trails matched random entries."""
    rng = np.random.default_rng(seed)
    days = _days("2000-01-03", "2015-12-31")
    out = {}
    for k in range(n_assets):
        x = np.zeros(len(days))
        for t in range(1, len(days)):
            x[t] = phi * x[t - 1] + rng.normal(0, 0.01)
        C = 100 * np.exp(x)
        out[f"R{k}"] = {"days": days, "high": C * 1.005, "low": C * 0.995, "close": C, "cost": 0.0005, "ppy": 252}
    return out


def _first(assets, k=3):
    return {name: assets[name] for name in list(assets)[:k]}


def test_breakout_decisive_failure_below_min_n():
    rep = ob.breakout_vs_random(_revert_assets(), n_random=100, n_boot=1000)
    assert rep["n"] < 150 and rep["ci"][1] <= 0
    _decisive(rep, "mean difference > 0 with cluster-bootstrap 95% CI excluding 0",
              "survives the 60-trial correction (DSR > 0.95 or Holm p < 0.05)")


def test_breakout_non_decisive_failure_below_min_n():
    _undecided(ob.breakout_vs_random(_first(_trend_assets(0.0, seed=6)), n_random=100, n_boot=1000))


def test_breakout_pass_below_min_n():
    _pass_below(ob.breakout_vs_random(_first(_trend_assets(0.004)), n_random=100, n_boot=1000))


# ------------------------------------------------------------------------------------------------ T-324 twin spread --

def test_twin_decisive_failure_below_min_n():
    rep = ob.twin_reversion(*_twins(1.0, seed=7), n_boot=1000)       # random-walk spread: the 8 bps cost is all that is left
    assert rep["n_trades"] < 1000 and rep["ci_bps"][1] <= 0
    _decisive(rep, "95% lower bound of mean net return per trade > 0")


def test_twin_non_decisive_failure_below_min_n():
    _undecided(ob.twin_reversion(*_twins(0.97), n_boot=1000))


def test_twin_pass_below_min_n():
    rep = ob.twin_reversion(*_twins(0.9), n_boot=1000)
    assert rep["n_trades"] < 1000
    _pass_below(rep)


# ---------------------------------------------------------------------------------------- T-216 opex MODEL-PRICED --

def _opex(opex_sd):
    days, C, vix = _opex_closes(opex_sd, seed=2)
    return ob.opex_straddle(days, C, vix, start="2012-01-01", n_boot=NB, n_perm=50)


def test_opex_decisive_failure_below_min_n():
    rep = _opex(0.02)                                                # opex Fridays move twice as much: the seller loses there
    assert rep["n"] < 300 and rep["ci_bps"][1] <= 0
    _decisive(rep, "difference > 0", "95% CI excludes 0")
    assert rep["as_worded_r0_no_dividend"]["verdict"] == "not_supported"


def test_opex_non_decisive_failure_below_min_n():
    _undecided(_opex(0.01))


def test_opex_pass_below_min_n():
    _pass_below(_opex(0.003))
