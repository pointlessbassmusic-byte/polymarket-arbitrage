"""Rule-5 round-2 follow-ups in batch4_ohlc, on synthetic data (no archive, no network):

* T-421 spread_shock keeps its pre-rule-5 early return at or above min_events: with fewer than two shock days (reachable
  only when min_events <= 1) it returns the old _decide([]) result instead of running the regression or raising
  walk_forward_splits' ValueError; below min_events the rule-5 'too few' return is unchanged.
* the twin_reversion docstring states rule 5 below min_n.
* rule-5 reason text counts whole resampling units: ibs_reversal passes whole blocks and _upper_dec never rounds a
  fractional unit count up past the >= 4 gate; decisions do not change.
"""

import re
import warnings

import pytest

from mandel.experiments import batch4_ohlc as ob

from tests.test_mandel_batch4_ohlc import _ibs_bars, _shock_bars

NB = 200
SHOCK = 80 + 40 * 11            # a planted shock day of _shock_bars (shocks every 40 days from day 80)


@pytest.fixture(scope="module")
def shock_bars():
    return _shock_bars(0.0)


def _one_shock(shock_bars, before, after, **kw):
    days, H, L, C, vix = shock_bars
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return ob.spread_shock(days, H, L, C, C, vix, start=days[SHOCK - before], end=days[SHOCK + after], n_boot=NB, **kw)


# ---------------------------------------------------------------------------- T-421: unchanged at or above min_n --

@pytest.mark.parametrize("min_events", [0, 1])
def test_spread_shock_single_shock_day_at_min_events_keeps_the_old_early_return(shock_bars, min_events):
    rep = _one_shock(shock_bars, 25, 14, min_events=min_events)
    assert rep["n_shock_days"] == 1 and rep["n"] == 1 and rep["n"] >= min_events
    v, why = ob._decide([], 1, min_events, "non-overlapping shock events")
    assert (v, why) == ("supported", "all criteria pass")                  # the pre-rule-5 result
    assert rep["verdict"] == v and rep["reason"] == f"CS spread shock: 1 non-overlapping events — {why}"
    assert "coef_shock" not in rep and "rule5" not in rep                   # no regression ran, rule 5 not applied


def test_spread_shock_no_shock_days_at_min_events_zero_keeps_the_old_early_return(shock_bars):
    days, H, L, C, vix = shock_bars
    rep = ob.spread_shock(days, H, L, C, C, vix, z_thr=1e9, min_events=0, n_boot=NB)
    assert rep["n_shock_days"] == 0 and rep["n"] == 0
    assert rep["verdict"] == "supported" and rep["reason"] == "CS spread shock: 0 non-overlapping events — all criteria pass"
    assert "coef_shock" not in rep and "rule5" not in rep


@pytest.mark.parametrize("half", [2, 5, 8])
def test_spread_shock_short_window_at_min_events_returns_early_instead_of_raising(shock_bars, half):
    # a window too short for the walk-forward split: the old code returned before splitting, so it must not raise now
    rep = _one_shock(shock_bars, half, half, min_events=1)
    assert rep["n_rows"] < 20 and rep["n_shock_days"] == 1
    assert rep["verdict"] == "supported" and rep["reason"] == "CS spread shock: 1 non-overlapping events — all criteria pass"


def test_spread_shock_below_min_events_with_one_shock_day_is_still_rule5_too_few(shock_bars):
    rep = _one_shock(shock_bars, 25, 14, min_events=60)
    assert rep["n_shock_days"] == 1 and rep["verdict"] == "inconclusive"
    assert "too few for the shock regression" in rep["reason"] and "house rule 5" in rep["reason"]
    assert "all criteria pass" not in rep["reason"] and "coef_shock" not in rep


def test_spread_shock_with_two_or_more_shock_days_still_runs_the_regression(shock_bars):
    rep = _one_shock(shock_bars, 25, 54, min_events=1)                      # two planted shocks in the window
    assert rep["n_shock_days"] >= 2 and "coef_shock" in rep


# ------------------------------------------------------------------------------- T-324: docstring states rule 5 --

def test_twin_reversion_docstring_states_rule5_below_min_n():
    doc = " ".join(ob.twin_reversion.__doc__.split())
    assert "below it the verdict is inconclusive" not in doc
    assert "house rule 5 applies" in doc and "never supported" in doc and "not_supported" in doc
    assert "any other failure inconclusive" in doc and "statistics are still reported" in doc


# ---------------------------------------------------------------------- whole resampling units in reason text --

def test_upper_dec_prints_whole_units_never_rounded_up_past_the_gate():
    f = lambda v: f"{v:+.2f}"
    dec, txt = ob._upper_dec(-1.0, 0.0, f, 50, 75 / 20)                     # 3.75 units: refused, printed as 3
    assert dec is False and txt == "95% interval on 50 observations in 3 resampling units, too few to decide"
    assert "in 3 resampling units" in ob._upper_dec(-1.0, 0.0, f, 50, 3.95)[1]
    assert ob._upper_dec(-1.0, 0.0, f, 50, 3)[1] == "95% interval on 50 observations in 3 resampling units, too few to decide"
    assert ob._upper_dec(-1.0, 0.0, f, 7, 10)[1] == "95% interval on 7 observations in 10 resampling units, too few to decide"
    assert "in nan resampling units" in ob._upper_dec(-1.0, 0.0, f, 50, float("nan"))[1]
    assert ob._upper_dec(-1.0, 0.0, f, 50, 4.0)[0] is True                   # 4 units decide


def test_whole_units_gate_matches_the_fractional_gate():
    for mb in (5, 20, 21, 20.0):
        for n in range(1, 500):
            assert ob._resolvable(8, n / mb) == ob._resolvable(8, int(n // mb)), (n, mb)


@pytest.fixture(scope="module")
def ibs_bars():
    return _ibs_bars(0.0)


def _ibs(ibs_bars, n):
    days, H, L, C = ibs_bars
    return ob.ibs_reversal(days, H, L, C, C, start=days[100], end=days[100 + n], n_boot=NB)


@pytest.mark.parametrize("n", [70, 75, 79])
def test_ibs_reversal_reason_counts_whole_blocks_below_four(ibs_bars, n):
    rep = _ibs(ibs_bars, n)
    assert rep["n"] == n and rep["verdict"] == "inconclusive" and "house rule 5" in rep["reason"]
    units = re.findall(r"stationary-bootstrap 95% CI on \d+ observations in (\S+) resampling units, too few to decide", rep["reason"])
    assert units == ["3"], rep["reason"]                                    # 3.5..3.95 blocks of 20: refused, and said so
    assert "in 4 resampling units, too few" not in rep["reason"]
    assert rep["rule5"]["criteria"][0][1] is None and rep["rule5"]["decisive_failures"] == []


def test_ibs_reversal_four_whole_blocks_decide(ibs_bars):
    rep = _ibs(ibs_bars, 80)
    assert rep["n"] == 80 and "house rule 5" in rep["reason"]
    assert "resampling units, too few to decide" not in rep["rule5"]["criteria"][0][0]
    assert "upper end of the stationary-bootstrap 95% CI" in rep["rule5"]["criteria"][0][0], rep["rule5"]["criteria"][0]
