"""Batch 13, group volregime_b (T-680, T-682, T-683, T-690): point-in-time signal construction (values shocked after the
decision never move the signal at it), the capped vol-matching constant, and inconclusive verdicts on missing bundles."""

import math

import numpy as np
import pandas as pd
import pytest

from mandel.experiments import batch13_volregime_b as M


def _bdays(n, start="1990-01-02"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(2 * n + 10, "D"), dtype="datetime64[D]")
    d = d[np.is_busday(d)][:n]
    return [str(x) for x in d]


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


# ================================================================================================ T-680 ==

def _factor(n, seed):
    rng = np.random.default_rng(seed)
    vol = 0.006 * np.exp(0.6 * np.sin(np.arange(n) / 70.0))
    return rng.standard_t(5, n) * vol / math.sqrt(5 / 3) + 0.0002


def test_semivar_weights_ignore_later_data():
    n = 2600
    days = _bdays(n, "1960-01-04")
    r = _factor(n, 1)
    F = M.factor_family(days, r, "1960-01")
    labs, last = F["labs"], F["last"]
    m = 80
    D = int(last[m])
    r2 = r.copy()
    r2[D + 1:] = np.random.default_rng(7).normal(0, 0.05, n - D - 1)        # violent path after the decision close
    F2 = M.factor_family(days, r2, "1960-01")
    for rd in ("close", "prev"):
        for sc in ("down", "tot", "up"):
            assert _same(F[rd][sc]["w"][:m + 1], F2[rd][sc]["w"][:m + 1]), (rd, sc)
            assert _same(F[rd][sc]["c"][:m + 1], F2[rd][sc]["c"][:m + 1]), (rd, sc)
            assert not _same(F[rd][sc]["w"][m + 1:], F2[rd][sc]["w"][m + 1:]), (rd, sc)
    # the decision-day return enters the close reading (the live proxy) but never the previous-close reading
    r3 = r.copy()
    r3[D] = -0.08
    F3 = M.factor_family(days, r3, "1960-01")
    assert F3["close"]["down"]["w"][m] != F["close"]["down"]["w"][m]
    assert F3["prev"]["down"]["w"][m] == F["prev"]["down"]["w"][m]
    assert len(labs) == F["R"].size


def test_solve_c_matches_the_capped_volatility():
    rng = np.random.default_rng(3)
    J = 300
    rv = rng.lognormal(-7.0, 0.8, J)
    U = 1.0 / rv
    Rn = rng.normal(0.004, 0.03, J)
    jmax = np.arange(J)
    c = M.solve_c(U, Rn, 0, jmax, cap=3.0, min_hist=24)
    assert np.isnan(c[:24]).all() and np.isfinite(c[24:]).all()
    for m in (24, 150, J - 1):
        x = np.minimum(3.0, c[m] * U[:m]) * Rn[:m]
        assert abs(x.std(ddof=1) - Rn[:m].std(ddof=1)) < 1e-9
    # holds after the decision never enter its constant
    Rn2 = Rn.copy()
    Rn2[150:] *= 9.0
    c2 = M.solve_c(U, Rn2, 0, jmax, cap=3.0, min_hist=24)
    assert _same(c[:151], c2[:151])


def test_managed_net_charges_weight_changes():
    w = np.array([1.0, 2.0, np.nan, 0.5])
    R = np.array([0.0, 0.01, -0.02, 0.03])
    x = M.managed_net(w, R, 0.001)
    assert math.isclose(x[1], 1.0 * 0.01 - 0.001 * 1.0)
    assert math.isclose(x[2], 2.0 * -0.02 - 0.001 * 1.0)
    assert np.isnan(x[3])                                     # no weight was decided at the third month-end


def test_sessions_only_folds_non_sessions_into_the_next():
    d, r = M.sessions_only(["a", "b", "c", "d"], [0.01, -0.001, 0.02, 0.0], {"a", "c", "d"})
    assert d == ["a", "c", "d"]
    assert math.isclose(r[1], (1 - 0.001) * 1.02 - 1)


# ================================================================================================ T-682 ==

