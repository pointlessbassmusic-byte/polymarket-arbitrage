"""Batch-6 directional/ratio structure harnesses on synthetic series: planted effects pass, nulls do not, and (house rule 10)
an effect that exists on one arbitrary grid phase does not pass while an effect aligned to the claim's expiry calendar does.
No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6_dir as bd
from mandel.options import bs
from mandel.options.payoff import Leg, Position

NB = 1000                               # bootstrap resamples in tests


# ---------------------------------------------------------------------------------------------- synthetic data --

def _days(n, start=date(1993, 1, 4), skip=()):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _gbm(days, vol, drift=0.0, seed=0):
    """Closes whose log variance over any window equals vol^2 x calendar years (matches the pricing clock), drift per year."""
    rng = np.random.default_rng(seed)
    cal = np.array([date.fromisoformat(d).toordinal() for d in days], float)
    dt = np.diff(cal) / 365.0
    lr = (drift - 0.5 * vol ** 2) * dt + vol * np.sqrt(dt) * rng.standard_normal(dt.size)
    return 100 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))


def _pattern(n_cycles, rets, hold=21, s0=100.0):
    """Closes for cycles of ``hold`` sessions whose cycle return k is rets[k % len(rets)] (linear within the cycle)."""
    c = [s0]
    for k in range(n_cycles):
        a = c[-1]; b = a * (1 + rets[k % len(rets)])
        c.extend(list(a + (b - a) * np.arange(1, hold + 1) / hold))
    return np.array(c)


def _bridge(n, anchors, levels, vol, seed=0):
    """Closes whose log price is pinned to ``levels`` at the sessions ``anchors`` (sorted), with Brownian-bridge noise of
    annual vol ``vol`` in between (flat before the first anchor and after the last)."""
    rng = np.random.default_rng(seed); lp = np.empty(n); sd = vol / math.sqrt(252)
    for i0, i1, l0, l1 in zip(anchors[:-1], anchors[1:], levels[:-1], levels[1:]):
        L = i1 - i0; t = np.arange(L + 1) / L
        w = np.concatenate([[0.0], np.cumsum(rng.normal(0.0, sd, L))])
        lp[i0:i1 + 1] = l0 + (l1 - l0) * t + (w - t * w[-1])
    lp[:anchors[0]] = levels[0]; lp[anchors[-1]:] = levels[-1]
    return 100 * np.exp(lp)


def _phase0_path(n, step, vol, hold=21, seed=0):
    """An effect planted on ONE grid phase: the log price moves by exactly ``step`` over every hold that starts at a
    multiple of ``hold`` sessions (grid offset 0), with large bridge noise everywhere in between."""
    anchors = list(range(0, n, hold))
    return _bridge(n, anchors, [step * k for k in range(len(anchors))], vol, seed)


def _mkt(close, bills_pct=0.0, adj=None, days=None):
    days = days or _days(len(close))
    prev = (date.fromisoformat(days[0]) - timedelta(days=3)).isoformat()
    return bd.make_market(days, close, close if adj is None else adj, {prev: bills_pct})


def _grid(close, vol, bills_pct=0.0, hold=bd.MONTH):
    """Rule 10(b): every daily entry pooled, with the hold start offsets."""
    m = _mkt(close, bills_pct)
    iv = np.full(len(close), vol)
    return m, iv, bd.offsets_grid(m, iv, hold, start=m.days[0])


def _dte_grid(close, vol, dte=30):
    """Rule 10(a): SPY monthly expiries entered about ``dte`` calendar days ahead."""
    m = _mkt(close); iv = np.full(len(close), vol)
    ent, exp = bd.dte_cycles(m, iv, bd.monthly_expiries(m, m.days[0]), dte, m.days[0])
    return m, iv, bd.calendar_grid(m, iv, ent, exp, "monthly expiries")


def _offset0(m, iv, G):
    """The pre-rule-10 construction: one fixed grid from the first day (offset 0 only)."""
    a = [int(x) for x in G.P["a"][G.offsets[0]]]
    return bd.calendar_grid(m, iv, a, [x + G.hold for x in a], "offset 0 only")


# --------------------------------------------------------------------------------------------- data conventions --

def test_cont_rate_and_prior_print():
    assert bd.cont_rate(5.0) == pytest.approx(-math.log(1 - 0.05 * 91 / 360) / (91 / 365))
    m = bd.make_market(["2020-01-02", "2020-01-03", "2020-01-06"], [100, 101, 102], [100, 101, 102],
                       {"2020-01-02": 2.0, "2020-01-03": 4.0})
    assert math.isnan(m.rate[0])                                      # no print before the first day
    assert m.rate[1] == pytest.approx(bd.cont_rate(2.0)) and m.rate[2] == pytest.approx(bd.cont_rate(4.0))


def test_bill_accrual_is_day_by_day_at_the_prior_print():
    days = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    m = bd.make_market(days, [100] * 4, [100] * 4, {"2020-01-01": 2.0, "2020-01-03": 6.0})
    r1, r2 = bd.cont_rate(2.0), bd.cont_rate(6.0)
    # (Jan 2, Jan 3] at the rate known on Jan 2 (2%); (Jan 3, Jan 6] at the rate known on Jan 3 (still 2%: the Jan 3 print is
    # dated that day); (Jan 6, Jan 7] at the 6% print
    assert m.accrual(0, 3) == pytest.approx(math.exp(r1 * 1 / 365 + r1 * 3 / 365 + r2 * 1 / 365))
    P = bd.cycle_panel(m, np.full(4, 0.2), hold=3, start=days[0])
    assert P["acc"][0] == pytest.approx(m.accrual(0, 3))


def test_dividends_from_adj_and_forward():
    close = np.array([100.0, 101.0, 100.5, 101.0, 102.0])
    # a 1.01 dividend going ex on day 2: every earlier adjclose is multiplied by 1 - 1.01/101
    f = 1 - 1.01 / 101.0
    adj = close * np.array([f, f, 1, 1, 1])
    div = bd.dividends_from_adj(close, adj)
    assert div[2] == pytest.approx(1.01, rel=1e-9) and div.sum() == pytest.approx(1.01, rel=1e-9)
    days = ["2024-03-13", "2024-03-14", "2024-03-15", "2024-03-18", "2024-03-19"]
    m = bd.make_market(days, close, adj, {"2024-03-01": 5.0})
    r = m.rate[0]
    assert m.pv_div(0, 4, r) == pytest.approx(1.01 * math.exp(-r * 2 / 365))
    assert m.pv_div(2, 4, r) == 0.0                                      # ex-date on the entry day: already in the close
    assert m.pv_div_path(np.array([0, 1, 2, 3]), 4)[2:].sum() == 0.0
    P = bd.cycle_panel(m, np.full(5, 0.2), hold=3, start=days[0])
    assert P["F"][0] == pytest.approx(close[0] - 1.01 * math.exp(-r * 2 / 365)) and P["ST"][0] == close[3]
    assert P["tr"][0] == pytest.approx(adj[3] / adj[0])


def test_iv_series_switches_to_primary_at_its_first_print():
    days = ["2009-09-16", "2009-09-17", "2009-09-18", "2009-09-21", "2009-09-22"]
    vix = {d: 20.0 for d in days}; v3 = {"2009-09-18": 25.0, "2009-09-22": 26.0}
    iv = bd.iv_series(days, v3, vix)
    assert list(iv) == pytest.approx([0.20, 0.20, 0.25, 0.25, 0.26])


def test_clopper_pearson():
    lo, hi = bd.clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** 0.1, abs=1e-6)
    lo, hi = bd.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.187086, abs=1e-5) and hi == pytest.approx(0.812914, abs=1e-5)


def test_settle_and_tree_zone_match_payoff_engine():
    K1, K3, K4 = np.array([100.0]), np.array([105.0]), np.array([107.5])
    legs = [("call", "long", 1, K1), ("call", "short", 3, K3), ("call", "long", 2, K4)]
    assert bd.settle(legs, [104.0])[0] == pytest.approx(4.0) and bd.settle(legs, [120.0])[0] == pytest.approx(0.0)
    D = 1.2
    pos = Position([Leg("call", "long", 1, 100.0, D), Leg("call", "short", 3, 105.0, 0.0), Leg("call", "long", 2, 107.5, 0.0)])
    be = pos.breakevens(100.0)
    assert be[0] == pytest.approx(100.0 + D, abs=1e-3) and be[1] == pytest.approx(107.5 - D / 2, abs=1e-3)


# ------------------------------------------------------------------------------------- rule 10: grids and calendars --

def test_offsets_grid_pools_every_daily_entry_and_partitions_it_by_start_offset():
    close = _gbm(_days(1000), 0.2, seed=1)
    m, iv, G = _grid(close, 0.2)
    assert G.pooled and G.P["n"] == 1000 - 21 and len(G.offsets) == 21 and G.block == 42
    assert G.n_holds == 999 // 21                                      # distinct non-overlapping holds in the window
    allpos = np.sort(np.concatenate(G.offsets))
    assert np.array_equal(allpos, np.arange(G.P["n"]))                 # the offsets partition the pooled entries
    for k, idx in enumerate(G.offsets):
        a = G.P["a"][idx]
        assert a[0] == k and np.all(np.diff(a) == 21)                  # offset k: non-overlapping grid from session k


def test_monthly_expiries_third_friday_and_holiday_shift():
    assert bd.third_friday(2003, 4) == date(2003, 4, 18) and bd.third_friday(2026, 6) == date(2026, 6, 19)
    assert bd.third_friday(1993, 10) == date(1993, 10, 15)             # the 1st is a Friday: the third Friday is the 15th
    days = _days(3000, start=date(2000, 1, 3), skip={"2003-04-18"})    # Good Friday 2003 falls on the third Friday
    m = _mkt(np.full(len(days), 100.0), days=days)
    ex = [m.days[i] for i in bd.monthly_expiries(m, m.days[0])]
    assert "2003-04-17" in ex and "2003-03-21" in ex and "2003-05-16" in ex
    assert all(date.fromisoformat(d).weekday() == 4 for d in ex if d != "2003-04-17")
    assert len(ex) == len(set(d[:7] for d in ex))                      # one expiry per month
    iv = np.full(len(days), 0.2)
    ent, exp = bd.dte_cycles(m, iv, bd.monthly_expiries(m, m.days[0]), 30, m.days[0])
    for a, b in zip(ent, exp):
        gap = m.cal[b] - m.cal[a]
        assert gap >= 30 and m.cal[a + 1] > m.cal[b] - 30               # the last session on or before 30 days ahead
    ent, exp = bd.roll_cycles(m, iv, bd.monthly_expiries(m, m.days[0]))
    assert ent[1:] == exp[:-1]                                         # expiry-to-expiry roll


def test_rule10_digital_effect_on_one_grid_phase_does_not_pass():
    """Regression (T-154/T-540 refutation): realised < RN only on grid offset 0. The old single-phase construction passes;
    the pooled all-offset estimate (the primary statistic under rule 10) does not, and only offset 0 passes."""
    close = _phase0_path(6700, 0.01, 0.50, seed=3)
    m, iv, G = _grid(close, 0.10)
    old = bd.eval_digital(_offset0(m, iv, G), n_boot=NB)
    assert old["verdict"] == "supported" and old["ci"][1] < 0
    rep = bd.eval_digital(G, n_boot=NB)
    assert rep["verdict"] == "not_supported" and rep["ci"][1] > 0
    s = rep["rule10"]["per_offset"]["ci"]
    assert s["offsets"] == 21 and 1 <= s["pass"] <= 2 and f"{s['pass']} of 21 start offsets pass" in rep["reason"]
    assert rep["n"] == G.n_holds and "rule 10(b)" in rep["reason"]


def test_rule10_christmas_tree_effect_on_one_grid_phase_does_not_pass():
    close = _phase0_path(6700, 0.04, 1.0, seed=4)                     # +4% over every offset-0 hold: inside the zone
    m, iv, G = _grid(close, 0.20)
    old = bd.eval_christmas_tree(_offset0(m, iv, G), n_boot=NB)
    assert old["verdict"] == "supported" and old["hit_rate"] == pytest.approx(1.0)
    rep = bd.eval_christmas_tree(G, n_boot=NB)
    assert rep["verdict"] == "not_supported" and rep["rule10"]["per_offset"]["ci"]["pass"] <= 2


def test_rule10_zebra_calendar_aligned_effect_passes_and_grid_phase_effect_does_not():
    """T-154 ('monthly 30-DTE'): the ZEBRA - delta0 x SPY difference is negative for a moderate decline (S_T between about
    0.94 S and S; it is convex and positive for large moves either way). An effect aligned to the monthly expiry calendar
    (SPY ends exactly 1% lower over every 30-DTE cycle, large noise in between) passes on the calendar even though the
    21-session grid fails; the same effect on the 21-session grid's offset 0 only does not pass on the calendar."""
    n = 6700; days = _days(n)
    m0 = _mkt(np.full(n, 100.0)); iv0 = np.full(n, 0.20)
    ent, exp = bd.dte_cycles(m0, iv0, bd.monthly_expiries(m0, m0.days[0]), 30, m0.days[0])
    lev = {**{e: 0.0 for e in ent}, **{x: -0.01 for x in exp}}
    assert not set(ent) & set(exp)
    anchors = sorted(lev)
    close = _bridge(n, anchors, [lev[a] for a in anchors], 0.80, seed=5)
    m, iv, C = _dte_grid(close, 0.20)
    _, _, G = _grid(close, 0.20)
    rep = bd.eval_zebra(C, n_boot=NB, robust=G)
    assert C.n_holds >= 300 and rep["ci"][1] < 0 and rep["verdict"] == "supported"
    rob = rep["rule10"]["grid_robustness"]
    assert rob["ci"][1] > 0 and "robustness (not the claim's calendar" in rep["reason"]

    close = _phase0_path(n, -0.01, 0.80, seed=6)                       # -1% over every offset-0 hold of the 21-session grid
    m, iv, C = _dte_grid(close, 0.20)
    _, _, G = _grid(close, 0.20)
    assert bd.eval_zebra(_offset0(m, iv, G), n_boot=NB)["verdict"] == "supported"          # the old construction
    rep = bd.eval_zebra(C, n_boot=NB, robust=G)
    assert rep["verdict"] == "not_supported" and "rule 10(a)" in rep["reason"]
    assert rep["rule10"]["grid_robustness"]["per_offset"]["pass"] <= 2


