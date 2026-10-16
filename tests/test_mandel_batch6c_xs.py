"""Batch-6c cross-sectional harnesses (T-309 52-week high, T-476 return seasonality, T-313 commodity-ETF momentum, T-482
frog in the pan, T-471 long-horizon country reversal, T-319 weekly ETF reversal, T-462 reversal and VIX) on synthetic data
only: for every core function a planted effect passes and a null does not; the panel calendars, book arithmetic
(drift-adjusted turnover, borrow, funded vs zero-investment), rank weights, overlapping cohorts, permutation null,
seasonal scores (earlier years only), information discreteness, the partial-family DSR bound, the HAC mean and the VIX
tool are checked directly; every harness runs JSON-safe on a fake archive, thin data and missing bundles give
inconclusive. No archive, no network."""

import json
import math
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_xs as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "N_PERM", 200)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


BILLS = m.Bills({"1990-01-02": 2.0})


def _month_bounds(days):
    first, last = {}, {}
    for i, d in enumerate(days):
        first.setdefault(d[:7], i)
        last[d[:7]] = i
    return sorted(last), first, last


def rank_drift(score, k, a, long_high=True):
    """+a on the k best scores, -a on the k worst (NaN scores ignored)."""
    d = np.zeros(score.size)
    idx = np.flatnonzero(np.isfinite(score))
    if idx.size < 2 * k or k < 1:
        return d
    o = idx[np.argsort(-score[idx] if long_high else score[idx], kind="stable")]
    d[o[:k]] = a
    d[o[-k:]] = -a
    return d


def sim_monthly(n, days, drift_fn, seed=0, vol=0.01, hold="ex"):
    """Daily log returns (noise); at every month-end decision drift_fn(L, me, t, r) gives each asset a per-day drift
    over the decision's hold (fill to fill for 'ex', month-end to month-end for 'me'), computed on the history only."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0002, vol, (n, len(days)))
    months, first, last = _month_bounds(days)
    for t in range(len(months) - 2):
        me = last[months[t]]
        lo, hi = (first[months[t + 1]] + 1, first[months[t + 2]]) if hold == "ex" else (me + 1, last[months[t + 1]])
        L = np.cumsum(r[:, :me + 1], axis=1)
        dr = drift_fn(L, me, t, r)
        if dr is not None:
            r[:, lo:hi + 1] += dr[:, None]
    return np.exp(np.cumsum(r, axis=1))


def series_of(syms, days, P):
    return {s: (days, P[i]) for i, s in enumerate(syms)}


def sim_weekly(n, days, drift_fn, seed=0, vol=0.01):
    """Daily log returns; at every week end e_w, drift_fn(r, e_w) gives each asset a per-day drift over days e_w+1..e_w+1."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, vol, (n, len(days)))
    e = m.week_ends(days)
    for w in range(len(e) - 1):
        dr = drift_fn(r, int(e[w]))
        if dr is not None:
            r[:, e[w] + 1:e[w + 1] + 1] += dr[:, None]
    return np.exp(np.cumsum(r, axis=1))


def syn_vix(days, seed=3):
    rng = np.random.default_rng(seed)
    v = 20 + 9 * np.sin(2 * math.pi * np.arange(len(days)) / 380) + rng.normal(0, 1.0, len(days))
    return {d: float(max(v[i], 9.0)) for i, d in enumerate(days)}


# ------------------------------------------------------------------------------------------- arithmetic --

def test_book_zero_investment_turnover_borrow_and_costs():
    W = np.array([[0.5, -0.5], [0.5, -0.5]])
    R = np.array([[0.10, 0.00], [0.0, 0.0]])
    b = m.book(W, R, np.array([0.001, 0.001]), np.array([0.0, 0.0365]), np.array([10.0, 10.0]))
    # period 1: gross 5%, borrow 0.5 x 3.65% x 10/365 = 0.05%, entry turnover 1 -> cost 0.1%
    assert b["gross"][0] == pytest.approx(0.05)
    assert b["borrow"][0] == pytest.approx(0.0005)
    assert b["net"][0] == pytest.approx((1 - 0.001) * (1 + 0.05 - 0.0005) - 1)
    # period 2: drifted weights 0.55/1.0495 and -0.5/1.0495; rebalancing back to +-0.5
    pre = 0.05 - 0.0005
    to = abs(0.5 - 0.55 / (1 + pre)) + abs(-0.5 + 0.5 / (1 + pre))
    assert b["turnover"][1] == pytest.approx(to)
    assert b["cost"][1] == pytest.approx(0.001 * to)


