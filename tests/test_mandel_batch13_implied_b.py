"""Batch 13, group implied_b (T-649, T-650, T-653): point-in-time signal construction, the statistics, and missing data."""

import math

import numpy as np
import pytest

from mandel.experiments import batch13_implied_b as M


def _bdays(n, start="1985-01-02"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(2 * n, "D"), dtype="datetime64[D]")
    d = d[np.is_busday(d)][:n]
    return [str(x) for x in d]


def _walk(n, seed, vol=0.01):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0.0003, vol, n)))


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


# ======================================================================================== T-649: VRP and HAR ==

def test_vrp_and_har_at_t_ignore_everything_after_t():
    n = 6000
    days = _bdays(n)
    px = _walk(n, 1)
    rng = np.random.default_rng(2)
    vix = {d: float(v) for d, v in zip(days, 15 + 5 * rng.random(n))}
    fr = M.vrp_frame(days, px, vix, har_from="1900-01-01", har_min=252)
    k = 150
    t = fr["pos"][k]
    px2 = px.copy()
    px2[t + 1:] *= np.exp(np.cumsum(rng.normal(0, 0.05, n - t - 1)))      # violent shock strictly after the close of t
    vix2 = {d: (v * 3 if d > days[t] else v) for d, v in vix.items()}
    fr2 = M.vrp_frame(days, px2, vix2, har_from="1900-01-01", har_min=252)
    assert np.isfinite(fr["vrp_har"][k]) and np.isfinite(fr["vrp"][k])
    for key in ("vrp", "vrp_har", "rv", "har", "vix"):
        assert _same(fr[key][:k + 1], fr2[key][:k + 1]), key
    assert not _same(fr["vrp"][k + 1:], fr2["vrp"][k + 1:])                  # the shock is visible later
    px3 = px.copy()
    px3[t] *= 1.05                                                           # a move AT t does enter VRP_t
    assert M.vrp_frame(days, px3, vix, har_from="1900-01-01", har_min=252)["vrp"][k] != fr["vrp"][k]


def test_vrp_definition_matches_formula():
    n = 400
    days = _bdays(n)
    px = _walk(n, 3)
    vix = {d: 20.0 for d in days}
    fr = M.vrp_frame(days, px, vix, har_from="1900-01-01", har_min=10 ** 9)
    t = fr["pos"][5]
    r = np.log(px[t - 20:t + 1] / px[t - 21:t])
    assert fr["vrp"][5] == pytest.approx(0.2 ** 2 / 12 - float(r @ r))


def _monthly_pipeline(px, days, x_of_day, restrict, h=63):
    pos = M.month_end_pos(days)
    n = len(days)
    y, end = M.window_targets(pos, h, n, lambda a, e: px[e] / px[a] - 1.0)
    x = np.array([x_of_day[days[i]] for i in pos], float)
    train = np.ones(pos.size, bool)
    org = np.arange(pos.size) >= 60
    fm, fb, sl = M.expanding_ols(x, y, pos, end, train, org, restrict=restrict)
    return pos, y, end, fm, fb, sl


@pytest.mark.parametrize("restrict", [False, True])
def test_expanding_forecast_at_t_uses_only_targets_ended_by_t(restrict):
    n = 5000
    days = _bdays(n)
    px = _walk(n, 4)
    rng = np.random.default_rng(5)
    xs = {d: float(v) for d, v in zip(days, rng.normal(size=n))}
    pos, y, end, fm, fb, _ = _monthly_pipeline(px, days, xs, restrict)
    j = 120
    t = pos[j]
    px2 = px.copy()
    px2[t + 1:] *= np.exp(np.cumsum(rng.normal(0, 0.05, n - t - 1)))
    xs2 = {d: (v + 10 * rng.normal() if d > days[t] else v) for d, v in xs.items()}
    _, y2, _, fm2, fb2, _ = _monthly_pipeline(px2, days, xs2, restrict)
    assert np.isfinite(fm[j]) and np.isfinite(fb[j])
    assert _same(fm[:j + 1], fm2[:j + 1]) and _same(fb[:j + 1], fb2[:j + 1])
    assert not _same(y[j - 2:j + 1], y2[j - 2:j + 1])                      # targets still running at t did move
    assert (end[np.isfinite(y) & (end <= t)] <= t).all()


