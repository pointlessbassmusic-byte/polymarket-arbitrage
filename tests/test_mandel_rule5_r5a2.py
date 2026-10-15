"""House rule 5, round 2, in batch4_fomc and batch4_vx, on synthetic data: below the trial's min_n a failing criterion
counts only when its bound at the pass's OWN confidence lies wholly on the wrong side. A one-sided 95% pass is mirrored
by the one-sided 95% bound on the other side from the same draws, not by the two-sided 95% interval (a one-sided 97.5%
bound). Each fixture here is a case the two-sided interval left undecided and the same-confidence mirror decides.
At or above min_n nothing changes. No archive, no network."""

import numpy as np
import pytest

from mandel.experiments import batch4_fomc as fm
from mandel.experiments import batch4_vx as vx

from tests.test_mandel_batch4_fomc import _drift_setup
from tests.test_mandel_batch4_vx import _flat_index, _vxx
from tests.test_mandel_rule5_r5a import _mm, _weeks

NB = 300


def _judged(rep, name):
    """The rule-5 judgement of criterion ``name`` (label suffix stripped) as (label, ok)."""
    for label, ok in rep["rule5"]["criteria"]:
        if label.split(" (")[0] == name:
            return label, ok
    raise KeyError(name)


def test_mirror_rejects():
    assert fm._mirror_rejects(0.0499) and not fm._mirror_rejects(0.05) and not fm._mirror_rejects(None)


# --------------------------------------------------------------------------------------- T-341 statement day --

def _statement(mu, seed, **kw):
    days, c, ev = _drift_setup(mu, seed=seed, start="2010-01-04")       # 137 statement days, below min_n 200
    return fm.statement_day_effect(days, c, ev, start="2010-01-01", n_boot=NB, **kw)


def test_statement_day_p_row_is_decisive_by_its_one_sided_mirror():
    rep = _statement(-0.002, 5)
    g = rep["net"]
    assert rep["n"] < 200 and g["p_greater"] >= 0.05
    assert g["p_less"] < 0.05                                       # the one-sided 95% bound lies below 0 ...
    assert g["ci"][1] > 0 and not fm._ci_at_or_below(g["ci"], 0.0)  # ... while the two-sided (97.5%) upper end is above it
    label, ok = _judged(rep, "block-bootstrap p < 0.05")
    assert ok is False and label.endswith("(fails decisively below min_n)")
    assert "block-bootstrap p < 0.05" in rep["rule5"]["decisive_failures"]
    assert rep["verdict"] == "not_supported"
    assert rep["reason"].startswith(f"only {rep['n']} statement days (min_n 200); mirror p (H0 diff >= 0) {g['p_less']:.4f}")
    assert "the mirror one-sided test from the same draws rejecting at 5%" in rep["reason"]


def test_statement_day_at_or_above_min_n_unchanged():
    rep = _statement(-0.002, 5, min_n=100)
    assert "rule5" not in rep and "sub_ci_bps" not in rep and "mirror p" not in rep["reason"]
    assert rep["verdict"] == "not_supported" and "house rule 5" not in rep["reason"]


# ---------------------------------------------------------------------------------------- T-342 cycle weeks --

def test_even_weeks_p_row_is_decisive_by_its_one_sided_mirror():
    rep = _weeks(-0.0008, 5)                                        # 1,285 cycle days, below min_n 1500
    g = rep["net"]
    assert rep["n"] < 1500 and g["p_less"] < 0.05 and g["ci"][1] > 0
    label, ok = _judged(rep, "block-bootstrap p < 0.05")
    assert ok is False and label.endswith("(fails decisively below min_n)")
    assert "block-bootstrap p < 0.05" in rep["rule5"]["decisive_failures"]
    assert _judged(rep, "random-offset placebo p < 0.05")[1] in (True, None)   # the placebo p still never decides
    assert rep["reason"].startswith(f"only {rep['n']} cycle days (min_n 1500); mirror p (H0 diff >= 0) {g['p_less']:.4f}")


# -------------------------------------------------------------------------------------- T-361 monetary momentum --

