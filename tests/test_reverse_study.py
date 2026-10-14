from cryptobot import reverse_study as RS
from cryptobot.perp_study import Barrier


def test_first_adverse_day_respects_conservative_ordering():
    cd = {"high": [1.0, 1.05, 1.12, 1.3], "low": [1.0, 0.95, 0.75, 0.9], "close": [1.0, 1.0, 1.0, 1.0]}
    # day 2 touches both the +10% stop and the -20% target: the stop counts first
    assert RS.first_adverse_day(cd, 0, 1.0, 0.10, 0.20, 14) == 2
    cd2 = {"high": [1.0, 1.02, 1.05], "low": [1.0, 0.79, 0.9], "close": [1.0, 1.0, 1.0]}
    assert RS.first_adverse_day(cd2, 0, 1.0, 0.10, 0.20, 14) is None          # target first


def test_reversal_outcome_scores_a_long_from_the_stop():
    cd = {"high": [1.0, 1.1, 1.15, 1.4], "low": [1.0, 1.0, 1.05, 1.2], "close": [1.0, 1.1, 1.12, 1.35]}
    # long from 1.10 with +20% target (1.32) reached on day 3 before any -10% stop
    assert RS.reversal_outcome(cd, 1, 1.10, Barrier(0.20, 0.10), 14) == 0.20
