"""Batch 6b, group chain: captured-chain arbitrage and financing claims and the MODEL-PRICED strangle vs straddle, on
synthetic data only (no archive, no network). Each core function gets a planted effect that passes and a null that does
not; synthetic chains are Black-Scholes prices with stated half-spreads."""

import json
import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6b_chain as c
from mandel.options import bs


# ===================================================================================================== fixtures ==

class _Entry:
    def __init__(self, name):
        self.name = name
        self.created_at = "2100-01-01T00:00:00+00:00"


class FakeArchive:
    def __init__(self, bundles):
        self.b = bundles

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name)

    def load(self, name):
        return iter(self.b[name])

    def entries(self):
        return [_Entry(n) for n in self.b]


def _bdays(start: str, n: int) -> list:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _px_rows(days, closes, adj=None):
    adj = closes if adj is None else adj
    out = []
    for d, cl, a in zip(days, closes, adj):
        t = int((date.fromisoformat(d) - date(1970, 1, 1)).days * 86400 + 14 * 3600)
        out.append({"available_at": d + "T23:00:00+00:00", "value": {"t": t, "close": float(cl), "adjclose": float(a)}})
    return out


def _fred_rows(days, pct):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": pct}} for d in days]


def _idx_rows(days, vals):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _sym(root, e, kind, K):
    return f"{root}{e[2:4]}{e[5:7]}{e[8:10]}{'C' if kind == 'call' else 'P'}{int(round(K * 1000)):08d}"


def chain_values(spot, quote_day, dtes, strikes, r_opt, sigma=0.2, hs=0.01, root="SPY", sig_by_dte=None):
    """Black-Scholes mids at rate r_opt (no dividends) with half-spread hs; bid floored at 0."""
    out = []
    qd = date.fromisoformat(quote_day)
    for dte in dtes:
        e = (qd + timedelta(days=dte)).isoformat()
        T = dte / 365.0
        s = sig_by_dte.get(dte, sigma) if sig_by_dte else sigma
        for K in strikes:
            for kind in ("call", "put"):
                mid = float(bs.price(spot, K, T, r_opt, s, kind, 0.0))
                d = float(bs.greeks(spot, K, T, r_opt, s, kind, 0.0)["delta"])
                out.append({"sym": _sym(root, e, kind, K), "expiry": e, "type": kind, "strike": float(K),
                            "bid": max(round(mid - hs, 6), 0.0), "ask": round(mid + hs, 6), "delta": d, "iv": s})
    return out


def _by(*a, **k):
    return c.chain_by_root(chain_values(*a, **k))


R = c.dtb3_continuous(4.0)          # the bill used throughout


# ================================================================================================ statistics ==

def test_binomial_bounds_match_closed_forms():
    assert c.cp_upper(0, 4) == pytest.approx(1 - 0.05 ** 0.25, abs=1e-6)
    assert c.cp_lower(4, 4) == pytest.approx(0.05 ** 0.25, abs=1e-6)
    assert c.binom_sf(3, 3, 0.5) == pytest.approx(0.125, abs=1e-9)
    assert c.binom_cdf(1, 4, 0.5) == pytest.approx(5 / 16, abs=1e-9)
    up = c.cp_upper(41, 49)
    assert 0.90 < up < 0.93                      # 41/49 cannot be 95%: decisive
    assert c.cp_upper(5000, 5000) == 1.0 and c.cp_lower(0, 7000) == 0.0
    assert c.cp_upper(0, 7404) == pytest.approx(1 - 0.05 ** (1 / 7404), rel=1e-4)


def test_sharpe_diff_test_planted_and_null():
    rng = np.random.default_rng(0)
    b = rng.standard_normal(1500)
    a = 0.25 + rng.standard_normal(1500)
    t = c.sharpe_diff_test(a, b, 10, 400, 0)
    assert t["diff"] > 0.15 and t["p_gt0"] < 0.01 and t["ci"][0] > 0
    t0 = c.sharpe_diff_test(rng.standard_normal(1500), rng.standard_normal(1500), 10, 400, 0)
    assert t0["p_gt0"] > 0.05


