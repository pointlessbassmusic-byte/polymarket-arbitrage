"""Structure engine: straddle P&L identity, zero-cost solve, smile interpolation and wing multiplier, max-loss grid."""

import math
from datetime import date, timedelta

import numpy as np

from mandel.experiments.structures import Smile, metric, run_structure
from mandel.options import bs


def _days(n):
    d = date(2000, 1, 3); out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _setup(n=600, seed=0):
    rng = np.random.default_rng(seed); days = _days(n)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return days, closes, {d: 20.0 for d in days}, {d: 4.0 for d in days}


def test_straddle_identity_and_max_loss():
    days, closes, vix, rates = _setup()
    res = run_structure(days, closes, vix, rates, [("call", "long", 1, 1.0), ("put", "long", 1, 1.0)], 30, 21, ("flat", 1.0), q=0.0)
    S, S1 = res["spot"], np.array([closes[days.index(d) + 21] for d in res["day"]])
    assert np.allclose(res["payoff"], np.abs(S1 - S)) and np.allclose(res["pnl"], res["payoff"] - res["debit"])
    assert np.allclose(res["max_loss"], res["debit"], rtol=1e-3)            # long straddle: worst case loses the premium
    r = math.log(1.04); T = 30 / 365
    assert abs(res["debit"][0] - (float(bs.price(S[0], S[0], T, r, 0.2, "call")) + float(bs.price(S[0], S[0], T, r, 0.2, "put")))) < 1e-9


def test_zero_cost_seagull_and_smile():
    days, closes, vix, rates = _setup()
    res = run_structure(days, closes, vix, rates, [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))], 30, 21, ("flat", 1.0))
    assert np.all(np.abs(res["debit"]) < 1e-6 * res["spot"])
    rows = [{"value": {"quote_date": "2026-10-13", "target_dte": 30, "ratio": {"0.90": 1.5, "1.00": 0.8, "1.10": 0.8}}},
            {"value": {"quote_date": "2026-10-14", "target_dte": 30, "ratio": {"0.90": 1.7, "1.00": 0.8, "1.10": 0.8}}}]
    sm = Smile(rows)
    assert sm.n_days == 2 and abs(sm.ratio(0.90, 30) - 1.6) < 1e-12 and abs(sm.ratio(0.95, 30) - 1.2) < 1e-12 and sm.ratio(0.80, 30) == 1.6
    assert abs(sm.ratio(0.90, 30, wing_mult=1.5) - (0.8 + 0.8 * 1.5)) < 1e-12 and sm.ratio(1.0, 30, wing_mult=1.5) == 0.8
    m = metric(res, "per_spot"); assert m.shape == res["pnl"].shape
