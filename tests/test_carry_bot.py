"""Tests for the funding-carry bot against faked venues."""

import asyncio
import datetime as dt
import json

import httpx
import pytest

from cryptobot.data.hyperliquid import Funding
from cryptobot.data.kraken import KrakenClient, hl_to_base
from cryptobot.execution.perp_exchange import PerpExecConfig
from cryptobot import carry_bot as CB

T0 = float(int(dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc).timestamp()))
H = 3600.0


class FakeHL:
    def __init__(self, mids, rates, daily_funding):
        self.mids, self.rates, self.daily = mids, rates, daily_funding

    async def all_mids(self):
        return dict(self.mids)

    async def universe(self):
        return list(self.mids)

    async def funding_rates(self):
        return dict(self.rates)

    async def funding_history(self, coin, start_ms=0, max_calls=3):
        rate = self.daily.get(coin, 0.0) / 24.0
        start = start_ms / 1000.0
        return [Funding(ts=start + h * H, rate=rate, premium=0.0)
                for h in range(int((CB.now() - start) / H))]

    async def close(self):
        pass


class FakeKraken:
    def __init__(self, spots, pairs=None):
        self.spots = spots
        self.pairs = pairs or {c: f"{hl_to_base(c)}USD" for c in spots}

    async def pair_for(self, coin):
        return self.pairs.get(coin)

    async def tickers(self, names):
        out = {}
        for c, p in self.pairs.items():
            if p in names and c in self.spots:
                s = self.spots[c]
                out[p] = (s * 0.999, s * 1.001)
        return out

    async def close(self):
        pass


class FakeExec:
    armed = False


def _bot(hl, kr, tmp=None, **cfg):
    return CB.CarryBot(CB.CarryConfig(coins=tuple(hl.mids), state_dir=tmp, **cfg),
                       200.0, 1000.0, PerpExecConfig(), hl=hl, kraken=kr, executor=FakeExec())


class TestKrakenClient:
    def test_hl_to_base_strips_the_k_prefix(self):
        assert hl_to_base("kPEPE") == "PEPE"
        assert hl_to_base("WIF") == "WIF"
        assert hl_to_base("kLUNC") == "LUNC"

    def test_pairs_and_tickers_parse(self):
        def handler(req):
            if req.url.path.endswith("/AssetPairs"):
                return httpx.Response(200, json={"result": {
                    "PEPEUSD": {"wsname": "PEPE/USD"}, "PEPEEUR": {"wsname": "PEPE/EUR"},
                    "XDGUSD": {"wsname": "XDG/USD"}}})
            return httpx.Response(200, json={"result": {
                "PEPEUSD": {"b": ["0.0000100", "1", "1"], "a": ["0.0000102", "1", "1"]}}})
        kc = KrakenClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                   base_url="https://x"))
        assert asyncio.run(kc.pair_for("kPEPE")) == "PEPEUSD"
        assert asyncio.run(kc.pair_for("DOGE")) == "XDGUSD"        # alias
        assert asyncio.run(kc.pair_for("NOPE")) is None
        t = asyncio.run(kc.tickers(["PEPEUSD"]))
        assert t["PEPEUSD"] == (1.0e-5, 1.02e-5)


class TestPosition:
    def test_short_receives_funding_by_the_hour(self):
        p = CB.CarryPosition("A", 100.0, 1.0, 1.0, T0)
        assert p.accrue(0.0001, T0 + 10 * H) == pytest.approx(0.1)
        assert p.accrue(0.0001, T0 + 12 * H) == pytest.approx(0.02)

    def test_basis_is_zero_when_both_legs_move_together(self):
        p = CB.CarryPosition("A", 100.0, 2.0, 2.0, T0)
        assert p.basis_pnl(3.0, 3.0) == pytest.approx(0.0)
        assert p.basis_pnl(1.0, 1.0) == pytest.approx(0.0)

    def test_basis_gains_when_perp_falls_to_spot(self):
        p = CB.CarryPosition("A", 100.0, perp_entry=2.02, spot_entry=2.0, opened_at=T0)
        assert p.basis_pnl(2.0, 2.0) == pytest.approx(100 * (0.02 / 2.02))

    def test_pnl_nets_fees(self):
        p = CB.CarryPosition("A", 100.0, 1.0, 1.0, T0, fees_usd=0.4)
        p.accrue(0.001, T0 + H)
        assert p.pnl(1.0, 1.0) == pytest.approx(0.1 - 0.4)


