# Mandel knowledge tree

Human-curated, agent-written knowledge. Read `SYNTHESIS.md` first.

- `sources/NN-*.md`: the user's 16 provided resources (videos, a playlist), distilled with
  an honest evidence-quality rating and a coverage confidence (how sure the writer is that
  the file reflects the specific video rather than the general topic).
- `adjacent/AN-*.md`: resources Mandel found itself, selected by a three-judge panel from a
  multi-lane sweep for the most adjacent and most applicable material.
- `SYNTHESIS.md`: cross-cutting ideas, tensions, design principles, open questions.

Every file has the same sections so that `python -m mandel ingest` can turn the
"What Mandel adopts", "What Mandel holds loosely or rejects" and "Design implications"
bullets into candidate insights with provenance `src:NN` / `adj:AN`.
