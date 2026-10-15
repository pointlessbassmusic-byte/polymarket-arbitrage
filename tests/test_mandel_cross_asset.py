"""Cross-asset harnesses: planted vol premium, one-sided ratio band, put-write normalised by strike."""

from datetime import date, timedelta

import numpy as np

from mandel.experiments import cross_asset as xa


def _days(n, cal=False):
    d = date(2010, 1, 4); out = []
    while len(out) < n:
        if cal or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def test_gap_test_detects_and_rejects():
    rng = np.random.default_rng(0); n = 2500; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.15 / np.sqrt(252), n)))
    rich = xa.gap_test(days, closes, {d: 20.0 for d in days}, 21, 252, 2.0, "vol", 21, label="x")
    assert rich["verdict"] == "supported" and rich["mean"] > 4
    fair = xa.gap_test(days, closes, {d: 15.0 for d in days}, 21, 252, 2.0, "vol", 21, label="x")
    assert fair["verdict"] == "not_supported"


def test_ratio_extremes_one_sided_band():
    rng = np.random.default_rng(1); n = 1500; days = _days(n, cal=True)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n))); b = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    ia = {d: 80 + 10 * np.sin(i / 50) for i, d in enumerate(days)}; ib = {d: 60.0 for d in days}
    rep = xa.ratio_extremes(days, a, days, b, ia, ib, n=30, ppy=365, window=365, lo_q=0.2, hi_q=None, block=2, win_req=None, label="t")
    assert rep["n"] >= 5 and "win rate >" not in rep["reason"]


def test_put_write_normalised_by_strike():
    rng = np.random.default_rng(2); n = 800; days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    rep = xa.short_put_mean(days, closes, {d: 20.0 for d in days}, {d: 4.0 for d in days}, -0.25, 30, 21, "2010-01-01", "IDX")
    assert rep["n_cycles"] > 30 and "of strike" in rep["reason"]
