# Theories and their trial math

Rendered from `registry.json` (hash `56f081ba23619bc7`). 45 theories. supported 7, not_supported 3, inconclusive 1, untested 3, blocked 23, parked 8.

A theory is one falsifiable statement. Its status moves only through a recorded experiment result or a ledgered park/unpark event. Parked theories are kept in full so they can be picked up without re-deriving them.

## Supported (7)

### T-01 · market-prices-beat-the-coin

**Claim.** Polymarket prices observed 1, 3, 7, 30 and 90 days before close predict resolution better than p=0.5 at every horizon.

- kind: market-structure · origin: adj:A5, src:11, src:12, engine
- statistic: Brier skill vs coin = 1 - Brier(market)/0.25 per horizon
- null: coin forecaster, Brier 0.25
- procedure: resolve closed markets from Gamma; take CLOB daily price at each horizon before close; score
- data: polymarket-closed-markets, polymarket-price-history-daily · min n: 300
- pass: skill > 0 at every horizon
- controls: only UMA-resolved binary markets; point-in-time join on available_at <= decision time; no look-ahead; one price per market per horizon
- harness: market_calibration
- result X-2a13dc3b: supported — market price beats the coin at every horizon (min skill 0.70)

### T-06 · price-series-are-multifractal

**Claim.** Daily logit-price series of Polymarket markets show concave tau(q) (multifractal scaling) beyond a shuffled-increments null in more than 25% of series.

- kind: scaling · origin: adj:A4, src:14, src:16, mandel:idea-3
- statistic: concavity of tau(q), q in {0.5..4}; share of series above the null's 95th percentile
- null: shuffled increments (same marginal, no clustering)
- procedure: partition function over dt; fit tau(q); compare with 200 shuffles per series
- data: polymarket-price-history-daily, 40 longest series · min n: 40
- pass: > 25% of series beyond null (chance 5%)
- controls: series >= 60 points; logit transform; shuffles keep the marginal
- harness: multifractal_scaling
- result X-2fb589be: supported — 30% of 40 daily logit-price series show concavity beyond the shuffled null (threshold 25%; chance ~5%)

### T-07 · prices-are-anti-persistent

**Claim.** Polymarket daily price increments are anti-persistent (Hurst H < 0.5) in a majority of markets, outside the shuffle null.

- kind: scaling · origin: src:14, adj:A4, src:08
- statistic: DFA Hurst exponent with shuffle interval; share of series outside their null
- null: H ~ 0.5 (shuffled increments)
- procedure: DFA per series; 200 shuffles for the interval
- data: polymarket-price-history-daily · min n: 40
- pass: > 25% of series outside the null
- controls: constant segments skipped; bounded prices induce mean reversion mechanically near 0/1
- harness: hurst_ci
- result X-485f95d2: supported — median H 0.35; 12/40 series outside their shuffle null (threshold 25%)
- note: a bounded price is mean-reverting by construction near the edges; the verdict says structure exists, not that it is tradable

### T-10 · simple-rule-search-overfits

**Claim.** Searching 21 momentum/mean-reversion rules on Polymarket prices yields an in-sample winner that does not survive deflation (DSR < 0.95, PBO > 0.5).

- kind: strategy · origin: src:13, adj:A4, engine
- statistic: deflated Sharpe of the best rule; probability of backtest overfitting (CSCV)
- null: zero-skill best-of-N
- procedure: declare the 21 rules; compute Sharpe per rule; DSR with n_trials=21; CSCV PBO
- data: polymarket-price-history-daily, 150 longest series · min n: 100
- pass: DSR < 0.95 and PBO > 0.5
- controls: rule set frozen; transaction costs not yet included (would only strengthen)
- harness: dsr_pbo_harness
- result X-cd5674d2: supported — best of 21 momentum rules: Sharpe -0.031, DSR 0.00, PBO 0.90

### T-11 · scoring-path-controls-hold

**Claim.** The forecast scoring path is intact: coin scores Brier 0.25, oracle 0, and the market beats the coin on the same questions.

