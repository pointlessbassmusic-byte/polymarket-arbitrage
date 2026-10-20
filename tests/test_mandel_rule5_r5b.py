"""House rule 5 in the batch-4 factor harnesses (mandel/experiments/batch4_fact.py), on synthetic data.

Below the trial's min_n the verdict can never be 'supported'; a failing criterion still counts when it fails decisively
(its interval lies wholly on the wrong side of the claimed bound) and any other failure is undecided, so the verdict is
inconclusive. At or above min_n every criterion is judged at face value, exactly as before."""

import numpy as np

from mandel.experiments import batch4_fact as bf
from mandel.experiments.underlying2 import _verdict
from tests.test_mandel_batch4_fact import SMALL_FAMILY, _bab_world, _bdays, _hedged_world, _industry_world, _months, _regime_factors, _size_world

RULE5 = "house rule 5"


def _exact(mu, sd, n, seed):
    """A series with sample mean exactly mu and sample sd exactly sd (keeps the planted cases off the knife edge)."""
    e = np.random.default_rng(seed).normal(0, 1, n)
    return mu + sd * (e - e.mean()) / e.std(ddof=1)


def _tail(rep):
    return rep["reason"].split(" — ", 1)[1]


# ------------------------------------------------------------------ the decision rule --

def test_decide_below_min_n_keeps_only_decisive_failures():
    dec = [("mean > 0", False, True, "upper 95% bound -1% <= 0"), ("DSR > 0.95", True, False, "")]
    v, why = bf._decide(dec, 50, 100, "months")
    assert v == "not_supported" and RULE5 in why
    assert "mean > 0 (fails decisively below min_n: upper 95% bound -1% <= 0)" in why
    v, why = bf._decide([("mean > 0", False, False, "upper 95% bound +1% > 0"), ("DSR > 0.95", True, False, "")], 50, 100, "months")
    assert v == "inconclusive" and "mean > 0 (fails, not decisively, below min_n: upper 95% bound +1% > 0; undecided)" in why
    assert "[criteria at face value: not_supported, failed: mean > 0]" in why
    v, why = bf._decide([("mean > 0", True, False, ""), ("DSR > 0.95", True, False, "")], 50, 100, "months")
    assert v == "inconclusive" and "n >= trial min_n (50 of 100 months)" in why        # a pass below min_n never confirms
    v, _ = bf._decide([("mean > 0", True, False, ""), ("QMJ", None, False, "")], 50, 100, "months")
    assert v == "inconclusive"


def test_decide_at_or_above_min_n_is_face_value():
    for rows in ([("mean > 0", False, False, "x"), ("DSR > 0.95", True, False, "")],
                 [("mean > 0", True, True, ""), ("DSR > 0.95", True, False, "")],
                 [("mean > 0", True, False, ""), ("QMJ", None, False, "")]):
        for n in (100, 150):
            assert bf._decide(rows, n, 100, "months") == _verdict([(">= 100 months", True)] + [(a, b) for a, b, _, _ in rows])


# --------------------------------------------------------------------- daily factor means --

def test_factor_mean_decisive_failure_below_min_n_is_not_supported():
    days = _bdays(2000)
    rep = bf.factor_mean_test(days, _exact(-0.0015, 0.006, 2000, 1), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=400)
    assert rep["n"] == 2000 and rep["ci_ann"][1] < 0
    assert rep["verdict"] == "not_supported" and RULE5 in rep["reason"]
    assert "lower 95% bound of the annualised mean > 0 (fails decisively below min_n" in rep["reason"]
    # the same data judged at a min_n it meets: face value, with the old reason format
    at = bf.factor_mean_test(days, _exact(-0.0015, 0.006, 2000, 1), days[0], days[-1], 2000, SMALL_FAMILY, n_boot=400)
    assert at["verdict"] == "not_supported" and RULE5 not in at["reason"]
    assert _tail(at) == "failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95"


def test_factor_mean_non_decisive_failure_and_pass_below_min_n_are_inconclusive():
    days = _bdays(2000)
    weak = bf.factor_mean_test(days, _exact(0.0002, 0.006, 2000, 2), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=400)
    assert weak["ci_ann"][0] < 0 < weak["ci_ann"][1]                              # fails, but the interval straddles 0
    assert weak["verdict"] == "inconclusive" and "fails, not decisively, below min_n" in weak["reason"]
    assert "[criteria at face value: not_supported" in weak["reason"]
    strong = bf.factor_mean_test(days, _exact(0.0012, 0.006, 2000, 3), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=400)
    assert strong["verdict"] == "inconclusive" and "[criteria at face value: supported, all criteria pass]" in strong["reason"]


