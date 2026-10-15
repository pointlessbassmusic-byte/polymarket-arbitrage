"""House rule 10 (no arbitrary grid phase) for the model-priced structure claims (structure_claims.py, structures.py).

The claims that name only a hold (T-100 ... T-126: '30-DTE', 'non-overlapping 21-trading-day cycles') are decided on every
start of the hold-h grid pooled (an entry on every day, block >= 2h days), with the per-start range reported; the claims that
roll a 1-month option monthly (CALENDAR: 'rolled monthly', 'monthly cycles') run on the standard monthly expiry calendar.
"""

import math
from datetime import date, timedelta

import numpy as np
import pytest

import mandel.experiments.structure_claims as sc
from mandel.experiments.structures import Q, metric, monthly_cycles, monthly_expiries, run_structure, third_friday
from mandel.options import bs


def _days(n, start=date(2000, 1, 3), drop=()):
    d = start; out = []
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in drop:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(n, seed, vol=0.20, drift=0.0):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift / 252, vol / math.sqrt(252), n)))


SMILE_ROWS = [{"value": {"quote_date": "2026-10-14", "target_dte": t, "ratio": {"0.90": 1.4, "1.00": 0.85, "1.10": 0.75}}}
              for t in (30, 45)]


def _grid_ctx(vix_of_index, n_cycles=70, hold=21, seed=11):
    """Synthetic SPY with 20% realised vol; VIX on day i is vix_of_index(i), so an effect can live on one grid start."""
    n = hold * n_cycles + hold; days = _days(n)
    return sc.Ctx(days, _closes(n, seed), {d: vix_of_index(i) for i, d in enumerate(days)}, {d: 4.0 for d in days}, SMILE_ROWS)


# ---------------------------------------------------------------- an effect on one grid start must not pass

