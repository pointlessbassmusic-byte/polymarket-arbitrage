"""Batch-5 hourly harnesses (T-427 intraday momentum, T-428 closing reversal) on synthetic bars: planted effects pass,
noise fails. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from mandel.experiments import batch5_hourly as bh

NY = ZoneInfo("America/New_York")
SESSION = ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]
N_FULL = 760     # synthetic weekday sessions 2023-11-15..2026-10-13: covers the claimed 2023-11..2026-10


# ------------------------------------------------------------------------------------------- synthetic market --

def _bdays(start, n):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _ts(day, hhmm):
    """Unix time of a New York wall-clock time (DST aware), as Yahoo stamps a bar start."""
    return int(datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=NY).timestamp())


def _bar(day, hhmm, o, c):
    return {"symbol": "X", "t": _ts(day, hhmm), "open": o, "high": max(o, c), "low": min(o, c), "close": c, "volume": 1}


def _daily(day, o, c, adj=None):
    return {"symbol": "X", "t": _ts(day, "09:30"), "open": o, "high": max(o, c), "low": min(o, c), "close": c,
            "volume": 1, "adjclose": c if adj is None else adj}


def simulate(n=N_FULL, seed=0, mom=0.0, beta_rev=0.0, sd_first=0.006, sd_mid=0.006, sd_last=0.002, sd_co=0.004,
             co_mean=0.0003, start="2023-11-14"):
    """Raw hourly and daily bar values plus the planted per-day quantities. Day 0 is a daily-only day before the
    hourly coverage, so day 1 has a previous official close. last = mom * sign(r1) + noise; CO(t+1) = co_mean +
    beta_rev * last + noise. The 15:30 bar's own last trade differs from the official close by noise."""
    rng = np.random.default_rng(seed)
    days = _bdays(start, n + 2)
    hourly, daily, truth = [], [], {}
    c_prev, o = 100.0, 100.0
    daily.append(_daily(days[0], 100.0, 100.0))
    for i, d in enumerate(days[1:n + 1], start=1):
        p1030 = o * (1 + rng.normal(0, sd_first))
        r1 = p1030 / c_prev - 1
        o1530 = p1030 * (1 + rng.normal(0, sd_mid))
        last = mom * np.sign(r1) + rng.normal(0, sd_last)
        c = o1530 * (1 + last)
        co = co_mean + beta_rev * last + rng.normal(0, sd_co)
        path = np.linspace(p1030, o1530, 6)               # 10:30 ... 15:30 prices
        hourly.append(_bar(d, "09:30", o, p1030))
        for k, hh in enumerate(SESSION[1:6]):
            hourly.append(_bar(d, hh, path[k], path[k + 1]))
        hourly.append(_bar(d, "15:30", o1530, c * (1 + rng.normal(0, 0.0003))))
        daily.append(_daily(d, o, c))
        truth[d] = {"r1": r1, "last": last, "co": co, "L45": 0.8 * last + rng.normal(0, 0.0005)}
        c_prev, o = c, c * (1 + co)
    daily.append(_daily(days[n + 1], o, o))
    return hourly, daily, truth


def sessions(**kw):
    h, d, truth = simulate(**kw)
    return bh.build_sessions(h, d), truth


# ------------------------------------------------------------------------------------------------- sessions --

def test_build_sessions_dst_early_close_missing_bars_and_dividends():
    winter, summer, half, gap, nxt = "2024-01-10", "2024-07-10", "2024-07-03", "2024-07-11", "2024-07-12"
    prev = "2024-01-09"
    hourly = []
    for d in (winter, summer):
        for k, hh in enumerate(SESSION):
            hourly.append(_bar(d, hh, 100 + k, 100.5 + k))
    for hh in ("09:30", "10:30", "11:30", "13:00"):
        hourly.append(_bar(half, hh, 100, 100))
    for hh in ("13:30", "14:30", "15:30"):
        hourly.append(_bar(gap, hh, 200, 201))
    for k, hh in enumerate(SESSION):
        hourly.append(_bar(nxt, hh, 300, 300))
    # the July 09:30 bar starts at 13:30 UTC, the January one at 14:30 UTC
    assert datetime.fromtimestamp(hourly[0]["t"], tz=timezone.utc).hour == 14
    assert datetime.fromtimestamp(hourly[7]["t"], tz=timezone.utc).hour == 13
    daily = [_daily(prev, 99, 99), _daily(winter, 100, 107), _daily("2024-07-09", 98, 98), _daily(half, 99, 99),
             _daily(summer, 100, 110, adj=110 * 0.99), _daily(gap, 200, 202, adj=202), _daily(nxt, 303, 303)]
    s = bh.build_sessions(hourly, daily)
    assert s["days"] == [winter, summer, gap, nxt]
    assert s["excluded"]["early_close"] == [half]
    assert s["excluded"]["missing_0930_bar"] == [gap]
    i = s["days"].index(winter)
    assert s["p1030"][i] == pytest.approx(100.5) and s["o1530"][i] == pytest.approx(106) and s["close"][i] == 107
    assert s["prev_close"][i] == pytest.approx(99)
    j = s["days"].index(summer)
    assert s["p1030"][j] == pytest.approx(100.5) and s["o1530"][j] == pytest.approx(106)
    k = s["days"].index(gap)
    assert math.isnan(s["p1030"][k]) and s["o1530"][k] == pytest.approx(200)
    # ex-dividend on the gap day: f(summer) = 0.99, f(gap) = 1, so the summer close in gap-day terms is 110 * 0.99
    assert s["co_next"][j] == pytest.approx(200 / (110 * 0.99) - 1)
    assert s["prev_close"][k] == pytest.approx(110 * 0.99)
    assert math.isnan(s["co_next"][s["days"].index(nxt)])           # no next daily bar


