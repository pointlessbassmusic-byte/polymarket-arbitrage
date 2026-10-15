"""Regression tests for the audit findings applied to mandel/experiments/underlying2.py (group u2), on synthetic data.

Each test names the finding it pins. They check that each harness tests its claim as worded: the stated thresholds on
every series the claim names, point-in-time fills, the stated benchmark, nulls and windows, and that a criterion
which is not implemented caps the verdict at inconclusive.
"""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import underlying2 as u2


# ----------------------------------------------------------------------------- helpers --

def _days(start, end, weekdays_only=True, drop=()):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    drop = set(drop)
    while d <= e:
        if (not weekdays_only or d.weekday() < 5) and d.isoformat() not in drop:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(ret):
    """Closes whose return ending on day i is ret[i] (ret[0] ignored)."""
    r = np.asarray(ret, float).copy(); r[0] = 0.0
    return 100 * np.cumprod(1 + r)


def _month_end_days(start_month, end_month):
    """One trading day per month (the 28th), for monthly harnesses fed with month-end-only series."""
    y, m = int(start_month[:4]), int(start_month[5:7]); out = []
    while f"{y:04d}-{m:02d}" <= end_month:
        out.append(f"{y:04d}-{m:02d}-28")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _monthly_series(months_days, monthly_ret):
    return months_days, _closes(monthly_ret)


def _by_ym(days):
    out = {}
    for i, d in enumerate(days):
        out.setdefault((int(d[:4]), int(d[5:7])), []).append(i)
    return out


def _failed(reason):
    return reason.split("failed: ", 1)[1].split(" (not implemented")[0] if "failed: " in reason else ""


def _not_implemented(reason):
    return reason.split("not implemented: ", 1)[1] if "not implemented: " in reason else ""


def _bills(days, pct):
    return list(days), [float(pct)] * len(days)


# --------------------------------------------------------------------------- loader --

class _Entry:
    created_at = "2030-01-01T00:00:00+00:00"


class _FakeArchive:
    def __init__(self, rows):
        self.rows = rows

    def get(self, name):
        return _Entry()

    def load(self, name):
        return list(self.rows)


def test_load_series_returns_pair_with_adjusted_opens():
    rows = []
    for i, (o, c, ac) in enumerate([(10.0, 11.0, 5.5), (11.0, 12.0, 6.0), (12.5, 13.0, 6.5)]):
        t = 1600000000 + i * 86400
        rows.append({"available_at": "2020-01-01T00:00:00+00:00", "value": {"t": t, "open": o, "close": c, "adjclose": ac}})
    s = u2.load_series(_FakeArchive(rows), "SVXY")
    days, closes = s                                       # still unpacks as a plain (days, closes) pair
    assert len(s) == 2 and list(closes) == [5.5, 6.0, 6.5]
    assert np.allclose(s.opens, [10.0 * 5.5 / 11.0, 11.0 * 6.0 / 12.0, 12.5 * 6.5 / 13.0])
    rows[1]["value"]["open"] = None
    assert u2.load_series(_FakeArchive(rows), "SVXY").opens is None


# ------------------------------------------------------------------ U2A-1 / OM-3 (T-350) --

def _santa_series(start, end, planted_pp, sd, seed):
    rng = np.random.default_rng(seed)
    days = _days(start, end)
    r = rng.normal(0.0003, sd, len(days))
    ym = _by_ym(days)
    for y in range(int(days[0][:4]), int(days[-1][:4])):
        dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
        if dec and jan:
            for i in dec[-5:] + jan[:2]:
                r[i] += planted_pp / 100 / 7
    return days, _closes(r)


def test_santa_rally_gates_spy_at_one_pp_and_spy_halves():
    gspc = _santa_series("1950-01-02", "2025-12-31", 2.5, 0.006, 0)
    spy_weak = _santa_series("1993-01-04", "2025-12-31", 0.5, 0.002, 1)
    rep = u2.santa_rally(gspc, spy_weak, n_place=400)
    assert rep["excess_pp"] > 1 and rep["p"] < 0.05 and 0 < rep["spy_excess_pp"] < 1
    assert rep["verdict"] == "not_supported" and "SPY excess >= 1 pp" in _failed(rep["reason"])
    spy_strong = _santa_series("1993-01-04", "2025-12-31", 2.5, 0.002, 1)
    rep2 = u2.santa_rally(gspc, spy_strong, n_place=400)
    assert rep2["verdict"] == "supported" and all(h > 0 for h in rep2["spy_halves_pp"])


