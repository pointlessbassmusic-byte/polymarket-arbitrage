"""Batch-5 macro harnesses on synthetic series: planted effects pass, noise fails. No archive, no network."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch5_macro as bm


def _days(start, end, skip=()):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(r):
    return 100 * np.cumprod(np.concatenate([[1.0], 1 + np.asarray(r)]))      # r[i-1] is the return ending on day i


def _first_on_or_after(days, dom):
    """Per month, the first day in ``days`` with day-of-month >= dom."""
    out, seen = [], set()
    for d in days:
        if int(d[8:]) >= dom and d[:7] not in seen:
            out.append(d); seen.add(d[:7])
    return out


def _first_fridays(days):
    out, seen = [], set()
    for d in days:
        if date.fromisoformat(d).weekday() == 4 and d[:7] not in seen:
            out.append(d); seen.add(d[:7])
    return out


# ------------------------------------------------------------------------------------------------ calendars --

def test_clean_release_days_drops_seasonal_revisions_and_corrections():
    kept, dropped = bm.clean_release_days(["2024-01-11", "2024-02-09", "2024-02-13", "2024-03-12"], "cpi")
    assert kept == ["2024-01-11", "2024-02-13", "2024-03-12"] and dropped == ["2024-02-09"]      # Feb seasonal-factor revision
    kept, dropped = bm.clean_release_days(["2020-04-03", "2020-05-08", "2020-05-11", "2020-06-05"], "es")
    assert kept == ["2020-04-03", "2020-05-08", "2020-06-05"] and dropped == ["2020-05-11"]      # correction after a release
    kept, dropped = bm.clean_release_days(["2000-08-16", "2000-09-15", "2000-09-28", "2000-10-18"], "cpi")
    assert dropped == ["2000-09-28"]                                                               # non-February CPI correction
    kept, dropped = bm.clean_release_days(["1996-01-19", "1996-02-02"], "es")
    assert kept == ["1996-01-19", "1996-02-02"] and dropped == []                                 # 14 days apart: both releases
    kept, dropped = bm.clean_release_days(["2010-02-05", "2010-02-08"], "es")
    assert kept == ["2010-02-05"]                                                                  # the February rule is CPI only


def test_delayed_release_flags():
    fl = bm.delayed_release_flags(["2013-08-02", "2013-09-06", "2013-10-22", "2013-11-08", "2013-12-06", "2014-01-10"])
    assert fl == ["2013-10-22", "2013-11-08"]


def test_to_sessions_maps_holidays_forward_and_drops_future():
    days = _days("2021-03-29", "2021-04-09", skip={"2021-04-02"})          # Good Friday closed
    s, moved = bm.to_sessions(["2021-04-02", "2021-04-07", "2021-05-07"], days)
    assert s == ["2021-04-05", "2021-04-07"] and moved == 1


def test_third_fridays():
    assert bm.third_friday(2024, 3) == "2024-03-15" and bm.third_friday(2024, 6) == "2024-06-21"
    assert bm.third_friday(2008, 3) == "2008-03-21" and bm.third_friday(2021, 1) == "2021-01-15"
    assert len(bm.third_fridays(2020, 2021, bm.WITCHING_MONTHS)) == 8


def test_straddle_premium_and_panel():
    prem = float(bm.straddle_premium(0.16))
    assert prem == pytest.approx(0.16 / np.sqrt(252) * np.sqrt(2 / np.pi), rel=0.01)
    days = ["2024-01-02", "2024-01-03", "2024-01-04"]
    P = bm.straddle_panel(days, [100.0, 103.0, 103.0], {"2024-01-02": 16.0, "2024-01-03": 16.0})
    assert list(P["days"]) == ["2024-01-03", "2024-01-04"]
    assert P["long"][0] == pytest.approx(0.03 - prem, rel=1e-6) and P["long"][1] == pytest.approx(-prem, rel=1e-6)


def test_rank_statistics():
    assert list(bm.rankdata([3, 1, 2, 2])) == [4.0, 1.0, 2.5, 2.5]
    x = np.arange(30.0)
    assert bm.spearman(x, -x) == pytest.approx(-1.0)
    assert bm.spearman_perm_p(x, -x, n_perm=2000) < 0.01
    assert bm.spearman_perm_p(x, x, n_perm=2000) > 0.99
    rng = np.random.default_rng(0); z = rng.normal(size=400)
    a, b = z + 0.1 * rng.normal(size=400), z + 0.1 * rng.normal(size=400)
    assert bm.spearman(a, b) > 0.9 and abs(bm.partial_spearman(a, b, z)) < 0.2


def test_net_of_blocks_charges_one_round_trip_per_run():
    f = np.array([False, True, True, False, True])
    net, entries = bm._net_of_blocks(np.zeros(5), f, 2.0)
    assert list(entries) == [False, True, False, False, True] and net[1] == pytest.approx(-2e-4) and net[2] == 0.0


# -------------------------------------------------------------------------------- T-343 announcement premium --

def _release_world(seed, plant_bps):
    rng = np.random.default_rng(seed)
    days = _days("1993-01-04", "2026-09-30")
    r = rng.normal(0.0003, 0.01, len(days) - 1)
    cpi = _first_on_or_after(days, 13); es = _first_fridays(days); fomc = [days[i] for i in range(25, len(days), 32)]
    pos = {d: i for i, d in enumerate(days)}
    for e in set(cpi) | set(es) | set(fomc):
        if pos[e] > 0:
            r[pos[e] - 1] += plant_bps / 1e4
    return days, _closes(r), cpi, es, fomc


def test_announcement_premium_planted_passes():
    days, c, cpi, es, fomc = _release_world(1, 40.0)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, n_boot=200)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["net"]["diff"] * 1e4 == pytest.approx(38.0, abs=8.0)
    assert rep["reason"].endswith("all criteria pass")


def test_announcement_premium_null_fails():
    days, c, cpi, es, fomc = _release_world(2, 0.0)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, n_boot=200)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_announcement_premium_short_sample_is_inconclusive():
    days, c, cpi, es, fomc = _release_world(3, 40.0)
    rep = bm.announcement_day_premium(days, c, cpi, es, fomc, start="2020-01-01", n_boot=100)
    assert rep["verdict"] == "inconclusive" and "min_n" in rep["reason"]


# ------------------------------------------------------------------------------------- T-208 IM/HM filter --

def test_event_move_table_hm_is_median_of_previous_events():
    days = _days("2020-01-01", "2020-12-31")
    moves = np.linspace(0.001, 0.010, 10)
    r = np.zeros(len(days) - 1); ev = [days[10 * (k + 1)] for k in range(10)]
    for k, e in enumerate(ev):
        r[days.index(e) - 1] = moves[k]
    vix = {d: 20.0 for d in days}
    T = bm.event_move_table(days, _closes(r), vix, ev, n_hm=8)
    assert len(T["days"]) == 2 and T["days"][0] == ev[8]
    assert T["hm"][0] == pytest.approx(np.median(moves[:8]), rel=1e-6)
    assert T["ratio"][0] == pytest.approx(0.845 * float(bm.straddle_premium(0.2)) / np.median(moves[:8]), rel=1e-6)


def _imhm_world(seed, planted):
    rng = np.random.default_rng(seed)
    days = _days("1994-01-03", "2026-06-30")
    vixv = rng.uniform(10, 40, len(days)); vix = dict(zip(days, vixv))
    r = rng.normal(0, 0.01, len(days) - 1)
    ev_idx = list(range(20, len(days), 32))
    for i in ev_idx:
        sd = vixv[i - 1] / 100 / np.sqrt(252)
        # planted: event moves ignore VIX, so a high VIX (high IM/HM) overprices the straddle; null: VIX is the true vol
        r[i - 1] = rng.choice([-1, 1]) * 0.01 * (0.5 + rng.random()) if planted else rng.normal(0, sd)
    return days, _closes(r), vix, [days[i] for i in ev_idx]


def test_im_hm_filter_planted_passes():
    days, c, vix, ev = _imhm_world(0, True)
    rep = bm.im_hm_filter(days, c, vix, ev, n_perm=2000, n_boot=1000, n_placebo=10)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["oos_spearman_rho"] < -0.5 and rep["oos_q1_minus_q5_ci"][0] > 0
    assert rep["label"] == "MODEL-PRICED" and rep["reason"].startswith("MODEL-PRICED")


def test_im_hm_filter_null_fails():
    days, c, vix, ev = _imhm_world(0, False)
    rep = bm.im_hm_filter(days, c, vix, ev, n_perm=2000, n_boot=1000, n_placebo=10)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_im_hm_filter_uses_only_in_sample_cutoffs():
    days, c, vix, ev = _imhm_world(4, True)
    rep = bm.im_hm_filter(days, c, vix, ev, n_perm=500, n_boot=200, n_placebo=0)
    T = bm.event_move_table(days, c, vix, ev)
    assert list(rep["in_sample_cutoffs"]) == pytest.approx(list(np.quantile(T["ratio"][T["days"] <= "2009-12-31"], [0.2, 0.4, 0.6, 0.8])))


# --------------------------------------------------------------------------------- T-224 GLD event straddle --

def _gld_world(seed, event_mult):
    rng = np.random.default_rng(seed)
    days = _days("2009-09-01", "2026-09-30")
    gvzv = rng.uniform(12, 30, len(days)); gvz = dict(zip(days, gvzv))
    sd = gvzv[:-1] / 100 / np.sqrt(252)
    r = rng.normal(0, 1, len(days) - 1) * sd                       # GVZ is the true vol on ordinary days
    fomc = [days[i] for i in range(30, len(days), 32)]; cpi = _first_on_or_after(days, 13)
    pos = {d: i for i, d in enumerate(days)}
    for e in set(fomc) | set(cpi):
        r[pos[e] - 1] *= event_mult
    return days, _closes(r), gvz, fomc, cpi


def test_gld_event_straddle_planted_passes():
    days, c, gvz, fomc, cpi = _gld_world(0, 2.5)
    rep = bm.gld_event_straddle(days, c, gvz, fomc, cpi, n_boot=400)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["full"]["diff"] < 0 and rep["label"] == "MODEL-PRICED"


def test_gld_event_straddle_null_fails():
    days, c, gvz, fomc, cpi = _gld_world(1, 1.0)
    rep = bm.gld_event_straddle(days, c, gvz, fomc, cpi, n_boot=400)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_gld_event_straddle_excludes_unscheduled_from_both_groups():
    days, c, gvz, fomc, cpi = _gld_world(2, 1.0)
    extra = [d for d in days[40:400:37] if d not in set(fomc) | set(cpi)]
    rep = bm.gld_event_straddle(days, c, gvz, fomc, cpi, exclude_days=extra, n_boot=100)
    base = bm.gld_event_straddle(days, c, gvz, fomc, cpi, n_boot=100)
    assert rep["full"]["n_event"] == base["full"]["n_event"] and rep["full"]["n_other"] == base["full"]["n_other"] - len(extra)


# ------------------------------------------------------------------------------- T-219 triple witching --

def _witching_world(seed, plant):
    rng = np.random.default_rng(seed)
    days = _days("1993-01-04", "2026-09-30")
    vix = {d: 20.0 for d in days}
    r = rng.normal(0, 0.2 / np.sqrt(252), len(days) - 1)
    pos = {d: i for i, d in enumerate(days)}
    for w in bm.third_fridays(1993, 2026, bm.WITCHING_MONTHS):
        if w in pos:
            r[pos[w] - 1] = rng.choice([-1, 1]) * plant * 0.2 / np.sqrt(252) if plant else r[pos[w] - 1]
    return days, _closes(r), vix


def test_witching_straddle_planted_passes():
    days, c, vix = _witching_world(0, 2.5)
    rep = bm.witching_straddle(days, c, vix, n_boot=500, n_perm=2000)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] >= 130 and rep["n_witching_skipped"] == 0


def test_witching_straddle_null_fails():
    days, c, vix = _witching_world(1, 0.0)
    rep = bm.witching_straddle(days, c, vix, n_boot=500, n_perm=2000)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_witching_skips_friday_without_thursday_session():
    days = _days("2025-06-01", "2025-06-30", skip={"2025-06-19"})          # Juneteenth Thursday closed
    vix = {d: 20.0 for d in days}
    P = bm.friday_panel(days, _closes(np.zeros(len(days) - 1)), vix)
    assert "2025-06-20" not in set(P["days"]) and "2025-06-13" in set(P["days"])


# ---------------------------------------------------------------------------------------------- harnesses --

class _EmptyArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


def test_harnesses_report_missing_bundles_as_inconclusive():
    for name, fn in bm.HARNESSES.items():
        stat, n, verdict, reason = fn(_EmptyArchive())
        assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert "missing data bundles" in reason


def test_theory_map_matches_harnesses():
    assert set(bm.THEORY_MAP) == {"T-343", "T-208", "T-224", "T-219"}
    assert set(bm.THEORY_MAP.values()) == set(bm.HARNESSES)
    assert all(k.startswith("macro_") for k in bm.HARNESSES)
