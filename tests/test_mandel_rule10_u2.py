"""Rule 10 (no arbitrary grid phase) for mandel/experiments/underlying.py and underlying2.py.

The only harness in these files whose verdict rested on a non-overlapping cycle grid with an arbitrary start is
crypto_weekly_v2 (T-486: 'weekly series from daily closes', no week end named), which used ISO weeks ending Sunday.
It now pools the seven week-ending grids (a 1-week hold entered every day). crypto_weekly_tsmom (T-315) names the
Sunday close, so it stays on the Sunday calendar. Every other harness in the two files is on calendar months, fixed
event dates or daily series.
"""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import underlying2 as u2
from mandel.validation.backtest_eval import deflated_sharpe_ratio


def _plant(start, end, seed, A=0.03, e_sd=0.027, stay=0.9, noise=0.002, sunday_only=True):
    """7-day crypto closes. Each Sunday-ending week t has a persistent sign x_t = +-A (Markov, stays with prob 0.9). With
    sunday_only, x_t sits on that week's Monday and Sunday as x_t/2 + e_t and x_t/2 - e_t: the Sunday-ending week sums to
    x_t (strong 1-week momentum), but every other week-ending grid sees u_{t-1} + m_t = (x_{t-1} + x_t)/2 + e_t - e_{t-1},
    whose lag-1 autocovariance (1 + rho)^2 A^2 / 4 - e_sd^2 is about zero at e_sd = 0.027: momentum on exactly one grid
    phase. Without sunday_only, x_t is spread evenly over the week and every grid sees it."""
    rng = np.random.default_rng(seed)
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
    r = rng.normal(0, noise, len(days))
    wk = [d + timedelta(days=(6 - d.weekday()) % 7) for d in days]
    sig, s = {}, 1.0
    for w in sorted(set(wk)):
        s = s if rng.random() < stay else -s
        sig[w] = s
    e = {w: rng.normal(0, e_sd) for w in sig}
    for i, d in enumerate(days):
        xt = sig[wk[i]] * A
        if not sunday_only:
            r[i] += xt / 7
        elif d.weekday() == 0:
            r[i] += xt / 2 + e[wk[i]]
        elif d.weekday() == 6:
            r[i] += xt / 2 - e[wk[i]]
    return [d.isoformat() for d in days], np.cumprod(1 + r) * 100


def _pair(**kw):
    return _plant("2014-09-17", "2026-09-30", 1, **kw), _plant("2017-11-09", "2026-09-30", 2, **kw)


def test_one_phase_momentum_does_not_pass_t486():
    btc, eth = _pair()
    rep = u2.crypto_weekly_v2(btc, eth)
    sun = rep["per_week_end"]["Sun"]
    # the old harness (Sunday grid only) would pass: the planted effect is real on that one grid
    assert sun["pass"] and sun["mean_bps"] > 80 and sun["ci_bps"][0] > 0 and sun["dsr"] > 0.95
    others = [g for k, g in rep["per_week_end"].items() if k != "Sun"]
    assert all(not g["pass"] and abs(g["mean_bps"]) < 30 for g in others)
    assert rep["week_ends_passing"] == 1
    # pooled all-start estimate is primary: it does not pass
    assert rep["verdict"] != "supported"
    assert rep["ci_bps"][0] <= 0 and rep["dsr"] <= 0.95
    assert "1/7 week ends pass" in rep["reason"] and "pooled over all 7 week-ending weekdays" in rep["reason"]
    lo, hi = rep["per_week_end_mean_bps_range"]
    assert lo < 0 < 80 < hi


def test_one_phase_momentum_still_found_where_claim_names_sunday_t315():
    """Calendar-aligned case: T-315 names the week end ('Sunday close used Monday open'), so its Sunday grid is the claim's
    own calendar and the Sunday-only effect is (correctly) found there."""
    btc, eth = _pair()
    rep = u2.crypto_weekly_tsmom(btc, eth)
    assert rep["verdict"] == "supported" and rep["ci_bps"][0] > 0
    # and it is exactly the Sunday grid of the pooled harness at T-315's costs
    ks, s, h, _ = u2._crypto_weekly_pool(btc, eth, 1, 0.003)
    assert rep["mean_diff_bps"] == pytest.approx(float((s - h).mean() * 1e4))
    ks6, s6, h6, _ = u2._crypto_weekly_pool(btc, eth, 1, 0.003, weekday=6)
    assert ks6 == ks and np.array_equal(s6, s) and np.array_equal(h6, h)


