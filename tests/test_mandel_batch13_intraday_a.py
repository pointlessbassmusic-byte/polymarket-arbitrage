"""Tests for mandel/experiments/batch13_intraday_a.py (T-659, T-669, T-660, T-664): point-in-time signal construction
(shocks after the decision time never move the signal) and rule-9 inconclusive verdicts when bundles are missing."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from mandel.experiments import batch13_intraday_a as M


class _NoArchive:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = M.HARNESSES[name](_NoArchive())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_names_harnesses():
    assert set(M.THEORY_MAP) == {"T-659", "T-669", "T-660", "T-664"}
    assert all(v in M.HARNESSES for v in M.THEORY_MAP.values())


# ------------------------------------------------------------------------------------------------------ T-659 --

def _ts(day: str, hour: int) -> float:
    d = datetime.fromisoformat(day).replace(hour=hour, tzinfo=M.NY)
    return d.timestamp()


def _bars(days, rng):
    """Synthetic ES-like hourly bars keyed (ET day, ET hour) for every hour of the given days."""
    out = {}
    px = 6000.0
    for d in days:
        for h in range(24):
            o = px
            c = o * (1 + rng.normal(0, 5e-4))
            out[(d, h)] = (o, max(o, c) + 0.5, min(o, c) - 0.5, c, _ts(d, h))
            px = c
    return out


def test_t659_signal_ignores_bars_after_its_close():
    rng = np.random.default_rng(1)
    days = ["2025-06-02", "2025-06-03", "2025-06-04"]
    bars = _bars(days, rng)
    base = M.closing_hour_signal(bars, "2025-06-03")
    nights0 = {r["day"]: r for r in M.t659_nights(bars, "ES_F", "2025-06-02", "2025-06-03")}
    shocked = dict(bars)
    for (d, h), b in bars.items():
        if (d == "2025-06-03" and h >= 16) or d > "2025-06-03":
            shocked[(d, h)] = (b[0] * 1.05, b[1] * 1.05, b[2] * 0.95, b[3] * 0.9, b[4])
    after = M.closing_hour_signal(shocked, "2025-06-03")
    assert after["down"] == base["down"] and after["ret"] == base["ret"]
    assert after["known_at"] == _ts("2025-06-03", 15) + 3600.0
    nights1 = {r["day"]: r for r in M.t659_nights(shocked, "ES_F", "2025-06-02", "2025-06-03")}
    assert nights1["2025-06-03"]["down"] == nights0["2025-06-03"]["down"]
    assert nights1["2025-06-03"]["net"] != nights0["2025-06-03"]["net"]      # the shocked trade bar moves the outcome only


def test_t659_trade_is_the_0200_bar_and_cost():
    rng = np.random.default_rng(2)
    bars = _bars(["2025-06-03", "2025-06-04"], rng)
    r = [x for x in M.t659_nights(bars, "ES_F", "2025-06-03", "2025-06-03")][0]
    o, _, _, c, _ = bars[("2025-06-04", 2)]
    assert r["gross"] == pytest.approx(c / o - 1)
    assert r["net"] == pytest.approx(c / o - 1 - (0.25 + 1.0 / 5.0) / o)


def test_t659_calendar_flags():
    assert M.ny_london_offset(_ts("2025-03-12", 2)) == -4.0          # US on EDT, UK still on GMT
    assert M.ny_london_offset(_ts("2025-06-11", 2)) == -5.0
    assert M.ny_london_offset(_ts("2025-10-29", 2)) == -4.0          # UK back on GMT, US still on EDT
    ec = M.early_closes(2024, 2025)
    assert {"2024-07-03", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24"} <= ec
    wins = M.roll_windows(2025, 2025)
    assert M.in_windows("2025-12-16", wins) and M.in_windows("2025-03-13", wins) and not M.in_windows("2025-03-12", wins)
    rng = np.random.default_rng(3)
    # a Friday condition (Monday trade = Sunday reopening) never forms a night
    bars = _bars(["2025-06-06", "2025-06-07", "2025-06-08", "2025-06-09"], rng)
    assert M.t659_nights(bars, "ES_F", "2025-06-06", "2025-06-08") == []


def test_t659_session_indexed_series():
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1e-3, 40)
    flag = rng.random(40) < 0.5
    d = M.cond_series(x, flag)
    assert d.size == 40                                                # one entry per eligible SESSION, not per trade
    assert d.mean() == pytest.approx(x[flag].mean())
    x2 = x.copy()
    x2[~flag] += 0.05                                                  # complement nights never enter the series
    np.testing.assert_allclose(M.cond_series(x2, flag), d)
    B = M.cond_boot(x, flag, 5)
    assert B["n"] == int(flag.sum()) and B["n_sessions"] == 40 and B["mean"] == pytest.approx(x[flag].mean())
    assert B["pg"] is not None and B["t"] is not None and B["pg_trades"] is not None


def test_t659_maker_needs_trade_through():
    r = {"o": 100.0, "h": 100.5, "l": 99.75, "c": 100.25, "tick": 0.25, "comm_pts": 0.2}
    assert M.maker_net(r) is None                                      # low touches the bid but does not trade through
    r["l"] = 99.5
    assert M.maker_net(r) == pytest.approx((100.25 - 0.125 - 99.75) / 99.75 - 0.2 / 99.75)


# ------------------------------------------------------------------------------------------------------ T-669 --

def _hbars(rng):
    out, px = {}, 500.0
    for k in M.T669_BAR_TIMES:
        o = px
        c = o * (1 + rng.normal(0, 2e-3))
        out[k] = (o, c)
        px = c
    return out


def test_t669_ratio_uses_open_implied_and_session_bars_only():
    rng = np.random.default_rng(4)
    hb = _hbars(rng)
    sv = M.session_variance(hb, 501.0)
    assert len(sv["r"]) == 7
    pts = [hb["09:30"][0]] + [hb[k][1] for k in M.T669_BAR_TIMES[:-1]] + [501.0]
    assert sv["rv"] == pytest.approx(float(np.sum(np.diff(np.log(pts)) ** 2)))
    # the 15:30 bar's own close is not an input (the official close ends the last 30-minute interval)
    hb2 = dict(hb)
    hb2["15:30"] = (hb["15:30"][0], hb["15:30"][1] * 1.2)
    assert M.session_variance(hb2, 501.0)["rv"] == sv["rv"]
    assert M.implied_session_var(16.0) == pytest.approx(0.16 ** 2 * 390 / 525600)
    hb3 = dict(hb)
    del hb3["15:30"]
    assert M.session_variance(hb3, 501.0) is None                     # early closes (no 15:30 bar) drop out


def test_t669_matching_rules():
    sessions = []
    d = datetime(2025, 1, 2)
    while len(sessions) < 80:
        if d.weekday() < 5:
            sessions.append(d.date().isoformat())
        d += timedelta(days=1)
    events = [sessions[20], sessions[55]]
    valid = set(sessions)
    excluded = set(events) | {sessions[25]}
    sets = M.match_sets(events, sessions, valid, excluded)
    assert [e for e, _ in sets] == events and all(len(ms) == 3 for _, ms in sets)
    for e, ms in sets:
        assert all(datetime.fromisoformat(m).weekday() == datetime.fromisoformat(e).weekday() for m in ms)
        assert all(abs(sessions.index(m) - sessions.index(e)) <= 10 for m in ms)
        assert sessions[25] not in ms
    # a day already matched to an earlier event is never reused
    near = M.match_sets([sessions[20], sessions[25]], sessions, valid, {sessions[20], sessions[25]})
    assert not set(near[0][1]) & set(near[1][1])


def _t669_synth(rng, n=130):
    """Synthetic NYSE sessions with SPY closes, VIX1D (open, close) and the 7 regular hourly SPY bars."""
    from mandel.experiments import batch6c_cal as CAL
    sd, d = [], datetime(2025, 1, 2).date()
    while len(sd) < n:
        if CAL.is_nyse_session(d):
            sd.append(d.isoformat())
        d += timedelta(days=1)
    sc, vx, hb, px = [], {}, {}, 500.0
    for s in sd:
        bars = {}
        for k in M.T669_BAR_TIMES:
            o = px
            c = o * (1 + rng.normal(0, 2e-3))
            bars[k] = (o, c)
            px = c
        hb[s] = bars
        sc.append(px * (1 + rng.normal(0, 5e-4)))
        vx[s] = (float(rng.uniform(10, 20)), float(rng.uniform(10, 20)))
    return sd, np.array(sc), vx, hb


def test_t669_implied_leg_and_matching_ignore_post_open_values():
    rng = np.random.default_rng(5)
    sd, sc, vx, hb = _t669_synth(rng)
    fomc, cpi, nfp = [sd[30], sd[75]], [sd[45]], [sd[60]]
    rows1 = M.t669_rows(sd, sc, vx, hb, sd[0], sd[-1])
    K1 = M.t669_calendar(rows1, sd, fomc, cpi, nfp)
    assert [e for e, _ in K1["S_f"]] == fomc and all(len(ms) >= 1 for _, ms in K1["S_f"])
    for d, r in rows1.items():                                       # logR's denominator is the VIX1D OPEN only
        assert r["iv"] == pytest.approx(M.implied_session_var(vx[d][0]))
    # shock everything known only after the event days' VIX1D open: their VIX1D close, every bar close (the R values)
    # and the official closes from the first event on
    vx2 = {d: ((v[0], v[1] * 3.0) if d in fomc + cpi + nfp else v) for d, v in vx.items()}
    hb2 = {d: {k: (o, c * (1 + rng.normal(0, 4e-3))) for k, (o, c) in b.items()} for d, b in hb.items()}
    sc2 = sc.copy()
    sc2[sd.index(fomc[0]):] *= 1.02
    rows2 = M.t669_rows(sd, sc2, vx2, hb2, sd[0], sd[-1])
    K2 = M.t669_calendar(rows2, sd, fomc, cpi, nfp)
    assert set(rows2) == set(rows1)
    for d in rows1:
        assert rows2[d]["iv"] == rows1[d]["iv"]                      # the implied leg never moves
    for e in fomc + cpi + nfp:                                       # the event day's VIX1D close (x3) is not in iv
        assert rows2[e]["iv"] == pytest.approx(M.implied_session_var(vx[e][0]))
    assert K2["S_f"] == K1["S_f"] and K2["S_p"] == K1["S_p"]         # matching is calendar-only
    assert K2["excluded"] == K1["excluded"]
    assert any(rows2[d]["logR"] != rows1[d]["logR"] for d in rows1)  # the outcome (realised variance) does move
    # the event day's own VIX1D close enters only the NEXT session's close-to-close robustness row
    e = fomc[0]
    nxt = sd[sd.index(e) + 1]
    vx3 = dict(vx)
    vx3[e] = (vx[e][0], vx[e][1] * 3.0)
    rows3 = M.t669_rows(sd, sc, vx3, hb, sd[0], sd[-1])
    assert rows3[e]["logR"] == rows1[e]["logR"] and rows3[e]["logR_cc"] == rows1[e]["logR_cc"]
    assert rows3[nxt]["logR_cc"] != rows1[nxt]["logR_cc"]
    vx4 = dict(vx)
    vx4[e] = (vx[e][0] * 1.5, vx[e][1])                              # sanity: the open IS the input
    assert M.t669_rows(sd, sc, vx4, hb, sd[0], sd[-1])[e]["iv"] != rows1[e]["iv"]


def test_t669_permutation_shift_null():
    rng = np.random.default_rng(6)
    per = [(1.0 + rng.normal(0, 0.1), rng.normal(0, 0.1, 3)) for _ in range(30)]
    obs, pg, pl, nd = M.set_perm_p(per, 0.2)
    assert obs == pytest.approx(np.mean([e for e, _ in per]) - 0.2 - np.mean(np.concatenate([m for _, m in per])))
    assert pg < 0.01
    obs2, pg2, _, _ = M.set_perm_p(per, 5.0)
    assert pg2 > 0.9


# ------------------------------------------------------------------------------------------------------ T-660 --

def test_t660_signal_known_at_formation_open():
    rng = np.random.default_rng(7)
    D, N = 120, 6
    C = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (D, N)), axis=0))
    O = C * np.exp(rng.normal(0, 0.003, (D, N)))
    Dv = np.zeros((D, N))
    f = 80
    s0 = M.overnight_signal(M.overnight_returns(O, C, Dv), f, 21)
    C2, O2, Dv2 = C.copy(), O.copy(), Dv.copy()
    C2[f:] *= 1.3                       # the formation session's close (the MOC buy) and everything later
    O2[f + 1:] *= 0.7
    Dv2[f + 1:] = 5.0
    s1 = M.overnight_signal(M.overnight_returns(O2, C2, Dv2), f, 21)
    np.testing.assert_allclose(s0, s1)
    O3 = O.copy()
    O3[f] *= 1.01                       # the formation session's open is inside the signal
    assert not np.allclose(M.overnight_signal(M.overnight_returns(O3, C, Dv), f, 21), s0)


def test_t660_dividend_added_back():
    O = np.array([[10.0], [10.2]])
    C = np.array([[10.0], [10.1]])
    Dv = np.array([[0.0], [0.3]])
    R = M.overnight_returns(O, C, Dv)
    assert R[1, 0] == pytest.approx((10.2 + 0.3) / 10.0 - 1)


def test_t660_caps_point_in_time():
    from mandel.experiments import batch6c_stockxs as SX
    days = ["2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-03"]
    f = 4                                                              # formation session 2025-01-31
    syms = ["AAA", "AAB", "BBB", "CCC"]                                # AAA/AAB: two member classes of issuer 101
    C = np.tile(np.array([50.0, 40.0, 30.0, 20.0]), (len(days), 1))
    shares = {101: [(SX._et_ts("2025-01-10", 16, 0), "2024-12-31", 1000.0),
                    (SX._et_ts(days[f], 9, 31), "2025-01-15", 5000.0)],          # accepted after 09:30 of f
              202: [(SX._et_ts("2024-11-01", 16, 0), "2023-09-30", 300.0)]}      # 489 days old at f: stale
    inp = {"base": {"ciks": [101, 101, 202, None]}, "days": days, "syms": syms, "C": C, "shares": shares,
           "splits": {"AAA": [("2025-01-20", 2.0)], "AAB": [], "BBB": [], "CCC": []}}
    cols = np.arange(4)
    caps = M.caps_at(inp, f, cols)
    # earlier filing only, previous close, split after the shares' date, count split across the issuer's two classes
    assert caps[0] == pytest.approx(50.0 * 1000.0 * 2.0 / 2)
    assert caps[1] == pytest.approx(40.0 * 1000.0 / 2)
    assert np.isnan(caps[2]) and np.isnan(caps[3])                     # older than 456 days; no CIK
    C2 = C.copy()
    C2[f:] *= 3.0                                                      # the formation close and later never enter
    np.testing.assert_allclose(M.caps_at(dict(inp, C=C2), f, cols), caps)
    C3 = C.copy()
    C3[f - 1, 0] *= 1.1                                                # sanity: the previous close is the input
    assert M.caps_at(dict(inp, C=C3), f, cols)[0] == pytest.approx(caps[0] * 1.1)
    early = dict(shares)
    early[101] = [shares[101][0], (SX._et_ts(days[f], 9, 29), "2025-01-15", 5000.0)]
    assert M.caps_at(dict(inp, shares=early), f, cols)[1] == pytest.approx(40.0 * 5000.0 / 2)   # before 09:30: used
    fresh = dict(shares)
    fresh[202] = [(SX._et_ts("2024-11-01", 16, 0), "2024-09-30", 300.0)]
    assert M.caps_at(dict(inp, shares=fresh), f, cols)[2] == pytest.approx(30.0 * 300.0)


def test_t660_weights_vw_with_missing_caps():
    score = np.arange(20, dtype=float)
    elig = np.ones(20, bool)
    caps = np.full(20, np.nan)
    caps[18], caps[19] = 1.0, 3.0
    w = M.portfolio_weights(score, elig, 10, True, caps)
    assert set(np.flatnonzero(w)) == {18, 19}
    assert w.sum() == pytest.approx(1.0) and w[19] == pytest.approx(0.75)
    caps[19] = np.nan
    w = M.portfolio_weights(score, elig, 10, True, caps)
    assert w[19] == pytest.approx(0.5) and w[18] == pytest.approx(0.5)  # a name without shares holds the equal weight
    w = M.portfolio_weights(score, elig, 10, False, None)
    assert set(np.flatnonzero(w)) == {0, 1}


# ------------------------------------------------------------------------------------------------------ T-664 --

def test_t664_dev_known_at_close_and_next_open_only_in_y():
    sd = ["2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05"]
    oo = np.array([100.0, 101.0, 102.0, 103.0])
    cc = np.array([100.5, 101.5, 102.5, 103.5])
    dd = np.zeros(4)
    b15 = {"2025-06-02": 100.4, "2025-06-03": 101.6, "2025-06-04": 102.5}
    out, cnt = M.new_rows(), M.new_counts()
    M.symbol_rows("AAPL", sd, oo, cc, dd, b15, "2025-01-01", set(), set(), set(), out, cnt)
    assert out["day"] == ["2025-06-02", "2025-06-03"]                    # 06-04: the 15:30 close equals the official close
    assert cnt["equal_dropped"] == 1
    assert out["dev"][0] == pytest.approx(math.log(100.5 / 100.4))
    assert out["y"][0] == pytest.approx(math.log(101.0 / 100.5))
    assert out["dev_prev"][1] == pytest.approx(out["dev"][0]) and np.isnan(out["dev_prev"][0])
    oo2, cc2 = oo.copy(), cc.copy()
    oo2[1:] *= 1.1
    cc2[1:] *= 0.9
    out2, cnt2 = M.new_rows(), M.new_counts()
    M.symbol_rows("AAPL", sd, oo2, cc2, dd, b15, "2025-01-01", set(), set(), set(), out2, cnt2)
    assert out2["dev"][0] == out["dev"][0]                               # later prices never move day 0's dev
    assert out2["y"][0] != out["y"][0]


def test_t664_bar_1530_not_the_close_stub():
    import pandas as pd
    idx = pd.to_datetime(["2025-06-02 19:30", "2025-06-02 20:00"], utc=True)
    df = pd.DataFrame({"o": [1.0, 2.0], "h": [1.0, 2.0], "l": [1.0, 2.0], "c": [1.5, 2.5], "v": [0, 0]}, index=idx)
    assert M.bar_1530(df) == {"2025-06-02": 1.5}


def test_t664_fe_wild_bootstrap():
    rng = np.random.default_rng(8)
    G, k = 300, 20
    g = np.repeat(np.arange(G), k)
    x = rng.normal(0, 1e-3, G * k)
    day = rng.normal(0, 5e-3, G)[g]
    y = -1.0 * x + day + rng.normal(0, 5e-4, G * k)
    fe = M.fe_slope(x, y, g)
    assert fe["slope"] == pytest.approx(-1.0, abs=0.1)
    pl, pg, nd = M.wild_cluster_p(fe, -0.5, n_boot=999, max_batches=2)
    assert pl < 0.01
    y0 = 0.0 * x + day + rng.normal(0, 5e-4, G * k)
    pl0, _, _ = M.wild_cluster_p(M.fe_slope(x, y0, g), -0.5, n_boot=999, max_batches=2)
    assert pl0 > 0.5


# ------------------------------------------------------------------------------------- local read errors (T-659/T-664) --

def _fresh_local(monkeypatch, fake):
    monkeypatch.setattr(M, "_LOCAL", {})
    monkeypatch.setattr(M, "_LOCAL_ERR", {})
    monkeypatch.setattr("mandel.ml.features.load_bars", fake)
    monkeypatch.setattr(M, "_missing", lambda archive, names: None)


def test_local_read_error_is_not_reported_as_missing(monkeypatch):
    def fake(interval, sym):
        if sym == "ES_F":
            raise ValueError("bad gzip header")
    _fresh_local(monkeypatch, fake)
    assert M._local("60m", "ES_F") is None and "bad gzip header" in M._local_err("60m", "ES_F")
    assert M._local("60m", "NQ_F") is None and M._local_err("60m", "NQ_F") is None       # absent, not an error
    stat, n, verdict, reason = M.b13_intraday_a_es_0200_drift(_NoArchive())
    assert verdict == "inconclusive" and n == 0
    assert "could not be read" in reason and "bad gzip header" in reason and "not on disk" not in reason
    assert stat["unreadable_local"] == {"ES_F": "ValueError: bad gzip header"}


def test_local_absent_file_still_reads_as_missing(monkeypatch):
    _fresh_local(monkeypatch, lambda interval, sym: None)
    stat, _, verdict, reason = M.b13_intraday_a_es_0200_drift(_NoArchive())
    assert verdict == "inconclusive" and "not on disk" in reason and stat["missing_local"] == ["ES_F", "NQ_F"]


def test_t664_unreadable_symbol_is_inconclusive_not_dropped(monkeypatch):
    import pandas as pd

    class _P:
        days = np.array(["2025-06-02", "2025-06-03", "2025-06-04"])
        symbols = np.array(["SPY", "AAPL"])

        def col(self, s, field):
            return np.array({"open": [100.0, 101.0, 102.0]}.get(field, [100.5, 101.5, 102.5]))

    idx = pd.to_datetime(["2025-06-02 19:30", "2025-06-03 19:30"], utc=True)
    spy = pd.DataFrame({"o": [100.0, 101.0], "h": [101.0, 102.0], "l": [99.0, 100.0], "c": [100.4, 101.6], "v": [0, 0]},
                       index=idx)

    def fake(interval, sym):
        if sym == "AAPL":
            raise OSError("corrupt csv")
        return spy if sym == "SPY" else None
    _fresh_local(monkeypatch, fake)
    monkeypatch.setattr("mandel.experiments.panel_cache.daily_panel", lambda archive: _P())
    stat, n, verdict, reason = M.b13_intraday_a_auction_reversal(_NoArchive())
    assert verdict == "inconclusive" and n == 0
    assert "AAPL" in reason and "corrupt csv" in reason and "could not be read" in reason
    assert stat["unreadable_local"] == {"AAPL": "OSError: corrupt csv"}
