"""Batch 6a, group surf: surface and index relative-value harnesses on synthetic data only (no archive, no network).
Each core function gets a planted effect that passes and a null that does not. For the claims that assert the ABSENCE of
an effect (T-227, T-511) the "planted" case is the world in which the claim holds."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6_surf as s
from mandel.options import bs

NB = 400            # bootstrap draws in tests (the harnesses use 2,000)


# ===================================================================================================== fixtures ==

def _bdays(start: str, n: int) -> list:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _path(daily_sd, seed=0, s0=100.0, z=None):
    """Price path whose return on day u (u >= 1) has sd daily_sd[u-1] (martingale in logs up to the drift term)."""
    sd = np.asarray(daily_sd, dtype=float)
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(sd.size) if z is None else z
    lr = -0.5 * sd ** 2 + sd * z
    return s0 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))


class FakeArchive:
    """In-memory stand-in for mandel.archive.Archive: get / load / entries."""

    def __init__(self, bundles=None):
        self.b = bundles or {}

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return SimpleNamespace(name=name, created_at="2100-01-01T00:00:00+00:00")

    def load(self, name):
        return iter(self.b[name])

    def entries(self):
        return [SimpleNamespace(name=n) for n in self.b]


def _price_rows(days, close, adj=None):
    adj = close if adj is None else adj
    out = []
    for d, c, a in zip(days, close, adj):
        t = datetime(*map(int, d.split("-")), 14, 30, tzinfo=timezone.utc).timestamp()
        out.append({"available_at": d + "T21:00:00+00:00", "value": {"t": t, "close": float(c), "adjclose": float(a)}})
    return out


def _index_rows(days, vals):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


# =================================================================================================== statistics ==

def test_stud_mean_planted_and_null():
    rng = np.random.default_rng(1)
    bt = s.stud_mean(0.4 + rng.standard_normal(300), 5, NB)
    assert s.lower_bound(bt, 0.95) > 0 and s.p_greater(bt) < 0.05
    bt0 = s.stud_mean(rng.standard_normal(300), 5, NB)
    lo, hi = s.two_sided(bt0)
    assert lo < 0 < hi and s.p_greater(bt0) > 0.05
    const = s.stud_mean(np.full(20, 2.0), 3, NB)
    assert const["t"] is None and s.two_sided(const) == (2.0, 2.0) and s.p_greater(const, 1.0) == 0.0
    assert s.stud_mean(np.array([1.0, 2.0]), 3) is None


def test_bounds_are_ordered_and_one_sided_is_tighter():
    rng = np.random.default_rng(2)
    bt = s.stud_mean(0.1 + rng.standard_normal(500), 5, NB)
    lo2, hi2 = s.two_sided(bt, 0.95)
    assert lo2 < s.lower_bound(bt, 0.95) < bt["est"] < s.upper_bound(bt, 0.95) < hi2
    assert s.p_less(bt) == pytest.approx(1 - s.p_greater(bt), abs=0.01)


def test_group_diff_planted_null_and_subset():
    rng = np.random.default_rng(3)
    n = 600
    lab = rng.integers(0, 3, n)
    x = rng.standard_normal(n) + np.where(lab == 2, 0.6, 0.0)
    bt = s.stud_group(x, lab == 2, lab == 0, 6, NB)
    assert bt["est"] > 0 and s.two_sided(bt)[0] > 0
    bt0 = s.stud_group(rng.standard_normal(n), lab == 2, lab == 0, 6, NB)
    lo, hi = s.two_sided(bt0)
    assert lo < 0 < hi
    sub = s.stud_group(x, lab == 2, np.ones(n, bool), 6, NB)          # overlapping groups: subset against all
    assert sub["est"] == pytest.approx(x[lab == 2].mean() - x.mean()) and s.two_sided(sub)[0] > 0
    assert s.stud_group(x, np.zeros(n, bool), lab == 0, 6) is None


def test_decide_below_min_n_needs_decisive_failure():
    v, why = s._decide([("a", False, False)], 10, 100, "cycles")
    assert v == "inconclusive" and "not decisively" in why
    v, _ = s._decide([("a", False, True)], 10, 100, "cycles")
    assert v == "not_supported"
    v, _ = s._decide([("a", True, False)], 10, 100, "cycles")
    assert v == "inconclusive"
    v, _ = s._decide([("a", True, False)], 100, 100, "cycles")
    assert v == "supported"


def test_rule10_helpers():
    rng = np.random.default_rng(9)
    x = rng.standard_normal((3, 500)).cumsum(axis=1)
    from mandel.validation.backtest_eval import _hac_var
    assert np.allclose(s._lrv(x, 126), _hac_var(x, 126)) and np.allclose(s._lrv(x, 5), _hac_var(x, 5))
    assert s.pool_block_len(21) == 126 and s.pool_block_len(63, 2) == 126 and s.pool_block_len(21, 1) == 42
    idx = np.arange(7, 7 + 21 * 10)
    assert s.n_holds(idx, 21) == 10 and s.n_holds(idx[:1], 21) == 1 and s.n_holds([], 21) == 0
    assert np.array_equal(s.offset_of(idx, 21)[:3], [0, 1, 2]) and s.offset_of(idx, 21)[21] == 0
    days = _bdays("2024-01-29", 30)
    assert [days[i] for i in s.month_first(days)] == ["2024-01-29", "2024-02-01", "2024-03-01"]
    ok = np.array([d != "2024-02-01" for d in days])
    assert [days[i] for i in s.month_first(days, ok=ok, start="2024-02-01")] == ["2024-02-02", "2024-03-01"]
    assert s.grid_cycles(50, 21, 3).tolist() == [[3, 24], [24, 45]]


# ================================================================================================= market data ==

def test_dtb3_conversion_and_prior_print():
    assert s.dtb3_continuous(5.0) == pytest.approx(-math.log(1 - 0.05 * 91 / 360) / (91 / 365))
    r = s.bill_rates(["2020-01-02", "2020-01-03", "2020-01-06"], {"2020-01-02": 1.0, "2020-01-03": 2.0})
    assert r[0] == pytest.approx(s.dtb3_continuous(1.0))          # before the first print: the first print
    assert r[1] == pytest.approx(s.dtb3_continuous(1.0))          # the same day's print is not yet published
    assert r[2] == pytest.approx(s.dtb3_continuous(2.0))


def test_dividends_forecast_and_trailing_yield():
    days = _bdays("2000-01-03", 600)
    close = np.full(600, 100.0)
    f = np.ones(600)
    for i in (100, 163, 226, 289, 352, 415, 478, 541):
        f[i:] *= 1.0 / (1.0 - 0.5 / 100.0)                           # a 0.50 dividend going ex on day i
    div = s.dividends(close, close * f)
    assert np.nonzero(div)[0].tolist() == [100, 163, 226, 289, 352, 415, 478, 541]
    assert div[100] == pytest.approx(0.5)
    fc = s.div_forecast(div)
    assert fc[99] == pytest.approx(0.5) and fc[120] == pytest.approx(0.5)
    y = s.trailing_yield(days, close, close * f)
    assert y[-1] == pytest.approx(4 * 0.5 / 100, rel=0.05)


def test_trailing_yield_is_point_in_time_before_the_first_full_year():
    # regression (T-229): days before one full year of dividend history used to be back-filled with the first full-year
    # value, i.e. with dividends paid AFTER those decisions. They now get the ex-ante constant and ignore later dividends.
    days = _bdays("1993-01-29", 600)
    close = np.full(600, 100.0)
    f = np.ones(600)
    for i in (35, 98, 161, 224, 287, 350, 413, 476, 539):
        f[i:] *= 1.0 / (1.0 - 0.7 / 100.0)
    y = s.trailing_yield(days, close, close * f)
    first = next(i for i, d in enumerate(days) if date.fromisoformat(d).toordinal() - date.fromisoformat(days[0]).toordinal() >= 365)
    assert np.all(y[:first] == s.PRE_YIELD) and s.PRE_YIELD == pytest.approx(0.03)
    assert y[first] == pytest.approx(4 * 0.7 / 100, rel=0.05)            # unchanged once computable
    f2 = f.copy()
    f2[200:] *= 1.0 / (1.0 - 5.0 / 100.0)                                # a huge later dividend must not move earlier days
    y2 = s.trailing_yield(days, close, close * f2)
    assert np.array_equal(y2[:200], y[:200])
    assert np.all(s.trailing_yield(days, close, close * f, pre=0.025)[:first] == 0.025)


def test_trailing_percentile_is_point_in_time_and_rolling_z():
    x = np.arange(300, dtype=float)
    p = s.trailing_pctl(x, 0.5, 252)
    assert np.isnan(p[251]) and p[252] == pytest.approx(np.median(x[:252]))
    x2 = x.copy()
    x2[260] = 1e6                                                   # a spike on day 260 must not move day 260's percentile
    assert s.trailing_pctl(x2, 0.9, 252)[260] == pytest.approx(p[260] * 0 + np.quantile(x[8:260], 0.9))
    z = s.rolling_z(np.r_[np.zeros(59), 10.0], 60)
    assert z[-1] > 2 and np.isnan(z[0])


# ========================================================================================== option pricing ==

def test_black76_parity_delta_and_smile_strike():
    F, T, r, sig = 20.0, 30 / 365, 0.03, 0.9
    K = s.b76_call_strike(F, T, sig, 0.25)
    sq = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / sq
    assert s._N(d1) == pytest.approx(0.25, abs=1e-6)
    put = math.exp(-r * T) * (K * s._N(-(d1 - sq)) - F * s._N(-d1))
    assert s.b76_call(F, K, T, r, sig) - put == pytest.approx(math.exp(-r * T) * (F - K), abs=1e-9)
    k_flat = s.strike_for_delta_smile(100.0, T, r, 0.01, lambda k: 0.2, -0.25, "put", 20.0, 100.0)
    assert k_flat == pytest.approx(bs.strike_for_delta(100.0, T, r, 0.2, -0.25, "put", 0.01), rel=1e-6)
    assert s._bs(100, 95, T, r, 0.01, 0.2, "put") == pytest.approx(float(bs.price(100, 95, T, r, 0.2, "put", 0.01)), rel=1e-9)


def _bs_chain(F, T, r, iv_fn, strikes, expiry, root="SPXW"):
    """Synthetic chain rows priced by Black-Scholes on the forward (q chosen so S e^{(r-q)T} = F with S = F e^{-rT})."""
    S = F * math.exp(-r * T)
    rows = []
    for K in strikes:
        sig = iv_fn(K)
        for kind in ("call", "put"):
            p = s._bs(S, K, T, r, 0.0, sig, kind)
            dl = s._bs_delta(S, K, T, r, 0.0, sig, kind)
            bid = p * 0.995 if p > 0.05 else 0.0
            rows.append({"sym": f"{root}261113{kind[0].upper()}{int(K * 1000):08d}", "expiry": expiry, "type": kind,
                         "strike": float(K), "bid": bid, "ask": p * 1.005 + 0.01, "iv": sig, "delta": dl})
    return rows


def test_variance_strip_recovers_flat_vol():
    qd, exp = "2026-10-13", "2026-11-12"
    T, r = 30 / 365, 0.04
    rows = _bs_chain(5000.0, T, r, lambda K: 0.20, np.arange(2500, 7505, 5), exp)
    st = s.variance_strip(rows, exp, qd, r)
    assert math.sqrt(st["var"]) == pytest.approx(0.20, abs=0.004)
    rows93 = _bs_chain(5000.0, 93 / 365, r, lambda K: 0.20, np.arange(1500, 9005, 5), "2027-01-14")
    chk = s.strip_check(rows + rows93, qd, r, 20.0, 20.0)
    assert abs(chk["err_30"]) < 0.4 and abs(chk["err_93"]) < 0.4


def test_calibrate_skew_slope_recovers_kappa():
    qd, exp = "2026-10-13", "2026-11-12"
    T, r, F = 30 / 365, 0.04, 6000.0
    slope = -0.8
    rows = _bs_chain(F, T, r, lambda K: max(0.15 + slope * math.log(K / F), 0.02), np.arange(4800, 6600, 5), exp)
    cal = s.calibrate_skew_slope(rows, qd, r, vix_q=18.75, skew_q=150.0)
    assert cal["slope"] == pytest.approx(slope, abs=0.02)
    assert cal["atm_ratio"] == pytest.approx(0.8, abs=0.005)
    assert cal["kappa"] == pytest.approx(0.016, abs=0.0005)


# ================================================================================ T-159: VRP by term regime ==

def _regime_world(factor_con, factor_bwd, n=6000, seed=0, blk=42):
    rng = np.random.default_rng(seed)
    nb = n // blk + 1
    reg = np.repeat(rng.random(nb) < 0.35, blk)[:n]                    # True = backwardation block
    lvl = np.repeat(rng.uniform(12, 40, nb), blk)[:n]                  # VIX level independent of the regime
    vix = lvl
    vix3m = np.where(reg, vix / 1.10, vix / 0.90)
    fac = np.where(reg, factor_bwd, factor_con)
    px = _path(fac[:-1] * vix[:-1] / 100 / math.sqrt(252), seed + 1)
    return _bdays("2009-09-18", n), px, vix, vix3m


def test_vrp_regime_planted_passes():
    days, px, vix, v3 = _regime_world(0.7, 1.4)
    rep = s.vrp_regime(days, px, vix, v3, n_boot=NB, n_shift=400)
    assert rep["verdict"] == "supported", rep["reason_core"]
    assert rep["terciles_passing"] >= 2


def test_vrp_regime_null_fails():
    days, px, vix, v3 = _regime_world(0.85, 0.85)
    rep = s.vrp_regime(days, px, vix, v3, n_boot=NB, n_shift=400)
    assert rep["verdict"] == "not_supported", rep["reason_core"]


def test_vrp_regime_untestable_terciles_cap_at_inconclusive():
    days, px, vix, v3 = _regime_world(0.7, 1.4)
    v3 = np.where(vix > np.quantile(vix, 0.67), v3, vix / 0.9)          # backwardation only in the high tercile
    rep = s.vrp_regime(days, px, vix, v3, n_boot=NB, n_shift=400)
    assert rep["verdict"] == "inconclusive"


def test_vrp_regime_failing_testable_tercile_is_a_failure_even_when_others_are_untestable():
    # regression (T-159): the claim says "within EACH VIX tercile", so every tercile is a criterion. Backwardation only in
    # the high tercile and no effect there: low/mid are untestable (None) but the testable high tercile FAILS, so the
    # verdict is not_supported (the old 2-of-3-only aggregate returned None -> inconclusive and "criteria pass").
    days, px, vix, v3 = _regime_world(0.85, 0.85)
    v3 = np.where(vix > np.quantile(vix, 0.67), v3, vix / 0.9)
    rep = s.vrp_regime(days, px, vix, v3, n_boot=NB, n_shift=400)
    rows = {r["tercile"]: r for r in rep["terciles"]}
    assert rows["low"]["pass"] is None and rows["mid"]["pass"] is None and rows["high"]["pass"] is False
    assert rows["high"]["n_backwardation"] >= 60
    assert rep["verdict"] == "not_supported", rep["why"]
    assert rep["why"].startswith("failed: high VIX tercile") and "implemented criteria pass" not in rep["why"]


def test_short_strangle_daily_entries_for_the_pooled_secondary():
    days = _bdays("2010-01-04", 120)
    fr = s.make_frame(days, _path(np.full(119, 0.1 / math.sqrt(252)), 3), vix=np.full(120, 20.0), rate=np.full(120, 0.02))
    grid = s.short_strangle_cycles(fr)
    daily = s.short_strangle_cycles(fr, starts=np.arange(120))
    assert grid["start"].tolist() == [0, 21, 42, 63, 84] and daily["start"].tolist() == list(range(99))
    assert np.allclose(daily["pnl"][grid["start"]], grid["pnl"])


def test_short_strangle_cycles_sign():
    days = _bdays("2010-01-04", 400)
    calm = _path(np.full(399, 0.05 / math.sqrt(252)), 3)
    fr = s.make_frame(days, calm, vix=np.full(400, 30.0), rate=np.full(400, 0.02))
    assert s.short_strangle_cycles(fr)["pnl"].mean() > 0               # sold at 30 vol, realised 5
    wild = _path(np.full(399, 0.80 / math.sqrt(252)), 3)
    fr2 = s.make_frame(days, wild, vix=np.full(400, 10.0), rate=np.full(400, 0.02))
    assert s.short_strangle_cycles(fr2)["pnl"].mean() < 0


# ================================================================== T-227: SKEW percentile and left tails ==

def _skew_world(informative, n=40000, seed=0):
    rng = np.random.default_rng(seed)
    nb = n // 10 + 1
    skew = np.repeat(rng.uniform(100, 150, nb), 10)[:n]
    vix = np.full(n, 25.0)
    hi = skew > 140
    vol = np.where(hi & informative, 0.50, 0.20)
    close = _path(vol[:-1] / math.sqrt(252), seed + 1)
    return _bdays("1900-01-01", n), close, skew, vix


def test_skew_tail_frequency_claim_holds_when_skew_is_uninformative():
    # each half's "skewness difference not significantly negative (p > 0.1)" test fails ~10% of the time under a true
    # null by construction; seed 1 is a draw where neither half does
    days, c, sk, vx = _skew_world(False, seed=1)
    rep = s.skew_tail_frequency(days, c, sk, vx, start="1900-06-01", window=5, block=5, lookback=50, split=days[20000],
                                n_boot=NB, n_placebo=20)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["upper_bound"] < 0.01


def test_skew_tail_frequency_fails_when_skew_predicts_tails():
    days, c, sk, vx = _skew_world(True)
    rep = s.skew_tail_frequency(days, c, sk, vx, start="1900-06-01", window=5, block=5, lookback=50, split=days[20000],
                                n_boot=NB, n_placebo=20)
    assert rep["verdict"] == "not_supported"
    assert rep["diff"] > 0.05


# ===================================================================== T-228: SKEW-implied tail vs realised ==

def test_skew_tail_prob_mapping():
    assert s.skew_tail_prob(100.0) == pytest.approx(0.0228)
    assert s.skew_tail_prob(145.0) == pytest.approx(0.1443)


def _gap_world(skew_level, n=21 * 340, seed=0):
    vix = np.full(n, 20.0)
    close = _path(np.full(n - 1, 0.20 / math.sqrt(252)), seed)
    return _bdays("1990-01-02", n), close, np.full(n, float(skew_level)), vix


def test_skew_implied_gap_planted_passes():
    days, c, sk, vx = _gap_world(140)
    rep = s.skew_implied_gap(days, c, sk, vx, n_boot=NB, n_placebo=50)
    assert rep["verdict"] == "supported", rep["reason"]


def test_skew_implied_gap_null_fails():
    days, c, sk, vx = _gap_world(100)                                     # P = 2.28% = the normal tail of a true-vol VIX
    rep = s.skew_implied_gap(days, c, sk, vx, n_boot=NB, n_placebo=50)
    assert rep["verdict"] == "not_supported"
    assert abs(rep["mean_gap"]) < 0.02


def test_skew_implied_gap_effect_only_on_one_grid_phase_does_not_pass():
    # rule 10 regression (T-228): SKEW is rich (140, P = 13.1%) only on the sessions of grid offset 0 and 100 (P = the
    # normal 2.28%) elsewhere. The old offset-0 grid clears the 2 pp margin; the pooled all-offset estimate (primary) does
    # not, so the claim must not pass.
    days, c, sk, vx = _gap_world(100)
    sk = sk.copy()
    sk[::21] = 140.0
    rep = s.skew_implied_gap(days, c, sk, vx, n_boot=NB, n_placebo=50)
    offs = {o["offset"]: o for o in rep["grid_offsets"]}
    assert offs[0]["pass"] and offs[0]["lower"] > 0.02
    assert sum(o["pass_bound"] for o in rep["grid_offsets"]) == 1
    assert rep["lower_bound_95_one_sided"] < 0.02 and rep["verdict"] == "not_supported", rep["reason"]
    assert rep["n"] == 340 - 1 and rep["n_entries"] == len(days) - 21           # n = distinct 21-session holds


def test_skew_implied_gap_needs_each_of_three_sub_periods():
    # refuter (T-228): the procedure requires the gap to be positive in EACH third; the pass rule's 2 of 3 is weaker.
    # Thirds 1 and 3 carry a large gap, the middle third a negative one: the pooled bound and 2-of-3 pass, each-of-3 fails.
    n = 21 * 600
    days = _bdays("1990-01-02", n)
    third = np.arange(n) * 3 // n
    mid = third == 1
    sk = np.where(mid, 100.0, 160.0)
    sd = np.where(mid, 0.40, 0.20) / math.sqrt(252)                       # realised vol 2x VIX in the middle third
    c = _path(sd[:-1], 4)
    rep = s.skew_implied_gap(days, c, sk, np.full(n, 20.0), n_boot=NB, n_placebo=50)
    assert rep["thirds"][0] > 0 > rep["thirds"][1] and rep["thirds"][2] > 0
    assert rep["lower_bound_95_one_sided"] > 0.02
    assert rep["verdict"] == "not_supported" and "EACH of the 3 sub-periods" in rep["reason"].split(" — ")[-1]
    assert "at least 2 of 3" not in rep["reason"].split(" — ")[-1]


def test_skew_implied_gap_placebo_is_on_the_realised_indicator():
    # refuter (T-228): the SKEW placebo must ask whether SKEW predicts REALISED tails (P_SKEW rises with SKEW by
    # construction, so a placebo on the gap could not fail).
    rng = np.random.default_rng(5)
    n = 21 * 400
    sk = np.repeat(rng.uniform(110, 160, n // 42 + 1), 42)[:n]
    days = _bdays("1990-01-02", n)
    flat = s.skew_implied_gap(days, _path(np.full(n - 1, 0.20 / math.sqrt(252)), 6), sk, np.full(n, 20.0),
                              n_boot=NB, n_placebo=300)
    sd = np.where(sk > 135, 0.45, 0.20) / math.sqrt(252)                 # high SKEW really precedes fat left tails
    info = s.skew_implied_gap(days, _path(sd[:-1], 6), sk, np.full(n, 20.0), n_boot=NB, n_placebo=300)
    assert info["skew_information"]["diff"] > 0.05 and info["skew_information"]["placebo_p"] < 0.05
    assert flat["skew_information"]["placebo_p"] > 0.05
    assert "REALISED tail" in flat["reason"] and "BELOW" in flat["reason"]    # benchmark gap below the margin is stated


def test_skew_implied_gap_reports_the_spy_splice():
    days, c, sk, vx = _gap_world(140)
    alt = np.where(np.arange(len(days)) >= 200, c, np.nan)                  # the same prices from session 200 on
    rep = s.skew_implied_gap(days, c, sk, vx, n_boot=NB, n_placebo=20, alt_close={"SPY splice": alt})
    a = rep["alt_series"]["SPY splice"]
    assert a["from"] == days[200] and a["mean_gap"] == pytest.approx(rep["mean_gap"])
    assert "SPY splice (from" in rep["reason"] and "the S&P 500 itself" in rep["reason"]


def test_gspc_calendar_carries_prints_point_in_time():
    gd = _bdays("1990-01-02", 30)
    gc = np.linspace(100, 110, 30)
    skew = {d: 120.0 + i for i, d in enumerate(gd) if i not in (5, 6, 7)}     # SKEW misses three index sessions
    vix = {d: 20.0 for d in gd[1:]}                                          # VIX starts a session later
    days, c, sk, vx, fresh = s.gspc_calendar(gd, gc, skew, vix)
    assert days == gd[1:] and c[0] == gc[1]                                 # from the first day with both prints
    i5 = days.index(gd[5])
    assert sk[i5] == 124.0 and sk[i5 + 2] == 124.0 and sk[i5 + 3] == 128.0   # last print at or before, never a later one
    assert not fresh[i5] and fresh[i5 + 3]
    v, f = s.asof_series(gd, {gd[0]: 1.0}, max_age=7)
    assert v[5] == 1.0 and np.isnan(v[6])                                  # 8 calendar days old: too stale


# ===================================================================== T-229: SKEW-gated SPX put spread ==

def _monthly_entries(days, dte=30):
    return s.calendar_entries(days, s.sessions_for(days, s.monthly_expiry_dates(days)), dte, non_overlap=True)


def _spread_world(planted, entries=400, seed=0):
    """SKEW in 21-session blocks; with ``planted`` a cheap-SKEW entry (below the trailing p20) on SPX's monthly-expiry
    calendar is followed by a 12% slide to its expiry."""
    rng = np.random.default_rng(seed)
    n = 252 + 21 * entries + 22
    days = _bdays("1990-01-02", n)
    blocks = n // 21 + 1
    skew = np.repeat(rng.uniform(110, 140, blocks), 21)[:n]
    p20 = s.trailing_pctl(skew, 0.20, 252)
    sd = np.full(n - 1, 0.15 / math.sqrt(252))
    lr = sd * rng.standard_normal(n - 1)
    if planted:
        for t, e in np.stack(_monthly_entries(days), axis=1):
            if t >= 252 and skew[t] < p20[t]:
                lr[t:e] = -0.12 / (e - t)
    close = 100 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))
    return days, close, skew, np.full(n, 20.0), np.full(n, 0.03), np.full(n, 0.015)


def test_monthly_expiry_entries_are_30_dte_and_never_overlap():
    days = _bdays("1990-01-02", 2000)
    ent, exp = _monthly_entries(days)
    o = s._ords(days)
    assert all(date.fromisoformat(days[e]).weekday() == 4 and 15 <= int(days[e][8:]) <= 21 for e in exp)   # third Fridays
    dte = o[exp] - o[ent]
    assert dte.min() >= 27 and dte.max() <= 32 and np.all(ent[1:] >= exp[:-1])
    assert np.any(ent[1:] == exp[:-1])                                   # 28-day months: entered at the previous expiry
    hol = [d for d in days if d != "1992-04-17"]                         # a holiday third Friday (Good Friday 1992)
    m = s.monthly_expiry_dates(hol)
    assert "1992-04-16" in m and "1992-04-17" not in m


def test_put_spread_cycle_prices_a_debit_spread():
    c = s.put_spread_cycle(100.0, 80.0, 30 / 365, 0.03, 0.015, 0.16, -0.6)
    debit, payoff, k_long, k_short = c
    assert k_short < k_long < 100.0 and 0 < debit < k_long - k_short
    assert payoff == pytest.approx(k_long - k_short)


def test_put_spread_skew_planted_passes():
    days, c, sk, vx, r, q = _spread_world(True)
    rep = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=200)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["calendar"].startswith("SPX monthly expiry") and 27 <= rep["dte_range"][0] <= rep["dte_range"][1] <= 32
    assert "standard monthly expiry calendar" in rep["reason"]


def test_put_spread_skew_entries_follow_the_expiry_calendar_not_a_grid():
    # rule 10(a) (T-229): "monthly 30-DTE" is the monthly expiry calendar. The same world tested on explicit 21-session
    # grid entries gives a different sample; the default must be the calendar's.
    days, c, sk, vx, r, q = _spread_world(False, entries=60)
    rep = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=20)
    ent, exp = _monthly_entries(days)
    keep = ent >= 252
    assert rep["first_entry"] == days[ent[keep][0]] and rep["last_expiry"] == days[exp[keep][-1]]
    g = s.grid_cycles(len(days), 21, 252)
    rep_g = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=20,
                              entries=g[:, 0], expiries=g[:, 1])
    assert rep_g["first_entry"] == days[252] and rep_g["dte_range"] != rep["dte_range"]


def test_put_spread_skew_null_fails():
    days, c, sk, vx, r, q = _spread_world(False)
    rep = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=200)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_put_spread_skew_reports_entries_on_an_assumed_yield():
    # regression (T-229): entries priced on the ex-ante assumed yield are counted and named in the reason
    days, c, sk, vx, r, q = _spread_world(False, entries=60)
    ent, _ = _monthly_entries(days)
    ent = ent[ent >= 252]
    qa = np.arange(len(days)) < ent[9] + 1                               # the first 10 calendar entries
    rep = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=20, q_assumed=qa)
    assert rep["entries_assumed_q"] == 10 and "ASSUMED dividend yield" in rep["reason"]
    rep0 = s.put_spread_skew(days, c, sk, vx, r, q, 0.8, 0.015, start="1990-01-02", n_boot=NB, n_placebo=20)
    assert rep0["entries_assumed_q"] == 0 and "ASSUMED" not in rep0["reason"]


# =========================================================================== T-237: VXN - VIX z extremes ==

def _spread_vol_world(mean_reverting, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.empty(n)
    x[0] = 4.0
    e = rng.standard_normal(n)
    for t in range(1, n):
        x[t] = (4.0 + 0.9 * (x[t - 1] - 4.0) + 1.5 * e[t]) if mean_reverting else (x[t - 1] + 0.15 * e[t])
    iv_b = np.full(n, 30.0)
    iv_a = np.maximum(iv_b + x, 2.0)
    z = rng.standard_normal(n - 1)                                       # shared shocks: realised spread tracks the vol path
    pa = _path(iv_a[:-1] / 100 / math.sqrt(252), z=z)
    pb = _path(iv_b[:-1] / 100 / math.sqrt(252), z=z)
    return _bdays("2009-09-14", n), iv_a, iv_b, pa, pb


def test_vol_spread_planted_passes():
    days, a, b, pa, pb = _spread_vol_world(True)
    rep = s.vol_spread_test(days, a, b, pa, pb, n_boot=NB, n_placebo=200)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] >= 30


def test_vol_spread_null_fails():
    days, a, b, pa, pb = _spread_vol_world(False)
    rep = s.vol_spread_test(days, a, b, pa, pb, n_boot=NB, n_placebo=200)
    assert rep["verdict"] != "supported", rep["reason"]


def test_vol_spread_each_side_is_a_criterion():
    # regression (T-237): the claim asserts both sides (realised spread below an extreme-wide implied spread AND above an
    # extreme-narrow one). Here realised QQQ-side vol runs 4 vol pts above its implied: the pooled statistic still passes
    # every pooled criterion (the narrow side's s = -1 flips the negative bias into a gain), but the wide side is negative.
    days, a, b, _, _ = _spread_vol_world(True)
    rng = np.random.default_rng(0)
    rng.standard_normal(4000)                                            # skip the spread innovations _spread_vol_world draws,
    shocks = rng.standard_normal(3999)                                   # then take the same shared return shocks
    pa = _path((a[:-1] + 4.0) / 100 / math.sqrt(252), z=shocks)
    pb = _path(b[:-1] / 100 / math.sqrt(252), z=shocks)
    rep = s.vol_spread_test(days, a, b, pa, pb, n_boot=NB, n_placebo=200)
    assert rep["mean"] > 0 and rep["ci_deflated"][0] > 0 and rep["win_rate"] > 0.6 and all(h > 0 for h in rep["halves"])
    w, nr = rep["sides"]["wide"], rep["sides"]["narrow"]
    assert w["n"] >= 30 and nr["n"] >= 30 and w["mean"] < 0 < nr["mean"]
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["reason"].split(" — ")[-1].startswith("failed: wide side")
    # the symmetric planted world passes on both sides
    days, a, b, pa, pb = _spread_vol_world(True)
    ok = s.vol_spread_test(days, a, b, pa, pb, n_boot=NB, n_placebo=200)
    assert ok["sides"]["wide"]["mean"] > 0 and ok["sides"]["narrow"]["mean"] > 0 and ok["verdict"] == "supported"
    # a side below min_n cannot pass (not a failure unless decisive): inconclusive
    small = s.vol_spread_test(days, a, b, pa, pb, n_boot=NB, n_placebo=50, min_n=ok["sides"]["wide"]["n"] + 1)
    assert small["verdict"] == "inconclusive" and "below min_n" in small["reason"]


# ===================================================================================== T-239: VIX call hedge ==

def _vix_cycles(days):
    return s.rolling_cycles(s.sessions_for(days, s.vix_expiry_dates(days)))


def _hedge_frame(spike, cycles=240, seed=0, calendar=True):
    """SPY grinds up 0.8% a cycle and falls 20% in every 20th cycle; with ``spike`` VIX jumps to 80 on that cycle's last
    session. ``calendar``: the cycles are the VIX expiry calendar's; otherwise the 21-session grid from session 0."""
    n = 21 * cycles + 60
    days = _bdays("2009-09-18", n)
    cyc = _vix_cycles(days) if calendar else s.grid_cycles(n, 21)
    adj = np.full(n, 100.0)
    vix = np.full(n, 15.0)
    for c, (t, e) in enumerate(cyc):
        crash = c % 20 == 10
        ret = -0.20 if crash else 0.008
        L = e - t
        adj[t + 1:e + 1] = adj[t] * (1 + ret * np.arange(1, L + 1) / L)
        adj[e + 1:] = adj[e]
        if crash and spike:
            vix[e] = 80.0                                                # VIX spikes into the crash cycle's expiry
    return s.make_frame(days, adj.copy(), adj=adj, vix=vix, rate=np.full(n, 0.02),
                        extra={"vix3m": vix * 1.1, "vvix": np.full(n, 90.0)})


