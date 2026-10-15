"""Batch 6a, group var: variance risk premium and short-premium harnesses on synthetic data only (no archive, no
network). Each core function gets a planted effect that passes and a null that does not."""

import json
import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch6_var as v
from mandel.options import bs

NB = 400            # bootstrap draws in tests (the harnesses use 2,000 to 20,000)


# ===================================================================================================== fixtures ==

def _bdays(start: str, n: int) -> list:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _gbm(days, sigma, seed=0, s0=100.0):
    """Martingale GBM on business days: each log return spans the calendar gap, variance sigma^2 * gap / 365."""
    rng = np.random.default_rng(seed)
    o = np.array([date.fromisoformat(d).toordinal() for d in days], dtype=float)
    gap = np.diff(o) / 365.0
    sig = np.broadcast_to(np.asarray(sigma, dtype=float), (len(days),))[:-1]
    lr = -0.5 * sig ** 2 * gap + sig * np.sqrt(gap) * rng.standard_normal(gap.size)
    return s0 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))


def _frame(n, vix_level, true_vol, seed=0, start="1990-01-02"):
    days = _bdays(start, n)
    return v.make_frame(days, _gbm(days, true_vol, seed), np.full(n, float(vix_level)))


def _iid_closes(n, daily_sd, seed=0, s0=100.0):
    rng = np.random.default_rng(seed)
    return s0 * np.exp(np.concatenate([[0.0], np.cumsum(daily_sd * rng.standard_normal(n - 1))]))


# =================================================================================================== statistics ==

def test_stud_ci_planted_and_null():
    rng = np.random.default_rng(1)
    lo, hi = v.stud_ci(0.4 + rng.standard_normal(300), 5, 0.95, NB)
    assert lo > 0
    lo, hi = v.stud_ci(rng.standard_normal(300), 5, 0.95, NB)
    assert lo < 0 < hi
    assert v.stud_ci(np.full(20, 2.0), 3, 0.95, NB) == (2.0, 2.0)
    assert v.stud_ci(np.array([1.0, 2.0]), 3) == (None, None)


def test_group_diff_planted_and_null():
    rng = np.random.default_rng(2)
    n = 400
    lab = rng.integers(0, 3, n)
    x = rng.standard_normal(n) + np.where(lab == 2, 0.6, 0.0)
    r = v.stud_ci_group_diff(x, lab == 2, lab == 0, 6, 0.95, NB)
    assert r["diff"] > 0 and r["ci"][0] > 0 and r["ci_percentile"][0] > 0
    x0 = rng.standard_normal(n)
    r0 = v.stud_ci_group_diff(x0, lab == 2, lab == 0, 6, 0.95, NB)
    assert r0["ci"][0] < 0 < r0["ci"][1]


def test_sharpe_diff_planted_and_null():
    rng = np.random.default_rng(3)
    b = 0.1 + rng.standard_normal(400)
    planted = v.sharpe_diff_test(b + 0.4, b, 6, NB)
    assert planted["diff"] > 0 and planted["p"] < 0.05
    null = v.sharpe_diff_test(0.1 + rng.standard_normal(400), b, 6, NB)
    assert null["p"] > 0.05


def test_mdd_and_ladder_verdict_planted_and_null():
    rng = np.random.default_rng(4)
    single = 0.0002 + 0.01 * rng.standard_normal(3000)
    single[1500:1520] -= 0.03                                            # one crash in each half
    single[400:420] -= 0.03
    planted = v.ladder_verdict(0.5 * single, single, 63, NB)
    assert abs(planted["full"]["ratio"] - 0.5) < 1e-9
    assert all(ok for _, ok, _ in planted["crit"])
    null = v.ladder_verdict(single.copy(), single, 63, NB)
    assert abs(null["full"]["ratio"] - 1.0) < 1e-9
    assert not any(ok for _, ok, _ in null["crit"])
    assert v._mdd_abs(np.array([1.0, -2.0, 0.5, -1.0]))[0] == pytest.approx(2.5)


def test_decide_below_min_n():
    v1, _ = v._decide([("x", False, False)], 10, 100, "cycles")
    assert v1 == "inconclusive"                                          # failing, not decisively, below min_n
    v2, _ = v._decide([("x", False, True)], 10, 100, "cycles")
    assert v2 == "not_supported"                                         # decisive failure counts below min_n
    v3, _ = v._decide([("x", True, False)], 10, 100, "cycles")
    assert v3 == "inconclusive"                                          # a pass below min_n cannot confirm
    v4, _ = v._decide([("x", True, False)], 100, 100, "cycles")
    assert v4 == "supported"


