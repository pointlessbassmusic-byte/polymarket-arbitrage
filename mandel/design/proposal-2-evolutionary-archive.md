# Proposal 2: Mandel as an evolutionary archive

Architect 2 of 4. Lens: open-ended archive with lineage (Darwin Gödel Machine, AlphaEvolve's program database, MAP-Elites). Written 2026-10-14 against engine v0.1.0 (`mandel/*.py`, `mandel/validation/*.py`), SYNTHESIS v0 and ORIGINAL-IDEAS v0. Everything below builds on what exists; each component names the module it extends.

## 1. Thesis

Mandel's objects of improvement (trading strategies, forecasters, and Mandel's own proposing procedures) are one population held in one archive with lineage: each generation proposes a few variants, kills most of them cheaply, gates the survivors out of sample, and keeps a variant that ran and is behaviourally novel even when it lost, because the best results in A1 and src:04 descended through ancestors that were temporarily worse. The fit is that Mandel already owns the two things an archive needs and most self-improvement loops lack, a proposal book with `supersedes` links and a gate the proposer cannot edit, so the archive is a thin index over them plus a parent-sampling rule, not a second engine.

What the archive is not: a validation status. An entry is search state. Only the gate accepts, only acceptance validates an insight, and only the user puts anything on the live-money path (MANDEL.md principle 13). A kept-but-not-accepted entry is called `stepping_stone` so that nobody reads "archived" as "validated".

## 2. Components

### 2.1 The archive: `mandel/archive.py`, state in `mandel/state/archive.jsonl`

Extends `mandel.proposals` (reads `ProposalBook`, uses `supersedes`, `depends_on_insights`, `n_trials_declared`) and writes to `mandel.ledger`. Same storage pattern as the other stores: JSONL loaded in memory, atomic locked writes, every mutation ledgered.

Three genome types share one table.

| genome_type | the genome | fitness (pre-registered metrics) | niche key |
|---|---|---|---|
| `strategy` | a parameter set plus code inside `EVOLVE-BLOCK` markers in `core/arb_engine.py` (edge estimate, sizing), `core/cross_platform_arb.py` (matcher weights, `min_similarity`), and a fee/fill model file | `dsr`, `mean_diff`, `bootstrap_p` at 2x friction, from `strategy_improvement_criteria` | `(platform, category, horizon_bucket)` |
| `forecaster` | a runnable spec: retrieval rule, prompt hash + model id + temperature, calibration map, abstention rule; or a child's repo at a commit | `skill_vs_market`, `brier_delta`, `n_resolved` from `forecast_improvement_criteria`, with coverage reported beside | `(category, market_band in {<0.3, 0.3–0.7, >0.7}, horizon_bucket)` |
| `procedure` | a version of Mandel's proposer: checklist, parent-selection weights, cascade thresholds; never the gate | acceptance rate per version, Brier skill of its idea-market forecasts against the class base rate, usd per accepted proposal | `(role)` |

Entry record:

```
ArchiveEntry
  id             "A-" + 8 hex
  genome_type    strategy | forecaster | procedure
  niche          dict, keys fixed per genome_type
  genome_ref     mandel/genomes/<id>/ (genome.json, optional code, README.md)
  genome_hash    sha256 over the genome directory
  parent_id      entry this was varied from; None for incumbents
  proposal_id    the Proposal that carried it through the gate
  change_type    literature_transfer | idea | hyperparameter | data_sampling | engineering | recombination
  status         stepping_stone | elite | retired
  stage_reached  0..3
  fitness        the gate's observed metrics, with as_of and holdout_id
  descriptor     list[float], behavioural vector from the harness (2.3)
  novelty        distance to nearest same-type entry at admission
  n_children     entries with parent_id == id
  cost           {tokens_est, usd_est, wall_seconds}
  generation_id  Cycle id; created_at; retired_reason
```

