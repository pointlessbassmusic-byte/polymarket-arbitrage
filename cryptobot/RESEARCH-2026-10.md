# Research sweep, October 2026: is there an edge we are missing?

Scope: public GitHub repositories with published results, academic and
SSRN/arXiv literature on crypto return predictability, practitioner
write-ups (Quantpedia, Robot Wealth, Deribit Insights, exchange research),
free alternative data, the US venue landscape, and portfolio/risk
construction. Six independent sweeps produced 41 candidates and 29 venue
facts; a merge against the hypotheses registry left 14; each survivor was
checked through three lenses (evidence as actually published, novelty
against our registry, feasibility for a US retail operator), with the
checks that could be run on cached data run rather than argued.

## 1. Summary

1. **No public source offers a credible, costed, out-of-sample edge that
   a US retail account can trade and that this project has not already
   tested.** Of 41 candidates, 33 were dropped at merge: already killed
   here under another name, in-sample or pre-2022 evidence only, costs
   omitted, or not tradeable from the US. The 14 that survived were
   dominated by corrections and diagnostics for what we already run, not
   new alpha. That is the main finding.
2. **Two of those corrections changed the project.** (a) Selection-bias
   diagnostics (`cryptobot/stats.py`): the bounce-short's selection is
   not statistically credible after correcting for the 4,512 rules
   searched; both bounce-short entries are now `inconclusive`. (b) Cost
   and margin realism: Coinbase's $0.20 per-contract fee floor and
   92–114% overnight short margin are now modelled, and doing so exposed
   a 1000× contract-unit bug that would have sized a $1,000 PEPE slot as
   ~2,600 contracts in a live account.
3. **Everything else on the shortlist is zero or noise at our scale:**
   vol-scaled sizing, fractional Kelly, an ensemble score instead of the
   binary rule, basket substitution for unaffordable contracts, and the
   daily-loss halt (which never fired in 2022–26).
4. **Venue facts that matter:** Kalshi now lists CFTC-approved perpetuals
   on DOGE (100 DOGE ≈ $8/contract) and SHIB (1M SHIB ≈ $5) at 4 bp
   taker, which removes Coinbase's whole-contract problem for small
   accounts; Robinhood has announced DOGE perps at 1 bp but with no API;
   CME micros have no memecoins and are irrelevant below ~$50k.
5. **What to do with real money:** treat it as paying for execution
   data, not as a test of the edge. The minimum track record to show the
   strategy's Sharpe is above zero is 32–104 months; a few months of real
   P&L cannot confirm or refute it, but they can measure slippage, fill
   quality, the 4pm ET margin switch and reconciliation.

## 2. Candidates verified, and what happened to each

