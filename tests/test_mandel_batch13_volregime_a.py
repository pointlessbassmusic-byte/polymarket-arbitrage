"""Batch 13, group volregime_a (T-679, T-681, T-684, T-685): point-in-time signal construction, the DP / Hodrick
machinery, and inconclusive verdicts on missing bundles."""

import itertools
import math

import numpy as np
import pytest

from mandel.experiments import batch13_volregime_a as M


def _bdays(n, start="1990-01-02"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(2 * n + 10, "D"), dtype="datetime64[D]")
    d = d[np.is_busday(d)][:n]
    return [str(x) for x in d]


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


# ================================================================================================ T-679 ==

def _spy_like(n, seed):
    rng = np.random.default_rng(seed)
    vol = 0.01 * np.exp(0.5 * np.sin(np.arange(n) / 90.0))
    r = rng.normal(0.0003, 1.0, n) * vol
    adj = 100 * np.cumprod(1 + r)
    B = np.cumprod(np.r_[1.0, np.full(n - 1, 1.0001)])
    return adj, B


def test_vol_target_weights_at_decision_ignore_later_data():
    n = 1500
    days = _bdays(n)
    adj, B = _spy_like(n, 1)
    vix = {d: 15.0 + (i % 17) for i, d in enumerate(days)}
    R = M.vol_target_family(days, adj, B, vix, win=("1991-01", "1994-06"))
    mdec = R["mdec"]
    k = 30
    D = int(mdec[k])
    adj2 = adj.copy()
    adj2[D + 1:] *= np.exp(np.cumsum(np.random.default_rng(9).normal(0, 0.05, n - D - 1)))   # violent path after D
    vix2 = {d: (v * 4 if d > days[D] else v) for d, v in vix.items()}
    R2 = M.vol_target_family(days, adj2, B, vix2, win=("1991-01", "1994-06"))
    for key, f in R["fam"].items():
        dec = f["dec"]
        upto = dec <= D
        assert _same(f["w_dec"][upto], R2["fam"][key]["w_dec"][upto]), key
        assert not _same(f["w_dec"][~upto], R2["fam"][key]["w_dec"][~upto]), key
    # hold-month excess returns that end by the decision close are untouched
    F = R["F"]
    done = F[1:] <= D
    for key in R["fam"]:
        assert _same(R["fam"][key]["ex_all"][done], R2["fam"][key]["ex_all"][done]), key
    # the decision close itself does enter sigma_t (known at that close; the fill is the next close)
    adj3 = adj.copy()
    adj3[D:] *= 1.08
    R3 = M.vol_target_family(days, adj3, B, vix, win=("1991-01", "1994-06"))
    j = int(np.where(R["fam"][("rv", 1.5, "monthly")]["dec"] == D)[0][0])
    assert R3["fam"][("rv", 1.5, "monthly")]["w_dec"][j] != R["fam"][("rv", 1.5, "monthly")]["w_dec"][j]


def test_mm_constant_uses_only_holds_completed_by_the_decision():
    rng = np.random.default_rng(3)
    M_ = 80
    dec = np.arange(M_) * 21 + 20
    F = dec + 1
    f = rng.normal(0.005, 0.04, M_ - 1)
    sig2 = rng.uniform(0.01, 0.06, M_)
    c = M.mm_constants(dec, sig2, f, F, min_hist=24)
    t = 50
    done = int(np.sum(F[1:] <= dec[t]))
    assert done == t - 1                                  # hold t-1 (fill t-1 -> fill t) is still open at decision t
    f2 = f.copy()
    f2[done:] *= -7.0
    c2 = M.mm_constants(dec, sig2, f2, F, min_hist=24)
    assert _same(c[:t + 1], c2[:t + 1])
    assert not _same(c[t + 1:], c2[t + 1:])
    assert np.isnan(c[:25]).all() and np.isfinite(c[30])


def test_simulate_drift_costs_and_financing():
    n = 6
    ra = np.r_[np.nan, [0.10, 0.0, 0.0, 0.0, 0.0]]
    rb = np.r_[np.nan, np.zeros(n - 1)]
    gap = np.r_[0.0, np.ones(n - 1)]
    v = M.simulate(ra, rb, gap, {0: 0.5, 3: 0.5}, 0.01, 0.0)
    assert v[0] == pytest.approx(1.0)
    after0 = 1.0 * (1 - 0.01 * 0.5)                       # entering 0.5 from cash costs 1% of 0.5
    assert v[1] == pytest.approx(after0 * (0.5 * 1.1 + 0.5))
    wd = after0 * 0.5 * 1.1 / v[3]
    assert v[4] == pytest.approx(v[3] * (1 - 0.01 * abs(0.5 - wd)))
    lev = M.simulate(np.r_[np.nan, [0.0, 0.0]], np.r_[np.nan, [0.0, 0.0]], np.r_[0.0, 365.0, 365.0], {0: 2.0}, 0.0, 0.005)
    assert lev[2] == pytest.approx(2.0 - (1.0 * 1.005 ** 2))        # the borrowed unit pays the spread


