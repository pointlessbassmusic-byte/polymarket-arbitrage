"""Batch-6 directional/ratio structure harnesses on synthetic series: planted effects pass, nulls do not. No archive, no network."""

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

def _days(n, start=date(1993, 1, 4)):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
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


def _mkt(close, bills_pct=0.0, adj=None):
    days = _days(len(close))
    prev = (date.fromisoformat(days[0]) - timedelta(days=3)).isoformat()
    return bd.make_market(days, close, close if adj is None else adj, {prev: bills_pct})


def _panel(close, vol, bills_pct=0.0):
    m = _mkt(close, bills_pct)
    iv = np.full(len(close), vol)
    return m, iv, bd.cycle_panel(m, iv, bd.MONTH, start=m.days[0])


# --------------------------------------------------------------------------------------------- data conventions --

def test_cont_rate_and_prior_print():
    assert bd.cont_rate(5.0) == pytest.approx(-math.log(1 - 0.05 * 91 / 360) / (91 / 365))
    m = bd.make_market(["2020-01-02", "2020-01-03", "2020-01-06"], [100, 101, 102], [100, 101, 102],
                       {"2020-01-02": 2.0, "2020-01-03": 4.0})
    assert math.isnan(m.rate[0])                                      # no print before the first day
    assert m.rate[1] == pytest.approx(bd.cont_rate(2.0)) and m.rate[2] == pytest.approx(bd.cont_rate(4.0))


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


# --------------------------------------------------------------------------------------------- T-113 jade lizard --

def test_jade_lizard_planted_short_premium_edge_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.08, seed=1), 0.25)
    rep = bd.eval_jade_lizard(P, n_boot=NB)
    assert rep["n"] >= 250 and rep["n_skipped"] == 0 and rep["ci"][0] > 0
    assert rep["verdict"] == "supported" and "MODEL-PRICED" in rep["reason"] and " — " in rep["reason"]


def test_jade_lizard_null_not_supported_and_skips_low_credit():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.20, seed=2), 0.20)
    rep = bd.eval_jade_lizard(P, n_boot=NB)
    assert rep["verdict"] != "supported"
    m, iv, P = _panel(_gbm(days, 0.05, seed=2), 0.05)             # at 5% IV the credit is below 1% of S: every month skipped
    res = bd.jade_lizard(P)
    assert res["n_skipped"] == res["n_total"] and res["x"].size == 0
    assert bd.eval_jade_lizard(P, n_boot=NB)["verdict"] == "inconclusive"


# -------------------------------------------------------------------------------------------- T-133 1x2 ratio --

def test_ratio_zero_cost_strike():
    K2 = bd.zero_cost_k2(100.0, 100.0, 30 / 365, 0.0, 0.2)
    assert 2 * float(bs.price(100.0, K2, 30 / 365, 0.0, 0.2, "call")) == pytest.approx(float(bs.price(100.0, 100.0, 30 / 365, 0.0, 0.2, "call")), rel=1e-8)
    assert 1.02 < K2 / 100 < 1.04


def test_ratio_1x2_planted_mean_and_tail_supported():
    rets = [0.025] * 22 + [-0.05] + [0.20] * 2              # gains of +2.5% (below K2), 8% of months far above 2 K2 - K1
    close = _pattern(325, rets)
    m, iv, P = _panel(close, 0.20)
    rep = bd.eval_ratio_1x2(P, n_boot=NB)
    assert rep["tail"]["freq"] == pytest.approx(0.08, abs=0.005) and rep["tail"]["ci"][0] > 0.03
    assert rep["ci"][0] > 0 and rep["verdict"] == "supported"


def test_ratio_1x2_null_not_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.20, seed=3), 0.20)
    assert bd.eval_ratio_1x2(P, n_boot=NB)["verdict"] == "not_supported"


# ------------------------------------------------------------------------------------- T-135 Christmas tree --

def test_christmas_tree_planted_zone_supported():
    close = _pattern(320, [0.04, 0.04, 0.04, 0.04, -0.05])
    m, iv, P = _panel(close, 0.20)
    rep = bd.eval_christmas_tree(P, n_boot=NB)
    assert rep["hit_rate"] == pytest.approx(0.8, abs=0.01) and rep["rn_mean"] < 0.45
    assert rep["verdict"] == "supported"


def test_christmas_tree_null_not_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.20, seed=4), 0.20)
    rep = bd.eval_christmas_tree(P, n_boot=NB)
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
    m, iv, P = _panel(close, 0.18)
    skew = {}
    for k, a in enumerate(P["a"]):
        for i in range(a, a + 21):
            skew[m.days[i]] = levels[lab[k]] + rng.normal(0, 0.5)
    return P, skew