Admission is code, not judgement. An entry is written when (a) its proposal reached stage 1 or beyond (compiled, passed tests, produced a descriptor), (b) its evidence was written by the harness, and (c) either the gate accepted it, making it `elite` for its niche and demoting the previous elite to `stepping_stone`, or its `novelty >= delta_type`, making it a `stepping_stone`. Variants failing (a) stay in the proposal book as rejected, ledgered as `archive.refused`, with no entry. Nothing is deleted: `retire(id, reason)` tombstones. Niche cap 12; above it, the oldest `stepping_stone` dominated on every metric and in no elite's lineage is retired with reason `dominated`.

Queries: `lineage(id)` (path to root with each ancestor's status and fitness, so the dips are visible), `elites()`, `by_niche(key)`, `niche_coverage()`, `stepping_stone_rate()` (fraction of elites with a `stepping_stone` ancestor). Ledger kinds: `archive.admitted|elite|demoted|retired|refused|parent_sampled`.

### 2.2 Parent sampling: `Archive.sample_parents(genome_type, k, seed)`

A1's rule with two changes. Within a genome type, w_i = s_i * h_i with s_i = 1 / (1 + exp(-lambda (f_i - f_med))), f_i the entry's primary fitness, f_med the median of its niche (lambda = 10, so a niche-median entry has s = 0.5), and h_i = 1 / (1 + n_children). Change one: one of the k slots per generation is drawn uniformly from `stepping_stone` entries only, the exploration slot, which is the chaos game's rule that every map keeps positive probability (src:09). Change two: every niche keeps probability >= p_floor = 0.05 of supplying at least one parent, so no niche is abandoned. The seed, the weights and the draw are ledgered as `archive.parent_sampled`; `n_trials` for deflation is reconstructed from these events and the cascade's run count, never from the proposer.

### 2.3 Behavioural descriptors: `mandel/validation/descriptors.py` (protected)

Novelty needs a distance that is cheap, numeric, and produced by code the proposer cannot edit. No embeddings and no model judgement.

- strategy: trades per day, mean edge at entry, median holding time, share of trades per platform, share per category (top five), share per regime label, all from the stage-1 slice.
- forecaster: coverage, mean |p - market_p|, ECE, share per category, mean horizon in days, from the stage-1 replay.
- procedure: acceptance rate, usd per proposal, share per change_type.

Dimensions are scaled by the archive's per-dimension IQR; novelty is the L2 distance to the nearest same-type entry. `delta_type` is frozen at generation 0 (0.5 after scaling for all types) and changes only through a `procedure` proposal with its own gate.

### 2.4 The cascade: `mandel/cascade.py`, extends `mandel.validation`

`gate.evaluate` stays as it is: dumb, reading frozen criteria. The cascade is the harness that produces the evidence the gate reads, cheap stages first, writing `stage_reached` and `harness_hash` onto the proposal and calling `record_evidence` itself from its own output.

| stage | what runs | cost | what it kills |
|---|---|---|---|
| 0 | static: protected-path refusal, spec completeness (the src:12 interrogation), string-level diff distance to existing genomes | 0 tokens, under 1 s | duplicates, ruler edits, unspecified changes |
| 1 | `pytest tests/`; strategy: point-in-time replay on the latest 10% of recorded order books; forecaster: replay on 20 resolved questions from the held-out pool, with a touch ledger per question | under 2 CPU-minutes, 0 tokens | crashes, no signal, clear losers; the descriptor is computed here |
| 2 | strategy: `walk_forward_splits` with embargo, 2x registered friction, `compare_strategies` with the harness trial count, a permutation null within blocks; forecaster: at least 30 held-out resolved questions, `skill_vs_market` against the `market:*` reference | under 10 CPU-minutes | the gate's own criteria |
| 3 | incubation on data that did not exist at selection: a forecaster records live under source `arch:<id>` until 30 resolutions; a strategy runs in the dry-run executor until 100 hypothetical fills priced with the backtest's cost model | weeks of wall clock, 0 tokens | drift, repaint, cost optimism |

Stage 2 can make a `forecaster` or `procedure` entry `elite`. A `strategy` entry becomes `elite` only after stage 3, and `elite` means eligible for the user's decision, never live.

Protected ruler, `mandel/protected.py`: a manifest hash over `mandel/validation/`, `mandel/cascade.py`, the admission code, `mandel/ledger.py`, `mandel/forecasts.py`, `core/risk_manager.py`, `core/execution.py` and the held-out datasets. `preregister` records `harness_hash`; `evaluate` refuses when the live hash differs; the manifest changes only with `actor="human"`; `draft` refuses a `change` touching it.

### 2.5 Generations: `mandel.cycles`, extended

A generation is a `Cycle`. `COST_FIELDS` gains `usd_est`; `OUTCOME_FIELDS` gains `variants_proposed`, `stage1_killed`, `stage2_killed`, `entries_admitted`, `elites_changed`, `stepping_stones_kept`. `start` takes a `budget` dict; `finish` records `budget_overrun`. `efficiency()` adds accepted per usd over the last ten generations, which is the campaign stop rule's input.

### 2.6 Children as population members and parallel evaluators: `mandel.children`, extended

Two roles, kept apart in code.

As population: a child's repository at a commit is a `forecaster` genome, `genome_ref = child:<name>@<sha>`, scored in the forecast book under `child:<name>` as now. `register` creates the entry; each reported commit becomes a variant whose `parent_id` is the previous commit's entry, so a child's own history is a lineage Mandel can read.

As evaluators: Mandel appends `EvalJob` rows to `mandel/state/children/<name>/jobs.jsonl`: `{job_id, entry_id, genome_hash, stage, holdout_id, harness_hash, deadline, budget}`. The child runs `python -m mandel job-run <job_id>` from this repository; the command executes the deterministic harness with a fixed seed and itself writes `job_result` (raw output, hash, wall seconds). The child's prose is not evidence. Rules: no child evaluates a variant of its own genome at stage 2 or 3; an entry about to become `elite` needs two independent evaluators (two children, or one child and the Linode cron) with matching evidence hashes, otherwise `claim.mismatch` is written and the entry is held; Mandel re-runs one job in five and records `evaluator_agreement` per child. Dispatch is through `jobs.jsonl` by default and through `send_message` when the user grants remote-session tools; the result path is the same.

### 2.7 Campaign notebook and proposer: `mandel/campaigns/<target>/notebook.md`, `mandel/proposer/vN/`

Per target an append-only notebook in src:04's shape: progression table generated from the archive, current recipe, dead ends with the check that caught each, ranked open ideas with `change_type`. The proposer is a directory, `checklist.md`, `weights.json` (lambda, p_floor, k, delta per type, stage budgets), `prompt.md`; its hash is the `procedure` genome. A generation's proposing step reads the notebook and the archive, samples parents, drafts one proposal per variant, and records an idea-market forecast (`mandel:self`, P(accept)) before `preregister`, as ORIGINAL-IDEAS 2 asks.

### 2.8 The graph: `mandel.graph`, extended

A fourth node class, `entry`, with `lineage` edges; elites coloured by niche; `supports` edge weights driven by insight helpful/harmful counters once `decide` moves them (A3, ORIGINAL-IDEAS 6).

## 3. Data flow

Observations enter from four streams: knowledge files via `ingest`, child reports via `record_report`, resolutions via `ForecastBook.resolve`, and the dry-run executor's fill log. The notebook summarises them per target. The proposer samples parents and drafts proposals; each names its parent entry, change type and the insights it depends on. The cascade runs the stages and writes evidence; the gate decides; the archive admits or refuses and moves the niche elite on a pass. `decide` increments `helpful` or `harmful` (new fields on `Insight`) for every insight in `depends_on_insights`, and a reflection step writes a procedure insight with provenance `proposal:<id>`. The generation closes with cost and outcomes; `graph` rebuilds. Everything is a file under `mandel/state/`, `mandel/genomes/` or `mandel/campaigns/`, committed by the daily cycle, so a fresh session or a child reconstructs the state with `git pull`.

Models that outlive their host chats come out of `mandel/genomes/`: a `forecaster` genome is a directory any runner, a Linode cron job or a child, executes without Mandel present, and its forecasts enter the book under `arch:<id>`. Mandel's session is the proposer and bookkeeper; the models are files.

## 4. One generation, end to end

Trigger: the daily maintenance Routine (OPERATIONS.md) at 06:40 on the Linode runs `verify`, `ingest`, resolutions, `graph`, and then `python -m mandel generation run --target <campaign> --budget usd_est=3,tokens_est=80000`. One generation per day per campaign for `strategy` and `procedure`; `forecaster` populations are evaluated continuously as questions resolve but selected weekly, because the resolution rate, not the budget, bounds them.

1. `cycle-start` with the budget; the generation refuses to open if the previous one overran twice in a row until a human notes why.
2. Sample k = 4 parents (three weighted, one exploration slot); ledger the draw.
3. Propose four variants, one idea each, each with `change_type`, spec, idea-market forecast; stage 0 runs immediately and refuses duplicates and ruler edits for free.
4. `preregister` the survivors with criteria from the standard sets plus `harness_hash`.
5. Stage 1 locally; typically two of four die here. Stage 2 for at most two, locally or as child jobs. At most one new stage-3 incubation starts per generation.
6. `decide`; archive admission; counters; reflection insight; notebook append.
7. `cycle-finish` with measured cost. If accepted per usd over the last ten generations is below the registered floor, the campaign pauses and reports; it never decides it is finished (src:04).

## 5. Validation

The gate is used exactly as built: frozen criteria, `out_of_sample`, harness-counted `n_trials`, the standard criteria sets. The archive adds no criterion and cannot relax one. New evaluators needed, all under the protected manifest: `descriptors.py`; the stage-1 slice replay and the stage-2 permutation null in `cascade.py`; a `procedure_improvement_criteria` set in `gate.py` (`acceptance_rate_delta > 0`, `n_proposals >= 20`, `usd_per_accepted` not worse) so proposer versions pass the same kind of gate as everything else; a touch ledger for held-out questions so a question used at stage 1 is never reused at stage 2; and the shadow-ablation logger (section 11, prediction 3). Incubation thresholds follow src:14's design implications and are pre-registered per entry.

## 6. Child integration

The first-contact protocol in MANDEL.md section 5 gains one step: register the child's repository commit as a `forecaster` entry and ask the twelve open questions from SYNTHESIS. Guidance carries, besides validated insights, the child's evaluation jobs and the lineage of any genome Mandel asks it to vary. A child's claims still enter as candidate insights; its evidence enters only through `job-run`. Independence is measured before pooling: the effective rank of the children's error matrix on shared questions is reported on the scoreboard, and two children citing one backtest count as one evaluator.

## 7. Frugality

Bounded: per-generation budget in tokens and usd, stage caps (4, 2, 1), zero model tokens in evaluation, archive and niche caps, and a campaign stop rule. Measured: every entry carries its cost, every generation its cost and kills per stage, and `status` prints accepted per usd, stage-1 kill rate, and stepping-stone rate. Initial budget per generation: about 80k tokens of proposing (four drafts from the notebook), under 15 CPU-minutes, about usd 1–3 when run as a Routine; these numbers are re-derived from the first four generations' measured cost, and the derivation is logged.

Not done: no LLM-graded fitness anywhere; no embedding store for novelty; no re-evaluation of the whole archive each generation (fitness carries `as_of`, and only elites are re-scored, monthly); no evolution of the ruler, the executor, the risk limits or the weights; no niche without a scorer; no population larger than the stage caps can evaluate.

## 8. Fractal fit

Structural, with the mechanism named. First, the archive is a parameter-space catalogue in src:16's sense: each niche is a region of settings, and the archive records the region over which the gate held (an elite and the neighbours that also passed), not only the best point; a variant within one grid step of a `retired` failure gets an extra out-of-sample window. Second, the same loop runs at three levels, procedure, child, strategy, in one table with a `genome_type` column, but each level's budgets, deltas and cadences are derived from that level's measured cost and resolution rate, since renormalised copies share shape and not parameters. Third, the exploration slot and p_floor are the chaos game's positive-probability rule (src:09). Fourth, ORIGINAL-IDEAS 3's scale-consistency check joins the stage-2 criteria once k is pre-registered. Decorative, and labelled so: any resemblance between the lineage tree and a Julia set, and any claim that the archive is "self-similar". If the three levels need different procedures (ORIGINAL-IDEAS 7's falsifier), the shared table stays and the shared loop is dropped.

