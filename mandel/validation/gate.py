"""
The gate.
=========

``evaluate`` turns a pre-registered proposal plus reported evidence into an
accept/reject decision with reasons. It is deliberately dumb: it applies the
criteria that were frozen before the experiment, checks the structural
honesty conditions (out-of-sample flag, trial count, finite numbers), and
refuses to be clever on anyone's behalf. It is statistical, not a proof:
every accepted proposal carries the false-accept risk of its criteria.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from mandel.proposals import Criterion, Proposal
from mandel.validation.backtest_eval import ComparisonResult

STRUCTURAL_EXEMPT_METRICS = {"tests_pass", "lint_pass", "typecheck_pass"}


@dataclass
class CheckResult:
    metric: str
    comparator: str
    threshold: float
    observed: Optional[float]
    passed: bool
    note: str = ""

    def as_dict(self) -> dict:
        return {"metric": self.metric, "comparator": self.comparator, "threshold": self.threshold,
                "observed": self.observed, "passed": self.passed, "note": self.note}


@dataclass
class GateResult:
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def rationale(self) -> str:
        head = "PASS" if self.passed else "FAIL"
        parts = [f"{c.metric} {c.comparator} {c.threshold}: observed={c.observed} -> {'ok' if c.passed else 'FAIL'}"
                 + (f" ({c.note})" if c.note else "") for c in self.checks]
        return f"{head}; " + "; ".join(parts + self.reasons)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "checks": [c.as_dict() for c in self.checks], "reasons": list(self.reasons)}


def _as_number(value) -> Optional[float]:
    """Finite float from a numeric evidence value; None for bool, non-numeric or non-finite."""
    if isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _as_count(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    f = _as_number(value)
    if f is None or f < 1 or f != int(f):
        return None
    return int(f)


def evaluate(proposal: Proposal, evidence: Optional[dict] = None) -> GateResult:
    ev = dict(proposal.evidence)
    if evidence:
        ev.update(evidence)
    proposal.check_integrity()

    checks: list[CheckResult] = []
    reasons: list[str] = []
    passed = True

    # Structural honesty conditions -------------------------------------
    needs_oos = any(c.metric not in STRUCTURAL_EXEMPT_METRICS for c in proposal.criteria)
    if needs_oos:
        if ev.get("out_of_sample") is not True:
            passed = False
            reasons.append("evidence not marked out_of_sample=True; in-sample results do not count")
        if "n_trials" not in ev:
            passed = False
            reasons.append("n_trials not reported; the honest trial count is required")
        else:
            n_trials = _as_count(ev.get("n_trials"))
            if n_trials is None:
                passed = False
                reasons.append(f"n_trials must be a positive integer, got {ev.get('n_trials')!r}")
            elif n_trials > proposal.n_trials_declared:
                passed = False
                reasons.append(f"ran {n_trials} trials but pre-registered {proposal.n_trials_declared}; re-register")

    # Criteria ------------------------------------------------------------
    for crit in proposal.criteria:
        if crit.metric not in ev:
            checks.append(CheckResult(crit.metric, crit.comparator, crit.threshold, None, False, "metric not reported"))
            passed = False
            continue
        raw = ev[crit.metric]
        if crit.metric in STRUCTURAL_EXEMPT_METRICS and isinstance(raw, bool):
            raw = 1.0 if raw else 0.0
        obs = _as_number(raw)
        if obs is None:
            checks.append(CheckResult(crit.metric, crit.comparator, crit.threshold, None, False,
                                      f"value {raw!r} is not a finite number"))
            passed = False
            continue
        ok = crit.holds(obs)
        checks.append(CheckResult(crit.metric, crit.comparator, crit.threshold, obs, ok))
        passed = passed and ok

    return GateResult(passed=passed, checks=checks, reasons=reasons)


# --------------------------------------------------------------------------
# Standard criteria sets and evidence builders
# --------------------------------------------------------------------------

def strategy_improvement_criteria(max_p: float = 0.05, min_dsr: float = 0.95) -> list[Criterion]:
    """Candidate trading strategy must beat the incumbent out of sample."""
    return [
        Criterion("sharpe_diff", ">", 0.0, "candidate per-period Sharpe minus incumbent's"),
        Criterion("mean_diff", ">", 0.0, "mean per-period return difference"),
        Criterion("bootstrap_p", "<=", max_p, "block-bootstrap one-sided p-value"),
        Criterion("dsr", ">=", min_dsr, "deflated Sharpe ratio of the candidate"),
    ]


def forecast_improvement_criteria(min_n: int = 30) -> list[Criterion]:
    """Candidate forecaster must lower the Brier score and beat the market on held-out questions."""
    return [
        Criterion("n_resolved", ">=", float(min_n), "resolved held-out questions"),
        Criterion("brier_delta", "<", 0.0, "candidate Brier minus incumbent Brier (negative is better)"),
        Criterion("skill_vs_market", ">", 0.0, "Brier skill score against the market price at forecast time"),
    ]


def code_change_criteria() -> list[Criterion]:
    return [Criterion("tests_pass", "==", 1.0, "full test suite passes")]


def evidence_from_comparison(res: ComparisonResult, *, holdout_id: str) -> dict:
    """Build gate evidence from a comparison. ``holdout_id`` names the held-out window or
    split the returns came from; it is what makes the out-of-sample claim auditable."""
    if not isinstance(holdout_id, str) or not holdout_id.strip():
        raise ValueError("holdout_id is required: name the held-out window these returns came from")
    return {
        "sharpe_diff": res.candidate_sharpe - res.incumbent_sharpe,
        "mean_diff": res.mean_diff,
        "bootstrap_p": res.bootstrap_p,
        "dsr": res.candidate_dsr,
        "n_trials": res.n_trials,
        "n_periods": res.n_periods,
        "holdout_id": holdout_id.strip(),
        "out_of_sample": True,
        "notes": list(res.notes),
    }
