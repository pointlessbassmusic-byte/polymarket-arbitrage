# Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models

- **Authors / kind:** Zhang et al. (Stanford, SambaNova, UC Berkeley). Paper, arXiv 2510.04618 (v3), 2025.
- **Links:** https://arxiv.org/abs/2510.04618 · https://arxiv.org/html/2510.04618v3
- **Date researched:** 2026-10-14. **How much was read:** about 75% of the HTML (method, main results, cost analysis, label-free results, limitations).
- **Selected as A3 because:** it is the closest existing blueprint for a knowledge substrate that improves itself without being rewritten by a model, and it documents the exact failure Mandel's insight store must avoid.

## What it says

- Two failure modes of earlier "evolve the context/prompt" methods: **brevity bias** (optimisation collapses toward short generic prompts and drops domain detail) and **context collapse** (when a model rewrites the whole accumulated context each step). The collapse example: on AppWorld the context at step 60 held 18,282 tokens at 66.7 accuracy; one rewrite later it was 122 tokens at 57.1, below the 63.7 no-adaptation baseline.
- **ACE architecture:** a **Generator** produces reasoning trajectories; a **Reflector** distils insights from successes and errors, optionally over several rounds; a **Curator** turns insights into compact *delta* entries that non-LLM logic merges into the context.
- **Structured bullets.** The context is itemised. Each bullet has a unique id, counters for how often it was marked helpful or harmful, and a small reusable strategy, concept or failure mode as content.
- **Incremental delta updates.** Only localised bullets change; no full rewrites; deltas can merge in parallel.
- **Grow-and-refine.** New bullets are appended, existing ones updated in place (counters incremented); a de-duplication step compares bullets by semantic embedding, run after each delta or lazily when the context window is exceeded.
- **Results (DeepSeek-V3.1):** AppWorld, offline with labels: ICL 46.0, GEPA 46.4, ACE 59.4 against a 42.4 ReAct base; online without labels ACE 59.5 versus Dynamic Cheatsheet 51.9. Finance (FiNER, Formula) offline with labels: ACE average 81.9 against GEPA 72.5 and base 69.1; online ACE 76.6 against DC 71.8.
- **Cost:** adaptation latency on AppWorld offline fell from 53,898 s (GEPA) to 9,517 s (−82.3%) and rollouts from 1,434 to 357 (−75.1%); FiNER online latency 65,104 s → 5,503 s (−91.5%) and token cost $17.7 → $2.9 (−83.6%). Average latency reduction reported as 86.9%. With prompt caching, 91.8% of input tokens were cache hits.
- **Without ground truth:** ACE still gains on AppWorld using execution signals (57.2 offline, 59.5 online). On finance, gains shrink or reverse without labels (FiNER online 67.3, −3.4): "without reliable feedback, the context can be polluted by spurious signals."
- **Limitations:** depends on a reasonably strong Reflector; some domains lack extractable insights; some tasks need only concise guidance.

## Evidence quality

**Rigorous** within its benchmarks (ablations, baselines, cost accounting), with the caveat that the headline numbers are on two task families and one base model, and that the paper's own text cites margins slightly different from its tables.

## What Mandel adopts

- **Never rewrite the knowledge file wholesale.** The insight store is already append-and-update with tombstones; the synthesis document is the one place a full rewrite is allowed, and it is regenerated from the store, not the other way round.
- **Helpful/harmful counters on every insight.** Each time a proposal that depended on an insight passes or fails the gate, the insight's counters move; confidence updates come from counters, not from re-reading.
- **Separate the roles.** Generator (the children and Mandel's proposers), Reflector (the post-mortem on each decided proposal), Curator (deterministic merge into the store). The Curator is code, not a model.
- **De-duplicate by meaning, lazily.** Near-duplicate insights are merged when the store grows past a threshold, keeping provenance from both.
- **Feedback quality gates adaptation.** Where Mandel has only weak signals (no resolutions yet, no backtest), it records candidates but does not adapt behaviour, because ACE's finance results show adaptation on noisy signals makes things worse.

## What Mandel holds loosely or rejects

- Embedding-based de-duplication as the only merge rule: for claims about markets, two bullets can be semantically close and factually opposite; merge requires provenance agreement too.
- Treating the Reflector as a single model call: Mandel's reflection on a failed proposal is a pre-registered checklist (look-ahead? fees? regime?) before any free-form reasoning.
- Accuracy on agent benchmarks as a proxy for forecasting value; the mechanism transfers, the numbers do not.

## Design implications for the RSI predictive substrate

- `Insight` gains `helpful: int`, `harmful: int`; `ProposalBook.decide` increments them for every insight in `depends_on_insights`; `update_confidence` can be driven by a Beta posterior over the counters.
- A `reflect(proposal)` step after every decision that writes a structured post-mortem (which assumption failed, which check caught it) as `kind="procedure"` insights with provenance `proposal:<id>`.
- `InsightStore.dedupe(threshold)` with a provenance-agreement rule; log merges to the ledger.
- `SYNTHESIS.md` is generated from validated insights plus the knowledge files, with a header stating the store version it was built from.
- Metrics: insight churn per cycle, fraction of insights with non-zero counters, collapse guard (store size must not drop by more than a set fraction in one cycle without a logged reason).

## Cross-links

- 06 (Claude as a second brain): the same problem at the personal scale; ACE gives the update rule the video lacks.
- 04 (RSI): the loop applied to context rather than code; A1 (DGM) and A2 (AlphaEvolve) are the code-side twins.
- 02 (Mossbridge): a field adapting on weak signals is what "context pollution" looks like in science.
- ORIGINAL-IDEAS #6 (the signal map as an instrument): edge weights from counters are ACE's helpful/harmful idea rendered.

## Sources used

- https://arxiv.org/html/2510.04618v3 (first ~100k characters)
- https://arxiv.org/abs/2510.04618