def test_window_note_flags_a_short_window():
    assert "inside the claimed" in bh.window_note("2023-11-15", "2026-10-13")
    assert "data limit" in bh.window_note("2024-10-16", "2026-10-13")
    assert not bh.window_short("2023-11-15", "2026-10-13")
    assert bh.window_short("2024-10-16", "2026-10-13") and bh.window_short("2023-11-15", "2026-08-18")


def test_calendars():
    cal = _bdays("2025-03-03", 60)                                   # to 2025-05-23
    cal.remove("2025-04-18")                                          # Good Friday
    ex = bh.expiration_days(cal)
    assert "2025-03-21" in ex and "2025-04-17" in ex
    assert bh.expiration_days(cal, months=(3, 6, 9, 12)) == {"2025-03-21"}
    me = bh.month_end_days(cal)
    assert "2025-03-31" in me and "2025-04-30" in me and not any(d.startswith(cal[-1][:7]) for d in me)
    kept = bh.cpi_release_days([{"day": d} for d in ("2024-01-11", "2024-02-09", "2024-02-13", "2024-03-12")])
    assert kept == ["2024-01-11", "2024-02-13", "2024-03-12"]


def test_hac_helpers_match_iid_case():
    rng = np.random.default_rng(1)
    x = rng.normal(0.5, 1.0, 4000)
    assert bh.nw_mean_t(x) == pytest.approx(x.mean() / (x.std() / math.sqrt(x.size)), rel=0.1)
    X = np.column_stack([np.ones(4000), rng.normal(0, 1, 4000)])
    y = 0.2 - 0.7 * X[:, 1] + rng.normal(0, 1, 4000)
    b, se = bh.ols_hac(y, X)
    assert b[1] == pytest.approx(-0.7, abs=0.05) and se[1] == pytest.approx(1 / math.sqrt(4000), rel=0.15)
    assert bh.sidak(0.001, 32) == pytest.approx(1 - 0.999 ** 32)


# -------------------------------------------------------------------------------------- T-427 intraday momentum --

def _three(mom_spy, mom_qqq, mom_iwm, n=N_FULL):
    spy, _ = sessions(n=n, seed=1, mom=mom_spy)
    qqq, _ = sessions(n=n, seed=2, mom=mom_qqq)
    iwm, _ = sessions(n=n, seed=3, mom=mom_iwm)
    return spy, {"QQQ": qqq, "IWM": iwm}


def test_momentum_planted_effect_is_supported():
    spy, others = _three(0.0015, 0.0015, 0.0015)
    rep = bh.intraday_momentum(spy, others, n_boot=500)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] == N_FULL and rep["mean_net_bps"] > 10 and rep["p_deflated"] < 0.05
    assert rep["mean_gross_bps"] - rep["mean_net_bps"] == pytest.approx(2.0)
    assert " — all criteria pass" in rep["reason"]
    json.dumps(bh._clean(rep))


def test_momentum_null_is_not_supported():
    spy, others = _three(0.0, 0.0, 0.0)
    rep = bh.intraday_momentum(spy, others, n_boot=500)
    assert rep["verdict"] == "not_supported"
    assert rep["mean_gross_bps"] - rep["mean_net_bps"] == pytest.approx(2.0)
    assert "deflated p" in rep["reason"].split(" — ")[1]


def test_momentum_cost_can_kill_a_small_gross_edge():
    spy, others = _three(0.0001, 0.0015, 0.0015, n=720)             # 1 bp gross < 2 bps cost (original 720-day draw)
    rep = bh.intraday_momentum(spy, others, n_boot=300)
    assert rep["verdict"] == "not_supported" and rep["mean_net_bps"] < 0


