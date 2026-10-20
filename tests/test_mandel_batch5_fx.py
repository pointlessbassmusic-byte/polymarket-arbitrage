"""Batch-5 FX carry and momentum harnesses (group 'fx') on synthetic data: planted effects pass, nulls do not.

No network and no archive: every market here is simulated (an in-memory fake archive stands in for the bundle store
in the end-to-end tests). Carry plants uncovered-interest-parity failure (spot driftless, so high-rate currencies earn
their differential); its null makes UIP hold exactly. Momentum plants persistent monthly drifts; its null is iid."""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch5_fx as fx


# ------------------------------------------------------------------------ fixtures --

def _bdays(start, end):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DAYS = _bdays("1998-01-01", "2026-10-09")
G10_RATES = {"USD": 1.0, "EUR": 0.0, "GBP": 2.0, "AUD": 6.0, "NZD": 7.0, "JPY": -0.5, "CHF": -0.2, "CAD": 3.0,
             "NOK": 5.0, "SEK": 1.5}
EM_RATES = {**G10_RATES, "MXN": 9.0, "ZAR": 8.0}


def make_market(rates, *, uip=False, phi=0.0, mu_sd=0.0, noise_m=0.012, seed=0, rate_months=("1990-01", "2026-09")):
    """(spot value dicts, rate value dicts). Constant OECD rates; daily log spot = monthly drift / days in month +
    noise. ``uip`` sets the drift to -(r_c - r_USD)/1200 a month (UIP holds); ``phi``/``mu_sd`` add an AR(1) monthly
    drift per currency (momentum)."""
    rng = np.random.default_rng(seed)
    months = [d[:7] for d in DAYS]
    um = sorted(set(months))
    pos = {m: i for i, m in enumerate(um)}
    idx = np.array([pos[m] for m in months])
    per = np.bincount(idx)[idx]
    spot = []
    for c in rates:
        if c == "USD":
            continue
        drift = np.zeros(len(um))
        if uip:
            drift -= (rates[c] - rates["USD"]) / 1200.0
        if phi:
            mu = np.empty(len(um))
            mu[0] = rng.normal(0, mu_sd)
            for t in range(1, len(um)):
                mu[t] = phi * mu[t - 1] + math.sqrt(1 - phi ** 2) * mu_sd * rng.normal()
            drift += mu
        lr = drift[idx] / per + rng.normal(0, noise_m / math.sqrt(21), len(DAYS))
        s = np.exp(np.cumsum(lr)) * (0.5 + rng.random())
        spot += [{"day": d, "ccy": c, "usd_per_unit": float(x)} for d, x in zip(DAYS, s)]
    rr = [{"month": m, "ccy": c, "rate3m": r} for c, r in rates.items() for m in fx.mrange(*rate_months)]
    return spot, rr


class _Entry:
    def __init__(self, created_at):
        self.created_at = created_at


class FakeArchive:
    """In-memory stand-in for the bundle store: get() raises KeyError for a missing bundle."""

    def __init__(self, bundles, created_at="2026-10-15T00:00:00+00:00"):
        self.b, self.cap = bundles, created_at

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(self.cap)

    def load(self, name):
        return iter(self.b[name])


def fake_archive(spot, rates, extra_spot=()):
    s = [{"available_at": v["day"] + "T21:00:00+00:00", "value": v} for v in spot]
    s += [{"available_at": at, "value": v} for v, at in extra_spot]
    r = [{"available_at": v["month"] + "-28T00:00:00+00:00", "value": v} for v in rates]
    return FakeArchive({fx.SPOT_BUNDLE: s, fx.RATE_BUNDLE: r})


@pytest.fixture(scope="module")
def carry_planted():
    return fx.build_panel(*make_market(G10_RATES, seed=1), fill_to="2026-08")


@pytest.fixture(scope="module")
def carry_null():
    return fx.build_panel(*make_market(G10_RATES, uip=True, seed=2), fill_to="2026-08")


@pytest.fixture(scope="module")
def mom_planted():
    return fx.build_panel(*make_market(G10_RATES, phi=0.9, mu_sd=0.015, noise_m=0.015, seed=3), fill_to="2026-08")


@pytest.fixture(scope="module")
def mom_null():
    return fx.build_panel(*make_market(G10_RATES, noise_m=0.02, seed=4), fill_to="2026-08")