def test_cluster_and_diff_bootstraps():
    assert c.cluster_share_upper([0, 0, 0], [100, 100, 100], n_boot=200) == 0.0
    up = c.cluster_share_upper([10, 0, 0, 0], [100, 100, 100, 100], n_boot=400)
    assert up > 0.025
    d = c.diff_share_ci([True] * 95 + [False] * 5, [False] * 18 + [True] * 2, n_boot=400)
    assert d["diff"] == pytest.approx(0.85) and d["ci"][0] > 0.6
    rows = [{"expiry": f"e{i % 5}", "met": i % 2 == 0, "at": i % 2 == 0} for i in range(200)]
    cl = c.diff_share_cluster_ci(rows, n_boot=300)
    assert cl["ci"][0] == pytest.approx(1.0)


def test_decisions_robust_all_days_and_rule5():
    assert c._robust([True, True]) is True and c._robust([False, False]) is False
    assert c._robust([True, False]) is None and c._robust([]) is None
    assert c._all_ok([True, False, None]) is False and c._all_ok([True, None]) is None and c._all_ok([True]) is True
    assert c._days_share([True, True], 0.8, 5) is None            # 2 of 5 days: undecided
    assert c._days_share([False, False], 0.8, 5) is False         # fails whatever 3 more days show
    assert c._days_share([True] * 4 + [False], 0.8, 5) is True
    t = c.share_test(0, 4, 0.8, "ge", min_n=20)
    assert t["pass"] is False and t["decisive"] is True           # upper bound 52.7% < 80%
    t = c.share_test(3, 4, 0.8, "ge", min_n=20)
    assert t["pass"] is False and t["decisive"] is False
    t = c.share_test(0, 5000, 0.001, "lt")
    assert t["pass"] is True
    t = c.share_test(60, 5000, 0.001, "lt")
    assert t["pass"] is False and t["decisive"] is True
    v, why = c._decide([("x", False, False)], 10, 100, "u")
    assert v == "inconclusive" and "not decisively" in why
    v, _ = c._decide([("x", False, True)], 10, 100, "u")
    assert v == "not_supported"


# ===================================================================================================== rates ==

