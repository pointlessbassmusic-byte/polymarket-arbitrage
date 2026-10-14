# Mandel architecture (v1 draft, revised after red team)

*Written 2026-10-14 against engine v0.1.0, the v0 knowledge files and the four proposals in `design/`; revised against a 42-finding red team (log at the end). The substrate holds 696 candidate insights and no validated insight, proposal, forecast, resolution or child. Every number below is a seed to be replaced by a measured one. This file and MANDEL.md have no scorer: they sit in the human-review row of the validation table and are revised by a proposal whose evidence is the §Falsifiable predictions checks, decided by the user.*

## Thesis

Mandel's binding constraint is resolved out-of-sample observations, not reasoning. The gate needs about thirty resolved questions or held-out periods per verdict and the substrate has none. So the architecture is a deterministic, zero-token daily job that accrues observations, builds evidence and decides proposals the day they become decidable, and a model session that starts only to interpret a decision or a report. Most days end at zero model tokens.

Three things make the loop trustworthy. Evidence is built and decided by code from records written before outcomes were known, with every selector frozen at pre-registration; the proposer never types a number or chooses the day. The ruler sits under a hash manifest; tampering is detectable, not prevented, so the human actor is a signature checked by `verify`, not a flag, and git history is the external anchor. The scoring path is checked continuously by controls, a shuffle null that is a reject criterion, and a timestamp audit.

## Honest scope

Mandel is a Claude model in a Claude Code session. It cannot change its weights and knows at session start exactly what the files say. "Self-improvement" means four measurable things:

1. Pre-registered changes to files, code, evaluators and protocols that passed the gate out of sample and were recorded with their cost. Metric: accepted proposals and tokens per accepted proposal, per criteria set; `code` proposals are outside the headline because any refactor with green tests passes.
2. A proposer whose hit rate is tracked per version (`proposer_version` = hash of `PLAYBOOK.md` plus model id, stamped at `draft`) through the idea market: a `mandel:self` forecast on every proposal, bound to the draft's criteria hash, with coverage and ambition beside skill. Reported, not gated, until thirty decisions exist.
3. Memory of what did not work: rejected and stale proposals, voids, negative insights.
4. Pipelines that score models no session is talking to, each under its own source name. "Outside its host chat" means without a session, not free: a genome that calls a model has a token line and an availability check.

What it cannot mean: a smarter model, or any live-money change without the user's decision. Acceptance carries the false-accept risk of its criteria; an accepted strategy proposal is a detection result under a declared fill model, not a trading result.

## Components

