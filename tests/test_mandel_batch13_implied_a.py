"""Batch 13 ``implied_a`` (T-651, T-652, T-654, T-655): point-in-time signal tests and missing-bundle verdicts."""

from __future__ import annotations

import copy
from datetime import date

import numpy as np
import pytest

from mandel.experiments import batch13_implied_a as M
from mandel.experiments import batch6c_cal as CAL


class _NoBundles:
    """A stub archive with no bundles: every lookup raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


def _sessions(start: str, n: int) -> list:
    d = date.fromisoformat(start)
    if not CAL.is_nyse_session(d):
        d = CAL.next_session(d)
    out = [d.isoformat()]
    while len(out) < n:
        d = CAL.next_session(d)
        out.append(d.isoformat())
    return out


def _vx_world(n: int = 420, seed: int = 1):
    """A synthetic VX curve (monthly expiries every 21 sessions), VIX closes and SPY closes on NYSE sessions."""
    rng = np.random.default_rng(seed)
    cal = _sessions("2019-01-02", n)
    expiries = [cal[k] for k in range(15, n, 21)]
    vix = {d: float(15 + 3 * np.sin(i / 17.0) + rng.normal(0, 0.5)) for i, d in enumerate(cal)}
    spy, p = {}, 300.0
    for d in cal:
        p *= 1.0 + rng.normal(0.0003, 0.01)
        spy[d] = p
    curve = {}
    for d in cal:
        curve[d] = {e: float(vix[d] + 0.08 * (cal.index(e) - cal.index(d)) + rng.normal(0, 0.2)) for e in expiries if e >= d}
    return cal, curve, vix, spy, expiries


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = M.HARNESSES[name](_NoBundles())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason


def test_theory_map_matches_harnesses():
    assert set(M.THEORY_MAP) == {"T-651", "T-652", "T-654", "T-655"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


class _OnlyMissing:
    """A stub archive that has every bundle except ``absent`` (get() raises KeyError for those)."""

    def __init__(self, absent):
        self.absent = set(absent)

    def get(self, name):
        if name in self.absent:
            raise KeyError(name)
        return object()


def test_t654_requires_dtb3():
    stat, n, verdict, reason = M.b13_implied_a_vvix_put_hedge(_OnlyMissing({M.DTB3_B}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"] == [M.DTB3_B]
    with pytest.raises(ValueError):
        M.put_weeks({}, {}, {}, None)


def test_and_rows_is_a_conjunction():
    P, F, U = ("nw", True, False), ("boot", False, False), ("boot", None, False)
    assert M.and_rows([P, ("boot", True, False)], "x")[1] is True
    assert M.and_rows([P, F], "x")[1] is False                       # one registered test fails -> the row fails
    assert M.and_rows([("nw", False, False), U], "x")[1] is False
    assert M.and_rows([P, U], "x")[1] is None                         # none fails, one unresolved -> undecided
    assert M.and_rows([P, ("boot", False, True)], "x")[2] is True     # decisive when a failing test is decisive
    assert M.and_rows([("nw", False, False), F], "x")[2] is False


def test_mean_rows_fails_when_only_the_bootstrap_fails(monkeypatch):
    x = np.full(200, 1.0) + np.random.default_rng(0).normal(0, 0.5, 200)   # NW t far above 1.645
    monkeypatch.setattr(M.CAL, "studentized_p_escalated", lambda *a, **k: (0.40, 0.60, 10000))
    row, info = M.mean_rows(x, 12, 12, "pooled mean")
    assert info["nw_p"] < 0.05 and row[1] is False


def test_slope_a_row_fails_when_only_newey_west_fails(monkeypatch):
    rng = np.random.default_rng(2)
    xv = rng.normal(0, 1, 160)
    y = 1.0 * xv + rng.normal(0, 0.3, 160)
    monkeypatch.setattr(M.CAL, "ols_nw", lambda y_, x_, lag: {"slope": 1.0, "se": 1.0, "t": 1.0})   # NW p 0.16
    row, info = M.slope_a_row(y, xv, "(a)", n_boot=500)
    assert info["p_nw"] > 0.05 and info["p_boot"] < 0.05 and row[1] is False


# ------------------------------------------------------------------------------------------------- T-651 --

def test_sessions_to_and_front_contract():
    cal = _sessions("2024-01-02", 60)
    ecal = M.extended_calendar(cal, "2024-06-30")
    e = cal[30]
    assert M.sessions_to(ecal, 20, e) == 10
    front = M.front_contracts(ecal, len(cal), [cal[25], cal[50]], 10)
    assert front[15] == cal[25] and front[16] == cal[50]      # 10 days left at 15, 9 at 16


def test_t651_signal_and_hedge_ratio_ignore_data_after_t():
    cal, curve, vix, spy, expiries = _vx_world()
    ecal = M.extended_calendar(cal, max(expiries))
    i = 330
    recs, _ = M.t651_records(cal, ecal, curve, vix, spy, start=cal[0], end=cal[-1])
    base = next(r for r in recs if r["i"] == i)
    c2, v2, s2 = copy.deepcopy(curve), dict(vix), dict(spy)
    for d in cal[i + 1:]:
        c2[d] = {e: 3.0 * x + 7.0 for e, x in c2[d].items()}
        v2[d] = v2[d] + 40.0
        s2[d] = s2[d] * 1.7
    recs2, _ = M.t651_records(cal, ecal, c2, v2, s2, start=cal[0], end=cal[-1])
    shocked = next(r for r in recs2 if r["i"] == i)
    for k in ("roll", "side", "contract", "tau_t", "tau_e"):
        assert shocked[k] == base[k]
    assert shocked["beta"] == pytest.approx(base["beta"], abs=1e-12)
    assert shocked["coef"] == pytest.approx(base["coef"], abs=1e-12)
    assert shocked["fx"] != base["fx"]                       # the outcome does move


def test_t651_hedge_fit_uses_the_window_ending_at_t():
    cal, curve, vix, spy, expiries = _vx_world()
    ecal = M.extended_calendar(cal, max(expiries))
    front = M.front_contracts(ecal, len(cal), expiries, M.T651_MIN_DAYS)
    ch = M.daily_changes(cal, ecal, curve, front, spy)
    b = M.hedge_fit(ch, 300)
    s2 = dict(spy)
    s2[cal[300]] *= 1.05                                     # the change into t is inside the window
    b2 = M.hedge_fit(M.daily_changes(cal, ecal, curve, front, s2), 300)
    assert not np.allclose(b, b2)
    s3 = dict(spy)
    s3[cal[301]] *= 1.05                                     # the change into t+1 is not
    b3 = M.hedge_fit(M.daily_changes(cal, ecal, curve, front, s3), 300)
    assert np.allclose(b, b3)


def test_t651_pnl_signs():
    rec = {"side": -1, "fe": 20.0, "fx": 19.0, "beta": -80.0, "r_spy": 0.01, "entry": "2024-01-02", "exit": "2024-01-09"}
    # short VX gains $1,000; the hedge is -side x 1000 x beta = -$80,000 of SPY, losing $800 on a +1% SPY week
    assert M.t651_pnl([rec], cost=0.0)[0] == pytest.approx(1000.0 - 800.0)
    assert M.t651_pnl([rec], cost=140.0, hedge="none")[0] == pytest.approx(860.0)


# ------------------------------------------------------------------------------------------------- T-652 --

def test_t652_forecasts_ignore_rows_after_t():
    rng = np.random.default_rng(3)
    n = 600
    x = np.cumsum(rng.normal(0, 0.05, n)) * 0.2 + np.log(16.0)
    r = rng.normal(-0.1, 0.05, n)
    Z = np.column_stack([x, r])
    j, h = 450, 18
    base = (M.var1_forecast(Z, j, h), M.ar1_forecast(Z[:, 0], j, h), M.har_forecast(Z[:, 0], j, h))
    Z2 = Z.copy()
    Z2[j + 1:] += 5.0
    shock = (M.var1_forecast(Z2, j, h), M.ar1_forecast(Z2[:, 0], j, h), M.har_forecast(Z2[:, 0], j, h))
    for a, b in zip(base, shock):
        assert a == pytest.approx(b, abs=1e-12)
    Z3 = Z.copy()
    Z3[j, 0] += 0.5                                          # t's own close does enter
    assert M.var1_forecast(Z3, j, h)[0] != pytest.approx(base[0][0])


def test_t652_trailing_z_and_cycles():
    days = _sessions("2020-01-02", 300)
    vals = np.linspace(10, 40, 300)
    z = M.trailing_z(days, vals, days[280], 252)
    v2 = vals.copy()
    v2[281:] = 999.0
    assert M.trailing_z(days, v2, days[280], 252) == pytest.approx(z)
    cal = _sessions("2021-01-04", 200)
    ecal = M.extended_calendar(cal, "2021-12-31")
    e1, e2, e3 = cal[10], cal[35], cal[55]                   # cycles of 25 and 20 sessions
    curve = {d: {e: 20.0 for e in (e1, e2, e3) if e >= d} for d in cal[:60]}
    cyc, _ = M.premium_cycles(cal, ecal, curve, start=cal[0])
    assert [(cal[t], e) for t, e, _, _ in cyc] == [(cal[35 - 21], e2), (cal[36], e3)]   # one per cycle, after E_prev


def _premium_world(seed: int = 11, n: int = 720):
    """Synthetic VX curve (expiries every 21 sessions from session 320, final settlement rows included), VIX, VIX3M,
    VVIX and SPY on NYSE sessions 2012-.., so cycles fall after T652_START."""
    rng = np.random.default_rng(seed)
    cal = _sessions("2012-01-03", n)
    pos = {d: i for i, d in enumerate(cal)}
    lv = np.empty(n)
    lv[0] = np.log(16.0)
    for i in range(1, n):
        lv[i] = 0.05 * np.log(16.0) + 0.95 * lv[i - 1] + rng.normal(0, 0.06)
    vix = {d: float(np.exp(lv[i])) for i, d in enumerate(cal)}
    vix3m = {d: float(vix[d] * np.exp(0.08 + rng.normal(0, 0.03))) for d in cal}
    vvix = {d: float(90 + 10 * np.sin(i / 23.0) + rng.normal(0, 3)) for i, d in enumerate(cal)}
    adj = 300.0 * np.cumprod(1.0 + rng.normal(0.0003, 0.01, n))
    expiries = [cal[k] for k in range(320, n, 21)]
    curve = {d: {e: float(vix[d] + 0.05 * (pos[e] - i) + rng.normal(0, 0.2)) for e in expiries if e >= d}
             for i, d in enumerate(cal)}
    return cal, curve, vix, vix3m, vvix, adj, expiries


@pytest.mark.parametrize("model,h_shift", [("var", 0), ("var", -1), ("ar1", 0), ("har", 0), ("raw", 0)])
def test_t652_cycles_end_to_end_ignore_data_after_t(model, h_shift):
    cal, curve, vix, vix3m, vvix, adj, expiries = _premium_world()
    ecal = M.extended_calendar(cal, max(expiries))
    args = (cal, ecal, curve, vix, vix3m, vvix, cal, adj)
    cyc, _ = M.build_premium_cycles(*args, model=model, h_shift=h_shift)
    assert len(cyc) >= 8
    base = cyc[len(cyc) // 2]
    t = cal.index(base["day"])
    c2 = copy.deepcopy(curve)
    v2, v3, vv2, adj2 = dict(vix), dict(vix3m), dict(vvix), adj.copy()
    for d in cal[t + 1:]:
        c2[d] = {e: 2.5 * x + 9.0 for e, x in c2[d].items()}     # the whole VX curve after t, final settlements included
        v2[d] *= 3.0
        v3[d] *= 0.5
        vv2[d] += 60.0
    adj2[t + 1:] *= np.exp(np.cumsum(np.full(len(cal) - t - 1, 0.03)))
    cyc2, _ = M.build_premium_cycles(cal, ecal, c2, v2, v3, vv2, cal, adj2, model=model, h_shift=h_shift)
    shocked = next(c for c in cyc2 if c["day"] == base["day"])
    for k in ("expiry", "h", "f1", "vix", "ev", "P", "vvix", "vvix_z", "rv", "rv_z"):
        assert shocked[k] == pytest.approx(base[k], abs=1e-12), k
    assert shocked["fs"] != pytest.approx(base["fs"])               # the outcome does move
    assert shocked["y"] != pytest.approx(base["y"])


# ------------------------------------------------------------------------------------------------- T-654 --

def test_t654_signals_from_the_session_before_entry():
    rng = np.random.default_rng(5)
    days = _sessions("2022-01-03", 400)
    idx = {k: (days, rng.normal(100 if k == "VVIX" else 20, 5, len(days))) for k in ("VVIX", "VIX", "SKEW")}
    adj = np.cumprod(1.0 + rng.normal(0, 0.01, len(days))) * 400.0
    rv = M.rv_series(days, adj, M.T654_RV_WIN)
    entry = days[350]
    base = M.week_signals(entry, idx, days, rv)
    shocked_idx = {}
    for k, (d, v) in idx.items():
        v2 = v.copy()
        v2[350:] = v2[350:] * 4.0 + 50.0                     # the entry day's own close and later
        shocked_idx[k] = (d, v2)
    adj2 = adj.copy()
    adj2[350:] *= 1.3
    shocked = M.week_signals(entry, shocked_idx, days, M.rv_series(days, adj2, M.T654_RV_WIN))
    for k in ("VVIX", "VIX", "SKEW", "rv21", "vvix_resid"):
        assert shocked[k] == pytest.approx(base[k], abs=1e-12)
    assert base["signal_session"] == days[349]


def test_t654_tercile_cut_uses_2019_2022_only_and_placebo():
    rng = np.random.default_rng(9)
    disc = [{"entry": f"2020-{1 + i % 12:02d}-10", "VVIX": float(z), "VIX": float(-z)} for i, z in enumerate(rng.normal(0, 1, 60))]
    conf = [{"entry": f"2024-{1 + i % 12:02d}-10", "VVIX": float(z), "VIX": float(z), "spread": float(r)}
            for i, (z, r) in enumerate(zip(rng.normal(0, 1, 40), rng.normal(0, 0.1, 40)))]
    base = M.tercile_split(conf, disc, "VVIX")
    conf2 = [dict(w, VVIX=w["VVIX"] * 10.0 + 5.0) for w in conf]  # confirmation z values never set the cut
    assert M.tercile_split(conf2, disc, "VVIX")["cut"] == pytest.approx(base["cut"])
    assert base["cut"] == pytest.approx(float(np.quantile([w["VVIX"] for w in disc], 2 / 3)))
    assert base["n_top"] + base["n_other"] == 40
    assert M.tercile_split(conf, disc, "SKEW")["cut"] is None          # SKEW not archived: control n/a
    pl = M.tercile_placebo(base["top"], base["other"], draws=500)
    assert 0.0 < pl["p"] <= 1.0 and pl["draws"] == 500
    pl_hi = M.tercile_placebo([10.0, 11.0], [0.0, 0.1, -0.1, 0.2, 0.05, 0.0], draws=2000)
    assert pl_hi["p"] < 0.1


# ------------------------------------------------------------------------------------------------- T-655 --

def test_t655_terciles_ignore_dvol_after_d():
    rng = np.random.default_rng(7)
    dv = 50 + np.cumsum(rng.normal(0, 1.0, 900))
    lab = M.tercile_labels(dv)
    k = 700
    dv2 = dv.copy()
    dv2[k + 1:] = dv2[k + 1:] * 0.1                          # every later close shocked
    lab2 = M.tercile_labels(dv2)
    assert np.array_equal(lab[:k + 1], lab2[:k + 1], equal_nan=True)
    assert np.isnan(lab[M.T655_WIN - 2]) and np.isfinite(lab[M.T655_WIN - 1])


def test_t655_forward_rv_window():
    c = np.exp(np.cumsum(np.full(40, 0.01)))
    rv = M.forward_rv(c, 30)
    assert rv[0] == pytest.approx(365.0 / 30 * 30 * 0.01 ** 2)
    assert np.isnan(rv[10])                                  # needs closes k..k+30
    c2 = c.copy()
    c2[31:] = 1.0                                            # closes after bar 30 do not enter RV at k = 0
    assert M.forward_rv(c2, 30)[0] == pytest.approx(rv[0])


def test_t655_vrp_frame_alignment():
    days = [f"2021-01-{d:02d}" for d in range(1, 32)] + [f"2021-02-{d:02d}" for d in range(1, 29)]
    dvol = {d: 80.0 for d in days}
    px = {d: 100.0 * np.exp(0.02 * i) for i, d in enumerate(days)}
    F = M.vrp_frame(dvol, px, start=days[0], end=days[-1])
    # constant 2% daily log returns: RV = 365 x 0.0004, IV^2 = 0.64
    assert F["ratio"][0] == pytest.approx(1.0 - 365.0 * 0.0004 / 0.64)
