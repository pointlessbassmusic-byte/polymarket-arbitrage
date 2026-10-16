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
- Decisions are computed by the gate inside ``decide`` from ledger events
  only (pre-registration + evidence); callers cannot pass a verdict, and a
  proposal whose file copy disagrees with the ledger refuses every step.
- ``reconcile`` replays the ledger for every proposal and recomputes every
  recorded verdict; ``python -m mandel verify`` fails on any disagreement.
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
    _LEDGER_STATUS = {"drafted": "drafted", "preregistered": "preregistered", "evidence": "evaluating",
                      "accepted": "accepted", "rejected": "rejected", "withdrawn": "withdrawn", "rolled_back": "rolled_back"}
    _ALLOWED_NEXT = {None: {"drafted"}, "drafted": {"preregistered", "withdrawn"}, "preregistered": {"evidence", "withdrawn"},
                     "evidence": {"evidence", "accepted", "rejected"}, "accepted": {"rolled_back"}, "rejected": set(),
                     "withdrawn": set(), "rolled_back": set()}

    def _history(self, proposal_id: str) -> list:
        """Ordered proposal.* events for one id, straight from the ledger."""
        return [ev for ev in self.ledger.events(kind="proposal.") if ev.payload.get("id") == proposal_id]

    def ledger_status(self, proposal_id: str) -> Optional[str]:
        hist = self._history(proposal_id)
        if not hist:
            return None
        return self._LEDGER_STATUS[hist[-1].kind.split(".", 1)[1]]

    def ledger_evidence(self, proposal_id: str) -> dict:
        """Merged evidence from every proposal.evidence event; the authoritative copy."""
        seen: dict = {}
        for ev in self._history(proposal_id):
            if ev.kind != "proposal.evidence":
                continue
            for k, v in (ev.payload.get("evidence") or {}).items():
                if k in seen and seen[k] != v:
                    raise IntegrityError(f"proposal {proposal_id}: ledger holds conflicting values for evidence key {k!r}")
                seen[k] = v
        return seen

    def proposal_from_ledger(self, proposal_id: str) -> Proposal:
        """Rebuild the frozen part of a proposal (criteria, trial count, hypothesis, target) and its
        merged evidence from ledger events alone. Used to recompute verdicts without trusting files."""
        drafted = self.ledger.find("proposal.drafted", id=proposal_id)
        prereg = self.ledger.find("proposal.preregistered", id=proposal_id)
        if drafted is None or prereg is None:
            raise IntegrityError(f"proposal {proposal_id}: ledger lacks drafted/preregistered events")
        q = Proposal(id=proposal_id, title=drafted.payload.get("title", ""), hypothesis=prereg.payload["hypothesis"],
                     target=drafted.payload.get("target", ""), change="",
                     criteria=[Criterion(**c) for c in prereg.payload["criteria"]],
                     n_trials_declared=int(prereg.payload["n_trials_declared"]), baseline=prereg.payload.get("baseline") or {},
                     status="evaluating", criteria_hash=prereg.payload["criteria_hash"], evidence=self.ledger_evidence(proposal_id))
        if q.compute_criteria_hash() != q.criteria_hash:
            raise IntegrityError(f"proposal {proposal_id}: pre-registration event is internally inconsistent")
        return q

    def gate_from_ledger(self, proposal_id: str):
        """Recompute the gate verdict from ledger events only (pre-registration + evidence)."""
        from mandel.validation.gate import evaluate
        q = self.proposal_from_ledger(proposal_id)
        if not q.evidence:
            raise IntegrityError(f"proposal {proposal_id}: no evidence events in the ledger")
        return evaluate(q)

    def check_integrity(self, p: Proposal) -> None:
        """The file copy must agree with the ledger: status, frozen criteria, evidence, decision."""
        p.check_integrity()
        hist = self._history(p.id)
        if not hist:
            raise IntegrityError(f"proposal {p.id}: present in file but never drafted in the ledger")
        kinds = [ev.kind.split(".", 1)[1] for ev in hist]
        prev = None
        for k in kinds:
            if k not in self._ALLOWED_NEXT[prev]:
                raise IntegrityError(f"proposal {p.id}: ledger history {' -> '.join(kinds)} is not a legal lifecycle")
            prev = k
        lstatus = self._LEDGER_STATUS[kinds[-1]]
        if p.status != lstatus:
            raise IntegrityError(f"proposal {p.id}: file says {p.status}, ledger says {lstatus}")
        if lstatus == "drafted" or (lstatus == "withdrawn" and "preregistered" not in kinds):
            return
        prereg = self.ledger.find("proposal.preregistered", id=p.id)
        if prereg is None:
            raise IntegrityError(f"proposal {p.id}: no pre-registration event in the ledger")
        if prereg.payload.get("criteria_hash") != p.criteria_hash or p.compute_criteria_hash() != prereg.payload.get("criteria_hash"):
            raise IntegrityError(f"proposal {p.id}: criteria differ from the ledger's pre-registration")
        if lstatus in ("evaluating", "accepted", "rejected", "rolled_back"):
            if p.evidence != self.ledger_evidence(p.id):
                raise IntegrityError(f"proposal {p.id}: evidence differs from the ledger's evidence events")
        if lstatus in ("accepted", "rejected", "rolled_back"):
            g = self.gate_from_ledger(p.id)
            decided = "accepted" if g.passed else "rejected"
            recorded = "accepted" if lstatus in ("accepted", "rolled_back") else "rejected"
            if decided != recorded:
                raise IntegrityError(f"proposal {p.id}: recorded verdict {recorded} but the ledger's evidence implies {decided}")

    def _require(self, proposal_id: str, allowed: tuple) -> Proposal:
        p = self._items[proposal_id]
        self.check_integrity(p)
        if p.status not in allowed:
            raise LifecycleError(f"proposal {proposal_id} is {p.status}; this step requires {' or '.join(allowed)}")
        return p

    def reconcile(self) -> list[str]:
        """Replay the ledger and report every disagreement with the proposals file."""
        problems: list[str] = []
        ids_in_ledger = []
        for ev in self.ledger.events(kind="proposal."):
            pid = ev.payload.get("id")
            if pid and pid not in ids_in_ledger:
                ids_in_ledger.append(pid)
        for pid in ids_in_ledger:
            if pid not in self._items:
                problems.append(f"{pid}: in the ledger but missing from the file")
                continue
            try:
                self.check_integrity(self._items[pid])
            except (IntegrityError, LifecycleError) as e:
                problems.append(str(e))
        for pid in self._items:
            if pid not in ids_in_ledger:
                problems.append(f"{pid}: present in file but never drafted in the ledger")
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
        self.check_integrity(p)
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
        p = self._require(proposal_id, ("drafted",))
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
        clean = jsonable(dict(evidence))            # raises before any mutation
        if not clean:
            raise ValueError("evidence is empty")
        with file_lock(self.path):
            p = self._require(proposal_id, ("preregistered", "evaluating"))
            seen = self.ledger_evidence(p.id)       # the ledger, not the file copy, decides what is already recorded
            clash = {k for k, v in clean.items() if k in seen and seen[k] != v}
            if clash:
                raise LifecycleError(f"evidence keys {sorted(clash)} were already recorded; evidence is write-once "
                                     f"(draft a new proposal with supersedes={p.id})")
            p.evidence = {**seen, **clean}
            p.status = "evaluating"
            self._flush()
            self.ledger.append("proposal.evidence", {"id": p.id, "evidence": clean, "criteria_hash": p.criteria_hash}, actor=actor)
        return p

    def decide(self, proposal_id: str, produces_insights: Iterable[str] = (), actor: str = "mandel") -> Proposal:
        """Apply the gate and record the verdict. The caller does not get to choose it."""
        with file_lock(self.path):
            p = self._require(proposal_id, ("evaluating",))
            g = self.gate_from_ledger(p.id)          # verdict from ledger events only
            p.evidence = self.ledger_evidence(p.id)
            return self._record_decision(p, g, produces_insights, actor)

    def _record_decision(self, p: Proposal, g, produces_insights: Iterable[str], actor: str) -> Proposal:
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
        self.check_integrity(p)
        if p.status == "evaluating":
            raise LifecycleError("evidence has already been seen; the proposal must be decided, not withdrawn")
        if p.status not in ("drafted", "preregistered"):
            raise LifecycleError("cannot withdraw a decided proposal")
        p.status = "withdrawn"
        p.decided_at = utcnow_iso()
        p.decision = reason
        self._flush()
        self.ledger.append("proposal.withdrawn", {"id": p.id, "reason": reason}, actor=actor)
        return p

    def roll_back(self, proposal_id: str, reason: str, actor: str = "mandel") -> Proposal:
        p = self._require(proposal_id, ("accepted",))
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