def test_slope_restriction_replaces_negative_slope_with_prevailing_mean():
    rng = np.random.default_rng(6)
    M_ = 200
    pos = np.arange(M_) * 21
    end = pos + 22
    x = rng.normal(size=M_)
    y = -0.5 * x + 0.01 * rng.normal(size=M_)
    org = np.arange(M_) >= 50
    fm, fb, sl = M.expanding_ols(x, y, pos, end, np.ones(M_, bool), org, restrict=True)
    assert (sl[org] < 0).all() and np.allclose(fm[org], fb[org])
    fm_u, _, _ = M.expanding_ols(x, y, pos, end, np.ones(M_, bool), org, restrict=False)
    assert not np.allclose(fm_u[org], fb[org])


def test_compounded_excess_target_and_cor1m_forecast_point_in_time():
    n = 4000
    days = _bdays(n, "2004-01-02")
    A = _walk(n, 7)
    rb = np.full(n, 0.0001)
    ex = np.zeros(n)
    ex[1:] = A[1:] / A[:-1] - 1 - rb[1:]
    E = np.cumprod(1 + ex)
    rng = np.random.default_rng(8)
    cor = {d: float(v) for d, v in zip(days, 30 + 10 * rng.random(n))}
    pos, y, end, fm, fb, _ = _monthly_pipeline(E, days, cor, True, h=126)
    a, e = pos[3] + 1, pos[3] + 1 + 126
    assert y[3] == pytest.approx(np.prod(1 + ex[a + 1:e + 1]) - 1)        # daily excess compounded over the window
    j = 100
    t = pos[j]
    E2 = E.copy()
    E2[t + 1:] *= 1.5
    cor2 = {d: (v * 2 if d > days[t] else v) for d, v in cor.items()}
    _, _, _, fm2, fb2, _ = _monthly_pipeline(E2, days, cor2, True, h=126)
    assert _same(fm[:j + 1], fm2[:j + 1]) and _same(fb[:j + 1], fb2[:j + 1])


def test_timing_rule_weights_costs_and_leverage():
    fm = np.array([0.02, 0.05, -0.01, np.nan])
    fb = np.array([0.02, 0.02, 0.02, 0.02])
    w = M.timing_weights(fm, fb)
    assert w.tolist() == [1.0, 1.5, 0.0, 0.0]
    rs, rb, cd = np.full(4, 0.01), np.full(4, 0.003), np.full(4, 30.0)
    ex = M.timing_excess(w, rs, rb, cd)
    assert ex[0] == pytest.approx(0.01 - 0.003 - 2e-4)                       # first entry pays 2 bp
    assert ex[1] == pytest.approx(1.5 * 0.007 - 0.5 * 0.005 * 30 / 365 - 2e-4)
    assert ex[3] == pytest.approx(0.0)                                       # unchanged weight: no cost


# ============================================================================================== statistics ==

def test_oos_stats_and_clark_west_reward_an_informative_forecast():
    rng = np.random.default_rng(9)
    n = 300
    s = rng.normal(size=n)
    y = 0.5 * s + rng.normal(size=n)
    fb = np.zeros(n)
    good = M.oos_stats(y, 0.5 * s, fb, np.ones(n, bool), 3)
    bad = M.oos_stats(y, -0.5 * s, fb, np.ones(n, bool), 3)
    assert good["oos_r2"] > 0 and good["cw_p"] < 0.01
    assert bad["oos_r2"] < 0 and bad["cw_p"] > 0.5


def test_nw_and_multi_ols():
    rng = np.random.default_rng(10)
    X = np.column_stack([np.ones(500), rng.normal(size=(500, 2))])
    y = X @ np.array([0.1, -0.3, 0.0]) + 0.1 * rng.normal(size=500)
    r = M.ols_nw_multi(y, X, 5)
    assert r["beta"][1] == pytest.approx(-0.3, abs=0.02) and r["t"][1] < -20
    assert M.nw_mean(np.ones(10) + np.arange(10) * 0, 2)["mean"] == 1.0