- kind: engine · origin: engine
- statistic: Brier of coin, oracle, market
- null: n/a (sanity control)
- procedure: write control forecasts for resolved markets; score
- data: polymarket-closed-markets, polymarket-price-history-daily · min n: 30
- pass: coin = 0.25, oracle = 0, market < coin
- controls: same questions for all three
- harness: controls
- result X-aa7f417a: supported — coin 0.25, oracle 0.0, market 0.024331208750000007: scoring path intact

### T-13 · skill-rises-toward-resolution

**Claim.** Market skill vs coin increases monotonically as the horizon shortens (90d -> 1d).

- kind: market-structure · origin: adj:A5, src:01
- statistic: skill per horizon from market_calibration
- null: flat skill across horizons
- procedure: read the per-horizon table
- data: same as T-01 · min n: 300
- pass: skill(1d) > skill(7d) > skill(30d) > skill(90d)
- controls: survivorship: only markets alive at each horizon
- harness: horizon_monotone
- result X-b7b7c690: supported — skill by horizon 1d 0.858, 3d 0.855, 7d 0.778, 30d 0.719, 90d 0.701 (non-increasing)
- note: automated as harness horizon_monotone (1-point tolerance). Reading 2026-10-14: skill 0.70 (90d), 0.72 (30d), 0.78 (7d), 0.86 (3d), 0.86 (1d): monotone as claimed; the 1d/3d tie is within noise.

### T-36 · tuned-indicator-bot-fails-out-of-sample

**Claim.** An indicator bot tuned on backtests has negative out-of-sample Sharpe on Polymarket prices.

- kind: strategy · origin: src:13
- statistic: out-of-sample Sharpe of the in-sample best rule
- null: Sharpe 0
- procedure: same declared search as T-10; the best in-sample rule's holdout Sharpe
- data: same as T-10 · min n: 100
- pass: holdout Sharpe <= 0
- controls: same split for all rules
- harness: dsr_pbo_harness
- result X-cd5674d2: supported — best of 21 momentum rules: Sharpe -0.031, DSR 0.00, PBO 0.90
- note: the dsr_pbo verdict (overfit) is the same statement from the other side

## Not Supported (3)

### T-02 · longshot-bias

**Claim.** Low-probability YES contracts (price < 0.10) resolve YES less often than their price implies (mean outcome - price < 0 in that bucket).

- kind: market-structure · origin: src:11, adj:A5
- statistic: mean(outcome - price) in the <0.10 bucket with bootstrap 95% interval
- null: zero mean error (calibrated)
- procedure: calibration table by price bucket from market_calibration's statistic
- data: same as T-01 · min n: 300
- pass: upper interval bound < 0
- controls: bucket chosen before looking; horizon fixed at 7d
- harness: longshot_bias
- result X-59df1d8a: not_supported — <0.1 bucket at 7d: mean(outcome-price) +0.0184, 95% [+0.0022, +0.0388], 8 YES events of 284
- note: sub-claim read from the market_calibration calibration table; automated as harness longshot_bias (7d, <0.10, bootstrap interval). Reading 2026-10-14: the <0.10 bucket (mean price 0.008-0.014) resolves YES at 0.010 (1d), 0.007 (3d), 0.028 (7d), 0.020 (30d), 0.019 (90d): at 7d+ slightly MORE often than priced, the reverse of the classic longshot bias, on 5-8 YES events per horizon. A lead, not a finding.

### T-04 · yes-no-bundle-arbitrage-exists

**Claim.** Live Polymarket order books contain YES+NO bundles priced below 1 - fees often enough to execute (>= 1 per 100 markets per snapshot).

- kind: market-structure · origin: repo:arbitrage-bot, src:13
- statistic: count and depth-weighted size of after-fee bundle mispricings per snapshot
- null: zero after-fee mispricings
- procedure: pull /book for YES and NO tokens of active markets; best-ask YES + best-ask NO + taker fee + gas < 1
- data: polymarket-books-snapshot (repeated) · min n: 200
- pass: >= 1 mispricing per 100 markets, persisting across >= 2 snapshots
- controls: fees 150 bps taker, gas estimate, min depth 5 USD; snapshots are a sample of time
- harness: bundle_arb_scan
- result X-8ca82b68: not_supported — 0 after-fee bundle mispricings in 268 markets (one snapshot)
- note: one snapshot so far; the claim needs repeated snapshots (half-life) before parking

