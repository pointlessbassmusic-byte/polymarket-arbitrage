"""Longshot, horizon-monotonicity and point-in-time harnesses on synthetic archives."""

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from mandel.archive import Archive
from mandel.experiments.run import harness_horizon_monotone, harness_longshot, harness_point_in_time
from mandel.ledger import Ledger


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _synthetic_markets(archive: Archive, n: int, longshot_yes_rate: float, seed: int = 0, calibrated_rest: bool = True):
    """n resolved markets closing at t_close; daily prices for 100 days before close. Longshots (p~0.03) resolve YES
    at longshot_yes_rate; the others at their price (calibrated)."""
    rng = np.random.default_rng(seed)
    t_close = 1_800_000_000
    markets, prices = [], []
    for i in range(n):
        p = 0.03 if i % 2 == 0 else float(rng.uniform(0.2, 0.9))
        o = int(rng.random() < (longshot_yes_rate if p == 0.03 else p))
        markets.append({"value": {"id": f"m{i}", "umaResolutionStatus": "resolved", "outcomePrices": json.dumps([str(float(o)), str(float(1 - o))]),
                                  "outcomes": json.dumps(["Yes", "No"]), "closedTime": _iso(t_close), "volumeNum": 1000, "question": f"q{i}"}})
        for d in range(100, 0, -1):
            # the price drifts toward the outcome as close approaches so skill rises toward resolution
            w = (100 - d) / 100
            pd = (1 - w) * p + w * (0.9 * o + 0.1 * p) if calibrated_rest else p
            prices.append({"value": {"market_id": f"m{i}", "t": t_close - d * 86400, "p": float(min(max(pd, 0.001), 0.999))}})
    archive.store("polymarket-closed-markets", "data", markets, recipe="synthetic")
    archive.store("polymarket-price-history-daily", "data", prices, recipe="synthetic")


@pytest.fixture
def env(tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    return Archive(tmp_path / "archive", ledger)


def test_longshot_bias_detected_and_absent(env):
    _synthetic_markets(env, 600, longshot_yes_rate=0.0, calibrated_rest=False)   # flat prices; cheap YES never pays: classic longshot over-pricing
    stat, n, verdict, reason = harness_longshot(env)
    assert verdict == "supported" and stat["ci"][1] < 0 and n >= 100
    env2 = Archive(env.root.parent / "archive2", env.ledger)
    _synthetic_markets(env2, 600, longshot_yes_rate=0.08, seed=1, calibrated_rest=False)  # cheap YES pays more often than priced
    stat, n, verdict, reason = harness_longshot(env2)
    assert verdict == "not_supported" and stat["mean_error"] > 0


def test_longshot_inconclusive_on_small_sample(env):
    _synthetic_markets(env, 40, longshot_yes_rate=0.0, calibrated_rest=False)
    assert harness_longshot(env)[2] == "inconclusive"


def test_horizon_monotone_on_learning_prices(env):
    _synthetic_markets(env, 300, longshot_yes_rate=0.03)
    stat, n, verdict, reason = harness_horizon_monotone(env)
    assert verdict == "supported" and stat["monotone"] and stat["skills"]["1"] >= stat["skills"]["90"]


def test_point_in_time_check_runs_and_reports_both_lags(env):
    rng = np.random.default_rng(5)
    n = 900
    t0 = 1_600_000_000
    f = (50 + np.cumsum(rng.normal(0, 4, n))) % 100
    env.store("crypto-fear-greed-history", "data", [{"observed_at": _iso(t0 + 86400 * i), "value": {"value": int(v)}} for i, v in enumerate(f)], recipe="synthetic")
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n + 20)))
    env.store("daily-history-BTC-USD", "data", [{"value": {"symbol": "BTC-USD", "t": t0 + 86400 * i, "close": float(c)}} for i, c in enumerate(closes)], recipe="synthetic")
    stat, n_out, verdict, reason = harness_point_in_time(env)
    assert n_out > 800 and stat["naive"]["verdict"] in ("supported", "not_supported") and stat["honest"]["verdict"] in ("supported", "not_supported")
    assert verdict in ("supported", "not_supported") and stat["naive"]["d_fear"] != stat["honest"]["d_fear"]
