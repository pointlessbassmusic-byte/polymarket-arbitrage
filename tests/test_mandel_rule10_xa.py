"""House rule 10 (no arbitrary grid phase) for mandel/experiments/cross_asset.py.

The option-writing claims name monthly options, so their cycles run on the expiry calendar: the standard monthly expiry (third Friday,
the prior session on a holiday) for GLD (T-270, T-279) and Deribit's last-Friday expiry for BTC (T-253, T-254, T-176), each written at
one expiry and settled at the next. The grid claims with no calendar (T-245, T-514, T-267, and the cycle-stated variance premia T-244,
T-246, T-271, T-512) are judged on the pooled all-phase estimate. In every case an effect planted on one phase of the old first-day
grid passes on that phase and does not pass the harness; an effect on the claim's own calendar does.
"""

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np

from mandel.experiments import cross_asset as xa
from mandel.experiments import run
from mandel.experiments.structures import monthly_cycles, monthly_expiries


def _days(n, cal=True, start=date(2012, 1, 2), holidays=()):
    d, out, skip = start, [], set(holidays)
    while len(out) < n:
        if (cal or d.weekday() < 5) and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _last_friday(y, m):
    last = date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - 4) % 7)


# ------------------------------------------------------------------------------------------------ calendars --

def test_deribit_sessions_are_the_last_closes_before_last_friday_expiries():
    days = _days(800, start=date(2021, 1, 1))
    s = xa._deribit_expiry_sessions(days)
    assert s[0] == "2021-01-28" and "2021-04-29" in s                       # Thursdays before Jan 29 and Apr 30, 2021 (last Fridays)
    for d in s:
        dd = date.fromisoformat(d) + timedelta(days=1)
        assert dd.weekday() == 4 and dd == _last_friday(dd.year, dd.month)
    assert len(s) == len({d[:7] for d in s}) == 26                         # one per month inside the data
    gap = [d for d in days if d != "2021-04-29"]                            # a missing Thursday: the prior available close
    assert "2021-04-28" in xa._deribit_expiry_sessions(gap)
    cy, cal = xa._calendar_cycles(days, "deribit")
    assert cy == list(zip(s[:-1], s[1:])) and "last Friday" in cal
    assert {(date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in cy} <= {28, 35}


def test_monthly_calendar_is_the_standard_expiry_and_bad_calendars_raise():
    days = _days(700, cal=False, start=date(2018, 1, 2), holidays=("2019-04-19",))   # Good Friday 2019 was the April third Friday
    cy, cal = xa._calendar_cycles(days, "monthly")
    assert cy == monthly_cycles(days) and ("2019-03-15", "2019-04-18") in cy and "third Friday" in cal
    assert xa._calendar_cycles(days, [("2018-01-02", "2018-02-01")])[0] == [("2018-01-02", "2018-02-01")]
    try:
        xa._calendar_cycles(days, "grid")
    except ValueError:
        pass
    else:
        raise AssertionError("an unnamed calendar must raise")


# ------------------------------------------------------- variance premia stated on cycles (T-244/T-246/T-271/T-512) --

def _btc_like(n=2400, seed=1):
    days = _days(n); rng = np.random.default_rng(seed)
    return days, 100 * np.exp(np.cumsum(rng.normal(0, 0.16 / math.sqrt(365), n)))


def test_cycle_premium_on_one_phase_does_not_pass_but_daily_claims_are_unchanged():
    days, closes = _btc_like()
    iv = {d: (30.0 if i % 30 == 0 else 12.0) for i, d in enumerate(days)}   # rich implied vol on phase 0 of the 30-day grid only
    rep = xa.gap_test(days, closes, iv, 30, 365, 0.0, "var", 30, label="DVOL^2 vs BTC")          # T-246's wiring
    assert rep["phase_pass"][0] and sum(rep["phase_pass"]) == 1          # the old first-day cycles alone would pass
    assert rep["verdict"] == "not_supported" and rep["ci"][1] < 0 and rep["block"] == 60
    assert rep["n_days"] == 2370 and rep["n"] == 79                     # n in cycles (ceil(2370 / 30)), not days
    assert "1 of 30 phases pass on their own" in rep["reason"] and "pooled over every daily entry" in rep["reason"]
    rich = xa.gap_test(days, closes, {d: 30.0 for d in days}, 30, 365, 0.0, "var", 30, label="DVOL^2 vs BTC")
    assert rich["verdict"] == "supported" and sum(rich["phase_pass"]) == 30
    daily = xa.gap_test(days, closes, iv, 30, 365, 0.0, "var", 30, label="BTC DVOL")              # T-175: a daily statistic
    assert daily["n"] == len(days) - 30 and "phase" not in daily["reason"] and "cycle" not in daily


def test_gap_trial_lookup_separates_t244_from_t271():
    days, closes = _btc_like(n=1500)
    iv = {d: 20.0 for d in days}
    t244 = xa.gap_test(days, closes, iv, 21, 252, 0.0, "var", 21, thirds=True, label="GVZ^2 vs GLD")
    t271 = xa.gap_test(days, closes, iv, 21, 252, 0.0, "var", 21, label="GVZ^2 vs GLD")
    assert (t244["min_n"], t271["min_n"], t244["cycle"], t271["cycle"]) == (180, 150, 21, 21)
    assert t244["n"] < 180 and "min_n 180" in t244["reason"] and t271["verdict"] == "inconclusive"   # 71 cycles: house rule 5


# ------------------------------------------------------------------------------- T-245: multi-asset variance --

def _legs(n_cycles):
    n = 21 * n_cycles + 1; days = _days(n, cal=False)
    def leg(seed, iv):
        rng = np.random.default_rng(seed)
        return days, 100 * np.exp(np.cumsum(rng.normal(0, 0.15 / math.sqrt(252), n))), {d: iv(i) for i, d in enumerate(days)}
    rich_on_phase0 = lambda i: 30.0 if i % 21 == 0 else 11.0               # the diversifying legs are rich only on phase-0 days
    return {"SPX": leg(1, lambda i: 18.0), "GLD": leg(2, rich_on_phase0), "USO": leg(3, rich_on_phase0), "TLT": leg(4, rich_on_phase0)}


def test_multi_asset_diversification_on_one_phase_does_not_pass():
    rep = xa.multi_asset_short_variance(_legs(200))
    assert rep["phase_pass"][0] and sum(rep["phase_pass"]) == 1          # the old harness's grid (phase 0) passes on its own
    assert rep["n_cycles"] == 200 and rep["n_entries"] == 21 * 200 - 20 and rep["block_days"] == 63
    assert rep["verdict"] == "not_supported" and rep["upper"] < 0
    assert "1 of 21 phases pass on their own" in rep["reason"]


# ----------------------------------------------------------------------------------- T-514: z-score slope --

def test_zscore_reversion_on_one_phase_does_not_pass():
    n = 4300; days = _days(n, cal=False, start=date(2008, 1, 2)); rng = np.random.default_rng(0)
    w = np.cumsum(rng.normal(0, 0.01, n))
    lr = w + np.where((np.arange(n) - 252) % 20 == 0, rng.normal(0, 0.05, n), 0.0)    # a one-day spike on phase-0 days, gone 20 days on
    a = {d: float(20 * math.exp(v)) for d, v in zip(days, lr)}; b = {d: 20.0 for d in days}
    rep = xa.zscore_slope(None, a, b, start=days[0])
    assert rep["phase_pass"][0] and sum(rep["phase_pass"]) == 1          # phase 0 (the old samples) shows 'reversion' in both halves
    assert rep["verdict"] == "not_supported" and min(rep["upper"]) > 0 and rep["block_days"] == 40
    assert rep["n"] == 202 and rep["n_entries"] > 4000                   # n in non-overlapping 20-day samples


# ------------------------------------------------------------------------------------ T-267: protective put --

def test_protective_put_hedge_on_one_roll_phase_does_not_pass():
    n = 30 * 40 + 1; days = _days(n, start=date(2015, 1, 1)); j = np.arange(n) % 30
    closes = 100 * np.exp(0.001 * np.arange(n)) * (1 - 0.7 * np.sin(np.pi * j / 30))   # a dip between phase-0 roll days, rising trend
    idx = {d: 60.0 for d in days}; rates = {d: 2.0 for d in days}
    rep = xa.protective_put_calmar(days, closes, idx, rates, days[0])
    assert rep["phase_pass"][0] and sum(rep["phase_pass"]) <= 5          # rolling at the peak: the old harness's phase passes
    assert rep["phase_diffs"][0] > 0.25 and rep["diff"] < 0 and rep["verdict"] == "not_supported"
    assert rep["n_cycles"] == 40 and rep["n_days"] < 40 * 30 and rep["block_days"] == 180
    assert "pooled over all 30 roll phases" in rep["reason"]


# ------------------------------------------------- monthly options on the expiry calendar (T-270/T-279, T-253/T-254) --

def _planted(days, quiet: set, seed: int):
    """Near 100 on the 'quiet' days; on every other day of the block between two quiet days, displaced by a random +-8..15%: a short put
    written and settled on quiet days keeps its premium, one written or settled on displaced days often pays out."""
    rng = np.random.default_rng(seed)
    noise = np.cumsum(rng.normal(0, 0.002, len(days)))
    logp, jump = np.empty(len(days)), 0.0
    for i, d in enumerate(days):
        if d in quiet:
            jump = rng.choice([-1, 1]) * rng.uniform(0.08, 0.15); logp[i] = noise[i]
        else:
            logp[i] = noise[i] + jump
    return 100 * np.exp(logp)


def _flat(days, v):
    return {d: v for d in days}


def test_gld_put_write_effect_on_one_grid_phase_does_not_pass():
    days = _days(2700, cal=False, start=date(2009, 10, 1))
    closes = _planted(days, {d for i, d in enumerate(days) if i % 21 == 0}, seed=3)          # quiet on phase 0 of the 21-session grid
    idx, rates = _flat(days, 16.0), _flat(days, 2.0)
    grid = [(days[i], days[i + 21]) for i in range(0, len(days) - 21, 21)]
    old = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 21, days[0], "GVZ", calendar=grid)
    assert old["verdict"] == "supported" and old["n_cycles"] >= 100       # the old first-day grid saw a premium
    rep = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 21, days[0], "GVZ")         # T-279's wiring: the monthly expiry calendar
    assert rep["calendar"].startswith("standard monthly expiry") and rep["n_cycles"] == len(monthly_cycles(days))
    assert rep["verdict"] == "not_supported" and rep["mean"] < 0


