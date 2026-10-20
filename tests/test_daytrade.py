import datetime as dt

from cryptobot import daytrade as D


def _ts(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp()


def test_windows():
    assert D.window(_ts(2026, 10, 19, 13, 30)) == "bull"       # Monday 13:30 UTC
    assert D.window(_ts(2026, 10, 19, 16, 0)) is None
    assert D.window(_ts(2026, 10, 18, 14, 0)) is None          # Sunday
    assert D.window(_ts(2026, 10, 19, 22, 15)) == "bear"       # Monday evening
    assert D.window(_ts(2026, 10, 20, 2, 45)) == "bear"        # spills past midnight into Tuesday
    assert D.window(_ts(2026, 10, 19, 2, 0)) is None           # Monday 02:00 belongs to Sunday's start: excluded
    assert D.window(_ts(2026, 10, 24, 1, 0)) == "bear"         # Saturday 01:00 belongs to Friday's session


def _bars_with_cross(start, n_flat=40, rise=0.002, after=None):
    """Flat, then a dip and a rise that makes EMA9 cross above EMA21 inside the bull window."""
    bars, p = [], 100.0
    for i in range(n_flat):
        bars.append((start + 900 * i, p, p * 1.001, p * 0.999, p, 10.0))
    t = start + 900 * n_flat
    for k in range(6):
        p *= 0.997
        bars.append((t, p, p * 1.001, p * 0.999, p, 10.0)); t += 900
    for k in range(6):
        o = p
        p *= 1 + rise
        bars.append((t, o, max(o, p) * 1.0005, min(o, p) * 0.9995, p, 10.0)); t += 900
    for step in (after or []):
        o = p
        p *= 1 + step
        bars.append((t, o, max(o, p) * 1.0005, min(o, p) * 0.9995, p, 10.0)); t += 900
    return bars


def test_v0_long_hits_target_and_costs_are_charged():
    start = _ts(2026, 10, 19, 13, 45) - 900 * 54    # the EMA cross lands on bar 54: 13:45 Monday
    bars = _bars_with_cross(start, after=[0.004] * 8)
    tr = D.backtest(bars, "V0", "BTC")
    longs = [t for t in tr if t["side"] == 1]
    assert longs and longs[0]["reason"] == "target"
    assert abs(longs[0]["gross_bp"] - 150) < 1e-6
    assert abs(longs[0]["net_bp"] - (150 - D.cost_bp("BTC"))) < 1e-6


def test_flat_out_of_hours():
    start = _ts(2026, 10, 19, 15, 30) - 900 * 54    # cross at 15:30, entry 15:45, the window ends 16:00
    bars = _bars_with_cross(start, after=[0.004] * 3 + [0.0] * 6)
    tr = D.backtest(bars, "V0", "BTC")
    assert any(t["reason"] == "flat_out_of_hours" for t in tr)


def test_paper_bot_logs_trades_once_and_survives_restart(tmp_path):
    import asyncio
    import httpx
    from cryptobot import daytrade_bot as B

    start = _ts(2026, 10, 19, 13, 45) - 900 * 54
    bars = _bars_with_cross(start, after=[0.004] * 8)
    clock = {"now": bars[-1][0] + 901}

    def handler(req: httpx.Request):
        return httpx.Response(200, json=[[b[0], b[3], b[2], b[1], b[4], b[5]] for b in reversed(bars)])

    async def run():
        c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        bot = B.DayTradeBot(tmp_path, {"assets": ["BTC"], "variants": ["V0"]}, client=c, now=lambda: clock["now"])
        bot.started = bars[0][0]                       # count the replayed trade as a paper trade for the test
        n1 = await bot.step()
        bot2 = B.DayTradeBot(tmp_path, {"assets": ["BTC"], "variants": ["V0"]}, client=c, now=lambda: clock["now"])
        bot2.started = bars[0][0]
        n2 = await bot2.step()                          # a restart replays the same bars: nothing is logged twice
        await c.aclose()
        return n1, n2
    n1, n2 = asyncio.run(run())
    assert n1 == 1 and n2 == 0
    r = B.report(tmp_path)
    assert r["trades"] == 1 and r["by_variant"]["V0"]["net_bp"] > 0
    assert "paper" in B.render(r)
    assert r["instruments"]["V0"]["spot"][0] == 1
    bins = [l for l in (tmp_path / "daytrade" / "binaries.jsonl").read_text().splitlines() if l]
    assert len(bins) == 1                               # the entry, scored as 15-minute and hourly binaries, once


def test_binary_pricing_and_scoring():
    assert D.binary_fee(0.51) == 0.02                  # 0.07 x 0.51 x 0.49 = 1.75 cents, rounded up
    assert abs(D.binary_bp(True) - (1 / 0.53 - 1) * 1e4) < 1e-6
    assert D.binary_bp(False) == -1e4
    t0 = 1_800_000_000 // 900 * 900
    bars = {t0 + 900 * i: (t0 + 900 * i, 100 + i, 101 + i, 99 + i, 100.5 + i, 1.0) for i in range(4)}
    assert D.binary_win(1, bars, t0, 15) is True       # 100 -> 100.5
    assert D.binary_win(-1, bars, t0, 60) is False     # 100 -> 103.5: the DOWN binary loses
    assert D.binary_win(1, bars, t0 + 900, 60) is None  # the hour is not complete
    tr = {"asset": "BTC", "side": -1, "entry_ts": t0, "net_bp": 10.0, "gross_bp": 18.4}
    sc = D.score(tr, bars)
    assert sc["spot"] is None and sc["perp"] == 10.0 and sc["bin15"] == -1e4
    tr["side"] = 1
    assert abs(D.score(tr, bars)["spot"] - (18.4 - D.spot_cost_bp("BTC"))) < 1e-9