# ================================================================================================== market data ==

def test_rates_prior_print_and_discount_conversion():
    assert v.dtb3_continuous(0.0) == 0.0
    d = 5.0
    r = v.dtb3_continuous(d)
    assert r == pytest.approx(-math.log(1 - 0.05 * 91 / 360) / (91 / 365))
    assert r > 0.05                                                      # a discount yield understates the rate
    rates = v.bill_rates(["2020-01-02", "2020-01-03", "2020-01-06"], {"2020-01-02": 1.0, "2020-01-03": 2.0})
    assert rates[0] == pytest.approx(v.dtb3_continuous(1.0))             # before any prior print: the first print
    assert rates[1] == pytest.approx(v.dtb3_continuous(1.0))             # the same day's print is not yet published
    assert rates[2] == pytest.approx(v.dtb3_continuous(2.0))


def test_dividends_from_adjclose_step_and_forecast():
    close = np.array([100.0, 101.0, 99.0, 100.0, 102.0, 101.0])
    D = 1.0                                                              # 1.00 goes ex on day 2, 0.5 on day 5
    f = np.ones(6)
    f[:2] = 1 - D / close[1]
    f[:5] *= 1 - 0.5 / close[4]
    div = v.dividends(close, close * f)
    assert div[2] == pytest.approx(1.0) and div[5] == pytest.approx(0.5)
    assert np.count_nonzero(div) == 2
    fc = v.div_forecast(div)
    assert list(fc) == pytest.approx([1.0, 1.0, 1.0, 1.0, 1.0, 0.5])    # point in time: last paid (the first before any)


# =========================================================================================== straddle engines ==

def test_hedged_straddle_matched_vol_is_fair_and_unmatched_is_not():
    fr = _frame(4300, 20.0, 0.20, seed=5)                                # implied = realised
    r = v.straddle_cycles(fr, 1.0, side=1, hedge=True)
    y = r["pnl"] / r["vega"]
    assert abs(y.mean()) < 3 * y.std(ddof=1) / math.sqrt(y.size)         # mean hedged P&L ~ 0
    assert y.std() < 0.3 * (r["payoff"] - r["prem"]).std() / r["vega"].mean()   # hedging removes most of the variance
    hi = v.straddle_cycles(_frame(4300, 20.0, 0.30, seed=6), 1.0, side=1, hedge=True)
    assert np.mean(hi["pnl"]) > 0                                        # realised above implied: long gamma earns
    # dividend forward lowers the call and raises the put: an ex-date inside the life changes the price
    fr2 = dict(fr)
    div = np.zeros(len(fr["days"]))
    div[10] = 2.0
    fr2 = v.make_frame(fr["days"], fr["close"], fr["vix"], div=div)
    a = v.straddle_cycles(fr2, 1.0, side=-1, hedge=False, hold=21)
    b = v.straddle_cycles(fr, 1.0, side=-1, hedge=False, hold=21)
    assert a["prem"][0] != pytest.approx(b["prem"][0]) and a["prem"][1] == pytest.approx(b["prem"][1])


def test_gamma_scalp_planted_and_null():
    planted = v.gamma_scalp(_frame(8300, 25.0, 0.12, seed=7), n_boot=NB, flip_grid=[0.3, 0.45, 0.6, 0.9])
    assert planted["n"] >= 390 and planted["verdict"] == "supported"
    assert planted["stat"]["sign_flip_scale"] == pytest.approx(0.48, abs=0.06)   # 0.12 / 0.25
    null = v.gamma_scalp(_frame(8300, 20.0, 0.18, seed=8), n_boot=NB, flip_grid=[0.8, 1.0])   # 0.9 x 20 = 18 = realised
    assert null["verdict"] == "not_supported"
    json.dumps(v._clean(null["stat"]), allow_nan=False)


def test_vrp_hedged_short_planted_and_null():
    planted = v.vrp_hedged_short(_frame(6600, 25.0, 0.12, seed=9), 0.80, n_boot=NB)
    assert planted["n"] >= 300 and planted["verdict"] == "supported"
    null = v.vrp_hedged_short(_frame(6600, 22.2, 0.18, seed=10), 0.81, n_boot=NB)   # 0.81 x 22.2 = 18 = realised
    assert null["verdict"] == "not_supported"
    no_smile = v.vrp_hedged_short(_frame(6600, 25.0, 0.12, seed=9), None, n_boot=NB)
    assert no_smile["verdict"] == "inconclusive" and "measured" in no_smile["reason"]