### T-19 · point-in-time-changes-a-verdict

**Claim.** Reconstructing inputs as of decision time (available_at) changes at least one backtest verdict relative to the naive join.

- kind: engine · origin: mandel:idea-1, src:13, adj:A5
- statistic: number of verdicts that differ between naive and point-in-time runs
- null: no difference
- procedure: run each harness twice: naive and PIT
- data: any bitemporal bundle (social, history) · min n: 1
- pass: >= 1 verdict differs
- controls: same seeds
- harness: point_in_time_check
- result X-95aa94c7: not_supported — naive not_supported (d_fear +0.0003) vs point-in-time not_supported (d_fear +0.0001): no change on this harness
- note: harness point_in_time_check runs the Fear & Greed test naive (lag 0) and honest (lag 1) and asks whether the verdict or sign changes; one harness only so far

## Inconclusive (1)

### T-38 · retail-attention-predicts-abs-return

**Claim.** Retail attention (standardised mention count per ticker-day on Reddit and StockTwits) rank-correlates positively with the next day's absolute return.

- kind: social · origin: social:reddit, social:stocktwits
- statistic: Spearman rho over ticker-days
- null: mentions permuted within ticker
- procedure: derive mentions daily; join next-day |return|; permutation test
- data: social-derived-*, social-prices-* · min n: 30
- pass: rho > 0 with p < 0.05 over >= 30 capture days
- controls: point-in-time join on available_at <= decision time; no look-ahead; mentions standardised within ticker
- harness: social_attention
- result X-95f1d3d2: inconclusive — 1/30 collection days, 2 usable ticker-days
- note: runs daily; inconclusive until 30 capture days

## Untested (3)

### T-12 · volume-improves-calibration

**Claim.** Higher-volume markets are better calibrated: Brier skill rises monotonically across volume quartiles.

- kind: market-structure · origin: src:11, adj:A5
- statistic: Brier skill per volume quartile at the 7d horizon
- null: skill equal across quartiles
- procedure: quartile by Gamma volume; score 7d-before-close prices
- data: same as T-01 · min n: 400
- pass: monotone increase, top-bottom gap interval excludes 0
- controls: volume is end-of-life volume (not point in time) - a known leak to fix before trusting
- note: harness not yet written: calibration_by_volume

### T-31 · small-mlp-beats-logit-on-market-features

**Claim.** A small MLP on (price, log volume, days to close) predicts resolution with lower walk-forward log loss than logistic regression.

- kind: learning · origin: src:05, src:07
- statistic: walk-forward log-loss difference
- null: equal (nonlinearity adds nothing)
- procedure: walk-forward by close date with embargo; same features
- data: same as T-01 · min n: 500
- pass: difference < 0, interval excludes 0
- controls: embargo; volume leak (end-of-life volume) must be fixed first
- note: harness not yet written: logit_vs_mlp_walkforward (numpy only)

### T-32 · cross-market-prices-are-low-rank

**Claim.** Daily price changes across concurrent Polymarket markets are low rank: the effective rank of their correlation matrix is below 10% of the number of markets.

- kind: scaling · origin: src:08, src:10, src:11
- statistic: effective rank (entropy of normalised eigenvalues) of the correlation matrix
- null: random-matrix (Marchenko-Pastur) spectrum
- procedure: align concurrent series; correlation; eigenvalues
- data: polymarket-price-history-daily · min n: 50
- pass: effective rank < 0.1 n and top eigenvalue outside MP bound
- controls: missing-data alignment; markets of the same event are mechanically correlated (exclude same-event pairs)
- note: harness not yet written: low_rank_structure

## Blocked (23)

### T-05 · cross-venue-arbitrage