def _mm_run(drift, seed, base, **kw):
    """``tests.test_mandel_rule5_r5a._mm`` (2 of every 5 meetings are surprises, 107 enter the gap, below min_n 120),
    with keyword arguments passed through so the same sample can be re-run with another min_n."""
    from tests.test_mandel_batch4_fomc import _closes, _days, _events
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
    return fm.monetary_momentum(days, _closes(r), dgs2, ev, n_perm=1000, n_boot=NB, **kw)


def test_monetary_momentum_permutation_row_is_decisive_by_its_lower_tail_mirror():
    rep = _mm_run(-0.0004, 1, 0.0002)
    assert rep == _mm(-0.0004, 1, 0.0002)                           # the round-1 fixture builder, unchanged
    cost_arm = 2 * 2.0 / 1e4
    assert rep["n"] == 107 and rep["permutation_p"] >= 0.05
    assert rep["gap_ci_net_pp"][1] / 100 + 2 * cost_arm > 0         # the gross-gap two-sided (97.5%) upper end is above 0
    label, ok = _judged(rep, "permutation p < 0.05")
    assert ok is False and label.endswith("(fails decisively below min_n)")
    assert "permutation p < 0.05" in rep["rule5"]["decisive_failures"]
    p_lo = rep["permutation_p_lower"]
    assert p_lo < 0.05
    # the mirror comes from the same 1,000 permutation draws: with no ties the two tails add to (n_perm + 2) / (n_perm + 1)
    assert rep["permutation_p"] + p_lo == pytest.approx(1002 / 1001, abs=2 / 1001)
    assert rep["reason"].startswith(f"only {rep['n']} expansionary+contractionary meetings (min_n 120); lower-tail "
                                    f"permutation p (H1 gap < 0) {p_lo:.4f}")


def test_monetary_momentum_at_or_above_min_n_unchanged():
    below, at = _mm_run(-0.0004, 1, 0.0002), _mm_run(-0.0004, 1, 0.0002, min_n=100)
    assert "rule5" not in at and "permutation_p_lower" not in at and "house rule 5" not in at["reason"]
    assert at["permutation_p"] == below["permutation_p"] and at["verdict"] == "not_supported"


# ---------------------------------------------------------------------------------------------- T-242 VXX decay --

def _decay(mu, seed, **kw):
    d, c = _vxx(700, mu, seed=seed)                                  # 33 cycles, below min_n 80
    return vx.vxx_decay(d, c, _flat_index(d, 15.0), _flat_index(d, 18.0), n_boot=400, n_place=50, **kw)


@pytest.mark.parametrize("mu,seed", [(-0.0008, 8), (-0.0007, 4)])
def test_vxx_decay_one_sided_lower_bound_decides(mu, seed):
    rep = _decay(mu, seed)
    assert rep["n"] == 33 and rep["ub95"] >= -0.03                  # the pass fails
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["rule5"]["decisive_failures"] == [
        "one-sided 95% studentized block-3 bootstrap upper bound of the conditional mean < -0.03"]
    lb = rep["rule5"]["lb95"]
    assert rep["ci95"][0] < -0.03 <= lb                              # one-sided 95% lower bound at or above -3%, 97.5% not
    assert ("fails decisively below min_n" in rep["reason"]
            and f"its one-sided 95% lower bound ({vx._pc(lb)}, the mirror of the one-sided 95% upper-bound pass" in rep["reason"])


def test_vxx_decay_at_or_above_min_n_unchanged():
    rep = _decay(-0.0008, 8, min_n=20)
    assert rep["verdict"] == "not_supported" and "rule5" not in rep and "house rule 5" not in rep["reason"]
    assert "lb95" not in rep and "one-sided 95% lower bound" not in rep["reason"]
    assert rep["criteria"][0] == ("n >= 20 non-overlapping conditional cycles (min_n)", True)


def test_vx_calendar_rule5_wording_unchanged():
    rows = [("c", False, True)]
    assert "its 95% CI wholly on the wrong side of the claimed bound (house rule 5)" in vx._rule5_note(rows, 5, 10, "obs")
    assert vx._rule5_note(rows, 10, 10, "obs") == ""
