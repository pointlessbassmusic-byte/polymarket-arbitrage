import math
import random

from cryptobot import book_study as B


def _rows(n=4000, seed=1, signal=0.0, t0=1_791_900_000.0):
    """15-second rows; `signal` is how much the next-minute mid change follows the imbalance."""
    rng = random.Random(seed)
    rows, mid, imb = [], 10.0, 0.0
    for i in range(n):
        imb = 0.7 * imb + rng.gauss(0, 0.3)
        imb = max(-1.0, min(1.0, imb))
        mid *= math.exp(signal * imb * 1e-4 + rng.gauss(0, 1e-4))
        rows.append({"ts": t0 + 15 * i, "mid": mid, "imb_10": imb, "imb_25": imb, "imb_50": imb})
    return rows


def test_forward_changes_align_on_time_and_stop_at_gaps():
    rows = _rows(100)
    f = B.forward_changes(rows, 1)
    assert f[0] is not None and abs(f[0] - math.log(rows[4]["mid"] / rows[0]["mid"])) < 1e-12
    assert f[-1] is None and f[-4] is None
    gap = rows[:10] + [dict(r, ts=r["ts"] + 3600) for r in rows[10:]]
    assert B.forward_changes(gap, 1)[9] is None


def test_signal_shows_in_regression_and_rule_and_noise_does_not():
    data = {"KXDOGEPERP": _rows(signal=40.0, seed=2), "KXKSHIBPERP": _rows(signal=40.0, seed=3)}
    res = B.run(data)
    assert res["pooled"]["imb25->5m"]["t"] > 5 and res["pooled"]["imb25->5m"]["beta_bp"] > 0
    doge = res["tickers"]["KXDOGEPERP"]["rules"]["imb25 hold5m maker"]
    assert doge["n"] > 100 and doge["net_bp"] > 0
    assert res["verdict"][0] == "collecting"                 # under 30 days
    noise = {"KXDOGEPERP": _rows(signal=0.0, seed=5), "KXKSHIBPERP": _rows(signal=0.0, seed=6)}
    rn = B.run(noise)
    assert abs(rn["pooled"]["imb25->5m"]["t"]) < 3
    assert rn["pooled_rules"]["imb25 hold5m taker"]["net_bp"] < 0
    assert "verdict:" in B.render(rn) and rn["trials"] == 18


def test_verdicts_after_thirty_days():
    def fake(days, t, taker_nets, maker_nets):
        tk = {}
        for name, tn, mn in zip(("KXDOGEPERP", "KXKSHIBPERP"), taker_nets, maker_nets):
            tk[name] = {"rules": {"imb25 hold5m taker": {"n": 50, "net_bp": tn, "first_half_bp": tn, "second_half_bp": tn},
                                  "imb25 hold5m maker": {"n": 50, "net_bp": mn}}}
        return {"days": days, "pooled": {"imb25->5m": {"t": t}}, "tickers": tk}
    assert B.passes(fake(10, 5.0, (1, 1), (2, 2)))[0] == "collecting"
    assert B.passes(fake(31, 5.0, (1, 1), (2, 2)))[0] == "alive"
    assert B.passes(fake(31, 1.0, (-1, -2), (-1, -1)))[0] == "killed"
    assert B.passes(fake(31, 5.0, (-1, -2), (3, 3)))[0] == "inconclusive"
