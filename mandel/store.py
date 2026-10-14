"""
Insight store.
==============

An *insight* is the atomic unit of Mandel's knowledge: one claim, with
provenance, a confidence, and a validation status. Insights start as
``candidate`` (read somewhere, sounds right), become ``validated`` only when
an accepted proposal names them or when two independent sources converge,
and are ``retired`` when contradicted or when the thing they supported is
rolled back.

Design rules
------------
- One claim per insight. Compound insights are split so they can fail separately.
- Provenance is mandatory and must be one of the recognised forms:
  ``src:NN`` (a user resource), ``adj:AN`` (an adjacent resource),
  ``child:<name>:report:<id>``, ``proposal:P-xxxxxxxx``, ``ideas:N``
  (Mandel's own ideas file), ``user``, or ``mandel:self`` (a Mandel-authored
  inference; confidence is capped at 0.5 when that is the only provenance).
- Confidence is a probability that the claim is true *as stated*, not
  enthusiasm.
- ``validated`` requires either an accepted proposal (checked against the
  attached ProposalBook) or ``converge:<ref>,<ref>`` naming two independent
  sources. Retired insights cannot be validated again; draft a new one.
- Every mutation is also appended to the ledger.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from mandel._io import atomic_write_text, file_lock
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path

KINDS = ("principle", "fact", "heuristic", "procedure", "metric", "question")
STATUSES = ("candidate", "validated", "retired")
PROVENANCE_RX = re.compile(
    r"^(src:\d{2}|adj:A\d+|child:[A-Za-z0-9_-]+:report:[A-Za-z0-9_-]+|proposal:P-[0-9a-f]{8}|ideas:\d+|user(:[\w-]+)?|mandel:self|synthesis)$"
)
PROPOSAL_ID_RX = re.compile(r"^P-[0-9a-f]{8}$")
SELF_ONLY_CAP = 0.5


@dataclass
class Insight:
    id: str
    text: str
    kind: str
    provenance: list[str]
    confidence: float
    status: str = "candidate"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    validated_by: list[str] = field(default_factory=list)
    contradicted_by: list[str] = field(default_factory=list)
    notes: str = ""

    def validate_fields(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if isinstance(self.confidence, bool) or not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not self.provenance:
            raise ValueError("provenance is mandatory")
        bad = [p for p in self.provenance if not PROVENANCE_RX.match(str(p))]
        if bad:
            raise ValueError(f"unrecognised provenance {bad}; use src:NN, adj:AN, child:<name>:report:<id>, "
                             f"proposal:P-xxxxxxxx, ideas:N, user, synthesis or mandel:self")
        if not self.text.strip():
            raise ValueError("text is empty")


def new_insight_id() -> str:
    return "I-" + uuid.uuid4().hex[:10]


class InsightStore:
    """JSONL file of insights, fully loaded in memory; writes are atomic and locked."""

    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None, proposals=None):
        self.path = Path(path) if path else data_path("insights.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self.proposals = proposals            # optional ProposalBook, needed to validate by proposal
        self._items: dict[str, Insight] = {}
        self._load()

    def _load(self) -> None:
        self._items = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        self._items[d["id"]] = Insight(**d)

    def _flush(self) -> None:
        atomic_write_text(self.path, "".join(json.dumps(asdict(i), ensure_ascii=False) + "\n" for i in self._items.values()))

    # -- CRUD --------------------------------------------------------------
    def add(
        self,
        text: str,
        kind: str,
        provenance: Iterable[str],
        confidence: float,
        tags: Iterable[str] = (),
        notes: str = "",
        actor: str = "mandel",
    ) -> Insight:
        prov = [str(p) for p in provenance]
        conf = float(confidence) if not isinstance(confidence, bool) else -1.0
        if prov and all(p == "mandel:self" for p in prov):
            conf = min(conf, SELF_ONLY_CAP)
        ins = Insight(id=new_insight_id(), text=text.strip(), kind=kind, provenance=prov, confidence=conf,
                      tags=sorted(set(tags)), notes=notes)
        ins.validate_fields()
        with file_lock(self.path):
            self._load()
            self._items[ins.id] = ins
            self._flush()
        self.ledger.append("insight.recorded", {"id": ins.id, "kind": kind, "confidence": ins.confidence,
                                                "provenance": ins.provenance, "text": ins.text}, actor=actor)
        return ins

    def get(self, insight_id: str) -> Insight:
        return self._items[insight_id]

    def exists(self, insight_id: str) -> bool:
        return insight_id in self._items

    def all(self) -> list[Insight]:
        return list(self._items.values())

    def query(
        self,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        text_regex: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[Insight]:
        rx = re.compile(text_regex, re.I) if text_regex else None
        out = []
        for ins in self._items.values():
            if status and ins.status != status:
                continue
            if kind and ins.kind != kind:
                continue
            if tag and tag not in ins.tags:
                continue
            if ins.confidence < min_confidence:
                continue
            if rx and not rx.search(ins.text):
                continue
            out.append(ins)
        return sorted(out, key=lambda i: (-i.confidence, i.created_at))

    def set_status(self, insight_id: str, status: str, by: str, actor: str = "mandel") -> Insight:
        ins = self._items[insight_id]
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if status == "validated":
            if ins.status == "retired":
                raise ValueError("a retired insight cannot be validated; record a new insight")
            if PROPOSAL_ID_RX.match(by):
                if self.proposals is None:
                    raise ValueError("validating by proposal requires an attached ProposalBook")
                try:
                    p = self.proposals.get(by)
                except KeyError:
                    raise ValueError(f"unknown proposal {by}") from None
                if p.status != "accepted":
                    raise ValueError(f"proposal {by} is {p.status}, not accepted")
                if insight_id not in p.produces_insights and insight_id not in p.depends_on_insights:
                    raise ValueError(f"proposal {by} does not name insight {insight_id}")
            elif by.startswith("converge:"):
                refs = [r for r in by[len("converge:"):].split(",") if r.strip()]
                if len(set(refs)) < 2 or not all(PROVENANCE_RX.match(r.strip()) for r in refs):
                    raise ValueError("converge: needs at least two distinct recognised provenance refs")
            else:
                raise ValueError("validated requires by=<accepted proposal id> or by=converge:<ref>,<ref>")
        old = ins.status
        ins.status = status
        ins.updated_at = utcnow_iso()
        if status == "validated" and by not in ins.validated_by:
            ins.validated_by.append(by)
        elif status == "retired" and by not in ins.contradicted_by:
            ins.contradicted_by.append(by)
        self._flush()
        self.ledger.append("insight.status", {"id": insight_id, "from": old, "to": status, "by": by}, actor=actor)
        return ins

    def update_confidence(self, insight_id: str, confidence: float, reason: str, actor: str = "mandel") -> Insight:
        ins = self._items[insight_id]
        if isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not reason.strip():
            raise ValueError("a reason is required to change confidence")
        old = ins.confidence
        ins.confidence = float(confidence)
        ins.updated_at = utcnow_iso()
        self._flush()
        self.ledger.append("insight.confidence", {"id": insight_id, "from": old, "to": ins.confidence, "reason": reason}, actor=actor)
        return ins

    # -- summaries ---------------------------------------------------------
    def summary(self) -> dict:
        by_status = {s: 0 for s in STATUSES}
        by_kind = {k: 0 for k in KINDS}
        for ins in self._items.values():
            by_status[ins.status] += 1
            by_kind[ins.kind] += 1
        return {"total": len(self._items), "by_status": by_status, "by_kind": by_kind}
