"""Batch-6c rates harnesses (T-373 Treasury carry + roll-down, T-377 SGOV vs DTB3, T-381 cross-asset carry composite,
T-430 credit spread timing, T-433 global bond carry, T-432 country-ETF dividend carry, T-474 Treasury butterfly) on
synthetic data only: for every core function a planted effect passes and a null does not; the bill conversions, the
ALFRED point-in-time reader, the as-of lookups, month-end periods, the composite's trailing weights, the butterfly's
block-shift null and the rule-5 path are checked directly; every harness runs JSON-safe on a fake archive, and missing
bundles give inconclusive. No archive, no network."""

import json
import math
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_rates as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def months_of(days):
    return sorted({d[:7] for d in days})


def px_from_levels(days, level_by_month, noise=None):
    """A price dict (days, close, adj, open) constant within each month at level_by_month[month] (x optional daily noise)."""
    c = np.array([level_by_month[d[:7]] for d in days], float)
    if noise is not None:
        c = c * noise
    return {"days": list(days), "close": c.copy(), "adj": c.copy(), "open": c.copy()}


def monthly_levels(months, rets, start=100.0):
    """level[months[i + 1]] = level[months[i]] (1 + rets[i])."""
    out, lvl = {}, start
    for i, mo in enumerate(months):
        out[mo] = lvl
        lvl *= 1.0 + rets[i]
    return out


BILLS0 = m.Bills({"1990-01-02": 0.0})


# ======================================================================================== small pieces ==

def test_bey_and_accrual_conversions():
    assert m.bey(5.0) == pytest.approx(100 * 365 * 0.05 / (360 - 91 * 0.05))
    assert m.bey(5.0) > 5.0
    dt = {"2020-01-01": 4.0}
    a_c, a_b, a_d = m.Accrual(dt, "cont"), m.Accrual(dt, "bey"), m.Accrual(dt, "disc")
    g_c, g_b, g_d = (a.growth("2020-01-02", "2021-01-01") for a in (a_c, a_b, a_d))
    assert g_d < g_c < g_b                                   # discount < continuous-equivalent < daily-compounded BEY
    assert g_c == pytest.approx(m.Bills(dt).growth("2020-01-02", "2021-01-01"), rel=1e-12)
    r = -math.log(1 - 0.04 * 91 / 360) / (91 / 365)
    assert math.log(g_c) == pytest.approx(r * 365 / 365, rel=1e-9)


def test_asof_strict_and_max_age():
    a = m.Asof({"2020-01-01": 1.0, "2020-01-10": 2.0}, max_age=5)
    assert a.at("2020-01-10") == 2.0
    assert a.at("2020-01-10", strict=True) is None          # 2020-01-01 is 9 days old: beyond max_age
    assert a.at("2020-01-12") == 2.0
    assert a.at("2020-01-20") is None
    assert m.Asof({"2020-01-01": 1.0}).at("2019-12-31") is None


def test_vintages_point_in_time():
    obs = {"2013-01": [("2013-06-03", "2014-01-31", 2.0, True, "2013-03-17"), ("2014-02-01", "9999-12-31", 2.1, False, None)],
           "2014-03": [("2014-04-12", "9999-12-31", 3.0, False, None)]}
    v = m.Vintages(obs)
    assert v.known("2013-01", "2013-03-10") is None          # before the lag-rule day
    assert v.known("2013-01", "2013-03-20") == 2.0           # pre-ALFRED: first-vintage value from lag_rule_at
    assert v.known("2013-01", "2014-03-01") == 2.1           # the vintage in force
    assert v.latest("2014-04-11") == ("2013-01", 2.1)
    assert v.latest("2014-04-30") == ("2014-03", 3.0)
    assert v.latest_vintage("2013-01") == 2.1


def test_rate_at_fill():
    r = {"EUR": {"2026-01": 2.0}}
    assert m._rate_at(r, "EUR", "2026-01") == (2.0, 0)
    assert m._rate_at(r, "EUR", "2026-05") == (2.0, 4)
    assert m._rate_at(r, "EUR", "2027-02")[0] is None
    assert m._rate_at(r, "EUR", "2025-12")[0] is None


