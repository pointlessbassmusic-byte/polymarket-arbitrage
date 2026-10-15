"""Regression tests for the options_market audit findings (OM-1 .. OM-12), all on synthetic data.

Each test names the finding it pins. The bill helpers invert the corrected FRED conversions (DTB3 discount basis, DGS2 semiannual), and
every bill row is dated BEFORE the capture day, as a point-in-time run would see it.
"""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import options_market as om
from mandel.options import bs


# ---------------------------------------------------------------------------------------------------------------- helpers --

def _weekdays(start, end):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _idx(days, vals):
    return [{"value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _px(days, closes, sym="SPY"):
    import datetime as dt
    return [{"value": {"symbol": sym, "t": dt.datetime.fromisoformat(d + "T20:00:00+00:00").timestamp(), "close": float(c)}} for d, c in zip(days, closes)]


def _dtb3_for(rc):
    return (1 - math.exp(-rc * 91 / 365)) * 360 / 91 * 100


def _dgs2_for(rc):
    return 200 * (math.exp(rc / 2) - 1)


def _bill_rows(rc=0.04, day="2026-09-30"):
    return [{"value": {"day": day, "value": _dtb3_for(rc)}}]


def _dgs2_rows(rc=0.04, day="2026-09-30"):
    return [{"value": {"day": day, "value": _dgs2_for(rc)}}]


def _capture_days(n, start="2026-10-14"):
    return _weekdays(start, "2027-12-31")[:n]


def _chain(spot, day, r, sigma, half_spread, expiries_dte, strikes, root=None):
    rows, cap = [], date.fromisoformat(day)
    for dte in expiries_dte:
        exp = (cap + timedelta(days=dte)).isoformat(); T = dte / 365
        for k in strikes:
            for kind in ("call", "put"):
                mid = float(bs.price(spot, k, T, r, sigma, kind))
                v = {"expiry": exp, "type": kind, "strike": float(k), "bid": max(mid - half_spread, 0.01), "ask": mid + half_spread}
                if root:
                    v["sym"] = root + exp.replace("-", "")[2:] + ("C" if kind == "call" else "P")
                rows.append({"value": v})
    return rows


def _spike_series(outcomes, v3_event=35.0, vix_event=40.0, block=30):
    """One VIX > 30 backwardation event every `block` days; VIX 21 days later = the outcome (VIX3M set high there so it is no event)."""
    n = block * len(outcomes) + 25
    vix = np.full(n, 15.0); v3 = np.full(n, 18.0)
    for i, out in enumerate(outcomes):
        t0 = block * i
        vix[t0], v3[t0] = vix_event, v3_event
        vix[t0 + 21], v3[t0 + 21] = out, 80.0
    days = _weekdays("2008-01-02", "2030-12-31")[:n]
    return _idx(days, vix), _idx(days, v3)


# F after an event at VIX 40 / VIX3M 35: sqrt((3*35^2 - 40^2)/2) = 32.2
_F = math.sqrt((3 * 35 ** 2 - 40 ** 2) / 2)


# ------------------------------------------------------------------------------------- OM-1 / OM-12: T-241 claim sentence --

def test_om1_t241_strategy_side_pass_refutes_claim_not_supported():
    """19/23 below F (CI above 0.5) is the strategy passing, which REFUTES T-241's 'fewer than 50%' sentence: not_supported (was supported),
    even below min_n, because the exact CI failure is decisive."""
    vix, v3 = _spike_series([20.0] * 19 + [36.0] * 4)          # 20 < F (and < spot); 36 > F (but < spot)
    rep = om.vix_spike_forward(vix, v3)
    assert rep["n_events"] == 23 and rep["p_below_forward"] == pytest.approx(19 / 23) and rep["ci_forward"][0] > 0.5
    assert rep["verdict"] == "not_supported"
    crit = dict((c, ok) for c, ok in rep["criteria"])
    assert crit["P(VIX_t+21 < F) < 0.5"] is False


def test_om1_t241_claim_consistent_data_is_never_supported():
    """Below F rarely, below spot always: every implemented criterion passes, but the put-spread P&L is not implemented -> inconclusive
    (with n >= min_n 25 and below it)."""
    for n in (30, 12):
        vix, v3 = _spike_series([34.0] * n)                       # F (32.2) < 34 < spot 40
        rep = om.vix_spike_forward(vix, v3)
        assert rep["p_below_forward"] == 0.0 and rep["p_below_spot"] == 1.0
        assert rep["verdict"] == "inconclusive", (n, rep["reason"])
        assert any(ok is None and "put spread" in c for c, ok in rep["criteria"])


def test_om1_t241_below_spot_criterion_is_gated():
    """'below spot VIX in more than 75% of cases' is now a criterion: decisively failing it (CI upper <= 0.75) is not_supported."""
    vix, v3 = _spike_series([45.0] * 12)                          # above spot and F every time
    rep = om.vix_spike_forward(vix, v3)
    assert rep["ci_spot"][1] <= 0.75 and rep["verdict"] == "not_supported"
    crit = dict((c, ok) for c, ok in rep["criteria"])
    assert crit["P(VIX_t+21 < spot VIX) > 0.75"] is False and crit["P(VIX_t+21 < F) < 0.5"] is True


def test_om1_t241_min_n_non_decisive_failure_is_inconclusive():
    """At n = 12 < min_n 25 a point frequency of 0.5 (CI covering 0.5) is not decisive -> inconclusive; at n = 26 it fails -> not_supported."""
    vix, v3 = _spike_series([30.0, 34.0] * 6)                     # 30 < F, 34 > F; both below spot
    rep = om.vix_spike_forward(vix, v3)
    assert rep["n_events"] == 12 and rep["p_below_forward"] == 0.5 and rep["verdict"] == "inconclusive"
    vix, v3 = _spike_series([30.0, 34.0] * 13)
    rep = om.vix_spike_forward(vix, v3)
    assert rep["n_events"] == 26 and rep["verdict"] == "not_supported"


def test_om1_t231_pass_below_min_n_is_not_supported_verdict():
    """T-231 (min_n 70 cycles): a clear pass on 40 cycles is inconclusive; the same on 75 cycles is supported."""
    rng = np.random.default_rng(3)

    def run(cycles):
        n = 63 * (cycles + 1) + 2
        days = _weekdays("2007-01-02", "2040-12-31")[:n]
        closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.10 / math.sqrt(252), n)))
        return om.term_vs_spot_premium(_idx(days, np.full(n, 20.0)), _idx(days, np.full(n, 23.0)), _px(days, closes))
    short, full = run(40), run(75)
    assert short["n_cycles"] < 70 and short["p_value"] < 0.025 and short["verdict"] == "inconclusive"
    assert full["n_cycles"] >= 70 and full["verdict"] == "supported"


