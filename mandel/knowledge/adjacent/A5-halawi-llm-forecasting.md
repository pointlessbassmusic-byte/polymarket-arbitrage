# Approaching Human-Level Forecasting with Language Models

- **Authors / kind:** Danny Halawi, Fred Zhang, Chen Yueh-Han, Jacob Steinhardt (UC Berkeley). Paper, arXiv 2402.18563, 2024.
- **Links:** https://arxiv.org/abs/2402.18563 · https://arxiv.org/html/2402.18563
- **Coverage confidence:** 0.65 (fraction of the source actually read and verified, see below).
- **Date researched:** 2026-10-14. **How much was read:** about 60% of the HTML (data, system, main results, calibration, limitations).
- **Selected as A5 because:** it is the closest published version of Mandel's central function, forecasting resolvable questions against a market or crowd, with leakage controls, proper scoring and an honest account of where the system wins and loses.

## What it says

- **Data:** 48,754 questions and 7,174,607 user forecasts (2015–2024) from Metaculus, Good Judgment Open, INFER, Polymarket and Manifold; after curation 5,516 binary questions (3,762 train, 840 validation, 914 test). The test set holds only questions opened after the models' knowledge cut-off (June 1, 2023); questions spanning the cut-off were discarded.
- **Leakage controls:** retrieval dates are placed geometrically between a question's open and close dates, never relative to the resolution date ("would leak information"); retrieval after resolution is excluded; post-training leakage was checked by manual queries about post-cut-off events.
- **System:** an LM writes search queries (query expansion plus sub-question decomposition, unioned); articles come from NewsCatcher and Google News; GPT-3.5 rates relevance from the title and first 250 words (about 70% cost saving); the top k = 15 summaries feed a GPT-4 scratchpad that rephrases the question, argues both sides, weighs them and checks against base rates.
- **Fine-tuning on self-generated reasoning that beat the crowd:** 73,632 reasonings on training questions, 13,253 kept whose predictions beat the crowd (discarding those more than 0.15 from the crowd), targets averaged with the crowd; GPT-4 fine-tuned on the 6,000 most recent for 2 epochs.
- **Ensembling:** three base-model and three fine-tuned samples (temperature 0.5) combined by trimmed mean, the best of five methods on validation.
- **Results (test Brier, lower is better):** crowd .149; system .179; best zero-shot baseline .208; random .250. Ablations: no fine-tuning .186; no fine-tuning and no retrieval .206. The crowd aggregated with the system improves to .146.
- **Selective forecasting (Table 3):** when the crowd is uncertain (0.3–0.7) the system scores .238 against the crowd's .240 (51% of forecasts); with early retrieval .186 vs .162; with at least 5 articles .175 vs .142; all three criteria jointly .240 vs .247 (22% of forecasts, 43% of questions), the one regime where the system beats the crowd significantly.
- **Calibration:** RMS calibration error .42 (system) vs .38 (crowd); zero-shot models were poorly calibrated; the system was underconfident on validation, which the authors attribute to hedging from safety training.
- **Limitations:** underperforms where the crowd is highly confident; standard errors assume i.i.d. data on what is a time series ("likely underestimate the true error"); selective strategies chosen on validation may be optimistic on test; fine-tuning targets include crowd information.

## Evidence quality

**Rating: rigorous.** **Rigorous.** Large curated dataset, explicit leakage controls, proper scoring, honest reporting of the regimes where the system loses. The remaining risks are the ones the authors name: optimistic selective results and underestimated errors from autocorrelation.

## What Mandel adopts

- **The crowd (market) is the benchmark, not accuracy.** Every forecaster on Mandel's scoreboard is measured by Brier against resolution and by skill against the market price at forecast time; already built into the forecast book.
- **Point-in-time retrieval.** Any evidence a forecast uses must carry a timestamp before the forecast; retrieval schedules must not depend on when the question resolved.
- **Selective forecasting as a first-class strategy.** A forecaster may abstain; the scoreboard tracks coverage and skill on the questions it chose. Mandel should expect edge, if any, where the market is uncertain and information is fresh, and no edge where the market is confident.
- **Keep what beats the crowd, with a distance cap.** Training signal comes from forecasts that beat the market by a bounded margin, not from extreme contrarian hits.
- **Ensemble by trimmed mean.** The default pooling rule for the children's forecasts, re-tested against log-opinion pooling as ORIGINAL-IDEAS #5 proposes.

## What Mandel holds loosely or rejects

- Fine-tuning as the route to improvement: Mandel runs on frozen weights; the equivalent is curating the retrieval and reasoning scaffold and the archive of reasonings that beat the market.
- The headline "approaching human level": the system loses to the crowd overall (.179 vs .149) and only wins in a selected regime; Mandel should quote the selective numbers with the coverage they imply.
- i.i.d. standard errors on resolved questions; Mandel's bootstrap must block by time, as the engine already does for returns.

## Design implications for the RSI predictive substrate

- Forecast records gain `evidence_cutoff_ts` and `abstained: bool`; the scoreboard reports coverage alongside skill.
- A per-forecaster "regime table": skill versus market bucketed by market price (0.3–0.7 vs the tails), by question age and by evidence count, so guidance to a child can say where it should and should not forecast.
- A reasoning archive: each forecast stores its rationale; rationales from forecasts that beat the market by less than a cap become retrieval material for later forecasts (the frozen-weights version of the paper's fine-tuning).
- Gate criterion for a forecaster: Brier skill versus market > 0 on at least N resolved questions in the regime it claims, with a time-blocked bootstrap interval excluding zero.
- Metrics: coverage, skill by regime, calibration RMS, fraction of questions where the pooled children beat the market.

## Cross-links

- 11 (Veritasium, Markov): the base-rate step in the scratchpad is Markov's memoryless prior; 02 (Mossbridge): what a forecasting field looks like when selective reporting is not controlled.
- 12, 13, 14 (Claude trading videos): the workflow those videos gesture at, done with leakage controls and proper scoring.
- A4 (MMAR): the market's own roughness sets how fast information decays and therefore how early retrieval must be.
- ORIGINAL-IDEAS #2 (Mandel forecasts its own proposals) and #5 (children's disagreement) are this paper's loop turned inward.

## Sources used

- https://arxiv.org/html/2402.18563 (first ~100k characters)
- https://arxiv.org/abs/2402.18563