# --------------------------------------------------------------------------------------------- T-113 jade lizard --

def test_jade_lizard_planted_short_premium_edge_supported():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.08, seed=1), 0.25)
    rep = bd.eval_jade_lizard(G, n_boot=NB)
    assert rep["n"] >= 250 and rep["n_skipped"] == 0 and rep["ci"][0] > 0
    assert rep["n"] == G.n_holds                                       # nothing skipped: n = distinct holds
    assert rep["rule10"]["per_offset"]["both"]["pass"] == 21
    assert rep["verdict"] == "supported" and "MODEL-PRICED" in rep["reason"] and " — " in rep["reason"]
    assert "median credit over entered cycles" in rep["reason"] and "chain mids at 60 days" in rep["reason"]


def test_jade_lizard_null_not_supported_and_skips_low_credit():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.20, seed=2), 0.20)
    rep = bd.eval_jade_lizard(G, n_boot=NB)
    assert rep["verdict"] != "supported"
    m, iv, G = _grid(_gbm(days, 0.05, seed=2), 0.05)             # at 5% IV the credit is below 1% of S: every month skipped
    res = bd.jade_lizard(G.P)
    assert res["n_skipped"] == res["n_total"] and res["x"].size == 0
    rep = bd.eval_jade_lizard(G, n_boot=NB)
    assert rep["verdict"] == "inconclusive" and rep["n"] == 0


