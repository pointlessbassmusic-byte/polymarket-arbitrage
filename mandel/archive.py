"""
Cold storage: park what is not useful now so it can be dug up later for less
than it cost to find.
=====================================================================

The user's rule: never delete data or knowledge just because the first
iteration found no use for it; store it with as little effort as possible,
indexed, so a later iteration can rehydrate it instead of re-finding it.

Two kinds of parked things:

- **Bundles** of data or results: gzip-compressed JSONL under
  ``mandel/archive/<kind>/<name>.jsonl.gz`` with a small index entry
  (what, when, rows, bytes, sha256, tags, the recipe that produced it, and
  why it was parked). Bundles above ``INLINE_LIMIT_BYTES`` are not kept in
  git; the index keeps the recipe and hash so the bundle can be rebuilt or
  copied from the machine that holds it.
- **Parked insights and theories**: they keep their records and status;
  they gain a ``parked`` tag and a reason in the ledger. Nothing is removed.

Everything here is append-only except the index, which is rewritten
atomically.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from mandel._io import atomic_write_text, file_lock
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import MANDEL_ROOT

ARCHIVE_ROOT = MANDEL_ROOT / "archive"
INDEX_PATH = ARCHIVE_ROOT / "INDEX.json"
INLINE_LIMIT_BYTES = 8 * 1024 * 1024      # bundles larger than this are kept out of git


@dataclass
class BundleEntry:
    name: str
    kind: str                     # "data" | "results" | "knowledge"
    path: str                     # relative to the repo root
    created_at: str
    rows: int
    bytes: int
    sha256: str
    tags: list[str] = field(default_factory=list)
    recipe: str = ""              # how to rebuild it (a command, an endpoint, a function)
    parked_reason: str = ""
    in_git: bool = True
    schema: str = ""              # one line describing a row


class Archive:
    def __init__(self, root: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.root = Path(root) if root else ARCHIVE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "INDEX.json"
        self.ledger = ledger if ledger is not None else Ledger()
        self._entries: dict[str, BundleEntry] = {}
        if self.index_path.exists():
            raw = self.index_path.read_text(encoding="utf-8").strip()
            for d in (json.loads(raw) if raw else {}).get("bundles", {}).values():
                self._entries[d["name"]] = BundleEntry(**d)

    def _rel(self, path: Path) -> str:
        for base in (MANDEL_ROOT.parent, self.root):
            try:
                return str(path.relative_to(base))
            except ValueError:
                continue
        return str(path)

    def _abs(self, rel: str) -> Path:
        p = Path(rel)
        if p.is_absolute():
            return p
        for base in (MANDEL_ROOT.parent, self.root):
            if (base / p).exists():
                return base / p
        return MANDEL_ROOT.parent / p

    def _reload_index(self) -> None:
        if self.index_path.exists():
            raw = self.index_path.read_text(encoding="utf-8").strip()
            for d in (json.loads(raw) if raw else {}).get("bundles", {}).values():
                self._entries.setdefault(d["name"], BundleEntry(**d))

    def _flush(self) -> None:
        atomic_write_text(self.index_path, json.dumps({"note": "Cold storage index. Bundles are gzip JSONL; "
                          "entries not in git carry the recipe to rebuild them.",
                          "bundles": {k: asdict(v) for k, v in self._entries.items()}}, indent=1, ensure_ascii=False))

    # -- bundles -----------------------------------------------------------
    def store(self, name: str, kind: str, rows: Iterable[dict], recipe: str, tags: Iterable[str] = (),
              parked_reason: str = "", schema: str = "", actor: str = "mandel") -> BundleEntry:
        if kind not in ("data", "results", "knowledge"):
            raise ValueError("kind must be data, results or knowledge")
        safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name)
        path = self.root / kind / f"{safe}.jsonl.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        n = 0
        with file_lock(self.index_path):                      # one lock for bundle + index; merges concurrent writers
            with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
                for r in rows:
                    line = json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str)
                    f.write(line + "\n")
                    h.update(line.encode("utf-8"))
                    n += 1
            size = path.stat().st_size
            entry = BundleEntry(name=safe, kind=kind, path=self._rel(path), created_at=utcnow_iso(),
                                rows=n, bytes=size, sha256=h.hexdigest(), tags=sorted(set(tags)), recipe=recipe,
                                parked_reason=parked_reason, in_git=size <= INLINE_LIMIT_BYTES, schema=schema)
            self._reload_index()
            self._entries[safe] = entry
            self._flush()
        self.ledger.append("archive.stored", {"name": safe, "kind": kind, "rows": n, "bytes": size, "sha256": entry.sha256,
                                              "in_git": entry.in_git, "parked_reason": parked_reason}, actor=actor)
        return entry

    def load(self, name: str) -> Iterator[dict]:
        entry = self._entries[name]
        path = self._abs(entry.path)
        if not path.exists():
            raise FileNotFoundError(f"bundle {name} is not on this machine; rebuild with recipe: {entry.recipe}")
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def verify(self, name: str) -> bool:
        entry = self._entries[name]
        h = hashlib.sha256()
        for r in self.load(name):
            h.update(json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))
        return h.hexdigest() == entry.sha256

    def entries(self, kind: Optional[str] = None, tag: Optional[str] = None) -> list[BundleEntry]:
        out = [e for e in self._entries.values() if (kind is None or e.kind == kind) and (tag is None or tag in e.tags)]
        return sorted(out, key=lambda e: e.created_at)

    def get(self, name: str) -> BundleEntry:
        return self._entries[name]

    # -- parking knowledge --------------------------------------------------
    def park_insight(self, store, insight_id: str, reason: str, actor: str = "mandel"):
        """Tag an insight as parked (kept, searchable, not used for guidance) with a reason."""
        ins = store.get(insight_id)
        if "parked" not in ins.tags:
            ins.tags = sorted(set(ins.tags) | {"parked"})
            ins.notes = (ins.notes + " | " if ins.notes else "") + f"parked: {reason}"
            store._flush()
        self.ledger.append("insight.parked", {"id": insight_id, "reason": reason}, actor=actor)
        return ins

    def unpark_insight(self, store, insight_id: str, reason: str, actor: str = "mandel"):
        ins = store.get(insight_id)
        ins.tags = sorted(set(ins.tags) - {"parked"})
        ins.notes = (ins.notes + " | " if ins.notes else "") + f"unparked: {reason}"
        store._flush()
        self.ledger.append("insight.unparked", {"id": insight_id, "reason": reason}, actor=actor)
        return ins

    def summary(self) -> dict:
        by_kind: dict[str, dict] = {}
        for e in self._entries.values():
            d = by_kind.setdefault(e.kind, {"bundles": 0, "rows": 0, "bytes": 0, "not_in_git": 0})
            d["bundles"] += 1; d["rows"] += e.rows; d["bytes"] += e.bytes; d["not_in_git"] += (0 if e.in_git else 1)
        return {"bundles": len(self._entries), "by_kind": by_kind}
