"""Harness rule 10 (no arbitrary grid phase) for mandel/experiments/volatility.py.

The model-priced overlays (T-54..T-57) used to run on a 21-session grid from the first aligned day: one of 21 equally valid
phases. Their claims name monthly options, so the cycles now follow the standard monthly expiry (third Friday, the prior
session on a holiday), written at one expiry's close and settled at the next. The variance-premium test uses every day and is
unaffected; a premium planted on one grid phase only does not carry it. The implied-move test (T-66) pools overlapping daily
captures, so its bootstrap block is at least twice the realised window.
"""

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import run
from mandel.experiments.volatility import implied_move_vs_realised, monthly_expiry_sessions, overlay_backtest, overlay_verdict, variance_risk_premium
from mandel.validation.backtest_eval import sharpe_ratio
from tests.test_mandel_audit_vs import _surface_history


def _sessions(start: str, n: int, holidays=()) -> list[str]:
    """n weekday sessions from start, skipping the given holidays."""
    d, out, skip = date.fromisoformat(start), [], set(holidays)
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _px_rows(days, closes, symbol="SPY"):
    return [{"value": {"symbol": symbol, "t": datetime.fromisoformat(d).replace(hour=20, tzinfo=timezone.utc).timestamp(), "close": float(c)}}
            for d, c in zip(days, closes)]


def _idx_rows(days, vals):
    return [{"value": {"day": d, "close": float(v)}} for d, v in zip(days, vals)]


def _bill_rows(days, pct):
    """A constant DTB3 series with one print dated the day before the data, so every cycle (session 0 of a grid included) has a
    print dated before its entry (harness rule 4)."""
    before = (date.fromisoformat(days[0]) - timedelta(days=1)).isoformat()
    return _idx_rows([before] + list(days), np.full(len(days) + 1, pct))


def _dtb3_cont(pct):
    """Harness rule 7: DTB3 is a discount yield; the continuous rate is -ln(1 - d*91/360)/(91/365)."""
    return -math.log(1 - pct / 100 * 91 / 360) / (91 / 365)


def _passes_t57(rep: dict) -> bool:
    """T-57's pass on an overlay: mean > 0, p < 0.05, both halves > 0."""
    v = overlay_verdict(rep, versus="zero", n_boot=500)
    return v["mean_excess_per_cycle"] > 0 and v["p_value_mean_excess"] < 0.05 and all(h > 0 for h in v["halves"])


def test_monthly_expiry_sessions_are_third_fridays_or_the_prior_session():
    days = _sessions("2018-01-01", 800, holidays=("2019-04-19",))          # Good Friday 2019 was the April third Friday
    ex = [days[j] for j in monthly_expiry_sessions(days)]
    assert "2019-04-18" in ex and "2019-04-19" not in ex                  # holiday: the prior session
    for d in ex:
        dd = date.fromisoformat(d)
        if d != "2019-04-18":
            assert dd.weekday() == 4 and 15 <= dd.day <= 21                # a third Friday
    months = {d[:7] for d in days if d[8:] >= "15"}                       # every month whose third Friday is inside the data
    assert len(ex) == len(set(e[:7] for e in ex)) and ex[0] == "2018-01-19"
    assert len(ex) >= len(months) - 1


def test_overlay_cycles_run_expiry_to_expiry_with_their_own_tenor():
    days = _sessions("2015-01-01", 1300)
    rng = np.random.default_rng(1)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(days))))
    px, vix, rate = _px_rows(days, closes), _idx_rows(days, np.full(len(days), 16.0)), _bill_rows(days, 2.0)
    rep = overlay_backtest(px, vix, rate, "cash_secured_put")
    ex = monthly_expiry_sessions(days)
    assert rep["n_cycles"] == len(ex) - 1 and rep["calendar"].startswith("monthly expiry")
    assert rep["first_day"] == days[ex[0]] and rep["last_day"] == days[ex[-1]]
    tenors = np.diff(ex) / 252
    assert np.allclose(rep["bill_returns"], np.exp(_dtb3_cont(2.0) * tenors) - 1)   # each cycle funded on its own 19-25 sessions (no holidays here)
    assert rep["cycle_sessions"] == [int(np.diff(ex).min()), int(np.diff(ex).max())] and 19 <= np.diff(ex).min() <= np.diff(ex).max() <= 25
    bh = overlay_backtest(px, vix, rate, "buy_and_hold")
    assert np.allclose(bh["benchmark"], closes[ex[1:]] / closes[ex[:-1]] - 1)
    assert abs(rep["sharpe"] - sharpe_ratio(rep["returns"] - rep["bill_returns"], 12)) < 1e-12
    # the old grid is still there as one explicit phase, never the default
    g0 = overlay_backtest(px, vix, rate, "buy_and_hold", calendar="grid", offset=0)
    idx = np.arange(0, len(closes) - 21, 21)
    assert np.allclose(g0["benchmark"], closes[idx + 21] / closes[idx] - 1) and "diagnostic only" in g0["calendar"]
    with pytest.raises(ValueError):
        overlay_backtest(px, vix, rate, "buy_and_hold", calendar="grid", offset=21)


