import json

from cryptobot import weather_study as W


def test_bucket_probabilities_sum_to_one_and_respect_integer_degrees():
    mu, sd = 72.3, 2.0
    ms = [{"strike_type": "less", "cap": 69}, {"strike_type": "between", "floor": 69, "cap": 70},
          {"strike_type": "between", "floor": 71, "cap": 72}, {"strike_type": "between", "floor": 73, "cap": 74},
          {"strike_type": "between", "floor": 75, "cap": 76}, {"strike_type": "greater", "floor": 76}]
    ps = [W.bucket_prob(m, mu, sd) for m in ms]
    assert abs(sum(ps) - 1) < 1e-9
    assert max(ps) == ps[2] or max(ps) == ps[3]


def test_daily_max_uses_local_standard_time(tmp_path):
    times = [f"2026-07-01T{h:02d}:00" for h in range(24)] + [f"2026-07-02T{h:02d}:00" for h in range(24)]
    vals = [60.0] * 48
    vals[4] = 99.0          # 04:00 UTC on Jul 1 = 23:00 EST on Jun 30: belongs to Jun 30's climate day
    vals[20] = 80.0         # 20:00 UTC on Jul 1 = 15:00 EST on Jul 1
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"hourly": {"time": times, "temperature_2m_previous_day1": vals}}))
    d = W.daily_max(p, -5)
    assert d["2026-07-01"] == 80.0
    assert "2026-06-30" not in d or d["2026-06-30"] == 99.0


def test_event_day_and_decision_times():
    assert W.event_day({"event": "KXHIGHNY-26OCT13"}) == "2026-10-13"
    assert W.decision_ts("2026-10-13", "eve") < W.decision_ts("2026-10-13", "morning")