def test_month_end_periods_skip_partial_and_incomplete():
    days = bdays("2020-06-01", "2020-10-05")
    adj = np.linspace(100, 101, len(days))
    p = m.month_end_periods(days, adj, "2020-06", "2020-10")
    assert p["labels"] == ["2020-07", "2020-08", "2020-09"]   # June has no prior month-end; October is not complete
    assert p["d0"][0] == "2020-06-30" and p["d1"][0] == "2020-07-31"


def test_sharpe_one_detects_positive_mean():
    rng = np.random.default_rng(0)
    pos = m.sharpe_ci(rng.normal(0.01, 0.02, 200))
    assert pos["ci"][0] > 0
    nul = m.sharpe_ci(rng.normal(0.0, 0.02, 200))
    assert nul["ci"][0] < 0 < nul["ci"][1]


def test_ols_nw_recovers_slopes():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(500, 2))
    y = 0.5 + 2 * X[:, 0] - 1 * X[:, 1] + rng.normal(0, 0.1, 500)
    r = m.ols_nw(y, X, 3)
    assert r["coef"][1] == pytest.approx(2, abs=0.05) and r["coef"][2] == pytest.approx(-1, abs=0.05)


# ======================================================================================= T-373 ==

def _t373(planted, seed=1):
    rng = np.random.default_rng(seed)
    days = bdays("2002-07-01")
    ms = months_of(days)
    neg = {mo: bool(rng.random() < 0.3) for mo in ms}
    rets = []
    for i, mo in enumerate(ms):
        prev_neg = neg[ms[i - 1]] if i else False             # the hold of month mo is decided at the end of mo - 1
        if planted:
            rets.append(rng.normal(-0.03, 0.01) if prev_neg else rng.normal(0.008, 0.02))
        else:
            rets.append(rng.normal(0.003, 0.025))
    px = {"TLT": px_from_levels(days, monthly_levels(ms, rets))}
    y = {"DGS20": {}, "DGS10": {}, "DTB3": {}}
    for d in days:
        a, b, c = (4.0, 4.3, 6.0) if neg[d[:7]] else (5.0, 4.5, 2.0)
        y["DGS20"][d], y["DGS10"][d], y["DTB3"][d] = a, b, c
    return px, y


def test_t373_signal_bey_and_switch_cost():
    px, y = _t373(True)
    res = m.curve_carry(px, y, m.Bills(y["DTB3"]))
    assert res["labels"][0] == "2002-08" and res["labels"][-1] == "2026-09"
    i = int(np.flatnonzero(res["sig"] < 0)[0])
    assert res["sig"][i] == pytest.approx((4.0 - m.bey(6.0)) / 12 + 17 * (4.0 - 4.3) / 120)
    assert res["cash_src"][i] == "DTB3" and res["ex_timed"][i] == pytest.approx(-m.T373_SWITCH if res["pos"][i - 1] == 1 else 0.0, abs=1e-12)
    assert res["n_switch"] == int(np.abs(np.diff(res["pos"])).sum())


def test_t373_planted_passes():
    px, y = _t373(True)
    j = m.judge_curve_carry(m.curve_carry(px, y, m.Bills(y["DTB3"])))
    assert j["n"] == 290
    assert j["test"]["diff"] > 0.15
    assert j["verdict"] == "supported", j["why"]


def test_t373_null_fails():
    px, y = _t373(False)
    j = m.judge_curve_carry(m.curve_carry(px, y, m.Bills(y["DTB3"])))
    assert j["verdict"] != "supported"


def test_t373_below_min_n_never_supported():
    px, y = _t373(True)
    j = m.judge_curve_carry(m.curve_carry(px, y, m.Bills(y["DTB3"])), min_n=400)
    assert j["verdict"] == "inconclusive"


# ======================================================================================= T-377 ==

def _sgov(drift_bp, dt=4.0, noise_bp=0.0, seed=2):
    rng = np.random.default_rng(seed)
    days = bdays("2020-06-01")
    acc = m.Accrual({"2019-01-01": dt}, "bey")
    adj = [100.0]
    for a, b in zip(days[:-1], days[1:]):
        g = acc.growth(a, b) * math.exp(drift_bp * 1e-4 * (m._ord(b) - m._ord(a)) / 365) * (1 + rng.normal(0, noise_bp * 1e-4 / 12))
        adj.append(adj[-1] * g)
    adj = np.array(adj)
    return {"days": days, "adj": adj, "close": adj, "open": adj}, {"2019-01-01": dt}