# ----------------------------------------------------------------------------------------------- OM-2: bill conversions --

def test_om2_dtb3_is_discount_basis_and_dgs2_semiannual():
    assert om._dtb3_cont(4.09) * 1e4 == pytest.approx(416.84, abs=0.05)       # was log(1.0409) = 400.9 bp
    assert om._semiannual_cont(4.79) * 1e4 == pytest.approx(473.4, abs=0.1)   # was log(1.0479) = 467.9 bp
    d3 = {"2026-10-13": 4.09}
    assert om._bill_cont(d3, "2026-10-14") == pytest.approx(om._dtb3_cont(4.09))
    curve = om._bill_curve(d3, {"2026-10-13": 4.79}, "2026-10-14")
    assert curve(0.1) == pytest.approx(om._dtb3_cont(4.09)) and curve(3.0) == pytest.approx(om._semiannual_cont(4.79))


def test_om2_box_borrowing_and_parity_use_the_continuous_bill():
    day, spot, r = "2026-10-14", 5000.0, 0.045
    rows = _chain(spot, day, r, 0.2, 0.0, [200, 400], range(4300, 5701, 100))
    rep = om.box_borrowing([(day, spot, rows)], _bill_rows(r), _dgs2_rows(r))
    assert rep["days"][0]["median_advantage_bp"] == pytest.approx(150.0, abs=0.5)    # r_borrow = r = bill -> exactly the 150 bp margin
    par = om.parity_check([(day, "XYZ", spot, _chain(spot, day, r, 0.2, 0.5, [45, 90], range(4800, 5201, 20)))], _bill_rows(r))
    assert abs(par["per_day"][0]["median_rate_gap_bp"]) < 0.5                         # the old conversion left a ~-16 bp gap here