def test_vix_hedge_planted_passes():
    rep = s.vix_hedge_test(_hedge_frame(True), None, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["reduction"] > 0.25 and rep["calendar"].startswith("VIX monthly expiry")


def test_vix_hedge_null_fails():
    rep = s.vix_hedge_test(_hedge_frame(False), None, n_boot=NB)
    assert rep["verdict"] == "not_supported"
    assert rep["reduction"] < 0.0                                        # premium spent, nothing paid


def test_vix_hedge_effect_only_on_one_grid_phase_does_not_pass():
    # rule 10 regression (T-239): the crash and the VIX spike sit on the 21-session grid from session 0, so a call rolled
    # on that grid's offset 0 pays off (the old harness: supported). The claim's "rolling 1-month" call follows the VIX
    # expiry calendar, where the spike falls mid-cycle and has faded by expiry: the verdict must not be supported.
    fr = _hedge_frame(True, calendar=False)
    rep = s.vix_hedge_test(fr, None, n_boot=NB)
    g = {o["offset"]: o["reduction"] for o in rep["grid_offsets"]}
    assert g[0] > 0.25 and sum(x > 0.25 for x in g.values()) <= 2           # only the planted phase clears the target
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert "grid sensitivity" in rep["reason"]


def test_vix_expiry_calendar_matches_cboe_rules():
    hol = {"2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02",
           "2024-11-28", "2024-12-25", "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26"}
    days = [d for d in _bdays("2024-01-02", 400) if d not in hol]
    v = s.vix_expiry_dates(days)
    assert "2024-06-18" in v and "2024-06-19" not in v                   # Juneteenth Wednesday -> Tuesday
    assert "2025-03-18" in v and "2025-03-19" not in v                   # Good Friday 2025-04-18 -> 30 days before Thursday
    assert {"2024-01-17", "2024-02-14", "2024-03-20", "2024-12-18", "2025-01-22"} <= set(v)
    m = s.monthly_expiry_dates(days)
    assert "2025-04-17" in m and "2025-04-18" not in m                   # holiday third Friday -> prior session
    assert {"2024-01-19", "2024-03-15", "2024-12-20"} <= set(m)
    cyc = s.rolling_cycles(s.sessions_for(days, v))
    assert np.all(cyc[1:, 0] == cyc[:-1, 1])                              # rolled at each expiry: no gap, no overlap


def test_mdd_rows():
    assert s._mdd_rows([0.1, -0.5, 0.2])[0] == pytest.approx(0.5)
    assert s._mdd_rows([0.1, 0.1])[0] == pytest.approx(0.0)


def test_mdd_paths_chains_daily_paths_and_reduces_to_cycle_returns():
    r = np.array([0.1, -0.5, 0.2])
    assert s._mdd_paths(s._as_paths(r))[0] == pytest.approx(s._mdd_rows(r)[0])
    P = np.array([[0.7, 1.05], [1.0, 1.1]])                            # a 30% dip inside cycle 1 that recovers by its end
    assert s._mdd_paths(P)[0] == pytest.approx(0.30)
    assert s._mdd_rows(P[:, -1] - 1)[0] == pytest.approx(0.0)
    # ragged cycles padded with their end value chain to the same curve
    rag = s._pad_paths([np.array([0.9, 1.1]), np.array([0.8]), np.array([1.2, 0.95, 1.3])])
    flat = np.concatenate([[1.0], np.cumprod([1.1, 0.8, 1.3])])
    assert rag.shape == (3, 3) and np.allclose(rag[:, -1], [1.1, 0.8, 1.3])
    eq = [1.0, 0.9, 1.1, 1.1 * 0.8, 1.1 * 0.8 * 1.2, 1.1 * 0.8 * 0.95, 1.1 * 0.8 * 1.3]
    want = max(1 - x / max(eq[:i + 1]) for i, x in enumerate(eq))
    assert s._mdd_paths(rag)[0] == pytest.approx(want) and flat[-1] == pytest.approx(eq[-1])


def _dip_frame(vix_peak, cycles=200):
    """On the VIX expiry calendar: SPY falls 30% by session 10 of every 20th cycle and recovers to +0.8% by its end; VIX
    rises to ``vix_peak`` with the dip and is back at 15 on the expiry session, so the calls pay nothing at expiry."""
    n = 21 * cycles + 60
    days = _bdays("2009-09-18", n)
    adj, vix = np.full(n, 100.0), np.full(n, 15.0)
    for c, (t, e) in enumerate(_vix_cycles(days)):
        L = e - t
        j = np.arange(1, L + 1)
        if c % 20 == 10:
            adj[t + 1:e + 1] = adj[t] * (1 + np.where(j <= 10, -0.30 * j / 10, -0.30 + 0.308 * (j - 10) / (L - 10)))
            vix[t + 1:e] = 15 + (vix_peak - 15) * np.where(j[:-1] <= 10, j[:-1] / 10, (L - j[:-1]) / (L - 10))
        else:
            adj[t + 1:e + 1] = adj[t] * (1 + 0.008 * j / L)
        adj[e + 1:] = adj[e]
    return s.make_frame(days, adj.copy(), adj=adj, vix=vix, rate=np.full(n, 0.02),
                        extra={"vix3m": vix * 1.1, "vvix": np.full(n, 90.0)})


def test_vix_hedge_drawdown_is_measured_on_daily_equity():
    # regression (T-239): MDD used to be computed on cycle-end points only, which misses an intra-cycle crash (SPY's
    # Feb-Mar 2020 drawdown) and the daily mark-up of the held calls. Now both curves are daily.
    fr = _dip_frame(80.0)
    ov = s.vix_call_overlay(fr, cycles=_vix_cycles(fr["days"]))
    assert np.allclose(ov["path_hedged"][:, -1] - 1, ov["r_hedged"], atol=1e-12)      # daily marks end at the cycle return
    assert np.allclose(ov["path_spy"][:, -1] - 1, ov["r_spy"], atol=1e-12)
    assert s._mdd_rows(ov["r_spy"])[0] == pytest.approx(0.0)                          # cycle-end sampling sees no drawdown
    rep = s.vix_hedge_test(fr, None, n_boot=NB)
    assert rep["mdd_spy"] == pytest.approx(0.30, abs=1e-9) and rep["mdd_measure"] == "daily equity"
    assert rep["mdd_hedged"] < 0.25 and rep["reduction"] > 0.25 and rep["verdict"] == "supported", rep["reason"]
    json.dumps(s._clean(rep), allow_nan=False)
    flat = s.vix_hedge_test(_dip_frame(15.0), None, n_boot=NB)                        # no VIX move: calls never help
    assert flat["mdd_spy"] == pytest.approx(0.30, abs=1e-9) and flat["reduction"] <= 0 and flat["verdict"] == "not_supported"
    assert flat["reduction_cycle_end_sampling"] is None                               # undefined on cycle ends (MDD 0)


# ================================================================================ T-240: VVIX vs realised ==

def _vvix_world(vvix_level, n=21 * 230, seed=0):
    vix = _path(np.full(n - 1, 0.80 / math.sqrt(252)), seed, s0=20.0)
    return _bdays("2006-03-06", n), np.full(n, float(vvix_level)), vix


def test_vvix_win_rate_planted_passes():
    days, vv, vx = _vvix_world(120)
    rep = s.vvix_win_rate(days, vv, vx, n_boot=NB, n_placebo=50)
    assert rep["verdict"] == "supported", rep["reason"]


def test_vvix_win_rate_null_fails():
    days, vv, vx = _vvix_world(80)
    rep = s.vvix_win_rate(days, vv, vx, n_boot=NB, n_placebo=50)
    assert rep["verdict"] == "not_supported"
    assert 0.3 < rep["win_rate"] < 0.7


def test_vvix_win_rate_uses_calendar_months():
    # rule 10(a) (T-240): "non-overlapping months" are calendar months entered at their first session. VVIX is rich only
    # on each month's first session: the claim holds on the calendar, while the 21-session grid would mostly miss it.
    days, _, vx = _vvix_world(80)
    first = set(s.month_first(days).tolist())
    vv = np.array([120.0 if i in first else 60.0 for i in range(len(days))])
    rep = s.vvix_win_rate(days, vv, vx, n_boot=NB, n_placebo=50)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] >= 200 and rep["calendar"].startswith("calendar months") and rep["grid_pooled_rate"] < 0.2
    assert all(days[i][:7] != days[i - 1][:7] for i in s.month_first(days)[1:])