def test_gld_put_write_effect_on_the_monthly_expiry_is_found():
    days = _days(2700, cal=False, start=date(2009, 10, 1))
    closes = _planted(days, set(monthly_expiries(days)), seed=4)           # quiet on every standard monthly expiry
    idx, rates = _flat(days, 16.0), _flat(days, 2.0)
    rep = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 21, days[0], "GVZ")
    assert rep["verdict"] == "supported" and rep["n_cycles"] >= 100 and rep["first_day"] == monthly_expiries(days)[0]
    cc = xa.covered_call_vs_hold(days, closes, idx, rates, 0.30, 30, 21, 12, days[0], "GVZ", (0.20, 0.30, 0.40))      # T-270's wiring
    assert cc["n_cycles"] == rep["n_cycles"] and cc["calendar"] == rep["calendar"]


def test_btc_put_on_the_deribit_calendar_not_the_30_day_grid():
    days = _days(2000, start=date(2020, 1, 1))
    idx, rates = _flat(days, 40.0), _flat(days, 2.0)
    on_grid = _planted(days, {d for i, d in enumerate(days) if i % 30 == 0}, seed=5)
    grid = [(days[i], days[i + 30]) for i in range(0, len(days) - 30, 30)]
    assert xa.short_put_mean(days, on_grid, idx, rates, -0.25, 30, 30, days[0], "DVOL", calendar=grid)["verdict"] == "supported"
    rep = xa.short_put_mean(days, on_grid, idx, rates, -0.25, 30, 30, days[0], "DVOL")       # T-254's wiring: Deribit's last Fridays
    assert rep["calendar"].startswith("Deribit monthly expiry") and rep["verdict"] == "not_supported"
    on_cal = _planted(days, set(xa._deribit_expiry_sessions(days)), seed=6)
    found = xa.short_put_mean(days, on_cal, idx, rates, -0.25, 30, 30, days[0], "DVOL")
    assert found["verdict"] == "supported" and found["n_cycles"] == len(xa._deribit_expiry_sessions(days)) - 1 >= 60
    cc = xa.covered_call_vs_hold(days, on_cal, idx, rates, 0.25, 30, 30, 12, days[0], "DVOL")  # T-253's wiring
    assert cc["n_cycles"] == found["n_cycles"] and cc["calendar"] == found["calendar"]