def test_family_dsr_bound_never_passes():
    rng = np.random.default_rng(11)
    strong = rng.normal(0.5, 1.0, 2000)
    (name, ok, dec), info = M.dsr_vs_uncomputed_family(strong, 9, "x")
    assert ok is None and info["dsr_upper_bound"] >= 0.95
    (name, ok, dec), _ = M.dsr_vs_uncomputed_family(rng.normal(-0.2, 1.0, 2000), 9, "x")
    assert ok is False and dec is True


# =========================================================================================== T-653: PC2 ==

def _curve_logs(n, seed):
    rng = np.random.default_rng(seed)
    lvl = np.cumsum(rng.normal(0, 0.03, n)) * 0.3 + math.log(18)
    slope = np.cumsum(rng.normal(0, 0.01, n)) * 0.3 + 0.1
    tau = np.array([-1.0, -0.5, 0.3, 1.0])
    return lvl[:, None] + slope[:, None] * tau[None, :] + rng.normal(0, 0.01, (n, 4))


def test_pc2_and_quintiles_at_t_ignore_everything_after_t():
    n = 1500
    days = _bdays(n, "2011-01-03")
    L = _curve_logs(n, 12)
    pcs = M.curve_pcs(days, L, min_pca=252)
    q = M.expanding_quintiles(days, pcs["pc2"], pcs["valid"], days[300], days[-1], min_hist=252)
    t = 900
    L2 = L.copy()
    L2[t + 1:] += np.random.default_rng(13).normal(0, 1.0, (n - t - 1, 4))  # shock strictly after t
    pcs2 = M.curve_pcs(days, L2, min_pca=252)
    q2 = M.expanding_quintiles(days, pcs2["pc2"], pcs2["valid"], days[300], days[-1], min_hist=252)
    assert _same(pcs["pc2"][:t + 1], pcs2["pc2"][:t + 1]) and _same(pcs["pc1"][:t + 1], pcs2["pc1"][:t + 1])
    assert (q[:t + 1] == q2[:t + 1]).all() and (q[t + 1:] != q2[t + 1:]).any()
    v = pcs["valid"]
    assert (pcs["load2"][v, 3] - pcs["load2"][v, 0] >= 0).all()             # sign normalised point in time
    assert set(np.unique(q[q > 0])) == {1, 2, 3, 4, 5} and (q[:251 + 252] == 0).all() and q[251 + 252] > 0


def test_steeper_contango_raises_pc2():
    n = 800
    days = _bdays(n, "2011-01-03")
    L = _curve_logs(n, 14)
    base = M.curve_pcs(days, L)["pc2"][-1]
    L2 = L.copy()
    L2[-1] += np.array([-0.2, -0.1, 0.1, 0.2])                               # steeper on the last day only
    assert M.curve_pcs(days, L2)["pc2"][-1] > base


def _toy_curve(days, seed):
    rng = np.random.default_rng(seed)
    exps = sorted({d for d in days if d[8:] in ("15", "16", "17") and np.is_busday(np.datetime64(d))})
    exps = [e for i, e in enumerate(exps) if i == 0 or e[:7] != exps[i - 1][:7]]
    exps += ["2099-01-15", "2099-02-15"]
    curve = {}
    for d in days:
        later = [e for e in exps if e >= d][:4]
        curve[d] = {e: float(18 + j + rng.normal(0, 0.5)) for j, e in enumerate(later)}
    return curve


