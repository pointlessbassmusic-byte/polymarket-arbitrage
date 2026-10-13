import json
import math
import random

from cryptobot import binary_vol_study as B


def _bars(n, start, seed=1):
    rng = random.Random(seed)
    p, out = 60000.0, []
    for i in range(n):
        o = p
        p *= math.exp(rng.gauss(0, 0.0008))
        out.append([start + i * B.STEP, o, max(o, p) * 1.0002, min(o, p) * 0.9998, p, 1.0])
    return out


def test_model_probability_is_monotone_in_strike():
    bars = _bars(40000, B.CUTOFF - 40000 * B.STEP)
    m = B.Model(bars)
    ts = bars[-1][0] + B.STEP
    spot = m.close_at[ts]
    ps = [m.prob("hour", ts - 3600 * 24, 1800, spot, "greater", spot * (1 + k / 1e3)) for k in (-5, -1, 0, 1, 5)]
    assert all(ps[i] >= ps[i + 1] for i in range(4))
    assert 0.4 < ps[2] < 0.6
    assert m.prob("none", ts, 1800, spot, "less", spot * 1.01) > 0.95


def test_run_scores_both_series(tmp_path):
    hist = _bars(40000, B.CUTOFF - 40000 * B.STEP)
    live = _bars(2000, B.CUTOFF, seed=2)
    (tmp_path / "btc5m").mkdir()
    (tmp_path / "btc5m" / "btc_5m.json").write_text(json.dumps(hist + live))
    m = B.Model(hist + live)
    for sub, series, span, minutes in (("state_collect", "KXBTCD", 3600, 30), ("state_binaries_15m", "KXBTC15M", 900, 10)):
        d = tmp_path / sub / "kalshi_binaries"
        (d / "candles").mkdir(parents=True)
        markets, cands = [], []
        for i in range(20, 1900, span // B.STEP):
            close = B.CUTOFF + i * B.STEP
            spot0, settle = m.close_at[close - span], m.close_at[close]
            strike = spot0 * 1.001
            ev = f"{series}-{i}"
            markets.append({"ticker": f"{ev}-T{strike:.2f}", "event": ev, "series": series, "strike_type": "greater",
                            "floor": strike, "cap": None, "open_ts": close - span, "close_ts": close,
                            "result": "yes" if settle > strike else "no", "settle": settle, "volume": 10.0})
            t = close - minutes * 60
            cands.append({"ticker": markets[-1]["ticker"], "bars": [[t - 60, 0.40, 0.44, 0.42, 1.0], [t, 0.40, 0.44, 0.42, 1.0]]})
        (d / "markets.jsonl").write_text("\n".join(json.dumps(x) for x in markets) + "\n")
        (d / "candles" / "a.jsonl").write_text("\n".join(json.dumps(x) for x in cands) + "\n")
    res = B.run(tmp_path)
    for s in ("KXBTCD", "KXBTC15M"):
        runs = res["series"][s]["runs"]
        assert any(r["quoted"] > 0 for r in runs.values())
        r = next(r for r in runs.values() if r["quoted"] > 0)
        assert 0 <= r["brier_model"] <= 1 and 0 <= r["brier_mid"] <= 1
    assert "basis" in res["series"]["KXBTCD"]
    assert B.render(res)
