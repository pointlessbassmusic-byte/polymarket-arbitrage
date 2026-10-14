"""
Improvement proposals with enforced pre-registration.
=====================================================

A proposal is Mandel's unit of self-improvement: a falsifiable hypothesis,
the change that tests it, and the success criteria written down *before*
any result is seen. The lifecycle is

    drafted -> preregistered -> evaluating -> accepted | rejected
                                           -> withdrawn
    accepted -> rolled_back

Rules enforced in code, not by good intentions:

- Criteria can be edited only while ``drafted``. ``preregister`` freezes
  them and writes their hash to the ledger.
- Evidence can be recorded only after pre-registration, and the criteria
  hash is re-checked at every step: if anyone edited the file by hand the
  proposal is poisoned and refuses to decide.
- ``n_trials_declared`` is the honest count of variants that will be tried.
  Evidence reporting more trials than declared fails the gate; the fix is a
  new pre-registration, not a bigger number after the fact.
- Decisions are made by ``mandel.validation.gate.evaluate``; the book only
  records them.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from mandel.ledger import Ledger, canonical_json, utcnow_iso
from mandel.paths import data_path

STATUSES = ("drafted", "preregistered", "evaluating", "accepted", "rejected", "withdrawn", "rolled_back")
COMPARATORS = ("<", "<=", ">", ">=", "==")


@dataclass
class Criterion:
    metric: str
    comparator: str
    threshold: float
    description: str = ""

    def validate(self) -> None:
        if self.comparator not in COMPARATORS:
            raise ValueError(f"comparator must be one of {COMPARATORS}")
        if not self.metric.strip():
            raise ValueError("metric name is empty")

    def holds(self, observed: float) -> bool:
        c, t = self.comparator, self.threshold
        return {"<": observed < t, "<=": observed <= t, ">": observed > t, ">=": observed >= t,
                "==": observed == t}[c]


@dataclass
class Proposal:
    id: str
    title: str
    hypothesis: str
    target: str                                  # "mandel:<module>" | "child:<name>" | "repo:<path>"
    change: str
    criteria: list[Criterion]
    n_trials_declared: int = 1
    baseline: dict = field(default_factory=dict)
    status: str = "drafted"
    created_at: str = field(default_factory=utcnow_iso)
    preregistered_at: Optional[str] = None
    decided_at: Optional[str] = None
    criteria_hash: Optional[str] = None
    evidence: dict = field(default_factory=dict)
    decision: str = ""
    depends_on_insights: list[str] = field(default_factory=list)
    produces_insights: list[str] = field(default_factory=list)
    rollback: str = ""
    author: str = "mandel"

    def compute_criteria_hash(self) -> str:
        body = {"criteria": [asdict(c) for c in self.criteria], "n_trials_declared": self.n_trials_declared,
                "hypothesis": self.hypothesis, "target": self.target}
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()

    def check_integrity(self) -> None:
        if self.criteria_hash and self.compute_criteria_hash() != self.criteria_hash:
            raise IntegrityError(f"proposal {self.id}: criteria changed after pre-registration")


class IntegrityError(RuntimeError):
    pass


class LifecycleError(RuntimeError):
    pass


def _to_proposal(d: dict) -> Proposal:
    d = dict(d)
    d["criteria"] = [Criterion(**c) for c in d.get("criteria", [])]
    return Proposal(**d)


class ProposalBook:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("proposals.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self._items: dict[str, Proposal] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        p = _to_proposal(json.loads(line))
                        self._items[p.id] = p

    def _flush(self) -> None:
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for p in self._items.values():
                f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
        tmp.replace(self.path)

    # -- lifecycle ---------------------------------------------------------
    def draft(
        self,
        title: str,
        hypothesis: str,
        target: str,
        change: str,
        criteria: Iterable[Criterion],
        n_trials_declared: int = 1,
        baseline: Optional[dict] = None,
        depends_on_insights: Iterable[str] = (),
        rollback: str = "",
        author: str = "mandel",
    ) -> Proposal:
        crits = list(criteria)
        if not crits:
            raise ValueError("a proposal needs at least one success criterion")
        for c in crits:
            c.validate()
        if n_trials_declared < 1:
            raise ValueError("n_trials_declared must be >= 1")
        p = Proposal(id="P-" + uuid.uuid4().hex[:8], title=title.strip(), hypothesis=hypothesis.strip(), target=target,
                     change=change.strip(), criteria=crits, n_trials_declared=n_trials_declared,
                     baseline=dict(baseline or {}), depends_on_insights=list(depends_on_insights),
                     rollback=rollback, author=author)
        self._items[p.id] = p
        self._flush()
        self.ledger.append("proposal.drafted", {"id": p.id, "title": p.title, "target": target}, actor=author)
        return p

    def edit_criteria(self, proposal_id: str, criteria: Iterable[Criterion], n_trials_declared: Optional[int] = None) -> Proposal:
        p = self._items[proposal_id]
        if p.status != "drafted":
            raise LifecycleError("criteria are frozen after pre-registration; draft a new proposal")
        crits = list(criteria)
        for c in crits:
            c.validate()
        p.criteria = crits
        if n_trials_declared is not None:
            p.n_trials_declared = n_trials_declared
        self._flush()
        return p

    def preregister(self, proposal_id: str, actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status != "drafted":
            raise LifecycleError(f"cannot pre-register from status {p.status}")
        p.criteria_hash = p.compute_criteria_hash()
        p.status = "preregistered"
        p.preregistered_at = utcnow_iso()
        self._flush()
        self.ledger.append("proposal.preregistered", {
            "id": p.id, "criteria_hash": p.criteria_hash, "criteria": [asdict(c) for c in p.criteria],
            "n_trials_declared": p.n_trials_declared, "hypothesis": p.hypothesis, "baseline": p.baseline,
        }, actor=actor)
        return p

    def record_evidence(self, proposal_id: str, evidence: dict, actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status not in ("preregistered", "evaluating"):
            raise LifecycleError(f"evidence requires a pre-registered proposal (status={p.status})")
        p.check_integrity()
        p.evidence.update(evidence)
        p.status = "evaluating"
        self._flush()
        self.ledger.append("proposal.evidence", {"id": p.id, "evidence": evidence, "criteria_hash": p.criteria_hash}, actor=actor)
        return p

    def decide(self, proposal_id: str, passed: bool, rationale: str, produces_insights: Iterable[str] = (), actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status != "evaluating":
            raise LifecycleError(f"decide requires status 'evaluating' (status={p.status}); record evidence first")
        p.check_integrity()
        p.status = "accepted" if passed else "rejected"
        p.decided_at = utcnow_iso()
        p.decision = rationale
        p.produces_insights = list(produces_insights)
        self._flush()
        self.ledger.append(f"proposal.{p.status}", {"id": p.id, "rationale": rationale, "evidence": p.evidence,
                                                     "criteria_hash": p.criteria_hash}, actor=actor)
        return p

    def withdraw(self, proposal_id: str, reason: str, actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status in ("accepted", "rejected", "rolled_back"):
            raise LifecycleError("cannot withdraw a decided proposal")
        p.status = "withdrawn"
        p.decided_at = utcnow_iso()
        p.decision = reason
        self._flush()
        self.ledger.append("proposal.withdrawn", {"id": p.id, "reason": reason}, actor=actor)
        return p

    def roll_back(self, proposal_id: str, reason: str, actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status != "accepted":
            raise LifecycleError("only accepted proposals can be rolled back")
        p.status = "rolled_back"
        p.decision = f"{p.decision} | ROLLED BACK: {reason}"
        self._flush()
        self.ledger.append("proposal.rolled_back", {"id": p.id, "reason": reason}, actor=actor)
        return p

    # -- queries -----------------------------------------------------------
    def get(self, proposal_id: str) -> Proposal:
        return self._items[proposal_id]

    def all(self) -> list[Proposal]:
        return sorted(self._items.values(), key=lambda p: p.created_at)

    def query(self, status: Optional[str] = None, target_prefix: Optional[str] = None) -> list[Proposal]:
        out = [p for p in self._items.values()
               if (status is None or p.status == status) and (target_prefix is None or p.target.startswith(target_prefix))]
        return sorted(out, key=lambda p: p.created_at)

    def summary(self) -> dict:
        counts = {s: 0 for s in STATUSES}
        for p in self._items.values():
            counts[p.status] += 1
        return {"total": len(self._items), "by_status": counts}
