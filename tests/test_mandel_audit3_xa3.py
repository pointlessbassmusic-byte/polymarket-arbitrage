"""Audit round 3, group xa3 (mandel/experiments/cross_asset.py): house rule 5 below the trial's min_n.

Was: _cap_min_n turned every verdict below min_n into inconclusive after _verdict, a decisive not_supported included. Now _rule5 runs
before _verdict: below min_n a passing criterion keeps True, a decisively failing one (its interval wholly on the wrong side of the
claimed bound, or a failure that would persist at min_n whatever the missing observations are) keeps False, any other failure becomes
None, and the unmet min_n criterion keeps the verdict from 'supported'."""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import cross_asset as xa


def _days(n, cal=True, start=date(2015, 1, 1)):
    d = start; out = []
    while len(out) < n:
        if cal or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------------------------------------ the helpers --

def test_rule5_at_or_above_min_n_judges_every_criterion_at_face_value():
    rows = [("a", True, False), ("b", False, False)]
    assert xa._rule5(rows, 10, 10, "x") == ("not_supported", "failed: b")
    assert xa._rule5(rows, 3, None, "x") == ("not_supported", "failed: b")          # no min_n: nothing to apply
    assert xa._rule5([("a", True, False)], 10, 10, "x") == ("supported", "all criteria pass")


def test_rule5_below_min_n_decisive_failure_stays_not_supported():
    v, why = xa._rule5([("a", True, False), ("b", False, True), ("c", False, False)], 5, 10, "cycles")
    assert v == "not_supported"
    assert "b (fails decisively below min_n)" in why and "c (fails, not decisively, below min_n: undecided)" in why
    assert "only 5 cycles, below the trial's min_n 10" in why and "n >= trial min_n (5 of 10 cycles)" in why


def test_rule5_below_min_n_non_decisive_failure_is_inconclusive():
    v, why = xa._rule5([("a", True, False), ("b", False, False)], 5, 10, "cycles")
    assert v == "inconclusive" and "b (fails, not decisively, below min_n: undecided)" in why
    assert "(criteria: not_supported, failed: b)" in why                                   # the face-value reading is still reported


def test_rule5_below_min_n_pass_is_inconclusive():
    v, why = xa._rule5([("a", True, False), ("b", True, True)], 9, 10, "cycles")
    assert v == "inconclusive" and "(criteria: supported, all criteria pass)" in why
    assert xa._rule5([("a", True, False), ("s", None, False)], 9, 10, "cycles")[0] == "inconclusive"   # not implemented stays None


def test_rate_and_first_half_persistence():
    # a 'rate > 0.6' criterion fails at min_n whatever comes only if (hits + missing) / min_n <= 0.6
    assert xa._rate_fails_at_min_n(2, 20, 25, 0.6)                # (2 + 5) / 25 = 0.28
    assert not xa._rate_fails_at_min_n(5, 20, 40, 0.6)            # (5 + 20) / 40 = 0.625 could still pass
    assert not xa._rate_fails_at_min_n(0, 20, 20, 0.6)            # at min_n rule 5 does not apply
    x = np.array([-1.0] * 10 + [5.0] * 2); y = -x
    assert xa._first_half_fails_at_min_n(12, 20, lambda k: x[:k].mean() > 0)          # first half at min_n = x[:10] is known and < 0
    assert not xa._first_half_fails_at_min_n(8, 20, lambda k: x[:k].mean() > 0)       # x[:10] not yet observed
    assert not xa._first_half_fails_at_min_n(12, 20, lambda k: y[:k].mean() > 0)      # y[:10] > 0: the halves may still pass


# -------------------------------------------------------------------- conditional_straddle (T-256 / T-272) --

def _straddle(p_wild, p_dip, n=3000, seed=3, dip=20.0):
    """Calm (0.1%/day) except a wild stretch (5%/day) at positions p_wild of every 120 days; the index dips to ~dip at positions p_dip."""
    rng = np.random.default_rng(seed); days = _days(n); p = np.arange(n) % 120
    r = np.where((p >= p_wild[0]) & (p < p_wild[1]), rng.normal(0, 0.05, n), rng.normal(0, 0.001, n))
    closes = 100 * np.exp(np.cumsum(r))
    iv = np.where((p >= p_dip[0]) & (p < p_dip[1]), dip + rng.uniform(0, 0.5, n), 50.0)
    return days, closes, {d: float(v) for d, v in zip(days, iv)}, {d: 2.0 for d in days}


def test_straddle_decisive_failure_below_min_n_stays_not_supported():
    # low-index entries (70..84) are held through the calm days only; the wild stretch (30..59) pays the all-days straddles
    days, closes, idx, rates = _straddle((30, 60), (70, 85))
    dvol = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "DVOL")     # T-256 wiring: min_n 25
    assert dvol["min_n"] == 25 and dvol["n_entries"] < 25 and dvol["ci"][1] < 0
    assert dvol["verdict"] == "not_supported" and "difference 95% CI > 0 (fails decisively below min_n)" in dvol["reason"]   # was inconclusive
    assert xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "X", min_n=1)["verdict"] == "not_supported"


