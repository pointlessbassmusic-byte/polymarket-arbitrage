import json
import random

from cryptobot import review as R


def _bench(mean=0.03, n=120):
    rng = random.Random(1)
    trades = [{"coin": "DOGE", "date": "2024-01-01", "ret": rng.gauss(mean, 0.08), "exit": "time_exit"} for _ in range(n)]
    return {"coins": ["DOGE"], "n": n, "mean": mean, "hit": 0.55, "first": "2022-01-01", "last": "2026-09-01",
            "exits": {"take_profit": 0.25, "stop_loss": 0.37, "time_exit": 0.38}, "trades": trades}


def test_compare_flags_a_live_record_far_below_the_backtest():
    bench = _bench()
    bad = [{"pnl_usd": -10.0, "size_usd": 100.0, "exit_reason": "stop_loss"}] * 12
    c = R.compare(bad, bench)
    assert c["n"] == 12 and c["p_low"] < 0.05 and c["status"].startswith("WARNING")
    ok = [{"pnl_usd": 3.0, "size_usd": 100.0, "exit_reason": "time_exit"}] * 12
    assert R.compare(ok, bench)["status"] == "within the backtest's range"
    assert R.compare(ok[:3], bench)["status"] == "too few trades to judge"


def test_render_reads_the_desk_books(tmp_path):
    (tmp_path / "cryptobot_real_portfolio.json").write_text(json.dumps({"closed": [
        {"pnl_usd": 5.0, "size_usd": 100.0, "exit_reason": "take_profit"}] * 6}))
    out = R.render(tmp_path, _bench())
    assert "real: 6 closed" in out and "sim: no closed trades yet" in out and "forward tests:" in out


def test_shipped_benchmark_is_present_and_sane():
    b = json.loads(R.BENCH.read_text())
    assert b["n"] >= 50 and abs(sum(b["exits"].values()) - 1) < 1e-9
