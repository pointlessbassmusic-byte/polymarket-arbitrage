"""Batch-4 VIX-futures harnesses (T-160 VX calendar, T-242 VXX decay) on synthetic data: planted effects pass, nulls
fail. No archive and no network."""

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch4_vx as vx

NB = 400            # bootstrap draws in tests (the harnesses use 5,000)


def _bdays(start: str, n: int) -> list:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _vx_values(n_days: int, every: int = 21, c: float = 1.0, noise: float = 0.05, rw: float = 0.0, seed: int = 0,
               n_listed: int = 4, start: str = "2015-01-05", vix_level: float = 15.0):
    """Synthetic VX settlements. Planted (rw=0): F = VIX + c * sqrt(business days to expiry) + iid noise. The
    concave curve makes M1 roll down faster than M2, so short M1 / long M2 earns. Null (c=0, rw>0): each contract
    follows its own zero-drift random walk, so spread changes have zero mean."""
    rng = np.random.default_rng(seed)
    ext = _bdays(start, n_days + (n_listed + 2) * every)
    days = ext[:n_days]
    exp_idx = list(range(5, len(ext), every))
    walk = {}
    vals = []
    for t, d in enumerate(days):
        live = [e for e in exp_idx if e >= t][:n_listed]
        for e in live:
            walk[e] = walk.get(e, 0.0) + (rng.normal(0.0, rw) if rw > 0 else 0.0)
            tau = e - t
            f = vix_level + c * math.sqrt(tau) + walk[e] + (rng.normal(0.0, noise) if noise > 0 else 0.0)
            vals.append({"expiry": ext[e], "day": d, "settle": round(max(f, 0.5), 4), "close": None})
    return days, vals


def _flat_index(days, level):
    return {d: float(level) for d in days}


# ============================================================================================== statistics ==

def test_stud_mean_sides_and_null():
    rng = np.random.default_rng(1)
    pos = vx.stud_mean(0.4 + rng.standard_normal(300), 5, NB)
    null = vx.stud_mean(rng.standard_normal(300), 5, NB)
    assert pos["ci95"][0] > 0 and pos["lb95"] > 0
    assert pos["ci95"][0] < pos["lb95"] < pos["mean"] < pos["ub95"] < pos["ci95"][1]   # one-sided bounds are tighter
    assert null["ci95"][0] < 0 < null["ci95"][1]
    const = vx.stud_mean(np.full(20, 2.0), 3, NB)
    assert const["ci95"] == [2.0, 2.0] and const["se"] == 0.0
    assert vx.stud_mean(np.array([1.0, 2.0]), 3, NB)["ci95"] == [None, None]


def test_cvar_and_drawdown():
    x = np.array([-10.0, 1, 1, 1, 1, 1, 1, 1, 1, 1] * 10)
    assert vx._cvar(x, 0.01) == -10.0
    assert vx._mdd_abs(np.array([5.0, -3.0, -4.0, 10.0])) == -7.0


# ======================================================================================= T-160 VX calendar ==

def test_vx_curve_drops_zero_settles_and_parses_us_dates():
    rows = [{"expiry": "2013-02-13", "day": "2013-01-02", "settle": 0.0, "close": 15.6},
            {"expiry": "2013-02-13", "day": "01/03/2013", "settle": 15.9, "close": 15.9},
            {"expiry": "02/13/2013", "day": "2013-01-04", "settle": None, "close": 15.3},
            {"expiry": "2013-02-13", "day": "2013-02-14", "settle": 15.0}]                # after expiry: dropped
    c = vx.vx_curve(rows)
    assert c == {"2013-01-03": {"2013-02-13": 15.9}}


def _toy_curve():
    d = _bdays("2020-01-06", 6)                         # Mon..Mon
    E1, E2, E3 = d[2], "2020-02-19", "2020-03-18"
    curve = {
        d[0]: {E1: 10.0, E2: 12.0, E3: 14.0},
        d[1]: {E1: 11.0, E2: 12.5, E3: 14.2},
        d[2]: {E1: 12.0, E2: 13.0, E3: 14.5},           # E1's final settlement
        d[3]: {E2: 13.2, E3: 14.4},
        d[4]: {E2: 13.0, E3: 14.6},
        d[5]: {E2: 12.8, E3: 14.6},
    }
    return d, curve, [E1, E2, E3]


