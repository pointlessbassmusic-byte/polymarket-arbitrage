"""Batch-6c calendar harnesses (T-345 month-end rebalancing flow, T-450 pension rebalancing slope, T-347 Friday-minus-
Monday speculative spread, T-349 pre-holiday effect, T-357 presidential year 3) on synthetic data only: the rule-based NYSE
calendar is checked against known dates; for every core judge a planted effect passes and a null does not; the
month-end windows, the rule-12 readings, the permutation machinery and rule 5 are checked directly; every harness runs on
a fake archive (JSON-safe, missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_cal as m

NB, NP = 200, 500                      # bootstrap and permutation draws in tests


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", NB)
    monkeypatch.setattr(m, "N_PERM", NP)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _yahoo(days, close, sym="X"):
    return [{"available_at": d + "T21:00:00+00:00",
             "value": {"symbol": sym, "t": datetime.fromisoformat(d + "T14:30:00+00:00").timestamp(),
                       "close": float(c), "adjclose": float(c)}} for d, c in zip(days, close)]


def _fred(days, vals):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(x)}} for d, x in zip(days, vals)]


def _cboe(days, vals):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(x)}} for d, x in zip(days, vals)]


def sessions(first, last):
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        if m.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _px(r):
    return 100 * np.cumprod(1 + np.asarray(r, float))


# ----------------------------------------------------------------------------------------------- NYSE calendar --

def test_easter_and_good_friday():
    for y, e in [(2000, date(2000, 4, 23)), (2008, date(2008, 3, 23)), (2019, date(2019, 4, 21)), (2025, date(2025, 4, 20)),
                 (1987, date(1987, 4, 19)), (2038, date(2038, 4, 25))]:
        assert m.easter_sunday(y) == e
    assert m.nyse_scheduled_holidays(2025)[date(2025, 4, 18)] == "Good Friday"


def test_holiday_rules_and_observance():
    h21 = m.nyse_scheduled_holidays(2021)
    assert date(2021, 12, 24) in h21                       # Christmas on Saturday -> Friday closed
    assert date(2021, 12, 31) not in h21                   # New Year 2022 on Saturday: 31 Dec stays open
    assert date(2022, 1, 1) not in m.nyse_scheduled_holidays(2022) and date(2022, 1, 3) not in m.nyse_scheduled_holidays(2022)
    assert date(2017, 1, 2) in m.nyse_scheduled_holidays(2017)          # Sunday New Year -> Monday
    assert date(2020, 7, 3) in m.nyse_scheduled_holidays(2020)          # Saturday 4 July -> Friday
    assert date(2022, 6, 20) in m.nyse_scheduled_holidays(2022)         # Juneteenth (Sunday) -> Monday, from 2022
    assert not any(n == "Juneteenth" for n in m.nyse_scheduled_holidays(2021).values())
    assert not any(n.startswith("Martin") for n in m.nyse_scheduled_holidays(1997).values())
    assert date(1998, 1, 19) in m.nyse_scheduled_holidays(1998)
    assert date(2024, 11, 28) in m.nyse_scheduled_holidays(2024) and date(2024, 9, 2) in m.nyse_scheduled_holidays(2024)
    assert date(2024, 5, 27) in m.nyse_scheduled_holidays(2024) and date(2024, 2, 19) in m.nyse_scheduled_holidays(2024)
    assert len(m.nyse_scheduled_holidays(2024)) == 10 and len(m.nyse_scheduled_holidays(2010)) == 9   # 2010: New Year 2011 on Saturday is not a 2010 closure
    with pytest.raises(ValueError):
        m.nyse_scheduled_holidays(1965)


def test_unscheduled_closures_are_not_holidays():
    assert m.nyse_closure("2001-09-11") == "September 11 attacks" and not m.is_nyse_session("2012-10-29")
    pre = m.pre_holiday_sessions("2001-01-01", "2012-12-31")
    assert "2001-09-10" not in pre and "2012-10-26" not in pre and "2004-06-10" not in pre
    assert pre["2001-11-21"] == "Thanksgiving Day" and pre["2007-04-05"] == "Good Friday"
    assert "2006-12-29" in pre                                           # New Year 2007 (Ford funeral the next day)
    assert m.post_holiday_sessions("2007-01-01", "2007-01-10") == {"2007-01-03": "New Year's Day"}


def test_pre_holiday_counts_match_the_rule_schedule():
    pre = m.pre_holiday_sessions("2024-01-01", "2024-12-31")
    assert sorted(pre) == ["2024-01-12", "2024-02-16", "2024-03-28", "2024-05-24", "2024-06-18", "2024-07-03",
                           "2024-08-30", "2024-11-27", "2024-12-24", "2024-12-31"]
    assert m.pre_holiday_sessions("2021-12-01", "2021-12-31") == {"2021-12-23": "Christmas Day"}   # 31 Dec 2021 is not pre-holiday


def test_calendar_check_flags_gaps_and_closed_bars():
    days = sessions("2024-01-02", "2024-12-31")
    ok = m.calendar_check(days)
    assert ok["unexplained_gaps"] == [] and ok["bars_on_closed_days"] == [] and ok["scheduled_holiday_gaps"] == 9
    bad = [d for d in days if d != "2024-03-05"] + ["2024-07-04"]
    ch = m.calendar_check(sorted(bad))
    assert ch["unexplained_gaps"] == ["2024-03-05"] and ch["bars_on_closed_days"] == ["2024-07-04"]


# ---------------------------------------------------------------------------------------- statistics helpers --

def test_flagged_series_means_are_the_differences():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 300); f = rng.random(300) < 0.3
    assert m.flag_diff_series(x, f).mean() == pytest.approx(x[f].mean() - x[~f].mean())
    wd = np.arange(300) % 5
    assert m.contrast_series(x, wd == 4, wd == 0).mean() == pytest.approx(x[wd == 4].mean() - x[wd == 0].mean())


def test_permuted_labels_stay_within_groups():
    labels = np.array([1, 2, 3, 4, 1, 2, 3, 4, 4, 1], dtype=np.int8)
    groups = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 3])
    for L in m.permuted_labels(labels, groups, n_perm=50, seed=3):
        for g in np.unique(groups):
            assert sorted(L[:, groups == g][0].tolist()) == sorted(labels[groups == g].tolist())
        assert (L[:, 8] == 4).all() and (L[:, 9] == 1).all()
        assert len({tuple(r) for r in L[:, :4].tolist()}) > 1


def test_holm_agree_and_bills():
    h = m._holm({"a": 0.01, "b": 0.04, "c": None}, m=3)
    assert h["a"] == pytest.approx(0.03) and h["b"] == pytest.approx(0.08) and h["c"] is None
    assert m._agree([True, True]) is True and m._agree([False, False]) is False
    assert m._agree([True, False]) is None and m._agree([True, None]) is None
    assert m.dtb3_cont(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    b = m.Bills({"2020-01-02": 4.0, "2020-01-03": 8.0})
    assert b.rate("2020-01-03") == pytest.approx(m.dtb3_cont(4.0))
    assert b.growth("2020-01-06", "2020-01-08") == pytest.approx(math.exp(m.dtb3_cont(8.0) * 2 / 365) - 1)


def test_monte_carlo_band_decides_p_only_when_clear():
    assert m.decide_p(0.01, 10000) is True and m.decide_p(0.20, 10000) is False
    assert m.decide_p(0.048, 10000) is None and m.decide_p(0.052, 10000) is None      # within simulation error of 0.05
    assert m.decide_p(0.048, 10 ** 7) is True and m.decide_p(None, 100) is None
    d = np.random.default_rng(2).normal(0.3, 1, 200)
    one = m.studentized_p(d, 5, 200, 0)[0]; five = m.studentized_p(d, 5, 200, 0, n_seeds=5)[0]
    assert five == pytest.approx(np.mean([m.studentized_p(d, 5, 200, k)[0] for k in range(5)])) and one > 0


def _const_batches(pg, pl, calls=None):
    def batch(k):
        if calls is not None:
            calls.append(k)
        return pg, pl
    return batch


def test_escalate_p_adds_draws_until_the_band_clears():
    # regression (T-349): a p undecided at 5 x 200 draws is resolved by more draws, not left to cap the verdict
    calls = []
    pg, pl, nd = m.escalate_p(_const_batches(0.043, 0.958, calls), 200, 5, 50)
    assert nd == 17 * 200 and calls == list(range(17))                # 16 x 200: 0.043 + 1.96 se = 0.0500 still straddles
    assert m.decide_p(pg, nd) is True and m.decide_p(pl, nd) is False
    assert m.decide_p(0.043, 5 * 200) is None and m.escalate_p(_const_batches(0.043, 0.958), 200, 5, 5)[2] == 1000
    pg, _, nd = m.escalate_p(_const_batches(0.0499, 0.951), 200, 5, 50)
    assert nd == 50 * 200 and m.decide_p(pg, nd) is None              # undecided only when it still straddles at the cap
    calls = []
    assert m.escalate_p(_const_batches(0.01, 0.99, calls), 200, 5, 50)[2] == 1000 and calls == list(range(5))
    assert m.escalate_p(_const_batches(None, None), 200, 5, 50)[:2] == (None, None)


def test_escalated_p_pools_the_seed_sequence():
    d = np.random.default_rng(4).normal(0.3, 1, 200)
    pg, pl, nd = m.studentized_p_escalated(d, 5, 200, 0, 5, 50)
    assert nd == 1000 and (pg, pl) == pytest.approx(m.studentized_p(d, 5, 200, 0, n_seeds=5))   # decided: no extra seeds
    x = np.random.default_rng(5).normal(0, 1, 300); f = np.arange(300) % 3 == 0
    x[f] += 0.6
    obs, pg, pl, nd = m.label_perm_test(x, f, None, 200, 0, 10)
    assert nd == 200 and (obs, pg, pl) == pytest.approx(m.label_perm_diff(x, f, None, 200, 0))


def test_pre_holiday_escalates_an_undecided_bootstrap_p(monkeypatch):
    # regression (T-349): with a borderline p every other criterion passing, the verdict follows the escalated p
    days, c = _holiday_series(0.004, 11)
    monkeypatch.setattr(m, "block_bootstrap_pvalue", lambda a, b, n_boot=0, block_len=0, seed=0: 0.043 if np.mean(a) > 0 else 0.958)
    rep = m.pre_holiday_effect(days, c, n_boot=NB)
    assert rep["test"]["draws"] == 17 * NB and rep["verdict"] == "supported", rep["reason"]
    assert "17 seeds x 200" in rep["reason"] and rep["reason"].endswith("all criteria pass")
    monkeypatch.setattr(m, "MAX_SEEDS", m.N_SEEDS)                      # the defect: no escalation -> capped at inconclusive
    rep = m.pre_holiday_effect(days, c, n_boot=NB)
    assert rep["verdict"] == "inconclusive" and rep["test"]["draws"] == m.N_SEEDS * NB
    monkeypatch.setattr(m, "MAX_SEEDS", 50)
    monkeypatch.setattr(m, "block_bootstrap_pvalue", lambda a, b, n_boot=0, block_len=0, seed=0: 0.0499 if np.mean(a) > 0 else 0.951)
    rep = m.pre_holiday_effect(days, c, n_boot=NB)
    assert rep["verdict"] == "inconclusive" and rep["test"]["draws"] == 50 * NB
    assert f"escalation cap ({50 * NB} resamples)" in rep["reason"]


def test_criterion_permutation_and_bootstrap_p_escalate_uniformly(monkeypatch):
    # the same escalation for every criterion p in the module (T-345, T-347, T-357), reported p's untouched
    monkeypatch.setattr(m, "block_bootstrap_pvalue", lambda a, b, n_boot=0, block_len=0, seed=0: 0.043 if np.mean(a) > 0 else 0.958)
    monkeypatch.setattr(m, "_perm_p", lambda obs, draws: (0.043, 0.958) if obs > 0 else (0.958, 0.043))
    spy, tlt = _rebal_series(-0.015, 5)
    rep = m.rebalancing_flow(spy, tlt, n_perm=NP, n_boot=NB)
    for r in rep["readings"].values():
        assert r["perm_draws"] == 7 * NP and r["boot_draws"] == 17 * NB
    assert rep["verdict"] == "supported", rep["reason"]
    spec, safe = _spread_series(0.0012, 9)
    rep = m.speculative_spread(spec, safe, n_perm=NP, n_boot=NB)
    assert rep["contrast"]["perm_draws"] == 7 * NP and rep["contrast"]["boot_draws"] == 17 * NB
    assert rep["verdict"] == "supported", rep["reason"]
    yrs, r = _annual(0.20, 14)
    rep = m.presidential_year3(yrs, r, n_perm=NP, n_boot=NB)
    assert all(p["draws"] == 7 * NP for p in rep["permutation"].values()) and rep["verdict"] == "supported", rep["reason"]
    assert m.group_test(np.arange(50.0), np.arange(50) % 5 == 0, 5, NB)["draws"] == NB          # reported: no escalation


def test_undecided_criteria_are_labelled_not_unimplemented():
    rows = m._undecided([("a", True, False), ("b", None, False)], "undecided: x")
    assert rows[1][0] == "b (undecided: x)" and rows[0][0] == "a"
    v, why, _ = m._judge(rows, 30, 20, "units")
    assert v == "inconclusive" and "undecided: x" in why


def test_rule5_keeps_decisive_failures_only():
    v, why, crit = m._judge([("a", True, False), ("b", False, False)], 10, 20, "units")
    assert v == "inconclusive" and "house rule 5" in why
    v, _, _ = m._judge([("a", True, False), ("b", False, True)], 10, 20, "units")
    assert v == "not_supported"
    v, _, _ = m._judge([("a", True, False), ("b", True, False)], 10, 20, "units")
    assert v == "inconclusive"
    assert m._judge([("a", True, False)], 20, 20, "units")[0] == "supported"


# ----------------------------------------------------------------------------------------- month-end windows --

def test_month_end_table_t3_and_previous_close_reading():
    days = sessions("2024-10-01", "2024-12-31")
    a = _px(np.full(len(days), 0.001)); b = _px(np.zeros(len(days)))
    tab = m.month_end_table(days, a, b, decision=3, first="2024-11", last="2024-11")
    assert len(tab) == 1
    r = tab[0]
    assert r["decision_day"] == "2024-11-26" and r["exit_day"] == "2024-11-29"          # Thanksgiving 28 Nov
    k = days.index("2024-11-26"); base = days.index("2024-10-31")
    assert r["S"] == pytest.approx(a[k] / a[base] - 1) and r["ra"] == pytest.approx(a[k + 2] / a[k] - 1)
    r1 = m.month_end_table(days, a, b, decision=3, lag=1, first="2024-11", last="2024-11")[0]
    assert r1["signal_day"] == "2024-11-25" and r1["decision_day"] == "2024-11-26"         # same window, earlier signal
    w = m.month_end_table(days, a, b, decision=4, exit_next=True, first="2024-11", last="2024-11")[0]
    assert w["decision_day"] == "2024-11-25" and w["exit_day"] == "2024-12-02"            # last 3 sessions + first of December
    q = m.month_end_table(days, a, b, decision=3, first="2024-12", last="2024-12", base="quarter")
    assert q == []                                                                        # no later month: December incomplete
    days2 = sessions("2024-09-01", "2025-01-31")
    a2 = _px(np.full(len(days2), 0.001))
    q = m.month_end_table(days2, a2, None, decision=3, first="2024-12", last="2024-12", base="quarter")[0]
    k = days2.index(q["signal_day"]); base = days2.index("2024-09-30")
    assert q["S"] == pytest.approx(a2[k] / a2[base] - 1)


# ----------------------------------------------------------------------------------- T-345 rebalancing flow --

def _rebal_series(plant: float, seed: int):
    days = sessions("2002-07-01", "2026-10-14")
    rng = np.random.default_rng(seed)
    rs, rt = rng.normal(0.0003, 0.01, len(days)), rng.normal(0.0002, 0.008, len(days))
    if plant:
        months, by = m.month_sessions(days)
        cs, ct = _px(rs), _px(rt)
        for j in range(1, len(months)):
            idx, base = by[months[j]], by[months[j - 1]][-1]
            k = idx[-3]
            if cs[k] / cs[base] - ct[k] / ct[base] > 0.02:
                rs[idx[-2]] += plant / 2; rs[idx[-1]] += plant / 2
        # prices after planting (the plant touches only the last two sessions, after the signal close)
    return (days, _px(rs)), (days, _px(rt))


def test_rebalancing_flow_planted_passes():
    spy, tlt = _rebal_series(-0.015, 5)
    rep = m.rebalancing_flow(spy, tlt, n_perm=NP, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] >= 80 and rep["readings"]["entry close"]["net"] < -0.0015
    assert rep["reason"].endswith("all criteria pass")


def test_rebalancing_flow_null_fails():
    spy, tlt = _rebal_series(0.0, 6)
    rep = m.rebalancing_flow(spy, tlt, n_perm=NP, n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]


def test_rebalancing_flow_below_min_n_never_supported():
    spy, tlt = _rebal_series(-0.015, 5)
    rep = m.rebalancing_flow(spy, tlt, first="2002-01", last="2006-12", n_perm=NP, n_boot=NB)
    assert rep["n"] < 80 and rep["verdict"] != "supported" and "house rule 5" in rep["reason"]


def test_rebalancing_grid_has_ten_trials():
    spy, tlt = _rebal_series(-0.015, 5)
    g = m.rebalancing_grid(spy, tlt, spy, None, n_perm=NP, n_boot=NB)
    assert len(g) == 10 and g["BTC analogue"]["p"] is None and g["2pp, T-3"]["p"] < 0.05
    assert all("p_holm" in v for v in g.values())


# ------------------------------------------------------------------------------------- T-450 pension flow -----

def _flow_series(beta: float, seed: int):
    days = sessions("2003-08-01", "2026-10-14")
    rng = np.random.default_rng(seed)
    rs, ra = rng.normal(0.0003, 0.01, len(days)), rng.normal(0.0001, 0.003, len(days))
    if beta:
        months, by = m.month_sessions(days)
        for j in range(1, len(months) - 1):
            cs, ca = _px(rs), _px(ra)
            idx, base = by[months[j]], by[months[j - 1]][-1]
            k = idx[-4]
            x = (cs[k] / cs[base] - 1) - (ca[k] / ca[base] - 1)
            for t in (idx[-3], idx[-2], idx[-1], by[months[j + 1]][0]):
                rs[t] += beta * x / 4
    bills = m.Bills({"2003-01-02": 2.0})
    return (days, _px(rs)), (days, _px(ra)), bills


def test_pension_flow_planted_passes():
    spy, agg, bills = _flow_series(-0.4, 7)
    rep = m.pension_flow(spy, agg, bills, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] == 276 and rep["readings"]["entry close"]["t"] <= -2


def test_pension_flow_null_fails():
    spy, agg, bills = _flow_series(0.0, 8)
    rep = m.pension_flow(spy, agg, bills, n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]


def test_ols_nw_matches_ols_slope():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 400); y = 0.5 * x + rng.normal(0, 1, 400)
    r = m.ols_nw(y, x, 5)
    assert r["slope"] == pytest.approx(np.polyfit(x, y, 1)[0]) and r["t"] > 5
    assert m.nw_lags(276) == 5


def test_bond_proxy_moves_against_yields():
    days = ["2020-01-02", "2020-01-03", "2020-01-06"]
    idx = m.bond_proxy_index(days, {"2020-01-02": 2.0, "2020-01-03": 2.1, "2020-01-06": 2.1})
    assert idx[1] < idx[0] and idx[2] > idx[1]


# ---------------------------------------------------------------------------------- T-347 speculative spread --

def _spread_series(plant: float, seed: int):
    days = sessions("2011-05-05", "2026-10-14")
    rng = np.random.default_rng(seed)
    common = rng.normal(0.0004, 0.01, len(days))
    spread = rng.normal(0.0, 0.006, len(days))
    wd = np.array([date.fromisoformat(d).weekday() for d in days])
    spread = spread + plant * (wd == 4) - plant * (wd == 0)
    return (days, _px(common + spread)), (days, _px(common))


def test_speculative_spread_planted_passes():
    spec, safe = _spread_series(0.0012, 9)
    rep = m.speculative_spread(spec, safe, n_perm=NP, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] >= 600 and rep["contrast"]["perm_p_greater"] < 0.05


def test_speculative_spread_null_fails():
    spec, safe = _spread_series(0.0, 10)
    rep = m.speculative_spread(spec, safe, n_perm=NP, n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]


def test_within_week_permutation_keeps_weekday_counts():
    days = sessions("2024-01-02", "2024-03-29")
    x = np.arange(len(days), dtype=float)
    w = m.weekday_contrast(days, x, n_boot=NB, n_perm=200)
    assert w["n_a"] == sum(date.fromisoformat(d).weekday() == 4 for d in days)
    assert 0 < w["perm_p_greater"] <= 1 and 0 < w["perm_p_less"] <= 1


# ----------------------------------------------------------------------------------------- T-349 pre-holiday --

def _holiday_series(plant: float, seed: int, first="2000-05-26"):
    days = sessions(first, "2026-10-14")
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0003, 0.012, len(days))
    pre = m.pre_holiday_sessions(days[0], days[-1])
    r += plant * np.array([d in pre for d in days])
    return days, _px(r)


def test_pre_holiday_planted_passes():
    days, c = _holiday_series(0.004, 11)
    rep = m.pre_holiday_effect(days, c, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert 230 <= rep["n"] <= 240 and rep["pre_holiday_sessions_without_a_bar"] == []


def test_pre_holiday_null_fails():
    days, c = _holiday_series(0.0, 12)
    rep = m.pre_holiday_effect(days, c, n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]


def test_pre_holiday_uses_the_rule_calendar_not_gaps():
    days, c = _holiday_series(0.0, 13)
    drop = {"2005-03-08", "2010-06-15"}                           # missing bars on ordinary sessions
    keep = [i for i, d in enumerate(days) if d not in drop]
    rep = m.pre_holiday_effect([days[i] for i in keep], c[keep], n_boot=NB)
    assert rep["n"] == m.pre_holiday_effect(days, c, n_boot=NB)["n"]
    pre = m.pre_holiday_sessions(days[1], days[-1])
    assert "2005-03-07" not in pre and "2001-09-10" not in pre


def test_holiday_week_flags():
    ds = sessions("2024-11-20", "2025-01-03")
    f = dict(zip(ds, m.holiday_week_flags(ds)))
    assert f["2024-11-25"] and f["2024-11-29"] and not f["2024-11-22"] and not f["2024-12-02"]
    assert f["2024-12-24"] and f["2024-12-31"] and not f["2024-12-23"] and not f["2025-01-02"]


# ------------------------------------------------------------------------------------ T-357 presidential cycle --

def _annual(plant: float, seed: int):
    yrs = np.arange(1928, 2026)
    rng = np.random.default_rng(seed)
    r = rng.normal(0.07, 0.15, yrs.size) + plant * (m.cycle_year(yrs) == 3)
    return yrs, r


def test_cycle_year_labels():
    assert m.cycle_year([1928, 1929, 1930, 1931, 1932, 2023, 2024, 2025]).tolist() == [4, 1, 2, 3, 4, 3, 4, 1]


def test_presidential_planted_passes():
    yrs, r = _annual(0.20, 14)
    rep = m.presidential_year3(yrs, r, n_perm=NP, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] == 24 and rep["halves"]["first"]["n_year3"] == 12 and rep["halves"]["second"]["n_year3"] == 12


def test_presidential_null_fails():
    yrs, r = _annual(0.0, 15)
    rep = m.presidential_year3(yrs, r, n_perm=NP, n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]


def test_annual_returns_complete_years_only():
    days = ["1927-12-30", "1928-12-31", "1929-12-31", "1930-06-30"]
    y, r = m.annual_returns(days, np.array([10.0, 12.0, 9.0, 8.0]))
    assert y.tolist() == [1928, 1929] and r.tolist() == pytest.approx([0.2, -0.25])   # a 1930 bar proves 1929 complete
    y, r = m.annual_returns(days + ["1931-01-02"], np.array([10.0, 12.0, 9.0, 8.0, 8.5]))
    assert y.tolist() == [1928, 1929, 1930]


# --------------------------------------------------------------------------------------------- harness level --

def _archive(full=True):
    rng = np.random.default_rng(20)
    b = {}
    d1 = sessions("2002-07-30", "2026-10-14")
    for sym, sd in (("SPY", 0.01), ("TLT", 0.008), ("AGG", 0.003), ("IWM", 0.012), ("GLD", 0.01)):
        b[f"daily-history-{sym}"] = _yahoo(d1, _px(rng.normal(0.0002, sd, len(d1))), sym)
    d2 = sessions("2011-05-05", "2026-10-14")
    for sym in ("SPHB", "SPLV", "USMV"):
        b[f"daily-history-{sym}"] = _yahoo(d2, _px(rng.normal(0.0003, 0.01, len(d2))), sym)
    b["cboe-VIX-history"] = _cboe(d2, 15 * np.exp(np.cumsum(rng.normal(0, 0.05, len(d2)))))
    b["fred-DTB3"] = _fred(d1, np.full(len(d1), 2.0))
    yrs = list(range(1927, 2027))
    gd = [m._last_weekday_of(y, 12, 4).isoformat() if y < 2026 else "2026-10-13" for y in yrs]
    b["daily-history--GSPC"] = _yahoo(gd, _px(rng.normal(0.07, 0.15, len(gd))), "^GSPC")
    if not full:
        del b["daily-history-TLT"]
    return FakeArchive(b)


def test_harness_contract_and_json():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-345", "T-347", "T-450", "T-349", "T-357"}
    assert all(h.startswith("b6c_cal_") and h == h.lower() for h in m.HARNESSES)
    a = _archive()
    for name, fn in m.HARNESSES.items():
        stat, n, v, why = fn(a)
        json.dumps(stat, allow_nan=False)
        assert isinstance(n, int) and v in ("supported", "not_supported", "inconclusive") and " — " in why, name
        _, tail = why.rsplit(" — ", 1)
        assert tail.startswith(("all criteria pass", "failed:", "implemented criteria pass", "only ")), (name, tail)


def test_harness_secondaries_report_unarchived_symbols():
    a = _archive()
    stat, n, v, why = m.b6c_cal_weekday_speculative_spread(a)
    sec = stat["secondary_holm"]
    assert sec["IWO-IWN (small growth minus small value)"]["p"] is None and "IWO" in why and "ARKK" in why
    assert sec["SPHB-USMV (USMV as the safe leg)"]["p"] is not None
    stat, n, v, why = m.b6c_cal_pre_holiday(a)
    assert stat["secondary_holm"]["Cultural New Year month in FXI/EWY/INDA"]["p"] is None and "FXI" in why
    assert stat["calendar_check"]["unexplained_gaps"] == 0 and stat["calendar_check"]["bars_on_closed_days"] == 0
    stat, n, v, why = m.b6c_cal_month_end_rebalancing(a)
    assert stat["declared_grid"]["BTC analogue"]["p"] is None and len(stat["declared_grid"]) == 10


def test_missing_bundles_inconclusive():
    a = _archive(full=False)
    stat, n, v, why = m.b6c_cal_month_end_rebalancing(a)
    assert v == "inconclusive" and n == 0 and stat["missing_bundles"] == ["daily-history-TLT"]
    stat, n, v, why = m.b6c_cal_pension_rebalancing(FakeArchive({}))
    assert v == "inconclusive" and set(stat["missing_bundles"]) == {"daily-history-SPY", "daily-history-AGG", "fred-DTB3"}


def test_rows_after_capture_are_dropped():
    days = sessions("2024-01-02", "2024-01-10")
    a = FakeArchive({"daily-history-SPY": _yahoo(days, np.arange(1, len(days) + 1))}, created="2024-01-08T00:00:00+00:00")
    d, c = m._daily(a, "daily-history-SPY")
    assert d[-1] == "2024-01-05"                    # the 01-08 bar is stamped available at 21:00 that day
