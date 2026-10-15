import datetime as dt

from cryptobot import carry_forward as F


def test_pair_collects_funding_when_hedge_is_perfect():
    start = dt.date(2026, 10, 15)
    days = [start + dt.timedelta(days=k) for k in range(-20, 60)]
    fund = {d: 0.20 / 365 for d in days}                 # 20%/yr, above the 4% switch
    perp = {d: 100.0 for d in days}
    ibit = {d: 50.0 for d in days if d.weekday() < 5}
    res = F.simulate(fund, perp, ibit, start)
    assert res["in_days"] == res["days"]
    # half of (20% - 0.25%) a year on both legs' capital, less one entry
    assert abs(res["net_ann"] - ((1 + (0.20 - 0.0025) / 2 / 365) ** 365 - 1)) < 0.01
    assert res["track_sd"] == 0


def test_flat_when_funding_is_low():
    start = dt.date(2026, 10, 15)
    days = [start + dt.timedelta(days=k) for k in range(-20, 40)]
    res = F.simulate({d: 0.01 / 365 for d in days}, {d: 100.0 for d in days}, {d: 50.0 for d in days}, start)
    assert res["in_days"] == 0 and res["net_total"] == 0