def test_phase_robust_momentum_passes_t486():
    btc, eth = _pair(sunday_only=False)
    rep = u2.crypto_weekly_v2(btc, eth)
    assert rep["verdict"] == "supported" and rep["week_ends_passing"] == 7


def test_pooled_series_and_units():
    btc, eth = _pair()
    rep = u2.crypto_weekly_v2(btc, eth)
    per, ks, d = u2._weekly_phases(btc, eth, 1, 0.004)
    assert len(d) == sum(len(x[1]) for x in per.values()) == rep["n_daily_entries"]
    assert ks == sorted(ks)                                                   # one timeline, a hold entered every day
    assert rep["mean_bps"] == pytest.approx(float(d.mean() * 1e4))
    # n stays in weeks (the claim's units), not daily entries
    assert rep["n"] == rep["n_weeks"] == min(len(x[1]) for x in per.values())
    assert abs(rep["n_weeks"] - rep["n_daily_entries"] / 7) < 2
    assert rep["block_daily_entries"] == 56 >= 2 * 7                         # 8 weeks of daily entries, >= 2 x the hold
    # the Sunday grid is the pre-rule-10 computation
    ks0, s0, h0, nb0 = u2._crypto_weekly_pool(btc, eth, 1, 0.004)
    assert rep["per_week_end"]["Sun"]["mean_bps"] == pytest.approx(float((s0 - h0).mean() * 1e4))
    assert rep["n_btc_only_weeks"] == nb0


def test_dsr_at_n_matches_deflated_sharpe_ratio():
    x = np.random.default_rng(0).normal(0.002, 0.02, 500)
    assert u2._dsr_at_n(x, 16, 0.003, len(x)) == pytest.approx(deflated_sharpe_ratio(x, n_trials=16, var_trials_sr=0.003))
    assert u2._dsr_at_n(x, 16, 0.0, len(x)) == pytest.approx(deflated_sharpe_ratio(x, n_trials=16, var_trials_sr=0.0))
    # fewer effective observations (overlapping entries counted in weeks) pull the DSR toward 0.5: less evidence either way
    for mu in (0.0005, 0.005):
        y = x - 0.002 + mu
        full, weeks = u2._dsr_at_n(y, 16, 0.003, len(y)), u2._dsr_at_n(y, 16, 0.003, len(y) // 7)
        assert abs(weeks - 0.5) < abs(full - 0.5)


def _iso_weekly(days, closes):
    last = {}
    for d, c in zip(days, closes):
        y, w, _ = date.fromisoformat(d).isocalendar()
        last[(y, w)] = (d, c)
    ks = sorted(last)
    return [last[k][0] for k in ks], np.array([last[k][1] for k in ks])


def test_weekly_default_is_iso_week_and_weekday_sets_the_week_end():
    rng = np.random.default_rng(1)
    d0 = date(2019, 12, 25)
    every = [(d0 + timedelta(days=i)).isoformat() for i in range(800)]
    trading = [d for d in every if date.fromisoformat(d).weekday() < 5 and d not in ("2020-01-01", "2020-04-10", "2021-12-24")]
    for days in (every, trading):
        c = rng.normal(100, 1, len(days))
        wd, wc = u2.weekly(days, c)
        iw, ic = _iso_weekly(days, c)
        assert wd == iw and np.array_equal(wc, ic)                            # default unchanged (opex_week, T-315)
    c = np.arange(len(every), dtype=float)
    for w in range(7):
        wd, wc = u2.weekly(every, c, w)
        assert all(date.fromisoformat(d).weekday() == w for d in wd[:-1])    # every complete week ends on weekday w
        assert all((date.fromisoformat(b) - date.fromisoformat(a)).days == 7 for a, b in zip(wd[:-1], wd[1:-1]))