def test_tercile_oos_planted_and_null():
    rng = np.random.default_rng(11)
    n_pre, n = 40, 420
    sig = rng.standard_normal(n_pre + n)
    planted = {s: 0.3 * sig[n_pre:] + rng.standard_normal(n) for s in (0.81, 0.9, 1.0)}
    t = v.tercile_oos(sig, planted, n_pre, n_boot=NB)
    assert t["n_oos"] == n                                              # every P&L cycle is out of sample
    assert all(t["by_scale"][s]["ci"][0] > 0 for s in planted)
    null = {s: rng.standard_normal(n) for s in (0.81, 0.9, 1.0)}
    t0 = v.tercile_oos(sig, null, n_pre, n_boot=NB)
    assert t0["by_scale"][0.9]["ci"][0] < 0 < t0["by_scale"][0.9]["ci"][1]
    t1 = v.tercile_oos(sig[n_pre:], null, 0, n_boot=NB)                 # no pre-period: 60 training cycles
    assert t1["n_oos"] == n - 60


def test_straddle_tercile_runs_and_gates_min_n():
    fr = _frame(3000, 20.0, 0.15, seed=12)
    rep = v.straddle_tercile(fr, n_boot=NB)
    assert rep["n"] < 390 and rep["verdict"] in ("inconclusive", "not_supported")
    assert "MODEL-PRICED" in rep["reason"] and " — " in rep["reason"]
    json.dumps(v._clean(rep["stat"]), allow_nan=False)


# ======================================================================================= 45-DTE short premium ==

def test_short_option_paths_strikes_and_expiry():
    fr = _frame(400, 20.0, 0.2, seed=13)
    p = v.short_option_paths(fr, [0, 100], [("put", -0.16), ("call", 0.16)], 45)
    assert p["n"] == 2
    for i, a in enumerate(p["entries"]):
        assert (p["tx"][i] - fr["ords"][a]) <= 45 and (p["tx"][i] - fr["ords"][a]) >= 42
        T = (p["tx"][i] - fr["ords"][a]) / 365
        dp = bs.greeks(fr["close"][a], p["strikes"][0][i], T, 0.0, 0.2, "put")["delta"]
        assert float(dp) == pytest.approx(-0.16, abs=1e-6)
    cols = v.exit_columns(p)
    assert (cols["dte21"] < cols["hold"]).all() and (cols["target50_or_dte21"] <= cols["dte21"]).all()


def test_theta_harvest_planted_and_null():
    # planted: realised vol far below VIX, so the options sit far out of the money at 21 DTE and most of the credit has
    # been earned in 24 of the 45 days; the 21-DTE exit earns more per day
    days = _bdays("1993-02-01", 6900)
    calm = v.make_frame(days, _gbm(days, 0.03, 14), np.full(len(days), 20.0))
    planted = v.theta_harvest(calm, daily=False, n_boot=NB)
    assert planted["n"] >= 300 and planted["verdict"] == "supported"
    # null: realised = implied, a martingale price: every exit rule has zero expected P&L, so the difference is ~0
    fair = v.make_frame(days, _gbm(days, 0.20, 15), np.full(len(days), 20.0))
    null = v.theta_harvest(fair, daily=False, n_boot=NB)
    assert null["verdict"] == "not_supported"
    json.dumps(v._clean(null["stat"]), allow_nan=False)


def test_exit_rule_test_bonferroni_level():
    rng = np.random.default_rng(16)
    t = v.exit_rule_test(0.5 + rng.standard_normal(400), 3, 6, NB)
    assert t["level"] == pytest.approx(1 - 0.05 / 3)
    assert all(h["ci"][0] > 0 for h in t["halves"])
    t0 = v.exit_rule_test(rng.standard_normal(400), 3, 6, NB)
    assert not all(h["ci"][0] > 0 for h in t0["halves"])


def test_put_book_and_theta_ladder_smoke():
    days = _bdays("1993-02-01", 2600)
    fr = v.make_frame(days, _gbm(days, 0.18, 17), np.full(len(days), 20.0))
    single = v.put_book(fr, v._month_starts(days), 1.0)
    ladder = v.put_book(fr, v._week_starts(days), 0.25)
    assert ladder["n_positions"] > 3.5 * single["n_positions"]
    assert 0.5 < ladder["exposure"].mean() / single["exposure"].mean() < 2.0   # comparable margin
    rep = v.theta_ladder(fr, n_boot=200)
    assert rep["n"] < 300 and rep["verdict"] in ("inconclusive", "not_supported")
    assert "MODEL-PRICED" in rep["reason"]
    json.dumps(v._clean(rep["stat"]), allow_nan=False)