def test_jade_lizard_n_counts_entered_months_in_claim_units():
    days = _days(6600); close = _gbm(days, 0.10, seed=21)
    m = _mkt(close); iv = np.where(np.arange(len(days)) % 42 < 21, 0.25, 0.05)       # alternate high/low IV months
    G = bd.offsets_grid(m, iv, bd.MONTH, start=m.days[0])
    rep = bd.eval_jade_lizard(G, n_boot=NB)
    frac = 1 - rep["n_skipped"] / rep["n_total_entries"]
    assert 0.3 < frac < 0.7 and rep["n"] == round(G.n_holds * frac)


# -------------------------------------------------------------------------------------------- T-133 1x2 ratio --

def test_ratio_zero_cost_strike():
    K2 = bd.zero_cost_k2(100.0, 100.0, 30 / 365, 0.0, 0.2)
    assert 2 * float(bs.price(100.0, K2, 30 / 365, 0.0, 0.2, "call")) == pytest.approx(float(bs.price(100.0, 100.0, 30 / 365, 0.0, 0.2, "call")), rel=1e-8)
    assert 1.02 < K2 / 100 < 1.04
    K2v = bd.zero_cost_k2(np.array([100.0, 100.0]), np.array([100.0, 100.0]), 30 / 365, 0.0, np.array([0.2, 0.4]))
    assert K2v[0] == pytest.approx(K2) and K2v[1] > K2v[0]