def test_rates_and_bill_variants():
    assert c.dtb3_continuous(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    assert c.bey_continuous(4.26) == pytest.approx(math.log(1 + 0.0426 * 91 / 365) / (91 / 365))
    dtb3 = {"2026-10-09": 4.06, "2026-10-13": 4.09}
    v = c.bill_variants(dtb3, {}, "2026-10-13")
    assert [lab.split()[0] for lab, _ in v] == ["DTB3", "DGS3MO"] and "2026-10-09" in v[0][0]
    assert v[1][1] > v[0][1]
    assert len(c.bill_variants({"2026-01-02": 4.0}, {}, "2026-01-05")) == 1      # no reference print for that date
    v = c.bill_variants(dtb3, {"2026-10-09": 4.3}, "2026-10-13")
    assert v[1][0] == "DGS3MO 2026-10-09"


def test_dividend_schedule_and_pv():
    assert c.spy_ex_date(2026, 12) == date(2026, 12, 18)
    assert c.spy_ex_date(2027, 6) == date(2027, 6, 17)             # Juneteenth observed on the third Friday
    assert c.ex_dates_between("2026-11-13", "2026-12-18") == [date(2026, 12, 18)]
    assert c.ex_dates_between("2026-10-13", "2026-11-30") == []
    pv = c.pv_div("2026-10-13", "2026-11-13", "2026-12-18", 2.0, 0.04)
    assert pv == pytest.approx(2.0 * math.exp(-0.04 * 66 / 365))
    t4 = c.trailing_four([("2025-12-19", 1.99), ("2026-03-20", 1.8), ("2026-06-18", 1.9), ("2026-09-18", 1.89)], "2026-10-13")
    assert t4 == {12: 1.99, 3: 1.8, 6: 1.9, 9: 1.89}
    assert c.pv_div("2026-10-13", "2026-10-13", "2027-03-31", t4, 0.0) == pytest.approx(1.99 + 1.8)
    close = np.array([100.0, 100.0, 98.0])
    adj = np.array([98.0, 98.0, 98.0])                             # a 2.0 dividend going ex on day 2
    assert c.dividends(close, adj)[2] == pytest.approx(2.0, rel=1e-6)


def test_sync_spot_and_capture_meta():
    by = _by(100.0, "2026-01-05", [3, 7, 30], np.arange(95, 106, 1.0), R)
    si = c.sync_spot(by, 100.6, "2026-01-05", R)                   # a stale close 0.6 away from the quotes' spot
    assert si["spot"] == pytest.approx(100.0, abs=1e-6) and si["offset_bp"] < -50
    days = ["2026-01-02", "2026-01-05", "2026-01-06"]
    assert c._capture_meta([{"observed_at": "2026-01-06 11:08:23"}], days) == ("2026-01-05", "")
    qd, why = c._capture_meta([{"observed_at": "2026-01-06 15:08:23"}], days)
    assert qd is None and "intraday" in why


# ============================================================================================ T-153 jelly roll ==

def _roll_by(r_opt, quote_day="2026-01-05"):
    return _by(100.0, quote_day, [7, 30, 60, 90], np.arange(95, 105.5, 0.5), r_opt, hs=0.005)


def test_jelly_roll_day_planted_and_null():
    by = _roll_by(R)
    pair = c.jelly_pair(by, "2026-01-05")
    assert [c._dte(e, "2026-01-05") for e in pair] == [30, 60]
    res = c.jelly_roll_day(by, 100.0, "2026-01-05", R, None, *pair)
    assert res["n"] >= 15 and res["share"] == 1.0 and abs(res["median_dev"]) < 1e-5
    res0 = c.jelly_roll_day(_roll_by(R + 0.02), 100.0, "2026-01-05", R, None, *pair)
    assert res0["n"] == res["n"] and res0["share"] == 0.0 and res0["median_dev"] > 0.1       # option financing above the bill: the roll is rich
    # a dividend inside (T1, T2] enters the fair value one for one
    resd = c.jelly_roll_day(by, 100.0, "2026-02-17", R, 1.0, "2026-03-13", "2026-04-17")
    assert resd["ex_dates"] == ["2026-03-20"] and resd["pv_div"] == pytest.approx(math.exp(-R * 31 / 365))


def _jdays(res, k=1):
    return [{"quote_day": f"2026-01-{5 + i:02d}", "capture": "x", "primary": {"DTB3": res}, "alt": None, "spx": None} for i in range(k)]


def test_jelly_roll_claim_planted_and_null():
    by = _roll_by(R)
    pair = c.jelly_pair(by, "2026-01-05")
    good = c.jelly_roll_day(by, 100.0, "2026-01-05", R, None, *pair)
    rep = c.jelly_roll_claim(_jdays(good, 2))
    assert rep["verdict"] == "inconclusive" and "confirmation at 60" in rep["reason"]
    rep = c.jelly_roll_claim(_jdays(good, 60), min_n=200)
    assert rep["verdict"] == "supported", rep["reason"]
    json.dumps(c._clean(rep["stat"]))
    bad = c.jelly_roll_day(_roll_by(R + 0.02), 100.0, "2026-01-05", R, None, *pair)
    rep0 = c.jelly_roll_claim(_jdays(good, 1) + _jdays(bad, 1))
    assert rep0["verdict"] == "not_supported" and rep0["reason"].endswith(")") and " — failed" in rep0["reason"]


# ======================================================================== T-182 / T-185 / T-507 / T-184 rates ==

QD = "2026-01-05"
K_GRID = np.arange(94, 106.01, 0.25)
DTES = [3, 7, 35, 42, 49, 56]


def _rate_days(fn, r_opt, n_days=1, extra=None):
    days = []
    for i in range(n_days):
        qd = (date.fromisoformat(QD) + timedelta(days=i)).isoformat()
        by = _by(100.0, qd, DTES, K_GRID, r_opt)
        rows = fn(by, 100.0, qd, R)
        d = {"quote_day": qd, "variants": {"close/DTB3": {"rows": rows, "r_bill": R}}, "sync": None}
        if extra:
            d.update(extra)
        days.append(d)
    return days


def test_conversion_planted_and_null():
    fn = lambda by, S, qd, r: c.conversion_pairs(by, S, qd)[0]
    days = _rate_days(fn, R - 0.01, 5)
    assert all(x["r_exec"] < R for x in days[0]["variants"]["close/DTB3"]["rows"])
    rep = c.conversion_claim(days)
    assert rep["verdict"] == "supported" and rep["n"] >= 100, rep["reason"]
    rep1 = c.conversion_claim(days[:1])
    assert rep1["verdict"] == "inconclusive"                        # 1 day cannot show 80% of captured days
    rep0 = c.conversion_claim(_rate_days(fn, R + 0.01, 1))
    assert rep0["verdict"] == "not_supported" and " — failed" in rep0["reason"]


def test_conversion_deep_itm_call_dropped():
    by = _by(100.0, QD, [35], [96.0, 100.0], R, sigma=0.08)
    rows, dropped = c.conversion_pairs(by, 100.0, QD)
    deep = {x["K"]: x["deep_itm_call"] for x in rows}
    assert deep[96.0] is True and deep[100.0] is False


def test_synthetic_short_planted_and_null():
    fn = lambda by, S, qd, r: c.synthetic_short_pairs(by, S, qd, r)
    days = _rate_days(fn, R, 5)
    b = [x["borrow"] * 1e4 for x in days[0]["variants"]["close/DTB3"]["rows"]]
    assert 0 < np.median(b) < 30                                    # only the spread cost: 0.02 / (K T)
    rep = c.synthetic_short_claim(days)
    assert rep["verdict"] == "supported", rep["reason"]
    rep0 = c.synthetic_short_claim(_rate_days(fn, R - 0.02, 1))
    assert rep0["verdict"] == "not_supported"


def test_synthetic_call_planted_and_null():
    fn = lambda by, S, qd, r: c.synthetic_call_rows(by, S, qd, r)
    rep = c.synthetic_call_claim(_rate_days(fn, R + 0.01, 5))
    assert rep["verdict"] == "supported", rep["reason"]
    rep0 = c.synthetic_call_claim(_rate_days(fn, R - 0.01, 1))
    assert rep0["verdict"] == "not_supported"


def test_synthetic_long_planted_and_null():
    dtes = [200, 250, 300, 350]

    def days_for(r_opt, n):
        out = []
        for i in range(n):
            qd = (date.fromisoformat(QD) + timedelta(days=i)).isoformat()
            by = _by(100.0, qd, dtes, [99.0, 100.0, 101.0], r_opt, hs=0.01)
            rows = c.synthetic_long_expiries(by, 100.0, qd, R, None)
            out.append({"quote_day": qd, "variants": {"close/DTB3": {"rows": rows}}})
        return out
    rows = days_for(R + 0.002, 1)[0]["variants"]["close/DTB3"]["rows"]
    assert len(rows) == 4 and all(15 < x["gap_bp"] < 30 for x in rows)
    rep = c.synthetic_long_claim(days_for(R + 0.002, 5))
    assert rep["verdict"] == "supported" and rep["n"] == 20, rep["reason"]
    rep_short = c.synthetic_long_claim(days_for(R + 0.002, 2))
    assert rep_short["verdict"] == "inconclusive"                   # 8 of 20 expiry observations
    rep0 = c.synthetic_long_claim(days_for(R + 0.015, 1))
    assert rep0["verdict"] == "not_supported"                       # 0/4 on day one: decisive below min_n


def test_synthetic_long_dividends_lower_the_rate():
    by = _by(100.0, "2026-10-13", [250], [100.0], R)
    a = c.synthetic_long_expiries(by, 100.0, "2026-10-13", R, None)[0]
    b = c.synthetic_long_expiries(by, 100.0, "2026-10-13", R, {12: 0.5, 3: 0.5, 6: 0.5, 9: 0.5})[0]
    assert b["pv_div"] > 1.4 and b["r_impl"] > a["r_impl"]          # a chain priced without dividends: PV(D) raises r


# ============================================================================================ T-191 ITM puts ==

def _put_chain(pin_met=True):
    """Deep ITM puts (spot 100, K 111-120): short expiries quoted at intrinsic (criterion met: interest > tiny call),
    a long expiry with a rich call (criterion failed) quoted well above intrinsic."""
    vals = []
    qd = date.fromisoformat(QD)
    for dte, call_mid, put_over in ((5, 0.01, 0.0), (12, 0.01, 0.0), (19, 0.01, 0.0), (700, 15.0, 3.0)):
        e = (qd + timedelta(days=dte)).isoformat()
        for K in np.arange(111, 121, 1.0):
            over = put_over if (pin_met or dte == 700) else 2.0
            pm = (K - 100.0) + over
            vals.append({"sym": _sym("SPY", e, "put", K), "expiry": e, "type": "put", "strike": K, "bid": pm - 0.05, "ask": pm + 0.05})
            vals.append({"sym": _sym("SPY", e, "call", K), "expiry": e, "type": "call", "strike": K, "bid": max(call_mid - 0.01, 0.0),
                         "ask": call_mid + 0.01})
    return c.chain_by_root(vals)


def test_itm_put_rows_classify():
    rows, dropped = c.itm_put_rows(_put_chain(), 100.0, QD, R, None)
    met = [x for x in rows if x["met"]]
    fail = [x for x in rows if not x["met"]]
    assert len(met) == 30 and len(fail) == 10
    assert all(x["at"] for x in met) and not any(x["at"] for x in fail)


def _ee_days(by, k=1):
    out = []
    for i in range(k):
        rows, _ = c.itm_put_rows(by, 100.0, QD, R, None)
        ci = c.diff_share_ci([x["at"] for x in rows if x["met"]], [x["at"] for x in rows if not x["met"]], n_boot=300)
        out.append({"quote_day": f"2026-01-{5 + i:02d}", "variants": {"close/DTB3": {"rows": rows, "ci": ci, "cluster": c.diff_share_cluster_ci(rows, n_boot=200)}}})
    return out


def test_early_exercise_claim_planted_and_null():
    rep = c.early_exercise_claim(_ee_days(_put_chain(), 1), min_n=20)
    assert rep["verdict"] == "inconclusive" and "stable over 20" in rep["reason"]
    rep = c.early_exercise_claim(_ee_days(_put_chain(), 20), min_n=20)
    assert rep["verdict"] == "supported", rep["reason"]
    rep0 = c.early_exercise_claim(_ee_days(_put_chain(pin_met=False), 1), min_n=20)
    assert rep0["verdict"] == "not_supported"


# ============================================================================================ T-500 butterflies ==

def _fly_by(spot, root, perturb=False, qd=QD, step=400):
    vals = chain_values(spot, qd, [10, 30, 60, 90, 180], np.arange(0.85 * spot, 1.15 * spot + 1e-9, spot / step), R, root=root, hs=0.001 * spot / 100)
    if perturb:                                                     # every 10th call strike: body bid lifted above the wings
        ks = sorted({v["strike"] for v in vals})
        bump = set(ks[5::10])
        for v in vals:
            if v["type"] == "call" and v["strike"] in bump:
                v["bid"] += 0.5 * spot / 100
                v["ask"] += 0.5 * spot / 100
    return c.chain_by_root(vals)


def _fly_days(perturb, n, step=400):
    out = []
    for i in range(n):
        qd = (date.fromisoformat(QD) + timedelta(days=i)).isoformat()
        out.append({"quote_day": qd, "scans": {"SPX": c.butterfly_scan(_fly_by(5000.0, "SPXW", perturb, qd, step), 5000.0, qd),
                                               "SPY": c.butterfly_scan(_fly_by(500.0, "SPY", False, qd, step), 500.0, qd)}})
    return out


def test_butterfly_planted_and_null():
    days = _fly_days(False, 5)
    assert days[0]["scans"]["SPX"]["k"] == 0 and days[0]["scans"]["SPX"]["n"] > 1000
    rep = c.butterfly_claim(days, min_n=1000)
    assert rep["verdict"] == "supported", rep["reason"]
    assert c.butterfly_claim(days[:2], min_n=1000)["verdict"] == "inconclusive"
    small = c.butterfly_claim(_fly_days(False, 5, step=100), min_n=1000)   # zero credits, too few to bound below 0.5%
    assert small["verdict"] == "inconclusive" and "not decisively" in small["reason"]
    bad = _fly_days(True, 1)
    assert bad[0]["scans"]["SPX"]["k"] / bad[0]["scans"]["SPX"]["n"] > 0.02
    rep0 = c.butterfly_claim(bad, min_n=1000)
    assert rep0["verdict"] == "not_supported" and "day one SPX" in rep0["reason"]


# ============================================================================================== T-501 calendars ==

def test_calendar_planted_and_null():
    by = _by(100.0, QD, [7, 14, 30, 60, 90], np.arange(85, 116, 1.0), 0.0)     # r = 0: European puts rise with T too
    sc = c.calendar_scan(by, 100.0, QD)
    assert sc["k"] == 0 and sc["n"] > 150
    days = [{"quote_day": f"2026-01-{5 + i:02d}", "scan": sc} for i in range(5)]
    assert c.calendar_claim(days, min_n=150)["verdict"] == "supported"
    # far expiries at a fraction of the near vol: far options cheaper than near ones
    by0 = _by(100.0, QD, [7, 14, 30, 60, 90], np.arange(85, 116, 1.0), 0.0, sig_by_dte={7: 0.8, 14: 0.1, 30: 0.8, 60: 0.1, 90: 0.8})
    sc0 = c.calendar_scan(by0, 100.0, QD)
    assert sc0["k"] / sc0["n"] > 0.05
    assert c.calendar_claim([{"quote_day": QD, "scan": sc0}], min_n=150)["verdict"] == "not_supported"


def test_total_variance_scan_flat_vol_has_no_violations():
    by = _by(5000.0, QD, [10, 30, 60], np.arange(4500, 5501, 25.0), R, root="SPXW", hs=0.5)
    tv = c.total_variance_scan(by, 5000.0, QD)
    assert tv["n"] > 20 and tv["k"] == 0


# ============================================================================================== T-508 verticals ==

def _vert_scans(perturb=False):
    out = {}
    for s, spot in (("SPY", 100.0), ("SPX", 5000.0), ("QQQ", 400.0), ("GLD", 200.0), ("IBIT", 50.0)):
        vals = chain_values(spot, QD, [10, 30, 90], np.linspace(0.8 * spot, 1.2 * spot, 81), R, root="SPXW" if s == "SPX" else s,
                            hs=0.0005 * spot)
        if perturb and s == "GLD":                                 # every 5th call strike priced above its lower neighbour
            ks = sorted({v["strike"] for v in vals})
            bump = set(ks[3::5])
            for v in vals:
                if v["type"] == "call" and v["strike"] in bump:
                    v["bid"] += 0.05 * spot
                    v["ask"] += 0.05 * spot
        out[s] = c.vertical_scan(c.chain_by_root(vals), QD, R, european=(s == "SPX"))
    return out


def test_vertical_planted_and_null():
    good = _vert_scans()
    assert all(v["k"] == 0 for v in good.values()) and sum(v["n"] for v in good.values()) > 1000
    days = [{"quote_day": f"2026-01-{5 + i:02d}", "scans": {"DTB3": good}} for i in range(5)]
    assert c.vertical_claim(days, min_n=1000)["verdict"] == "supported"
    bad = _vert_scans(perturb=True)
    assert bad["GLD"]["mono"] > 0
    rep0 = c.vertical_claim([{"quote_day": QD, "scans": {"DTB3": bad}}], min_n=1000)
    assert rep0["verdict"] == "not_supported" and "GLD" in rep0["reason"]


def test_vertical_width_bound_discounting():
    # a European call spread bid exactly at the undiscounted width violates the discounted bound only
    by = c.chain_by_root([{"sym": _sym("SPXW", "2026-07-05", "call", 100), "expiry": "2026-07-05", "type": "call", "strike": 100.0, "bid": 19.97, "ask": 20.1},
                          {"sym": _sym("SPXW", "2026-07-05", "call", 105), "expiry": "2026-07-05", "type": "call", "strike": 105.0, "bid": 14.9, "ask": 14.99}])
    assert c.vertical_scan(by, QD, 0.05, european=True)["width"] == 1
    assert c.vertical_scan(by, QD, 0.05, european=False)["width"] == 0


# ======================================================================================= T-103 strangle model ==

def _smile_rows(r_put=1.1, r_atm=0.8, r_call=0.65):
    ratio = {f"{m:.2f}": float(np.interp(m, [0.9, 1.0, 1.1], [r_put + 0.2, r_atm, r_call])) for m in np.arange(0.85, 1.16, 0.01)}
    ratio["0.95"], ratio["1.00"], ratio["1.05"] = r_put, r_atm, r_call
    return [{"value": {"quote_date": "2026-10-13", "expiry": "2026-11-13", "dte": 31, "target_dte": 30, "index_level": 15.0, "ratio": ratio}},
            {"value": {"quote_date": "2026-10-13", "expiry": "2026-11-27", "dte": 45, "target_dte": 45, "index_level": 15.0, "ratio": ratio}}]


def test_strangle_panel_and_returns_in_a_flat_market():
    days = _bdays("2020-01-02", 300)
    close = np.full(300, 100.0)
    panel = c.strangle_panel(days, close, close, {d: 20.0 for d in days}, {d: 2.0 for d in days}, start="2020-01-03")
    assert panel["idx"].size == 300 - 21 - 1 and np.all(panel["pvd"] == 0)
    sm = c.Smile(_smile_rows())
    rat = c.leg_ratios(panel, "smile", sm)
    assert rat["put"][0] == pytest.approx(1.1) and rat["call"][0] == pytest.approx(0.65) and rat["atm"][0] == pytest.approx(0.8)
    x = c.structure_returns(panel, rat)
    i = 0
    T, r = panel["T"][i], panel["r"][i]
    prem = float(bs.price(100, 100, T, r, 0.8 * 0.2, "put") + bs.price(100, 100, T, r, 0.8 * 0.2, "call"))
    assert x["straddle"][i] == pytest.approx(prem * 0.95 * math.exp(r * T) / 100)         # no move: keep the haircut premium
    assert np.all(x["strangle"] > 0)
    fl = c.leg_ratios(panel, "flat")
    assert np.all(fl["put"] == 1)
    sk = c.leg_ratios(panel, "skew", sm, {d: 130.0 for d in days}, 130.0)
    assert sk["put"][0] == pytest.approx(1.1)
    sk100 = c.leg_ratios(panel, "skew", sm, {d: 100.0 for d in days}, 130.0)
    assert sk100["put"][0] == pytest.approx(0.8) and sk100["call"][0] == pytest.approx(0.8)


def test_strangle_panel_prices_on_the_dividend_forward():
    days = _bdays("2026-02-02", 120)
    close = np.full(120, 100.0)
    adj = close.copy()
    j = days.index("2026-03-20")
    adj[:j] = 99.0                                                  # a 1.0 dividend went ex on 2026-03-20
    panel = c.strangle_panel(days, close, adj, {d: 20.0 for d in days}, {d: 2.0 for d in days}, start="2026-03-02")
    exs = c.projected_ex_sessions(days)
    seen_div = seen_none = False
    for k, i in enumerate(panel["idx"]):
        d0, d1 = days[i], days[i + 21]
        inside = [x for x in exs if d0 < x <= d1]
        amt = 1.0 if d0 >= "2026-03-20" else 0.0                     # forecast = the last dividend gone ex by the entry
        want = sum(amt * math.exp(-panel["r"][k] * (date.fromisoformat(x) - date.fromisoformat(d0)).days / 365) for x in inside)
        assert panel["pvd"][k] == pytest.approx(want)
        seen_div |= want > 0
        seen_none |= bool(inside) and amt == 0                     # an ex-date ahead before any dividend is known: none priced
    assert seen_div and seen_none


def _fake_panel(n):
    days = _bdays("1993-02-01", n + 30)
    return {"idx": np.arange(n), "hold": 21, "entry_days": days[:n]}


def _runs(a, b):
    r = {"strangle": a, "straddle": b, "prem_strangle": np.full(a.size, 0.01), "prem_straddle": np.full(a.size, 0.02)}
    return {"smile": r, "flat": r, "skew": r, "iv0.9": r, "iv1.1": r}


def test_strangle_vs_straddle_planted_null_and_proxy_cap():
    rng = np.random.default_rng(3)
    n = 21 * 400
    b = 0.02 * rng.standard_normal(n)
    a = 0.004 + 0.01 * rng.standard_normal(n)
    rep = c.strangle_vs_straddle(_fake_panel(n), _runs(a, b), 60, n_boot=300, seeds=(0,), blocks=(42,))
    assert rep["verdict"] == "supported" and rep["n"] == 400, rep["reason"]
    assert c.MP in rep["reason"] and rep["reason"].count(" — ") == 1
    capped = c.strangle_vs_straddle(_fake_panel(n), _runs(a, b), 2, n_boot=300, seeds=(0,), blocks=(42,))
    assert capped["verdict"] == "inconclusive" and "proxy cap" in capped["reason"]
    a0 = 0.02 * rng.standard_normal(n)
    rep0 = c.strangle_vs_straddle(_fake_panel(n), _runs(a0, b), 60, n_boot=300, seeds=(0,), blocks=(42,))
    assert rep0["verdict"] == "not_supported"
    json.dumps(c._clean(rep0["stat"]))


# ======================================================================================== harness wiring ==

def test_maps_and_names():
    assert set(c.THEORY_MAP) == {"T-153", "T-182", "T-184", "T-185", "T-191", "T-500", "T-501", "T-507", "T-508", "T-103"}
    assert set(c.THEORY_MAP.values()) == set(c.HARNESSES)
    assert all(k.startswith("b6b_chain_") and k == k.lower() for k in c.HARNESSES)


@pytest.mark.parametrize("name", sorted(c.HARNESSES))
def test_harness_missing_bundles_is_inconclusive(name):
    stat, n, v, reason = c.HARNESSES[name](FakeArchive({}))
    assert v == "inconclusive" and n == 0 and stat["missing_bundles"] and "missing data bundles" in reason


def _spy_world(qdays, r_opt, extra_days=5):
    """A SPY history through the quote days (flat at 100), DTB3 at 4%, and one pre-open chain capture per quote day."""
    days = _bdays("2025-10-01", 80 + extra_days)
    days = sorted(set(days) | set(qdays))
    b = {c.SPY_B: _px_rows(days, [100.0] * len(days)), c.DTB3_B: _fred_rows(days, 4.0)}
    for qd in qdays:
        cap = days[days.index(qd) + 1]
        vals = chain_values(100.0, qd, DTES, K_GRID, r_opt)
        b[f"{c.CHAIN_P}SPY-{cap}"] = [{"observed_at": f"{cap} 11:08:23", "available_at": f"{cap}T11:12:25+00:00", "value": v} for v in vals]
    return b


def test_harness_conversion_end_to_end_planted_and_null():
    qdays = _bdays("2026-01-05", 5)
    stat, n, v, reason = c.HARNESSES["b6b_chain_conversion"](FakeArchive(_spy_world(qdays, R - 0.01)))
    json.dumps(stat)
    assert v == "supported" and n >= 100, reason
    assert "close/DTB3" in reason and "sync/DTB3" in reason and reason.count(" — ") == 1
    stat, n, v, reason = c.HARNESSES["b6b_chain_conversion"](FakeArchive(_spy_world(qdays[:1], R + 0.01)))
    assert v == "not_supported", reason


def test_harness_jelly_roll_end_to_end_null():
    qd = "2026-01-05"
    w = _spy_world([qd], R + 0.02)
    cap = "2026-01-06"
    vals = chain_values(100.0, qd, [7, 30, 60, 90], np.arange(95, 105.5, 0.5), R + 0.02, hs=0.005)
    w[f"{c.CHAIN_P}SPY-{cap}"] = [{"observed_at": f"{cap} 11:08:23", "available_at": f"{cap}T11:12:25+00:00", "value": v} for v in vals]
    stat, n, v, reason = c.HARNESSES["b6b_chain_jelly_roll"](FakeArchive(w))
    json.dumps(stat)
    assert v == "not_supported" and n > 0, reason


def test_harness_vertical_needs_every_chain():
    w = _spy_world(["2026-01-05"], R)
    stat, n, v, reason = c.HARNESSES["b6b_chain_vertical_bounds"](FakeArchive(w))
    assert v == "inconclusive" and any("QQQ" in m for m in stat["missing_bundles"])


def test_harness_intraday_capture_skipped():
    w = _spy_world(["2026-01-05"], R - 0.01)
    name = next(k for k in w if k.startswith(c.CHAIN_P))
    w[name] = [dict(r, observed_at=r["observed_at"].replace("11:08:23", "15:00:00")) for r in w[name]]
    stat, n, v, reason = c.HARNESSES["b6b_chain_conversion"](FakeArchive(w))
    assert v == "inconclusive" and "intraday" in reason and reason.endswith(" — no data")


def test_harness_strangle_end_to_end_small_sample():
    rng = np.random.default_rng(7)
    days = _bdays("2018-01-02", 800)
    ret = 0.0003 + 0.009 * rng.standard_normal(len(days))
    spy = 100 * np.exp(np.cumsum(ret))
    vix = np.full(len(days), 16.0)
    b = {c.SPY_B: _px_rows(days, spy), c.VIX_B: _idx_rows(days, vix), c.DTB3_B: _fred_rows(days, 2.0),
         c.SKEW_B: _idx_rows(days + ["2026-10-13"], np.full(len(days) + 1, 130.0)),
         "spy-smile-2026-10-13": _smile_rows()}
    stat, n, v, reason = c.HARNESSES["b6b_chain_strangle_vs_straddle"](FakeArchive(b))
    json.dumps(stat)
    assert v in ("inconclusive", "not_supported") and 0 < n < c.T103_MIN_N and c.MP in reason
    assert stat["sensitivities"]["skew"] is not None and stat["sensitivities"]["flat"] is not None
