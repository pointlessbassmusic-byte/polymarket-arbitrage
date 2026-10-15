"""Batch 6a, group xc: crypto model-priced hedging and captured-chain arbitrage harnesses on synthetic data only (no
archive, no network). Each core function gets a planted effect that passes and a null that does not."""

import json
import math
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6_xc as x
from mandel.options import bs

NB = 400            # bootstrap draws in tests (the harnesses use 2,000 to 4,000)


# ===================================================================================================== fixtures ==

def _cal_days(start: str, n: int) -> list:
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def _gbm365(n: int, sigma, seed: int = 0, s0: float = 30000.0) -> np.ndarray:
    """Martingale GBM on calendar days (a 24/7 asset), annual vol sigma (scalar or per-day array)."""
    rng = np.random.default_rng(seed)
    sig = np.broadcast_to(np.asarray(sigma, dtype=float), (n,))[:-1]
    dt = 1.0 / 365.0
    lr = -0.5 * sig ** 2 * dt + sig * math.sqrt(dt) * rng.standard_normal(n - 1)
    return s0 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))


def _sym(root: str, expiry: str, kind: str, k: float) -> str:
    return f"{root}{expiry[2:4]}{expiry[5:7]}{expiry[8:10]}{'C' if kind == 'call' else 'P'}{int(round(k * 1000)):08d}"


def _chain(root: str, spot: float, quote_day: str, dtes, strikes, r: float, q: float, sigma: float = 0.2, half: float = 0.02,
           cp_shift: float = 0.0) -> list:
    """Compact CBOE-style option rows priced by European BS (r, q continuous), symmetric half-spread ``half``; cp_shift
    adds to every call mid and subtracts from every put mid (a parity violation of 2 * cp_shift)."""
    out = []
    q0 = date.fromisoformat(quote_day)
    K = np.asarray(strikes, dtype=float)
    for dte in dtes:
        e = (q0 + timedelta(days=int(dte))).isoformat()
        T = dte / 365.0
        for kind, sh in (("call", cp_shift), ("put", -cp_shift)):
            px = np.asarray(bs.price(spot, K, T, r, sigma, kind, q), dtype=float) + sh
            for k, p in zip(K, px):
                p = max(float(p), 2 * half + 0.01)
                out.append({"sym": _sym(root, e, kind, k), "expiry": e, "type": kind, "strike": float(k), "bid": round(p - half, 4),
                            "ask": round(p + half, 4)})
    return out


# =================================================================================================== statistics ==

def test_stud_ci_planted_and_null():
    rng = np.random.default_rng(1)
    lo, hi = x.stud_ci(0.4 + rng.standard_normal(300), 5, 0.95, NB)
    assert lo > 0
    lo, hi = x.stud_ci(rng.standard_normal(300), 5, 0.95, NB)
    assert lo < 0 < hi
    assert x.stud_ci(np.full(20, 2.0), 3, 0.95, NB) == (2.0, 2.0)
    assert x.stud_ci(np.array([1.0, 2.0]), 3) == (None, None)


def test_var_ratio_ci_planted_and_null():
    rng = np.random.default_rng(2)
    a = rng.standard_normal(200)
    planted = x.var_ratio_ci(0.4 * a + 0.1 * rng.standard_normal(200), a, 3, 0.95, NB)
    assert planted["hi"] < 0.8 and planted["ratio"] < 0.3
    null = x.var_ratio_ci(rng.standard_normal(200), rng.standard_normal(200), 3, 0.95, NB)
    assert null["lo"] < 1.0 < null["hi"] and not null["hi"] < 0.8
    assert x.var_ratio_ci(a[:5], a[:5], 2)["lo"] is None


def test_day_cluster_share_ci_planted_and_null():
    clean = [[False] * 200 for _ in range(6)]
    lo, hi = x.day_cluster_share_ci(clean, 0.95, NB)
    assert hi < 0.01
    dirty = [[True] * 10 + [False] * 190 for _ in range(6)]            # 5% flagged on every day
    lo, hi = x.day_cluster_share_ci(dirty, 0.95, NB)
    assert lo >= 0.01
    assert x.day_cluster_share_ci(clean[:2]) == (None, None)            # fewer than MIN_DAYS_SHARE days: no interval