def test_cm_vx_weights_and_returns_start_after_t():
    curve = {"2020-01-02": {"2020-01-12": 10.0, "2020-02-11": 20.0}, "2020-01-03": {"2020-01-12": 11.0, "2020-02-11": 22.0}}
    cm = M.cm_vx_daily(curve)
    assert cm["w1"][0] == pytest.approx((40 - 30) / (40 - 10))               # tau1 10, tau2 40 calendar days
    p0 = cm["w1"][0] * 10 + (1 - cm["w1"][0]) * 20
    p1 = cm["w1"][0] * 11 + (1 - cm["w1"][0]) * 22
    assert cm["ret"][0] == pytest.approx(p1 / p0 - 1) and cm["dollar"][0] == pytest.approx(1000 * (p1 - p0))
    days = _bdays(200, "2020-01-02")
    cv = _toy_curve(days, 15)
    cm = M.cm_vx_daily(cv)
    sig = days[50:150]
    y = M.forward_returns(sig, cm["days"], cm["ret"])
    t = days[100]
    i = sig.index(t)
    cv2 = {d: ({e: s * 1.3 for e, s in v.items()} if d <= t else v) for d, v in cv.items()}   # shock AT and before t
    y2 = M.forward_returns(sig, M.cm_vx_daily(cv2)["days"], M.cm_vx_daily(cv2)["ret"])
    assert y2[i] == pytest.approx(y[i])                                      # the t+1..t+6 settle return never sees t
    k1 = cm["days"].index(days[101])
    assert y[i] == pytest.approx(np.prod(1 + cm["ret"][k1:k1 + 5]) - 1)


def test_gate_at_t_trades_from_the_next_settle():
    days = _bdays(60, "2021-01-04")
    cm = M.cm_vx_daily(_toy_curve(days, 16))
    gate = np.zeros(len(days), bool)
    gate[20] = True
    tf = M.gated_short_vx(cm, days, gate, days[0], days[-1])
    k = tf["days"].index(days[21])
    on = np.where(np.abs(tf["gated"]) > 1e-9)[0]
    assert set(on) == {k, k + 1}                     # held only over [settle t+1, settle t+2]; the exit is booked at t+2
    assert tf["gated"][k] == pytest.approx(-cm["dollar"][cm["days"].index(days[21])] - 70.0)
    assert tf["gated"][k + 1] == pytest.approx(-70.0)


def test_cm_vx_rebalance_and_roll_trades_are_charged_in_both_arms():
    e1, e2, e3 = "2020-01-15", "2020-02-19", "2020-03-18"
    curve = {"2020-01-13": {e1: 15.0, e2: 17.0, e3: 18.0}, "2020-01-14": {e1: 15.5, e2: 17.2, e3: 18.1},
             "2020-01-15": {e1: 15.2, e2: 17.1, e3: 18.0}, "2020-01-16": {e2: 17.4, e3: 18.3}}
    cm = M.cm_vx_daily(curve)
    w = cm["w1"]
    assert w[0] == pytest.approx(7 / 35) and w[1] == pytest.approx(6 / 35) and w[2] == 1.0    # e1 expires on 01-15
    assert cm["e1"][2] == e2 and cm["e2"][2] == e3
    idx = [0, 1, 2]
    c = M.vx_trade_costs(cm, idx, np.ones(3, bool))
    reweight = 2 * (w[0] - w[1])                                             # F1 down, F2 up by the same amount
    roll = w[1] + abs(1.0 - (1.0 - w[1])) + 0.0                              # e1 settles (w1), e2 tops up to 1, e3 0
    assert c["traded"].tolist() == pytest.approx([1.0, reweight, roll, 1.0])
    assert c["settled"].tolist() == pytest.approx([0.0, 0.0, w[1], 0.0])
    assert c["cost"].tolist() == pytest.approx([70.0, 70 * reweight, 70 * (roll + 1.0)])  # final exit booked on the last
    tf = M.gated_short_vx(cm, ["2020-01-10", "2020-01-13", "2020-01-14", "2020-01-15"], np.array([True, True, True, True]),
                          "2020-01-13", "2020-01-15")
    assert tf["always"].tolist() == pytest.approx((-cm["dollar"][:3] - c["cost"]).tolist())
    assert tf["gated"].tolist() == pytest.approx(tf["always"].tolist())        # gate always on = always-short
    g = M.vx_trade_costs(cm, idx, np.array([False, True, False]))
    assert g["cost"].tolist() == pytest.approx([0.0, 70.0, 70.0])               # on only over [01-14, 01-15]: no re-weighting
    assert g["settled"][2] == pytest.approx(w[1])                               # its e1 leg closes at the final settle
    k = M.vx_trade_costs(cm, idx, np.array([True, True, False]))
    assert k["cost"][1] == pytest.approx(70 * reweight) and k["cost"][2] == pytest.approx(70.0)


