import asyncio
import datetime as dt
import math
import random

import pytest

from cryptobot import vrp_study as V


def _path(days=400, vol=0.40, seed=1, start=dt.date(2024, 1, 1), s0=50_000.0):
    rng = random.Random(seed)
    px, s = {}, s0
    for i in range(days):
        s *= math.exp(rng.gauss(0.0, vol / math.sqrt(365.0)))
        px[start + dt.timedelta(days=i)] = s
    return px


def test_black_scholes_matches_the_textbook_approximation_and_parity():
    c, p, dc = V.bs(100.0, 100.0, 0.5, 30 / 365)
    assert c + p == pytest.approx(0.8 * 0.5 * math.sqrt(30 / 365) * 100, rel=0.01)
    assert c - p == pytest.approx(0.0, abs=1e-9)                 # zero rates: ATM call = put
    assert 0.5 < dc < 0.56
    kc, kp = V.wing_strikes(100.0, 0.5, 30 / 365, 0.10)
    assert kc > 100 > kp
    assert V.bs(100.0, kc, 0.5, 30 / 365)[2] == pytest.approx(0.10, abs=1e-6)
    assert V.bs(100.0, kp, 0.5, 30 / 365)[2] - 1.0 == pytest.approx(-0.10, abs=1e-6)
    val, dlt = V.position(100.0, 100.0, kc, kp, 0.5, 30 / 365)
    assert 0 < val < c + p and abs(dlt) < 0.2
    assert V.bs(120.0, 100.0, 0.5, 0.0) == (20.0, 0.0, 1.0)      # expiry: intrinsic


def test_realised_vol_counts_observations_and_annualises_per_source():
    px = _path(60, vol=0.50, seed=3)
    c = V.Closes(px)
    end = max(px)
    rv = c.realised(end, 20)
    assert rv is not None and 0.2 < rv < 0.9
    assert c.realised(min(px), 20) is None                           # not enough history
    # IBIT: weekdays only, annualised on 252
    wk = {d: v for d, v in px.items() if d.weekday() < 5}
    ci = V.Closes(wk, annual=252.0)
    endw = max(wk)
    assert ci.realised(endw, 20) == pytest.approx(V.Closes(wk, annual=365.0).realised(endw, 20) * math.sqrt(252 / 365))
    exp = c.expiry_after(dt.date(2024, 1, 5), 30)
    assert exp >= dt.date(2024, 2, 4) and exp.weekday() < 5
    assert c.realised_between(dt.date(2024, 1, 5), exp) is not None
    assert V.gate_open(0.50, 0.40, 5.0) and not V.gate_open(0.50, 0.46, 5.0) and V.gate_open(0.5, None, None)


def test_short_variance_earns_when_implied_exceeds_realised_and_loses_otherwise():
    px = _path(500, vol=0.40, seed=7)
    rich = {d: 0.60 for d in px}
    cheap = {d: 0.25 for d in px}
    swap_rich = V.variance_swap_trades(rich, px, None)
    swap_cheap = V.variance_swap_trades(cheap, px, None)
    assert len(swap_rich) >= 12 and all(t["exit"] > t["entry"] for t in swap_rich)
    assert sum(t["pnl"] for t in swap_rich) > 0 > sum(t["pnl"] for t in swap_cheap)
    st_rich = V.straddle_trades(rich, px, None)
    st_cheap = V.straddle_trades(cheap, px, None)
    assert sum(t["pnl"] for t in st_rich) > 0 > sum(t["pnl"] for t in st_cheap)
    # one at a time: no overlap; the ladder: one a weekday at 1/21 size
    for a, b in zip(st_rich, st_rich[1:]):
        assert b["entry"] > a["exit"]
    ladder = V.straddle_trades(rich, px, None, overlap=True)
    assert len(ladder) > 5 * len(st_rich)
    assert abs(sum(t["pnl"] for t in ladder) - sum(t["pnl"] for t in st_rich)) < abs(sum(t["pnl"] for t in st_rich)) * 2
    early = V.straddle_trades(rich, px, None, close_dte=7)
    assert all((t["exit"] - t["entry"]).days < 30 for t in early)
    wings = V.straddle_trades(rich, px, None, wing_delta=0.10)
    assert len(wings) == len(st_rich)
    assert sum(t["premium_pct"] for t in wings) == pytest.approx(sum(t["premium_pct"] for t in st_rich))


