"""Tests for the funding-carry study on hand-built funding histories."""

import datetime as dt

import pytest

from cryptobot.data.hyperliquid import Funding
from cryptobot import carry_study as C

DAY = 86400
T0 = int(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp())


def _hourly(coin_rates: dict[str, float], days: int, start=T0):
    """Constant hourly rate per coin for `days` days."""
    return {c: [Funding(ts=start + h * 3600, rate=r, premium=0.0)
                for h in range(days * 24)] for c, r in coin_rates.items()}


class TestDailyFunding:
    def test_sums_hourly_rows_into_days(self):
        daily = C.daily_funding(_hourly({"A": 0.0001}, 2))
        assert set(daily["A"]) == {T0, T0 + DAY}
        assert daily["A"][T0] == pytest.approx(0.0024)

    def test_trailing_uses_only_prior_days(self):
        daily = C.daily_funding(_hourly({"A": 0.0001}, 10))
        daily["A"][T0 + 5 * DAY] = 1.0        # today's value must not count
        assert C.trailing(daily["A"], T0 + 5 * DAY, 3) == pytest.approx(0.0024)

    def test_trailing_needs_enough_history(self):
        assert C.trailing({T0: 0.001}, T0 + 10 * DAY, 7) is None


class TestSimulate:
    def test_holds_the_best_payer_and_collects_its_funding(self):
        fund = _hourly({"A": 0.0002, "B": 0.00001, "C": -0.0001}, 40)
        daily = C.daily_funding(fund)
        rule = C.CarryRule(top_n=1, lookback=7, enter_min=0.0001, exit_min=0.0)
        res = C.simulate(daily, rule, T0 + 15 * DAY, T0 + 40 * DAY, round_trip=0.01)
        r = res[2024]
        assert r["entries"] == 1
        assert r["fees"] == pytest.approx(0.01)
        assert r["gross"] == pytest.approx(25 * 0.0002 * 24)
        assert r["utilisation"] == pytest.approx(1.0)

    def test_nothing_held_when_no_coin_clears_the_entry_bar(self):
        daily = C.daily_funding(_hourly({"A": 0.000001}, 30))
        res = C.simulate(daily, C.CarryRule(enter_min=0.001), T0 + 15 * DAY, T0 + 30 * DAY)
        assert res[2024]["entries"] == 0 and res[2024]["net"] == 0.0

    def test_exit_when_recent_funding_turns_negative(self):
        fund = _hourly({"A": 0.0002}, 40)
        for f in fund["A"]:
            if f.ts >= T0 + 25 * DAY:
                f.rate = -0.0002
        daily = C.daily_funding(fund)
        rule = C.CarryRule(top_n=1, lookback=7, enter_min=0.0001, exit_lookback=3, exit_min=0.0)
        res = C.simulate(daily, rule, T0 + 15 * DAY, T0 + 40 * DAY, round_trip=0.0)
        # held from day 15 through the first negative days, then exited
        assert res[2024]["utilisation"] < 0.7
        assert res[2024]["gross"] > 0

    def test_fees_are_charged_per_slot_share(self):
        fund = _hourly({"A": 0.0002, "B": 0.0002, "C": 0.0002}, 30)
        daily = C.daily_funding(fund)
        res = C.simulate(daily, C.CarryRule(top_n=3, enter_min=0.0001), T0 + 15 * DAY,
                         T0 + 30 * DAY, round_trip=0.03)
        assert res[2024]["entries"] == 3
        assert res[2024]["fees"] == pytest.approx(0.03)   # 3 x 0.03/3

    def test_sweep_ranks_by_worst_year(self):
        fund = _hourly({"A": 0.0003, "B": 0.0001}, 400)
        rows = C.sweep(C.daily_funding(fund), T0 + 15 * DAY, T0 + 400 * DAY)
        worsts = [r[0] for r in rows]
        assert worsts == sorted(worsts, reverse=True)
        assert "top" in str(rows[0][4])