def test_inverse_call_settles_each_last_friday_at_its_delivery_price():
    days = _days(900, start=date(2021, 3, 1)); rng = np.random.default_rng(7)
    closes = 30000 * np.exp(np.cumsum(rng.normal(0.002, 0.02, len(days))))
    idx, rates = _flat(days, 70.0), _flat(days, 2.0)
    pos = {d: i for i, d in enumerate(days)}
    delivery = {d: float(closes[pos[d]] * 1.05) for d in days if date.fromisoformat(d).weekday() == 4}   # Fridays only
    rep = xa.inverse_covered_call_btc(days, closes, idx, rates, "2021-04-01", delivery=delivery, min_n=5)
    sched = xa._calendar_cycles(days, "deribit")[0]
    res = xa._cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, "2021-04-01", sched)
    settle = [(date.fromisoformat(x) + timedelta(days=1)) for x in res["exit"]]
    assert all(s == _last_friday(s.year, s.month) for s in settle) and res["day"][0] == "2021-04-29"
    ST = np.array([delivery[s.isoformat()] for s in settle]); K = np.array([k[0] for k in res["strikes"]])
    want = -res["debit"] / res["spot"] - np.maximum(ST - K, 0) / ST - 0.0006
    assert rep["n_cycles"] == len(want) and rep["dropped"] == 0 and abs(rep["mean_btc"] - want.mean()) < 1e-12
    assert rep["calendar"].startswith("Deribit monthly expiry") and "Deribit delivery prices at each expiry" in rep["reason"]