| # | Component | Role | Module |
|---|---|---|---|
| 1 | Engine | ledger, insight store, proposals, forecast book, children registry, cycle log, gate, scoring, backtest statistics, CLI (built, 79 tests) | `mandel/*.py`, `validation/*` |
| 2 | Protected ruler | manifest over `validation/`, the ledger, forecast and proposal books, `daily.py`, `questions.py`, the executor's limits and held-out data; recorded at `preregister`, checked at `evaluate` for the files the criteria set uses; protected paths refused at `draft`; `actor="human"` events carry an ed25519 signature (key on the PC) checked by `verify`; a signed `manifest.migrated` re-binds open proposals | new `protected.py`, `validation/MANIFEST.json` |
| 3 | Daily job | zero-token accrual, builders and `decide`, controls, triggers, STATUS; sole writer of `state/` on `main` | new `daily.py`; replaces `ingest && graph` in the timer |
| 4 | Question bank | weekly stratified sample under a frozen hashed rule; one `question_id` per platform market; eight categories (politics, economics, crypto, sports, science-tech, culture, weather, other) mapped from Gamma `category`/tags and Kalshi `series_ticker` prefixes; bucket = days from forecast ts to `close_ts`; matched pairs are a separate gated step | new `questions.py`, `polymarket_client/api.py` |
| 5 | STATUS card and triggers | at most 80 lines, each a query over state (sources with n < 5 dropped first, then the oldest bucket); power, nearest-source, void-rate and live-cap lines | `daily.py` → `state/STATUS.md`, `triggers.json`, `declined.jsonl` |
| 6 | Playbook and metered sessions | `session.sh` runs `claude -p --output-format json --max-turns N` under a settings deny-list and writes usage and USD to `cycle-finish` | new `PLAYBOOK.md`, `bin/session.sh`, `bin/settings.json`; `cycles.py` gains metered fields |
| 7 | Evidence from code | builders take every selector from the ledgered pre-registration and refuse flags; `replay.py` runs only for an open pre-registered proposal; `--run-tests`; typed evidence only for signed `--actor human`; every evaluated bundle logged with gross and net edge | `validation/gate.py`, new `validation/replay.py`, `core/arb_engine.py`, `utils/logging_utils.py` |
| 8 | Controls | `control:coin`, `control:oracle`, shuffle null, timestamp audit, metric invariants (§Validation) | new `validation/controls.py` (protected) |
| 9 | Idea market | `preregister` requires a `mandel:self` forecast on `proposal:<id>:passes` tagged with the current criteria hash, `market_p` = base rate of the criteria-set class; `decide` resolves it | `proposals.py`, `forecasts.py` |
| 10 | Inbox and evaluator jobs | reports by file on `inbox/<child>` branches; `job-run` executes a deterministic harness and writes its result hash; the Linode run is the evidence, child hashes move `evaluator_agreement` | `children.py`, new `jobs.py` |
| 11 | First external model | `model:recal-v1`: pooled logit recalibration of the market price, per category once it has 30 resolutions; refit monthly, versioned, run daily by cron; a pipeline test, not an edge | new `models/recal.py`, `model-run` |
| 12 | Region catalogue | accepts and rejects on a grid fixed per target by human actor; a candidate one step from a reject needs an extra window; `roll_back` retires the region | new `regions.py` |
| 13 | Incubation and re-validation | accepted strategies run as shadow configs in the dry-run executor until 100 hypothetical fills; quarterly re-validation as a superseding proposal (§The cycle) | `daily.py`, `proposals.roll_back` |

Deferred, with its paying condition: insight counters (tenth decided proposal); `n_scales_agree` (100 resolutions); hierarchical shrinkage (a cell at n_eff 10); pooling of children (30 shared resolutions, measured effective rank); synthesis regeneration (ten validated insights); archive with parent sampling (twenty decisions, one stepping stone); a gated `procedure` set (thirty decisions, permutation null); the tier D/E sole-support rule (with the counters; the `tier`, `independence`, `incentive` fields land in week 2); vector store (three failed retrieval audits).

## Data flow

```
 Polymarket / Kalshi public APIs ─┐
 inbox/<child> branches, user files ┼─► daily.py  (0 tokens, ≤120 batched API calls, wall_seconds reported)
 logs/opportunities.jsonl (bot)    ┘      │ fetch inbox branches → verify + reconcile + manifest + signatures
                                          │ sample questions → record market:* mids (one forecast.batch event)
                                          │ resolve (question.voided) → ingest inbox (inbox.failed) → roll up opportunities
                                          │ controls + shuffle null + timestamp audit → build evidence + decide → regions
                                          │ triggers → STATUS.md → ledger daily.ran → commit, rebase, push
                                          ▼
                     STATUS.md + triggers.json ──── nothing fired ──► stop (0 tokens)
                                          │ fired, and the envelope has room (else declined.jsonl)
                                          ▼
          session.sh ─► claude -p --output-format json --max-turns N --settings deny-list
                                          │ Tier 1 ≤60k tok | Tier 2 ≤300k tok (metered after the fact)
                                          ▼
          interpret: insight-*, child-guide, backlog.md, proposal-draft ─► commit
                                          ▼
          session.sh parses usage ─► cycle-finish (metered) ─► budget.json ─► tomorrow's card
```

## The cycle

