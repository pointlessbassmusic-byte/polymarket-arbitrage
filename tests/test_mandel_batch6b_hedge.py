"""Batch 6b, group hedge: Cboe hedged-overlay benchmark claims, the BS replication of BXM/PUT and the VIX SOQ credit
spread, on synthetic data only (no archive, no network). Each core function gets a planted effect that passes and a
null that does not."""

import json
import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6b_hedge as h

NB = 400            # bootstrap draws in tests (the harnesses use 2,000 to 4,000)


# ===================================================================================================== fixtures ==

def _bdays(start: str, n: int) -> list:
    """n Monday-Friday days from ``start`` (no holidays)."""
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _months(n: int, start=(1990, 1)) -> list:
    y, m = start
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = y + (m == 12), m % 12 + 1
    return out


def _panel(n: int, bill: float = 0.002, **series) -> dict:
    return {"months": _months(n), "ret": {k: np.asarray(v, dtype=float) for k, v in series.items()},
            "bill": np.full(n, bill), "span": np.full(n, 365.25 / 12), "first": "1989-12-29", "last": "2030-01-31",
            "excluded": []}


class _Entry:
    def __init__(self, name):
        self.name = name
        self.created_at = "2100-01-01T00:00:00+00:00"


class FakeArchive:
    def __init__(self, bundles):
        self.b = bundles

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name)

    def load(self, name):
        return iter(self.b[name])

    def entries(self):
        return [_Entry(n) for n in self.b]


def _idx_rows(days, closes, **extra):
    return [{"available_at": d + "T23:00:00+00:00", "value": {"day": d, "close": float(c), **extra}} for d, c in zip(days, closes)]


def _px_rows(days, closes, adj=None):
    adj = closes if adj is None else adj
    out = []
    for d, c, a in zip(days, closes, adj):
        t = int((date.fromisoformat(d) - date(1970, 1, 1)).days * 86400 + 14 * 3600)
        out.append({"available_at": d + "T23:00:00+00:00", "value": {"t": t, "close": float(c), "adjclose": float(a), "open": float(c)}})
    return out


def _fred_rows(days, pct):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": pct}} for d in days]


# =================================================================================================== statistics ==

def test_stud_ci_planted_and_null():
    rng = np.random.default_rng(1)
    lo, hi = h.stud_ci(0.4 + rng.standard_normal(300), 5, 0.95, NB)
    assert lo > 0
    lo, hi = h.stud_ci(rng.standard_normal(300), 5, 0.95, NB)
    assert lo < 0 < hi
    assert h.stud_ci(np.array([1.0, 2.0]), 3) == (None, None)


def test_sharpe_diff_test_planted_and_null():
    rng = np.random.default_rng(2)
    b = 0.01 + 0.04 * rng.standard_normal(400)
    planted = h.sharpe_diff_test(0.8 * b - 0.004 + 0.01 * rng.standard_normal(400), b, 6, 0.95, NB)
    assert planted["diff"] < 0 and planted["ci"][1] < 0
    null = h.sharpe_diff_test(b + 0.01 * rng.standard_normal(400), b, 6, 0.95, NB)
    assert null["ci"][0] < 0 < null["ci"][1]
    assert h.sharpe_diff_test(b[:5], b[:5])["diff"] is None


def test_slope_ci_planted_and_null():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(450) * 4
    planted = h.slope_ci(x, 0.002 * x + 0.02 * rng.standard_normal(450), 6, 0.95, NB)
    assert planted["ci"][0] > 0 and abs(planted["slope"] - 0.002) < 0.001
    null = h.slope_ci(x, 0.02 * rng.standard_normal(450), 6, 0.95, NB)
    assert null["ci"][0] < 0 < null["ci"][1]


def test_ols_hac_recovers_coefficients():
    rng = np.random.default_rng(4)
    X = rng.standard_normal((500, 2))
    y = 0.5 + 2.0 * X[:, 0] - 1.0 * X[:, 1] + 0.1 * rng.standard_normal(500)
    r = h.ols_hac(y, X, 6)
    assert abs(r["coef"][1] - 2.0) < 0.05 and abs(r["coef"][2] + 1.0) < 0.05 and r["t"][1] > 10