def test_ratio_1x2_planted_mean_and_tail_supported():
    rets = [0.025] * 22 + [-0.05] + [0.20] * 2              # gains of +2.5% (below K2), 8% of months far above 2 K2 - K1
    close = _pattern(325, rets)
    m, iv, G = _grid(close, 0.20)
    rep = bd.eval_ratio_1x2(G, n_boot=NB)
    assert rep["tail"]["ci"][0] > 0.03 and rep["ci"][0] > 0 and rep["verdict"] == "supported"
    assert rep["rule10"]["per_offset"]["both"]["pass"] >= 10              # the pattern is cut at offset 0, so some offsets miss it


def test_ratio_1x2_null_not_supported():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.20, seed=3), 0.20)
    assert bd.eval_ratio_1x2(G, n_boot=NB)["verdict"] == "not_supported"


# ------------------------------------------------------------------------------------- T-135 Christmas tree --

def test_christmas_tree_planted_zone_supported():
    close = _pattern(320, [0.04, 0.04, 0.04, 0.04, -0.05])
    m, iv, G = _grid(close, 0.20)
    rep = bd.eval_christmas_tree(G, n_boot=NB)
    assert rep["hit_rate"] > 0.55 and rep["rn_mean"] < 0.45
    assert rep["verdict"] == "supported" and "mechanism (report only)" in rep["reason"]