## 9. First four weeks

Week 1. `mandel/archive.py` with `ArchiveEntry`, admission, `lineage`, `sample_parents` with ledgered seeds; `mandel/protected.py` manifest, `harness_hash` on `Proposal`, `parent_entry`, `change_type`, `niche`, `stage_reached` fields; tests. Start `core/recorder.py` writing point-in-time order-book snapshots with `available_at` to `data/books/`, because `utils/backtest.py` is a simulator with planted mispricings and nothing in the archive may be scored on it. Generation 0: register incumbents, the current `config.yaml` bot as strategy S0, the market-copy forecaster F0, proposer v1 as P0.

Week 2. `mandel/cascade.py` stages 0–2 for strategies and forecasters; `descriptors.py`; `generation run` CLI; first generation with four variants of S0 (`min_edge`, `min_similarity`, sizing, fee model); idea-market forecasts recorded.

Week 3. Children protocol: `jobs.jsonl`, `job-run`, `job-verify` with one-in-five re-runs; the first child registered as a forecaster entry; campaign notebook; `helpful`/`harmful` counters moved by `decide`; reflection insights.

Week 4. Proposer v1 as a directory and the `procedure` criteria set; archive layer in `graph.py`; stepping-stone rate, stage-kill rate and evaluator agreement in `status`; first re-derivation of budgets from measured cost.