def test_vol_target_daily_weights_ignore_later_data():
    n = 1200
    rng = np.random.default_rng(5)
    e = np.r_[np.nan, rng.normal(0.0003, 0.01, n - 1) * np.exp(0.5 * np.sin(np.arange(n - 1) / 40))]
    rb = np.r_[np.nan, np.full(n - 1, 1e-4)]
    r = e + rb
    w = M.vt_weights_daily(e)
    _, p, _ = M.position_returns(w, e, r, rb, 2e-4)
    t = 700
    e2 = e.copy()
    e2[t + 1:] = rng.normal(0, 0.06, n - t - 1)
    w2 = M.vt_weights_daily(e2)
    _, p2, _ = M.position_returns(w2, e2, e2 + rb, rb, 2e-4)
    assert _same(w[:t + 1], w2[:t + 1]) and not _same(w[t + 1:], w2[t + 1:])
    assert _same(p[:t + 3], p2[:t + 3])                       # the weight of close t is held over session t + 2
    assert np.isnan(w[:62]).all() and np.isfinite(w[63:]).all()


def test_fx_units_use_the_lagged_rate_and_past_spots_only():
    days = _bdays(500, "2010-01-04")
    rng = np.random.default_rng(2)
    spot = []
    for c in M.G10:
        s = 1.0 + 0.1 * rng.random()
        for d in days:
            s *= math.exp(rng.normal(0, 0.006))
            spot.append({"day": d, "ccy": c, "usd_per_unit": s})
    months = sorted({d[:7] for d in days} | {"2009-12"})
    rates = [{"month": m, "ccy": c, "rate3m": 2.0 + (0.5 if c == "AUD" else 0.0)} for m in months for c in M.G10 + ("USD",)]
    P = M.fx_panel(spot, rates)
    U = M.fx_units(P)
    t = 300
    # a rate printed for the month of day t (or later) never enters day t's accrual (one-month lag)
    shocked = [dict(r_, rate3m=r_["rate3m"] + (9.0 if r_["month"] >= days[t][:7] else 0.0)) for r_ in rates]
    U2 = M.fx_units(M.fx_panel(spot, shocked))
    first_of_month = next(i for i in range(t, 0, -1) if days[i][:7] != days[i - 1][:7])
    assert _same(U["FX"]["e"][:first_of_month], U2["FX"]["e"][:first_of_month])
    # spots after day t never move the basket's weights through t
    spot3 = [dict(r_, usd_per_unit=r_["usd_per_unit"] * (1.5 if r_["day"] > days[t] else 1.0)) for r_ in spot]
    U3 = M.fx_units(M.fx_panel(spot3, rates))
    assert _same(U["FX"]["w"][:t + 1], U3["FX"]["w"][:t + 1])
    assert _same(U["AUD"]["w"][:t + 1], U3["AUD"]["w"][:t + 1])


def test_to_master_compounds_onto_the_session_calendar():
    master = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    src = ["2020-01-02", "2020-01-04", "2020-01-06"]               # a print on a non-session day, none on 01-03 / 01-07
    x = M.to_master(src, [0.01, 0.02, 0.03], master)
    assert math.isclose(x[0], 0.01) and x[1] == 0.0 and math.isclose(x[2], 1.02 * 1.03 - 1)
    assert np.isnan(x[3])                                           # after the source's last print


def test_joint_bootstrap_did_runs_and_brackets():
    rng = np.random.default_rng(1)
    n, rows = 400, 6 + 9 + 1 + 9
    U = rng.normal(0.0003, 0.01, (rows, n))
    S = U * 1.1 + rng.normal(0, 0.001, (rows, n))
    out = M.joint_boot_did(S, U, 6, 9, 200, 0)
    for rd in ("basket", "pairs"):
        lo, hi = out[rd]["ci"]
        assert lo < hi


# ================================================================================================ T-683 ==

def _asset(n, seed):
    rng = np.random.default_rng(seed)
    vol = 0.01 * np.exp(0.7 * np.sin(np.arange(n) / 120.0))
    lr = rng.normal(0.0002, 1.0, n) * vol
    return 100.0 * np.exp(np.cumsum(lr))


def test_har_forecasts_ignore_later_data():
    n = 2400
    days = _bdays(n, "2003-01-02")
    adj = _asset(n, 4)
    iv = {d: 15.0 + 5 * math.sin(i / 50.0) for i, d in enumerate(days)}
    F = M.asset_forecasts(days, adj, iv, msm=False)
    t = 1900
    adj2 = adj.copy()
    adj2[t + 1:] *= np.exp(np.cumsum(np.random.default_rng(8).normal(0, 0.05, n - t - 1)))
    iv2 = {d: (v * 3 if d > days[t] else v) for d, v in iv.items()}
    F2 = M.asset_forecasts(days, adj2, iv2, msm=False)
    for k in ("EWMA", "HAR", "SHAR", "HARIV"):
        assert np.isfinite(F[k][t]), k
        assert _same(F[k][:t + 1], F2[k][:t + 1]), k
        assert not _same(F[k][t + 1:], F2[k][t + 1:]), k
    # the realised target is forward-looking by construction (it is never an input)
    assert not _same(F["T"][t - 25:t + 1], F2["T"][t - 25:t + 1])