def test_t377_planted_passes():
    sg, dt = _sgov(-2.0, noise_bp=5)
    t = m.tracking_difference(sg, dt)
    assert t["n"] == 75 and t["labels"][0] == "2020-07"
    j = m.judge_tracking(t)
    assert abs(t["bey"]["mean_bp"]) < 10 and abs(t["cont"]["mean_bp"]) < 10
    assert j["verdict"] == "supported", j["why"]


def test_t377_null_fails():
    sg, dt = _sgov(-30.0, noise_bp=5)
    j = m.judge_tracking(m.tracking_difference(sg, dt))
    assert j["verdict"] == "not_supported"


def test_t377_fee_added_back():
    sg, dt = _sgov(-9.0)
    a, b = m.tracking_difference(sg, dt), m.tracking_difference(sg, dt, fee=0.0009)
    assert b["bey"]["mean_bp"] - a["bey"]["mean_bp"] == pytest.approx(9.0, abs=1e-6)


# ======================================================================================= T-430 ==

def _t430(planted, seed=3):
    rng = np.random.default_rng(seed)
    bd = bdays("1996-01-02")
    bms = months_of(bd)
    sig = {mo: 2.0 + math.sin(2 * math.pi * k / 50.0) + rng.normal(0, 0.05) for k, mo in enumerate(bms)}
    baa = {d: sig[d[:7]] for d in bd}
    on = {}
    for k, mo in enumerate(bms):
        if k >= 59:
            w = [sig[bms[k - j]] for j in range(60)]
            on[mo] = sig[mo] > float(np.median(w))
    days = bdays("2002-07-29")
    ms = months_of(days)
    rets = []
    for i, mo in enumerate(ms):
        prev = on.get(ms[i - 1], False) if i else False
        rets.append(rng.normal(0.01, 0.008) if (planted and prev) else rng.normal(0.0, 0.01))
    px = {"LQD": px_from_levels(days, monthly_levels(ms, rets)), "IEF": px_from_levels(days, {mo: 100.0 for mo in ms})}
    return px, baa


def test_t430_planted_passes():
    px, baa = _t430(True)
    res = m.credit_timing(px, baa, BILLS0)
    assert res["labels"][0] == "2003-01" and len(res["labels"]) == 285
    assert 0.3 < res["on"].mean() < 0.7
    j = m.judge_credit_timing(res)
    assert j["verdict"] == "supported", j["why"]


def test_t430_null_fails():
    px, baa = _t430(False)
    j = m.judge_credit_timing(m.credit_timing(px, baa, BILLS0))
    assert j["verdict"] != "supported"


def test_t430_switch_cost_and_hedge_ratio():
    px, baa = _t430(True)
    res = m.credit_timing(px, baa, BILLS0)
    k = int(np.flatnonzero(np.diff(res["on"]) != 0)[0]) + 1
    on = res["on"][k] > 0
    expect = (res["lqd"][k] - 8.5 / 7.5 * res["ief"][k] if on else 0.0) - m.T430_SWITCH
    assert res["ex_base"][k] == pytest.approx(expect, abs=1e-12)


# ======================================================================================= T-433 ==

def _t433(planted, seed=4):
    rng = np.random.default_rng(seed)
    ms = m._months("1988-01", "2026-09")
    cc = m.T433_CC
    lvl = {c: 0.5 * i for i, c in enumerate(cc)}                    # persistent carry ranking: NZ highest
    y = {c: {} for c in cc}
    cur = {c: 3.0 + lvl[c] for c in cc}
    for mo in ms:
        for i, c in enumerate(cc):
            if planted:
                drift = -0.03 if i >= 7 else (0.03 if i < 3 else 0.0)
                cur[c] += drift + rng.normal(0, 0.03)
                y[c][mo] = cur[c]
            else:
                y[c][mo] = 3.0 + rng.normal(0, 0.5)
    r3m = {m.T433_CCY[c]: {mo: 2.0 for mo in ms} for c in cc}
    vint = {}
    for c in cc:
        obs = {}
        for mo in ms:
            rs = (date.fromisoformat(m._month_last_day(mo)) + timedelta(days=10)).isoformat()
            obs[mo] = [(rs, "9999-12-31", y[c][mo], False, None)]
        vint[c] = m.Vintages(obs)
    return vint, y, r3m


