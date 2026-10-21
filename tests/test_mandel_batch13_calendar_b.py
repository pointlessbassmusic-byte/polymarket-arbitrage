"""Batch 13, group calendar_b (T-586, T-584, T-585, T-590): point-in-time signal construction, the statistics, and
missing data."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch13_calendar_b as M


def _sessions(start: str, end: str) -> list:
    """NYSE rule-calendar sessions in [start, end] (what the archive's bars match)."""
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if CAL.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _walk(n, seed, vol=0.01, drift=0.0003):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


def _shock_after(x, i, seed=99, vol=0.05):
    """A copy of price path x with a violent random path multiplied in strictly after index i."""
    rng = np.random.default_rng(seed)
    y = np.asarray(x, float).copy()
    y[i + 1:] *= np.exp(np.cumsum(rng.normal(0, vol, y.size - i - 1)))
    return y


# ============================================================================ T-586 threshold rebalancing ==

def test_band_zero_resets_every_close_so_its_deviation_is_the_one_day_drift():
    rs = np.array([0.0, 0.02, -0.01, 0.03])
    rb = np.array([0.0, -0.005, 0.004, 0.0])
    dev = M.band_deviations(rs, rb, [0.0])[:, 0]
    for t in range(1, 4):
        w = 0.6 * (1 + rs[t]) / (0.6 * (1 + rs[t]) + 0.4 * (1 + rb[t]))
        assert dev[t] == pytest.approx(w - 0.6)
    assert dev[0] == 0.0


def test_wide_band_never_resets_so_its_deviation_is_buy_and_hold_drift():
    rng = np.random.default_rng(1)
    rs, rb = rng.normal(0, 0.002, 200), rng.normal(0, 0.001, 200)
    rs[0] = rb[0] = 0.0
    dev = M.band_deviations(rs, rb, [0.5])[:, 0]
    gs, gb = np.cumprod(1 + rs), np.cumprod(1 + rb)
    w = 0.6 * gs / (0.6 * gs + 0.4 * gb)
    assert np.allclose(dev, w - 0.6)


def test_band_resets_at_the_close_it_breaches_and_the_deviation_recorded_is_pre_reset():
    rs = np.array([0.0, 0.05, 0.0, 0.0])                   # a 5% equity jump breaches the 1% band on day 1
    rb = np.zeros(4)
    dev = M.band_deviations(rs, rb, [0.01])[:, 0]
    assert dev[1] > 0.01                                    # the deviation the reset trades away
    assert dev[2] == pytest.approx(0.0) and dev[3] == pytest.approx(0.0)    # reset to 60/40 at close 1


def _rebal_inputs(n=1400, start="2015-01-02"):
    days = _sessions(start, "2030-12-31")[:n]
    spy, ief, tlt = _walk(n, 2), _walk(n, 3, 0.004, 0.0001), _walk(n, 4, 0.009, 0.0001)
    syn = _walk(n, 5, 0.004, 0.0001)
    return days, spy, ief, tlt, syn


KEYS_AT_DECISION = ("sig_a", "sig_b", "plc_a", "plc_b", "k_a", "k_b", "q80_a", "q80_b", "sig_syn", "tom", "d345")


def test_rebal_signal_at_the_entry_close_ignores_every_later_price():
    days, spy, ief, tlt, syn = _rebal_inputs()
    P = M.rebal_panel(days, spy, ief, tlt, syn)
    j = 900
    t = j + 2                                               # entry index of row j (position close t -> t+1)
    assert P["day"][j] == days[t] and P["ret_day"][j] == days[t + 1]
    P2 = M.rebal_panel(days, _shock_after(spy, t), _shock_after(ief, t, 7), _shock_after(tlt, t, 8), _shock_after(syn, t, 9))
    assert np.isfinite(P["k_b"][j]) and np.isfinite(P["q80_b"][j])
    for k in KEYS_AT_DECISION:
        assert _same(P[k][:j + 1], P2[k][:j + 1]), k
    assert not np.isclose(P["y_a"][j], P2["y_a"][j]) and not np.isclose(P["y_b"][j], P2["y_b"][j])  # the outcome moves


def test_reading_b_signal_ignores_the_entry_close_itself_and_reading_a_does_not():
    days, spy, ief, tlt, syn = _rebal_inputs()
    j = 900
    t = j + 2
    spy2 = spy.copy()
    spy2[t:] *= 1.04                                        # a 4% move AT the entry close t (and carried after)
    P, P2 = M.rebal_panel(days, spy, ief, tlt, syn), M.rebal_panel(days, spy2, ief, tlt, syn)
    for k in ("sig_b", "k_b", "q80_b", "plc_b"):
        assert P[k][j] == P2[k][j] or (np.isnan(P[k][j]) and np.isnan(P2[k][j])), k
    assert P["sig_a"][j] != P2["sig_a"][j]
    syn2 = syn.copy()
    syn2[t - 1:] *= 1.03                                    # the synthetic leg is lagged one more day (FRED posts next day)
    assert M.rebal_panel(days, spy, ief, tlt, syn2)["sig_syn"][j] == P["sig_syn"][j]


def test_trailing_beta_and_quantile_use_only_the_past():
    rng = np.random.default_rng(6)
    rs, rb = rng.normal(0, 0.01, 600), rng.normal(0, 0.004, 600)
    k = M.trailing_beta(rs, rb, 252)
    t = 400
    a = slice(t - 251, t + 1)
    c = np.cov(rs[a], rb[a], bias=True)
    assert k[t] == pytest.approx(c[0, 1] / c[1, 1])
    rs2 = rs.copy(); rs2[t + 1:] += 1.0
    assert _same(M.trailing_beta(rs2, rb, 252)[:t + 1], k[:t + 1])
    x = rng.normal(size=600)
    q = M.trailing_quantile(x, 0.8, 252)
    assert q[t] == pytest.approx(np.quantile(x[t - 252:t], 0.8))
    x2 = x.copy(); x2[t:] = 100.0                          # the value AT t does not enter its own threshold
    assert M.trailing_quantile(x2, 0.8, 252)[t] == q[t]


def test_trigger_pays_two_bps_per_leg_at_least_and_trades_against_the_signal():
    sig = np.array([0.02, -0.02, 0.001])
    y = np.array([0.01, 0.01, 0.01])
    q80 = np.array([0.01, 0.01, 0.01])
    k = np.array([0.5, 2.0, 0.5])
    p = M.trigger_pnl(sig, y, q80, k)
    assert p[0] == pytest.approx(-0.01 - 2e-4 * 2)          # overweight equities -> short the spread; 2 legs x 2 bps
    assert p[1] == pytest.approx(0.01 - 2e-4 * 3)           # IEF leg 2x notional pays 2 x 2 bps
    assert np.isnan(p[2])                                   # below the trailing 80th percentile: no trade


def test_t345_dummy_marks_last_two_sessions_after_spy_beats_tlt_by_two_points():
    days = _sessions("2019-01-02", "2019-04-30")
    n = len(days)
    spy, tlt = np.full(n, 100.0), np.full(n, 100.0)
    feb = [i for i, d in enumerate(days) if d[:7] == "2019-02"]
    spy[feb[0]:] = 104.0                                    # SPY +4 pp month-to-date in February by its first close
    out = M.t345_return_days(days, spy, tlt)
    assert out == {days[feb[-2]], days[feb[-1]]}


def test_rebal_test_finds_a_planted_negative_slope():
    rng = np.random.default_rng(11)
    n = 1200
    days = np.array(_sessions("2020-01-02", "2030-12-31")[:n])
    sig = rng.normal(size=n)
    y = -0.002 * sig + rng.normal(0, 0.005, n)
    P = {"day": days, "ret_day": days, "d345": np.zeros(n), "tom": np.zeros((n, 7)), "tom_any": np.zeros(n)}
    for lab in ("a", "b"):
        P.update({f"sig_{lab}": sig, f"plc_{lab}": rng.normal(size=n), f"k_{lab}": np.full(n, 0.5), f"y_{lab}": y,
                  f"yv_{lab}": y, f"q80_{lab}": np.full(n, 1.0)})
    P["d345"][::20] = 1.0
    P["tom"][::7, 0] = 1.0
    P["tom_any"] = P["tom"].max(axis=1)
    rep = M.rebal_test(P, start="2020-01-01", n_boot=300, n_seeds=1)
    assert rep["readings"]["b"]["slope"]["coef"] < 0
    assert rep["criteria"][0][1] is True and rep["criteria"][1][1] is True


# ================================================================================== T-584 post-FOMC drift ==

def _fomc_inputs():
    sdays = _sessions("2004-01-02", "2012-12-31")
    n = len(sdays)
    rng = np.random.default_rng(12)
    cal = [d for d in _sessions("2004-01-01", "2012-12-31")]
    dtb3 = {d: float(v) for d, v in zip(cal, 2 + np.cumsum(rng.normal(0, 0.02, len(cal))))}
    dgs10 = {d: float(v) for d, v in zip(cal, 4 + np.cumsum(rng.normal(0, 0.05, len(cal))))}
    dgs2 = {d: float(v) for d, v in zip(cal, 3 + np.cumsum(rng.normal(0, 0.04, len(cal))))}
    dff = {d: 2.0 for d in cal}
    ief = 100 * np.exp(np.cumsum(-7.5 * np.diff(np.r_[4.0, [dgs10[d] for d in sdays]]) / 100))
    meetings = [sdays[i] for i in range(300, n - 80, 40)]
    return sdays, ief, dtb3, dgs10, dgs2, dff, meetings


def _bump(series: dict, after: str, by: float) -> dict:
    return {d: (v + by if d > after else v) for d, v in series.items()}


def test_fomc_surprise_duration_and_entry_ignore_everything_after_the_entry_close():
    sdays, ief, dtb3, dgs10, dgs2, dff, meetings = _fomc_inputs()
    ev = {e["day"]: e for e in M.fomc_events(meetings, sdays, ief, dtb3, dgs10, dgs2, dff)}
    t = meetings[5]
    i = sdays.index(t)
    entry = sdays[i + 2]
    assert ev[t]["entry"] == entry
    ief2 = _shock_after(ief, i + 2)
    ev2 = {e["day"]: e for e in M.fomc_events(meetings, sdays, ief2, _bump(dtb3, entry, 1.0), _bump(dgs10, entry, 1.0),
                                              _bump(dgs2, entry, 1.0), _bump(dff, entry, -2.0))}
    for k in ("s", "s2", "dff_prev", "dur", "y_entry"):
        assert ev2[t][k] == ev[t][k], k
    assert ev2[t]["y20"] != ev[t]["y20"] and ev2[t]["r20"] != ev[t]["r20"]       # the outcome moves


def test_fomc_surprise_uses_the_statement_day_and_the_previous_print_only():
    sdays, ief, dtb3, dgs10, dgs2, dff, meetings = _fomc_inputs()
    t = meetings[3]
    e = M.fomc_events([t], sdays, ief, dtb3, dgs10, dgs2, dff)[0]
    prev = max(d for d in dtb3 if d < t)
    assert e["s"] == pytest.approx(dtb3[t] - dtb3[prev])
    after = _bump(dtb3, t, 5.0)                             # every print after the statement day
    assert M.fomc_events([t], sdays, ief, after, dgs10, dgs2, dff)[0]["s"] == e["s"]
    assert e["dur"] == pytest.approx(7.5, rel=0.05)         # the synthetic IEF has duration 7.5


def test_fomc_sizing_uses_only_earlier_meetings():
    sdays, ief, dtb3, dgs10, dgs2, dff, meetings = _fomc_inputs()
    ev = M.fomc_events(meetings, sdays, ief, dtb3, dgs10, dgs2, dff)
    M.size_positions(ev)
    j = 12
    assert "pos" in ev[j]
    ev2 = M.fomc_events(meetings, sdays, ief, dtb3, dgs10, dgs2, dff)
    for e in ev2[j + 1:]:
        e["s"] *= 50.0                                      # later surprises do not set today's scale
    M.size_positions(ev2)
    assert ev2[j]["pos"] == ev[j]["pos"] and ev2[j]["notional"] == ev[j]["notional"]
    sd = np.std([e["s"] for e in ev[:j]], ddof=1)
    assert ev[j]["pos"] == pytest.approx(np.clip(-ev[j]["s"] / sd, -2, 2))


def test_meeting_bootstrap_and_permutation_see_a_planted_slope():
    rng = np.random.default_rng(13)
    s = rng.normal(0, 5, 80)
    y = 0.8 * s + rng.normal(0, 3, 80)
    pg, pl = M.perm_slope(s, y, 2000, 0)
    assert pg < 0.01 and pl > 0.99
    bg, _ = M.meeting_boot(s, y, 500, 0)
    assert bg < 0.05
    pg0, _ = M.perm_slope(s, rng.normal(0, 3, 80), 2000, 1)
    assert pg0 > 0.01


def test_fomc_drift_below_sixty_meetings_outside_zlb_is_inconclusive():
    rng = np.random.default_rng(14)
    ev = []
    for k in range(40):
        s = float(rng.normal(0, 0.05))
        ev.append({"day": f"20{10 + k // 8:02d}-{1 + k % 8:02d}-15", "s": s, "dff_prev": 1.0, "y20": 2 * s + float(rng.normal(0, 0.02)),
                   "r20": -0.01 * s, "bill20": 0.0, "notional": -s * 10})
    rep = M.fomc_drift_test(ev, start="2010-01-01", end="2014-12-31", split="2012-06-01", n_draws=2000)
    assert rep["n_outside_zlb"] == 40 and rep["verdict"] == "inconclusive"


# ================================================================================== T-585 dash for cash ==

def test_era_boundaries_are_the_sec_compliance_dates():
    assert M.era_of("2017-09-01") == "T+3" and M.era_of("2017-09-05") == "T+2"
    assert M.era_of("2024-05-24") == "T+2" and M.era_of("2024-05-28") == "T+1"
    assert M.era_of("1995-06-30") is None and M.era_of("1995-07-03") == "T+3"


def test_month_end_panel_returns_are_the_last_four_sessions_close_to_close():
    days = _sessions("2016-01-04", "2019-12-31")
    c = _walk(len(days), 15)
    rows = {r["month"]: r for r in M.month_end_panel(days, c)}
    r = rows["2017-09"]
    sep = [i for i, d in enumerate(days) if d[:7] == "2017-09"]
    assert r["d0"] == days[sep[-1]] == "2017-09-29"
    for j in range(4):
        i = sep[-1 - j]
        assert r[f"d{j}"] == days[i] and r[f"r{j}"] == pytest.approx(c[i] / c[i - 1] - 1)
    assert r["era"] == "T+2" and rows["2017-08"]["era"] == "T+3"


def test_month_end_panel_rows_ignore_prices_after_the_month():
    days = _sessions("2016-01-04", "2019-12-31")
    c = _walk(len(days), 16)
    i = max(k for k, d in enumerate(days) if d[:7] == "2018-06")
    a = {r["month"]: r for r in M.month_end_panel(days, c)}
    b = {r["month"]: r for r in M.month_end_panel(days, _shock_after(c, i))}
    for m, row in a.items():
        if m <= "2018-06":
            assert row == b[m], m


def test_month_positions_of_an_unfinished_month_count_the_scheduled_sessions():
    full = _sessions("2026-08-03", "2026-10-30")
    cut = [d for d in full if d <= "2026-10-14"]
    fs1, fe1, c1 = M.month_positions(full)
    fs2, fe2, c2 = M.month_positions(cut)
    k = len(cut)
    assert np.array_equal(fs1[:k], fs2) and np.array_equal(fe1[:k], fe2)
    assert c1[k - 1] and not c2[k - 1]
    assert fe2[k - 1] == len([d for d in full if d[:7] == "2026-10" and d > "2026-10-14"]) + 1
    assert not M.month_end_panel(cut, np.ones(k)) or all(r["month"] != "2026-10" for r in M.month_end_panel(cut, np.ones(k)))


def test_unscheduled_closure_months_are_dropped():
    days = _sessions("2012-08-01", "2013-01-31")             # Hurricane Sandy: 2012-10-29/30 closed
    rows = {r["month"]: r for r in M.month_end_panel(days, _walk(len(days), 17))}
    assert rows["2012-10"]["sched_ok"] is False and rows["2012-11"]["sched_ok"] is True


def _panel_rows(n, rho, era, seed):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=n)
    b = rho * a + np.sqrt(1 - rho * rho) * rng.normal(size=n)
    return [{"month": f"m{seed}-{k}", "sched_ok": True, "era": era, "r3": float(a[k]) * 0.01, "r2": float(b[k]) * 0.01}
            for k in range(n)]


