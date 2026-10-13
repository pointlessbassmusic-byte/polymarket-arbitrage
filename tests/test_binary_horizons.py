import json
import random

from cryptobot import binary_horizons_study as B


def _write(d, markets, cands):
    k = d / "kalshi_binaries"
    (k / "candles").mkdir(parents=True)
    (k / "markets.jsonl").write_text("\n".join(json.dumps(m) for m in markets) + "\n")
    (k / "candles" / "a.jsonl").write_text("\n".join(json.dumps(c) for c in cands) + "\n")


def test_classes():
    assert B.horizon_class(900) == "15m"
    assert B.horizon_class(3600) == "hourly"
    assert B.horizon_class(86400 + 3600) == "daily"
    assert B.horizon_class(7 * 86400) == "weekly"
    assert B.horizon_class(30 * 86400) == "monthly+"


def test_favourite_bias_found_and_scored(tmp_path):
    rng = random.Random(7)
    markets, cands = [], []
    t0 = 1_790_000_000
    for e in range(120):
        open_ts = t0 + e * 86400
        close_ts = open_ts + 86400
        tk = f"KXTESTD-{e}-T1"
        # quoted at 0.90 but resolves in favour 97% of the time
        res = "yes" if rng.random() < 0.97 else "no"
        markets.append({"ticker": tk, "event": f"E{e}", "series": "KXTESTD", "strike_type": "greater", "floor": 1.0, "cap": None,
                        "open_ts": open_ts, "close_ts": close_ts, "result": res, "settle": 1.0, "volume": 10.0})
        cands.append({"ticker": tk, "bars": [[open_ts + 3600 * h, 0.89, 0.91, 0.9, 1.0] for h in range(25)]})
    _write(tmp_path / "state_bin" / "KXTESTD", markets, cands)
    res = B.run(tmp_path)
    d = res["classes"]["daily"]
    assert d["markets"] == 120
    st = d["fav"][0.5]
    assert st["events"] == 120 and st["net"] > 0.03 and st["t"] > 2.5
    assert any(c.startswith("daily") for c in res["candidates"])
    assert B.render(res)
