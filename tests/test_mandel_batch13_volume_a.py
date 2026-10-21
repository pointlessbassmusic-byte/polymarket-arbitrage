"""Tests for mandel/experiments/batch13_volume_a.py (T-691, T-698, T-692, T-693, T-694).

Each signal construction is checked for look-ahead: values after the decision time are shocked and the signal at the
decision must not move. Every harness must return inconclusive when its bundles are missing."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch13_volume_a as M


class StubArchive:
    """An archive with nothing in it: every get() raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


def _sessions(n: int, start: str = "2010-01-04") -> list:
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _prices(D: int, N: int, seed: int = 0) -> tuple:
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0005, 0.02, (D, N))
    A = 50.0 * np.exp(np.cumsum(r, axis=0))
    C = A * rng.uniform(0.95, 1.0, (1, N))           # adjclose / close ratio constant per name
    O = C * np.exp(rng.normal(0, 0.005, (D, N)))
    V = rng.lognormal(14.0, 0.5, (D, N)) * rng.uniform(0.5, 2.0, (1, N))
    return A, C, O, V


def _shock_after(X: np.ndarray, i: int, seed: int = 9) -> np.ndarray:
    rng = np.random.default_rng(seed)
    Y = X.copy()
    Y[i + 1:] = Y[i + 1:] * rng.uniform(0.2, 5.0, Y[i + 1:].shape)
    return Y


# ================================================================================================= wiring ==

