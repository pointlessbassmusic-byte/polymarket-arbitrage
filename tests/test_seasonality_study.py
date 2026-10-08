import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from cryptobot import seasonality_study as SS

ET = ZoneInfo("America/New_York")


def synthetic(days: int = 10):
    """Hourly closes where price rises 1% between 16:00 ET and the next
    10:00 ET and falls 0.5% during the session, flat otherwise."""
    rows = []
    price = 100.0
    t0 = dt.datetime(2025, 3, 3, 0, 0, tzinfo=ET)      # a Monday
    for h in range(days * 24):
        start = t0 + dt.timedelta(hours=h)
        end = start + dt.timedelta(hours=1)
        if end.weekday() < 5 and end.hour == 10 and start.weekday() < 5:
            pass
        # price move realised in the candle ending at `end`
        if end.hour == 10 and end.weekday() < 5:
            price *= 1.01
        elif end.hour == 16 and end.weekday() < 5:
            price *= 0.995
        rows.append((int(start.timestamp()), price, price, price, price, 1.0))
    return rows


def test_legs_measure_overnight_and_session_returns():
    rows = SS.legs(SS.hourly_closes(synthetic()))
    weekdays = [r for r in rows if not r["weekend"]]
    assert weekdays and all(abs(r["overnight"] - 0.01) < 1e-9 for r in weekdays)
    assert all(abs(r["session"] + 0.005) < 1e-9 for r in weekdays)
    fri = [r for r in rows if r["weekend"]]
    assert fri and all(abs(r["overnight"] - 0.01) < 1e-9 for r in fri)   # Friday 16:00 -> Monday 10:00


def test_report_and_verdict():
    rows = SS.legs(SS.hourly_closes(synthetic(40)))
    rep = SS.report(rows, 0.0008, dt.date(2025, 1, 1), dt.date(2025, 12, 31), dt.date(2025, 3, 20))
    assert rep["overall"]["n"] == len(rows) and rep["overall"]["mean"] == pytest.approx(0.01 - 0.0008)
    assert rep["overall"]["mean"] > 0 and rep["post_pub"]["n"] > 0   # constant returns: sd 0, SR undefined
    assert "inconclusive" in SS.verdict(rep)                           # SR 0 with sd 0 never passes
    flat = {"overall": {"sr": 0.0, "psr": 0.5, "sum": -1.0}, "post_pub": {"sum": -1.0}}
    assert SS.verdict(flat).startswith("FAIL")
    assert "inconclusive" in SS.verdict({"overall": {"sr": 0.1, "psr": 0.8, "sum": 1.0}, "post_pub": {"sum": 0.5}})
    assert "overnight leg" in SS.render(rep)
