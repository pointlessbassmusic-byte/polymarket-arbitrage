import math
import random

import pytest

from cryptobot import pairs_study as P

DAY = 86400


def _cointegrated(n: int = 600, seed: int = 3, beta: float = 1.5, kappa: float = 0.15, sd_e: float = 0.05):
    """Two log prices sharing a random walk with a mean-reverting spread."""
    rng = random.Random(seed)
    x, e = 0.0, 0.0
    closes = {"A": {}, "B": {}}
    for i in range(n):
        x += rng.gauss(0, 0.03)
        e = (1 - kappa) * e + rng.gauss(0, sd_e)
        d = 1_700_000_000 - 1_700_000_000 % DAY + i * DAY
        closes["B"][d] = math.exp(x)
        closes["A"][d] = math.exp(0.2 + beta * x + e)
    return closes


def test_ols_and_adf_find_the_planted_relation():
    closes = _cointegrated()
    days = sorted(closes["A"])
    y = [math.log(closes["A"][d]) for d in days]
    x = [math.log(closes["B"][d]) for d in days]
    alpha, beta, e = P.ols(y, x)
    assert abs(beta - 1.5) < 0.1 and abs(alpha - 0.2) < 0.1
    assert P.adf_t(e) < -5                        # strongly stationary residual
    walk = [sum(random.Random(1).gauss(0, 1) for _ in range(i)) for i in range(1, 200)]
    assert P.adf_t(walk) > -3.37                  # a random walk does not pass


def test_signal_window_and_z():
    closes = _cointegrated()
    days = sorted(closes["A"])
    y = [math.log(closes["A"][d]) for d in days]
    x = [math.log(closes["B"][d]) for d in days]
    assert P.signal_on(y[:50], x[:50], P.PairRule()) is None      # shorter than beta_window
    s = P.signal_on(y[:200], x[:200], P.PairRule())
    assert s and abs(s["z"]) < 5 and s["adf_t"] < 0 and s["sd"] > 0


def test_simulate_trades_the_spread_and_charges_four_executions():
    closes = _cointegrated(n=800, sd_e=0.08)
    days = sorted(closes["A"])
    res = P.simulate(closes, {}, ("A", "B"), P.PairRule(z_entry=1.5, require_eg=False), days[200], days[-1])
    closed = [t for t in res["trades"] if t["exit_reason"] != "open"]
    assert len(closed) >= 5
    for t in closed:
        assert t["fees"] == pytest.approx(4 * P.COST_PER_EXECUTION)
        assert t["net"] == pytest.approx(t["gross"] + t["funding"] - t["fees"])
        assert t["exit_day"] > t["entry_day"] and t["days"] <= 20
        # a rich y (z > 0) is shorted
        assert (t["side_y"] < 0) == (t["entry_z"] > 0)
    m = P.metrics(res["trades"], res["daily"])
    assert m["trades"] == len(closed) and m["mean_net"] > 0 and m["sharpe"] > 1.0   # planted reversion


def test_funding_sign_long_pays_short_receives():
    closes = _cointegrated(n=400, sd_e=0.08)
    days = sorted(closes["A"])
    funding = {"A": {d: 0.001 for d in days}, "B": {d: 0.001 for d in days}}   # 0.1%/day both
    rule = P.PairRule(z_entry=1.5, require_eg=False)
    free = P.simulate(closes, {}, ("A", "B"), rule, days[150], days[-1])
    paid = P.simulate(closes, funding, ("A", "B"), rule, days[150], days[-1])
    # equal rates on both legs cancel: long pays what the short receives
    for a, b in zip(free["trades"], paid["trades"]):
        assert b["funding"] == pytest.approx(0.0, abs=1e-12) and a["gross"] == pytest.approx(b["gross"])
    skew = P.simulate(closes, {"A": {d: 0.001 for d in days}}, ("A", "B"), rule, days[150], days[-1])
    for t in skew["trades"]:
        assert (t["funding"] < 0) == (t["side_y"] > 0)        # long A pays, short A receives


def test_passes_and_year_pairs():
    m = {"net_2025_26": -0.01, "sharpe": 2.0, "psr": 0.99, "trades": 50}
    assert P.passes(m, 0.99) == (False, "killed: net negative in 2025-2026")
    m = {"net_2025_26": 0.01, "sharpe": 0.6, "psr": 0.96, "trades": 31}
    assert P.passes(m, 0.96)[0] and not P.passes(m, 0.5)[0]
    assert P.year_pairs_positive({2022: 1.0, 2023: -2.0, 2024: 3.0}) == pytest.approx(2 / 3)


def test_run_counts_every_grid_cell_as_a_trial():
    closes = _cointegrated(n=700, sd_e=0.08)
    closes["C"] = dict(closes["B"])
    days = sorted(closes["A"])
    res = P.run(closes, {}, days[200], days[-1], pairs=(("A", "B"),), z_grid=(1.5, 2.0), eg_grid=(False,))
    # the registered rule (z=2, EG on) plus two grid cells that differ from it
    assert res["trials"] == 3 and len(res["grid"]) == 2 and "combined" in res["registered"]
    assert res["verdict"][1] in ("alive", "inconclusive") or res["verdict"][1].startswith("killed")
    assert "registered rule" in P.render(res)
