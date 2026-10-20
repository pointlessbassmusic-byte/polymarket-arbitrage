"""Underlying harnesses: rule mechanics, deflation on noise, planted calendar/ratio effects."""

import numpy as np

from mandel.experiments.underlying import ma_rule_returns, ratio_reversion, rule_search, trend_rules_multi, tsmom_returns, turn_of_month, weekday_effect, weekend_effect


def _days(n, start="2005-01-03", weekdays_only=True):
    import datetime as dt
    d = dt.date.fromisoformat(start); out = []
    while len(out) < n:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def test_rule_mechanics_and_costs():
    closes = np.array([100, 101, 102, 103, 102, 101, 100, 99, 98, 99, 100, 101, 102.0])
    r = tsmom_returns(closes, 3, cost_bps=0)
    assert r.shape == (12,) and np.all(r[:3] == 0)                    # warm-up flat
    rc = tsmom_returns(closes, 3, cost_bps=100)
    assert rc.sum() < r.sum()                                            # costs bite on position changes
    m = ma_rule_returns(closes, 5, cost_bps=0)
    assert m.shape == (12,) and np.all(m[:4] == 0)


def test_rule_search_on_noise_is_deflated():
    rng = np.random.default_rng(0)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 4000)))
    rep = rule_search(closes, [("ma", 50), ("ma", 100), ("ma", 200), ("tsmom", 63), ("tsmom", 126), ("tsmom", 252)])
    assert rep["n_variants"] == 6 and rep["dsr_best"] < 0.95 and 0 <= rep["pbo"] <= 1
    multi = trend_rules_multi({"A": closes, "B": 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 4000)))}, [("ma", 100), ("ma", 200)])
    assert multi["verdict"] == "not_supported" and multi["n_trials_total"] == 4


def test_turn_of_month_planted_and_null():
    rng = np.random.default_rng(1)
    n = 5000; days = _days(n)
    r = rng.normal(0.0002, 0.01, n - 1)
    rep0 = turn_of_month(days, 100 * np.exp(np.cumsum(np.concatenate([[0], r]))), n_boot=300)
    assert rep0["verdict"] == "not_supported"
    months = [d[:7] for d in days[1:]]
    first = {}
    for i, m in enumerate(months):
        first.setdefault(m, i)
    for m, i in first.items():
        r[i:i + 3] += 0.004                                              # +40 bps on the first 3 days of each month
    rep1 = turn_of_month(days, 100 * np.exp(np.cumsum(np.concatenate([[0], r]))), n_boot=300)
    assert rep1["verdict"] == "supported" and rep1["difference_bps"] > 10


def test_weekday_weekend_and_ratio():
    rng = np.random.default_rng(2)
    n = 4000; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    wk = weekday_effect(days, closes, n_boot=200)
    assert wk["verdict"] in ("not_supported", "supported") and set(wk["by_weekday"]) <= {"Mon", "Tue", "Wed", "Thu", "Fri"}
    days7 = _days(3000, weekdays_only=False)
    hits = 0
    for seed in range(8):                                                # size check: at most 2 of 8 null series may "support"
        c7 = 100 * np.exp(np.cumsum(np.random.default_rng(50 + seed).normal(0, 0.03, 3000)))
        we = weekend_effect(days7, c7, n_boot=150)
        assert we["n_weekend"] > 700
        hits += we["verdict"] == "supported"
    assert hits <= 2
    # planted mean-reverting ratio: b follows a plus an AR(1) spread
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 4000)))
    spread = np.zeros(4000)
    for i in range(1, 4000):
        spread[i] = 0.97 * spread[i - 1] + rng.normal(0, 0.01)
    b = a * np.exp(-spread)
    rep = ratio_reversion(_days(4000), a, _days(4000), b, lookback=250, z_entry=1.5, n_boot=200)
    assert rep["verdict"] == "supported" and rep["mean_reversion_log"] > 0


def test_u2_verdict_treats_numpy_false_as_failure():
    import numpy as np
    from mandel.experiments.underlying2 import _verdict
    assert _verdict([("a", np.bool_(False)), ("b", True)])[0] == "not_supported"
    assert _verdict([("a", np.bool_(True)), ("b", None)])[0] == "inconclusive"
    assert _verdict([("a", np.bool_(True)), ("b", True)])[0] == "supported"
