"""Tests for mandel.experiments.batch13_intraday_b (T-671, T-662, T-663, T-665): point-in-time signal construction
(shocks after the decision never move the signal at the decision) and inconclusive verdicts on missing bundles."""

from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from mandel.experiments import batch13_intraday_b as M


class _Stub:
    """An archive with no bundles: every lookup raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_Stub())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_covers_harnesses():
    assert set(M.THEORY_MAP) == {"T-671", "T-662", "T-663", "T-665"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


# --------------------------------------------------------------------------------------------------- T-671 ----

def _vol_panel(D=60, S=30, seed=1):
    rng = np.random.default_rng(seed)
    return rng.lognormal(13.0, 0.5, size=(D, S))


def test_abnormal_volume_ignores_day_t_and_later():
    V = _vol_panel()
    i = 40
    for lag in (1, 2):
        base = M.abnormal_volume(V, lag)
        V2 = V.copy()
        V2[i - lag + 1:] *= 50.0                      # shock every volume after the measured day
        shocked = M.abnormal_volume(V2, lag)
        assert np.allclose(base[i], shocked[i], equal_nan=True)
        assert np.isfinite(base[i]).all()
        V3 = V.copy()
        V3[i - lag] *= 50.0                           # the measured day itself does move it
        assert not np.allclose(M.abnormal_volume(V3, lag)[i], base[i])


def test_abnormal_volume_definition():
    V = _vol_panel(D=30, S=3)
    i = 25
    av = M.abnormal_volume(V, 1)[i]
    want = np.log(V[i - 1] / V[i - 21:i - 1].mean(axis=0))
    assert np.allclose(av, want)


def test_top_decile_at_decision_ignores_later_volume_and_returns():
    V = _vol_panel(D=60, S=40)
    elig = np.ones(V.shape, bool)
    i = 45
    AV = M.abnormal_volume(V, 1)
    w0, rest0, n0 = M.decile_weights(AV[i], elig[i], True)
    V2 = V.copy()
    V2[i:] = V2[i:][::-1] * 7.0
    w1, rest1, n1 = M.decile_weights(M.abnormal_volume(V2, 1)[i], elig[i], True)
    assert n0 == n1 == 40 and np.allclose(w0, w1) and np.allclose(rest0, rest1)
    assert w0.sum() == pytest.approx(4.0)
    # the day-t returns enter the means only, never the ranking
    R = np.random.default_rng(3).normal(0, 0.01, V.shape)
    s0 = M.spread_series(AV, elig, R, np.array([i]))
    R2 = R.copy()
    R2[i + 1:] += 0.5
    s1 = M.spread_series(AV, elig, R2, np.array([i]))
    assert np.allclose(s0["d"], s1["d"])


def test_trailing_z_ignores_day_t_and_later():
    X = np.random.default_rng(5).normal(0.4, 0.05, size=(120, 10))
    i = 100
    z0 = M.trailing_z(X, 1)[i]
    X2 = X.copy()
    X2[i:] = 9.0
    assert np.allclose(M.trailing_z(X2, 1)[i], z0)
    mu, sd = X[i - 61:i - 1].mean(axis=0), X[i - 61:i - 1].std(axis=0, ddof=1)
    assert np.allclose(z0, (X[i - 1] - mu) / sd)


# --------------------------------------------------------------------------------------------------- T-662 ----

def _bars(seed=0, days=("2025-03-03", "2025-03-04", "2025-03-05")):
    rng = np.random.default_rng(seed)
    out = {}
    for s in [f"S{k}" for k in range(10)]:
        b = {}
        for d in days:
            b[d] = {hm: tuple(100 * (1 + rng.normal(0, 0.01, 4))) for hm in
                    ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")}
        out[s] = b
    return out


def test_t662_rod3_and_quintile_ignore_after_1430():
    days = ["2025-03-03", "2025-03-04", "2025-03-05"]
    syms = [f"S{k}" for k in range(10)]
    bars = _bars()
    rng = np.random.default_rng(9)
    close = {s: 100 * (1 + rng.normal(0, 0.01, 3)) for s in syms}
    divs = {"S3": {"2025-03-04": 0.5}}
    p0 = M.t662_panel(bars, days, close, divs, syms)
    i = 1
    # shock everything after 14:30 on day t: the 14:30 bar, the 15:30 bar's high/low/close, the official close, day t+1
    b2 = {s: {d: dict(v) for d, v in b.items()} for s, b in bars.items()}
    c2 = {s: v.copy() for s, v in close.items()}
    for s in syms:
        b2[s][days[i]]["14:30"] = (1.0, 500.0, 0.5, 300.0)
        o = b2[s][days[i]]["15:30"][0]
        b2[s][days[i]]["15:30"] = (o, 900.0, 0.1, 400.0)
        b2[s][days[i + 1]] = {hm: (5.0, 6.0, 4.0, 5.5) for hm in b2[s][days[i + 1]]}
        c2[s][i] *= 3.0
        c2[s][i + 1] *= 0.2
    p1 = M.t662_panel(b2, days, c2, divs, syms)
    assert np.allclose(p0["ROD3"][i], p1["ROD3"][i])
    w0 = M.quintile_weights(p0["ROD3"][i], p0["elig"][i])
    w1 = M.quintile_weights(p1["ROD3"][i], p1["elig"][i])
    assert np.allclose(w0, w1) and w0.sum() == pytest.approx(2.0)
    # a missing official close (the exit) never moves the 15:30 selection
    c3 = {s: v.copy() for s, v in close.items()}
    c3["S5"][i] = np.nan
    p3 = M.t662_panel(bars, days, c3, divs, syms)
    assert np.array_equal(p0["elig"][i], p3["elig"][i])
    assert np.allclose(M.quintile_weights(p3["ROD3"][i], p3["elig"][i]), w0)
    # the definition: log(close of the 13:30 bar / (prior close - dividend on the ex-date))
    j = syms.index("S3")
    assert p0["ROD3"][i, j] == pytest.approx(np.log(bars["S3"][days[i]]["13:30"][3] / (close["S3"][0] - 0.5)))
    assert p0["R"][i, j] == pytest.approx(close["S3"][i] / bars["S3"][days[i]]["15:30"][0] - 1.0)


def test_t662_early_close_excluded():
    days = ["2025-11-28"]
    syms = ["A", "B"]
    bars = {s: {days[0]: {"09:30": (1, 1.1, 0.9, 1), "10:30": (1, 1.1, 0.9, 1), "11:30": (1, 1.1, 0.9, 1),
                          "13:00": (1, 1, 1, 1)}} for s in syms}
    p = M.t662_panel(bars, days, {s: np.array([1.0]) for s in syms}, {}, syms)
    assert p["early"][0] and not p["valid"].any() and not p["elig"].any()


def test_net_long_costs():
    r = np.array([0.0, 0.01])
    assert np.allclose(M.net_long(r), r - 2e-4 - 27.80e-6 * (1 + r))


# --------------------------------------------------------------------------------------------------- T-663 ----

def _fake_pan(D=140, S=30, seed=2):
    rng = np.random.default_rng(seed)
    days = np.array([str(np.datetime64("2020-01-01") + np.timedelta64(k, "D")) for k in range(D)])
    open_ts = np.array([datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp() + 14.5 * 3600 for d in days])
    A = 100 * np.cumprod(1 + rng.normal(0, 0.01, (D, S)), axis=0)
    spy = 100 * np.cumprod(1 + rng.normal(0, 0.008, D))
    syms = [f"S{k}" for k in range(S)]
    return {"days": days, "open_ts": open_ts, "syms": syms, "M": np.ones((D, S), bool), "C": A.copy(), "A": A,
            "spy_a": spy, "alias": {}}


def _releases(pan, seed=4):
    rng = np.random.default_rng(seed)
    out = []
    for k, s in enumerate((70, 85, 100)):
        av = pan["open_ts"][s - 1] + 9 * 3600            # published the evening before session s
        rows = {M.finra_sym(y): ("", float(rng.uniform(1e5, 1e7)), float(rng.uniform(1e5, 1e6))) for y in pan["syms"]}
        out.append({"settle": f"r{k}", "av": av, "rows": rows})
    return out


def test_t663_entry_is_first_open_after_publication():
    pan = _fake_pan()
    rel = _releases(pan)
    s = M.entry_rows(pan["open_ts"], [r["av"] for r in rel])
    assert list(s) == [70, 85, 100]
    assert all(pan["open_ts"][k] > r["av"] for k, r in zip(s, rel))
    assert all(pan["open_ts"][k - 1] <= r["av"] for k, r in zip(s, rel))


def test_t663_formation_ignores_later_prices_and_releases():
    pan = _fake_pan()
    rel = _releases(pan)
    f0 = M.t663_formations(pan, rel)
    pan2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in pan.items()}
    s = f0[1]["s"]
    pan2["A"][s:] *= np.random.default_rng(8).uniform(0.2, 5.0, pan2["A"][s:].shape)
    pan2["C"][s:] *= 3.0
    pan2["spy_a"][s:] *= 2.0
    rel2 = [dict(r) for r in rel]
    rel2[2] = {"settle": "r2", "av": rel[2]["av"], "rows": {k: ("", 1.0, 1.0) for k in rel[2]["rows"]}}
    f1 = M.t663_formations(pan2, rel2)
    assert f0[1]["s"] == f1[1]["s"]
    assert np.allclose(f0[1]["dtc"], f1[1]["dtc"], equal_nan=True)
    assert np.allclose(f0[1]["ivol"], f1[1]["ivol"], equal_nan=True)
    assert np.isfinite(f0[1]["dtc"]).all() and np.isfinite(f0[1]["ivol"]).all()


def test_ivol_uses_rows_before_entry_only():
    rng = np.random.default_rng(1)
    Rs = rng.normal(0, 0.01, (100, 5))
    Rm = rng.normal(0, 0.01, 100)
    s = 80
    v0 = M.ivol_at(Rs, Rm, s)
    Rs2, Rm2 = Rs.copy(), Rm.copy()
    Rs2[s:] = 1.0
    Rm2[s:] = -1.0
    assert np.allclose(M.ivol_at(Rs2, Rm2, s), v0)
    y, x = Rs[s - 60:s, 0], Rm[s - 60:s]
    b = np.polyfit(x, y, 1)
    e = y - np.polyval(b, x)
    assert v0[0] == pytest.approx(np.sqrt((e * e).sum() / 58))


def test_hold_series_switches_sets_at_the_entry_open():
    D, S = 12, 20
    rng = np.random.default_rng(0)
    ID = rng.normal(0, 0.01, (D, S))
    ON = rng.normal(0, 0.01, (D, S))
    sc1 = np.arange(S, dtype=float)
    sc2 = sc1[::-1].copy()
    forms = [{"s": 2, "dtc": sc1, "elig": np.ones(S, bool)}, {"s": 6, "dtc": sc2, "elig": np.ones(S, bool)}]
    h = M.hold_series(D, forms, "dtc", ID, ON)
    hi1, lo1 = [18, 19], [0, 1]
    hi2, lo2 = [0, 1], [18, 19]
    # session 6: intraday from the new set, the overnight into 6 from the old set
    assert h["id"][6] == pytest.approx(ID[6, hi2].mean() - ID[6, lo2].mean())
    assert h["on"][6] == pytest.approx(ON[6, hi1].mean() - ON[6, lo1].mean())
    assert h["on"][7] == pytest.approx(ON[7, hi2].mean() - ON[7, lo2].mean())
    assert np.isnan(h["id"][1]) and np.isnan(h["on"][2])
    # returns after a day never move that day's components
    ID2, ON2 = ID.copy(), ON.copy()
    ID2[7:] += 1.0
    ON2[7:] += 1.0
    h2 = M.hold_series(D, forms, "dtc", ID2, ON2)
    assert np.allclose(h["d"][:7], h2["d"][:7], equal_nan=True)


# --------------------------------------------------------------------------------------------------- T-665 ----

def _fx_frame(start="2025-01-13", hours=24 * 6, seed=0, base=1.1):
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    c = base * np.exp(np.cumsum(rng.normal(0, 5e-4, hours)))
    o = np.concatenate([[base], c[:-1]])
    df = pd.DataFrame({"o": o, "h": np.maximum(o, c) * 1.0002, "l": np.minimum(o, c) * 0.9998, "c": c, "v": 0.0}, index=t)
    df.index.name = "t"
    return df


def test_fx_window_ignores_bars_at_and_after_window_end():
    df = _fx_frame()
    hs = M.HourSeries.from_frame(df)
    d = date(2025, 1, 15)
    a, b = M.edge_ts(d, M.PRE_T[0]), M.edge_ts(d, M.PRE_T[1])
    r0 = hs.window(np.array([a]), np.array([b]))[0]
    df2 = df.copy()
    late = df2.index >= pd.Timestamp(b, unit="s", tz="UTC")
    df2.loc[late, ["o", "h", "l", "c"]] *= 1.5
    r1 = M.HourSeries.from_frame(df2).window(np.array([a]), np.array([b]))[0]
    assert np.isfinite(r0) and r0 == pytest.approx(r1)
    ia = df.index.get_loc(pd.Timestamp(a, unit="s", tz="UTC"))
    ib = df.index.get_loc(pd.Timestamp(b, unit="s", tz="UTC"))
    assert r0 == pytest.approx(np.log(df["c"].iloc[ib - 1] / df["o"].iloc[ia]))


def test_fx_pre_window_ignores_post_window_bars():
    frames = {c: _fx_frame(seed=k) for k, (c, *_r) in enumerate(M.T665_CCY)}
    series = {c: M.HourSeries.from_frame(f) for c, f in frames.items()}
    days = [date(2025, 1, 15), date(2025, 1, 16)]
    pre0 = M.window_table(series, days, M.PRE_T)
    post_start = M.edge_ts(days[0], M.POST_T[0])
    shocked = {}
    for c, f in frames.items():
        f2 = f.copy()
        m = (f2.index >= pd.Timestamp(post_start, unit="s", tz="UTC")) & (f2.index < pd.Timestamp(M.edge_ts(days[0], M.POST_T[1]), unit="s", tz="UTC"))
        f2.loc[m, ["o", "h", "l", "c"]] *= 1.3
        shocked[c] = M.HourSeries.from_frame(f2)
    pre1 = M.window_table(shocked, days, M.PRE_T)
    assert np.allclose(pre0[0], pre1[0])
    assert np.isfinite(pre0[0]).all()
    # sign alignment: positive = USD up (EURUSD falls)
    j = [c for c, *_r in M.T665_CCY].index("EUR")
    a, b = M.edge_ts(days[0], M.PRE_T[0]), M.edge_ts(days[0], M.PRE_T[1])
    assert pre0[0, j] == pytest.approx(-series["EUR"].window(np.array([a]), np.array([b]))[0])


def test_fx_stale_or_missing_bar_drops_window():
    df = _fx_frame()
    d = date(2025, 1, 15)
    a, b = M.edge_ts(d, M.PRE_E[0]), M.edge_ts(d, M.PRE_E[1])
    mid = pd.Timestamp(a + 2 * 3600, unit="s", tz="UTC")
    st = df.copy()
    st.loc[mid, ["o", "h", "l", "c"]] = 1.2
    assert np.isnan(M.HourSeries.from_frame(st).window(np.array([a]), np.array([b]))[0])
    gap = df.drop(index=mid)
    assert np.isnan(M.HourSeries.from_frame(gap).window(np.array([a]), np.array([b]))[0])


def test_monday_pre_tokyo_needs_sunday_1700_bar():
    # Yahoo's first Sunday bar is 19:00 ET: a Monday's pre-T (from Sunday 17:00 New York) is incomplete
    df = _fx_frame(start="2025-01-12 00:00", hours=24 * 3)
    sunday = df.index.tz_convert("America/New_York")
    keep = ~((sunday.dayofweek == 6) & (sunday.hour < 19))
    hs = M.HourSeries.from_frame(df[keep])
    d = date(2025, 1, 13)
    assert np.isnan(hs.window(np.array([M.edge_ts(d, M.PRE_T[0])]), np.array([M.edge_ts(d, M.PRE_T[1])]))[0])


def test_window_edges_follow_local_time():
    winter, summer = date(2025, 1, 15), date(2025, 7, 15)
    h = lambda d, spec: datetime.fromtimestamp(M.edge_ts(d, spec), timezone.utc).hour
    assert (h(winter, M.PRE_T[0]), h(summer, M.PRE_T[0])) == (22, 21)
    assert (h(winter, M.POST_T[1]), h(summer, M.POST_T[1])) == (7, 6)
    assert (h(winter, M.POST_L[0]), h(summer, M.POST_L[0])) == (16, 15)


# ------------------------------------------------------------------------------------------------- helpers ----

def test_holm_decide():
    assert M.holm_decide([0.01, 0.04], [None, None]) == [True, True]
    assert M.holm_decide([0.03, 0.04], [None, None]) == [False, False]
    assert M.holm_decide([0.004, None, None, None, None, None], [None] * 6)[0] is True
    assert M.holm_decide([0.009, None, None, None, None, None], [None] * 6)[0] is False


def test_mean_test_direction():
    x = np.random.default_rng(0).normal(-0.002, 0.001, 300)
    t = M.mean_test(x, -10e-4, "less", 5, 10)
    assert t["mean"] < -10e-4 and t["p_nw"] < 0.05 and t["p_bt"] < 0.05
    t2 = M.mean_test(x, 0.0, "greater", 5, 10)
    assert t2["p_nw"] > 0.95 and t2["p_nw_opp"] < 0.05


# ------------------------------------------------------------------------------------- review fixes (T-663) ----

def _cap_pan(D=10):
    days = np.array([str(np.datetime64("2024-01-01") + np.timedelta64(k, "D")) for k in range(D)])
    open_ts = np.array([datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp() + 14.5 * 3600 for d in days])
    syms = ["AAA", "GOOGL", "GOOG", "BRK-B", "ZZZ"]
    C = np.tile(np.array([50.0, 100.0, 101.0, 400.0, 20.0]), (D, 1))
    F = np.ones((D, len(syms)))
    F[:4, 0] = 2.0                                   # AAA split 2:1 with ex-date days[4]
    return {"days": days, "open_ts": open_ts, "syms": syms, "col": {y: j for j, y in enumerate(syms)}, "C": C, "F": F}


def _cap_inputs(pan, s=6):
    forms = [{"settle": "r0", "s": s, "dtc": np.array([1.0, 2.0, 3.0, 4.0, 5.0])}]
    rel = [{"settle": "r0", "rows": {M.finra_sym(y): (nm, 1.0, 1.0) for y, nm in
                                     (("AAA", "Aaa Corp"), ("GOOGL", "Alphabet Inc. Class A"), ("GOOG", "Alphabet Inc. Class C"),
                                      ("BRK-B", "Berkshire Hathaway Class B"), ("ZZZ", "Zeta Holdings"))},
            "stock": frozenset({"AAA", "GOOGL", "GOOG", "GOOGM", "BRKA", "BRKB", "ZZZ"})}]
    av0 = pan["open_ts"][1]                          # accepted well before the entry open
    sec = {"cik_of": {"AAA": 1, "GOOGL": 2, "GOOG": 2, "BRK-B": 3, "ZZZ": 4},
           "by_cik": {1: ["AAA"], 2: ["GOOGL", "GOOG", "GOOGM"], 3: ["BRK-B", "BRK-A"], 4: ["ZZZ"]},
           "names": {1: ["Aaa Corp"], 2: ["Alphabet Inc."], 3: ["Berkshire Hathaway Inc"], 4: ["Omega Widgets Inc"]},
           "shares": {1: [(av0, str(pan["days"][0]), 1000.0)], 2: [(av0, str(pan["days"][0]), 600.0)],
                      3: [(av0, str(pan["days"][0]), 10.0)], 4: [(av0, str(pan["days"][0]), 5.0)]}}
    return forms, rel, sec


def test_formation_caps_definition_and_classes():
    pan = _cap_pan()
    forms, rel, sec = _cap_inputs(pan)
    cap = M.formation_caps(pan, forms, rel, sec)[0]
    # split after the cover date restates the count: close 50 (post-split basis) x 1000 x 2
    assert cap[0] == pytest.approx(50.0 * 1000.0 * 2.0)
    # GOOGL / GOOG share the summed count; the depositary row GOOGM is not a class
    assert cap[1] == pytest.approx(100.0 * 600.0 / 2) and cap[2] == pytest.approx(101.0 * 600.0 / 2)
    # BRK-A is a listed class with no price in the panel: no cap
    assert np.isnan(cap[3])
    # the FINRA issue name disagrees with the CIK's SEC names (a reused ticker): no cap
    assert np.isnan(cap[4])


def test_formation_caps_ignore_data_after_the_entry_open():
    pan = _cap_pan()
    forms, rel, sec = _cap_inputs(pan)
    s = forms[0]["s"]
    c0 = M.formation_caps(pan, forms, rel, sec)[0]
    pan2 = dict(pan)
    pan2["C"] = pan["C"].copy()
    pan2["C"][s:] *= 7.0                             # prices from the entry session on
    sec2 = {k: (dict(v) if isinstance(v, dict) else v) for k, v in sec.items()}
    sec2["shares"] = {c: sorted(v + [(pan["open_ts"][s] + 60.0, str(pan["days"][s]), 1e9)]) for c, v in sec["shares"].items()}
    c1 = M.formation_caps(pan2, forms, rel, sec2)[0]
    assert np.allclose(c0, c1, equal_nan=True)
    # a price at s-1 does move it (the cap is the close before the entry)
    pan3 = dict(pan)
    pan3["C"] = pan["C"].copy()
    pan3["C"][s - 1, 0] *= 3.0
    assert M.formation_caps(pan3, forms, rel, sec)[0][0] == pytest.approx(3.0 * c0[0])


def test_hold_series_value_weights():
    D, S = 8, 20
    rng = np.random.default_rng(1)
    ID = rng.normal(0, 0.01, (D, S))
    ON = rng.normal(0, 0.01, (D, S))
    sc = np.arange(S, dtype=float)
    caps = [np.linspace(1.0, 20.0, S)]
    caps[0][19] = np.nan                             # a name without a cap carries no weight
    forms = [{"s": 2, "dtc": sc, "elig": np.ones(S, bool)}]
    h = M.hold_series(D, forms, "dtc", ID, ON, caps=caps)
    w_lo = caps[0][[0, 1]]
    assert h["id"][4] == pytest.approx(ID[4, 18] - (ID[4, [0, 1]] * w_lo).sum() / w_lo.sum())
    ID2 = ID.copy()
    ID2[5:] += 1.0
    h2 = M.hold_series(D, forms, "dtc", ID2, ON, caps=caps)
    assert np.allclose(h["d"][:5], h2["d"][:5], equal_nan=True)


def test_two_sided_vs_zero_is_against_zero_not_the_bar():
    x = np.random.default_rng(3).normal(-1e-4, 1e-3, 800)
    r = M.two_sided_vs_zero(x, 10, 20)
    t = M.nw(x, 10)["t"]
    assert r["nw_t"] == pytest.approx(t)
    assert r["p_nw"] == pytest.approx(2 * (1 - M._phi(abs(t))))
    bar = M.mean_test(x, 2e-4, "greater", 10, 20)
    assert r["p_nw"] > min(1.0, 2 * min(bar["p_nw"], bar["p_nw_opp"]))


# ------------------------------------------------------------------------------------- review fixes (T-665) ----

def _j(v):
    return (v, f"{v} why", [(f"c {v}", v == "supported")])


def test_combine_fixes_conjunction_at_each_fix_own_n():
    labels = {"T": "Tokyo fix", "E": "Europe fix"}
    ns = {"T": 575, "E": 721}
    v, why, crit, n = M.combine_fixes({"T": _j("inconclusive"), "E": _j("not_supported")}, ns, labels)
    assert v == "not_supported" and n == 721 and "own n 721" in why
    v, _w, _c, n = M.combine_fixes({"T": _j("inconclusive"), "E": _j("supported")}, ns, labels)
    assert v == "inconclusive" and n == 575
    v, _w, _c, n = M.combine_fixes({"T": _j("supported"), "E": _j("supported")}, ns, labels)
    assert v == "supported"
    assert [c[0].split(":")[0] for c in crit] == ["Tokyo fix", "Europe fix"]


def test_combine_fixes_rule5_shields_only_the_thin_fix():
    # the same failing rows: below min_n (Tokyo) a non-decisive failure is undecided, at min_n (Europe) it fails
    rows = [("significance", False, False), ("halves", True, False)]
    jT = M._judge(rows, 575, M.T665_MIN_N, "Tokyo fix basket days")
    jE = M._judge(rows, 721, M.T665_MIN_N, "Europe fix basket days")
    assert jT[0] == "inconclusive" and jE[0] == "not_supported"
    v, _w, _c, n = M.combine_fixes({"T": jT, "E": jE}, {"T": 575, "E": 721}, {"T": "Tokyo fix", "E": "Europe fix"})
    assert v == "not_supported" and n == 721


def test_jp_holidays_include_coming_of_age_days():
    assert {"2024-01-08", "2025-01-13", "2026-01-12"} <= M.JP_HOLIDAYS