def test_t433_pit_uses_released_prints_only():
    vint, y, r3m = _t433(True)
    res = m.bond_carry(vint, y, r3m, m._months("2010-01", "2010-03"))
    assert res["obs_lag_months"]["max"] == 3 and res["obs_lag_months"]["mean"] == 3.0   # t-2's print comes 10 days after its end
    w = m.bond_carry(vint, y, r3m, m._months("2010-01", "2010-03"), timing="worded")
    assert w["obs_lag_months"]["mean"] == 2.0


def test_t433_planted_passes():
    vint, y, r3m = _t433(True)
    res = m.bond_carry(vint, y, r3m, m._months("1990-01", "2026-09"))
    assert res["long"][-1] == ["NZ", "NO", "SE"] and res["short"][-1] == ["DE", "GB", "US"][::-1] or set(res["short"][-1]) == {"US", "DE", "GB"}
    top2 = m.bond_carry(vint, y, r3m, m._months("1990-01", "2026-09"), k=2)
    tw = m._window(res["labels"], *m.T433_TEST)
    fam = {"top3": res["net"][tw], "top2": top2["net"][m._window(top2["labels"], *m.T433_TEST)]}
    j = m.judge_bond_carry(res, {"r": 0.95, "ci": [0.93, 0.96], "n": 200}, fam)
    assert j["n"] == 201
    assert j["verdict"] == "supported", j["why"]


def test_t433_null_fails_and_corr_gate():
    vint, y, r3m = _t433(False)
    res = m.bond_carry(vint, y, r3m, m._months("1990-01", "2026-09"))
    tw = m._window(res["labels"], *m.T433_TEST)
    j = m.judge_bond_carry(res, {"r": 0.95, "ci": [0.93, 0.96], "n": 200}, {"top3": res["net"][tw]})
    assert j["verdict"] != "supported"
    vint, y, r3m = _t433(True)
    res = m.bond_carry(vint, y, r3m, m._months("1990-01", "2026-09"))
    tw = m._window(res["labels"], *m.T433_TEST)
    j = m.judge_bond_carry(res, {"r": 0.7, "ci": [0.6, 0.78], "n": 200}, {"top3": res["net"][tw]})
    assert j["verdict"] == "not_supported"                     # the approximation check fails decisively


def test_t433_synthetic_return_formula():
    vint, y, r3m = _t433(True)
    res = m.bond_carry(vint, y, r3m, ["2015-06"])
    x = res["x_us"]["2015-06"]
    assert x == pytest.approx((y["US"]["2015-05"] - 2.0) / 1200 - 8 * (y["US"]["2015-06"] - y["US"]["2015-05"]) / 100)


def test_ief_monthly_excess_alignment():
    days = bdays("2015-01-02", "2015-05-10")
    lv = {"2015-01": 100.0, "2015-02": 101.0, "2015-03": 99.0, "2015-04": 100.0, "2015-05": 100.0}
    me, av = m.ief_monthly_excess(px_from_levels(days, lv), BILLS0)
    assert me["2015-02"] == pytest.approx(0.01) and me["2015-03"] == pytest.approx(99 / 101 - 1)
    assert "2015-05" not in me                                  # incomplete month


# ======================================================================================= T-432 ==

SYMS10 = tuple("ABCDEFGHIJ")