# ====================================================================================== model-free variance ==

def test_short_variance_units_planted_and_null():
    n = 8400
    days = _bdays("1993-02-01", n)
    c = _iid_closes(n, 0.01, 18)
    ann = 0.01 * math.sqrt(252) * 100                                    # realised vol in vol points
    planted = v.short_variance_units(days, c, np.full(n, ann * 1.25), n_boot=NB)
    assert planted["n"] >= 390 and planted["verdict"] == "supported"
    null = v.short_variance_units(days, c, np.full(n, ann * 0.97), n_boot=NB)
    assert null["verdict"] == "not_supported"


def test_vix2_win_rate_planted_and_null():
    n = 9300
    days = _bdays("1990-01-02", n)
    c = _iid_closes(n, 0.01, 19)
    var_ann = 0.01 ** 2 * 252
    planted = v.vix2_win_rate(days, c, np.full(n, 100 * math.sqrt(2.0 * var_ann)), n_boot=NB)
    assert planted["n"] >= 300 and planted["verdict"] == "supported"
    null = v.vix2_win_rate(days, c, np.full(n, 100 * math.sqrt(1.187 * var_ann)), n_boot=NB)   # chi2_21/21 75th pct
    assert null["verdict"] == "not_supported"
    assert 0.65 < null["stat"]["win_rate"] < 0.85


def _vol_path(n, seed, phi=0.995, sd=0.06, mean=math.log(0.16)):
    rng = np.random.default_rng(seed)
    lv = np.empty(n)
    lv[0] = mean
    for i in range(1, n):
        lv[i] = mean + phi * (lv[i - 1] - mean) + sd * rng.standard_normal()
    return np.exp(lv)


def test_scaled_short_variance_planted_and_null():
    n = 12000
    days = _bdays("1980-01-01", n)
    rng = np.random.default_rng(20)
    sig = _vol_path(n, 21)
    c = 100 * np.exp(np.concatenate([[0.0], np.cumsum(sig[:-1] / math.sqrt(252) * rng.standard_normal(n - 1))]))
    # planted: a persistent variance premium p_t that VIX carries and the HAR forecast does not
    p = np.empty(n)
    p[0] = 0.3
    e = rng.standard_normal(n)
    for i in range(1, n):
        p[i] = 0.3 + 0.997 * (p[i - 1] - 0.3) + 0.04 * e[i]
    p = np.clip(p, -0.6, 2.0)
    vix_p = {d: 100 * s * math.sqrt(1 + q) for d, s, q in zip(days, sig, p) if d >= "1990-01-02"}
    planted = v.scaled_short_variance(days, c, vix_p, n_boot=NB)
    assert planted["n"] >= 300
    assert planted["stat"]["sharpe_diff_test"]["diff"] > 0 and planted["stat"]["sharpe_diff_test"]["p"] < 0.05
    # null: iid returns at constant vol and a constant VIX, so z carries no information about the next month
    c0 = _iid_closes(n, 0.01, 22)
    vix_0 = {d: 0.01 * math.sqrt(252) * 100 * 1.15 for d in days if d >= "1990-01-02"}
    null = v.scaled_short_variance(days, c0, vix_0, n_boot=NB)
    assert null["verdict"] == "not_supported"
    assert null["stat"]["sharpe_diff_test"]["p"] > 0.05


def test_har_forecast_is_point_in_time():
    n = 1500
    c = _iid_closes(n, 0.01, 23)
    refit = np.zeros(n, dtype=bool)
    refit[::21] = True
    f = v.har_forecast(c, refit, min_obs=300)
    c2 = c.copy()
    c2[1200:] *= np.exp(np.cumsum(0.05 * np.ones(n - 1200)))             # change the future only
    f2 = v.har_forecast(c2, refit, min_obs=300)
    ok = np.isfinite(f[:1200])
    assert ok.sum() > 500 and np.allclose(f[:1200][ok], f2[:1200][ok])
    assert np.nanmean(f) == pytest.approx(0.01 ** 2 * 252, rel=0.2)