**Claim.** The same event priced on Polymarket and Kalshi differs by more than combined fees at least weekly.

- kind: market-structure · origin: repo:arbitrage-bot
- statistic: |p_poly - p_kalshi| - fees on matched events
- null: no after-fee divergence
- procedure: match events across venues; compare contemporaneous mid prices
- data: polymarket active + kalshi markets + a matching table · min n: 50
- pass: > 0 after fees on >= 5 matched events per week
- controls: matching errors are the main false positive; manual review of matches
- blocked on: a question-matching table between venues (none yet)

### T-14 · pooled-children-beat-best-child

**Claim.** A trimmed mean of the children's forecasts has lower Brier than the best single child over 100 shared resolved questions.

- kind: forecasting · origin: adj:A5, mandel:idea-5
- statistic: Brier(pool) - Brier(best child); n_effective of the error matrix
- null: best single child
- procedure: children record forecasts on shared questions; resolve; pool by trimmed mean and by log-opinion pool
- data: forecast book · min n: 100
- pass: difference < 0, interval excludes 0
- controls: pooling rule pre-registered; children may be correlated (report effective rank)
- blocked on: registered children recording forecasts (none yet)

### T-15 · llm-forecasts-approach-the-market

**Claim.** A child's probability forecasts, made before market close, have Brier skill vs coin within 0.1 of the market's on the same questions.

- kind: forecasting · origin: adj:A5
- statistic: skill(child) - skill(market)
- null: child at coin level (skill 0)
- procedure: same questions, same horizon, scored together
- data: forecast book · min n: 100
- pass: skill(child) > 0.5 x skill(market)
- controls: forecast timestamps ledgered before resolution
- blocked on: registered children (none yet)

### T-16 · idea-market-self-forecast-has-skill

**Claim.** Mandel's pre-decision probability that a proposal passes the gate has positive Brier skill against the class base rate over 50 decided proposals.

- kind: engine · origin: mandel:idea-2, adj:A5
- statistic: Brier skill vs class base rate; coverage
- null: base-rate forecaster
- procedure: forecast ledgered before the criteria hash; score on decision
- data: proposals + forecast book · min n: 50
- pass: skill > 0 with coverage not falling
- controls: forecast must precede pre-registration
- blocked on: 50 decided proposals (0 now)

### T-17 · bits-per-token-ranking-is-stable

**Claim.** Insight classes ranked by validated gain per cost keep their order across cycles (rank correlation > 0.5 cycle to cycle).

- kind: engine · origin: mandel:idea-4, adj:A3
- statistic: cycle-to-cycle Spearman of class rankings
- null: rankings independent (rho ~ 0)
- procedure: counters on insights cited by decided proposals; cost from cycle log
- data: cycles + proposals · min n: 3
- pass: rho > 0.5 over >= 3 cycle pairs
- controls: costs are operator estimates
- blocked on: >= 4 cycles with decided proposals

### T-18 · signal-map-counters-predict-outcomes

**Claim.** An insight's helpful/harmful counter ratio predicts whether the next proposal citing it passes, better than the ingest prior.

- kind: engine · origin: mandel:idea-6, adj:A3
- statistic: AUC of counter ratio vs pass/fail, compared with prior confidence
- null: AUC 0.5
- procedure: collect citations; score on decisions
- data: proposals · min n: 50
- pass: AUC(counter) > AUC(prior) and > 0.6
- controls: easy proposals inflate counters
- blocked on: 50 decided proposals

### T-20 · stepping-stones-exist

**Claim.** Some rejected proposals are later cited by accepted proposals (archive stepping-stone rate > 0 over 50 decisions).

- kind: engine · origin: adj:A1
- statistic: share of accepted proposals citing a rejected ancestor
- null: 0
- procedure: lineage from supersedes links
- data: proposals · min n: 50
- pass: > 0.1
- controls: citations must be in the pre-registration
- blocked on: 50 decided proposals

### T-21 · evaluation-cascade-saves-cost

**Claim.** A cheap-first evaluation cascade rejects >= 50% of candidate proposals before the expensive stage with no loss of eventually accepted ones.