# ================================================================================================ T-681 ==

def test_umd_weights_point_in_time_both_readings():
    n = 3000
    days = _bdays(n, "1995-01-02")
    rng = np.random.default_rng(4)
    r = rng.normal(0.0002, 0.01, n)
    _, last, R = M.calendar_months(days, r)
    k = 60
    i = int(last[k])
    w0 = M.umd_weights(r, last, 126, 2.0, 0)
    w1 = M.umd_weights(r, last, 126, 2.0, 1)
    r2 = r.copy()
    r2[i + 1:] *= 5.0
    assert _same(w0[:k + 1], M.umd_weights(r2, last, 126, 2.0, 0)[:k + 1])
    assert _same(w1[:k + 1], M.umd_weights(r2, last, 126, 2.0, 1)[:k + 1])
    r3 = r.copy()
    r3[i] = 0.2                                            # a move on the month-end day itself
    assert M.umd_weights(r3, last, 126, 2.0, 1)[k] == w1[k]          # the previous-close reading never sees it
    assert M.umd_weights(r3, last, 126, 2.0, 0)[k] != w0[k]          # the as-worded reading does
    net = M.scaled_returns(w0, R, 0.002)
    assert net[k + 1] == pytest.approx(w0[k] * R[k + 1] - 0.002 * abs(w0[k] - w0[k - 1]))


def test_calendar_months_drops_an_incomplete_final_month():
    days = [d for d in _bdays(400, "2001-01-02") if d <= "2001-04-11"]          # April incomplete
    labs, last, _ = M.calendar_months(days, np.zeros(len(days)))
    assert labs[-1] == "2001-03" and days[last[-1]] == "2001-03-30"
    full = [d for d in days if d <= "2001-03-30"]                                 # March ends on its last weekday
    labs2, _, _ = M.calendar_months(full, np.zeros(len(full)))
    assert labs2[-1] == "2001-03"


# ================================================================================================ T-684 ==

def test_dp_path_is_the_exact_optimum():
    rng = np.random.default_rng(5)
    for _ in range(25):
        T = 8
        lam = float(rng.choice([0.0, 0.4, 1.5]))
        l0, l1 = rng.random(T) * 2, rng.random(T) * 2
        best = min(np.where(np.array(s), l1, l0).sum() + lam * np.abs(np.diff(s)).sum()
                   for s in itertools.product([0, 1], repeat=T))
        p = M.dp_path((l1 - l0)[None], np.array([lam]))[0]
        assert np.where(p, l1, l0).sum() + lam * np.abs(np.diff(p.astype(int))).sum() == pytest.approx(best)


def test_online_state_is_last_state_of_the_trailing_window_only():
    rng = np.random.default_rng(6)
    W, J = 40, 25
    dl = rng.normal(size=(3, W - 1 + J))
    lam = np.array([0.0, 1.0, 4.0])
    on = M.online_states(dl, lam, W, J)
    for j in range(J):
        assert np.array_equal(on[:, j], M.dp_path(dl[:, j:j + W], lam)[:, -1])
    dl2 = dl.copy()
    dl2[:, W - 1 + 11:] = rng.normal(size=(3, J - 11)) * 50            # shock strictly after day 10
    assert np.array_equal(M.online_states(dl2, lam, W, J)[:, :11], on[:, :11])


def test_jm_features_ignore_later_returns():
    rng = np.random.default_rng(7)
    x = np.r_[np.nan, rng.normal(0, 0.01, 999)]
    F = M.jm_features(x)
    x2 = x.copy()
    x2[501:] = rng.normal(0, 0.08, 499)
    assert _same(F[:501], M.jm_features(x2)[:501])


