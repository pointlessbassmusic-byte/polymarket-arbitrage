"""Batch-2 underlying harnesses on synthetic series: planted effects pass, noise fails."""

from datetime import date, timedelta

import numpy as np

from mandel.experiments import underlying2 as u2


def _bdays(n, start="1950-01-03", weekdays_only=True):
    d = date.fromisoformat(start); out = []
    while len(out) < n:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _series(days, r):
    return days, 100 * np.cumprod(1 + np.concatenate([[0.0], r[: len(days) - 1]]))


def test_sell_in_may_planted_and_null():
    rng = np.random.default_rng(0)
    days = _bdays(252 * 70)
    r = rng.normal(0.0003, 0.008, len(days))
    null = u2.sell_in_may(_series(days, r), _series(days[-252 * 30:], r[-252 * 30:]))
    assert null["verdict"] == "not_supported"
    winter = np.array([int(d[5:7]) in (11, 12, 1, 2, 3, 4) for d in days])
    r2 = r + np.where(winter, 0.0006, -0.0006)                   # about +2.5% a month gap
    rep = u2.sell_in_may(_series(days, r2), _series(days[-252 * 30:], r2[-252 * 30:]))
    assert rep["verdict"] == "supported" and rep["diff_bps_per_month"] > 50


def test_btc_reversal_claim_direction():
    rng = np.random.default_rng(1)
    days = _bdays(3000, "2014-01-01", weekdays_only=False)
    r = rng.normal(0.001, 0.03, len(days))
    rep = u2.btc_reversal(*_series(days, r))
    assert rep["verdict"] == "supported"                           # noise: no tradable reversal, claim holds
    big = r.copy()
    for i in range(61, len(big) - 1):
        if big[i] < np.quantile(big[i - 60:i], 0.10):
            big[i + 1] += 0.03                                     # planted 3% bounce, far above 0.6% cost
    assert u2.btc_reversal(*_series(days, big))["verdict"] == "not_supported"


def test_quarter_end_planted():
    rng = np.random.default_rng(2)
    days = _bdays(252 * 26, "2000-01-03")
    r = rng.normal(0.0002, 0.006, len(days))
    by_month = {}
    for i, d in enumerate(days):
        by_month.setdefault(d[:7], []).append(i)
    ms = sorted(by_month)
    for a, b in zip(ms[:-1], ms[1:]):
        if int(a[5:7]) in (3, 6, 9, 12):
            r[by_month[a][-1] - 1] += 0.006; r[by_month[b][0] - 1] -= 0.006      # r[i-1] is the return ending on day i
    rep = u2.quarter_end_reversal(*_series(days, r))
    assert rep["mean_bps"] > 50 and rep["verdict"] == "supported"