def _t432(planted, seed=5, start="1999-01-04"):
    rng = np.random.default_rng(seed)
    days = bdays(start)
    ms = months_of(days)
    dyl = {s: 0.01 + 0.005 * i for i, s in enumerate(SYMS10)}
    series, divs = {}, {}
    for i, s in enumerate(SYMS10):
        if planted:
            mu = 0.012 if i >= 6 else (-0.012 if i < 4 else 0.0)
            rets = rng.normal(mu, 0.015, len(ms))
        else:
            rets = rng.normal(0.004, 0.04, len(ms))
        lv = monthly_levels(ms, rets)
        noise = np.exp(rng.normal(0, 0.002, len(days)))
        series[s] = px_from_levels(days, lv, noise)
        dv = {}
        for d, c in zip(series[s]["days"], series[s]["close"]):
            if d[5:7] in ("03", "06", "09", "12") and d[:7] not in {x[:7] for x in dv}:
                dv[d] = dyl[s] * c / 4
        divs[s] = dv
    rates = {"USD": {mo: 2.0 for mo in ms}}
    return series, divs, rates, {s: "USD" for s in SYMS10}


def test_t432_panel_dividend_yield_and_rate_lag():
    series, divs, rates, ccys = _t432(True)
    rates["USD"]["2010-05"] = 7.0
    P = m.country_panel(series, divs, rates, ccys, "2005-01", "2026-09")
    k = P["labels"].index("2010-07")                            # decision at the end of 2010-06 uses the 2010-05 rate
    i = P["syms"].index("J")
    assert P["dy"][k, i] == pytest.approx(dyl := 0.01 + 0.005 * 9, rel=0.15)
    assert P["carry"][k, i] == pytest.approx(P["dy"][k, i] - 0.07)
    assert P["carry"][k + 1, i] == pytest.approx(P["dy"][k + 1, i] - 0.02)


def test_t432_planted_passes():
    series, divs, rates, ccys = _t432(True)
    P = m.country_panel(series, divs, rates, ccys, "2001-01", "2026-09")
    base = m.country_book(P)
    assert set(np.flatnonzero(base["W"][-1] > 0)) == {6, 7, 8, 9} and set(np.flatnonzero(base["W"][-1] < 0)) == {0, 1, 2, 3}
    win = lambda b: b["net"][m._window(b["labels"], *m.T432_TEST)]
    fam = {"base": win(base), "top3": win(m.country_book(P, k=3))}
    j = m.judge_country_carry(base, fam)
    assert j["n"] == 189
    assert j["verdict"] == "supported", j["why"]


def test_t432_null_fails():
    series, divs, rates, ccys = _t432(False)
    P = m.country_panel(series, divs, rates, ccys, "2001-01", "2026-09")
    base = m.country_book(P)
    j = m.judge_country_carry(base, {"base": base["net"][m._window(base["labels"], *m.T432_TEST)]})
    assert j["verdict"] != "supported"


def test_t432_costs_and_borrow_charged():
    series, divs, rates, ccys = _t432(True)
    P = m.country_panel(series, divs, rates, ccys, "2001-01", "2026-09")
    b0 = m.country_book(P, cost=0.0, borrow=0.0)
    b1 = m.country_book(P)
    assert np.all(b1["net"] <= b0["net"] + 1e-15)
    assert b1["borrow"][5] == pytest.approx(m.T432_BORROW * 1.0 * P["hold_days"][np.flatnonzero(np.isin(P["labels"], b1["labels"][5]))[0]] / 365)


def test_t432_weighting_choice_reports_both():
    series, divs, rates, ccys = _t432(True)
    P = m.country_panel(series, divs, rates, ccys, "2001-01", "2026-09")
    sel = m.choose_weighting(P, ("2001-01", "2010-12"))
    assert sel["chosen"] in ("equal", "invvol") and sel["fit"]["equal"]["months"] > 100


# ======================================================================================= T-474 ==

def _t474(planted, seed=6):
    rng = np.random.default_rng(seed)
    days = bdays("2005-01-03")
    n = len(days)
    fly = np.zeros(n)
    for t in range(1, n):
        if planted:
            jump = rng.choice([-0.3, 0.3]) if rng.random() < 0.012 else 0.0
            fly[t] = 0.93 * fly[t - 1] + rng.normal(0, 0.004) + jump
        else:
            fly[t] = fly[t - 1] + rng.normal(0, 0.03)
    level = np.cumsum(rng.normal(0, 0.02, n))
    y2, y10 = 2.0 + level, 3.0 + level
    y5 = (y2 + y10 + fly) / 2
    ylds = {"DGS2": dict(zip(days, y2)), "DGS5": dict(zip(days, y5)), "DGS10": dict(zip(days, y10))}
    px = {}
    for sym, y, D in (("SHY", y2, 1.9), ("IEI", y5, 4.4), ("IEF", y10, 7.3)):
        p = np.r_[100.0, 100.0 * np.cumprod(1 - D * np.diff(y) / 100)]
        px[sym] = {"days": days, "adj": p, "close": p, "open": p}
    return px, ylds