def test_days_share_and_min_n_rules():
    assert x._days_share([True] * 20, 0.8, 20) is True
    assert x._days_share([True] * 15 + [False] * 5, 0.8, 20) is False   # 15/20 = 75%
    assert x._days_share([True, False], 0.8, 20) is None                # 19/20 still reachable
    assert x._days_share([False] * 5, 0.8, 20) is False                 # at best 15/20 = 75%
    assert x._days_share([False, False], 0.8, 5) is False               # at best 3/5
    assert x._days_share([True, True], 0.8, 5) is None                  # cannot confirm before 5 days
    assert x._share_fails_at_min_n(2, 4, 10, 0.9)                       # 2 misses: at best 8/10
    assert not x._share_fails_at_min_n(3, 4, 10, 0.9)                   # 1 miss: 9/10 still reachable
    v, why = x._decide([("c", False, False)], 5, 10, "u")
    assert v == "inconclusive" and "not decisively" in why
    v, _ = x._decide([("c", False, True)], 5, 10, "u")
    assert v == "not_supported"
    v, _ = x._decide([("c", True, False)], 10, 10, "u")
    assert v == "supported"
    v, _ = x._decide([("c", True, False)], 9, 10, "u")
    assert v == "inconclusive"


def test_days_share_judges_all_captured_days_regression():
    """Regression (T-199 _days_share): min_days is only the minimum before judging; once reached, the share runs over
    ALL captured days, so later days count (the old code kept only the first min_days)."""
    assert x._days_share([True] * 5 + [False] * 5, 0.8, 5) is False      # 50% of captured days (old code: True)
    assert x._days_share([False] * 2 + [True] * 8, 0.8, 5) is True       # 80% of captured days (old code: False)
    assert x._days_share([False, False], 0.8, 5) is False                # below 5 days: at best 3/5, decisive
    assert x._days_share([True, False], 0.8, 5) is None                  # 4/5 still reachable
    # unjudged days (None: the named input missing) count as unknown, never as passes or failures
    assert x._days_share([True] * 4 + [None], 0.8, 5) is True            # 4/5 even if the unjudged day failed
    assert x._days_share([True] * 3 + [None] * 2, 0.8, 5) is None        # 60% to 100% depending on the unjudged days
    assert x._days_share([True, False, False, None, None], 0.8, 5) is False   # at best 3/5
    assert x._days_share([True, None], 0.8, 5) is None


def test_spy_spx_financing_keeps_first_20_days_regression():
    """T-194's pass names '20 captured days': the harness slices the first 20 itself, so the all-days rule of
    _days_share leaves it unchanged (20 good days then 6 bad: 20/20, where all 26 days would give 77%)."""
    good = _t194_captures(20, 10)
    bad = _t194_captures(6, 10, spy_rate_shift=0.01, base="2026-08-23")
    rep = x.spy_spx_financing(good + bad)
    assert [d["pass"] for d in rep["stat"]["per_day"]] == [True] * 20 + [False] * 6
    assert rep["stat"]["days_criterion"] is True and rep["verdict"] == "supported", rep["reason"]


# ================================================================================================= SPY dividends ==

def test_dividends_and_ex_dates():
    close = np.array([100.0, 101.0, 99.0, 99.5])
    adj = close * np.array([0.98, 0.98, 1.0, 1.0])                     # ex on day 2: D = 101 * (1 - 0.98) = 2.02
    d = x.dividends(close, adj)
    assert d[2] == pytest.approx(2.02) and d[[0, 1, 3]].sum() == 0
    assert x.last_dividend(["a", "b", "c", "d"], close, adj, before="c") == pytest.approx(2.02)
    assert x.spy_ex_date(2026, 12) == date(2026, 12, 18)
    assert x.spy_ex_date(2026, 6) == date(2026, 6, 18)                  # Juneteenth Friday: ex on the Thursday
    assert x.spy_ex_date(2027, 6) == date(2027, 6, 17)                  # Juneteenth observed Friday 2027-06-18
    assert x.spy_ex_date(2027, 3) == date(2027, 3, 19)
    assert x.pv_dividends("2026-10-13", "2026-12-17", 1.9, 0.04) == 0.0
    pv = x.pv_dividends("2026-10-13", "2026-12-18", 1.9, 0.04)
    assert pv == pytest.approx(1.9 * math.exp(-0.04 * 66 / 365))


