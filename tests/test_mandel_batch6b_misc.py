"""Batch-6b misc harnesses (T-188 box-bill spread vs VIX, T-518 OPEC USO straddle, T-522 election-day SPY move, T-275
SLV call backspread) on synthetic data only: for every core judge a planted effect passes and a null does not; the
calendars, rates, pricing engines and the point-in-time handling of OPEC dates are checked directly; every harness runs on
a fake archive (JSON-safe, labelled, missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.data.cboe_strategy import trading_days
from mandel.experiments import batch6b_misc as m

NB = 200                                # bootstrap resamples in tests


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", NB)
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


def _yahoo(days, close, sym, adj=None):
    adj = close if adj is None else adj
    return [{"available_at": d + "T21:00:00+00:00",
             "value": {"symbol": sym, "t": datetime.fromisoformat(d + "T14:30:00+00:00").timestamp(),
                       "close": float(c), "adjclose": float(a)}} for d, c, a in zip(days, close, adj)]


def _cboe(days, level):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(x)}} for d, x in zip(days, level)]


def _fred(days, vals):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(x)}} for d, x in zip(days, vals)]


def _gbm(n, sigma_d, seed, mu=0.0, s0=100.0):
    rng = np.random.default_rng(seed)
    lr = rng.normal(mu - 0.5 * sigma_d ** 2, sigma_d, n)
    lr[0] = 0.0
    return s0 * np.exp(np.cumsum(lr)), lr


# ------------------------------------------------------------------------------------------- rates, calendars --

def test_dtb3_conversion_and_prior_print():
    assert m.dtb3_cont(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    b = m.Bills({"2020-01-02": 4.0, "2020-01-03": 8.0})
    assert b.rate("2020-01-03") == pytest.approx(m.dtb3_cont(4.0))           # the 01-03 print is not known on 01-03
    assert b.rate("2020-01-06") == pytest.approx(m.dtb3_cont(8.0))


def test_election_days_fixed_by_law():
    assert m.election_day(1994) == date(1994, 11, 8)
    assert m.election_day(2000) == date(2000, 11, 7)
    assert m.election_day(2012) == date(2012, 11, 6)
    assert m.election_day(2020) == date(2020, 11, 3)
    assert m.election_day(2024) == date(2024, 11, 5)
    els = m.election_days(1994, "2026-09-14")
    assert len(els) == 16 and els[0].year == 1994 and els[-1].year == 2024     # 2026-11-03 not yet


def test_exact_sign_test_matches_the_pass_threshold():
    one, two = m.sign_test(13, 16)
    assert one == pytest.approx(697 / 65536) and two == pytest.approx(2 * 697 / 65536) and two < 0.05
    assert m.sign_test(12, 16)[1] > 0.05                                       # ">= 13 of 16" is the two-sided cut


def test_monthly_expiries_third_friday_and_holiday():
    days = trading_days("2025-03-01", "2025-05-31")
    assert [days[i] for i in m.monthly_expiries(days)] == ["2025-03-21", "2025-04-17", "2025-05-16"]  # Good Friday


def test_cl_last_trade_and_close_time():
    assert m.cl_last_trade(2024, 2) == date(2024, 1, 22)                        # CLG24
    assert m.cl_last_trade(2024, 1) == date(2023, 12, 19)                       # CLF24: the 25th is Christmas
    assert m.close_time_utc("2020-07-01").hour == 20 and m.close_time_utc("2020-01-02").hour == 21


def test_trailing_rv_and_dividend_steps():
    c = 100 * np.exp(np.cumsum(np.r_[0.0, np.tile([0.01, -0.01], 50)]))
    rv = m.trailing_rv(c, 60)
    assert np.isnan(rv[59]) and rv[60] == pytest.approx(0.01 * math.sqrt(252))
    days = trading_days("2020-01-02", "2020-01-10")
    close = np.array([100.0, 101.0, 99.0, 100.0, 100.0, 100.0, 100.0])
    f = np.array([0.98, 0.98, 1.0, 1.0, 1.0, 1.0, 1.0])                         # ex-date 2020-01-06
    d = m._divs(days, close, close * f)
    assert list(d) == ["2020-01-06"] and d["2020-01-06"] == pytest.approx(101.0 * (1 - 0.98))


# ------------------------------------------------------------------------------------------- T-188 box vs VIX --

def _box_changes(n, rho, seed):
    rng = np.random.default_rng(seed)
    dv = rng.standard_t(5, n)
    ds = rho * dv / dv.std() + math.sqrt(1 - rho ** 2) * rng.normal(0, 1, n)
    return ds, dv


def test_corr_test_recovers_correlation():
    ds, dv = _box_changes(1500, 0.5, 1)
    t = m.corr_test(ds, dv, 5, NB)
    assert t["r"] == pytest.approx(np.corrcoef(ds, dv)[0, 1]) and t["ci"][0] < t["r"] < t["ci"][1]
    assert t["ci"][0] > 0.4 and t["n"] == 1500
    z = m.corr_test(*_box_changes(1500, 0.0, 2), 5, NB)
    assert z["ci"][0] < 0 < z["ci"][1]


def test_judge_box_vix_planted_supported_null_not():
    planted = {k: m.corr_test(*_box_changes(800, 0.45, s), 5, NB) for k, s in (("a", 3), ("b", 4))}
    assert m.judge_box_vix(planted, 800, maturity_observed=True)[0] == "supported"
    assert m.judge_box_vix(planted, 800)[0] == "inconclusive"                  # the 60-120 DTE series is missing
    null = {k: m.corr_test(*_box_changes(800, 0.0, s), 5, NB) for k, s in (("a", 5), ("b", 6))}
    assert m.judge_box_vix(null, 800, maturity_observed=True)[0] == "not_supported"


def test_judge_box_vix_disagreeing_variants_and_rule5():
    a = m.corr_test(*_box_changes(800, 0.45, 7), 5, NB)
    b = m.corr_test(*_box_changes(800, 0.10, 8), 5, NB)
    v, why = m.judge_box_vix({"a": a, "b": b}, 800, maturity_observed=True)
    assert v == "inconclusive" and "not implemented: correlation > 0.2" in why    # MARGINAL when variants disagree
    small = {k: m.corr_test(*_box_changes(60, 0.1, s), 5, NB) for k, s in (("a", 9), ("b", 10))}
    assert m.judge_box_vix(small, 60, maturity_observed=True)[0] == "inconclusive"   # below min_n, not decisive


def _box_archive(rho, seed=11):
    rng = np.random.default_rng(seed)
    days = trading_days("2004-01-02", "2010-12-31")
    n = len(days)
    ds, dv = _box_changes(n, rho, seed)
    vix = 20 + np.cumsum(dv) * 0.5
    vix = vix - vix.min() + 10
    spread = 0.5 + np.cumsum(ds) * 0.02                                         # percent
    dtb3 = 2.0 + np.cumsum(rng.normal(0, 0.002, n))
    bill = np.array([m.dtb3_cont(x) * 100 for x in dtb3])
    b6 = bill + spread
    b12 = b6 + 0.1 + rng.normal(0, 0.001, n)
    box = [{"available_at": "2021-11-23T13:58:00+00:00",
            "value": {"day": d, "box_6m": float(x), "box_12m": float(y), "box_18m": float(y + 0.1),
                      "gov_6m": float(x - 0.35), "gov_12m": float(y - 0.35)}} for d, x, y in zip(days, b6, b12)]
    fomc = [{"available_at": "2004-01-27T00:00:00+00:00", "value": {"decision_day": d}} for d in days[20::40]]
    return FakeArchive({"box-rates-bdg": box, "fred-DTB3": _fred(days, dtb3), "cboe-VIX-history": _cboe(days, vix),
                        "fomc-meetings": fomc})


def test_box_harness_planted_criteria_pass_but_maturity_caps():
    stat, n, verdict, reason = m.b6b_misc_box_bill_vix_corr(_box_archive(0.5))
    json.dumps(stat, allow_nan=False)
    assert verdict == "inconclusive" and n == len(trading_days("2004-01-02", "2010-12-31")) - 1
    assert stat["tests"]["box6m-bill"]["ci"][0] > 0.2 and stat["tests"]["box3m-bill"]["r"] > 0.2
    assert "not implemented: box rate at the claim's 60-120 DTE" in reason and stat["no_fomc"]["dropped"] > 0


def test_box_harness_null_not_supported():
    stat, n, verdict, reason = m.b6b_misc_box_bill_vix_corr(_box_archive(0.0, seed=12))
    assert verdict == "not_supported" and "failed: correlation > 0.2" in reason


# ------------------------------------------------------------------------------------- T-518 OPEC USO straddle --

def test_straddle_atm_identities():
    p, prem = m.straddle_atm(np.array([100.0]), np.array([100.0]), np.array([0.3]), 1 / 252, np.array([0.0]))
    assert p[0] == pytest.approx(-prem[0]) and prem[0] == pytest.approx(0.3 * math.sqrt(1 / 252) * 0.7979, rel=0.01)
    up, _ = m.straddle_atm(np.array([100.0]), np.array([105.0]), np.array([0.3]), 1 / 252, np.array([0.0]))
    dn, _ = m.straddle_atm(np.array([100.0]), np.array([95.0]), np.array([0.3]), 1 / 252, np.array([0.0]))
    assert up[0] == pytest.approx(dn[0]) and up[0] == pytest.approx(0.05 - prem[0])


def _event_series(n, n_ev, jump, seed):
    rng = np.random.default_rng(seed)
    pnl = rng.normal(-0.002, 0.01, n)
    ev = np.zeros(n, bool)
    ev[np.linspace(30, n - 30, n_ev).astype(int)] = True
    pnl[ev] += jump
    return pnl, ev


def test_judge_event_diff_planted_supported_null_not():
    pnl, ev = _event_series(3000, 50, 0.02, 1)
    t = m.event_diff_test(pnl, ev, ~ev, 21, NB)
    assert t["diff"] == pytest.approx(pnl[ev].mean() - pnl[~ev].mean()) and t["ci"][0] > 0
    assert m.judge_event_diff(t, 50, True)[0] == "supported"
    assert m.judge_event_diff(t, 50, None)[0] == "inconclusive"                # flags not known in advance
    pnl0, ev0 = _event_series(3000, 50, 0.0, 2)
    assert m.judge_event_diff(m.event_diff_test(pnl0, ev0, ~ev0, 21, NB), 50, True)[0] == "not_supported"
    assert m.judge_event_diff(None, 0, None)[0] == "inconclusive"


def test_opec_events_mapping_and_point_in_time():
    days = trading_days("2021-06-28", "2021-07-16")
    rows = [{"kind": "opec-announcement", "available_at": "2021-07-05T23:59:59+00:00",
             "value": {"day": "2021-07-05", "effective_weekday": "2021-07-05", "known_since": None}},     # holiday
            {"kind": "opec-announcement", "available_at": "2021-06-20T23:59:59+00:00",
             "value": {"day": "2021-07-10", "effective_weekday": "2021-07-12", "known_since": "2021-06-20"}},  # Sat
            {"kind": "oil-supply-surprise", "available_at": "2026-06-09T00:00:00+00:00", "value": {"day": "2021-07-05"}}]
    ev = m.opec_events(rows, days)
    assert [e["session"] for e in ev] == ["2021-07-06", "2021-07-12"]
    assert [e["prev"] for e in ev] == ["2021-07-02", "2021-07-09"]
    assert [e["pit"] for e in ev] == [False, True]


def _opec_archive(jump, verified, seed=31, n_ev=50):
    days = trading_days("2009-06-01", "2016-12-30")
    n = len(days)
    sd = 0.35 / math.sqrt(252)
    rng = np.random.default_rng(seed)
    lr = rng.normal(0, sd, n)
    lr[0] = 0.0
    sess = [i for i in np.linspace(120, n - 20, n_ev).astype(int)]
    for i in sess:
        lr[i] = (1 if rng.random() < 0.5 else -1) * jump * sd if jump else lr[i]
    close = 50 * np.exp(np.cumsum(lr))
    rows = []
    for i in sess:
        d = days[i]
        av = (date.fromisoformat(d) - timedelta(days=30)).isoformat() if verified else d
        rows.append({"kind": "opec-announcement", "available_at": av + "T23:59:59+00:00",
                     "value": {"day": d, "effective_weekday": d, "vintage": "2016M12",
                               "known_since": av if verified else None}})
    return FakeArchive({"opec-announcements": rows, "daily-history-USO": _yahoo(days, close, "USO"),
                        "cboe-OVX-history": _cboe([d for d in days if d >= "2009-09-18"], [35.0] * sum(d >= "2009-09-18" for d in days)),
                        "fred-DTB3": _fred(days[:1], [0.5])})


def test_opec_harness_unverified_dates_not_point_in_time():
    stat, n, verdict, reason = m.b6b_misc_opec_uso_straddle(_opec_archive(3.0, verified=False))
    json.dumps(stat, allow_nan=False)
    assert verdict == "inconclusive" and n == 0 and stat["n_events_pit"] == 0 and stat["n_events_expost"] == 50
    assert "not implementable point in time" in reason and "LOOK-AHEAD" in reason and "MODEL-PRICED" in reason
    assert stat["expost"]["ci"][0] > 0                                          # the planted effect, ex post only


def test_opec_harness_verified_planted_supported_null_not():
    stat, n, verdict, reason = m.b6b_misc_opec_uso_straddle(_opec_archive(3.0, verified=True))
    assert verdict == "supported" and n == 50 and stat["pit_test"]["ci"][0] > 0
    stat, n, verdict, reason = m.b6b_misc_opec_uso_straddle(_opec_archive(0.0, verified=True, seed=33))
    assert verdict == "not_supported" and n == 50


def test_opec_calendar_fixes_documented_deviations():
    """Regression (T-518 review): Kanzig's list is an announcement list, not the meeting calendar. Documented
    non-meetings leave both pools; the session of the unrecorded Sunday 2023-04-02 cut leaves the non-event pool."""
    days = trading_days("2021-06-01", "2025-06-30")
    row = lambda d, eff: {"kind": "opec-announcement", "available_at": d + "T23:59:59+00:00",
                          "value": {"day": d, "effective_weekday": eff, "known_since": None}}
    rows = [row("2021-07-05", "2021-07-05"), row("2024-03-03", "2024-03-04"), row("2025-03-03", "2025-03-03"),
            row("2023-06-04", "2023-06-05"), row("2022-12-04", "2022-12-05")]
    ex = m.opec_calendar_fixes(m.opec_events(rows, days), days)
    assert sorted(ex) == ["2021-07-06", "2023-04-03", "2024-03-04", "2025-03-03"]
    assert "called off" in ex["2021-07-06"] and "2023-04-02" in ex["2023-04-03"]
    # a session that also carries a real meeting stays an event
    ex2 = m.opec_calendar_fixes(m.opec_events(rows + [row("2024-03-04", "2024-03-04")], days), days)
    assert "2024-03-04" not in ex2
    # an unrecorded date already on an event session is not excluded
    ex3 = m.opec_calendar_fixes(m.opec_events(rows + [row("2023-04-03", "2023-04-03")], days), days)
    assert "2023-04-03" not in ex3


def _opec_archive_2020s(jump, seed=35):
    """Verified (point-in-time) events 2020-2025 on regular sessions plus the three documented non-meeting dates."""
    days = trading_days("2020-06-01", "2025-12-31")
    n = len(days)
    sd = 0.35 / math.sqrt(252)
    rng = np.random.default_rng(seed)
    lr = rng.normal(0, sd, n)
    lr[0] = 0.0
    skip = {"2021-07-06", "2023-04-03", "2024-03-04", "2025-03-03"}
    sess = [i for i in np.linspace(40, n - 20, 47).astype(int) if days[i] not in skip][:45]
    for i in sess:
        lr[i] = (1 if rng.random() < 0.5 else -1) * jump * sd if jump else lr[i]
    close = 50 * np.exp(np.cumsum(lr))
    rows = []
    for d, eff in [(days[i], days[i]) for i in sess] + [("2021-07-05", "2021-07-05"), ("2024-03-03", "2024-03-04"),
                                                         ("2025-03-03", "2025-03-03")]:
        av = (date.fromisoformat(d) - timedelta(days=30)).isoformat()
        rows.append({"kind": "opec-announcement", "available_at": av + "T23:59:59+00:00",
                     "value": {"day": d, "effective_weekday": eff, "vintage": "2025M12", "known_since": av}})
    return FakeArchive({"opec-announcements": rows, "daily-history-USO": _yahoo(days, close, "USO"),
                        "cboe-OVX-history": _cboe(days, [35.0] * n), "fred-DTB3": _fred(days[:1], [0.5])}), len(sess)


def test_opec_harness_drops_documented_non_meetings_before_the_test():
    """Regression (T-518 review): the three documented non-meeting sessions are not events (even with a verified
    known_since) and not non-events, 2023-04-03 is not a non-event, and the reason says the list is not the calendar."""
    arc, k = _opec_archive_2020s(3.0)
    stat, n, verdict, reason = m.b6b_misc_opec_uso_straddle(arc)
    json.dumps(stat, allow_nan=False)
    assert k >= 40 and n == k and stat["n_events_pit"] == k and stat["n_events_expost"] == k and verdict == "supported"
    assert sorted(stat["calendar_excluded"]) == ["2021-07-06", "2023-04-03", "2024-03-04", "2025-03-03"]
    assert not set(stat["calendar_excluded"]) & set(stat["event_sessions"])
    for t in (stat["pit_test"], stat["expost"]):
        assert t["n_event"] == k and t["n_other"] == stat["n_sessions"] - k - 4
    assert stat["expost_uncorrected_list"]["n_event"] == k + 3
    assert stat["expost_uncorrected_list"]["n_other"] == stat["n_sessions"] - k - 3
    assert "NOT the OPEC+ ministerial-meeting calendar" in reason and "misses at least the Sunday 2023-04-02" in reason
    assert "session 2023-04-03 out of the non-event pool" in reason and "session 2021-07-06 out of both pools" in reason
    assert "non-event days can include unrecorded OPEC+ announcements" in reason
    _, n0, v0, _ = m.b6b_misc_opec_uso_straddle(_opec_archive_2020s(0.0, seed=36)[0])
    assert v0 == "not_supported" and n0 == k


# ----------------------------------------------------------------------------------- T-522 election-day move --

def test_judge_election_planted_null_and_rule5():
    rng = np.random.default_rng(3)
    planted = np.abs(rng.normal(1.0, 0.3, 16))
    planted[[2]] *= -1
    assert m.judge_election(planted, n_boot=NB)[0] == "supported"               # 15 of 16
    null = rng.normal(0, 1, 16)
    null = np.where(np.arange(16) < 8, np.abs(null), -np.abs(null))
    v, why, det = m.judge_election(null, n_boot=NB)
    assert v == "not_supported" and det["positive"] == 8
    assert m.judge_election(np.abs(rng.normal(1, 0.2, 12)), n_boot=NB)[0] == "inconclusive"   # 12 of 12, below min_n
    assert m.judge_election(-np.abs(rng.normal(1, 0.2, 12)), n_boot=NB)[0] == "not_supported"  # 0 + 4 missing < 13


def _spy_archive(plant, seed=41):
    days = trading_days("1993-01-29", "2026-10-14")
    n = len(days)
    rng = np.random.default_rng(seed)
    lr = rng.normal(0, 0.009, n)
    lr[0] = 0.0
    pos = {d: i for i, d in enumerate(days)}
    if plant:
        for E in m.election_days(1994, "2026-09-14"):
            i = pos[E.isoformat()]
            lr[i] = lr[i + 1] = 0.02 * (1 if rng.random() < 0.5 else -1)
    close = 45 * np.exp(np.cumsum(lr))
    return FakeArchive({"daily-history-SPY": _yahoo(days, close, "SPY"), "cboe-VIX-history": _cboe(days, [16.0] * n),
                        "fred-DTB3": _fred(days[:1], [3.0])})


def test_two_day_window_ratio_and_dividend_forward():
    days = trading_days("2020-11-02", "2020-11-06")
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    pos = {d: i for i, d in enumerate(days)}
    w = m.two_day_window(pos, days, close, {"2020-11-02": 18.0}, date(2020, 11, 3), m.Bills({"2020-10-30": 1.0}),
                         {"2020-11-04": 0.5})
    assert w["before"] == "2020-11-02" and w["after"] == "2020-11-04"
    assert w["ratio"] == pytest.approx(0.02 / (0.18 / math.sqrt(126))) and w["div_in_window"] == 0.5
    assert m.two_day_window(pos, days, close, {"2020-11-02": 18.0}, date(2020, 11, 7)) is None    # not a session


def test_two_day_window_names_a_closure_inside_the_window():
    """Regression (T-522 review): 2018-12-05 was a market closure, so the window around Tuesday 2018-12-04 runs Monday to
    Thursday; it is flagged and named, and a Monday holiday moves the before-close to the Friday."""
    days = trading_days("2018-11-26", "2019-01-31")
    close = np.linspace(100.0, 110.0, len(days))
    pos = {d: i for i, d in enumerate(days)}
    vix = {d: 20.0 for d in days}
    w = m.two_day_window(pos, days, close, vix, date(2018, 12, 4))
    assert (w["before"], w["after"], w["closed"]) == ("2018-12-03", "2018-12-06", ["2018-12-05"]) and not m._regular(w)
    ok = m.two_day_window(pos, days, close, vix, date(2018, 12, 11))
    assert ok["closed"] == [] and m._regular(ok)
    mlk = m.two_day_window(pos, days, close, vix, date(2019, 1, 22))
    assert (mlk["before"], mlk["closed"]) == ("2019-01-18", ["2019-01-21"])
    rows = [{"year": 2018, "diff": 0.1, "event": ok, "before": mlk, "after": w}]
    n_win, odd = m.window_calendar(rows)
    assert n_win == 3 and [o["window"] for o in odd] == ["before", "after"]
    assert "runs Friday 2019-01-18 to Wednesday 2019-01-23 because 2019-01-21 was not a session (a market closure)" \
        in odd[0]["text"]
    assert "runs Monday 2018-12-03 to Thursday 2018-12-06 because 2018-12-05 was not a session" in odd[1]["text"]


def test_election_harness_names_the_2018_after_window_exception():
    """Regression (T-522 review): the reason no longer says every matched window is Monday-to-Wednesday; it names the
    2018 after-window and reports the variant that drops it."""
    stat, n, verdict, reason = m.b6b_misc_election_spy_move(_spy_archive(False, seed=42))
    json.dumps(stat, allow_nan=False)
    assert "the same Monday-to-Wednesday windows" not in reason
    assert "47 of 48 windows (election and matched) run Monday to Wednesday" in reason
    assert ("the 2018 after-window runs Monday 2018-12-03 to Thursday 2018-12-06 because 2018-12-05 was not a session "
            "(a market closure); still 2 sessions, so VIX/sqrt(126) applies") in reason
    assert stat["n_windows"] == 48 and [(o["year"], o["window"]) for o in stat["irregular_windows"]] == [(2018, "after")]
    r18 = next(r for r in stat["elections"] if r["year"] == 2018)
    d18 = r18["event"]["ratio"] - r18["before"]["ratio"]                       # the 2018 matched ratio without it
    others = [r["diff"] for r in stat["elections"] if r["year"] != 2018]
    ro = stat["regular_only"]
    assert ro["n"] == 16 and ro["positive"] == sum(x > 0 for x in others) + (d18 > 0)
    assert ro["mean_diff"] == pytest.approx((sum(others) + d18) / 16)
    assert "dropping the irregular window: " in reason


def test_election_harness_planted_supported_null_not():
    stat, n, verdict, reason = m.b6b_misc_election_spy_move(_spy_archive(True))
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported" and n == 16 and stat["positive"] >= 13 and "MODEL-PRICED" in reason
    stat, n, verdict, reason = m.b6b_misc_election_spy_move(_spy_archive(False, seed=42))
    assert verdict == "not_supported" and n == 16 and stat["positive"] < 13


# -------------------------------------------------------------------------------------- T-275 SLV backspread --

def test_backspread_engine_strikes_and_payoff():
    S, T, r, sig = 20.0, 90 / 365, 0.02, 0.3
    o = m.backspread(np.array([S, S, S]), np.array([15.0, 0.0, 40.0]), np.array([T] * 3), np.array([r] * 3),
                     np.array([sig] * 3))
    k1 = S * math.exp((r + sig ** 2 / 2) * T)
    assert o["k1"][0] * S == pytest.approx(k1, rel=1e-6) and o["k2"][0] > o["k1"][0]
    assert o["pnl"][0] == pytest.approx(o["credit"][0] * math.exp(r * T))       # below K1: keep the net credit
    K1, K2 = o["k1"][2] * S, o["k2"][2] * S
    assert o["pnl"][2] * S == pytest.approx(o["credit"][2] * S * math.exp(r * T) - (40 - K1) + 2 * (40 - K2))
    with_div = m.backspread(np.array([S]), np.array([15.0]), np.array([T]), np.array([r]), np.array([sig]),
                            fwd=np.array([S - 0.5]))
    assert with_div["k1"][0] < o["k1"][0]                                       # priced on the escrowed spot


def test_dte_cycles_on_monthly_calendar():
    days = trading_days("2019-01-02", "2020-12-31")
    rv = np.full(len(days), 0.3)
    rv[:61] = np.nan
    ents, exps = m.dte_cycles(days, rv, m.monthly_expiries(days))
    lives = [(date.fromisoformat(days[b]) - date.fromisoformat(days[a])).days for a, b in zip(ents, exps)]
    assert ents and min(lives) >= 90 and max(lives) <= 93 and days[ents[0]] >= days[61]


def test_judge_backspread_planted_null_and_rule5():
    rng = np.random.default_rng(5)
    good = rng.normal(0.02, 0.03, 200)
    assert m.judge_backspread(good, good - 0.005, captured_iv=True, n_boot=NB)[0] == "supported"
    assert m.judge_backspread(good, good - 0.005, n_boot=NB)[0] == "inconclusive"   # captured IV not available
    null = rng.normal(0.0, 0.03, 200)
    assert m.judge_backspread(null, null, captured_iv=True, n_boot=NB)[0] == "not_supported"
    small = rng.normal(0.0, 0.03, 50)
    assert m.judge_backspread(small, small, captured_iv=True, n_boot=NB)[0] == "inconclusive"   # not decisive
    bad = rng.normal(-0.05, 0.01, 50)
    assert m.judge_backspread(bad, bad, captured_iv=True, n_boot=NB)[0] == "not_supported"     # decisive below min_n


def _slv_archive(jumps, seed=51):
    days = trading_days("2006-04-28", "2026-10-14")
    n = len(days)
    rng = np.random.default_rng(seed)
    lr = rng.normal(0, 0.25 / math.sqrt(252), n)
    if jumps:                                                                   # rare upside squeezes: +30% over 5 days
        for i in np.arange(100, n - 5, 250):                                    # about once a year, mostly unpriced by RV60
            lr[i:i + 5] += 0.06
    lr[0] = 0.0
    close = 14 * np.exp(np.cumsum(lr))
    gd = trading_days("2004-11-18", "2026-10-14")
    gc, _ = _gbm(len(gd), 0.01, seed + 1, s0=44.0)
    return FakeArchive({"daily-history-SLV": _yahoo(days, close, "SLV"), "daily-history-GLD": _yahoo(gd, gc, "GLD"),
                        "fred-DTB3": _fred(days[:1], [2.0])})


def test_slv_harness_planted_capped_null_not_supported():
    stat, n, verdict, reason = m.b6b_misc_slv_call_backspread(_slv_archive(True))
    json.dumps(stat, allow_nan=False)
    assert verdict == "inconclusive" and n >= 230 and stat["judge"]["RV + 5 vol points"]["mean"] > 0
    assert "not implemented: final verdict on captured SLV IV/skew" in reason and "rule 10(a)" in reason.lower()
    stat, n, verdict, reason = m.b6b_misc_slv_call_backspread(_slv_archive(False, seed=52))
    assert verdict == "not_supported" and "MODEL-PRICED" in reason and stat["gld_control"]["n"] > 0


# ---------------------------------------------------------------------------------------------- plumbing --

def _all_archive():
    b = {}
    for fa in (_box_archive(0.3), _opec_archive(2.0, verified=False), _spy_archive(False), _slv_archive(False)):
        for k, v in fa.bundles.items():
            b.setdefault(k, v)
    return FakeArchive(b)


def test_harnesses_registry_json_safe_and_labelled():
    assert set(m.THEORY_MAP) == {"T-188", "T-518", "T-522", "T-275"} and set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(h.startswith("b6b_misc_") and h == h.lower() for h in m.HARNESSES)
    fa = _all_archive()
    for tid, h in m.THEORY_MAP.items():
        stat, n, verdict, reason = m.HARNESSES[h](fa)
        json.dumps(stat, allow_nan=False)
        assert verdict in ("supported", "not_supported", "inconclusive") and isinstance(n, int), tid
        assert " — " in reason and reason.startswith(tid), tid
        if tid != "T-188":
            assert stat["label"] == "MODEL-PRICED" and "MODEL-PRICED" in reason, tid


def test_missing_bundles_inconclusive():
    for name, h in (("box-rates-bdg", "b6b_misc_box_bill_vix_corr"), ("opec-announcements", "b6b_misc_opec_uso_straddle"),
                    ("daily-history-SPY", "b6b_misc_election_spy_move"), ("daily-history-SLV", "b6b_misc_slv_call_backspread")):
        fa = _all_archive()
        del fa.bundles[name]
        m._CACHE.clear()
        stat, n, verdict, reason = m.HARNESSES[h](fa)
        assert verdict == "inconclusive" and n == 0 and name in stat["missing_bundles"] and " — " in reason
