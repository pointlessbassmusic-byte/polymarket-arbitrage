"""Tests for mandel/experiments/batch13_volume_b.py (T-695, T-697, T-699, T-700, T-702).

Each signal construction is checked for look-ahead: values after the decision time are shocked and the signal at the
decision must not move. Every harness must return inconclusive when its bundles are missing."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from mandel.experiments import batch13_volume_b as M

NY = ZoneInfo("America/New_York")


class StubArchive:
    """An archive with nothing in it: every get() raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, *a, **k):
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
    C = A * rng.uniform(0.95, 1.0, (1, N))
    O = C * np.exp(rng.normal(0, 0.005, (D, N)))
    V = rng.lognormal(14.0, 0.5, (D, N)) * rng.uniform(0.5, 2.0, (1, N))
    return A, C, O, V


def _shock_after(X: np.ndarray, i: int, seed: int = 9, axis: int = 0) -> np.ndarray:
    """Multiply every entry after index ``i`` along ``axis`` by a random factor."""
    rng = np.random.default_rng(seed)
    Y = np.array(X, float, copy=True)
    sl = [slice(None)] * Y.ndim
    sl[axis] = slice(i + 1, None)
    sl = tuple(sl)
    Y[sl] = Y[sl] * rng.uniform(0.2, 5.0, Y[sl].shape)
    return Y


def _same(a, b) -> bool:
    return bool(np.allclose(np.asarray(a, float), np.asarray(b, float), equal_nan=True))


# ================================================================================================= wiring ==

