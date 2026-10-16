"""Batch-6c pairs harnesses (T-321 GGR distance pairs, T-322 Engle-Granger persistence, T-323 Kalman versus static hedge,
T-468 Brent-WTI spread on USO/BNO, T-470 dual-class spreads) on synthetic data only: for every core function a planted
effect passes and a null does not; the MacKinnon tables, the batched ADF, both spread simulators (fills, costs, borrow,
rebalancing), the roll calendars and the EM are checked directly; every harness runs on a fake archive (JSON-safe,
missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_pairs as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 200)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "REPS_MAX", 2)
    monkeypatch.setattr(m, "N_RANDOM", 200)
    monkeypatch.setattr(m, "T323_EM_ITERS", 6)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _yahoo(days, close, adj=None, vol=None, hour="14:30"):
    adj = close if adj is None else adj
    vol = np.full(len(days), 1e6) if vol is None else vol
    return [{"available_at": (date.fromisoformat(d) + timedelta(days=1)).isoformat() + f"T{hour}:00+00:00",
             "value": {"t": datetime.fromisoformat(f"{d}T{hour}:00+00:00").timestamp(), "close": float(c), "adjclose": float(a),
                       "volume": float(v)}}
            for d, c, a, v in zip(days, close, adj, vol)]


def wdays(first, last):
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cdays(first, last):
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _rw(rng, n, sd=0.01, p0=100.0):
    return p0 * np.exp(np.cumsum(rng.normal(0.0, sd, n)))


def _ou(rng, n, phi, sd):
    u = np.zeros(n)
    e = rng.normal(0.0, sd, n)
    for t in range(1, n):
        u[t] = phi * u[t - 1] + e[t]
    return u


def _json_ok(out):
    stat, n, verdict, reason = out
    json.dumps(stat)
    assert isinstance(n, int)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert " — " in reason
    return stat, n, verdict, reason


# ---------------------------------------------------------------------------------------------- MacKinnon, ADF --

def test_mackinnon_tables_hit_their_levels():
    for N in (1, 2):
        for lv in (0.01, 0.05, 0.10):
            tau_inf = m.MK2010_C[N][lv][0]
            assert abs(float(m.mackinnon_p(tau_inf, N)) - lv) < 0.002
    assert abs(float(m.mackinnon_crit(2, 0.05, 250)) - (-3.33613 - 6.1101 / 250 - 6.823 / 250 ** 2)) < 1e-12
    assert float(m.mackinnon_p(5.0, 1)) == 1.0 and float(m.mackinnon_p(-30.0, 2)) == 0.0


def test_adf_batch_matches_ols_and_separates_stationary_from_unit_root():
    rng = np.random.default_rng(1)
    T = 250
    rw = np.cumsum(rng.standard_normal((T, 20)), axis=0)
    ar = np.zeros((T, 20))
    for t in range(1, T):
        ar[t] = 0.6 * ar[t - 1] + rng.standard_normal(20)
    r_rw, r_ar = m.adf_batch(rw, "c"), m.adf_batch(ar, "c")
    crit = m.mackinnon_crit(1, 0.05, 249)
    assert (r_ar["tau"] < crit).mean() > 0.9           # planted: stationary series reject
    assert (r_rw["tau"] < crit).mean() < 0.3           # null: unit roots mostly do not
    k = 3
    p = int(r_ar["lag"][k])
    e, de = ar[:, k], np.diff(ar[:, k])
    n = T - 1 - p
    Z = np.column_stack([e[p:T - 1], np.ones(n)] + [de[p - i:T - 1 - i] for i in range(1, p + 1)])
    y = de[p:]
    coef = np.linalg.lstsq(Z, y, rcond=None)[0]
    s2 = ((y - Z @ coef) ** 2).sum() / (n - Z.shape[1])
    tau = coef[0] / math.sqrt(s2 * np.linalg.inv(Z.T @ Z)[0, 0])
    assert abs(tau - r_ar["tau"][k]) < 1e-8
    assert r_ar["nobs"][k] == n


def test_half_life_and_ols_cols():
    rng = np.random.default_rng(2)
    u = _ou(rng, 4000, 0.8, 1.0)
    assert abs(float(m.half_life(u[:, None])[0]) - math.log(2) / -math.log(0.8)) < 0.5
    assert np.isinf(m.half_life(np.cumsum(np.ones(50))[:, None] ** 2)[0]) or m.half_life(np.cumsum(np.ones(50))[:, None] ** 2)[0] > 30
    x = rng.normal(size=(300, 2))
    y = 0.3 + 1.7 * x + rng.normal(0, 0.01, (300, 2))
    a, b, e = m.ols_cols(y, x)
    assert np.allclose(b, 1.7, atol=0.01) and np.allclose(a, 0.3, atol=0.01) and abs(e.mean()) < 1e-12


# ---------------------------------------------------------------------------------------------- spread simulator --

def test_spread_sim_hand_example_wait_costs_and_borrow():
    z = np.array([[0.0, 2.5, 1.0, -0.1, 0.0, 0.0]])
    rA = np.array([[0.0, 0.01, 0.02, -0.01, 0.03, 0.0]])
    rB = np.array([[0.0, 0.00, 0.01, 0.02, -0.02, 0.0]])
    V = np.ones((1, 6), bool)
    dt = np.ones((1, 6))
    c, bw = 0.001, 0.0365                                 # borrow 1 bp a day on the short leg
    r = m.spread_sim(z, 1.0, rA, rB, V, 2.0, 0.0, np.inf, c, c, bw, dt, wait=1)
    # decision at close 1 (z > 2: short A / long B), fill at close 2; exit decided at close 3 (z <= 0), filled at close 4
    A, B = -1.0, 1.0
    exp = np.zeros(6)
    exp[2] = -2 * c
    exp[3] = A * rA[0, 3] + B * rB[0, 3] - bw * 1.0 / 365
    A3, B3 = A * (1 + rA[0, 3]), B * (1 + rB[0, 3])
    exp[4] = A3 * rA[0, 4] + B3 * rB[0, 4] - bw * abs(A3) / 365
    A4, B4 = A3 * (1 + rA[0, 4]), B3 * (1 + rB[0, 4])
    exp[4] -= c * (abs(A4) + abs(B4))
    assert np.allclose(r["pnl"][0], exp, atol=1e-12)
    assert r["n_open"][0] == 1 and r["days_in"][0] == 2
    # immediate execution fills the same closes: open at close 1, close at close 3
    r0 = m.spread_sim(z, 1.0, rA, rB, V, 2.0, 0.0, np.inf, c, c, 0.0, dt, wait=0)
    assert r0["pnl"][0, 1] == pytest.approx(-2 * c) and r0["pnl"][0, 4] == 0.0 and r0["pnl"][0, 3] != 0.0


def test_spread_sim_no_open_on_last_close_forced_close_and_rebalance():
    V = np.ones((1, 4), bool)
    z = np.array([[0.0, 0.0, 3.0, 3.0]])
    r = m.spread_sim(z, 1.0, np.zeros((1, 4)), np.zeros((1, 4)), V, 2.0, 0.0, cost_a=0.01, cost_b=0.01)
    assert r["n_open"][0] == 0 and np.all(r["pnl"] == 0)     # signal at close 2 would fill at the last close: skipped
    z = np.array([[-2.5, -1.0, -1.0, -1.0, -1.0, -1.0]])
    beta = np.array([[1.0, 1.0, 1.2, 1.2, 1.2, 1.2]])
    rr = m.spread_sim(z, beta, np.zeros((1, 6)), np.zeros((1, 6)), np.ones((1, 6), bool), 2.0, 0.0, cost_a=0.0, cost_b=0.001,
                      rebalance=0.05)
    assert rr["n_open"][0] == 1 and rr["n_rebalance"][0] == 1
    # open (A +1, B -1: 0.1% on B), rebalance B to -1.2 at close 3 (0.02% on 0.2), forced close at the last (0.12%)
    assert rr["pnl"][0].sum() == pytest.approx(-(0.001 * 1.0 + 0.001 * 0.2 + 0.001 * 1.2))


def _ou_rows(rng, N, T, phi):
    lb = np.cumsum(rng.normal(0, 0.01, (N, T)), axis=1)
    s = np.vstack([_ou(rng, T, phi, 0.01) for _ in range(N)])
    la = lb + s
    PA, PB = np.exp(la), np.exp(lb)
    rA = np.c_[np.zeros(N), PA[:, 1:] / PA[:, :-1] - 1]
    rB = np.c_[np.zeros(N), PB[:, 1:] / PB[:, :-1] - 1]
    F = 60                                   # frozen "formation" mean and sd from the first 60 columns, trading after
    z = (s - s[:, :F].mean(axis=1, keepdims=True)) / s[:, :F].std(axis=1, ddof=1, keepdims=True)
    return z, rA, rB


def test_spread_sim_planted_reversion_earns_and_random_walk_does_not():
    rng = np.random.default_rng(3)
    N, T = 150, 310
    V = np.zeros((N, T), bool)
    V[:, 60:] = True
    z, rA, rB = _ou_rows(rng, N, T, 0.8)
    pl = m.spread_sim(z, 1.0, rA, rB, V, 2.0, 0.0, cost_a=0.002, cost_b=0.002)["pnl"].sum(axis=1)
    z0, rA0, rB0 = _ou_rows(rng, N, T, 1.0)
    nu = m.spread_sim(z0, 1.0, rA0, rB0, V, 2.0, 0.0, cost_a=0.002, cost_b=0.002)["pnl"].sum(axis=1)
    assert pl.mean() > 0.02
    assert nu.mean() < 0.0


# ---------------------------------------------------------------------------------------------- T-321 GGR --

def _ggr_panel(rng, planted: bool, n_twin=20, n_free=4, first="2000-01-03", last="2005-12-30"):
    days = wdays(first, last)
    n = len(days)
    cols, names, cls = [], [], []
    for i in range(n_twin):
        f = np.cumsum(rng.normal(0, 0.01, n))
        for j in range(2):
            u = _ou(rng, n, 0.85, 0.012) if planted else np.cumsum(rng.normal(0, 0.01, n))
            cols.append(100 * np.exp(f + u))
            names.append(f"T{i}{'ab'[j]}")
            cls.append(f"c{i % 3}")
    for i in range(n_free):
        cols.append(_rw(rng, n))
        names.append(f"F{i}")
        cls.append(f"c{i % 3}")
    return days, np.column_stack(cols), names, cls


def test_ggr_planted_twins_pass_and_independent_walks_do_not():
    rng = np.random.default_rng(4)
    days, P, names, cls = _ggr_panel(rng, True)
    res = m.ggr_run(days, P, names, cls, first="2001-01", end="2005-12-31", n_random=200)
    j = m.ggr_judge(res, min_n=24)
    assert j["n"] >= 50 and j["mean"] > 0
    assert j["mean"] > j["q95_random"]
    assert j["verdict"] == "supported", j["why"]
    days, P, names, cls = _ggr_panel(rng, False)
    res0 = m.ggr_run(days, P, names, cls, first="2001-01", end="2005-12-31", n_random=200)
    j0 = m.ggr_judge(res0, min_n=24)
    assert j0["verdict"] != "supported"
    assert res0["count_min"] >= 1 and len(res0["cells"]) == len(m.T321_CELLS)


def test_ggr_formation_ssd_and_selection():
    rng = np.random.default_rng(5)
    Nf = 1 + np.cumsum(rng.normal(0, 0.01, (100, 6)), axis=0)
    Nf[:, 1] = Nf[:, 0] + rng.normal(0, 0.001, 100)          # a near twin
    I, J, ssd, sd = m.ggr_formation(Nf)
    k = int(np.argmin(ssd))
    assert (I[k], J[k]) == (0, 1)
    assert ssd[k] == pytest.approx(((Nf[:, 0] - Nf[:, 1]) ** 2).sum())
    assert sd[k] == pytest.approx((Nf[:, 0] - Nf[:, 1]).std(ddof=1))
    sel = m.ggr_select(I, J, ssd, sd, Nf, ["a", "a", "b", "b", "c", "c"], top=3)
    assert sel["top20"][0] == k and len(sel["top5"]) == 5
    assert all(["a", "a", "b", "b", "c", "c"][I[i]] == ["a", "a", "b", "b", "c", "c"][J[i]] for i in sel["class"])


# ---------------------------------------------------------------------------------------------- T-322 persistence --

def _coint_panel(rng, planted: bool, n_clusters=3, size=4, first="2000-01-03", last="2006-12-29"):
    """Planted: clusters of funds sharing one random walk plus small stationary noise, so every within-cluster pair is
    cointegrated (the noise is small next to the walk's daily moves: random walk plus large noise makes ADF over-reject,
    Schwert 1989). Null: independent random walks."""
    days = wdays(first, last)
    n = len(days)
    cols = []
    for c in range(n_clusters):
        f = np.cumsum(rng.normal(0, 0.02, n))
        for k in range(size):
            u = _ou(rng, n, 0.8, 0.006) if planted else np.cumsum(rng.normal(0, 0.02, n))
            cols.append(100 * np.exp((f if planted else 0.0) + u))
    return days, np.column_stack(cols)


def test_persistence_planted_pairs_pass_and_random_walks_do_not():
    rng = np.random.default_rng(6)
    days, P = _coint_panel(rng, True)
    sc = m.coint_scan(days, P, first="2001-01", end="2006-12-31")
    j = m.persistence_judge(sc, min_n=50, n_random=200)
    assert j["share"] > 0.6 and j["share"] > j["random_share"] + 0.25
    assert j["verdict"] == "supported", j["why"]
    days, P = _coint_panel(rng, False)
    sc0 = m.coint_scan(days, P, first="2001-01", end="2006-12-31")
    j0 = m.persistence_judge(sc0, min_n=50, n_random=200)
    assert j0["verdict"] != "supported"
    assert j0["share"] is None or j0["share"] < 0.4


def test_coint_scan_includes_crypto_candidate_on_its_calendar():
    rng = np.random.default_rng(7)
    days, P = _coint_panel(rng, True, n_clusters=1, size=4, first="2000-01-03", last="2002-12-31")
    cd = cdays("2000-01-01", "2002-12-31")
    lb = np.cumsum(rng.normal(0, 0.02, len(cd)))
    C = np.column_stack([100 * np.exp(lb + _ou(rng, len(cd), 0.8, 0.02)), 100 * np.exp(lb)])
    sc = m.coint_scan(days, P, cd, C, first="2001-01", end="2002-12-31")
    assert all(w["K"] == 6 + 1 for w in sc["windows"])
    assert sum(w["crypto_sel"] for w in sc["windows"]) > 0
    fr = m.pw_frame(sc, sc["rows"]["sel"].astype(bool), "crypto", cd, C, days)
    assert fr is not None and fr["ppy"] == 365 and fr["cost"] == 0.004
    assert fr["Vf"].sum(axis=1).min() >= 365                    # a crypto formation is a calendar year
    assert np.all(np.diff(fr["DI"], axis=1) >= 0)


# ---------------------------------------------------------------------------------------------- T-323 Kalman --

def test_kalman_em_tracks_a_drifting_beta_and_stays_flat_on_a_constant_one():
    rng = np.random.default_rng(8)
    N, T = 60, 252
    X = 4.0 + np.cumsum(rng.normal(0, 0.012, (N, T)), axis=1)        # log prices of a ~$55 fund
    beta = 1.0 + np.cumsum(rng.normal(0, 0.003, (N, T)), axis=1)
    Y = 0.01 + beta * X + rng.normal(0, 0.002, (N, T))
    V = np.ones((N, T), bool)
    em = m.kalman_em(Y, X, V, n_iter=30)
    kp = m.kalman_pass(Y, X, V, em["w"], em["R"], em["m0"])
    err_k = np.abs(kp["beta"][:, 60:] - beta[:, 60:]).mean()
    err_s = np.abs(em["m0"][:, 1:2] - beta[:, 60:]).mean()
    assert err_k < 0.5 * err_s                                      # planted: the filter tracks the drift
    Y0 = 0.01 + 1.0 * X + rng.normal(0, 0.002, (N, T))
    em0 = m.kalman_em(Y0, X, V, n_iter=30)
    assert np.median(em0["delta"]) < 0.1 * np.median(em["delta"])  # null: the state noise collapses
    kp0 = m.kalman_pass(Y0, X, V, em0["w"], em0["R"], em0["m0"])
    assert np.abs(kp0["beta"][:, 60:] - 1.0).mean() < 0.02


def test_kalman_em_likelihood_does_not_fall():
    rng = np.random.default_rng(9)
    T = 200
    X = np.cumsum(rng.normal(0, 0.01, (1, T)), axis=1)
    Y = (1 + np.cumsum(rng.normal(0, 0.01, (1, T)), axis=1)) * X + rng.normal(0, 0.003, (1, T))
    V = np.ones((1, T), bool)

    def ll(em):
        kp = m.kalman_pass(Y, X, V, em["w"], em["R"], em["m0"])
        e, q = kp["e"][0], kp["Q"][0]
        return float(-0.5 * np.sum(np.log(2 * np.pi * q) + e * e / q))
    lls = [ll(m.kalman_em(Y, X, V, n_iter=k)) for k in (1, 3, 10, 30)]
    assert all(b >= a - 1e-6 for a, b in zip(lls, lls[1:]))


def _judge_inputs(rng, planted: bool):
    labels = [f"{y}-{mo:02d}" for y in range(2014, 2021) for mo in range(1, 13)]
    wins = [(k, labels[k]) for k in range(12, 78)]
    kk = np.repeat([k for k, _ in wins], 12)
    d = rng.normal(0.6 if planted else 0.0, 1.0, kk.size)
    dcell = {c: d + (0 if c == m.T323_PRIMARY else rng.normal(0, 0.2, kk.size)) for c in m.T323_KCELLS}
    series = {}
    for hn, _ in m.T323_HALVES:
        xs = rng.normal(0.0, 0.01, 800)
        xk = rng.normal(0.0015 if planted else 0.0, 0.01, 800)
        series[hn] = (xk, xs)
    fam = {c: rng.normal(0.003 if planted else 0.0, 0.01, 1600) for c in m.T323_KCELLS}
    return kk, dcell, labels, wins, series, fam


def test_kalman_judge_planted_passes_null_does_not():
    rng = np.random.default_rng(10)
    j = m.kalman_judge(*_judge_inputs(rng, True), min_n=50)
    assert j["verdict"] == "supported", j["why"]
    assert all(h["mean"] > 0 for h in j["halves"].values())
    j0 = m.kalman_judge(*_judge_inputs(rng, False), min_n=50)
    assert j0["verdict"] != "supported"


def test_kalman_study_end_to_end_runs_on_selected_pair_windows():
    rng = np.random.default_rng(11)
    days, P = _coint_panel(rng, True, n_clusters=2, size=3, first="2000-01-03", last="2002-12-31")
    sc = m.coint_scan(days, P, first="2001-01", end="2002-12-31")
    fr = m.pw_frame(sc, sc["rows"]["sel"].astype(bool), "etf", days, P, days)
    assert fr is not None
    sm = m.static_sim(fr, (2.0, 0.5, 4.0))
    assert sm["n_open"].sum() > 0 and np.isfinite(sm["pnl"]).all()
    j = m.kalman_study(sc, [fr], len(days), min_n=10, em_iters=3)
    assert j["verdict"] in ("supported", "not_supported", "inconclusive")
    assert len(j["criteria"]) == 3 and j["n_pair_windows"] == fr["k"].size


# ---------------------------------------------------------------------------------------------- per-trade rule --

def test_trade_rule_fills_next_close_time_stop_and_costs():
    days = wdays("2020-01-01", "2020-01-31")
    n = len(days)
    z = np.full(n, 0.5)
    z[2] = 2.5                                   # decided at close 2 -> short A / long B filled at close 3
    rA = np.full(n, 0.001)
    rB = np.zeros(n)
    r = m.trade_rule(days, z, rA, rB, 2.0, 0.0, 4, 0.0005, 0.0005, 0.0, "", "2020-12-31")
    t = r["trades"][0]
    assert t["entry"] == days[3] and t["exit"] == days[7] and t["reason"] == "time stop" and t["days_held"] == 4
    exp = -0.001 - 0.001 * sum(1.001 ** k for k in range(4)) - 0.0005 * (1.001 ** 4 + 1.0)
    assert t["pnl"] == pytest.approx(exp, abs=1e-12)
    z2 = np.full(n, -1.0)
    z2[2], z2[4] = -2.5, 0.1                     # long A / short B at close 3; z crosses 0 at close 4 -> exit at close 5
    r2 = m.trade_rule(days, z2, rA, rB, 2.0, 0.0, 20, 0.0, 0.0, 0.0365, "", "2020-12-31")
    t2 = r2["trades"][0]
    assert days[3:6] == ["2020-01-06", "2020-01-07", "2020-01-08"]
    assert t2["exit"] == days[5] and t2["reason"] == "z exit"
    assert t2["pnl"] == pytest.approx((1.001 ** 2 - 1) - 0.0365 / 365 * 2, abs=1e-12)
    r3 = m.trade_rule(days, z, rA, rB, 2.0, 0.0, 4, 0.0, 0.0, 0.0, days[3], "2020-12-31")
    assert r3["trades"] == []                    # the only signal is dated before ``start``


def test_trailing_z_masked_uses_only_unmasked_values():
    rng = np.random.default_rng(12)
    s = rng.normal(size=400)
    ok = np.ones(400, bool)
    ok[::3] = False
    z = m.trailing_z_masked(s, ok, 50, 10)
    t = 300
    w = s[t - 49:t + 1][ok[t - 49:t + 1]]
    if ok[t]:
        assert z[t] == pytest.approx((s[t] - w.mean()) / w.std(ddof=1))
    assert np.all(np.isnan(z[~ok]))


# ---------------------------------------------------------------------------------------------- T-468 Brent-WTI --

def test_roll_calendars():
    assert m.cl_last_trade(2024, 3) == date(2024, 2, 20)       # 25 Feb 2024 is a Sunday: 4 business days before
    assert m.cl_last_trade(2023, 11) == date(2023, 10, 20)     # 25 Oct 2023 is a Wednesday: 3 business days before
    assert m.bz_last_trade(2016, 3) == date(2016, 1, 29)       # new rule: last business day of the second prior month
    assert m.bz_last_trade(2016, 2) == date(2016, 1, 14)       # old rule: day before the 15th day before 1 Feb
    days = wdays("2018-01-01", "2018-12-31")
    ms, md = m.roll_mask(days, 5, "sessions"), m.roll_mask(days, 5, "days")
    assert 0.6 < ms.mean() < 0.9 and 0.4 < md.mean() < ms.mean()


def _oil(rng, planted: bool, first="1988-01-01", last="2026-10-14"):
    days = wdays(first, last)
    n = len(days)
    cl = 60 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    s = _ou(rng, n, 0.93, 0.012) if planted else np.cumsum(rng.normal(0, 0.012, n))
    bz = cl * np.exp(0.05 + s)
    uso, bno = cl * 0.5, bz * 0.4
    return days, cl, bz, uso, bno


def test_brent_wti_planted_reversion_passes_random_walk_does_not():
    # the +-5-session roll mask leaves about a fifth of the sessions, so the synthetic history trades from 1990 to reach
    # min_n under both readings; the sub-periods are the claim's own
    rng = np.random.default_rng(13)
    days, cl, bz, uso, bno = _oil(rng, True)
    j = m.brent_wti({"BZ": (days, bz), "CL": (days, cl)}, {"USO": (days, uso), "BNO": (days, bno)}, (days, uso * 1.01),
                    start="1990-01-01")
    assert all(R["n"] >= 20 and R["mean"] > 0 and R["p_null"] < 0.05 for R in j["readings"].values())
    assert j["verdict"] == "supported", j["why"]
    days, cl, bz, uso, bno = _oil(rng, False)
    j0 = m.brent_wti({"BZ": (days, bz), "CL": (days, cl)}, {"USO": (days, uso), "BNO": (days, bno)}, start="1990-01-01")
    assert j0["verdict"] != "supported"


# ---------------------------------------------------------------------------------------------- T-470 dual class --

def _dual_data(rng, planted: bool, drop=(), first="2013-01-02", last="2021-12-31"):
    days = wdays(first, last)
    n = len(days)
    data = {}
    for A, B, k, _ in m.T470_PAIRS:
        if A in drop or B in drop:
            continue
        pb = _rw(rng, n, 0.015, 50.0)
        x = _ou(rng, n, 0.7, 0.01) if planted else np.cumsum(rng.normal(0, 0.003, n))
        pa = k * pb * np.exp(x)
        for t, p in ((A, pa), (B, pb)):
            data[t] = {"days": days, "adj": p, "close": p, "vol": rng.uniform(1e5, 1e6, n)}
    return data


def test_dual_class_planted_passes_null_and_missing_pair_do_not():
    rng = np.random.default_rng(14)
    j = m.dual_class(_dual_data(rng, True), min_n=200, end="2021-12-31")
    assert j["n"] >= 200
    assert j["verdict"] == "supported", j["why"]
    j0 = m.dual_class(_dual_data(rng, False), min_n=200, end="2021-12-31")
    assert j0["verdict"] != "supported"
    jm = m.dual_class(_dual_data(rng, True, drop=("LBRDK",)), min_n=200, end="2021-12-31")
    assert jm["missing"] == ["LBRDK/LBRDA"] and jm["verdict"] == "inconclusive"
    assert jm["criteria"][0][1] is None and jm["criteria"][2][1] is None and jm["criteria"][1][1] is True


def test_dual_class_thin_cost_reading_must_agree():
    rng = np.random.default_rng(15)
    data = _dual_data(rng, True)
    j = m.dual_class(data, min_n=200, end="2021-12-31")
    a = j["pooled"]["claim: 5 bps per leg"]["mean"]
    b = j["pooled"]["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]["mean"]
    assert b < a                                                     # thin legs cost more
    bf = j["per_pair"]["BF-B/BF-A"]
    assert bf["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]["mean"] < bf["claim: 5 bps per leg"]["mean"]
    g = j["per_pair"]["GOOGL/GOOG"]
    assert g["controls: 25 bps on BF-A/LEN-B/HEI-A legs"]["mean"] == g["claim: 5 bps per leg"]["mean"]


# ---------------------------------------------------------------------------------------------- harnesses --

@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_harness_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = _json_ok(m.HARNESSES[name](FakeArchive({})))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]


def test_maps_are_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-321", "T-322", "T-323", "T-468", "T-470"}
    assert all(k.startswith("b6c_pairs_") and k == k.lower() for k in m.HARNESSES)
    assert len(m.UNIVERSE) == 51 and len(set(m.UNIVERSE)) == 51 and set(m.ASSET_CLASS) == set(m.UNIVERSE)


def _etf_archive(rng, first="2006-11-01", last="2008-09-30"):
    days = wdays(first, last)
    n = len(days)
    b = {}
    f = np.cumsum(rng.normal(0, 0.01, n))
    for i, s in enumerate(m.UNIVERSE):
        p = 50 * np.exp(f + (_ou(rng, n, 0.9, 0.01) if i % 2 else np.cumsum(rng.normal(0, 0.008, n))))
        b[m.dh(s)] = _yahoo(days, p)
    cd = cdays(first, last)
    lb = np.cumsum(rng.normal(0, 0.03, len(cd)))
    b[m.dh("BTC-USD")] = _yahoo(cd, 1000 * np.exp(lb), hour="00:00")
    b[m.dh("ETH-USD")] = _yahoo(cd, 50 * np.exp(lb + _ou(rng, len(cd), 0.9, 0.02)), hour="00:00")
    return b


def test_etf_harnesses_run_on_a_fake_archive():
    rng = np.random.default_rng(16)
    arc = FakeArchive(_etf_archive(rng))
    for name in ("b6c_pairs_distance", "b6c_pairs_cointegration", "b6c_pairs_kalman"):
        stat, n, verdict, reason = _json_ok(m.HARNESSES[name](arc))
        assert stat.get("criteria")


def test_oil_and_dual_class_harnesses_run_on_a_fake_archive():
    rng = np.random.default_rng(17)
    days, cl, bz, uso, bno = _oil(rng, True, first="2009-01-01", last="2014-12-31")

    arc = FakeArchive({m.dh("BZ=F"): _yahoo(days, bz, hour="04:00"), m.dh("CL=F"): _yahoo(days, cl, hour="04:00"),
                       m.dh("USO"): _yahoo(days, uso), m.dh("BNO"): _yahoo(days, bno), m.dh("UGA"): _yahoo(days, uso * 0.9)})
    stat, n, verdict, reason = _json_ok(m.b6c_pairs_brent_wti(arc))
    assert set(stat["readings"]) == {"+-5 sessions", "+-5 calendar days"}
    data = _dual_data(rng, True, drop=("LBRDK", "LBRDA"))
    arc2 = FakeArchive({m.dh(t): _yahoo(d["days"], d["close"], d["adj"], d["vol"]) for t, d in data.items()})
    stat, n, verdict, reason = _json_ok(m.b6c_pairs_dual_class(arc2))
    assert verdict == "inconclusive" and stat["missing_pairs"] == ["LBRDK/LBRDA"] and "LBRDK" in reason