def test_gate_skips_months_and_run_counts_every_series_as_a_trial():
    px = _path(700, vol=0.40, seed=11)
    iv = {d: (0.60 if (d.month % 2) else 0.30) for d in px}      # the gate is shut every other month
    trades = V.straddle_trades(iv, px, 5.0)
    assert trades and all(t["entry"].month % 2 == 1 for t in trades)
    res = V.run(iv, px, wing_delta=0.10, overlap=True, close_dte=7)
    assert res["trials"] == 2 * 4 + 2 + 2 + 2
    reg = res["straddle"][5.0]
    assert "dsr" in reg and reg["trials"] == res["trials"] and len(reg["monthly"]) == res["straddle"][None]["months"]
    text = V.render(res)
    assert "ladder" in text and "iron butterfly" in text and "bought back 7 days" in text and "verdict:" in text
    assert V.passes({"trades": 0}) == ("inconclusive", "no trades")
    assert V.passes({"trades": 5, "worst_month": -20.0, "sharpe": 2.0, "psr": 0.99}) [0] == "inconclusive"
    assert V.passes({"trades": 5, "worst_month": -5.0, "sharpe": 1.0, "psr": 0.99, "dsr": 0.5})[1].startswith("clears the bar but DSR")
    assert V.passes({"trades": 5, "worst_month": -5.0, "sharpe": 1.0, "psr": 0.99, "dsr": 0.97}) == ("alive", "clears the bar")


def test_monthly_series_fills_empty_months_with_zero():
    trades = [{"entry": dt.date(2025, 1, 10), "pnl": 2.0}, {"entry": dt.date(2025, 3, 3), "pnl": -1.0}]
    ms = V.monthly_series(trades, dt.date(2025, 1, 1), dt.date(2025, 4, 15))
    assert ms == [("2025-01", 2.0), ("2025-02", 0.0), ("2025-03", -1.0), ("2025-04", 0.0)]
    s = V.summarize(trades, dt.date(2025, 1, 1), dt.date(2025, 4, 15))
    assert s["months"] == 4 and s["worst_month"] == -1.0 and s["total"] == 1.0 and s["by_year"] == {2025: 1.0}


class FakeHttp:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params))

        class R:
            status_code = 200

            def __init__(self, body):
                self._b = body

            def json(self):
                return self._b
        if "deribit" in url:
            a = params["start_timestamp"] // 1000
            b = params["end_timestamp"] // 1000
            return R({"result": {"data": [[t * 1000, 50.0, 55.0, 45.0, 50.0 + i] for i, t in enumerate(range(a, b, 86400))]}})
        a = dt.datetime.fromisoformat(params["start"].replace("Z", "+00:00")).timestamp()
        return R([[int(a) + i * 86400, 1, 1, 1, 100.0 + i, 1.0] for i in range(3)])

    async def aclose(self):
        pass


def test_fetch_pages_and_extends_from_the_last_day(tmp_path):
    http = FakeHttp()
    today = dt.date(2021, 4, 10)
    added = asyncio.run(V.fetch(tmp_path, client=http, today=today))
    assert added["dvol"] > 0 and added["btc"] > 0
    rows = V.read_jsonl(V.dvol_file(tmp_path))
    assert rows[0]["date"] == "2021-03-24" and all(set(r) == {"date", "open", "high", "low", "close"} for r in rows)
    n = len(http.calls)
    again = asyncio.run(V.fetch(tmp_path, client=http, today=today))
    assert again == {"dvol": 0, "btc": 0}                              # nothing new, no duplicates
    assert len(V.read_jsonl(V.dvol_file(tmp_path))) == len(rows)
    assert len(http.calls) > n
    iv, px = V.load(tmp_path)
    assert iv and len(px) and all(0 < v < 2 for v in iv.values())


def test_ibit_source_reads_the_collector_rows(tmp_path):
    d = tmp_path / "options"
    d.mkdir()
    (d / "ibit.jsonl").write_text('{"date": "2026-10-12", "iv30_atm": 0.366, "spot": 46.6}\n{"date": "2026-10-13", "iv30_atm": null}\n')
    (d / "ibit_closes.jsonl").write_text('{"date": "2026-10-10", "close": 46.0}\n{"date": "2026-10-12", "close": 46.6}\n')
    iv, px = V.load(tmp_path, "ibit")
    assert list(iv) == [dt.date(2026, 10, 12)] and px.annual == 252.0 and len(px) == 2
