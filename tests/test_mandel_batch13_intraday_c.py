"""Batch 13 ``intraday_c`` harnesses (T-666, T-657, T-661, T-668): point-in-time signal construction and rule 9."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pytest

from mandel.experiments import batch13_intraday_c as M


class _Stub:
    """An archive with no bundles: ``get`` raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self):
        return []


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_are_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_Stub())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_points_at_harnesses():
    assert set(M.THEORY_MAP) == {"T-666", "T-657", "T-661", "T-668"}
    assert all(h in M.HARNESSES for h in M.THEORY_MAP.values())


# ------------------------------------------------------------------------------------------------------ T-666 --

def test_same_hour_signal_uses_only_earlier_rows():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(60, 4))
    X[10, 2] = np.nan
    S = M.same_hour_signal(X, 20)
    d = 40
    X2 = X.copy()
    X2[d:] += 50.0                                          # shock the decision row and everything after it
    S2 = M.same_hour_signal(X2, 20)
    np.testing.assert_allclose(S[:d + 1], S2[:d + 1], equal_nan=True)
    assert math.isclose(S[d, 0], X[d - 20:d, 0].mean())
    fin = X[:d, 2][np.isfinite(X[:d, 2])]
    assert math.isclose(S[d, 2], fin[-20:].mean())          # the missing bar is skipped: 20 observations
    assert np.isnan(S[19, 0]) and np.isfinite(S[20, 0])


@pytest.mark.parametrize("h", [0, 2, 3, 6])
def test_t666_design_ignores_the_dependent_bar_and_later(h):
    rng = np.random.default_rng(2)
    D, N = 50, 6
    Rdm = rng.normal(size=(D, 7, N))
    ONdm = rng.normal(size=(D, N))
    prev = np.ones(D, bool)
    d = 30
    y, S, c1, c2 = M.t666_design(Rdm, ONdm, prev, h, 20)
    R2 = Rdm.copy()
    R2[d, h:] += 9.0                                         # the bar itself and the rest of session d
    R2[d + 1:] += 9.0                                        # every later session
    O2 = ONdm.copy()
    O2[d + 1:] += 9.0
    y2, S2, c12, c22 = M.t666_design(R2, O2, prev, h, 20)
    for a, b in ((S, S2), (c1, c12), (c2, c22)):
        np.testing.assert_allclose(a[d], b[d])
    assert not np.allclose(y[d], y2[d])                      # the dependent did move


def test_t666_prior_1530_control_needs_adjacent_session():
    Rdm = np.ones((5, 7, 3))
    ON = np.zeros((5, 3))
    prev = np.array([False, True, False, True, True])
    _, _, _, c2 = M.t666_design(Rdm, ON, prev, 0, 1)
    assert np.isnan(c2[0]).all() and np.isnan(c2[2]).all() and np.isfinite(c2[1]).all()


def test_cs_slopes_recovers_a_planted_slope():
    rng = np.random.default_rng(3)
    D, N = 200, 39
    S = rng.normal(size=(D, N))
    c1, c2 = rng.normal(size=(D, N)), rng.normal(size=(D, N))
    y = 0.3 * S + 0.1 * c1 + rng.normal(scale=0.5, size=(D, N))
    b, k = M.cs_slopes(y, S, c1, c2, 20)
    assert abs(np.nanmean(b) - 0.3) < 0.03 and (k == N).all()


def test_demean_is_cross_sectional():
    X = np.array([[1.0, 2.0, np.nan, 3.0]])
    np.testing.assert_allclose(M.demean(X, axis=1), [[-1.0, 0.0, np.nan, 1.0]], equal_nan=True)


# ------------------------------------------------------------------------------------------------------ T-657 --

def test_volume_condition_uses_earlier_sessions_only():
    rng = np.random.default_rng(4)
    V = rng.lognormal(size=200)
    k = 120
    r = M.volume_ratio(V)
    top, ok, cut = M.trailing_tercile(r)
    V2 = V.copy()
    V2[k + 1:] *= 30.0                                      # sessions after the decision
    r2 = M.volume_ratio(V2)
    top2, _ok2, cut2 = M.trailing_tercile(r2)
    np.testing.assert_allclose(r[:k + 1], r2[:k + 1], equal_nan=True)
    np.testing.assert_allclose(cut[:k + 1], cut2[:k + 1], equal_nan=True)
    assert (top[:k + 1] == top2[:k + 1]).all()
    V3 = V.copy()
    V3[k] *= 30.0                                           # the day's own 09:30 bar moves the ratio, not the cut-off
    _, _, cut3 = M.trailing_tercile(M.volume_ratio(V3))
    assert cut3[k] == cut[k]
    assert math.isclose(r[k], V[k] / V[k - 20:k].mean())
    assert not ok[:M.T657_BURN].any() and ok[M.T657_BURN]


def test_t657_position_is_fixed_at_1030():
    s = {"p1030": np.array([101.0, 99.0, 100.0]), "prev_adj": np.array([100.0, 100.0, 100.0]),
         "o1530": np.array([102.0, 98.0, 100.0]), "close": np.array([103.0, 97.0, 101.0])}
    a = M.t657_leg(s)
    s2 = dict(s, o1530=s["o1530"] * 1.1, close=s["close"] * 0.5)   # after 15:30: only the payoff may change
    b = M.t657_leg(s2)
    np.testing.assert_array_equal(a["pos"], b["pos"])
    np.testing.assert_array_equal(a["pos"], [1.0, -1.0, 0.0])
    assert math.isclose(a["net"][0], 103 / 102 - 1 - 2e-4) and math.isclose(a["net"][2], 0.0)


