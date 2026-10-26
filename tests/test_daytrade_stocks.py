import datetime as dt
import pickle
import random
from zoneinfo import ZoneInfo

from cryptobot import daytrade as D
from cryptobot import daytrade_stocks_study as S
from cryptobot.data.geckoterminal import Candle

ET = ZoneInfo("America/New_York")


def _et(d, h, m):
    return dt.datetime.combine(d, dt.time(h, m), ET).timestamp()


def test_stock_windows_follow_new_york_time_across_dst():
    assert D.stock_window(_et(dt.date(2026, 10, 19), 9, 30)) == "am"      # EDT
    assert D.stock_window(_et(dt.date(2026, 12, 14), 9, 30)) == "am"      # EST: a different UTC hour
    assert D.stock_window(_et(dt.date(2026, 10, 19), 12, 15)) is None
    assert D.stock_window(_et(dt.date(2026, 10, 19), 15, 50)) == "pm"
    assert D.stock_window(_et(dt.date(2026, 10, 19), 15, 55)) is None
    assert D.stock_window(_et(dt.date(2026, 10, 18), 10, 0)) is None      # Sunday


def _session(d, rng, px):
    out = []
    t = dt.datetime.combine(d, dt.time(9, 30), ET)
    while t.time() < dt.time(16, 0):
        o = px
        px *= 1 + rng.gauss(0, 0.001)
        out.append(Candle(ts=int(t.timestamp()), open=o, high=max(o, px) * 1.0003, low=min(o, px) * 0.9997,
                          close=px, volume_usd=1e6))
        t += dt.timedelta(minutes=5)
    return out, px


def test_study_runs_on_cached_bars_and_charges_stock_costs(tmp_path):
    rng = random.Random(3)
    bars, px, d = [], 500.0, dt.date(2025, 1, 6)
    while len({dt.datetime.fromtimestamp(b.ts, ET).date() for b in bars}) < 60:
        if d.weekday() < 5:
            s, px = _session(d, rng, px)
            bars += s
        d += dt.timedelta(days=1)
    pre = [Candle(ts=bars[0].ts - 3600, open=1, high=1, low=1, close=1, volume_usd=1)]   # pre-market: dropped
    (tmp_path / "SPY_5m.pkl").write_bytes(pickle.dumps(pre + bars))
    res = S.run(tmp_path)
    assert set(res["cells"]) == {f"{v}|{f}|SPY|{i}" for v in ("V1", "V2") for f in ("15m", "30m") for i in ("etf", "perp")}
    c = res["cells"]["V1|15m|SPY|etf"]
    assert c["n"] > 20 and abs((c["gross"] - c["net"]) - S.etf_cost_bp("SPY")) < 1e-9
    p = res["cells"]["V1|15m|SPY|perp"]
    assert abs((p["gross"] - p["net"]) - S.PERP_BP) < 1e-9
    assert res["trials"] == 8 and "verdict" in S.render(res)
    tr = D.backtest(S.resample(S.regular_hours(bars), 900), "V2", "SPY", window_fn=D.stock_window, cost=1.0)
    for t in tr:                                     # V2 never enters before 10:00 (the opening range must be complete)
        assert dt.datetime.fromtimestamp(t["entry_ts"], ET).time() > dt.time(10, 0)
