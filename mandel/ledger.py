"""
Append-only, hash-chained ledger.
==================================

Every consequential thing Mandel does (ingesting a source, recording an
insight, pre-registering a proposal, recording a validation result,
adopting or rejecting a change, contacting a child) is appended here as
an event. Each event carries the hash of the previous one, so the history
cannot be silently rewritten: ``verify()`` recomputes the chain.

Why this matters for self-improvement: the single most common failure in
"self-improving" systems is quietly moving the goalposts after seeing the
results. The ledger makes the order of events (criterion first, result
second) checkable after the fact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from mandel.paths import data_path

GENESIS_HASH = "0" * 64


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON used for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


@dataclass
class Event:
    seq: int
    ts: str
    kind: str                      # e.g. "insight.recorded", "proposal.preregistered"
    actor: str                     # "mandel", "child:<name>", "user"
    payload: dict[str, Any]
    prev_hash: str
    hash: str = ""

    def compute_hash(self) -> str:
        body = {
            "seq": self.seq,
            "ts": self.ts,
            "kind": self.kind,
            "actor": self.actor,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class Ledger:
    """JSONL-backed hash chain. One instance per file; not safe for concurrent writers."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else data_path("ledger.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last: Optional[Event] = None
        self._count = 0
        if self.path.exists():
            for ev in self._iter_raw():
                self._last = ev
                self._count += 1

    # -- reading -----------------------------------------------------------
    def _iter_raw(self) -> Iterator[Event]:
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                yield Event(**d)

    def events(self, kind: Optional[str] = None, actor: Optional[str] = None) -> list[Event]:
        if not self.path.exists():
            return []
        out = []
        for ev in self._iter_raw():
            if kind and not ev.kind.startswith(kind):
                continue
            if actor and ev.actor != actor:
                continue
            out.append(ev)
        return out

    def __len__(self) -> int:
        return self._count

    @property
    def head_hash(self) -> str:
        return self._last.hash if self._last else GENESIS_HASH

    # -- writing -----------------------------------------------------------
    def append(self, kind: str, payload: dict[str, Any], actor: str = "mandel") -> Event:
        ev = Event(
            seq=self._count,
            ts=utcnow_iso(),
            kind=kind,
            actor=actor,
            payload=payload,
            prev_hash=self.head_hash,
        )
        ev.hash = ev.compute_hash()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(ev), ensure_ascii=False, default=str) + "\n")
        self._last = ev
        self._count += 1
        return ev

    # -- integrity ---------------------------------------------------------
    def verify(self) -> tuple[bool, str]:
        """Recompute the chain. Returns (ok, message)."""
        prev = GENESIS_HASH
        n = 0
        for ev in self.events():
            if ev.seq != n:
                return False, f"sequence gap at {n} (found seq={ev.seq})"
            if ev.prev_hash != prev:
                return False, f"prev_hash mismatch at seq={ev.seq}"
            if ev.compute_hash() != ev.hash:
                return False, f"hash mismatch at seq={ev.seq}"
            prev = ev.hash
            n += 1
        return True, f"ok: {n} events, head={prev[:12]}"
