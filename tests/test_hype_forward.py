import json
import random

from cryptobot import hype_forward as H


def _write_rows(tmp_path, hours=600, spike_every=150):
    d = tmp_path / "hype"
    d.mkdir()
    rng = random.Random(3)
    t0 = 1_790_000_000 // 3600 * 3600
    rows = []
    for i in range(hours):
        spike = i % spike_every == spike_every - 1
        tw = {c: {"rate_per_h": (40.0 if (spike and c == "DOGE") else 2.0), "bull": 1, "bear": 1} for c in H.COINS}
        memes = [{"symbol": "DOGE", "vol24": 1e9 * (5 if spike else 1.0)}]
        rows.append({"ts": t0 + 3600 * i, "trending": [], "memes": memes, "twits": tw, "fng": 50, "errors": []})
    (d / "2026-10-20.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return t0, rows


def test_spikes_become_events_and_a_fade_is_scored(tmp_path):
    t0, rows = _write_rows(tmp_path)
    spikes = {r["ts"] for i, r in enumerate(rows) if i % 150 == 149}

    def price(coin):
        out = {}
        for i in range(800):
            t = t0 + 3600 * i
            p = 100.0
            if coin == "DOGE":
                for s in spikes:      # DOGE drops 5% over the 24 h after each spike
                    if s <= t:
                        p *= 0.95 ** min(1.0, (t - s) / (24 * 3600))
            out[t] = p
        return out

    res = H.run(tmp_path, price=price)
    assert res["events"] >= 2
    s24 = res["by_horizon"][24]
    assert s24["n"] >= 2 and s24["mean"] > 0.03
    assert "verdict" in H.render(res, "test")


def test_guard_refuses_before_the_read_date(tmp_path, capsys):
    _write_rows(tmp_path, hours=50)
    H.main(["--state", str(tmp_path)])
    assert "days to go" in capsys.readouterr().out
