import pytest
from fastapi.testclient import TestClient

from cryptobot import desk as D


def cfg_for(tmp_path):
    return {"perp": {"venue": "kalshi"}, "allocation": {"carry": 0.0, "bounce_short": 1.0},
            "risk": {"bankroll_usd": 200}, "sim": {"bankroll_usd": 200},
            "allocator": {"mode": "auto", "learning_floor": 0.5, "max_drawdown_real": 0.25},
            "strategies": {"bounce": {"registry": "bounce-short-us3", "backtest_mean": 0.02,
                                      "backtest_sd": 0.131, "confidence": 0.34}}}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    cfg = cfg_for(tmp_path)
    bots = D.build(cfg, tmp_path)

    async def fake_balance():
        bot = bots["bounce"]
        return {"total_usd_balance": bot.books["real"].equity({}), "available_margin": 0.0}
    bots["bounce"].executor.balance = fake_balance
    return D.Desk(bots, cfg, tmp_path)


@pytest.mark.asyncio
async def test_cycle_sets_capital_from_weights_and_reads_registry_verdict(desk):
    st = await desk.allocation_cycle()
    assert st["weights"]["bounce"] == 0.0 and "paper only" in st["reasons"]["bounce"]   # not armed
    desk.bots["bounce"].executor._armed = True
    st = await desk.allocation_cycle()
    assert st["weights"]["bounce"] == 0.5 and st["capital"]["total"] == 200.0
    assert desk.bots["bounce"].real_capital == 100.0
    s = desk.state()
    assert s["strategies"]["bounce"]["verdict"] == "inconclusive"
    assert s["strategies"]["bounce"]["registry_id"] == "bounce-short-us3"
    assert any(r["id"] == "selection-bias-diagnostics" for r in s["registry"])


def test_api_endpoints_require_token_and_apply_manual_weights(desk):
    app = D.create_desk_app(desk.bots, "tok", {"testserver"}, desk=desk)
    c = TestClient(app)
    assert c.get("/api/desk").status_code == 401
    r = c.get("/api/desk", headers={"x-dashboard-token": "tok"})
    assert r.status_code == 200 and "allocation" in r.json()
    page = c.get("/")
    assert page.status_code == 200 and "Trading desk" in page.text and "api/desk" in page.text
    desk.bots["bounce"].executor._armed = True
    r = c.post("/api/allocation", json={"mode": "manual", "weights": {"bounce": 0.3}}, headers={"x-dashboard-token": "tok"})
    assert r.status_code == 200 and r.json()["mode"] == "manual" and r.json()["weights"]["bounce"] == 0.3
    assert desk.bots["bounce"].real_capital == pytest.approx(60.0)
    r = c.post("/api/allocation", json={"mode": "manual", "weights": {"bounce": 1.5}}, headers={"x-dashboard-token": "tok"})
    assert r.status_code == 400
    r = c.post("/api/allocation", json={"mode": "auto"}, headers={"x-dashboard-token": "tok"})
    assert r.json()["weights"]["bounce"] == 0.5
    r = c.post("/api/resume", json={"strategy": "nope"}, headers={"x-dashboard-token": "tok"})
    assert r.status_code == 404
    r = c.post("/api/strategy_mode", json={"strategy": "bounce", "mode": "real"}, headers={"x-dashboard-token": "tok"})
    assert r.status_code == 200 and desk.bots["bounce"].mode == "real"


@pytest.mark.asyncio
async def test_drawdown_kill_and_resume_through_desk(desk):
    bot = desk.bots["bounce"]
    bot.executor._armed = True
    await desk.allocation_cycle()
    bot.books["real"].portfolio.realized_pnl = -60.0            # $200 -> $140: -30%
    st = await desk.allocation_cycle()
    assert st["weights"]["bounce"] == 0.0 and "KILLED" in st["reasons"]["bounce"]
    assert bot.real_capital == 0.0 and any(a["text"].startswith("KILL bounce") for a in desk.alerts)
    desk.allocator.resume("bounce", 140.0)
    st = await desk.allocation_cycle()
    assert st["weights"]["bounce"] == 0.5 and bot.real_capital == pytest.approx(70.0)
