import json
import random

from cryptobot import maker_taker_study as M


def _tape(tmp_path, adverse: float, n=6000, seed=1, step_sd=0.02):
    """Fair value follows a random walk; takers buy at FV + half-spread and
    sell at FV - half-spread; with `adverse`, takers trade ahead of the
    next move (informed flow)."""
    rng = random.Random(seed)
    fv, t, rows = 100.0, 1_790_000_000.0, []
    half = 0.0005 * 100           # 5 bp half-spread
    for i in range(n):
        step = rng.gauss(0, step_sd)
        side = 1 if rng.random() < 0.5 else -1
        if adverse and rng.random() < adverse:
            side = 1 if step > 0 else -1
        rows.append([t, fv + side * half, 1.0 + rng.random() * 5, side, f"id{i}"])
        fv += step
        t += 6.0
    d = tmp_path / "tape"
    d.mkdir(exist_ok=True)
    (d / "KXDOGEPERP.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_uninformed_flow_pays_the_maker(tmp_path):
    _tape(tmp_path, adverse=0.0)
    res = M.run(tmp_path, ["KXDOGEPERP"])
    m = res["tickers"]["KXDOGEPERP"]["markout"]
    assert 2.0 < m[10]["maker_gross_bp"] < 8.0          # about the 5 bp half-spread
    assert M.render(res)


def test_informed_flow_hurts_the_maker(tmp_path):
    _tape(tmp_path, adverse=0.9, step_sd=0.15)          # informed moves (~12 bp) larger than the 5 bp half-spread
    res = M.run(tmp_path, ["KXDOGEPERP"])
    m = res["tickers"]["KXDOGEPERP"]["markout"]
    assert m[60]["maker_net_bp"] < 0
