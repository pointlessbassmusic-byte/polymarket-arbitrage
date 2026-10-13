import math
import random

from cryptobot import perp_hourly_study as H


def _series(n=2000, kind="walk", seed=1, t0=1_790_000_000):
    rng = random.Random(seed)
    out, x = [], 0.0
    for i in range(n):
        if kind == "walk":
            x += rng.gauss(0, 0.004)
        elif kind == "reverting":
            x = 0.6 * x + rng.gauss(0, 0.004)
        else:  # trending bursts
            x += 0.5 * (out[-1][2] if out else 0.0) + rng.gauss(0, 0.004)
        out.append((t0 + 3600 * i, 100.0 * math.exp(x), x - (out[-1][1] if out else 0.0)))
    return [(ts, c) for ts, c, _ in out]


def test_grid_has_26_trials_and_rules_fire_both_ways():
    rs = H.rules()
    assert len(rs) == 24 and len({r["name"] for r in rs}) == 24
    s = _series(kind="reverting")
    tr = H.rule_trades(s, rs[0], 18.0, "X")                              # reversal-1h-k1.5-hold1h
    assert tr and {t["side"] for t in tr} == {"long", "short"}
    for a, b in zip(tr, tr[1:]):
        assert b["entry_ts"] > a["entry_ts"]                              # one position at a time
    assert all(t["net_bp"] == t["gross_bp"] - 18.0 for t in tr)


def test_reversal_wins_on_a_reverting_series_and_nothing_wins_on_a_walk():
    data = {f"C{i}": _series(kind="reverting", seed=i) for i in range(3)}
    res = H.run(data, cost_bp=18.0)
    rev = res["rules"]["reversal-1h-k1.5-hold1h"]
    mom = res["rules"]["momentum-1h-k1.5-hold1h"]
    assert rev["gross_bp"] > 10 > 0 > mom["gross_bp"]
    assert res["verdict"][0] in ("alive", "inconclusive") and res["trials"] == 26
    walk = {f"W{i}": _series(kind="walk", seed=10 + i) for i in range(3)}
    res_w = H.run(walk, cost_bp=18.0)
    nets = [s["net_bp"] for s in res_w["rules"].values() if s.get("n")]
    assert statistics_mean(nets) < 0                                      # the fee wins on a random walk
    text = H.render(res_w)
    assert "walk-forward" in text and "verdict:" in text


def test_hour_of_day_uses_only_training_bars():
    data = {"A": _series(n=4000, kind="walk", seed=4)}
    full = H.hour_of_day_trades(data, 18.0)
    assert set(full) == {"hour-long", "hour-short"} and full["hour-long"] and full["hour-short"]
    cut = data["A"][len(data["A"]) // 2][0]
    train = H.hour_of_day_trades(data, 18.0, train_until_ts=cut)
    assert train["hour-long"]                                             # chosen on the first half, traded on all


def statistics_mean(xs):
    return sum(xs) / len(xs)