# ============================================================================ end-to-end cores (synthetic) ==

_VERDICTS = {"supported", "not_supported", "inconclusive"}


def _bills(days):
    return M.CAL.Bills({d: 2.0 for d in days[::5]})


def test_vrp_core_runs_end_to_end_and_counts_the_registered_forecasts():
    days = _bdays(9900, "1989-01-02")
    days = [d for d in days if d <= "2026-10-15"]
    n = len(days)
    px = _walk(n, 21)
    rng = np.random.default_rng(22)
    vix = {d: float(v) for d, v in zip(days, 14 + 10 * rng.random(n)) if d >= "1990-01-02"}
    spy = {d: float(v) for d, v in zip(days, _walk(n, 23)) if d >= "1993-01-29"}
    rep = M.vrp_premium_test(days, px, vix, spy, _bills(days), n_boot=60, reps=1)
    assert rep["verdict"] in _VERDICTS and rep["n"] == 222                  # 2008-01..2026-06 month-ends
    assert rep["stat"]["first_last_forecast"] == ["2008-01-31", "2026-06-30"]
    assert len(rep["stat"]["criteria"]) == 5                                 # the CT-truncated reading is not judged
    ct = rep["stat"]["ct_truncated_not_registered"]
    assert set(ct) == {"h21", "h63", "h126"} and ct["h63"]["n"] == 222
    assert rep["stat"]["timing_rule_identical_under_truncation"] is True
    assert "No Campbell-Thompson slope or sign restriction is applied" in rep["reason"]


def test_cor1m_core_runs_end_to_end_and_counts_the_registered_forecasts():
    days = [d for d in _bdays(6000, "2005-01-03") if d <= "2026-10-15"]
    n = len(days)
    adj = _walk(n, 24)
    rng = np.random.default_rng(25)
    cor = {d: float(v) for d, v in zip(days, 20 + 40 * rng.random(n)) if d >= "2006-01-03"}
    dspx = {d: float(v) for d, v in zip(days, 15 + 20 * rng.random(n)) if d >= "2014-06-19"}
    vix = {d: float(v) for d, v in zip(days, 14 + 10 * rng.random(n))}
    rep = M.cor1m_premium_test(days, adj, adj, cor, dspx, vix, _bills(days), n_boot=60, reps=1)
    assert rep["verdict"] in _VERDICTS and rep["n"] == 159                  # 2013-01..2026-03 month-ends
    assert rep["stat"]["cells"]["dspx_h126"]["n"] > 0
    assert len(rep["stat"]["criteria"]) == 4


def test_vix_curve_core_runs_end_to_end_and_never_passes_the_uncomputed_family_dsr():
    days = [d for d in _bdays(4200, "2011-01-03") if d <= "2026-10-15"]
    n = len(days)
    L = _curve_logs(n, 26)
    idx = {t: {d: float(math.exp(L[i, j])) for i, d in enumerate(days)} for j, t in enumerate(M.TENORS)}
    curve = {d: v for d, v in _toy_curve(days, 27).items() if d >= "2013-05-20"}
    vxx = ([d for d in days if d >= "2018-01-25"], _walk(sum(d >= "2018-01-25" for d in days), 28, 0.04))
    svxy = ([d for d in days if d >= "2011-10-04"], _walk(sum(d >= "2011-10-04" for d in days), 29, 0.03))
    rep = M.vix_curve_test(idx, curve, vxx, svxy)
    assert rep["verdict"] in {"not_supported", "inconclusive"} and rep["n"] > 1500
    assert rep["stat"]["criteria"][2][1] in (False, None)                  # the family DSR can fail but never pass


# ======================================================================================= missing bundles ==

class _NoArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


@pytest.mark.parametrize("name", list(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    stat, n, verdict, reason = M.HARNESSES[name](_NoArchive())
    assert verdict == "inconclusive" and n == 0 and "missing" in reason


def test_theory_map_covers_the_group():
    assert set(M.THEORY_MAP) == {"T-649", "T-650", "T-653"} and set(M.THEORY_MAP.values()) == set(M.HARNESSES)
