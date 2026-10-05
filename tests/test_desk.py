"""The combined desk: mounted dashboards, the token, summary, preflight."""

import pytest
from fastapi.testclient import TestClient

from cryptobot import desk as D


class FakeBot:
    def __init__(self, sim_start, sim_eq, real_start=0.0, real_eq=0.0, open_=0):
        self.mode = "sim"
        self._s = (sim_start, sim_eq, real_start, real_eq, open_)

    def state(self):
        ss, se, rs, re_, o = self._s
        book = lambda s, e: {"starting_equity": s, "equity": e,
                             "summary": {"open_positions": o, "trades": 2}}
        return {"mode": self.mode, "real_unlocked": False,
                "books": {"sim": book(ss, se), "real": book(rs, re_)}}

    def set_mode(self, mode):
        return False, "not armed"


def _client(token="tok"):
    bots = {"bounce": FakeBot(100, 110, open_=3), "carry": FakeBot(100, 95, open_=1)}
    return TestClient(D.create_desk_app(bots, token, {"testserver"})), bots


class TestMountedAuth:
    def test_mounted_api_still_requires_the_token(self):
        c, _ = _client()
        for path in ("/bounce/api/state", "/carry/api/state"):
            assert c.get(path).status_code == 401
            assert c.get(path, headers={"x-dashboard-token": "wrong"}).status_code == 401
            assert c.get(path, headers={"x-dashboard-token": "tok"}).status_code == 200

    def test_mounted_mode_switch_requires_the_token(self):
        c, _ = _client()
        assert c.post("/carry/api/mode", json={"mode": "real"}).status_code == 401
        r = c.post("/carry/api/mode", json={"mode": "real"}, headers={"x-dashboard-token": "tok"})
        assert r.status_code == 200 and r.json()["ok"] is False

    def test_summary_requires_the_token(self):
        c, _ = _client()
        assert c.get("/api/summary").status_code == 401
        assert c.get("/api/summary?t=tok").status_code == 200

    def test_foreign_host_is_refused_everywhere(self):
        c, _ = _client()
        for path in ("/", "/carry/", "/api/summary?t=tok"):
            assert c.get(path, headers={"host": "evil.example"}).status_code == 421

    def test_pages_load_and_fetch_relative_paths(self):
        c, _ = _client()
        assert c.get("/").status_code == 200
        page = c.get("/carry/").text
        assert 'fetch("api/state"' in page and 'fetch("/api/state"' not in page

    def test_bare_prefix_redirects_keeping_the_token(self):
        c, _ = _client()
        r = c.get("/carry?t=tok", follow_redirects=False)
        assert r.status_code in (302, 307) and r.headers["location"] == "/carry/?t=tok"


class TestSummary:
    def test_totals_add_up_across_strategies(self):
        s = D.summary({"bounce": FakeBot(100, 110, open_=3), "carry": FakeBot(100, 95, open_=1)})
        assert s["total"]["sim"]["equity"] == 205 and s["total"]["sim"]["start"] == 200
        assert s["total"]["sim"]["return_pct"] == pytest.approx(0.025)
        assert s["strategies"]["bounce"]["sim"]["open"] == 3

    def test_zero_real_bankroll_does_not_divide_by_zero(self):
        s = D.summary({"x": FakeBot(100, 100)})
        assert s["total"]["real"]["return_pct"] == 0.0


CFG = {"risk": {"bankroll_usd": 1000}, "allocation": {"carry": 0.5, "bounce_short": 0.5},
       "carry": {"top_n": 3, "slot_fraction": 0.30, "perp_leverage": 1.0},
       "perp": {"max_trade_usd": 50}}


class TestPreflight:
    def test_capital_plan_splits_venues(self):
        p = D.capital_plan(CFG)
        # carry $500 * 0.9 deployed / 2 legs = $225 spot on Kraken, $225 margin on HL
        assert p["kraken_usd"] == pytest.approx(225.0)
        assert p["hyperliquid_usdc"] == pytest.approx(225.0 + 500.0)
        assert p["largest_order"] == pytest.approx(75.0)

    def test_nothing_set_is_not_ready(self):
        checks = D.preflight(CFG, {})
        assert not any(ok for name, ok, _ in checks if name != "orders fit under max_trade_usd")
        assert "NOT ready" in D.render_preflight(CFG, checks)

    def test_undersized_trade_cap_is_flagged(self):
        checks = dict((n, ok) for n, ok, _ in D.preflight(CFG, {}))
        assert checks["orders fit under max_trade_usd"] is False      # $75 > $50
        big = {**CFG, "perp": {"max_trade_usd": 100}}
        assert dict((n, ok) for n, ok, _ in D.preflight(big, {}))["orders fit under max_trade_usd"]

    def test_everything_set_and_funded_is_ready(self):
        cfg = {**CFG, "perp": {"live": True, "max_trade_usd": 100}, "carry": {**CFG["carry"], "live": True}}
        env = {"CRYPTOBOT_ARM_LIVE": "yes", "CRYPTOBOT_PRIVATE_KEY": "0xabc",
               "CRYPTOBOT_KRAKEN_KEY": "k", "CRYPTOBOT_KRAKEN_SECRET": "s"}
        checks = D.preflight(cfg, env, {"kraken_usd": 300, "hyperliquid_usdc": 800})
        assert all(ok for _, ok, _ in checks)
        assert "READY" in D.render_preflight(cfg, checks)

    def test_underfunded_venue_fails(self):
        checks = D.preflight(CFG, {}, {"kraken_usd": 100, "hyperliquid_usdc": 800})
        res = {n: ok for n, ok, _ in checks}
        assert res["kraken_usd >= $225.00"] is False and res["hyperliquid_usdc >= $725.00"] is True
