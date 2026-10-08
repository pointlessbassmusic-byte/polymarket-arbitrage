import pytest

from cryptobot.allocator import Allocator, AllocatorConfig, Evidence, posterior_mean


def ev(**kw):
    base = dict(name="bounce", backtest_mean=0.020, backtest_sd=0.131, confidence=0.34,
                verdict="inconclusive", live_returns=[], real_equity=200.0, armed=True)
    return Evidence(**{**base, **kw})


def test_posterior_is_shrunk_backtest_until_live_trades_accumulate():
    cfg = AllocatorConfig(pseudo_trades=50)
    m, n = posterior_mean(ev(), cfg)
    assert n == 0 and m == pytest.approx(0.020 * 0.34)
    m2, n2 = posterior_mean(ev(live_returns=[0.10] * 5), cfg)
    assert n2 == 5 and m2 == pytest.approx((50 * 0.0068 + 5 * 0.10) / 55)
    # five great trades move the posterior by 5/55, not to the moon
    assert m2 < 0.02


def test_auto_weight_uses_kelly_then_learning_floor(tmp_path):
    cfg = AllocatorConfig(kelly_fraction=0.5, learning_floor=0.5, pseudo_trades=50)
    a = Allocator(cfg, tmp_path / "allocation.json")
    d = a.decide({"bounce": ev()})
    f_star = 0.0068 / 0.131 ** 2                       # ~0.40
    assert d.posterior["bounce"]["f_star"] == pytest.approx(f_star, rel=1e-3)
    assert d.weights["bounce"] == 0.5 and "learning floor" in d.reasons["bounce"]
    assert d.cash == pytest.approx(0.5)
    strong = ev(backtest_mean=0.05, confidence=1.0, backtest_sd=0.10)   # f* = 5 -> capped
    d2 = a.decide({"bounce": strong})
    assert d2.weights["bounce"] == 1.0 and d2.cash == 0.0


def test_gates_killed_unarmed_and_slippage(tmp_path):
    a = Allocator(AllocatorConfig(), tmp_path / "a.json")
    d = a.decide({"bounce": ev(verdict="killed"), "carry": ev(name="carry", armed=False),
                  "x": ev(name="x", exec_slippage_bps=80.0, exec_fills=12)})
    assert d.weights["bounce"] == 0.0 and "killed" in d.reasons["bounce"]
    assert d.weights["carry"] == 0.0 and "paper only" in d.reasons["carry"]
    assert d.weights["x"] == pytest.approx(0.25) and "HALVED" in d.reasons["x"]


def test_drawdown_kill_persists_until_resumed(tmp_path):
    path = tmp_path / "a.json"
    a = Allocator(AllocatorConfig(max_drawdown_real=0.25), path)
    a.decide({"bounce": ev(real_equity=200.0)})
    d = a.decide({"bounce": ev(real_equity=140.0)})           # -30%
    assert d.weights["bounce"] == 0.0 and d.reasons["bounce"].startswith("KILLED")
    b = Allocator(AllocatorConfig(max_drawdown_real=0.25), path)   # restart keeps the kill
    assert "bounce" in b.killed
    d = b.decide({"bounce": ev(real_equity=190.0)})           # recovered, still killed until resumed
    assert d.weights["bounce"] == 0.0
    b.resume("bounce", 190.0)
    d = b.decide({"bounce": ev(real_equity=190.0)})
    assert d.weights["bounce"] > 0 and b.peaks["bounce"] == 190.0


def test_manual_mode_and_validation(tmp_path):
    a = Allocator(AllocatorConfig(), tmp_path / "a.json")
    assert a.set_manual({"bounce": 0.7, "carry": 0.5}) == (False, "weights add up to more than 100% (no leverage)")
    assert a.set_manual({"bounce": "x"})[0] is False
    ok, _ = a.set_manual({"bounce": 0.3})
    assert ok and a.mode == "manual"
    d = a.decide({"bounce": ev()})
    assert d.weights["bounce"] == 0.3 and d.reasons["bounce"].startswith("manual")
    assert a.set_mode("auto") == (True, "")
    d = a.decide({"bounce": ev()})
    assert d.weights["bounce"] == 0.5
    assert len(a.history) >= 2                      # changes are recorded


def test_scales_down_when_total_exceeds_max_deploy(tmp_path):
    a = Allocator(AllocatorConfig(learning_floor=0.6, max_deploy=1.0), tmp_path / "a.json")
    d = a.decide({"a": ev(name="a"), "b": ev(name="b")})
    assert d.weights["a"] == pytest.approx(0.5) and d.weights["b"] == pytest.approx(0.5) and d.cash == 0.0