def test_t474_fly_z_and_known_day():
    px, ylds = _t474(True)
    zd, zv = m.fly_series(ylds)
    assert np.isnan(zv[:249]).all() and np.isfinite(zv[249:]).all()
    f = np.array([2 * ylds["DGS5"][d] - ylds["DGS2"][d] - ylds["DGS10"][d] for d in zd])
    w = f[300 - 249:301]
    assert zv[300] == pytest.approx((f[300] - w.mean()) / w.std(ddof=1))
    sim = m.fly_trades(px, zd, zv, BILLS0)
    e, x, sg = sim["trades"][0]
    j = zd.index(sim["sess"][e])
    assert abs(zv[j - 1]) > 2 and np.sign(zv[j - 1]) == sg      # the z of the print dated before the entry session
    assert all(x2 - e2 <= m.T474_MAX_HOLD for e2, x2, _ in sim["trades"])


def test_t474_planted_passes():
    px, ylds = _t474(True)
    zd, zv = m.fly_series(ylds)
    sim = m.fly_trades(px, zd, zv, BILLS0)
    pd_, pz = m.fly_series(ylds, "pca")
    pca = m.fly_trades(px, pd_, pz, BILLS0)
    assert sim["net"].size >= 30
    assert sim["daily"].sum() == pytest.approx(sim["net"].sum(), rel=1e-9, abs=1e-12)
    j = m.judge_butterfly(sim, {"f": sim["net"], "p": pca["net"]}, {"f": sim["daily"], "p": pca["daily"]}, True)
    assert j["block_shift"]["p"] < 0.05
    assert j["verdict"] == "supported", j["why"]


def test_t474_null_fails():
    px, ylds = _t474(False)
    zd, zv = m.fly_series(ylds)
    sim = m.fly_trades(px, zd, zv, BILLS0)
    j = m.judge_butterfly(sim, {"f": sim["net"]}, {"f": sim["daily"]}, True)
    assert j["verdict"] != "supported"


def test_t474_trade_costs():
    px, ylds = _t474(True)
    zd, zv = m.fly_series(ylds)
    sim = m.fly_trades(px, zd, zv, BILLS0)
    cost = 2 * m.T474_COST * sum(abs(w) for w in m.T474_LEGS.values())
    e, x, sg = sim["trades"][0]
    shortn = sum(max(-sg * w, 0) for w in m.T474_LEGS.values())
    borrow = m.T474_BORROW * shortn * (sim["o"][x] - sim["o"][e]) / 365
    assert sim["gross"][0] - sim["net"][0] == pytest.approx(cost + borrow)
    assert sum(m.T474_LEGS[s] * m.T474_DUR[s] for s in m.T474_LEGS) == pytest.approx(0.0)   # DV01 neutral


def test_t474_block_shift_zero_shift_is_observed():
    px, ylds = _t474(True)
    zd, zv = m.fly_series(ylds)
    sim = m.fly_trades(px, zd, zv, BILLS0)
    full = m._trade_pnl(sim, sim["trades"], shift=len(sim["o"]))   # a full rotation lands every trade back in place
    assert full["net"] == pytest.approx(sim["net"])


# ======================================================================================= T-381 ==

def _sleeves(mu, seed=7, names=("fx", "bonds", "eq", "credit")):
    rng = np.random.default_rng(seed)
    ms = m._months("2009-01", "2026-09")
    return {nm: {mo: float(rng.normal(mu, 0.01 * (k + 1))) for mo in ms} for k, nm in enumerate(names)}


