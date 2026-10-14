import pytest

from cryptobot import polymarket_history as P


def test_inverse_of_a_resolved_loser_and_winner():
    loser = {"entry": 0.20, "ret": -1.0}           # paid 20c, ended worth 0
    winner = {"entry": 0.80, "ret": 0.25}          # paid 80c, ended worth 1
    # opposite of the loser: paid 80c for the other side, ended worth 1 -> +25%
    assert abs(P.inverse_ret(loser, 0.0) - 0.25) < 1e-9
    # opposite of the winner: paid 20c, ended worth 0 -> -100%
    assert abs(P.inverse_ret(winner, 0.0) + 1.0) < 1e-9
    # a spread makes the inverse worse
    assert P.inverse_ret(loser, 0.02) < P.inverse_ret(loser, 0.0)


def test_analyse_finds_the_losing_cell():
    closed = []
    for i in range(40):
        # crypto up/down longshots that lose 9 times in 10
        won = i % 10 == 0
        closed.append({"avgPrice": 0.15, "totalBought": 100, "realizedPnl": (100 - 15) if won else -15, "curPrice": 1 if won else 0,
                       "slug": f"btc-updown-15m-{i}", "title": "Bitcoin Up or Down", "outcomeIndex": 0, "asset": f"a{i}"})
    for i in range(10):
        closed.append({"avgPrice": 0.6, "totalBought": 50, "realizedPnl": 20, "curPrice": 1, "slug": f"nba-x-{i}",
                       "title": "Lakers vs Celtics", "outcomeIndex": 1, "asset": f"b{i}"})
    res = P.analyse({"closed": closed, "open": [], "activity": []})
    assert res["closed"] == 50
    assert res["by_category"]["crypto up/down"]["pnl"] < 0
    assert res["rules"] and res["rules"][0]["cell"].startswith("crypto up/down")
    assert P.render(res)


def test_rejects_bad_address():
    with pytest.raises(ValueError):
        P.History("not-an-address")