def test_max_drawdown_and_stationary_indices():
    assert h.max_drawdown([0.1, -0.5, 0.2])[0] == pytest.approx(0.5)
    assert h.max_drawdown([0.01, 0.02])[0] == 0.0
    rng = np.random.default_rng(5)
    idx = h._stationary_idx(rng, 100, 10, 50)
    assert idx.shape == (50, 100) and idx.min() >= 0 and idx.max() < 100
    runs = (np.diff(idx, axis=1) % 100 == 1).mean()                # most steps continue a block (p = 0.9)
    assert 0.8 < runs < 0.97


def test_robust_decision_and_rule5():
    allp = h.robust_decision(lambda b, s: (0.1, 0.2), lambda l, u: l > 0, lambda l, u: u <= 0)
    assert allp["ok"] is True and allp["n_pass"] == 6
    mixed = h.robust_decision(lambda b, s: (-0.01, 0.2) if b == 12 else (0.01, 0.2), lambda l, u: l > 0, lambda l, u: u <= 0)
    assert mixed["ok"] is None and mixed["n_pass"] == 3
    nonep = h.robust_decision(lambda b, s: (-0.3, -0.1), lambda l, u: l > 0, lambda l, u: u <= 0)
    assert nonep["ok"] is False and nonep["decisive"] is True
    v, why = h._decide([("c", False, False)], 5, 10, "u")
    assert v == "inconclusive" and "not decisively" in why
    v, _ = h._decide([("c", False, True)], 5, 10, "u")
    assert v == "not_supported"
    v, _ = h._decide([("c", True, False)], 10, 10, "u")
    assert v == "supported"


# ============================================================================================ panels and flags ==

def test_strategy_series_applies_flags():
    rows = _idx_rows(["2009-10-15", "2009-10-16", "2009-10-17", "2009-10-19"], [100, 80, 80, 81])
    rows[1]["value"]["flag"] = "level step -19.8% while SPX fell 0.8%: splice in the free file"
    rows[2]["value"]["flag"] = "row on a market-closed day (weekend)"
    rows[3]["value"]["backtest"] = True
    s = h.strategy_series(rows)
    assert s["breaks"] == {"2009-10-16"} and "2009-10-17" in s["dropped"] and "2009-10-17" not in s["close"]
    assert s["backtest"] == {"2009-10-19"}


def test_monthly_panel_month_ends_bills_and_breaks():
    days = _bdays("2020-01-01", 90)
    a = {d: 100.0 * 1.001 ** i for i, d in enumerate(days)}
    b = {d: 50.0 for d in days}
    p = h.monthly_panel({"A": a, "B": b}, {"2019-12-31": 4.0}, "2020-02", "2020-04")
    me = {}
    for d in days:
        me[d[:7]] = d
    assert p["months"] == ["2020-02", "2020-03", "2020-04"]
    assert p["ret"]["A"][0] == pytest.approx(a[me["2020-02"]] / a[me["2020-01"]] - 1)
    r = h.dtb3_continuous(4.0)
    span0 = (date.fromisoformat(me["2020-02"]) - date.fromisoformat(me["2020-01"])).days
    assert p["bill"][0] == pytest.approx(math.exp(r * span0 / 365) - 1, rel=1e-9)
    assert p["span"][0] == span0
    # a -20% level step on a break day is excluded from every leg (not compounded)
    a2 = dict(a)
    brk = me["2020-03"][:8] + "10"
    brk = next(d for d in days if d >= brk)
    for d in days:
        if d >= brk:
            a2[d] = a[d] * 0.8
    raw = h.monthly_panel({"A": a2, "B": b}, {}, "2020-02", "2020-04")
    cut = h.monthly_panel({"A": a2, "B": b}, {}, "2020-02", "2020-04", breaks={brk})
    assert raw["ret"]["A"][1] < -0.15
    expect = a[me["2020-03"]] / a[me["2020-02"]] / 1.001 - 1          # every March return but the break day's
    assert cut["ret"]["A"][1] == pytest.approx(expect, rel=1e-9)
    assert cut["ret"]["B"][1] == 0.0 and cut["excluded"] == [brk]