def test_dtb3_and_prior_print():
    assert x.dtb3_continuous(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    s = {"2026-10-08": 4.0, "2026-10-09": 4.1, "2026-10-13": 4.2}
    assert x.prior_print(s, "2026-10-13") == ("2026-10-09", 4.1)       # strictly before the quote day
    assert x.prior_print(s, "2026-10-08") is None


# ===================================================================================== T-255: hedged straddle ==

def _btc(n_days=1300, true_vol=0.45, iv_level=60.0, seed=0):
    days = _cal_days("2021-01-01", n_days)
    return days, _gbm365(n_days, true_vol, seed), np.full(n_days, iv_level)


def test_hedged_straddle_mechanics():
    days, close, iv = _btc(400, 0.5, 50.0)
    r = x.hedged_straddle(days, close, iv, start="2021-01-01", end="2021-12-31")
    assert r["x_gross"].size == 12 and (r["prem"] > 0).all()
    assert (r["net"] < r["gross"]).all()                                # fees are costs
    # a flat path: no hedge P&L, payoff 0, gross = premium
    flat = x.hedged_straddle(days, np.full(400, 100.0), iv, start="2021-01-01", end="2021-12-31")
    assert np.allclose(flat["x_gross"], 1.0)


def test_btc_vrp_straddle_planted_passes():
    days, close, iv = _btc(1300, 0.40, 60.0, seed=3)                   # implied 60 vs realised 40: rich premium
    rep = x.btc_vrp_straddle(days, close, iv, start="2021-01-01", end="2024-12-31", n_boot=NB)
    assert rep["n"] >= 36
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["stat"]["mean_gross"] > 0 and rep["stat"]["sharpe_net_annual"] > 0.5
    json.dumps(x._clean(rep["stat"]), allow_nan=False)


def test_btc_vrp_straddle_null_fails():
    days, close, iv = _btc(1300, 0.60, 60.0, seed=4)                   # implied = realised: no premium
    rep = x.btc_vrp_straddle(days, close, iv, start="2021-01-01", end="2024-12-31", n_boot=NB)
    assert rep["verdict"] != "supported", rep["reason"]
    days, close, iv = _btc(1300, 0.80, 60.0, seed=5)                   # implied below realised: losses
    rep = x.btc_vrp_straddle(days, close, iv, start="2021-01-01", end="2024-12-31", n_boot=NB)
    assert rep["verdict"] == "not_supported"


def test_btc_vrp_straddle_below_min_n_never_supported():
    days, close, iv = _btc(700, 0.40, 60.0, seed=6)
    rep = x.btc_vrp_straddle(days, close, iv, start="2021-01-01", end="2022-12-31", n_boot=NB)
    assert rep["n"] < 36 and rep["verdict"] == "inconclusive"


# ================================================================================== T-261: inverse strangle ==

def test_inverse_strangle_identities():
    days, close, iv = _btc(400, 0.6, 60.0, seed=7)
    r = x.inverse_strangle(days, close, iv, start="2021-01-01", end="2021-12-31")
    move = close[r["start"] + 30] - close[r["start"]]
    assert np.allclose(r["corrected"], r["naive"] - r["prem_btc"] * move)
    assert np.allclose(r["corrected"], r["naive_lin"])                 # hedging the coin premium = a USD premium
    assert np.allclose(r["corrected_coll"], r["naive_lin"])
    assert (r["Kc"] > r["spot"]).all() and (r["Kp"] < r["spot"]).all()
    assert (r["im_btc"] >= 0.2).all()


def test_inverse_hedge_ratio_planted_passes():
    days, close, iv = _btc(1300, 0.8, 80.0, seed=8)
    rep = x.inverse_hedge_ratio(days, close, iv, start="2021-01-01", end="2024-12-31", delta=0.45, n_boot=NB)
    assert rep["n"] >= 36
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["stat"]["var_ratio_usd"]["hi"] < 0.8
    assert rep["stat"]["usdc_linear_correct_rule"]["ratio"] == pytest.approx(1.0)


def test_inverse_hedge_ratio_null_fails():
    days, close, iv = _btc(1300, 0.8, 80.0, seed=9)
    rep = x.inverse_hedge_ratio(days, close, iv, start="2021-01-01", end="2024-12-31", delta=0.01, n_boot=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]             # a tiny coin premium: nothing to correct
    assert rep["stat"]["var_ratio_usd"]["ratio"] > 0.9


# ========================================================================== T-194: SPY vs SPX financing ==

def _t194_captures(n_days: int, n_exp: int, r_box: float = 0.043, spy_rate_shift: float = 0.0, base: str = "2026-08-03") -> list:
    caps = []
    for i in range(n_days):
        qd = (date.fromisoformat(base) + timedelta(days=i)).isoformat()
        dtes = [30 + 3 * j for j in range(n_exp)]
        spy = _chain("SPY", 700.0, qd, dtes, np.arange(690, 711, 1.0), r_box + spy_rate_shift, x.SPY_FEE, half=0.01)
        spx = _chain("SPXW", 7000.0, qd, dtes, np.arange(6300, 7701, 50.0), r_box, 0.013, half=0.5)
        caps.append({"quote_day": qd, "spy_spot": 700.0, "spx_spot": 7000.0, "spy": spy, "spx": spx})
    return caps


def test_box_rate_and_regression_forward_recover_inputs():
    qd = "2026-08-03"
    legs = x.chain_by_root(_chain("SPXW", 7000.0, qd, [60], np.arange(6300, 7701, 25.0), 0.045, 0.013, half=0.5))
    (key, lg), = legs.items()
    rb, nb = x.box_rate(lg, 7000.0, 60 / 365)
    assert nb > 50 and rb == pytest.approx(0.045, abs=2e-5)
    fw = x.regression_forward(lg, x.atm_pm(lg, 7000.0, 3))
    assert fw["F"] == pytest.approx(7000.0 * math.exp((0.045 - 0.013) * 60 / 365), rel=1e-6)


def test_spy_spx_financing_planted_passes():
    rep = x.spy_spx_financing(_t194_captures(20, 10))
    assert rep["n"] == 10
    assert rep["verdict"] == "supported", rep["reason"]
    assert all(abs(r["diff_bp"]) < 1 for d in rep["stat"]["per_day"] for r in d["expiries"])
    json.dumps(x._clean(rep["stat"]), allow_nan=False)


def test_spy_spx_financing_null_fails():
    rep = x.spy_spx_financing(_t194_captures(2, 10, spy_rate_shift=0.01))   # SPY finances 100 bp above the box
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_spy_spx_financing_two_days_below_min_n_inconclusive():
    rep = x.spy_spx_financing(_t194_captures(2, 4))
    assert rep["n"] == 4 and rep["verdict"] == "inconclusive"
    assert "min_n" in rep["reason"]
    rep = x.spy_spx_financing(_t194_captures(2, 4, spy_rate_shift=0.01))     # 4 of 4 off on day one: decisive below min_n
    assert rep["verdict"] == "not_supported"


def test_spy_spx_financing_respects_ex_date_and_dte():
    caps = _t194_captures(1, 10, base="2026-11-10")                          # every expiry falls on or after 2026-12-10
    rep = x.spy_spx_financing(caps, ex_date="2026-12-18")
    assert all(r["expiry"] < "2026-12-18" for d in rep["stat"].get("per_day", []) for r in d["expiries"])


# =================================================================================== T-199: GLD implied carry ==

def _gld_caps(n_days: int, carry_shift: float = 0.0, bill: float = 0.042) -> list:
    caps = []
    for i in range(n_days):
        qd = (date.fromisoformat("2026-08-03") + timedelta(days=i)).isoformat()
        # implied financing r_impl = bill - 0.40% (+ shift): price with r = bill + shift and q = GLD fee
        vals = _chain("GLD", 380.0, qd, [95, 130, 160, 250, 340], np.arange(370, 391, 1.0), bill + carry_shift, x.GLD_FEE, half=0.05)
        caps.append({"quote_day": qd, "spot": 380.0, "values": vals, "bill": bill, "bill_day": qd})
    return caps


def test_implied_carry_pairs_recover_rate():
    c = _gld_caps(1)[0]
    pairs = x.implied_carry_pairs(c["values"], c["spot"], c["quote_day"], c["bill"], x.GLD_FEE)
    assert len(pairs) == 5 * 7                                                # ATM +/- 3 strikes x 5 expiries
    assert all(abs(p["resid_bp"]) < 10 for p in pairs)


def test_gld_carry_planted_passes():
    rep = x.gld_carry(_gld_caps(5))
    assert rep["n"] == 35
    assert rep["verdict"] == "supported", rep["reason"]


def test_gld_carry_null_fails():
    rep = x.gld_carry(_gld_caps(2, carry_shift=0.012))                       # implied carry 120 bp above bill - fee
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["stat"]["share_day_one"] == 0.0


def test_gld_carry_two_good_days_cannot_confirm():
    rep = x.gld_carry(_gld_caps(2))
    assert rep["verdict"] == "inconclusive" and "from 5 days" in rep["reason"]


def test_bey_continuous_and_dgs3mo_bill_regression():
    """Regression (T-199 bill): the trial names FRED DGS3MO, a bond-equivalent yield; it is converted with
    ln(1 + y 91/365) / (91/365), and sits 9 bp above DTB3 (continuous) on the 2026-10-09 prints."""
    assert x.bey_continuous(4.25) * 1e4 == pytest.approx(422.76, abs=0.01)
    assert x.dtb3_continuous(4.06) * 1e4 == pytest.approx(413.77, abs=0.01)
    dtb3 = {"2026-10-08": 4.05, "2026-10-09": 4.06, "2026-10-13": 4.09}
    # archived fred-DGS3MO: the print dated strictly before the quote day
    b, d, src = x._bill_dgs3mo({"2026-10-09": 4.25, "2026-10-13": 4.26}, dtb3, "2026-10-13")
    assert (d, src) == ("2026-10-09", x.DGS3MO_B) and b == pytest.approx(x.bey_continuous(4.25))
    # not archived: the reference print, only when it is the latest FRED print before the quote day
    b, d, src = x._bill_dgs3mo({}, dtb3, "2026-10-14")
    assert d == "2026-10-13" and src.startswith("DGS3MO_REF") and b == pytest.approx(x.bey_continuous(4.26))
    later = dict(dtb3, **{"2026-10-14": 4.10})                               # DTB3 has a newer print the reference lacks
    assert x._bill_dgs3mo({}, later, "2026-10-15") == (None, None, None)


def test_gld_carry_judges_named_bill_and_reports_proxy_regression():
    """Regression (T-199): the criteria are judged on the trial's bill (DGS3MO); the DTB3 proxy is reported next to it.
    Planted: the market carries bill - fee exactly; a proxy 70 bp lower would put every pair outside the band."""
    caps = [dict(c, bill_src="DGS3MO_REF (fred-DGS3MO not archived)", proxy=c["bill"] - 0.007, proxy_day=c["bill_day"]) for c in _gld_caps(2)]
    rep = x.gld_carry(caps)
    d0 = rep["stat"]["per_day"][0]
    assert d0["share"] == 1.0 and d0["pass"] is True and d0["dtb3_proxy"]["share"] == 0.0
    assert d0["dtb3_proxy"]["bill_minus_proxy_bp"] == pytest.approx(70.0)
    assert rep["verdict"] == "inconclusive"                                  # judged on DGS3MO: 2 good days cannot confirm
    assert "70.0 to 70.0 bp above the DTB3 proxy" in rep["reason"] and "DGS3MO_REF" in rep["reason"]
    # null: the proxy is right and the named bill 70 bp too high -> judged on the named bill, the claim fails
    caps = [dict(c, bill=c["bill"] + 0.007, proxy=c["bill"], proxy_day=c["bill_day"]) for c in _gld_caps(2)]
    rep = x.gld_carry(caps)
    assert rep["verdict"] == "not_supported" and rep["stat"]["per_day"][0]["dtb3_proxy"]["share"] == 1.0


def test_gld_carry_day_without_named_bill_is_unjudged_regression():
    """Regression (T-199): a later day with no DGS3MO print is reported under the DTB3 proxy and left unjudged, so it
    cannot make the days criterion decisive."""
    caps = _gld_caps(2)
    caps[1] = dict(caps[1], bill=None, bill_day=None, proxy=caps[1]["bill"] + 0.012, proxy_day="2026-08-03")
    rep = x.gld_carry(caps)
    d1 = rep["stat"]["per_day"][1]
    assert d1["as_worded"] is False and d1["pass"] is None and d1["share"] == 0.0
    assert rep["stat"]["days_criterion"] is None and rep["verdict"] == "inconclusive"
    assert "left unjudged" in rep["reason"]


def test_gld_carry_reports_day_one_margin_regression():
    """Regression (T-199): the reason states how far day one is from flipping (pairs short and bp beyond the band)."""
    caps = _gld_caps(1)
    first = min(v["expiry"] for v in caps[0]["values"])
    vals = [dict(v, bid=v["bid"] + 1.0, ask=v["ask"] + 1.0) if v["type"] == "call" and v["expiry"] == first and v["strike"] in (377, 378, 379, 380)
            else v for v in caps[0]["values"]]
    rep = x.gld_carry([dict(caps[0], values=vals)])
    d0 = rep["stat"]["per_day"][0]
    assert (d0["n_within"], d0["n_pairs"]) == (31, 35) and d0["pairs_short_of_need"] == 1      # needs 32 of 35
    assert d0["nearest_outside_beyond_band_bp"] > 0
    assert rep["verdict"] == "not_supported" and "1 pair short of 90%" in rep["reason"]
    planted = x.gld_carry(_gld_caps(1))["stat"]["per_day"][0]
    assert planted["pairs_to_spare"] == 3 and planted["pairs_short_of_need"] == 0


# ============================================================================== T-137: parity deviation scan ==

def _t137_days(n_days: int, n_exp: int = 10, shift_frac: float = 0.0) -> list:
    out = []
    for i in range(n_days):
        qd = (date.fromisoformat("2026-08-03") + timedelta(days=i)).isoformat()
        dtes = [7 + 20 * j for j in range(n_exp)]
        r = 0.042
        pairs = x.european_pairs(_chain("SPXW", 7000.0, qd, dtes, np.arange(6300, 7701, 25.0), r, 0.013, half=0.5, cp_shift=shift_frac * 7000),
                                 7000.0, qd, r)
        for sym, s in (("SPY", 700.0), ("GLD", 380.0), ("IBIT", 46.0)):
            vals = _chain(sym, s, qd, dtes, np.linspace(0.97 * s, 1.03 * s, 13).round(2), r, 0.0, half=0.01 * s / 100,
                          cp_shift=shift_frac * s)
            pairs += x.american_pairs(vals, s, qd, r, sym)
        out.append((qd, pairs))
    return out


def test_parity_scan_planted_passes():
    rep = x.parity_scan(_t137_days(5), n_boot=NB)
    assert rep["n"] >= 500 and rep["stat"]["share"] == 0.0
    assert rep["verdict"] == "supported", rep["reason"]
    json.dumps(x._clean(rep["stat"]), allow_nan=False)


def test_parity_scan_null_fails():
    rep = x.parity_scan(_t137_days(5, shift_frac=0.003), n_boot=NB)         # C - P off by 0.6% of spot everywhere
    assert rep["stat"]["share"] > 0.5
    assert rep["verdict"] == "not_supported"


def test_parity_scan_two_days_clean_is_inconclusive():
    rep = x.parity_scan(_t137_days(2), n_boot=NB)
    assert rep["verdict"] == "inconclusive"                                  # share passes, the day-clustered CI needs 5 days


def test_parity_scan_missing_symbol_caps_verdict():
    days = [(qd, [p for p in ps if p["symbol"] != "IBIT"]) for qd, ps in _t137_days(5)]
    rep = x.parity_scan(days, n_boot=NB)
    assert rep["verdict"] == "inconclusive" and "IBIT" in rep["stat"]["absent_symbols"]


def test_european_pairs_flag_box_vs_bill():
    qd = "2026-08-03"
    vals = _chain("SPXW", 7000.0, qd, [365], np.arange(6300, 7701, 25.0), 0.05, 0.013, half=0.5)
    pairs = x.european_pairs(vals, 7000.0, qd, 0.04)                         # market discounts at 5%, bill 4%
    assert all(p["flag"] for p in pairs) and not any(p["flag_box"] for p in pairs)
    assert pairs[0]["r_box_bp"] == pytest.approx(500, abs=1)


def _ibit_offset_chain(true_spot: float, qd: str = "2026-10-14") -> list:
    return _chain("IBIT", true_spot, qd, [1, 3, 7, 30, 90, 200], np.arange(43.0, 49.01, 0.5), 0.04, 0.0, sigma=0.5, half=0.005)


def test_parity_implied_spot_recovers_quote_synchronous_spot_regression():
    """Regression (T-137 spot timing): quotes struck at 46.305 while the close prints 46.24 (+14 bp). The short-dated
    parity recovers the quote-synchronous spot; the upper-bound flags at the stale close vanish at that spot."""
    qd = "2026-10-14"
    vals = _ibit_offset_chain(46.305, qd)
    si = x.parity_implied_spot(vals, 46.24, qd, 0.04)
    assert si["spot"] == pytest.approx(46.305, abs=2e-3) and si["offset_bp"] == pytest.approx(14.0, abs=0.5)
    at_close = x.american_pairs(vals, 46.24, qd, 0.04, "IBIT")
    at_sync = x.american_pairs(vals, si["spot"], qd, 0.04, "IBIT")
    assert all(p["flag"] and p["side"] == "upper" for p in at_close)
    assert not any(p["flag"] for p in at_sync)
    # null: quotes synchronous with the close -> no offset and nothing flagged
    vals0 = _ibit_offset_chain(46.24, qd)
    s0 = x.parity_implied_spot(vals0, 46.24, qd, 0.04)
    assert abs(s0["offset_bp"]) < 0.5 and not any(p["flag"] for p in x.american_pairs(vals0, 46.24, qd, 0.04, "IBIT"))
    assert x.parity_implied_spot(_chain("IBIT", 46.0, qd, [30], [46.0], 0.04, 0.0), 46.0, qd, 0.04) is None   # no 1-10 DTE expiry


def test_spot_timing_lenient_reading_regression():
    """Regression (T-137): the lenient reading (SPX at its own box rate) is recomputed at the quote-synchronous spot,
    and flags that vanish there are labelled spot-timing artefacts. SPX here discounts at 5% vs a 4% bill: flagged
    under the bill, clean at its box rate."""
    qd = "2026-10-14"
    spx = x.european_pairs(_chain("SPXW", 7000.0, qd, [365], np.arange(6300, 7701, 25.0), 0.05, 0.013, half=0.5), 7000.0, qd, 0.04)
    vals = _ibit_offset_chain(46.305, qd)
    si = x.parity_implied_spot(vals, 46.24, qd, 0.04)
    close = spx + x.american_pairs(vals, 46.24, qd, 0.04, "IBIT")
    sync = spx + x.american_pairs(vals, si["spot"], qd, 0.04, "IBIT")
    t = x.spot_timing([(qd, close)], [(qd, sync)], {(qd, "IBIT"): si})
    ibit = next(r for r in t["by_day_symbol"] if r["symbol"] == "IBIT")
    assert ibit["flags_at_close"] == ibit["n"] == ibit["upper_at_close"] == ibit["spot_timing_artefacts"] > 0
    assert ibit["flags_at_implied_spot"] == 0 and ibit["offset_bp"] == pytest.approx(14.0, abs=0.5)
    assert t["lenient_close"] == pytest.approx(ibit["n"] / len(close)) and t["lenient_sync"] == 0.0
    assert t["share_sync"] == pytest.approx(len(spx) / len(sync))                 # the main reading keeps the SPX flags
    # null: synchronous quotes -> no artefacts, lenient share unchanged
    vals0 = _ibit_offset_chain(46.24, qd)
    p0 = spx + x.american_pairs(vals0, 46.24, qd, 0.04, "IBIT")
    t0 = x.spot_timing([(qd, p0)], [(qd, p0)], {(qd, "IBIT"): x.parity_implied_spot(vals0, 46.24, qd, 0.04)})
    assert all(r["spot_timing_artefacts"] == 0 for r in t0["by_day_symbol"]) and t0["lenient_close"] == t0["lenient_sync"] == 0.0
    json.dumps(x._clean(t), allow_nan=False)


def test_american_pairs_dividend_widens_lower_bound():
    qd = "2026-10-13"
    vals = _chain("SPY", 700.0, qd, [66], np.arange(690, 711, 1.0), 0.04, 0.0, half=0.01, cp_shift=-3.0)
    flagged = x.american_pairs(vals, 700.0, qd, 0.04, "SPY", None)
    with_div = x.american_pairs(vals, 700.0, qd, 0.04, "SPY", 1.9)           # the 2026-12-18 ex-date falls inside T
    assert all(p["flag"] and p["side"] == "lower" for p in flagged)
    assert not any(p["flag"] for p in with_div)


# ============================================================================================== DVOL haircut ==

def test_measured_atm_over_dvol():
    rows = [{"observed_at": "2026-10-14T11:00:00+00:00", "value": {"expiry": "30OCT26", "atm_mark_iv": 40.0}},
            {"observed_at": "2026-10-14T11:00:00+00:00", "value": {"expiry": "27NOV26", "atm_mark_iv": 40.0}}]
    ratio, k = x.measured_atm_over_dvol({"deribit-surface-BTC-2026-10-14": rows}, {"2026-10-13": 50.0})
    assert k == 1 and ratio == pytest.approx(0.8)
    late = {"2026-10-13": (50.0, "2026-10-14T12:00:00+00:00")}            # not yet available at the capture
    assert x.measured_atm_over_dvol({"s": rows}, late) == (None, 0)


# ====================================================================================== harness plumbing ==

class _Entry:
    def __init__(self, name, created_at):
        self.name, self.created_at = name, created_at


class FakeArchive:
    def __init__(self, bundles: dict, created: dict):
        self.b, self.c = bundles, created

    def entries(self):
        return [_Entry(n, self.c[n]) for n in self.b]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name, self.c[name])

    def load(self, name):
        if name not in self.b:
            raise KeyError(name)
        return iter(list(self.b[name]))