## 10. Risks

Resolution rate: the forecaster population fills slowly; for months the archive is mostly strategy and procedure entries. Data: the bot has no historical store, so the recorder gates everything; until weeks of books exist, strategy variants cannot reach stage 2. Niche proliferation dilutes the budget; the niche key is fixed and a new niche needs a proposal. Novelty gaming: a proposer could emit novel junk; admission requires stage 1, novelty is a bonus not the objective, and the niche cap bounds the damage. Correlated evaluators: children share a base model and data; the deterministic harness, cross-niche assignment and re-run sampling make their evidence reproducible, not independent, and the design says so. Procedure evolution is slowest to measure (twenty proposals per version). `stepping_stone` must never be read as validated; `status` prints the distinction.

## 11. Falsifiable predictions

1. Stage 1 kills at least half of variants at under five percent of evaluation cost within the first eight generations; if stage 1 never kills anything stage 2 would not have, the cascade collapses to two stages.
2. After forty decided proposals, at least one elite has a `stepping_stone` ancestor; if the rate is still zero at one hundred, the archive is replaced by champion-only selection (SYNTHESIS principle 10).
3. Novelty-weighted sampling fills more niches with elites than score-only sampling, measured by running the ablation in shadow mode (logging what it would have picked) for eight generations; if the two pick the same parents, h_i is dropped.
4. Child evaluations agree with Mandel's re-runs on evidence hash at least 95% of the time; a lower rate means the environments differ and child evidence is downgraded to stage 1 only.
5. Proposer v2, written after the first notebook of dead ends, has a higher acceptance rate than v1 at equal cost over twenty proposals; if not, procedure evolution is paused as cost without gain.
6. Within six weeks at least one forecaster entry shows `skill_vs_market > 0` on thirty held-out questions in some niche with coverage reported; if none does, the forecaster population shrinks to F0 plus one explorer, and the finding is recorded as a negative insight.
7. Measured usd per generation stays within the registered budget in at least eight of the first ten generations; two consecutive overruns stop the campaign until a human reads the costs.