def test_rho_test_detects_a_lower_correlation_in_the_new_regime():
    panel = _panel_rows(80, -0.4, "T+2", 1) + _panel_rows(260, 0.2, "T+3", 2)
    r = M.rho_test(panel, n_draws=2000, escalate=False)
    assert r["diff"] < -0.3 and r["boot_p_less"] < 0.01 and r["perm_p_less"] < 0.01
    flat = _panel_rows(80, 0.1, "T+2", 3) + _panel_rows(260, 0.1, "T+3", 4)
    r0 = M.rho_test(flat, n_draws=2000, escalate=False)
    assert r0["boot_p_less"] > 0.01 and r0["perm_p_less"] > 0.01


# ================================================================================== T-590 payday 16th ==

def test_payday_flag_is_the_first_session_on_or_after_the_16th():
    days = _sessions("2021-01-04", "2021-12-31")
    flagged = [d for d, f in zip(days, M.payday_flags(days)) if f]
    assert len(flagged) == 12
    assert "2021-05-17" in flagged                          # the 16th is a Sunday
    assert "2021-01-19" in flagged                          # Sat 16th, Mon 18th is MLK day
    assert "2021-03-16" in flagged


def test_payday_sample_flags_are_calendar_only_and_returns_close_to_close():
    days = _sessions("2010-11-01", "2012-12-31")
    c = _walk(len(days), 18)
    ds, x, f, excl = M.payday_sample(days, c, start="2011-01-01", end="2012-12-31")
    i16 = days.index("2011-03-16")
    k = list(ds).index("2011-03-16")
    assert f[k] and x[k] == pytest.approx(c[i16] / c[i16 - 1] - 1)
    ds2, _, f2, _ = M.payday_sample(days, _shock_after(c, 10), start="2011-01-01", end="2012-12-31")
    assert np.array_equal(f, f2) and list(ds) == list(ds2)
    fs, fe, _ = M.month_positions(days)
    tom = {d for d, a, b in zip(days, fs, fe) if a <= 3 or b <= 4}
    assert not (set(ds) & tom) and excl == 0
    cut = [d for d in days if d <= "2011-03-16"]           # the classification of a day needs no later bar
    ds3, _, f3, _ = M.payday_sample(cut, c[:len(cut)], start="2011-01-01", end="2011-02-28")
    m = [d <= "2011-02-28" for d in ds]
    assert list(ds3) == list(np.asarray(ds)[m]) and np.array_equal(f3, np.asarray(f)[m])