def test_t381_trailing_weights():
    s = _sleeves(0.002)
    c = m.carry_composite(s)
    t = c["labels"].index("2015-06")
    past = [s["eq"][m._month_add("2015-06", -j)] for j in range(1, 37)]
    assert c["weights"][t]["eq"] == pytest.approx(0.05 / (np.std(past, ddof=1) * math.sqrt(12)))
    assert c["ret"][t] == pytest.approx(sum(c["weights"][t][k] * s[k]["2015-06"] for k in s))
    s["fx"].pop("2014-03")
    c2 = m.carry_composite(s)
    assert "2014-03" in c2["dropped"] and "2017-03" in c2["dropped"] and "2017-04" not in c2["dropped"]


def test_t381_derisk_halves_after_drawdown():
    s = {"a": {mo: 0.0 for mo in m._months("2009-01", "2026-09")}}
    for mo in m._months("2009-01", "2012-12"):
        s["a"][mo] = 0.01 * (1 if int(mo[5:7]) % 2 else -1)
    s["a"]["2013-01"] = -2.0                                      # a -2 return x weight 0.05/(0.01 sqrt 12)/... = a deep loss
    s["a"]["2013-02"] = 0.01
    c = m.carry_composite(s, derisk=True)
    assert "2013-02" in c["halved"]


def test_t381_planted_passes():
    s = _sleeves(0.004)
    comp, dr = m.carry_composite(s), m.carry_composite(s, derisk=True)
    assert comp["ret"].size == 165
    j = m.judge_composite(comp, dr, {"c": comp["ret"], "d": dr["ret"], **{k: np.array(list(v.values())[-165:]) for k, v in s.items()}})
    assert j["verdict"] == "supported", j["why"]


def test_t381_null_fails():
    s = _sleeves(0.0, seed=8)
    comp, dr = m.carry_composite(s), m.carry_composite(s, derisk=True)
    j = m.judge_composite(comp, dr, {"c": comp["ret"]})
    assert j["verdict"] != "supported"


# ======================================================================================= harnesses on a fake archive ==

class FakeArchive:
    def __init__(self, bundles, created="2026-10-15T08:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


_EPOCH = date(1970, 1, 1).toordinal()


def _yahoo(p):
    rows = []
    for d, c, a, o in zip(p["days"], p["close"], p["adj"], p["open"]):
        od = date.fromisoformat(d).toordinal()
        rows.append({"available_at": date.fromordinal(od + 1).isoformat() + "T14:30:00+00:00",
                     "value": {"t": (od - _EPOCH) * 86400 + 14.5 * 3600, "open": float(o), "high": float(c), "low": float(c),
                               "close": float(c), "adjclose": float(a)}})
    return rows


def _fred(series):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(v)}} for d, v in sorted(series.items())]


