"""Shadow launch logger: filters, ledger, revisits and report."""

import asyncio
import datetime as dt
import json
import time

import httpx
import pytest

from cryptobot import launch_shadow as L

NOW = 1_800_000_000.0


def _raw(addr="P1", age_min=120, liq=50_000, vol24=100_000, mcap=500_000, price=1.0,
         b30=30, s30=10, b1=60, s1=20, trades=400, v1=10_000, v6=40_000):
    created = dt.datetime.fromtimestamp(NOW - age_min * 60, dt.timezone.utc).isoformat()
    return {"attributes": {
        "address": addr, "name": addr, "pool_created_at": created.replace("+00:00", "Z"),
        "base_token_price_usd": str(price), "reserve_in_usd": str(liq),
        "market_cap_usd": str(mcap), "fdv_usd": None,
        "volume_usd": {"h24": str(vol24), "h6": str(v6), "h1": str(v1)},
        "transactions": {"m30": {"buys": b30, "sells": s30}, "h1": {"buys": b1, "sells": s1},
                         "h24": {"buys": trades // 2, "sells": trades - trades // 2}}}}


def _p(**kw):
    return L.normalise(_raw(**kw), "solana", NOW)


class TestFilters:
    def test_normalise_reads_the_fields(self):
        p = _p()
        assert p["age_min"] == pytest.approx(120) and p["trades_h24"] == 400
        assert p["liq"] == 50_000 and p["mcap"] == 500_000

    def test_mcap_falls_back_to_fdv(self):
        raw = _raw()
        raw["attributes"]["market_cap_usd"] = None
        raw["attributes"]["fdv_usd"] = "700000"
        assert L.normalise(raw, "solana", NOW)["mcap"] == 700_000

    @pytest.mark.parametrize("kw,reason", [
        ({"age_min": 10}, "age"), ({"age_min": 73 * 60}, "age"),
        ({"liq": 11_999}, "liquidity"), ({"vol24": 39_000}, "volume"),
        ({"mcap": 50_000}, "mcap"), ({"mcap": 9_000_000}, "mcap"),
        ({"trades": 149}, "trades"), ({"b1": 21, "s1": 0}, "no_sells")])
    def test_each_hard_threshold_fires(self, kw, reason):
        assert L.hard_kill(_p(**kw)) == reason

    def test_a_clean_launch_passes(self):
        assert L.hard_kill(_p()) is None

    def test_crowd_proxy(self):
        assert L.crowd_proxy(_p())
        assert not L.crowd_proxy(_p(b30=5, s30=10))          # sellers in the last 30m
        assert not L.crowd_proxy(_p(v1=30_000, v6=40_000))   # one spike, not spread

    def test_costs_and_losses_are_capped_at_the_ticket(self):
        assert L.round_trip(1e-6) == 1.0
        assert L.round_trip(0) == 1.0
        assert L.net_return(1.0, 0.5, 1e-6) == -1.0
        assert L.net_return(1.0, None, 50_000) == -1.0
        assert L.net_return(1.0, 2.0, 50_000) == pytest.approx(1.0 - 0.008)

    def test_round_trip_grows_as_pools_thin(self):
        assert L.round_trip(50_000) == pytest.approx(2 * (0.003 + 0.001))
        assert L.round_trip(12_000) > L.round_trip(50_000)


class TestLedger:
    def test_first_appearance_only_and_reload(self, tmp_path):
        f = tmp_path / "l.jsonl"
        led = L.Ledger(f)
        p = _p()
        assert led.enter(p, "fresh", NOW)
        assert not led.enter({**p, "price": 9.0}, "fresh", NOW + 900)   # later sighting ignored
        led2 = L.Ledger(f)
        assert led2.entries[("solana", "P1", "fresh")]["price"] == 1.0

    def test_marks_come_due_by_horizon_and_persist(self, tmp_path):
        f = tmp_path / "l.jsonl"
        led = L.Ledger(f)
        led.enter(_p(), "hard", NOW)
        assert led.due(NOW + 1800) == []
        assert led.due(NOW + 3700) == [(("solana", "P1", "hard"), 1)]
        led.mark(("solana", "P1", "hard"), 1, 1.5)
        assert L.Ledger(f).marks[("solana", "P1", "hard")] == {1: 1.5}
        assert [h for _, h in L.Ledger(f).due(NOW + 25 * 3600)] == [4, 24]

    def test_corrupt_lines_are_skipped(self, tmp_path):
        f = tmp_path / "l.jsonl"
        f.write_text("{bad\n")
        assert L.Ledger(f).entries == {}


class TestScanner:
    def _scanner(self, tmp_path, pools, multi=None):
        def handler(req):
            if "/pools/multi/" in req.url.path:
                return httpx.Response(200, json={"data": multi or []})
            if req.url.params.get("page") == "1" and req.url.params.get("duration") == "1h" \
                    and "/solana/" in req.url.path:
                return httpx.Response(200, json={"data": pools})
            return httpx.Response(200, json={"data": []})
        return L.Scanner(L.Ledger(tmp_path / "l.jsonl"),
                         client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    def test_scan_sorts_pools_into_groups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(L, "CALL_PAUSE_S", 0)
        monkeypatch.setattr(L.time, "time", lambda: NOW)
        pools = [_raw("OK"), _raw("THIN", liq=5_000), _raw("OLD", age_min=80 * 60),
                 _raw("SPIKE", v1=35_000, v6=40_000)]
        sc = self._scanner(tmp_path, pools)
        stats = asyncio.run(sc.scan())
        groups = {(k[1], k[2]) for k in sc.ledger.entries}
        assert ("OLD", "fresh") not in groups
        assert ("THIN", "fresh") in groups and ("THIN", "hard") not in groups
        assert ("SPIKE", "hard") in groups and ("SPIKE", "crowd") not in groups
        assert ("OK", "crowd") in groups
        assert stats["kills"] == {"liquidity": 1}

    def test_revisit_marks_prices_and_vanished_pools(self, tmp_path, monkeypatch):
        monkeypatch.setattr(L, "CALL_PAUSE_S", 0)
        sc = self._scanner(tmp_path, [], multi=[
            {"attributes": {"address": "A", "base_token_price_usd": "2.0"}}])
        sc.ledger.enter({**_p(addr="A")}, "hard", NOW)
        sc.ledger.enter({**_p(addr="B")}, "hard", NOW)
        monkeypatch.setattr(L.time, "time", lambda: NOW + 3700)
        assert asyncio.run(sc.revisit()) == 2
        assert sc.ledger.marks[("solana", "A", "hard")][1] == 2.0
        assert sc.ledger.marks[("solana", "B", "hard")][1] is None


class TestReport:
    def test_vanished_pools_count_as_total_loss(self, tmp_path):
        led = L.Ledger(tmp_path / "l.jsonl")
        led.enter(_p(addr="A"), "hard", NOW)
        led.enter(_p(addr="B"), "hard", NOW)
        led.mark(("solana", "A", "hard"), 1, 1.0)
        led.mark(("solana", "B", "hard"), 1, None)
        line = next(l for l in L.report(led).splitlines() if l.startswith("hard"))
        cols = line.split()
        expected = (0.0 - L.round_trip(50_000) + -1.0) / 2
        assert cols[2] == "2"                                   # n
        assert cols[3] == f"{100 * expected:+.1f}%"             # mean net
        assert cols[-1] == "1" and cols[-2] == "1"             # one gone, one <= -50%
