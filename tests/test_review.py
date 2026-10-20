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


def test_review_once_warns_once_and_sends_weekly(tmp_path):
    import asyncio
    import datetime as dt

    class FakeAlerter:
        def __init__(self):
            self.sent = []

        async def send(self, text):
            self.sent.append(text)
            return True

    bad = [{"pnl_usd": -10.0, "size_usd": 100.0, "exit_reason": "stop_loss"}] * 12
    (tmp_path / "cryptobot_real_portfolio.json").write_text(json.dumps({"closed": bad}))
    a = FakeAlerter()
    tuesday = dt.datetime(2026, 10, 20, 13, 10, tzinfo=dt.timezone.utc)
    st = asyncio.run(R.review_once(tmp_path, a, now=tuesday))
    assert st.startswith("WARNING") and len(a.sent) == 1 and a.sent[0].startswith("REVIEW WARNING")
    asyncio.run(R.review_once(tmp_path, a, now=tuesday + dt.timedelta(days=1)))
    assert len(a.sent) == 1                                   # the warning is sent once, not every day
    monday = dt.datetime(2026, 10, 26, 13, 10, tzinfo=dt.timezone.utc)
    asyncio.run(R.review_once(tmp_path, a, now=monday))
    assert len(a.sent) == 2 and a.sent[1].startswith("weekly review")
    assert (tmp_path / "review_latest.txt").exists()