def test_family_dsr_decisiveness_uses_the_benchmark_at_min_n():
    # 500 zero-Sharpe days: against the 1/(T-1) floor at T = 500 the DSR is below 0.05, but the trial's benchmark at
    # min_n (floor 1/(8000-1)) is far lower, so the DSR failure is not decisive and the verdict stays inconclusive
    days = _bdays(500)
    rep = bf.factor_mean_test(days, _exact(0.0, 0.006, 500, 4), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=300)
    assert rep["family"]["dsr"] <= 0.05
    assert rep["verdict"] == "inconclusive"
    assert "family-wide DSR > 0.95 (fails, not decisively, below min_n: DSR" in rep["reason"]


# ---------------------------------------------------------------------- hedged / size / BAB --

def test_hedged_alpha_early_return_now_computes_the_family_dsr():
    # fewer than 12 months: the alpha regression is not estimable (undecided), but the daily family DSR is, and it fails
    # decisively for a book that loses every day; this used to return 'inconclusive' without computing anything
    names = bf.FF5 + ["UMD"]
    days, rq, rs, rf, ms, F = _hedged_world(-0.003, 11)
    k = 300
    rep = bf.hedged_alpha_test(days[:k], rq[:k], rs[:k], rf[:k], ms, F, names, start=days[0], end=days[k - 1], qmj_loading=0.7,
                               family_sharpes=SMALL_FAMILY, n_boot=50)
    assert rep["n"] < 12 and rep["family"] is not None
    assert rep["verdict"] == "not_supported" and "family-wide DSR > 0.95 (fails decisively below min_n" in rep["reason"]
    assert "FF5+UMD alpha NW t >= 2.0 (not estimated" in rep["reason"]
    few = bf.hedged_alpha_test(days[:k], rq[:k], rs[:k], rf[:k], ms, F, names, start=days[0], end=days[k - 1], qmj_loading=0.7, n_boot=50)
    assert few["verdict"] == "inconclusive"                                       # no family: nothing can fail


def test_hedged_alpha_below_min_n_decisive_and_not():
    names = bf.FF5 + ["UMD"]
    days, rq, rs, rf, ms, F = _hedged_world(-0.003, 11)
    k = 1500
    bad = bf.hedged_alpha_test(days[:k], rq[:k], rs[:k], rf[:k], ms, F, names, start=days[0], end=days[k - 1], qmj_loading=0.7,
                               family_sharpes=SMALL_FAMILY, n_boot=50)
    assert bad["n"] < 150 and bad["alpha_t"] <= -2
    assert bad["verdict"] == "not_supported" and "FF5+UMD alpha NW t >= 2.0 (fails decisively below min_n" in bad["reason"]
    days, rq, rs, rf, ms, F = _hedged_world(0.0, 12)
    null = bf.hedged_alpha_test(days[:k], rq[:k], rs[:k], rf[:k], ms, F, names, start=days[0], end=days[k - 1], qmj_loading=0.7,
                                family_sharpes=SMALL_FAMILY, n_boot=50)
    assert -2 < null["alpha_t"] < 2 and null["verdict"] == "inconclusive"


def test_size_spread_decisive_failure_below_min_n():
    days, rl, rs, ms, F = _size_world(-0.0005, -0.5, 13)
    rep = bf.size_spread_test(days[:3000], rl[:3000], rs[:3000], ms, F, start=days[0], end=days[2999], family_sharpes=SMALL_FAMILY, n_boot=400)
    assert rep["n"] == 3000 and rep["verdict"] == "not_supported"
    assert "lower 95% bound of the annualised mean > 0 (fails decisively below min_n" in rep["reason"]
    assert "RMW loading significantly positive (NW t > 1.96) (fails decisively below min_n" in rep["reason"]


def test_bab_spread_rule5(monkeypatch):
    days, rl, rh, rm, rate = _bab_world(-0.001, 0.001, 15, n=1500)
    bad = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=300)
    assert bad["n"] < 3500 and bad["verdict"] == "not_supported"
    assert "net excess return > 0 (fails decisively below min_n" in bad["reason"]
    # a beta-switching low leg leaves a net beta whose interval still overlaps (-0.1, 0.1): undecided below min_n
    days, rl, rh, rm, rate = _bab_world(0.0003, -0.0003, 17, n=2000)
    b = np.where((np.arange(len(rm)) // 60) % 2 == 0, 0.2, 1.8)
    rl = b * rm + 0.0003 + np.random.default_rng(100).normal(0, 0.004, len(rm))
    sw = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=300)
    assert abs(sw["ex_post_beta"]) >= 0.1 and sw["verdict"] == "inconclusive"
    assert "|ex-post beta to the market| < 0.1 (fails, not decisively, below min_n: 95% NW interval of the beta" in sw["reason"]
    # a book hedged with a low-leg beta estimate twice too high is under-levered on that leg: a net short beta whose
    # whole 95% interval lies below -0.1 is a decisive failure even below min_n
    real, calls = bf.trailing_beta, []

    def biased(y, x, window=60, gap=2):
        calls.append(1)
        return real(y, x, window, gap) * (2.0 if len(calls) % 2 == 1 else 1.0)  # bab_spread_test asks for the low leg first

    monkeypatch.setattr(bf, "trailing_beta", biased)
    days, rl, rh, rm, rate = _bab_world(0.0003, -0.0003, 15, n=2000)
    mis = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=300)
    assert mis["ex_post_beta"] < -0.1 and mis["verdict"] == "not_supported"
    assert "|ex-post beta to the market| < 0.1 (fails decisively below min_n: 95% NW interval of the beta" in mis["reason"]


