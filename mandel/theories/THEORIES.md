# Theories and their trial math

Rendered from `registry.json` (hash `4bd40862980defa6`). 476 theories. supported 38, not_supported 119, inconclusive 13, untested 169, blocked 129, parked 8.

A theory is one falsifiable statement. Its status moves only through a recorded experiment result or a ledgered park/unpark event. Parked theories are kept in full so they can be picked up without re-deriving them.

## Supported (38)

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
- result X-85bebeee: supported — 28% of 40 daily logit-price series show concavity beyond the shuffled null (200 shuffles; threshold 25%; chance ~5%)

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
- result X-2d6b0510: supported — median H 0.35; 80% of 40 series with H < 0.5 (need > 50%); 12/40 significantly anti-persistent, below their 200-shuffle null (need > 25%); 0 significantly persistent (count against)
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
- result X-82a019fd: supported — best of 21 momentum rules: Sharpe -0.031, DSR 0.00, PBO 0.90

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
- result X-664c674d: supported — coin 0.25, oracle 0.0, market 0.024225094059405948: scoring path intact

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
- result X-3ba2e1c3: supported — in-sample best of 21 momentum rules mom_lb3_h3 (IS Sharpe -0.0264 over 6367 periods to 2025-08-12 00:00 UTC) has holdout Sharpe -0.0581 over 6220 later periods from 150 series (pass: <= 0)
- note: the dsr_pbo verdict (overfit) is the same statement from the other side

### T-48 · variance-risk-premium-spx

**Claim.** VIX-implied variance exceeds the realised variance of SPY over the following 21 trading days on average (a positive variance risk premium).

- kind: volatility · origin: literature:carr-wu-2009, cboe:VIX, options-sweep
- statistic: mean(VIX^2 - RV^2) over all days, vol-point gap, share positive
- null: implied = realised; studentized circular block bootstrap (block 42) of the daily difference
- procedure: align VIX close at t with realised variance of returns t+1..t+21; test the mean difference; require both halves positive
- data: cboe-VIX-history, daily-history-SPY · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: overlapping windows handled by the block bootstrap; VIX is SPX IV applied to SPY (tracking error small); point in time by construction
- harness: vrp_spx
- result X-c3f695ac: supported — implied 21.0 vs realised 18.6 vol pts over 8459 days (1993-01-29..2026-09-11); VRP positive on 84% of days, block-bootstrap p=0.0140, halves +0.0103/+0.0092
- result X-aa8c7df3: supported — implied 21.0 vs realised 18.6 vol pts over 8460 days (1993-01-29..2026-09-14); VRP positive on 84% of days, block-bootstrap p=0.0150, halves +0.0103/+0.0092

### T-49 · variance-risk-premium-btc

**Claim.** Deribit DVOL-implied variance exceeds realised BTC variance over the following 30 days on average.

- kind: volatility · origin: deribit:DVOL, options-sweep
- statistic: mean(DVOL^2 - RV^2), 365-day convention
- null: implied = realised; block bootstrap
- procedure: same as T-48 with 30-day windows and 7-day weeks
- data: deribit-dvol-BTC-history, daily-history-BTC-USD · min n: 1000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: DVOL history starts 2021-03; crypto trades 24/7 so the window is 30 calendar days
- harness: vrp_btc
- result X-c41a0dfb: supported — implied 62.9 vs realised 54.9 vol pts over 2000 days (2021-03-24..2026-09-13); VRP positive on 71% of days, block-bootstrap p=0.0010, halves +0.1535/+0.0345
- result X-7972f2f2: supported — implied 62.9 vs realised 54.9 vol pts over 2001 days (2021-03-24..2026-09-14); VRP positive on 71% of days, block-bootstrap p=0.0010, halves +0.1535/+0.0344

### T-50 · variance-risk-premium-gold

**Claim.** GVZ-implied variance exceeds realised GLD variance over the following 21 trading days on average.

- kind: volatility · origin: cboe:GVZ, options-sweep
- statistic: mean(GVZ^2 - RV^2)
- null: implied = realised; block bootstrap
- procedure: as T-48 on GLD
- data: cboe-GVZ-history, daily-history-GLD · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: GVZ is the IV of GLD options, so no index-vs-ETF mismatch
- harness: vrp_gold
- result X-eb9af641: supported — implied 18.7 vs realised 16.9 vol pts over 4267 days (2009-09-18..2026-09-11); VRP positive on 79% of days, block-bootstrap p=0.0040, halves +0.0084/+0.0040
- result X-b2950263: supported — implied 18.7 vs realised 16.9 vol pts over 4268 days (2009-09-18..2026-09-14); VRP positive on 79% of days, block-bootstrap p=0.0045, halves +0.0084/+0.0041

### T-53 · vix-term-structure-reversion

**Claim.** When VIX is above VIX3M (backwardation), VIX falls over the next 21 trading days by more than it does from contango.

- kind: volatility · origin: cboe:VIX3M, options-sweep
- statistic: mean 21d change in VIX after backwardation minus after contango
- null: VIX/VIX3M ratio circularly shifted against VIX changes
- procedure: state at close t; change t -> t+21; block-shift null; halves agree
- data: cboe-VIX-history, cboe-VIX3M-history · min n: 2000
- pass: difference < 0, p < 0.05, both halves < 0
- controls: mean reversion of VIX is mechanical in part; the test is whether the term structure adds to it (conditional means differ)
- harness: term_structure_reversion
- result X-47917835: supported — 21d change in VIX after backwardation -6.09 vs contango +0.45 pts (diff -6.54, block-shift p=0.0005, halves -5.43/-7.53; backwardation on 8% of days)
- result X-c287ea93: supported — 21d change in VIX after backwardation -6.09 vs contango +0.45 pts (diff -6.54, block-shift p=0.0005, halves -5.43/-7.53; backwardation on 8% of days)

### T-59 · turn-of-month-effect

**Claim.** SPY earns more on the last four and first three trading days of each month than on the other days.

- kind: underlying-strategy · origin: literature:lakonishok-smidt-1988, underlying-sweep
- statistic: mean daily return difference (bps), turn-of-month minus other days
- null: equal means; studentized block bootstrap (block 21) of the paired daily series
- procedure: flag days by month position; both halves must agree
- data: daily-history-SPY · min n: 3000
- pass: difference > 0, p < 0.05, both halves > 0
- controls: window fixed in advance (4 before, 3 after); no costs needed for a timing effect of this size to matter
- harness: turn_of_month
- result X-bc27e9fd: supported — turn-of-month days +9.0 bps/day vs others +1.6 (diff +7.4 bps, block-bootstrap p=0.0020, halves +8.8/+5.9)
- result X-3c158b05: supported — turn-of-month days +9.0 bps/day vs others +2.7 (diff +6.3 bps, block-bootstrap p=0.0065, halves +7.8/+4.8)

### T-63 · variance-risk-premium-oil

**Claim.** OVX-implied variance exceeds realised USO variance over the following 21 trading days on average.

- kind: volatility · origin: cboe:OVX, options-sweep
- statistic: mean(OVX^2 - RV^2)
- null: implied = realised; studentized block bootstrap
- procedure: as T-48
- data: cboe-OVX-history, daily-history-USO · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: overlapping windows via block bootstrap; index IV applied to the ETF
- harness: vrp_oil
- result X-888bbcd8: supported — implied 41.8 vs realised 36.7 vol pts over 4267 days (2009-09-18..2026-09-11); VRP positive on 79% of days, block-bootstrap p=0.0015, halves +0.0314/+0.0483
- result X-2a418ad7: supported — implied 41.8 vs realised 36.7 vol pts over 4268 days (2009-09-18..2026-09-14); VRP positive on 79% of days, block-bootstrap p=0.0015, halves +0.0313/+0.0484

### T-64 · variance-risk-premium-bonds

**Claim.** VXTLT-implied variance exceeds realised TLT variance over the following 21 trading days on average.

- kind: volatility · origin: cboe:VXTLT, options-sweep
- statistic: mean(VXTLT^2 - RV^2)
- null: implied = realised; studentized block bootstrap
- procedure: as T-48
- data: cboe-VXTLT-history, daily-history-TLT · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: overlapping windows via block bootstrap; index IV applied to the ETF
- harness: vrp_bonds
- result X-b147605f: supported — implied 15.5 vs realised 14.4 vol pts over 5697 days (2004-01-02..2026-09-11); VRP positive on 72% of days, block-bootstrap p=0.0220, halves +0.0019/+0.0044
- result X-1593db1c: supported — implied 15.5 vs realised 14.4 vol pts over 5698 days (2004-01-02..2026-09-14); VRP positive on 72% of days, block-bootstrap p=0.0215, halves +0.0019/+0.0044

### T-114 · big-lizard

**Claim.** A 30-DTE SPY big lizard (short ATM straddle, long +2% call), sold at the smile-scaled VIX model price and held to expiry, has positive mean P&L per unit downside max loss over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.tastylive.com/concepts-strategies/jade-lizard, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: mean P&L/max loss with block-bootstrap CI; condition frequency (C_r >= 0.02 S) by VIX bucket; paired difference vs the short straddle
- null: mean P&L = 0
- procedure: Price the straddle at s*VIX (s grid) and the +2% call at VIX x r(1.02); settle at S_{t+21}.
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 · min n: 390
- pass: lower CI > 0 under the smile-scaled model and at s = 0.90
- controls: Width fixed at 2%; proxy cap; costs haircut.
- harness: structure_t_114
- result X-84bd401c: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean +0.4% (95% CI +0.2 to +0.6); s=0.90 mean +0.5% (95% CI +0.2 to +0.7) — all criteria pass
- result X-0c32d400: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; percentile block-bootstrap CIs): smile mean +0.4% (95% CI +0.2 to +0.6); s=0.90 (call at VIX x r(1.02)) mean +0.9% (95% CI +0.7 to +1.1) — all criteria pass
- note: from the options-library library: Big Lizard; harness suggestion: harness 'big_lizard_condition' sharing straddle engine | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-115 · strip

**Claim.** A 30-DTE ATM SPY strip priced at BS(s*VIX) has lower mean P&L per unit premium than the ATM straddle on the same dates, over 1993-2026, for every s in {0.81, 0.90, 1.00} (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Straddle, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: paired mean difference (strip - straddle) of P&L/premium; studentized block-bootstrap CI
- null: no difference
- procedure: Shared ATM engine with a (calls, puts) ratio parameter
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 390
- pass: upper CI of the difference < 0 at all three s
- controls: Same dates; equity drift is the main driver, so also report a drift-removed version.
- harness: structure_t_115
- result X-b486bff8: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): strip-straddle s=0.81 mean -6.7% (95% CI -10.4 to -2.9); strip-straddle s=0.9 mean -6.1% (95% CI -9.4 to -2.7); strip-straddle s=1.0 mean -5.6% (95% CI -8.6 to -2.5) — all criteria pass
- result X-b9aaaeb9: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): strip-straddle s=0.81 mean -6.7% (95% CI -10.4 to -2.5); strip-straddle s=0.9 mean -6.1% (95% CI -9.5 to -2.3); strip-straddle s=1.0 mean -5.6% (95% CI -8.6 to -2.1) — all criteria pass
- note: from the options-library library: Strip; harness suggestion: include in 'straddle_vrp' harness as a ratio parameter (calls, puts) in {(1,1),(1,2),(2,1)} | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-116 · strap

**Claim.** A 30-DTE ATM SPY strap priced at BS(s*VIX) has higher mean P&L per unit premium than the strip on the same dates over 1993-2026, for every s in {0.81, 0.90, 1.00} (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Straddle
- statistic: paired mean difference (strap - strip) of P&L/premium; block-bootstrap CI
- null: no difference
- procedure: Shared ratio engine (2,1) vs (1,2)
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 390
- pass: lower CI of the difference > 0 at all three s
- controls: Drift is the obvious driver; report a drift-removed version.
- harness: structure_t_116
- result X-61fd43e1: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): strap-strip s=0.81 mean +13.3% (95% CI +5.7 to +20.6); strap-strip s=0.9 mean +12.1% (95% CI +5.3 to +18.7); strap-strip s=1.0 mean +11.0% (95% CI +4.9 to +17.0) — all criteria pass
- result X-a346d37e: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; percentile block-bootstrap CIs): strap-strip s=0.81 mean +13.3% (95% CI +5.7 to +20.6); strap-strip s=0.9 mean +12.1% (95% CI +5.3 to +18.7); strap-strip s=1.0 mean +11.0% (95% CI +4.9 to +17.0) — all criteria pass
- note: from the options-library library: Strap; harness suggestion: same ratio parameter in 'straddle_vrp' | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-126 · long-put

**Claim.** A 1-month ATM SPY put priced at VIX IV (model-priced, flat smile, so call and put carry the same IV) has a lower mean monthly return on premium than the matching ATM call over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/long-put, https://scholarsarchive.byu.edu/facpub/9281
- statistic: mean of paired monthly differences (put return minus call return) with block bootstrap CI; also each mean separately
- null: put mean return >= call mean return
- procedure: same engine as long-call: price the ATM put and ATM call at VIX IV each cycle, payoff from the SPY close, paired differences, at iv_scale 1.0 and 0.9
- data: SPY, VIX, DTB3 · min n: 300
- pass: upper CI of (put - call) < 0 at both iv_scales
- controls: Because both legs carry the same flat IV, this tests only drift plus the VIX-vs-realised gap. It does not test put-skew richness, which needs the captured chain (60+ days). VIX > ATM IV overprices both legs equally in vol terms. Paired design removes common vol shocks.
- harness: structure_t_126
- result X-ef87c11c: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): put-call s=1.0 mean -33.2% (95% CI -51.1 to -14.7); put-call s=0.9 mean -36.5% (95% CI -56.3 to -15.9) — all criteria pass
- result X-7e14bd33: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): put-call s=1.0 mean -33.2% (95% CI -51.1 to -14.7); put-call s=0.9 mean -36.5% (95% CI -56.3 to -15.9) — all criteria pass
- note: from the options-library library: Long Put; harness suggestion: vix_priced_option_returns(strategy='long_put', dte=30) paired with long_call output | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-130 · bear-put-spread

**Claim.** A 1-month ATM/-5% SPY bear put spread priced at VIX IV (model-priced) has a negative mean return per dollar of debit, and a lower mean than the matching ATM/+5% bull call spread, over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/bear-put-spread, https://cdn.cboe.com/resources/options/Trading_Strategies.pdf
- statistic: mean return on debit with block bootstrap CI; paired difference vs the bull call spread
- null: mean >= 0, or mean(bear put) >= mean(bull call)
- procedure: same monthly engine; puts at K2 = spot and K1 = 0.95 x spot priced at VIX IV; payoff from the SPY close
- data: SPY, VIX, DTB3 · min n: 300
- pass: upper CI < 0 and paired-difference upper CI < 0
- controls: Flat VIX overprices the ATM long put (VIX > ATM IV) and underprices the short 5%-OTM put (skew), so both biases inflate the modelled D and push toward a too-negative result, favouring a pass. Rerun at 0.9 x VIX and with chain mids at 60 days. Report with and without 2008 and 2020.
- harness: structure_t_130
- result X-c50f79b2: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): bear put spread mean -40.3% (95% CI -50.5 to -29.7); bear put - bull call mean -53.5% (95% CI -72.1 to -34.6) — all criteria pass
- result X-87b98a57: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): bear put spread mean -40.3% (95% CI -50.5 to -29.7); bear put - bull call mean -53.5% (95% CI -72.1 to -34.6) — all criteria pass
- note: from the options-library library: Bear Put Spread (Debit); harness suggestion: vix_priced_option_returns(strategy='bear_put_spread', dte=30, strikes=('ATM','OTM5')) | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-131 · bull-put-credit-spread

**Claim.** A 1-month 5%/10%-OTM SPY bull put spread priced at VIX IV (model-priced), rolled monthly, has a positive mean P&L per unit of max loss and a win rate above 85%, while its worst single month exceeds 10x the median credit, over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/bull-put-spread-credit-put-spread, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_SP_500_PutWrite_Indices_Methodology.pdf
- statistic: mean P&L / max loss with block bootstrap CI; win rate with binomial CI; ratio of the worst monthly loss to the median credit
- null: mean <= 0 (no premium left after the tails)
- procedure: monthly cycles; K2 = 0.95S, K1 = 0.90S puts priced at VIX IV; payoff from the SPY close; collateral earns DTB3
- data: SPY, VIX, DTB3 · min n: 300
- pass: lower CI of the mean > 0 AND win rate > 0.85 AND worst/median > 10 (all three pre-registered)
- controls: Correction: flat IV underprices both OTM puts, and the farther 10%-OTM long leg carries more skew, so the real credit may be smaller than modelled; the bias direction is indeterminate, not conservative. Use PSR with skew/kurtosis, walk-forward halves, and recheck with chain mids at 60 days.
- harness: structure_t_131
- result X-072c25c9: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): bull put spread mean +5.6% (95% CI +3.6 to +7.5); win rate 0.92, worst/median credit 30.1 — all criteria pass
- result X-2b7c636c: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): bull put spread mean +5.6% (95% CI +3.6 to +7.5); win rate 0.92, worst/median credit 30.1 — all criteria pass
- note: from the options-library library: Bull Put Spread (Credit); harness suggestion: vix_priced_option_returns(strategy='bull_put_spread', dte=30, strikes=('OTM5','OTM10')) | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-148 · straddle-calendar

**Claim.** The 30-to-93-day forward variance implied by VIX and VIX3M, FV = (93*VIX3M^2 - 30*VIX^2)/63, exceeds the realised SPY variance over the subsequent trading days 21..63 on average (a forward variance risk premium), so the reverse straddle calendar (short far / long near, delta-hedged) has positive expectancy and the long straddle calendar negative.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3, https://www.macroption.com/vix3m/
- statistic: Mean of (FV - RV_fwd) in annualised volatility points, where RV_fwd is realised SPY variance over trading days 21..63 after entry; also the share of positive observations
- null: Zero mean forward premium (expectations hypothesis holds for the 30-93 day segment)
- procedure: Daily since 2007-12-04 (VIX3M start); compute FV from VIX and VIX3M in variance units, RV_fwd from SPY log returns; studentized block bootstrap with block 63 for the overlapping daily series and a plain bootstrap on non-overlapping 3-month windows; walk-forward halves
- data: CBOE VIX and VIX3M daily history, SPY daily closes · min n: 60
- pass: 95% CI of the mean excludes 0 in both halves and the mean exceeds 1 vol point; sign test p < 0.05 on non-overlapping windows
- controls: Compare with the spot VRP (VIX^2 - RV_30) to show the forward premium is incremental to the 30-day premium; report 2008 and 2020 separately; the position-level P&L requires model pricing, but the claim itself is data-only
- harness: forward_variance_premium
- result X-439c1b3e: supported — forward vol (VIX/VIX3M, days 21-63) exceeds realised by +6.21 vol pts on average (87% of 4229 days since 2009-09-18); halves +6.42/+5.99 (p 0.000/0.012); sign test 59/68 p=0.0000
- result X-8f04150f: supported — forward vol (VIX/VIX3M, days 21-63) exceeds realised by +6.21 vol pts on average (87% of 4229 days since 2009-09-18); halves +6.42/+5.99 (p 0.000/0.012); sign test 59/68 p=0.0000
- note: from the options-library library: Straddle calendar (time spread of straddles / forward-vol trade); harness suggestion: forward_variance_premium(vix_rows, vix3m_rows, price_rows) in experiments/volatility.py alongside variance_risk_premium; then a model-priced straddle-calendar P&L using the two-expiry simulator as a secondary check. | superseded by T-510 (verifier-corrected wording)

### T-175 · covered-call-ibit

**Claim.** From 2021-03-24 to 2026-10, Deribit BTC DVOL exceeds the subsequent 30-calendar-day realised volatility of BTC daily closes by more than 5 vol points on average.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=1D, https://www.deribit.com/api/v2/public/get_historical_volatility?currency=BTC
- statistic: Mean of (DVOL_t - RV_{t, t+30d}), RV annualised with 365 days
- null: Mean <= 5 vol points
- procedure: Page public/get_volatility_index_data backwards (it returns at most ~1000 daily rows per call) to get the full 2021-03-24 onward series (2,031 rows today). Compute forward 30-day realised vol from BTC daily closes. Use non-overlapping or HAC (lag 30) inference, stationary block bootstrap, walk-forward halves. Repeat for ETH.
- data: DVOL BTC/ETH 2021-03 onward (paged), BTC/ETH daily closes (archived), Deribit get_historical_volatility (384 rows) as a cross-check · min n: 700
- pass: Lower 95% CI of the mean gap > 5 vol points, with the same sign in both halves
- controls: The same statistic for SPX (VIX vs forward RV) as the known-positive reference; crash months (May-21, Nov-22) kept in. The IBIT-vs-DVOL IV basis is measured separately from the daily IBIT chain capture.
- harness: dvol_gap_5pts
- result X-f7120cfc: supported — BTC DVOL implied minus realised over 30 periods: +8.4055 vol pts since 2021-03-24 (95% CI +5.3997 to +11.4100), halves +12.1785/+4.6324 — all criteria pass
- note: from the options-library library: Covered call on IBIT / BTC ETF; harness suggestion: Already close to the BTC-VRP harness; add the conditional-on-percentile split and report expected premium capture per 30-delta covered call via Black-Scholes at DVOL. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-216 · opex-gamma-pin-short-straddle

**Claim.** A 1-day ATM SPY short straddle model-priced with VIX-as-IV (sigma = VIX at Thursday's close, T = 1/252), sold at Thursday's close and settled at Friday's close, has a higher mean P&L when that Friday is a monthly third-Friday expiration than on other Fridays.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable-products/0dte, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Difference in mean MODEL-PRICED short-straddle P&L (opex Fridays minus other Fridays), bootstrap CI; secondary: distance of SPY close to nearest $1 strike, opex vs non-opex (permutation test).
- null: Opex-Friday mean P&L <= other-Friday mean P&L.
- procedure: Third Fridays since 1993; SPY closes; VIX; settle on |SPY_Fri - SPY_Thu|; compare groups. The open-to-close version and OI/GEX conditioning need OHLC and chain captures.
- data: SPY daily closes since 1993, VIX; later chain OI captures. · min n: 300
- pass: Difference > 0 with 95% CI excluding 0.
- controls: Exclude opex days with FOMC/CPI; quarterly vs non-quarterly opex; pre/post-2010 split.
- harness: ohlc_opex_pin_straddle
- result X-ace3719a: supported — MODEL-PRICED (BS, sigma = Thursday VIX, T=1/252): 395 opex vs 1253 other Fridays 1993-02-05..2026-10-09; short-straddle P&L +26.99 vs +17.85 bps of spot, difference +9.14 bps (95% block-8 CI +1.81..+16.31, p=0.005); settled on raw closes |SPY_Fri - SPY_Thu| with the known dividend priced into the forward S_thu - D on the 132 ex-dividend Fridays (132 of them opex); as-worded sensitivity at r = q = 0 ignoring the dividend: +6.57, CI -0.76..+13.77 (not supported, so the verdict depends on how the dividend is treated); with all ex-dividend Fridays dropped: +10.15, CI +2.05..+18.11; $1-strike distance opex 0.256 vs 0.250 (perm p=0.760) — all criteria pass
- note: from the options-library library: Monthly opex gamma pin (short ATM straddle / iron butterfly on heavy-OI strikes); harness suggestion: Add a GEX estimator (sum over strikes of OI*gamma*spot^2*0.01 with sign convention calls +, puts -) once chain captures accumulate; join to the opex clustering test. | verifier: corrected claim/trial | Scope (2026-10-15): supported for the MODEL-PRICED straddle (sigma = Thursday VIX, T = 1/252), priced on the dividend forward on ex-dividend Fridays. The 132 quarterly opex Fridays are SPY ex-dividend days; at r = q = 0 with the dividend ignored the difference is +6.57 bps with a CI of -0.76..+13.77, so the as-priced reading matters. With every ex-dividend Friday dropped the result holds (+10.15 bps, CI +2.05..+18.11). A traded-price test needs 1-day implied vol on opex Thursdays (chain captures). CPI-day exclusion control pending (task: CPI-calendar controls).

### T-224 · metals-macro-event-straddle

**Claim.** On FOMC and CPI days since 2009-09, a 1-day ATM GLD straddle model-priced with GVZ-as-IV (sigma = GVZ at the T-1 close, T = 1/252) and sold at the T-1 close has a lower mean P&L than the same model-priced straddle on non-event days.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.optionseducation.org/strategies/all-strategies/short-strangle
- statistic: Difference in mean MODEL-PRICED short-straddle P&L (event minus non-event), bootstrap CI; mean |r|/(GVZ/sqrt(252)) by group.
- null: Event-day mean P&L >= non-event mean P&L.
- procedure: Load GLD daily closes and the GVZ CSV; FOMC (Fed calendars) and CPI dates (hardcoded from BLS archives); stratify by GVZ tercile and by real-rate regime.
- data: GLD daily closes (free, not wired), Cboe GVZ history (free CSV, not in the current list), FOMC/CPI calendars. · min n: 150
- pass: Difference < 0 with 95% CI excluding 0.
- controls: Placebo dates; exclude 2020-03; compare with the SPX result.
- harness: macro_gld_event_straddle
- result X-6e050abd: supported — MODEL-PRICED short 1-day ATM GLD straddle (BS, sigma=GVZ(T-1), T=1/252) 2009-09-21..2026-10-13: event mean +7.2 vs non-event +15.3 bps of spot; difference -8.1 bps (95% CI -15.2 to -1.7, one-sided p=0.0095) over 328 event days (FOMC 136, CPI 203) / 3955 other; |r|/(GVZ/sqrt252) event 0.74 vs other 0.65; FOMC -20.1, CPI -1.3 bps; placebo +/-7d +1.0 bps; ex Mar-2020 -8.6 bps; SPY/VIX same events -6.2 bps — all criteria pass
- note: from the options-library library: Metals macro-event straddle (FOMC / CPI / NFP) on GC or GLD; harness suggestion: Generalise the VIX-as-IV straddle harness to (underlying, vol index) pairs: (SPY,VIX), (GLD,GVZ), (BTC,DVOL), (QQQ,VXN). | verifier: corrected claim/trial | Scope (2026-10-15): supported for the claim as worded, a MODEL-PRICED straddle at sigma = GVZ(T-1). GVZ is 30-day implied vol; on event days the true 1-day implied vol carries the event premium, so a traded short straddle collects more than this model and the gap would shrink. A traded test needs event-day 1-day GLD implied vol.

### T-244 · gold_vrp_gvz

**Claim.** Since 2009-09, the 30-day gold variance premium, (GVZ/100)^2 minus the subsequently realised 21-trading-day variance of GLD, is positive on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean of (GVZ_t/100)^2 - RV_GLD(t..t+21) (annualised); secondary: the premium as a fraction of implied variance compared with the SPX figure (VIX/SPY) on the same dates.
- null: Mean <= 0.
- procedure: Non-overlapping 21d cycles from 2009-09-18 (~200); studentized block bootstrap; walk-forward thirds; side-by-side with harness_vrp_spx on common dates.
- data: CBOE GVZ (archive), GLD closes (archive). Model-free (index-implied variance). · min n: 180
- pass: Mean > 0 with the 95% CI excluding zero, positive in at least 2 of 3 thirds.
- controls: Buy-and-hold GLD (harness_controls); shuffled-GVZ placebo; GC=F front-futures closes (archive) instead of GLD.
- harness: gvz_var_premium_thirds
- result X-e4186ff5: supported — GVZ^2 vs GLD implied minus realised over 21 periods: +0.0062 variance since 2009-09-18 (95% CI +0.0032 to +0.0089), thirds +0.0091/+0.0065/+0.0031 — all criteria pass
- note: from the options-library library: Gold volatility premium (GVZ) via GLD straddles / GC strangles; harness suggestion: harness_vrp_gold exists; add the ratio-to-SPX comparison and a 15-delta strangle pricer; add SLV ATM IV from surface_summary for the silver twin. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-246 · btc_dvol_vrp

**Claim.** Over the Deribit DVOL history (2021-03 to 2026-10), (DVOL/100)^2 exceeds the subsequently realised 30-calendar-day BTC variance (365-day annualisation) on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.deribit.com/kb/options, https://docs.deribit.com/_llms/production/api-reference/json-rpc-api.txt
- statistic: Mean of (DVOL_t/100)^2 - RV_BTC(t..t+30 calendar days); secondary: win rate, share of cumulative premium lost in the worst decile of months, and a model-priced hedged straddle with funding at 0 and +/-10% p.a.
- null: Mean <= 0.
- procedure: Non-overlapping 30-calendar-day cycles over the archived DVOL history (~67); studentized block bootstrap; walk-forward halves; cross-check the implied level against today's deribit_book ATM mark_iv.
- data: Deribit DVOL history (archive, deribit_dvol_history), BTC/ETH daily closes (archive), deribit_book snapshot. · min n: 60
- pass: Mean > 0 with the 95% CI excluding zero, positive in both halves.
- controls: Buy-and-hold BTC; shuffled-DVOL placebo; the SPX VRP over the same dates for scale.
- harness: dvol_var_premium
- result X-b01e58de: supported — DVOL^2 vs BTC implied minus realised over 30 periods: +0.0940 variance since 2021-03-24 (95% CI +0.0539 to +0.1348), halves +0.1535/+0.0345 — all criteria pass
- note: from the options-library library: BTC/ETH volatility premium (DVOL vs realised) via Deribit inverse straddles; harness suggestion: harness_vrp_btc and harness_vrp_eth exist; add the worst-decile share, a funding sensitivity parameter and an inverse-payoff conversion in the payoff engine (payoff in BTC = payoff_usd / S_T). | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-266 · eth-btc-vol-pair

**Claim.** When the ETH/BTC DVOL ratio is below its trailing 365-day 20th percentile, the subsequent 30-day realised vol ratio (ETH/BTC) exceeds the entry DVOL ratio on average, 2022-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&start_timestamp=1700000000000&end_timestamp=1700300000000&resolution=86400
- statistic: Mean of (RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC), conditional on the low percentile
- null: Mean <= 0
- procedure: Daily DVOL for both; 30-day forward realised vol from closes; 365-day percentile filter; non-overlapping entries; block bootstrap; walk-forward
- data: BTC and ETH DVOL from 2021-03-24; BTC/ETH closes · min n: 25
- pass: CI > 0; report the unconditional mean (usually negative, since DVOL carries a VRP) for comparison
- controls: High-percentile mirror trade; random dates
- harness: eth_btc_dvol_ratio
- result X-7cf64c6f: error — harness raised ValueError
- result X-39ddc726: supported — ETH/BTC DVOL extremes: 21 signals, mean +0.072 log units (95% CI +0.015 to +0.125), win rate 0.71 — all criteria pass
- note: from the options-library library: ETH vs BTC relative volatility (vol pair / dispersion); harness suggestion: deribit_dvol_history('ETH') alongside BTC; ratio harness | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-271 · gold-vrp-short-strangle

**Claim.** The gold variance risk premium (GVZ^2 minus the subsequent 30-day realised variance of GLD, both annualised) is positive on average over 2009-10 to 2026-09, with a block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Mean VRP over non-overlapping 30-day windows (conditional mean when GVZ > its 1-year median reported)
- null: Mean VRP <= 0
- procedure: GVZ daily; realised from GLD closes over the next 21 trading days; non-overlapping windows; studentized block bootstrap; walk-forward halves
- data: GVZ history 2009-09-18..; GLD closes (Yahoo) · min n: 150
- pass: CI > 0 pooled and positive mean in both halves
- controls: SPY/VIX VRP as benchmark; shuffled GVZ
- harness: gvz_var_premium_halves
- result X-c5b6056b: supported — GVZ^2 vs GLD implied minus realised over 21 periods: +0.0062 variance since 2009-10-01 (95% CI +0.0032 to +0.0089), halves +0.0083/+0.0041 — all criteria pass
- note: from the options-library library: Gold variance risk premium (delta-hedged short strangle on GLD/GC); harness suggestion: Clone the SPY/VIX VRP harness with GVZ/GLD inputs | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-279 · metals-put-write

**Claim.** Model-priced (BS with GVZ as a flat IV): writing a 25-delta 30-DTE GLD put each month over 2009-10 to 2026-09 has a positive mean cycle P&L ((premium - payoff)/K), with a studentized block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.optionseducation.org/strategies/all-strategies/cash-secured-put, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Mean cycle P&L / K
- null: Mean <= 0
- procedure: Monthly cycles on GLD closes; BS at GVZ; bootstrap; walk-forward halves
- data: GVZ history; GLD closes (Yahoo) · min n: 100
- pass: CI > 0 pooled and positive mean in both halves
- controls: SPY/VIX put-write (PUT index behaviour) as positive control; GVZ - 2 vol points sensitivity
- harness: gld_put_write
- result X-70072aa5: supported — MODEL-PRICED at flat GVZ: 0.25-delta short put mean +0.33% of spot per cycle over 203 cycles (95% CI +0.16 to +0.49), halves +0.14/+0.51 — all criteria pass
- result X-460817bd: supported — MODEL-PRICED at flat GVZ: 0.25-delta short put mean +0.33% of strike per cycle over 203 cycles (95% CI +0.16 to +0.49), halves +0.14/+0.51 — all criteria pass
- note: from the options-library library: Metals put-write for accumulation (GLD/SLV cash-secured; GC/SI SPAN); harness suggestion: Shares loop with gold-covered-call; kind='put' | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-320 · crypto-short-term-reversal

**Claim.** For BTC-USD 2015-2026, the mean next-day return after a bottom-decile daily return is NOT greater than the unconditional mean by more than 0.6% (one Coinbase taker round trip); reversal, if present, is below cost.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1016/j.irfa.2021.101908, https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php
- statistic: difference in mean next-day return (conditional minus unconditional), studentized block bootstrap interval; net Sharpe of the rule
- null: no conditional difference (shuffled-increment null preserving marginal)
- procedure: walk-forward thresholds from the trailing 60 days (no look-ahead); 1000 block-bootstrap resamples (block 10 days); DSR across the five variants
- data: Yahoo BTC-USD since 2014, ETH-USD since 2017; Coinbase daily candles since 2015-07 for executable prices; CoinGecko market caps for the cross-section · min n: 400
- pass: strategy is supported only if the net difference's lower interval bound > 0; otherwise the claim (no tradable reversal) stands
- controls: look-ahead via trailing quantiles; survivorship in the cross-section (delisted coins) handled by using the trailing market-cap list at formation; costs 0.6% round trip; multiple testing via DSR; regime: 2015-2019 vs 2020-2026
- harness: btc_reversal
- result X-0d11fe29: supported — 492 bottom-decile days: next-day excess +8.8 bps gross, -51.2 net of 0.6% (95% CI -76.9 to -24.6) — no tradable reversal: the claim holds
- result X-5add37e1: supported — 492 bottom-decile days: next-day excess +8.8 bps gross, -51.2 net of 0.6% (95% CI -76.9 to -24.6) — no tradable reversal: the claim holds
- result X-a95bab1b: supported — 492 bottom-decile days: next-day excess +8.9 bps gross, -51.1 net of 0.6% (95% CI -76.9 to -24.6) — no tradable reversal: the claim holds
- note: from the underlying-library library: Crypto short-term reversal (time-series BTC/ETH and cross-section of coins); harness suggestion: ts_reversal_quantile: generic conditional-next-return test with trailing quantile thresholds, reusable for SPY/QQQ | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-469 (verifier-corrected wording)

### T-332 · index-etf-daily-technical-reversal

**Claim.** On SPY from 2000-01 to 2026-09, the mean next-day close-to-close return after IBS < 0.2 exceeds the unconditional mean next-day return by more than 2 bps (one round-trip spread).

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1080/17446540701206576, https://doi.org/10.2139/ssrn.1095202
- statistic: conditional minus unconditional mean next-day return; net Sharpe of each rule; DSR over 6 rules x 2 tickers (12 trials)
- null: no conditional difference (block-shifted signal null preserving return autocorrelation; stationary bootstrap block 20)
- procedure: Compute signals from OHLC and next-day returns. Run 2,000 resamples. Split-sample sign check (2000-2012 / 2013-2026). DSR and CSCV PBO over the rule grid. Report next-open execution as well as same-close.
- data: Yahoo daily OHLC: SPY (1993; use 2000- because early opens/highs/lows are unreliable), QQQ (1999) · min n: 2000
- pass: 95% lower bound of the difference > 2 bps AND same sign in both halves AND DSR > 0.95
- controls: Look-ahead: trading at the same close that defines IBS is optimistic (MOC orders must be sent before the final print), so next-open/next-close execution is reported. Costs: 1 bp spread per side, zero commission. Multiple testing: 12 trials plus prior T-58/T-10/T-36. Regime: post-2013 weakening reported; VIX terciles.
- harness: ohlc_ibs_reversal
- result X-660e7d9f: supported — SPY IBS<0.2 on 1310 of 6725 days 2000-01-03..2026-09-29: next-day +15.93 vs unconditional +3.90 bps, difference +12.03 bps (95% stationary-bootstrap CI +5.14..+19.55; needs lower > 2); block-shift p=0.0005; halves +16.66 / +7.10 bps; DSR 0.976 over 12 trials; execution diagnostics: next-open-to-close +7.54 bps, next-close entry +6.89 bps — all criteria pass
- note: from the underlying-library library: Index ETF daily technical reversal (RSI(2), Bollinger, IBS, down-day streak); harness suggestion: daily_rule_grid: declared indicator set, conditional-mean test, split-sample sign check, dsr_pbo_harness feed (parallels the Polymarket T-10 harness) | verifier: corrected claim/trial | Scope (2026-10-15): min_n 2000 is counted in trading days (6,725 in the window); the signal fires on 1,310 days. The pass statistic trades at the close that defines IBS (optimistic for MOC); next-open-to-close +7.5 bps and next-close entry +6.9 bps are reported as execution diagnostics, both above the 2 bps bar but not tested against it.

### T-436 · crypto-calendar-effects

**Claim.** Over 2014-2026, BTC-USD's mean Monday (UTC) return exceeds the mean of the other six days by at least 20 bps, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/finlet/v31y2019ics1544612318304513.html
- statistic: Monday mean minus other-day mean (bps); single pre-registered contrast.
- null: Equal means. Studentized block bootstrap (block 14 calendar days) of the day-flagged series; plus a within-week weekday-label permutation.
- procedure: Run on BTC-USD (primary). ETH/SOL and the secondary rules are Holm-adjusted trials. A full 7-weekday scan is reported only as exploratory, with Bonferroni over 7.
- data: daily-history-BTC-USD (2014-09-17-), ETH-USD (stored), SOL-USD via Yahoo; Coinbase hourly candles for the hours arm (untested, 300 bars per request). · min n: 600
- pass: Monday excess > 20 bps with p < 0.05 and both halves positive. Net-of-maker-fee (0.4% round trip) weekly strategy Sharpe > buy-and-hold is reported but expected to fail.
- controls: Look-ahead: none; Yahoo's BTC daily bar is the UTC day. Survivorship: BTC/ETH/SOL only (biased toward survivors). Costs: 52 round trips/yr at venue fees, decisive. Multiple testing: 1 primary plus 6 Holm. Regime: halves; 2017 and 2021 bubbles; T-62 null as prior.
- harness: btc_monday_v2
- result X-6198668a: supported — BTC Monday +36.5 bps vs other days (p=0.012), halves +52.8/+20.1 — all criteria pass
- result X-e5c606da: supported — BTC Monday +36.5 bps vs other days (p=0.013), halves +52.9/+20.2 — all criteria pass
- note: from the underlying-library library: Crypto calendar effects: Monday, month-turn, expiry, holidays; harness suggestion: weekday_contrast(days, closes, 'Mon', 'rest', calendar=7) beside weekday_effect; turn_of_month on 7-day calendars; last_fridays-based event_day_effect two-sided; data/fetch.py coinbase_candles(product, 3600) with paging for the hours arm. | verifier-corrected restatement of T-354, whose verdict tested the earlier wording and stands | READ WITH CARE: the verifier's restatement dropped the Bonferroni correction over seven weekdays that T-354 carried. Uncorrected p = 0.012 passes; corrected it would be about 0.08. Mandel has also tested BTC weekend vs weekday (T-62, not supported) and the BTC weekday family, so the honest multiplicity is at least seven. A Monday-only strategy net of a 0.4% round trip has Sharpe 0.18 vs buy-and-hold 0.99 (T-354): the effect is not tradable at retail cost.

### T-510 · straddle-calendar

**Claim.** The 30-to-93-day forward variance implied by VIX and VIX3M, FV = (93*VIX3M^2 - 30*VIX^2)/63, exceeds the realised SPY variance over trading days 21..63 after entry on average: a positive forward variance risk premium of more than 1 vol point.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3, https://www.macroption.com/vix3m/
- statistic: Mean of (sqrt(FV) - sqrt(RV_fwd)) in annualised vol points, where RV_fwd is the realised SPY variance over trading days 21..63; also the share of positive observations
- null: Zero mean forward premium (the expectations hypothesis holds for the 30-93 day segment)
- procedure: Daily since the first aligned VIX/VIX3M/SPY date. Compute FV from VIX and VIX3M in variance units and RV_fwd from SPY log returns. Studentized block bootstrap (block 63) on the overlapping daily series, a sign test on non-overlapping 63-day windows, walk-forward halves.
- data: CBOE VIX and VIX3M daily history, SPY daily closes (data-only: no option pricing) · min n: 60
- pass: Mean > 1 vol point with the one-sided p < 0.025 in both halves and a sign test p < 0.05 on non-overlapping windows
- controls: VIX and VIX3M are variance-swap rates, so FV is a forward variance-swap rate, not a forward ATM-straddle vol (it includes the skew premium). Compare with the spot VRP (VIX^2 - RV_30) to show the forward premium adds information. Report 2008 and 2020 separately. Position-level straddle-calendar P&L needs model pricing; the claim itself is data-only.
- harness: forward_variance_premium
- result X-8f04150f: supported — forward vol (VIX/VIX3M, days 21-63) exceeds realised by +6.21 vol pts on average (87% of 4229 days since 2009-09-18); halves +6.42/+5.99 (p 0.000/0.012); sign test 59/68 p=0.0000
- result X-a3e70303: supported — forward vol (VIX/VIX3M, days 21-63) exceeds realised by +6.21 vol pts on average (87% of 4230 days since 2009-09-18); halves +6.42/+6.00 (p 0.000/0.010); sign test 59/68 p=0.0000
- note: from the options-library library: Straddle calendar (time spread of straddles / forward-vol trade); harness suggestion: Already harnessed as T-148, forward_variance_premium in experiments/options_market.py (not volatility.py). The archived verdict is supported: +6.21 vol points, positive on 87% of 4,229 days since 2009-09-18, halves +6.42/+5.99, sign test 59/68. Next: a model-priced delta-hedged reverse straddle-calendar P&L through the two-expiry simulator, to check that the premium survives four-leg costs. | verifier-corrected restatement of T-148, whose verdict tested the earlier wording and stands

### T-512 · crude-ovx-vrp

**Claim.** The crude-oil variance risk premium (OVX^2 minus the subsequent 30-day realised variance of USO, annualised) is positive on average over 2009-10 to 2026-09, with a block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-specific, https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv, https://www.optionseducation.org/strategies/all-strategies/short-strangle
- statistic: Mean VRP over non-overlapping 30-day windows
- null: Mean VRP <= 0
- procedure: OVX daily; realised from split-adjusted USO closes over the next 21 trading days; studentized block bootstrap; walk-forward halves; report with and without 2020-03..2020-06
- data: Cboe OVX_History.csv (from 2009-09-18, verified); USO closes (Yahoo, in collect_history) · min n: 150
- pass: CI > 0 pooled and positive mean in both halves
- controls: GVZ/GLD and VIX/SPY VRPs as comparators; shuffled OVX
- harness: ovx_var_premium
- result X-40ab469d: supported — OVX^2 vs USO implied minus realised over 21 periods: +0.0397 variance since 2009-10-01 (95% CI +0.0130 to +0.0635), halves +0.0311/+0.0484 — all criteria pass
- note: from the options-library library: Crude oil variance risk premium (OVX on USO) short strangle; harness suggestion: Clone the GVZ VRP harness with OVX/USO inputs; cboe_index_history('OVX') | added by the verifier pass | tested by mandel/experiments/cross_asset.py

### T-514 · gvz-vix-relative-vol

**Claim.** The 20-trading-day forward change in log(GVZ/VIX) is negatively related to the ratio's z-score versus its trailing 252-day mean (OLS slope < 0), 2010-2026.

- kind: options-strategy · origin: options-library:crypto-metals-specific, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv, https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- statistic: OLS slope of the 20-day forward change in log(GVZ/VIX) on the 252-day z-score
- null: Slope >= 0
- procedure: Daily GVZ and VIX; z-score; regress the forward change; block bootstrap (block = 20 days) for the slope CI; walk-forward halves; then model-price the straddle pair (BS at GVZ and VIX) on |z| > 1.5 entries
- data: Cboe GVZ and VIX histories (verified CSVs); GLD and SPY closes (Yahoo) · min n: 150
- pass: Slope 95% CI < 0 in both halves
- controls: Shuffled-date null; the same test on log(OVX/VIX)
- harness: gvz_vix_zscore_slope
- result X-46f63ac4: supported — GVZ/VIX 20-day reversion: slope on z-score -0.0837 (upper -0.0598) and -0.0723 (upper -0.0397) in the two halves, 201 samples — all criteria pass
- note: from the options-library library: Gold vs equity implied-vol spread (GVZ/VIX relative value); harness suggestion: Ratio z-score harness over cboe_index_history('GVZ') and ('VIX') | added by the verifier pass | tested by mandel/experiments/cross_asset.py

### T-515 · btc-weekend-theta

**Claim.** BTC's mean squared UTC close-to-close daily return on Saturdays and Sundays is less than 0.9 times its mean squared daily return on Mondays to Fridays, 2017-2026.

- kind: options-strategy · origin: options-library:crypto-metals-specific, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://www.optionseducation.org/strategies/all-strategies/short-strangle
- statistic: Ratio of mean squared Sat+Sun daily returns to mean squared Mon-Fri daily returns
- null: Ratio >= 0.9
- procedure: From daily BTC closes (UTC 00:00) split returns by day of week; compute the ratio pooled and per year; block bootstrap (block = 4 weeks); report per-year ratios
- data: BTC daily closes (Yahoo BTC-USD, UTC daily bars) · min n: 200
- pass: Pooled 95% CI of the ratio entirely < 0.9, and ratio < 1 in at least 70% of years
- controls: Same ratio for ETH; shuffled weekday labels as null; exclude the top 1% |returns| as a robustness check
- harness: btc_weekend_ratio_v2
- result X-696b70b5: supported — BTC weekend/weekday squared-return ratio 0.47 (95% CI 0.38-0.57, needs entirely < 0.9); below 1 in 100% of years (needs 70%)
- result X-a15a3182: supported — BTC weekend/weekday squared-return ratio 0.47 (95% CI 0.38-0.57, needs entirely < 0.9); below 1 in 100% of years (needs 70%)
- result X-177cecd0: supported — BTC weekend/weekday squared-return ratio 0.47 (95% CI 0.38-0.57, needs entirely < 0.9); below 1 in 100% of years (needs 70%)
- note: from the options-library library: Weekend theta harvest (24/7 pricing vs weekend realised vol); harness suggestion: Extend underlying.weekend_effect to variance ratios; later confirm the pricing side with weekend-daily trade IVs | verifier-corrected restatement of T-264, whose verdict tested the earlier wording and stands

### T-517 · seagull

**Claim.** A 1-month zero-cost SPY seagull (long ATM call, short 5%-OTM call, short put struck to make net premium zero; all at VIX IV, model-priced) has a positive mean monthly P&L per unit spot over 1993-2026, holding in both walk-forward halves.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/bull-call-spread-debit-call-spread, https://www.optionseducation.org/strategies/all-strategies/naked-put-uncovered-put-short-put
- statistic: mean P&L per unit spot with block bootstrap CI, per half
- null: mean <= 0
- procedure: monthly cycles; solve K1 for zero cost at VIX IV; payoff from the SPY close
- data: SPY, VIX, DTB3 · min n: 300
- pass: lower CI > 0 in the full sample and the mean > 0 in both halves
- controls: Under flat pricing the zero-cost put sits near ATM, whereas with real skew it sits 3-6% OTM, so the model trade is far more put-heavy than the traded one: a chain-based rerun at 60 days is required before any trading conclusion. Run at iv_scale 0.9.
- harness: structure_t_517
- result X-19a801eb: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): seagull mean +0.9% (95% CI +0.6 to +1.2); halves +0.68%/+1.14% — all criteria pass
- result X-b780aa15: supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): seagull mean +0.9% (95% CI +0.6 to +1.2); halves +0.69%/+1.14% — all criteria pass
- note: from the options-library library: Seagull (Put-Financed Call Spread); harness suggestion: overlay_backtest(strategy='seagull', k_put='zero_cost') in mandel/experiments/volatility.py | added by the verifier pass | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-530 · calendar_vol_spread

**Claim.** Conditional on VIX3M/VIX > 1.10 at entry, the 1-to-3-month SPX forward variance F^2 = (93*VIX3M^2 - 30*VIX^2)/63 exceeds the SPY variance realised over trading days 22-63 after entry on average, so the far leg of a reverse calendar is sold above its subsequent realised variance.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.cboe.com/tradable_products/vix/term_structure/, https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv
- statistic: Mean of F^2 - RV(22..63), both annualised, over entries with VIX3M/VIX > 1.10.
- null: Conditional mean <= 0.
- procedure: Daily VIX and VIX3M from 2009-09-18 (the free VIX3M file starts there, not 2007) and SPY closes. Non-overlapping 63d cycles (~68 in total, fewer conditional), plus all daily starts with a 63-day-block studentized bootstrap. Walk-forward over declared thresholds 1.05/1.10/1.15, deflated.
- data: CBOE VIX and VIX3M (archive), SPY closes. Index-implied variance, not option prices; the calendar's own P&L needs chain history. · min n: 40
- pass: Conditional mean > 0 with the 95% CI excluding zero, positive in both halves of 2009-2026.
- controls: Unconditional forward premium (harness_forward_variance); shuffled-ratio placebo; sensitivity run excluding 2020.
- harness: conditional_forward_v2
- result X-eb6f8b95: supported — 63 contango entries: forward variance minus realised (days 22-63) +0.0220 (p=0.0005), halves +0.0185/+0.0254
- result X-d4ada054: supported — 63 contango entries: forward variance minus realised (days 22-63) +0.0220 (p=0.0005), halves +0.0185/+0.0254
- note: from the options-library library: Calendar vol spread (ATM time spread, long or reverse); harness suggestion: harness_forward_variance (T-148, uses 93/30/63) and harness_term_vs_spot (T-231, uses the cruder (3*VIX3M^2 - VIX^2)/2) already compute this gap; add the VIX3M/VIX gate and unify both on the 93/30/63 formula. The calendar P&L comes from build_position with two expiries once captures exist. | verifier-corrected restatement of T-231, whose verdict tested the earlier wording and stands

### T-534 · vix_contango_short_call_spread

**Claim.** When VIX3M/VIX > 1.10, spot VIX 21 trading days later is below the forward-variance-implied level F = sqrt((93*VIX3M^2 - 30*VIX^2)/63) in more than 60% of non-overlapping months.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.cboe.com/tradable_products/vix/faqs/
- statistic: Frequency of VIX_{t+21} < F_t and mean F_t - VIX_{t+21}, conditional on VIX3M/VIX > 1.10. Repeat with the convexity-adjusted proxy F_adj = F*exp(-(VVIX/100)^2*T/2), T = 1/12, because VIX futures trade below sqrt(forward variance). Secondary, model-priced: call-spread P&L with Black-76 on F_adj and VVIX as IV.
- null: Conditional frequency <= 0.60.
- procedure: Daily VIX and VIX3M from 2009-09-18, VVIX; non-overlapping 21d cycles; exact binomial CI and studentized block bootstrap; walk-forward threshold; deflated Sharpe on the model-priced secondary.
- data: CBOE VIX, VIX3M and VVIX (archive). VIX futures settlement history is not in the free set, so F/F_adj are proxies biased above the futures price. · min n: 100
- pass: Lower 95% bound of the frequency > 0.60 on F_adj (not just F), and mean F_adj - VIX_{t+21} > 0 at p < 0.05.
- controls: Unconditional (no contango filter); shuffled term-structure placebo; F (unadjusted) reported to show the size of the convexity bias.
- harness: contango_forward_v2
- result X-f0f50dc7: supported — contango months: VIX 21 days later below F_adj in 141/177 = 80% (95% CI 0.73-0.85, needs lower > 0.60), below unadjusted F in 83%; mean F_adj - VIX(t+21) +2.13, p=0.0005
- result X-fc0a22c8: supported — contango months: VIX 21 days later below F_adj in 141/177 = 80% (95% CI 0.73-0.85, needs lower > 0.60), below unadjusted F in 83%; mean F_adj - VIX(t+21) +2.13, p=0.0005
- note: from the options-library library: VIX futures roll-down harvest via short VIX call spread; harness suggestion: harness_vix_forward_contango (T-238) runs the data part; add F_adj and the Black-76 call-spread pricer (sigma = VVIX/100, T from the VIX monthly calendar). | verifier-corrected restatement of T-238, whose verdict tested the earlier wording and stands

### T-535 · vix_spike_reversion_put

**Claim.** After VIX closes above 30 and above VIX3M, spot VIX 21 trading days later is below the forward-variance-implied level F = sqrt((93*VIX3M^2 - 30*VIX^2)/63) in more than 50% of events, i.e. the curve under-prices mean reversion.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.cboe.com/tradable_products/vix/vix_futures/
- statistic: P(VIX_{t+21} < F_t | VIX_t > 30 and VIX_t > VIX3M_t); also P(VIX_{t+21} < VIX_t) and the same with the convexity-adjusted F_adj = F*exp(-(VVIX/100)^2*T/2), T = 1/12.
- null: P(VIX_{t+21} < F) <= 0.5 (the forward is fair or too low after spikes).
- procedure: Daily VIX and VIX3M from 2009-09-18 (not 2007), VVIX; non-overlapping 21d event entries; exact binomial CI; walk-forward halves. Low event count, so report it explicitly. F sits above the futures price (convexity), which inflates the hit rate; the F_adj run is the decisive one.
- data: CBOE VIX, VIX3M and VVIX (archive). · min n: 20
- pass: P(VIX_{t+21} < F_adj) > 0.5 with the exact 95% CI excluding 0.5; otherwise record 'the forward is fair after spikes' as the finding.
- controls: All-days baseline; VIX > 30 without backwardation; event-count sensitivity to the 30 threshold (25/35).
- harness: spike_forward_v2
- result X-d74fdd76: supported — 23 spike events since 2009-09-18: VIX 21 days later below F_adj in 19/23 (0.61-0.95), below unadjusted F in 83%, below spot in 83%
- result X-5fa20844: supported — 23 spike events since 2009-09-18: VIX 21 days later below F_adj in 19/23 (0.61-0.95), below unadjusted F in 83%, below spot in 83%
- note: from the options-library library: VIX spike mean-reversion via long VIX put / put spread; harness suggestion: harness_vix_spike (T-241) runs this; add F_adj and report the exact event count. | verifier-corrected restatement of T-241, whose verdict tested the earlier wording and stands

## Not Supported (119)

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
- result X-ad24c88b: not_supported — <0.1 bucket at 7d: mean(outcome-price) +0.0208, event-clustered 95% [+0.0022, +0.0510], 9 YES events of 277 markets in 91 events
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
- result X-71e7a200: not_supported — 2 snapshot(s): snapshot: 0 after-fee in 268 markets (0 with YES+NO asks below 1 before fees), median round-trip spread 0.020; 2026-10-15: 0 after-fee in 277 markets (0 with YES+NO asks below 1 before fees), median round-trip spread 0.020
- result X-12f8332a: not_supported — 2 snapshot(s): snapshot: 0 after-fee long bundles in 268 markets (0 with YES+NO asks below 1 before fees; 0 short-side, not counted), median round-trip spread 0.020; 2026-10-15: 0 after-fee long bundles in 277 markets (0 with YES+NO asks below 1 before fees; 0 short-side, not counted), median round-trip spread 0.020
- note: one snapshot so far; the claim needs repeated snapshots (half-life) before parking

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
- result X-0e02429c: not_supported — skill by horizon 1d 0.780, 3d 0.795, 7d 0.743, 30d 0.735, 90d 0.689; strict order fails on n >= 300: skill(1d) <= skill(3d)
- note: automated as harness horizon_monotone (1-point tolerance). Reading 2026-10-14: skill 0.70 (90d), 0.72 (30d), 0.78 (7d), 0.86 (3d), 0.86 (1d): monotone as claimed; the 1d/3d tie is within noise.

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
- result X-983681da: not_supported — naive not_supported (d_fear -0.0006) vs point-in-time not_supported (d_fear +0.0003): no verdict change on this harness; d_fear sign flips (reported only)
- note: harness point_in_time_check runs the Fear & Greed test naive (lag 0) and honest (lag 1) and asks whether the verdict or sign changes; one harness only so far

### T-51 · variance-risk-premium-nasdaq

**Claim.** VXN-implied variance exceeds realised QQQ variance over the following 21 trading days on average.

- kind: volatility · origin: cboe:VXN, options-sweep
- statistic: mean(VXN^2 - RV^2)
- null: implied = realised; block bootstrap
- procedure: as T-48 on QQQ
- data: cboe-VXN-history, daily-history-QQQ · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: VXN is NDX IV applied to QQQ
- harness: vrp_nasdaq
- result X-a052edc2: not_supported — implied 22.6 vs realised 20.6 vol pts over 4275 days (2009-09-14..2026-09-11); VRP positive on 80% of days, block-bootstrap p=0.0950, halves +0.0104/+0.0063
- result X-710ccee8: not_supported — implied 22.6 vs realised 20.6 vol pts over 4276 days (2009-09-14..2026-09-14); VRP positive on 80% of days, block-bootstrap p=0.0935, halves +0.0104/+0.0063

### T-52 · skew-predicts-crashes

**Claim.** When the CBOE SKEW index is in its top quintile, the probability of a 21-day SPY drop worse than -5% is higher than when it is in its bottom quintile.

- kind: volatility · origin: cboe:SKEW, options-sweep
- statistic: difference in crash probability, top minus bottom quintile
- null: SKEW circularly shifted against returns
- procedure: quintiles over the full sample; forward 21d log return; block-shift null; both halves must agree
- data: cboe-SKEW-history, daily-history-SPY · min n: 2000
- pass: difference > 0, p < 0.05, both halves > 0
- controls: quintile edges use the full sample (mild look-ahead on the threshold, none on the signal); overlapping windows via block shift
- harness: skew_tail
- result X-4b59c8db: not_supported — P(21d drop < -5%) top SKEW quintile 0.068 vs bottom 0.123 (diff -0.055, block-shift p=0.880, halves +nan/+0.069)
- result X-3a9fe359: not_supported — P(21d drop < -5%) top SKEW quintile 0.067 vs bottom 0.123 (diff -0.055, block-shift p=0.881, halves +nan/+0.068); failed: difference > 0; block-shift p < 0.05 (not implemented: both halves > 0 (half not testable: <= 20 top- or bottom-quintile days))
- note: literature finds SKEW a weak predictor; this is the test, not the belief

### T-58 · trend-rules-beat-buy-and-hold

**Claim.** A declared grid of six long/flat trend rules (50/100/200-day moving average, 3/6/12-month time-series momentum) beats buy-and-hold after deflation on a majority of SPY, QQQ, GLD, SLV, TLT, IWM, BTC and ETH.

- kind: underlying-strategy · origin: literature:moskowitz-ooi-pedersen-2012, underlying-sweep
- statistic: per asset: best variant's Sharpe vs buy-and-hold, deflated Sharpe over the grid, PBO (CSCV); count of assets passing
- null: zero-skill best-of-48
- procedure: full histories, 5 bps per position change, positions decided at close for the next day
- data: daily-history-* (8 assets) · min n: 1500
- pass: majority of assets with best Sharpe > B&H, block-bootstrap p < 0.05 and DSR > 0.95
- controls: no look-ahead (signal at close t, return t+1); costs; the grid is the trial count; cash earns zero (conservative for the rule)
- harness: trend_rules
- result X-1974bcf3: not_supported — 0/8 assets where the best of 6 trend rules beats buy-and-hold after deflation (median DSR 0.99, median PBO 0.45); SPY: best tsmom126 SR 0.64 vs B&H 0.55, DSR 1.00, PBO 0.20; QQQ: best tsmom126 SR 0.53 vs B&H 0.40, DSR 0.99, PBO 0.43; GLD: best tsmom126 SR 0.65 vs B&H 0.63, DSR 0.99, PBO 0.29; SLV: best tsmom252 SR 0.42 vs B&H 0.39, DSR 0.86, PBO 0.64; TLT: best tsmom63 SR 0.09 vs B&H 0.05, DSR 0.41, PBO 0.53; IWM: best tsmom252 SR 0.39 vs B&H 0.40, DSR 0.94, PBO 0.47; BTC-USD: best ma50 SR 1.48 vs B&H 1.12, DSR 1.00, PBO 0.11; ETH-USD: best ma50 SR 1.02 vs B&H 0.66, DSR 0.99, PBO 0.60
- result X-094704b4: not_supported — 1/8 assets where the best of 6 trend rules beats buy-and-hold on Sharpe (block-bootstrap p < 0.05) with DSR > 0.95 over 48 trials (median DSR 0.43, median PBO 0.38); SPY: best tsmom252 SR 0.74 vs B&H 0.64 (p=0.200), DSR 0.72, PBO 0.36; QQQ: best tsmom126 SR 0.56 vs B&H 0.43 (p=0.189), DSR 0.34, PBO 0.40; GLD: best tsmom126 SR 0.65 vs B&H 0.63 (p=0.415), DSR 0.52, PBO 0.29; SLV: best tsmom252 SR 0.42 vs B&H 0.39 (p=0.415), DSR 0.17, PBO 0.64; TLT: best tsmom63 SR 0.30 vs B&H 0.29 (p=0.453), DSR 0.05, PBO 0.30; IWM: best tsmom252 SR 0.43 vs B&H 0.46 (p=0.587), DSR 0.15, PBO 0.50; BTC-USD: best ma50 SR 1.47 vs B&H 1.11 (p=0.049), DSR 0.99, PBO 0.11; ETH-USD: best ma50 SR 1.02 vs B&H 0.66 (p=0.116), DSR 0.76, PBO 0.60

### T-60 · weekday-effect

**Claim.** Some weekday's SPY close-to-close return differs from the other weekdays' after correcting for having looked at five weekdays.

- kind: underlying-strategy · origin: literature:french-1980, underlying-sweep
- statistic: per weekday mean difference vs rest; smallest Bonferroni-corrected two-sided p
- null: equal means across weekdays
- procedure: block bootstrap per weekday; Bonferroni x5; halves must agree in sign
- data: daily-history-SPY · min n: 3000
- pass: corrected p < 0.05 with halves agreeing
- controls: multiple testing corrected; the classic Monday effect decayed after publication
- harness: weekday_effect
- result X-cd38bf54: not_supported — strongest weekday Fri: -5.1 bps vs rest (Bonferroni p=0.425, halves agree True)
- result X-da0d36f5: not_supported — strongest weekday Mon: +1.3 bps vs rest (Bonferroni p=1.000, halves agree True)

### T-61 · gold-silver-ratio-reverts

**Claim.** When the GLD/SLV log ratio is more than two standard deviations from its 250-day mean it moves back toward the mean over the next 21 trading days.

- kind: underlying-strategy · origin: underlying-sweep
- statistic: mean of -sign(z) x 21-day change in the log ratio on signal days
- null: z series circularly shifted against future changes
- procedure: trailing 250-day z-score; signals |z| > 2; block-shift null; halves agree
- data: daily-history-GLD, daily-history-SLV · min n: 2500
- pass: mean > 0, p < 0.05, both halves > 0, >= 30 signals
- controls: no look-ahead (trailing window); overlapping horizons via block shift; costs not charged (reversion size vs spread to be checked before any trade)
- harness: gold_silver_ratio
- result X-3983c31f: not_supported — 716 signal days (|z|>2.0); mean 21d move back toward the mean -0.0058 log units (block-shift p=0.739, halves -0.0175/+0.0119)
- result X-4e86823c: not_supported — 716 signal days (|z|>2.0); mean 21d move back toward the mean -0.0058 log units (block-shift p=0.739, halves -0.0175/+0.0119); failed: mean > 0; block-shift p < 0.05; both halves > 0

### T-62 · crypto-weekend-effect

**Claim.** BTC's Saturday and Sunday close-to-close returns differ from its weekday returns.

- kind: underlying-strategy · origin: underlying-sweep
- statistic: mean weekend minus weekday daily return (bps), two-sided
- null: equal means; block bootstrap (block 14)
- procedure: 7-day series since 2014; halves agree in sign
- data: daily-history-BTC-USD · min n: 2000
- pass: two-sided p < 0.05 with halves agreeing
- controls: two-sided because the literature disagrees on the sign; weekend volatility ratio reported
- harness: crypto_weekend
- result X-45ddf2f7: not_supported — weekend +12.1 bps/day vs weekday +20.1 (diff -8.0, two-sided block-bootstrap p=0.402, halves -14.1/-1.9); weekend vol is 0.72x weekday vol
- result X-c5c063b9: not_supported — weekend +12.1 bps/day vs weekday +20.0 (diff -7.9, two-sided block-bootstrap p=0.405, halves -14.1/-1.7); weekend vol is 0.72x weekday vol

### T-65 · variance-risk-premium-russell

**Claim.** RVX-implied variance exceeds realised IWM variance over the following 21 trading days on average.

- kind: volatility · origin: cboe:RVX, options-sweep
- statistic: mean(RVX^2 - RV^2)
- null: implied = realised; studentized block bootstrap
- procedure: as T-48
- data: cboe-RVX-history, daily-history-IWM · min n: 2000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: overlapping windows via block bootstrap; index IV applied to the ETF
- harness: vrp_russell
- result X-3f3a7dbe: not_supported — implied 24.9 vs realised 22.2 vol pts over 4268 days (2009-09-16..2026-09-11); VRP positive on 83% of days, block-bootstrap p=0.0950, halves +0.0151/+0.0098
- result X-8aa0cd5f: not_supported — implied 24.9 vs realised 22.2 vol pts over 4269 days (2009-09-16..2026-09-14); VRP positive on 83% of days, block-bootstrap p=0.0945, halves +0.0151/+0.0098

### T-67 · variance-risk-premium-eth

**Claim.** Deribit DVOL(ETH)-implied variance exceeds realised ETH variance over the following 30 days on average.

- kind: volatility · origin: deribit:DVOL, options-sweep
- statistic: mean(DVOL^2 - RV^2), 365-day convention
- null: implied = realised; block bootstrap
- procedure: as T-49 on ETH
- data: deribit-dvol-ETH-history, daily-history-ETH-USD · min n: 1000
- pass: p < 0.05, mean > 0, both halves > 0
- controls: DVOL-ETH history from 2021-03
- harness: vrp_eth
- result X-80732af2: not_supported — implied 77.4 vs realised 74.4 vol pts over 2000 days (2021-03-24..2026-09-13); VRP positive on 64% of days, block-bootstrap p=0.2019, halves +0.1137/-0.0218
- result X-ea153b37: not_supported — implied 77.4 vs realised 74.4 vol pts over 2001 days (2021-03-24..2026-09-14); VRP positive on 64% of days, block-bootstrap p=0.2019, halves +0.1137/-0.0217

### T-100 · long-straddle

**Claim.** A 30-DTE ATM SPY straddle, bought at the model price BS(s*VIX/100) and held to expiry, has negative mean P&L per unit premium over 1993-2026 for every ATM scale s in {0.81, 0.90, 1.00}. MODEL-PRICED proxy.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf
- statistic: mean P&L / premium over non-overlapping 21-trading-day cycles; studentized block-bootstrap 95% CI (block 6 cycles); run separately for each s
- null: mean P&L = 0 (straddle fairly priced at s*VIX)
- procedure: For each cycle start t: S_t from daily-history-SPY, r from fred-DTB3, sigma = s*VIX_t/100, T = 21/252, K = S_t. Price call + put by BS (mandel/options/bs.price), pay |S_{t+21} - K|, P&L = payoff - premium. The existing overlay_backtest(strategy='long_straddle', iv_scale=s) in mandel/experiments/volatility.py already computes this.
- data: daily-history-SPY (1993-01-29 on), cboe-VIX-history (1990 on), fred-DTB3 · min n: 390
- pass: upper CI < 0 for all three s; if the sign holds only at s = 1.00, report 'pricing-artefact, not supported'
- controls: s grid pre-registered; s = 0.81 comes from one capture day and is refit as options-surface captures accumulate. VIX is SPX, not SPY. SPY closes are unadjusted (price return) and q = 0 in pricing, a small bias. No transaction costs (adding them strengthens a negative result). Prior evidence: the mirror short-straddle harness (T-57, short_straddle_model) gave +1.10%/month at s = 1.0 but +0.24%/month at s = 0.81 (p 0.07), so this claim is expected to FAIL at s = 0.81.
- harness: structure_t_100
- result X-ac351508: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): s=0.81 mean -5.9% (95% CI -13.2 to +1.7); s=0.9 mean -15.3% (95% CI -21.9 to -8.4); s=1.0 mean -23.7% (95% CI -29.7 to -17.6) — failed: s=0.81: upper CI < 0
- result X-53693711: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): s=0.81 mean -6.1% (95% CI -12.8 to +3.0); s=0.9 mean -15.4% (95% CI -21.5 to -7.2); s=1.0 mean -23.8% (95% CI -29.3 to -16.5) — failed: s=0.81: upper CI < 0
- note: from the options-library library: Long Straddle; harness suggestion: new module mandel/experiments/options.py with bs_price/bs_greeks and straddle_vrp(spy, vix, tbill); register harness 'straddle_vrp' in HARNESSES in mandel/experiments/run.py with bundles ['spy-daily-closes','cboe-vix-daily','fred-tbill-3m']; verdict via block_bootstrap_pvalue from mandel/validation/backtest_eval.py | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-102 · long-strangle

**Claim.** A 30-DTE SPY long strangle at +/-5% strikes, bought at the smile-scaled VIX model price and held to expiry, has negative mean P&L per unit premium over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-strangle-long-combination, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean P&L/premium, non-overlapping 21-day cycles, studentized block-bootstrap CI; secondary: realised frequency of S_{t+21} inside [K_p, K_c] vs the model's risk-neutral probability
- null: mean P&L = 0
- procedure: Price each leg with mandel/options/bs.price at sigma = VIX_t x r(moneyness). Pay at intrinsic on S_{t+21}. Repeat at flat VIX (reported as the overpriced bound) and with the put ratio scaled by SKEW_t/SKEW_2026-10-14.
- data: daily-history-SPY, cboe-VIX-history, cboe-SKEW-history, fred-DTB3, options-surface-2026-10-14 (smile ratios) · min n: 390
- pass: upper CI < 0 under the smile-scaled model AND under the SKEW-scaled sensitivity
- controls: Width pre-registered at 5% (3% and 8% reported, deflated with n_trials = 3). The smile ratios come from one day: verdict capped at 'proxy' until 60 capture days refit them. Width varies with vol level; also report a delta-rule version.
- harness: structure_t_102
- result X-56e4027b: inconclusive — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -42.4% (95% CI -67.5 to -8.7) — implemented criteria pass; not implemented: SKEW-scaled put sensitivity
- result X-e2acd1d2: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): smile mean -42.4% (95% CI -64.4 to +19.0) — failed: smile: upper CI < 0 (not implemented: SKEW-scaled put sensitivity)
- note: from the options-library library: Long Strangle; harness suggestion: harness 'strangle_vrp' in options.py; parameter width in {3,5,8}% declared up front and fed to deflated_sharpe_ratio(n_trials=3) | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-104 · long-butterfly

**Claim.** A 30-DTE SPY ATM call butterfly with +/-5% wings, bought at the smile-scaled VIX model price and held to expiry, has positive mean P&L per unit debit over 1993-2026: realised 30-day returns land near the money more often than the model's risk-neutral density implies (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-call-butterfly
- statistic: mean P&L/debit with studentized block-bootstrap CI; secondary: realised frequency of |S_{t+21}/S_t - 1| < 2.5% vs the model-implied probability
- null: mean P&L = 0
- procedure: Price three legs with the smile-scaled model (and the ATM-scale grid s in {0.81, 0.90, 1.00} with flat wings as a sensitivity); terminal payoff from daily-history-SPY.
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 (smile ratios) · min n: 390
- pass: lower CI > 0 under the smile-scaled model and at s = 0.90
- controls: Wing width fixed at 5%. Flat VIX is reported only as the optimistic-for-buyer bound. Proxy cap until 60 capture days refit the smile.
- harness: structure_t_104
- result X-6c62e346: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -8.9% (95% CI -15.6 to -1.9); s=0.90 mean +12.1% (95% CI +3.9 to +20.5) — failed: smile: lower CI > 0
- result X-ddb49077: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): smile mean -8.9% (95% CI -16.5 to -2.2); s=0.90 mean +12.1% (95% CI +3.4 to +20.1) — failed: smile: lower CI > 0
- note: from the options-library library: Long Butterfly (call or put); harness suggestion: harness 'butterfly_density' in options.py; same bundles; can reuse a generic multi_leg_payoff(legs, S_T) helper | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-105 · short-butterfly

**Claim.** Mirror of long-butterfly: the 30-DTE +/-5% SPY short call butterfly at the smile-scaled VIX model price has negative mean P&L per unit max loss over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-call-butterfly, https://en.wikipedia.org/wiki/Options_strategy
- statistic: mean P&L/max loss with block-bootstrap CI (sign-flipped long-butterfly series)
- null: mean P&L = 0
- procedure: as long-butterfly, sign flipped
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 · min n: 390
- pass: upper CI < 0
- controls: One harness, two verdicts; the controls are the same as long-butterfly.
- harness: structure_t_105
- result X-71227f64: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean +5.7% (95% CI -0.5 to +11.7) — failed: smile: upper CI < 0
- result X-065c7e94: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; percentile block-bootstrap CIs): smile mean +5.7% (95% CI -0.5 to +11.7) — failed: smile: upper CI < 0
- note: from the options-library library: Short Butterfly (call or put); harness suggestion: same 'butterfly_density' harness emits both signs | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-106 · iron-butterfly

**Claim.** A 30-DTE SPY iron butterfly with +/-5% wings, sold at the smile-scaled VIX model price and held to expiry, has positive mean P&L per unit max loss over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-iron-butterfly
- statistic: mean P&L/max loss with studentized block-bootstrap CI; secondary: max drawdown and Sharpe vs the naked short straddle (paired, compare_strategies)
- null: mean P&L = 0
- procedure: Price four legs with the smile-scaled model; terminal payoff; paired with the short-straddle series on the same dates.
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 · min n: 390
- pass: lower CI > 0 under the smile-scaled model and at ATM scale s = 0.90
- controls: Wing width fixed. Flat VIX is reported as the optimistic bound. The same cost haircut applies. Proxy cap until the smile is refit.
- harness: structure_t_106
- result X-7a424f37: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -9.3% (95% CI -15.9 to -2.3); s=0.90 mean +11.5% (95% CI +3.4 to +19.9) — failed: smile: lower CI > 0
- result X-c1573e0b: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): smile mean -9.3% (95% CI -16.9 to -2.6); s=0.90 mean +11.5% (95% CI +2.9 to +19.5) — failed: smile: lower CI > 0
- note: from the options-library library: Iron Butterfly (short, credit); harness suggestion: harness 'iron_fly_vs_straddle' with compare_strategies | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-107 · reverse-iron-butterfly

**Claim.** A 30-DTE SPY reverse iron butterfly with +/-5% wings, bought at the smile-scaled VIX model price, has negative mean P&L per unit debit over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-iron-butterfly
- statistic: mean P&L/debit with block-bootstrap CI; lowest-VIX-decile mean reported as a secondary
- null: mean P&L = 0
- procedure: sign-flipped iron-fly engine; decile cut on an expanding window
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 · min n: 390
- pass: upper CI < 0 under the smile-scaled model and at s = 0.90
- controls: Flat VIX reported as the pessimistic-for-buyer bound; proxy cap.
- harness: structure_t_107
- result X-ebe24649: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean +6.2% (95% CI -0.1 to +12.1); s=0.90 mean -8.8% (95% CI -14.2 to -3.7) — failed: smile: upper CI < 0
- result X-a20c1cdc: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; percentile block-bootstrap CIs): smile mean +6.2% (95% CI -0.1 to +12.1); s=0.90 mean -8.8% (95% CI -14.2 to -3.7) — failed: smile: upper CI < 0
- note: from the options-library library: Reverse Iron Butterfly (long, debit); harness suggestion: same 'iron_fly_vs_straddle' harness, sign flipped, with decile conditioning | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-109 · iron-condor

**Claim.** A 45-DTE SPY iron condor with short strikes at +/-5% and wings at +/-8%, sold at the smile-scaled VIX model price and held to expiry, has positive mean P&L per unit max loss over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-condor, https://www.cboe.com/tradable_products/vix/
- statistic: mean P&L/max loss over non-overlapping 31-trading-day cycles, studentized block-bootstrap CI; secondary: realised breach frequency vs the model-implied breach probability
- null: mean P&L = 0
- procedure: Price four legs with the smile-scaled model at T = 45/365; settle at S_{t+31}. Sensitivity: term-adjust VIX toward VIX3M (VIX3M history starts 2009-09-18 in the archive, so this covers 2009-2026 only).
- data: daily-history-SPY, cboe-VIX-history, cboe-VIX3M-history, fred-DTB3, options-surface-2026-10-14 · min n: 260
- pass: lower CI > 0 under the smile-scaled model; flat-VIX result reported as the optimistic bound
- controls: Widths fixed. The 30-day VIX vs 45-day tenor mismatch is flagged. Proxy cap until 60 capture days refit the smile (the 2026-10-14 calibration is a low-vol, high-SKEW day).
- harness: structure_t_109
- result X-a5fdc39b: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -3.3% (95% CI -8.4 to +1.7) — failed: smile: lower CI > 0
- result X-85f781ce: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 273 cycles, trial min_n 260; studentized block-bootstrap CIs): smile mean -3.3% (95% CI -9.5 to +1.3) — failed: smile: lower CI > 0
- note: from the options-library library: Iron Condor (short, credit); harness suggestion: harness 'iron_condor_breach' in options.py; implied breach probability from norm_cdf already in backtest_eval.py | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-110 · reverse-iron-condor

**Claim.** Mirror of iron-condor: the 45-DTE SPY reverse iron condor (+/-5% inner, +/-8% outer), bought at the smile-scaled VIX model price, has negative mean P&L per unit debit over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-iron-condor
- statistic: mean P&L/debit with block-bootstrap CI
- null: mean P&L = 0
- procedure: sign-flipped iron condor engine
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 · min n: 260
- pass: upper CI < 0 under the smile-scaled model
- controls: Same as iron condor.
- harness: structure_t_110
- result X-2b560d7e: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -0.3% (95% CI -26.1 to +26.0) — failed: smile: upper CI < 0
- result X-cf21e5db: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 273 cycles, trial min_n 260; percentile block-bootstrap CIs): smile mean -0.3% (95% CI -26.1 to +26.0) — failed: smile: upper CI < 0
- note: from the options-library library: Reverse Iron Condor (long, debit); harness suggestion: same 'iron_condor_breach' harness, sign flipped | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-124 · short-vol-with-wings

**Claim.** A 30-DTE SPY short ATM straddle with +/-10% wings, sold at the smile-scaled VIX model price and held to expiry, has positive mean P&L per unit max loss over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-iron-butterfly, https://www.optionseducation.org/strategies/all-strategies/short-condor
- statistic: mean P&L/max loss with studentized block-bootstrap CI; secondary: paired Sharpe and max drawdown vs the naked short straddle (compare_strategies)
- null: mean P&L = 0
- procedure: Short straddle at s*VIX (s grid), wings at VIX x r(0.90) and VIX x r(1.10) (r(1.10) extrapolated, flagged); settle at S_{t+21}; wing-price multipliers 1.5 and 2.0 as SKEW-range sensitivities
- data: daily-history-SPY, cboe-VIX-history, cboe-SKEW-history, fred-DTB3, options-surface-2026-10-14 · min n: 390
- pass: lower CI > 0 under the smile-scaled model AND under the 1.5x wing multiplier
- controls: Flat VIX reported as the upper bound; proxy cap until the smile is refit; costs haircut.
- harness: structure_t_124
- result X-03436e65: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): smile mean -4.4% (95% CI -8.7 to -0.5); wings x1.5 mean -8.9% (95% CI -13.2 to -4.8) — failed: smile: lower CI > 0; wings x1.5: lower CI > 0
- result X-804b88ef: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 390; studentized block-bootstrap CIs): smile mean -4.4% (95% CI -9.5 to -0.6); wing prices x1.5 mean -7.7% (95% CI -13.1 to -3.5); wing prices x2.0 (sensitivity, not in the pass rule) mean -10.4% (95% CI -16.1 to -6.0) — failed: smile: lower CI > 0; wing prices x1.5: lower CI > 0
- note: from the options-library library: Short Vol with Wings (tail-protected short straddle/strangle); harness suggestion: harness 'winged_short_vol' built on compare_strategies with wing-price multiplier sensitivity; later re-run on chain capture when available | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-125 · long-call

**Claim.** A 1-month ATM SPY call priced by Black-Scholes at VIX IV (model-priced, flat smile) and held to expiry has a negative mean monthly return on premium over 1993-2026, and this still holds when IV is scaled down to 0.9 x VIX.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/long-call, https://scholarsarchive.byu.edu/facpub/9281
- statistic: mean monthly return on premium, (payoff - C)/C, with studentized block bootstrap 95% CI, at iv_scale 1.0 and 0.9
- null: mean return >= 0 at either iv_scale
- procedure: non-overlapping 21-trading-day cycles; K = spot; price BS call with sigma = iv_scale*VIX/100, r = FRED DTB3, q = constant assumption (SPY dividends are not in the free data list; run q = 0 and q = 1.8%); payoff from the SPY close at cycle end; about 400 returns
- data: SPY daily closes, CBOE VIX daily, FRED DTB3 · min n: 300
- pass: upper CI bound < 0 at both iv_scale 1.0 and 0.9
- controls: VIX exceeds 30-day ATM IV on average (it integrates the OTM put wing), so pricing ATM at VIX overprices the call and biases the result toward a pass; the 0.9 x VIX run is the guard. Compare with chain mids once capture reaches 60 days. DSR with n_trials = number of family strategies tested.
- harness: structure_t_125
- result X-1d7ea485: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): s=1.0 mean -7.7% (95% CI -16.9 to +1.3); s=0.9 mean +2.3% (95% CI -7.9 to +12.3) — failed: s=1.0: upper CI < 0; s=0.9: upper CI < 0
- result X-aeb3c086: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; studentized block-bootstrap CIs): s=1.0 q=0.0% mean -10.5% (95% CI -19.3 to -1.6); s=0.9 q=0.0% mean -1.2% (95% CI -10.7 to +8.7); s=1.0 q=1.8% mean -7.1% (95% CI -16.2 to +2.3); s=0.9 q=1.8% mean +3.0% (95% CI -7.0 to +13.5) — failed: s=0.9 q=0.0%: upper CI < 0; s=1.0 q=1.8%: upper CI < 0; s=0.9 q=1.8%: upper CI < 0
- note: from the options-library library: Long Call; harness suggestion: vix_priced_option_returns(strategy='long_call', dte=30, strike='ATM') in mandel/experiments/options.py; reuse block_bootstrap_pvalue and deflated_sharpe_ratio | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-127 · short-naked-call

**Claim.** Selling a 1-month 5%-OTM SPY call at VIX IV (model-priced), rolled monthly, has a positive mean P&L but a lower Sharpe ratio than the matching 5%-OTM short put over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/naked-call-uncovered-call-short-call, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Sharpe of monthly P&L per unit spot for the short call vs the short put; difference with block bootstrap
- null: Sharpe(short call) >= Sharpe(short put)
- procedure: price both legs at VIX IV each cycle, payoff from the SPY close, P&L normalised by spot
- data: SPY, VIX, DTB3 · min n: 300
- pass: bootstrap p < 0.05 for Sharpe(call) < Sharpe(put), and the call mean's lower CI > 0
- controls: Flat IV overprices the OTM call relative to the real smile (optimistic for the call) and underprices the 5%-OTM put (conservative for the put), so the bias favours the null: a pass is robust. Recheck with chain mids after 60 days.
- harness: structure_t_127
- result X-7cde2127: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): Sharpe put minus call -0.59 (one-sided 95% lower -1.33); short call mean +0.4% (95% CI +0.3 to +0.5) — failed: Sharpe(put) > Sharpe(call), one-sided p < 0.05
- result X-1157681c: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): Sharpe put minus call -0.59 (one-sided 95% lower -1.33); short call mean +0.4% (95% CI +0.3 to +0.5) — failed: Sharpe(put) > Sharpe(call), one-sided p < 0.05
- note: from the options-library library: Short (Naked) Call; harness suggestion: vix_priced_option_returns(strategy='short_call', dte=30, strike='OTM5') compared to short_put | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-129 · bull-call-spread

**Claim.** A 1-month ATM/+5% SPY bull call spread priced at VIX IV (model-priced) has a negative mean return per dollar of debit over 1993-2026, but less negative than the plain ATM long call.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/bull-call-spread-debit-call-spread, https://cdn.cboe.com/resources/options/Trading_Strategies.pdf
- statistic: mean return on debit for the spread and for the long call, each with block bootstrap CI, plus the paired difference
- null: spread mean >= 0, or spread mean <= call mean
- procedure: monthly cycles; price both strikes at VIX IV (and 0.9 x VIX); payoff from the SPY close; compute (payoff - D)/D
- data: SPY, VIX, DTB3 · min n: 300
- pass: spread upper CI < 0 and paired (spread - call) lower CI > 0
- controls: Correction: flat VIX overprices both C(K1) (VIX > ATM IV) and C(K2) (OTM call IV < ATM IV), so the sign of the bias on D is indeterminate and must be measured against chain mids at 60 days. Report the iv_scale sensitivity.
- harness: structure_t_129
- result X-856f5dfa: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): bull call spread mean +13.2% (95% CI +2.2 to +23.7); spread - long call mean +20.9% (95% CI +17.5 to +24.7) — failed: bull call spread: upper CI < 0
- result X-86dc6336: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): bull call spread mean +13.2% (95% CI +2.2 to +23.7); spread - long call mean +20.9% (95% CI +17.5 to +24.7) — failed: bull call spread: upper CI < 0
- note: from the options-library library: Bull Call Spread (Debit); harness suggestion: vix_priced_option_returns(strategy='bull_call_spread', dte=30, strikes=('ATM','OTM5')) | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-132 · bear-call-credit-spread

**Claim.** A 1-month 3%/6%-OTM SPY bear call spread priced at VIX IV (model-priced) has a mean P&L per unit of max loss that is not positive over 1993-2026 (equity drift exceeds the flat-IV call premium).

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/bear-call-spread-credit-call-spread
- statistic: mean P&L / max loss with block bootstrap CI
- null: mean > 0
- procedure: monthly cycles; K1 = 1.03S, K2 = 1.06S at VIX IV; payoff from the SPY close
- data: SPY, VIX, DTB3 · min n: 300
- pass: upper CI <= 0
- controls: Correction: flat IV overprices both OTM calls relative to the real smile; the sign of the bias on the net credit is indeterminate (depends on the smile slope between K1 and K2), so do not assume the real result is more negative. Compare with the bull put spread in the same months and with chain mids at 60 days.
- harness: structure_t_132
- result X-591cc927: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): bear call spread mean +3.9% (95% CI +0.7 to +7.1) — failed: upper CI <= 0
- result X-bdb9f113: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): bear call spread mean +3.9% (95% CI +0.7 to +7.1) — failed: bear call spread: upper CI <= 0
- note: from the options-library library: Bear Call Spread (Credit); harness suggestion: vix_priced_option_returns(strategy='bear_call_spread', dte=30, strikes=('OTM3','OTM6')) | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-134 · backspread-1x2

**Claim.** A 1-month 1x2 SPY put backspread (short 1 ATM put, long 2 delta -0.25 puts, priced at VIX IV; model-priced) has a negative mean P&L overall but a positive mean P&L in months entered with VIX below 15, over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/long-ratio-put-spread
- statistic: mean P&L per unit spot, overall and conditional on VIX < 15 at entry, with block bootstrap CIs
- null: conditional mean <= 0
- procedure: monthly cycles; solve the delta -0.25 strike at VIX IV; payoff from the SPY close; split by entry VIX
- data: SPY, VIX, DTB3 · min n: 300
- pass: overall upper CI < 0 AND conditional (VIX < 15) lower CI > 0
- controls: The threshold of 15 is fixed before looking; report the number of low-VIX months (about 1/3 of the sample). Flat IV underprices the 25-delta puts relative to skew, which flatters the long wings: state this. With fixed 5% wings the position is short gamma at VIX < 15, which is why the strike rule is delta-based.
- harness: structure_t_134
- result X-19107292: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape): all months mean +0.1% (95% CI -0.1 to +0.3); VIX<15 (n=140) mean -0.0% (95% CI -0.1 to +0.1) — failed: all months: upper CI < 0; VIX<15 (n=140): lower CI > 0
- result X-30692d85: not_supported — MODEL-PRICED proxy (smile from 2 quote days, held fixed in shape; 403 cycles, trial min_n 300; percentile block-bootstrap CIs): all months mean +0.1% (95% CI -0.1 to +0.3); VIX<15 (n=140) mean -0.0% (95% CI -0.1 to +0.1) — failed: all months: upper CI < 0; VIX<15 (n=140): lower CI > 0
- note: from the options-library library: Backspread (1x2 Long Ratio: Call or Put); harness suggestion: vix_priced_option_returns(strategy='put_backspread_1x2', dte=30, condition='vix<15') | verifier: corrected claim/trial | tested with the model-priced structure engine; the smile shape comes from the captured SPY quote days (2 on 2026-10-15) and is held fixed through history, so verdicts are re-run as the capture grows

### T-160 · vix-futures-calendar

**Claim.** The VX M1-M2 calendar (short M1 / long M2), held only while VIX/VIX3M < 1 and flattened otherwise, has positive mean daily P&L after $2/contract/leg roll costs since 2013.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.cboe.com/tradable_products/vix/vix_futures/, https://www.cboe.com/tradable_products/vix/vix_futures/specifications/
- statistic: Mean daily P&L of the gated spread (points times $1,000); Sharpe and 1% CVaR reported alongside
- null: Zero mean (studentized block bootstrap of daily spread changes, block 21), with a block-shifted regime label as a placebo
- procedure: Build continuous M1/M2 series from per-contract CBOE VX settlement files with Wednesday rolls; apply the VIX/VIX3M gate. Studentized block bootstrap; walk-forward halves; costs per roll.
- data: CBOE VX per-contract daily history CSVs (free: cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_<expiry>.csv; verified for 2013-01-16 and 2026-11-18 expiries, while a 2008-01-16 file returned 403, so pre-2013 needs another source), plus VIX and VIX3M · min n: 2500
- pass: Mean > 0 with the CI excluding 0 in both halves after costs
- controls: Margin outlay as capital. Roll-date convention. Report with and without Feb 2018 and Mar 2020. Some rows have Settle = 0 (e.g. the 2013 file) and must be filtered. The VIX3M - VIX slope serves as a free cross-check of the basis.
- harness: vx_calendar_gated
- result X-c5827bb7: not_supported — VX M1-M2 calendar (short M1 / long M2, $1,000/pt) on CBOE daily settlements 2013-05-22..2026-10-14, n=3373 daily intervals (2013 rows with Settle = 0 dropped, so the first settlement is 2013-05-20; 0 intervals bridged a missing settle, booking $0 absolute held P&L and $0 absolute spread move across gaps, 0 trades deferred, 0 stale closes); held on 93% of days under the point-in-time gate (VIX/VIX3M < 1 at the previous close); costs $2/contract/leg on every leg traded (149 rolls at $8, 167 gate entries/exits at $4, total $1,860). Mean net $3.9/day, 95% CI [-$9.8, $16.8] (n >= 2500: True); first half mean -$7.6, CI [-$29.0, $10.8]; second half mean $15.3, CI [-$3.0, $33.3] (each needs mean > 0 and lower > 0). Sharpe 0.17 (x sqrt 252), 1% CVaR -$1,844/day (-$1,878 on held days), max drawdown -$27,981; without 2018-02/2020-03: mean $5.7, CI [-$7.5, $18.5]; ungated always-on mean $12.9; lag-0 gate (15-min look-ahead) mean $7.2, halves CI [-$21.6, $14.2] and [-$0.3, $34.5]; block-shifted gate placebo: 100% of 155 shifts reach the actual gross mean $4.4; basis cross-check corr(M2 - M1, VIX3M - VIX) = 0.87. Margin outlay is not archived (the statistic is dollars per spread) — failed: first half 2013-05-22..2020-01-29: mean > 0 and studentized block-21 95% CI excludes 0; second half 2020-01-30..2026-10-14: mean > 0 and studentized block-21 95% CI excludes 0
- note: from the options-library library: VIX futures / VIX options calendar (term-structure roll trade); harness suggestion: Add a cboe_vx_settlements ingest (per-contract daily settlement CSVs) and a continuous-contract builder; then vx_calendar_backtest with the regime gate; register as a theory blocked on ingest. | verifier: corrected claim/trial

### T-176 · deribit-covered-call-inverse

**Claim.** In a model-priced monthly roll from 2021-04 to 2026-10 (premium = Black-76 at DVOL, not traded marks; settlement at Deribit delivery prices; 0.0003 BTC fee per side), writing a 25-delta 30-day BTC call against 1 BTC has a positive mean BTC-denominated P&L.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name=BTC-27NOV26-120000-C
- statistic: Mean monthly BTC-denominated overlay P&L = c - max(S_T - K, 0)/S_T - fees (model-priced)
- null: Mean <= 0
- procedure: Monthly roll on the last-Friday cycle; strike = 25-delta at DVOL; settle with public/get_delivery_prices; block bootstrap by month; a skew adjustment from today's book is a sensitivity only
- data: DVOL 2021-03-24 onward (paged, 2,031 rows), BTC closes (archived), Deribit delivery prices (2,638 daily records) · min n: 60
- pass: Bootstrap 95% CI of the mean > 0
- controls: ATM strike vs 25-delta; fee at 2x; USD-terms annual return vs BTC buy-and-hold reported descriptively
- harness: btc_inverse_covered_call
- result X-7bb88d2c: not_supported — MODEL-PRICED at flat DVOL: 25-delta 30-day BTC call against 1 BTC earns +0.0058 BTC per cycle on average over 67 cycles (95% CI -0.0052 to +0.0162); spot closes stand in for Deribit delivery prices — failed: 95% CI of the mean > 0
- note: from the options-library library: Deribit covered call on BTC/ETH inventory (inverse options); harness suggestion: Mandel's deribit_book + DVOL fetchers already exist; add public/get_delivery_prices (free, 2,638 daily records) so expiries settle at the official TWAP rather than a close. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states; spot closes stand in for Deribit delivery prices (30-minute TWAP)

### T-177 · covered-call-metals

**Claim.** From 2009-09 to 2026-10, Cboe GVZ exceeds the subsequent 21-trading-day realised volatility of GLD daily closes by at least 2 vol points on average.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.kgieworld.sg/futures/cme-comex-gold-contractspecs, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write
- statistic: Mean of (GVZ_t - RV_GLD,{t, t+21}), RV annualised with 252 days
- null: Mean < 2 vol points
- procedure: Cboe GVZ history (the free CSV starts 2009-09-18) vs realised vol from archived GLD closes; HAC (lag 21) or stationary block bootstrap; walk-forward halves; report the SPX VRP (VIX vs SPY RV) on the same dates for scale
- data: GVZ 2009-09 onward, GLD daily closes (archived daily-history-GLD, 2004-11 onward), VIX, SPY · min n: 400
- pass: Lower 95% CI of the mean > 2 vol points, with the same sign in both halves
- controls: Exclude 2011 and 2020 spikes one at a time; OVX/USO as another commodity reference
- harness: gvz_gap_2pts
- result X-b7862591: not_supported — GVZ/GLD implied minus realised over 21 periods: +2.3535 vol pts since 2009-09-18 (95% CI +1.7626 to +2.9158), halves +2.8537/+1.8533 — failed: lower 95% CI > 2.0
- note: from the options-library library: Covered call on gold/silver (GLD/SLV equity route; GC/SI futures-options route); harness suggestion: GVZ history is already fetched; add GLD/SLV daily closes (free) and reuse the VRP harness; GC futures closes are not free - use GLD as the proxy. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-181 · put-call-parity-synthetic-forward

**Claim.** On CBOE delayed SPY/SPX chains, option-implied forwards from ATM +/-5 strikes deviate from S*e^{rT} - FV(D) by more than half the combined call+put bid-ask spread in fewer than 2% of (K,T) pairs, so there is no exploitable parity edge in liquid ETF/index options and the implied financing rate sits within 50 bp of the FRED 3-month bill.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://docs.deribit.com/api-reference/market-data/public-ticker
- statistic: Fraction of (K,T) pairs with |F_impl - F_theo| > 0.5*(spread_call + spread_put); and median (r_impl - r_bill).
- null: Deviations are inside the half-spread noise band (exploitable fraction = 0, median rate gap = 0 +/- 50 bp).
- procedure: Each day: pull SPY and SPX chains, FRED 3m bill, SPY dividend schedule; for each expiry take ATM +/-5 strikes; compute F_impl from mids and r_impl per expiry; count violations; block-bootstrap the daily violation rate as capture accumulates.
- data: CBOE delayed chains (SPY, SPX), FRED DGS3MO, SPY ex-div calendar (Mar/Jun/Sep/Dec third Friday). · min n: 200
- pass: Violation fraction < 2% and |median r_impl - r_bill| < 50 bp on day one; stable over 20 captured days.
- controls: Exclude strikes with zero bid; use mids not lasts; re-run with quotes aged < 15 min; placebo: shuffle puts across adjacent strikes to confirm the statistic detects artificial violations.
- harness: parity_forward
- result X-adaf1657: not_supported — SPY 2026-10-14: 3.8% of 320 pairs outside half-spread, implied rate -693 bp vs bill; SPX 2026-10-14: 3.1% of 540 pairs outside half-spread, implied rate +91 bp vs bill (claim: < 2% and within 50 bp, stable over 20 days); the implied rate from ten strikes is noise-dominated for SPY's $1 strikes, so the violation rate is the reliable half
- result X-ddf2141f: not_supported — SPY 2026-10-14: 3.8% of 320 pairs outside half-spread, implied rate -693 bp vs bill; SPY 2026-10-15: 0.3% of 320 pairs outside half-spread, implied rate -568 bp vs bill; SPX 2026-10-14: 3.1% of 540 pairs outside half-spread, implied rate +91 bp vs bill; SPX 2026-10-15: 1.3% of 520 pairs outside half-spread, implied rate +82 bp vs bill (claim: < 2% and within 50 bp, stable over 20 days); the implied rate from ten strikes is noise-dominated for SPY's $1 strikes, so the violation rate is the reliable half
- result X-1dfce7cb: not_supported — SPY 2026-10-14: implied rate -712 bp vs bill, 3.8% of 320 pairs off a free cross-strike fit by more than the half-spread; SPY 2026-10-15: implied rate -587 bp vs bill, 0.3% of 320 pairs off a free cross-strike fit by more than the half-spread; SPX 2026-10-14: implied rate +72 bp vs bill, 3.1% of 540 pairs off a free cross-strike fit by more than the half-spread; SPX 2026-10-15: implied rate +63 bp vs bill, 1.3% of 520 pairs off a free cross-strike fit by more than the half-spread (claim: within 50 bp and < 2% violations against F_theo on day one, stable over 20 days); the free-fit violation rate is a diagnostic, not the claim's F_theo statistic; the implied rate from ten strikes is noise-dominated for SPY's $1 strikes; verdict: failed: day one: |median r_impl - r_bill| < 50 bp for every symbol (SPX 2026-10-14, SPY 2026-10-14); stable over the first 20 captured days: rate gap within 50 bp on every one of them (not implemented: violation fraction |F_impl - F_theo| > half-spread < 2%, F_theo = S e^{rT} - FV(D) (needs a dividend schedule the inputs do not carry))
- note: from the options-library library: Put-call parity scan / synthetic forward; harness suggestion: mandel/options/parity.py: implied_forward(chain, r, divs) -> per-(K,T) table; wire into payoff engine as a 2-leg template; daily job appends to data/options/parity/. | market-priced from the daily raw CBOE chains (local disk on the capturing machine); one day can falsify, confirmation needs 20 capture days | superseded by T-505 (verifier-corrected wording)

### T-186 · long-box-spread-lend

**Claim.** The SPX box-implied lending rate for 3-12 month maturities, computed from executable prices (pay the half-spread on all four legs), exceeds the matched-maturity FRED Treasury bill rate by 15-80 bp on at least 80% of trading days, i.e. SPX boxes are a positive-carry substitute for bills.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Box_spread, https://www.nber.org/papers/w26138
- statistic: Median (r_box - r_bill) across boxes per day; share of boxes with positive net spread.
- null: r_box - r_bill <= 0 after spreads (no convenience-yield premium).
- procedure: Each day: build boxes at every SPX expiry with 90 <= DTE <= 365 using strikes +/- 15% around spot; r_box = ln((K2-K1)/debit_exec)/T; interpolate FRED bill to the same maturity; record spread; block-bootstrap the daily median as capture accumulates.
- data: CBOE delayed SPX chain (29,918 contracts today), FRED DGS1MO/DGS3MO/DGS6MO/DGS1. · min n: 20
- pass: Day-one median spread in [15, 80] bp with >= 80% of boxes positive; maintained over 20 captured days.
- controls: Use mid and executable prices; drop legs with zero bid; compare to SPXW vs SPX AM-settled to check settlement effects; check that r_box is strike-invariant (if not, parity noise dominates).
- harness: spx_box_lending
- result X-a110b91c: not_supported — 1 capture day(s); latest 2026-10-14: 1680 boxes, executable lending spread over bills median -5 bp (mid +69 bp), 45% positive; claim needs [15, 80] bp and 80% positive on 80% of 20+ days
- result X-b8a1631b: not_supported — 2 capture day(s); latest 2026-10-15: 1680 boxes, executable lending spread over bills median -39 bp (mid +69 bp), 18% positive; claim needs [15, 80] bp and 80% positive on 80% of 20+ days
- result X-0faed075: not_supported — 2 capture day(s); day one 2026-10-14: executable spread median -20 bp (fail); latest 2026-10-15: 1680 boxes, executable lending spread over bills median -53 bp (mid +54 bp), 7% positive; claim needs [15, 80] bp and 80% positive on day one and on 80% of 20+ days; verdict: failed: day one (2026-10-14): median executable spread in [15, 80] bp with >= 80% of boxes positive (not implemented: maintained on >= 80% of >= 20 captured days (2 so far))
- note: from the options-library library: Long box spread (SPX box lending); harness suggestion: mandel/options/box.py: box_rate(chain, expiry, K1, K2) and daily box_curve; payoff engine test asserts flat K2-K1. | market-priced from the daily raw CBOE chains (local disk on the capturing machine); one day can falsify, confirmation needs 20 capture days | superseded by T-503 (verifier-corrected wording)

### T-187 · short-box-spread-borrow

**Claim.** The executable SPX short-box borrowing rate for 6-24 month maturities is at least 100 bp below a benchmark retail margin rate of (3-month bill + 150 bp) on at least 80% of trading days, so portfolio-margin accounts can refinance margin loans via boxes.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Box_spread, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: r_box_borrow (hit bids / lift offers on four legs) minus (r_bill + 150 bp).
- null: r_box_borrow >= r_bill + 50 bp (no advantage over margin loans).
- procedure: Daily over SPX expiries with 180 <= DTE <= 730: build wide boxes, compute executable borrowing rate, compare to bill + 150 bp; also record the mid-based rate.
- data: CBOE delayed SPX chain; FRED DGS6MO/DGS1/DGS2. · min n: 10
- pass: Median advantage > 100 bp on day one and on >= 80% of captured days.
- controls: Check strike-invariance; drop expiries with zero-bid legs; compare SPX vs XSP implied rates (should match).
- harness: spx_box_borrowing
- result X-8a3bbd3c: not_supported — 1 capture day(s); latest 2026-10-14: 1440 boxes, borrowing via short box beats bill+150 bp by a median -4 bp (claim: > 100 bp on 80% of 20+ days)
- result X-fb00bd60: not_supported — 2 capture day(s); latest 2026-10-15: 1440 boxes, borrowing via short box beats bill+150 bp by a median -27 bp (claim: > 100 bp on 80% of 20+ days)
- result X-e9a80339: not_supported — 2 capture day(s); day one 2026-10-14: median advantage +15 bp; latest 2026-10-15: 1440 boxes, borrowing via short box beats bill+150 bp by a median -8 bp (claim: > 100 bp on day one and on 80% of days, 10+ days to confirm); verdict: failed: day one (2026-10-14): median advantage over bill + 150 bp > 100 bp (not implemented: advantage > 100 bp on >= 80% of >= 10 captured days (2 so far))
- note: from the options-library library: Short box spread (SPX box borrowing); harness suggestion: box.py with side='short' using executable prices; report borrow curve. | market-priced from the daily raw CBOE chains (local disk on the capturing machine); one day can falsify, confirmation needs 20 capture days | superseded by T-506 (verifier-corrected wording)

### T-192 · pin-risk-expiration-pinning

**Claim.** On SPY option-expiration days (monthly third Fridays and weeklies), the closing price is closer to the nearest $1 strike than on non-expiration days: the mean distance of SPY's close to the nearest integer is at least 10% smaller on expiration days than on other days (uniform expectation 0.25).

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: Mean |close - nearest integer| on expiration days vs non-expiration days; bootstrap difference.
- null: No difference (distance ~ uniform on [0, 0.5], mean 0.25 both groups).
- procedure: SPY daily closes since 2005 (when $1 strikes and weeklies became available), flag third Fridays (and Mon/Wed/Fri weeklies from 2016); compute distance to nearest integer; studentized block bootstrap of the difference; walk-forward by year.
- data: SPY daily closes (available), expiration calendar (deterministic). · min n: 200
- pass: Expiration-day mean distance at least 10% below non-expiration mean with bootstrap p < 0.05, and the effect present in the majority of years.
- controls: Placebo days (Thursdays); scale test with $0.50 strikes post-2020; repeat for QQQ and single names with $5 strikes where the effect should be larger.
- harness: opex_pinning
- result X-0e2b4775: not_supported — SPY close's distance to the nearest $1 on 255 monthly opex days 0.255 vs 0.249 on other days (ratio 1.03, need <= 0.90; p=0.765); lower in 9/22 years
- result X-89d6979d: not_supported — SPY close's distance to the nearest $1 on 255 monthly opex days 0.255 vs 0.249 on other days (ratio 1.03, need <= 0.90; p=0.755); lower in 9/22 years
- note: from the options-library library: Expiration pin risk management and pinning trade; harness suggestion: mandel/experiments/pinning.py on SPY closes; later join captured OI to test OI-weighted pins. | harness tests monthly third-Friday opex only; SPY has expired every trading day since 2022, so 'weekly expiration days' no longer have a non-expiry comparison group | superseded by T-502 (verifier-corrected wording)

### T-198 · perp-funding-vs-synthetic-carry

**Claim.** Over non-overlapping 90-day windows since 2020, cumulative BTC-PERPETUAL funding received by a short perp exceeds the annualised basis of the front quarterly future paid at window start (pro-rated to 90 days) in at least 50% of windows.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://docs.deribit.com/api-reference/market-data/public-ticker, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Share of windows with funding_90d - basis_90d > 0; mean difference with block-bootstrap CI.
- null: Share < 50% (the dated basis prices funding fully or over-prices it).
- procedure: Funding: sum interest_1h per window from get_funding_rate_history; basis: front-quarterly close / spot at window start from get_tradingview_chart_data (expired instruments available); compute differences; bootstrap; walk-forward by year.
- data: Deribit public API funding history and expired-futures chart data (both verified reachable), BTC daily closes. · min n: 24
- pass: Share >= 50% with the mean difference's 95% CI excluding 0 from below.
- controls: ETH replication; drop top 1% funding prints; account for taker fees on four legs; options-synthetic version tested separately on captured chains.
- harness: carry_perp_funding_vs_quarterly
- result X-e906b9f3: not_supported — 27 non-overlapping 90-day windows from 2020-01-01 (front quarterly with >= 7 days to expiry, F and Deribit index both at 08:00 UTC): funding_90d > basis_90d in 15/27 = 56% (need >= 50%); mean funding_90d +1.75 pp, mean basis_90d +1.63 pp, mean difference +0.12 pp, 95% block-bootstrap CI [-0.70, +0.93] pp (need lower > 0) — failed: mean difference's 95% block-bootstrap CI above 0
- note: from the options-library library: Perpetual funding vs dated-future/option-synthetic carry; harness suggestion: mandel/ingest deribit funding history -> mandel/experiments/perp_funding_carry.py with block bootstrap. | verifier: corrected claim/trial

### T-208 · implied-vs-realised-move-filter

**Claim.** Across scheduled FOMC days since 1994, the ratio IM/HM (IM = 0.845*VIX-as-IV one-day straddle/S, HM = median |SPY return| over the prior 8 FOMC days) is negatively rank-correlated with the subsequent model-priced long-straddle P&L.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://www.cboe.com/tradable_products/vix/vix_options/specifications/
- statistic: Spearman rho between IM/HM and the model-priced long-straddle return; Q5-Q1 quintile mean difference with bootstrap CI.
- null: rho >= 0.
- procedure: For each FOMC event: straddle priced by Black-Scholes with sigma = VIX_{T-1}, T=1/252 on SPY_{T-1} (MODEL-PRICED, not traded prices); realised P&L = |SPY_T - SPY_{T-1}| - straddle; HM from prior 8 FOMC-day moves. Walk-forward: cutoffs on 1994-2009, test 2010-2026. Traded-price version for earnings later from chains.
- data: Now: SPY daily closes since 1993, VIX daily since 1990, FOMC dates (Fed calendars). Later: chain captures + earnings dates. · min n: 200
- pass: rho < -0.1 with p < 0.05 out-of-sample and Q1-Q5 > 0 with CI excluding 0.
- controls: Placebo on random non-event days; partial out VIX level; close-to-close vs close-to-open realised definitions (open requires OHLC, not in the current data list).
- harness: macro_fomc_im_hm_filter
- result X-65240d9f: not_supported — MODEL-PRICED long 1-day ATM SPY straddle (BS, sigma=VIX(T-1), T=1/252) on 253 scheduled FOMC days 1995-02-01..2026-09-16; OOS 2010+ (133 events): Spearman rho(IM/HM, long P&L) -0.030 (permutation p=0.3621); Q1-Q5 with 1994-2009 cutoffs +5.3 bps of spot (95% CI -28.3 to +40.1; Q1 n=30, Q5 n=41); in-sample rho +0.085, VIX-partialled OOS rho -0.041, return-on-debit OOS rho -0.024, close-to-open OOS rho -0.096, random-day placebo mean rho +0.039 — failed: OOS Spearman rho < -0.1; OOS one-sided permutation p < 0.05; OOS Q1-Q5 95% CI excludes 0
- note: from the options-library library: Implied-move vs realised-move signal (conditional straddle, sign chosen by IM/HM); harness suggestion: Build an 'event-move table' harness (event_type, date, IM, HM, realised) as the shared dataset for the whole family; VIX-as-IV SPX FOMC version first. | verifier: corrected claim/trial

### T-214 · spx-macro-event-straddle

**Claim.** On scheduled FOMC decision days since 1994, a 1-day ATM SPY straddle model-priced with VIX-as-IV (sigma = VIX at the T-1 close, T = 1/252) and sold at the T-1 close has a lower mean P&L than the same model-priced straddle sold on non-FOMC days, i.e. the 30-day VIX does not embed the FOMC-day event variance.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable-products/0dte
- statistic: Difference in mean P&L (FOMC minus non-FOMC) of the MODEL-PRICED short straddle (BS, sigma=VIX_{T-1}, T=1/252, settled on |SPY_T - SPY_{T-1}|), bootstrap CI; also mean of |r_T|/(VIX_{T-1}/sqrt(252)) by group.
- null: FOMC-day mean P&L >= non-FOMC mean P&L.
- procedure: FOMC decision dates 1994-2026 (about 260, from Fed calendars, hardcoded); price and settle each day; compare with all non-FOMC days; stratify by VIX tercile; estimate on 1994-2010, confirm on 2011-2026. This is a proxy: traded event-expiry straddles carry an event premium that VIX-as-IV cannot see; the traded version needs SPXW chain capture.
- data: SPY daily closes since 1993, VIX daily since 1990, FOMC dates. · min n: 200
- pass: Difference < 0 with 95% CI excluding 0 in both halves.
- controls: Placebo dates (FOMC +/- 7 days); exclude 2008-09 and 2020-03; trailing ratio of 1-day to 30-day realised vol as a scale check.
- harness: fomc_spx_event_straddle
- result X-38efc61c: not_supported — MODEL-PRICED short 1-day ATM SPY straddle (BS, sigma=VIX(T-1), T=1/252): FOMC minus non-FOMC mean P&L -6.2 bps of spot over 261 FOMC / 7980 other days; 1994-2010 -0.9 bps (95% CI -14.0 to +12.2, 136 FOMC days); 2011-2026 -12.0 bps (95% CI -24.4 to -0.4, 125 FOMC days); |r|/(VIX/sqrt252) FOMC 0.67 vs other 0.61; placebo +/-7d +3.1 bps; ex Sep-2008/Mar-2020 -6.8 bps — failed: 1994-2010 FOMC-minus-non-FOMC short-straddle P&L < 0 with 95% CI excluding 0
- note: from the options-library library: SPX macro-event straddle (FOMC / CPI / NFP): event vol vs realised; harness suggestion: VIX-as-IV straddle pricer over an event-date list; run the identical code for CPI and NFP dates once BLS release calendars are loaded (also free). | verifier: corrected claim/trial

### T-215 · pre-fomc-drift-call-spread

**Claim.** SPY's close(T-1)-to-close(T) return on scheduled FOMC decision days exceeds its mean close-to-close return on non-FOMC days over the out-of-sample period 2012-2026.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean return difference (FOMC minus non-FOMC), bootstrap/HAC CI; pre/post-2011 split.
- null: Difference <= 0 in 2012-2026.
- procedure: Daily closes only (the listed data has SPY closes, not opens), so close-to-close on day T, which includes the post-statement move (zero-mean noise for the drift test, but lower power). The true 13:55 ET window needs intraday data. Option overlay: BS-price the spread with VIX-as-IV at T-1 and at T (MODEL-PRICED).
- data: SPY daily closes since 1993, VIX, FOMC dates (Fed calendars). · min n: 100
- pass: Difference > 0 with 95% CI excluding 0 in 2012-2026 (about 120 meetings).
- controls: Random-date placebo; exclude unscheduled meetings; subtract the unconditional mean.
- harness: fomc_pre_drift_oos
- result X-a98432dc: not_supported — SPY FOMC-day close-to-close +10.6 bps vs non-FOMC +6.2 bps over 2012-2026 (117 FOMC days): difference +4.4 bps, 95% block-bootstrap CI -15.1 to +23.3 (HAC -15.0 to +23.8), random-date placebo p=0.327; 1994-2011 difference +31.4 bps; MODEL-PRICED 1% call spread FOMC +2.0 vs other +0.7 bps of spot — failed: 95% CI excludes 0 (lower bound > 0)
- note: from the options-library library: Pre-FOMC announcement drift call spread; harness suggestion: Event-window return harness with (T-1 close -> T open) and (T-1 close -> T close) variants; flag that intraday 13:55 is the true target. | verifier: corrected claim/trial

### T-219 · triple-witching-close-gamma

**Claim.** A 1-day ATM SPY straddle model-priced with VIX-as-IV (sigma = VIX at Thursday's close, T = 1/252), bought at Thursday's close and settled at Friday's close, has a higher mean P&L on quarterly triple-witching Fridays than on other Fridays.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable-products/0dte
- statistic: Difference in mean MODEL-PRICED long-straddle P&L (witching minus other Fridays), bootstrap CI and permutation p-value.
- null: Difference <= 0.
- procedure: Quarterly third Fridays since 1993; SPY closes; VIX; settle on |SPY_Fri - SPY_Thu|. This tests the close-to-close proxy only; the 15:00-16:00 claim needs an intraday capture at 15:00 ET (blocked).
- data: SPY daily closes, VIX, computed calendar. · min n: 100
- pass: Difference > 0 with 95% CI excluding 0 and permutation p < 0.05.
- controls: Monthly non-quarterly opex Fridays as a separate control; exclude witching days with FOMC; pre/post-2010 split.
- harness: macro_triple_witching_straddle
- result X-00792bd7: not_supported — MODEL-PRICED long 1-day ATM SPY straddle Thursday close to Friday close (BS, sigma=VIX(Thu), T=1/252) 1993-02-05..2026-10-09; dividend: priced on the dividend forward F = S_Thu(1 - D/S_Thu) on ex-dividend Fridays, K = S_Thu, settled on raw closes (ex-dividend on 132 of 132 witching and 0 other Fridays, mean D/S 44.5 bps): witching Fridays -25.0 vs other Fridays -19.6 bps of spot; difference -5.4 bps (95% CI -16.7 to +6.1) over 132 witching / 1516 other Fridays, permutation p=0.7960; dividend-neutral |r|/(VIX/sqrt252) witching 0.51 vs other 0.62; vs monthly opex +3.0 bps; ex FOMC weeks -11.6 bps; pre-2010 -7.4 bps, 2010+ -3.2 bps; difference with the dividend ignored (q = 0, raw move) +2.3, previous ex-date yield as forecast -5.5, dividend-adjusted closes -13.2 bps — failed: witching-minus-other mean long P&L > 0; 95% CI excludes 0 (lower bound > 0); permutation p < 0.05
- note: from the options-library library: Triple witching / quarterly rebalance close (long gamma into the close); harness suggestion: Event-day realised-move comparison harness (event dates vs matched weekday controls) with VIX-as-IV straddle pricer. | verifier: corrected claim/trial

### T-221 · crypto-macro-event-straddle

**Claim.** On FOMC decision days since April 2021, a 1-day ATM BTC straddle model-priced with DVOL-as-IV (sigma = DVOL at 00:00 UTC of the decision day, T = 1/365) and sold at 00:00 UTC has a lower mean P&L than the same model-priced straddle on non-FOMC days, settled on the next 00:00 UTC BTC close.

- kind: options-strategy · origin: options-library:event-driven, https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Difference in mean MODEL-PRICED short-straddle P&L (FOMC minus non-FOMC), bootstrap CI; mean |r|/(DVOL/sqrt(365)) by group.
- null: FOMC mean P&L >= non-FOMC mean P&L.
- procedure: Page DVOL 1D candles back to 2021-04; BTC daily closes aligned to 00:00 UTC (match DVOL candle timestamps); FOMC dates (about 44 events); pooled FOMC+CPI (about 110) as a variant with CPI dates hardcoded from BLS archives.
- data: Deribit DVOL history (public API), BTC daily closes, FOMC calendar. · min n: 40
- pass: Difference < 0 with 95% CI excluding 0 (FOMC-only; pooled reported alongside).
- controls: Random non-macro days; weekend exclusion; VIX-regime control; check BTC- vs USD-accounting give the same sign.
- harness: fomc_btc_event_straddle
- result X-bd896fa6: not_supported — MODEL-PRICED short 1-day ATM BTC straddle (BS, sigma=DVOL 00:00 UTC, T=1/365) since 2021-04-01: FOMC minus non-FOMC mean P&L -40.6 bps of spot (95% CI -101.1 to +19.1) over 44 FOMC / 1979 other days; |r|/(DVOL/sqrt365) FOMC 0.71 vs other 0.63; weekdays only -13.5 bps; coin accounting -36.1 bps; CPI-pooled variant not run (no CPI calendar) — failed: FOMC-minus-non-FOMC short-straddle P&L < 0 with 95% CI excluding 0
- note: from the options-library library: Crypto macro-event straddle on Deribit (FOMC / CPI) - DVOL vs realised; harness suggestion: Reuse the BTC VRP harness (DVOL vs realised) with an event-date mask; add inverse-option payoff mode to the payoff engine (payoff/S_T). | verifier: corrected claim/trial

### T-232 · vega_neutral_gamma_long

**Claim.** When VIX9D is below the trailing 10-day realised vol of SPY (short-dated implied under realised), the next 9-trading-day realised variance exceeds VIX9D-implied variance more often than not, so the vega-neutral long-near/short-far straddle swap entered on that signal has positive expectancy.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/term_structure/, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean of RV(1..9)^2 - VIX9D^2 conditional on VIX9D < RV(-10..0), and win rate; simulated gamma-scalp P&L of the swap with BS Greeks (VIX9D as near IV, VIX3M as far IV).
- null: Conditional near-term VRP >= 0 (implied still exceeds realised even when it sits below trailing realised).
- procedure: Daily VIX9D (from 2011), VIX3M, SPY closes; non-overlapping 9d cycles; studentized block bootstrap; walk-forward; deflated Sharpe on the simulated P&L.
- data: CBOE VIX9D, VIX3M history, SPY daily closes. · min n: 150
- pass: Conditional RV^2 - VIX9D^2 > 0 with 95% CI excluding zero and simulated P&L Sharpe > 0 after a 0.5 vol-point round-trip cost.
- controls: Unconditional control (should be negative, the VRP); random-entry placebo.
- harness: vix9d_conditional
- result X-d311688d: not_supported — 156 signals (VIX9D below trailing 10d realised): next-9d RV^2 - VIX9D^2 mean -0.0084, realised wins 17%, p=0.644
- result X-bda12d5b: not_supported — 156 signals (VIX9D below trailing 10d realised): next-9d RV^2 - VIX9D^2 mean -0.0084, realised wins 17%, p=0.644
- note: from the options-library library: Vega-neutral gamma-positive straddle swap (reverse calendar straddle); harness suggestion: New harness_gamma_swap built on harness_term_structure's index loader plus a daily-rehedge simulator (bs.delta) over SPY closes. | harness implements the data part only: it can falsify the claim, and a passing data part returns inconclusive until the strategy simulation exists | superseded by T-533 (verifier-corrected wording)

### T-241 · vix_spike_reversion_put

**Claim.** When VIX closes above 30 and above VIX3M (backwardation), spot VIX 21 trading days later is below the VIX3M/VIX-implied forward F in fewer than 50% of cases (the curve already prices the decline), but is below spot VIX in more than 75% of cases: an ATM-on-the-forward put spread has positive expectancy only when struck at spot, and the claim is that the excess reversion beyond F is not significant.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/term_structure/, https://www.cboe.com/tradable_products/vix/vix_options/specifications/
- statistic: Frequencies P(VIX_{t+21} < F_t) and P(VIX_{t+21} < VIX_t) conditional on VIX_t > 30 and VIX_t > VIX3M_t; simulated P&L of the put spread struck at F vs at spot (priced with VVIX as IV).
- null: P(VIX_{t+21} < F) = 0.5 (the forward is an unbiased forecast after spikes).
- procedure: Daily VIX, VIX3M, VVIX since 2007; event entries with 21d hold, non-overlapping; exact binomial CI and studentized block bootstrap; walk-forward.
- data: CBOE VIX, VIX3M, VVIX history. · min n: 25
- pass: Report both frequencies with CIs; strategy passes only if P(VIX_{t+21} < F) > 0.5 with the 95% CI excluding 0.5, otherwise record 'forward is fair' as the finding.
- controls: All-days baseline; VIX > 30 without backwardation.
- harness: vix_spike_forward
- result X-a1f4f715: supported — 23 spike events (VIX>30, backwardation): VIX 21 days later below the forward in 19/23 (0.61-0.95), below spot in 19/23 (0.61-0.95)
- result X-b9399c71: supported — 23 spike events (VIX>30, backwardation): VIX 21 days later below the forward in 19/23 (0.61-0.95), below spot in 19/23 (0.61-0.95); the pass rule (strategy passes) is met, which REFUTES the claim sentence that the curve already prices the decline
- result X-d52e3c83: not_supported — 23 spike events (VIX>30, backwardation): VIX 21 days later below the forward in 19/23 (0.61-0.95), below spot in 19/23 (0.61-0.95); the curve UNDER-prices the reversion (the strategy-side pass rule is met), which refutes the claim sentence that the curve already prices the decline (that reading is T-535); verdict: failed: P(VIX_t+21 < F) < 0.5; excess reversion beyond F not significant (exact 95% CI not above 0.5) (not implemented: put spread struck at F vs at spot: positive expectancy only when struck at spot (VVIX-priced P&L simulation); sample reaches trial min_n 25 events (23 so far))
- note: from the options-library library: VIX spike mean-reversion via long VIX put / put spread; harness suggestion: Add a 'backwardation event' study to harness_term_structure; event count will be small (~25-40 since 2007), report exact CIs. | WORDING CONFLICT: the claim sentence says VIX lands below the forward in fewer than 50% of spikes; the pass rule asks for more than 50% with the CI above 0.5. The verdict follows the pass rule. On 2026-10-14 data (19/23 below forward, CI 0.61-0.95) the pass rule is met and the claim sentence is refuted. Small n (23 non-overlapping events); in-sample. | superseded by T-535 (verifier-corrected wording)

### T-242 · vxx_uvxy_decay_options

**Claim.** Conditional on VIX3M/VIX > 1.10 at entry, the mean 21-trading-day log return of VXX is below -3%.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/term_structure/, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Mean 21d VXX log return conditional on VIX3M/VIX > 1.10; secondary: model-priced put-spread P&L (BS on VXX with a VVIX-scaled IV proxy) until VXX chain captures exist.
- null: Conditional mean >= -0.03.
- procedure: Daily VXX closes (current VXX from 2018-01; splice the matured 2009-2019 series only with a documented roll), VIX and VIX3M; non-overlapping 21d cycles; studentized block bootstrap; walk-forward threshold; deflated Sharpe. Replace the IV proxy with surface_summary VXX IVs after 60 captures.
- data: VXX/UVXY daily closes (NOT in the archive); SVXY closes ARE archived (from 2011-10: -1x until 2018-02-27, -0.5x after); VIX and VIX3M (archive); daily VXX chain capture (not in CHAIN_SYMBOLS). · min n: 80
- pass: Upper 95% bound of the conditional mean < -0.03; model-priced P&L reported separately.
- controls: Unconditional VXX drift (also expected negative); random-entry placebo; worst-month table; SVXY-based proxy run (sign-flipped, leverage-adjusted) as a cross-check.
- harness: vx_vxx_contango_decay
- result X-a09c37e5: not_supported — VXX (current series B, zero-volume bars dropped) 2018-01-29..2026-10-13: n=87 non-overlapping 21-day cycles entered at the close after a VIX3M/VIX > 1.1 close (need >= 80); mean log return -3.9% (median -6.1%), one-sided 95% studentized block-3 upper bound -1.0% (need < -3.0%), 95% CI [-6.8%, -0.5%]. Controls: unconditional mean -4.6% over 104 cycles; random-entry placebo: 71% of 2000 draws at or below the conditional mean; lag-0 entry mean -3.8% (n=87); fixed-grid phases -5.5% to -1.8%; walk-forward threshold 1.2 (first half to 2022-06-03) gives second-half mean -4.6% (n=22); DSR of the short-VXX cycle over 5 thresholds 0.884; worst cycles (largest VXX gains) 2018-02-01 +40%, 2022-02-09 +34%, 2025-03-26 +30%; SVXY proxy (sign-flipped, -1x to 2018-02-27 then -0.5x) 2011-10-04..2026-10-13: n=156, mean -5.0%, upper bound -2.6%, pre-2018 cycles 68 mean -7.2%. Secondary, reported separately: MODEL-PRICED: Black-Scholes, long ATM / short 17.5% OTM VXX puts, 75 DTE, marked after 21 trading days; IV = point-in-time scale x VVIX/100; DTB3 rate; no skew, no spread: n=78, mean P&L +16.2% of the debit (debit 7.1% of spot, IV proxy 61%), win rate 64% — failed: one-sided 95% studentized block-3 bootstrap upper bound of the conditional mean < -0.03
- note: from the options-library library: VXX / UVXY decay harvest with options (put spreads, call spreads, diagonals); harness suggestion: Add VXX/UVXY/SVXY to CHAIN_SYMBOLS and to the daily closes fetch; then a harness_vxx_decay in the harness_term_structure style. | verifier: corrected claim/trial

### T-243 · vvix_vol_of_vol

**Claim.** The 30-day realised volatility of the VIX (annualised stdev of daily log changes) is below VVIX by more than 10 vol points on average, and the gap is widest when VVIX is in its top quartile, so a short VIX strangle sized on VVIX has a positive vol-of-vol premium outside crisis months.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.cboe.com/tradable_products/vix/vix_options/specifications/
- statistic: Mean of VVIX_t - RV_vix(t..t+21) overall and by VVIX quartile; simulated short VIX strangle P&L priced with VVIX as IV on the forward F; crisis-month losses tabulated.
- null: VVIX - RV_vix <= 0 on average or not increasing in VVIX quartile.
- procedure: Daily VVIX and VIX since 2007; non-overlapping 21d cycles; studentized block bootstrap; quartile monotonicity test (harness_horizon_monotone pattern); deflated Sharpe.
- data: CBOE VVIX, VIX, VIX3M history. · min n: 200
- pass: Mean gap > 10 with 99% CI excluding zero; quartile means monotone increasing; simulated Sharpe > 0.3 after costs with worst-month loss < 5x average monthly gain.
- controls: Shuffled VVIX placebo; realised vol of the forward proxy F instead of spot VIX as a lower-variance check.
- harness: vvix_premium
- result X-ba2577e8: not_supported — VVIX exceeds realised VIX vol by -21.3 pts on average over 5102 days (p for gap > 10: 1.0000); quartile gaps -30.1/-19.0/-19.6/-16.3 NOT monotone
- result X-b139bb3f: not_supported — VVIX exceeds realised VIX vol by -21.3 pts on average over 5102 days (p for gap > 10: 1.0000); quartile gaps -30.1/-19.0/-19.6/-16.3 NOT monotone; note: VVIX is the implied vol of VIX futures, which move less than spot VIX, so comparing it with spot-VIX realised vol (as the claim does) understates any vol-of-vol premium
- result X-041e6dcb: not_supported — VVIX exceeds realised VIX vol by -21.3 pts on average over 5103 days (p for gap > 10: 1.0000); quartile gaps -30.1/-19.0/-19.6/-16.3 NOT monotone; note: VVIX is the implied vol of VIX futures, which move less than spot VIX, so comparing it with spot-VIX realised vol (as the claim does) understates any vol-of-vol premium
- note: from the options-library library: Vol-of-vol trade: VIX straddle / strangle vs VVIX; harness suggestion: Same harness_vvix_vrp as the VIX call ratio entry; add the quartile split and a strangle pricer. | harness implements the data part only: it can falsify the claim, and a passing data part returns inconclusive until the strategy simulation exists | the claim compares VVIX with spot-VIX realised vol; VVIX prices VIX futures, which are less volatile than spot, so a fair test of the vol-of-vol premium needs VIX futures history (CFE, not yet captured) | superseded by T-536 (verifier-corrected wording)

### T-245 · oil_bond_vrp_ovx_vxtlt

**Claim.** Over 2009-09 to 2026, an equal-vega portfolio of short 21-day variance positions on SPX, GLD, USO and TLT struck at VIX^2, GVZ^2, OVX^2 and VXTLT^2 has a higher Sharpe ratio than the SPX-only short variance position.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Sharpe(portfolio) - Sharpe(SPX only) of monthly variance-swap P&L (strike^2 - RV^2, vega-normalised); secondary: per-asset mean VRP and the monthly correlation matrix.
- null: Sharpe difference <= 0 (no diversification benefit).
- procedure: Non-overlapping 21d cycles from 2009-09-18 (OVX and GVZ start; VXTLT runs from 2004 and VIX from 1990, but use the common sample); fixed equal-vega weights (no optimisation, to avoid PBO); studentized bootstrap of the Sharpe difference; walk-forward halves.
- data: CBOE VIX, GVZ, OVX and VXTLT (archive); SPY, GLD, USO (split-adjusted) and TLT closes (archive). Model-free (index-implied variance). · min n: 180
- pass: Sharpe difference > 0 with bootstrap p < 0.05, positive in both halves.
- controls: Equal-weight buy-and-hold of the underlyings; shuffled-index placebo; drop-one-asset sensitivity.
- harness: multi_asset_short_var
- result X-e6c23238: not_supported — equal-vega short variance on SPX/GLD/USO/TLT Sharpe 0.95 vs SPX alone 1.13 over 204 months since 2009-09-18 (diff -0.17, one-sided lower -0.41; halves +0.35/-0.26) — failed: Sharpe diff > 0 with one-sided p < 0.05; positive in both halves
- note: from the options-library library: Oil and bond volatility premium (OVX via USO, VXTLT via TLT); harness suggestion: harness_vrp_oil and harness_vrp_bonds exist; add a portfolio aggregator over the harness outputs with the correlation matrix. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-247 · cross_asset_vol_ratio

**Claim.** After GVZ/VIX falls below its trailing 3-year 10th percentile (s = +1) or rises above its 90th (s = -1), s*[ln(RV_GLD/RV_SPY) - ln(GVZ/VIX)] over the next 21 trading days is positive on average: the realised vol ratio ends on the far side of the extreme implied ratio.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.deribit.com/kb/options
- statistic: Mean of s*[ln(RV_GLD/RV_SPY)_{t,t+21} - ln(GVZ_t/VIX_t)] over event entries; secondary: model-priced vega-neutral straddle-pair P&L.
- null: Mean <= 0.
- procedure: Daily GVZ and VIX from 2009-09-18, GLD and SPY closes; the trailing 3-year window makes 2012-09 the first usable entry; event entries with non-overlapping 21d holds; studentized block bootstrap; walk-forward; deflated over the 10/90 and 20/80 cut pairs. Repeat for DVOL/VIX on its shorter sample.
- data: CBOE GVZ, VIX, OVX and VXTLT (archive); Deribit DVOL (archive); GLD, SPY, USO, TLT and BTC closes (archive). Model-free for the statistic. · min n: 40
- pass: Mean > 0 with the 95% CI excluding zero and win rate > 0.6 for GVZ/VIX; DVOL/VIX reported with its own n.
- controls: Unconditional ratio drift; random-entry placebo; VIX-level stratification.
- harness: gvz_vix_extremes
- result X-00e1fb1e: not_supported — GVZ/VIX extremes: 90 signals, mean -0.052 log units (95% CI -0.145 to +0.038), win rate 0.46 — failed: mean > 0 with CI excluding 0; win rate > 0.6
- note: from the options-library library: Cross-asset implied vol ratio trades (GVZ/VIX, DVOL/VIX, OVX/VIX); harness suggestion: Combine harness_vrp_gold and harness_vrp_spx outputs into a ratio harness; the DVOL/VIX version joins harness_vrp_btc. | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-253 · btc-covered-call

**Claim.** Model-priced (BS with DVOL as a flat IV, no skew): writing a 25-delta 30-DTE call each month on 1 BTC gives a higher annualised Sharpe than buy-and-hold BTC over 2021-04 to 2026-09, with the studentized block-bootstrap 95% CI of the Sharpe difference excluding zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: Difference in annualised Sharpe (covered call minus buy-and-hold)
- null: Sharpe difference <= 0
- procedure: Daily BTC closes + daily DVOL (paginate get_volatility_index_data: 1000 points per call, history from 2021-03-24). Every 30 calendar days, sell a 25-delta call priced by BS with sigma = DVOL/100, r = 3-month bill, q = 0, and hold to expiry. Studentized block bootstrap (block = 30 calendar days). Walk-forward 2021-04..2023-12 / 2024-01..2026-09. Deflated Sharpe across the delta/DTE grid tried.
- data: BTC daily closes (Yahoo BTC-USD); Deribit DVOL daily from 2021-03-24 (verified); FRED DGS3MO · min n: 60
- pass: Pooled bootstrap 95% CI of the Sharpe difference excludes 0 and the sign holds in both walk-forward halves (about 33 cycles each, so per-half CIs are reported, not required); deflated Sharpe > 0
- controls: SPY covered call with VIX as IV (model-priced; should replicate the known BXM-style result). Cost min(0.0003 BTC, 12.5% of premium) per contract + 5% of premium for bid-ask. Skew sensitivity: price the call at DVOL +/- 3 vol points.
- harness: btc_covered_call
- result X-130e1ef5: not_supported — MODEL-PRICED at flat DVOL: 0.25-delta covered call Sharpe 0.51 vs hold 0.38 over 67 cycles (diff +0.13, 95% CI -0.05 to +0.41; halves +0.19/+0.12), DSR 0.44, MDD -60% vs -73% — failed: Sharpe diff 95% CI excludes 0
- note: from the options-library library: BTC covered call on coin inventory; harness suggestion: mandel.data.options.deribit_dvol_history + BTC closes -> bs.price with sigma=DVOL; payoff via Position; bootstrap from validation | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-254 · btc-cash-secured-put

**Claim.** Model-priced (BS with DVOL as a flat IV): selling a 25-delta 30-DTE BTC put each month from 2021-04 to 2026-09 has a positive mean cycle P&L ((premium - payoff)/K, i.e. excess over the bill yield the collateral already earns), with a studentized block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.optionseducation.org/strategies/all-strategies/cash-secured-put, https://www.deribit.com/api/v2/public/get_instruments?currency=USDC&kind=option&expired=false
- statistic: Mean of (premium - payoff)/K per cycle
- null: Mean <= 0
- procedure: Monthly cycles on BTC closes, put priced at DVOL via BS; studentized block bootstrap on cycle P&L; walk-forward halves; compare to the same rule on SPY with VIX (model-priced)
- data: BTC closes; DVOL from 2021-03-24 (paged); FRED DGS3MO · min n: 60
- pass: Pooled 95% bootstrap CI of the mean > 0 and a positive mean in both halves
- controls: Fee min(0.0003 BTC, 12.5% of premium) per contract; slippage 5% of premium; repeat at DVOL - 5 vol points (the 25-delta put can trade below DVOL, which is a variance-swap index)
- harness: btc_short_put
- result X-a9d5ba07: not_supported — MODEL-PRICED at flat DVOL: 0.25-delta short put mean +0.88% of spot per cycle over 67 cycles (95% CI -0.44 to +2.15), halves +0.80/+0.96 — failed: 95% CI of the mean > 0
- result X-af2e1a54: not_supported — MODEL-PRICED at flat DVOL: 0.25-delta short put mean +0.88% of strike per cycle over 67 cycles (95% CI -0.44 to +2.15), halves +0.80/+0.96 — failed: 95% CI of the mean > 0
- note: from the options-library library: Coin-secured / cash-secured put to accumulate BTC or metal; harness suggestion: Same loop as btc-covered-call with kind='put'; reuse VRP harness | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-256 · dvol-percentile-vega

**Claim.** Model-priced (BS at DVOL): ATM BTC straddles bought when DVOL is below its trailing 365-day 20th percentile and held 60 days to expiry have a higher mean return than straddles bought on all days, 2022-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: Mean straddle return conditional on low DVOL minus the unconditional mean
- null: Difference <= 0
- procedure: Rolling 365-day percentile of DVOL (warm-up ends 2022-03); on entry days price a 60-DTE straddle at DVOL (DVOL is a 30-day IV, so a term mismatch is a known model bias); hold 60 days; use non-overlapping entries for the conditional set; block bootstrap of the difference; walk-forward halves
- data: DVOL history 2021-03-24..today; BTC closes · min n: 25
- pass: Difference CI > 0 (also report whether the conditional mean is > 0)
- controls: Random entry days matched by count; SPY straddle at VIX (model-priced) as sanity check; a 30-DTE version to remove the term mismatch
- harness: btc_low_dvol_straddle
- result X-766daf94: not_supported — MODEL-PRICED at flat DVOL: 60-day ATM straddles bought with DVOL below its trailing 20% quantile return +31.0% on premium vs +14.0% on all days (629 of 1605 daily entries; diff 95% CI -12.1 to +46.8, overlapping entries, block = holding period) — failed: difference 95% CI > 0
- note: from the options-library library: DVOL percentile vega timing (long/short vol regimes); harness suggestion: Add percentile filter to the DVOL harness; straddle P&L via Position | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-258 · funding-carry-option-hedged

**Claim.** With the hedge model-priced (10-delta 30-DTE call at DVOL), long-spot/short-BTC-PERPETUAL funding carry net of the rolling call cost has a positive mean monthly return over 2021-04 to 2026-09, with a studentized block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name=BTC-PERPETUAL&start_timestamp=1728000000000&end_timestamp=1728100000000
- statistic: Mean monthly carry net of hedge cost
- null: Mean <= 0
- procedure: Pull get_funding_rate_history (hourly) for 2021-04..2026-09 and sum interest_1h per month; each month price a 10-delta 30-DTE call with BS at DVOL and add its expiry payoff; net; block bootstrap; walk-forward halves
- data: Deribit funding history (verified from 2019-05); DVOL; BTC closes; FRED DGS3MO for excess return · min n: 24
- pass: CI of net monthly carry > 0; Sharpe > 1 reported
- controls: Unhedged carry as comparison; months with negative funding included; call priced at DVOL + 5 vol points (the 10-delta call wing usually trades above DVOL)
- harness: carry_funding_call_hedged
- result X-f07adf1e: not_supported — MODEL-PRICED (BS at DVOL, 10-delta 30-DTE call). 66 months 2021-04..2026-09: mean funding +0.43%/month, mean call premium +0.74%, mean payoff +1.22%; net carry mean +0.909%/month, studentized 95% CI [-0.029, +3.156]% (need lower > 0); Sharpe of net over DTB3 0.44 (need > 1); unhedged mean +0.431%, Sharpe 0.69; DVOL+5 hedge mean +0.665% — failed: studentized block-bootstrap 95% CI of mean monthly net carry above 0; annualised Sharpe of monthly net carry over DTB3 > 1
- note: from the options-library library: Perpetual funding carry hedged with options; harness suggestion: Add deribit_funding_history to mandel.data.options; monthly aggregation; hedge from DVOL | verifier: corrected claim/trial

### T-264 · btc-weekend-theta

**Claim.** BTC Friday-close-to-Monday-close (3 calendar days) realised variance is less than 3x the average single weekday variance (i.e. weekend variance per calendar day is lower), 2017-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Ratio of weekend 3-day variance to 3x mean weekday 1-day variance
- null: Ratio >= 1
- procedure: From daily BTC closes split returns by weekday; compute ratio per year; bootstrap CI
- data: BTC daily closes since 2015 (need day-of-week stamps) · min n: 200
- pass: Ratio CI entirely < 0.9 in at least 70% of years
- controls: Same ratio for ETH; shuffled weekday labels as null
- harness: btc_weekend_variance
- result X-1d68b098: not_supported — weekend (Fri->Mon) variance / 3x weekday variance: CI below 0.9 in 2/10 years (need 70%); ratios 2017:0.53, 2018:0.61, 2019:0.79, 2020:0.43, 2021:0.72, 2022:0.86, 2023:0.93, 2024:0.95, 2025:0.55, 2026:0.33
- result X-6122d1b6: not_supported — weekend (Fri->Mon) variance / 3x weekday variance: CI below 0.9 in 2/10 years (need 70%); ratios 2017:0.53, 2018:0.61, 2019:0.79, 2020:0.43, 2021:0.72, 2022:0.86, 2023:0.93, 2024:0.95, 2025:0.55, 2026:0.34
- note: from the options-library library: Weekend theta harvest (24/7 pricing vs weekend realised vol); harness suggestion: Pure closes-based test; later confirm pricing side with Deribit daily-expiry captures | superseded by T-515 (verifier-corrected wording)

### T-267 · btc-protective-put

**Claim.** Model-priced (BS at DVOL): holding BTC with rolling 10-delta 90-DTE puts gives a higher Calmar ratio (CAGR / max drawdown) than buy-and-hold BTC over 2021-04 to 2026-09.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: Calmar ratio difference (hedged - unhedged); also max drawdown ratio and annual cost
- null: Calmar difference <= 0
- procedure: Simulate monthly rolls on BTC closes with BS puts at DVOL (+3 vol points skew haircut variant); compare paths; stationary block bootstrap of the Calmar difference; 3 walk-forward windows
- data: BTC closes; DVOL from 2021-03-24; FRED DGS3MO · min n: 20
- pass: Bootstrap 95% CI of the Calmar difference > 0 and positive in at least 2 of 3 windows
- controls: SPY/VIX (model-priced; protective puts there are known to underperform collars); collar variant as a comparator
- harness: btc_protective_put
- result X-a4d32b86: not_supported — MODEL-PRICED at flat DVOL: BTC + rolling 10-delta 90-day puts Calmar 0.13 vs hold 0.07 over 22 cycles (diff +0.06, 95% lower -0.42; thirds +0.10/-2.20/-0.08) — failed: Calmar difference 95% CI > 0; positive in >= 2 of 3 windows
- note: from the options-library library: Protective put / tail hedge on BTC inventory sized by DVOL; harness suggestion: Payoff engine rolling template; reuse covered-call loop | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-270 · gold-covered-call

**Claim.** Model-priced (BS with GVZ as a flat IV): a 30-delta 30-DTE GLD covered call written monthly has a higher annualised Sharpe than long GLD over 2009-10 to 2026-09, with a studentized block-bootstrap 95% CI of the difference above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: Annualised Sharpe difference (covered call - long GLD)
- null: Sharpe difference <= 0
- procedure: GLD closes + GVZ daily; monthly covered call priced at GVZ; studentized block bootstrap; walk-forward (2009-2017 / 2018-2026); deflated Sharpe over the delta/DTE grid
- data: Cboe GVZ_History.csv (2009-09-18..2026-10-13, verified); GLD daily closes (Yahoo chart, in collect_history); FRED DGS3MO · min n: 100
- pass: CI excludes 0 pooled and the sign holds in both halves; deflated Sharpe > 0
- controls: SPY/VIX covered call as positive control (model-priced); slippage 2% of premium; GVZ - 1 vol point (GVZ is a variance-swap level, above the 30-delta call IV)
- harness: gld_covered_call
- result X-e5665ac0: not_supported — MODEL-PRICED at flat GVZ: 0.30-delta covered call Sharpe 0.70 vs hold 0.57 over 203 cycles (diff +0.12, 95% CI -0.04 to +0.32; halves +0.03/+0.29), DSR 0.22, MDD -28% vs -43% — failed: Sharpe diff 95% CI excludes 0
- note: from the options-library library: Gold covered call (GLD / GC-OG) using GVZ as the IV reference; harness suggestion: cboe_index_history('GVZ') exists in mandel.data.options (CBOE_INDICES); add GLD to the closes feed; reuse VRP harness with GVZ | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-272 · gvz-low-long-straddle

**Claim.** Model-priced (BS at GVZ): 90-DTE ATM GLD straddles bought when GVZ is below its trailing 252-day 20th percentile have a higher mean hold-to-expiry return than straddles bought on all days, 2010-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Conditional minus unconditional mean straddle return
- null: Difference <= 0
- procedure: 252-day percentile filter on GVZ; price the straddle at GVZ (30-day index used for a 90-day option, a known term mismatch); hold 90 days; non-overlapping conditional entries; block bootstrap; walk-forward
- data: GVZ history; GLD closes · min n: 20
- pass: Difference CI > 0 (also report whether the conditional mean is > 0)
- controls: Random entry dates; VIX/SPY analogue; 30-DTE version
- harness: gld_low_gvz_straddle
- result X-4d1156f7: not_supported — MODEL-PRICED at flat GVZ: 90-day ATM straddles bought with GVZ below its trailing 20% quantile return +12.1% on premium vs -0.5% on all days (1131 of 3974 daily entries; diff 95% CI -5.9 to +32.1, overlapping entries, block = holding period) — failed: difference 95% CI > 0
- note: from the options-library library: GVZ low-percentile long gold vol (crisis convexity); harness suggestion: Percentile harness shared with dvol-percentile-vega | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py; MODEL-PRICED at the index as a flat IV, as the claim states

### T-273 · gold-event-vol

**Claim.** GVZ falls on average from the close before an FOMC decision day to the close after it, 2009-10 to 2026-09.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Mean change in GVZ from t-1 to t+1 around FOMC decision days (share declining reported)
- null: Mean change >= 0
- procedure: FOMC decision dates (federalreserve.gov calendars, 8/year, ~135 decisions); GVZ daily; paired differences; bootstrap + sign test; repeat for CPI dates
- data: GVZ history; FOMC and CPI date tables · min n: 100
- pass: Mean change < 0 with 95% CI excluding 0
- controls: Non-event days matched by weekday; the same test on VIX as positive control; note that 30-day VIX-method indices mechanically drop when an event leaves the window
- harness: fomc_gvz_event_change
- result X-dfd2c227: not_supported — GVZ change from the close before to the close after 135 scheduled FOMC decision days (2009-11-04..2026-09-16): mean +0.053 vol pts (95% CI -0.247 to +0.385), 56% declining (sign-test p=0.0841); weekday-matched non-event 2-day change -0.086; VIX positive control +0.009 pts (95% CI -0.414 to +0.437) — failed: mean GVZ change < 0 with 95% CI excluding 0
- note: from the options-library library: Gold event vol (FOMC/CPI straddle on GLD); harness suggestion: Event-date table in mandel/knowledge; paired-difference harness over cboe_index_history('GVZ') | verifier: corrected claim/trial

### T-274 · gold-silver-ratio-options

**Claim.** When the GLD/SLV price ratio exceeds its trailing 5-year 90th percentile, the 180-day forward log change of the ratio is negative on average, 2011-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: Mean 180-day forward log change of GLD/SLV, conditional on > 90th percentile
- null: Mean >= 0
- procedure: Daily GLD and SLV closes (SLV from 2006-04, so 5-year percentiles start 2011); non-overlapping forward windows; block bootstrap; extend the sample with GC=F/SI=F futures closes (Yahoo, from 2000; unverified) for more episodes
- data: GLD and SLV daily closes (Yahoo, in collect_history); SLV IV from daily chain capture for the option overlay · min n: 15
- pass: Conditional mean < 0 at 90% confidence (few independent episodes; report the count) and hit rate > 60%
- controls: Low-percentile mirror; random dates
- harness: gold_silver_ratio_extreme
- result X-5beb6789: not_supported — GLD/SLV above its 5-year 90th percentile: 16 independent episodes, 180-day change -0.042 (one-sided 90% upper +0.010), hit rate 0.62 — failed: mean < 0 at 90% confidence
- note: from the options-library library: Gold-silver ratio options trade; harness suggestion: Underlying-ratio harness now; option overlay once SLV surface_summary history exists | verifier: corrected claim/trial | tested by mandel/experiments/cross_asset.py

### T-302 · crypto-trend-sma-50-200

**Claim.** On BTC-USD 2014-2026, the 50/200 golden-cross long/flat rule has a maximum drawdown at least 40% smaller than buy-and-hold and a Sharpe ratio not lower than buy-and-hold after 25 bps per side, and the same direction holds on ETH 2017-2026.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/crypto, https://www.nber.org/papers/w24877 (Liu-Tsyvinski; fetched), https://arxiv.org/abs/2009.12155 (fetched)
- statistic: Sharpe difference (rule minus buy-and-hold) via block bootstrap on daily returns (block 30 days); max-drawdown ratio; DSR across the declared variant grid
- null: Rule Sharpe = buy-and-hold Sharpe; drawdown ratio no better than a random in/out sequence with matched time-in-market
- procedure: Daily series; declare the variant list; walk-forward with 30-day embargo (parameters are fixed so this is a pure out-of-sample evaluation); 2000 bootstrap draws; 1000 matched random in/out paths for the drawdown null; DSR with n_trials = number of variants (grid of Mo et al. counted in full if run)
- data: daily-history-BTC-USD, daily-history-ETH-USD (Yahoo); cross-check against Coinbase daily candles from 2016 · min n: 1500
- pass: Drawdown reduction > 40% on BTC and ETH; Sharpe difference lower 95% bound > -0.2; DSR > 0.5 for the golden cross
- controls: Look-ahead: close at 00:00 UTC, trade next day; survivorship: BTC/ETH are survivors among thousands of coins, so the claim is per-asset not for 'crypto'; costs: 25 bps per side plus 10 bps slippage; multiple testing: whole grid; regime: report per halving cycle (2014-16, 2016-20, 2020-24, 2024-) and flag that 3 cycles is the effective sample
- harness: golden_cross_crypto
- result X-3f905d4b: not_supported — BTC: MDD -70% vs -83% (-17%), Sharpe 1.07 vs 1.10 (lower -0.39), DSR 1.00; ETH: MDD -78% vs -79% (-2%), Sharpe 0.70 vs 0.77 (lower -0.60), DSR 0.94 — failed: BTC drawdown reduction > 40%; BTC Sharpe diff lower bound > -0.2; ETH drawdown reduction > 40%; ETH Sharpe diff lower bound > -0.2
- result X-2988e0ba: not_supported — BTC: MDD -70% vs -83% (-17%), Sharpe 1.07 vs 1.10 (lower -0.39), DSR 1.00; ETH: MDD -78% vs -79% (-2%), Sharpe 0.70 vs 0.77 (lower -0.60), DSR 0.94 — failed: BTC drawdown reduction > 40%; BTC Sharpe diff lower bound > -0.2; ETH drawdown reduction > 40%; ETH Sharpe diff lower bound > -0.2
- result X-31c71edc: not_supported — BTC: MDD -70% vs -83% (-17%), Sharpe 1.05 vs 1.10 (lower -0.41), DSR 1.00; ETH: MDD -78% vs -86% (-10%), Sharpe 0.68 vs 0.62 (lower -0.47), DSR 0.94 — failed: BTC drawdown reduction > 40%; BTC Sharpe diff lower bound > -0.2; ETH drawdown reduction > 40%; ETH Sharpe diff lower bound > -0.2
- note: from the underlying-library library: Crypto trend: 50/200 SMA and 12-week momentum on BTC and ETH; harness suggestion: trend.py sma_cross(prices, fast, slow) and donchian(prices, n); harness crypto_trend_vs_bh over BTC/ETH bundles; add Coinbase candle fetcher (api.exchange.coinbase.com/products/BTC-USD/candles, verified) as a second source to check Yahoo closes. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-485 (verifier-corrected wording)

### T-303 · crypto-trend-funding-filter

**Claim.** On BTC 2021-01 to 2026-10, adding the funding crowding state machine to the 200-day SMA long/flat rule raises after-cost Sharpe ratio, with the paired block-bootstrap 95% interval of the Sharpe difference (filtered minus unfiltered) excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/crypto, https://arxiv.org/abs/2212.06888 (fetched), https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name=BTC-PERPETUAL (endpoint verified live; history from 2020-01)
- statistic: Sharpe(filtered) - Sharpe(unfiltered), paired daily; count of HALF/FLAT activations caused by funding; DSR over the joint funding-trial count
- null: Funding adds no information beyond the trend signal: Sharpe difference = 0; placebo with F shifted +30 days gives the same difference
- procedure: Fetch hourly funding 2020-01 onward in 14-day pages into bundle deribit-funding-BTC-PERPETUAL with available_at = record timestamp; compute F and trailing percentiles strictly from past records; paired circular block bootstrap (block 30 days, 5,000 draws); +30-day shifted placebo; DSR with joint n_trials
- data: daily-history-BTC-USD (archive); Deribit public funding history (endpoint verified live, hourly from 2020-01-01) · min n: 2000
- pass: Sharpe difference > 0 with 95% interval excluding 0, placebo interval includes 0, DSR > 0.95, and at least 10 separate funding-driven activations (fewer = inconclusive)
- controls: Look-ahead: only funding records timestamped before the decision; percentile window strictly trailing; survivorship: n/a; costs: 25 bps per side plus 10 bps slippage on every extra state change; multiple testing: joint count with sibling funding entries; regime: report 2021-22 and 2023-26 halves
- harness: carry_trend_funding_filter
- result X-45363c88: not_supported — 2113 days 2021-01-01..2026-10-14: Sharpe filtered 0.64 vs unfiltered 0.57, difference 0.067 with 95% interval [-0.099, 0.230] (need > 0 and excluding 0); placebo difference -0.028 interval [-0.163, 0.114] (need to include 0); DSR 0.043 (need > 0.95); 10 funding-driven activations (need >= 10) — failed: Sharpe difference > 0 with paired block-bootstrap 95% interval excluding 0; DSR of daily filtered-minus-unfiltered returns > 0.95 (n_trials = 39)
- note: from the underlying-library library: Funding-rate-aware crypto trend (crowding filter on BTC/ETH trend signals); harness suggestion: New fetcher mandel/data/deribit.py: funding_history(instrument, start, end) paging by 14 days into bundle deribit-funding-<instrument> with available_at = timestamp; harness funding_filter_vs_trend in trend.py sharing the sma rule; report activation count as a hard inconclusive gate. | verifier: corrected claim/trial

### T-304 · donchian-breakout-atr-stop

**Claim.** Pooled across the listed ETFs and crypto pairs, the mean after-cost return per trade of the 55-day breakout with 10-ATR trailing stop exceeds the mean return of random-entry trades on the same assets with matched holding periods, with the asset-clustered bootstrap 95% interval of the difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/breakout, https://www.cis.upenn.edu/~mkearns/finread/trend.pdf (Wilcox-Crittenden 2005; fetched and text-extracted), https://concretumgroup.com/does-trend-following-still-work-on-stocks/ (Zarattini-Pagani-Wilcox 2025; fetched)
- statistic: Mean trade return (rule) minus mean trade return (matched random entries), clustered by asset; diagnostics: trade-return skewness, portfolio Sharpe vs equal-weight buy-and-hold
- null: Breakout entries are no better than random entries held for the same durations
- procedure: Simulate per asset on adjusted daily OHLC with one-bar execution delay; for each rule trade draw 1,000 random entry dates on the same asset with the same holding length; cluster bootstrap by asset and calendar year (5,000 draws); Holm or DSR over the 60-trial grid
- data: Yahoo daily OHLC plus adjclose for SPY, QQQ, GLD, SLV, XLK, XLE, BTC-USD, ETH-USD (XLK/XLE not yet in archive; bundle schema currently keeps close and volume only) · min n: 150
- pass: Difference > 0 with 95% interval excluding 0 over at least 150 pooled trades, surviving the 60-trial correction (DSR > 0.95 on the trade-return series or Holm-adjusted p < 0.05)
- controls: Look-ahead: signal on close t, fill at close t+1; dividend adjustment of OHLC; survivorship: survivor ETFs/crypto only, single-stock version blocked; costs: 5 bps ETFs, 25+10 bps crypto per side, plus gap slippage when the close-to-close move through the stop exceeds the stop; multiple testing: 60 trials; regime: trades by decade and VIX tercile
- harness: ohlc_donchian_atr_breakout
- result X-d019c368: not_supported — 658 closed trades across 8 assets (181 asset-year clusters): rule mean net +2.39% vs matched random entries +1.57% (same costs), difference +0.82% (cluster 95% CI -0.26..+2.17, p=0.0956, 60-trial Bonferroni 1.000); trade-return DSR 0.998 over 60; vs cost-free random +0.65%; trade skew +9.69 — failed: mean difference > 0 with cluster-bootstrap 95% CI excluding 0
- note: from the underlying-library library: Donchian channel breakout and all-time-high entry with ATR trailing stop; harness suggestion: trend.py donchian_atr(ohlc, n, atr_mult) returning trade list and daily returns; harness breakout_expectancy with the matched-hold random-entry control; extend the Yahoo bundle schema to keep open/high/low (currently close and volume). | verifier: corrected claim/trial

### T-305 · dual-momentum-gem

**Claim.** GEM (12-month, SPY/EFA/AGG) achieves a Sharpe ratio at least equal to a 60/40 SPY/AGG benchmark after costs over 2003-2026 with a maximum drawdown at least 25% smaller, and the lookback-6-to-12 ensemble does so with lower variance of outcomes than any single lookback.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/dual, https://mebfaber.com/timing-model/ (fetched; on parameter stability and monthly evaluation), https://www.advisorperspectives.com/articles/2019/05/06/global-equity-momentum-a-craftsmans-perspective (ReSolve; 403 here, summarised from search result)
- statistic: Sharpe difference vs 60/40 via block bootstrap on monthly returns; max drawdown ratio; dispersion of Sharpe across lookbacks 6-12 (parameter sensitivity)
- null: GEM Sharpe = 60/40 Sharpe; lookback choice explains the result (PBO > 0.5 across the lookback set)
- procedure: Monthly series since 2003 (AGG start; EFA 2001); declare lookbacks 3-12 and the 4 structural variants; walk-forward with 1-month embargo; 2000 block bootstraps (block 12); CSCV PBO over the lookback x variant matrix; DSR with n_trials = matrix size
- data: daily-history-{SPY,EFA,VEU,AGG,BND,BIL}, FRED TB3MS · min n: 250
- pass: Sharpe difference >= 0 with lower 95% bound > -0.15, drawdown reduction > 25%, PBO < 0.5 across lookbacks
- controls: Look-ahead: month-end close used next day; survivorship: ETFs chosen are the paper's, no selection; costs: 3 bps per switch; multiple testing: lookback and structural variants counted; regime: the 2003-2026 window has only two large bear markets (2008, 2022) and one flash (2020); report the result with and without 2008
- harness: gem_dual_momentum
- result X-681555d4: error — harness raised NameError
- result X-289f61db: not_supported — GEM Sharpe 0.80 vs 60/40 0.87 (diff -0.07, lower -0.48), MDD -21% vs -32%, PBO 0.39 over 265 months — failed: Sharpe diff >= 0 with lower bound > -0.15 (not implemented: ensemble lowers outcome variance)
- result X-267f9afa: not_supported — GEM excess Sharpe 0.59 vs 60/40 0.64 (diff -0.05, lower -0.43), MDD -24% vs -33%, PBO 0.60 over 264 months (fills at the next day's close, 3 bps per switch) — failed: Sharpe diff >= 0 with lower bound > -0.15; PBO < 0.5 (not implemented: ensemble lowers outcome variance)
- note: from the underlying-library library: Dual momentum (Antonacci GEM): relative + absolute momentum between US and foreign equity with a bond fallback; harness suggestion: trend.py dual_momentum(prices_dict, lookback, fallback) -> monthly weights; harness gem_vs_6040 with pbo_cscv across the lookback grid. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-480 (verifier-corrected wording)

### T-306 · xs-momentum-etf-rotation

**Claim.** Top-3 12-1 rotation across the 9 sector SPDRs earns a positive after-cost alpha against SPY (monthly regression) over 1999-2026 with the alpha's block-bootstrap interval excluding zero, and the result is not driven by a single sector or decade.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional, https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1249-1290.html (Moskowitz-Grinblatt; fetched), https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html (Jegadeesh-Titman; fetched)
- statistic: Monthly CAPM alpha vs SPY and Sharpe difference; leave-one-sector-out and leave-one-decade-out ranges; PBO across the ranking-window grid
- null: Zero alpha: rotation = SPY beta exposure; rank ordering carries no information (permutation of ranks within month)
- procedure: Monthly series; declare the grid (4 lookbacks x 3 top-k x filter on/off x long-only/long-short); walk-forward with embargo; 1000 within-month rank permutations as the null; block bootstrap for alpha; CSCV PBO; DSR with n_trials = grid size
- data: daily-history for the 9 sector SPDRs and the asset-class set (Yahoo; add via collect_history) · min n: 300
- pass: Alpha > 0 with 95% interval excluding 0 and above the 95th percentile of the permutation null; PBO < 0.5; sign of alpha positive in each leave-one-out subset
- controls: Look-ahead: ranks from month-end closes, trade next open; survivorship: sector SPDRs are a fixed, complete set since 1998 (no bias); costs: 3-5 bps per side, turnover about 30-50% per month; multiple testing: grid counted; regime: report by decade, exclude 2000-02 and 2008 as robustness
- harness: sector_rotation
- result X-61ec30e0: error — harness raised NameError
- result X-0667ba9d: not_supported — sector top-3 alpha +17.3 bps/month over 322 months (95% CI -5.9 to +41.0; random-pick 95th pct +19.5), PBO 0.29, leave-one-out min -1.4 — failed: alpha > 0 with CI excluding 0; alpha above 95th pct of permutation null; alpha > 0 leaving out each sector
- result X-e8562d46: not_supported — sector top-3 alpha +17.3 bps/month over 322 months (95% CI -5.9 to +41.0; cost-matched random-pick 95th pct +23.2), PBO 0.29, leave-one-sector-out min -1.4, leave-one-decade-out 2000s +4.5/2010s +33.1/2020s +11.7 — failed: alpha > 0 with CI excluding 0; alpha above 95th pct of permutation null; alpha > 0 leaving out each sector
- note: from the underlying-library library: Cross-sectional ETF momentum (sector and asset-class rotation); harness suggestion: trend.py xs_momentum(prices_df, lookback, skip, top_k, long_short) -> weights; harness xs_etf_momentum with within-month rank permutation null; reuse pbo_cscv. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-475 (verifier-corrected wording)

### T-312 · trend-metals-gold-silver

**Claim.** A gold+silver risk-parity 12-1 TSMOM long/flat strategy on GLD/SLV earns a positive after-cost excess return over 2006-2026 with a lower drawdown than buy-and-hold, and the pooled monthly return exceeds the historical-mean long strategy with the bootstrap interval excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/metals, https://www.nber.org/papers/w11222 (Erb-Harvey; fetched), https://arxiv.org/abs/1404.3274 (Lemperiere et al.; fetched)
- statistic: Pooled monthly return difference vs historical-mean long; Sharpe and max drawdown vs buy-and-hold; DSR across signal variants
- null: Zero difference vs historical-mean long (Huang et al. null); random in/out with matched time-in-market for the drawdown
- procedure: Monthly series for GLD/SLV (and GC=F/SI=F with roll-day returns dropped as a check); declare variants; walk-forward; block bootstrap (block 12 months); matched random null; DSR
- data: daily-history-{GLD,SLV,IAU,GC=F,SI=F,PPLT,PALL} (Yahoo, verified reachable) · min n: 200
- pass: Difference > 0 with interval excluding 0; drawdown reduction > 25%; sign agrees between ETF and chained-futures series; DSR > 0.5
- controls: Look-ahead: month-end close used next day; survivorship: ETFs chosen ex ante, all survive; costs: 3-5 bps ETFs, GLD expense 40 bps/yr included via price; multiple testing: variants counted; regime: report per regime episode (5 episodes), flag the 2013 gold crash and 2011 silver crash as single-day gap risk for breakout variants
- harness: metals_tsmom
- result X-394ef7eb: supported — metals TSMOM minus always-long -15.0 bps/month over 234 months (95% CI -54.3 to +21.4), drawdown -31% vs -51% (-40%), futures -19.9, DSR 0.99 — all criteria pass
- result X-59b357ad: not_supported — metals TSMOM minus always-long -15.0 bps/month over 234 months (95% CI -54.3 to +21.4), drawdown -31% vs -51% (-40%), futures -19.9, DSR 0.99 — failed: difference > 0 with CI excluding 0
- result X-22d2e29d: not_supported — metals TSMOM minus historical-mean strategy -4.9 bps/month over 233 months from 2007-06 (95% CI -42.6 to +31.0), drawdown -31% vs buy-and-hold -51% (-40%), futures -7.0 over the same 233 months, DSR 0.99, excess over bills +70.1 bps/month — failed: difference vs historical-mean > 0 with CI excluding 0
- note: from the underlying-library library: Trend following on precious metals (gold and silver ETFs and chained futures); harness suggestion: collect_history for GLD, SLV, IAU, GC=F, SI=F, PPLT, PALL; trend.py functions from the TSMOM entry with an inverse-vol combiner; harness metals_trend with a roll-day mask for =F symbols. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-487 (verifier-corrected wording)

### T-315 · btc-eth-short-horizon-tsmom

**Claim.** The 1-week TSMOM long/flat rule on BTC and ETH, 2014/2017-2026, earns a positive after-cost weekly excess return over the historical-mean long strategy with the block-bootstrap interval excluding zero, and the result holds in the 2019-2026 post-publication window alone.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/crypto, https://www.nber.org/papers/w24877 (fetched), https://quantpedia.com/trend-following-and-mean-reversion-in-bitcoin/ (fetched)
- statistic: Paired weekly difference (rule minus historical-mean long); Sharpe; DSR over the k x implementation grid; separate estimate for 2019-2026
- null: Zero difference vs historical-mean long (no predictability)
- procedure: Weekly series; declare grid; walk-forward with 1-week embargo; 2000 block bootstraps (block 8 weeks); DSR; sub-period test
- data: daily-history-BTC-USD, daily-history-ETH-USD (Yahoo), Coinbase candles as a check · min n: 400
- pass: Difference > 0 with interval excluding 0 after 30 bps per side costs; 2019-2026 sub-period difference > 0; DSR > 0.5
- controls: Look-ahead: Sunday close used Monday open; survivorship: two surviving assets, per-asset claim; costs: 30 bps per side applied to every switch (~25 switches/yr); multiple testing: grid counted; regime: per halving cycle
- harness: crypto_weekly_tsmom
- result X-9cf9dbda: supported — weekly TSMOM minus always-long -46.3 bps/week over 630 weeks (95% CI -91.8 to +2.3), 2019- -40.5, DSR 0.99 — all criteria pass
- result X-33eb058b: not_supported — weekly TSMOM minus always-long -46.3 bps/week over 630 weeks (95% CI -91.8 to +2.3), 2019- -40.5, DSR 0.99 — failed: difference > 0 with CI excluding 0; 2019- difference > 0
- result X-b83f8cf1: not_supported — weekly TSMOM minus historical-mean strategy -41.3 bps/week over 604 weeks (164 BTC-only before ETH's warm-up ends; 95% CI -90.7 to +7.5), 2019- -39.9, DSR 0.99 — failed: difference vs historical-mean > 0 with CI excluding 0; 2019- difference > 0
- note: from the underlying-library library: Short-horizon time-series momentum in BTC and ETH (1-4 week); harness suggestion: trend.py sign_lookback on weekly resample; harness btc_weekly_tsmom; reuse crypto_trend_vs_bh infrastructure. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-486 (verifier-corrected wording)

### T-333 · overnight-intraday-reversal

**Claim.** On SPY from 2000-01 to 2026-09, buying at the open after overnight gaps below -0.5% and shorting at the open after gaps above +0.5%, closing at the same day's close, earns a positive mean net intraday return per trade after 2 bps round trip.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://personal.lse.ac.uk/polk/research/tugofwar.pdf, https://doi.org/10.1016/j.jfineco.2019.03.011
- statistic: mean net intraday return per gap trade with bootstrap interval; diagnostic: corr(o_t, i_t)
- null: mean net return per trade = 0; zero correlation for the diagnostic
- procedure: Compute o and i from OHLC. Condition on the gap sign. Run 2,000 block-bootstrap resamples (block 20). Split by decade. Run QQQ and the IBIT control.
- data: Yahoo daily OHLC SPY/QQQ 2000-2026 (official auction opens); IBIT 2024-; stock variants need point-in-time universes (fja05680 + Yahoo, survivorship-biased) · min n: 500
- pass: 95% lower bound of mean net return per trade > 0 AND same sign in 2000-2012 and 2013-2026 AND DSR > 0.95 over variants; the correlation alone, if significant, parks the entry as 'structure without edge'
- controls: Look-ahead: trade at the opening auction print. Costs: 1 bp per side plus auction slippage for size. Survivorship: stock variants biased. Multiple testing: 6 variants. Regime: pre/post 2013, VIX terciles.
- harness: ohlc_gap_fade
- result X-e6d84c5e: not_supported — 1952 gap trades |o|>0.50% 2000-01-03..2026-09-30 (902 long, 1050 short): mean net -6.25 bps after 2 bps RT (95% CI -12.45..-0.15); gap net of the ex-date dividend (108 ex-dividend days, 38 traded; raw-gap sensitivity: 1954 trades, 40 on ex-dividend days, mean -6.64 bps, CI -12.92..-0.56; 36 days change side); halves <2013-01-01 -7.34 / >=2013-01-01 -5.03 bps; DSR 0.000 over 6 variants; diagnostic corr(o,i) +0.018 (95% CI -0.036..+0.069); IBIT control (expected no edge) 540 trades, mean -11.2 bps — failed: 95% lower bound of mean net per trade > 0; DSR > 0.95 over 6 variants
- note: from the underlying-library library: Overnight vs intraday return reversal; harness suggestion: overnight_intraday_decomp: OHLC decomposition, correlation test, gap-fade simulator, IBIT control | verifier: corrected claim/trial

### T-341 · pre-fomc-announcement-drift

**Claim.** SPY's close-to-close return on scheduled FOMC statement days exceeds its mean return on all other days by at least 15 bps over 1994-2026, and the excess is positive in the 2016-2026 subsample.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.newyorkfed.org/research/staff_reports/sr512.html, https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html
- statistic: Mean daily return difference (bps), FOMC statement days minus all other days.
- null: Equal means. Test with a studentized block bootstrap (block 10) of the day-flagged daily series, as in turn_of_month.
- procedure: Flag scheduled statement days; run the full sample and the 2016-2026 subsample. The primary is SPY. QQQ, IWM, TLT, GLD and BTC plus the 5 non-primary variants are 10 further trials, Holm-adjusted. This test shares FOMC days with the macro-announcement entry and must not be counted as independent confirmation of it.
- data: daily-history-SPY (1993-, stored); FOMC statement dates parsed from federalreserve.gov (fomchistorical1994.htm and fomccalendars.htm verified reachable); VIX from CBOE (stored); Polymarket Fed markets (stored); Kalshi KXFEDDECISION via /historical/markets. · min n: 200
- pass: Difference > 15 bps with p < 0.05 over 1994-2026 AND a 2016-2026 difference > 0.
- controls: Look-ahead: the schedule is published a year ahead; scheduled dates only. Survivorship: n/a. Costs: 8 round trips/yr at 1-2 bps, charged. Multiple testing: 1 primary plus 10 secondary trials (Holm). Regime: pre/post-2015 is the pre-registered split; ZLB years 2009-2015 flagged; overlap with CPI release days flagged.
- harness: fomc_statement_day_drift
- result X-3b985170: not_supported — SPY statement-day return +21.6 bps (net of 2 bps) vs other days +4.2 bps over 261 statement days 1994-01-03..2026-10-13: net difference +17.4 bps (95% CI +3.1 to +31.5), p=0.0070 (H0 diff<=0; p vs 15 bps 0.384); 2016-2026 -5.3 bps; secondary Holm p QQQ +26.2 bps p_holm=0.060, IWM +23.9 bps p_holm=0.070, TLT +7.2 bps p_holm=0.409, GLD +7.0 bps p_holm=0.431, BTC-USD +6.8 bps p_holm=0.431 — failed: 2016-2026 net difference > 0
- note: from the underlying-library library: Pre-FOMC announcement drift; harness suggestion: events.py: fomc_dates() fetcher (parse statement URLs by year, cache to mandel/data as 'fomc-dates'), then event_day_effect(days, closes, event_days, offset=-1, n_boot=2000) generalizing turn_of_month's paired block bootstrap; add subsample argument. | verifier: corrected claim/trial

### T-342 · fomc-cycle-even-weeks

**Claim.** Over 1994-2026, SPY's mean daily return in even FOMC-cycle weeks (0, 2, 4, 6) exceeds its mean in odd weeks by at least 5 bps per day, with the difference positive in both halves and in the 2017-2026 subsample.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://papers.ssrn.com/abstract=2687614, https://rpc.cfainstitute.org/research/cfa-digest/2020/05/dig-v50-n5-2
- statistic: Mean daily return difference (bps), even-week days minus odd-week days.
- null: Equal means. Test with a studentized block bootstrap (block 5) of the day-flagged series. Second p-value from a calendar placebo: shift every cycle origin by an odd number of weeks (1 or 3, which flips parity) or by a uniform random 1-30 trading days. Shifts of 2 or 4 weeks preserve parity and are NOT valid placebos.
- procedure: Compute cycle weeks from scheduled statement dates. Test the full sample, halves (1994-2009 / 2010-2026) and 2017-2026. The placebo distribution comes from 1,000 random-offset calendars. The 4 non-primary variants are extra trials (Holm).
- data: daily-history-SPY (stored), FOMC statement dates (same fetcher as the pre-FOMC entry), EFA (stored), BTC-USD (stored). · min n: 1500
- pass: Difference > 5 bps/day with p < 0.05; both halves and 2017-2026 positive; random-offset placebo p < 0.05.
- controls: Look-ahead: scheduled dates only. Survivorship: n/a. Costs: about 28 round trips/yr at 1-2 bps (about 30-55 bps/yr), charged. Multiple testing: week indexing fixed to the published definition, 5 variants Holm. Regime: halves, ZLB years flagged.
- harness: fomc_cycle_even_weeks
- result X-93025618: not_supported — SPY even FOMC-cycle weeks +7.55 bps/day (net of 2 bps per block, 24 blocks/yr) vs odd +0.73 bps/day over 4385+3818 days 1994-01-03..2026-10-13: net difference +6.8 bps/day (95% CI +2.1 to +11.9), p=0.0050; 1994-2009 +12.1, 2010-2026 +1.8, 2017-2026 -5.2; random-offset placebo p=0.002 (gross +7.18 vs placebo 95th pct +4.14); week 0 = days -1..+3 then 5-day weeks — failed: 2017-2026 net difference > 0
- note: from the underlying-library library: FOMC-cycle even-week effect; harness suggestion: events.py: fomc_cycle_week(days, statement_days) -> week index per day; even_week_effect(days, closes, statement_days, cost_bps=1.5) with the cycle-shift placebo; verdict format as weekday_effect. | verifier: corrected claim/trial

### T-343 · macro-announcement-day-premium

**Claim.** Over 1993-2026, SPY's mean close-to-close return on scheduled CPI, Employment Situation and FOMC statement days exceeds its mean on all other days by at least 5 bps per day, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/how-much-do-investors-care-about-macroeconomic-risk-evidence-from-scheduled-economic-announcements/C6A48B33065D93550C87FEB53C029A0B, https://www.nber.org/papers/w25817
- statistic: Mean daily return difference (bps), release days minus other days; Sharpe on release days vs other days.
- null: Equal means. Test with a studentized block bootstrap (block 10) of the day-flagged series.
- procedure: Build the release-day set from published schedules (point-in-time; dates are announced a year ahead). Run the full sample, halves (1993-2009 / 2010-2026) and a per-type breakdown (Holm over 3 types). The 5 non-primary variants count as trials.
- data: daily-history-SPY (stored). FOMC dates from the Fed site (reachable). CPI and Employment Situation release dates 1993-2026: the FRED API fred/release/dates (release_id 10 CPI, 50 Employment Situation) answers 'api_key is not set' without a key (verified). The BLS schedule archive returns 403 from this host. Kalshi gives CPI dates only from 2021-07. · min n: 600
- pass: Difference > 5 bps/day with p < 0.05 and both halves positive; the FOMC-excluded sensitivity is also reported.
- controls: Look-ahead: scheduled dates only; shutdown-delayed releases (Oct 2013, autumn 2025) use the actual release day, flagged. Survivorship: n/a. Costs: about 32 round trips/yr at 1-2 bps, charged. Multiple testing: 6 variants plus 3 types (Holm). Regime: halves; 2008 and 2020 flagged; overlap with pre-FOMC days declared.
- harness: macro_announcement_day_premium
- result X-05b99f6b: not_supported — SPY release-day close-to-close +8.93 bps (net of 2 bps per round trip, 30/yr) vs other days +3.92 bps over 1047 release days (CPI 403, jobs 404, FOMC 261) 1993-02-01..2026-10-13: net difference +5.01 bps/day (gross +6.95; 95% CI -3.3 to +13.0), p=0.1034 (H0 diff<=0; p vs 5 bps 0.487); 1993-2009 +12.7 bps, 2010-2026 -2.7 bps; per type CPI +0.6 (Holm p 0.473), Employment Situation +4.6 (Holm p 0.473), FOMC +17.7 (Holm p 0.022); FOMC-excluded +2.5 bps (p=0.297); net Sharpe, each day type annualised by sqrt of its days/yr (31 release, 221 other): release 0.41 vs other 0.50 (release-only strategy, flat otherwise, 0.41); primary Holm p over 5 variants 0.517 — failed: studentized block-bootstrap p < 0.05; 2010-2026 net difference > 0
- note: from the underlying-library library: Scheduled macro announcement-day premium (CPI, jobs, FOMC, GDP, ISM); harness suggestion: data/fetch.py: fred_release_dates(release_id) cached as 'fred-release-dates-<id>'; events.py: event_day_effect(days, closes, event_days, offset=0) shared with pre-FOMC; per-type loop with Bonferroni as in weekday_effect. | verifier: corrected claim/trial

### T-344 · turn-of-month-replication

**Claim.** The turn-of-month premium found on SPY (T-59, window -4..+3) replicates with a positive, block-bootstrap-significant difference in at least three of the five assets QQQ, IWM, TLT, GLD and BTC-USD over their full histories.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://rpc.cfainstitute.org/research/financial-analysts-journal/2008/equity-returns-at-the-turn-of-the-month, https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
- statistic: per asset: mean daily return difference (bps), TOM days minus other days; count of assets with p < 0.05 and both halves positive
- null: equal means per asset; studentized block bootstrap (block 21); a count of 3 or more of 5 at the 5% level has binomial probability < 0.002 under independence
- procedure: run turn_of_month unchanged on each asset (window fixed, no search); report halves; BTC/ETH use 7-day calendars
- data: daily-history-QQQ, daily-history-IWM, daily-history-TLT, daily-history-GLD, daily-history-BTC-USD (Yahoo, same loader as SPY) · min n: 2500
- pass: at least 3 of 5 assets with difference > 0, p < 0.05, both halves > 0
- controls: look-ahead (none: calendar), survivorship (n/a), costs (12 rt/yr at 1-2 bps for ETFs, 20-60 bps for BTC at retail taker fees: charged), multiple testing (5 assets + 4 variants = 9 declared trials; the pass rule is a joint count), regime dependence (halves per asset)
- harness: tom_replication
- result X-4d5f471c: not_supported — turn-of-month replicates on 2/5 assets (need 3): QQQ +5.9 bps net, p=0.061; IWM +7.8 bps net, p=0.016; TLT +0.1 bps net, p=0.424; GLD -0.5 bps net, p=0.518; BTC-USD +13.7 bps net, p=0.038 — failed: at least 3 of 5 assets pass
- result X-9a309bb4: not_supported — turn-of-month replicates on 2/5 assets (need 3): QQQ +5.9 bps net, p=0.061; IWM +7.8 bps net, p=0.016; TLT +0.1 bps net, p=0.424; GLD -0.5 bps net, p=0.518; BTC-USD +13.7 bps net, p=0.038 — failed: at least 3 of 5 assets pass
- result X-38a6588c: not_supported — turn-of-month replicates on 2/5 assets (need 3): QQQ +5.9 bps net, p=0.061; IWM +7.8 bps net, p=0.016; TLT +0.1 bps net, p=0.424; GLD -0.5 bps net, p=0.518; BTC-USD +13.5 bps net, p=0.041 — failed: at least 3 of 5 assets pass
- note: from the underlying-library library: Turn-of-the-month premium: cross-asset and sub-window replication; harness suggestion: Extend run.py: loop turn_of_month(days, closes) over the five symbols after fetch_yahoo_history for QQQ/IWM/TLT/GLD (social.py yahoo_history is the fetcher); add window and payday variants as parameters (before, after, mid=(14,16)). | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-443 (verifier-corrected wording)

### T-346 · quarter-end-window-dressing

**Claim.** IWM's return on the last trading day of each quarter exceeds its return on the first trading day of the next quarter by at least 20 bps on average over 2000-2026 (mark-up then reversal), with both halves agreeing in sign.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/f/pca244.html, https://faculty.wharton.upenn.edu/wp-content/uploads/2016/11/MUSTOD-10003064-2025-1.pdf
- statistic: mean (last-day return minus next-day return) across quarter ends (bps)
- null: zero difference; bootstrap over quarter-end pairs and a placebo using the same day-pair at random non-quarter month ends
- procedure: flag quarter-end last/first trading days from the NYSE calendar; compute paired differences; halves 2000-2012 / 2013-2026; ^RUT extends to 1987 as a pre-publication check
- data: daily-history-IWM (2000-), ^RUT from Yahoo (1987-), daily-history-SPY · min n: 100
- pass: difference > 20 bps, bootstrap p < 0.05, both halves positive, placebo p > 0.1
- controls: look-ahead (calendar only), survivorship (n/a for ETFs), costs (8 rt/yr at 1-3 bps: charged), multiple testing (5 variants), regime dependence (halves; pre/post-2002 publication split on ^RUT)
- harness: quarter_end_reversal
- result X-979dcb94: not_supported — IWM quarter-end minus next-day -17.1 bps over 106 quarters (p=0.824), halves -55.6/+18.5; placebo month ends -26.7 bps (p=0.956) — failed: bootstrap p < 0.05
- result X-c518ca95: not_supported — IWM quarter-end minus next-day -17.1 bps over 106 quarters (p=0.824), halves -55.6/+18.5; placebo month ends -26.7 bps (p=0.956) — failed: mean > 20 bps; bootstrap p < 0.05; both halves positive
- result X-66ce388f: not_supported — IWM quarter-end minus next-day -17.1 bps over 106 quarters (p=0.824), halves -55.6/+18.5; placebo month ends -26.7 bps (p=0.956) — failed: mean > 20 bps; bootstrap p < 0.05; both halves positive
- note: from the underlying-library library: Quarter-end window dressing and 'leaning for the tape'; harness suggestion: events.py: quarter_end_pairs(days) -> list of (last_day_idx, first_day_idx); paired_day_effect(closes, pairs, placebo_pairs) with bootstrap over pairs; run on IWM, ^RUT, SPY. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-439 (verifier-corrected wording)

### T-348 · overnight-vs-intraday

**Claim.** Over 1993-2026, SPY's mean close-to-next-open return, with dividends added back on ex-dates, exceeds its mean open-to-close return by at least 3 bps per trading day, with the gap positive in both halves.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://researchonline.lse.ac.uk/id/eprint/87481, https://ideas.repec.org/a/pal/assmgt/v12y2011i2d10.1057_jam.2011.2.html
- statistic: Mean overnight minus mean intraday return (bps/day). Secondary: Sharpe of the overnight-only series net of a 1 bp round trip vs buy-and-hold.
- null: Equal means. Studentized block bootstrap (block 10) of the paired daily (overnight, intraday) series.
- procedure: r_night = open_t / close_{t-1} - 1 (+ dividend_t / close_{t-1} on ex-dates, since ex-dividend drops land overnight). r_day = close_t / open_t - 1. Halves 1993-2009 / 2010-2026. Other assets and variants are Holm-adjusted trials.
- data: Yahoo daily OHLC (the chart endpoint returns open for SPY from 1993; open == close on about 1% of days, flagged) and Yahoo dividend events (events=div, verified). The stored daily-history bundles keep only close/adjclose/volume, so they must be re-fetched with the open field. · min n: 3000
- pass: Gap > 3 bps/day with p < 0.05 and both halves positive. The net-of-cost Sharpe comparison is reported but is not part of the pass.
- controls: Look-ahead: none. Survivorship: n/a. Costs: 252 round trips/yr at 1 bp (2 bp sensitivity). Multiple testing: 6 assets plus 3 variants (Holm). Regime: halves; Yahoo's 'open' may be the first print rather than the auction price, flagged; dividend adjustment mandatory.
- harness: ohlc_overnight_vs_intraday
- result X-5ba41761: not_supported — SPY 1993-02-01..2026-10-13 (8483 days, 136 ex-dividend nights with D/C added back): overnight +4.03 vs intraday +0.74 bps/day, gap +3.29 bps (95% CI +1.05..+5.55; one-sided 95% lower bound +1.44; claim: at least 3 bps), p=0.404 vs gap <= 3 bps (the pass criterion; p=0.0025 vs equal means, the trial's stated null, shows only that the gap is positive); halves <2010-01-01 +5.19 / >=2010-01-01 +1.38 bps; secondary Sharpe overnight net 1 bp 0.72 (2 bp 0.48) vs buy-hold 0.65; open==close on 1.0% of days (flagged) — failed: p < 0.05 vs gap <= 3 bps (studentized block-10 bootstrap)
- note: from the underlying-library library: Overnight vs intraday return split (the night effect); harness suggestion: social.py yahoo_history: keep open/high/low; experiments/volatility.price_ohlc(rows) returning aligned arrays; events.py: overnight_intraday(days, opens, closes, cost_bps=1.0) with paired block bootstrap and net Sharpe. | verifier: corrected claim/trial

### T-350 · santa-claus-rally

**Claim.** SPY's cumulative return over the last five trading days of December plus the first two of January exceeds the average return of all other 7-trading-day windows by at least 1 percentage point over 1993-2026 (and ^GSPC 1928-2026), with both halves agreeing.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://en.wikipedia.org/wiki/Santa_Claus_rally, https://pro.thestreet.com/portfolio/what-are-the-actual-odds-of-a-santa-claus-rally
- statistic: mean Santa-window 7-day return minus the mean of all other overlapping 7-day windows (pp); sign-agreement rate of the barometers vs 0.5 adjusted for drift
- null: window is unexceptional: bootstrap distribution of randomly placed 7-day windows (block-preserving) per year; barometers: binomial with p equal to the unconditional probability of a positive year
- procedure: compute per year; ^GSPC extends to 1928 for ~98 observations; halves; report overlap with the turn-of-month flag by also testing the window net of the TOM days
- data: daily-history-SPY; ^GSPC from Yahoo (1927-12-30 onward); IWM, QQQ, BTC-USD, GLD · min n: 30
- pass: excess > 1 pp with placement-bootstrap p < 0.05 on ^GSPC (n ~ 98) and positive on SPY; barometers pass only if sign-agreement exceeds the drift-adjusted binomial 95th percentile
- controls: look-ahead (none), survivorship (n/a), costs (1 rt/yr), multiple testing (6 variants; the window was chosen by Hirsch after looking at data, so treat 1950-1972 as in-sample and 1973-2026 as the real test), regime dependence (halves; overlap with TOM removed as a sensitivity)
- harness: santa_rally
- result X-77358286: supported — Santa window excess over the average 7-day window +1.38 pp on ^GSPC over 98 years (placement p=0.000), SPY +0.49 pp, halves +2.14/+0.61 — all criteria pass
- result X-22d944f4: supported — Santa window excess over the average 7-day window +1.38 pp on ^GSPC over 98 years (placement p=0.000), SPY +0.49 pp, halves +2.14/+0.61 — all criteria pass
- result X-2450086d: not_supported — Santa window excess over the average 7-day window +1.38 pp on ^GSPC over 98 years (placement p=0.000), halves +2.14/+0.61; SPY +0.49 pp over 33 years, halves +0.89/+0.12 — failed: SPY excess >= 1 pp (1993-)
- note: from the underlying-library library: Santa Claus rally and turn-of-year indicators; harness suggestion: events.py: fixed_window_vs_random(days, closes, window_fn, length=7, n_boot=2000) where window_fn returns the Santa window per year; barometer_sign_test(days, closes, rule) for the indicator variants. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-440 (verifier-corrected wording)

### T-351 · january-small-cap-effect

**Claim.** The IWM-minus-SPY cumulative return from the close of the sixth-to-last trading day of December to the close of the tenth trading day of January is positive on average by at least 1 percentage point over 2000-2026, and the ^RUT-minus-^GSPC version is positive over 1987-2026 with both halves agreeing.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://rpc.cfainstitute.org/research/financial-analysts-journal/2006/the-january-effect, https://ideas.repec.org/a/taf/ufajxx/v62y2006i5p78-88.html
- statistic: mean turn-of-year spread return (pp) across years; sign count
- null: zero mean spread; bootstrap over years and a placement placebo using the same-length window at random dates in each year
- procedure: compute per year on IWM-SPY (2000-) and ^RUT-^GSPC (1987-); halves on the longer series; placement placebo gives a second p-value
- data: daily-history-IWM, daily-history-SPY, ^RUT and ^GSPC from Yahoo, IWC, IWN · min n: 25
- pass: mean spread > 1 pp with bootstrap p < 0.05 on the 1987-2026 series, both halves positive, placement-placebo p < 0.05
- controls: look-ahead (none), survivorship (indexes/ETFs only; the single-stock tax-loss variant is flagged as survivorship-biased), costs (2 legs x 1 rt/yr at 1-2 bps; short borrow on SPY negligible), multiple testing (6 variants), regime dependence (halves; 2000-2002 and 2020-2021 small-cap episodes flagged)
- harness: january_small_cap
- result X-f0511619: not_supported — Russell minus S&P over the turn of the year +0.87 pp over 39 years (p=0.025, placebo p=0.034), halves +1.91/-0.13; IWM-SPY +0.09 pp — failed: both halves positive
- result X-2a0f4e77: not_supported — Russell minus S&P over the turn of the year +0.87 pp over 39 years (p=0.025, placebo p=0.034), halves +1.91/-0.13; IWM-SPY +0.09 pp — failed: ^RUT-^GSPC mean > 1 pp; both halves positive
- result X-65c1b193: not_supported — Russell minus S&P over the turn of the year +0.87 pp over 39 years (p=0.025, placebo p=0.034), halves +1.91/-0.13; IWM-SPY +0.09 pp — failed: ^RUT-^GSPC mean > 1 pp; both halves positive
- note: from the underlying-library library: Turn-of-year small-cap premium (January effect, tax-loss rebound); harness suggestion: events.py: fixed_window_vs_random on a spread series built from two symbols (helper spread_series(days_a, a, days_b, b)); reuse from the Santa-rally harness with a different window_fn. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-444 (verifier-corrected wording)

### T-352 · sell-in-may-halloween

**Claim.** SPY's mean monthly return in November-April exceeds its mean in May-October by at least 50 bps per month over 1993-2026 (and ^GSPC 1928-2026), and the difference is positive in the post-2002 (post-publication) subsample.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.aeaweb.org/articles?id=10.1257/000282802762024683, https://www.tias.edu/docs/default-source/Kennisartikelen/ssrn-id2154873.pdf
- statistic: mean monthly return difference, Nov-Apr minus May-Oct (bps/month); Sharpe of the switching strategy vs buy-and-hold
- null: equal means; studentized block bootstrap (block 6 months) of the monthly series; month-of-year grid: Bonferroni over 12
- procedure: monthly returns from daily closes; full sample on ^GSPC and SPY; subsamples pre-2002 and 2002-2026; variants counted as trials (7) for DSR
- data: daily-history-SPY, ^GSPC (Yahoo), QQQ, IWM, EFA, TLT, GLD, sector SPDRs, BTC-USD · min n: 360
- pass: difference > 50 bps/month with p < 0.05 on ^GSPC 1928-2026, SPY 1993-2026 difference > 0, 2002-2026 difference > 0
- controls: look-ahead (none), survivorship (n/a), costs (2 rt/yr; sector rotation 12 legs/yr), multiple testing (7 variants + 12-month grid; DSR over 19), regime dependence (pre/post-publication split is pre-registered; 2008 and 2020 crash months fall in different halves, flagged)
- harness: sell_in_may
- result X-eef67ea9: not_supported — Nov-Apr minus May-Oct +40 bps/month on ^GSPC over 98 years from 1928 (p=0.051); SPY +50; post-2002 +43 — failed: p < 0.05
- result X-f434df42: not_supported — Nov-Apr minus May-Oct +40 bps/month on ^GSPC over 98 years from 1928 (p=0.051); SPY +50; post-2002 +43 — failed: ^GSPC difference > 50 bps/month; p < 0.05
- result X-e7437d51: not_supported — Nov-Apr minus May-Oct +40 bps/month on ^GSPC over 98 years from 1928 (p=0.051); SPY +50; post-2002 +43 — failed: ^GSPC difference > 50 bps/month; p < 0.05; SPY difference >= 50 bps/month (1993-)
- note: from the underlying-library library: Sell in May / Halloween indicator and month-of-year seasonality; harness suggestion: events.py: half_year_effect(days, closes, start_month=11, end_month=4) returning monthly means, block-bootstrap p, Sharpe of switching vs buy-and-hold; month_of_year_grid(days, closes) with Bonferroni, mirroring weekday_effect. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-441 (verifier-corrected wording)

### T-353 · opex-week-triple-witching

**Claim.** SPY's return over the monthly options-expiration week (Monday to third-Friday close) exceeds the average return of other weeks by at least 20 bps over 1993-2026, with the difference positive in both halves.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/jbfina/v37y2013i11p4226-4240.html, https://rpc.cfainstitute.org/research/financial-analysts-journal/1991/expiration-day-effects-what-has-changed
- statistic: mean opex-week return minus mean other-week return (bps); week-after and witching-day arms reported alongside
- null: equal weekly means; studentized block bootstrap (block 4 weeks) of the paired weekly series; Bonferroni over the 3 week-type arms
- procedure: compute third Fridays from the calendar; weekly returns Friday close to Friday close; halves 1993-2009 / 2010-2026; BTC and GLD arms with their own expiry rules
- data: daily-history-SPY, QQQ, IWM, BTC-USD, GLD (Yahoo) · min n: 350
- pass: opex-week excess > 20 bps, Bonferroni p < 0.05, both halves positive
- controls: look-ahead (none), survivorship (n/a), costs (12 rt/yr at 1-2 bps), multiple testing (7 variants; Bonferroni on the 3 week arms), regime dependence (halves; the rise of weekly/0DTE options after 2016 and 2022 flagged as a mechanism change)
- harness: opex_week
- result X-4ecac469: not_supported — SPY opex week +24.4 vs other weeks +23.2 bps (excess +1.2, Bonferroni p=1.000, halves +18.1/-15.8) — failed: Bonferroni p < 0.05; both halves positive
- result X-c1129583: not_supported — SPY opex week +24.4 vs other weeks +23.2 bps (excess +1.2, Bonferroni p=1.000, halves +18.1/-15.8) — failed: excess > 20 bps; Bonferroni p < 0.05; both halves positive
- result X-d802443d: not_supported — SPY opex week +21.7 vs other weeks +22.9 bps (excess -1.2, Bonferroni p=1.000, halves +19.8/-22.1) — failed: excess > 20 bps; Bonferroni p < 0.05; both halves positive
- note: from the underlying-library library: Options-expiration week and triple witching; harness suggestion: events.py: third_fridays(days) and last_fridays(days); week_type_effect(days, closes, week_flag_fn) producing weekly returns and the paired bootstrap; witching_day_effect reuses event_day_effect. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-438 (verifier-corrected wording)

### T-354 · crypto-calendar-effects

**Claim.** BTC-USD's Monday (UTC) close-to-close return exceeds the mean of the other six weekdays by at least 20 bps over 2014-2026 after Bonferroni correction over seven weekdays, with both halves agreeing.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/finlet/v31y2019ics1544612318304513.html, https://philippdubach.com/posts/crypto-mean-reversion-trading/
- statistic: Monday mean minus other-day mean (bps), two-sided, Bonferroni x7
- null: equal weekday means; studentized block bootstrap (block 14) of the paired daily series (weekday_effect already implements this for 7-day series)
- procedure: run weekday_effect on BTC-USD and ETH-USD; expiry and holiday arms via event_day_effect two-sided; TOM arm via turn_of_month; hourly arm blocked
- data: daily-history-BTC-USD (2014-), daily-history-ETH-USD (2017-); Coinbase hourly candles for the hours arm (untested, paged 300 bars/request) · min n: 600
- pass: Monday excess > 20 bps, Bonferroni p < 0.05, both halves positive, and the net-of-maker-fee (0.4% per round trip) weekly strategy Sharpe > buy-and-hold (expected fail on costs even if the effect exists)
- controls: look-ahead (none), survivorship (BTC/ETH only, no dead coins), costs (52 rt/yr at 0.4-0.6%: charged, decisive), multiple testing (7 variants + 7 weekdays; Bonferroni), regime dependence (halves; 2017 and 2021 bubbles flagged; T-62's weekend null is a prior)
- harness: btc_monday
- result X-c698c81e: not_supported — BTC Monday +36.5 bps vs other days (Bonferroni p=0.112); Monday-only net of 0.4% Sharpe 0.18 vs buy-and-hold 0.99 — failed: Bonferroni p < 0.05; net Monday strategy Sharpe > buy-and-hold
- result X-f79ca263: not_supported — BTC Monday +36.5 bps vs other days (Bonferroni p=0.112); Monday-only net of 0.4% Sharpe 0.18 vs buy-and-hold 0.99 — failed: Bonferroni p < 0.05; net Monday strategy Sharpe > buy-and-hold
- result X-9b84676e: not_supported — BTC Monday +36.5 bps vs other days (Bonferroni p=0.077); Monday-only net of 0.4% Sharpe 0.18 vs buy-and-hold 0.98 — failed: Bonferroni p < 0.05; net Monday strategy Sharpe > buy-and-hold
- note: from the underlying-library library: Crypto calendar effects: weekday, month-turn, derivatives expiry and trading-hours; harness suggestion: Reuse weekday_effect and turn_of_month on BTC/ETH; add last_fridays-based event_day_effect two-sided; hours arm waits on data/fetch.py coinbase_candles(product, granularity=3600) with paging. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-436 (verifier-corrected wording)

### T-356 · gold-seasonality

**Claim.** GLD's mean daily return in September-November exceeds its mean in the other nine months by at least 5 bps per day over 2004-2026 (GC=F 2000-2026), with the difference positive in both halves.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/riibaf/v27y2013i1p1-11.html, https://ideas.repec.org/a/vrs/ijomae/v60y2024i3p157-172n1001.html
- statistic: mean daily return difference (bps), Sep-Nov days minus other days; month-of-year grid with Bonferroni over 12 as a secondary
- null: equal means; studentized block bootstrap (block 21) of the paired daily series
- procedure: flag months; full sample on GC=F (2000-) and GLD (2004-); halves; post-2013 subsample as the post-publication test; grid variant reports the strongest month after Bonferroni
- data: daily-history-GLD, GC=F, SLV, GDX from Yahoo (same loader) · min n: 2500
- pass: difference > 5 bps/day, p < 0.05, both halves positive, post-2013 difference > 0
- controls: look-ahead (none), survivorship (n/a), costs (1-2 rt/yr at 2-3 bps), multiple testing (7 variants + 12-month grid; Bonferroni), regime dependence (halves; 2011 top and 2020, 2024-25 rallies flagged; the published reversal is the pre-registered expectation)
- harness: gold_autumn
- result X-415ea23a: not_supported — GLD Sep-Nov minus other months -2.26 bps/day (p=0.725), halves +3.76/-8.26, post-2013 -8.09; GC=F -2.46 — failed: difference > 5 bps/day; p < 0.05; both halves positive; post-2013 > 0
- result X-4396480e: not_supported — GLD Sep-Nov minus other months -2.26 bps/day (p=0.725), halves +3.76/-8.26, post-2013 -8.09; GC=F -2.46 — failed: difference > 5 bps/day; p < 0.05; both halves positive; post-2013 > 0
- result X-08b2d59b: not_supported — GLD Sep-Nov minus other months -2.26 bps/day (p=0.725), halves +3.76/-8.26, post-2013 -8.09; GC=F -2.56 — failed: difference > 5 bps/day; p < 0.05; both halves positive; post-2013 > 0; GC=F difference >= 5 bps/day (2000-)
- note: from the underlying-library library: Gold seasonality: autumn effect, Indian wedding season and Lunar New Year; harness suggestion: events.py: month_set_effect(days, closes, months={9,10,11}) sharing code with half_year_effect; month_of_year_grid(days, closes) with Bonferroni; run over GLD, GC=F, SLV, GDX. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-437 (verifier-corrected wording)

### T-362 · crypto-cme-cash-and-carry

**Claim.** On monthly CME BTC contracts from January 2018 to September 2026, a hold-to-expiry cash-and-carry entered only when the synchronous annualized basis exceeds DTB3 + 3% earns a positive mean annualized excess return over DTB3 on total capital (spot plus 40% margin) after 20 bp round-trip costs.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.bis.org/publ/work1087.htm, https://query1.finance.yahoo.com/v8/finance/chart/BTC=F
- statistic: Mean annualized excess return over DTB3 per contract-month on total capital. Contract-months not entered count as 0 excess.
- null: Mean excess return <= 0 after costs.
- procedure: For each contract month: entry basis from synchronous prices (BTC=F close vs Coinbase hourly close at the CME settle hour). Realized return = (F_entry - S_entry)/S_entry, minus settlement slippage (F_final vs the Coinbase hourly close at 16:00 London on expiry Friday, as a BRR proxy), minus 20 bp, plus T-bill interest on the margin, minus DTB3 on all capital. Studentized block bootstrap over months (block 3, 5,000 draws). Walk-forward: choose h on 2018-2021, freeze it for the 2022-01 to 2026-09 test with a one-contract embargo. Report the 2018-2021 fit window separately.
- data: daily-history-BTC=F (from 2017-12-18); new bundle coinbase-hourly-BTC-USD (api.exchange.coinbase.com, from 2015); daily-history-ETH=F (from 2021-02) with coinbase-hourly-ETH-USD; fred-DTB3. Later: daily captures of CDE and MBT contracts and IBIT. · min n: 50
- pass: Test-window (2022-2026, about 57 contract-months) bootstrap lower 95% bound of mean excess return > 0, and DSR > 0.95 with n_trials = 10 (2 assets x 4 thresholds + 2 reverse).
- controls: Look-ahead: days to expiry from the exchange calendar; spot sampled at the futures settle time; DTB3 known on the day. Yahoo's front-month roll date is undocumented: drop observations within 3 days of expiry, and cross-check the continuous series against listed contracts (BTCZ26.CME has data from 2024-12) where they overlap. Costs: 20 bp round trip plus CME fees ($2.5-6 per 5-BTC contract). Margin earns T-bills. Survivorship: none (single asset). Multiple testing: 10 trials into the DSR. Regimes: pre/post FTX (2022-11) and pre/post spot ETF (2024-01) reported separately.
- harness: carry_cme_cash_and_carry
- result X-952748a4: not_supported — 57 test contract-months 2022-01..2026-09 (h = DTB3 + 3%, entered 26; exit at the 16:00 London index, the trial's BRR proxy): mean annualised excess over DTB3 on capital +0.14%, one-sided 95% lower bound -0.57% (need > 0); DSR 0.095 (need > 0.95); mean settlement slippage +0.103% of spot; control with the mean 15:00/16:00 London index as exit (not in the verdict): mean +1.01%, lower bound +0.35%, DSR 0.991; claim window 2018-01..2026-09 covered: no, 17 contract-months (2018-01..2019-05) have no settle-synchronous spot; fit window covered from 2019-06 with mean +5.47% over 31 contracts — failed: one-sided 95% studentized block-bootstrap lower bound of mean annualised excess > 0; DSR > 0.95 (n_trials = 10) (not implemented: claim window from 2018-01 covered by settle-synchronous spot)
- note: from the underlying-library library: Crypto cash-and-carry via CME/Coinbase dated futures; harness suggestion: mandel/experiments/carry.py: basis_carry(spot, fut, rf, cost_bps) reusing ratio_reversion bootstrap; add Yahoo BTC=F/ETH=F/MBT=F to the daily-history bundles | verifier: corrected claim/trial

### T-363 · crypto-perpetual-funding-carry

**Claim.** From January 2023 to September 2026 (test window, threshold fixed on 2020-2022), a long BTC / short Deribit BTC-PERPETUAL position held only while trailing 7-day annualized funding exceeds DTB3 + 4% earns an annualized Sharpe of excess return over DTB3 above 1.0, after 10 bp per side and the perp-spot spread at entry and exit.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://arxiv.org/abs/2212.06888, https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name=BTC-PERPETUAL
- statistic: Annualized Sharpe of daily excess returns (funding + spread mark-to-market - costs - DTB3 on capital) in the test window. Also reported: max drawdown and the AR(1) of hourly funding.
- null: Sharpe <= 0 (funding received does not exceed spread losses and costs).
- procedure: Pull Deribit funding (hourly) and perp mark/index prices (get_tradingview_chart_data) from 2020-01. Simulate daily decisions. Stationary block bootstrap (mean block 14 days, 5,000 draws) for the Sharpe CI. Walk-forward: threshold chosen on 2020-2022, frozen for 2023-2026, 7-day embargo. Replicate on Kraken (1 year) now and on CDE after 180 days of capture.
- data: New bundles deribit-funding-BTC/ETH and deribit-perp-mark (reachable); coinbase-hourly-BTC-USD; fred-DTB3; kraken-funding-PF_XBTUSD (1 year); later coinbase-cde-funding daily capture. · min n: 250
- pass: Test-window Sharpe > 1.0 with bootstrap lower bound > 0.3 over at least 250 in-position days, and DSR > 0.95 with n_trials = 12.
- controls: Look-ahead: funding is known only after each hour (available_at = record timestamp). Inverse-contract P&L is converted to USD at each mark. Costs: taker 5-10 bp per side plus the observed spot-perp spread. Liquidation is modeled for linear perps at 2x with the daily mark. Survivorship: BTC and ETH only, but venue survivorship applies (FTX perps no longer exist, so the result is Deribit-specific). Deribit is not US-accessible, so the US claim needs the Kraken/CDE replication. Regimes reported: 2020 crash, 2021 bull, 2022 FTX, 2024+ ETF era. 12 trials deflated.
- harness: carry_perp_funding_threshold
- result X-4644d81f: not_supported — test 2023-01-01..2026-09-30, 1369 days, 372 in position, 118 switches overall (threshold DTB3 + 4%, 10 bp per side per leg): Sharpe of daily excess, pessimistic / central / optimistic spread = -1.35 / -0.64 / 0.40 (need > 1; funding-only -0.80); one-sided 95% lower bound -2.53 / -2.00 / -1.15 (need > 0.3); DSR 0.000 / 0.001 / 0.191 (need > 0.95); perp mark history not archived, spread reconstructed from funding with |u| <= 0.05%; cost read as 10 bp per side for the whole position instead of per leg: Sharpe 0.40 / 1.94 / 4.02; hysteresis control (exit < DTB3) central Sharpe 1.13 — failed: test Sharpe > 1.0 after costs and perp-spot spread (spread-bounded); stationary-bootstrap one-sided 95% lower bound of Sharpe > 0.3 (spread-bounded); DSR > 0.95 with n_trials = 12 (spread-bounded)
- note: from the underlying-library library: Perpetual funding-rate carry (long spot, short perp); harness suggestion: mandel/data/options.py: add deribit_funding_history and coinbase_cde_products snapshot to collect_options_daily; mandel/experiments/carry.py: funding_carry() | verifier: corrected claim/trial

### T-364 · crypto-carry-predicts-crashes

**Claim.** From December 2018 to September 2026, weeks in which the synchronous annualized BTC=F basis sits in its trailing 52-week top decile are followed by a mean 30-day maximum drawdown of BTC-USD at least 10 percentage points deeper than weeks in the bottom half of the trailing distribution.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.bis.org/publ/work1087.htm, https://www.nber.org/papers/w13249
- statistic: Difference in mean forward 30-day maximum drawdown (top-decile weeks minus bottom-half weeks).
- null: No difference: basis state independent of the forward drawdown.
- procedure: Weekly observations. Percentile thresholds from trailing 52 weeks only. Forward 30-day max drawdown from Coinbase daily closes. Block permutation of state labels (block 8 weeks, 5,000 draws) to handle overlapping horizons. Count non-overlapping top-decile episodes (separated by at least 30 days). Report 2018-2021 and 2022-2026 separately.
- data: daily-history-BTC=F, coinbase-hourly-BTC-USD (new), fred-DTB3; ETH=F/ETH-USD for the variant. · min n: 350
- pass: Gap >= 10 points with permutation p < 0.05, the same sign in both halves, and at least 8 non-overlapping top-decile episodes. Otherwise record 'insufficient events'. DSR on the timing rule with n_trials = 4.
- controls: Look-ahead: trailing percentiles only, synchronous spot, roll days excluded. Overlap handled by block permutation. Costs: 10 bp per switch for the timing rule. Survivorship: none. Multiple testing: 4 variants counted. Regime: pre/post 2022 and pre/post ETF reported.
- harness: carry_basis_crash_predictor
- result X-1578602f: not_supported — 321 weeks 2020-05-04..2026-09-14 (31 top-decile, 175 bottom-half): mean 30-day max drawdown 10.6% vs 13.7%, gap -3.2 pp (need >= 10); permutation p 0.9304 (need < 0.05); halves -2.4 / -2.7 pp (need both > 0); 14 non-overlapping episodes (need >= 8); weeks need >= 350; window from 2018-12 covered: no (settle-synchronous spot starts 2019-05, first labelled week 2020-05-04) — failed: depth gap (top decile - bottom half) >= 10 pp; block-permutation p < 0.05; gap positive in both halves (split 2022-01) (not implemented: weeks >= 350 (min_n); claim window from 2018-12 covered by settle-synchronous basis with a 52-week history)
- note: from the underlying-library library: Crypto carry as a crash predictor (basis signal); harness suggestion: mandel/experiments/carry.py: conditional_tail(signal, returns, horizon) with block permutation | verifier: corrected claim/trial

### T-368 · fx-carry-g10-retail

**Claim.** From January 2013 to September 2026, a monthly G10 carry portfolio (long the 3 highest-, short the 3 lowest-yielding of 10 currencies including USD, ranked on one-month-lagged OECD 3-month rates) earns an annualized Sharpe above 0.3 after a 1% annual financing drag per leg and 2 bp per trade.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.oanda.com/us-en/trading/financing-fees/, https://www.cxoadvisory.com/currency-trading/currency-carry-trade-over-the-long-run/
- statistic: Annualized net Sharpe in the test window. Also reported: skewness, max drawdown and the carry-spread t-stat.
- null: Uncovered interest parity: net Sharpe <= 0.
- procedure: Monthly, as in the rule. Walk-forward: weights and filters chosen on 2002-05 to 2012-12, frozen for 2013-2026. Stationary block bootstrap (block 12 months, 5,000 draws).
- data: FRED DEXUSAL, DEXJPUS, DEXUSNZ, DEXNOUS, DEXSZUS, DEXUSEU, DEXCAUS, DEXSDUS, DEXUSUK (daily, verified to 2026-10-09). FRED IR3TIB01 for AU, NZ, CA, NO, SE, CH, US (to 2026-08), JP (starts 2002-04, not 1999) and EZ, GB (stale after 2026-01: splice with a policy-rate or overnight-rate proxy, flagged). fred-DTB3, cboe-VIX-history. · min n: 150
- pass: Test-window Sharpe > 0.3 with bootstrap lower bound > 0, and DSR > 0.95 with n_trials = 6.
- controls: Look-ahead: OECD monthly averages lagged one month. Costs: FRED noon fixing vs broker fill (+2 bp), financing 1% per leg per year. Survivorship: none (fixed G10 universe; EUR from 1999, legacy DEM not used). Regime: pre/post 2008, ZIRP 2009-2021, 2022 hikes and the 2024 yen unwind reported. Stale-series splice flagged. Crash skew reported. 6 trials deflated.
- harness: fx_carry_g10
- result X-a37f0b0b: not_supported — G10 carry (10 incl. USD, top 3 - bottom 3), test 2013-01..2026-09 (165 months), weights equal + VIX > 30 filter chosen on 2002-06..2012-12 (train Sharpe equal 0.33 vs inverse-vol 0.26, with VIX > 30 filter equal 0.38 vs inverse-vol 0.31; test Sharpe of the other weighting with the same filter -0.35; flat in 8 of 165 test months): net Sharpe -0.30 (need > 0.3); stationary-bootstrap 95% interval [-0.66, +0.10] (lower bound need > 0); DSR 0.008 at 6 trials (need > 0.95). Gross Sharpe 0.01, net -1.65%/yr, costs 0.05% trade + 1.67% financing a year, skew -0.26, MDD -27.9%, carry spread 2.39 pp; stale rates spliced by forward fill (flagged): EUR 2026-02..2026-08 (7 mo), GBP 2026-02..2026-08 (7 mo), JPY 2026-08..2026-08 (1 mo); Sharpe through 2026-02 (before the splice) -0.36; one-month gaps filled: USD 2020-04..2020-04 (1 mo) — failed: test-window net Sharpe > 0.3; stationary-bootstrap lower bound > 0; DSR > 0.95 with n_trials = 6
- note: from the underlying-library library: G10 FX carry for US retail (OANDA/IBKR); harness suggestion: mandel/experiments/carry.py: cross_sectional_carry(rates, spots, k=3) with bootstrap; FRED fetch list extended | verifier: corrected claim/trial

### T-379 · vix-futures-roll-yield-carry

**Claim.** Since 2011, holding SVXY/SVIX (short VIX futures ETP) only on days when VIX3M/VIX > 1.05 earns a higher Sharpe than always-short, and a positive return after 10 bp per switch, with maximum drawdown below 50%.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.cxoadvisory.com/volatility-effects/timing-and-hedging-the-roll-return-for-vix-futures/, https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_2024-01-17.csv
- statistic: Sharpe (filtered vs unfiltered), max drawdown, CVaR 1%
- null: filter adds nothing (block permutation of filter days); Sharpe <= 0
- procedure: daily SVXY (2011-10) and SVIX (2022-03) adjusted closes with cboe-VIX and VIX3M histories; Cboe VX CSVs (cdn.cboe.com .../historical_data/VX/VX_<expiry>.csv, verified reachable) for the futures version; block bootstrap (block 21 days); walk-forward 2011-2017 / 2018-2026 so Feb 2018 and Mar 2020 are in the test window
- data: daily-history-SVXY, SVIX, VXX, UVXY, cboe-VIX-history, cboe-VIX3M-history, Cboe VX CSVs (to add) · min n: 2500
- pass: test-window Sharpe > 0.5 with lower bound > 0 and max drawdown < 50%; 4 variants counted
- controls: XIV delisting (survivorship) noted: SVXY changed leverage to -0.5x in Feb 2018 (regime); ETP tracking vs futures; borrow fee for shorting VXX; costs 10 bp; regime dependence central
- harness: svxy_regime
- result X-7ca7aeae: error — harness raised NameError
- result X-de245b0b: not_supported — SVXY in contango only, 2018-: Sharpe 0.16 (lower -0.42), MDD -47% vs always-long Sharpe 0.07, MDD -95% — failed: test Sharpe > 0.5 with lower bound > 0 (not implemented: SVIX arm)
- result X-42cab9a8: not_supported — SVXY in contango only, 2018-, filled at the next open: Sharpe 0.20 (lower -0.40), MDD -48% vs always-long Sharpe 0.07, MDD -95% — failed: test Sharpe > 0.5 with lower bound > 0 (not implemented: SVIX arm)
- note: from the underlying-library library: VIX futures roll-yield carry via ETPs; harness suggestion: mandel/experiments/volatility.py: term_structure_filter(etp, vix, vix3m); add Cboe VX CSV fetcher to mandel/data/options.py | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-435 (verifier-corrected wording)

### T-382 · value-hml-etf-tilt

**Claim.** The Fama-French HML daily factor has a positive mean return over the post-publication window 1993-01 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip (reachable, 200)
- statistic: Annualized mean of daily HML returns with studentized block-bootstrap 95% CI (block 20 trading days, 10,000 resamples). Diagnostics (not part of pass): IWD-IWF net spread mean, capture ratio = slope of spread on HML, rolling 10-year means.
- null: Mean daily HML return over 1993-01 to 2026-09 is <= 0.
- procedure: Download FF daily factors (store the file vintage and download date, because Ken French restates history when CRSP/Compustat are revised); compute mean and bootstrap CI over the fixed window; no fitted parameters, so no walk-forward needed. Build the IWD-IWF spread from Yahoo adjusted closes (2000-06 onward) net of 0.35% blended fees, 0.5% borrow and 5 bp half-spread per rebalance; report capture ratio and rolling means.
- data: Ken French F-F_Research_Data_Factors_daily (verified 200 today); Yahoo IWD, IWF, VLUE, IWN, IWO, SPY adjusted closes. · min n: 8000
- pass: Lower 95% bootstrap bound of the annualized HML mean > 0 over >= 8000 daily observations AND the result survives the family-wide deflation (DSR over all factor-ETF variants tried, about 34 across entries value/quality/low-vol/size/profitability/BAB/factor-momentum/contrarian-timing).
- controls: Look-ahead: FF portfolios formed in June using prior-fiscal-year book equity (6-month lag by construction); pin the data vintage. Survivorship: none (CRSP-based, includes delistings). Costs: applied to the ETF diagnostic (fees, borrow, spreads). Multiple testing: 5 variants here, counted in the family-wide DSR. Regime: report 1993-2006, 2007-2020 and 2021-2026 separately; the 2007-2020 drawdown is the key stress.
- harness: fact_value_hml
- result X-7be8d61a: not_supported — HML 1993-01-04..2026-08-31 [data end 2026-08-31; claim window runs to 2026-09] (n=8473 days): annualised mean +2.36%, 95% studentized block-20 CI -1.73% to +6.61%; family DSR 0.003 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); regimes 1993-2006 +7.18%, 2007-2020 -4.75%, 2021-2026 +8.04%; rolling 10y means -6.89% to +10.25% (54% > 0); diagnostic IWD-IWF net -1.91%/yr, capture ratio 0.69 — failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Value premium (HML) via value/growth ETF pair; harness suggestion: mandel/experiments/underlying.py: add factor_etf_tilt(symbol_long, symbol_short, ff_factor) returning capture ratio, alpha t-stat, bootstrap CI; shared by value/quality/size/profitability/BAB entries. | verifier: corrected claim/trial

### T-383 · quality-qmj-etf-tilt

**Claim.** A beta-hedged long QUAL / short SPY spread has positive monthly alpha against FF5 + momentum over 2013-08 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Intercept of monthly hedged-spread returns regressed on FF5 + UMD, Newey-West t (6 lags); bootstrap CI on annualized alpha. Validity check: loading on AQR QMJ.
- null: FF5+UMD alpha <= 0 after fees and hedge costs.
- procedure: Hedged spread from Yahoo adjusted closes with betas estimated on data to t-1; monthly regression on Ken French factors; separate regression on AQR QMJ to confirm the ETF tracks the intended factor; rolling 36-month alpha for regime display.
- data: Yahoo QUAL/SPHQ/DGRW/SPY; Ken French FF5 + momentum; AQR Quality-Minus-Junk-Factors-Daily.xlsx (verified 200, ~31 MB). · min n: 150
- pass: Alpha t >= 2.0 over >= 150 monthly observations AND QMJ loading > 0.5 (validity) AND survives the family-wide DSR. Power note: with ~158 months, only alphas above ~3%/yr are detectable.
- controls: Look-ahead: betas from t-1; ETF prices tradable. Survivorship: none at ETF level. Costs: 0.15% fee, SPY borrow ~0.3%, 2 bp/month hedge rebalance. Multiple testing: 4 variants into the family-wide DSR. Regime: 2020-2022 growth/rate shock sub-sample reported separately.
- harness: fact_quality_qual
- result X-a957b72c: not_supported — QUAL-SPY hedged spread 2013-11..2026-08 [data end 2026-08; claim window runs to 2026-09] (n=154 months, net of 0.30% borrow, 0.15% fee, 2 bp/month): alpha -1.04%/yr, NW t -1.34 (needs >= 2.0), bootstrap 95% CI -2.70% to +0.47%; QMJ loading not available; family DSR 0.000 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); without re-deducting the in-NAV fee alpha t -1.15; QMJ validity needs the AQR QMJ series (not archived) — failed: FF5+UMD alpha NW t >= 2.0; family-wide DSR > 0.95 (not implemented: QMJ loading > 0.5 (validity))
- note: from the underlying-library library: Quality minus junk via quality ETF; harness suggestion: Reuse factor_etf_tilt; add a factor-regression helper (OLS with Newey-West) on FF5+UMD that every factor-ETF entry calls. | verifier: corrected claim/trial

### T-384 · low-volatility-tilt

**Claim.** Over 2011-11 to 2026-09 USMV has a higher Sharpe ratio than SPY, and the SPLV-SPHB spread has positive mean, consistent with the low-volatility anomaly surviving its publication and ETF launch.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=980865 (Blitz-van Vliet; not fetched, 403)
- statistic: Sharpe ratio difference (USMV - SPY) with Ledoit-Wolf / studentized block-bootstrap CI; mean of SPLV-SPHB spread with bootstrap CI.
- null: Sharpe difference <= 0; spread mean <= 0.
- procedure: Daily adjusted closes; compute Sharpe difference and bootstrap (block 20); FF variance portfolios 1963-2026 for the long-history check; rolling 5-year windows for regime dependence.
- data: Yahoo USMV, SPLV, SPHB, SPY; Ken French variance portfolios (monthly). · min n: 3500
- pass: Lower 95% bound of Sharpe difference > 0 over the full live window and positive in at least 3 of 4 rolling windows.
- controls: Look-ahead: none. Survivorship: none at ETF level. Costs: 0.15-0.25% fees, 0.3% borrow on short leg. Multiple testing: 4 variants into the shared DSR. Regime: separate 2022 rate-shock window; test sensitivity to 10-year yield changes (FRED DGS10).
- harness: low_vol_tilt
- result X-9bfda3b1: not_supported — USMV Sharpe 0.90 vs SPY 0.93 since 2011-10-20 (diff -0.04, lower -0.26); sub-windows +0.22/+0.27/-0.05/-0.35; SPLV-SPHB -2.53 bps/day — failed: Sharpe diff lower bound > 0; positive in >= 3 of 4 windows
- result X-cecc68c9: not_supported — USMV Sharpe 0.90 vs SPY 0.93 since 2011-10-20 (diff -0.04, lower -0.26); sub-windows +0.22/+0.27/-0.05/-0.35; SPLV-SPHB -2.53 bps/day — failed: Sharpe diff lower bound > 0; positive in >= 3 of 4 windows; SPLV-SPHB mean > 0
- result X-bebc64d1: not_supported — USMV excess Sharpe 0.75 vs SPY 0.82 over 2011-11-01..2026-09-30 (3749 days; diff -0.07, lower -0.30); rolling 5-year windows +0.23/+0.29/-0.08/-0.28; SPLV-SPHB -3.23 bps/day — failed: Sharpe diff lower bound > 0; positive in >= 3 of 4 rolling 5-year windows; SPLV-SPHB mean > 0
- note: from the underlying-library library: Low-volatility / minimum-variance tilt; harness suggestion: factor_etf_tilt with a sharpe_diff mode; add FRED DGS10 as a conditioning variable for the regime test. | harness tests every stated criterion it can; a criterion it cannot implement makes the best possible verdict 'inconclusive' (see the reason) | superseded by T-448 (verifier-corrected wording)

### T-385 · size-smb-tilt

**Claim.** The dollar-neutral IJR minus IWM spread has a positive mean return over 2000-06 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.aqr.com/Insights/Research/Working-Paper/Size-Matters-If-You-Control-Your-Junk (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Annualized mean daily spread with studentized block-bootstrap CI (block 20); mechanism check: RMW loading from FF5 regression.
- null: Mean IJR-IWM spread <= 0.
- procedure: Yahoo adjusted closes (dividends included); bootstrap; FF5 regression to confirm RMW loading > 0; June-excluded variant; rolling 5-year means.
- data: Yahoo IJR, IWM, VB, SPY; Ken French SMB and FF5 daily. · min n: 6000
- pass: Lower 95% bound > 0 over >= 6000 daily observations AND RMW loading significantly positive (mechanism) AND survives the family-wide DSR.
- controls: Look-ahead: none (no parameters). Survivorship: none at ETF/factor level. Costs: fee differential (IJR 0.06%, IWM 0.19%) is in NAV; IWM borrow ~0.3%; 5 bp per rebalance. Multiple testing: 4 variants into the family-wide DSR. Regime: 2000-2006 small-cap boom vs 2014-2026 mega-cap era; June reconstitution confound.
- harness: fact_size_ijr_iwm
- result X-d778fa2b: not_supported — IJR-IWM 2000-06-01..2026-09-30 (n=6622 days, 0.3% borrow, 5 bp per monthly reset): annualised mean +0.22%, 95% studentized CI -1.21% to +1.71%; RMW loading +0.18 (NW t +4.68, needs > 1.96); family DSR 0.001 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); June-excluded +0.32%/yr — failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Size premium (small minus big); harness suggestion: factor_etf_tilt; add a two-part verdict (raw vs conditional) in the registry so the parked raw-size claim and the live conditional claim are distinct trials. | verifier: corrected claim/trial

### T-386 · profitability-rmw-tilt

**Claim.** The FF RMW daily factor has a positive mean return over 2013-07 to 2026-09 (after Novy-Marx's 2013 publication).

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched), https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk (fetched; profitability is a QMJ component)
- statistic: Annualized mean of daily RMW with studentized block-bootstrap CI (block 20). Diagnostic: COWZ hedged-spread FF5 alpha with XLE loading.
- null: Mean RMW return over 2013-07 to 2026-09 <= 0.
- procedure: Download RMW daily (record vintage); bootstrap over the fixed window; COWZ diagnostic with sector controls (XLE, XLK).
- data: Ken French F-F_Research_Data_5_Factors_2x3_daily (verified 200) and Portfolios_Formed_on_OP (verified 200); Yahoo COWZ, CALF, SPY, IWM, XLE. · min n: 3000
- pass: Lower 95% bound of the RMW mean > 0 over >= 3000 daily observations AND survives the family-wide DSR.
- controls: Look-ahead: June formation with prior fiscal-year accounting data; pin vintage. Survivorship: none (CRSP). Costs: COWZ 0.49% fee is material in the diagnostic. Multiple testing: 4 variants. Regime: 2021-2023 energy rally; 2020 junk rally.
- harness: fact_profitability_rmw
- result X-895b101f: not_supported — RMW 2013-07-01..2026-08-31 [data end 2026-08-31; claim window runs to 2026-09] (n=3312 days): annualised mean +1.86%, 95% studentized block-20 CI -2.60% to +6.38%; family DSR 0.050 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); regimes 2013-2019 +1.57%, 2020-2026 +2.14%; rolling 5y means -1.89% to +8.26% (98% > 0); diagnostic COWZ hedged FF5+XLE+XLK alpha +0.63%/yr (t +0.35), XLE loading +0.11 — failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Profitability / cash-flow tilt (RMW); harness suggestion: factor_etf_tilt + factor regression helper; add sector-ETF controls (XLE, XLK) as optional regressors. | verifier: corrected claim/trial

### T-387 · betting-against-beta-etf

**Claim.** The ex-ante beta-neutral SPLV-levered / SPHB-delevered spread has a positive mean excess return after financing and borrow over 2011-06 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.aqr.com/Insights/Research/Journal-Article/Betting-Against-Beta (fetched), https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Daily (fetched)
- statistic: Annualized mean of the net spread (financing at DGS3MO + 1.0% broker spread, 0.5% borrow) with block-bootstrap CI; validity check: realised full-sample beta of the spread to SPY; secondary: FF5 alpha (does it survive RMW/CMA?).
- null: Spread mean <= 0; if |ex-post beta| >= 0.1 the trial is invalid, not passed.
- procedure: Rolling betas to t-1 from Yahoo adjusted closes; construct spread with financing; bootstrap; FF5 regression; compare with AQR BAB post-2014; rolling 3-year means.
- data: Yahoo SPLV, USMV, SPHB, SPY; FRED DGS3MO; AQR Betting-Against-Beta-Equity-Factors-Daily.xlsx (verified 200). · min n: 3500
- pass: Lower 95% bound > 0 over >= 3500 days AND |ex-post beta| < 0.1 AND survives the family-wide DSR.
- controls: Look-ahead: betas to t-1. Survivorship: none at ETF level. Costs: broker margin rate (not T-bill), borrow, 2 bp rebalance. Multiple testing: 4 variants; trials correlated with low-volatility-tilt (same ETFs). Regime: 2020 high-beta rebound; 2022 rate hikes.
- harness: fact_bab_etf
- result X-4f844e88: not_supported — BAB spread 2011-08-03..2026-09-30 (n=3812 days, 289 resets, financing at bill + 1.0%, 0.5% borrow, 2 bp per reset; 67 flat days held in cash because a reset found a trailing beta <= 0 or missing; held ex-ante beta within +/-0.150): annualised mean +0.71%, 95% studentized CI -7.28% to +8.58%; ex-post beta +0.012 (needs |b| < 0.1); family DSR 0.008 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); diagnostic FF5 alpha -0.92%/yr (t -0.26), corr with AQR BAB since 2014 0.46 — failed: lower 95% bound of the annualised mean net excess return > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Betting against beta (BAB) with low/high-beta ETFs; harness suggestion: Add beta_neutral_spread() to underlying.py (rolling beta, leverage, financing) and reuse for any pair; ingest AQR BAB Excel through the same fetch layer as Ken French. | verifier: corrected claim/trial

### T-388 · factor-momentum-rotation

**Claim.** Time-series factor momentum (hold each FF/AQR factor only after a positive 12-1 return) has a higher Sharpe ratio than the static equal-risk portfolio of the same factors over 1964-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w25551 (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Sharpe difference (timed minus static), monthly, with studentized block-bootstrap CI (block 12 months); deflated Sharpe over all formation variants; post-2019 window reported separately.
- null: Sharpe difference <= 0.
- procedure: Parameters fixed ex ante (12-1, monthly). 1-month skip embargo between formation and holding. Count 1-, 3-, 6-, 12-month formations and the cross-sectional rule as trials; PBO via CSCV on the FF sample. ETF rotation 2013-2026 and the 2019-2026 post-publication window are reported as out-of-sample diagnostics.
- data: Ken French monthly factors (FF5 + UMD); AQR BAB monthly; Yahoo factor ETFs. · min n: 600
- pass: Lower 95% bound of the Sharpe difference > 0 over >= 600 months AND DSR > 0.95 with all 5 variants counted AND PBO < 0.5; post-2019 point estimate reported (sign expected positive).
- controls: Look-ahead: 1-month skip; vol weights to t-1. Survivorship: none. Costs: ~2 switches/yr per factor at 5 bp, factor turnover itself not costed in FF series (note: paper factors are pre-cost). Multiple testing: formation windows and rules counted. Regime: 2009 momentum crash, 2020-2021 value reversal.
- harness: fact_factor_momentum
- result X-1ee8d7ce: not_supported — HML/SMB/RMW/CMA/UMD/BAB 1964-07..2026-07 (n=745 months): timed 12-1 Sharpe 1.04 vs static 1.08, difference -0.04 (95% studentized CI -0.24 to +0.17); DSR 0.080 over 5 variants (annualised Sharpe of each timed-minus-static series: ts_12_1 +0.00, ts_1 -0.33, ts_3 -0.16, ts_6 -0.14, xs_12_1 -0.37); PBO 0.29; post-2019 difference 0.06 (reported) — failed: lower 95% bound of the Sharpe difference > 0; DSR > 0.95 with all 5 variants counted
- note: from the underlying-library library: Factor momentum rotation across factor ETFs; harness suggestion: Reuse the deflated trend-rule search from T-58 (overfit.py) with factor series as the input; add ETF implementation as the holdout. | verifier: corrected claim/trial

### T-389 · contrarian-factor-timing

**Claim.** Tilting a static equal-risk FF5+UMD portfolio by 60-month factor-return reversal z-scores raises its Sharpe ratio over 1968-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.aqr.com/Insights/Research/Journal-Article/Contrarian-Factor-Timing-is-Deceptively-Difficult (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Sharpe difference (timed minus static), monthly, studentized block-bootstrap CI (block 12).
- null: Sharpe difference <= 0.
- procedure: Pre-registered windows {36, 60} and sets {all, ex-HML}, plus the value-spread variant: 5 trials. Expanding-window z-scores only; one-quarter embargo between signal and rebalance; deflated Sharpe over 5 trials.
- data: Ken French monthly FF5 + UMD; 6_Portfolios_2x3 BE/ME section (verified 200). · min n: 600
- pass: Lower 95% bound > 0 AND DSR > 0.95 over 5 trials; otherwise parked with reason 'contrarian factor timing adds nothing beyond static exposure' (the expected outcome).
- controls: Look-ahead: expanding windows; BE/ME uses fiscal-year t-1 book known by June t. Survivorship: none. Costs: quarterly tilts at 5 bp. Multiple testing: 5 trials. Regime: 2018-2020 value drawdown is the key stress.
- harness: fact_contrarian_timing
- result X-fb91d2c6: not_supported — Mkt-RF/SMB/HML/RMW/CMA/UMD 1968-01..2026-08 (n=704 months): 60-month z tilt Sharpe 1.07 vs static 1.11, difference -0.03 (95% studentized CI -0.12 to +0.04); DSR 0.056 over 5 trials not decided: value-spread trial not computable (6_Portfolios_2x3 BE/ME not archived), so only 4 of the 5 trial Sharpes are in the variance (reported only); annualised Sharpe of each timed-minus-static series z60_all -0.13, z60_exHML -0.13, z36_all -0.05, z36_exHML +0.02 — failed: lower 95% bound of the Sharpe difference > 0 (not implemented: DSR > 0.95 over 5 trials (value-spread trial not computable))
- note: from the underlying-library library: Contrarian factor timing (value-spread / long-term factor reversal); harness suggestion: Small addition to the factor-momentum harness: z-score tilt vs static baseline, same bootstrap. | verifier: corrected claim/trial

### T-397 · esg-exclusion-sin-premium

**Claim.** An equal-weight portfolio of FF 'Smoke', 'Beer' and 'Guns' industries has positive FF5 alpha over 2009-01 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w28940 (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Monthly FF5 alpha (Newey-West t) of the sin portfolio excess return; bootstrap CI; CAPM alpha alongside.
- null: FF5 alpha <= 0.
- procedure: Ken French 48 industry monthly returns (value-weighted); regress on FF5; split 1965-2008 vs 2009-2026; ETF and single-stock variants as live checks.
- data: Ken French 48_Industry_Portfolios (verified 200) and FF5; Yahoo ESGU, SPYX, SPY, sin names. · min n: 200
- pass: FF5 alpha t >= 2 over >= 200 post-2009 months.
- controls: Look-ahead: none (industry codes are point-in-time in CRSP). Survivorship: FF industry portfolios include delistings; the single-stock basket is survivor-picked today (flag, context only). Costs: 5 bp per rebalance; ESGU borrow ~0.5%. Multiple testing: 4 variants. Regime: 2017-2022 tobacco multiple compression; 2022 defence rally.
- harness: fact_sin_alpha
- result X-da0f8875: not_supported — Smoke/Beer/Guns EW 2009-01..2026-08 [data end 2026-08; claim window runs to 2026-09] (n=212 months): FF5 alpha +3.08%/yr, NW t +1.41 (needs >= 2), bootstrap 95% CI -1.77% to +7.45%; CAPM alpha +4.80%/yr (t +1.88); 1965-2008 FF5 alpha -0.88%/yr (t -0.51) — failed: FF5 alpha NW t >= 2
- note: from the underlying-library library: ESG exclusion / sin-stock premium; harness suggestion: Reuse factor regression helper on Ken French industry portfolios; add an industry-portfolio loader to data/fetch.py. | verifier: corrected claim/trial

### T-421 · highlow-spread-liquidity-shock

**Claim.** On SPY 2000-2026, a +2 sigma Corwin-Schultz spread shock predicts a 20-day forward return at least 1 percentage point above the unconditional mean, after controlling for the same-day VIX change.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/j.1540-6261.2012.01729.x (Corwin and Schultz 2012, A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.jfineco.2022.09.004 (Ranaldo and Santucci de Magistris 2022, realized Amihud measure)
- statistic: Shock coefficient in a regression of 20-day forward return on the shock indicator and the same-day VIX change (overlapping windows, block-bootstrap CI). Walk-forward Sharpe of the rule vs a VIX-only rule.
- null: Shock coefficient <= 0 given the VIX control, and no improvement over the VIX-only rule.
- procedure: Event regression with a 20-day-block bootstrap. Nested comparison against a VIX-threshold rule with compare_strategies. 32 cells into DSR and PBO.
- data: Yahoo daily OHLCV; CBOE VIX history (in store); Coinbase daily candles for BTC/ETH; Kalshi candles for the event variant. · min n: 60
- pass: At least 60 non-overlapping SPY shock events (at least 40 on BTC). Coefficient >= 1 point with p < 0.05. DSR >= 0.95. Beats the VIX-only rule out of sample.
- controls: Look-ahead: estimators use days t-1 and t only; VIX at the same close. Survivorship: not applicable. Costs: SPY 1 bp; BTC 0.5-1% round trip at retail. Multiple testing: 32 cells. Regime: report excluding 2008 and 2020.
- harness: ohlc_cs_spread_shock
- result X-ea63a856: not_supported — SPY 2000-01-03..2026-09-14: 356 shock days (CS spread > +2 sd of trailing 60), 131 non-overlapping events (need 60); 20-day forward-return coefficient +0.13 points (95% CI -0.70..+0.88; need >= 1) with p=0.373 vs <= 0 (p=0.980 vs <= 1 point), controlling for the VIX change; excluding 2008/2020 +0.32 points; rule DSR 0.344 over 32 cells; out-of-sample Sharpe vs VIX-only rule -0.23 (one-sided 95% lower -0.48) — failed: shock coefficient >= 1 point; p < 0.05 (H0 coefficient <= 0); DSR >= 0.95 over 32 cells; beats the VIX-only rule out of sample
- note: from the underlying-library library: Liquidity-shock timing from daily high-low spread estimates; harness suggestion: Implement corwin_schultz() and amihud() helpers in mandel/experiments/volatility.py (needs highs/lows from the Yahoo rows); timing rule via the ma_rule_returns pattern; compare_strategies against a VIX rule; pbo_cscv on the grid. | verifier: corrected claim/trial

### T-423 · perp-funding-basis-sentiment

**Claim.** Top-decile Deribit BTC funding (trailing-30-day z-score of daily mean interest_8h) predicts a 7-day BTC spot return at least 2 percentage points below the unconditional 7-day mean.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://www.deribit.com/api/v2/public/get_funding_rate_history (public endpoint; same host as the DVOL feed Mandel already pulls), Alexander, Choi, Park, Sohn 2020, BitMEX bitcoin derivatives: Price discovery, informational efficiency, and hedging effectiveness, Journal of Futures Markets 40(1) (publisher page returned 403 from this host)
- statistic: Mean 7-day forward return on top-decile days minus the unconditional mean, with block-bootstrap CI. Net Sharpe of the contrarian and carry rules.
- null: Difference >= 0 (stationary block bootstrap, 7-day blocks, 5,000 draws).
- procedure: Pull hourly funding from 2019-06. Event study with overlapping windows. 2019-22 vs 2023-26. 24 cells into DSR.
- data: Deribit public/get_funding_rate_history (verified: hourly records with index_price, interest_1h, interest_8h); Deribit futures prices; Coinbase/Yahoo BTC-USD, ETH-USD daily. · min n: 200
- pass: At least 200 top-decile days and at least 30 non-overlapping events. Difference <= -2 points with p < 0.05 out of sample. DSR >= 0.95. Carry variant reported with its maximum drawdown.
- controls: Look-ahead: daily mean uses only hours up to 00:00 UTC; entry at the next hourly bar. Survivorship: not applicable. Costs: spot 0.5-1% round trip retail; perp 5 bps taker (not available to US persons). Multiple testing: 24 cells. Regime: bull vs bear; liquidation-cascade days (|return| > 10%).
- harness: carry_funding_sentiment
- result X-6eca056b: not_supported — 2469 days (261 top-decile, 112 non-overlapping events): full-sample 7-day return top +0.84% vs all +1.05%, difference -0.21 pp; out-of-sample 2023+ difference +0.10 pp (need <= -2) with p 0.5741 (need < 0.05; 169 top days); in-sample difference -0.78 pp; DSR of contrarian vs buy-and-hold 0.000 (need >= 0.95) — failed: out-of-sample difference <= -2 pp; out-of-sample stationary-bootstrap p < 0.05 (H0: difference >= 0); DSR >= 0.95 of contrarian-minus-buy-and-hold daily returns (n_trials = 24)
- note: from the underlying-library library: Crypto perpetual basis and funding as positioning sentiment; harness suggestion: Add deribit_funding_history() beside deribit_dvol_history in mandel/data/options.py (page backward like DVOL); event study and rule P&L via underlying.py helpers; costs through backtest_eval inputs. | verifier: corrected claim/trial

### T-427 · intraday-half-hour-momentum

**Claim.** On SPY from 2023-11 to 2026-10, holding SPY from 15:30 to 16:00 ET in the direction of the previous-close-to-10:30 return earns a positive mean net return after 2 bps round-trip cost.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.jfineco.2018.05.009 (Gao, Han, Li, Zhou 2018, Market intraday momentum), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.jfineco.2021.04.029 (Baltussen, Da, Lammers, Martens 2021, Hedging demand and market intraday momentum)
- statistic: Mean net daily return with HAC t-stat and bootstrap CI. Diagnostic: OLS slope of the last half-hour return on r1.
- null: Mean net return <= 0.
- procedure: Fixed rule on Yahoo 1h bars. 60 cells into DSR. BTC session variant on Coinbase hourly over 2016-2026 as a longer replication.
- data: Yahoo chart interval=1h range=730d (verified: 2023-11-15 to 2026-10-14, about 725 trading days, 7 bars a day); Yahoo daily bars for the official close; Coinbase hourly BTC-USD. · min n: 500
- pass: At least 500 days. Mean net return > 0 with p < 0.05 after deflation over 60 cells. Same sign on QQQ and IWM.
- controls: Look-ahead: r1 known at 10:30; the position opens at the 15:30 bar open; the exit uses the daily official close, not the 15:30 bar's last trade. Survivorship: not applicable. Costs: 2 bps round trip. Multiple testing: 60 cells. Regime: FOMC/CPI and option-expiration days (gamma mechanism).
- harness: hourly_half_hour_momentum
- result X-34f40b31: not_supported — SPY 2023-11-15..2026-10-13, n=720 sessions (7 early closes, 1 day(s) without the 09:30 bar, 1 without the 15:30 bar and 1 without an available daily bar excluded); archived window 2023-11-15..2026-10-13, inside the claimed 2023-11..2026-10. Rule sign(prev close->10:30) held 15:30 bar open->official close: mean net -2.09 bps/day (gross -0.09 bps, cost 2 bps round trip on 720 trades), HAC t -2.58, 95% block-bootstrap CI [-3.71, -0.55] bps, raw p 0.993, annualised net Sharpe -1.49; DSR over 60 cells 0.000 -> deflated p 1.000 (needs < 0.05); QQQ mean net -2.42 bps (n=720, HAC t -2.26); IWM mean net -1.04 bps (n=720, HAC t -1.07); diagnostic slope of the last half hour on r1 -0.0040 (HAC t -0.22) — failed: SPY mean net return > 0; deflated p < 0.05 over 60 cells; same sign on QQQ and IWM (mean net return > 0 on both)
- note: from the underlying-library library: Market intraday momentum: first half-hour predicts last half-hour; harness suggestion: Yahoo interval=1h pilot fetch; regression and rule P&L in mandel/experiments/intraday_equity.py; BTC session variant via coinbase_candles(granularity=3600). | verifier: corrected claim/trial

### T-428 · closing-auction-reversal

**Claim.** On SPY from 2023-11 to 2026-10, the next close-to-open return has a slope of at most -0.2 on the last-half-hour return (15:30 to official close).

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, Bogousslavsky and Muravyev 2023, Who trades at the close? Implications for price discovery and liquidity, Journal of Financial Markets 66 (publisher page returned 403 from this host)
- statistic: OLS slope of close-to-open on L, with HAC t-stat and bootstrap CI. Reversal-leg net Sharpe.
- null: Slope >= 0 (no reversal beyond the overnight drift).
- procedure: Yahoo 1h bars plus daily close and open. The regression controls for the unconditional overnight mean and for the day's open-to-15:30 return. 32 cells deflated.
- data: Yahoo interval=1h range=730d (15:30 bar verified) and daily OHLC for SPY, QQQ, IWM, GLD. Imbalance feeds are paid. · min n: 500
- pass: At least 500 days. Slope <= -0.2 with p < 0.01 after deflation. Reversal-leg net Sharpe > 0.5.
- controls: Look-ahead: decision information ends at 15:45; the MOC cutoff is honoured; L is measured to the official close, which is the fill price. Survivorship: not applicable. Costs: no spread at the close print; 1 bp at the open. Multiple testing: 32 cells. Regime: month-end, index rebalances, triple witching.
- harness: hourly_closing_reversal
- result X-749ca45c: not_supported — SPY 2023-11-15..2026-10-12, n=720 close-to-next-open pairs (7 early closes, 1 day(s) without the 15:30 bar and 1 without an available daily bar excluded; 1 without an archived next open); archived window 2023-11-15..2026-10-12, inside the claimed 2023-11..2026-10. OLS CO(t+1) = a + b L + c R(open->15:30): b = -0.084 (HAC t -0.48, one-sided p 0.3166, Sidak over 32 cells 1.0000, 95% block-bootstrap CI [-0.416, +0.253]) vs b <= -0.2 and deflated p < 0.01; a = +6.22 bps, c = -0.039; univariate b -0.096; reversal leg sized on the 15:45 state not built (1h bars hold no price between 15:30 and the close); LOOK-AHEAD proxy sized on L to the official close: net +1.92 bps/day, annualised Sharpe +0.50, diagnostic only; QQQ slope -0.129 (HAC t -0.72, n=720); IWM slope -0.148 (HAC t -1.01, n=720); GLD slope -0.831 (HAC t -1.64, n=720) — failed: slope <= -0.2; deflated (Sidak, 32 cells) one-sided p < 0.01 (not implemented: reversal-leg net Sharpe > 0.5 sized on the 15:45 state (needs sub-hourly bars))
- note: from the underlying-library library: Closing-auction imbalance and close-to-open reversal; harness suggestion: Pilot on Yahoo interval=1h bars in mandel/experiments/intraday_equity.py; full version waits for minute data; register the proxy and feed versions as separate trials. | verifier: corrected claim/trial

### T-431 · em-fx-carry

**Claim.** From January 2013 to September 2026, a monthly carry portfolio over the 10 G10 currencies plus MXN and ZAR (top 3 minus bottom 3 by lagged OECD 3-month rates) earns an annualized Sharpe above 0.3 after retail financing admin and EM spreads.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.nber.org/papers/w14082, https://www.oanda.com/us-en/trading/financing-fees/
- statistic: Annualized net Sharpe in the test window. Also reported: skewness and max drawdown.
- null: Net Sharpe <= 0.
- procedure: As in fx-carry-g10-retail. Walk-forward: 2002-2012 fit, 2013-2026 test. Stationary block bootstrap (block 12 months).
- data: FRED DEX series (G10 + DEXMXUS from 1993, DEXSFUS, DEXKOUS), IR3TIB01 rates as listed, fred-DTB3. · min n: 150
- pass: Test Sharpe > 0.3 with bootstrap lower bound > 0, and DSR > 0.95 with n_trials = 4 plus the G10 entry's 6 (shared deflation).
- controls: Look-ahead: rates lagged one month. Costs: EM financing 1-2% admin plus spread. Survivorship: none (fixed list chosen ex ante). Crash skew reported. Regimes: 2013 taper, 2015, 2020, 2024 yen unwind.
- harness: fx_carry_em
- result X-5357a646: not_supported — G10 + MXN + ZAR carry (top 3 - bottom 3), test 2013-01..2026-09 (165 months), weights equal, no filter, chosen on 2002-06..2012-12 (train Sharpe equal 0.23 vs inverse-vol 0.17, with VIX > 30 filter equal 0.21 vs inverse-vol 0.19; test Sharpe of the other weighting with the same filter 0.12): net Sharpe 0.15 (need > 0.3); stationary-bootstrap 95% interval [-0.30, +0.64] (lower bound need > 0); DSR 0.155 at 10 trials (need > 0.95). Gross Sharpe 0.44, net +1.11%/yr, costs 0.03% trade + 2.24% financing a year, skew -0.90, MDD -23.6%, carry spread 5.27 pp; stale rates spliced by forward fill (flagged): EUR 2026-02..2026-08 (7 mo), GBP 2026-02..2026-08 (7 mo), JPY 2026-08..2026-08 (1 mo); Sharpe through 2026-02 (before the splice) 0.10; one-month gaps filled: USD 2020-04..2020-04 (1 mo) — failed: test-window net Sharpe > 0.3; stationary-bootstrap lower bound > 0; DSR > 0.95 with n_trials = 10
- note: from the underlying-library library: Emerging-market FX carry (high-yielders vs funders); harness suggestion: Reuse cross_sectional_carry() with an extended universe. Add DEXMXUS, DEXSFUS, DEXKOUS and the EM IR3TIB01 series to the FRED list. | added by the verifier pass

### T-435 · vix-futures-roll-yield-carry

**Claim.** From October 2011 to September 2026, holding SVXY only on days after VIX3M/VIX > 1.05 (else SGOV) earns a higher annualized Sharpe than always holding SVXY, after 10 bp per switch.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.cxoadvisory.com/volatility-effects/timing-and-hedging-the-roll-return-for-vix-futures/, https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_2024-01-17.csv
- statistic: Paired Sharpe difference (filtered - always-on). Also reported: max drawdown and 1% CVaR.
- null: Sharpe difference <= 0.
- procedure: Daily SVXY adjusted closes with Cboe VIX and VIX3M histories (signal at close t, position from close t+1). Paired stationary block bootstrap (block 21 days, 5,000 draws). Walk-forward: the 1.05 threshold is fixed ex ante; 2011-2017 reported as in-sample, 2018-2026 as test (includes 2018-02 and 2020-03). Report the regime before and after SVXY's 2018-02-27 leverage change separately.
- data: daily-history-SVXY, SVIX, VXX; cboe-VIX-history, cboe-VIX3M-history; Cboe VX CSVs (verified reachable) for the futures version. · min n: 2500
- pass: Test-window (2018-2026) Sharpe difference > 0 with bootstrap p < 0.05, and DSR > 0.95 with n_trials = 6.
- controls: Survivorship: XIV, terminated in 2018, is excluded; including its history would change the always-on benchmark, so it is reported as a sensitivity. SVXY's leverage change is a regime break. Costs: 10 bp per switch and the ETP expense ratio. Look-ahead: signal at t, trade at t+1. Regime dependence is central. 6 trials.
- harness: svxy_v2
- result X-9515b742: not_supported — SVXY contango filter vs always, 2018-: Sharpe diff +0.09 (one-sided 95% lower -0.58), DSR 0.24 — failed: Sharpe diff > 0 with one-sided p < 0.05; DSR > 0.95
- result X-20fc541b: not_supported — SVXY contango filter (position from close t+1, cash at T-bill) vs always, test 2018-01-01..2026-09-30 (2198 days; claim window 3768 days vs min_n 2500): excess Sharpe -0.17 vs 0.01, diff -0.18 (one-sided 95% lower -0.67), DSR 0.19 — failed: Sharpe diff > 0 with one-sided p < 0.05; DSR > 0.95
- note: from the underlying-library library: VIX futures roll-yield carry via ETPs; harness suggestion: mandel/experiments/volatility.py: term_structure_filter(etp, vix, vix3m, threshold) with a paired bootstrap. Add a Cboe VX CSV fetcher to mandel/data/options.py. | verifier-corrected restatement of T-379, whose verdict tested the earlier wording and stands

### T-437 · gold-seasonality

**Claim.** Over 2011-2026, after Baur's 1980-2010 sample, GLD's mean daily return in September-November exceeds its mean in the other nine months by at least 5 bps per day.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/riibaf/v27y2013i1p1-11.html, https://ideas.repec.org/a/vrs/ijomae/v60y2024i3p157-172n1001.html
- statistic: Mean daily return difference (bps), Sep-Nov minus other months.
- null: Equal means. Studentized block bootstrap (block 21) of the month-flagged daily series.
- procedure: Primary on GLD 2011-2026 (out-of-sample to Baur). 2004-2010 GLD is reported as in-sample. Halves 2011-2018 / 2019-2026. The 6 non-primary variants are Holm-adjusted; the grid gets Bonferroni over 12.
- data: daily-history-GLD, SLV, GC-F (stored); GDX via Yahoo. · min n: 2500
- pass: Difference > 5 bps/day with p < 0.05 and both halves positive. The pre-registered expectation is failure (Potrykus-Augustynowicz).
- controls: Look-ahead: none. Survivorship: n/a. Costs: 1-2 round trips/yr at 1-3 bps plus the pro-rated 0.40% expense ratio (GLD). Multiple testing: 7 variants plus a 12-month grid. Regime: halves; the 2011 top, 2020 and 2024-26 rallies flagged; GC=F roll artifacts removed.
- harness: gold_autumn_v2
- result X-0424429c: not_supported — GLD 2011- Sep-Nov minus other months -8.00 bps/day (p=0.988), halves -10.55/-5.27 — failed: difference > 5 bps/day; p < 0.05; both halves positive
- result X-0dae2bc6: not_supported — GLD 2011- Sep-Nov minus other months -8.00 bps/day (p=0.988), halves -10.55/-5.27 — failed: difference > 5 bps/day; p < 0.05; both halves positive
- note: from the underlying-library library: Gold seasonality: autumn effect and the published reversal; harness suggestion: events.py: month_set_effect(days, closes, months={9,10,11}, start='2011-01-01') sharing code with half_year_effect; month_of_year_grid; futures_roll_mask(days, closes) for GC=F. | verifier-corrected restatement of T-356, whose verdict tested the earlier wording and stands

### T-438 · opex-week-triple-witching

**Claim.** Over 1993-2026, SPY's return over monthly options-expiration weeks (Friday close before, to the expiration-day close) exceeds the mean return of all other Friday-to-Friday weeks by at least 20 bps, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/eee/jbfina/v37y2013i11p4226-4240.html, https://rpc.cfainstitute.org/research/financial-analysts-journal/1991/expiration-day-effects-what-has-changed
- statistic: Mean opex-week return minus mean other-week return (bps).
- null: Equal weekly means. Studentized block bootstrap (block 4 weeks) of the weekly series.
- procedure: Compute third Fridays (with the holiday rule); weekly returns Friday close to Friday close; halves 1993-2009 / 2010-2026. The 6 non-primary variants are Holm-adjusted.
- data: daily-history-SPY, QQQ, IWM, BTC-USD, GLD (stored). · min n: 350
- pass: Excess > 20 bps with p < 0.05 and both halves positive.
- controls: Look-ahead: none. Survivorship: n/a. Costs: 12 round trips/yr at 1-2 bps. Multiple testing: 1 primary plus 6 Holm. Regime: halves; weekly options (2005+), and SPX dailies/0DTE (2022+) flagged as mechanism changes.
- harness: opex_week_v2
- result X-b691f14a: not_supported — SPY opex week +24.4 vs other weeks +23.2 bps (excess +1.2, p=0.487, halves +18.1/-15.8) — failed: excess > 20 bps; p < 0.05; both halves positive
- result X-9487020c: not_supported — SPY opex week +21.7 vs other weeks +22.9 bps (excess -1.2, p=0.530, halves +19.8/-22.1) — failed: excess > 20 bps; p < 0.05; both halves positive
- note: from the underlying-library library: Options-expiration week and triple witching; harness suggestion: events.py: third_fridays(days, holidays) and last_fridays(days); week_type_effect(days, closes, week_flag_fn) producing weekly returns and the bootstrap; the witching day reuses event_day_effect. | verifier-corrected restatement of T-353, whose verdict tested the earlier wording and stands

### T-439 · quarter-end-window-dressing

**Claim.** Over 2000-2026, IWM's return on the last trading day of each quarter exceeds its return on the first trading day of the next quarter by at least 20 bps on average, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/bla/jfinan/v57y2002i2p661-693.html, https://ideas.repec.org/f/pca244.html
- statistic: Mean paired difference (last-day return minus next-day return) across quarter ends (bps).
- null: Zero difference. Bootstrap over quarter-end pairs. Placebo: the same paired difference at non-quarter month ends.
- procedure: Flag quarter-end last/first trading days from the trading calendar. Halves 2000-2012 / 2013-2026. ^RUT 1987-2001 reported separately as the pre-publication benchmark. 6 variants count as trials (Holm).
- data: daily-history-IWM (2000-), daily-history--RUT (1987-09-10-), daily-history-SPY, QQQ (all stored). · min n: 100
- pass: Difference > 20 bps, bootstrap p < 0.05, both halves positive, and placebo difference not significant (p > 0.1).
- controls: Look-ahead: calendar only. Survivorship: n/a for ETFs/indexes. Costs: 8 trades/yr at 1-3 bps; IWM easy to borrow. Multiple testing: 6 variants, Holm. Regime: halves and pre/post-2002 publication split.
- harness: quarter_end_reversal
- result X-66ce388f: not_supported — IWM quarter-end minus next-day -17.1 bps over 106 quarters (p=0.824), halves -55.6/+18.5; placebo month ends -26.7 bps (p=0.956) — failed: mean > 20 bps; bootstrap p < 0.05; both halves positive
- result X-a1030409: not_supported — IWM quarter-end minus next-day -21.1 bps net of 4 bps costs over 106 quarters (p=0.876), halves -59.6/+14.5; placebo month ends -26.7 bps (two-sided p=0.088) — failed: mean > 20 bps net of costs; bootstrap p < 0.05; both halves positive; placebo not significant (two-sided p > 0.1)
- note: from the underlying-library library: Quarter-end window dressing and 'leaning for the tape'; harness suggestion: events.py: quarter_end_pairs(days) -> list of (last_idx, first_idx); paired_day_effect(closes, pairs, placebo_pairs, n_boot=5000); run on IWM, ^RUT, SPY. | verifier-corrected restatement of T-346, whose verdict tested the earlier wording and stands

### T-440 · santa-claus-rally

**Claim.** Over 1973-2026, after the window was published, ^GSPC's cumulative return over the last five trading days of December plus the first two of January exceeds the mean of all other 7-trading-day windows by at least 1 percentage point.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://en.wikipedia.org/wiki/Santa_Claus_rally, https://pro.thestreet.com/portfolio/what-are-the-actual-odds-of-a-santa-claus-rally
- statistic: Mean Santa-window 7-day return minus the mean of non-overlapping 7-day windows in the same years (pp).
- null: The window is unexceptional. Placement bootstrap: draw one random 7-day window per year (avoiding the Santa window) 10,000 times and compare means. Barometers: binomial with p equal to the unconditional probability of a positive year.
- procedure: Per year 1973-2026 (n = 53). Halves 1973-1999 / 2000-2026. 1950-1972 is reported as in-sample. A TOM-excluded sensitivity removes overlap with T-59. 6 variants are secondary.
- data: daily-history--GSPC (stored from 1927-12-30; note social.yahoo_history with period1=0 truncates to 1970, so re-fetches need a negative period1), SPY, IWM, QQQ, BTC-USD, GLD (stored). · min n: 50
- pass: Excess > 1 pp with placement-bootstrap p < 0.05 over 1973-2026 and both halves positive; barometers pass only above the drift-adjusted binomial 95th percentile.
- controls: Look-ahead: none; the window was chosen by Hirsch on pre-1972 data, so only post-1972 counts. Survivorship: n/a. Costs: 1 round trip/yr. Multiple testing: 6 variants. Regime: halves; TOM overlap removed as a sensitivity.
- harness: santa_v2
- result X-df833342: not_supported — post-publication (1973-) Santa excess +0.86 pp over 53 years (placement p=0.010), halves +1.36/+0.37 — failed: excess > 1 pp
- result X-3a7fb152: not_supported — post-publication (1973-) Santa excess +0.86 pp over 53 years (placement p=0.010), halves +1.36/+0.37 — failed: excess > 1 pp
- note: from the underlying-library library: Santa Claus rally and turn-of-year indicators; harness suggestion: events.py: fixed_window_vs_random(days, closes, window_fn, length=7, n_boot=10000, start_year=1973); barometer_sign_test(days, closes, rule). | verifier-corrected restatement of T-350, whose verdict tested the earlier wording and stands | post-publication window: +0.86 pp (p 0.010), significant but under the 1 pp bar; the 1928- reading (+1.38 pp, T-350) is dominated by the pre-publication years. | 2026-10-15: after the harness audit added the claim's SPY >= 1 pp gate, T-350 was re-run and is now not_supported (SPY +0.49 pp over 33 years); T-350 and this restatement now agree.

### T-441 · sell-in-may-halloween

**Claim.** Over 1928-2026, ^GSPC's mean monthly price return in November-April exceeds its mean in May-October by at least 50 bps per month, and the difference is positive over November 2002-October 2026 (post-publication).

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.cxoadvisory.com/calendar-effects/halloween-indicator-out-of-sample-test, https://www.tias.edu/docs/default-source/Kennisartikelen/ssrn-id2154873.pdf
- statistic: Mean monthly return difference, Nov-Apr minus May-Oct (bps/month).
- null: Equal means. Studentized block bootstrap of the monthly series (block 6 months).
- procedure: Monthly returns from daily closes. Full sample plus the post-2002 subsample. DSR over 7 variants plus the 12-month grid = 19 trials.
- data: daily-history--GSPC (stored, 1927-), SPY, QQQ, IWM, EFA, TLT, GLD, XLB..XLY, BTC-USD (stored); DTB3 (stored) for the cash leg. · min n: 360
- pass: Difference > 50 bps/month with p < 0.05 over 1928-2026 AND the 2002-2026 difference > 0.
- controls: Look-ahead: none. Survivorship: n/a. Costs: 2 round trips/yr; sector rotation 12 legs/yr. Multiple testing: 19 trials. Regime: the pre/post-publication split is pre-registered; ^GSPC is price-only and dividends are not seasonal enough to matter (flagged); 1929-32, 2008 and 2020 flagged.
- harness: sell_in_may_v2
- result X-be07895f: not_supported — Nov-Apr minus May-Oct +40 bps/month over 98 years (p=0.051), post-2002 +43 — failed: difference > 50 bps/month; p < 0.05
- result X-5c815255: not_supported — Nov-Apr minus May-Oct +40 bps/month over 98 years (p=0.051), 2002-11..2026-09 +26 (144 winter / 143 summer months) — failed: difference > 50 bps/month; p < 0.05
- note: from the underlying-library library: Sell in May / Halloween indicator; harness suggestion: events.py: half_year_effect(days, closes, start_month=11, end_month=4, cash=dtb3) -> monthly means, block-bootstrap p, switching Sharpe; month_of_year_grid(days, closes) with Bonferroni over 12. | verifier-corrected restatement of T-352, whose verdict tested the earlier wording and stands

### T-443 · turn-of-month-replication

**Claim.** The SPY turn-of-month premium (T-59, window -4..+3) replicates with a positive, block-bootstrap-significant (p < 0.05) difference with both halves positive in at least three of the five assets QQQ, IWM, TLT, GLD and BTC-USD over their full histories.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://rpc.cfainstitute.org/research/financial-analysts-journal/2008/equity-returns-at-the-turn-of-the-month, https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
- statistic: Per asset: mean daily return difference (bps), TOM days minus other days. Joint statistic: count of assets meeting the per-asset criterion.
- null: No TOM effect in any asset. The null distribution of the count comes from a joint block bootstrap that resamples the same calendar blocks (block 21) across all five assets after demeaning each asset's TOM/non-TOM difference. This preserves cross-asset correlation; QQQ and IWM share SPY's days, so an independence binomial would understate the null probability.
- procedure: Run turn_of_month unchanged on each asset (window fixed, no search). Report halves per asset. Crypto on 7-day calendars. The 5 non-primary variants are reported but cannot change the primary verdict.
- data: daily-history-QQQ, IWM, TLT, GLD, BTC-USD (all stored); ETH-USD and SLV stored. · min n: 2500
- pass: Count >= 3 with joint-bootstrap p < 0.05 for the count.
- controls: Look-ahead: none (calendar). Survivorship: n/a. Costs: ETFs 12 round trips/yr at 1-2 bps; BTC at venue fees, charged. Multiple testing: the joint count is the single pre-registered test; variants are flagged exploratory. Regime: halves per asset; correlation with SPY's T-59 result is acknowledged (QQQ/IWM are not independent replications).
- harness: tom_replication_v2
- result X-5733d8cb: not_supported — turn-of-month replicates on 2/5 assets (need 3): QQQ +5.9 bps net, p=0.061; IWM +7.8 bps net, p=0.016; TLT +0.1 bps net, p=0.424; GLD -0.5 bps net, p=0.518; BTC-USD +13.7 bps net, p=0.038; joint p for 2 passes 0.029 — failed: at least 3 of 5 assets pass
- result X-8c333d01: not_supported — turn-of-month replicates on 2/5 assets (need 3): QQQ +5.9 bps net, p=0.061; IWM +7.8 bps net, p=0.016; TLT +0.1 bps net, p=0.424; GLD -0.5 bps net, p=0.518; BTC-USD +13.5 bps net, p=0.041; joint p for 2 passes 0.025 (shared 21-day calendar blocks on demeaned series, 1000 draws) — failed: at least 3 of 5 assets pass
- note: from the underlying-library library: Turn-of-the-month premium: cross-asset replication; harness suggestion: mandel/experiments/underlying.py: turn_of_month already exists. Add tom_replication(series: dict[str, (days, closes)], n_boot=2000) with a shared block-index bootstrap across assets for the count null; window and payday parameters for variants. | verifier-corrected restatement of T-344, whose verdict tested the earlier wording and stands

### T-444 · january-small-cap-effect

**Claim.** Over 1987-2026, the ^RUT-minus-^GSPC return from the close of the 6th-to-last trading day of December to the close of the 10th trading day of January averages at least 1 percentage point, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://rpc.cfainstitute.org/research/financial-analysts-journal/2006/the-january-effect, https://ideas.repec.org/a/taf/ufajxx/v62y2006i5p78-88.html
- statistic: Mean turn-of-year spread return (pp) across years; sign count.
- null: Zero mean spread. Bootstrap over years. Placement placebo: same-length spread windows at random dates in each year.
- procedure: Per year (n = 39). Halves 1987-2006 / 2007-2026; the second half is post-Haug-Hirschey. 6 secondary variants.
- data: daily-history--RUT (1987-09-10-), daily-history--GSPC, IWM, SPY (stored); IWC (2005-08-, verified on Yahoo), IWN via Yahoo. · min n: 35
- pass: Mean > 1 pp with bootstrap p < 0.05, both halves positive, and placement-placebo p < 0.05.
- controls: Look-ahead: none. Survivorship: indexes/ETFs only; the single-stock variant is flagged biased. Costs: 2 legs x 1 round trip/yr. Multiple testing: 7 variants. Regime: halves; 2000-2002 and 2020-2021 flagged. Both are price indexes, and the dividend gap over 15 days is negligible.
- harness: january_small_cap
- result X-65c1b193: not_supported — Russell minus S&P over the turn of the year +0.87 pp over 39 years (p=0.025, placebo p=0.034), halves +1.91/-0.13; IWM-SPY +0.09 pp — failed: ^RUT-^GSPC mean > 1 pp; both halves positive
- result X-741364e1: not_supported — Russell minus S&P over the turn of the year +0.87 pp over 39 years (p=0.025, placebo p=0.013), halves +1.91/-0.13; IWM-SPY +0.09 pp over 26 years — failed: ^RUT-^GSPC mean > 1 pp; both halves positive; IWM-SPY mean >= 1 pp (2000-)
- note: from the underlying-library library: Turn-of-year small-cap premium (January effect); harness suggestion: events.py: spread_series() plus fixed_window_vs_random() from the Santa harness with a different window_fn. | verifier-corrected restatement of T-351, whose verdict tested the earlier wording and stands

### T-445 · accruals-anomaly

**Claim.** The low-minus-high accruals quintile spread (Ken French, value-weighted) has a positive mean monthly return over 1996-07 to 2026-09 (after Sloan's publication).

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://ideas.repec.org/a/inm/ormnsc/v57y2011i5p797-816.html (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Portfolios_Formed_on_AC_CSV.zip (200)
- statistic: Mean monthly spread with block-bootstrap CI (block 12); FF5 alpha.
- null: Mean spread <= 0.
- procedure: Download Portfolios_Formed_on_AC (verified 200); compute spread; split 1963-1996 vs 1996-2026; no parameters.
- data: Ken French accruals portfolios and FF5. · min n: 300
- pass: Lower 95% bound > 0 over >= 300 post-publication months AND FF5 alpha t >= 2; otherwise parked as 'arbitraged away'.
- controls: Look-ahead: June formation with lagged accounting data. Survivorship: none (CRSP/Compustat with delistings). Costs: annual rebalance ~5-10 bp per side, not in paper returns. Multiple testing: 4 variants. Regime: 2000-2002 and 2008.
- harness: fact_accruals
- result X-3a88110f: not_supported — Accruals Lo20-Hi20 1996-07..2026-08 [data end 2026-08; claim window runs to 2026-09] (n=362 months): mean +0.17%/month, 95% studentized block-12 CI -0.10 to +0.42; FF5 alpha +0.17%/month (NW t +1.21, needs >= 2); before 1996-07 mean +0.38%/month — failed: lower 95% bound of the mean monthly spread > 0; FF5 alpha NW t >= 2
- note: from the underlying-library library: Accruals anomaly (Sloan) post-publication; harness suggestion: data/kenfrench.py sort-portfolio loader; one spread_test() for all characteristic-sorted Ken French files (AC, NI, OP, INV, VAR). | added by the verifier pass

### T-446 · stock-momentum-umd

**Claim.** The FF UMD daily factor has a positive mean return over 1993-01 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w25551 (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip (200)
- statistic: Annualized mean daily UMD with studentized block-bootstrap CI (block 20).
- null: Mean UMD <= 0.
- procedure: FF momentum factor daily (verified 200); fixed window; MTUM diagnostic regression on FF5+UMD.
- data: Ken French F-F_Momentum_Factor_daily; Yahoo MTUM, SPY. · min n: 8000
- pass: Lower 95% bound > 0 over >= 8000 days AND survives family-wide DSR.
- controls: Look-ahead: skip month in formation. Survivorship: none (CRSP). Costs: UMD turnover is high (~100%+/yr per leg); paper factor pre-cost; note. Multiple testing: 4 variants; overlaps factor-momentum entry and the trend family. Regime: 2009 and 2020-2021 crashes.
- harness: fact_momentum_umd
- result X-a05566d2: not_supported — UMD 1993-01-04..2026-08-31 [data end 2026-08-31; claim window runs to 2026-09] (n=8473 days): annualised mean +5.45%, 95% studentized block-20 CI -0.74% to +11.09%; family DSR 0.033 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); regimes 1993-2008 +11.33%, 2009-2026 +0.12%; rolling 10y means -4.79% to +14.63% (86% > 0) — failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Cross-sectional stock momentum (UMD) post-publication; harness suggestion: factor_etf_tilt on UMD/MTUM; flag cross-family duplicate with trend library. | added by the verifier pass

### T-447 · investment-asset-growth-cma

**Claim.** The FF CMA daily factor has a positive mean return over 2008-07 to 2026-09 (after Cooper-Gulen-Schill publication).

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://cxoadvisory.com/fundamental-valuation/asset-growth-cross-section-stock-returns (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip (200)
- statistic: Annualized mean of daily CMA with studentized block-bootstrap CI (block 20).
- null: Mean CMA <= 0.
- procedure: FF5 daily download (verified); fixed window; no parameters; rolling 5-year means.
- data: Ken French F-F_Research_Data_5_Factors_2x3_daily; Portfolios_Formed_on_INV. · min n: 4000
- pass: Lower 95% bound > 0 over >= 4000 days AND survives family-wide DSR.
- controls: Look-ahead: June formation. Survivorship: none. Costs: paper factor pre-cost; note. Multiple testing: 4 variants. Regime: 2008, 2020 junk rally.
- harness: fact_investment_cma
- result X-38e281c1: not_supported — CMA 2008-07-01..2026-08-31 [data end 2026-08-31; claim window runs to 2026-09] (n=4570 days): annualised mean +0.39%, 95% studentized block-20 CI -3.02% to +3.68%; family DSR 0.004 (needs > 0.95; 34 trials, trial-Sharpe var 3.96e-04 from 14 computable variants); regimes 2008-2019 +0.49%, 2020-2026 +0.21%; rolling 5y means -4.18% to +4.98% (60% > 0) — failed: lower 95% bound of the annualised mean > 0; family-wide DSR > 0.95
- note: from the underlying-library library: Investment / asset-growth factor (CMA); harness suggestion: factor_etf_tilt bootstrap mode on FF5 columns. | added by the verifier pass

### T-448 · low-volatility-tilt

**Claim.** USMV has a higher Sharpe ratio than SPY over 2011-11 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://hedgefundalpha.com/strategies/the-volatility-effect-revisited/ (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (fetched)
- statistic: Difference in annualized Sharpe ratios (USMV minus SPY) on daily excess returns over T-bills, with studentized block-bootstrap 95% CI (Ledoit-Wolf 2008 method, block 20 days).
- null: Sharpe(USMV) - Sharpe(SPY) <= 0.
- procedure: Daily adjusted closes; excess over FRED DGS3MO; Ledoit-Wolf bootstrap; rolling 5-year Sharpe differences for regime display; FF variance portfolios 1963-2026 as long-history context (not part of pass).
- data: Yahoo USMV, SPLV, SPHB, SPY; FRED DGS3MO, DGS10; Ken French Portfolios_Formed_on_VAR (verified 200). · min n: 3500
- pass: Lower 95% bound of the Sharpe difference > 0 over >= 3500 daily observations AND survives the family-wide DSR. Power note: over 15 years only Sharpe gaps above ~0.35 are detectable.
- controls: Look-ahead: none in the primary (no parameters); hedge betas from t-1 in variants. Survivorship: none at ETF level. Costs: 0.15-0.25% fees (in NAV), 0.3% borrow in hedged variants. Multiple testing: 4 variants into the family-wide DSR; overlaps with betting-against-beta-etf (same SPLV/SPHB legs) so trials are correlated. Regime: separate 2022 rate shock; condition on DGS10 changes.
- harness: low_vol_v2
- result X-c5c2c5d0: not_supported — USMV Sharpe 0.90 vs SPY 0.93 over 3765 days (lower -0.26) — failed: Sharpe diff lower bound > 0 (not implemented: family-wide DSR)
- result X-1c1042af: not_supported — USMV excess Sharpe 0.75 vs SPY 0.82 over 3749 days 2011-11-01..2026-09-30 (lower -0.30) — failed: Sharpe diff lower bound > 0 (not implemented: family-wide DSR)
- note: from the underlying-library library: Low-volatility / minimum-variance tilt; harness suggestion: factor_etf_tilt with a sharpe_diff mode (Ledoit-Wolf studentized bootstrap); FRED DGS10 as a conditioning variable. | verifier-corrected restatement of T-384, whose verdict tested the earlier wording and stands

### T-449 · net-share-issuance

**Claim.** The repurchaser-minus-high-issuer spread from Ken French net-share-issues portfolios has a positive mean monthly return over 2008-05 to 2026-09 (after Pontiff-Woodgate publication).

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html (fetched), https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Portfolios_Formed_on_NI_CSV.zip (200)
- statistic: Mean monthly spread with block-bootstrap CI; FF5 alpha (note CMA/RMW overlap).
- null: Mean spread <= 0.
- procedure: Download Portfolios_Formed_on_NI (verified 200); compute spread; pre/post publication split; PKW diagnostic.
- data: Ken French NI portfolios and FF5; Yahoo PKW, SPY. · min n: 200
- pass: Lower 95% bound > 0 over >= 200 months AND FF5 alpha t >= 2 (beyond CMA).
- controls: Look-ahead: June formation. Survivorship: none at portfolio level. Costs: annual rebalance. Multiple testing: 4 variants; correlated with buyback-announcement-drift. Regime: 2021 SPAC/issuance boom; 2023 buyback excise tax.
- harness: fact_net_issuance
- result X-b0f715c4: not_supported — Net issuance (<0)-Hi20 2008-05..2026-08 [data end 2026-08; claim window runs to 2026-09] (n=220 months): mean +0.30%/month, 95% studentized block-12 CI -0.18 to +0.86; FF5 alpha +0.23%/month (NW t +1.35, needs >= 2); before 2008-05 mean +0.55%/month; diagnostic PKW-SPY -0.01%/month 2007-01..2026-09 — failed: lower 95% bound of the mean monthly spread > 0; FF5 alpha NW t >= 2
- note: from the underlying-library library: Net share issuance; harness suggestion: spread_test() on Ken French NI file; PKW via factor_etf_tilt. | added by the verifier pass

### T-469 · crypto-short-term-reversal

**Claim.** For Coinbase BTC-USD from 2015-08 to 2026-09, the mean next-day return after a daily return below the trailing-250-day 10th percentile exceeds the unconditional mean next-day return by more than 0.6% (one retail maker round trip).

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1016/j.irfa.2021.101908, https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php
- statistic: conditional minus unconditional mean next-day return; net Sharpe of the long-only rule as secondary
- null: no conditional difference (signal series circularly block-shifted against returns, as in T-61, plus stationary block bootstrap, block 10 days)
- procedure: Use trailing 250-day thresholds only (walk-forward by construction). Run 2,000 block-shift and bootstrap resamples. Use DSR across all variants run, counting T-62/T-58 BTC daily trials in n_trials. Split 2015-2020 and 2021-2026. Repeat on Yahoo BTC-USD (2014-09) as a data-source check.
- data: Coinbase BTC-USD daily candles since 2015-07 and ETH-USD since 2016-05 (public, verified); Yahoo BTC-USD (2014-09) and ETH-USD (2017-11) · min n: 250
- pass: bootstrap 95% lower bound of (conditional - unconditional) > 0.6% AND both halves > 0.6% AND DSR > 0.95; otherwise park as 'no tradable daily reversal in BTC'
- controls: Look-ahead: thresholds use t-250..t-1. Executing at the same 00:00 UTC print that defines r_t is optimistic, so entry at the 01:00 UTC hourly candle is also reported. Costs: 0.6% maker round trip (1.2% taker sensitivity). Survivorship: none for BTC/ETH; the cross-section is blocked rather than run on survivors. Multiple testing: DSR across variants plus prior Mandel BTC daily trials. Regime: halves, with the 2017 and 2021 bubbles flagged.
- harness: btc_reversal_v2
- result X-9d32ac28: not_supported — 422 signals: next-day excess +11.3 bps (95% CI -23.6 to +47.1; needs > 60), halves +13.9/+8.7 — failed: lower bound > 0.6%; both halves > 0.6% (not implemented: DSR > 0.95)
- result X-baf34d0a: not_supported — 422 signals: next-day excess +11.3 bps (95% CI -23.6 to +47.2; needs > 60), halves +13.9/+8.7 — failed: lower bound > 0.6%; both halves > 0.6% (not implemented: DSR > 0.95)
- note: from the underlying-library library: Crypto short-term reversal (time-series BTC/ETH; cross-section of coins); harness suggestion: ts_reversal_quantile: conditional-next-return test with trailing quantile thresholds and block-shift null (generalizes underlying.ratio_reversion's null), reusable for SPY/QQQ/GLD | verifier-corrected restatement of T-320, whose verdict tested the earlier wording and stands

### T-475 · xs-momentum-etf-rotation

**Claim.** Top-3 12-1 rotation across the 9 original sector SPDRs earns a positive after-cost monthly CAPM alpha versus SPY over 2000-01 to 2026-09, with the block-bootstrap 95% interval of alpha excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional, https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1249-1290.html (Moskowitz-Grinblatt; fetched in this pass), https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html (Jegadeesh-Titman)
- statistic: Intercept of monthly regression r_rotation - rf = alpha + beta (r_SPY - rf); DSR of the alpha series (rotation minus beta x SPY); within-month rank-permutation p-value
- null: alpha = 0; ranks carry no information (1,000 within-month rank permutations give the same alpha)
- procedure: Monthly adjclose series; HAC and studentized block bootstrap (block 12 months) for alpha; permutation null; CSCV PBO and DSR over the 96-trial grid; leave-one-sector-out and leave-one-decade-out as robustness
- data: Yahoo adjclose for the 9 SPDRs and SPY (SPDRs not yet in archive), fred-DTB3 · min n: 320
- pass: alpha > 0 with 95% interval excluding 0 AND above the 95th percentile of the permutation null AND DSR > 0.95 AND PBO < 0.5; alpha sign positive in every leave-one-sector-out run
- controls: Look-ahead: ranks from month-end t, trades at t+1; survivorship: constant 9-fund set, but the 2018 GICS reshuffle moved large names from XLK/XLY into XLC and XLRE was carved out of XLF in 2015: treat 2015-10 and 2018-09 as structural breaks and report results before and after; costs: 3-5 bps per side on 30-50% monthly turnover; multiple testing: 96 trials; regime: by decade, excluding 2000-02 and 2008
- harness: sector_rotation_v2
- result X-890ef6fe: not_supported — sector top-3 alpha +17.3 bps/month over 322 months (95% CI -5.9 to +41.0; random-pick 95th pct +19.5), PBO 0.29, leave-one-out min -1.4 — failed: alpha > 0 with CI excluding 0; above permutation 95th pct; leave-one-out positive (not implemented: DSR > 0.95)
- result X-8c4a47ea: not_supported — sector top-3 alpha +17.3 bps/month over 322 months (95% CI -5.9 to +41.0; cost-matched random-pick 95th pct +23.2), proxy PBO (12 variants, diagnostic) 0.29, leave-one-sector-out min -1.4, leave-one-decade-out 2000s +4.5/2010s +33.1/2020s +11.7 — failed: alpha > 0 with CI excluding 0; above permutation 95th pct; leave-one-out positive (not implemented: PBO < 0.5 over the declared 96-trial grid; DSR > 0.95 over the declared 96-trial grid)
- note: from the underlying-library library: Cross-sectional sector ETF momentum (Select Sector SPDR rotation); harness suggestion: underlying.py: xs_momentum(adj_monthly_df, lookback, skip, top_k, long_short, abs_filter) -> weights and returns; harness xs_etf_momentum with rank-permutation null; pbo_cscv from overfit.py. | verifier-corrected restatement of T-306, whose verdict tested the earlier wording and stands

### T-478 · currency-momentum-g10

**Claim.** Over 1999-2026, the 1-month G10 currency momentum portfolio (top third minus bottom third, with interest differentials) earns a positive mean monthly excess return after 5 bps per side, with the block-bootstrap 95% interval excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional/fx, https://ideas.repec.org/a/eee/jfinec/v106y2012i3p660-684.html (Menkhoff et al. 2012; fetched in this pass)
- statistic: Mean monthly long-short excess return; DSR over 16 trials; permutation percentile
- null: Mean = 0
- procedure: Month-end FRED spot rates (point-in-time via available_at); block bootstrap (block 12 months); 1,000 rank permutations; DSR; ETF-implementable version reported 2007-2026 (FXE etc. history) as a cost check
- data: FRED H.10 daily rates and OECD 3-month interbank rates (FRED reachable; series not yet in archive); Yahoo FXE/FXY/FXB/FXF/FXC/FXA · min n: 300
- pass: Mean > 0 with 95% interval excluding 0, DSR > 0.95, above the permutation 95th percentile
- controls: Look-ahead: month-end noon NY rates published next business day; survivorship: none (fixed currency set, EUR replaces legacy DEM from 1999); costs: 5 bps per side spot, 10-20 bps ETF spreads; multiple testing: 16 trials; regime: 2008 and 2022 dollar spikes reported
- harness: fx_momentum_g10
- result X-44d40cbe: not_supported — currency momentum 1999-01..2026-09 (333 months, 9-currency universe; 41 early months with 6-8 currencies while CHF/JPY rates are missing; DKK not archived): mean net -19.0 bps/month, 95% CI [-38.5, +1.0] (need > 0 and CI excluding 0); DSR 0.000 at 16 trials (need > 0.95); permutation 95th pct +1.2 bps, observed at pctile 25.7 (need above the 95th). Gross -5.4 bps, costs 13.6 bps/month, net Sharpe -0.34; full 9-currency sub-sample from 2002-06 (292 months) -12.1 bps [-32.9, +9.2]; same-fixing (no skip) -21.35 bps; stale rates spliced by forward fill (flagged): EUR 2026-02..2026-08 (7 mo), GBP 2026-02..2026-08 (7 mo), JPY 2026-08..2026-08 (1 mo); one-month gaps filled: USD 2020-04..2020-04 (1 mo); ETF cost check not run (FXE/FXY/FXB/FXF/FXC/FXA not archived; reported item, not a pass criterion) — failed: mean net monthly excess return > 0 with block-bootstrap 95% CI excluding 0; DSR > 0.95 with 16 trials; mean above the permutation 95th percentile
- note: from the underlying-library library: Currency momentum on G10 spot rates (FRED H.10) traded through currency ETFs; harness suggestion: mandel/data/fred.py batch fetch of the H.10 and IR3TIB series; xs_momentum reused on the currency panel; harness currency_momentum. | added by the verifier pass

### T-480 · dual-momentum-gem

**Claim.** Over 2003-10 to 2026-09, GEM (12-month, SPY/EFA, AGG fallback) earns a higher after-cost Sharpe ratio than the monthly-rebalanced 60/40 SPY/AGG portfolio, with the paired block-bootstrap 95% interval of the Sharpe difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/dual, https://www.advisorperspectives.com/articles/2019/05/06/global-equity-momentum-a-craftsmans-perspective (ReSolve 2019; located via search in this pass, page itself 403 earlier), https://alphaarchitect.com/2015/02/asset-allocation-horserace-robust-asset-allocation-raa-vs-dual-momentum/ (search result)
- statistic: Sharpe(GEM) - Sharpe(60/40), paired monthly; PBO (CSCV) across the 60-trial matrix; diagnostics: max drawdown ratio, post-2014 sub-sample
- null: Sharpe difference = 0
- procedure: Monthly adjclose series; paired studentized block bootstrap (block 12 months, 5,000 draws); CSCV PBO over the trial matrix with 16 partitions; DSR with n_trials = 60
- data: Yahoo adjclose for SPY, EFA, AGG, IEF, BIL, GLD (only SPY/GLD in archive now); fred-DTB3 · min n: 270
- pass: Sharpe difference > 0 with 95% interval excluding 0 AND PBO < 0.5 AND DSR > 0.95
- controls: Look-ahead: month-end returns used next day; survivorship: instruments named ex ante; costs: 3 bps per side per switch; dividends: adjclose mandatory (AGG's return is mostly coupons); multiple testing: 60 trials; regime: with and without 2008, and 2014-2026 (post-publication) separately
- harness: gem_v2
- result X-d9d8fb12: not_supported — GEM Sharpe 0.80 vs 60/40 0.87 (diff -0.07, lower -0.48), MDD -21% vs -32%, PBO 0.39 over 265 months — failed: Sharpe diff > 0 with 95% CI excluding 0 (not implemented: DSR > 0.95)
- result X-3b44aadc: not_supported — GEM excess Sharpe 0.59 vs 60/40 0.64 (diff -0.05, lower -0.44), MDD -24% vs -33%, proxy PBO (10 lookbacks, diagnostic) 0.61 over 264 months (fills at the next day's close, 6 bps per switch) — failed: Sharpe diff > 0 with 95% CI excluding 0 (not implemented: PBO < 0.5 over the declared 60-trial matrix (16 partitions); DSR > 0.95 (n_trials = 60))
- note: from the underlying-library library: Dual momentum (Antonacci GEM): SPY vs foreign equity with T-bill filter and bond fallback; harness suggestion: underlying.py: dual_momentum(adj_monthly: dict, lookback, fallback, filter_on) -> monthly weights; harness gem_vs_6040 with pbo_cscv from overfit.py. | verifier-corrected restatement of T-305, whose verdict tested the earlier wording and stands

### T-485 · crypto-trend-sma-50-200

**Claim.** On BTC-USD daily data 2015-04 to 2026-10, the 50/200 golden-cross long/flat rule's after-cost Sharpe ratio exceeds buy-and-hold's, with the studentized block-bootstrap 95% interval of the Sharpe difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/crypto, https://arxiv.org/abs/2009.12155 (Rozario et al. 2020; abstract fetched in this pass), https://www.nber.org/papers/w24877 (Liu-Tsyvinski; fetched in this pass)
- statistic: Sharpe(rule) - Sharpe(buy-and-hold) on daily returns (365-day annualisation), paired; DSR of the rule over 72 trials; diagnostics: max drawdown ratio, ETH replication, post-2020-09 (post-Rozario) sub-sample
- null: Sharpe difference = 0
- procedure: Daily series; paired studentized circular block bootstrap (block 30 days, 5,000 draws) of the Sharpe difference (Ledoit-Wolf 2008 style); DSR with n_trials = 72; spell-preserving random in/out null reported for drawdown; ETH run as replication, not pooled
- data: daily-history-BTC-USD, daily-history-ETH-USD (in archive); Coinbase daily candles as a close cross-check · min n: 4000
- pass: Sharpe difference > 0 with 95% interval excluding 0 AND DSR > 0.95; ETH Sharpe difference point estimate > 0 (replication gate); post-2020-09 difference reported
- controls: Look-ahead: SMA through close t, return from close t+1; survivorship: BTC/ETH are survivors of thousands of coins, claim is per-asset only; costs: 25 bps per side plus 10 bps slippage; multiple testing: 72 trials including T-58; regime: by halving cycle (2015-16, 2016-20, 2020-24, 2024-26)
- harness: golden_cross_v2
- result X-b265f43a: not_supported — BTC: Sharpe diff -0.03 (95% CI -0.39 to +0.35), DSR 1.00; ETH: Sharpe diff -0.07 (95% CI -0.60 to +0.47), DSR 0.94 — failed: BTC Sharpe diff > 0 with CI excluding 0; ETH diff > 0
- result X-888b07c2: not_supported — SMA through close t, return from close t+1; BTC from 2015-04-06: Sharpe diff -0.04 (95% CI -0.39 to +0.34), DSR 1.00 (n_trials 72, variance of 4 run variants); ETH from 2018-05-29: Sharpe diff -0.00 (95% CI -0.55 to +0.52), DSR 0.89 (n_trials 72, variance of 4 run variants) — failed: BTC Sharpe diff > 0 with CI excluding 0; ETH diff > 0
- note: from the underlying-library library: Crypto trend: 50/200-day SMA golden cross on BTC and ETH; harness suggestion: Reuse underlying.ma_rule_returns and rule_search (T-58 harness) with an sma_cross(fast, slow) addition and a paired Sharpe-difference bootstrap; add a coinbase_candles() fetcher for the cross-check. | verifier-corrected restatement of T-302, whose verdict tested the earlier wording and stands

### T-486 · btc-eth-short-horizon-tsmom

**Claim.** On BTC and ETH (equal weight), the 1-week TSMOM long/flat rule earns a higher mean weekly after-cost return than the historical-mean strategy, with the studentized block-bootstrap 95% interval of the difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/crypto, https://www.nber.org/papers/w24877 (Liu-Tsyvinski; fetched in this pass), https://quantpedia.com/trend-following-and-mean-reversion-in-bitcoin/
- statistic: Mean weekly difference d = r(rule) - r(historical-mean strategy); DSR of d over 16 trials; 2019-2026 sub-period mean
- null: E[d] = 0
- procedure: Weekly series from daily closes; studentized block bootstrap (block 8 weeks, 5,000 draws); DSR; sub-period estimate
- data: daily-history-BTC-USD, daily-history-ETH-USD (archive); Coinbase candles as a cross-check · min n: 600
- pass: Mean d > 0 with 95% interval excluding 0 after costs AND DSR > 0.95 AND 2019-2026 mean d > 0
- controls: Look-ahead: one-bar delay; survivorship: per-asset claim on two survivors; costs: 30 bps per side plus 10 bps slippage on about 25 switches a year; multiple testing: 16 trials; regime: per halving cycle
- harness: crypto_weekly_v2
- result X-9db7487c: not_supported — weekly TSMOM minus historical-mean strategy -29.5 bps/week over 604 weeks (95% CI -80.4 to +20.7), DSR 0.03, 2019- -40.5 — failed: mean d > 0 with CI excluding 0; DSR > 0.95; 2019- mean d > 0
- result X-fd121342: not_supported — weekly TSMOM minus historical-mean strategy -46.3 bps/week over 604 weeks (164 BTC-only; 40 bps per side; 95% CI -96.0 to +2.7), DSR 0.00 (n_trials 16), 2019- -44.9 — failed: mean d > 0 with CI excluding 0; DSR > 0.95; 2019- mean d > 0
- note: from the underlying-library library: Short-horizon time-series momentum in BTC and ETH (1-4 week); harness suggestion: Weekly resample plus tsmom_returns from underlying.py; harness btc_weekly_tsmom sharing the crypto trend infrastructure. | verifier-corrected restatement of T-315, whose verdict tested the earlier wording and stands

### T-487 · trend-metals-gold-silver

**Claim.** Over 2007-05 to 2026-09, the inverse-vol gold+silver 12-1 long/flat TSMOM strategy earns a higher mean monthly after-cost return than the historical-mean strategy on the same metals, with the studentized block-bootstrap 95% interval of the difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series/metals, https://arxiv.org/abs/1404.3274 (Lemperiere et al.; fetched in this pass), https://econpapers.repec.org/article/eeejbfina/v_3a31_3ay_3a2007_3ai_3a6_3ap_3a1863-1886.htm (Miffre-Rallis; record fetched in this pass, no abstract)
- statistic: Mean monthly difference d = r(TSMOM) - r(historical-mean); DSR of d over 24 trials; diagnostics: max drawdown vs buy-and-hold, chained-futures sign agreement
- null: E[d] = 0 (no predictability beyond drift)
- procedure: Monthly adjclose series; studentized block bootstrap (block 12 months, 5,000 draws); DSR; GC=F/SI=F run with roll days masked as a sign check
- data: daily-history-GLD, daily-history-SLV (archive; refetch with adjclose for consistency), Yahoo GC=F, SI=F; fred-DTB3 · min n: 220
- pass: Mean d > 0 with 95% interval excluding 0 AND DSR > 0.95 AND same sign on the chained-futures check
- controls: Look-ahead: month-end signal, next-day trade; survivorship: GLD/SLV chosen ex ante, both survive; costs: 3-5 bps per side, expense ratios inside adjclose; multiple testing: 24 trials incl. T-58; regime: per gold episode, with the 2013-04 gold crash and 2011-05 silver crash reported
- harness: metals_v2
- result X-9538d6f6: not_supported — metals TSMOM minus historical-mean strategy +1.7 bps/month over 234 months (95% CI -42.0 to +45.0), DSR 0.43, futures -15.7 — failed: mean d > 0 with CI excluding 0; DSR > 0.95; futures same sign
- result X-f829a5fe: not_supported — metals TSMOM minus historical-mean strategy -4.9 bps/month over 233 months from 2007-06 (95% CI -42.6 to +31.0), DSR 0.19 (n_trials 24), futures -7.0 over the same 233 months — failed: mean d > 0 with CI excluding 0; DSR > 0.95
- note: from the underlying-library library: Trend following on gold and silver ETFs; harness suggestion: Reuse the TSMOM harness with an inverse_vol_combiner and a roll-day mask for =F symbols. | verifier-corrected restatement of T-312, whose verdict tested the earlier wording and stands

### T-502 · pin-risk-expiration-pinning

**Claim.** Using unadjusted SPY closes, the mean distance of the close to the nearest whole dollar on monthly (third-Friday) expiration days is at least 10% smaller than on non-expiration days (uniform expectation 0.25).

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Pin_risk, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean |close - round(close)| on monthly expiration days vs control days; studentized block-bootstrap difference.
- null: Ratio of means >= 0.90.
- procedure: SPY unadjusted daily closes since 2005 (SPY options with $1 strikes); treatment = third-Friday monthly expirations; control = days with no SPY expiration (pre-2016 non-Fridays; after daily expirations began in late 2022 use non-monthly days and report separately); walk-forward by year.
- data: SPY daily closes (available; must be UNADJUSTED - dividend-adjusted closes destroy the integer grid), deterministic expiration calendar. · min n: 200
- pass: Ratio < 0.90 with bootstrap p < 0.05 and the effect present in a majority of years.
- controls: Placebo Thursdays; $0.50 grid as a second test; QQQ replication; single names with $5 strikes.
- harness: opex_pinning
- result X-89d6979d: not_supported — SPY close's distance to the nearest $1 on 255 monthly opex days 0.255 vs 0.249 on other days (ratio 1.03, need <= 0.90; p=0.755); lower in 9/22 years
- result X-45d0a06f: not_supported — SPY close's distance to the nearest $1 on 214 monthly expiration days 0.250 vs 0.246 on 2886 days with no SPY expiration, 2005 to Nov 2022 (ratio 1.016, need < 0.90; P(boot ratio >= 0.90) = 0.998; difference p 0.646); lower in 7/18 years (4 at least 10% lower); regimes (reported, the last outside the verdict): 2005-2015 (control Mon-Thu) 1.015, 2016-Nov 2022 (control Tue/Thu) 1.036, Nov 2022 on (daily expiries; control non-monthly days) 1.126; verdict: failed: ratio of means < 0.90; bootstrap p < 0.05 against ratio >= 0.90; opex mean lower in a majority of years
- note: from the options-library library: Expiration pin risk management and pinning trade; harness suggestion: mandel/experiments/pinning.py on SPY closes; later join captured OI for OI-weighted pins. | verifier-corrected restatement of T-192, whose verdict tested the earlier wording and stands

### T-505 · put-call-parity-synthetic-forward

**Claim.** On the CBOE delayed SPX chain (European, cash-settled), fewer than 2% of (K, T) pairs within ATM +/- 5 strikes have an implied forward F_impl = K + (C_mid - P_mid) e^{rT} that differs from the median F_impl of the same root and expiry by more than half the combined call + put bid-ask spread (times e^{rT}).

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://en.wikipedia.org/wiki/Synthetic_position
- statistic: Share of (K, T) pairs with |F_impl(K,T) - median_K F_impl(T)| > 0.5 e^{rT} (spread_call + spread_put).
- null: The share is >= 2% (parity is not strike-consistent within spreads on the SPX book).
- procedure: Day one: pull the SPX chain, split by root (SPX vs SPXW), take ATM +/- 5 strikes per expiry, drop zero-bid legs, compute F_impl from mids using the FRED 3-month bill (the rate cancels to first order in the cross-strike comparison), count exceedances; repeat daily and block-bootstrap the daily share as capture accumulates.
- data: CBOE delayed SPX chain (available today); FRED DGS3MO. No dividend input is needed because the comparison is across strikes within one expiry. · min n: 200
- pass: Day-one share < 2% with a one-sided 95% bootstrap bound < 2%; still < 2% on >= 16 of the first 20 captured days.
- controls: Placebo: shift put quotes by one strike and confirm the statistic flags them; repeat on XSP (should match SPX); repeat on SPY with the American band instead of equality; exclude quotes whose last update is older than the chain timestamp.
- harness: parity_v2
- result X-b2f95ecc: not_supported — day one 2026-10-14: 2.2% of 590 SPX/SPXW (K,T) pairs have an implied forward outside the half-spread band around the expiry median (one-sided 95% bound 3.2%; needs < 2%)
- result X-ddcd0c9a: not_supported — day one 2026-10-14: 2.2% of 590 SPX/SPXW (K,T) pairs have an implied forward outside the half-spread band around the expiry median (one-sided 95% bound 3.2%; needs < 2%); later days: 2026-10-15 0.5% (the claim makes day one decisive)
- result X-486a58ea: not_supported — day one 2026-10-14: 2.2% of 590 SPX/SPXW (K,T) pairs have an implied forward outside the half-spread band around the expiry median (one-sided 95% bound 3.2%; needs < 2%); later days: 2026-10-15 0.5% (the claim makes day one decisive)
- note: from the options-library library: Put-call parity scan / synthetic forward; harness suggestion: mandel/options/parity.py: implied_forward(chain, r) -> per-(K,T) table with strike-dispersion column; inverse_parity(deribit_book) using F_impl = K/(1 - (C_btc - P_btc)); 2-leg template [call+, put-] in the payoff engine must draw a straight line. | verifier-corrected restatement of T-181, whose verdict tested the earlier wording and stands

### T-506 · short-box-spread-borrow

**Claim.** On the capture day, the median executable SPX short-box borrowing rate (sell bids, buy offers on all four legs) across expiries with 180-730 DTE is below the FRED 3-month bill + 50 bp, i.e. at least 100 bp below a benchmark retail margin rate of bill + 150 bp.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Box_spread, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: Median over expiries of r_box_borrow_exec - r_bill.
- null: Median >= 50 bp.
- procedure: Day one: for each SPX expiry with 180-730 DTE build wide boxes from legs with bids > 0; compute executable and mid borrowing rates; compare to DGS3MO (margin rates float off short rates, so the 3-month bill is the right benchmark); repeat daily.
- data: CBOE delayed SPX chain, FRED DGS3MO. · min n: 10
- pass: Median < 50 bp on day one and on >= 80% of captured days.
- controls: Strike-invariance; SPX vs XSP agreement; mid vs executable gap reported.
- harness: box_borrow_v2
- result X-da417e54: not_supported — day one 2026-10-14: executable short-box borrowing rate is bill +171 bp over 29815 boxes (needs < +50 bp)
- result X-546d5c3b: not_supported — day one 2026-10-14: executable short-box borrowing rate is bill +171 bp over 29815 boxes (needs < +50 bp); later days: 2026-10-15 +202 bp
- result X-44e5c0f0: not_supported — day one 2026-10-14: executable short-box borrowing rate is bill +145 bp, median over 12 expiries (29815 boxes; pooled box median +152 bp) (needs < +50 bp); later days: 2026-10-15 +179 bp
- note: from the options-library library: Short box spread (SPX box borrowing); harness suggestion: box.py with side='short' using executable prices; borrow-curve output. | verifier-corrected restatement of T-187, whose verdict tested the earlier wording and stands

### T-533 · vega_neutral_gamma_long

**Claim.** Conditional on VIX9D closing below the trailing 10-day realised SPY volatility, the SPY variance realised over the next 9 calendar days exceeds VIX9D^2 on average.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://www.cboe.com/us/indices/dashboard/vix9d/
- statistic: Mean of RV(next 9 calendar days, ~6-7 trading days, annualised) - (VIX9D/100)^2 over signal days.
- null: Conditional mean <= 0 (implied still exceeds realised even when it sits below trailing realised).
- procedure: Daily VIX9D from 2011-01-04 and SPY closes; non-overlapping 9-calendar-day windows (VIX9D is a 9-calendar-day measure, not 9 trading days); studentized block bootstrap; walk-forward. The trailing-RV windows 5/10/20 are declared and deflated. Secondary: the swap's gamma-scalp P&L simulated with BS (model-priced: VIX9D as near IV, VIX3M as far IV).
- data: CBOE VIX9D and VIX3M (archive), SPY closes. · min n: 100
- pass: Conditional mean > 0 with the 95% CI excluding zero; the model-priced swap Sharpe after a 0.5 vol-point round-trip cost is reported separately and is not part of the pass.
- controls: Unconditional version (expected negative: the VRP); random-entry placebo with the same count.
- harness: vix9d_v2
- result X-f152f25f: not_supported — 180 signals: next-9-calendar-day RV^2 - VIX9D^2 mean -0.0121 (realised larger in 19%), p=0.977
- result X-8e2bdb37: not_supported — 180 signals: next-9-calendar-day RV^2 - VIX9D^2 mean -0.0121 (realised larger in 19%), p=0.977
- note: from the options-library library: Vega-neutral gamma-positive straddle swap (long near / short far straddle); harness suggestion: harness_vix9d (T-232) already runs this but uses 9 trading-day windows; switch to 9 calendar days. Add a harness_gamma_swap daily-rehedge simulator (bs.delta) on SPY closes for the model-priced secondary. | verifier-corrected restatement of T-232, whose verdict tested the earlier wording and stands

### T-536 · vvix_vol_of_vol

**Claim.** Over non-overlapping months since 2006, VVIX exceeds the subsequently realised 21-trading-day volatility of daily log changes in spot VIX by more than 10 vol points on average.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.cboe.com/us/indices/dashboard/vvix/, https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv
- statistic: Mean of VVIX_t - 100*sqrt(252)*sd(dlnVIX_{t..t+21}); by VVIX quartile as a secondary; model-priced short-strangle P&L (Black-76 on F_adj with VVIX as IV) with crisis months tabulated.
- null: Mean gap <= 10.
- procedure: Daily VVIX from 2006-03-06 and VIX; non-overlapping 21d windows; studentized block bootstrap; quartile monotonicity test (harness_horizon_monotone pattern); deflated Sharpe on the model-priced secondary.
- data: CBOE VVIX, VIX and VIX3M (archive). · min n: 200
- pass: Lower 99% bound of the mean gap > 10; quartile means increasing (reported); model-priced Sharpe reported separately.
- controls: Shuffled-VVIX placebo; realised vol of the forward proxy F instead of spot VIX (lower variance, closer to what VVIX prices).
- harness: vvix_v2
- result X-8010d5c8: not_supported — 243 non-overlapping months: VVIX minus realised spot-VIX vol -22.4 pts (lower 99% -29.8, needs > 10); VVIX prices VIX futures, which move less than spot
- result X-1b1179af: not_supported — 243 non-overlapping months: VVIX minus realised spot-VIX vol -22.4 pts (lower 99% -29.8, needs > 10); VVIX prices VIX futures, which move less than spot
- note: from the options-library library: Vol-of-vol trade: short VIX strangle vs VVIX; harness suggestion: harness_vvix (T-243) implements the data part; add the strangle pricer so a pass is no longer reported as inconclusive. | verifier-corrected restatement of T-243, whose verdict tested the earlier wording and stands

## Inconclusive (13)

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
- result X-d516666f: inconclusive — skill > 0 at every horizon scored on n >= 300, but the claim needs every horizon with n >= 300: 90d n 260

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
- result X-cd4319f5: inconclusive — 2/30 collection days, 79 usable ticker-days
- result X-a01508eb: inconclusive — 1/30 capture days with a point-in-time joined row, 0 usable ticker-days (87 rows captured after close(day) dropped)
- note: runs daily; inconclusive until 30 capture days

### T-54 · covered-call-beats-buy-and-hold

**Claim.** Writing monthly 30-delta covered calls on SPY produces a higher Sharpe ratio than holding SPY.

- kind: options-strategy · origin: cboe:BXMD, options-sweep
- statistic: Sharpe difference over non-overlapping monthly cycles
- null: Sharpe(covered call) <= Sharpe(buy and hold); circular block bootstrap of paired cycles
- procedure: every 21 trading days: hold SPY, sell a 30-delta call priced by BSM at VIX; settle at expiry
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 100
- pass: Sharpe higher and p < 0.05
- controls: MODEL-PRICED: Black-Scholes with VIX as a flat IV and the 3-month bill; a flat VIX overstates OTM call premium and understates OTM put premium, so call-selling results are an upper bound. Tests the strategy's logic, not market option prices; the daily chain capture (from 2026-10-14) will replace it.
- harness: covered_call_overlay
- result X-c3d19508: supported — model-priced (VIX as flat IV, upper bound for call selling): Sharpe 1.17 vs buy-and-hold 0.62, CAGR 16.4% vs 8.9%, MDD -42% vs -56%, Sharpe-diff p=0.000, 403 cycles
- result X-2f57d496: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: Sharpe 1.17 vs B&H 0.62, CAGR 16.4% vs 8.9%; at IV x0.81: Sharpe 0.87, CAGR 11.1%, MDD -46% vs -56% (403 cycles)
- result X-de4b55fd: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: Sharpe 1.11 vs B&H 0.57, CAGR 18.5% vs 10.8%; at IV x0.81: Sharpe 0.81, CAGR 13.2%, MDD -44% vs -55% (403 cycles)
- blocked on: a history of the ATM-IV/VIX ratio and 30-delta premia from the daily options-surface capture (~250 days) to replace flat-VIX pricing
- note: Harness returns inconclusive by design while model-priced: against the live SPY chain on 2026-10-14 (30 DTE) a flat VIX overstated the 30-delta call premium by 79%, the ATM call by 23%, the ATM put by 17% and the 30-delta put by 8% (VIX 15.27 vs SPY ATM IV 12.3). The statistic is reported at VIX and at IV x0.81 as a sensitivity. Becomes a verdict when the daily surface capture gives a history of the ATM-IV/VIX ratio and of the 30-delta premia (blocked_on: ~250 capture days).

### T-55 · put-writing-beats-buy-and-hold

**Claim.** Writing monthly ATM cash-secured puts on SPY produces a higher Sharpe ratio than holding SPY.

- kind: options-strategy · origin: cboe:PUT, options-sweep
- statistic: Sharpe difference over monthly cycles
- null: Sharpe(put write) <= Sharpe(buy and hold); block bootstrap
- procedure: every 21 trading days: sell an ATM put priced at VIX, hold the strike in bills
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 100
- pass: Sharpe higher and p < 0.05
- controls: MODEL-PRICED: Black-Scholes with VIX as a flat IV and the 3-month bill; a flat VIX overstates OTM call premium and understates OTM put premium, so call-selling results are an upper bound. Tests the strategy's logic, not market option prices; the daily chain capture (from 2026-10-14) will replace it.
- harness: csp_overlay
- result X-babe2142: supported — model-priced: Sharpe 1.27 vs buy-and-hold 0.62, CAGR 12.9% vs 8.9%, MDD -32% vs -56%, Sharpe-diff p=0.005
- result X-0b25a5ae: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: Sharpe 1.27 vs B&H 0.62, CAGR 12.9% vs 8.9%; at IV x0.81: Sharpe 0.76, CAGR 7.3%, MDD -38% vs -56%
- result X-d5823f74: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: Sharpe 1.02 vs B&H 0.57, CAGR 12.9% vs 10.8%; at IV x0.81: Sharpe 0.51, CAGR 7.3%, MDD -38% vs -55%
- blocked on: a history of the ATM-IV/VIX ratio and 30-delta premia from the daily options-surface capture (~250 days) to replace flat-VIX pricing
- note: Harness returns inconclusive by design while model-priced: against the live SPY chain on 2026-10-14 (30 DTE) a flat VIX overstated the 30-delta call premium by 79%, the ATM call by 23%, the ATM put by 17% and the 30-delta put by 8% (VIX 15.27 vs SPY ATM IV 12.3). The statistic is reported at VIX and at IV x0.81 as a sensitivity. Becomes a verdict when the daily surface capture gives a history of the ATM-IV/VIX ratio and of the 30-delta premia (blocked_on: ~250 capture days).

### T-56 · collar-cuts-drawdown-cheaply

**Claim.** A monthly 30-delta collar on SPY cuts the maximum drawdown by at least a third while keeping the Sharpe ratio within 0.10 of buy-and-hold.

- kind: options-strategy · origin: cboe:CLL, options-sweep
- statistic: max drawdown ratio and Sharpe difference
- null: descriptive thresholds (no sampling null)
- procedure: every 21 trading days: hold SPY, sell 30-delta call, buy 30-delta put, both priced at VIX
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 100
- pass: MDD(collar) < 2/3 MDD(SPY) and Sharpe >= Sharpe(SPY) - 0.10
- controls: MODEL-PRICED: Black-Scholes with VIX as a flat IV and the 3-month bill; a flat VIX overstates OTM call premium and understates OTM put premium, so call-selling results are an upper bound. Tests the strategy's logic, not market option prices; the daily chain capture (from 2026-10-14) will replace it. A flat VIX under-prices the put, so the collar's cost is understated.
- harness: collar_overlay
- result X-70018c19: supported — model-priced: MDD -26% vs -56% (needs < -38%), Sharpe 1.15 vs 0.62, CAGR 10.3% vs 8.9%
- result X-24cba6b2: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: MDD -26% vs -56%, Sharpe 1.15 vs 0.62; at IV x0.81: MDD -21%, Sharpe 1.19, CAGR 9.3% vs 8.9%
- result X-b0a5f811: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: MDD -24% vs -55%, Sharpe 1.06 vs 0.57; at IV x0.81: MDD -19%, Sharpe 1.09, CAGR 11.3% vs 10.8%
- blocked on: a history of the ATM-IV/VIX ratio and 30-delta premia from the daily options-surface capture (~250 days) to replace flat-VIX pricing
- note: Harness returns inconclusive by design while model-priced: against the live SPY chain on 2026-10-14 (30 DTE) a flat VIX overstated the 30-delta call premium by 79%, the ATM call by 23%, the ATM put by 17% and the 30-delta put by 8% (VIX 15.27 vs SPY ATM IV 12.3). The statistic is reported at VIX and at IV x0.81 as a sensitivity. Becomes a verdict when the daily surface capture gives a history of the ATM-IV/VIX ratio and of the 30-delta premia (blocked_on: ~250 capture days).

### T-57 · short-straddle-earns-the-vrp

**Claim.** Selling the monthly ATM SPY straddle priced at VIX earns a positive mean P&L (the variance risk premium in option form).

- kind: options-strategy · origin: literature:vrp, options-sweep
- statistic: mean monthly P&L as a share of notional
- null: mean P&L = 0; studentized block bootstrap
- procedure: every 21 trading days: sell ATM call and put priced at VIX, settle at |S_T - K|
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 100
- pass: mean > 0, p < 0.05, both halves > 0
- controls: MODEL-PRICED: Black-Scholes with VIX as a flat IV and the 3-month bill; a flat VIX overstates OTM call premium and understates OTM put premium, so call-selling results are an upper bound. Tests the strategy's logic, not market option prices; the daily chain capture (from 2026-10-14) will replace it. ATM pricing at VIX is close to fair (VIX is roughly the ATM-ish 30-day IV), so this one is the least biased of the overlays.
- harness: short_straddle_model
- result X-13ef8afe: supported — model-priced: mean +1.10% of notional per month, Sharpe 1.33, MDD -23%, block-bootstrap p=0.0005, halves +1.14%/+1.06%
- result X-c9662a62: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: mean +1.10%/month (p=0.0005); at IV x0.81: mean +0.24%/month (p=0.0745), Sharpe 0.29, MDD -37%
- result X-1acb0719: inconclusive — MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%. At VIX: mean +1.10%/month (p=0.0005); at IV x0.81: mean +0.24%/month (p=0.0745), Sharpe 0.29, MDD -37%
- blocked on: a history of the ATM-IV/VIX ratio and 30-delta premia from the daily options-surface capture (~250 days) to replace flat-VIX pricing
- note: Harness returns inconclusive by design while model-priced: against the live SPY chain on 2026-10-14 (30 DTE) a flat VIX overstated the 30-delta call premium by 79%, the ATM call by 23%, the ATM put by 17% and the 30-delta put by 8% (VIX 15.27 vs SPY ATM IV 12.3). The statistic is reported at VIX and at IV x0.81 as a sensitivity. Becomes a verdict when the daily surface capture gives a history of the ATM-IV/VIX ratio and of the 30-delta premia (blocked_on: ~250 capture days).

### T-66 · implied-move-exceeds-realised

**Claim.** The ATM straddle's implied move at about 30 days exceeds the realised move to expiry on average across SPY, QQQ, IWM, TLT, GLD, SLV, USO and IBIT.

- kind: volatility · origin: options-sweep, cboe:chains
- statistic: mean(implied move % - realised |move| %) over resolved captures; share implied > realised
- null: equal; block bootstrap over captures
- procedure: daily surface capture; pair each capture's ~30 DTE straddle with the realised move once the expiry passes
- data: options-surface-* (daily), daily-history-* · min n: 30
- pass: mean > 0, p < 0.05
- controls: market-priced (actual mids), point in time by construction; needs the expiry to pass, so the first verdict is ~2 months after 2026-10-14
- harness: implied_move
- result X-fe2505e4: inconclusive — 0/30 captures with an expired ~30d expiry (chain capture started 2026-10-14)
- result X-c288209a: inconclusive — 0/30 captures with an expired ~30d expiry (chain capture started 2026-10-14)
- result X-0a8698e7: inconclusive — 0/30 independent ~30d expiry cycles (0 resolved capture days, 0 symbol-captures; overlapping captures share one realised path; chain capture started 2026-10-14)
- note: the market-priced replacement for the model-priced short-straddle overlay (T-57)

### T-231 · calendar_vol_spread

**Claim.** The forward 1-to-3 month variance implied by VIX3M and VIX exceeds the variance subsequently realised over trading days 22-63 by more, on average, than spot VIX implied variance exceeds realised variance over days 1-21: the term premium is positive and larger than the spot VRP, so being short the far leg (reverse calendar, vega-weighted) when VIX3M/VIX > 1.10 has positive expectancy.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/term_structure/, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Mean of F^2 - RV(22..63) where F^2 = (3*VIX3M^2 - VIX^2)/2 (forward variance), minus mean of VIX^2 - RV(1..21); plus conditional version when VIX3M/VIX > 1.10.
- null: Forward variance premium <= spot variance premium (no extra term premium).
- procedure: Daily VIX, VIX3M since 2007 (VIX3M start), SPY realised variance; non-overlapping 63d cycles; studentized block bootstrap; walk-forward threshold selection; deflated Sharpe on the conditional short-forward-variance series.
- data: CBOE VIX and VIX3M history, SPY closes. · min n: 70
- pass: Forward premium > spot premium with 95% CI excluding zero; conditional premium positive in both halves of the sample.
- controls: Shuffle VIX3M/VIX ratio placebo; exclude 2008 and 2020 as sensitivity.
- harness: term_vs_spot_premium
- result X-44c31e4c: not_supported — forward premium minus spot premium +0.0046 (variance units) over 68 non-overlapping 63d cycles, p=0.351; conditional (VIX3M/VIX>1.10, n=48) forward premium halves +0.0234/+0.0031
- result X-1edbb78f: inconclusive — forward premium minus spot premium +0.0046 (variance units) over 68 non-overlapping 63d cycles, p=0.351; conditional (VIX3M/VIX>1.10, n=48) forward premium halves +0.0234/+0.0031; verdict: implemented criteria pass; not implemented: forward premium > spot premium, 95% CI excluding 0 (fails, not decisively, below min_n: undecided); short far leg / reverse calendar (vega-weighted) when VIX3M/VIX > 1.10 has positive expectancy (walk-forward threshold, deflated Sharpe on the conditional short-forward-variance series, shuffled-ratio placebo, ex-2008/2020 sensitivity): not implemented; sample reaches trial min_n 70 cycles (68 so far)
- note: from the options-library library: Calendar vol spread (ATM time spread, long or reverse); harness suggestion: Extend harness_term_structure with the forward-variance decomposition F^2 = (3*VIX3M^2 - VIX^2)/2 and a 63-day realised window; P&L of the calendar via build_position with two expiries. | superseded by T-530 (verifier-corrected wording)

### T-238 · vix_contango_short_call_spread

**Claim.** When VIX3M exceeds VIX by more than 10% (contango), spot VIX 21 trading days later is below the VIX3M-VIX-implied 1-month forward level F = sqrt((3*VIX3M^2 - VIX^2)/2) in more than 65% of months, so a VIX call spread struck at F has positive expectancy.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.cboe.com/tradable_products/vix/term_structure/
- statistic: Frequency and mean of F_t - VIX_{t+21} conditional on VIX3M/VIX > 1.10; simulated P&L of the call spread priced with BS on F using VVIX as IV.
- null: VIX_{t+21} >= F on average (the forward is unbiased or too low).
- procedure: Daily VIX, VIX3M, VVIX since 2007; non-overlapping 21d cycles; studentized block bootstrap; walk-forward threshold; deflated Sharpe; sensitivity to using actual VIX futures when CFE settlement history is added.
- data: CBOE VIX, VIX3M, VVIX history (VIX futures settlement history is not in the free set; F from VIX3M/VIX is the proxy). · min n: 100
- pass: Conditional frequency > 0.60 with 95% CI above 0.5 and mean F - VIX_{t+21} > 0 at p<0.05; simulated call-spread Sharpe > 0.5 after 0.10 vol-point costs.
- controls: Unconditional (no contango filter) control; shuffled term-structure placebo.
- harness: vix_forward_contango
- result X-a0277481: inconclusive — in contango (VIX3M/VIX>1.10), VIX 21 days later is below the forward 147/177 = 83% (95% CI 0.77-0.88); mean F - VIX(t+21) +2.90 pts, p=0.0005; data part passes, call-spread simulation not implemented
- result X-0b47e7e3: inconclusive — in contango (VIX3M/VIX>1.10), VIX 21 days later is below the forward 147/177 = 83% (95% CI 0.77-0.88); mean F - VIX(t+21) +2.90 pts, p=0.0005; data part passes, call-spread simulation not implemented
- note: from the options-library library: VIX futures roll-down harvest via short VIX call spread; harness suggestion: Extend harness_term_structure with the forward-level proxy F and a VIX-call-spread pricer (bs.price with sigma = VVIX/100, T from the VIX monthly calendar). | harness implements the data part only: it can falsify the claim, and a passing data part returns inconclusive until the strategy simulation exists | superseded by T-534 (verifier-corrected wording)

### T-324 · etf-nav-premium-reversion

**Claim.** For SPY/IVV from 2010-01 to 2026-09, the twin rule (enter at |z| > 2 of the 60-day log price-ratio z-score, exit at z = 0 or 5 days) earns a positive mean net return per trade after 2 bps per leg per trade (8 bps per round trip of both legs).

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.3905/jod.2006.635418, https://doi.org/10.2139/ssrn.1572907
- statistic: mean net return per trade with bootstrap interval; AR(1) half-life of x_t and share of signals whose excursion exceeds costs as diagnostics
- null: zero mean net return per trade
- procedure: Compute x_t from Yahoo adjusted closes (total-return basis neutralizes SPY's quarterly UIT dividend timing). Simulate the rule with trailing statistics only. Bootstrap over trades, clustered by month. Repeat on the other twins and report as variants in DSR.
- data: Yahoo daily adjusted closes: SPY (1993), IVV (2000), VOO (2010), QQQM (2020-10), GLD (2004), IAU (2005), IBIT/FBTC (2024-01) · min n: 1000
- pass: 95% lower bound of mean net return per trade > 0 AND DSR > 0.95 across the 5 twin variants; otherwise park as 'reversion real but below retail cost'
- controls: Look-ahead: trailing windows; execute at the next close after the signal. Dividends: total-return series, because SPY (UIT) holds dividends in cash and pays quarterly with a lag, creating a slow drift absorbed by the trailing mean. Closing-auction prints for both legs. Costs: 2 bps per leg per trade. Survivorship: none (all twins listed). Multiple testing: 5 twins. Regime: March 2020 reported separately.
- harness: ohlc_spy_ivv_twin
- result X-baa72a98: inconclusive — SPY/IVV 2010-01-04..2026-09-30 (4211 days): 175 trades at |z|>2, mean gross +0.17 bps, net -7.83 bps after 8 bps RT (month-clustered 95% CI -9.14..-6.58); DSR 0.000 across 5 twins (variance of trial Sharpes zero-skill floor: VOO, IAU, QQQM, FBTC not archived); AR(1) phi 0.940, half-life 11.3 days; 27% of signals with excursion > cost; March 2020 2 trades; min_n counted in trades (the statistic is per trade): 175 trades, the window allows about 2105 at most; on the trades available the CI lies entirely below 0 and these criteria would fail: 95% lower bound of mean net return per trade > 0; DSR > 0.95 across 5 twin variants — data cannot support the claim: 175 trades, below the trial's min_n 1000
- note: from the underlying-library library: ETF premium/discount to NAV reversion (and identical-exposure twins); harness suggestion: twin_spread_halflife: ratio AR(1), excursion-vs-cost counter, rule simulator; later nav_premium_reversion when NAV lands | verifier: corrected claim/trial

### T-329 · crypto-futures-basis-carry

**Claim.** From 2018-01 to 2026-09, after the annualized CME front-month BTC basis rises more than 2 sd above its trailing 60-day mean, a long-spot/short-futures position held 5 trading days earns a positive mean net return after 20 bps round-trip costs (equivalently, the basis falls by more than its deterministic time decay plus costs).

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.bis.org/publ/work1087.htm, https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency
- statistic: mean net return per trade (spot P&L + futures P&L - costs) with bootstrap interval; diagnostic: mean 5-day change in basis vs the time-decay-implied change
- null: mean net return per trade = 0 (block-shifted signal null, block 20 days)
- procedure: Build b_t from Yahoo BTC=F and Coinbase hourly candles at settlement time. Drop roll windows. Trailing z. Simulate trades. Bootstrap over trades clustered by month. DSR over 5 variants. Pre/post spot-ETF (2024-01) split.
- data: Yahoo BTC=F (2017-12-) and ETH=F daily; Coinbase BTC-USD hourly (2015-, verified); FRED DTB3; Deribit public book summaries (today forward) · min n: 40
- pass: 95% lower bound of mean net return per trade > 0 AND same sign before and after 2024-01 AND DSR > 0.95
- controls: Synchronicity: Yahoo BTC-USD's 00:00 UTC close is 2-3 hours away from CME settlement, and that hourly BTC move (~0.5-1%) exceeds a month of basis, so only settlement-aligned hourly spot is valid. T-362 uses BTC-USD daily closes and has the same flaw (flagged). Roll contamination: BTC=F is a continuous front-month series, expired per-contract history is not on Yahoo (BTCZ23.CME returns null), so roll windows are excluded rather than reconstructed. Costs: 20 bps round trip plus margin financing at DTB3+1.5%. Regime: 2021 boom, 2022, post-ETF. Multiple testing: 5 variants.
- harness: carry_cme_basis_spike
- result X-2543136c: inconclusive — 30 trades 2019-06-18..2026-08-18 (synchronous spot from 2019-05-01; z > 2 vs the valid settles in the trailing 60 trading days, at least 20, the 5 days before expiry excluded; enter next settle, hold 5 trading days in the same contract, 20 bp round trip; 17 exits inside the roll window): mean net +0.178%, one-sided 95% lower bound +0.070% (need > 0); pre-2024 mean +0.229% (n=22), post +0.039% (n=8) (need both > 0); DSR 0.982 (need > 0.95); window from 2018-01 covered: no, no settle-synchronous spot before 2019-05-01 — implemented criteria pass; not implemented: trades >= 40 (min_n); claim window from 2018-01 covered by settle-synchronous spot
- note: from the underlying-library library: Crypto futures basis / cash-and-carry (CME BTC futures and Deribit); harness suggestion: basis_carry_harness: basis calculator with roll detection, hurdle rule, hold-to-expiry accounting; daily Deribit snapshot writer for the forward sample | verifier: corrected claim/trial

### T-361 · post-fomc-monetary-momentum

**Claim.** Over 1994-2026, SPY's cumulative return over the 15 trading days starting at the close of t+2 after a scheduled FOMC statement is higher after expansionary surprises (DGS2 down more than 5 bps on day t) than after contractionary ones (up more than 5 bps) by at least 1 percentage point, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w24748, https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm
- statistic: Mean 15-day SPY return after expansionary minus after contractionary meetings (pp).
- null: Zero gap. Permutation of surprise labels across meetings (10,000); bootstrap over meetings.
- procedure: Classify each scheduled meeting by the DGS2 change; entry at the t+2 close respects H.15 publication. Halves 1994-2009 / 2010-2026; ZLB meetings 2009-2015 (compressed DGS2 moves) reported separately. 6 variants Holm.
- data: daily-history-SPY (stored); fred-DGS2 (stored; fredgraph.csv keyless, verified to 2026-10-09); FOMC dates (Fed site); ^FVX via Yahoo; Polymarket Fed markets (stored); Kalshi KXFEDDECISION via /historical. · min n: 120
- pass: Gap > 1 pp with permutation p < 0.05 and both halves positive; the long-only expansionary arm's Sharpe beats buy-and-hold over matched windows.
- controls: Look-ahead: entry after DGS2 is published (t+2); the ^FVX variant uses same-day closes. Survivorship: n/a. Costs: up to 16 legs/yr at 1-2 bps. Multiple testing: 6 variants. Regime: halves and ZLB split.
- harness: fomc_monetary_momentum
- result X-bf82b216: inconclusive — only 85 expansionary+contractionary meetings (min_n 120); SPY 15 trading days from the t+2 close: after 50 expansionary (DGS2 < -5 bps) +0.42% vs 35 contractionary -0.30% of 261 classified meetings: net gap +0.64 pp (95% CI -1.34 to +2.74), permutation p=0.2097; 1994-2009 +0.67 pp, 2010-2026 +0.70 pp; ZLB 2009-2015 +3.94 pp; long-only arm Sharpe 0.05 vs buy-and-hold 0.52 (1994-01-03..2026-10-09, excess over T-bills) — inconclusive: only 85 of 261 classified meetings enter the gap (min_n 120); criteria on this sample, not used for the verdict: failed: net gap > 1 pp; permutation p < 0.05; long-only expansionary arm Sharpe > buy-and-hold Sharpe
- note: from the underlying-library library: Post-FOMC directional drift (monetary momentum); harness suggestion: data/fetch.py: fred_series('DGS2') (the FRED route exists); events.py: post_event_directional_drift(days, closes, event_days, signal_by_event, horizon=15, threshold_bps=5) with label permutation and block bootstrap. | verifier: corrected claim/trial

### T-503 · long-box-spread-lend

**Claim.** On the capture day, the median mid-price SPX box lending rate across SPX/SPXW expiries with 60-120 DTE (strike pairs within +/- 15% of spot) exceeds the FRED 3-month bill (continuously compounded) by between 15 and 80 bp.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Box_spread, https://www.nber.org/papers/w26138
- statistic: Median over boxes of r_box_mid - r_bill; companion executable rate r_box_exec (pay the ask on long legs, receive the bid on short legs).
- null: Median r_box_mid - r_bill <= 15 bp or >= 80 bp.
- procedure: Day one: build all boxes at 60-120 DTE (matched to the 3-month bill) from strike pairs with both legs bid > 0; r_box = ln((K2-K1)/debit)/T; median and bootstrap CI over strike pairs; repeat daily; extend to 6-12 months once DGS6MO/DGS1 are pulled from the same free FRED API.
- data: CBOE delayed SPX chain (29,918 contracts today), FRED DGS3MO. · min n: 20
- pass: Day-one median spread inside [15, 80] bp with the 95% bootstrap CI inside [0, 120] bp; persistence over 20 captured days.
- controls: Strike-invariance of r_box (if r_box varies by more than spreads across pairs, quote noise dominates); SPX AM vs SPXW PM roots; XSP replication; convert DGS3MO from bond-equivalent to continuous.
- harness: box_mid_v2
- result X-afab5dd0: inconclusive — day one 2026-10-14: 15583 boxes (SPX and SPXW, 60-120 DTE), mid box rate minus bill median +63 bp (95% CI +63 to +63); needs [15, 80] with CI in [0, 120]; persistence needs 20 capture days (2 so far); the CI resamples boxes that share strikes, so it understates uncertainty
- result X-23bc344d: inconclusive — day one 2026-10-14: 15583 boxes (SPX and SPXW, 60-120 DTE), mid box rate minus bill median +63 bp (95% CI +63 to +63); needs [15, 80] with CI in [0, 120]; later days: 2026-10-15 +65 bp (in range); persistence needs 20 capture days (2 so far); the CI resamples boxes that share strikes, so it understates uncertainty
- result X-0e895672: inconclusive — day one 2026-10-14: 248432 boxes (SPX and SPXW, 60-120 DTE, all strike pairs), mid box rate minus bill median +39 bp (95% CI +39 to +39); needs [15, 80] with CI in [0, 120] (robustness, $25 grid and width >= 5% of spot: +44 bp over 15583 boxes); later days: 2026-10-15 +44 bp (in range); persistence needs 20 capture days (2 so far); the CI resamples boxes that share strikes, so it understates uncertainty; verdict: implemented criteria pass; not implemented: persistence: in range on every one of the first 20 captured days (2 so far)
- note: from the options-library library: Long box spread (SPX box lending); harness suggestion: mandel/options/box.py: box_rate(chain, expiry, K1, K2, side) and daily box_curve; payoff-engine test asserts a flat K2 - K1. | verifier-corrected restatement of T-186, whose verdict tested the earlier wording and stands | the bootstrap CI over boxes is too narrow (boxes share strikes and are not independent); the persistence criterion over 20 capture days is the real test

## Untested (169)

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

### T-101 · short-straddle

**Claim.** For 30-DTE ATM SPY short straddles priced at the model price BS(0.90*VIX/100), mean P&L per unit premium is higher when entered with VIX minus trailing 21-day realised vol in its top tercile than in its bottom tercile, out of sample (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-straddle, https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf
- statistic: difference in mean P&L/premium (top tercile minus bottom tercile of VIX - RV21 at entry); studentized block-bootstrap CI; deflated Sharpe with n_trials = number of conditioning rules tried
- null: no tercile difference
- procedure: overlay_backtest(strategy='short_straddle') with iv_scale in {0.81, 0.90, 1.00}; RV21 from SPY log returns; tercile cut-points set on the training window of walk_forward_splits and applied out of sample
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 390
- pass: OOS top-minus-bottom difference CI excludes 0 at s = 0.90, with the same sign at s = 0.81 and s = 1.00
- controls: Tercile thresholds fixed in-sample. Report skewness, kurtosis, PSR, max drawdown and the unconditional mean (T-57 found +0.24%/month, p 0.07, at s = 0.81). Repeat with a 5%-of-premium round-trip haircut. 2008 and 2020 stay in the sample.
- note: from the options-library library: Short Straddle; harness suggestion: harness 'short_straddle_vrp' sharing options.py pricing; conditioning rule set declared up front and passed to deflated_sharpe_ratio(n_trials=len(rules)) | verifier: corrected claim/trial

### T-103 · short-strangle

**Claim.** A 30-DTE SPY short strangle at +/-5% strikes, priced with the smile-scaled VIX model, has a higher Sharpe ratio than the ATM short straddle priced on the same model and the same entry dates, 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-strangle, https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf
- statistic: paired Sharpe difference (strangle - straddle) of per-cycle returns on notional; studentized block bootstrap via compare_strategies
- null: no Sharpe difference
- procedure: Same entry dates as the short-straddle harness; price both structures with the smile-scaled model and pay at intrinsic.
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3, options-surface-2026-10-14 (smile ratios) · min n: 390
- pass: paired Sharpe difference p < 0.05 with strangle > straddle; same sign under the flat-VIX and SKEW-scaled sensitivities
- controls: Width fixed at 5% before looking. The same 5%-of-premium cost haircut applies to both. Report PSR, max drawdown and skew. Proxy cap until 60 capture days refit the smile ratios.
- note: from the options-library library: Short Strangle; harness suggestion: harness 'short_strangle_vs_straddle' using compare_strategies from mandel/validation/backtest_eval.py on per-trade P&L series | verifier: corrected claim/trial

### T-113 · jade-lizard

**Claim.** A 1-month SPY jade lizard (short 30-delta put, short 30-delta call, long call 1% of S above it, priced at VIX IV; model-priced; months with credit < width skipped) has a positive mean P&L per unit of naked-put margin over 1993-2026.

- kind: options-strategy · origin: options-library:volatility, https://www.tastylive.com/concepts-strategies/jade-lizard, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean P&L / (0.2 x S) with block bootstrap CI; number of skipped months reported
- null: mean <= 0
- procedure: monthly cycles; solve the 30-delta strikes at VIX IV; enter only when Cr >= w; payoff from the SPY close
- data: SPY, VIX, DTB3 · min n: 250
- pass: lower CI > 0 and positive in both walk-forward halves
- controls: Overlaps the neutral/income family; DSR counts it once across families. Flat pricing understates the put credit and overstates the call credit relative to real skew; recheck with chain mids at 60 days.
- note: from the options-library library: Jade Lizard; harness suggestion: harness 'jade_lizard_condition' in options.py reading chain capture; shares strike-by-delta selector with bwb harness | verifier: corrected claim/trial

### T-123 · gamma-scalping-long-straddle

**Claim.** A 30-DTE ATM SPY straddle bought at BS(0.90*VIX) and delta-hedged daily at that entry vol has negative mean P&L per unit vega over 1993-2026 (MODEL-PRICED proxy).

- kind: options-strategy · origin: options-library:volatility, https://emanuelderman.com/wp-content/uploads/1999/02/gs-volatility_swaps.pdf, https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf
- statistic: mean hedged P&L/vega over non-overlapping cycles, studentized block-bootstrap CI; run at s in {0.81, 0.90, 1.00}; secondary: correlation of P&L with (RV_21 - (s*VIX)^2)
- null: mean hedged P&L = 0
- procedure: Each cycle: price the straddle at s*VIX_t; each day compute BS delta (bs.greeks) at the entry vol, hedge at the SPY close, charge 1 bp per share traded; sum to expiry
- data: daily-history-SPY, cboe-VIX-history, fred-DTB3 · min n: 390
- pass: upper CI < 0 at s = 0.90; report the s at which the sign flips
- controls: Daily (not intraday) hedging; cost declared; VIX is SPX; q = 0 with unadjusted closes; report the variance-term share of P&L vs hedging error; BTZ 1990-2007 as an external anchor (monthly %^2 units).
- note: from the options-library library: Gamma Scalping a Long Straddle (delta-neutral); harness suggestion: harness 'gamma_scalp_vrp' in options.py: functions bs_delta, hedge_path(prices, vix_entry, r, cost_bps) returning per-trade P&L; verdict via block_bootstrap_pvalue and a reported VRP series; a sibling 'dvol_vrp' harness runs the same on BTC with DVOL as IV (bundles deribit-dvol-daily, btc-daily-closes) | verifier: corrected claim/trial

### T-128 · short-naked-put

**Claim.** Selling a 1-month ATM SPY put at VIX IV (model-priced), fully collateralised in 3-month bills with the PUT-index construction, has a higher Sharpe ratio than SPY buy-and-hold over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/naked-put-uncovered-put-short-put, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_SP_500_PutWrite_Indices_Methodology.pdf
- statistic: annualised Sharpe difference (putwrite minus SPY) with studentized block bootstrap p-value; also the max drawdown ratio
- null: Sharpe(putwrite) <= Sharpe(SPY)
- procedure: third-Friday roll; strike = nearest strike at or below spot; premium = BS put at VIX IV; collateral earns DTB3; settle at the SPY close (proxy for the SOQ); walk-forward halves; repeat at iv_scale 0.9
- data: SPY, VIX, DTB3; benchmark check against the actual Cboe PUT index daily history (cdn.cboe.com PUT_History.csv: 4,983 rows from 1991-03-04 to 2026-10-13, with gaps) · min n: 300
- pass: p < 0.05 at both iv_scale 1.0 and 0.9, holding in both walk-forward halves
- controls: Correction: VIX is usually above ATM IV, so pricing the ATM put at VIX overstates the premium and the result is optimistic, not conservative; the 0.9 x VIX run and the comparison with the real PUT index guard this. Sharpe flatters negatively skewed returns, so report skew, kurtosis and PSR. SPY is price-only unless total return is reconstructed; state the dividend convention.
- note: from the options-library library: Short (Naked / Cash-Secured) Put; harness suggestion: putwrite_vs_spy() reproducing the Cboe PUT methodology with VIX pricing; later swap in captured SPY chain mids | verifier: corrected claim/trial

### T-133 · ratio-front-spread-1x2

**Claim.** A 1-month zero-cost 1x2 SPY call ratio spread (long 1 ATM call, short 2 calls at the strike where 2C(K2) = C(K1), all priced at VIX IV; model-priced) has a positive mean monthly P&L per unit spot, yet loses more than 3x its median gain in more than 3% of months, over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/short-ratio-put-spread
- statistic: mean P&L per unit spot with block bootstrap CI; frequency of months with a loss > 3x the median gain, with binomial CI
- null: mean <= 0, or tail frequency <= 3%
- procedure: monthly cycles; solve K2 for zero cost at that month's VIX; long 1 call at S, short 2 at K2; payoff from the SPY close
- data: SPY, VIX, DTB3 · min n: 300
- pass: lower CI of the mean > 0 AND tail-frequency lower CI > 3% (both pre-registered)
- controls: Flat IV overprices the OTM shorts relative to the real smile, so the real zero-cost K2 sits closer to ATM (more negative gamma); report by VIX tercile; recheck with chain mids at 60 days.
- note: from the options-library library: Ratio Vertical Front Spread (1x2 Call or Put Ratio Spread); harness suggestion: vix_priced_option_returns(strategy='ratio_call_1x2', dte=30, strikes=('ATM','OTM5')) | verifier: corrected claim/trial

### T-135 · ladder-christmas-tree

**Claim.** A 1-month 1-3-2 SPY call Christmas tree (A = ATM, w = 2.5%, priced at VIX IV; model-priced) finishes inside its profit zone [K1 + D, K4 - D/2] more often than the zone's Black-Scholes risk-neutral probability at entry over 1993-2026 (VRP narrows the realised distribution and positive drift moves mass into the zone just above spot).

- kind: options-strategy · origin: options-library:directional-vertical, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-christmas-tree-spread-calls
- statistic: realised zone hit rate minus the mean risk-neutral zone probability at entry, with block bootstrap CI
- null: hit rate <= risk-neutral probability
- procedure: monthly cycles; price the 4 strikes at VIX IV; compute the zone; count months in which the SPY close lands in the zone; RN probability from the same lognormal (N(d2) differences)
- data: SPY, VIX, DTB3 · min n: 300
- pass: lower CI of (hit - RN) > 0
- controls: Correction: the original direction (hit rate below RN because drift carries SPY past the zone) does not hold up. Monthly drift is about 1% and the zone spans about +1% to +7%, so drift and VRP both push mass into the zone; the claim was reversed. The zone is defined from model prices only; report ATM and ITM anchors.
- note: from the options-library library: Ladder / Christmas Tree (1-3-2 and 1-1-1); harness suggestion: vix_priced_option_returns(strategy='call_tree_132', dte=30, width=0.025) with zone_hit_rate statistic | verifier: corrected claim/trial

### T-136 · stock-repair

**Claim.** After a 10%+ SPY drawdown from its 252-day high, a 3-month zero-cost stock repair (stock + long 1 ATM call + short 2 calls at K2 = (prior high + spot)/2, priced at VIX IV; model-priced) has a higher mean 3-month P&L than holding SPY alone, over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/stock-repair, https://www.optionseducation.org/strategies/all-strategies/covered-ratio-spread
- statistic: mean of (repair P&L - hold P&L)/S per episode, which equals the embedded 1x2 call ratio spread's P&L; studentized bootstrap over non-overlapping episodes
- null: mean difference <= 0
- procedure: detect the first day of each >= 10% drawdown from the trailing 252-day high (re-arm after 63 days); B = prior high; K1 = S, K2 = (B+S)/2 at VIX IV (VIX3M where available, since the tenor is about 63 days); mark both at the 63-day SPY close
- data: SPY, VIX, VIX3M, DTB3; QQQ as a second sample · min n: 30
- pass: lower CI of the mean difference > 0
- controls: Correction: the original 'recovers breakeven more often' claim was tautological, because the repaired breakeven K2 < B makes it true by construction; replaced with the mean-P&L comparison. Expect only about 25-40 SPY episodes, so report power; QQQ episodes overlap in time and are not independent. Flat IV misprices skew (stated).
- note: from the options-library library: Stock Repair (Covered Ratio Spread); harness suggestion: drawdown_event_study(strategy='stock_repair', trigger=-0.10, horizon=63d) | verifier: corrected claim/trial

### T-138 · risk-reversal-directional

**Claim.** Months in which the CBOE SKEW index at entry is in its top quintile (steep put skew) are followed by a higher mean 1-month P&L on a bullish SPY risk reversal (long 5%-OTM call, short 5%-OTM put, legs priced at VIX IV; model-priced) than months in the bottom quintile, 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://en.wikipedia.org/wiki/Risk_reversal, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: difference in mean monthly P&L per unit spot, top minus bottom SKEW quintile, studentized block bootstrap
- null: difference <= 0
- procedure: monthly cycles from SPY inception (1993); quintiles of SKEW computed on the full history and also on an expanding window; legs priced at VIX IV; payoff from the SPY close
- data: SPY, VIX, CBOE SKEW daily, DTB3 · min n: 300
- pass: lower CI of the difference > 0 in both the full-sample and expanding-window quintile definitions
- controls: Flat pricing means the entry premium does not vary with skew, so this isolates the conditional return of the underlying wings (a SKEW timing test). A real skew-premium test needs chain capture (60+ days, follow-up). Under flat pricing the structure is a small debit, not a credit; state this. SPY starts in 1993, so the sample is 1993-2026, not 1990.
- note: from the options-library library: Risk Reversal (Directional, OTM Combo); harness suggestion: conditional_option_returns(strategy='risk_reversal_25d', condition='SKEW quintile'); follow-up skew_premium_harvest once chains have 60 days | verifier: corrected claim/trial

### T-139 · leaps-stock-replacement

**Claim.** A SPY 1-year 20%-ITM call priced at VIX3M IV (VIX before 2007; model-priced), rolled annually with the rest of the capital in 3-month bills, earns a lower annualised return than SPY over 1993-2026 but with a smaller maximum drawdown.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/long-call, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: annualised return difference (LEAPS + bills minus SPY) with block bootstrap CI; ratio of max drawdowns
- null: return difference >= 0, or drawdown ratio >= 1
- procedure: annual cycles plus 12 monthly-staggered cohorts; K = 0.8*S; BS at VIX3M/100 (VIX before 2007-12), r = DTB3, q = constant assumption; hold to expiry; (S - C) earns DTB3; compare against SPY under the same dividend convention as q
- data: SPY, VIX, VIX3M, DTB3 · min n: 30
- pass: return difference upper CI < 0 AND drawdown ratio < 1 (both pre-registered); report that n of independent annual cycles is about 33
- controls: Correction: by put-call parity, call + (S - C) in bills = SPY + a 1-year 20%-OTM put financed at the bill rate (with dividends via q), so the original claim (higher return, drawdown >= 1.5x SPY) contradicted the structure, since loss per cycle is capped at C. The return difference equals the embedded put's P&L. IV proxy mismatch: 1-year IV is usually above VIX3M, so the put cost is understated (stated).
- note: from the options-library library: LEAPS Call as Stock Replacement; harness suggestion: vix_priced_option_returns(strategy='leaps_itm20', dte=365, iv_source='VIX3M', cohorts='monthly') | verifier: corrected claim/trial

### T-140 · deep-itm-call-stock-substitute

**Claim.** A monthly-rolled SPY 10%-ITM call priced at VIX IV (model-priced), held with the rest of the capital (S - C) in 3-month bills, has a daily-return correlation above 0.98 with SPY and an annualised shortfall versus SPY below 1 percentage point over 1993-2026.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/long-call, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: correlation of daily portfolio returns (call re-marked by BS at that day's VIX, plus bills) with SPY; annualised shortfall vs SPY under the same dividend convention as q; block bootstrap CIs
- null: correlation <= 0.98 or shortfall >= 1 pp
- procedure: monthly roll at K = 0.9*S at VIX IV; mark daily; compute portfolio returns and shortfall relative to SPY
- data: SPY, VIX, DTB3 · min n: 300
- pass: correlation lower CI > 0.98 AND shortfall upper CI < 1 pp
- controls: Correction: the original drag bound (DTB3*K/S + 1pp) compared an unfunded option with SPY. With the bills included, parity makes the shortfall equal the P&L of the embedded 10%-OTM 1-month put (premium minus payoff), which is the quantity tested. Bid-ask on deep-ITM strikes is not in the history; add it once chain capture reaches 20 days.
- note: from the options-library library: Deep ITM Call as Short-Dated Stock Substitute; harness suggestion: vix_priced_option_returns(strategy='deep_itm_call', dte=30, strike='ITM10', daily_marks=True) | verifier: corrected claim/trial

### T-143 · long-calendar-spread

**Claim.** A 30/60-DTE ATM SPY call calendar held to the front expiry, model-priced (front IV = VIX, back IV = VIX/VIX3M total-variance interpolation to 60 days), has a higher mean P&L per unit of debit on entries made when VIX/VIX3M >= 1.0 than on entries made when VIX/VIX3M <= 0.9.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-calls, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-puts
- statistic: Difference in mean P&L/debit to the front expiry between entries with VIX/VIX3M >= 1.0 and entries with VIX/VIX3M <= 0.9
- null: No regime difference: the VIX/VIX3M regime label is circularly block-shifted against the P&L series
- procedure: Run from 2007-12-04, the first VIX3M date (verified in FRED VXVCLS). On each trading day, price 30- and 60-DTE ATM calls with Black-Scholes (front IV = VIX; back IV from the total-variance interpolation w(60) = w(30) + (w(93) - w(30))*(60-30)/(93-30), where w = IV^2*T). Hold 21 trading days, then revalue the far leg at the IV interpolated that day and the SPY close. Use a studentized block bootstrap (block 21) on the daily series, a plain bootstrap on non-overlapping monthly entries, deflation for the thresholds tested, and walk-forward halves.
- data: SPY daily closes, CBOE VIX and VIX3M daily history, FRED 3-month bill rate (all free and in the data list) · min n: 30
- pass: Regime difference > 0 with p < 0.05 after deflating for thresholds (0.9/0.95/1.0), with the same sign in both walk-forward halves. A sensitivity rerun at today's measured SPY 30/60-DTE ATM IV spread from the chain capture.
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV because it includes the skew, so using VIX as ATM IV overstates premium levels. This trial is model-priced, not market-priced, and runs on a flat smile. The verdict stays 'model-only' until at least 120 daily chain captures confirm the real front-vs-back ATM IV spread. Costs and pin risk at T1 are modelled by closing both legs at mid minus half the spread. Backwardation entries cluster in 2008, 2011, 2020 and 2022, so report the result with each of those episodes left out.
- note: from the options-library library: Long calendar (horizontal) spread; harness suggestion: Add a two-expiry mode to the payoff engine: Position.value_at(t=T1) that settles legs with T<=T1 at intrinsic and reprices legs with T>T1 via bs.price at a supplied IV; then calendar_model_backtest(price_rows, vix_rows, vix3m_rows, front_dte, back_dte, strike_rule) in experiments/volatility.py reusing _block_shift_null and _halves_agree. | verifier: corrected claim/trial

### T-144 · short-calendar-spread

**Claim.** A 30/60-DTE ATM SPY short call calendar, entered only on days when VIX3M/VIX >= 1.15 (steep contango) and closed at the front expiry, has positive mean P&L, model-priced (front IV = VIX, back IV = VIX/VIX3M total-variance interpolation).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/short-calendar-spread-calls, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3
- statistic: Mean P&L per conditional entry as a fraction of the far leg's premium
- null: Zero conditional mean (studentized block bootstrap); for the placebo, the regime label is block-shifted
- procedure: Daily entries since 2007-12-04 on days meeting the gate. Price with Black-Scholes from VIX/VIX3M. Revalue the far short at T1 (21 trading days) with the IV interpolated that day. Studentized block bootstrap (block 21), walk-forward halves, and deflation for the 1.10/1.15/1.20 thresholds.
- data: SPY closes, CBOE VIX, VIX3M, FRED 3-month bill · min n: 60
- pass: Conditional mean > 0 with the 95% CI excluding 0 in both halves after deflation, surviving removal of the five largest VIX-spike months
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced, and runs on a flat smile. A VIX-level tercile control checks that the result is not just a low-VIX effect. Unconditional entry is reported alongside. Cost is half the bid-ask on four fills, from today's SPY chain spreads.
- note: from the options-library library: Short (reverse) calendar spread; harness suggestion: Reuse calendar_model_backtest with legs reversed and an entry mask from the VIX3M/VIX ratio; report conditional/unconditional means side by side with the existing term_structure_reversion output. | verifier: corrected claim/trial

### T-145 · long-diagonal-spread

**Claim.** On SPY, a 0.70-delta/90-DTE long call vs 0.30-delta/30-DTE short call diagonal, with the short rolled monthly and the long replaced at 30 DTE, has a higher annualised Sharpe ratio than the 30-DTE vertical call spread on the same strikes rolled monthly, model-priced (VIX as the 30-DTE IV, VIX/VIX3M total-variance interpolation for 90 DTE).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/concepts-strategies/diagonal-spread, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-calls
- statistic: Difference in annualised Sharpe between the diagonal and the vertical
- null: Zero difference; monthly P&L pairs permuted between the two strategies
- procedure: Monthly entries since 2007-12. Black-Scholes pricing with daily mark-to-model. Paired bootstrap on monthly P&L, walk-forward halves, deflated Sharpe for the pair.
- data: SPY closes, VIX, VIX3M, FRED 3-month bill · min n: 150
- pass: Sharpe difference > 0 with the bootstrap 95% CI excluding 0 in both halves, and PBO < 0.5
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced. A flat smile overstates SPY OTM call premia, so rerun with a SKEW-index tilt. Report how often each entry met tastylive's setup rules. Costs come from today's SPY chain spreads.
- note: from the options-library library: Long diagonal spread (bullish call / bearish put); harness suggestion: Extend the two-expiry payoff mode with a roll schedule (list of (dte, action) tuples) so diagonals, PMCC and collars share one simulator; output Sharpe/PBO through the existing overfit module. | verifier: corrected claim/trial

### T-146 · double-calendar

**Claim.** Entered on the same days and held to the front expiry, a +/-5% 30/60-DTE double calendar on SPY has a lower standard deviation of P&L as a percentage of debit than the ATM single calendar of the same expiries, model-priced (VIX/VIX3M).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/double-diagonal-spread, https://www.tastylive.com/concepts-strategies/calendar-spread
- statistic: Ratio of standard deviations of P&L/debit (double / single), paired by entry date
- null: Ratio = 1 (variance-ratio test via paired bootstrap of non-overlapping monthly entries)
- procedure: Daily entries since 2007-12-04 with Black-Scholes pricing from VIX/VIX3M (OTM legs at the same flat IV; a SKEW-based tilt as a sensitivity), revalued at T1. Non-overlapping monthly subsample for CIs; walk-forward halves.
- data: SPY closes, VIX, VIX3M, SKEW, FRED 3-month bill · min n: 150
- pass: Std ratio < 0.9 with the 95% CI excluding 1 in both halves
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced. A flat smile understates the put wing. Commissions for 8 fills vs 4. Pin risk modelled by closing at mid minus half the spread at T1. The OTM debit is smaller, so also report std of P&L per unit of max loss.
- note: from the options-library library: Double calendar spread; harness suggestion: Same two-expiry simulator as the single calendar with a strike list; add SKEW-index tilt as an optional smile adjustment (put IV = VIX + k*(SKEW-100)). | verifier: corrected claim/trial

### T-147 · double-diagonal

**Claim.** On SPY, a double diagonal (near 0.16-delta strangle at 30 DTE, far 0.10-delta wings at 60 DTE) has a higher mean P&L per unit of max loss than the 30-DTE iron condor on the same strikes when entered with VIX below its trailing 1-year median, model-priced.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/double-diagonal-spread, https://www.tastylive.com/concepts-strategies/diagonal-spread
- statistic: Mean P&L / max loss for the double diagonal minus that of the iron condor, on low-VIX entry days
- null: Zero difference; paired monthly P&L permuted between the two structures
- procedure: Monthly entries since 2007-12 on days with VIX below its trailing 252-day median. Black-Scholes pricing from VIX/VIX3M, with a SKEW tilt as a sensitivity. Revalue at T1; paired bootstrap; walk-forward halves.
- data: SPY closes, VIX, VIX3M, SKEW, FRED 3-month bill · min n: 80
- pass: Difference > 0 with the 95% CI excluding 0 in both halves, holding with and without the SKEW tilt
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced. Costs on eight fills vs four. Max-loss normalisation uses the realised far-wing value at T1.
- note: from the options-library library: Double diagonal spread; harness suggestion: Two-expiry simulator with four legs; add an iron-condor control leg set in the same run and report the paired difference. | verifier: corrected claim/trial

### T-149 · ratio-calendar

**Claim.** Re-sized to vega-neutral at each weekly entry and held 5 trading days, the SPY 30/90-DTE ATM ratio call calendar has weekly P&L whose absolute Spearman correlation with the weekly change in VIX is below 0.3, model-priced (VIX/VIX3M term interpolation).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/concepts-strategies/calendar-spread, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/short-calendar-spread-calls
- statistic: Spearman correlation of 5-day P&L with delta-VIX over the same 5 days
- null: |rho| >= 0.3 (block bootstrap of the correlation)
- procedure: Weekly entries since 2007-12. Black-Scholes pricing with front IV = VIX and back IV from the VIX/VIX3M total-variance interpolation; n set from model vegas at entry. Revalue after 5 trading days with the new interpolated IVs and SPY close. Block bootstrap (block 4 weeks); walk-forward halves. The 1:1 calendar is the comparison.
- data: SPY closes, VIX, VIX3M, FRED 3-month bill · min n: 300
- pass: Upper bound of the 95% CI of |rho| < 0.3 in both halves
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced. Gamma losses co-move with VIX spikes, so also report the correlation of the delta-hedged P&L. Separate top-decile VIX-spike weeks. Costs on 2.7 fills.
- note: from the options-library library: Ratio (vega-weighted) calendar spread; harness suggestion: Add fractional qty support to the two-expiry simulator (already numeric in Leg) and a sizing hook that sets qty from model vegas at entry. | verifier: corrected claim/trial

### T-150 · poor-mans-covered-call

**Claim.** On SPY, a PMCC (0.80-delta 12-month LEAPS replaced at 90 DTE, plus a monthly 0.30-delta short call) does not have a higher annualised Sharpe ratio, measured on capital deployed, than the stock-based covered call with the same short-call rule, model-priced (LEAPS IV = VIX3M, short IV = VIX).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.optionsplaybook.com/blogs/poor-mans-covered-call-how-to-run-a-covered-call-strategy-for-less-capital, https://www.tastylive.com/concepts-strategies/diagonal-spread
- statistic: Difference in annualised Sharpe (PMCC minus covered call), monthly returns on capital deployed
- null: Sharpe(PMCC) > Sharpe(CC): the claim is falsified if the paired-bootstrap 95% CI of the difference lies entirely above 0
- procedure: Monthly rebalance since 2007-12, Black-Scholes pricing and daily mark-to-model, roll rules as in the claim. Paired block bootstrap of the Sharpe difference (run.py _sharpe_diff_p); walk-forward halves. Sensitivity at today's SPY 12-month ATM IV vs VIX3M from the chain capture.
- data: SPY closes and dividends, VIX, VIX3M, FRED 3-month bill · min n: 150
- pass: The claim survives if the CI of the Sharpe difference includes 0 or lies below it in both halves; return on capital and drawdown are also reported
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, and VIX3M (93-day) is a coarse proxy for 365-day IV (sensitivity +/-3 vol points), so this trial is model-priced, not market-priced. The covered call receives dividends and the PMCC does not. Costs on monthly rolls.
- note: from the options-library library: Poor man's covered call (PMCC / LEAPS diagonal); harness suggestion: Roll-schedule simulator shared with diagonals; add a 'capital deployed' denominator option (debit vs stock price) to overlay_verdict so ROC and absolute return are both reported. | verifier: corrected claim/trial

### T-151 · leaps-collar

**Claim.** A LEAPS collar on SPY (12-month -0.25-delta put rolled at 90 DTE, monthly 0.30-delta calls) has a higher annualised Sharpe ratio than the same-delta standard collar with both put and call at 30 DTE rolled monthly, model-priced.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/collar, https://www.optionsplaybook.com/blogs/poor-mans-covered-call-how-to-run-a-covered-call-strategy-for-less-capital
- statistic: Difference in annualised Sharpe (LEAPS collar minus standard collar); max drawdown and the credit-coverage ratio reported alongside
- null: Zero Sharpe difference; paired monthly returns permuted between the two strategies
- procedure: Monthly rebalance since 2007-12 with Black-Scholes pricing (put IV = VIX3M proxy, call IV = VIX) and daily mark-to-model. Paired block bootstrap; walk-forward halves. Sensitivity at today's SPY 12-month 25-delta put IV from the chain.
- data: SPY closes and dividends, VIX, VIX3M, FRED 3-month bill · min n: 150
- pass: Sharpe difference > 0 with the 95% CI excluding 0 in both halves
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, and VIX3M is a coarse proxy for 365-day IV (sensitivity +/-3 vol points), so this trial is model-priced, not market-priced. A flat smile underprices the OTM put: rerun with a SKEW-index tilt. Dividends are credited to the stock leg in both strategies.
- note: from the options-library library: LEAPS collar (long-dated put, serial short calls); harness suggestion: Roll-schedule simulator with an underlying leg; reuse overlay_backtest's drawdown function (dd) and overlay_verdict for the benchmark comparison. | verifier: corrected claim/trial

### T-152 · calendarised-butterfly

**Claim.** In the top-decile months of VIX increase since 2007-12, a calendarised ATM SPY butterfly (+/-3% wings at 60 DTE, 2x ATM body at 30 DTE) loses less per unit of debit by the front expiry than the 30-DTE butterfly on the same strikes, model-priced.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-butterfly-spread-calls, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-calls
- statistic: Mean paired difference in P&L/debit (time fly minus plain fly) within top-decile delta-VIX holding periods
- null: Zero difference in the spike decile (paired bootstrap)
- procedure: Monthly entries since 2007-12. Black-Scholes pricing from VIX/VIX3M. Revalue both structures at T1 and sort by delta-VIX over the hold. Paired bootstrap; walk-forward halves.
- data: SPY closes, VIX, VIX3M, FRED 3-month bill · min n: 15
- pass: Spike-decile difference > 0 with the 95% CI excluding 0
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced (flat smile). Costs on 6 vs 4 contracts. Pin risk modelled at mid minus half the spread. The overall mean P&L is reported but is not the claim.
- note: from the options-library library: Calendarised (time) butterfly; harness suggestion: Two-expiry simulator with K-slot strikes; add the plain butterfly as the control leg set and report by delta-VIX decile. | verifier: corrected claim/trial

### T-153 · jelly-roll

**Claim.** On every SPY chain capture from 2026-10-14 on, the mid-price 30/60-DTE jelly roll at strikes within +/-5% of spot deviates from bill-implied carry, K(exp(-r*T1) - exp(-r*T2)) - PV(div), by less than half the sum of the four legs' bid-ask spreads for at least 95% of strikes.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.law.cornell.edu/uscode/text/26/1256, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-calls
- statistic: Per capture: the share of strikes with |roll_mid - fair| <= 0.5 * sum of the four legs' spreads; median absolute deviation in cents
- null: Share < 0.95 (a binomial test per capture)
- procedure: For each capture, compute the roll at every strike in the band from chain mids, r from FRED, and PV(div) from SPY's quarterly dividend schedule. Repeat on SPX (European; uses each expiry's parity-implied forward) to isolate the early-exercise premium. Accumulate captures; a single capture can falsify.
- data: CBOE SPY and SPX chain captures from 2026-10-14 (mid, bid, ask per leg), FRED 3-month bill, SPY dividend schedule · min n: 200
- pass: Share >= 0.95 on every capture (one failing day falsifies); confirmation at 60 captures
- controls: Exclude zero-bid legs and spreads > 5% of mid. Delayed snapshots may not be synchronous across legs. Ex-dividend-spanning expiries are reported separately (that was a second claim and is now a diagnostic). Compare the SPX result with T-181 parity_check.
- note: from the options-library library: Jelly roll (synthetic time spread / financing trade); harness suggestion: jelly_roll_check(chain_rows, rate, dividends) producing per-capture deviation statistics; store in the options-surface file so it accumulates daily. | verifier: corrected claim/trial

### T-154 · zebra

**Claim.** A monthly 30-DTE SPY call ZEBRA (long 2 delta-0.70 calls, short 1 ATM call, priced at VIX IV; model-priced) has a lower mean monthly P&L than a delta-matched SPY position (entry delta x 1 share) over 1993-2026.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/concepts-strategies/zebra
- statistic: mean of (ZEBRA P&L - delta_0 x SPY P&L)/S with block bootstrap CI
- null: mean difference >= 0
- procedure: monthly cycles; solve the 0.70-delta strike at VIX IV; payoff from the SPY close; the cash difference earns DTB3
- data: SPY, VIX, DTB3 · min n: 300
- pass: upper CI < 0
- controls: The net extrinsic paid (about 0.25% of S per month under flat pricing) is the cost tested against the convexity gained. Flat IV misprices the ITM call wing; rerun on chain mids at 60 days.
- note: from the options-library library: ZEBRA (zero extrinsic back ratio); harness suggestion: Add a 'zero-extrinsic solver' to strategies.py (choose K1 so 2*extrinsic(K1) = extrinsic(K2)) and run through the roll-schedule simulator; compare to leaps-stock-replacement in the same report. | verifier: corrected claim/trial

### T-155 · roll-out-up-down

**Claim.** For a 0.16-delta 45-DTE SPY short put that is tested (delta beyond -0.30) at 21 DTE, rolling it out at the same strike to the next monthly does not produce a higher mean P&L per day than closing it and opening a fresh 0.16-delta 45-DTE put, model-priced (VIX as IV).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/news-insights/how-to-roll-options-position, https://www.optionsplaybook.com/blogs/poor-mans-covered-call-how-to-run-a-covered-call-strategy-for-less-capital
- statistic: Mean P&L per day held, roll path minus close-and-reset path, paired by entry
- null: Roll path P&L/day > reset path. The claim is falsified if the paired-bootstrap 95% CI of the difference lies entirely above 0.
- procedure: Daily entries since 1993-01-29 (SPY inception; VIX exists from 1990, but SPY prices do not). Black-Scholes pricing from VIX. At 21 DTE apply the 'tested' trigger; simulate both paths to the next cycle's 21-DTE exit. Paired block bootstrap; walk-forward halves.
- data: SPY closes, VIX, FRED 3-month bill · min n: 200
- pass: The claim survives if the CI of (roll - reset) includes 0 or lies below it in both halves; the variance ratio is reported
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV and has no skew, so this trial is model-priced, not market-priced; rerun with a SKEW tilt. Both paths pay the same number of fills. Margin-time cost charged at the bill rate.
- note: from the options-library library: Rolling a short option (out / up / down); harness suggestion: Roll-schedule simulator with conditional actions (on delta/DTE triggers); expose roll vs reset as two action lists over the same price path. | verifier: corrected claim/trial

### T-156 · theta-harvest-45dte

**Claim.** For model-priced 45-DTE 1SD SPY short strangles, exiting at 21 DTE yields a higher mean P&L per day in the trade than holding to expiration.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/concepts-strategies/managing-winners, https://www.tastylive.com/news-insights/How-Capital-Allocation-Impacts-Volatility
- statistic: Mean P&L per day in the trade, 21-DTE exit minus hold-to-expiry, paired by entry; the 50% rule and the standard deviations are reported alongside
- null: No difference between exit rules (exit labels permuted within entry)
- procedure: Daily entries since 1993-01-29 (SPY inception), with VIX as IV for the Black-Scholes premium and daily mark-to-model to trigger exits. Non-overlapping monthly entries for the CIs; paired bootstrap; walk-forward halves; deflate for the three rules.
- data: SPY daily closes, VIX daily history, FRED 3-month bill · min n: 300
- pass: (21-DTE - hold) P&L/day > 0 with the CI excluding 0 in both halves after deflation
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV (it overstates 0.16-delta call premium and understates put skew), so this trial is model-priced, not market-priced; SKEW-tilt sensitivity. Commissions $0.65/contract; margin-time cost. Compare with the existing harness_short_straddle outputs.
- note: from the options-library library: Time-decay harvesting (45 DTE short premium, managed at 50% or 21 DTE); harness suggestion: Extend overlay_backtest with exit rules (profit_target, dte_exit) and report P&L/day; the BTC version runs on DVOL/realised-vol from Deribit with the same code path. | verifier: corrected claim/trial

### T-157 · theta-ladder

**Claim.** A 4-rung weekly ladder of quarter-size 0.16-delta SPY short puts, each managed at 50% or 21 DTE, has a maximum drawdown at least 15% smaller than a single full-size 45-DTE monthly entry managed the same way, model-priced (VIX as IV).

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/news-insights/How-Capital-Allocation-Impacts-Volatility, https://www.tastylive.com/concepts-strategies/managing-winners
- statistic: Ratio of max drawdowns (ladder / single entry); mean monthly P&L per unit of margin and the standard deviation are reported alongside
- null: Drawdown ratio >= 0.85 (compared across block-bootstrap resampled paths)
- procedure: Daily simulation since 1993-01-29 (SPY inception) with VIX-as-IV pricing. The single-entry book enters monthly at 45 DTE; the ladder enters weekly at a quarter size; identical exit rules. Studentized block bootstrap; walk-forward halves.
- data: SPY closes, VIX, FRED 3-month bill · min n: 300
- pass: Drawdown ratio < 0.85 with the bootstrap CI upper bound < 1 in both halves
- controls: VIX is a 30-day variance-swap index that sits above 30-day ATM IV, so this trial is model-priced, not market-priced. Four times the fills are charged. Strikes are set on different days, so the average moneyness differs; report delta-matched results. Same total margin.
- note: from the options-library library: Theta ladder (staggered-expiry short premium); harness suggestion: Roll-schedule simulator run with an entry cadence parameter (weekly vs monthly) and a size parameter; drawdown via overlay_backtest's dd helper. | verifier: corrected claim/trial

### T-159 · vix-term-structure-regime-filter

**Claim.** Within each VIX-level tercile, the 21-day SPY variance risk premium (VIX^2 minus the subsequent 21-trading-day realised variance) is higher on days when VIX/VIX3M < 0.95 than on days when VIX/VIX3M > 1.05.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3, https://www.macroption.com/vix3m/
- statistic: Contango-minus-backwardation difference in mean VRP (variance units, and vol points), within each VIX tercile; model-priced strangle P&L reported as a secondary
- null: No regime difference, with the regime label circularly block-shifted against the VRP series (as in term_structure_reversion)
- procedure: Daily since 2007-12-04. Compute the ratio and the forward 21-day VRP; stratify by VIX tercile. Studentized block bootstrap (block 21); walk-forward halves; deflate for the thresholds 0.90/0.95/1.00/1.05.
- data: CBOE VIX and VIX3M history, SPY closes (data-only for the VRP; FRED 3-month bill for the strangle secondary) · min n: 60
- pass: Difference > 0 with p < 0.05 after deflation, in both halves and in at least 2 of 3 VIX terciles (the high tercile holds most backwardation days)
- controls: VIX level (terciles). Regime autocorrelation (block null). Report with and without 2008 and 2020. The strangle secondary is model-priced (VIX overstates ATM IV; flat smile).
- note: from the options-library library: VIX term-structure regime filter (VIX3M/VIX gate for premium selling); harness suggestion: term_structure_conditional_pnl(vix_rows, vix3m_rows, price_rows, strategy) in experiments/volatility.py reusing overlay_backtest for the strangle path and variance_risk_premium for the VRP; register alongside vix-term-structure-reversion. | verifier: corrected claim/trial

### T-161 · covered-call-atm-buywrite

**Claim.** Over 2002-03 to 2026-10, monthly excess returns of the Cboe BXM index over the 3-month T-bill have a positive Jensen alpha against SPY total-return excess returns (beta ~0.63), i.e. ATM overwriting adds return beyond its reduced equity exposure.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_BuyWrite_Indices_Methodology.pdf
- statistic: Intercept (annualised alpha) of an OLS regression of BXM monthly excess return on SPY total-return monthly excess return
- null: alpha <= 0 (overwriting is just de-risking; no variance premium captured)
- procedure: Pull BXM_History.csv (Cboe CDN; it redirects to cdn-api.cboe.com and starts 2002-03-22). Build SPY total return from the Yahoo chart endpoint with events=div / adjclose (the archived daily-history-SPY rows hold only the unadjusted close). Take FRED DTB3, sample month-ends, run OLS with HAC standard errors, stationary block bootstrap (12-month blocks) of alpha, and split into walk-forward halves.
- data: BXM 2002-03-22 onward (6,177 daily rows); SPY closes plus dividends 1993 onward; FRED DTB3 · min n: 280
- pass: Bootstrap 95% CI of annualised alpha > 0 in the full sample, with a positive point estimate in both halves
- controls: Israelov & Nielsen decomposition: compare with a beta-matched SPY-TR/T-bill blend; price-only SPX as a sensitivity (it biases against SPX by ~2%/yr of dividends)
- note: from the options-library library: Covered call / buy-write (ATM, BXM-style); harness suggestion: Add BXM, BXMD, BXY, BXMW, BXMH, BXMC, BXN, BXR to CBOE_INDICES in mandel/data/options.py (same CSV format, single column). Sanity numbers computed today: BXM 2002-2026 CAGR 6.23% vol 10.6% maxDD -40% beta 0.63 vs SPX price-only CAGR 8.11% vol 14.8%. | verifier: corrected claim/trial

### T-162 · covered-call-delta-targeted

**Claim.** On the common sample 2002-03 to 2026-10, the Cboe BXMD (30-delta) buy-write has a higher monthly Sharpe ratio (excess over 3m T-bill) than the ATM BXM buy-write.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/BXMD_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/BXMD_History.csv
- statistic: Sharpe(BXMD) - Sharpe(BXM) on month-end excess returns
- null: Sharpe(BXMD) - Sharpe(BXM) <= 0
- procedure: Download BXMD_History.csv, BXM_History.csv and BXY_History.csv; align on 2002-03-22 onward; take month-end excess returns over DTB3; studentized block bootstrap (12-month blocks) of the Sharpe difference (or Ledoit-Wolf test); repeat on walk-forward halves; regress the BXMD-BXM spread on the SPX monthly return to show the convexity difference.
- data: Cboe CDN daily histories (BXMD 1986-06 onward, BXY 1988-06 onward, BXM 2002-03 onward), FRED DTB3 · min n: 280
- pass: Bootstrap 95% CI of the Sharpe difference > 0 in the full sample, with the same sign in both halves
- controls: Beta-matched SPY-TR/T-bill blend; BXMC is NOT an ATM series (it is the conditional buy-write: full unit if VIX >= 20, else half), so use it only as a separately labelled third arm
- note: from the options-library library: OTM / delta-targeted covered call (30-delta, BXMD; 2% OTM, BXY); harness suggestion: Today's figures: BXMD 1986- CAGR 10.67% vol 12.8%, BXY 10.40%/11.9%, BXMC (ATM, 1990-) 9.73%/11.0%, SPX price 8.9%/15.2%. Use SPY adjusted closes for a TR benchmark. | verifier: corrected claim/trial

### T-163 · covered-call-weekly-ladder

**Claim.** Over 2012-06 to 2026-10, the Cboe BXMW multi-week buy-write has a higher monthly Sharpe ratio (excess over 3m T-bill) than the monthly BXM buy-write.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/BXMW_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/BXMW_History.csv
- statistic: Sharpe(BXMW) - Sharpe(BXM) on month-end excess returns from 2012-06-29
- null: Difference <= 0
- procedure: Cboe CDN BXMW_History.csv vs BXM_History.csv; month-end excess returns over DTB3; studentized block bootstrap of the Sharpe difference; split pre/post 2020
- data: BXMW 2012-06-29 onward (3,589 rows), BXM, FRED DTB3 · min n: 160
- pass: 95% CI of the Sharpe difference excludes 0 from below, with the same sign in both halves
- controls: Beta-matched SPY-TR blend; cost sensitivity: subtract 4x roll costs at 0.05% of notional per roll
- note: from the options-library library: Multi-week / laddered covered call (BXMW, weekly overwriting); harness suggestion: Computed today: BXMW 2012- CAGR 7.72% vol 8.25% maxDD -30.6%; BXM same era needs re-alignment to 2012 start. | verifier: corrected claim/trial

### T-164 · partial-overwrite-etf-mechanics

**Claim.** Over 2002-03 to 2026-10, the Cboe BXMH half buy-write has a higher monthly Sharpe ratio (excess over 3m T-bill) than the full ATM BXM buy-write.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_Half_Buywrite_Indices_Methodology.pdf, https://www.globalxetfs.com/funds/qyld/
- statistic: Sharpe(BXMH) - Sharpe(BXM) on month-end excess returns; secondary: Sharpe of synthetic blends w*BXM + (1-w)*SPY TR for w in {0.25, 0.5, 0.75, 1}
- null: Sharpe(BXMH) <= Sharpe(BXM)
- procedure: Cboe CDN BXMH_History.csv (1990-) and BXM_History.csv (2002-); align on 2002-03-22 onward; take excess returns over DTB3; studentized block bootstrap of the Sharpe difference; walk-forward halves
- data: Cboe CDN BXMH, BXM, BXMC; SPY closes plus dividends via the Yahoo chart endpoint; FRED DTB3 · min n: 280
- pass: Bootstrap 95% CI of the Sharpe difference > 0, with the same sign in both halves
- controls: Beta-matched comparison; 0.35-0.60% fee drag applied when interpreting ETF replication; BXMC as the VIX-conditional w arm
- note: from the options-library library: Partial overwrite / overwriting-ETF mechanics (JEPI, QYLD, XYLD, BXMH); harness suggestion: Today's figures: BXMH 1990- CAGR 10.07% vol 12.1% vs BXMC 9.73% vol 11.0%. Add BXMH/BXMC to the Cboe index list. | verifier: corrected claim/trial

### T-166 · collar

**Claim.** Over 2008-08 to 2026-10, the Cboe CLL 95-110 collar index has a lower CAGR than a beta-matched (OLS beta ~0.63) SPY-total-return/T-bill blend.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/collar-protective-collar, https://cdn.cboe.com/api/global/us_indices/governance/CLL_Methodology.pdf
- statistic: CAGR(CLL) - CAGR(blend), where blend = beta*SPY TR + (1-beta)*T-bill, rebalanced monthly
- null: CAGR(CLL) >= CAGR(blend)
- procedure: Cboe CDN CLL_History.csv (2008-08-26 onward; the methodology base date is 1986 but the free CSV starts 2008; it has gaps up to 11 days, so use month-ends); SPY TR from the Yahoo chart adjclose; DTB3; estimate beta on the first half and apply it out of sample to the second; block bootstrap
- data: CLL 4,520 rows, SPY closes plus dividends, FRED DTB3 · min n: 200
- pass: Bootstrap 95% CI of the CAGR difference entirely below 0
- controls: CLL1M and CLL3M (2004-) as alternative collars; PPUT (put only) to isolate the call leg; CLLZ (1986-) as the long-history collar
- note: from the options-library library: Collar (protective collar, Cboe CLL 95-110); harness suggestion: Today: CLL 2008- CAGR 6.96% vol 12.3% maxDD -26.3% beta 0.51 vs SPX price CAGR 10.5% maxDD ~-34% (2020) / -57% (2009 not in sample start). | verifier: corrected claim/trial

### T-168 · put-spread-collar

**Claim.** Over 1993-02 to 2026-10, the Cboe CLLZ zero-cost put-spread collar index has no higher monthly Sharpe ratio (excess over 3m T-bill) than SPY total return.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/daily_prices/CLLZ_History.csv, https://www.cboe.com/us/indices/indicesproducts/
- statistic: Sharpe(CLLZ) - Sharpe(SPY TR) on month-end excess returns
- null: Sharpe(CLLZ) > Sharpe(SPY TR) (the put-spread collar improves risk-adjusted return)
- procedure: Cboe CDN CLLZ_History.csv (1986-06 onward); SPY TR from Yahoo chart adjclose (1993 onward); DTB3; studentized block bootstrap of the Sharpe difference; walk-forward halves; also report the mean return difference in months with SPX < -5% to show the bounded protection
- data: CLLZ 10,151 rows; SPY closes plus dividends; FRED DTB3 · min n: 380
- pass: Bootstrap 95% CI upper bound of the Sharpe difference <= 0.05 and point estimate <= 0 (rejecting the null requires the CI to lie below a small positive margin)
- controls: CLL and PPUT as full-floor comparators; price-only SPX as a sensitivity
- note: from the options-library library: Put-spread collar (Cboe CLLZ zero-cost put-spread collar); harness suggestion: Today: CLLZ 1986- CAGR 8.14% vol 11.6% maxDD -47.2% worst month -17.1% vs SPX price CAGR 8.94% vol 15.2%; the -47% drawdown is the fingerprint of the short tail. | verifier: corrected claim/trial

### T-169 · protective-put

**Claim.** Over 1993-02 to 2026-10, the Cboe PPUT index has a CAGR more than 1%/yr below a beta-matched (OLS beta ~0.73) SPY-total-return/T-bill blend.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/protective-put-married-put, https://cdn.cboe.com/api/global/us_indices/governance/PPUT_Methodology.pdf
- statistic: CAGR(PPUT) - CAGR(blend), blend = beta*SPY TR + (1-beta)*T-bill rebalanced monthly
- null: CAGR(PPUT) - CAGR(blend) >= -1%/yr
- procedure: Cboe CDN PPUT_History.csv (1986-06 onward), SPY TR (Yahoo chart adjclose, 1993-), DTB3; estimate beta out of sample (first half), apply to the second; monthly block bootstrap; VRP cross-check: VIX vs forward 21-day SPX realised vol since 1990
- data: PPUT 10,145 rows, SPY closes plus dividends, DTB3, VIX 1990- · min n: 380
- pass: Bootstrap 95% CI of the CAGR difference entirely below -1%/yr
- controls: Exclude 2008 and 2020 one at a time; PPUT3M (2004-) as the tail variant
- note: from the options-library library: Protective put / married put (Cboe PPUT 5% OTM); harness suggestion: Today: PPUT 1986- CAGR 8.02% vol 12.3% maxDD -42% worst month -10.6% (vs SPX -19.6% ex 1987 crash months): protection shows up in the worst month but costs ~1%/yr vs SPX price-only CAGR 8.91%. | verifier: corrected claim/trial

### T-170 · cash-secured-put

**Claim.** Over 2007-01 to 2026-10, the Cboe PUT (ATM put-write) index has a higher monthly Sharpe ratio (excess over 3m T-bill) than the BXM (ATM buy-write) index.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/cash-secured-put, https://www.optionseducation.org/strategies/all-strategies/naked-put-uncovered-put-short-put
- statistic: Sharpe(PUT) - Sharpe(BXM) on month-end excess returns, 2007-01 onward
- null: Sharpe(PUT) <= Sharpe(BXM) (parity: no difference)
- procedure: Cboe CDN PUT_History.csv. It has only 1-2 rows per year before 2007-01-03, with gaps up to 1,159 days, so start in 2007. Align with BXM_History.csv; excess returns over DTB3; studentized block bootstrap; walk-forward halves
- data: PUT (daily from 2007-01-03), BXM, FRED DTB3; PUTY 1986- and WPUT/PUTD 2006- as secondary arms · min n: 220
- pass: Bootstrap 95% CI of the Sharpe difference > 0 in the full sample, with the same sign in both halves
- controls: PUTY vs BXY (both 2% OTM, 1988-) as a longer parity check
- note: from the options-library library: Cash-secured put / put-write (Cboe PUT, WPUT, PUTD); harness suggestion: Note: PUT_History.csv appears sparse in early years (4,984 rows for 35 years) - validate day counts before monthly sampling; computed WPUT 2006- CAGR 4.84% vol 9.6% maxDD -28.6%, PUTD 9.67%/12.0%. | verifier: corrected claim/trial

### T-171 · the-wheel

**Claim.** In a model-priced simulation (Black-Scholes with VIX as the implied vol, not market prices) on SPX from 1990 to 2026, a wheel whose call strike is constrained to be >= the cost basis has a lower Sharpe ratio than the same wheel writing an unconstrained 30-delta call.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/cash-secured-put, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write
- statistic: Sharpe(basis-constrained wheel) - Sharpe(unconstrained 30-delta wheel), model-priced
- null: Difference >= 0 (the basis rule helps or is neutral)
- procedure: Model-priced backtest on SPX daily since 1990 (IV = VIX, with an OTM adjustment from SKEW as a sensitivity), 30-45 DTE cycles, 10 bps slippage. Gate: the same pricer must first reproduce BXM (2002-) and PUT (2007-) monthly returns with tracking error < 2%/yr, or results do not count. Block bootstrap of the paired Sharpe difference.
- data: SPX daily 1975-, VIX 1990-, SKEW 1990-, BXM/PUT histories for calibration, FRED DTB3 · min n: 400
- pass: Calibration gate passed AND the 95% CI of the Sharpe difference < 0
- controls: Constant-IV pricer to show sensitivity; ATM-both-phases wheel vs the actual PUT index as an external check
- note: from the options-library library: The wheel (cash-secured put -> assignment -> covered call -> called away); harness suggestion: Reuse the model-priced overlay harness; calibrate it to BXM/PUT first (now downloadable) and report the calibration error as a gate. | verifier: corrected claim/trial

### T-172 · covered-strangle

**Claim.** Over 1988-06 to 2026-10, the Cboe CMBO covered combo index has a higher monthly Sharpe ratio (excess over 3m T-bill) than the BXY 2% OTM buy-write, i.e. adding the ATM short put on T-bill collateral improves risk-adjusted return.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/covered-strangle-covered-combination, https://cdn.cboe.com/api/global/us_indices/governance/CMBO_Methodology.pdf
- statistic: Sharpe(CMBO) - Sharpe(BXY) on month-end excess returns
- null: Sharpe(CMBO) <= Sharpe(BXY)
- procedure: Cboe CDN CMBO_History.csv (1986-06) and BXY_History.csv (1988-06); align; excess over DTB3; studentized block bootstrap; walk-forward halves; report worst-5% months as a secondary description
- data: Cboe CDN histories, FRED DTB3 · min n: 400
- pass: Bootstrap 95% CI of the Sharpe difference > 0, with the same sign in both halves
- controls: Beta-matched SPY-TR blend (CMBO beta ~0.66); PUTY 2% OTM put-write as the put-only arm
- note: from the options-library library: Covered strangle / covered combination (Cboe CMBO); harness suggestion: Today: CMBO 1986- CAGR 9.37% vol 11.0% maxDD -42.7% worst month -17.3% beta 0.66. | verifier: corrected claim/trial

### T-174 · covered-put

**Claim.** In a model-priced simulation (Black-Scholes at VIX, not market prices) of short SPX + short monthly ATM SPX puts with T-bill interest on proceeds, the CAGR is negative in at least 90% of rolling 120-month windows from 1990 to 2026.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/all-strategies-en, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Fraction of rolling 120-month windows with negative CAGR (model-priced)
- null: Fraction < 0.9
- procedure: Model-priced with VIX-as-IV on SPX daily, monthly rolls, T-bill interest on short proceeds, dividends owed on the short; pricer must first pass the BXM/PUT calibration gate
- data: SPX price 1975-, SPY dividends (Yahoo chart events=div), VIX 1990-, FRED DTB3 · min n: 300
- pass: Fraction of negative windows >= 0.9
- controls: Short SPX alone to isolate the put income
- note: from the options-library library: Covered put (short stock + short put); harness suggestion: Low priority: include for completeness of the payoff library; the claim is mostly a sanity check of the engine's sign conventions. | verifier: corrected claim/trial

### T-178 · iron-butterfly-bfly

**Claim.** Over 1986-06 to 2026-10, the Cboe BFLY iron butterfly index has a lower monthly Sharpe ratio (excess over T-bill) than the Cboe CNDR iron condor index.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/BFLY_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/BFLY_History.csv
- statistic: Sharpe(BFLY) - Sharpe(CNDR) on month-end excess returns
- null: Sharpe(BFLY) >= Sharpe(CNDR)
- procedure: Cboe CDN BFLY_History.csv and CNDR_History.csv (both 1986-06-20 onward), FRED DTB3; studentized block bootstrap; split pre/post 2008
- data: Cboe CDN (10,151 rows each), FRED DTB3 · min n: 400
- pass: Bootstrap 95% CI of the Sharpe difference < 0, with the same sign in both halves
- controls: Relate monthly P&L to VIX minus subsequent realised vol
- note: from the options-library library: Iron butterfly benchmark overlay (Cboe BFLY: short ATM straddle, long 5% wings, over T-bills); harness suggestion: Today: BFLY 1986- CAGR 3.66% vol 10.8% maxDD -54.9% beta 0.08; CNDR 5.38% vol 7.0% maxDD -19.8% beta 0.13. | verifier: corrected claim/trial

### T-179 · iron-condor-cndr

**Claim.** From 1990 to 2026, CNDR's monthly excess return over the 1-month T-bill rises with the roll-day gap between VIX and trailing 21-day SPX realised volatility (positive regression slope).

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/CNDR_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/CNDR_History.csv
- statistic: OLS slope of monthly CNDR excess return (roll to roll) on (VIX at roll - trailing 21-day SPX realised vol)
- null: Slope <= 0
- procedure: Cboe CDN CNDR_History.csv sampled at 3rd-Friday roll dates; VIX history; SPX realised vol from Cboe SPX daily; FRED DTB3; HAC standard errors; block bootstrap; walk-forward halves
- data: CNDR 1986- (use 1990- for VIX), SPX daily, VIX, DTB3 · min n: 400
- pass: Bootstrap 95% CI of the slope > 0, with the same sign in both halves
- controls: Beta to SPX near zero (0.13 today); add SPX month return as a regressor to separate the variance premium from direction
- note: from the options-library library: Iron condor benchmark overlay (Cboe CNDR: short 20-delta strangle, long 5-delta wings, over T-bills); harness suggestion: CNDR is the cleanest free realised series for the SPX variance premium harness; add it as a validation target for the model-priced condor. | verifier: corrected claim/trial

### T-180 · cboe-benchmark-replication

**Claim.** A Black-Scholes overlay simulation on SPX (model-priced, with VIX as the implied vol and FRED DTB3 as the rate) reproduces the monthly returns of BXM (2002-2026) and PUT (2007-2026) with R^2 > 0.95 and annualised tracking error below 2%.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_BuyWrite_Indices_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/BXMD_History.csv
- statistic: R^2 and annualised tracking error between simulated and actual monthly returns for BXM and PUT (secondary: BXMD, CNDR)
- null: R^2 <= 0.95 or TE >= 2%/yr for either BXM or PUT
- procedure: Simulate each index's strike/roll rule on SPX daily with VIX (SKEW-based OTM adjustment for BXMD/CNDR as a documented sensitivity), compare with downloaded histories, and report by sub-period. Use SPX price plus SPY dividends (Yahoo chart events=div) for the total-return leg.
- data: SPX daily, VIX, SKEW, DTB3, SPY dividends, Cboe benchmark CSVs · min n: 220
- pass: R^2 > 0.95 and TE < 2%/yr for both BXM and PUT; document the shortfall for BXMD/CNDR (skew)
- controls: Price-only vs total-return SPX; VWAP vs close fill assumption
- note: from the options-library library: Buy-write benchmark family map (BXM/BXMD/BXY/BXMW/BXMH/BXN/BXR/PUT/CLL/CLLZ/CMBO/PPUT/BFLY/CNDR) as replication targets; harness suggestion: This is the first thing to run: extend cboe_index_history to the list above (the CDN 307-redirects to cdn-api.cboe.com; httpx follow_redirects is already on), then calibrate the model-priced overlay harness against it. | verifier: corrected claim/trial

### T-182 · conversion

**Claim.** For SPY expiries before the next ex-dividend date (2026-12-18) with 30-64 DTE and strikes within +/- 5% of spot, the executable conversion lending rate (stock at ask, put at ask, call at bid, D = 0) is below the FRED 3-month bill rate in at least 95% of (K, T) pairs.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Share of (K, T) pairs with r_conv_exec = ln(K / (S_ask + P_ask - C_bid)) / T below r_bill (both continuously compounded).
- null: Share < 95% (executable conversions beat bills in a material fraction of pairs).
- procedure: Day one: SPY chain plus underlying quote; restrict to expiries strictly before 2026-12-18 so no dividend enters; compute r_conv_exec per pair; compare to DGS3MO converted to continuous compounding; repeat daily until the ex-date window closes, then roll to the next quarter.
- data: CBOE delayed SPY chain with underlying bid/ask; FRED DGS3MO. · min n: 100
- pass: >= 95% of pairs below r_bill on day one and on >= 80% of captured days.
- controls: Mid-price version should sit near the SPX box rate (bill + ~0-60 bp); drop zero-bid legs; drop pairs where the short call is deep ITM (early-exercise contamination).
- note: from the options-library library: Conversion; harness suggestion: Reuse parity.py implied rate per name; add payoff template [underlying+, put+, call-] and assert flat payoff in payoff engine test. | verifier: corrected claim/trial

### T-184 · synthetic-long-stock

**Claim.** For SPY expiries with 180-365 DTE, the executable financing rate of an ATM synthetic long (call at ask, put at bid, dividends from SPY's trailing four distributions) is below the 3-month bill + 50 bp in at least 80% of expiries, i.e. at least 100 bp cheaper than a benchmark retail margin rate of bill + 150 bp.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.optionseducation.org/strategies/all-strategies-en, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity
- statistic: r_impl_exec - r_bill per expiry, r_impl_exec solving C_ask - P_bid = S - PV(D) - K e^{-r T}.
- null: r_impl_exec - r_bill >= 50 bp in more than 20% of expiries.
- procedure: Day one on SPY (QQQ/IWM/GLD/IBIT as replications): ATM strike per expiry with 180-365 DTE; PV(D) from trailing distributions on the known quarterly ex-dates; compute r_impl_exec and r_impl_mid; compare to DGS3MO; repeat daily.
- data: CBOE delayed SPY chain, FRED DGS3MO, SPY trailing four quarterly distributions (4 public numbers entered by hand; not in the listed feeds). GLD/IBIT replications need no dividends. · min n: 20
- pass: >= 80% of expiries with r_impl_exec - r_bill < 50 bp on day one and on >= 80% of captured days.
- controls: Sensitivity to +/-10% dividend forecast; mid-based rate; exclude expiries with a zero-bid leg; GLD/IBIT dividend-free replication.
- note: from the options-library library: Synthetic long stock (combo); harness suggestion: Template [call+, put-]; payoff engine must reproduce a straight line; parity.py reports r_impl_askbid alongside r_impl_mid. | verifier: corrected claim/trial

### T-185 · synthetic-short-stock

**Claim.** For SPY expiries before 2026-12-18 with 30-64 DTE (no dividend inside T), the executable implicit borrow cost of an ATM synthetic short, r_bill - r_impl with r_impl solving C_bid - P_ask = S - K e^{-r T}, is below 50 bp/yr in at least 80% of (K, T) pairs within +/- 2% of spot.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.optionseducation.org/strategies/all-strategies-en, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity
- statistic: Share of near-ATM pairs with r_bill - r_impl_exec < 50 bp.
- null: Share < 80% (synthetic shorts in SPY cost more than 50 bp/yr over general collateral).
- procedure: Day one: SPY chain, expiries strictly before the ex-date, strikes within +/- 2%; compute r_impl_exec from put ask / call bid; compare to DGS3MO; repeat daily; replicate on GLD and IBIT with no dividend (their expense ratios reduce the forward via the underlying market and are reported separately).
- data: CBOE delayed SPY/GLD/IBIT chains, FRED DGS3MO. · min n: 20
- pass: Share >= 80% on day one and on >= 80% of captured days.
- controls: Mid-price version; stale-quote filter; exclude zero-bid legs; compare with the SPX box rate to separate the bill-vs-option-financing basis from borrow.
- note: from the options-library library: Synthetic short stock (combo); harness suggestion: Template [put+, call-]; parity.py implicit_borrow column. | verifier: corrected claim/trial

### T-191 · early-exercise-itm-put-interest

**Claim.** Among SPY puts with K/S >= 1.10, the share whose mid is within one tick plus half the bid-ask of intrinsic value (K - S) is at least 30 percentage points higher for strikes meeting K (1 - e^{-rT}) > C_mid + PV(D) than for strikes failing it.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Difference in at-intrinsic share between criterion-met and criterion-failed groups.
- null: Difference <= 30 pp (quotes do not reflect the early-exercise rule).
- procedure: Day one: SPY chain; for each deep ITM put compute the criterion using the same-strike call mid, DGS3MO and SPY dividends inside T; classify at-intrinsic quotes; bootstrap the difference across strikes; replicate on QQQ/IWM and daily.
- data: CBOE delayed SPY chain, FRED DGS3MO, SPY distributions (few public numbers, manual; not in the listed feeds). · min n: 100
- pass: Difference > 30 pp with the 95% CI excluding 30 pp on day one; stable over 20 captured days.
- controls: SPX (European) deep ITM puts should trade at or below discounted intrinsic, never pinned at undiscounted intrinsic; exclude zero-bid quotes.
- note: from the options-library library: Early exercise of deep ITM American puts for interest; harness suggestion: early_exercise.py put_exercise_criterion; scan function over chains; SPX control built in. | verifier: corrected claim/trial

### T-194 · etf-vs-index-option-parity-spy-spx-xsp

**Claim.** For SPY expiries before its 2026-12-18 ex-date with 30-64 DTE, the SPY parity-implied financing rate ln(F_spy_impl / SPY) / T + 0.0945% (no distribution inside T, so dividends drop out) lies within 25 bp/yr of the SPX box rate at the nearest SPXW expiry in at least 90% of expiries.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: |r_spy_impl - r_box_spx| per matched expiry, in bp/yr.
- null: Share within 25 bp < 90% (the two venues price financing differently).
- procedure: Day one: SPY F_impl from ATM +/- 3 mids (American bias small near ATM); SPX box rate from wide strike pairs at the matched SPXW expiry; compare; repeat daily.
- data: CBOE delayed SPY (13,470 contracts) and SPX (29,918) chains. No dividend or bill input needed. · min n: 10
- pass: >= 90% of matched expiries within 25 bp on day one and on >= 80% of 20 captured days.
- controls: XSP box as a second reference; strike-invariance of each forward; exclude AM-settled SPX monthlies.
- note: from the options-library library: ETF vs index option parity (SPY vs SPX vs XSP); harness suggestion: parity.py cross_venue(spy_chain, spx_chain, xsp_chain) returning residual table; payoff template with qty 10:1. | verifier: corrected claim/trial

### T-195 · crypto-put-call-parity-deribit

**Claim.** For Deribit BTC options at expiries with a listed dated future, strikes within 10% of F and DTE 7-180, fewer than 1% of hourly (K, T) observations have |F_impl - F_mark| / F_mark (F_impl = K/(1 - (C_mid - P_mid))) larger than the round-trip taker fees of the three legs.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://docs.deribit.com/api-reference/market-data/public-ticker, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Exceedance rate of |F_impl - F_mark| / F_mark over the fee threshold; also the 99th percentile in bp.
- null: Exceedance rate >= 1% (exploitable violations are common).
- procedure: Poll get_book_summary_by_currency (kind=option and future) and ticker hourly for 7 days; keep expiries whose underlying_index is a listed future (not SYN.); compute F_impl from mids and from executable bid/ask; bootstrap the exceedance rate.
- data: Deribit public API (live, verified reachable 2026-10-14). · min n: 500
- pass: Exceedance rate < 1% with the 95% upper bound < 1% and no violation persisting > 1 hour.
- controls: Executable vs mid; drop zero-bid quotes; isolate the 07:00-08:30 UTC settlement window; ETH replication.
- note: from the options-library library: Crypto put-call parity vs dated future (Deribit inverse options); harness suggestion: mandel/options/deribit_parity.py polling public endpoints (get_instruments, ticker, get_book_summary_by_currency); payoff engine with inverse payoff mode (divide USD payoff by S_T). | verifier: corrected claim/trial

### T-196 · deribit-inverse-box-spread

**Claim.** For the two most liquid Deribit BTC quarterly expiries, the executable long-box USD lending rate after taker fees (strike pairs within +/- 20% of F) exceeds the FRED 3-month bill by at least 100 bp annualised in the median hourly snapshot.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://docs.deribit.com/api-reference/market-data/public-ticker, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Median over snapshots of r_box_exec - r_bill (bp).
- null: Median <= 100 bp.
- procedure: Hourly polls for 14 days; build boxes from executable bid/ask; subtract fees; join DGS3MO; bootstrap (block = 1 day).
- data: Deribit public API, FRED DGS3MO. · min n: 200
- pass: Median > 100 bp with the 95% CI excluding 100 bp.
- controls: Mid vs executable; strike-pair invariance; exclude the settlement hour; ETH replication; report r_box_exec - basis separately.
- note: from the options-library library: Deribit inverse box spread (USD lending/borrowing in BTC collateral); harness suggestion: deribit_parity.py box_rate(); inverse payoff mode in payoff engine; join with FRED via existing ingest. | verifier: corrected claim/trial

### T-197 · cash-and-carry-options

**Claim.** Across the daily history of expired and live Deribit BTC quarterly futures, the median annualised basis of the second-nearest quarterly over the index exceeds the same-day FRED 3-month bill by at least 100 bp.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://docs.deribit.com/api-reference/market-data/public-ticker
- statistic: Median over days of [ln(F_q2 / S) x 365/DTE - r_bill]; block-bootstrap CI.
- null: Median <= 100 bp.
- procedure: Pull daily closes for every quarterly via get_tradingview_chart_data (works for expired instruments, e.g. BTC-27DEC24, verified); spot proxy = BTC daily close (or BTC-PERPETUAL close at the same tick); compute annualised basis of the second quarterly; join DGS3MO; studentized block bootstrap (block 20 days); walk-forward by year.
- data: Deribit public API (chart data for expired dated futures), BTC daily closes, FRED DGS3MO. · min n: 500
- pass: Median > 100 bp with the 95% CI excluding 100 bp and the sign holding in a majority of calendar years.
- controls: Timestamp alignment of futures and spot closes; exclude the final 7 days before each expiry; ETH replication; report 2022 separately (basis compression).
- note: from the options-library library: Cash-and-carry with options (spot vs synthetic short / dated future); harness suggestion: mandel/options/deribit_basis.py (futures curve snapshot) feeding both this and the box entry; payoff template [underlying+, put+, call-]. | verifier: corrected claim/trial

### T-199 · gld-options-implied-gold-carry

**Claim.** At 90-365 DTE, the GLD option-implied financing rate from ATM +/- 3 mid prices lies within 50 bp of (FRED 3-month bill - 0.40%) in at least 90% of strike/expiry pairs on the capture day.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Share of pairs with |r_impl - (r_bill - 0.40%)| <= 50 bp.
- null: Share < 90% (a material lease/borrow premium is priced).
- procedure: Day one: GLD and SLV chains; ATM +/- 3 strikes at expiries 90-365 DTE; r_impl from mids; compare with DGS3MO - fee; repeat daily; report SLV separately.
- data: CBOE delayed GLD/SLV chains, FRED DGS3MO. No dividends. · min n: 30
- pass: Share >= 90% on day one and on >= 80% of captured days.
- controls: Executable vs mid; strike-invariance; compare the residual against the SPX box-bill spread (option-market financing basis) to avoid attributing it to lease rates.
- note: from the options-library library: GLD options-implied gold carry (ETF parity for metals); harness suggestion: parity.py with q = expense ratio as continuous 'dividend'; report per-symbol implied carry. | verifier: corrected claim/trial

### T-223 · deribit-expiry-max-pain-pin

**Claim.** An 8-hour ATM BTC short straddle model-priced with DVOL-as-IV (T = 8/(24*365)), sold at 00:00 UTC and settled on the 08:00 UTC price, has a higher mean P&L on Deribit monthly-expiry Fridays than on other Fridays.

- kind: options-strategy · origin: options-library:event-driven, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data
- statistic: Difference in mean MODEL-PRICED P&L (monthly-expiry Fridays minus other Fridays), bootstrap CI; mean |00-08 UTC return| by group (permutation test).
- null: Monthly-expiry mean P&L <= other-Friday mean P&L.
- procedure: BTC-PERPETUAL hourly candles from public/get_tradingview_chart_data (available back to 2019; a proxy for the settlement index), DVOL 1D for pricing (from 2021-04); monthly expiry calendar (last Friday). Max-pain convergence (|S_08 - K_maxpain| vs |S_00 - K_maxpain|) needs OI captures.
- data: Deribit public hourly perp candles, DVOL history, expiry calendar. · min n: 60
- pass: Difference > 0 with 95% CI excluding 0.
- controls: Weekly vs monthly split; exclude expiries coinciding with FOMC/CPI; ETH separately.
- note: from the options-library library: Deribit expiry max-pain pin (sell the 08:00 UTC settlement straddle); harness suggestion: Deribit hourly index fetcher + expiry calendar; max-pain calculator from book summary OI. | verifier: corrected claim/trial

### T-227 · risk_reversal_skew

**Claim.** Since 1991, the frequency of 21-trading-day S&P 500 log returns below -2 VIX-implied sigma is not higher, by 1 percentage point or more, in windows starting with CBOE SKEW above its trailing 252-day 80th percentile than in windows starting with SKEW below its 20th percentile (the extra put premium a high-SKEW risk reversal sells is not paid back by more realised left-tail events).

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Difference (high-SKEW minus low-SKEW) in the frequency of r_{t,t+21} < -2*(VIX_t/100)*sqrt(21/252) on ^GSPC; secondary: difference in realised 21d skewness of daily returns.
- null: freq_high - freq_low >= 0.01 (SKEW carries real information about future left tails).
- procedure: Daily SKEW and VIX since 1990-01; ^GSPC closes (archive daily-history--GSPC, because SPY only starts in 1993-01); trailing 252-day SKEW percentile, so the first usable window is in 1991. Use overlapping daily-start 21d windows with a 21-day-block studentized bootstrap, because non-overlapping windows leave only ~85 per quintile and a handful of tail events. Reject the null if the bootstrap 95% upper bound of the difference is < 0.01. Deflate for the two cut pairs tried (80/20 and 90/10).
- data: CBOE SKEW and VIX daily history and ^GSPC daily closes, all in the archive. Index data only, no option prices. · min n: 300
- pass: 95% upper bound of (freq_high - freq_low) < 0.01, and the realised-skewness difference is not significantly negative (p > 0.1) in both halves 1991-2008 and 2009-2026.
- controls: Shuffled-SKEW placebo; VIX-tercile stratification (SKEW must not proxy for the VIX level); sensitivity run excluding Oct-2008 and Mar-2020; repeat with the 21-day SKEW change instead of its level.
- note: from the options-library library: Risk reversal (25-delta skew trade); harness suggestion: Extend harness_skew_tail: bucket by SKEW percentile, compare CBOE-table implied 2-sigma probability vs realised frequency; log skew-vega P&L once surface_summary 25d put/call IVs have 60+ captures. | verifier: corrected claim/trial

### T-228 · put_skew_ratio_sale

**Claim.** The CBOE SKEW-implied risk-neutral probability of a 30-day S&P 500 log return below -2 sigma, P = 0.0228 + 0.0270*(SKEW-100)/10 (the white paper's Gram-Charlier mapping: 2.3% at SKEW 100, 14.45% at 145), exceeds the realised frequency of 21-trading-day returns below -2*(VIX/100)*sqrt(21/252) by more than 2 percentage points on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Mean over windows of P_SKEW(t) - 1{r_{t,t+21} < -2*(VIX_t/100)*sqrt(21/252)}.
- null: Mean gap <= 0.02.
- procedure: Non-overlapping 21d windows since 1990 (^GSPC closes before SPY's 1993 start); studentized block bootstrap; require the gap to be positive in each of three sub-periods. Report the SKEW > 135 conditional gap only as a secondary, with PBO across thresholds 125/130/135/140.
- data: CBOE SKEW and VIX history and ^GSPC/SPY closes (archive). Index-only: this tests the tail premium the strategy sells, not the 1x2's P&L, which needs 10d/25d IVs from chain capture. · min n: 300
- pass: Lower 95% bound of the mean gap > 0.02, and the gap is positive in at least 2 of 3 sub-periods.
- controls: Constant-normal benchmark (P = 2.28%) to show SKEW adds information; shuffled-SKEW placebo. SKEW readings above 145 (154.7 on 2026-10-13) are outside the white-paper table and use the formula's extrapolation; report them separately.
- note: from the options-library library: Put-skew richness sale (1x2 put ratio spread, delta-hedged); harness suggestion: Add a 'skew_implied_tail' statistic to harness_skew_tail using the CBOE white-paper mapping (100 -> 2.3%, 145 -> 14.45%, interpolate); P&L of the 1x2 needs surface_summary 10d/25d IVs, which accumulate from today. | verifier: corrected claim/trial

### T-229 · skew_cheap_put_spread

**Claim.** Model-priced: a 30-DTE 25d/10d SPX put spread bought only in months when CBOE SKEW is below its trailing 252-day 20th percentile has a higher mean ratio of expiry payoff to entry debit than the same spread bought every month.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean(payoff/debit | SKEW < p20) - mean(payoff/debit | all months). The debit is model-priced with BS: ATM IV = VIX/100 times the ATM-to-VIX ratio measured on the captured SPX chain; strike IVs come from a linear-in-log-moneyness smile with slope kappa*(SKEW-100), kappa calibrated once on the 2026-10-14 SPX surface. Payoff from ^GSPC at expiry.
- null: Difference <= 0.
- procedure: Monthly 30-DTE entries since 1991, held to expiry (21 trading days, non-overlapping); walk-forward trailing percentile; studentized block bootstrap of the difference; deflated Sharpe of the conditional series. Rerun with kappa x0.5 and x2, because the smile model drives the debit.
- data: CBOE SKEW and VIX, ^GSPC/SPY closes (model-priced, not market prices); today's SPX surface for kappa. Switch to captured 25d/10d IVs once surface_summary stores 10d and 36+ monthly captures exist. · min n: 300
- pass: Difference > 0 with the 95% CI excluding zero, at least 60 low-SKEW entries, and the sign unchanged at kappa x0.5 and x2.
- controls: Random-timing placebo with the same entry count; VIX-tercile stratification; a VIX < 15 gate as an alternative rule counted in the deflation.
- note: from the options-library library: SKEW-conditioned tail hedge (put spread when skew is cheap); harness suggestion: Reuse the monthly model-priced cycle of harness_vrp_spx with a SKEW gate; swap in real 10d/25d IVs from surface_summary when available. | verifier: corrected claim/trial

### T-233 · vrp_short_straddle_hedged

**Claim.** Model-priced: a daily delta-hedged short 30-DTE SPY ATM straddle priced at ATM IV = 0.81 x VIX (the ATM-to-VIX ratio used by harness_short_straddle, to be recalibrated on the captured SPY surface) earns a positive mean P&L per monthly cycle after a 0.5 vol-point round-trip cost.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.optionseducation.org/strategies/all-strategies/short-straddle, https://en.wikipedia.org/wiki/Variance_swap
- statistic: Mean cycle P&L / straddle premium for the BS-priced, daily-rehedged short straddle.
- null: Mean <= 0.
- procedure: Monthly non-overlapping cycles from 1993-02 (SPY) with VIX-scaled IV and FRED DTB3 rates; hedge at daily closes; studentized block bootstrap; walk-forward thirds; deflated Sharpe over the IV scales {1.0, 0.9, 0.81} and hedge frequencies tried.
- data: CBOE VIX, SPY closes and FRED DTB3. Model-priced: the captured ATM IV/VIX ratio replaces the 0.81 scale as chain history accrues. · min n: 300
- pass: Mean > 0 with the 95% CI excluding zero at IV scale 0.81 and at the scale measured on the capture; deflated Sharpe p < 0.05; positive in all three thirds.
- controls: Unhedged short straddle; buy-and-hold SPY (harness_controls); shuffled-VIX placebo.
- note: from the options-library library: VRP harvest: delta-hedged short ATM straddle; harness suggestion: harness_vrp_spx and harness_short_straddle already compute this; add the daily-rehedge path and costs; cross-asset twins harness_vrp_nasdaq/russell/gold/oil/bonds/btc/eth. | verifier: corrected claim/trial

### T-234 · variance_strip_replication

**Claim.** VIX^2 exceeds the subsequently realised 21-trading-day S&P 500 variance in more than 75% of non-overlapping months since 1990.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://en.wikipedia.org/wiki/Variance_swap, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Win rate of 1{(VIX_t/100)^2 > RV_{t,t+21}}; secondary: mean ln(RV/VIX^2) and the dollar P&L of a short variance swap with vega notional 1.
- null: Win rate <= 0.75.
- procedure: Monthly non-overlapping cycles since 1990-01, with VIX as the strike and ^GSPC closes for RV (SPY from 1993 as a check; price returns, no dividends); exact binomial CI plus a block bootstrap; walk-forward thirds. Measure the strip-vs-VIX^2 truncation error on the captured SPX chain.
- data: CBOE VIX (archive), ^GSPC/SPY closes. Model-free: VIX is the strip's fair strike. Today's SPX chain (29,918 contracts) for the discretisation check. · min n: 300
- pass: Lower 95% bound of the win rate > 0.75 and positive in all three thirds; truncation error < 5% of the strike on the captured chain (reported, not part of the pass).
- controls: ATM-straddle-only VRP (should be smaller: the smile adds premium); shuffled-returns placebo; dividend-adjusted SPY as a check on the ^GSPC price-return RV.
- note: from the options-library library: Variance swap replication by 1/K^2 strip (log contract); harness suggestion: Wrap harness_vrp_spx's implied-minus-realised statistic in the log form and add a 'strip_from_chain' function in mandel/options that sums 2/(T*K^2)*mid over the current CBOE chain to compare with VIX^2. | verifier: corrected claim/trial

### T-235 · iv_rv_spread_conditional

**Claim.** Scaling a short 21-day S&P 500 variance position struck at VIX^2 by max(z, 0), where z is the entry z-score of VIX minus a walk-forward HAR realised-vol forecast, gives a higher Sharpe ratio than the constant-notional short over the same months.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Sharpe(scaled) - Sharpe(constant) of the monthly P&L N_t*((VIX_t/100)^2 - RV_{t,t+21}).
- null: Sharpe difference <= 0 (the spread carries no timing information).
- procedure: HAR(1,5,22) fitted walk-forward (expanding window, refit monthly); monthly cycles since 1991 using ^GSPC closes; studentized bootstrap of the Sharpe difference; PBO across the declared scaling rules (on/off at z > 0.5, z > 1, linear max(z,0)).
- data: CBOE VIX and ^GSPC/SPY closes. Model-free variance P&L: the straddle implementation is model-priced and reported separately. Twins: DVOL + BTC, GVZ + GLD (archive). · min n: 300
- pass: Sharpe difference > 0 at p < 0.05 and PBO < 0.3.
- controls: VIX-level-only scaling (shows the realised forecast adds information beyond the VIX level); random-z placebo; top-tercile share of P&L reported descriptively.
- note: from the options-library library: Conditional VRP: trade only when implied-minus-realised spread is wide; harness suggestion: Add a 'gate' argument to harness_vrp_spx / harness_vrp_btc accepting a spread z-score and report deflated Sharpe vs the ungated run. | verifier: corrected claim/trial

### T-237 · cross_index_vol_spread

**Claim.** After the 60-day z-score of VXN - VIX passes +/-2, the statistic s*[(VXN - VIX) - (RV_QQQ - RV_SPY)] over the next 21 trading days, with s = +1 for z > +2 and -1 for z < -2, is positive on average: the realised spread falls short of an extreme-wide implied spread and exceeds an extreme-narrow one.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_historical_data/, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean of s*[(VXN_t - VIX_t) - (RV_QQQ - RV_SPY)_{t,t+21}] over event entries; secondary: model-priced vega-neutral straddle-pair P&L.
- null: Mean <= 0 (the implied spread is an unbiased forecast of the realised spread).
- procedure: Daily VXN from 2009-09-14 (the free file starts there, not 2001), VIX, SPY and QQQ closes; event entries with non-overlapping 21d holds; studentized block bootstrap; walk-forward z-window (40/60/120 declared, deflated).
- data: CBOE VIX, VXN and RVX (archive); SPY, QQQ and IWM closes (archive). Index-implied vols, model-free for the statistic. · min n: 30
- pass: Mean > 0 with the 95% CI excluding zero, win rate > 0.6, same sign in both halves.
- controls: Unconditional spread (no signal); random-entry placebo with a matched count; RVX-VIX replication with IWM.
- note: from the options-library library: Cross-index vol spread (QQQ vs SPY, IWM vs SPY straddle pairs); harness suggestion: Pair harness_vrp_nasdaq and harness_vrp_spx outputs: new harness_vol_spread computing the implied-minus-realised spread differential conditioned on the VXN-VIX z-score. | verifier: corrected claim/trial

### T-239 · vix_call_hedge

**Claim.** Model-priced: over 2009-09 to 2026, a rolling 1-month 25-delta VIX call overlay with a fixed premium budget of 1% of portfolio value per year reduces SPY's maximum drawdown by more than 25% relative to unhedged SPY.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: 1 - MDD(hedged)/MDD(unhedged); secondary: Sharpe difference and hedge P&L per cycle.
- null: Drawdown reduction <= 25%.
- procedure: Monthly cycles from 2009-09 (VIX3M start). The call is priced with Black-76 on F_adj = sqrt((93*VIX3M^2 - 30*VIX^2)/63)*exp(-(VVIX/100)^2*T/2) with sigma = VVIX/100 (model-priced); payoff on spot VIX at expiry as the SOQ proxy. Block bootstrap of the drawdown ratio by resampling 12-month blocks; budget fixed ex ante.
- data: CBOE VIX, VIX3M and VVIX (archive), SPY closes. Model-priced: no VIX option or futures history. · min n: 180
- pass: Lower 95% bound of the drawdown reduction > 25%, with the Sharpe difference reported (not required to be positive).
- controls: SPX 10-delta put hedge with the same budget (model-priced at VIX x skew scale); cash-drag control at the same budget.
- note: from the options-library library: VIX call hedge (rolling long OTM VIX calls); harness suggestion: Monthly model-priced overlay in the harness_vrp_spx style with the VVIX-as-IV pricer; report hedged vs unhedged via harness_controls. | verifier: corrected claim/trial

### T-240 · vix_call_spread_ratio

**Claim.** The realised 21-trading-day volatility of daily log changes in spot VIX is below the entry VVIX in more than 70% of non-overlapping months since 2006.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.cboe.com/tradable_products/vix/vix_options/specifications/, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Win rate of 1{VVIX_t > 100*sqrt(252)*sd(dlnVIX_{t..t+21})}; secondary: model-priced 1x2 P&L with Black-76 on F_adj and VVIX as IV.
- null: Win rate <= 0.70.
- procedure: Daily VVIX from 2006-03-06 (not 2007) and VIX; non-overlapping 21d windows (~245); exact binomial CI plus block bootstrap; walk-forward halves. Spot VIX realises more vol than the futures VVIX refers to, so the test is biased against the claim (conservative).
- data: CBOE VVIX and VIX (archive); VIX3M for the forward proxy in the secondary. · min n: 200
- pass: Lower 95% bound of the win rate > 0.70; positive premium in both halves.
- controls: SPX VRP win rate (VIX^2 vs RV^2) for scale; shuffled-VVIX placebo.
- note: from the options-library library: VIX call spread and call ratio (defined-cost vol hedge / vol-of-vol sale); harness suggestion: New harness_vvix_vrp using cboe_index_history('VVIX') with realised vol of log VIX; reuse harness_vrp_spx structure. | verifier: corrected claim/trial

### T-249 · forward_variance_term_premium

**Claim.** Since 2009-09, the 1-to-3-month SPX forward variance premium as a fraction of implied, (F^2 - RV(22..63))/F^2 with F^2 = (93*VIX3M^2 - 30*VIX^2)/63, exceeds the spot 30-day premium fraction (VIX^2 - RV(1..21))/VIX^2 on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://en.wikipedia.org/wiki/Variance_swap, https://www.cboe.com/tradable_products/vix/term_structure/
- statistic: Mean paired difference [(F^2 - RV_fwd)/F^2] - [(VIX^2 - RV_spot)/VIX^2] per entry.
- null: Paired difference <= 0.
- procedure: Daily VIX and VIX3M from 2009-09-18, SPY closes; non-overlapping 63d cycles (~68) plus all daily starts with a 63-day-block studentized bootstrap; walk-forward halves. Strip discretisation error is measured on the captured SPX chain at the two expiries.
- data: CBOE VIX and VIX3M (archive), SPY closes, captured SPX chain. Model-free. · min n: 60
- pass: Paired difference > 0 with the 95% CI excluding zero; forward win rate > 0.7 (reported).
- controls: Shuffled-VIX3M placebo; sensitivity run excluding 2020; level (not ratio) version as in harness_term_vs_spot.
- note: from the options-library library: Forward-start variance / term-premium strip (long far strip, short near strip); harness suggestion: Same extension of harness_term_structure as the calendar entry; add the premium-to-implied ratio and a two-expiry strip builder in mandel/options. | verifier: corrected claim/trial

### T-255 · btc-vrp-short-straddle

**Claim.** Model-priced (BS at DVOL, daily rehedge on daily closes): a delta-hedged short 30-day ATM BTC straddle has positive mean P&L per cycle over 2021-04 to 2026-09, with a studentized block-bootstrap 95% CI above zero.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/, https://www.deribit.com/api/v2/public/get_historical_volatility?currency=BTC
- statistic: Mean hedged P&L per non-overlapping 30-day cycle (normalised by premium); reported alongside the mean of DVOL^2 - RV^2_30d
- null: Mean hedged P&L <= 0
- procedure: DVOL daily from get_volatility_index_data (paged from 2021-03-24); realised vol from BTC closes; simulate a daily delta-hedged straddle with BS at sigma = DVOL; studentized block bootstrap; walk-forward halves; deflated Sharpe over threshold variants
- data: DVOL 2021-03-24..today (~2,030 days, verified paging); BTC closes · min n: 36
- pass: CI excludes 0 pooled and the sign holds in both halves; Sharpe of hedged P&L > 0.5 after fees
- controls: SPY/VIX hedged straddle as positive control (model-priced); shuffled-DVOL negative control; 1 bp/day funding; haircut the premium by the DVOL-ATM IV gap (estimated from history.deribit.com trade IVs)
- note: from the options-library library: BTC variance risk premium harvest (delta-hedged short straddle); harness suggestion: Existing BTC VRP harness (cycle 3) extended with hedged straddle simulation in Position + daily rehedge | verifier: corrected claim/trial

### T-257 · btc-collar-risk-reversal

**Claim.** Using daily BTC smiles reconstructed from Deribit trade prints, a 30-day delta-hedged 25-delta risk reversal that sells the richer wing has positive mean P&L on entries where |RR25| > 5 vol points, 2022-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name=BTC-30OCT26-70000-C
- statistic: Mean 30-day P&L of the delta-hedged RR, conditional on |RR25| > 5
- null: Mean <= 0
- procedure: From history.deribit.com trades (sampled, e.g. 07:00-09:00 UTC each day), fit a per-expiry smile from trade IVs and interpolate 25-delta call and put IV at 30 DTE; enter when the threshold is hit; price legs by BS at their fitted IVs; hedge daily on closes; mark using the next fitted smiles; non-overlapping entries; block bootstrap
- data: history.deribit.com option trades (iv, mark_price, index_price; free, verified); BTC closes; ongoing daily book capture as quote-based confirmation from 2026-10-14 · min n: 40
- pass: CI > 0 and hit rate > 55%
- controls: Random entry days; fees and a 1-vol-point slippage per leg; re-run on quote captures once 120+ days accumulate
- note: from the options-library library: BTC zero-cost collar / risk reversal on inventory (skew harvest); harness suggestion: Extend deribit_book capture to store 25d RR per expiry; harness on accumulated history | verifier: corrected claim/trial

### T-261 · inverse-quanto-short-strangle

**Claim.** Model-priced (BS at DVOL, daily rehedge on closes): for a short 15-delta inverse BTC strangle, the variance of 30-day USD P&L when hedged with the coin-corrected delta is at least 20% lower than when hedged with the naive BS delta, 2021-04 to 2026-09.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Ratio of USD P&L variance (corrected hedge / naive hedge)
- null: Ratio >= 0.8
- procedure: Simulate daily-rehedged short strangles on BTC closes with IV = DVOL; book the premium in coin; compute USD P&L under both hedge rules; bootstrap the variance ratio
- data: BTC closes; DVOL from 2021-03-24 · min n: 36
- pass: Upper end of the 95% CI of the variance ratio < 0.8
- controls: The same test on a USDC-linear strangle must give ratio ~1; vary collateral treatment (premium only vs premium + collateral)
- note: from the options-library library: Inverse-settled short strangle with coin-payoff (quanto) correction; harness suggestion: Add an inverse-payoff flag to payoff.Leg (divide USD payoff by S_T, premium in coin) and the corrected delta to bs.greeks | verifier: corrected claim/trial

### T-262 · btc-calendar-term-structure

**Claim.** Using BTC ATM IVs reconstructed from Deribit trade prints, long ATM call calendars (front 7-30 DTE / back ~90 DTE) entered when the front IV exceeds the back by more than 5 vol points and held 14 days have positive mean P&L, 2022-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Mean 14-day calendar P&L conditional on inversion > 5 points (hit rate reported)
- null: Mean <= 0
- procedure: Daily ATM IV per expiry from fitted trade-print smiles; detect inversion; price legs by BS at their own IVs; re-mark after 14 days with that day's fitted IVs; non-overlapping entries; block bootstrap
- data: history.deribit.com option trades (free, verified); BTC closes; quote captures from 2026-10-14 as confirmation · min n: 30
- pass: CI > 0
- controls: Random entry days; SPY with VIX vs VIX3M as a structural analogue (model-priced); 1 vol point slippage per leg
- note: from the options-library library: BTC IV term-structure calendar (DVOL vs long-dated IV); harness suggestion: Store ATM IV per expiry per day from deribit_book; term-slope harness mirrors the existing VIX/VIX3M one | verifier: corrected claim/trial

### T-263 · crypto-event-vol

**Claim.** For FOMC decisions 2022-2026, the BTC ATM straddle-implied move (from Deribit trade prints on the day before, for the first post-decision expiry) exceeds the realised close-to-close |return| over the same window on average.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&start_timestamp=1700000000000&end_timestamp=1700300000000&resolution=86400
- statistic: Mean (implied move - realised |move|) across FOMC decisions; hit rate reported
- null: Mean <= 0
- procedure: For each FOMC decision (Fed calendar), take ATM call and put trade prints/marks on the first post-decision expiry during the 24h before; implied move = straddle/index; compare to the realised move to that expiry's 08:00 UTC settlement; bootstrap and sign test
- data: history.deribit.com option trades (free, verified); BTC closes; FOMC dates from federalreserve.gov (8/year, ~38 decisions 2022-2026) · min n: 16
- pass: Mean > 0 with 95% CI excluding 0
- controls: Non-event days with the same DTE as baseline; DVOL change around FOMC (also testable now)
- note: from the options-library library: Crypto event straddle / pre-event IV crush; harness suggestion: Event-date table + straddle capture; interim DVOL pre/post FOMC t-test from existing DVOL history | verifier: corrected claim/trial

### T-268 · dvol-futures-basis

**Claim.** Across expired BTCDVOL futures, the futures mark 7 days before expiry exceeds DVOL at settlement on average (positive vol-futures term premium).

- kind: options-strategy · origin: options-library:crypto-metals-options, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: Mean (F at T-7d - DVOL at settlement), in vol points, across expiries
- null: Mean <= 0
- procedure: For each expired BTCDVOL_USDC future, take mark_price from trades nearest T-7d (history.deribit.com get_last_trades_by_instrument_and_time); DVOL at expiry from get_volatility_index_data; bootstrap across expiries
- data: history.deribit.com DVOL-futures trades (verified free); DVOL history · min n: 12
- pass: 95% CI > 0 (report the mean, target > 2 vol points)
- controls: VIX futures roll-down on the same dates as structural comparison; trade-print timing noise checked against index_price in the same records
- note: from the options-library library: DVOL futures vs straddle basis (vol-of-vol carry); harness suggestion: Extend deribit_book to USDC futures filtered to DVOL instruments | verifier: corrected claim/trial

### T-269 · cme-btc-options-1256

**Claim.** For a top-bracket US individual (37% ordinary, 20% long-term, NIIT ignored), a CME BTC futures covered call has a higher mean annual after-tax return than an IBIT covered call over 2021-2025. Pre-tax P&L is model-priced at DVOL; the CME futures carry is proxied by the Deribit dated-futures basis; IBIT option P&L is short-term and IBIT share gains are long-term when held > 1 year.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: Mean annual after-tax return difference (CME - IBIT)
- null: Difference <= 0
- procedure: Take pre-tax monthly P&L from the btc-covered-call simulation; CME version subtracts the futures basis (annualised, from history.deribit.com dated-futures trades vs index_price) and taxes all P&L 60/40 (26.8% blended) marked at year end; IBIT version taxes option P&L at 37% and share P&L at 20% on realisation (subject to qualified-covered-call rules). Note the identity: on equal pre-tax gains the 1256 edge is 0.102 x gain, so 3 pp/yr needs a pre-tax return >= 29.4%, not 20%.
- data: Simulated P&L from btc-covered-call; Deribit futures trade history (basis proxy); statutory rates · min n: 5
- pass: Mean difference > 0 across years with bootstrap over years; sensitivity table over basis levels
- controls: Zero-return year (difference ~ -basis); loss years (1256 three-year carryback)
- note: from the options-library library: CME Bitcoin options futures-style (1256) covered/short premium; harness suggestion: Post-processing layer on existing covered-call P&L; tax function with 1256 flag | verifier: corrected claim/trial

### T-275 · silver-call-backspread

**Claim.** Model-priced with SLV's trailing 60-day realised vol as a flat IV (no VRP, no skew, so optimistic), 1x2 SLV call backspreads (0.50/0.25 delta, 90 DTE) entered monthly have positive mean P&L over 2006-2026.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: Mean P&L per backspread (as % of SLV price); skewness reported
- null: Mean <= 0
- procedure: SLV closes; monthly entries priced with BS at trailing 60-day RV; hold to expiry; block bootstrap; repeat with RV + 5 vol points (VRP) and with captured SLV IV/skew once available
- data: SLV daily closes (Yahoo, from 2006-04); SLV IV from chain capture later · min n: 100
- pass: Mean CI > 0 under RV pricing and still > 0 at RV + 5 vol points; final verdict on captured IV
- controls: Same on GLD; shuffled returns (kills tail clustering)
- note: from the options-library library: Silver call backspread (squeeze convexity); harness suggestion: Payoff engine template with K1/K2 rules; realised-vol proxy pricing flagged as model-priced | verifier: corrected claim/trial

### T-300 · tsmom-12-1-multi-asset

**Claim.** Pooled across the listed assets (2000-2026, asset-months as available), the 12-1 long/flat TSMOM rule earns a higher mean monthly after-cost return than the Huang et al. historical-mean strategy (long when the asset's expanding-window mean excess return is positive, else T-bill), with the studentized block-bootstrap 95% interval of the pooled mean difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum (fetched), https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing (fetched)
- statistic: Pooled monthly return difference d = r(TSMOM 12-1 long/flat) - r(historical-mean strategy), equal-weighted across active assets each month; its mean and annualised Sharpe; DSR of the d series with n_trials = 104
- null: E[d] = 0: the 12-1 sign carries no information beyond the asset's unconditional drift (Huang-Li-Wang-Zhou null)
- procedure: Refetch adjclose histories; build monthly excess returns with fred-DTB3; compute both strategies per asset with identical execution and costs; pool by calendar month; studentized circular block bootstrap (block 12 months, 5,000 draws) on d; DSR with n_trials = 104 and the observed variance of trial Sharpes; report the 2013-2026 post-publication window separately and the per-asset d signs as diagnostics
- data: Yahoo adjclose daily for SPY, QQQ, GLD, SLV, EFA, AGG, TLT, DBC, BTC-USD, ETH-USD (EFA, AGG, DBC not yet in the archive); fred-DTB3 (in archive) · min n: 300
- pass: Mean d > 0 with bootstrap 95% interval excluding 0 AND DSR(d) > 0.95 over 300+ calendar months; post-2012 mean d >= 0 reported (a negative post-2012 d downgrades to 'decayed')
- controls: Look-ahead: signal uses closes through month-end t, trade one day later, available_at enforced; survivorship: only surviving ETFs (delisted multi-asset ETFs ignored, small upward bias, stated); costs: 2 bps per side SPY/QQQ, 5 bps other ETFs, 25 bps plus 10 bps slippage crypto, T-bill on idle cash; multiple testing: 104 trials incl. T-58; regime: by decade, by VIX tercile at decision, and leave-one-asset-out; dividends: adjclose mandatory (price-only closes understate bond-ETF returns by their yield)
- note: from the underlying-library library: Time-series momentum 12-1 (TSMOM) on index, gold and crypto ETFs/pairs; harness suggestion: New module mandel/experiments/trend.py with signal library (sign_lookback, sma_cross, donchian, nearness_52w) returning per-period strategy returns; harness tsmom_vs_mean(archive, symbols, variants) that reuses backtest_eval.deflated_sharpe_ratio, overfit.pbo_cscv and the block bootstrap; add bundles via mandel.data.social.collect_history for GLD, SLV, EFA, AGG, TLT, DBC and a FRED fetcher for TB3MS. | verifier: corrected claim/trial

### T-301 · sma-10m-timing-multi-asset

**Claim.** On SPY 1994-2026, the 10-month SMA long/flat rule's maximum drawdown is smaller than that of at least 95% of 1,000 random in/out timing paths matched on time in market and on the number and length distribution of out-of-market spells.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://mebfaber.com/timing-model/ (fetched), https://www.aqr.com/Insights/Research/Journal-Article/Which-Trend-Is-Your-Friend (Levine-Pedersen; fetched)
- statistic: Maximum drawdown of the rule; its percentile within the matched random-timing distribution; secondary guardrail: paired Sharpe difference (rule minus buy-and-hold) with studentized block-bootstrap interval
- null: Drawdown reduction is what any timing path with the same exposure profile achieves (the rule's out-of-market months are no better chosen than random spells)
- procedure: Monthly adjclose series; generate 1,000 random paths by randomly re-placing the rule's own out-of-market spells (spell-length preserving) within the sample; compute MDD for rule and paths; Holm correction across the 96 declared variants on the percentile p-values; Sharpe difference via block bootstrap (block 12 months)
- data: Yahoo adjclose for SPY (and EFA, IEF, DBC, VNQ, QQQ, GLD, BTC-USD, ETH-USD for variants); fred-DTB3 · min n: 380
- pass: Rule MDD below the 5th percentile of the matched null (Holm-adjusted p < 0.05) AND Sharpe difference lower 95% bound > -0.15 (non-inferiority)
- controls: Look-ahead: month-end close, trade next day; survivorship: surviving ETFs only (stated); costs: 2 bps SPY, 5 bps others, 25+10 bps crypto per switch; dividends via adjclose (price-only SMA would bias exits for high-yield sleeves); multiple testing: 96 trials plus T-58's 48; regime: 1994-2008, 2009-2021, 2022-2026 reported separately since the reputation rests on 2000-02 and 2008
- note: from the underlying-library library: Long-moving-average timing (Faber 10-month SMA / 200-day) on multi-asset ETFs; harness suggestion: trend.py: sma_timing(prices, months, band) -> position series; harness sma_timing_vs_bh with the matched-time-in-market random null implemented as a permutation of monthly in/out flags; feed per-period returns to deflated_sharpe_ratio and pbo_cscv. | verifier: corrected claim/trial

### T-308 · residual-momentum

**Claim.** On the 9 sector SPDRs 2002-2026, top-3 residual momentum (vs SPY, 36-month betas) has a higher after-cost Sharpe ratio than top-3 total-return 12-2 momentum, with the paired block-bootstrap 95% interval of the Sharpe difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional, https://ideas.repec.org/a/eee/empfin/v18y2011i3p506-521.html (Blitz-Huij-Martens; abstract fetched)
- statistic: Sharpe(residual) - Sharpe(total-return), paired monthly; rank correlation between the two signals (power diagnostic); worst 12-month return of each
- null: Sharpe difference = 0
- procedure: Rolling OLS on monthly excess returns using only months <= t-1; paired studentized block bootstrap (block 12 months, 5,000 draws); DSR over 8 trials; report the average Spearman correlation of the two rankings
- data: Yahoo adjclose for the 9 SPDRs and SPY; fred-DTB3 · min n: 280
- pass: Sharpe difference > 0 with 95% interval excluding 0 AND DSR > 0.95; if mean rank correlation > 0.9 the test is labelled low-power
- controls: Look-ahead: betas and residuals from months up to t-1, trade at t+1; survivorship: constant SPDR set with the 2015/2018 sector reshuffle breaks reported; costs: 5 bps per side; multiple testing: 8 trials; regime: 2008-09 and 2020 reported separately since the claimed benefit is crash reduction
- note: from the underlying-library library: Residual (idiosyncratic) momentum; harness suggestion: trend.py residual_momentum(returns_df, factor_df, window) using numpy lstsq; harness residual_vs_total reusing xs_momentum for the comparison leg. | verifier: corrected claim/trial

### T-309 · fifty-two-week-high

**Claim.** Over 2004-2026, the monthly long-short portfolio formed on 52-week-high nearness across the 19-ETF universe earns a positive after-cost mean return, with the block-bootstrap 95% interval excluding zero and the mean above the 95th percentile of a within-month rank-permutation null.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional and time-series, https://www.nber.org/papers/w23394 (Hou-Xue-Zhang; fetched), https://ideas.repec.org/a/bla/jfinan/v59y2004i5p2145-2176.html (George-Hwang; 404 here, paper known from the literature)
- statistic: Mean monthly long-short return after costs; permutation percentile; DSR over 8 trials; diagnostic: paired difference vs the 12-1 ranking on the same universe
- null: Mean = 0; nearness ranks uninformative
- procedure: Monthly panel from adjclose; universe grows as ETFs reach 252 days of history (full 19 from 2007; start when at least 12 names); block bootstrap (block 12 months); 1,000 permutations; DSR
- data: Yahoo adjclose for the 19 ETFs (most not in archive yet) · min n: 250
- pass: Mean > 0 with 95% interval excluding 0, above the permutation 95th percentile, DSR > 0.95
- controls: Look-ahead: 252-day window ends at t inclusive, trade at t+1; survivorship: ETFs named ex ante; costs: 5 bps per side ETFs, 50 bps a year borrow on shorts; dividends: adjclose (price-only nearness penalises high-yield bond ETFs after each ex-date); multiple testing: 8 trials; regime: by decade
- note: from the underlying-library library: 52-week-high proximity (George-Hwang) as a trend signal; harness suggestion: trend.py nearness_52w(prices) and reuse xs_momentum ranking machinery; harness fifty_two_week_vs_12_1. | verifier: corrected claim/trial

### T-310 · volatility-scaled-trend

**Claim.** Volatility scaling raises the after-cost Sharpe ratio of the 12-1 TSMOM long/flat rule (pooled across the listed assets) by more than it raises the Sharpe ratio of buy-and-hold on the same assets, with the block-bootstrap 95% interval of this difference-in-differences excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/risk-management, https://ideas.repec.org/a/eee/finmar/v30y2016icp103-124.html (Kim-Tse-Wald; fetched), https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html (Barroso-Santa-Clara; fetched)
- statistic: DiD = [Sharpe(scaled TSMOM) - Sharpe(unscaled TSMOM)] - [Sharpe(scaled B&H) - Sharpe(unscaled B&H)], pooled portfolio level; per-asset DiD as diagnostic
- null: DiD = 0: scaling helps the trend rule only as much as it helps buy-and-hold (Kim-Tse-Wald/Cederburg null)
- procedure: Daily data, monthly rebalancing; all four strategies computed with identical costs and financing; joint circular block bootstrap (block 60 days, 5,000 draws) resampling the same blocks for all four; DSR/Holm across 20 trials
- data: Yahoo adjclose daily for the listed assets; fred-DTB3; deribit-dvol-BTC-history (archive) · min n: 300
- pass: DiD > 0 with 95% interval excluding 0 AND Holm-adjusted across 20 trials; DiD sign positive in at least 2 of 3 decades
- controls: Look-ahead: sigma_hat uses returns through t only and no full-sample scaling constant (the Cederburg critique of Moreira-Muir); survivorship: as TSMOM entry; costs: 2-5 bps ETFs and 25+10 bps crypto on all scaling turnover; financing above 1x at T-bill + 50 bps; multiple testing: 20 trials plus the TSMOM base count; regime: 2008, 2020, 2022 reported separately
- note: from the underlying-library library: Volatility-scaled trend (constant-volatility targeting of TSMOM and momentum portfolios); harness suggestion: trend.py vol_scale(positions, returns, estimator, target, cap); harness vol_scaling_dod computing the difference-of-differences; add a Deribit DVOL fetcher (public get_volatility_index_data) for the BTC variant. | verifier: corrected claim/trial

### T-311 · momentum-crash-protection

**Claim.** Over 2000-2026, the bear-and-high-vol filter reduces the worst 3-month return of the sector-SPDR long/short momentum portfolio by more than 95% of random filters with the same number and length of activation spells.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/risk-management, https://www.nber.org/papers/w20439 (Daniel-Moskowitz; fetched), https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html (Barroso-Santa-Clara; fetched)
- statistic: Worst rolling 3-month return of the filtered portfolio; its percentile among 1,000 spell-preserving random activation paths; guardrail: paired Sharpe difference
- null: The filter's activation dates are no better than random dates with the same activation profile
- procedure: Point-in-time indicators; random activation paths by re-placing the filter's own spells; Holm across 24 trials; paired block bootstrap (block 12 months) for the Sharpe guardrail; count activation episodes
- data: Yahoo adjclose for SPY and the 9 SPDRs; crypto variant: CMC data-api historical listings plus Yahoo coin histories · min n: 300
- pass: Worst-3-month return below the 5th percentile of the random-filter null (Holm-adjusted) AND Sharpe difference lower 95% bound > -0.1 AND at least 5 distinct activation episodes; fewer than 5 = inconclusive
- controls: Look-ahead: indicators from data through t; survivorship: constant SPDR set; costs: 5 bps per side at switches, 50 bps a year borrow on shorts; multiple testing: 24 trials; regime: the US sample likely has only 2 activation episodes (2001-03, 2008-09; SPY's 24-month return stayed positive through 2022), so the ETF test is expected to be inconclusive by its own gate and the crypto variant carries the power
- note: from the underlying-library library: Momentum crash protection (Daniel-Moskowitz dynamic momentum / bear-market filter); harness suggestion: trend.py crash_filter(base_weights, market_prices, lookback, vol_pct); harness crash_filter_vs_random with permuted activations; shares xs_momentum output. | verifier: corrected claim/trial

### T-313 · xs-commodity-momentum-etf-proxy

**Claim.** Over 2012-12 to 2026-09, the top-third minus bottom-third 12-1 momentum portfolio across the 13 commodity ETFs earns a positive after-cost mean monthly return, with the block-bootstrap 95% interval excluding zero and the mean above the 95th percentile of a within-month rank-permutation null.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional/commodities, https://www.nber.org/papers/w11222 (Erb-Harvey; fetched), https://econpapers.repec.org/article/eeejbfina/v_3a31_3ay_3a2007_3ai_3a6_3ap_3a1863-1886.htm (Miffre-Rallis; record only)
- statistic: Mean monthly long-short return after costs and borrow; permutation percentile; DSR over 12 trials
- null: Mean = 0; ranks uninformative
- procedure: Monthly adjclose panel; block bootstrap (block 12 months, 5,000 draws); 1,000 within-month permutations; DSR; sub-periods 2013-2019 and 2020-2026
- data: Yahoo adjclose for the 13 ETFs and DBC (only GLD, SLV, USO in archive) · min n: 160
- pass: Mean > 0 with 95% interval excluding 0, above the permutation 95th percentile, DSR > 0.95, positive in both sub-periods
- controls: Look-ahead: ranks at t, trades at t+1; survivorship: universe picked from 2026 survivors (delisted commodity ETNs such as several iPath notes excluded; list exclusions in the result); costs: 10-20 bps per side on thin names plus 1-3% a year borrow for UNG/USO shorts; multiple testing: 12 trials; regime: report ex-energy (USO, UNG, DBE removed) since energy dominates 2014-16 and 2020-22; USO 2020 restructuring flagged
- note: from the underlying-library library: Cross-sectional commodity momentum via commodity ETF proxies (futures version blocked); harness suggestion: collect_history for the ETF list; reuse xs_momentum; harness xs_commodity_etf with an exclusion list recorded in the result for the survivorship control. | verifier: corrected claim/trial

### T-314 · xs-crypto-momentum-weekly

**Claim.** Over 2018-2026, the top-tertile 3-week momentum portfolio of the point-in-time top-30 coins earns a positive mean weekly return in excess of BTC after costs, with the block-bootstrap 95% interval excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional/crypto, https://www.nber.org/papers/w25882 (Liu-Tsyvinski-Wu; fetched), https://www.nber.org/papers/w24877 (Liu-Tsyvinski; fetched)
- statistic: Mean weekly (long top tertile - BTC) return after costs; DSR over 24 trials; permutation percentile; diagnostic: same statistic on today's-top-30 universe to measure survivorship inflation
- null: Mean = 0; ranks uninformative
- procedure: Scrape weekly CMC snapshots 2017-12 onward into bundle cmc-historical-listings with available_at = snapshot date + 1 day; weekly ranks; block bootstrap (block 8 weeks, 5,000 draws); 1,000 permutations; DSR
- data: CMC data-api historical listings (reachable, not yet ingested); Yahoo *-USD daily closes as a cross-check · min n: 400
- pass: Mean > 0 with 95% interval excluding 0 after 40 bps per side plus 10 bps slippage, DSR > 0.95, above the permutation 95th percentile
- controls: Look-ahead: snapshot ranks and prices as of t, trade t+1; survivorship: point-in-time universe mandatory, delisted coins held until their last snapshot price (a coin that vanishes is marked at its last price minus 50% as a stress case); costs: 40+10 bps per side; multiple testing: 24 trials; regime: per cycle (2018-20, 2021-22, 2023-26)
- note: from the underlying-library library: Cross-sectional crypto momentum (1-4 week, Liu-Tsyvinski-Wu factor); harness suggestion: New fetcher for dated top-N lists (CoinMarketCap historical snapshot scrape, or CoinGecko coins/markets saved daily from now on as a growing bundle); trend.py xs_momentum reused on weekly bars; harness xs_crypto_momentum with the survivorship sensitivity reported as a statistic. | verifier: corrected claim/trial

### T-316 · prediction-market-momentum-event-time

**Claim.** Over at least 300 shock events in Polymarket markets priced in [0.15, 0.85], buying in the direction of a 2.5-sd daily logit shock and holding 3 days earns a positive mean return after a 2-cent round-trip cost, with the market-clustered bootstrap 95% interval excluding zero and the mean above that of price-matched non-shock control days.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/event-contracts, https://quantpedia.com/exploiting-mean-reversion-in-decentralized-prediction-markets-evidence-from-polymarket-binary-contracts/ (fetched; cites Clinton-Huang 2025), https://fc26.ifca.ai/defi/papers/market-efficiency-prediction-markets.pdf (fetched and text-extracted)
- statistic: Mean 3-day post-shock return in probability points (shock direction) minus cost; difference vs matched controls (same price bucket, same days-to-endDate bucket); DSR of event returns with n_trials = 36
- null: Zero post-shock drift; post-shock returns equal matched-control returns
- procedure: polymarket-price-history-daily joined to polymarket-closed-markets metadata; point-in-time shock detection; 2,000 bootstraps clustered by market; Kalshi candles as replication set
- data: polymarket-price-history-daily (399 markets, 62,362 rows), polymarket-closed-markets (2,100 metadata rows), kalshi-candles (68 markets) · min n: 300
- pass: Mean > 0.02 with 95% interval excluding 0 and exceeding matched controls, DSR > 0.95, Kalshi replication sign agrees
- controls: Look-ahead: shock at day t, entry at day t+1 price; variant B must use the endDate as first published, but the closed-markets snapshot was taken 2026-10-14 (available_at) so endDate may have been revised after the fact: restrict B to markets whose endDate is within 1 day of the actual close, or drop B; survivorship: the 399-market history set was selected by volume ex post (stated leak); costs: 2 cents Polymarket, Kalshi fee formula; multiple testing: 36 trials incl. T-10; regime: by category and days-to-resolution bucket
- note: from the underlying-library library: Prediction-market price momentum revisited: event-time, shock-conditioned and cross-outcome versions; harness suggestion: mandel/experiments/pm_momentum.py: shock_continuation(series_by_market, sd_mult, hold) with matched controls; event_time_momentum(...) using listing/resolution dates from closed-markets; cross_outcome(...) grouping markets by event id (Gamma 'events' field); register as theories T-48..T-50 with T-10 named as the superseded search. | verifier: corrected claim/trial

### T-317 · trend-crisis-alpha-smile

**Claim.** Over 2000-2026, the quarterly returns of the equal-risk TSMOM long/short portfolio have a positive coefficient on squared quarterly SPY excess return that exceeds the coefficient produced by the same rule applied to simulated driftless random walks with each sleeve's volatility and cross-correlation, with the block-bootstrap 95% interval of the excess coefficient excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/portfolio-property, https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing (fetched), https://arxiv.org/abs/1404.3274 (fetched)
- statistic: gamma = coefficient on SPY^2 (with SPY linear term) minus the mean gamma from 1,000 simulated no-autocorrelation paths (mechanical convexity); diagnostic: mean trend return in SPY's worst-decile quarters
- null: gamma equals the mechanical convexity of a trend rule on random walks (no real crisis alpha)
- procedure: Monthly sleeve returns from adjclose, quarterly aggregation; HAC regression plus block bootstrap (block 4 quarters, 5,000 draws); simulation null by resampling sleeve return vectors i.i.d. by month (keeps cross-correlation, removes autocorrelation); Holm across 8 trials
- data: Yahoo adjclose for the 8 sleeves (most not in archive); fred-DTB3 · min n: 100
- pass: gamma minus simulated gamma > 0 with 95% interval excluding 0, Holm-adjusted across 8 trials; leave-one-crisis-out (2000-02, 2008, 2020, 2022) keeps the sign
- controls: Look-ahead: signals lagged one month, vol from past returns; survivorship: fixed sleeves; costs: 5 bps per side plus borrow on shorts; multiple testing: 8 trials (Holm, since DSR does not fit a regression coefficient); regime: about 4 crisis episodes drive the result, reported individually
- note: from the underlying-library library: Trend-following crisis alpha: convexity of trend returns in large market moves; harness suggestion: trend.py tsmom_portfolio(...) feeding a harness crisis_smile with the quadratic regression and the worst-decile statistic; share sleeve code with the TSMOM entry. | verifier: corrected claim/trial

### T-318 · ta-rule-universe-reality-check

**Claim.** On SPY 1994-2026, the walk-forward-selected best rule from the frozen 88-rule universe does not beat buy-and-hold after costs: Hansen's SPA test of the full universe against buy-and-hold does not reject at 5% and the CSCV probability of backtest overfitting exceeds 0.5.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/meta-control, https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html (Sullivan-Timmermann-White; abstract fetched), https://ideas.repec.org/a/bla/jecsur/v21y2007i4p786-826.html (Park-Irwin; fetched)
- statistic: Hansen SPA p-value (benchmark buy-and-hold, loss = negative daily excess return); CSCV PBO; DSR of the in-sample best rule with n_trials = 88; out-of-sample Sharpe of the walk-forward-selected rule minus buy-and-hold
- null: (for the control) No rule beats buy-and-hold (SPA null); selected rule's out-of-sample rank is random (PBO = 0.5)
- procedure: Compute daily returns for all 88 rules; SPA with stationary bootstrap (mean block 20 days, 5,000 draws); pbo_cscv with 16 partitions; deflated_sharpe_ratio; walk-forward selection every 5 years with block bootstrap on the out-of-sample difference; repeat on QQQ, GLD, BTC as replications
- data: Yahoo adjclose daily for SPY, QQQ, GLD, BTC-USD · min n: 8000
- pass: Control confirmed if SPA p > 0.05 AND PBO > 0.5 AND the out-of-sample difference's interval includes or lies below 0; if SPA p < 0.05 and PBO < 0.5, record a surprise and promote the surviving rule to its own theory
- controls: Look-ahead: one-bar delay; survivorship: single surviving assets; costs: 2 bps SPY, 5 bps GLD/QQQ, 25+10 bps BTC per switch (fast rules trade 20-50 times a year); multiple testing: this entry measures it; regime: PBO per decade
- note: from the underlying-library library: Technical rule universe reality check on SPY and BTC (declared MA/channel search, expected to fail); harness suggestion: Extend mandel/experiments/overfit.py momentum_variants to a rule_universe(prices, spec) generator; harness ta_reality_check reusing pbo_cscv and deflated_sharpe_ratio; register as a control theory analogous to T-10 for underlyings. | verifier: corrected claim/trial

### T-319 · xs-short-term-reversal

**Claim.** On the declared 30-ETF universe from 2010-01 to 2026-09, the weekly skip-a-day 1-week reversal quintile long-short portfolio has a mean weekly return greater than zero net of 10 bps per leg per trade and 50 bps/yr borrow on the short leg.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.nber.org/papers/w2533, https://doi.org/10.1111/j.1540-6261.1990.tb05110.x
- statistic: mean weekly net long-short return (and annualized net Sharpe); deflated Sharpe with n_trials = every variant run (at least 8)
- null: mean net weekly return = 0 (studentized circular block bootstrap, block 8 weeks, re-centred at zero)
- procedure: The rule is parameter-free; declare the universe, variants and cost model before the run. Compute weekly long-short returns from Yahoo adjusted closes. Vol targeting uses only trailing data. Run a 5,000-resample studentized block bootstrap for the interval, DSR over all variants, and CSCV PBO (overfit.pbo_cscv) across the variant matrix. Report 2010-2017 and 2018-2026 separately, plus VIX terciles.
- data: Yahoo daily adjusted closes for the 30 declared ETFs (all start by 2000); stock variant from fja05680 S&P 500 membership plus Yahoo (delisted members missing); CBOE VIX history (archive) · min n: 500
- pass: bootstrap 95% lower bound of mean net weekly return > 0 AND DSR > 0.95 AND PBO < 0.5 AND same sign in both halves
- controls: Look-ahead: formation ends at close t-1 and the trade is at close t; a next-open variant is reported. Yahoo back-adjustment for dividends does not leak future information into returns. Survivorship: the ETF universe is clean; the stock variant lacks delisted members and is reported only as a biased upper bound. Asynchrony: country ETFs trade after their home markets close, so part of any reversal is ETF premium reversion (still tradable on ETF prices; flagged). Costs: 10 bps/leg/trade plus 50 bps/yr borrow; break-even cost reported. Multiple testing: DSR/PBO over all variants. Regime: halves and VIX terciles.
- note: from the underlying-library library: Cross-sectional short-term reversal (1-week and 1-month); harness suggestion: xs_reversal_walkforward: ranks trailing returns per universe, builds decile L/S, applies cost model, feeds dsr_pbo_harness | verifier: corrected claim/trial

### T-321 · pairs-distance

**Claim.** The GGR top-20 distance rule with one-day wait on the declared 51-ETF universe, trading 2008-01 to 2026-09, earns a positive mean monthly return on committed capital net of 15 bps per leg per trade and 50 bps/yr borrow.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.nber.org/papers/w7032, https://doi.org/10.2469/faj.v66.n4.1
- statistic: mean monthly net return on committed capital; Sharpe; DSR over variants
- null: zero net return; secondary control: randomly drawn pairs traded with identical rules
- procedure: Rolling 12-month formation and 6-month trading with all parameters declared. Studentized block bootstrap over monthly returns (block 6). Random-pair control: 1,000 draws of 20 random pairs. DSR with n_trials = variants x thresholds; CSCV PBO.
- data: Yahoo daily adjusted closes for the 51 ETFs (most since 1999-2007; universe grows point-in-time as ETFs list) · min n: 120
- pass: net mean > 0 with 95% interval excluding 0 AND mean exceeds the 95th percentile of the random-pair control AND DSR > 0.95
- controls: Look-ahead: an ETF enters the universe only after 12 months of history. Yahoo back-adjustment scales all earlier prices by a constant, so normalized formation indices are unaffected (this replaces the old dividend-timing note, which was not a look-ahead issue). Survivorship: the ETF universe has no delistings; the stock variant is biased. Costs: 15 bps/leg/trade plus borrow. Multiple testing: DSR/PBO. Regime: 2008-2014 vs 2015-2026.
- note: from the underlying-library library: Pairs trading, distance method (Gatev-Goetzmann-Rouwenhorst); harness suggestion: pairs_distance_harness: formation/trading windows, SSD ranking, spread rules, cost model; outputs monthly series to dsr_pbo_harness | verifier: corrected claim/trial

### T-322 · pairs-cointegration

**Claim.** Pairs selected by Engle-Granger cointegration (p < 0.05 with MacKinnon critical values, half-life 2-30 days) over a 12-month window keep a stationary spread (rolling ADF p < 0.10) in the following 6 months in more than 50% of cases.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1080/14697688.2016.1164337, https://doi.org/10.1080/00036846.2014.975417
- statistic: share of selected pairs whose out-of-sample spread passes ADF at p < 0.10 (net trading Sharpe reported as a secondary, not a pass condition)
- null: persistence share equal to that of an equal number of randomly drawn candidate pairs given the same test (false-discovery baseline)
- procedure: Rolling formation/trading windows 2008-2026. Count persistence and bootstrap the share over windows (block = 1 year). Random-pair baseline from 1,000 draws. Trade survivors with the declared thresholds and report Sharpe and DSR over variants.
- data: Yahoo daily adjusted closes: 51 ETFs (2007-), BTC-USD/ETH-USD · min n: 200
- pass: 95% lower bound of the persistence share > 50% AND > random-pair share + 20 percentage points
- controls: Look-ahead: beta, mean, sd and thresholds frozen at formation end. Critical values: MacKinnon EG tables, since naive DF values over-reject. Survivorship: ETF universe clean. Costs: 15 bps/leg (ETFs), 40 bps/leg (crypto) for the secondary Sharpe. Multiple testing: the number of candidate pairs is the trial count; the persistence share is the FDR measure. Regime: 2008-2009, 2020 and 2022 windows reported separately.
- note: from the underlying-library library: Pairs trading, cointegration method (Engle-Granger / Johansen spread); harness suggestion: pairs_coint_harness: ADF/Johansen with numpy-only implementation, rolling persistence counter, spread z trading; shares the cost model with pairs_distance_harness | verifier: corrected claim/trial

### T-323 · pairs-kalman

**Claim.** On the same pairs and 6-month windows as pairs-cointegration (2008-2026), the Kalman time-varying hedge ratio yields a higher out-of-sample net Sharpe than the static OLS hedge ratio, with the bootstrap interval of the paired difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1080/14697680500149370, https://doi.org/10.1111/joes.12153
- statistic: paired difference in net Sharpe (Kalman minus static) across pair-windows; Ledoit-Wolf HAC Sharpe-difference test plus block bootstrap over windows
- null: zero difference
- procedure: Same pairs, windows and cost model; only the hedge-ratio estimator differs. EM fitted on the formation window; the filter runs forward only. Count the delta/threshold grid as trials.
- data: as pairs-cointegration (Yahoo adjusted closes for 51 ETFs; BTC/ETH) · min n: 100
- pass: mean difference > 0 with 95% interval excluding 0 in both 2008-2016 and 2017-2026, and DSR of the Kalman variant > 0.95
- controls: Look-ahead: forward filter, formation-only parameters. Costs include extra hedge-leg rebalancing (15 bps/leg ETFs, 40 bps crypto). Multiple testing: delta x threshold grid counts as trials. Regime: halves; 2020 and 2022 breaks reported.
- note: from the underlying-library library: Pairs trading with a Kalman-filter (state-space) hedge ratio; harness suggestion: pairs_kalman_harness: numpy Kalman filter with EM, paired against pairs_coint_harness output | verifier: corrected claim/trial

### T-325 · leveraged-etf-short-pair-decay

**Claim.** Shorting equal dollars of TQQQ and SQQQ, reset monthly, from 2010-03 to 2026-09, earns a positive mean monthly return on gross short notional after a 3%/yr borrow fee on each leg, with DTB3 interest credited on short proceeds.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1137/090760805, https://doi.org/10.1017/s0022109012000622
- statistic: mean monthly net return on gross short notional with block-bootstrap interval; diagnostics: borrow break-even, max drawdown, regression of monthly P&L on QQQ realized variance
- null: mean monthly net return = 0
- procedure: Simulate daily from Yahoo adjusted closes with monthly resets. Apply 3%/yr borrow per leg (sensitivity 0-8%) and DTB3 income. Studentized block bootstrap (block 6 months). Report the borrow break-even. Repeat on the 3 other pairs and the threshold rule (8 trials) for DSR.
- data: Yahoo daily adjusted closes (split-adjusted): TQQQ/SQQQ since 2010-02, SSO/SDS since 2006, UPRO/SPXU since 2009, UVXY/SVXY since 2011; FRED DTB3 (archive); Yahoo 60-minute bars (~730 days) for the late-day variant · min n: 150
- pass: 95% lower bound of mean monthly net return > 0 at 3%/yr borrow AND DSR > 0.95 over the 8 trials
- controls: Look-ahead: none (mechanical). Structural changes: SVXY and UVXY leverage changes on 2018-02-28 modelled as breaks; reverse splits handled by split-adjusted closes. Costs: borrow is time-varying and spikes in stress (sensitivity grid); FINRA leveraged-ETF short margin (roughly leverage x standard requirement, up to ~90-100% for 3x) means forced covering in drawdowns, modelled with a margin-call stop at 2x initial margin. Regime: 2010-2019 vs 2020-2026; the 2022 trend year reported. Multiple testing: 8 trials.
- note: from the underlying-library library: Leveraged ETF volatility decay: short both legs of a +3x/-3x pair; harness suggestion: letf_short_pair_sim: daily simulator with borrow/financing inputs and realized-variance regression; outputs borrow break-even | verifier: corrected claim/trial

### T-326 · gold-silver-ratio-reversion

**Claim.** On GLD/SLV from 2008-04 (after a 500-day warm-up) to 2026-09, the declared 500-day-anchor z-score rule earns a positive mean daily net return after 20 bps per leg per trade and 50 bps/yr borrow on the short leg.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1016/s1044-0283(01)00034-5, https://www.tcd.ie/triss/assets/PDFs/iiis/iiisdp55.pdf
- statistic: mean daily net return of the rule (and Sharpe); diagnostic: variance ratio VR(20/60/250) of the log ratio with heteroskedasticity-robust intervals
- null: mean daily net return = 0 (stationary block bootstrap, block 60 days); VR = 1 for the diagnostic
- procedure: Trailing statistics only. Simulate the rule. Block bootstrap. DSR with n_trials = this entry's 4 anchor/route variants plus T-61's tested variant. Repeat on roll-adjusted GC=F/SI=F from 2002.
- data: Yahoo GLD (2004-11) and SLV (2006-04) adjusted closes; Yahoo GC=F and SI=F continuous front-month (2000-09), rolled using CME active-month calendars · min n: 2000
- pass: 95% lower bound of mean daily net return > 0 AND DSR > 0.95 AND same sign on the GC/SI route
- controls: Look-ahead: trailing windows; execution at the next close. Futures roll: GC (Feb/Apr/Jun/Aug/Oct/Dec) and SI (Mar/May/Jul/Sep/Dec) roll on different calendars, so roll jumps do NOT cancel in the ratio (corrects the earlier note); roll-adjust or use GLD/SLV as primary. Costs: 20 bps/leg plus borrow. Multiple testing: includes T-61. Regime: 2008, the 2011 silver spike, 2020 and 2024-2026 reported separately. Few trades expected (~10-25), so power is low: report trade count.
- note: from the underlying-library library: Gold-silver ratio mean reversion; harness suggestion: ratio_reversion_harness: variance ratio + z-rule simulator, parameterised by two tickers (reusable for ETH/BTC, GLD/GDX) | verifier: corrected claim/trial

### T-328 · btc-etf-premium-discount

**Claim.** For IBIT from 2024-04 to 2026-09, fading |z| > 2 deviations of the 16:00 ET premium to synthetic NAV against an opposite Coinbase spot position, closed at z = 0 or after 3 trading days, earns a positive mean net return per trade after 0.85% round-trip costs (Coinbase maker 0.40% each way plus 5 bps IBIT spread).

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://arxiv.org/abs/2409.00270, https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf
- statistic: mean net return per trade with bootstrap interval; diagnostics: AR(1) half-life of premium_t, signal count, gross mean per trade
- null: mean net return per trade = 0
- procedure: Build the synthetic NAV from Coinbase hourly candles (public, 300 per call, paginated) and calibrate bitcoin-per-share to iShares' published figure. Compute premium and z. Simulate. Bootstrap over trades clustered by week. Report the cost at which the rule breaks even (expected to be far below 0.85%).
- data: Yahoo IBIT/FBTC daily (2024-01-) and 60-minute bars (~730 days); Coinbase BTC-USD hourly candles (verified); iShares published bitcoin-per-share for calibration · min n: 30
- pass: 95% lower bound of mean net return per trade > 0 at 0.85% cost; else park as 'premium within AP cost band'
- controls: Look-ahead: synthetic NAV uses only the candle ending 16:00 ET; trailing z. Costs: 0.85% retail and 0.25% high-tier sensitivity. Sponsor-fee drift modelled. Settlement mismatch: T+1 equities vs immediate crypto needs capital on both venues. Regime: launch period excluded; 2025-2026 reported separately. Multiple testing: 6 variants.
- note: from the underlying-library library: Spot bitcoin ETF premium/discount to BTC (IBIT, FBTC) reversion; harness suggestion: etf_vs_spot_premium: synthetic-NAV builder (hourly spot x holdings per share) + AR(1) + z rule; shares code with trust_discount_reversion | verifier: corrected claim/trial

### T-330 · stablecoin-peg-reversion

**Claim.** Across USDT and USDC discount episodes 2018-2026 defined on Yahoo daily closes (executed at the next close, Kraken/Coinbase closes where available), the mean net return per episode after 0.40% round-trip cost is greater than zero.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.nber.org/papers/w27136, https://doi.org/10.1111/jofi.12903
- statistic: mean net return per episode with bootstrap interval; diagnostics: repeg-within-3-days rate (Wilson interval), worst episode loss
- null: mean net return per episode = 0
- procedure: Detect episodes on Yahoo closes and re-price each at executable venue closes where they exist (Coinbase USDT-USD 2021-; Kraken USDCUSD/USDTUSD daily bars rebuilt from the public Trades endpoint, which pages full tick history; the OHLC endpoint is capped at 720 bars). Bootstrap over episodes. Report USDT and USDC separately and pooled. Include UST/USDN in a tail-risk appendix.
- data: Yahoo USDT-USD (2017-11-) and USDC-USD (2018-10-) daily (composite); Coinbase USDT-USD daily (2021-); Kraken Trades endpoint (full history, verified back to 2017 for XBTUSD) · min n: 10
- pass: 95% lower bound of mean net return per episode > 0 with at least 10 episodes; if fewer than 10, verdict 'inconclusive (too few events)'
- controls: Look-ahead: enter at the close after the signal close. Composite prices overstate executable depth, so the venue re-pricing is the clean read. Costs: 0.40% round trip (Kraken stablecoin schedule); 1.2% Coinbase taker sensitivity. Survivorship: failed pegs reported in the appendix. Power: expect only ~5-20 episodes; the earlier min_n of 20 was likely unattainable. Regime: 2022 (UST), 2023-03 (SVB).
- note: from the underlying-library library: Stablecoin peg deviation reversion (USDT, USDC); harness suggestion: peg_event_harness: event detector on daily lows, repeg counter, per-event P&L with venue fee inputs | verifier: corrected claim/trial

### T-331 · crypto-cross-exchange-gap

**Claim.** For BTC-USD from 2022-01 to 2026-09, the last-trade Coinbase-vs-Kraken gap at hourly marks exceeds 0.70% (the cheapest two-venue maker cost at retail tiers) in at least 0.5% of hours.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.2139/ssrn.3171204, https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- statistic: share of hourly marks with |gap| > 0.70%, with Wilson interval; diagnostics: gap AR(1), single-venue rule net return
- null: share = 0 beyond what a 1-minute price-staleness simulation produces
- procedure: Pull Coinbase 1-minute candles and Kraken public Trades (paged since timestamps; full history) for 2022-2026. Align on UTC hour marks using last trades. Compute the gap series. Count excursions. Simulate the staleness null by shifting one venue's mark by up to 60 s. Report stress windows (2022-11 FTX, 2023-03, 2024-08).
- data: Coinbase BTC-USD 1-minute/hourly candles (public, verified to 2015); Kraken public Trades endpoint (verified: returns 2017 trades) or Kraken's downloadable historical OHLCVT files · min n: 2000
- pass: lower Wilson bound of the excursion share >= 0.5%; otherwise record 'no retail-tier cross-exchange edge'
- controls: Look-ahead: last trade at or before the mark only. Staleness: candle closes overstate gaps, hence the 60 s staleness null. Costs: maker fees on both venues plus periodic inventory rebalancing (withdrawal fees, transfer time). Regime: stress windows separate. Multiple testing: 4 variants.
- note: from the underlying-library library: Cross-exchange crypto price gap reversion (Coinbase vs Kraken); harness suggestion: cross_venue_gap: dual-venue aligner, excursion counter, gap AR(1) and reversion rule; also feeds the Polymarket-Kalshi cross-venue harness | verifier: corrected claim/trial

### T-334 · index-rebalance-reversal

**Claim.** For S&P 500 additions with effective dates 2010-2026, the mean 20-trading-day return after the effective-date close, relative to SPY, is below -0.2% (net of 10 bps per leg per trade), with the bootstrap upper bound below zero.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.2139/ssrn.427001, https://www.nber.org/papers/w30748
- statistic: mean 20-day excess return after the effective date; trend of the mean by 5-year bucket
- null: zero excess return; placebo: random non-changing S&P 500 members matched on size and on the same dates
- procedure: Build the change list from fja05680 (membership by date; additions = first appearance). Pull Yahoo prices. Compute event returns vs SPY. Bootstrap over events clustered by effective date (multiple adds share a date). Placebo sampler with 1,000 draws.
- data: fja05680/sp500 historical components (MIT licence) + Yahoo daily adjusted closes; SPY · min n: 150
- pass: mean 20-day excess < -0.2% net with 95% upper bound < 0 AND placebo centred on zero
- controls: Look-ahead: trade only on dates the membership change is public; using later-known membership as the universe is forbidden. Survivorship: additions are listed at entry and rarely delist within 20 days, so they are the clean read; deletions often delist and are missing from Yahoo (biased). Costs: 10 bps/leg. Regime: 5-year buckets show the Greenwood-Sammon decline. Multiple testing: 5 variants.
- note: from the underlying-library library: Index-rebalance reversal (S&P 500 additions/deletions, Russell reconstitution, month-end flows); harness suggestion: index_event_study: event-date loader, excess-return windows, placebo sampler; month_end_flow for the calendar variant on SPY | verifier: corrected claim/trial

### T-336 · polymarket-kalshi-cross-venue-convergence

**Claim.** On hand-audited templated Polymarket-Kalshi pairs (FOMC, CPI, BTC thresholds) observed hourly, gaps above 5 points halve within 24 hours in more than 70% of episodes.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://quantpedia.com/systematic-edges-in-prediction-markets/, https://papers.ssrn.com/abstract=5331995
- statistic: 24-hour gap-halving rate with Wilson interval; diagnostics: weekly episode count, convergence-trade net return per episode
- null: halving rate equal to that of simulated random-walk gaps with matched hourly volatility
- procedure: Backfill: Kalshi settled markets and hourly candles (archive plus API) and Polymarket CLOB prices-history with startTs/endTs and fidelity=60 for the matched resolved markets. Then capture forward. Join on resolution date and threshold. Compute episodes and halving. Simulate the null. Bootstrap clustered by event.
- data: Kalshi public API (settled markets, hourly candles; KXFED verified live); Polymarket Gamma + CLOB prices-history (long-lived FOMC/CPI markets have hourly history; short-lived daily BTC markets have few points); FRED release calendar · min n: 50
- pass: lower Wilson bound of the halving rate > 70% with at least 50 episodes; secondary: convergence-trade mean net return per episode > 0
- controls: Matching errors (resolution source, timing, strike definition) are the main false positive, so every pair is audited by hand. Fees per venue. Point-in-time joins on observed_at; hourly candles from both venues aligned to the same UTC hour. Capital lock to resolution for the pure-arb variant. Regime: release windows vs quiet periods.
- note: from the underlying-library library: Polymarket vs Kalshi cross-venue convergence (templated events); harness suggestion: cross_venue_match: template matcher (series ticker <-> slug regex), hourly gap series, episode/halving counter, lead-lag permutation test | verifier: corrected claim/trial

### T-337 · polymarket-vs-deribit-digital-arb

**Claim.** On Polymarket BTC Above markets with p_RN between 0.05 and 0.95, observed hourly over 2024-2026, fading |gap_t| > 5 points against the Deribit-implied probability earns a positive mean net return per trade after Polymarket crypto taker fees (0.07 x p x (1 - p)) and a 1-point model-error haircut.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://fc26.ifca.ai/defi/papers/market-efficiency-prediction-markets.pdf, https://arxiv.org/abs/2606.19517
- statistic: mean net return per trade (resolution or exit P&L) with bootstrap interval; diagnostics: AR(1) half-life of gap_t, paired Brier difference p_RN vs p_poly on resolved markets
- null: mean net return per trade = 0
- procedure: Historical backfill: Deribit option trades/IV from history.deribit.com by hour; Polymarket prices-history (fidelity=60, startTs/endTs) for weekly and monthly Above markets (daily markets have too few points). Fit smiles. Compute p_RN and gap. Simulate fades. Bootstrap clustered by market. Then capture forward hourly. Report SVI vs cubic fits.
- data: Deribit history API (free, verified) and public book summaries; Deribit DVOL (archive, crude flat-smile cross-check); Polymarket Gamma crypto events + CLOB prices-history; resolutions from Gamma · min n: 300
- pass: 95% lower bound of mean net return per trade > 0 under both smile fits AND same sign in 2024-2025 and 2026
- controls: Look-ahead: only option trades and Polymarket prices with timestamps <= decision time; resolution excluded from inputs. Model risk: two smile fits, difference used as an error bar; sparse-trade hours flagged. Risk-premium confound: tails excluded from the primary read. Fees: Polymarket crypto taker 0.07; makers free. Resolution-source mismatch: Binance vs Deribit index basis applied. Regime: weekends, macro-release days. Multiple testing: 7 variants in DSR.
- note: from the underlying-library library: Polymarket BTC threshold contracts vs Deribit option-implied digital probabilities; harness suggestion: digital_vs_rn_harness: smile fitter + Breeden-Litzenberger integrator, gap store, fade simulator, proper-score comparison reusing scoring.py | verifier: corrected claim/trial

### T-345 · month-end-rebalancing-flow

**Claim.** Over 2002-2026, in months where SPY has beaten TLT month-to-date by more than 2 pp at the T-3 close, SPY's return over the last two trading days is lower than its last-two-day return in all other months by at least 15 bps on average, with the gap negative in both halves.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w33554, https://research.aalto.fi/en/publications/dash-for-cash-monthly-market-impact-of-institutional-liquidity-ne/
- statistic: Mean 2-day SPY return in signal months minus the mean in other months (bps). Secondary: the mean SPY-minus-TLT 2-day spread in signal months.
- null: No conditional difference. Permutation of the signal label across months (10,000 draws), plus a block bootstrap over months (block 3).
- procedure: The signal uses closes available at the T-3 close. The 2-day window is fixed. Halves 2002-2013 / 2014-2026. Declared grid: 3 thresholds x 2 decision days, plus quarter-end, equity-leg and GLD/BTC analogues = 10 trials (DSR/Holm).
- data: daily-history-SPY, TLT (2002-07-), AGG, IWM, GLD, BTC-USD (stored); IEF via Yahoo (2002-07-30, verified). · min n: 80
- pass: Difference < -15 bps with permutation p < 0.05, both halves negative, net of 2 bps per leg; min_n counts signal months.
- controls: Look-ahead: signal at the T-3 close. Survivorship: n/a. Costs: 2 legs x up to 12 trades/yr at 1-2 bps. Multiple testing: 10 trials. Regime: halves; 2008, 2020 and the 2022 bond bear flagged.
- note: from the underlying-library library: Month-end rebalancing flow (stocks vs bonds); harness suggestion: events.py: month_end_rebalance(days_spy, closes_spy, days_tlt, closes_tlt, threshold_pp=2.0, decision_day=-3, window=2) -> conditional means, permutation p, halves; share the month-indexing helper with turn_of_month. | verifier: corrected claim/trial

### T-347 · day-of-week-speculative-spread

**Claim.** Over 2011-2026, the daily return of the SPHB-minus-SPLV spread is higher on Fridays than on Mondays by at least 10 bps on average, with the contrast positive in both halves.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://alphaarchitect.com/2019/03/investor-mood-day-of-the-week-and-the-cross-section-of-returns/, https://academicnewsletter.sufe.edu.cn/info/356118
- statistic: Mean spread return on Fridays minus mean on Mondays (bps). This is a single pre-registered contrast; no weekday Bonferroni applies to it.
- null: Equal Friday and Monday means. Studentized block bootstrap (block 10 trading days) of the day-flagged spread series; plus a permutation of weekday labels within calendar weeks.
- procedure: Build the spread series from daily closes. Run the contrast with halves 2011-2018 / 2019-2026. The 5 non-primary variants are Holm-adjusted secondary trials.
- data: daily-history-SPHB, SPLV, USMV (stored); IWO, IWN, ARKK via Yahoo (ARKK verified from 2014-10-31); VIX (stored); GLD, SLV (stored). · min n: 600
- pass: Contrast > 10 bps with p < 0.05 and both halves positive; the net-of-cost strategy (about 4-8 bps/week) is reported separately.
- controls: Look-ahead: none. Survivorship: ETFs chosen ex ante except ARKK (flagged). Costs: 2 legs x 2 round trips/week at 1-2 bps. Multiple testing: 1 primary plus 5 Holm. Regime: halves; 2020-2021 meme period flagged.
- note: from the underlying-library library: Day-of-week effects: speculative-minus-safe Monday/Friday spread; harness suggestion: Reuse weekday_effect on a synthetic spread series: spread_closes = cumulative product of (1 + r_spec - r_safe); add a 'contrast' parameter to compare two named weekdays directly. | verifier: corrected claim/trial

### T-349 · pre-holiday-effect

**Claim.** Over 2000-2026, IWM's return on the last trading day before scheduled NYSE holidays exceeds its mean return on all other days by at least 10 bps, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/taf/apfiec/v15y2005i2p107-119.html, https://cfr.ivo-welch.info/published/papers/ko2021pre.pdf
- statistic: Mean daily return difference (bps), pre-holiday days minus other days.
- null: Equal means. Studentized block bootstrap (block 10) of the day-flagged series.
- procedure: Holidays come from a rule-based NYSE schedule (an explicit list of the holiday rules plus the unscheduled-closure exclusion list). Halves 2000-2012 / 2013-2026. The other 6 variants are Holm-adjusted secondary trials.
- data: daily-history-IWM, daily-history--RUT, daily-history-SPY (stored); FXI, EWY, INDA via Yahoo. · min n: 200
- pass: Difference > 10 bps with p < 0.05 and both halves positive.
- controls: Look-ahead: inferring holidays from missing bars would include unscheduled closures nobody knew in advance; the rule-based schedule avoids that. Survivorship: n/a. Costs: 10 round trips/yr at 1-2 bps. Multiple testing: 1 primary plus 6 Holm. Regime: halves; SPY expected null.
- note: from the underlying-library library: Pre-holiday and holiday-week effects; harness suggestion: events.py: holidays_from_gaps(days) -> set of pre-holiday day indexes (weekday with missing bar); event_day_effect(days, closes, pre_holiday_days); loop over IWM, SPY, country ETFs. | verifier: corrected claim/trial

### T-357 · presidential-cycle

**Claim.** Over 1928-2026, the S&P 500's price return in pre-election years (year 3 of the presidential term) exceeds the mean annual return of the other three years by at least 5 percentage points, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w23184, https://pwlcapital.com/?p=5381
- statistic: Mean year-3 annual return minus mean annual return of other years (pp).
- null: Equal means. Permute the cycle label within each 4-year block (preserving year-to-year dependence), 10,000 draws.
- procedure: Annual returns from ^GSPC daily closes, price only. Halves 1928-1976 / 1977-2026; 1990-2026 reported separately. The party variant uses inauguration dates. 6 variants; the year-3 test is the single pre-registered one.
- data: daily-history--GSPC (stored, 1927-12-30-; social.yahoo_history with period1=0 truncates to 1970, so re-fetch with a negative period1); SPY, IWM, TLT, GLD (stored); Polymarket election markets (stored). · min n: 20
- pass: Year-3 excess > 5 pp with permutation p < 0.05 and both halves positive.
- controls: Look-ahead: none. Survivorship: n/a. Costs: one trade per 4 years. Multiple testing: 6 variants, 1 pre-registered. Regime: halves, and the post-Almanac 1990-2026 period separately; dividends excluded (flagged).
- note: from the underlying-library library: Presidential election cycle and party-in-power effects; harness suggestion: events.py: cycle_year_effect(days, closes, anchor_year=1928, period=4, target=3) with within-block label permutation; party_effect(days, closes, terms) for the inauguration-based split. | verifier: corrected claim/trial

### T-358 · binary-event-uncertainty-premium

**Claim.** Over 2020-2026, across scheduled market-relevant binary events listed on Polymarket or Kalshi, SPY's return over the two trading days into resolution increases with the contracts' ex-ante uncertainty p(1-p) measured three trading days before; the regression slope is positive with p < 0.05.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w25817, https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/how-much-do-investors-care-about-macroeconomic-risk-evidence-from-scheduled-economic-announcements/C6A48B33065D93550C87FEB53C029A0B
- statistic: OLS slope of the 2-day pre-event SPY return on U, with events sharing a date averaged into one observation.
- null: Zero slope. Bootstrap clustered by event date. Placebo: each date's U assigned to a random non-event 2-day window.
- procedure: Freeze the tagging rule and record the event list before any SPY read. p comes from the daily price 3 trading days before the scheduled end date (available_at respected). Halves 2020-2022 / 2023-2026. 6 variants Holm.
- data: Stored Polymarket closed markets and daily price history; Kalshi /historical/markets plus historical candles for KXCPI, KXFEDDECISION, KXPAYROLLS (to be fetched; route verified); daily-history-SPY, TLT, GLD, BTC-USD (stored). · min n: 60
- pass: Slope > 0 with clustered p < 0.05, the same sign in both halves, and placebo slope indistinguishable from 0; min_n counts distinct event dates.
- controls: Look-ahead: p taken 3 days before the scheduled end date; end dates can be edited on Polymarket (hasReviewedDates), so markets whose end date moved after the event are flagged; tagging frozen first. Survivorship: resolved markets only; voided markets counted. Costs: 1-2 bps per SPY round trip. Multiple testing: 6 variants Holm. Regime: halves; 2020 and the 2022 hiking cycle flagged.
- note: from the underlying-library library: Scheduled binary-event uncertainty premium in SPY, scaled by prediction-market odds; harness suggestion: experiments/markets.py: tag_scheduled_events(markets, categories, min_volume) -> list of (event_date, p_minus_3d); events.py: event_window_regression(days, closes, events, window=2) with date-clustered bootstrap and the U-shuffle placebo. | verifier: corrected claim/trial

### T-359 · prediction-market-resolution-date-effects

**Claim.** Across Mandel's resolved Polymarket markets, buying the leading side priced between 0.90 and 0.98 within the final three days before the scheduled end date earns a positive mean return per dollar after a 1-cent spread and any market fee.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://people.duke.edu/~clemen/bio/Published%20Papers/45.PredictionMarkets-Page&Clemen-EJ-2013.pdf, https://www.karlwhelan.com/Papers/Kalshi.pdf
- statistic: Mean net return per dollar = (1{win} - cost) / cost, with cost = p + 0.01 + fee, pooled; calibration slope of outcome on price in the final 3 days.
- null: Prices calibrated. Parametric bootstrap with outcomes drawn as Bernoulli(p) per market; market-cluster bootstrap for realized returns.
- procedure: For each resolved market, take the daily price at end_date minus 1, 2 and 3 days (one entry per market: the first qualifying day). Day-14 entry on the same markets is the horizon contrast. Exclude 50-50/void resolutions and count them. Halves by resolution date. 6 variants plus categories (Bonferroni).
- data: Stored polymarket-closed-markets (2,100) and polymarket-price-history-daily; Kalshi /historical/markets plus candles (route verified) for the Kalshi arm; order-book snapshots for a spread sanity check. · min n: 400
- pass: Mean net return > 0 with cluster-bootstrap p < 0.05, calibration slope > 1, both halves agreeing, and beating the day-14 entry.
- controls: Look-ahead: prices taken before the scheduled end date; Polymarket end dates can be edited (hasReviewedDates), so edited markets are flagged and excluded in a sensitivity. Survivorship: resolved only; voids counted. Costs: spread, fee fields, and capital locked during UMA disputes. Multiple testing: 6 variants plus categories. Regime: halves; sports dominance of recent volume reported.
- note: from the underlying-library library: Prediction-market resolution-date effects (favorite drift into expiry, post-outcome gap, known vs open-ended dates); harness suggestion: experiments/markets.py: late_favorite_returns(markets, histories, days_before=(1,2,3), p_lo=0.90, p_hi=0.98, spread=0.01) with Bernoulli(p) parametric bootstrap and market-cluster bootstrap; horizon contrast at day -14; post_outcome_gap(markets) using end_date vs resolved_at. | verifier: corrected claim/trial

### T-360 · kalshi-macro-settlement-convergence

**Claim.** Over 2021-07 to 2026 CPI releases, buying the Kalshi KXCPI threshold side whose Cleveland Fed nowcast-implied probability exceeds its day-before ask by more than 10 percentage points earns a positive mean net return per contract after Kalshi fees.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.karlwhelan.com/Papers/Kalshi.pdf, https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
- statistic: Mean net P&L per contract (cents), averaged per release first (release = cluster); secondary: hit rate minus mean entry price.
- null: Prices calibrated, so expected net P&L is zero or negative. Parametric bootstrap with outcomes drawn as Bernoulli(mid price) per contract, clustered by release; plus a release-level block bootstrap of realized P&L.
- procedure: Align Kalshi candles to the 16:00 ET bar before release (available_at). Take the nowcast vintage dated that day from the JSON. sigma comes from prior releases only. Settle on the BLS print as resolved by Kalshi. Halves 2021-2023 / 2024-2026. 5 variants Holm.
- data: Cleveland Fed nowcast_month.json (verified: daily vintages since 2013-07); Kalshi historical KXCPI markets and candles (verified routes); BLS release timestamps via Kalshi close_time. · min n: 40
- pass: Mean net P&L > 0 with cluster-bootstrap p < 0.05 and both halves positive, Holm over 5; min_n counts releases with at least one qualifying trade.
- controls: Look-ahead: the archive vintage is assumed to be real-time and not re-estimated after model changes (unconfirmed; test by snapshotting the JSON daily from now and comparing future vintages); sigma uses past releases only. Survivorship: all releases included. Costs: Kalshi fee formula plus spreads of 2-5c in thin thresholds. Multiple testing: 5 variants. Regime: 2021-2023 high-inflation vs 2024-2026; the delayed autumn-2025 releases flagged.
- note: from the underlying-library library: Kalshi macro-contract settlement convergence vs nowcasts; harness suggestion: data/fetch.py: cleveland_nowcast() daily snapshot stored with available_at (start accumulating now); experiments/markets.py: kalshi_bucket_calibration(markets, candles, release_dates) which runs today without the nowcast (variant 5) and gains the nowcast join later. | verifier: corrected claim/trial

### T-365 · liquid-staking-token-discount-carry

**Claim.** From 2023-04-12 to 2026-09-30, buying stETH at the Yahoo daily close after two consecutive days of discount above 1.5% to ETH, and holding 10 days, earns a mean stETH-over-ETH log return above the 30 bp round-trip cost.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://blog.lido.fi/ethereum-withdrawals-overview-faq/, https://fortune.com/2022/06/29/crypto-winter-crash-nansen-three-arrows-capital-celsius-ether-staked-depeg
- statistic: Mean 10-day log return of stETH/ETH after entry, net of 30 bp, per non-overlapping episode.
- null: Mean net relative return <= 0 (the discount is a random walk over 10 days).
- procedure: Define episodes on trailing data only. Bootstrap over episodes (2,000 draws). Shuffled-increment null for the ratio. Report the pre-Shapella regime separately (not pooled).
- data: daily-history-STETH-USD, daily-history-ETH-USD; coinbase-daily-CBETH-ETH for the cbETH variant. · min n: 15
- pass: Lower 90% CI of the mean net return > 0 with at least 15 non-overlapping post-Shapella episodes. With fewer than 15 episodes, record 'insufficient events' (the expected outcome) rather than a verdict. DSR with n_trials = 4.
- controls: Yahoo stETH is a composite exchange price, not the Curve pool, so the two-day confirmation filters glitches. Costs: 30 bp plus gas. Survivorship: none. Look-ahead: none (close-to-close). Regime: pre/post Shapella and the 2025 exit-queue episode reported. 4 trials.
- note: from the underlying-library library: Liquid-staking-token discount carry (stETH / cbETH); harness suggestion: mandel/experiments/carry.py: discount_episodes(ratio_series, threshold, horizon) | verifier: corrected claim/trial

### T-366 · staking-yield-carry

**Claim.** From 2023-04-12 to 2026-09-30, the Coinbase CBETH-ETH market price ratio rises at an annualized rate between 1.5% and 3.5%, the range of the net staking yield after Coinbase's commission, with the HAC 95% CI excluding zero.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://thebigwhale.io/tokens/coinbase-wrapped-staked-eth, https://www.stakingrewards.com/defi/0xbe9895146f7af43049ca1c1ae358b0541ea49704
- statistic: Annualized OLS slope of log(CBETH-ETH) on time, with Newey-West (HAC) standard errors. Also reported: the share of rolling 252-day windows with a positive slope.
- null: Slope <= 0 (no pass-through).
- procedure: Daily Coinbase CBETH-ETH closes after the Shapella upgrade. HAC lag 30. Rolling-window sign test. Compare the slope with the published net APY path.
- data: New bundle coinbase-daily-CBETH-ETH; daily-history-CBETH-USD and ETH-USD for robustness. · min n: 900
- pass: Slope in [1.5%, 3.5%] with HAC 95% CI excluding 0. A slope below 1.5% means the market discount ate the yield and fails the claim.
- controls: Discount noise handled by using the full-sample slope, not endpoints. Look-ahead: none. Survivorship: none. Costs: one round trip of about 30-50 bp amortized over the holding period. Single trial plus 1 robustness check.
- note: from the underlying-library library: Proof-of-stake staking yield as carry; harness suggestion: mandel/experiments/carry.py: ratio_drift(a, b) with HAC SE | verifier: corrected claim/trial

### T-367 · stablecoin-defi-yield-carry

**Claim.** From February 2023 to September 2026, the TVL-weighted mean spread of the 7-day base APY of US-accessible Ethereum USDC lending pools (Aave v3, Spark, Maple) over DTB3 is below the 1.5% smart-contract risk charge, so DeFi stablecoin lending is not a positive carry over T-bills after that charge.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://yields.llama.fi/pools, https://www.legistorm.com/reports/view/crs/608234/The_Stablecoin_Yield_Debate.html
- statistic: TVL-weighted mean daily spread (APY - DTB3) with its 95% CI. Also reported: the share of days with APY > DTB3, the 10th percentile of the spread, and its correlation with the trailing 90-day ETH return.
- null: Mean spread >= 1.5% (positive carry after the risk charge).
- procedure: Daily yields.llama.fi/chart/<pool> apyBase and tvlUsd for the pre-registered pool IDs, aligned with fred-DTB3 (bond-equivalent). Block bootstrap (block 30 days, 5,000 draws). Report by ETH up/down quarter.
- data: New bundle defillama-yields (pools + chart, reachable), fred-DTB3, daily-history-ETH-USD. · min n: 900
- pass: Bootstrap 95% upper bound of the mean spread < 1.5%: claim supported (no carry). A venue whose own lower bound is above 1.5% is recorded as a venue-specific carry, and counted as a trial.
- controls: Posted APY is not realized APY (bad debt, utilization spikes); use base APY only, no token rewards. Survivorship: the /pools endpoint lists current pools, so fix pool IDs from a dated snapshot and note that dead pools may be missing. Look-ahead: APY known at the timestamp. Costs: gas $1-10 per move. Multiple testing: 5 trials. US-access filter applied per venue.
- note: from the underlying-library library: Stablecoin and tokenized-treasury yield as carry (US access); harness suggestion: mandel/data/social.py: defillama_yields(pool_ids) into store; mandel/experiments/carry.py: spread_over_rf() | verifier: corrected claim/trial

### T-370 · metals-cash-and-carry-basis

**Claim.** From 2005 to September 2026, the annualized gold futures implied financing rate (GC=F vs GLD-implied spot, excluding roll weeks) minus DTB3 has a mean within plus or minus 50 bp, so a GLD-long/GC-short lender earns no excess return over T-bills before GLD's 40 bp fee.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.kitco.com/opinion/2026-04-23/londons-silver-running-out-room, https://finance.yahoo.com/news/exclusion-trumps-tariffs-reduces-premium-171033042.html
- statistic: Mean of the daily (i - DTB3), with a HAC 95% CI. Also reported: its SD and the share of days with i < 0.
- null: |mean(i - DTB3)| > 50 bp (a carry exists in either direction).
- procedure: Daily from 2005-01: compute i per the rule, drop roll windows, HAC (lag 21) CI. Robustness: use GLD NAV (LBMA PM-based) instead of the GLD close. Run the silver/platinum/copper variants separately.
- data: daily-history-GC=F, SI=F, PL=F, PA=F, HG=F, GLD, SLV, PPLT, PALL, CPER (to add); fred-DTB3. · min n: 4000
- pass: HAC 95% CI of the mean deviation lies inside [-50, +50] bp. Each other metal is a separate trial with the same criterion; 6 trials counted.
- controls: Asynchrony: GLD closes at 16:00 ET while the Yahoo GC=F close may be the 17:00 ET session end. This adds noise but no bias to the mean; check with GLD NAV. The roll date of Yahoo's continuous series is undocumented: windows dropped. GLD premium/discount to NAV. First notice and delivery not modeled. Costs: futures $2-5 per contract, GLD 40 bp a year. Survivorship: none. Regime: pre/post 2020 and the 2024-25 tariff EFP episode reported.
- note: from the underlying-library library: Metals cash-and-carry and implied lease rate (GC, SI); harness suggestion: mandel/experiments/carry.py: implied_financing(fut, spot, rf); metals bundles GC=F, SI=F, PL=F, PA=F, HG=F added to daily-history | verifier: corrected claim/trial

### T-372 · equity-index-futures-basis

**Claim.** From 2010 to September 2026, the ES-implied financing rate (ES=F vs ^GSPC, with prior-year SPY dividends as the dividend forecast, measured on days 5-60 after each roll) exceeds DTB3 by more than 20 bp on average.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.nber.org/papers/w26773, https://query1.finance.yahoo.com/v8/finance/chart/ES=F
- statistic: Mean (r_imp - DTB3) with Newey-West CI (lag 21), plus a quarter-clustered bootstrap.
- null: Mean spread <= 20 bp.
- procedure: Daily per the rule. Robustness: realized dividends (ex-post) instead of forecast. Report ZIRP (2010-2015, 2020-2021) vs positive-rate regimes. Variants run separately.
- data: daily-history-ES=F (from 2000), ^GSPC, SPY with events=div, NQ=F, ^NDX, QQQ dividends; fred-DTB3. Listed contracts (ESZ26.CME from 2021-09) for cross-checking the continuous series. · min n: 2500
- pass: Lower 95% bound of the mean spread > 20 bp under both the HAC and the clustered bootstrap; 5 trials counted.
- controls: Look-ahead: dividend forecast from the prior year (no realized dividends in the base test). Continuous-contract roll: only days 5-60 after the roll. ES=F daily close may be the 17:00 ET session end vs the index at 16:00 ET: also run on the 16:00 settle where available and report the difference. Costs: ES $2-4 round trip, SPY 1 bp. Survivorship: none. Regime: ZIRP vs post-2022, quarter-ends.
- note: from the underlying-library library: Equity index futures basis (implied financing) as lender/borrower; harness suggestion: mandel/experiments/carry.py: implied_financing(fut, spot, rf, dividends) shared with metals; add ES=F, NQ=F to bundles and SPY dividends via events=div | verifier: corrected claim/trial

### T-373 · treasury-curve-carry-rolldown

**Claim.** From August 2002 (TLT inception) to September 2026, holding TLT only in months when 20-year carry plus roll-down (FRED DGS20, DGS10, DTB3) is positive earns a higher Sharpe than buy-and-hold TLT, and the difference is significant in the 2014-2026 test window.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.cxoadvisory.com/big-ideas/unified-carry-trade-theory/, https://www.aqr.com/Insights/Research/Journal-Article/Carry
- statistic: Sharpe difference (timed minus buy-and-hold) on monthly excess returns.
- null: Sharpe difference <= 0.
- procedure: Monthly signal from month-end FRED yields (published same day; trade next open). TLT total return from Yahoo adjusted close. Paired block bootstrap (block 12 months, 5,000 draws). Walk-forward: no fitted parameters; the 2002-2013 window is reported as in-sample and 2014-2026 is the test.
- data: daily-history-TLT, IEF, IEI, SHY, SGOV, BIL; fred DGS20, DGS10, DGS7, DGS5, DGS2, DTB3. · min n: 280
- pass: Test-window Sharpe difference > 0.15 with bootstrap p < 0.05, and DSR > 0.95 with n_trials = 4.
- controls: FRED constant-maturity par yields only approximate TLT's roll-down. TLT expense ratio 15 bp. Costs 2 bp per switch. Survivorship: none. Look-ahead: month-end yields used for next-month positions. Regime: ZIRP, 2022 hikes. 4 trials.
- note: from the underlying-library library: Treasury curve carry and roll-down; harness suggestion: mandel/experiments/carry.py: bond_carry_timing() reusing turn_of_month bootstrap utilities | verifier: corrected claim/trial

### T-374 · dividend-capture

**Claim.** For current S&P 500 dividend payers from 2010 to September 2026, the mean market-adjusted return from month start to the day before the predicted ex-dividend date exceeds the same firms' mean market-adjusted return over the same span in non-dividend months by at least 20 bp.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.cxoadvisory.com/fundamental-valuation/successfully-exploiting-the-ex-dividend-effect/, https://alphaarchitect.com/2011/10/dividends-can-pay-without-paying
- statistic: Firm-clustered mean difference in market-adjusted (vs SPY) returns, dividend vs non-dividend firm-months.
- null: Difference <= 0.
- procedure: Yahoo chart with events=div per ticker gives ex-dates and amounts. Predicted months from the prior year. Firm- and month-clustered bootstrap (2,000 draws). Split 2010-2017 / 2018-2026. ETF-only robustness.
- data: daily-history-<ticker> with dividends for about 400 current S&P 500 payers, plus SPY/VYM/SCHD/SDY/DVY (to add; Yahoo rate-limits, so throttle about 4 s per call). · min n: 5000
- pass: Difference >= 20 bp with clustered p < 0.01 in both halves, holding on the ETF-only robustness. DSR with n_trials = 4.
- controls: Survivorship: the current-constituent universe biases upward; the claim stands only if the ETF robustness agrees. Market adjustment with SPY. Look-ahead: predicted schedule from prior-year ex-dates only. Costs 5 bp. Tax: holdings under 61 days make dividends non-qualified (noted, not modeled). 4 trials.
- note: from the underlying-library library: Dividend capture and the dividend-month premium; harness suggestion: mandel/experiments/carry.py: dividend_month_premium(prices, dividends) and ex_day_drop(); Yahoo dividend events into the observation store | verifier: corrected claim/trial

### T-375 · securities-lending-yield

**Claim.** From May 2020 to September 2026, stocks in the top decile of FINRA days-to-cover underperform the bottom decile by more than 0.83% per month (half of a 20% annual borrow fee, the lender's share) over the following month.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.interactivebrokers.com/en/pricing/stock-yield-enhancement-program.php, https://robinhood.com/us/en/support/articles/stock-lending/
- statistic: Mean monthly (bottom - top) decile return minus 0.83%, Newey-West t-stat.
- null: Underperformance <= 0.83% per month (buying to lend breaks even or better).
- procedure: FINRA consolidated short interest (api.finra.org, POST query, verified; data from 2020-04). Portfolios formed on each publication date (about 7 business days after settlement; available_at = publication). Next-period returns from Yahoo daily prices, value- and equal-weighted. Block bootstrap by period.
- data: New bundle finra-short-interest (reachable, 2020-04 onward, includes daysToCoverQuantity); daily-history-<ticker> for all names passing the filters. · min n: 120
- pass: Mean underperformance > 0.83% per month with p < 0.05 in both equal- and value-weighted versions, and the same sign in at least 5 of 7 calendar years. DSR with n_trials = 3.
- controls: Days-to-cover is a proxy for the fee; actual fees need IBKR shortable-stock files captured daily (start now) or paid data. Survivorship: the FINRA file includes later-delisted names, but Yahoo lacks their prices; delisting returns are set to -30% as a sensitivity. Publication lag respected. Costs 10 bp. The 2021 meme squeeze is flagged and reported with and without.
- note: from the underlying-library library: Securities-lending yield on hard-to-borrow stocks; harness suggestion: mandel/data/social.py: finra_short_interest(); mandel/experiments/carry.py: decile_sort(signal, returns) shared with other cross-sectional tests; start daily capture of IBKR usa.txt shortable file | verifier: corrected claim/trial

### T-377 · tbill-ladder-risk-free-leg

**Claim.** From June 2020 to September 2026, SGOV's monthly total return tracks the compounded DTB3 investment yield within 10 bp annualized on average, after its 9 bp fee, with a tracking-difference SD below 20 bp annualized, so SGOV is an adequate stand-in for a bill ladder.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.treasurydirect.gov/marketable-securities/treasury-bills/, https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf
- statistic: Annualized mean and SD of the monthly (SGOV total return - DTB3 accrual) difference.
- null: |Mean difference| >= 10 bp or SD >= 20 bp.
- procedure: Monthly SGOV adjusted-close returns (Yahoo) vs DTB3 converted from discount to investment yield and accrued actual/365. HAC CI.
- data: daily-history-SGOV (from 2020-05-26), BIL, fred-DTB3. · min n: 70
- pass: |Mean| < 10 bp with HAC 95% CI inside +/-15 bp, and SD < 20 bp.
- controls: Discount-to-yield conversion; SGOV holds 0-3 month bills, so the curve-slope difference vs 3-month bills is reported; Yahoo adjusted close assumes reinvestment; day-count. Single trial.
- note: from the underlying-library library: T-bill ladder and cash sweep as the risk-free leg; harness suggestion: mandel/experiments/carry.py: tracking_difference(etf, rf); becomes the shared rf leg for all carry harnesses | verifier: corrected claim/trial

### T-378 · event-contract-near-certain-yes-carry

**Claim.** Across resolved Polymarket and Kalshi binary markets, buying the favorite side at its first observed price in [0.95, 0.99] between 1 and 60 days before resolution earns a mean annualized return, net of venue fees and (on Polymarket) forgone DTB3, above the box rate + 2%.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.karlwhelan.com/Papers/Kalshi.pdf, https://people.duke.edu/~clemen/bio/Published%20Papers/45.PredictionMarkets-Page&Clemen-EJ-2013.pdf
- statistic: Market-level mean annualized net return minus the hurdle. Also reported: calibration gap (realized win rate - price) with Wilson CI, worst-cluster loss, and the share of gross profit from the largest cluster.
- null: Mean net annualized return <= hurdle (equivalently, realized win rate <= price + fee-and-time cost).
- procedure: From polymarket-closed-markets with daily price history and kalshi-settled-markets with candles: one observation per market per horizon bucket, at the first entry into the bin (available_at <= decision time). Payoff at resolution. Cluster bootstrap by event and resolution day (2,000 draws). Variants evaluated separately and deflated.
- data: polymarket-closed-markets, polymarket-price-history-daily (2,100 markets), kalshi-settled-markets, kalshi-candles, fred-DTB3, T-186 box captures when available. · min n: 500
- pass: Bootstrap lower 95% bound of the mean net annualized excess over the hurdle > 0 in the pooled sample, no single event cluster contributing more than half of gross profit, and DSR > 0.95 with n_trials = 12.
- controls: Look-ahead: first entry into the bin, never last; prices point-in-time. Pseudo-replication: one observation per market per bucket. Survivorship: the Polymarket closed set is volume-selected (largest markets), so report Kalshi separately. Fees per venue and category; Kalshi APY credited; disputed or voided markets treated as losses (sensitivity: as refunds). Regime: 2022-2023 vs 2024-2026 and pre/post Polymarket fees. 12 trials.
- note: from the underlying-library library: Event-contract near-certain YES carry (buying 0.95-0.99) and its tail; harness suggestion: extend mandel/experiments/markets.py market_calibration with a price-bin x horizon x side table and net-return accounting; reuse T-47 longshot harness | verifier: corrected claim/trial

### T-381 · cross-asset-carry-composite

**Claim.** From January 2013 to September 2026, the equal-risk composite of the testable carry sleeves (FX, global bonds, equity-country, credit) earns an annualized Sharpe above 0.6 after sleeve-level costs, using trailing-only volatility weights.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.cxoadvisory.com/big-ideas/unified-carry-trade-theory/, https://www.aqr.com/Insights/Research/Journal-Article/Carry
- statistic: Composite annualized Sharpe in the test window. Also reported: diversification gain over the average sleeve and drawdown overlap with NBER recessions.
- null: Composite Sharpe <= 0.6.
- procedure: Run after the sleeve harnesses. Stack monthly sleeve returns and apply trailing 36-month volatility weights. Block bootstrap (block 12 months, 5,000 draws).
- data: Outputs of fx-carry-g10-retail, em-fx-carry, global-government-bond-carry, equity-country-dividend-carry, credit-carry-spread-timing, crypto-cme-cash-and-carry. · min n: 150
- pass: Bootstrap lower 95% bound of the composite Sharpe > 0.6 is not required; the pass is point Sharpe > 0.6 with lower bound > 0.2, and DSR > 0.95 with n_trials = 3 plus every sleeve trial.
- controls: Inherits each sleeve's controls. Trailing-only weights. The DSR counts all sleeve variants as trials. Regime reporting by NBER recession dates (FRED USREC).
- note: from the underlying-library library: Cross-asset carry composite (crypto basis, FX, bonds, commodities, VIX); harness suggestion: mandel/experiments/carry.py: composite(sleeve_returns) with risk parity and DSR over total trials | verifier: corrected claim/trial

### T-391 · insider-cluster-buys

**Claim.** Insider purchase clusters (>= 3 buyers within 30 days), bought at the close after the third filing's acceptance and held 126 trading days, earn a positive mean size-matched abnormal return over 2006-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w16454 (fetched), https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets (fetched)
- statistic: Mean 126-day abnormal return per cluster (size-matched ETF benchmark) with event-month clustered bootstrap; calendar-time FF5 alpha as secondary.
- null: Mean abnormal return <= 0.
- procedure: Ingest SEC Insider Transactions Data Sets (quarterly ZIPs from 2006q1, verified) and EDGAR daily index for the live tail with a User-Agent that contains a contact email (verified: 200 with email, 403 with the repo's current URL-only UA); build clusters; align on acceptance datetime; price with Yahoo; walk-forward by year (no fitted parameters) with a 6-month embargo between clusters of the same issuer.
- data: SEC insider transactions data sets 2006q1-; EDGAR full index; Yahoo adjusted closes; Ken French FF5; shares outstanding from SEC XBRL companyfacts (dei) for size matching. · min n: 1000
- pass: Lower 95% bound of mean abnormal return > 0 AND calendar-time alpha t >= 2.5 over >= 1000 clusters across >= 10 years.
- controls: Look-ahead: acceptance datetime. Survivorship: Yahoo lacks delisted tickers, and small-cap cluster names delist often; flag via SEC CIK/ticker history and apply a -30% delisting return for performance delistings (Shumway) with a sensitivity band. Costs: 10 bp per side plus ADV cap. Multiple testing: 5 variants. Regime: 2008-2009 and 2020 cluster waves; report ex-crisis.
- note: from the underlying-library library: Insider cluster buying (Form 4 open-market purchases); harness suggestion: flow_events.py event-study harness; data/edgar.py for insider data-set ZIPs and daily form.idx; cluster builder with the routine filter. | verifier: corrected claim/trial

### T-392 · 13f-best-ideas-cloning

**Claim.** The equal-weight union of rule-selected concentrated managers' largest active positions, bought at 13F acceptance dates and rebalanced quarterly, has positive FF5+UMD alpha over 2013 Q3 to 2026 Q2.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets (fetched), https://data.sec.gov/submissions/CIK0000320193.json (reachable, 200)
- statistic: Monthly calendar-time portfolio alpha against FF5+UMD (Newey-West t); bootstrap CI on annualized alpha.
- null: Alpha <= 0 after costs and the ~45-day lag.
- procedure: Parse SEC Form 13F data sets (2013q2 onward, verified); apply the manager-selection rule with past filings only; compute active weights; align on acceptance date; compare with the hindsight quarter-end version to quantify the lag haircut.
- data: SEC 13F data sets; EDGAR submissions JSON (acceptance dates); SEC XBRL companyfacts (shares outstanding); Yahoo prices; Ken French factors; GVIP. · min n: 150
- pass: Alpha t >= 2 over >= 150 monthly observations AND positive point estimate in both halves (2013-2019, 2020-2026).
- controls: Look-ahead: acceptance date; manager list by rule, not by today's reputation (naming Berkshire/Baupost/Pershing/Greenlight is selection on known success). Survivorship: delisted holdings flagged. Costs: 5 bp per side, ~100%/yr turnover. Multiple testing: 5 variants. Regime: 2021-2022 crowded-name drawdown.
- note: from the underlying-library library: 13F cloning of concentrated managers' best ideas; harness suggestion: data/edgar.py (13F ZIP ingest, CIK list, acceptance dates) + flow_events.py calendar-time portfolio alpha. | verifier: corrected claim/trial

### T-393 · short-interest-days-to-cover

**Claim.** Among the top 1000 US stocks, the bottom days-to-cover decile outperforms the top decile over the following release period, with a positive mean long-short return after borrow costs over 2017-12 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w21166 (fetched), https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest (reachable, 200; fields verified)
- statistic: Mean per-period long-short return with block-bootstrap CI (block 6 periods); FF5 alpha as secondary; hit rate.
- null: Mean long-short return <= 0.
- procedure: Pull consolidatedShortInterest from the FINRA Query API (verified: data back to settlement 2017-12-29, none before 2017-10; query by settlementDate partitions); align on publication date; price with Yahoo; no fitted parameters; report with and without Jan-Mar 2021.
- data: FINRA Query API consolidatedShortInterest (free, 2017-12-); SEC XBRL shares outstanding; Yahoo adjusted closes; Ken French factors. · min n: 150
- pass: Lower 95% bound > 0 over >= 150 release dates AND alpha t >= 2 AND holds excluding the 2021 squeeze window.
- controls: Look-ahead: publication date, not settlement; shares outstanding point-in-time from filings, not Yahoo's current quoteSummary. Survivorship: universe rebuilt each date from all filers; delisted names flagged. Costs: 1% generic borrow on the short leg (higher for DTC 5-10), 5 bp per side. Multiple testing: 5 variants. Regime: 2021 squeezes; 2022 bear market.
- note: from the underlying-library library: Short interest and days-to-cover cross-section; harness suggestion: data/finra.py (Query API pagination with partition filters: the API refuses global sorts, so query by settlementDate) + cross-sectional decile harness in underlying.py. | verifier: corrected claim/trial

### T-394 · finra-short-volume-ratio

**Claim.** A daily off-exchange short-volume-ratio z-score > 2 predicts a negative mean 5-day abnormal return for S&P 500 stocks after costs over 2019-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://cdn.finra.org/equity/regsho/daily/CNMSshvol20251010.txt (reachable, 200), https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data (fetched)
- statistic: Mean 5-day abnormal return (vs SPY) of events, date-clustered bootstrap; Fama-MacBeth slope of 5-day return on SVR z as secondary.
- null: Mean 5-day abnormal return >= 0.
- procedure: Download CNMS daily files from cdn.finra.org (verified 200 back to 2019-01-02; 2010-2018 files 403; regShoDaily API returns only recent data); z-scores; events; walk-forward by year; gross and net reported.
- data: FINRA CNMS daily short-volume files 2019-01-; Yahoo prices; Wikipedia S&P 500 changes table for membership. · min n: 5000
- pass: Lower... upper 95% bound of mean abnormal return < 0 net of costs over >= 5000 events AND same sign in both halves (2019-2022, 2023-2026); otherwise parked as 'daily SVR not informative'.
- controls: Look-ahead: next-day open. Survivorship: point-in-time membership. Costs: 5 bp per side; daily turnover makes costs decisive. Multiple testing: 4 trials. Regime: 2021 meme period. Definitional: off-exchange only, not total short volume.
- note: from the underlying-library library: FINRA daily short-volume ratio; harness suggestion: data/finra.py daily file loader + the generic cross-sectional event harness; add gross-vs-net reporting since turnover is daily. | verifier: corrected claim/trial

### T-395 · buyback-announcement-drift

**Claim.** Firms announcing open-market repurchase authorisations >= 5% of market cap, bought at the close after the 8-K acceptance and held 12 months, earn a positive mean size-matched abnormal return over 2005-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://efts.sec.gov/LATEST/search-index?q=%22Form%204%22&forms=4 (reachable, 200; efts full-text search works from this host), https://academic.oup.com/rfs/article-abstract/22/4/1693/1570427 (Peyer-Vermaelen; fetched, text truncated)
- statistic: Mean 12-month abnormal return per event (size-matched ETF) with event-month clustered bootstrap; calendar-time FF5 alpha as the primary robustness check (Bradford shows BHARs and alphas can disagree).
- null: Mean abnormal return <= 0.
- procedure: EDGAR full-text search (efts, 200 with email UA, 2001-); regex parse authorisation amounts with a hand-checked sample of 50; align on acceptance; event study; walk-forward by year.
- data: EDGAR efts; SEC XBRL companyfacts (shares); Yahoo prices; Ken French factors; PKW. · min n: 800
- pass: Lower 95% bound > 0 over >= 800 events AND calendar-time FF5 alpha t >= 2 AND positive in both halves (2005-2015, 2016-2026).
- controls: Look-ahead: acceptance datetime; shares from prior filing. Survivorship: acquired/delisted firms missing from Yahoo; coverage reported. Costs: 5 bp per side. Multiple testing: 5 variants. Regime: 2008-2009 cancellations; 2023 1% buyback excise tax.
- note: from the underlying-library library: Share buyback announcements and buyback-achiever tilt; harness suggestion: data/edgar.py full-text-search client; flow_events.py; regex parser for authorisation amounts with a manual-check sample of 50. | verifier: corrected claim/trial

### T-398 · fund-flow-dumb-money

**Claim.** The 4-quarter sum of mutual funds' net equity purchases (Fed Z.1) predicts next-4-quarter US market excess returns negatively over 1952-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w11526 (fetched), https://www.ici.org/research/stats/combined_flows (fetched)
- statistic: Predictive regression slope of next-4-quarter market excess return on the flow z-score, Hansen-Hodrick/Newey-West t for overlapping returns plus block bootstrap (block 8 quarters); quintile difference as secondary.
- null: Slope >= 0.
- procedure: FRED quarterly series (latest vintage, ALFRED vintages where available to avoid revision look-ahead); market returns from Ken French Mkt-RF (1926-) and SPY; signal lagged to the release date; walk-forward expanding-window z; horizons 1 and 4 quarters as 2 trials.
- data: FRED BOGZ1FA653064100Q (verified 1946-10 to 2026-04); Ken French market factor; FRED T-bill. ICI combined_flows_data_2026.xls (verified: only 2024- monthly and recent weeks; older year files 404, so no free weekly history). · min n: 250
- pass: Slope t <= -2 with overlapping-return correction over >= 250 quarters AND negative slope in both halves (1952-1989, 1990-2026).
- controls: Look-ahead: release-date lag; Z.1 revisions (prefer vintages). Survivorship: none (aggregate). Costs: quarterly rebalance at 1 bp; leverage financing for 150%. Multiple testing: 4 variants. Regime: 1987, 2008, 2020 flow spikes; report ex-crisis.
- note: from the underlying-library library: Fund-flow momentum and dumb money (aggregate and ETF flows); harness suggestion: data/ici.py (.xls loader via xlrd); predictive-regression harness with overlapping-return correction, reusable by the aggregate-short-interest variant. | verifier: corrected claim/trial

### T-400 · crypto-mvrv-regime

**Claim.** BTC's forward 90-day log return is higher on days when MVRV < 1 than on days when MVRV > 3 over 2011-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=CapMVRVCur (reachable, 200; data verified to 2026-10-13), https://coverage.coinmetrics.io/asset-metrics/CapMVRVCur (fetched; definition page not rendered)
- statistic: Difference in mean forward 90-day log return between regimes; overlapping-observation block bootstrap (block 90 days); number of distinct regime episodes reported as effective n.
- null: Difference <= 0.
- procedure: Fetch CapMVRVCur and BTC-USD; one-day lag; thresholds fixed ex ante; z-score variant walk-forward by cycle (train cycles 1-2, test 3-4); deflated Sharpe and PBO across thresholds.
- data: CoinMetrics community API CapMVRVCur (BTC 2010-07-, ETH); Yahoo BTC-USD (2014-) and CoinMetrics PriceUSD for 2010-2014. · min n: 4
- pass: CI excludes zero AND >= 4 distinct episodes of each regime AND the rule beats buy-and-hold Sharpe in held-out cycles; else 'insufficient independent episodes' (parked, revisit each cycle).
- controls: Look-ahead: one-day lag; store CoinMetrics vintage (realized cap can be restated). Survivorship: none. Costs: 10-60 bp per switch depending on venue. Multiple testing: 4 variants; PBO via CSCV. Regime: halving cycles; post-ETF (2024) structural shift.
- note: from the underlying-library library: Bitcoin MVRV regime (market value to realized value); harness suggestion: data/coinmetrics.py (paged community API); regime-conditional forward-return harness in underlying.py with episode counting; reuse the deflated-Sharpe threshold search from T-58. | verifier: corrected claim/trial

### T-402 · crypto-stablecoin-supply-ratio

**Claim.** The 30-day growth rate of aggregate stablecoin supply predicts BTC's next-30-day log return positively over 2018-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://community-api.coinmetrics.io/v4/catalog/assets?assets=btc (reachable, 200; catalog lists free metrics), Griffin & Shams 2020 JF 'Is Bitcoin Really Untethered?' (not fetched)
- statistic: Predictive regression slope (next-30-day BTC return on 30-day supply growth), weekly non-overlapping sampling, HAC t; daily overlapping version with Hansen-Hodrick as robustness.
- null: Slope <= 0.
- procedure: Fetch SplyCur for listed stablecoins and CapMrktCurUSD; weekly sampling; walk-forward by year; with/without 2022-05 and 2023-03.
- data: CoinMetrics community API (SplyCur verified for usdt/usdc/dai/busd/tusd); Yahoo BTC-USD. · min n: 400
- pass: HAC t >= 2 over >= 400 weekly observations AND positive slope in both halves (2018-2021, 2022-2026).
- controls: Look-ahead: one-day lag. Survivorship: include defunct BUSD/TUSD; UST missing from the free API (note bias). Costs: weekly 10 bp. Multiple testing: 3 variants. Regime: UST collapse and USDC depeg outliers.
- note: from the underlying-library library: Stablecoin supply ratio (dry-powder) for BTC/ETH; harness suggestion: data/coinmetrics.py; predictive-regression harness with HH correction shared with fund-flow entry. | verifier: corrected claim/trial

### T-403 · crypto-hash-ribbons

**Claim.** BTC's forward 90-day log return after a hash-ribbon recovery-with-momentum signal exceeds the unconditional 90-day forward return over 2011-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://api.blockchain.info/charts/hash-rate?timespan=1year&format=json (reachable, 200), https://capriole.com/hash-ribbons/ (not fetched, 403)
- statistic: Difference in mean 90-day forward return (signal vs unconditional) with block bootstrap; signal count (~15-20 expected).
- null: Difference <= 0.
- procedure: Hash rate from blockchain.info charts API (timespan=all) cross-checked with CoinMetrics HashRate (200); crosses; one-day lag; split 2011-2019 (author's in-sample) vs 2019-08-2026 (post-publication).
- data: blockchain.info hash-rate API; CoinMetrics HashRate; Yahoo/CoinMetrics BTC price. · min n: 15
- pass: CI excludes zero over >= 15 signals AND >= 60% of post-publication signals positive.
- controls: Look-ahead: one-day lag, daily estimates only. Survivorship: none. Costs: 10-40 bp per switch. Multiple testing: 4 variants into DSR. Regime: 2021 China mining ban produced a mechanical signal.
- note: from the underlying-library library: Hash ribbons / miner capitulation buy signal; harness suggestion: Event-study variant of the crypto regime harness; the signal is sparse, so report effective n prominently. | verifier: corrected claim/trial

### T-404 · gold-etf-flows-vs-price

**Claim.** The 4-week change in GLD gold holdings predicts the next week's GLD return positively over 2005-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.spdrgoldshares.com/usa/historical-data/ (fetched), https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows (fetched)
- statistic: Predictive regression slope of next-week GLD return on the 4-week flow z (HAC t); contemporaneous slope and two-way Granger tests reported alongside.
- null: Slope <= 0.
- procedure: Parse the SPDR archive XLSX (sheet 'US GLD Historical Archive', column 'Tonnes of Gold'); weekly non-overlapping returns; walk-forward by year.
- data: SPDR GLD historical archive (api.spdrgoldshares.com historical-archive, XLSX, 2004-11-18-); WGC ETF flows (page fetched); Yahoo GLD/IAU/SLV. · min n: 1000
- pass: HAC t >= 2 over >= 1000 weeks AND positive slope in both halves (2005-2015, 2016-2026); otherwise parked as 'flows follow price'.
- controls: Look-ahead: holdings published after the close; use t+1 availability. Survivorship: none. Costs: GLD 0.40% fee (GLDM 0.10%), 1 bp spread. Multiple testing: 5 variants. Regime: 2013 outflows, 2020 inflow surge, 2022-2026 central-bank-led rally; real-yield control (FRED DFII10).
- note: from the underlying-library library: Gold ETF flows vs gold price (GLD tonnes, WGC flows); harness suggestion: data/gold.py (SPDR archive + WGC Excel); predictive-regression harness; Granger test utility. | verifier: corrected claim/trial

### T-405 · gold-silver-cot-positioning

**Claim.** Weeks with extreme managed-money net long positioning in COMEX gold (z > 2) are followed by lower 4-week GLD returns than weeks with extreme net short positioning (z < -2) over 2006-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm (fetched), https://www.cftc.gov/files/dea/history/fut_disagg_txt_2024.zip (reachable, 200)
- statistic: Difference in mean 4-week forward GLD return (z < -2 weeks minus z > 2 weeks); block bootstrap (block 8 weeks); predictive slope with HAC t as secondary.
- null: Difference <= 0.
- procedure: CFTC disaggregated history (2006-2016 combined file and annual files, verified 200) plus legacy for 1986-; z on trailing 156 weeks to t; release-date alignment; walk-forward by year.
- data: CFTC historical compressed COT files; Yahoo GLD, SLV, GDX, BTC-USD; FRED DFII10 control. · min n: 50
- pass: CI excludes zero with >= 50 extreme weeks of each sign AND slope t <= -2; if either tail has < 50 weeks, report 'insufficient extremes' and park.
- controls: Look-ahead: release date (3-day lag). Survivorship: none. Costs: GLD 1 bp, low turnover. Multiple testing: 5 variants; threshold fixed at 2. Regime: real yields (DFII10) as control; 2013 and 2020 regimes.
- note: from the underlying-library library: Gold and silver COT positioning extremes; harness suggestion: data/cftc.py (annual zip loader, contract code mapping: gold 088691, silver 084691, BTC 133741); regime-conditional forward-return harness with release-date alignment. | verifier: corrected claim/trial

### T-408 · pm-hourly-reversal

**Claim.** On Kalshi, fading 3-hour YES-mid moves of at least 5 cents (buying the side that fell, at the ask, and holding 3 hours) earns a positive mean net return per trade after the taker fee.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://docs.kalshi.com/api-reference/market/get-market-candlesticks, https://docs.kalshi.com/api-reference/market/get-trades (public trades: taker_outcome_side, yes_price_dollars, count_fp, created_time, cursor pagination)
- statistic: Mean net return per trade in cents for the headline cell. Annualised Sharpe of hourly P&L. Deflated Sharpe of the best cell. CSCV PBO over the 108 cells.
- null: Mean net return <= 0, i.e. hourly mid changes are a martingale after costs (stationary block bootstrap of hourly mid changes within market, 24h blocks, 2,000 draws).
- procedure: Declare the 108-cell grid. Compute P&L per market. Walk forward by market open date, with a 7-day embargo. Get the bootstrap p-value. Compute PBO over the cells. Then replicate on Polymarket with assumed spreads.
- data: Kalshi settled markets by series_ticker: /markets?status=settled for markets settled after the 2026-08-15 historical cutoff, and /historical/markets plus /historical/markets/{ticker}/candlesticks?period_interval=60 before it (both verified 2026-10-14). Polymarket /prices-history with startTs/endTs windows at fidelity=60 for the 400 largest resolved markets (verified). interval=max with fidelity=60 returns an empty history for resolved markets. · min n: 3000
- pass: On out-of-sample Kalshi markets, bootstrap p < 0.01 for mean net return > 0 in the headline cell, AND PBO < 0.2, AND DSR >= 0.95 over the 108 cells (plus the 21 daily rules). The Polymarket replication has the same sign.
- controls: Look-ahead: the signal uses the mid at candle close; the fill uses the ask at the same close, never the mid. Bid-ask bounce: Kalshi signals only from bid/ask mids. Survivorship: all settled markets, including zero-volume hours (flagged). Costs: Kalshi taker fee 0.07 x C x P(1-P); Polymarket fee formula by category plus the assumed half-spread. Multiple testing: 108 cells plus the 21 daily rules. Regime: by category and hours-to-resolution; 2024 vs 2025-26.
- note: from the underlying-library library: Hourly anti-persistence (intraday mean reversion) on Kalshi/Polymarket prices; harness suggestion: New mandel/experiments/intraday_pm.py: reuse kalshi_candles(period=60) rows from the store and polymarket_price_history(fidelity=60); P&L builder patterned on ma_rule_returns in mandel/experiments/underlying.py; pbo_cscv from mandel/experiments/overfit.py; deflated_sharpe_ratio and block_bootstrap_pvalue from mandel/validation/backtest_eval.py. | verifier: corrected claim/trial

### T-409 · kalshi-polymarket-leadlag

**Claim.** On paired Kalshi/Polymarket markets, buying the lagging venue in the direction of the higher-volume venue's last-hour mid change of at least 3 cents earns a positive mean net return over the next hour after both venues' fees and spreads.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://docs.polymarket.com/developers/CLOB/timeseries, https://docs.kalshi.com/api-reference/market/get-market-candlesticks
- statistic: Mean net return per follow trade, in cents. Diagnostics: Hasbrouck information share and Granger F-tests in both directions per pair.
- null: Mean net return <= 0: the follower's next-hour change is independent of the leader's lagged change (pairs bootstrap, resampling whole pairs).
- procedure: Freeze the pairs table and fee model before touching prices. Calibrate on the first half of pairs by start date and test on the second. Use market-clustered standard errors. DSR and PBO over the 32 cells.
- data: Polymarket /prices-history with startTs/endTs at fidelity=60; Kalshi live and /historical candlesticks at period 60 (both verified 2026-10-14); a hand-built pairs.json with rule checks. · min n: 40
- pass: At least 40 pairs with >= 200 overlapping hours and >= 300 follow trades in total. Out-of-sample mean net return > 0 with pairs-bootstrap 95% CI excluding zero. DSR >= 0.95 over the 32 cells.
- controls: Look-ahead: strictly lagged leader change, both series stamped at candle end. Survivorship: rule-mismatched and differently resolved pairs are kept. Costs: both fee formulas, the Kalshi quoted spread, and an assumed Polymarket spread from captured books. The arbitrage variant carries capital lock-up at the T-bill rate. Multiple testing: 32 cells. Regime: 2024 election vs 2025-26; low-volume pairs separately.
- note: from the underlying-library library: Kalshi vs Polymarket price-discovery lead-lag; harness suggestion: New mandel/experiments/venues_leadlag.py with a pairs.json registry; re-use polymarket_price_history and kalshi_candles from mandel/data/fetch.py; implement Hasbrouck information share (VECM via numpy OLS) and Granger F; P&L with the cost inputs already used by bundle_arb_scan. | verifier: corrected claim/trial

### T-411 · clob-market-making

**Claim.** On Kalshi, quoting both sides at the touch with the four pull rules, filled only on trade-through prints, earns a positive mean daily net P&L per market-day (spread capture minus 60-minute markout minus maker fees), excluding any rewards or rebates.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://help.polymarket.com/en/articles/13364466-liquidity-rewards (max spread, min size, two-sided rule below $0.10, daily payout threshold $1), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1080/14697680701381228 (Avellaneda and Stoikov 2008, High-frequency trading in a limit order book)
- statistic: Mean daily net P&L per market-day. Per fill, realised spread = 2 x s x (fill price - mid_{t+60m}), where s = +1 when the maker sold (taker bought) and -1 when the maker bought. Sharpe of daily P&L.
- null: Mean daily net P&L <= 0: fills are fully adversely selected.
- procedure: Stage 1: replay on Kalshi settled markets using hourly yes_bid/yes_ask candles and public trade prints. Block bootstrap of daily P&L by market. Walk forward on parameters (first half of markets by open date). DSR over 27 cells. Stage 2, before capital: live paper quoting with real fills, comparing realised fills to the replay fill rule. Stage 3: Polymarket, once books are captured.
- data: Kalshi /markets/trades and /historical/trades (taker_outcome_side, yes_price_dollars, count_fp, created_time; verified 2026-10-14); live and /historical 60-minute candlesticks; an event calendar from FRED release dates and market metadata. · min n: 1500
- pass: At least 1,500 market-days. Mean daily net P&L > 0 with bootstrap p < 0.01. Positive in each of the 3 largest categories. DSR >= 0.95 over 27 cells. Paper-trading realised spread within 50% of the replay before any capital.
- controls: Look-ahead: quotes come from the candle closed before the trade; markout mids from later candles. Survivorship: include markets that resolved against inventory. Costs: Kalshi maker fees where charged; rewards and rebates excluded from the headline. Multiple testing: 27 cells. Regime: news hours vs quiet hours; near-resolution reported separately.
- note: from the underlying-library library: Passive liquidity provision on Polymarket/Kalshi CLOBs with adverse-selection controls; harness suggestion: Add trade-print capture to mandel/data/fetch.py (Kalshi get-trades with cursor; Polymarket data-api /trades); new mandel/experiments/mm_replay.py with Avellaneda-Stoikov quotes, conservative fill rule, markout computation; score daily P&L with block_bootstrap_pvalue and sharpe_ratio from backtest_eval.py. | verifier: corrected claim/trial

### T-414 · stocktwits-bullish-ratio

**Claim.** The pre-open StockTwits bullish ratio for a symbol predicts the sign of that symbol's open-to-next-open return with accuracy at least 2 points above 50% in the pre-declared follow direction.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.jbankfin.2017.07.002 (Renault 2017, Intraday online investor sentiment and return patterns in the U.S. stock market), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/j.1540-6261.2004.00662.x (Antweiler and Frank 2004, Is All That Talk Just Noise?)
- statistic: Directional accuracy. Daily cross-sectional information coefficient (Spearman of B with forward return) and its t-stat. Net return of the rule.
- null: Accuracy = 50% and IC = 0 (B permuted across days within symbol, 2,000 times).
- procedure: Backfill. Pooled IC with symbol-clustered standard errors. Permutation p-value. All 16 cells deflated. First vs second half of the sample as a stability check.
- data: StockTwits /streams/symbol/{S}.json paged by the max cursor. History reaches about 2025-12-23 (ids under about 630M return empty; checked on NVDA and SPY on 2026-10-14), so about 200 trading days x 14 symbols. Yahoo daily OHLC. · min n: 1200
- pass: At least 1,200 symbol-days. Accuracy >= 52% with permutation p < 0.01 after deflation. IC t > 3. Same sign in both halves.
- controls: Look-ahead: only messages created before 09:00 ET; entry at the 09:30 open. The window is fixed, so the 30-message page cap does not decide coverage. Survivorship: symbol list declared in advance. Costs: 1 bp SPY/QQQ, 5 bps round trip single names. Multiple testing: 16 cells. Regime: earnings days flagged; VIX split.
- note: from the underlying-library library: StockTwits bullish ratio as a directional signal; harness suggestion: Reuse mandel/experiments/social.py daily_closes() and spearman(); add bullish-ratio derivation to mandel/data/social.py from stored messages; gate by capture-day count as social_attention does. | verifier: corrected claim/trial

### T-415 · social-volume-volatility

**Claim.** Abnormal StockTwits message intensity (z > 2) predicts next-day realised volatility beyond lagged realised vol and same-day implied vol, with incremental R^2 >= 2% in a pooled HAR regression.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/j.1540-6261.2004.00662.x (Antweiler and Frank 2004), https://apewisdom.io/api/
- statistic: Coefficient t-stat and incremental R^2 of z_t in RV_{t+1} = a + b1 RV_t + b2 RV_week + b3 RV_month + b4 IV_t + c z_t. Out-of-sample QLIKE gain over HAR+IV.
- null: c = 0, and no out-of-sample QLIKE gain (Diebold-Mariano).
- procedure: Pooled panel with Driscoll-Kraay standard errors. Expanding-window walk-forward with a 5-day embargo for out-of-sample QLIKE. Diebold-Mariano test. All 12 cells deflated.
- data: StockTwits cursor backfill to about 2025-12-23; CBOE VIX, VXN, RVX, VXAPL, VXAZN, VXGOG, GVZ, OVX, VXEEM, VXTLT histories (in store); Deribit DVOL (in store); Yahoo daily OHLC; Coinbase hourly candles. · min n: 1500
- pass: At least 1,500 symbol-days. c t-stat > 3 with incremental R^2 >= 2%. Out-of-sample QLIKE improvement with DM p < 0.05.
- controls: Look-ahead: intensity samples taken before the close; RV from the next day's bars; IV at the same close. Survivorship: symbol list declared. Costs: none for the forecast; overlay costs belong to the options family. Multiple testing: 12 cells. Regime: earnings and FOMC days flagged.
- note: from the underlying-library library: Social message volume predicts next-day realised volatility; harness suggestion: Extend attention_vs_abs_return in mandel/experiments/social.py into a HAR-RV regression with IV from mandel/data/options.py surface summaries; add QLIKE and Diebold-Mariano to mandel/validation/backtest_eval.py. | verifier: corrected claim/trial

### T-416 · fear-greed-extremes

**Claim.** First crossings of F <= 20 predict a BTC 30-day forward log return at least 5 percentage points above the unconditional 30-day mean, after controlling for the trailing 30-day return.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.alternative.me/fng/?limit=0 (full history, verified), mandel/experiments/social.py fear_greed_forward_returns (the 7-day result already recorded)
- statistic: Coefficient on the first-crossing indicator in a regression of 30-day forward log return on the indicator and the trailing 30-day return, over non-overlapping events. Rule Sharpe vs buy-and-hold.
- null: Coefficient <= 0 (stationary block bootstrap with 30-day blocks, 5,000 draws).
- procedure: Event study over the 72 cells, deflated. Subsamples 2018-21 and 2022-26. Power note: with about 30 independent events and BTC's 30-day volatility of about 18%, the minimum detectable effect is about 8 points, so a non-rejection is recorded as underpowered, not as a refutation.
- data: alternative.me FNG history 2018-02-01 to 2026-10-14 (3,174 days, in store); Yahoo BTC-USD and ETH-USD daily. · min n: 30
- pass: At least 30 non-overlapping first-crossing events at H = 30 (the store has 30: 42 crossings, 30 non-overlapping at 30 days, 21 at 60 days). Coefficient >= 5 points with one-sided bootstrap p < 0.05. DSR >= 0.95 over the 72 cells. Same sign in both subsamples.
- controls: Look-ahead: available_at = day + 1 at 00:00 UTC; entry at that day's close. Survivorship: not applicable. Costs: 0.5-1.2% round trip at retail Coinbase/Kraken taker tiers; 0.3-0.5% maker. Multiple testing: 72 cells plus the 7-day trial. Regime: halving-cycle phase; the 2022 drawdown reported separately.
- note: from the underlying-library library: Crypto Fear & Greed extremes at longer horizons; harness suggestion: Extend fear_greed_forward_returns in mandel/experiments/social.py to horizons 30/60/90, first-crossing events, and a trailing-return control; grid into pbo_cscv and deflated_sharpe_ratio; register the 7-day result as trial 1. | verifier: corrected claim/trial

### T-419 · high-volume-return-premium

**Claim.** Across the declared ETF plus BTC/ETH universe, 2005-2026, a top-decile idiosyncratic volume day without a 2-sigma price move predicts a positive 10-day beta-adjusted forward return of at least 50 bps.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/0022-1082.00349 (Gervais, Kaniel, Mingelgrin 2001, The High Volume Return Premium)
- statistic: Mean 10-day beta-adjusted abnormal return of events. Calendar-time portfolio Sharpe with HAC t-stat.
- null: Abnormal return <= 0 (placebo: event dates shifted by random block offsets within asset, 2,000 shifts).
- procedure: Event study with the block-shift placebo. Calendar-time portfolio. Walk forward by date halves. 36 cells into DSR and PBO.
- data: Yahoo daily OHLCV for the declared list; Coinbase daily candles for BTC/ETH. · min n: 800
- pass: At least 800 events. Mean abnormal return >= 50 bps with p < 0.01. Calendar-time net Sharpe > 0.5 after 5 bps round trip. Same sign in the ETF and crypto buckets. DSR >= 0.95.
- controls: Look-ahead: trailing-50-day percentiles only; entry at the next open. Market-wide volume days hit every ETF at once, which inflates the event count; idiosyncratic volume and calendar-time portfolios fix that. Survivorship: the ETF list is 2026 survivors; add dead ETFs where Yahoo keeps history. Costs: 2-10 bps ETFs, 50-100 bps crypto at retail. Multiple testing: 36 cells. Regime: VIX > 30 separately.
- note: from the underlying-library library: High-volume return premium; harness suggestion: Add volume parsing to price_closes-style helpers in mandel/experiments/volatility.py and an event-study function in mandel/experiments/underlying.py; use block-shift placebo via block_bootstrap_pvalue; grid into pbo_cscv. | verifier: corrected claim/trial

### T-420 · volume-conditioned-momentum

**Claim.** In the declared ETF universe, 2007-2026, 6-month momentum conditioned on low turnover earns a top-minus-bottom-tercile spread over the next 3 months at least 1 percentage point per quarter higher than unconditioned 6-month momentum.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, Lee and Swaminathan 2000, Price Momentum and Trading Volume, Journal of Finance 55(5) (DOI 10.1111/0022-1082.00280; publisher page not fetched from this host), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/0022-1082.00349 (Gervais, Kaniel, Mingelgrin 2001)
- statistic: Quarterly spread difference (conditioned minus unconditioned) with HAC t-stat. DSR and PBO over 72 cells.
- null: Spread difference <= 0.
- procedure: Monthly rebalanced overlapping portfolios. Select on 2007-16, test on 2017-26 with a 1-quarter embargo. CSCV PBO. Plain momentum registered as the baseline trial.
- data: Yahoo daily OHLCV aggregated to months for the declared lists. · min n: 200
- pass: At least 200 monthly observations. Out-of-sample spread difference >= 1 point a quarter with p < 0.05. DSR >= 0.95. PBO < 0.3.
- controls: Look-ahead: skip-month convention; turnover from past data only. Survivorship: the ETF list is chosen from survivors (add dead ETFs Yahoo still serves); the crypto top-20 must be point-in-time, not the 2026 ranking. Costs: 5-10 bps per ETF leg, 50-100 bps crypto. Multiple testing: 72 cells. Regime: momentum crashes (2009, 2020) reported.
- note: from the underlying-library library: Volume-conditioned momentum; harness suggestion: Cross-sectional monthly engine in mandel/experiments/underlying.py (new function) reusing _series(); pbo_cscv over the grid and deflated_sharpe_ratio; register plain momentum as the baseline trial. | verifier: corrected claim/trial

### T-424 · btc-leads-altcoins

**Claim.** BTC's lagged 1-hour return positively predicts the next-hour return of the point-in-time top-10 alt basket, and the theta = 1 sigma follow rule earns positive mean net return after 50 bps round-trip costs.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles (granularities 60-86400 s, 300 candles/request, unauthenticated), Ciaian, Rajcaniova, Kancs 2018, Virtual relationships: Short- and long-run evidence from BitCoin and altcoin markets, Journal of International Financial Markets, Institutions and Money 52 (not fetched from this host)
- statistic: Net mean return per trade and net Sharpe of the follow rule. Diagnostics: HAC t-stat of the lagged-BTC coefficient; Granger F.
- null: Net mean <= 0 (stationary block bootstrap of hourly returns, 24h blocks).
- procedure: Coinbase hourly backfill 2019-2026 (300 candles per call; about 210 calls per product-year). Fit theta on 2019-22, test on 2023-26. 14 cells deflated.
- data: Coinbase Exchange public candles (hourly BTC-USD back to 2016 verified); Yahoo daily for the 1d variant. · min n: 20000
- pass: At least 20,000 out-of-sample hourly bars. Net Sharpe > 0.5 with bootstrap p < 0.05. DSR >= 0.95.
- controls: Look-ahead: strictly lagged BTC bar; UTC candle alignment; basket membership from trailing data only. Survivorship: point-in-time listing and ranking, not 2026 survivors. Costs: 50 bps round trip default (Kraken 0.26% and Coinbase retail taker per side); a maker-only variant at 30 bps. Multiple testing: 14 cells. Regime: 2021 bull vs 2022 bear.
- note: from the underlying-library library: Bitcoin leads altcoins (cross-asset lead-lag in crypto); harness suggestion: Add coinbase_candles() backfill to mandel/data/fetch.py; lead-lag regression and follow-rule P&L in a new mandel/experiments/leadlag.py shared with the futures and venue entries; block_bootstrap_pvalue and deflated_sharpe_ratio from backtest_eval.py. | verifier: corrected claim/trial

### T-425 · cross-exchange-btc-discovery

**Claim.** At 1-minute resolution, 2023-2026, the inventory-neutral Coinbase-Kraken BTC-USD arbitrage rule with a threshold of all-in cost plus 10 bps earns positive annual net P&L at the user's actual fee tier.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles, https://api.kraken.com/0/public/OHLC?pair=XBTUSD (verified in SOCIAL-SOURCES.md)
- statistic: Annual net P&L and mean net return per trigger, after both venues' fees, inventory financing and amortised transfer costs. Trigger count per year. Information share.
- null: Net P&L <= 0.
- procedure: Coinbase 1-minute candles (300 per call). Kraken minute bars rebuilt from /0/public/Trades, which pages full history with side and timestamps (verified from 2023-01-01); OHLC returns only the last 720 bars. Conservative fills at the next minute's close. 8 cells deflated.
- data: Coinbase Exchange candles; Kraken public Trades (full history, side b/s); both verified 2026-10-14. · min n: 100000
- pass: At least 100,000 aligned minutes. Net P&L > 0 with bootstrap p < 0.05 at the user's tier. Reported for each tier.
- controls: Look-ahead: execution at the close of the minute after the trigger. Survivorship: not applicable. Costs: Coinbase and Kraken taker/maker by tier; transfer fees; inventory capital. Multiple testing: 8 cells. Regime: volatility spikes (|hourly return| > 3%) vs calm.
- note: from the underlying-library library: Cross-exchange BTC price discovery (Coinbase vs Kraken premium); harness suggestion: coinbase_candles() and kraken_ohlc() in mandel/data/fetch.py; information-share estimator shared across lead-lag entries; arbitrage trigger simulation with fee tiers as inputs in backtest_eval. | verifier: corrected claim/trial

### T-430 · credit-carry-spread-timing

**Claim.** From January 2003 to September 2026, the duration-matched LQD-minus-IEF position held only when BAA10Y exceeds its trailing 60-month median earns a positive annualized excess return with Sharpe above 0.3 after 5 bp per switch.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.aqr.com/Insights/Research/Journal-Article/Carry, https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA10Y
- statistic: Annualized Sharpe of the monthly timed duration-hedged excess return.
- null: Sharpe <= 0.
- procedure: Monthly signal from month-end BAA10Y (published with a 1-day lag; trade the next day). LQD/IEF total returns from Yahoo adjusted closes. Block bootstrap (block 12 months). Report 2003-2012 vs 2013-2026 (post-Koijen).
- data: fred BAA10Y (verified 1986 to 2026-10-09), daily-history-LQD (2002-07), IEF, HYG (2007-04), IEI, SGOV. · min n: 250
- pass: Sharpe > 0.3 with bootstrap lower bound > 0 in 2013-2026, and DSR > 0.95 with n_trials = 4.
- controls: Look-ahead: trailing median only, 1-day publication lag. Duration ratio from published fund durations (fixed ex ante). Costs 5 bp per switch plus expense ratios. Regime: 2008, March 2020 ETF discount dislocation, 2022. Survivorship: none. 4 trials.
- note: from the underlying-library library: Credit carry: corporate spread timing (LQD/HYG vs duration-matched Treasuries); harness suggestion: mandel/experiments/carry.py: spread_timing(signal, long_etf, hedge_etf, hedge_ratio). Add BAA10Y to the FRED list and LQD/HYG/IEF/IEI to daily-history. | added by the verifier pass

### T-432 · equity-country-dividend-carry

**Claim.** From January 2011 to September 2026, a monthly long-top-4 / short-bottom-4 portfolio of US-listed country ETFs ranked by trailing dividend yield minus lagged local 3-month rate earns an annualized Sharpe above 0.3 after 10 bp per trade and 50 bp a year short-borrow cost.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://ideas.repec.org/a/eee/jfinec/v127y2018i2p197-225.html, https://www.aqr.com/Insights/Research/Journal-Article/Carry
- statistic: Annualized net Sharpe of the long-short in the test window.
- null: Net Sharpe <= 0.
- procedure: Monthly formation on month-end data with a one-month rate lag. Walk-forward: 1997-2010 fit (k, weighting), 2011-2026 test. Block bootstrap (block 12 months).
- data: daily-history for the 17 ETFs with events=div (Yahoo, 1996+); FRED IR3TIB01 for AU, CA, SE, EZ (DE/IT/NL/AT/ES/FR via EZ), GB, CH, JP, US (HK, SG, MY, DK to be verified; drop any missing); fred-DTB3. · min n: 150
- pass: Test Sharpe > 0.3 with bootstrap lower bound > 0, and DSR > 0.95 with n_trials = 4.
- controls: Survivorship: fixed 1996 list; any closed ETF kept until its last price. Lumpy (semiannual or annual) distributions smoothed by a trailing 12-month sum. Look-ahead: distributions counted from the ex-date; rates lagged. EZ/GB rate staleness after 2026-01 flagged. Costs 10 bp plus borrow. Regime: 2008, 2020, euro crisis 2011-12. 4 trials.
- note: from the underlying-library library: Equity-country carry (dividend yield minus local rate) via country ETFs; harness suggestion: mandel/experiments/carry.py: cross_sectional_carry() with a carry function equity_carry(div_series, price, local_rate). Add the country ETFs with dividends to daily-history. | added by the verifier pass

### T-433 · global-government-bond-carry

**Claim.** From January 2010 to September 2026, a duration-neutral portfolio long the 3 highest and short the 3 lowest 10-year-minus-3-month carry government bond markets among 10 developed countries earns an approximate FX-hedged annualized Sharpe above 0.3 after 5 bp per trade.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.aqr.com/Insights/Research/Journal-Article/Carry, https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01DEM156N
- statistic: Annualized Sharpe of the approximate hedged long-short excess return.
- null: Sharpe <= 0.
- procedure: Monthly per the rule. Walk-forward: 1990-2009 fit, 2010-2026 test. Block bootstrap (block 12 months). Approximation check: compare the US leg's synthetic return with IEF's actual excess return (correlation > 0.9 required).
- data: FRED IRLTLT01 for the 10 countries (DE and JP verified to 2026-08), IR3TIB01 (EZ and GB stale after 2026-01), fred-DTB3, daily-history-IEF. · min n: 150
- pass: Test Sharpe > 0.3 with bootstrap lower bound > 0, the US synthetic-vs-IEF correlation > 0.9, and DSR > 0.95 with n_trials = 3.
- controls: OECD series are monthly averages, not month-end values, which introduces timing error (both legs lagged one month to avoid look-ahead). The duration approximation misses convexity. Stale EZ/GB 3-month rates flagged. Costs 5 bp. Regime: negative rates 2014-2021, 2022. 3 trials.
- note: from the underlying-library library: Global government bond carry (cross-country, FX-hedged); harness suggestion: mandel/experiments/carry.py: synthetic_bond_returns(y10, duration) plus cross_sectional_carry(). Add the IRLTLT01 series to the FRED list. | added by the verifier pass

### T-442 · treasury-auction-cycle

**Claim.** Over 2002-2026, TLT's mean return from the close of a 10- or 30-year auction day to the close three trading days later exceeds its unconditional mean 3-day return by at least 10 bps, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/oup/rfinst/v26y2013i8p1891-1912.html, https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query
- statistic: Mean 3-day post-auction TLT return minus the unconditional mean 3-day TLT return (bps), per auction-week cluster.
- null: No auction effect. Block bootstrap of the daily series (block 10) with event flags held fixed; placement placebo with clusters moved to random non-auction weeks.
- procedure: Fetch auction dates and merge them into weekly clusters. Halves 2002-2013 / 2014-2026. The DGS10 1990-2026 variant uses yield changes in bps (sign-flipped). 6 variants Holm.
- data: fiscaldata.treasury.gov /v1/accounting/od/auctions_query (keyless, verified; filter security_term 10-Year/30-Year and the 9-Year 11-Month/29-Year 11-Month reopening terms); daily-history-TLT (stored); IEF via Yahoo (2002-07-30, verified); fred-DGS10 (stored). · min n: 200
- pass: Excess > 10 bps with p < 0.05 and both halves positive; placebo not significant.
- controls: Look-ahead: auction schedules are announced in advance and the auction date is known at entry. Survivorship: n/a. Costs: about 24 round trips/yr at 1-2 bps (TLT). Multiple testing: 6 variants Holm. Regime: halves; 2008, the 2020 dash for cash and the 2022 bond bear flagged; overlap with CPI weeks reported.
- note: from the underlying-library library: Treasury auction cycle (pre-auction concession, post-auction recovery); harness suggestion: data/fetch.py: treasury_auctions(terms=('10-Year','30-Year','9-Year 11-Month','29-Year 11-Month')) cached as 'treasury-auctions'; events.py: event_window_effect(days, closes, event_days, start=0, end=3, cluster='week') reusing block_bootstrap_pvalue. | added by the verifier pass

### T-450 · pension-rebalancing-flow

**Claim.** The SPY return over the last 3 trading days of the month plus the first day of the next month is negatively related to the month-to-date SPY-minus-AGG return differential over 2003-10 to 2026-09.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w33554 (fetched; abstract verified)
- statistic: Slope of the 4-day window SPY excess return on the month-to-date differential (HAC t), plus the mean return of the threshold rule with bootstrap CI.
- null: Slope >= 0.
- procedure: Yahoo SPY, AGG adjusted closes; differential known at t-3 close; non-overlapping monthly windows; quarter-end subset; long-history replication using FF daily market and a FRED DGS10 duration proxy.
- data: Yahoo SPY, AGG, TLT; Ken French daily market; FRED DGS10. · min n: 250
- pass: Slope t <= -2 over >= 250 monthly windows AND negative point estimate in both halves (2003-2014, 2015-2026).
- controls: Look-ahead: signal at t-3 close. Survivorship: none. Costs: 2 round trips/month at 1 bp + financing for 150%. Multiple testing: 4 variants. Regime: 2008, 2020, 2022 (stocks and bonds fell together).
- note: from the underlying-library library: Pension and balanced-fund rebalancing flow (month-end); harness suggestion: Extend underlying.py turn_of_month() with a conditioning variable (month-to-date stock-bond differential). | added by the verifier pass

### T-451 · piotroski-fscore-value

**Claim.** Within the top book-to-market quintile, stocks with F-score 8-9 outperform stocks with F-score 0-2 over the 12 months after their 10-K acceptance, over 2011-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://researchworks.creighton.edu/esploro/outputs/journalArticle/Value-Stocks-and-Accounting-Screens-Has/991006117468602656 (fetched), https://data.sec.gov/api/xbrl/frames/us-gaap/NetIncomeLoss/USD/CY2019Q1.json (200)
- statistic: Mean monthly calendar-time long-short return with block-bootstrap CI; FF5 alpha.
- null: Mean <= 0.
- procedure: Build F-scores from XBRL companyfacts (needs two prior years, so from ~2011); staggered entry at acceptance; calendar-time portfolios.
- data: SEC XBRL companyfacts/frames; Yahoo prices; Ken French factors. · min n: 150
- pass: Lower 95% bound > 0 over >= 150 months AND FF5 alpha t >= 2.
- controls: Look-ahead: acceptance date; facts restricted to the filing's own accession. Survivorship: delisted names missing from Yahoo (value-distressed names delist often: strong upward bias; sensitivity with delisting returns). Costs: 10-20 bp per side. Multiple testing: 4 variants. Regime: 2020-2021 junk rally.
- note: from the underlying-library library: Piotroski F-score within value stocks; harness suggestion: data/edgar.py fundamentals mapper (standard tag fallbacks); calendar-time harness in flow_events.py. | added by the verifier pass

### T-452 · pead-xbrl-sue

**Claim.** The top-minus-bottom SUE decile portfolio, formed at the close after each 10-Q/10-K acceptance and held 60 trading days, earns a positive mean return over 2011-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf (fetched; abstract verified), https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json (200 with email UA)
- statistic: Calendar-time monthly long-short return mean with block-bootstrap CI; FF5+UMD alpha (Newey-West).
- null: Mean long-short return <= 0.
- procedure: Pull XBRL companyfacts/frames (from 2009; SUE needs 8 prior seasonal differences, so signals from ~2011); align on acceptance datetime; price with Yahoo; no fitted parameters; size-split variants.
- data: SEC XBRL companyfacts and frames (verified 200 with an email-bearing UA); EDGAR submissions JSON; Yahoo prices; Ken French factors. · min n: 150
- pass: Lower 95% bound > 0 over >= 150 months AND FF5+UMD alpha t >= 2; size-split results reported (Martineau predicts large-cap null).
- controls: Look-ahead: acceptance datetime; XBRL facts filtered to the filing's own accession (no later restatements). Survivorship: Yahoo lacks delisted names; flag and apply delisting-return sensitivity. Costs: 10 bp per side small caps, 3 bp large. Multiple testing: 5 variants. Regime: 2020 earnings dispersion.
- note: from the underlying-library library: Post-earnings-announcement drift (PEAD) from SEC XBRL; harness suggestion: data/edgar.py companyfacts loader keyed by accession with available_at = acceptance; flow_events.py calendar-time portfolios. | added by the verifier pass

### T-458 · consumer-confidence-size-premium

**Claim.** From 1990 to 2026, a top-tercile orthogonalised Michigan sentiment reading predicts a negative 3-month ^RUT-minus-^GSPC return, with an out-of-sample R^2 above zero.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1093/rfs/hhj038 (Lemmon and Portniaguina 2006; metadata resolved), https://fred.stlouisfed.org/graph/fredgraph.csv?id=UMCSENT (fetched)
- statistic: Campbell-Thompson out-of-sample R^2 of the 3-month RUT-GSPC return. Long-short net Sharpe.
- null: Out-of-sample R^2 <= 0 (Clark-West test).
- procedure: Expanding window from 1990, with the orthogonalisation also estimated in the expanding window. 12 cells deflated.
- data: FRED UMCSENT monthly since 1952 (fetched 2026-10-14); FRED UNRATE, CPIAUCSL, DTB3; ^RUT and ^GSPC daily (in store); SPHB/SPLV for the variant. · min n: 400
- pass: At least 400 monthly observations. Out-of-sample R^2 > 0 with Clark-West p < 0.05 after deflation. Net Sharpe of the long-short > 0.3.
- controls: Look-ahead: FRED dates monthly observations at the first of the month, but UMCSENT final values are released near the end of that month. Mandel's FRED rule (observation date + 1 day) would leak about a month, so available_at = first day of the next month (or ALFRED vintages). Survivorship: indices. Costs: 5 bps per leg. Multiple testing: 12 cells. Regime: recessions.
- note: from the underlying-library library: Consumer confidence and the small-minus-large premium; harness suggestion: fred_series in mandel/data/options.py needs per-series release lags (monthly survey series: next month start). Predictive regression in mandel/experiments/underlying2.py with Clark-West. | added by the verifier pass

### T-459 · crypto-trade-flow-imbalance

**Claim.** On Kraken BTC-USD, 2023-2026, a 5-minute signed-volume imbalance above 2 sigma predicts a positive 5-minute forward return large enough that the maker-only follow rule earns positive mean net return.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.kraken.com/0/public/Trades?pair=XBTUSD&since=1672531200000000000 (verified), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/jjfinec/nbt003 (fetched)
- statistic: Mean net return per trade. Diagnostic: forward-return regression slope with HAC t-stat.
- null: Mean net return <= 0 (stationary block bootstrap, 1-day blocks).
- procedure: Rebuild 1-minute bars and signed volume from trades. Fit thresholds on 2023-24, test on 2025-26. 36 cells deflated.
- data: Kraken public Trades (full history, side); Coinbase trades and candles for replication. · min n: 20000
- pass: At least 20,000 out-of-sample trades. Mean net > 0 with p < 0.01. DSR >= 0.95.
- controls: Look-ahead: signal from closed minutes. Maker fills only when a later trade prints through the quote. Survivorship: not applicable. Costs: Kraken maker 0.16%, taker 0.26% at the base tier. Multiple testing: 36 cells. Regime: volatility terciles.
- note: from the underlying-library library: Crypto trade-flow imbalance predicts short-horizon returns; harness suggestion: kraken_trades() in mandel/data/fetch.py. Signed-volume bars plus P&L in a shared mandel/experiments/leadlag.py or crypto_micro.py. | added by the verifier pass

### T-462 · short-term-reversal-liquidity

**Claim.** In the declared ETF universe, 2007-2026, the weekly bottom-minus-top quintile reversal portfolio earns a positive net return after 10 bps per leg, higher when VIX is above its 1-year median.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1093/rfs/hhs066 (Nagel 2012, Evaporating Liquidity; metadata resolved), https://doi.org/10.2307/2937816 (Lehmann 1990; metadata resolved)
- statistic: Weekly long-short net return with HAC t-stat. High-VIX minus low-VIX difference.
- null: Net mean <= 0.
- procedure: Select on 2007-16, test on 2017-26. 18 cells into DSR and PBO.
- data: Yahoo daily for the declared lists; CBOE VIX (in store). · min n: 500
- pass: At least 500 weeks. Out-of-sample net mean > 0 with p < 0.05. DSR >= 0.95.
- controls: Look-ahead: ranks from returns known at formation. Survivorship: as in volume-conditioned-momentum. Costs: 10 bps per ETF leg; 50-100 bps crypto. Multiple testing: 18 cells. Regime: VIX conditioning is the hypothesis; 2008 and 2020 reported.
- note: from the underlying-library library: Short-term reversal as liquidity provision (weekly cross-section); harness suggestion: Shares the cross-sectional engine with volume-conditioned-momentum in mandel/experiments/underlying.py. | added by the verifier pass

### T-463 · pm-trade-flow-imbalance

**Claim.** On Kalshi, buying the side that takers bought on net (|F| > 0.5 over the last hour, at least 20 trades) and holding 6 hours earns a positive mean net return per trade after the taker fee and spread.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://docs.kalshi.com/api-reference/market/get-trades (fetched), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/jjfinec/nbt003 (Cont, Kukanov, Stoikov; abstract fetched)
- statistic: Mean net return per trade. Diagnostic: hit rate.
- null: Mean net return <= 0 (F permuted across hours within market).
- procedure: Kalshi trades and hourly candles. Walk forward by market open date with a 24h embargo. 16 cells into DSR and PBO.
- data: Kalshi /markets/trades and /historical/trades with ticker filter; 60-minute candlesticks (yes_bid/yes_ask); Polymarket data-api trades for the replication. · min n: 3000
- pass: At least 3,000 out-of-sample trades. Mean net > 0 with bootstrap p < 0.01. DSR >= 0.95. PBO < 0.3.
- controls: Look-ahead: flow up to the hour close; fills at the next candle's ask. Survivorship: all settled markets except KXMVE combos. Costs: fee formulas plus quoted spread. Multiple testing: 16 cells plus the book-imbalance grid. Regime: by category; final 48h separately.
- note: from the underlying-library library: Signed trade-flow imbalance on Kalshi/Polymarket; harness suggestion: kalshi_trades() in mandel/data/fetch.py. Flow aggregation and P&L in mandel/experiments/intraday_pm.py next to the hourly-reversal harness, sharing its cost model. | added by the verifier pass

### T-465 · vpin-crypto-volatility

**Claim.** On BTC-USD, 2023-2026, VPIN adds at least 2% incremental R^2 for next-hour realised volatility over a HAR model with lagged realised volatility and volume.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1093/rfs/hhs053 (Easley, Lopez de Prado, O'Hara 2012; metadata resolved), https://api.kraken.com/0/public/Trades (verified)
- statistic: Incremental R^2 and t-stat of VPIN in a HAR-RV model with volume. Out-of-sample QLIKE gain.
- null: VPIN coefficient = 0, and no QLIKE gain (Diebold-Mariano).
- procedure: Expanding-window walk-forward. HAC standard errors. 8 cells deflated.
- data: Kraken public Trades; Coinbase candles for realised vol. · min n: 20000
- pass: At least 20,000 hourly observations. Incremental R^2 >= 2% with t > 3. DM p < 0.05 out of sample.
- controls: Look-ahead: buckets closed before the forecast hour. Survivorship: not applicable. Costs: not applicable for the forecast. Multiple testing: 8 cells. Regime: weekends vs weekdays.
- note: from the underlying-library library: VPIN flow toxicity predicts crypto volatility; harness suggestion: VPIN builder in a crypto microstructure module. HAR and QLIKE shared with social-volume-volatility. | added by the verifier pass

### T-467 · cross-listed-parity-reversion

**Claim.** Pooled over the 10 declared NYSE/TSX pairs on Yahoo 60-minute bars from 2023-11 to 2026-10, the |z| > 2 last-hour parity fade earns a positive mean net return per trade after 3 bps per leg per trade plus 2 bps FX.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1016/j.jfineco.2010.03.005, https://ideas.repec.org/a/eee/jfinec/v97y2010i1p53-80.html
- statistic: pooled mean net return per trade with bootstrap interval clustered by date
- null: mean net return per trade = 0
- procedure: Pull Yahoo 60-minute bars (about 730 days, verified for RY.TO and CAD=X). Align the 15:00-16:00 ET bars. Compute d_t and z. Simulate. Bootstrap. DSR over 4 variants.
- data: Yahoo 60-minute bars for the 20 listings and CAD=X (2023-11 onward); daily closes for longer history are unusable because FX closes are asynchronous · min n: 200
- pass: 95% lower bound of pooled mean net return per trade > 0 AND DSR > 0.95
- controls: Look-ahead: bar closes only; execution at the closing auctions that follow. Synchronicity: a stale FX quote can create fake deviations, so the hourly bar's last FX print is required and a 1-bar-lag FX placebo is run. Costs: 3 bps per leg per trade plus 2 bps FX (Norbert's gambit takes days). Survivorship: current large caps only. Regime: 2024-2026 only (short).
- note: from the underlying-library library: Cross-listed parity reversion (Canadian interlisted stocks NYSE vs TSX); harness suggestion: cross_listed_parity: hourly aligner for equity pairs plus FX, deviation z-rule, FX-lag placebo; shares code with cross_venue_gap | added by the verifier pass

### T-468 · brent-wti-spread-reversion

**Claim.** From 2011-01 to 2026-09, the USO/BNO equal-dollar trade on |z| > 2 of the trailing-250-day Brent-WTI log front-month spread earns a positive mean net return per trade after 5 bps per leg per trade and 50 bps/yr borrow.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.eia.gov/finance/markets/reports_presentations/2012PaperBrentWTI.pdf, https://arxiv.org/abs/1610.03153
- statistic: mean net return per trade with bootstrap interval; diagnostic: AR(1) half-life of s_t by sub-period
- null: mean net return per trade = 0 (block-shifted signal null, block 60)
- procedure: Yahoo BZ=F, CL=F for signals with roll windows masked. USO/BNO adjusted closes for P&L (BNO listed 2010-06). Trailing z. Simulate. Bootstrap. DSR over 3 runnable variants. Report 2011-2014, 2015-2019 (US export ban lifted Dec 2015), 2020-2026.
- data: Yahoo BZ=F (2007-08-), CL=F (2000-09-), USO (2006-), BNO (2010-06-), UGA daily · min n: 20
- pass: 95% lower bound of mean net return per trade > 0 AND at least 20 trades AND same sign in at least 2 of 3 sub-periods
- controls: Maturity mismatch: Brent's front contract expires about a month earlier than WTI's, so the front-front spread mixes delivery months; masked around rolls and checked against the ETF-implied spread. USO and BNO roll differently and USO changed its roll schedule in 2020 (structural break flagged). Negative WTI print 2020-04-20 excluded. Costs: 5 bps/leg plus borrow. Regime: sub-periods. Multiple testing: 3 variants.
- note: from the underlying-library library: Crude oil spread mean reversion (Brent-WTI); harness suggestion: reuse underlying.ratio_reversion with a roll-window mask and ETF P&L legs | added by the verifier pass

### T-470 · dual-class-share-spread

**Claim.** Pooled across the 10 declared dual-class pairs, 2014-2026, the |z| > 2 reversion rule earns a positive mean net return per trade after 5 bps per leg per trade and 50 bps/yr borrow.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1016/j.jfineco.2010.06.007, https://papers.ssrn.com/abstract=1338885
- statistic: pooled mean net return per trade with bootstrap interval clustered by pair-month
- null: mean net return per trade = 0
- procedure: Yahoo adjusted closes. Trailing z only. Simulate per pair, then pool. Bootstrap. DSR over the 5 variants. Per-pair results reported.
- data: Yahoo daily adjusted closes for the 20 tickers · min n: 200
- pass: 95% lower bound of pooled mean net return per trade > 0 AND positive in at least 6 of 10 pairs AND DSR > 0.95
- controls: Look-ahead: trailing windows; next-close execution. Dividends: adjusted closes, since some classes pay different dividends; voting-premium drift (e.g. around GOOG-class buybacks) is absorbed by the trailing mean and reported. Survivorship: pairs that unified or delisted before 2026 are absent from Yahoo; the declared list is current pairs only (biased toward survivors). Costs: 5 bps/leg (25+ bps for thin classes like BF-A, LEN-B, HEI-A). Multiple testing: 5 variants x 10 pairs pooled. Regime: halves.
- note: from the underlying-library library: Dual-class share spread reversion (GOOG/GOOGL, BRK-A/BRK-B and others); harness suggestion: reuse twin_spread_halflife / underlying.ratio_reversion with a share-ratio constant k and a pooled per-trade bootstrap | added by the verifier pass

### T-471 · long-horizon-country-reversal

**Claim.** From 1999-04 to 2026-09, the bottom-minus-top-quartile 36-to-12-month country-ETF reversal portfolio earns a positive mean monthly return after 10 bps per leg per trade and 50 bps/yr borrow.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.1111/0022-1082.00225, https://quantpedia.com/strategies/mean-reversion-effect-in-country-equity-indexes
- statistic: mean monthly net long-short return and Sharpe; DSR over variants
- null: mean monthly net return = 0 (studentized block bootstrap, block 12 months)
- procedure: Signals from trailing adjusted closes only. Overlapping-cohort portfolio. Block bootstrap. DSR and PBO over 4 variants. Report 1999-2012 and 2013-2026.
- data: Yahoo monthly adjusted closes for 21 iShares country ETFs (1996-) · min n: 300
- pass: 95% lower bound of mean monthly net return > 0 AND same sign in both halves AND DSR > 0.95
- controls: Look-ahead: formation ends at t-12 and the trade is at month-end t. Survivorship: none of the 21 ETFs delisted. Overlap: cohorts overlap, so the block length is 12 months. Costs: 10 bps/leg plus borrow; country ETFs have wider spreads (3-15 bps). Low power: about 27 years with a 3-year half-life gives fewer than 10 independent reversion cycles. Multiple testing: 4 variants. Regime: 2008 and 2020.
- note: from the underlying-library library: Long-horizon reversal across country equity ETFs (De Bondt-Thaler / Balvers-Wu-Gilliland); harness suggestion: reuse xs_reversal_walkforward with monthly formation windows and overlapping cohorts | added by the verifier pass

### T-472 · bullion-trust-discount-reversion

**Claim.** From 2012-01 to 2026-09, long PHYS / short GLD opened when PHYS's discount is more than 1 percentage point below its trailing 250-day mean, and closed at that mean or after 60 trading days, earns a positive mean net return per trade after 10 bps per leg per trade and 50 bps/yr GLD borrow.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://sprott.com/investment-strategies/exchange-listed-products/physical-bullion-funds/gold/, https://doi.org/10.2307/2946710
- statistic: mean net return per trade (and per day held) with bootstrap interval; diagnostics: AR(1) half-life of d_t minus its trailing mean, trade count
- null: mean net return per trade = 0 (trades resampled in monthly clusters; block-shift of the signal series as a second null)
- procedure: Scrape Sprott's embedded daily premium/discount series (4,228 points since 2010-02 in the page's Highcharts data). Join PHYS and GLD Yahoo closes. Trailing statistics only. Simulate the rule. Bootstrap. Count the 4 runnable variants in DSR. Disclose that the 2015-2026 descriptive statistics were seen before registration.
- data: Sprott PHYS page (embedded daily premium/discount since 2010-02, verified 2026-10-14); Yahoo PHYS, GLD, PSLV, SLV daily closes · min n: 30
- pass: 95% lower bound of mean net return per trade > 0 AND at least 30 trades AND same sign in 2012-2019 and 2020-2026
- controls: Look-ahead: NAV is struck after the close, so execute at the next close; trailing windows only; the disclosed descriptive peek is counted as a trial. Costs: PHYS spread ~3-5 bps, 10 bps/leg modelled, GLD borrow, fee differential (0.39% vs 0.40%) negligible. Tax: PHYS is a PFIC for US holders (QEF election), outside the return calculation. Regime: 2020 stress and the 2022-2026 drift. Multiple testing: 4 variants.
- note: from the underlying-library library: Physical bullion trust discount reversion (PHYS vs GLD); harness suggestion: trust_discount_reversion: Sprott page scraper (Highcharts data arrays), trailing-mean-relative z rule, per-trade bootstrap; generic for any premium/NAV series | added by the verifier pass

### T-473 · pca-etf-residual-statarb

**Claim.** On S&P 500 point-in-time members with Yahoo prices, 2010-2026, the Avellaneda-Lee sector-ETF s-score strategy with the published thresholds earns an annualized Sharpe greater than zero net of 5 bps per side per trade.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://math.nyu.edu/~avellane/AvellanedaLeeStatArb20090616.pdf, https://doi.org/10.1080/14697680903124632
- statistic: annualized net Sharpe of daily strategy returns; DSR over variants
- null: net Sharpe = 0 (stationary block bootstrap, block 20 days)
- procedure: Re-estimate daily on trailing 60/252-day windows only. Simulate with costs. Block bootstrap. DSR and CSCV PBO over the 5 variants. Report 2010-2017 and 2018-2026.
- data: fja05680 S&P 500 membership + Yahoo daily adjusted closes and volumes; sector SPDR ETFs · min n: 2000
- pass: 95% lower bound of net Sharpe > 0 AND DSR > 0.95 AND PBO < 0.5
- controls: Look-ahead: trailing estimation; trade at the next close after the signal close. Survivorship: delisted members are missing from Yahoo, so the read is a biased upper bound; the clean read needs CRSP/Norgate. Costs: 5 bps per side per trade plus 50 bps/yr borrow. Multiple testing: DSR/PBO. Regime: halves; 2020-03 and 2022 reported.
- note: from the underlying-library library: Residual (PCA / sector-ETF factor) statistical arbitrage (Avellaneda-Lee s-score); harness suggestion: residual_statarb: rolling regression/PCA factor model, OU s-score, threshold state machine, cost model; feeds overfit.pbo_cscv | added by the verifier pass

### T-474 · treasury-butterfly-reversion

**Claim.** From 2008-01 to 2026-09, the duration-neutral SHY/IEI/IEF butterfly traded on |z| > 2 of the FRED 2s5s10s fly earns a positive mean net return per trade after 3 bps per leg per trade and 30 bps/yr borrow on the short legs.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://www.johnhcochrane.com/s/Duarte_Longstaff_Yu_nickelsRFS.pdf, https://doi.org/10.2139/ssrn.872004
- statistic: mean net return per trade (and daily Sharpe of the sleeve) with bootstrap interval
- null: mean net return per trade = 0 (block-shift of the signal, block 60 days)
- procedure: FRED yields set signals (available_at = next business day, since FRED posts H.15 with a lag); ETF adjusted closes for P&L. Trailing z. Simulate. Bootstrap. DSR over 4 runnable variants. Report the ZLB (2009-2015) and post-2022 hiking periods.
- data: FRED DGS2, DGS5, DGS10 (DGS2/DGS10 in the archive; DGS5 reachable, verified); Yahoo SHY (2002), IEI (2007-01), IEF (2002), TLH, TLT adjusted closes · min n: 30
- pass: 95% lower bound of mean net return per trade > 0 AND at least 30 trades AND DSR > 0.95
- controls: Look-ahead: FRED yields used only from their availability date; ETF trades at the next close. Duration drift: fixed durations introduce residual level/slope exposure, so a regression of P&L on yield-level and slope changes is reported. Costs: 3 bps/leg plus borrow. Regime: ZLB, 2022 hiking. Multiple testing: 4 variants.
- note: from the underlying-library library: Treasury curve butterfly (2s5s10s) mean reversion; harness suggestion: curve_fly_harness: FRED yield fly with available_at lag, DV01-weighted ETF P&L, z-rule, residual-exposure regression | added by the verifier pass

### T-476 · return-seasonality-etfs

**Claim.** Over 2004-2026, the same-calendar-month long-short portfolio on the 14-ETF universe earns a positive after-cost mean monthly return, with the block-bootstrap 95% interval excluding zero and the mean above the 95th percentile of a within-month rank-permutation null.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional, https://www.nber.org/papers/w20815.pdf (Keloharju-Linnainmaa-Nyberg working paper; search result), https://academicnewsletter.sufe.edu.cn/info/359830 (abstract mirror; search result)
- statistic: Mean monthly long-short return after costs; permutation percentile; DSR over 8 trials
- null: Mean = 0; seasonal ranks uninformative
- procedure: Monthly adjclose panel; expanding seasonal averages using only prior years; block bootstrap (block 12 months); 1,000 permutations; DSR
- data: Yahoo adjclose for the 14 ETFs (GLD, SLV, USO, TLT in archive without adjclose) · min n: 260
- pass: Mean > 0 with 95% interval excluding 0, above the permutation 95th percentile, DSR > 0.95
- controls: Look-ahead: scores use years before the current one only; survivorship: fixed ETF set; costs: 5 bps per side SPDRs, 10 bps commodity ETFs, borrow on shorts; multiple testing: 8 trials; regime: by decade and ex-energy
- note: from the underlying-library library: Return seasonality (same-calendar-month momentum) on sector and commodity ETFs; harness suggestion: underlying.py seasonal_score(adj_monthly, min_years, max_years) feeding xs_momentum; harness return_seasonality_etf. | added by the verifier pass

### T-479 · breadth-momentum-canary-daa

**Claim.** Over 2008-05 to 2026-09, the DAA rule earns a higher after-cost Sharpe ratio than the same top-6 rotation without the canary, with the paired block-bootstrap 95% interval of the Sharpe difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/dual, https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/ (search result), https://vvv.quantpedia.com/?p=25576 (search result)
- statistic: Sharpe(DAA) - Sharpe(no-canary rotation), paired monthly; PBO over the 4-trial x threshold matrix; diagnostic: post-2018 sub-sample
- null: Sharpe difference = 0: the canary adds nothing
- procedure: Monthly adjclose panel (BND from 2007-04 sets the start); paired block bootstrap (block 12 months, 5,000 draws); CSCV PBO; DSR
- data: Yahoo adjclose for the 15 ETFs (not in archive); fred-DTB3 · min n: 200
- pass: Sharpe difference > 0 with 95% interval excluding 0, DSR > 0.95, PBO < 0.5
- controls: Look-ahead: month-end scores, next-day trades; survivorship: ETFs named ex ante by the authors (but chosen after seeing history: stated); costs: 5 bps per side, turnover reported; multiple testing: 4 trials plus threshold; regime: 2008, 2020, 2022 and post-2018
- note: from the underlying-library library: Breadth momentum with a canary universe (Keller-Keuning DAA); harness suggestion: underlying.py score_13612w() and daa_weights(); harness daa_vs_rotation with pbo_cscv. | added by the verifier pass

### T-481 · cross-asset-tsmom-bond-equity

**Claim.** On SPY 1994-2026, the cross-asset long/flat rule ((e + b)/2 clipped at 0) has a higher after-cost Sharpe ratio than SPY's own 12-1 long/flat TSMOM, with the paired block-bootstrap 95% interval of the Sharpe difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://ideas.repec.org/a/eee/jfinec/v136y2020i1p63-85.html (Pitkäjärvi-Suominen-Vaittinen 2020; fetched in this pass)
- statistic: Sharpe(cross-asset) - Sharpe(own TSMOM), paired monthly; DSR over 12 trials
- null: Sharpe difference = 0: the bond signal adds nothing
- procedure: Monthly adjclose and synthetic bond series; paired studentized block bootstrap (block 12 months, 5,000 draws); DSR; placebo with the bond signal shifted 12 months
- data: Yahoo adjclose SPY, IEF, TLT; fred-DGS10 and fred-DTB3 (both in archive) · min n: 380
- pass: Sharpe difference > 0 with 95% interval excluding 0, DSR > 0.95, placebo interval includes 0
- controls: Look-ahead: month-end yields and closes used next day (FRED available_at respected); survivorship: n/a; costs: 2 bps per side SPY; synthetic bond return approximation error checked against IEF over 2002-2026; multiple testing: 12 trials; regime: 1994-2007, 2008-2021, 2022-2026
- note: from the underlying-library library: Cross-asset time-series momentum (bond momentum times equities); harness suggestion: underlying.py synthetic_bond_returns(dgs10) and cross_asset_tsmom(); harness cross_asset_tsmom_vs_own. | added by the verifier pass

### T-482 · frog-in-the-pan-continuity

**Claim.** Over 2004-2026, among panel assets with positive 12-1 returns, the low-ID (continuous) half earns a higher mean next-month after-cost return than the high-ID half, with the block-bootstrap 95% interval of the difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://alphaarchitect.com/2015/11/frog-in-the-pan-identifying-the-highest-quality-momentum-stocks/ (summary; search result), https://www3.nd.edu/~zda/Frog.pdf (paper; search result)
- statistic: Mean monthly return difference (continuous half minus discrete half); DSR over 4 trials
- null: Difference = 0
- procedure: Monthly panel from daily adjclose; block bootstrap (block 12 months, 5,000 draws); DSR; leave-crypto-out robustness
- data: Yahoo adjclose daily for the 21 assets · min n: 250
- pass: Difference > 0 with 95% interval excluding 0, DSR > 0.95, sign holds without crypto
- controls: Look-ahead: formation through t, trade t+1; survivorship: fixed panel; costs: 5 bps ETFs, 25+10 bps crypto; multiple testing: 4 trials; regime: by decade
- note: from the underlying-library library: Frog-in-the-pan: continuity of information as a momentum filter (ETF and crypto panel); harness suggestion: underlying.py information_discreteness(daily_returns, window); harness frog_in_pan_panel. | added by the verifier pass

### T-483 · leverage-for-the-long-run

**Claim.** Over 1994-2026, the 2x-above-200-day-SMA rule's after-cost, after-financing compound annual growth rate exceeds SPY buy-and-hold's, with the block-bootstrap 95% interval of the mean daily log-return difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://www.cxoadvisory.com/volatility-effects/leveraging-the-u-s-stock-market-based-on-sma-rules/ (summary of Gayed-Bilello; search result), https://www.quantconnect.com/learning/articles/investment-strategy-library/leveraged-etfs-with-systematic-risk-management (search result)
- statistic: Mean daily log-return difference (rule minus SPY), annualised; DSR of the difference series over 6 trials plus T-58's SPY trials; diagnostic: max drawdown, SSO cross-check 2006-2026
- null: Mean log-return difference = 0
- procedure: Daily adjclose and DTB3; circular block bootstrap (block 60 days, 5,000 draws); DSR; SSO real-fund replication
- data: daily-history-SPY (refetch with adjclose); Yahoo SSO, UPRO; fred-DTB3 · min n: 8000
- pass: Mean log difference > 0 with 95% interval excluding 0, DSR > 0.95, SSO 2006-2026 point estimate same sign
- controls: Look-ahead: one-bar delay; survivorship: n/a; costs: 2 bps per switch SPY, 5 bps SSO, financing at T-bill + 50 bps; multiple testing: 6 trials plus T-58; regime: 2018-Q4, 2020-03 and 2022 whipsaws reported
- note: from the underlying-library library: Leverage for the long run: 2x S&P exposure above the 200-day SMA, T-bills below; harness suggestion: underlying.py leveraged_sma(adj, dtb3, lev, length); harness leverage_long_run. | added by the verifier pass

### T-484 · bond-tsmom-fred-long-history

**Claim.** Over 1963-2026, the 12-1 long/short TSMOM rule on the synthetic 10-year Treasury excess return earns a higher mean monthly return than the historical-mean strategy, with the studentized block-bootstrap 95% interval of the difference excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/time-series, https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr657.html (Durham 2013; search result), https://arxiv.org/abs/1404.3274 (Lemperiere et al.; fetched in this pass)
- statistic: Mean monthly difference d = r(TSMOM) - r(historical-mean); DSR over 8 trials; sub-periods 1963-1981, 1982-2020, 2021-2026
- null: E[d] = 0
- procedure: Monthly synthetic returns; studentized block bootstrap (block 12 months, 5,000 draws); DSR; validate the synthetic series against IEF adjclose 2002-2026 (correlation > 0.95 required)
- data: fred-DGS10, fred-DGS2, fred-DTB3 (all in archive); Yahoo IEF adjclose for validation · min n: 700
- pass: Mean d > 0 with 95% interval excluding 0, DSR > 0.95, and d > 0 in at least 2 of 3 sub-periods
- controls: Look-ahead: FRED values used with available_at; survivorship: none; costs: 2 bps per side (futures/ETF equivalent); synthetic-return approximation error measured against IEF; multiple testing: 8 trials; regime: three rate regimes reported
- note: from the underlying-library library: Long-history Treasury trend from FRED yields (synthetic 10-year bond TSMOM since 1962); harness suggestion: underlying.py synthetic_bond_returns(dgs, maturity) shared with cross-asset-tsmom-bond-equity; harness bond_tsmom_long_history reusing the TSMOM harness. | added by the verifier pass

### T-500 · butterfly-convexity-arbitrage

**Claim.** On the CBOE delayed SPX and SPY chains, fewer than 0.5% of equally spaced call or put butterflies (adjacent listed strikes within +/- 20% of spot, all expiries) can be bought for a net credit at executable prices (ask on wings, bid on the body).

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Butterfly_(options), https://arxiv.org/abs/1204.0646
- statistic: Share of butterflies with B_exec < 0.
- null: Share >= 0.5%.
- procedure: Day one: enumerate butterflies from adjacent equally spaced strikes; compute B_exec and B_mid; count; bootstrap across expiries; repeat daily.
- data: CBOE delayed SPX and SPY chains (available). · min n: 1000
- pass: Share < 0.5% with the 95% upper bound < 0.5% on day one and on >= 80% of captured days.
- controls: Mid-price share should be small but non-zero; drop legs with zero bid; separate wing strikes (> 10% OTM) from the core.
- note: from the options-library library: Butterfly convexity arbitrage (negative-priced butterfly); harness suggestion: mandel/options/static_arb.py: butterfly_scan(chain) with executable and mid prices; payoff engine template [call+ K1, call-2 K2, call+ K3]. | added by the verifier pass

### T-501 · calendar-time-value-arbitrage

**Claim.** On the CBOE delayed SPY chain (American), fewer than 0.1% of same-strike call or put pairs at adjacent expiries can be bought as a calendar for a net credit at executable prices (far ask < near bid).

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Calendar_spread, https://arxiv.org/abs/1204.0646
- statistic: Share of same-strike adjacent-expiry pairs with far_ask < near_bid.
- null: Share >= 0.1%.
- procedure: Day one: enumerate pairs; count executable credits; for SPX, compute total-variance violations at fixed forward-moneyness as a companion statistic; repeat daily.
- data: CBOE delayed SPY and SPX chains (available). · min n: 5000
- pass: Share < 0.1% on day one and on >= 80% of captured days.
- controls: Exclude zero-bid near legs; separate deep ITM calls straddling ex-div (early-exercise value); Deribit total-variance scan as a crypto replication.
- note: from the options-library library: Calendar (time-value) arbitrage; harness suggestion: static_arb.py calendar_scan(chain) plus total_variance_check(surface). | added by the verifier pass

### T-507 · synthetic-call-put-stock-option

**Claim.** For SPY expiries before 2026-12-18 with 30-64 DTE and strikes within +/- 5% of spot, buying SPY at the ask plus the put at the ask costs less than buying the call at the ask plus holding K e^{-r_bill T} in bills in at least 60% of strikes, because option prices embed a financing rate above the bill rate.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Synthetic_position, https://en.wikipedia.org/wiki/Protective_put
- statistic: Share of strikes with (S_ask + P_ask) < (C_ask + K e^{-r_bill T}).
- null: Share < 60%.
- procedure: Day one: SPY chain and underlying quote; no dividend inside T; compute both costs per strike; repeat daily.
- data: CBOE delayed SPY chain, FRED DGS3MO. · min n: 50
- pass: Share >= 60% on day one and on >= 80% of captured days.
- controls: Replace r_bill with the SPX box rate (the share should fall to ~50%); mid-price version; GLD/IBIT dividend-free replications.
- note: from the options-library library: Synthetic options (synthetic call / synthetic put from stock + option); harness suggestion: Templates [underlying+, put+] vs [call+] plus a bond leg; payoff engine must show identical kinked shapes offset by K - S0 - P + C. | added by the verifier pass

### T-508 · vertical-spread-bound-arbitrage

**Claim.** Across the CBOE delayed SPY, SPX, QQQ, GLD and IBIT chains, fewer than 0.1% of adjacent-strike call or put verticals violate monotonicity or the width bound at executable prices on the capture day.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Vertical_spread, https://en.wikipedia.org/wiki/Bull_spread
- statistic: Share of adjacent-strike verticals with executable violation (debit < 0 or bid > width bound).
- null: Share >= 0.1%.
- procedure: Day one: enumerate adjacent pairs per expiry; compute executable debits/credits; count violations; repeat daily.
- data: CBOE delayed chains (available), FRED DGS3MO for discounting. · min n: 5000
- pass: Share < 0.1% on day one and on >= 80% of captured days.
- controls: Mid-price violation rate as a quote-quality diagnostic; exclude zero-bid legs; IBIT/GLD reported separately (wider spreads).
- note: from the options-library library: Vertical-spread bound and strike-monotonicity arbitrage; harness suggestion: static_arb.py vertical_scan(chain); also used as a quote-sanity gate in the daily options-fetch job. | added by the verifier pass

### T-511 · weekend-theta-capture

**Claim.** Since SPY's inception (1993-01-29), the variance of SPY Friday-close-to-Monday-close log returns is less than 1.5 times the mean variance of Monday-Thursday single-night close-to-next-close returns, so a Friday option priced on three calendar days of variance overcharges for the weekend.

- kind: options-strategy · origin: options-library:Time / term-structure, https://api.crossref.org/works/10.1111/jofi.12603, https://api.crossref.org/works/10.1016/0304-405x(86)90004-8
- statistic: Variance ratio R = Var(Fri close -> Mon close) / Var(single-night weekday close -> next close)
- null: R >= 1.5
- procedure: From SPY daily closes, label each return by its calendar gap (1 day = weekday night, 3 days = normal weekend; exclude holiday gaps). Compute R overall and in walk-forward halves. Block bootstrap by week; robustness with the top 1% |returns| winsorised.
- data: SPY daily closes since inception (data-only). The option-price side (Friday vs Monday marks) needs chain captures from 2026-10-14. · min n: 1500
- pass: Upper bound of the 95% CI of R < 1.5 in both halves
- controls: Holiday weekends separately. Winsorised vs raw. The realised-variance leg is testable now; whether listed option prices actually charge calendar-day variance is a separate check on the daily captures (Friday-close vs Monday-open ATM straddle marks), with paid history needed for a backtest. Jones and Shemesh's evidence is on option returns, not on realised variance.
- note: from the options-library library: Weekend theta capture (Friday-to-Monday short premium); harness suggestion: spy_weekend_variance(spy_rows) in experiments/options_market.py, mirroring btc_weekend_variance; then a capture-driven check of the Friday-close-to-Monday ATM straddle mark change vs realised. | added by the verifier pass

### T-516 · digital-tight-vertical

**Claim.** For SPY 30-day digital puts at K = 0.97S, the risk-neutral probability N(-d2) computed at VIX IV (model-priced) exceeds the realised frequency of SPY closing below K over 1993-2026 (downside digitals are overpriced).

- kind: options-strategy · origin: options-library:directional-vertical, https://en.wikipedia.org/wiki/Binary_option, https://api.elections.kalshi.com/trade-api/v2/series/KXINX
- statistic: realised frequency minus mean N(-d2), with block bootstrap CI; Brier score of N(-d2) vs climatology
- null: realised frequency >= mean risk-neutral probability
- procedure: non-overlapping 21-day cycles; K = 0.97S; N(-d2) at VIX/100, r = DTB3; outcome 1{S_T < K}
- data: SPY, VIX, DTB3 · min n: 300
- pass: upper CI of (realised - RN) < 0
- controls: Flat IV ignores skew, which raises the market's digital-put price further (the slope term -dC/dK includes the skew), so the real overpricing is larger than modelled. Follow-up (blocked): compare SPXW tight-vertical probabilities with Kalshi KXINX mids at synchronised snapshots.
- note: from the options-library library: Digital (Binary) via Tight Vertical Spread; harness suggestion: digital_calibration(symbol='SPY', moneyness=0.97, dte=21) using proper scoring in mandel/forecasts.py; Kalshi follow-up after 30 synchronised SPXW + KXINX snapshots | added by the verifier pass

### T-522 · election-event-straddle

**Claim.** On US federal election days since 1994, SPY's absolute 2-day return (close before election day to close after) divided by the VIX-implied 2-day move (VIX/sqrt(126)) is larger than the same ratio on matched non-election 2-day windows.

- kind: options-strategy · origin: options-library:event-driven, https://www.nber.org/papers/w19812, https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- statistic: Mean ratio difference (election minus matched windows); exact sign test across 16 elections; MODEL-PRICED straddle P&L with VIX-as-IV.
- null: Election ratio <= matched-window ratio.
- procedure: Elections 1994-2024 (16 dates, every 2 years); SPY closes, VIX; matched windows = same weekday pairs 4 weeks before/after.
- data: SPY daily closes, VIX, election dates; Polymarket/Kalshi odds for 2024+ only. · min n: 16
- pass: Sign test p < 0.05 (>= 13 of 16) and mean difference > 0 (underpowered: report as indicative).
- controls: Presidential vs midterm split; VIX regime; exclude 2008 (crisis).
- note: from the options-library library: Election / political-event straddle (index vol spanning a scheduled vote); harness suggestion: Reuse the VIX-as-IV event pricer with a 2-day horizon; add Polymarket odds as a covariate when n grows. | added by the verifier pass

### T-527 · call-spread-overwrite

**Claim.** In a model-priced simulation on SPX from 1990 to 2026 (Black-Scholes at VIX, not market prices; this flat-IV pricer overprices OTM calls relative to the skewed market, so it is biased against the wing), a monthly short-ATM / long-5%-OTM call-spread overwrite has a higher Sharpe ratio than the plain ATM covered call priced the same way.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write, https://www.optionseducation.org/strategies/all-strategies/bear-call-spread-credit-call-spread
- statistic: Sharpe(call-spread overwrite) - Sharpe(ATM covered call), both model-priced on identical paths
- null: Difference <= 0
- procedure: Model-priced on SPX daily with VIX-as-IV and DTB3, monthly 3rd-Friday rolls, 5 bps per leg slippage; calibration gate vs actual BXM (TE < 2%/yr); paired block bootstrap; walk-forward halves
- data: SPX daily, VIX 1990-, DTB3, SPY dividends, BXM for calibration · min n: 400
- pass: Calibration gate passed AND 95% CI of the Sharpe difference > 0 in both halves
- controls: SKEW-adjusted wing pricing as a sensitivity; a chain-priced re-test once ~24 monthly cohorts of SPY chain capture exist
- note: from the options-library library: Call-spread overwrite (covered call with upside re-entry); harness suggestion: Add as a two-call overlay in the model-priced overlay harness. Re-test with captured chains once ~24 monthly cohorts exist (from 2026-10-14) to remove the flat-IV bias. | added by the verifier pass

### T-528 · vix-call-tail-hedge-overlay

**Claim.** Over 2006-03 to 2026-10, the Cboe VXTH index has a smaller maximum drawdown than the PPUT3M 10%-OTM quarterly put index's companion period, measured on the common 2006-03 onward sample against SPX total return: maxDD(VXTH) is at least 10 points shallower than maxDD(SPY TR).

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_VIX_Tail_Hedge_Index_Methodology.pdf, https://cdn.cboe.com/api/global/us_indices/daily_prices/VXTH_History.csv
- statistic: maxDD(SPY TR) - maxDD(VXTH) on the common sample, daily
- null: Difference < 10 percentage points
- procedure: Cboe CDN VXTH_History.csv (2006-03-31 onward); SPY TR from the Yahoo chart adjclose; compute daily maximum drawdowns; bootstrap the drawdown difference with stationary block resampling of daily returns (block 63 days)
- data: VXTH 5,163 rows; SPY closes plus dividends · min n: 2500
- pass: Bootstrap 90% CI of the drawdown difference > 10 points
- controls: PPUT3M (2004-) and PPUT over the same window as put-based tail hedges; CAGR cost reported alongside
- note: from the options-library library: VIX-call tail-hedge overlay on an equity holding (Cboe VXTH); harness suggestion: Add VXTH and PPUT3M to the benchmark list. Recomputed today: VXTH 2006- CAGR 9.93% / vol 17.2% / maxDD -43.3% / worst month -10.7%. The hedge's 2008 drawdown is large, so the claim may fail; that is the point of testing it. | added by the verifier pass

### T-529 · zero_dte_vix1d_premium

**Claim.** The VIX1D close implies a next-day S&P 500 variance, (VIX1D/100)^2/365 (the conservative calendar-day convention), that exceeds the next trading day's squared ^GSPC close-to-close log return on average.

- kind: options-strategy · origin: options-library:relative-value-surface, https://www.cboe.com/us/indices/dashboard/vix1d/, https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX1D_History.csv
- statistic: Mean of (VIX1D_t/100)^2/365 - r_{t+1}^2; repeat with /252 as the liberal convention.
- null: Mean <= 0 under the /365 convention.
- procedure: Daily VIX1D (history from 2022-05-13) and ^GSPC closes; daily non-overlapping one-day windows (~1,100); studentized block bootstrap (5-day blocks); walk-forward halves; report event days separately.
- data: CBOE VIX1D (archive), ^GSPC/SPY closes. Index-implied variance, no option prices; the straddle P&L itself is model-priced. · min n: 500
- pass: Mean > 0 with the 95% CI excluding zero under the /365 convention, positive in both halves.
- controls: Same test with VIX/sqrt(21)-scaled daily variance (shows whether the 1-day premium differs from the 30-day one); event-day exclusion.
- note: from the options-library library: 1-day (0DTE) variance premium: short SPX daily straddle vs VIX1D; harness suggestion: New harness_vix1d in the harness_vrp_spx style, using archive cboe-VIX1D-history and daily-history--GSPC. | added by the verifier pass

### T-540 · variance-swap-replication

**Claim.** Short 30-day variance struck at (VIX_t/100)^2 and settled on the next 21 trading days' SPY close-to-close realised variance has positive mean P&L in monthly variance units over 1993-2026.

- kind: options-strategy · origin: options-library:volatility, https://emanuelderman.com/wp-content/uploads/1999/02/gs-volatility_swaps.pdf, https://en.wikipedia.org/wiki/Variance_swap
- statistic: mean of (VIX_t^2 - RV21_{t+}) / 12 in percent-squared per month over non-overlapping cycles; studentized block-bootstrap CI; report skew, kurtosis, worst cycle
- null: mean = 0
- procedure: RV21 = (252/21) * sum of squared daily log returns over t+1..t+21; non-overlapping cycles
- data: cboe-VIX-history, daily-history-SPY · min n: 390
- pass: lower CI > 0; robust to excluding the single worst cycle is NOT required (the tail is the point), but report it
- controls: SPX vs SPY basis; close-to-close vs 5-minute RV (BTZ use 5-minute RV, which runs lower); no cap; vrp_spx already supports this in vol units (T-48), so this is the variance-unit and tail-statistics restatement.
- note: from the options-library library: Variance Swap Replication (long / short variance via 1/K^2 strip); harness suggestion: Extend 'vrp_spx' (mandel/experiments/volatility.variance_risk_premium) with a variance-unit, non-overlapping mode and tail statistics; the same mode for vrp_btc and vrp_gold. | added by the verifier pass

## Blocked (129)

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

### T-108 · broken-wing-butterfly

**Claim.** A 30-45 DTE SPY put BWB (K3 30-delta, K2 20-delta, K2 - K1 = 2(K3 - K2)) entered at mid on captured chains and held to expiry has positive mean P&L per unit max loss.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-call-butterfly, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean P&L/max loss over daily entries, studentized block-bootstrap CI (overlapping trades, block >= holding period)
- null: mean P&L = 0
- procedure: Select strikes by delta from options-chain-SPY-<date>; fill at mid and, separately, at bid/ask; settle at intrinsic on the expiry close from daily-history-SPY.
- data: options-chain-SPY-<date> (daily capture from 2026-10-14), daily-history-SPY · min n: 250
- pass: lower CI > 0 at bid/ask fills, with at least one >10% SPY drawdown month in the sample
- controls: Delta rule fixed. Report credit frequency as descriptive only. Verdict capped at 'inconclusive' without a stress episode.
- blocked on: daily chain capture: 250 entry days (each resolving 30-45 days later) including a stress month
- note: from the options-library library: Broken-Wing (Skip-Strike) Butterfly; harness suggestion: harness 'bwb_skew_credit' reading the chain-capture bundle; store per-day strike selection in the result for audit | verifier: corrected claim/trial

### T-111 · long-condor

**Claim.** On captured SPX chains, opening the condor range bet as an iron condor (sold at the bid) costs less than buying the all-call condor at the ask at the same strikes, after PV adjustment, on at least 80% of capture days: the iron form beats the all-call form on execution.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-call-condor
- statistic: fraction of days with [PV(W) - C_iron_bid] < D_callcondor_ask; secondary: mid-parity residual |C_iron_mid + D_condor_mid - PV(W)| vs the average leg spread
- null: the iron form is cheaper on <= 50% of days
- procedure: Matched strikes (16-delta shorts, wings 2% beyond) from options-chain-SPX-<date>, all legs at the same timestamp; PV at fred-DTB3
- data: options-chain-SPX-<date> (daily capture from 2026-10-14), fred-DTB3 · min n: 30
- pass: fraction >= 0.8 with binomial 95% lower bound > 0.5
- controls: SPX is European, so there is no early-exercise premium. Delayed-quote staleness documented. The SPY run is reported separately (dividends and American exercise).
- blocked on: daily chain capture, 30 days (no expiry wait needed)
- note: from the options-library library: Long Condor (all-call or all-put, debit); harness suggestion: harness 'condor_parity_check' as an engine sanity control (like 'controls' for scoring) | verifier: corrected claim/trial

### T-112 · short-condor-vertical

**Claim.** On captured SPX chains, the reverse iron condor bought at the ask is cheaper than the same-strike short call condor sold at the bid (after PV of the width) on at least 80% of capture days.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-call-condor, https://en.wikipedia.org/wiki/Options_strategy
- statistic: fraction of days with D_rev_iron_ask < PV(W) - C_shortcallcondor_bid
- null: <= 50% of days
- procedure: as long-condor, credit side
- data: options-chain-SPX-<date>, fred-DTB3 · min n: 30
- pass: fraction >= 0.8 with binomial lower bound > 0.5
- controls: as long-condor
- blocked on: daily chain capture, 30 days
- note: from the options-library library: Short Condor (all-call or all-put, credit); harness suggestion: covered by 'condor_parity_check' | verifier: corrected claim/trial

### T-117 · guts

**Claim.** On captured SPX chains, buying the guts at the ask costs more (after subtracting PV(K_p - K_c)) than buying the swapped-strike strangle at the ask on at least 80% of capture days: the strangle beats the guts on execution.

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Options_strategy, https://www.optionseducation.org/strategies/all-strategies/long-strangle-long-combination
- statistic: fraction of days with guts_ask - PV(K_p - K_c) > strangle_ask; secondary: mid-parity residual
- null: <= 50% of days
- procedure: Matched strikes (K_c = 25-delta put strike, K_p = 25-delta call strike) from options-chain-SPX-<date>; PV at fred-DTB3
- data: options-chain-SPX-<date>, options-chain-SPY-<date>, fred-DTB3 · min n: 30
- pass: fraction >= 0.8 with binomial lower bound > 0.5 on SPX
- controls: SPX European (clean); SPY reported separately since the American early-exercise premium can legitimately break parity; same timestamp for all legs.
- blocked on: daily chain capture, 30 days
- note: from the options-library library: Guts (long / short); harness suggestion: include in 'condor_parity_check' as a second parity test | verifier: corrected claim/trial

### T-118 · albatross

**Claim.** A 45-DTE SPY short iron albatross (short 5-delta strangle, long wings at the next strikes 2% further out), entered at mid on captured chains and held to expiry, has positive mean P&L per unit max loss.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-condor, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: mean P&L/max loss with studentized block-bootstrap CI; secondary: realised breach frequency vs mid-implied and the IV(5d put)/IV(ATM) ratio series
- null: mean P&L = 0
- procedure: Daily strike selection by delta; mid and bid/ask fills; settle on the expiry close
- data: options-chain-SPY-<date>, daily-history-SPY · min n: 250
- pass: lower CI > 0 at bid/ask fills with a >10% drawdown month in the sample
- controls: Verdict capped at 'inconclusive' until a stress month is captured.
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Albatross (long / short); harness suggestion: harness 'tail_wing_richness' in options.py; implied vol from the engine's implied_vol() | verifier: corrected claim/trial

### T-119 · call-ratio-backspread

**Claim.** A 60-DTE SPY 1:2 call backspread (short ATM, long 2x 25-delta calls), entered at mid on captured chains and held to expiry, has negative mean P&L per unit max loss: realised upside rarely reaches the upper breakeven.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-ratio-call-spread
- statistic: mean P&L/max loss with studentized block-bootstrap CI
- null: mean P&L = 0
- procedure: Delta-selected strikes from daily chains; mid and bid/ask fills; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY · min n: 250
- pass: upper CI < 0 at mid fills
- controls: Rule fixed; credit/debit frequency reported descriptively; IBIT and GLD runs reported as cross-asset contrasts.
- blocked on: daily chain capture: 250 entry days resolving ~60 days later
- note: from the options-library library: Call Ratio Backspread; harness suggestion: harness 'backspread_credit_frequency' in options.py | verifier: corrected claim/trial

### T-120 · put-ratio-backspread

**Claim.** A 60-DTE SPY 1:2 put backspread (short ATM, long 2x 5%-OTM puts), entered at mid on captured chains and held to expiry, has negative mean P&L per unit max loss (the crash hedge costs money on average).

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/long-ratio-call-spread, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean P&L/max loss with studentized block-bootstrap CI; secondary: P&L conditional on a >10% drawdown inside the holding window
- null: mean P&L = 0
- procedure: Daily strike selection; mid and bid/ask; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY, cboe-SKEW-history (descriptive) · min n: 250
- pass: upper CI < 0 at mid fills, with a stress month in the sample
- controls: A sample without a crash is biased toward a negative result, so the verdict is capped at 'inconclusive' until a stress episode is captured.
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Put Ratio Backspread; harness suggestion: same 'backspread_credit_frequency' harness, put side | verifier: corrected claim/trial

### T-121 · front-ratio-spread

**Claim.** A 45-DTE SPY put front-ratio (long 40-delta put, short two 20-delta puts), entered at mid on captured chains and held to expiry, has positive mean P&L per unit of naked-leg margin.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-ratio-call-spread
- statistic: mean P&L/margin with studentized block-bootstrap CI
- null: mean P&L = 0
- procedure: Delta-selected strikes; mid and bid/ask fills; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY · min n: 250
- pass: lower CI > 0 at bid/ask with a stress month in the sample
- controls: Rule fixed; tail absent from short samples, so the verdict is capped at inconclusive.
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Front Ratio Spread (short ratio call / put spread); harness suggestion: harness 'front_ratio_skew' sharing the delta selector | verifier: corrected claim/trial

### T-122 · unbalanced-iron-condor

**Claim.** A 45-DTE SPY 2:1 put-weighted unbalanced 16-delta iron condor has higher mean P&L per unit max loss than the balanced 16-delta condor entered on the same captured days and held to expiry.

- kind: options-strategy · origin: options-library:volatility, https://www.optionseducation.org/strategies/all-strategies/short-condor, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: paired mean difference of P&L/max loss with studentized block-bootstrap CI; put credit share reported descriptively
- null: no difference
- procedure: Both structures built from the same daily chain at mid; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY · min n: 250
- pass: lower CI of the difference > 0 with a stress month in the sample
- controls: Rules fixed; mid and bid/ask; SKEW index for regime description.
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Unbalanced (Skewed) Iron Condor; harness suggestion: harness 'condor_credit_split' in options.py | verifier: corrected claim/trial

### T-137 · synthetic-long-short-stock

**Claim.** In captured SPX (European), SPY, GLD and IBIT chains, the mid-price synthetic forward K + C - P deviates from the parity forward by more than the two half-spreads plus 10 bps of spot in fewer than 1% of near-ATM strike-expiry pairs (no exploitable conversion/reversal edge for a retail API account).

- kind: options-strategy · origin: options-library:directional-vertical, https://www.optionseducation.org/strategies/all-strategies/synthetic-long-stock, https://www.optionseducation.org/strategies/all-strategies/synthetic-short-stock
- statistic: share of pairs with |K + C_mid - P_mid - F| > half-spread(C) + half-spread(P) + 0.001*S, where F = S*exp((r-q)T) for SPX, and for American SPY/GLD/IBIT the check is against the American no-arbitrage bounds S - PV(div) - K <= C - P <= S - K*exp(-rT)
- null: share >= 1%
- procedure: for each daily capture, take the 3 strikes nearest spot for every expiry; r from FRED DTB3; q for SPX/SPY implied from the SPX box/parity regression (dividends are not in the free data list); cluster CIs by capture day
- data: CBOE delayed chains for _SPX, SPY, GLD, IBIT (daily capture from 2026-10-14); DTB3 · min n: 500
- pass: share < 1% with a day-clustered 95% CI entirely below 1%
- controls: Delayed (15-min) quotes can be stale: exclude crossed or zero bids. SPX is the clean European control. The repo's T-181 parity_check (mandel/experiments/options_market.py) already regresses C - P on K: run both.
- blocked on: daily chain capture, about 5 trading days. One capture already gives about 250 near-ATM pairs (SPY/GLD/IBIT/SPX have dozens of expiries each), so 500 pairs come quickly, but at least 5 separate days are needed for a day-clustered CI. Not 20 days.
- note: from the options-library library: Synthetic Long / Short Stock (Combo); harness suggestion: parity_deviation_scan(symbols=['SPY','GLD','IBIT']) over the chain archive | verifier: corrected claim/trial

### T-141 · zero-dte-directional-debit-spread

**Claim.** An SPX 0DTE ATM/+0.5% bull call spread bought at the mid at a fixed intraday capture time and held to the 4:00 pm settlement has a mean return per dollar of debit <= 0 after one half-spread per leg, over 120 or more sessions.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: mean return on debit after half-spread costs, studentized bootstrap CI over sessions
- null: mean > 0
- procedure: at each fixed-time intraday capture, record the same-day SPXW ATM and ATM + 0.5% call bid/ask; debit = mid difference; settle at the SPX close; subtract one half-spread per leg
- data: CBOE delayed _SPX chain (today's capture includes the same-day 2026-10-14 expiry) captured at a fixed intraday time, SPX close · min n: 120
- pass: upper CI <= 0
- controls: Capture time fixed in advance. Delayed (15-min) quotes are a known stale-quote bias: record the SPX level at capture and discard sessions where SPX moved > 0.3% during the delay. Also run the mirror bear put spread. The existing daily capture job must run intraday (before 4 pm), not after the close, or same-day expiries will already be gone.
- blocked on: intraday (fixed-time, before 4 pm ET) 0DTE chain capture, 120 sessions
- note: from the options-library library: Zero-DTE Directional Debit Spread; harness suggestion: zero_dte_spread_study(symbol='SPX', side='call', width=0.005) over the chain archive; add Deribit daily-expiry twin with the 08:00 UTC TWAP | verifier: corrected claim/trial

### T-142 · zero-dte-directional-credit-spread

**Claim.** An SPX 0DTE 10-delta / 0.5%-wide bull put spread sold at the mid at a fixed intraday capture time has a win rate above 85%, and its mean P&L per unit of max loss after one half-spread per leg is below +2%, over 120 or more sessions.

- kind: options-strategy · origin: options-library:directional-vertical, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: win rate with binomial CI; mean P&L / max loss after costs with studentized bootstrap CI
- null: win rate <= 85%, or mean P&L / max loss >= +2%
- procedure: at each fixed-time capture, select the same-day put nearest delta -0.10 (CBOE Greeks) and the put 0.5% of S below it; credit = mid difference minus half-spreads; settle at the SPX close
- data: CBOE delayed _SPX chain with Greeks captured at a fixed intraday time, SPX close · min n: 120
- pass: win-rate lower CI > 0.85 AND mean upper CI < +0.02 (an equivalence margin)
- controls: Correction: the original pass rule ('CI includes 0') rewarded low power and was not falsifiable; replaced with an equivalence bound. Capture time fixed; stale-quote filter as in the debit twin; report the mirror call side; DSR over the family's 0DTE trials. Bandi-Fusari-Reno: 0DTE prices embed jump and vol-of-vol premia, so a positive mean would be a premium, not mispricing.
- blocked on: intraday (fixed-time, before 4 pm ET) 0DTE chain capture, 120 sessions
- note: from the options-library library: Zero-DTE Directional Credit Spread; harness suggestion: zero_dte_spread_study(symbol='SPX', side='put', delta=-0.10, width=0.005) | verifier: corrected claim/trial

### T-158 · event-calendar

**Claim.** Across earnings events in the 10 most option-active US single stocks (including TSLA, NVDA, AAPL), the ATM calendar sold in the event-week expiry and bought in the next monthly has positive mean P&L as a percentage of debit when the front straddle's implied move is at least 1.25 times the trailing 8-quarter median realised earnings move.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.tastylive.com/concepts-strategies/diagonal-spread, https://www.fidelity.com/learning-center/investment-products/options/options-strategy-guide/long-calendar-spread-calls
- statistic: Mean P&L/debit across qualifying events (implied/realised ratio >= 1.25)
- null: Zero mean (bootstrap across events); for the placebo, ratios are permuted across events
- procedure: For each event, capture front and back ATM IVs and the straddle on the close before the event. Realised move = |log(close_after/close_before)|. Revalue the back leg at the front expiry from the captured post-event IV. Bootstrap across events; tercile monotonicity as a diagnostic.
- data: Daily CBOE chain captures (from 2026-10-14) for the 10 names plus SPY/TLT; earnings and FOMC/CPI calendars (free IR pages, SEC 8-K, Federal Reserve schedule; not yet ingested); daily closes · min n: 40
- pass: Mean > 0 with the 95% CI excluding 0 over at least 40 qualifying events
- controls: Exclude events with concurrent M&A or guidance shocks. Compare with the plain short front straddle to test whether the back leg earns its cost. Costs from captured spreads. Trailing realised moves need 8 quarters of closes (available).
- blocked on: Daily chain capture spanning at least 40 qualifying events. With 10 names (about 40 earnings a year), and only the high-ratio subset qualifying, that takes roughly 18-24 months of captures (TSLA/NVDA/AAPL alone would take about 3+ years). Paid chain history (ORATS/ThetaData) would unblock it now. An earnings-calendar ingest is also needed.
- note: from the options-library library: Event (earnings / macro) calendar; harness suggestion: Tag chain captures with event dates (free IR calendars / SEC 8-K, FOMC schedule); store per-capture front/back ATM IV and straddle-implied move in the surface file so the test runs itself once n is reached. | verifier: corrected claim/trial

### T-165 · covered-call-dividend-aware

**Claim.** For SPY and QQQ American calls that are in-the-money on the trading day before an ex-dividend date with remaining time value smaller than the dividend, more than 80% of open interest is exercised early (OI falls by more than 80% by the ex-date).

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.irs.gov/publications/p550, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write
- statistic: Fraction of open interest removed between T-1 and the ex-date for ITM strikes with (dividend - time value) > 0, with a logistic fit of OI drop on (dividend - time value)
- null: OI-drop fraction <= 0.8 for dividend > time value, or no relation to (dividend - time value)
- procedure: Daily CBOE chain captures for SPY/QQQ around each quarterly ex-date: record OI by strike at T-2, T-1, ex-date and T+1. Compute time value from the T-1 mid minus intrinsic, then the per-strike OI drop and its contract-weighted fraction. OI drop is a proxy for exercise, since closing trades also reduce OI.
- data: Daily chain capture (starts 2026-10-14); needs at least 4 ex-dates per symbol · min n: 200
- pass: Contract-weighted OI-drop fraction > 0.8 (95% CI) for dividend > time value, with a positive logistic slope at p < 0.01
- controls: The same strikes in non-dividend weeks; OTM strikes on ex-dates; European index options (SPX/NDX) as a no-early-exercise placebo
- blocked on: daily chain capture through at least 4 quarterly SPY/QQQ ex-dates (Dec-2026 to Sep-2027, ~340 days)
- note: from the options-library library: Dividend-aware covered call (ex-dividend management, qualified covered call); harness suggestion: Add an ex-dividend calendar for SPY/QQQ/IWM/DIA to the daily capture and store OI per strike at T-2..T+1. | verifier: corrected claim/trial

### T-167 · zero-cost-collar

**Claim.** For 30-DTE SPX options, the call strike whose mid price equals the mid price of the 5%-OTM put lies closer to spot than the put does: the time-averaged ratio (K_c - S)/(S - K_p) is below 1.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/collar-protective-collar, https://cdn.cboe.com/api/global/us_indices/governance/CLL_Methodology.pdf
- statistic: Mean over capture days of (K_c - S)/(S - K_p), with K_c interpolated between listed strikes at equal mid to the 95% put, nearest-30-DTE expiry
- null: Mean ratio >= 1 (symmetric or call-wider band)
- procedure: From the daily CBOE SPX chain capture, select the ~30-DTE expiry, interpolate the 95% put mid, solve the equal-mid call strike, and record the ratio. HAC (Newey-West, lag 21) CI on the mean. A model-priced version from VIX-as-IV with a parametric skew is NOT acceptable evidence.
- data: Daily chain capture SPX/SPY from 2026-10-14; Cboe SKEW history for later conditioning · min n: 120
- pass: Upper 95% HAC CI of the mean ratio < 1, with the same sign in both halves
- controls: The same statistic on GLD (expect ratio > 1) and IBIT (regime-dependent)
- blocked on: daily chain capture, ~120 trading days
- note: from the options-library library: Zero-cost collar; harness suggestion: Write surface_summary to also store, per capture, the equal-premium call strike for 5%/10% OTM puts at 30/60/90 DTE for SPX, GLD, IBIT. | verifier: corrected claim/trial

### T-173 · covered-ratio-spread-1x2

**Claim.** For SPY, the mean monthly P&L of the 1x2 overlay (short 2x 5%-OTM calls, long 1x 10%-OTM call, 30 DTE, held to expiry) minus a single 5%-OTM covered call overlay is higher when the prior 5%-to-10% OTM call IV slope is in its top quartile than when it is in its bottom quartile.

- kind: options-strategy · origin: options-library:income-overlay-on-holding, https://www.optionseducation.org/strategies/all-strategies/covered-ratio-spread, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Difference in mean overlay-P&L spread (1x2 minus single OTM call) between the top and bottom quartiles of the entry-day call-skew slope
- null: Top-quartile mean <= bottom-quartile mean
- procedure: Daily SPY chain capture: on each capture day record 5%/10% OTM ~30-DTE call mids and IVs; settle each overlapping cohort at expiry with SPY closes; stratify by entry skew slope; block bootstrap by expiry cohort
- data: Daily chain capture (from 2026-10-14) + SPY closes · min n: 24
- pass: 95% CI of the top-minus-bottom quartile difference > 0
- controls: The same test on GLD and IBIT, where the skew sign differs
- blocked on: daily chain capture, ~24 monthly expiry cohorts (~730 days); daily overlapping entries help but remain cohort-correlated
- note: from the options-library library: Covered ratio spread / 1x2 ratio write; harness suggestion: Store 5%/10% OTM call mids and IVs at 30 DTE per capture day for SPY/GLD/IBIT to shorten the wait. | verifier: corrected claim/trial

### T-183 · reversal-reverse-conversion

**Claim.** On a single capture day, the 90th percentile of options-implied borrow (r_bill - r_impl from 30-90 DTE ATM parity at mid prices, dividend-adjusted) across the 200 most liquid optionable US single names exceeds 200 bp/yr.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: 90th percentile across names of implied borrow b_i = r_bill - r_impl,i.
- null: 90th percentile <= 200 bp (implied borrow is not dispersed).
- procedure: For each name: ATM +/- 2 strikes at the first two expiries with 30-90 DTE; r_impl from parity with PV(D) of declared dividends inside T; b_i = r_bill - r_impl; take the cross-sectional 90th percentile; bootstrap across names; repeat daily.
- data: CBOE delayed chains (available), FRED DGS3MO, ex-dividend dates and amounts for 200 names (NOT in the listed feeds). · min n: 200
- pass: Day-one 90th percentile > 200 bp with bootstrap 95% lower bound > 200 bp.
- controls: SPY/QQQ/IWM computed the same way should be < 50 bp; exclude names with a zero-bid ATM leg; placebo with mismatched expiries.
- blocked on: Single-name ex-dividend calendar (free sources exist but are not ingested); without it dividend yield is indistinguishable from implied borrow. The cross-section itself needs only today's chain.
- note: from the options-library library: Reversal (reverse conversion); harness suggestion: Same parity.py output, reported as implied_borrow column; payoff template [underlying-, call+, put-]. | verifier: corrected claim/trial

### T-188 · box-treasury-convenience-yield

**Claim.** Daily changes in the SPX box-minus-bill spread (60-120 DTE, mid prices) are positively correlated with daily changes in VIX, with correlation above 0.2.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.nber.org/papers/w26138, https://en.wikipedia.org/wiki/Box_spread
- statistic: Pearson correlation of d(r_box - r_bill) with d(VIX), studentized block bootstrap CI.
- null: Correlation <= 0.
- procedure: Build a daily SPX box-rate series from captured chains; join DGS3MO and VIX; block bootstrap (5-day blocks) of the correlation; report the mean spread separately.
- data: Daily SPX chain capture (none before 2026-10-14), FRED DGS3MO, CBOE VIX history. · min n: 120
- pass: Correlation > 0.2 with the 95% CI excluding 0.
- controls: Fixed strike-pair rule; exclude < 30 DTE; mid series for the statistic, executable for P&L; check robustness to dropping FOMC days.
- blocked on: daily SPX chain capture, ~120 trading days, to form a box-rate series (alternative: ingest published van Binsbergen-Diamond-Grotteria box-rate data)
- note: from the options-library library: Box-vs-Treasury convenience-yield trade; harness suggestion: box.py daily series -> mandel/experiments/box_bill_spread.py joining FRED + VIX; bootstrap via existing block bootstrap. | verifier: corrected claim/trial

### T-189 · dividend-arbitrage-itm-put

**Claim.** For SPY and liquid US dividend payers on ex-dividend eve, the executable time value (P_ask - (K - S_bid)) of puts with delta < -0.9 and 7-30 DTE exceeds the declared dividend in more than 95% of observations.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Share of ex-div-eve observations with P_ask - (K - S_bid) > D.
- null: Share <= 95% (an exploitable pocket exists among liquid names).
- procedure: Capture chains on ex-div eves; compute executable time value; compare with declared D; stratify by option volume.
- data: CBOE delayed chains captured on ex-div eves; ex-dividend calendar (not ingested); SPY 2026-12-18 ex-date as first ETF observation. · min n: 100
- pass: Share > 95% with the bootstrap 95% lower bound > 95% in liquid names.
- controls: Exclude special dividends; placebo on non-ex-div days (time value > 0 always); report illiquid names separately.
- blocked on: ex-dividend calendar feed plus chain capture on ex-div eves (~60 days to reach 100 observations)
- note: from the options-library library: Dividend arbitrage (long stock + ITM put over ex-div); harness suggestion: mandel/options/dividend_play.py keyed off an ex-div calendar; payoff template [underlying+, put+ ITM]. | verifier: corrected claim/trial

### T-190 · early-exercise-itm-call-ex-div

**Claim.** Across the 2026-12-18 SPY ex-dividend date, SPY calls expiring within 30 days that satisfy D > P + K (1 - e^{-r tau}) on ex-div eve lose at least 30 percentage points more of their open interest than ITM calls that fail the criterion.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Difference in mean relative OI decline (criterion-met minus criterion-failed), from the ex-div-eve chain to the chain published after exercises are processed.
- null: Difference <= 30 pp.
- procedure: Capture SPY (and QQQ/IWM at their December ex-dates) daily through the ex-date; classify ITM calls by the criterion using eve mids and the bill rate; compute OI changes; bootstrap the group difference.
- data: Daily SPY chain capture with OI (from 2026-10-14) through 2026-12-21; FRED DGS3MO; SPY declared December distribution. · min n: 40
- pass: Difference > 30 pp with the 95% CI excluding 30 pp.
- controls: Same-strike puts should show no exercise-driven OI drop; exclude strikes with trading volume on the eve larger than 10% of OI.
- blocked on: daily chain capture through the 2026-12-18 SPY ex-dividend date (~66 days)
- note: from the options-library library: Early exercise of deep ITM calls before ex-dividend (and dividend spread); harness suggestion: mandel/options/early_exercise.py with exercise_criterion(D, P, K, r, T); OI-change study on captured chains. | verifier: corrected claim/trial

### T-193 · hard-to-borrow-synthetic-implied-borrow

**Claim.** US stocks in the top decile of options-implied borrow (30-90 DTE parity, dividend-adjusted) underperform the bottom decile by at least 0.5% over the following month.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Monthly bottom-minus-top decile return spread; block-bootstrap t-stat; deflated Sharpe.
- null: Spread <= 0.
- procedure: Daily chain capture for ~500 optionable names -> implied borrow per name -> monthly decile sorts -> next-month returns from daily closes; walk-forward; PBO across sort definitions.
- data: Daily chain capture (from 2026-10-14) for ~500 names, daily closes, FRED bill, ex-dividend calendar (not ingested). · min n: 12
- pass: Spread >= 0.5%/month with bootstrap p < 0.05 after >= 12 monthly sorts; deflated Sharpe > 0.
- controls: Size and momentum controls; exclude ex-div months; randomised-decile placebo.
- blocked on: daily chain capture across ~500 names for >= 12 months plus an ex-dividend calendar (the day-one cross-section is measurable today)
- note: from the options-library library: Hard-to-borrow synthetic (implied borrow extraction and lending via conversion); harness suggestion: parity.py implied_borrow across symbol universe -> mandel/experiments/implied_borrow_sort.py using existing walk-forward and deflated Sharpe. | verifier: corrected claim/trial

### T-200 · gc-vs-gld-options-basis

**Claim.** At matched maturities (expiries within 7 days), the OG-implied gold forward and the GLD-implied gold forward (GLD F_impl divided by oz/share x e^{-fee T}) differ by less than 20 bp in at least 90% of daily observations.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: Residual = F_gc_impl x oz_per_share x e^{-fee T} / F_gld_impl - 1 (bp); share with |residual| > 20 bp.
- null: Share > 10%.
- procedure: Daily: OG and GLD chains at matched maturities; implied forwards from ATM pairs (Black-76 parity for OG); GLD oz/share from the trust's daily file; record; bootstrap.
- data: CBOE delayed GLD chain (available); CME OG/GC option chain (not in the free data set; CME pages refused automated fetches); GLD daily oz/share. · min n: 60
- pass: Share with |residual| > 20 bp below 10% over 60 days.
- controls: American early-exercise bounds on OG; expiry alignment; spot-gold fix as a third reference if a free source is added.
- blocked on: CME GC/OG option chain source (CME delayed quotes or a paid feed) plus ~60 days of daily capture
- note: from the options-library library: GC futures-options vs GLD options basis; harness suggestion: Extend parity.py cross_venue() to futures-style options (discount at r, no dividend) once a GC/OG chain source exists. | verifier: corrected claim/trial

### T-201 · spx-vs-es-futures-options-parity

**Claim.** At matched quarterly expiries, the SPX option-implied forward and the ES option-implied futures price differ by less than 3 bp in at least 95% of daily observations.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: |F_spx_impl - F_es_impl| / F in bp; share above 3 bp.
- null: Share above 3 bp exceeds 5%.
- procedure: Daily SPX chain plus ES quarterly option quotes; implied forwards from ATM pairs; record; bootstrap.
- data: CBOE delayed SPX chain (available); CME ES option quotes (not in the free data set). · min n: 60
- pass: Share above 3 bp below 5% over 60 days.
- controls: Quarterly-only matching; executable vs mid; XSP/MES replication.
- blocked on: CME ES/MES option quote source plus ~60 days of daily capture
- note: from the options-library library: Index options vs futures options parity (SPX vs ES, XSP vs MES); harness suggestion: parity.py cross_venue() with futures-option pricing (Black-76) once an ES chain source exists. | verifier: corrected claim/trial

### T-202 · covered-call-short-put-equivalence

**Claim.** Over their common daily history in Cboe's published files, the annualised return of the Cboe S&P 500 PutWrite Index (PUT) exceeds that of the BuyWrite Index (BXM) by between 0 and 1.5 percentage points.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity, https://www.optionseducation.org/strategies/all-strategies-en
- statistic: Annualised return difference PUT - BXM from monthly returns; studentized block-bootstrap CI.
- null: Difference <= 0 or >= 1.5 pp/yr.
- procedure: Download PUT and BXM daily histories (free Cboe CSVs); monthly returns; block bootstrap of the difference; walk-forward by decade; report monthly correlation as a diagnostic.
- data: Cboe PUT and BXM index histories (free download, not yet ingested; PUT dashboard lists daily data since January 2007, with longer back-calculated history); FRED bills to explain the collateral-yield component. · min n: 200
- pass: 95% CI of the difference inside (0, 1.5) pp/yr.
- controls: BXMD (OTM calls) for strike dependence; check that 2008 and 2020 drawdowns coincide; T-bill collateral yield subtracted as an explanation test.
- blocked on: Cboe PUT/BXM index CSV ingest (free, one-off download; no option-chain history needed)
- note: from the options-library library: Covered call / cash-secured put equivalence (synthetic identity trade); harness suggestion: mandel/ingest cboe_index_history(PUT, BXM); experiments/putwrite_vs_buywrite.py with block bootstrap. | verifier: corrected claim/trial

### T-203 · event-contract-vs-vertical-replication

**Claim.** For Kalshi S&P 500 daily-close threshold contracts matched within 15 minutes to the delayed SPXW 0 DTE chain, the YES mid lies outside the mid-price no-arbitrage band [(C(K) - C(K+5))/5, (C(K-5) - C(K))/5] by more than $0.02 in at least 10% of snapshots.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/, https://www.cboe.com/tradable_products/sp_500/mini_spx_options/
- statistic: Share of matched snapshots with YES outside the band by > $0.02; signed mean of the violation.
- null: Share < 10%.
- procedure: Hourly during RTH: pull Kalshi/Polymarket S&P threshold contracts and the SPXW chain; compute the band from the two verticals around K; log violations and settlements; also Brier-score both the YES price and the band midpoint against outcomes; bootstrap the share by day.
- data: Kalshi/Polymarket contract data (available), CBOE delayed SPXW chain polled intraday (available, 15-min delay), SPX official closes. · min n: 100
- pass: Share >= 10% with the 95% CI excluding 10%.
- controls: Timestamp matching; fee-adjusted thresholds; exclude the last 30 minutes; placebo with thresholds shifted by one strike.
- blocked on: intraday SPXW snapshots matched to event prices must be captured from today (no chain history); ~3-5 trading days of hourly polling for n = 100
- note: from the options-library library: Event-contract vs vertical-spread replication (Kalshi/Polymarket digitals vs SPXW verticals); harness suggestion: mandel/options/digitals.py: implied_digital(chain, K1, width) + join to existing Polymarket/Kalshi clients; proper scoring already in the engine. | verifier: corrected claim/trial

### T-204 · earnings-straddle-buy-before

**Claim.** For US large-cap stocks, an ATM straddle in the first expiry after earnings, bought at the close 3 trading days before the announcement and sold at the last close before it, has a positive mean return on debit net of half the quoted bid/ask spread.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://www.cboe.com/tradable-products/0dte
- statistic: Mean per-trade return on debit with 95% studentized block-bootstrap CI (blocks by announcement week); secondary: mean dIV(T-3 -> T-1) vs mean theta decay as % of straddle.
- null: Mean net return <= 0 (IV ramp fully priced; theta >= ramp).
- procedure: For every earnings date in the capture window and every captured symbol: at close T-3 record the ATM straddle mid in the first post-earnings expiry; at the last pre-print close record the same straddle mid; return = (mid_exit - mid_entry - half-spread costs)/mid_entry. T-7 and T-10 entries are variants counted in the deflated-Sharpe trial count. Walk-forward: first season chooses any IV-percentile filter, later seasons test.
- data: Daily CBOE chain captures (bid/ask/IV) for ~200 liquid names from 2026-10-14; earnings dates from EDGAR 8-K Item 2.02 filings (free, not wired) or company IR calendars. · min n: 200
- pass: Bootstrap 95% CI for mean net return excludes 0 with point estimate > 1% of debit; deflated Sharpe p < 0.05.
- controls: Same structure on non-earnings 3-day windows for the same stocks (placebo); exclude windows with a VIX change > 10%; per-season sign test for stability.
- blocked on: daily chain capture through at least 1-2 earnings seasons (~90-180 days) for ~200 single names; earnings-date history (EDGAR, free, not wired).
- note: from the options-library library: Pre-earnings long straddle (buy the IV ramp, exit before the print); harness suggestion: Add an 'event window' harness: takes (symbol, event_date, offsets) and returns straddle mid/IV path from the chain store; reuse payoff engine for mark-to-market via BS reprice at captured IV. | verifier: corrected claim/trial

### T-205 · earnings-hold-through-straddle

**Claim.** Among US large-cap earnings events with IM/HM < 0.8 (IM = 0.845*ATM straddle/S at the T-1 close, HM = median |gap| over the prior 8 prints), an ATM straddle bought at the T-1 close and sold at the T+1 open has a positive mean return on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Mean per-trade return on debit in the filtered bucket with bootstrap CI; unfiltered mean and hit rate reported as the base-rate control.
- null: Filtered mean return <= 0.
- procedure: Record straddle mid at the T-1 close and at the T+1 open (or reprice with the T+1 captured IV and the opening gap when no intraday snapshot exists); compute IM and HM; bucket by IM/HM; threshold chosen on the first season, tested walk-forward.
- data: Daily chain capture + daily OHLC for ~200 names (single-name OHLC free, not wired); earnings dates from EDGAR. · min n: 300
- pass: Filtered-bucket mean > 0 with 95% CI excluding 0 out-of-sample, with at least 60 filtered events.
- controls: Placebo: same filter on random non-earnings nights; shuffled IM/HM labels; drop the top-3 winners and re-test; unfiltered mean expected < 0.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history; T+1 marks (needs the T+1 chain capture for the IV crush).
- note: from the options-library library: Hold-through-earnings long straddle/strangle (realised move > implied move); harness suggestion: Implied-move vs realised-move table per symbol-quarter stored as a first-class dataset; it feeds this and the three short-vol earnings entries. | verifier: corrected claim/trial

### T-206 · earnings-iv-crush-short-strangle

**Claim.** Selling a 1x-implied-move strangle in the first post-earnings expiry at the T-1 close and covering at the T+1 open has a positive mean P&L on Reg-T margin, net of half-spreads, across US large-cap earnings.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/short-strangle
- statistic: Mean P&L as % of margin with bootstrap CI; hit rate, 5% CVaR and mean/CVaR reported for sizing.
- null: Mean P&L <= 0.
- procedure: From the implied-move dataset: strangle credit at the T-1 close, value at the T+1 open (reprice with T+1 captured IV and the gap); subtract spread costs; aggregate by season; walk-forward IM/HM filter.
- data: Daily chain captures + daily OHLC; earnings dates. · min n: 300
- pass: Mean > 0 with 95% CI excluding 0 on out-of-sample seasons; mean/CVaR(5%) >= 0.1 required before sizing above 1% of capital.
- controls: Random-night placebo; IM/HM terciles to check monotonicity; drop the 5 largest losses and confirm the sign is unchanged (robustness, not proof).
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings IV-crush short straddle/strangle; harness suggestion: Short-vol event harness reporting CVaR and Kelly fraction alongside mean; margin model (Reg-T formula) in the payoff engine so P&L can be reported on margin. | verifier: corrected claim/trial

### T-207 · earnings-iron-condor

**Claim.** An iron condor with shorts at 1x implied move and longs at 2x implied move, sold at the T-1 close and covered at the T+1 open, has a positive mean return on max loss net of four half-spreads across US large-cap earnings.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/short-strangle, https://www.cboe.com/tradable-products/0dte
- statistic: Mean return on max loss with bootstrap CI; secondary: paired difference in mean/CVaR(5%) vs the naked 1x-IM strangle on the same prints.
- null: Mean return on max loss <= 0.
- procedure: Same pipeline as the short strangle, adding the long wings at 2x IM; per-print paired comparison; walk-forward IM/HM filter.
- data: Daily chain captures + daily OHLC; earnings dates. · min n: 300
- pass: Mean > 0 with 95% CI excluding 0 out-of-sample.
- controls: Placebo nights; spread-cost sensitivity (0.5x, 1x, 1.5x quoted half-spread); sector stratification.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings iron condor / iron butterfly (defined-risk IV crush); harness suggestion: Payoff engine already handles 4-leg structures; add a 'paired structures on same event' comparator to the trial runner. | verifier: corrected claim/trial

### T-209 · pre-earnings-calendar

**Claim.** An ATM calendar short the last pre-earnings weekly and long the first post-earnings expiry, opened 10-15 trading days before the print and closed at the near expiry, has a positive mean return on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Mean return on debit, hit rate, bootstrap CI.
- null: Mean return <= 0.
- procedure: From chain captures, mark both legs at entry and at the near-expiry close; compute return; test monotonicity across terciles of term-structure slope (IV_far - IV_near) at entry.
- data: Daily chain captures with weekly expiries for ~200 names; earnings dates. · min n: 200
- pass: Mean > 0 with 95% CI excluding 0; flattest-slope tercile outperforms steepest.
- controls: Same calendar in windows with no earnings between the expiries (placebo); exclude names with an ex-date between legs.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Pre-earnings long calendar (sell pre-event expiry, buy event expiry); harness suggestion: Term-structure slope per symbol per day (IV_near vs IV_event) as a stored feature; mark-to-market via BS reprice. | verifier: corrected claim/trial

### T-210 · earnings-reverse-calendar

**Claim.** Selling the ATM straddle in the first post-earnings expiry and buying a vega-matched ATM straddle in the following monthly, entered at the T-1 close and closed at the T+1 open, has a positive mean P&L net of half-spreads across US large-cap earnings.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/short-strangle, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean P&L with bootstrap CI; secondary: paired Sharpe difference vs the naked short straddle on the same prints.
- null: Mean P&L <= 0.
- procedure: Chain-capture marks at the T-1 close and T+1 (reprice the far leg with captured T+1 IV); per-print P&L for both structures; paired bootstrap.
- data: Daily chain captures incl. monthly expiries; earnings dates. · min n: 250
- pass: Mean > 0 with 95% CI excluding 0 out-of-sample.
- controls: Placebo nights; vega-ratio sensitivity (0.3, 0.4, 0.5); exclude prints within 5 days of index opex.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings reverse calendar / event forward-variance sale (sell event expiry, buy next); harness suggestion: Add forward-variance calculator (sigma_fwd^2 = (s2^2 T2 - s1^2 T1)/(T2-T1)) to the engine; event vol = s1^2 T1 - sigma_fwd^2 * T1. | verifier: corrected claim/trial

### T-211 · pead-vertical-spread

**Claim.** A 30-45 DTE ATM/+5% call debit spread bought at the T+1 close after a top-decile positive earnings gap that closes in the top 20% of its day range earns a higher mean return on debit over 30 trading days than the same spread bought on matched random days for the same stocks.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Mean return on debit minus matched random-day spread return, bootstrap CI; underlying 30-day drift as a sanity check.
- null: Event spread return <= random-day spread return.
- procedure: Underlying leg first: sort post-earnings gaps by size/direction, measure 30-day drift (single-name closes + earnings dates). Option leg: mark the spread at the T+1 close and 30 days later from chain captures (or BS-reprice with captured IV).
- data: Earnings dates (EDGAR) and gap size as surprise proxy (consensus is not free); single-name daily OHLC; chain captures. · min n: 200
- pass: Mean excess return > 0 with 95% CI excluding 0 over at least 2 non-overlapping seasons.
- controls: Match on SPY return over the holding period; size terciles; random-day placebo; bear-spread mirror after negative gaps.
- blocked on: earnings-date history + single-name daily OHLC (free, not wired); chain capture for option-level marks (30+ days after each entry).
- note: from the options-library library: Post-earnings announcement drift (PEAD) with vertical spreads; harness suggestion: Reuse the underlying 'event drift' harness for the stock leg; BS-reprice the spread with captured IV for the option overlay. | verifier: corrected claim/trial

### T-212 · dividend-runup-options

**Claim.** For US stocks with trailing dividend yield > 3%, a 70-delta call in the first expiry after the ex-date, bought at the close 10 trading days before the ex-date and sold at the last cum-dividend close, has a positive mean return on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Mean return on debit with bootstrap CI; underlying excess return (event window minus matched non-event window) as the mechanism check.
- null: Mean call return <= 0.
- procedure: Build the ex-date calendar; for each (stock, ex-date) mark the 70-delta call from chain captures at entry and exit; compute the underlying 10-day pre-ex return and a matched control.
- data: Ex-dividend dates (Nasdaq dividend calendar / EDGAR, free, not wired), single-name daily closes, chain captures. · min n: 500
- pass: Mean call return > 0 with 95% CI excluding 0.
- controls: Same stocks on random dates; SPY-adjusted returns; yield-tercile monotonicity.
- blocked on: ex-dividend date history and single-name closes (free, not wired); chain capture for call marks (~1 quarter for 500 ex-dates across a broad universe).
- note: from the options-library library: Dividend run-up and ex-dividend option plays; harness suggestion: Event-drift harness with 'declaration-to-ex' and 'ex-to-pay' windows; add early-exercise check (extrinsic vs dividend) to the engine. | verifier: corrected claim/trial

### T-213 · index-inclusion-options

**Claim.** For S&P 500 additions announced since 2020, a 1-month ATM/+8% call spread bought at the first post-announcement open and sold at the effective-date close has a positive mean return on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean return on debit; underlying excess return vs SPY over the same window; bootstrap CIs.
- null: Mean spread return <= 0.
- procedure: Collect S&P DJI index-change announcements (announcement and effective dates); mark the spread from chain captures (or BS with captured IV); post-effective 20-day window as the reversal variant.
- data: S&P DJI press release history (needs scraping; spglobal.com blocks plain fetches), single-name OHLC, chain captures. · min n: 60
- pass: Mean > 0 with 95% CI excluding 0.
- controls: Matched non-included stocks of similar size and momentum; placebo dates; separate bucket for direct adds after IPO/spin-off.
- blocked on: index-change announcement history (scrape), single-name OHLC; chain capture for option marks (about 60 additions take 1-2 years at current turnover).
- note: from the options-library library: Index inclusion / rebalance options (S&P 500 adds, Russell reconstitution); harness suggestion: Generic 'two-window event' harness (announce->effective, effective->+20d). | verifier: corrected claim/trial

### T-217 · 0dte-iron-condor-positive-gex

**Claim.** A 0DTE SPXW iron condor sold at 10:00 ET with shorts at +/-0.6% and wings at +/-1.0% has a higher mean return on max loss on days when the prior-close estimated dealer gamma is positive than on days when it is negative.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable-products/0dte, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean return on max loss by GEX sign, difference with bootstrap CI; hit rate; CVaR; overall mean after fees.
- null: Mean(positive GEX) <= Mean(negative GEX).
- procedure: Prior-close chain captures give OI and Greeks -> GEX estimate; a 10:00 ET SPXW snapshot gives entry credit; SPX 4pm close gives settlement.
- data: SPX chain captures (prior close OI + 10:00 ET snapshot), SPX daily close; accumulating from 2026-10-14. · min n: 120
- pass: GEX-sign difference > 0 with 95% CI excluding 0 over >= 120 trading days.
- controls: Shuffle GEX labels; exclude event days; 'sell every day' baseline; fee sensitivity.
- blocked on: daily chain capture (~120 trading days) plus an added 10:00 ET SPXW snapshot; GEX estimator.
- note: from the options-library library: 0DTE SPX iron condor in positive dealer-gamma regime; harness suggestion: Add a second intraday capture of SPX chains at 10:00 ET; GEX estimator from OI*gamma; 0DTE P&L via settlement price. | verifier: corrected claim/trial

### T-218 · 0dte-long-straddle-negative-gex

**Claim.** A 0DTE ATM SPXW straddle bought at 10:00 ET and held to settlement has a positive mean return on debit on days when the prior-close estimated dealer gamma is negative.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable-products/0dte, https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data
- statistic: Mean return on debit by GEX sign, bootstrap CI; share of days with |move| > implied.
- null: Mean(negative GEX) <= 0.
- procedure: GEX from prior-close chain captures; entry debit from a 10:00 ET snapshot; settlement from the 4pm SPX close; stratify by GEX sign and event flag. Interim proxy (MODEL-PRICED, no GEX): unconditional 1-day straddle at VIX-as-IV using SPY closes.
- data: SPX chain captures + SPX daily close; VIX for proxy pricing. · min n: 120
- pass: Negative-GEX mean > 0 with 95% CI excluding 0 (expect roughly 30-40 negative-GEX days in 120).
- controls: Shuffle GEX; event-day exclusion; compare with the unconditional 0DTE straddle (expected negative).
- blocked on: daily chain capture (~120+ trading days, more if negative-GEX days are rare) for GEX plus a 10:00 ET snapshot.
- note: from the options-library library: 0DTE SPX long straddle on negative dealer-gamma / event days; harness suggestion: Same GEX estimator and 10:00 ET snapshot as the condor; report conditional on GEX sign and on event flag. | verifier: corrected claim/trial

### T-220 · vix-settlement-soq

**Claim.** A VIX call credit spread (short front-future+2, long +5 higher) expiring at the Wednesday SOQ and sold 3 trading days before settlement when VIX3M/VIX > 1.1 has a positive mean return on max loss net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/tradable_products/vix/vix_options/, https://www.cboe.com/tradable_products/vix/vix_options/specifications/
- statistic: Mean return on max loss with bootstrap CI; preliminary: mean (VRO - VIX close on the prior day) on settlement days vs mean daily VIX change on other Wednesdays.
- null: Mean return <= 0.
- procedure: Settlement calendar since 2006 (computable); front-future level from Cboe CFE settlement history; option entry credit from captured VIX chains (from today) or Black-76 with VVIX as vol-of-vol (MODEL-PRICED); settlement from VRO (free Cboe CSV since 2008).
- data: VIX, VIX3M daily OHLC (listed); VRO and VVIX daily history (free Cboe CSVs, not in the current list); VIX futures settlement history (free CFE files, not wired); VIX option chain captures from 2026-10-14. · min n: 60
- pass: Mean > 0 with 95% CI excluding 0.
- controls: Backwardation subsample; non-settlement Wednesdays for the SOQ-deviation check; exclude 2008, 2018-02, 2020-03 as robustness.
- blocked on: VIX futures settlement history (free CFE files, not wired) plus either VIX chain capture (~12+ monthly settlements) or a VVIX-based model price; VRO history (free) enables the preliminary SOQ test.
- note: from the options-library library: VIX settlement (Wednesday SOQ) trades; harness suggestion: VIX settlement calendar generator + VIX/VIX3M OHLC event harness; add VIX futures history fetch (Cboe CFE CSVs) for the futures-based version. | verifier: corrected claim/trial

### T-222 · crypto-catalyst-strangle

**Claim.** For hard-dated BTC/ETH catalysts, a 25-delta strangle in the first expiry after the date, bought 21 days before and sold 1 day before, has a positive mean return on debit net of fees.

- kind: options-strategy · origin: options-library:event-driven, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false, https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data
- statistic: Mean return on debit; mean change in event-expiry IV minus change in DVOL over the window; exact sign test given small n.
- null: Mean return <= 0.
- procedure: Capture event-expiry mark IV and DVOL daily from the Deribit public book (from today); for each catalyst compute window statistics; cross-check with Polymarket odds for the event.
- data: Deribit book captures (mark IV by expiry), DVOL, catalyst calendar, Polymarket event odds. · min n: 20
- pass: Sign test p < 0.05 and mean > 0 with 95% CI excluding 0 once n >= 20.
- controls: Non-catalyst 21-day windows; DVOL-only control; ETF-type vs protocol-type split.
- blocked on: Deribit expiry-level IV capture across >= 20 hard-dated catalysts (years at current frequency; partial evidence after 3-5).
- note: from the options-library library: Crypto scheduled-catalyst strangle (ETF decisions, halving, protocol upgrades); harness suggestion: Catalyst calendar table joined to Deribit expiry-level IV captures and Polymarket odds; report IV ramp per event. | verifier: corrected claim/trial

### T-225 · binary-catalyst-pdufa-strangle

**Claim.** For FDA PDUFA dates on small-cap biotechs, a 25%/45%-OTM asymmetric strangle bought 5 trading days before the date and sold at the first open after a decision (or at the date +1 close if delayed) has a positive mean return on debit, delays included.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Mean return on debit with delays included; hit rate; decided-only mean reported separately; bootstrap CI.
- null: Mean return <= 0 including delays.
- procedure: Build a PDUFA calendar (company 8-Ks/press releases; FDA describes the review process but publishes no calendar); chain captures for the strangle marks; daily OHLC for the move; walk-forward on an implied-probability filter.
- data: PDUFA/ruling calendar; chain captures; single-name OHLC; Polymarket/Kalshi odds where listed. · min n: 80
- pass: Mean > 0 with 95% CI excluding 0 including delays.
- controls: Random biotech non-event windows; XBI-adjusted moves; exclude large-cap pharma; calibration of implied vs realised approval rate as a diagnostic.
- blocked on: PDUFA calendar history + chain captures across >= 80 decisions (roughly 12 months).
- note: from the options-library library: Binary-catalyst strangle vs condor (FDA PDUFA, court rulings, merger votes); harness suggestion: Bimodal implied-distribution fitter (two-point mixture) from the chain; comparator with Polymarket/Kalshi odds. | verifier: corrected claim/trial

### T-226 · earnings-risk-reversal-skew

**Claim.** For US stocks whose pre-earnings 25-delta put-minus-call IV skew in the event expiry is in the top decile of its own history, a 25-delta long put / short call risk reversal opened at the T-1 close and closed at the T+1 open has a positive mean P&L per unit of spot net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/short-strangle, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Mean P&L per unit spot with bootstrap CI; Spearman between skew decile and T+1 open return as mechanism check.
- null: Mean P&L <= 0.
- procedure: From chain captures interpolate 25-delta IVs at the T-1 close; sort into deciles; reprice at T+1 captured IV and opening gap; walk-forward decile cutoffs.
- data: Daily chain captures (IV by delta), earnings dates, daily OHLC. · min n: 300
- pass: Top-decile mean > 0 with 95% CI excluding 0 out-of-sample (at least 30 top-decile events).
- controls: Placebo nights; control for prior-month return; sector dummies; hypothesis-A structure as the opposite-sign check.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings risk reversal (skew mean-reversion into the print); harness suggestion: Skew-by-delta extractor from the chain capture (interpolate IV at 25-delta) stored per symbol-day; shared with the skew-family harness already built. | verifier: corrected claim/trial

### T-230 · smile_curvature_butterfly

**Claim.** 30-DTE SPY credit iron butterflies (short ATM straddle, long 25-delta strangle) entered at the captured mid and held to expiry have a positive mean P&L per unit of max loss after paying half the quoted bid/ask on every leg.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean of P&L / max loss per cycle; secondary: regression of the entry 25d butterfly (average wing IV minus ATM IV) on realised 30d excess kurtosis.
- null: Mean <= 0.
- procedure: Daily SPY/_SPX captures (surface_summary has ATM and 25d IVs and straddle mids; strike-level mids come from the raw chain). One entry per monthly expiry, held to expiry. A 7-DTE weekly version is a declared secondary that reaches 36 cycles in ~36 weeks. Studentized bootstrap clustered by expiry; walk-forward once 2 years exist.
- data: Daily CBOE chain capture (SPY, _SPX) from 2026-10-14; SPY/^GSPC closes. · min n: 36
- pass: Mean P&L/max loss > 0 at p < 0.05 over at least 36 cycles, with the same sign in both halves.
- controls: ATM short straddle alone over the same cycles (separates the level VRP from the curvature premium); vega-neutral variant; BS flat-smile control (zero curvature premium by construction).
- blocked on: daily chain capture: ~36 monthly cycles (~3 years) for the 30-DTE test, ~36 weeks for the 7-DTE secondary; a 90-day capture gives a first read on butterfly levels vs realised kurtosis.
- note: from the options-library library: Smile curvature trade (butterfly vs straddle, kurtosis); harness suggestion: New harness_smile_curvature: compute 25d butterfly from surface_summary per capture day; P&L via build_position + payoff engine. | verifier: corrected claim/trial

### T-236 · dispersion_index_vs_components

**Claim.** Cboe COR1M (implied correlation of the top-50 SPX constituents) exceeds the subsequently realised 21-day correlation of the same constituents, computed with the same formula on realised vols and index weights, on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://en.wikipedia.org/wiki/Dispersion_trading, https://en.wikipedia.org/wiki/Variance_swap
- statistic: Mean of COR1M_t/100 - rho_real(t..t+21), with rho_real = (RV_idx^2 - sum w_i^2 RV_i^2) / (sum_{i!=j} w_i w_j RV_i RV_j).
- null: Mean <= 0 (no correlation risk premium).
- procedure: COR1M daily since 2006-01 (archive) vs realised correlation from constituent closes and point-in-time weights; non-overlapping 21d windows (~240); studentized block bootstrap; walk-forward. The P&L leg runs once 60+ daily captures of the top-20 components exist.
- data: CBOE COR1M and DSPX history (archive); daily closes and weights of the top-50 SPX constituents (NOT in the archive); constituent chain capture for the P&L. · min n: 120
- pass: Mean gap > 0.05 with the 95% CI excluding zero; positive in both halves; crisis months (VIX > 30) reported separately.
- controls: VIX-tercile stratification; equal-weight vs cap-weight realised correlation; sector-ETF realised correlation (archive) as a cross-check.
- blocked on: daily closes and point-in-time weights of the top-50 SPX constituents (implied side COR1M is reachable now); constituent chain capture ~60 days for a first P&L read.
- note: from the options-library library: Dispersion trade (short index vol, long component vol); harness suggestion: New harness_dispersion: pull COR1M/DSPX via cboe_index_history, component closes via the fetch layer, compute implied-minus-realised correlation; P&L via build_position per component once captures exist. | verifier: corrected claim/trial

### T-248 · event_implied_move_vs_realised

**Claim.** Across US large-cap earnings events, the mean ratio of the realised move |S_expiry - K_ATM| to the ATM straddle mid captured the day before the announcement (first expiry after the event) is below 0.85.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://www.optionseducation.org/strategies/all-strategies/short-straddle, https://www.deribit.com/kb/options
- statistic: Mean of |S_T - K|/C0 per event; equivalently, mean short-straddle P&L as a fraction of C0 = 1 - mean ratio, after a 5% spread cost.
- null: Mean ratio >= 0.85.
- procedure: Implied move from the captured chain the day before each earnings date; realised move to the first post-event expiry; pooled across names; studentized bootstrap clustered by date; walk-forward across seasons; deflated over the name filters tried.
- data: Daily chain capture of >= 50 large caps (CHAIN_SYMBOLS currently has only TSLA, NVDA and AAPL as single names), an earnings-calendar feed, daily closes. · min n: 200
- pass: Upper 95% bound of the mean ratio < 0.85; no single event contributes > 20% of total P&L.
- controls: Non-event days with the same DTE (should show the ordinary, smaller VRP); shuffled event-date placebo.
- blocked on: chain capture of >= 50 large caps (add to CHAIN_SYMBOLS; 3 names give only ~12 events a year), ~4 quarterly seasons to reach 200 events, plus an earnings-calendar feed.
- note: from the options-library library: Event vol: implied move vs realised move (earnings / macro straddles); harness suggestion: harness_implied_move exists; add an event-date join and the realised/implied ratio statistic. | verifier: corrected claim/trial

### T-250 · sector_correlation_trade

**Claim.** Implied cross-sector correlation computed from SPY and the nine original SPDR sector ETFs' 30-day ATM IVs exceeds the subsequently realised 21-day correlation of the same ETFs (same formula on realised vols, SPY sector weights) by more than 0.05 on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://en.wikipedia.org/wiki/Dispersion_trading, https://www.cboe.com/tradable_products/vix/vix_historical_data/
- statistic: Mean of rho_implied(t) - rho_realised(t..t+21).
- null: Mean <= 0.05.
- procedure: Daily chain captures of SPY and the 9 sectors give implied correlation per day; realised correlation from the archived sector closes; non-overlapping 21d cycles; studentized block bootstrap; walk-forward after 2 years.
- data: Daily CBOE chain capture of SPY plus XLB/XLE/XLF/XLI/XLK/XLP/XLU/XLV/XLY (sector chains are NOT yet in CHAIN_SYMBOLS); sector closes are archived (XLRE and XLC are missing and have short histories). · min n: 36
- pass: Lower 95% bound of the mean > 0.05 over at least 36 cycles; positive in > 65% of non-crisis months (reported).
- controls: COR1M as an external implied-correlation check; VIX-tercile stratification; crisis months (VIX > 30) reported separately.
- blocked on: daily chain capture of the 9 sector ETFs (add to CHAIN_SYMBOLS): ~60 days for a first read, ~36 monthly cycles (~3 years) for the test. The realised side can be computed now from the archived sector closes.
- note: from the options-library library: Correlation trade via index vs sector/sub-basket straddles (QQQ vs XLK, SPY vs sector ETFs); harness suggestion: Same harness_dispersion as the index-vs-components entry with the sector list; implied correlation from surface_summary ATM IVs. | verifier: corrected claim/trial

### T-251 · skew_term_structure

**Claim.** Conditional on SPY's 30-day 25-delta put-minus-call IV skew exceeding its 90-day skew at entry, the delta-hedged short-near/long-far skew position held for 21 trading days has a positive mean P&L.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf, https://www.deribit.com/kb/options
- statistic: Mean 21-trading-day P&L of the hedged four-leg position (build_position on captured mids), per unit of near vega; secondary: mean 21d change in skew_30d - skew_90d.
- null: Mean P&L <= 0.
- procedure: Daily captures give surface_summary skew25 at the expiries nearest 30 and 90 DTE; entries on signal days, non-overlapping 21d holds; studentized bootstrap clustered by entry month; walk-forward after 2 years.
- data: Daily CBOE chain capture (SPY, _SPX, GLD, IBIT) from 2026-10-14; SKEW index history as a level control. · min n: 36
- pass: Mean P&L > 0 at p < 0.05 over at least 36 signal cycles.
- controls: Flat-vega single-expiry risk reversal; unconditional (all days) version; SKEW-level stratification.
- blocked on: daily chain capture: ~90 days to see how often the signal fires, and ~36 signal cycles (likely 3+ years) for the P&L test.
- note: from the options-library library: Skew term-structure trade (near vs far put skew); harness suggestion: surface_summary already stores 25d put/call IV per expiry; add a per-day skew-term series and feed build_position with two expiries. | verifier: corrected claim/trial

### T-252 · straddle_vix_basis

**Claim.** The 30-day SPX smile premium VIX - sigma_ATM(30d) exceeds the subsequently realised convexity premium RV_21d - sqrt(pi/2)*mean|r_daily|*sqrt(252) on average.

- kind: options-strategy · origin: options-library:volatility-surface-relative-value, https://en.wikipedia.org/wiki/Variance_swap, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: Mean of [VIX_t - 100*sigma_ATM,t] - [RV_{t,t+21} - sqrt(pi/2)*mean|r|*sqrt(252)] (vol points). The second bracket is the excess of realised vol over its MAD-implied normal vol, i.e. the realised fat-tail contribution.
- null: Mean <= 0.
- procedure: Daily captures of SPX 30d ATM IV (surface_summary atm_iv, interpolated to 30 DTE) alongside VIX; non-overlapping 21d cycles; studentized block bootstrap. The realised-convexity series can be computed on history now to pre-register its distribution.
- data: Daily _SPX chain capture from 2026-10-14; CBOE VIX (archive); ^GSPC closes. · min n: 36
- pass: Mean > 0 with the 95% CI excluding zero over at least 36 cycles.
- controls: BS flat-smile control (premium zero by construction); SKEW stratification.
- blocked on: daily SPX chain capture: ~90 days for a first read of the basis series, ~36 monthly cycles (~3 years) for the test. The realised-convexity side can be computed on history now.
- note: from the options-library library: Straddle-vs-VIX basis (ATM straddle implied vs variance-swap strike); harness suggestion: Add VIX minus surface_summary ATM IV at the ~30d expiry as a daily series in harness_implied_move; the realised convexity statistic can be added to harness_vrp_spx today. | verifier: corrected claim/trial

### T-259 · deribit-conversion-reversal

**Claim.** In daily synchronous snapshots of Deribit BTC books, put-call-parity gaps at the ATM strike exceed round-trip fees at mid prices on fewer than 2% of (expiry, day) pairs.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=future&expired=false, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/
- statistic: Fraction of (expiry, day) pairs with |(c - p) - (1 - K/F)| > fees, at mid
- null: Fraction >= 2%
- procedure: Capture the BTC option book + futures marks in the same snapshot daily; compute the parity gap per expiry at the strike nearest F; count; report at touch prices too
- data: Deribit book + futures captures from 2026-10-14 (trade prints are asynchronous and too noisy for fee-level parity) · min n: 60
- pass: Fraction < 2% at mid (then archived as 'no retail edge'); any excess at touch prices flagged
- controls: Mid vs touch prices; exclude expiries < 1 day
- blocked on: daily synchronous Deribit book + futures capture, 60 days
- note: from the options-library library: Conversion / reversal basis arbitrage on Deribit inverse options; harness suggestion: Extend deribit_book to include futures mark; parity scan job | verifier: corrected claim/trial

### T-260 · deribit-box-spread

**Claim.** The BTC option-implied USD rate from boxes bracketing ATM on 30-90 DTE expiries exceeds the 3-month T-bill by more than 200 bp annualised on at least 70% of capture days.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name=BTC-30OCT26-70000-C
- statistic: Fraction of capture days with r_implied - DGS3MO > 2% (annualised, mid prices)
- null: Fraction <= 70%
- procedure: From daily synchronous book captures, price the box at mid for strikes bracketing ATM; solve for r; compare to FRED; repeat at bid/ask
- data: Deribit book captures from 2026-10-14; FRED DGS3MO · min n: 60
- pass: Fraction > 70% at mid (also report the median spread and bid/ask results)
- controls: Futures-basis implied rate on the same days (also back-testable from futures trade history)
- blocked on: daily synchronous Deribit book capture, 60 days (futures-basis proxy testable now)
- note: from the options-library library: Deribit box spread (synthetic coin lending / implied rate); harness suggestion: Parity/box scanner over stored book snapshots; FRED via fred_series | verifier: corrected claim/trial

### T-265 · btc-cross-venue-vol

**Claim.** IBIT 30-DTE ATM IV exceeds Deribit BTC 30-DTE ATM IV (same-day, interpolated to 30 days) by a median of more than 2 vol points over daily captures.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/, https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name=BTC-30OCT26-70000-C
- statistic: Daily ATM IV spread (IBIT - Deribit), median; sign test
- null: Median <= 2 vol points
- procedure: Daily CBOE IBIT chain capture (surface_summary ATM IV at 30 DTE) vs Deribit ATM mark_iv interpolated to 30 DTE at the same timestamp (~US close); HAC-corrected bootstrap of the median
- data: CBOE delayed IBIT chain (daily from 2026-10-14); Deribit book capture (from 2026-10-14) · min n: 60
- pass: Median > 2 with 95% CI excluding 2
- controls: Compare to DVOL (variance-swap level, expected above ATM) as a method check; QQQ ATM IV vs VXN for method sanity
- blocked on: daily chain capture, 60 days (IBIT chain history starts 2026-10-14)
- note: from the options-library library: Cross-venue BTC vol spread (IBIT/CME vs Deribit); harness suggestion: collect_options_daily already stores IBIT surface; join with deribit_dvol_history by date | verifier: corrected claim/trial

### T-276 · gold-contango-calendar

**Claim.** After fitting per-expiry forwards, GC (OG) ATM-forward implied vols at 1-, 2- and 3-month tenors match GLD ATM-forward implied vols at the same tenors within 1 vol point on average.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.law.cornell.edu/uscode/text/26/1256
- statistic: Mean |IV_GC,ATMF - IV_GLD,ATMF| by tenor
- null: Mean gap >= 1 vol point
- procedure: Daily GLD chain (CBOE, free from 2026-10-14) + OG quotes (broker API); fit forward per expiry from put-call parity; interpolate ATM-forward IV at fixed tenors; compare
- data: GLD chains (free from today); GC/OG quotes (not free: IBKR or CME data entitlement) · min n: 60
- pass: Mean gap < 1 vol point with CI (structural knowledge; no retail edge) or > 1 (venue spread worth a gld-gc-cross-venue trade)
- controls: Carry model from FRED DGS3MO minus a lease rate of 0-0.5%
- blocked on: CME GC/OG option quotes (paid or broker API entitlement); GLD side capturable now
- note: from the options-library library: Gold futures-options contango calendar (curve-aware); harness suggestion: Add a futures-forward field to surface_summary so GC chains can be fitted when a feed exists | verifier: corrected claim/trial

### T-277 · gld-gc-cross-venue

**Claim.** GLD 30-DTE ATM-forward IV exceeds GC (OG) 30-DTE ATM-forward IV by a median of more than 0.5 vol point on daily observations.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://www.law.cornell.edu/uscode/text/26/1256, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Median daily IV spread (GLD - OG); sign test
- null: Median <= 0.5
- procedure: GLD ATM IV from the CBOE chain (free); OG IV from a broker feed; fit forwards; interpolate both to 30 DTE; HAC-aware bootstrap
- data: GLD chain daily (free from 2026-10-14); OG quotes (paid) · min n: 60
- pass: Median > 0.5 with 95% CI above 0.5
- controls: SPY vs ES options as a comparison pair
- blocked on: CME OG option quotes (paid / broker API); GLD side capturable now
- note: from the options-library library: GLD vs GC (equity option vs futures option) cross-venue vol spread; harness suggestion: surface_summary for GLD already captured daily; add a broker-feed adapter later | verifier: corrected claim/trial

### T-278 · gdx-gld-dispersion

**Claim.** The ratio of GDX 30-DTE ATM IV to GLD 30-DTE ATM IV exceeds the ratio of their subsequent 30-day realised vols on average.

- kind: options-strategy · origin: options-library:crypto-metals-options, https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv
- statistic: Mean (IV ratio - forward RV ratio)
- null: Mean <= 0
- procedure: Daily CBOE chains for GDX and GLD; realised vol from closes; overlapping daily observations with HAC/block bootstrap for a pilot, non-overlapping windows for the verdict
- data: CBOE GDX and GLD chains (from 2026-10-14); GDX/GLD closes (Yahoo) · min n: 36
- pass: CI > 0 on non-overlapping windows
- controls: Replace GLD IV with GVZ as a check on chain-derived IV; VIX/VXN as equity-beta control
- blocked on: daily chain capture for GDX and GLD: ~90 days for an overlapping-window pilot (HAC, ~60 obs); ~3 years for 36 non-overlapping 30-day windows
- note: from the options-library library: Gold miners vs gold vol dispersion (GDX vs GLD); harness suggestion: Add GDX to CHAIN_SYMBOLS in mandel.data.options; dispersion harness | verifier: corrected claim/trial

### T-307 · xs-momentum-stocks-12-1

**Claim.** The 12-1 decile long-short portfolio on a point-in-time US large-cap universe earns a positive after-cost mean monthly return over 2000-2026, with the block-bootstrap 95% interval excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional, https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html (fetched), https://www.aqr.com/Insights/Research/Journal-Article/Fact-Fiction-and-Momentum-Investing (fetched)
- statistic: Mean monthly long-short return after costs; DSR over 24 trials; within-month rank-permutation p-value
- null: Mean = 0; ranks uninformative
- procedure: Build dated constituent table; download daily adjclose for all historical members including delisted names; monthly ranks; block bootstrap (block 12 months); permutation; DSR; missing-data audit
- data: Point-in-time constituents (not available) and delisted-stock price histories (Yahoo drops many delisted tickers) · min n: 300
- pass: Mean > 0 with 95% interval excluding 0, above the permutation 95th percentile, DSR > 0.95, and fewer than 10% constituent-months with missing prices (otherwise inconclusive)
- controls: Look-ahead: membership as of t; survivorship: delisted names mandatory, missing-data gate; costs: 10 bps per side plus 50 bps a year borrow on shorts; multiple testing: 24 trials; regime: with and without 2009 and 2020-11 (vaccine-day reversal)
- blocked on: Point-in-time membership and delisted-stock prices (EDGAR 403 from this host; Yahoo lacks most delisted tickers). An external, survivorship-clean reference is reachable now: Ken French's 10_Portfolios_Prior_12_2 CSV returned HTTP 200 in this pass, so a separate stage-1 claim on those published returns can run, but it does not test this constructed large-cap claim.
- note: from the underlying-library library: Cross-sectional stock momentum 12-1 (Jegadeesh-Titman) on a large-cap universe; harness suggestion: Stage 1 (now): fetch Ken French 10 momentum portfolios (free CSV) as a reference series and test the claim on those returns (external, but survivorship-clean). Stage 2: constituents table + Yahoo closes; trend.py xs_momentum reused; add a missing-data audit that gates the verdict to inconclusive. | verifier: corrected claim/trial

### T-327 · gold-etf-futures-basis-and-trust-premium

**Claim.** PHYS's premium/discount to NAV 2015-2026 is stationary with half-life under 60 trading days, and buying PHYS vs GLD at discount < -2% and unwinding at > -1% earns a positive return net of 10 bps per leg and the fee differential.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://doi.org/10.2307/2946710, https://www.nber.org/papers/w3465
- statistic: ADF/half-life of the discount series; net return per round trip and Sharpe
- null: discount is a random walk (no reversion); zero net return
- procedure: build discount series; ADF with bootstrap; simulate the rule; compare to GLD-only control
- data: PHYS and GLD prices from Yahoo (now); PHYS daily NAV/premium history from Sprott or CEFConnect (not in the free set; Sprott page returned 503, CEFConnect API 500 at test) · min n: 1000
- pass: half-life < 60 days with interval excluding non-stationarity AND net return > 0 with interval excluding 0
- controls: look-ahead: NAV published after close (use next-day execution); costs: PHYS spread ~5 bps, GLD borrow; fee differential PHYS 0.41% vs GLD 0.40%; regime: 2020 stress; multiple testing across the 5 variants
- blocked on: PHYS/CEF daily NAV and premium history (Sprott or CEFConnect download; one scrape job) and individual-month GC contract settlements for a clean basis (CME delayed data or Yahoo per-contract tickers GCZ26.CMX, untested)
- note: from the underlying-library library: Gold ETF vs COMEX futures basis, and physical-trust premium/discount reversion; harness suggestion: trust_discount_reversion: generic premium/NAV stationarity + rule simulator; basis_calc for futures vs ETF implied financing

### T-335 · polymarket-multi-outcome-bundle-arb

**Claim.** Across 60-second snapshots of all live Polymarket negRisk events over 30 days, the sum of best YES asks plus taker fees is below 1 with at least $20 of depth on every leg in at least 1% of event-snapshots.

- kind: underlying-strategy · origin: underlying-library:mean-reversion-statarb, https://arxiv.org/abs/2508.03474, https://www.ubplj.org/index.php/jpm/article/view/1796
- statistic: rate of after-fee, depth-qualified mispricings per event-snapshot (Wilson interval); diagnostics: persistence across consecutive snapshots, annualized yield on locked capital vs DTB3
- null: zero after-fee mispricings (consistent with T-04)
- procedure: Extend bundle_arb_scan to the event level: Gamma /events (negRisk flag) plus CLOB books per token, every 60 s for 30 days, with the per-category fee formula and depth filter. Wilson intervals. Report by category and by the number of outcomes n.
- data: Polymarket Gamma events (negRisk verified live) + CLOB order books, captured forward; the archived 300-book snapshot as a seed · min n: 2000
- pass: lower Wilson bound of the rate >= 1% AND median annualized yield on locked capital > DTB3 + 2%
- controls: Fees per category formula. Gas/approvals on Polygon. Depth threshold. Resolution-rule risk: an 'exhaustive' set that is not exhaustive (e.g. an unlisted 'other') is audited per event. Snapshots are a time sample. Capital lock to resolution vs T-bills. No free parameters, but the category breakdown is reported.
- blocked on: No historical order-book archive: the executable claim needs 30 days of forward 60-second book capture (free endpoints, collector startable today; first verdict ~30 days after start). The historical last-price proxy is runnable now as a diagnostic only.
- note: from the underlying-library library: Prediction-market multi-outcome bundle arbitrage (negRisk sums and combinatorial dependencies); harness suggestion: negrisk_bundle_scan: event-level extension of bundle_arb_scan with per-category fees, depth, persistence; ladder_monotonicity_check for nested markets | verifier: corrected claim/trial

### T-338 · post-earnings-announcement-drift

**Claim.** Over 2010-2026, among US stocks outside the 500 largest by dollar volume, a dollar-neutral portfolio long the top and short the bottom decile of CAR(-1,+1) earnings surprises, entered at the close of day +1 and held 60 trading days, earns a positive mean return net of 20 bps round-trip costs and 2%/yr short borrow, with both halves (2010-2017, 2018-2026) positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w13090, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607
- statistic: Mean net 60-day long-short return per cohort (bps), and the annualized Sharpe of the rolling-cohort daily series.
- null: Zero mean. Test with a studentized block bootstrap (block 63 days) of the daily long-short series. Placebo: each stock's announcement dates are shifted by a random 20-120 trading days, keeping the cross-sectional structure.
- procedure: Walk-forward. Breakpoints come from the trailing 63 trading days of surprises. Entry is at the close of day +1 (available_at = day +1 close). Run the full grid, both halves and the placebo. Deflated Sharpe over all declared trials: 2 surprise definitions x 2 horizons x 4 portfolio forms (L/S, long-only, sector-hedged, large-cap control) = 16.
- data: Earnings dates, EPS and consensus: api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD is keyless and verified to return rows from 2009 with EPS, consensus and % surprise. It is survivor-only (current tickers; no delisted names seen) and the consensus vintage is unknown. Alpha Vantage EARNINGS (25 calls/day free) is a cross-check. Prices: Yahoo daily OHLC, which lacks delisted names. The pass needs a delisted-inclusive universe. · min n: 2000
- pass: Mean net 60-day L/S return > 0 with bootstrap p < 0.05; DSR > 0.95 over 16 trials; both halves positive; placebo mean indistinguishable from 0. A survivor-only pilot is reported as biased upward and cannot pass the claim.
- controls: Look-ahead: day-0 timing rule, breakpoints from past cohorts only, consensus captured before release (Nasdaq consensus vintage unverified, flagged). Survivorship: delisted names are required; the Nasdaq calendar and Yahoo are survivor-only. Costs: 20 bps round trip plus 2%/yr borrow; 40 bps sensitivity for the smallest names. Multiple testing: 16 trials, DSR/PBO. Regime: halves; 2020-Q1 excluded as a sensitivity.
- blocked on: A survivorship-free universe. The keyless Nasdaq earnings calendar (verified, 2009-) lists only currently listed tickers, and Yahoo has no prices for delisted stocks, so any run now is survivor-biased. Needed: delisted-inclusive dates and prices (EDGAR 8-K item 2.02 dates from the user's server, plus a delisted-price source).
- note: from the underlying-library library: Post-earnings announcement drift (PEAD); harness suggestion: mandel/experiments/events.py: pead(announcements: list[dict{symbol, report_date, before_open: bool, surprise}], prices: dict[symbol -> (days, closes)], horizon=60, cost_bps=20) -> rolling-cohort long-short daily series; reuse block_bootstrap_pvalue and deflated_sharpe_ratio; add shift_placebo() that re-dates announcements. | verifier: corrected claim/trial

### T-339 · earnings-announcement-premium

**Claim.** Over 2010-2026, an equal-weighted portfolio of US expected earnings announcers (same calendar month a year earlier) outperforms non-announcers by at least 50 bps per month net of 10 bps round-trip costs, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w13090
- statistic: Mean monthly spread, announcers minus non-announcers (bps), with its Newey-West (lag 3) t-statistic.
- null: Zero spread. Test with a studentized block bootstrap of the monthly spread series (block 6 months).
- procedure: The expected-announcer flag uses only announcements at least 11 months old (point-in-time). Monthly rebalance; halves 2010-2017 / 2018-2026; all 5 variants count as trials (DSR).
- data: Nasdaq keyless earnings calendar (verified 2009-, survivor-only) for announcement months, plus Yahoo daily closes. The SPY aggregate arm needs only daily-history-SPY. · min n: 150
- pass: Spread > 50 bps/month with p < 0.05, both halves positive, still > 20 bps value-weighted, and DSR > 0.95 over 5 trials, on a survivorship-free universe.
- controls: Look-ahead: lagged announcement history only. Survivorship: delisted names required (blocked). Costs: 10 bps round trip at about 100% monthly turnover per leg. Multiple testing: 5 variants. Regime: halves; 2020 excluded as a sensitivity.
- blocked on: A survivorship-free cross-section of announcement dates and prices. The Nasdaq calendar (verified keyless from 2009) and Yahoo are survivor-only. Only the aggregate SPY earnings-season arm is testable now, and it does not test the claim.
- note: from the underlying-library library: Earnings announcement premium (pre-announcement run-up); harness suggestion: events.py: expected_announcers(dates) -> monthly membership; announcement_premium(membership, prices) -> spread series; aggregate arm: calendar_window_effect(days, closes, window_fn) reused from turn_of_month with a 'heavy earnings week' flag. | verifier: corrected claim/trial

### T-340 · index-inclusion-deletion

**Claim.** Over 2010-2026, S&P 500 additions earn a positive mean SPY-adjusted return of at least 50 bps from the close of the first trading day after the announcement to the effective-date close, net of 10 bps round-trip costs, with both halves positive.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://www.nber.org/papers/w30748, https://www.nber.org/papers/w19290
- statistic: Mean SPY-adjusted return from close A+1 to close E (bps) across additions.
- null: Zero mean abnormal return. Test by bootstrap over events clustered by effective date. Placebo: the same stocks over randomly dated windows of equal length, drawn from 60-250 days after inclusion.
- procedure: Event study with SPY-adjusted returns. A is the press-release timestamp (available_at). Halves 2010-2017 / 2018-2026. All 6 variants count as trials (Holm). The ETF arm runs now via reconstitution_week().
- data: A point-in-time list of S&P 500 changes with announcement and effective dates (S&P DJI press releases; not tested from this host). Wikipedia's changes table carries mostly effective dates, not announcements. Yahoo daily closes, which lack prices for deleted names that later delisted. ETF arm: daily-history-IWM and daily-history-SPY (stored). · min n: 150
- pass: Mean > 50 bps net, cluster-bootstrap p < 0.05, both halves positive, placebo indistinguishable from 0, Holm-adjusted over 6 trials.
- controls: Look-ahead: the announcement timestamp, not the effective date, defines entry. Survivorship: deletions are often delisted later; prices must be sourced or the arm marked biased. Costs: 5-15 bps round trip in large caps. Multiple testing: 6 variants, Holm. Regime: halves; decay is the pre-registered expectation.
- blocked on: A point-in-time index-change list with announcement and effective dates, plus prices for later-delisted deletions. The ETF reconstitution-week arm is testable now but does not test the claim.
- note: from the underlying-library library: Index inclusion, deletion and reconstitution flows; harness suggestion: events.py: index_change_event_study(changes, prices, spy) and reconstitution_week(days_iwm, closes_iwm, days_spy, closes_spy) using the last-Friday-of-June rule; both reuse block_bootstrap_pvalue. | verifier: corrected claim/trial

### T-355 · bitcoin-halving-cycle

**Claim.** Across halvings, BTC-USD's 365-day log return after a halving exceeds its 365-day log return before it.

- kind: underlying-strategy · origin: underlying-library:Event and calendar strategies on the underlying, https://ideas.repec.org/a/gam/jjrfmx/v18y2025i5p242-d1647669.html, https://arxiv.org/pdf/2511.05512
- statistic: Mean (post minus pre) 365-day log return across halvings.
- null: No difference. Placement bootstrap: random dates replace halving dates, with the same pre/post comparison, preserving autocorrelation.
- procedure: Compute for 2016, 2020, 2024 (BTC) and 2015, 2019, 2023 (LTC). Report the point estimates and placement p. The verdict is forced to 'inconclusive' while n < 8.
- data: daily-history-BTC-USD (stored), LTC-USD via Yahoo. · min n: 8
- pass: Cannot pass before 8 halvings exist (about 2044 for BTC). The harness records estimates and parks the theory as untestable at power.
- controls: Look-ahead: dates are deterministic. Survivorship: BTC/LTC survived; dead halving coins are excluded, biasing the pooled variant up. Costs: irrelevant. Multiple testing: 5 variants on 3-6 events; any 'significant' result is noise by construction. Regime: each cycle is one regime.
- blocked on: Sample size, not data. Six halvings across BTC and LTC exist in reachable data, below the min_n of 8. Park as untestable at power, with a monitoring hook after each halving.
- note: from the underlying-library library: Bitcoin halving cycle; harness suggestion: events.py: halving_windows(days, closes, dates, horizon=365) returning per-event pre/post returns and a placement-bootstrap p; verdict forced to 'inconclusive' while n < 8. | verifier: corrected claim/trial

### T-369 · cip-basis-dollar-lending

**Claim.** From 2015 to 2026, a US retail account lending dollars synthetically through short CME 6J futures plus yen held at a retail broker's JPY deposit rate earns less than DTB3 + 10 bp on average, net of exchange fees.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.nber.org/papers/w23170, https://libertystreeteconomics.newyorkfed.org/2023/10/options-for-calculating-risk-free-rates
- statistic: Mean (retail implied USD rate - DTB3) per quarterly roll, net of 2 bp round trip.
- null: Mean net spread >= 10 bp (the basis is capturable).
- procedure: Quarterly: 6J=F close vs DEXJPUS (2-hour asynchrony noted) 5 days after each roll. Retail JPY rate from broker history. Institutional proxy computed with IR3TIB01JPM156N (interbank, includes a credit spread). HAC CI.
- data: daily-history-6J=F (Yahoo, from 2000-11, verified), fred DEXJPUS, IR3TIB01JPM156N (from 2002-04), DTB3. Blocked: retail broker JPY deposit-rate history, JGB bill yields. · min n: 40
- pass: Mean net retail spread < 10 bp with 95% CI upper bound < 20 bp (claim supported: not capturable).
- controls: Continuous-contract roll jumps: use only days 5-60 after each roll. FX close asynchrony. Interbank vs bill credit spread. Quarter-end spikes reported separately. Costs: CME fees and spread. Look-ahead: none.
- blocked on: Retail JPY deposit/borrow rate history (IBKR does not publish a downloadable history) and daily JGB bill yields. The institutional proxy (6J=F vs DEXJPUS with OECD rates) is computable now, but it answers a different question.
- note: from the underlying-library library: Covered-interest-parity basis as a lender; harness suggestion: Defer; if pursued, reuse basis_carry() from crypto-cme-cash-and-carry on 6J/6E contracts | verifier: corrected claim/trial

### T-371 · commodity-term-structure-carry

**Claim.** From January 2013 to September 2026, a monthly top-quintile-minus-bottom-quintile roll-yield portfolio across at least 15 US commodity futures earns an annualized Sharpe above 0.3 after 15 bp per leg per month.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.nber.org/papers/w13249, https://ideas.repec.org/a/taf/apeclt/v30y2023i13p1749-1753.html
- statistic: Long-short annualized Sharpe and Newey-West t-stat.
- null: Sharpe <= 0.
- procedure: Build F1/F2 for each root from individual contract histories, then monthly portfolio formation using month-end data only. Block bootstrap (block 6 months). Walk-forward: any tuning on data before 2013 only.
- data: Individual contract histories for 20 roots (needed; not reachable for expired contracts); fred DHHNGSP (from 1997), DCOILWTICO (from 1986), daily-history-UNG, USO, NG=F, CL=F for the proxy variant. · min n: 120
- pass: Test Sharpe > 0.3 with bootstrap lower bound > 0, and DSR > 0.95 with n_trials = 5.
- controls: Survivorship: fixed list of roots alive throughout. Roll timing fixed ex ante. Costs 15 bp per leg plus slippage in illiquid agriculturals. Regime: 2008, 2014-16 oil crash, April 2020 negative WTI (exclude CL that month), 2022. Look-ahead: month-end prices only. 5 trials deflated.
- blocked on: F1/F2 history: Yahoo serves only currently listed contracts (expired ones return 404) and Nasdaq Data Link CHRIS returns 403. Start a daily capture of all listed contracts now; the claim becomes testable on captured data only after years. The UNG/USO roll-drag proxy variant is testable now with FRED spot and Yahoo continuous fronts.
- note: from the underlying-library library: Commodity term-structure (basis) carry, cross-sectional; harness suggestion: mandel/experiments/carry.py: roll_yield_sort() and etf_roll_drag(etf, spot, front); contract-history fetcher for Yahoo <ROOT><MY>.<EXCH> | verifier: corrected claim/trial

### T-376 · box-spread-financing

**Claim.** Across at least 60 daily CBOE SPX chain captures, the median executable (ask-side) lender box rate at 90-365 days exceeds the maturity-matched Treasury yield by more than 10 bp.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://libertystreeteconomics.newyorkfed.org/2023/10/options-for-calculating-risk-free-rates, https://www.nber.org/papers/w26138
- statistic: Per capture day, the median (r_lend - Treasury) across qualifying boxes; then the median across days with a bootstrap CI.
- null: Median executable spread <= 10 bp.
- procedure: mandel/experiments/options_market.py box_rates()/box_lending() (T-186) over each options-surface capture. Treasury yields interpolated from DTB3/DGS1/DGS2. Block bootstrap over days (block 10).
- data: options-surface-<day> for _SPX (daily captures from 2026-10-14), fred DTB3, DGS1, DGS2. · min n: 60
- pass: Median executable spread > 10 bp with bootstrap 95% CI excluding 10 bp across at least 60 capture days spanning at least one quarter-end. DSR with n_trials = 5.
- controls: Quotes are delayed (15 min), so mid and executable are both reported and only executable counts. Commissions $0.65 x 4 legs. OCC counterparty vs Treasury. Early exercise avoided by using SPX only. Look-ahead: none (same-capture prices). Quarter-end included.
- blocked on: Needs at least 60 daily SPX chain captures; 1 day exists (2026-10-14: executable median -5.5 bp, fail). This entry duplicates options-library harnesses T-186/T-187: keep one theory ID and point this entry to it.
- note: from the underlying-library library: Box-spread financing: lend (and borrow) at the options-implied rate; harness suggestion: mandel/options/strategies.py: box template exists in the payoff engine; add implied_rate_from_box() over options-surface captures in mandel/experiments/volatility.py | verifier: corrected claim/trial

### T-380 · closed-end-fund-discount-carry

**Claim.** From 2015 to September 2026, among at least 100 US closed-end funds, those with a discount z-score below -1.5 earn a 12-month benchmark-adjusted return at least 3 percentage points higher than funds with a z-score above 0.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.nber.org/papers/w3465, https://econpapers.repec.org/RAS/ppo122.htm
- statistic: Fund-clustered difference in mean 12-month benchmark-adjusted returns between the z < -1.5 and z > 0 groups. Also reported: the discount half-life.
- null: Difference <= 0.
- procedure: Monthly formation using NAVs published the prior evening (available_at = next day). Overlapping 12-month returns handled by clustering by fund and month. Fund-clustered bootstrap.
- data: daily-history-<CEF tickers> (Yahoo); NAV history (blocked); GBTC with Coinbase hourly BTC-USD for the crypto variant. · min n: 100
- pass: Difference >= 3 points with clustered p < 0.05. DSR with n_trials = 4.
- controls: Survivorship: liquidated and merged funds must be included (needs a dated fund list). Return-of-capital distributions. Fund leverage. Spreads 20-50 bp. NAV publication lag. 4 trials.
- blocked on: CEF NAV history (CEFConnect connection failed from this host; sponsor scraping or paid data) and a survivorship-free fund list. The GBTC variant is testable now as an approximate single-asset episode study.
- note: from the underlying-library library: Closed-end fund and crypto-trust discount carry; harness suggestion: Defer; the GBTC/PHYS variants could reuse discount_episodes() from the LST entry once NAV series exist | verifier: corrected claim/trial

### T-390 · congressional-ptr-mimicry

**Claim.** Equal-weighted purchases disclosed in House and Senate PTRs over 2021-2026, bought at the first close after availability and held 63 trading days, earn a positive mean size-matched abnormal return.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w26975 (fetched), https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2025FD.zip (reachable, 200)
- statistic: Mean 63-day abnormal return per purchase event (benchmark: size-matched ETF, SPY/IJH/IWM by market cap) with event-month clustered bootstrap; calendar-time FF5 alpha.
- null: Mean abnormal return <= 0 (expected not to be rejected).
- procedure: Use the House PTR index already ingested (mandel/data/social.py house_ptr_index); parse PTR PDFs (text PDFs via pdftotext; scanned ones via OCR) and Senate eFD (session/agreement cookie); map tickers; align on available_at; price with Yahoo; also compute trade-date returns; bootstrap by month cluster.
- data: House clerk FD zips (200) + PTR PDFs; Senate eFD (200, needs session); Yahoo prices; NANC, GOP, SPY. · min n: 500
- pass: Lower 95% bound of mean abnormal return > 0 AND calendar-time alpha t >= 2 over >= 500 purchase events spanning >= 24 months; otherwise parked as 'no edge after disclosure lag'.
- controls: Look-ahead: available_at, never trade date. Survivorship: delisted names missing from Yahoo; report ticker-resolution coverage and abort if < 90%. Costs: 5 bp per side, ~4x/yr turnover. Multiple testing: 6 variants. Regime: 2023-2025 mega-cap concentration; FF5 control.
- blocked on: PTR PDF parsing (House PDFs reachable; some are scanned and need OCR) and a cookie-based Senate eFD scrape. The NANC/GOP ETF variant is testable now but has only ~44 monthly observations (low power; Yahoo serves GOP, not KRUZ).
- note: from the underlying-library library: Congressional trading mimicry (House/Senate PTRs, NANC/KRUZ); harness suggestion: New experiments/flow_events.py: generic event-study harness (filing-date alignment, size-matched benchmark, clustered bootstrap, calendar-time alpha) shared by congress, insider, buyback and 13F entries; PTR PDF parser as a data/ module with a coverage report. | verifier: corrected claim/trial

### T-396 · analyst-revision-momentum

**Claim.** S&P 500 stocks in the top decile of one-month consensus FY1 EPS revisions outperform the bottom decile over the following month after costs.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, Chan, Jegadeesh, Lakonishok 1996 JF 'Momentum strategies' (not fetched), Jegadeesh, Kim, Krische, Lee 2004 JF 'Analyzing the analysts' (not fetched)
- statistic: Mean monthly decile spread with block-bootstrap CI; FF5+UMD alpha.
- null: Spread mean <= 0.
- procedure: Requires point-in-time estimates. Free route: daily snapshots of Yahoo quoteSummary earningsTrend from now on (note: the endpoint now returns 401 without a crumb/cookie handshake, verified today), giving ~24 monthly observations in two years.
- data: Blocked: IBES/FactSet (paid). Free partial: Yahoo quoteSummary snapshots with crumb, accumulated daily. · min n: 24
- pass: Alpha t >= 2 over >= 24 months once data exist (low power; treat as exploratory).
- controls: Look-ahead: snapshots avoid IBES restatement bias. Survivorship: universe fixed at snapshot time. Costs: 5 bp per side, ~50% monthly turnover. Multiple testing: 3 variants. Regime: earnings-season clustering.
- blocked on: No free point-in-time estimate history; Yahoo quoteSummary needs a crumb/cookie flow (401 today). Start a snapshot job or buy IBES via the user's server.
- note: from the underlying-library library: Analyst revision momentum; harness suggestion: Add a snapshot job in ingest.py writing quoteSummary bundles with available_at; defer the harness. | verifier: corrected claim/trial

### T-399 · retail-attention-herding-reversal

**Claim.** Stocks with a >= 5x daily spike in Reddit/StockTwits mentions that rank top-10 by count earn negative mean 20-day abnormal returns relative to SPY net of borrow.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.sciencedirect.com/science/article/abs/pii/S0304405X21004980 (Barber et al.; not fetched, 403), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3715077 (Barber et al. SSRN; not fetched, 403)
- statistic: Mean 20-day abnormal return after events, date-clustered bootstrap; net of borrow at 20% annualised.
- null: Mean abnormal return >= 0.
- procedure: Accumulate daily mention counts (ingest running; one day so far); events defined ex ante; first read only when n >= 250 events over >= 12 months. Meanwhile run the Robintrack 2018-2020 replication as a separate in-sample trial.
- data: Mandel social bundles (Reddit, StockTwits); Robintrack historical download (page 200, format unverified); Yahoo prices. · min n: 250
- pass: Upper 95% bound of mean abnormal return < 0 over >= 250 events AND holds net of 20% borrow.
- controls: Look-ahead: counts to 16:00 ET, trade next open. Survivorship: none (forward events); Robintrack universe includes later-delisted names, coverage reported. Costs: borrow 10-100% on meme names, 10 bp spreads; avoid-only variant costless. Multiple testing: 5 variants. Regime: gamma squeezes; cap sizing.
- blocked on: One day of mention data; needs ~12 months. Pushshift is no longer free. Partial unblock: Robintrack (2018-2020) may allow an in-sample replication now if its download still serves files.
- note: from the underlying-library library: Retail attention herding reversal (Reddit/StockTwits mentions); harness suggestion: Extend experiments/social.py with the herding-event definition and a scheduled first read when n >= 250; store events with available_at. | verifier: corrected claim/trial

### T-401 · crypto-sopr-exchange-netflows

**Claim.** In BTC uptrends (price > 200-day MA), a 7-day SOPR reset to <= 1.0 followed by an upturn predicts a 30-day forward return above the unconditional uptrend 30-day return.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://api.glassnode.com/v1/metrics/indicators/sopr?a=BTC (probed; 401 without key), https://docs.glassnode.com/ (redirect target of the SOPR academy page; not fetched)
- statistic: Difference in mean 30-day forward log return (signal days minus all uptrend days) with block bootstrap; independent-signal count.
- null: Difference <= 0.
- procedure: SOPR daily via a Glassnode key; signals with one-day lag; walk-forward by cycle.
- data: Glassnode SOPR (key required); CryptoQuant netflows (paid); Yahoo BTC-USD. · min n: 40
- pass: CI excludes zero over >= 40 signals spanning >= 3 cycles.
- controls: Look-ahead: one-day lag. Survivorship: none. Costs: 10-40 bp per switch. Multiple testing: 4 variants. Regime: pre/post-2024 ETF custody shift.
- blocked on: Glassnode API key (free-tier sign-up) for SOPR; exchange netflows need a paid tier or self-built exchange-address labelling.
- note: from the underlying-library library: Bitcoin SOPR and exchange netflows (holder behaviour); harness suggestion: Same regime-conditional harness as MVRV; add a keyed Glassnode client behind an env var when the user supplies a key. | verifier: corrected claim/trial

### T-406 · polymarket-smart-wallet-cloning

**Claim.** Following new positions of trailing-90-day top-100 PnL wallets at the best ask within 60 minutes yields a lower Brier score on resolved markets than the contemporaneous market mid.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://data-api.polymarket.com/trades?limit=2 (reachable, 200), https://data-api.polymarket.com/positions?user=... (reachable, 200)
- statistic: Mean Brier difference (wallet-implied side vs market mid at copy time) over resolved markets, market-clustered bootstrap; realized ROI net of spread as secondary.
- null: Brier difference >= 0.
- procedure: Ingest data-api /trades and /positions (public, 200); Goldsky subgraph if per-wallet depth is insufficient; point-in-time monthly leaderboards with a 1-day embargo; walk-forward monthly; fills simulated on stored books.
- data: Polymarket data-api; Mandel's resolved-market store and 300 order books. · min n: 300
- pass: Upper 95% bound of the Brier difference < 0 over >= 300 resolved markets AND net ROI > 0 after 1.5% round-trip cost.
- controls: Look-ahead: point-in-time leaderboard; no resolution-based selection. Survivorship: include wallets that later went bust. Costs: 1-3 cent spreads; check the current fee schedule in Polymarket docs (taker fees apply to some market types; the earlier '2% winnings fee' claim is unverified). Multiple testing: 4 variants. Regime: election-cycle volume; test ex-election.
- blocked on: Wallet-level trade history ingest (data-api /trades is public; per-wallet historical depth unverified; may need the Goldsky subgraph). Not in Mandel's current data list.
- note: from the underlying-library library: Prediction-market smart-wallet cloning (Polymarket 13F analogue); harness suggestion: data/polymarket_wallets.py + a Brier-vs-price overlay harness in experiments/markets.py reusing the existing proper-scoring code. | verifier: corrected claim/trial

### T-407 · pm-book-imbalance

**Claim.** On Polymarket and Kalshi binary markets, taking the side indicated by top-3-level YES-book depth imbalance |I| > 0.4 and holding for 6 hours earns a positive mean net return per trade after the taker fee and the quoted spread.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/jjfinec/nbt003 (Cont, Kukanov, Stoikov 2014, The Price Impact of Order Book Events), https://docs.polymarket.com/developers/CLOB/timeseries (prices-history: interval, fidelity in minutes, default 1)
- statistic: Mean net return per trade in cents for the headline cell (k=3, q=0.4, h=6h, static I, taker), after the fee formula and half-spread at entry and exit. Diagnostics: hit rate, and Spearman correlation of I_t with the forward mid change.
- null: Mean net return <= 0, and I_t carries no information about the forward mid change (I permuted across snapshots within each market).
- procedure: Pre-register the 108-cell grid. Walk forward by snapshot date: first 60% of dates to fit, last 40% to test, with a 24h embargo. p-value from 1,000 per-market block permutations of I. Standard errors clustered by market and by date. Deflated Sharpe and CSCV PBO across all 108 cells.
- data: Hourly Polymarket CLOB /book captures and Kalshi /markets/{ticker}/orderbook captures for at least 30 days, joined to later mids (Polymarket /prices-history with startTs/endTs at fidelity=60; Kalshi 60-minute candles with yes_bid/yes_ask). available_at = capture time. Today the store holds one snapshot of 300 Polymarket markets (2026-10-14 09:34 UTC). · min n: 5000
- pass: On the out-of-sample dates the headline cell's mean net return is > 0 with a block-bootstrap 95% CI excluding zero, AND DSR >= 0.95 across the 108 cells, AND PBO < 0.3.
- controls: Look-ahead: only the book at t; forward mids come from later timestamps. Survivorship: include markets that later went illiquid or were voided. Costs: fee formula by category (not a flat 150 bps), half-spread at entry and exit; the passive variant fills only when a later trade prints through the quote. Multiple testing: all 108 cells feed DSR and PBO. Regime: split by days-to-resolution, by category (politics, sports, crypto, economics), and by market volume tercile.
- blocked on: No source archives order books, so history cannot be backfilled. Hourly captures on both venues for at least 30 days (free) are needed before min_n is reached. The trade-print version is testable now and is entered separately as pm-trade-flow-imbalance.
- note: from the underlying-library library: CLOB order-book imbalance on prediction markets; harness suggestion: Extend mandel/experiments/markets.py (bundle_arb_scan already parses book rows) with book_imbalance_forward(): join book snapshots to next mids from polymarket_price_history(fidelity=60) in mandel/data/fetch.py; p-values via block_bootstrap_pvalue and the grid through pbo_cscv / deflated_sharpe_ratio in mandel/validation/backtest_eval.py. | verifier: corrected claim/trial

### T-410 · crowd-vs-polls

**Claim.** On resolved race-markets where the market price and the debiased poll-implied probability differ by more than 10 points at 30 days before the vote, the poll-implied probability has a lower mean Brier score than the market price.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/poq/nfp082 (Rothschild 2009, Forecasting Elections: Comparing Prediction Markets, Polls, and Their Biases), https://api.semanticscholar.org/graph/v1/paper/DOI:10.1257/0895330041371321 (Wolfers and Zitzewitz 2004, Prediction Markets)
- statistic: Mean paired Brier difference (market minus poll-implied) on the deviation subset. Secondary: Kelly-sized P&L toward polls after fees.
- null: Mean Brier difference <= 0: polls are no better than the market on the deviation subset.
- procedure: Fit the error model on cycles before 2024. Freeze it, and register the 2026 deviations before 2026-11-03. Paired bootstrap over races, with the race as the unit. Report all d x H x direction cells (18) and deflate.
- data: Polymarket resolved election markets (daily prices in store, hourly via windowed re-fetch); Kalshi 2024 election markets via /historical; poll margins from Wikipedia polling tables read at the revision live on each date (MediaWiki revisions API). · min n: 60
- pass: At least 60 race-markets in the deviation subset (2024 + 2026). Brier difference favours polls with bootstrap p < 0.05 after deflation for 18 cells. Same sign in the 2024 and 2026 subsets. Net P&L CI excludes zero.
- controls: Look-ahead: poll averages as of each date (Wikipedia revision history, not current tables); error model fit only on earlier cycles. Survivorship: every race with both a market and polls, not only close races. Costs: fees, spreads, capital locked to resolution. Multiple testing: 18 cells. Regime: cycle-specific polling bias is the main failure mode; report per cycle.
- blocked on: No poll archive is ingested. The FiveThirtyEight poll CSVs now redirect to abcnews.com (dead; verified 2026-10-14), RealClearPolling returns 403, and the fivethirtyeight/data GitHub CSVs stop at 2016. Wikipedia polling tables are reachable (200) and need a revision-history scraper. The 2026 races resolve after 2026-11-03.
- note: from the underlying-library library: Prediction-market crowd vs poll averages; harness suggestion: Add polls ingestion to mandel/data/ (CSV archive with available_at = poll release date); harness in mandel/experiments/markets.py beside market_calibration() comparing Brier scores with paired bootstrap; count the error-model fits as trials in the registry. | verifier: corrected claim/trial

### T-412 · attention-reversal-trending

**Claim.** Assets that newly enter a daily trending or most-mentioned list underperform their beta-adjusted benchmark by at least 1% on average over the following 10 trading days.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/rfs/hhm079 (Barber and Odean 2008, All that Glitters), Da, Engelberg, Gao 2011, In Search of Attention, Journal of Finance 66(5) (DOI 10.1111/j.1540-6261.2011.01679.x; publisher page returned 403 from this host)
- statistic: Mean beta-adjusted 10-day abnormal return of shock events. Calendar-time portfolio alpha with HAC t-stat. Event-time bootstrap.
- null: Abnormal return = 0: the same as matched controls (same 20-day volatility decile, same market-cap tercile, no shock).
- procedure: Event study with matched controls. Calendar-time portfolios handle overlap. All 48 cells declared and deflated.
- data: StockTwits trending, ApeWisdom and CoinGecko trending, captured daily from 2026-10-14 only. arctic_shift Reddit posts (created_utc, title, selftext; verified reachable) for a 2020-2026 backfill. Yahoo daily OHLCV. · min n: 300
- pass: At least 300 shock events. Mean 10-day abnormal return <= -1% with bootstrap p < 0.01 after deflation. Same sign in at least 2 of the sources. The avoidance variant raises benchmark Sharpe.
- controls: Look-ahead: shock from the 06:40 UTC capture (or arctic_shift created_utc), entry at the next open. arctic_shift scores are placeholders until about 36h after posting, so only counts are usable. Survivorship: Yahoo drops many delisted meme tickers; log missing ones, because this biases against finding underperformance. Costs: 1-5 bps large caps, 20-50 bps small caps, borrow fees for shorts (avoidance is the primary variant). Multiple testing: 48 cells. Regime: VIX > 30 frenzy days separately.
- blocked on: Trending lists have no history (one capture day). The arctic_shift backfill is free and reachable but is not in Mandel's data yet. The cashtag extractor's precision must be measured first.
- note: from the underlying-library library: Attention-driven reversal on trending tickers and coins; harness suggestion: Extend mandel/experiments/social.py (attention_vs_abs_return already joins derived mention rows to prices) with an event-study function using daily_closes(); matched controls by volatility decile; capture-day count gate like social_attention's 30-day rule. | verifier: corrected claim/trial

### T-413 · wsb-dd-drift

**Claim.** Tickers named in bullish r/wallstreetbets DD posts dated after 2022-01-01 outperform size- and volatility-matched controls by at least 1% over the next 20 trading days.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/search?query=Place+your+bets+Reddit (Bradley, Hanousek, Jame, Xiao 2021 SSRN 3806065: 1.1% two-day return, 2% monthly drift, decline after Jan 2021), https://arctic-shift.photon-reddit.com/api/posts/search (Reddit archive, verified in SOCIAL-SOURCES.md)
- statistic: Mean 20-day matched-control abnormal return. Calendar-time alpha against SPY/IWM with HAC t-stat. DD-minus-non-DD-mention difference.
- null: Abnormal return = 0, and the DD label adds nothing beyond the generic mention shock.
- procedure: arctic_shift backfill 2019-2026. Pre-2021 replication and post-2022 test are registered as separate trials. Matched controls. All 36 cells deflated.
- data: arctic_shift posts (link_flair_text=DD filter verified 2026-10-14); SEC company_tickers.json dated copies; Yahoo daily OHLCV. · min n: 400
- pass: At least 400 qualifying post-2022 events. Mean abnormal return >= 1% with p < 0.01 after deflation. Calendar-time alpha t > 2.5. DD-minus-non-DD difference significant.
- controls: Look-ahead: entry at least 2h after created_utc. Scores and comment counts are placeholders until about 36h, so any engagement filter delays entry. Ticker universe as of the post date. Survivorship: delisted tickers missing from Yahoo are logged; they bias the test. Costs: 5-20 bps spreads plus impact on viral days. Multiple testing: 36 cells plus the replication. Regime: the 2021 frenzy is excluded from the headline.
- blocked on: Historical Reddit posts are not ingested. arctic_shift is free and verified reachable, but it is not in Mandel's data yet. The cashtag extractor needs a labelled precision check.
- note: from the underlying-library library: WallStreetBets due-diligence post drift; harness suggestion: Add arctic_shift backfill to mandel/data/social.py (fields id,title,selftext,link_flair_text,created_utc); event study in mandel/experiments/social.py with matched controls; register the 2021 replication as a separate trial from the post-2022 test. | verifier: corrected claim/trial

### T-417 · google-trends-timing

**Claim.** The Preis 'debt' rule applied to SPY from 2012-01 to 2026-10 earns a positive Sharpe ratio with block-bootstrap p < 0.05 and deflated Sharpe >= 0.95 across the 20-cell grid.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/srep01684 (Preis, Moat, Stanley 2013, Quantifying Trading Behavior in Financial Markets Using Google Trends), https://arxiv.org/abs/1307.4643 (Challet and Ayed 2013: random finance keywords no better than random keywords; fragility)
- statistic: Weekly strategy Sharpe. DSR across 20 cells. Mean next-week return difference between up-search and down-search weeks.
- null: Sharpe <= 0 (stationary block bootstrap, 4-week blocks).
- procedure: Fixed-rule backtest on 2012-2026. 20 cells plus the published in-sample result counted as trials. DSR and PBO.
- data: Google Trends weekly series fetched as fixed 5-year windows ending before each trade week, because Trends rescales every request. Yahoo weekly prices. · min n: 700
- pass: At least 700 weeks. Sharpe > 0 with p < 0.05. DSR >= 0.95. PBO < 0.3.
- controls: Look-ahead: Trends is renormalised and revised per request; only use windows ending before the trade week, and archive raw responses with fetch time. Survivorship: not applicable. Costs: about 5 bps a week on SPY. Multiple testing: 21 trials. Regime: COVID weeks winsorised and reported.
- blocked on: Google Trends returned HTTP 429 from this host (verified 2026-10-14) and has no official API. It needs the user's server with fixed-window fetches. Wikipedia page views (entered separately) are a free proxy with stable counts.
- note: from the underlying-library library: Google Trends search-volume timing (Preis-Moat-Stanley); harness suggestion: If Trends data is obtained (user's server with pytrends, fixed windows), reuse the ma_rule_returns pattern in mandel/experiments/underlying.py for weekly bars with pbo_cscv and deflated_sharpe_ratio. | verifier: corrected claim/trial

### T-418 · news-headline-sentiment

**Claim.** A dollar-neutral top-minus-bottom quintile portfolio on lexicon headline sentiment, formed at the open after the headlines, earns a positive next-day return with annualised Sharpe > 1 after 10 bps round-trip costs in a liquid large-cap universe.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://www.nber.org/papers/w26186 (Ke, Kelly, Xiu 2019, Predicting Returns with Text Data), https://arxiv.org/abs/2304.07619 (Lopez-Lira and Tang 2023, Can ChatGPT Forecast Stock Price Movements?)
- statistic: Daily long-short net return. HAC t-stat. Annualised Sharpe. Decay profile over days 1-20.
- null: Mean <= 0 (scores permuted across tickers within day, 2,000 times).
- procedure: Freeze the scorer and the org-to-ticker map before seeing returns. Within-day permutation. 24 cells deflated. Halves 2015-20 and 2021-26.
- data: GDELT 2.0 GKG 15-minute files since 2015-02-18 (masterfilelist verified over HTTPS on 2026-10-14); SEC company_tickers.json; Yahoo daily OHLC. · min n: 500
- pass: At least 500 trading days. Net Sharpe > 1 with HAC p < 0.01 after deflation. Present in both halves. Small-cap results reported, not used to pass.
- controls: Look-ahead: GDELT DATE plus the 15-minute publication lag; headlines before 09:00 ET only. An LLM's training data contains the future, so LLM-scored tests run only after its cutoff. Survivorship: no free historical S&P constituent list; use liquid names with continuous Yahoo history and flag the bias. Costs: 10 bps large caps, 30+ bps small, plus borrow. Multiple testing: 24 cells, plus the entity-mapping choices. Regime: earnings season.
- blocked on: No news history is ingested. GDELT is free and reachable but not in Mandel's data, and the GKG files are large. The org-to-ticker mapping must be built and validated. LLM scoring costs API fees and is look-ahead before the model cutoff.
- note: from the underlying-library library: News-headline sentiment drift; harness suggestion: Add GDELT GKG ingestion (entity + tone) to mandel/data/; cross-sectional quintile engine in a new mandel/experiments/news.py using compare_strategies / block_bootstrap_pvalue from backtest_eval.py; freeze the prompt text in the theory registry before any run. | verifier: corrected claim/trial

### T-422 · futures-lead-etf

**Claim.** A follower that trades SPY one minute after an ES=F one-minute move larger than 2 bps earns a positive mean net return after the SPY half-spread.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/qje/qjv027 (Budish, Cramton, Shim 2015: ES-SPY arbitrage at millisecond scale), Hasbrouck 2003, Intraday Price Formation in U.S. Equity Index Markets, Journal of Finance 58(6) (DOI 10.1046/j.1540-6261.2003.00609.x; publisher and Semantic Scholar lookups failed from this host)
- statistic: Mean net return per follow trade. Diagnostics: Hasbrouck information share and Granger F at the 1-minute lag.
- null: Mean net return <= 0. The claim is expected to fail, which would confirm there is no retail-latency alpha.
- procedure: Yahoo 1-minute pilot (8 days per request, about 30 days back) now. The full test needs years of minute bars. Follow-trade P&L with declared latency. 16 cells deflated.
- data: Yahoo chart API: interval=1m (8 days per request, about 30 days back) and 1h (730 days), for ES=F, NQ=F, GC=F, SPY, QQQ, GLD (verified 2026-10-14). Multi-year minute history (Polygon, Alpaca free tiers) is not reachable from this host. · min n: 50000
- pass: At least 50,000 aligned minutes (about 130 trading days). Net return CI excluding zero on the positive side would refute the efficiency prior. Information share is reported either way.
- controls: Look-ahead: strictly lagged ES bars. Yahoo bars are last-trade, so the SPY half-spread is charged explicitly. Survivorship: not applicable. Costs: SPY 1 bp half-spread. Multiple testing: 16 cells. Regime: open and close half-hours; ES roll dates (Yahoo ES=F is a front-month continuation).
- blocked on: Minute history beyond Yahoo's about 30-day window. A 30-day pilot gives about 11,700 SPY minutes, below min_n. Polygon or Alpaca free minute history from the user's server would unblock it.
- note: from the underlying-library library: Index futures lead the ETF and cash index (ES -> SPY, SPX -> SPY); harness suggestion: Pilot script using Yahoo 1m/1h intervals (extend fetch route with interval parameter); information-share estimator shared with kalshi-polymarket-leadlag; mark the daily 'open gap' variant as a data-quality check only. | verifier: corrected claim/trial

### T-426 · opening-range-breakout

**Claim.** A 5-minute ORB on QQQ (direction from the first bar, stop at the opposite range side, exit at the close) earns positive mean net daily return with annualised Sharpe > 0.5 over 2024-2026.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, Zarattini, Aziz, Barbon 2023, Can Day Trading Really Be Profitable?, SSRN 4416622 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622; returned 403 from this host)
- statistic: Daily net return mean, HAC t-stat, Sharpe; DSR over 72 cells; PBO.
- null: Mean <= 0 (stationary block bootstrap of daily P&L, 5-day blocks).
- procedure: Replication on 2016-2023 and out-of-sample test on 2024-2026, on 1- or 5-minute bars. Costs: 1 bp half-spread plus one tick of slippage per stop fill.
- data: Yahoo 5m bars reach only 60 days (verified: 30m/60d), so multi-year minute bars (Polygon or Alpaca free tiers) must come from the user's server. Coinbase minute candles serve the BTC proxy. · min n: 500
- pass: At least 500 out-of-sample days. Net Sharpe > 0.5 with p < 0.05. DSR >= 0.95. PBO < 0.3.
- controls: Look-ahead: range from completed bars; stops fill at the next bar's open or worse. Survivorship: not applicable. Costs: spread, slippage, TQQQ financing and decay. Multiple testing: 72 cells plus the published rule. Regime: trend vs chop days; FOMC days.
- blocked on: Multi-year 1- or 5-minute equity bars are not reachable (Yahoo 5m covers 60 days). The 60-minute ORB pilot on Yahoo 1h bars (730 days) is a different rule and does not test this claim.
- note: from the underlying-library library: Opening-range breakout (ORB) on index ETFs; harness suggestion: New mandel/experiments/intraday_equity.py once minute bars exist; grid into pbo_cscv and deflated_sharpe_ratio; add a Yahoo interval=5m pilot fetch to confirm bar quality. | verifier: corrected claim/trial

### T-429 · twap-execution-shortfall

**Claim.** For $1,000 Polymarket orders, a 6-hour 8-slice passive-first TWAP has lower implementation shortfall against the arrival mid than immediate taker execution by at least 1 cent per share on average, including fees and rebates.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111/j.1540-6261.1988.tb02591.x (Berkowitz, Logue, Noser 1988, The Total Cost of Transactions on the NYSE), Almgren and Chriss 2001, Optimal execution of portfolio transactions, Journal of Risk 3(2) (not fetched)
- statistic: Paired difference in implementation shortfall (execution price minus arrival mid, signed) between TWAP and immediate execution. Worst-decile shortfall.
- null: Paired difference <= 0.
- procedure: Stage 1: replay. Drift and passive fills come from public trade prints (Kalshi /trades and /historical/trades now; Polymarket data-api trades, capped at offset 10,000). Taker book-walk costs come from captured hourly books. Stage 2: paired live paper orders, alternating policies on matched markets. 72 cells deflated.
- data: Hourly book snapshots and trade prints for at least 30 days, plus Mandel's own order log, which is the only true measure of impact. · min n: 400
- pass: At least 400 simulated or paper orders. Paired difference >= 1 cent with bootstrap p < 0.01. TWAP's worst-decile shortfall no more than 3 cents worse than immediate execution.
- controls: Look-ahead: child fills only from prints after the child was placed; arrival mid from the snapshot at decision time. Survivorship: aborted and partial orders counted at their realised fills. Costs: fee formula, rebates. Multiple testing: 72 cells. Regime: news hours vs quiet; near-resolution excluded.
- blocked on: Book-walk costs need captured books (no history anywhere). Impact needs Mandel's own fills. The drift component can be simulated now from Kalshi trade prints.
- note: from the underlying-library library: TWAP/VWAP execution vs immediate taker (implementation shortfall); harness suggestion: Build on the same capture used for clob-market-making; new mandel/experiments/execution.py with arrival-mid shortfall, passive-fill rule and book-walk model; results feed the transaction-cost inputs in mandel/validation/backtest_eval.py so every other strategy's cost assumptions become measured rather than assumed. | verifier: corrected claim/trial

### T-434 · treasury-cash-futures-basis

**Claim.** From 2018 to September 2026, the implied repo rate of the ZN front-contract CTD exceeded SOFR by more than 15 bp on average over days 5-60 after each roll.

- kind: underlying-strategy · origin: underlying-library:Carry, basis and yield, https://www.federalreserve.gov/econres/notes/feds-notes/quantifying-treasury-cash-futures-basis-trades-20240308.html, https://www.federalreserve.gov/econres/notes/feds-notes/recent-developments-in-hedge-funds-treasury-futures-and-repo-positions-20230830.html
- statistic: Mean (implied repo - SOFR) with HAC CI.
- null: Mean <= 15 bp.
- procedure: Daily: CTD selection by the highest implied repo among deliverable notes using CME conversion factors, futures settle, and the note's clean price plus accrued interest. HAC (lag 21).
- data: Needed: individual ZN contract settles (Yahoo serves no expired contracts), daily prices for every deliverable note (TreasuryDirect/FedInvest end-of-day prices, reachability unverified), CME conversion factors; FRED SOFR (from 2018-04-03, verified). · min n: 1000
- pass: HAC lower 95% bound > 15 bp.
- controls: Delivery-option value; repo specialness; month-end and quarter-end effects; costs of 1-2 bp; regime (March 2020). Look-ahead: CTD chosen with same-day prices only.
- blocked on: Individual Treasury futures contract histories and daily deliverable-note prices. Also not retail-implementable (repo financing at bank haircuts).
- note: from the underlying-library library: Treasury cash-futures basis trade (implied repo vs repo); harness suggestion: Defer. If FedInvest prices are reachable, start a daily capture of deliverable-note prices and listed ZN/ZF settles and reuse implied_financing(). | added by the verifier pass

### T-453 · sp500-index-inclusion

**Claim.** Stocks announced as S&P 500 additions earn a positive mean abnormal return (vs SPY) from the first close after announcement to the effective-date close, net of 10 bp round-trip costs, over 2015-2026.

- kind: underlying-strategy · origin: underlying-library:Factor, fundamental and flow, https://www.nber.org/papers/w30748 (fetched; abstract verified), https://en.wikipedia.org/wiki/List_of_S%26P_500_companies (200)
- statistic: Mean announcement-to-effective abnormal return per event, bootstrap over events (clustered by month).
- null: Mean net abnormal return <= 0.
- procedure: Collect announcement dates from S&P DJI press releases (scrape) and effective dates from the Wikipedia 'Selected changes' table (200); event study; migration vs new-entrant split.
- data: Wikipedia List of S&P 500 companies changes table (effective dates); S&P DJI press releases (announcement dates; scrape not yet verified); Yahoo prices. · min n: 150
- pass: Lower 95% bound > 0 over >= 150 additions.
- controls: Look-ahead: trade after the announcement is public. Survivorship: deleted and acquired names missing from Yahoo (affects deletions variant). Costs: 10 bp round trip; event-day spreads. Multiple testing: 4 variants. Regime: Tesla 2020 outlier; report with/without.
- blocked on: Announcement dates need an S&P DJI press-release scrape (not verified). The post-effective reversal variant is testable now from Wikipedia effective dates.
- note: from the underlying-library library: S&P 500 index inclusion effect; harness suggestion: flow_events.py with an index-changes loader (Wikipedia table + press releases). | added by the verifier pass

### T-454 · aggregate-short-interest

**Claim.** From 2015 to 2026, top-tercile detrended aggregate short interest predicts a negative 1-month SPY excess return, with positive out-of-sample R^2.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1016/j.jfineco.2016.03.004 (Rapach, Ringgenberg, Zhou 2016; metadata resolved)
- statistic: Out-of-sample R^2 (Clark-West). Timing-rule Sharpe vs buy-and-hold.
- null: Out-of-sample R^2 <= 0.
- procedure: Expanding window. 12 cells deflated.
- data: FINRA semi-monthly equity short interest (not ingested) plus shares outstanding (not reachable, because EDGAR returns 403 from this host). · min n: 120
- pass: At least 120 months. Out-of-sample R^2 > 0 with Clark-West p < 0.05 after deflation.
- controls: Look-ahead: short interest is published with about an 8-business-day lag. Survivorship: universe at each date. Costs: 5 bps. Multiple testing: 12 cells. Regime: 2020.
- blocked on: No short-interest history or shares-outstanding data is ingested. FINRA short interest files are free; shares outstanding needs EDGAR (403 here) and could run from the user's server.
- note: from the underlying-library library: Aggregate short interest predicts market returns; harness suggestion: FINRA short interest ingestion plus EDGAR shares from the user's server. Predictive regression next to consumer-confidence-size-premium. | added by the verifier pass

### T-455 · amihud-illiquidity-premium

**Claim.** In US stocks 2005-2026, the most-illiquid minus most-liquid Amihud quintile earns a positive net annual return after costs.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1016/S1386-4181(01)00024-6 (Amihud 2002; metadata resolved)
- statistic: Long-short net return with HAC t-stat.
- null: Net mean <= 0.
- procedure: Four cells deflated; walk-forward.
- data: A survivorship-free stock universe with delisting returns (CRSP, paid). Yahoo lacks most delisted names. · min n: 200
- pass: At least 200 months. Net mean > 0 with p < 0.05.
- controls: Look-ahead: trailing data only. Survivorship: the crux, and the reason this is blocked. Costs: illiquid names cost 50+ bps. Multiple testing: 4 cells. Regime: liquidity crises.
- blocked on: No survivorship-free stock universe. A Yahoo-based test would be biased toward survivors in exactly the illiquid tail.
- note: from the underlying-library library: Amihud illiquidity premium (cross-section); harness suggestion: Only with a survivorship-free universe; amihud() helper shared with highlow-spread-liquidity-shock. | added by the verifier pass

### T-456 · cot-positioning-extremes

**Claim.** Managed-money net long positioning in COMEX gold above the 90th percentile of its trailing 3-year range predicts a GLD 4-week return below its unconditional 4-week mean.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://www.cftc.gov/files/dea/history/fut_disagg_txt_2023.zip (verified 200), https://www.cftc.gov/files/dea/history/fut_fin_txt_2023.zip (verified 200)
- statistic: Difference in 4-week forward GLD return (extreme weeks minus all weeks).
- null: Difference >= 0 (4-week block bootstrap).
- procedure: Fixed rule 2006-2026. 16 cells deflated. Halves 2006-15 and 2016-26.
- data: CFTC historical disaggregated futures files (fut_disagg_txt_YYYY.zip verified 200) and TFF files (fut_fin_txt_YYYY.zip verified 200); Yahoo prices. · min n: 500
- pass: At least 500 weeks. Difference < 0 with p < 0.05 after deflation. Same sign in both halves.
- controls: Look-ahead: positions as of Tuesday, released Friday at 15:30 ET, so entry at Monday's open. Survivorship: not applicable. Costs: 5 bps. Multiple testing: 16 cells. Regime: 2008, 2020.
- blocked on: CFTC files are not in Mandel's data list. They are free and verified reachable; a yearly-ZIP download is needed.
- note: from the underlying-library library: CFTC Commitments of Traders positioning extremes; harness suggestion: cftc_cot(year, report) in mandel/data/fetch.py with release-time available_at. Rule P&L in mandel/experiments/underlying2.py. | added by the verifier pass

### T-457 · congress-ptr-copy

**Claim.** Stocks bought by members of Congress, entered at the disclosure date, outperform size- and momentum-matched controls by at least 1% over the following 60 trading days (2014-2026).

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1017/S0022109000003161 (Ziobrowski et al. 2004; metadata resolved), https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2024FD.zip (verified 200)
- statistic: Mean 60-day matched abnormal return from the disclosure date. Calendar-time alpha.
- null: Abnormal return = 0.
- procedure: Parse PTRs. Use two event clocks: the trade date (not tradable) and the disclosure date (tradable). Matched controls. 24 cells deflated.
- data: House FD yearly ZIP indexes (2024FD.zip verified 200), PTR PDFs (e-filed have a text layer; paper filings need OCR), Senate eFD HTML tables; Yahoo prices. · min n: 1000
- pass: At least 1,000 purchase events. Abnormal return >= 1% with p < 0.01 after deflation, on the disclosure clock.
- controls: Look-ahead: the disclosure clock only; the House filing date is day-granular, so use the next day. Survivorship: delisted tickers. Costs: 5-20 bps. Multiple testing: 24 cells. Regime: election years.
- blocked on: Only one day of the House PTR index is captured. Historical PTR PDFs need a parser and OCR for paper filings. Senate eFD needs a click-through session scraper. Non-commercial-use terms apply.
- note: from the underlying-library library: Congressional trade copying (House/Senate PTRs); harness suggestion: PTR parser in mandel/data/social.py (the House index route exists). Event study with matched controls in mandel/experiments/social.py. | added by the verifier pass

### T-460 · polymarket-informed-wallets

**Claim.** Trades larger than $1,000 by wallets in the top decile of walk-forward Brier skill predict a positive 24-hour price move in their direction, large enough that copying them at the ask earns positive mean net return after the taker fee.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://data-api.polymarket.com/trades?limit=1 (verified; offset > 10,000 returns 'max historical trades offset of 10000 exceeded')
- statistic: Mean net return per copied trade.
- null: Mean <= 0 (placebo: random wallets with matching trade sizes).
- procedure: Walk-forward wallet ranking with a 30-day embargo. 8 cells deflated.
- data: Polymarket data-api /trades (offset cap 10,000 per query) and on-chain CTF Exchange fill events (Polygon; untested); resolutions from Gamma markets (in store). · min n: 1000
- pass: At least 1,000 copied trades. Mean net > 0 with p < 0.01. DSR >= 0.95.
- controls: Look-ahead: the ranking uses only markets resolved before the trade. Survivorship: all wallets, including those that stopped trading. Costs: fee formula plus spread. Multiple testing: 8 cells. Regime: the 2024 election separately.
- blocked on: Complete trade history: the data-api offset cap (10,000 per query) truncates large markets. On-chain fill logs are free but untested from this host.
- note: from the underlying-library library: Polymarket informed-wallet following; harness suggestion: polymarket_trades(market, start, end) with time-window pagination in mandel/data/fetch.py. Wallet-skill ranking in mandel/experiments/markets.py. | added by the verifier pass

### T-461 · retail-order-imbalance-bjzz

**Claim.** The weekly top-minus-bottom decile portfolio on BJZZ retail order imbalance earns a positive net return in 2020-2026.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1111/jofi.13033 (Boehmer, Jones, Zhang, Zhang 2021; metadata resolved)
- statistic: Weekly long-short net return with HAC t-stat.
- null: Net mean <= 0.
- procedure: Six cells, deflated; walk-forward.
- data: TAQ trade-level data with sub-penny prices (paid; not reachable). · min n: 300
- pass: At least 300 weeks. Net mean > 0 with p < 0.01.
- controls: Look-ahead: weekly imbalance known at formation. Survivorship: CRSP universe. Costs: 10-30 bps. Multiple testing: 6 cells. Regime: 2021 meme period.
- blocked on: Trade-level TAQ data (paid). The FINRA daily short-volume files do not identify retail trades.
- note: from the underlying-library library: Retail order imbalance (sub-penny price improvement); harness suggestion: Only if trade-level data is licensed. | added by the verifier pass

### T-464 · stablecoin-issuance-btc

**Claim.** Weeks with stablecoin supply growth above 1 sigma are followed by higher BTC returns over the next week than other weeks (2019-2026).

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1111/jofi.12903 (Griffin and Shams 2020; metadata resolved), https://stablecoins.llama.fi/stablecoincharts/all (verified)
- statistic: Difference in next-week mean BTC return (high-issuance minus other weeks).
- null: Difference <= 0 (4-week block bootstrap).
- procedure: Fixed rule. 16 cells deflated. 2019-22 vs 2023-26.
- data: DefiLlama stablecoins API (stablecoincharts/all verified 200); Yahoo or Coinbase BTC. · min n: 300
- pass: At least 300 weeks. Difference > 0 with p < 0.05 after deflation. Same sign in both halves.
- controls: Look-ahead: supply measured at the week's end, before entry. Survivorship: include defunct stablecoins (UST). Costs: 0.5-1% round trip. Multiple testing: 16 cells. Regime: bull vs bear.
- blocked on: DefiLlama is not in Mandel's data list. It is free and verified reachable (200); a single download is needed.
- note: from the underlying-library library: Stablecoin issuance and BTC returns; harness suggestion: defillama_stablecoins() in mandel/data/social.py; rule P&L in mandel/experiments/underlying2.py. | added by the verifier pass

### T-466 · wikipedia-pageviews-attention

**Claim.** The Moat DJIA-company page-view rule applied to SPY from 2015-07 to 2026-10 earns a positive Sharpe with DSR >= 0.95 over the 24-cell grid.

- kind: underlying-strategy · origin: underlying-library:Microstructure, liquidity and sentiment, https://doi.org/10.1038/srep01801 (Moat et al. 2013; metadata resolved), https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Bitcoin/daily/20150701/20150703 (verified)
- statistic: Weekly Sharpe; DSR; PBO.
- null: Sharpe <= 0 (4-week block bootstrap).
- procedure: Fixed rule on 2015-07 to 2026-10 (the Wikimedia REST API starts in 2015-07). 24 cells plus the published result as trials.
- data: Wikimedia REST pageviews API per article, daily since 2015-07-01 (verified 200 with a descriptive User-Agent; rate-limited when bursting); Yahoo weekly prices. · min n: 500
- pass: At least 500 weeks. Sharpe > 0 with p < 0.05. DSR >= 0.95. PBO < 0.3.
- controls: Look-ahead: views for completed days only. Survivorship: page set fixed from the DJIA composition at each date. Costs: about 5 bps a week. Multiple testing: 25 trials. Regime: COVID weeks reported.
- blocked on: Wikimedia pageviews are not in Mandel's data list. The API is free and verified reachable but rate-limits bursts from this host (429 after a few calls). A throttled backfill, about one call per article-year, is needed.
- note: from the underlying-library library: Wikipedia page-view attention timing; harness suggestion: wikimedia_pageviews(article, start, end) in mandel/data/social.py with a throttle and declared User-Agent. Weekly rule in the style of the Google Trends entry. | added by the verifier pass

### T-477 · crypto-trend-factor-ctrend

**Claim.** Over 2018-2026, the long-only top-quintile CTREND-style portfolio from the point-in-time top-100 coins earns a positive mean weekly return in excess of BTC after 40 bps per side, with the block-bootstrap 95% interval excluding zero.

- kind: underlying-strategy · origin: underlying-library:trend-momentum/cross-sectional/crypto, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178 (search result), https://open.icm.edu.pl/handle/123456789/25542 (Fieberg et al. 2023 crypto factor momentum; search result)
- statistic: Mean weekly (top quintile - BTC) return after costs; DSR over 8 trials
- null: Mean = 0
- procedure: Point-in-time universe from CMC snapshots; rolling regressions using only past weeks; block bootstrap (block 8 weeks, 5,000 draws); DSR; survivorship sensitivity vs today's top-100
- data: CMC historical listings (verified reachable) plus daily price/volume for every coin ever in the top 100 (not verified for delisted coins) · min n: 400
- pass: Mean > 0 with 95% interval excluding 0, DSR > 0.95
- controls: Look-ahead: rolling coefficients from data before week t; survivorship: point-in-time universe, delisted coins marked at last price minus 50% as stress; costs: 40+10 bps per side; multiple testing: 8 trials plus the xs-crypto-momentum-weekly trials on the same universe; regime: per cycle
- blocked on: Daily price and volume histories for delisted coins are not in the verified free data (CMC snapshots are weekly; CoinGecko full history now needs a key). The weekly-snapshot approximation can run once the CMC fetcher exists.
- note: from the underlying-library library: Crypto multi-horizon trend factor (CTREND-style) on a point-in-time coin universe; harness suggestion: Shares the cmc.py fetcher with xs-crypto-momentum-weekly; underlying.py ctrend_forecast(panel, horizons, window). | added by the verifier pass

### T-504 · merger-arbitrage-options-collar

**Claim.** Collared cash-merger arbitrage on US targets with listed options earns an annualised return above the 3-month bill after option spreads, averaged across all deals in the sample.

- kind: options-strategy · origin: options-library:Arbitrage and synthetic relationships, https://en.wikipedia.org/wiki/Merger_arbitrage, https://en.wikipedia.org/wiki/Risk_arbitrage
- statistic: Mean annualised deal-level return minus the bill rate; bootstrap across deals.
- null: Mean excess return <= 0.
- procedure: For each announced cash deal: enter the collar at the first close after announcement, hold to completion or break; compute returns; bootstrap; deflated Sharpe across collar-strike choices.
- data: Deal database (announcement, offer, outcome dates; not in the listed feeds) and option chains at announcement (history begins 2026-10-14). · min n: 50
- pass: Mean excess return > 0 with the 95% CI excluding 0.
- controls: Uncollared merger-arb return as benchmark; exclude deals with competing bids; size buckets.
- blocked on: deal database plus option chains captured at announcement (chain history starts today); ~12+ months to accumulate 50 deals
- note: from the options-library library: Merger arbitrage with options (collared cash deal); harness suggestion: mandel/experiments/merger_collar.py once a deal feed exists; payoff template [underlying+, call- K=O, put+ K_p]. | added by the verifier pass

### T-509 · horizontal-time-butterfly

**Claim.** On SPY, when the ATM total-variance curvature c = w60 - (w30 + w90)/2 (w = IV^2*T from the daily chain capture) is in its top quintile, a long horizontal ATM call time butterfly (+1x30 / -2x60 / +1x90 DTE) held 10 trading days has positive mean P&L at captured mid prices.

- kind: options-strategy · origin: options-library:Time / term-structure, https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3, https://en.wikipedia.org/w/index.php?title=Calendar_spread&action=raw
- statistic: Mean 10-day P&L (per unit of 30-day ATM call premium) on top-quintile-curvature entry days
- null: Zero mean (block bootstrap); quintile label block-shifted as a placebo
- procedure: From each daily capture interpolate ATM IV at 30/60/90 DTE and compute c. Once enough history exists, enter on top-quintile days (quintile from trailing captures only), mark at mids 10 trading days later, and block bootstrap.
- data: CBOE SPY chain captures from 2026-10-14 (no history before today) · min n: 50
- pass: Mean > 0 with the 95% CI excluding 0
- controls: Quintiles use trailing data only (no look-ahead). Costs at half the spread on 6 contracts. A curvature computed from VIX/VIX3M alone is impossible (two points), so no model-priced proxy exists. Expiries are mapped to listed dates nearest 30/60/90.
- blocked on: Daily chain capture: about 250 days to form a trailing quintile and collect at least 50 top-quintile entry days; VIX/VIX3M give only two term-structure points, so no free historical proxy exists.
- note: from the options-library library: Horizontal time butterfly (same strike, three expiries); harness suggestion: Add atm_term_curve(chain_rows) to the options surface file (ATM IV at fixed 30/60/90 DTE per capture) so curvature accumulates daily; the trial then reuses the two-expiry simulator extended to three expiries. | added by the verifier pass

### T-513 · deribit-expiry-pin

**Claim.** For Deribit BTC weekly and monthly expiries, the max-pain strike measured 24h before expiry predicts the delivery price with a lower mean absolute error than the index price at that same time.

- kind: options-strategy · origin: options-library:crypto-metals-specific, https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name=BTC-30OCT26-70000-C, https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false
- statistic: Mean of (|delivery - K_mp| - |delivery - S_{T-24h}|)/S_{T-24h}
- null: Mean >= 0
- procedure: Daily (plus Thursday 08:00 UTC) book captures with OI for all strikes of the next expiry; compute K_mp; record the delivery price; paired bootstrap
- data: Deribit book captures with open_interest (from 2026-10-14); delivery prices from the API · min n: 26
- pass: 95% CI of the mean < 0
- controls: Replace K_mp with the max-OI strike; ETH; random-strike null
- blocked on: daily/Thursday Deribit book capture with OI, ~26 weekly expiries (~6 months)
- note: from the options-library library: Deribit expiry pin / max-pain iron butterfly; harness suggestion: Add OI to deribit_book captures; max-pain calculator; pin harness | added by the verifier pass

### T-518 · crude-oil-opec-eia-event-straddle

**Claim.** On OPEC+ ministerial meeting days since 2009-09, a 1-day ATM USO straddle model-priced with OVX-as-IV (sigma = OVX at the T-1 close, T = 1/252) and bought at the T-1 close has a higher mean P&L than on non-event days.

- kind: options-strategy · origin: options-library:event-driven, https://www.cboe.com/us/indices/dashboard/ovx/, https://www.optionseducation.org/strategies/all-strategies/long-straddle
- statistic: Difference in mean MODEL-PRICED long-straddle P&L (event minus non-event), bootstrap CI.
- null: Event-day mean P&L <= non-event mean P&L.
- procedure: OVX CSV (free, since 2009-09) and USO closes (free, not wired); OPEC+ meeting dates hardcoded from OPEC press releases; EIA Wednesdays as a second event set.
- data: Cboe OVX history, USO daily closes, OPEC+ meeting calendar, EIA release calendar. · min n: 40
- pass: Difference > 0 with 95% CI excluding 0.
- controls: USO roll-date exclusion; 2020-03/04 exclusion; non-event Wednesdays for EIA.
- blocked on: USO closes and OVX history fetchers (both free, not in the current data list) and an OPEC+ meeting calendar.
- note: from the options-library library: Crude-oil scheduled-event straddle (OPEC+ meetings / EIA inventory); harness suggestion: Add (USO, OVX) to the (underlying, vol index) event harness. | added by the verifier pass

### T-519 · earnings-covered-call-overwrite

**Claim.** For US large-cap holders, selling a 1x-implied-move call in the first post-earnings expiry at the T-1 close and covering at the T+1 open raises the mean T-1-to-T+1-open return of the stock position, net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write, https://api.crossref.org/works/10.1093/rfs/hhy060
- statistic: Mean of (overwrite P&L - stock-only P&L) per event, bootstrap CI.
- null: Mean difference <= 0.
- procedure: Chain captures at T-1 close and T+1 (reprice with captured IV and gap); per-event paired difference.
- data: Chain captures, daily OHLC, earnings dates. · min n: 300
- pass: Mean difference > 0 with 95% CI excluding 0 out-of-sample.
- controls: IM/HM terciles; placebo nights; drop the 5 largest upside gaps.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings overwrite (covered call sold into the print); harness suggestion: Paired 'with/without overlay' comparator on the event harness. | added by the verifier pass

### T-520 · earnings-protective-collar

**Claim.** Across US large-cap earnings, the mean T-1-close-to-T+1-open return of a zero-cost 25-delta-put collared long is not lower than the unhedged long's mean return by more than half the collar's round-trip spread cost.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/collar-protective-collar, https://www.optionseducation.org/strategies/all-strategies/protective-put-married-put
- statistic: Mean of (collar P&L - stock-only P&L) per event, bootstrap CI.
- null: Mean difference < -(half round-trip spread cost), i.e. the hedge has a real cost beyond frictions.
- procedure: Chain captures at T-1 close and T+1; paired per-event difference; report variance reduction.
- data: Chain captures, daily OHLC, earnings dates. · min n: 300
- pass: 95% CI lower bound of the difference >= -(half round-trip spread cost).
- controls: Skew deciles; sector strata; placebo nights.
- blocked on: daily chain capture through 2+ earnings seasons; earnings-date history.
- note: from the options-library library: Earnings protective collar (hedge a long through the print); harness suggestion: Same paired comparator as the overwrite; report variance and CVaR reduction. | added by the verifier pass

### T-521 · earnings-season-dispersion

**Claim.** A dollar-weighted long-dispersion book (long ATM straddles on the top 20 SPX constituents, short the ATM SPX straddle) opened 5 trading days after quarter-end and closed 25 trading days later has a positive mean P&L on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://www.optionseducation.org/strategies/all-strategies/long-straddle, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean P&L on debit per season with bootstrap CI over seasons and a per-name decomposition; implied minus realised correlation as mechanism.
- null: Mean P&L <= 0.
- procedure: Chain captures at entry/exit; realised correlation from single-name closes; one book per season (plus overlapping weekly-start variants for power).
- data: Chain captures (SPX + top 20 names), single-name closes; Cboe implied-correlation index history (free, not wired) for a longer proxy. · min n: 8
- pass: Mean > 0 with 95% CI excluding 0 over >= 8 seasons (or >= 40 overlapping weekly starts with block bootstrap).
- controls: Same book in non-earnings windows; VIX-change control; sector strata.
- blocked on: chain capture across >= 8 earnings seasons (about 2 years) or a longer proxy from Cboe implied-correlation history plus single-name closes (both not wired).
- note: from the options-library library: Earnings-season dispersion (long single-name straddles, short index straddle); harness suggestion: Basket-straddle builder from the chain store; implied vs realised correlation calculator. | added by the verifier pass

### T-523 · ipo-lockup-expiry-put-spread

**Claim.** For US IPOs with listed options, an ATM/-12% put spread in the first expiry after lockup expiry, bought 5 trading days before and sold 2 trading days after, has a positive mean return on debit net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://api.crossref.org/works/10.2139/ssrn.205011, https://www.optionseducation.org/strategies/all-strategies/bear-put-spread
- statistic: Mean return on debit with bootstrap CI; underlying abnormal return (vs IPO-sector ETF) as mechanism check.
- null: Mean return <= 0.
- procedure: Lockup dates from IPO prospectuses (EDGAR 424B4, free, not wired); chain captures at entry/exit.
- data: EDGAR prospectuses, single-name closes, chain captures. · min n: 80
- pass: Mean > 0 with 95% CI excluding 0.
- controls: VC-backed vs not; insider-share-of-float terciles; placebo windows 30 days earlier.
- blocked on: lockup-date history (EDGAR, not wired) and chain capture across ~80 lockup expiries (about 1-2 years).
- note: from the options-library library: IPO lockup-expiry bear put spread; harness suggestion: Corporate-event calendar table (lockups, spin-offs, index changes) feeding the two-window event harness. | added by the verifier pass

### T-524 · merger-arb-target-collar

**Claim.** For US all-cash deals with listed options, a target collar (long stock, short call at the highest strike <= deal price, long put near the pre-announcement price) opened at the T+1 close after announcement and held to deal close or expiry has a mean annualised return above the 3-month T-bill rate net of half-spreads.

- kind: options-strategy · origin: options-library:event-driven, https://api.crossref.org/works/10.2139/ssrn.268144, https://www.optionseducation.org/strategies/all-strategies/collar-protective-collar
- statistic: Mean annualised excess return over the FRED 3-month bill with bootstrap CI; break-rate and loss-given-break.
- null: Mean annualised excess return <= 0.
- procedure: Deal list from EDGAR (DEFM14A / SC TO-T, free, not wired); chain captures at entry; outcome from closes; excess over T-bill.
- data: EDGAR deal filings, single-name closes, chain captures, FRED 3-month bill. · min n: 60
- pass: Mean excess > 0 with 95% CI excluding 0.
- controls: Stock-only merger arb on the same deals (paired); deal-size and regulatory-risk strata; market return over the holding period.
- blocked on: deal list (EDGAR, not wired) and chain capture through deal completion (months per deal; ~60 deals ~ 1 year).
- note: from the options-library library: Merger-arbitrage collar on the target (cash deals); harness suggestion: Deal-tracker table (announce, terms, expected close, outcome) joined to chain captures; payoff engine already supports stock + options legs. | added by the verifier pass

### T-525 · digital-call-spread-vs-event-contract

**Claim.** Whenever the gap between an S&P 500 event-contract YES price and the SPXW call-spread-implied digital exceeds round-trip costs at a daily snapshot, the convergence trade (buy cheap side, sell dear side, hold to settlement) has a positive mean P&L.

- kind: options-strategy · origin: options-library:event-driven, https://docs.polymarket.com/, https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/
- statistic: Mean P&L per $1 notional with bootstrap CI; frequency of tradable gaps.
- null: Mean P&L <= 0.
- procedure: Aligned daily snapshots of SPXW chains and Kalshi/Polymarket index contracts; compute digital = (C(K)-C(K+w))/w at mids and executable sides; trade when the executable gap > costs; settle both.
- data: SPXW chain captures from 2026-10-14; Polymarket/Kalshi event-contract data (reachable). · min n: 60
- pass: Mean > 0 with 95% CI excluding 0 after fees.
- controls: Mid vs executable prices; settlement-source mismatch cases flagged; random-entry baseline.
- blocked on: aligned chain + event-contract snapshot capture (~60 trading days of matched contracts).
- note: from the options-library library: Options-implied digital vs event contract (call spread vs Kalshi/Polymarket); harness suggestion: Digital extractor (call-spread / w, plus Breeden-Litzenberger density) from the chain store, joined to the existing Polymarket/Kalshi market tables. | added by the verifier pass

### T-526 · weekend-holiday-theta

**Claim.** Market-quoted ATM SPY straddles in the next weekly expiry lose a larger share of their mid value from Friday close to Monday close than from Monday close to Tuesday close, net of the realised move.

- kind: options-strategy · origin: options-library:event-driven, https://api.crossref.org/works/10.2139/ssrn.1364721, https://www.optionseducation.org/strategies/all-strategies/short-straddle
- statistic: Mean short-straddle P&L/credit (Fri->Mon) minus (Mon->Tue), paired by week, bootstrap CI.
- null: Difference <= 0.
- procedure: Chain captures at each daily close; mark the same contract on both windows; subtract half-spread costs.
- data: Daily SPY/SPX chain captures from 2026-10-14. · min n: 30
- pass: Difference > 0 with 95% CI excluding 0 over >= 30 weeks.
- controls: Holiday weekends separately; Deribit BTC weekend vs weekday as the 24/7 control; exclude weeks with Monday macro releases.
- blocked on: daily chain capture for at least 30 weeks (traded marks are required; VIX-as-IV cannot test a pricing anomaly).
- note: from the options-library library: Weekend / holiday theta harvest (short straddle over non-trading periods); harness suggestion: Same-contract mark tracker (contract id -> daily mid path) on the chain store. | added by the verifier pass

### T-531 · put_call_iv_spread_selection

**Claim.** Weekly, equal-weight long-short portfolios of US large caps formed on the ATM call-minus-put IV spread (top minus bottom quintile) earn a positive mean return over the following week.

- kind: options-strategy · origin: options-library:relative-value-surface, https://doi.org/10.1017/S002210901000013X, https://en.wikipedia.org/wiki/Put%E2%80%93call_parity
- statistic: Mean weekly long-short return; t-stat with Newey-West errors.
- null: Mean <= 0.
- procedure: Weekly IV spreads from the captured chains (same strike and expiry, nearest-ATM, ~30 DTE), next-week returns from closes; exclude names with no bid; walk-forward; deflated Sharpe over the spread definitions tried.
- data: Daily chain capture of >= 100 US large caps (CHAIN_SYMBOLS has 3 single names today) and their daily closes. · min n: 52
- pass: Mean > 0 at p < 0.05 after 10 bps per side, positive in both halves.
- controls: Borrow-cost proxy exclusion (drop names with put IV - call IV > 5 points from known hard-to-borrow lists); size and momentum-neutral version; random-quintile placebo.
- blocked on: chain capture of >= 100 large caps (add to CHAIN_SYMBOLS) and their daily closes; >= 52 weekly cycles (~1 year).
- note: from the options-library library: Put-call IV spread (parity-deviation) stock selection; harness suggestion: New harness_iv_spread_xs on surface_summary extended with same-strike call/put IVs per name; weekly portfolio sorts in the underlying-library style. | added by the verifier pass

### T-532 · surface_static_arbitrage

**Claim.** On at least 10% of capture days, the SPY or SPX chain contains at least one butterfly, calendar or vertical spread that violates static no-arbitrage bounds at executable bid/ask prices after $0.65/contract fees.

- kind: options-strategy · origin: options-library:relative-value-surface, https://arxiv.org/abs/1204.0646, https://en.wikipedia.org/wiki/Butterfly_(options)
- statistic: Share of capture days with >= 1 executable violation (SPY or _SPX), plus the count and size of violations per day.
- null: Share of days <= 0.10.
- procedure: For each capture and expiry, check monotonicity and convexity of call and put asks/bids in strike, vertical bounds, and calendar monotonicity of total variance at matched forward moneyness. Drop quotes with zero bid or crossed markets. Exact binomial CI over capture days.
- data: Daily CBOE chain capture (SPY, _SPX) from 2026-10-14 (the first day is available now); deribit_book for the crypto twin. · min n: 30
- pass: Lower 95% bound of the share of days > 0.10; otherwise record 'no retail-executable static arbitrage' as the finding.
- controls: Mid-price scan (expected to show many more violations, so the bid/ask distinction matters); stale-quote filter sensitivity.
- blocked on: daily chain capture, 30 capture days (a one-day cross-section is available now from the 2026-10-14 capture).
- note: from the options-library library: Static-arbitrage scan of the surface (negative butterflies, calendar inversions, vertical bounds); harness suggestion: New harness_static_arb on the raw chain bundles: convexity, vertical and calendar checks per expiry, reusing harness_parity's quote filters. | added by the verifier pass

### T-537 · delta-hedged-risk-reversal

**Claim.** A 30-45 DTE SPY 25-delta risk reversal (short put, long call), entered at captured mids and delta-hedged daily to expiry, has positive mean P&L per unit put vega.

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Risk_reversal, https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- statistic: mean hedged P&L/vega with studentized block-bootstrap CI
- null: mean = 0
- procedure: Strikes from the captured chain's delta field; daily delta hedge at SPY closes using bs.greeks at the entry IVs; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY, cboe-SKEW-history (descriptive) · min n: 250
- pass: lower CI > 0 with a >10% drawdown month in the sample
- controls: Without a crash in-sample the result is biased positive, so the verdict is capped at inconclusive; report against the skew_tail harness (SKEW vs realised tails).
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Delta-Hedged Risk Reversal (skew trade); harness suggestion: Harness 'rr_skew_premium' combining the delta selector with the 'gamma_scalp_vrp' hedging loop. | added by the verifier pass

### T-538 · dispersion-trade

**Claim.** Over 2006-2026, 1-month implied correlation (COR1M) exceeds the subsequently realised average pairwise correlation of the index constituents on average, so a vega-neutral short-index/long-constituent straddle book has positive mean P&L.

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Dispersion_trading, https://cdn.cboe.com/api/global/us_indices/governance/Cboe_Implied_Correlation_Indices_Methodology.pdf
- statistic: mean of (COR1M_t - realised average correlation over t+1..t+21) with studentized block-bootstrap CI; realised correlation from constituent daily returns via sigma_idx^2 = sum w_i^2 s_i^2 + sum_{i!=j} w_i w_j s_i s_j rho
- null: mean = 0
- procedure: Monthly non-overlapping; COR1M from the archive; realised correlation from constituent or sector-ETF closes
- data: cboe-COR1M-history (archive, 2006 on), daily closes of the top-50 constituents or the 11 sector SPDRs (NOT yet captured) · min n: 240
- pass: lower CI > 0
- controls: Sector ETFs give an upward-biased realised correlation (diversified within sector), which is conservative; COR1M uses the top-50 constituents.
- blocked on: constituent or sector-ETF daily closes are not in the free data set yet (the daily-history fetcher already handles ETFs, so adding XLK..XLU bundles unblocks the proxy); a market-priced test also needs single-stock chain captures
- note: from the options-library library: Dispersion Trade (short index vol, long constituent vol); harness suggestion: Harness 'implied_vs_realised_correlation' in mandel/experiments/volatility.py with bundles ['cboe-COR1M-history','daily-history-XL*']. | added by the verifier pass

### T-539 · ladder

**Claim.** A 45-DTE SPY long put ladder (long 40-delta put, short 25-delta and 15-delta puts), entered at mid on captured chains and held to expiry, has positive mean P&L per unit naked-leg margin.

- kind: options-strategy · origin: options-library:volatility, https://en.wikipedia.org/wiki/Ladder_(option_combination)
- statistic: mean P&L/margin with studentized block-bootstrap CI
- null: mean P&L = 0
- procedure: Delta-selected strikes; mid and bid/ask; settle at expiry
- data: options-chain-SPY-<date>, daily-history-SPY · min n: 250
- pass: lower CI > 0 at bid/ask with a stress month in the sample
- controls: Rule fixed; verdict capped at inconclusive without a stress episode.
- blocked on: daily chain capture: 250 entry days including a stress episode
- note: from the options-library library: Ladder / Christmas Tree (long or short, call or put); harness suggestion: Harness 'ladder_skew' sharing the delta selector with 'front_ratio_skew'. | added by the verifier pass

### T-541 · vix-call-spread

**Claim.** 30-60 DTE VIX 25-delta/10-delta call spreads bought at captured mids and held to settlement have negative mean P&L per unit debit.

- kind: options-strategy · origin: options-library:volatility, https://www.cboe.com/tradable_products/vix/, https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf
- statistic: mean P&L/debit with studentized block-bootstrap CI; secondary: P&L conditional on a >10% SPY drawdown in the window
- null: mean = 0
- procedure: Delta-selected strikes from options-chain-VIX-<date>; settle on the published VIX settlement value
- data: options-chain-VIX-<date> (capture began 2026-10-14), cboe-VIX-history, cboe-VVIX-history (archive, descriptive) · min n: 200
- pass: upper CI < 0 with a stress month in the sample
- controls: VVIX vs realised spot-VIX vol is a partial proxy only (spot VIX is more volatile than the futures VIX options settle against, which biases the proxy against finding a premium). VIX futures history is not in the free data list.
- blocked on: VIX option chain capture: 200 entry days including a vol spike; VIX futures history not available
- note: from the options-library library: VIX Call Spread (long vol-of-vol hedge); harness suggestion: Harness 'vix_call_spread' reading options-chain-VIX-*; settlement values from CBOE. | added by the verifier pass

### T-542 · spx-parity-20-day-persistence

**Claim.** On the CBOE delayed SPX chain split by root, the share of (K, T) pairs within ATM +/- 5 strikes whose implied forward lies outside the half-spread band around the expiry median is below 2% on at least 16 of the first 20 capture days (2026-10-14 onward).

- kind: options-strategy · origin: options-library:arbitrage-synthetics, T-505
- statistic: count of capture days with share < 2% among the first 20
- null: parity deviations exceed the half-spread band (share >= 2%) on more than 4 of 20 days
- procedure: parity_v2 per capture day; count days below 2% once 20 capture days exist
- data: options-chain-SPX-* (daily raw captures), fred-DTB3 · min n: 20
- pass: >= 16 of the first 20 capture days below 2%
- controls: registered on 2026-10-15 with 2 of the 20 days already observed (2.2% and 0.5%); no day-one gate; same band and strike set as T-505
- blocked on: 20 SPX capture days (2 of 20 on 2026-10-15)
- note: pre-registered restatement of T-505 without its day-one gate, which let one noisy day decide the claim

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