class TestBook:
    def test_open_close_and_persistence(self, tmp_path):
        b = CB.CarryBook("sim", 200.0, state_file=tmp_path / "c.json")
        b.open("A", 60.0, 1.0, 1.0, T0, 0.008)
        b2 = CB.CarryBook("sim", 200.0, state_file=tmp_path / "c.json")
        b2.load()
        assert "A" in b2.positions and b2.positions["A"].fees_usd == pytest.approx(0.24)
        t = b2.close("A", 1.0, 1.0, T0 + H, 0.008, "test")
        assert t.fees_usd == pytest.approx(0.48) and t.pnl_usd == pytest.approx(-0.48)
        assert b2.realized == pytest.approx(-0.48)
        assert json.loads((tmp_path / "c.json").read_text())["closed"][0]["reason"] == "test"

    def test_corrupt_state_starts_flat(self, tmp_path):
        f = tmp_path / "c.json"
        f.write_text("{not json")
        b = CB.CarryBook("sim", 200.0, state_file=f)
        b.load()
        assert b.positions == {} and b.realized == 0.0


class TestDaily:
    def _bot(self, monkeypatch, daily, tmp=None, **cfg):
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
        hl = FakeHL({c: 1.0 for c in daily}, {c: r / 24 for c, r in daily.items()}, daily)
        kr = FakeKraken({c: 1.0 for c in daily})
        return _bot(hl, kr, tmp, **cfg), hl, kr

    def test_enters_top_n_above_the_bar(self, monkeypatch):
        bot, hl, kr = self._bot(monkeypatch, {"A": 0.002, "B": 0.0015, "C": 0.001,
                                              "D": 0.0008, "E": 0.0001, "F": -0.001})
        asyncio.run(bot.run_daily())
        assert set(bot.books["sim"].positions) == {"A", "B", "C"}
        assert not bot.books["real"].positions
        pos = bot.books["sim"].positions["A"]
        assert pos.notional_usd == pytest.approx(60.0)      # 30% of $200
        assert bot.journal.recent(1)[0]["action"] == "opened"

    def test_nothing_below_the_entry_bar(self, monkeypatch):
        bot, *_ = self._bot(monkeypatch, {"A": 0.0002, "B": 0.0001})
        asyncio.run(bot.run_daily())
        assert not bot.books["sim"].positions

    def test_coin_without_a_kraken_pair_is_skipped(self, monkeypatch):
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
        daily = {"A": 0.002, "B": 0.002}
        hl = FakeHL({c: 1.0 for c in daily}, {}, daily)
        kr = FakeKraken({"A": 1.0, "B": 1.0}, pairs={"A": "AUSD"})
        bot = _bot(hl, kr)
        asyncio.run(bot.run_daily())
        assert set(bot.books["sim"].positions) == {"A"}

    def test_exits_when_recent_funding_turns_negative(self, monkeypatch):
        bot, hl, kr = self._bot(monkeypatch, {"A": 0.002, "B": 0.0015, "C": 0.001, "D": 0.0009})
        asyncio.run(bot.run_daily())
        hl.daily["A"] = -0.001                          # trailing 3d now negative
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert "A" not in bot.books["sim"].positions
        assert "D" in bot.books["sim"].positions        # slot refilled
        closed = bot.books["sim"].closed[-1]
        assert closed.coin == "A" and "funding" in closed.reason

    def test_exits_when_rank_collapses(self, monkeypatch):
        bot, hl, kr = self._bot(monkeypatch, {"A": 0.002, "B": 0.0015, "C": 0.001, "D": 0.0009,
                                              "E": 0.0009, "F": 0.0009, "G": 0.0009}, top_n=1)
        asyncio.run(bot.run_daily())
        assert set(bot.books["sim"].positions) == {"A"}
        hl.daily["A"] = 0.0007                          # still positive, but rank 7
        bot.last_daily_run = 0
        asyncio.run(bot.run_daily())
        assert "A" not in bot.books["sim"].positions

    def test_monitor_accrues_funding_and_tracks_basis(self, monkeypatch):
        bot, hl, kr = self._bot(monkeypatch, {"A": 0.0024})
        asyncio.run(bot.run_daily())
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400 + 5 * H)
        asyncio.run(bot.monitor())
        pos = bot.books["sim"].positions["A"]
        assert pos.funding_usd == pytest.approx(60.0 * 0.0001 * 5)
        hl.mids["A"] = 1.02                              # perp rallies, spot flat
        asyncio.run(bot.monitor())
        eq = bot.books["sim"].equity(bot.perps, bot.spots)
        assert eq < 200.0 + pos.funding_usd              # basis loss shows in equity

    def test_state_serialises_and_dashboard_renders(self, monkeypatch):
        from fastapi.testclient import TestClient
        from cryptobot.dashboard import create_app
        bot, *_ = self._bot(monkeypatch, {"A": 0.002, "B": 0.0001})
        asyncio.run(bot.run_daily())
        asyncio.run(bot.monitor())
        json.dumps(bot.state())
        c = TestClient(create_app(bot, token="t", extra_hosts={"testserver"}))
        assert c.get("/").status_code == 200
        r = c.get("/api/state", headers={"x-dashboard-token": "t"})
        assert r.status_code == 200 and r.json()["books"]["sim"]["positions"][0]["symbol"] == "A"

    def test_set_mode_refuses_real_when_unarmed(self, monkeypatch):
        bot, *_ = self._bot(monkeypatch, {"A": 0.002})
        ok, why = bot.set_mode("real")
        assert not ok and "ARM_LIVE" in why

    def test_refuses_a_coin_whose_spot_is_a_different_asset(self, monkeypatch):
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
        daily = {"LIT": 0.003, "A": 0.002}
        hl = FakeHL({"LIT": 4.0, "A": 1.0}, {}, daily)
        kr = FakeKraken({"LIT": 0.12, "A": 1.0})      # ticker collision
        bot = _bot(hl, kr)
        asyncio.run(bot.run_daily())
        assert set(bot.books["sim"].positions) == {"A"}
        assert any(d["stage"] == "identity" and d["symbol"] == "LIT"
                   for d in bot.journal.recent(10))

    def test_normal_basis_passes_the_identity_gate(self, monkeypatch):
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
        hl = FakeHL({"A": 1.0}, {}, {"A": 0.002})
        bot = _bot(hl, FakeKraken({"A": 1.004}))
        asyncio.run(bot.run_daily())
        assert "A" in bot.books["sim"].positions

    def test_empty_coin_list_discovers_the_universe(self, monkeypatch):
        monkeypatch.setattr(CB, "now", lambda: T0 + 30 * 86400)
        daily = {"A": 0.002, "B": 0.002, "C": 0.0001}
        hl = FakeHL({c: 1.0 for c in daily}, {}, daily)
        kr = FakeKraken({c: 1.0 for c in daily}, pairs={"A": "AUSD", "C": "CUSD"})
        bot = CB.CarryBot(CB.CarryConfig(), 200.0, 1000.0, PerpExecConfig(),
                          hl=hl, kraken=kr, executor=FakeExec())
        asyncio.run(bot.run_daily())
        assert [r["coin"] for r in bot.ranking] == ["A", "C"]     # B has no spot pair
        assert set(bot.books["sim"].positions) == {"A"}

    def test_short_window_rate_comes_from_the_same_fetch(self, monkeypatch):
        bot, hl, kr = self._bot(monkeypatch, {"A": 0.0024})
        long_r, short_r = asyncio.run(bot.trailing_rates("A"))
        assert long_r == pytest.approx(0.0024) and short_r == pytest.approx(0.0024)

    def test_daily_due_once_per_day(self, monkeypatch):
        bot, *_ = self._bot(monkeypatch, {"A": 0.002})
        day0 = int(T0 // 86400) * 86400
        bot.last_daily_run = day0 + 2000
        assert not bot._daily_due(day0 + 5000)
        assert not bot._daily_due(day0 + 86400 + 100)
        assert bot._daily_due(day0 + 86400 + 1300)