def test_book_funded_long_only_earns_cash_and_rejects_a_held_name_without_a_return():
    W = np.array([[0.5, 0.0]])
    b = m.book(W, np.array([[0.02, np.nan]]), np.zeros(2), rf=np.array([0.01]))
    assert b["gross"][0] == pytest.approx(0.01 + 0.5 * (0.02 - 0.01))
    with pytest.raises(ValueError):
        m.book(np.array([[0.5, 0.5]]), np.array([[0.02, np.nan]]), np.zeros(2))


def test_rank_weights_overlap_and_ties():
    s = np.array([3.0, 1.0, 2.0, 2.0, np.nan, 0.0])
    el = np.array([True, True, True, True, True, False])
    w = m.rank_weights(s, el, 1, long_high=True)
    assert w.tolist() == [1.0, -1.0, 0.0, 0.0, 0.0, 0.0]               # NaN and ineligible names never held
    w = m.rank_weights(s, el, 1, long_high=False)
    assert w[1] == 1.0 and w[0] == -1.0
    t = m.rank_weights(np.array([1.0, 1.0, 0.0]), np.ones(3, bool), 1, True, short=False)
    assert t.tolist() == [1.0, 0.0, 0.0]                                  # stable order on a tie
    assert m.rank_weights(s, el, 3, True).sum() == 0 and not m.rank_weights(s, el, 3, True).any()
    C = np.arange(12, dtype=float).reshape(6, 2)
    O = m.overlap(C, 3, t0=1)
    assert not O[0].any() and O[1].tolist() == C[1].tolist() and O[5].tolist() == C[3:6].mean(axis=0).tolist()


def test_perm_null_is_centred_and_exact_when_names_are_identical():
    rng = np.random.default_rng(1)
    R = rng.normal(0, 0.05, (200, 12))
    el = np.ones_like(R, bool)
    null = m.perm_null(R, el, 4, 400)
    assert abs(null.mean()) < 0.002 and null.std() < 0.01
    same = np.tile(rng.normal(0, 0.05, (200, 1)), (1, 12))
    assert np.allclose(m.perm_null(same, el, 4, 50), 0.0)
    (name, ok, dec), info = m.perm_row(0.01, 0.0, null, "x")
    assert ok and not dec and info["p"] < 0.05


def test_month_panel_own_grids_fill_to_fill_and_crypto_calendar():
    days = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28", "2020-03-02", "2020-03-31", "2020-04-01"]
    adj = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    cd = cdays("2020-01-30", "2020-04-01")
    ca = np.arange(1, len(cd) + 1, dtype=float)
    PN = m.month_panel({"E": (days, adj), "C": (cd, ca)}, "2020-01", "2020-03")
    t = PN["pos"]["2020-01"]
    assert PN["PME"][0, t] == 2.0 and PN["PEX"][0, t] == 3.0             # decision 01-31, fill 02-03
    assert PN["R_ex"][0, t] == pytest.approx(5.0 / 3.0 - 1)               # hold 02-03 -> 03-02
    assert PN["R_me"][0, t] == pytest.approx(4.0 / 2.0 - 1)
    i = PN["syms"].index("C")
    assert cd[PN["JME"][i, t]] == "2020-01-31" and PN["PEX"][i, t] == ca[cd.index("2020-02-01")]
    assert PN["ex_day"][t] == "2020-02-01"                                # union calendar includes the crypto days


def test_daily_panel_majority_calendar_forward_fill_and_week_ends():
    a = ["2021-01-04", "2021-01-05", "2021-01-06", "2021-01-07", "2021-01-08", "2021-01-09"]   # a stray Saturday bar
    b = ["2021-01-04", "2021-01-05", "2021-01-07", "2021-01-08"]                                # b misses 01-06
    c = ["2021-01-04", "2021-01-05", "2021-01-06", "2021-01-07", "2021-01-08"]
    s = {"A": (a, np.arange(1.0, 7.0)), "B": (b, np.array([10.0, 11.0, 12.0, 13.0])), "C": (c, np.ones(5))}
    dp = m.daily_panel(s, "2021-01-01", "2021-12-31")
    assert dp["days"] == a[:5]                                            # 01-09 has 1 of 3 listed names: dropped
    j = dp["syms"].index("B")
    assert dp["P"][2, j] == 11.0 and not dp["real"][2, j]                 # forward-filled, flagged as no bar
    hol = ["2021-03-29", "2021-03-30", "2021-03-31", "2021-04-01", "2021-04-05"]          # Good Friday 04-02
    assert [hol[i] for i in m.week_ends(hol)] == ["2021-04-01", "2021-04-05"]


