"""Volatility harnesses on synthetic data: VRP detection and null, skew/term-structure nulls, overlay engine sanity."""

import numpy as np

from mandel.experiments.volatility import overlay_backtest, overlay_verdict, skew_tail, term_structure_reversion, variance_risk_premium


def _days(n, start=1_262_304_000):            # 2010-01-01, daily (weekends included: harmless for these tests)
    from datetime import datetime, timezone
    return [datetime.fromtimestamp(start + 86400 * i, tz=timezone.utc).strftime("%Y-%m-%d") for i in range(n)]


def _idx_rows(days, vals):
    return [{"value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _px_rows(days, closes, start=1_262_304_000, symbol="SPY"):
    return [{"value": {"symbol": symbol, "t": start + 86400 * i, "close": float(c)}} for i, c in enumerate(closes)]


def test_vrp_detects_premium_and_respects_null():
    rng = np.random.default_rng(0)
    n = 3000; days = _days(n)
    true_vol = 0.16
    closes = 100 * np.exp(np.cumsum(rng.normal(0, true_vol / np.sqrt(252), n)))
    rich = variance_risk_premium(_idx_rows(days, np.full(n, 22.0)), _px_rows(days, closes))           # implied 22 vs realised 16
    assert rich["verdict"] == "supported" and rich["vrp_vol_points"] > 0.04 and rich["p_value"] < 0.01
    fair = variance_risk_premium(_idx_rows(days, np.full(n, 16.0)), _px_rows(days, closes), seed=1)   # implied = realised
    assert fair["verdict"] == "not_supported" and fair["p_value"] > 0.05
    assert variance_risk_premium(_idx_rows(days[:50], np.full(50, 20.0)), _px_rows(days[:50], closes[:50]))["verdict"] == "inconclusive"


def test_skew_and_term_structure_nulls_do_not_fire_on_noise():
    rng = np.random.default_rng(2)
    n = 2500; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    skew = 120 + np.cumsum(rng.normal(0, 1, n)) * 0.3
    rep = skew_tail(_idx_rows(days, skew), _px_rows(days, closes), n_boot=300)
    assert rep["verdict"] in ("not_supported", "inconclusive") and rep["n"] > 2000
    vix = 20 + np.cumsum(rng.normal(0, 0.5, n)) * 0.2; vix3m = vix + rng.normal(0, 1.0, n)
    ts = term_structure_reversion(_idx_rows(days, np.clip(vix, 9, 80)), _idx_rows(days, np.clip(vix3m, 9, 80)), n_boot=300)
    assert ts["verdict"] in ("not_supported", "supported") and 0.2 < ts["share_backwardation"] < 0.8


def test_term_structure_detects_planted_reversion():
    rng = np.random.default_rng(3)
    n = 3000; days = _days(n)
    vix = np.empty(n); vix[0] = 20
    for i in range(1, n):
        vix[i] = max(9, vix[i - 1] + 0.05 * (20 - vix[i - 1]) + rng.normal(0, 1.2))    # strongly mean-reverting
    vix3m = 0.6 * vix + 0.4 * 20                                                       # anchored to the long-run mean
    rep = term_structure_reversion(_idx_rows(days, vix), _idx_rows(days, vix3m), n_boot=300)
    assert rep["verdict"] == "supported" and rep["difference"] < 0


def test_overlay_engine_relationships():
    rng = np.random.default_rng(4)
    n = 2600; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    vix_rows = _idx_rows(days, np.full(n, 16.0)); px = _px_rows(days, closes); rate = _idx_rows(days, np.full(n, 2.0))
    bh = overlay_backtest(px, vix_rows, rate, "buy_and_hold"); cc = overlay_backtest(px, vix_rows, rate, "covered_call")
    col = overlay_backtest(px, vix_rows, rate, "collar"); ss = overlay_backtest(px, vix_rows, rate, "short_straddle"); ls = overlay_backtest(px, vix_rows, rate, "long_straddle")
    assert bh["n_cycles"] == cc["n_cycles"] > 100 and cc["model_priced"]
    assert cc["returns"].std() < bh["returns"].std()                       # capped upside lowers volatility
    assert col["max_drawdown"] > bh["max_drawdown"]                          # drawdown less negative with a put floor
    assert np.allclose(ss["returns"], -ls["returns"])                        # straddle P&L antisymmetric
    v = overlay_verdict(ss, versus="zero", n_boot=300)
    assert "p_value_mean_excess" in v and "returns" not in v


def test_implied_move_pairs_captures_with_expiries():
    from mandel.experiments.volatility import implied_move_vs_realised
    days = _days(1200)
    px = {"SPY": {d: 100 * (1 + 0.001 * i) for i, d in enumerate(days)}}
    rows = []
    for i in range(1, 1150):
        cap = days[i]; exp = days[i + 30]
        rows.append({"available_at": cap + "T12:00:00+00:00", "value": {"symbol": "SPY", "expiry": exp, "dte": 30, "implied_move_pct": 5.0}})
    # audit OM-2: 60 overlapping daily captures are 2 independent ~30d cycles, not 60 observations (this test used to expect supported)
    short = implied_move_vs_realised(rows[:60], px, min_captures=30)
    assert short["n_resolved_captures"] == 60 and short["n_independent_cycles"] == 2 and short["verdict"] == "inconclusive"
    rep = implied_move_vs_realised(rows, px, min_captures=30)
    assert rep["n_independent_cycles"] >= 30 and rep["verdict"] == "supported" and rep["mean_realised_pct"] < 5
    few = implied_move_vs_realised(rows[:10], px, min_captures=30)
    assert few["verdict"] == "inconclusive" and "1/30 independent" in few["reason"]
    unresolved = implied_move_vs_realised([{"available_at": days[100] + "T12:00:00+00:00", "value": {"symbol": "SPY", "expiry": "2099-01-01", "dte": 30, "implied_move_pct": 5.0}}], px)
    assert unresolved["n_resolved_captures"] == 0
