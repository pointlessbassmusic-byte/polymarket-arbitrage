"""
Ingest: turn curated knowledge files into candidate insights.
=============================================================

The knowledge files under ``mandel/knowledge/`` are written by research
agents and read by humans. The insight store is what Mandel's processes
query. ``ingest_knowledge`` bridges them:

- every bullet under "## What Mandel adopts" becomes a *candidate* insight
  tagged ``adopt``, with provenance ``src:NN`` or ``adj:AN`` and a prior
  confidence derived from the file's stated evidence quality;
- every bullet under "## What Mandel holds loosely or rejects" becomes a
  low-confidence insight tagged ``skeptical`` so the doubt is searchable;
- every bullet under "## Design implications ..." becomes a ``procedure``
  insight tagged ``design``.

Ingestion is idempotent: an insight is keyed by the hash of its normalised
text and provenance, so re-running after a file is edited adds only the new
bullets.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from mandel.paths import KNOWLEDGE_ROOT
from mandel.store import InsightStore

SECTION_RULES = (
    # (heading regex, kind, tag, confidence multiplier)
    (re.compile(r"^##\s+what mandel adopts", re.I), "principle", "adopt", 1.0),
    (re.compile(r"^##\s+what mandel holds loosely", re.I), "question", "skeptical", 0.4),
    (re.compile(r"^##\s+design implications", re.I), "procedure", "design", 0.9),
)

QUALITY_PRIOR = {
    "rigorous": 0.80,
    "mainstream-educational": 0.70,
    "practitioner-anecdotal": 0.50,
    "speculative": 0.30,
    "promotional": 0.25,
}
DEFAULT_PRIOR = 0.5

_QUALITY_RX = re.compile(r"(rigorous|mainstream-educational|practitioner-anecdotal|speculative|promotional)", re.I)
_BULLET_RX = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*\S)\s*$")
_FILE_RX = re.compile(r"^(?P<num>\d{2}|A\d+)-(?P<slug>.+)\.md$")


@dataclass
class IngestReport:
    files: int = 0
    added: int = 0
    skipped_existing: int = 0
    per_file: Optional[dict] = None

    def __post_init__(self):
        self.per_file = self.per_file or {}


def _provenance_for(path: Path) -> Optional[str]:
    m = _FILE_RX.match(path.name)
    if not m:
        return None
    num = m.group("num")
    return f"adj:{num}" if num.startswith("A") else f"src:{num}"


def _evidence_quality(text: str) -> Optional[str]:
    """Look for the rating in the 'Evidence quality' section first, then anywhere."""
    section = re.split(r"^##\s+evidence quality.*$", text, flags=re.I | re.M)
    haystack = section[1].split("\n## ")[0] if len(section) > 1 else text
    m = _QUALITY_RX.search(haystack) or _QUALITY_RX.search(text)
    return m.group(1).lower() if m else None


def _sections(text: str) -> Iterable[tuple[str, list[str]]]:
    """Yield (heading line, bullet texts) for every '## ' section."""
    heading, bullets = None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                yield heading, bullets
            heading, bullets = line, []
        elif heading is not None:
            m = _BULLET_RX.match(line)
            if m:
                bullets.append(m.group(1))
    if heading is not None:
        yield heading, bullets


def _fingerprint(text: str, prov: str) -> str:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha1(f"{prov}|{norm}".encode("utf-8")).hexdigest()[:16]


def _strip_markup(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s.strip()


def ingest_file(path: Path, store: InsightStore, existing: set[str]) -> tuple[int, int]:
    prov = _provenance_for(path)
    if prov is None:
        return 0, 0
    text = path.read_text(encoding="utf-8")
    prior = QUALITY_PRIOR.get(_evidence_quality(text) or "", DEFAULT_PRIOR)
    added = skipped = 0
    for heading, bullets in _sections(text):
        for rx, kind, tag, mult in SECTION_RULES:
            if rx.match(heading):
                for b in bullets:
                    body = _strip_markup(b)
                    if len(body) < 12:
                        continue
                    fp = _fingerprint(body, prov)
                    if fp in existing:
                        skipped += 1
                        continue
                    store.add(body, kind, [prov], round(min(0.95, prior * mult), 3),
                              tags=[tag, "ingested", prov.split(":")[0]], notes=f"fp:{fp}")
                    existing.add(fp)
                    added += 1
    return added, skipped


def ingest_knowledge(store: InsightStore, root: Path = KNOWLEDGE_ROOT) -> IngestReport:
    existing = {ins.notes[3:] for ins in store.all() if ins.notes.startswith("fp:")}
    rep = IngestReport()
    files = sorted((root / "sources").glob("*.md")) + sorted((root / "adjacent").glob("*.md"))
    for f in files:
        a, s = ingest_file(f, store, existing)
        rep.files += 1
        rep.added += a
        rep.skipped_existing += s
        rep.per_file[f.name] = {"added": a, "skipped": s}
    return rep
