"""Polymarket Up/Down study: fees, fair value, DMI, fills, and parsing."""

import json
import math

import pytest

from cryptobot import updown_study as U
from cryptobot.updown_data import UpDownMarket, parse_event

T0 = 1_790_000_100


class TestCosts:
    def test_fee_matches_polymarket_docs_example(self):
        # docs: 100 shares at $0.50 -> $1.75 fee
        assert 100 * U.fee(0.5) == pytest.approx(1.75)

    def test_fee_vanishes_at_the_extremes(self):
        assert U.fee(0.99) < U.fee(0.9) < U.fee(0.5)

    def test_taker_cost_adds_spread_then_fee(self):
        q = 0.55 + U.HALF_SPREAD
        assert U.taker_cost(0.55) == pytest.approx(q + 0.07 * q * (1 - q))


class TestFairValue:
    def test_at_the_open_it_is_a_coin_flip(self):
        assert U.fair_value(100.0, 100.0, 0.001, 10) == pytest.approx(0.5)

    def test_above_the_open_favours_up_and_more_so_with_less_time(self):
        early = U.fair_value(100.0, 100.1, 0.001, 10)
        late = U.fair_value(100.0, 100.1, 0.001, 1)
        assert 0.5 < early < late

    def test_matches_the_normal_cdf(self):
        z = math.log(101 / 100) / (0.002 * math.sqrt(4))
        assert U.fair_value(100, 101, 0.002, 4) == pytest.approx(U.phi(z))

    def test_expiry_is_the_outcome(self):
        assert U.fair_value(100, 100, 0.001, 0) == 1.0
        assert U.fair_value(100, 99.9, 0.001, 0) == 0.0


def _candles(closes, start=T0 - 200 * 60, spread=0.0):
    out = {}
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        out[start + i * 60] = (o, max(o, c) + spread, min(o, c) - spread, c, 1.0)
    return out


class TestInputs:
    def test_quote_after_is_the_first_print_after_the_decision(self):
        h = [(T0, 0.4), (T0 + 60, 0.6), (T0 + 120, 0.9)]
        assert U.quote_after(h, T0) == (T0 + 60, 0.6)
        assert U.quote_after(h, T0 + 60) == (T0 + 120, 0.9)
        assert U.quote_after(h, T0 + 120) is None
        assert U.quote_after([(T0, 0.4), (T0 + 500, 0.6)], T0, within=120) is None

    def test_snapshot_model_never_knows_more_than_the_quote(self):
        # BTC jumps between the stale quote and the decision time: the
        # information-test model must not see the jump; the trading model may,
        # but then it trades at the next quote, which has seen it too.
        from cryptobot.updown_data import UpDownMarket
        start, end = T0, T0 + 900
        closes = [100.0] * 260
        jump_at = (end - 5 * 60 - 60 - (start - 200 * 60)) // 60    # candle ending at t
        for i in range(jump_at, 260):
            closes[i] = 101.0
        candles = _candles(closes, start=start - 200 * 60)
        hist = [(end - 5 * 60 - 100, 0.5), (end - 5 * 60 + 20, 0.9)]
        m = UpDownMarket("s", start, end, "u", "d", True, history=hist)
        (row,) = U.snapshots({"markets": {"s": m}, "candles": {"BTC-USD": candles}}, 5)
        assert row["price"] == 0.5 and row["entry"] == 0.9
        assert row["model_info"] == pytest.approx(0.5, abs=0.01)
        assert row["model"] > 0.9

    def test_price_at_takes_the_last_quote_not_a_future_one(self):
        h = [(T0, 0.4), (T0 + 60, 0.6), (T0 + 120, 0.9)]
        assert U.price_at(h, T0 + 90) == 0.6
        assert U.price_at(h, T0 - 10) is None
        assert U.price_at(h, T0 + 1000) is None          # stale

    def test_spot_is_the_close_of_the_candle_ending_at_t(self):
        c = _candles([100, 101, 102], start=T0)
        assert U.spot(c, T0 + 120) == 101                # candle T0+60 closes at T0+120

    def test_realized_vol_of_a_flat_series_is_zero(self):
        c = _candles([100.0] * 200)
        assert U.realized_vol(c, T0 - 30 * 60) == pytest.approx(0.0)