def test_calendar_pnl_marks_final_settlement_rolls_and_costs():
    d, curve, ex = _toy_curve()
    res = vx.calendar_pnl(curve, _flat_index(d, 0.9), lag=1, expiries=ex)
    assert res["day"] == [d[2], d[3], d[4], d[5]]
    # (d1, d2]: short E1 (11 -> final 12), long E2 (12.5 -> 13): -500, entry of 2 legs = $4
    # (d2, d3]: rolled at the expiry-day close into E2/E3: (14.4-14.5) - (13.2-13.0) = -0.3 -> -300, roll = $8
    assert res["gross"].tolist() == pytest.approx([-500.0, -300.0, 400.0, 200.0])
    assert res["cost"].tolist() == pytest.approx([4.0, 8.0, 0.0, 0.0])
    assert res["net"].tolist() == pytest.approx([-504.0, -308.0, 400.0, 200.0])
    assert res["m1"] == [ex[0], ex[1], ex[1], ex[1]] and res["n_rolls"] == 1


def test_calendar_gate_is_point_in_time():
    d, curve, ex = _toy_curve()
    ratio = _flat_index(d, 0.9)
    ratio[d[2]] = 1.05                                  # backwardation observed at the close of d2 only
    lag1 = vx.calendar_pnl(curve, ratio, lag=1, expiries=ex)
    # decided at the close of d2, traded at the settle of d3: the (d3, d4] interval is flat (exit $4, no P&L),
    # and (d4, d5] re-enters ($4)
    assert lag1["w"].tolist() == [1, 1, 0, 1]
    assert lag1["net"].tolist() == pytest.approx([-504.0, -308.0, -4.0, 196.0])
    # the (d2, d3] interval is never affected by the d2 close under lag 1 (no look-ahead)
    assert lag1["net"][1] == pytest.approx(-308.0)
    lag0 = vx.calendar_pnl(curve, ratio, lag=0, expiries=ex)
    assert lag0["day"][0] == d[1] and lag0["w"].tolist() == [1, 1, 0, 1, 1]


def test_calendar_missing_settle_is_bridged_not_skipped():
    d, curve, ex = _toy_curve()
    del curve[d[4]][ex[2]]
    res = vx.calendar_pnl(curve, _flat_index(d, 0.9), lag=1, expiries=ex)
    # both intervals touching the hole are kept; E3 is marked at its last valid settle (14.4 on d3) through d4
    assert res["day"] == [d[2], d[3], d[4], d[5]] and res["gaps"] == [(d[4], "missing settle"), (d[5], "missing settle")]
    assert res["gross"].tolist() == pytest.approx([-500.0, -300.0, 200.0, 400.0])
    assert res["gross"].sum() == pytest.approx(-200.0)                       # = the complete-data total
    assert res["cost"].sum() == pytest.approx(12.0) and res["n_deferred"] == 0


def _gap_toy():
    """The reviewer's case: M1 flat at 20, M2 steps 21 -> 26 on 2020-01-09, gate always on (VIX/VIX3M = 0.9)."""
    days = _bdays("2020-01-06", 7)
    e1, e2 = "2020-02-19", "2020-03-18"
    m2 = [21.0, 21.0, 21.0, 26.0, 26.0, 26.0, 26.0]
    return days, {d: {e1: 20.0, e2: b} for d, b in zip(days, m2)}, e1, e2


def test_calendar_gap_in_held_leg_keeps_the_move_regression():
    # regression: a one-day hole in M2 used to drop two intervals, and the held spread's +$5,000 vanished (net -$4, n=3)
    days, curve, e1, e2 = _gap_toy()
    full = vx.calendar_pnl(curve, _flat_index(days, 0.9), lag=1)
    del curve["2020-01-09"][e2]
    gap = vx.calendar_pnl(curve, _flat_index(days, 0.9), lag=1)
    assert full["net"].sum() == pytest.approx(4996.0) and len(full["net"]) == 5 and full["gaps"] == []
    assert gap["net"].sum() == pytest.approx(4996.0) and len(gap["net"]) == 5
    assert gap["cost"].sum() == pytest.approx(4.0)                          # no phantom exit / re-entry
    assert [g[0] for g in gap["gaps"]] == ["2020-01-09", "2020-01-10"]
    assert gap["net"].tolist() == pytest.approx([-4.0, 0.0, 5000.0, 0.0, 0.0])  # booked when the settle returns
    assert gap["gap_abs_gross"] == pytest.approx(5000.0) and gap["gap_abs_spread_chg"] == pytest.approx(5000.0)