- kind: engine · origin: adj:A2
- statistic: cheap-stage rejection rate; false-reject rate on later-accepted candidates
- null: cascade rejects nothing useful
- procedure: run cascade; audit rejections
- data: proposal stream · min n: 40
- pass: >= 50% cheap rejections, 0 false rejects
- controls: audit sample of rejections
- blocked on: a stream of candidate proposals

### T-22 · itemised-context-improves-hit-rate

**Claim.** Proposer hit rate (gate pass rate) is higher with itemised context (ACE counters) than with a flat summary.

- kind: engine · origin: adj:A3
- statistic: pass-rate difference
- null: equal
- procedure: alternate context styles across proposals
- data: proposals · min n: 40
- pass: difference > 0, interval excludes 0
- controls: equal budgets
- blocked on: 40 proposals

### T-23 · self-similar-loop-holds

**Claim.** The same propose-preregister-test-decide loop works at the Mandel, child and strategy levels without level-specific procedure.

- kind: engine · origin: mandel:idea-7, src:16, adj:A1
- statistic: count of level-specific procedural exceptions needed
- null: 0 exceptions
- procedure: run one full cycle at each level; log exceptions
- data: cycle logs · min n: 3
- pass: exceptions <= 1
- controls: budgets derived per level from measured cost
- blocked on: one full cycle at each level

### T-25 · retrieval-scaffold-improves-llm-forecasts

**Claim.** A retrieval + reasoning scaffold improves a child's Brier by >= 0.02 over its unscaffolded forecast on the same questions.

- kind: forecasting · origin: adj:A5
- statistic: paired Brier difference
- null: zero difference
- procedure: each child forecasts both ways on each question; paired test
- data: forecast book · min n: 100
- pass: mean difference >= 0.02, interval excludes 0
- controls: order randomised; both recorded before resolution
- blocked on: registered children

### T-27 · log-loss-and-brier-rank-sources-alike

**Claim.** Ranking sources by log loss and by Brier agree (Spearman > 0.9) so either can be the headline metric.

- kind: forecasting · origin: src:01
- statistic: Spearman between the two rankings
- null: independent rankings
- procedure: scoreboard over all sources
- data: forecast book with >= 5 real sources · min n: 5
- pass: rho > 0.9
- controls: extreme forecasts dominate log loss; clip at 0.01
- blocked on: >= 5 scored sources (3 controls only now)

### T-28 · fractional-kelly-grows-faster

**Claim.** Given a calibrated edge, fractional Kelly (0.25-0.5) sizing has higher terminal log wealth than fixed sizing out of sample.

- kind: strategy · origin: src:01, adj:A4
- statistic: terminal log wealth difference, walk-forward
- null: equal growth
- procedure: size by Kelly fraction of estimated edge vs fixed 1%
- data: resolved markets + a source with positive skill · min n: 200
- pass: difference > 0 in > 80% of bootstrap paths
- controls: edge must be out of sample; costs included
- blocked on: a validated positive-skill source (none yet; market itself is the benchmark)

### T-30 · self-modification-raises-validated-hit-rate

**Claim.** Letting Mandel modify its own proposer/evaluator raises the validated proposal pass rate across cycles.

- kind: engine · origin: src:04, adj:A1
- statistic: pass-rate trend across cycles
- null: flat
- procedure: versioned proposer; compare pass rate per version
- data: cycles + proposals · min n: 3
- pass: positive trend, interval excludes 0
- controls: same gate throughout
- blocked on: >= 3 cycles with proposals

### T-37 · memoryful-agents-beat-stateless

**Claim.** Children with access to the substrate (insights, past verdicts) forecast better than the same children without it.

- kind: forecasting · origin: src:11, src:12, src:06
- statistic: paired Brier difference with/without substrate access
- null: zero difference
- procedure: A/B by question
- data: forecast book · min n: 100
- pass: difference favours substrate, interval excludes 0
- controls: same model, same questions
- blocked on: registered children

### T-39 · lexicon-sentiment-predicts-sign

