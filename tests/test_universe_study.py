import datetime as dt
import json
import math
import random

from cryptobot import universe_study as U


def _hist(n=700, seed=1, vol=0.02, drift=0.0, start=dt.date(2017, 1, 3)):
    rng = random.Random(seed)
    rows, px, d = [], 100.0, start
    while len(rows) < n:
        if d.weekday() < 5:
            px *= math.exp(drift + rng.gauss(0, vol))
            rows.append({"date": d.isoformat(), "open": px, "close": px, "high": px, "low": px, "volume": 1e6 * (1 + abs(rng.gauss(0, 0.3)))})
        d += dt.timedelta(days=1)
    return rows


def test_features_standouts_and_a_planted_vol_effect(tmp_path):
    (tmp_path / "universe" / "hist").mkdir(parents=True)
    (tmp_path / "universe" / "si").mkdir(parents=True)
    meta = {}
    for i in range(60):
        vol = 0.01 + 0.0005 * i                              # higher-vol names drift DOWN hard: the planted effect
        rows = _hist(seed=i, vol=vol, drift=-0.004 * i / 60)
        json.dump(rows, open(tmp_path / "universe" / "hist" / f"S{i}.json", "w"))
        meta[f"S{i}"] = {"name": f"S{i}", "sector": "Tech", "cap": 1e9, "dollar_volume": 1e7}
        if i % 2 == 0:
            json.dump([{"settlementDate": "09/30/2026", "interest": "1,000", "avgDailyShareVolume": "100", "daysToCover": float(i)},
                       {"settlementDate": "09/15/2026", "interest": "900", "avgDailyShareVolume": "100", "daysToCover": float(i)}],
                      open(tmp_path / "universe" / "si" / f"S{i}.json", "w"))
    json.dump({"symbols": list(meta), "meta": meta}, open(tmp_path / "universe" / "universe.json", "w"))
    u, hist, si = U.load_universe(tmp_path)
    assert len(hist) == 60 and len(si) == 30
    f = U.features_at(hist["S10"], 300)
    assert f and 0 < f["vol"] < 1 and f["vol_ratio"] > 0
    st = U.standouts(u, hist, si)
    assert int(st["most_volatile"][0]["symbol"][1:]) >= 50 and st["highest_days_to_cover"][0]["symbol"] == "S58"
    assert int(st["least_volatile"][0]["symbol"][1:]) < 10
    res = U.run(tmp_path)
    assert res["trials"] == 6 and res["sorts"]["vol"]["spread"]["mean_bp"] < 0
    text = U.render(res)
    assert "most volatile" in text and "verdict:" in text
