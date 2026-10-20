"""Batch-4 factor and ETF-tilt harnesses (group 'fact') on synthetic data: planted effects pass, nulls do not.

No network and no archive: every series here is simulated. Each core claim test gets a planted-effect case that
reaches 'supported' (or the best verdict its unimplementable criteria allow) and a null case that does not."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch4_fact as bf


# ------------------------------------------------------------------------ fixtures --

def _bdays(n, start="1990-01-02"):
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _months(y, m, n):
    return [f"{y + (m - 1 + k) // 12:04d}-{(m - 1 + k) % 12 + 1:02d}" for k in range(n)]


SMALL_FAMILY = [0.0, 0.004, -0.004, 0.008, -0.002]          # per-day Sharpes of a quiet family


# ------------------------------------------------------------------- statistics --

def test_stud_mean_ci_covers_true_mean_under_autocorrelation():
    rng = np.random.default_rng(0)
    hits = 0
    for k in range(120):
        e = rng.normal(0, 1, 600)
        x = np.empty(600)
        x[0] = e[0]
        for t in range(1, 600):
            x[t] = 0.5 * x[t - 1] + e[t]                     # AR(1), true mean 0
        _, lo, hi = bf.stud_mean_ci(x, 10, n_boot=400, seed=k)
        hits += lo <= 0 <= hi
    assert 0.86 <= hits / 120 <= 1.0


def test_ols_nw_recovers_coefficients():
    rng = np.random.default_rng(1)
    X = rng.normal(0, 1, (2000, 3))
    y = 0.5 + X @ np.array([1.0, -2.0, 0.3]) + rng.normal(0, 0.1, 2000)
    r = bf.ols_nw(y, X, 6)
    assert np.allclose(r["coef"], [0.5, 1.0, -2.0, 0.3], atol=0.02)
    assert r["t"][0] > 50


def test_sharpe_diff_ci_detects_planted_and_null():
    rng = np.random.default_rng(2)
    b = rng.normal(0.005, 0.04, 700)
    a = b * 0.5 + rng.normal(0.006, 0.01, 700)              # much higher Sharpe
    obs, lo, hi = bf.sharpe_diff_ci(a, b, 12, 12, n_boot=500)
    assert obs > 0 and lo > 0 and hi > lo
    c = rng.normal(0.005, 0.04, 700)
    obs, lo, hi = bf.sharpe_diff_ci(c, b, 12, 12, n_boot=500)
    assert lo < 0 < hi


def test_trailing_beta_uses_only_data_to_t_minus_1():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 0.01, 300)
    y = 1.5 * x + rng.normal(0, 0.002, 300)
    b = bf.trailing_beta(y, x, 60, gap=2)
    assert np.isnan(b[60]) and np.isfinite(b[61]) and abs(b[200] - 1.5) < 0.1
    y2 = y.copy()
    y2[199] += 0.5                                           # the day before the position day must not matter
    assert bf.trailing_beta(y2, x, 60, gap=2)[200] == pytest.approx(b[200])
    y2[198] += 0.5                                           # two days before is in the window
    assert bf.trailing_beta(y2, x, 60, gap=2)[200] != pytest.approx(b[200])


def test_ls_book_dollar_neutral_month_pnl_is_leg_difference():
    days = _bdays(60, "2020-01-01")
    rng = np.random.default_rng(4)
    rl, rs = rng.normal(0, 0.01, 60), rng.normal(0, 0.01, 60)
    one = np.ones(60)
    pnl, nreb = bf.ls_book(days, rl, rs, one, one)
    jan = [i for i, d in enumerate(days) if d[:7] == "2020-01"]
    expect = np.prod(1 + rl[jan]) - np.prod(1 + rs[jan])
    assert pnl[jan].sum() == pytest.approx(expect)
    assert nreb == len({d[:7] for d in days})


def test_compound_monthly_drops_incomplete_months():
    days = _bdays(70, "2020-01-15")                          # starts mid-January, ends mid-April
    ms, r = bf.compound_monthly(days, np.full(70, 0.001))
    assert ms == ["2020-02", "2020-03"]
    assert r[0] == pytest.approx(1.001 ** 20 - 1)


def test_family_dsr_floors_variance_and_rewards_skill():
    rng = np.random.default_rng(5)
    good = bf.family_dsr(rng.normal(0.002, 0.01, 5000), SMALL_FAMILY)
    bad = bf.family_dsr(rng.normal(0.0, 0.01, 5000), SMALL_FAMILY)
    assert good["var_trials_sr"] >= 1 / 4999 and good["n_trials"] == 34
    assert good["dsr"] > 0.95 and bad["dsr"] < 0.5


# ------------------------------------------------------------- core claim tests --

def test_factor_mean_test_planted_null_short_and_no_family():
    rng = np.random.default_rng(10)
    days = _bdays(9000)
    planted = bf.factor_mean_test(days, rng.normal(0.0012, 0.006, 9000), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=1000)
    assert planted["verdict"] == "supported" and planted["ci_ann"][0] > 0
    null = bf.factor_mean_test(days, rng.normal(0.0, 0.006, 9000), days[0], days[-1], 8000, SMALL_FAMILY, n_boot=1000)
    assert null["verdict"] == "not_supported"
    short = bf.factor_mean_test(days, rng.normal(0.0012, 0.006, 9000), days[0], days[3000], 8000, SMALL_FAMILY, n_boot=200)
    assert short["verdict"] == "inconclusive"
    nofam = bf.factor_mean_test(days, rng.normal(0.0012, 0.006, 9000), days[0], days[-1], 8000, None, n_boot=200)
    assert nofam["verdict"] == "inconclusive"                # DSR criterion not implemented -> never supported
    assert " — " in planted["reason"] and planted["reason"].endswith("all criteria pass")


def _hedged_world(alpha_d, seed):
    rng = np.random.default_rng(seed)
    n = 4300
    days = _bdays(n, "2005-01-03")
    rf = np.full(n, 0.0001)
    r_s = rng.normal(0.0004, 0.01, n)
    fac = rng.normal(0, 0.004, (n, 6))
    fac[:, 0] = r_s - rf                                       # Mkt-RF is the hedge asset's excess return
    r_q = rf + 0.9 * (r_s - rf) + 0.2 * fac[:, 3] + alpha_d + rng.normal(0, 0.003, n)
    cols = []
    ms = None
    for j in range(6):
        ms, c = bf.compound_monthly(days, fac[:, j])
        cols.append(c)
    return days, r_q, r_s, rf, ms, np.column_stack(cols)


def test_hedged_alpha_test_planted_and_null():
    names = bf.FF5 + ["UMD"]
    days, rq, rs, rf, ms, F = _hedged_world(0.0006, 11)
    rep = bf.hedged_alpha_test(days, rq, rs, rf, ms, F, names, start=days[0], end=days[-1], qmj_loading=0.7,
                               family_sharpes=SMALL_FAMILY, n_boot=200)
    assert rep["verdict"] == "supported" and rep["alpha_t"] > 2 and abs(rep["mean_hedge_ratio"] - 0.9) < 0.1
    assert rep["loadings"]["RMW"]["beta"] == pytest.approx(0.2, abs=0.1)
    no_qmj = bf.hedged_alpha_test(days, rq, rs, rf, ms, F, names, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=50)
    assert no_qmj["verdict"] == "inconclusive"               # the archived harness's situation: QMJ not available
    days, rq, rs, rf, ms, F = _hedged_world(0.0, 12)
    null = bf.hedged_alpha_test(days, rq, rs, rf, ms, F, names, start=days[0], end=days[-1], qmj_loading=0.7,
                                family_sharpes=SMALL_FAMILY, n_boot=50)
    assert null["verdict"] == "not_supported" and null["alpha_t"] < 2


def _size_world(drift, rmw_load, seed):
    rng = np.random.default_rng(seed)
    n = 6600
    days = _bdays(n, "2000-06-01")
    f5 = rng.normal(0, 0.004, (n, 5))
    r_s = rng.normal(0.0003, 0.012, n)
    r_l = r_s + drift + rmw_load * f5[:, 3] + rng.normal(0, 0.002, n)
    cols, ms = [], None
    for j in range(5):
        ms, c = bf.compound_monthly(days, f5[:, j])
        cols.append(c)
    return days, r_l, r_s, ms, np.column_stack(cols)


def test_size_spread_test_planted_and_null():
    days, rl, rs, ms, F = _size_world(0.0005, 0.5, 13)
    rep = bf.size_spread_test(days, rl, rs, ms, F, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=1000)
    assert rep["verdict"] == "supported" and rep["rmw_t"] > 1.96 and rep["ci_ann"][0] > 0
    days, rl, rs, ms, F = _size_world(0.0, 0.0, 14)
    null = bf.size_spread_test(days, rl, rs, ms, F, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=1000)
    assert null["verdict"] == "not_supported"


def _bab_world(alpha_low, alpha_high, seed, n=4000):
    rng = np.random.default_rng(seed)
    days = _bdays(n, "2011-05-02")
    r_m = rng.normal(0.0004, 0.01, n)
    r_l = 0.6 * r_m + alpha_low + rng.normal(0, 0.004, n)
    r_h = 1.4 * r_m + alpha_high + rng.normal(0, 0.006, n)
    return days, r_l, r_h, r_m, np.full(n, 0.02)


def test_bab_spread_test_planted_and_null():
    days, rl, rh, rm, rate = _bab_world(0.0003, -0.0003, 15)
    rep = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=1000)
    assert rep["verdict"] == "supported" and abs(rep["ex_post_beta"]) < 0.1 and rep["ci_ann"][0] > 0
    assert rep["mean_long_notional"] + rep["mean_short_notional"] <= 2.0 + 1e-9
    days, rl, rh, rm, rate = _bab_world(0.0, 0.0, 16)
    null = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=1000)
    assert null["verdict"] == "not_supported" and null["mean_ann"] < 0          # financing and borrow eat a zero-alpha spread


def test_bab_spread_test_invalid_when_beta_not_neutral():
    # the low-beta leg's true beta switches 0.2 <-> 1.8 every 60 days; trailing betas lag, and 1/beta leverage makes
    # the lag asymmetric, so the book carries net market exposure: the ex-post beta criterion must be what fails
    days, rl, rh, rm, rate = _bab_world(0.0003, -0.0003, 17)
    rng = np.random.default_rng(100)
    b = np.where((np.arange(len(rm)) // 60) % 2 == 0, 0.2, 1.8)
    rl = b * rm + 0.0003 + rng.normal(0, 0.004, len(rm))
    rep = bf.bab_spread_test(days, rl, rh, rm, rate, start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=200)
    assert rep["verdict"] == "not_supported" and abs(rep["ex_post_beta"]) >= 0.1
    assert "|ex-post beta to the market| < 0.1" in rep["reason"].split(" — ")[1]


def test_bab_spread_flattens_unhedgeable_book_instead_of_carrying_stale_positions():
    # regression (reviewer, T-387): the low-beta leg's beta falls to 0.08 (hedgeable: the 2x gross cap keeps the book
    # beta-neutral), then to -0.3 (not hedgeable), and the market is flat for 70 days (beta missing). The old 0.1 floor
    # skipped those resets and carried drifted positions with a held ex-ante beta up to 0.90; the book must instead
    # stay inside the +/-0.15 band on every live day and sit flat in cash when a reset cannot hedge it.
    n = 4000
    rng = np.random.default_rng(18)
    days = _bdays(n, "2011-05-02")
    rm = rng.normal(0.0004, 0.01, n)
    rm[3200:3270] = 0.0
    b = np.full(n, 0.6)
    b[1500:2300] = 0.08
    b[2300:3000] = -0.3
    rl = b * rm + 0.0003 + rng.normal(0, 0.002, n)
    rh = 1.4 * rm - 0.0003 + rng.normal(0, 0.006, n)
    rep = bf.bab_spread_test(days, rl, rh, rm, np.full(n, 0.02), start=days[0], end=days[-1], family_sharpes=SMALL_FAMILY, n_boot=200)
    assert rep["max_abs_exante_beta_held"] <= 0.15 + 1e-9
    assert abs(rep["ex_post_beta"]) < 0.1
    idx = np.array([days.index(d) for d in rep["_days"]])
    flat = rep["_flat"]
    assert rep["n_flat_days"] == int(flat.sum()) > 500 and f"{rep['n_flat_days']} flat days" in rep["reason"]
    assert flat[(idx >= 2400) & (idx < 3000)].all()               # negative beta: flat, not stale
    assert not flat[(idx >= 1600) & (idx < 2300)].any()           # small positive beta: hedged under the gross cap
    nanb = ~np.isfinite(bf.trailing_beta(rl, rm, 60, 2)[idx])
    assert nanb.sum() > 5 and flat[nanb].all()                    # beta missing: flattened at once
    episodes = int(flat[0]) + int(np.sum(flat[1:] & ~flat[:-1]))
    pf = rep["_pnl"][flat]
    assert np.all((pf == 0.0) | (pf == -0.0002)) and int(np.sum(pf == -0.0002)) == episodes   # only the flattening trade costs


def _regime_factors(seed, T=760, K=6):
    rng = np.random.default_rng(seed)
    F = np.empty((T, K))
    for k in range(K):
        mu = np.empty(T)
        t, s = 0, rng.choice([-1, 1])
        while t < T:
            L = int(rng.integers(36, 96))
            mu[t:t + L] = s * 0.012
            s, t = -s, t + L
        F[:, k] = mu + rng.normal(0, 0.02, T)
    return F


def test_factor_momentum_test_planted_and_null():
    ms = _months(1963, 7, 760)
    names = ["HML", "SMB", "RMW", "CMA", "UMD", "BAB"]
    rep = bf.factor_momentum_test(ms, _regime_factors(20), names, n_boot=1000)
    assert rep["verdict"] == "supported" and rep["ci"][0] > 0 and rep["dsr"] > 0.95 and rep["pbo"] < 0.5
    assert rep["window_used"].startswith("1964-07")               # 12-1 formation needs 12 months of history
    null = bf.factor_momentum_test(ms, np.random.default_rng(21).normal(0.003, 0.02, (760, 6)), names, n_boot=1000)
    assert null["verdict"] == "not_supported"


def test_tilt_is_contrarian_and_capped():
    t = bf._tilt(np.array([-3.0, -1.5, -0.5, 0.5, 1.5, 3.0, np.nan]))
    assert list(t) == [0.5, 0.25, 0.0, 0.0, -0.25, -0.5, 0.0]


def test_contrarian_timing_test_planted_and_null():
    T = 760
    ms = _months(1963, 7, T)
    names = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
    rng = np.random.default_rng(22)
    t = np.arange(T)
    F = 0.004 + 0.02 * np.sin(2 * np.pi * t[:, None] / 80 + rng.uniform(0, 2 * np.pi, 6)[None, :]) + rng.normal(0, 0.015, (T, 6))
    start = ms.index("1968-01")
    vs = bf.contrarian_portfolios(F, ms, 48, np.ones(6), start)[1]       # stand-in for the 5th (value-spread) trial
    rep = bf.contrarian_timing_test(ms, F, names, n_boot=1000, value_spread_timed=vs)
    assert rep["verdict"] == "supported" and rep["ci"][0] > 0 and rep["dsr"] > 0.95
    assert rep["window_used"].startswith("1968-01") and len(rep["trial_diff_sharpes_ann"]) == 5
    null = bf.contrarian_timing_test(ms, rng.normal(0.004, 0.02, (T, 6)), names, n_boot=1000)
    assert null["verdict"] == "not_supported"


def test_contrarian_timing_dsr_unimplemented_without_value_spread_trial():
    # regression (reviewer, T-389): the archive has no 6_Portfolios_2x3 BE/ME, so the 5th DSR trial is uncomputed;
    # the DSR criterion must then be None and a passing CI can reach only 'inconclusive', never 'supported'
    T = 760
    ms = _months(1963, 7, T)
    names = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
    rng = np.random.default_rng(22)
    t = np.arange(T)
    F = 0.004 + 0.02 * np.sin(2 * np.pi * t[:, None] / 80 + rng.uniform(0, 2 * np.pi, 6)[None, :]) + rng.normal(0, 0.015, (T, 6))
    rep = bf.contrarian_timing_test(ms, F, names, n_boot=1000)
    assert rep["ci"][0] > 0 and rep["dsr"] > 0.95                         # both would pass ...
    assert rep["verdict"] == "inconclusive" and rep["dsr_decided"] is False  # ... but the DSR is not decided
    assert rep["reason"].endswith("not implemented: DSR > 0.95 over 5 trials (value-spread trial not computable)")
    assert "value-spread trial not computable" in rep["reason"].split(" — ")[0]
    with pytest.raises(ValueError):
        bf.contrarian_timing_test(ms, F, names, n_boot=50, value_spread_timed=np.zeros(10))


def test_monthly_engines_use_no_future_data():
    T = 300
    ms = _months(1963, 7, T)
    rng = np.random.default_rng(23)
    F = rng.normal(0.004, 0.02, (T, 6))
    G = F.copy()
    G[200:] += rng.normal(0, 0.05, (T - 200, 6))                 # rewrite history from month 200 on
    s1, t1 = bf.contrarian_portfolios(F, ms, 60, np.ones(6), 120)
    s2, t2 = bf.contrarian_portfolios(G, ms, 60, np.ones(6), 120)
    assert np.allclose(t1[:200 - 120], t2[:200 - 120]) and np.allclose(s1[:80], s2[:80])
    assert not np.allclose(t1[80:], t2[80:])
    m1, v1 = bf.momentum_portfolios(F, 12)
    m2, v2 = bf.momentum_portfolios(G, 12)
    assert np.allclose(m1[:200 - 12], m2[:200 - 12])
    assert all(np.allclose(v1[k][:200 - 12], v2[k][:200 - 12]) for k in v1)


def test_contrarian_tilt_waits_one_quarter():
    # a shock to HML in 1980-04 enters the 60-month z-score from 1980-04; with the one-quarter embargo the 1980-07
    # rebalance reads 1980-03 (unchanged) and the 1980-10 rebalance reads 1980-06 (changed: HML now cheap)
    T = 300
    ms = _months(1963, 7, T)
    F = np.random.default_rng(24).normal(0.004, 0.02, (T, 6))
    G = F.copy()
    G[ms.index("1980-04"), 2] -= 0.6
    _, _, t1 = bf.contrarian_portfolios(F, ms, 60, np.ones(6), 120, return_tilts=True)
    _, _, t2 = bf.contrarian_portfolios(G, ms, 60, np.ones(6), 120, return_tilts=True)
    assert all(np.allclose(t1[m], t2[m]) for m in t1 if m <= "1980-07")
    assert t2["1980-10"][2] == pytest.approx(0.5) and not np.allclose(t1["1980-10"], t2["1980-10"])


def _industry_world(alpha_m, seed, T=420):
    rng = np.random.default_rng(seed)
    ms = _months(1991, 1, T)
    F5 = rng.normal(0.005, 0.03, (T, 5))
    rf = np.full(T, 0.002)
    port = rf + alpha_m + F5 @ np.array([0.7, 0.2, 0.3, 0.4, 0.1]) + rng.normal(0, 0.02, T)
    return ms, port, rf, F5


def test_industry_alpha_test_planted_and_null():
    ms, port, rf, F5 = _industry_world(0.006, 30)
    rep = bf.industry_alpha_test(ms, port, rf, F5)
    assert rep["verdict"] == "supported" and rep["n"] >= 200 and rep["alpha_t"] >= 2
    ms, port, rf, F5 = _industry_world(0.0, 31)
    assert bf.industry_alpha_test(ms, port, rf, F5)["verdict"] == "not_supported"
    short = bf.industry_alpha_test(ms, port, rf, F5, start="2015-01")
    assert short["verdict"] == "inconclusive"


def test_sort_spread_test_planted_and_null():
    rng = np.random.default_rng(40)
    T = 760
    ms = _months(1963, 7, T)
    F5 = rng.normal(0.005, 0.03, (T, 5))
    planted = 0.007 + 0.3 * F5[:, 4] + rng.normal(0, 0.02, T)
    rep = bf.sort_spread_test(ms, planted, ms, F5, "1996-07", "2026-09", 300, "planted", split_before="1996-07", n_boot=2000)
    assert rep["verdict"] == "supported" and rep["ci_month"][0] > 0 and rep["alpha_t"] >= 2
    null = 0.3 * F5[:, 4] + rng.normal(0, 0.02, T)
    assert bf.sort_spread_test(ms, null, ms, F5, "1996-07", "2026-09", 300, "null", n_boot=2000)["verdict"] == "not_supported"


# ------------------------------------------------------------------ module contract --

def test_registry_maps_every_theory_to_a_harness():
    assert set(bf.THEORY_MAP) == {"T-382", "T-383", "T-385", "T-386", "T-387", "T-388", "T-389", "T-397", "T-445", "T-446", "T-447", "T-449"}
    assert set(bf.THEORY_MAP.values()) == set(bf.HARNESSES)
    assert all(h.startswith("fact_") for h in bf.HARNESSES)
    assert len(bf.FAMILY) == 14


class _EmptyArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


def test_harnesses_are_inconclusive_when_data_missing():
    for name, h in bf.HARNESSES.items():
        stat, n, verdict, reason = h(_EmptyArchive())
        assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert " — " in reason