def test_christmas_tree_null_not_supported():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.20, seed=4), 0.20)
    rep = bd.eval_christmas_tree(G, n_boot=NB)
    assert abs(rep["diff"]) < 0.05 and rep["verdict"] != "supported"


# ---------------------------------------------------------------------------------------- T-136 stock repair --

def test_drawdown_episodes_trigger_and_rearm():
    c = np.array([10, 11, 12, 12, 10.7, 10.5, 10.4, 10.3, 10.2, 12, 12, 12, 12, 12, 12], float)
    eps = bd.drawdown_episodes(c, trigger=0.10, look=5, rearm=3, hold=2, new_crossing=False)
    assert [e[0] for e in eps] == [4, 7] and eps[0][1] == 12.0       # level trigger: first day <= -10%, re-fires 3 sessions later
    eps2 = bd.drawdown_episodes(c, trigger=0.10, look=5, rearm=3, hold=2)
    assert [e[0] for e in eps2] == [4]                                # default (primary): no recovery above -10% in between
    assert bd.drawdown_refires(c, eps, look=5) == (1, 1, 1)           # the level trigger's 2nd episode is a re-fire in 1 spell
    assert bd.drawdown_refires(c, eps2, look=5) == (0, 0, 1)


def _long_spell_path(n_spells=20, seed=1):
    """Each drawdown drops to -20% and stays below -10% for three 63-session quarters, rising +3.5% per quarter, then rallies
    to a new high: one drawdown per spell, but the 63-session level trigger re-fires inside it."""
    rng = np.random.default_rng(seed)
    c = list(100 * np.exp(np.cumsum(np.full(260, 0.0004))))
    for _ in range(n_spells):
        hi = c[-1] * 1.15
        c.extend(list(np.linspace(c[-1], hi, 31)[1:]))
        c.append(0.80 * hi)                                          # one-session drop to -20%
        for _q in range(3):
            base = c[-1]
            c.extend(list(base * (1 + 0.035 * np.arange(1, 64) / 63 + rng.normal(0, 0.001, 63))))
        c.extend([c[-1]] * 5)
    return np.array(c)


def test_stock_repair_counts_first_crossings_not_refires():
    """Regression (T-136): the episode count behind min_n is the number of drawdowns (first crossing of -10%), not the
    63-session level-trigger re-fires inside a drawdown already under way."""
    close = _long_spell_path()
    m = _mkt(close); iv = np.full(close.size, 0.20)
    level = bd.drawdown_episodes(close, new_crossing=False)
    assert len(level) >= 30 and bd.drawdown_refires(close, level)[0] >= 20      # the looser reading crosses min_n
    rep = bd.eval_stock_repair(m, iv, n_boot=NB)
    assert rep["n"] == 20 and rep["ci"][0] > 0                         # one episode per drawdown; planted edge
    assert rep["verdict"] == "inconclusive" and "10 short of min_n 30" in rep["reason"]
    alt = rep["rearm_level_trigger_variant"]
    assert alt["n"] == len(level) and alt["refires"] == alt["n"] - 20 and alt["spells_with_refires"] == 20
    assert alt["verdict"] == "supported"                              # reported only: the re-fires would have decided it
    assert rep["rule10"]["kind"] == "not applicable" and "rule 10(c)" in rep["reason"]