def test_vix1d_premium_planted_and_null():
    n = 1100
    days = _bdays("2022-05-13", n)
    c = _iid_closes(n, 0.01, 24)
    planted = v.vix1d_premium(days, c, {d: 100 * math.sqrt(365 * 1.4e-4) for d in days}, n_boot=NB)
    assert planted["n"] >= 500 and planted["verdict"] == "supported"
    null = v.vix1d_premium(days, c, {d: 100 * math.sqrt(365 * 0.9e-4) for d in days}, n_boot=NB)
    assert null["verdict"] == "not_supported"
    ev = v.vix1d_premium(days, c, {d: 100 * math.sqrt(365 * 1.4e-4) for d in days},
                         events={"CPI": {days[i] for i in range(5, n, 21)}}, n_boot=NB)
    assert ev["stat"]["event_days"]["n"] > 40


def test_strip_variance_recovers_flat_vol():
    S, r, sig, qd = 5000.0, 0.03, 0.18, "2026-01-02"
    rows = []
    for ex_days in (28, 35):
        exp = (date.fromisoformat(qd) + timedelta(days=ex_days)).isoformat()
        T = ex_days / 365
        for K in np.arange(2500.0, 8000.0, 5.0):
            for kind in ("call", "put"):
                px = float(bs.price(S, K, T, r, sig, kind))
                if px < 0.05:
                    continue
                rows.append({"sym": f"SPXW{K:.0f}{kind[0]}", "expiry": exp, "type": kind, "strike": float(K),
                             "bid": max(px - 0.05, 0.0), "ask": px + 0.05})
    out = v.strip_variance(rows, qd, r)
    assert out is not None
    assert out["vol30"] == pytest.approx(18.0, abs=0.3)                 # strip of a flat-vol chain = sigma^2


# ======================================================================================== harness wiring ==

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


def _px_rows(days, closes, adj=None, symbol="SPY"):
    adj = closes if adj is None else adj
    out = []
    for d, c, a in zip(days, closes, adj):
        t = int(datetime.fromisoformat(d + "T14:30:00+00:00").timestamp())
        out.append({"available_at": d + "T23:00:00+00:00",
                    "value": {"symbol": symbol, "t": t, "close": float(c), "adjclose": float(a), "volume": 1000}})
    return out


def _idx_rows(days, vals):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(x)}} for d, x in zip(days, vals)]


def _bundles(n=1500):
    days = _bdays("2018-01-02", n)
    spy = _gbm(days, 0.16, 25, 250.0)
    f = np.ones(n)
    for i in range(60, n, 63):                                           # quarterly dividends
        f[:i] *= 1 - 1.5 / spy[i - 1]
    smile_rows = [{"value": {"quote_date": "2026-10-13", "target_dte": t, "dte": t, "index_level": 15.0,
                             "ratio": {f"{m:.2f}": 0.8 + 2.0 * (1.0 - m) for m in np.arange(0.70, 1.21, 0.01)}}}
                  for t in (30, 45)]
    return {
        "daily-history-SPY": _px_rows(days, spy, spy * f),
        "daily-history--GSPC": _px_rows(days, spy * 10, symbol="^GSPC"),
        "cboe-VIX-history": _idx_rows(days, np.full(n, 18.0)),
        "cboe-VIX1D-history": _idx_rows(days, np.full(n, 15.0)),
        "fred-DTB3": [{"value": {"day": d, "value": 2.0}} for d in days],
        "spy-smile-2026-10-13": smile_rows,
        "fomc-meetings": [{"value": {"decision_day": days[i], "future": False}} for i in range(30, n, 30)],
    }


def test_harnesses_missing_bundles_are_inconclusive():
    empty = FakeArchive({})
    for name, h in v.HARNESSES.items():
        stat, n, verdict, reason = h(empty)
        assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert "missing data bundles" in reason


def test_harnesses_run_on_synthetic_archive():
    arc = FakeArchive(_bundles())
    assert set(v.THEORY_MAP.values()) == set(v.HARNESSES)
    assert all(k.startswith("b6_var_") and k == k.lower() for k in v.HARNESSES)
    for name, h in v.HARNESSES.items():
        stat, n, verdict, reason = h(arc)
        assert verdict in ("supported", "not_supported", "inconclusive"), name
        assert isinstance(n, int)
        json.dumps(stat, allow_nan=False)
        if "missing_bundles" not in stat:
            assert " — " in reason, name
    # short synthetic history: no claim may be supported below its min_n
    for name in ("b6_var_short_straddle_tercile", "b6_var_gamma_scalp_long_straddle", "b6_var_theta_ladder",
                 "b6_var_variance_swap_units", "b6_var_variance_strip_win_rate", "b6_var_vix1d_premium"):
        assert v.HARNESSES[name](arc)[2] != "supported", name
