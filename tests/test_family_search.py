import datetime as dt
import math
import random

from cryptobot import family_search as F


def _series(n=3000, seed=1, trend=0.0, bar=3600, t0=1_700_000_000):
    rng = random.Random(seed)
    out, x, mom = [], 100.0, 0.0
    for i in range(n):
        mom = 0.9 * mom + rng.gauss(0, 0.004) * trend
        x *= math.exp(mom + rng.gauss(0, 0.004))
        out.append((t0 + i * bar, x, abs(rng.gauss(100, 20))))
    return out


def test_features_bands_and_outcomes():
    cfg = F.SETS["kalshi_hourly"]
    s = _series(500)
    f = F.features(s, cfg)
    assert {"ret_1", "ret_4", "ret_24", "ret_168", "vol", "range_pos", "vol_ratio", "hour"} <= set(f)
    assert f["ret_168"][167] is None and f["ret_168"][168] is not None
    assert all(v is None or 0.0 <= v <= 1.0 for v in f["range_pos"])
    cuts = F.tercile_cuts(f["ret_1"])
    assert len(cuts) == 2 and F.band(None, cuts) == -1 and F.band(cuts[0] - 1, cuts) == 0 and F.band(cuts[1] + 1, cuts) == 2
    closes = [100, 101, 103, 99, 98, 100, 100, 100]
    lr, sr, ex = F.outcomes(closes, 0.02, 0.01, 4)
    assert lr[0] > 0.02 and ex[0] == 2                      # long from 100 hits +3% at bar 2
    assert sr[0] < 0 and ex[0] >= 2                          # the short is stopped there too


def test_rule_grid_and_names_round_trip():
    rs = F.rules(["a", "b"])
    assert len(rs) == 6 + 9
    name = F.rule_name((("ret_1", 2), ("vol", 0)), "short", (0.01, 0.005, 24))
    assert F.parse_name(name) == ("short", (("ret_1", 2), ("vol", 0)), (0.01, 0.005, 24))


def test_family_on_noise_is_not_a_candidate_and_runs_end_to_end():
    cfg = dict(F.SETS["kalshi_hourly"], geometries=((0.01, 0.005, 4), (0.02, 0.01, 24)))
    data = {f"C{i}": _series(1200, seed=i) for i in range(3)}
    res = F.run(data, cfg)
    assert res["n_columns"] > 50 and res["n_eff"] >= 1 and len(res["top"]) == 10
    assert res["verdict"][0] in ("inconclusive", "closed")
    text = F.render(res, "test")
    assert "walk-forward" in text and "verdict:" in text
    wf = res["walk_forward"]
    assert wf["n"] > 0 and len(wf["chosen"]) >= 1
