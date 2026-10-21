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


def test_t669_matching_is_calendar_only():
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
    for e, ms in sets:
        assert len(ms) <= 3 and all(datetime.fromisoformat(m).weekday() == datetime.fromisoformat(e).weekday() for m in ms)
        assert all(abs(sessions.index(m) - sessions.index(e)) <= 10 for m in ms)
        assert sessions[25] not in ms
    rng = np.random.default_rng(5)
    v1 = {s: float(rng.normal()) for s in sessions}
    v2 = {s: float(rng.normal()) * 10 for s in sessions}
    assert M.match_sets(events, sessions, valid, excluded) == sets       # values never enter the matching
    c1, c2 = M.event_contrast(sets, v1), M.event_contrast(sets, v2)
    assert c1["n_matched"] == c2["n_matched"]


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