def test_maps_cover_the_five_theories():
    assert set(M.THEORY_MAP) == {"T-691", "T-698", "T-692", "T-693", "T-694"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for name, fn in M.HARNESSES.items():
        assert name.startswith("b13_volume_a_")
        assert fn.__doc__ and "T-" in fn.__doc__


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    r = M.HARNESSES[name](StubArchive())
    assert r[2] == "inconclusive"
    assert r[1] == 0
    assert "missing" in r[3]


# ============================================================================================ shared base ==

def test_identity_mask_is_point_in_time_and_flags_a_tiny_series():
    D, N = 200, 12
    A, C, O, V = _prices(D, N)
    V[:, 0] = V[:, 0] / 1000.0                            # another company's series: three orders of magnitude smaller
    member = np.ones((D, N), bool)
    m = M.identity_mask(C, V, member)
    assert m[100:, 0].all() and not m[100:, 1:].any()
    i = 120
    m2 = M.identity_mask(_shock_after(C, i), _shock_after(V, i), member)
    assert (m[:i + 1] == m2[:i + 1]).all()


def test_roll_sum_and_median_windows():
    x = np.arange(10, dtype=float)[:, None]
    s_ex = M.roll_sum(x, 3, incl=False)
    s_in = M.roll_sum(x, 3, incl=True)
    assert np.isnan(s_ex[2, 0]) and s_ex[3, 0] == 0 + 1 + 2
    assert s_in[2, 0] == 0 + 1 + 2 and s_in[9, 0] == 7 + 8 + 9
    med = M.roll_median(x, 3, chunk=2)
    assert np.isnan(med[1, 0]) and med[2, 0] == 1.0 and med[9, 0] == 8.0


def test_split_factor_matrix_counts_only_later_splits():
    days = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    F = M.split_factor_matrix(days, ["X"], {"X": [("2020-01-06", 2.0)]})
    assert F[:, 0].tolist() == [2.0, 2.0, 1.0, 1.0]


# ====================================================================================================== T-691 ==

def test_form_month_uses_no_data_after_the_formation_close():
    D, N = 120, 30
    A, C, O, V = _prices(D, N)
    member = np.ones(N, bool)
    adj = np.full(N, 1e7)
    e0, f = 79, 100
    a = M.form_month(A, C, V, member, e0, f, adj)
    b = M.form_month(_shock_after(A, f), _shock_after(C, f), _shock_after(V, f), member, e0, f, adj)
    for k in ("r", "to", "cap"):
        assert np.allclose(a[k], b[k], equal_nan=True)
    assert (a["el"] == b["el"]).all()
    assert np.allclose(a["r"], A[f] / A[e0] - 1.0)
    assert np.allclose(a["to"], V[e0 + 1:f + 1].sum(axis=0) / adj)


def test_unit_filter_rejects_scale_errors_and_is_point_in_time():
    D, N = 60, 5
    A, C, O, V = _prices(D, N)
    e0, f = 20, 41
    true = V[e0 + 1:f + 1].sum(axis=0) / 0.15            # monthly turnover 15%
    adj = true.copy()
    adj[1] *= 1e3                                        # filed x1,000 too large
    adj[2] /= 1e3                                        # x1,000 too small
    out, n_bad = M.unit_filter(adj, V, e0, f)
    assert n_bad == 2 and np.isnan(out[1]) and np.isnan(out[2]) and np.isfinite(out[[0, 3, 4]]).all()
    out2, _ = M.unit_filter(adj, _shock_after(V, f), e0, f)
    assert np.allclose(out, out2, equal_nan=True)


def test_shares_known_uses_only_facts_available_by_the_decision():
    series = [(100.0, "2019-12-31", 1e6), (200.0, "2020-03-31", 2e6)]
    assert M.shares_known(series, 150.0, "2020-04-30") == (1e6, "2019-12-31")
    assert M.shares_known(series, 250.0, "2020-04-30") == (2e6, "2020-03-31")
    assert M.shares_known(series, 50.0, "2020-04-30") is None
    assert M.shares_known(series, 150.0, "2021-12-31") is None        # older than 15 months


def test_legs_2x2_and_book_arithmetic():
    r = np.array([0.10, 0.05, -0.05, -0.10, 0.00])
    to = np.array([0.50, 0.10, 0.40, 0.05, 0.20])
    el = np.ones(5, bool)
    lm, sm = M.legs_2x2(r, to, el, "stmom")
    assert lm.tolist() == [True, False, False, False, False]
    assert sm.tolist() == [False, False, True, False, False]
    sl, ss = M.legs_2x2(r, to, el, "strev")
    assert sl.tolist() == [False, False, True, True, False] and ss.tolist() == [True, True, False, False, False]
    WL = np.array([[1.0, 0, 0], [1.0, 0, 0]])
    WS = np.array([[0, 1.0, 0], [0, 1.0, 0]])
    HR = np.array([[0.02, 0.01, 0.0], [0.0, 0.0, 0.0]])
    bk = M.book(WL, WS, HR, np.array([True, True]), [365, 365], 1e-3, 0.005)
    assert np.allclose(bk["gross"], [0.01, 0.0])
    # entry 2 units, held (no rebalance trade: the single name stays at weight 1), final exit 2 units
    assert np.allclose(bk["turnover"], [2.0, 2.0])
    assert np.allclose(bk["net"], [0.01 - 2e-3 - 0.005, 0.0 - 2e-3 - 0.005])
    # an ineligible month closes the book: its exit is charged to the last eligible month
    bk2 = M.book(WL, WS, HR, np.array([True, False]), [365, 365], 1e-3, 0.0)
    assert np.allclose(bk2["turnover"], [4.0, 0.0]) and bk2["net"][1] == 0.0


# ====================================================================================================== T-698 ==

def test_t698_features_use_no_data_after_the_signal_close():
    D, N = 200, 40
    A, C, O, V = _prices(D, N, seed=1)
    member = np.ones((D, N), bool)
    t = 150
    F = M.t698_features(A, C, O, V, member, 0)
    G = M.t698_features(_shock_after(A, t), _shock_after(C, t), _shock_after(O, t), _shock_after(V, t), member, 0)
    for k in ("r", "av", "avd", "size", "vol"):
        assert np.allclose(F[k][t], G[k][t], equal_nan=True), k
    assert (F["base"][t] == G["base"][t]).all()
    assert np.isfinite(F["av"][t]).all() and np.isfinite(F["size"][t]).all()
    # the dependent return starts at the next open: shocks from t+3 on do not move y(t), the open at t+1 does
    H = M.t698_features(_shock_after(A, t + 2), _shock_after(C, t + 2), _shock_after(O, t + 2), V, member, 0)
    assert np.allclose(F["y"][t], H["y"][t])
    O2 = O.copy()
    O2[t] = O2[t] * 3.0
    assert np.allclose(F["y"][t], M.t698_features(A, C, O2, V, member, 0)["y"][t])
    assert np.allclose(F["y"][t], (O[t + 2] * A[t + 2] / C[t + 2]) / (O[t + 1] * A[t + 1] / C[t + 1]) - 1.0)


def test_fm_day_recovers_a_planted_interaction():
    rng = np.random.default_rng(3)
    n = 300
    r = rng.normal(0, 0.02, n)
    av = rng.normal(0, 0.3, n)
    size = np.exp(rng.normal(17, 1, n))
    vol = rng.uniform(0.01, 0.03, n)
    y = -2.0 * r * av + rng.normal(0, 1e-4, n)
    res = M.fm_day(r, av, size, vol, y, np.ones(n, bool))
    for t in ("bottom", "middle", "top"):
        assert abs(res[t][2] + 2.0) < 0.05


# ====================================================================================================== T-692 ==

def test_iso_weeks_partition_the_calendar():
    days = _sessions(30)
    s0, s1 = M.iso_weeks(days)
    assert s0[0] == 0 and s1[-1] == len(days) - 1 and (s0[1:] == s1[:-1] + 1).all()
    for a, b in zip(s0, s1):
        assert len({date.fromisoformat(days[i]).isocalendar()[:2] for i in range(a, b + 1)}) == 1


def test_weekly_panel_and_flags_use_no_data_after_the_week_close():
    days = _sessions(800)
    D, N = len(days), 60
    A, C, O, V = _prices(D, N, seed=2)
    member = np.ones((D, N), bool)
    s0, s1 = M.iso_weeks(days)
    w = 140
    i = int(s1[w])
    W1 = M.weekly_panel(A, V, member, s0, s1)
    W2 = M.weekly_panel(_shock_after(A, i), _shock_after(V, i), member, s0, s1)
    for k in ("lv", "ret", "raw", "idio", "sig"):
        assert np.allclose(W1[k][:w + 1], W2[k][:w + 1], equal_nan=True), k
    assert np.isfinite(W1["idio"][w]).all() and np.isfinite(W1["sig"][w]).all()
    assert (M.week_flags(W1)[:w + 1] == M.week_flags(W2)[:w + 1]).all()
    assert M.week_flags(W1)[w].sum() >= 1


def test_roll_beta_is_trailing():
    rng = np.random.default_rng(4)
    D, N = 400, 5
    Mr = rng.normal(0, 0.01, D)
    R = 1.5 * Mr[:, None] + rng.normal(0, 0.005, (D, N))
    b = M.roll_beta(R, Mr, 252, 200)
    i = 300
    R2 = R.copy()
    R2[i + 1:] *= -3.0
    M2 = Mr.copy()
    M2[i + 1:] *= 4.0
    b2 = M.roll_beta(R2, M2, 252, 200)
    assert np.allclose(b[:i + 1], b2[:i + 1], equal_nan=True)
    assert np.all(np.abs(b[i] - 1.5) < 0.2) and np.isnan(b[150]).all()


def test_dedupe_keeps_the_first_event_within_the_hold():
    F = np.zeros((6, 1), bool)
    F[[0, 1, 3, 5], 0] = True
    entry = np.array([5, 10, 15, 20, 25, 30])
    out = M.dedupe_events(F, entry, gap=20)
    assert np.flatnonzero(out[:, 0]).tolist() == [0, 5]


def test_block_shift_placebo_detects_a_planted_effect():
    rng = np.random.default_rng(5)
    Wk, N = 400, 30
    E = rng.random((Wk, N)) < 0.03
    Y = rng.normal(0, 0.01, (Wk, N)) + np.where(E, 0.02, 0.0)
    valid = np.ones((Wk, N), bool)
    obs = float(Y[E].mean())
    p = M.block_shift_p(E, Y, valid, obs, n_shift=500)
    assert p["p"] < 0.01
    Y0 = rng.normal(0, 0.01, (Wk, N))
    p0 = M.block_shift_p(E, Y0, valid, float(Y0[E].mean()), n_shift=500)
    assert p0["p"] > 0.01


# ============================================================================================ T-693 / T-694 ==

def _month_bounds(days):
    ms = sorted({d[:7] for d in days})
    first = np.array([min(i for i, d in enumerate(days) if d[:7] == m) for m in ms])
    last = np.array([max(i for i, d in enumerate(days) if d[:7] == m) for m in ms])
    return ms, first, last


def test_aggregate_illiq_uses_no_data_after_the_month_end():
    days = _sessions(900)
    D, N = len(days), 40
    A, C, O, V = _prices(D, N, seed=6)
    member = np.ones((D, N), bool)
    Fs = np.ones((D, N))
    gs = 1000.0 * np.exp(np.cumsum(np.random.default_rng(7).normal(0, 0.01, D)))
    ms, fs, ls = _month_bounds(days)
    L, Lap, cnt = M.aggregate_illiq(A, C, V, member, Fs, gs, fs, ls, 1)
    k = 20
    i = int(ls[k])
    L2, _, _ = M.aggregate_illiq(_shock_after(A, i), _shock_after(C, i), _shock_after(V, i), member, Fs,
                                 _shock_after(gs[:, None], i)[:, 0], fs, ls, 1)
    assert np.allclose(L[:k + 1], L2[:k + 1], equal_nan=True)
    assert np.isfinite(L[2:k + 1]).all() and cnt[k] == N


def test_ar1_expectation_and_one_step_forecasts_are_real_time():
    rng = np.random.default_rng(8)
    n = 120
    L = np.zeros(n)
    for k in range(1, n):
        L[k] = 0.1 + 0.9 * L[k - 1] + rng.normal(0, 0.1)
    X, rho = M.ar1_expectation(L, 0)
    k = 80
    L2 = L.copy()
    L2[k + 1:] += 5.0
    X2, _ = M.ar1_expectation(L2, 0)
    assert np.allclose(X[:k + 1], X2[:k + 1], equal_nan=True) and np.isfinite(X[k])
    y = rng.normal(0, 0.05, n)
    f1 = M.expanding_1step(X, y, 60, 100, 24)
    y2 = y.copy()
    y2[k + 1:] += 1.0                                     # the target of origin k and everything later
    f2 = M.expanding_1step(X, y2, 60, 100, 24)
    i = int(np.flatnonzero(f1["k"] == k)[0])
    assert f1["fm"][i] == f2["fm"][i] and f1["fb"][i] == f2["fb"][i]


def test_detrended_turnover_uses_no_data_after_the_month_end():
    days = _sessions(1700)
    D, N = len(days), 40
    A, C, O, V = _prices(D, N, seed=10)
    member = np.ones((D, N), bool)
    ms, fs, ls = _month_bounds(days)
    S, nS, lv, det = M.detrended_turnover(V, member, fs, ls, hist=60)
    k = 70
    i = int(ls[k])
    S2, *_ = M.detrended_turnover(_shock_after(V, i), member, fs, ls, hist=60)
    assert np.allclose(S[:k + 1], S2[:k + 1], equal_nan=True)
    assert np.isfinite(S[k]) and np.isnan(S[59])
    k0 = 61
    assert np.allclose(det[k0, 3], lv[k0, 3] - lv[k0 - 60:k0, 3].mean())


def test_expanding_h_trains_only_on_realised_targets():
    rng = np.random.default_rng(11)
    n, h = 200, 12
    x = rng.normal(0, 1, n)
    y = rng.normal(0, 1, n)
    f1 = M.expanding_h(x, y, 100, 150, h, 36)
    k = 120
    y2 = y.copy()
    y2[k - h + 1:k] += 10.0                               # targets not yet realised at origin k
    f2 = M.expanding_h(x, y2, 100, 150, h, 36)
    i = int(np.flatnonzero(f1["k"] == k)[0])
    assert f1["fm"][i] == f2["fm"][i] and f1["fb"][i] == f2["fb"][i]


def test_window_sums_and_hodrick_slope_sign():
    rng = np.random.default_rng(12)
    n = 400
    S = rng.normal(0, 1, n)
    g = rng.normal(0, 0.02, n)
    g[1:] += -0.01 * S[:-1]                               # the signal predicts the next month negatively
    y = M.window_sums(g, 12)
    assert np.isclose(y[10], g[11:23].sum()) and np.isnan(y[n - 5])
    hs = M.hod_slope(S, y, g, np.arange(0, n - 12))
    assert hs["slope"] < 0 and hs["p"] < 0.05