def test_effect_on_one_grid_start_does_not_pass(monkeypatch):
    monkeypatch.setitem(sc.MIN_N, "T-100", 50)
    c = _grid_ctx(lambda i: 80.0 if i % 21 == 0 else 5.0)        # straddles bought at 80 vol only on start 0
    for s in sc.FLATS:                                            # the old first-day grid: every cycle overpriced, a clean 'pass'
        x = metric(c.run(sc.STRADDLE, ("flat", s), q=0.0), "per_premium")
        assert sc._ci_t(x)[1] < 0
    rep = sc.evaluate("T-100", c)
    assert rep["verdict"] == "not_supported" and rep["grid_starts"] == 21
    failed = rep["reason"].split("failed: ")[1]
    assert all(f"s={s}: upper CI < 0" in failed for s in sc.FLATS) and rep["reason"].count("1 of 21 starts pass") == 3
    m = len(c.aligned("daily").run(sc.STRADDLE, ("flat", 1.0), q=0.0)["pnl"])
    assert rep["n_cycles"] == -(-m // 21) == 70                   # n in the claim's own 21-day cycles, not daily entries
    assert "block 42 days" in rep["ci"] and "all 21 starts of the 21-day grid pooled" in rep["reason"]


def test_effect_on_every_grid_start_still_passes(monkeypatch):
    monkeypatch.setitem(sc.MIN_N, "T-100", 50)
    rep = sc.evaluate("T-100", _grid_ctx(lambda i: 80.0))
    assert rep["verdict"] == "supported" and rep["reason"].count("21 of 21 starts pass") == 3


def test_effect_on_one_start_of_the_31_day_grid_does_not_pass(monkeypatch):
    """Planted in the price path: SPY sits on a quiet base every 31st day (start 0 sees no move, so the bought reverse condor
    always expires worthless) and swings +/-12% in between (every other start sees big moves and collects)."""
    monkeypatch.setitem(sc.MIN_N, "T-110", 30)                   # reverse iron condor bought: upper CI < 0
    rng = np.random.default_rng(5); n = 31 * 46; days = _days(n)
    base = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n // 31 + 1)))
    closes = np.array([base[i // 31] * (1.0 if i % 31 == 0 else math.exp(rng.normal(0, 0.12))) for i in range(n)])
    c = sc.Ctx(days, closes, {d: 20.0 for d in days}, {d: 4.0 for d in days}, SMILE_ROWS)
    ic = [("put", "long", 1, 0.92), ("put", "short", 1, 0.95), ("call", "short", 1, 1.05), ("call", "long", 1, 1.08)]
    assert sc._ci(metric(c.run(sc._flip(ic), ("smile", 1.0), 45, 31), "per_premium"))[1] < 0    # first-day grid would pass
    rep = sc.evaluate("T-110", c)
    assert rep["verdict"] == "not_supported" and rep["grid_starts"] == 31 and "1 of 31 starts pass" in rep["reason"]
    assert "block 62 days" in rep["ci"] and rep["n_cycles"] == 45


def test_pooled_series_holds_every_grid_start_and_the_primary_ci_uses_block_2h(monkeypatch):
    c = _grid_ctx(lambda i: 20.0, n_cycles=30)
    pooled = c.aligned("daily").run([("call", "long", 1, 1.0)], ("flat", 0.9), q=0.0)
    for k in (0, 7, 20):                                          # start k of the pooled series IS the grid started on day k
        g = run_structure(c.days, c.closes, c.vix, c.rates, [("call", "long", 1, 1.0)], 30, 21, ("flat", 0.9), start=c.days[k], q=0.0)
        assert pooled["day"][k::21] == g["day"] and np.array_equal(pooled["pnl"][k::21], g["pnl"])
    calls = []
    orig = sc._ci_t
    monkeypatch.setattr(sc, "_ci_t", lambda x, *a, **k: (calls.append((np.asarray(x).size, a, k)), orig(x, *a, **k))[1])
    sc.evaluate("T-125", c)
    primary = [cl for cl in calls if cl[0] == len(pooled["pnl"])]
    assert len(primary) == 4 and all(cl[1] == (42,) for cl in primary)   # 2 q x 2 s, each pooled with block 2 x 21
    assert len(calls) == 4 * 22                                            # + the 21 per-start CIs of each criterion


def test_grid_start_shift_moves_only_the_reported_range():
    """Dropping the first days shifts every start of a first-day grid; the pooled series just loses its first entries."""
    c = _grid_ctx(lambda i: 20.0, n_cycles=30)
    legs = [("put", "long", 1, 1.0)]
    full = run_structure(c.days, c.closes, c.vix, c.rates, legs, 30, 21, ("flat", 1.0), step=1)
    late = run_structure(c.days, c.closes, c.vix, c.rates, legs, 30, 21, ("flat", 1.0), start=c.days[5], step=1)
    assert late["day"] == full["day"][5:] and np.array_equal(late["pnl"], full["pnl"][5:])


# ---------------------------------------------------------------- the monthly expiry calendar where the claim names one

def test_monthly_expiries_third_friday_or_prior_session():
    days = _days(400, drop={"2000-04-21"})                       # Good Friday 2000 is April's third Friday
    e = monthly_expiries(days)
    assert e[:5] == ["2000-01-21", "2000-02-18", "2000-03-17", "2000-04-20", "2000-05-19"]
    assert all(x == third_friday(int(x[:4]), int(x[5:7])).isoformat() for x in e if x != "2000-04-20")
    cy = monthly_cycles(days)
    assert cy[:2] == [("2000-01-21", "2000-02-18"), ("2000-02-18", "2000-03-17")] and len(cy) == len(e) - 1
    assert third_friday(2026, 6).isoformat() == "2026-06-19" and third_friday(2008, 3).isoformat() == "2008-03-21"


def test_calendar_claims_are_the_monthly_roll():
    assert sc.CALENDAR == {"T-127", "T-129", "T-130", "T-131", "T-132", "T-134", "T-517"}
    assert not sc.CALENDAR & {"T-100", "T-102", "T-104", "T-105", "T-106", "T-107", "T-109", "T-110", "T-114", "T-115", "T-116",
                              "T-124", "T-125", "T-126"}


def _calendar_ctx(n=1300, seed=3):
    days = _days(n, drop={"2000-04-21", "2003-04-18"})
    exp = set(monthly_expiries(days))
    vix = {d: (5.0 if d in exp else 80.0) for d in days}         # cheap only on the standard expiry sessions
    return sc.Ctx(days, _closes(n, seed), vix, {d: 4.0 for d in days}, SMILE_ROWS), sorted(exp)


def test_calendar_claim_enters_at_monthly_expiries_and_prices_actual_days(monkeypatch):
    monkeypatch.setitem(sc.MIN_N, "T-132", 30)
    c, exp = _calendar_ctx()
    legs = [("call", "short", 1, 1.03), ("call", "long", 1, 1.06)]
    rep = sc.evaluate("T-132", c)
    res = c.aligned("monthly").run(legs, ("flat", 1.0))           # the cached series evaluate tested
    assert res["day"] == exp[:-1] and res["exit"] == exp[1:] and rep["n_cycles"] == len(exp) - 1 and rep["grid_starts"] == 1
    # bear call spread sold for almost nothing on expiry sessions (VIX 5): mean P&L per max loss <= 0 on the calendar
    assert rep["verdict"] == "supported" and "standard monthly expiry calendar" in rep["reason"] and "block 6 cycles" in rep["ci"]
    # a grid entered off the calendar (VIX 80) collects a fat credit: the same claim fails there
    off = metric(c.aligned("daily").run(legs, ("flat", 1.0)), "per_max_loss")
    assert off.mean() > 0
    j = res["day"].index("2000-03-17"); assert res["exit"][j] == "2000-04-20"            # holiday: the prior session
    S = res["spot"][j]; T = (date(2000, 4, 20) - date(2000, 3, 17)).days / 365; r = math.log(1.04)
    want = -float(bs.price(S, 1.03 * S, T, r, 0.05, "call", Q)) + float(bs.price(S, 1.06 * S, T, r, 0.05, "call", Q))
    assert abs(res["debit"][j] - want) < 1e-12 and T == 34 / 365


def test_t517_flag_on_the_calendar_series_blocks_support(monkeypatch):
    monkeypatch.setitem(sc.MIN_N, "T-517", 30)
    c, _ = _calendar_ctx(n=900)
    seagull = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]
    good = c.aligned("monthly").run(seagull, ("flat", 1.0)); assert good["zero_cost_ok"].all()
    good["zero_cost_ok"][0] = False                                # shared cache: evaluate's calendar view sees the flag
    rep = sc.evaluate("T-517", c)
    assert rep["verdict"] != "supported" and "1 cycles with no zero-cost put strike" in rep["reason"]
    # the report describes the calendar it ran on (the halves split once reused `h`, the grid-start count, and reported
    # 'all 20 starts of the 20-day grid pooled', block 6 days, grid_starts 20)
    assert rep["grid_starts"] == 1 and "standard monthly expiry calendar" in rep["entries"] and rep["ci"].endswith("block 6 cycles")
    assert rep["entries"] in rep["reason"] and "starts of the" not in rep["reason"] and "block 6 days" not in rep["reason"]


@pytest.mark.parametrize("cid", sorted(sc.CALENDAR))
def test_calendar_claims_report_the_calendar_they_ran_on(cid):
    """Every CALENDAR claim's report (grid_starts, entries, ci, n_cycles and the reason built from them) names the monthly
    expiry calendar and blocks of 6 cycles, whatever locals the claim's own branch uses."""
    c, exp = _calendar_ctx(n=900)
    rep = sc.evaluate(cid, c)
    assert rep["grid_starts"] == 1 and rep["n_cycles"] == len(exp) - 1
    assert rep["entries"].startswith("standard monthly expiry calendar") and rep["ci"].endswith("block 6 cycles")
    assert f"{rep['entries']}; " in rep["reason"] and "block 6 cycles)" in rep["reason"] and "starts of the" not in rep["reason"]


def test_t517_halves_split_the_calendar_series():
    c, _ = _calendar_ctx(n=900)
    rep = sc.evaluate("T-517", c)
    seagull = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]
    x = metric(c.aligned("monthly").run(seagull, ("flat", 1.0)), "per_spot"); half = len(x) // 2
    assert f"halves {x[:half].mean()*100:+.2f}%/{x[half:].mean()*100:+.2f}%" in rep["reason"]


def test_default_engine_grid_unchanged_for_other_callers():
    """run_structure's default (first-day grid) is what cross_asset still calls; step/schedule are opt-in."""
    c = _grid_ctx(lambda i: 20.0, n_cycles=10)
    legs = [("call", "long", 1, 1.0), ("put", "long", 1, 1.0)]
    a = run_structure(c.days, c.closes, c.vix, c.rates, legs, 30, 21, ("flat", 1.0))
    b = run_structure(c.days, c.closes, c.vix, c.rates, legs, 30, 21, ("flat", 1.0), step=21)
    assert a["day"] == b["day"] == c.days[0:210:21] and np.array_equal(a["pnl"], b["pnl"])
    assert np.allclose(a["max_loss"], a["debit"], rtol=1e-3)       # vectorised max-loss grid: long straddle loses the premium