def _daily_rows(sym, days, closes):
    out = []
    for d, c in zip(days, closes):
        t = datetime.fromisoformat(d + "T13:30:00+00:00")
        out.append({"observed_at": t.isoformat(), "available_at": (t + timedelta(days=1)).isoformat(),
                    "value": {"symbol": sym, "t": t.timestamp(), "close": c, "adjclose": c}})
    return out


def test_harnesses_report_missing_bundles():
    empty = FakeArchive({}, {})
    for name, fn in x.HARNESSES.items():
        stat, n, verdict, reason = fn(empty)
        assert verdict == "inconclusive" and n == 0 and "missing" in reason
        json.dumps(stat, allow_nan=False)
    assert set(x.THEORY_MAP.values()) == set(x.HARNESSES)
    assert all(k.startswith("b6_xc_") for k in x.HARNESSES)


def _gld_fake(bill: float, dgs3mo=None):
    days = ["2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14"]
    hist = _daily_rows("GLD", days, [379.0, 380.0, 381.0, 382.0])
    dtb3 = [{"observed_at": d, "available_at": d, "value": {"day": d, "value": 4.0}} for d in ("2026-10-09", "2026-10-13")]
    bundles = {"daily-history-GLD": hist, "fred-DTB3": dtb3}
    created = {"daily-history-GLD": "2026-10-15T08:00:00+00:00", "fred-DTB3": "2026-10-14T11:00:00+00:00"}
    if dgs3mo:
        bundles["fred-DGS3MO"] = [{"observed_at": d, "available_at": d, "value": {"day": d, "value": v}} for d, v in dgs3mo.items()]
        created["fred-DGS3MO"] = "2026-10-14T11:00:00+00:00"
    for cap, qd, s in (("2026-10-14", "2026-10-13", 381.0), ("2026-10-15", "2026-10-14", 382.0)):
        vals = _chain("GLD", s, qd, [95, 130, 160, 250, 340], np.arange(s - 10, s + 11, 1.0), bill, x.GLD_FEE, half=0.05)
        name = f"options-chain-GLD-{cap}"
        bundles[name] = [{"observed_at": f"{cap} 07:00:00", "available_at": f"{cap}T07:05:00+00:00", "value": v} for v in vals]
        created[name] = f"{cap}T07:06:00+00:00"
    return FakeArchive(bundles, created)