def test_vvix_win_rate_effect_only_on_one_grid_phase_does_not_pass():
    # rule 10 regression (T-240): VVIX is rich only on grid offset 0 (every 21st session): the old grid's offset 0 wins
    # every window, the calendar months almost never do.
    days, _, vx = _vvix_world(80)
    vv = np.where(np.arange(len(days)) % 21 == 0, 120.0, 60.0)
    rep = s.vvix_win_rate(days, vv, vx, n_boot=NB, n_placebo=50)
    g0 = next(g for g in rep["grid_offsets"] if g["offset"] == 0)
    assert g0["cp_lower"] > 0.7 and sum(g["cp_lower"] > 0.7 for g in rep["grid_offsets"]) == 1
    assert rep["verdict"] == "not_supported" and rep["win_rate"] < 0.3


def test_vvix_win_rate_skips_sessions_without_a_vvix_print():
    days, vv, vx = _vvix_world(120)
    vv = vv.copy()
    gap = [i for i, d in enumerate(days) if d[:7] == "2006-04"]
    vv[gap[:5]] = np.nan                                                   # April 2006's first five sessions have no VVIX
    rep = s.vvix_win_rate(days, vv, vx, n_boot=NB, n_placebo=20)
    assert rep["late_entries"] == [days[gap[5]]] and "1 month(s) entered after their first session" in rep["reason"]
    full = s.vvix_win_rate(days, np.where(np.isfinite(vv), vv, 120.0), vx, n_boot=NB, n_placebo=20)
    assert full["late_entries"] == [] and full["n"] == rep["n"]