# ------------------------------------------------------------------------------------------------------ T-661 --

def _session_days(n_months: int) -> list:
    out = []
    for m in range(n_months):
        y, mm = 2016 + m // 12, m % 12 + 1
        out += [f"{y}-{mm:02d}-{d:02d}" for d in range(1, 21)]
    return out


def test_reversal_intensity_known_at_month_end():
    rng = np.random.default_rng(5)
    days = _session_days(16)
    D, N = len(days), 8
    R, RI = rng.normal(size=(D, N)), rng.normal(size=(D, N))
    _months, st = M.month_starts(days)
    sn, _sp, _ = M.reversal_shares(R, RI, st)
    NR = M.intensity(sn)
    m = 13
    end = st[m + 1]                                         # first row after month m
    R2, RI2 = R.copy(), RI.copy()
    R2[end:] = 1.0
    RI2[end:] = -1.0
    sn2, _, _ = M.reversal_shares(R2, RI2, st)
    NR2 = M.intensity(sn2)
    np.testing.assert_allclose(NR[:m + 1], NR2[:m + 1], equal_nan=True)
    assert np.isnan(NR[11]).all() and np.isfinite(NR[12]).all()       # 12 prior months needed
    rows = slice(st[m], st[m + 1])
    want = ((R[rows, 0] > 0) & (RI[rows, 0] < 0)).mean() / sn[m - 12:m, 0].mean()
    assert math.isclose(NR[m, 0], want)


def test_reversal_share_needs_15_valid_days():
    days = _session_days(1)
    R = np.ones((20, 1))
    RI = -np.ones((20, 1))
    R[:6] = np.nan
    _, st = M.month_starts(days)
    sn, _, nv = M.reversal_shares(R, RI, st)
    assert nv[0, 0] == 14 and np.isnan(sn[0, 0])


def test_hold_returns_exit_at_last_price():
    A = np.array([[10.0, 20.0], [11.0, 21.0], [12.0, np.nan], [13.0, np.nan]])
    r = M.hold_returns(A, 0, 3)
    assert math.isclose(r[0], 0.3) and math.isclose(r[1], 0.05)


def test_t661_fill_is_after_formation():
    days = _session_days(30)
    inp = {"days": days}
    for f, s, e, hm in M.t661_formations(inp, "2016-02", "2017-12"):
        assert s == f + 1 and days[f][:7] < days[s][:7] == hm and days[e][:7] > hm


def test_drift_and_port():
    w = np.array([0.5, 0.5, 0.0])
    r = np.array([0.1, np.nan, 0.2])
    assert math.isclose(M._port(w, r), 0.1)
    np.testing.assert_allclose(M._drift(w, r), [1.0, 0.0, 0.0])


# ------------------------------------------------------------------------------------------------------ T-668 --

def _minute_rows(days: int, drop: tuple = (), shock_from: int | None = None):
    t0 = int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp())
    rows = []
    for k in range(days * 1440):
        t = t0 + 60 * k
        if k in drop:
            continue
        c = 100.0 + 0.01 * k
        if shock_from is not None and k >= shock_from:
            c *= 3.0
        rows.append({"value": {"t": t, "close": c}})
    return t0, rows


def test_block_returns_use_minutes_inside_the_block_only():
    t0, rows = _minute_rows(3)
    day1 = t0 // 86400 + 1
    h0, CE, _ = M.hour_end_closes(M.hour_last_closes(rows))
    R = M.block_returns(h0, CE, [day1])
    k_end, k_start = 1440 + 23 * 60 + 59, 1440 + 21 * 60 + 59
    assert math.isclose(R[0, 11], math.log((100 + 0.01 * k_end) / (100 + 0.01 * k_start)))
    _, rows2 = _minute_rows(3, shock_from=2 * 1440)          # every minute after day 1's 23:59 is shocked
    h02, CE2, _ = M.hour_end_closes(M.hour_last_closes(rows2))
    np.testing.assert_allclose(R, M.block_returns(h02, CE2, [day1]))
    R0 = M.block_returns(h0, CE, [t0 // 86400])
    assert np.isnan(R0[0, 0]) and np.isfinite(R0[0, 1:]).all()    # block 0 needs the previous day's 23:59


def test_missing_minute_is_forward_filled():
    k_end = 1440 + 23 * 60 + 59
    t0, rows = _minute_rows(3, drop=(k_end,))
    h0, CE, _ = M.hour_end_closes(M.hour_last_closes(rows))
    R = M.block_returns(h0, CE, [t0 // 86400 + 1])
    k_start = 1440 + 21 * 60 + 59
    assert math.isclose(R[0, 11], math.log((100 + 0.01 * (k_end - 1)) / (100 + 0.01 * k_start)))


def test_block_minus_rest():
    R = np.tile(np.arange(12, dtype=float), (3, 1))
    np.testing.assert_allclose(M.block_minus_rest(R, 11), 11 - np.arange(11).mean())


def test_span_days_partial_bundle():
    class E:
        def __init__(self, tags):
            self.tags = tags

    assert M._span_days(E(["partial", "span:2026-10-01..2026-10-03"])) == {"2026-10-01", "2026-10-02"}
    assert M._span_days(E(["complete", "span:2026-09-29..2026-09-30"])) == {"2026-09-29", "2026-09-30"}