def test_third_friday_moves_to_thursday_on_good_friday():
    assert M.third_friday_session(2019, 4) == "2019-04-18"
    assert M.third_friday_session(2021, 10) == "2021-10-15"


def test_payday_stats_charge_the_cost_and_test_the_bar():
    rng = np.random.default_rng(19)
    days = np.array(_sessions("2011-01-03", "2026-09-30"))
    x = rng.normal(0.0003, 0.01, days.size)
    f = M.payday_flags(list(days))
    x[f] += 0.0010
    s = M.payday_stats(days, x, f, n_boot=300, n_seeds=1)
    assert s["net"] == pytest.approx(s["gross"] - 2e-4)
    assert s["gross"] == pytest.approx(x[f].mean() - x[~f].mean())
    assert s["n16"] == int(f.sum())


# ===================================================================================== missing data ==

class _NoArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


@pytest.mark.parametrize("name", list(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    _, n, verdict, reason = M.HARNESSES[name](_NoArchive())
    assert verdict == "inconclusive" and n == 0 and "missing" in reason


def test_theory_map_names_every_harness():
    assert set(M.THEORY_MAP) == {"T-586", "T-584", "T-585", "T-590"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for name, fn in M.HARNESSES.items():
        assert name.startswith("b13_calendar_b_") and fn.__doc__.split(":")[0] in M.THEORY_MAP