def _repair_path(n_eps=36, seed=0):
    rng = np.random.default_rng(seed)
    c = list(100 * np.exp(np.cumsum(np.full(260, 0.0004))))         # warm-up: a full 252-day window
    for _ in range(n_eps):
        hi = c[-1] * 1.15
        c.extend(list(np.linspace(c[-1], hi, 31)[1:]))               # rally to a new high
        c.extend(list(np.linspace(hi, 0.885 * hi, 9)[1:]))           # drop through -10%
        base = c[-1]
        c.extend(list(base * (1 + 0.04 * np.arange(1, 64) / 63 + rng.normal(0, 0.001, 63))))   # +4% over the 63 sessions
        c.extend([c[-1]] * 5)
    return np.array(c)


def test_stock_repair_planted_supported():
    close = _repair_path()
    m = _mkt(close); iv = np.full(close.size, 0.20)
    rep = bd.eval_stock_repair(m, iv, n_boot=NB)
    assert rep["n"] >= 30 and rep["ci"][0] > 0 and rep["verdict"] == "supported"


def test_stock_repair_null_and_small_sample():
    days = _days(8000)
    close = _gbm(days, 0.30, seed=5)
    m = _mkt(close); iv = np.full(close.size, 0.30)
    rep = bd.eval_stock_repair(m, iv, n_boot=NB)
    assert rep["verdict"] != "supported"
    close = _repair_path(n_eps=10)                                    # planted edge but below min_n: never supported
    m = _mkt(close); iv = np.full(close.size, 0.20)
    rep = bd.eval_stock_repair(m, iv, n_boot=NB)
    assert rep["n"] < 30 and rep["verdict"] == "inconclusive"


# ------------------------------------------------------------------------------- T-138 SKEW-timed risk reversal --

def _skew_setup(planted, seed=6, n_cycles=330):
    rng = np.random.default_rng(seed)
    levels = np.array([150.0, 140.0, 130.0, 120.0, 110.0])
    lab = rng.integers(0, 5, n_cycles)
    if planted:
        rets = np.where(lab == 0, 0.08, np.where(lab == 4, -0.08, 0.0)) + rng.normal(0.0, 0.03, n_cycles)
    else:
        rets = rng.normal(0.0, 0.04, n_cycles)
    close = [100.0]
    for r in rets:
        a = close[-1]; b = a * (1 + r); close.extend(list(a + (b - a) * np.arange(1, 22) / 21))
    close = np.array(close)
    m, iv, G = _grid(close, 0.18)
    skew = {}
    for k in range(n_cycles):
        for i in range(21 * k, 21 * k + 21):
            skew[m.days[i]] = levels[lab[k]] + rng.normal(0, 0.5)
    return G, skew


def test_group_diff_ci_matches_difference():
    rng = np.random.default_rng(0); x = rng.normal(0, 1, 400); g1 = np.arange(400) % 5 == 0; g2 = np.arange(400) % 5 == 1
    x[g1] += 1.0
    d, lo, hi = bd.ci_t_group_diff(x, g1, g2, 6, 500)
    assert d == pytest.approx(x[g1].mean() - x[g2].mean()) and lo > 0 and hi > lo


def test_risk_reversal_skew_planted_supported():
    G, skew = _skew_setup(True)
    rep = bd.eval_risk_reversal(G, skew, n_boot=NB)
    assert rep["groups"]["full"]["ci"][0] > 0 and rep["groups"]["expanding"]["ci"][0] > 0
    assert rep["verdict"] == "supported" and rep["n"] == G.n_holds


def test_risk_reversal_skew_null_not_supported():
    G, skew = _skew_setup(False, seed=7)
    assert bd.eval_risk_reversal(G, skew, n_boot=NB)["verdict"] != "supported"


# -------------------------------------------------------------------------------------- T-139 / T-140 funded calls --