def _tiny_panel(end_spots, rates, daily=None):
    """Hand-built panel: end_spots {ccy: {month: spot}}, rates {ccy: {month: pct}}."""
    first = {c: dict(v) for c, v in end_spots.items()}
    end_day = {c: {m: m + "-28" for m in v} for c, v in end_spots.items()}
    return {"end": end_spots, "end_day": end_day, "first": first, "daily": daily or {}, "rates": rates,
            "filled": {}, "gaps": {}, "last_day": "2030-01-01"}


# ------------------------------------------------------------------------ months and panel --

def test_month_helpers():
    assert fx.madd("2013-01", -2) == "2012-11"
    assert fx.madd("2012-12", 1) == "2013-01"
    assert fx.mrange("2012-11", "2013-02") == ["2012-11", "2012-12", "2013-01", "2013-02"]


def test_build_panel_complete_months_first_fix_and_fills():
    spot = [{"day": d, "ccy": "EUR", "usd_per_unit": 1.0 + i / 100} for i, d in enumerate(_bdays("2026-08-03", "2026-10-09"))]
    rates = [{"month": m, "ccy": "EUR", "rate3m": 2.0} for m in ("2025-11", "2025-12", "2026-01")]
    rates += [{"month": m, "ccy": "USD", "rate3m": 4.0} for m in ("2026-01", "2026-03")]          # 2026-02 is a gap
    p = fx.build_panel(spot, rates, fill_to="2026-04")
    assert "2026-09" in p["end"]["EUR"] and "2026-10" not in p["end"]["EUR"]                     # October incomplete
    assert p["first"]["EUR"]["2026-10"] == pytest.approx(p["daily"]["EUR"][1][p["daily"]["EUR"][0].index("2026-10-01")])
    assert p["end_day"]["EUR"]["2026-09"] == "2026-09-30"
    assert p["filled"]["EUR"] == ["2026-02", "2026-03", "2026-04"] and p["rates"]["EUR"]["2026-04"] == 2.0
    assert p["gaps"]["USD"] == ["2026-02"] and p["filled"]["USD"] == ["2026-04"]


def test_values_drop_rows_not_available_at_capture():
    spot, rates = make_market({"USD": 1.0, "EUR": 2.0}, seed=0)
    late = ({"day": "2026-10-12", "ccy": "EUR", "usd_per_unit": 99.0}, "2026-10-20T21:00:00+00:00")
    a = fake_archive(spot, rates, extra_spot=[late])
    vals = fx._values(a, fx.SPOT_BUNDLE)
    assert max(v["day"] for v in vals) == "2026-10-09"


# ------------------------------------------------------------------------ carry engine --

def test_carry_ranks_on_one_month_lagged_rate():
    ms = fx.mrange("2019-01", "2020-06")
    spots = {c: {m: 1.0 for m in ms} for c in ("AAA", "BBB", "CCC")}
    rates = {"USD": {m: 1.0 for m in ms}, "AAA": {m: 5.0 for m in ms}, "BBB": {m: 3.0 for m in ms},
             "CCC": {m: (0.0 if m < "2020-03" else 9.0) for m in ms}}                             # CCC jumps in 2020-03
    p = _tiny_panel(spots, rates)
    u = ["USD", "AAA", "BBB", "CCC"]
    bt = fx.carry_backtest(p, u, ["2020-04", "2020-05"], k=1)
    # H=2020-04 is decided at the end of 2020-03 on the 2020-02 rate: CCC still lowest
    assert bt["short"][0] == ["CCC"] and bt["long"][0] == ["AAA"]
    # H=2020-05 ranks on the 2020-03 rate: CCC now highest
    assert bt["long"][1] == ["CCC"]
    # flat spots: AAA long earns its differential at the month-M rate, short CCC pays its own
    assert bt["gross"][0] == pytest.approx((5.0 - 1.0) / 1200 - (9.0 - 1.0) / 1200)


