"""Filesystem layout for Mandel's persistent state."""

from __future__ import annotations

import os
from pathlib import Path

MANDEL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = MANDEL_ROOT.parent

# All mutable state lives under DATA_ROOT so it can be relocated in tests
# (set MANDEL_DATA_ROOT) and so the knowledge/ tree stays human-curated.
DATA_ROOT = Path(os.environ.get("MANDEL_DATA_ROOT", MANDEL_ROOT / "state"))

KNOWLEDGE_ROOT = MANDEL_ROOT / "knowledge"


def data_path(*parts: str) -> Path:
    """Return a path under DATA_ROOT, creating parent directories."""
    p = DATA_ROOT.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
