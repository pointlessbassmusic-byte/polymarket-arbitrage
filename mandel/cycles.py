"""
Cycle log: improvement per unit of cost.
========================================

One *cycle* is one full turn of the improvement loop (observe, hypothesise,
pre-register, change, measure, gate, record, propagate). The user's
constraint is minimal resource waste, so every cycle records what it cost
and what it produced. The ratio is Mandel's own efficiency metric, and it
is tracked the same way everything else is: in a file, with history.

Costs are recorded by the operator (Mandel) because the session cannot
meter its own tokens exactly; estimates are labelled as such.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from mandel._io import atomic_write_text
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path

COST_FIELDS = ("agents", "api_calls", "wall_seconds", "tokens_est")
OUTCOME_FIELDS = ("proposals_accepted", "proposals_rejected", "insights_added", "insights_validated",
                  "children_contacted", "sources_learned")


@dataclass
class Cycle:
    id: str
    goal: str
    started_at: str
    finished_at: Optional[str] = None
    cost: dict = field(default_factory=dict)
    outcomes: dict = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def open(self) -> bool:
        return self.finished_at is None

    def gains(self) -> int:
        return int(self.outcomes.get("proposals_accepted", 0)) + int(self.outcomes.get("insights_validated", 0))


class CycleLog:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("cycles.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self._items: dict[str, Cycle] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        self._items[d["id"]] = Cycle(**d)

    def _flush(self) -> None:
        atomic_write_text(self.path, "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in self._items.values()))

    def start(self, goal: str, actor: str = "mandel") -> Cycle:
        if any(c.open for c in self._items.values()):
            raise RuntimeError("a cycle is already open; finish it first")
        c = Cycle(id="C-" + uuid.uuid4().hex[:8], goal=goal.strip(), started_at=utcnow_iso())
        self._items[c.id] = c
        self._flush()
        self.ledger.append("cycle.started", {"id": c.id, "goal": c.goal}, actor=actor)
        return c

    def note_action(self, cycle_id: str, action: str) -> Cycle:
        c = self._items[cycle_id]
        if not c.open:
            raise RuntimeError("cycle is finished")
        c.actions.append(action)
        self._flush()
        return c

    def finish(self, cycle_id: str, cost: dict, outcomes: dict, notes: str = "", actor: str = "mandel") -> Cycle:
        c = self._items[cycle_id]
        if not c.open:
            raise RuntimeError("cycle already finished")
        bad = set(cost) - set(COST_FIELDS)
        if bad:
            raise ValueError(f"unknown cost fields {sorted(bad)}; allowed {COST_FIELDS}")
        bad = set(outcomes) - set(OUTCOME_FIELDS)
        if bad:
            raise ValueError(f"unknown outcome fields {sorted(bad)}; allowed {OUTCOME_FIELDS}")
        c.cost = {k: float(v) for k, v in cost.items()}
        c.outcomes = {k: int(v) for k, v in outcomes.items()}
        c.notes = notes
        c.finished_at = utcnow_iso()
        self._flush()
        self.ledger.append("cycle.finished", {"id": c.id, "cost": c.cost, "outcomes": c.outcomes, "gains": c.gains()}, actor=actor)
        return c

    def current(self) -> Optional[Cycle]:
        return next((c for c in self._items.values() if c.open), None)

    def all(self) -> list[Cycle]:
        return sorted(self._items.values(), key=lambda c: c.started_at)

    def efficiency(self) -> dict:
        """Validated gains per unit of each cost, over all finished cycles."""
        done = [c for c in self._items.values() if not c.open]
        gains = sum(c.gains() for c in done)
        totals = {k: sum(c.cost.get(k, 0.0) for c in done) for k in COST_FIELDS}
        per = {k: (gains / v if v else None) for k, v in totals.items()}
        return {"cycles": len(done), "gains": gains, "total_cost": totals, "gains_per_unit": per}
