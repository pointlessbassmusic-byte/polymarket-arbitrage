"""batch4_fomc and batch4_vx, house rule 10 (no arbitrary grid phase). Synthetic data only: no archive, no network.

T-242 (vxx_decay) rested on one non-overlapping scan of 21-day VXX cycles started on the first day. The claim names no
entry calendar, so the primary statistic is now pooled over every qualifying daily entry (overlapping 21-day holds,
studentized circular block bootstrap with blocks of 63 entries = 3 cycles, >= 2 x the hold): the pass (one-sided 95%
upper bound < -3%) and, below min_n, the decisive failure (one-sided 95% lower bound >= -3%) both read the pooled
bootstrap. n stays in cycles: the maximal non-overlapping set (the sequential scan from the first day). The reason
reports each start offset's sequential scan and each fixed 21-session grid phase, their ranges and how many pass.

The rule-5 cases below replace the seed-tuned ones in test_mandel_rule5_r5a2 (written for the single-scan statistic).

Unaffected (pinned by invariance tests at the end): T-160 is a daily series on the VX expiry calendar; the FOMC
harnesses are day-flagged daily series (T-214, T-215, T-221, T-341), an event study on fixed decision days (T-273),
cycle weeks counted from the scheduled statement days (T-342) and 15-day holds from each statement's t+2 close (T-361)."""

import math

import numpy as np
import pytest

from mandel.experiments import batch4_fomc as fm
from mandel.experiments import batch4_vx as vx

from tests.test_mandel_batch4_fomc import _closes, _days, _events, _mm_setup
from tests.test_mandel_batch4_vx import NB, FakeArchive, _bdays, _flat_index, _idx_rows, _px_rows, _vxx

POOLED_ROW = "one-sided 95% studentized block-63 bootstrap upper bound of the pooled conditional mean < -0.03"


def _pooled(days, closes, vix, vix3m, threshold=1.10, horizon=21, lag=1):
    return vx.conditional_cycles(days, closes, vx.ratio_series(vix3m, vix), threshold, horizon, lag, overlapping=True)


def _runs_ratio(days, seed=0, p_on=0.08, p_off=0.12):
    """VIX/VIX3M levels whose VIX3M/VIX > 1.10 state comes in runs (a two-state Markov chain)."""
    rng = np.random.default_rng(seed); on = False; v3 = {}
    for d in days:
        on = (rng.random() > p_off) if on else (rng.random() < p_on)
        v3[d] = 18.0 if on else 15.0
    return _flat_index(days, 15.0), v3


# ------------------------------------------------------------------------------------------ the cycle samplers --

def test_conditional_cycles_offset_and_overlapping_entries():
    days = _bdays("2020-01-01", 120)
    closes = np.linspace(100, 50, 120)
    ratio = {d: 1.0 for d in days}
    ratio[days[10]] = 1.2; ratio[days[20]] = 1.2; ratio[days[40]] = 1.2
    assert vx.conditional_cycles(days, closes, ratio, 1.10, 21, 1)["idx"] == [11, 41]          # unchanged default
    assert vx.conditional_cycles(days, closes, ratio, 1.10, 21, 1, overlapping=True)["idx"] == [11, 21, 41]
    assert vx.conditional_cycles(days, closes, ratio, 1.10, 21, 1, offset=15)["idx"] == [21]   # scan starts at day 16
    every = vx.conditional_cycles(days, closes, ratio, None, 21, 1, overlapping=True)
    assert every["idx"] == list(range(1, 120 - 21))
    assert every["logret"][3] == pytest.approx(math.log(closes[25] / closes[4]))


def test_offset_zero_scan_is_the_maximal_non_overlapping_set():
    days, closes = _vxx(1500, -0.002, seed=3)
    vix, v3 = _runs_ratio(days, seed=5)
    ratio = vx.ratio_series(v3, vix)
    n0 = vx.conditional_cycles(days, closes, ratio, 1.10, 21, 1)
    counts = [len(vx.conditional_cycles(days, closes, ratio, 1.10, 21, 1, offset=p)["idx"]) for p in range(21)]
    assert len(n0["idx"]) == counts[0] == max(counts) and min(counts) < max(counts)   # the phase changes the count ...
    assert np.all(np.diff(n0["idx"]) >= 21)                                          # ... offset 0 is the maximum


def test_grid_phases_partition_the_pooled_entries():
    days, closes = _vxx(1200, -0.002, seed=4)
    vix, v3 = _runs_ratio(days, seed=6)
    ratio = vx.ratio_series(v3, vix)
    phases = np.concatenate([vx.grid_cycles(days, closes, ratio, 1.10, p, 21, 1) for p in range(21)])
    pooled = _pooled(days, closes, vix, v3)["logret"]
    assert len(phases) == len(pooled) and np.allclose(np.sort(phases), np.sort(pooled))


# --------------------------------------------------------------------------------- T-242: the pooled primary --