def test_har_refit_uses_only_targets_realised_by_the_refit():
    n = 1500
    days = _bdays(n, "2004-01-02")
    lr = np.r_[np.nan, np.diff(np.log(_asset(n, 6)))]
    T = M.fwd_sum(lr * lr)
    X = M.har_design(lr, "SHAR")
    f, fits = M.har_forecasts_daily(days, X, T, 22, 500)
    me = M.month_end_idx(days)
    e = int(me[me > 900][0])
    T2 = T.copy()
    T2[e - 20:] *= 50.0                       # targets that end after the refit close e (s + 21 > e)
    f2, _ = M.har_forecasts_daily(days, X, T2, 22, 500)
    assert fits > 0
    assert _same(f[:e + 1], f2[:e + 1])


def test_tracking_loss_window_uses_its_own_sessions():
    rng = np.random.default_rng(0)
    lr = rng.normal(0, 0.01, 200)
    p = np.ones(200)
    L = M.tracking_losses(p, lr)
    s = 50
    v = math.sqrt(252 / 21 * np.sum(lr[s:s + 21] ** 2))
    assert math.isclose(L[s], math.log(v / 0.10) ** 2)
    lr2 = lr.copy()
    lr2[s + 21:] *= 4
    assert math.isclose(M.tracking_losses(p, lr2)[s], L[s])
    assert np.isnan(L[-20:]).all()


def test_dm_test_sign():
    rng = np.random.default_rng(1)
    d = rng.normal(-0.05, 0.2, 2000)
    r = M.dm_test(d)
    assert r["mean"] < 0 and r["p_less"] < 0.05


# ================================================================================================ T-690 ==

def _bars(days, seed, start=100.0):
    rng = np.random.default_rng(seed)
    c = start * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(days))))
    o = c * np.exp(rng.normal(0, 0.002, len(days)))
    v = rng.lognormal(14, 0.3, len(days))
    idx = pd.to_datetime(days).tz_localize("UTC") + pd.Timedelta(hours=13, minutes=30)
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) * 1.002, "l": np.minimum(o, c) * 0.998, "c": c, "v": v}, index=idx)


def _t690_inputs(days, syms):
    bars = {s: _bars(days, k + 1, 50 + 10 * k) for k, s in enumerate(syms)}
    fac = {s: {d: 1.0 - 0.0001 * (len(days) - i) / len(days) for i, d in enumerate(days)} for s in syms}
    cts = M.close_ts(days)
    si = {}
    for k, s in enumerate(syms):
        pub = cts[::10] + 3 * 3600 + 7 * 86400              # published a week after settlement, after the close
        rng = np.random.default_rng(100 + k)
        si[s] = (pub.astype(np.int64), rng.normal(13, 1, pub.size), rng.normal(0, 20, pub.size), rng.uniform(1, 5, pub.size))
    ivk = {"VIX": (cts + 5400, np.log(15 + 5 * np.sin(np.arange(len(days)) / 30.0)))}
    fomc = cts[::30] - 2 * 3600
    cpi = cts[5::21] - int(7.5 * 3600)
    return bars, fac, si, ivk, {"SPY": "VIX"}, fomc, cpi


def _shock_after(bars, fac, si, ivk, day, cts_day):
    b2 = {}
    for s, b in bars.items():
        b = b.copy()
        late = b.index > pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=23)
        b.loc[late, ["o", "h", "l", "c"]] *= 1.7
        b.loc[late, "v"] *= 9.0
        b2[s] = b
    f2 = {s: {d: (x * 0.5 if d > day else x) for d, x in f.items()} for s, f in fac.items()}
    s2 = {s: (a, np.where(a > cts_day, lv + 5, lv), np.where(a > cts_day, ch + 50, ch), np.where(a > cts_day, dt * 4, dt))
          for s, (a, lv, ch, dt) in si.items()}
    iv2 = {k: (a, np.where(a > cts_day, v + 2, v)) for k, (a, v) in ivk.items()}
    return b2, f2, s2, iv2


