"""Tests for mandel.experiments.batch13_crossasset_a: point-in-time signal construction (shocks after the decision
never move the signal at the decision) and inconclusive verdicts when bundles are missing."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch13_crossasset_a as M


class _NoBundles:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


def _weekdays(start: str, n: int) -> list:
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------------------------------------- missing data --

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_NoBundles())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_matches_harnesses():
    assert set(M.THEORY_MAP) == {"T-603", "T-605", "T-598", "T-600", "T-596"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


# ------------------------------------------------------------------------------------------------------- T-605 --

def _rates(months, rng):
    return {c: {m: float(rng.normal(2, 1)) for m in months} for c in ("USD",) + M.T605_G10}


def test_t605_afd_uses_previous_month_only():
    rng = np.random.default_rng(1)
    months = M.mrange("2015-01", "2015-12")
    rates = _rates(months, rng)
    dm = "2015-06"
    base = M.afd_at(rates, M.T605_G10, dm)
    exp = np.mean([rates[c]["2015-05"] for c in M.T605_G10]) - rates["USD"]["2015-05"]
    assert base == pytest.approx(exp)
    shocked = {c: dict(v) for c, v in rates.items()}
    for v in shocked.values():
        for m in months:
            if m >= dm:                      # the decision month's own average and later are not known at its end
                v[m] += 50.0
    assert M.afd_at(shocked, M.T605_G10, dm) == pytest.approx(base)


def _fx_panel(days, rng, rates):
    daily = {c: (list(days), np.exp(np.cumsum(rng.normal(0, 0.005, len(days))))) for c in M.T605_G10}
    return {"daily": daily, "rates": rates, "filled": {}}


def test_t605_sign_ignores_spot_and_later_rates():
    rng = np.random.default_rng(2)
    days = _weekdays("2014-01-01", 600)
    months = M.mrange("2013-10", "2016-06")
    rates = _rates(months, rng)
    p = _fx_panel(days, rng, rates)
    b0 = M.t605_book(p, M.T605_G10, "2014-03", "2015-12")
    p2 = _fx_panel(days, np.random.default_rng(99), {c: dict(v) for c, v in rates.items()})   # different spot path
    H = "2015-01"
    for c in p2["rates"]:
        for m in months:
            if m >= M.madd(H, -1):
                p2["rates"][c][m] -= 30.0
    b1 = M.t605_book(p2, M.T605_G10, "2014-03", "2015-12")
    s0 = {r["H"]: r["sign"] for r in b0["rows"]}
    s1 = {r["H"]: r["sign"] for r in b1["rows"]}
    assert s0[H] == s1[H]
    fills = {r["H"]: r["fill"] for r in b0["rows"]}
    assert fills[H][:7] == H                 # filled in the holding month, after the decision month ends


def test_t605_spell_shuffle_keeps_spells():
    s = np.array([1, 1, 1, -1, -1, 1, -1, -1, -1, -1], float)
    paths = M.spell_shuffle(s, 50, np.random.default_rng(0))
    assert paths.shape == (50, s.size)
    assert np.all(paths.sum(axis=1) == s.sum())
    assert np.all(np.sort(paths, axis=1) == np.sort(s))


def test_t605_costs_charge_flips():
    rows = [{"H": f"2020-{k + 1:02d}", "afd": 1.0, "sign": sg, "r": np.zeros(9)} for k, sg in enumerate([1, 1, -1, -1])]
    R = M.t605_returns(rows)
    cost = R["gross"] - R["net"]
    assert cost[0] == pytest.approx(M.T605_LEG + M.T605_ROLL)
    assert cost[1] == pytest.approx(M.T605_LEG + M.T605_ROLL)
    assert cost[2] == pytest.approx(2 * M.T605_LEG + M.T605_ROLL)
    assert cost[3] == pytest.approx(2 * M.T605_LEG + M.T605_ROLL)          # the final close


# ------------------------------------------------------------------------------------------------ T-598 / T-600 --

def test_oil_month_unaffected_by_later_prices():
    rng = np.random.default_rng(3)
    days = _weekdays("2010-01-01", 400)
    c = 70 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    mask = M.cl_roll_mask(days, 5, "sessions")
    x0 = M.oil_monthly(days, c, mask)
    t = "2010-06"
    last = max(i for i, d in enumerate(days) if d[:7] == t)
    c2 = c.copy()
    c2[last + 1:] *= 3.0
    c2[last + 5] = -10.0                      # a negative print after the decision
    x1 = M.oil_monthly(days, c2, mask)
    assert x1[t] == pytest.approx(x0[t])
    assert M.madd(t, 1) in x1


def test_log_changes_never_bridge_nonpositive_print():
    c = np.array([10.0, 11.0, -5.0, 12.0, 13.0])
    ch = M.log_changes(c)
    assert np.isnan(ch[2]) and np.isnan(ch[3])
    assert ch[1] == pytest.approx(np.log(1.1))


def test_cl_roll_mask_is_scheduled():
    days = _weekdays("2015-01-01", 300)
    m1 = M.cl_roll_mask(days, 5, "sessions")
    assert 0.3 < m1.mean() < 0.7
    assert np.array_equal(m1[:200], M.cl_roll_mask(days[:200], 5, "sessions"))


def test_expanding_forecast_ignores_unrealised_pairs():
    rng = np.random.default_rng(4)
    n = 120
    x = rng.normal(size=n)
    y = 0.3 * x + rng.normal(size=n)
    k = 80
    r0 = M.expanding_oos(x, y, k, k)
    y2, x2 = y.copy(), x.copy()
    y2[k - 1:] += 100.0                      # pair k-1 ends after the decision at k; pair k is the target
    x2[k + 1:] -= 100.0
    r1 = M.expanding_oos(x2, y2, k, k)
    assert r0["fm"][0] == pytest.approx(r1["fm"][0])
    assert r0["fb"][0] == pytest.approx(r1["fb"][0])


def test_spy_target_starts_after_month_end():
    days = _weekdays("2012-01-02", 120)
    adj = np.linspace(100, 120, len(days))

    class _B:
        def growth(self, a, b):
            return 0.0
    tg = M.spy_targets(days, adj, _B(), ["2012-02"])
    _y, d0, d1 = tg["2012-02"]
    assert d0[:7] == "2012-03" and d1[:7] == "2012-04"


def test_gp_change_unaffected_by_later_prices():
    rng = np.random.default_rng(5)
    days = _weekdays("2005-01-03", 500)
    g = 400 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    p = 800 * np.exp(np.cumsum(rng.normal(0, 0.012, len(days))))
    gm = M.MISC.roll_flags(days, M.T600_GC_MONTHS, 2)
    pm = M.MISC.roll_flags(days, M.T600_PL_MONTHS, 2)
    x0 = M.delta(M.gp_monthly(days, g, days, p, gm, pm))
    t = "2005-04"                             # 2005-05-02 lies outside every GC / PL roll window
    last = max(i for i, d in enumerate(days) if d[:7] == t)
    assert not gm[last + 1] and not pm[last + 1]
    g2, p2 = g.copy(), p.copy()
    g2[last + 1:] *= 2.0
    p2[last + 1:] *= 0.5
    x1 = M.delta(M.gp_monthly(days, g2, days, p2, gm, pm))
    assert x1[t] == pytest.approx(x0[t])
    assert abs(x1[M.madd(t, 1)] - x0[M.madd(t, 1)]) > 0.1


def test_switching_rule_costs():
    y = np.array([0.01, 0.02, -0.01, 0.03])
    f = np.array([1.0, 1.0, -1.0, 1.0])
    r = M.switching(y, f, 2e-4)
    assert r == pytest.approx([0.01 - 2e-4, 0.02, -2e-4, 0.03 - 2e-4])


# ------------------------------------------------------------------------------------------------------- T-603 --

def _stock_panel(D=80, N=12, seed=6):
    rng = np.random.default_rng(seed)
    A = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, (D, N)), axis=0))
    C = A * 0.98
    V = rng.uniform(1e5, 1e6, (D, N))
    return A, C, V


def test_t603_formation_unaffected_after_decision():
    A, C, V = _stock_panel()
    N = A.shape[1]
    mem = np.ones(N, bool)
    el = np.ones(N, bool)
    sh = np.full(N, 1e7)
    e_prev, f = 20, 41
    F0 = M.formation(A, C, V, mem, el, e_prev, f, sh)
    A2, C2, V2 = A.copy(), C.copy(), V.copy()
    A2[f + 1:] *= 5.0
    C2[f + 1:] *= 5.0
    V2[f + 1:] = np.nan
    F1 = M.formation(A2, C2, V2, mem, el, e_prev, f, sh)
    for k in ("r", "to", "cap"):
        assert np.allclose(F0[k], F1[k], equal_nan=True)
    l0 = M.stmom_legs(F0["r"], F0["to"], F0["el"])
    l1 = M.stmom_legs(F1["r"], F1["to"], F1["el"])
    assert all(np.array_equal(a, b) for a, b in zip(l0, l1))
    assert l0[0].sum() > 0 and l0[1].sum() > 0


def test_t603_shares_enter_at_availability():
    series = [(1000.0, "2018-12-31", 5e8), (2000.0, "2019-03-31", 6e8)]
    assert M.shares_known(series, 1500.0, "2019-02-01") == (5e8, "2018-12-31")
    assert M.shares_known(series, 2000.0, "2019-05-01") == (6e8, "2019-03-31")
    assert M.shares_known(series, 999.0, "2019-01-15") is None
    assert M.shares_known(series, 1500.0, "2020-03-01") is None         # older than 400 days


def test_t603_book_costs_and_placebo_permutation():
    rng = np.random.default_rng(7)
    Mn, N = 10, 20
    R = rng.normal(0, 0.05, (Mn, N))
    TO = rng.uniform(0.05, 0.5, (Mn, N))
    TO[0, 3] = np.nan
    EL = np.isfinite(TO)
    CAP = rng.uniform(1e9, 1e10, (Mn, N))
    HR = rng.normal(0, 0.05, (Mn, N))
    b = M.book_returns(R, TO, CAP, EL, HR)
    assert b["turnover"][0] >= 2.0 - 1e-9                # first entry: both legs from zero
    assert np.allclose(b["net"], b["gross"] - M.T603_COST * b["turnover"])
    P = M.permute_cols(TO, rng)
    assert np.array_equal(np.isfinite(P), np.isfinite(TO))
    for j in range(N):
        assert np.allclose(np.sort(P[np.isfinite(P[:, j]), j]), np.sort(TO[np.isfinite(TO[:, j]), j]))


# ------------------------------------------------------------------------------------------------------- T-596 --

def test_trailing_mean_point_in_time():
    rng = np.random.default_rng(8)
    X = rng.normal(size=(100, 5))
    i = 70
    m0 = M.trailing_mean(X, 60, 60)
    X2 = X.copy()
    X2[i + 1:] += 1000.0
    m1 = M.trailing_mean(X2, 60, 60)
    assert np.allclose(m0[:i + 1], m1[:i + 1], equal_nan=True)
    assert np.isnan(m0[58]).all() and np.isfinite(m0[59]).all()


def test_t596_industry_signal_unaffected_after_friday():
    rng = np.random.default_rng(9)
    N = 30
    r_week = rng.normal(0, 0.03, N)
    dv = rng.uniform(1e6, 1e8, N)
    el = np.ones(N, bool)
    sic2 = np.repeat([28, 35, 73], 10)
    y0 = rng.normal(0, 0.03, N)
    c0 = np.full(N, 0.002)
    w0 = M.industry_week(r_week, dv, el, sic2, y0, c0)
    w1 = M.industry_week(r_week, dv, el, sic2, y0 + 5.0, c0 * 3)      # only the target week changes
    assert np.allclose(w0["L"], w1["L"]) and np.allclose(w0["F"], w1["F"])
    assert list(w0["ind"]) == [28, 35, 73]
    assert np.all(w0["nf"] == 3)                                         # floor(10 / 3) followers per industry
    lead = np.argsort(dv[:10])[-3:]
    assert w0["L"][0] == pytest.approx((dv[lead] * r_week[lead]).sum() / dv[lead].sum())


def test_t596_week_ends_and_derangement():
    days = _weekdays("2021-01-04", 30)
    fr = M.week_last_sessions(days)
    assert all(date.fromisoformat(days[i]).weekday() == 4 for i in fr[:-1])
    src = M.derange(7, 200, np.random.default_rng(10))
    assert np.all(src != np.arange(7)[None, :])
    assert np.all(np.sort(src, axis=1) == np.arange(7)[None, :])


def test_t596_ls_week_legs():
    L = np.array([0.05, -0.04, 0.01, 0.0, -0.01, 0.02, 0.03, -0.02, 0.04, -0.03])
    nf = np.full(10, 2.0)
    sy = np.arange(10, dtype=float) * 0.01
    sc = np.full(10, 0.004)
    net, gross = M.ls_week(L, nf, sy, sc)
    top, bot = [0, 8], [1, 9]
    assert gross == pytest.approx(sy[top].sum() / 4 - sy[bot].sum() / 4)
    assert net == pytest.approx(gross - 0.004)