# ====================================================================== T-249: forward variance premium ==

def _fwd_world(v3, n=63 * 66 + 64, seed=0):
    px = _path(np.full(n - 1, 0.15 / math.sqrt(252)), seed)
    return _bdays("2009-09-18", n), px, np.full(n, 16.0), np.full(n, float(v3))


def test_forward_variance_planted_passes():
    rep = s.forward_variance_premium(*_fwd_world(20.0), n_boot=NB, n_shift=20)
    assert rep["verdict"] == "supported", rep["reason_core"]


def test_forward_variance_null_fails():
    rep = s.forward_variance_premium(*_fwd_world(16.0), n_boot=NB, n_shift=20)
    assert rep["verdict"] == "not_supported", rep["reason_core"]


def test_forward_variance_effect_only_on_one_grid_phase_does_not_pass():
    # rule 10 regression (T-249): VIX3M is rich (a forward premium) only on the sessions of offset 0 of the 63-session
    # grid; that grid passes, the pooled all-offset estimate (primary) does not.
    days, px, vix, v3 = _fwd_world(16.0)
    v3 = v3.copy()
    v3[::63] = 20.0
    rep = s.forward_variance_premium(days, px, vix, v3, n_boot=NB, n_shift=20)
    offs = {o["offset"]: o for o in rep["grid_offsets"]}
    assert offs[0]["pass"] and offs[0]["mean"] > 0.3 and len(offs) == 63
    assert rep["ci_pooled"][0] < 0 < rep["ci_pooled"][1]
    assert rep["verdict"] == "not_supported", rep["reason_core"]
    assert rep["n"] >= 60 and rep["block_days"] == 126
    # even without any planted effect a few adjacent 63-session grids clear the bar by chance (~67 cycles each): the
    # reason has to report that spread
    null = s.forward_variance_premium(*_fwd_world(16.0), n_boot=NB, n_shift=20)
    assert null["verdict"] == "not_supported" and "offsets pass" in null["reason_core"]


