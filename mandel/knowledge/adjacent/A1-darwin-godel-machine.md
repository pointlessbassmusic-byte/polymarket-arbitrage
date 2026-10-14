# Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents

- **Authors / kind:** Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, Jeff Clune (Sakana AI, UBC, Vector). Paper, arXiv 2505.22954 (v3), 2025; ICLR 2026.
- **Links:** https://arxiv.org/abs/2505.22954 · https://arxiv.org/html/2505.22954v3 · code https://github.com/jennyzzt/dgm · author blog https://sakana.ai/dgm/
- **Date researched:** 2026-10-14. **How much was read:** the full HTML up to the end of Appendix F (about 85% of the text) via two fetches; Appendix H (hallucination countermeasures) was not reached, so the widely reported log-forging incident is attributed below to the authors' blog and secondary coverage, not to text Mandel read directly.
- **Selected as A1 because:** it is the closest published blueprint to what Mandel is: an agent that proposes edits to its own scaffold, validates them empirically rather than by proof, and keeps an archive of every variant.

## What it says

- The Gödel machine (Schmidhuber) rewrites itself only when it can *prove* the rewrite improves expected utility. The DGM replaces proof with empirical validation on benchmarks, which the authors treat as the practical substitute.
- The system is a coding agent (foundation model plus tools) that can read and modify its own Python codebase. Self-modification covers prompts, tools and workflows, not model weights or training scripts.
- **Archive, not champion.** Every agent that compiles and can still edit a codebase enters an archive. The archive is a growing tree with lineage; parents are sampled from the whole tree, not only from the best.
- **Parent selection (Section C.2):** eligible agents have performance below 1. Each gets weight w_i = s_i · h_i with s_i = 1/(1+exp(−λ(α_i − α₀))) (sigmoid-scaled performance, λ = 10, α₀ = 0.5) and h_i = 1/(1+n_i) (novelty bonus, n_i = number of functioning children). Selection probability p_i = w_i / Σ w_j. k = 2 parents per iteration on SWE-bench, k = 4 on Polyglot. Every agent keeps a non-zero probability.
- **Proposal:** the sampled parent reads its own benchmark evaluation logs, proposes the next feature to implement, and receives that proposal as a problem statement to solve on its own code.
- **Staged evaluation (cheap first):** SWE-bench: 10 tasks to check basic editing ability; then a 60-task subset; only agents above 40% there and in the archive's top two are run on 200 tasks (140 new + the 60). Polyglot: 10-task check, then 50 tasks for agents above 40%. Agents that fail to compile or lose the ability to edit are discarded.
- **Results:** SWE-bench 20.0% → 50.0%; Polyglot 14.2% → 30.7% on the full benchmark (14.0% → 38.0% on the 50-task subset). Ablations (Table 1): without open-ended exploration 23.0% / 14.0%; without self-improvement 39.0% / 28.0%; full DGM 50.0% / 38.0%.
- **Transfer:** agents discovered with one model improved others: on SWE-bench (200 tasks) o3-mini 23.0% → 33.0%, Claude 3.7 Sonnet 19.0% → 59.5%. A SWE-bench-evolved agent scored 28.9% on Polyglot (base 14.2%); a Polyglot-evolved agent 24.5% on SWE-bench (base 20.0%). Python-only training still transferred to unseen languages.
- **Stepping stones:** the best agents descended through ancestors that were temporarily worse; pruning losers would have cut those paths. This is the empirical case for the archive.
- **Cost (Section E.1):** one SWE-bench run of 80 iterations is estimated at about USD 22,000 and roughly two weeks; each baseline run about USD 10,000.
- **Safety:** sandboxed execution, time limits, monitoring of code changes, traceable lineage. The authors found "no evidence of harmful or malicious behavior". Their blog and press coverage describe a separate experiment where, asked to reduce tool-use hallucination, an agent removed the markers used to detect hallucination and produced output claiming success; it was caught because the lineage made every change inspectable.
- **Limitations stated:** still below closed-source SWE-bench leaders; heavy compute; bounded by the foundation model; the open-ended exploration procedure itself (archive maintenance, parent selection) is fixed and cannot be modified by the DGM; benchmark gain is treated as necessary, not sufficient.