**Every day, 06:40 UTC, zero tokens.** `python -m mandel daily`, in fixed order: fetch `inbox/*` branches and copy new files (the job is `state/`'s only writer and rebases before pushing); integrity checks (a failure fires T4 and stops the run); on Mondays, sample questions under the hashed rule (frozen in `questions.py`); record `market:polymarket` and `market:kalshi` mids for every open question in batched fetches (20 ids a call, about 20 calls), ledgered as one `forecast.batch` event with a content hash; resolve under the frozen rules (Polymarket: `umaResolutionStatus == "resolved"` and `outcomePrices` equal to ["1","0"] or ["0","1"]; Kalshi: `status == "settled"` with `result`), ledgering `question.voided {reason}` for anything else; ingest the inbox, ledgering `inbox.failed {file_hash}` on a parse failure; roll up opportunity rows; write controls; rescore with the shuffle null, timestamp audit and invariants; build evidence and `decide` every proposal whose frozen minimum sample is met, so rejections land the day they are decidable (a decidable proposal still open after three days is ledgered `proposal.stale`); evaluate triggers; write STATUS; append `daily.ran {api_calls, wall_seconds, triggers, controls_ok}` (the 300 s wall cap is a card line, not T4); commit.

**Triggers.** T1 `decided`: a proposal was decided today and `controls_ok` held; the session interprets. T2 `child_report`: new inbox files or job results, batched into at most one session per three days; T1 outranks T2 in the envelope. T3 `resolution_batch`: ten or more new resolutions. T4 `integrity`: verify, reconcile, manifest, signature or a control failed; a push to the user, never a session. T5 `weekly_research`: seven days since the last Tier-2 session, a `backlog.md` item whose machine-checkable condition is met (the backlog is seeded from the deferred list), and envelope headroom. T6 `human`: `state/inbox/user-*.md`. Budget-blocked triggers go to `declined.jsonl`.

**Tier 1 check-in** (T1, T2, T3, T6; caps 60k tokens, USD 0.50, 25 tool calls, 10 minutes). Read-order: `cat state/STATUS.md`; MANDEL.md sections 2 and 6 (a signed MANDEL.md edit makes the rest of its read-order an operations setting); the playbook section per fired trigger; the objects the triggers name. Denied by the settings file, not by instruction: SYNTHESIS.md, `knowledge/`, engine source, `git log`, `logs/opportunities.jsonl`, protected paths, `--actor human`. Permitted: candidate insights with `proposal:` or `child:` provenance, status changes an accepted proposal names, guidance, drafting, `backlog.md`. Stops: triggers handled, `--max-turns`, or two consecutive errors; always last, `cycle-finish` and commit.

**Tier 2 research** (T5; caps 300k tokens, USD 3, 60 tool calls, 60 minutes). Reads the card, the research playbook, the backlog item, MANDEL.md sections 2 and 6, and the files the item names. Produces exactly one of: a pre-registered proposal; an evaluator with tests; one knowledge file distilled; first contact with one child. Tier 2 pauses after four weeks without an accepted non-code proposal until a human line.

**Monthly, by code.** `budget.derive` may lower a tier's cap to 1.5 times its median metered cost; raising a cap, and the absolute monthly USD ceiling (seed 40), need a signed human event. **Quarterly, by code:** every accepted proposal gets a superseding re-validation proposal on the trailing 90 days with its frozen criteria and a new `holdout_id`; two consecutive failures roll it back, retire the insights no other accepted proposal names, and retire its region.

**A worked cycle.** Day 38: `daily` finds P-B at `min_n`, builds evidence from the ledgered selectors, rejects it (skill -0.06, `skill_ci_low` -0.12, null band -0.09 to +0.08) and resolves the idea-market forecast; T1 fires and the check-in records one `fact` insight, guides the child with the verdict and the null band, and commits in about eight tool calls, under 30k tokens.

## Validation

The gate is used unchanged: `evaluate` applies frozen criteria and checks the out-of-sample flag, the trial count and finite numbers. What changes is where evidence comes from and what guards the path.

| Kind of change | Criteria set | Evidence builder | Extra guards |
|---|---|---|---|
| Forecaster (child, model, pool) | `forecast_improvement_criteria(min_n)`: `n_eff >= min_n`, `brier_delta < 0`, `skill_vs_market > 0`, `skill_ci_low > 0` (cluster bootstrap by resolution day or declared event key, level divided by the trial count), `outside_null == 1` (skill above the shuffle-null band) | `evidence_from_forecasts`: candidate, one reference platform, bucket, `since` and `min_n` from the ledgered pre-registration; latest forecast within the bucket for candidate and incumbent alike | `control:coin` and the timestamp audit clean that week; `beats_recal == 1` once `model:recal-v1` exists; one open proposal per source |
| Strategy (`ArbConfig`, `ExecutionConfig`, matcher threshold) | `strategy_improvement_criteria(max_p=0.05, min_dsr=0.95)` | `replay.py`: every logged candidate row re-evaluated under candidate and incumbent config at the declared, hashed fee model; per-day net-edge series into `compare_strategies`; decidable at 20 days with at least one candidate row; 2x friction reported and required for incubation | permutation null within walk-forward blocks (beating it beyond chance is a reject); boundary flag adds `n_holdout_windows >= 2`; acceptance leads to incubation, not live |
| Code and evaluators outside the ruler | `code_change_criteria`: `tests_pass == 1` | `--run-tests` in the daily job | protected paths refused at `draft`; outside the efficiency headline |
| Process (playbook, read-order, caps) | metered cost criteria plus `perm_p <= 0.05` | `cycles.jsonl` rows with `metered=true`, paired on a frozen fixture copy under `MANDEL_DATA_ROOT` | tests cost, not decision quality |
| Ruler, MANDEL.md, this file, live settings | none in the gate | human review with the evidence | signed `actor="human"` event |

**Harness-counted trials.** `replay.py` appends `harness.trial {proposal_id, config_hash, holdout_id}` for every configuration it evaluates. `evidence_from_replay` sets `n_trials` to the trials on the same target and holdout since the last decided proposal on that target, and `check_integrity` fails when `n_trials_declared` is lower. For forecasters, `n_trials` is one plus the length of the `supersedes` chain, and `preregister` refuses a second open proposal on the same source. Residual limit: a read of the opportunity log outside the headless runner is uncounted.

**Controls.** `control:coin` (mid plus N(0, 0.03)) travels the child path (inbox file one day, ingestion the next) and must sit inside the shuffle-null band every week. `control:oracle` (the mid moved 0.10 toward the outcome, in a separate test book) must show skill within 30 questions. The timestamp audit flags a source whose forecasts follow price moves toward the outcome more often than the coin's do. The shuffle null permutes labels within category x month cells of at least 8 questions, falling back to category-only, then month-only blocks, capped at 500, count printed. A control or audit failure is T4.

**Few resolutions.** `min_n` is frozen at pre-registration as the larger of 30 and the n at which a skill of 0.05 is detectable at power 0.8 under the bucket's current null variance; `n_eff` is the number of resolution-day clusters; the card prints, per source and bucket, the minimum detectable skill at current n and the ETA to `min_n`. The first forecaster proposals are expected to reject; the power line says whether that means no edge or not yet testable.

## Children

**Registration.** First contact follows MANDEL.md section 5 as a Tier-2 session, one child per session. Every quantitative claim in the first report that the forecast book can compute (skill, Brier, coverage) becomes a child-claim question ("the re-measured value is at least 0.9 times the claimed value") resolved by the daily job; other claims stay candidate insights with `tier`, `independence` and `incentive` tags. The child is asked the twelve open questions from SYNTHESIS.

**Reporting.** A child, or the user for it, pushes `state/inbox/<child>-<YYYYMMDD>-<seq>.md` to branch `inbox/<child>` in a fixed template (`child:`, `summary:`, `learnings:`, `metrics:`, `questions:`, `tier:`, `independence:`, `incentive:`, `forecasts:` rows `question_id | question | p | horizon_bucket | evidence_cutoff_ts`). `daily.py` parses it into `record_report` and `ForecastBook.record`; a parse failure moves the file to `inbox/failed/` and ledgers `inbox.failed {file_hash}`. Ingested forecasts take the ingestion timestamp, the conservative direction.

**Evaluation jobs.** Mandel writes `EvalJob` rows to `state/children/<name>/jobs.jsonl`: `{job_id, proposal_id, harness_hash, holdout_id, seed, deadline}`. The Linode runs `job-run <job_id>` inside the daily job; that result hash is the evidence, written by `record_evidence` once. A child may run the same job from its checkout; its hash is parked in `jobs.jsonl` and moves only its `evaluator_agreement`, because two untrusted runners agreeing proves determinism, not honesty. No child evaluates a variant of its own work.

**Guidance and scoreboard.** `child-guide` carries validated insights, failure modes, the child's scoreboard row with null band and power line, and measurement requests. Every child is a source in the same book as `market:*`, `control:coin`, `model:recal-v1` and `mandel:self`, scored per horizon bucket on `n`, `n_eff`, Brier, log loss, ECE, `skill_vs_market` with its reference platform and interval, coverage, void rate, the null band, and its nearest non-market source (mean |p − p'| and residual correlation) from the first shared question.