# ================================================================================== T-511: weekend variance ==

def _weekend_world(mult, n=9000, seed=0):
    days = _bdays("1993-02-01", n)
    o = np.array([date.fromisoformat(d).toordinal() for d in days])
    gap = np.diff(o)
    sd = 0.01 * np.sqrt(np.where(gap == 3, mult, 1.0))
    return days, _path(sd, seed)


def test_weekend_ratio_planted_passes():
    days, px = _weekend_world(1.0)
    rep = s.weekend_variance_ratio(days, px, n_boot=NB)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["R"] == pytest.approx(1.0, abs=0.15)


def test_weekend_ratio_null_fails():
    days, px = _weekend_world(3.0)                                       # calendar-time variance: 3x over a weekend
    rep = s.weekend_variance_ratio(days, px, n_boot=NB)
    assert rep["verdict"] == "not_supported"
    assert rep["R"] == pytest.approx(3.0, rel=0.15)


def test_week_stats_labels_and_holidays():
    days = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-09"]   # Wed->Fri is a 2-day gap
    st = s._week_stats(days, np.array([100, 101, 100, 102, 101, 103.0]))
    assert st["n_weekend"] == 1 and st["n_weekday"] == 3


# ========================================================================= T-538: implied vs realised corr ==

def _corr_world(cor_level, rho=0.3, k=5, n=21 * 250 + 22, seed=0):
    rng = np.random.default_rng(seed)
    f = rng.standard_normal(n - 1)
    R = math.sqrt(rho) * f[None, :] + math.sqrt(1 - rho) * rng.standard_normal((k, n - 1))
    px = 100 * np.exp(np.concatenate([np.zeros((k, 1)), np.cumsum(0.01 * R, axis=1)], axis=1))
    return _bdays("2006-01-03", n), np.full(n, float(cor_level)), px


