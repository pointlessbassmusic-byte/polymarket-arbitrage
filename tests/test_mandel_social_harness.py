"""Social harnesses: honest shortfall, null calibration, and power on planted effects (synthetic data)."""

import math

import numpy as np

from mandel.experiments.social import attention_vs_abs_return, fear_greed_forward_returns, spearman


def _price_rows(symbol, closes, t0=1_700_000_000):
    return [{"value": {"symbol": symbol, "t": t0 + 86400 * i, "close": float(c)}} for i, c in enumerate(closes)]


def _day(i, t0=1_700_000_000):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t0 + 86400 * i, tz=timezone.utc).strftime("%Y-%m-%d")


def _derived_rows(mentions_by_ticker):
    # captured on the day itself, before the 16:00 New York close that starts the close(day) -> close(day+1) window
    # (audit OM-4: this helper used to capture at 01:00 UTC the next day, after the decision time, with a placeholder source "x")
    rows = []
    for t, ms in mentions_by_ticker.items():
        for i, m in enumerate(ms):
            rows.append({"available_at": _day(i) + "T15:00:00+00:00", "value": {"source": "reddit", "ticker": t, "day": _day(i), "mentions": m}})
    return rows


def test_spearman_basic():
    assert abs(spearman(np.array([1, 2, 3, 4.0]), np.array([10, 20, 30, 40.0])) - 1.0) < 1e-12
    assert abs(spearman(np.array([1, 2, 3, 4.0]), np.array([4, 3, 2, 1.0])) + 1.0) < 1e-12
    assert spearman(np.array([1, 1, 1.0]), np.array([1, 2, 3.0])) == 0.0


def test_attention_reports_shortfall_on_one_day():
    rows = _derived_rows({"AAA": [5], "BBB": [3]})
    px = _price_rows("AAA", [100, 101, 102]) + _price_rows("BBB", [50, 49, 51])
    rep = attention_vs_abs_return(rows, px, min_days=30)
    assert rep["verdict"] == "inconclusive" and rep["n_days"] == 1 and "1/30" in rep["reason"]


def test_attention_detects_planted_effect_and_is_calibrated_under_null():
    rng = np.random.default_rng(1)
    n_days = 60
    # planted: |return| scales with mentions
    mentions = {t: rng.poisson(20, n_days).astype(float) for t in ("AAA", "BBB", "CCC")}
    px = []
    for t, ms in mentions.items():
        closes = [100.0]
        for i in range(n_days):
            sigma = 0.002 + 0.002 * (ms[i] / 20.0)
            closes.append(closes[-1] * math.exp(rng.normal(0, sigma)))
        px += _price_rows(t, closes)
    rep = attention_vs_abs_return(_derived_rows(mentions), px, min_days=30, n_perm=400)
    assert rep["verdict"] == "supported" and rep["rho"] > 0.15
    # null: mentions independent of returns -> p-values spread out, not always small
    ps = []
    for seed in range(6):
        rng = np.random.default_rng(100 + seed)
        mentions = {t: rng.poisson(20, n_days).astype(float) for t in ("AAA", "BBB", "CCC")}
        px = []
        for t in mentions:
            closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n_days + 1)))
            px += _price_rows(t, closes)
        ps.append(attention_vs_abs_return(_derived_rows(mentions), px, min_days=30, n_perm=200, seed=seed)["p_value"])
    assert max(ps) > 0.2 and sum(p < 0.05 for p in ps) <= 2


def _fng_rows(values, t0=1_700_000_000):
    from datetime import datetime, timezone
    return [{"observed_at": datetime.fromtimestamp(t0 + 86400 * i, tz=timezone.utc).isoformat(), "value": {"value": int(v)}} for i, v in enumerate(values)]


def test_fear_greed_shortfall_and_null():
    rng = np.random.default_rng(2)
    small = fear_greed_forward_returns(_fng_rows(rng.integers(0, 100, 50)), _price_rows("BTC-USD", 100 * np.exp(np.cumsum(rng.normal(0, 0.03, 60)))))
    assert small["verdict"] == "inconclusive"
    n = 1500
    f = (50 + np.cumsum(rng.normal(0, 4, n))) % 100      # autocorrelated index, wraps through both extremes
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n + 10)))
    rep = fear_greed_forward_returns(_fng_rows(f), _price_rows("BTC-USD", closes), n_boot=300)
    assert rep["n"] >= 1400 and rep["verdict"] in ("not_supported", "inconclusive")
    if rep["verdict"] == "not_supported":
        assert rep["p_fear"] > 0.01 or rep["p_greed"] > 0.01


def test_fear_greed_detects_planted_contrarian_effect():
    rng = np.random.default_rng(3)
    n = 1500
    f = (50 + np.cumsum(rng.normal(0, 4, n))) % 100
    rets = rng.normal(0, 0.02, n + 10)
    for i in range(n):
        if f[i] <= 25:
            rets[i + 1:i + 8] += 0.004                                    # fear -> drift up over next 7 days
        elif f[i] >= 75:
            rets[i + 1:i + 8] -= 0.004
    closes = 100 * np.exp(np.cumsum(rets))
    rep = fear_greed_forward_returns(_fng_rows(f), _price_rows("BTC-USD", closes), n_boot=300)
    assert rep["verdict"] == "supported" and rep["d_fear"] > 0 and rep["d_greed"] < 0