class TestTradeLog:
    def test_records_entry_exit_and_funding_per_trade(self):
        fund = _hourly({"A": 0.0002}, 40)
        for f in fund["A"]:
            if f.ts >= T0 + 25 * DAY:
                f.rate = -0.0002
        daily = C.daily_funding(fund)
        trades = []
        rule = C.CarryRule(top_n=1, lookback=7, enter_min=0.0001, exit_lookback=3, exit_min=0.0)
        C.simulate(daily, rule, T0 + 15 * DAY, T0 + 40 * DAY, round_trip=0.0, trades=trades)
        t = trades[0]
        assert t["coin"] == "A" and t["entry"] == T0 + 15 * DAY
        assert t["exit"] > T0 + 25 * DAY and not t.get("open")
        held_days = (t["exit"] - t["entry"]) // DAY
        assert t["funding"] == pytest.approx(10 * 0.0048 - (held_days - 10) * 0.0048)

    def test_open_positions_are_logged_at_the_end(self):
        daily = C.daily_funding(_hourly({"A": 0.0002}, 30))
        trades = []
        C.simulate(daily, C.CarryRule(top_n=1, enter_min=0.0001), T0 + 15 * DAY,
                   T0 + 30 * DAY, trades=trades)
        assert trades == [{"coin": "A", "entry": T0 + 15 * DAY, "exit": T0 + 30 * DAY,
                           "funding": pytest.approx(15 * 0.0048), "open": True}]


class TestRender:
    def test_render_lists_years(self):
        fund = _hourly({"A": 0.0002}, 30)
        daily = C.daily_funding(fund)
        rule = C.CarryRule(top_n=1, enter_min=0.0001)
        text = C.render(rule, C.simulate(daily, rule, T0 + 15 * DAY, T0 + 30 * DAY))
        assert "2024" in text and "net positive" in text


class TestGuardAndCapital:
    def _bars(self, highs, opens=None, start=T0):
        from cryptobot.backtest import Candle
        opens = opens or [1.0] * len(highs)
        return {start + i * DAY: Candle(ts=start + i * DAY, open=opens[i], high=h, low=0.9,
                                        close=1.0, volume_usd=1.0)
                for i, h in enumerate(highs)}

    def _trade(self):
        return {"coin": "A", "entry": T0 + DAY, "exit": T0 + 6 * DAY, "funding": 0.0}

    def test_liquidation_level(self):
        assert C.liquidation_rise(1) == pytest.approx(0.975)
        assert C.liquidation_rise(2) == pytest.approx(0.475)

    def test_guard_exits_before_liquidation(self):
        bars = {"A": self._bars([1.0, 1.0, 1.6, 1.0, 1.0, 1.0, 1.0])}
        daily = {"A": {T0 + k * DAY: 0.01 for k in range(10)}}
        (t,) = C.guard_trades([self._trade()], bars, 0.5, 1.0, daily, 0.005)
        assert t["status"] == "guarded" and t["exit"] == T0 + 2 * DAY
        assert t["net"] == pytest.approx(0.01 - 0.005)          # one day of funding

    def test_a_day_through_liquidation_is_a_liquidation_without_a_guard(self):
        bars = {"A": self._bars([1.0, 1.0, 2.1, 1.0, 1.0, 1.0, 1.0])}
        (t,) = C.guard_trades([self._trade()], bars, None, 1.0, {}, 0.0)
        assert t["status"] == "liquidated"

    def test_same_day_guard_and_liquidation_counts_as_liquidation(self):
        # conservative: the day could have jumped straight through both
        bars = {"A": self._bars([1.0, 1.0, 2.1, 1.0, 1.0, 1.0, 1.0])}
        (t,) = C.guard_trades([self._trade()], bars, 0.5, 1.0, {}, 0.0)
        assert t["status"] == "liquidated"

    def test_opening_past_the_guard_but_below_liquidation_is_guarded(self):
        bars = {"A": self._bars([1.0, 1.0, 2.1, 1.0, 1.0, 1.0, 1.0],
                                opens=[1.0, 1.0, 1.6, 1.0, 1.0, 1.0, 1.0])}
        (t,) = C.guard_trades([self._trade()], bars, 0.5, 1.0, {}, 0.0)
        assert t["status"] == "guarded"

    def test_return_on_capital_halves_notional_yield_at_1x(self):
        trades = [{"entry": T0 + DAY, "net": 0.30}]
        start, end = T0, T0 + 365 * DAY
        oc1 = C.on_capital(trades, 1.0, 1, start, end)
        oc3 = C.on_capital(trades, 3.0, 1, start, end)
        (y,) = oc1
        assert oc1[y] == pytest.approx(0.15, rel=0.05)
        assert oc3[y] == pytest.approx(0.30 * 0.75, rel=0.05)