def test_gld_harness_end_to_end_quote_day_mapping():
    """fred-DGS3MO not archived: the bill is the DGS3MO_REF print (FRED print day = the prior DTB3 print day), the
    DTB3 proxy is reported next to it."""
    stat, n, verdict, reason = x.b6_xc_gld_implied_carry(_gld_fake(x.bey_continuous(4.25)))
    assert [d["quote_day"] for d in stat["per_day"]] == ["2026-10-13", "2026-10-14"]   # pre-open captures: previous session
    assert stat["per_day"][0]["bill_day"] == "2026-10-09"                              # FRED print dated before the quote day
    assert stat["per_day"][0]["bill_cont_bp"] == pytest.approx(x.bey_continuous(4.25) * 1e4)
    assert stat["per_day"][0]["dtb3_proxy"]["rate_cont_bp"] == pytest.approx(x.dtb3_continuous(4.0) * 1e4)
    assert stat["bill_series"] == ["DGS3MO_REF (fred-DGS3MO not archived)"]
    assert stat["per_day"][1]["spot"] == 382.0                                         # the quote day's raw close
    assert n == 35 and stat["share_day_one"] == 1.0
    assert verdict == "inconclusive"                                                   # 2 good days cannot confirm the 80% rule
    json.dumps(stat, allow_nan=False)


