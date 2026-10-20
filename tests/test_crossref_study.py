import datetime as dt
import math
import random

from cryptobot import crossref_study as X


def _stock(n=900, seed=1, beta=1.5, btc=None, start=dt.date(2017, 1, 2)):
    rng = random.Random(seed)
    rows, px, d, i = [], 100.0, start, 0
    while len(rows) < n:
        if d.weekday() < 5:
            b = btc.get(d.isoformat(), 0.0) if btc else 0.0
            px *= math.exp(beta * b + rng.gauss(0, 0.01))
            rows.append({"date": d.isoformat(), "open": px * math.exp(rng.gauss(0, 0.002)), "close": px,
                         "high": px * 1.01, "low": px * 0.99, "volume": 1e6 * (1 + abs(rng.gauss(0, 0.2)))})
            i += 1
        d += dt.timedelta(days=1)
    return rows


def test_pairs_and_squeeze_and_rules():
    rng = random.Random(3)
    days, d = [], dt.date(2016, 1, 1)
    while len(days) < 1400:
        days.append(d.isoformat()); d += dt.timedelta(days=1)
    rets = {dd: rng.gauss(0, 0.02) for dd in days}
    level, btc = 10000.0, {}
    for dd in days:
        level *= math.exp(rets[dd]); btc[dd] = level
    stock = _stock(900, beta=1.5, btc=rets)
    res = X.pairs_relation(stock, btc)
    assert set(res) == {5, 20} and res[5]["n"] > 300 and "rule" in res[5]
    # a squeeze: +40% in 10 days on 5x volume, then a planted reversal
    rows = _stock(400, seed=9)
    for k in range(200, 210):
        rows[k]["close"] *= 1.04 ** (k - 199); rows[k]["volume"] *= 6
    for k in range(210, 221):
        rows[k]["close"] = rows[209]["close"] * 0.8
    ev = X.squeeze_events({"GME": rows})
    assert len(ev) == 1 and ev[0][0] == "GME" and ev[0][2] < 0
    assert X.threshold_rule([(dd, 0.05) for dd in days[:30]], 8.0)["net_bp"] > 400
    st = X.nw([(dd, rng.gauss(0, 1), rng.gauss(0, 0.01)) for dd in days[:500]])
    assert abs(st["t"]) < 3 and len(st["halves"]) == 2 and not X.candidate(st, 1)


def test_btc_at_uses_eastern_hours():
    base = dt.datetime(2026, 7, 1, 20, 0, tzinfo=dt.timezone.utc)     # 16:00 ET in summer
    hourly = {int(base.timestamp()): 100.0}
    assert X.btc_at(hourly, "2026-07-01", 16) == 100.0
    assert X.btc_at(hourly, "2026-07-01", 20) is None
