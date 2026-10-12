import asyncio
import datetime as dt
import json
import math

import pytest

from cryptobot import oos_track as T
from cryptobot import vrp_collect as V


def _hourly(days: list[dt.date], px: dict[dt.date, float]) -> dict:
    """A 16:00 ET bar for each day with the given price (open == close)."""
    out = {}
    for d in days:
        ts = int(dt.datetime(d.year, d.month, d.day, 16, tzinfo=T.ET).timestamp())
        out[ts] = (px[d], px[d])
    return out


def test_classify_threshold_both_ways():
    assert T.classify(0.01, -0.01) == "stocks up, BTC down"
    assert T.classify(-0.01, 0.02) == "stocks down, BTC up"
    assert T.classify(0.01, 0.01) is None and T.classify(0.004, -0.01) is None


def test_build_rows_uses_prior_session_and_next_day_print():
    d0, d1, d2, d3 = (dt.date(2026, 10, 9) + dt.timedelta(days=i) for i in (0, 3, 4, 5))  # Fri, Mon, Tue, Wed
    spx = {d0: 100.0, d1: 101.0, d2: 100.0}
    px = {d0: 100.0, d1: 99.0, d2: 99.5, d3: 101.0}
    hourly = _hourly([d0, d1, d2, d3], px)
    rows = T.build_rows(spx, hourly, start=dt.date(2026, 10, 10))
    assert [r["day"] for r in rows] == [d1.isoformat(), d2.isoformat()]
    r1, r2 = rows
    assert r1["spx"] == pytest.approx(math.log(1.01)) and r1["btc"] == pytest.approx(math.log(0.99))
    assert r1["kind"] == "stocks up, BTC down" and r1["btc_next24"] == pytest.approx(math.log(99.5 / 99.0))
    assert r2["kind"] == "stocks down, BTC up" and r2["btc_next24"] == pytest.approx(math.log(101.0 / 99.5))
    # without tomorrow's print the row is pending
    rows = T.build_rows(spx, {k: v for k, v in hourly.items() if k != max(hourly)}, start=dt.date(2026, 10, 10))
    assert rows[-1]["btc_next24"] is None


def test_merge_completes_pending_rows_and_keeps_history():
    old = [{"day": "2026-10-13", "kind": "stocks up, BTC down", "btc_next24": None},
           {"day": "2026-10-10", "kind": None, "btc_next24": 0.01}]
    fresh = [{"day": "2026-10-13", "kind": "stocks up, BTC down", "btc_next24": 0.004},
             {"day": "2026-10-14", "kind": None, "btc_next24": None}]
    out = T.merge(old, fresh)
    assert [r["day"] for r in out] == ["2026-10-10", "2026-10-13", "2026-10-14"]
    assert out[1]["btc_next24"] == 0.004
    # a completed row is not overwritten by a later refetch
    again = T.merge(out, [{"day": "2026-10-13", "kind": "stocks up, BTC down", "btc_next24": 0.009}])
    assert again[1]["btc_next24"] == 0.004


def test_summary_counts_and_decides_only_at_the_target():
    rows = [{"day": f"2026-{m:02d}-01", "kind": "stocks up, BTC down", "btc_next24": 0.005} for m in range(1, 13)]
    s = T.summary(rows, target_days=60)
    assert s["qualifying"]["n"] == 12 and s["verdict"] == "collecting" and not s["decided"]
    many = [{"day": f"d{i}", "kind": "stocks up, BTC down", "btc_next24": 0.004 + 0.001 * (i % 3)} for i in range(60)]
    s = T.summary(many, target_days=60)
    assert s["decided"] and s["verdict"] == "alive" and s["qualifying"]["t"] > 2
    bad = [{"day": f"d{i}", "kind": "stocks up, BTC down", "btc_next24": -0.001} for i in range(60)]
    assert T.summary(bad, target_days=60)["verdict"] == "killed"
    assert T.summary([])["verdict"] == "collecting"


class FakeHttp:
    def __init__(self, fred_text, candles):
        self.fred_text, self.candles = fred_text, candles

    async def get(self, url, params=None):
        class R:
            def __init__(self, status, text="", body=None):
                self.status_code, self.text, self._b = status, text, body

            def json(self):
                return self._b
        if "fred" in url:
            return R(200, text=self.fred_text)
        return R(200, body=self.candles)

    async def aclose(self):
        pass


def test_update_writes_rows_and_status_reads_them(tmp_path):
    today = dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(6, -1, -1)]
    fred = "observation_date,SP500\n" + "\n".join(f"{d.isoformat()},{100 + i}" for i, d in enumerate(days))
    candles = []
    for i, d in enumerate(days):
        ts = int(dt.datetime(d.year, d.month, d.day, 16, tzinfo=T.ET).timestamp())
        candles.append([ts, 1, 1, 100 - i, 100 - i, 1])          # BTC falls while S&P rises
    s = asyncio.run(T.update(tmp_path, client=FakeHttp(fred, candles)))
    rows = T.read_rows(tmp_path)
    assert rows and s["days_tracked"] == len(rows)
    assert all(r["kind"] in ("stocks up, BTC down", None) for r in rows)
    st = V.status(tmp_path)
    assert st["divergence_oos"]["days_tracked"] == len(rows) and st["options"]["days"] == 0
    assert "divergence tracker" in T.render(rows)


def test_status_summarises_collector_files(tmp_path):
    V.append_jsonl(tmp_path / "options" / "ibit.jsonl",
                   {"date": "2026-10-12", "spot": 46.6, "iv30_atm": 0.366, "rv20": 0.375, "iv_minus_rv20": -0.009, "gate_open": False})
    V.append_jsonl(tmp_path / "kalshi_hourly" / "KXBTCPERP.jsonl", {"end_ts": 1_791_830_400, "close": 8.5})
    st = V.status(tmp_path)
    assert st["options"]["days"] == 1 and st["options"]["gate_open"] is False and st["options"]["gated_days"] == 1
    assert st["kalshi_hourly"]["KXBTCPERP"]["rows"] == 1 and st["kalshi_hourly"]["KXBTCPERP"]["last"].startswith("2026-10-12")
    assert st["divergence_oos"]["verdict"] == "collecting"
