"""batch4_ohlc, rule-5 round 3 (r5d3) and rule 10 (no arbitrary grid phase). Synthetic data only: no archive, no network.

Rule 5 (below min_n, a one-sided p criterion fails decisively only at the pass's own confidence, from the same draws):
* T-348 overnight_intraday: 'p < 0.05 vs gap <= 3 bps' is decided by the studentized mirror p against gap >= 3 bps.
* T-421 spread_shock: 'p < 0.05 (H0 coefficient <= 0)' is decided by the centred mirror p against coefficient >= 0.
* T-304 breakout_vs_random: the Holm route is decided at 1 - 0.05/n_trials (n_trials x the opposite-tail p < 0.05).
At or above min_n the reports carry no new keys.

Rule 10: no harness in the module rests on a non-overlapping grid with an arbitrary start. T-216 is a calendar event study
(third Fridays vs other Fridays), T-332/T-333/T-348 are daily series, T-421's regression uses every overlapping daily row
and its event count is the maximal non-overlapping set, and T-304/T-324 trade a signal-driven rule whose trades do not
depend on the day the scan starts. The last tests pin those invariances."""

import math

import numpy as np

from mandel.experiments import batch4_ohlc as ob
from mandel.validation.backtest_eval import block_bootstrap_pvalue

from tests.test_mandel_batch4_ohlc import _days, _path, _shock_bars, _trend_assets, _twins
from tests.test_mandel_rule5_r5d import _revert_assets

P_ROW = "p < 0.05 vs gap <= 3 bps (studentized block-10 bootstrap)"
COEF_P_ROW = "p < 0.05 (H0 coefficient <= 0)"
DIFF_ROW = "mean difference > 0 with cluster-bootstrap 95% CI excluding 0"
TRIAL_ROW = "survives the 60-trial correction (DSR > 0.95 or Holm p < 0.05)"


def _row(rep, prefix):
    rows = [(name, ok) for name, ok in rep["rule5"]["criteria"] if name.startswith(prefix)]
    assert len(rows) == 1, rep["rule5"]
    return rows[0]


# ------------------------------------------------------------------------------- T-348 overnight vs intraday --

def _overnight(mu, seed=11):
    rng = np.random.default_rng(seed)
    night, day = rng.normal(mu, 0.005, 300), rng.normal(0, 0.008, 300)
    days = _days("2008-01-01", "2012-12-31")[:301]
    return days, *_path(night, day)


def test_overnight_p_row_fails_decisively_on_the_studentized_mirror():
    days, O, C = _overnight(-0.0005)
    rep = ob.overnight_intraday(days, O, C)
    assert rep["n"] == 300 and rep["gap_ci_bps"][1] > 3          # the two-sided 97.5% end does not decide ...
    assert rep["p_gap_le_threshold"] >= 0.05
    d = (O[1:] / C[:-1] - 1) - (C[1:] / O[1:] - 1)
    mirror = block_bootstrap_pvalue(np.full(300, 0.0003), d, n_boot=2000, block_len=10, seed=0)
    assert rep["p_gap_ge_threshold"] == mirror and mirror < 0.05   # ... the one-sided 95% studentized bound does
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == [P_ROW]
    name, ok = _row(rep, P_ROW)
    assert ok is False and "fails decisively below min_n" in name and "p vs gap >= 3 bps 0.027" in name
    assert _row(rep, "gap > 3 bps/day")[1] is None               # the point-estimate row still uses the 95% CI


def test_overnight_p_row_stays_undecided_when_the_mirror_p_is_not_below_005():
    rep = ob.overnight_intraday(*_overnight(-0.0002))
    assert rep["p_gap_le_threshold"] >= 0.05 and rep["p_gap_ge_threshold"] >= 0.05
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []
    name, ok = _row(rep, P_ROW)
    assert ok is None and "fails, not decisively" in name


def test_overnight_report_has_no_new_keys_at_min_n():
    rep = ob.overnight_intraday(*_overnight(-0.0005), min_n=300)
    assert "rule5" not in rep and "p_gap_ge_threshold" not in rep


# ------------------------------------------------------------------------------------ T-421 spread shock --

def _spread(drift):
    days, H, L, C, vix = _shock_bars(drift, 0)
    return ob.spread_shock(days, H, L, C, C, vix, start=days[3000], end=days[3900], n_boot=2000)


def test_spread_shock_p_row_fails_decisively_on_the_centred_mirror():
    rep = _spread(-0.001)
    assert rep["n"] == 23 and rep["coef_ci"][1] > 0               # the 97.5% percentile end is above 0 ...
    assert rep["p_coef_le0"] >= 0.05 and rep["p_coef_ge0"] < 0.05  # ... the one-sided 95% mirror is decisive
    assert abs(rep["p_coef_ge0"] - 0.0255) < 1e-3
    assert COEF_P_ROW in rep["rule5"]["decisive_failures"]
    name, ok = _row(rep, COEF_P_ROW)
    assert ok is False and "p vs coefficient >= 0 0.025" in name
    assert rep["verdict"] == "not_supported"


def test_spread_shock_p_row_stays_undecided_when_the_mirror_p_is_not_below_005():
    rep = _spread(0.0)
    assert rep["p_coef_le0"] >= 0.05 and rep["p_coef_ge0"] >= 0.05
    assert COEF_P_ROW not in rep["rule5"]["decisive_failures"]
    name, ok = _row(rep, COEF_P_ROW)
    assert ok is None and "fails, not decisively" in name
    assert rep["verdict"] == "inconclusive", rep["reason"]


