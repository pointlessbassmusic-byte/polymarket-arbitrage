"""Audit group XA (mandel/experiments/cross_asset.py): regression tests on synthetic data, one block per confirmed finding."""

import math
from bisect import bisect_left
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import cross_asset as xa


def _days(n, cal=True, start=date(2015, 1, 1)):
    d = start; out = []
    while len(out) < n:
        if cal or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _ratio_data(n=1300, seed=1):
    """Calendar series where RV_a/RV_b (~1.5) always exceeds the implied ratio ia/ib (0.8..1.2): every low-ratio signal wins."""
    rng = np.random.default_rng(seed); days = _days(n)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n))); b = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    ia = {d: 50 + 10 * math.sin(i / 50) for i, d in enumerate(days)}; ib = {d: 50.0 for d in days}
    return days, a, b, ia, ib


_ETH = dict(n=30, ppy=365, window=365, lo_q=0.20, hi_q=None, block=2, win_req=None)


# ------------------------------------------------------------------------------- XA-3: min_n (T-266, T-256) --

def test_xa3_ratio_extremes_enforces_min_n_in_signals():
    days, a, b, ia, ib = _ratio_data()
    ok = xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="t", min_n=2)
    n = ok["n"]
    assert 2 <= n < 25 and ok["verdict"] == "supported"                       # criteria pass on this planted effect
    thin = xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="t", min_n=n + 1)
    assert thin["verdict"] == "inconclusive" and f"min_n {n + 1}" in thin["reason"] and thin["mean"] == ok["mean"]
    # the run.py wiring passes only the label: T-266's min_n 25 applies (was: a hard-coded floor of 10, so 21 signals were 'supported')
    eth = xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="ETH/BTC DVOL")
    assert eth["min_n"] == 25 and eth["verdict"] == "inconclusive" and "below the trial's min_n 25" in eth["reason"]
    assert xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="GVZ/VIX")["min_n"] == 40                  # T-247


def _straddle_data(n=3000, seed=3):
    """Calm (0.3%/day) with a wild stretch (5%/day) at positions 90..119 of every 120 days; the index dips to ~20 (below its trailing
    20th percentile) at positions 70..84, just before each wild stretch, and sits at 50 otherwise. Low-index straddles win big."""
    rng = np.random.default_rng(seed); days = _days(n)
    p = np.arange(n) % 120
    r = np.where(p >= 90, rng.normal(0, 0.05, n), rng.normal(0, 0.003, n))
    closes = 100 * np.exp(np.cumsum(r))
    iv = np.where((p >= 70) & (p < 85), 20 + rng.uniform(0, 0.5, n), 50.0)
    return days, closes, {d: float(v) for d, v in zip(days, iv)}, {d: 2.0 for d in days}


def test_xa3_conditional_straddle_uses_non_overlapping_entries_and_min_n():
    days, closes, idx, rates = _straddle_data()
    rep = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "X", min_n=5)
    pos = [days.index(d) for d in rep["entry_days"]]
    assert rep["n_entries"] == len(pos) and all(b - a >= 60 for a, b in zip(pos, pos[1:]))   # was: every overlapping low day counted
    assert rep["n_entries"] < rep["n_low_days"] and rep["n_days"] > rep["n_low_days"]
    assert rep["verdict"] == "supported" and rep["ci"][0] > 0 and rep["conditional_mean_positive"]
    thin = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "X", min_n=rep["n_entries"] + 1)
    assert thin["verdict"] == "inconclusive" and "non-overlapping conditional entries" in thin["reason"]
    dvol = xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "DVOL")             # T-256 wiring: min_n 25
    assert dvol["min_n"] == 25 and dvol["n_entries"] < 25 and dvol["verdict"] == "inconclusive"
    assert xa.conditional_straddle(days, closes, idx, rates, 60, 60, days[0], 252, 0.20, "GVZ")["min_n"] == 20  # T-272


def test_xa3_below_min_n_caps_a_failing_verdict_too():
    days, closes, idx, rates = _straddle_data()
    flat = {d: 45.0 if i % 120 < 20 else 50.0 for i, d in enumerate(days)}       # low days carry no information
    rng = np.random.default_rng(9); calm = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(days))))
    ok = xa.conditional_straddle(days, calm, flat, rates, 60, 60, days[0], 252, 0.20, "X", min_n=1)
    assert ok["verdict"] == "not_supported"
    rep = xa.conditional_straddle(days, calm, flat, rates, 60, 60, days[0], 252, 0.20, "X", min_n=ok["n_entries"] + 1)
    assert rep["verdict"] == "inconclusive" and "criteria: not_supported" in rep["reason"]          # batch4_fomc convention