def test_seasonal_scores_use_only_earlier_years():
    days = bdays("1998-12-01", "2010-12-31")
    rng = np.random.default_rng(4)
    P = np.exp(np.cumsum(rng.normal(0, 0.01, (2, len(days))), axis=1))
    PN = m.month_panel(series_of(["A", "B"], days, P), "1990-01", "2011-01")
    dec = np.array([PN["pos"]["2005-12"]])                                # decision for January 2006
    s0 = m.seasonal_scores(PN, dec, 20)
    P2 = P.copy()
    jan06 = [i for i, d in enumerate(days) if d[:7] == "2006-01"]
    P2[:, jan06[0]:] *= 1.5                                               # move January 2006 and everything after
    PN2 = m.month_panel(series_of(["A", "B"], days, P2), "1990-01", "2011-01")
    assert np.allclose(m.seasonal_scores(PN2, dec, 20), s0)
    jan = [PN["R_me"][0, PN["pos"][f"{y}-01"] - 1] for y in range(1999, 2006)]
    assert s0[0, 0] == pytest.approx(np.mean(jan))                       # 7 earlier Januaries
    assert np.isnan(m.seasonal_scores(PN, np.array([PN["pos"]["2002-12"]]), 20, min_years=5)[0, 0])   # only 4 Januaries


def test_info_discreteness():
    adj = np.array([100.0, 101.0, 102.0, 101.5, 103.0])                  # 3 up days, 1 down, PRET > 0
    pret, idv = m.info_discreteness(adj, 0, 4)
    assert pret == pytest.approx(0.03) and idv == pytest.approx(0.25 - 0.75)
    pret, idv = m.info_discreteness(adj[::-1], 0, 4)                      # PRET < 0: the sign flips
    assert pret < 0 and idv == pytest.approx(-(0.75 - 0.25))


def test_dsr_bound_is_never_below_any_completion_and_fails_only_when_the_bound_does():
    rng = np.random.default_rng(5)
    x = rng.normal(0.004, 0.01, 500)
    known = [float(v) for v in rng.normal(0.1, 0.05, 8)]
    (name, ok, dec), info = m.dsr_bound(x, known, 18, "t")
    for _ in range(50):
        full = known + [float(v) for v in rng.normal(0.1, rng.uniform(0.001, 0.3), 10)]
        d = m.family_dsr(x, full, 18)["dsr"]
        assert d <= info["dsr_upper_bound"] + 1e-12
    assert ok is None and "not archived" in name
    weak = rng.normal(0.0, 0.01, 500)
    (name, ok, dec), info = m.dsr_bound(weak, known, 18, "t")
    assert ok is False and "fails whatever" in name
    (name, ok, dec), info = m.dsr_bound(x, known + known[:2] * 5, 18, "t")
    assert info["complete"] and ok is not None


def test_hac_mean_and_vix_tool():
    rng = np.random.default_rng(6)
    x = rng.normal(0.1, 1.0, 400)
    h = m.hac_mean(x, lag=0)
    assert h["t"] == pytest.approx(x.mean() / (x.std(ddof=0) / math.sqrt(400)))
    assert h["p"] == pytest.approx(1 - m._N.cdf(h["t"]))
    days = bdays("2020-01-01", "2021-12-31")
    vix = {d: float(i) for i, d in enumerate(days) if i % 7}               # some days without a print
    vt = m.VixTool(vix, days)
    q = 400
    assert vt.level(q) == (q if q % 7 else q - 1)
    vals = [vix[d] for d in sorted(vix) if d <= days[q]][-252:]
    assert vt.trailing(q, 0.5) == pytest.approx(np.quantile(vals, 0.5))
    assert math.isnan(vt.trailing(10, 0.5))


def test_weekly_book_signal_ends_at_q_and_the_hold_runs_week_end_to_week_end():
    days = bdays("2015-01-01", "2016-12-31")
    rng = np.random.default_rng(7)
    P = np.exp(np.cumsum(rng.normal(0, 0.01, (10, len(days))), axis=1))
    s = {f"A{i}": (days, P[i], P[i]) for i in range(10)}
    dp = m.daily_panel(s, "2015-01-01", "2016-12-31")
    e = m.week_ends(dp["days"])
    ws = np.arange(20, 60)
    b = m.weekly_book(dp, e, ws, 5, 1, cost=0.0)
    P2 = P.copy()
    w0 = ws[0]
    P2[:, e[w0]] *= np.linspace(0.8, 1.2, 10)                             # change only the decision-day close
    dp2 = m.daily_panel({f"A{i}": (days, P2[i], P2[i]) for i in range(10)}, "2015-01-01", "2016-12-31")
    b2 = m.weekly_book(dp2, e, ws, 5, 1, cost=0.0)
    assert np.allclose(b["W"][0], b2["W"][0])                             # skip-a-day: close t is not in the signal
    q = e[w0] - 1
    ret = P[:, q] / P[:, q - 5] - 1
    assert b["W"][0][np.argmin(ret)] == pytest.approx(0.5) and b["W"][0][np.argmax(ret)] == pytest.approx(-0.5)
    R = P[:, e[w0 + 1]] / P[:, e[w0]] - 1
    assert b["gross"][0] == pytest.approx(float(b["W"][0] @ R))
    bv = m.weekly_book(dp, e, ws, 5, 1, cost=0.0, vol_target=0.10)
    x = np.nan_to_num(dp["DR"][q - 59:q + 1]) @ b["W"][0]
    assert bv["scale"][0] == pytest.approx(0.10 / (x.std(ddof=1) * math.sqrt(252)))


