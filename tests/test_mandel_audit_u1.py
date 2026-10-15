"""Regression tests for the audit findings applied to mandel/experiments/underlying.py (group u1), on synthetic data.

U-1 (T-61): a half with < 15 signals is not testable, so "both halves > 0" is unimplemented and caps the verdict.
U-2 (T-58): the per-asset test is the best variant's Sharpe vs buy-and-hold (not the mean return), and the DSR deflates
            against the zero-skill best of variants x assets trials.
U-3 (T-58/59/60): daily closes are dividend-adjusted (adjclose) and point in time (available_at <= capture).
"""

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np

from mandel.experiments import underlying2 as u2
from mandel.experiments.underlying import (_rule_matrix, _series, _sharpe_diff_test, ratio_reversion, rule_search,
                                           trend_rules_multi, weekday_effect)
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio

RULES = [("ma", 50), ("ma", 100), ("ma", 200), ("tsmom", 63), ("tsmom", 126), ("tsmom", 252)]


def _days(n, start="2005-01-03"):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------------- U-1 (T-61) --

def _trend_then(tail, trend_days=2400):
    """GLD/SLV-style pair whose log ratio is a smooth trend (|z| = sqrt(3) < 2: no signals) and then ``tail``."""
    trend = 0.0001 * np.arange(trend_days)
    lr = np.concatenate([trend, trend[-1] + tail])
    days = _days(len(lr)); b = 50 * np.ones(len(lr))
    return days, b * np.exp(lr), days, b


def test_u1_ratio_reversion_untestable_half_caps_at_inconclusive():
    rng = np.random.default_rng(0)
    dev = np.zeros(1800)
    for i in range(1, 1800):
        dev[i] = 0.95 * dev[i - 1] + rng.normal(0, 0.01)                 # mean-reverting only in the second half
    rep = ratio_reversion(*_trend_then(dev), n_boot=200)
    # every other T-61 criterion passes, which is what the old code turned into "supported"
    assert math.isnan(rep["halves"][0]) and rep["halves"][1] > 0
    assert rep["p_value"] < 0.05 and rep["mean_reversion_log"] > 0 and rep["n_signals"] >= 30
    assert rep["halves_testable"] is False
    assert rep["verdict"] == "inconclusive" and "a half has < 15 signals" in rep["reason"]


def test_u1_ratio_reversion_untestable_half_does_not_mask_a_failing_criterion():
    rng = np.random.default_rng(0)
    rep = ratio_reversion(*_trend_then(np.cumsum(rng.normal(0, 0.01, 1800))), n_boot=200)   # random walk: no reversion
    assert math.isnan(rep["halves"][0]) and rep["p_value"] >= 0.05
    assert rep["verdict"] == "not_supported" and "block-shift p < 0.05" in rep["reason"]


def test_u1_ratio_reversion_both_halves_testable_still_supported():
    rng = np.random.default_rng(3)
    spread = np.zeros(4000)
    for i in range(1, 4000):
        spread[i] = 0.95 * spread[i - 1] + rng.normal(0, 0.01)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 4000))); b = a * np.exp(-spread)
    rep = ratio_reversion(_days(4000), a, _days(4000), b, n_boot=200)
    assert rep["halves_testable"] is True and all(h > 0 for h in rep["halves"])
    assert rep["verdict"] == "supported"


# ------------------------------------------------------------------------- U-2 (T-58) --

def _crash_asset(seed, n=10000, drop=-0.25, cycle=350, vlen=40):
    """Calm uptrend, then a 5-day 25% slide, a volatile flat spell and a one-day jump back to the pre-drop level. A
    long/flat MA rule takes one slide day and misses the jump: lower mean than buy-and-hold, much lower volatility."""
    rng = np.random.default_rng(seed); r = []
    while len(r) < n:
        r += list(rng.normal(0.0008, 0.008, cycle))
        r += [(1 + drop) ** (1 / 5) - 1] * 5
        r += list(rng.normal(0.0, 0.015, vlen))
        r += [1 / ((1 + drop) * np.prod(1 + np.array(r[-vlen:]))) - 1]
    r = np.array(r[:n]); r[0] = 0.0
    return 100 * np.cumprod(1 + r)