def test_calendar_trade_needing_a_missing_settle_is_deferred():
    days, curve, e1, e2 = _gap_toy()
    ratio = _flat_index(days, 1.05)
    ratio[days[1]] = ratio[days[2]] = 0.9               # gate on at the 01-07 and 01-08 closes: enter at the 01-08 settle
    del curve[days[2]][e2]                              # ... but M2 has no settle on 01-08
    res = vx.calendar_pnl(curve, ratio, lag=1)
    # entry deferred to the 01-09 settle (M2 at 26 after the jump): no P&L from the jump, one $4 entry; the gate is
    # off from the 01-09 close, so the spread is closed at the 01-10 settle ($4)
    assert res["n_deferred"] == 1 and res["w"].tolist() == [0, 0, 1, 0, 0]
    assert res["gross"].sum() == pytest.approx(0.0) and res["cost"].tolist() == pytest.approx([0, 0, 4, 4, 0])


def test_calendar_expired_leg_without_final_settle_is_closed_stale():
    d, curve, ex = _toy_curve()
    del curve[d[2]][ex[0]]                              # E1's final settlement is missing
    res = vx.calendar_pnl(curve, _flat_index(d, 0.9), lag=1, expiries=ex)
    # E1 is marked at 11.0 (d1) and closed there; the roll still happens at the d2 close
    assert res["n_stale_closes"] == 1 and res["n_rolls"] == 1 and res["n_deferred"] == 0
    assert res["gross"].tolist() == pytest.approx([500.0, -300.0, 400.0, 200.0])
    assert res["cost"].tolist() == pytest.approx([4.0, 8.0, 0.0, 0.0])


def test_vx_calendar_planted_contango_supported():
    days, vals = _vx_values(900, c=1.0, noise=0.05, seed=3)
    curve = vx.vx_curve(vals)
    rep = vx.vx_calendar(curve, _flat_index(days, 15.0), _flat_index(days, 16.5), n_boot=NB, min_n=500)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["mean_net"] > 50 and rep["halves"]["first"]["ci95"][0] > 0 and rep["halves"]["second"]["ci95"][0] > 0
    assert rep["frac_held"] == 1.0 and rep["reason"].endswith("all criteria pass")
    assert rep["n_rolls"] >= 40 and rep["total_cost"] == pytest.approx(8.0 * rep["n_rolls"] + 4.0)


def test_vx_calendar_null_random_walk_not_supported():
    days, vals = _vx_values(900, c=0.0, noise=0.0, rw=0.3, seed=5)
    curve = vx.vx_curve(vals)
    rep = vx.vx_calendar(curve, _flat_index(days, 15.0), _flat_index(days, 16.5), n_boot=NB, min_n=500)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_vx_calendar_gate_flat_in_backwardation():
    days, vals = _vx_values(400, c=1.0, noise=0.05, seed=3)
    curve = vx.vx_curve(vals)
    rep = vx.vx_calendar(curve, _flat_index(days, 20.0), _flat_index(days, 18.0), n_boot=NB, min_n=100)
    assert rep["frac_held"] == 0.0 and rep["mean_net"] == 0.0 and rep["verdict"] == "not_supported"


def test_vx_calendar_short_window_is_at_best_inconclusive():
    days, vals = _vx_values(400, c=1.0, noise=0.05, seed=3)
    rep = vx.vx_calendar(vx.vx_curve(vals), _flat_index(days, 15.0), _flat_index(days, 16.5), n_boot=NB)   # min_n 2500
    assert rep["verdict"] == "inconclusive" and "not implemented: n >= 2500" in rep["reason"]


# ============================================================================================ T-242 VXX decay ==

def _vxx(n, mu, sd=0.01, seed=0, start="2018-01-29"):
    rng = np.random.default_rng(seed)
    days = _bdays(start, n)
    closes = 100.0 * np.exp(np.cumsum(mu + sd * rng.standard_normal(n)))
    return days, closes


def test_conditional_cycles_lag_and_non_overlap():
    days = _bdays("2020-01-01", 120)
    closes = np.linspace(100, 50, 120)
    ratio = {d: 1.0 for d in days}
    ratio[days[10]] = 1.2; ratio[days[20]] = 1.2; ratio[days[40]] = 1.2
    ev = vx.conditional_cycles(days, closes, ratio, threshold=1.10, horizon=21, lag=1)
    assert ev["idx"] == [11, 41]                        # the close after the signal; day 20's signal falls inside the first cycle
    assert ev["logret"][0] == pytest.approx(math.log(closes[32] / closes[11]))
    ev0 = vx.conditional_cycles(days, closes, ratio, threshold=1.10, horizon=21, lag=0)
    assert ev0["idx"] == [10, 40]
    unc = vx.conditional_cycles(days, closes, ratio, threshold=None, horizon=21, lag=1)
    assert unc["idx"] == [1, 22, 43, 64, 85]