**Claim.** Mean lexicon sentiment per ticker-day predicts the sign of the next day's return better than chance.

- kind: social · origin: social:reddit, social:stocktwits
- statistic: accuracy of sign(mean_score) vs sign(next return); binomial test
- null: 0.5
- procedure: same join as T-38
- data: social-derived-*, social-prices-* · min n: 30
- pass: accuracy > 0.5, p < 0.05
- controls: ticker-days with |score| > 0.2 only (pre-registered)
- blocked on: >= 30 capture days (1 now); extend social_attention

### T-40 · stocktwits-bullish-ratio-is-contrarian

**Claim.** Extreme StockTwits bullish ratios (> 0.8) precede below-median 5-day returns.

- kind: social · origin: social:stocktwits
- statistic: 5d return after extreme ratio minus median
- null: 0
- procedure: ratio per ticker-day; forward 5d return
- data: social-stocktwits-*, social-prices-* · min n: 30
- pass: difference < 0, block-shift p < 0.05
- controls: min 20 messages per ticker-day
- blocked on: >= 30 capture days

### T-42 · congress-ptr-purchases-beat-spy

**Claim.** Stocks bought in House periodic transaction reports outperform SPY over the 90 days after the filing date.

- kind: flow · origin: social:house-clerk
- statistic: mean 90d excess return of disclosed purchases
- null: 0 (random tickers on the same dates)
- procedure: parse PTR PDFs for tickers and dates; forward returns from filing date
- data: social-house-ptr-*, prices · min n: 100
- pass: excess > 0, permutation p < 0.05
- controls: filing date, not trade date; survivorship of tickers
- blocked on: PDF ticker extraction (recipe: ptr-pdfs/<year>/<DocID>.pdf) and 90 days of forward prices

### T-43 · reddit-mentions-precede-volume

**Claim.** Ticker-days with a mention z-score > 2 on Reddit are followed by above-median volume z-score the next trading day.

- kind: flow · origin: social:reddit
- statistic: share of high-attention days followed by high volume
- null: 0.5
- procedure: mention z within ticker; next-day volume z
- data: social-derived-*, social-prices-* · min n: 30
- pass: > 0.5, binomial p < 0.05
- controls: z-scores need >= 20 days per ticker
- blocked on: >= 30 capture days

### T-44 · coingecko-trending-reverses

**Claim.** Coins on CoinGecko's trending list underperform BTC over the following 7 days.

- kind: flow · origin: social:coingecko
- statistic: mean 7d return vs BTC of trending coins
- null: 0
- procedure: snapshot trending daily; forward prices
- data: social-crypto-* · min n: 30
- pass: < 0, p < 0.05
- controls: survivorship (delisted coins)
- blocked on: >= 30 trending snapshots and per-coin prices

### T-45 · x-sentiment-leads-retail-flow

**Claim.** Cashtag sentiment on X leads StockTwits sentiment by one day (cross-correlation peaks at lag 1).

- kind: social · origin: social:x
- statistic: lagged cross-correlation of daily sentiment
- null: 0 at all lags
- procedure: collect both daily; cross-correlate
- data: social-x-*, social-stocktwits-* · min n: 30
- pass: lag-1 correlation > 0, p < 0.05
- controls: same ticker set
- blocked on: X_BEARER_TOKEN (official API); collection then >= 30 days

### T-46 · social-attention-moves-prediction-markets

**Claim.** Polymarket markets whose topic trends on Reddit move more (|Δprice|) the next day than non-trending markets.

- kind: social · origin: social:reddit, repo:arbitrage-bot
- statistic: |Δprice| trending vs not
- null: equal
- procedure: match post topics to market questions; compare next-day |Δprice|
- data: social-reddit-*, polymarket active prices · min n: 30
- pass: difference > 0, p < 0.05
- controls: topic matching precision audited
- blocked on: topic-to-market matching and >= 30 capture days

### T-47 · cheap-yes-underpriced-at-7d

**Claim.** Polymarket YES contracts priced under 0.10 seven days before close resolve YES more often than their price implies (mean outcome - price > 0), on markets resolved after 2026-10-14.