def test_realised_avg_corr_matches_equicorrelation():
    days, _, px = _corr_world(30.0, n=20001)
    lr = np.diff(np.log(px), axis=1).T
    assert s.realised_avg_corr(lr) == pytest.approx(0.3, abs=0.03)


def test_implied_corr_planted_and_null_with_constituents():
    days, cor, px = _corr_world(60.0)
    rep = s.implied_vs_realised_corr(days, cor, px, list("ABCDE"), n_boot=NB, constituents=True)
    # the correlation criterion passes; the claim's straddle-book P&L clause needs chains, so the cap is inconclusive
    assert rep["verdict"] == "inconclusive" and rep["ci95"][0] > 0
    assert rep["reason"].split(" — ")[-1].startswith("implemented criteria pass")
    days, cor, px = _corr_world(30.0)
    rep0 = s.implied_vs_realised_corr(days, cor, px, list("ABCDE"), n_boot=NB, constituents=True)
    assert rep0["verdict"] == "not_supported"


def test_implied_corr_effect_only_on_one_grid_phase_does_not_pass():
    # rule 10 regression (T-538): COR1M is rich only on grid offset 0's sessions (and slightly below the realised 0.3
    # elsewhere). Offset 0's grid passes; the pooled estimate (primary) does not.
    days, cor, px = _corr_world(28.0)
    cor = cor.copy()
    cor[::21] = 60.0
    rep = s.implied_vs_realised_corr(days, cor, px, list("ABCDE"), n_boot=NB, constituents=True)
    offs = {o["offset"]: o for o in rep["grid_offsets"]}
    assert offs[0]["pass"] and sum(o["pass"] for o in rep["grid_offsets"]) == 1
    assert rep["verdict"] == "not_supported" and rep["ci95"][0] < 0 < offs[0]["ci"][0], rep["reason"]
    assert rep["n"] == 251 and rep["block_days"] == 126                  # = the old offset-0 grid's window count