class TestDMI:
    def test_steady_uptrend_has_plus_di_dominant_and_strong_adx(self):
        c = _candles([100 + i * 0.5 for i in range(200)], spread=0.1)
        pdi, ndi, adx = U.dmi(c, T0)
        assert pdi > ndi and adx > 25

    def test_steady_downtrend_mirrors_it(self):
        c = _candles([200 - i * 0.5 for i in range(200)], spread=0.1)
        pdi, ndi, adx = U.dmi(c, T0)
        assert ndi > pdi and adx > 25

    def test_choppy_series_has_weak_adx(self):
        c = _candles([100 + (0.5 if i % 2 else -0.5) for i in range(200)], spread=0.1)
        assert U.dmi(c, T0)[2] < 20

    def test_too_little_history_is_none(self):
        assert U.dmi(_candles([100.0] * 10, start=T0 - 600), T0) is None


def _row(price=0.5, model=0.5, up=1, history=None, dmi=None, day="2026-09-21"):
    return {"slug": "s", "start": T0, "end": T0 + 900, "t": T0 + 300, "day": day,
            "price": price, "model": model, "model_info": model, "entry": price,
            "entry_ts": T0 + 300, "dmi": dmi, "up": up,
            "history": history or [(T0 + 300, price)]}


class TestStrategies:
    def test_taker_buys_the_side_the_model_prefers(self):
        r = _row(price=0.40, model=0.70, up=1)
        (t,) = U.taker_trades([r], edge=0.0)
        assert t["side_up"] and t["pnl"] == pytest.approx(1 - U.taker_cost(0.40))

    def test_taker_skips_when_the_edge_does_not_cover_costs(self):
        assert U.taker_trades([_row(price=0.50, model=0.52)], edge=0.0) == []

    def test_down_side_uses_the_complement_price(self):
        (t,) = U.taker_trades([_row(price=0.70, model=0.30, up=0)], edge=0.0)
        assert not t["side_up"] and t["cost"] == pytest.approx(U.taker_cost(0.30))

    def test_hedge_locks_when_the_pair_costs_under_a_dollar(self):
        hist = [(T0 + 300, 0.40), (T0 + 400, 0.80)]     # Up rallies, Down gets cheap
        r = _row(price=0.40, model=0.70, up=0, history=hist)
        (t,) = U.with_hedge(U.taker_trades([r], edge=0.0))
        expected = 1 - U.taker_cost(0.40) - U.taker_cost(0.20)
        assert t["locked"] and t["pnl"] == pytest.approx(expected) and expected > 0

    def test_a_small_favourable_move_already_locks_a_sliver(self):
        # Up 40c -> 45c: Down now costs ~57c all-in, the pair ~99.4c: locked
        r = _row(price=0.40, model=0.70, up=1, history=[(T0 + 300, 0.40), (T0 + 400, 0.45)])
        (t,) = U.with_hedge(U.taker_trades([r], edge=0.0))
        assert t["locked"] and 0 < t["pnl"] < 0.01

    def test_hedge_does_nothing_when_price_moves_against_the_entry(self):
        r = _row(price=0.40, model=0.70, up=1, history=[(T0 + 300, 0.40), (T0 + 400, 0.35)])
        (t,) = U.with_hedge(U.taker_trades([r], edge=0.0))
        assert not t["locked"] and t["pnl"] == pytest.approx(1 - U.taker_cost(0.40))

    def test_maker_fills_only_when_price_trades_through_the_bid(self):
        hist = [(T0 + 300, 0.50), (T0 + 360, 0.47), (T0 + 420, 0.55)]
        r = _row(price=0.50, model=0.55, up=1, history=hist)
        (t,) = [x for x in U.maker_trades([r], margin=0.07) if x["side_up"]]
        assert t["cost"] == pytest.approx(0.48) and t["pnl"] == pytest.approx(0.52)
        none = _row(price=0.50, model=0.55, up=1, history=[(T0 + 300, 0.50), (T0 + 360, 0.49)])
        assert not [x for x in U.maker_trades([none], margin=0.07) if x["side_up"]]

    def test_maker_never_bids_above_the_market(self):
        r = _row(price=0.40, model=0.70, history=[(T0 + 300, 0.40), (T0 + 360, 0.30)])
        assert not [x for x in U.maker_trades([r], margin=0.0) if x["side_up"]]

    def test_dmi_rule_follows_the_dominant_index_above_adx_25(self):
        rows = [_row(price=0.5, up=1, dmi=(30.0, 10.0, 30.0)),
                _row(price=0.5, up=1, dmi=(10.0, 30.0, 30.0)),
                _row(price=0.5, up=1, dmi=(30.0, 10.0, 15.0))]
        t = U.dmi_trades(rows)
        assert [x["side_up"] for x in t] == [True, False]
        assert [x["hit"] for x in t] == [1, 0]


