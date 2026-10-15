"""Harness rule 10 (no arbitrary grid phase) for mandel/experiments/options_market.py, all on synthetic data.

No claim in this module names an entry or expiry calendar for its cycles. The claims tested on non-overlapping h-day cycles (T-148's
sign test, T-231, T-232, T-238, T-243, T-530, T-533, T-534, T-536) are now decided on every start of the h-day grid pooled
(overlapping entries, block bootstrap with blocks of at least 2h), each start's own grid reported; an effect planted on one grid start
must not pass. The spike claims (T-241, T-535) name their entries (the first event, then the first event after each 21-day hold):
those entries do not depend on where the data starts, and the pooled all-event-day frequency is reported beside them.
"""

import datetime as dt
import math
from datetime import date, timedelta

import numpy as np

from mandel.experiments import options_market as om


def _days(n, start="2009-01-02"):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _idx(days, vals):
    return [{"value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _px(days, closes, sym="SPY"):
    return [{"value": {"symbol": sym, "t": dt.datetime.fromisoformat(d + "T20:00:00+00:00").timestamp(), "close": float(c)}}
            for d, c in zip(days, closes)]


def _closes(daily_var, seed=0, alternating=False):
    """Closes from returns with the given annualised variance per day: random normal, or +-sqrt(var/252) alternating (exact RV)."""
    sd = np.sqrt(np.asarray(daily_var, float) / 252)
    z = np.where(np.arange(sd.size) % 2 == 0, 1.0, -1.0) if alternating else np.random.default_rng(seed).normal(0, 1, sd.size)
    return 100 * np.exp(np.concatenate([[0.0], np.cumsum(sd * z)]))


def _phase_var(n_returns, high, low, hold=63, n_high=21):
    """Annualised variance per return: the first n_high returns of every hold-day block are high, the rest low (a pattern locked to the
    grid that starts on the first day)."""
    return np.where(np.arange(n_returns) % hold < n_high, high, low)


# ----------------------------------------------------------------------------------------------------------- helpers --

def test_lockout_is_earliest_first_and_maximal():
    assert om._lockout([0, 1, 2, 5, 21, 22, 40, 43, 64], lambda t: t + 21) == [0, 21, 43, 64]
    assert om._lockout([], lambda t: t + 21) == []


def test_by_start_partitions_every_entry_once():
    rows = om._by_start(np.arange(100), 21, lambda m: {"n": int(m.sum()), "pass": bool(m[0])})
    assert [r["start"] for r in rows] == list(range(21)) and sum(r["n"] for r in rows) == 100
    s, txt = om._starts([dict(r, v=float(r["n"])) for r in rows], "v", "n", ".0f")
    assert s["passing_starts"] == [0] and s["range"] == [4.0, 5.0] and "1 of 21 pass" in txt


def test_pooled_tests_need_four_blocks_of_twice_the_hold():
    x = np.random.default_rng(0).normal(1, 1, 100)
    assert om._pooled_p(x, 26) is None and om._pooled_p(x, 25) < 0.01
    assert om._pooled_freq_ci(np.ones(100, bool), np.ones(100, bool), 26) == (None, None)
    assert om._pooled_share_p(np.ones(100, bool), 0.5, 26) is None


def test_pooled_frequency_ci_covers_the_truth_and_resamples_the_timeline():
    rng = np.random.default_rng(3)
    mask = rng.random(3000) < 0.4; hit = rng.random(3000) < 0.7
    lo, hi = om._pooled_freq_ci(hit, mask, 42)
    assert lo < hit[mask].mean() < hi and lo < 0.7 < hi and hi - lo < 0.1


# ----------------------------------------------------------------- T-530: an effect on one grid start must not pass --

def _t530_world(var, cycles=80, seed=1):
    n = 63 * (cycles + 1) + 1
    days = _days(n)
    return _idx(days, np.full(n, 20.0)), _idx(days, np.full(n, 23.0)), _px(days, _closes(var(n - 1), seed))


def test_t530_effect_on_one_grid_start_does_not_pass():
    """F^2 = 0.059 (VIX 20, VIX3M 23, every day in contango). Realised variance is 0.20 on days 1-21 of each 63-day block from the first
    day and 0.03 on days 22-63, so the grid starting on day 0 sells forward variance at 0.059 against 0.03 every cycle (the old harness's
    entries: a clean 'supported'), while a random 42-day window realises 0.087 on average."""
    vix, v3, spy = _t530_world(lambda m: _phase_var(m, 0.20, 0.03))
    rep = om.conditional_forward_v2(vix, v3, spy)
    assert rep["verdict"] == "not_supported" and rep["mean_var"] < -0.02
    gs = rep["grid_starts"]
    assert gs["starts"] == 63 and 0 in gs["passing_starts"] and gs["passing"] < 63 and gs["range"][1] > 0.02
    assert rep["n"] == 81 and rep["n_entries"] == 63 * 80 + 1         # n in non-overlapping 63-day cycles, not daily entries
    assert "POOLED over all" in rep["reason"] and "126-entry blocks" in rep["reason"] and f"{gs['passing']} of 63 pass" in rep["reason"]


def test_t530_effect_on_every_grid_start_still_passes():
    vix, v3, spy = _t530_world(lambda m: np.full(m, 0.03))
    rep = om.conditional_forward_v2(vix, v3, spy)
    assert rep["verdict"] == "supported" and rep["p"] < 0.025 and rep["grid_starts"]["passing"] == 63


# ---------------------------------------------------------------- T-534 / T-238: frequencies planted on one start --

def test_t534_hit_rate_planted_on_one_grid_start_does_not_pass():
    """VVIX 200 makes F_adj fall below spot when VIX3M/VIX = 1.11, but not when it is 1.20. Days 0, 21, 42, ... carry the 1.20 ratio, so
    only the grid starting on day 0 sees VIX(t+21) < F_adj (frequency 1.0, the old harness's entries); every other start sees 0."""
    n = 21 * 60 + 22; days = _days(n)
    vix = 20 + np.random.default_rng(2).normal(0, 0.05, n)
    ratio = np.where(np.arange(n) % 21 == 0, 1.20, 1.11)
    rep = om.contango_forward_v2(_idx(days, vix), _idx(days, vix * ratio), _idx(days, np.full(n, 200.0)))
    assert rep["verdict"] == "not_supported" and rep["freq_adj"] < 0.1 and rep["ci"][0] < 0.6
    assert rep["grid_starts"]["passing_starts"] == [0]
    assert rep["n"] == len(range(0, n - 21, 21)) and rep["n_entries"] == n - 21


def test_t534_frequency_on_every_start_still_passes():
    n = 21 * 60 + 22; days = _days(n)
    vix = 20 + np.random.default_rng(2).normal(0, 0.05, n)
    rep = om.contango_forward_v2(_idx(days, vix), _idx(days, vix * 1.20), _idx(days, np.full(n, 90.0)))
    assert rep["verdict"] == "supported" and rep["ci"][0] > 0.9 and rep["grid_starts"]["passing"] == 21


def test_t238_hit_rate_planted_on_one_grid_start_is_not_a_pass():
    """VIX grows 20.8% every 21 days. With VIX3M/VIX = 1.11 the forward is 16% above spot, so VIX 21 days later lands above it; on days
    0, 21, 42, ... the ratio is 1.40 (forward 56% above spot) and it lands below. Only the day-0 grid passes the data part."""
    n = 21 * 40 + 22; days = _days(n)
    vix = 10 * np.exp(0.009 * np.arange(n)) * (1 + np.random.default_rng(4).normal(0, 0.001, n))
    ratio = np.where(np.arange(n) % 21 == 0, 1.40, 1.11)
    rep = om.vix_forward_contango(_idx(days, vix), _idx(days, vix * ratio))
    assert rep["verdict"] == "not_supported" and rep["freq_below_forward"] < 0.1
    assert rep["grid_starts"]["passing_starts"] == [0] and "data part passes" not in rep["reason"]


# ----------------------------------------------------------------------------------- T-536 / T-243: VVIX gap --

def _vvix_world(vvix_of_t, n=21 * 60 + 22, seed=5):
    days = _days(n, "2006-03-06")
    vix = 20 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.01, n)))       # ~16 vol points of realised VIX vol
    return _idx(days, [vvix_of_t(t) for t in range(n)]), _idx(days, vix)