def _full_archive():
    rng = np.random.default_rng(11)
    b = {}
    days = bdays("2002-07-29")
    ms = months_of(days)
    for sym in ("TLT", "IEF", "IEI", "SHY", "BIL", "SGOV", "LQD", "HYG", "DBC"):
        start = {"SGOV": "2020-06-01", "BIL": "2007-05-30", "IEI": "2007-01-11", "HYG": "2007-04-11"}.get(sym, days[0])
        dd = [d for d in days if d >= start]
        lv = monthly_levels(months_of(dd), rng.normal(0.003, 0.02, len(months_of(dd))))
        b[m.dh(sym)] = _yahoo(px_from_levels(dd, lv, np.exp(rng.normal(0, 0.002, len(dd)))))
    for sym in m.T432_ETFS:
        lv = monthly_levels(ms, rng.normal(0.004, 0.04, len(ms)))
        p = px_from_levels(days, lv, np.exp(rng.normal(0, 0.003, len(days))))
        b[m.dh(sym)] = _yahoo(p)
        if sym != "SPY":
            ev, seen = [], set()
            for d, c in zip(p["days"], p["close"]):
                if d[5:7] in ("06", "12") and d[:7] not in seen:
                    seen.add(d[:7])
                    ev.append({"kind": "dividend", "available_at": d + "T14:30:00+00:00",
                               "value": {"type": "dividend", "ex_date": d, "amount": float(c * rng.uniform(0.005, 0.02))}})
            b[m.de(sym)] = ev
    fd = bdays("1996-01-02")
    for sid, base in (("DGS1", 2.0), ("DGS2", 2.2), ("DGS3", 2.4), ("DGS5", 2.8), ("DGS7", 3.1), ("DGS10", 3.4), ("DGS20", 3.8)):
        b[m.fr(sid)] = _fred({d: base + 0.5 * math.sin(k / 400.0) + rng.normal(0, 0.02) for k, d in enumerate(fd)})
    b[m.DTB3_B] = _fred({d: 2.0 + 1.5 * math.sin(k / 700.0) for k, d in enumerate(fd)})
    b[m.fr("BAA10Y")] = _fred({d: 2.0 + math.sin(k / 300.0) for k, d in enumerate(fd)})
    b[m.fr("DFF")] = _fred({d: 2.0 for d in fd})
    om = m._months("2004-01", "2026-09")
    for cc, sid in m.T433_SID.items():
        yv = {mo: 3.0 + rng.normal(0, 0.3) for mo in om}
        b[m.fr(sid)] = [{"available_at": m._month_last_day(mo) + "T23:59:59+00:00",
                         "value": {"day": mo + "-01", "value": yv[mo]}} for mo in om]
        rows = []
        for mo in om:
            rs = (date.fromisoformat(m._month_last_day(mo)) + timedelta(days=14)).isoformat()
            rows.append({"available_at": rs + "T23:59:59+00:00",
                         "value": {"day": mo + "-01", "value": yv[mo], "realtime_start": rs, "realtime_end": None,
                                   "first_release": True, "first_vintage": False, "lag_rule_at": None}})
        b[m.al(sid)] = rows
    rm = m._months("1995-01", "2026-08")
    ccys = ("USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "NOK", "SEK", "MXN", "ZAR")
    b[m.RATES_B] = [{"available_at": mo + "-28T00:00:00+00:00", "value": {"month": mo, "ccy": c, "rate3m": 1.0 + i * 0.4 + rng.normal(0, 0.1)}}
                    for i, c in enumerate(ccys) for mo in rm if not (c in ("EUR", "GBP") and mo > "2026-01")]
    sd = bdays("2000-01-03")
    b[m.SPOT_B] = [{"available_at": d + "T17:00:00+00:00", "value": {"day": d, "ccy": c, "usd_per_unit": float(v)}}
                   for c in ccys[1:] for d, v in zip(sd, np.exp(np.cumsum(rng.normal(0, 0.005, len(sd)))))]
    b[m.FOMC_B] = [{"available_at": "2010-01-01T00:00:00+00:00", "value": {"decision_day": d}}
                   for d in ("2010-03-16", "2015-12-16", "2020-03-15")]
    b[m.USREC_B] = [{"available_at": mo + "-28T00:00:00+00:00", "value": {"day": mo + "-01", "value": 1.0 if mo in ("2020-03", "2020-04") else 0.0}}
                    for mo in m._months("2000-01", "2026-08")]
    return FakeArchive(b)


@pytest.fixture(scope="module")
def fake():
    return _full_archive()


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_every_harness_runs_json_safe(fake, name):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES[name](fake)
    json.dumps(stat, allow_nan=False)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert isinstance(n, int) and n > 0
    assert " — " in reason


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason and " — " in reason


def test_optional_bundles_are_optional(fake):
    b = dict(fake.bundles)
    for k in ("daily-history-SGOV", "daily-history-BIL", "daily-history-HYG", m.FOMC_B, m.USREC_B, m.fr("DFF"), "daily-history-DBC"):
        b.pop(k, None)
    arch = FakeArchive(b)
    for name in ("b6c_rates_treasury_carry_rolldown", "b6c_rates_credit_spread_timing", "b6c_rates_treasury_butterfly",
                 "b6c_rates_cross_asset_carry", "b6c_rates_equity_country_carry"):
        m._CACHE.clear()
        stat, n, verdict, reason = m.HARNESSES[name](arch)
        assert "missing_bundles" not in stat and n > 0


def test_maps_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-373", "T-377", "T-381", "T-430", "T-433", "T-474", "T-432"}
    assert all(k.startswith("b6c_rates_") and k == k.lower() for k in m.HARNESSES)
    assert m.T381_N_TRIALS == 34 and m.T381_N_TRIALS_EX_CRYPTO == 24