# ------------------------------------------------------------------------- XA-4: DSR is a probability (T-253) --

def _rich_call_data(n=800, seed=4):
    """Low realised vol (~10%/yr) under a flat index of 60: the covered call's Sharpe is far above holding."""
    rng = np.random.default_rng(seed); days = _days(n, cal=False)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, n)))
    return days, closes, {d: 60.0 for d in days}, {d: 2.0 for d in days}


def test_xa4_deflated_sharpe_criterion_needs_probability_above_half(monkeypatch):
    days, closes, idx, rates = _rich_call_data()
    base = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "IDX")
    assert base["verdict"] == "supported" and base["dsr"] > 0.5
    for p in (0.3, 1e-5):                                    # 1e-5 is what a clearly losing series gets; 'DSR > 0' passed it
        monkeypatch.setattr(xa, "deflated_sharpe_ratio", lambda *a, **k: p)
        rep = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "IDX")
        assert rep["verdict"] == "not_supported" and "failed: deflated Sharpe > 0 (DSR probability > 0.5)" in rep["reason"]
    monkeypatch.setattr(xa, "deflated_sharpe_ratio", lambda *a, **k: 0.51)
    assert xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "IDX")["verdict"] == "supported"


def test_xa3_covered_call_min_n_by_label():
    days, closes, idx, rates = _rich_call_data()
    rep = xa.covered_call_vs_hold(days, closes, idx, rates, 0.25, 30, 21, 12, days[0], "GVZ")                  # T-270: min_n 100 cycles
    assert rep["n_cycles"] < 100 and rep["verdict"] == "inconclusive" and "min_n 100" in rep["reason"]


# ------------------------------------------------------------- XA-5: one-sided 90% bound, 180-day horizon (T-274) --

def test_xa5_one_sided_90_bound_and_calendar_horizon():
    rng = np.random.default_rng(5); n = 2600; days = _days(n, cal=False)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))); b = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    rep = xa.ratio_mean_reversion_signal(days, a, days, b, window=250, start=days[0], min_n=3)
    x = np.array(rep["changes"]); assert len(x) >= 3
    r = np.random.default_rng(0); bs = np.array([r.choice(x, x.size).mean() for _ in range(4000)])
    assert rep["upper90"] == pytest.approx(float(np.quantile(bs, 0.90)))                 # was the 0.95 quantile
    assert rep["upper90"] != pytest.approx(float(np.quantile(bs, 0.95)))
    for (s, e), (s2, _) in zip(rep["episodes"], rep["episodes"][1:] + [(None, None)]):
        target = (date.fromisoformat(s) + timedelta(days=180)).isoformat()
        assert e == days[bisect_left(days, target)]                                       # first trading day >= entry + 180 calendar days
        assert s2 is None or s2 >= e                                                      # non-overlapping
    lr = np.log(a / b); i = {d: k for k, d in enumerate(days)}
    assert x[0] == pytest.approx(lr[i[rep["episodes"][0][1]]] - lr[i[rep["episodes"][0][0]]])
    thin = xa.ratio_mean_reversion_signal(days, a, days, b, window=250, start=days[0], min_n=len(x) + 1)
    assert thin["verdict"] == "inconclusive" and "independent episodes" in thin["reason"]


# -------------------------------------------- XA-6: premium in BTC at inception, Deribit delivery settlement (T-176) --

def _btc_data(n=700, seed=6, drift=0.004, vol=0.01, iv=80.0):
    rng = np.random.default_rng(seed); days = _days(n)
    closes = 20000 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return days, closes, {d: iv for d in days}, {d: 2.0 for d in days}


def test_xa6_premium_converted_at_inception_price():
    days, closes, idx, rates = _btc_data(drift=0.01)                     # S_T/S_0 ~ 1.35 per cycle: conversion date matters
    rep = xa.inverse_covered_call_btc(days, closes, idx, rates, days[0], min_n=5)
    res = xa._cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, days[0])
    K = np.array([s[0] for s in res["strikes"]]); S0 = res["spot"]; c = -res["debit"] / S0
    ST = np.array([closes[days.index(d) + 30] for d in res["day"]])
    want = c - np.maximum(ST - K, 0) / ST - 0.0006
    old = res["pnl"] / ST - 0.0006                                       # premium converted at S_T (the defect)
    assert rep["mean_btc"] == pytest.approx(want.mean()) and abs(old.mean() - want.mean()) > 1e-3
    assert rep["mean_premium_btc"] == pytest.approx(c.mean())


