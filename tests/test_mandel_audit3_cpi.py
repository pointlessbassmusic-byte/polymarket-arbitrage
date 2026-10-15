"""Audit 3: the CPI release calendar (``macro-release-cpi``) in the batch-4 harnesses, on synthetic data.

The CPI parts are reported variants and controls, never pass criteria: T-221's pooled FOMC+CPI variant and random
non-macro-day control, T-273's CPI-date repeat, T-341's CPI-overlap flag and T-216's "exclude opex days with FOMC/CPI"
control. Each harness loads the bundle only for those parts; without it they are listed as not run and the verdict is
the same. No archive, no network."""

import inspect
import json
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from mandel.experiments import batch4_fomc as fm
from mandel.experiments import batch4_ohlc as ob

CAPTURED = "2026-10-15T08:00:00+00:00"


def _days(start, end, weekdays_only=True):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(r):
    return 100 * np.cumprod(np.concatenate([[1.0], 1 + np.asarray(r)]))      # r[i-1] is the return ending on day i


def _ret_index(days, ev):
    pos = {d: i for i, d in enumerate(days)}
    return np.array([pos[e] - 1 for e in ev if e in pos and pos[e] > 0], dtype=int)


def _cpi_rows(days):
    return [{"available_at": d + "T12:30:00+00:00", "value": {"day": d, "series": "CPIAUCSL", "release": "cpi", "days_since_previous": None}}
            for d in days]


class _Entry:
    def __init__(self, created_at):
        self.created_at = created_at


class _TraceArchive:
    """Fake archive that records every bundle it is asked to load."""

    def __init__(self, bundles):
        self.b = bundles
        self.loaded = []

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(CAPTURED)

    def load(self, name):
        if name not in self.b:
            raise KeyError(name)
        self.loaded.append(name)
        return iter(self.b[name])


@pytest.fixture(autouse=True)
def _fresh_caches():
    fm._CACHE.clear(); ob._CACHE.clear()
    yield
    fm._CACHE.clear(); ob._CACHE.clear()


# ---------------------------------------------------------------------------------------------- the calendar --

def test_cpi_calendar_drops_revision_vintages_and_rows_after_capture():
    vintages = ["2024-01-11", "2024-02-09", "2024-02-13", "2024-03-12", "2024-03-20", "2024-04-10", "2026-11-12"]
    # 2024-02-09: February seasonal-factor vintage 4 days before the January CPI -> dropped in favour of 2024-02-13
    # 2024-03-20: 8 days after a kept release outside February -> a correction, dropped
    # 2026-11-12: available after the bundle's capture -> not visible
    want = ["2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10"]
    arc = _TraceArchive({"macro-release-cpi": _cpi_rows(vintages)})
    assert fm._cpi(arc) == want
    assert ob._cpi_days(_TraceArchive({"macro-release-cpi": _cpi_rows(vintages)})) == want


def test_cpi_calendar_absent_is_none_and_never_loaded():
    arc = _TraceArchive({})
    assert fm._cpi(arc) is None and ob._cpi_days(arc) is None
    assert arc.loaded == []


def test_no_stale_not_implemented_cpi_notes():
    for mod in (fm, ob):
        src = inspect.getsource(mod)
        assert "no CPI calendar" not in src and "no CPI release calendar" not in src, mod.__name__


# ----------------------------------------------------------------------------- T-221 pooled FOMC+CPI variant --

