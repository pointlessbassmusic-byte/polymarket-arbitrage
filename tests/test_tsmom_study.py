import datetime as dt
import math
import random

from cryptobot import tsmom_study as T


def _closes(n_days=2600, drift=0.0, vol=0.01, trend=0.0, seed=1, start=dt.date(2016, 1, 4)):
    rng = random.Random(seed)
    out, x, mom = {}, 100.0, 0.0
    d = start
    while len(out) < n_days:
        if d.weekday() < 5:
            mom = 0.98 * mom + rng.gauss(0, vol) * trend
            x *= math.exp(drift + mom + rng.gauss(0, vol))
            out[d] = x
        d += dt.timedelta(days=1)
    return out


def test_month_ends_and_signals():
    c = _closes(300)
    me = T.month_ends(c)
    assert [m for m, _ in me] == sorted({d.strftime("%Y-%m") for d in c})
    sig = T.signals(me, 3)
    assert set(sig.values()) <= {-1, 0, 1} and len(sig) == len(me) - 3


def test_costs_only_on_flips_and_carry_every_month():
    up = {d: 100.0 * math.exp(0.001 * i) for i, d in enumerate(sorted(_closes(700)))}   # steady uptrend
    gross = T.strategy({"A": up}, 3, False, cost_bp=0.0, carry=0.0)
    net = T.strategy({"A": up}, 3, False, cost_bp=8.0, carry=0.05)
    assert len(gross) == len(net) > 10
    # always long: one flip at the start, then only the carry
    assert gross[0][1] - net[0][1] > 0.0008
    for (m, g), (_, n) in list(zip(gross, net))[1:]:
        assert abs((g - n) - 0.05 / 12) < 1e-9


def test_trending_universe_is_alive_and_a_random_one_is_not():
    trending = {f"T{i}": _closes(trend=1.0, vol=0.012, seed=i) for i in range(8)}
    res = T.run(trending, cost_bp=8.0, carry=0.05)
    reg = res["variants"]["long-short-12m"]
    assert reg["months"] > 90 and reg["annual"] > 0 and res["trials"] == 8
    assert res["verdict"][0] in ("alive", "inconclusive")
    rnd = {f"R{i}": _closes(trend=0.0, seed=20 + i) for i in range(8)}
    res_r = T.run(rnd, cost_bp=8.0, carry=0.05)
    assert res_r["variants"]["long-short-12m"]["annual"] < 0.05
    text = T.render(res_r)
    assert "registered" in text and "verdict:" in text and "per instrument" in text
    assert T.passes({"months": 100, "mean_month": -0.001, "annual": -0.012})[0] == "killed"
    assert T.passes({"months": 100, "mean_month": 0.01, "annual": 0.12, "sharpe": 1.0, "psr": 0.99, "dsr": 0.99,
                     "positive_full_years": 7, "full_years": 9})[0] == "alive"
