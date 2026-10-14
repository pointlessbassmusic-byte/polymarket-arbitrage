"""
Validation: the gate that decides whether an "improvement" is real.
===================================================================

Modules
-------
- ``scoring``       proper scoring rules for probabilistic forecasts (Brier, log loss,
                    Murphy decomposition, calibration tables, skill scores)
- ``backtest_eval`` statistics for comparing strategies out of sample (walk-forward
                    splits with embargo, block bootstrap, probabilistic and deflated
                    Sharpe ratios)
- ``gate``          combines pre-registered criteria with evidence into an accept /
                    reject decision with reasons
"""

from mandel.validation.scoring import (  # noqa: F401
    brier_score,
    log_loss,
    murphy_decomposition,
    calibration_table,
    expected_calibration_error,
    brier_skill_score,
)
from mandel.validation.backtest_eval import (  # noqa: F401
    sharpe_ratio,
    probabilistic_sharpe_ratio,
    expected_max_sharpe,
    deflated_sharpe_ratio,
    block_bootstrap_pvalue,
    walk_forward_splits,
    compare_strategies,
    ComparisonResult,
)
from mandel.validation.gate import (  # noqa: F401
    evaluate,
    GateResult,
    CheckResult,
    strategy_improvement_criteria,
    forecast_improvement_criteria,
    code_change_criteria,
    evidence_from_comparison,
)
