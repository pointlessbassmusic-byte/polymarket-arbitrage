import asyncio
import datetime as dt
import json
import random

import pytest

from cryptobot import pead_collect as C
from cryptobot import pead_study as P


def test_money_and_number_parsing():
    assert C._money("$1.72") == 1.72 and C._money("($0.13)") == -0.13 and C._money("") is None
    assert C._money("$54,036,886,000") == 54_036_886_000.0 and C._money("N/A") is None
    assert C._num("-4.44") == -4.44 and C._num("N/A") is None and C._num("7") == 7.0


def test_parse_calendar_and_history():
    payload = {"data": {"rows": [
        {"symbol": "DAL", "name": "Delta", "eps": "$1.72", "epsForecast": "$1.80", "surprise": "-4.44",
         "noOfEsts": "7", "marketCap": "$54,036,886,000", "time": "time-not-supplied", "fiscalQuarterEnding": "Sep/2026"},
        {"symbol": "bad symbol!", "eps": "$1"},
        {"symbol": "HIFS", "eps": "$3.86", "epsForecast": "", "surprise": "N/A", "noOfEsts": "N/A", "marketCap": "$619"}]}}
    rows = C.parse_calendar(payload, dt.date(2026, 10, 9))
    assert [r["symbol"] for r in rows] == ["DAL", "HIFS"]
    assert rows[0]["surprise_pct"] == -4.44 and rows[0]["n_est"] == 7 and rows[0]["market_cap"] == 54_036_886_000.0
    assert rows[1]["surprise_pct"] is None and rows[1]["n_est"] == 0
    hist = C.parse_history({"data": {"tradesTable": {"rows": [
        {"date": "10/09/2026", "close": "$46.55", "open": "$46.93", "high": "$47", "low": "$46", "volume": "1,000"},
        {"date": "10/08/2026", "close": "$46.00", "open": "$0"}]}}})
    assert len(hist) == 1 and hist[0]["date"] == "2026-10-09" and hist[0]["volume"] == 1000.0


class FakeHttp:
    def __init__(self, cal_rows_by_date, hist_rows):
        self.cal, self.hist, self.calls = cal_rows_by_date, hist_rows, []

    async def get(self, url, params=None):
        self.calls.append((url, params))

        class R:
            status_code = 200

            def __init__(self, b):
                self._b = b

            def json(self):
                return self._b
        if "calendar" in url:
            return R({"data": {"rows": self.cal.get(params["date"], [])}})
        return R({"data": {"tradesTable": {"rows": self.hist}}})

    async def aclose(self):
        pass


def test_calendar_collection_is_resumable_and_skips_weekends(tmp_path):
    cal = {"2026-10-08": [{"symbol": "AAA", "eps": "$1", "epsForecast": "$0.9", "surprise": "11.1", "noOfEsts": "4", "marketCap": "$1,000"}],
           "2026-10-09": [{"symbol": "BBB", "eps": "$1", "epsForecast": "$1.1", "surprise": "-9.1", "noOfEsts": "5", "marketCap": "$2,000"}]}
    http = FakeHttp(cal, [])
    c = C.PeadCollector(tmp_path, client=http, pause_s=0.0)
    n = asyncio.run(c.calendar(dt.date(2026, 10, 8), dt.date(2026, 10, 12)))      # Thu..Mon
    assert n == 2 and len(http.calls) == 3                                           # Thu, Fri, Mon; no weekend
    assert c.days_done() == {"2026-10-08", "2026-10-09", "2026-10-12"}
    http.calls.clear()
    assert asyncio.run(c.calendar(dt.date(2026, 10, 8), dt.date(2026, 10, 12))) == 0 and http.calls == []
    assert c.symbols_needed(min_estimates=3) == ["AAA", "BBB"]
    assert c.symbols_needed(min_estimates=3, max_cap=1500) == ["AAA"]


def test_prices_collection_writes_one_file_per_symbol(tmp_path):
    hist = [{"date": "10/09/2026", "close": "$10", "open": "$9"}]
    c = C.PeadCollector(tmp_path, client=FakeHttp({}, hist), pause_s=0.0)
    assert asyncio.run(c.prices(["AAA", "BBB"], workers=3)) == 2
    assert json.loads((tmp_path / "earnings" / "prices" / "AAA.json").read_text())[0]["close"] == 10.0
    assert asyncio.run(c.prices(["AAA"])) == 0                                       # already on file