class TestStats:
    def test_summary_counts_days_and_per_dollar(self):
        tr = [{"pnl": 0.4, "cost": 0.6, "day": "a"}, {"pnl": -0.5, "cost": 0.5, "day": "b"}]
        s = U.summary(tr)
        assert s["per_dollar"] == pytest.approx(-0.1 / 1.1) and s["days_up"] == 1

    def test_logistic_recovers_a_clear_signal(self):
        X = [[x / 10] for x in range(-50, 51)] * 3
        y = [1 if x[0] > 0 else 0 for x in X]
        w = U.fit_logistic(X, y, steps=2000, lr=0.5)
        assert w[1] > 1

    def test_choose_picks_on_half_one_only(self):
        tr = [_row(price=0.40, model=0.70, up=1)] * 40
        te = [_row(price=0.40, model=0.70, up=0)] * 40
        g, s_tr, s_te = U.choose(tr, te, U.taker_trades, (0.0, 0.5))
        assert g == 0.0 and s_tr["per_dollar"] > 0 > s_te["per_dollar"]


class TestParse:
    def test_parse_event_maps_outcomes_to_tokens(self):
        ev = {"slug": "btc-updown-15m-1", "markets": [{
            "outcomes": json.dumps(["Down", "Up"]), "clobTokenIds": json.dumps(["d", "u"]),
            "outcomePrices": json.dumps(["0", "1"]), "closed": True,
            "eventStartTime": "2026-09-21T14:15:00Z", "endDate": "2026-09-21T14:30:00Z",
            "volumeNum": 123.0}]}
        m = parse_event(ev)
        assert (m.up_token, m.down_token, m.up_won) == ("u", "d", True)
        assert m.end - m.start == 900

    def test_unresolved_or_malformed_events(self):
        ev = {"slug": "x", "markets": [{
            "outcomes": json.dumps(["Up", "Down"]), "clobTokenIds": json.dumps(["u", "d"]),
            "outcomePrices": json.dumps(["0.5", "0.5"]), "closed": False,
            "eventStartTime": "2026-09-21T14:15:00Z", "endDate": "2026-09-21T14:30:00Z"}]}
        assert parse_event(ev).up_won is None
        assert parse_event({"markets": [{}]}) is None


def test_load_resolves_caches_written_as_main(tmp_path):
    import pickle, sys, types
    from cryptobot import updown_data as D
    fake = types.ModuleType("__fake_main__")
    cls = type("UpDownMarket", (), {})
    cls.__module__ = "__fake_main__"
    fake.UpDownMarket = cls
    sys.modules["__fake_main__"] = fake
    try:
        obj = cls()
        obj.__dict__.update(D.UpDownMarket("s", 1, 2, "u", "d", True).__dict__)
        (tmp_path / "c.pkl").write_bytes(pickle.dumps({"markets": {"s": obj}}))
    finally:
        del sys.modules["__fake_main__"]
    m = D.load(tmp_path / "c.pkl")["markets"]["s"]
    assert isinstance(m, D.UpDownMarket) and m.up_token == "u"
