"""Published-strategy study, on synthetic panels with known answers."""

import datetime as dt

import pytest

from cryptobot.backtest import Candle, PoolMeta
from cryptobot.data.hyperliquid import Funding
from cryptobot import factor_study as F

D = F.DAY
T0 = int(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp())   # a Monday


def _pool(sym, closes, vols=None, start=T0):
    vols = vols or [1000.0] * len(closes)
    return (PoolMeta(chain="hyperliquid", pair_address=sym, symbol=sym, token_address="",
                     liquidity_usd=0.0, fdv_usd=None),
            [Candle(ts=start + i * D, open=c, high=c, low=c, close=c, volume_usd=vols[i])
             for i, c in enumerate(closes)])


class TestPanel:
    def test_returns_and_long_funding(self):
        p = F.Panel({"A": _pool("A", [1.0, 2.0, 3.0])},
                    {"A": [Funding(ts=T0 + D + h * 3600, rate=0.001, premium=0.0) for h in range(48)]})
        assert p.ret("A", T0, T0 + 2 * D) == pytest.approx(2.0)
        assert p.funding("A", T0, T0 + 2 * D) == pytest.approx(0.048)   # days 1 and 2
        assert p.ret("A", T0, T0 + 9 * D) is None

    def test_sma_needs_full_window(self):
        p = F.Panel({"A": _pool("A", [1.0, 2.0, 3.0])})
        assert p.sma("A", T0 + 2 * D, 3) == pytest.approx(2.0)
        assert p.sma("A", T0 + 2 * D, 4) is None


def _trending_panel(persist: bool):
    """20 coins with fixed weekly drifts: rank stays the same every week
    when `persist`, flips every week otherwise."""
    pools = {}
    for k in range(20):
        drift = (k - 10) / 1000
        closes, px = [], 100.0
        for i in range(400):
            wk = i // 7
            sign = 1 if persist or wk % 2 == 0 else -1
            px *= 1 + sign * drift
            closes.append(px)
        pools[f"C{k}"] = _pool(f"C{k}", closes)
    return F.Panel(pools)


class TestWeeklyLongShort:
    def test_persistent_ranks_make_momentum_pay(self):
        p = _trending_panel(persist=True)
        rows = F.weekly_long_short(p, F.momentum_score(p), start=T0 + 35 * D)
        assert rows and all(r["gross"] > 0 for r in rows)

    def test_flipping_ranks_make_reversal_pay(self):
        p = _trending_panel(persist=False)
        mom = F.weekly_long_short(p, F.momentum_score(p), start=T0 + 35 * D)
        rev = F.weekly_long_short(p, F.momentum_score(p), start=T0 + 35 * D, reverse=True)
        assert sum(r["gross"] for r in mom) < 0 < sum(r["gross"] for r in rev)

    def test_cost_is_two_round_trips_per_week(self):
        p = _trending_panel(persist=True)
        r = F.weekly_long_short(p, F.momentum_score(p), start=T0 + 35 * D)[0]
        assert r["net"] == pytest.approx(r["gross"] + r["funding"] - 2 * F.RT)

    def test_coins_without_history_are_ineligible(self):
        p = _trending_panel(persist=True)
        assert F.weekly_long_short(p, F.momentum_score(p), start=T0 + 7 * D,
                                   min_history=30)[0]["week"] >= T0 + 28 * D


class TestEvents:
    def test_fomo_fires_on_a_volume_spike_in_an_uptrend(self):
        n = 60
        up = [100 * 1.01 ** i for i in range(n)]
        vols = [100.0] * n
        vols[50] = 1000.0
        p = F.Panel({"BTC": _pool("BTC", up), "A": _pool("A", up, vols)})
        ev = F.fomo_events(p, start=T0, holds=(1,))
        assert [d for d, _ in ev["signal"][1]] == [T0 + 50 * D]
        assert len(ev["baseline"][1]) > 1

    def test_fomo_silent_when_btc_is_below_trend(self):
        n = 60
        down = [100 * 0.99 ** i for i in range(n)]
        vols = [100.0] * n
        vols[50] = 1000.0
        p = F.Panel({"BTC": _pool("BTC", down), "A": _pool("A", [100 * 1.01 ** i for i in range(n)], vols)})
        assert F.fomo_events(p, start=T0, holds=(1,))["signal"][1] == []

    def test_listing_short_return_and_cutoff(self):
        old = _pool("OLD", [1.0] * 40, start=F.LISTING_CUTOFF - 100 * D)
        new = _pool("NEW", [2.0] + [1.0] * 40)
        rows = F.listing_events(F.Panel({"OLD": old, "NEW": new}), holds=(7,))
        assert [r["coin"] for r in rows] == ["NEW"]
        assert rows[0][7] == pytest.approx(0.5 - F.RT)
