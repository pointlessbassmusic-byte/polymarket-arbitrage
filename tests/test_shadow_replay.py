import datetime as dt
from types import SimpleNamespace

from cryptobot import shadow_replay as S
from cryptobot.review import load_bench


def _cs(path):
    t0 = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp()
    return [SimpleNamespace(ts=t0 + 86400 * i, open=p, high=p * 1.01, low=p * 0.99, close=p) for i, p in enumerate(path)]


def test_signal_then_target():
    path = [100.0 * (1.001 if i % 2 else 0.999) for i in range(100)]
    path += [96.0, 92.0, 90.0, 94.0]              # three days down, then a bounce: the signal day
    path += [94.0 * (1 - 0.03 * k) for k in range(1, 9)]   # the decline resumes past -20%
    tr = S.replay({"DOGE": _cs(path)}, since=dt.date(2026, 7, 1))
    hit = [t for t in tr if t["exit_reason"] == "take_profit"]
    assert hit and abs(hit[0]["ret"] - (0.20 - S.COST)) < 1e-9
    assert "take_profit" in S.render(tr, load_bench(), dt.date(2026, 10, 20))