def test_spread_shock_report_has_no_new_keys_at_min_events():
    days, H, L, C, vix = _shock_bars(0.0, seed=5)
    rep = ob.spread_shock(days, H, L, C, C, vix, n_boot=400)
    assert rep["n"] >= 60 and "rule5" not in rep and "p_coef_ge0" not in rep


# --------------------------------------------------------------------------------------- T-304 breakout --

def test_breakout_holm_route_undecided_when_the_ci_is_below_0_but_holm_p_cannot_reach_005():
    rep = ob.breakout_vs_random(_revert_assets(), n_random=100, n_boot=1000)
    assert rep["n"] < 150 and rep["ci"][1] <= 0
    assert 60 * rep["p_diff_ge0"] >= 0.05
    assert rep["rule5"]["decisive_failures"] == [DIFF_ROW]          # crit[0] still decides on the cluster CI
    name, ok = _row(rep, TRIAL_ROW)
    assert ok is None and "fails, not decisively" in name and "Holm route: 60 x p vs difference >= 0" in name
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_breakout_holm_route_decisive_at_one_minus_005_over_60():
    rep = ob.breakout_vs_random(_revert_assets(phi=0.95), n_random=100, n_boot=5000, min_n=500)
    assert 60 * rep["p_diff_ge0"] < 0.05
    assert rep["rule5"]["decisive_failures"] == [DIFF_ROW, TRIAL_ROW]
    name, ok = _row(rep, TRIAL_ROW)
    assert ok is False and "Holm route: 60 x p vs difference >= 0 = 0.012 < 0.05" in name


def test_breakout_holm_route_needs_both_routes():
    rep = ob.breakout_vs_random(_revert_assets(phi=0.95), n_random=100, n_boot=1000, min_n=500)
    assert 60 * rep["p_diff_ge0"] >= 0.05                          # 1000 draws cannot resolve p < 0.05/60
    assert _row(rep, TRIAL_ROW)[1] is None and rep["verdict"] == "not_supported"


def test_breakout_report_has_no_new_keys_at_min_n():
    rep = ob.breakout_vs_random(_revert_assets(), n_random=100, n_boot=1000, min_n=100)
    assert "rule5" not in rep and "p_diff_ge0" not in rep


# ------------------------------------------------------------------------------------ rule 10: no grid phase --

def test_twin_trades_do_not_depend_on_the_scan_start():
    days, a, b = _twins(0.9, seed=2)
    z = ob._trailing_z(np.log(np.asarray(a) / np.asarray(b)), 60, include_current=True)
    first = int(np.where(np.isfinite(z))[0][0]); last = len(z) - 1
    base = ob.twin_trades(z, first, last)
    assert len(base) > 50
    for k in range(1, 6):
        tr = ob.twin_trades(z, first + k, last)
        assert set(tr[1:]) <= set(base) and len(set(tr) ^ set(base)) <= 2


def test_donchian_trades_do_not_depend_on_the_series_start():
    a = _trend_assets(0.004, n_assets=2, seed=3)
    for nm, x in a.items():
        h, l, c = (np.asarray(x[k]) for k in ("high", "low", "close"))
        base, _ = ob.donchian_atr_trades(h, l, c)
        assert len(base) > 20
        for k in (1, 5, 20, 54):
            tr, _ = ob.donchian_atr_trades(h[k:], l[k:], c[k:])
            shifted = [(e + k, x_ + k) for e, x_ in tr]
            assert set(shifted[1:]) <= set(base) and len(set(base) ^ set(shifted)) <= 2, (nm, k)   # only the warm-up trade


def _max_spaced(t, gap):
    """Largest subset of sorted rows ``t`` with consecutive spacing >= gap (dynamic programme, not greedy)."""
    t = list(t); f = [0] * (len(t) + 1)
    for i in range(1, len(t) + 1):
        j = int(np.searchsorted(t, t[i - 1] - gap, side="right"))
        f[i] = max(f[i - 1], 1 + f[j])
    return f[-1]


def test_spread_shock_event_count_is_the_maximal_non_overlapping_set():
    days, H, L, C, vix = _shock_bars(0.0, seed=7)
    rng = np.random.default_rng(7)
    extra = np.sort(rng.choice(np.arange(200, len(C) - 40), 60, replace=False))   # irregular, clustered shocks
    H = H.copy(); L = L.copy()
    for s in extra:
        H[s - 1:s + 1] = C[s - 1:s + 1] * 1.02; L[s - 1:s + 1] = C[s - 1:s + 1] * 0.98
    rep = ob.spread_shock(days, H, L, C, C, vix, n_boot=100)
    S = ob.corwin_schultz(H, L, C); z = ob._trailing_z(S, 60)
    vd = sorted(vix); vv = np.array([vix[d] for d in vd]); v = vv[np.searchsorted(vd, days, side="right") - 1]
    dv = np.full(len(C), np.nan); dv[1:] = np.diff(v)
    R = np.full(len(C), np.nan); R[: len(C) - 21] = C[21:] / C[1: len(C) - 20] - 1
    m = np.isfinite(z) & np.isfinite(dv) & np.isfinite(R) & ob._range_mask(np.array(days), "2000-01-01", "2026-12-31")
    shock_rows = np.where(m & (np.nan_to_num(z) > 2.0))[0]
    assert rep["n_shock_days"] == len(shock_rows) > rep["n"]
    assert rep["n"] == _max_spaced(shock_rows, 20)                  # n_ev is a property of the shock set, not of a start phase