- kind: market-structure · origin: experiment:X-59df1d8a, src:11
- statistic: mean(outcome - price) in the <0.10 bucket at the 7d horizon, bootstrap 95% interval
- null: calibrated bucket (mean error 0)
- procedure: same as harness longshot_bias, run ONLY on markets whose close is after 2026-10-14 (out of sample for this lead)
- data: a future polymarket-closed-markets pull restricted to close > 2026-10-14, plus price history · min n: 300
- pass: lower interval bound > 0 on the fresh sample
- controls: pre-registered here before any fresh data; horizon and bucket fixed; the in-sample reading (+0.018, [+0.002, +0.039], 8 YES events) is NOT evidence
- blocked on: a fresh pull of markets resolved after 2026-10-14 with >= 300 sub-0.10 observations at 7d (about one to two months of resolutions)
- note: pre-registered lead from the in-sample longshot_bias run: the classic longshot bias (T-02) was rejected and the sign points the other way. Eight YES events in 284 is far too few to act on; this entry exists so the fresh data decides, not the reading that suggested it.

## Parked (8)

### T-03 · edge-sign-consistent-across-scales

**Claim.** A real structural mispricing keeps the same sign of mean error at every horizon (1-90d); an artefact flips sign across horizons.

- kind: market-structure · origin: mandel:idea-3, adj:A4
- statistic: sign of mean(outcome - price) per horizon and whether any interval excludes zero
- null: mean error zero at every horizon
- procedure: bootstrap mean error per horizon; test sign agreement only if some horizon excludes zero
- data: same as T-01 · min n: 300
- pass: some horizon excludes zero AND signs agree across all horizons
- controls: horizons pre-registered; coarse horizons have small n
- harness: multiscale_edge
- result X-7389e3a9: not_supported — no horizon shows a mean error whose interval excludes zero: no structural market bias to be consistent about
- parked (was not_supported): not useful this iteration: no horizon shows a mean error whose interval excludes zero, so there is no structural bias to test sign-consistency on. Unpark when multiscale_edge finds any horizon excluding zero.

### T-08 · first-order-markov-beats-base-rate

**Claim.** A first-order Markov model on price buckets predicts the next move with positive information gain over the base rate, out of sample.

- kind: scaling · origin: src:09
- statistic: mean bits/step gain over base rate, walk-forward
- null: base-rate predictor
- procedure: fit transitions on the first 70%, score on the rest, per series
- data: polymarket-price-history-daily · min n: 60
- pass: mean gain > 0 with interval excluding 0
- controls: walk-forward; bucket edges fixed
- harness: markov_baseline
- result X-d969e49c: not_supported — first-order price-bucket Markov vs base rate: mean -0.0398 bits/step over 60 series
- parked (was not_supported): not useful this iteration: first-order Markov on price buckets loses 0.04 bits/step to the base rate out of sample over 60 series. Unpark to retry with finer buckets or on the long BTC/SPY daily histories.

### T-09 · msm-volatility-beats-rolling

**Claim.** A binomial Markov-switching multifractal volatility filter beats 20-day rolling variance on out-of-sample Gaussian log score.

- kind: scaling · origin: adj:A4
- statistic: median out-of-sample log-score gain (nats/obs)
- null: 20-day rolling variance
- procedure: fit MSM(k=3) by grid on the first half; filter the second half
- data: polymarket-price-history-daily, 12 longest series · min n: 12
- pass: median gain > 0
- controls: variance floor 1e-3 x series variance; same split for both
- harness: msm_volatility
- result X-28a5b00d: not_supported — MSM(k=3) vs 20-day rolling variance, out of sample: median gain -1.183 nats/obs over 12 series
- parked (was not_supported): not useful this iteration: MSM(k=3) scores 1.18 nats/obs worse than 20-day rolling variance on 12 Polymarket series; the series are too short to fit regime persistence. Unpark to retest on daily-history-BTC-USD / SPY (4411 / 8484 points) with the same harness.

