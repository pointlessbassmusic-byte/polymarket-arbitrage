"""
Insight store.
==============

An *insight* is the atomic unit of Mandel's knowledge: one claim, with
provenance, a confidence, and a validation status. Insights start as
``candidate`` (read somewhere, sounds right), become ``validated`` only when
a proposal that depends on them passes the gate or when independent sources
converge, and are ``retired`` when contradicted or when the thing they
supported is rolled back.

Design rules
------------
- One claim per insight. Compound insights are split so they can fail separately.
- Provenance is mandatory. ``src:04`` means the user's resource 04,
  ``adj:A2`` an adjacent resource, ``child:<name>:report:<n>`` a child's
  report, ``proposal:<id>`` a validated proposal, ``mandel:self`` a
  Mandel-authored inference (lowest default confidence).
- Confidence is a probability that the claim is true *as stated*, not
  enthusiasm.
- Every mutation is also appended to the ledger.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path

KINDS = ("principle", "fact", "heuristic", "procedure", "metric", "question")
STATUSES = ("candidate", "validated", "retired")


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
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not self.provenance:
            raise ValueError("provenance is mandatory")
        if not self.text.strip():
            raise ValueError("text is empty")


def new_insight_id() -> str:
    return "I-" + uuid.uuid4().hex[:10]


class InsightStore:
    """JSONL file of insights, fully loaded in memory; appends are rewritten atomically."""

    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("insights.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self._items: dict[str, Insight] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        self._items[d["id"]] = Insight(**d)

    # -- persistence -------------------------------------------------------
    def _flush(self) -> None:
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for ins in self._items.values():
                f.write(json.dumps(asdict(ins), ensure_ascii=False) + "\n")
        tmp.replace(self.path)

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
        ins = Insight(
            id=new_insight_id(), text=text.strip(), kind=kind,
            provenance=list(provenance), confidence=float(confidence),
            tags=sorted(set(tags)), notes=notes,
        )
        ins.validate_fields()
        self._items[ins.id] = ins
        self._flush()
        self.ledger.append("insight.recorded", {"id": ins.id, "kind": kind, "confidence": ins.confidence,
                                                "provenance": ins.provenance, "text": ins.text}, actor=actor)
        return ins

    def get(self, insight_id: str) -> Insight:
        return self._items[insight_id]

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
        old = ins.status
        ins.status = status
        ins.updated_at = utcnow_iso()
        if status == "validated":
            ins.validated_by.append(by)
        elif status == "retired":
            ins.contradicted_by.append(by)
        self._flush()
        self.ledger.append("insight.status", {"id": insight_id, "from": old, "to": status, "by": by}, actor=actor)
        return ins

    def update_confidence(self, insight_id: str, confidence: float, reason: str, actor: str = "mandel") -> Insight:
        ins = self._items[insight_id]
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        old = ins.confidence
        ins.confidence = float(confidence)
        ins.updated_at = utcnow_iso()
        self._flush()
        self.ledger.append("insight.confidence", {"id": insight_id, "from": old, "to": confidence, "reason": reason}, actor=actor)
        return ins

    # -- summaries ---------------------------------------------------------
    def summary(self) -> dict:
        by_status = {s: 0 for s in STATUSES}
        by_kind = {k: 0 for k in KINDS}
        for ins in self._items.values():
            by_status[ins.status] += 1
            by_kind[ins.kind] += 1
        return {"total": len(self._items), "by_status": by_status, "by_kind": by_kind}
