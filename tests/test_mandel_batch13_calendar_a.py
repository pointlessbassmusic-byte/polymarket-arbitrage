"""Batch 13, group calendar_a (T-589, T-592, T-582, T-581, T-583): point-in-time signal construction, the statistics'
linearised series, and missing data."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch13_calendar_a as M
from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL


def _bdays(n, start="2010-01-04"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(3 * n, "D"), dtype="datetime64[D]")
    d = d[np.is_busday(d)][:n]
    return [str(x) for x in d]


def _sessions(start, end):
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if CAL.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _walk(n, seed, vol=0.01, drift=0.0003):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


def _bars(days, seed=0):
    rng = np.random.default_rng(seed)
    c = _walk(len(days), seed)
    o = c * np.exp(rng.normal(0, 0.003, len(days)))
    h = np.maximum(o, c) * (1 + rng.random(len(days)) * 0.01)
    lo = np.minimum(o, c) * (1 - rng.random(len(days)) * 0.01)
    return OHLC.Bars(list(days), o, h, lo, c, c.copy())


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


# ================================================================================================ T-589 auctions ==

def _yields(days, seed):
    rng = np.random.default_rng(seed)
    out = {}
    for t in M.T589_TENORS:
        if t == 30:
            continue
        out[t] = {d: float(v) for d, v in zip(days, 2 + t / 10 + np.cumsum(rng.normal(0, 0.03, len(days))))}
    out[30] = out[20]
    return out


def test_synth_returns_use_only_the_previous_close():
    days = _bdays(800, "2013-06-03")
    y = _yields(days, 1)
    P = M.synth_panel(y, start="2014-01-01", end="2026-12-31")
    k = 300
    cut = P["days"][k]
    y2 = {t: {d: (v + (0.5 if d > cut else 0.0)) for d, v in s.items()} for t, s in y.items() if t != 30}
    y2[30] = y2[20]
    P2 = M.synth_panel(y2, start="2014-01-01", end="2026-12-31")
    assert _same(P["V"][:, :k + 1], P2["V"][:, :k + 1])                    # nothing after the close of day k moves it
    assert not _same(P["V"][:, k + 1:], P2["V"][:, k + 1:])
    j = 10                                                                  # the 10-year leg is unscaled; others are DV01-scaled
    i10 = P["tenors"].index(10)
    d, p = P["days"][j], P["days"][j - 1]
    r = y[10][p] / 100 / 252 - M.mod_duration(y[10][p], 10) * (y[10][d] - y[10][p]) / 100
    assert P["V"][i10, j] == pytest.approx(r)
    assert (P["U"][:, P["me"]] == 0).all() and P["me"].sum() > 0           # month-end sessions are excluded


def test_auction_tenor_maps_reopenings_to_the_auctioned_tenor():
    assert M.auction_tenor("9-Year 11-Month") == 10
    assert M.auction_tenor("19-Year 10-Month") == 20
    assert M.auction_tenor("29-Year 11-Month") == 30
    assert M.auction_tenor("2-Year") == 2 and M.auction_tenor("7-Year") == 7


def _auction_rows():
    rows = []
    def add(cusip, term, ad, ann, amt, frn="No", tips="No", reopen="No", held=True):
        v = {"cusip": cusip, "security_type": "Note", "security_term": term, "auction_date": ad, "announcemt_date": ann,
             "offering_amt": str(amt), "reopening": reopen, "inflation_index_security": tips, "floating_rate": frn,
             "nominal_coupon": frn == "No" and tips == "No"}
        rows.append({"kind": "auction-announcement", "key": f"{cusip}:{ad}", "available_at": f"{ann}T23:59:59+00:00", "value": v})
        if held:
            rows.append({"kind": "auction-result", "key": f"{cusip}:{ad}", "value": {}})
    # a 2/5/7 week, a 10/30 week, an FRN-only week, a TIPS week
    add("A2", "2-Year", "2015-01-27", "2015-01-22", 26e9)
    add("A5", "5-Year", "2015-01-28", "2015-01-22", 35e9)
    add("A7", "7-Year", "2015-01-29", "2015-01-22", 29e9)
    add("A3", "3-Year", "2015-02-10", "2015-02-05", 24e9)
    add("A10", "10-Year", "2015-02-11", "2015-02-05", 24e9)
    add("F2", "2-Year", "2015-02-25", "2015-02-19", 15e9, frn="Yes")
    add("T5", "5-Year", "2015-03-19", "2015-03-12", 16e9, tips="Yes")
    add("X2", "2-Year", "2015-04-28", "2015-04-23", 26e9, held=False)            # announced, not held: out
    return rows


def test_auction_parsing_filters_frn_tips_and_unheld():
    au, weeks = M.t589_auctions(_auction_rows())
    assert {a["cusip"] for a in au} == {"A2", "A5", "A7", "A3", "A10"}
    assert M.iso_week("2015-02-25") in weeks and M.iso_week("2015-03-19") in weeks   # FRN/TIPS weeks are coupon weeks


def test_clusters_unseen_vs_seen_and_t_is_the_first_auction():
    days = _bdays(400, "2014-10-01")
    au, _ = M.t589_auctions(_auction_rows())
    un = M.t589_clusters(au, days, M.T589_UNSEEN, M.T589_SEEN)
    se = M.t589_clusters(au, days, M.T589_SEEN)
    assert [c["t"] for c in un] == ["2015-01-27"] and un[0]["tenors"] == [2, 5, 7]
    assert [c["t"] for c in se] == ["2015-02-10"] and se[0]["tenors"] == [10]       # the 3-year sets t, has no series
    c = un[0]
    assert days[c["a"]] < days[c["i_t"] - 1] < "2015-01-27" <= days[c["i_t"]]
    assert c["i_t"] - c["a"] == M.T589_SPAN + 1


def test_auction_z_ignores_later_auctions():
    base = [{"tenor": 2, "date": f"2015-{m:02d}-25", "amt": 26e9 + m * 1e8, "cusip": f"C{m}"} for m in range(1, 13)]
    z = M.auction_z(base, min_prior=6)
    k = ("C8", "2015-08-25")
    later = [dict(a, amt=a["amt"] * (5 if a["date"] > "2015-08-25" else 1)) for a in base]
    assert z[k] == pytest.approx(M.auction_z(later, min_prior=6)[k])
    earlier = [dict(a, amt=a["amt"] * (2 if a["date"] == "2015-03-25" else 1)) for a in base]
    assert M.auction_z(earlier, min_prior=6)[k] != pytest.approx(z[k])


def test_size_window_starts_after_the_announcement_day():
    days = _bdays(400, "2014-10-01")
    y = _yields(days, 2)
    P = M.synth_panel(y, start="2014-11-01", end="2016-12-31")
    au, _ = M.t589_auctions(_auction_rows())
    un = M.t589_clusters(au, P["days"], M.T589_UNSEEN, M.T589_SEEN, start="2014-11-01")
    z = {(a["cusip"], a["date"]): 0.5 for a in au}
    cons = M.size_rows(P, un, z, conservative=True)
    reg = M.size_rows(P, un, z, conservative=False)
    assert cons[0][2] == reg[0][2] - 1                                       # one session fewer: the next close after the stamp
    # shocking yields after t-1 leaves the size window's return untouched (only the full-sample baseline mean moves)
    cut = P["days"][un[0]["i_t"] - 1]
    y2 = {t: {d: (v + (1.0 if d > cut else 0.0)) for d, v in s.items()} for t, s in y.items() if t != 30}
    y2[30] = y2[20]
    P2 = M.synth_panel(y2, start="2014-11-01", end="2016-12-31")

    def raw(Q, row):
        ks = [Q["tenors"].index(t) for t in un[0]["tenors"]]
        return row[1] + row[2] * np.mean([Q["U"][k, ~Q["me"]].mean() for k in ks])
    r2 = M.size_rows(P2, un, z, conservative=True)[0]
    assert r2[0] == cons[0][0] and r2[2] == cons[0][2] and raw(P2, r2) == pytest.approx(raw(P, cons[0]))


def test_concession_test_detects_an_injected_concession_and_cluster_values_are_window_minus_mean():
    days = _bdays(1500, "2014-01-02")
    y = _yields(days, 3)
    P = M.synth_panel(y, start="2014-01-01", end="2026-12-31")
    rng = np.random.default_rng(4)
    starts = np.sort(rng.choice(np.arange(10, P["U"].shape[1] - 10, 7), 60, replace=False))
    cl = [{"t": P["days"][a + 5], "a": int(a), "tenors": [2, 5]} for a in starts]
    W = M.windows(P["U"])
    A = M._weights(cl, P["tenors"])
    vals = M.cluster_values(W, A, starts)
    k2, k5 = P["tenors"].index(2), P["tenors"].index(5)
    v0 = 0.5 * (W[k2, starts[0]] - W[k2].mean()) + 0.5 * (W[k5, starts[0]] - W[k5].mean())
    assert vals[0] == pytest.approx(v0)
    V = P["V"].copy()
    for a in starts:
        V[:, a + 1:a + 5] -= 0.01                                            # a 4-session concession of 400 bps
    Q = dict(P, V=V, U=V * (~P["me"])[None, :])
    pool = np.array([[a - 5 + k for k in range(5)] for a in range(20, Q["U"].shape[1] - 30, 9)])
    r = M.concession_test(Q, cl, pool, 0.0, n_boot=300, split=None)
    assert r["excess"] < -0.01 and r["boot_p_less"] < 0.01 and r["place_p_less"] < 0.01


def test_period_demeaned_values_use_each_clusters_own_half():
    rng = np.random.default_rng(20)
    W = rng.normal(0, 1, (2, 400))
    seg = (np.arange(400) >= 250).astype(int)
    starts = np.array([10, 100, 260, 390])
    A = np.array([[0.5, 0.5], [1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    v = M.cluster_values(W, A, starts, seg)
    for c, a in enumerate(starts):
        m = W[:, seg == seg[a]].mean(axis=1)
        assert v[c] == pytest.approx(float(A[c] @ (W[:, a] - m)))
    assert _same(M.cluster_values(W, A, starts), M.cluster_values(W, A, starts, np.zeros(400, int)))


def test_window_segments_classify_by_the_close_of_t_minus_1():
    days = _bdays(30, "2019-12-02")
    seg = M.window_segments(days, len(days) - M.T589_SPAN, "2020-01-01")
    for a, s in enumerate(seg):
        assert s == (days[a + M.T589_SPAN] >= "2020-01-01")


def test_year_stratified_placement_never_draws_another_year():
    days = _bdays(800, "2014-01-02")
    S = len(days) - M.T589_SPAN
    pool = M.placement_pool(days, set())
    py = M.pool_years(days, pool)
    assert set(py) >= {2014, 2015, 2016}
    W = np.zeros((1, S))
    W[0, pool[py == 2015].ravel()] = 1.0                                    # only the 2015 pool weeks' windows carry 1
    A = np.ones((6, 1))
    wd = np.array([0, 1, 2, 3, 4, 2])
    cy = np.array([2015] * 6)
    seg = np.zeros(S, int)
    const = 1.0 - W[0].mean()                                               # every same-year draw: 1 - the unconditional mean
    lo = M._placement_strat_batch(W, A, wd, pool, py, cy, seg, const - 1e-9, 500, 0)
    hi = M._placement_strat_batch(W, A, wd, pool, py, cy, seg, const + 1e-9, 500, 0)
    assert lo == (1.0, pytest.approx(1 / 501)) and hi == (pytest.approx(1 / 501), 1.0)


def test_placement_pool_excludes_coupon_weeks():
    days = _bdays(200, "2015-01-05")
    weeks = {M.iso_week(d) for d in days[:50]}
    pool = M.placement_pool(days, weeks)
    assert pool.size and all(M.iso_week(days[s + 5]) not in weeks for s in pool[:, 2])


# ============================================================================================== T-592 put-write ==

def test_rolling_beta_uses_prior_intervals_only():
    rng = np.random.default_rng(5)
    gx = rng.normal(0, 0.01, 400)
    ex = 0.5 * gx + rng.normal(0, 0.002, 400)
    b = M.rolling_beta(ex, gx, 60)
    k = 200
    ex2, gx2 = ex.copy(), gx.copy()
    ex2[k:] += 0.05; gx2[k:] *= -3
    b2 = M.rolling_beta(ex2, gx2, 60)
    assert _same(b[:k + 1], b2[:k + 1]) and not _same(b[k + 1:], b2[k + 1:])
    assert np.isnan(b[:60]).all() and b[61] == pytest.approx(np.polyfit(gx[1:61], ex[1:61], 1)[0])


def _put_setup(seed=6, start="2012-01-03", end="2013-12-31"):
    days = _sessions(start, end)
    lv = _walk(len(days), seed, 0.006)
    g = _walk(len(days), seed + 1, 0.01)
    idx = {"close": dict(zip(days, lv)), "backtest": {d: False for d in days}}
    gspc = dict(zip(days, g))
    bills = BW.Bills({d: 0.1 for d in _bdays(800, "2011-06-01")})
    return days, idx, gspc, bills


def test_put_interval_labels_rolls_dte_and_holidays():
    days, idx, gspc, bills = _put_setup()
    iv = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=False)
    d0, d1 = np.array(iv["d0"]), np.array(iv["d1"])
    k = list(d0).index("2012-03-09")                                         # Fri -> Mon 12 March, 6 days before the 16 March roll
    assert iv["weekend"][k] and iv["short_dte"][k]
    k = list(d1).index("2012-03-16")                                         # Thu -> roll Friday
    assert iv["roll_end"][k] and iv["weekday"][k]
    k = list(d0).index("2012-03-02")                                         # Fri -> Mon, 14 days before expiry at its end: kept
    assert iv["weekend"][k] and not iv["excluded"][k]
    k = list(d1).index("2012-11-21")                                         # Tue -> Wed before Thanksgiving: next to a closure
    assert iv["hol_adj"][k]
    k = list(d0).index("2012-11-21")                                         # Wed -> Fri spans Thanksgiving: neither type
    assert iv["spans"][k] and not iv["weekend"][k] and not iv["weekday"][k]
    w = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=True)
    k = list(np.array(w["d1"])).index("2012-03-09")                          # weekly: every Friday is a roll
    assert w["roll_end"][k] and not w["short_dte"].any()


def test_roll_day_interval_is_excluded_on_monthly_indices_only():
    days, idx, gspc, bills = _put_setup()
    iv = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=False)
    k = list(iv["d0"]).index("2012-03-16")                                   # Fri -> Mon starting on the 16 March roll
    assert iv["weekend"][k] and iv["roll_start"][k] and not iv["short_dte"][k] and not iv["roll_end"][k]
    assert iv["excluded"][k] and not iv["excluded_end_only"][k]              # the roll-day clause alone removes it
    assert (iv["excluded"] == (iv["excluded_end_only"] | iv["roll_start"])).all()
    t = M.weekend_test(iv, "2012-01-03", "2013-12-31", None, pvals=False)
    te = M.weekend_test(iv, "2012-01-03", "2013-12-31", None, pvals=False, excl="excluded_end_only")
    assert te["n_weekend"] - t["n_weekend"] == t["n_excluded"]["roll_start_only"] > 0
    w = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=True)
    k = list(w["d0"]).index("2012-03-09")                                    # WPUT: the first weekend of each weekly put is kept
    assert w["roll_start"][k] and w["weekend"][k] and not w["excluded"][k]
    assert (w["excluded"] == w["excluded_end_only"]).all()


def test_roll_exclusions_do_not_depend_on_marks_after_the_interval():
    days, idx, gspc, bills = _put_setup()
    iv = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=False)
    k = 150
    cut = iv["d1"][k]
    idx2 = {"close": {d: (v * 0.5 if d > cut else v) for d, v in idx["close"].items()}, "backtest": idx["backtest"]}
    iv2 = M.put_intervals(idx2, gspc, bills, "2012-01-03", weekly=False)
    for key in ("roll_start", "roll_end", "short_dte", "hol_adj", "excluded", "excluded_end_only"):
        assert (iv[key][:k + 1] == iv2[key][:k + 1]).all(), key


def test_put_residual_ignores_marks_after_the_interval():
    days, idx, gspc, bills = _put_setup()
    iv = M.put_intervals(idx, gspc, bills, "2012-01-03", weekly=False)
    k = 150
    cut = iv["d1"][k]
    idx2 = {"close": {d: (v * 1.3 if d > cut else v) for d, v in idx["close"].items()}, "backtest": idx["backtest"]}
    g2 = {d: (v * 0.7 if d > cut else v) for d, v in gspc.items()}
    iv2 = M.put_intervals(idx2, g2, bills, "2012-01-03", weekly=False)
    assert _same(iv["resid"][:k + 1], iv2["resid"][:k + 1]) and _same(iv["beta"][:k + 1], iv2["beta"][:k + 1])


def test_backtested_marks_never_enter():
    days, idx, gspc, bills = _put_setup()
    bt = {d: d < "2012-06-01" for d in days}
    iv = M.put_intervals({"close": idx["close"], "backtest": bt}, gspc, bills, "2012-01-03", weekly=False)
    assert min(iv["d0"]) >= "2012-06-01"


def test_weekend_linearised_series_mean_is_D():
    days, idx, gspc, bills = _put_setup(7, "2008-01-02", "2013-12-31")
    iv = M.put_intervals(idx, gspc, bills, "2008-01-02", weekly=False)
    t = M.weekend_test(iv, "2008-01-02", "2013-12-31", None, pvals=False)
    assert t["D"] == pytest.approx(t["mean_weekend"] - 1.5 * t["mean_weekday"])
    assert t["n_weekend"] > 100 and t["n_weekday"] > 300


# ================================================================================================= T-582 HVIX ==

def test_vix_spike_at_t_ignores_everything_after_t():
    days = _bdays(600)
    rng = np.random.default_rng(8)
    vix = {d: float(v) for d, v in zip(days, 15 + 4 * rng.random(600))}
    vix[days[300]] = 30.0
    s = M.vix_spikes(vix)
    assert s[days[300]][0]
    v2 = {d: (v * 3 if d > days[300] else v) for d, v in vix.items()}
    s2 = M.vix_spikes(v2)
    assert all(s[d] == s2[d] for d in days[1:301])
    m = 0.0
    for d in days[:300]:
        m = 0.7 * vix[d] + 0.3 * m
    assert s[days[300]][1] == pytest.approx(30.0 - m)


def test_expanding_deciles_use_past_returns_only():
    rng = np.random.default_rng(9)
    r = rng.normal(0, 0.01, 1000)
    d = M.expanding_deciles(r, 250)
    r2 = r.copy(); r2[601:] = rng.normal(0.05, 0.1, 399)                   # every return after day 600 moved
    assert np.array_equal(d[:601], M.expanding_deciles(r2, 250)[:601])
    assert (d[:250] == -1).all() and set(d[250:]) <= set(range(10))
    k = 700
    cut = np.quantile(r[:k], np.arange(1, 10) / 10)
    assert d[k] == int(np.searchsorted(cut, r[k], side="right"))


def test_hvix_frame_signal_at_t_is_fixed_before_the_t_plus_1_open():
    days = _bdays(800, "1999-01-04")
    b = _bars(days, 10)
    rng = np.random.default_rng(11)
    vix = {d: float(v) for d, v in zip(days, 15 + 4 * rng.random(800))}
    fr = M.hvix_frame(b, M.vix_spikes(vix), dec_from="1990-01-01", dec_min=100)
    k = 500
    t = fr["i"][k]
    b2 = OHLC.Bars(b.days, b.open.copy(), b.high.copy(), b.low.copy(), b.close.copy(), b.adj.copy())
    for arr in (b2.open, b2.high, b2.low, b2.close, b2.adj):
        arr[t + 1:] *= 1.2                                                   # shock from the t+1 open on
    v2 = {d: (v * 2 if d > days[t] else v) for d, v in vix.items()}
    fr2 = M.hvix_frame(b2, M.vix_spikes(v2), dec_from="1990-01-01", dec_min=100)
    for key in ("spike", "vex", "dec", "ibs", "c2c"):
        assert _same(np.asarray(fr[key][:k + 1], float), np.asarray(fr2[key][:k + 1], float)), key
    assert fr["y"][k] == pytest.approx(b.close[t + 1] / b.open[t + 1] - 1)


def test_matched_diff_linearised_series_mean_is_the_difference():
    rng = np.random.default_rng(12)
    n = 3000
    y = rng.normal(0, 0.01, n); dec = rng.integers(0, 10, n); ev = rng.random(n) < 0.03
    md = M.matched_diff(y, ev, dec)
    c = {k: y[~ev & (dec == k)].mean() for k in range(10)}
    assert md["diff"] == pytest.approx(np.mean([y[i] - c[dec[i]] for i in np.where(ev)[0]]))
    assert md["z"].mean() == pytest.approx(md["diff"])


def test_stationary_index_runs_and_cluster_bootstrap():
    rng = np.random.default_rng(21)
    idx = M.stationary_idx(rng, 100, 3.0, 400)
    step = (idx[:, 1:] - idx[:, :-1]) % 100
    cont = step == 1
    assert idx.min() >= 0 and idx.max() < 100
    assert 0.55 < cont.mean() < 0.78                                         # P(continue) = 1 - 1/3, plus chance hits
    months = np.repeat([f"{2018 + k // 12}-{k % 12 + 1:02d}" for k in range(60)], 20)
    x = rng.normal(0.0, 1.0, months.size)
    pg, pl = M.stationary_cluster_boot(x + 0.5, months, 1000, 0, 3.0)
    assert pg < 0.01 and pl > 0.99
    pg0, pl0 = M.stationary_cluster_boot(x[:100], months[:100], 1000, 0, 3.0)   # 5 clusters: below the 8-cluster minimum
    assert pg0 is None and pl0 is None


def test_declustering_uses_past_events_only():
    fr = {"spike": np.array([1, 1, 0, 0, 0, 0, 0, 1, 0, 1], bool), "i": np.arange(10)}
    # 1 follows 0 within 5 sessions; 7 is 6 sessions after the last earlier event (1); 9 follows 7 within 5
    assert M.declustered(fr, 5).tolist() == [True, False, False, False, False, False, False, True, False, False]
    fr2 = {"spike": np.array([1, 0, 0, 0, 0, 0, 0, 1], bool), "i": np.arange(8)}
    assert M.declustered(fr2, 5).tolist() == [True, False, False, False, False, False, False, True]


# ============================================================================================ T-581 VIX build-up ==

def test_buildup_z_uses_closes_through_t_minus_2():
    rng = np.random.default_rng(13)
    v = 15 + np.cumsum(rng.normal(0, 0.5, 900))
    z = M.buildup_z(v, 3)
    t = 600
    v2 = v.copy(); v2[t - 1:] += rng.normal(0, 5, v.size - t + 1)           # the VIX close of t-1 and later moved
    assert _same(z[:t + 1], M.buildup_z(v2, 3)[:t + 1])
    v3 = v.copy(); v3[t - 2] += 3.0
    assert M.buildup_z(v3, 3)[t] != pytest.approx(z[t])
    ch = v[3:] - v[:-3]                                                      # ch index j -> change ending at j + 3
    sd = np.std(ch[t - 2 - 249 - 3:t - 2 - 3 + 1], ddof=1)
    assert z[t] == pytest.approx((v[t - 2] - v[t - 5]) / sd)


def test_buildup_frame_controls_are_known_at_the_t_minus_1_close():
    days = _bdays(800)
    b = _bars(days, 14)
    rng = np.random.default_rng(15)
    vix = {d: float(v) for d, v in zip(days, 15 + 4 * rng.random(800))}
    fr = M.buildup_frame(b, vix, {days[500]}, {days[400]})
    t = 500
    b2 = OHLC.Bars(b.days, b.open.copy(), b.high.copy(), b.low.copy(), b.close.copy(), b.adj.copy())
    for arr in (b2.open, b2.high, b2.low, b2.close, b2.adj):
        arr[t:] *= 0.8                                                       # the statement session itself and later
    fr2 = M.buildup_frame(b2, {d: (x * 2 if d >= days[t - 1] else x) for d, x in vix.items()}, {days[500]}, {days[400]})
    for key in ("z3", "z6", "c1", "c2"):
        assert _same(fr[key][:t + 1], fr2[key][:t + 1]), key
    assert fr["fomc"][t] == 1 and fr["nfp"][400] == 1
    assert fr["c1"][t] == pytest.approx(b.adj[t - 2] / b.adj[t - 5] - 1)


def test_tercile_cutoffs_use_earlier_events_only():
    days = _bdays(3000, "1994-01-03")
    n = len(days)
    rng = np.random.default_rng(16)
    ev = np.zeros(n); ev[::40] = 1
    fr = {"day": np.array(days), "fomc": ev, "z3": rng.normal(size=n), "cc": rng.normal(0, 0.01, n)}
    a = M.tercile_spread(fr, ("2000-01-01", "2002-12-31"))
    fr2 = dict(fr, z3=fr["z3"].copy())
    fr2["z3"][np.array(days) > "2002-12-31"] = 99.0                          # later events cannot move earlier terciles
    assert M.tercile_spread(fr2, ("2000-01-01", "2002-12-31")) == a
    assert a["spread_net"] == pytest.approx(a["mean_top"] - a["mean_bottom"] - 2 * M.T581_COST)


def test_hac_and_block_bootstrap_recover_an_interaction():
    rng = np.random.default_rng(17)
    n = 1500
    z = rng.normal(size=n); D = (rng.random(n) < 0.05).astype(float)
    y = 0.001 * z * D * 5 + rng.normal(0, 0.002, n)
    X = np.column_stack([z, D, z * D])
    r = M.coef_test(y, X, 2, 5, 21, n_boot=300)
    assert r["coef"] > 0 and r["hac_p_greater"] < 0.01 and r["boot_p_greater"] < 0.05


# =========================================================================================== T-583 FOMC carry ==

def _book(months, ccys, seed=18):
    rng = np.random.default_rng(seed)
    out = {}
    for k, c in enumerate(ccys):
        out[c] = [(m, float(k + rng.normal(0, 0.1)), f"{m}-28T00:00:00+00:00") for m in months]
    return out


def test_rank_uses_month_m_minus_1_rates_known_at_the_rank_day():
    days = _bdays(300, "2015-01-02")
    months = sorted({d[:7] for d in days} | {"2014-12"})
    book = _book(months, M.G10)
    sched = M.rank_schedule(days, book)
    rd, basket, stale = [s for s in sched if s[0][:7] == "2015-05"][0]
    lv = {c: [x for m, x, _ in book[c] if m == "2015-04"][0] for c in M.G10}
    assert basket == tuple(sorted(sorted(lv, key=lambda c: -lv[c])[:3])) and not stale
    book2 = {c: [(m, (x + (50 if c == "EUR" and m >= "2015-05" else 0)), av) for m, x, av in l] for c, l in book.items()}
    assert [s for s in M.rank_schedule(days, book2) if s[0][:7] == "2015-05"][0][1] == basket   # May's own print not used
    book3 = {c: [(m, x, av) if not (c == "EUR" and m == "2015-04") else (m, x, "2015-06-15T00:00:00+00:00") for m, x, av in l]
             for c, l in book.items()}
    rd3, b3, st3 = [s for s in M.rank_schedule(days, book3) if s[0][:7] == "2015-05"][0]
    assert "EUR" in st3                                                     # a print not yet out: the earlier one, flagged stale


def test_rate_publication_gate_ignores_the_own_month_stamp():
    assert M.rate_available("2015-04", "2015-04-28T00:00:00+00:00") == "2015-05-15"   # the stamp precedes the month's end
    assert M.rate_available("2015-12", "2015-12-28T00:00:00+00:00") == "2016-01-15"
    assert M.rate_available("2026-01", "2026-03-02T00:00:00+00:00") == "2026-03-02"   # a later stamp wins
    days = _bdays(300, "2015-01-02")
    months = sorted({d[:7] for d in days} | {"2014-12"})
    book = _book(months, M.G10)                                             # stamped on the 28th of their own month
    late = {c: [(m, x, av) if not (c == "EUR" and m == "2015-04") else (m, x, "2015-04-28T00:00:00+00:00") for m, x, av in l]
            for c, l in book.items()}
    rd, basket, stale = [s for s in M.rank_schedule(days, late) if s[0][:7] == "2015-05"][0]
    assert "EUR" not in stale                                               # published 2015-05-15, before the May rank day
    early = [d for d in days if d[:7] == "2015-05" and d < "2015-05-15"]
    assert M.rate_available("2015-04", "2015-04-28") > early[-1]            # a mid-May rank could not have used it


def test_carry_window_fixed_at_noon_t_minus_1():
    days = _bdays(400, "2015-01-02")
    rng = np.random.default_rng(19)
    px = {c: np.exp(np.cumsum(rng.normal(0, 0.005, len(days)))) for c in M.G10}
    sched = M.rank_schedule(days, _book(sorted({d[:7] for d in days} | {"2014-12"}), M.G10))
    fomc = [days[100], days[160], days[250]]
    cs = M.carry_series(days, px, sched, fomc, "2015-01-01", "2016-12-31")
    w = cs["windows"][1]
    i = days.index(w["t"])
    b = w["basket"]
    g = np.mean([np.log(px[c][i + 1] / px[c][i - 1]) for c in b])
    assert w["gross"] == pytest.approx(g) and w["net"] == pytest.approx(g - M.round_trip(b))
    px2 = {c: v.copy() for c, v in px.items()}
    for c in px2:
        px2[c][i + 2:] *= 1.5
    cs2 = M.carry_series(days, px2, sched, fomc, "2015-01-01", "2016-12-31")
    assert cs2["windows"][1]["net"] == pytest.approx(w["net"])
    assert not cs["f"][cs["day"] == days[i + 2]].any()                       # the day after t+1 is a baseline day
    d = 2.0 * CAL.flag_diff_series(cs["x"], cs["f"])
    s = M.carry_stat(cs)
    assert d.mean() == pytest.approx(s["diff_net"])


def test_round_trip_costs():
    assert M.round_trip(("AUD", "NZD", "CAD")) == pytest.approx(3e-4)
    assert M.round_trip(("NOK", "SEK", "AUD")) == pytest.approx(2 * (4 + 4 + 1.5) / 3 * 1e-4)


# ============================================================================================= wiring / missing ==

class _NoArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, *a, **k):
        return []


@pytest.mark.parametrize("name", list(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    stat, n, verdict, reason = M.HARNESSES[name](_NoArchive())
    assert verdict == "inconclusive" and n == 0 and "missing" in reason


def test_theory_map_covers_the_group():
    assert set(M.THEORY_MAP) == {"T-589", "T-592", "T-582", "T-581", "T-583"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
