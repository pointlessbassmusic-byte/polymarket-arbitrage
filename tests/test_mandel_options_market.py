"""Options-library harnesses on synthetic inputs: exact binomial CI, boxes and parity on a chain priced at a known rate,
pinning with a planted effect, forward premium with known implied > realised."""

import math
from datetime import date, timedelta

import numpy as np

from mandel.experiments import options_market as om
from mandel.options import bs


def _days(n, start="2008-01-02"):
    d = date.fromisoformat(start); out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _idx(days, vals):
    return [{"value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _px(days, closes, sym="SPY"):
    import datetime as dt
    return [{"value": {"symbol": sym, "t": dt.datetime.fromisoformat(d + "T20:00:00+00:00").timestamp(), "close": float(c)}} for d, c in zip(days, closes)]


def test_binomial_ci_and_sign_test():
    lo, hi = om._binom_two_sided_ci(7, 10)
    assert abs(lo - 0.3475) < 1e-3 and abs(hi - 0.9333) < 1e-3
    assert om._binom_two_sided_ci(0, 10)[0] == 0.0 and om._binom_two_sided_ci(10, 10)[1] == 1.0
    assert abs(om._sign_test_p(9, 10) - 11 / 1024) < 1e-12


def _dtb3_for(rc):
    """DTB3 discount-basis quote (%) whose continuous 91-day rate is rc (inverse of om._dtb3_cont)."""
    return (1 - math.exp(-rc * 91 / 365)) * 360 / 91 * 100


def _dgs2_for(rc):
    """DGS2 bond-equivalent quote (%) whose continuous rate is rc (inverse of om._semiannual_cont)."""
    return 200 * (math.exp(rc / 2) - 1)


def _chain(spot, day, r, sigma, half_spread, expiries_dte, strikes):
    rows = []
    cap = date.fromisoformat(day)
    for dte in expiries_dte:
        exp = (cap + timedelta(days=dte)).isoformat(); T = dte / 365
        for k in strikes:
            for kind in ("call", "put"):
                mid = float(bs.price(spot, k, T, r, sigma, kind))
                rows.append({"value": {"expiry": exp, "type": kind, "strike": float(k), "bid": max(mid - half_spread, 0.01), "ask": mid + half_spread}})
    return rows


def test_boxes_recover_the_pricing_rate():
    day = "2026-10-14"; spot = 5000.0; r = 0.045
    rows = _chain(spot, day, r, 0.2, 0.0, [120, 240], range(4300, 5701, 100))
    rb = math.log(1.04)                                   # bills dated the session before the capture (no same-day look-ahead), flat curve at rb
    dtb3 = [{"value": {"day": "2026-10-13", "value": _dtb3_for(rb)}}]; dgs2 = [{"value": {"day": "2026-10-13", "value": _dgs2_for(rb)}}]
    bx = om.box_rates(rows, spot, day, dtb3, dgs2, (90, 365))
    assert bx and all(abs(b["r_mid"] - r) < 1e-6 and abs(b["r_lend"] - r) < 1e-6 for b in bx)
    wide = om.box_rates(_chain(spot, day, r, 0.2, 0.5, [120], range(4300, 5701, 100)), spot, day, dtb3, dgs2, (90, 365))
    assert all(b["r_lend"] < r < b["r_borrow"] for b in wide)            # paying spreads lowers the lending rate, raises borrowing
    rep = om.box_lending([(day, spot, rows)], dtb3, dgs2)
    spread_bp = (r - rb) * 1e4
    assert abs(rep["days"][0]["median_spread_bp"] - spread_bp) < 1 and rep["verdict"] in ("inconclusive", "not_supported")


def test_parity_on_a_clean_european_chain():
    day = "2026-10-14"; spot = 100.0; r = math.log(1.04)
    rows = _chain(spot, day, r, 0.25, 0.05, [45, 90], np.arange(80, 121, 1.0))
    rep = om.parity_check([(day, "XYZ", spot, rows)], [{"value": {"day": "2026-10-13", "value": _dtb3_for(r)}}])
    d = rep["per_day"][0]
    assert d["violation_rate"] == 0.0 and abs(d["median_rate_gap_bp"]) < 1 and rep["verdict"] == "inconclusive"


def test_pinning_planted_and_null():
    rng = np.random.default_rng(0)
    days = [d for d in _days(5000, "2005-01-03")]
    closes = 100 + rng.uniform(0, 1, len(days)) + np.arange(len(days)) * 0.05
    rep0 = om.expiry_pinning(_px(days, closes), n_boot=500)
    assert rep0["verdict"] == "not_supported"
    opex = {om._third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in days}
    pinned = np.array([round(c) + rng.uniform(-0.05, 0.05) if d in opex else c for d, c in zip(days, closes)])
    rep1 = om.expiry_pinning(_px(days, pinned), n_boot=500)
    assert rep1["verdict"] == "supported" and rep1["ratio"] < 0.5


def test_forward_premium_detects_rich_implied():
    rng = np.random.default_rng(1)
    n = 3000; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.15 / math.sqrt(252), n)))
    rep = om.forward_variance_premium(_idx(days, np.full(n, 20.0)), _idx(days, np.full(n, 21.0)), _px(days, closes))
    assert rep["verdict"] == "supported" and rep["mean_gap_vol_pts"] > 4
    fair = om.forward_variance_premium(_idx(days, np.full(n, 15.0)), _idx(days, np.full(n, 15.0)), _px(days, closes))
    assert fair["verdict"] == "not_supported"


def test_v2_boxes_parity_and_forward_adjustment():
    day = "2026-10-14"; spot = 5000.0; r = 0.045
    rows = _chain(spot, day, r, 0.2, 0.0, [90, 300], range(4300, 5701, 100))
    for row in rows:                                    # give rows an OCC-like symbol so roots split
        row["value"]["sym"] = "SPXW" + row["value"]["expiry"].replace("-", "")[2:] + ("C" if row["value"]["type"] == "call" else "P")
    dtb3 = [{"value": {"day": "2026-10-13", "value": _dtb3_for(r)}}]
    mid = om.box_mid_v2([(day, spot, rows)], dtb3)
    assert abs(mid["days"][0]["median_bp"]) < 1 and mid["verdict"] == "not_supported"     # 0 bp spread is outside [15, 80]
    rows_sp = _chain(spot, day, r, 0.2, 0.05, [90, 300], range(4300, 5701, 100))
    for row in rows_sp:
        row["value"]["sym"] = "SPXW" + row["value"]["expiry"].replace("-", "")[2:]
    par = om.parity_v2([(day, spot, rows_sp)], dtb3)
    assert par["days"][0]["share"] == 0.0 and par["verdict"] == "inconclusive"
    days = _days(400)
    vix = _idx(days, np.full(400, 15.0)); v3 = _idx(days, np.full(400, 18.0)); vv = _idx(days, np.full(400, 90.0))
    rep = om.contango_forward_v2(vix, v3, vv)
    assert rep["freq_adj"] == 1.0 and rep["mean_gap"] > 0          # flat VIX at 15, forward ~19.5 adjusted ~18.9 -> always below