# ------------------------------------------------------------------- monthly timing tests --

def test_factor_momentum_rule5():
    names = ["HML", "SMB", "RMW", "CMA", "UMD", "BAB"]
    T = 300
    good = bf.factor_momentum_test(_months(1963, 7, T), _regime_factors(20, T=T), names, n_boot=400)
    assert good["n"] < 600 and good["ci"][0] > 0 and good["verdict"] == "inconclusive"
    assert "[criteria at face value: supported, all criteria pass]" in good["reason"]
    t = np.arange(400)
    rng = np.random.default_rng(5)
    phase = rng.integers(0, 18, 6)
    F = 0.012 * np.where(((t[:, None] + phase[None, :]) // 9) % 2 == 0, 1, -1) + rng.normal(0, 0.01, (400, 6))   # 9-month swings
    bad = bf.factor_momentum_test(_months(1963, 7, 400), F, names, n_boot=400)
    assert bad["n"] < 600 and bad["ci"][1] < 0 and bad["verdict"] == "not_supported"
    assert "lower 95% bound of the Sharpe difference > 0 (fails decisively below min_n" in bad["reason"]


def test_contrarian_timing_rule5():
    names = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
    T = 420
    ms = _months(1963, 7, T)
    start = ms.index("1968-01")
    rng = np.random.default_rng(22)
    t = np.arange(T)
    F = 0.004 + 0.02 * np.sin(2 * np.pi * t[:, None] / 80 + rng.uniform(0, 2 * np.pi, 6)[None, :]) + rng.normal(0, 0.015, (T, 6))
    good = bf.contrarian_timing_test(ms, F, names, n_boot=400, value_spread_timed=bf.contrarian_portfolios(F, ms, 48, np.ones(6), start)[1])
    assert good["n"] < 600 and good["verdict"] == "inconclusive"
    assert "[criteria at face value: supported, all criteria pass]" in good["reason"]
    R = _regime_factors(20, T=T)                                                  # persistent trends: leaning against them loses
    bad = bf.contrarian_timing_test(ms, R, names, n_boot=400)                     # DSR undecided (no value-spread trial) ...
    assert bad["ci"][1] < 0 and bad["verdict"] == "not_supported"                 # ... but the CI fails decisively
    assert "lower 95% bound of the Sharpe difference > 0 (fails decisively below min_n" in bad["reason"]


def test_industry_alpha_rule5():
    ms, port, rf, F5 = _industry_world(-0.01, 30)
    bad = bf.industry_alpha_test(ms, port, rf, F5, start="2015-01")
    assert bad["n"] < 200 and bad["alpha_t"] <= -2 and bad["verdict"] == "not_supported"
    assert "FF5 alpha NW t >= 2 (fails decisively below min_n: NW t" in bad["reason"]
    ms, port, rf, F5 = _industry_world(0.0, 31)
    null = bf.industry_alpha_test(ms, port, rf, F5, start="2015-01")
    assert -2 < null["alpha_t"] < 2 and null["verdict"] == "inconclusive" and RULE5 in null["reason"]
    tiny = bf.industry_alpha_test(ms, port, rf, F5, start="2024-06")              # 19 months: nothing estimable
    assert tiny["n"] < 24 and tiny["verdict"] == "inconclusive" and "not estimated" in tiny["reason"]


def test_sort_spread_rule5():
    T = 400
    ms = _months(1993, 1, T)
    F5 = np.random.default_rng(40).normal(0.005, 0.03, (T, 5))
    neg = -0.01 + 0.3 * F5[:, 4] + np.random.default_rng(41).normal(0, 0.02, T)
    bad = bf.sort_spread_test(ms, neg, ms, F5, "2018-01", "2026-09", 300, "neg", n_boot=800)
    assert bad["n"] == 100 and bad["verdict"] == "not_supported"
    assert "lower 95% bound of the mean monthly spread > 0 (fails decisively below min_n" in bad["reason"]
    weak = np.concatenate([np.zeros(T - 100), _exact(0.002, 0.02, 100, 42)])
    w = bf.sort_spread_test(ms, weak, ms, F5, "2018-01", "2026-09", 300, "weak", n_boot=800)
    assert w["ci_month"][0] < 0 < w["ci_month"][1] and w["verdict"] == "inconclusive"
    assert "fails, not decisively, below min_n" in w["reason"]
