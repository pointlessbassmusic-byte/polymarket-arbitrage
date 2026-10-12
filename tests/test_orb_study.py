import datetime as dt
import math
import random

import pytest

from cryptobot import orb_study as O
from cryptobot.data.geckoterminal import Candle


def _session_bars(day: dt.date, first_up: bool, drift: float, rng: random.Random, px: float = 400.0,
                  pre_market: bool = True) -> list[Candle]:
    """78 five-minute bars 09:30-16:00 New York, plus a pre-market bar that must be ignored."""
    out = []
    start = dt.datetime(day.year, day.month, day.day, 9, 30, tzinfo=O.ET)
    if pre_market:
        t = start - dt.timedelta(minutes=30)
        out.append(Candle(ts=t.timestamp(), open=px, high=px + 5, low=px - 5, close=px, volume_usd=0))
    for i in range(78):
        t = start + dt.timedelta(minutes=5 * i)
        o = px
        if i == 0:
            c = px + (0.3 if first_up else -0.3)
        else:
            c = px + (drift if first_up else -drift) + rng.gauss(0, 0.15)
        hi, lo = max(o, c) + 0.05, min(o, c) - 0.05
        out.append(Candle(ts=t.timestamp(), open=o, high=hi, low=lo, close=c, volume_usd=1000 * c))
        px = c
    return out


def _bars(days: int = 120, drift: float = 0.08, seed: int = 5) -> list[Candle]:
    rng = random.Random(seed)
    bars = []
    day = dt.date(2024, 1, 2)
    while days:
        if day.weekday() < 5:
            bars.extend(_session_bars(day, rng.random() < 0.5, drift, rng))
            days -= 1
        day += dt.timedelta(days=1)
    return bars


def test_sessions_keep_regular_hours_only_and_need_the_open_bar():
    bars = _bars(5)
    sess = O.sessions(bars)
    assert len(sess) == 5
    for d, bs in sess.items():
        assert len(bs) == 78 and O._minute_of(bs[0]) == 9 * 60 + 30 and O._minute_of(bs[-1]) == 15 * 60 + 55
    # a session missing its 09:30 bar is dropped
    trimmed = [b for b in bars if not (O._minute_of(b) == 9 * 60 + 30 and
                                       dt.datetime.fromtimestamp(b.ts, dt.timezone.utc).astimezone(O.ET).date() == dt.date(2024, 1, 2))]
    assert len(O.sessions(trimmed)) == 4


def test_atr_uses_prior_sessions_only():
    daily = [{"day": dt.date(2024, 1, 1) + dt.timedelta(days=i), "open": 100, "high": 101 + i, "low": 99, "close": 100}
             for i in range(20)]
    a = O.atr(daily, 14)
    d16 = dt.date(2024, 1, 1) + dt.timedelta(days=16)
    # ATR known on day 16 is the mean of the true ranges of days 2..15 (computed through day 15)
    expect = sum(max(2 + i, 1 + i, 1) for i in range(2, 16)) / 14
    assert a[d16] == pytest.approx(expect)
    assert min(a) > daily[14]["day"]


def test_simulate_day_direction_stop_and_sizing():
    rng = random.Random(1)
    day = dt.date(2024, 3, 4)
    bars = O.sessions(_session_bars(day, True, 0.2, rng))[day]
    rule = O.OrbRule()
    t = O.simulate_day(bars, atr_today=4.0, rule=rule, slip=0.01, capital=25_000)
    assert t and t["side"] == 1.0 and t["entry"] == bars[1].open
    assert t["shares"] == math.floor(min(0.01 * 25_000 / 0.4, 4 * 25_000 / t["entry"]))
    assert t["cost"] == pytest.approx(0.02 * t["shares"]) and t["net"] == pytest.approx(t["gross"] - t["cost"])
    # a stop: force the second bar through the stop level
    bars2 = list(bars)
    bars2[2] = Candle(ts=bars[2].ts, open=bars[2].open, high=bars[2].high, low=t["entry"] - 1.0, close=bars[2].close, volume_usd=0)
    s = O.simulate_day(bars2, 4.0, rule, 0.01, 25_000)
    assert s["reason"] == "stop" and s["r"] == pytest.approx(-1.0)
    # doji first bar: no trade
    doji = [Candle(ts=bars[0].ts, open=400, high=401, low=399, close=400, volume_usd=0)] + bars[1:]
    assert O.simulate_day(doji, 4.0, rule, 0.01, 25_000) is None


def test_planted_momentum_is_profitable_and_costs_bite():
    bars = _bars(160, drift=0.08)
    cheap = O.run(bars, slip=0.0)
    dear = O.run(bars, slip=0.05)
    assert cheap["trades"] > 100 and cheap["ann_net_pct"] > 0 and cheap["mean_r"] > 0
    assert dear["ann_net_pct"] < cheap["ann_net_pct"]
    assert O.passes(cheap)[0] in ("alive", "inconclusive")
    noise = O.run(_bars(160, drift=0.0, seed=9), slip=0.02)
    assert noise["ann_net_pct"] < cheap["ann_net_pct"]
    assert "sessions" in O.render("x", cheap)


def test_passes_rules():
    base = {"trades": 500, "ann_net_pct": 0.05, "sharpe": 0.8, "psr": 0.97, "net_2023_on": 0.01}
    assert O.passes(base) == ("alive", "clears the bar")
    assert O.passes({**base, "ann_net_pct": -0.01}) == ("killed", "net <= 0 at 1 c/share")
    assert O.passes({**base, "trades": 50})[0] == "inconclusive"
    assert O.passes({**base, "psr": 0.5})[0] == "inconclusive"