def test_calendar_cycle_without_an_index_value_on_entry_is_named_not_silently_dropped():
    # GVZ has no value on 2020-10-16, the October 2020 expiry: T-270/T-279 price 202 of the calendar's 203 cycles and must say so (rule 9)
    days = _days(1200, cal=False, start=date(2015, 1, 2)); rng = np.random.default_rng(9)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    cyc = [c for c in monthly_cycles(days) if c[0] >= "2015-03-01"]
    gap, early, plain = cyc[5][0], monthly_cycles(days)[0][0], days[401]   # a missing expiry, one before start, one mid-cycle day
    assert plain not in monthly_expiries(days)
    idx = {d: 16.0 for d in days if d not in (gap, early, plain)}; rates = _flat(days, 2.0)
    sp = xa.short_put_mean(days, closes, idx, rates, -0.25, 30, 21, "2015-03-01", "GVZ")
    cc = xa.covered_call_vs_hold(days, closes, idx, rates, 0.30, 30, 21, 12, "2015-03-01", "GVZ", (0.20, 0.30, 0.40))
    for rep in (sp, cc):
        assert rep["n_cycles"] == len(cyc) - 1 and rep["dropped_no_index"] == [list(cyc[5])]
        assert f", 1 calendar cycle dropped for a missing index value on entry ({gap}) — " in rep["reason"]
    whole = xa.short_put_mean(days, closes, _flat(days, 16.0), rates, -0.25, 30, 21, "2015-03-01", "GVZ")
    assert whole["n_cycles"] == len(cyc) and whole["dropped_no_index"] == [] and "dropped for a missing index" not in whole["reason"]
    btc = _days(800, start=date(2021, 3, 1)); bc = 30000 * np.exp(np.cumsum(rng.normal(0, 0.02, len(btc))))
    sess = xa._deribit_expiry_sessions(btc)
    dvol = {d: 70.0 for d in btc if d not in (sess[2], sess[4])}
    inv = xa.inverse_covered_call_btc(btc, bc, dvol, _flat(btc, 2.0), "2021-04-01", min_n=5)
    assert inv["dropped_no_index"] == [[sess[2], sess[3]], [sess[4], sess[5]]] and inv["n_cycles"] == len(sess) - 1 - 1 - 2   # one before start
    assert f"2 calendar cycles dropped for a missing index value on entry ({sess[2]}, {sess[4]})" in inv["reason"]
    put = xa.short_put_mean(btc, bc, dvol, _flat(btc, 2.0), -0.25, 30, 30, "2021-04-01", "DVOL")
    assert put["dropped_no_index"] == inv["dropped_no_index"] and put["n_cycles"] == inv["n_cycles"]


# -------------------------------------------------------------------------------------- the run.py wiring --

class _Arch:
    def __init__(self, bundles):
        self._b = bundles

    def get(self, name):
        return None

    def load(self, name):
        return iter(self._b[name])


def _px_rows(days, closes):
    return [{"value": {"t": datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp(), "close": float(c)}} for d, c in zip(days, closes)]


def _ix_rows(days, v):
    return [{"value": {"day": d, "close": float(v)}} for d in days]


def test_run_wrappers_use_the_claims_calendars():
    btc = _days(2000, start=date(2021, 3, 1)); gld = _days(2400, cal=False, start=date(2009, 9, 1))
    rng = np.random.default_rng(8)
    arch = _Arch({"daily-history-BTC-USD": _px_rows(btc, 30000 * np.exp(np.cumsum(rng.normal(0, 0.02, len(btc))))),
                  "deribit-dvol-BTC-history": _ix_rows(btc, 60.0), "fred-DTB3": _ix_rows(sorted(set(btc) | set(gld)), 2.0),
                  "daily-history-GLD": _px_rows(gld, 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(gld))))), "cboe-GVZ-history": _ix_rows(gld, 16.0)})
    stat, n, verdict, reason = run.XA_HARNESSES["btc_short_put"](arch)
    want = [c for c in xa._calendar_cycles(btc, "deribit")[0] if c[0] >= "2021-04-01"]
    assert n == len(want) and stat["first_day"] == want[0][0] == "2021-04-29" and "Deribit monthly expiry" in reason
    stat, n, verdict, reason = run.XA_HARNESSES["gld_put_write"](arch)
    want = [c for c in monthly_cycles(gld) if c[0] >= "2009-10-01"]
    assert n == len(want) and stat["first_day"] == "2009-10-16" and "standard monthly expiry" in reason