def test_vxx_decay_primary_is_the_pooled_statistic():
    days, closes = _vxx(2000, -0.003, seed=2)
    vix, v3 = _runs_ratio(days, seed=1, p_on=0.2, p_off=0.05)
    rep = vx.vxx_decay(days, closes, vix, v3, n_boot=NB, n_place=50)
    pool = _pooled(days, closes, vix, v3)
    st = vx.stud_mean(pool["logret"], 63, NB, 0)
    assert rep["n_pooled_entries"] == len(pool["logret"]) > rep["n"] and rep["pooled_block"] == 63
    assert rep["mean_logret"] == pytest.approx(pool["logret"].mean())
    assert rep["ub95"] == pytest.approx(st["ub95"]) and rep["ci95"] == pytest.approx(st["ci95"])
    assert rep["n"] == len(vx.conditional_cycles(days, closes, vx.ratio_series(v3, vix), 1.10, 21, 1)["idx"]) >= 80
    r10 = rep["rule10"]
    for kind in ("sequential_offsets", "grid_phases"):
        rows = r10[kind]["offsets"]
        assert len(rows) == 21 and r10[kind]["n_pass"] == sum(r["pass"] for r in rows)
        assert r10[kind]["ub95_range"] == pytest.approx([min(r["ub95"] for r in rows), max(r["ub95"] for r in rows)])
    assert rep["verdict"] == "supported" and rep["reason"].endswith("all criteria pass")
    assert "rule 10: the claim names no entry calendar" in rep["reason"]
    assert f"{r10['sequential_offsets']['n_pass']}/21 offsets pass" in rep["reason"]
    assert f"{r10['grid_phases']['n_pass']}/21 phases pass" in rep["reason"]


def _pulses(n=2700, period=30, run=5, drop=-0.10, sd=0.002, seed=0):
    """VIX3M/VIX > 1.10 for ``run`` days every ``period``; VXX drops 10% on the return two days after each run starts,
    so only the entry on the run's first qualifying close holds the drop."""
    rng = np.random.default_rng(seed)
    days = _bdays("2015-01-05", n)
    lr = sd * rng.standard_normal(n); sig = set()
    for s in range(30, n - 30, period):
        sig.update(range(s, s + run)); lr[s + 2] += drop
    return days, 100 * np.exp(np.cumsum(lr)), _flat_index(days, 15.0), {d: (18.0 if i in sig else 15.0) for i, d in enumerate(days)}


def test_vxx_decay_verdict_reads_the_pooled_entries_not_the_first_day_scan():
    """Regression: the scan from the first day (the pre-rule-10 primary) enters only on each run's first close and
    passes on every start offset; the claim's conditional mean over every qualifying entry is about -2%, so it fails."""
    days, closes, vix, v3 = _pulses()
    seq = vx.conditional_cycles(days, closes, vx.ratio_series(v3, vix), 1.10, 21, 1)["logret"]
    assert len(seq) >= 80 and vx.stud_mean(seq, 3, NB, 0)["ub95"] < -0.09          # the old statistic: a clear pass
    rep = vx.vxx_decay(days, closes, vix, v3, n_boot=NB, n_place=50)
    assert rep["n"] == len(seq) and rep["n_pooled_entries"] == 5 * len(seq)
    assert rep["mean_logret"] == pytest.approx(-0.02, abs=0.003) and rep["ub95"] > -0.03
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule10"]["sequential_offsets"]["n_pass"] == 21
    assert 0 < rep["rule10"]["grid_phases"]["n_pass"] < 21
    assert "21/21 offsets pass" in rep["reason"] and "rule5" not in rep


# ------------------------------------------------------------------------------- T-242: rule 5 on the pooled bound --

def _decay(mu, seed, **kw):
    d, c = _vxx(700, mu, seed=seed)                                    # 33 cycles, below min_n 80
    return d, c, vx.vxx_decay(d, c, _flat_index(d, 15.0), _flat_index(d, 18.0), n_boot=400, n_place=50, **kw)


@pytest.mark.parametrize("mu,seed", [(-0.0007, 8), (-0.0007, 22)])
def test_vxx_decay_pooled_one_sided_lower_bound_decides(mu, seed):
    d, c, rep = _decay(mu, seed)
    lb = rep["rule5"]["lb95"]
    st = vx.stud_mean(_pooled(d, c, _flat_index(d, 15.0), _flat_index(d, 18.0))["logret"], 63, 400, 0)
    assert rep["n"] == 33 and lb == pytest.approx(st["lb95"]) and rep["ub95"] >= -0.03
    assert rep["ci95"][0] < -0.03 <= lb                               # one-sided 95% at or above -3%, 97.5% not
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == [POOLED_ROW]
    assert f"its one-sided 95% lower bound ({vx._pc(lb)}, the mirror of the one-sided 95% upper-bound pass" in rep["reason"]