def test_gld_harness_uses_archived_dgs3mo_regression():
    """Regression (T-199): once fred-DGS3MO is archived it is the bill (prior print, bond-equivalent -> continuous);
    the reference prints are no longer used. Planted at the archived print: passes day one; DTB3 is 4.0."""
    dg = {"2026-10-09": 5.10, "2026-10-13": 5.12}
    stat, n, verdict, reason = x.b6_xc_gld_implied_carry(_gld_fake(x.bey_continuous(5.10), dg))
    d0 = stat["per_day"][0]
    assert stat["bill_series"] == [x.DGS3MO_B] and d0["bill_day"] == "2026-10-09"
    assert d0["bill_cont_bp"] == pytest.approx(x.bey_continuous(5.10) * 1e4) and d0["share"] == 1.0
    assert "DGS3MO_REF" not in reason and verdict == "inconclusive"
    # null: the market carries the DTB3 level, ~99 bp below the archived DGS3MO -> judged on DGS3MO, day one fails
    stat, n, verdict, reason = x.b6_xc_gld_implied_carry(_gld_fake(x.dtb3_continuous(4.0), dg))
    assert stat["share_day_one"] == 0.0 and stat["per_day"][0]["dtb3_proxy"]["share"] == 1.0 and verdict == "not_supported"
