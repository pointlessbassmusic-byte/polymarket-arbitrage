"""Batch-6c cryptovenue harnesses (T-328 IBIT premium fade, T-330 stablecoin peg reversion, T-365 stETH discount carry,
T-366 cbETH staking drift, T-419 high-volume return premium, T-424 BTC leads altcoins) on synthetic data only: for every
core function a planted effect passes and a null does not; the session-close candle (DST, early closes), the live and
lagged fills, the z invariance to the bitcoin-per-share calibration, the venue midnight closes, the peg entry/exit
timing, the episode rule, the claims' own 'too few events' rules, the band readings, the volume-surprise events, the
placebo, the calendar-time portfolio, the point-in-time basket ranking and the hourly grid are checked directly; every
harness runs JSON-safe on a fake archive, and missing bundles give inconclusive. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_cryptovenue as m

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
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


def epoch(day, hh=0):
    return int(datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), hh, tzinfo=UTC).timestamp())


def ibit_world(spike_p, spike=0.05, phi=0.5, noise=0.0005, seed=0):
    rng = np.random.default_rng(seed)
    days = bdays("2024-01-11", "2026-10-14")
    n = len(days)
    spot = 40000 * np.cumprod(1 + rng.normal(0, 0.02, n))
    prem = np.zeros(n)
    for t in range(1, n):
        prem[t] = phi * prem[t - 1] + noise * rng.normal()
        if rng.random() < spike_p:
            prem[t] += spike * (1 if rng.random() < 0.5 else -1)
    bps, ref = 0.00057, "2026-10-15"
    close = bps * m.fee_factor(days, ref) * spot * (1 + prem)
    return days, close, spot, bps, ref


# ======================================================================================================= T-328 ==

def test_session_close_candle_dst_and_early_closes():
    assert datetime.fromtimestamp(m.close_bar_start("2024-01-16"), tz=UTC).hour == 20        # 15:00 EST
    assert datetime.fromtimestamp(m.close_bar_start("2024-07-16"), tz=UTC).hour == 19        # 15:00 EDT
    for d in ("2024-07-03", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24"):
        assert m.early_close(d), d
    for d in ("2024-07-05", "2026-07-03", "2024-11-28", "2021-12-24", "2025-11-21"):
        assert not m.early_close(d), d
    assert datetime.fromtimestamp(m.close_bar_start("2024-11-29"), tz=UTC).hour == 17        # 12:00 EST candle -> 13:00


def test_spot_at_close_picks_the_candle_ending_at_the_close():
    days = ["2024-01-16", "2024-11-29"]
    ts = np.array([m.close_bar_start(d) for d in days] + [m.close_bar_start(days[0]) - 3600], np.int64)
    cl = np.array([100.0, 200.0, 99.0])
    o = np.argsort(ts)
    spot, stale = m.spot_at_close(days, (ts[o], cl[o]))
    assert spot.tolist() == [100.0, 200.0] and stale == 0
    spot, stale = m.spot_at_close(days[:1], (np.array([m.close_bar_start(days[0]) - 3600], np.int64), np.array([99.0])))
    assert spot.tolist() == [99.0] and stale == 1


def test_fade_trades_live_and_lagged_timing():
    days = [f"2024-05-{d:02d}" for d in range(1, 13)]
    z = np.array([0, 0, 2.5, 1.0, 0.5, -0.1, 0, 0, -3.0, -1, -1, -1], float)
    A = np.linspace(100, 111, 12)
    B = np.full(12, 50.0)
    live = m.fade_trades(days, z, A, B, "live", start=days[0], end=days[-1])
    lag = m.fade_trades(days, z, A, B, "lagged", start=days[0], end=days[-1])
    assert (live[0]["e"], live[0]["x"], live[0]["sg"]) == (2, 5, -1.0)          # exit when z crosses 0 (day 5)
    assert (lag[0]["e"], lag[0]["x"]) == (3, 6)
    assert (live[1]["e"], live[1]["x"], live[1]["sg"]) == (8, 11, 1.0)          # max hold of 3 sessions
    assert len(lag) == 1                                                          # the lagged second trade runs past the end
    assert live[0]["gross"] == pytest.approx(-(A[5] / A[2] - 1.0))


def test_fade_trades_reexamine_the_exit_decision_day():
    """Regression: a fresh |z| > 2 on the exit-decision day opens a new fade there (z through 0 past the opposite
    threshold, and z still beyond 2 at the 3-session timeout); the new entry fill equals the old exit fill."""
    days = [f"2024-05-{d:02d}" for d in range(1, 13)]
    A = np.linspace(100, 111, 12)
    B = np.full(12, 50.0)
    z = np.array([0, 0, 2.5, 1.0, -2.5, -1.0, 0.1, 0, 0, 0, 0, 0], float)       # crosses 0 and past -2 on day 4
    live = m.fade_trades(days, z, A, B, "live", start=days[0], end=days[-1])
    lag = m.fade_trades(days, z, A, B, "lagged", start=days[0], end=days[-1])
    assert [(q["e"], q["x"], q["sg"]) for q in live] == [(2, 4, -1.0), (4, 6, 1.0)]
    assert [(q["e"], q["x"], q["sg"]) for q in lag] == [(3, 5, -1.0), (5, 7, 1.0)]
    assert [q["signal"] for q in live] == [days[2], days[4]]
    z2 = np.array([0, 0, 2.5, 2.4, 2.3, 2.2, -0.5, 0, 0, 0, 0, 0], float)       # still beyond 2 at the timeout
    live2 = m.fade_trades(days, z2, A, B, "live", start=days[0], end=days[-1])
    lag2 = m.fade_trades(days, z2, A, B, "lagged", start=days[0], end=days[-1])
    assert [(q["e"], q["x"], q["sg"]) for q in live2] == [(2, 5, -1.0), (5, 6, -1.0)]
    assert [(q["e"], q["x"], q["sg"]) for q in lag2] == [(3, 6, -1.0), (6, 7, -1.0)]
    for tr in (live, lag, live2, lag2):
        assert all(b["e"] >= a["x"] for a, b in zip(tr, tr[1:]))               # never enter before the previous exit


def test_z_is_invariant_to_the_calibration():
    days, close, spot, bps, ref = ibit_world(0.05, seed=3)
    a = m.ibit_fade_test(days, close, spot, bps, ref)
    b = m.ibit_fade_test(days, close, spot, bps * 1.7, ref)
    assert np.allclose(a["z"], b["z"], equal_nan=True)
    assert [q["gross"] for q in a["runs"]["live"]] == [q["gross"] for q in b["runs"]["live"]]


def test_t328_planted_passes():
    days, close, spot, bps, ref = ibit_world(0.10, seed=1)
    j = m.ibit_fade_test(days, close, spot, bps, ref)
    assert j["n"] >= 30
    assert j["verdict"] == "supported", j["why"]
    assert not j["park_condition"]


def test_t328_null_fails_and_parks():
    days, close, spot, bps, ref = ibit_world(0.0, noise=0.001, phi=0.0, seed=2)
    j = m.ibit_fade_test(days, close, spot, bps, ref)
    assert j["verdict"] == "not_supported", j["why"]
    assert j["park_condition"] is True


# ======================================================================================================= T-330 ==

def test_peg_signals_rule():
    c = {f"2020-01-{d:02d}": 1.0 for d in range(1, 10)}
    c["2020-01-06"] = 0.99                       # only 5 closes >= 0.998 before it
    c["2020-01-07"] = 0.99                       # streak broken: no signal
    assert m.peg_signals(c) == ["2020-01-06"]
    c2 = dict(c)
    c2["2020-01-03"] = 0.997                      # streak broken before day 6
    assert m.peg_signals(c2) == []


def test_venue_closes_last_trade_before_midnight():
    s = epoch("2020-03-16")
    trades = [(s + 3600, 0.99), (s + 86400 - 10, 0.98), (s + 86400 + 5, 1.0), (s + 3 * 86400 - 60, 1.001)]
    vc = m.venue_closes(trades, s, s + 4 * 86400)
    assert vc["2020-03-16"][0] == 0.98 and vc["2020-03-16"][1] == pytest.approx(10 / 3600)
    assert vc["2020-03-17"][0] == 1.0
    assert vc["2020-03-18"][0] == 1.001
    assert "2020-03-19" not in vc                 # the last trade is more than 24 h old at that midnight


def test_peg_trade_entry_next_close_exit_first_repeg():
    closes = {"2020-01-01": 0.99, "2020-01-02": 0.985, "2020-01-03": 0.995, "2020-01-04": 0.9992, "2020-01-05": 0.99}
    tr = m.peg_trade("2020-01-01", closes.get)
    assert (tr["entry"], tr["exit"], tr["repeg"], tr["days"]) == ("2020-01-02", "2020-01-04", True, 2)
    assert tr["gross"] == pytest.approx(0.9992 / 0.985 - 1)
    closes["2020-01-04"] = 0.99
    tr = m.peg_trade("2020-01-01", closes.get)
    assert (tr["exit"], tr["repeg"]) == ("2020-01-05", False)
    assert m.peg_trade("2020-01-03", closes.get) is None


def _episodes(gross, coins=("USDT", "USDC")):
    return [{"coin": coins[i % len(coins)], "signal": f"2019-{1 + i % 12:02d}-{1 + i // 12:02d}", "gross": g, "repeg": g > 0}
            for i, g in enumerate(gross)]


def test_t330_planted_passes():
    rng = np.random.default_rng(0)
    j = m.peg_test(_episodes(0.012 + rng.normal(0, 0.002, 12)))
    assert j["verdict"] == "supported", j["why"]


def test_t330_null_fails():
    rng = np.random.default_rng(1)
    j = m.peg_test(_episodes(rng.normal(0, 0.002, 12)))
    assert j["verdict"] == "not_supported", j["why"]


def test_t330_below_ten_is_too_few_events_even_when_decisive():
    j = m.peg_test(_episodes([-0.01, -0.011, -0.012, -0.009, -0.01, -0.0105]))
    assert j["verdict"] == "inconclusive" and j["rule5_decisive"] is True
    assert "too few events" in j["criteria"][0][0]


# ======================================================================================================= T-365 ==

def lst_world(spike_every, seed=0, base=0.002, spike=0.03):
    rng = np.random.default_rng(seed)
    days = cdays("2020-12-23", "2026-10-14")
    disc = base + rng.normal(0, 0.001, len(days))
    if spike_every:
        for k in range(10, len(days) - 12, spike_every):
            prof = [spike, spike, spike * 0.8, spike * 0.5, spike * 0.3, spike * 0.15, 0.006, 0.004]
            for i, v in enumerate(prof):
                disc[k + i] = v
    return days, 1.0 - disc


def test_lst_episodes_rule_and_timing():
    days = cdays("2023-05-01", "2023-06-30")
    disc = np.full(len(days), 0.001)
    disc[5] = 0.02                                   # one day only: no signal
    disc[10:13] = 0.02                               # signal at index 11 (second day)
    ratio = 1 - disc
    live = m.lst_episodes(days, ratio, start=days[0], end=days[-1])
    lag = m.lst_episodes(days, ratio, start=days[0], end=days[-1], timing="lagged")
    assert [e["signal"] for e in live] == [days[11]] and live[0]["entry"] == days[11] and live[0]["exit"] == days[21]
    assert lag[0]["entry"] == days[12] and lag[0]["exit"] == days[22]
    assert live[0]["net"] == pytest.approx(math.log(ratio[21] / ratio[11]) - 0.003)
    # non-overlapping: a second spike inside the hold is skipped
    disc[15:17] = 0.02
    assert len(m.lst_episodes(days, 1 - disc, start=days[0], end=days[-1])) == 1


def test_t365_planted_passes():
    days, ratio = lst_world(60, seed=1)
    j = m.lst_test(days, ratio, n_shuffle=200)
    assert j["n"] >= 15
    assert j["verdict"] == "supported", j["why"]


def test_t365_null_is_insufficient_events():
    days, ratio = lst_world(0, seed=2)
    j = m.lst_test(days, ratio, n_shuffle=50)
    assert j["n"] == 0 and j["verdict"] == "inconclusive"
    assert "insufficient events" in j["why"]


def test_t365_few_losing_episodes_stay_inconclusive():
    days, ratio = lst_world(300, seed=3, spike=0.03)
    disc = 1 - ratio
    starts = [k for k in range(10, len(days) - 12, 300)]
    for k in starts:                                    # every spike widens further after the entry: losing trades
        disc[k + 2: k + 13] = 0.06
    j = m.lst_test(days, 1 - disc, n_shuffle=50)
    assert 0 < j["n"] < 15 and j["verdict"] == "inconclusive"


# ======================================================================================================= T-366 ==

def drift_world(rate, sd=0.002, seed=0):
    rng = np.random.default_rng(seed)
    days = cdays("2023-04-12", "2026-09-30")
    t = np.arange(len(days)) / 365.0
    noise = np.zeros(len(days))
    for i in range(1, len(days)):
        noise[i] = 0.9 * noise[i - 1] + rng.normal(0, sd)
    return days, np.exp(rate * t + noise)


def test_t366_planted_passes():
    days, r = drift_world(0.025)
    j = m.drift_test(days, r)
    assert j["verdict"] == "supported", j["why"]
    assert j["drift"]["slope"] == pytest.approx(0.025, abs=0.003)


def test_t366_null_fails():
    days, r = drift_world(0.0, seed=1)
    assert m.drift_test(days, r)["verdict"] == "not_supported"


def test_t366_above_band_fails_and_band_readings_disagree_is_undecided():
    days, r = drift_world(0.06, seed=2)
    assert m.drift_test(days, r)["verdict"] == "not_supported"
    days, r = drift_world(0.0346, sd=0.0, seed=3)            # log rate 3.46% inside, compounded 3.52% outside
    j = m.drift_test(days, r)
    assert j["verdict"] == "inconclusive" and "disagree" in j["why"]


def test_rolling_share():
    days, r = drift_world(0.03, sd=0.0)
    assert m.rolling_share(days, r)["share_positive"] == 1.0


# ======================================================================================================= T-419 ==

def _bars_of(days, r, lv, start=100.0):
    c = start * np.cumprod(1 + r)
    o = np.concatenate([[start], c[:-1]])
    return {"days": list(days), "open": o, "close": c, "adj": c.copy(), "aopen": o.copy(), "volume": 1e6 * np.exp(lv)}


def hvp_world(drift, seed=0, start="2011-01-03", end="2026-09-30", n_etf=6):
    rng = np.random.default_rng(seed)
    sess = bdays(start, end)
    cal = cdays(start, end)
    n, nc = len(sess), len(cal)
    mr, mlv = rng.normal(0.0003, 0.01, n), rng.normal(0, 0.3, n)
    raw = {"SPY": ("etf", sess, mr, mlv)}
    mlv_by = dict(zip(sess, mlv))
    for i in range(n_etf):
        raw[f"E{i}"] = ("etf", sess, (0.5 + 0.1 * i) * mr + rng.normal(0, 0.01, n), 0.5 * mlv + rng.normal(0, 0.3, n))
    for k in ("C1-USD", "C2-USD"):
        lvm = np.array([0.3 * mlv_by.get(d, 0.0) for d in cal])
        raw[k] = ("crypto", cal, rng.normal(0.0005, 0.03, nc), lvm + rng.normal(0, 0.4, nc))

    def build(rr):
        bars = {k: _bars_of(v[1], rr[k], v[3]) for k, v in raw.items()}
        mkt = m.hvp_market(bars["SPY"])
        return [m.hvp_asset(bars[k], raw[k][0], mkt, None) for k in raw]
    rr = {k: v[2].copy() for k, v in raw.items()}
    assets = build(rr)
    if drift:
        for (k, v), a in zip(raw.items(), assets):
            if k == "SPY":
                continue
            f = m.hvp_flags(a, 0.90, "idio")
            d = drift if v[0] == "etf" else 2 * drift
            for j in np.flatnonzero(f):
                rr[k][j + 1: j + 11] += d
        assets = build(rr)
    return assets, list(raw)


def test_hvp_flags_need_volume_surprise_and_small_move():
    a = {"u": np.r_[np.zeros(60), 5.0, 5.0], "x": np.zeros(62), "r": np.r_[np.zeros(60), 0.001, 0.5],
         "sig": np.full(62, 0.01)}
    a["u"][:60] = np.random.default_rng(0).normal(0, 1, 60)
    f = m.hvp_flags(a, 0.9, "idio")
    assert f[60] and not f[61]                          # day 61 moved more than 2 sigma


def test_placebo_finds_no_effect_in_shuffled_noise():
    assets, names = hvp_world(0.0, seed=5, start="2016-01-04")
    A = [a for a, nm in zip(assets, names) if nm != "SPY"]
    fl = [m.hvp_flags(a, 0.9, "idio") & np.isfinite(a["fwd"][10]["AR"]) for a in A]
    obs = float(np.concatenate([a["fwd"][10]["AR"][f] for a, f in zip(A, fl)]).mean())
    p = m.placebo_p(A, fl, 10, obs, "2005-01-01", "2026-12-31", 300)
    assert 0.02 < p["p"] < 0.98 and p["n_shift"] == 300


def test_cal_portfolio_weights_and_costs():
    days = cdays("2020-01-01", "2020-01-31")
    a = {"days": days, "ords": np.array([m._ord(d) for d in days]), "kind": "crypto", "n": len(days),
         "AR1": np.full(len(days), 0.01)}
    f = np.zeros(len(days), bool)
    f[3] = True
    p = m.cal_portfolio([a], [f], 5, cost=0.001, cap=0.05, start="2020-01-01")
    assert p["days_active"] == 5
    assert p["gross"][:5] == pytest.approx([0.05 * 0.01] * 5)
    assert p["gross"][:5].sum() - p["net"].sum() == pytest.approx(0.05 * 0.001)     # one round trip on a 5% weight


def test_t419_planted_passes():
    assets, names = hvp_world(0.003, seed=1)
    j = m.hvp_test(assets, names=names, mkt_sym="SPY", n_shift=300)
    assert j["n"] >= 800
    assert j["verdict"] == "supported", j["why"]


def test_t419_null_fails():
    assets, names = hvp_world(0.0, seed=2)
    j = m.hvp_test(assets, names=names, mkt_sym="SPY", n_shift=300)
    assert j["verdict"] == "not_supported", j["why"]
    assert j["mean_ar"] < 0.005


def test_t419_halves_are_date_halves():
    """Regression: the walk-forward halves split by date (midpoint of the event span), not by event count, so no date
    lies in both halves; each half reports its date range and event count."""
    assets, names = hvp_world(0.0, seed=4, start="2016-01-04", n_etf=3)
    j = m.hvp_test(assets, names=names, mkt_sym="SPY", n_shift=50)
    h = j["halves"]
    lo, hi = j["first_event"], j["last_event"]
    mid = date.fromordinal((date.fromisoformat(lo).toordinal() + date.fromisoformat(hi).toordinal()) // 2).isoformat()
    assert h["split"] == mid and "date halves" in h["basis"]
    assert h["first"]["from"] == lo and h["second"]["to"] == hi
    assert h["first"]["to"] < mid <= h["second"]["from"]                      # no date on both sides
    assert h["first"]["n"] + h["second"]["n"] == j["n"]
    # same-day events: a count split at n // 2 would cut a date in two; the date split never does
    A = [a for a, nm in zip(assets, names) if nm != "SPY"]
    dts = [a["days"][i] for a in A
           for i in np.flatnonzero(m.hvp_flags(a, 0.9, "idio") & m._in_window(a, m.T419_START, m.T419_END)
                                   & np.isfinite(a["fwd"][10]["AR"]))]
    assert len(dts) == j["n"] and sum(d < mid for d in dts) == h["first"]["n"]


# ======================================================================================================= T-424 ==

def test_cb_members_point_in_time_and_exclusions():
    days = cdays("2021-01-01", "2021-03-31")
    daily = {p: {d: (1.0, v) for d in days} for p, v in (("A-USD", 100.0), ("B-USD", 50.0), ("C-USD", 10.0), ("BTC-USD", 1e6),
                                                         ("USDT-USD", 1e6), ("CBETH-USD", 1e5), ("D-EUR", 1e6))}
    daily["C-USD"]["2021-02-15"] = (1.0, 1e5)            # a one-day spike: C enters the next day, not the same day
    del daily["B-USD"]["2021-02-20"]                      # B did not trade on 02-20: out of the basket on 02-21
    mem = m.cb_members(daily, "2021-02-10", "2021-03-01", top=2)
    assert mem["2021-02-15"] == ["A-USD", "B-USD"]
    assert mem["2021-02-16"] == ["C-USD", "A-USD"]
    assert mem["2021-02-21"] == ["C-USD", "A-USD"]
    assert mem["2021-02-22"] == ["C-USD", "A-USD"]                                     # C's spike is still in the window
    assert all("BTC-USD" not in v and "USDT-USD" not in v and "CBETH-USD" not in v for v in mem.values())


def test_hourly_grid_returns_fill_missing_hours():
    t0 = epoch("2021-01-01")
    ts = np.array([t0 + 3600, t0 + 2 * 3600, t0 + 5 * 3600], np.int64)
    r = m.hourly_grid_returns(ts, np.array([100.0, 110.0, 121.0]), t0, 7)
    assert np.isnan(r[:2]).all()
    assert r[2] == pytest.approx(0.1) and r[3] == 0.0 and r[4] == 0.0 and r[5] == pytest.approx(0.1) and r[6] == 0.0


def test_follow_rule_costs_and_signal_lag():
    lead = np.array([0.0, 0.02, 0.02, 0.0, 0.0])
    bsk = np.array([0.0, 0.0, 0.01, 0.01, 0.01])
    fr = m.follow_rule(lead, bsk, np.zeros(5), 0.01, 0.005)
    assert fr["pos"].tolist() == [0, 0, 1, 1, 0]
    assert fr["net"].tolist() == pytest.approx([0, 0, 0.01 - 0.0025, 0.01, -0.0025])


def leadlag_world(beta, seed=0, n=45000):
    rng = np.random.default_rng(seed)
    lead = rng.normal(0, 0.01, n)
    bsk = rng.normal(0, 0.004, n)
    bsk[1:] += beta * lead[:-1]
    fit = np.zeros(n, bool); fit[:15000] = True
    return lead, bsk, np.full(n, 0.04 / 8760), fit, ~fit


def test_t424_planted_passes():
    lead, bsk, rf, fit, test = leadlag_world(0.9, seed=1)
    pre = m.leadlag_test(lead, bsk, rf, fit, test, [], n_boot=200, reps=2)
    fam = [pre["sharpe"] / math.sqrt(8760)] + [0.0] * 9
    j = m.leadlag_test(lead, bsk, rf, fit, test, fam, n_boot=200, reps=2)
    assert j["n"] >= 20000 and j["coef"] > 0.5
    assert j["verdict"] == "supported", j["why"]


def test_t424_null_fails():
    lead, bsk, rf, fit, test = leadlag_world(0.0, seed=2)
    j = m.leadlag_test(lead, bsk, rf, fit, test, [0.0] * 10, n_boot=200, reps=2)
    assert j["verdict"] == "not_supported", j["why"]


def test_stationary_test_size():
    x = np.random.default_rng(3).normal(0, 1, 2000)
    t = m.stationary_test(x, 24, 300, 0)
    assert 0.02 < t["p"] < 0.98
    t = m.stationary_test(x + 0.2, 24, 300, 0)
    assert t["p"] < 0.01


# ============================================================================================ fake archive ==

class FakeArchive:
    def __init__(self, bundles, created="2026-10-16T12:00:00+00:00"):
        self.bundles = bundles
        self.created = created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created, name=name, kind="data")

    def load(self, name):
        return iter(self.bundles[name])

    def entries(self, kind=None, tag=None):
        return [SimpleNamespace(name=n, kind="data", created_at=self.created) for n in sorted(self.bundles)]


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _yahoo_rows(days, close, vol=None, hh=14.5, crypto=False):
    rows = []
    vol = np.full(len(days), 1e6) if vol is None else vol
    prev = close[0]
    for d, c, v in zip(days, close, vol):
        t = epoch(d) + (0 if crypto else int(hh * 3600))
        rows.append({"available_at": _iso(t + 86400), "value": {"t": t, "open": float(prev), "high": float(c), "low": float(c),
                                                                "close": float(c), "adjclose": float(c), "volume": float(v)}})
        prev = c
    return rows


def _cb_rows(days, close, vol):
    out = []
    prev = close[0]
    for d, c, v in zip(days, close, vol):
        t = epoch(d)
        out.append({"available_at": _iso(t + 86400), "value": {"symbol": "x", "t": t, "open": float(prev), "high": float(c),
                                                               "low": float(c), "close": float(c), "volume": float(v)}})
        prev = c
    return out


def _hourly_rows(ts, close):
    return [{"available_at": _iso(int(t) + 3600), "value": {"t": int(t), "open": float(c), "high": float(c), "low": float(c),
                                                           "close": float(c), "volume": 1.0}} for t, c in zip(ts, close)]


def _full_archive():
    rng = np.random.default_rng(7)
    b = {}
    # T-328: IBIT, BTC hourly (2022-06..2023-06 in full for T-424, plus every IBIT session's close candle), iShares
    days, close, spot, bps, ref = ibit_world(0.05, seed=4)
    b[m.IBIT_B] = _yahoo_rows(days, close)
    b[m.FBTC_B] = _yahoo_rows(days, close * 1.6)
    hrs = np.arange(epoch("2022-06-01"), epoch("2023-06-30"), 3600)
    btc_h = 20000 * np.cumprod(1 + rng.normal(0, 0.006, hrs.size))
    ts = list(hrs) + [m.close_bar_start(d) for d in days]
    cl = list(btc_h) + list(spot)
    o = np.argsort(ts)
    b[m.CB_BTC_H] = _hourly_rows(np.array(ts)[o], np.array(cl)[o])
    b[m.ISH_SNAP] = [{"kind": "snapshot", "available_at": "2026-10-15T21:00:00+00:00",
                      "value": {"btc_per_share": bps, "nav_as_of": "2026-10-15"}}]
    b[m.ISH_PREM] = [{"kind": "premium-discount", "available_at": _iso(epoch(d) + 86400 + 14 * 3600),
                      "value": {"day": d, "premium_discount_pct": float(100 * (close[i] / (bps * m.fee_factor([d], ref)[0] * spot[i]) - 1))}}
                     for i, d in enumerate(days) if d >= "2025-01-02"]
    # T-330: Yahoo USDT/USDC closes with 12 discount episodes, Kraken trades in their windows
    cd = cdays("2017-11-09")
    usdt = np.full(len(cd), 1.0) + rng.normal(0, 0.0003, len(cd))
    usdc = np.full(len(cd), 1.0) + rng.normal(0, 0.0003, len(cd))
    sig = {"USDT": [], "USDC": []}
    for k, i in enumerate(range(200, len(cd) - 20, 250)):
        coin = "USDT" if k % 2 == 0 else "USDC"
        arr = usdt if coin == "USDT" else usdc
        arr[i: i + 2] = 0.99
        arr[i + 2] = 0.995
        sig[coin].append(cd[i])
    b[m.USDT_Y] = _yahoo_rows(cd, usdt, crypto=True)
    b[m.USDC_Y] = _yahoo_rows(cd, usdc, crypto=True)
    kr = []
    cix = {d: i for i, d in enumerate(cd)}
    for coin, ds in sig.items():
        arr = usdt if coin == "USDT" else usdc
        for dd in ds:
            s, e = epoch(dd) - 86400, epoch(dd) + 7 * 86400
            for t in range(s + 600, e, 3600):
                kr.append({"kind": "trade", "available_at": _iso(t), "value": {"coin": coin, "signal_day": dd, "time": float(t),
                                                                               "price": float(arr[cix[m._dday(t)]])}})
            kr.append({"kind": "episode-window", "available_at": _iso(e),
                       "value": {"coin": coin, "signal_day": dd, "start": _iso(s), "end": _iso(e), "complete": True}})
    b[m.KR_EP] = kr
    b[m.CB_USDT] = _cb_rows(cd[1300:], usdt[1300:], np.full(len(cd) - 1300, 1e7))
    # T-365 / T-366
    sd = cdays("2020-12-23")
    eth = 1000 * np.cumprod(1 + rng.normal(0, 0.03, len(sd)))
    b[m.ETH_Y] = _yahoo_rows(sd, eth, crypto=True)
    b[m.STETH_Y] = _yahoo_rows(sd, eth * (1 - 0.002 - np.abs(rng.normal(0, 0.002, len(sd)))), crypto=True)
    cbd = cdays("2022-08-25")
    ratio = np.exp(0.028 * np.arange(len(cbd)) / 365 + rng.normal(0, 0.001, len(cbd)))
    b[m.CB_CBETH_ETH] = _cb_rows(cbd, ratio, np.full(len(cbd), 50.0))
    b[m.CBETH_Y] = _yahoo_rows(sd, eth * np.exp(0.028 * np.arange(len(sd)) / 365), crypto=True)
    # T-419: ETFs from 2012 on a common market, Coinbase BTC/ETH daily, DTB3, VIX
    sess = bdays("2012-01-03", "2026-10-14")
    mr, mlv = rng.normal(0.0003, 0.01, len(sess)), rng.normal(0, 0.3, len(sess))
    for s in list(m.T419_ETFS) + list(m.T419_EXTRA):
        r = mr if s == "SPY" else 0.7 * mr + rng.normal(0, 0.008, len(sess))
        lv = mlv if s == "SPY" else 0.5 * mlv + rng.normal(0, 0.3, len(sess))
        b[m.dh(s)] = _yahoo_rows(sess, 100 * np.cumprod(1 + r), 1e6 * np.exp(lv))
    cal = cdays("2015-07-20")
    for p in ("BTC-USD", "ETH-USD"):
        px = 300 * np.cumprod(1 + rng.normal(0.001, 0.03, len(cal)))
        b[m.cbd(p)] = _cb_rows(cal, px, 1e4 * np.exp(rng.normal(0, 0.4, len(cal))))
    b[m.DTB3_B] = [{"available_at": _iso(epoch(d) + 86400), "value": {"day": d, "value": 4.0}} for d in bdays("2002-01-02")]
    b[m.VIX_B] = [{"available_at": _iso(epoch(d) + 79200), "value": {"day": d, "close": float(15 + 20 * (i % 50 == 0))}}
                  for i, d in enumerate(sess)]
    # T-424: products snapshot, Coinbase daily for 4 alts + a stablecoin, hourly bundles (2022-06..2023-06)
    alts = ("ETH-USD", "AAA-USD", "BBB-USD", "CCC-USD")
    b["coinbase-products-2026-10-16"] = [{"available_at": "2026-10-16T00:00:00+00:00",
                                          "value": {"id": p, "fx_stablecoin": p == "USDC-USD"}} for p in alts + ("BTC-USD", "USDC-USD")]
    hd = cdays("2022-05-01", "2023-06-30")
    for p in alts[1:] + ("USDC-USD",):
        b[m.cbd(p)] = _cb_rows(hd, 10 * np.cumprod(1 + rng.normal(0, 0.04, len(hd))), 1e5 * np.exp(rng.normal(0, 0.5, len(hd))))
    for p in alts:
        b[m.cbh(p)] = _hourly_rows(hrs, 10 * np.cumprod(1 + rng.normal(0, 0.008, hrs.size)))
    for s in ("GLD", "SLV", "GDX"):
        b.setdefault(m.dh(s), _yahoo_rows(sess, 100 * np.cumprod(1 + rng.normal(0, 0.01, len(sess)))))
    return FakeArchive(b)


@pytest.fixture(scope="module")
def fake():
    return _full_archive()


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_every_harness_runs_json_safe(fake, name):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES[name](fake)
    json.dumps(stat, allow_nan=False)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert isinstance(n, int) and n >= 0
    assert " — " in reason
    assert "missing_bundles" not in stat


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason and " — " in reason


def test_optional_bundles_are_optional(fake):
    bb = dict(fake.bundles)
    for k in (m.FBTC_B, m.ISH_PREM, m.CB_USDT, m.CBETH_Y, m.VIX_B):
        bb.pop(k, None)
    arch = FakeArchive(bb)
    for name in ("b6c_cryptovenue_ibit_premium_fade", "b6c_cryptovenue_stablecoin_peg_reversion",
                 "b6c_cryptovenue_cbeth_staking_drift", "b6c_cryptovenue_high_volume_premium"):
        m._CACHE.clear()
        stat, n, verdict, reason = m.HARNESSES[name](arch)
        assert "missing_bundles" not in stat and n > 0, name


def test_t330_harness_reprices_at_kraken(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_cryptovenue_stablecoin_peg_reversion"](fake)
    assert n >= 10 and all(e.get("venue") == "kraken" for e in stat["episodes"])
    assert all(e["entry"] > e["signal"] for e in stat["episodes"])


def test_t328_harness_reports_park_and_calibration(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_cryptovenue_ibit_premium_fade"](fake)
    assert isinstance(stat["park_condition"], bool) and "park" in reason.lower()
    assert stat["calibration_vs_official"]["corr"] > 0.99          # the fake official premium is the synthetic one
    assert n == min(stat["per_timing"]["live"]["n"], stat["per_timing"]["lagged"]["n"])


def test_maps_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-328", "T-330", "T-365", "T-366", "T-419", "T-424"}
    assert all(k.startswith("b6c_cryptovenue_") and k == k.lower() for k in m.HARNESSES)
