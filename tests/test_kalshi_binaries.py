import asyncio
import datetime as dt
import random

import pytest

from cryptobot import binary_tails_study as T
from cryptobot import kalshi_binaries as K


def _market(ticker, event, close_ts, result, volume=10.0, strike=80000.0):
    return {"ticker": ticker, "event_ticker": event, "strike_type": "greater", "floor_strike": strike,
            "open_time": dt.datetime.fromtimestamp(close_ts - 3600, dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "close_time": dt.datetime.fromtimestamp(close_ts, dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "result": result, "expiration_value": "82349.50", "volume_fp": f"{volume:.2f}"}


class FakeKalshi:
    """Two pages of settled markets, one 429 on the first candles call."""

    def __init__(self, pages, candles):
        self.pages, self.candles = pages, candles
        self.calls, self._throttled = [], False

    async def get(self, url, params=None):
        self.calls.append((url, params))

        class R:
            def __init__(self, code, body):
                self.status_code, self._b = code, body

            def json(self):
                return self._b
        if url.endswith("/markets"):
            i = int(params.get("cursor") or 0)
            body = {"markets": self.pages[i], "cursor": str(i + 1) if i + 1 < len(self.pages) else None}
            return R(200, body)
        if "candlesticks" in url:
            if not self._throttled:
                self._throttled = True
                return R(429, {"error": "too_many_requests"})
            return R(200, {"candlesticks": self.candles})

    async def aclose(self):
        pass


def test_collector_lists_traded_settled_markets_and_fetches_candles_resumably(tmp_path):
    now = 1_791_856_800
    pages = [[_market("KXBTCD-A-T1", "KXBTCD-A", now, "yes"), _market("KXBTCD-A-T2", "KXBTCD-A", now, "no", volume=0.0)],
             [_market("KXBTCD-B-T1", "KXBTCD-B", now - 3600, "no"), _market("KXBTCD-OLD-T1", "KXBTCD-OLD", now - 40 * 86400, "no")]]
    candles = [{"end_period_ts": now - 3600 + 60 * i, "yes_bid": {"close_dollars": "0.9000"}, "yes_ask": {"close_dollars": "0.9300"},
                "price": {"close_dollars": "0.9100"} if i % 2 else {}, "volume_fp": "3.00"} for i in range(61)]
    fake = FakeKalshi(pages, candles)
    c = K.KalshiBinaries(tmp_path, client=fake, pace_s=0.0)
    since = dt.datetime.fromtimestamp(now - 30 * 86400, dt.timezone.utc)
    assert asyncio.run(c.list_settled(since)) == 2                       # zero-volume and too-old rows skipped
    ms = c.markets()
    assert [m["ticker"] for m in ms] == ["KXBTCD-A-T1", "KXBTCD-B-T1"]
    assert ms[0]["series"] == "KXBTCD" and ms[0]["settle"] == 82349.5 and ms[0]["close_ts"] - ms[0]["open_ts"] == 3600
    assert asyncio.run(c.list_settled(since)) == 0                       # idempotent
    assert asyncio.run(c.fetch_candles(limit=1)) == 1                    # newest first, survives one 429
    assert c.pace_s > 0.0                                                # slowed down after the 429
    slowed = c.pace_s
    assert c.candles_done() == {"KXBTCD-A-T1"}
    assert asyncio.run(c.fetch_candles()) == 1                           # the other one, no refetch
    assert 0.0 <= c.pace_s < slowed                                      # and eases back toward the base pace
    st = c.status()
    assert st == {"markets": 2, "with_candles": 2, "events": 2, "first": st["first"], "last": st["last"]}
    markets, bars = T.load(tmp_path)
    assert len(markets) == 2 and len(bars["KXBTCD-A-T1"]) == 61
    b = bars["KXBTCD-A-T1"][1]
    assert b[1] == 0.9 and b[2] == 0.93 and b[3] == 0.91 and b[4] == 3.0
    assert bars["KXBTCD-A-T1"][0][3] is None                              # no trade that minute


def _synthetic(n_hours=400, p_win=None, seed=3, spread=0.02):
    """Hourly events with one favourite strike each, quoted at a random
    0.86-0.96 and won with probability `p_win` (None: the implied one)."""
    rng = random.Random(seed)
    markets, bars = [], {}
    t0 = 1_790_000_000
    for h in range(n_hours):
        close = t0 + h * 3600
        yes_px = rng.uniform(0.86, 0.96)
        side_yes = rng.random() < 0.5                                     # favourite quoted as YES or as NO
        prob = yes_px if p_win is None else p_win
        fav_wins = rng.random() < prob
        if side_yes:
            result = "yes" if fav_wins else "no"
            bid, ask = yes_px - spread / 2, yes_px + spread / 2
        else:
            result = "no" if fav_wins else "yes"
            bid, ask = (1 - yes_px) - spread / 2, (1 - yes_px) + spread / 2
        tk = f"KXBTCD-{h}-T1"
        markets.append({"ticker": tk, "event": f"KXBTCD-{h}", "series": "KXBTCD", "strike_type": "greater", "floor": 1.0, "cap": None,
                        "open_ts": close - 3600, "close_ts": close, "result": result, "settle": 1.0, "volume": 5.0})
        last = 1.0 if result == "yes" else 0.0
        bars[tk] = [[close - 3600 + 60 * i, round(bid, 4), round(ask, 4), (round(bid, 4) if i < 55 else last), 1.0] for i in range(1, 61)]
    return markets, bars


def test_quote_at_and_sides():
    bars = [[100, 0.1, 0.12, None, 1.0], [160, 0.9, 0.93, 0.91, 1.0], [220, None, 0.5, None, 0.0]]
    assert T.quote_at(bars, 160) == (0.9, 0.93, 0.91, 1)
    assert T.quote_at(bars, 190) == (0.9, 0.93, 0.91, 1)                 # the last bar within tolerance
    assert T.quote_at(bars, 220) is None                                  # one-sided
    assert T.quote_at(bars, 50) is None
    assert T.favourite(0.9, 0.93) == ("yes", 0.93, pytest.approx(0.915))
    side, price, implied = T.favourite(0.05, 0.08)
    assert side == "no" and price == pytest.approx(0.95) and implied == pytest.approx(0.935)
    assert T.favourite(0.4, 0.5) is None
    assert T.longshot(0.05, 0.08) == ("yes", 0.08, pytest.approx(0.065))
    side, price, implied = T.longshot(0.9, 0.93)
    assert side == "no" and price == pytest.approx(0.1) and implied == pytest.approx(0.085)
    assert T.fee(0.95) == pytest.approx(0.07 * 0.95 * 0.05)


def test_calibrated_market_loses_the_fee_and_a_biased_one_pays():
    m, b = _synthetic(p_win=None)
    cal = T.summarize(T.trades(m, b, 30))
    assert cal["n"] > 300 and abs(cal["hit"] - cal["implied"]) < 0.04
    assert cal["net"] < 0.01                                              # at best the fee is lost
    m2, b2 = _synthetic(p_win=0.995, seed=5)
    rich = T.summarize(T.trades(m2, b2, 30))
    assert rich["net"] > 0.03 and rich["t"] > 4 and rich["hit"] > rich["implied"] + 0.05
    res = T.run(m2, b2)
    assert res["trials"] == 8 and res["verdict"][0] in ("alive", "inconclusive")
    assert "favourite" in T.render(res) and "verdict:" in T.render(res)
    # the longshot mirror of a biased favourite loses
    assert T.summarize(T.trades(m2, b2, 30, "longshot", T.LONG_LO, T.LONG_HI))["net"] < 0
    # killed when the favourite loses at both decision times
    m3, b3 = _synthetic(p_win=0.80, seed=7)
    assert T.run(m3, b3)["verdict"][0] == "killed"


def test_maker_fill_needs_a_print_through_the_bid():
    m, b = _synthetic(n_hours=60, p_win=None, seed=9)
    mk = T.trades(m, b, 30, "maker")
    taker = T.trades(m, b, 30, "favourite")
    assert 0 < len(mk) < len(taker)                                       # only the markets whose last trade went through
    assert all(t["net"] != 0 for t in mk)
    # a market whose trades never cross the bid is never filled
    one_m, one_b = _synthetic(n_hours=1, p_win=None, seed=1)
    tk = one_m[0]["ticker"]
    for bar in one_b[tk]:
        bar[3] = bar[1] + 0.005                                           # prints sit inside the spread the whole hour
    assert T.trades(one_m, one_b, 30, "maker") == []


def test_cluster_t_shrinks_with_shared_shocks():
    rng = random.Random(2)
    xs = [rng.gauss(0.01, 0.05) for _ in range(400)]
    iid = T.cluster_t(xs, list(range(400)))
    shared = T.cluster_t([x + (0.1 if (i // 20) % 2 else -0.1) for i, x in enumerate(xs)], [i // 20 for i in range(400)])
    assert abs(shared) < abs(iid)
    assert T.cluster_t([1.0, 1.0], [0, 1]) == 0.0