# ------------------------------------------------------------------------------------------- T-309 --

U19T = [f"E{i:02d}" for i in range(19)]
DAYS02 = bdays("2002-01-02")


def _near_drift(a):
    def fn(L, me, t, r):
        if me < 251:
            return None
        P = np.exp(L)
        return rank_drift(P[:, me] / P[:, me - 251:me + 1].max(axis=1), 6, a)
    return fn


def test_t309_planted_nearness_passes():
    P = sim_monthly(19, DAYS02, _near_drift(0.002), seed=11)
    j = m.fifty_two_week_high(series_of(U19T, DAYS02, P), BILLS)
    assert j["n"] >= 250 and j["verdict"] == "supported", j["why"]
    assert j["perm"]["p"] < 0.05 and j["dsr"]["dsr"] > 0.95


def test_t309_null_does_not_pass():
    P = sim_monthly(19, DAYS02, lambda *a: None, seed=12)
    j = m.fifty_two_week_high(series_of(U19T, DAYS02, P), BILLS)
    assert j["verdict"] != "supported"


def test_t309_family_and_late_joiners():
    assert len(m.T309_FAMILY) == 8 and m.T309_PRIMARY in m.T309_FAMILY
    P = sim_monthly(19, DAYS02, lambda *a: None, seed=13)
    s = series_of(U19T, DAYS02, P)
    late = bdays("2006-02-06")
    s["E18"] = (late, np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, len(late)))))
    j = m.fifty_two_week_high(s, BILLS)
    ready = late[251][:7]                                                 # the month of its 252nd session
    assert j["names_first"] == 18 and j["all_names_from"] == m._month_add(ready, 1)


# ------------------------------------------------------------------------------------------- T-476 --

U14T = [f"S{i:02d}" for i in range(14)]
DAYS98 = bdays("1998-12-01")


def _seasonal_prices(a, seed):
    rng = np.random.default_rng(seed)
    mu = rng.choice([-a, a], size=(14, 12))
    r = rng.normal(0.0002, 0.01, (14, len(DAYS98)))
    mo = np.array([int(d[5:7]) - 1 for d in DAYS98])
    r += mu[:, mo]
    return np.exp(np.cumsum(r, axis=1))


def test_t476_planted_seasonality_passes():
    j = m.return_seasonality(series_of(U14T, DAYS98, _seasonal_prices(0.003, 21)), BILLS)
    assert j["n"] >= 260 and j["verdict"] == "supported", j["why"]


def test_t476_null_does_not_pass():
    j = m.return_seasonality(series_of(U14T, DAYS98, _seasonal_prices(0.0, 22)), BILLS)
    assert j["verdict"] != "supported"
    assert len(m.T476_FAMILY) == 8


# ------------------------------------------------------------------------------------------- T-313 --

U13T = list(m.U13)
DAYS10 = bdays("2010-01-04")


def _mom_drift(a, k=4):
    def fn(L, me, t, r):
        months, first, last = _month_bounds(DAYS10)
        if t < 12:
            return None
        return rank_drift(L[:, last[months[t - 1]]] - L[:, last[months[t - 12]]], k, a)
    return fn


def test_t313_planted_momentum_passes_at_both_cost_ends():
    P = sim_monthly(13, DAYS10, _mom_drift(0.002), seed=31)
    j = m.commodity_momentum(series_of(U13T, DAYS10, P), BILLS, bench=(DAYS10, P[0]))
    assert j["n"] >= 160 and j["verdict"] == "supported", j["why"]
    assert j["means"]["low"] > j["means"]["high"] > 0 and j["k"] == 4
    assert set(j["subs"]["high"]) == {"2013-2019", "2020-2026"}


def test_t313_null_does_not_pass_and_family_is_12():
    P = sim_monthly(13, DAYS10, lambda *a: None, seed=32)
    j = m.commodity_momentum(series_of(U13T, DAYS10, P), BILLS)
    assert j["verdict"] != "supported"
    assert len(m.T313_FAMILY) == 12


def test_t313_cost_readings_disagreeing_is_undecided():
    rows = [("low", True, False), ("high", False, False)]
    name, ok, dec = m.all_constructions(rows, "x")
    assert ok is None and "disagree" in name


