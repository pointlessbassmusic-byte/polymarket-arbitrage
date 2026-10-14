"""
Experiments: the trial math, executable.
=========================================

Each experiment is a harness that takes data (arrays or observation rows),
computes a pre-declared statistic against a pre-declared null, and returns
an ``ExperimentResult`` that is recorded in ``state/experiments.jsonl`` and
in the ledger. Theories in ``mandel/theories/registry.json`` map onto
harness ids; a theory's status moves from ``untested`` to ``supported``,
``not_supported`` or ``inconclusive`` only through a recorded result.

Harness ids (see each module):
  market_calibration, bundle_arb_scan, multifractal_scaling, markov_baseline,
  multiscale_edge, hurst_ci, msm_volatility, controls, dsr_pbo_harness,
  cost_accounting
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from mandel._io import append_line, jsonable
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path

VERDICTS = ("supported", "not_supported", "inconclusive", "error")


@dataclass
class ExperimentResult:
    id: str
    harness: str
    theory_ids: list[str]
    statistic: dict                 # named numbers
    null: str                       # what the null was and how it was simulated
    n: int                          # sample size that the verdict rests on
    verdict: str                    # supported | not_supported | inconclusive | error
    reason: str                     # one sentence
    data_bundles: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)      # wall_seconds, rows, api_calls
    created_at: str = field(default_factory=utcnow_iso)

    def as_dict(self) -> dict:
        return jsonable(asdict(self))


class ExperimentLog:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("experiments.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()

    def record(self, harness: str, theory_ids: list[str], statistic: dict, null: str, n: int, verdict: str, reason: str,
               data_bundles: list[str] = (), params: Optional[dict] = None, cost: Optional[dict] = None,
               actor: str = "mandel") -> ExperimentResult:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        res = ExperimentResult(id="X-" + uuid.uuid4().hex[:8], harness=harness, theory_ids=list(theory_ids),
                               statistic=jsonable(statistic), null=null, n=int(n), verdict=verdict, reason=reason,
                               data_bundles=list(data_bundles), params=jsonable(params or {}), cost=jsonable(cost or {}))
        append_line(self.path, json.dumps(res.as_dict(), ensure_ascii=False))
        self.ledger.append("experiment.recorded", {"id": res.id, "harness": harness, "theory_ids": res.theory_ids,
                                                   "verdict": verdict, "n": res.n, "statistic": res.statistic}, actor=actor)
        return res

    def all(self) -> list[ExperimentResult]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(ExperimentResult(**json.loads(line)))
        return out

    def latest_by_harness(self) -> dict[str, ExperimentResult]:
        latest: dict[str, ExperimentResult] = {}
        for r in self.all():
            latest[r.harness] = r
        return latest
