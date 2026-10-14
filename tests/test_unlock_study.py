import json

from cryptobot import unlock_study as U


def _chart(days, supply_jump_day=None, drift=0.0):
    t0 = 1_760_000_000_000
    prices, caps = [], []
    px, sup = 1.0, 1e9
    for i in range(days):
        if supply_jump_day is not None and i == supply_jump_day:
            sup *= 1.05
        if supply_jump_day is not None and supply_jump_day - 20 <= i <= supply_jump_day + 10:
            px *= (1 + drift)
        prices.append([t0 + 86400000 * i, px])
        caps.append([t0 + 86400000 * i, px * sup])
    return {"prices": prices, "market_caps": caps}


def test_unlock_drift_is_found(tmp_path):
    d = tmp_path / "unlocks"
    d.mkdir()
    (d / "bitcoin.json").write_text(json.dumps(_chart(200)))
    for k, coin in enumerate(U.COINS[:12]):
        (d / f"{coin}.json").write_text(json.dumps(_chart(200, supply_jump_day=60 + k, drift=-0.004)))
    res = U.run(tmp_path)
    assert res["events"]["n"] == 12
    assert res["events"]["mean"] > 0.08          # ~ -11.4% token move, shorted, less 1.26% costs
    assert U.render(res)