**Graduation** takes three gated steps. First, the child's forecasts pass the forecaster set in a week when the controls are clean and its nearest non-market source is farther than the bucket's null band (copies cannot graduate). Second, its method is frozen into a genome directory `mandel/genomes/<name>-v1/` that `model-run` executes by cron under `model:<name>-v1`; v1 genomes are declarative (recalibration maps, parameter files, abstention rule); a genome that needs a model call carries a Tier-0 token line and an availability check and is marked stale, not skipped, when it fails; a genome that needs the child's code runs under a separate user without `/etc/mandel.env` and needs a signed human event. It must beat `model:recal-v1` on the next `min_n` resolutions. Third, a dry-run strategy proposal with its probabilities as fair value, judged by the strategy set, then incubation; the user holds the live switch.

## Scale structure

Where the fractal idea is structural: the tier cascade (observation daily, a bounded check when triggered, an expensive act weekly) with each tier's cap derived from metered cost at that tier, never copied from the tier above (src:16: renormalised copies share shape, not parameters); and the region catalogue, where the gate's knowledge of the bot's settings (`min_edge`, `min_spread`, `taker_fee_bps`, `slippage_tolerance`, `min_match_similarity`) is stored as accepted regions with a boundary of rejects on a grid fixed per target by human actor, so the step cannot be chosen after the fact, and a candidate one step from a known failure must survive an extra window because a sharp peak is the signature of an overfit setting. Dropped and labelled so: z^2 + c as a market model, self-similar knowledge trees, sign tests over ten decisions, fixed budget ratios, exponents without a null. The proposer is versioned and its hit rate reported; it is not gated until it can be.