# -------------------------------------------------------------------------- U2A-3 (T-379) --

def _svxy_setup(seed=0, gap=0.02):
    rng = np.random.default_rng(seed)
    days = _days("2015-01-01", "2020-12-31")
    n = len(days)
    ratio = np.where(rng.random(n) < 0.5, 1.2, 0.9)             # VIX3M/VIX: in contango about half the days
    vix = {d: 20.0 for d in days}; vix3m = {d: 20.0 * x for d, x in zip(days, ratio)}
    sig = ratio > 1.05
    c = np.empty(n); o = np.empty(n); c[0] = o[0] = 100.0
    for i in range(1, n):
        o[i] = c[i - 1] * (1 + (gap if sig[i - 1] else -gap))  # overnight gap after a contango close: only a same-close fill gets it
        c[i] = o[i] * (1 + rng.normal(0, 0.01))
    return days, c, o, vix, vix3m


def test_svxy_regime_fills_at_next_open():
    days, c, o, vix, vix3m = _svxy_setup()
    rep = u2.svxy_regime(u2.PriceSeries(days, c, o), vix, vix3m, test_from="2016-01-01")
    assert rep["fill"] == "next open"
    assert rep["sharpe"] < 1.0                                  # the planted overnight gap is not reachable from the 16:15 signal
    assert "next open" not in _not_implemented(rep["reason"])
    same_close = (np.array([float(vix3m[d] / vix[d] > 1.05) for d in days[:-1]]) * (c[1:] / c[:-1] - 1))
    assert u2._sr(same_close, 252) > 5                          # what the old same-close fill would have earned
    rep3 = u2.svxy_regime((days, c, o), vix, vix3m, test_from="2016-01-01")
    assert rep3["fill"] == "next open" and rep3["sharpe"] == pytest.approx(rep["sharpe"])


def test_svxy_regime_without_opens_is_capped():
    days, c, o, vix, vix3m = _svxy_setup()
    rep = u2.svxy_regime((days, c), vix, vix3m, test_from="2016-01-01")
    assert rep["fill"].startswith("next close")
    assert "signal filled at SVXY's next open" in rep["reason"] and rep["verdict"] != "supported"


# ------------------------------------------------------------------- U2A-4 / U2A-5 (T-306) --

def _sectors_iid(seed=0):
    rng = np.random.default_rng(seed)
    days = _month_end_days("1998-12", "2026-09")
    sectors = {s: _monthly_series(days, rng.normal(0.008, 0.05, len(days))) for s in u2.SECTORS}
    spy = _monthly_series(days, np.mean([np.r_[0, np.diff(np.log(v[1]))] for v in sectors.values()], axis=0))
    return days, sectors, spy


def test_sector_rotation_permutation_null_is_cost_matched():
    days, sectors, spy = _sectors_iid(0)
    bd, bv = _bills(days, 2.0)
    rep = u2.sector_rotation(sectors, spy, bd, bv, cost_side=0.01, n_perm=200)
    # iid sectors carry no rank information; with heavy costs, a null that charges random picks their own (higher)
    # turnover sits far below the strategy and would pass the criterion wrongly
    assert rep["alpha_bps_month"] < rep["null_q95_bps"]
    assert "alpha above 95th pct of permutation null" in _failed(rep["reason"]) and "cost-matched" in rep["reason"]