def test_vxx_decay_pooled_failure_with_lower_bound_below_the_bound_is_undecided():
    _, _, rep = _decay(-0.0008, 8)                 # decisive under the single-scan statistic, not under the pooled one
    assert rep["rule5"]["lb95"] < -0.03 <= rep["ub95"]
    assert rep["verdict"] == "inconclusive" and rep["rule5"]["decisive_failures"] == []
    assert (POOLED_ROW + " (fails, not decisively, below min_n: undecided)", None) in rep["criteria"]


def test_vxx_decay_at_or_above_min_n_has_no_rule5_keys():
    _, _, rep = _decay(-0.0007, 8, min_n=20)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]
    assert rep["criteria"] == [("n >= 20 non-overlapping conditional cycles (min_n)", True), (POOLED_ROW, False)]


# --------------------------------------------------------------------------------------------- T-242 harness --

def test_harness_controls_run_on_pooled_entries():
    vd, closes = _vxx(1300, -0.004, seed=2, start="2015-01-05")
    vix, v3 = _runs_ratio(vd, seed=3, p_on=0.3, p_off=0.05)
    rows = lambda ser: [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(v)}} for d, v in ser.items()]
    ar = FakeArchive({vx.VXX_BUNDLE: _px_rows(vd, closes), vx.VIX_BUNDLE: rows(vix), vx.VIX3M_BUNDLE: rows(v3),
                      vx.VVIX_BUNDLE: _idx_rows(vd, 100.0), vx.DTB3_BUNDLE: _idx_rows(vd, 2.0)})
    stat, n, v, reason = vx.vx_vxx_contango_decay(ar)
    pool = _pooled(vd, closes, vix, v3)
    assert n == stat["n"] and stat["n_pooled_entries"] == len(pool["idx"])
    hist_ok = sum(1 for i in pool["idx"] if i - 252 - 21 >= 0)
    assert stat["model_priced_put_spread"]["n"] == hist_ok > n          # every qualifying entry with a VVIX history
    assert stat["unconditional_n_entries"] == len(vd) - 22 and stat["lag0"]["n_entries"] > 0
    assert stat["walk_forward"]["n_entries"] >= stat["walk_forward"]["n"]
    months = [d[:7] for d, _ in stat["worst_months"]]
    assert len(months) == len(set(months)) == 5                          # one row per entry month
    assert "Controls (pooled daily entries)" in reason and f"n={hist_ok} pooled entries" in reason
    assert v == stat["verdict"] and reason == stat["reason"]


# ------------------------------------------------------------------------------- unaffected harnesses (rule 10) --

def test_t160_daily_series_has_no_phase():
    """T-160 marks every trading day on the VX expiry calendar: starting the curve later changes nothing after the
    first roll that both runs share."""
    from tests.test_mandel_batch4_vx import _vx_values
    days, vals = _vx_values(300, c=1.0, noise=0.05, seed=3)
    curve = vx.vx_curve(vals); ratio = {d: 0.9 for d in days}
    full = vx.calendar_pnl(curve, ratio)
    late = vx.calendar_pnl({d: v for d, v in curve.items() if d >= days[40]}, ratio)
    k = full["day"].index(late["day"][0]); roll = next(i for i, m in enumerate(late["m1"]) if m != late["m1"][0]) + 1
    assert np.allclose(full["net"][k + roll:], late["net"][roll:])


def test_t342_cycle_weeks_are_anchored_on_statement_days():
    days = _days("2000-01-03", "2006-12-29"); ev = _events(days, 33, first=7)
    w = fm.fomc_cycle_weeks(days, ev)
    for k in (5, 13, 30):
        wk = fm.fomc_cycle_weeks(days[k:], ev)
        first = days.index(next(e for e in ev if e >= days[k])) - 1        # day -1 of the first cycle in the cut series
        assert np.array_equal(w[first:], wk[first - k:])


def test_t361_meeting_holds_do_not_depend_on_where_the_series_starts():
    days, c, dgs2, ev = _mm_setup(0.002)
    a = fm.monetary_momentum(days, c, dgs2, ev, start="1996-01-01", n_perm=500, n_boot=100)
    k = days.index("1995-06-01") if "1995-06-01" in days else 300
    b = fm.monetary_momentum(days[k:], c[k:], dgs2, ev, start="1996-01-01", n_perm=500, n_boot=100)
    for key in ("n", "n_expansionary", "n_contractionary", "gap_net_pp", "permutation_p", "arm_sharpe", "buy_hold_sharpe"):
        assert a[key] == pytest.approx(b[key]), key
    assert a["verdict"] == b["verdict"]


def test_fomc_module_states_rule10_does_not_bind():
    doc = fm.__doc__
    assert "House rule 10 (no arbitrary grid phase) does not bind here" in doc
    for t in ("T-214", "T-215", "T-221", "T-341", "T-273", "T-342", "T-361"):
        assert t in doc.split("House rule 10")[1]