| candidate | verdict | what the check found |
|---|---|---|
| Overfitting diagnostics (CSCV/PBO, Deflated Sharpe, CPCV, MinTRL) | **built** | 4,512 trials, N_eff 10–59; PBO 0.09–0.22 (family not overfit); rule never in-sample best; PSR 0.87–0.99; DSR 0.00 at nominal N, 0.13–0.35 at N_eff; cross-sectional lift zero; CPCV 5/5 paths positive; MinTRL 32–104 months. Both bounce-short entries downgraded to inconclusive. |
| Cost-model realism (fee floor, spread, margin) | **built** | 0.05%/side with $0.20/contract floor (SHIB: 0.38%/side); overnight short margin 92/114/95%; contract units for 1000PEPE/1000SHIB were 1000× too small. Paper book now charges and sizes as the venue does. |
| Vol-scaled slot sizing | weak | Harvey et al. 2018: Sharpe gains only for assets with a leverage effect; here ~0 Sharpe change, 1–4 pt drawdown improvement; on whole contracts rounding dominates. |
| Integer-contract optimiser / basket substitution | inconclusive | Source author retracted his own t=3.7 result. Replayed: substitute mode $1.5k +5.4/+9.0/+8.4/+5.0/+2.2 vs off +8.9/+9.0/+11.0/+3.4/−2.6; $3k +4.5/+9.1/+34.7/−4.7/−2.8 vs +4.5/+9.1/+17.2/−7.8/−2.8. Noise. Kept as `perp.basket_mode`, off by default. |
| Fractional Kelly with shrinkage | weak | f* = 1.17 ± 0.75 of capital per trade on 152 US-3 trades; the venue's margin caps the slot at 1/3 regardless. No change to `slot_risk`. |
| Daily-loss halt vs none vs drawdown scaler | rejected | Halt fired 0 times 2022–26 in every configuration (needs three same-day stop-outs); a drawdown scaler removes 60–100% of profit. Halt kept as a harmless backstop. |
| Ensemble score over daily features | weak | The cited paper ranks factors by test-set Sharpe; incremental edge 0–0.3%/trade, undetectable within three years at SE 1.4–2.2%/trade/year. One more fitted rule also lowers DSR. |
| Third-condition gates (coin drawdown/trend, funding sign) | not pursued | `btc-trend-filter-bounce-short` already killed; Coinbase funding on these coins is 0.0001–0.002%/hour, no sign to gate on; any added condition is another selected rule. |
| Vol-targeted BTC trend sleeve | not pursued | A-grade pre-registered method, but a drawdown cutter for a long-BTC holding, not alpha; irrelevant to a memecoin-short desk unless idle cash is parked in BTC. |
| Dated-futures basis monitor (CME cash-and-carry) | not pursued | 2026 CME BTC basis 3–8% gross vs 4.2% two-year Treasury; after fees and margin drag, nothing. Park idle cash in T-bills/USDC yield instead. |
| Execution study (post-only entries, hour of day, boundary) | **do with real money** | This is what the small-real-money phase is for; see §5. |
| Crowding / positioning features | not pursued | C-grade; the cross-sectional version is already killed (`crowding-factor`); Coinbase publishes no long/short ratios. |
| COT leveraged-money / 30-day negative funding (BTC) | not pursued | BTC-only, long-horizon regime signals; a different strategy, not an improvement to this one. |
| BTC outside-US-hours seasonality | **tested, inconclusive** (pre-registered, `btc-offhours-seasonality`) | 1,504 holdings 2021–2026 on Coinbase hourly data: +0.076%/holding net at 0.08%, PSR 0.84; post-publication window (2024-11 on) +6.9% over 504 holdings, t = 0.14; negative at Coinbase fees. Real through 2024, flat since. |

