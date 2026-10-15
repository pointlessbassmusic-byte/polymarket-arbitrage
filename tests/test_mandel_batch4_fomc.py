"""Batch-4 FOMC harnesses on synthetic series: planted effects pass, noise fails. No archive, no network."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch4_fomc as fm


def _days(start, end, weekdays_only=True):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(r):
    return 100 * np.cumprod(np.concatenate([[1.0], 1 + np.asarray(r)]))      # r[i-1] is the return ending on day i


def _events(days, every, first=20):
    return [days[i] for i in range(first, len(days), every)]


def _ret_index(days, ev):
    """Index into the return array r (r[i-1] ends on day i) of each event day."""
    pos = {d: i for i, d in enumerate(days)}
    return np.array([pos[e] - 1 for e in ev if e in pos and pos[e] > 0])


# ------------------------------------------------------------------------------------------------ calendar --

def test_scheduled_decision_days_filters_unscheduled():
    rows = [{"value": {"decision_day": "2020-03-18", "scheduled": True}}, {"value": {"decision_day": "2020-03-15", "scheduled": False}},
            {"value": {"decision_day": "2020-01-29", "scheduled": True}}]
    assert fm.scheduled_decision_days(rows) == ["2020-01-29", "2020-03-18"]
    assert fm.scheduled_decision_days(rows, scheduled_only=False) == ["2020-01-29", "2020-03-15", "2020-03-18"]


def test_cycle_week_definition():
    w = fm.weeks_from_origins(60, [10, 40])
    assert w[8] == -1                         # before the first cycle's day -1
    assert list(w[9:14]) == [0, 0, 0, 0, 0]   # days -1..+3 = week 0
    assert w[14] == 1 and w[18] == 1 and w[19] == 2
    assert w[38] == 5                         # day +28 of the first cycle (until the next meeting's day -2)
    assert w[39] == 0 and w[40] == 0          # next meeting's day -1 and day 0
    days = _days("2020-01-01", "2020-03-31")
    wk = fm.fomc_cycle_weeks(days, [days[10], "2021-01-01"])     # a meeting after the data is ignored
    assert wk[9] == 0 and wk[-1] == (len(days) - 1 - 10 + 1) // 5


def test_straddle_pnl_is_premium_when_price_unchanged():
    pnl, prem, coin = fm.short_straddle_pnl([100.0], [100.0], [0.16], 1 / 252)
    assert pnl[0] == pytest.approx(prem[0]) and coin[0] == pytest.approx(prem[0])
    assert prem[0] == pytest.approx(0.16 / np.sqrt(252) * np.sqrt(2 / np.pi), rel=0.01)    # ATM straddle ~ sigma sqrt(T) sqrt(2/pi)
    pnl2, _, _ = fm.short_straddle_pnl([100.0], [103.0], [0.16], 1 / 252)
    assert pnl2[0] == pytest.approx(prem[0] - 0.03)


def test_flag_diff_series_mean_is_difference():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 500); f = rng.random(500) < 0.1
    assert fm.flag_diff_series(x, f).mean() == pytest.approx(x[f].mean() - x[~f].mean())


# ----------------------------------------------------------------------------------------- T-214 SPX straddle --

def _spx_setup(event_sd, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-10-13")
    ev = _events(days, 32)
    r = rng.normal(0, 0.01, len(days) - 1)
    k = _ret_index(days, ev)
    r[k] = rng.normal(0, event_sd, len(k))
    vix = {d: 16.0 for d in days}
    return days, _closes(r), vix, ev


def test_spx_event_straddle_planted_and_null():
    days, c, vix, ev = _spx_setup(0.03)
    rep = fm.spx_event_straddle(days, c, vix, ev, n_boot=300)
    assert rep["label"] == "MODEL-PRICED" and rep["n"] >= 200
    assert rep["verdict"] == "supported", rep["reason"]
    days, c, vix, ev = _spx_setup(0.01, seed=1)
    null = fm.spx_event_straddle(days, c, vix, ev, n_boot=300)
    assert null["verdict"] == "not_supported", null["reason"]


def test_spx_event_straddle_too_few_events_is_inconclusive():
    days, c, vix, ev = _spx_setup(0.03)
    rep = fm.spx_event_straddle(days, c, vix, ev[:50], n_boot=100)
    assert rep["verdict"] == "inconclusive"


# ----------------------------------------------------------------------------------------- T-221 BTC straddle --

def _btc_setup(event_sd, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2021-03-01", "2026-10-14", weekdays_only=False)
    ev = [d for d in _events(days, 45) if d >= "2021-04-01"]
    r = rng.normal(0, 0.03, len(days) - 1)
    k = _ret_index(days, ev)
    r[k] = rng.normal(0, event_sd, len(k))
    dvol = {d: 60.0 for d in days}
    return days, _closes(r), dvol, ev


def test_btc_event_straddle_planted_and_null():
    days, c, dvol, ev = _btc_setup(0.09)
    rep = fm.btc_event_straddle(days, c, dvol, ev, n_boot=300)
    assert rep["n"] >= 40 and rep["verdict"] == "supported", rep["reason"]
    days, c, dvol, ev = _btc_setup(0.03, seed=3)
    null = fm.btc_event_straddle(days, c, dvol, ev, n_boot=300)
    assert null["verdict"] == "not_supported", null["reason"]


# ------------------------------------------------------------------------------------------- T-215 pre-drift --

def _drift_setup(event_mu, seed=0, start="1994-01-03"):
    rng = np.random.default_rng(seed)
    days = _days(start, "2026-10-13")
    ev = _events(days, 32)
    r = rng.normal(0.0003, 0.01, len(days) - 1)
    r[_ret_index(days, ev)] += event_mu
    return days, _closes(r), ev


def test_pre_fomc_drift_oos_planted_and_null():
    days, c, ev = _drift_setup(0.005)
    rep = fm.pre_fomc_drift_oos(days, c, ev, n_boot=300, n_placebo=300)
    assert rep["n"] >= 100 and rep["verdict"] == "supported", rep["reason"]
    days, c, ev = _drift_setup(0.0, seed=4)
    null = fm.pre_fomc_drift_oos(days, c, ev, n_boot=300, n_placebo=300)
    assert null["verdict"] == "not_supported", null["reason"]


def test_call_spread_overlay_gains_on_planted_rally():
    days, c, ev = _drift_setup(0.01)
    vix = {d: 16.0 for d in days}
    ov = fm.call_spread_overlay(days, c, vix, ev, "2012-01-01", "2026-12-31")
    assert ov["label"] == "MODEL-PRICED" and ov["mean_pnl_fomc_bps"] > ov["mean_pnl_other_bps"]


# --------------------------------------------------------------------------------------- T-341 statement day --

def test_statement_day_effect_planted_and_null():
    days, c, ev = _drift_setup(0.004, seed=5)
    rep = fm.statement_day_effect(days, c, ev, n_boot=300)
    assert rep["net"]["diff"] > 0.0015 and rep["verdict"] == "supported", rep["reason"]
    days, c, ev = _drift_setup(0.0, seed=6)
    null = fm.statement_day_effect(days, c, ev, n_boot=300)
    assert null["verdict"] == "not_supported", null["reason"]


def test_statement_day_effect_subsample_sign_decides():
    rng = np.random.default_rng(7)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 32)
    r = rng.normal(0.0003, 0.01, len(days) - 1)
    for i in _ret_index(days, ev):
        r[i] += 0.006 if days[i + 1] < "2016-01-01" else -0.004       # strong early effect, reversed after 2015
    rep = fm.statement_day_effect(days, _closes(r), ev, n_boot=300)
    assert rep["net"]["diff"] > 0.0015 and rep["sub_2016_2026_diff_bps"] < 0
    assert rep["verdict"] == "not_supported" and "2016-2026 net difference > 0" in rep["reason"]


# ---------------------------------------------------------------------------------------- T-342 cycle weeks --

def test_even_week_effect_planted_and_null():
    rng = np.random.default_rng(8)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 33)
    w = fm.fomc_cycle_weeks(days, ev)[1:]
    r = rng.normal(0.0003, 0.01, len(days) - 1)
    rep = fm.even_week_effect(days, _closes(r + np.isin(w, fm.EVEN_WEEKS) * 0.0012), ev, n_boot=300, n_placebo=200)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["parity_flip_shifts_bps"]["shift_5_trading_days"] < 0          # shifting by one week flips parity
    null = fm.even_week_effect(days, _closes(r), ev, n_boot=300, n_placebo=200)
    assert null["verdict"] == "not_supported", null["reason"]


# -------------------------------------------------------------------------------------- T-361 monetary momentum --

def _mm_setup(drift, seed=0, labels=None):
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 32)
    pos = {d: i for i, d in enumerate(days)}
    lab = rng.choice([-1, 0, 1], len(ev)) if labels is None else np.resize(np.asarray(labels), len(ev))
    level = 5.0; dgs2 = {}
    evset = dict(zip(ev, lab))
    for d in days:
        level += evset.get(d, 0) * 0.10 + rng.normal(0, 0.005)              # +/-10 bps on meeting days, small noise otherwise
        dgs2[d] = level
    r = rng.normal(0.0002, 0.01, len(days) - 1)
    for e, s in zip(ev, lab):
        i = pos[e] + 2                                                       # entry at the t+2 close
        if s != 0 and i + 15 < len(days):
            r[i:i + 15] += -s * drift                                        # rates down (s=-1) -> stocks up
    return days, _closes(r), dgs2, ev


def test_monetary_momentum_planted_and_null():
    days, c, dgs2, ev = _mm_setup(0.002)
    rep = fm.monetary_momentum(days, c, dgs2, ev, n_perm=2000, n_boot=300)
    assert rep["gap_net_pp"] > 1 and rep["verdict"] == "supported", rep["reason"]
    days, c, dgs2, ev = _mm_setup(0.0, seed=9)
    null = fm.monetary_momentum(days, c, dgs2, ev, n_perm=2000, n_boot=300)
    assert null["verdict"] == "not_supported", null["reason"]


def test_monetary_momentum_entry_is_after_publication():
    """A drift planted only on days t+1..t+2 (before the t+2 close entry) must not be captured."""
    rng = np.random.default_rng(10)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 32); pos = {d: i for i, d in enumerate(days)}
    lab = rng.choice([-1, 1], len(ev)); level = 5.0; dgs2 = {}; m = dict(zip(ev, lab))
    for d in days:
        level += m.get(d, 0) * 0.10; dgs2[d] = level
    r = rng.normal(0.0, 0.002, len(days) - 1)
    for e, s in zip(ev, lab):
        i = pos[e]
        r[i:i + 2] += -s * 0.02                                              # returns ending on t+1 and t+2
    rep = fm.monetary_momentum(days, _closes(r), dgs2, ev, n_perm=1000, n_boot=200)
    assert abs(rep["gap_gross_pp"]) < 0.5


def test_monetary_momentum_exact_5bp_move_is_neutral():
    """Regression: DGS2 has 2 decimals; (5.60 - 5.65) * 100 is -5.000000000000071 in floating point. 'More than 5 bps'
    means an exact 5 bp move is neutral."""
    rng = np.random.default_rng(13)
    days = _days("1994-01-03", "2026-10-13"); ev = _events(days, 32); pos = {d: i for i, d in enumerate(days)}
    exact = [(5.65, 5.60), (1.82, 1.87), (0.74, 0.69), (1.72, 1.77)]           # float error put these in exp / con
    moved = [(5.65, 5.59), (1.82, 1.88), (0.74, 0.64), (1.72, 1.82)]           # 6 and 10 bps: exp, con, exp, con
    assert (5.60 - 5.65) * 100 < -5 and (1.87 - 1.82) * 100 > 5                  # the float trap the fix removes
    dgs2 = {}
    for k, e in enumerate(ev):
        prev, now = (exact if k % 2 == 0 else moved)[(k // 2) % 4]
        dgs2[days[pos[e] - 1]] = prev; dgs2[e] = now
    r = rng.normal(0.0002, 0.01, len(days) - 1)
    rep = fm.monetary_momentum(days, _closes(r), dgs2, ev, n_perm=500, n_boot=100)
    n_cls = rep["n_expansionary"] + rep["n_contractionary"] + rep["n_neutral"]; n_exact = (n_cls + 1) // 2
    assert rep["n_neutral"] == n_exact, (rep["n_neutral"], n_exact)
    assert abs(rep["n_expansionary"] - rep["n_contractionary"]) <= 1 and rep["n_expansionary"] + rep["n_contractionary"] == n_cls - n_exact


def test_monetary_momentum_min_n_counts_only_expansionary_and_contractionary():
    """Regression: min_n is compared with the meetings that enter the gap, not with all classified meetings."""
    days, c, dgs2, ev = _mm_setup(0.002, seed=14, labels=[-1, 0, 1, 0, 0])      # 2 of every 5 meetings are surprises
    rep = fm.monetary_momentum(days, c, dgs2, ev, n_perm=2000, n_boot=300)
    n_used = rep["n_expansionary"] + rep["n_contractionary"]
    assert rep["n_classified"] >= 120 and n_used < 120 and rep["n"] == n_used
    assert rep["verdict"] == "inconclusive", rep["reason"]
    assert rep["reason"].startswith(f"only {n_used} expansionary+contractionary meetings (min_n 120)")
    assert rep["criteria_verdict_if_min_n_ignored"] == "supported" and all(rep["criteria"].values())   # criteria still reported
    assert rep["reason"].rsplit(" — ", 1)[1].startswith("inconclusive")
    ok = fm.monetary_momentum(days, c, dgs2, ev, n_perm=2000, n_boot=300, min_n=n_used)
    assert ok["verdict"] == "supported", ok["reason"]


# ------------------------------------------------------------------------------- unscheduled-meeting exclusion --

def test_align_to_trading_days():
    days = _days("2020-03-02", "2020-03-20")
    assert fm.align_to_trading_days(days, ["2020-03-15", "2020-03-03", "2020-03-21", "2020-03-01"]) == {"2020-03-16", "2020-03-03"}


def test_unscheduled_days_include_release_day():
    class _A:
        def load(self, name):
            return [{"value": {"decision_day": "2020-03-02", "scheduled": False}}, {"value": {"decision_day": "2020-03-15", "scheduled": False}},
                    {"value": {"decision_day": "2020-03-18", "scheduled": True}}]
    assert fm._fomc_unscheduled(_A()) == ["2020-03-02", "2020-03-03", "2020-03-15"]


def test_sunday_unscheduled_meeting_excludes_the_next_session():
    """Regression: an unscheduled meeting on a Sunday (2020-03-15) must drop the Monday reaction session (2020-03-16)
    from the non-FOMC group in T-214 and T-215."""
    days, c, ev = _drift_setup(0.0, seed=15)
    assert "2020-03-16" in days and "2020-03-16" not in ev and "2020-03-15" not in days
    i = days.index("2020-03-16"); r = c[1:] / c[:-1] - 1; r[i - 1] = -0.11; c = _closes(r)     # a -11% Monday
    base = fm.pre_fomc_drift_oos(days, c, ev, n_boot=200, n_placebo=50)
    ex = fm.pre_fomc_drift_oos(days, c, ev, exclude_days=["2020-03-15"], n_boot=200, n_placebo=50)
    assert ex["test"]["n_other"] == base["test"]["n_other"] - 1 and ex["test"]["mean_other"] > base["test"]["mean_other"]
    vix = {d: 16.0 for d in days}
    P = fm.event_straddle_panel(days, c, vix, ev, 1 / 252, 252, exclude_days=["2020-03-15"])
    assert "2020-03-16" not in set(P["days"]) and "2020-03-13" in set(P["days"])
    s0 = fm.spx_event_straddle(days, c, vix, ev, n_boot=100)
    s1 = fm.spx_event_straddle(days, c, vix, ev, exclude_days=["2020-03-15"], n_boot=100)
    assert s1["full"]["n_other"] == s0["full"]["n_other"] - 1


# ---------------------------------------------------------------------------------------------- T-273 GVZ --

def _gvz_setup(bump, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2009-09-01", "2026-10-01"); ev = [d for d in _events(days, 31) if "2009-10-01" <= d <= "2026-09-30"]
    x = 20 + rng.normal(0, 0.5, len(days))
    pos = {d: i for i, d in enumerate(days)}
    for e in ev:
        i = pos[e]
        x[max(0, i - 4):i + 1] += bump                                       # premium builds into the event, gone the day after
    return {d: float(v) for d, v in zip(days, x)}, ev


def test_gvz_fomc_change_planted_and_null():
    gvz, ev = _gvz_setup(1.5)
    rep = fm.gvz_fomc_change(gvz, ev, vix=gvz, n_boot=500)
    assert rep["n"] >= 100 and rep["gvz"]["mean"] < -1 and rep["verdict"] == "supported", rep["reason"]
    gvz0, ev0 = _gvz_setup(0.0, seed=11)
    null = fm.gvz_fomc_change(gvz0, ev0, n_boot=500)
    assert null["verdict"] == "not_supported", null["reason"]


# ------------------------------------------------------------------------------------------- module contract --

class _EmptyArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


def test_contract_and_missing_bundles_are_inconclusive():
    assert set(fm.THEORY_MAP) == {"T-214", "T-215", "T-221", "T-273", "T-341", "T-342", "T-361"}
    assert set(fm.THEORY_MAP.values()) <= set(fm.HARNESSES)
    for name, fn in fm.HARNESSES.items():
        assert name == name.lower() and name.startswith("fomc_")
        stat, n, verdict, reason = fn(_EmptyArchive())
        assert verdict == "inconclusive" and n == 0 and "missing data bundles" in reason and stat["missing_bundles"]


def test_reason_ends_with_verdict_explanation():
    days, c, ev = _drift_setup(0.0, seed=12)
    rep = fm.statement_day_effect(days, c, ev, n_boot=200)
    assert " — " in rep["reason"] and rep["reason"].rsplit(" — ", 1)[1].startswith(("failed", "all criteria", "implemented"))
    stat = fm._clean(rep)
    import json
    json.dumps(stat)
