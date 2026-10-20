"""Batch-4 crypto carry/funding harnesses on synthetic series: planted effects pass, nulls fail. No archive, no network."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch4_carry as cy

NB = 400            # bootstrap draws in tests (the harnesses use 5,000)


def _days(a, b, weekdays_only=False):
    d, e, out = date.fromisoformat(a), date.fromisoformat(b), []
    while d <= e:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _hours(a, b):
    t0, t1 = cy._utc_ts(a), cy._utc_ts(b)
    return np.arange(t0 + 3600, t1 + 1, 3600, dtype=np.int64)


# ------------------------------------------------------------------------------------------------ helpers --

def test_cme_expiry_calendar_and_settle_times():
    assert cy.cme_btc_expiry(2021, 3) == date(2021, 3, 26)
    assert cy.cme_btc_expiry(2024, 3) == date(2024, 3, 28)          # Good Friday -> Thursday
    assert cy.cme_btc_expiry(2020, 12) == date(2020, 12, 24)        # Christmas Friday -> Thursday
    ex = cy.cme_expiries(2020, 2021)
    assert cy.front_expiry("2021-03-26", ex) == date(2021, 3, 26)   # Yahoo holds the expiring contract through expiry
    assert cy.front_expiry("2021-03-29", ex) == date(2021, 4, 30)
    assert cy.cme_settle_ts("2020-07-01") == cy._utc_ts("2020-07-01", 20)   # 15:00 CDT
    assert cy.cme_settle_ts("2020-01-02") == cy._utc_ts("2020-01-02", 21)   # 15:00 CST
    assert cy.brr_ts("2020-07-01") == cy._utc_ts("2020-07-01", 15)          # 16:00 BST
    assert cy.brr_ts("2020-01-02") == cy._utc_ts("2020-01-02", 16)          # 16:00 GMT


def test_bey_and_point_in_time_rates():
    assert cy.bey(5.0) == pytest.approx(365 * 0.05 / (360 - 91 * 0.05))
    r = cy.Rates({"2020-01-02": 1.0, "2020-01-03": 2.0})
    assert r.before("2020-01-03") == pytest.approx(cy.bey(1.0))     # the same day's print is not used
    assert r.before("2020-01-06") == pytest.approx(cy.bey(2.0))


def test_window_sum_is_left_open_right_closed():
    ts, cs = cy._hourly([10, 20, 30, 40], [1.0, 2.0, 3.0, 4.0])
    s, c = cy.window_sum(ts, cs, 10, 30)
    assert s == 5.0 and c == 2
    assert np.isnan(cy.value_at(ts, np.array([1.0, 2, 3, 4]), 25)[0]) and cy.value_at(ts, np.array([1.0, 2, 3, 4]), 30)[0] == 3


def test_student_mean_ci_sides():
    rng = np.random.default_rng(0)
    pos = cy.student_mean_ci(0.5 + rng.standard_normal(80), 3, NB)
    null = cy.student_mean_ci(rng.standard_normal(80), 3, NB)
    assert pos["lb95"] > 0 and pos["ci95"][0] < pos["lb95"]          # one-sided bound is tighter than the 2.5% end
    assert null["ci95"][0] < 0 < null["ci95"][1]


def test_funding_state_machine():
    trend = np.array([1, 1, 1, 1, 1, 1, 0, 1, 1], dtype=float)
    p90 = np.full(9, 1.0); p97 = np.full(9, 2.0)
    F = np.array([0.5, 3, 3, 3, 1.5, 0.5, 3, 1.5, 0.5])
    s = cy.funding_states(trend, F, p90, p97)
    assert list(s) == [1, 1, 1, 0.5, 0.5, 1, 0, 0, 1]   # HALF after 3 days > P97, held in the band, FLAT held until <= P90


# -------------------------------------------------------------------------- T-198 funding vs quarterly basis --

def _quarterly_setup(funding_mean, ann_basis, seed=0):
    rng = np.random.default_rng(seed)
    fts = _hours("2019-12-01", "2026-12-31")
    i1 = funding_mean + 5e-6 * rng.standard_normal(len(fts))
    idx = 10000 * np.exp(np.cumsum(0.003 * rng.standard_normal(len(fts))))
    futures = []
    e = date(2020, 3, 27)
    while e <= date(2027, 6, 30):
        ets = cy._utc_ts(e, 8)
        ct = np.array([ets - k * 86400 for k in range(270, 0, -1)], dtype=np.int64)
        S = cy.value_at(fts, idx, ct)
        F = S * (1 + ann_basis * (ets - ct) / 86400 / 365)
        futures.append({"expiry_ts": ets, "close_ts": ct, "close": F})
        e += timedelta(days=91)
    return fts, i1, idx, futures


def test_t198_planted_funding_above_basis_supported():
    fts, i1, idx, fut = _quarterly_setup(3e-5, 0.01)            # ~26%/yr funding vs 1%/yr basis
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    assert rep["n"] >= 24 and rep["share"] == 1.0
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["reason"].endswith("all criteria pass")


def test_t198_null_basis_prices_funding_not_supported():
    fts, i1, idx, fut = _quarterly_setup(0.0, 0.08, seed=1)     # no funding, 8%/yr basis paid
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]


# -------------------------------------------------------------------------- T-258 option-hedged funding carry --

def _hedged_setup(funding_mean, realised_vol, seed=0):
    rng = np.random.default_rng(seed)
    fts = _hours("2021-03-01", "2026-11-15")
    i1 = funding_mean + 5e-6 * rng.standard_normal(len(fts))
    days = _days("2021-03-01", "2026-11-15")
    px = 40000 * np.exp(np.cumsum(realised_vol / np.sqrt(365) * rng.standard_normal(len(days))))
    deliv = dict(zip(days, px.tolist()))
    dvol = {d: 60.0 for d in days}
    return fts, i1, deliv, dvol, {d: 2.0 for d in days}


def test_t258_planted_high_funding_supported():
    fts, i1, deliv, dvol, rf = _hedged_setup(1.5e-4, 0.3)
    rep = cy.funding_call_hedged(fts, i1, deliv, dvol, rf, n_boot=NB)
    assert rep["n"] == 66 and "MODEL-PRICED" in rep["reason"]
    assert rep["verdict"] == "supported", rep["reason"]


def test_t258_null_no_funding_not_supported():
    fts, i1, deliv, dvol, rf = _hedged_setup(0.0, 0.3, seed=2)   # pays the call premium, earns nothing
    rep = cy.funding_call_hedged(fts, i1, deliv, dvol, rf, n_boot=NB)
    assert rep["mean_net"] < 0
    assert rep["verdict"] == "not_supported", rep["reason"]


# ------------------------------------------------------------------------------- T-303 trend + funding filter --

def _trend_setup(planted, seed=2):
    rng = np.random.default_rng(seed)
    days = _days("2019-01-01", "2026-10-01"); n = len(days)
    fts = cy._utc_ts(days[0]) + 3600 * np.arange(1, n * 24 + 1)
    lvl = 1e-4 + 2e-5 * rng.standard_normal(n)
    r = 0.003 + 0.035 * rng.standard_normal(n)
    for k, s in enumerate(range(420, n - 20, 100)):
        lvl[s - 8:s - 2] = 1e-4 * (8 + 2 * k) * np.linspace(0.6, 1.0, 6)    # escalating crowding before each event
        lvl[s - 2:s + 8] = 2.5e-4                                          # then elevated (between P90 and P97)
        if planted:
            r[s:s + 6] = -0.04                                             # crash while crowded
    i8 = np.repeat(lvl, 24) + 1e-6 * rng.standard_normal(n * 24)
    return days, 100 * np.cumprod(1 + r), fts, i8


def test_t303_planted_crowding_before_crashes_supported():
    days, closes, fts, i8 = _trend_setup(True)
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2026-10-01", n_boot=NB)
    assert rep["n"] >= 2000 and rep["activations"] >= 10
    assert rep["verdict"] == "supported", rep["reason"]


def test_t303_null_funding_unrelated_to_returns_not_supported():
    days, closes, fts, i8 = _trend_setup(False)
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2026-10-01", n_boot=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_t303_too_few_activations_is_inconclusive_not_supported():
    days, closes, fts, i8 = _trend_setup(True)
    rep = cy.trend_funding_filter(days, closes, fts, i8, start="2020-03-01", end="2026-10-01", n_boot=NB,
                                  min_activations=1000)
    assert rep["verdict"] == "inconclusive"


# ------------------------------------------------------------------------------------- T-329 CME basis spikes --

def _cme_setup(planted, seed=0, spike_ntd=15):
    rng = np.random.default_rng(seed)
    days = _days("2018-01-02", "2026-09-30", weekdays_only=True); n = len(days)
    S = 10000 * np.exp(np.cumsum(0.02 * rng.standard_normal(n)))
    ex = cy.cme_expiries(2017, 2027)
    dte = np.array([(cy.front_expiry(d, ex) - date.fromisoformat(d)).days for d in days], dtype=float)
    b = 0.05 + 0.005 * rng.standard_normal(n)
    if planted:
        ntd = np.array([days.index(cy.front_expiry(d, ex).isoformat()) - i if cy.front_expiry(d, ex).isoformat() in days else 99
                        for i, d in enumerate(days)])
        for i in np.flatnonzero(ntd == spike_ntd):
            b[i:i + 2] = 0.60                                    # spike on the signal and entry day, gone by exit
    F = S * (1 + b * dte / 365)
    return days, F, S, np.ones(n, dtype=bool), ex


def test_t329_planted_reverting_spikes_supported():
    days, F, S, std, ex = _cme_setup(True)
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB)
    assert rep["n"] >= 40 and rep["mean_net"] > 0.01
    assert rep["verdict"] == "supported", rep["reason"]
    assert "trailing 60 trading days" in rep["reason"]


def test_t329_null_noise_basis_not_supported():
    days, F, S, std, ex = _cme_setup(False, seed=3)
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_t329_missing_early_window_caps_at_inconclusive():
    days, F, S, std, ex = _cme_setup(True)
    S2 = S.copy(); S2[:400] = np.nan                            # no synchronous spot for the first ~19 months
    rep = cy.cme_basis_spike(days, F, S2, std, ex, n_boot=NB)
    assert rep["verdict"] == "inconclusive" and "covered" in rep["reason"]


def test_t329_exit_inside_roll_window_of_same_contract_is_kept():
    # regression: spikes 8 sessions before expiry put the 5-day exit 2 sessions before expiry, inside the roll window
    # but in the same contract; those trades used to be discarded (0 trades)
    days, F, S, std, ex = _cme_setup(True, spike_ntd=8)
    rep = cy.cme_basis_spike(days, F, S, std, ex, n_boot=NB)
    assert rep["n"] >= 40 and all(t["exit_in_roll_window"] for t in rep["trades"])
    assert all(cy.front_expiry(t["entry"], ex) == cy.front_expiry(t["exit"], ex) for t in rep["trades"])
    assert rep["verdict"] == "supported", rep["reason"]


def test_t329_basis_trades_exit_rules():
    days = _days("2021-03-15", "2021-04-09", weekdays_only=True); n = len(days)
    F = np.full(n, 101.0); S = np.full(n, 100.0); ok = np.ones(n, dtype=bool); sig = np.zeros(n, dtype=bool)
    exp = [cy.front_expiry(d, cy.cme_expiries(2021, 2021)) for d in days]
    sig[days.index("2021-03-17")] = True                         # exit 2021-03-25, the day before expiry
    valid = np.ones(n, dtype=bool); roll = np.ones(n, dtype=bool); roll[days.index("2021-03-25")] = False
    assert len(cy._basis_trades(days, F, S, roll, exp, sig, 5, 0.002, valid)) == 1     # exit in the roll window kept
    valid[days.index("2021-03-25")] = False
    assert cy._basis_trades(days, F, S, roll, exp, sig, 5, 0.002, valid) == []         # invalid exit bar dropped
    sig[:] = False; sig[days.index("2021-03-19")] = True                               # exit 2021-03-29: next contract
    assert cy._basis_trades(days, F, S, ok, exp, sig, 5, 0.002, np.ones(n, dtype=bool)) == []


def test_t329_trailing_z_uses_trailing_60_trading_days():
    # regression: the window is the valid observations dated within the last 60 sessions, not the last 60 valid ones
    rng = np.random.default_rng(0); n = 300
    b = np.zeros(n); ok = np.zeros(n, dtype=bool)
    ok[:150] = True; b[:150] = 10 + rng.standard_normal(150)    # old regime, densely observed
    ok[150::3] = True; b[150:] = rng.standard_normal(150)        # new regime, every third session valid
    z = cy.trailing_z(b, ok, 60, 20)
    i = 297; w = b[[j for j in range(i - 60, i) if ok[j]]]
    assert ok[i] and len(w) == 20
    assert z[i] == pytest.approx((b[i] - w.mean()) / w.std(ddof=1))
    assert abs(z[i]) < 5                                          # the last 60 observations would reach the old regime
    assert np.isnan(cy.trailing_z(b, ok, 60, 21)[i])              # fewer than the minimum count -> no z


def test_cme_daily_basis_drops_roll_window_and_expiry_day():
    days = _days("2021-03-15", "2021-04-09", weekdays_only=True)
    n = len(days); S = np.full(n, 100.0); F = np.full(n, 101.0)
    tab = cy.cme_daily_basis(days, F, S, np.ones(n, dtype=bool), cy.cme_expiries(2021, 2021), roll_trading_days=5)
    ok = dict(zip(days, tab["ok"]))
    assert ok["2021-03-18"] and not ok["2021-03-19"]             # 5 trading days before the 2021-03-26 expiry dropped
    assert not ok["2021-03-26"] and ok["2021-03-29"]              # expiry day dropped, next contract starts
    i = days.index("2021-03-29")
    assert tab["basis"][i] == pytest.approx(0.01 * 365 / 32)      # (F/S - 1) x 365 / days to 2021-04-30


def test_cme_contract_table_decision_and_16_london_exit():
    # regression (T-362): the exit is the trial's BRR proxy, the 16:00 London index; the 15:00/16:00 mean is a control
    days = _days("2021-02-22", "2021-05-05", weekdays_only=True)
    n = len(days); F = np.full(n, 101.0); std = np.ones(n, dtype=bool)
    spot = lambda t: 100.0 + (t % 7200) / 3600.0                  # alternates 100 / 101 by hour parity
    tab = cy.cme_contract_table(days, F, std, spot, cy.cme_expiries(2021, 2021), first="2021-04", last="2021-04")
    c = tab[0]
    assert c["decision"] == "2021-03-29" and c["expiry"] == "2021-04-30"
    assert c["S_exit"] == spot(cy.brr_ts("2021-04-30")) == 101.0   # 16:00 BST = 15:00 UTC
    assert c["S_exit_15_16_mean"] == pytest.approx(100.5)


# ----------------------------------------------------------------------------------- T-362 cash-and-carry --

def _contracts(ann_basis, slip_mean=0.0, slip_sd=0.0, seed=0):
    rng = np.random.default_rng(seed); out = []
    for (y, m) in cy._months("2018-01", "2026-09"):
        e = cy.cme_btc_expiry(y, m); py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
        dec = cy.cme_btc_expiry(py, pm) + timedelta(days=3)
        d = (e - dec).days; S0 = 10000.0
        sx = 12000.0 * (1 + 0.01 * rng.standard_normal())
        out.append({"contract": f"{y:04d}-{m:02d}", "expiry": e.isoformat(), "decision": dec.isoformat(), "F0": S0 * (1 + ann_basis * d / 365),
                    "S0": S0, "F_final": sx + S0 * (slip_mean + slip_sd * rng.standard_normal()), "S_exit": sx, "rf": 0.02})
    return out


def test_t362_planted_rich_basis_supported():
    rep = cy.cme_cash_and_carry(_contracts(0.15, slip_sd=0.001), n_boot=NB)
    assert rep["n"] == 57 and rep["entered"] == 57
    assert rep["verdict"] == "supported", rep["reason"]


def test_t362_null_slippage_eats_carry_not_supported():
    rep = cy.cme_cash_and_carry(_contracts(0.055, slip_mean=0.004, slip_sd=0.01, seed=4), n_boot=NB)
    assert rep["mean_ann_excess"] < 0
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_t362_verdict_uses_16_london_exit_not_the_window_mean():
    # regression: the 16:00 London index sits 3% below the final settlement and the 15:00 point 3% above, so the
    # 15:00/16:00 mean matches it; the claim must be judged on the trial's 16:00 proxy
    rng = np.random.default_rng(7)
    days = _days("2018-01-01", "2026-09-30", weekdays_only=True); n = len(days)
    ex = cy.cme_expiries(2017, 2027); S = 10000.0
    dte = np.array([(cy.front_expiry(d, ex) - date.fromisoformat(d)).days for d in days], dtype=float)
    F = S * (1 + (0.15 + 0.02 * rng.standard_normal(n)) * dte / 365)       # expiry day: F = S (final settlement)
    brr = {cy.brr_ts(e) for e in ex}
    spot = lambda t: S * 0.97 if t in brr else S * 1.03 if t + 3600 in brr else S
    tab = cy.cme_contract_table(days, F, np.ones(n, dtype=bool), spot, ex)
    rep = cy.cme_cash_and_carry(tab, n_boot=NB)
    assert rep["n"] == 57 and rep["mean_slippage"] == pytest.approx(0.03)
    assert rep["verdict"] == "not_supported", rep["reason"]
    ctl = rep["brr_window_mean_exit_control"]
    assert ctl["mean_slippage"] == pytest.approx(0.0) and ctl["lb95"] > 0 and ctl["dsr"] > 0.95   # control alone would pass
    assert "not in the verdict" in rep["reason"]


def test_t362_uncovered_claim_months_cap_at_inconclusive():
    # regression: no synchronous spot for 2018-01..2019-05 -> the claim window is not covered, at best inconclusive
    cs = _contracts(0.15, slip_sd=0.001)
    cs = [{**c, "S0": float("nan")} if c["contract"] <= "2019-05" else c for c in cs]
    rep = cy.cme_cash_and_carry(cs, n_boot=NB)
    assert rep["uncovered_contracts"][0] == "2018-01" and len(rep["uncovered_contracts"]) == 17
    assert rep["verdict"] == "inconclusive" and "17 contract-months (2018-01..2019-05)" in rep["reason"], rep["reason"]
    assert cy.cme_cash_and_carry(_contracts(0.15, slip_sd=0.001), n_boot=NB)["uncovered_contracts"] == []


def test_t362_never_entering_is_not_supported():
    rep = cy.cme_cash_and_carry(_contracts(0.03), n_boot=NB)          # 3% basis never clears DTB3 + 3%
    assert rep["entered"] == 0 and rep["verdict"] == "not_supported"


# ----------------------------------------------------------------------------- T-363 thresholded perp carry --

def test_t363_planted_persistent_funding_supported():
    rng = np.random.default_rng(0)
    fts = _hours("2019-05-01", "2026-10-15")
    i1 = 0.30 / 8760 + 2e-6 * rng.standard_normal(len(fts))
    rep = cy.perp_funding_carry(fts, i1, {"2019-01-02": 2.0}, n_boot=NB)
    assert rep["days_in_position"] >= 250 and rep["sharpe"]["pess"] > 1
    assert rep["verdict"] == "supported", rep["reason"]


def test_t363_null_iid_funding_not_supported():
    rng = np.random.default_rng(1)
    fts = _hours("2019-05-01", "2026-10-15")
    i1 = 1.5e-4 * rng.standard_normal(len(fts))                 # often above the threshold, no persistence
    rep = cy.perp_funding_carry(fts, i1, {"2019-01-02": 2.0}, n_boot=NB)
    assert rep["days_in_position"] >= 250
    assert rep["verdict"] == "not_supported", rep["reason"]


# ------------------------------------------------------------------------------ T-364 basis as crash signal --

def _crash_setup(planted, seed=0):
    rng = np.random.default_rng(seed)
    weeks = [d for d in _days("2017-12-04", "2026-09-28") if date.fromisoformat(d).weekday() == 0]
    b = 0.05 + 0.01 * rng.standard_normal(len(weeks))
    spikes = list(range(5, len(weeks), 13))
    b[spikes] = 0.20
    pdays = _days("2017-11-01", "2026-12-31")
    r = 0.01 * rng.standard_normal(len(pdays))
    if planted:
        pos = {d: i for i, d in enumerate(pdays)}
        for k in spikes:
            i = pos[weeks[k]]
            r[i + 1:i + 11] = -0.035                            # ~30% fall over the 10 days after a top-decile week
    return weeks, b, pdays, 100 * np.cumprod(1 + r)


def test_t364_planted_crash_after_rich_basis_supported():
    weeks, b, pdays, px = _crash_setup(True)
    rep = cy.basis_crash_predictor(weeks, b, pdays, px, n_perm=NB)
    assert rep["n"] >= 350 and rep["episodes"] >= 8 and rep["gap_pp"] >= 10
    assert rep["verdict"] == "supported", rep["reason"]


def test_t364_null_unrelated_drawdowns_not_supported():
    weeks, b, pdays, px = _crash_setup(False, seed=5)
    rep = cy.basis_crash_predictor(weeks, b, pdays, px, n_perm=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]


# ---------------------------------------------------------------------------------- T-423 funding sentiment --

def _sentiment_setup(planted, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2019-06-01", "2026-10-31"); n = len(days)
    lvl = 1e-4 + 2e-5 * rng.standard_normal(n)
    spike = rng.random(n) < 0.12
    lvl[spike] = 3e-4
    fts = cy._utc_ts(days[0]) + 3600 * np.arange(1, n * 24 + 1)
    i8 = np.repeat(lvl, 24)
    lr = 0.002 * rng.standard_normal(n * 24)
    if planted:
        for d in np.flatnonzero(spike):
            h0 = (d + 1) * 24                                   # entry hour index (d+1 01:00 is fts[h0])
            lr[h0:h0 + 7 * 24] += np.log(0.95) / (7 * 24)      # -5% over the next 7 days
    idx = 30000 * np.exp(np.cumsum(lr))
    return fts, i8, idx


def test_t423_planted_crowded_funding_predicts_drop_supported():
    fts, i8, idx = _sentiment_setup(True)
    rep = cy.funding_sentiment(fts, i8, idx, i1=i8 / 8, n_boot=NB)
    assert rep["n_top"] >= 200 and rep["events"] >= 30 and rep["oos"]["diff"] <= -0.02
    assert rep["verdict"] == "supported", rep["reason"]


def test_t423_null_no_predictability_not_supported():
    fts, i8, idx = _sentiment_setup(False, seed=6)
    rep = cy.funding_sentiment(fts, i8, idx, n_boot=NB)
    assert rep["verdict"] == "not_supported", rep["reason"]


# ------------------------------------------------------------------------------------------- contract --

def test_registry_contract():
    assert set(cy.THEORY_MAP) == {"T-198", "T-258", "T-303", "T-329", "T-362", "T-363", "T-364", "T-423"}
    assert all(h in cy.HARNESSES and h.startswith("carry_") for h in cy.THEORY_MAP.values())


class _NoData:
    def get(self, name):
        raise KeyError(name)


def test_missing_bundles_are_inconclusive():
    for fn in cy.HARNESSES.values():
        stat, n, v, reason = fn(_NoData())
        assert v == "inconclusive" and n == 0 and "missing data bundles" in reason
