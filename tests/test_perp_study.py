"""Tests for the Hyperliquid client parsing and the multi-year perp study."""

import asyncio
import datetime as dt
import json

import httpx
import pytest

from cryptobot.backtest import Candle, PoolMeta
from cryptobot.data.hyperliquid import HyperliquidClient, Funding, TAKER_FEE
from cryptobot.research import Barrier
from cryptobot import perp_study as P

DAY = 86400


def _meta(sym):
    return PoolMeta(chain="hyperliquid", pair_address=sym, symbol=sym,
                    token_address="", liquidity_usd=0.0, fdv_usd=None)


def _pool(sym, closes, start=1_704_067_200, highs=None, lows=None):   # 2024-01-01
    highs = highs or closes
    lows = lows or closes
    return (_meta(sym), [Candle(ts=start + DAY * i, open=c, high=highs[i],
                                low=lows[i], close=c, volume_usd=1000.0)
                         for i, c in enumerate(closes)])


class TestHyperliquidClient:
    def _client(self, handler):
        transport = httpx.MockTransport(handler)
        return HyperliquidClient(client=httpx.AsyncClient(transport=transport))

    def test_candles_parse_and_sort_oldest_first(self):
        def handler(req):
            body = json.loads(req.content)
            assert body["type"] == "candleSnapshot"
            assert body["req"]["coin"] == "kPEPE"
            return httpx.Response(200, json=[
                {"t": 2000_000, "o": "2", "h": "3", "l": "1", "c": "2.5", "v": "10"},
                {"t": 1000_000, "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "20"},
            ])
        hl = self._client(handler)
        out = asyncio.run(hl.candles("kPEPE", "1d"))
        assert [c.ts for c in out] == [1000.0, 2000.0]
        assert out[0].close == 1.5
        assert out[0].volume_usd == pytest.approx(20 * 1.5)   # base volume × price

    def test_zero_close_rows_are_dropped(self):
        def handler(req):
            return httpx.Response(200, json=[
                {"t": 1000, "o": "1", "h": "1", "l": "1", "c": "0", "v": "1"}])
        assert asyncio.run(self._client(handler).candles("X")) == []

    def test_funding_paginates_until_a_short_page(self):
        calls = []

        def handler(req):
            body = json.loads(req.content)
            calls.append(body["startTime"])
            start = body["startTime"]
            n = 500 if len(calls) == 1 else 3
            rows = [{"time": start + i * 3_600_000, "fundingRate": "0.0001",
                     "premium": "0.0"} for i in range(n)]
            return httpx.Response(200, json=rows)
        hl = self._client(handler)
        out = asyncio.run(hl.funding_history("DOGE", start_ms=0))
        assert len(out) == 503
        assert len(calls) == 2
        assert calls[1] == 499 * 3_600_000 + 1        # cursor moves past the last row

    def test_funding_stops_when_cursor_does_not_advance(self):
        def handler(req):
            rows = [{"time": 5, "fundingRate": "0.0001"}] * 500
            return httpx.Response(200, json=rows)
        hl = self._client(handler)
        out = asyncio.run(hl.funding_history("DOGE", start_ms=10, max_calls=50))
        assert len(out) == 500        # one page, no infinite loop

    def test_universe_skips_delisted(self):
        def handler(req):
            return httpx.Response(200, json={"universe": [
                {"name": "DOGE"}, {"name": "OLD", "isDelisted": True}]})
        assert asyncio.run(self._client(handler).universe()) == ["DOGE"]


class TestOutcome:
    bar = Barrier(0.10, 0.05)

    def _o(self, highs, lows, closes, horizon, side):
        return P.outcome(highs, lows, closes, 0, 100.0, self.bar, horizon, side)

    def test_long_target_first_wins_the_target(self):
        assert self._o([100, 100, 111], [100, 100, 100], [100, 100, 105], 5, "long") == (1, 0.10)

    def test_short_is_the_mirror(self):
        h, l, c = [100, 100, 100], [100, 100, 89], [100, 100, 95]
        assert self._o(h, l, c, 5, "short") == (1, 0.10)
        assert self._o(h, l, c, 5, "long")[0] == 0

    def test_stop_first_loses_the_stop(self):
        assert self._o([100, 100], [100, 94], [100, 97], 5, "long") == (0, -0.05)
        assert self._o([100, 106], [100, 100], [100, 103], 5, "short") == (0, -0.05)

    def test_same_candle_touching_both_is_the_stop(self):
        assert self._o([100, 111], [100, 94], [100, 100], 5, "long") == (0, -0.05)
        assert self._o([100, 106], [100, 89], [100, 100], 5, "short") == (0, -0.05)

    def test_stop_hit_earlier_blocks_a_later_target(self):
        assert self._o([100, 106, 100], [100, 100, 80], [100, 103, 85], 5, "short") == (0, -0.05)

    def test_timeout_realizes_the_move_to_horizon_not_the_stop(self):
        h, l, c = [100, 102, 103, 120], [100, 98, 97, 80], [100, 101, 102, 100]
        assert self._o(h, l, c, 2, "long") == (0, pytest.approx(0.02))
        assert self._o(h, l, c, 2, "short") == (0, pytest.approx(-0.02))

    def test_running_off_the_end_uses_the_last_close(self):
        assert self._o([100, 101], [100, 99], [100, 101], 10, "long") == (0, pytest.approx(0.01))


class TestDailyFeatures:
    def test_offsets_and_drawdown(self):
        closes = [100.0] * 40
        closes[-31] = 50.0      # i-30
        closes[-8] = 80.0       # i-7
        closes[-2] = 90.0       # i-1
        closes[-11] = 200.0     # inside the 30d window: the peak
        i = len(closes) - 1
        f = P.daily_features(closes, [1.0] * 40, i)
        assert f["move_30d"] == pytest.approx(1.0)
        assert f["move_7d"] == pytest.approx(0.25)
        assert f["move_1d"] == pytest.approx(100 / 90 - 1)
        assert f["drawdown_30d"] == pytest.approx(-0.5)

    def test_vol_surge_is_one_when_flat(self):
        f = P.daily_features([100.0] * 40, [7.0] * 40, 39)
        assert f["vol_surge_7d"] == pytest.approx(1.0)

    def test_features_ignore_the_future(self):
        closes = [100.0] * 50
        a = P.daily_features(closes, [1.0] * 50, 35)
        closes[40] = 1.0
        assert P.daily_features(closes, [1.0] * 50, 35) == a


class TestCollectAndYears:
    def test_year_is_taken_from_the_entry_candle(self):
        n = P.WARMUP_DAYS + 30
        start = int(dt.datetime(2023, 12, 1, tzinfo=dt.timezone.utc).timestamp())
        pools = {"a": _pool("A", [100.0] * n, start=start)}
        rows = P.collect(pools, Barrier(0.1, 0.05), 7, "long")
        years = {r["year"] for r in rows}
        assert years == {2023, 2024}

    def test_uptrend_wins_long_and_loses_short(self):
        n = P.WARMUP_DAYS + 40
        pools = {"a": _pool("A", [100.0 * 1.03 ** i for i in range(n)])}
        bar = Barrier(0.10, 0.05)
        assert all(r["win"] for r in P.collect(pools, bar, 7, "long"))
        assert not any(r["win"] for r in P.collect(pools, bar, 7, "short"))

    def test_by_year_uses_timestamps_for_the_standard_error(self):
        n = P.WARMUP_DAYS + 40
        import random, statistics
        rng = random.Random(2)
        closes = [100.0]
        for _ in range(n - 1):
            closes.append(closes[-1] * (1 + rng.gauss(0, 0.04)))
        pools = {k: _pool(k, closes) for k in "abcdefgh"}   # 8 identical coins
        bar = Barrier(0.10, 0.05)
        rows = P.collect(pools, bar, 7, "long")
        tab = P.by_year(rows, bar, lambda y: 0.002)
        assert tab[0]["n"] == 8 * tab[0]["days"]
        # se computed from `days`, not `n`: 8× fewer effective observations
        pnl = [r["pnl"] for r in rows if r["year"] == tab[0]["year"]]
        assert tab[0]["se"] == pytest.approx(statistics.pstdev(pnl) / tab[0]["days"] ** 0.5)
        assert tab[0]["se"] > 0


class TestCosts:
    def test_fees_both_ways(self):
        assert P.round_trip_cost(0, 0.0, "long") == pytest.approx(2 * (TAKER_FEE + P.SLIPPAGE))

    def test_longs_pay_positive_funding_and_shorts_receive_it(self):
        base = P.round_trip_cost(0, 0.0, "long")
        assert P.round_trip_cost(4, 0.001, "long") == pytest.approx(base + 0.004)
        assert P.round_trip_cost(4, 0.001, "short") == pytest.approx(base - 0.004)

    def test_funding_by_year_scales_hourly_to_daily(self):
        t = int(dt.datetime(2025, 3, 1, tzinfo=dt.timezone.utc).timestamp())
        funding = {"X": [Funding(ts=t + 3600 * i, rate=0.0001, premium=0.0) for i in range(48)]}
        assert P.funding_by_year(funding) == {2025: pytest.approx(0.0024)}


class TestRuleByYear:
    def test_rules_are_chosen_on_the_first_half_only(self):
        n = P.WARMUP_DAYS + 400
        import random
        rng = random.Random(1)
        pools = {}
        for k in range(6):
            px, closes = 100.0, []
            for _ in range(n):
                px *= 1 + rng.gauss(0, 0.05)
                closes.append(px)
            pools[str(k)] = _pool(f"T{k}", closes)
        bar = Barrier(0.10, 0.05)
        rows = P.collect(pools, bar, 7, "long")
        table = P.rule_by_year(rows, bar, lambda y: 0.002, top_k=3)
        assert len(table) <= 3
        for t in table:
            assert t["years"]
            for c in t["years"].values():
                assert c["n"] >= 30
        text = P.render_rules("long", table)
        assert "yrs+" in text


class TestWalkForward:
    def _rows(self, years, per_year=400, seed=0):
        import random
        rng = random.Random(seed)
        rows = []
        for y in years:
            t0 = int(dt.datetime(y, 1, 1, tzinfo=dt.timezone.utc).timestamp())
            for i in range(per_year):
                a, b = rng.random(), rng.random()
                # rule cell (a high, b low) wins; everything else loses
                good = a > 0.66 and b < 0.34
                rows.append({"ts": t0 + i * 3600 * 6, "year": y, "symbol": f"S{i % 5}",
                             "fa": a, "fb": b, "win": int(good),
                             "pnl": 0.05 if good else -0.01})
        rows.sort(key=lambda r: r["ts"])
        return rows

    def test_parse_rule(self):
        assert P.parse_rule("move_7d[2] & rvol_7d[1]") == (("move_7d", 2), ("rvol_7d", 1))
        assert P.parse_rule("a[0]&b[2]") == (("a", 0), ("b", 2))
        with pytest.raises(ValueError):
            P.parse_rule("a[0]")

    def test_first_years_are_only_used_for_fitting(self):
        rows = self._rows([2021, 2022, 2023, 2024])
        table = P.walk_forward_rule(rows, (("fa", 2), ("fb", 0)), lambda y: 0.002)
        assert [r["year"] for r in table] == [2023, 2024]
        assert table[0]["fit_n"] == 800 and table[1]["fit_n"] == 1200

    def test_rule_beats_benchmark_when_the_cell_is_the_edge(self):
        rows = self._rows([2021, 2022, 2023, 2024])
        table = P.walk_forward_rule(rows, (("fa", 2), ("fb", 0)), lambda y: 0.002)
        for r in table:
            assert r["net"] > 0.04
            assert r["bench"] < 0
            assert r["lift"] > 0

    def test_cost_is_charged_per_year(self):
        rows = self._rows([2021, 2022, 2023])
        cheap = P.walk_forward_rule(rows, (("fa", 2), ("fb", 0)), lambda y: 0.0)
        dear = P.walk_forward_rule(rows, (("fa", 2), ("fb", 0)), lambda y: 0.01)
        assert cheap[0]["net"] - dear[0]["net"] == pytest.approx(0.01)

    def test_render_summarises(self):
        rows = self._rows([2021, 2022, 2023])
        table = P.walk_forward_rule(rows, (("fa", 2), ("fb", 0)), lambda y: 0.002)
        text = P.render_walk_forward("short", Barrier(0.1, 0.05), (("fa", 2), ("fb", 0)), table)
        assert "beats benchmark" in text and "trade-weighted" in text