def test_straddle_non_decisive_failure_below_min_n_is_inconclusive():
    days, _, _, rates = _straddle((30, 60), (70, 85))
    flat = {d: 45.0 if i % 120 < 20 else 50.0 for i, d in enumerate(days)}           # low days carry no information
    calm = 100 * np.exp(np.cumsum(np.random.default_rng(9).normal(0, 0.003, len(days))))
    full = xa.conditional_straddle(days, calm, flat, rates, 60, 60, days[0], 252, 0.20, "X", min_n=1)
    assert full["verdict"] == "not_supported" and full["ci"][0] < 0 < full["ci"][1]
    thin = xa.conditional_straddle(days, calm, flat, rates, 60, 60, days[0], 252, 0.20, "X", min_n=full["n_entries"] + 1)
    assert thin["verdict"] == "inconclusive" and "fails, not decisively, below min_n: undecided" in thin["reason"]


def test_straddle_pass_below_min_n_is_inconclusive():
    days, closes, idx, rates = _straddle((90, 120), (70, 85))                       # the dip precedes the wild stretch: a planted edge
    full = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "X", min_n=1)
    assert full["verdict"] == "supported" and full["ci"][0] > 0
    thin = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "X", min_n=full["n_entries"] + 1)
    assert thin["verdict"] == "inconclusive" and "(criteria: supported, all criteria pass)" in thin["reason"]


# ---------------------------------------------------- short put, inverse covered call, covered call (BTC, DVOL) --

def _btc(drift, vol, iv=20.0, n=700, seed=6):
    rng = np.random.default_rng(seed); days = _days(n)
    return days, 20000 * np.exp(np.cumsum(rng.normal(drift, vol, n))), {d: iv for d in days}, {d: 2.0 for d in days}


def test_short_put_and_inverse_call_decisive_below_min_n():
    days, closes, idx, rates = _btc(-0.004, 0.02)                                   # falling BTC under a cheap flat index: puts lose
    sp = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 30, days[0], "DVOL")  # T-254: min_n 60
    assert sp["n_cycles"] < 60 and sp["ci"][1] < 0 and sp["verdict"] == "not_supported"
    assert "95% CI of the mean > 0 (fails decisively below min_n)" in sp["reason"]
    days, closes, idx, rates = _btc(0.004, 0.02, seed=7)                            # rising BTC: the 25-delta call is assigned at a loss
    ic = xa.inverse_covered_call_btc(days, closes, idx, rates, days[0])               # T-176: min_n 60
    assert ic["n_cycles"] < 60 and ic["ci"][1] < 0 and ic["verdict"] == "not_supported"


def test_short_put_pass_below_min_n_is_inconclusive():
    days, closes, idx, rates = _btc(0.0, 0.005, iv=80.0)                            # rich premium: every put expires worthless
    sp = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 30, days[0], "DVOL")
    assert sp["ci"][0] > 0 and sp["verdict"] == "inconclusive" and "min_n 60" in sp["reason"]
    assert xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 30, days[0], "DVOL", min_n=1)["verdict"] == "supported"


def test_covered_call_lower_sharpe_ci_below_min_n_is_decisive():
    # 30-day blocks of +25% rallies or -10% slides under a 20 index: capping the rallies costs far more than the premium
    rng = np.random.default_rng(7); n = 30 * 30 + 31; days = _days(n); up = rng.random(n // 30 + 2) < 0.5
    closes = 20000 * np.exp(np.cumsum(np.array([0.0075 if up[i // 30] else -0.0035 for i in range(n)]) + rng.normal(0, 0.001, n)))
    idx = {d: 20.0 for d in days}; rates = {d: 2.0 for d in days}
    cc = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 30, 12, days[0], "DVOL")    # T-253: min_n 60
    assert cc["n_cycles"] < 60 and cc["ci"][1] < 0 and cc["verdict"] == "not_supported"
    assert "covered call Sharpe higher than hold (Sharpe difference > 0) (fails decisively below min_n)" in cc["reason"]
    # at face value the same evidence fails on the claim's 'higher Sharpe' (was the post-hoc 'LOWER Sharpe' override)
    assert xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 30, 12, days[0], "X")["verdict"] == "not_supported"


def test_covered_call_dsr_shortfall_below_min_n_is_inconclusive(monkeypatch):
    rng = np.random.default_rng(4); n = 800; days = _days(n, cal=False)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, n))); idx = {d: 60.0 for d in days}; rates = {d: 2.0 for d in days}
    monkeypatch.setattr(xa, "deflated_sharpe_ratio", lambda *a, **k: 0.3)
    face = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "X")
    assert face["verdict"] == "not_supported" and face["ci"][0] > 0
    thin = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "GVZ")    # T-270: min_n 100
    assert thin["n_cycles"] < 100 and thin["verdict"] == "inconclusive"
    assert "deflated Sharpe > 0 (DSR probability > 0.5) (fails, not decisively, below min_n: undecided)" in thin["reason"]


# ------------------------------------------------------------------------- ratio_extremes (T-247 / T-266) --