# ------------------------------------------------------------------------------------------ OM-3: day one is a criterion --

def _patch_box_rates(monkeypatch):
    monkeypatch.setattr(om, "box_rates", lambda rows, spot, day, dtb3, dgs2, dte_range, *a, **k: rows)


def _lend_boxes(bp, bill=0.04, n=20):
    return [{"r_lend": bill + bp / 1e4, "r_mid": bill + bp / 1e4, "r_borrow": None, "bill": bill} for _ in range(n)]


def test_om3_t186_failed_day_one_is_not_supported(monkeypatch):
    _patch_box_rates(monkeypatch)
    days = _capture_days(20)
    caps = [(d, 5000.0, _lend_boxes(-40 if i == 0 else 40)) for i, d in enumerate(days)]
    assert om.box_lending(caps, _bill_rows(), _dgs2_rows())["verdict"] == "not_supported"           # was supported (19/20 pass)
    assert om.box_lending(caps[:2], _bill_rows(), _dgs2_rows())["verdict"] == "not_supported"       # was inconclusive


def test_om3_t186_persistence_needs_20_days_and_80_percent(monkeypatch):
    _patch_box_rates(monkeypatch)
    days = _capture_days(20)
    good = [(d, 5000.0, _lend_boxes(40)) for d in days]
    assert om.box_lending(good, _bill_rows(), _dgs2_rows())["verdict"] == "supported"
    assert om.box_lending(good[:19], _bill_rows(), _dgs2_rows())["verdict"] == "inconclusive"
    mixed = [(d, 5000.0, _lend_boxes(40 if i < 15 else -40)) for i, d in enumerate(days)]           # 15/20 = 75%
    assert om.box_lending(mixed, _bill_rows(), _dgs2_rows())["verdict"] == "not_supported"


def _borrow_boxes(adv_bp, bill=0.04, n=20):
    return [{"r_lend": None, "r_mid": None, "r_borrow": bill + 0.015 - adv_bp / 1e4, "bill": bill} for _ in range(n)]


def test_om3_t187_failed_day_one_is_not_supported_and_min_n_10(monkeypatch):
    _patch_box_rates(monkeypatch)
    days = _capture_days(20)
    caps = [(d, 5000.0, _borrow_boxes(0 if i == 0 else 150)) for i, d in enumerate(days)]
    rep = om.box_borrowing(caps, _bill_rows(), _dgs2_rows())
    assert rep["days"][0]["median_advantage_bp"] == pytest.approx(0, abs=1e-6) and rep["verdict"] == "not_supported"   # was supported
    assert om.box_borrowing(caps[:2], _bill_rows(), _dgs2_rows())["verdict"] == "not_supported"                     # was inconclusive
    good = [(d, 5000.0, _borrow_boxes(150)) for d in days]
    assert om.box_borrowing(good[:10], _bill_rows(), _dgs2_rows())["verdict"] == "supported"       # trial.min_n 10 days
    assert om.box_borrowing(good[:9], _bill_rows(), _dgs2_rows())["verdict"] == "inconclusive"


# ------------------------------------------------------------------------------------- OM-4 / OM-11: T-181 parity --

def _parity_caps(rates, bill=0.04, sym="SPX"):
    spot = 5000.0
    return [(d, sym, spot, _chain(spot, d, r, 0.2, 0.5, [45, 90], range(4800, 5201, 20))) for d, r in zip(_capture_days(len(rates)), rates)]


def test_om4_t181_failed_day_one_is_not_supported():
    caps = _parity_caps([0.09, 0.04])                     # day one implied rate 500 bp off the bill, day two on it
    rep = om.parity_check(caps, _bill_rows(0.04))
    assert rep["per_day"][0]["rate_ok"] is False and rep["per_day"][1]["rate_ok"] is True
    assert rep["verdict"] == "not_supported"              # was inconclusive


def test_om4_t181_any_failure_in_first_20_days_is_not_supported():
    rep = om.parity_check(_parity_caps([0.04, 0.04, 0.09]), _bill_rows(0.04))
    assert rep["verdict"] == "not_supported"