def test_implied_corr_sector_proxy_caps_at_inconclusive():
    days, cor, px = _corr_world(60.0)
    rep = s.implied_vs_realised_corr(days, cor, px, list("ABCDE"), n_boot=NB)
    assert rep["verdict"] == "inconclusive" and rep["ci95"][0] > 0
    assert "NOT an acceptable stand-in" in rep["reason"]


# ===================================================================================== harness contract ==

def test_maps_are_consistent():
    assert set(s.THEORY_MAP.values()) == set(s.HARNESSES)
    assert set(s.THEORY_MAP) == {"T-159", "T-227", "T-228", "T-229", "T-237", "T-239", "T-240", "T-249", "T-511", "T-538"}
    assert all(k.startswith("b6_surf_") and k == k.lower() for k in s.HARNESSES)


@pytest.mark.parametrize("name", sorted(s.HARNESSES))
def test_every_harness_reports_missing_bundles(name):
    stat, n, verdict, reason = s.HARNESSES[name](FakeArchive())
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason
    json.dumps(stat, allow_nan=False)


def test_weekend_harness_end_to_end_on_a_fake_archive():
    days, px = _weekend_world(1.0)
    arch = FakeArchive({s.SPY_B: _price_rows(days, px)})
    stat, n, verdict, reason = s.b6_surf_weekend_variance(arch)
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported" and n == stat["n"] >= 1500 and " — " in reason


def test_vvix_harness_end_to_end_on_a_fake_archive():
    days, vv, vx = _vvix_world(80)
    arch = FakeArchive({s.VIX_B: _index_rows(days, vx), s.VVIX_B: _index_rows(days, vv)})
    stat, n, verdict, reason = s.b6_surf_vvix_vs_realised(arch)
    json.dumps(stat, allow_nan=False)
    assert verdict == "not_supported" and n >= 200 and reason.split(" — ")[-1].startswith("failed")


def test_implied_correlation_harness_end_to_end_on_a_fake_archive():
    days, cor, px = _corr_world(60.0, k=len(s.SECTORS_LEGACY))
    b = {s.COR1M_B: _index_rows(days, cor)}
    for i, sym in enumerate(s.SECTORS_LEGACY):
        b[f"daily-history-{sym}"] = _price_rows(days, px[i])
    stat, n, verdict, reason = s.b6_surf_implied_correlation(FakeArchive(b))
    json.dumps(stat, allow_nan=False)
    assert verdict == "inconclusive" and n >= 240 and stat["sectors_not_used"]["XLC"] == "not archived"