def test_t690_features_at_a_decision_ignore_later_data():
    days = _bdays(900, "2018-01-02")
    syms = ["SPY", "TLT", "GLD", "XLF"]
    bars, fac, si, ivk, ivm, fomc, cpi = _t690_inputs(days, syms)
    bill = lambda d: 1e-4 * (M.VRA._ord(d) - M.VRA._ord(days[0]))
    P = M.build_t690_panel(bars, fac, si, ivk, ivm, fomc, cpi, bill, end="2099-12-31")
    t = 700
    b2, f2, s2, iv2 = _shock_after(bars, fac, si, ivk, days[t], int(P["close_ts"][t]))
    P2 = M.build_t690_panel(b2, f2, s2, iv2, ivm, fomc, cpi, bill, end="2099-12-31")
    for k in M.T690_FEATS:
        src = P["common"] if k in P["common"] else P["read"]["adj"]["f"]
        src2 = P2["common"] if k in P2["common"] else P2["read"]["adj"]["f"]
        assert _same(src[k][:t + 1], src2[k][:t + 1]), k
    for rd in ("adj", "raw"):
        for k in ("rv63", "dsv63", "skew63", "vol_z", "dvol_z", "vn"):
            assert _same(P["read"][rd]["f"][k][:t + 1], P2["read"][rd]["f"][k][:t + 1]), (rd, k)
        assert not _same(P["read"][rd]["y"][t - 70:t + 1], P2["read"][rd]["y"][t - 70:t + 1])   # targets look forward
    assert np.isfinite(P["common"]["si_dtc"][t]).all() and np.isfinite(P["common"]["iv_log"][t, 0])
    # a short-interest release published after the decision close is not visible at it
    a, _, _, dt = si["SPY"]
    j = int(np.searchsorted(a, P["close_ts"][t], side="right")) - 1
    assert P["common"]["si_dtc"][t, 0] == dt[j] and a[j] <= P["close_ts"][t] < a[j + 1]


def test_t690_predictions_purged_and_point_in_time():
    days = _bdays(1100, "2017-01-03")
    syms = ["SPY", "TLT", "GLD", "XLF", "XLK", "IWM"]
    bars, fac, si, ivk, ivm, fomc, cpi = _t690_inputs(days, syms)
    bill = lambda d: 0.0
    P = M.build_t690_panel(bars, fac, si, ivk, ivm, fomc, cpi, bill, end="2099-12-31")
    me = M.month_end_sessions(days)
    dec = [int(i) for i in me if days[i][:4] == "2020"][:6]
    t = dec[-1]
    fp = M.fit_predict_year(P, "adj", list(M.T690_FEATS), "ridge", 2020, dec)
    b2, f2, s2, iv2 = _shock_after(bars, fac, si, ivk, days[t], int(P["close_ts"][t]))
    P2 = M.build_t690_panel(b2, f2, s2, iv2, ivm, fomc, cpi, bill, end="2099-12-31")
    fp2 = M.fit_predict_year(P2, "adj", list(M.T690_FEATS), "ridge", 2020, dec)
    assert fp["ok"] and fp2["ok"] and fp["n_train"] == fp2["n_train"]
    for i in dec:
        assert np.array_equal(fp["preds"][i][0], fp2["preds"][i][0])
        assert np.allclose(fp["preds"][i][1], fp2["preds"][i][1])
    # every training row's target was realised before the fit date
    days_a = np.array(days)
    first_2020 = int(np.searchsorted(days_a, "2020-01-01"))
    y2 = P["read"]["adj"]["y"].copy()
    late = np.where(P["yend"] >= first_2020)[0]
    P3 = {**P, "read": {**P["read"], "adj": {**P["read"]["adj"], "y": y2}}}
    P3["read"]["adj"]["y"][late] += 3.0
    fp3 = M.fit_predict_year(P3, "adj", list(M.T690_FEATS), "ridge", 2020, dec)
    for i in dec:
        assert np.allclose(fp["preds"][i][1], fp3["preds"][i][1])