def test_sector_rotation_leave_one_decade_out():
    rng = np.random.default_rng(1)
    days = _month_end_days("1998-12", "2026-09")
    spy_r = rng.normal(0.006, 0.04, len(days))
    alpha = np.array([0.03 if d[:3] == "201" else -0.005 for d in days])         # all of the alpha is earned in the 2010s
    sec_r = spy_r + alpha + rng.normal(0, 0.002, len(days))
    sectors = {s: _monthly_series(days, sec_r) for s in u2.SECTORS}
    bd, bv = _bills(days, 0.0)
    rep = u2.sector_rotation(sectors, _monthly_series(days, spy_r), bd, bv, n_perm=20)
    assert set(rep["lodo_bps"]) == {"2000s", "2010s", "2020s"}
    assert rep["alpha_bps_month"] > 0 and rep["lodo_bps"]["2010s"] < 0 < rep["lodo_bps"]["2000s"]
    assert "alpha > 0 leaving out each decade" in _failed(rep["reason"])


# -------------------------------------------------------------- U2A-6 / U2A-13 / U2-9 (T-305) --

def _gem_inputs(seed=0, spy_drift=0.0004, crash_day=None, spy_sd=0.006):
    rng = np.random.default_rng(seed)
    days = _days("2003-01-01", "2016-12-31")
    n = len(days)
    spy = spy_drift + rng.normal(0, spy_sd, n)
    if crash_day is not None:
        i = days.index(crash_day); spy[i] = -0.30; spy[i + 1] = 1 / 0.7 - 1
    efa = rng.normal(0.0, 0.006, n); agg = 0.0001 + rng.normal(0, 0.001, n)
    return days, (days, _closes(spy)), (days, _closes(efa)), (days, _closes(agg))


def test_gem_fills_at_next_trading_day_close():
    days, spy, efa, agg = _gem_inputs(spy_drift=0.0008, spy_sd=0.002, crash_day="2010-06-01")   # 1st trading day of June 2010: -30%, back next day
    bd, bv = _bills(days, 2.0)
    rep = u2.gem(spy, efa, agg, bd, bv)
    # on the execution-day grid the holding period ending at the 2010-06-01 close carries the -30%; on a month-end
    # grid (trading at the signal's own close) both days fall inside June and the crash would be invisible
    assert rep["mdd"] < -0.25 and rep["bench_mdd"] < -0.15
    first_signal_month = rep["first_month"]
    assert rep["first_fill_day"][:7] > first_signal_month and rep["first_fill_day"][8:] in ("01", "02", "03", "04")


def test_gem_sharpe_on_excess_returns_and_switch_costs():
    days, spy, efa, agg = _gem_inputs(spy_drift=0.0012)
    lo = u2.gem(spy, efa, agg, *_bills(days, 0.01))
    hi = u2.gem(spy, efa, agg, *_bills(days, 8.0))
    # GEM (always SPY here) is more volatile than 60/40: subtracting a higher bill rate raises its excess-Sharpe gap;
    # on raw returns the two runs would give the same Sharpe difference
    assert hi["sharpe_diff"] > lo["sharpe_diff"] + 0.05
    assert lo["cost_per_switch_bps"] == pytest.approx(3.0)
    v2 = u2.gem_v2(spy, efa, agg, *_bills(days, 2.0))
    assert v2["cost_per_switch_bps"] == pytest.approx(6.0)                     # T-480: 3 bps per side per switch


# ------------------------------------------------------------- U2A-7 / U2A-8 (T-351, T-444) --

def _turn_of_year(start, end, planted_pp, seed, sd=0.004):
    """(small, large) daily series whose spread gains planted_pp over each Dec[-6] -> Jan[9] window."""
    rng = np.random.default_rng(seed)
    days = _days(start, end); n = len(days)
    big = rng.normal(0.0003, 0.008, n); small = big + rng.normal(0, sd, n)
    ym = _by_ym(days)
    for y in range(int(days[0][:4]), int(days[-1][:4])):
        dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
        if dec and jan and len(dec) >= 6 and len(jan) >= 10:
            idx = list(range(dec[-6] + 1, jan[9] + 1))
            small[idx] += planted_pp / 100 / len(idx)
    return (days, _closes(small)), (days, _closes(big))