def test_xa6_delivery_settlement_and_unimplemented_criterion():
    days, closes, idx, rates = _btc_data(drift=0.0, vol=0.005)          # rich premium: CI of the mean > 0
    proxy = xa.inverse_covered_call_btc(days, closes, idx, rates, days[0], min_n=5)
    assert proxy["ci"][0] > 0 and proxy["verdict"] == "inconclusive" and "not implemented: settled at Deribit delivery prices" in proxy["reason"]
    rows = [{"value": {"date": (date.fromisoformat(d) + timedelta(days=1)).isoformat(), "delivery_price": float(closes[i] * 1.02)}} for i, d in enumerate(days)]
    dv = xa.delivery_prices(rows)
    rep = xa.inverse_covered_call_btc(days, closes, idx, rates, days[0], delivery=dv, min_n=5)
    res = xa._cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, days[0])
    K = np.array([s[0] for s in res["strikes"]]); c = -res["debit"] / res["spot"]
    ST = np.array([dv.get((date.fromisoformat(d) + timedelta(days=31)).isoformat(), np.nan) for d in res["day"]]); ok = np.isfinite(ST)
    want = c[ok] - np.maximum(ST[ok] - K[ok], 0) / ST[ok] - 0.0006
    assert rep["n_cycles"] == ok.sum() and rep["dropped"] == (~ok).sum()
    assert rep["mean_btc"] == pytest.approx(want.mean()) and rep["verdict"] == "supported" and "Deribit delivery prices on day +31" in rep["reason"]
    assert xa.inverse_covered_call_btc(days, closes, idx, rates, days[0], delivery=dv)["verdict"] == "inconclusive"   # 22 cycles < min_n 60


# ------------------------------------------------- XA-7: T-266 level statistic and the unconditional comparator --

def test_xa7_level_statistic_and_unconditional_mean():
    days, a, b, ia, ib = _ratio_data()
    rep = xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="ETH/BTC DVOL")
    assert rep["statistic"] == "level"
    pos = {d: i for i, d in enumerate(days)}
    lvl = [xa._fwd_rv(a, pos[d], 30, 365) / xa._fwd_rv(b, pos[d], 30, 365) - ia[d] / ib[d] for d in rep["signal_days"]]
    assert rep["mean"] == pytest.approx(np.mean(lvl))                                    # was ln(RV ratio) - ln(DVOL ratio)
    log = xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="ETH/BTC DVOL", statistic="log")
    assert log["mean"] == pytest.approx(np.mean([math.log(xa._fwd_rv(a, pos[d], 30, 365) / xa._fwd_rv(b, pos[d], 30, 365)) - math.log(ia[d] / ib[d])
                                                 for d in log["signal_days"]]))
    unc = [xa._fwd_rv(a, t, 30, 365) / xa._fwd_rv(b, t, 30, 365) - ia[days[t]] / ib[days[t]] for t in range(365, len(days) - 30)]
    assert rep["unconditional_mean"] == pytest.approx(np.mean(unc)) and "unconditional mean over all" in rep["reason"]
    assert xa.ratio_extremes(days, a, days, b, ia, ib, **_ETH, label="GVZ/VIX")["statistic"] == "log"           # T-247 unchanged


# ----------------------------------------------- XA-8: daily-path drawdown and monthly rolls (T-267) --

def test_xa8_daily_path_drawdown_and_monthly_roll():
    n = 30 * 25 + 1; days = _days(n)
    closes = 100 * (1 - 0.5 * np.sin(np.pi * (np.arange(n) % 30) / 30))     # back to 100 at every roll date, 50 mid-month
    idx = {d: 60.0 for d in days}; rates = {d: 2.0 for d in days}
    rep = xa.protective_put_calmar(days, closes, idx, rates, days[0])
    assert rep["n_cycles"] == 25                                             # monthly rolls (was 90-day hold-to-expiry cycles)
    assert rep["mdd_hold"] == pytest.approx(-0.5)                            # cycle-end sampling saw no drawdown at all
    assert rep["mdd_hedged"] > rep["mdd_hold"]                               # the put cushions the intra-month dip
    assert "daily-path MDD" in rep["reason"] and "rolled every 30 days" in rep["reason"]
    short = xa.protective_put_calmar(days[:30 * 10 + 1], closes[:30 * 10 + 1], idx, rates, days[0])
    assert short["n_cycles"] == 10 and short["verdict"] == "inconclusive" and "min_n 20" in short["reason"]