def test_funded_call_path_identity():
    days = _days(120); close = _gbm(days, 0.2, seed=8); m = _mkt(close, bills_pct=4.0); iv = np.full(close.size, 0.2)
    p = bd.funded_call_path(m, iv, [0, 21, 42], 21, 0.9)
    S0, K = close[0], 0.9 * close[0]
    C0 = float(bs.price(S0, K, (m.cal[21] - m.cal[0]) / 365, m.rate[0], 0.2, "call"))
    bills = (S0 - C0) * math.exp(m.rate[0] * (m.cal[21] - m.cal[0]) / 365)
    assert p["R"][0] == pytest.approx((max(close[21] - K, 0) + bills) / S0 - 1, rel=1e-9)
    assert np.allclose(np.cumprod(1 + p["ret"]), p["V"][1:] / p["V"][0]) and p["idx"].size == 64
    P = bd.cycle_panel(m, iv, 21, entries=[0, 21, 42])                 # the vectorised hold-to-expiry returns match
    assert np.allclose(bd.funded_call_cycles(P, 0.9)["R"], p["R"], rtol=1e-10)
    q = bd.funded_call_path(m, iv, [0, 23], None, 0.9, expiries=[23, 50])               # explicit (calendar) expiries
    assert q["idx"][-1] == 50 and q["R"].size == 2


def _crash_path(n, seed=9):
    days = _days(n); close = _gbm(days, 0.12, drift=0.10, seed=seed)
    i = n // 2
    close[i:i + 20] = close[i] * np.linspace(1.0, 0.6, 20)              # a 40% crash over 20 sessions
    close[i + 20:] = close[i + 20:] / close[i + 20] * close[i + 19]
    return close


def test_leaps_planted_supported():
    close = _crash_path(8200)
    m = _mkt(close); iv = np.full(close.size, 0.35)
    rep = bd.eval_leaps(m, iv, n_boot=NB)
    assert rep["n"] >= 30 and rep["ci"][1] < 0 and rep["mdd_ratio_mean"] < 1
    assert rep["verdict"] == "supported"
    r10 = rep["rule10"]
    assert r10["start_offsets"] == 252 and r10["bootstrap_block"] == 504 and rep["n"] == r10["n_holds"] == 8199 // 252


def test_leaps_null_not_supported():
    days = _days(8200); close = _gbm(days, 0.20, seed=10)
    m = _mkt(close); iv = np.full(close.size, 0.20)
    assert bd.eval_leaps(m, iv, n_boot=NB)["verdict"] == "not_supported"


def test_deep_itm_planted_supported():
    days = _days(6600); close = _gbm(days, 0.12, drift=0.06, seed=11)
    m = _mkt(close); iv = np.full(close.size, 0.15)
    rep = bd.eval_deep_itm(m, iv, n_boot=NB)
    assert rep["n"] >= 300 and rep["corr_ci"][0] > 0.98 and rep["shortfall_ci"][1] < 0.01
    assert rep["verdict"] == "supported" and rep["rule10"]["kind"] == "calendar"
    assert "rule 10(a)" in rep["reason"] and rep["rule10"]["grid_robustness"]["corr"]["offsets"] == 21


def test_deep_itm_high_vol_not_supported():
    days = _days(6600); close = _gbm(days, 0.60, seed=12)
    m = _mkt(close); iv = np.full(close.size, 0.60)
    rep = bd.eval_deep_itm(m, iv, n_boot=NB)
    assert rep["corr_ci"][0] < 0.98 and rep["verdict"] == "not_supported"


# ----------------------------------------------------------------------------------------------- T-154 ZEBRA --

def test_zebra_planted_supported():
    days = _days(6600)
    m, iv, C = _dte_grid(_gbm(days, 0.10, seed=13), 0.30)
    res = bd.zebra(C.P)
    assert np.allclose(np.median(res["delta0"]), 2 * 0.70 - np.median(np.asarray(bs.greeks(C.P["F"], C.P["S"], C.P["T"], C.P["r"], C.P["sig"], "call")["delta"])), atol=1e-6)
    rep = bd.eval_zebra(C, n_boot=NB)
    assert rep["ci"][1] < 0 and rep["verdict"] == "supported" and rep["n"] >= 300


def test_zebra_null_not_supported():
    days = _days(6600)
    m, iv, C = _dte_grid(_gbm(days, 0.20, seed=14), 0.20)
    assert bd.eval_zebra(C, n_boot=NB)["verdict"] != "supported"


# --------------------------------------------------------------------------------------------- T-516 digital --