def test_group_diff_ci_matches_difference():
    rng = np.random.default_rng(0); x = rng.normal(0, 1, 400); g1 = np.arange(400) % 5 == 0; g2 = np.arange(400) % 5 == 1
    x[g1] += 1.0
    d, lo, hi = bd.ci_t_group_diff(x, g1, g2, 6, 500)
    assert d == pytest.approx(x[g1].mean() - x[g2].mean()) and lo > 0 and hi > lo


def test_risk_reversal_skew_planted_supported():
    P, skew = _skew_setup(True)
    rep = bd.eval_risk_reversal(P, skew, n_boot=NB)
    assert rep["groups"]["full"]["ci"][0] > 0 and rep["groups"]["expanding"]["ci"][0] > 0
    assert rep["verdict"] == "supported"


def test_risk_reversal_skew_null_not_supported():
    P, skew = _skew_setup(False, seed=7)
    assert bd.eval_risk_reversal(P, skew, n_boot=NB)["verdict"] != "supported"


# -------------------------------------------------------------------------------------- T-139 / T-140 funded calls --

def test_funded_call_path_identity():
    days = _days(120); close = _gbm(days, 0.2, seed=8); m = _mkt(close, bills_pct=4.0); iv = np.full(close.size, 0.2)
    p = bd.funded_call_path(m, iv, [0, 21, 42], 21, 0.9)
    S0, K = close[0], 0.9 * close[0]
    C0 = float(bs.price(S0, K, (m.cal[21] - m.cal[0]) / 365, m.rate[0], 0.2, "call"))
    bills = (S0 - C0) * math.exp(m.rate[0] * (m.cal[21] - m.cal[0]) / 365)
    assert p["R"][0] == pytest.approx((max(close[21] - K, 0) + bills) / S0 - 1, rel=1e-9)
    assert np.allclose(np.cumprod(1 + p["ret"]), p["V"][1:] / p["V"][0]) and p["idx"].size == 64


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


def test_leaps_null_not_supported():
    days = _days(8200); close = _gbm(days, 0.20, seed=10)
    m = _mkt(close); iv = np.full(close.size, 0.20)
    assert bd.eval_leaps(m, iv, n_boot=NB)["verdict"] == "not_supported"


def test_deep_itm_planted_supported():
    days = _days(6600); close = _gbm(days, 0.12, drift=0.06, seed=11)
    m = _mkt(close); iv = np.full(close.size, 0.15)
    rep = bd.eval_deep_itm(m, iv, n_boot=NB)
    assert rep["n"] >= 300 and rep["corr_ci"][0] > 0.98 and rep["shortfall_ci"][1] < 0.01
    assert rep["verdict"] == "supported"


def test_deep_itm_high_vol_not_supported():
    days = _days(6600); close = _gbm(days, 0.60, seed=12)
    m = _mkt(close); iv = np.full(close.size, 0.60)
    rep = bd.eval_deep_itm(m, iv, n_boot=NB)
    assert rep["corr_ci"][0] < 0.98 and rep["verdict"] == "not_supported"


# ----------------------------------------------------------------------------------------------- T-154 ZEBRA --

def test_zebra_planted_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.10, seed=13), 0.30)
    res = bd.zebra(P)
    assert np.allclose(np.median(res["delta0"]), 2 * 0.70 - np.median(np.asarray(bs.greeks(P["F"], P["S"], P["T"], P["r"], P["sig"], "call")["delta"])), atol=1e-6)
    rep = bd.eval_zebra(P, n_boot=NB)
    assert rep["ci"][1] < 0 and rep["verdict"] == "supported"


def test_zebra_null_not_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.20, seed=14), 0.20)
    assert bd.eval_zebra(P, n_boot=NB)["verdict"] != "supported"


# --------------------------------------------------------------------------------------------- T-516 digital --

def test_digital_planted_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.10, seed=15), 0.25)
    rep = bd.eval_digital(P, n_boot=NB)
    assert rep["realised"] < rep["rn_mean"] and rep["ci"][1] < 0 and rep["verdict"] == "supported"


def test_digital_null_not_supported():
    days = _days(6600)
    m, iv, P = _panel(_gbm(days, 0.20, seed=16), 0.20)
    rep = bd.eval_digital(P, n_boot=NB)
    assert abs(rep["diff"]) < 0.05 and rep["verdict"] != "supported"


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
    stat, n, verdict, reason = bd.b6_dir_digital_put(fa)
    assert verdict == "supported"                                       # planted: realised 10% vs IV 25%
    assert bd._prices(fa, "SPY")[0][-1] == days[-2]                     # unavailable last bar dropped


def test_missing_bundles_inconclusive():
    fa, _ = _fake_archive(n=300)
    del fa.bundles["cboe-SKEW-history"]
    stat, n, verdict, reason = bd.b6_dir_risk_reversal_skew(fa)
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"] == ["cboe-SKEW-history"]
    del fa.bundles["fred-DTB3"]
    for h in bd.HARNESSES.values():
        stat, n, verdict, reason = h(fa)
        assert verdict == "inconclusive" and "fred-DTB3" in stat["missing_bundles"]
