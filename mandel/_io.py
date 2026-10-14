"""Small, boring I/O helpers shared by the stores: locking, atomic writes, JSON coercion."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


@contextlib.contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Exclusive advisory lock on ``<path>.lock`` for the duration of the block."""
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, text: str) -> None:
    """Write to a unique temp file in the same directory, fsync, then rename over ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def append_line(path: Path, line: str) -> None:
    """Append one line, repairing a missing trailing newline first, then fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        if f.tell() > 0:
            with path.open("rb") as r:
                r.seek(-1, os.SEEK_END)
                if r.read(1) != b"\n":
                    f.write(b"\n")
        f.write(line.encode("utf-8"))
        if not line.endswith("\n"):
            f.write(b"\n")
        f.flush()
        os.fsync(f.fileno())


def _fsync_dir(d: Path) -> None:
    with contextlib.suppress(OSError):
        fd = os.open(str(d), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def jsonable(obj: Any) -> Any:
    """Coerce numpy scalars/arrays and other awkward values into plain JSON types.

    Raises ValueError for values that still cannot be serialised, so callers can refuse
    them before mutating any state."""
    try:
        import numpy as np  # local import: numpy is optional for the stores
    except Exception:  # pragma: no cover
        np = None
    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    try:
        json.dumps(obj)
        return obj
    except TypeError as e:
        raise ValueError(f"value {obj!r} of type {type(obj).__name__} is not JSON-serialisable") from e
