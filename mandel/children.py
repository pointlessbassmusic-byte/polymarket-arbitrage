"""
Children: the sibling Claude Code sessions Mandel learns from and guides.
=========================================================================

Mandel does not run inside the children and cannot see their context
directly except through the remote-session tools the user grants it. The
protocol is therefore file-based and explicit:

- A child is *registered* once, with a name, its session id, its domain and
  what it is for.
- A child *reports*: what it learned, what metrics it measured, what it is
  unsure about. Reports are append-only.
- Mandel *guides*: validated insights, warnings about known failure modes,
  requests for specific measurements. Guidance is also append-only.
- Everything a child claims arrives as a *candidate* insight. It becomes
  validated the same way anything else does: through the gate.

Naming: the children are named after the people and objects of fractal and
dynamical mathematics, probability and information. Mandel suggests; the
user decides.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from mandel._io import append_line, atomic_write_text, file_lock
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path

NAME_POOL: list[tuple[str, str]] = [
    ("Julia", "Julia sets: the per-parameter dynamics the Mandelbrot set catalogues"),
    ("Fatou", "Fatou sets: the stable, predictable regions of a dynamical system"),
    ("Douady", "Adrien Douady, who with Hubbard proved the Mandelbrot set is connected"),
    ("Hubbard", "John Hubbard, structure of the Mandelbrot set (resource 16)"),
    ("Barnsley", "Michael Barnsley, iterated function systems and the fern (resources 08, 09)"),
    ("Sierpinski", "Sierpinski triangle: self-similarity from simple rules"),
    ("Koch", "Koch curve: infinite length in finite space"),
    ("Cantor", "Cantor set: the first fractal, and the measure of what is left out"),
    ("Hausdorff", "Hausdorff dimension: roughness made measurable (resource 15)"),
    ("Hurst", "Hurst exponent: long memory in time series"),
    ("Feigenbaum", "Feigenbaum constants: universality at the edge of chaos"),
    ("Lyapunov", "Lyapunov exponents: how fast prediction decays"),
    ("Lorenz", "Lorenz attractor: deterministic yet unpredictable"),
    ("Levy", "Lévy flights: fat tails that textbooks ignore"),
    ("Markov", "Markov chains: memoryless prediction (resource 11)"),
    ("Shannon", "Claude Shannon: information as a measurable quantity (resource 01)"),
    ("Bayes", "Bayesian updating: the only coherent way to change one's mind"),
    ("Brier", "Brier score: the proper scoring rule Mandel grades everyone with"),
    ("Kelly", "Kelly criterion: how much to bet on an edge you are unsure of"),
    ("Laplace", "Laplace: probability as a calculus of ignorance"),
    ("Kolmogorov", "Kolmogorov complexity: the shortest description that works"),
    ("Solomonoff", "Solomonoff induction: the ideal predictor nothing can compute"),
]

_SAFE = re.compile(r"[^a-z0-9_-]+")


def slugify(name: str) -> str:
    return _SAFE.sub("-", name.strip().lower()).strip("-")


@dataclass
class Child:
    name: str
    session_id: str
    domain: str
    description: str
    status: str = "active"           # active | paused | graduated | archived
    registered_at: str = field(default_factory=utcnow_iso)
    last_contact: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)   # latest reported metrics by name
    report_count: int = 0
    guidance_count: int = 0


@dataclass
class ChildReport:
    id: str
    child: str
    ts: str
    summary: str
    learnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    questions: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)   # paths, URLs, commit hashes


@dataclass
class Guidance:
    id: str
    to: str
    ts: str
    summary: str
    insights: list[str] = field(default_factory=list)    # insight ids or texts
    warnings: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)    # measurements Mandel wants back


class ChildRegistry:
    def __init__(self, root: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.root = Path(root) if root else data_path("children", ".keep").parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "registry.json"
        self.ledger = ledger if ledger is not None else Ledger()
        self._children: dict[str, Child] = {}
        if self.index_path.exists():
            raw = self.index_path.read_text(encoding="utf-8").strip()
            data = json.loads(raw) if raw else {}
            for d in data.values():
                self._children[d["name"]] = Child(**d)

    def _flush(self) -> None:
        atomic_write_text(self.index_path, json.dumps({k: asdict(v) for k, v in self._children.items()}, indent=2, ensure_ascii=False))

    def _child_dir(self, name: str, create: bool = False) -> Path:
        d = self.root / slugify(name)
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def _resolve(self, name: str) -> str:
        """Case-insensitive lookup: returns the registered display name."""
        slug = slugify(name)
        for n in self._children:
            if slugify(n) == slug:
                return n
        raise KeyError(name)

    # -- registry ----------------------------------------------------------
    def suggest_names(self, n: int = 5) -> list[tuple[str, str]]:
        taken = {c.name.lower() for c in self._children.values()}
        return [(nm, why) for nm, why in NAME_POOL if nm.lower() not in taken][:n]

    def register(self, name: str, session_id: str, domain: str, description: str, tags: list[str] | None = None) -> Child:
        if not slugify(name):
            raise ValueError("name must contain letters or digits")
        clash = [n for n in self._children if slugify(n) == slugify(name)]
        if clash:
            raise ValueError(f"child {name!r} collides with registered child {clash[0]!r} (names are case-insensitive)")
        child = Child(name=name, session_id=session_id, domain=domain, description=description, tags=sorted(set(tags or [])))
        with file_lock(self.index_path):
            self._children[name] = child
            self._child_dir(name, create=True)
            self._flush()
        self.ledger.append("child.registered", {"name": name, "session_id": session_id, "domain": domain}, actor="mandel")
        return child

    def get(self, name: str) -> Child:
        return self._children[self._resolve(name)]

    def all(self) -> list[Child]:
        return sorted(self._children.values(), key=lambda c: c.registered_at)

    def set_status(self, name: str, status: str) -> Child:
        if status not in ("active", "paused", "graduated", "archived"):
            raise ValueError("bad status")
        name = self._resolve(name)
        c = self._children[name]
        c.status = status
        self._flush()
        self.ledger.append("child.status", {"name": name, "status": status}, actor="mandel")
        return c

    # -- protocol ----------------------------------------------------------
    def record_report(self, name: str, summary: str, learnings: list[str] | None = None, metrics: dict | None = None,
                      questions: list[str] | None = None, artifacts: list[str] | None = None) -> ChildReport:
        name = self._resolve(name)
        c = self._children[name]
        rep = ChildReport(id="R-" + uuid.uuid4().hex[:10], child=name, ts=utcnow_iso(), summary=summary,
                          learnings=list(learnings or []), metrics=dict(metrics or {}),
                          questions=list(questions or []), artifacts=list(artifacts or []))
        append_line(self._child_dir(name, create=True) / "reports.jsonl", json.dumps(asdict(rep), ensure_ascii=False))
        c.last_contact = rep.ts
        c.report_count += 1
        c.metrics.update(rep.metrics)
        self._flush()
        self.ledger.append("child.report", {"id": rep.id, "child": name, "n_learnings": len(rep.learnings),
                                            "metrics": rep.metrics}, actor=f"child:{name}")
        return rep

    def record_guidance(self, name: str, summary: str, insights: list[str] | None = None, warnings: list[str] | None = None,
                        requests: list[str] | None = None, known_ids: Optional[set[str]] = None) -> Guidance:
        """``insights`` holds insight ids (I-...) or plain texts. With ``known_ids``, an id that is not in it is refused,
        so guidance never cites an insight that does not exist."""
        name = self._resolve(name)
        if known_ids is not None:
            bad = [i for i in (insights or []) if re.fullmatch(r"I-[0-9a-f]{6,}", i) and i not in known_ids]
            if bad:
                raise ValueError(f"guidance cites unknown insight ids: {bad}")
        c = self._children[name]
        g = Guidance(id="G-" + uuid.uuid4().hex[:10], to=name, ts=utcnow_iso(), summary=summary,
                     insights=list(insights or []), warnings=list(warnings or []), requests=list(requests or []))
        append_line(self._child_dir(name, create=True) / "guidance.jsonl", json.dumps(asdict(g), ensure_ascii=False))
        c.guidance_count += 1
        self._flush()
        self.ledger.append("child.guidance", {"id": g.id, "to": name, "n_insights": len(g.insights),
                                              "n_requests": len(g.requests)}, actor="mandel")
        return g

    def reports(self, name: str) -> list[ChildReport]:
        p = self._child_dir(self._resolve(name)) / "reports.jsonl"
        if not p.exists():
            return []
        return [ChildReport(**json.loads(l)) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def guidance(self, name: str) -> list[Guidance]:
        p = self._child_dir(self._resolve(name)) / "guidance.jsonl"
        if not p.exists():
            return []
        return [Guidance(**json.loads(l)) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
