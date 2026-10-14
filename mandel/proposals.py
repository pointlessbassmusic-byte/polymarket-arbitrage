"""
Improvement proposals with enforced pre-registration.
=====================================================

A proposal is Mandel's unit of self-improvement: a falsifiable hypothesis,
the change that tests it, and the success criteria written down *before*
any result is seen. The lifecycle is

    drafted -> preregistered -> evaluating -> accepted | rejected
                              -> withdrawn (only before evidence is seen)
    accepted -> rolled_back

Rules enforced in code, not by good intentions:

- Criteria can be edited only while ``drafted``. ``preregister`` freezes
  them and writes their hash to the ledger.
- The frozen hash is checked against the *ledger's* pre-registration event,
  not only against the proposals file, so loosening criteria by hand in
  the file is detected.
- Evidence is write-once per key. Re-recording a key with a different value
  is refused; the fix is a new proposal, not a corrected number.
- ``n_trials_declared`` is the honest count of variants that will be tried.
- Decisions are computed by the gate inside ``decide``; callers cannot pass
  a verdict.
- Re-drafting an identical hypothesis after a decision requires naming the
  proposal it supersedes, so the search history stays linked.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from mandel._io import atomic_write_text, file_lock, jsonable
from mandel.ledger import Ledger, canonical_json, utcnow_iso
from mandel.paths import data_path

STATUSES = ("drafted", "preregistered", "evaluating", "accepted", "rejected", "withdrawn", "rolled_back")
COMPARATORS = ("<", "<=", ">", ">=", "==")


class IntegrityError(RuntimeError):
    pass


class LifecycleError(RuntimeError):
    pass


@dataclass
class Criterion:
    metric: str
    comparator: str
    threshold: float
    description: str = ""

    def validate(self) -> None:
        if self.comparator not in COMPARATORS:
            raise ValueError(f"comparator must be one of {COMPARATORS}")
        if not str(self.metric).strip():
            raise ValueError("metric name is empty")
        if isinstance(self.threshold, bool):
            raise ValueError("threshold must be a number, not a boolean")
        try:
            self.threshold = float(self.threshold)
        except (TypeError, ValueError) as e:
            raise ValueError(f"threshold must be a number, got {self.threshold!r}") from e
        if not math.isfinite(self.threshold):
            raise ValueError("threshold must be finite")

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
    gate_result: dict = field(default_factory=dict)
    depends_on_insights: list[str] = field(default_factory=list)
    produces_insights: list[str] = field(default_factory=list)
    rollback: str = ""
    author: str = "mandel"
    supersedes: Optional[str] = None

    def compute_criteria_hash(self) -> str:
        body = {"criteria": [asdict(c) for c in self.criteria], "n_trials_declared": self.n_trials_declared,
                "hypothesis": self.hypothesis, "target": self.target}
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()

    def check_integrity(self) -> None:
        """Local check: frozen criteria must still hash to the recorded value."""
        if self.status != "drafted" and not self.criteria_hash:
            raise IntegrityError(f"proposal {self.id}: status {self.status} but no criteria hash recorded")
        if self.criteria_hash and self.compute_criteria_hash() != self.criteria_hash:
            raise IntegrityError(f"proposal {self.id}: criteria changed after pre-registration")


def _to_proposal(d: dict) -> Proposal:
    d = dict(d)
    d["criteria"] = [Criterion(**c) for c in d.get("criteria", [])]
    return Proposal(**d)


class ProposalBook:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("proposals.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self._items: dict[str, Proposal] = {}
        self._load()

    def _load(self) -> None:
        self._items = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        p = _to_proposal(json.loads(line))
                        self._items[p.id] = p

    def _flush(self) -> None:
        atomic_write_text(self.path, "".join(json.dumps(asdict(p), ensure_ascii=False) + "\n" for p in self._items.values()))

    # -- integrity against the ledger ------------------------------------
    def check_integrity(self, p: Proposal) -> None:
        p.check_integrity()
        if p.status == "drafted":
            return
        ev = self.ledger.find("proposal.preregistered", id=p.id)
        if ev is None:
            raise IntegrityError(f"proposal {p.id}: no pre-registration event in the ledger")
        if ev.payload.get("criteria_hash") != p.criteria_hash or p.compute_criteria_hash() != ev.payload.get("criteria_hash"):
            raise IntegrityError(f"proposal {p.id}: criteria differ from the ledger's pre-registration")

    def reconcile(self) -> list[str]:
        """Compare each proposal's file status with the ledger's last event for it."""
        problems: list[str] = []
        last_kind: dict[str, str] = {}
        for ev in self.ledger.events(kind="proposal."):
            pid = ev.payload.get("id")
            if pid:
                last_kind[pid] = ev.kind.split(".", 1)[1]
        for pid, p in self._items.items():
            lk = last_kind.get(pid)
            if lk is None:
                problems.append(f"{pid}: present in file but never drafted in the ledger")
                continue
            expected = {"drafted": "drafted", "preregistered": "preregistered", "evidence": "evaluating",
                        "accepted": "accepted", "rejected": "rejected", "withdrawn": "withdrawn",
                        "rolled_back": "rolled_back"}[lk]
            if p.status != expected:
                problems.append(f"{pid}: file says {p.status}, ledger says {expected}")
        for pid in last_kind:
            if pid not in self._items:
                problems.append(f"{pid}: in the ledger but missing from the file")
        return problems

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
        supersedes: Optional[str] = None,
    ) -> Proposal:
        crits = list(criteria)
        if not crits:
            raise ValueError("a proposal needs at least one success criterion")
        for c in crits:
            c.validate()
        if isinstance(n_trials_declared, bool) or int(n_trials_declared) != n_trials_declared or n_trials_declared < 1:
            raise ValueError("n_trials_declared must be an integer >= 1")
        p = Proposal(id="P-" + uuid.uuid4().hex[:8], title=title.strip(), hypothesis=hypothesis.strip(), target=target,
                     change=change.strip(), criteria=crits, n_trials_declared=int(n_trials_declared),
                     baseline=jsonable(dict(baseline or {})), depends_on_insights=list(depends_on_insights),
                     rollback=rollback, author=author, supersedes=supersedes)
        if not p.hypothesis:
            raise ValueError("hypothesis is empty")
        h = p.compute_criteria_hash()
        twins = [q for q in self._items.values() if q.compute_criteria_hash() == h and q.status != "withdrawn"]
        if twins and supersedes not in {q.id for q in twins}:
            raise LifecycleError(f"an identical hypothesis/criteria set already exists ({', '.join(q.id for q in twins)}); "
                                 f"pass supersedes=<id> to link the retry")
        if supersedes is not None and supersedes not in self._items:
            raise ValueError(f"supersedes names unknown proposal {supersedes}")
        with file_lock(self.path):
            self._load()
            self._items[p.id] = p
            self._flush()
        self.ledger.append("proposal.drafted", {"id": p.id, "title": p.title, "target": target, "supersedes": supersedes}, actor=author)
        return p

    def edit_criteria(self, proposal_id: str, criteria: Iterable[Criterion], n_trials_declared: Optional[int] = None) -> Proposal:
        p = self._items[proposal_id]
        if p.status != "drafted":
            raise LifecycleError("criteria are frozen after pre-registration; draft a new proposal")
        crits = list(criteria)
        if not crits:
            raise ValueError("a proposal needs at least one success criterion")
        for c in crits:
            c.validate()
        p.criteria = crits
        if n_trials_declared is not None:
            if n_trials_declared < 1:
                raise ValueError("n_trials_declared must be >= 1")
            p.n_trials_declared = int(n_trials_declared)
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
        self.check_integrity(p)
        clean = jsonable(dict(evidence))            # raises before any mutation
        if not clean:
            raise ValueError("evidence is empty")
        clash = {k for k, v in clean.items() if k in p.evidence and p.evidence[k] != v}
        if clash:
            raise LifecycleError(f"evidence keys {sorted(clash)} were already recorded; evidence is write-once "
                                 f"(draft a new proposal with supersedes={p.id})")
        p.evidence.update(clean)
        p.status = "evaluating"
        self._flush()
        self.ledger.append("proposal.evidence", {"id": p.id, "evidence": clean, "criteria_hash": p.criteria_hash}, actor=actor)
        return p

    def decide(self, proposal_id: str, produces_insights: Iterable[str] = (), actor: str = "mandel") -> Proposal:
        """Apply the gate and record the verdict. The caller does not get to choose it."""
        from mandel.validation.gate import evaluate   # local import: gate depends on this module's types
        p = self._items[proposal_id]
        if p.status != "evaluating":
            raise LifecycleError(f"decide requires status 'evaluating' (status={p.status}); record evidence first")
        self.check_integrity(p)
        g = evaluate(p)
        p.status = "accepted" if g.passed else "rejected"
        p.decided_at = utcnow_iso()
        p.decision = g.rationale()
        p.gate_result = g.as_dict()
        p.produces_insights = list(produces_insights) if g.passed else []
        self._flush()
        self.ledger.append(f"proposal.{p.status}", {"id": p.id, "rationale": p.decision, "evidence": p.evidence,
                                                     "gate": p.gate_result, "criteria_hash": p.criteria_hash,
                                                     "produces_insights": p.produces_insights}, actor=actor)
        return p

    def withdraw(self, proposal_id: str, reason: str, actor: str = "mandel") -> Proposal:
        p = self._items[proposal_id]
        if p.status == "evaluating":
            raise LifecycleError("evidence has already been seen; the proposal must be decided, not withdrawn")
        if p.status in ("accepted", "rejected", "rolled_back", "withdrawn"):
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
