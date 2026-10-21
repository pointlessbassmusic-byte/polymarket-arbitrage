"""Synthetic tests for mandel.experiments.batch13_cryptoderiv_a (T-608, T-613, T-612, T-614): every signal is unchanged
when data after its decision time is shocked, each harness is inconclusive when its bundles are missing, and a few
construction details (T-424 universe rule, turnover accounting, Bonferroni combination). No network, no real archive."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch13_cryptoderiv_a as M
from mandel.experiments import batch6c_cryptovenue as CV

UTC = timezone.utc


class _StubArchive:
    """Every bundle is missing: get() and load() raise KeyError, entries() is empty."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, kind=None, tag=None):
        return []


def _ts(d: str, hh: int = 0) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()) + hh * 3600


def _hourly(first: str, n_days: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    t0 = _ts(first)
    ts = t0 + 3600 * np.arange(24 * n_days, dtype=np.int64)
    lr = rng.normal(0, 0.004, ts.size)
    cl = 30000 * np.exp(np.cumsum(lr))
    op = np.concatenate([[cl[0]], cl[:-1]]) * np.exp(rng.normal(0, 0.0003, ts.size))
    return ts, op, cl


# ========================================================================================= missing bundles (rule 9) ==

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    out = M.HARNESSES[name](_StubArchive())
    assert out[2] == "inconclusive"
    assert out[1] == 0
    assert "missing" in out[3]


def test_maps_cover_the_four_theories():
    assert set(M.THEORY_MAP) == {"T-608", "T-613", "T-612", "T-614"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for fn in M.HARNESSES.values():
        assert fn.__doc__ and fn.__doc__.startswith("T-6")


# ============================================================================================================ T-614 ==

def test_t614_signal_ignores_bars_from_0800():
    ts, op, cl = _hourly("2024-03-25", 10, seed=1)
    days = ["2024-03-29"]                                   # a last Friday (Deribit monthly + quarterly expiry)
    assert M.is_expiry_friday(days[0])
    base = M.day_marks(ts, op, cl, days)
    t8 = _ts(days[0], 8)
    op2, cl2 = op.copy(), cl.copy()
    after = ts >= t8                                        # every bar starting at or after 08:00 UTC
    op2[after] *= 1.37
    cl2[after] *= 0.61
    shocked = M.day_marks(ts, op2, cl2, days)
    assert base["ok"][0] and shocked["ok"][0]
    assert shocked["r1"][0] == pytest.approx(base["r1"][0], abs=0, rel=0)
    assert shocked["side"][0] == base["side"][0]
    assert shocked["r2"][0] != base["r2"][0]                # the outcome does move
    # the 08:00 mark is the close of the bar starting 07:00: shocking that bar does move the signal
    cl3 = cl.copy()
    cl3[ts == _ts(days[0], 7)] *= 1.05
    assert M.day_marks(ts, op, cl3, days)["r1"][0] != base["r1"][0]


def test_t614_missing_bar_drops_the_day():
    ts, op, cl = _hourly("2024-03-25", 10, seed=2)
    keep = ts != _ts("2024-03-29", 15)
    mk = M.day_marks(ts[keep], op[keep], cl[keep], ["2024-03-29", "2024-03-28"])
    assert not mk["ok"][0] and mk["ok"][1]


def test_t614_slope_difference_detects_planted_reversal():
    rng = np.random.default_rng(3)
    o0 = date(2019, 5, 1).toordinal()
    days = [date.fromordinal(o0 + k).isoformat() for k in range(2000)]
    exp = np.array([M.is_expiry_friday(d) for d in days])
    mt = np.array([date.fromisoformat(d).weekday() <= 3 for d in days])
    x = rng.normal(0, 0.01, len(days))
    y = np.where(exp, -0.8 * x, 0.0) + rng.normal(0, 0.004, len(days))
    t = M.slope_diff_test(x, y, exp, mt, n_boot=1000)
    assert t["diff"] < -0.5 and t["p_less"] < 0.01


# ============================================================================================================ T-613 ==

def test_t613_weekend_return_ignores_bars_after_the_monday_mark():
    ts, op, cl = _hourly("2024-06-01", 20, seed=4)
    ev = [("2024-06-07", "2024-06-10")]
    base = M.btc_window_returns(ev, ts, cl)
    t_mark = int(CV.et_epoch("2024-06-10", "09:00"))        # the bar ending 09:00 ET is the last one used
    cl2 = cl.copy()
    cl2[ts >= t_mark] *= 1.5
    shocked = M.btc_window_returns(ev, ts, cl2)
    assert shocked["x"][0] == base["x"][0]
    cl3 = cl.copy()
    cl3[ts == t_mark - 3600] *= 1.5
    assert M.btc_window_returns(ev, ts, cl3)["x"][0] != base["x"][0]


def test_t613_holiday_monday_rolls_and_good_friday_starts_thursday():
    sess = ["2024-03-27", "2024-03-28", "2024-04-01", "2024-08-30", "2024-09-03", "2024-09-04"]
    ev = M.gap_events(sess, "weekend")
    assert ("2024-03-28", "2024-04-01") in ev and ("2024-08-30", "2024-09-03") in ev
    assert M.gap_events(sess, "wednesday") == [("2024-09-03", "2024-09-04")]


def test_t613_expanding_terciles_use_prior_weekends_only():
    rng = np.random.default_rng(5)
    x = rng.normal(0, 0.03, 200)
    f, v = M.expanding_tercile_flags(x, min_prior=52)
    assert not v[:52].any() and v[52:].all()
    for k in (52, 90, 150):
        x2 = x.copy()
        x2[k + 1:] = rng.normal(5, 1, x2.size - k - 1)
        f2, v2 = M.expanding_tercile_flags(x2, min_prior=52)
        assert np.array_equal(f2[:k + 1], f[:k + 1]) and np.array_equal(v2[:k + 1], v[:k + 1])
    g = rng.normal(0, 0.01, 200)
    rf, rv = M.residual_flags(x, g, np.ones(200, bool))
    x3, g3 = x.copy(), g.copy()
    x3[121:] += 3.0
    g3[121:] -= 2.0
    rf3, rv3 = M.residual_flags(x3, g3, np.ones(200, bool))
    assert np.array_equal(rf3[:121], rf[:121]) and np.array_equal(rv3[:121], rv[:121])


def test_t613_bonferroni_combination():
    good = {"contrast": -0.003, "p_less": 0.0001, "draws": 100000, "halves": [-0.002, -0.004], "rule_minus_always": 0.0005}
    weak = {"contrast": -0.003, "p_less": 0.03, "draws": 100000, "halves": [-0.002, -0.004], "rule_minus_always": 0.0005}
    bad = {"contrast": 0.001, "p_less": 0.9, "draws": 100000, "halves": [0.001, 0.001], "rule_minus_always": -0.0001}
    assert M.etf_criteria({"SPY": bad, "QQQ": good, "IWM": bad})[0] is True
    assert M.etf_criteria({"SPY": bad, "QQQ": weak, "IWM": bad})[0] is False   # p 0.03 x 3 > 0.05
    assert M.etf_criteria({"SPY": bad, "QQQ": bad, "IWM": bad})[0] is False


# ============================================================================================================ T-612 ==

def _cot_rows(n: int, seed: int = 6) -> list:
    rng = np.random.default_rng(seed)
    rows, d = [], date(2022, 5, 3)
    for k in range(n):
        rd = (d + timedelta(days=7 * k)).isoformat()
        rel = datetime.fromisoformat(rd).replace(tzinfo=UTC) + timedelta(days=3, hours=19, minutes=30)
        rows.append({"available_at": rel.isoformat(),
                     "value": {"report_date": rd, "pit": "live", "release_rule": rel.isoformat(),
                               "lev_money_positions_long": str(int(rng.integers(1000, 5000))),
                               "lev_money_positions_short": str(int(rng.integers(5000, 12000))),
                               "asset_mgr_positions_long": str(int(rng.integers(500, 3000))),
                               "asset_mgr_positions_short": "100", "open_interest_all": str(int(rng.integers(15000, 25000)))}})
    return rows


def test_t612_change_ignores_later_reports():
    rows = _cot_rows(60)
    base = M.cot_records(rows)
    k = 30
    rows2 = [dict(r, value=dict(r["value"])) for r in rows]
    for r in rows2[k + 1:]:
        r["value"]["lev_money_positions_long"] = "99999"
        r["value"]["open_interest_all"] = "123456"
    shocked = M.cot_records(rows2)
    for i in range(k + 1):
        assert shocked[i]["dlf"] == base[i]["dlf"] or (math.isnan(shocked[i]["dlf"]) and math.isnan(base[i]["dlf"]))
        assert shocked[i]["dam"] == base[i]["dam"] or (math.isnan(shocked[i]["dam"]) and math.isnan(base[i]["dam"]))
        assert shocked[i]["z"] == base[i]["z"] or (math.isnan(shocked[i]["z"]) and math.isnan(base[i]["z"]))


def test_t612_catch_up_releases_are_superseded():
    rows = _cot_rows(6)
    late = rows[4]["available_at"]
    for r in rows[1:4]:
        r["available_at"] = late                          # a bulk-load stamp: three reports public at once
    recs = M.cot_records(rows)
    assert [q["superseded"] for q in recs] == [False, True, True, True, False, False]


def test_t612_entry_and_controls_are_point_in_time():
    ts, op, cl = _hourly("2022-05-01", 40, seed=7)
    daily = {"t": np.array([_ts("2018-01-01")], np.int64), "open": np.array([1.0]), "close_by_day": {}}
    t_dec = _ts("2022-05-20", 19) + 30 * 60 + 8          # 19:30:08 UTC
    ee = M.entry_exit(t_dec, (ts, op, cl), daily)
    assert ee["te"] >= t_dec and ee["te"] == _ts("2022-05-20", 20) and ee["tx"] == ee["te"] + 7 * 86400
    op2 = op.copy()
    op2[ts > ee["te"]] *= 2.0                             # shock every bar after the entry bar
    ee2 = M.entry_exit(t_dec, (ts, op2, cl), daily)
    assert ee2["prior"] == ee["prior"] and ee2["pe"] == ee["pe"]
    fut = {"2022-05-17": 31000.0}
    b = M.basis_on("2022-05-17", fut, (ts, op, cl), daily)
    cl2 = cl.copy()
    cl2[ts >= int(CV.et_epoch("2022-05-17", "16:00"))] *= 3.0
    assert M.basis_on("2022-05-17", fut, (ts, op, cl2), daily) == b
    assert M.front_expiry_days("2022-05-17") == 10 and M.front_expiry_days("2022-05-31") == 24


def test_t612_rule_series_costs():
    pos = np.array([0, 1, 1, 0, 1], float)
    r = np.full(5, 0.01)
    rf = np.zeros(5)
    out = M.rule_series(pos, r, rf, 0.001)
    assert np.allclose(out, [0.0, 0.009, 0.01, -0.001, 0.009])


# ============================================================================================================ T-608 ==

def _daily_panel(P: int = 40, T: int = 160, seed: int = 8, first: str = "2019-01-01"):
    rng = np.random.default_rng(seed)
    o0 = date.fromisoformat(first).toordinal()
    daily = {}
    for i in range(P):
        pid = f"C{i:02d}-USD"
        c = 10 * np.exp(np.cumsum(rng.normal(0, 0.04, T)))
        o = np.concatenate([[c[0]], c[:-1]]) * np.exp(rng.normal(0, 0.002, T))
        v = rng.lognormal(10, 1, T) * (1 + i)
        start = int(rng.integers(0, 20)) if i % 7 == 0 else 0
        daily[pid] = {date.fromordinal(o0 + k).isoformat(): (float(o[k]), float(c[k]), float(v[k])) for k in range(start, T)
                      if not (i % 11 == 0 and k % 13 == 0)}
    return daily


def test_t608_universe_matches_t424_cb_members():
    daily = _daily_panel()
    pan = M.build_panel(daily, "2019-01-01", "2019-06-09")
    cbm = CV.cb_members({p: {d: (c, v) for d, (o, c, v) in m.items()} for p, m in daily.items()}, "2019-02-15", "2019-05-01",
                        exclude=frozenset(), top=30, window=30)
    for d, ms in cbm.items():
        k = date.fromisoformat(d).toordinal() - pan["o0"]
        assert [pan["pids"][i] for i in M.universe_at(pan, k)] == ms


def test_t608_signal_ignores_monday_and_later_data():
    daily = _daily_panel()
    pan = M.build_panel(daily, "2019-01-01", "2019-06-09")
    k = date(2019, 4, 1).toordinal() - pan["o0"]           # a Monday column
    mem = M.universe_at(pan, k)
    sig = M.week_signal(pan, k, mem)
    lm = M.loser_mask(sig[np.isfinite(sig)], [pan["pids"][i] for i in mem[np.isfinite(sig)]])
    rng = np.random.default_rng(9)
    shocked = {}
    for p, m in daily.items():
        shocked[p] = {d: ((o * rng.uniform(0.3, 3), c * rng.uniform(0.3, 3), v * rng.uniform(0, 50)) if d >= "2019-04-01" else (o, c, v))
                      for d, (o, c, v) in m.items()}
    pan2 = M.build_panel(shocked, "2019-01-01", "2019-06-09")
    mem2 = M.universe_at(pan2, k)
    sig2 = M.week_signal(pan2, k, mem2)
    assert np.array_equal(mem, mem2)
    assert np.array_equal(np.nan_to_num(sig, nan=-9), np.nan_to_num(sig2, nan=-9))
    lm2 = M.loser_mask(sig2[np.isfinite(sig2)], [pan2["pids"][i] for i in mem2[np.isfinite(sig2)]])
    assert np.array_equal(lm, lm2)
    # the Sunday close (the bar ending Monday 00:00) is part of the signal: shocking it moves the signal
    sun = {p: dict(m) for p, m in daily.items()}
    p0 = pan["pids"][mem[0]]
    o, c, v = sun[p0]["2019-03-31"]
    sun[p0]["2019-03-31"] = (o, c * 1.5, v)
    pan3 = M.build_panel(sun, "2019-01-01", "2019-06-09")
    assert M.week_signal(pan3, k, mem[:1])[0] != sig[0]


def test_t608_delisted_exit_haircut_and_turnover():
    first = "2019-01-01"
    o0 = date.fromisoformat(first).toordinal()
    T = 120
    daily = {}
    for i in range(18):
        daily[f"C{i:02d}-USD"] = {date.fromordinal(o0 + k).isoformat(): (10.0, 10.0, 1000.0 * (i + 1)) for k in range(T)}
    # C00 stops trading for good after column 80 (a delisting)
    daily["C00-USD"] = {d: x for d, x in daily["C00-USD"].items() if date.fromisoformat(d).toordinal() - o0 <= 80}
    pan = M.build_panel(daily, first, date.fromordinal(o0 + T - 1).isoformat())
    k = 77                                                  # exit column 84: C00 has no bar at or after it
    rows = np.arange(len(pan["pids"]))
    r, gone = M.week_returns(pan, k, rows)
    i0 = pan["pids"].index("C00-USD")
    assert gone[i0] and r[i0] == pytest.approx(-0.5)
    assert np.allclose(np.delete(r, i0), 0.0)
    # flat prices: after the first week each book's turnover is zero (drift equals the target weights)
    cols = [c for c in range(35, 70) if date.fromordinal(o0 + c).weekday() == 0]
    res = M.weekly_books(pan, cols)
    W = res["weeks"]
    assert W[0]["to_all"] == 1.0 and all(q["to_all"] == pytest.approx(0.0) for q in W[1:])
    assert all(q["d"] == pytest.approx(W[0]["d"] if i == 0 else 0.0, abs=1e-12) for i, q in enumerate(W))


def test_t608_placebo_is_centred_on_minus_cost():
    rng = np.random.default_rng(10)
    weeks = [{"r": rng.normal(0, 0.05, 30)} for _ in range(300)]
    null = M.placebo_null(weeks, cost_diff=0.001, n=400)
    assert abs(null.mean() + 0.001) < 0.0005