def test_january_small_cap_placebo_length_and_iwm_gate():
    rut, gspc = _turn_of_year("1987-09-10", "2025-12-31", 3.0, 0)
    iwm0, spy0 = _turn_of_year("2000-05-26", "2025-12-31", 0.0, 1, sd=0.001)
    rep = u2.january_small_cap(iwm0, spy0, rut, gspc, n_place=300)
    assert rep["placebo_window_days"] == [15]                                  # same-length windows (was a fixed 25)
    assert rep["mean_pp"] > 1 and abs(rep["iwm_spy_mean_pp"]) < 1
    assert rep["verdict"] == "not_supported" and "IWM-SPY mean >= 1 pp" in _failed(rep["reason"])
    iwm3, spy3 = _turn_of_year("2000-05-26", "2025-12-31", 3.0, 1, sd=0.001)
    rep2 = u2.january_small_cap(iwm3, spy3, rut, gspc, n_place=300)
    assert "IWM-SPY" not in _failed(rep2["reason"])


# ------------------------------------------------------------------ U2A-8 (T-352, T-356) --

def _seasonal(start, end, winter_minus_summer_monthly, seed, sd=0.002):
    rng = np.random.default_rng(seed)
    days = _days(start, end)
    winter = np.array([int(d[5:7]) in (11, 12, 1, 2, 3, 4) for d in days])
    r = rng.normal(0.0003, sd, len(days)) + np.where(winter, 1, -1) * winter_minus_summer_monthly / 2 / 21
    return days, _closes(r)


def test_sell_in_may_gates_spy_at_50_bps():
    gspc = _seasonal("1927-12-30", "2025-12-31", 0.025, 0, sd=0.008)
    spy = _seasonal("1993-01-04", "2025-12-31", 0.003, 1, sd=0.0005)
    rep = u2.sell_in_may(gspc, spy)
    assert rep["diff_bps_per_month"] > 50 and 0 < rep["spy_diff_bps"] < 50
    assert rep["verdict"] == "not_supported" and "SPY difference >= 50 bps/month" in _failed(rep["reason"])


def test_gold_autumn_gates_gcf_at_5_bps():
    rng = np.random.default_rng(2)
    days = _days("2004-11-18", "2025-12-31")
    autumn = np.array([int(d[5:7]) in (9, 10, 11) for d in days])
    gld = (days, _closes(rng.normal(0.0002, 0.004, len(days)) + np.where(autumn, 0.0015, 0.0)))
    gdays = _days("2000-08-30", "2025-12-31")
    gcf = (gdays, _closes(rng.normal(0.0002, 0.004, len(gdays))))
    rep = u2.gold_autumn(gld, gcf)
    assert rep["diff_bps"] > 5 and rep["gcf_diff_bps"] < 5
    assert "GC=F difference >= 5 bps/day" in _failed(rep["reason"])


# -------------------------------------------------------------------------- U2A-9 (T-346) --

def test_quarter_end_two_sided_placebo_and_costs():
    rng = np.random.default_rng(3)
    days = _days("2000-01-03", "2025-12-31")
    r = rng.normal(0.0002, 0.002, len(days))
    ym = {}
    for i, d in enumerate(days):
        ym.setdefault(d[:7], []).append(i)
    ms = sorted(ym)
    for a, b in zip(ms[:-1], ms[1:]):
        bump = 0.006 if int(a[5:7]) in (3, 6, 9, 12) else -0.005               # placebo month ends: significantly negative
        r[ym[a][-1]] += bump; r[ym[b][0]] -= bump
    gross = u2.quarter_end_reversal(days, _closes(r), rt_cost=0.0, n_boot=1000)
    rep = u2.quarter_end_reversal(days, _closes(r), n_boot=1000)
    assert rep["cost_bps_per_quarter"] == pytest.approx(4.0)
    assert gross["mean_bps"] - rep["mean_bps"] == pytest.approx(4.0)
    assert rep["placebo_mean_bps"] < -50 and rep["placebo_p"] < 0.1             # one-sided p_pos would be ~1 and pass
    assert "placebo not significant (two-sided p > 0.1)" in _failed(rep["reason"])


# ------------------------------------------------------------------------- U2A-10 (T-353) --