def test_u2_p_best_vs_bh_tests_the_sharpe_difference_not_the_mean():
    c = _crash_asset(0)
    rep = rule_search(c, RULES)
    R, bh, names = _rule_matrix(c, RULES, 5.0)
    best = R[:, names.index(rep["best"])]
    assert best.mean() < bh.mean()                                         # long/flat earns less on average ...
    assert block_bootstrap_pvalue(best, bh, n_boot=1000) > 0.5             # ... so the old mean-return p could never pass
    assert rep["best_sharpe"] > rep["buy_and_hold_sharpe"]                 # but its Sharpe is higher, significantly so
    assert rep["sharpe_diff_best_minus_bh"] > 0 and rep["sharpe_diff_lower_5pct"] > 0 and rep["p_best_vs_bh"] < 0.05
    obs, lo, p = _sharpe_diff_test(best, bh, 252)
    assert (obs, lo, p) == (rep["sharpe_diff_best_minus_bh"], rep["sharpe_diff_lower_5pct"], rep["p_best_vs_bh"])


def test_u2_sharpe_diff_test_ignores_mean_level():
    rng = np.random.default_rng(1)
    b = rng.normal(0.0008, 0.02, 5000)
    a = 0.3 * b + 0.0001 + rng.normal(0, 0.001, 5000)                      # lower mean, higher Sharpe
    assert a.mean() < b.mean() and sharpe_ratio(a) > sharpe_ratio(b)
    obs, lo, p = _sharpe_diff_test(a, b, 252)
    assert obs > 0 and lo > 0 and p < 0.05
    assert _sharpe_diff_test(b, a, 252)[2] > 0.95                          # one-sided: the reverse comparison fails


def test_u2_trend_rules_multi_counts_sharpe_wins_deflated_over_the_full_grid():
    series = {f"A{s}": _crash_asset(s) for s in (0, 2, 3, 4, 5)}
    rep = trend_rules_multi(series, RULES)
    assert rep["n_trials_total"] == 30 and all(o["dsr_n_trials"] == 30 for o in rep["per_asset"].values())
    assert rep["assets_where_best_beats_bh_after_deflation"] >= 4 and rep["verdict"] == "supported"


def test_u2_dsr_deflates_against_variants_times_assets():
    rng = np.random.default_rng(11)
    series = {f"A{k}": 100 * np.exp(np.cumsum(rng.normal(mu, 0.01, 3000)))
              for k, mu in enumerate([0.0006, -0.0006, 0.0012, -0.0012, 0.0, 0.0009, -0.0003, 0.0004])}
    rep = trend_rules_multi(series, RULES)
    assert rep["n_trials_total"] == 48
    mats = {s: _rule_matrix(c, RULES, 5.0) for s, c in series.items()}
    all_sr = [sharpe_ratio(R[:, j]) for R, _, _ in mats.values() for j in range(R.shape[1])]
    assert len(all_sr) == 48
    for s, (R, _, names) in mats.items():
        o = rep["per_asset"][s]
        assert o["dsr_n_trials"] == 48
        assert o["dsr_best"] == deflated_sharpe_ratio(R[:, names.index(o["best"])], n_trials=48, trial_sharpes=all_sr)
    solo = rule_search(series["A0"], RULES, n_boot=200)
    assert solo["dsr_n_trials"] == 6 and solo["dsr_best"] > 0.95             # passes against its own 6 variants ...
    assert rep["per_asset"]["A0"]["dsr_best"] < 0.95                          # ... not against the best of 48


# -------------------------------------------------------------------- U-3 (T-58/59/60) --

def _bar(t, close, adj=None, avail_lag=86400, observed=True):
    row = {"value": {"symbol": "SPY", "t": t, "close": close}}
    if adj is not None:
        row["value"]["adjclose"] = adj
    if observed:
        row["observed_at"] = datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
        row["available_at"] = datetime.fromtimestamp(t + avail_lag, tz=timezone.utc).isoformat()
    return row