def _btc(fomc_sd, cpi_sd, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2021-03-01", "2026-10-14", weekdays_only=False)
    fomc = [days[i] for i in range(20, len(days), 45) if days[i] >= "2021-04-01"]
    cpi = [days[i] for i in range(25, len(days), 30) if days[i] >= "2021-04-01"] + [fomc[3]]    # one same-day FOMC+CPI
    r = rng.normal(0, 0.03, len(days) - 1)
    r[_ret_index(days, cpi)] = rng.normal(0, cpi_sd, len(set(cpi)))
    r[_ret_index(days, fomc)] = rng.normal(0, fomc_sd, len(fomc))
    return days, _closes(r), {d: 60.0 for d in days}, fomc, sorted(set(cpi))


def test_btc_pooled_variant_is_reported_and_never_decides():
    days, c, dvol, fomc, cpi = _btc(0.03, 0.10)        # big CPI-day moves, ordinary FOMC days
    base = fm.btc_event_straddle(days, c, dvol, fomc, n_boot=300)
    rep = fm.btc_event_straddle(days, c, dvol, fomc, cpi_days=cpi, n_boot=300, n_placebo=300)
    assert base["pooled_fomc_cpi"] is None and any("pooled FOMC+CPI" in x for x in base["not_run"])
    assert "pooled FOMC+CPI variant and non-macro control not run" in base["reason"]
    assert rep["not_run"] == [] and rep["full"] == base["full"]
    assert rep["verdict"] == base["verdict"] == "not_supported"                  # FOMC-only pass decides
    pooled = rep["pooled_fomc_cpi"]
    assert pooled["n_fomc"] == len(fomc) and pooled["n_cpi"] == len(cpi) and pooled["n_fomc_and_cpi_same_day"] == 1
    assert pooled["n_event"] == len(fomc) + len(cpi) - 1                          # the shared day counts once
    assert pooled["diff"] < 0 and pooled["ci"][1] < 0 and pooled["meets_pass_rule_as_fomc"]
    assert rep["cpi_only"]["diff"] < 0 and rep["cpi_only"]["n_event"] == len(cpi) - 1   # the FOMC day is not a CPI-only day
    assert "pooled FOMC+CPI (reported, not a criterion)" in rep["reason"]
    json.dumps(fm._clean(rep))


def test_btc_non_macro_control_and_placebo():
    days, c, dvol, fomc, cpi = _btc(0.10, 0.03, seed=1)   # big FOMC-day moves
    rep = fm.btc_event_straddle(days, c, dvol, fomc, cpi_days=cpi, n_boot=300, n_placebo=500)
    assert rep["verdict"] == "supported", rep["reason"]
    nm = rep["non_macro_control"]
    assert nm["n_event"] == len(fomc) and nm["n_other"] == len(days) - 1 - len(fomc) - (len(cpi) - 1) - 30   # 30 March days before start
    assert nm["diff"] < 0 and nm["random_non_macro_placebo_p_lower"] < 0.05
    obs, p = fm._random_day_placebo(np.zeros(10), np.zeros(10, dtype=bool), np.ones(10, dtype=bool), 10, 0)
    assert obs is None and p is None


# ---------------------------------------------------------------------------------------- T-273 CPI repeat --

def test_events_clear_of_window_rule():
    idx = {d: 20.0 for d in _days("2024-01-01", "2024-01-31")}
    e = "2024-01-10"                                     # Wednesday: window = close 01-09 .. close 01-11
    assert fm.events_clear_of(idx, [e], ["2024-01-11"]) == []          # other event inside the window
    assert fm.events_clear_of(idx, [e], [e]) == []
    assert fm.events_clear_of(idx, [e], ["2024-01-09"]) == [e]         # on the close-before day: before the window
    assert fm.events_clear_of(idx, [e], ["2024-01-12"]) == [e]
    assert fm.events_clear_of(idx, [e], []) == [e]
    assert fm.events_clear_of(idx, ["2024-01-13"], ["2024-01-15"]) == []   # weekend event: window 01-12 .. 01-15


def _gvz(bump_cpi, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2009-09-01", "2026-10-01")
    fomc = [days[i] for i in range(20, len(days), 31) if "2009-10-01" <= days[i] <= "2026-09-30"]
    cpi = [days[i] for i in range(27, len(days), 21) if "2009-10-01" <= days[i] <= "2026-09-30"]
    x = 20 + rng.normal(0, 0.5, len(days)); pos = {d: i for i, d in enumerate(days)}
    for e in cpi:
        i = pos[e]; x[max(0, i - 4):i + 1] += bump_cpi
    return {d: float(v) for d, v in zip(days, x)}, fomc, cpi


def test_gvz_cpi_repeat_is_reported_and_never_decides():
    gvz, fomc, cpi = _gvz(1.5)
    base = fm.gvz_fomc_change(gvz, fomc, vix=gvz, n_boot=300)
    rep = fm.gvz_fomc_change(gvz, fomc, vix=gvz, cpi_days=cpi, n_boot=300)
    assert base["cpi_repeat"] is None and any("CPI-date repeat" in x for x in base["not_run"]) and "CPI-date repeat not run" in base["reason"]
    assert rep["not_run"] == [] and rep["verdict"] == base["verdict"]
    assert rep["gvz"]["mean"] == base["gvz"]["mean"] and rep["gvz"]["ci"] == base["gvz"]["ci"]
    cr = rep["cpi_repeat"]
    assert cr["gvz"]["n"] == len(cpi) and cr["gvz"]["mean"] < -1 and cr["gvz"]["ci"][1] < 0
    clear = fm.events_clear_of(gvz, cpi, fomc)
    assert 0 < len(clear) < len(cpi) and cr["gvz_windows_without_fomc"]["n"] == len(clear)
    assert cr["vix"]["n"] == len(cpi)
    # the FOMC test's weekday-matched control now uses non-macro days only
    assert rep["gvz"]["n_control_days"] < base["gvz"]["n_control_days"]
    assert "CPI-date repeat (reported, not a criterion)" in rep["reason"] and "non-macro" in rep["reason"]


def test_index_event_change_control_exclude():
    idx = {d: 20.0 for d in _days("2020-01-01", "2020-12-31")}
    ev = ["2020-03-04", "2020-06-10"]
    a = fm.index_event_change(idx, ev, "2020-01-01", "2020-12-31", n_boot=50)
    b = fm.index_event_change(idx, ev, "2020-01-01", "2020-12-31", n_boot=50, control_exclude=["2020-09-16"])
    assert b["n_control_days"] == a["n_control_days"] - 3            # the CPI day and the days either side leave the control


# -------------------------------------------------------------------------------------- T-341 CPI-overlap flag --

def test_statement_day_cpi_overlap_flag():
    rng = np.random.default_rng(3)
    days = _days("1994-01-03", "2026-10-13")
    ev = [days[i] for i in range(20, len(days), 32)]
    overlap = ev[5:15:1]                                                       # 10 statement days that are CPI days
    mondays = [e for e in ev[20:] if date.fromisoformat(e).weekday() == 0]
    sat = (date.fromisoformat(mondays[0]) - timedelta(days=2)).isoformat()      # a Saturday release maps to Monday's session
    cpi = overlap + [sat] + [days[i] for i in range(9, len(days), 21) if days[i] not in set(ev)]
    r = rng.normal(0.0003, 0.01, len(days) - 1)
    r[_ret_index(days, overlap + [mondays[0]])] += 0.03
    c = _closes(r)
    base = fm.statement_day_effect(days, c, ev, n_boot=200)
    rep = fm.statement_day_effect(days, c, ev, cpi_days=cpi, n_boot=200)
    assert base["cpi_overlap"] is None and any("CPI-overlap" in x for x in base["not_run"]) and "CPI-overlap flag not run" in base["reason"]
    assert rep["verdict"] == base["verdict"] and rep["net"] == base["net"]       # a flag, not a criterion
    co = rep["cpi_overlap"]
    assert co["n_overlap"] == 11 and co["overlap_days"] == sorted(overlap + [mondays[0]])
    ds, rr = fm._returns(days, c, "1994-01-01", "2026-12-31")
    f = np.isin(ds, ev); ov = np.isin(ds, co["overlap_days"]); net = rr - f * 2.0 / 1e4
    want = net[f & ~ov].mean() - net[~f].mean()
    assert co["excluding_overlap_days"]["net_diff_bps"] == pytest.approx(want * 1e4)
    assert co["excluding_overlap_days"]["net_diff_bps"] < rep["net"]["diff"] * 1e4 - 5
    assert co["excluding_overlap_days"]["n_statement_days"] == rep["n"] - 11
    assert "CPI overlap (flag, not a criterion): 11 statement days" in rep["reason"]


# ------------------------------------------------------------------------- T-216 FOMC/CPI opex exclusion control --

def _opex(seed=0):
    rng = np.random.default_rng(seed)
    days = _days("1993-02-01", "2026-09-30")
    tf = {ob.third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in days}
    r = np.array([rng.normal(0, 0.003 if d in tf else 0.01) for d in days])
    return days, 100 * np.cumprod(1 + r), {d: 16.0 for d in days}


def test_opex_fomc_cpi_exclusion_control():
    days, C, vix = _opex()
    years = range(1995, 2021)
    cpi_fri = [ob.third_friday(y, m).isoformat() for y in years for m in (1, 4, 7, 10)]
    cpi_thu = [(ob.third_friday(y, m) - timedelta(days=1)).isoformat() for y in years for m in (2, 5, 8, 11)]
    fomc = {(ob.third_friday(y, 3) - timedelta(days=1)).isoformat() for y in range(2000, 2005)}
    base = ob.opex_straddle(days, C, vix, fomc_days=fomc, n_boot=500, n_perm=100)
    rep = ob.opex_straddle(days, C, vix, fomc_days=fomc, cpi_days=cpi_fri + cpi_thu, n_boot=500, n_perm=100)
    assert "ex_fomc_cpi_opex" not in base["controls"] and base["not_run"] and "CPI exclusion control not run" in base["reason"]
    assert rep["not_run"] == [] and rep["verdict"] == base["verdict"] == "supported"        # a control, not a criterion
    assert rep["diff_bps"] == base["diff_bps"] and rep["ci_bps"] == base["ci_bps"]
    ctrl = rep["controls"]; e = ctrl["ex_fomc_cpi_opex"]
    assert ctrl["n_opex_cpi_excluded"] == len(cpi_fri) and ctrl["n_opex_fomc_excluded"] == len(fomc)
    assert e["n_opex_excluded"] == len(cpi_fri) + len(fomc) and e["n_opex"] == rep["n"] - e["n_opex_excluded"]
    assert e["also_thursday_cpi"]["n_opex_thursday_cpi"] == len(cpi_thu)              # a Thursday release precedes the sale
    assert e["also_thursday_cpi"]["n_opex"] == e["n_opex"] - len(cpi_thu)
    fri, pnl, _, _ = ob.thu_fri_straddles(days, C, vix)
    fr = np.array(fri); ox = np.array([d == ob.third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in fr])
    drop = np.isin(fr, cpi_fri) | np.isin(fr, [(date.fromisoformat(d) + timedelta(days=1)).isoformat() for d in fomc])
    want = pnl[ox & ~drop].mean() - pnl[~ox].mean()
    assert e["diff_bps"] == pytest.approx(want * 1e4) and e["ci_bps"][0] > 0
    both = e["macro_fridays_out_of_both_groups"]
    assert both["n_other"] == base["n_other"] and both["n_fridays_dropped"] == e["n_opex_excluded"]   # no non-opex macro Friday here
    assert "control, opex Fridays with FOMC/CPI excluded" in rep["reason"]


# ------------------------------------------------------------------------------------------ harness wiring --

def _bar_rows(sym, days, closes, hour="14:30"):
    rows = []
    for d, c in zip(days, closes):
        t = datetime.fromisoformat(f"{d}T{hour}:00+00:00").timestamp()
        rows.append({"available_at": d + "T23:00:00+00:00", "value": {"symbol": sym, "t": t, "open": c, "high": c * 1.004, "low": c * 0.996,
                                                                      "close": c, "adjclose": c}})
    return rows


def _index_rows(series):
    return [{"available_at": d + "T23:00:00+00:00", "value": {"day": d, "close": v}} for d, v in series.items()]


def _fomc_rows(days):
    return [{"value": {"decision_day": d, "scheduled": True}} for d in days]


def test_harnesses_load_cpi_only_when_archived_and_keep_their_verdicts(monkeypatch):
    seen = {}

    def spy(name, real):
        def f(*a, **k):
            seen[name] = k.get("cpi_days")
            return real(*a, **k)
        return f

    monkeypatch.setattr(fm, "statement_day_effect", spy("T-341", lambda *a, **k: {"n": 0, "verdict": "inconclusive", "reason": "stub — x"}))
    gvz, fomc_g, _ = _gvz(0.0, seed=4)
    bd, bc, dvol, fomc_b, _ = _btc(0.03, 0.03, seed=5)
    od, oc, vix = _opex(seed=6)
    bundles = {"cboe-GVZ-history": _index_rows(gvz), "fomc-meetings": _fomc_rows(sorted(set(fomc_g) | set(fomc_b))),
               "daily-history-BTC-USD": _bar_rows("BTC-USD", bd, bc, hour="00:00"), "deribit-dvol-BTC-history": _index_rows(dvol),
               "daily-history-SPY": _bar_rows("SPY", od, oc), "cboe-VIX-history": _index_rows(vix)}
    cpi_days = []                                                     # one release a month: the 12th, or the next weekday
    for y in range(2005, 2027):
        for m in range(1, 13):
            d = date(y, m, 12)
            d += timedelta(days=(7 - d.weekday()) % 7 if d.weekday() >= 5 else 0)
            if d.isoformat() <= "2026-10-14":
                cpi_days.append(d.isoformat())
    out = {}
    for with_cpi in (False, True):
        b = dict(bundles)
        if with_cpi:
            b["macro-release-cpi"] = _cpi_rows(cpi_days)
        for name, fn in (("fomc_btc_event_straddle", fm.fomc_btc_event_straddle), ("fomc_gvz_event_change", fm.fomc_gvz_event_change),
                         ("fomc_statement_day_drift", fm.fomc_statement_day_drift), ("ohlc_opex_pin_straddle", ob.ohlc_opex_pin_straddle)):
            fm._CACHE.clear(); ob._CACHE.clear()
            arc = _TraceArchive(b)
            stat, n, verdict, reason = fn(arc)
            json.dumps(stat)
            assert ("macro-release-cpi" in arc.loaded) == with_cpi, name
            out[(name, with_cpi)] = (verdict, stat)
        assert (seen["T-341"] is not None) == with_cpi
    assert seen["T-341"] == cpi_days
    for name in ("fomc_btc_event_straddle", "fomc_gvz_event_change", "ohlc_opex_pin_straddle"):
        (v0, s0), (v1, s1) = out[(name, False)], out[(name, True)]
        assert v0 == v1, name
        assert s0["not_run"] and any("macro-release-cpi not archived" in x for x in s0["not_run"]), name
        assert not any("macro-release-cpi" in x for x in s1["not_run"]), name
    assert out[("fomc_btc_event_straddle", True)][1]["pooled_fomc_cpi"]["n_cpi"] == len([d for d in cpi_days if "2021-04-01" <= d <= bd[-1]])
    assert out[("fomc_gvz_event_change", True)][1]["cpi_repeat"]["gvz"]["n"] == len([d for d in cpi_days if "2009-10-01" <= d <= "2026-09-30"])
    assert "ex_fomc_cpi_opex" in out[("ohlc_opex_pin_straddle", True)][1]["controls"]