def test_maps_cover_the_five_theories():
    assert set(M.THEORY_MAP) == {"T-695", "T-697", "T-699", "T-700", "T-702"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for name, fn in M.HARNESSES.items():
        assert name.startswith("b13_volume_b_")
        assert fn.__doc__ and "T-" in fn.__doc__


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    r = M.HARNESSES[name](StubArchive())
    assert r[2] == "inconclusive"
    assert r[1] == 0
    assert "missing" in r[3]


def test_quantile_legs_and_terciles_are_strict():
    s = np.arange(10, dtype=float)
    el = np.ones(10, bool)
    lo, hi = M.q_legs(s, el)
    assert lo.tolist() == [True, True] + [False] * 8
    assert hi.tolist() == [False] * 8 + [True, True]
    t = M.terciles(s, el)
    assert sum(m.sum() for m in t) == 10 and t[0][:3].all() and t[2][-3:].all()
    assert not (t[0] & t[2]).any()


def test_dsr_bound_cannot_pass_and_fails_on_a_losing_series():
    rng = np.random.default_rng(1)
    good = rng.normal(0.01, 0.02, 400)
    row, info = M.dsr_bound(good, 26, "x", "family")
    assert row[1] in (None, False) and info["dsr_bound"] is not None
    bad = rng.normal(-0.01, 0.02, 400)
    row, _ = M.dsr_bound(bad, 26, "x", "family")
    assert row[1] is False and row[2] is True


# ====================================================================================================== T-695 ==

def test_month_index_partitions_the_calendar():
    days = _sessions(70, "2020-01-02")
    months, s0, s1 = M.month_index(days)
    assert months[0] == "2020-01" and len(months) == len({d[:7] for d in days})
    assert (s1 - s0 + 1).sum() == len(days)
    for m, a, b in zip(months, s0, s1):
        assert days[a][:7] == m and days[b][:7] == m


def test_volume_cv_uses_no_month_after_the_formation_month():
    days = _sessions(1200, "2010-01-04")
    _, _, _, V = _prices(len(days), 6)
    _months, s0, s1 = M.month_index(days)
    MV, valid = M.monthly_volume(V, s0, s1)
    k = 40
    cv, mv = M.volume_cv(MV, valid, k)
    f = int(s1[k])                                    # the formation session: month k's last session
    V2 = _shock_after(V, f)
    MV2, valid2 = M.monthly_volume(V2, s0, s1)
    cv2, mv2 = M.volume_cv(MV2, valid2, k)
    assert _same(cv, cv2) and _same(mv, mv2)
    X = MV[k - 35:k + 1]
    assert np.allclose(cv, X.std(axis=0, ddof=1) / X.mean(axis=0))
    # a missing session invalidates the month; fewer than 24 valid months -> no CV
    V3 = V.copy()
    for kk in range(k - 35, k - 35 + 13):
        V3[int(s0[kk]), 0] = np.nan
    MV3, valid3 = M.monthly_volume(V3, s0, s1)
    cv3, _ = M.volume_cv(MV3, valid3, k)
    assert np.isnan(cv3[0]) and np.isfinite(cv3[1:]).all()


# ====================================================================================================== T-697 ==

def test_trailing_high_and_first_crossing_are_point_in_time():
    D, N = 700, 5
    _, C, _, _ = _prices(D, N, seed=3)
    Hx = M.trailing_extreme(C, 252, "max", chunk=37)
    i = 500
    assert np.allclose(Hx[i], C[i - 252:i].max(axis=0))
    assert np.isnan(Hx[251]).all() and np.isfinite(Hx[252]).all()
    # shocking the event day itself and everything after leaves the previous-window high unchanged
    C2 = _shock_after(C, i - 1)
    Hx2 = M.trailing_extreme(C2, 252, "max", chunk=64)
    assert _same(Hx[:i + 1], Hx2[:i + 1])
    E = M.first_crossings(C, Hx, 60)
    C3 = _shock_after(C, i)
    E3 = M.first_crossings(C3, M.trailing_extreme(C3, 252, "max"), 60)
    assert (E[:i + 1] == E3[:i + 1]).all()
    # an event has no crossing in the previous 60 sessions
    for r, c in zip(*np.nonzero(E)):
        assert not (C[r - 60:r, c] > Hx[r - 60:r, c]).any()
    Lx = M.trailing_extreme(C, 252, "min")
    assert np.allclose(Lx[i], C[i - 252:i].min(axis=0))


def test_av_ratio_uses_the_previous_fifty_sessions_only():
    D, N = 200, 4
    _, _, _, V = _prices(D, N, seed=4)
    av = M.av_ratio(V)
    i = 120
    assert np.allclose(av[i], V[i] / np.median(V[i - 50:i], axis=0))
    av2 = M.av_ratio(_shock_after(V, i))
    assert _same(av[:i + 1], av2[:i + 1])
    V0 = V.copy()
    V0[i, 0] = 0.0                                    # a zero-volume bar is a stale print: no AV
    assert np.isnan(M.av_ratio(V0)[i, 0])


def test_expanding_breakpoints_ignore_same_day_and_later_events():
    rng = np.random.default_rng(5)
    n = 400
    day = np.sort(rng.integers(0, 150, n))
    av = rng.lognormal(0, 0.5, n)
    cl = M.expanding_classes(day, av, burn=100)
    k = 250
    d_k = day[k]
    av2 = av.copy()
    later = day >= d_k
    av2[later] = av2[later] * rng.uniform(0.1, 10.0, later.sum())
    cl2 = M.expanding_classes(day, av2, burn=100)
    early = day < d_k
    assert (cl["cls"][early] == cl2["cls"][early]).all()
    # breakpoints of an event come from strictly earlier days
    same_day = day == d_k
    assert _same(cl["q"][same_day], cl2["q"][same_day])
    prior = np.sort(av[day < d_k])
    j = int(np.flatnonzero(same_day)[0])
    if prior.size >= 100:
        assert np.isclose(cl["q"][j, 1], np.quantile(prior, 2 / 3))
    assert (cl["cls"][cl["n_prior"] < 100] == -1).all()


def test_forward_return_starts_at_the_next_open_and_roll_sd_is_trailing():
    D, N = 120, 3
    A, C, O, _ = _prices(D, N, seed=6)
    AO = O * (A / C)
    MO = AO[:, 0].copy()
    beta = np.zeros((D, N))
    W = M.fwd_abnormal(AO, MO, beta, 20)
    i = 50
    assert np.allclose(W[i], AO[i + 21] / AO[i + 1] - 1.0)
    AO2 = AO.copy()
    AO2[:i + 1] *= 3.0                                 # the event day's own open and earlier never enter the return
    assert _same(M.fwd_abnormal(AO2, MO, beta, 20)[i], W[i])
    assert np.isnan(W[D - 21:]).all()
    R = M.daily_returns(A)
    sd = M.roll_sd(R, 60)
    assert np.allclose(sd[i + 30], R[i - 29:i + 31].std(axis=0, ddof=1))
    sd2 = M.roll_sd(_shock_after(R, i), 60)
    assert _same(sd[:i + 1], sd2[:i + 1])


def test_matched_placebo_is_seeded_and_excludes_the_event_day():
    D, N = 300, 3
    rng = np.random.default_rng(7)
    net = rng.normal(0, 0.02, (D, N))
    vol = np.full((D, N), 0.02)
    dist = np.zeros((D, N))
    pool = np.ones((D, N), bool)
    ev_i, ev_j = np.array([50, 120, 200]), np.array([0, 1, 2])
    a = M.matched_placebo(ev_i, ev_j, net, vol, dist, pool, n_draw=500, seed=1)
    b = M.matched_placebo(ev_i, ev_j, net, vol, dist, pool, n_draw=500, seed=1)
    assert a["p"] == b["p"] and 0 < a["p"] <= 1 and a["n_matched"] == 3
    pool2 = np.zeros((D, N), bool)
    pool2[ev_i, ev_j] = True                            # only the event days themselves: nothing to match
    c = M.matched_placebo(ev_i, ev_j, net, vol, dist, pool2, n_draw=50)
    assert c["p"] is None and c["n_unmatched"] == 3


# ====================================================================================================== T-699 ==

def _bar_ts(day: str, hm: str) -> int:
    y, m, d = map(int, day.split("-"))
    h, mi = map(int, hm.split(":"))
    return int(datetime(y, m, d, h, mi, tzinfo=NY).astimezone(timezone.utc).timestamp())


def _hourly_and_daily(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    days = _sessions(n, "2023-11-01")
    hv, dv = [], []
    px = 450.0
    for d in days:
        o = px
        for k, hm in enumerate(("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30")):
            c = o * (1 + rng.normal(0, 0.002))
            hv.append({"t": _bar_ts(d, hm), "open": o, "high": max(o, c), "low": min(o, c), "close": c,
                       "volume": float(rng.lognormal(16, 0.3))})
            o = c
        hv.append({"t": _bar_ts(d, "16:00"), "open": o, "high": o, "low": o, "close": o, "volume": 0.0})
        close = o * (1 + rng.normal(0, 0.0005))
        dv.append({"t": _bar_ts(d, "09:30"), "open": px * (1 + rng.normal(0, 0.001)), "close": close,
                   "adjclose": close * 0.99})
        px = close * (1 + rng.normal(0, 0.003))
    return days, hv, dv


def test_rvol_classes_use_only_earlier_sessions():
    rng = np.random.default_rng(8)
    v = rng.lognormal(16, 0.4, 300)
    a = M.rvol_classes(v)
    j = 200
    assert np.isclose(a["ratio"][j], v[j] / np.median(v[j - 20:j]))
    assert np.isclose(a["p_hi"][j], np.percentile(a["ratio"][j - 60:j], 67))
    b = M.rvol_classes(_shock_after(v, j))
    assert _same(a["ratio"][:j + 1], b["ratio"][:j + 1])
    assert (a["cls"][:j + 1] == b["cls"][:j + 1]).all()
    assert (a["cls"][:80] == -1).all() and (a["cls"][80:] >= 0).all()


def test_session_signal_is_known_at_the_1530_open_and_ignores_the_print_bar():
    days, hv, dv = _hourly_and_daily(120)
    S = M.t699_sessions(hv, dv, start="2023-11-01", end="2026-12-31")
    k = 90
    d = days[k]
    assert S["days"][k] == d and S["test"][k]
    mn = M.momentum_net(S)
    # shock everything known after the 15:30 open: the 15:30 bar's close/high/low/volume, the 16:00 print and every
    # later bar and daily close; the signal (sign of 15:30 open / previous close) and the RVOL class must not move
    t1530 = _bar_ts(d, "15:30")
    hv2 = []
    for v in hv:
        v = dict(v)
        if v["t"] > t1530 or v["t"] == t1530:
            for f in ("high", "low", "close", "volume"):
                v[f] = v[f] * 3.7 + 1.0
        hv2.append(v)
    dv2 = [dict(v, close=v["close"] * 1.3, adjclose=v["adjclose"] * 1.3) if v["t"] >= _bar_ts(d, "09:30") else v for v in dv]
    S2 = M.t699_sessions(hv2, dv2, start="2023-11-01", end="2026-12-31")
    mn2 = M.momentum_net(S2)
    assert np.isclose(mn["r1"][k], mn2["r1"][k]) and mn["pos"][k] == mn2["pos"][k]
    rv, rv2 = M.rvol_classes(S["v0930"]), M.rvol_classes(S2["v0930"])
    assert rv["cls"][k] == rv2["cls"][k] and np.isclose(rv["ratio"][k], rv2["ratio"][k], equal_nan=True)
    # the trade exits at the official daily close, not at the 15:30 bar's last trade
    assert np.isclose(mn["last"][k], dv[k]["close"] / S["o1530"][k] - 1.0)
    # the previous close is put on day t's dividend basis (constant adj ratio here: unchanged)
    assert np.isclose(S["prev_close"][k], dv[k - 1]["close"])


def test_sessions_without_the_1530_bar_are_excluded():
    days, hv, dv = _hourly_and_daily(40)
    drop = _bar_ts(days[30], "15:30")
    S = M.t699_sessions([v for v in hv if v["t"] != drop], dv, start="2023-11-01", end="2026-12-31")
    assert days[30] in S["excluded"]["missing_1530_bar"] and not S["test"][30]


def test_within_week_placebo_returns_valid_p_values():
    rng = np.random.default_rng(9)
    n = 150
    net = rng.normal(0, 1e-3, n)
    cls = rng.integers(0, 3, n)
    weeks = np.arange(n) // 5
    p = M.within_week_placebo(net, cls, weeks, n_draw=200, seed=2)
    assert 0 < p["p_high"] <= 1 and 0 < p["p_hml"] <= 1 and p["n_draw"] == 200


# ====================================================================================================== T-700 ==

def test_epoch_seconds_handles_second_and_nanosecond_indexes():
    t = np.array([1700577000, 1700580600])
    i_s = pd.DatetimeIndex(pd.to_datetime(t, unit="s", utc=True)).as_unit("s")
    i_ns = i_s.as_unit("ns")
    assert M.epoch_seconds(i_s).tolist() == t.tolist()
    assert M.epoch_seconds(i_ns).tolist() == t.tolist()


def test_slot_day_returns_need_all_seven_bars_and_drop_the_print_bar():
    days = _sessions(3, "2024-03-04")
    t, o, c = [], [], []
    for d in days:
        px = 100.0
        for hm in M.T700_SLOTS + ("16:00",):
            if d == days[1] and hm == "12:30":
                continue                                    # an incomplete day
            t.append(_bar_ts(d, hm))
            o.append(px)
            px *= 1.01
            c.append(px)
    R = M.slot_day_returns(np.array(t), np.array(o), np.array(c))
    assert set(R) == {days[0], days[2]}
    assert np.allclose(R[days[0]], 0.01)


def test_lookback_means_exclude_the_current_day():
    rng = np.random.default_rng(10)
    D, Hs, N = 80, 7, 25
    R = rng.normal(0, 0.003, (D, Hs, N))
    same, other = M.lookback_means(R, 20)
    d = 50
    assert np.allclose(same[d], R[d - 20:d].mean(axis=0))
    oth = (R[d - 20:d].sum(axis=(0, 1))[None, :] - R[d - 20:d].sum(axis=0)) / (20 * 6)
    assert np.allclose(other[d], oth)
    R2 = _shock_after(R, d - 1)                         # day d itself and every later day
    s2, o2 = M.lookback_means(R2, 20)
    assert _same(same[:d + 1], s2[:d + 1]) and _same(other[:d + 1], o2[:d + 1])
    assert np.isnan(same[:20]).all()
    R3 = R.copy()
    R3[d - 5, 3, 0] = np.nan                            # an incomplete earlier day removes the name's lookback
    s3, _ = M.lookback_means(R3, 20)
    assert np.isnan(s3[d, :, 0]).all() and np.isfinite(s3[d, :, 1]).all()


def test_slot_regressions_detect_planted_same_slot_continuation():
    rng = np.random.default_rng(11)
    D, Hs, N = 120, 7, 40
    mu = rng.normal(0, 0.002, (Hs, N))                  # a persistent name-by-slot mean
    R = mu[None] + rng.normal(0, 0.002, (D, Hs, N))
    same, other = M.lookback_means(R, 20)
    G = M.slot_regressions(R, same, other)
    assert G["uni"].size > 0 and G["uni"].mean() > 0 and G["joint"].mean() > 0
    cost = np.full(N, 2e-4)
    sp = M.slot_portfolio(R, same, cost)
    assert sp["n_slot_days"] > 0 and np.mean(sp["gross"]) > 0
    assert np.allclose(sp["net"], sp["gross"] - 4 * 2e-4)


# ====================================================================================================== T-702 ==

def _crypto_daily(n_days: int, n_prod: int, seed: int = 12, start: str = "2019-01-01") -> dict:
    rng = np.random.default_rng(seed)
    o0 = date.fromisoformat(start).toordinal()
    out = {}
    for p in range(n_prod):
        px = 10.0
        m = {}
        for k in range(n_days):
            px *= np.exp(rng.normal(0, 0.04))
            if rng.random() < 0.03:
                continue                                    # a day without trades
            m[date.fromordinal(o0 + k).isoformat()] = (px, float(rng.lognormal(10, 0.6)))
        out[f"C{p:02d}-USD"] = m
    return out


def test_week_signals_use_bars_through_saturday_only():
    daily = _crypto_daily(200, 30)
    Pn = M.crypto_panel(daily, "2019-01-01", "2019-07-19")
    o = date.fromisoformat("2019-05-05").toordinal()          # a Sunday entry
    assert date.fromordinal(o).weekday() == 6
    e = o - Pn["o0"]
    for rd in ("base", "dollar"):
        a = M.week_signals(Pn, e, rd)
        P2 = dict(Pn)
        P2["C"] = _shock_after(Pn["C"], e - 1, axis=1)
        P2["Cf"] = _shock_after(Pn["Cf"], e - 1, axis=1)
        P2["V"] = _shock_after(Pn["V"], e - 1, axis=1)
        b = M.week_signals(P2, e, rd)
        for k in ("ret", "rv", "hist"):
            assert _same(a[k], b[k]), (rd, k)
    s = e - 1
    a = M.week_signals(Pn, e, "base")
    assert np.allclose(a["ret"], Pn["Cf"][:, s] / Pn["Cf"][:, s - 7] - 1.0, equal_nan=True)
    rv = Pn["V"][:, s - 6:s + 1].mean(axis=1) / Pn["V"][:, s - 29:s + 1].mean(axis=1)
    assert np.allclose(a["rv"], rv, equal_nan=True)


def test_weekly_legs_do_not_move_when_later_bars_are_shocked():
    daily = _crypto_daily(260, 40)
    first, last = "2019-03-03", "2019-08-25"
    members = {}
    o = date.fromisoformat("2019-02-20").toordinal()
    while o <= date.fromisoformat("2019-09-17").toordinal():
        members[date.fromordinal(o).isoformat()] = sorted(daily)
        o += 1
    Pn = M.crypto_panel(daily, "2019-01-01", "2019-09-17")
    S = M.t702_series(Pn, members, 6, "base", first=first, last=last)
    assert S["rows"] and all(date.fromisoformat(r["day"]).weekday() == 6 for r in S["rows"])
    k = 10
    day = S["rows"][k]["day"]
    e = date.fromisoformat(day).toordinal() - Pn["o0"]
    P2 = dict(Pn)
    for f in ("C", "Cf", "V"):
        P2[f] = _shock_after(Pn[f], e - 1, axis=1)
    P2["traded"] = Pn["traded"]                          # trading status on the entry day is known at entry
    S2 = M.t702_series(P2, members, 6, "base", first=first, last=last)
    r1, r2 = S["rows"][k], S2["rows"][k]
    for leg in ("lal", "law", "hal", "haw"):
        assert (r1[leg] == r2[leg]).all(), leg
    assert r1["lal"].any() and not (r1["lal"] & r1["law"]).any() and not (r1["lal"] & r1["hal"]).any()
    # the hold runs from the Sunday close to the next Sunday close
    x = e + 7
    j = int(np.flatnonzero(r1["lal"])[0])
    assert np.isclose(r1["hold"][j], Pn["Cf"][j, x] / Pn["C"][j, e] - 1.0)
    st = M.t702_stats(S, M.T702_COST_SIDE)
    assert st["n_weeks"] > 0 and np.all(st["ex"] <= st["ex_gross"] + 1e-15)


def test_leg_book_charges_both_sides_of_the_round_trip():
    P = 4
    rows = []
    for k in range(3):
        m = np.zeros(P, bool)
        m[k] = True                                       # a full rotation every week
        rows.append({"lal": m, "univ_ret": 0.0, "hold": np.zeros(P)})
    bk = M.leg_book(rows, "lal", 0.0025)
    assert np.allclose(bk["gross"], 0.0)
    assert np.allclose(bk["turnover"], [1.0, 2.0, 3.0])          # entry; exit + entry; exit + entry + final exit
    assert np.allclose(bk["net"], -0.0025 * np.array([1.0, 2.0, 3.0]))