def test_carry_costs_turnover_and_financing_usd_exempt():
    ms = fx.mrange("2019-01", "2019-12")
    spots = {c: {m: 1.0 for m in ms} for c in ("AAA", "BBB", "CCC")}
    rates = {"USD": {m: 0.0 for m in ms}, "AAA": {m: 5.0 for m in ms}, "BBB": {m: 2.0 for m in ms}, "CCC": {m: 1.0 for m in ms}}
    p = _tiny_panel(spots, rates)
    u = ["USD", "AAA", "BBB", "CCC"]
    bt = fx.carry_backtest(p, u, fx.mrange("2019-03", "2019-06"), k=1, cost_bps={c: 2.0 for c in u[1:]},
                           admin={c: 0.01 for c in u[1:]})
    assert bt["long"][0] == ["AAA"] and bt["short"][0] == ["USD"]                                # USD is the funder
    assert bt["turnover"].tolist() == [1.0, 0.0, 0.0, 0.0]                                       # USD leg trades nothing
    assert bt["trade_cost"][0] == pytest.approx(2e-4)
    assert np.allclose(bt["fin_cost"], 0.01 / 12)                                                 # one non-USD unit held
    assert np.allclose(bt["net"], 5.0 / 1200 - bt["trade_cost"] - 0.01 / 12)


def test_invvol_weights_and_usd_member_kept_as_cash():
    order = ["AAA", "USD", "BBB", "CCC", "DDD", "EEE"]
    w = fx._carry_weights(order, 3, "invvol", {"AAA": 0.01, "BBB": 0.02, "CCC": 0.01, "DDD": 0.01, "EEE": 0.02}, order)
    assert w["USD"] == pytest.approx(1 / 3)
    assert w["AAA"] == pytest.approx(2 / 3 * 2 / 3) and w["BBB"] == pytest.approx(2 / 3 * 1 / 3)
    assert w["CCC"] + w["DDD"] + w["EEE"] == pytest.approx(-1.0) and w["EEE"] == pytest.approx(-0.2)
    r = fx._carry_weights(order, 3, "rank", {}, order)
    assert sum(v for v in r.values() if v > 0) == pytest.approx(1.0) and r["AAA"] > r["USD"] > 0 > r["DDD"] > r["EEE"]


def test_carry_backtest_planted_earns_spread_and_uip_null_does_not(carry_planted, carry_null):
    cb, ad = fx.g10_costs()
    ms = fx.mrange("2013-01", "2026-09")
    pl = fx.carry_backtest(carry_planted, fx.G10, ms, cost_bps=cb, admin=ad)
    nu = fx.carry_backtest(carry_null, fx.G10, ms, cost_bps=cb, admin=ad)
    assert pl["long"][0] == ["AUD", "NZD", "NOK"] and pl["short"][0] == ["EUR", "JPY", "CHF"]
    assert pl["net"].mean() > 0.003 and fx._sr(pl["net"], 12) > 0.8
    assert nu["net"].mean() < 0 and fx._sr(nu["net"], 12) < 0.3


