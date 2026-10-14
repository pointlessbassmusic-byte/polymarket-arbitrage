import datetime as dt
import json
import math
import random

from cryptobot import macro_study as M
from cryptobot.data import macro as D


def _write(state, sid, rows):
    D.write_series(state, sid, rows)


def _days(n, start=dt.date(2016, 1, 4)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def test_predictor_kinds_and_prior_value():
    vals = {d: float(i) for i, d in enumerate(_days(100))}
    diff = M.predictor(vals, "diff", 5)
    assert all(abs(v - 5.0) < 1e-9 for v in diff.values())
    lvl = M.predictor(vals, "level", 1)
    assert lvl == vals
    z = M.predictor(vals, "z", 10)
    assert all(v > 0 for v in z.values())
    assert M.prior_value(vals, _days(100)[10]) == vals[_days(100)[9]]


def test_a_planted_lead_is_a_candidate_and_noise_is_not(tmp_path):
    rng = random.Random(3)
    days = _days(2600)
    pred_rows, px, x = [], [], 100.0
    levels = [100.0]
    for i, d in enumerate(days):
        levels.append(levels[-1] + rng.gauss(0, 1))             # the real yield as a random walk
        pred_rows.append((d, levels[-1]))
        q = levels[-1] - levels[max(0, len(levels) - 6)]        # its 5-day change, the registered predictor
        # the target drifts AGAINST that change over the following days (literature sign -1), strongly
        x *= math.exp(-0.0015 * q + rng.gauss(0, 0.004))
        px.append((d, x))
    _write(tmp_path, "DFII10", pred_rows)
    _write(tmp_path, "GLD", px)
    noise = [(d, 100 + rng.gauss(0, 1)) for d in days]
    _write(tmp_path, "VIXCLS", noise)
    spy = []
    y = 100.0
    for d in days:
        y *= math.exp(rng.gauss(0.0002, 0.01))
        spy.append((d, y))
    _write(tmp_path, "SPY", spy)
    res = M.run(tmp_path)
    gold = res["relations"]["real yield 5d chg -> GLD"]
    assert gold["horizons"][5]["t"] < -2.5 and gold["verdict"][0] == "candidate"
    vix = res["relations"]["VIX level -> SPY"]
    assert vix["verdict"][0] in ("inconclusive", "killed")
    assert "GDX/GLD" in M.render(res) and res["trials"] > 0