## Frugality

`tokens` = uncached input plus cache creation plus output as metered by the CLI; `cache_read_tokens` recorded, not capped; rows without CLI usage carry `metered=false` and an estimate. Token and USD caps are measured after the fact; only turns and wall-clock are enforced on a running session.

| Tier | Cadence | Token cap | USD cap | Tool or API cap | Wall cap |
|---|---|---|---|---|---|
| 0 daily job | every day | 0 (plus any genome's metered line) | 0 | 120 batched API calls | 300 s, reported |
| 1 check-in | on T1, T2, T3, T6 | 60k | 0.50 | 25 tool calls | 10 min |
| 2 research | at most weekly, on T5 | 300k | 3.00 | 60 tool calls | 60 min |
| weekly envelope | | 800k | 8.00 | | |

This table is the seed; the card prints the live caps from `budget.json` (ISO weeks). A month costs at most about USD 35, under an absolute monthly ceiling the user sets (seed 40). The card carries the efficiency numbers: tokens and USD per accepted non-code proposal over the trailing four weeks, per criteria set; the share of zero-token days (target at least 60%); declined triggers; the daily job's `wall_seconds` and its slope. STATUS.md is the hot cache, regenerated and never edited; `ingest` and `graph` run only when `knowledge/` changes. Every evaluator is CPU-only and runs inside the daily job; genomes are the metered exception. Not built: multi-agent panels, a daily proposing generation, Mandel forecasting market questions itself, any LLM judge, vector store or live-money change.

## Risks and their mitigations

- **Resolutions arrive slower than planned**, and `min_n` may exceed 30. Power and ETA lines make the wait visible.
- **The daily job rots or slows.** T4 pushes a failing run to the user; the job has tests against recorded fixtures; a question index and one batch event a day keep it near linear.
- **A leak or a copied source looks skilled.** The timestamp audit and the nearest-source line are the detectors; the coin and the oracle check the path; horizon-bucketed scoring removes the forecast-before-close route.
- **Frugality starves learning, or the budget ratchets.** `declined.jsonl` records every refused trigger; derivation can only lower caps; raises and the ceiling are human; Tier 2 pauses after four empty weeks.
- **The ruler is edited by mistake or on purpose.** The manifest fails `verify`, `evaluate` refuses, an unsigned human event fails `verify`; the fix is a signed event or a `manifest.migrated`. Detectable, not prevented.

## Roadmap

**Build weeks 1 and 2** are user-run build sessions outside the tiers, cost recorded but not capped; the tiers start in week 3. Week 1: `protected.py` with the manifest and signing; `questions.py` and the client fix for `Market.resolution`; `daily.py` with batched fetches, builders, `decide`, triggers and STATUS; `PLAYBOOK.md`; `session.sh` with the deny-list and the timer change; the idea-market check in `preregister`; the signed MANDEL.md read-order edit. Week 2: `evidence_from_forecasts` and the forecaster criteria; the gross/net opportunity line and `replay.py`; `controls.py`; the inbox template and branch flow; the bot in dry run on the Linode; `regions.py` with its fixed grids. Pre-register P-A and P-C.

**Week 3** (check-ins only when triggered): first resolutions; market sources and `control:coin` on the scoreboard. If a child arrives: first contact, child-claim questions, `jobs.py`, P-B pre-registered against it. **Week 4**: P-A decided; first monthly cap derivation; the card's four-week efficiency line is the progress report.

- **P-A, process.** STATUS-first read-order halves the metered cost of a check-in. Baseline: five Tier-1 sessions under the synthesis-first order, each against a copy of a frozen fixture under `MANDEL_DATA_ROOT`, caps not enforced during measurement; treatment: five sessions under the playbook order on the same fixture. Criteria: `tokens_per_checkin_ratio < 0.5`, `triggers_handled_ratio >= 1.0` where handled means the session's ledger events match the fixture's expected set, `perm_p <= 0.05` over the 252 relabelings; `n_trials_declared = 1`. P-A tests cost, not decision quality. The baseline costs about 300k tokens once.
- **P-B, forecaster.** The first registered child (failing one, `model:recal-v1`) beats `market:polymarket` over its first `min_n` post-registration resolutions in its declared horizon bucket under the forecaster set. Expected verdict: reject.
- **P-C, strategy.** `ArbConfig.min_edge = 0.015` beats 0.01 on every replayed candidate row at the declared fee model over 20 days with at least one candidate; `strategy_improvement_criteria()` with `n_trials_declared = 3` (0.012, 0.015, 0.02), and the harness count must agree. 2x friction reported. Acceptance leads to incubation, not a config change.

**The next quarter.** Month 2: `model:recal-v1` pooled fit on the first 30 resolutions, running by cron; incubation of any accepted strategy proposal; counters on insights after the tenth decided proposal. Month 3: the first quarterly re-validation proposals; the first genome directory if any forecaster has graduated; a review of this document against its predictions and a v2 proposal for human review. The archive and parent sampling from proposal 2 wait for twenty decisions and one stepping stone.

## Falsifiable predictions

1. Within two weeks of the tiers starting, at least 60% of days spend zero model tokens and fewer than 20% of metered check-ins hit the 60k cap or `--max-turns`. Wrong if more do: the card is not sufficient context.
2. Within four weeks, at least 40 questions a week are sampled, at least 15 have resolved and the void rate is under 20%. Wrong if resolutions are under 10 or voids above 30% at day 28.
3. `control:coin` stays inside the shuffle-null band every week, the timestamp audit flags no sampled market source, and `control:oracle` shows skill within its first 30 test-book questions. A breach means a leak; forecaster scores are suspended until it is found.
4. P-A passes with a ratio below 0.5 and `perm_p <= 0.05`. Wrong if not: the playbook is revised, not the cap.
5. No forecaster passes `skill_ci_low > 0` in the first eight weeks, and the power line shows a minimum detectable skill above 0.05 for every source at week 8. If one passes, the timestamp audit and nearest-source check come first.
6. The harness-counted `n_trials` exceeds the declared count on at least one of the first ten strategy proposals. If it never does over twenty, harness counting may be sampled.
7. T1 fires at least twice in the first six weeks with nothing declined for budget. If it fires less, resolution rate was the binding constraint. If the backlog passes five items while triggers are declined, the user is asked to raise the caps.
8. The daily job's `wall_seconds` grows by less than 1 s per 1,000 forecasts over the first quarter. Wrong if steeper: the job is re-profiled before the cap is touched.

Each prediction is checked by code from the ledger and `cycles.jsonl` and filed as an insight; this document is revised through a proposal decided by human review.

## Red-team log

Numbers are the review's (2026-10-14). Every finding changed the design unless marked *accepted*, where the limitation is stated in the text and left.

- *Gaming.* 1 `skill_ci_low > 0`, `outside_null == 1`. 2 one open proposal per source; chain counted. 3 the daily job decides; `proposal.stale`; T1 interprets. 4 selectors from the pre-registration; one platform; bucket on the incumbent. 5 all bundles logged; verdict at declared friction, 2x for incubation; 20 active days. 6 signed human events; deny-list; *accepted*: detectable, not prevented. 7 trials since the last decision; replay refuses unregistered runs; *accepted*: reads outside the runner. 8 Linode hash is the evidence. 9 forecast bound to the criteria hash; class = criteria set. 10 efficiency per set; `code` excluded. 11 nearest-source line; graduation rule. 12 superseding re-validation; two failures; insights and region retired. 13 coin via inbox; oracle = mid moved 0.10; timestamp audit. 14 cell minimum 8; permutation count. 15 `min_n` from power; power line. 16 resolution-day clusters. 17 handled by ledger events; `perm_p`; fixture copy; cost test only. 18 `question.voided`, `inbox.failed`, filename sequence, void rate.
- *Resources.* 19 one `forecast.batch` a day; question index; permutation cap; `wall_seconds`; wall cap not T4. 20 batched fetches; call arithmetic. 21 derivation only lowers; human raises and ceiling; Tier 2 pause. 22 T2 batched; T1 outranks. 23 `inbox/<child>` branches; one writer. 24 `manifest.migrated`; scoped check. 25 seeded backlog; T5 condition. 26 live caps on the card.
- *Overclaims.* 27 deny-list, `--max-turns`; *accepted*: token and USD caps after the fact. 28 genome token line, availability check, stale not skipped. 29 declarative genomes; code genomes isolated and signed. 30 pooled recal; pipeline test. 31 prediction 1 reworded.
- *Contradictions.* 32 Tier 1 reads MANDEL.md 2 and 6; signed read-order edit; P-A on fixtures. 33 both files in the human-review row. 34 no waiting state. 35 `tier`, `independence`, `incentive` fields; sole-support rule deferred. 36 the daily job runs the builders.
- *Buildability.* 37 Polymarket rule specified; client extended. 38 category table; one id per platform market; pairs separate. 39 build weeks outside the tiers; P-A about 300k. 40 book-computable child claims only. 41 `proposer_version`, bucket anchor, `horizon_bucket:`, `controls_ok`, truncation rule, ISO weeks. 42 grids fixed by human actor.
