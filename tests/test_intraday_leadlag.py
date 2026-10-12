import datetime as dt
import json
import math
import random

import pytest

from cryptobot import intraday_leadlag as L


def _series(hours: int = 1200, lead: float = 0.0, seed: int = 2, start: int = 1_791_000_000):
    """Hourly closes for 'btc' and 'us500'; with `lead` > 0 the US500 hour
    follows BTC's previous hour off-session."""
    rng = random.Random(seed)
    btc, us = {}, {}
    pb, pu = 8.0, 13.7
    prev_rb = 0.0
    for i in range(hours):
        ts = start - start % 3600 + i * 3600
        rb = rng.gauss(0, 0.004)
        ru = rng.gauss(0, 0.001) + (lead * prev_rb if not L.cash_open(ts) else 0.0)
        pb *= math.exp(rb)
        pu *= math.exp(ru)
        btc[ts], us[ts] = pb, pu
        prev_rb = rb
    return btc, us


def test_cash_open_flags_new_york_session_hours():
    mon_1430 = int(dt.datetime(2026, 10, 12, 14, 30, tzinfo=L.ET).timestamp())   # hour ending 14:30 ET Monday
    assert L.cash_open(mon_1430)
    assert not L.cash_open(int(dt.datetime(2026, 10, 12, 3, 0, tzinfo=L.ET).timestamp()))
    assert not L.cash_open(int(dt.datetime(2026, 10, 11, 14, 0, tzinfo=L.ET).timestamp()))   # Sunday
    assert L.cash_open(int(dt.datetime(2026, 10, 12, 10, 0, tzinfo=L.ET).timestamp()))       # 09:00-10:00 overlaps the open


def test_align_requires_consecutive_shared_hours():
    btc, us = _series(50)
    rows = L.align(btc, us)
    assert len(rows) == 48 and all(r["ts"] % 3600 == 0 for r in rows)
    gap = {k: v for k, v in btc.items() if k != sorted(btc)[10]}
    assert len(L.align(gap, us)) == 45            # the gap removes the hour, its return, and its "next"


def test_planted_lead_is_found_and_the_follow_rule_earns():
    btc, us = _series(2000, lead=0.5)
    res = L.run(btc, us)
    assert res["enough"] and res["btc_leads"]["closed"]["t"] > 5
    assert abs(res["btc_leads"]["open"]["t"]) < 3                    # no lead during the session
    assert res["follow_closed"]["mean_bp"] > 0 and res["verdict"][0] == "candidate"
    noise = L.run(*_series(2000, lead=0.0, seed=4))
    assert noise["verdict"][0] in ("killed", "inconclusive")
    assert "shared consecutive hours" in L.render(res)


def test_too_little_data_is_collecting(tmp_path):
    btc, us = _series(100)
    res = L.run(btc, us)
    assert not res["enough"] and res["verdict"][0] == "collecting"
    d = tmp_path / "kalshi_hourly"
    d.mkdir()
    (d / "KXBTCPERP.jsonl").write_text("".join(json.dumps({"end_ts": k, "close": v}) + "\n" for k, v in btc.items()))
    assert L.read_closes(d / "KXBTCPERP.jsonl") == btc
    assert L.read_closes(d / "missing.jsonl") == {}
