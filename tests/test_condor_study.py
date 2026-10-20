import datetime as dt
import math
import random

from cryptobot import condor_study as C
from cryptobot.vrp_study import Closes


def _path(days=600, vol=0.40, seed=1, start=dt.date(2024, 1, 1)):
    rng = random.Random(seed)
    px, s = {}, 50_000.0
    for i in range(days):
        s *= math.exp(rng.gauss(0.0, vol / math.sqrt(365.0)))
        px[start + dt.timedelta(days=i)] = s
    return px


def test_condor_pays_when_implied_is_rich_and_loses_when_cheap():
    px = Closes(_path(vol=0.40, seed=3))
    rich = {d: 0.70 for d in px.px}
    cheap = {d: 0.20 for d in px.px}
    tr = C.condor_trades(rich, px, None)
    assert len(tr) >= 12 and all(t["exit"] > t["entry"] for t in tr)
    assert all(-100.5 <= t["pnl"] <= 100.5 for t in tr)                  # defined risk: never beyond the width
    assert sum(t["pnl"] for t in tr) > 0
    tc = C.condor_trades(cheap, px, None)
    assert sum(t["pnl"] for t in tc) < 0
    for a, b in zip(tr, tr[1:]):
        assert b["entry"] > a["exit"]                                     # one at a time
    assert {t["outcome"] for t in tr} <= {"max", "partial", "wiped"}


def test_run_counts_nine_trials_and_renders():
    px = Closes(_path(900, vol=0.45, seed=7))
    iv = {d: 0.55 for d in px.px}
    res = C.run(iv, px)
    assert res["trials"] == 9 and res["registered"] in res["variants"]
    reg = res["variants"][res["registered"]]
    assert reg["trades"] > 10 and "dsr" in reg
    text = C.render(res)
    assert "registered" in text and "verdict:" in text
    assert C.passes({"trades": 5, "mean_month": -1.0})[0] == "killed"
    assert C.passes({"trades": 5, "mean_month": 2.0, "sharpe": 1.0, "psr": 0.99, "dsr": 0.99, "worst_month": -30, "net_2024_on": 5})[0] == "alive"
