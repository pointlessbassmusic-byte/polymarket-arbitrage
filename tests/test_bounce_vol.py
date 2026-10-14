import math
import pickle
import random
from types import SimpleNamespace

from cryptobot import bounce_vol_study as B


def test_runs_and_weights_are_clipped(tmp_path):
    rng = random.Random(2)
    d = {}
    for coin in ("DOGE", "kSHIB", "WIF"):
        p, cs = 1.0, []
        for i in range(500):
            o = p
            sd = 0.03 if (i // 60) % 2 else 0.09
            p *= math.exp(rng.gauss(0, sd))
            cs.append(SimpleNamespace(ts=1_700_000_000 + 86400 * i, open=o, high=max(o, p) * (1 + sd / 3),
                                      low=min(o, p) * (1 - sd / 3), close=p, volume_usd=1e6))
        d[coin] = (SimpleNamespace(symbol=coin), cs)
    pickle.dump(d, open(tmp_path / "hl_all_daily.pkl", "wb"))
    res = B.run(tmp_path)
    assert res["memecoins"]["equal"]["n"] >= 10
    assert all(0.25 <= t["w"] <= 2.0 for t in B.trades(d["DOGE"][1]))
    assert res["verdict"] in ("adopt", "killed") and B.render(res)
