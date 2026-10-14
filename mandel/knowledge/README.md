# Mandel knowledge tree

Human-curated, agent-written knowledge. Read `SYNTHESIS.md` first, then `ORIGINAL-IDEAS.md`,
then `CRITIQUE-<date>.md` for what the next learning pass must fix.

- `sources/NN-*.md`: the user's 16 provided resources (videos, a playlist), distilled with an
  honest evidence-quality rating and a coverage confidence (how sure the writer is that the
  file reflects the specific video rather than the general topic).
- `adjacent/AN-*.md`: resources Mandel found itself, selected from a 7-lane, 68-candidate sweep
  (`adjacent/candidates.json`) for adjacency to the user's picks and applicability to the loop.
- `SYNTHESIS.md`: cross-cutting ideas, tensions, design principles, open questions, coverage.
  Regenerated as a whole when its inputs change; never patched in place.
- `ORIGINAL-IDEAS.md`: Mandel's own ideas beyond the sources, each with its falsifier.
- `CRITIQUE-2026-10-14.md`: an independent critic's report on the first pass.

Every source and adjacent file carries the same sections and two frontmatter lines that the
tooling reads: `**Coverage confidence:** 0.NN` and `**Rating: <quality>.**` at the top of
"Evidence quality". `python -m mandel ingest` turns the "What Mandel adopts", "What Mandel holds
loosely or rejects" and "Design implications" bullets into candidate insights with provenance
`src:NN` / `adj:AN`; `python -m mandel graph` rebuilds the signal map from the same files.

`SOCIAL-SOURCES.md` (2026-10-14): 36 verified sentiment / attention / flow / congress / crypto sources by priority (now, with-key, later, avoid), the daily collection plan and the controls every predictive use must pass. The theories they feed are T-38 to T-47 in `../theories/THEORIES.md`.