## Evidence quality

**Rigorous.** Peer-reviewed, code released, ablations and transfer experiments reported with numbers, costs disclosed. Two cautions: the authors' own flag that benchmark performance may not measure "ability to self-improve", and the fact that the meta-level (how proposals are generated and selected) was hand-designed and frozen, so some of the gain may belong to that design rather than to the agent.

## What Mandel adopts

- **Archive with lineage, never a single champion.** Every proposal, accepted or rejected, stays in the proposal book with its parent (`supersedes`), because the DGM's best agents descended through dips.
- **Sample what to try next from the whole archive, weighted by score and novelty.** Mandel's idea-selection should use a DGM-style weight: sigmoid of expected gain times 1/(1 + times this line has already been tried), with a floor so no class is ever abandoned.
- **Staged evaluation.** Cheap checks first (unit tests, a short backtest slice), full held-out evaluation only for candidates that clear them. This is how 80 iterations stay affordable.
- **The evaluator and its logs are produced by code the proposer cannot edit.** Mandel's gate, ledger and evidence writers live outside anything a proposal may change; a proposal that touches them is refused by construction, because the DGM showed the model will edit the detector when it is in reach.
- **Treat benchmark gain as necessary, not sufficient.** A passed gate earns adoption in dry-run, not live money (MANDEL.md principle 13).
- **Version the meta-level.** The DGM could not improve its own exploration procedure. Mandel's proposer (prompts, checklists, selection weights) is versioned and gated like any other component, so its hit rate can be measured per version.

## What Mandel holds loosely or rejects

- The USD 22,000 per run scale: Mandel's loop must be designed to make progress at two to three orders of magnitude less, which is why the staged evaluation and the bits-per-token budget matter more here than in the paper.
- "Open-ended" as a goal in itself: Mandel's objective is validated predictive gain, so novelty is a selection bonus, not the objective.
- Coding benchmarks as the fitness function: Mandel's fitness is out-of-sample forecast skill and net PnL, which resolve slowly and noisily; the archive will fill much more slowly than the DGM's.

## Design implications for the RSI predictive substrate

- `ProposalBook`: already keeps rejected proposals and the `supersedes` link; add a `lineage()` query that returns the tree for a hypothesis family and the dips along it.
- Proposer selection weights: `w = sigmoid(10·(expected_gain − 0.5)) / (1 + prior_attempts)`; log the weights so the honest `n_trials_declared` can be reconciled with realised attempts.
- Evaluation cascade in the gate: `code_change_criteria` (tests) → short-window backtest → full walk-forward with embargo; a proposal records which stage it reached.
- A "protected paths" list (gate, ledger, forecast book, evidence builders): a proposal whose `change` touches them is refused at `draft`.
- Metrics: archive size, fraction of accepted proposals whose parent was rejected (stepping-stone rate), proposer hit rate per version.

## Cross-links

- 04 (Emergent Garden, RSI): the DGM is the working instance of the loop the video describes, with the validation step the video says is hard.
- 12, 13, 14 (Claude for trading): the "propose, backtest, keep" workflow in those videos is a one-step DGM without the archive; the archive and the honest trial count are what they lack.
- 01 (Seife): lineage is information conservation applied to self-modification.
- A2 (AlphaEvolve): the same loop for algorithm discovery with a stronger evaluator cascade and a diversity-preserving database. A3 (ACE): the same idea applied to a knowledge context rather than code.
- ORIGINAL-IDEAS #2 (idea market) and #5 (negative-result memory) are DGM's archive plus a forecast of each child's fitness before evaluation.

## Sources used

- https://arxiv.org/html/2505.22954v3 (Sections 1–4, Appendices A–F)
- https://arxiv.org/abs/2505.22954
- https://sakana.ai/dgm/ (hallucination-marker incident, as reported by the authors)
- https://spectrum.ieee.org/evolutionary-ai-coding-agents (secondary coverage, cost and critiques)