def _planted(days, quiet: set, seed: int):
    """Flat-ish SPY that sits near 100 on the 'quiet' sessions and jumps by a random +-8..15% on every other session of the
    block between two quiet sessions: a short straddle written and settled on quiet sessions keeps its whole premium."""
    rng = np.random.default_rng(seed)
    noise = np.cumsum(rng.normal(0, 0.002, len(days)))
    logp, jump = np.empty(len(days)), 0.0
    for i, d in enumerate(days):
        if d in quiet:
            jump = rng.choice([-1, 1]) * rng.uniform(0.08, 0.15)        # the next block's displacement
            logp[i] = noise[i]
        else:
            logp[i] = noise[i] + jump
    return 100 * np.exp(logp)


def test_short_straddle_effect_on_one_grid_phase_does_not_pass():
    days = _sessions("2010-01-01", 2700)
    closes = _planted(days, {d for i, d in enumerate(days) if i % 21 == 0}, seed=3)    # quiet only on phase 0 of the 21-session grid
    px, vix, rate = _px_rows(days, closes), _idx_rows(days, np.full(len(days), 16.0)), _bill_rows(days, 2.0)
    phase0 = overlay_backtest(px, vix, rate, "short_straddle", calendar="grid", offset=0)
    assert _passes_t57(phase0)                                             # the old harness's phase sees a 'premium'
    others = [_passes_t57(overlay_backtest(px, vix, rate, "short_straddle", calendar="grid", offset=o)) for o in range(1, 21)]
    assert not any(others)                                                 # no other phase does
    rep = overlay_backtest(px, vix, rate, "short_straddle")                # the claim's calendar: monthly expiries
    assert not _passes_t57(rep) and rep["mean_cycle_return"] < 0


def test_short_straddle_effect_on_the_monthly_expiry_calendar_is_found():
    days = _sessions("2010-01-01", 2700)
    quiet = {days[j] for j in monthly_expiry_sessions(days)}
    closes = _planted(days, quiet, seed=4)                                 # quiet on every monthly expiry session
    px, vix, rate = _px_rows(days, closes), _idx_rows(days, np.full(len(days), 16.0)), _bill_rows(days, 2.0)
    rep = overlay_backtest(px, vix, rate, "short_straddle")
    assert rep["n_cycles"] >= 100 and _passes_t57(rep)
    assert not _passes_t57(overlay_backtest(px, vix, rate, "short_straddle", calendar="grid", offset=0))


class _Arch:
    def __init__(self, bundles):
        self._b = bundles

    def load(self, name):
        return iter(self._b[name])


def test_overlay_harnesses_report_monthly_expiry_cycles():
    days = _sessions("2012-01-02", 2600)
    rng = np.random.default_rng(6)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(days))))
    arch = _Arch({"daily-history-SPY": _px_rows(days, closes), "cboe-VIX-history": _idx_rows(days, np.full(len(days), 16.0)),
                  "fred-DTB3": _bill_rows(days, 2.0)})
    n_monthly = len(monthly_expiry_sessions(days)) - 1
    for h in (run.harness_covered_call, run.harness_csp, run.harness_collar, run.harness_short_straddle):
        stat, n, verdict, reason = h(arch)
        assert n == n_monthly and verdict == "inconclusive"                # model-priced: inconclusive by design
        assert stat["at_vix"]["calendar"].startswith("monthly expiry") and stat["at_vix"]["n_cycles"] == n_monthly


def test_variance_premium_is_a_daily_series_and_ignores_a_one_phase_premium():
    days = _sessions("2010-01-01", 3000)
    rng = np.random.default_rng(8)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.16 / math.sqrt(252), len(days))))
    iv = np.where(np.arange(len(days)) % 21 == 0, 30.0, 12.0)              # rich implied vol on phase-0 days only
    rep = variance_risk_premium(_idx_rows(days, iv), _px_rows(days, closes))
    assert rep["n"] == len(days) - 1 - 21 and rep["verdict"] == "not_supported" and rep["vrp_variance_points"] < 0


def test_implied_move_block_is_at_least_twice_the_realised_window():
    """T-66 pools every overlapping daily capture; rule 10 asks for bootstrap blocks at least twice the hold. A 21-session
    realised window shared by about 21 consecutive captures needs a block of at least 42 captures (it was about 21)."""
    rep = implied_move_vs_realised(*_surface_history(seed=3, n_cap=700, h=21), n_boot=199)
    assert rep["block_len"] >= 42 and f"block {rep['block_len']} captures" in rep["reason"]


def test_overlay_without_a_prior_bill_is_inconclusive_not_an_error():
    """Rule 9: when no DTB3 print is dated before any entry, every cycle is dropped and the overlay is a data limit
    (inconclusive, the cause named), never a crash."""
    from mandel.experiments import volatility as vol
    days = _sessions("2010-01-04", 400)
    px = _px_rows(days, [100.0 + 0.05 * i for i in range(len(days))])
    vix = _idx_rows(days, [20.0] * len(days))
    late = _bill_rows(["2099-01-02"], [5.0])                   # the only print is dated after every entry
    rep = vol.overlay_backtest(px, vix, late, "covered_call")
    assert rep["n_cycles"] == 0 and rep["cycles_without_prior_bill"] > 0 and "no DTB3 print" in rep["no_cycles_reason"]
    out = vol.overlay_verdict(rep)
    assert out["verdict"] == "inconclusive" and "no DTB3 print dated before any entry" in out["reason"]