def test_t536_gap_planted_on_one_grid_start_does_not_pass():
    vv, vx = _vvix_world(lambda t: 100.0 if t % 21 == 0 else 5.0)
    rep = om.vvix_v2(vv, vx)
    assert rep["verdict"] == "not_supported" and rep["mean_gap"] < 0 and rep["p_mean_above_10"] > 0.5
    assert rep["grid_starts"]["passing_starts"] == [0] and rep["n_months"] == -(-rep["n_entries"] // 21)


def test_t536_gap_on_every_start_passes_and_t243_reports_the_starts():
    vv, vx = _vvix_world(lambda t: 100.0)
    rep = om.vvix_v2(vv, vx)
    assert rep["verdict"] == "supported" and rep["p_mean_above_10"] < 0.005 and rep["grid_starts"]["passing"] == 21
    planted = om.vvix_premium(*_vvix_world(lambda t: 100.0 if t % 21 == 0 else 5.0))
    assert planted["verdict"] == "not_supported" and planted["grid_starts"]["starts"] == 21
    assert planted["grid_starts"]["passing"] <= 1 and "21 grid starts alone" in planted["reason"]


# ------------------------------------------------------------------------------------------ T-148: the sign test --

def test_t148_sign_test_planted_on_one_grid_start_does_not_pass():
    """FV = 0.04 (20 vol). Realised vol is 85% on days 1-21 of each 63-day block and 10% on days 22-63, so every day-0 window (days 21-63)
    realises ~10 vol (gap +10: the old sign test on g[::63] passes 70/70) while almost every other start's window catches the spike."""
    cycles = 70; n = 63 * cycles + 64; days = _days(n)
    closes = _closes(_phase_var(n - 1, 0.85 ** 2, 0.10 ** 2), seed=6)
    rep = om.forward_variance_premium(_idx(days, np.full(n, 20.0)), _idx(days, np.full(n, 20.0)), _px(days, closes))
    st = rep["sign_test_starts"]
    assert 0 in st["passing_starts"] and st["passing"] <= 5 and st["starts"] == 63
    assert rep["p_sign"] > 0.05 and rep["verdict"] == "not_supported"
    assert rep["nonoverlap_n"] == -(-rep["n"] // 63) and "POOLED over all 63 grid starts" in rep["reason"]


# ------------------------------------------------------------------------ T-231: pooled premium and rule 5 on it --

VIX, V3 = 20.0, 22.5
F2 = (3 * (V3 / 100) ** 2 - (VIX / 100) ** 2) / 2


def _alternating(var, length):
    a = math.sqrt(var / 252)
    return [a if i % 2 == 0 else -a for i in range(length)]


def _om2_run(d, fwd):
    """The audit-round-2 builder: each 63-day cycle of the grid that starts on day 0 has exactly the designed premia (realised variance
    set separately on its days 1-21 and 22-63), i.e. the premia are planted on ONE grid start."""
    rets = []
    for dd, f in zip(d, fwd):
        rets += _alternating((VIX / 100) ** 2 + dd - f, 21) + _alternating(F2 - f, 42)
    rets.append(0.0)
    closes = 100 * np.exp(np.concatenate([[0.0], np.cumsum(rets)]))
    days = _days(len(closes), "2007-01-02")
    return om.term_vs_spot_premium(_idx(days, np.full(len(days), VIX)), _idx(days, np.full(len(days), V3)), _px(days, closes))


def _t231_world(vix, f2, var=0.0225):
    """Phase-free world: |returns| constant, so realised variance is exactly ``var`` over any window; entry t has VIX vix[t] and forward
    variance f2[t] (VIX3M^2 = (2 F^2 + VIX^2) / 3), hence premium F^2 - VIX^2 and forward premium F^2 - var, exactly, on every day."""
    vix, f2 = np.asarray(vix, float), np.asarray(f2, float); m = vix.size; n = m + 64
    v3 = np.concatenate([100 * np.sqrt((2 * f2 + (vix / 100) ** 2) / 3), np.full(64, 20.0)])
    days = _days(n, "2007-01-02")
    return om.term_vs_spot_premium(_idx(days, np.concatenate([vix, np.full(64, 20.0)])), _idx(days, v3),
                                   _px(days, _closes(np.full(n - 1, var), alternating=True)))


def _t231(d):
    """VIX 20 and premium exactly d[t] on every daily entry; entries with d > 0.0126 have VIX3M/VIX > 1.10 and forward premium
    0.04 + d - 0.0225 > 0."""
    d = np.asarray(d, float)
    return _t231_world(np.full(d.size, 20.0), 0.04 + d)


def _noise(n, sd, seed):
    z = np.random.default_rng(seed).normal(0, sd, n)
    return z - z.mean()


def test_t231_premium_planted_on_one_grid_start_does_not_decide():
    """The day-0 grid carries a significantly NEGATIVE premium (the old harness: decisive, not_supported); pooled over all 63 starts the
    planted pattern averages out to F^2 - VIX^2 and cannot decide the verdict."""
    rep = _om2_run(-0.01 + _noise(40, 0.005, 3), np.full(40, 0.006))
    assert rep["n_cycles"] == 40 and abs(rep["mean_term_minus_spot_var"] - (F2 - 0.04)) < 0.002
    assert ["forward premium > spot premium, 95% CI excluding 0", False] not in rep["criteria"] and rep["verdict"] == "inconclusive"
    assert rep["grid_starts"]["range"][0] < -0.008 and rep["grid_starts"]["starts"] == 63


def test_t231_builder_sets_the_pooled_premium_exactly():
    d = 0.004 + _noise(40 * 63, 0.003, 1)
    rep = _t231(d)
    assert rep["n_cycles"] == 40 and rep["n_entries"] == 40 * 63 and abs(rep["mean_term_minus_spot_var"] - 0.004) < 1e-9


def test_t231_below_min_n_significantly_negative_pooled_premium_is_decisive():
    rep = _t231(-0.01 + _noise(40 * 63, 0.005, 3))
    assert rep["n_cycles"] < om.T231_MIN_CYCLES and rep["p_value"] > 0.975
    assert rep["verdict"] == "not_supported" and ["forward premium > spot premium, 95% CI excluding 0", False] in rep["criteria"]


def test_t231_below_min_n_non_significant_positive_pooled_premium_is_inconclusive():
    rep = _t231(0.0001 + _noise(40 * 63, 0.005, 2))
    assert rep["mean_term_minus_spot_var"] > 0 and rep["p_value"] > 0.05
    assert rep["verdict"] == "inconclusive"
    crit = dict((c.split(" (")[0], ok) for c, ok in rep["criteria"])
    assert crit["forward premium > spot premium, 95% CI excluding 0"] is None and crit["conditional"] is True


def test_t231_at_min_n_non_significant_fails_and_a_clear_pass_stays_inconclusive():
    weak = _t231(0.0001 + _noise(75 * 63, 0.005, 9))
    assert weak["n_cycles"] == 75 and weak["p_value"] > 0.025 and weak["verdict"] == "not_supported"
    clear = _t231(0.01 + _noise(75 * 63, 0.005, 10))
    assert clear["p_value"] < 0.025 and clear["verdict"] == "inconclusive"     # the strategy clause is not implemented


def test_t231_under_four_blocks_no_test_runs():
    for mean in (0.019, -0.019):
        rep = _t231(mean + _noise(6 * 63, 0.005, 4))
        assert rep["n_cycles"] == 6 and rep["p_value"] is None and rep["verdict"] == "inconclusive" and "p n/a" in rep["reason"]


def test_t231_conditional_half_decisive_only_when_significantly_negative():
    """Every entry is conditional. First half: VIX 20, forward premium +0.0375; second half: VIX 8 and a forward premium of -0.005
    (significant: not_supported) or -0.00005 (not significant below min_n: inconclusive); the main premium stays clearly positive."""
    m = 40 * 63; h = m // 2
    noise = np.concatenate([_noise(h, 0.002, 6), _noise(m - h, 0.002, 7)])
    vix = np.where(np.arange(m) < h, 20.0, 8.0)
    reps = [_t231_world(vix, 0.0225 + np.where(np.arange(m) < h, 0.0375, late) + noise) for late in (-0.005, -0.00005)]
    for rep in reps:
        halves = rep["conditional_forward_premium_halves"]
        assert rep["n_conditional_entries"] == m and rep["p_value"] < 0.025 and halves[1] < 0 < halves[0]
    assert [r["verdict"] for r in reps] == ["not_supported", "inconclusive"]


# ------------------------------------------------------------------- T-232 / T-533: every signal day pooled --

def _vix9d_world(v9_level, n=1500, seed=7):
    days = _days(n, "2011-01-04")
    closes = _closes(np.full(n - 1, 0.04), alternating=True)                      # realised vol exactly 20 over any window
    v9 = v9_level + np.random.default_rng(seed).normal(0, 0.5, n)
    return _idx(days, v9), _px(days, closes)


def test_t232_pools_every_signal_day_and_counts_non_overlapping_cycles():
    v9, spy = _vix9d_world(15.0)
    rep = om.short_horizon_conditional(v9, spy)
    n_r = 1500 - 1
    assert rep["n_entries"] == n_r - 18 and rep["n_signals"] == len(range(10, n_r - 8, 9))
    assert rep["verdict"] == "inconclusive" and "data part passes" in rep["reason"] and rep["grid_starts"]["passing"] == 9


def test_t533_pools_every_signal_day_and_counts_non_overlapping_windows():
    v9, spy = _vix9d_world(15.0)
    rep = om.vix9d_v2(v9, spy)
    assert rep["verdict"] == "supported" and rep["n_entries"] == 1499 - 18 and rep["grid_starts"]["starts"] == 9
    assert rep["n_signals"] < rep["n_entries"] / 6 and "18-entry blocks" in rep["reason"]
    none = om.vix9d_v2(*_vix9d_world(30.0))                                      # VIX9D never below trailing realised
    assert none["verdict"] == "inconclusive" and none["n_signals"] == 0


# ------------------------------------------------------------- T-241 / T-535: event entries named by the claim --

def _spike_series(outcomes, lead=0, block=30):
    """One VIX > 30 backwardation event every ``block`` days after ``lead`` quiet days; VIX 21 days later = the outcome."""
    n = lead + block * len(outcomes) + 25
    vix = np.full(n, 15.0); v3 = np.full(n, 18.0)
    for i, out in enumerate(outcomes):
        t0 = lead + block * i
        vix[t0], v3[t0] = 40.0, 35.0
        vix[t0 + 21], v3[t0 + 21] = out, 80.0
    days = _days(n, "2008-01-02")
    return _idx(days, vix), _idx(days, v3), _idx(days, np.full(n, 90.0))


def test_spike_event_entries_do_not_depend_on_where_the_data_starts():
    outcomes = [20.0] * 19 + [36.0] * 4
    base = None
    for lead in (0, 3, 11, 20):
        vix, v3, vv = _spike_series(outcomes, lead=lead)
        a, b = om.spike_forward_v2(vix, v3, vv), om.vix_spike_forward(vix, v3)
        key = (a["n_events"], a["p_adj"], tuple(a["ci"]), a["verdict"], b["n_events"], b["p_below_forward"], b["verdict"])
        base = base or key
        assert key == base
        assert a["pooled_event_days"]["event_days"] == 23 and "rule 10 does not apply" in a["reason"]
        assert b["pooled_event_days"]["p_below_forward"] == b["p_below_forward"]       # one event day per event here
    assert base[0] == 23 and base[3] == "supported" and base[6] == "not_supported"
