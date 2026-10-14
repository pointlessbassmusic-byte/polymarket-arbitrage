import datetime as dt
import json

from cryptobot import kalshi_carry_study as K


def test_carry_rule_collects_funding_and_charges_cost(tmp_path):
    days = [(dt.date(2026, 6, 1) + dt.timedelta(days=k)).isoformat() for k in range(120)]
    # 20%/yr funding every day: well above the 8% threshold
    fund = {"KXBTCPERP": [[d, 0.20 / 365] for d in days]}
    (tmp_path / "funding").mkdir()
    (tmp_path / "funding" / "kalshi_funding.json").write_text(json.dumps(fund))
    kh = tmp_path / "state_collect" / "kalshi_hourly"
    kh.mkdir(parents=True)
    t0 = int(dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp())
    (kh / "KXBTCPERP.jsonl").write_text("\n".join(json.dumps({"end_ts": t0 + 3600 * h, "open": 1, "high": 1, "low": 1, "close": 1.0, "volume": 1})
                                                  for h in range(24 * 120)) + "\n")
    (tmp_path / "btc5m").mkdir()
    (tmp_path / "btc5m" / "btc_5m.json").write_text(json.dumps([[t0 + 300 * k, 1, 1, 1, 1.0, 1] for k in range(288 * 120)]))
    res = K.run(tmp_path)
    r = res["rule"]
    assert r["n"] >= 6
    # 14 days at 20%/yr = 0.767%, minus 58 bp, flat basis
    assert abs(r["mean"] - (0.20 * 14 / 365 - K.COST)) < 1e-6
    assert K.render(res)