def test_om11_t181_clean_20_days_is_inconclusive_without_f_theo():
    """20 clean days used to be 'supported'; the claim's violation statistic needs F_theo = S e^{rT} - FV(D), which is not implemented."""
    rep = om.parity_check(_parity_caps([0.04] * 20), _bill_rows(0.04))
    assert rep["n_days"] == 20 and all(d["rate_ok"] for d in rep["per_day"]) and rep["verdict"] == "inconclusive"
    assert "F_theo" in rep["reason"] and rep["per_day"][0]["violation_rate_basis"].startswith("free-intercept")


def test_om11_level_shifted_forward_is_invisible_to_the_diagnostic():
    """A forward shifted 5 points above S e^{rT} at a 0.1 half-spread: the free-fit diagnostic reports 0% (it absorbs the level), so it
    cannot stand in for the claim's statistic and the verdict cannot be supported."""
    day, spot, r = "2026-10-14", 5000.0, 0.04
    rows = _chain(spot + 5 * math.exp(-r * 60 / 365), day, r, 0.2, 0.05, [60], range(4800, 5201, 20))
    rep = om.parity_check([(day, "SPX", spot, rows)], _bill_rows(r))
    assert rep["per_day"][0]["violation_rate"] == 0.0 and rep["verdict"] != "supported"


# ---------------------------------------------------------------------------------------- OM-5: T-503 persistence --