def test_zero_volume_spikes_flag_only_isolated_zero_volume_prints():
    # the CPER pattern: 2014-12-03 flat at zero volume (legitimate), 2014-12-04 a bogus 13.05 print at zero volume
    close = [19.42, 19.52, 19.52, 13.05, 19.56, 19.50]
    vol = [600, 1200, 0, 0, 200, 200]
    assert m.zero_volume_spikes(close, vol) == [3]
    assert m.zero_volume_spikes(close, [600, 1200, 0, 500, 200, 200]) == []           # a traded print is a real price
    assert m.zero_volume_spikes(close, [600, 1200, 0, None, 200, 200]) == []          # unknown volume is never flagged
    assert m.zero_volume_spikes([20.0, 16.0, 12.0, 12.1], [100, 0, 100, 100]) == []   # a move (neighbours on both sides)
    assert m.zero_volume_spikes([20.0, 19.0, 19.1, 19.2], [100, 0, 100, 100]) == []   # within 15% of the neighbours
    assert m.zero_volume_spikes([13.0, 19.5, 19.6], [0, 100, 0]) == []                # end bars have one neighbour
    days, adj = ["d0", "d1", "d2"], np.array([1.0, 0.6, 1.1])
    out = m.patch_bars((days, adj, adj.copy()), ["d1"])
    assert list(out[1]) == [1.0, 1.0, 1.1] and list(out[2]) == [1.0, 1.0, 1.1] and adj[1] == 0.6   # copy, not in place