def test_opex_week_keeps_holiday_expiry_weeks():
    holidays = ["2014-04-18", "2019-04-19", "2022-04-15"]                       # third Fridays the market was closed
    days = _days("2000-01-03", "2025-12-31", drop=holidays)
    rng = np.random.default_rng(4)
    rep = u2.opex_week(days, _closes(rng.normal(0.0003, 0.01, len(days))))
    assert rep["n_opex_weeks"] == 26 * 12                                      # one expiry week per month, holidays included
    wd, _ = u2.weekly(days, np.ones(len(days)))
    monday = [date.fromisoformat(d) - timedelta(days=date.fromisoformat(d).weekday()) for d in wd]
    assert all((b - a).days == 7 for a, b in zip(monday[:-1], monday[1:]))      # consecutive weeks, never two merged


# ------------------------------------------------------------ U2A-11 / U2A-12 / U2-2 / U2-4 --

def _falling_crypto(start, end, seed):
    rng = np.random.default_rng(seed)
    days = _days(start, end, weekdays_only=False)
    return days, _closes(-0.0014 + rng.normal(0, 0.0008, len(days)))


def test_crypto_weekly_benchmark_is_historical_mean():
    btc = _falling_crypto("2014-09-17", "2020-12-31", 5); eth = _falling_crypto("2017-11-09", "2020-12-31", 6)
    rep = u2.crypto_weekly_tsmom(btc, eth)
    # falling prices: the historical-mean strategy is flat after its warm-up, as is TSMOM, so d is near 0;
    # against always-long (the old benchmark) d would be about +100 bps/week
    assert abs(rep["mean_diff_bps"]) < 20 and "historical-mean" in rep["reason"]
    v2 = u2.crypto_weekly_v2(btc, eth)
    assert v2["cost_side_bps"] == pytest.approx(40.0) and v2["dsr_n_trials"] == 16
    eth_weeks = u2.weekly(*eth)[0][1:][26:]                                     # ETH's scored weeks, after its own warm-up
    btc_weeks = u2.weekly(*btc)[0][1:][26:]
    assert v2["n_btc_only_weeks"] == sum(1 for k in btc_weeks if k not in set(eth_weeks))
    assert v2["n_btc_only_weeks"] == rep["n_btc_only_weeks"]


def _metal(first_month, last_month, drift, seed):
    rng = np.random.default_rng(seed)
    days = _month_end_days(first_month, last_month)
    return _monthly_series(days, drift + rng.normal(0, 0.01, len(days)))


def test_metals_tsmom_vs_historical_mean_and_bills_criterion():
    gld, slv = _metal("2004-11", "2026-09", -0.02, 7), _metal("2006-04", "2026-09", -0.02, 8)
    gcf, scf = _metal("2000-08", "2026-09", -0.02, 9), _metal("2000-08", "2026-09", -0.02, 10)
    rep = u2.metals_tsmom(gld, slv, gcf, scf)
    # both legs flat on a falling pair: d is exactly 0, so 'difference > 0' fails (always-long would make it pass)
    assert rep["mean_diff_bps"] == pytest.approx(0.0, abs=1e-9) and rep["first_month"] == "2007-06"
    assert "difference vs historical-mean > 0" in _failed(rep["reason"])
    assert "after-cost excess over bills > 0 (T-bill series not supplied)" in _not_implemented(rep["reason"])
    bd, bv = _bills(gld[0], 2.0)
    rep_b = u2.metals_tsmom(gld, slv, gcf, scf, bill_days=bd, bill_vals=bv)
    assert "after-cost excess over bills > 0" in _failed(rep_b["reason"]) and rep_b["excess_over_bills_bps"] < 0


def test_metals_v2_live_benchmark_per_switch_costs_and_trial_count():
    gld, slv = _metal("2004-11", "2026-09", 0.02, 11), _metal("2006-04", "2026-09", 0.02, 12)
    gcf, scf = _metal("2000-08", "2026-09", 0.02, 13), _metal("2000-08", "2026-09", 0.02, 14)
    rep = u2.metals_v2(gld, slv, gcf, scf, *_bills(gld[0], 2.0))
    # rising pair: TSMOM and the historical-mean strategy are both long every scored month and never switch, so d is
    # exactly 0 (the old flat 2 bps charge and the 12 forced-flat benchmark months made it non-zero)
    assert rep["mean_bps"] == pytest.approx(0.0, abs=1e-9)
    assert rep["first_month"] == "2007-06" and rep["futures_n_months"] == rep["n_months"]
    assert rep["dsr_n_trials"] == 24