def _mid_boxes(bp, bill=0.04, n=41):
    return [{"root": "SPXW", "expiry": "2027-01-15", "T": 0.25, "k1": 5000.0, "k2": 5250.0, "r_mid": bill + (bp + j / 20) / 1e4, "r_borrow": None}
            for j in range(-(n // 2), n // 2 + 1)]


def _patch_boxes_v2(monkeypatch):
    seen = []

    def fake(rows, spot, day, dte_range, *a, **k):
        seen.append(k)
        return rows
    monkeypatch.setattr(om, "_boxes_v2", fake)
    return seen


def test_om5_t503_persistence_has_no_tolerance(monkeypatch):
    _patch_boxes_v2(monkeypatch)
    days = _capture_days(20)
    caps = [(d, 5000.0, _mid_boxes(150 if i in (3, 7, 11, 15) else 40)) for i, d in enumerate(days)]   # 16/20 in range
    assert om.box_mid_v2(caps, _bill_rows(), n_boot=100)["verdict"] == "not_supported"                 # was supported (80% rule)
    good = [(d, 5000.0, _mid_boxes(40)) for d in days]
    assert om.box_mid_v2(good, _bill_rows(), n_boot=100)["verdict"] == "supported"
    assert om.box_mid_v2(good[:3], _bill_rows(), n_boot=100)["verdict"] == "inconclusive"
    early = [(d, 5000.0, _mid_boxes(150 if i == 1 else 40)) for i, d in enumerate(days[:3])]
    assert om.box_mid_v2(early, _bill_rows(), n_boot=100)["verdict"] == "not_supported"                # a failure among the first 20 is decisive


def test_om5_t503_persistence_uses_the_first_20_days(monkeypatch):
    _patch_boxes_v2(monkeypatch)
    days = _capture_days(22)
    caps = [(d, 5000.0, _mid_boxes(40 if i < 20 else 150)) for i, d in enumerate(days)]                # days 21-22 out of range
    assert om.box_mid_v2(caps, _bill_rows(), n_boot=100)["verdict"] == "supported"


# --------------------------------------------------------------------------- OM-8: T-503 uses all strike pairs --

def test_om8_t503_uses_all_pairs_with_both_bids(monkeypatch):
    day, spot, r = "2026-10-14", 5000.0, 0.044
    rows = _chain(spot, day, r, 0.2, 0.0, [90], range(4306, 5700, 25), root="SPXW")    # strikes all off the $25 grid
    rep = om.box_mid_v2([(day, spot, rows)], _bill_rows(0.04), n_boot=100)
    d0 = rep["days"][0]
    assert rep["n_days"] == 1 and d0["n_boxes"] > 0                                    # the old step=25 filter found no boxes at all
    assert d0["median_bp"] == pytest.approx(40.0, abs=0.5) and d0["robustness_step25_wide"]["n_boxes"] == 0
    seen = _patch_boxes_v2(monkeypatch)
    om.box_mid_v2([(day, spot, _mid_boxes(40))], _bill_rows(), n_boot=50)
    assert seen[0].get("min_width_frac") == 0.0 and seen[0].get("step", "unset") is None


# ---------------------------------------------------------------------------- OM-9: T-506 median over expiries --

def test_om9_t506_median_is_over_expiries_not_pooled(monkeypatch):
    _patch_boxes_v2(monkeypatch)
    b0 = 0.04
    boxes = ([{"root": "SPXW", "expiry": "2027-06-18", "r_borrow": b0 + 40 / 1e4, "r_mid": None}] * 100
             + [{"root": "SPXW", "expiry": e, "r_borrow": b0 + 60 / 1e4, "r_mid": None} for e in ("2027-09-17", "2027-12-17") for _ in range(5)])
    rep = om.box_borrow_v2([("2026-10-14", 5000.0, boxes)], _bill_rows(b0))
    d0 = rep["days"][0]
    assert d0["pooled_median_bp"] == pytest.approx(40) and d0["median_bp"] == pytest.approx(60) and d0["n_expiries"] == 3
    assert rep["verdict"] == "not_supported"                                            # pooled median (40 < 50) would have passed day one


# ------------------------------------------------------------------------------ OM-10: point-in-time bill rows --

def test_om10_bill_is_the_row_before_the_capture_day(monkeypatch):
    assert om._bill_obs({"2026-10-09": 4.06, "2026-10-13": 4.09, "2026-10-14": 9.99}, "2026-10-14") == ("2026-10-13", 4.09)
    with pytest.raises(ValueError):
        om._bill_obs({"2026-10-14": 4.09}, "2026-10-14")
    dtb3 = [{"value": {"day": "2026-10-13", "value": _dtb3_for(0.04)}}, {"value": {"day": "2026-10-14", "value": 9.99}}]
    _patch_boxes_v2(monkeypatch)
    rep = om.box_mid_v2([("2026-10-14", 5000.0, _mid_boxes(40))], dtb3, n_boot=50)
    d0 = rep["days"][0]
    assert d0["bill"]["bill_day"] == "2026-10-13" and d0["median_bp"] == pytest.approx(40, abs=0.01)
    rep = om.box_borrow_v2([("2026-10-14", 5000.0, [{"root": "SPX", "expiry": "2027-06-18", "r_borrow": 0.045, "r_mid": None}])], dtb3)
    assert rep["days"][0]["bill"]["bill_day"] == "2026-10-13"


def test_om10_chain_harnesses_record_the_bill_used():
    day, spot, r = "2026-10-14", 5000.0, 0.04
    dtb3 = [{"value": {"day": "2026-10-13", "value": _dtb3_for(r)}}, {"value": {"day": day, "value": 9.99}}]
    dgs2 = [{"value": {"day": "2026-10-13", "value": _dgs2_for(r)}}, {"value": {"day": day, "value": 9.99}}]
    rows = _chain(spot, day, r, 0.2, 0.0, [120, 240], range(4300, 5701, 100), root="SPXW")
    lend = om.box_lending([(day, spot, rows)], dtb3, dgs2)
    assert lend["days"][0]["bill"]["bill_day"] == "2026-10-13" and lend["days"][0]["bill"]["dgs2_day"] == "2026-10-13"
    assert abs(lend["days"][0]["median_spread_bp"]) < 0.5                             # same-day 9.99% would give about -600 bp
    par = om.parity_check([(day, "SPX", spot, _chain(spot, day, r, 0.2, 0.5, [45, 90], range(4800, 5201, 20)))], dtb3)
    assert par["per_day"][0]["bill"]["bill_day"] == "2026-10-13" and abs(par["per_day"][0]["median_rate_gap_bp"]) < 0.5
    pv = om.parity_v2([(day, spot, _chain(spot, day, r, 0.2, 0.5, [45, 90], range(4800, 5201, 20), root="SPXW"))], dtb3)
    assert pv["days"][0]["bill"]["bill_day"] == "2026-10-13"


# ------------------------------------------------------------------------- OM-6 / OM-7: T-502 pinning --

def _pin_closes(days, opex_dist, control_dist, other_dist=0.25):
    """Closes whose distance to the nearest $1 is set per day: evenly spread quantiles per year for opex and control days."""
    monthly = om._monthly_expiries(days); expiring = om._spy_expiry_days(days) | monthly
    dist = {}
    for y in sorted({d[:4] for d in days}):
        yd = [d for d in days if d.startswith(y)]
        a = [d for d in yd if d in monthly]; b = [d for d in yd if d not in expiring]
        for j, d in enumerate(a):
            dist[d] = opex_dist(j, len(a), d)
        perm = np.random.default_rng(int(y)).permutation(len(b))
        for j, d in zip(perm, b):
            dist[d] = control_dist(j, len(b), d)
    return [100 + (i % 50) + dist.get(d, other_dist) for i, d in enumerate(days)]


def test_om6_t502_p_is_against_ratio_090_not_difference_zero():
    """True ratio 0.88: significantly below 1 (the old p) but not significantly below 0.90 (T-502's null) -> not_supported (was supported)."""
    days = _weekdays("2005-01-03", "2022-11-11")             # primary period only, so the planted per-year means are exact
    closes = _pin_closes(days, lambda j, n, d: (j + 0.5) / n * 0.44, lambda j, n, d: (j + 0.5) / n * 0.5)
    rep = om.expiry_pinning(_px(days, closes), n_boot=2000)
    assert rep["ratio"] == pytest.approx(0.88, abs=0.005) and rep["p_diff"] < 0.05     # the old test would pass
    assert rep["p_value"] >= 0.05 and rep["verdict"] == "not_supported"
    strong = _pin_closes(days, lambda j, n, d: (j + 0.5) / n * 0.3, lambda j, n, d: (j + 0.5) / n * 0.5)
    rep = om.expiry_pinning(_px(days, strong), n_boot=2000)
    assert rep["ratio"] == pytest.approx(0.6, abs=0.005) and rep["p_value"] < 0.05 and rep["verdict"] == "supported"


def test_om6_t502_ratio_at_the_090_boundary_is_not_supported():
    """At the null boundary (ratio 0.90) the old code (ratio <= 0.9 and p against 0) said supported; P(boot ratio >= 0.90) is ~0.5 now."""
    days = _weekdays("2005-01-03", "2022-11-11")
    closes = _pin_closes(days, lambda j, n, d: (j + 0.5) / n * 0.45, lambda j, n, d: (j + 0.5) / n * 0.5)
    rep = om.expiry_pinning(_px(days, closes), n_boot=500)
    assert rep["ratio"] == pytest.approx(0.90, abs=1e-9) and rep["p_diff"] < 0.05 and rep["p_value"] > 0.3 and rep["verdict"] == "not_supported"


def test_om7_calendar_control_and_holiday_third_fridays():
    days = [d for d in _weekdays("2014-01-01", "2023-12-29") if d not in ("2014-04-18", "2019-04-19")]   # Good Fridays (third Fridays)
    monthly = om._monthly_expiries(days); expiring = om._spy_expiry_days(days)
    assert "2014-04-17" in monthly and "2019-04-18" in monthly                          # holiday third Friday -> Thursday is the treatment day
    assert "2015-03-16" not in expiring                                                 # pre-2016 Monday: no SPY expiration (control)
    assert "2017-03-13" in expiring and "2017-03-15" in expiring                        # 2016+ Monday and Wednesday weeklies
    assert "2017-03-14" not in expiring and "2017-03-16" not in expiring                # Tuesday / Thursday: control
    assert "2023-03-14" in expiring                                                     # daily expirations from late 2022


def test_om7_weekly_pinning_does_not_contaminate_the_control():
    """Pin EVERY SPY expiration (monthlies and weeklies). The old control (all non-third-Friday days) held the pinned weeklies; the
    calendar control holds only days with no expiration, so the planted effect shows in full and the post-2022 regime is reported apart."""
    days = _weekdays("2005-01-03", "2024-06-28")
    expiring = om._spy_expiry_days(days) | om._monthly_expiries(days)
    rng = np.random.default_rng(5)
    closes = [100 + (i % 50) + (0.03 if d in expiring else rng.uniform(0, 0.5)) for i, d in enumerate(days)]
    rep = om.expiry_pinning(_px(days, closes), n_boot=500)
    assert rep["ratio"] < 0.2 and rep["verdict"] == "supported"
    assert rep["n_opex"] >= om.T502_MIN_OPEX and len(rep["regimes"]) == 3
    post = rep["regimes"]["Nov 2022 on (daily expiries; control non-monthly days)"]
    assert post["n_opex"] > 0 and post["ratio"] == pytest.approx(1.0, abs=0.01)      # every day pinned after 2022: no contrast, reported only
