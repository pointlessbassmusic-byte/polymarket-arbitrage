"""Batch-4 OHLC harnesses on synthetic bars: planted effects pass, noise fails. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch4_ohlc as ob


def _days(start, end, weekdays_only=True):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _path(night, day, c0=100.0, divs=None):
    """opens/closes from overnight and intraday returns; with divs the open drops by D (ex-dividend)."""
    n = len(night) + 1
    O, C = np.empty(n), np.empty(n)
    O[0] = C[0] = c0
    D = np.zeros(n) if divs is None else np.asarray(divs, dtype=float)
    for t in range(1, n):
        O[t] = C[t - 1] * (1 + night[t - 1]) - D[t]
        C[t] = O[t] * (1 + day[t - 1])
    return O, C


# ------------------------------------------------------------------------------------------------- data layer --

def test_bars_from_rows_filters_capture_and_bad_rows():
    def row(day, avail, **v):
        t = datetime.fromisoformat(day + "T14:30:00+00:00").timestamp()
        base = {"t": t, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "adjclose": 10.0}
        base.update(v)
        return {"available_at": avail, "value": base}
    rows = [row("2024-01-02", "2024-01-03T14:30:00+00:00"), row("2024-01-03", "2024-01-04T14:30:00+00:00", open=None),
            row("2024-01-04", "2024-01-05T14:30:00+00:00", low=0.0), row("2024-01-05", "2024-01-06T14:30:00+00:00", adjclose=None),
            row("2024-01-08", "2024-01-09T14:30:00+00:00")]
    b = ob.bars_from_rows(rows, captured_at="2024-01-08T00:00:00+00:00")
    assert b.days == ["2024-01-02", "2024-01-05"]
    assert b.adj[0] == 10.0 and b.adj[1] == 10.5          # adjclose falls back to close


def test_ex_dividends_recovers_cash_dividend():
    close = np.array([100.0, 101.0, 100.5, 102.0])
    D = 0.8                                                   # ex-date at index 2: earlier adjclose scaled by 1 - D/C_1
    f = np.array([1 - D / close[1], 1 - D / close[1], 1.0, 1.0])
    adj = (close * f).astype(np.float32).astype(float)        # Yahoo stores float32
    d = ob.ex_dividends(close, adj)
    assert d[2] == pytest.approx(D, rel=1e-4)
    assert d[1] == 0 and d[3] == 0 and d[0] == 0


def test_stationary_bootstrap_block_length():
    rng = np.random.default_rng(0)
    idx = ob.stationary_idx(20000, 20, rng)
    breaks = np.sum(np.diff(idx) != 1) + 1
    assert 20000 / breaks == pytest.approx(20, rel=0.15)
    assert idx.min() >= 0 and idx.max() < 20000


def test_trailing_z_uses_prior_window():
    x = np.concatenate([np.tile([0.0, 1.0], 30), [10.0]])
    z = ob._trailing_z(x, 60)
    assert np.isnan(z[59]) and z[60] == pytest.approx((10 - 0.5) / np.std(x[:60], ddof=1))
    zi = ob._trailing_z(x, 60, include_current=True)
    assert zi[60] == pytest.approx((10 - x[1:61].mean()) / np.std(x[1:61], ddof=1))


# ----------------------------------------------------------------------------------- T-348 overnight vs intraday --

def _night_day(n, night_mu, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(night_mu, 0.005, n), rng.normal(0.0, 0.008, n)


def test_overnight_intraday_planted_gap_supported():
    days = _days("1993-02-01", "2026-09-30")
    night, day = _night_day(len(days) - 1, 0.0008)
    O, C = _path(night, day)
    rep = ob.overnight_intraday(days, O, C)
    assert rep["gap_bps"] > 3 and rep["p_gap_le_threshold"] < 0.05 and all(h > 0 for h in rep["halves_gap_bps"])
    assert rep["verdict"] == "supported", rep["reason"]
    assert rep["reason"].endswith("all criteria pass")


def test_overnight_intraday_null_not_supported():
    days = _days("1993-02-01", "2026-09-30")
    night, day = _night_day(len(days) - 1, 0.0, seed=1)
    O, C = _path(night, day)
    rep = ob.overnight_intraday(days, O, C)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_overnight_intraday_p_is_against_the_3bp_magnitude():
    """Regression (T-348): a gap just above 3 bps that is significant only against equal means fails the claim
    'at least 3 bps per trading day'; the p criterion is H0: gap <= 3 bps."""
    days = _days("1993-02-01", "2026-09-30")
    night, day = _night_day(len(days) - 1, 0.0, seed=9)
    early = np.array(days[1:]) < "2010-01-01"
    for g in (early, ~early):                                        # exact gap of 3.3 bps in each half
        night[g] += 0.00033 - night[g].mean(); day[g] -= day[g].mean()
    O, C = _path(night, day)
    rep = ob.overnight_intraday(days, O, C)
    assert rep["gap_bps"] == pytest.approx(3.3, abs=1e-6) and all(h > 0 for h in rep["halves_gap_bps"])
    assert rep["p_equal_means"] < 0.05                                # positive gap is significant ...
    assert rep["p_gap_le_threshold"] >= 0.05 and rep["gap_lower95_one_sided_bps"] < 3   # ... but not one of at least 3 bps
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert "failed: p < 0.05 vs gap <= 3 bps" in rep["reason"]


def test_overnight_intraday_adds_dividends_back():
    days = _days("1993-02-01", "2026-09-30")
    night, day = _night_day(len(days) - 1, 0.0008, seed=2)
    divs = np.zeros(len(days)); divs[60::63] = 0.5                   # quarterly ex-dates
    O, C = _path(night, day, divs=divs)
    with_div = ob.overnight_intraday(days, O, C, divs=divs)
    without = ob.overnight_intraday(days, O, C)
    assert with_div["mean_night_bps"] == pytest.approx(night.mean() * 1e4, abs=1e-6)
    assert without["mean_night_bps"] < with_div["mean_night_bps"]
    assert with_div["n_ex_dividend_days"] == int((divs > 0).sum())


def test_overnight_intraday_short_sample_inconclusive():
    days = _days("2020-01-01", "2022-12-31")
    night, day = _night_day(len(days) - 1, 0.002)
    O, C = _path(night, day)
    rep = ob.overnight_intraday(days, O, C)
    assert rep["verdict"] == "inconclusive" and "min_n" in rep["reason"]


# -------------------------------------------------------------------------------------------- T-333 gap fade --

def _gap_path(beta, seed=0):
    days = _days("2000-01-03", "2026-09-30")
    rng = np.random.default_rng(seed)
    o = rng.normal(0, 0.008, len(days) - 1)
    i = beta * o + rng.normal(0, 0.006, len(days) - 1)
    O, C = _path(o, i)
    return days, O, C


def test_gap_fade_planted_reversal_supported():
    days, O, C = _gap_path(-0.4)
    sh = [ob.sharpe_ratio(ob.gap_fade_series(O, C, thr, 0.0002)[3]) for thr in (0.0025, 0.005, 0.01)] * 2
    rep = ob.gap_fade(days, O, C, variant_sharpes=sh)
    assert rep["ci_bps"][0] > 0 and rep["dsr"] > 0.95 and rep["corr_o_i"] < 0
    assert rep["verdict"] == "supported", rep["reason"]


def test_gap_fade_null_not_supported():
    days, O, C = _gap_path(0.0, seed=3)
    rep = ob.gap_fade(days, O, C, variant_sharpes=[0.0] * 6)
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert rep["mean_net_bps"] == pytest.approx(-2.0, abs=4.0)       # only the 2 bps round trip


def test_gap_fade_without_variants_is_at_best_inconclusive():
    days, O, C = _gap_path(-0.4)
    rep = ob.gap_fade(days, O, C)
    assert rep["dsr"] is None and rep["verdict"] == "inconclusive"


def test_gap_fade_sides():
    O = np.array([100.0, 99.0, 101.5, 100.0])          # gap -1% (long), +2.5% (short), -1.5% (long)
    C = np.array([100.0, 99.5, 101.0, 100.0])
    o, i, side, daily = ob.gap_fade_series(O, C, 0.005, 0.0002)
    assert list(side) == [1.0, -1.0, 1.0]
    assert daily[0] == pytest.approx(99.5 / 99 - 1 - 0.0002)
    assert daily[1] == pytest.approx(-(101 / 101.5 - 1) - 0.0002)


def test_gap_fade_series_adds_ex_dividend_back():
    """Regression (T-333): the cash dividend that lands overnight is not a gap. Day 1: real gap +0.2% with D = 0.8
    (raw gap -0.6%, a false long). Day 2: real gap +0.9% with D = 0.5 (raw gap about +0.4%, a missed short)."""
    C = np.array([100.0, 100.0, 100.0])
    D = np.array([0.0, 0.8, 0.5])
    O = np.array([100.0, 100.0 * 1.002 - 0.8, 100.0 * 1.009 - 0.5])
    o_raw, _, side_raw, _ = ob.gap_fade_series(O, C, 0.005, 0.0002)
    o, i, side, daily = ob.gap_fade_series(O, C, 0.005, 0.0002, divs=D)
    assert list(side_raw) == [1.0, 0.0] and list(side) == [0.0, -1.0]
    assert o == pytest.approx([0.002, 0.009])
    assert i == pytest.approx(C[1:] / O[1:] - 1)                     # intraday leg is unchanged


def test_gap_fade_reports_raw_gap_sensitivity():
    days, O, C = _gap_path(-0.4, seed=10)
    D = np.zeros(len(days)); D[60::63] = 0.006 * C[59::63][: len(D[60::63])]   # quarterly ex-dates, 60 bps
    O = O - D                                                       # the dividend lands in the open
    sh = [0.05] * 6
    rep = ob.gap_fade(days, O, C, variant_sharpes=sh, divs=D)
    raw = rep["raw_gap_sensitivity"]
    assert rep["dividend_neutral_gap"] and raw["n_ex_dividend_days"] > 90
    assert raw["n_side_changed"] > 0 and raw["n_raw_trades_on_ex_dividend_days"] > raw["n_trades_on_ex_dividend_days"]
    assert "raw-gap sensitivity" in rep["reason"] and raw["ci_bps"][0] is not None
    plain = ob.gap_fade(days, O, C, variant_sharpes=sh)
    assert plain["raw_gap_sensitivity"] is None and plain["n"] == raw["n_trades"]


# ------------------------------------------------------------------------------------------- T-332 IBS reversal --

def _ibs_bars(effect, seed=0):
    days = _days("2000-01-03", "2026-09-30")
    n = len(days)
    rng = np.random.default_rng(seed)
    x = rng.random(n)
    r = rng.normal(0.0002, 0.01, n)
    r[1:] += effect * (x[:-1] < 0.2)                    # next-day return after a low-IBS close
    C = 100 * np.cumprod(1 + r)
    rngw = C * 0.012
    L = C - x * rngw
    H = L + rngw
    return days, H, L, C


def test_ibs_planted_effect_supported():
    days, H, L, C = _ibs_bars(0.003)
    grid = [ob.sharpe_ratio(ob.rule_daily_net(p, C)) for p in ob.reversal_rule_positions(H, L, C, C).values()] * 2
    rep = ob.ibs_reversal(days, H, L, C, C, grid_sharpes=grid)
    assert rep["ci_bps"][0] > 2 and rep["dsr"] > 0.95 and rep["p_block_shift"] < 0.05
    assert rep["verdict"] == "supported", rep["reason"]


def test_ibs_null_not_supported():
    days, H, L, C = _ibs_bars(0.0, seed=4)
    grid = [0.01] * 12
    rep = ob.ibs_reversal(days, H, L, C, C, grid_sharpes=grid)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_ibs_definition_and_rules():
    assert ob.ibs([11.0, 10.0], [9.0, 10.0], [9.2, 10.0])[0] == pytest.approx(0.1)
    assert math.isnan(ob.ibs([11.0, 10.0], [9.0, 10.0], [9.2, 10.0])[1])
    c = np.array([10, 9, 8, 7, 8, 9], dtype=float)
    pos = ob.reversal_rule_positions(c + 0.5, c - 0.5, c, c)["down3"]
    assert list(pos) == [0, 0, 0, 1, 0, 0]               # in after three down closes, out at the first up close
    net = ob.rule_daily_net(np.array([0, 1, 1, 0.0]), np.array([100, 100, 110, 121.0]), cost_side=0.001)
    assert net == pytest.approx([0.0, 0.1 - 0.001, 0.1])


# ------------------------------------------------------------------------------ T-421 Corwin-Schultz spread shock --

def test_corwin_schultz_bounce_and_trend():
    # constant mid with highs at the ask and lows at the bid: the two-day range equals the one-day range
    H, L, C = np.array([101.0, 101.0]), np.array([99.0, 99.0]), np.array([100.0, 100.0])
    s = ob.corwin_schultz(H, L, C)
    b = 2 * math.log(101 / 99) ** 2; g = math.log(101 / 99) ** 2; k = 3 - 2 * math.sqrt(2)
    a = (math.sqrt(2 * b) - math.sqrt(b)) / k - math.sqrt(g / k)
    assert s[1] == pytest.approx(2 * (math.exp(a) - 1) / (1 + math.exp(a)))
    assert s[1] > 0.005
    # a strong trend: two-day range much wider than daily ranges -> negative estimate set to 0
    s2 = ob.corwin_schultz(np.array([100.5, 103.5]), np.array([99.5, 102.5]), np.array([100.0, 103.0]))
    assert s2[1] == 0.0


def _shock_bars(drift, seed=0):
    days = _days("1999-06-01", "2026-09-30")
    n = len(days)
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.01, n)
    w = np.full(n, 0.004)
    shocks = np.arange(80, n - 30, 40)
    for s in shocks:
        r[s] = 0.0                       # close unchanged on the shock day, both days' ranges wide
        w[s - 1] = w[s] = 0.04
        r[s + 2: s + 22] += drift
    C = 100 * np.cumprod(1 + r)
    H, L = C * (1 + w / 2), C * (1 - w / 2)
    vix = {d: 20 + v for d, v in zip(days, np.cumsum(rng.normal(0, 0.5, n)))}
    return days, H, L, C, vix


def test_spread_shock_planted_supported():
    days, H, L, C, vix = _shock_bars(0.002)
    rep = ob.spread_shock(days, H, L, C, C, vix)
    assert rep["n"] >= 60 and rep["coef_shock"] >= 0.01 and rep["p_coef_le0"] < 0.05
    assert rep["verdict"] == "supported", rep["reason"]


def test_spread_shock_null_not_supported():
    days, H, L, C, vix = _shock_bars(0.0, seed=5)
    rep = ob.spread_shock(days, H, L, C, C, vix)
    assert rep["n"] >= 60
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_spread_shock_too_few_events_inconclusive():
    days, H, L, C, vix = _shock_bars(0.002)
    rep = ob.spread_shock(days, H, L, C, C, vix, start="2024-01-01")
    assert rep["verdict"] == "inconclusive" and rep["n"] < 60


def test_hold_positions_window():
    pos = ob._hold_positions(30, [5], 20)
    assert pos[6] == 0 and pos[7] == 1 and pos[26] == 1 and pos[27] == 0


# ---------------------------------------------------------------------------------------------- T-304 Donchian --

def test_atr_and_donchian_trade_mechanics():
    n = 120
    C = np.concatenate([np.full(70, 100.0), np.linspace(100.5, 110, 20), np.full(5, 110.0), [100.0], np.full(n - 96, 99.0)])
    H, L = C + 1.0, C - 1.0
    atr = ob.atr_wilder(H, L, C, 20)
    assert atr[20] == pytest.approx(2.0)                                 # constant 2-point range
    trades, open_e = ob.donchian_atr_trades(H, L, C, n=55, atr_n=20, mult=10.0)
    assert trades and trades[0][0] == 56                                 # flat closes equal the 55-day max: signal at 55
    e, x = trades[-1]
    assert x == 96                                                       # the drop at 95 breaks the 13-day low; filled next close


def _trend_assets(regime, n_assets=8, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2000-01-03", "2015-12-31")
    out = {}
    for k in range(n_assets):
        n = len(days)
        mu = np.zeros(n); t = 0; sgn = 1.0
        while t < n:
            L = int(rng.integers(60, 160)); mu[t:t + L] = sgn * regime; sgn = -sgn; t += L
        r = mu + rng.normal(0, 0.01, n)
        C = 100 * np.cumprod(1 + r)
        out[f"A{k}"] = {"days": days, "high": C * 1.005, "low": C * 0.995, "close": C, "cost": 0.0005, "ppy": 252}
    return out


def test_breakout_planted_trend_supported():
    rep = ob.breakout_vs_random(_trend_assets(0.004), n_random=200, n_boot=2000)
    assert rep["n"] >= 150 and rep["ci"][0] > 0
    assert rep["verdict"] == "supported", rep["reason"]


def test_breakout_random_walk_not_supported():
    rep = ob.breakout_vs_random(_trend_assets(0.0, seed=6), n_random=200, n_boot=2000)
    assert rep["n"] >= 150
    assert rep["verdict"] == "not_supported", rep["reason"]


# -------------------------------------------------------------------------------------------- T-324 twin spread --

def test_twin_trades_exit_rules():
    z = np.array([0, 2.5, 1.0, 0.5, -0.1, 0, 0, -3, -2, -2, -2, -2, -2, -2, -2, 0], dtype=float)
    tr = ob.twin_trades(z, 0, 14, 2.0, 5)
    assert tr[0] == (2, 5, -1.0)          # z > 2 at 1, in at 2, crosses at 4, out at 5
    assert tr[1] == (8, 13, 1.0)          # z < -2 at 7, in at 8, no cross: out 5 days later


def _twins(phi, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("2009-06-01", "2026-09-30")
    n = len(days)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0, 0.0015)
    common = np.cumsum(rng.normal(0.0003, 0.01, n))
    return days, np.exp(common + x) * 100, np.exp(common) * 100


def test_twin_planted_reversion_supported():
    days, a, b = _twins(0.5)
    rep = ob.twin_reversion(days, a, b, min_n=100)
    assert rep["n"] == rep["n_trades"] >= 100
    assert rep["ci_bps"][0] > 0 and rep["dsr"] > 0.95 and rep["half_life_days"] < 2
    assert rep["verdict"] == "supported", rep["reason"]


def test_twin_random_walk_not_supported():
    days, a, b = _twins(1.0, seed=7)
    rep = ob.twin_reversion(days, a, b, min_n=100)
    assert rep["n_trades"] >= 100
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_twin_min_n_counts_trades():
    """Regression (T-324): the statistic is per trade, so min_n 1000 counts trades, not daily observations of x.
    Fewer trades -> never supported, with the interval still reported in the reason. House rule 5: the random walk's
    net CI lies wholly below 0 (a decisive failure), so the verdict is not_supported rather than capped at inconclusive."""
    days, a, b = _twins(1.0, seed=7)
    rep = ob.twin_reversion(days, a, b)
    assert rep["n"] == rep["n_trades"] < 1000 < rep["n_days"]
    assert rep["ci_bps"][1] < 0
    assert rep["verdict"] == "not_supported", rep["reason"]
    assert f"{rep['n_trades']} trades, below the trial's min_n 1000" in rep["reason"] and "house rule 5" in rep["reason"]
    assert "fails decisively below min_n" in rep["reason"]
    assert "95% lower bound of mean net return per trade > 0" in rep["rule5"]["decisive_failures"]
    assert f"{rep['ci_bps'][0]:+.2f}..{rep['ci_bps'][1]:+.2f}" in rep["reason"]
    assert rep["criteria_on_available_trades"]["95% lower bound of mean net return per trade > 0"] is False


# ------------------------------------------------------------------------------------ T-216 opex MODEL-PRICED --

def test_third_friday_and_premium():
    assert ob.third_friday(2024, 3).isoformat() == "2024-03-15"
    assert ob.third_friday(2026, 10).isoformat() == "2026-10-16"
    days = ["2024-03-14", "2024-03-15"]
    fri, pnl, raw, prem = ob.thu_fri_straddles(days, [100.0, 100.0], {"2024-03-14": 16.0})
    assert fri == ["2024-03-15"] and pnl[0] == pytest.approx(prem[0])
    assert prem[0] == pytest.approx(0.16 / np.sqrt(252) * np.sqrt(2 / np.pi), rel=0.01)


def test_thu_fri_straddle_settles_raw_and_prices_the_dividend():
    """Regression (T-216): settlement is the raw |SPY_Fri - SPY_Thu|; the dividend known before the ex-date moves the
    model forward to S_thu - D instead of moving the settlement. The as-worded r = q = 0 price ignores it."""
    days, vix = ["2024-03-14", "2024-03-15"], {"2024-03-14": 16.0}
    T = 1 / 252
    fri, pnl, raw, prem = ob.thu_fri_straddles(days, [100.0, 99.4], vix, divs=[0.0, 0.6])  # the close falls by D only
    p_fwd = (ob.bs.price(99.4, 100.0, T, 0.0, 0.16, "call") + ob.bs.price(99.4, 100.0, T, 0.0, 0.16, "put")) / 100
    p_atm = (ob.bs.price(100.0, 100.0, T, 0.0, 0.16, "call") + ob.bs.price(100.0, 100.0, T, 0.0, 0.16, "put")) / 100
    assert prem[0] == pytest.approx(p_fwd) and p_fwd > p_atm
    assert pnl[0] == pytest.approx(p_fwd - 0.006)                    # settled on |99.4 - 100|, not on C + D
    assert raw[0] == pytest.approx(p_atm - 0.006)
    _, pnl0, raw0, prem0 = ob.thu_fri_straddles(days, [100.0, 99.4], vix)  # no dividend: both prices agree
    assert pnl0[0] == pytest.approx(raw0[0]) == pytest.approx(p_atm - 0.006) and prem0[0] == pytest.approx(p_atm)


def _opex_closes(opex_sd, seed=0):
    rng = np.random.default_rng(seed)
    days = _days("1993-02-01", "2026-09-30")
    tf = {ob.third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in days}
    r = np.array([rng.normal(0, opex_sd if d in tf else 0.01) for d in days])
    return days, 100 * np.cumprod(1 + r), {d: 16.0 for d in days}


def test_opex_planted_pin_supported():
    days, C, vix = _opex_closes(0.003)
    rep = ob.opex_straddle(days, C, vix, n_boot=1000, n_perm=200)
    assert rep["label"] == "MODEL-PRICED" and rep["reason"].startswith("MODEL-PRICED")
    assert rep["n"] >= 300 and rep["ci_bps"][0] > 0
    assert rep["verdict"] == "supported", rep["reason"]


def test_opex_null_not_supported():
    days, C, vix = _opex_closes(0.01, seed=8)
    rep = ob.opex_straddle(days, C, vix, n_boot=1000, n_perm=200)
    assert rep["verdict"] == "not_supported", rep["reason"]


def test_opex_reports_as_worded_dividend_sensitivity():
    """Regression (T-216): with a 1% cash dividend going ex on every opex Friday, the forward-priced model keeps the
    planted pin, the as-worded r = q = 0 price charges the drop to the seller, and the reason says the verdict
    depends on the dividend treatment."""
    rng = np.random.default_rng(11)
    days = _days("1993-02-01", "2026-09-30")
    tf = {ob.third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in days}
    C, D = np.empty(len(days)), np.zeros(len(days))
    C[0] = 100.0
    for t in range(1, len(days)):
        opex = days[t] in tf
        D[t] = 0.01 * C[t - 1] if opex else 0.0
        C[t] = C[t - 1] * (1 + rng.normal(0, 0.006 if opex else 0.01)) - D[t]
    rep = ob.opex_straddle(days, C, {d: 16.0 for d in days}, divs=D, n_boot=1000, n_perm=200)
    assert rep["settlement"].startswith("raw closes") and rep["n_ex_dividend_opex"] == rep["n"]
    assert rep["verdict"] == "supported", rep["reason"]
    aw = rep["as_worded_r0_no_dividend"]
    assert aw["diff_bps"] < rep["diff_bps"] and aw["verdict"] == "not_supported"
    assert rep["verdict_depends_on_dividend_treatment"] and "depends on how the dividend is treated" in rep["reason"]


# --------------------------------------------------------------------------------------- harness contract --

class _Entry:
    def __init__(self, created_at):
        self.created_at = created_at


class _FakeArchive:
    def __init__(self, bundles):
        self.b = bundles

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry("2026-10-15T08:00:00+00:00")

    def load(self, name):
        return iter(self.b[name])


def _price_rows(sym, days, seed):
    rng = np.random.default_rng(seed)
    C = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(days)))
    O = C * (1 + rng.normal(0, 0.003, len(days)))
    rows = []
    for d, o, c in zip(days, O, C):
        t = datetime.fromisoformat(d + "T14:30:00+00:00").timestamp()
        rows.append({"available_at": d + "T23:00:00+00:00",
                     "value": {"symbol": sym, "t": t, "open": o, "high": max(o, c) * 1.004, "low": min(o, c) * 0.996, "close": c, "adjclose": c}})
    return rows


def test_harness_maps_are_consistent():
    assert set(ob.THEORY_MAP) == {"T-216", "T-304", "T-324", "T-332", "T-333", "T-348", "T-421"}
    assert set(ob.THEORY_MAP.values()) == set(ob.HARNESSES)
    assert all(k.startswith("ohlc_") for k in ob.HARNESSES)


def test_harnesses_report_missing_bundles_as_inconclusive():
    arc = _FakeArchive({})
    for name, fn in ob.HARNESSES.items():
        stat, n, verdict, reason = fn(arc)
        assert verdict == "inconclusive" and n == 0 and "missing" in reason, name


def test_harnesses_run_end_to_end_on_synthetic_archive():
    days = _days("2016-01-04", "2021-12-31")
    syms = ["SPY", "IVV", "QQQ", "IBIT", "GLD", "SLV", "XLK", "XLE", "BTC-USD", "ETH-USD"]
    bundles = {ob._bundle(s): _price_rows(s, days, k) for k, s in enumerate(syms)}
    bundles["cboe-VIX-history"] = [{"available_at": d + "T23:00:00+00:00", "value": {"day": d, "close": 18.0}} for d in days]
    bundles["fomc-meetings"] = [{"value": {"decision_day": "2018-03-21", "scheduled": True}}]
    arc = _FakeArchive(bundles)
    ob._CACHE.clear()
    for name, fn in ob.HARNESSES.items():
        stat, n, verdict, reason = fn(arc)
        json.dumps(stat)
        assert verdict in {"supported", "not_supported", "inconclusive"}, name
        assert " — " in reason and isinstance(n, int), name