def test_vxx_decay_planted_supported():
    days, closes = _vxx(2000, -0.004, seed=2)
    rep = vx.vxx_decay(days, closes, _flat_index(days, 15.0), _flat_index(days, 18.0), n_boot=NB, n_place=200)
    assert rep["n"] >= 80 and rep["ub95"] < -0.03
    assert rep["verdict"] == "supported", rep["reason"]


def test_vxx_decay_null_not_supported():
    days, closes = _vxx(2000, 0.0, seed=4)
    rep = vx.vxx_decay(days, closes, _flat_index(days, 15.0), _flat_index(days, 18.0), n_boot=NB, n_place=200)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_vxx_decay_condition_never_met_and_short_history():
    days, closes = _vxx(2000, -0.004, seed=2)
    none = vx.vxx_decay(days, closes, _flat_index(days, 18.0), _flat_index(days, 18.0), n_boot=NB, n_place=50)
    assert none["n"] == 0 and none["verdict"] == "inconclusive"
    d2, c2 = _vxx(700, -0.004, seed=2)
    short = vx.vxx_decay(d2, c2, _flat_index(d2, 15.0), _flat_index(d2, 18.0), n_boot=NB, n_place=50)
    assert short["n"] < 80 and short["verdict"] == "inconclusive", short["reason"]


def test_svxy_proxy_inverts_and_deleverages():
    days = _bdays("2018-02-20", 10)
    r_vxx = np.array([0.0, 0.05, -0.02, 0.10, -0.04, 0.03, 0.01, -0.05, 0.02, 0.0])
    lev = np.array([0.5 if d >= vx.SVXY_HALF_FROM else 1.0 for d in days])
    svxy = 50.0 * np.cumprod(1.0 - lev * r_vxx)
    proxy = vx.svxy_proxy(days, svxy)
    assert proxy[1:] / proxy[:-1] - 1.0 == pytest.approx(r_vxx[1:])


def test_put_spread_model_is_labelled_and_gains_when_vxx_decays():
    days, closes = _vxx(420, -0.004, sd=0.01, seed=6)
    vvix = _flat_index(days, 100.0)
    mp = vx.put_spread_model(days, closes, [300, 330], vvix, {d: 2.0 for d in days})
    assert mp["pricing"].startswith("MODEL-PRICED") and mp["n"] == 2
    assert mp["mean_pnl_over_spot"] > 0 and 0.1 < mp["mean_scale"] < 0.3
    assert vx.put_spread_model(days, closes, [100], vvix, {})["n"] == 0      # not enough history before entry


# ================================================================================================= harnesses ==

class _Entry:
    created_at = "2100-01-01T00:00:00+00:00"


class FakeArchive:
    def __init__(self, bundles):
        self.b = bundles

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry()

    def load(self, name):
        return iter(self.b[name])


def _idx_rows(days, level):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(level)}} for d in days]


def _px_rows(days, closes):
    out = []
    for d, c in zip(days, closes):
        t = int(datetime.fromisoformat(d + "T14:30:00+00:00").replace(tzinfo=timezone.utc).timestamp())
        out.append({"available_at": d + "T23:00:00+00:00",
                    "value": {"t": t, "close": float(c), "adjclose": float(c), "volume": 1000}})
    return out


def test_harnesses_registry_and_missing_bundles():
    assert set(vx.THEORY_MAP) == {"T-160", "T-242"}
    assert set(vx.THEORY_MAP.values()) == set(vx.HARNESSES)
    for h in vx.HARNESSES.values():
        stat, n, v, reason = h(FakeArchive({}))
        assert v == "inconclusive" and n == 0 and "missing data bundles" in reason


def test_harnesses_run_on_synthetic_archive():
    days, vals = _vx_values(400, c=1.0, noise=0.05, seed=3)
    vxx_days, closes = _vxx(2000, -0.004, seed=2, start="2015-01-05")
    alld = sorted(set(days) | set(vxx_days))
    ar = FakeArchive({
        vx.VX_BUNDLE: [{"available_at": v["day"] + "T21:30:00+00:00", "value": v} for v in vals],
        vx.VIX_BUNDLE: _idx_rows(alld, 15.0),
        vx.VIX3M_BUNDLE: _idx_rows(alld, 18.0),
        vx.VXX_BUNDLE: _px_rows(vxx_days, closes),
    })
    stat, n, v, reason = vx.vx_calendar_gated(ar)
    assert v == "inconclusive" and n < 2500 and " — " in reason          # planted effect, but below min_n
    stat, n, v, reason = vx.vx_vxx_contango_decay(ar)
    assert v == "supported" and n >= 80 and reason.endswith("all criteria pass")
    assert stat["svxy_proxy"] is None and stat["model_priced_put_spread"]["n"] == 0