def _t313_archive(bogus: bool):
    """U13 + DBC + DTB3 with volumes; CPER's first session of 2015-02 (a fill date) is a zero-volume bar: at the
    previous close in the clean archive, a bogus print 30% below it otherwise."""
    dd = bdays("2010-01-04")
    b = {}
    for k, s in enumerate(list(m.U13) + ["DBC"]):
        r = np.random.default_rng(300 + k).normal(0.0002, 0.01, len(dd))
        adj = 100 * np.exp(np.cumsum(r))
        vol = np.full(len(dd), 1000.0)
        if s == "CPER":
            kb = dd.index("2015-02-02")
            adj[kb] = adj[kb - 1] * (0.7 if bogus else 1.0)
            vol[kb] = 0.0
        rows = _yahoo(dd, adj)
        for row, v in zip(rows, vol):
            row["value"]["volume"] = float(v)
        b[m.dh(s)] = rows
    b[m.DTB3_B] = [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": 2.0}} for d in bdays("2009-01-02")[::5]]
    return FakeArchive(b)


def test_t313_harness_sets_a_zero_volume_spike_fill_to_the_previous_close():
    clean, bogus = _t313_archive(False), _t313_archive(True)
    st_c, n_c, v_c, why_c = m.b6c_xs_commodity_etf_momentum(clean)
    m._CACHE.clear()
    st_b, n_b, v_b, why_b = m.b6c_xs_commodity_etf_momentum(bogus)
    assert st_c["patched_bars"] == {} and st_b["patched_bars"] == {"CPER": ["2015-02-02"]}
    assert "CPER 2015-02-02" in why_b and n_b == n_c
    assert st_b["means"] == pytest.approx(st_c["means"], abs=1e-15)      # the patched run is the clean run
    # without the screen the bogus print would move the book (the defect)
    raw = {s: m._daily(bogus, m.dh(s)) for s in m.U13}
    j = m.commodity_momentum(raw, m._bills(bogus))
    assert abs(j["means"]["low"] - st_c["means"]["low"]) > 1e-4


# ------------------------------------------------------------------------------------------- T-482 --

U12F = [f"F{i:02d}" for i in range(10)] + ["C1", "C2"]


def _frog_drift(a):
    def fn(L, me, t, r):
        months, first, last = _month_bounds(DAYS02)
        if t < 12:
            return None
        j0, j1 = last[months[t - 12]], last[months[t - 1]]
        cand = []
        for i in range(L.shape[0]):
            pret = L[i, j1] - L[i, j0]
            rr = r[i, j0 + 1:j1 + 1]
            if pret > 0:
                cand.append(((rr < 0).mean() - (rr > 0).mean(), i))
        cand.sort()
        k = len(cand) // 2
        d = np.zeros(L.shape[0])
        if k >= 1:
            for _, i in cand[:k]:
                d[i] = a
            for _, i in cand[-k:]:
                d[i] = -a
        return d
    return fn


def test_t482_planted_continuity_passes():
    P = sim_monthly(12, DAYS02, _frog_drift(0.002), seed=41)
    j = m.frog_in_pan(series_of(U12F, DAYS02, P), crypto=("C1", "C2"))
    assert j["n"] >= 250 and j["verdict"] == "supported", j["why"]
    assert j["no_crypto"]["mean"] > 0


def test_t482_null_does_not_pass():
    P = sim_monthly(12, DAYS02, lambda *a: None, seed=42)
    j = m.frog_in_pan(series_of(U12F, DAYS02, P), crypto=("C1", "C2"))
    assert j["verdict"] != "supported"
    assert len(m.T482_FAMILY) == 4


def test_boundary_shares_split_tied_names_equally():
    v = [1.0, 2.0, 2.0, 3.0]
    assert list(m.boundary_shares(v, 2, True)) == [1.0, 0.5, 0.5, 0.0]
    assert list(m.boundary_shares(v, 2, False)) == [0.0, 0.5, 0.5, 1.0]
    assert list(m.boundary_shares([1.0, 2.0, 3.0, 4.0], 2, True)) == [1.0, 1.0, 0.0, 0.0]   # no tie: whole slots
    assert list(m.boundary_shares([0.5, 0.5, 0.5], 1, False)) == pytest.approx([1 / 3] * 3)
    assert m.boundary_shares([2.0, 2.0, 1.0, 2.0, 0.0], 3, True).sum() == pytest.approx(3.0)


def test_t482_ids_tied_at_the_split_do_not_depend_on_the_panel_order():
    P = sim_monthly(12, DAYS02, lambda *a: None, seed=42)
    s = series_of(U12F, DAYS02, P)
    j = m.frog_in_pan(s, crypto=("C1", "C2"))
    jr = m.frog_in_pan({k: s[k] for k in reversed(list(s))}, crypto=("C1", "C2"))
    assert j["tie_months"] > 20                                            # equal counts over equal windows tie often
    assert jr["mean_test"]["est"] == pytest.approx(j["mean_test"]["est"], abs=1e-12)
    assert jr["no_crypto"]["mean"] == pytest.approx(j["no_crypto"]["mean"], abs=1e-12)
    assert jr["family_sharpe_ann"] == pytest.approx(j["family_sharpe_ann"], abs=1e-9)
    tr = j["tie_break_range"]                                              # the list-order tie-breaks it replaced differ
    assert abs(tr["declared"]["mean"] - tr["reversed"]["mean"]) > 1e-5
    assert jr["tie_break_range"]["declared"]["mean"] == pytest.approx(tr["reversed"]["mean"], abs=1e-12)


# ------------------------------------------------------------------------------------------- T-471 --

U12C = [f"K{i:02d}" for i in range(12)]
DAYS96 = bdays("1996-03-18")


def _rev_drift(a, k=3):
    hist = []

    def fn(L, me, t, r):
        months, first, last = _month_bounds(DAYS96)
        if t < 36:
            return None
        sig = L[:, last[months[t - 12]]] - L[:, last[months[t - 36]]]
        hist.append(m.rank_weights(sig, np.ones(sig.size, bool), k, long_high=False))
        return a * k * np.mean(hist[-12:], axis=0)
    return fn


def test_t471_planted_reversal_passes():
    P = sim_monthly(12, DAYS96, _rev_drift(0.002), seed=51, hold="me")
    j = m.country_reversal(series_of(U12C, DAYS96, P))
    assert j["n"] >= 300 and j["verdict"] == "supported", j["why"]
    assert set(j["family_mean"]) == {"36-12", "36-0", "parametric", "long-only"}


def test_t471_null_does_not_pass():
    P = sim_monthly(12, DAYS96, lambda *a: None, seed=52, hold="me")
    j = m.country_reversal(series_of(U12C, DAYS96, P))
    assert j["verdict"] != "supported"


def test_same_sign_is_literal():
    assert m.same_sign({"a": {"mean": -1.0}, "b": {"mean": -2.0}}) is True
    assert m.same_sign({"a": {"mean": 1.0}, "b": {"mean": -2.0}}) is False
    assert m.same_sign({"a": {"mean": 1.0}, "b": None}) is None


# ------------------------------------------------------------------------------------------- T-319 --

U20W = [f"W{i:02d}" for i in range(20)]
DAYS08 = bdays("2008-01-02")


def _wrev_drift(a, k=4, vix=None, days=None, a_low=None):
    vd = sorted(vix) if vix else None
    vv = np.array([vix[d] for d in vd]) if vix else None

    def fn(r, ew):
        q = ew - 1
        if q < 70:
            return None
        aa = a
        if vix is not None:
            p = vd.index(days[q])
            aa = a if (p >= 251 and vv[p] > np.quantile(vv[p - 251:p + 1], 0.5)) else a_low
        return rank_drift(r[:, q - 4:q + 1].sum(axis=1), k, aa, long_high=False)
    return fn


def test_t319_planted_reversal_passes_both_readings():
    P = sim_weekly(20, DAYS08, _wrev_drift(0.003), seed=61)
    s = {sym: (DAYS08, P[i], P[i]) for i, sym in enumerate(U20W)}
    j = m.xs_short_term_reversal(s, syn_vix(DAYS08))
    assert j["n"] >= 500 and j["verdict"] == "supported", j["why"]
    assert set(j["info"]) == {"vol-targeted", "unscaled"}


def test_t319_null_does_not_pass():
    P = sim_weekly(20, DAYS08, lambda r, e: None, seed=62)
    s = {sym: (DAYS08, P[i], P[i]) for i, sym in enumerate(U20W)}
    j = m.xs_short_term_reversal(s, syn_vix(DAYS08))
    assert j["verdict"] != "supported"
    assert len(m.T319_FAMILY) == 9 and m.T319_PRIMARY == ("1w", 1, False, "close")


# ------------------------------------------------------------------------------------------- T-462 --

U25W = [f"V{i:02d}" for i in range(25)]
DAYS05 = bdays("2005-06-01")


def _t462_series(planted, seed):
    vix = syn_vix(DAYS05, seed=seed + 1)
    fn = _wrev_drift(0.003, k=5, vix=vix, days=DAYS05, a_low=0.001) if planted else (lambda r, e: None)
    P = sim_weekly(25, DAYS05, fn, seed=seed)
    return {sym: (DAYS05, P[i], P[i]) for i, sym in enumerate(U25W)}, vix


def test_t462_planted_effect_is_capped_by_the_missing_crypto_cells_and_passes_with_a_complete_family():
    s, vix = _t462_series(True, 71)
    j = m.reversal_liquidity(s, vix)
    assert j["n"] >= 500
    crit = dict(j["criteria"])
    oos = [v for k, v in crit.items() if k.startswith("out-of-sample")][0]
    vx = [v for k, v in crit.items() if k.startswith("higher when VIX")][0]
    ds = [v for k, v in crit.items() if k.startswith("DSR")][0]
    assert oos is True and vx is True and ds is None
    assert j["verdict"] == "inconclusive", j["why"]
    j8 = m.reversal_liquidity(s, vix, n_trials=8)                        # every trial computed: the exact DSR decides
    assert j8["verdict"] == "supported", j8["why"]


def test_t462_null_does_not_pass():
    s, vix = _t462_series(False, 72)
    j = m.reversal_liquidity(s, vix)
    assert j["verdict"] == "not_supported"
    assert len(m.T462_CELLS) == 8 and m.T462_N_TRIALS == 18


def _vix_hi(vix, days):
    vd = sorted(vix)
    vv = np.array([vix[d] for d in vd])

    def hi(q):
        p = vd.index(days[q])
        return p >= 251 and vv[p] > np.quantile(vv[p - 251:p + 1], 0.5)
    return hi


def _crit(j, prefix):
    return [(k, v) for k, v in j["criteria"] if k.startswith(prefix)][0]


def test_vix_slope_and_rule12_readings():
    rng = np.random.default_rng(5)
    hi = rng.random(600) > 0.5
    net = 0.01 * hi + rng.normal(0, 0.01, 600)
    first = np.arange(600) < 300
    sv = m.vix_slope(net, hi, first)
    assert sv["n"] == 300 and sv["beta"] == pytest.approx(net[first & hi].mean() - net[first & ~hi].mean())
    assert sv["t"] > 3 and sv["p"] < 0.01
    assert m.vix_slope(net, np.ones(600, bool), first) is None                # one side empty
    name, ok, dec = m._rule12([("live", True, False), ("previous close", False, False)], "x")
    assert ok is None and "readings disagree" in name and "rule 12" in name
    assert m._rule12([("a", False, True), ("b", False, True)], "x")[1:] == (False, True)


def test_t462_vix_criterion_is_judged_on_the_out_of_sample_entries():
    # VIX-conditional reversal before 2017 only, the same reversal at every VIX level after it
    vix = syn_vix(DAYS05, seed=82)
    hi = _vix_hi(vix, DAYS05)

    def fn(r, ew):
        q = ew - 1
        if q < 70:
            return None
        aa = (0.003 if hi(q) else 0.0005) if DAYS05[q] < "2017-01-01" else 0.002
        return rank_drift(r[:, q - 4:q + 1].sum(axis=1), 5, aa, long_high=False)
    P = sim_weekly(25, DAYS05, fn, seed=81)
    j = m.reversal_liquidity({sym: (DAYS05, P[i], P[i]) for i, sym in enumerate(U25W)}, vix)
    name, ok = _crit(j, "higher when VIX")
    assert ok is False and "out of sample (2017-2026" in name, name
    full = [x["vix_full_diagnostic"] for x in j["readings"].values()]
    assert all(f["beta"] > 0 and f["p"] < 0.01 for f in full)          # the 2007-2026 reading the old harness judged
    assert _crit(j, "out-of-sample")[1] is True and j["verdict"] == "not_supported"


def test_t462_live_proxy_and_previous_close_readings_disagreeing_is_undecided():
    # the reversal keys on the fill-day (close t) return under high VIX: only the no-skip (live-proxy) cell sees it
    vix = syn_vix(DAYS05, seed=92)
    hi = _vix_hi(vix, DAYS05)

    def fn(r, ew):
        if ew < 70:
            return None
        return rank_drift(r[:, ew], 5, 0.003 if hi(ew) else 0.0, long_high=False)
    P = sim_weekly(25, DAYS05, fn, seed=91)
    j = m.reversal_liquidity({sym: (DAYS05, P[i], P[i]) for i, sym in enumerate(U25W)}, vix)
    assert j["selected"][1] == 0 and set(j["readings"]) == {m.T462_LIVE, m.T462_PREV}
    live, prev = j["readings"][m.T462_LIVE], j["readings"][m.T462_PREV]
    assert prev["cell"] == [j["selected"][0], 1, j["selected"][2]] and prev["vix_cell"][1:] == [1, False]
    assert live["oos"]["p"] < 0.05 and live["vix_oos"]["p"] < 0.05     # the live proxy alone would pass both
    assert not (prev["oos"]["mean"] > 0 and prev["oos"]["p"] < 0.05)
    for prefix in ("out-of-sample", "higher when VIX"):
        name, ok = _crit(j, prefix)
        assert ok is None and "undecided under rule 12" in name, name
    assert j["verdict"] != "supported"


def test_t462_declared_universe_matches_the_fetcher_list():
    from mandel.data.market_history import ETF60_EXTRA
    assert list(m.ETF60_EXTRA) == list(ETF60_EXTRA)
    assert len(m.ARCHIVED26) == 26 and len(m.U68) == len(set(m.U68)) == 68


# ------------------------------------------------------------------------------------- harness level --

class FakeArchive:
    def __init__(self, bundles, created="2026-10-15T08:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


_EPOCH = date(1970, 1, 1).toordinal()


def _yahoo(days, adj, crypto=False):
    hh = 0.0 if crypto else 14.5
    rows = []
    for d, a in zip(days, adj):
        o = date.fromisoformat(d).toordinal()
        t = (o - _EPOCH) * 86400 + hh * 3600
        nxt = date.fromordinal(o + 1).isoformat()
        av = f"{nxt}T{'00:00' if crypto else '14:30'}:00+00:00"
        rows.append({"available_at": av, "value": {"t": t, "open": float(a) * 0.999, "high": float(a) * 1.004,
                                                     "low": float(a) * 0.996, "close": float(a), "adjclose": float(a)}})
    return rows


def _fake_archive(start="2003-01-02", cstart="2015-01-01"):
    syms = sorted(set(m.U19) | set(m.U14) | set(m.U13) | set(m.U21) | set(m.COUNTRY21) | set(m.U30) | set(m.U68))
    b = {}
    dd = bdays(start)
    cd = cdays(cstart)
    for k, s in enumerate(syms):
        crypto = s in m.CRYPTO
        days = cd if crypto else dd
        r = np.random.default_rng(100 + k).normal(0.0003, 0.02 if crypto else 0.01, len(days))
        b[m.dh(s)] = _yahoo(days, 100 * np.exp(np.cumsum(r)), crypto)
    b[m.DTB3_B] = [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": 2.0}} for d in bdays("1990-01-02")[::5]]
    vd = bdays("1995-01-02")
    b[m.VIX_B] = [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": 15.0 + (i % 40)}} for i, d in enumerate(vd)]
    return FakeArchive(b)


def test_every_harness_runs_json_safe_on_a_fake_archive():
    a = _fake_archive()
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-309", "T-476", "T-319", "T-462", "T-471", "T-313", "T-482"}
    assert all(k.startswith("b6c_xs_") and k == k.lower() for k in m.HARNESSES)
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(a)
        json.dumps(stat, allow_nan=False)
        assert isinstance(n, int) and n > 0, name
        assert verdict in ("supported", "not_supported", "inconclusive"), name
        assert " — " in reason, name
    st, n, v, why = m.b6c_xs_reversal_vix_liquidity(a)
    assert "cmc-daily-listings" in why and st["n_trials"] == 18


def test_thin_data_is_inconclusive_never_an_error():
    a = _fake_archive(start="2025-06-02", cstart="2025-06-01")
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(a)
        json.dumps(stat, allow_nan=False)
        assert verdict == "inconclusive" and stat.get("too_short"), name
        assert " — " in reason


def test_missing_bundles_are_inconclusive():
    a = FakeArchive({})
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(a)
        assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert "missing data bundles" in reason