# ------------------------------------------------------------- U2A-13 / U2A-14 / U2-7 / U2-10 --

def _low_vol_pair(start="2010-01-04", end="2027-06-30", seed=15):
    rng = np.random.default_rng(seed)
    days = _days(start, end)
    u = rng.normal(0.0004, 0.006, len(days))
    return days, (days, _closes(u)), (days, _closes(2 * u))                     # SPY = 2 x USMV: equal raw Sharpe


def test_low_vol_excess_sharpe_window_and_rolling_windows():
    days, usmv, spy = _low_vol_pair()
    raw = u2.low_vol_tilt(usmv, spy, usmv, spy)
    assert raw["diff"] == pytest.approx(0.0, abs=1e-9)
    assert "Sharpe on daily excess returns over T-bills" in _not_implemented(raw["reason"])
    ex = u2.low_vol_tilt(usmv, spy, usmv, spy, bill_days=days, bill_vals=[5.0] * len(days))
    assert ex["diff"] < -0.05 and ex["excess_over_bills"]                    # excess Sharpe favours the higher-vol leg here
    assert "excess returns over T-bills" not in ex["reason"]
    assert ex["first_day"] == "2011-11-01" and ex["last_day"] == "2026-09-30"
    assert ex["window_days"] == 1260 and len(ex["subwindows"]) == 4
    short = u2.low_vol_tilt((days[:900], usmv[1][:900]), (days[:900], spy[1][:900]), bill_days=days, bill_vals=[5.0] * len(days), start="2010-01-01")
    assert "positive in >= 3 of 4 rolling 5-year windows" in _not_implemented(short["reason"])


def test_low_vol_v2_uses_bills_and_drops_mislabelled_spread():
    days, usmv, spy = _low_vol_pair()
    rep = u2.low_vol_v2(usmv, spy, bill_days=days, bill_vals=[5.0] * len(days))
    assert "splv_minus_sphb_bps_day" not in rep and rep["excess_over_bills"]
    assert rep["diff"] < 0 and "T-bill series not supplied" not in rep["reason"]
    assert rep["n_days"] >= 3500
    rep0 = u2.low_vol_v2(usmv, spy)
    assert "T-bill series not supplied" in _not_implemented(rep0["reason"])


def test_v2_reports_drop_reprinted_comparison_series():
    rng = np.random.default_rng(16)
    gdays = _days("2004-11-18", "2025-12-31")
    g = u2.gold_autumn_v2((gdays, _closes(rng.normal(0.0002, 0.01, len(gdays)))))
    assert "gcf_diff_bps" not in g
    s = u2.sell_in_may_v2(_seasonal("1927-12-30", "2025-12-31", 0.0, 17, sd=0.008))
    assert "spy_diff_bps" not in s


# --------------------------------------------------------------------- U2A-15 / U2-4 / U2-5 --

def _crypto(start, end, seed):
    rng = np.random.default_rng(seed)
    days = _days(start, end, weekdays_only=False)
    return days, _closes(rng.normal(0.001, 0.03, len(days)))


def test_golden_cross_scores_from_the_50_200_warm_up():
    btc, eth = _crypto("2014-09-17", "2019-12-31", 18), _crypto("2017-11-09", "2021-12-31", 19)
    rep = u2.golden_cross(btc, eth)
    assert rep["BTC"]["start"] == btc[0][200] and rep["ETH"]["start"] == eth[0][200]   # return index 199, not 300
    assert rep["n"] == min(len(btc[0]), len(eth[0])) - 200


def test_golden_cross_v2_window_and_declared_trials():
    btc, eth = _crypto("2014-09-17", "2019-12-31", 18), _crypto("2017-11-09", "2021-12-31", 19)
    rep = u2.golden_cross_v2(btc, eth)
    assert rep["BTC"]["start"] == "2015-04-05"                                 # first valid 50/200 position inside 2015-04-
    assert rep["ETH"]["start"] == eth[0][200]
    assert rep["BTC"]["dsr_n_trials"] == 72 and rep["n"] == rep["BTC"]["n_days"]