def _panel(months: int = 72, names: int = 40, drift_per_surprise: float = 0.0005, seed: int = 11):
    """Synthetic calendar + prices: each month `names` announcers with
    surprises in [-20, 20]%; the 20-day return after the report rises
    with the surprise when `drift_per_surprise` > 0."""
    rng = random.Random(seed)
    cal, prices = [], {}
    day0 = dt.date(2017, 1, 5)          # 72 months reach into 2022, which the verdict rule checks
    syms = [f"S{i:03d}" for i in range(names)]
    for sym in syms:
        rows, px = [], 50.0
        d = day0 - dt.timedelta(days=30)
        while d < dt.date(2023, 6, 30):
            if d.weekday() < 5:
                o = px * (1 + rng.gauss(0, 0.002))
                c = o * (1 + rng.gauss(0, 0.01))
                rows.append({"date": d.isoformat(), "open": o, "close": c})
                px = c
            d += dt.timedelta(days=1)
        prices[sym] = rows
    for m in range(months):
        y, mo = 2017 + m // 12, 1 + m % 12
        report = dt.date(y, mo, 10)
        for sym in syms:
            s = rng.uniform(-20, 20)
            cal.append({"date": report.isoformat(), "symbol": sym, "surprise_pct": s, "n_est": 5, "market_cap": 1e9})
            if drift_per_surprise:
                # the 20 closes after the report carry a level shift proportional to the surprise
                rows = prices[sym]
                i = next(k for k, r in enumerate(rows) if r["date"] > report.isoformat())
                for r in rows[i:i + 20]:
                    r["close"] *= (1 + drift_per_surprise * s)
    return cal, prices


def test_window_return_enters_next_open_and_charges_two_sides():
    rows = [{"date": "2026-10-08", "open": 10.0, "close": 10.5}, {"date": "2026-10-09", "open": 11.0, "close": 11.5},
            {"date": "2026-10-12", "open": 12.0, "close": 12.5}]
    w = P.window_return(rows, "2026-10-08", 2, 0.0005)
    assert w["entry_date"] == "2026-10-09" and w["exit_date"] == "2026-10-12"
    assert w["gross"] == pytest.approx(12.5 / 11.0 - 1) and w["net_long"] == pytest.approx(w["gross"] - 0.001)
    assert P.window_return(rows, "2026-10-12", 2, 0.0005) is None                  # no session after the report
    assert P.window_return(rows, "2026-09-01", 2, 0.0005) is None                  # history starts weeks later: no window


def test_planted_drift_is_detected_and_noise_is_not():
    cal, prices = _panel(drift_per_surprise=0.004)
    res = P.run(cal, prices, hold_days=20, cost_side=0.0005)
    s = res["summary"]
    assert s["months"] >= 60 and s["mean_spread_month"] > 0 and s["sharpe_spread"] > 1.0
    assert P.passes(s)[0] == "alive"
    cal0, prices0 = _panel(drift_per_surprise=0.0, seed=3)
    s0 = P.run(cal0, prices0)["summary"]
    assert abs(s0["mean_spread_month"]) < abs(s["mean_spread_month"])
    assert "PEAD" in P.render(res)
    assert P.passes({"months": 10})[0] == "inconclusive"


def test_coverage_reports_missing_histories_by_year():
    cal, prices = _panel(months=24, names=30, drift_per_surprise=0.0, seed=2)
    res = P.run(cal, prices)
    assert res["coverage"]["share"] == 1.0 and set(res["coverage"]["by_year"]) == {2017, 2018}
    gone = {k: v for k, v in prices.items() if k != "S000"}
    res2 = P.run(cal, gone)
    assert res2["coverage"]["with_prices"] == res2["coverage"]["announcements"] - 24
    assert "usable price windows" in P.render(res2)


def test_merge_state_folds_parallel_streams(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for root, rows, days in ((a, [{"date": "2016-01-04", "symbol": "AAA"}], ["2016-01-04"]),
                             (b, [{"date": "2016-01-04", "symbol": "AAA"}, {"date": "2021-06-01", "symbol": "BBB"}],
                              ["2021-06-01"])):
        for r in rows:
            C.append_jsonl(root / "earnings" / "calendar.jsonl", r)
        (root / "earnings" / "calendar_days.txt").write_text("".join(d + "\n" for d in days))
    (b / "earnings" / "prices").mkdir()
    (b / "earnings" / "prices" / "BBB.json").write_text("[]")
    out = C.merge_state(a, b)
    assert out == {"calendar_rows_added": 1, "days": 2, "prices_copied": 1}
    assert len(C.read_jsonl(a / "earnings" / "calendar.jsonl")) == 2
    assert (a / "earnings" / "prices" / "BBB.json").exists()
    assert C.merge_state(a, b)["calendar_rows_added"] == 0

