"""Tests for the knowledge -> insight ingest bridge."""

from mandel.ingest import ingest_knowledge, _evidence_quality, _provenance_for
from mandel.ledger import Ledger
from mandel.store import InsightStore
from pathlib import Path

SAMPLE = """# Some resource
- **Creator:** X
- **Coverage confidence:** 0.5

## What it says
- a claim that is not ingested

## Evidence quality
**Rating: speculative.** Because reasons.

## What Mandel adopts
- **Pre-register** everything, because `goalposts` move.
- Short
- Another principle worth keeping, with detail.

## What Mandel holds loosely or rejects
1. Precognition as a mechanism.

## Design implications for the RSI predictive substrate
- Add an `available_at` timestamp to every datum.

## Sources used
- https://example.org
"""


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    (root / "sources").mkdir(parents=True)
    (root / "adjacent").mkdir()
    (root / "sources" / "07-sample.md").write_text(SAMPLE)
    (root / "adjacent" / "A2-other.md").write_text(SAMPLE.replace("speculative", "rigorous"))
    (root / "sources" / "README.md").write_text("# not a source file")
    return root


def test_provenance_and_quality_parsing():
    assert _provenance_for(Path("07-sample.md")) == "src:07"
    assert _provenance_for(Path("A2-other.md")) == "adj:A2"
    assert _provenance_for(Path("README.md")) is None
    assert _evidence_quality(SAMPLE) == "speculative"


def test_ingest_sections_priors_and_idempotency(tmp_path):
    root = _tree(tmp_path)
    store = InsightStore(tmp_path / "i.jsonl", Ledger(tmp_path / "l.jsonl"))
    rep = ingest_knowledge(store, root)
    assert rep.files == 3
    assert rep.per_file["README.md"] == {"added": 0, "skipped": 0}
    # per file: 2 adopt bullets (the "Short" one is dropped), 1 skeptical, 1 design
    assert rep.per_file["07-sample.md"]["added"] == 4
    assert rep.added == 8

    adopt = store.query(tag="adopt")
    assert all(i.kind == "principle" for i in adopt)
    src7 = [i for i in adopt if i.provenance == ["src:07"]]
    assert src7 and all(i.confidence == 0.3 for i in src7)          # speculative prior
    assert any("Pre-register everything, because goalposts move." == i.text for i in src7)   # markup stripped
    a2 = [i for i in adopt if i.provenance == ["adj:A2"]]
    assert a2 and all(i.confidence == 0.8 for i in a2)             # rigorous prior
    skept = store.query(tag="skeptical")
    assert len(skept) == 2 and all(i.kind == "question" and i.confidence < 0.4 for i in skept)
    design = store.query(tag="design")
    assert len(design) == 2 and all(i.kind == "procedure" for i in design)

    rep2 = ingest_knowledge(store, root)
    assert rep2.added == 0 and rep2.skipped_existing == 8
    # an edit adds only the new bullet
    f = root / "sources" / "07-sample.md"
    f.write_text(f.read_text().replace("## What Mandel holds loosely or rejects", "- A brand new adopted principle here.\n\n## What Mandel holds loosely or rejects"))
    rep3 = ingest_knowledge(store, root)
    assert rep3.added == 1