T0 = 1767274200                                                              # 2026-01-01T13:30:00Z


def test_u3_series_prefers_adjclose_and_falls_back_to_close():
    rows = [_bar(T0, 100.0, 98.0), _bar(T0 + 86400, 101.0, 99.0), _bar(T0 + 2 * 86400, 102.0), _bar(T0 + 3 * 86400, 103.0, 103.0)]
    days, closes = _series(rows, "SPY", cap="2030-01-01T00:00:00+00:00")
    assert len(days) == 4 and list(closes) == [98.0, 99.0, 102.0, 103.0]


def test_u3_series_is_point_in_time():
    rows = [_bar(T0 + i * 86400, 100.0 + i, 100.0 + i) for i in range(5)]
    # explicit capture time: bars available after it are dropped
    cap = rows[2]["available_at"]
    days, _ = _series(rows, "SPY", cap=cap)
    assert len(days) == 3
    # no capture time: the newest observation bounds it, so the still-unavailable last bar is dropped, the rest kept
    days, closes = _series(rows, "SPY")
    assert len(days) == 4 and closes[-1] == 103.0
    # rows without timestamps (legacy/synthetic) are all kept
    bare = [_bar(T0 + i * 86400, 100.0 + i, observed=False) for i in range(5)]
    assert len(_series(bare, "SPY")[0]) == 5


class _Entry:
    def __init__(self, created_at):
        self.created_at = created_at


class _FakeArchive:
    def __init__(self, rows, created_at):
        self.rows, self.entry = rows, _Entry(created_at)

    def get(self, name):
        return self.entry

    def load(self, name):
        return iter(list(self.rows))


def _dividend_bars(n=3000, y=0.003, seed=4):
    """Weekday bars whose total-return path is noise; raw closes drop by y on the third Friday of each month (ex-dividend).
    Yahoo-style: adjclose_t = close_t x prod over later ex-dates of (1 - y), so adjclose == close on the last bar."""
    rng = np.random.default_rng(seed)
    days = _days(n, "2010-01-04")
    adj = 100 * np.cumprod(1 + rng.normal(0.0003, 0.004, n))
    ex = np.array([date.fromisoformat(d).weekday() == 4 and 15 <= int(d[8:]) <= 21 for d in days])
    later = np.concatenate([np.cumsum(ex[::-1])[::-1][1:], [0]])               # ex-dates strictly after each day
    close = adj / (1 - y) ** later
    rows = []
    for d, c, a in zip(days, close, adj):
        t = int(datetime.fromisoformat(d + "T13:30:00+00:00").timestamp())
        rows.append({"observed_at": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                     "available_at": datetime.fromtimestamp(t + 86400, tz=timezone.utc).isoformat(),
                     "value": {"symbol": "SPY", "t": t, "close": float(c), "adjclose": float(a)}})
    return days, close, rows


def test_u3_run_closes_is_adjusted_point_in_time_and_matches_load_series():
    from mandel.experiments import run
    days, close, rows = _dividend_bars(400)
    cap = rows[-1]["observed_at"][:10] + "T18:00:00+00:00"                    # captured during the last bar's session
    fa = _FakeArchive(rows, cap)
    d1, c1 = run._closes(fa, "SPY")
    d2, c2 = u2.load_series(fa, "SPY")
    assert d1 == d2 == days[:-1] and np.allclose(c1, c2)
    assert not np.allclose(c1, close[:-1])                                      # not the raw closes


def test_u3_friday_dividend_drops_do_not_make_a_weekday_effect():
    days, close, rows = _dividend_bars()
    raw = weekday_effect(days, close, n_boot=300)
    assert raw["strongest"] == "Fri" and raw["verdict"] == "supported"        # the price-only artifact the audit found
    d, c = _series(rows, "SPY")
    adj = weekday_effect(d, c, n_boot=300)
    assert adj["verdict"] == "not_supported"