def test_tranche_book_months_use_prices_through_their_end_only():
    days = _bdays(400, "2019-01-02")
    rng = np.random.default_rng(3)
    O = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (400, 10)), axis=0))
    me = M.month_end_sessions(days)
    dec = list(me[:12])
    sel = {k: (np.array([0, 1]), np.array([8, 9])) for k in range(10)}
    b = M.tranche_book(O, dec, sel, days)["net"]
    j = 5
    O2 = O.copy()
    O2[dec[j + 1] + 2:] *= 1.5                                # after the open that ends book month j
    b2 = M.tranche_book(O2, dec, sel, days)["net"]
    assert _same(b[:j + 1], b2[:j + 1]) and not _same(b[j + 1:], b2[j + 1:])
    # one tranche in the first month: a third of capital, entry cost on both legs
    L = np.mean(O[dec[1] + 1, [0, 1]] / O[dec[0] + 1, [0, 1]])
    S = np.mean(O[dec[1] + 1, [8, 9]] / O[dec[0] + 1, [8, 9]])
    gap = (np.datetime64(days[dec[1] + 1]) - np.datetime64(days[dec[0] + 1])).astype(int)
    exp = (L - 1 - (S - 1)) / 3 - 1e-4 * 2 / 3 - 0.005 / 3 * 1.0 * gap / 365
    assert math.isclose(b[0], exp, rel_tol=1e-9, abs_tol=1e-12)


def test_xs_select_top_and_bottom_fifth():
    L, S = M.xs_select(np.arange(10), np.arange(10.0))
    assert set(L) == {8, 9} and set(S) == {0, 1}
    L, S = M.xs_select(np.arange(10), np.arange(10.0), low_is_long=True)
    assert set(L) == {0, 1} and set(S) == {8, 9}


def test_days_to_next_and_asof_strict():
    ev = np.array([100, 200, 300])
    assert np.allclose(M.days_to_next(ev, np.array([100, 150])) * 86400, [100, 50])
    v = M.asof_values(np.array([10, 20]), np.array([1.0, 2.0]), np.array([9, 10, 19, 25]))
    assert np.isnan(v[0]) and v[1] == 1.0 and v[2] == 1.0 and v[3] == 2.0


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
    assert set(M.THEORY_MAP) == {"T-680", "T-682", "T-683", "T-690"}


# ================================================================== review fixes (filter sensitivity, RegSHO, lockbox) ==

def test_positivity_filter_only_floors_nonpositive_and_counts_triggers():
    n = 1500
    days = _bdays(n, "2004-01-02")
    lr = np.r_[np.nan, np.diff(np.log(_asset(n, 6)))]
    T = M.fwd_sum(lr * lr)
    X = M.har_design(lr, "SHAR")
    dg = {}
    fb, _ = M.har_forecasts_daily(days, X, T, 22, 500, diag=dg)
    fp, _ = M.har_forecasts_daily(days, X, T, 22, 500, filt="pos")
    assert dg["range"] + dg["nonpos"] >= 0
    differ = np.isfinite(fb) & (np.abs(fb - fp) > 1e-15)
    assert set(np.where(differ)[0]) <= set(dg["range_days"]) | set(dg["nonpos_days"])
    assert np.all(fp[np.isfinite(fp)] > 0)


def test_harv_iv_needs_250_rows_with_the_index():
    n = 1500
    days = _bdays(n, "2004-01-02")
    lr = np.r_[np.nan, np.diff(np.log(_asset(n, 6)))]
    T = M.fwd_sum(lr * lr)
    X = M.har_design(lr, "HAR")
    X[:900] = np.nan
    me = M.month_end_idx(days)
    f, _ = M.har_forecasts_daily(days, X, T, 22, M.T683_IV_ENTRY, refits=me)
    first = np.where(np.isfinite(f))[0][0]
    rows_by = np.isfinite(X).all(1)[:first - M.T683_H + 1].sum()
    assert rows_by >= M.T683_IV_ENTRY


def test_svr20_known_only_at_its_20th_file_and_ignores_later_shocks():
    rows = [(1000 + i, 10.0 + i, 100.0) for i in range(30)]
    e, x = M.svr20_events(rows)
    assert e[0] == 1019 and x.size == 11
    rows2 = rows[:25] + [(1000 + i, 99.0, 100.0) for i in range(25, 30)]
    e2, x2 = M.svr20_events(rows2)
    q = np.array([1022])                              # decision before the shocked files' available_at
    assert _same(M.asof_values(e, x, q), M.asof_values(e2, x2, q))


def test_lockbox_count_from_data():
    d = _bdays(400, "2026-09-01")
    assert M.lockbox_count(d[:30]) == 0
    assert M.lockbox_count(d) >= 12
