from cryptobot import hedge_study as HS


def test_beta_is_long_btc_when_trades_lose_in_rallies():
    # trade pnl falls 0.5 for every +1 of BTC: hedge beta should come out +0.5 (long BTC)
    trades = [{"year": 2023, "ts": i * 86400.0, "pnl": -0.5 * b, "btc": b}
              for i, b in enumerate([x / 100 for x in range(-20, 21)])]
    trades += [{"year": 2024, "ts": 1e7 + i * 86400.0, "pnl": -0.5 * b, "btc": b}
               for i, b in enumerate([x / 100 for x in range(-10, 11)])]
    btc = {int(r["ts"] // 86400) * 86400: r["btc"] for r in trades}
    rows = HS.study(trades, btc, cost=0.0)
    y24 = next(r for r in rows if r["year"] == 2024)
    assert abs(y24["beta"] - 0.5) < 1e-9
    assert y24["hedged"]["sd"] < y24["unhedged"]["sd"]           # perfectly hedged: variance gone
    assert "hedged Sharpe higher in" in HS.render(rows)