### T-26 · provenance-store-retrieves-sources

**Claim.** Querying the insight store returns the originating source in the top 3 for >= 90% of held-out insight texts.

- kind: engine · origin: src:06
- statistic: top-3 retrieval precision
- null: random (~5/21)
- procedure: hold out insights; query by paraphrase
- data: insights.jsonl · min n: 100
- pass: >= 0.9
- controls: paraphrases generated blind
- parked (was untested): knowledge-management claim with no trading value this cycle; cheap to run later against insights.jsonl if retrieval quality becomes a bottleneck.
- note: knowledge-management claim; low value for trading; harness not written

### T-29 · pre-information-edge-presentiment

**Claim.** Some source produces forecasts, ledgered before any public information, that beat the coin on later-resolved questions.

- kind: psi · origin: src:02, src:03
- statistic: Brier skill vs coin of pre-information forecasts
- null: coin
- procedure: forecasts timestamped before information release; shuffle null
- data: forecast book · min n: 200
- pass: skill > 0, shuffle p < 0.01
- controls: timestamps ledgered; no post-hoc selection of questions
- blocked on: a source claiming pre-information forecasts; tested through the standard control design
- parked (was blocked): no mechanism and no claimant source; the standard control design (ledgered timestamps, shuffle null, coin and oracle) already tests any future pre-information claim. Kept for completeness.

### T-34 · box-count-dimension-matches-hurst

**Claim.** The box-counting dimension of a price path equals 2 - H within its interval, confirming the fractal-dimension reading of H.

- kind: scaling · origin: src:14
- statistic: D_box - (2 - H_DFA) per series
- null: D = 2 - H
- procedure: box count at dyadic scales; DFA for H
- data: polymarket-price-history-daily · min n: 40
- pass: |D - (2-H)| < 0.1 in > 75% of series
- controls: scale range fixed; finite-size bias at small boxes
- parked (was untested): diagnostic duplicate: hurst_ci already measures H by DFA; the box-count check adds no decision. Unpark if a fractal-dimension estimate is needed for a trading rule.
- note: harness not yet written; diagnostic, not a trading claim

### T-35 · mandelbrot-set-structure-is-a-metaphor

**Claim.** Escape-time structure of the Mandelbrot set yields no trading-relevant statistic beyond the multifractal and Hurst tests already in the registry.

- kind: metaphor · origin: src:15, src:16
- statistic: none proposed
- null: n/a
- procedure: n/a
- data: n/a · min n: 0
- pass: a concrete statistic is proposed
- controls: none
- blocked on: a concrete, falsifiable statistic (none proposed by the sources)
- parked (was blocked): the sources propose no falsifiable statistic beyond the multifractal and Hurst tests already in T-06 and T-07; kept as a record that the metaphor was considered.

### T-41 · crypto-fear-greed-is-contrarian

**Claim.** After extreme fear (index <= 25) the forward 7-day BTC log return exceeds the unconditional mean, and after extreme greed (>= 75) it falls short.

- kind: social · origin: social:alternative.me
- statistic: conditional minus unconditional mean forward return; block-shift p; split halves
- null: index circularly shifted against returns
- procedure: align index(d), usable d+1, to log(close(d+1+7)/close(d+1))
- data: crypto-fear-greed-history, daily-history-BTC-USD · min n: 200
- pass: p < 0.05 on fear or greed side with both halves agreeing in sign
- controls: point-in-time join on available_at <= decision time; no look-ahead; overlapping forward windows handled by the block shift
- harness: fear_greed_contrarian
- result X-1ad5ebb0: not_supported — 7d BTC-USD log return after fear<=25: +0.0001 vs all (block-shift p=0.518, halves +0.0070/-0.0086); after greed>=75: +0.0229 (p=0.957)
- parked (was not_supported): not useful this iteration: no contrarian effect of extreme crypto fear or greed on 7-day BTC returns over 3166 aligned days (block-shift p 0.52 and 0.96; the two halves disagree in sign). Unpark only for a pre-registered variant (e.g. 30-day horizon or index changes).