def test_carry_report_planted_supported(carry_planted):
    cb, ad = fx.g10_costs()
    rep = fx.carry_report(carry_planted, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", n_boot=1000)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] == 165 and rep["test_window"] == ["2013-01", "2026-09"]
    assert rep["weight_selection"]["train"]["equal"]["first"] == "2002-05"
    assert rep["reason"].endswith("— all criteria pass")


def test_carry_report_uip_null_not_supported(carry_null):
    cb, ad = fx.g10_costs()
    rep = fx.carry_report(carry_null, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", n_boot=1000)
    assert rep["verdict"] == "not_supported"
    assert "net Sharpe" in rep["reason"] and "failed:" in rep["reason"]


def test_carry_report_short_window_inconclusive(carry_planted):
    cb, ad = fx.g10_costs()
    rep = fx.carry_report(carry_planted, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10",
                          test=("2024-01", "2026-09"), n_boot=200)
    assert rep["verdict"] == "inconclusive" and "need 150" in rep["reason"]


def test_carry_report_flags_stale_rate_splice():
    spot, rates = make_market(G10_RATES, seed=5)
    rates = [r for r in rates if not (r["ccy"] in ("EUR", "GBP") and r["month"] > "2026-01")]
    p = fx.build_panel(spot, rates, fill_to="2026-08")
    cb, ad = fx.g10_costs()
    rep = fx.carry_report(p, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", n_boot=200)
    assert rep["spliced_rates"]["EUR"][0] == "2026-02" and rep["spliced_rates"]["GBP"][-1] == "2026-08"
    assert rep["sharpe_before_splice"]["through"] == "2026-02"
    assert "EUR 2026-02..2026-08 (7 mo)" in rep["reason"]


def _vix_hot_before(holding_months):
    """Synthetic VIX {day: close}: 45 on every day of the decision month M = H-1 of each listed holding month H,
    15 elsewhere, so the VIX > 30 filter goes flat for exactly those H."""
    hot = {fx.madd(h, -1) for h in holding_months}
    return {d: (45.0 if d[:7] in hot else 15.0) for d in DAYS}


def _extreme_months(panel, months, n, worst=True):
    cb, ad = fx.g10_costs()
    bt = fx.carry_backtest(panel, fx.G10, months, cost_bps=cb, admin=ad)
    order = np.argsort(bt["gross"])
    pick = order[:n] if worst else order[-n:]
    return [bt["months"][i] for i in pick]


def test_choose_weighting_freezes_vix_filter_when_it_wins_training(carry_planted):
    # Regression (T-368 reviewer finding): the walk-forward chooses weights AND filters, so a VIX > 30 filter that
    # sidesteps the worst training months must be frozen for the test book, not dropped.
    cb, ad = fx.g10_costs()
    tr, te = fx.mrange(*fx.CARRY_TRAIN), fx.mrange(*fx.CARRY_TEST)
    vix = _vix_hot_before(_extreme_months(carry_planted, tr, 12) + _extreme_months(carry_planted, te, 6))
    sel = fx.choose_weighting(carry_planted, fx.G10, fx.CARRY_TRAIN, cb, ad, vix=vix)
    t = sel["train"]
    assert set(t) == {"equal", "invvol", "equal+vix30", "invvol+vix30"} and t["equal+vix30"]["flat_months"] == 12
    assert t["equal+vix30"]["sharpe"] > t["equal"]["sharpe"]
    assert sel["filter"] == "vix30" and sel["chosen_book"] == max(t, key=lambda k: t[k]["sharpe"])
    rep = fx.carry_report(carry_planted, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", vix=vix, n_boot=500)
    frozen = fx.carry_backtest(carry_planted, fx.G10, te, weighting=rep["weighting"], cost_bps=cb, admin=ad, vix=vix)
    assert rep["filter"] == "vix30" and rep["flat_months"] == 6 == sum(frozen["flat"])
    assert rep["sharpe"] == pytest.approx(fx._sr(frozen["net"], 12))                              # the test book is filtered
    alt = fx.carry_backtest(carry_planted, fx.G10, te, weighting=rep["alt_weighting"], cost_bps=cb, admin=ad, vix=vix)
    assert rep["alt_weighting_test_sharpe"] == pytest.approx(fx._sr(alt["net"], 12))              # same filter on the alt
    assert f"weights {rep['weighting']} + VIX > 30 filter chosen" in rep["reason"] and "flat in 6 of 165" in rep["reason"]


def test_choose_weighting_keeps_unfiltered_book_when_filter_loses_or_ties(carry_planted):
    cb, ad = fx.g10_costs()
    tr, te = fx.mrange(*fx.CARRY_TRAIN), fx.mrange(*fx.CARRY_TEST)
    hurts = _vix_hot_before(_extreme_months(carry_planted, tr, 12, worst=False) + _extreme_months(carry_planted, te, 6))
    calm = {d: 15.0 for d in DAYS}                                                                # filter never binds
    for vix in (hurts, calm):
        sel = fx.choose_weighting(carry_planted, fx.G10, fx.CARRY_TRAIN, cb, ad, vix=vix)
        assert sel["filter"] == "none" and sel["filter_evaluated"]
        rep = fx.carry_report(carry_planted, universe=fx.G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", vix=vix, n_boot=500)
        plain = fx.carry_backtest(carry_planted, fx.G10, te, weighting=rep["weighting"], cost_bps=cb, admin=ad)
        assert rep["filter"] == "none" and rep["flat_months"] == 0
        assert rep["sharpe"] == pytest.approx(fx._sr(plain["net"], 12))
        assert "no filter, chosen" in rep["reason"]
    sel = fx.choose_weighting(carry_planted, fx.G10, fx.CARRY_TRAIN, cb, ad)                       # no VIX bundle
    assert sel["filter"] == "none" and not sel["filter_evaluated"] and set(sel["train"]) == {"equal", "invvol"}


def test_harness_carry_g10_freezes_vix_filter_from_archive():
    spot, rates = make_market(G10_RATES, seed=11)
    panel = fx.build_panel(spot, rates, fill_to="2026-08")
    vix = _vix_hot_before(_extreme_months(panel, fx.mrange(*fx.CARRY_TRAIN), 12) + _extreme_months(panel, fx.mrange(*fx.CARRY_TEST), 4))
    a = fake_archive(spot, rates)
    a.b[fx.VIX_BUNDLE] = [{"available_at": d + "T21:00:00+00:00", "value": {"day": d, "close": x}} for d, x in vix.items()]
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_carry_g10(a)
    assert stat["filter"] == "vix30" and stat["flat_months"] == 4 and n == 165, why
    assert "+ VIX > 30 filter chosen" in why and v == "supported"
    fx._CACHE.clear()


def test_em_timeseries_planted_and_null():
    ms = fx.mrange("2010-01", "2014-12")
    cb, ad = fx.em_costs()
    flat = {c: {m: 1.0 for m in ms} for c in fx.EM}
    hi = _tiny_panel(flat, {"USD": {m: 1.0 for m in ms}, "MXN": {m: 8.0 for m in ms}, "ZAR": {m: 7.0 for m in ms}})
    lo = _tiny_panel(flat, {"USD": {m: 1.0 for m in ms}, "MXN": {m: 3.0 for m in ms}, "ZAR": {m: 2.0 for m in ms}})
    a = fx.em_timeseries(hi, fx.mrange("2010-03", "2014-12"), 3.0, cb, ad)
    b = fx.em_timeseries(lo, fx.mrange("2010-03", "2014-12"), 3.0, cb, ad)
    assert a["net"][1:].mean() == pytest.approx(((7 + 6) / 2) / 1200 - (0.01 + 0.02) / 2 / 12)
    assert np.all(b["net"] == 0.0)


# ------------------------------------------------------------------------ momentum --

def test_momentum_eligibility_skip_day_and_thirds():
    ms = fx.mrange("2000-01", "2000-06")
    u = ["A", "B", "C", "D", "E", "F", "G"]
    end = {c: {m: 1.0 + 0.01 * i * (j + 1) for j, m in enumerate(ms)} for i, c in enumerate(u)}
    rates = {c: {m: 1.0 for m in ms} for c in u + ["USD"]}
    del rates["G"]                                                                                # G has no rate history
    p = _tiny_panel(end, rates)
    bt = fx.momentum_backtest(p, u, ["2000-04"], 1, "thirds", True, 5.0, True)
    assert bt["n_elig"] == [6] and "G" not in bt["detail"][0][1]
    assert bt["long"][0] == ["F", "E"] and bt["short"][0] == ["B", "A"]                          # k = 6 // 3 = 2
    f = p["first"]
    exp = (f["F"]["2000-05"] / f["F"]["2000-04"] + f["E"]["2000-05"] / f["E"]["2000-04"]
           - f["B"]["2000-05"] / f["B"]["2000-04"] - f["A"]["2000-05"] / f["A"]["2000-04"]) / 2
    assert bt["gross"][0] == pytest.approx(exp)
    assert bt["net"][0] == pytest.approx(exp - 2.0 * 5e-4)                                       # entry: 2 units traded
    bt2 = fx.momentum_backtest(p, u, ["2000-04"], 1, "thirds", True, 5.0, True, min_elig=7)
    assert bt2["months"] == [] and bt2["dropped"] == ["2000-04"]


def test_momentum_report_planted_supported(mom_planted):
    rep = fx.momentum_report(mom_planted, n_perm=300, n_boot=1000)
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["n"] == 333 and rep["window"] == ["1999-01", "2026-09"]
    assert rep["mean_bps"] > 0 and rep["ci_bps"][0] > 0 and rep["perm_pctile"] > 95


def test_momentum_report_null_not_supported(mom_null):
    rep = fx.momentum_report(mom_null, n_perm=300, n_boot=1000)
    assert rep["verdict"] == "not_supported"
    assert rep["mean_bps"] < 0                                                                   # costs on a zero edge


def test_momentum_report_too_few_months_inconclusive(mom_planted):
    rep = fx.momentum_report(mom_planted, window=("2010-01", "2026-09"), n_perm=50, n_boot=200)
    assert rep["verdict"] == "inconclusive" and "need 300" in rep["reason"]


def test_permutation_null_planted_beats_q95_and_null_does_not(mom_planted, mom_null):
    ms = fx.mrange("1999-01", "2026-09")
    for panel, should_beat in ((mom_planted, True), (mom_null, False)):
        bt = fx.momentum_backtest(panel, fx.G10_FX, ms)
        pn, pg = fx.permutation_null(bt["detail"], fx.G10_FX, 5.0, 300, seed=1)
        assert abs(np.median(pg)) < 5e-4                                                         # random books ~ 0 gross
        assert bool(bt["net"].mean() > np.quantile(pn, 0.95)) is should_beat


# ------------------------------------------------------------------------ statistics --

def test_stationary_bootstrap_sharpe_planted_and_null():
    rng = np.random.default_rng(7)
    pl = rng.normal(0.01, 0.02, 240)                                                             # annual Sharpe ~1.7
    nu = rng.normal(0.0, 0.02, 240)
    bp = fx.stationary_boot_sharpe(pl, 12, 12.0, 2000, 0)
    bn = fx.stationary_boot_sharpe(nu, 12, 12.0, 2000, 0)
    assert np.quantile(bp, 0.025) > 0
    assert np.quantile(bn, 0.025) < 0 < np.quantile(bn, 0.975)
    assert abs(np.median(bp) - fx._sr(pl, 12)) < 0.25


def test_family_dsr_floor_and_planted_vs_null():
    rng = np.random.default_rng(8)
    pl, nu = rng.normal(0.01, 0.02, 200), rng.normal(0.0, 0.02, 200)
    d = fx.family_dsr(pl, [0.1, 0.11, 0.12], 6)
    assert d["var_trials_sr"] == pytest.approx(1 / 199)                                          # floored
    assert d["dsr"] > 0.95
    assert fx.family_dsr(nu, [0.0, 0.05, -0.05], 6)["dsr"] < 0.95


def test_nw_tstat_and_skew():
    rng = np.random.default_rng(9)
    assert fx.nw_tstat(rng.normal(0.5, 1, 400)) > 5
    assert abs(fx.nw_tstat(rng.normal(0, 1, 400))) < 3
    assert fx.skewness(np.r_[np.zeros(50), -5.0]) < -3


# ------------------------------------------------------------------------ harnesses end to end --

def test_harness_carry_g10_planted_and_null_on_fake_archive():
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_carry_g10(fake_archive(*make_market(G10_RATES, seed=11)))
    assert v == "supported" and n == 165, why
    assert stat["family_sharpes_ann"]["vix30_filter"] is None                                    # no VIX bundle here
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_carry_g10(fake_archive(*make_market(G10_RATES, uip=True, seed=12)))
    assert v == "not_supported" and " — failed:" in why


def test_harness_carry_em_planted_supported():
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_carry_em(fake_archive(*make_market(EM_RATES, seed=13)))
    assert v == "supported", why
    assert stat["last_positions"]["long"] == ["NZD", "MXN", "ZAR"]
    assert stat["costs"]["admin_per_year"]["ZAR"] == 0.02 and stat["costs"]["trade_bps"]["MXN"] == 5.0
    assert stat["dsr_detail"]["n_trials"] == 10 and stat["family_sharpes_ann"]["em:plus_krw_research"] is None


def test_harness_momentum_planted_and_null():
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_momentum_g10(fake_archive(*make_market(G10_RATES, phi=0.9, mu_sd=0.015, noise_m=0.015, seed=14)))
    assert v == "supported" and n == 333, why
    fx._CACHE.clear()
    stat, n, v, why = fx.fx_momentum_g10(fake_archive(*make_market(G10_RATES, noise_m=0.02, seed=15)))
    assert v == "not_supported"


def test_harness_missing_bundles_inconclusive():
    for h in fx.HARNESSES.values():
        stat, n, v, why = h(FakeArchive({}))
        assert v == "inconclusive" and n == 0 and "missing data bundles" in why


def test_registry_maps():
    assert set(fx.THEORY_MAP) == {"T-368", "T-431", "T-478"}
    assert all(name in fx.HARNESSES and name.startswith("fx_") for name in fx.THEORY_MAP.values())