def test_ratio_extremes_decisive_ci_below_min_n_stays_not_supported():
    rng = np.random.default_rng(1); n = 1300; days = _days(n)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n))); b = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    ia = {d: 110 + 10 * math.sin(i / 50) for i, d in enumerate(days)}; ib = {d: 50.0 for d in days}   # implied ~2.2 > realised ~1.5
    eth = dict(n=30, ppy=365, window=365, lo_q=0.20, hi_q=None, block=2, win_req=None)
    rep = xa.ratio_extremes(days, a, days, b, ia, ib, **eth, label="ETH/BTC DVOL")                # T-266: min_n 25
    assert rep["n"] < 25 and rep["ci"][1] < 0 and rep["verdict"] == "not_supported"          # was inconclusive
    # a 0/6 win rate is not decisive against min_n 40: 34 missing wins would make 0.85 > 0.6
    rep = xa.ratio_extremes(days, a, days, b, ia, ib, **{**eth, "win_req": 0.6}, label="t", min_n=40)
    assert rep["win_rate"] == 0 and "win rate > 0.6 (fails, not decisively, below min_n: undecided)" in rep["reason"]


# ------------------------------------------------------------------------------------- multi-asset (T-245) --

def _legs(n_cycles):
    n = 21 * n_cycles + 1; days = _days(n, cal=False)
    def leg(seed, vol, iv):
        rng = np.random.default_rng(seed)
        return days, 100 * np.exp(np.cumsum(rng.normal(0, vol / math.sqrt(252), n))), {d: iv for d in days}
    # SPX: rich variance premium; the other legs are under-priced, so the equal-vega portfolio has the lower Sharpe
    return {"SPX": leg(1, 0.10, 30.0), "GLD": leg(2, 0.30, 10.0), "USO": leg(3, 0.30, 10.0), "TLT": leg(4, 0.30, 10.0)}


def test_multi_asset_decisive_below_min_n_and_halves_persistence():
    rep = xa.multi_asset_short_variance(_legs(60))                                  # 60 < min_n 180
    assert rep["upper"] <= 0 and rep["verdict"] == "not_supported"
    assert "Sharpe diff > 0 with one-sided p < 0.05 (fails decisively below min_n)" in rep["reason"]
    assert "positive in both halves (fails, not decisively" in rep["reason"]          # the first 90 cycles are not all observed yet
    rep = xa.multi_asset_short_variance(_legs(100))                                 # cycles 0..89, the first half at 180, are known
    assert "positive in both halves (fails decisively below min_n)" in rep["reason"]


# --------------------------------------------------------------------------------------- zscore slope (T-514) --

def test_zscore_half_with_ci_wholly_above_zero_is_decisive():
    rng = np.random.default_rng(5); n = 4000; days = _days(n, cal=False); e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.98 * e[t - 1] + rng.normal(0, 0.003)                               # momentum: the slope is positive
    a = {d: float(20 * math.exp(v)) for d, v in zip(days, np.cumsum(e))}; b = {d: 20.0 for d in days}
    rep = xa.zscore_slope(None, a, b, start=days[0], min_n=10_000)
    assert rep["lower"][0] < 0 < rep["lower"][1] and rep["verdict"] == "not_supported"
    assert "second-half slope CI < 0 (fails decisively below min_n)" in rep["reason"]
    assert "first-half slope CI < 0 (fails, not decisively, below min_n: undecided)" in rep["reason"]


# ------------------------------------------------------------------------------- protective put (T-267) --

def test_protective_put_decisive_ci_and_settled_windows():
    n = 30 * 25 + 1; days = _days(n)
    closes = 100 * (1 - 0.5 * np.sin(np.pi * (np.arange(n) % 30) / 30))          # identical roll periods: the put drags every one
    idx = {d: 60.0 for d in days}; rates = {d: 2.0 for d in days}
    short = xa.protective_put_calmar(days[:30 * 10 + 1], closes[:30 * 10 + 1], idx, rates, days[0])   # 10 < min_n 20
    assert short["upper"] <= 0 and short["verdict"] == "not_supported"                           # was inconclusive
    assert "Calmar difference 95% CI > 0 (fails decisively below min_n)" in short["reason"]
    assert "positive in >= 2 of 3 windows (fails, not decisively" in short["reason"]              # only window 1 of 3 at min_n is known
    rep = xa.protective_put_calmar(days, closes, idx, rates, days[0], min_n=30)                    # windows [0,10) and [10,20) known
    assert "positive in >= 2 of 3 windows (fails decisively below min_n)" in rep["reason"]


# ------------------------------------------------------------------------ hit rate (T-274) via the helper --

@pytest.mark.parametrize("hits,n,min_n,decisive", [(3, 12, 15, True),    # (3 + 3) / 15 = 0.4
                                                    (6, 12, 15, True),    # (6 + 3) / 15 = 0.6 is not > 0.6
                                                    (7, 12, 15, False),   # (7 + 3) / 15 = 0.67 could still pass
                                                    (9, 16, 15, False)])  # at or above min_n rule 5 does not apply
def test_gold_silver_hit_rate_persistence(hits, n, min_n, decisive):
    assert xa._rate_fails_at_min_n(hits, n, min_n, 0.6) is decisive
