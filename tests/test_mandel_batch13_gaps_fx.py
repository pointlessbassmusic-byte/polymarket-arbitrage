"""Tests for mandel.experiments.batch13_gaps_fx: point-in-time signal construction (values shocked after the decision
never move the signal at the decision) and inconclusive verdicts when bundles are missing."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch13_gaps_fx as M


class _NoBundles:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


def _weekdays(start: str, end: str) -> list:
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _spot(days, ccys, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    out = {}
    for c in ccys:
        lv = np.exp(np.cumsum(rng.normal(0, 0.006, len(days))))
        out[c] = dict(zip(days, lv))
    return out


def _shock_after(spot: dict, cut: str, k: float = 3.0) -> dict:
    """Every fix whose H.10 release is after ``cut`` multiplied by k (alternating, so log changes move too)."""
    out = {}
    for c, s in spot.items():
        out[c] = {d: (v * (k if i % 2 else 1.0 / k) if M.h10_release(d) > cut else v)
                  for i, (d, v) in enumerate(sorted(s.items()))}
    return out


# ------------------------------------------------------------------------------------------------- missing data --

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_NoBundles())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_matches_harnesses():
    assert set(M.THEORY_MAP) == {"T-719", "T-720", "T-725", "T-728"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


# ---------------------------------------------------------------------------------------------- H.10 calendar --

def test_h10_release_is_next_monday_or_after_holiday():
    assert M.h10_release("2024-05-21") == "2024-05-28"        # Memorial Day Monday 05-27 moves the release to Tuesday
    assert M.h10_release("2024-05-31") == "2024-06-03"
    assert M.h10_release("2024-01-08") == "2024-01-16"        # King's Birthday 01-15
    assert M.h10_release("2026-09-04") == "2026-09-08"        # Labor Day 09-07
    assert M.h10_release("2024-12-27") == "2024-12-30"
    for d in _weekdays("2020-01-01", "2020-12-31"):
        r = date.fromisoformat(M.h10_release(d))
        assert r > date.fromisoformat(d) and M.is_fed_business(r)


def test_pub_idx_never_includes_an_unreleased_fix():
    days = _weekdays("2021-01-04", "2021-03-31")
    P = M.common_panel(_spot(days, M.G9), M.G9)
    for D in ("2021-01-31", "2021-02-28", "2021-03-31"):
        i = M.pub_idx(P, D)
        assert M.h10_release(P["days"][i]) <= D
        assert i + 1 == len(days) or M.h10_release(P["days"][i + 1]) > D


# ------------------------------------------------------------------------------------------------------- T-719 --

def test_t719_gv_ignores_fixes_not_yet_published():
    days = _weekdays("2019-01-01", "2019-06-30")
    spot = _spot(days, M.G9, 1)
    D = "2019-04-30"
    base = M.gv_rv(M.common_panel(spot, M.G9), D)
    assert np.isfinite(base)
    shocked = M.gv_rv(M.common_panel(_shock_after(spot, D), M.G9), D)
    assert shocked == pytest.approx(base)
    moved = M.gv_rv(M.common_panel(_shock_after(spot, "2019-04-10"), M.G9), D)   # published fixes do move it
    assert moved != pytest.approx(base)


def test_expanding_fc_uses_only_targets_known_at_the_decision():
    rng = np.random.default_rng(3)
    n = 60
    x, y = rng.normal(size=n), rng.normal(size=n)
    months = M.mrange("2010-01", M.madd("2010-01", n - 1))
    dday = [M.month_end_day(m) for m in months]
    kday = [M.month_end_day(M.madd(m, 4)) for m in months]       # each target ends 4 months later
    origins = np.zeros(n, bool)
    origins[45] = True
    fm, fb, _ = M.expanding_fc(x, y, kday, dday, np.ones(n, bool), origins)
    y2 = y.copy()
    unknown = np.array([k > dday[45] for k in kday])
    y2[unknown] += 100.0
    x2 = x.copy()
    x2[46:] += 50.0
    fm2, fb2, _ = M.expanding_fc(x2, y2, kday, dday, np.ones(n, bool), origins)
    assert fm2[45] == pytest.approx(fm[45]) and fb2[45] == pytest.approx(fb[45])


def test_position_net_costs():
    net, _gross = M.position_net([1.0, 1.0, -1.0], [0.0, 0.0, 0.0])
    assert net[0] == pytest.approx(-(M.LEG + M.ROLL))
    assert net[1] == pytest.approx(-M.ROLL)
    assert net[2] == pytest.approx(-(2 * M.LEG + M.ROLL + M.LEG))     # flip plus the final close


# ------------------------------------------------------------------------------------------------------- T-720 --

def test_t720_vp_ignores_prices_after_t():
    days = _weekdays("2015-01-01", "2015-08-31")
    rng = np.random.default_rng(4)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    vix = {d: float(v) for d, v in zip(days, rng.uniform(12, 30, len(days)))}
    base = M.vp_frame(days, close, vix, "2015-02", "2015-07")
    j = base["month"].index("2015-04")
    t = base["day"][j]
    c2 = close.copy()
    c2[[i for i, d in enumerate(days) if d > t]] *= 1.7
    v2 = {d: (v * 3 if d > t else v) for d, v in vix.items()}
    sh = M.vp_frame(days, c2, v2, "2015-02", "2015-07")
    assert sh["vp"][j] == pytest.approx(base["vp"][j])
    assert base["vp"][j] == pytest.approx(base["vix"][j] ** 2 / 12 - base["rv"][j])


def test_t720_controls_use_published_fixes_and_known_rates_only():
    days = _weekdays("2016-01-01", "2016-09-30")
    spot = _spot(days, M.G9, 5)
    months = M.mrange("2015-06", "2016-09")
    R = {c: (months, {m: 1.0 + 0.1 * k for k, m in enumerate(months)}) for c in ("USD",) + M.G9}
    rel = {c: {m: M.month_end_day(M.madd(m, 1)) for m in months} for c in ("USD",) + M.G9}
    pit = M.PitRates("proxy", R, rel=rel)
    dec = ["2016-03-31", "2016-04-29", "2016-05-31", "2016-06-30"]
    base = M.t720_targets(M.common_panel(spot, M.G9), R, pit, dec)
    t = dec[2]
    R2 = {c: (ms, {m: (v + 9.0 if rel[c][m] > t else v) for m, v in d.items()}) for c, (ms, d) in R.items()}
    pit2 = M.PitRates("proxy", R2, rel=rel)
    sh = M.t720_targets(M.common_panel(_shock_after(spot, t), M.G9), R2, pit2, dec)
    assert sh["last_dol"][2] == pytest.approx(base["last_dol"][2])
    assert sh["afd_pit"][2] == pytest.approx(base["afd_pit"][2])


def test_median_arm_uses_previous_decisions_only():
    rng = np.random.default_rng(6)
    vp = rng.normal(size=100)
    oos = np.zeros(100, bool)
    oos[70:] = True
    s = M.median_arm(vp, oos)
    v2 = vp.copy()
    v2[81:] += 10.0
    assert M.median_arm(v2, oos)[80] == s[80]
    assert np.isnan(M.median_arm(vp, np.ones(100, bool))[10])


# ------------------------------------------------------------------------------------------- point-in-time rates --

def test_pit_proxy_rates_ignore_later_releases():
    months = M.mrange("2018-01", "2018-12")
    R = {"USD": (months, {m: 2.0 + 0.05 * k for k, m in enumerate(months)})}
    rel = {"USD": {m: M.month_end_day(M.madd(m, 1 + (k % 2))) for k, m in enumerate(months)}}
    pit = M.PitRates("proxy", R, rel=rel)
    D = "2018-07-31"
    m0, x0, _ = pit.known("USD", D)
    assert rel["USD"][m0] <= D
    R2 = {"USD": (months, {m: (v + 5.0 if rel["USD"][m] > D else v) for m, v in R["USD"][1].items()})}
    m1, x1, _ = M.PitRates("proxy", R2, rel=rel).known("USD", D)
    assert (m1, x1) == (m0, pytest.approx(x0))


def test_first_release_days_takes_the_earliest_release():
    rows = [{"day": "2010-03-01", "realtime_start": "2013-06-03", "first_release": True, "first_vintage": True,
             "lag_rule_at": "2010-05-15T23:59:59+00:00", "value": 1.0},
            {"day": "2014-03-01", "realtime_start": "2014-05-02", "first_release": True, "first_vintage": False,
             "lag_rule_at": None, "value": 2.0},
            {"day": "2014-03-01", "realtime_start": "2015-01-01", "first_release": False, "value": 2.1}]
    assert M.first_release_days(rows) == {"2010-03": "2010-05-15", "2014-03": "2014-05-02"}


# ------------------------------------------------------------------------------------------------------- T-725 --

def test_t725_gv_uses_published_sessions_of_the_month_only():
    days = _weekdays("2020-01-01", "2020-05-31")
    spot = _spot(days, M.G9, 7)
    m = "2020-03"
    base = M.gv_abs(M.common_panel(spot, M.G9), m)
    sh = M.gv_abs(M.common_panel(_shock_after(spot, M.month_end_day(m)), M.G9), m)
    assert np.isfinite(base) and sh == pytest.approx(base)


def test_t725_ar1_flag_ignores_later_months():
    rng = np.random.default_rng(8)
    gv = 0.005 + 0.001 * rng.random(200)
    base = M.ar1_flags(gv, 5)
    t = 120
    g2 = gv.copy()
    g2[t + 1:] *= 4.0
    sh = M.ar1_flags(g2, 5)
    assert sh["u"][t] == pytest.approx(base["u"][t])
    assert sh["thr"][t] == pytest.approx(base["thr"][t])
    assert sh["flag"][t] == base["flag"][t]
    assert base["flag"][: t + 1].sum() > 0


def test_t725_carry_weights_use_rates_known_at_the_decision():
    months = M.mrange("2017-01", "2017-12")
    rng = np.random.default_rng(9)
    R = {c: (months, {m: float(rng.normal(2, 1)) for m in months}) for c in M.G10U}
    rel = {c: {m: M.month_end_day(M.madd(m, 1)) for m in months} for c in M.G10U}
    D = "2017-06-30"
    w = M.carry_weights(M.PitRates("proxy", R, rel=rel), D)
    R2 = {c: (ms, {m: (v + 50.0 * (k + 1) if rel[c][m] > D else v) for m, v in d.items()})
          for k, (c, (ms, d)) in enumerate(R.items())}
    w2 = M.carry_weights(M.PitRates("proxy", R2, rel=rel), D)
    assert w == w2
    assert sum(v > 0 for v in w.values()) == 3 and sum(v < 0 for v in w.values()) == 3


def test_book_net_switch_costs():
    rows = [{"H": f"2015-0{k + 1}", "w": np.array([1 / 3, 1 / 3, 1 / 3, -1 / 3, -1 / 3, -1 / 3, 0, 0, 0, 0]),
             "r": np.zeros(10)} for k in range(3)]
    un, _ = M.book_net(rows, M.G10U)
    tn, _ = M.book_net(rows, M.G10U, [1.0, 0.0, 1.0], switch=M.T725_SWITCH)
    nonusd = 5 / 3                                               # USD (first) carries a third of the long leg as cash
    assert tn[1] == pytest.approx(-nonusd * 2e-4 - nonusd * M.T725_SWITCH)
    assert tn[2] < un[2]


def test_sb_sharpe_diff_signs():
    rng = np.random.default_rng(10)
    b = rng.normal(0, 0.02, 160)
    a = b + 0.01
    r = M.sb_sharpe_diff(a, b, n_boot=500, n_seeds=1)
    assert r["diff"] > 0 and r["p"] < 0.05


# ------------------------------------------------------------------------------------------------------- T-728 --

def test_t728_betas_ignore_rows_at_or_after_t():
    rng = np.random.default_rng(11)
    T = 120
    Rm = rng.normal(0, 0.02, (T, 11))
    dv = rng.normal(0, 3, T)
    B = M.rolling_betas(Rm, dv)
    t = 90
    R2, d2 = Rm.copy(), dv.copy()
    R2[t:] += 1.0
    d2[t:] *= -5.0
    B2 = M.rolling_betas(R2, d2)
    assert np.allclose(B2[t], B[t])
    Bd = M.rolling_betas_draws(Rm, dv[None, :])[0]
    assert np.allclose(Bd[M.T728_BETA_N:], B[M.T728_BETA_N:])


def test_t728_vix_month_end_and_sort():
    vd = ["2019-01-30", "2019-01-31", "2019-02-27", "2019-03-29"]
    vv = np.array([10.0, 11.0, 12.0, 13.0])
    out = M.vix_month_end(vd, vv, ["2019-01", "2019-02", "2019-03", "2019-04"])
    assert list(out[:3]) == [11.0, 12.0, 13.0] and np.isnan(out[3])
    w = M.sort_weights(np.arange(11, dtype=float))
    assert np.allclose(w[:3], 1 / 3) and np.allclose(w[-3:], -1 / 3) and np.allclose(w[3:8], 0)


def _t728_inputs(seed: int = 12):
    days = _weekdays("2008-01-01", "2014-06-30")
    spot = _spot(days, M.U11, seed)
    rng = np.random.default_rng(seed)
    vix = {d: float(v) for d, v in zip(days, 15 + 5 * np.abs(np.cumsum(rng.normal(0, 0.3, len(days)))) % 40)}
    rmonths = M.mrange("2007-12", "2014-06")
    R = {c: (rmonths, {m: float(rng.normal(3, 1)) for m in rmonths}) for c in ("USD",) + M.U11}
    return spot, vix, R


def _t728_beta(spot, vix, R, months, H):
    P = M.common_panel(spot, M.U11)
    vd = sorted(vix)
    vv = np.array([vix[d] for d in vd])
    _Rm, _dv, B = M.t728_betas(P, R, vd, vv, months)
    midx = {m: i for i, m in enumerate(months)}
    return M.t728_decision_beta(P, B, midx, H), B, midx


def test_t728_pipeline_weights_for_h_ignore_month_h_minus_1_and_later():
    spot, vix, R = _t728_inputs()
    months = M.mrange("2008-01", "2014-05")
    H = "2014-03"                                               # decided at the end of 2014-02; window 2009-02..2014-01
    b0, B0, midx = _t728_beta(spot, vix, R, months, H)
    assert b0 is not None and np.isfinite(b0).all()
    w0 = M.sort_weights(b0)
    cut = "2014-02-01"                                          # month H-1 and everything later
    sp2 = {c: {d: (v * (1.5 if i % 2 else 0.6) if d >= cut else v) for i, (d, v) in enumerate(sorted(s.items()))}
           for c, s in spot.items()}
    vx2 = {d: (v * 3.0 + 7.0 if d >= cut else v) for d, v in vix.items()}
    R2 = {c: (ms, {m: (v + 9.0 if m >= "2014-01" else v) for m, v in d.items()}) for c, (ms, d) in R.items()}
    b1, B1, _ = _t728_beta(sp2, vx2, R2, months, H)
    assert np.allclose(b1, b0)
    assert np.array_equal(M.sort_weights(b1), w0)
    # an off-by-one (row H instead of H-1) would put month H-1 in the window: that row does move
    assert not np.allclose(B1[midx[H]], B0[midx[H]])
    # and the window does reach month H-2: shocking only its fixes moves the betas
    sp3 = {c: {d: (v * (1.5 if i % 2 else 0.6) if d[:7] == "2014-01" else v) for i, (d, v) in enumerate(sorted(s.items()))}
           for c, s in spot.items()}
    b3, _, _ = _t728_beta(sp3, vix, R, months, H)
    assert not np.allclose(b3, b0)


def test_t728_monthly_excess_runs_last_common_fix_to_last_common_fix():
    spot, _vix, R = _t728_inputs(13)
    del spot["ZAR"]["2014-01-31"]                               # the last common fix of 2014-01 becomes 01-30
    P = M.common_panel(spot, M.U11)
    months = M.mrange("2013-11", "2014-03")
    Rm = M.monthly_excess(P, R, months)
    j = months.index("2014-02")
    a, b = "2014-01-30", "2014-02-28"
    assert P["days"][P["last"]["2014-01"]] == a and P["days"][P["last"]["2014-02"]] == b
    us = R["USD"][1]["2014-01"]
    exp = np.array([spot[c][b] / spot[c][a] - 1.0 + (R[c][1]["2014-01"] - us) / 1200.0 for c in M.U11])
    assert np.allclose(Rm[j], exp)


def test_lag_rates_use_month_t_minus_2_only():
    months = M.mrange("2017-01", "2017-12")
    rng = np.random.default_rng(14)
    R = {c: (months, {m: float(rng.normal(2, 1)) for m in months}) for c in M.G10U}
    D = "2017-06-30"
    lag = M.LagRates(R)
    m, x, _ = lag.known("USD", D)
    assert m == "2017-04" and x == pytest.approx(R["USD"][1]["2017-04"])
    w = M.carry_weights(lag, D)
    R2 = {c: (ms, {mm: (v + 40.0 * (k + 1) if mm > "2017-04" else v) for mm, v in d.items()})
          for k, (c, (ms, d)) in enumerate(R.items())}
    assert M.carry_weights(M.LagRates(R2), D) == w


def test_gain_and_placebo_are_none_not_zero_when_a_sharpe_is_undefined():
    rng = np.random.default_rng(15)
    x = rng.normal(0, 0.02, 40)
    assert M._gain(np.zeros(40), x) is None and M._gain(x, np.zeros(40)) is None
    assert M._gain(x, x) == pytest.approx(0.0)
    rows = [{"H": f"2015-{k + 1:02d}", "w": np.array([1 / 3, 1 / 3, 1 / 3, -1 / 3, -1 / 3, -1 / 3, 0, 0, 0, 0]),
             "r": rng.normal(0, 0.02, 10)} for k in range(12)]
    pl = M.placebo_gains(rows, M.G10U, 3, None, 5, rng)
    assert np.isnan(pl).all()
    assert M.placebo_summary(pl, 0.1) == {"n": 0, "p95": None, "mean": None, "pct_rank": None}
    assert M.placebo_summary(np.array([0.1, np.nan, 0.3]), None)["pct_rank"] is None


def test_tranche_positions_use_signs_decided_up_to_the_row():
    s = np.array([1.0, -1.0, 1.0, 1.0, np.nan, 1.0, 1.0, 1.0])
    J = [2, 3, 4, 5, 6, 7]
    tr = M.tranche_positions(s, J)
    assert np.allclose(tr[[0, 1, 5]], [1 / 3, 1 / 3, 1.0]) and np.isnan(tr[2:5]).all()
    s2 = s.copy()
    s2[4:] = -1.0
    assert M.tranche_positions(s2, [2, 3]) == pytest.approx(tr[:2])


def test_fe_panel_slope_recovers_the_slope_and_ignores_currency_constants():
    rng = np.random.default_rng(16)
    G, C = 150, 9
    x = rng.normal(size=G)
    Y = 0.5 * x[:, None] + rng.normal(0, 0.5, (G, C))
    Y[rng.random((G, C)) < 0.05] = np.nan
    r = M.fe_panel_slope(Y, x)
    assert r["b"] == pytest.approx(0.5, abs=0.08) and r["t"] > 5 and r["n_months"] == G
    r2 = M.fe_panel_slope(Y + np.arange(C)[None, :] * 3.0, x)
    assert r2["b"] == pytest.approx(r["b"]) and r2["t"] == pytest.approx(r["t"])


def test_t720_dtb3_us_leg_replaces_only_the_us_accrual():
    days = _weekdays("2016-01-01", "2016-09-30")
    spot = _spot(days, M.G9, 17)
    months = M.mrange("2015-06", "2016-09")
    R = {c: (months, {m: 1.0 for m in months}) for c in ("USD",) + M.G9}
    dec = ["2016-03-31", "2016-04-29", "2016-05-31", "2016-06-30"]
    P = M.common_panel(spot, M.G9)
    a = M.t720_targets(P, R, None, dec)
    b = M.t720_targets(P, R, None, dec, us_rate={m: 3.0 for m in months})
    ok = np.isfinite(a["y1"])
    assert ok.sum() >= 2
    assert np.allclose(b["y1"][ok] - a["y1"][ok], (1.0 - 3.0) / 1200.0)
    assert np.allclose(b["y1c"][ok] - a["y1c"][ok], (1.0 - 3.0) / 1200.0)
    assert M.month_avg({"2020-01-02": 1.0, "2020-01-03": 3.0, "2020-02-03": 5.0}) == {"2020-01": 2.0, "2020-02": 5.0}