def test_digital_planted_supported():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.10, seed=15), 0.25)
    rep = bd.eval_digital(G, n_boot=NB)
    assert rep["realised"] < rep["rn_mean"] and rep["ci"][1] < 0 and rep["verdict"] == "supported"
    assert rep["breakeven_iv_scale"] is not None and rep["breakeven_iv_scale"] < 0.81
    assert all(o["ci"][1] < 0 for o in rep["iv_scale_sensitivity"].values())


def test_digital_null_not_supported():
    days = _days(6600)
    m, iv, G = _grid(_gbm(days, 0.20, seed=16), 0.20)
    rep = bd.eval_digital(G, n_boot=NB)
    assert abs(rep["diff"]) < 0.05 and rep["verdict"] != "supported"


def test_expanding_climatology_is_point_in_time():
    P = {"a": np.array([0, 1, 2, 3, 4, 5]), "b": np.array([2, 3, 4, 5, 6, 7])}
    y = np.array([1.0, 0.0, 1.0, 1.0, 0.0, 0.0])
    c = bd.expanding_climatology(P, y, 1)
    # entry 2 sees only cycle 0 (settled at 2); entry 3 sees cycles 0-1; entry 5 sees cycles 0-3; entries 0-1 see none
    assert np.isnan(c[0]) and np.isnan(c[1]) and c[2] == 1.0 and c[3] == 0.5 and c[5] == pytest.approx(0.75)
    assert np.isnan(bd.expanding_climatology(P, y, 3)[3])


# ------------------------------------------------------------------------------------------ harness plumbing --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _fake_archive(n=6700, vol=0.10, iv=25.0, skip_last=True):
    days = _days(n); close = _gbm(days, vol, seed=17)
    spy = []
    for d, c in zip(days, close):
        t = datetime.fromisoformat(d + "T14:30:00+00:00").timestamp()
        spy.append({"available_at": d + "T21:00:00+00:00", "value": {"symbol": "SPY", "t": t, "close": float(c), "adjclose": float(c)}})
    if skip_last:                                                       # a bar not yet available at capture is dropped
        spy[-1]["available_at"] = "2031-01-01T00:00:00+00:00"
    vix = [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": iv}} for d in days]
    bills = [{"available_at": "1989-12-29T20:00:00+00:00", "value": {"day": "1989-12-29", "value": 0.0}}]
    return FakeArchive({"daily-history-SPY": spy, "cboe-VIX-history": vix, "fred-DTB3": bills,
                        "cboe-VIX3M-history": vix, "cboe-SKEW-history": [{"available_at": r["available_at"], "value": {"day": r["value"]["day"], "close": 120.0 + (i % 50)}} for i, r in enumerate(vix)]}), days


def test_harnesses_run_on_fake_archive_and_are_json_safe():
    fa, days = _fake_archive()
    assert set(bd.THEORY_MAP.values()) == set(bd.HARNESSES) and len(bd.THEORY_MAP) == 9
    assert all(h.startswith("b6_dir_") for h in bd.HARNESSES)
    for tid, h in bd.THEORY_MAP.items():
        stat, n, verdict, reason = bd.HARNESSES[h](fa)
        json.dumps(stat, allow_nan=False)
        assert verdict in ("supported", "not_supported", "inconclusive") and isinstance(n, int)
        assert "MODEL-PRICED" in reason and " — " in reason
        assert "rule 10" in reason and "rule10" in stat
    stat, n, verdict, reason = bd.b6_dir_digital_put(fa)
    assert verdict == "supported"                                       # planted: realised 10% vs IV 25%
    assert bd._prices(fa, "SPY")[0][-1] == days[-2]                     # unavailable last bar dropped
    stat, n, verdict, reason = bd.b6_dir_zebra(fa)
    assert stat["rule10"]["kind"] == "calendar" and "monthly expiries" in reason


def test_missing_bundles_inconclusive():
    fa, _ = _fake_archive(n=300)
    del fa.bundles["cboe-SKEW-history"]
    stat, n, verdict, reason = bd.b6_dir_risk_reversal_skew(fa)
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"] == ["cboe-SKEW-history"]
    del fa.bundles["fred-DTB3"]
    for h in bd.HARNESSES.values():
        stat, n, verdict, reason = h(fa)
        assert verdict == "inconclusive" and "fred-DTB3" in stat["missing_bundles"]