def test_jm_good_flags_and_penalty_choice_are_point_in_time():
    n = 1700
    days = _bdays(n, "1990-01-02")
    rng = np.random.default_rng(8)
    vol = np.where((np.arange(n) // 150) % 2 == 0, 0.006, 0.02)
    x = np.r_[np.nan, rng.normal(0.0003, 1.0, n - 1) * vol[1:]]
    kw = {"lams": (0.0, 5.0, 25.0), "train": 300, "warmup": 20, "n_init": 3}
    G = M.jm_good_flags(days, x, **kw)
    t = 1100
    x2 = x.copy()
    x2[t + 1:] = rng.normal(-0.01, 0.05, n - t - 1)
    G2 = M.jm_good_flags(days, x2, **kw)
    assert (G["good"][:, 400:t + 1] >= 0).all()
    assert np.array_equal(G["good"][:, :t + 1], G2["good"][:, :t + 1])
    S = M.select_penalty(days, G["good"], x, 1, years=1)
    S2 = M.select_penalty(days, G2["good"], x2, 1, years=1)
    assert np.array_equal(S["choice"][:t + 1], S2["choice"][:t + 1])
    assert np.array_equal(S["g"][:t + 1], S2["g"][:t + 1])
    # the month's choice depends only on returns before the month's first session
    fm = next(k for k in range(t - 40, t) if days[k][:7] != days[k - 1][:7])
    x3 = x.copy()
    x3[fm:] *= -3.0
    assert S["choice"][fm] == M.select_penalty(days, G["good"], x3, 1, years=1)["choice"][fm]


def test_jm_good_flags_undefined_when_a_live_feature_row_is_nonfinite(monkeypatch):
    n = 1400
    days = _bdays(n, "1990-01-02")
    rng = np.random.default_rng(9)
    x = np.r_[np.nan, rng.normal(0.0003, 0.01, n - 1)]
    kw = {"lams": (0.0, 5.0), "train": 300, "warmup": 20, "n_init": 2}
    base = M.jm_good_flags(days, x, **kw)
    live = np.where((base["good"][0] >= 0))[0]
    k = int(live[len(live) // 2])
    orig = M.jm_features

    def feats(xx):
        X = np.array(orig(xx), float)
        X[k] = np.nan
        return X
    monkeypatch.setattr(M, "jm_features", feats)
    G = M.jm_good_flags(days, x, **kw)
    # every day whose trailing 300-session window holds row k is undefined; days before k unchanged
    assert (G["good"][:, k:min(n, k + 300)] == -1).all()
    assert np.array_equal(G["good"][:, :k], base["good"][:, :k])


def test_lagged_positions_trade_at_the_close_after_the_signal():
    f = np.array([1, 0, 1, 1, -1, 0], np.int8)
    p = M.lagged_positions(f, 1)
    assert np.isnan(p[:2]).all() and list(p[2:]) == [1.0, 0.0, 1.0, 1.0]
    p5 = M.lagged_positions(np.arange(10) % 2, 5)
    assert np.isnan(p5[:6]).all() and p5[6] == 0 and p5[7] == 1
    e = M.strat_excess(np.array([np.nan, 1.0, 1.0, 0.0]), np.array([0.1, 0.02, 0.03, 0.04]), 0.001)
    assert np.isnan(e[:2]).all() and e[2] == pytest.approx(0.03) and e[3] == pytest.approx(-0.001)


# ================================================================================================ T-685 ==

def test_targets_start_at_the_next_close_and_vrp_ignores_later_data():
    from mandel.experiments import batch13_implied_b as IMP
    n = 900
    days = _bdays(n, "1995-01-02")
    rng = np.random.default_rng(10)
    px = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    vix = {d: 20.0 for d in days}
    fr = IMP.vrp_frame(days, px, vix, har_min=10 ** 9)
    pos = fr["pos"]
    r = np.r_[np.nan, np.log(px[1:] / px[:-1])]
    y, a, e = M.window_sum_targets(pos, 63, r)
    k = 10
    t = int(pos[k])
    assert a[k] == t + 1 and e[k] == t + 64
    assert y[k] == pytest.approx(math.log(px[t + 64] / px[t + 1]))
    r2 = r.copy()
    r2[t + 1] += 0.5                                       # the return INTO the next close is not in the target
    assert M.window_sum_targets(pos, 63, r2)[0][k] == pytest.approx(y[k])
    px2 = px.copy()
    px2[t + 1:] *= 1.3
    vix2 = {d: (60.0 if d > days[t] else v) for d, v in vix.items()}
    fr2 = IMP.vrp_frame(days, px2, vix2, har_min=10 ** 9)
    assert _same(fr["vrp"][:k + 1], fr2["vrp"][:k + 1])


def test_hodrick_matches_ols_and_white_on_one_period_windows():
    rng = np.random.default_rng(11)
    n = 400
    r = rng.normal(0.001, 0.01, n)
    pos = np.arange(5, n - 3)
    y, a, _ = M.window_sum_targets(pos, 1, r)
    z = rng.normal(size=pos.size)
    X = np.column_stack([np.ones(z.size), z])
    H = M.hodrick_ols(y, X, a, 1, r)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    assert np.allclose(H["beta"], b)
    u = y - y.mean()
    XtXi = np.linalg.inv(X.T @ X)
    V = XtXi @ (X * (u * u)[:, None]).T @ X @ XtXi
    assert H["se"][1] == pytest.approx(math.sqrt(V[1, 1]))


def test_hodrick_window_sums_reproduce_overlapping_targets():
    rng = np.random.default_rng(12)
    r = rng.normal(0, 0.01, 600)
    pos = np.arange(10, 500, 21)
    y, a, e = M.window_sum_targets(pos, 63, r)
    for j in range(pos.size):
        assert y[j] == pytest.approx(r[a[j] + 1:e[j] + 1].sum())


# =========================================================================================== missing data ==

class _Empty:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _, n, verdict, reason = M.HARNESSES[name](_Empty())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason


def test_theory_map_covers_every_harness():
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    assert set(M.THEORY_MAP) == {"T-679", "T-681", "T-684", "T-685"}
