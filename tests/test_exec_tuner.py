import time
from dataclasses import dataclass

from cryptobot import exec_tuner as XT


def test_decide_widens_tightens_and_waits_for_evidence():
    cfg = XT.TunerConfig(min_attempts=10)
    assert XT.decide(0.005, 3, 2, 10.0, cfg)[0] == 0.005                        # too few attempts
    new, why = XT.decide(0.005, 7, 3, 10.0, cfg)                                 # 30% unfilled
    assert new == 0.00625 and why.startswith("widen")
    new, why = XT.decide(0.005, 20, 0, 5.0, cfg)                                 # all filled, 5 bp vs 50 bp limit
    assert new == 0.004 and why.startswith("tighten")
    assert XT.decide(0.005, 20, 0, 30.0, cfg)[0] == 0.005                        # fills, but slippage near the limit
    assert XT.decide(0.02, 5, 5, 10.0, cfg)[0] == 0.02                           # at the cap
    assert XT.decide(0.001, 20, 0, 1.0, cfg)[0] == 0.001                         # at the floor


@dataclass
class Cfg:
    max_slippage: float = 0.005


class Ex:
    def __init__(self):
        self.cfg = Cfg()


def test_apply_changes_executor_persists_and_respects_cooldown(tmp_path):
    path = tmp_path / "exec_tuning.json"
    tuner = XT.ExecTuner(XT.TunerConfig(min_attempts=10, cooldown_s=3600), path)
    ex = Ex()
    t = tuner.apply("bounce", ex, {"fills": 7, "unfilled": 3, "slippage_bps_all": [10.0] * 7})
    assert t.changed and ex.cfg.max_slippage == 0.00625
    t2 = tuner.apply("bounce", ex, {"fills": 7, "unfilled": 3, "slippage_bps_all": [10.0] * 7})
    assert not t2.changed and ex.cfg.max_slippage == 0.00625 and "cooldown" in t2.reason
    fresh = XT.ExecTuner(XT.TunerConfig(), path)                     # restart restores the learned limit
    ex2 = Ex()
    fresh.apply("bounce", ex2, None)
    assert ex2.cfg.max_slippage == 0.00625
