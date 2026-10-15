"""Audit fixes for the model-priced structure claims (structure_claims.py, structures.py), on synthetic data.

OM-1 studentized CI where trial.statistic names one; OM-2 T-124 wing-PRICE multiplier; OM-3 zero-cost put solver bracket and
direction; OM-4 T-114 s=0.90 run prices the +2% call at VIX x r(1.02); OM-5 n is the tested series' length and trial.min_n is
enforced; OM-6 T-125 runs q = 0 and q = 1.8% (and T-100 q = 0, as its controls state).
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

import mandel.experiments.structure_claims as sc
from mandel.experiments.structures import Q, Smile, metric, run_structure
from mandel.options import bs

REGISTRY = Path(__file__).resolve().parents[1] / "mandel" / "theories" / "registry.json"


def _days(n):
    d = date(2000, 1, 3); out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _smile_rows(ratio):
    return [{"value": {"quote_date": "2026-10-14", "target_dte": t, "ratio": {f"{k:.2f}": v for k, v in ratio.items()}}} for t in (30, 45)]


SMILE = {0.85: 1.6, 0.90: 1.45, 0.95: 1.15, 1.00: 0.80, 1.02: 0.72, 1.05: 0.70, 1.10: 0.68, 1.15: 0.68}


def _ctx(n=900, seed=0, vix=20.0, rate=4.0, ratio=SMILE):
    rng = np.random.default_rng(seed); days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    return sc.Ctx(days, closes, {d: vix for d in days}, {d: rate for d in days}, _smile_rows(ratio))


def _recorder(monkeypatch):
    """Record every series evaluate() sends to a CI (in order) without changing the CI."""
    seen = []
    for name in ("_ci", "_ci_t"):
        orig = getattr(sc, name)
        monkeypatch.setattr(sc, name, (lambda o: lambda x, *a, **k: (seen.append(np.asarray(x, float).copy()), o(x, *a, **k))[1])(orig))
    return seen


class _FakeSmile:
    n_days = 2


class _FakeCtx:
    """evaluate() only needs run/m and smile.n_days; m returns preset series per (legs, mode)."""
    def __init__(self, series):
        self.series, self.smile = series, _FakeSmile()

    def m(self, legs, mode, kind, dte=30, hold=21, q=Q):
        return self.series[(tuple(legs), mode)]


# ---------------------------------------------------------------- OM-1: studentized block-bootstrap CI

def _skewed(n=403, seed=0):
    """Long-option-like P&L per premium: most cycles lose ~60% of premium, one pays +50x."""
    rng = np.random.default_rng(seed); x = -0.6 + rng.normal(0, 0.05, n); x[n // 3] = 50.0
    return x


def test_om1_studentized_ci_widens_the_right_tail_the_percentile_ci_misses():
    x = _skewed()
    lo_p, hi_p = sc._ci(x); lo_t, hi_t = sc._ci_t(x)
    assert hi_p < 0 < hi_t                         # percentile 'upper CI < 0' passes; the stated (studentized) statistic fails it
    assert lo_t < x.mean() < hi_t


def test_om1_studentized_ci_matches_normal_theory_on_iid_gaussian():
    rng = np.random.default_rng(3); x = rng.normal(0.1, 1.0, 2000)
    lo, hi = sc._ci_t(x); se = x.std(ddof=1) / math.sqrt(x.size)
    assert abs((hi - lo) / (2 * 1.96 * se) - 1) < 0.15 and abs((lo + hi) / 2 - x.mean()) < 0.5 * se


def test_om1_t102_uses_the_studentized_ci_and_fails_on_a_skewed_series():
    legs = (("put", "long", 1, 0.95), ("call", "long", 1, 1.05))
    rep = sc.evaluate("T-102", _FakeCtx({(legs, ("smile", 1.0)): _skewed()}))
    assert rep["verdict"] == "not_supported" and "failed: smile: upper CI < 0" in rep["reason"]
    assert "studentized" in rep["ci"]


def test_om1_studentized_set_and_min_n_match_the_registry():
    reg = json.load(open(REGISTRY)); items = reg["theories"] if isinstance(reg, dict) else reg
    trials = {t["id"]: t["trial"] for t in items if t.get("id") in sc.CLAIMS}
    assert set(trials) == set(sc.CLAIMS)
    assert {c for c, t in trials.items() if "studentized" in t["statistic"].lower()} == sc.STUDENTIZED
    assert {c: t["min_n"] for c, t in trials.items()} == sc.MIN_N


# ---------------------------------------------------------------- OM-2: T-124 wing-price multiplier

def test_om2_t124_multiplies_both_wing_prices_by_1_5(monkeypatch):
    c = _ctx(); seen = _recorder(monkeypatch)
    rep = sc.evaluate("T-124", c)
    w = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("put", "long", 1, 0.90), ("call", "long", 1, 1.10)]
    base = run_structure(c.days, c.closes, c.vix, c.rates, w, 30, 21, ("smile", 1.0), c.smile)
    S = base["spot"]; T = 30 / 365; r = math.log(1.04); V = 0.20
    put_w = np.array([float(bs.price(s, 0.90 * s, T, r, V * c.smile.ratio(0.90, 30), "put", Q)) for s in S])
    call_w = np.array([float(bs.price(s, 1.10 * s, T, r, V * c.smile.ratio(1.10, 30), "call", Q)) for s in S])
    extra = 0.5 * (put_w + call_w)
    # max loss of the iron fly is the 10% wing width less the net credit; paying 1.5x for the wings raises it by `extra`
    assert np.allclose(base["max_loss"], 0.10 * S + base["debit"], rtol=1e-6)
    expect = (base["pnl"] - extra) / (0.10 * S + base["debit"] + extra)
    assert np.allclose(seen[0], metric(base, "per_max_loss")) and np.allclose(seen[1], expect)
    # the old code scaled the IV-ratio deviation from ATM: with r(1.10) < r(1.00) that made the call wing CHEAPER
    old = run_structure(c.days, c.closes, c.vix, c.rates, w, 30, 21, ("smile", 1.5), c.smile)
    assert not np.allclose(seen[1], metric(old, "per_max_loss"))
    assert "wing prices x1.5 mean" in rep["reason"] and "wings x1.5" not in rep["reason"]


def test_om2_smile_wing_mult_is_documented_as_deviation_scaling():
    sm = Smile(_smile_rows(SMILE))
    assert abs(sm.ratio(1.10, 30, wing_mult=1.5) - (0.80 + (0.68 - 0.80) * 1.5)) < 1e-12      # call wing ratio FALLS
    import mandel.experiments.structures as st
    assert "not a wing-PRICE" in st.__doc__ and "deviation" in Smile.ratio.__doc__


# ---------------------------------------------------------------- OM-3: zero-cost put solver

SEAGULL = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]


def test_om3_zero_cost_strike_above_spot_at_low_vix_high_bills():
    days = _days(200); closes = np.full(200, 100.0)
    res = run_structure(days, closes, {d: 11.0 for d in days}, {d: 5.0 for d in days}, SEAGULL, 30, 21, ("flat", 1.0))
    k = np.array([s[2] for s in res["strikes"]]) / res["spot"]
    assert np.all(k > 1.0) and np.all(np.abs(res["debit"]) < 1e-9 * res["spot"]) and res["zero_cost_ok"].all()


def test_om3_long_zero_cost_put_solves_in_the_right_direction():
    days = _days(200); closes = np.full(200, 100.0)
    collar = [("call", "short", 1, 1.05), ("put", "long", 1, ("zero_cost_put",))]
    res = run_structure(days, closes, {d: 20.0 for d in days}, {d: 4.0 for d in days}, collar, 30, 21, ("flat", 1.0))
    k = np.array([s[1] for s in res["strikes"]]) / res["spot"]
    assert np.all(np.abs(res["debit"]) < 1e-9 * res["spot"]) and np.all(k > 0.5 + 1e-6) and res["zero_cost_ok"].all()


def test_om3_no_root_in_bracket_is_flagged_and_t517_cannot_be_supported():
    days = _days(200); closes = np.full(200, 100.0)
    credit_only = [("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]     # selling a put cannot zero a credit
    res = run_structure(days, closes, {d: 20.0 for d in days}, {d: 4.0 for d in days}, credit_only, 30, 21, ("flat", 1.0))
    assert not res["zero_cost_ok"].any()
    c = _ctx(n=21 * 320, seed=5, vix=18.0)
    good = c.run(SEAGULL, ("flat", 1.0)); assert good["zero_cost_ok"].all()
    good["zero_cost_ok"][0] = False                                                       # cached: evaluate sees the flag
    rep = sc.evaluate("T-517", c)
    assert rep["verdict"] != "supported" and "1 cycles with no zero-cost put strike" in rep["reason"]


# ---------------------------------------------------------------- OM-4: T-114 s=0.90 prices the +2% call at VIX x r(1.02)

def test_om4_t114_s090_straddle_at_0p9_vix_call_at_smile(monkeypatch):
    c = _ctx(); seen = _recorder(monkeypatch)
    sc.evaluate("T-114", c)
    bl = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("call", "long", 1, 1.02)]
    st = run_structure(c.days, c.closes, c.vix, c.rates, bl[:2], 30, 21, ("flat", 0.9), c.smile)
    S = st["spot"]; T = 30 / 365; r = math.log(1.04)
    call = np.array([float(bs.price(s, 1.02 * s, T, r, 0.20 * c.smile.ratio(1.02, 30), "call", Q)) for s in S])
    S1 = np.array([c.closes[c.days.index(d) + 21] for d in st["day"]])
    pnl = st["pnl"] + np.maximum(S1 - 1.02 * S, 0) - call
    assert np.allclose(seen[1], pnl / (S + st["debit"] + call))
    assert not np.allclose(seen[1], c.m(bl, ("flat", 0.9), "per_max_loss"))            # the old run priced the call at 0.9 VIX


def test_om4_combined_max_loss_equals_the_engine_grid_when_pricing_coincides(monkeypatch):
    flat = {k: 0.9 for k in SMILE}                     # r(K) = 0.9 everywhere: the mixed run must equal the all-flat 0.9 run
    c = _ctx(ratio=flat); seen = _recorder(monkeypatch)
    sc.evaluate("T-114", c)
    bl = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("call", "long", 1, 1.02)]
    assert np.allclose(seen[1], c.m(bl, ("flat", 0.9), "per_max_loss"), rtol=1e-9, atol=1e-12)


# ---------------------------------------------------------------- OM-5: n is the tested series; trial.min_n enforced

def test_om5_n_cycles_is_the_45dte_series_length():
    c = _ctx(n=21 * 120)
    rep = sc.evaluate("T-109", c)
    n45 = len(c.run([("put", "long", 1, 0.92), ("put", "short", 1, 0.95), ("call", "short", 1, 1.05), ("call", "long", 1, 1.08)],
                    ("smile", 1.0), 45, 31)["pnl"])
    assert rep["n_cycles"] == n45 < len(c.run(sc.STRADDLE, ("flat", 1.0))["pnl"]) and rep["min_n"] == 260


def _t116_ctx(n, shift):
    rng = np.random.default_rng(1)
    strap = (("call", "long", 2, 1.0), ("put", "long", 1, 1.0)); strip = (("call", "long", 1, 1.0), ("put", "long", 2, 1.0))
    ser = {}
    for s in sc.FLATS:
        e = rng.normal(0, 0.2, n); ser[(strap, ("flat", s))] = shift + e - e.mean(); ser[(strip, ("flat", s))] = np.zeros(n)
    return _FakeCtx(ser)


def test_om5_min_n_caps_a_pass_below_min_n():
    assert sc.evaluate("T-116", _t116_ctx(400, 0.3))["verdict"] == "supported"
    rep = sc.evaluate("T-116", _t116_ctx(100, 0.3))
    assert rep["verdict"] == "inconclusive" and rep["n_cycles"] == 100 and "n >= trial min_n (100 of 390 cycles)" in rep["reason"]


def test_om5_below_min_n_only_a_decisive_failure_decides():
    assert sc.evaluate("T-116", _t116_ctx(100, 0.0))["verdict"] == "inconclusive"      # CI straddles 0: not decisive
    rep = sc.evaluate("T-116", _t116_ctx(100, -0.3))                                   # CI wholly below 0: decisive
    assert rep["verdict"] == "not_supported"
    assert sc.evaluate("T-116", _t116_ctx(400, 0.0))["verdict"] == "not_supported"     # adequate data: any failure decides


def test_om5_conditional_subsample_is_not_counted_against_min_n():
    class C(_FakeCtx):
        def run(self, legs, mode, dte=30, hold=21, q=Q):
            n = 403; rng = np.random.default_rng(2)
            return {"pnl": rng.normal(-1, 0.1, n), "spot": np.full(n, 100.0), "vix": np.where(np.arange(n) < 140, 12.0, 25.0),
                    "debit": np.ones(n), "max_loss": np.ones(n)}
    rep = sc.evaluate("T-134", C({}))
    assert rep["n_cycles"] == 403 and "VIX<15 (n=140)" in rep["reason"]


# ---------------------------------------------------------------- OM-6: q per claim

def test_om6_ctx_cache_keys_on_q():
    c = _ctx(n=600)
    a = c.run([("call", "long", 1, 1.0)], ("flat", 1.0), q=0.0); b = c.run([("call", "long", 1, 1.0)], ("flat", 1.0), q=0.018)
    assert a is not b and np.all(a["debit"] > b["debit"])                               # dividends cheapen the call


def test_om6_t125_runs_q0_and_q18_and_t100_runs_q0(monkeypatch):
    c = _ctx(); seen = _recorder(monkeypatch)
    rep = sc.evaluate("T-125", c)
    call = [("call", "long", 1, 1.0)]
    want = [metric(run_structure(c.days, c.closes, c.vix, c.rates, call, 30, 21, ("flat", s), c.smile, q=q), "per_premium")
            for q in (0.0, 0.018) for s in (1.0, 0.9)]
    assert len(seen) == 4 and all(np.allclose(a, b) for a, b in zip(seen, want))
    for lab in ("s=1.0 q=0.0%", "s=0.9 q=0.0%", "s=1.0 q=1.8%", "s=0.9 q=1.8%"):
        assert lab in rep["reason"]
    seen.clear(); sc.evaluate("T-100", c)
    want = [metric(run_structure(c.days, c.closes, c.vix, c.rates, sc.STRADDLE, 30, 21, ("flat", s), c.smile, q=0.0), "per_premium")
            for s in sc.FLATS]
    assert all(np.allclose(a, b) for a, b in zip(seen, want))
