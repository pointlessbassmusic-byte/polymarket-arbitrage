# Proposal 3: Everything Is a Scored Question

*Architect 3 of 4. Lens: forecasting-first, Bayesian hierarchical. Written 2026-10-14 against the engine as it stands (`mandel/*.py`, `mandel/validation/*.py`, 696 ledger events, 0 forecasts, 0 proposals).*

## 1. Thesis

Every belief Mandel holds is written as a probability on a question that will resolve, is scored with a proper scoring rule when it does, and is pooled hierarchically (question → category → source → global) so that thin cells borrow strength from thick ones. Mandel's beliefs about the children ("Julia beats the market on sports at 7–30 day horizons") are forecasts in the same book, scored the same way, and the posterior from that book is the only thing that decides where tokens, questions and guidance go.

This fits because the forecast book, proper scoring and skill-versus-market already exist (`forecasts.py`, `validation/scoring.py`), because the host repository's domain, prediction markets, produces an external, mechanical, unfakeable resolution stream for free, and because the requirement that models "live outside their host chats" is met the moment a model is just another `source` whose forecasts a cron job writes into the book.

## 2. Components

Each component names the module it extends. Nothing below replaces the ledger, store, proposal book, gate or CLI.

**2.1 Question bank** (`mandel/questions.py`, new; extends `forecasts.py`). A `Question` record: `qid`, `text`, `kind` ∈ {`market`, `meta`, `child-claim`, `child-model`}, `category` (Gamma `category` / Kalshi `series_ticker`, mapped to a fixed list of eight), `platform_refs` {`polymarket_condition_id`, `kalshi_ticker`}, `open_ts`, `close_ts`, `resolution_rule`, `resolution_source`, `status` ∈ {open, resolved, void}, `sampled_by` (the hash of the sampling rule). `ForecastBook.record` gains a `question_id` lookup into the bank and refuses forecasts after `close_ts`; `Forecast` gains `evidence_cutoff_ts` and `abstained` (A5). Stored in `state/questions.jsonl`, append-only with status events.

Four question kinds:

- *Market questions*: binary markets closing in 1–60 days, sampled weekly by a frozen stratified rule (five per category, horizon buckets ≤7d / 7–30d / 30–60d filled in rotation, liquidity ≥ USD 5k, spread ≤ 4c). The mid price at sampling and at every daily refresh is recorded as `market:polymarket` / `market:kalshi` forecasts, which is what `_market_reference` already needs.
- *Meta questions*: "P-xxxx passes the gate" (ORIGINAL-IDEAS 2), "insight I-xxxx is cited by an accepted proposal within 90 days", "child X delivers ≥ 15 forecasts by date". These resolve mechanically from ledger events, so they cost nothing to adjudicate.
- *Child-claim questions*: every number in a `ChildReport.metrics` ("win rate 0.57") becomes "the re-measured out-of-sample value is ≥ 0.57 × 0.9", with the child's implied confidence as its forecast and Mandel's shrunk estimate beside it. Resolution is the re-run.
- *Child-model questions*: "over the next 30 resolved questions in category c, child s has skill > 0". Mandel's forecast is the posterior predictive from 2.3; this is where a model of a child becomes a scored object.

**2.2 Resolution feed** (`mandel/resolve.py`, new; extends `ForecastBook.resolve`, uses `polymarket_client.api` and `kalshi_client.api` read-only). Pulls `Market.resolved/resolution` and `KalshiMarket.result` for open market questions, resolves meta questions by scanning `Ledger.events("proposal.")` etc., writes `Resolution` with both `resolved_at` (world time) and `available_at` (when Mandel learned it, ORIGINAL-IDEAS 1). Ambiguous platform resolutions void the question rather than being guessed.

**2.3 Hierarchical scoreboard** (`mandel/validation/hierarchy.py`, new; extends `scoring.py` and `ForecastBook.scoreboard`). For source s, category c, resolved question q, the observation is the Brier difference against the market, d_{scq} = BS(market_q) − BS(s,q), positive when s beat the price. Per cell: mean d̄_{sc}, variance s²_{sc}, and n_eff from the lag-1 autocorrelation of d ordered by resolution time (src:11; `n_eff = n(1−ρ)/(1+ρ)`). The model is a two-level normal hierarchy, fitted by method of moments (DerSimonian–Laird) in closed form, no sampler:

```
d̄_sc | θ_sc ~ N(θ_sc, s²_sc / n_eff_sc)
θ_sc  | a_s  ~ N(a_s, τ²)          # category effect within a source
a_s   | μ    ~ N(μ, ω²)             # source effect
```

Posterior for a cell: shrink d̄_{sc} toward â_s with weight v/(v+τ²), v = s²/n_eff; report `theta_hat`, `theta_sd`, `p_positive = Φ(theta_hat / theta_sd)`, `n`, `n_eff`, `coverage` (fraction of assigned questions the source answered). Cells with n_eff < 5 inherit the parent's posterior with sd inflated by τ. The same operator runs one level up (source toward global μ), which is the one place the fractal framing is structural (section 8). Output is `state/scoreboard.json`, regenerated whole each run (A3's rule for derived files), with a `scoreboard.refit` ledger event carrying the input hash.

The scoreboard also carries a per-source *regime table* (A5): `p_positive` by market-price bucket (0.3–0.7 vs tails) and by horizon bucket, computed with the same shrinkage. `ForecastBook.scored_pairs` gains a `horizon_bucket` argument that takes the latest forecast *within the bucket*, so a source cannot earn its score by forecasting an hour before close.

**2.4 Pools as sources** (`mandel/pool.py`, new; extends `ForecastBook`). On any question with ≥ 2 non-market sources, two pooled forecasts are written as sources `pool:trimmed` (A5) and `pool:lop` (log-opinion pool weighted by `p_positive` of the contributing cells, extremising exponent fixed at 1.0 until pre-registered otherwise). Pools are scored like everyone else. `n_effective` (effective rank of the sources' residual matrix on shared questions, src:10) is reported beside every pool score because two children on one base model are closer to one source than two.

**2.5 Models outside chats** (`mandel/models/recal.py`, new; registers as source `model:recal-v1`). The first external model is deliberately plain: a logit recalibration of the market price per category, `logit(p) = α_c + β_c·logit(m)`, with (α_c, β_c) shrunk toward (0, 1) using the same hierarchy, refit monthly on resolved questions only, frozen and versioned (`model:recal-v1`, `-v2`, ...). The daily job runs it on every open question. It is the baseline every child and later model (src:11's Markov count model, A4's MSM feature) must beat, and it proves the pipeline scores a model no session is talking to.

**2.6 Allocation** (`mandel/allocate.py`, new; extends `cycles.py` and `children.py`). Three budgets are allocated weekly from the posterior: *guidance slots* (which cells receive Mandel's attention and a regime table), *proposal slots* (which cells get a gate run, the expensive step), and *Mandel's own forecast slots* (which questions Mandel spends tokens forecasting). Allocation is Thompson sampling: draw θ̃ from each cell's posterior 1,000 times, allocate in proportion to the frequency a cell is best, mixed with a uniform floor of 0.15 (src:11's damping, A1's exploration floor). Question sampling itself is *not* allocated; it stays stratified-uniform under a hashed rule, so the question set cannot be bent toward where a child looks good. Every allocation is a ledger event `allocation.weekly` with the posterior snapshot it used, so ORIGINAL-IDEAS 4's test (is the ranking stable enough to act on?) is answerable from the record.

**2.7 Insights tied to questions** (extends `store.py`). `Insight` gains `question_ids: list[str]`. When a linked question resolves, `InsightStore.update_from_resolution` moves confidence by a Bayes step with a logged reason, replacing the ad hoc helpful/harmful counters with a scored forecast. The `mandel:self` cap of 0.5 is untouched.

**2.8 Child protocol** (extends `children.py`). `ChildReport` gains `forecasts: list[{question_id, p, ts, evidence_cutoff_ts, abstained}]`; `record_report` writes them into the book under `child:<name>`. `Guidance` gains `questions_assigned` and `regime_table`. Files: `state/children/<slug>/inbox.jsonl` (questions Mandel assigns) and `outbox.jsonl` (forecasts the child returns via `python -m mandel child-forecast`). When the user grants remote-session tools, the same two files are what Mandel sends and reads.

**2.9 Gate criteria** (extends `validation/gate.py`). New standard set `forecaster_hier_criteria`: `n_eff_resolved ≥ 30`, `p_positive ≥ 0.9`, `skill_vs_market_ci_low > 0` from a time-blocked bootstrap of the d series (reusing `block_bootstrap_pvalue` on d versus zeros), `coverage ≥ declared`, `beats_recal == 1`. `evaluate` is unchanged; it only learns new metric names.

**2.10 CLI** (extends `cli.py`): `questions`, `question-sample`, `resolve-pull`, `scoreboard --hier [--by category|horizon]`, `allocate`, `child-forecast`, `model-run`.

## 3. Data flow

Platforms → `question-sample` (stratified, hashed rule) → `questions.jsonl` with `market:*` prices → children (inbox), Mandel, `model:recal-v1` and pools write forecasts → `forecasts.jsonl` → daily `resolve-pull` → `Resolution` → `hierarchy.fit` → `scoreboard.json` + `scoreboard.refit` event → `allocate` → guidance (regime tables, question slots) and proposal drafts → gate → accepted proposals validate insights; resolutions move linked insights' confidence → `SYNTHESIS.md` regenerated from the store monthly. Every arrow is a file or a ledger event.

## 4. One cycle end to end

- **Daily, no model tokens** (the existing systemd timer in OPERATIONS.md, or a Routine): `resolve-pull`, refresh `market:*` prices on open questions, `model-run recal-v1`, `scoreboard --hier`, `verify`, commit. Budget: ≤ 300 API calls, < 60 s wall.
- **Weekly, one session** (trigger: Monday Routine): `question-sample` 40; read child outboxes and record reports; `allocate`; Mandel forecasts its ≤ 20 allocated questions with a declared `evidence_cutoff_ts`; write guidance with regime tables and assigned questions; for any cell with `p_positive ≥ 0.9` and `n_eff ≥ 30`, draft one proposal (forecaster criteria, or a `core/` strategy proposal in dry-run if the cell is a child or model whose forecasts can be turned into signals); for any cell with `p_positive ≤ 0.1`, guidance says abstain there. Pre-register, record evidence from the scoreboard (the gate reads the file the hierarchy wrote, not the proposer's claim), decide. Finish the cycle with cost. Budget: ≤ 150k tokens (operator estimate), ≤ 90 min.
- **Monthly**: refit `recal` to a new version, pooling comparison checkpoint (trimmed versus lop), proposer hit rate per version, Mandel's Brier skill on meta questions versus the class base rate, regenerate SYNTHESIS. Budget: ≤ 400k tokens.
- **Quarterly**: re-validate every accepted forecaster proposal on the trailing 90 days; roll back any whose `p_positive` has fallen below 0.5 (principle 10).

A cycle always produces a week of resolutions and one allocation; it produces a proposal only when the posterior says one is worth the gate run.

## 5. Validation

The existing gate decides, unchanged. What is new is where evidence comes from and the controls around it.

- Evidence for forecaster proposals is read from `scoreboard.json` by the gate wrapper, never typed by the proposer; the file's hash is in the `scoreboard.refit` event.
- Two permanent control sources on the board: `control:coin` (the market mid plus N(0, 0.03) noise) must sit at `p_positive` ≈ 0.5; `control:oracle` (outcome with 20% label noise, written after resolution into a *separate* test book, never the live one) must reach `p_positive` > 0.95 within 30 questions. If coin shows skill, there is a leak; if oracle does not, the scoring path is broken.
- A label-shuffle null: outcomes permuted within category × month blocks; every source's `p_positive` under the null is reported beside the real one.
- Calibration is tested as a slope: β_s shrunk toward 1; a child with β < 0.6 gets a recalibration proposal, not a trading proposal.
- Metric invariants run on every refit: Brier ∈ [0,1], Murphy reconstruction matches `brier_score`, d bounded in [−1, 1].
- Mandel's own forecasts on meta questions are scored as Brier skill against the base rate of the proposal class (SYNTHESIS verdict on idea 2), with coverage and an ambition measure (mean predicted pass probability) reported beside skill.

## 6. Child integration

First contact follows MANDEL.md section 5 and adds two steps: Mandel assigns the child 20 questions from the cells in its domain with the highest posterior sd (where there is most to learn), and turns each quantitative claim in its first report into a child-claim question. From then on the child is a row on the scoreboard. Guidance to a child is mostly its own regime table: where its `p_positive` is high, low, and unknown, with the questions assigned for the week. A child silent for three weeks keeps only its floor share of guidance. Graduation is a scoreboard event: a child cell that passes `forecaster_hier_criteria` becomes the input to a dry-run strategy proposal against `core/arb_engine.py` (its probabilities as the fair-value side of a bundle or cross-platform signal), judged by `strategy_improvement_criteria` with friction doubled. The user holds the live switch.

## 7. Frugality

Bounded: 40 questions/week; Mandel forecasts ≤ 20/week; daily job spends API calls only; weekly ≤ 150k tokens; monthly ≤ 400k; hierarchy fit is closed form and runs in milliseconds; pools and `recal` cost nothing beyond the daily job. Measured: cost per resolved question, validated bits per 1k tokens (log-loss reduction of accepted sources over `recal`), gate runs per accepted proposal, all in `cycles.jsonl`. Not done in v1: no MCMC, no vector store, no LLM judge, no retrieval pipeline for Mandel's own forecasts (A5's retrieval wins were 22% of questions at real cost; Mandel's first forecaster is `recal` plus a Markov base rate, and retrieval enters only as a gated proposal), no fine-tuning, no live money, no per-question horizon × category × source cells until n permits.

## 8. Where the fractal framing is structural

Partial pooling is the same operator applied at every level: a cell is shrunk toward its source, a source toward the global mean, with the shrinkage weight re-estimated from the variance *at that level*. That is renormalisation in the sense SYNTHESIS allows (same shape, re-derived parameters, src:16). ORIGINAL-IDEAS 3 becomes a criterion here: the sign of θ̂ must agree at cell, source and global levels for the cell to be called an edge, and `n_scales_agree` is reported. Nothing else fractal is claimed; the market is not asserted to be self-similar.

## 9. First four weeks

1. Week 1: `questions.py`, `resolve.py`, CLI commands, tests; sample the first 40 market questions and record prices; add `control:coin`; ledger kinds `question.*`, `scoreboard.refit`.
2. Week 2: `hierarchy.py` with the moment estimator, `scoreboard.json`, horizon-bucketed scoring, meta questions auto-created at `preregister` (ORIGINAL-IDEAS 2 live); daily Routine or timer running.
3. Week 3: child inbox/outbox and `child-forecast`; `allocate` v1; `model:recal-v1` running daily; first child registered and assigned 20 questions.
4. Week 4: `pool.py` sources; `forecaster_hier_criteria`; pre-register the six predictions in section 11 as proposals; regenerate SYNTHESIS from the store.

## 10. Risks

Resolution is slow: 40/week at 1–60 day horizons gives roughly 150 resolved questions by week 8, so cells stay thin and shrinkage makes every source look like the global mean for a while; correct, but the design's advantage is invisible early. Market mid as reference is noisy on thin books; the liquidity and spread filters mitigate but do not remove it. Children on one base model are correlated, so pooling gains will be small and `n_effective` may be near 1. Meta questions can be gamed by proposing only safe bets; ambition is reported but not enforced. Platform APIs change, and voiding loses questions. The normal model on Brier differences is a convenience; with n_eff < 10 per cell its posterior sd is an understatement and the gate's `n_eff ≥ 30` is what protects against it.

## 11. Falsifiable predictions

1. By week 6, ≥ 120 market questions have resolved, `control:coin` has `p_positive` in [0.3, 0.7], and `control:oracle` exceeds 0.95; a coin with skill means a leak and the design is wrong until it is found.
2. No child, pool or model reaches source-level `p_positive ≥ 0.9` with `n_eff ≥ 30` within the first 100 resolved questions; if one does, it is the first real candidate for a strategy proposal.
3. Shrunk and raw cell rankings differ in at least one allocation decision in each of the first 8 weeks; if they never differ, the hierarchy is bookkeeping and can be dropped.
4. Week-to-week Spearman correlation of cell `theta_hat` rankings stays below 0.5 for the first 8 weeks, so the floor dominates allocation; if it exceeds 0.7 by week 4, exploitation can start earlier than planned.
5. With two children sharing a base model, `n_effective` < 1.5 and neither pool beats the best single child over the first 100 shared questions (ORIGINAL-IDEAS 5's precondition fails before its test can pass).
6. Mandel's Brier skill against the class base rate on meta questions is positive over the first 30 decided proposals; if not, the proposer's priors carry no information and allocation should ignore them.
