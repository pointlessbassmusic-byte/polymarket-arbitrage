"""
Append-only, hash-chained ledger.
==================================

Every consequential thing Mandel does (ingesting a source, recording an
insight, pre-registering a proposal, recording a validation result,
adopting or rejecting a change, contacting a child) is appended here as
an event. Each event carries the hash of the previous one, so in-place
edits are detectable: ``verify()`` recomputes the chain.

What this does and does not guarantee
-------------------------------------
- An edited, inserted or reordered line breaks the chain and is reported.
- A *truncated* chain is still internally valid, so the head ``(seq, hash)``
  is also written to ``ledger.head`` after every append and checked by
  ``verify()``; truncation below the anchor is reported.
- A full regeneration of both files by someone with write access cannot be
  detected from inside the repository. The external anchor is git history:
  the ledger and its head file are committed, so the commit log holds past
  heads. ``verify(anchor=...)`` accepts a head hash copied from a commit.
- Concurrent writers are serialised with an advisory file lock, and the
  in-memory head is re-synced with the file before every append.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from mandel._io import append_line, atomic_write_text, file_lock, jsonable
from mandel.paths import data_path

GENESIS_HASH = "0" * 64


class LedgerCorrupt(RuntimeError):
    def __init__(self, line_no: int, reason: str):
        super().__init__(f"ledger corrupt at line {line_no}: {reason}")
        self.line_no = line_no
        self.reason = reason


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
        body = {"seq": self.seq, "ts": self.ts, "kind": self.kind, "actor": self.actor,
                "payload": self.payload, "prev_hash": self.prev_hash}
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class Ledger:
    """JSONL-backed hash chain with a head anchor file and an advisory lock."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else data_path("ledger.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.head_path = self.path.with_suffix(".head")
        self._last: Optional[Event] = None
        self._count = 0
        self._size = -1
        self.corrupt: Optional[LedgerCorrupt] = None
        self._sync()

    # -- reading -----------------------------------------------------------
    def _iter_raw(self) -> Iterator[Event]:
        """Yield events; raise LedgerCorrupt at the first unparseable line."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    d = json.loads(s)
                    yield Event(**d)
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    raise LedgerCorrupt(i, f"{type(e).__name__}: {str(e)[:80]}") from e

    def _sync(self) -> None:
        """Refresh the cached head from disk (cheap when the file has not changed size)."""
        size = self.path.stat().st_size if self.path.exists() else 0
        if size == self._size:
            return
        last, count, corrupt = None, 0, None
        try:
            for ev in self._iter_raw():
                last, count = ev, count + 1
        except LedgerCorrupt as e:
            corrupt = e
        self._last, self._count, self._size, self.corrupt = last, count, size, corrupt

    def events(self, kind: Optional[str] = None, actor: Optional[str] = None) -> list[Event]:
        out = []
        for ev in self._iter_raw():
            if kind and not ev.kind.startswith(kind):
                continue
            if actor and ev.actor != actor:
                continue
            out.append(ev)
        return out

    def tail(self, n: int, kind: Optional[str] = None) -> list[Event]:
        """Last ``n`` events (optionally filtered), holding only ``n`` in memory."""
        from collections import deque
        dq: deque[Event] = deque(maxlen=max(1, n))
        for ev in self._iter_raw():
            if kind and not ev.kind.startswith(kind):
                continue
            dq.append(ev)
        return list(dq)

    def find(self, kind: str, **payload_match: Any) -> Optional[Event]:
        """First event of ``kind`` whose payload matches every given key."""
        for ev in self._iter_raw():
            if ev.kind == kind and all(ev.payload.get(k) == v for k, v in payload_match.items()):
                return ev
        return None

    def last_of(self, kind_prefix: str, **payload_match: Any) -> Optional[Event]:
        """Most recent event whose kind starts with ``kind_prefix`` and payload matches."""
        found = None
        for ev in self._iter_raw():
            if ev.kind.startswith(kind_prefix) and all(ev.payload.get(k) == v for k, v in payload_match.items()):
                found = ev
        return found

    def __len__(self) -> int:
        self._sync()
        return self._count

    @property
    def head_hash(self) -> str:
        self._sync()
        return self._last.hash if self._last else GENESIS_HASH

    # -- writing -----------------------------------------------------------
    def append(self, kind: str, payload: dict[str, Any], actor: str = "mandel") -> Event:
        payload = jsonable(payload)
        with file_lock(self.path):
            self._sync()
            if self.corrupt is not None:
                raise self.corrupt
            ev = Event(seq=self._count, ts=utcnow_iso(), kind=kind, actor=actor, payload=payload,
                       prev_hash=self._last.hash if self._last else GENESIS_HASH)
            ev.hash = ev.compute_hash()
            append_line(self.path, json.dumps(asdict(ev), ensure_ascii=False))
            atomic_write_text(self.head_path, json.dumps({"seq": ev.seq, "hash": ev.hash, "ts": ev.ts}))
            self._last, self._count = ev, self._count + 1
            self._size = self.path.stat().st_size
        return ev

    def anchor_now(self) -> str:
        """Explicitly (re)write the head anchor for the current chain. Only for migrating a ledger
        created before anchors existed; the call is itself recorded as an event first."""
        ev = self.append("ledger.anchored", {"reason": "explicit re-anchor"}, actor="user")
        return ev.hash

    # -- integrity ---------------------------------------------------------
    def verify(self, anchor: Optional[str] = None) -> tuple[bool, str]:
        """Recompute the chain, check the head anchor file and an optional external anchor."""
        prev, n = GENESIS_HASH, 0
        seen: dict[int, str] = {}
        try:
            for ev in self._iter_raw():
                if ev.seq != n:
                    return False, f"sequence gap at {n} (found seq={ev.seq})"
                if ev.prev_hash != prev:
                    return False, f"prev_hash mismatch at seq={ev.seq}"
                if ev.compute_hash() != ev.hash:
                    return False, f"hash mismatch at seq={ev.seq}"
                prev = ev.hash
                seen[ev.seq] = ev.hash
                n += 1
        except LedgerCorrupt as e:
            return False, str(e)
        if (n > 0 or self.path.exists()) and not self.head_path.exists():
            return False, f"head anchor file missing (ledger has {n} events); restore it from git or re-anchor explicitly with anchor_now()"
        if self.head_path.exists():
            try:
                head = json.loads(self.head_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False, "head anchor file unreadable"
            if head.get("seq") is None or head["seq"] >= n:
                return False, f"ledger truncated: anchor says seq {head.get('seq')} exists, file has {n} events"
            if seen.get(head["seq"]) != head.get("hash"):
                return False, f"anchor mismatch at seq {head['seq']}"
        if anchor and anchor not in seen.values():
            return False, f"external anchor {anchor[:12]} not found in chain"
        return True, f"ok: {n} events, head={prev[:12]}"