# ============================================================================== T-166 / T-169 beta-matched CAGR ==

def _blend_case(alpha_m: float, n: int = 300, seed: int = 0):
    rng = np.random.default_rng(seed)
    rs = 0.008 + 0.04 * rng.standard_normal(n)
    rb = np.full(n, 0.002)
    ra = rb + 0.6 * (rs - rb) + alpha_m + 0.004 * rng.standard_normal(n)
    return _panel(n, 0.002, CLL=ra, SPY=rs)


def test_beta_blend_planted_passes():
    rep = h.beta_blend_claim(_blend_case(-0.003), "CLL", "SPY", 0.0, 200, 0.63, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert abs(rep["stat"]["beta_ols"] - 0.6) < 0.05 and rep["stat"]["ci95"][1] < 0
    rep2 = h.beta_blend_claim(_blend_case(-0.003), "CLL", "SPY", -0.01, 200, 0.6, n_boot=NB, live_from="2005-01")   # ~-3.5%/yr
    assert rep2["verdict"] == "supported", rep2["reason"]
    assert rep2["stat"]["live_only"]["n"] == 300 - 180 and "live (post-launch)" in rep2["reason"]
    assert h._live_month("CLLZ") == "2015-09" and h._live_month("CLL") == "2008-10"
    json.dumps(h._clean(rep["stat"]))


def test_beta_blend_null_fails():
    rep = h.beta_blend_claim(_blend_case(0.0), "CLL", "SPY", 0.0, 200, 0.63, n_boot=NB)
    assert rep["verdict"] == "not_supported"
    assert rep["stat"]["ci95"][0] < 0 < rep["stat"]["ci95"][1]
    small = h.beta_blend_claim(_blend_case(0.0, n=100), "CLL", "SPY", 0.0, 200, 0.63, n_boot=NB)
    assert small["verdict"] == "inconclusive"                    # below min_n, CI straddles 0: not decisive


def test_cagr_vs_blend_fixed_beta():
    p = _blend_case(-0.002)
    r = h.cagr_vs_blend(p["ret"]["CLL"], p["ret"]["SPY"], p["bill"], p["span"], beta=0.6, n_boot=NB)
    assert r["beta"] == 0.6 and r["beta_fixed"] and r["diff"] < 0


# ============================================================================= T-168 / T-178 Sharpe differences ==

def test_sharpe_noworse_planted_and_null():
    rng = np.random.default_rng(6)
    n = 400
    spy = 0.01 + 0.045 * rng.standard_normal(n)
    good = _panel(n, 0.002, CLLZ=0.7 * spy - 0.002 + 0.008 * rng.standard_normal(n), SPY=spy)
    rep = h.sharpe_noworse_claim(good, "CLLZ", "SPY", 0.05, 380, crash=spy, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["stat"]["crash_months"]["n"] > 0
    bad = _panel(n, 0.002, CLLZ=0.7 * spy + 0.004 + 0.008 * rng.standard_normal(n), SPY=spy)
    rep = h.sharpe_noworse_claim(bad, "CLLZ", "SPY", 0.05, 380, n_boot=NB)
    assert rep["verdict"] == "not_supported"


def test_sharpe_lower_planted_and_null():
    rng = np.random.default_rng(7)
    n = 480
    cndr = 0.006 + 0.02 * rng.standard_normal(n)
    planted = _panel(n, 0.002, BFLY=cndr - 0.004 + 0.005 * rng.standard_normal(n), CNDR=cndr)
    rep = h.sharpe_lower_claim(planted, "BFLY", "CNDR", "2008-01", 400, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    null = _panel(n, 0.002, BFLY=cndr + 0.005 * rng.standard_normal(n), CNDR=cndr)
    rep = h.sharpe_lower_claim(null, "BFLY", "CNDR", "2008-01", 400, n_boot=NB)
    assert rep["verdict"] != "supported"


# ================================================================================== T-179 CNDR on the VRP gap ==

def test_roll_sessions_third_friday_and_holiday():
    days = [d for d in _bdays("2024-01-01", 300) if d != "2024-03-15"]       # March 3rd Friday removed
    ix = h.roll_sessions(days)
    rolled = [days[i] for i in ix]
    assert "2024-01-19" in rolled and "2024-02-16" in rolled and "2024-03-14" in rolled


def test_trailing_rv_constant_vol():
    lr = np.tile([0.01, -0.01], 50)
    c = 100 * np.exp(np.concatenate([[0], np.cumsum(lr)]))
    rv = h.trailing_rv(c, [21, 60, 5])
    assert rv[0] == pytest.approx(100 * math.sqrt(252) * 0.01) and math.isnan(rv[2])


def _rp(n, slope, seed=8):
    rng = np.random.default_rng(seed)
    vix = 18 + 6 * rng.standard_normal(n)
    rv = 15 + 5 * rng.standard_normal(n)
    gap = vix - rv
    ret = 0.002 + 0.003 + slope * gap + 0.01 * rng.standard_normal(n)
    return {"day": _months(n), "end": _months(n), "ret": ret, "bill": np.full(n, 0.003), "vix": vix, "rv": rv,
            "spx": 0.008 + 0.04 * rng.standard_normal(n)}


def test_gap_slope_planted_and_null():
    rep = h.gap_slope_claim(_rp(450, 0.001), {"zero rate": np.zeros(450)}, 400, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    rep = h.gap_slope_claim(_rp(450, 0.0), {"zero rate": np.zeros(450)}, 400, n_boot=NB)
    assert rep["verdict"] == "not_supported"


# ================================================================================== T-528 VXTH drawdowns ==

def _dp(n, hedge_scale, rival_scale, seed=9):
    rng = np.random.default_rng(seed)
    ref = 0.0002 + 0.02 * rng.standard_normal(n)
    days = _bdays("2006-03-31", n + 1)
    return {"days": days, "end_days": days[1:], "ret": {"VXTH": hedge_scale * ref, "SPY": ref, "PPUT3M": rival_scale * ref,
                                                        "PPUT": 0.7 * ref}}


def test_drawdown_gap_planted_and_null():
    planted = h.tail_hedge_claim(_dp(3000, 0.3, 0.8), n_boot=300)
    assert planted["verdict"] == "supported", planted["reason"]
    assert planted["stat"]["gap_vs_ref_pts"] > 10
    null = h.tail_hedge_claim(_dp(3000, 1.0, 1.0), n_boot=300)
    assert null["verdict"] == "not_supported"
    assert null["stat"]["gap_vs_ref_pts"] == pytest.approx(0.0)


def test_daily_paired_drops_break_returns():
    days = _bdays("2010-01-01", 6)
    a = dict(zip(days, [100, 101, 80, 81, 82, 83]))
    b = dict(zip(days, [10, 10, 10, 10, 10, 10]))
    dp = h.daily_paired({"A": a, "B": b}, "", {days[2]})
    assert dp["ret"]["A"].size == 4 and dp["ret"]["A"].min() > -0.05 and days[2] not in dp["end_days"]


# ========================================================================= T-180 Black-Scholes replication ==

def _frame(n_days=2100, seed=10, vol=0.15):
    rng = np.random.default_rng(seed)
    days = _bdays("2001-01-01", n_days)
    lr = -0.5 * vol ** 2 / 252 + vol / math.sqrt(252) * rng.standard_normal(n_days - 1)
    S = 1000 * np.exp(np.concatenate([[0], np.cumsum(lr)]))
    n = len(days)
    return {"days": days, "ords": h._ords(days), "S": S, "O": S.copy(), "divy_smooth": np.full(n, 0.015 / 252),
            "divy_lump": np.zeros(n), "q": np.full(n, 0.015), "vix": np.full(n, 100 * vol), "rate": np.full(n, 0.02)}


def test_overlay_index_flat_market_earns_premium():
    fr = _frame(200)
    fr["S"] = np.full(len(fr["days"]), 1000.0)
    fr["divy_smooth"] = np.zeros(len(fr["days"]))
    rolls = h.roll_sessions(fr["days"])
    put = h.overlay_index(fr, rolls, "put")
    call = h.overlay_index(fr, rolls, "call")
    a, b = int(rolls[0]), int(rolls[1])
    T = (fr["ords"][b] - fr["ords"][a]) / 365
    p0 = float(h.bs.price(1000.0, 1000.0, T, 0.02, 0.15, "put", 0.015))
    c0 = float(h.bs.price(1000.0, 1000.0, T, 0.02, 0.15, "call", 0.015))
    assert put[b] / put[a] - 1 == pytest.approx((1 + p0 / 1000) * math.exp(0.02 * T) - 1, rel=1e-9)
    assert call[b] / call[a] - 1 == pytest.approx(1000 / (1000 - c0) - 1, rel=1e-9)


def _actual_from(fr, kind, noise, seed=11, unrelated=False):
    rolls = h.roll_sessions(fr["days"])
    sim = h.overlay_index(fr, rolls, kind)
    rng = np.random.default_rng(seed)
    ok = np.isfinite(sim)
    if unrelated:
        lvl = 100 * np.exp(np.cumsum(0.01 * rng.standard_normal(len(sim))))
    else:
        lvl = sim * np.exp(np.cumsum(noise * rng.standard_normal(len(sim))))
    return {d: float(v) for d, v, k in zip(fr["days"], lvl, ok) if k}


def test_replication_planted_and_null():
    fr = _frame()
    good = {"BXM": _actual_from(fr, "call", 0.0002), "PUT": _actual_from(fr, "put", 0.0002)}
    rep = h.replication_claim(fr, good, {"BXM": "2001-01-01", "PUT": "2001-01-01"}, None, 60)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["stat"]["bxm"]["roll"]["r2"] > 0.99 and rep["stat"]["put"]["month"]["te"] < 0.02
    assert rep["stat"]["label"] == h.MP
    bad = {"BXM": _actual_from(fr, "call", 0, unrelated=True), "PUT": _actual_from(fr, "put", 0, seed=12, unrelated=True)}
    rep = h.replication_claim(fr, bad, {"BXM": "2001-01-01", "PUT": "2001-01-01"}, None, 60)
    assert rep["verdict"] == "not_supported"


def test_spx_frame_spreads_spy_dividends():
    days = _bdays("2005-01-03", 140)
    g = {"days": days, "close": np.full(140, 1000.0), "adj": np.full(140, 1000.0), "open": np.full(140, 1000.0)}
    close = np.full(140, 100.0)
    f = np.ones(140)
    f[60:] = 1.0 / (1 - 0.005)                 # 0.50 dividend (0.5%) goes ex on day 60
    f[120:] = f[60] / (1 - 0.005)
    spy = {"days": days, "close": close, "adj": close * f}
    fr = h.spx_frame(g, spy, {d: 15.0 for d in days}, {days[0]: 2.0})
    assert fr["divy_lump"][60] == pytest.approx(0.005, rel=1e-6) and fr["divy_lump"][59] == 0
    assert fr["divy_smooth"][:61].sum() == pytest.approx(0.005, rel=1e-6)
    assert fr["divy_smooth"][61:121].sum() == pytest.approx(0.005, rel=1e-3)
    assert fr["q"][59] == 0 and fr["q"][60] == pytest.approx(0.005, rel=1e-6)


# =================================================================================== T-220 VIX SOQ spread ==

def _soq_world(n_months=100, seed=13, loss_share=0.0, partial_share=0.0):
    rng = np.random.default_rng(seed)
    tdays = _bdays("2013-01-01", int(n_months * 21.7) + 30)
    exps = []
    y, m = 2013, 2
    while len(exps) < n_months:
        d = date(y, m, 1)
        d += timedelta(days=(2 - d.weekday()) % 7 + 14)               # third Wednesday
        exps.append(d.isoformat())
        y, m = y + (m == 12), m % 12 + 1
    exps = [e for e in exps if e <= tdays[-1]]
    pos = {d: i for i, d in enumerate(tdays)}
    curve, vro = {}, {}
    for e in exps:
        i = pos[e]
        F = 14 + 4 * rng.random()
        for d in tdays[i - 5:i + 1]:
            curve.setdefault(d, {})[e] = F
        u = rng.random()
        if u < loss_share:
            vro[e] = F + 2 + 5 + 3 * rng.random()                    # max loss
        elif u < loss_share + partial_share:
            vro[e] = round(F + 2) + 0.3                              # small partial loss
        else:
            vro[e] = F - 3 * rng.random()                            # expires worthless
    vix = {d: 15.0 for d in tdays}
    vix3m = {d: 17.0 for d in tdays}                                 # ratio 1.13 > 1.1
    vvix = {d: 100.0 for d in tdays}
    return dict(tdays=tdays, expiries=exps, curve=curve, vix=vix, vix3m=vix3m, vvix=vvix, vro=vro, rates={tdays[0]: 2.0})


def test_soq_spread_planted_and_null():
    w = _soq_world(100, partial_share=0.05)
    main = h.soq_spread_trades(hs1=0.03, hs2=0.02, **w)
    assert len(main["trades"]) >= 90
    t = main["trades"][0]
    assert t["K1"] == round(t["F"] + 2) and t["net_credit"] == pytest.approx(t["mid_credit"] - 0.05)
    rep = h.soq_spread_claim(main, {}, None, None, 60, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    w = _soq_world(100, loss_share=0.3, seed=14)
    rep = h.soq_spread_claim(h.soq_spread_trades(hs1=0.03, hs2=0.02, **w), {}, None, None, 60, n_boot=NB)
    assert rep["verdict"] == "not_supported"
    assert rep["stat"]["mean_ret_on_max_loss"] < 0


def test_soq_spread_gate_and_costs_unmeasured():
    w = _soq_world(80)
    w["vix3m"] = {d: 15.5 for d in w["tdays"]}                       # ratio 1.03: gate shut
    assert h.soq_spread_trades(hs1=0.0, hs2=0.0, **w)["trades"] == []
    w = _soq_world(80)
    rep = h.soq_spread_claim(h.soq_spread_trades(hs1=0.0, hs2=0.0, **w), {}, None, None, 60, n_boot=NB, costs_measured=False)
    assert rep["verdict"] == "inconclusive" and "half-spreads not measurable" in rep["reason"]


def test_chain_calibration_recovers_half_spreads_and_iv():
    q, e = "2026-10-13", "2026-10-21"
    F, vv = 16.84, 180.0                                     # wide enough that the K2 bid stays positive
    T = (date.fromisoformat(e).toordinal() - date.fromisoformat(q).toordinal() - 0.28) / 365
    rows = []
    for K, hs in ((19.0, 0.035), (24.0, 0.025), (20.0, 0.04)):
        mid = float(h.b76_call(F, K, T, 0.04, vv / 100))
        rows.append({"available_at": "2026-10-14T11:12:00+00:00",
                     "value": {"sym": f"VIX261021C{int(K * 1000):08d}", "expiry": e, "type": "call", "strike": K,
                               "bid": mid - hs, "ask": mid + hs}})
    cal = h.chain_calibration([rows], {q: {e: F}}, {q: vv}, {"2026-10-01": 4.0}, [q, "2026-10-14"])
    c = cal["captures"][0]
    assert c["K1"] == 19 and c["K2"] == 24
    assert cal["hs1"] == pytest.approx(0.035) and cal["hs2"] == pytest.approx(0.025)
    assert cal["ratio1"] == pytest.approx(1.0, abs=0.02) and c["model_credit"] == pytest.approx(c["market_mid_credit"], rel=0.02)


def test_vro_clean_filters():
    rows = [{"value": {"day": "2020-01-22", "close": 12.0, "expiry": True, "carried": False}},
            {"value": {"day": "2020-01-23", "close": 12.0, "expiry": False, "carried": True}},
            {"value": {"day": "2019-01-16", "close": 20.09, "expiry": True, "carried": True}},
            {"value": {"day": "2019-01-09", "close": 28.09, "expiry": True, "carried": False, "flag": "stale"}}]
    assert h.vro_clean(rows) == {"2020-01-22": 12.0}


def test_soq_preliminary_planted_and_null():
    days = _bdays("2008-07-01", 1500)
    rng = np.random.default_rng(15)
    vix = {d: 20 + rng.standard_normal() for d in days}
    weds = [d for d in days if date.fromisoformat(d).weekday() == 2]
    monthly = set(weds[::4])
    pos = {d: i for i, d in enumerate(days)}
    vro = {d: vix[days[pos[d] - 1]] + 1.0 + 0.2 * rng.standard_normal() for d in monthly}
    r = h.soq_preliminary(vro, vix, days, monthly, 500)
    assert r["diff"] > 0.5 and r["ci95"][0] > 0
    vro0 = {d: vix[days[pos[d] - 1]] + (vix[d] - vix[days[pos[d] - 1]]) for d in monthly}
    r0 = h.soq_preliminary(vro0, vix, days, monthly, 500)
    assert r0["ci95"][0] < 0 < r0["ci95"][1]


# ======================================================================================== harness wiring ==

def test_maps_and_names():
    assert set(h.THEORY_MAP) == {"T-166", "T-168", "T-169", "T-178", "T-179", "T-180", "T-528", "T-220"}
    assert set(h.THEORY_MAP.values()) == set(h.HARNESSES)
    assert all(k.startswith("b6b_hedge_") and k == k.lower() for k in h.HARNESSES)


@pytest.mark.parametrize("name", sorted(h.HARNESSES))
def test_harness_missing_bundles_is_inconclusive(name):
    stat, n, v, reason = h.HARNESSES[name](FakeArchive({}))
    assert v == "inconclusive" and n == 0 and stat["missing_bundles"] and "missing data bundles" in reason


def _monthly_world(start="1986-06-02", n_days=10600, seed=16):
    rng = np.random.default_rng(seed)
    days = _bdays(start, n_days)
    spy_r = 0.0004 + 0.011 * rng.standard_normal(n_days - 1)
    spy = 50 * np.exp(np.concatenate([[0], np.cumsum(spy_r)]))
    return days, spy, rng


def test_harness_cllz_sharpe_end_to_end():
    days, spy, rng = _monthly_world("1993-01-04", 8600)
    lr = np.diff(np.log(spy))
    cllz = 100 * np.exp(np.concatenate([[0], np.cumsum(0.6 * lr - 0.0002 + 0.002 * rng.standard_normal(lr.size))]))
    arch = FakeArchive({h.CB("CLLZ"): _idx_rows(days, cllz, backtest=False), h.SPY_B: _px_rows(days, spy),
                        h.GSPC_B: _px_rows(days, spy), h.DTB3_B: _fred_rows(days[::5], 2.0)})
    stat, n, v, reason = h.HARNESSES["b6b_hedge_cllz_sharpe"](arch)
    json.dumps(stat)
    assert n >= 380 and v == "supported", reason
    assert reason.count(" — ") >= 1


def test_harness_bfly_cndr_end_to_end_null():
    days, spy, rng = _monthly_world()
    r = 0.0002 + 0.003 * rng.standard_normal(len(days) - 1)
    lvl = 100 * np.exp(np.concatenate([[0], np.cumsum(r)]))
    arch = FakeArchive({h.CB("BFLY"): _idx_rows(days, lvl), h.CB("CNDR"): _idx_rows(days, lvl * 1.0),
                        h.DTB3_B: _fred_rows(days[::5], 2.0)})
    stat, n, v, reason = h.HARNESSES["b6b_hedge_bfly_vs_cndr_sharpe"](arch)
    json.dumps(stat)
    assert n >= 400 and v != "supported"
