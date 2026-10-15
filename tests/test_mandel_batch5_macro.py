"""Batch-5 macro harnesses on synthetic series: planted effects pass, noise fails. No archive, no network."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

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


def test_announcement_sharpe_annualised_by_each_day_types_days_per_year():
    # regression: both day types were annualised by sqrt(252), overstating the ~31/yr release days by sqrt(252/31).
    # Same per-day distribution on every day: each type's Sharpe must scale with sqrt(its own days per year).
    rng = np.random.default_rng(5)
    days = _days("1993-01-04", "2026-09-30")
    r = rng.normal(0.003, 0.01, len(days) - 1)
    cpi = _first_on_or_after(days, 13); es = _first_fridays(days); fomc = [days[i] for i in range(25, len(days), 32)]
    rep = bm.announcement_day_premium(days, _closes(r), cpi, es, fomc, n_boot=50)
    ds, rr = bm._returns(days, _closes(r), "1993-01-01", "2026-12-31")
    flag = np.zeros(len(ds), dtype=bool)
    for evs in (cpi, es, fomc):
        flag |= np.isin(ds, bm.to_sessions(evs, days)[0])
    net, _ = bm._net_of_blocks(rr, flag, 2.0)
    yrs = len(rr) / 252
    sh, py = rep["sharpe_by_day_type"], rep["days_per_year_by_type"]
    assert py["release"] == pytest.approx(flag.sum() / yrs) and py["release"] + py["other"] == pytest.approx(252)
    for lab, m in (("release", flag), ("other", ~flag)):
        x = net[m]
        assert sh[lab] == pytest.approx(x.mean() / x.std(ddof=1) * np.sqrt(m.sum() / yrs), rel=1e-9)
    assert sh["release"] == pytest.approx(rep["sharpe_release_only_strategy"], rel=0.1)       # flat-otherwise strategy
    assert sh["release"] / sh["other"] < 0.6          # ~sqrt(31/221) = 0.37; sqrt(252) for both gave ~0.9
    assert "annualised by sqrt of its days/yr" in rep["reason"]


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

def _witching_returns(seed, plant, start="1993-01-04"):
    rng = np.random.default_rng(seed)
    days = _days(start, "2026-09-30")
    vix = {d: 20.0 for d in days}
    r = rng.normal(0, 0.2 / np.sqrt(252), len(days) - 1)
    pos = {d: i for i, d in enumerate(days)}
    for w in bm.third_fridays(1993, 2026, bm.WITCHING_MONTHS):
        if w in pos:
            r[pos[w] - 1] = rng.choice([-1, 1]) * plant * 0.2 / np.sqrt(252) if plant else r[pos[w] - 1]
    return days, r, vix


def _witching_world(seed, plant):
    days, r, vix = _witching_returns(seed, plant)
    return days, _closes(r), vix


def _ex_dividend_on_witching(days, r, y):
    """Raw closes with a dividend of y x the Thursday close going ex on every witching Friday (total return r unchanged),
    Yahoo-style adjusted closes (every close before an ex-date times 1 - y) and the {ex-day: y} map."""
    pos = {d: i for i, d in enumerate(days)}
    ex = [w for w in bm.third_fridays(1993, 2026, bm.WITCHING_MONTHS) if pos.get(w, 0) > 0]
    r_raw = np.array(r, dtype=float)
    fac = np.ones(len(days))
    for w in ex:
        r_raw[pos[w] - 1] -= y                      # S_Fri = S_Thu (1 + r) - D, D = y S_Thu
        fac[:pos[w]] *= 1 - y
    raw = _closes(r_raw)
    return raw, raw * fac, {w: y for w in ex}


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


def test_ex_dividend_yields_reads_adjclose_steps():
    days = _days("2024-03-11", "2024-03-29")
    raw = 100 + 0.5 * np.arange(len(days))
    ys = {"2024-03-15": 0.004, "2024-03-22": 0.003}
    fac = np.ones(len(days))
    for d, y in ys.items():
        fac[:days.index(d)] *= 1 - y
    out = bm.ex_dividend_yields(days, raw, np.round(raw * fac, 4))        # rounding steps stay below tol
    assert set(out) == set(ys) and all(out[d] == pytest.approx(y, abs=2e-6) for d, y in ys.items())
    assert bm.ex_dividend_yields(days, raw, raw) == {}


def test_straddle_panel_prices_known_dividend_on_the_forward():
    days = ["2024-03-14", "2024-03-15"]
    P = bm.straddle_panel(days, [100.0, 99.6], {"2024-03-14": 16.0}, div_yield={"2024-03-15": 0.004})
    fwd = float(bm.bs.price(0.996, 1.0, 1 / 252, 0.0, 0.16, "call") + bm.bs.price(0.996, 1.0, 1 / 252, 0.0, 0.16, "put"))
    assert P["premium"][0] == pytest.approx(fwd) and P["premium"][0] > float(bm.straddle_premium(0.16))
    assert P["move"][0] == pytest.approx(0.004) and P["move_fwd"][0] == pytest.approx(0.0, abs=1e-12)


def test_witching_ex_dividend_drop_is_not_a_witching_effect():
    # regression: SPY goes ex-dividend on the witching Friday; with q = 0 the known drop inflated |S_Fri - S_Thu| on
    # witching Fridays only. No witching volatility effect is planted; the dividend is exaggerated (150 bps) so the
    # artefact is unmistakable.
    days, r, vix = _witching_returns(1, 0.0)
    raw, _, divs = _ex_dividend_on_witching(days, r, 0.015)
    ignored = bm.witching_straddle(days, raw, vix, n_boot=300, n_perm=2000)
    assert ignored["verdict"] == "supported"                                       # the artefact reads as an effect
    rep = bm.witching_straddle(days, raw, vix, div_yield=divs, n_boot=300, n_perm=2000)
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["n_ex_dividend_witching"] == rep["n"] and rep["n_ex_dividend_other"] == 0
    ra = rep["abs_r_over_vix_daily"]
    assert abs(ra["witching"] - ra["other"]) < 0.1                                # dividend-neutral move
    sens = rep["dividend_treatment_sensitivity_diff_bps"]
    assert sens["ignored (q = 0, raw move)"] == pytest.approx(ignored["full"]["diff"] * 1e4)
    assert abs(sens["dividend-adjusted closes"]) < 15 and "dividend forward" in rep["reason"]


def test_witching_planted_effect_passes_with_dividends_priced():
    days, r, vix = _witching_returns(0, 2.5)
    raw, _, divs = _ex_dividend_on_witching(days, r, 0.0045)
    rep = bm.witching_straddle(days, raw, vix, div_yield=divs, n_boot=500, n_perm=2000)
    assert rep["verdict"] == "supported", rep["reason"]


class _RowsArchive:
    """Read-only stand-in for Archive: {bundle name: rows}."""

    def __init__(self, bundles):
        self.bundles = bundles

    def get(self, name):
        return SimpleNamespace(created_at=None) if name in self.bundles else None

    def load(self, name):
        return iter(self.bundles[name])


def _spy_rows(days, raw, adj):
    noon = lambda d: datetime.fromisoformat(d + "T16:00:00").replace(tzinfo=timezone.utc).timestamp()
    return [{"value": {"symbol": "SPY", "t": noon(d), "open": c, "high": c, "low": c, "close": float(c), "adjclose": float(a),
                       "volume": 1}} for d, c, a in zip(days, raw, adj)]


def test_witching_harness_reads_dividends_from_adjclose():
    # regression for the harness: it loaded raw closes only and priced at q = 0
    days, r, vix = _witching_returns(1, 0.0, start="1999-01-04")
    raw, adj, divs = _ex_dividend_on_witching(days, r, 0.015)
    arch = _RowsArchive({"daily-history-SPY": _spy_rows(days, raw, adj),
                         "cboe-VIX-history": [{"value": {"day": d, "close": v}} for d, v in vix.items()]})
    stat, n, verdict, reason = bm.macro_triple_witching_straddle(arch)
    assert verdict == "not_supported", reason
    assert stat["n_ex_dividend_witching"] == n == len([d for d in divs if d <= stat["last_day"]]) - stat["n_witching_skipped"]
    assert stat["dividend_treatment_sensitivity_diff_bps"]["ignored (q = 0, raw move)"] > 30
    assert "dividend forward" in reason and reason.startswith("MODEL-PRICED")


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
