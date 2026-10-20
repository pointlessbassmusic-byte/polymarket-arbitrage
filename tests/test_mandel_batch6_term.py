"""Batch-6 term-structure harnesses (calendars, diagonals, PMCC, LEAPS collar, time fly, tested-put roll) on synthetic data:
planted effects pass, nulls do not. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6_term as bt
from mandel.options import bs

NB = 400                                # bootstrap resamples in judge tests


# ---------------------------------------------------------------------------------------------- synthetic data --

def _days(n, start=date(2008, 1, 2)):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _flat_term(n, vol):
    v = np.full(n, vol)
    return bt.Term(v.copy(), v.copy(), v.copy(), np.zeros(n, bool), None)


def _mkt(close, bills_pct=0.0, adj=None, start=date(2008, 1, 2)):
    days = _days(len(close), start)
    prev = (date.fromisoformat(days[0]) - timedelta(days=3)).isoformat()
    return bt.make_market(days, close, close if adj is None else adj, {prev: bills_pct})


def _ar(n, phi, sd, seed):
    rng = np.random.default_rng(seed); e = rng.standard_normal(n) * sd * math.sqrt(1 - phi ** 2); x = np.empty(n); x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


# --------------------------------------------------------------------------------------------- data conventions --

def test_cont_rate_and_prior_print():
    assert bt.cont_rate(5.0) == pytest.approx(-math.log(1 - 0.05 * 91 / 360) / (91 / 365))
    m = bt.make_market(["2020-01-02", "2020-01-03", "2020-01-06"], [100, 101, 102], [100, 101, 102],
                       {"2020-01-02": 2.0, "2020-01-03": 4.0})
    assert math.isnan(m.rate[0])                                      # no print dated before the first day
    assert m.rate[1] == pytest.approx(bt.cont_rate(2.0)) and m.rate[2] == pytest.approx(bt.cont_rate(4.0))


def test_dividends_forward_and_projection():
    close = np.array([100.0, 101.0, 100.5, 101.0, 102.0])
    f = 1 - 1.01 / 101.0                                              # a 1.01 dividend going ex on day 2
    adj = close * np.array([f, f, 1, 1, 1])
    m = bt.make_market(["2024-03-13", "2024-03-14", "2024-03-15", "2024-03-18", "2024-03-19"], close, adj, {"2024-03-01": 5.0})
    assert m.div[2] == pytest.approx(1.01, rel=1e-9)
    r = m.rate[0]
    assert m.pv_div([0], m.cal[4])[0] == pytest.approx(1.01 * math.exp(-r * 2 / 365))
    assert m.pv_div([2], m.cal[4])[0] == 0.0                          # ex on the valuation day: already in the close
    # projected: the same dividend 364 days later is counted for a long-dated option, not before
    assert m.n_projected == 2
    assert m.pv_div([4], m.cal[2] + 364)[0] == pytest.approx(1.01 * math.exp(-r * 360 / 365))
    assert m.pv_div([4], m.cal[2] + 363)[0] == 0.0
    # the option prices on S - PV(D)
    F = 100.0 - m.pv_div([0], m.cal[4])[0]
    assert bt.px(m, [0], m.cal[4], 100.0, "call", 0.2)[0] == pytest.approx(float(bs.price(F, 100.0, 6 / 365, r, 0.2, "call")))


def test_term_iv_interpolation_and_proxy():
    days = _days(3, date(2009, 9, 16))
    vix = {d: 20.0 for d in days}; v3 = {days[2]: 25.0}; v6 = {d: 27.0 for d in days}
    t = bt.make_term(days, vix, v3, v6)
    assert math.isnan(t.v93[0]) and t.v93[2] == pytest.approx(0.25)
    w30, w93 = 0.2 ** 2 * 30, 0.25 ** 2 * 93
    assert bt.term_iv(t, [2], [60.0])[0] == pytest.approx(math.sqrt((w30 + (w93 - w30) * 30 / 63) / 60))
    assert bt.term_iv(t, [2], [10.0])[0] == pytest.approx(0.20)            # flat VIX below 30 days
    w182 = 0.27 ** 2 * 182
    assert bt.term_iv(t, [2], [120.0])[0] == pytest.approx(math.sqrt((w93 + (w182 - w93) * 27 / 89) / 120))
    assert bt.term_iv(t, [2], [365.0])[0] == pytest.approx(0.27)           # flat VIX6M beyond 182 days
    tp = bt.make_term(days, vix, v3, v6, proxy_before=True)
    assert tp.proxy[0] and not tp.proxy[2] and tp.v93[2] == pytest.approx(0.25)
    assert tp.v93[0] == pytest.approx(math.sqrt((0.04 * 30 + (0.27 ** 2 * 182 - 0.04 * 30) * 63 / 152) / 93))
    assert bt.scaled_term(t, 0.5).v30[2] == pytest.approx(0.10)


def _chain_rows(S, qd, half=0.001, expiries=(30, 60, 90, 365)):
    q0 = date.fromisoformat(qd); rows = []
    for dte in expiries:
        exp = (q0 + timedelta(days=dte)).isoformat()
        for K in np.arange(0.8, 1.21, 0.01) * S:
            for kind in ("call", "put"):
                intr = max(S - K, 0) if kind == "call" else max(K - S, 0)
                mid = intr + 0.02 * S * math.exp(-abs(math.log(K / S)) * 10) * math.sqrt(dte / 30)
                otm = (kind == "call" and K >= S) or (kind == "put" and K <= S)
                hs = half * S if otm else 0.02 * S                  # ITM quotes are stale and wide
                rows.append({"value": {"expiry": exp, "type": kind, "strike": float(K), "bid": max(mid - hs, 0.01), "ask": mid + hs,
                                       "last_time": qd + "T15:59:00"}})
    return rows


def test_spreads_from_chain_otm_only():
    sp = bt.Spreads.from_chains([_chain_rows(500.0, "2026-10-13")])
    assert sp.quote_days == ["2026-10-13"]
    assert sp.frac(30, 1.0) == pytest.approx(0.001, rel=0.05)
    assert sp.frac(60, 0.85) == pytest.approx(0.001, rel=0.05)              # an ITM call is charged the OTM put's spread
    assert float(sp.cost(30, 520.0, 500.0)) == pytest.approx(0.5, rel=0.05)
    assert bt.Spreads.zero().cost(30, 100.0, 100.0) == 0.0


def _smile_rows(qd, idx=20.0):
    ks = [f"{x:.2f}" for x in np.arange(0.80, 1.21, 0.01)]
    def curve(slope):
        return {k: 0.8 + slope * (1.0 - float(k)) for k in ks}       # put wing above ATM, call wing below
    return [{"value": {"quote_date": qd, "target_dte": t, "dte": t, "index_level": idx, "ratio": curve(s)}} for t, s in ((30, 3.0), (45, 2.5))]


def test_skew_tilt():
    days = _days(3, date(2026, 10, 12))
    skew = {days[0]: 130.0, days[1]: 150.0, days[2]: 120.0}
    tl = bt.Tilt.build(_smile_rows(days[1]), days, skew, np.full(3, 0.2))
    assert tl.ref == pytest.approx(150.0)
    base = np.full(3, 0.16)
    s = tl.sig(base, [1, 1, 1], np.array([90.0, 100.0, 110.0]), 100.0, 30.0)
    assert s[1] == pytest.approx(0.16)                                       # ATM unchanged
    assert s[0] == pytest.approx(0.16 + 3.0 * 0.1 * 0.2) and s[2] == pytest.approx(0.16 - 3.0 * 0.1 * 0.2)
    s2 = tl.sig(base[:1], [2], 90.0, 100.0, 30.0)                            # SKEW 120: 40% of the captured tilt
    assert s2[0] == pytest.approx(0.16 + 3.0 * 0.1 * 0.2 * 0.4)


# ------------------------------------------------------------------------------------------------ pricing engine --

def test_two_expiry_calendar_flat_vol():
    n = 80; m = _mkt(np.full(n, 100.0)); t = _flat_term(n, 0.2)
    r = bt.long_calendar(m, t, np.array([0]), bt.Spreads.zero())
    T1 = (m.cal[21] - m.cal[0]) / 365
    c30, c60 = float(bs.price(100, 100, T1, 0.0, 0.2, "call")), float(bs.price(100, 100, T1 + 30 / 365, 0.0, 0.2, "call"))
    assert r["debit"][0] == pytest.approx(c60 - c30)
    assert r["val1"][0] == pytest.approx(float(bs.price(100, 100, 30 / 365, 0.0, 0.2, "call")))     # front expires worthless
    assert r["x"][0] == pytest.approx((r["val1"][0] - r["debit"][0]) / r["debit"][0])
    s = bt.short_calendar(m, t, np.array([0]), bt.Spreads.zero())
    assert s["pnl"][0] == pytest.approx(-r["pnl"][0]) and s["x"][0] == pytest.approx(s["pnl"][0] / c60)
    rc = bt.long_calendar(m, t, np.array([0]), bt.Spreads(np.full((8, 9), 1e-3)))
    assert rc["cost"][0] == pytest.approx(4 * 1e-3 * 100)                    # four fills
    tf = bt.time_vs_plain_fly(m, t, np.array([0]), bt.Spreads(np.full((8, 9), 1e-3)))
    assert np.isfinite(tf["xt"][0]) and np.isfinite(tf["xp"][0])


def test_long_schedule_marks_are_continuous():
    n = 260; rng = np.random.default_rng(1)
    m = _mkt(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), 2.0); t = _flat_term(n, 0.2)
    g = np.arange(5, n, 21)
    lg = bt.long_schedule(m, g, 2, 30.0, "call", 0.7, lambda i, T: t.v30[np.asarray(i, int)], bt.Spreads.zero())
    for k in range(len(g) - 2):
        if not lg["first"][k + 1]:
            assert lg["v1"][k] == pytest.approx(lg["v0"][k + 1])            # the held leg is marked once per grid day
        else:
            assert lg["E"][k] - m.cal[g[k + 1]] == pytest.approx(30.0)        # replaced with 30 days left
    d0 = float(bs.greeks(m.close[g[0]] - m.pv_div([g[0]], lg["E"][0])[0], lg["K"][0], (lg["E"][0] - m.cal[g[0]]) / 365,
                         m.rate[g[0]], 0.2, "call")["delta"])
    assert d0 == pytest.approx(0.7, abs=1e-6)
    ml = bt.monthly_leg(m, g, "put", -0.25, lambda i, T: t.v30[np.asarray(i, int)], bt.Spreads.zero())
    assert np.all(ml["K"] < m.close[g[:-1]]) and np.all(ml["pay"] >= 0)


def test_spike_months():
    days = _days(70, date(2020, 1, 1)); vix = np.full(70, 15.0)
    vix[[d.startswith("2020-02") for d in days].index(True) + 5] = 40.0
    vix[[d.startswith("2020-03") for d in days].index(True) + 3] = 25.0
    assert bt.spike_months(days, vix, 2) == ["2020-02", "2020-03"]


# ---------------------------------------------------------------------------------------------------- statistics --

def test_studentized_mean_and_group_diff():
    rng = np.random.default_rng(0)
    pos = rng.normal(0.3, 1.0, 400); zero = rng.normal(0.0, 1.0, 400)
    lo, hi = bt.t_bounds(bt.boot_mean_t(pos, 5, NB), 0.05)
    assert lo > 0 and hi > lo
    lo0, hi0 = bt.t_bounds(bt.boot_mean_t(zero, 5, NB), 0.05)
    assert lo0 < 0 < hi0
    g1 = rng.random(400) < 0.3; x = rng.normal(0, 1, 400) + 0.8 * g1
    res = bt.boot_group_diff_t(x, g1, ~g1, 5, NB)
    assert res["est"] == pytest.approx(x[g1].mean() - x[~g1].mean())
    assert bt.t_bounds(res, 0.05)[0] > 0 and bt.t_pvalue(res) < 0.01


def test_spearman_with_ties():
    a = np.array([1.0, 2.0, 2.0, 3.0, 4.0]); b = np.array([10.0, 20.0, 20.0, 30.0, 40.0])
    assert bt.spearman(a, b) == pytest.approx(1.0)
    assert list(bt.rank_avg(a)) == [0.0, 1.5, 1.5, 3.0, 4.0]
    assert bt.spearman(a, -b) == pytest.approx(-1.0)


# ----------------------------------------------------------------------------- per-claim judges: planted vs null --

def _regime_data(effect, seed=0, n=3000):
    ratio = 0.90 + _ar(n, 0.95, 0.08, seed)                                 # ~10% of days >= 1.0, ~50% <= 0.9
    x = _ar(n, 0.95, 0.3, seed + 1) + effect * (ratio >= 1.0)
    return x, ratio


def test_t143_regime_planted_passes():
    x, ratio = _regime_data(1.0)
    j = bt.judge_regime(x, ratio, x, 30, NB)
    assert j["verdict"] == "supported", j["why"]
    assert j["difference"] > 0.8 and j["p_shift_deflated"] < 0.05


def test_t143_regime_null_fails():
    x, ratio = _regime_data(0.0, seed=3)
    j = bt.judge_regime(x, ratio, x, 30, NB)
    assert j["verdict"] != "supported"
    j2 = bt.judge_regime(x, ratio, None, 30, NB)                             # no sensitivity rerun: never supported
    assert j2["verdict"] != "supported"
    xp, rp = _regime_data(1.0)
    assert bt.judge_regime(xp, rp, None, 30, NB)["verdict"] == "inconclusive"


def test_t144_conditional_mean():
    x = 0.5 + _ar(800, 0.9, 0.5, 2)
    assert bt.judge_conditional_mean(x, None, 60, NB)["verdict"] == "supported"
    assert bt.judge_conditional_mean(_ar(800, 0.9, 0.5, 4), None, 60, NB)["verdict"] == "not_supported"
    small = bt.judge_conditional_mean(0.5 + _ar(40, 0.5, 0.5, 2), None, 60, NB)
    assert small["verdict"] == "inconclusive"                                 # below min_n a pass cannot confirm


def test_sharpe_halves_gt_and_not_above():
    rng = np.random.default_rng(5); b = rng.normal(0.005, 0.03, 240)
    a = b + 0.02 + rng.normal(0, 0.005, 240)
    assert bt.judge_sharpe_halves(a, b, 12, "gt", 150, "months", NB)["verdict"] == "supported"
    a0 = rng.normal(0.005, 0.03, 240)
    assert bt.judge_sharpe_halves(a0, b, 12, "gt", 150, "months", NB)["verdict"] == "not_supported"
    worse = b - 0.01 + rng.normal(0, 0.005, 240)                            # T-150's claim true: PMCC not better
    assert bt.judge_sharpe_halves(worse, b, 12, "not_above", 150, "months", NB)["verdict"] == "supported"
    assert bt.judge_sharpe_halves(a, b, 12, "not_above", 150, "months", NB)["verdict"] == "not_supported"
    ext = bt.judge_sharpe_halves(a, b, 12, "gt", 150, "months", NB, extra=[("PBO < 0.5", False, False)])
    assert ext["verdict"] == "not_supported"


def test_t146_std_ratio():
    rng = np.random.default_rng(6); xs = rng.normal(0, 1, 220)
    assert bt.judge_std_ratio(0.5 * xs + rng.normal(0, 0.1, 220), xs, 150, NB)["verdict"] == "supported"
    assert bt.judge_std_ratio(rng.normal(0, 1, 220), xs, 150, NB)["verdict"] == "not_supported"


def test_t147_paired_halves():
    rng = np.random.default_rng(7)
    ok = bt.judge_paired_halves({"flat IV": rng.normal(0.05, 0.05, 120), "SKEW tilt": rng.normal(0.05, 0.05, 120)}, 80, "months", NB)
    assert ok["verdict"] == "supported"
    bad = bt.judge_paired_halves({"flat IV": rng.normal(0.0, 0.05, 120), "SKEW tilt": rng.normal(0.05, 0.05, 120)}, 80, "months", NB)
    assert bad["verdict"] == "not_supported"
    miss = bt.judge_paired_halves({"flat IV": rng.normal(0.05, 0.05, 120), "SKEW tilt": None}, 80, "months", NB)
    assert miss["verdict"] == "inconclusive"


def test_t149_spearman():
    rng = np.random.default_rng(8); dv = rng.normal(0, 2, 1400)
    assert bt.judge_spearman(rng.normal(0, 1, 1400), dv, 300, NB)["verdict"] == "supported"
    assert bt.judge_spearman(dv + rng.normal(0, 2, 1400), dv, 300, NB)["verdict"] == "not_supported"


def test_t152_spike_decile():
    rng = np.random.default_rng(9); dv = rng.normal(0, 3, 220); xp = rng.normal(-0.2, 0.3, 220)
    xt = xp + rng.normal(0, 0.1, 220) + 0.5 * (dv >= np.quantile(dv, 0.9))
    j = bt.judge_spike_decile(xt, xp, dv, 15, NB)
    assert j["verdict"] == "supported" and j["n"] == 22
    assert bt.judge_spike_decile(rng.normal(-0.2, 0.3, 220), xp, dv, 15, NB)["verdict"] == "not_supported"
    gap = bt.judge_spike_decile(xt, xp, dv, 15, NB, extra=[("claim window since 2007-12", None, False)])
    assert gap["verdict"] == "inconclusive"                  # an unreachable claim window (inputs after 2007-12) caps the verdict


def test_t152_vix_for_vix3m_panel():
    """Regression (T-152): VIX stands in for VIX3M only where VIX3M has no print; the fit is VIX - VIX3M on the overlap."""
    n = 60; v30 = np.full(n, 0.20); v93 = np.full(n, 0.22); v93[:25] = np.nan
    t = bt.Term(v30, v93, np.full(n, np.nan), np.zeros(n, bool), None)
    tw = bt.vix_for_vix3m(t)
    assert np.all(tw.v93[:25] == 0.20) and np.all(tw.v93[25:] == 0.22)
    assert tw.proxy[:25].all() and not tw.proxy[25:].any() and tw.proxy_label == "VIX-for-VIX3M proxy"
    assert bt.term_iv(tw, np.arange(25), 60.0) == pytest.approx(np.full(25, 0.20))     # back legs priced at VIX
    assert bt.scaled_term(tw, 0.9).proxy_label == tw.proxy_label
    fit = bt.vix_for_vix3m_fit(t)
    assert fit["n"] == 35 and fit["mean_err_3m"] == pytest.approx(-2.0) and fit["mae_3m"] == pytest.approx(2.0)
    assert -2.0 < fit["mean_err_back"] < 0.0                                 # the 60-DTE leg sits between VIX and VIX3M
    assert bt.vix_for_vix3m_fit(bt.vix_for_vix3m(t))["n"] == 35              # filled days never count as overlap


def test_swap_permutation_p():
    rng = np.random.default_rng(12); b = rng.normal(0.005, 0.03, 240)
    assert bt.swap_perm_p(b + 0.02, b, 12, NB) < 0.01
    assert bt.swap_perm_p(rng.normal(0.005, 0.03, 240), b, 12, NB) > 0.05


def test_t155_roll():
    rng = np.random.default_rng(10); reset = rng.normal(1e-4, 2e-4, 600)
    assert bt.judge_roll(reset - 2e-5 + rng.normal(0, 1e-5, 600), reset, 200, NB)["verdict"] == "supported"
    assert bt.judge_roll(reset + 1e-4 + rng.normal(0, 1e-5, 600), reset, 200, NB)["verdict"] == "not_supported"


def test_t155_nearest_expiry_ties_and_dte_entries():
    c0 = 800000.0
    j, ok = bt.nearest_expiry([c0, c0, c0], [c0 - 3, c0 + 31, c0 + 59, c0 + 87])
    assert ok.all() and list(j) == [2, 2, 2]                                    # 31 vs 59 days: tie to the later expiry
    j, ok = bt.nearest_expiry([c0, c0 + 1], [c0 + 28, c0 + 63])
    assert list(j) == [0, 1]                                                    # 28 (17 from 45) beats 63 (18); then 27 vs 62
    j, ok = bt.nearest_expiry([c0], [c0 - 10, c0])
    assert not ok[0]                                                            # nothing strictly after the entry


def _t155_market(n=760, seed=4):
    """Weekdays from 2008-01-02 without Good Friday 2008 (the March 2008 monthly expiry moves to Thursday 2008-03-20)."""
    days = [d for d in _days(n + 1, date(2008, 1, 2)) if d != "2008-03-21"][:n]
    rng = np.random.default_rng(seed); close = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
    m = bt.make_market(days, close, close, {"2007-12-31": 2.0})
    return m, np.full(n, 0.2)


def test_t155_rule10a_paths_share_the_next_monthly_expiry_and_exit():
    """Regression (batch-6a check, rule 10a): T-155's claim names the monthly calendar ('to the next monthly'). The put sold at
    each daily entry lives on the standard monthly expiry nearest 45 DTE (not entry + 45 days), the test is at that expiry's
    21-DTE close, and the roll (same strike) and the reset (fresh 0.16-delta put at the test close) are both on the NEXT
    monthly expiry and both exit at its 21-DTE close, so they share expiry, exit and days held (the old harness rolled to
    E0 + 28 days and reset to test + 45 days: two different synthetic expiries and exits)."""
    m, v30 = _t155_market()
    ec = bt.expiry_ordinals(m); ecs = set(ec.tolist())
    tf = {bt.third_friday(y, mo).toordinal() for y in (2008, 2009, 2010, 2011) for mo in range(1, 13)}
    assert date(2008, 3, 20).toordinal() in ecs and date(2008, 3, 21).toordinal() not in ecs
    assert ecs - {date(2008, 3, 20).toordinal()} <= tf and ec[-1] > m.cal[-1]       # projected past the data
    a = np.arange(len(m.days))
    res = bt.roll_vs_reset(m, v30, a, bt.Spreads.zero(), ec, tested=1.0)              # every put 'tested': check all paths
    A, E0, E1, c, e = res["a"], res["E0"], res["E1"], res["check"], res["exit"]
    assert A.size > 600 and res["tested"].all()
    assert set(E0.tolist()) <= ecs and set(E1.tolist()) <= ecs
    assert np.all(E1 == ec[np.searchsorted(ec, E0) + 1])                              # the next monthly expiry
    dte = E0 - m.cal[A]
    assert np.all((dte >= 27) & (dte <= 63)) and np.mean(dte != 45) > 0.9             # the calendar, not entry + 45 days
    for i in range(A.size):                                                           # nearest 45 DTE among later expiries
        later = ec[ec > m.cal[A[i]]]
        assert abs(dte[i] - 45) <= np.min(np.abs(later - m.cal[A[i]] - 45))
    assert np.all(m.cal[c] >= E0 - 21) and np.all(m.cal[c - 1] < E0 - 21)            # first close with <= 21 days left
    assert np.all(m.cal[e] >= E1 - 21) and np.all(m.cal[e - 1] < E1 - 21)
    assert np.all(res["days"] == m.cal[e] - m.cal[c]) and set(np.unique(res["days"]).tolist()) <= {27, 28, 29, 34, 35, 36}
    assert set(np.unique(E1 - E0).tolist()) <= {27, 28, 29, 34, 35, 36}               # one monthly cycle (Good Friday moves)
    assert np.all(m.cal[c] - m.cal[A] > 0)
    # the reset strike is the 0.16-delta put on E1 at the test close; the roll keeps the entry strike
    d_reset = np.asarray(bt.greeks_at(m, c, E1, res["K_reset"], "put", v30[c])["delta"], float)
    assert np.allclose(d_reset, -0.16, atol=1e-3)
    d_entry = np.asarray(bt.greeks_at(m, A, E0, res["K"], "put", v30[A])["delta"], float)
    assert np.allclose(d_entry, -0.16, atol=1e-3)
    # every entry mapped to one expiry shares the reset path: same decision, same strike, same P&L
    for cyc in np.unique(res["cycle"])[:5]:
        s = res["cycle"] == cyc
        assert np.unique(c[s]).size == 1 and np.unique(e[s]).size == 1 and np.ptp(res["reset"][s]) == 0
    # same exit and days: with zero costs and rates, roll - reset is the P&L of (short K, long K_reset) on E1 from c to e
    z = bt.make_market(m.days, m.close, m.close, {"2007-12-31": 0.0}); rz = bt.roll_vs_reset(z, v30, a, bt.Spreads.zero(), ec, tested=1.0)
    K, Ks, cz, ez, E1z = rz["K"], rz["K_reset"], rz["check"], rz["exit"], rz["E1"]
    leg = lambda Kx, i: bt.px(z, i, E1z, Kx, "put", v30[i])
    want = ((leg(K, cz) - leg(K, ez)) - (leg(Ks, cz) - leg(Ks, ez))) / (z.cal[ez] - z.cal[cz]) / z.close[cz]
    assert np.allclose(rz["roll"] - rz["reset"], want, rtol=0, atol=1e-12)


def test_t155_one_entry_about_45_dte_per_expiry():
    m, v30 = _t155_market()
    ec = bt.expiry_ordinals(m); a = np.arange(len(m.days))
    e1 = bt.entries_near_dte(m, ec, a)
    r = bt.roll_vs_reset(m, v30, e1, bt.Spreads.zero(), ec)
    assert r["a"].size >= 30 and np.all(np.abs(r["dte_entry"] - 45) <= 3)
    assert np.unique(r["cycle"]).size == r["a"].size                                   # one entry per monthly expiry
    assert np.all(np.diff(r["E0"]) >= 27)


# ------------------------------------------------------------------------------------ fake archive, end to end --

class FakeArchive:
    def __init__(self, bundles):
        self.b = bundles

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return SimpleNamespace(name=name, created_at="2100-01-01T00:00:00+00:00")

    def load(self, name):
        return iter(self.b[name])

    def entries(self):
        return [SimpleNamespace(name=n, created_at="2100-01-01T00:00:00+00:00") for n in self.b]


def _idx_rows(days, vals):
    return [{"value": {"day": d, "close": float(v)}, "available_at": d + "T21:30:00+00:00"} for d, v in zip(days, vals)]


def _synthetic_archive(n=1900, seed=11):
    rng = np.random.default_rng(seed); days = _days(n, date(2007, 1, 3))
    lv = np.log(18) + _ar(n, 0.985, 0.35, seed)
    vix = np.exp(lv); shock = rng.standard_normal(n)
    vix = np.clip(vix + 6 * np.maximum(-shock - 1.8, 0), 9, 80)
    vix3m = vix * (1.12 - 0.25 * (vix - 18) / 18).clip(0.85, 1.3); vix6m = vix3m * 1.05
    ret = -0.6 * np.diff(np.log(vix), prepend=np.log(vix[0])) * 0.1 + vix / 100 / math.sqrt(252) * rng.standard_normal(n) + 0.0003
    close = 100 * np.exp(np.cumsum(ret))
    ratio = np.ones(n)                                                        # quarterly 0.4% dividends on third Fridays
    for i in range(1, n):
        d = date.fromisoformat(days[i]); y = 0.004 if d.month % 3 == 0 and d.weekday() == 4 and 15 <= d.day <= 21 else 0.0
        ratio[i] = ratio[i - 1] / (1 - y) if y else ratio[i - 1]
    adj = close * ratio / ratio[-1]
    t0 = lambda d: datetime.fromisoformat(d + "T14:30:00+00:00").timestamp()
    spy = [{"value": {"symbol": "SPY", "t": t0(d), "close": float(c), "adjclose": float(a)}, "available_at": d + "T21:30:00+00:00"}
           for d, c, a in zip(days, close, adj)]
    first3 = days.index(next(d for d in days if d >= "2009-09-18")); first6 = days.index(next(d for d in days if d >= "2008-01-02"))
    qd = days[-1]; cap = (date.fromisoformat(qd) + timedelta(days=1)).isoformat()
    S = float(close[-1])
    surface = [{"observed_at": cap + " 11:00:00", "value": {"symbol": "SPY", "expiry": (date.fromisoformat(cap) + timedelta(days=dte)).isoformat(),
                "dte": dte, "atm_iv": 0.8 * vix[-1] / 100 * (1 + 0.1 * dte / 365), "iv_put25d": 0.95 * vix[-1] / 100 * (1 + 0.1 * dte / 365)}}
               for dte in (7, 29, 45, 64, 92, 180, 350, 420)]
    return FakeArchive({
        "daily-history-SPY": spy,
        "cboe-VIX-history": _idx_rows(days, vix),
        "cboe-VIX3M-history": _idx_rows(days[first3:], vix3m[first3:]),
        "cboe-VIX6M-history": _idx_rows(days[first6:], vix6m[first6:]),
        "cboe-SKEW-history": _idx_rows(days, 125 + 10 * np.sin(np.arange(n) / 50)),
        "fred-DTB3": [{"value": {"day": d, "value": 1.0}, "available_at": d + "T20:00:00+00:00"} for d in days],
        "options-chain-SPY-" + cap: _chain_rows(S, qd, 0.0005),
        "options-surface-" + cap: surface,
        "spy-smile-" + qd: _smile_rows(qd, float(vix[-1])),
    })


@pytest.fixture(scope="module")
def fake():
    return _synthetic_archive()


def test_harness_registry():
    assert set(bt.THEORY_MAP.values()) == set(bt.HARNESSES)
    assert sorted(bt.THEORY_MAP) == ["T-143", "T-144", "T-145", "T-146", "T-147", "T-149", "T-150", "T-151", "T-152", "T-155"]
    assert all(h.startswith("b6_term_") and h == h.lower() for h in bt.HARNESSES)


@pytest.mark.parametrize("harness", sorted(bt.HARNESSES))
def test_harness_end_to_end(fake, harness):
    stat, n, verdict, reason = bt.HARNESSES[harness](fake)
    assert verdict in ("supported", "not_supported", "inconclusive")
    json.dumps(stat, allow_nan=False)
    assert isinstance(n, int) and n > 0
    assert reason.startswith("MODEL-PRICED") and " — " in reason
    assert "IV-scale sensitivity" in reason
    assert "rule 10" in reason                                              # every harness states its entry-calendar treatment
    if harness == "b6_term_calendarised_fly":                               # T-152's claim names its window: priced from 2007-12
        assert "claim window: daily entries from 2007-12-03" in reason and "real VIX3M only, from its first print 2009-09-18" in reason
        assert "rule 10(b)" in reason and "start offsets pass" in reason
    elif harness != "b6_term_roll_tested_put":
        assert "2009-09-18" in reason                                       # the claim window starts at the first VIX3M print
        assert "window sensitivity" in reason


def test_window_note_and_proxy_used(fake):
    stat, n, verdict, reason = bt.HARNESSES["b6_term_long_calendar"](fake)
    assert "proxy vs real VIX3M" in reason and "entries on the VIX/VIX6M VIX3M proxy" in reason
    assert stat["spread_shift"] is not None                                 # the surface capture fed the sensitivity rerun


@pytest.mark.parametrize("harness", sorted(bt.HARNESSES))
def test_missing_inputs_inconclusive(harness):
    stat, n, verdict, reason = bt.HARNESSES[harness](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "daily-history-SPY" in stat["missing_bundles"]


@pytest.fixture(scope="module")
def fake_long():
    return _synthetic_archive(4600)                                           # 2007-01 to 2024-08: >= 15 spike-decile months


def test_t152_prices_claim_window(fake_long):
    """Regression (T-152): the claim's window (since 2007-12) is priced with VIX for VIX3M before the first VIX3M print and
    is not a not-implemented criterion; the real-VIX3M-only run and the VIX/VIX6M proxy are report-only sensitivities."""
    stat, n, verdict, reason = bt.HARNESSES["b6_term_calendarised_fly"](fake_long)
    assert stat["first_entry"] == "2007-12-03" and stat["proxy_entries"] > 0     # every session of 2007-12 (pooled, rule 10b)
    assert stat["offsets_summary"]["offsets"] == 21 and len(stat["halves"]) == 2 and all(len(h["ci"]) == 2 for h in stat["halves"])
    assert "pin-risk sensitivity" in reason and "all entries (not the claim): mean P&L/debit time fly" in reason
    assert all(d < "2009-09-18" for d in stat["proxy_spike_days"])
    assert n == stat["n"] >= 15 and verdict == "supported" and reason.endswith("all criteria pass")
    assert "not implemented" not in reason and "the claim's window, top-decile months" not in reason
    assert "VIX stands in for VIX3M" in reason and "proxy error against the real VIX3M" in reason
    real = stat["sensitivities"]["real_vix3m_only"]
    assert real["window"].startswith("2009-09-18") and real["n"] > 0 and len(real["ci"]) == 2
    assert "vix6m_proxy" in stat["sensitivities"] and stat["proxy_fit"]["mean_err_3m"] is not None
    json.dumps(stat, allow_nan=False)


def test_t152_window_criterion_when_inputs_start_after_2007_12(fake_long):
    """Regression (T-152) null: when SPY / VIX / the bill cannot reach 2007-12 even with VIX for VIX3M, the window stays a
    criterion that is not implemented, so the same planted effect is inconclusive, never supported."""
    late = {"daily-history-SPY", "cboe-VIX-history", "fred-DTB3"}
    b = {k: ([r for r in rows if r["available_at"][:7] >= "2008-03"] if k in late else rows) for k, rows in fake_long.b.items()}
    stat, n, verdict, reason = bt.HARNESSES["b6_term_calendarised_fly"](FakeArchive(b))
    assert stat["first_entry"] >= "2008-03" and verdict == "inconclusive"
    assert "not implemented: the claim's window, top-decile months since 2007-12" in reason


def test_t147_without_smile_is_inconclusive_at_best(fake):
    b = {k: v for k, v in fake.b.items() if not k.startswith("spy-smile-")}
    stat, n, verdict, reason = bt.HARNESSES["b6_term_double_diagonal"](FakeArchive(b))
    assert verdict == "inconclusive" and "spy-smile-<date>" in stat["missing_bundles"]


# ------------------------------------------------------------------------- rule 10: entry calendars and grid phase --

def test_monthly_expiries_third_friday_and_holiday():
    """Rule 10(a): the standard monthly expiry is the third Friday, or the prior session when it is a holiday."""
    days = [d for d in _days(260, date(2008, 1, 2)) if d != "2008-03-21"]           # Good Friday 2008: exchange holiday
    m = bt.make_market(days, np.full(len(days), 100.0), np.full(len(days), 100.0), {"2007-12-31": 3.0})
    g = bt.monthly_expiries(m, "2008-01-01"); got = [m.days[i] for i in g]
    assert got[:5] == ["2008-01-18", "2008-02-15", "2008-03-20", "2008-04-18", "2008-05-16"]
    assert all(date.fromisoformat(d).weekday() == 4 for d in got if d != "2008-03-20") and len(got) == 12
    assert list(bt.monthly_expiries(m, "2008-01-19")) == list(g[1:])
    g2, ec = bt.calendar_cycles(m, _flat_term(len(days), 0.2), "2008-01-21")
    assert m.days[g2[0]] == "2008-02-15" and ec.size == g2.size + 24
    assert list(ec[:g2.size]) == list(m.cal[g2]) and ec[g2.size] == date(2009, 1, 16).toordinal()   # projected past the data


def test_calendar_roll_long_legs_expire_on_the_calendar():
    """Rule 10(a): on the monthly expiry calendar the 90-DTE long is the expiry three cycles out (one cycle left at its
    replacement) and the 12-month LEAPS the expiry twelve cycles out (three cycles, about 90 days, left)."""
    n = 700; rng = np.random.default_rng(3)
    m = _mkt(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), 2.0); t = _flat_term(n, 0.2)
    g, ec = bt.calendar_cycles(m, t, m.days[0])
    assert all(date.fromisoformat(m.days[i]).weekday() == 4 and 15 <= int(m.days[i][8:]) <= 21 for i in g)
    iv = lambda i, T: t.v30[np.asarray(i, int)]
    for L, xc, buy, left in ((2, 1, (83, 99), (27, 36)), (9, 3, (356, 372), (83, 99))):
        lg = bt.long_schedule(m, g, L, 0.0, "call", 0.7, iv, bt.Spreads.zero(), exp_cal=ec, extra_cycles=xc)
        for j in np.flatnonzero(lg["first"]):
            E = lg["E"][j]
            assert E in set(ec) and buy[0] <= E - m.cal[g[j]] <= buy[1]
            if j + L < g.size:
                assert left[0] <= E - m.cal[g[j + L]] <= left[1]
    dv = bt.diagonal_vs_vertical(m, t, g, bt.Spreads.zero(), exp_cal=ec)
    assert dv["xd"].size == g.size - 1 and np.all(np.isfinite(dv["xd"]))


def _phase_only_fly(effect_all=False, n_cycles=200, seed=20):
    rng = np.random.default_rng(seed); n = 21 * n_cycles
    dv = rng.normal(0, 3, n); top = dv >= np.quantile(dv, 0.9); ph0 = np.arange(n) % 21 == 0
    xp = rng.normal(-0.2, 0.3, n)
    plant = np.where(top, 0.5, 0.0) if effect_all else np.where(top & ph0, 0.5, np.where(top, -0.5 / 20, 0.0))
    return xp + rng.normal(0, 0.1, n) + plant, xp, dv


def test_rule10_t152_phase_only_effect_does_not_pass():
    """Regression (T-540/T-154/T-152 refutation): an effect that exists on one start offset of the 21-session grid passes
    on that grid alone but must not pass the pooled all-offset statistic, which is the primary one."""
    xt, xp, dv = _phase_only_fly()
    P0 = np.arange(0, xt.size, 21)
    assert bt.judge_spike_decile(xt[P0], xp[P0], dv[P0], 15, NB)["verdict"] == "supported"     # the lucky single grid
    j = bt.spike_decile_rule10(xt, xp, dv, 15, NB)
    assert j["verdict"] == "not_supported" and j["block"] == 42 and j["n"] == 20           # n in spike-decile months
    s = j["offsets_summary"]
    assert s["offsets"] == 21 and 1 <= s["pass"] <= 2 and s["stat"][1] > 0.4
    jp = bt.spike_decile_rule10(*_phase_only_fly(effect_all=True), 15, NB)                 # control: effect on every offset
    assert jp["verdict"] == "supported" and jp["offsets_summary"]["pass"] == 21


def test_rule10_t146_phase_only_effect_does_not_pass():
    rng = np.random.default_rng(21); n = 21 * 220; ph0 = np.arange(n) % 21 == 0
    xs = rng.normal(0, 1, n); xd = np.where(ph0, 0.5, 1.02) * xs + rng.normal(0, 0.05, n)
    P0 = np.arange(0, n, 21)
    assert bt.judge_std_ratio(xd[P0], xs[P0], 150, NB)["verdict"] == "supported"
    j = bt.std_ratio_rule10(xd, xs, 150, NB)
    assert j["verdict"] == "not_supported" and j["n"] == 220 and j["block"] == 42
    assert j["offsets_summary"]["pass"] == 1 and j["offsets_summary"]["offsets"] == 21
    ok = bt.std_ratio_rule10(0.5 * xs + rng.normal(0, 0.05, n), xs, 150, NB)
    assert ok["verdict"] == "supported" and ok["offsets_summary"]["pass"] == 21


def test_rule10_t147_gated_phase_only_effect_does_not_pass():
    rng = np.random.default_rng(22); n = 21 * 240; gate = rng.random(n) < 0.6; ph0 = np.arange(n) % 21 == 0
    d_all = rng.normal(0, 0.05, n) + np.where(ph0, 0.10, -0.10 / 20); d = d_all[gate]
    old = d_all[ph0 & gate]
    assert bt.judge_paired_halves({"flat IV": old, "SKEW tilt": old}, 80, "months", NB)["verdict"] == "supported"
    j = bt.paired_halves_rule10({"flat IV": d, "SKEW tilt": d}, gate, 80, "low-VIX monthly entries", NB)
    assert j["verdict"] == "not_supported" and j["n"] == bt.gated_units(gate) and 80 <= j["n"] <= 160
    assert j["offsets_summary"]["pass"] == 1
    miss = bt.paired_halves_rule10({"flat IV": d, "SKEW tilt": None}, gate, 80, "low-VIX monthly entries", NB)
    assert miss["verdict"] == "not_supported"                                            # a failing series still fails


def test_rule10_t149_pooled_weekly_offsets():
    rng = np.random.default_rng(23); n = 5 * 400; dv = rng.normal(0, 2, n)
    j = bt.spearman_rule10(rng.normal(0, 1, n), dv, 300, NB)
    assert j["verdict"] == "supported" and j["n"] == 400 and j["block"] == 20 and j["offsets_summary"]["offsets"] == 5
    ph0 = np.arange(n) % 5 == 0                                                         # correlated on one weekday only
    x = np.where(ph0, dv, 0.0) + rng.normal(0, 1, n)
    jj = bt.spearman_rule10(x, dv, 300, NB)
    assert jj["offsets_summary"]["pass"] == 4 and jj["verdict"] == "supported"           # pooled |rho| ~ 0.17: the claim holds


def test_rule10_t143_blocks_and_offsets():
    x, ratio = _regime_data(1.0)
    j = bt.judge_regime(x, ratio, x, 30, NB)
    assert j["block"] == 42 and j["trial_block"] == 21 and j["lower_deflated_trial_block"] is not None
    assert len(j["offsets"]) == 21 and j["offsets_summary"]["offsets"] == 21
    assert bt.n_holds(np.arange(100, 4300), 21) == 200


def test_rule10_calendar_harnesses_enter_on_monthly_expiries(fake):
    for h in ("b6_term_long_diagonal", "b6_term_pmcc", "b6_term_leaps_collar"):
        stat, n, verdict, reason = bt.HARNESSES[h](fake)
        d = date.fromisoformat(stat["first_entry"])
        assert d.weekday() == 4 and 15 <= d.day <= 21 and "rule 10(a)" in reason
        assert stat["offsets_summary"]["offsets"] == 21 and "not the calendar the claim names" in reason
    for h in ("b6_term_double_calendar", "b6_term_double_diagonal", "b6_term_ratio_calendar", "b6_term_calendarised_fly"):
        stat, n, verdict, reason = bt.HARNESSES[h](fake)
        assert "rule 10(b)" in reason and stat["offsets_summary"]["offsets"] in (5, 21) and stat["block"] in (20, 42)


def test_rule10_t155_harness_on_the_monthly_calendar(fake):
    """Regression (rule 10a/10b, T-155) end to end: tested puts live on standard monthly expiries, the pooled daily entries use
    blocks of 2 x the longest entry-to-exit hold, and the one-entry-per-expiry 45-DTE run is reported."""
    stat, n, verdict, reason = bt.HARNESSES["b6_term_roll_tested_put"](fake)
    assert "rule 10(a)" in reason and "rule 10(b)" in reason and "next monthly expiry" in reason
    assert "+28 days" not in reason and "fresh 0.16-delta 45-DTE put" not in reason
    assert stat["tested_expiries"] and all(date.fromisoformat(d).weekday() == 4 and 15 <= int(d[8:]) <= 21 for d in stat["tested_expiries"])
    assert stat["block"] == 2 * stat["hold_sessions"] >= stat["decision_block"] and stat["hold_sessions"] > 21
    assert 27 <= stat["dte_entry"][0] <= stat["dte_entry"][1] == 45 <= stat["dte_entry"][2] <= 63
    assert stat["near_45"]["n_entries"] > 0 and len(stat["near_45"]["halves"]) == 2 and stat["n_tested_cycles"] > 0
    assert stat["offsets_summary"]["offsets"] >= 15 and n == stat["n"] > 0
