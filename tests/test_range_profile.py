import math
import random

from cryptobot import range_profile as R


def _bars(n=20000, sec=300, seed=1, t0=1_790_000_000):
    rng = random.Random(seed)
    out, px = [], 100.0
    for i in range(n):
        o = px
        px *= math.exp(rng.gauss(0, 0.001))
        hi, lo = max(o, px) * (1 + abs(rng.gauss(0, 0.0005))), min(o, px) * (1 - abs(rng.gauss(0, 0.0005)))
        out.append((t0 + i * sec, o, hi, lo, px, abs(rng.gauss(10, 3))))
    return out


def test_resample_and_profile_scale_with_horizon():
    bars = _bars()
    h = R.resample(bars, 3600)
    assert len(h) > 0
    assert all(b[2] >= max(b[1], b[4]) >= min(b[1], b[4]) >= b[3] for b in h)
    prof = R.horizon_profile(bars, 300)
    assert "5m" in prof and "1h" in prof and "1d" in prof, list(prof)
    assert prof["5m"]["move_median_bp"] < prof["1h"]["move_median_bp"] < prof["1d"]["move_median_bp"]
    assert 0 <= prof["1h"]["share_move_gt_cost"] <= 1


def test_seasonality_volume_and_render():
    bars = _bars(90000)
    s = R.seasonality(bars, 300)
    assert len(s["hour"]) == 24 and len(s["weekday"]) == 7
    assert abs(sum(v["vol_share"] for v in s["hour"].values()) - 1.0) < 1e-6
    v = R.volume_signal(bars, 300)
    assert "base" in v and "1h" in v and abs(v["base"]["ret_t"]) < 4
    res = {"source": "test", "base": 300, "coins": {"X": {"profile": R.horizon_profile(bars, 300), "season": s, "volume": v}}, "pooled": {}}
    for name, _ in R.HORIZONS:
        if name in res["coins"]["X"]["profile"]:
            res["pooled"][name] = {k: val for k, val in res["coins"]["X"]["profile"][name].items() if k != "n"} | {"coins": 1}
    text = R.render(res)
    assert "busiest UTC hours" in text and "volume ratio" in text


def test_minute_structure_on_synthetic_minutes():
    import math, random
    from cryptobot import range_profile as R
    rng = random.Random(3)
    p, bars = 100.0, []
    t0 = 1_700_000_000 - 1_700_000_000 % 3600
    for i in range(60 * 24 * 20):
        o = p
        p *= math.exp(rng.gauss(0, 0.0005))
        bars.append((t0 + 60 * i, o, max(o, p) * 1.0001, min(o, p) * 0.9999, p, 1.0 + rng.random()))
    ms = R.minute_structure(bars, 60)
    assert len(ms["minute"]) == 60
    assert abs(ms["autocorr"]["1m lag 1"]["t"]) < 4
    assert set(ms["within_hour"]) == {15, 30, 45}
    assert R.minute_structure(bars, 300) == {}
    prof = R.horizon_profile(bars, 60)
    assert "1m" in prof and "10m" in prof