Dropped at merge (33), grouped: cross-sectional momentum/reversal/carry
factors on 100+ Binance coins (not tradeable in the US; our 176-coin
versions were killed); liquidation-cascade and order-book signals
(intraday, negative after fees in the one quantitative study); weekend
vol selling (Deribit, not available to US retail); ETF-flow and
stablecoin-supply predictors (BTC daily, in-sample); Kalshi/Polymarket
cross-venue arbitrage (three overlapping markets, no depth); Coinbase
listing effects (killed here); LightGBM cross-sectional forecasts (net
Sharpe 1.45 in-sample, deflated 0.12 by the authors themselves);
intraday reversal (gross edge below the bid-ask bounce); Kalshi rain
markets (not crypto, and the author's own replication shrank it).

## 3. Why the sweep came back thin

- The public record of crypto strategies is mostly 2020–21 bull data
  with no costs. The few pre-registered, costed, post-2022 studies
  (crypto-trend-research, crypto-fundingrate-alpha, edgeproof, the
  strategy-graveyard repo) report null or risk-management results, which
  agrees with our own registry.
- The strategies with real evidence (cross-sectional factors on 100+
  coins, funding carry on 150 perps, options vol selling) need venues a
  US resident cannot use. US venues list three memecoin perps.
- Most "improve the model" proposals are sizing overlays. On a strategy
  with ~30 trades a year per coin, a sizing overlay cannot be
  distinguished from noise in less time than it takes the strategy to
  prove itself.

## 4. US venue facts (verified 2026-10-07/08)

| venue | memecoin instruments | contract | fees | notes |
|---|---|---|---|---|
| Coinbase Derivatives | DOGE, 1000PEPE, 1000SHIB perpetual-style | 5,000 DOGE (~$420), 100,000×1000PEPE (~$380), 10,000×1000SHIB (~$53) | 0.05%/side, $0.20/contract minimum | overnight short margin 92/114/95% (no leverage on shorts); funding hourly, 0.0001–0.002%/h; public candles since 2025-12; one CDP key for spot and futures |
| Kalshi perpetuals | KXDOGEPERP (100 DOGE ≈ $8), KXKSHIBPERP (1M SHIB ≈ $5); no PEPE | tiny | 4 bp taker / 2 bp maker (entry tier) | CFTC-approved 2026-05-29, trading since June; CF Benchmarks index; funding 3×/day capped ±2%; API with RSA signing; CME is suing the CFTC over the approval (D.D.C. 1:26-cv-01763) |
| Kraken US (Bitnomial) | 16 perps incl. DOGE, SHIB; no PEPE | per Trade page | $0.15/contract/side all-in | API availability for US accounts unconfirmed |
| Robinhood (announced 2026-09-30) | BTC, ETH, SOL, XRP, DOGE, ADA, LINK, HYPE | — | 1 bp promotional | no API; unusable by a bot until one exists |
| CME micros | none | 0.1 BTC (~$8k), 0.1 ETH, 25 SOL, 2,500 XRP | ~$1–2/contract via IBKR/Tradovate | Section 1256 tax treatment; irrelevant below ~$50k |
| Polymarket US | BTC up/down families documented, not live | — | taker 0.0695·p(1−p), maker rebate | the killed Up/Down verdicts transfer |

Tax: CME futures are Section 1256 (60/40, marked to market); Coinbase and
Kalshi perpetual-style contracts are not settled 1256 instruments; wash
sale rules do not currently apply to crypto property but bills are
pending; Form 1099-DA gross proceeds reporting started for tax year 2025.

## 5. Small real money: the protocol

Real money here buys execution data. The edge cannot be confirmed by a
few months of live trading (MinTRL 32–104 months), so the gates are about
execution and operations, never about P&L.

**Gate 0, before any order (done or in `--preflight`):** units pinned to
the API's `contract_size`; fee floor and overnight margin in the sim;
order preview accepted for one contract of each coin; reconciliation
and alerts live; `.env` with a trade-only CDP key; seed history built.

**Gate 1, paper for 4+ weeks on the Linode.** Pass when: no crash, no
venue mismatch, every daily run logged, digest arriving, at least one
full trade cycle (entry, hourly funding accrual, exit) in the paper book.

**Gate 2, one contract.** Set `risk.bankroll_usd` so one slot is exactly
one SHIB contract (~$160 bankroll at 1/3 slots) or, for DOGE/PEPE, one
contract each (~$1,500). Arm. Run 6–8 weeks. Measure, per fill:
realised slippage vs the signal close (entry at 00:10 UTC is a thin
hour), fill latency, whether the 16:00 ET intraday→overnight margin
switch ever moves margin usage above 90%, fee charged vs modelled
(confirm the $0.20 floor on SHIB), and the sim-vs-real gap in the
digest. Pass when the real book tracks the sim within the modelled
costs (gap explained by fees + measured slippage) and reconciliation
never disagrees.

**Gate 3, size whose loss you can shrug off.** $1,500–$3,000. Expect the
lumpy year-by-year numbers in the README table, including negative
years; the point is still measurement, now of whole-contract skips and
of how often DOGE/PEPE are unaffordable.

**Gate 4, scale only on execution evidence, not on P&L.** If the
sim-vs-real gap stays inside modelled costs for a quarter, increase to
the size where all three contracts fit (~$6,000). Never scale because a
quarter was profitable; the diagnostics say that is noise.

**Stops the ramp:** any reconciliation mismatch you cannot explain; a
real fill more than 0.5% worse than the signal price twice in a month; a
margin-switch event; a fee charge that does not match the model; the
registry verdict moving to killed.

Kalshi is the alternative for the smallest sizes: its ~$8 DOGE and ~$5
SHIB contracts make whole-contract rounding irrelevant at $200, with 4 bp
fees. It needs a new executor (RSA-signed REST), a liquidity check on
those two books, and the same gates. It does not list PEPE.

## 6. If there were no constraints except US legality

**Thesis.** The scarce resource is not capital; it is credible evidence.
With unlimited capital the right move is still to run small, because the
strategy's expected return after deflating for the search is close to
zero with wide error bars, and nothing in the public record offers a
better-evidenced US-tradeable replacement. Capital should go where the
evidence is strongest per dollar of risk, which today is mostly nowhere.

**Venues and instruments.** Coinbase Derivatives for DOGE/PEPE/SHIB (the
only US PEPE listing); Kalshi perps for DOGE/SHIB at small size and for a
second quote on the same coins; Kraken US as a cold standby. CME micros
only for a BTC/ETH sleeve, which this desk does not have an edge in.

**Strategy set and sizing.** One slot per coin at 1× (the venue allows
nothing else on shorts), bounce-short as deployed, no overlays (every
overlay tested is zero or negative). Expected: shrink the backtest's
+9–15%/year toward 0–5% with −20% drawdowns possible; no leverage; no
carry in the US (funding ≈ 0). Idle cash in T-bills or a money-market
fund, not in a basis trade.

**Data and infrastructure.** Already sufficient for the daily strategy:
Coinbase public candles stitched to seeded Hyperliquid history, hourly
funding and margin read live, the Linode, Docker, alerts, digest,
reconciliation. What is missing and worth building:
1. **Own fill and funding log** (Coinbase exposes no funding history and
   no fill history beyond orders): every fill, fee, funding settlement
   and margin snapshot to a JSONL in `state/`, so the execution study in
   §5 has data.
2. **Kalshi executor** for the small-contract venue.
3. **A pre-registration file** for any future rule: write the rule,
   universe, horizon, costs and success criterion before running it, and
   record `trials_run` as the registry now requires. The DSR result is
   the cost of not having done this from the start.

**Validation protocol.** Per the registry rule adopted this month: a
rule is `alive` only with DSR ≥ 0.95 at N_eff, PBO ≤ 0.5, ≥ 80% of CPCV
paths positive, and trials_run recorded. The bounce-short does not meet
it and is run as inconclusive at small size.

**What the current system was missing, now fixed or recorded:**
multiplicity correction; per-contract fees; overnight margin; correct
contract units; a statement of what the edge is (basket timing, not coin
selection); a track-record counter in the digest.

**Realistic expectation.** With $1.5k–$6k on Coinbase: a strategy whose
backtest says +9% to +15% a year on capital, whose deflated evidence says
the true number could be zero, trading three thin contracts with a
whole-contract constraint. Plan for returns anywhere from −20% to +30% in
a given year and for the record to stay uninformative for years. Anyone
promising more from this data is selecting from noise.

## 7. Searched and empty, so it is not repeated

freqtrade/jesse/hummingbot/nautilus/passivbot strategy collections
(logic without costed OOS results); "funding rate arbitrage bot" repos
(none with results on US venues); cross-exchange arbitrage repos (spreads
inside fees, as our own test found); Kalshi/Polymarket arbitrage bots
(three overlapping markets); Liu–Tsyvinski–Wu factor replications
post-2022 (momentum decayed, size/reversal in illiquid coins only);
order-book wall and liquidation signals (negative after fees);
LightGBM/LSTM directional models on 15-minute perps (deflated Sharpe
≈ 0); Coinbase fee pages (HTTP 403 to fetches; the $0.20 floor comes
from Coinbase's blog and should be confirmed on the first real fill).