# --------------------------------------------------------------------------------- U2-1 --

def test_svxy_v2_position_from_next_close_and_cash_at_bills():
    rng = np.random.default_rng(20)
    days = _days("2015-01-01", "2020-12-31"); n = len(days)
    ratio = np.where(rng.random(n) < 0.5, 1.2, 0.9)
    vix = {d: 20.0 for d in days}; vix3m = {d: 20.0 * x for d, x in zip(days, ratio)}
    ret = np.zeros(n)
    ret[1:] = np.where(ratio[:-1] > 1.05, 0.03, -0.03) + rng.normal(0, 0.005, n - 1)    # r(close t -> t+1) set by signal t
    rep = u2.svxy_v2((days, _closes(ret)), vix, vix3m, test_from="2016-01-01")
    assert rep["sharpe_diff"] < 1.0                                            # the lag-0 fill would show a Sharpe gap of ~30
    assert "cash leg earns the T-bill rate" in _not_implemented(rep["reason"])
    cash = {d: 20.0 * 0.9 for d in days}                                       # never in contango: always in cash
    rep_b = u2.svxy_v2((days, _closes(ret)), vix, cash, test_from="2016-01-01", bill_days=days, bill_vals=[5.0] * n)
    assert rep_b["strategy_mean_bps_day"] == pytest.approx(5.0 / 252 * 100, rel=1e-9)
    assert rep_b["cash_leg"] == "T-bill" and "T-bill" in rep_b["reason"]


# --------------------------------------------------------------------------------- U2-3 --

def test_tom_replication_v2_null_shares_calendar_blocks():
    rng = np.random.default_rng(21)
    days = _days("2008-01-01", "2020-12-31")
    r = rng.normal(0.0003, 0.008, len(days))
    series = {s: (days, _closes(r)) for s in ("QQQ", "IWM", "TLT", "GLD", "BTC-USD")}   # five perfectly correlated assets
    rep = u2.tom_replication_v2(series, {s: 2 for s in series}, n_boot=60)
    # one shared set of calendar blocks per replicate: identical assets pass or fail together (independent per-asset
    # shifts, the old null, spread the count over 0..5)
    assert set(rep["null_count_freq"]) <= {0, 5}


# --------------------------------------------------------------------------------- U2-6 --

def test_v2_pbo_over_declared_grid_is_not_implemented():
    days, spy, efa, agg = _gem_inputs()
    g = u2.gem_v2(spy, efa, agg, *_bills(days, 2.0))
    assert "PBO < 0.5 over the declared 60-trial matrix" in _not_implemented(g["reason"]) and "pbo_proxy_10_lookbacks" in g
    sdays, sectors, sspy = _sectors_iid(22)
    s = u2.sector_rotation_v2(sectors, sspy, *_bills(sdays, 2.0), n_perm=20)
    assert "PBO < 0.5 over the declared 96-trial grid" in _not_implemented(s["reason"]) and "pbo_proxy_12_variants" in s


# --------------------------------------------------------------------------------- U2-8 --

def test_sell_in_may_v2_post_publication_window():
    rng = np.random.default_rng(23)
    days = _days("1927-12-30", "2026-10-14")
    m = np.array([d[:7] for d in days])
    summer = np.array([5 <= int(d[5:7]) <= 10 for d in days])
    r = rng.normal(0.0003, 0.0005, len(days)) + np.where(summer, 0.00005, 0.0)        # summer slightly better throughout
    r[(m >= "2002-05") & (m <= "2002-10")] -= 0.05 / 21                                 # a summer-2002 crash
    rep = u2.sell_in_may_v2((days, _closes(r)))
    assert rep["post_window"] == ["2002-11", "2026-09"]                                 # Oct 2026 is incomplete: dropped
    assert rep["post2002_diff_bps"] < 0                                                 # season years from 2002 would include the crash
    assert "2002-11..2026-10 difference > 0" in _failed(rep["reason"])
