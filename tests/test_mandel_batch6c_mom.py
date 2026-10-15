"""Batch-6c momentum harnesses (T-300 TSMOM vs historical mean, T-301 SMA drawdown vs random timing, T-308 residual
momentum, T-311 crash filter, T-317 crisis smile, T-310 vol-scaled trend DiD, T-481 cross-asset TSMOM) on synthetic
data only: for every core function a planted effect passes and a null does not; calendars, bills, spell permutations,
Holm, drawdowns, turnover and the synthetic bond are checked directly; every harness runs on a fake archive (JSON-safe,
missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_mom as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start="1993-01-29", end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cdays(start="2014-09-17", end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def month_no(days):
    return np.array([int(d[:4]) * 12 + int(d[5:7]) - 1 for d in days])


def price(r, s0=100.0):
    return s0 * np.cumprod(1 + np.asarray(r, float))


BILLS = m.Bills({"1950-01-03": 3.0})
DAYS = bdays()
MO = month_no(DAYS)


def regime_returns(seed, period=24, mu=0.025, vol=0.008, phase=0, days=DAYS):
    rng = np.random.default_rng(seed)
    mo = month_no(days)
    k = (mo - mo[0] + phase) // period
    sign = np.where(k % 2 == 0, 1.0, -1.0)
    return sign * mu / 21 + rng.normal(0, vol, len(days))


def iid_returns(seed, mu=0.0003, vol=0.009, n=len(DAYS)):
    return np.random.default_rng(seed).normal(mu, vol, n)


# ---------------------------------------------------------------------------------------- calendars, bills --

def test_month_grid_decision_and_fill_and_incomplete_month():
    days = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28", "2020-03-02", "2020-03-03"]
    g = m.month_grid(days)
    assert g["months"] == ["2020-01", "2020-02"]                  # March has no later bar: not a decision month
    assert [days[i] for i in g["me"]] == ["2020-01-31", "2020-02-28"]
    assert [days[i] for i in g["ex"]] == ["2020-02-03", "2020-03-02"]


def test_bill_logcum_matches_bills_growth_and_discount_conversion():
    b = m.Bills({"2020-01-02": 4.0, "2020-03-02": 1.0})
    days = ["2019-12-20", "2020-01-02", "2020-01-03", "2020-02-14", "2020-03-02", "2020-03-03", "2020-06-30"]
    C = m.bill_logcum(b, days)
    for i in range(len(days)):
        for j in range(i, len(days)):
            assert math.exp(C[j] - C[i]) == pytest.approx(b.growth(days[i], days[j]), rel=1e-12)
    r = -math.log(1 - 0.04 * 91 / 360) / (91 / 365)                # rule 7: discount yield -> continuous rate
    assert b.rate("2020-02-01") == pytest.approx(r)


def test_spell_paths_preserve_count_lengths_and_never_merge():
    f = np.zeros(120, bool)
    for s, l in ((3, 5), (20, 1), (40, 12), (90, 3)):
        f[s:s + l] = True
    kv = np.arange(120, dtype=float)
    paths, src = m.spell_paths(f, 400, np.random.default_rng(1))
    for p, sr in zip(paths, src):
        rr = m.runs(p)
        assert sorted(l for _, l in rr) == [1, 3, 5, 12]
        assert p.sum() == f.sum()
        # every carried value comes from inside an original spell, in order within the spell
        for s, l in rr:
            vals = kv[sr[s:s + l]]
            assert np.all(f[sr[s:s + l]]) and np.all(np.diff(vals) == 1)
    assert paths[:, 0].mean() > 0 and paths[:, -1].mean() > 0      # spells can sit at either edge
    p2, s2 = m.spell_paths(f, 10, np.random.default_rng(1), with_src=False)
    assert s2 is None and p2.shape == (10, 120)


def test_episodes_merge_short_gaps():
    f = np.zeros(30, bool)
    f[2:4] = True
    f[6:8] = True                # gap 2 -> merged
    f[12:13] = True              # gap 4 -> new episode
    assert len(m.runs(f)) == 3 and len(m.episodes(f, 2)) == 2


def test_holm_adjusted_and_bounds():
    ps = {"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.002}
    h = m.holm_adjusted(ps)
    assert h["d"] == pytest.approx(0.008) and h["a"] == pytest.approx(0.03)
    assert h["c"] == pytest.approx(0.06) and h["b"] == pytest.approx(0.06)
    full = m.holm_primary(ps, "a")
    assert full["adj"] == pytest.approx(0.03)
    part = m.holm_primary({"a": 0.01, "b": None, "c": 0.5}, "a")
    assert part["adj"] is None and part["lo"] <= 0.03 <= part["hi"] == pytest.approx(0.03)
    assert m.holm_row(part, "x")[1] is True                                              # Bonferroni 0.03 < 0.05
    mid = m.holm_primary({"a": 0.02, "b": None, "c": 0.5}, "a")
    assert mid["lo"] == pytest.approx(0.04) and mid["hi"] == pytest.approx(0.06)
    assert m.holm_row(mid, "x")[1] is None                                               # unresolved
    assert m.holm_row(m.holm_primary({"a": 0.03, "b": None, "c": 0.5}, "a"), "x")[1] is False   # >= 2 x 0.03
    assert m.holm_row(m.holm_primary({"a": 0.001, "b": None}, "a"), "x")[1] is True       # Bonferroni 0.002


def test_drawdowns_and_turnover():
    r = np.array([0.1, -0.5, 0.2, 0.1])
    assert m.mdd_depth(r)[0] == pytest.approx(0.5)
    L = np.cumsum(np.log1p(r))[None]
    assert m.mdd_from_logwealth(L)[0] == pytest.approx(0.5)
    w = np.array([[0.5], [0.5]])
    R = np.array([[1.0], [0.0]])
    pre = np.array([0.5, 0.0])
    # after +100% on half the book the asset is 2/3 of the account; rebalancing to 1/2 trades 1/6
    assert m.drift_turnover(w, R, pre)[1] == pytest.approx(1 / 6)


def test_ma_state_band_hysteresis():
    x = np.array([10, 10, 10, 10.5, 10.05, 9.9, 9.5, 10.0, 10.6])
    st = m.ma_state(x, 3, 0.02, "SMA")
    assert np.isnan(st[0]) and st[3] == 1.0
    assert st[4] == 1.0                                  # inside the band: unchanged
    assert st[6] == 0.0                                  # below MA (1 - 2%)


def test_synthetic_bond_formula():
    y = np.array([5.0, 6.0, 5.5])
    r = m.synthetic_bond(y, 8.0)
    assert r[0] == pytest.approx(0.05 / 12 - 8 * 0.01) and r[1] == pytest.approx(0.06 / 12 + 8 * 0.005)
    assert 6.3 < m.par_duration(9.0) < 6.7 and 9.0 < m.par_duration(1.5) < 9.5


def test_rebalanced_five_sleeve_logwealth_matches_loop():
    rng = np.random.default_rng(3)
    n, S = 40, 3
    lr = rng.normal(0, 0.01, (S, n))
    seg = np.zeros(n, bool)
    seg[[0, 13, 27]] = True
    cell = {"sleeves": {f"s{i}": {"lR": lr[i], "lrf": np.zeros(n)} for i in range(S)}, "seg_start": seg,
            "sidx": np.maximum.accumulate(np.where(seg, np.arange(n), 0)), "seg_end": np.r_[seg[1:], True]}
    inm = {f"s{i}": np.ones((1, n), bool) for i in range(S)}
    L = m._t301_logwealth(cell, inm, {f"s{i}": 0.0 for i in range(S)})[0]
    V, out = 1.0, []
    hold = np.full(S, 1.0 / S)
    for t in range(n):
        if seg[t]:
            hold = np.full(S, V / S)
        hold = hold * np.exp(lr[:, t])
        V = hold.sum()
        out.append(math.log(V))
    assert np.allclose(L, out)


# ------------------------------------------------------------------------------------------- T-300 TSMOM --

def _t300_assets(planted):
    out = {}
    for k, s in enumerate(("SPY", "QQQ", "GLD")):
        r = regime_returns(10 + k, period=24, mu=0.03, phase=7 * k) if planted else iid_returns(20 + k, mu=0.0004)
        out[s] = (DAYS, price(r))
    return out


def test_t300_planted_trend_beats_historical_mean():
    j = m.tsmom_vs_hist_mean(_t300_assets(True), BILLS)
    assert j["n"] >= 300 and j["mean"]["est"] > 0
    assert j["verdict"] == "supported", j["why"]


def test_t300_null_does_not_pass():
    j = m.tsmom_vs_hist_mean(_t300_assets(False), BILLS)
    assert j["verdict"] != "supported"


def test_t300_family_is_the_declared_grid():
    assert len(m.T300_FAMILY) == 56 and m.T300_N_TRIALS == 104 and m.T300_PRIMARY in m.T300_FAMILY


# ------------------------------------------------------------------------------------ T-301 SMA vs random --

BEARS = (("2000-04", "2002-09", -0.0010), ("2007-11", "2009-02", -0.0022), ("2015-06", "2016-02", -0.0012), ("2022-01", "2022-10", -0.0018))


def _bear_spy(seed, planted):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0005, 0.007, len(DAYS))
    if planted:
        for a, z, mu in BEARS:
            mm = np.array([a <= d[:7] <= z for d in DAYS])
            r[mm] += mu - 0.0005
    return price(r)


T301_TEST_FAMILY = (m.T301_PRIMARY, (12, 0.0, "SMA", "monthly", "SPY"), (10, 0.01, "EMA", "monthly", "SPY"))


def test_t301_planted_bears_rule_beats_random_timing():
    j = m.sma_timing_vs_random({"SPY": (DAYS, _bear_spy(5, True))}, BILLS, family=T301_TEST_FAMILY, n_null=1000, n_refine=2000)
    assert j["primary"]["share_worse_1000"] >= 0.95
    assert j["verdict"] == "supported", j["why"]


def test_t301_null_does_not_pass():
    j = m.sma_timing_vs_random({"SPY": (DAYS, _bear_spy(6, False))}, BILLS, family=T301_TEST_FAMILY, n_null=1000, n_refine=2000)
    assert j["verdict"] != "supported"


def test_t301_family_is_96_and_daily_cell_windows():
    assert len(m.T301_FAMILY) == 96 and len(set(m.T301_FAMILY)) == 96
    five = {s: (DAYS, price(iid_returns(30 + k))) for k, s in enumerate(m.FIVE)}
    cell = m._t301_sleeves(five, BILLS, "five-sleeve", "daily", "1994-01")
    pos = m._t301_positions(cell, 12, 0.0, "SMA", "daily")
    assert all(p.size == len(cell["labels"]) for p in pos.values())
    st = m.ma_state(cell["sleeves"]["SPY"]["x"], 12 * m.DAYS_PER_MONTH, 0.0, "SMA")
    assert np.isfinite(st[cell["sleeves"]["SPY"]["lo"] - 2])        # every lookback defined on the shared window


# ------------------------------------------------------------------------------------ T-308 residual mom --

def _t308_data(planted, seed=7):
    rng = np.random.default_rng(seed)
    mo = MO - MO[0]
    nm = mo.max() + 1
    mkt = rng.normal(0.0, 0.009, len(DAYS))
    betas = np.linspace(0.4, 1.6, 9)
    sec = {}
    for i, s in enumerate(m.SECTORS):
        a = np.zeros(nm)
        if planted:
            for t in range(1, nm):
                a[t] = 0.97 * a[t - 1] + rng.normal(0, 0.015 * math.sqrt(1 - 0.97 ** 2))
        r = betas[i] * mkt + a[mo] / 21 + rng.normal(0, 0.006, len(DAYS))
        sec[s] = (DAYS, price(r))
    return sec, (DAYS, price(mkt))


def test_t308_planted_residual_momentum_wins():
    sec, spy = _t308_data(True)
    j = m.residual_vs_total(sec, spy, BILLS)
    assert j["n"] >= 280
    assert j["verdict"] == "supported", j["why"]


def test_t308_null_does_not_pass():
    sec, spy = _t308_data(False, seed=8)
    j = m.residual_vs_total(sec, spy, BILLS)
    assert j["verdict"] != "supported"
    assert -1 <= j["mean_rank_corr"] <= 1


# ------------------------------------------------------------------------------------ T-311 crash filter --

def _t311_data(planted, seed=11):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.007, len(DAYS))
    for y in (1995, 2001, 2005, 2009, 2013, 2017, 2021):
        mm = np.array([f"{y}-01" <= d[:7] <= f"{y + 1}-02" for d in DAYS])
        r[mm] = rng.normal(-0.0015, 0.022, mm.sum())
    spy = price(r)
    g = m.month_grid(DAYS)
    dec_days = [DAYS[i] for i in g["me"]]
    A = m._spy_indicators(DAYS, spy, dec_days, 24, 0.8)
    months = g["months"]
    k_act = [k for k in range(len(A)) if A[k]]
    if not planted:
        k_act = sorted(rng.choice(np.arange(60, len(A)), size=len(k_act), replace=False).tolist())
    squeeze = set(k_act)
    idx_month = {mm: [i for i, d in enumerate(DAYS) if d[:7] == mm] for mm in months}
    trend = np.zeros((len(months) + 1, 9))
    for t in range(1, len(months) + 1):
        trend[t] = 0.9 * trend[t - 1] + rng.normal(0, 0.012, 9)
    P = np.full((len(DAYS), 9), np.nan)
    lvl = np.full(9, 100.0)
    last_me = {}
    allm = sorted(set(d[:7] for d in DAYS))
    for mi, mm in enumerate(allm):
        ii = idx_month[mm] if mm in idx_month else [i for i, d in enumerate(DAYS) if d[:7] == mm]
        bump = np.zeros(9)
        prev = mi - 1                                                    # decision at the end of the previous month
        if prev in squeeze and prev >= 13:
            mom = P[last_me[prev - 1]] / P[last_me[prev - 12]] - 1
            o = np.argsort(-mom)
            bump[o[-3:]] = 0.25
            bump[o[:3]] = -0.05
        for q, i in enumerate(ii):
            rr = 0.8 * r[i] + trend[mi] / 21 + rng.normal(0, 0.005, 9)
            if q >= 1:
                rr = rr + bump / max(1, len(ii) - 1)
            lvl = lvl * (1 + rr)
            P[i] = lvl
        last_me[mi] = ii[-1]
    sec = {s: (DAYS, P[:, k].copy()) for k, s in enumerate(m.SECTORS)}
    return sec, (DAYS, spy)


T311_TEST_FAMILY = (m.T311_PRIMARY, (24, 0.8, "short", "binary"))


def test_t311_planted_filter_beats_random_spells():
    sec, spy = _t311_data(True)
    j = m.crash_filter_vs_random(sec, spy, BILLS, family=T311_TEST_FAMILY, n_null=400)
    assert j["primary"]["n_episodes"] >= 5
    assert j["verdict"] == "supported", j["why"]


def test_t311_null_does_not_pass():
    sec, spy = _t311_data(False, seed=12)
    j = m.crash_filter_vs_random(sec, spy, BILLS, family=T311_TEST_FAMILY, n_null=400)
    assert j["verdict"] != "supported"


def test_t311_below_episode_gate_is_never_a_soft_failure():
    sec, spy = _t311_data(True)
    j = m.crash_filter_vs_random(sec, spy, BILLS, family=((24, 0.95, "both", "binary"),), n_null=200)
    if j["primary"]["n_episodes"] < 5:
        assert j["verdict"] in ("inconclusive", "not_supported")
        names = [c[0] for c in j["criteria"]]
        assert any("episode" in nm for nm in names)


def test_t311_family_is_24():
    assert len(m.T311_FAMILY) == 24 and m.T311_PRIMARY in m.T311_FAMILY


# ------------------------------------------------------------------------------------- T-317 crisis smile --

def _t317_data(planted, seed=17):
    rng = np.random.default_rng(seed)
    if planted:
        spy_r = regime_returns(seed, period=18, mu=0.045, vol=0.007)
        k = (MO - MO[0]) // 18
        tlt_r = -np.where(k % 2 == 0, 1.0, -1.0) * 0.02 / 21 + rng.normal(0, 0.005, len(DAYS))
    else:
        spy_r = iid_returns(seed, mu=0.0, vol=0.01)
        tlt_r = iid_returns(seed + 1, mu=0.0, vol=0.006)
    return {"SPY": (DAYS, price(spy_r)), "TLT": (DAYS, price(tlt_r)), "GLD": (DAYS, price(iid_returns(seed + 2, mu=0.0, vol=0.008)))}


T317_TEST_FAMILY = (m.T317_PRIMARY, ("monthly", False, "LS"))


def test_t317_planted_trends_are_convex_beyond_mechanical():
    j = m.crisis_smile(_t317_data(True), BILLS, family=T317_TEST_FAMILY, n_sim=150, n_boot=300, reps=2)
    assert j["n"] >= 100 and j["primary"]["excess"] > 0
    assert j["verdict"] == "supported", j["why"]


def test_t317_null_does_not_pass():
    j = m.crisis_smile(_t317_data(False), BILLS, family=T317_TEST_FAMILY, n_sim=150, n_boot=300, reps=2)
    assert j["verdict"] != "supported"


# ---------------------------------------------------------------------------------------- T-310 vol DiD --

def _ohlc(days, adj):
    return {"days": list(days), "close": adj.copy(), "adj": adj.copy(), "open": np.r_[adj[0], adj[:-1]],
            "high": np.maximum(adj, np.r_[adj[0], adj[:-1]]) * 1.002, "low": np.minimum(adj, np.r_[adj[0], adj[:-1]]) * 0.998}


def _t310_data(planted, seed=31):
    out = {}
    for k, s in enumerate(("SPY", "QQQ", "GLD", "TLT")):
        rng = np.random.default_rng(seed + k)
        if planted:
            mo = MO - MO[0] + 11 * k
            cyc = mo % 60                                   # 36 months up, 24 months down
            up = cyc < 36
            calm = (cyc // 6) % 2 == 0
            mu = np.where(up, np.where(calm, 0.02, 0.0), -0.01) / 21
            vol = np.where(up, np.where(calm, 0.005, 0.02), 0.004)
            r = mu + rng.normal(0, 1, len(DAYS)) * vol
        else:
            r = rng.normal(0.0003, 0.009, len(DAYS))
        out[s] = _ohlc(DAYS, price(r))
    return out


T310_TEST_FAMILY = (m.T310_PRIMARY, ("rv21", 0.10, 2.0))


def test_t310_planted_scaling_helps_trend_more_than_buy_and_hold():
    j = m.vol_scaled_did(_t310_data(True), BILLS, family=T310_TEST_FAMILY, n_boot=300, n_boot_other=300, reps=2)
    assert j["n"] >= 300 and j["primary"]["did"] > 0
    assert j["verdict"] == "supported", j["why"]


def test_t310_null_does_not_pass():
    j = m.vol_scaled_did(_t310_data(False), BILLS, family=T310_TEST_FAMILY, n_boot=300, n_boot_other=300, reps=2)
    assert j["verdict"] != "supported"


def test_t310_joint_bootstrap_matches_direct_resampling():
    rng = np.random.default_rng(0)
    x, y = rng.normal(0.001, 0.01, 250), rng.normal(0.0, 0.01, 250)
    a = m.joint_sharpe_boot([x, y], 60, 50, seed=4)
    # the same draws by explicit circular index arrays
    r2 = np.random.default_rng(4)
    nb = math.ceil(250 / 60)
    st = r2.integers(0, 250, size=(50, nb))
    for d in range(50):
        idx = np.concatenate([(st[d, b] + np.arange(60 if b < nb - 1 else 250 - 60 * (nb - 1))) % 250 for b in range(nb)])
        assert a[d, 0] == pytest.approx(x[idx].mean() / x[idx].std(ddof=1) * math.sqrt(252), rel=1e-9)
        assert a[d, 1] == pytest.approx(y[idx].mean() / y[idx].std(ddof=1) * math.sqrt(252), rel=1e-9)


# ------------------------------------------------------------------------------------ T-481 cross-asset --

def _t481_data(planted, seed=41):
    rng = np.random.default_rng(seed)
    allm = sorted(set(d[:7] for d in bdays("1990-01-01", "2026-10-14")))
    dy = rng.normal(0, 0.3, len(allm))
    ym = 6.0 + np.cumsum(dy)
    ym = np.clip(ym, 0.5, 15)
    ydays = bdays("1990-01-01", "2026-10-14")
    mi = {mm: k for k, mm in enumerate(allm)}
    yd = {d: ym[mi[d[:7]]] for d in ydays}
    dgs10 = {d: (v, d + "T20:00:00+00:00") for d, v in yd.items()}
    syn = np.r_[0.0, m.synthetic_bond(ym, 8.0)]                       # monthly synthetic returns by month index
    bill_m = 0.03 / 12
    b = np.zeros(len(allm))
    for t in range(12, len(allm)):
        cum = np.prod(1 + syn[t - 11:t]) / (1 + bill_m) ** 11 - 1
        b[t] = np.sign(cum)
    mo_d = [mi[d[:7]] for d in DAYS]
    if planted:
        drift = np.array([0.03 * b[k - 1] / 21 if k >= 13 else 0.0 for k in mo_d])
        spy_r = drift + rng.normal(0, 0.008, len(DAYS))
    else:
        spy_r = rng.normal(0.0004, 0.009, len(DAYS))
    idays = [d for d in DAYS if d >= "2002-07-30"]
    # IEF level flat within a month, equal at each month-end to the cumulative synthetic return
    me_level, lv = {}, 100.0
    for mm in allm:
        if mm >= "2002-08":
            lv *= 1 + syn[mi[mm]]
        me_level[mm] = lv
    ief = np.array([me_level[d[:7]] for d in idays])
    return (DAYS, price(spy_r)), (idays, ief), (idays, ief * 1.0), dgs10


T481_TEST_FAMILY = (m.T481_PRIMARY, ("synthetic", "LF", 12))


def test_t481_planted_bond_signal_adds_to_own_trend():
    spy, ief, tlt, dgs = _t481_data(True)
    j = m.cross_asset_tsmom(spy, ief, tlt, dgs, BILLS, family=T481_TEST_FAMILY)
    assert j["n"] >= 380 and j["sharpe"]["diff"] > 0
    assert j["verdict"] == "supported", j["why"]


def test_t481_null_does_not_pass():
    spy, ief, tlt, dgs = _t481_data(False, seed=42)
    j = m.cross_asset_tsmom(spy, ief, tlt, dgs, BILLS, family=T481_TEST_FAMILY)
    assert j["verdict"] != "supported"


def test_t481_yield_known_by_the_fill_only():
    spy, ief, tlt, dgs = _t481_data(False, seed=43)
    late = {d: (v, (date.fromisoformat(d) + timedelta(days=10)).isoformat() + "T20:00:00+00:00") for d, (v, _) in dgs.items()}
    D = m._t481_monthly(spy, ief, tlt, late, BILLS)
    k = D["months"].index("2010-06")
    # each month-end yield must be a print released by the fill: with a 10-day publication lag it is an older print
    assert D["y"][k] != dgs[D["me_day"][k]][0] or D["y"][k] == D["y"][k - 1]


# ------------------------------------------------------------------------------------------ fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2026-10-15T08:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _yahoo(days, adj, crypto=False, close=None):
    close = adj if close is None else close
    hh = "00:00" if crypto else "14:30"
    rows = []
    for d, a, c in zip(days, adj, close):
        t = datetime.fromisoformat(f"{d}T{hh}:00+00:00").timestamp()
        av = (datetime.fromisoformat(f"{d}T{hh}:00+00:00") + timedelta(hours=24)).isoformat()
        rows.append({"available_at": av, "value": {"t": t, "open": float(c) * 0.999, "high": float(c) * 1.004,
                                                     "low": float(c) * 0.996, "close": float(c), "adjclose": float(a)}})
    return rows


def _fred(vals):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(v)}} for d, v in vals.items()]


def _fake_archive():
    b = {}
    k = 0
    for s in set(m.T300_ASSETS) | set(m.FIVE) | set(m.SECTORS) | set(m.T317_SLEEVES) | set(m.T310_ASSETS) | {"IEF"}:
        k += 1
        if s in m.CRYPTO:
            dd = cdays()
            b[m.dh(s)] = _yahoo(dd, price(np.random.default_rng(100 + k).normal(0.001, 0.03, len(dd))), crypto=True)
        else:
            dd = DAYS if s == "SPY" else bdays("1998-12-22")
            b[m.dh(s)] = _yahoo(dd, price(np.random.default_rng(100 + k).normal(0.0003, 0.01, len(dd))))
    b[m.DTB3_B] = _fred({d: 3.0 for d in bdays("1990-01-02")[::5]})
    b[m.DGS10_B] = _fred({d: 5.0 + 0.5 * math.sin(i / 300) for i, d in enumerate(bdays("1985-01-02"))})
    b[m.VIX_B] = [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": 15 + (i % 40)}} for i, d in enumerate(DAYS)]
    b[m.DVOL_B] = [{"available_at": d + "T23:59:00+00:00", "value": {"ts_ms": datetime.fromisoformat(d + "T00:00:00+00:00").timestamp() * 1000,
                                                                       "close": 60.0}} for d in cdays("2021-03-24")]
    return FakeArchive(b)


@pytest.fixture
def small_families(monkeypatch):
    monkeypatch.setattr(m, "T301_FAMILY", T301_TEST_FAMILY)
    monkeypatch.setattr(m, "T301_N_REFINE", 1500)
    monkeypatch.setattr(m, "T311_FAMILY", T311_TEST_FAMILY)
    monkeypatch.setattr(m, "T311_N_NULL", 200)
    monkeypatch.setattr(m, "T317_FAMILY", (m.T317_PRIMARY, ("quarterly", True, "LS")))
    monkeypatch.setattr(m, "T317_N_SIM", 60)
    monkeypatch.setattr(m, "T310_FAMILY", (m.T310_PRIMARY, ("dvol_btc", 0.10, 2.0)))
    monkeypatch.setattr(m, "T310_N_BOOT_OTHER", 200)
    monkeypatch.setattr(m, "T300_FAMILY", (m.T300_PRIMARY, ("6-1", "LF", "excess", "sign")))
    monkeypatch.setattr(m, "T481_FAMILY", T481_TEST_FAMILY)
    monkeypatch.setattr(m, "T308_FAMILY", (m.T308_PRIMARY, (24, True, "top3")))


def test_every_harness_runs_json_safe_on_a_fake_archive(small_families):
    a = _fake_archive()
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(k.startswith("b6c_mom_") and k == k.lower() for k in m.HARNESSES)
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(a)
        json.dumps(stat, allow_nan=False)
        assert isinstance(n, int) and n > 0, name
        assert verdict in ("supported", "not_supported", "inconclusive"), name
        assert " — " in reason, name


def test_missing_bundles_are_inconclusive():
    a = FakeArchive({})
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(a)
        assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert "missing data bundles" in reason
