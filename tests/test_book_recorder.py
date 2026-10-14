import asyncio

import pytest

from cryptobot import book_recorder as B


def _book(mid=10.0):
    asks = [[f"{mid * (1 + bp / 1e4):.4f}", "100"] for bp in (5, 15, 30, 45, 80)]
    bids = [[f"{mid * (1 - bp / 1e4):.4f}", "200"] for bp in (5, 15, 30, 45, 80)]
    return {"asks": list(reversed(asks)), "bids": list(reversed(bids))}       # far-to-near, as Kalshi sends them


def test_reduce_book_bands_and_imbalance():
    r = B.reduce_book(_book(), contract_units=100.0)
    assert r["bid"] < r["mid"] < r["ask"] and 9 < r["spread_bp"] < 11
    assert r["bid_10"] == 200 and r["ask_10"] == 100 and r["imb_10"] == pytest.approx(1 / 3)
    assert r["bid_25"] == 400 and r["ask_25"] == 200
    assert r["bid_50"] == 800 and r["ask_50"] == 400
    assert r["bid_usd_25"] == pytest.approx(400 * r["mid"]) and r["units"] == 100.0
    assert B.reduce_book({"asks": [], "bids": [["1", "1"]]}) is None
    assert B.reduce_book({"asks": [["9", "1"]], "bids": [["10", "1"]]}) is None   # crossed


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append(url)

        class R:
            status_code = 200

            def __init__(self, b):
                self._b = b

            def json(self):
                return self._b
        if url.endswith("/orderbook"):
            return R({"orderbook": _book()})
        if url.endswith("/markets/BAD"):
            R.status_code = 500
            return R({})
        return R({"market": {"price": "10.01", "open_interest": "500", "contract_size": "100", "reference_price": {"price": "9.99"}}})

    async def aclose(self):
        pass


def test_recorder_writes_daily_files_and_refreshes_market_once_a_minute(tmp_path):
    clock = {"t": 1_791_900_000.0}
    fake = FakeClient()
    rec = B.BookRecorder(tmp_path, tickers=("KXDOGEPERP",), interval_s=15, client=fake, now=lambda: clock["t"])
    rows = asyncio.run(rec.run_once())
    r = rows["KXDOGEPERP"]
    assert r["ticker"] == "KXDOGEPERP" and r["last"] == 10.01 and r["oi"] == 500 and r["basis_bp"] == pytest.approx((r["mid"] / 9.99 - 1) * 1e4)
    clock["t"] += 15
    asyncio.run(rec.run_once())
    assert sum(1 for u in fake.calls if u.endswith("/markets/KXDOGEPERP")) == 1   # market read once within the minute
    clock["t"] += 60
    asyncio.run(rec.run_once())
    assert sum(1 for u in fake.calls if u.endswith("/markets/KXDOGEPERP")) == 2
    st = B.status(tmp_path)
    assert st["KXDOGEPERP"]["rows"] == 3 and st["KXDOGEPERP"]["days"] == 1
    assert "KXDOGEPERP" in B.render(st)
    bad = B.BookRecorder(tmp_path, tickers=("BAD",), client=fake, now=lambda: clock["t"])
    assert asyncio.run(bad.run_once()) == {"BAD": None} and bad.errors == 1