def test_momentum_needs_same_sign_on_qqq_and_iwm():
    spy, others = _three(0.0015, 0.0015, -0.0015)
    rep = bh.intraday_momentum(spy, others, n_boot=300)
    assert rep["verdict"] == "not_supported"
    assert "same sign on QQQ and IWM" in rep["reason"].split(" — ")[1]


def test_momentum_missing_replication_asset_is_at_best_inconclusive():
    spy, others = _three(0.0015, 0.0015, 0.0015)
    rep = bh.intraday_momentum(spy, {"QQQ": others["QQQ"], "IWM": None}, n_boot=300)
    assert rep["verdict"] == "inconclusive" and "not implemented: same sign" in rep["reason"]


def test_momentum_short_window_is_inconclusive():
    spy, others = _three(0.0015, 0.0015, 0.0015, n=300)
    rep = bh.intraday_momentum(spy, others, n_boot=300)
    assert rep["verdict"] == "inconclusive" and "data limit" in rep["reason"]


def test_momentum_late_start_window_with_enough_days_is_at_best_inconclusive():
    # regression: 1h coverage from 2024-08 (a recapture after ~2026-11), n >= 500 and a planted edge used to be
    # 'supported' although 2023-11..2024-07 of the claimed window was never tested
    spy, _ = sessions(n=560, seed=1, mom=0.0015, start="2024-08-01")
    qqq, _ = sessions(n=560, seed=2, mom=0.0015, start="2024-08-01")
    iwm, _ = sessions(n=560, seed=3, mom=0.0015, start="2024-08-01")
    rep = bh.intraday_momentum(spy, {"QQQ": qqq, "IWM": iwm}, n_boot=300)
    assert rep["n"] == 560 and rep["mean_net_bps"] > 10 and rep["p_deflated"] < 0.05
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert "not implemented: archived window covers the claimed 2023-11..2026-10" in rep["reason"]
    # a failing SPY criterion on the same short window is still not_supported
    spy0, _ = sessions(n=560, seed=1, mom=0.0, start="2024-08-01")
    rep0 = bh.intraday_momentum(spy0, {"QQQ": qqq, "IWM": iwm}, n_boot=300)
    assert rep0["verdict"] == "not_supported" and "SPY mean net return > 0" in rep0["reason"].split(" — ")[1]


def test_momentum_uses_official_close_not_the_bar_last_trade():
    spy, _ = sessions(n=60, seed=4, mom=0.0)
    leg = bh.momentum_leg(spy, cost_rt=0.0)
    i = 5
    d = leg["days"][i]
    k = spy["days"].index(d)
    assert leg["last"][i] == pytest.approx(spy["close"][k] / spy["o1530"][k] - 1)
    assert leg["r1"][i] == pytest.approx(spy["p1030"][k] / spy["prev_close"][k] - 1)


# ------------------------------------------------------------------------------------- T-428 closing reversal --

def _ldec(sess, truth):
    return np.array([truth[d]["L45"] for d in sess["days"]])


def test_reversal_planted_with_1545_signal_is_supported():
    s, truth = sessions(n=N_FULL, seed=5, beta_rev=-0.5, sd_co=0.002)
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=300)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["slope_L"] < -0.4 and rep["p_deflated_sidak"] < 0.01 and rep["reversal_leg"]["sharpe_net_annual"] > 0.5


def test_reversal_planted_from_hourly_bars_alone_is_inconclusive():
    s, _ = sessions(n=N_FULL, seed=5, beta_rev=-0.5, sd_co=0.002)
    rep = bh.closing_reversal(s, n_boot=300)
    assert rep["verdict"] == "inconclusive"
    assert "not implemented: reversal-leg net Sharpe" in rep["reason"] and "LOOK-AHEAD" in rep["reason"]


def test_reversal_null_is_not_supported():
    s, truth = sessions(n=N_FULL, seed=6, beta_rev=0.0)
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=300)
    assert rep["verdict"] == "not_supported"
    assert "slope <= -0.2" in rep["reason"].split(" — ")[1]


def test_reversal_significant_but_small_slope_fails():
    s, truth = sessions(n=N_FULL, seed=7, beta_rev=-0.1, sd_co=0.0003)
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=300)
    assert rep["p_deflated_sidak"] < 0.01 and rep["slope_L"] > -0.2
    assert rep["verdict"] == "not_supported"


