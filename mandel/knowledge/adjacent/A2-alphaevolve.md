# AlphaEvolve: A coding agent for scientific and algorithmic discovery

- **Authors / kind:** Novikov et al., Google DeepMind. White paper, arXiv 2506.13131, 2025.
- **Links:** https://arxiv.org/abs/2506.13131 · https://arxiv.org/html/2506.13131 · https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- **Coverage confidence:** 0.60 (fraction of the source actually read and verified, see below).
- **Date researched:** 2026-10-14. **How much was read:** roughly the first 60% of the HTML (system description, results, limitations); the mathematical appendices were not read.
- **Selected as A2 because:** it states the precondition Mandel must respect (a machine-gradable evaluator), and it shows how to keep an evolutionary search affordable (cascade) and diverse (program database).

## What it says

- An evolutionary coding loop with four parts: a **program database** (programs plus their evaluation results), a **prompt sampler** that builds prompts from database programs (explicit context, stochastic formatting, rendered evaluation results, meta-prompts), an **LLM ensemble** (Gemini 2.0 Flash for throughput, Gemini 2.0 Pro for occasional higher-quality suggestions) that emits code diffs, and **evaluators** that run the user's `evaluate` function. A controller runs samplers and evaluators asynchronously.
- **EVOLVE-BLOCK markers.** Users wrap the code that may change in `# EVOLVE-BLOCK-START` / `# EVOLVE-BLOCK-END`. Everything else is a fixed skeleton that calls the evolved pieces from `evaluate`. The initial block must be complete, even if rudimentary.
- **Evaluation cascade.** Candidates are tested at small scale first to filter faulty programs and advance to harder stages only if they do well enough at every earlier stage.
- **Multiple metrics.** Several user-provided scores can be optimised at once; the authors argue this often helps even when only one matters. Properties hard to encode (simplicity) can be scored by separate LLM calls.
- **Diversity.** The database is "inspired by a combination of the MAP elites algorithm" and island-based population models; it keeps diverse good solutions rather than one champion.
- **Results:** a rank-48 algorithm for 4×4 complex matrix multiplication, "the first improvement, after 56 years, over Strassen's algorithm in this setting", plus state-of-the-art for 14 matrix multiplication targets; kissing number in 11 dimensions raised from 592 to 593; a data-centre scheduling heuristic that "continuously recovers on average 0.7% of Google's fleet-wide compute resources"; an average 23% kernel speedup and a 1% reduction in Gemini's overall training time; FlashAttention kernel 32% faster, pre/post-processing 15%; on over 50 open mathematical problems it matched the best known construction on about 75% and surpassed it on about 20%.
- **Precondition and limits:** "The main limitation of AlphaEvolve is that it handles problems for which it is possible to devise an automated evaluator." Natural sciences with only partly simulable experiments are harder. LLM-graded evaluation is "not a setting we have optimized for". Improving AlphaEvolve's own infrastructure had feedback loops "on the order of months" with "moderate" gains.

## Evidence quality

**Rating: mainstream-educational.** **Rigorous** for the discoveries (several results are independently checkable constructions), **mainstream-educational** for the system description, which is a white paper without ablations or costs. The loop's dependence on Google-scale compute is undisclosed.

## What Mandel adopts

- **Evaluator first.** Nothing enters Mandel's improvement loop until it has an automatic scorer: for strategies the walk-forward comparison, for forecasters the forecast book's Brier and skill, for code the test suite. Components without a scorer are documented as not yet improvable.
- **Evolve-blocks.** Each improvable component (edge estimator, sizing rule, fee model, calibration layer, the children's prompts) gets an explicit boundary; proposals may change only what is inside it. The skeleton, the gate and the evidence writers stay outside.
- **Cascade.** Unit tests → short backtest slice → full held-out evaluation; most failures die cheaply. This is the operational form of principle 6 (information has a cost).
- **Several metrics at once.** Record Brier, log loss, calibration error and net PnL together; a proposal that improves one by wrecking another is visible.
- **Diversity in the archive.** Keep the best variant per niche (per market category, per horizon) rather than one global best, which is MAP-Elites applied to strategies.

## What Mandel holds loosely or rejects

- The scale of search: AlphaEvolve samples thousands of programs; Mandel's budget allows tens of proposals per cycle, so the cascade must reject most candidates at the first stage.
- LLM-graded evaluators for anything that feeds the gate: the paper itself did not optimise for them, and the DGM (A1) showed what happens when the judged party can touch the judge.
- Months-long self-improvement loops: Mandel's cycle must close in days, with the forecast book providing resolutions continuously.

## Design implications for the RSI predictive substrate

- A `scorers.py` registry: each improvable component maps to a scorer and a cascade; `draft` refuses a proposal whose target has no scorer.
- Evolve-block markers in the repo's strategy code (`core/arb_engine.py` edge calculation, sizing, fee model) so a child's proposals are scoped automatically.
- Niche keys for the archive: `(platform, category, horizon)`; `ProposalBook.query` by niche; the signal map can colour accepted proposals by niche.
- Metrics: stage-1 rejection rate (should be high and cheap), cost per accepted proposal by stage, number of niches with an accepted variant.

## Cross-links

- 04 (RSI): the loop with the validation step made explicit; 13 (Claude Code as a quant): the hypothesis → backtest workflow is a one-block AlphaEvolve without a database.
- 05, 07 (neural networks): gradient descent is also a loop of propose-evaluate-keep; AlphaEvolve replaces the gradient with an LLM and the loss with any evaluator.
- A1 (DGM): same family; DGM evolves the agent, AlphaEvolve the solution. A3 (ACE): the same incremental, non-collapsing update applied to a knowledge context.
- ORIGINAL-IDEAS #4 (bits per token): the cascade is how that budget is spent.

## Sources used

- https://arxiv.org/html/2506.13131 (first ~100k characters)
- https://arxiv.org/abs/2506.13131
- https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