def test_reversal_controls_for_open_to_1530_return():
    rng = np.random.default_rng(8)
    s, _ = sessions(n=N_FULL, seed=8)
    d = bh.reversal_data(s)
    # overnight return loads on R only; L is correlated with R. The controlled slope on L stays near 0.
    s2 = dict(s)
    co = np.full(len(s["days"]), np.nan)
    co[d["mask"]] = 0.5 * d["R"] + rng.normal(0, 0.001, d["mask"].sum())
    s2["co_next"] = co
    s2["close"] = s["close"].copy()
    rep = bh.closing_reversal(s2, n_boot=200)
    assert abs(rep["slope_L"]) < 0.2 and rep["coef_open_to_1530"] == pytest.approx(0.5, abs=0.05)


def test_reversal_short_window_is_inconclusive():
    s, truth = sessions(n=200, seed=5, beta_rev=-0.5, sd_co=0.002)
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=200)
    assert rep["verdict"] == "inconclusive" and "data limit" in rep["reason"]


def test_reversal_late_start_window_with_enough_days_is_at_best_inconclusive():
    # regression: with a supplied 15:45 signal, a late-starting window with n >= 500 used to be 'supported'
    s, truth = sessions(n=560, seed=1, beta_rev=-0.6, start="2024-08-01")
    rep = bh.closing_reversal(s, l_decision=_ldec(s, truth), n_boot=300)
    assert rep["n"] == 560 and rep["slope_L"] < -0.4 and rep["p_deflated_sidak"] < 0.01
    assert rep["reversal_leg"]["sharpe_net_annual"] > 0.5
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert "not implemented: archived window covers the claimed 2023-11..2026-10" in rep["reason"]
    s0, truth0 = sessions(n=560, seed=6, beta_rev=0.0, start="2024-08-01")
    rep0 = bh.closing_reversal(s0, l_decision=_ldec(s0, truth0), n_boot=300)
    assert rep0["verdict"] == "not_supported" and "slope <= -0.2" in rep0["reason"].split(" — ")[1]


# ----------------------------------------------------------------------------------------------- harnesses --

class _Entry:
    def __init__(self, created_at):
        self.created_at = created_at


class FakeArchive:
    """Synthetic stand-in for Archive: get(name) -> entry with created_at, load(name) -> rows."""

    def __init__(self, bundles, created_at="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created_at = bundles, created_at

    def get(self, name):
        return _Entry(self.created_at) if name in self.bundles else None

    def load(self, name):
        return iter(self.bundles[name])


def _rows(values, available_at="2029-01-01T00:00:00+00:00"):
    return [{"observed_at": "", "available_at": available_at, "value": v} for v in values]


def _archive(mom=0.0, beta_rev=0.0, n=N_FULL, syms=("SPY", "QQQ", "IWM", "GLD")):
    b = {}
    for k, sym in enumerate(syms):
        h, d, _ = simulate(n=n, seed=10 + k, mom=mom, beta_rev=beta_rev, sd_co=0.002)
        b["hourly-" + sym] = _rows(h)
        b["daily-history-" + sym] = _rows(d)
    return FakeArchive(b)


def test_harness_contract_and_missing_bundles():
    assert set(bh.THEORY_MAP) == {"T-427", "T-428"}
    assert all(v in bh.HARNESSES and v.startswith("hourly_") for v in bh.THEORY_MAP.values())
    for name, fn in bh.HARNESSES.items():
        stat, n, v, why = fn(FakeArchive({}))
        assert v == "inconclusive" and n == 0 and "hourly-SPY" in why and " — " in why


def test_harness_momentum_planted_and_null():
    stat, n, v, why = bh.hourly_half_hour_momentum(_archive(mom=0.0015))
    assert v == "supported" and n == N_FULL, why
    json.dumps(stat)
    stat, n, v, why = bh.hourly_half_hour_momentum(_archive(mom=0.0))
    assert v == "not_supported"


def test_harness_reversal_planted_and_null():
    stat, n, v, why = bh.hourly_closing_reversal(_archive(beta_rev=-0.5))
    assert v == "inconclusive" and stat["slope_L"] < -0.4 and "not implemented" in why
    json.dumps(stat)
    stat, n, v, why = bh.hourly_closing_reversal(_archive(beta_rev=0.0))
    assert v == "not_supported"


def test_harness_drops_rows_not_available_at_capture():
    arch = _archive(mom=0.0015, syms=("SPY", "QQQ", "IWM"))
    rows = arch.bundles["daily-history-SPY"]
    for r in rows[-100:]:
        r["available_at"] = "2031-01-01T00:00:00+00:00"                 # after capture: must be ignored
    stat, n, v, why = bh.hourly_half_hour_momentum(arch)
    assert n < N_FULL and stat["excluded"]["no_daily_bar"] >= 99
